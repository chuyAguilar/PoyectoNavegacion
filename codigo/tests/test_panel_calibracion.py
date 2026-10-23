"""La calibracion desde el panel, como la de la sesion en vivo (meta 002, fase 4; P18). Sin Qt y sin camara.

- recetas: las medidas del calibrador, las casillas por medida, el reporte y la luz en el argv de
  calibrar_camara.py; el detector "ambos"; la receta de comprobar_escala.py; los valores invalidos paran.
- perfil_editor: los escalares del .yml (detector, lado, criterio) y cuando se ofrece apuntar el perfil.
- Las recetas componen el comando: ninguna prueba lanza un proceso ni abre una camara.
"""
from __future__ import annotations

import numpy as np
import pytest
import yaml

import calibrar_camara as cc
import comprobar_escala as ce
import perfil_editor
import recetas

from .conftest import ITER4_DIR

PERFIL_GS1 = str(ITER4_DIR / "tracker_config_gs1.yaml")
MEDIDAS_P17 = [149.1, 149.1, 149.1, 149.1, 149.4]     # clarify.md P17: 6 casillas -> 24.86 mm


def _a(argv, bandera):
    return argv[argv.index(bandera) + 1]


# ----------------------------------------------------------------------------
# Medidas y lado
# ----------------------------------------------------------------------------

def test_parsear_medidas() -> None:
    assert recetas.parsear_medidas("149.1, 149.1, 149.1, 149.1, 149.4") == MEDIDAS_P17
    assert recetas.parsear_medidas("149.1;149.1 149.4") == [149.1, 149.1, 149.4]
    assert recetas.parsear_medidas([99.9, "99.85"]) == [99.9, 99.85]
    assert recetas.parsear_medidas("") == []
    for malo in ("149,1 149,2x", "abc", "149.1, -2", "0, 100"):
        with pytest.raises(ValueError):
            recetas.parsear_medidas(malo)


@pytest.mark.parametrize("medidas,casillas", [
    (MEDIDAS_P17, 6), ([99.90, 99.85, 99.92, 99.88, 99.86], 4), ([25.01, 24.99, 25.0, 25.02, 24.98], 1),
    ([149.8] * 4, 6),
])
def test_lado_de_medidas_es_la_cuenta_de_calibrar_camara(medidas, casillas) -> None:
    assert recetas.lado_de_medidas(medidas, casillas) == cc.lado_desde_medidas(medidas, casillas)


def test_lado_de_medidas_p17_y_errores() -> None:
    assert recetas.lado_de_medidas(MEDIDAS_P17, 6) == 24.86
    with pytest.raises(ValueError):
        recetas.lado_de_medidas([], 4)
    with pytest.raises(ValueError):
        recetas.lado_de_medidas(MEDIDAS_P17, 0)


def test_reporte_por_defecto_y_valor_arg() -> None:
    assert recetas.reporte_por_defecto("../Claude outputs/camaras/vistas_gs2", "gs2", "ambos") == \
        "../Claude outputs/camaras/calibracion_gs2_ambos.json"
    assert recetas.valor_arg(["a", "--output", "x.yml"], "--output") == "x.yml"
    assert recetas.valor_arg(["a", "--output"], "--output") is None and recetas.valor_arg([], "--x") is None


# ----------------------------------------------------------------------------
# receta_calibrar_camara con medidas, reporte, luz y "ambos"
# ----------------------------------------------------------------------------

def test_receta_calibrar_camara_como_la_sesion_en_vivo() -> None:
    r = recetas.receta_calibrar_camara(
        PERFIL_GS1, "iter4/data/intrinsecos_gs1_1280x960.yml", 24.86, "../Claude outputs/camaras/vistas_gs1",
        detector="ambos", luz="caja nivel 2", medidas_mm=MEDIDAS_P17, casillas_por_medida=6,
        reporte="../Claude outputs/camaras/calibracion_gs1_ambos.json")
    a = r.argv
    assert a[2] == "iter4/calibrar_camara.py" and _a(a, "--square-mm") == "24.86" and _a(a, "--detector") == "ambos"
    assert _a(a, "--medidas-mm") == "149.1,149.1,149.1,149.1,149.4" and _a(a, "--casillas-por-medida") == "6"
    assert _a(a, "--luz") == "caja nivel 2" and _a(a, "--reporte").replace("\\", "/").endswith("calibracion_gs1_ambos.json")
    assert _a(a, "--n-control") == "3" and _a(a, "--min-vistas") == "15" and _a(a, "--timeout") == "900"
    assert len(r.outputs) == 2 and r.outputs[1].replace("\\", "/").endswith("calibracion_gs1_ambos.json")
    assert r.ventana_titulo == cc.TITULO_VENTANA and r.usa_camara
    # El argv lo acepta calibrar_camara.py (lado y medidas coherentes): se comprueba con su propia funcion.
    assert cc.comprobar_lado(24.86, cc._parsear_medidas(_a(a, "--medidas-mm")), 6) == 24.86
    assert "ambos" in cc.MODOS_DETECTOR


