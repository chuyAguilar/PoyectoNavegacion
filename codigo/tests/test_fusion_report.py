"""fusion.report (meta 006, fase 1): el informe se escribe en un solo HTML con la tabla de
criterios, las graficas en base64 y los diagramas Mermaid (CDN de jsdelivr), y no pisa uno
que exista; `figures_for` da >= 6 PNG con unos resultados minimos; `mermaid_diagrams` da
>= 2 diagramas. Fase 2: la seccion de B94 (veredicto, la posicion repetida y las mitades).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fusion import report as rp


def _results() -> tuple[dict, dict]:
    rng = np.random.default_rng(1)
    n = 300
    t = 1000.0 + np.arange(n) / 63.0
    pos = {"gs1": rng.normal(0, 0.05, (n, 3)) + [20, 5, 380], "gs2": rng.normal(0, 0.05, (n, 3)) + [20.3, 5, 380],
           "numpy_pose": rng.normal(0, 0.03, (n, 3)) + [20.1, 5, 380]}
    series = {"S1_reposo": {"t": t, "positions": pos},
              "S3_tapa_gs1": {"t": t, "positions": {"numpy_pose": pos["numpy_pose"], "gs1": pos["gs1"], "gs2": pos["gs2"]},
                              "events": [(t[100], t[200])]}}
    cams = {c: {"sd_3d_mm": 0.09, "sd_3d_detrended_mm": 0.08, "sd_axes_mm": [0.05, 0.05, 0.05]} for c in ("gs1", "gs2")}
    motor = {"sd_3d_mm": 0.05, "sd_3d_detrended_mm": 0.045, "sd_axes_mm": [0.03, 0.03, 0.03], "reduction": 0.44,
             "reduction_detrended": 0.43, "rms_px_median": 0.2}
    results = {
        "criterios": [{"id": "1", "nombre": "coinciden", "valor": "0.3 mm / 0.1 grados", "umbral": "< 0.5", "estado": "cumple", "nota": ""},
                      {"id": "2", "nombre": "jitter", "valor": "44 %", "umbral": ">= 30 %", "estado": "cumple", "nota": ""},
                      {"id": "3", "nombre": "tapar", "valor": None, "umbral": "<= 0.5 mm", "estado": "sin evaluar", "nota": "x"},
                      {"id": "delta", "nombre": "desfase", "valor": 1.5, "umbral": "—", "estado": "informativo", "nota": ""}],
        "avisos": ["un aviso"], "notas": ["una nota"], "subtitulo": "prueba",
        "comprobacion": {"S1_reposo": {"ok": True, "anchor_diff_ms": 0.001, "overlap_s": 64.9, "expected_s": 65.0,
                                       "fraction_with_pose": {"gs1": 0.99, "gs2": 1.0}, "calibration_ok": {"gs1": True, "gs2": True},
                                       "rotation_max_diff_deg": {"gs1": 2e-6, "gs2": 1e-6}, "reasons": []}},
        "extrinsecos": {"T_ref_other": np.eye(4), "n_positions": 5, "segmentos": ["S2_pos1"], "angle_deg": 48.9, "baseline_mm": 192.0,
                        "spread_mm": 0.1, "spread_deg": 0.01},
        "consistencia": {"segmentos": ["S2_pos1", "S2_pos2"], "distancias": [{"a": "S2_pos1", "b": "S2_pos2", "gs1": 62.5, "gs2": 55.7, "diff_mm": 6.8}],
                         "vista_unica": {"S2_pos1": {"gs1": {"rms_px": 0.1}, "gs2": {"rms_px": 0.2}}, "S2_pos2": {"gs1": {"rms_px": 0.1}, "gs2": {"rms_px": 0.2}}},
                         "vista_unica_max_rms_px": 0.2, "distancias_max_diff_mm": 6.8,
                         "bundle": {"T_ref_other": np.eye(4), "rms_px": 5.7, "rms_por_posicion": [{"gs1": 1.0, "gs2": 2.0}, {"gs1": 1.0, "gs2": 2.0}],
                                    "iteraciones": 10, "combinaciones": 4, "angle_deg": 50.0},
                         "loo": [{"segmento": "S2_pos1", "rms_px": 1.0, "angle_deg": 47.0, "mean_mm": 19.5, "mean_deg": 2.8, "mean_dxyz_mm": [1, 2, 3]}]},
        "criterio_1": {"por_posicion": [{"segmento": "S2_pos1", "n": 1961, "mean_mm": 0.3, "sd_mm": 0.1, "max_mm": 0.6, "mean_deg": 0.1,
                                         "sd_deg": 0.05, "mean_dxyz_mm": [0.1, 0.2, 0.1], "bias_mm": 0.25}]},
        "sigma_px": {"gs1": {"sigma_px": 0.08, "sigma_px_detrended": 0.07, "segmentos": ["S2_pos1"], "origen": "ajustado"}},
        "criterio_2": {"por_segmento": [{"segmento": "S1_reposo", "parejas": 3000, "camaras": cams, "mejor": "gs2",
                                         "predicha": {"reduction_3d": 0.56}, "motores": {"numpy_pose": motor},
                                         "discrepancia_gs1_gs2_mm": 0.3, "discrepancia_gs1_gs2_deg": 0.1}]},
        "criterio_3": {"por_segmento": [{"segmento": "S3_tapa_gs1", "tapada": "gs1", "eventos": [[t[100], t[200]]],
                                         "motores": {"numpy_pose": {"fraction_with_pose": 1.0, "transitions": [
                                             {"kind": "tapar", "t_rel_s": 1.6, "n_before": 15, "n_after": 15, "jump_mm": 0.2, "max_step_mm": 0.3}]}}}]},
        "desfase": {"segmento": "S4_movimiento", "informativo": True, "speed_mm_s": 32.0, "offset_ms": 1.5, "rms_min_mm": 0.3, "rms_at_zero_mm": 0.4,
                    "note": "", "curve": {"delta_ms": [-2, 0, 2], "rms_mm": [0.5, 0.4, 0.45]}, "sin_alinear": {"offset_ms": -20.0, "rms_min_mm": 7.2, "note": "borde"}},
        "ippe_otra_solucion": {"S1_reposo": {"gs1": {"sin_deteccion": 16, "varias_detecciones": 0, "pose_invalida": 0, "rescatables_por_la_otra_solucion": 0}}},
        "tiempos": {"por_motor": {"numpy_pose": {"n": 10, "mean_ms": 1.0, "p50_ms": 1.0, "p95_ms": 2.0, "max_ms": 3.0}}, "total_s": 12.0},
        "segmento_reposo": "S1_reposo",
        "tolerancia_ancla_ms": 20.0,
        "b94": {"veredicto": "sesgo_por_vista", "motivo": "nada se movio y el criterio 1 no cumple (prueba)",
                "posiciones_repetidas": ["S2_pos1", "S2_pos1_fin"],
                "umbrales": {"mm": 0.5, "deg": 0.2, "volvio_mm": 5.0, "volvio_deg": 2.0},
                "repeticion": {"n_first": 2800, "n_last": 2750, "diff_mm": 0.12, "diff_deg": 0.03, "coinciden": True,
                               "marker_shift_ref_mm": 0.8, "marker_shift_ref_deg": 0.4, "marker_shift_other_mm": 0.9, "marker_shift_other_deg": 0.5},
                "mitades": {"S2_pos1": {"n": 2800, "n_first": 1400, "n_second": 1400, "diff_mm": 0.05, "diff_deg": 0.01},
                            "S2_pos3": {"n": 2700, "n_first": 1350, "n_second": 1350, "diff_mm": 0.71, "diff_deg": 0.02}},
                "mitades_peor_mm": 0.71, "mitades_peor_deg": 0.02, "distancias_max_diff_mm": 6.8, "criterio_1_cumple": False},
    }
    return results, series


def test_figures_y_diagramas() -> None:
    results, series = _results()
    figs = rp.figures_for(results, series)
    assert len(figs) >= 6 and all(png[:8] == b"\x89PNG\r\n\x1a\n" for png in figs.values())
    assert {"posicion_reposo", "plano_reposo", "coincidencia", "reduccion", "saltos", "desfase"} <= set(figs)
    d = rp.mermaid_diagrams(("numpy_pose",))
    assert len(d) >= 2 and all(code.startswith("flowchart") for code in d.values())


def test_write_report_escribe_un_html_y_no_pisa(tmp_path: Path) -> None:
    results, series = _results()
    figs = rp.figures_for(results, series)
    p = rp.write_report(results, figs, rp.mermaid_diagrams(("numpy_pose",)), tmp_path / "informe.html")
    html = p.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>") and html.count("data:image/png;base64,") == len(figs)
    assert html.count('<pre class="mermaid">') == 2 and rp.MERMAID_URL in html and "mermaid@11" in rp.MERMAID_URL
    assert "Los criterios del spec" in html and "coinciden" in html and "sin evaluar" in html and "un aviso" in html
    assert "62.50" in html and "+6.80" in html       # el diagnostico de distancias
    assert "S3_tapa_gs1" in html and "tapar" in html and "una nota" in html
    # Fase 2: la seccion de B94 con el veredicto, la repetida, las mitades y la tolerancia usada.
    assert "B94" in html and "sesgo_por_vista" in html and "20.0 ms" in html and "0.710" in html and "2800" in html
    assert html.index("B94 · Las dos camaras") < html.index("Diagnostico · Las posiciones")
    sin = dict(results)
    sin.pop("b94")
    assert "Sin veredicto de B94" in rp._section_b94(sin)
    sin_rep = {**results, "b94": {**results["b94"], "repeticion": None}}
    assert "Sin la posicion 1 repetida" in rp._section_b94(sin_rep)
    with pytest.raises(FileExistsError):
        rp.write_report(results, figs, {}, p)
    assert "| 1 |" not in rp.criteria_table(results) and "<table>" in rp.criteria_table(results)
