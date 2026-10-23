"""calibrar_camara.py sin camara (meta 002, fase 4).

Vistas sinteticas proyectadas con una K conocida: `calibrar` la recupera (fx/fy
dentro del 0.1 %, RMS < 0.05 px, control < 0.05 px); `cobertura`; el lado desde
las medidas del calibrador; los dos detectores sobre una vista renderizada; el
.yml con sus extras; la captura con una camara falsa; `main --desde-vistas` de
punta a punta; y la receta del panel (square_mm y vistas_dir obligatorios).
"""
from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

import calibrar_camara as cc
import camera_backend
import perfil_editor
import recetas

from .conftest import ITER4_DIR
from . import tablero_sintetico as ts

PERFIL_GS1 = str(ITER4_DIR / "tracker_config_gs1.yaml")
COLS, ROWS, SQ = 8, 5, 24.97


class CamFalsa:
    """read() da los frames de `frames` en ciclo; registra close(); sin ajustes leidos."""

    def __init__(self, frames, ajustes_leidos=None, tamano_real=None):
        self.frames = list(frames)
        self.i = 0
        self.cerrada = False
        self.ajustes_leidos = ajustes_leidos
        self.tamano_real = tamano_real

    def open(self):
        pass

    def read(self):
        f = self.frames[self.i % len(self.frames)]
        self.i += 1
        return f, None, 0.0

    def close(self):
        self.cerrada = True


def sin_ventanas(monkeypatch):
    monkeypatch.setattr(cc.cv2, "namedWindow", lambda *a, **k: None)
    monkeypatch.setattr(cc.cv2, "imshow", lambda *a, **k: None)
    monkeypatch.setattr(cc.cv2, "destroyAllWindows", lambda: None)


@pytest.fixture(autouse=True)
def sin_camara_real(monkeypatch):
    """Ninguna prueba de este modulo puede abrir una camara real, aunque cambie un perfil
    (incidente de la fase 4: una prueba llego a create_backend con el perfil real)."""
    def _prohibido(*_a, **_k):
        raise AssertionError("una prueba intento abrir una camara real (create_backend)")
    monkeypatch.setattr(cc, "create_backend", _prohibido)


def _perfil_gs1_copia(tmp_path) -> str:
    """Copia temporal del perfil gs1 con el mismo nombre (mismo slug); sin calibration_file."""
    import yaml
    cfg = yaml.safe_load(open(PERFIL_GS1, encoding="utf-8"))
    cfg["camera"]["calibration_file"] = None
    d = tmp_path / "perfil"
    d.mkdir(exist_ok=True)
    ruta = d / "tracker_config_gs1.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(ruta)


# ----------------------------------------------------------------------------
# Funciones puras
# ----------------------------------------------------------------------------

def test_construir_objp() -> None:
    o = cc.construir_objp(COLS, ROWS, SQ)
    assert o.shape == (40, 3) and o.dtype == np.float32
    assert tuple(o[0]) == (0.0, 0.0, 0.0) and o[1][0] == pytest.approx(SQ) and o[COLS][1] == pytest.approx(SQ)
    assert not o[:, 2].any()


def test_lado_desde_medidas_y_comprobar_lado() -> None:
    medidas = [99.90, 99.85, 99.92, 99.88, 99.86]
    assert cc.lado_desde_medidas(medidas, 4) == pytest.approx(round(sum(medidas) / 5 / 4, 2))
    assert cc.comprobar_lado(24.97, medidas) == pytest.approx(24.97)
    with pytest.raises(ValueError, match="no coincide"):
        cc.comprobar_lado(25.00, medidas)
    with pytest.raises(ValueError, match="al menos 5"):
        cc.comprobar_lado(24.97, medidas[:4])
    with pytest.raises(ValueError):
        cc.lado_desde_medidas([], 4)
    with pytest.raises(ValueError):
        cc.lado_desde_medidas([100.0, -1.0], 4)
    with pytest.raises(ValueError):
        cc.lado_desde_medidas([100.0], 0)


def test_cobertura_y_celdas() -> None:
    shape = (1280, 960)
    assert cc.cobertura([], shape) == 0.0
    una = [np.array([[[10.0, 10.0]], [[20.0, 20.0]]], dtype=np.float32)]
    assert cc.celdas_cubiertas(una, shape) == {(0, 0)}
    assert cc.cobertura(una, shape) == pytest.approx(1 / 12)
    xs = np.linspace(5, 1275, 40)
    ys = np.linspace(5, 955, 30)
    todas = [np.array([[[x, y]] for x in xs for y in ys], dtype=np.float32)]
    assert cc.cobertura(todas, shape) == 1.0
    borde = [np.array([[[1280.0, 960.0]]])]                 # en el borde exacto cae en la ultima celda
    assert cc.celdas_cubiertas(borde, shape) == {(3, 2)}
    assert cc.cobertura(una, shape, celdas=(2, 2)) == 0.25
    with pytest.raises(ValueError):
        cc.celdas_cubiertas(una, (0, 960))


