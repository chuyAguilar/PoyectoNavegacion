"""fusion.extrinsics (meta 006, fase 1): con dos camaras sinteticas sin ruido, los
extrinsecos por Marker0 en 5 posiciones se recuperan a < 0.01 mm y < 0.001 grados; la
validacion cruzada da coincidencia ~0; el `.yml` se escribe, se lee, no se pisa y aborta si
cambia el sha256 de un intrinseco.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fusion import extrinsics as ex
from fusion import geometry as g
from fusion.dataset import ippe_solutions

from .test_fusion_geometry import DIST, K, SIZE, marker_pose, second_camera

POSITIONS = [dict(x=20, y=5, z=380), dict(x=-60, y=5, z=380), dict(x=100, y=5, z=380),
             dict(x=20, y=-70, z=370, euler=(185 + 30, 8)), dict(x=20, y=80, z=390, euler=(185, 8 + 30))]


def _pairs(T12: np.ndarray, n: int = 30, noise_px: float = 0.0, seed: int = 1) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    out = []
    for pos in POSITIONS:
        T1 = marker_pose(**pos)
        T2 = g.inv(T12) @ T1
        z1, z2 = g.project_corners(T1, SIZE, K, DIST), g.project_corners(T2, SIZE, K, DIST)
        Ta = np.array([ippe_solutions(z1 + rng.normal(0, noise_px, (4, 2)), SIZE, K, DIST)[0][0] for _ in range(n)])
        Tb = np.array([ippe_solutions(z2 + rng.normal(0, noise_px, (4, 2)), SIZE, K, DIST)[0][0] for _ in range(n)])
        out.append((Ta, Tb))
    return out


def test_extrinsecos_sin_ruido_se_recuperan() -> None:
    T12 = second_camera(30.0)
    E = ex.from_marker_positions(_pairs(T12))
    dmm, ddeg = g.pose_difference(E["T_ref_other"], T12)
    assert dmm < 0.01 and ddeg < 0.001, (dmm, ddeg)
    assert E["n_positions"] == 5 and E["pairs_per_position"] == [30] * 5
    assert E["spread_mm"] < 0.01 and E["spread_deg"] < 0.001
    assert E["angle_deg"] == pytest.approx(30.0, abs=1e-3)       # IPPE sobre datos exactos: ~1e-5 grados
    assert ex.optical_axis_angle_deg(np.eye(4)) == 0.0
    loo = ex.leave_one_out(_pairs(T12))
    assert len(loo) == 5 and all(r["agreement"]["mean_mm"] < 0.01 and r["agreement"]["mean_deg"] < 0.001 for r in loo)
    assert all(r["n_others"] == 4 for r in loo)
    solo = ex.leave_one_out(_pairs(T12)[:1])
    assert solo[0]["agreement"] is None and "una sola" in solo[0]["note"]


def test_con_ruido_la_dispersion_crece_y_la_coincidencia_queda_bajo_el_umbral() -> None:
    T12 = second_camera(30.0)
    E = ex.from_marker_positions(_pairs(T12, n=200, noise_px=0.1))
    dmm, ddeg = g.pose_difference(E["T_ref_other"], T12)
    assert dmm < 0.3 and ddeg < 0.05
    assert 0 < E["spread_mm"] < 0.5
    loo = ex.leave_one_out(_pairs(T12, n=200, noise_px=0.1))
    peor = max(r["agreement"]["mean_mm"] for r in loo)
    assert 0 < peor < 0.5
    a = loo[0]["agreement"]
    assert set(a) >= {"n", "mean_mm", "sd_mm", "max_mm", "mean_deg", "sd_deg", "max_deg", "mean_dxyz_mm", "bias_mm"}
    assert a["bias_mm"] <= a["mean_mm"] + 1e-9


def test_apply_extrinsics_y_errores() -> None:
    T12 = second_camera(10.0)
    Ts = np.array([marker_pose(), marker_pose(x=50)])
    out = ex.apply_extrinsics(T12, Ts)
    assert out.shape == (2, 4, 4) and np.allclose(out[1], T12 @ Ts[1])
    with pytest.raises(ValueError):
        ex.from_marker_positions([])
    with pytest.raises(ValueError):
        ex.agreement_stats(Ts, Ts[:1])


def test_yml_se_escribe_se_lee_y_comprueba_el_sha(tmp_path: Path) -> None:
    y1, y2 = tmp_path / "gs1.yml", tmp_path / "gs2.yml"
    y1.write_text("a: 1\n", encoding="utf-8")
    y2.write_text("b: 2\n", encoding="utf-8")
    from fusion.dataset import sha256_file
    T12 = second_camera(30.0)
    e = ex.Extrinsics(T_ref_other=T12, reference="gs1", other="gs2", method="marker0", mount="pinzas",
                      intrinsics_sha256={"gs1": sha256_file(y1), "gs2": sha256_file(y2)},
                      angle_deg=ex.optical_axis_angle_deg(T12), validation={"peor_mm": 0.1, "posiciones": 5},
                      alternative=None)
    p = ex.save_extrinsics(tmp_path / "extrinsecos_gs1_gs2_pinzas.yml", e)
    texto = p.read_text(encoding="utf-8")
    assert "format: 1" in texto and "T_ref_other:" in texto and "mount: pinzas" in texto
    leido = ex.load_extrinsics(p, {"gs1": y1, "gs2": y2})
    assert np.allclose(leido.T_ref_other, T12) and leido.other == "gs2" and leido.validation["posiciones"] == 5
    assert leido.angle_deg == pytest.approx(30.0, abs=1e-6)
    with pytest.raises(FileExistsError):
        ex.save_extrinsics(p, e)
    y2.write_text("b: 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        ex.load_extrinsics(p, {"gs1": y1, "gs2": y2})
    with pytest.raises(FileNotFoundError):
        ex.load_extrinsics(tmp_path / "no.yml", {})
    roto = tmp_path / "roto.yml"
    roto.write_text("format: 1\nT_ref_other: [[1,0,0,0],[0,2,0,0],[0,0,1,0],[0,0,0,1]]\nreference: a\nother: b\nmethod: m\nmount: p\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rigida"):
        ex.load_extrinsics(roto, {})