def test_receta_calibrar_camara_sin_medidas_solo_lado() -> None:
    r = recetas.receta_calibrar_camara(PERFIL_GS1, "x.yml", 24.86, "v", detector="ambos")
    assert "--medidas-mm" not in r.argv and "--casillas-por-medida" not in r.argv
    assert "--reporte" not in r.argv and "--luz" not in r.argv and r.outputs == [recetas._rel("x.yml")]


@pytest.mark.parametrize("kwargs", [
    {"medidas_mm": MEDIDAS_P17[:4], "casillas_por_medida": 6},          # < 5 medidas
    {"medidas_mm": MEDIDAS_P17, "casillas_por_medida": 4},              # 37.29 != 24.86
    {"medidas_mm": "149.1, abc", "casillas_por_medida": 6},
    {"medidas_mm": [149.1, 149.1, 149.1, 149.1, -1.0], "casillas_por_medida": 6},
    {"medidas_mm": MEDIDAS_P17, "casillas_por_medida": 0},
    {"detector": "ambos", "n_control": 0},                              # ambos elige por el control
    {"detector": "todos"},
])
def test_receta_calibrar_camara_valores_invalidos_paran(kwargs) -> None:
    base = {"output": "x.yml", "square_mm": 24.86, "vistas_dir": "v"}
    base.update(kwargs)
    with pytest.raises(ValueError):
        recetas.receta_calibrar_camara(PERFIL_GS1, **base)


# ----------------------------------------------------------------------------
# receta_comprobar_escala
# ----------------------------------------------------------------------------

def test_receta_comprobar_escala_como_la_sesion_en_vivo() -> None:
    r = recetas.receta_comprobar_escala(PERFIL_GS1, 24.859999999999999, "sb", recetas.POSICIONES_ESCALA,
                                        "../Claude outputs/camaras/escala_gs1.json", luz="caja nivel 2")
    a = r.argv
    assert a[2] == "iter4/comprobar_escala.py" and _a(a, "--config").endswith("tracker_config_gs1.yaml")
    assert _a(a, "--square-mm") == "24.86" and _a(a, "--detector") == "sb"
    assert _a(a, "--desplazamientos-mm") == "0,80,0,80,0,80" and _a(a, "--frames-por-posicion") == "30"
    assert _a(a, "--luz") == "caja nivel 2" and _a(a, "--salida").replace("\\", "/").endswith("escala_gs1.json")
    assert _a(a, "--cols") == "8" and _a(a, "--rows") == "5" and _a(a, "--timeout") == "900"
    assert r.clave == "comprobar_escala" and r.ventana_titulo == ce.VENTANA and r.usa_camara
    assert r.outputs == [recetas._rel("../Claude outputs/camaras/escala_gs1.json")]
    # Lo que el script hace con las posiciones
    assert ce._parsear_lista(_a(a, "--desplazamientos-mm")) == [0.0, 80.0, 0.0, 80.0, 0.0, 80.0]
    r2 = recetas.receta_comprobar_escala(PERFIL_GS1, 24.86, "clasico", [0, 100.5, 200], "e.json")
    assert _a(r2.argv, "--desplazamientos-mm") == "0,100.5,200" and "--luz" not in r2.argv


@pytest.mark.parametrize("kwargs", [
    {"detector": "ambos"}, {"detector": "raro"}, {"desplazamientos_mm": "0"}, {"desplazamientos_mm": ""},
    {"desplazamientos_mm": "0,8o"}, {"square_mm": 0.0}, {"square_mm": "x"}, {"salida": ""},
    {"frames_por_posicion": 0},
])
def test_receta_comprobar_escala_valores_invalidos_paran(kwargs) -> None:
    base = {"square_mm": 24.86, "detector": "sb", "desplazamientos_mm": "0,80", "salida": "e.json"}
    base.update(kwargs)
    with pytest.raises(ValueError):
        recetas.receta_comprobar_escala(PERFIL_GS1, **base)