def test_elegir_control() -> None:
    a = cc.elegir_control(20, 3, semilla=7)
    assert a == sorted(a) and len(set(a)) == 3 and all(0 <= i < 20 for i in a)
    assert cc.elegir_control(20, 3, semilla=7) == a           # reproducible
    assert cc.elegir_control(20, 3, semilla=8) != a or True   # otra semilla puede coincidir; no se exige
    assert cc.elegir_control(5, 0) == []
    with pytest.raises(ValueError):
        cc.elegir_control(5, 5)
    with pytest.raises(ValueError):
        cc.elegir_control(5, -1)


def test_evaluar_criterio() -> None:
    bien = {"n_vistas_usadas": 17, "rms_px": 0.3, "rms_control_px": 0.5}
    assert cc.evaluar_criterio(bien, 0.9) == []
    f = cc.evaluar_criterio({"n_vistas_usadas": 10, "rms_px": 0.6, "rms_control_px": 0.9}, 0.5)
    assert len(f) == 4 and any("vistas" in x for x in f) and any("RMS 0.600" in x for x in f)
    assert any("control" in x for x in f) and any("cobertura" in x for x in f)
    assert cc.evaluar_criterio(dict(bien, rms_control_px=None), 0.9) == ["sin vistas de control"]
    assert cc.evaluar_criterio(dict(bien, n_vistas_usadas=5), 0.9, {"rms_px": 0.5, "rms_control_px": 0.75,
                                                                    "cobertura": 0.8, "min_vistas": 5}) == []


def test_elegir_ganador() -> None:
    # La sesion en vivo de la fase 4: gana sb (0.146 < 0.181).
    assert cc.elegir_ganador({"clasico": {"rms_control_px": 0.1806, "cumple": True},
                              "sb": {"rms_control_px": 0.1458, "cumple": True}}) == "sb"
    assert cc.elegir_ganador({"clasico": {"rms_control_px": 0.12, "cumple": True},
                              "sb": {"rms_control_px": 0.15, "cumple": True}}) == "clasico"
    # Gana el que cumple aunque el otro tenga menor control.
    assert cc.elegir_ganador({"clasico": {"rms_control_px": 0.30, "cumple": True},
                              "sb": {"rms_control_px": 0.10, "cumple": False}}) == "clasico"
    # Ninguno cumple: el de menor control. Empate: el primero de DETECTORES.
    assert cc.elegir_ganador({"clasico": {"rms_control_px": 0.9, "cumple": False},
                              "sb": {"rms_control_px": 0.8, "cumple": False}}) == "sb"
    assert cc.elegir_ganador({"sb": {"rms_control_px": 0.2, "cumple": True},
                              "clasico": {"rms_control_px": 0.2, "cumple": True}}) == "clasico"
    assert cc.elegir_ganador({"sb": {"rms_control_px": 0.2, "cumple": True},
                              "clasico": {"rms_control_px": None, "cumple": False}}) == "sb"
    with pytest.raises(ValueError):
        cc.elegir_ganador({"clasico": {"rms_control_px": None, "cumple": True}})
    with pytest.raises(ValueError):
        cc.elegir_ganador({})
    assert "ambos" in cc.MODOS_DETECTOR and "ambos" not in cc.DETECTORES


# ----------------------------------------------------------------------------
# Calibrar con vistas sinteticas
# ----------------------------------------------------------------------------

K_TRUE = ts.K_de(1050.0, 1045.0, 650.0, 470.0)
DIST_TRUE = np.array([-0.08, 0.03, 0.0005, -0.0003, 0.0])
SHAPE = (1280, 960)


@pytest.fixture(scope="module")
def sinteticas():
    return ts.vistas_sinteticas(K_TRUE, DIST_TRUE, COLS, ROWS, SQ, SHAPE, n=20, semilla=3)


