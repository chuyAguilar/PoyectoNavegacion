"""El informe HTML del experimento (meta 006, fase 1): un solo archivo con la tabla de
criterios, las tablas de cada bloque, las graficas (PNG de matplotlib embebido en base64)
y los diagramas Mermaid (por la CDN de jsdelivr, `mermaid@11`, como la pagina
`como-funciona-tracking.html` de la meta 007: sin Internet, el texto del diagrama se ve
igual dentro de su `<pre>`). `write_report` no pisa un informe que exista. Desde la fase 2,
la seccion de B94 (`_section_b94`): el veredicto, la posicion 1 repetida y las mitades.

Context7 (2026-11-05): matplotlib `/matplotlib/matplotlib` (`Figure` + `FigureCanvasAgg` sin
pyplot, `fig.savefig(buffer, format="png")`); Mermaid `/mermaid-js/mermaid` (plan: `<pre
class="mermaid">` + `import mermaid from '...mermaid@11/dist/mermaid.esm.min.mjs';
mermaid.initialize({ startOnLoad: true })`). Instalado: matplotlib 3.10.9.
"""
from __future__ import annotations

import base64
import html
import io
import math
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
COLORS = {"gs1": "#1f77b4", "gs2": "#ff7f0e", "numpy_pose": "#2ca02c", "numpy_reproj": "#9467bd",
          "gtsam_pose": "#8c564b", "gtsam_reproj": "#e377c2", "gtsam_smoother": "#17becf"}


# ---------------------------------------------------------------------------
# Graficas
# ---------------------------------------------------------------------------

def _png(fig: Figure) -> bytes:
    canvas = FigureCanvasAgg(fig)
    buf = io.BytesIO()
    canvas.print_png(buf)
    return buf.getvalue()


def _fig(w: float = 9.0, h: float = 5.0) -> Figure:
    return Figure(figsize=(w, h), dpi=110, layout="constrained")


