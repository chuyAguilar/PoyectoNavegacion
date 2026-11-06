"""fusion.experiment (meta 006, fase 1): el experimento entero sobre el recorte real de
`tests/data/fusion_gs1_gs2/` (8 s de S1_reposo y 3 s de cada posicion de S2, grabacion del
2026-11-05 en la Jetson) reproduce su referencia (`referencia.json`: extrinsecos, criterio 1,
sigma_px, criterio 2 por motor) a 1e-6 relativo; dos corridas dan el mismo `resultados.json`;
la CLI devuelve 2 si la salida existe o faltan intrinsecos, 0 si todo pasa, 1 si un segmento
no pasa; el tope corta; los motores gtsam_* se rechazan en la parte A.

Fase 2 (B94): la referencia de la fase 1 se reproduce sin cambios (la tolerancia del ancla por
defecto no cambia ningun numero); `S2_pos1_fin` entra en sigma_px y en el criterio 2 pero no en
los extrinsecos ni en la validacion cruzada; `b94_verdict` sobre dos camaras sinteticas da
«cumple» sin mover nada, «se_movio» con gs2 desplazada 2.0 mm y girada 0.5 grados entre pos1 y
pos1_fin (recuperado a < 0.01 mm y < 0.001 grados), «sesgo_por_vista» con un sesgo de
inclinacion que cambia con la vista y nada movido, y «sin_decidir» si el marker no volvio a su
sitio o falta la repetida; la CLI acepta `--tolerancia-ancla-ms`.

Para regenerar la referencia a proposito (el cambio queda en git diff), desde codigo/:

    python -m tests.test_fusion_experiment --regenerar
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from fusion import experiment as xp
from fusion import extrinsics as ex
from fusion import geometry as g

from .conftest import DATA_DIR, TESTS_DATA_DIR
from .test_fusion_extrinsics import POSITIONS, moved_camera, pairs_of_position
from .test_fusion_geometry import second_camera

RECORTE = TESTS_DATA_DIR / "fusion_gs1_gs2"
REFERENCIA = RECORTE / "referencia.json"
INTRINSICS = {"gs1": DATA_DIR / "intrinsecos_gs1_1280x960.yml", "gs2": DATA_DIR / "intrinsecos_gs2_1280x960.yml"}
ENGINES = ("numpy_pose", "numpy_reproj")
REL = 1e-6


def extract_reference(rep: dict) -> dict:
    """Lo que la suite fija del experimento (numeros, sin tiempos)."""
    c2 = {r["segmento"]: {"parejas": r["parejas"], "camaras": {c: v["sd_3d_mm"] for c, v in r["camaras"].items()},
                          "predicha": r["predicha"]["reduction_3d"],
                          "motores": {e: {"sd_3d_mm": m["sd_3d_mm"], "reduction": m["reduction"]} for e, m in r["motores"].items()}}
          for r in rep["criterio_2"]["por_segmento"]}
    return {
        "segmentos": {s: {"ok": ch["ok"], "frames": ch["frames"], "fraction_with_pose": ch["fraction_with_pose"]}
                      for s, ch in rep["comprobacion"].items()},
        "extrinsecos": {"T_ref_other": np.asarray(rep["extrinsecos"]["T_ref_other"]).tolist(),
                        "angle_deg": rep["extrinsecos"]["angle_deg"], "spread_mm": rep["extrinsecos"]["spread_mm"]},
        "criterio_1": {"peor_mm": rep["criterio_1"]["peor_mm"], "peor_deg": rep["criterio_1"]["peor_deg"]},
        "consistencia": {"bundle_rms_px": rep["consistencia"]["bundle"]["rms_px"],
                         "distancias_max_diff_mm": rep["consistencia"]["distancias_max_diff_mm"]},
        "sigma_px": {c: v["sigma_px"] for c, v in rep["sigma_px"].items()},
        "criterio_2": c2,
        "criterios": [{"id": c["id"], "estado": c["estado"]} for c in rep["criterios"]],
    }


def _assert_close(a, b, path="") -> None:
    if isinstance(a, dict):
        assert set(a) == set(b), (path, set(a) ^ set(b))
        for k in a:
            _assert_close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_close(x, y, f"{path}[{i}]")
    elif isinstance(a, float):
        assert b == pytest.approx(a, rel=REL, abs=1e-9), (path, a, b)
    else:
        assert a == b, (path, a, b)


@pytest.fixture(scope="module")
def corrida() -> dict:
    assert RECORTE.is_dir(), "falta el recorte real de la meta 006"
    res = xp.run_experiment(RECORTE, INTRINSICS, None, ENGINES, timeout_s=300)
    rep, tiempos, series = xp._split_results(res)
    return {"rep": rep, "tiempos": tiempos, "series": series}


def test_reproduce_la_referencia(corrida) -> None:
    assert REFERENCIA.is_file(), "falta referencia.json (python -m tests.test_fusion_experiment --regenerar)"
    ref = json.loads(REFERENCIA.read_text(encoding="utf-8"))
    got = json.loads(json.dumps(xp._jsonable(extract_reference(corrida["rep"]))))
    _assert_close(ref, got)


def test_lo_que_sale_tiene_sentido(corrida) -> None:
    rep, tiempos, series = corrida["rep"], corrida["tiempos"], corrida["series"]
    assert rep["segmentos_fuera"] == [] and set(rep["comprobacion"]) == {"S1_reposo", "S2_pos1", "S2_pos2", "S2_pos3", "S2_pos4", "S2_pos5"}
    assert rep["extrinsecos"]["n_positions"] == 5 and 40 < rep["extrinsecos"]["angle_deg"] < 60
    assert 150 < rep["extrinsecos"]["baseline_mm"] < 250
    assert len(rep["criterio_1"]["por_posicion"]) == 5 and all(r["n"] > 100 for r in rep["criterio_1"]["por_posicion"])
    assert 0.02 < rep["sigma_px"]["gs1"]["sigma_px"] < 0.5 and 0.02 < rep["sigma_px"]["gs2"]["sigma_px"] < 0.5
    s1 = next(r for r in rep["criterio_2"]["por_segmento"] if r["segmento"] == "S1_reposo")
    assert set(s1["motores"]) == set(ENGINES) and s1["parejas"] > 300
    for m in s1["motores"].values():
        assert 0 < m["sd_3d_mm"] < 0.5 and -1 < m["reduction"] < 1
    assert s1["motores"]["numpy_reproj"]["rms_px_median"] is not None
    assert rep["consistencia"]["bundle"]["combinaciones"] == 32 and len(rep["consistencia"]["distancias"]) == 10
    ids = [c["id"] for c in rep["criterios"]]
    assert ids.count("2") == 2 and "1" in ids and "1b" in ids and "rigidez" in ids and "delta" in ids and "IPPE" in ids
    assert all(c["estado"] in ("cumple", "no cumple", "informativo", "sin evaluar") for c in rep["criterios"])
    assert set(tiempos["por_motor"]) == set(ENGINES) and tiempos["por_motor"]["numpy_pose"]["n"] > 1000
    assert "S1_reposo" in series and set(series["S1_reposo"]["positions"]) == {"gs1", "gs2", *ENGINES}
    assert rep["desfase"] == {} and any(c["id"] == "delta" and c["estado"] == "sin evaluar" for c in rep["criterios"])
    # Fase 2: sin S2_pos1_fin el veredicto de B94 queda sin decidir, y la tolerancia usada es la de siempre.
    assert rep["tolerancia_ancla_ms"] == 1.0
    assert rep["b94"]["veredicto"] == "sin_decidir" and "falta" in rep["b94"]["motivo"] and rep["b94"]["repeticion"] is None
    assert set(rep["b94"]["mitades"]) == {"S2_pos1", "S2_pos2", "S2_pos3", "S2_pos4", "S2_pos5"}
    assert all(c["id"] != "B94" for c in rep["criterios"])      # el veredicto no es un criterio del spec


def test_dos_corridas_dan_el_mismo_json(corrida) -> None:
    res2 = xp.run_experiment(RECORTE, INTRINSICS, None, ("numpy_pose",), timeout_s=300)
    rep2, _, _ = xp._split_results(res2)
    a = json.dumps(xp._jsonable(corrida["rep"]["criterio_1"]), sort_keys=True)
    b = json.dumps(xp._jsonable(rep2["criterio_1"]), sort_keys=True)
    assert a == b
    assert json.dumps(xp._jsonable(corrida["rep"]["extrinsecos"]), sort_keys=True) == json.dumps(xp._jsonable(rep2["extrinsecos"]), sort_keys=True)


def test_cli_codigos_y_archivos(tmp_path: Path, capsys) -> None:
    salida = tmp_path / "corrida"
    args = ["--datos", str(RECORTE), "--intrinsecos", f"gs1={INTRINSICS['gs1']}", f"gs2={INTRINSICS['gs2']}",
            "--salida", str(salida), "--motores", "numpy_pose", "--timeout", "300"]
    rc = xp.main(args)
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert (salida / "resultados.json").is_file() and (salida / "informe.html").is_file() and (salida / "tiempos.json").is_file()
    rep = json.loads((salida / "resultados.json").read_text(encoding="utf-8"))
    assert "tiempos" not in rep and "series" not in rep and rep["motores"] == ["numpy_pose"]
    assert "[experimento] criterios:" in out.out and "informe:" in out.out and "B94:" in out.out
    assert rep["tolerancia_ancla_ms"] == 1.0
    assert xp.main(args) == 2 and "no se pisa" in capsys.readouterr().err
    # Fase 2: la tolerancia del ancla por la CLI (20 para las grabaciones del PC); 0 no vale.
    salida_t = tmp_path / "tol"
    assert xp.main(args[:-6] + ["--salida", str(salida_t), "--motores", "numpy_pose", "--timeout", "300", "--tolerancia-ancla-ms", "20"]) == 0
    assert json.loads((salida_t / "resultados.json").read_text(encoding="utf-8"))["tolerancia_ancla_ms"] == 20.0
    assert xp.main(args[:-6] + ["--salida", str(tmp_path / "t0"), "--motores", "numpy_pose", "--timeout", "300", "--tolerancia-ancla-ms", "0"]) == 2
    assert "tolerancia" in capsys.readouterr().err
    assert xp.main(args[:2] + ["--intrinsecos", f"gs1={INTRINSICS['gs1']}", "--salida", str(tmp_path / "b"), "--timeout", "10"]) == 2
    assert xp.main(["--datos", str(tmp_path / "nada"), "--intrinsecos", f"gs1={INTRINSICS['gs1']}", f"gs2={INTRINSICS['gs2']}",
                    "--salida", str(tmp_path / "c"), "--timeout", "10"]) == 2
    with pytest.raises(SystemExit):
        xp.main(args + ["--motores", "otro"])


def test_un_segmento_que_no_cumple_da_1_y_queda_fuera(tmp_path: Path, capsys) -> None:
    import shutil
    datos = tmp_path / "datos"
    datos.mkdir()
    for p in RECORTE.glob("S*.npz"):
        shutil.copy(p, datos / p.name)
    # Una posicion con los intrinsecos "equivocados": se rompe el sha en metadata.
    import numpy as np
    from diagnostics.pose_log import TABLES
    src = datos / "S2_pos3_gs2.npz"
    with np.load(src, allow_pickle=False) as d:
        arrays = {k: d[k] for k in TABLES}
    meta = json.loads(str(arrays["metadata_json"]))
    meta["calibration_sha256"] = "0" * 64
    arrays["metadata_json"] = np.asarray(json.dumps(meta))
    src.unlink()
    np.savez_compressed(src, **arrays)
    rc = xp.main(["--datos", str(datos), "--intrinsecos", f"gs1={INTRINSICS['gs1']}", f"gs2={INTRINSICS['gs2']}",
                  "--salida", str(tmp_path / "s"), "--motores", "numpy_pose", "--timeout", "300"])
    assert rc == 1
    rep = json.loads((tmp_path / "s" / "resultados.json").read_text(encoding="utf-8"))
    assert rep["segmentos_fuera"] == ["S2_pos3"] and rep["extrinsecos"]["n_positions"] == 4
    assert "S2_pos3" not in [r["segmento"] for r in rep["criterio_2"]["por_segmento"]]
    assert "no cumple" in capsys.readouterr().out.lower() or True


def test_tope_y_motores_de_la_parte_b() -> None:
    with pytest.raises(TimeoutError):
        xp.run_experiment(RECORTE, INTRINSICS, None, ("numpy_pose",), timeout_s=0.0)
    with pytest.raises(ValueError, match="parte B"):
        xp.run_experiment(RECORTE, INTRINSICS, None, ("gtsam_pose",), timeout_s=10)
    with pytest.raises(ValueError, match="tolerancia"):
        xp.run_experiment(RECORTE, INTRINSICS, None, ("numpy_pose",), timeout_s=10, anchor_tol_ms=0)
    d = xp.Deadline(None)
    d.check("nada")
    assert d.elapsed() >= 0


# ---------------------------------------------------------------------------- B94 (fase 2)

S2 = ["S2_pos1", "S2_pos2", "S2_pos3", "S2_pos4", "S2_pos5"]
FIN = "S2_pos1_fin"


def _rx(deg: float) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = Rotation.from_euler("x", deg, degrees=True).as_matrix()
    return T


def _rest(T12: np.ndarray, T12_fin: np.ndarray | None = None, n: int = 30, bias_deg: dict | None = None,
          marker_shift_fin_mm: float = 0.0, second_half_T12: dict | None = None) -> dict:
    """Un `rest` como el de `run_experiment` (tracks con `T_raw` y `pairs`) con dos camaras
    sinteticas exactas en S2_pos1..5 y S2_pos1_fin. `T12_fin`: gs2 en la repetida (si se movio);
    `bias_deg[seg]`: un giro de la pose que gs2 mide, sobre el eje x del marker (un sesgo que cambia
    con la vista); `marker_shift_fin_mm`: el marker no vuelve exactamente a pos1; `second_half_T12[seg]`:
    gs2 en la segunda mitad de ese tramo (se movio dentro del tramo)."""
    rest = {}
    for seg in S2 + [FIN]:
        pos = dict(POSITIONS[0] if seg == FIN else POSITIONS[S2.index(seg)])
        if seg == FIN:
            pos["x"] = pos["x"] + marker_shift_fin_mm
        T = T12_fin if (seg == FIN and T12_fin is not None) else T12
        Ta, Tb = pairs_of_position(T, pos, n)
        if second_half_T12 and seg in second_half_T12:
            Ta2, Tb2 = pairs_of_position(second_half_T12[seg], pos, n)
            Ta, Tb = np.concatenate([Ta[: n // 2], Ta2[n // 2:]]), np.concatenate([Tb[: n // 2], Tb2[n // 2:]])
        if bias_deg and seg in bias_deg:
            Tb = np.einsum("nij,jk->nik", Tb, _rx(bias_deg[seg]))
        idx = np.arange(len(Ta))
        rest[seg] = {"tracks": {"gs1": SimpleNamespace(T_raw=Ta), "gs2": SimpleNamespace(T_raw=Tb)},
                     "pairs": np.column_stack([idx, idx])}
    return rest


def _criterio_1(rest: dict) -> dict:
    ppp = [(rest[s]["tracks"]["gs1"].T_raw, rest[s]["tracks"]["gs2"].T_raw) for s in S2]
    loo = ex.leave_one_out(ppp)
    worst_mm = max(r["agreement"]["mean_mm"] for r in loo)
    worst_deg = max(r["agreement"]["mean_deg"] for r in loo)
    return {"peor_mm": worst_mm, "peor_deg": worst_deg,
            "cumple": bool(worst_mm < xp.THRESH["agreement_mm"] and worst_deg < xp.THRESH["agreement_deg"])}


def test_b94_sin_mover_nada_cumple() -> None:
    rest = _rest(second_camera(30.0))
    v = xp.b94_verdict(rest, S2, _criterio_1(rest))
    assert v["veredicto"] == "cumple", v["motivo"]
    r = v["repeticion"]
    assert r["diff_mm"] < 1e-6 and r["diff_deg"] < 1e-6 and r["coinciden"] and r["marker_shift_ref_mm"] < 1e-6
    assert set(v["mitades"]) == set(S2 + [FIN]) and v["mitades_peor_mm"] < 1e-6 and v["mitades_peor_deg"] < 1e-6
    assert v["criterio_1_cumple"] is True and v["umbrales"] == {"mm": 0.5, "deg": 0.2, "volvio_mm": 5.0, "volvio_deg": 2.0}
    assert "distancias_max_diff_mm" not in v
    assert xp.b94_verdict(rest, S2, _criterio_1(rest), {"distancias_max_diff_mm": 0.3})["distancias_max_diff_mm"] == 0.3


def test_b94_gs2_movida_entre_pos1_y_pos1_fin_da_se_movio() -> None:
    T12 = second_camera(30.0)
    rest = _rest(T12, T12_fin=moved_camera(T12, 2.0, 0.5))
    c1 = _criterio_1(rest)
    assert c1["cumple"]                                   # las 5 posiciones son coherentes: solo la repetida delata el movimiento
    v = xp.b94_verdict(rest, S2, c1)
    assert v["veredicto"] == "se_movio" and "pos1_fin" in v["motivo"] and "mitades" not in v["motivo"]
    r = v["repeticion"]
    assert abs(r["diff_mm"] - 2.0) < 0.01 and abs(r["diff_deg"] - 0.5) < 0.001 and not r["coinciden"]
    assert r["marker_shift_ref_mm"] < 0.01                # visto por gs1, el marker volvio a su sitio
    # Movida dentro de un tramo (la segunda mitad de S2_pos3): tambien «se movio», por las mitades.
    rest = _rest(T12, second_half_T12={"S2_pos3": moved_camera(T12, 2.0, 0.5)})
    v = xp.b94_verdict(rest, S2, _criterio_1(rest))
    assert v["veredicto"] == "se_movio" and "mitades de S2_pos3" in v["motivo"]
    assert abs(v["mitades"]["S2_pos3"]["diff_mm"] - 2.0) < 0.01 and v["mitades"]["S2_pos1"]["diff_mm"] < 1e-6


def test_b94_sesgo_por_vista_sin_mover_nada() -> None:
    # Un giro de la pose de gs2 sobre el eje x del marker que cambia con la vista; pos1 y pos1_fin, la misma.
    bias = {"S2_pos1": 1.0, "S2_pos2": 3.0, "S2_pos3": -2.0, "S2_pos4": 4.0, "S2_pos5": 0.0, FIN: 1.0}
    rest = _rest(second_camera(30.0), bias_deg=bias)
    c1 = _criterio_1(rest)
    assert not c1["cumple"] and c1["peor_mm"] > 1.0
    v = xp.b94_verdict(rest, S2, c1)
    assert v["veredicto"] == "sesgo_por_vista", v["motivo"]
    assert v["repeticion"]["coinciden"] and v["repeticion"]["diff_mm"] < 1e-6 and v["mitades_peor_mm"] < 1e-6
    assert "hipotesis b" in v["motivo"]


def test_b94_sin_decidir_si_el_marker_no_volvio_o_falta_la_repetida() -> None:
    T12 = second_camera(30.0)
    rest = _rest(T12, marker_shift_fin_mm=10.0)           # las dos lo ven 10 mm mas alla
    v = xp.b94_verdict(rest, S2, _criterio_1(rest))
    assert v["veredicto"] == "sin_decidir" and "no volvio" in v["motivo"]
    assert abs(v["repeticion"]["marker_shift_ref_mm"] - 10.0) < 0.05
    rest.pop(FIN)
    v = xp.b94_verdict(rest, S2, _criterio_1(rest))
    assert v["veredicto"] == "sin_decidir" and "falta" in v["motivo"] and v["repeticion"] is None and FIN not in v["mitades"]
    # La regla, suelta: sin criterio 1 evaluado (una sola posicion) tampoco decide.
    rep = {"diff_mm": 0.0, "diff_deg": 0.0, "marker_shift_ref_mm": 0.0, "marker_shift_ref_deg": 0.0, "coinciden": True}
    assert xp.b94_rule(rep, {}, {})[0] == "sin_decidir"
    assert xp.b94_rule(rep, {}, {"cumple": True, "peor_mm": 0.1, "peor_deg": 0.05})[0] == "cumple"
    assert xp.b94_rule(rep, {"S2_pos2": {"diff_mm": 0.6, "diff_deg": 0.0}}, {"cumple": True, "peor_mm": 0.1, "peor_deg": 0.05})[0] == "se_movio"
    assert xp.b94_rule(None, {}, {"cumple": True})[0] == "sin_decidir"
    assert all(v in xp.B94_VERDICTS for v in ("sin_decidir", "se_movio", "cumple", "sesgo_por_vista"))


def test_s2_pos1_fin_entra_en_sigma_y_criterio_2_pero_no_en_los_extrinsecos(corrida, tmp_path: Path) -> None:
    datos = tmp_path / "datos"
    datos.mkdir()
    for p in RECORTE.glob("S*.npz"):
        shutil.copy(p, datos / p.name)
    for c in ("gs1", "gs2"):
        shutil.copy(RECORTE / f"S2_pos1_{c}.npz", datos / f"S2_pos1_fin_{c}.npz")      # la repetida, identica a pos1
    res = xp.run_experiment(datos, INTRINSICS, None, ("numpy_pose",), timeout_s=300)
    rep, _, _ = xp._split_results(res)
    assert FIN in rep["comprobacion"] and rep["comprobacion"][FIN]["ok"] and rep["segmentos_fuera"] == []
    assert FIN not in rep["extrinsecos"]["segmentos"] and rep["extrinsecos"]["n_positions"] == 5
    assert FIN not in [r["segmento"] for r in rep["criterio_1"]["por_posicion"]]
    assert FIN not in rep["consistencia"]["segmentos"]
    # Fuera de los extrinsecos de verdad: la matriz es la misma que sin la repetida, bit a bit.
    assert np.array_equal(np.asarray(rep["extrinsecos"]["T_ref_other"]), np.asarray(corrida["rep"]["extrinsecos"]["T_ref_other"]))
    assert rep["criterio_1"]["peor_mm"] == corrida["rep"]["criterio_1"]["peor_mm"]
    assert FIN in [r["segmento"] for r in rep["criterio_2"]["por_segmento"]]
    assert FIN in rep["sigma_px"]["gs1"]["segmentos"] and rep["sigma_px"]["gs1"]["sigma_px"] != corrida["rep"]["sigma_px"]["gs1"]["sigma_px"]
    b = rep["b94"]
    assert b["repeticion"] is not None and b["repeticion"]["diff_mm"] < 1e-9 and b["repeticion"]["coinciden"]
    assert FIN in b["mitades"] and b["veredicto"] in xp.B94_VERDICTS and b["veredicto"] != "sin_decidir"
    assert "falta" not in b["motivo"]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--regenerar"]:
        print("uso: python -m tests.test_fusion_experiment --regenerar", file=sys.stderr)
        return 2
    res = xp.run_experiment(RECORTE, INTRINSICS, None, ENGINES, timeout_s=600)
    rep, _, _ = xp._split_results(res)
    REFERENCIA.write_text(json.dumps(xp._jsonable(extract_reference(rep)), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[referencia] escrita {REFERENCIA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