def test_calibrar_recupera_la_K_sintetica(sinteticas) -> None:
    objs, imgs, _poses = sinteticas
    r = cc.calibrar(objs, imgs, SHAPE, n_control=3, semilla=1)
    assert r["n_vistas_usadas"] == 17 and r["n_control"] == 3
    assert not set(r["indices_fit"]) & set(r["indices_control"]) and len(r["indices_fit"]) + 3 == 20
    assert r["K"][0, 0] == pytest.approx(K_TRUE[0, 0], rel=1e-3)
    assert r["K"][1, 1] == pytest.approx(K_TRUE[1, 1], rel=1e-3)
    assert r["K"][0, 2] == pytest.approx(K_TRUE[0, 2], abs=2.0) and r["K"][1, 2] == pytest.approx(K_TRUE[1, 2], abs=2.0)
    assert r["rms_px"] < 0.05 and r["rms_control_px"] < 0.05
    assert len(r["errores_vista_px"]) == 17 and max(r["errores_vista_px"]) < 0.05
    assert len(r["errores_control_px"]) == 3 and r["dist"].shape == (5,)
    assert r["dist"][0] == pytest.approx(DIST_TRUE[0], abs=5e-3)
    assert set(r["std_intrinsecos"]) == {"fx", "fy", "cx", "cy"} and r["std_intrinsecos"]["fx"] < 1.0
    assert len(r["rvecs"]) == 17 and len(r["tvecs"]) == 17
    assert cc.rms_control([objs[i] for i in r["indices_control"]], [imgs[i] for i in r["indices_control"]],
                          r["K"], r["dist"]) == pytest.approx(r["rms_control_px"])
    r2 = cc.calibrar(objs, imgs, SHAPE, n_control=3, semilla=1)
    assert r2["indices_control"] == r["indices_control"] and r2["rms_px"] == pytest.approx(r["rms_px"])
    assert cc.evaluar_criterio(r, cc.cobertura([imgs[i] for i in r["indices_fit"]], SHAPE)) == []


def test_calibrar_sin_control_y_errores(sinteticas) -> None:
    objs, imgs, _p = sinteticas
    r = cc.calibrar(objs[:6], imgs[:6], SHAPE, n_control=0)
    assert r["indices_control"] == [] and r["rms_control_px"] is None and r["n_vistas_usadas"] == 6
    with pytest.raises(ValueError):
        cc.calibrar(objs[:5], imgs[:4], SHAPE)
    with pytest.raises(ValueError):
        cc.calibrar(objs[:1], imgs[:1], SHAPE, n_control=0)
    with pytest.raises(ValueError):
        cc.calibrar(objs[:4], imgs[:4], SHAPE, n_control=3)      # quedaria 1 para el ajuste
    with pytest.raises(ValueError):
        cc.rms_control([], [], K_TRUE, DIST_TRUE)


def test_rms_control_con_la_K_verdadera_es_cero(sinteticas) -> None:
    objs, imgs, _p = sinteticas
    e = cc.errores_control(objs[:3], imgs[:3], K_TRUE, DIST_TRUE)
    assert len(e) == 3 and max(e) < 1e-3
    assert cc.rms_control(objs[:3], imgs[:3], K_TRUE, DIST_TRUE) < 1e-3
    K_mala = K_TRUE.copy()
    K_mala[0, 0] *= 1.05
    assert cc.rms_control(objs[:3], imgs[:3], K_mala, DIST_TRUE) > 0.5


# ----------------------------------------------------------------------------
# Detectores sobre una vista renderizada
# ----------------------------------------------------------------------------

K_640 = ts.K_de(600.0, 600.0, 320.0, 240.0)
SHAPE_640 = (640, 480)
RVEC_1 = np.array([0.25, -0.2, 0.1])
TVEC_1 = ts.pose_hacia(K_640, RVEC_1, (330.0, 235.0), 600.0, COLS, ROWS, SQ)


@pytest.fixture(scope="module")
def vista_640():
    return ts.renderizar_vista(K_640, RVEC_1, TVEC_1, COLS, ROWS, SQ, SHAPE_640)


@pytest.mark.parametrize("metodo", cc.DETECTORES)
def test_detectar_esquinas_en_vista_renderizada(vista_640, metodo: str) -> None:
    c = cc.detectar_esquinas(vista_640, COLS, ROWS, metodo)
    assert c is not None and c.shape == (COLS * ROWS, 1, 2) and c.dtype == np.float32
    verdad = ts.proyectar(cc.construir_objp(COLS, ROWS, SQ), RVEC_1, TVEC_1, K_640).reshape(-1, 2)
    d = np.linalg.norm(c.reshape(-1, 2) - verdad, axis=1)
    if d.mean() > 1.0:                      # el detector puede devolver el tablero recorrido al reves
        d = np.linalg.norm(c.reshape(-1, 2)[::-1] - verdad, axis=1)
    assert d.mean() < 0.5, f"{metodo}: error medio {d.mean():.3f} px"
    assert cc.detectar_esquinas(ts.a_bgr(vista_640), COLS, ROWS, metodo, rapido=True) is not None
    assert cc.detectar_esquinas(np.full((480, 640), 128, dtype=np.uint8), COLS, ROWS, metodo) is None


