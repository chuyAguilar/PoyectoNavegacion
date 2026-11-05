"""Emparejar por hora las medidas de dos camaras y estimar su desfase (meta 006, fase 1).

Las SVPRO no dan hora de hardware: la de cada frame es `perf_counter` al volver
`cam.read()`, en la misma Jetson para las dos camaras (el mismo reloj; `dataset.check_segment`
comprueba el ancla). `pair_by_time` empareja cada frame de una camara con el mas cercano de
la otra dentro de una tolerancia (medio periodo, P13 a), sin repetir ninguno.
`estimate_offset` busca, con el marker en movimiento (S4), el corrimiento `delta` que
mejor superpone la trayectoria de gs2 (llevada a gs1 e interpolada) sobre la de gs1: en
reposo no hay nada que medir y lo dice.
"""
from __future__ import annotations

import numpy as np

from fusion.dataset import CameraTrack

MIN_SPEED_MM_S = 5.0


def pair_by_time(t_a: np.ndarray, t_b: np.ndarray, tolerance_s: float,
                 offset_s: float = 0.0) -> np.ndarray:
    """Indices `(M, 2)` de las parejas `(i_a, j_b)` con `|t_a[i] - (t_b[j] + offset)| <= tol`,
    la mas cercana primero y sin repetir ningun indice de ningun lado. `t_a` y `t_b` van
    crecientes. Vacio si no hay parejas."""
    ta = np.asarray(t_a, dtype=np.float64).reshape(-1)
    tb = np.asarray(t_b, dtype=np.float64).reshape(-1) + float(offset_s)
    if ta.size == 0 or tb.size == 0:
        return np.zeros((0, 2), dtype=np.int64)
    # Candidatos: para cada a, el b anterior y el siguiente.
    pos = np.searchsorted(tb, ta)
    cand_i, cand_j = [], []
    for shift in (-1, 0):
        j = pos + shift
        ok = (j >= 0) & (j < tb.size)
        cand_i.append(np.flatnonzero(ok))
        cand_j.append(j[ok])
    ci = np.concatenate(cand_i)
    cj = np.concatenate(cand_j)
    d = np.abs(ta[ci] - tb[cj])
    keep = d <= float(tolerance_s)
    ci, cj, d = ci[keep], cj[keep], d[keep]
    order = np.lexsort((cj, ci, d))          # por distancia; empates, por indice
    used_a = np.zeros(ta.size, dtype=bool)
    used_b = np.zeros(tb.size, dtype=bool)
    out = []
    for k in order:
        i, j = int(ci[k]), int(cj[k])
        if used_a[i] or used_b[j]:
            continue
        used_a[i] = used_b[j] = True
        out.append((i, j))
    if not out:
        return np.zeros((0, 2), dtype=np.int64)
    arr = np.asarray(out, dtype=np.int64)
    return arr[np.argsort(arr[:, 0])]


def _interp_rows(t_src: np.ndarray, p_src: np.ndarray, t_dst: np.ndarray,
                 max_gap_s: float | None = None) -> np.ndarray:
    """Interpolacion lineal de cada columna de `p_src(t_src)` en `t_dst` (NaN fuera del rango
    y, con `max_gap_s`, tambien donde las dos muestras vecinas de `t_src` distan mas que eso:
    un hueco sin pose no se rellena)."""
    out = np.full((t_dst.size, p_src.shape[1]), np.nan)
    inside = (t_dst >= t_src[0]) & (t_dst <= t_src[-1])
    if max_gap_s is not None and t_src.size > 1:
        j = np.clip(np.searchsorted(t_src, t_dst), 1, t_src.size - 1)
        inside &= (t_src[j] - t_src[j - 1]) <= max_gap_s
    for c in range(p_src.shape[1]):
        out[inside, c] = np.interp(t_dst[inside], t_src, p_src[:, c])
    return out


def _rigid_rms(pa: np.ndarray, pb: np.ndarray) -> float:
    """El RMS entre `pa` y `pb` tras alinear `pb` sobre `pa` con la mejor rotacion y
    traslacion (Kabsch): lo que queda es la forma de las trayectorias, no los extrinsecos."""
    ca, cb = pa.mean(axis=0), pb.mean(axis=0)
    H = (pb - cb).T @ (pa - ca)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    q = (pb - cb) @ R.T + ca
    return float(np.sqrt(np.mean(np.sum((pa - q) ** 2, axis=1))))


