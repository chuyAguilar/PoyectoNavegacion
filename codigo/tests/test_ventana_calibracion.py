"""La ventana «Calibrar cámara» del panel, sin Qt y sin cámara (meta 002, fase 5; P19, P20, P21).

- El tablero guardado (data/tablero_calibracion.yaml): se lee, se reescribe en un temporal, los
  valores inválidos paran.
- Las tres recetas que compone la ventana para un perfil: enfocar (medir_modos.py --enfocar con el
  modo del perfil), calibrar (con el tablero guardado y lo fijo) y comprobar la escala (con el lado y
  el detector del .yml, y las idas y vueltas).
- «Última …» de cada paso, en lenguaje llano, desde JSON/.yml temporales.
Ninguna prueba lanza un proceso ni abre una cámara: las recetas solo componen el comando.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

from gui import calibration_window as calibracion
from calibration import calibrate_camera as cc
from calibration import check_scale as ce
from diagnostics import measure_modes as mm
from gui import recipes as recetas

from .conftest import DATA_DIR, PROFILES_DIR

PERFIL_GS1 = str(PROFILES_DIR / "tracker_config_gs1.yaml")
MEDIDAS_P17 = [149.1, 149.1, 149.1, 149.1, 149.4]


def _a(argv, bandera):
    return argv[argv.index(bandera) + 1]


def _cfg(**cam):
    base = {"camera_type": "webcam", "usb_port_windows": "PCIROOT(0)#USB(3)", "width": 1280, "height": 960,
            "fps": 90, "fourcc": "MJPG", "backend": "MSMF"}
    base.update(cam)
    return {"camera": base}


# ----------------------------------------------------------------------------
# El tablero guardado
# ----------------------------------------------------------------------------

def test_el_tablero_versionado_es_el_de_p17() -> None:
    t = calibracion.leer_tablero(DATA_DIR / "tablero_calibracion.yaml")
    assert calibracion.RUTA_TABLERO == DATA_DIR / "tablero_calibracion.yaml"
    assert t.casillas == (9, 6) and t.esquinas == (8, 5) and t.medidas_mm == MEDIDAS_P17
    assert t.casillas_por_medida == 6 and t.lado_mm == 24.86 and t.fecha == "2026-10-22"
    assert t.lado_mm == cc.lado_desde_medidas(MEDIDAS_P17, 6)


def test_escribir_y_volver_a_leer_el_tablero(tmp_path) -> None:
    ruta = tmp_path / "tablero.yaml"
    ruta.write_bytes((DATA_DIR / "tablero_calibracion.yaml").read_bytes())
    t = calibracion.escribir_tablero(ruta, "99.9, 99.8, 99.9, 99.9, 99.6", 4)
    assert t.casillas == (9, 6) and t.lado_mm == 24.96 and t.fecha == time.strftime("%Y-%m-%d") and t.fuente == "panel"
    leido = calibracion.leer_tablero(ruta)
    assert leido.medidas_mm == [99.9, 99.8, 99.9, 99.9, 99.6] and leido.casillas_por_medida == 4
    assert leido.lado_mm == 24.96 and leido.esquinas == (8, 5)
    assert ruta.read_text(encoding="utf-8").startswith("# Tablero de calibracion")
    assert not (tmp_path / "tablero.yaml.tmp").exists()
    # Sin archivo previo: 9x6
    assert calibracion.escribir_tablero(tmp_path / "nuevo.yaml", MEDIDAS_P17, 6).casillas == (9, 6)


@pytest.mark.parametrize("medidas,cuadros", [
    ("149.1, 149.1, 149.1, 149.1", 6),          # 4 medidas
    ("149.1, abc, 149.1, 149.1, 149.4", 6),
    ("149.1, 149.1, 149.1, 149.1, -1", 6),
    (MEDIDAS_P17, 0), (MEDIDAS_P17, 10),
    ("1, 1, 1, 1, 1", 1),                        # 1 mm por cuadro: fuera de rango
])
def test_escribir_tablero_invalido_para_y_no_toca_el_archivo(tmp_path, medidas, cuadros) -> None:
    ruta = tmp_path / "tablero.yaml"
    ruta.write_bytes((DATA_DIR / "tablero_calibracion.yaml").read_bytes())
    antes = ruta.read_bytes()
    with pytest.raises(ValueError):
        calibracion.escribir_tablero(ruta, medidas, cuadros)
    assert ruta.read_bytes() == antes


@pytest.mark.parametrize("cambio", [
    {"esquinas_horizontales": 9},                 # tienen que ser casillas - 1
    {"lado_mm": 25.0},                            # no sale de las medidas
    {"medidas_mm": [149.1, 149.1]},
    {"medidas_mm": "149.1"},
    {"casillas_por_medida": 12},
    {"casillas_horizontales": "9"},
    {"lado_mm": "x"},
])
def test_leer_tablero_invalido_para(tmp_path, cambio) -> None:
    import yaml
    d = yaml.safe_load((DATA_DIR / "tablero_calibracion.yaml").read_text(encoding="utf-8"))
    d.update(cambio)
    ruta = tmp_path / "t.yaml"
    ruta.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(ValueError):
        calibracion.leer_tablero(ruta)
    with pytest.raises(OSError):
        calibracion.leer_tablero(tmp_path / "no_existe.yaml")
    (tmp_path / "roto.yaml").write_text("casillas: [9, 6\n", encoding="utf-8")
    with pytest.raises(ValueError):
        calibracion.leer_tablero(tmp_path / "roto.yaml")


# ----------------------------------------------------------------------------
# Las tres recetas
# ----------------------------------------------------------------------------

def test_receta_enfocar_y_su_ventana() -> None:
    r = recetas.receta_enfocar(PERFIL_GS1, 1280, 960, "MJPG", 90, "../Claude outputs/camaras/enfoque_gs1.json",
                               luz="caja nivel 2")
    a = r.argv
    assert a[2:4] == ["-m", "diagnostics.measure_modes"] and "--enfocar" in a and _a(a, "--modo") == "1280x960:MJPG"
    assert _a(a, "--fps") == "90" and _a(a, "--timeout") == "600" and _a(a, "--luz") == "caja nivel 2"
    assert _a(a, "--salida").replace("\\", "/").endswith("enfoque_gs1.json")
    assert r.clave == "enfocar" and r.usa_camara and r.ventana_titulo == mm.VENTANA
    assert r.outputs == [recetas._rel("../Claude outputs/camaras/enfoque_gs1.json")]


@pytest.mark.parametrize("kwargs", [
    {"ancho": None}, {"ancho": 0}, {"fps": "x"}, {"fourcc": "MJ"}, {"fourcc": None}, {"salida": ""},
])
def test_receta_enfocar_invalida_para(kwargs) -> None:
    base = {"ancho": 1280, "alto": 960, "fourcc": "MJPG", "fps": 90, "salida": "e.json"}
    base.update(kwargs)
    with pytest.raises(ValueError):
        recetas.receta_enfocar(PERFIL_GS1, **base)


def test_salidas_del_perfil() -> None:
    s = calibracion.salidas_del_perfil(PERFIL_GS1, _cfg())
    assert s["slug"] == "gs1" and s["yml"] == "data/intrinsecos_gs1_1280x960.yml"
    assert s["reporte"] == "../Claude outputs/camaras/calibracion_gs1_ambos.json"
    assert s["escala"].endswith("escala_gs1.json") and s["enfoque"].endswith("enfoque_gs1.json")
    with pytest.raises(ValueError):
        calibracion.salidas_del_perfil(PERFIL_GS1, _cfg(width=None))


def test_receta_enfocar_del_perfil() -> None:
    r = calibracion.receta_enfocar_perfil(PERFIL_GS1, _cfg())
    assert _a(r.argv, "--modo") == "1280x960:MJPG" and _a(r.argv, "--fps") == "90"
    assert _a(r.argv, "--config").endswith("tracker_config_gs1.yaml")
    with pytest.raises(ValueError):
        calibracion.receta_enfocar_perfil(PERFIL_GS1, _cfg(usb_port_windows=None))


def test_receta_calibrar_con_el_tablero_guardado() -> None:
    t = calibracion.leer_tablero(DATA_DIR / "tablero_calibracion.yaml")
    a = calibracion.receta_calibrar_perfil(PERFIL_GS1, _cfg(), t).argv
    assert _a(a, "--square-mm") == "24.86" and _a(a, "--cols") == "8" and _a(a, "--rows") == "5"
    assert _a(a, "--detector") == "ambos" and _a(a, "--min-vistas") == "15" and _a(a, "--n-control") == "3"
    assert _a(a, "--medidas-mm") == "149.1,149.1,149.1,149.1,149.4" and _a(a, "--casillas-por-medida") == "6"
    assert _a(a, "--luz") == "caja nivel 2" and _a(a, "--timeout") == "900"
    assert _a(a, "--output").replace("\\", "/") == "data/intrinsecos_gs1_1280x960.yml"
    assert _a(a, "--reporte").replace("\\", "/").endswith("calibracion_gs1_ambos.json")
    assert cc.comprobar_lado(24.86, cc._parsear_medidas(_a(a, "--medidas-mm")), 6) == 24.86
    assert calibracion.LIMITE_ERROR_PX == cc.CRITERIO["rms_control_px"]


def test_posiciones_ida_vuelta() -> None:
    assert calibracion.posiciones_ida_vuelta(80, 3) == [0.0, 80.0, 0.0, 80.0, 0.0, 80.0]
    assert calibracion.posiciones_ida_vuelta(100, 1) == [0.0, 100.0]
    for malo in ((0, 3), (80, 0), ("x", 3)):
        with pytest.raises(ValueError):
            calibracion.posiciones_ida_vuelta(*malo)
    # comprobar_escala.py lo acepta y juzga por medias
    assert ce.hay_repeticiones(ce._parsear_lista(",".join(recetas._num(p) for p in
                                                          calibracion.posiciones_ida_vuelta(80, 3))))


def _yml(tmp_path, detector="sb", cumplido=True, nombre="intrinsecos_gs9_1280x960.yml"):
    ruta = tmp_path / nombre
    extra = {"detector": detector, "rms_control_px": 0.1500, "criterio_cumplido": cumplido} if detector else {}
    cc.guardar_yml(ruta, np.eye(3) * 836.7, np.zeros(5), 1280, 960, 0.154, 23, 8, 5, 24.86, extra)
    return ruta


def test_receta_escala_con_el_yml_del_perfil(tmp_path) -> None:
    t = calibracion.leer_tablero(DATA_DIR / "tablero_calibracion.yaml")
    a = calibracion.receta_escala_perfil(PERFIL_GS1, _yml(tmp_path), t, 80, 3).argv
    assert a[2:4] == ["-m", "calibration.check_scale"] and _a(a, "--square-mm") == "24.86" and _a(a, "--detector") == "sb"
    assert _a(a, "--desplazamientos-mm") == "0,80,0,80,0,80" and _a(a, "--cols") == "8" and _a(a, "--rows") == "5"
    assert _a(a, "--salida").replace("\\", "/").endswith("escala_gs1.json") and _a(a, "--timeout") == "900"
    a2 = calibracion.receta_escala_perfil(PERFIL_GS1, _yml(tmp_path, "clasico"), t, 100, 2).argv
    assert _a(a2, "--desplazamientos-mm") == "0,100,0,100" and _a(a2, "--detector") == "clasico"
    with pytest.raises(ValueError):          # un .yml sin detector (anterior a la fase 4)
        calibracion.receta_escala_perfil(PERFIL_GS1, _yml(tmp_path, None, nombre="viejo.yml"), t)


# ----------------------------------------------------------------------------
# «Última …» de cada paso
# ----------------------------------------------------------------------------

def test_dia_mes() -> None:
    assert calibracion.dia_mes("2026-10-23 14:05:49") == "23-10"
    assert calibracion.dia_mes("") == "" and calibracion.dia_mes(None) == "" and calibracion.dia_mes("ayer") == ""
    # La fecha UTC del .yml pasa a la hora local (la del equipo)
    utc = "2026-10-23T04:25:00+00:00"
    from datetime import datetime
    local = datetime.fromisoformat(utc).astimezone()
    assert calibracion.dia_mes(utc) == f"{local.day:02d}-{local.month:02d}"


def test_ultima_nitidez(tmp_path) -> None:
    ruta = tmp_path / "enfoque.json"
    assert calibracion.ultima_nitidez(ruta) == "—"
    ruta.write_text(json.dumps({"fecha": "2026-10-22 16:12:53", "modo": "enfocar",
                                "enfoque": {"nitidez": 156.0, "nitidez_max": 170.7}}), encoding="utf-8")
    assert calibracion.ultima_nitidez(ruta) == "nitidez 156 (22-10)"
    ruta.write_text(json.dumps({"fecha": "2026-10-22 16:12:53", "error": "puerto"}), encoding="utf-8")
    assert "no se pudo medir" in calibracion.ultima_nitidez(ruta)


def test_ultima_calibracion_el_mas_nuevo(tmp_path) -> None:
    reporte = tmp_path / "calibracion_gs9_ambos.json"
    yml = _yml(tmp_path)
    assert calibracion.ultima_calibracion(tmp_path / "no.json", tmp_path / "no.yml") == ("—", None)
    texto, ok = calibracion.ultima_calibracion(reporte, yml)          # solo el .yml
    assert ok is True and "error 0.15 píxeles (aceptable hasta 0.75)" in texto and texto.startswith("Calibrada el ")
    reporte.write_text(json.dumps({"fecha": "2026-10-23 14:05:49", "criterio": {"rms_control_px": 0.75},
                                   "resultado": {"rms_control_px": 0.9, "cumple": False}}), encoding="utf-8")
    os.utime(yml, (time.time() - 100, time.time() - 100))             # el reporte es el mas nuevo
    texto, ok = calibracion.ultima_calibracion(reporte, yml)
    assert ok is False and texto.startswith("Calibrada el 23-10 · error 0.90 píxeles") and "no salió bien" in texto
    reporte.write_text(json.dumps({"fecha": "2026-10-23 14:05:49", "error": "ningun detector calibro"}), encoding="utf-8")
    texto, ok = calibracion.ultima_calibracion(reporte, yml)
    assert ok is False and "no terminó" in texto


def test_ultima_escala(tmp_path) -> None:
    ruta = tmp_path / "escala.json"
    assert calibracion.ultima_escala(ruta) == ("—", None)
    medianas = [[-114.536, 27.278, 409.65], [-41.359, 30.935, 441.763], [-113.331, 27.398, 409.933],
                [-41.353, 30.61, 442.039], [-114.202, 27.185, 410.087], [-40.967, 30.639, 442.149]]
    e = {"fecha": "2026-10-23 14:21:17"}
    e.update(ce.juzgar_escala(medianas, [0, 80, 0, 80, 0, 80]))
    ruta.write_text(json.dumps(e), encoding="utf-8")
    assert calibracion.ultima_escala(ruta) == (
        "La cámara midió 79.6 mm donde la regla dice 80 (diferencia 0.4 mm; aceptable hasta 0.8)", True)
    ruta.write_text(json.dumps({"fecha": "2026-10-22 23:05:42", "cumple": False, "pasos": []}), encoding="utf-8")
    texto, ok = calibracion.ultima_escala(ruta)                       # un JSON con la cuenta anterior
    assert ok is None and "cuenta anterior" in texto and "no salía bien" in texto
    ruta.write_text(json.dumps({"fecha": "2026-10-22 23:05:42", "error": "solo 1 posicion"}), encoding="utf-8")
    assert calibracion.ultima_escala(ruta)[1] is False


def test_marca() -> None:
    assert calibracion.marca(True) == " ✔" and calibracion.marca(False) == " ✘" and calibracion.marca(None) == ""