def test_detectar_esquinas_metodo_desconocido(vista_640) -> None:
    with pytest.raises(ValueError):
        cc.detectar_esquinas(vista_640, COLS, ROWS, "otro")


def test_detectar_vistas_descarta_las_sin_tablero(vista_640) -> None:
    lisa = np.full_like(vista_640, 128)
    pts, idx = cc.detectar_vistas([vista_640, lisa, vista_640], COLS, ROWS, "clasico")
    assert len(pts) == 2 and idx == [0, 2]


# ----------------------------------------------------------------------------
# Vistas en disco y el .yml
# ----------------------------------------------------------------------------

def test_cargar_vistas(tmp_path, vista_640) -> None:
    with pytest.raises(FileNotFoundError):
        cc.listar_vistas(tmp_path / "no")
    with pytest.raises(ValueError):
        cc.cargar_vistas(tmp_path)
    cv2.imwrite(str(tmp_path / "vista_02.png"), vista_640)
    cv2.imwrite(str(tmp_path / "vista_01.png"), ts.a_bgr(vista_640))
    (tmp_path / "captura.json").write_text("{}", encoding="utf-8")
    v = cc.cargar_vistas(tmp_path)
    assert len(v) == 2 and all(x.ndim == 2 and x.shape == (480, 640) for x in v)
    assert [p.name for p in cc.listar_vistas(tmp_path)] == ["vista_01.png", "vista_02.png"]
    cv2.imwrite(str(tmp_path / "vista_03.png"), vista_640[:240, :320])
    with pytest.raises(ValueError, match="mismo tamano"):
        cc.cargar_vistas(tmp_path)


def test_guardar_yml_con_extra(tmp_path) -> None:
    ruta = tmp_path / "intrinsecos_gs1_1280x960.yml"
    extra = {"detector": "sb", "rms_control_px": 0.41, "cobertura": 0.9167,
             "std_intrinsecos": {"fx": 0.8, "fy": 0.7, "cx": 0.5, "cy": 0.4},
             "usb_port_windows": "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(3)",
             "modo": {"width": 1280, "height": 960, "fps": 90, "fourcc": "MJPG", "backend": "MSMF"},
             "ajustes_leidos": {"exposure_ms": 0.977, "gain": 11.0},
             "errores_vista_px": [0.3, 0.4], "medidas_calibrador_mm": [99.9, 99.85],
             "criterio_cumplido": True, "luz": None}
    cc.guardar_yml(ruta, K_TRUE, DIST_TRUE, 1280, 960, 0.37, 17, COLS, ROWS, SQ, extra)
    assert camera_backend.leer_tamano_yml(ruta) == (1280, 960)
    assert perfil_editor.validar_yml_intrinsecos(ruta) is None
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    try:
        assert np.allclose(fs.getNode("camera_matrix").mat(), K_TRUE)
        assert np.allclose(fs.getNode("distortion_coefficients").mat().flatten(), DIST_TRUE)
        assert fs.getNode("square_mm").real() == pytest.approx(SQ)
        assert fs.getNode("detector").string() == "sb"
        assert fs.getNode("usb_port_windows").string() == extra["usb_port_windows"]
        assert fs.getNode("modo").getNode("width").real() == 1280 and fs.getNode("modo").getNode("fourcc").string() == "MJPG"
        assert fs.getNode("ajustes_leidos").getNode("exposure_ms").real() == pytest.approx(0.977)
        e = fs.getNode("errores_vista_px")
        assert e.isSeq() and [e.at(i).real() for i in range(e.size())] == [0.3, 0.4]
        assert fs.getNode("criterio_cumplido").real() == 1 and fs.getNode("luz").string() == ""
        assert fs.getNode("n_views").real() == 17
    finally:
        fs.release()
    # El backend la carga tal cual
    b = camera_backend.WebcamBackend(source=0, width=1280, height=960, calibration_file=str(ruta))
    b._load_calibration()
    K, d = b.get_intrinsics()
    assert np.allclose(K, K_TRUE) and d.shape == (5,)


# ----------------------------------------------------------------------------
# Captura con camara falsa
# ----------------------------------------------------------------------------

