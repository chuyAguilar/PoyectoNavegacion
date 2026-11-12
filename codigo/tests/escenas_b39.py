"""Las escenas sinteticas de B39 para el barrido de `error_correction_rate` (meta 006, fase
7d2 · Los IDs falsos del tablero en el detector del tracker). Con semilla fija.

pytest no recoge este archivo (no empieza por `test_`). Lo usan `test_barrido_correccion.py`
y, fuera de la suite, el barrido sintetico completo (`Claude outputs/fases/006/fase-7d2/
sintetico.py`, que escribe el `sinteticos.json` que lee la sesion).

- `poses_referencia`: la referencia de ID 100 (98.6 mm) con `synthetic.render_marker` en las
  poses de B39 (fase 7c): a 350-550 mm, +-40 mm de lado, inclinada hasta +-40 grados en dos
  ejes; K sintetica (fx 800), 640 x 480.
- `vistas_tablero`: el tablero ChArUco de la fase 7d (9 x 7 de 26 mm, `DICT_4X4_50`) con
  `tablero_sintetico.renderizar_charuco`: 1280 x 960, la K y la distorsion de gs1, a
  30-60 cm, inclinado hasta ~34 grados en dos ejes y girado, la mitad de las vistas con
  ruido de sd 3 niveles de gris. Con `con_referencia`, la referencia (ID 100, 100 mm) en el
  mismo plano, a la derecha del tablero y entera a la vista, como en el punto 9 de la 7d.
- `dos_copias_referencia`: un frame con dos copias del ID 100 lado a lado (lo que el filtro
  de la fase 7d2b no publica; aqui, lo que la regla tiene que contar como repetido).

Todas dan `(nombre, gris)`: lo que toma `diagnostics.barrido_correccion.barrer`. Las poses
de la 7c y las vistas de la 7d se midieron con guiones que no se guardaron: estas son poses
nuevas en los mismos rangos, asi que sus numeros no tienen por que ser los de entonces.
"""
from __future__ import annotations

from typing import Iterator

import cv2
import numpy as np

from calibration import calibrate_extrinsics as ce
from calibration import charuco_board as chb
from vision.detection import get_dictionary

from . import tablero_sintetico as ts
from .conftest import DATA_DIR
from .synthetic import render_marker

ID_REF, MM_REF = 100, 98.6                          # la referencia nueva (P48); el lado, el ejemplo de la 7c
DICCIONARIO_REF = "DICT_ARUCO_MIP_36h12"
Z_REF_MM, LADO_REF_MM, INCLINACION_REF_DEG = (350.0, 550.0), 40.0, 40.0

TABLERO = chb.TableroCharuco((9, 7), 26.0, 19.5, "DICT_4X4_50")     # el de P59
SHAPE_TABLERO = (1280, 960)
Z_TABLERO_MM, INCLINACION_TABLERO_RAD, GIRO_TABLERO_RAD = (300.0, 600.0), 0.6, 0.6
RUIDO_SD = 3.0
MARGEN_TABLERO_MM = 8.0
LADO_PLANO_REF_MM, BORDE_PLANO_REF_MM, PPMM_PLANO_REF = 100.0, 15.0, 4.0
MAX_INTENTOS = 200

_GS1: dict = {}
_PLANO_REF: list = []


def _gs1() -> tuple[np.ndarray, np.ndarray]:
    """La K y la distorsion de gs1 (meta 002), leidas una vez."""
    if not _GS1:
        _GS1.update(ce.leer_intrinsecos(DATA_DIR / "intrinsecos_gs1_1280x960.yml"))
    return _GS1["K"], _GS1["dist"]


def poses_referencia(n: int, semilla: int = 0) -> Iterator[tuple[str, np.ndarray]]:
    """`n` frames en gris (480, 640) de la referencia ID 100 sola, en poses al azar con
    `semilla`: profundidad 350-550 mm, +-40 mm de lado, inclinada hasta +-40 grados en x y en y."""
    rng = np.random.default_rng(semilla)
    for i in range(int(n)):
        tz = float(rng.uniform(*Z_REF_MM))
        tx = float(rng.uniform(-LADO_REF_MM, LADO_REF_MM))
        ax = 180.0 + float(rng.uniform(-INCLINACION_REF_DEG, INCLINACION_REF_DEG))
        ay = float(rng.uniform(-INCLINACION_REF_DEG, INCLINACION_REF_DEG))
        bgr = render_marker(tz, tx, marker_id=ID_REF, size_mm=MM_REF, euler_xy=(ax, ay))
        yield f"ref_{i:04d}", cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def _plano_referencia() -> np.ndarray:
    """El dibujo plano de la referencia (ID 100, 100 mm, con 15 mm de blanco alrededor) a 4 px/mm, suavizado."""
    if not _PLANO_REF:
        ppmm = PPMM_PLANO_REF
        lado, borde = int(LADO_PLANO_REF_MM * ppmm), int(BORDE_PLANO_REF_MM * ppmm)
        plano = np.full((lado + 2 * borde,) * 2, 255, np.uint8)
        plano[borde:borde + lado, borde:borde + lado] = cv2.aruco.generateImageMarker(get_dictionary(DICCIONARIO_REF), ID_REF, lado)
        _PLANO_REF.append(cv2.GaussianBlur(plano, (0, 0), 0.4 * ppmm))
    return _PLANO_REF[0]


