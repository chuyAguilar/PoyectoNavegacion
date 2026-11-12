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


# ----------------------------------------------------------------------------
# El tablero ChArUco (meta 006, fase 7d)
# ----------------------------------------------------------------------------

_REJILLAS: dict = {}
_PLANOS: dict = {}


def _rejilla_normalizada(K, dist, shape) -> tuple[np.ndarray, np.ndarray]:
    """Por pixel de una imagen `shape` = (w, h), las coordenadas normalizadas sin distorsion de
    su centro (`undistortPoints`), en dos arrays float32 (h, w). Se guarda por (K, dist, shape)."""
    K = np.asarray(K, dtype=np.float64)
    d = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64).flatten()
    clave = (K.tobytes(), d.tobytes(), tuple(shape))
    if clave not in _REJILLAS:
        w, h = int(shape[0]), int(shape[1])
        uu, vv = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
        pts = np.stack([uu.ravel(), vv.ravel()], axis=1).reshape(-1, 1, 2)
        n = cv2.undistortPoints(pts, K, d).reshape(h, w, 2)
        _REJILLAS[clave] = (np.ascontiguousarray(n[..., 0], dtype=np.float32), np.ascontiguousarray(n[..., 1], dtype=np.float32))
    return _REJILLAS[clave]


def renderizar_plano(plano: np.ndarray, origen_px, ppmm: float, K, rvec, tvec, shape, dist=None,
                     fondo: int = 128, sobre: np.ndarray | None = None) -> np.ndarray:
    """La vista en gris (h, w) de un dibujo plano con la pose dada, CON distorsion: cada pixel se
    lleva a su rayo sin distorsion, el rayo al plano z = 0 del objeto y de ahi a `plano` (una
    imagen a `ppmm` pixeles por mm cuyo punto (0, 0) mm cae en `origen_px`, en coordenadas de
    borde de pixel). Convencion de `projectPoints`: el centro del pixel (i, j) es (i, j).
    `plano` tiene que venir suavizado (bordes mas anchos que un pixel de la vista): el muestreo
    es puntual. Fuera del dibujo queda `fondo` o, si se da, la imagen `sobre`."""
    w, h = int(shape[0]), int(shape[1])
    nx, ny = _rejilla_normalizada(K, dist, (w, h))
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))
    Hi = np.linalg.inv(np.column_stack([R[:, 0], R[:, 1], np.asarray(tvec, dtype=np.float64).reshape(3)])).astype(np.float32)
    W = nx * Hi[2, 0] + ny * Hi[2, 1] + Hi[2, 2]
    delante = W > 1e-9
    W = np.where(delante, W, np.float32(1.0))
    mx = ((nx * Hi[0, 0] + ny * Hi[0, 1] + Hi[0, 2]) / W * np.float32(ppmm) + np.float32(origen_px[0] - 0.5)).astype(np.float32)
    my = ((nx * Hi[1, 0] + ny * Hi[1, 1] + Hi[1, 2]) / W * np.float32(ppmm) + np.float32(origen_px[1] - 0.5)).astype(np.float32)
    mx[~delante] = -10.0
    my[~delante] = -10.0
    out = np.full((h, w), fondo, dtype=np.uint8) if sobre is None else sobre.copy()
    cv2.remap(plano, mx, my, cv2.INTER_LINEAR, dst=out, borderMode=cv2.BORDER_TRANSPARENT)
    return out


def plano_charuco(t, ppmm: float = 8.0, margen_mm: float = 8.0, desenfoque_mm: float = 0.4) -> np.ndarray:
    """La imagen del tablero ChArUco `t` (`charuco_board.imagen`) suavizada con una gaussiana de
    `desenfoque_mm` (la optica: sin ella, el muestreo puntual clava los bordes en medios pixeles
    y `cornerSubPix` se va 0.1-0.2 px; medido en la fase 7d). Se guarda por sus argumentos."""
    from calibration import charuco_board as chb
    clave = (t, float(ppmm), float(margen_mm), float(desenfoque_mm))
    if clave not in _PLANOS:
        img = chb.imagen(t, margen_mm, ppmm)
        _PLANOS[clave] = cv2.GaussianBlur(img, (0, 0), desenfoque_mm * ppmm) if desenfoque_mm > 0 else img
    return _PLANOS[clave]