def test_capturar_vistas_con_camara_falsa(tmp_path, monkeypatch, vista_640) -> None:
    sin_ventanas(monkeypatch)
    monkeypatch.setattr(cc, "ANTIRREBOTE_S", 0.0)
    lisa = np.full((480, 640, 3), 128, dtype=np.uint8)
    cam = CamFalsa([ts.a_bgr(vista_640), ts.a_bgr(vista_640), lisa, ts.a_bgr(vista_640), ts.a_bgr(vista_640)])
    teclas = iter([ord(" "), ord(" "), ord(" "), ord("u"), ord(" "), ord("q")])
    rutas = cc.capturar_vistas(cam, COLS, ROWS, "clasico", limite=float("inf"), vistas_dir=tmp_path / "v",
                               min_total=18, leer_tecla=lambda: next(teclas, ord("q")))
    # frames: vista(cap 1), vista(cap 2), lisa (ESPACIO sin tablero: no captura), vista (u: quita la 2), vista (cap 2)
    assert [r.name for r in rutas] == ["vista_01.png", "vista_02.png"]
    assert sorted(p.name for p in (tmp_path / "v").iterdir()) == ["vista_01.png", "vista_02.png"]
    assert cc.cargar_vistas(tmp_path / "v")[0].shape == (480, 640)


def test_capturar_vistas_respeta_el_limite(tmp_path, monkeypatch, vista_640) -> None:
    sin_ventanas(monkeypatch)
    cam = CamFalsa([ts.a_bgr(vista_640)])
    rutas = cc.capturar_vistas(cam, COLS, ROWS, "clasico", limite=0.0, vistas_dir=tmp_path / "v",
                               min_total=18, leer_tecla=lambda: ord(" "))
    assert rutas == [] and cam.i == 0


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

K_GS = ts.K_de(720.0, 720.0, 640.0, 480.0)


def _vistas_gs1(directorio, n_por_celda: int = 1) -> int:
    """Una vista por celda de la rejilla 4x3 a 1280x960 (cobertura alta con pocas vistas)."""
    directorio.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(5)
    k = 0
    for iy in range(3):
        for ix in range(4):
            for _ in range(n_por_celda):
                objetivo = ((ix + 0.5) * 1280 / 4, (iy + 0.5) * 960 / 3)
                rvec = rng.uniform(-0.3, 0.3, size=3)
                tvec = ts.pose_hacia(K_GS, rvec, objetivo, rng.uniform(550, 750), COLS, ROWS, SQ)
                g = ts.renderizar_vista(K_GS, rvec, tvec, COLS, ROWS, SQ, SHAPE)
                k += 1
                cv2.imwrite(str(directorio / f"vista_{k:02d}.png"), g)
    return k


def _argv(tmp_path, *extra: str) -> list[str]:
    return ["--config", PERFIL_GS1, "--output", str(tmp_path / "intrinsecos_gs1_1280x960.yml"),
            "--square-mm", f"{SQ}", "--cols", str(COLS), "--rows", str(ROWS), "--timeout", "60", *extra]


def test_main_desde_vistas_de_punta_a_punta(tmp_path) -> None:
    vistas = tmp_path / "vistas_gs1"
    n = _vistas_gs1(vistas)
    cc.guardar_captura_json(vistas, {"fecha": "2026-10-22 10:00:00", "puerto": "P", "ajustes_leidos": {"exposure_ms": 0.977}})
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv(tmp_path, "--detector", "clasico", "--desde-vistas", str(vistas), "--min-vistas", "8",
                       "--n-control", "2", "--medidas-mm", "99.90,99.85,99.92,99.88,99.86",
                       "--reporte", str(reporte), "--luz", "caja nivel 2"))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    r = e["resultado"]
    assert rc == 0, r["fallos"]
    assert e["vistas"] == {"total": n, "detectadas": n, "indices_detectados": list(range(n))}
    assert r["n_vistas_usadas"] == n - 2 and len(r["indices_control"]) == 2 and r["cumple"] is True
    assert r["rms_px"] < 0.3 and r["rms_control_px"] < 0.3 and r["cobertura"] >= 0.8
    # Vistas renderizadas con poca inclinacion (+-0.3 rad): fx queda a ~1.5 % (std ~8 px); la
    # exactitud fina la fija test_calibrar_recupera_la_K_sintetica con puntos proyectados.
    assert r["K"][0][0] == pytest.approx(720.0, rel=0.03) and r["K"][1][1] == pytest.approx(720.0, rel=0.03)
    assert e["captura"]["ajustes_leidos"] == {"exposure_ms": 0.977} and e["luz"] == "caja nivel 2"
    yml = tmp_path / "intrinsecos_gs1_1280x960.yml"
    assert camera_backend.leer_tamano_yml(yml) == (1280, 960)
    fs = cv2.FileStorage(str(yml), cv2.FILE_STORAGE_READ)
    try:
        assert fs.getNode("usb_port_windows").string().endswith("#USB(3)")
        assert fs.getNode("ajustes_leidos").getNode("exposure_ms").real() == pytest.approx(0.977)
        assert fs.getNode("criterio_cumplido").real() == 1 and fs.getNode("detector").string() == "clasico"
        assert fs.getNode("square_mm_medido").real() == pytest.approx(SQ)
        m = fs.getNode("medidas_calibrador_mm")
        assert m.size() == 5 and m.at(0).real() == pytest.approx(99.90)
    finally:
        fs.release()


