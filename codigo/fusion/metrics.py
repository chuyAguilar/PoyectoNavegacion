"""Los numeros del experimento (meta 006, fase 1): coincidencia, sd en reposo, mejora
predicha, tramos tapados y saltos.

- `agreement`: el criterio 1 del spec (gs2 llevada a gs1 frente a gs1, pareja a pareja).
- `rest_sd`: la sd 3D de la posicion (raiz de la traza de la covarianza, P26 a), por eje,
  y las mismas sin la media movil de 1 s (lo que deja fuera la deriva lenta, B77).
- `predicted_reduction`: lo que la formula `Sigma_f = (Sigma_1^-1 + Sigma_2^-1)^-1` dice
  que baja la sd fusionada frente a la mejor camara.
- `occlusion_events` y `jumps`: los tramos sin deteccion de la camara tapada (S3) y, en
  cada transicion, lo que salta la pose fusionada (media despues - media antes, y el paso
  maximo entre frames seguidos cerca de la transicion).
"""
from __future__ import annotations

import numpy as np

from fusion.dataset import CameraTrack
from fusion.extrinsics import agreement_stats, apply_extrinsics


def agreement(tracks: dict[str, CameraTrack], T_ref_other: np.ndarray, pairs: np.ndarray,
              reference: str = "gs1", other: str = "gs2") -> dict:
    """La coincidencia entre `reference` y `other` llevada a `reference` sobre las parejas
    `(i_ref, j_other)`; pose cruda, sin filtros."""
    pairs = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
    if len(pairs) == 0:
        return {"n": 0}
    Ta = tracks[reference].T_raw[pairs[:, 0]]
    Tb = apply_extrinsics(T_ref_other, tracks[other].T_raw[pairs[:, 1]])
    return agreement_stats(Ta, Tb)


