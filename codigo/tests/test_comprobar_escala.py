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

import calibrar_camara as cc
import comprobar_escala as ce

from .conftest import ITER4_DIR
from . import tablero_sintetico as ts

PERFIL_GS1 = str(ITER4_DIR / "tracker_config_gs1.yaml")
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
    cfg = yaml.safe_load((ITER4_DIR / "tracker_config_gs1.yaml").read_text(encoding="utf-8"))
    cfg["camera"] = {"camera_type": "webcam", "source": 0, "width": 640, "height": 480, "fps": 30,
                     "backend": "MSMF", "fourcc": "MJPG", "calibration_file": yml.name}
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