def estimate_offset(track_a: CameraTrack, track_b: CameraTrack, T_a_b: np.ndarray,
                    search_ms: float = 20.0, step_ms: float = 0.5,
                    min_speed_mm_s: float = MIN_SPEED_MM_S, align: str = "rigid") -> dict:
    """El desfase `delta` (ms) que hay que sumar a la hora de `b` para que su trayectoria,
    llevada al frame de `a` con `T_a_b` e interpolada, caiga sobre la de `a`: el minimo del
    RMS de la diferencia de posicion en una rejilla `[-search, search]` con paso `step`, mas
    un ajuste parabolico alrededor del minimo. Con `align="rigid"` (por defecto) a cada
    `delta` se alinea la trayectoria de `b` sobre la de `a` con la mejor rotacion y traslacion,
    para que un error de los extrinsecos (mm o grados) no mueva el minimo; con `align="none"`
    se comparan tal cual. Exige movimiento: si la velocidad media de `a` es
    < `min_speed_mm_s`, no da `delta` y lo dice."""
    va, vb = track_a.valid, track_b.valid
    ta, pa = track_a.t[va], track_a.positions[va]
    tb = track_b.t[vb]
    Tb = track_b.T_raw[vb]
    pb = np.einsum("ij,nj->ni", np.asarray(T_a_b)[:3, :3], Tb[:, :3, 3]) + np.asarray(T_a_b)[:3, 3]
    out: dict = {"n_a": int(ta.size), "n_b": int(tb.size), "search_ms": float(search_ms),
                 "step_ms": float(step_ms), "align": align, "offset_ms": None, "ok": False, "note": ""}
    if align not in ("rigid", "none"):
        raise ValueError(f"align desconocido {align!r} (rigid | none)")
    if ta.size < 10 or tb.size < 10:
        out["note"] = "menos de 10 frames con pose en una camara"
        return out
    speed = float(np.mean(np.linalg.norm(np.diff(pa, axis=0), axis=1) / np.diff(ta)))
    out["speed_mm_s"] = speed
    if speed < min_speed_mm_s:
        out["note"] = f"sin movimiento: velocidad media {speed:.1f} mm/s < {min_speed_mm_s} mm/s"
        return out
    deltas = np.arange(-search_ms, search_ms + step_ms / 2, step_ms) / 1000.0
    rms = np.full(deltas.size, np.nan)
    max_gap = 2.5 * track_b.period_s if np.isfinite(track_b.period_s) else None
    for k, d in enumerate(deltas):
        pb_at_a = _interp_rows(tb + d, pb, ta, max_gap)
        ok = np.isfinite(pb_at_a[:, 0])
        if ok.sum() < 10:
            continue
        if align == "rigid":
            rms[k] = _rigid_rms(pa[ok], pb_at_a[ok])
        else:
            rms[k] = float(np.sqrt(np.mean(np.sum((pa[ok] - pb_at_a[ok]) ** 2, axis=1))))
    if not np.isfinite(rms).any():
        out["note"] = "las trayectorias no se solapan"
        return out
    k = int(np.nanargmin(rms))
    delta = float(deltas[k])
    if 0 < k < deltas.size - 1 and np.isfinite(rms[k - 1]) and np.isfinite(rms[k + 1]):
        y0, y1, y2 = rms[k - 1], rms[k], rms[k + 1]
        den = y0 - 2 * y1 + y2
        if den > 0:
            delta = float(deltas[k] + 0.5 * (y0 - y2) / den * (deltas[1] - deltas[0]))
    rms0 = float(rms[int(np.argmin(np.abs(deltas)))])
    out.update({"offset_ms": delta * 1000.0, "rms_min_mm": float(rms[k]), "rms_at_zero_mm": rms0,
                "curve_depth_mm": rms0 - float(rms[k]),
                "curve": {"delta_ms": [float(x) for x in deltas * 1000.0],
                          "rms_mm": [float(x) for x in rms]},
                "ok": True, "note": ""})
    notas = []
    if abs(delta * 1000.0) >= search_ms - step_ms:
        notas.append("el minimo cae en el borde de la busqueda")
    if out["curve_depth_mm"] < 0.1 * float(rms[k]):
        notas.append(f"la curva es plana (de delta = 0 al minimo baja {out['curve_depth_mm']:.3f} mm sobre {rms[k]:.3f}): "
                     "el desfase no se distingue de la diferencia de forma entre las dos trayectorias")
    if notas:
        out["ok"] = False
        out["note"] = "; ".join(notas)
    return out
