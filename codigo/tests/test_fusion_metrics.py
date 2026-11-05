"""fusion.metrics (meta 006, fase 1): la sd 3D no depende del giro de los ejes y el quitar
la media movil deja fuera una deriva; `predicted_reduction` da 29 % con dos camaras
paralelas e iguales y mas con angulo; los tramos tapados se encuentran y los saltos se
miden donde se pusieron; `agreement` y `measured_reduction` sobre casos conocidos.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from fusion import geometry as g
from fusion import metrics as mt
from fusion.dataset import CameraTrack

from .test_fusion_geometry import DIST, K, SIZE, marker_pose, second_camera

FS = 63.0


def _rng() -> np.random.Generator:
    return np.random.default_rng(3)


def test_rest_sd_invariante_al_giro_y_sin_deriva() -> None:
    rng = _rng()
    n = 3000
    t = np.arange(n) / FS
    p = rng.normal(0, [0.01, 0.01, 0.045], (n, 3)) + [20, 5, 380]
    r = mt.rest_sd(p, t)
    assert r["sd_3d_mm"] == pytest.approx(np.sqrt(0.01 ** 2 * 2 + 0.045 ** 2), rel=0.05)
    R = Rotation.from_euler("y", 37, degrees=True).as_matrix()
    assert mt.rest_sd(p @ R.T, t)["sd_3d_mm"] == pytest.approx(r["sd_3d_mm"], rel=1e-9)
    assert r["sd_axes_mm"][2] == pytest.approx(0.045, rel=0.05) and r["n"] == n
    deriva = p.copy()
    deriva[:, 2] += 0.004 * t                                   # 4 um/s, como gs1 en la Jetson (B77)
    d = mt.rest_sd(deriva, t)
    assert d["sd_3d_mm"] > r["sd_3d_mm"] * 1.3
    assert d["sd_3d_detrended_mm"] == pytest.approx(r["sd_3d_detrended_mm"], rel=0.05)
    assert d["sd_3d_detrended_mm"] < d["sd_3d_mm"]
    con_nan = p.copy()
    con_nan[::7] = np.nan
    assert mt.rest_sd(con_nan, t)["n"] == n - len(range(0, n, 7))
    assert np.isnan(mt.rest_sd(np.full((2, 3), np.nan), t[:2])["sd_3d_mm"])


def test_predicted_reduction_paralelas_y_con_angulo() -> None:
    A = np.diag([0.01, 0.01, 0.045]) ** 2
    par = mt.predicted_reduction(A, A)
    assert par["reduction_3d"] == pytest.approx(1 - 1 / np.sqrt(2), abs=1e-9)         # 29.3 %
    assert par["best"] == "a" and par["sd_3d_fused_mm"] == pytest.approx(par["sd_3d_a_mm"] / np.sqrt(2))
    R = Rotation.from_euler("y", 60, degrees=True).as_matrix()
    ang = mt.predicted_reduction(A, R @ A @ R.T)
    assert ang["reduction_3d"] > 0.55 and ang["reduction_axes"][2] > ang["reduction_axes"][1]
    peor = mt.predicted_reduction(A, 1.5 * A)
    assert 0.2 < peor["reduction_3d"] < par["reduction_3d"]
    m = mt.measured_reduction({"gs1": 0.046, "gs2": 0.043}, 0.030)
    assert m["best"] == "gs2" and m["reduction"] == pytest.approx(1 - 0.030 / 0.043)


def _track_with_gap(name: str, gap: tuple[float, float], seconds: float = 30.0, fs: float = FS) -> CameraTrack:
    t = np.arange(0, seconds, 1 / fs)
    n = len(t)
    T = np.tile(marker_pose(), (n, 1, 1))
    corners = np.tile(g.project_corners(marker_pose(), SIZE, K, DIST), (n, 1, 1))
    tapado = (t >= gap[0]) & (t < gap[1])
    T[tapado] = np.nan
    corners[tapado] = np.nan
    return CameraTrack(name=name, t=t, T_raw=T, T_alt=np.full((n, 4, 4), np.nan), corners=corners,
                       reproj_px=np.zeros(n), reproj_alt_px=np.full(n, np.nan), T_sent=np.full((n, 4, 4), np.nan),
                       K=K, dist=DIST, size_mm=SIZE)


def test_occlusion_events_y_jumps() -> None:
    tr = _track_with_gap("gs1", (10.0, 15.0))
    ev = mt.occlusion_events(tr)
    assert len(ev) == 1 and ev[0][0] == pytest.approx(10.0, abs=1 / FS) and ev[0][1] == pytest.approx(15.0, abs=1 / FS)
    assert mt.occlusion_events(_track_with_gap("gs1", (10.0, 10.3))) == []
    assert mt.occlusion_events(_track_with_gap("gs1", (10.0, 10.3)), min_gap_s=0.2) != []
    # Una linea fusionada que salta 0.3 mm al tapar y vuelve al destapar, con ruido pequeno.
    rng = _rng()
    t = tr.t
    p = np.tile([20.0, 5.0, 380.0], (len(t), 1)) + rng.normal(0, 0.005, (len(t), 3))
    dentro = (t > ev[0][0]) & (t <= ev[0][1])
    p[dentro, 2] += 0.3
    j = mt.jumps(t, p, ev)
    assert len(j["transitions"]) == 2 and j["fraction_with_pose"] == 1.0
    tapar, destapar = j["transitions"]
    assert tapar["kind"] == "tapar" and destapar["kind"] == "destapar"
    assert tapar["jump_mm"] == pytest.approx(0.3, abs=0.01) and destapar["jump_mm"] == pytest.approx(0.3, abs=0.01)
    assert j["max_jump_mm"] == pytest.approx(0.3, abs=0.01)
    assert 0.3 <= j["max_step_mm"] < 0.35
    assert tapar["n_before"] == pytest.approx(0.25 * FS, abs=2) and tapar["n_after"] == pytest.approx(0.25 * FS, abs=2)
    p[dentro] = np.nan
    j2 = mt.jumps(t, p, ev)
    assert j2["fraction_with_pose"] < 1.0 and np.isnan(j2["transitions"][0]["jump_mm"])
    assert np.isnan(mt.jumps(t, p, [])["max_jump_mm"])


def test_agreement_sobre_parejas_conocidas() -> None:
    T12 = second_camera(30.0)
    n = 50
    T1 = np.tile(marker_pose(), (n, 1, 1))
    T2 = np.array([g.inv(T12) @ marker_pose(x=20.0 + 0.2) for _ in range(n)])     # gs2 ve el marker 0.2 mm corrido
    tracks = {"gs1": _track_with_gap("gs1", (0, 0)), "gs2": _track_with_gap("gs2", (0, 0))}
    tracks["gs1"].T_raw[:n] = T1
    tracks["gs2"].T_raw[:n] = T2
    pairs = np.column_stack([np.arange(n), np.arange(n)])
    a = mt.agreement(tracks, T12, pairs)
    assert a["n"] == n and a["mean_mm"] == pytest.approx(0.2, abs=1e-9) and a["mean_deg"] < 1e-9
    assert a["mean_dxyz_mm"] == pytest.approx([-0.2, 0.0, 0.0], abs=1e-9)
    assert mt.agreement(tracks, T12, np.zeros((0, 2), int)) == {"n": 0}