def test_main_desde_vistas_pocas_vistas_falla_fuerte(tmp_path) -> None:
    vistas = tmp_path / "v"
    _vistas_gs1(vistas)
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv(tmp_path, "--detector", "clasico", "--desde-vistas", str(vistas), "--min-vistas", "15",
                       "--n-control", "3", "--reporte", str(reporte)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 1 and "hacen falta 18 vistas" in e["error"] and not (tmp_path / "intrinsecos_gs1_1280x960.yml").exists()


def test_main_vistas_de_otro_tamano_que_el_perfil(tmp_path, vista_640) -> None:
    vistas = tmp_path / "v"
    vistas.mkdir()
    cv2.imwrite(str(vistas / "vista_01.png"), vista_640)
    cv2.imwrite(str(vistas / "vista_02.png"), vista_640)
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv(tmp_path, "--detector", "clasico", "--desde-vistas", str(vistas), "--min-vistas", "2",
                       "--n-control", "0", "--reporte", str(reporte)))
    assert rc == 1 and "640x480" in json.loads(reporte.read_text(encoding="utf-8"))["error"]


@pytest.mark.parametrize("quitar,anadir", [
    ("--square-mm", []),                                                   # sin lado medido
    (None, ["--detector", "clasico"]),                                     # con camara sin --vistas-dir
    (None, ["--detector", "clasico", "--vistas-dir", "v", "--medidas-mm", "100,100,100,100,100"]),  # 25.00 != 24.97
    (None, ["--detector", "clasico", "--vistas-dir", "v", "--medidas-mm", "99.88,99.88"]),           # < 5 medidas
    (None, ["--detector", "raro", "--vistas-dir", "v"]),
    (None, ["--vistas-dir", "v"]),                                         # sin --detector
])
def test_main_exige_argumentos_explicitos(tmp_path, quitar, anadir) -> None:
    argv = _argv(tmp_path, *anadir)
    if quitar:
        i = argv.index(quitar)
        del argv[i:i + 2]
    with pytest.raises(SystemExit):
        cc.main(argv)


# ----------------------------------------------------------------------------
# --detector ambos (P18): los dos detectores sobre las mismas vistas, gana el de menor control
# ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def vistas_gs1_modulo(tmp_path_factory):
    d = tmp_path_factory.mktemp("ambos") / "vistas_gs1"
    return d, _vistas_gs1(d)


def _argv_copia(tmp_path, *extra: str) -> list[str]:
    return ["--config", _perfil_gs1_copia(tmp_path), "--output", str(tmp_path / "salida" / "intrinsecos_gs1_1280x960.yml"),
            "--square-mm", f"{SQ}", "--cols", str(COLS), "--rows", str(ROWS), "--timeout", "60", *extra]


def _leer_yml(ruta):
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    try:
        comp = fs.getNode("detector_comparacion")
        return {"K": fs.getNode("camera_matrix").mat(), "detector": fs.getNode("detector").string(),
                "detector_captura": fs.getNode("detector_captura").string(),
                "comparacion": {k: comp.getNode(k).real() for k in cc.DETECTORES} if not comp.empty() else None,
                "criterio_cumplido": fs.getNode("criterio_cumplido").real()}
    finally:
        fs.release()


