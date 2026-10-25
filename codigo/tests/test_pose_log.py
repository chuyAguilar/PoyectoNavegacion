"""Grabacion de la pose del tracker y su replay, sin camara (meta 003, fase 1; fase 4).

`pose_log.PoseLog` y `summarize` sobre datos fijos, y `tracker.main()` de punta
a punta con una camara y un emisor OpenIGTLink falsos (`tests/synthetic.py`):
`--record` guarda exactamente lo que se envio, el replay de Marker0 lo repite
en 0.0 y la deteccion sobre los PNG guardados da las esquinas grabadas. Ninguna
prueba abre una camara real ni un puerto (B34): `create_backend` e `IgtlSender`
se sustituyen en el modulo `tracker`.
"""
from __future__ import annotations

import types
from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.spatial.transform import Rotation

from diagnostics import pose_log
import tracker

from . import replay_util
from .conftest import PROFILES_DIR
from .synthetic import DIST_SYN, K_SYN, FakeCamera, FakeSender, render_marker

N_FRAMES = 12


# ---------------------------------------------------------------------------
# PoseLog y summarize con datos fijos
# ---------------------------------------------------------------------------

def _M(z: float, deg: float = 0.0) -> np.ndarray:
    M = np.eye(4)
    M[:3, :3] = Rotation.from_euler("x", deg, degrees=True).as_matrix()
    M[:3, 3] = [10.0, -5.0, z]
    return M


def test_poselog_round_trip_y_frames(tmp_path: Path) -> None:
    log = pose_log.PoseLog(tmp_path / "g.npz", tmp_path / "frames", 3)
    gray = np.full((8, 8), 7, np.uint8)
    c = np.arange(8, dtype=np.float32).reshape(1, 4, 2)
    for i in range(7):
        ids = np.array([[0], [5]]) if i % 2 == 0 else None
        corners = (c + i, c - i) if ids is not None else ()
        poses = [("Marker0", _M(450.0 + i))] if ids is not None else []
        log.add(100.0 + i * 0.01, ids, corners, poses, gray)
    log.save(K_SYN, DIST_SYN, {"whitelist": [0, 5]})
    rec = pose_log.load_recording(tmp_path / "g.npz")
    assert rec["frame_offsets"].tolist() == [0, 2, 2, 4, 4, 6, 6, 8]
    assert rec["marker_ids"].tolist() == [0, 5] * 4
    assert np.array_equal(rec["corners_2d"][2], (c + 2).reshape(4, 2))
    assert rec["sent_frame"].tolist() == [0, 2, 4, 6]
    assert rec["sent_name"].tolist() == ["Marker0"] * 4
    assert rec["sent_M"][3, 2, 3] == 456.0
    assert rec["frames_saved"].tolist() == [0, 3, 6]
    assert sorted(p.name for p in (tmp_path / "frames").iterdir()) == [
        "frame_00000.png", "frame_00003.png", "frame_00006.png"]
    assert rec["metadata"] == {"whitelist": [0, 5]}
    assert np.array_equal(rec["K"], K_SYN)


def test_poselog_no_pisa(tmp_path: Path) -> None:
    (tmp_path / "g.npz").write_bytes(b"x")
    with pytest.raises(FileExistsError):
        pose_log.PoseLog(tmp_path / "g.npz")
    with pytest.raises(ValueError):
        pose_log.PoseLog(tmp_path / "g.txt")
    (tmp_path / "fr").mkdir()
    (tmp_path / "fr" / "frame_00000.png").write_bytes(b"x")
    with pytest.raises(FileExistsError):
        pose_log.PoseLog(tmp_path / "h.npz", tmp_path / "fr")
    with pytest.raises(ValueError):
        pose_log.PoseLog(tmp_path / "h.npz", None, 0)


def test_summarize_numeros_conocidos(tmp_path: Path) -> None:
    log = pose_log.PoseLog(tmp_path / "g.npz")
    zs = [450.0, 451.0, 450.0, 451.0, 450.0, 451.0, 450.0, 451.0, 450.0, 451.0]
    angs = [0, 0, 0, 0, 0, 10, 0, 0, 0, 0]
    for i, (z, a) in enumerate(zip(zs, angs)):
        poses = [] if i == 8 else [("Marker0", _M(z, a)), ("Dodecaedro", _M(0.0))]
        log.add(i * 0.05, None, (), poses, None)
    log.save(K_SYN, DIST_SYN, {"fps_average": 19.5, "show_window": True})
    s = pose_log.summarize(tmp_path / "g.npz", "Marker0")
    z_ok = np.array([z for i, z in enumerate(zs) if i != 8])
    assert s["frames"] == 10 and s["frames_with_pose"] == 9
    assert s["fraction_with_pose"] == pytest.approx(0.9)
    assert s["fps"] == pytest.approx(9 / 0.45)
    assert s["fps_tracker"] == 19.5
    assert s["sd_z_mm"] == pytest.approx(float(z_ok.std(ddof=1)))
    assert s["sd_x_mm"] == pytest.approx(0.0, abs=1e-12)
    assert s["range_z_mm"] == pytest.approx(1.0)
    assert s["jumps_over_5deg"] == 2           # 0 -> 10 y 10 -> 0
    assert s["max_step_deg"] == pytest.approx(10.0)
    assert s["consecutive_pairs"] == 7         # el frame 8 sin pose corta dos pares
    assert s["sd_orientation_deg"] > 0.0


# ---------------------------------------------------------------------------
# tracker.main() de punta a punta con camara y emisor falsos
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def frames_syn() -> list[np.ndarray]:
    return [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i) for i in range(N_FRAMES)]