def _sd(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    return float(np.std(x, ddof=1)) if x.size > 1 else float("nan")


def _moving_average_residual(t: np.ndarray, p: np.ndarray, window_s: float) -> np.ndarray:
    """`p - media movil de ancho window_s` (en frames, a la fps media), por columna."""
    n = len(t)
    if n < 3 or t[-1] <= t[0]:
        return p - p.mean(axis=0)
    fs = (n - 1) / (t[-1] - t[0])
    w = int(min(max(2, round(fs * window_s)), n))
    kernel = np.ones(w) / w
    out = np.empty((n - w + 1, p.shape[1]))
    for c in range(p.shape[1]):
        out[:, c] = p[(w - 1) // 2:(w - 1) // 2 + n - w + 1, c] - np.convolve(p[:, c], kernel, mode="valid")
    return out


def rest_sd(positions: np.ndarray, t: np.ndarray, detrend_window_s: float = 1.0) -> dict:
    """Con el marker quieto: `sd_3d_mm` = raiz de la suma de las varianzas de x, y, z (la raiz
    de la traza de la covarianza; no depende de como se giren los ejes), `sd_axes_mm` por eje,
    y `sd_3d_detrended_mm` / `sd_axes_detrended_mm` sobre el residuo frente a la media movil de
    `detrend_window_s`. Filas con NaN fuera."""
    p = np.asarray(positions, dtype=np.float64).reshape(-1, 3)
    t = np.asarray(t, dtype=np.float64).reshape(-1)
    ok = np.isfinite(p).all(axis=1)
    p, t = p[ok], t[ok]
    out = {"n": int(len(p)), "sd_3d_mm": float("nan"), "sd_axes_mm": [float("nan")] * 3,
           "sd_3d_detrended_mm": float("nan"), "sd_axes_detrended_mm": [float("nan")] * 3,
           "mean_mm": [float("nan")] * 3, "detrend_window_s": float(detrend_window_s)}
    if len(p) < 3:
        return out
    var = p.var(axis=0, ddof=1)
    res = _moving_average_residual(t, p, detrend_window_s)
    var_d = res.var(axis=0, ddof=1) if len(res) > 1 else np.full(3, np.nan)
    out.update({"sd_3d_mm": float(np.sqrt(var.sum())), "sd_axes_mm": [float(np.sqrt(v)) for v in var],
                "sd_3d_detrended_mm": float(np.sqrt(var_d.sum())),
                "sd_axes_detrended_mm": [float(np.sqrt(v)) for v in var_d],
                "mean_mm": [float(x) for x in p.mean(axis=0)]})
    return out


def predicted_reduction(cov_a: np.ndarray, cov_b_in_a: np.ndarray) -> dict:
    """Con las covarianzas 3x3 de la posicion de las dos camaras en el mismo frame:
    `Sigma_f = (A^-1 + B^-1)^-1`; la sd 3D (raiz de la traza) de cada una y de la fusion, la
    reduccion frente a la mejor camara (`1 - sd_f / sd_mejor`) y lo mismo por eje."""
    A = np.asarray(cov_a, dtype=np.float64).reshape(3, 3)
    B = np.asarray(cov_b_in_a, dtype=np.float64).reshape(3, 3)
    F = np.linalg.inv(np.linalg.inv(A) + np.linalg.inv(B))
    sd_a, sd_b, sd_f = (float(np.sqrt(np.trace(M))) for M in (A, B, F))
    best = "a" if sd_a <= sd_b else "b"
    sd_best = min(sd_a, sd_b)
    axes_a, axes_b, axes_f = (np.sqrt(np.diag(M)) for M in (A, B, F))
    axes_best = np.minimum(axes_a, axes_b)
    return {"sd_3d_a_mm": sd_a, "sd_3d_b_mm": sd_b, "sd_3d_fused_mm": sd_f, "best": best,
            "reduction_3d": float(1.0 - sd_f / sd_best) if sd_best > 0 else float("nan"),
            "sd_axes_a_mm": [float(x) for x in axes_a], "sd_axes_b_mm": [float(x) for x in axes_b],
            "sd_axes_fused_mm": [float(x) for x in axes_f],
            "reduction_axes": [float(1.0 - f / b) if b > 0 else float("nan") for f, b in zip(axes_f, axes_best)],
            "cov_fused": F}


def measured_reduction(sd_cameras: dict[str, float], sd_fused: float) -> dict:
    """`1 - sd_fused / min(sd de las camaras)`, con cual fue la mejor."""
    best = min(sd_cameras, key=lambda c: sd_cameras[c])
    sd_best = sd_cameras[best]
    return {"best": best, "sd_best_mm": float(sd_best), "sd_fused_mm": float(sd_fused),
            "reduction": float(1.0 - sd_fused / sd_best) if sd_best > 0 else float("nan")}


def occlusion_events(track: CameraTrack, min_gap_s: float = 1.0) -> list[tuple[float, float]]:
    """Los tramos sin deteccion de `track` que duran al menos `min_gap_s`: `(t_ultimo_visto,
    t_primero_visto_despues)`. Un hueco de frames (sin muestras) cuenta tambien."""
    t, seen = track.t, track.detected
    if len(t) < 2:
        return []
    idx = np.flatnonzero(seen)
    if idx.size < 2:
        return []
    out = []
    for a, b in zip(idx[:-1], idx[1:]):
        if t[b] - t[a] >= min_gap_s:
            out.append((float(t[a]), float(t[b])))
    return out


def jumps(fused_t: np.ndarray, fused_p: np.ndarray, events: list[tuple[float, float]],
          window_s: float = 0.25, step_window_s: float = 1.0) -> dict:
    """Por cada transicion (tapar = inicio del tramo, destapar = fin): `|media de la posicion
    fusionada en los window_s despues - media en los window_s antes|` (mm) y el paso maximo
    entre frames seguidos en +-step_window_s. Ademas `fraction_with_pose`: la fraccion de
    instantes de la linea fusionada con pose (NaN en `fused_p` cuenta como sin pose)."""
    t = np.asarray(fused_t, dtype=np.float64).reshape(-1)
    p = np.asarray(fused_p, dtype=np.float64).reshape(-1, 3)
    ok = np.isfinite(p).all(axis=1)
    out: dict = {"fraction_with_pose": float(ok.mean()) if ok.size else float("nan"),
                 "n": int(ok.size), "transitions": []}
    tv, pv = t[ok], p[ok]
    for k, (t_cover, t_uncover) in enumerate(events):
        for kind, tc in (("tapar", t_cover), ("destapar", t_uncover)):
            before = (tv >= tc - window_s) & (tv < tc)
            after = (tv > tc) & (tv <= tc + window_s)
            near = (tv >= tc - step_window_s) & (tv <= tc + step_window_s)
            row = {"event": k, "kind": kind, "t": float(tc), "n_before": int(before.sum()),
                   "n_after": int(after.sum()), "jump_mm": float("nan"), "max_step_mm": float("nan")}
            if before.any() and after.any():
                row["jump_mm"] = float(np.linalg.norm(pv[after].mean(axis=0) - pv[before].mean(axis=0)))
            if near.sum() >= 2:
                row["max_step_mm"] = float(np.max(np.linalg.norm(np.diff(pv[near], axis=0), axis=1)))
            out["transitions"].append(row)
    vals = [r["jump_mm"] for r in out["transitions"] if np.isfinite(r["jump_mm"])]
    out["max_jump_mm"] = float(max(vals)) if vals else float("nan")
    steps = [r["max_step_mm"] for r in out["transitions"] if np.isfinite(r["max_step_mm"])]
    out["max_step_mm"] = float(max(steps)) if steps else float("nan")
    return out


__all__ = ["agreement", "rest_sd", "predicted_reduction", "measured_reduction",
           "occlusion_events", "jumps"]