def test_main_ambos_gana_el_de_menor_control(tmp_path, vistas_gs1_modulo, capsys) -> None:
    vistas, n = vistas_gs1_modulo
    reporte = tmp_path / "calibracion_gs1_ambos.json"
    rc = cc.main(_argv_copia(tmp_path, "--detector", "ambos", "--desde-vistas", str(vistas), "--min-vistas", "8",
                             "--n-control", "2", "--reporte", str(reporte), "--luz", "caja nivel 2"))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 0, e.get("error") or e["resultado"]["fallos"]
    dets = e["detectores"]
    assert set(dets) == {"clasico", "sb"} and all(dets[d]["cumple"] for d in dets)
    control = {d: dets[d]["rms_control_px"] for d in dets}
    ganador = min(control, key=control.get)
    perdedor = ({"clasico", "sb"} - {ganador}).pop()
    assert e["ganador"] == ganador and e["resultado"]["detector"] == ganador and e["detector"] == "ambos"
    assert e["resultado"]["K"] == dets[ganador]["K"] and e["resultado"]["rms_control_px"] == control[ganador]
    # Las mismas vistas (todas detectadas por los dos) y las mismas de control.
    assert dets["clasico"]["vistas"]["indices_detectados"] == dets["sb"]["vistas"]["indices_detectados"] == list(range(n))
    assert dets["clasico"]["indices_control"] == dets["sb"]["indices_control"]
    # Solo el ganador se escribe; el perdedor no pisa nada.
    salida = tmp_path / "salida"
    assert [p.name for p in salida.iterdir()] == ["intrinsecos_gs1_1280x960.yml"]
    y = _leer_yml(salida / "intrinsecos_gs1_1280x960.yml")
    assert y["detector"] == ganador and y["detector_captura"] == "clasico" and y["criterio_cumplido"] == 1
    assert np.allclose(y["K"], dets[ganador]["K"]) and not np.array_equal(y["K"], np.array(dets[perdedor]["K"]))
    assert y["comparacion"] == pytest.approx(control)
    log = capsys.readouterr().out
    assert "[clasico] RMS de control" in log and "[sb] RMS de control" in log
    assert f"Detectores, RMS de control: clasico {control['clasico']:.4f} px, sb {control['sb']:.4f} px -> gana {ganador}" in log
    assert f"Detector ganador: {ganador}" in log


