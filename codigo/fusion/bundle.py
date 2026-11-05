"""Los extrinsecos por Marker0 como un ajuste conjunto (meta 006, fase 1, parte A; P12 b).

La formula por posicion del plan (`extrinsics.from_marker_positions`: `T_gs1<-gs2 =
mean(T_gs1<-M) . mean(T_gs2<-M)^-1`) hereda tal cual el error de orientacion de la pose de
un marker visto por una sola camara: en la grabacion del 2026-11-05 dio una dispersion de
17.7 mm / 2.7 grados entre las 5 posiciones. Aqui se ajustan a la vez `T_gs1<-gs2` y la
pose del marker en cada posicion (`X_p = T_gs1<-M_p`) para que las esquinas medias de las
dos camaras reproyecten bien (Gauss-Newton con amortiguacion, jacobianas analiticas por la
derecha de `fusion.geometry`). Sobran 16P - 6P - 6 ecuaciones: el residuo que queda dice si
las dos vistas son compatibles con un marker rigido y los intrinsecos (si no, o una camara
se movio entre posiciones o sus intrinsecos no valen para esa zona de la imagen).

Las derivadas: `T_gs2<-M = T12^-1 X_p`; una perturbacion por la derecha de `X_p` lo es
tambien de `T_gs2<-M`; una de `T12` (`T12 exp(xi)`) entra por la izquierda,
`exp(-xi) T12^-1 X_p = T' exp(-Ad_{T'^-1} xi)`, asi que `dr/dxi = J(T') . (-Ad(T'^-1))`.
"""
from __future__ import annotations

import numpy as np

from fusion import geometry as g

MAX_ITERS = 50


def _residuals(T12: np.ndarray, Xs: list[np.ndarray], obs: list[dict], size_mm: float, K: dict, dist: dict,
               sigma: dict, cams: tuple[str, str]) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """`(r, J, detalle)`: residuos blanqueados, jacobiana (16P x (6 + 6P)) con T12 primero, y
    por posicion el RMS en px (sin pesar) de cada camara."""
    ref, other = cams
    P = len(Xs)
    r = np.zeros(16 * P)
    J = np.zeros((16 * P, 6 + 6 * P))
    T12i = g.inv(T12)
    detalle = []
    for p, X in enumerate(Xs):
        z1 = np.asarray(obs[p][ref], dtype=np.float64).reshape(8)
        z2 = np.asarray(obs[p][other], dtype=np.float64).reshape(8)
        p1, J1 = g._project(X, size_mm, K[ref], dist[ref], True)
        Tp = T12i @ X
        p2, J2 = g._project(Tp, size_mm, K[other], dist[other], True)
        w1, w2 = 1.0 / sigma[ref], 1.0 / sigma[other]
        a = 16 * p
        r[a:a + 8] = (p1 - z1) * w1
        r[a + 8:a + 16] = (p2 - z2) * w2
        J[a:a + 8, 6 + 6 * p:12 + 6 * p] = J1 * w1
        J[a + 8:a + 16, 6 + 6 * p:12 + 6 * p] = J2 * w2
        J[a + 8:a + 16, 0:6] = -(J2 @ g.adjoint(g.inv(Tp))) * w2
        detalle.append({ref: float(np.sqrt(np.mean((p1 - z1) ** 2))), other: float(np.sqrt(np.mean((p2 - z2) ** 2)))})
    return r, J, detalle


