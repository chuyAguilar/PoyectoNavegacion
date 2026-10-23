"""medir_modos.py sin camara: una camara falsa y markers sinteticos (meta 002, fase 3).

Cubre las funciones puras (k_nominal, fraccion_saturada, elegir_exposicion,
elegir_exposicion_comun, exposicion_cambia_brillo, elegir_resolucion,
tabla_markdown, estimar_segundos), la medicion sobre una camara falsa
(medir_captura solo lee frames y guarda la muestra; analizar_muestra y
medir_tracking con un marker real del diccionario; medir_fila abre por el
perfil, anota la exposicion leida y libera), y main (argumentos explicitos,
tope, --elegir sin camara, las dos mediciones con la camara falsa y cada fila
guardada al tenerla).
"""
from __future__ import annotations

import json
import time

import cv2
import numpy as np
import pytest

import medir_modos as mm
import tracker

from .conftest import ITER4_DIR

PERFIL_GS1 = str(ITER4_DIR / "tracker_config_gs1.yaml")
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_MIP_36h12)


# ----------------------------------------------------------------------------
# Falsos
# ----------------------------------------------------------------------------

def imagen_marker(mid: int = 3, lado: int = 120, lienzo: tuple[int, int] = (300, 300)) -> np.ndarray:
    """Un frame BGR con el marker `mid` del diccionario del tracker centrado sobre fondo blanco."""
    img = DICT.generateImageMarker(mid, lado)
    h, w = lienzo
    canvas = np.full((h, w), 255, dtype=np.uint8)
    y, x = (h - lado) // 2, (w - lado) // 2
    canvas[y:y + lado, x:x + lado] = img
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)


class CamFalsa:
    """read() da los frames de `frames` en ciclo (None cuenta como fallo); registra close()."""

    def __init__(self, frames: list, ajustes_leidos: dict | None = None) -> None:
        self.frames = list(frames)
        self.i = 0
        self.lecturas = 0
        self.cerrada = False
        self.ajustes_leidos = ajustes_leidos

    def read(self):
        f = self.frames[self.i % len(self.frames)]
        self.i += 1
        self.lecturas += 1
        if f is None:
            return None, None, None
        return f, None, time.time()

    def close(self) -> None:
        self.cerrada = True


def cfg_gs1() -> dict:
    return tracker.cargar_config(PERFIL_GS1)


def fila_exp(ms: float, fps: float = 90.0, sat: float | None = 0.0, markers: float | None = 4,
             brillo: float | None = 100.0) -> dict:
    return {"pedido": {"ancho": 1280, "alto": 960, "fourcc": "MJPG", "fps": 90},
            "exposicion_ms": ms, "fps_captura": fps, "saturada": sat,
            "markers_mediana": markers, "brillo": brillo}


def fila_modo(w: int, h: int, fps_ventana: float | None, fcc: str = "MJPG") -> dict:
    return {"pedido": {"ancho": w, "alto": h, "fourcc": fcc, "fps": 90},
            "fps_tracking_ventana": fps_ventana}


# ----------------------------------------------------------------------------
# Funciones puras
# ----------------------------------------------------------------------------

def test_k_nominal_90_grados() -> None:
    K, dist = mm.k_nominal(640, 480, 90.0)
    assert K[0, 0] == pytest.approx(320.0) and K[1, 1] == pytest.approx(320.0)
    assert (K[0, 2], K[1, 2], K[2, 2]) == (320.0, 240.0, 1.0)
    assert dist.shape == (5,) and not dist.any()
    K2, _ = mm.k_nominal(1280, 960, 84.0)
    assert K2[0, 0] == pytest.approx(640.0 / np.tan(np.radians(42.0)))


@pytest.mark.parametrize("fov", [0.0, 180.0, -10.0])
def test_k_nominal_fov_invalido(fov: float) -> None:
    with pytest.raises(ValueError):
        mm.k_nominal(640, 480, fov)


def test_fraccion_saturada_sintetica() -> None:
    gray = np.zeros((200, 200), dtype=np.uint8)
    gray[60:80, 60:80] = 255                       # 400 pixeles saturados dentro
    gray[150, 150] = 255                           # uno fuera de la envolvente
    esquinas = [np.array([[[50, 50], [100, 50], [100, 100], [50, 100]]], dtype=np.float32)]
    sin_margen = mm.fraccion_saturada(gray, esquinas, margen_px=0)
    assert sin_margen == pytest.approx(400 / (51 * 51))
    con_margen = mm.fraccion_saturada(gray, esquinas, margen_px=10)
    assert 0 < con_margen < sin_margen                 # mas area, misma cuenta
    gray[:, :] = 0
    assert mm.fraccion_saturada(gray, esquinas) == 0.0
    gray[:, :] = 255
    assert mm.fraccion_saturada(gray, esquinas) == 1.0


