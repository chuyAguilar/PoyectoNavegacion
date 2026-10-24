"""Tablero de ajedrez sintetico para las pruebas sin camara (meta 002, fase 4).

Proyecta las esquinas interiores con una K conocida (cv2.projectPoints) y, para
probar los detectores y la pose, renderiza la vista del tablero por homografia
(warpPerspective de un tablero plano; exacto solo sin distorsion).

Convencion: la misma de calibrar_camara.construir_objp: la esquina interior
(i, j) esta en (i*square_mm, j*square_mm, 0); el tablero tiene (cols+1) x
(rows+1) casillas y un borde blanco de `borde_casillas` casillas alrededor.
"""
from __future__ import annotations

import cv2
import numpy as np


from calibration import calibrate_camera as cc


def K_de(fx: float, fy: float, cx: float, cy: float) -> np.ndarray:
    return np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float64)


def proyectar(objp: np.ndarray, rvec, tvec, K, dist=None) -> np.ndarray:
    """Esquinas (N, 1, 2) float32 de objp con la pose y la K dadas."""
    d = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64)
    p, _j = cv2.projectPoints(np.asarray(objp, dtype=np.float64), np.asarray(rvec, dtype=np.float64),
                              np.asarray(tvec, dtype=np.float64), np.asarray(K, dtype=np.float64), d)
    return np.asarray(p, dtype=np.float32).reshape(-1, 1, 2)


def pose_hacia(K, rvec, objetivo_px, z_mm: float, cols: int, rows: int, square_mm: float) -> np.ndarray:
    """tvec que pone el centro del tablero en objetivo_px a la profundidad z_mm con la rotacion rvec."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))
    centro_mm = np.array([(cols - 1) / 2.0 * square_mm, (rows - 1) / 2.0 * square_mm, 0.0])
    u, v = objetivo_px
    centro_cam = np.array([(u - K[0, 2]) / K[0, 0] * z_mm, (v - K[1, 2]) / K[1, 1] * z_mm, z_mm])
    return centro_cam - R @ centro_mm


def dentro(puntos, shape, margen: int = 8) -> bool:
    p = np.asarray(puntos).reshape(-1, 2)
    w, h = shape
    return bool((p[:, 0] > margen).all() and (p[:, 0] < w - margen).all()
                and (p[:, 1] > margen).all() and (p[:, 1] < h - margen).all())


def vistas_sinteticas(K, dist, cols: int, rows: int, square_mm: float, shape, n: int, semilla: int = 0,
                      z_mm=(450.0, 800.0), ang_max: float = 0.5):
    """n vistas validas (todas las esquinas dentro): (obj_points, img_points, poses)."""
    rng = np.random.default_rng(semilla)
    objp = cc.construir_objp(cols, rows, square_mm)
    objs, imgs, poses = [], [], []
    w, h = shape
    intentos = 0
    while len(imgs) < n and intentos < 50 * n:
        intentos += 1
        rvec = np.array([rng.uniform(-ang_max, ang_max), rng.uniform(-ang_max, ang_max), rng.uniform(-0.6, 0.6)])
        z = rng.uniform(*z_mm)
        objetivo = (rng.uniform(0.15 * w, 0.85 * w), rng.uniform(0.15 * h, 0.85 * h))
        tvec = pose_hacia(K, rvec, objetivo, z, cols, rows, square_mm)
        img = proyectar(objp, rvec, tvec, K, dist)
        if not dentro(img, shape):
            continue
        objs.append(objp.copy())
        imgs.append(img)
        poses.append((rvec, tvec))
    if len(imgs) < n:
        raise RuntimeError(f"solo {len(imgs)} vistas validas de {n}")
    return objs, imgs, poses


def tablero_plano(cols: int, rows: int, square_mm: float, px_por_mm: float = 4.0,
                  borde_casillas: float = 1.0) -> tuple[np.ndarray, float]:
    """Imagen gris del tablero plano y el offset (mm) del origen de objp respecto a la esquina de la imagen."""
    sq = square_mm
    n_x, n_y = cols + 1, rows + 1
    offset_mm = (1.0 + borde_casillas) * sq           # objp (0,0) esta a una casilla + borde del canto
    W = int(round((n_x + 2 * borde_casillas) * sq * px_por_mm))
    H = int(round((n_y + 2 * borde_casillas) * sq * px_por_mm))
    img = np.full((H, W), 255, dtype=np.uint8)
    for i in range(n_x):
        for j in range(n_y):
            if (i + j) % 2 == 0:
                x0 = int(round((borde_casillas + i) * sq * px_por_mm))
                y0 = int(round((borde_casillas + j) * sq * px_por_mm))
                x1 = int(round((borde_casillas + i + 1) * sq * px_por_mm))
                y1 = int(round((borde_casillas + j + 1) * sq * px_por_mm))
                img[y0:y1, x0:x1] = 0
    return img, offset_mm


def renderizar_vista(K, rvec, tvec, cols: int, rows: int, square_mm: float, shape,
                     px_por_mm: float = 4.0, fondo: int = 128) -> np.ndarray:
    """Vista en gris (h, w) del tablero con la pose dada, por homografia (sin distorsion)."""
    plano, off = tablero_plano(cols, rows, square_mm, px_por_mm)
    Hp, Wp = plano.shape
    esquinas_mm = np.array([[-off, -off, 0.0], [Wp / px_por_mm - off, -off, 0.0],
                            [Wp / px_por_mm - off, Hp / px_por_mm - off, 0.0], [-off, Hp / px_por_mm - off, 0.0]])
    src = np.array([[0, 0], [Wp, 0], [Wp, Hp], [0, Hp]], dtype=np.float32)
    dst = proyectar(esquinas_mm, rvec, tvec, K, None).reshape(-1, 2).astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    w, h = shape
    return cv2.warpPerspective(plano, M, (int(w), int(h)), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=fondo)


def a_bgr(gray: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
