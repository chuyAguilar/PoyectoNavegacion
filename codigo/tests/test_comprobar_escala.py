"""comprobar_escala.py sin camara (meta 002, fase 4).

`errores_escala` y `errores_pasos` con desplazamientos sinteticos; la pose del
tablero sobre una vista renderizada con una K conocida; `medir_posiciones` y
`main` con una camara falsa y un perfil temporal que apunta a un .yml.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from calibration import calibrate_camera as cc
from calibration import check_scale as ce

from .conftest import PROFILES_DIR
from . import tablero_sintetico as ts

PERFIL_GS1 = str(PROFILES_DIR / "tracker_config_gs1.yaml")
COLS, ROWS, SQ = 8, 5, 24.97
K = ts.K_de(600.0, 600.0, 320.0, 240.0)
SHAPE = (640, 480)
RVEC = np.array([0.2, -0.15, 0.05])


class CamSecuencia:
    """read() devuelve cada frame tantas veces como diga su tramo y luego el ultimo; get_intrinsics fija."""

    def __init__(self, tramos, K, dist):
        self.tramos = list(tramos)
        self.K, self.dist = K, dist
        self.i = 0
        self.cerrada = False
        self.abierta = False

    def open(self):
        self.abierta = True

    def read(self):
        acumulado = 0
        frame = self.tramos[-1][0]
        for f, n in self.tramos:
            acumulado += n
            if self.i < acumulado:
                frame = f
                break
        self.i += 1
        return frame, None, 0.0

    def get_intrinsics(self):
        return self.K, self.dist

    def close(self):
        self.cerrada = True


def sin_ventanas(monkeypatch):
    monkeypatch.setattr(ce.cv2, "namedWindow", lambda *a, **k: None)
    monkeypatch.setattr(ce.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(ce.cv2, "pollKey", lambda: -1)          # fase 2c: refrescar durante la medida
    monkeypatch.setattr(ce.cv2, "destroyAllWindows", lambda: None)


@pytest.fixture(autouse=True)
def sin_camara_real(monkeypatch):
    """Ninguna prueba de este modulo puede abrir una camara real aunque cambie un perfil (P18; el
    incidente de la fase 4). main usa create_backend si no se le pasa `abrir`."""
    def _prohibido(*_a, **_k):
        raise AssertionError("una prueba intento abrir una camara real (create_backend)")
    monkeypatch.setattr(ce, "create_backend", _prohibido)


# ----------------------------------------------------------------------------
# Funciones puras
# ----------------------------------------------------------------------------

def test_errores_escala_sinteticos() -> None:
    t = [np.array([0.0, 0.0, 500.0]), np.array([100.0, 0.0, 500.0]), np.array([201.0, 0.0, 500.0])]
    assert ce.errores_escala(t, [0, 100, 200]) == pytest.approx([0.0, 1.0])
    assert ce.errores_escala(t, [300, 200, 100]) == pytest.approx([0.0, 1.0])          # la regla al reves
    assert ce.errores_escala([t[0], np.array([0.0, 99.5, 500.0])], [0, 100]) == pytest.approx([-0.5])
    with pytest.raises(ValueError):
        ce.errores_escala(t, [0, 100])
    with pytest.raises(ValueError):
        ce.errores_escala(t[:1], [0])
    with pytest.raises(ValueError):
        ce.errores_escala([np.zeros(2), np.zeros(2)], [0, 100])


def test_errores_pasos_y_tolerancia() -> None:
    assert ce.tolerancia_mm(100) == 1.0 and ce.tolerancia_mm(200) == 2.0 and ce.tolerancia_mm(-50) == 0.5
    t = [np.array([0.0, 0.0, 500.0]), np.array([100.0, 0.0, 500.0]), np.array([201.2, 0.0, 500.0])]
    p = ce.errores_pasos(t, [0, 100, 200])
    assert len(p) == 2 and p[0]["cumple"] and p[0]["error_mm"] == pytest.approx(0.0)
    assert p[1] == {"de_mm": 100.0, "a_mm": 200.0, "paso_regla_mm": 100.0, "paso_medido_mm": 101.2,
                    "error_mm": 1.2, "tolerancia_mm": 1.0, "cumple": False}
    with pytest.raises(ValueError):
        ce.errores_pasos(t[:1], [0])


def test_resumir_posicion() -> None:
    r = ce.resumir_posicion([np.array([1.0, 2.0, 500.0]), np.array([1.0, 2.0, 502.0]), np.array([1.0, 2.0, 501.0])])
    assert r["n"] == 3 and r["mediana_mm"] == [1.0, 2.0, 501.0] and r["sd_mm"][2] == pytest.approx(0.816, abs=1e-3)
    assert r["distancia_mm"] == pytest.approx(501.0, abs=0.01)
    assert ce.resumir_posicion([np.zeros(3)])["sd_mm"] == [0.0, 0.0, 0.0]
    with pytest.raises(ValueError):
        ce.resumir_posicion([])


# ----------------------------------------------------------------------------
# Pose sobre una vista renderizada
# ----------------------------------------------------------------------------

def _vista(tvec):
    return ts.renderizar_vista(K, RVEC, tvec, COLS, ROWS, SQ, SHAPE)


@pytest.mark.parametrize("metodo", cc.DETECTORES)
def test_pose_tablero_recupera_la_traslacion(metodo: str) -> None:
    tvec = ts.pose_hacia(K, RVEC, (320.0, 240.0), 600.0, COLS, ROWS, SQ)
    p = ce.pose_tablero(_vista(tvec), COLS, ROWS, SQ, K, np.zeros(5), metodo)
    assert p is not None
    rvec, t = p
    # El centro del tablero vale con los dos ordenes de esquinas (girado 180 grados); el origen no.
    R_true, _ = ce.cv2.Rodrigues(RVEC)
    centro_true = R_true @ ce.centro_tablero_mm(COLS, ROWS, SQ) + tvec
    assert np.linalg.norm(t - centro_true) < 1.5, f"{metodo}: {t} frente a {centro_true}"
    R, _ = ce.cv2.Rodrigues(rvec)
    assert abs(float(R[:, 2] @ R_true[:, 2])) > np.cos(0.02)      # la normal del tablero, salvo el signo
    assert ce.pose_tablero(np.full((480, 640), 128, dtype=np.uint8), COLS, ROWS, SQ, K, np.zeros(5), metodo) is None


def test_pose_tablero_ve_un_desplazamiento_de_100_mm() -> None:
    t0 = ts.pose_hacia(K, RVEC, (300.0, 240.0), 600.0, COLS, ROWS, SQ)
    t1 = t0 + np.array([100.0, 0.0, 0.0])
    p0 = ce.pose_tablero(_vista(t0), COLS, ROWS, SQ, K, np.zeros(5), "clasico")
    p1 = ce.pose_tablero(_vista(t1), COLS, ROWS, SQ, K, np.zeros(5), "clasico")
    e = ce.errores_escala([p0[1], p1[1]], [0, 100])
    assert abs(e[0]) < 1.0


# ----------------------------------------------------------------------------
# medir_posiciones y main con camara falsa
# ----------------------------------------------------------------------------

def test_medir_posiciones_con_camara_falsa(monkeypatch) -> None:
    sin_ventanas(monkeypatch)
    t0 = ts.pose_hacia(K, RVEC, (300.0, 240.0), 600.0, COLS, ROWS, SQ)
    a, b = ts.a_bgr(_vista(t0)), ts.a_bgr(_vista(t0 + np.array([100.0, 0.0, 0.0])))
    cam = CamSecuencia([(a, 3), (b, 3)], K, np.zeros(5))
    teclas = iter([ord(" "), ord(" ")])
    filas = ce.medir_posiciones(cam, COLS, ROWS, SQ, K, np.zeros(5), "clasico", [0.0, 100.0], 2,
                                limite=float("inf"), leer_tecla=lambda: next(teclas, ord("q")))
    assert len(filas) == 2 and filas[0]["n"] == 2 and filas[1]["desplazamiento_mm"] == 100.0
    e = ce.errores_pasos([f["mediana_mm"] for f in filas], [f["desplazamiento_mm"] for f in filas])
    assert e[0]["cumple"]


def test_medir_posiciones_sin_tablero_no_avanza(monkeypatch) -> None:
    sin_ventanas(monkeypatch)
    lisa = np.full((480, 640, 3), 128, dtype=np.uint8)
    cam = CamSecuencia([(lisa, 1)], K, np.zeros(5))
    teclas = iter([ord(" "), ord("q")])
    filas = ce.medir_posiciones(cam, COLS, ROWS, SQ, K, np.zeros(5), "clasico", [0.0, 100.0], 2,
                                limite=float("inf"), leer_tecla=lambda: next(teclas, ord("q")),
                                segundos_por_posicion=0.2)
    assert filas == []


def _perfil_temporal(tmp_path) -> str:
    yml = tmp_path / "intrinsecos_prueba_640x480.yml"
    cc.guardar_yml(yml, K, np.zeros(5), 640, 480, 0.1, 10, COLS, ROWS, SQ)
    cfg = yaml.safe_load((PROFILES_DIR / "tracker_config_gs1.yaml").read_text(encoding="utf-8"))
    cfg["camera"] = {"camera_type": "webcam", "source": 0, "width": 640, "height": 480, "fps": 30,
                     "backend": "MSMF", "fourcc": "MJPG",
                     # absoluta: desde la meta 003 (fase 3) una ruta relativa del perfil es relativa
                     # a codigo/, no a la carpeta del perfil (profiles.load)
                     "calibration_file": str(yml)}
    ruta = tmp_path / "tracker_config_prueba.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(ruta)


def test_main_con_camara_falsa(tmp_path, monkeypatch) -> None:
    sin_ventanas(monkeypatch)
    t0 = ts.pose_hacia(K, RVEC, (300.0, 240.0), 600.0, COLS, ROWS, SQ)
    frames = [(ts.a_bgr(_vista(t0 + np.array([d, 0.0, 0.0]))), 3) for d in (0.0, 100.0, 200.0)]
    cam = CamSecuencia(frames, K, np.zeros(5))
    teclas = iter([ord(" ")] * 3)
    monkeypatch.setattr(ce.cv2, "waitKey", lambda *a, **k: next(teclas, ord("q")))
    salida = tmp_path / "escala.json"
    rc = ce.main(["--config", _perfil_temporal(tmp_path), "--cols", str(COLS), "--rows", str(ROWS),
                  "--square-mm", f"{SQ}", "--detector", "clasico", "--desplazamientos-mm", "0,100,200",
                  "--frames-por-posicion", "2", "--luz", "caja nivel 2", "--salida", str(salida), "--timeout", "60"],
                 abrir=lambda c: cam)
    e = json.loads(salida.read_text(encoding="utf-8"))
    assert rc == 0, e
    assert cam.abierta and cam.cerrada and len(e["posiciones"]) == 3 and e["cumple"] is True
    assert [p["paso_regla_mm"] for p in e["pasos"]] == [100.0, 100.0] and all(abs(p["error_mm"]) < 1.0 for p in e["pasos"])
    assert len(e["errores_acumulados_mm"]) == 2 and e["luz"] == "caja nivel 2" and e["tolerancia_mm_por_100"] == 1.0
    assert np.allclose(e["K"], K)
    assert e["criterio"] == "pasos" and "medias" not in e      # sin posiciones repetidas: por paso (P20)


def _perfil_gs1_sin_yml(tmp_path) -> str:
    """El perfil gs1 sin calibration_file: main tiene que parar antes de abrir nada (la camara real)."""
    cfg = yaml.safe_load(Path(PERFIL_GS1).read_text(encoding="utf-8"))
    cfg["camera"]["calibration_file"] = None
    ruta = tmp_path / "tracker_config_gs1_sin_yml.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(ruta)


SIN_YML = "<gs1 sin calibration_file>"


@pytest.mark.parametrize("argv", [
    ["--config", SIN_YML, "--square-mm", "24.97", "--detector", "clasico", "--desplazamientos-mm", "0,100"],     # sin .yml
    ["--square-mm", "24.97", "--detector", "clasico", "--desplazamientos-mm", "0"],                            # 1 posicion
    ["--square-mm", "24.97", "--detector", "clasico"],                                                         # sin regla
    ["--square-mm", "24.97", "--desplazamientos-mm", "0,100"],                                                 # sin detector
    ["--detector", "clasico", "--desplazamientos-mm", "0,100"],                                                # sin lado
])
def test_main_exige_argumentos_explicitos(tmp_path, argv: list[str]) -> None:
    if "--config" not in argv:
        argv = ["--config", _perfil_temporal(tmp_path), *argv]
    elif SIN_YML in argv:
        argv = [_perfil_gs1_sin_yml(tmp_path) if a == SIN_YML else a for a in argv]
    with pytest.raises(SystemExit):
        ce.main([*argv, "--salida", str(tmp_path / "e.json"), "--timeout", "60"])


def test_main_sin_timeout_o_sin_config_para(tmp_path) -> None:
    base = ["--square-mm", "24.97", "--detector", "clasico", "--desplazamientos-mm", "0,100",
            "--salida", str(tmp_path / "e.json")]
    with pytest.raises(SystemExit):
        ce.main(["--config", _perfil_temporal(tmp_path), *base])                 # sin --timeout
    with pytest.raises(SystemExit):
        ce.main([*base, "--timeout", "60"])                                       # sin --config


# ----------------------------------------------------------------------------
# P20 (fase 5): el criterio por medias con posiciones repetidas, y --desde-json
# ----------------------------------------------------------------------------

# Las medianas de las dos sesiones reales (Claude outputs/camaras/escala_gs2.json, 2026-10-23, y
# escala_gs1_topes.json, 2026-10-22), copiadas aqui para que la prueba no dependa de esos archivos.
REGLA_IDA_VUELTA = [0.0, 80.0, 0.0, 80.0, 0.0, 80.0]
MEDIANAS_GS2 = [[-114.536, 27.278, 409.65], [-41.359, 30.935, 441.763], [-113.331, 27.398, 409.933],
                [-41.353, 30.61, 442.039], [-114.202, 27.185, 410.087], [-40.967, 30.639, 442.149]]
MEDIANAS_GS1_TOPES = [[0.013, 30.606, 429.506], [75.264, 30.96, 401.836], [0.063, 30.716, 429.748],
                      [75.553, 31.052, 401.895], [0.609, 30.628, 429.517], [75.785, 31.155, 401.668]]


def test_hay_repeticiones() -> None:
    assert ce.hay_repeticiones(REGLA_IDA_VUELTA) and ce.hay_repeticiones([0, 80, 0.0])
    assert not ce.hay_repeticiones([0, 100, 200]) and not ce.hay_repeticiones([0, 80])


def test_agrupar_por_lectura_media_y_repetibilidad() -> None:
    t = [[0.0, 0.0, 500.0], [80.0, 0.0, 500.0], [0.0, 2.0, 500.0], [80.0, 0.0, 500.0]]
    g = ce.agrupar_por_lectura(t, [0, 80, 0, 80])
    assert [x["lectura_mm"] for x in g] == [0.0, 80.0] and [x["posiciones"] for x in g] == [[0, 2], [1, 3]]
    assert g[0]["media_mm"] == [0.0, 1.0, 500.0] and g[0]["repetibilidad_mm"] == pytest.approx(1.0)
    assert g[1]["repetibilidad_mm"] == 0.0 and g[0]["distancias_a_la_media_mm"] == [1.0, 1.0]
    with pytest.raises(ValueError):
        ce.agrupar_por_lectura(t[:1], [0])
    with pytest.raises(ValueError):
        ce.errores_medias(t[:2], [0, 0])                     # una sola lectura distinta


def test_criterio_por_medias_las_dos_sesiones_reales() -> None:
    """P20: gs2 falla 2 de 5 pasos (el segundo 0 quedo 1.24 mm corrido) y cumple por medias (-0.37 mm);
    gs1 (topes) cumple por las dos cuentas (+0.27 mm por medias)."""
    r2 = ce.juzgar_escala(MEDIANAS_GS2, REGLA_IDA_VUELTA)
    assert r2["criterio"] == "medias" and r2["cumple"] is True and r2["cumple_por_pasos"] is False
    assert [p["cumple"] for p in r2["pasos"]] == [True, False, False, True, True]
    assert len(r2["medias"]) == 1 and r2["error_criterio_mm"] == pytest.approx(-0.368, abs=1e-3)
    assert r2["peor"]["paso_medido_mm"] == pytest.approx(79.632, abs=1e-3) and r2["peor"]["tolerancia_mm"] == 0.8
    assert [g["n"] for g in r2["grupos"]] == [3, 3] and r2["grupos"][0]["repetibilidad_mm"] == pytest.approx(0.702, abs=1e-3)
    r1 = ce.juzgar_escala(MEDIANAS_GS1_TOPES, REGLA_IDA_VUELTA)
    assert r1["criterio"] == "medias" and r1["cumple"] and r1["cumple_por_pasos"]
    assert r1["error_criterio_mm"] == pytest.approx(0.271, abs=1e-3)


def test_criterio_por_medias_que_no_cumple() -> None:
    t = [[0.0, 0.0, 500.0], [81.0, 0.0, 500.0], [0.0, 0.0, 500.0], [81.0, 0.0, 500.0]]
    r = ce.juzgar_escala(t, [0, 80, 0, 80])
    assert r["criterio"] == "medias" and r["cumple"] is False and r["error_criterio_mm"] == pytest.approx(1.0)


def test_sin_repeticiones_el_criterio_sigue_por_paso() -> None:
    t = [np.array([0.0, 0.0, 500.0]), np.array([100.0, 0.0, 500.0]), np.array([201.2, 0.0, 500.0])]
    r = ce.juzgar_escala(t, [0, 100, 200])
    assert r["criterio"] == "pasos" and "medias" not in r and r["cumple"] is False
    assert r["error_criterio_mm"] == pytest.approx(1.2) and r["peor"]["a_mm"] == 200.0
    # Con medias por lectura seguidas y tres lecturas distintas: dos comparaciones
    g, m = ce.errores_medias(t + [np.array([100.0, 0.0, 500.0])], [0, 100, 200, 100])
    assert [(c["de_mm"], c["a_mm"]) for c in m] == [(0.0, 100.0), (100.0, 200.0)]


def test_parsear_lista_exige_dos_lecturas_distintas() -> None:
    with pytest.raises(ValueError):
        ce._parsear_lista("80,80,80")
    assert ce._parsear_lista("0,80,0") == [0.0, 80.0, 0.0]


def _json_sesion(tmp_path, medianas, nombre="escala_sesion.json") -> Path:
    """Un JSON como el que deja la sesion en vivo, con el criterio viejo (por paso)."""
    posiciones = [{"desplazamiento_mm": d, "n": 30, "mediana_mm": m, "sd_mm": [0.02, 0.01, 0.02],
                   "frames_sin_pose": 0} for d, m in zip(REGLA_IDA_VUELTA, medianas)]
    viejo = {"fecha": "2026-10-23 14:21:17", "perfil": "profiles\\tracker_config_gs2.yaml", "detector": "sb",
             "square_mm": 24.86, "K": K.tolist(), "posiciones": posiciones,
             "pasos": ce.errores_pasos(medianas, REGLA_IDA_VUELTA), "cumple": False}
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(viejo), encoding="utf-8")
    return ruta


def test_desde_json_recalcula_sin_camara(tmp_path) -> None:
    entrada = _json_sesion(tmp_path, MEDIANAS_GS2)
    salida = tmp_path / "recalculado.json"
    rc = ce.main(["--desde-json", str(entrada), "--salida", str(salida)])
    e = json.loads(salida.read_text(encoding="utf-8"))
    assert rc == 0 and e["cumple"] is True and e["criterio"] == "medias"
    assert e["error_criterio_mm"] == pytest.approx(-0.368, abs=1e-3)
    assert e["recalculado"]["cumple_antes"] is False and e["recalculado"]["criterio_antes"] == "pasos"
    assert len(e["posiciones"]) == 6 and np.allclose(e["K"], K) and e["detector"] == "sb"   # se conserva
    assert json.loads(entrada.read_text(encoding="utf-8"))["cumple"] is False                # la entrada no se toca
    # Recalcular sobre el mismo archivo es estable
    assert ce.main(["--desde-json", str(salida), "--salida", str(salida)]) == 0
    assert json.loads(salida.read_text(encoding="utf-8"))["error_criterio_mm"] == e["error_criterio_mm"]


def test_desde_json_no_cumple_da_exit_1_y_errores(tmp_path) -> None:
    malas = [[0.0, 0.0, 500.0], [81.0, 0.0, 500.0]] * 3
    assert ce.main(["--desde-json", str(_json_sesion(tmp_path, malas)), "--salida", str(tmp_path / "s.json")]) == 1
    vacio = tmp_path / "vacio.json"
    vacio.write_text(json.dumps({"posiciones": [], "error": "q antes de medir"}), encoding="utf-8")
    assert ce.main(["--desde-json", str(vacio), "--salida", str(tmp_path / "v.json")]) == 1
    assert ce.main(["--desde-json", str(tmp_path / "no_existe.json"), "--salida", str(tmp_path / "n.json")]) == 1
    with pytest.raises(SystemExit):        # con --desde-json no se abre la camara: sobran los de la camara
        ce.main(["--desde-json", str(vacio), "--config", PERFIL_GS1, "--salida", str(tmp_path / "x.json")])


def test_textos_de_la_ventana_llanos_y_sin_acentos() -> None:
    """P21: lo que se pinta sobre la imagen; cv2.putText (Hershey) pinta '??' por cada letra con acento."""
    for visto in (True, False):
        l1, l2 = ce.textos_ventana(1, 6, 80.0, visto)
        assert l1.isascii() and l2.isascii()
        assert l1.startswith("Posicion 2 de 6: lleva el tablero a la marca de 80 mm y pulsa ESPACIO")
        assert ("NO lo veo" in l2) is (not visto) and "q = salir" in l2


# ----------------------------------------------------------------------------
# Fase 2c de la meta 004 (P11): la ventana no se congela y la vista previa no la frena
# ----------------------------------------------------------------------------

class Refresco:
    """refrescar(img) falso: cuenta las llamadas y devuelve las teclas que se le den (255 = ninguna)."""

    def __init__(self, teclas=()):
        self.llamadas = 0
        self.teclas = iter(teclas)

    def __call__(self, img) -> int:
        assert img.ndim == 3
        self.llamadas += 1
        return next(self.teclas, 255)


def _espiar_textos(monkeypatch) -> list[tuple]:
    vistos: list[tuple] = []
    original = ce.texto_midiendo

    def espia(i, total, lectura, k, n, sin_tablero=0):
        vistos.append((i, k, n, sin_tablero))
        return original(i, total, lectura, k, n, sin_tablero)
    monkeypatch.setattr(ce, "texto_midiendo", espia)
    return vistos


def test_medir_posiciones_repinta_en_cada_pose(monkeypatch) -> None:
    """Durante la medida se pinta y se atienden las teclas al menos una vez por pose, con
    'k de N' subiendo; la medida da lo mismo que sin pintar (las mismas medianas)."""
    sin_ventanas(monkeypatch)
    vistos = _espiar_textos(monkeypatch)
    t0 = ts.pose_hacia(K, RVEC, (300.0, 240.0), 600.0, COLS, ROWS, SQ)
    a, b = ts.a_bgr(_vista(t0)), ts.a_bgr(_vista(t0 + np.array([100.0, 0.0, 0.0])))
    cam = CamSecuencia([(a, 4), (b, 4)], K, np.zeros(5))
    teclas = iter([ord(" "), ord(" ")])
    refresco = Refresco()
    filas = ce.medir_posiciones(cam, COLS, ROWS, SQ, K, np.zeros(5), "clasico", [0.0, 100.0], 3,
                                limite=float("inf"), leer_tecla=lambda: next(teclas, ord("q")), refrescar=refresco)
    assert len(filas) == 2 and [f["n"] for f in filas] == [3, 3]
    assert refresco.llamadas >= sum(f["n"] for f in filas)
    assert [(i, k) for i, k, _n, _s in vistos] == [(0, 1), (0, 2), (0, 3), (1, 1), (1, 2), (1, 3)]
    for f, img in zip(filas, (a, b)):
        p = ce.pose_tablero(ce.cv2.cvtColor(img, ce.cv2.COLOR_BGR2GRAY), COLS, ROWS, SQ, K, np.zeros(5), "clasico")
        assert f["mediana_mm"] == np.asarray(p[1]).round(3).tolist()


def test_medir_posiciones_sin_tablero_repinta_y_cuenta(monkeypatch) -> None:
    """Sin tablero (el caso que congelaba la ventana 15 s): cada frame fallido se pinta, con la cuenta."""
    sin_ventanas(monkeypatch)
    vistos = _espiar_textos(monkeypatch)
    lisa = np.full((480, 640, 3), 128, dtype=np.uint8)
    cam = CamSecuencia([(lisa, 1)], K, np.zeros(5))
    teclas = iter([ord(" "), ord("q")])
    refresco = Refresco()
    filas = ce.medir_posiciones(cam, COLS, ROWS, SQ, K, np.zeros(5), "clasico", [0.0, 100.0], 2,
                                limite=float("inf"), leer_tecla=lambda: next(teclas, ord("q")),
                                segundos_por_posicion=0.3, refrescar=refresco)
    assert filas == [] and refresco.llamadas >= 1 and refresco.llamadas == len(vistos)
    assert [s for *_x, s in vistos] == list(range(1, len(vistos) + 1)) and all(k == 0 for _i, k, _n, _s in vistos)


def test_q_durante_la_medida_cancela_y_sale(monkeypatch) -> None:
    sin_ventanas(monkeypatch)
    t0 = ts.pose_hacia(K, RVEC, (300.0, 240.0), 600.0, COLS, ROWS, SQ)
    cam = CamSecuencia([(ts.a_bgr(_vista(t0)), 1)], K, np.zeros(5))
    teclas = iter([ord(" ")])
    refresco = Refresco([255, ord("q")])
    filas = ce.medir_posiciones(cam, COLS, ROWS, SQ, K, np.zeros(5), "clasico", [0.0, 100.0], 30,
                                limite=float("inf"), leer_tecla=lambda: next(teclas, ord(" ")), refrescar=refresco)
    assert filas == [] and refresco.llamadas == 2


def test_texto_midiendo_llano_y_sin_acentos() -> None:
    t = ce.texto_midiendo(1, 6, 80.0, 12, 30)
    assert t.isascii() and "Midiendo posicion 2 de 6 (80 mm): 12 de 30 poses" in t and "sin tablero" not in t
    t = ce.texto_midiendo(0, 6, 0.0, 0, 30, sin_tablero=7)
    assert t.isascii() and "0 de 30 poses (sin tablero en 7 frames)" in t and "q = salir" in t


def _vista_1280():
    K2 = ts.K_de(850.0, 850.0, 640.0, 480.0)
    tvec = ts.pose_hacia(K2, RVEC, (640.0, 480.0), 420.0, COLS, ROWS, SQ)
    return ts.renderizar_vista(K2, RVEC, tvec, COLS, ROWS, SQ, (1280, 960))


def test_detectar_previa_a_la_mitad() -> None:
    g = _vista_1280()
    completa = cc.detectar_esquinas(g, COLS, ROWS, "clasico", rapido=True)
    mitad = ce.detectar_previa(g, COLS, ROWS, 0.5)
    assert completa is not None and mitad is not None and mitad.shape == completa.shape
    assert np.abs(mitad - completa).max() < 1.0              # solo para pintar: en el frame completo
    assert np.array_equal(ce.detectar_previa(g, COLS, ROWS, 1.0), completa)
    assert ce.detectar_previa(np.full((960, 1280), 128, np.uint8), COLS, ROWS) is None
    for mala in (0.0, -0.5, 1.5):
        with pytest.raises(ValueError):
            ce.detectar_previa(g, COLS, ROWS, mala)


def _esperar(cond, tope_s: float = 10.0) -> bool:
    fin = ce.time.monotonic() + tope_s
    while ce.time.monotonic() < fin:
        if cond():
            return True
        ce.time.sleep(0.01)
    return cond()


def test_previa_en_hilo_detecta_y_se_cierra() -> None:
    h = ce.PreviaEnHilo(COLS, ROWS)
    try:
        assert h.ultimas() is None
        h.enviar(_vista_1280())
        assert _esperar(lambda: h.hechas >= 1)
        assert h.ultimas() is not None and h.ultimas().shape == (COLS * ROWS, 1, 2)
        h.enviar(np.full((960, 1280), 128, np.uint8))
        assert _esperar(lambda: h.hechas >= 2) and h.ultimas() is None
    finally:
        h.cerrar()
    assert not h.vivo()
    with pytest.raises(ValueError):
        ce.PreviaEnHilo(COLS, ROWS, escala=0.0)


def test_previa_en_hilo_relanza_su_error() -> None:
    def falla(*_a):
        raise ce.cv2.error("detector roto")
    h = ce.PreviaEnHilo(COLS, ROWS, detectar=falla)
    try:
        h.enviar(np.zeros((10, 10), np.uint8))
        assert _esperar(lambda: not h.vivo())
        with pytest.raises(RuntimeError, match="vista previa"):
            h.ultimas()
    finally:
        h.cerrar()
