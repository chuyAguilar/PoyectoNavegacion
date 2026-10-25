"""`diagnostics.identify_ids` sin camara (meta 003, fase 7b · Botones de tracker sin
ventana y de vista previa para posicionar las cámaras; clarify.md P13 = c).

Los dos modos (IDs y vista previa, `--no-detect`) salen limpio con `q`, con la
ventana cerrada (la X) y al `--timeout`; sin frames durante NO_FRAMES_S salen con
codigo 1 y lo dicen; cierran la camara y escriben `[Salida limpia]` siempre,
tambien si `read` lanza. `--config` y `--timeout` son obligatorios, `--timeout 0`
se rechaza y `--no-detect --permisivo` tambien. Con `--no-detect` no se crea el
detector ni se pasa a gris. `make_detector` da los mismos parametros que antes
de la fase (estricto y permisivo, campo a campo). Reloj falso: ninguna prueba
espera de verdad. La camara es la falsa de `synthetic` (fixture B34 de conftest).
"""
from __future__ import annotations

import itertools
import types
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from diagnostics import identify_ids
from vision.detection import apply_detector_params

from .conftest import PROFILES_DIR
from .synthetic import FakeCamera, render_marker

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"


def _clock(step_s: float) -> types.SimpleNamespace:
    """Un `time` falso: `perf_counter` avanza `step_s` por llamada."""
    n = itertools.count()
    return types.SimpleNamespace(perf_counter=lambda: 1000.0 + step_s * next(n))


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    gs1 = yaml.safe_load(GS1.read_text(encoding="utf-8"))
    cfg = {"camera": {"camera_type": "webcam"}, "markers": gs1["markers"]}
    ruta = tmp_path / "perfil_ids.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return ruta


@pytest.fixture
def fakes(monkeypatch):
    """Camara, ventana y reloj falsos en `identify_ids`; devuelve un lanzador."""
    est: dict = {}

    def run(frames, profile, extra=(), keys=(), visible=None, step_s=0.011, cam=None, loop=True):
        est.clear()
        est.update(imshow=0, destroy=0, titles=set(), named=[])
        cam = cam or FakeCamera(frames, loop=loop, delay_s=0.0)
        monkeypatch.setattr(identify_ids, "create_backend", lambda cfg_cam: cam)
        monkeypatch.setattr(identify_ids, "time", _clock(step_s))
        teclas = iter(keys)
        visibles = iter(visible) if visible is not None else None

        def imshow(title, img):
            est["imshow"] += 1
            est["titles"].add(title)
            assert img.ndim == 3 and img.shape[2] == 3
        monkeypatch.setattr(identify_ids.cv2, "namedWindow", lambda t, f=0: est["named"].append(t))
        monkeypatch.setattr(identify_ids.cv2, "imshow", imshow)
        monkeypatch.setattr(identify_ids.cv2, "waitKey", lambda ms: next(teclas, -1))
        monkeypatch.setattr(identify_ids.cv2, "getWindowProperty",
                            lambda t, p: (next(visibles, 1.0) if visibles is not None else 1.0))
        monkeypatch.setattr(identify_ids.cv2, "destroyAllWindows",
                            lambda: est.__setitem__("destroy", est["destroy"] + 1))
        rc = identify_ids.main(["--config", str(profile), "--timeout", "600", *extra])
        return rc, cam, est
    return run


@pytest.fixture(scope="module")
def frames() -> list[np.ndarray]:
    return [render_marker(450.0, 2.0 + 0.2 * i) for i in range(4)]