@pytest.fixture
def profile_syn(tmp_path: Path) -> Path:
    gs1 = yaml.safe_load((PROFILES_DIR / "tracker_config_gs1.yaml").read_text(encoding="utf-8"))
    cfg = {
        "camera": {"camera_type": "webcam"},
        "markers": gs1["markers"],
        "igtlink": {"transforms_port": 18944, "video_port": 18945, "send_video": False},
        "filtering": gs1["filtering"],
        "debug": {"show_window": True, "verbose": False},
    }
    ruta = tmp_path / "perfil_syn.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return ruta


def _run_main(monkeypatch, frames, profile: Path, extra: list[str]):
    """Corre tracker.main con camara, emisor y reloj falsos; devuelve (camara, emisor)."""
    reloj = iter(np.arange(1000.0, 1000.0 + 10 * (len(frames) + 50), 0.011).tolist())
    cam = FakeCamera(frames)
    FakeSender.instances = []
    monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: cam)
    monkeypatch.setattr(tracker, "IgtlSender", FakeSender)
    monkeypatch.setattr(tracker, "time", types.SimpleNamespace(time=lambda: next(reloj)))

    def _sin_ventana(*a, **k):
        raise AssertionError("con --no-window no se abre ventana")
    monkeypatch.setattr(tracker.cv2, "imshow", _sin_ventana)
    assert tracker.main(["--config", str(profile), "--no-window", *extra]) == 0
    assert len(FakeSender.instances) == 1
    return cam, FakeSender.instances[0]


def test_main_record_guarda_lo_enviado_y_el_replay_lo_repite(
        tmp_path: Path, monkeypatch, frames_syn, profile_syn) -> None:
    rec_path = tmp_path / "out" / "marker0_syn.npz"
    frames_dir = tmp_path / "out" / "frames"
    cam, srv = _run_main(monkeypatch, frames_syn, profile_syn,
                         ["--record", str(rec_path), "--save-frames", str(frames_dir),
                          "--frames-every", "4"])
    assert cam.opened and cam.closed and srv.closed
    enviados = [m for (n, m) in srv.sent if n == "Marker0ToTracker"]
    assert len(enviados) == N_FRAMES, "el marker sintetico tiene que verse en todos los frames"

    rec = pose_log.load_recording(rec_path)
    assert len(rec["timestamps"]) == N_FRAMES
    assert rec["sent_name"].tolist() == ["Marker0"] * N_FRAMES
    assert rec["sent_frame"].tolist() == list(range(N_FRAMES))
    for M_rec, M_srv in zip(rec["sent_M"], enviados):
        assert np.array_equal(M_rec.astype(np.float32), M_srv)
    assert rec["frames_saved"].tolist() == [0, 4, 8]
    meta = rec["metadata"]
    assert meta["show_window"] is False and meta["whitelist"] == [0] and meta["frames"] == N_FRAMES

    replay = replay_util.run_marker0_replay(rec_path, profile_syn)
    c = replay_util.compare_marker0(replay, replay_util.recorded_marker0(rec_path))
    assert c["sends"] == N_FRAMES and c["frames_differ"] == 0
    assert c["max_diff_translation_mm"] == 0.0 and c["max_diff_rotation_deg"] == 0.0

    d = replay_util.compare_detection(rec_path, frames_dir, profile_syn)
    assert d["frames"] == 3 and d["frames_ids_differ"] == 0 and d["detections"] == 3
    assert d["max_diff_px"] == 0.0

    s = pose_log.summarize(rec_path, "Marker0")
    assert s["fraction_with_pose"] == 1.0
    assert 445.0 < s["mean_z_mm"] < 455.0


def test_main_sin_opciones_envia_lo_mismo(tmp_path: Path, monkeypatch, frames_syn,
                                          profile_syn) -> None:
    """Las opciones de grabacion no cambian lo que se envia: mismo reloj, mismos frames."""
    _, srv_a = _run_main(monkeypatch, frames_syn, profile_syn, [])
    _, srv_b = _run_main(monkeypatch, frames_syn, profile_syn,
                         ["--record", str(tmp_path / "g.npz")])
    assert [n for n, _ in srv_a.sent] == [n for n, _ in srv_b.sent]
    for (_, a), (_, b) in zip(srv_a.sent, srv_b.sent):
        assert np.array_equal(a, b)


def test_main_record_no_pisa_y_no_abre_la_camara(tmp_path: Path, monkeypatch,
                                                  profile_syn) -> None:
    (tmp_path / "g.npz").write_bytes(b"x")

    def _prohibido(cfg_cam):
        raise AssertionError("no tenia que llegar a crear la camara")
    monkeypatch.setattr(tracker, "create_backend", _prohibido)
    with pytest.raises(FileExistsError):
        tracker.main(["--config", str(profile_syn), "--record", str(tmp_path / "g.npz")])


def test_main_save_frames_sin_record_falla(profile_syn) -> None:
    with pytest.raises(SystemExit):
        tracker.main(["--config", str(profile_syn), "--save-frames", "x"])


def test_main_duration_sale_limpio(tmp_path: Path, monkeypatch, frames_syn, profile_syn) -> None:
    """--duration corta el bucle por tiempo (reloj falso a 11 ms por llamada)."""
    cam, srv = _run_main(monkeypatch, frames_syn * 20, profile_syn,
                         ["--duration", "0.5", "--record", str(tmp_path / "g.npz")])
    assert cam.closed and srv.closed
    assert cam.i < len(frames_syn) * 20
    rec = pose_log.load_recording(tmp_path / "g.npz")
    assert rec["timestamps"][-1] - rec["metadata"]["t_start"] >= 0.5
