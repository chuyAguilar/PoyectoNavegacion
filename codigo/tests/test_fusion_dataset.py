"""fusion.dataset (meta 006, fase 1): `ippe_solutions` da dos soluciones y la primera es la de
`solvePnP` (la del tracker); `build_track` rehace la pose cruda desde las esquinas de un `.npz`
de `PoseLog` (sintetico y el recorte real) con la rotacion igual a la enviada; `check_segment`
pasa con una grabacion buena y dice por que no con una mala; `cut_segment` recorta sin frames
y `expected_duration` lee el `--duration` o el recorte; `segment_file` elige el ultimo intento.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from diagnostics.pose_log import PoseLog, load_recording
from fusion import dataset as ds
from fusion import geometry as g
from vision.pose import estimate_single_pose

from .conftest import DATA_DIR, TESTS_DATA_DIR
from .test_fusion_geometry import DIST, K, SIZE, marker_pose, second_camera

RECORTE = TESTS_DATA_DIR / "fusion_gs1_gs2"
INTRINSICS = {"gs1": DATA_DIR / "intrinsecos_gs1_1280x960.yml", "gs2": DATA_DIR / "intrinsecos_gs2_1280x960.yml"}


def _meta(camera: str, t_start: float, t_loop_start: float, duration: float, calib_sha: str = "") -> dict:
    return {"argv": ["tracker.py", "--config", f"profiles/tracker_config_{camera}.yaml", "--duration", str(duration)],
            "markers": [{"id": 0, "name": "Marker0", "size_mm": SIZE}], "t_start": t_start, "t_loop_start": t_loop_start,
            "calibration_sha256": calib_sha, "filtering": {"enabled": False}}


def write_fake_npz(path: Path, camera: str, t: np.ndarray, Ts: np.ndarray, K=K, dist=DIST, t_start: float = 1.7e9,
                   t_loop_start: float = 1000.0, duration: float = 10.0, calib_sha: str = "", hide=None) -> Path:
    """Un `.npz` de `PoseLog` con las esquinas proyectadas de `Ts` (NaN en `hide` = sin deteccion)
    y la pose enviada sin filtro."""
    log = PoseLog(path)
    for i, (ti, T) in enumerate(zip(t, Ts)):
        if hide is not None and hide[i]:
            log.add(ti, None, (), [], None)
            continue
        c = g.project_corners(T, SIZE, K, dist).astype(np.float32)
        pose = estimate_single_pose(c, SIZE, K, dist)
        poses = []
        if pose is not None:
            poses = [("Marker0", g.exp_se3(np.zeros(6)) @ np.eye(4))]
            M = np.eye(4)
            M[:3, :3], _ = cv2.Rodrigues(pose[0])
            M[:3, 3] = pose[1].ravel()
            poses = [("Marker0", M)]
        log.add(ti, np.array([[0]]), (c.reshape(1, 4, 2),), poses, None)
    return log.save(K, dist, _meta(camera, t_start, t_loop_start, duration, calib_sha))


@pytest.fixture
def fake_segment(tmp_path: Path) -> tuple[Path, np.ndarray]:
    T12 = second_camera(30.0)
    t1 = 1000.0 + np.arange(0, 10, 1 / 63.0)
    t2 = 1000.0 + 0.004 + np.arange(0, 10, 1 / 66.0)
    X = marker_pose()
    write_fake_npz(tmp_path / "S1_reposo_gs1.npz", "gs1", t1, np.tile(X, (len(t1), 1, 1)))
    write_fake_npz(tmp_path / "S1_reposo_gs2.npz", "gs2", t2, np.tile(g.inv(T12) @ X, (len(t2), 1, 1)))
    return tmp_path, T12


def test_ippe_solutions_dos_y_la_primera_es_la_del_tracker() -> None:
    rng = np.random.default_rng(5)
    T = marker_pose()
    z = g.project_corners(T, SIZE, K, DIST) + rng.normal(0, 0.1, (4, 2))
    sols = ds.ippe_solutions(z, SIZE, K, DIST)
    assert len(sols) == 2 and sols[0][1] < sols[1][1]
    rvec, tvec = estimate_single_pose(z, SIZE, K, DIST)
    assert np.allclose(sols[0][0][:3, 3], tvec.ravel()) and np.allclose(cv2.Rodrigues(rvec)[0], sols[0][0][:3, :3])
    assert g.pose_difference(sols[0][0], T)[0] < 0.5


def test_build_track_y_check_segment_con_un_segmento_bueno(fake_segment) -> None:
    folder, T12 = fake_segment
    tracks = ds.load_segment(folder, "S1_reposo")
    a, b = tracks["gs1"], tracks["gs2"]
    assert a.valid.all() and b.valid.all() and a.T_raw.shape == (len(a.t), 4, 4)
    assert np.allclose(a.T_sent[0], a.T_raw[0]) and np.isfinite(a.corners).all()
    assert a.period_s == pytest.approx(1 / 63.0, rel=1e-6) and a.span_s == pytest.approx(10 - 1 / 63.0, abs=1e-6)
    assert g.pose_difference(T12 @ b.T_raw[0], a.T_raw[0])[0] < 1e-3
    assert ds.expected_duration(a.meta) == 10.0
    # El sha256 "grabado" no es el de data/: la comprobacion lo dice; con el sha bien, pasa.
    ch = ds.check_segment(tracks, INTRINSICS, 10.0)
    assert not ch["ok"] and any("calibracion" in r for r in ch["reasons"])
    assert ch["anchor_diff_ms"] == pytest.approx(0.0, abs=1e-6) and ch["overlap_s"] > 9.9
    assert ch["fraction_with_pose"] == {"gs1": 1.0, "gs2": 1.0}
    assert ch["rotation_max_diff_deg"]["gs1"] <= 1e-9 and ch["frames_differ"] == {"gs1": 0, "gs2": 0}
    for c in ("gs1", "gs2"):
        tracks[c].meta["calibration_sha256"] = ds.sha256_file(INTRINSICS[c])
    ch = ds.check_segment(tracks, INTRINSICS, 10.0)
    assert ch["ok"] and ch["reasons"] == []


def test_check_segment_dice_por_que_no(fake_segment) -> None:
    folder, _ = fake_segment
    tracks = ds.load_segment(folder, "S1_reposo")
    for c in ("gs1", "gs2"):
        tracks[c].meta["calibration_sha256"] = ds.sha256_file(INTRINSICS[c])
    tracks["gs2"].meta["t_start"] += 0.005                     # 5 ms de ancla
    ch = ds.check_segment(tracks, INTRINSICS, 10.0)
    assert not ch["ok"] and any("ancla" in r for r in ch["reasons"]) and ch["anchor_diff_ms"] == pytest.approx(5.0, abs=0.01)
    tracks["gs2"].meta["t_start"] -= 0.005
    assert any("solape" in r for r in ds.check_segment(tracks, INTRINSICS, 25.0)["reasons"])
    n = len(tracks["gs1"].t)
    tracks["gs1"].T_raw[: n // 2] = np.nan                       # la mitad sin pose
    ch = ds.check_segment(tracks, INTRINSICS, 10.0)
    assert any("con pose en 50" in r for r in ch["reasons"]) and any("frames con pose en un lado" in r for r in ch["reasons"])
    tracks["gs1"].T_sent[: n // 2] = np.nan
    ch = ds.check_segment(tracks, INTRINSICS, 10.0, occluded="gs1")
    assert ch["fraction_with_pose"]["gs1"] == pytest.approx(0.5) and any("tapada" in r for r in ch["reasons"])
    tracks["gs1"].T_raw[: n // 4] = tracks["gs1"].T_sent[: n // 4] = tracks["gs1"].T_raw[-1]
    assert ds.check_segment(tracks, INTRINSICS, 10.0, occluded="gs1")["ok"]
    del tracks["gs1"].meta["t_start"]
    assert any("t_start" in r for r in ds.check_segment(tracks, INTRINSICS, 10.0, occluded="gs1")["reasons"])


def test_build_track_cuenta_lo_excluido_y_la_otra_solucion(tmp_path: Path) -> None:
    t = 1000.0 + np.arange(0, 2, 1 / 63.0)
    X = marker_pose()
    hide = np.zeros(len(t), bool)
    hide[10:20] = True
    p = write_fake_npz(tmp_path / "S3_tapa_gs1_gs1.npz", "gs1", t, np.tile(X, (len(t), 1, 1)), hide=hide)
    tr = ds.build_track(load_recording(p), "gs1", file=p.name)
    assert tr.excluded["sin_deteccion"] == 10 and (~tr.detected).sum() == 10 and (~tr.valid).sum() == 10
    assert np.isfinite(tr.T_alt[0, 3, 3]) and tr.reproj_alt_px[0] > tr.reproj_px[0]
    assert tr.file == "S3_tapa_gs1_gs1.npz"
    with pytest.raises(ValueError, match="no tiene un marker"):
        ds.build_track(load_recording(p), "gs1", name="Dodecaedro")


def test_segment_file_elige_el_ultimo_intento(tmp_path: Path) -> None:
    for n in ("S2_pos3_gs1.npz", "S2_pos3_gs1_r2.npz", "S2_pos3_gs1_r3.npz", "S2_pos3_gs2.npz"):
        (tmp_path / n).write_bytes(b"x")
    assert ds.segment_file(tmp_path, "S2_pos3", "gs1").name == "S2_pos3_gs1_r3.npz"
    assert ds.segment_file(tmp_path, "S2_pos3", "gs1", "r2").name == "S2_pos3_gs1_r2.npz"
    assert ds.segment_file(tmp_path, "S2_pos3", "gs2").name == "S2_pos3_gs2.npz"
    with pytest.raises(FileNotFoundError):
        ds.segment_file(tmp_path, "S2_pos3", "gs2", "r2")
    with pytest.raises(FileNotFoundError):
        ds.segment_file(tmp_path, "S2_pos4", "gs1")
    with pytest.raises(FileNotFoundError):
        ds.load_segment(tmp_path, "S2_pos4")


def test_expected_duration() -> None:
    assert ds.expected_duration({"argv": ["x", "--duration", "65"]}) == 65.0
    assert ds.expected_duration({"argv": ["x", "--duration=40"]}) == 40.0
    assert ds.expected_duration({"argv": ["x", "--duration", "no"]}) is None
    assert ds.expected_duration({"argv": ["x"]}) is None and ds.expected_duration({}) is None
    assert ds.expected_duration({"argv": ["x", "--duration", "65"], "recorte": {"duration_s": 8}}) == 8.0


def test_cut_segment_recorta_sin_frames_y_no_pisa(fake_segment, tmp_path: Path) -> None:
    folder, _ = fake_segment
    out = tmp_path / "recorte"
    salidas = ds.cut_segment(folder, "S1_reposo", out, 2.0, 5.0)
    assert [p.name for p in salidas] == ["S1_reposo_gs1.npz", "S1_reposo_gs2.npz"]
    rec = load_recording(salidas[0])
    assert 185 <= len(rec["timestamps"]) <= 191 and len(rec["frames_saved"]) == 0
    assert rec["metadata"]["recorte"]["duration_s"] == 3.0 and ds.expected_duration(rec["metadata"]) == 3.0
    assert rec["timestamps"][0] >= 1000.0 + 0.004 + 2.0 - 1e-9
    tr = ds.build_track(rec, "gs1")
    assert tr.valid.all() and np.allclose(tr.T_sent[0], tr.T_raw[0])
    with pytest.raises(FileExistsError):
        ds.cut_segment(folder, "S1_reposo", out, 2.0, 5.0)
    with pytest.raises(ValueError):
        ds.cut_segment(folder, "S1_reposo", tmp_path / "otro", 5.0, 2.0)
    rc = ds.main(["recortar", "--datos", str(folder), "--segmento", "S1_reposo", "--desde-s", "0", "--hasta-s", "1",
                  "--salida", str(tmp_path / "cli")])
    assert rc == 0 and (tmp_path / "cli" / "S1_reposo_gs2.npz").is_file()
    assert ds.main(["recortar", "--datos", str(folder), "--segmento", "S9", "--desde-s", "0", "--hasta-s", "1",
                    "--salida", str(tmp_path / "cli2")]) == 1


def test_el_recorte_real_carga_y_pasa_la_comprobacion() -> None:
    """`tests/data/fusion_gs1_gs2/`: 8 s de S1_reposo y 3 s de cada posicion de S2 de la
    grabacion del 2026-11-05 en la Jetson, sin frames (< 1 MB)."""
    assert RECORTE.is_dir(), "falta el recorte real de la meta 006"
    total = sum(p.stat().st_size for p in RECORTE.glob("*.npz"))
    assert 0 < total < 1_000_000, total
    tracks = ds.load_segment(RECORTE, "S1_reposo")
    ch = ds.check_segment(tracks, INTRINSICS, ds.expected_duration(tracks["gs1"].meta))
    assert ch["ok"], ch["reasons"]
    assert ch["anchor_diff_ms"] < 0.05 and ch["rotation_max_diff_deg"]["gs1"] < 1e-4      # ARM (Jetson) frente a x86: ~3e-6
    assert tracks["gs1"].meta["recorte"]["source"] == "S1_reposo_gs1.npz"
    assert tracks["gs1"].valid.mean() > 0.95 and tracks["gs2"].valid.mean() > 0.95
    assert tracks["gs1"].size_mm == 80.0 and tracks["gs1"].K.shape == (3, 3)
    ref = json.loads((RECORTE / "referencia.json").read_text(encoding="utf-8"))
    assert ref["segmentos"]["S1_reposo"]["frames"] == {c: int(len(tracks[c].t)) for c in ("gs1", "gs2")}