def _centered(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    ok = np.isfinite(p).all(axis=1)
    out = np.full_like(p, np.nan)
    if ok.any():
        out[ok] = p[ok] - p[ok].mean(axis=0)
    return out


def fig_positions(series: dict, segment: str) -> bytes:
    """La posicion (menos su media) de cada camara y de la fusion a lo largo del tiempo, por eje."""
    fig = _fig(10, 6.5)
    axes = fig.subplots(3, 1, sharex=True)
    s = series[segment]
    t0 = s["t"][0]
    for name, p in s["positions"].items():
        c = _centered(p)
        for k, ax in enumerate(axes):
            ax.plot(s["t"] - t0, c[:, k], lw=0.6, color=COLORS.get(name, None), label=name)
    for k, ax in enumerate(axes):
        ax.set_ylabel(f"{'xyz'[k]} − media (mm)")
        ax.grid(alpha=0.3)
    axes[0].legend(loc="upper right", ncol=4, fontsize=8)
    axes[-1].set_xlabel("t (s)")
    fig.suptitle(f"{segment}: posicion de Marker0 en el frame de gs1, cruda (sin 1-Euro) y fusionada por instante")
    return _png(fig)


def _ellipse(ax, p: np.ndarray, color: str, label: str) -> None:
    ok = np.isfinite(p).all(axis=1)
    q = p[ok] - p[ok].mean(axis=0)
    if len(q) < 3:
        return
    ax.scatter(q[:, 0], q[:, 1], s=2, alpha=0.35, color=color, label=label)
    C = np.cov(q.T)
    vals, vecs = np.linalg.eigh(C)
    ang = math.degrees(math.atan2(vecs[1, 1], vecs[0, 1]))
    e = Ellipse((0, 0), 2 * 2 * math.sqrt(max(vals[1], 0)), 2 * 2 * math.sqrt(max(vals[0], 0)), angle=ang,
                fill=False, color=color, lw=1.5)
    ax.add_patch(e)


def fig_plane(series: dict, segment: str) -> bytes:
    """La dispersion en el plano x-z de gs1 (el de las dos camaras) con la elipse de 2 sigma."""
    fig = _fig(7.5, 7)
    ax = fig.subplots()
    s = series[segment]
    for name, p in s["positions"].items():
        _ellipse(ax, p[:, [0, 2]], COLORS.get(name, "k"), name)
    ax.set_xlabel("x − media (mm)")
    ax.set_ylabel("z − media (mm)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, markerscale=4)
    fig.suptitle(f"{segment}: dispersion en el plano x–z del frame de gs1 (elipses de 2 sigma)")
    return _png(fig)


def fig_agreement(results: dict) -> bytes:
    """La coincidencia por posicion (validacion cruzada) frente a los umbrales 0.5 mm y 0.2 grados."""
    rows = results.get("criterio_1", {}).get("por_posicion", [])
    fig = _fig(9, 4.5)
    ax = fig.subplots()
    ax2 = ax.twinx()
    names = [r["segmento"] for r in rows]
    mm = [r["mean_mm"] for r in rows]
    deg = [r["mean_deg"] for r in rows]
    x = np.arange(len(rows))
    ax.bar(x - 0.2, mm, width=0.4, color="#1f77b4", label="|Δt| medio (mm)")
    ax2.bar(x + 0.2, deg, width=0.4, color="#ff7f0e", label="ángulo medio (°)")
    ax.axhline(0.5, color="#1f77b4", ls="--", lw=1)
    ax2.axhline(0.2, color="#ff7f0e", ls="--", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20)
    ax.set_ylabel("mm")
    ax2.set_ylabel("grados")
    ax.grid(alpha=0.3, axis="y")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
    fig.suptitle("Criterio 1: gs2 llevada a gs1 frente a gs1, con los extrinsecos de las otras posiciones")
    return _png(fig)


def fig_reduction(results: dict) -> bytes:
    """La reduccion predicha frente a la medida por segmento y motor."""
    rows = results.get("criterio_2", {}).get("por_segmento", [])
    fig = _fig(10, 4.8)
    ax = fig.subplots()
    names = [r["segmento"] for r in rows]
    x = np.arange(len(rows))
    engines = [e for e in COLORS if e.startswith(("numpy", "gtsam")) and any(e in r["motores"] for r in rows)]
    n = len(engines) + 1
    w = 0.8 / n
    ax.bar(x - 0.4 + w / 2, [100 * r["predicha"]["reduction_3d"] for r in rows], width=w, color="#7f7f7f",
           label="predicha (jacobiana)")
    for k, e in enumerate(engines):
        vals = [100 * r["motores"][e]["reduction"] if e in r["motores"] else np.nan for r in rows]
        ax.bar(x - 0.4 + w * (k + 1.5), vals, width=w, color=COLORS[e], label=f"medida · {e}")
    ax.axhline(30, color="k", ls="--", lw=1, label="umbral 30 %")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20)
    ax.set_ylabel("reduccion de la sd 3D (%)")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)
    fig.suptitle("Criterio 2: cuanto baja la sd 3D fusionada frente a la mejor camara cruda")
    return _png(fig)


def fig_occlusion(series: dict, results: dict) -> bytes:
    """Los saltos de S3: la posicion fusionada alrededor de tapar y destapar."""
    segs = [r["segmento"] for r in results.get("criterio_3", {}).get("por_segmento", [])]
    fig = _fig(10, 3.2 * max(1, len(segs)))
    axes = np.atleast_1d(fig.subplots(max(1, len(segs)), 1, squeeze=False))[:, 0]
    for ax, seg in zip(axes, segs):
        s = series.get(seg)
        if s is None:
            continue
        t0 = s["t"][0]
        for name, p in s["positions"].items():
            c = _centered(p)
            ax.plot(s["t"] - t0, c[:, 2], lw=0.6, color=COLORS.get(name, None), label=f"{name} z")
        for e in s.get("events", []):
            ax.axvline(e[0] - t0, color="r", ls="--", lw=1)
            ax.axvline(e[1] - t0, color="g", ls="--", lw=1)
        ax.set_title(f"{seg}: z − media; rojo = tapar, verde = destapar", fontsize=10)
        ax.set_ylabel("mm")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, ncol=4, loc="upper right")
    axes[-1].set_xlabel("t (s)")
    fig.suptitle("Criterio 3 (por instante): la fusion al tapar y destapar una camara")
    return _png(fig)