def fit_extrinsics_bundle(obs: list[dict], size_mm: float, K: dict, dist: dict, sigma_px: dict,
                          T12_init: np.ndarray, X_init: list[np.ndarray],
                          cams: tuple[str, str] = ("gs1", "gs2"), tol: float = 1e-10) -> dict:
    """`obs[p] = {cam: esquinas 4x2}` (las medias de la posicion p), `K[cam]`, `dist[cam]`,
    `sigma_px[cam]`. Devuelve `T_ref_other`, `poses` (X_p), `cov_T12` (6x6, por la derecha),
    `rms_px` (total, sin pesar), `rms_por_posicion` (por camara), `iteraciones`, `angle_deg`."""
    if len(obs) < 1 or len(obs) != len(X_init):
        raise ValueError("fit_extrinsics_bundle: hacen falta P >= 1 posiciones con su pose inicial")
    T12 = np.asarray(T12_init, dtype=np.float64).reshape(4, 4).copy()
    Xs = [np.asarray(X, dtype=np.float64).reshape(4, 4).copy() for X in X_init]
    r, J, det = _residuals(T12, Xs, obs, size_mm, K, dist, sigma_px, cams)
    cost = float(r @ r)
    lam = 1e-6
    it = 0
    for it in range(1, MAX_ITERS + 1):
        H = J.T @ J
        gvec = J.T @ r
        delta = -g.spd_solve(H + lam * np.diag(np.diag(H)), gvec)
        if float(delta @ delta) < tol ** 2:
            break
        T12_new = T12 @ g.exp_se3(delta[:6])
        Xs_new = [X @ g.exp_se3(delta[6 + 6 * p:12 + 6 * p]) for p, X in enumerate(Xs)]
        r_new, J_new, det_new = _residuals(T12_new, Xs_new, obs, size_mm, K, dist, sigma_px, cams)
        cost_new = float(r_new @ r_new)
        if cost_new <= cost * (1.0 + 1e-12):
            converged = cost - cost_new <= 1e-12 * max(cost, 1e-300)
            T12, Xs, r, J, det, cost = T12_new, Xs_new, r_new, J_new, det_new, cost_new
            lam = max(lam / 10.0, 1e-12)
            if converged:
                break
        else:
            lam = min(lam * 10.0, 1e6)
    H = J.T @ J
    cov = g.spd_inv(H)[:6, :6] if len(obs) >= 1 else np.full((6, 6), np.nan)
    sin_peso = []
    for p in range(len(obs)):
        sin_peso += [det[p][cams[0]] ** 2, det[p][cams[1]] ** 2]
    return {"T_ref_other": T12, "poses": Xs, "cov_T12": cov, "rms_px": float(np.sqrt(np.mean(sin_peso))),
            "rms_por_posicion": det, "iteraciones": it, "cost": cost,
            "angle_deg": float(np.degrees(np.arccos(np.clip(T12[2, 2], -1.0, 1.0)))),
            "n_positions": len(obs)}


def fit_extrinsics_bundle_multistart(obs: list[dict], size_mm: float, K: dict, dist: dict, sigma_px: dict,
                                     T12_init: np.ndarray, X_inits: list[list[np.ndarray]],
                                     cams: tuple[str, str] = ("gs1", "gs2"), max_combinations: int = 64) -> dict:
    """Como `fit_extrinsics_bundle`, probando todas las combinaciones de poses iniciales por
    posicion (`X_inits[p]` = las soluciones de IPPE de esa posicion: la ambiguedad planar da
    2^P minimos locales) y quedandose con la de menor coste. Anade `combinaciones` y
    `coste_por_combinacion`."""
    import itertools
    opciones = [list(x) for x in X_inits]
    combos = list(itertools.product(*[range(len(o)) for o in opciones]))
    if len(combos) > max_combinations:
        raise ValueError(f"demasiadas combinaciones ({len(combos)} > {max_combinations})")
    mejor = None
    costes = []
    for c in combos:
        f = fit_extrinsics_bundle(obs, size_mm, K, dist, sigma_px, T12_init, [opciones[p][k] for p, k in enumerate(c)], cams)
        costes.append(f["cost"])
        if mejor is None or f["cost"] < mejor["cost"]:
            mejor = f
            mejor["combinacion"] = list(c)
    assert mejor is not None
    mejor["combinaciones"] = len(combos)
    mejor["coste_por_combinacion"] = costes
    return mejor


def mean_corners(corners: np.ndarray) -> np.ndarray:
    """La media de N esquinas (N, 4, 2) con NaN fuera."""
    c = np.asarray(corners, dtype=np.float64).reshape(-1, 4, 2)
    ok = np.isfinite(c).all(axis=(1, 2))
    if not ok.any():
        raise ValueError("mean_corners: ninguna esquina valida")
    return c[ok].mean(axis=0)


__all__ = ["fit_extrinsics_bundle", "fit_extrinsics_bundle_multistart", "mean_corners"]
