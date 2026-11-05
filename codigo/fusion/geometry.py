"""SE(3) en numpy, OpenCV y scipy para la fusion de las dos camaras (meta 006, fase 1, parte A).

Convenciones:
  - Una pose `T` (4x4, mm) lleva puntos del frame del marker al de la camara: es la
    `T_cam<-marker` que da `solvePnP` (`vision.pose.rvec_tvec_to_matrix`).
  - La tangente es `xi = [omega, rho]` (la rotacion primero, como GTSAM) y la
    perturbacion es por la derecha: `T(xi) = T . exp(xi^)`.
  - Una medida `Z` de la pose `X` con ruido es `Z = X . exp(eps)`, `eps ~ N(0, Sigma)`:
    la covarianza vive en el frame del marker, asi que llevar la medida a otro frame
    (`T_ref<-cam . Z`) no la cambia (`transport_covariance` lo deja explicito).

`pose_covariance` saca la covarianza de una pose por la jacobiana de la reproyeccion de las
cuatro esquinas respecto a `xi` (analitica: la de `cv2.projectPoints` respecto a `rvec` y
`tvec`, encadenada con la del giro por la derecha): `Sigma = sigma_px^2 (J^T J)^-1`.
`fuse_poses` hace la media ponderada de N poses en SE(3) por Gauss-Newton y `joint_pnp`
resuelve una sola pose del marker con las esquinas de varias camaras a la vez
(`scipy.optimize.least_squares`, metodo LM, con esa misma jacobiana).

Context7 (2026-11-05): OpenCV `/opencv/opencv` (`projectPoints(obj, rvec, tvec, K, dist)`
devuelve `(puntos Nx1x2, jacobiana 2N x (10 + n_dist))` con las columnas `rvec(3), tvec(3),
f(2), c(2), dist`; `Rodrigues` pasa de rvec a matriz y al reves; `solvePnP` da
`T_cam<-objeto`); SciPy `/scipy/scipy` (`least_squares(fun, x0, jac=callable, method="lm")`;
`Rotation.from_matrix(...).mean()`). Instalados: OpenCV 4.11.0, SciPy 1.17.1, numpy 1.26.4.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from vision.pose import build_object_points

_I3 = np.eye(3)
_I6 = np.eye(6)


def spd_inv(M: np.ndarray) -> np.ndarray:
    """La inversa de una matriz simetrica definida positiva por Cholesky (`scipy.linalg`):
    `np.linalg.inv` de una 6x6 tarda ~0.3 ms con el BLAS en hilos; esto, ~0.07. Si no es
    definida positiva, cae a `np.linalg.inv`."""
    M = np.asarray(M, dtype=np.float64)
    try:
        return cho_solve(cho_factor(M, check_finite=False), np.eye(M.shape[0]), check_finite=False)
    except np.linalg.LinAlgError:
        return np.linalg.inv(M)


def spd_solve(M: np.ndarray, b: np.ndarray) -> np.ndarray:
    M = np.asarray(M, dtype=np.float64)
    try:
        return cho_solve(cho_factor(M, check_finite=False), b, check_finite=False)
    except np.linalg.LinAlgError:
        return np.linalg.solve(M, b)


# ---------------------------------------------------------------------------
# Lie: hat, exp, log, inversa, adjunta
# ---------------------------------------------------------------------------

def skew(w) -> np.ndarray:
    w = np.asarray(w, dtype=np.float64).reshape(3)
    return np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])


def inv(T: np.ndarray) -> np.ndarray:
    """La inversa de una pose 4x4 (R^T, -R^T t), sin `np.linalg.inv`."""
    T = np.asarray(T, dtype=np.float64)
    R, t = T[:3, :3], T[:3, 3]
    out = np.eye(4)
    out[:3, :3] = R.T
    out[:3, 3] = -R.T @ t
    return out


def rotvec_to_matrix(omega) -> np.ndarray:
    R, _ = cv2.Rodrigues(np.asarray(omega, dtype=np.float64).reshape(3, 1))
    return R


def matrix_to_rotvec(R) -> np.ndarray:
    rvec, _ = cv2.Rodrigues(np.asarray(R, dtype=np.float64).reshape(3, 3))
    return rvec.reshape(3)


def _so3_V(omega: np.ndarray) -> np.ndarray:
    """La matriz V de exp en SE(3): rho -> traslacion."""
    th = float(np.linalg.norm(omega))
    W = skew(omega)
    if th < 1e-8:
        return _I3 + 0.5 * W + W @ W / 6.0
    a = (1.0 - np.cos(th)) / th ** 2
    b = (th - np.sin(th)) / th ** 3
    return _I3 + a * W + b * (W @ W)


def _so3_right_jacobian_inv(omega: np.ndarray) -> np.ndarray:
    """J_r^-1(omega) de SO(3): `rotvec(exp(omega^) exp(d^)) ~ omega + J_r^-1(omega) d`."""
    th = float(np.linalg.norm(omega))
    W = skew(omega)
    if th < 1e-6:
        return _I3 + 0.5 * W + W @ W / 12.0
    c = 1.0 / th ** 2 - (1.0 + np.cos(th)) / (2.0 * th * np.sin(th))
    return _I3 + 0.5 * W + c * (W @ W)


def exp_se3(xi) -> np.ndarray:
    """exp de `xi = [omega, rho]` (6,) a una pose 4x4."""
    xi = np.asarray(xi, dtype=np.float64).reshape(6)
    omega, rho = xi[:3], xi[3:]
    T = np.eye(4)
    T[:3, :3] = rotvec_to_matrix(omega)
    T[:3, 3] = _so3_V(omega) @ rho
    return T


def log_se3(T: np.ndarray) -> np.ndarray:
    """log de una pose 4x4 a `xi = [omega, rho]` (6,)."""
    T = np.asarray(T, dtype=np.float64)
    omega = matrix_to_rotvec(T[:3, :3])
    rho = np.linalg.solve(_so3_V(omega), T[:3, 3])
    return np.concatenate([omega, rho])


def adjoint(T: np.ndarray) -> np.ndarray:
    """Ad_T (6x6) para `[omega, rho]`: `T exp(xi) = exp(Ad_T xi) T`."""
    T = np.asarray(T, dtype=np.float64)
    R, t = T[:3, :3], T[:3, 3]
    A = np.zeros((6, 6))
    A[:3, :3] = R
    A[3:, 3:] = R
    A[3:, :3] = skew(t) @ R
    return A


def ad(xi) -> np.ndarray:
    """ad_xi (6x6), el corchete de Lie en forma de matriz, para `[omega, rho]`."""
    xi = np.asarray(xi, dtype=np.float64).reshape(6)
    A = np.zeros((6, 6))
    A[:3, :3] = skew(xi[:3])
    A[3:, 3:] = skew(xi[:3])
    A[3:, :3] = skew(xi[3:])
    return A


def left_jacobian_inv(xi) -> np.ndarray:
    """J_l^-1(xi) ~ I - ad/2 + ad^2/12 (serie truncada, exacta hasta el segundo orden):
    `log(exp(eps) exp(xi)) ~ xi + J_l^-1(xi) eps`."""
    A = ad(xi)
    return np.eye(6) - 0.5 * A + (A @ A) / 12.0


def angle_deg(Ra: np.ndarray, Rb: np.ndarray) -> float:
    """El angulo de Ra^T Rb por atan2 (estable cerca de 0)."""
    D = np.asarray(Ra).T @ np.asarray(Rb)
    s = 0.5 * np.linalg.norm([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]])
    c = 0.5 * (np.trace(D) - 1.0)
    return float(np.degrees(np.arctan2(s, c)))


def pose_difference(Ta: np.ndarray, Tb: np.ndarray) -> tuple[float, float]:
    """(|t_a - t_b| en mm, angulo entre R_a y R_b en grados)."""
    Ta, Tb = np.asarray(Ta), np.asarray(Tb)
    return float(np.linalg.norm(Ta[:3, 3] - Tb[:3, 3])), angle_deg(Ta[:3, :3], Tb[:3, :3])


def mean_pose(Ts: np.ndarray) -> np.ndarray:
    """La media de N poses: `Rotation.mean` de las rotaciones y la media de las traslaciones."""
    Ts = np.asarray(Ts, dtype=np.float64).reshape(-1, 4, 4)
    if len(Ts) == 0:
        raise ValueError("mean_pose: no hay poses")
    T = np.eye(4)
    T[:3, :3] = Rotation.from_matrix(Ts[:, :3, :3]).mean().as_matrix()
    T[:3, 3] = Ts[:, :3, 3].mean(axis=0)
    return T


# ---------------------------------------------------------------------------
# Reproyeccion y covarianza de una pose
# ---------------------------------------------------------------------------

def _project(T_cam_marker: np.ndarray, size_mm: float, K, dist,
             with_jacobian: bool) -> tuple[np.ndarray, np.ndarray | None]:
    """Las 4 esquinas proyectadas (8,) y, si se pide, la jacobiana (8x6) respecto a `xi` por la
    derecha de `T_cam<-marker`: `[J_rvec . J_r^-1(rvec), J_tvec . R]`."""
    T = np.asarray(T_cam_marker, dtype=np.float64)
    R, t = T[:3, :3], T[:3, 3]
    rvec = matrix_to_rotvec(R)
    pts, jac = cv2.projectPoints(build_object_points(size_mm).astype(np.float64), rvec, t.copy(),
                                 np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64))
    z = pts.reshape(8)
    if not with_jacobian:
        return z, None
    J = np.empty((8, 6))
    J[:, :3] = jac[:, 0:3] @ _so3_right_jacobian_inv(rvec)
    J[:, 3:] = jac[:, 3:6] @ R
    return z, J


def project_corners(T_cam_marker: np.ndarray, size_mm: float, K, dist) -> np.ndarray:
    """Las 4 esquinas del marker (orden de IPPE_SQUARE) proyectadas con `K` y `dist`: (4, 2) px."""
    return _project(T_cam_marker, size_mm, K, dist, False)[0].reshape(4, 2)


def reprojection_jacobian(T_cam_marker: np.ndarray, size_mm: float, K, dist) -> np.ndarray:
    """d(esquinas proyectadas, 8) / d(xi por la derecha, 6): (8, 6)."""
    return _project(T_cam_marker, size_mm, K, dist, True)[1]


def pose_covariance(T_cam_marker: np.ndarray, size_mm: float, K, dist, sigma_px: float) -> np.ndarray:
    """La covarianza 6x6 (por la derecha, `[omega, rho]`) de la pose de un marker cuadrado
    con ruido isotropo de `sigma_px` en cada esquina: `sigma^2 (J^T J)^-1`."""
    J = reprojection_jacobian(T_cam_marker, size_mm, K, dist)
    return float(sigma_px) ** 2 * spd_inv(J.T @ J)


def transport_covariance(T_ref_cam: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """La covarianza de una medida `Z` llevada a `T_ref<-cam . Z`. Con la perturbacion por
    la derecha (`Z = X exp(eps)`), `T_ref<-cam Z = (T_ref<-cam X) exp(eps)`: la misma
    `eps`, la misma covarianza. Se deja como funcion para que el experimento lo diga y la
    suite lo compruebe frente a `adjoint`."""
    np.asarray(T_ref_cam, dtype=np.float64).reshape(4, 4)
    return np.array(cov, dtype=np.float64).reshape(6, 6).copy()


def position_covariance(T_ref_marker: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """La covarianza 3x3 de la posicion del marker en el frame de referencia: `R Sigma_rho R^T`
    (la perturbacion `rho` esta en el frame del marker; el origen del marker no se mueve con
    `omega`)."""
    R = np.asarray(T_ref_marker, dtype=np.float64)[:3, :3]
    S = np.asarray(cov, dtype=np.float64)[3:, 3:]
    return R @ S @ R.T


# ---------------------------------------------------------------------------
# Fusion por instante
# ---------------------------------------------------------------------------

def fuse_poses(poses: list[np.ndarray], covs: list[np.ndarray], iters: int = 10,
               tol: float = 1e-9) -> tuple[np.ndarray, np.ndarray]:
    """La media ponderada en SE(3) de N medidas `Z_i = X exp(eps_i)`, `eps_i ~ N(0, Sigma_i)`,
    todas en el mismo frame de referencia, por Gauss-Newton con el residuo
    `r_i = log(X^-1 Z_i)` y la jacobiana `-J_l^-1(r_i)`. Para cuando `|delta| < tol`
    (rad y mm) o a las `iters`. Devuelve `(X, Sigma_X)`."""
    if not poses or len(poses) != len(covs):
        raise ValueError("fuse_poses: hacen falta N poses y N covarianzas, N >= 1")
    Zs = [np.asarray(Z, dtype=np.float64).reshape(4, 4) for Z in poses]
    Ws = [spd_inv(np.asarray(S, dtype=np.float64).reshape(6, 6)) for S in covs]
    X = Zs[0].copy()
    H = _I6.copy()
    for _ in range(max(1, int(iters))):
        H = np.zeros((6, 6))
        g = np.zeros(6)
        Xi = inv(X)
        for Z, W in zip(Zs, Ws):
            r = log_se3(Xi @ Z)
            J = -left_jacobian_inv(r)
            JW = J.T @ W
            H += JW @ J
            g += JW @ r
        delta = -spd_solve(H, g)
        X = X @ exp_se3(delta)
        if float(np.dot(delta, delta)) < tol ** 2:
            break
    return X, spd_inv(H)


def _stack_observations(observations, sigma_px):
    obs = []
    for cam, corners, K, dist, T_ref_cam in observations:
        obs.append((np.asarray(corners, dtype=np.float64).reshape(8),
                    np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64),
                    inv(T_ref_cam), 1.0 / float(sigma_px[cam])))
    return obs


def _residuals_and_jacobian(T: np.ndarray, obs, size_mm: float) -> tuple[np.ndarray, np.ndarray]:
    res, rows = [], []
    for z, K, dist, T_cam_ref, w in obs:
        # La perturbacion por la derecha de T es la misma para T_cam_ref T.
        p, J = _project(T_cam_ref @ T, size_mm, K, dist, True)
        res.append((p - z) * w)
        rows.append(J * w)
    return np.concatenate(res), np.vstack(rows)


def joint_pnp(observations: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
              size_mm: float, T0: np.ndarray, sigma_px: dict[str, float],
              solver: str = "gn", iters: int = 20, tol: float = 1e-9) -> tuple[np.ndarray, np.ndarray, float]:
    """Una sola pose `T_ref<-marker` que explica las esquinas de varias camaras a la vez.

    Cada observacion es `(camara, esquinas 4x2, K, dist, T_ref<-cam)`; `sigma_px[camara]`
    pesa sus residuos (1/sigma). Minimiza sobre `xi` con `T = T0 exp(xi)` y la jacobiana
    analitica por la derecha: con `solver="gn"`, Gauss-Newton con amortiguacion de
    Levenberg (~0.5 ms por pareja); con `solver="scipy"`, `scipy.optimize.least_squares`
    (LM), el mismo minimo (~5 ms, lo pesa el envoltorio). Devuelve `(T_ref<-marker,
    Sigma 6x6 por la derecha, RMS px sin pesar)`.
    """
    if not observations:
        raise ValueError("joint_pnp: no hay observaciones")
    obs = _stack_observations(observations, sigma_px)
    T = np.asarray(T0, dtype=np.float64).reshape(4, 4).copy()
    if solver == "scipy":
        T0c = T.copy()
        sol = least_squares(lambda x: _residuals_and_jacobian(T0c @ exp_se3(x), obs, size_mm)[0],
                            np.zeros(6),
                            jac=lambda x: _residuals_and_jacobian(T0c @ exp_se3(x), obs, size_mm)[1],
                            method="lm", xtol=1e-10, ftol=1e-10, gtol=1e-10, max_nfev=50)
        T = T0c @ exp_se3(sol.x)
    elif solver == "gn":
        lam = 1e-6
        r, J = _residuals_and_jacobian(T, obs, size_mm)
        cost = float(r @ r)
        for _ in range(max(1, int(iters))):
            H = J.T @ J
            g = J.T @ r
            delta = -spd_solve(H + lam * np.diag(np.diag(H)), g)
            if float(np.dot(delta, delta)) < tol ** 2:
                break
            T_new = T @ exp_se3(delta)
            r_new, J_new = _residuals_and_jacobian(T_new, obs, size_mm)
            cost_new = float(r_new @ r_new)
            if cost_new <= cost * (1.0 + 1e-12):
                converged = cost - cost_new <= 1e-12 * max(cost, 1e-300)
                T, r, J, cost = T_new, r_new, J_new, cost_new
                lam = max(lam / 10.0, 1e-12)
                if converged:
                    break
            else:
                lam = min(lam * 10.0, 1e6)
    else:
        raise ValueError(f"joint_pnp: solver desconocido {solver!r} (gn | scipy)")
    # Los residuos ya van blanqueados: Sigma = (J^T J)^-1 con la jacobiana por la derecha
    # en la solucion.
    r, J = _residuals_and_jacobian(T, obs, size_mm)
    cov = spd_inv(J.T @ J)
    sin_peso = np.concatenate([_project(T_cam_ref @ T, size_mm, K, dist, False)[0] - z
                               for z, K, dist, T_cam_ref, _w in obs])
    rms = float(np.sqrt(np.mean(sin_peso ** 2)))
    return T, cov, rms