def fig_offset(results: dict) -> bytes:
    """La curva del desfase: RMS de la diferencia de trayectorias frente a delta."""
    d = results.get("desfase", {}) or {}
    fig = _fig(8, 4.2)
    ax = fig.subplots()
    curve = d.get("curve")
    if curve:
        ax.plot(curve["delta_ms"], curve["rms_mm"], lw=1.2)
        if d.get("offset_ms") is not None:
            ax.axvline(d["offset_ms"], color="r", ls="--", lw=1, label=f"δ = {d['offset_ms']:.2f} ms")
            ax.legend(fontsize=8)
        ax.set_xlabel("δ sumado a la hora de gs2 (ms)")
        ax.set_ylabel("RMS |p_gs1 − p_gs2→gs1| (mm)")
    else:
        ax.text(0.5, 0.5, d.get("note") or "sin S4", ha="center", va="center", transform=ax.transAxes)
    ax.grid(alpha=0.3)
    fig.suptitle("Desfase entre camaras (S4, con el marker en movimiento)" + (" — informativo" if d.get("informativo") else ""))
    return _png(fig)


def figures_for(results: dict, series: dict) -> dict[str, bytes]:
    """Las graficas del informe, en PNG; `series` trae las posiciones por segmento
    (`run_experiment` lo devuelve en `series`)."""
    figs: dict[str, bytes] = {}
    s1 = results.get("segmento_reposo")
    if s1 and s1 in series:
        figs["posicion_reposo"] = fig_positions(series, s1)
        figs["plano_reposo"] = fig_plane(series, s1)
    if results.get("criterio_1", {}).get("por_posicion"):
        figs["coincidencia"] = fig_agreement(results)
    if results.get("criterio_2", {}).get("por_segmento"):
        figs["reduccion"] = fig_reduction(results)
    if results.get("criterio_3", {}).get("por_segmento"):
        figs["saltos"] = fig_occlusion(series, results)
    figs["desfase"] = fig_offset(results)
    return figs


# ---------------------------------------------------------------------------
# Diagramas
# ---------------------------------------------------------------------------

def mermaid_diagrams(engines: tuple[str, ...]) -> dict[str, str]:
    camino = """flowchart LR
    subgraph J["Jetson (grabacion, tracker --record)"]
        A1["gs1.npz<br/>esquinas + hora + pose enviada"]
        A2["gs2.npz"]
    end
    subgraph PC["PC (.venv, fusion/)"]
        D["dataset<br/>IPPE_SQUARE (2 soluciones), comprobacion"]
        P["pairing<br/>medio periodo"]
        E["extrinsics<br/>T_gs1<-gs2 por Marker0, leave-one-out"]
        F["geometry<br/>fuse_poses · joint_pnp"]
        M["metrics<br/>sd 3D, saltos, delta"]
        R["report<br/>informe.html + resultados.json"]
    end
    A1 --> D
    A2 --> D
    D --> P --> E --> F --> M --> R"""
    grafo = """flowchart LR
    Z1(["Z_gs1 = T_gs1<-M<br/>Sigma_1 = sigma_1^2 (J^T J)^-1"]) -->|"factor de pose"| X["X_k = T_gs1<-M"]
    Z2(["Z_gs2 = T_gs1<-gs2 · T_gs2<-M<br/>Sigma_2 (sin cambiar: por la derecha)"]) -->|"factor de pose"| X
    C1(["esquinas gs1 (8 px)"]) -.->|"factor de reproyeccion (joint_pnp)"| X
    C2(["esquinas gs2 (8 px)"]) -.->|"factor de reproyeccion (joint_pnp)"| X
    X --> S["sd 3D en reposo<br/>frente a la mejor camara"]"""
    return {"camino_de_los_datos": camino, "grafo_por_instante": grafo}


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _fmt(v, nd: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        if not math.isfinite(float(v)):
            return "—"
        a = abs(float(v))
        if a != 0 and (a < 1e-3 or a >= 1e5):
            return f"{float(v):.3g}"
        return f"{float(v):.{nd}f}"
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x, nd) for x in v)
    return html.escape(str(v))