def test_fraccion_saturada_sin_markers_es_none() -> None:
    assert mm.fraccion_saturada(np.zeros((10, 10), dtype=np.uint8), []) is None


def test_fraccion_saturada_envolvente_de_varios_markers() -> None:
    gray = np.zeros((200, 200), dtype=np.uint8)
    gray[95:105, 95:105] = 255                     # entre los dos markers: dentro de la envolvente
    dos = [np.array([[10, 10], [40, 10], [40, 40], [10, 40]], dtype=np.float32),
           np.array([[160, 160], [190, 160], [190, 190], [160, 190]], dtype=np.float32)]
    assert mm.fraccion_saturada(gray, dos, margen_px=0) > 0.0


def test_elegir_exposicion_mas_markers_y_empate_la_mayor() -> None:
    filas = [fila_exp(7.813, markers=3), fila_exp(3.906, markers=5), fila_exp(1.953, markers=5),
             fila_exp(0.977, markers=2)]
    assert mm.elegir_exposicion(filas)["exposicion_ms"] == 3.906


def test_elegir_exposicion_descarta_fps_saturacion_y_sin_dato() -> None:
    filas = [fila_exp(7.813, fps=60.0, markers=9),            # no llega a 88.2
             fila_exp(3.906, sat=0.05, markers=9),            # saturada > 1 %
             fila_exp(1.953, sat=None, markers=9),            # sin markers: sin medida
             fila_exp(0.977, markers=None),
             fila_exp(0.488, sat=0.01, markers=3)]            # justo en el umbral: vale
    assert mm.elegir_exposicion(filas)["exposicion_ms"] == 0.488
    assert mm.elegir_exposicion(filas[:4]) is None
    assert mm.elegir_exposicion([]) is None


def test_elegir_exposicion_comun() -> None:
    a = [fila_exp(7.813, markers=6), fila_exp(3.906, markers=5), fila_exp(1.953, markers=4)]
    b = [fila_exp(7.813, sat=0.2, markers=6), fila_exp(3.906, markers=3), fila_exp(1.953, markers=4)]
    r = mm.elegir_exposicion_comun(a, b)
    assert r["exposicion_ms"] == 1.953 and r["a"] is a[2] and r["b"] is b[2]   # min(4,4) > min(5,3)
    assert mm.elegir_exposicion_comun(a, [fila_exp(0.488)]) is None


def test_exposicion_cambia_brillo() -> None:
    mitad = [fila_exp(7.813, brillo=200.0), fila_exp(3.906, brillo=100.0), fila_exp(1.953, brillo=50.0)]
    r = mm.exposicion_cambia_brillo(mitad)
    assert r["cambia"] is True and r["monotona"] is True
    assert [p["bajada"] for p in r["pasos"]] == [0.5, 0.5]
    assert r["pasos"][0] == {"de_ms": 7.813, "a_ms": 3.906, "brillo_de": 200.0, "brillo_a": 100.0, "bajada": 0.5}
    plano = [fila_exp(7.813, brillo=235.0), fila_exp(3.906, brillo=234.0), fila_exp(1.953, brillo=235.5)]
    r = mm.exposicion_cambia_brillo(plano)
    assert r["cambia"] is False and r["monotona"] is True
    sube = [fila_exp(7.813, brillo=100.0), fila_exp(3.906, brillo=150.0)]
    assert mm.exposicion_cambia_brillo(sube) == {"cambia": False, "monotona": False,
                                                 "pasos": [{"de_ms": 7.813, "a_ms": 3.906, "brillo_de": 100.0,
                                                            "brillo_a": 150.0, "bajada": -0.5}]}
    assert mm.exposicion_cambia_brillo([fila_exp(7.813, brillo=None)]) == {"cambia": False, "monotona": False, "pasos": []}


