"""fusion.bundle (meta 006, fase 1): el ajuste conjunto de los extrinsecos y las poses de cada
posicion recupera la verdad sin ruido (< 1e-6 mm y grados) desde una inicializacion
desviada, con ruido deja un RMS del orden del ruido, y el multiarranque sobre la ambiguedad
de IPPE encuentra el mismo minimo.
"""
from __future__ import annotations

import numpy as np
import pytest

from fusion import bundle as bd
from fusion import geometry as g
from fusion.dataset import ippe_solutions

from .test_fusion_extrinsics import POSITIONS
from .test_fusion_geometry import DIST, K, SIZE, marker_pose, second_camera

KD = {"gs1": K, "gs2": K}
DD = {"gs1": DIST, "gs2": DIST}
SIG = {"gs1": 0.1, "gs2": 0.1}


def _scene(noise_px: float = 0.0, seed: int = 2):
    rng = np.random.default_rng(seed)
    T12 = second_camera(30.0)
    Xs = [marker_pose(**p) for p in POSITIONS]
    obs = [{"gs1": g.project_corners(X, SIZE, K, DIST) + rng.normal(0, noise_px, (4, 2)),
            "gs2": g.project_corners(g.inv(T12) @ X, SIZE, K, DIST) + rng.normal(0, noise_px, (4, 2))} for X in Xs]
    return T12, Xs, obs


def test_sin_ruido_recupera_los_extrinsecos() -> None:
    T12, Xs, obs = _scene()
    T0 = T12 @ g.exp_se3([0.02, -0.03, 0.01, 5.0, -3.0, 8.0])
    X0 = [X @ g.exp_se3([0.01, 0.01, -0.01, 1.0, 1.0, -2.0]) for X in Xs]
    f = bd.fit_extrinsics_bundle(obs, SIZE, KD, DD, SIG, T0, X0)
    dmm, ddeg = g.pose_difference(f["T_ref_other"], T12)
    assert dmm < 1e-6 and ddeg < 1e-6 and f["rms_px"] < 1e-6, (dmm, ddeg, f["rms_px"])
    assert f["iteraciones"] <= 15 and f["n_positions"] == 5 and f["angle_deg"] == pytest.approx(30.0, abs=1e-6)
    assert all(g.pose_difference(a, b)[0] < 1e-6 for a, b in zip(f["poses"], Xs))
    assert f["cov_T12"].shape == (6, 6) and np.all(np.diag(f["cov_T12"]) > 0)
    assert len(f["rms_por_posicion"]) == 5 and set(f["rms_por_posicion"][0]) == {"gs1", "gs2"}


def test_con_ruido_el_rms_es_del_orden_del_ruido() -> None:
    T12, Xs, obs = _scene(noise_px=0.1)
    f = bd.fit_extrinsics_bundle(obs, SIZE, KD, DD, SIG, T12, Xs)
    assert 0.03 < f["rms_px"] < 0.15
    dmm, ddeg = g.pose_difference(f["T_ref_other"], T12)
    assert dmm < 1.0 and ddeg < 0.2
    sd = np.sqrt(np.diag(f["cov_T12"]))
    assert dmm < 4 * np.linalg.norm(sd[3:]) + 0.05


def test_multiarranque_sobre_la_ambiguedad_de_ippe() -> None:
    T12, Xs, obs = _scene(noise_px=0.05)
    Xi = [[T for T, _e in ippe_solutions(o["gs1"], SIZE, K, DIST) if T[2, 3] > 0] for o in obs]
    assert all(len(x) == 2 for x in Xi)
    f = bd.fit_extrinsics_bundle_multistart(obs, SIZE, KD, DD, SIG, T12 @ g.exp_se3([0.01, 0, 0, 2.0, 0, 0]), Xi)
    assert f["combinaciones"] == 32 and len(f["coste_por_combinacion"]) == 32
    assert g.pose_difference(f["T_ref_other"], T12)[0] < 0.5 and f["rms_px"] < 0.1
    assert f["cost"] == min(f["coste_por_combinacion"])
    with pytest.raises(ValueError, match="combinaciones"):
        bd.fit_extrinsics_bundle_multistart(obs, SIZE, KD, DD, SIG, T12, Xi, max_combinations=8)
    with pytest.raises(ValueError):
        bd.fit_extrinsics_bundle([], SIZE, KD, DD, SIG, T12, [])
    c = np.full((3, 4, 2), np.nan)
    c[1] = obs[0]["gs1"]
    assert np.allclose(bd.mean_corners(c), obs[0]["gs1"])
    with pytest.raises(ValueError):
        bd.mean_corners(np.full((2, 4, 2), np.nan))