def test_main_ambos_con_un_detector_que_no_ve_el_tablero(tmp_path, vistas_gs1_modulo, monkeypatch) -> None:
    vistas, _n = vistas_gs1_modulo
    original = cc.detectar_esquinas
    monkeypatch.setattr(cc, "detectar_esquinas",
                        lambda g, c, r, metodo, rapido=False: None if metodo == "sb" else original(g, c, r, metodo, rapido))
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv_copia(tmp_path, "--detector", "ambos", "--desde-vistas", str(vistas), "--min-vistas", "8",
                             "--n-control", "2", "--reporte", str(reporte)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 0 and e["ganador"] == "clasico"
    assert "hacen falta 10 vistas" in e["detectores"]["sb"]["error"] and e["detectores"]["sb"]["vistas"]["detectadas"] == 0
    assert _leer_yml(tmp_path / "salida" / "intrinsecos_gs1_1280x960.yml")["detector"] == "clasico"


def test_main_ambos_sin_ningun_detector_falla_fuerte(tmp_path, vistas_gs1_modulo, monkeypatch) -> None:
    vistas, _n = vistas_gs1_modulo
    monkeypatch.setattr(cc, "detectar_esquinas", lambda *a, **k: None)
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv_copia(tmp_path, "--detector", "ambos", "--desde-vistas", str(vistas), "--min-vistas", "8",
                             "--n-control", "2", "--reporte", str(reporte)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 1 and "ningun detector pudo calibrar" in e["error"]
    assert not (tmp_path / "salida").exists()


def test_main_ambos_exige_vistas_de_control(tmp_path) -> None:
    with pytest.raises(SystemExit):
        cc.main(_argv_copia(tmp_path, "--detector", "ambos", "--desde-vistas", str(tmp_path), "--n-control", "0"))


def test_main_ambos_con_camara_falsa_captura_con_el_clasico(tmp_path, vistas_gs1_modulo, monkeypatch) -> None:
    vistas, n = vistas_gs1_modulo
    sin_ventanas(monkeypatch)
    monkeypatch.setattr(cc, "ANTIRREBOTE_S", 0.0)
    frames = [cv2.imread(str(p), cv2.IMREAD_COLOR) for p in cc.listar_vistas(vistas)]
    cam = CamFalsa(frames, ajustes_leidos={"exposure_ms": 0.977}, tamano_real=(1280, 960))
    monkeypatch.setattr(cc, "abrir_sin_yml", lambda cfg: cam)
    teclas = iter([ord(" ")] * n)
    monkeypatch.setattr(cc.cv2, "waitKey", lambda *a, **k: next(teclas, ord("q")))
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv_copia(tmp_path, "--detector", "ambos", "--vistas-dir", str(tmp_path / "capturadas"),
                             "--min-vistas", "8", "--n-control", "2", "--reporte", str(reporte)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 0, e.get("error")
    assert cam.cerrada and e["captura"]["detector_captura"] == "clasico" and e["captura"]["n_vistas"] == n
    assert cc.leer_captura_json(tmp_path / "capturadas")["ajustes_leidos"] == {"exposure_ms": 0.977}
    assert e["ganador"] in cc.DETECTORES and set(e["detectores"]) == set(cc.DETECTORES)


def test_main_un_detector_sigue_igual(tmp_path, vistas_gs1_modulo) -> None:
    """Los modos clasico y sb no cambian: sin 'detectores' ni 'ganador' en el reporte, sin prefijo en el log."""
    vistas, n = vistas_gs1_modulo
    reporte = tmp_path / "cal.json"
    rc = cc.main(_argv_copia(tmp_path, "--detector", "sb", "--desde-vistas", str(vistas), "--min-vistas", "8",
                             "--n-control", "2", "--reporte", str(reporte)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 0 and "detectores" not in e and "ganador" not in e and e["resultado"]["detector"] == "sb"
    assert e["vistas"]["detectadas"] == n
    y = _leer_yml(tmp_path / "salida" / "intrinsecos_gs1_1280x960.yml")
    assert y["detector"] == "sb" and y["comparacion"] is None and y["detector_captura"] == ""


# ----------------------------------------------------------------------------
# La receta del panel
# ----------------------------------------------------------------------------

def test_receta_calibrar_camara_explicita() -> None:
    r = recetas.receta_calibrar_camara(PERFIL_GS1, "iter4/data/intrinsecos_gs1_1280x960.yml", 24.97,
                                       "../Claude outputs/camaras/vistas_gs1", detector="sb", luz="caja nivel 2")
    a = r.argv
    assert a[2] == "iter4/calibrar_camara.py" and a[a.index("--square-mm") + 1] == "24.97"
    assert a[a.index("--detector") + 1] == "sb" and a[a.index("--vistas-dir") + 1].endswith("vistas_gs1")
    assert a[a.index("--min-vistas") + 1] == "15" and a[a.index("--n-control") + 1] == "3"
    assert a[a.index("--luz") + 1] == "caja nivel 2" and a[a.index("--timeout") + 1] == "900"
    assert r.ventana_titulo == cc.TITULO_VENTANA and r.usa_camara
    assert r.outputs == [recetas._rel("iter4/data/intrinsecos_gs1_1280x960.yml")]
    assert "24.97 mm medidos" in r.descripcion


@pytest.mark.parametrize("kwargs", [
    {"square_mm": None}, {"square_mm": "abc"}, {"square_mm": 25000}, {"square_mm": 0.0},
    {"detector": "raro"}, {"vistas_dir": ""}, {"output": ""},
])
def test_receta_calibrar_camara_rechaza(kwargs) -> None:
    base = {"output": "x.yml", "square_mm": 24.97, "vistas_dir": "v"}
    base.update(kwargs)
    with pytest.raises(ValueError):
        recetas.receta_calibrar_camara(PERFIL_GS1, **base)


def test_receta_calibrar_camara_sin_square_mm_no_compila() -> None:
    with pytest.raises(TypeError):
        recetas.receta_calibrar_camara(PERFIL_GS1, "x.yml")        # square_mm y vistas_dir sin default


@pytest.mark.parametrize("modulo", ["calibrar_camara", "comprobar_escala"])
def test_importa_camaras_uvc_antes_que_cv2(modulo: str) -> None:
    fuente = (ITER4_DIR / f"{modulo}.py").read_text(encoding="utf-8")
    assert fuente.index("import camaras_uvc") < fuente.index("import cv2")


def test_textos_de_la_ventana_llanos_y_sin_acentos() -> None:
    """P21 (fase 5): lo que se pinta sobre la imagen al tomar las fotos; cv2.putText (Hershey) pinta
    '??' por cada letra con acento, y nada de 'vistas', 'cobertura' ni el nombre del detector."""
    for visto in (True, False):
        l1, l2 = cc.textos_ventana(12, 18, 9, 12, visto)
        assert l1.isascii() and l2.isascii()
        assert "Fotos: 12" in l1 and "zonas cubiertas 9 de 12" in l1 and ("NO lo veo" in l1) is (not visto)
        assert "ESPACIO = tomar foto" in l2 and "u = borrar la ultima" in l2 and "q = terminar" in l2
        for jerga in ("vistas", "cobertura", "clasico", "sb", "RMS"):
            assert jerga not in (l1 + l2).split(), jerga