def test_elegir_resolucion_la_mayor_que_cumple_en_las_dos() -> None:
    gs1 = [fila_modo(640, 480, 90.1), fila_modo(960, 720, 89.0), fila_modo(1280, 960, 88.5), fila_modo(1920, 1080, 30.0)]
    gs2 = [fila_modo(640, 480, 89.9), fila_modo(960, 720, 88.3), fila_modo(1280, 960, 70.0), fila_modo(1920, 1080, 29.0)]
    r = mm.elegir_resolucion(gs1, gs2)
    assert r["modo"] == {"ancho": 960, "alto": 720, "fourcc": "MJPG"} and r["umbral_fps"] == 88.2
    assert r["gs1"] is gs1[1] and r["gs2"] is gs2[1]


def test_elegir_resolucion_tolerancia_y_ninguna() -> None:
    gs1 = [fila_modo(1280, 960, 88.2)]
    gs2 = [fila_modo(1280, 960, 88.2)]
    assert mm.elegir_resolucion(gs1, gs2)["modo"]["ancho"] == 1280          # 88.2 = 90 * 0.98: vale
    assert mm.elegir_resolucion(gs1, gs2, tolerancia=0.0) is None            # estricto: no
    assert mm.elegir_resolucion(gs1, [fila_modo(1280, 960, None)]) is None   # sin medida
    assert mm.elegir_resolucion([fila_modo(1280, 960, 90, "YUY2")], gs2) is None   # otro formato
    assert mm.elegir_resolucion([], []) is None


def test_tabla_markdown_solo_columnas_presentes() -> None:
    t = mm.tabla_markdown([fila_exp(3.906, sat=0.004), {"pedido": {"ancho": 640, "alto": 480, "fourcc": "YUY2", "fps": 90},
                                                      "error": "abre pero no entrega frames"}])
    cab = t.splitlines()[0]
    assert "| modo |" in cab and "fps captura" in cab and "saturada" in cab and "error" in cab
    assert "fps tracking" not in cab and "exp. leida" not in cab
    assert "| 1280x960 MJPG |" in t and "0.4 %" in t and "abre pero no entrega frames" in t
    assert mm.tabla_markdown([]) == "(sin filas)"


def test_estimar_segundos() -> None:
    assert mm.estimar_segundos(5, 10, 0, 0) == 5 * (mm.APERTURA_S + 10 + mm.MARGEN_FILA_S)
    assert mm.estimar_segundos(5, 10, 3, 30) == 5 * (mm.APERTURA_S + 10 + mm.MARGEN_FILA_S) + 3 * 60


# ----------------------------------------------------------------------------
# Con la camara falsa
# ----------------------------------------------------------------------------

def test_medir_captura_solo_lee_y_guarda_muestra() -> None:
    cam = CamFalsa([imagen_marker(), None, imagen_marker()])
    fila, muestra = mm.medir_captura(cam, 0.3, muestra_cada_s=0.1)
    assert fila["frames"] > 0 and fila["fallos"] > 0 and fila["frames"] + fila["fallos"] == cam.lecturas
    assert fila["fps_captura"] > 0 and fila["real"] == {"ancho": 300, "alto": 300}
    assert 2 <= fila["frames_muestra"] == len(muestra) <= 5
    assert all(isinstance(f, np.ndarray) for f in muestra)


def test_preparar_tracking_con_el_perfil_gs1() -> None:
    ctx = mm.preparar_tracking(cfg_gs1())
    assert ctx["ids_rb"] == set(range(3, 14)) and 0 in ctx["ids_conocidos"]
    assert ctx["min_markers"] == 3 and ctx["filtering"]["enabled"] is True
    assert isinstance(ctx["detector"], cv2.aruco.ArucoDetector)


def test_preparar_tracking_exige_un_rigid_body() -> None:
    cfg = cfg_gs1()
    cfg["rigid_bodies"] = []
    with pytest.raises(ValueError, match="un solo rigid body"):
        mm.preparar_tracking(cfg)


def test_analizar_muestra_ve_el_marker_y_la_saturacion() -> None:
    ctx = mm.preparar_tracking(cfg_gs1())
    r = mm.analizar_muestra([imagen_marker(3), imagen_marker(3)], ctx)
    assert r["markers_mediana"] == 1 and r["frames_con_markers"] == 2
    assert 0.0 < r["saturada"] < 1.0                   # fondo blanco a 255 dentro del margen
    assert 100.0 < r["brillo"] < 255.0
    gris = np.full((300, 300, 3), 77, dtype=np.uint8)
    r2 = mm.analizar_muestra([gris], ctx)
    assert r2 == {"brillo": 77.0, "saturada": None, "markers_mediana": 0, "frames_con_markers": 0}
    r3 = mm.analizar_muestra([imagen_marker(0)], ctx)   # Marker0 no es del dodecaedro
    assert r3["markers_mediana"] == 0 and r3["saturada"] is None


