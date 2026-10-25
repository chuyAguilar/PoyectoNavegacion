"""El bucle de `tracker.main()` con una camara y un emisor falsos (meta 003, fases 4 y 7).

Sale con `q` y cierra todo (camara, hilo de captura, emisor, ventana); `--config`
es obligatorio; `send_video: true` aborta antes de crear nada (P7); sin Slicer en
el tope aborta con codigo 3 sin abrir la camara (fase 7); sin frames la camara
se da por perdida y se cierra limpio; lo que se envia es lo que `MarkerTracker`
da con los tiempos de captura (`perf_counter`, fase 7); y `draw_poses` pinta
sobre el frame. Ninguna prueba abre una camara ni un puerto (B34, fixture de
conftest).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from diagnostics import pose_log
import tracker
from vision.tracking import MarkerTracker

from .conftest import PROFILES_DIR
from .synthetic import DIST_SYN, K_SYN, FakeCamera, FakeSender, fake_time, render_marker

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

    def run(frames, profile, extra=(), keys=None, loop=False, delay_s=None, connected=True):
        cam = FakeCamera(frames, loop=loop, **({"delay_s": delay_s} if delay_s is not None else {}))
        FakeSender.instances = []
        FakeSender.connected = connected
        monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: cam)
        monkeypatch.setattr(tracker, "IgtlSender", FakeSender)
        monkeypatch.setattr(tracker, "time", fake_time())
        teclas = iter(keys or [])

        def imshow(title, img):
            estado["imshow"] += 1
            estado["title"] = title
            assert img.shape[2] == 3
        monkeypatch.setattr(tracker.cv2, "imshow", imshow)
        monkeypatch.setattr(tracker.cv2, "waitKey", lambda ms: next(teclas, -1))
        monkeypatch.setattr(tracker.cv2, "destroyAllWindows",
                            lambda: estado.__setitem__("destroy", estado["destroy"] + 1))
        try:
            rc = tracker.main(["--config", str(profile), *extra])
        finally:
            FakeSender.connected = True
        return rc, cam, (FakeSender.instances[0] if FakeSender.instances else None), estado
    return run


@pytest.fixture(scope="module")
def frames_syn() -> list[np.ndarray]:
    return [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i) for i in range(8)]


def test_sale_con_q_y_cierra_todo(fakes, frames_syn, profile_syn) -> None:
    rc, cam, sender, est = fakes(frames_syn, profile_syn(), keys=[-1, -1, -1, -1, ord("q")], loop=True)
    assert rc == 0
    assert cam.opened and cam.closed and sender.closed
    assert sender.port == 18944 and sender.waited == [tracker.DEFAULT_SLICER_TIMEOUT_S]
    assert est["imshow"] == 5 and est["destroy"] == 1 and est["title"] == tracker.WINDOW_TITLE
    assert [n for n, _ in sender.sent] == ["Marker0ToTracker"] * 5       # cinco frames, 'q' en el quinto
    assert 5 <= cam.i <= 6                                               # el hilo pudo leer uno mas


def test_lo_enviado_es_lo_que_da_marker_tracker(fakes, frames_syn, profile_syn, tmp_path) -> None:
    """Las matrices enviadas son las de `MarkerTracker` sobre cada frame con el tiempo de
    captura (`perf_counter` del hilo, grabado en `timestamps`): el hilo entrega todos los
    frames de la camara falsa, en orden, y el 1-Euro corre con esos tiempos."""
    profile = profile_syn()
    rec_path = tmp_path / "g.npz"
    rc, _cam, sender, _ = fakes(frames_syn, profile, extra=["--no-window", "--record", str(rec_path)])
    assert rc == 0 and len(sender.sent) == len(frames_syn)
    rec = pose_log.load_recording(rec_path)
    ts = rec["timestamps"]
    assert len(ts) == len(frames_syn) and np.all(np.diff(ts) > 0)
    assert np.allclose(np.diff(ts), 0.011)             # un paso del reloj falso por frame leido
    assert ts[0] >= 1000.0 + 3 * 0.011                 # antes: la espera a Slicer (2) y t_start (1)
    cfg = yaml.safe_load(profile.read_text(encoding="utf-8"))
    mt = MarkerTracker(cfg["markers"], cfg["filtering"])
    for f, t, (nombre, M) in zip(frames_syn, ts, sender.sent):
        poses = mt.process(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), float(t), K_SYN, DIST_SYN)
        assert nombre == "Marker0ToTracker" and np.array_equal(M, poses[0].matrix.astype(np.float32))
    assert rec["metadata"]["clock"] == "time.perf_counter"
    assert rec["metadata"]["capture"]["frames_read"] >= len(frames_syn)


def test_sync_capture_envia_lo_mismo_sin_hilo(fakes, frames_syn, profile_syn, tmp_path) -> None:
    """--sync-capture (la captura en el bucle, como hasta la fase 6) procesa los mismos frames
    y manda las mismas matrices que el hilo cuando el bucle alcanza a la camara."""
    profile = profile_syn()
    rc_a, _c, s_a, _ = fakes(frames_syn, profile, extra=["--no-window"])
    rc_b, cam, s_b, _ = fakes(frames_syn, profile, extra=["--no-window", "--sync-capture",
                                                          "--record", str(tmp_path / "s.npz")],
                              delay_s=0.0)
    assert rc_a == rc_b == 0 and len(s_a.sent) == len(s_b.sent) == len(frames_syn)
    for (na, Ma), (nb, Mb) in zip(s_a.sent, s_b.sent):
        assert na == nb and np.array_equal(Ma, Mb)
    assert cam.closed and cam.i == len(frames_syn)
    meta = pose_log.load_recording(tmp_path / "s.npz")["metadata"]
    assert meta["capture"]["mode"] == "sync" and meta["capture"]["frames_skipped"] == 0


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
    assert "[WARN] cam.read() retornando None (1 consecutivos)" in out
    assert "[ERROR] Camara no entrega frames" in out and "[Salida limpia]" in out


def test_sin_slicer_aborta_sin_abrir_la_camara(fakes, frames_syn, profile_syn, capsys) -> None:
    rc, cam, sender, est = fakes(frames_syn, profile_syn(), extra=["--slicer-timeout", "0.5"],
                                 connected=False)
    assert rc == tracker.EXIT_NO_SLICER and sender.waited == [0.5]
    assert not cam.opened and cam.closed and sender.closed and sender.sent == []
    assert est["imshow"] == 0
    cap = capsys.readouterr()
    assert "Slicer no se conecto al puerto 18944 en 0 s" in cap.err or \
        "Slicer no se conecto al puerto 18944" in cap.err
    assert "[Salida limpia]" in cap.out
    with pytest.raises(SystemExit):
        tracker.main(["--config", str(profile_syn()), "--slicer-timeout", "0"])


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
    assert "[OpenIGTLink] Cliente conectado" in out and "[Captura] Camara" in out


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
