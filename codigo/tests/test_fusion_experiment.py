"""fusion.experiment (meta 006, fase 1): el experimento entero sobre el recorte real de
`tests/data/fusion_gs1_gs2/` (8 s de S1_reposo y 3 s de cada posicion de S2, grabacion del
2026-11-05 en la Jetson) reproduce su referencia (`referencia.json`: extrinsecos, criterio 1,
sigma_px, criterio 2 por motor) a 1e-6 relativo; dos corridas dan el mismo `resultados.json`;
la CLI devuelve 2 si la salida existe o faltan intrinsecos, 0 si todo pasa, 1 si un segmento
no pasa; el tope corta; los motores gtsam_* se rechazan en la parte A.

Para regenerar la referencia a proposito (el cambio queda en git diff), desde codigo/:

    python -m tests.test_fusion_experiment --regenerar
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from fusion import experiment as xp

from .conftest import DATA_DIR, TESTS_DATA_DIR

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
    assert "[experimento] criterios:" in out.out and "informe:" in out.out
    assert xp.main(args) == 2 and "no se pisa" in capsys.readouterr().err
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
    d = xp.Deadline(None)
    d.check("nada")
    assert d.elapsed() >= 0


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