def test_medir_tracking_sin_ventana_un_marker_no_da_pose() -> None:
    ctx = mm.preparar_tracking(cfg_gs1())
    K, dist = mm.k_nominal(300, 300, 84.0)
    r = mm.medir_tracking(CamFalsa([imagen_marker(5)]), ctx, 0.3, False, K, dist)
    assert r["frames"] > 0 and r["fps"] > 0 and r["interrumpida"] is False
    assert r["markers_mediana"] == 1 and r["fraccion_pose"] == 0.0      # min_markers 3


def test_medir_tracking_con_pose_pasa_por_el_1_euro(monkeypatch) -> None:
    ctx = mm.preparar_tracking(cfg_gs1())
    ctx["min_markers"] = 1
    llamadas = []

    def pose_fija(det, geom, K, dist):
        llamadas.append(sorted(det))
        return np.array([[0.1], [0.2], [0.3]]), np.array([[1.0], [2.0], [500.0]]), len(det)
    monkeypatch.setattr(mm.tracker, "estimar_pose_rigid_body", pose_fija)
    K, dist = mm.k_nominal(300, 300, 84.0)
    r = mm.medir_tracking(CamFalsa([imagen_marker(9)]), ctx, 0.3, False, K, dist)
    assert r["fraccion_pose"] == 1.0 and llamadas and llamadas[0] == [9]


def test_cfg_camara_para_no_toca_el_perfil() -> None:
    cam = cfg_gs1()["camera"]
    c = mm.cfg_camara_para(cam, (1280, 960, "MJPG"), 90, 1.953)
    assert (c["width"], c["height"], c["fourcc"], c["fps"], c["calibration_file"]) == (1280, 960, "MJPG", 90, None)
    assert c["controls"]["exposure_ms"] == 1.953 and c["controls"]["exposure_manual"] is True
    assert c["controls"]["gain"] == 11 and c["usb_port_windows"] == cam["usb_port_windows"]
    assert cam["controls"]["exposure_ms"] == 0.977 and cam["width"] == 1280      # el perfil no cambia
    sin = mm.cfg_camara_para(cam, (640, 480, "YUY2"), 30, None)
    assert sin["controls"] == cam["controls"] and sin["fourcc"] == "YUY2"


def test_medir_fila_anota_la_exposicion_leida_y_libera() -> None:
    cfg = cfg_gs1()
    ctx = mm.preparar_tracking(cfg)
    cams, pedidos = [], []

    def abrir(cfg_camera):
        pedidos.append(cfg_camera)
        cams.append(CamFalsa([imagen_marker(3)], ajustes_leidos={"exposure_ms": 1.9531, "gain": 11.0}))
        return cams[-1]
    fila = mm.medir_fila(cfg, ctx, (300, 300, "MJPG"), 90, 1.953, 0.2, 0.0, 84.0, abrir=abrir)
    assert pedidos[0]["controls"]["exposure_ms"] == 1.953 and pedidos[0]["calibration_file"] is None
    assert fila["exposicion_ms"] == 1.953 and fila["exposicion_leida_ms"] == 1.9531
    assert fila["fps_captura"] > 0 and fila["markers_mediana"] == 1 and fila["brillo"] is not None
    assert "fps_tracking" not in fila and "error" not in fila and "total_s" in fila
    assert cams[0].cerrada