def _referencia_entera(K, dist, rv, tv, x0: float, y0: float, margen_px: float = 6.0) -> bool:
    """Si el plano de la referencia (con su blanco), puesto en (x0, y0) mm del tablero, cae entero en la imagen."""
    lado = LADO_PLANO_REF_MM + 2 * BORDE_PLANO_REF_MM
    esquinas = np.array([[x0, y0, 0.0], [x0 + lado, y0, 0.0], [x0 + lado, y0 + lado, 0.0], [x0, y0 + lado, 0.0]])
    p = cv2.projectPoints(esquinas, rv, tv, K, dist)[0].reshape(-1, 2)
    w, h = SHAPE_TABLERO
    return bool((p[:, 0] > margen_px).all() and (p[:, 0] < w - 1 - margen_px).all()
                and (p[:, 1] > margen_px).all() and (p[:, 1] < h - 1 - margen_px).all())


def vistas_tablero(n: int, con_referencia: bool, semilla: int = 0) -> Iterator[tuple[str, np.ndarray]]:
    """`n` vistas en gris (960, 1280) del tablero ChArUco, en poses al azar con `semilla`: su
    centro cerca del de la imagen, a 30-60 cm, inclinado hasta +-0.6 rad (~34 grados) en dos
    ejes y girado hasta +-0.6 rad; las vistas impares llevan ruido de sd 3. Con
    `con_referencia`, la referencia ID 100 en el plano del tablero, a su derecha (a 10 mm de
    su margen), y solo valen las poses que la dejan entera en la imagen (el tablero puede
    salirse en parte)."""
    K, dist = _gs1()
    rng = np.random.default_rng(semilla)
    w, h = SHAPE_TABLERO
    x0, y0 = TABLERO.ancho_mm + MARGEN_TABLERO_MM + 10.0, 20.0     # la esquina del plano de la referencia, en mm del tablero
    for i in range(int(n)):
        for _ in range(MAX_INTENTOS):
            rv = np.array([rng.uniform(-INCLINACION_TABLERO_RAD, INCLINACION_TABLERO_RAD),
                           rng.uniform(-INCLINACION_TABLERO_RAD, INCLINACION_TABLERO_RAD),
                           rng.uniform(-GIRO_TABLERO_RAD, GIRO_TABLERO_RAD)])
            z = float(rng.uniform(*Z_TABLERO_MM))
            objetivo = (float(rng.uniform(0.35 * w, 0.65 * w)), float(rng.uniform(0.35 * h, 0.65 * h)))
            if con_referencia:                                      # el conjunto, mas a la izquierda: cabe la referencia
                objetivo = (objetivo[0] - 0.2 * w, objetivo[1])
            tv = ts.pose_charuco_hacia(TABLERO, K, rv, objetivo, z)
            if not con_referencia or _referencia_entera(K, dist, rv, tv, x0, y0):
                break
        else:
            raise RuntimeError(f"vista {i}: ninguna pose de {MAX_INTENTOS} deja la referencia entera en la imagen")
        img = ts.renderizar_charuco(TABLERO, K, rv, tv, SHAPE_TABLERO, dist, margen_mm=MARGEN_TABLERO_MM)
        if con_referencia:
            ppmm = PPMM_PLANO_REF
            img = ts.renderizar_plano(_plano_referencia(), (-x0 * ppmm, -y0 * ppmm), ppmm, K, rv, tv, SHAPE_TABLERO, dist, sobre=img)
        if i % 2 == 1:
            img = np.clip(img.astype(np.float64) + rng.normal(0.0, RUIDO_SD, img.shape), 0, 255).astype(np.uint8)
        yield f"{'tablero_ref' if con_referencia else 'tablero'}_{i:03d}", img


def dos_copias_referencia(tz: float = 500.0, dx: float = 0.0) -> tuple[str, np.ndarray]:
    """Un frame en gris (480, 640) con dos copias del ID 100 de 98.6 mm, de frente a `tz` mm,
    una a cada lado (x = -85 + dx y 85 + dx mm): el detector lee el 100 dos veces."""
    de_frente = (180.0, 0.0)
    izq = render_marker(tz, -85.0 + dx, marker_id=ID_REF, size_mm=MM_REF, euler_xy=de_frente)
    der = render_marker(tz, 85.0 + dx, marker_id=ID_REF, size_mm=MM_REF, euler_xy=de_frente)
    if np.any((izq != 110) & (der != 110)):
        raise ValueError("las dos copias se pisan")
    return "dos_copias", cv2.cvtColor(np.where(der != 110, der, izq), cv2.COLOR_BGR2GRAY)