def _table(headers: list[str], rows: list[list], classes: list[str] | None = None) -> str:
    out = ["<table>", "<thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr></thead>", "<tbody>"]
    for k, r in enumerate(rows):
        cls = f' class="{classes[k]}"' if classes and classes[k] else ""
        out.append(f"<tr{cls}>" + "".join(f"<td>{c if isinstance(c, str) and c.startswith('<') else _fmt(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def _status_class(status: str) -> str:
    return {"cumple": "ok", "no cumple": "bad", "informativo": "info", "sin evaluar": "na"}.get(status, "")


def criteria_table(results: dict) -> str:
    rows, classes = [], []
    for c in results.get("criterios", []):
        rows.append([c["id"], c["nombre"], _fmt(c.get("valor")), c.get("umbral", "—"), c.get("estado", "—"), c.get("nota", "")])
        classes.append(_status_class(c.get("estado", "")))
    return _table(["#", "criterio", "obtenido", "umbral", "estado", "nota"], rows, classes)


def _matrix_html(M) -> str:
    M = np.asarray(M, dtype=np.float64).reshape(4, 4)
    return "<pre>" + "\n".join("  ".join(f"{v:12.6f}" for v in fila) for fila in M) + "</pre>"


def _section_checks(results: dict) -> str:
    rows, classes = [], []
    for seg, ch in results.get("comprobacion", {}).items():
        fr = ch.get("fraction_with_pose", {})
        rows.append([seg, ch.get("ok"), _fmt(ch.get("anchor_diff_ms"), 3), _fmt(ch.get("overlap_s"), 1),
                     _fmt(ch.get("expected_s"), 0),
                     " / ".join(f"{c} {100 * v:.1f} %" for c, v in fr.items()),
                     " / ".join(f"{c} {'sí' if v else 'no'}" for c, v in ch.get("calibration_ok", {}).items()),
                     " / ".join(f"{c} {v:.1e}" for c, v in ch.get("rotation_max_diff_deg", {}).items()),
                     "; ".join(ch.get("reasons", [])) or "—"])
        classes.append("ok" if ch.get("ok") else "bad")
    return _table(["segmento", "ok", "|Δ ancla| ms", "solape s", "esperado s", "pose", "calibración", "rot. rehecha − enviada (°)", "motivos"], rows, classes)


def _section_extrinsics(results: dict) -> str:
    e = results.get("extrinsecos") or {}
    if not e:
        return "<p>Sin extrínsecos (ninguna posición usable).</p>"
    out = [f"<p>T<sub>gs1←gs2</sub> por Marker0 sobre {e.get('n_positions')} posiciones ({', '.join(e.get('segmentos', []))}); "
           f"ángulo entre ejes ópticos θ = <b>{_fmt(e.get('angle_deg'), 2)}°</b>; distancia entre cámaras {_fmt(e.get('baseline_mm'), 1)} mm; "
           f"dispersión entre posiciones {_fmt(e.get('spread_mm'), 3)} mm / {_fmt(e.get('spread_deg'), 4)}°.</p>",
           _matrix_html(e["T_ref_other"])]
    if e.get("aviso_angulo"):
        out.append(f"<p class=\"bad\">{html.escape(e['aviso_angulo'])}</p>")
    return "\n".join(out)


def _section_consistency(results: dict) -> str:
    c = results.get("consistencia") or {}
    if not c or not c.get("segmentos"):
        return "<p>Sin posiciones.</p>"
    out = []
    b = c.get("bundle")
    if b:
        out.append(f"<p><b>Ajuste conjunto</b> (T<sub>gs1←gs2</sub> + la pose del marker en cada posicion, sobre las esquinas medias; "
                   f"{b['combinaciones']} combinaciones de la ambiguedad de IPPE probadas): RMS <b>{_fmt(b['rms_px'])} px</b>, "
                   f"θ = {_fmt(b['angle_deg'], 2)}°, {b['iteraciones']} iteraciones; cada vista sola ajusta a ≤ {_fmt(c.get('vista_unica_max_rms_px'))} px. "
                   f"Si el conjunto no cabe y cada vista si, o una camara se movio entre posiciones o la pose de un marker solo tiene un error que cambia con la vista.</p>")
        out.append(_matrix_html(b["T_ref_other"]))
        rows = [[s, _fmt(d.get("gs1")), _fmt(d.get("gs2")), _fmt(c["vista_unica"][s]["gs1"]["rms_px"]), _fmt(c["vista_unica"][s]["gs2"]["rms_px"])]
                for s, d in zip(c["segmentos"], b["rms_por_posicion"])]
        out.append(_table(["posicion", "conjunto gs1 (px)", "conjunto gs2 (px)", "vista sola gs1 (px)", "vista sola gs2 (px)"], rows))
        rows = [[r["segmento"], _fmt(r["rms_px"]), _fmt(r["angle_deg"], 2), _fmt(r["mean_mm"]), _fmt(r["mean_deg"]), _fmt(r["mean_dxyz_mm"])] for r in c.get("loo", [])]
        out.append("<p>Dejando una posicion fuera (ajuste conjunto sobre las demas) y la coincidencia en ella:</p>")
        out.append(_table(["posicion fuera", "RMS del ajuste (px)", "θ (°)", "|Δt| medio mm", "ángulo medio °", "Δxyz medio mm"], rows))
    rows = [[d["a"], d["b"], _fmt(d["gs1"], 2), _fmt(d["gs2"], 2), f"{d['diff_mm']:+.2f}"] for d in c.get("distancias", [])]
    classes = ["bad" if abs(d["diff_mm"]) > 1.0 else "ok" for d in c.get("distancias", [])]
    out.append("<p><b>Distancias entre los centros del marker de cada par de posiciones</b>, medidas por cada camara. No dependen de los extrinsecos: "
               "con las camaras quietas y los intrinsecos bien, tendrian que coincidir al nivel del ruido (decimas de mm).</p>")
    out.append(_table(["posicion a", "posicion b", "gs1 (mm)", "gs2 (mm)", "gs1 − gs2"], rows, classes))
    return "\n".join(out)


def _section_agreement(results: dict) -> str:
    c1 = results.get("criterio_1") or {}
    rows = [[r["segmento"], r["n"], _fmt(r["mean_mm"]), _fmt(r["sd_mm"]), _fmt(r["max_mm"]), _fmt(r["mean_deg"]), _fmt(r["sd_deg"]),
             _fmt(r["mean_dxyz_mm"]), _fmt(r.get("bias_mm"))] for r in c1.get("por_posicion", [])]
    if not rows:
        return f"<p>{html.escape(c1.get('nota', 'Sin validación cruzada.'))}</p>"
    return _table(["posición", "parejas", "|Δt| medio mm", "sd mm", "máx mm", "ángulo medio °", "sd °", "Δxyz medio (gs1 − gs2→gs1) mm", "sesgo mm"], rows)


def _section_b94(results: dict) -> str:
    """El veredicto de B94 (fase 2): la posicion 1 repetida, las mitades de cada tramo y la regla."""
    b = results.get("b94") or {}
    if not b:
        return "<p>Sin veredicto de B94: este resultados.json es anterior a la fase 2 o el experimento no lo calculo.</p>"
    v = str(b.get("veredicto", "—"))
    cls = {"cumple": "ok", "se_movio": "bad", "sesgo_por_vista": "bad", "sin_decidir": "na"}.get(v, "")
    u = b.get("umbrales") or {}
    out = [f"<p>Veredicto: <b class=\"{cls}\">{html.escape(v)}</b>. {html.escape(str(b.get('motivo', '')))}</p>",
           f"<p class=\"nota\">Tolerancia del ancla de reloj usada en la comprobacion: {_fmt(results.get('tolerancia_ancla_ms'), 1)} ms. "
           f"Umbrales: extrinsecos iguales si difieren &lt; {_fmt(u.get('mm'), 1)} mm y &lt; {_fmt(u.get('deg'), 1)}°; el marker volvio a su sitio si, "
           f"visto por gs1, pos1_fin esta a ≤ {_fmt(u.get('volvio_mm'), 0)} mm y ≤ {_fmt(u.get('volvio_deg'), 0)}° de pos1.</p>"]
    r = b.get("repeticion")
    if r:
        rows = [["extrinsecos T<sub>gs1←gs2</sub> de pos1 frente a pos1_fin", r["n_first"], r["n_last"], _fmt(r["diff_mm"]), _fmt(r["diff_deg"]), r["coinciden"]],
                ["el marker, visto por gs1 (pose media)", r["n_first"], r["n_last"], _fmt(r["marker_shift_ref_mm"], 2), _fmt(r["marker_shift_ref_deg"], 2), "—"],
                ["el marker, visto por gs2 (pose media)", r["n_first"], r["n_last"], _fmt(r["marker_shift_other_mm"], 2), _fmt(r["marker_shift_other_deg"], 2), "—"]]
        out.append("<p><b>La posicion 1 al principio y al final.</b> Si los extrinsecos coinciden y el marker volvio a su sitio, nada se movio entre las camaras.</p>")
        out.append(_table(["que", "parejas pos1", "parejas pos1_fin", "Δ mm", "Δ °", "coinciden"], rows,
                          ["ok" if r["coinciden"] else "bad", "", ""]))
    else:
        out.append("<p class=\"bad\">Sin la posicion 1 repetida (S2_pos1_fin): la comparacion que separa las dos hipotesis de B94 no se pudo hacer.</p>")
    m = b.get("mitades") or {}
    if m:
        rows = [[seg, h["n"], h["n_first"], h["n_second"], _fmt(h["diff_mm"]), _fmt(h["diff_deg"])] for seg, h in m.items()]
        classes = ["ok" if (h["diff_mm"] < (u.get("mm") or 0.5) and h["diff_deg"] < (u.get("deg") or 0.2)) else "bad" for h in m.values()]
        out.append(f"<p><b>Las dos mitades de cada tramo</b> (el suelo de ruido de los extrinsecos y si algo se movio dentro del tramo): "
                   f"peor {_fmt(b.get('mitades_peor_mm'))} mm / {_fmt(b.get('mitades_peor_deg'))}°.</p>")
        out.append(_table(["tramo", "parejas", "1.ª mitad", "2.ª mitad", "Δ mm", "Δ °"], rows, classes))
    if b.get("distancias_max_diff_mm") is not None:
        out.append(f"<p class=\"nota\">Distancias entre posiciones medidas por gs1 y por gs2 (invariantes a los extrinsecos; seccion Diagnostico): "
                   f"difieren hasta {_fmt(b['distancias_max_diff_mm'], 2)} mm.</p>")
    out.append("<p class=\"nota\">La regla, en orden: «sin decidir» si falta la repetida o el marker no volvio a su sitio; «se movio» si los extrinsecos "
               "de pos1 y pos1_fin, o las dos mitades de un tramo, difieren ≥ los umbrales; «cumple» si nada se movio y el criterio 1 cumple; "
               "«sesgo por vista» si nada se movio y el criterio 1 no cumple. El veredicto es el resultado de la fase 2, no su criterio.</p>")
    return "\n".join(out)


def _section_sigma(results: dict) -> str:
    s = results.get("sigma_px") or {}
    rows = [[cam, _fmt(v.get("sigma_px"), 4), _fmt(v.get("sigma_px_detrended"), 4), ", ".join(v.get("segmentos", [])), v.get("origen", "")]
            for cam, v in s.items()]
    return _table(["cámara", "σ_px (sd cruda)", "σ_px (sin deriva)", "ajustado en", "origen"], rows)


def _section_reduction(results: dict) -> str:
    c2 = results.get("criterio_2") or {}
    rows, classes = [], []
    for r in c2.get("por_segmento", []):
        cams = r["camaras"]
        base = [r["segmento"], r["parejas"],
                " / ".join(f"{c} {cams[c]['sd_3d_mm']:.4f}" for c in cams),
                " / ".join(f"{c} {cams[c]['sd_3d_detrended_mm']:.4f}" for c in cams),
                r["mejor"], f"{100 * r['predicha']['reduction_3d']:.1f} %",
                f"{_fmt(r.get('discrepancia_gs1_gs2_mm'), 2)} mm / {_fmt(r.get('discrepancia_gs1_gs2_deg'), 2)}°"]
        for e, m in r["motores"].items():
            rows.append(base + [e, _fmt(m["sd_3d_mm"], 4), _fmt(m["sd_3d_detrended_mm"], 4),
                                f"{100 * m['reduction']:.1f} %", f"{100 * m['reduction_detrended']:.1f} %",
                                f"{100 * (r['predicha']['reduction_3d'] - m['reduction']):+.1f} pt",
                                _fmt(m.get("sd_axes_mm"), 4), _fmt(m.get("rms_px_median"), 2)])
            classes.append("ok" if m["reduction"] >= 0.30 else "bad")
    if not rows:
        return "<p>Sin segmentos de reposo usables.</p>"
    return _table(["segmento", "parejas", "sd 3D cruda (mm)", "sd 3D sin deriva (mm)", "mejor", "predicha", "gs1 vs gs2→gs1 (sesgo)",
                   "motor", "sd 3D fusionada", "sin deriva", "reducción", "reducción sin deriva", "parte común", "sd por eje fusionada",
                   "RMS px (reproj)"], rows, classes)


def _section_occlusion(results: dict) -> str:
    c3 = results.get("criterio_3") or {}
    rows, classes = [], []
    for r in c3.get("por_segmento", []):
        for e, m in r["motores"].items():
            for tr in m["transitions"]:
                rows.append([r["segmento"], r["tapada"], e, tr["kind"], _fmt(tr["t_rel_s"], 2), tr["n_before"], tr["n_after"],
                             _fmt(tr["jump_mm"], 3), _fmt(tr["max_step_mm"], 3), f"{100 * m['fraction_with_pose']:.2f} %"])
                classes.append("ok" if math.isfinite(tr["jump_mm"]) and tr["jump_mm"] <= 0.5 else "bad")
    if not rows:
        return "<p>Sin segmentos S3 usables.</p>"
    return _table(["segmento", "tapada", "motor", "transición", "t (s)", "n antes", "n después", "salto mm", "paso máx mm", "con pose"], rows, classes)


def _section_offset(results: dict) -> str:
    d = results.get("desfase") or {}
    if not d:
        return "<p>Sin S4.</p>"
    txt = (f"<p>Segmento {html.escape(str(d.get('segmento', 'S4')))}{' (informativo: no pasó la comprobación)' if d.get('informativo') else ''}: "
           f"velocidad media {_fmt(d.get('speed_mm_s'), 1)} mm/s; δ = <b>{_fmt(d.get('offset_ms'), 2)} ms</b> con la trayectoria de gs2 "
           f"alineada rigidamente sobre la de gs1 a cada δ (RMS mínimo {_fmt(d.get('rms_min_mm'), 3)} mm, en δ = 0: {_fmt(d.get('rms_at_zero_mm'), 3)} mm). "
           f"{html.escape(d.get('note') or '')}</p>")
    s = d.get("sin_alinear") or {}
    if s:
        txt += (f"<p class=\"nota\">Sin alinear (con los extrinsecos tal cual): δ = {_fmt(s.get('offset_ms'), 2)} ms, RMS mínimo {_fmt(s.get('rms_min_mm'), 2)} mm. "
                f"{html.escape(s.get('note') or '')} Un RMS de mm tras alinear dice que las dos camaras no ven la misma trayectoria: "
                f"la posicion del marker desde una camara sola cambia con su inclinacion.</p>")
    return txt


def _section_ippe(results: dict) -> str:
    rows = [[seg, cam, v["sin_deteccion"], v["varias_detecciones"], v["pose_invalida"], v["rescatables_por_la_otra_solucion"]]
            for seg, cams in (results.get("ippe_otra_solucion") or {}).items() for cam, v in cams.items()]
    return _table(["segmento", "cámara", "sin detección", "varias detecciones", "1ª solución con z ≤ 0", "rescatables con la 2ª"], rows)


def _section_timing(results: dict) -> str:
    t = results.get("tiempos") or {}
    rows = [[e, v.get("n"), _fmt(v.get("p50_ms"), 3), _fmt(v.get("p95_ms"), 3), _fmt(v.get("max_ms"), 3)] for e, v in t.get("por_motor", {}).items()]
    extra = f"<p>Total del experimento: {_fmt(t.get('total_s'), 1)} s.</p>" if t.get("total_s") is not None else ""
    return extra + (_table(["motor", "fusiones", "p50 ms", "p95 ms", "máx ms"], rows) if rows else "")


CSS = """
body { font-family: Segoe UI, Arial, sans-serif; margin: 24px auto; max-width: 1280px; color: #222; line-height: 1.4; }
h1 { font-size: 1.5em; } h2 { font-size: 1.2em; margin-top: 1.6em; border-bottom: 1px solid #ddd; }
table { border-collapse: collapse; margin: 8px 0; font-size: 0.86em; } th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left; vertical-align: top; }
th { background: #f4f6f8; } tr.ok td:nth-child(5), tr.ok td.estado { color: #0a7a2f; font-weight: 600; }
tr.ok { background: #f3fbf5; } tr.bad { background: #fdf3f3; } tr.info { background: #f6f6fb; } tr.na { color: #666; }
p.bad { color: #a40000; font-weight: 600; } b.ok { color: #0a7a2f; } b.bad { color: #a40000; } b.na { color: #666; }
pre { background: #f8f8f8; border: 1px solid #eee; padding: 8px; overflow-x: auto; font-size: 0.85em; }
pre.mermaid { background: #fff; border: 1px solid #eaeef2; border-radius: 8px; padding: 10px; }
img { max-width: 100%; border: 1px solid #eee; margin: 6px 0; }
.nota { color: #555; font-size: 0.9em; }
"""


def write_report(results: dict, figures: dict[str, bytes], mermaid: dict[str, str], path: Path) -> Path:
    """Escribe el informe en `path` (no pisa). `results` es el de `run_experiment` (sin `series`)."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"el informe ya existe, no se pisa: {path}")
    titulo = results.get("titulo", "Meta 006 · Fase 1 · El experimento fuera de linea de las dos camaras")
    partes = [f"<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>{html.escape(titulo)}</title>",
              f"<style>{CSS}</style></head><body>", f"<h1>{html.escape(titulo)}</h1>"]
    if results.get("subtitulo"):
        partes.append(f"<p class=\"nota\">{html.escape(results['subtitulo'])}</p>")
    for aviso in results.get("avisos", []):
        partes.append(f"<p class=\"bad\">{html.escape(aviso)}</p>")
    partes += ["<h2>Los criterios del spec</h2>", criteria_table(results),
               "<p class=\"nota\">Los numeros de los criterios son el resultado, no el criterio de la fase: la fase cierra aunque alguno no cumpla.</p>",
               "<h2>La comprobacion de la grabacion</h2>", _section_checks(results),
               "<h2>Los extrinsecos por Marker0</h2>", _section_extrinsics(results),
               "<h2>Criterio 1 · Las camaras coinciden (validacion cruzada)</h2>", _section_agreement(results),
               "<h2>B94 · Las dos camaras no ven el Marker0 en el mismo sitio: el veredicto</h2>", _section_b94(results),
               "<h2>Diagnostico · Las posiciones caben en dos camaras rigidas?</h2>", _section_consistency(results),
               "<h2>σ_px por camara</h2>", _section_sigma(results),
               "<h2>Criterio 2 · La fusion baja el jitter (por instante)</h2>", _section_reduction(results),
               "<h2>Criterio 3 · Tapar una camara (por instante, sin factor de movimiento)</h2>", _section_occlusion(results),
               "<h2>El desfase δ entre camaras</h2>", _section_offset(results),
               "<h2>La otra solucion de IPPE</h2>", _section_ippe(results),
               "<h2>Tiempos</h2>", _section_timing(results),
               "<h2>Graficas</h2>"]
    for name, png in figures.items():
        b64 = base64.b64encode(png).decode("ascii")
        partes.append(f"<h3>{html.escape(name)}</h3><img alt=\"{html.escape(name)}\" src=\"data:image/png;base64,{b64}\">")
    partes.append("<h2>Diagramas</h2>")
    for name, code in mermaid.items():
        partes.append(f"<h3>{html.escape(name)}</h3><pre class=\"mermaid\">\n{html.escape(code)}\n</pre>")
    for nota in results.get("notas", []):
        partes.append(f"<p class=\"nota\">{html.escape(nota)}</p>")
    partes.append(f"<script type=\"module\">import mermaid from \"{MERMAID_URL}\"; mermaid.initialize({{ startOnLoad: true }});</script>")
    partes.append("</body></html>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(partes), encoding="utf-8")
    return path


__all__ = ["figures_for", "mermaid_diagrams", "write_report", "criteria_table"]
