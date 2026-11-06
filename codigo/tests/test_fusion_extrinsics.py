"""fusion.extrinsics (meta 006, fase 1): con dos camaras sinteticas sin ruido, los
extrinsecos por Marker0 en 5 posiciones se recuperan a < 0.01 mm y < 0.001 grados; la
validacion cruzada da coincidencia ~0; el `.yml` se escribe, se lee, no se pisa y aborta si
cambia el sha256 de un intrinseco. Fase 2 (B94): sin mover nada, `repeat_check` y
`half_split` dan < 1e-6; con gs2 desplazada 2.0 mm y girada 0.5 grados entre pos1 y pos1_fin,
`repeat_check` lo recupera a < 0.01 mm y < 0.001 grados; la orden `guardar` escribe el `.yml`
solo si el criterio 1 (y el veredicto de B94) cumplen.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from fusion import extrinsics as ex
from fusion import geometry as g
from fusion.dataset import ippe_solutions, sha256_file

from .test_fusion_geometry import DIST, K, SIZE, marker_pose, second_camera

POSITIONS = [dict(x=20, y=5, z=380), dict(x=-60, y=5, z=380), dict(x=100, y=5, z=380),
             dict(x=20, y=-70, z=370, euler=(185 + 30, 8)), dict(x=20, y=80, z=390, euler=(185, 8 + 30))]


def pairs_of_position(T12: np.ndarray, pos: dict, n: int = 30, noise_px: float = 0.0,
                      rng: np.random.Generator | None = None) -> tuple[np.ndarray, np.ndarray]:
    """`(T_gs1<-M (n,4,4), T_gs2<-M (n,4,4))` de IPPE sobre las esquinas proyectadas (con ruido
    si se pide) del marker en `pos`, con gs2 en `T12 = T_gs1<-gs2`."""
    rng = np.random.default_rng(1) if rng is None else rng
    T1 = marker_pose(**pos)
    T2 = g.inv(T12) @ T1
    z1, z2 = g.project_corners(T1, SIZE, K, DIST), g.project_corners(T2, SIZE, K, DIST)
    Ta = np.array([ippe_solutions(z1 + rng.normal(0, noise_px, (4, 2)), SIZE, K, DIST)[0][0] for _ in range(n)])
    Tb = np.array([ippe_solutions(z2 + rng.normal(0, noise_px, (4, 2)), SIZE, K, DIST)[0][0] for _ in range(n)])
    return Ta, Tb


def _pairs(T12: np.ndarray, n: int = 30, noise_px: float = 0.0, seed: int = 1) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    return [pairs_of_position(T12, pos, n, noise_px, rng) for pos in POSITIONS]


def moved_camera(T12: np.ndarray, dx_mm: float = 2.0, dyaw_deg: float = 0.5) -> np.ndarray:
    """gs2 movida respecto a si misma: `T12 . delta` (la traslacion de delta es exactamente
    |t| = dx_mm y su giro dyaw_deg, asi que `pose_difference(T12, T12 . delta) = (dx_mm, dyaw_deg)`)."""
    d = np.eye(4)
    d[:3, :3] = Rotation.from_euler("z", dyaw_deg, degrees=True).as_matrix()
    d[:3, 3] = [dx_mm, 0.0, 0.0]
    return T12 @ d


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


# ---------------------------------------------------------------------------- B94 (fase 2)


def test_sin_mover_nada_repeat_check_y_half_split_dan_cero() -> None:
    T12 = second_camera(30.0)
    first = pairs_of_position(T12, POSITIONS[0])
    last = pairs_of_position(T12, POSITIONS[0])          # la misma geometria, otra vez
    r = ex.repeat_check(first, last)
    assert r["diff_mm"] < 1e-6 and r["diff_deg"] < 1e-6 and r["coinciden"]
    assert r["marker_shift_ref_mm"] < 1e-6 and r["marker_shift_other_mm"] < 1e-6
    assert r["n_first"] == 30 and r["n_last"] == 30 and r["tol_mm"] == 0.5 and r["tol_deg"] == 0.2
    assert g.pose_difference(r["T_first"], T12)[0] < 0.01
    for Ta, Tb in _pairs(T12):
        h = ex.half_split(Ta, Tb)
        assert h["diff_mm"] < 1e-6 and h["diff_deg"] < 1e-6 and h["n"] == 30 and h["n_first"] == 15 and h["n_second"] == 15
    # Con ruido de 0.1 px y 200 parejas, el suelo queda muy por debajo de los umbrales (0.5 mm, 0.2 grados).
    rng = np.random.default_rng(7)
    first = pairs_of_position(T12, POSITIONS[0], 200, 0.1, rng)
    last = pairs_of_position(T12, POSITIONS[0], 200, 0.1, rng)
    r = ex.repeat_check(first, last)
    assert 0 < r["diff_mm"] < 0.2 and 0 < r["diff_deg"] < 0.05 and r["coinciden"]
    h = ex.half_split(*first)
    assert 0 < h["diff_mm"] < 0.3 and 0 < h["diff_deg"] < 0.1
    with pytest.raises(ValueError, match="4 parejas"):
        ex.half_split(first[0][:3], first[1][:3])
    with pytest.raises(ValueError):
        ex.half_split(first[0], first[1][:10])


def test_repeat_check_recupera_que_gs2_se_movio_2mm_y_medio_grado() -> None:
    T12 = second_camera(30.0)
    T12b = moved_camera(T12, 2.0, 0.5)
    assert g.pose_difference(T12, T12b) == pytest.approx((2.0, 0.5), abs=1e-9)
    first = pairs_of_position(T12, POSITIONS[0])
    last = pairs_of_position(T12b, POSITIONS[0])         # el marker en el mismo sitio; gs2 movida
    r = ex.repeat_check(first, last)
    assert abs(r["diff_mm"] - 2.0) < 0.01 and abs(r["diff_deg"] - 0.5) < 0.001, (r["diff_mm"], r["diff_deg"])
    assert not r["coinciden"]
    assert r["marker_shift_ref_mm"] < 0.01 and r["marker_shift_ref_deg"] < 0.001      # gs1 no se movio
    assert r["marker_shift_other_mm"] > 1.5                                           # gs2 si lo ve movido
    # Dentro de un tramo: la segunda mitad con gs2 movida.
    Ta = np.concatenate([first[0], last[0]])
    Tb = np.concatenate([first[1], last[1]])
    h = ex.half_split(Ta, Tb)
    assert abs(h["diff_mm"] - 2.0) < 0.01 and abs(h["diff_deg"] - 0.5) < 0.001


def _resultados(tmp_path: Path, cumple: bool, b94: str | None = "cumple", with_bundle: bool = True,
                intr: dict[str, Path] | None = None) -> Path:
    T12 = second_camera(30.0)
    shas = {c: sha256_file(p) for c, p in (intr or {}).items()}
    rep = {"datos": "20261106-000000",
           "comprobacion": {"S2_pos1": {"calibration_sha256": {c: {"recorded": s, "local": s} for c, s in shas.items()}}},
           "extrinsecos": {"T_ref_other": T12.tolist(), "segmentos": ["S2_pos1", "S2_pos2"], "n_positions": 2,
                           "spread_mm": 0.1, "spread_deg": 0.01, "angle_deg": 30.0},
           "consistencia": {"bundle": {"T_ref_other": (T12 @ np.diag([1, 1, 1, 1])).tolist(), "rms_px": 0.2, "angle_deg": 30.1}} if with_bundle else {},
           "criterio_1": {"cumple": cumple, "peor_mm": 0.3 if cumple else 19.5, "peor_deg": 0.1 if cumple else 5.8, "min_parejas": 2500}}
    if b94 is not None:
        rep["b94"] = {"veredicto": b94, "motivo": "prueba"}
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "resultados.json"
    p.write_text(json.dumps(rep), encoding="utf-8")
    return p


def test_guardar_escribe_el_yml_solo_si_el_criterio_1_cumple(tmp_path: Path, capsys) -> None:
    y1, y2 = tmp_path / "gs1.yml", tmp_path / "gs2.yml"
    y1.write_text("a: 1\n", encoding="utf-8")
    y2.write_text("b: 2\n", encoding="utf-8")
    intr = {"gs1": y1, "gs2": y2}
    salida = tmp_path / "extrinsecos_gs1_gs2_pinzas.yml"
    base = ["guardar", "--montaje", "pinzas", "--intrinsecos", f"gs1={y1}", f"gs2={y2}", "--salida", str(salida)]
    # No cumple: codigo 1, nada escrito.
    assert ex.main(base + ["--resultados", str(_resultados(tmp_path / "a", False, intr=intr)), "--metodo", "marker0"]) == 1
    assert not salida.exists() and "no cumple" in capsys.readouterr().err
    # Cumple pero el veredicto de B94 es otro: codigo 1.
    assert ex.main(base + ["--resultados", str(_resultados(tmp_path / "b", True, "se_movio", intr=intr)), "--metodo", "marker0"]) == 1
    assert not salida.exists() and "se_movio" in capsys.readouterr().err
    # Sin ajuste conjunto no hay metodo bundle: codigo 2.
    assert ex.main(base + ["--resultados", str(_resultados(tmp_path / "c", True, with_bundle=False, intr=intr)), "--metodo", "bundle"]) == 2
    # Otro intrinseco que el grabado: codigo 2.
    y3 = tmp_path / "otro.yml"
    y3.write_text("c: 3\n", encoding="utf-8")
    rc = ex.main(["guardar", "--montaje", "pinzas", "--intrinsecos", f"gs1={y1}", f"gs2={y3}", "--salida", str(salida),
                  "--resultados", str(_resultados(tmp_path / "d", True, intr=intr)), "--metodo", "marker0"])
    assert rc == 2 and "sha256" in capsys.readouterr().err and not salida.exists()
    # Cumple: se escribe, se lee y lleva la alternativa; la segunda vez no se pisa (2).
    res = _resultados(tmp_path / "e", True, intr=intr)
    assert ex.main(base + ["--resultados", str(res), "--metodo", "marker0"]) == 0
    out = capsys.readouterr().out
    assert "escrito" in out and "metodo marker0" in out
    leido = ex.load_extrinsics(salida, intr)
    assert leido.method == "marker0" and leido.mount == "pinzas" and leido.alternative["method"] == "bundle"
    assert leido.validation["criterio_1_peor_mm"] == 0.3 and leido.validation["b94"] == "cumple" and leido.validation["posiciones"] == 2
    assert np.allclose(leido.T_ref_other, second_camera(30.0))
    assert ex.main(base + ["--resultados", str(res), "--metodo", "marker0"]) == 2
    assert "no se pisa" in capsys.readouterr().err
    # El metodo bundle, con marker0 de alternativa; y un criterio 1 sin evaluar (cumple None) no guarda.
    salida2 = tmp_path / "bundle.yml"
    assert ex.main(["guardar", "--montaje", "estructura", "--intrinsecos", f"gs1={y1}", f"gs2={y2}", "--salida", str(salida2),
                    "--resultados", str(res), "--metodo", "bundle"]) == 0
    assert ex.load_extrinsics(salida2, intr).alternative["method"] == "marker0"
    with pytest.raises(ValueError, match="no se evaluo"):
        ex.extrinsics_from_results({"criterio_1": {}}, "marker0", "pinzas", intr)
    with pytest.raises(SystemExit):
        ex.main(["guardar", "--resultados", str(res)])


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
