"""fusion.geometry (meta 006 · Grafo de factores optico-inercial, fase 1 · Verlo, parte A):
exp/log/inversa/adjunta de SE(3); la jacobiana analitica de la reproyeccion frente a la
numerica; la covarianza por la jacobiana frente a la empirica (Monte Carlo, 2000 muestras,
+-10 %); `transport_covariance` frente a la adjunta; `fuse_poses` exacta sin ruido
(< 1e-6 mm) y con la reduccion medida igual a la predicha (+-3 puntos); `joint_pnp` con los
dos solvers en el mismo minimo y exacto sin ruido. Sin camara: dos camaras sinteticas con
verdad conocida (K de `tests/synthetic.py`-estilo, 1280x960).
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from fusion import geometry as g
from fusion.dataset import ippe_solutions
from fusion.metrics import predicted_reduction

K = np.array([[850.0, 0.0, 640.0], [0.0, 849.0, 480.0], [0.0, 0.0, 1.0]])
DIST = np.array([0.017, 0.011, 0.0028, -0.0009, -0.107])
SIZE = 80.0
SIGMA = 0.1


def _rng() -> np.random.Generator:
    return np.random.default_rng(20261105)


def marker_pose(x: float = 20.0, y: float = 5.0, z: float = 380.0, euler=(185.0, 8.0)) -> np.ndarray:
    """T_gs1<-M: el marker de frente a gs1 (como el fisico: 185 grados en x)."""
    T = np.eye(4)
    T[:3, :3] = Rotation.from_euler("xy", list(euler), degrees=True).as_matrix()
    T[:3, 3] = [x, y, z]
    return T


def second_camera(angle_deg: float = 30.0, baseline_mm: float = 200.0) -> np.ndarray:
    """T_gs1<-gs2: gs2 desplazada `baseline` en x y girada `angle` hacia el marker."""
    T = np.eye(4)
    T[:3, :3] = Rotation.from_euler("y", -angle_deg, degrees=True).as_matrix()
    T[:3, 3] = [baseline_mm, 0.0, baseline_mm * np.tan(np.radians(angle_deg / 2))]
    return T


# ----------------------------------------------------------------------------- Lie


def test_exp_log_inversa_y_adjunta() -> None:
    rng = _rng()
    for _ in range(50):
        xi = rng.normal(0, 0.8, 6)
        xi[:3] *= 0.9 * np.pi / max(np.pi, np.linalg.norm(xi[:3]))     # |omega| < pi: el log es el principal
        xi[3:] *= 100
        assert np.allclose(g.log_se3(g.exp_se3(xi)), xi, atol=1e-9)
    T = g.exp_se3(rng.normal(0, 0.5, 6) * [1, 1, 1, 100, 100, 100])
    assert np.allclose(g.inv(T) @ T, np.eye(4), atol=1e-12)
    xi = rng.normal(0, 0.01, 6)
    assert np.allclose(T @ g.exp_se3(xi), g.exp_se3(g.adjoint(T) @ xi) @ T, atol=1e-9)
    assert np.allclose(g.exp_se3(np.zeros(6)), np.eye(4))
    assert np.allclose(g.log_se3(np.eye(4)), np.zeros(6))
    # J_l^-1: log(exp(eps) exp(xi)) ~ xi + J_l^-1(xi) eps
    xi = rng.normal(0, 0.05, 6)
    eps = rng.normal(0, 1e-4, 6)
    lhs = g.log_se3(g.exp_se3(eps) @ g.exp_se3(xi))
    assert np.allclose(lhs, xi + g.left_jacobian_inv(xi) @ eps, atol=1e-9)
    assert g.angle_deg(np.eye(3), Rotation.from_euler("z", 0.3, degrees=True).as_matrix()) == pytest.approx(0.3, abs=1e-9)
    assert g.pose_difference(marker_pose(), marker_pose(x=21.0)) == pytest.approx((1.0, 0.0), abs=1e-9)


def test_mean_pose_y_spd_inv() -> None:
    rng = _rng()
    T = marker_pose()
    Ts = np.array([T @ g.exp_se3(rng.normal(0, 1e-3, 6)) for _ in range(500)])
    M = g.mean_pose(Ts)
    assert g.pose_difference(M, T)[0] < 0.02 and g.pose_difference(M, T)[1] < 0.02
    A = np.cov(rng.normal(size=(6, 60)))
    assert np.allclose(g.spd_inv(A), np.linalg.inv(A), rtol=1e-8, atol=1e-10)
    b = rng.normal(size=6)
    assert np.allclose(g.spd_solve(A, b), np.linalg.solve(A, b))
    with pytest.raises(ValueError):
        g.mean_pose(np.zeros((0, 4, 4)))


# ----------------------------------------------------------------------------- jacobiana y covarianza


def test_jacobiana_analitica_igual_a_la_numerica() -> None:
    T = marker_pose()
    Ja = g.reprojection_jacobian(T, SIZE, K, DIST)
    Jn = np.zeros((8, 6))
    for k in range(6):
        h = 1e-6 if k < 3 else 1e-3
        d = np.zeros(6)
        d[k] = h
        mas = g.project_corners(T @ g.exp_se3(d), SIZE, K, DIST).reshape(8)
        menos = g.project_corners(T @ g.exp_se3(-d), SIZE, K, DIST).reshape(8)
        Jn[:, k] = (mas - menos) / (2 * h)
    assert np.abs(Ja - Jn).max() / np.abs(Jn).max() < 1e-7
    assert Ja.shape == (8, 6) and g.project_corners(T, SIZE, K, DIST).shape == (4, 2)


def test_covarianza_por_la_jacobiana_coincide_con_la_empirica() -> None:
    """Monte Carlo (2000 muestras) con ruido de 0.1 px: la sd empirica de cada componente
    de log(X^-1 Z) de la pose por minimos cuadrados (joint_pnp con una camara) esta a +-10 %
    de la predicha. IPPE_SQUARE (la pose del tracker) no es de minimos cuadrados y sale mas
    ruidosa: su cociente se anota (1.0-1.6)."""
    rng = _rng()
    T = marker_pose()
    cov = g.pose_covariance(T, SIZE, K, DIST, SIGMA)
    z0 = g.project_corners(T, SIZE, K, DIST)
    eps_ml, eps_ippe = [], []
    for _ in range(2000):
        z = z0 + rng.normal(0, SIGMA, (4, 2))
        Z_ippe = ippe_solutions(z, SIZE, K, DIST)[0][0]
        Z_ml, _, _ = g.joint_pnp([("gs1", z, K, DIST, np.eye(4))], SIZE, Z_ippe, {"gs1": SIGMA})
        eps_ml.append(g.log_se3(g.inv(T) @ Z_ml))
        eps_ippe.append(g.log_se3(g.inv(T) @ Z_ippe))
    sd_pred = np.sqrt(np.diag(cov))
    ratio_ml = np.array(eps_ml).std(axis=0, ddof=1) / sd_pred
    ratio_ippe = np.array(eps_ippe).std(axis=0, ddof=1) / sd_pred
    assert np.all((ratio_ml > 0.90) & (ratio_ml < 1.10)), ratio_ml
    assert np.all((ratio_ippe >= 0.95) & (ratio_ippe < 1.6)), ratio_ippe
    # La z (la profundidad) es el eje debil: unas 5 veces peor que x e y.
    assert 3 < sd_pred[5] / sd_pred[3] < 10


def test_transport_covariance_no_cambia_por_la_derecha() -> None:
    """Z = X exp(eps): T Z = (T X) exp(eps). La covarianza por la derecha no cambia; por la
    izquierda cambiaria con la adjunta: se comprueba que son distintas, para que quede claro
    que convencion se usa."""
    rng = _rng()
    T12 = second_camera()
    cov = g.pose_covariance(marker_pose(), SIZE, K, DIST, SIGMA)
    assert np.array_equal(g.transport_covariance(T12, cov), cov)
    Ad = g.adjoint(T12)
    assert not np.allclose(Ad @ cov @ Ad.T, cov)
    # Monte Carlo: eps por la derecha de Z y de T12 Z son los mismos numeros.
    X = marker_pose()
    for _ in range(20):
        eps = rng.normal(0, 1e-3, 6)
        Z = X @ g.exp_se3(eps)
        assert np.allclose(g.log_se3(g.inv(T12 @ X) @ (T12 @ Z)), eps, atol=1e-10)
    P = g.position_covariance(X, cov)
    assert P.shape == (3, 3) and np.trace(P) == pytest.approx(np.trace(cov[3:, 3:]))


# ----------------------------------------------------------------------------- fusion


def test_fuse_poses_sin_ruido_es_exacta_y_pondera_bien() -> None:
    T = marker_pose()
    cov = g.pose_covariance(T, SIZE, K, DIST, SIGMA)
    X, C = g.fuse_poses([T, T], [cov, cov])
    assert g.pose_difference(X, T)[0] < 1e-6 and g.pose_difference(X, T)[1] < 1e-6
    assert np.allclose(C, cov / 2)
    # Una medida mucho mas segura manda: la fusion cae sobre ella.
    Z2 = T @ g.exp_se3([0, 0, 0, 0.5, 0, 0])
    X, _ = g.fuse_poses([T, Z2], [cov, cov * 1e-6])
    assert g.pose_difference(X, Z2)[0] < 1e-3
    # Con el mismo peso, la fusion cae en medio (es el minimo de la suma de los dos residuos
    # al cuadrado en SE(3), que difiere del punto medio en terminos de segundo orden: ~1e-3 mm).
    X, _ = g.fuse_poses([T, Z2], [cov, cov])
    assert g.pose_difference(X, T @ g.exp_se3([0, 0, 0, 0.25, 0, 0]))[0] < 0.01
    with pytest.raises(ValueError):
        g.fuse_poses([], [])


def test_reduccion_medida_igual_a_la_predicha_con_dos_camaras() -> None:
    """Dos camaras a 30 grados: la sd 3D fusionada (Monte Carlo, 2000 parejas, poses por
    minimos cuadrados) baja lo que dice `predicted_reduction` a +-3 puntos; la fusion de
    poses y el PnP conjunto dan el mismo numero a +-2 puntos."""
    rng = _rng()
    T1 = marker_pose()
    T12 = second_camera(30.0)
    T2 = g.inv(T12) @ T1
    cov1 = g.pose_covariance(T1, SIZE, K, DIST, SIGMA)
    cov2 = g.pose_covariance(T2, SIZE, K, DIST, SIGMA)
    pred = predicted_reduction(g.position_covariance(T1, cov1), g.position_covariance(T12 @ T2, cov2))
    z10, z20 = g.project_corners(T1, SIZE, K, DIST), g.project_corners(T2, SIZE, K, DIST)
    p1, p2, pf, pj = [], [], [], []
    for _ in range(2000):
        z1 = z10 + rng.normal(0, SIGMA, (4, 2))
        z2 = z20 + rng.normal(0, SIGMA, (4, 2))
        Z1 = g.joint_pnp([("gs1", z1, K, DIST, np.eye(4))], SIZE, ippe_solutions(z1, SIZE, K, DIST)[0][0], {"gs1": SIGMA})[0]
        Z2 = T12 @ g.joint_pnp([("gs2", z2, K, DIST, np.eye(4))], SIZE, ippe_solutions(z2, SIZE, K, DIST)[0][0], {"gs2": SIGMA})[0]
        X, _ = g.fuse_poses([Z1, Z2], [cov1, g.transport_covariance(T12, cov2)])
        J, _, _ = g.joint_pnp([("gs1", z1, K, DIST, np.eye(4)), ("gs2", z2, K, DIST, T12)], SIZE, Z1,
                              {"gs1": SIGMA, "gs2": SIGMA})
        p1.append(Z1[:3, 3])
        p2.append(Z2[:3, 3])
        pf.append(X[:3, 3])
        pj.append(J[:3, 3])

    def sd3(p):
        return float(np.sqrt(np.var(np.asarray(p), axis=0, ddof=1).sum()))
    best = min(sd3(p1), sd3(p2))
    red_f, red_j = 1 - sd3(pf) / best, 1 - sd3(pj) / best
    assert abs(red_f - pred["reduction_3d"]) < 0.03, (red_f, pred["reduction_3d"])
    assert abs(red_j - pred["reduction_3d"]) < 0.03, (red_j, pred["reduction_3d"])
    assert abs(red_f - red_j) < 0.02
    assert 0.5 < pred["reduction_3d"] < 0.8          # a 30 grados, ~0.67 con el mismo ruido


def test_joint_pnp_sin_ruido_es_exacto_y_los_dos_solvers_coinciden() -> None:
    rng = _rng()
    T1 = marker_pose()
    T12 = second_camera(25.0)
    T2 = g.inv(T12) @ T1
    z1, z2 = g.project_corners(T1, SIZE, K, DIST), g.project_corners(T2, SIZE, K, DIST)
    T0 = T1 @ g.exp_se3([0.01, -0.01, 0.005, 2.0, -1.0, 5.0])
    obs = [("gs1", z1, K, DIST, np.eye(4)), ("gs2", z2, K, DIST, T12)]
    Ta, cov, rms = g.joint_pnp(obs, SIZE, T0, {"gs1": SIGMA, "gs2": SIGMA})
    assert g.pose_difference(Ta, T1)[0] < 1e-6 and g.pose_difference(Ta, T1)[1] < 1e-6 and rms < 1e-6
    assert cov.shape == (6, 6) and np.all(np.linalg.eigvalsh(cov) > 0)
    Tb, _, _ = g.joint_pnp(obs, SIZE, T0, {"gs1": SIGMA, "gs2": SIGMA}, solver="scipy")
    assert g.pose_difference(Ta, Tb)[0] < 1e-6 and g.pose_difference(Ta, Tb)[1] < 1e-6
    zr = z1 + rng.normal(0, SIGMA, (4, 2))
    Tc = g.joint_pnp([("gs1", zr, K, DIST, np.eye(4))], SIZE, T0, {"gs1": SIGMA})[0]
    Td = g.joint_pnp([("gs1", zr, K, DIST, np.eye(4))], SIZE, T0, {"gs1": SIGMA}, solver="scipy")[0]
    assert g.pose_difference(Tc, Td)[0] < 1e-6 and g.pose_difference(Tc, Td)[1] < 1e-6
    with pytest.raises(ValueError, match="solver"):
        g.joint_pnp(obs, SIZE, T0, {"gs1": SIGMA, "gs2": SIGMA}, solver="x")
    with pytest.raises(ValueError):
        g.joint_pnp([], SIZE, T0, {})