def _forbid_detection(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("con --no-detect no se detecta ni se pasa a gris")
    monkeypatch.setattr(identify_ids.cv2.aruco, "ArucoDetector", boom)
    monkeypatch.setattr(identify_ids.cv2, "cvtColor", boom)


def test_ids_sale_con_q_y_dibuja_los_ids(fakes, frames, profile, capsys) -> None:
    rc, cam, est = fakes(frames, profile, keys=[-1, -1, ord("q")])
    assert rc == 0 and cam.opened and cam.closed and est["destroy"] == 1
    assert est["imshow"] == 3 and est["titles"] == {identify_ids.WINDOW_TITLE}
    assert est["named"] == [identify_ids.WINDOW_TITLE]
    out = capsys.readouterr().out
    assert "visibles: [0]" in out and "[IDs] q: saliendo." in out and out.rstrip().endswith("[Salida limpia]")


def test_vista_previa_sin_deteccion_sale_con_q(fakes, frames, profile, capsys, monkeypatch) -> None:
    _forbid_detection(monkeypatch)
    monkeypatch.setattr(identify_ids, "REPORT_EVERY_S", 0.05)
    rc, cam, est = fakes(frames, profile, extra=["--no-detect"], keys=[-1] * 6 + [ord("q")])
    assert rc == 0 and cam.closed and est["destroy"] == 1
    assert est["titles"] == {identify_ids.PREVIEW_WINDOW_TITLE} and est["imshow"] == 7
    out = capsys.readouterr().out
    assert "[Vista previa] camara " in out and " fps" in out
    assert "visibles" not in out and "[Vista previa] q: saliendo." in out and "[Salida limpia]" in out


@pytest.mark.parametrize("extra", [[], ["--no-detect"]])
def test_sale_al_cerrar_la_ventana(fakes, frames, profile, capsys, extra) -> None:
    rc, cam, est = fakes(frames, profile, extra=extra, visible=[1.0, 1.0, 0.0])
    assert rc == 0 and cam.closed and est["imshow"] == 3
    out = capsys.readouterr().out
    assert "ventana cerrada: saliendo." in out and "[Salida limpia]" in out


@pytest.mark.parametrize("extra", [[], ["--no-detect"]])
def test_sale_al_tope(fakes, frames, profile, capsys, extra, monkeypatch) -> None:
    rc, cam, est = fakes(frames, profile, extra=extra, step_s=1.0)   # 1 s por llamada al reloj
    assert rc == 0 and cam.closed and est["destroy"] == 1
    out = capsys.readouterr().out
    assert "tope de 600 s: saliendo." in out and "[Salida limpia]" in out
    assert 250 <= est["imshow"] <= 600      # una o dos llamadas al reloj por vuelta


@pytest.mark.parametrize("extra", [[], ["--no-detect"]])
def test_sin_frames_sale_con_codigo_1(fakes, profile, capsys, extra) -> None:
    rc, cam, est = fakes([None], profile, extra=extra, step_s=1.0)
    assert rc == 1 and cam.closed and est["imshow"] == 0 and est["destroy"] == 1
    cap = capsys.readouterr()
    assert "la camara no entrega frames desde hace 10 s" in cap.err
    assert "[Salida limpia]" in cap.out


class _BrokenCamera(FakeCamera):
    def read(self):
        if self.i >= 2:
            raise RuntimeError("driver caido")
        return super().read()


@pytest.mark.parametrize("extra", [[], ["--no-detect"]])
def test_si_read_lanza_cierra_igual(fakes, frames, profile, capsys, extra) -> None:
    cam = _BrokenCamera(frames, loop=True, delay_s=0.0)
    with pytest.raises(RuntimeError, match="driver caido"):
        fakes(frames, profile, extra=extra, cam=cam)
    assert cam.closed
    assert "[Salida limpia]" in capsys.readouterr().out


def test_argumentos_obligatorios_y_excluyentes() -> None:
    cfg = ["--config", str(GS1)]
    ok = identify_ids.parse_args(cfg + ["--timeout", "2.5"])
    assert ok.timeout == 2.5 and not ok.no_detect and not ok.permisivo
    assert identify_ids.parse_args(cfg + ["--timeout", "600", "--no-detect"]).no_detect
    for malo in ([], ["--timeout", "600"], cfg, cfg + ["--timeout", "0"], cfg + ["--timeout", "-1"],
                 cfg + ["--timeout", "x"], cfg + ["--timeout", "600", "--no-detect", "--permisivo"]):
        with pytest.raises(SystemExit):
            identify_ids.parse_args(malo)


def _fields(params) -> dict:
    return {k: getattr(params, k) for k in dir(params)
            if not k.startswith("_") and not callable(getattr(params, k))}


def test_make_detector_da_los_parametros_de_antes() -> None:
    """Los mismos numeros que tenia main() antes de la fase 7b, campo a campo."""
    cfg = yaml.safe_load(GS1.read_text(encoding="utf-8"))["markers"]
    ref = cv2.aruco.DetectorParameters()
    ref.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    ref.minMarkerPerimeterRate = 0.05
    ref.polygonalApproxAccuracyRate = 0.03
    ref.maxErroneousBitsInBorderRate = 0.10
    ref.errorCorrectionRate = 0.35
    ref.minOtsuStdDev = 5.0
    strict = identify_ids.make_detector(cfg, permisive=False).getDetectorParameters()
    assert _fields(strict) == _fields(ref) and len(_fields(ref)) > 20

    ref_p = cv2.aruco.DetectorParameters()
    ref_p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    apply_detector_params(ref_p, cfg.get("detector", {}))
    perm = identify_ids.make_detector(cfg, permisive=True).getDetectorParameters()
    assert _fields(perm) == _fields(ref_p) and _fields(perm) != _fields(ref)


def test_draw_ids_y_draw_preview_pintan() -> None:
    frame = render_marker(450.0, 0.0)
    cfg = yaml.safe_load(GS1.read_text(encoding="utf-8"))["markers"]
    det = identify_ids.make_detector(cfg, permisive=False)
    corners, ids, _ = det.detectMarkers(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    disp = frame.copy()
    assert identify_ids.draw_ids(disp, corners, ids) == [0] and not np.array_equal(disp, frame)
    assert identify_ids.draw_ids(frame.copy(), (), None) == []
    prev = frame.copy()
    identify_ids.draw_preview(prev, None, "tracker_config_gs1.yaml")
    h, w = prev.shape[:2]
    assert tuple(prev[h // 2, 5]) == (0, 255, 255) and tuple(prev[h - 5, w // 2]) == (0, 255, 255)
    identify_ids.draw_preview(frame.copy(), 89.7, "tracker_config_gs1.yaml")
