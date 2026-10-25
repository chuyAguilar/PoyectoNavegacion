"""El bucle de `tracker.main()` con una camara y un emisor falsos (meta 003, fase 4).

Sale con `q` y cierra todo (camara, emisor, ventana); `--config` es obligatorio;
`send_video: true` aborta antes de crear nada (P7); sin frames la camara se da
por perdida y se cierra limpio; lo que se envia es lo que `MarkerTracker` da; y
`draw_poses` pinta sobre el frame. Ninguna prueba abre una camara ni un puerto
(B34, fixture de conftest).
"""
from __future__ import annotations

import types
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

import tracker
from vision.tracking import MarkerTracker

from .conftest import PROFILES_DIR
from .synthetic import DIST_SYN, K_SYN, FakeCamera, FakeSender, render_marker

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"


@pytest.fixture
def profile_syn(tmp_path: Path):
    """El perfil gs1 sin camara real (webcam por indice: el backend no se usa, se inyecta uno falso)."""
    gs1 = yaml.safe_load(GS1.read_text(encoding="utf-8"))

    def make(**igtl):
        cfg = {"camera": {"camera_type": "webcam"}, "markers": gs1["markers"],
               "igtlink": {"transforms_port": 18944, "video_port": 18945, "send_video": False, **igtl},
               "filtering": gs1["filtering"], "debug": {"show_window": True, "verbose": False}}
        ruta = tmp_path / "perfil_syn.yaml"
        ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        return ruta
    return make


@pytest.fixture
def fakes(monkeypatch):
    """Camara, emisor y reloj falsos inyectados en el modulo tracker; devuelve un lanzador."""
    estado: dict = {"imshow": 0, "destroy": 0, "keys": []}

    def run(frames, profile, extra=(), keys=None, loop=False):
        cam = FakeCamera(frames, loop=loop)
        FakeSender.instances = []
        reloj = iter(np.arange(1000.0, 1000.0 + 0.011 * (10 * len(frames) + 500), 0.011).tolist())
        monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: cam)
        monkeypatch.setattr(tracker, "IgtlSender", FakeSender)
        monkeypatch.setattr(tracker, "time", types.SimpleNamespace(time=lambda: next(reloj)))
        teclas = iter(keys or [])

        def imshow(title, img):
            estado["imshow"] += 1
            estado["title"] = title
            assert img.shape[2] == 3
        monkeypatch.setattr(tracker.cv2, "imshow", imshow)
        monkeypatch.setattr(tracker.cv2, "waitKey", lambda ms: next(teclas, -1))
        monkeypatch.setattr(tracker.cv2, "destroyAllWindows",
                            lambda: estado.__setitem__("destroy", estado["destroy"] + 1))
        rc = tracker.main(["--config", str(profile), *extra])
        return rc, cam, (FakeSender.instances[0] if FakeSender.instances else None), estado
    return run


@pytest.fixture(scope="module")
def frames_syn() -> list[np.ndarray]:
    return [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i) for i in range(8)]


def test_sale_con_q_y_cierra_todo(fakes, frames_syn, profile_syn) -> None:
    rc, cam, sender, est = fakes(frames_syn, profile_syn(), keys=[-1, -1, -1, -1, ord("q")], loop=True)
    assert rc == 0
    assert cam.opened and cam.closed and sender.closed
    assert sender.port == 18944
    assert est["imshow"] == 5 and est["destroy"] == 1 and est["title"] == tracker.WINDOW_TITLE
    assert cam.i == 5                                              # cinco frames, 'q' en el quinto
    assert [n for n, _ in sender.sent] == ["Marker0ToTracker"] * 5


def test_lo_enviado_es_lo_que_da_marker_tracker(fakes, frames_syn, profile_syn) -> None:
    profile = profile_syn()
    rc, _cam, sender, _ = fakes(frames_syn, profile, extra=["--no-window"])
    assert rc == 0 and len(sender.sent) == len(frames_syn)
    cfg = yaml.safe_load(profile.read_text(encoding="utf-8"))
    mt = MarkerTracker(cfg["markers"], cfg["filtering"])
    t = 1000.0 + 0.011 * 2                                         # reloj falso: open, t_start, primer frame
    esperado = []
    for f in frames_syn:
        poses = mt.process(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), t, K_SYN, DIST_SYN)
        esperado.append(poses[0].matrix.astype(np.float32))
        t += 0.011
    for (nombre, M), E in zip(sender.sent, esperado):
        assert nombre == "Marker0ToTracker" and np.array_equal(M, E)


def test_sin_marker_no_envia_y_sin_ventana_no_pinta(fakes, profile_syn) -> None:
    vacios = [np.full((480, 640, 3), 110, np.uint8)] * 3
    rc, cam, sender, est = fakes(vacios, profile_syn(), extra=["--no-window"])
    assert rc == 0 and sender.sent == [] and est["imshow"] == 0 and est["destroy"] == 0
    assert cam.closed and sender.closed


def test_camara_sin_frames_se_da_por_perdida_y_cierra(fakes, profile_syn, capsys) -> None:
    rc, cam, sender, _ = fakes([None] * (tracker.MAX_READ_FAILURES + 5), profile_syn(),
                               extra=["--no-window"], loop=True)
    assert rc == 0 and cam.closed and sender.closed
    out = capsys.readouterr().out
    assert "[ERROR] Camara no entrega frames" in out and "[Salida limpia]" in out


def test_send_video_true_aborta_antes_de_crear_nada(fakes, frames_syn, profile_syn, capsys) -> None:
    rc, cam, sender, _ = fakes(frames_syn, profile_syn(send_video=True), extra=["--no-window"])
    assert rc == 2 and sender is None and not cam.opened
    assert "send_video" in capsys.readouterr().err


def test_config_obligatorio_y_aceleracion_en_el_log(fakes, frames_syn, profile_syn, capsys) -> None:
    with pytest.raises(SystemExit):
        tracker.main([])
    fakes(frames_syn, profile_syn(), extra=["--no-window"])
    out = capsys.readouterr().out
    assert "[Tracker] Aceleracion HW de MSMF" in out
    assert "[Whitelist] IDs aceptados: [0]" in out and "[Salida limpia]" in out


def test_draw_poses_pinta_sobre_el_frame() -> None:
    frame = render_marker(450.0, 0.0)
    cfg = yaml.safe_load(GS1.read_text(encoding="utf-8"))
    mt = MarkerTracker(cfg["markers"], {"enabled": False})
    poses = mt.process(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 0.0, K_SYN, DIST_SYN)
    display = frame.copy()
    tracker.draw_poses(display, poses, K_SYN, DIST_SYN)
    assert len(poses) == 1 and not np.array_equal(display, frame)
    sin = frame.copy()
    tracker.draw_poses(sin, [], K_SYN, DIST_SYN)
    assert np.array_equal(sin, frame)
