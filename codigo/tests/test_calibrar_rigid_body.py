"""Tests para calibrar_rigid_body.py.

Cubre funciones puras + tests con datasets sinteticos.
Ejecutar: python -m pytest tests/test_calibrar_rigid_body.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
CODIGO_DIR = HERE.parent
sys.path.insert(0, str(CODIGO_DIR))

import calibrar_rigid_body as cr


def _generar_geometria_teorica_simple():
    """Tres markers de 16 mm, uno como ancla y dos en posiciones conocidas."""
    geom = {}
    # ID 100 (ancla): cara TOP, normal +Z
    geom[100] = cr.marker_pose_a_esquinas(
        np.array([0.0, 0.0, 22.27]), np.array([0.0, 0.0, 0.0]), 16.0
    )
    # ID 101: cara lateral, rotada 90 grados alrededor de Y
    geom[101] = cr.marker_pose_a_esquinas(
        np.array([22.27, 0.0, 0.0]),
        Rotation.from_euler("y", 90, degrees=True).as_rotvec(),
        16.0,
    )
    # ID 102: otra cara lateral
    geom[102] = cr.marker_pose_a_esquinas(
        np.array([0.0, 22.27, 0.0]),
        Rotation.from_euler("x", -90, degrees=True).as_rotvec(),
        16.0,
    )
    return geom


def _generar_dataset_sintetico(geom, K, dist, n_frames=20, seed=42):
    """Genera frames sinteticos perfectos (sin ruido) proyectando la geom con poses al azar."""
    rng = np.random.RandomState(seed)
    frames = []
    poses = []
    for _ in range(n_frames):
        rvec = rng.uniform(-1.5, 1.5, 3)
        tvec = np.array([rng.uniform(-50, 50), rng.uniform(-50, 50),
                         rng.uniform(250, 450)])
        detecciones = {}
        for mid, esquinas in geom.items():
            proy, _ = cv2.projectPoints(esquinas.astype(np.float64),
                                          rvec, tvec, K, dist)
            detecciones[mid] = proy.reshape(4, 2).astype(np.float32)
        frames.append({"timestamp": 0.0, "detecciones": detecciones})
        poses.append((rvec, tvec))
    return frames, poses


def _K_dist_default():
    K = np.array([[427.0, 0.0, 315.0],
                  [0.0, 427.0, 237.0],
                  [0.0, 0.0, 1.0]], dtype=np.float64)
    dist = np.zeros((1, 5), dtype=np.float64)
    return K, dist


# --- Hash ---

def test_hash_sha256_estable(tmp_path):
    p1 = tmp_path / "a"; p1.write_text("X", encoding="utf-8")
    p2 = tmp_path / "b"; p2.write_text("X", encoding="utf-8")
    assert cr.hash_sha256(p1) == cr.hash_sha256(p2)


# --- Cargar referencia ---

def test_cargar_referencia_archivo_real():
    p = CODIGO_DIR / "data" / "reference_dodecaedro.txt"
    if not p.exists():
        pytest.skip("data/reference_dodecaedro.txt no existe")
    geom = cr.cargar_referencia(p)
    assert len(geom) == 11
    assert set(geom.keys()) == set(range(151, 162))
    for mid in geom:
        assert geom[mid].shape == (4, 3)


# --- Parametrizacion rigida ---

def test_marker_pose_a_esquinas_es_cuadrado():
    """Las 4 esquinas forman un cuadrado de lado marker_mm."""
    centro = np.array([1.0, 2.0, 3.0])
    rvec = np.array([0.1, 0.2, 0.3])
    esq = cr.marker_pose_a_esquinas(centro, rvec, 16.0)
    assert esq.shape == (4, 3)
    for i in range(4):
        lado = np.linalg.norm(esq[i] - esq[(i+1) % 4])
        assert abs(lado - 16.0) < 1e-9


def test_marker_pose_a_esquinas_centro_correcto():
    centro = np.array([5.0, -3.0, 10.0])
    esq = cr.marker_pose_a_esquinas(centro, np.zeros(3), 16.0)
    np.testing.assert_allclose(esq.mean(axis=0), centro, atol=1e-10)


def test_esquinas_a_marker_pose_round_trip():
    """marker_pose -> esquinas -> marker_pose recupera centro y rvec (modulo eq)."""
    centro_orig = np.array([1.0, 2.0, 3.0])
    rvec_orig = np.array([0.1, -0.2, 0.5])
    esq = cr.marker_pose_a_esquinas(centro_orig, rvec_orig, 16.0)
    centro_rec, rvec_rec = cr.esquinas_a_marker_pose(esq, 16.0)
    np.testing.assert_allclose(centro_rec, centro_orig, atol=1e-9)
    # rvec puede tener equivalencias, comparar la matriz de rotacion
    R_orig = Rotation.from_rotvec(rvec_orig).as_matrix()
    R_rec = Rotation.from_rotvec(rvec_rec).as_matrix()
    np.testing.assert_allclose(R_rec, R_orig, atol=1e-9)


def test_parametrizar_reconstruir_round_trip():
    """Geom teorica -> params libres -> geom reconstruida es identica."""
    geom = _generar_geometria_teorica_simple()
    ids_orden = sorted(geom.keys())
    params, offsets = cr.parametrizar_geometria(geom, ids_orden, 100, 16.0)
    # Parametrizacion libre: 2 markers no anclados x 12 floats = 24 params
    assert len(params) == 24
    geom_rec = cr.reconstruir_geometria(params, offsets, geom[100], ids_orden, 100, 16.0)
    for mid in ids_orden:
        np.testing.assert_allclose(geom_rec[mid], geom[mid], atol=1e-12,
                                    err_msg=f"ID {mid}")


# --- jac_sparsity ---

def test_construir_jac_sparsity_shape():
    """Forma de la matriz: (total_residuos, n_total_params).

    Parametrizacion libre: 24 params (2 markers no-ancla x 12) + 6 pose = 30 totales.
    Frame con 3 markers detectados -> 3*8 = 24 residuos.
    """
    geom = _generar_geometria_teorica_simple()
    ids_orden = sorted(geom.keys())
    _, offsets = cr.parametrizar_geometria(geom, ids_orden, 100, 16.0)
    frames = [{"timestamp": 0.0, "detecciones": {100: np.zeros((4, 2)),
                                                   101: np.zeros((4, 2)),
                                                   102: np.zeros((4, 2))}}]
    A = cr.construir_jac_sparsity(frames, ids_orden, 100, offsets,
                                    n_geom_params=24, n_pose_params=6)
    assert A.shape == (24, 30)


def test_construir_jac_sparsity_solo_no_ancla_tiene_jac_geom():
    """Las filas del ancla solo dependen de la pose, no de params de geometria."""
    geom = _generar_geometria_teorica_simple()
    ids_orden = sorted(geom.keys())
    _, offsets = cr.parametrizar_geometria(geom, ids_orden, 100, 16.0)
    frames = [{"timestamp": 0.0, "detecciones": {100: np.zeros((4, 2))}}]
    A = cr.construir_jac_sparsity(frames, ids_orden, 100, offsets,
                                    n_geom_params=24, n_pose_params=6).toarray()
    # Las primeras 24 columnas (geom) deberian ser todas cero
    assert A[:, :24].sum() == 0
    # Las ultimas 6 (pose) deberian ser todas uno
    assert A[:, 24:].sum() == 8 * 6  # 8 residuos x 6 params de pose


def test_construir_jac_sparsity_estructura_por_esquina():
    """Cada residuo de la esquina k depende solo de los 3 params de esa esquina."""
    geom = _generar_geometria_teorica_simple()
    ids_orden = sorted(geom.keys())
    _, offsets = cr.parametrizar_geometria(geom, ids_orden, 100, 16.0)
    frames = [{"timestamp": 0.0, "detecciones": {101: np.zeros((4, 2))}}]
    A = cr.construir_jac_sparsity(frames, ids_orden, 100, offsets,
                                    n_geom_params=24, n_pose_params=6).toarray()
    marker_offset = offsets[101]
    # Filas 0-1 (c0): depend de cols [marker_offset, marker_offset+3) y de pose
    for r in (0, 1):
        for c in range(3):
            assert A[r, marker_offset + c] == 1
        for c in range(3, 12):
            assert A[r, marker_offset + c] == 0  # no debe depender de otras esquinas
    # Filas 6-7 (c3): depend de cols [marker_offset+9, marker_offset+12)
    for r in (6, 7):
        for c in range(9, 12):
            assert A[r, marker_offset + c] == 1
        for c in range(9):
            assert A[r, marker_offset + c] == 0


# --- Residuos ---

def test_residuos_zero_con_geometria_y_poses_perfectas():
    """Con datos sinteticos perfectos y la geom teorica, los residuos son ~0."""
    K, dist = _K_dist_default()
    geom = _generar_geometria_teorica_simple()
    frames, poses = _generar_dataset_sintetico(geom, K, dist, n_frames=10)

    ids_orden = sorted(geom.keys())
    params_g, offsets = cr.parametrizar_geometria(geom, ids_orden, 100, 16.0)
    params_p = cr.parametrizar_poses(poses)
    params = np.concatenate([params_g, params_p])

    res = cr.calcular_residuos(params, frames, ids_orden, 100, geom[100],
                                offsets, len(params_g), 16.0, K, dist)
    rmse = np.sqrt(np.mean(res**2))
    assert rmse < 1e-3, f"RMSE = {rmse} para datos perfectos (deberia ser ~0)"


def test_residuos_aumentan_con_perturbacion():
    """Si perturbamos la geometria, los residuos crecen."""
    K, dist = _K_dist_default()
    geom = _generar_geometria_teorica_simple()
    frames, poses = _generar_dataset_sintetico(geom, K, dist, n_frames=10)

    ids_orden = sorted(geom.keys())
    params_g, offsets = cr.parametrizar_geometria(geom, ids_orden, 100, 16.0)
    params_p = cr.parametrizar_poses(poses)
    params_ok = np.concatenate([params_g, params_p])

    # Perturbar 5 mm el centro del marker 101
    params_perturbed = params_ok.copy()
    params_perturbed[offsets[101]] += 5.0  # cx

    res_ok = cr.calcular_residuos(params_ok, frames, ids_orden, 100, geom[100],
                                    offsets, len(params_g), 16.0, K, dist)
    res_p = cr.calcular_residuos(params_perturbed, frames, ids_orden, 100, geom[100],
                                  offsets, len(params_g), 16.0, K, dist)
    assert np.sqrt(np.mean(res_p**2)) > 5 * np.sqrt(np.mean(res_ok**2))


# --- RMSE por marker ---

def test_rmse_por_marker_agrupa_correctamente():
    """Dado residuos sinteticos, agrupa por tag_id correctamente."""
    frames = [
        {"detecciones": {1: None, 2: None}},  # 2 detecciones, 16 residuos
        {"detecciones": {1: None}},  # 1 deteccion, 8 residuos
    ]
    # 16 + 8 = 24 residuos. ID 1 aparece en frame 0 (idx 0-7) y frame 1 (idx 16-23).
    # ID 2 aparece en frame 0 (idx 8-15).
    residuos = np.zeros(24)
    residuos[0:8] = 1.0      # ID 1 frame 0
    residuos[8:16] = 2.0     # ID 2 frame 0
    residuos[16:24] = 3.0    # ID 1 frame 1
    rmse_m = cr.rmse_por_marker(residuos, frames)
    # ID 1: 16 residuos, mitad valen 1 mitad 3 -> RMSE = sqrt((8*1 + 8*9)/16) = sqrt(5)
    assert abs(rmse_m[1][0] - np.sqrt(5)) < 1e-9
    assert rmse_m[1][1] == 2  # 2 detecciones
    assert abs(rmse_m[2][0] - 2.0) < 1e-9
    assert rmse_m[2][1] == 1


# --- BA end-to-end con datos sinteticos ---

def test_ba_recupera_geometria_perturbada():
    """Geom perturbada como semilla, BA con datos perfectos recupera la real."""
    from scipy.optimize import least_squares

    K, dist = _K_dist_default()
    geom_real = _generar_geometria_teorica_simple()
    ancla_id = 100
    ids_orden = sorted(geom_real.keys())

    # Datos sinteticos perfectos generados con geom_real
    frames, poses_real = _generar_dataset_sintetico(geom_real, K, dist, n_frames=20)

    # Geometria perturbada (semilla para BA): mover los markers no-ancla 3 mm
    geom_seed = {ancla_id: geom_real[ancla_id].copy()}
    rng = np.random.RandomState(42)
    for mid in ids_orden:
        if mid == ancla_id:
            continue
        # Pequeno desplazamiento en el centro
        centro_orig = geom_real[mid].mean(axis=0)
        rvec_orig = cr.esquinas_a_marker_pose(geom_real[mid], 16.0)[1]
        centro_pert = centro_orig + rng.uniform(-3, 3, 3)
        rvec_pert = rvec_orig + rng.uniform(-0.1, 0.1, 3)
        geom_seed[mid] = cr.marker_pose_a_esquinas(centro_pert, rvec_pert, 16.0)

    params_g, offsets = cr.parametrizar_geometria(geom_seed, ids_orden, ancla_id, 16.0)
    params_p = cr.parametrizar_poses(poses_real)
    params_init = np.concatenate([params_g, params_p])

    n_geom = len(params_g)
    n_pose = len(params_p)
    A_sparse = cr.construir_jac_sparsity(frames, ids_orden, ancla_id, offsets,
                                            n_geom, n_pose)

    resultado = least_squares(
        cr.calcular_residuos, params_init,
        args=(frames, ids_orden, ancla_id, geom_real[ancla_id],
              offsets, n_geom, 16.0, K, dist),
        jac_sparsity=A_sparse, x_scale="jac",
        method="trf", loss="huber", f_scale=2.0, max_nfev=100,
    )

    rmse = np.sqrt(np.mean(resultado.fun**2))
    assert rmse < 0.01, f"BA no convergio: RMSE final = {rmse}"

    geom_rec = cr.reconstruir_geometria(resultado.x[:n_geom], offsets,
                                          geom_real[ancla_id], ids_orden, ancla_id, 16.0)
    for mid in ids_orden:
        max_err = np.max(np.linalg.norm(geom_rec[mid] - geom_real[mid], axis=1))
        assert max_err < 0.1, f"ID {mid}: max err = {max_err} mm"


# --- Validacion prereqs ---

def test_validar_prerrequisitos_falla_si_input_inexistente(tmp_path):
    with pytest.raises(SystemExit):
        cr.validar_prerrequisitos(tmp_path / "no.npz", tmp_path / "g.txt",
                                    tmp_path / "out.txt", 151)


def test_validar_prerrequisitos_pasa_con_archivos_validos(tmp_path):
    inp = tmp_path / "input.npz"; inp.write_bytes(b"dummy")
    teo = tmp_path / "teorico.txt"; teo.write_text("dummy", encoding="utf-8")
    out = tmp_path / "output.txt"
    cr.validar_prerrequisitos(inp, teo, out, 151)
