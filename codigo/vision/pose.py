"""Pose de un marker individual con SOLVEPNP_IPPE_SQUARE.

Eran `construir_object_points`, `estimar_pose_individual` y
`rvec_tvec_a_matriz` de `tracker.py` (meta 003, fase 4): los cuerpos no
cambian, solo el nombre y el sitio. La pose multi-marker del dodecaedro
(`estimar_pose_rigid_body`) esta archivada en
`codigo/historico/iter4/dodecahedron/pose_rigid_body.py`.

Context7 (2026-10-24, OpenCV 4.13; instalado 4.11): `SOLVEPNP_IPPE_SQUARE`
exige exactamente 4 puntos en el orden (-s/2, s/2), (s/2, s/2), (s/2, -s/2),
(-s/2, -s/2): es el de `build_object_points`. `solvePnP` devuelve `(ok, rvec,
tvec)`; `Rodrigues` pasa el rvec a matriz 3x3.
"""
from __future__ import annotations

import cv2
import numpy as np


def build_object_points(size_mm: float) -> np.ndarray:
    """4 esquinas de un marcador individual centrado en su origen local (4x3 float32)."""
    half = size_mm / 2.0
    return np.array(
        [
            [-half,  half, 0],   # c0 = top-left
            [ half,  half, 0],   # c1 = top-right
            [ half, -half, 0],   # c2 = bottom-right
            [-half, -half, 0],   # c3 = bottom-left
        ],
        dtype=np.float32,
    )


def estimate_single_pose(corners_2d, size_mm: float, K, dist):
    """Pose de un marcador individual con SOLVEPNP_IPPE_SQUARE.

    IPPE_SQUARE devuelve la mejor de las DOS soluciones posibles para un
    marker planar (espejada en el plano de imagen). A veces el ranking de
    OpenCV elige la solucion equivocada, que termina con el marker DETRAS
    de la camara (tvec[2] < 0). Esos casos se filtran como invalidos en
    lugar de propagarlos a Slicer.

    Devuelve (rvec, tvec) o None si falla o si la pose es invalida (z <= 0).
    """
    object_pts = build_object_points(size_mm)
    image_pts = np.asarray(corners_2d).reshape(4, 2).astype(np.float32)

    ok, rvec, tvec = cv2.solvePnP(
        object_pts, image_pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE
    )
    if not ok:
        return None
    if float(tvec[2, 0]) <= 0:
        # Marker fisicamente DETRAS de la camara: ambiguedad planar de IPPE.
        return None
    return rvec, tvec


def rvec_tvec_to_matrix(rvec, tvec) -> np.ndarray:
    """Convierte rvec/tvec a matriz homogenea 4x4 (float64)."""
    R, _ = cv2.Rodrigues(rvec)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = np.asarray(tvec).flatten()
    return M