def renderizar_charuco(t, K, rvec, tvec, shape, dist=None, ppmm: float = 8.0, margen_mm: float = 8.0,
                       desenfoque_mm: float = 0.4, fondo: int = 128, sobre: np.ndarray | None = None) -> np.ndarray:
    """Vista en gris (h, w) del tablero ChArUco `t` con la pose `T_cam<-tablero` (rvec, tvec; el
    origen del tablero es su esquina exterior, como en `charuco_board.puntos_objeto`), con la K y
    la distorsion dadas. Las esquinas verdaderas son `projectPoints(puntos_objeto(t, ids), ...)`."""
    plano = plano_charuco(t, ppmm, margen_mm, desenfoque_mm)
    return renderizar_plano(plano, (margen_mm * ppmm, margen_mm * ppmm), ppmm, K, rvec, tvec, shape, dist, fondo, sobre)


def pose_charuco_hacia(t, K, rvec, objetivo_px, z_mm: float) -> np.ndarray:
    """tvec que pone el centro del tablero ChArUco en `objetivo_px` a la profundidad `z_mm`."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))
    centro = np.array([t.ancho_mm / 2.0, t.alto_mm / 2.0, 0.0])
    u, v = objetivo_px
    return np.array([(u - K[0, 2]) / K[0, 0] * z_mm, (v - K[1, 2]) / K[1, 1] * z_mm, z_mm]) - R @ centro


# ----------------------------------------------------------------------------
# La referencia junto al tablero ChArUco (meta 006, fase 7c3)
# ----------------------------------------------------------------------------

REF_DICCIONARIO, REF_ID = "DICT_ARUCO_MIP_36h12", 100     # la referencia de los perfiles (P48)
REF_MARGEN_MM = 14.0            # el blanco alrededor del marker en su placa (130 mm de placa, ~100 de marker)
TABLERO_MARGEN_MM = 8.0         # el blanco alrededor del tablero impreso (fase 7d)
_PLANOS_MARKER: dict = {}


def plano_marker(diccionario: str, marker_id: int, lado_mm: float, margen_mm: float, px_por_modulo: int = 50,
                 desenfoque_mm: float = 0.4) -> tuple[np.ndarray, float]:
    """El dibujo plano de un marker ArUco de `lado_mm` con sus bordes en el sitio exacto, y su
    escala: `(plano, ppmm)`. El marker se dibuja a `px_por_modulo` pixeles por modulo
    (`generateImageMarker`; 8 modulos por lado en 36h12), asi que `ppmm` = modulos x
    `px_por_modulo` / `lado_mm` no tiene por que ser entero (`renderizar_plano` lo admite) y
    cualquier lado sale exacto. Alrededor, `margen_mm` de blanco redondeado hacia arriba a
    pixeles enteros: el marker queda centrado y su primera esquina cae en el pixel (m, m), con
    m = (plano.shape[0] - modulos x px_por_modulo) / 2. Suavizado con una gaussiana de
    `desenfoque_mm` (como `plano_charuco`). Se guarda por sus argumentos."""
    from vision.detection import get_dictionary
    clave = (str(diccionario), int(marker_id), float(lado_mm), float(margen_mm), int(px_por_modulo), float(desenfoque_mm))
    if clave not in _PLANOS_MARKER:
        if not lado_mm > 0 or margen_mm < 0 or px_por_modulo < 1:
            raise ValueError(f"lado_mm > 0, margen_mm >= 0 y px_por_modulo >= 1, no {lado_mm}, {margen_mm} y {px_por_modulo}")
        dic = get_dictionary(diccionario)
        lado_px = (int(dic.markerSize) + 2) * int(px_por_modulo)
        ppmm = lado_px / float(lado_mm)
        m = int(np.ceil(margen_mm * ppmm))
        plano = np.full((lado_px + 2 * m, lado_px + 2 * m), 255, np.uint8)
        plano[m:m + lado_px, m:m + lado_px] = cv2.aruco.generateImageMarker(dic, int(marker_id), lado_px)
        if desenfoque_mm > 0:
            plano = cv2.GaussianBlur(plano, (0, 0), desenfoque_mm * ppmm)
        _PLANOS_MARKER[clave] = (plano, ppmm)
    return _PLANOS_MARKER[clave]


def escena_tablero_y_marker(t, K, dist, rvec, tvec, lado_mm: float, x0_mm: float, y0_mm: float, altura_mm: float,
                            shape, ruido_sd: float = 0.0, rng=None) -> tuple[np.ndarray, np.ndarray]:
    """La vista en gris (h, w) del tablero ChArUco `t` con la pose `T_cam<-tablero` (rvec, tvec)
    y, a su lado, la referencia (ID 100, `DICT_ARUCO_MIP_36h12`) de `lado_mm` con su placa blanca
    (`REF_MARGEN_MM`); y las 4 esquinas verdaderas de la referencia, (4, 2) float64, en el orden
    del detector (`projectPoints`).

    La referencia va en la pose del tablero trasladada a (`x0_mm`, `y0_mm`, -`altura_mm`) en mm
    del tablero: (x0, y0) es donde cae la primera esquina de su cuadro negro (la de arriba a la
    izquierda), con los ejes de `charuco_board.puntos_objeto` (x a la derecha, y hacia abajo,
    z hacia dentro del tablero); `altura_mm` > 0 la acerca a la camara (su cara queda mas alta
    que la del tablero), paralela a el. El tablero se dibuja a la primera escala de
    `charuco_board.PPMM_PNG` en que su casilla mide pixeles enteros (20 px/mm con 25.95 mm).
    Con `ruido_sd` > 0, ruido gaussiano en niveles de gris (`rng`, o uno nuevo con semilla 0)."""
    from calibration import charuco_board as chb
    ppmm_t = next((p for p in chb.PPMM_PNG if abs(t.casilla_mm * p - round(t.casilla_mm * p)) < 1e-6
                   and abs(TABLERO_MARGEN_MM * p - round(TABLERO_MARGEN_MM * p)) < 1e-6), None)
    if ppmm_t is None:
        raise ValueError(f"la casilla de {t.casilla_mm:g} mm no mide pixeles enteros a ninguna de las escalas {chb.PPMM_PNG}")
    img = renderizar_charuco(t, K, rvec, tvec, shape, dist, ppmm=float(ppmm_t), margen_mm=TABLERO_MARGEN_MM)
    plano, ppmm = plano_marker(REF_DICCIONARIO, REF_ID, lado_mm, REF_MARGEN_MM)
    m = (plano.shape[0] - round(lado_mm * ppmm)) / 2.0
    rv = np.asarray(rvec, dtype=np.float64).reshape(3)
    R, _ = cv2.Rodrigues(rv.reshape(3, 1))
    tv = np.asarray(tvec, dtype=np.float64).reshape(3) + R @ np.array([x0_mm, y0_mm, -altura_mm], dtype=np.float64)
    img = renderizar_plano(plano, (m, m), ppmm, K, rv, tv, shape, dist, sobre=img)
    L = float(lado_mm)
    cuadro = np.array([[0.0, 0.0, 0.0], [L, 0.0, 0.0], [L, L, 0.0], [0.0, L, 0.0]])
    d = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64)
    esquinas = cv2.projectPoints(cuadro, rv, tv, np.asarray(K, dtype=np.float64), d)[0].reshape(4, 2).astype(np.float64)
    if ruido_sd > 0:
        rng = np.random.default_rng(0) if rng is None else rng
        img = np.clip(img.astype(np.float64) + rng.normal(0.0, ruido_sd, img.shape), 0, 255).astype(np.uint8)
    return img, esquinas