def test_detectores_de_la_receta_y_de_los_scripts() -> None:
    assert set(recetas.DETECTORES_ESCALA) == set(ce.DETECTORES) == set(cc.DETECTORES)
    assert set(recetas.DETECTORES_CALIBRACION) == set(cc.MODOS_DETECTOR)
    assert recetas.DETECTORES_CALIBRACION[0] == "ambos"           # el del dialogo por defecto


# ----------------------------------------------------------------------------
# perfil_editor: el .yml y la oferta de apuntar el perfil
# ----------------------------------------------------------------------------

K = np.array([[849.94, 0.0, 603.56], [0.0, 848.88, 488.87], [0.0, 0.0, 1.0]])


def _yml(tmp_path, nombre="intrinsecos_gs9_1280x960.yml", cumplido=True):
    ruta = tmp_path / nombre
    extra = {"detector": "sb", "rms_control_px": 0.1458, "luz": "caja nivel 2", "criterio_cumplido": cumplido,
             "criterio": {"rms_px": 0.5, "rms_control_px": 0.75}, "detector_comparacion": {"clasico": 0.18, "sb": 0.15},
             "vistas_dir": "..\\Claude outputs\\camaras\\vistas_gs9"}
    cc.guardar_yml(ruta, K, np.zeros(5), 1280, 960, 0.167, 20, 8, 5, 24.86, extra)
    return ruta


def test_leer_campos_yml(tmp_path) -> None:
    c = perfil_editor.leer_campos_yml(_yml(tmp_path))
    assert c["detector"] == "sb" and float(c["square_mm"]) == pytest.approx(24.86)
    assert c["criterio_cumplido"] == "1" and float(c["rms_control_px"]) == pytest.approx(0.1458)  # el de 1er nivel
    assert c["luz"] == "caja nivel 2" and c["image_width"] == "1280" and c["image_height"] == "960"
    assert "camera_matrix" not in c and "clasico" not in c
    # Un archivo con CRLF da lo mismo
    crlf = tmp_path / "crlf.yml"
    crlf.write_bytes(_yml(tmp_path, "otro.yml").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert perfil_editor.leer_campos_yml(crlf)["detector"] == "sb"


def test_ofrecer_apuntar(tmp_path) -> None:
    bueno = _yml(tmp_path)
    assert perfil_editor.ofrecer_apuntar(0, bueno, "", tmp_path) == (True, f"data/{bueno.name}")
    assert perfil_editor.ofrecer_apuntar(0, bueno, "data/otro.yml", tmp_path) == (True, f"data/{bueno.name}")
    ok, motivo = perfil_editor.ofrecer_apuntar(1, bueno, "", tmp_path)
    assert not ok and "exit 1" in motivo
    ok, motivo = perfil_editor.ofrecer_apuntar(0, bueno, f"data/{bueno.name}", tmp_path)
    assert not ok and "ya apunta" in motivo
    ok, motivo = perfil_editor.ofrecer_apuntar(0, _yml(tmp_path, "malo.yml", cumplido=False), "", tmp_path)
    assert not ok and "criterio" in motivo
    ok, motivo = perfil_editor.ofrecer_apuntar(0, tmp_path / "no_existe.yml", "", tmp_path)
    assert not ok and "no existe" in motivo


def test_apuntar_sobre_una_copia_del_perfil_con_backup(tmp_path) -> None:
    """El mecanismo de siempre (ADR-018) sobre una COPIA del perfil gs1: una sola linea, con backup."""
    copia = tmp_path / "tracker_config_gs1.yaml"
    copia.write_bytes(open(PERFIL_GS1, "rb").read())
    ok, valor = perfil_editor.ofrecer_apuntar(0, _yml(tmp_path), "data/intrinsecos_gs1_1280x960.yml", tmp_path)
    assert ok
    backup, _antes, despues = perfil_editor.aplicar_cambio(copia, valor)
    assert backup.exists() and despues.strip() == f"calibration_file: {valor}"
    cfg = yaml.safe_load(copia.read_text(encoding="utf-8"))
    assert cfg["camera"]["calibration_file"] == valor
    assert open(PERFIL_GS1, "rb").read() == backup.read_bytes()      # el perfil real no se toco