def test_medir_fila_con_tracking(monkeypatch) -> None:
    cfg = cfg_gs1()
    ctx = mm.preparar_tracking(cfg)
    monkeypatch.setattr(mm.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(mm.cv2, "waitKey", lambda *a, **k: -1)
    monkeypatch.setattr(mm.cv2, "destroyAllWindows", lambda: None)
    fila = mm.medir_fila(cfg, ctx, (300, 300, "MJPG"), 90, None, 0.2, 0.2, 84.0,
                         abrir=lambda c: CamFalsa([imagen_marker(4)]))
    assert fila["fps_tracking"] > 0 and fila["fps_tracking_ventana"] > 0
    assert fila["tracking_sin_ventana"]["frames"] > 0 and fila["tracking_con_ventana"]["frames"] > 0
    assert fila["markers_mediana"] == 1 and fila["fraccion_pose"] == 0.0
    assert fila["exposicion_leida_ms"] is None        # la camara falsa no leyo ajustes


def test_medir_fila_si_no_abre_queda_el_error() -> None:
    def abrir(_c):
        raise RuntimeError("[Webcam] el frame real es 1280x960 y el perfil pide 1600x1200")
    fila = mm.medir_fila(cfg_gs1(), None, (1600, 1200, "MJPG"), 90, None, 0.2, 0.0, 84.0, abrir=abrir)
    assert fila["error"].startswith("[Webcam] el frame real") and "fps_captura" not in fila


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _base(tmp_path, *extra: str) -> list[str]:
    return ["--config", PERFIL_GS1, "--salida", str(tmp_path / "m.json"), "--timeout", "60", *extra]


@pytest.mark.parametrize("argv", [
    [],                                                                 # ningun modo
    ["--enfocar", "--modos", "640x480:MJPG"],                            # dos modos
    ["--enfocar"],                                                       # sin --modo ni --fps
    ["--exposiciones-ms", "3.906", "--modo", "1280x960:MJPG", "--fps", "90"],   # faltan explicitos
    ["--exposiciones-ms", "5.0", "--modo", "1280x960:MJPG", "--fps", "90",      # 5 ms no es 2^k
     "--segundos-captura", "1", "--fov-grados", "84", "--luz", "2"],
    ["--modos", "640x480:MJPG", "--fps", "90", "--segundos-captura", "1",       # sin --segundos-tracking
     "--fov-grados", "84", "--luz", "2"],
])
def test_main_exige_argumentos_explicitos(tmp_path, argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        mm.main(_base(tmp_path, *argv))


def test_main_para_si_el_tope_no_alcanza(tmp_path, capsys) -> None:
    with pytest.raises(SystemExit):
        mm.main(_base(tmp_path, "--modos", ",".join(["640x480:MJPG"] * 5), "--fps", "90",
                      "--segundos-captura", "10", "--segundos-tracking", "30", "--fov-grados", "84", "--luz", "2"))
    assert "el tope no alcanza" in capsys.readouterr().err


def test_main_exige_perfil_con_puerto(tmp_path) -> None:
    with pytest.raises(SystemExit):
        mm.main(["--config", str(ITER4_DIR / "data" / "historico" / "tracker_config_doctor.yaml"),   # sin puerto (archivado, fase 6)
                 "--enfocar", "--modo", "640x480:MJPG",
                 "--fps", "90", "--salida", str(tmp_path / "m.json"), "--timeout", "60"])


def test_main_exposicion_con_camara_falsa(tmp_path, monkeypatch) -> None:
    def abrir(cfg_camera):
        e = cfg_camera["controls"]["exposure_ms"]
        brillo = 200 if e > 5 else 100          # a la mitad de exposicion, la mitad de brillo
        frame = np.full((300, 300, 3), brillo, dtype=np.uint8)
        frame[90:210, 90:210] = imagen_marker(3)[90:210, 90:210]
        frame[frame == 255] = 250               # sin pixeles saturados: la candidata vale
        return CamFalsa([frame], ajustes_leidos={"exposure_ms": e})
    monkeypatch.setattr(mm, "abrir_por_perfil", abrir)
    salida = tmp_path / "m.json"
    rc = mm.main(_base(tmp_path, "--exposiciones-ms", "7.813,3.906", "--modo", "300x300:MJPG", "--fps", "90",
                       "--segundos-captura", "0.2", "--fov-grados", "84", "--luz", "caja nivel 2"))
    assert rc == 0
    e = json.loads(salida.read_text(encoding="utf-8"))
    assert e["modo"] == "exposicion" and e["luz"] == "caja nivel 2" and e["puerto"].endswith("#USB(3)")
    assert [f["exposicion_ms"] for f in e["filas"]] == [7.813, 3.906]
    assert [f["exposicion_leida_ms"] for f in e["filas"]] == [7.813, 3.906]
    assert all(f["fps_captura"] > 0 and f["markers_mediana"] == 1 for f in e["filas"])
    assert e["brillo_responde"]["cambia"] is True and e["eleccion"]["exposicion_ms"] in (7.813, 3.906)
    assert "aceleracion_msmf" in e and e["umbrales"]["fps_min"] == 88.2


def test_main_modos_guarda_cada_fila_al_tenerla(tmp_path, monkeypatch) -> None:
    salida = tmp_path / "m.json"
    guardados = []
    original = mm._guardar

    def guardar(estado, ruta):
        guardados.append(len(estado.get("filas", [])))
        original(estado, ruta)
    monkeypatch.setattr(mm, "_guardar", guardar)
    monkeypatch.setattr(mm.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(mm.cv2, "waitKey", lambda *a, **k: -1)
    monkeypatch.setattr(mm.cv2, "destroyAllWindows", lambda: None)

    def abrir(cfg_camera):
        if cfg_camera["fourcc"] == "YUY2":
            raise RuntimeError("[Webcam] la camara no entrego ningun frame en el warmup")
        return CamFalsa([imagen_marker(3, lienzo=(cfg_camera["height"], cfg_camera["width"]))])
    monkeypatch.setattr(mm, "abrir_por_perfil", abrir)
    rc = mm.main(_base(tmp_path, "--modos", "300x300:MJPG,320x240:MJPG", "--modos-solo-captura", "640x480:YUY2",
                       "--fps", "90", "--segundos-captura", "0.2", "--segundos-tracking", "0.2",
                       "--fov-grados", "84", "--luz", "2", "--exposicion-ms", "1.953"))
    assert rc == 1                                            # la fila YUY2 trae error
    e = json.loads(salida.read_text(encoding="utf-8"))
    assert guardados[:3] == [1, 2, 3]                         # B25: una escritura por fila
    assert [f["pedido"]["fourcc"] for f in e["filas"]] == ["MJPG", "MJPG", "YUY2"]
    assert e["filas"][0]["fps_tracking_ventana"] > 0 and e["filas"][0]["exposicion_ms"] == 1.953
    assert "fps_tracking" not in e["filas"][2] and e["filas"][2]["error"].startswith("[Webcam]")
    assert e["modos_que_cumplen"] == [] or all("MJPG" in m for m in e["modos_que_cumplen"])


def test_main_elegir_sin_camara(tmp_path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"modo": "modos", "perfil": "gs1",
                             "filas": [fila_modo(640, 480, 90.0), fila_modo(1280, 960, 89.0)]}), encoding="utf-8")
    b.write_text(json.dumps({"modo": "modos", "perfil": "gs2",
                             "filas": [fila_modo(640, 480, 90.0), fila_modo(1280, 960, 80.0)]}), encoding="utf-8")
    salida = tmp_path / "e.json"
    rc = mm.main(["--config", PERFIL_GS1, "--elegir", str(a), str(b), "--salida", str(salida), "--timeout", "60"])
    e = json.loads(salida.read_text(encoding="utf-8"))
    assert rc == 0 and e["modo"] == "elegir" and e["eleccion"]["modo"] == {"ancho": 640, "alto": 480, "fourcc": "MJPG"}
    assert e["de"]["a"]["perfil"] == "gs1" and e["de"]["b"]["perfil"] == "gs2"
    a.write_text(json.dumps({"modo": "exposicion", "perfil": "gs1", "filas": [fila_exp(3.906)]}), encoding="utf-8")
    assert mm.main(["--config", PERFIL_GS1, "--elegir", str(a), str(b), "--salida", str(salida),
                    "--timeout", "60"]) == 1                     # mediciones distintas
    b.write_text(json.dumps({"modo": "exposicion", "perfil": "gs2", "filas": [fila_exp(3.906)]}), encoding="utf-8")
    assert mm.main(["--config", PERFIL_GS1, "--elegir", str(a), str(b), "--salida", str(salida), "--timeout", "60"]) == 0
    assert json.loads(salida.read_text(encoding="utf-8"))["eleccion"]["exposicion_ms"] == 3.906


def test_importa_camaras_uvc_antes_que_cv2() -> None:
    """La aceleracion HW de MSMF se apaga antes de cargar cv2 (CONTEXT.md 4.18); lo fija
    tambien test_aceleracion_msmf.MODULOS_MSMF en un proceso nuevo."""
    fuente = (ITER4_DIR / "medir_modos.py").read_text(encoding="utf-8")
    assert fuente.index("import camaras_uvc") < fuente.index("import cv2")


# ----------------------------------------------------------------------------
# Fase 4 (B33): la Medicion 2 con los intrinsecos reales en vez de la K nominal
# ----------------------------------------------------------------------------

class CamConK(CamFalsa):
    def __init__(self, frames, K, dist):
        super().__init__(frames)
        self._K, self._dist = K, dist

    def get_intrinsics(self):
        return self._K, self._dist


def test_cfg_camara_para_con_intrinsecos_conserva_el_yml() -> None:
    cam = cfg_gs1()["camera"]
    c = mm.cfg_camara_para(cam, (1280, 960, "MJPG"), 90, None, "data/intrinsecos_gs1_1280x960.yml")
    assert c["calibration_file"] == "data/intrinsecos_gs1_1280x960.yml" and c["width"] == 1280
    assert mm.cfg_camara_para(cam, (1280, 960, "MJPG"), 90, None)["calibration_file"] is None


def test_medir_fila_con_intrinsecos_usa_la_K_del_backend(monkeypatch, tmp_path) -> None:
    cfg = cfg_gs1()
    ctx = mm.preparar_tracking(cfg)
    monkeypatch.setattr(mm.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(mm.cv2, "waitKey", lambda *a, **k: -1)
    monkeypatch.setattr(mm.cv2, "destroyAllWindows", lambda: None)
    K_real = np.array([[333.0, 0.0, 150.0], [0.0, 333.0, 150.0], [0.0, 0.0, 1.0]])
    vistas = []

    def pose_espia(det, geom, K, dist):
        vistas.append(K.copy())
        return None
    monkeypatch.setattr(mm.tracker, "estimar_pose_rigid_body", pose_espia)
    ctx["min_markers"] = 1
    pedidos = []

    def abrir(cfg_camera):
        pedidos.append(cfg_camera)
        return CamConK([imagen_marker(4)], K_real, np.zeros(5))
    yml = str(tmp_path / "k.yml")
    fila = mm.medir_fila(cfg, ctx, (300, 300, "MJPG"), 90, None, 0.2, 0.2, None, abrir=abrir, intrinsecos=yml)
    assert pedidos[0]["calibration_file"] == yml and fila["intrinsecos"] == yml
    assert fila["K"] == K_real.tolist() and vistas and np.allclose(vistas[0], K_real)


def test_main_intrinsecos_solo_en_la_medicion_2(tmp_path, monkeypatch) -> None:
    yml = tmp_path / "k.yml"
    yml.write_text("%YAML:1.0\n", encoding="utf-8")
    with pytest.raises(SystemExit):           # con --exposiciones-ms no vale
        mm.main(_base(tmp_path, "--exposiciones-ms", "3.906", "--modo", "300x300:MJPG", "--fps", "90",
                      "--segundos-captura", "0.2", "--fov-grados", "84", "--luz", "2", "--intrinsecos", str(yml)))
    with pytest.raises(SystemExit):           # el .yml tiene que existir
        mm.main(_base(tmp_path, "--modos", "300x300:MJPG", "--fps", "90", "--segundos-captura", "0.2",
                      "--segundos-tracking", "0.2", "--luz", "2", "--intrinsecos", str(tmp_path / "no.yml")))
    monkeypatch.setattr(mm.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(mm.cv2, "waitKey", lambda *a, **k: -1)
    monkeypatch.setattr(mm.cv2, "destroyAllWindows", lambda: None)
    K_real, _ = mm.k_nominal(300, 300, 84.0)
    monkeypatch.setattr(mm, "abrir_por_perfil", lambda c: CamConK([imagen_marker(3)], K_real, np.zeros(5)))
    rc = mm.main(_base(tmp_path, "--modos", "300x300:MJPG", "--fps", "90", "--segundos-captura", "0.2",
                       "--segundos-tracking", "0.2", "--luz", "2", "--intrinsecos", str(yml)))   # sin --fov-grados
    assert rc == 0
    e = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert e["intrinsecos"] == str(yml) and e["fov_grados"] is None and e["filas"][0]["K"] == K_real.round(3).tolist()


def test_textos_de_enfoque_llanos_y_sin_acentos() -> None:
    """P19/P21 (fase 5): lo que se pinta sobre la imagen al enfocar; sin acentos (cv2.putText)."""
    l1, l2 = mm.textos_enfoque(156.4, 170.7)
    assert l1.isascii() and l2.isascii()
    assert l1.startswith("Nitidez: 156") and "171" in l1 and "q = terminar" in l2 and "Gira el lente" in l2
