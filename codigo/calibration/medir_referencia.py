# -*- coding: utf-8 -*-
"""
El lado de la referencia medido con la camara contra el tablero ChArUco registrado (meta 006 ·
Grafo de factores optico-inercial, fase 7c3 · El tamano de la referencia medido con el tablero;
B55, P76 a P80; y fase 7c4 · P9 con la referencia sobre el tablero, P86 a P90). Fuera de la
cadena: no abre camara ni red y no importa `vision.tracking`; lee los PNG en gris que guarda el
tracker (`--save-frames`).

Por que: el `size_mm` de la referencia es la escala de toda la pose que se publica, y el calibrador
apoyado sobre una pieza impresa plana no lo da mejor que +-0.8 % (P76). El tablero si tiene una
escala fiable (su casilla se midio restando dos tramos, B - A). Desde la fase 7c4 (P87 a) la
referencia va ENCIMA del tablero, centrada (las dos piezas en planos paralelos por contacto, la
cara de la referencia 2.8 mm mas alta: `--altura-mm 2.8`), y la camara mide su lado en ese plano.
En la 7c3 iba a su lado, y P9 midio la inclinacion de las piezas, no el lado (P85, P86).

Como: por homografia, no por pose. Las esquinas del tablero y las de la referencia se llevan a
coordenadas normalizadas sin distorsion (`undistortPointsIter`); la homografia tablero (mm) ->
normalizadas se ajusta con las esquinas leidas del tablero (`findHomography`, minimos cuadrados)
y su inversa lleva las 4 esquinas de la referencia al plano del tablero, en mm. Es un cociente de
longitudes en un mismo plano: fx, fy, cx y cy los absorbe la homografia y solo entran por la
distorsion (por eso se descartan los frames con la referencia lejos del centro, `RADIO_MAX_PX`).
Lo que se mide es el borde que ve el detector del tracker (`vision.detection.detect` con el
detector del perfil, el mismo refinado), que es lo que `size_mm` tiene que valer.

La altura: si la cara de la referencia queda `altura_mm` mas cerca de la camara que la del
tablero (planos paralelos), su proyeccion sobre el plano del tablero desde el centro de la camara
es una homotecia de razon d / (d - altura), exacta con cualquier inclinacion; d es la distancia
del centro de la camara al plano del tablero (`distancia_al_plano`). `corregir_altura` la deshace.
Las dos piezas miden 2.8 mm (P78): al lado, `--altura-mm 0`; encima, 2.8.

La coplanaridad (fase 7c4, P88 a): si la referencia no esta paralela al tablero, su lado sale mal
en theta x L x tan(vista) (la media de los cuatro, hasta eso / raiz(2)), y la homografia no lo ve.
Cada frame da la pose IPPE de la referencia (con el `size_mm` del perfil) frente a la del
tablero (`pose_referencia`, `pose_tablero`, `coplanaridad`): el angulo entre las normales, la
vista y el sesgo estimado que la inclinacion mete en el lado. Una colocacion no vale si la
mediana de ese sesgo pasa de `MAX_SESGO_MM` (`decidir`).

Constantes:
- `CRITERIO_UNDISTORT`: 100 iteraciones o 1e-12; las 5 iteraciones por defecto de
  `undistortPoints` dejan un error que aqui se veria.
- `MIN_ESQUINAS` = 10 (P87 a): con la referencia encima y centrada se leen 12 esquinas del
  tablero (sus dos columnas de los extremos; la placa de 130 mm tapa el resto), menos dos de
  holgura. Esas 12 rodean la referencia: la homografia interpola. En la 7c3 eran 30 de 48.
- `MIN_ENCIERRO_MM` = 5 (P87 a, la puerta "encerrada"): las 4 esquinas de la referencia, a >= 5 mm
  dentro de la envolvente de las esquinas leidas (`encierro_mm`); si no, `"fuera_del_tablero"`.
- `MAX_SESGO_MM` = 0.05 (P88 a).
- `RADIO_MAX_PX` = 382: la distancia maxima, en px, del centro de la referencia al centro de la
  imagen. Sale del criterio 4 de la fase 7c3: a 30 cm de frente, con el conjunto corrido hacia una
  esquina, el radio en que una K desviada como la del diagnostico (fx y fy +11, cx -9.5, cy
  -7.3 px) mete mas de 0.03 mm (`tests/test_medir_referencia.py` lo recalcula). Es un tope
  grueso, no una garantia: a 40 y 55 cm ese error llega antes (295 y 315 px), y con el conjunto
  corrido hacia el lado del tablero crece aunque la referencia quede mas cerca del centro. Por
  eso cada frame da tambien `conjunto_px` (cuanto se aparta del centro de la imagen el centro de
  todo lo leido: ~0.001 mm de error por px con esa K a 30-40 cm) y la sesion pide centrar.
- `MIN_FRAMES` = 30 y `MAX_DIF_CAMARAS_MM` = 0.3: la regla de P77.
- `MAX_ERROR_MEDIANA_MM` = 0.02 y `FACTOR_MEDIANA` = 1.2533 (raiz(pi / 2)), P89 a: el error tipico
  de la mediana, 1.2533 x sd / raiz(n), sustituye a la sd entre frames <= 0.05 de P77. La sd real
  entre frames es 0.08-0.21 mm (el diagnostico de P9), no 0.012-0.016 como en el sintetico.

Lo que mide, medido en la fase 7c3 sobre escenas sinteticas: el refinado `CORNER_REFINE_SUBPIX`
del detector mete cada esquina del cuadro negro ~0.15 px hacia dentro sobre un borde suavizado,
asi que el lado sale ~0.10 mm por debajo del dibujado (de -0.04 a -0.13 mm entre 30 y 55 cm). Es
lo que ve el tracker en cada frame; depende del desenfoque y de la distancia.

La regla de P77 con P88 y P89 (`decidir`): la medida vale si cada colocacion de cada camara tiene
>= 30 frames validos, el error de su mediana <= 0.02 mm y |sesgo| <= 0.05 mm, y las dos camaras
difieren <= 0.3 mm. El valor es la media de las dos camaras, a 0.1 mm; se cambia el `size_mm`
solo si se aparta del nominal mas que U = sqrt(u_tablero^2 + (|gs1 - gs2| / 2)^2).
`u_tablero_mm` va explicito (principio 7): 0.14 mm sale de la resolucion del calibrador (0.1 mm:
+-0.05 por lectura, +-0.07 la resta B - A) sobre 51.9 mm, +-0.13 % de la casilla, y eso en un
lado de ~100 mm.

Uso (desde codigo\\, con el venv; argumentos explicitos, principio 7). La medida, con las dos
colocaciones de cada camara (P90 a: la segunda, girada 90 grados y el conjunto movido en la imagen):
    python -m calibration.medir_referencia --tablero data\\tablero_charuco.yaml ^
        --camara gs1_a profiles\\tracker_config_gs1.yaml <PNG gs1, colocacion a> ^
        --camara gs1_b profiles\\tracker_config_gs1.yaml <PNG gs1, colocacion b> ^
        --camara gs2_a profiles\\tracker_config_gs2.yaml <PNG gs2, colocacion a> ^
        --camara gs2_b profiles\\tracker_config_gs2.yaml <PNG gs2, colocacion b> ^
        --altura-mm 2.8 --u-tablero-mm 0.14 --salida <json> --timeout 300
La comprobacion de una colocacion (tras la vista previa; no aplica P77):
    python -m calibration.medir_referencia --tablero data\\tablero_charuco.yaml ^
        --camara gs1_a profiles\\tracker_config_gs1.yaml <PNG> --altura-mm 2.8 --u-tablero-mm 0.14 ^
        --salida <json> --timeout 60 --colocacion

`--camara ETIQUETA PERFIL CARPETA` se repite, una por colocacion; `decidir` agrupa por perfil (una
camara = un perfil). El nominal es el `size_mm` de la referencia del perfil: todos tienen que
decir lo mismo. Escribe el `.json` (no pisa), una linea `[Lado]` por colocacion y una
`[Decision]` (con `--colocacion`, una linea `[Colocacion]`). Codigos: 0 medida valida (cambie o
no; con `--colocacion`, la colocacion vale); 1 no valida (o no vale); 2 uso (la salida existe,
una carpeta sin PNG, un perfil sin `calibration_file`, un PNG de otra forma que la de los
intrinsecos, perfiles con distinto `size_mm`, el tablero sin medir, `--colocacion` con mas de un
`--camara`): no escribe nada; 4 salto el tope: escribe lo hecho y no decide.

Context7 (2026-11-12, `/websites/opencv`, documentacion 5.0; instalado 4.11.0, firmas comprobadas
con `__doc__`): `undistortPointsIter(src, cameraMatrix, distCoeffs, R, P, criteria) -> dst` (con
P vacia, coordenadas normalizadas; en 4.11 `undistortPoints` no admite `criteria` desde Python);
`findHomography(srcPoints, dstPoints[, method]) -> retval, mask` (metodo 0: minimos cuadrados
con todos los puntos, refinado con Levenberg-Marquardt; matriz vacia si no se puede estimar;
normalizada con h33 = 1); `solvePnP(objectPoints, imagePoints, cameraMatrix, distCoeffs, flags=
SOLVEPNP_IPPE) -> retval, rvec, tvec` (>= 4 puntos coplanares; imagePoints contiguos (N, 1, 2));
`perspectiveTransform(src (N, 1, 2), m 3x3) -> dst`. Fase 7c4 (2026-11-12, la misma fuente):
`solvePnPGeneric(..., flags=SOLVEPNP_IPPE_SQUARE) -> retval, rvecs, tvecs, reprojectionError`
(4 puntos en el orden (-s/2, s/2), (s/2, s/2), (s/2, -s/2), (-s/2, -s/2); dos soluciones);
`pointPolygonTest(contour, pt, measureDist=True)` (distancia con signo al borde: positiva dentro).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from calibration import charuco_board as chb   # antes de cv2: apaga la aceleracion HW de MSMF (CONTEXT 4.18)
import cv2
import numpy as np
import yaml

import profiles
from calibration.calibrate_extrinsics import leer_intrinsecos
from calibration.charuco_board import TableroCharuco
from vision.detection import create_detector, detect

TAG = "[medir_referencia]"
EXIT_OK, EXIT_NO_VALIDA, EXIT_USO, EXIT_TOPE = 0, 1, 2, 4
FORMATO = 1

CRITERIO_UNDISTORT = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 100, 1e-12)
MIN_ESQUINAS = 10               # P87 a: las 12 que se leen con la referencia encima y centrada, menos dos
MIN_ENCIERRO_MM = 5.0           # P87 a: las 4 esquinas de la referencia, dentro de la envolvente de las leidas
MAX_SESGO_MM = 0.05             # P88 a: lo que la inclinacion de la referencia puede meter en el lado
RADIO_MAX_PX = 382.0            # el criterio 4 de la fase 7c3, a 30 cm (ver el docstring y su prueba)
MIN_FRAMES = 30                 # P77
MAX_ERROR_MEDIANA_MM = 0.02     # P89 a: FACTOR_MEDIANA x sd / raiz(n)
FACTOR_MEDIANA = 1.2533         # raiz(pi / 2): el error tipico de la mediana de una normal, en sd / raiz(n)
MAX_DIF_CAMARAS_MM = 0.3        # P77
MOTIVOS = ("sin_tablero", "sin_referencia", "referencia_repetida", "fuera_del_tablero", "descentrada")
_EPS = 1e-9                     # holgura de las comparaciones de la regla (0.3 no es exacto en binario)


class TopeSuperado(TimeoutError):
    """El tope de `medir_carpeta`: `parcial` trae lo hecho hasta ese momento."""

    def __init__(self, mensaje: str, parcial: dict):
        super().__init__(mensaje)
        self.parcial = parcial


# ----------------------------------------------------------------------------
# La geometria
# ----------------------------------------------------------------------------

def _normalizadas(puntos_px, K, dist) -> np.ndarray:
    """Los puntos (N, 2) en px, en coordenadas normalizadas sin distorsion (N, 2) float64."""
    p = np.ascontiguousarray(np.asarray(puntos_px, dtype=np.float64).reshape(-1, 1, 2))
    d = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64).flatten()
    return cv2.undistortPointsIter(p, np.asarray(K, dtype=np.float64), d, None, None, CRITERIO_UNDISTORT).reshape(-1, 2)


def _similitud(p: np.ndarray) -> np.ndarray:
    """La normalizacion de Hartley de unos puntos (N, 2): centro en el origen y distancia media raiz de 2."""
    c = p.mean(axis=0)
    s = math.sqrt(2.0) / max(float(np.mean(np.linalg.norm(p - c, axis=1))), 1e-300)
    return np.array([[s, 0.0, -s * c[0]], [0.0, s, -s * c[1]], [0.0, 0.0, 1.0]])


def _homografia(obj: np.ndarray, img: np.ndarray) -> np.ndarray:
    """La homografia (3x3, float64) que lleva `obj` (N, 2) a `img` (N, 2) con el menor error de
    reproyeccion: `findHomography` (metodo 0) y, sobre su resultado, Gauss-Newton en float64 con
    las dos nubes normalizadas. El pulido hace falta para la exactitud, no para el ruido:
    `findHomography` sola deja ~1e-5 mm de error con puntos exactos (medido en la fase; trabaja
    en float32) y con el pulido queda en ~1e-11. ValueError si no se puede estimar."""
    H0, _mask = cv2.findHomography(np.ascontiguousarray(obj.reshape(-1, 1, 2)), np.ascontiguousarray(img.reshape(-1, 1, 2)), 0)
    if H0 is None or np.asarray(H0).shape != (3, 3) or not np.all(np.isfinite(H0)):
        raise ValueError("la homografia tablero -> imagen no se pudo estimar (esquinas en linea o degeneradas)")
    To, Ti = _similitud(obj), _similitud(img)
    Hn = Ti @ np.asarray(H0, dtype=np.float64) @ np.linalg.inv(To)
    if abs(Hn[2, 2]) < 1e-12:
        raise ValueError("la homografia tablero -> imagen es degenerada")
    h = (Hn / Hn[2, 2]).flatten()[:8]
    x, y = (To[0, 0] * obj[:, 0] + To[0, 2]), (To[1, 1] * obj[:, 1] + To[1, 2])
    u0, v0 = (Ti[0, 0] * img[:, 0] + Ti[0, 2]), (Ti[1, 1] * img[:, 1] + Ti[1, 2])
    cero, uno = np.zeros_like(x), np.ones_like(x)
    for _ in range(20):
        w = h[6] * x + h[7] * y + 1.0
        u, v = (h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w
        J = np.vstack([np.column_stack([x / w, y / w, uno / w, cero, cero, cero, -u * x / w, -u * y / w]),
                       np.column_stack([cero, cero, cero, x / w, y / w, uno / w, -v * x / w, -v * y / w])])
        paso = np.linalg.lstsq(J, -np.concatenate([u - u0, v - v0]), rcond=None)[0]
        h = h + paso
        if float(np.max(np.abs(paso))) < 1e-15:
            break
    H = np.linalg.inv(Ti) @ np.append(h, 1.0).reshape(3, 3) @ To
    if not np.all(np.isfinite(H)) or abs(np.linalg.det(H)) < 1e-18:
        raise ValueError("la homografia tablero -> imagen no se pudo estimar (esquinas en linea o degeneradas)")
    return H


def lados_en_plano(esq_ref_px: np.ndarray, esq_tab_px: np.ndarray, ids_tab: np.ndarray, t: TableroCharuco,
                   K: np.ndarray, dist: np.ndarray) -> dict:
    """Las 4 esquinas de la referencia (`esq_ref_px`, en el orden del detector) llevadas al plano
    del tablero `t` por la homografia que ajustan las esquinas del tablero (`esq_tab_px` con sus
    `ids_tab`), en mm del tablero.

    Devuelve `lados_mm` (4: de la esquina i a la i + 1, en el orden del detector), `diagonales_mm`
    (2: 0-2 y 1-3), `centro_mm` (x, y), `esquinas_mm` (4, 2) y `residuo_px` (el RMS de la
    homografia sobre las esquinas del tablero, en px con fx). No corrige la altura. ValueError
    con menos de 4 esquinas del tablero, si la referencia no trae 4 o si la homografia no sale.
    """
    ref = np.asarray(esq_ref_px, dtype=np.float64).reshape(-1, 2)
    tab = np.asarray(esq_tab_px, dtype=np.float64).reshape(-1, 2)
    ids = np.asarray(ids_tab).flatten().astype(int)
    if ref.shape[0] != 4:
        raise ValueError(f"la referencia tiene que traer 4 esquinas, no {ref.shape[0]}")
    if tab.shape[0] < 4 or tab.shape[0] != ids.size:
        raise ValueError(f"hacen falta >= 4 esquinas del tablero con su ID, no {tab.shape[0]} esquinas y {ids.size} IDs")
    obj = np.ascontiguousarray(chb.puntos_objeto(t, ids)[:, :2].astype(np.float64))
    n_tab = _normalizadas(tab, K, dist)
    n_ref = _normalizadas(ref, K, dist)
    H = _homografia(obj, n_tab)
    reproy = cv2.perspectiveTransform(obj.reshape(-1, 1, 2), H).reshape(-1, 2)
    residuo = float(np.sqrt(np.mean(np.sum((reproy - n_tab) ** 2, axis=1))) * float(np.asarray(K)[0, 0]))
    p = cv2.perspectiveTransform(np.ascontiguousarray(n_ref.reshape(-1, 1, 2)), np.linalg.inv(H)).reshape(4, 2)
    lados = np.array([np.linalg.norm(p[(i + 1) % 4] - p[i]) for i in range(4)])
    diagonales = np.array([np.linalg.norm(p[2] - p[0]), np.linalg.norm(p[3] - p[1])])
    return {"lados_mm": lados, "diagonales_mm": diagonales, "centro_mm": p.mean(axis=0), "esquinas_mm": p,
            "residuo_px": residuo}


def pose_tablero(esq_tab_px: np.ndarray, ids_tab: np.ndarray, t: TableroCharuco, K: np.ndarray,
                 dist: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """La pose del tablero en la camara, `(R (3, 3), t (3,))`, en mm: `solvePnP` con `SOLVEPNP_IPPE`
    sobre sus esquinas leidas. Los ejes son los de `charuco_board.puntos_objeto`: x a la derecha,
    y hacia abajo y z hacia dentro del tablero (su normal `R[:, 2]` se aleja de la camara).
    ValueError con menos de 4 esquinas o si no hay pose."""
    tab = np.ascontiguousarray(np.asarray(esq_tab_px, dtype=np.float64).reshape(-1, 1, 2))
    ids = np.asarray(ids_tab).flatten().astype(int)
    if tab.shape[0] < 4 or tab.shape[0] != ids.size:
        raise ValueError(f"hacen falta >= 4 esquinas del tablero con su ID, no {tab.shape[0]} esquinas y {ids.size} IDs")
    obj = np.ascontiguousarray(chb.puntos_objeto(t, ids).astype(np.float64))
    d = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64).flatten()
    ok, rvec, tvec = cv2.solvePnP(obj, tab, np.asarray(K, dtype=np.float64), d, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        raise ValueError("solvePnP no dio la pose del tablero")
    R, _ = cv2.Rodrigues(rvec)
    return R, np.asarray(tvec, dtype=np.float64).reshape(3)


def distancia_al_plano(esq_tab_px: np.ndarray, ids_tab: np.ndarray, t: TableroCharuco, K: np.ndarray,
                       dist: np.ndarray) -> float:
    """La distancia, en mm, del centro de la camara al plano del tablero: la pose de
    `pose_tablero` y d = |R[:, 2] . t|. Solo entra en la correccion de altura (un 1 % de
    error en d mueve el lado 0.01 x altura x lado / d: nada). ValueError si no hay pose."""
    R, tv = pose_tablero(esq_tab_px, ids_tab, t, K, dist)
    return float(abs(R[:, 2] @ tv))


def pose_referencia(esq_ref_px: np.ndarray, lado_mm: float, K: np.ndarray, dist: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """La pose de la referencia en la camara, `(R (3, 3), t (3,), razon)`, con `solvePnPGeneric` y
    `SOLVEPNP_IPPE_SQUARE` sobre sus 4 esquinas (el orden del detector, que es el de la
    documentacion y el de `vision.pose.build_object_points`: (-s/2, s/2), (s/2, s/2), (s/2, -s/2),
    (-s/2, -s/2); el origen es el centro del marker y su normal `R[:, 2]` mira a la camara). De
    las dos soluciones de IPPE, la de menor error de reproyeccion con t[2] > 0; `razon` es el
    error de la otra entre el de la elegida (cuanto mas alta, menos ambigua; `math.inf` si solo
    hay una). ValueError si no trae 4 esquinas, si `lado_mm` no es > 0 o si no hay ninguna."""
    ref = np.asarray(esq_ref_px, dtype=np.float64).reshape(-1, 2)
    if ref.shape[0] != 4:
        raise ValueError(f"la referencia tiene que traer 4 esquinas, no {ref.shape[0]}")
    if not float(lado_mm) > 0:
        raise ValueError(f"lado_mm tiene que ser > 0, no {lado_mm}")
    h = float(lado_mm) / 2.0
    obj = np.array([[-h, h, 0.0], [h, h, 0.0], [h, -h, 0.0], [-h, -h, 0.0]], dtype=np.float64)
    d = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64).flatten()
    try:
        _n, rvecs, tvecs, errs = cv2.solvePnPGeneric(obj, np.ascontiguousarray(ref.reshape(4, 1, 2)),
                                                     np.asarray(K, dtype=np.float64), d, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    except cv2.error as e:
        raise ValueError(f"solvePnPGeneric no dio la pose de la referencia: {e}") from None
    sols = sorted(((float(e), cv2.Rodrigues(rv)[0], np.asarray(tv, dtype=np.float64).reshape(3))
                   for rv, tv, e in zip(rvecs, tvecs, np.asarray(errs, dtype=np.float64).flatten())
                   if float(np.asarray(tv).reshape(3)[2]) > 0), key=lambda s: s[0])
    if not sols:
        raise ValueError("solvePnPGeneric no dio ninguna pose de la referencia delante de la camara")
    razon = sols[1][0] / max(sols[0][0], 1e-12) if len(sols) > 1 else math.inf
    return sols[0][1], sols[0][2], float(razon)


def aspecto_propio(esq_ref_px: np.ndarray, K: np.ndarray, dist: np.ndarray) -> tuple[float, float]:
    """La razon de lados de la referencia y el angulo entre ellos, en grados, solo con sus 4
    esquinas y K (sin el tablero): la homografia del cuadrado unidad a sus esquinas normalizadas
    es lambda [a r1, b r2, t], asi que a / b = |h1| / |h2| y el angulo es el de h1 con h2. Un
    cuadrado da (1, 90). Informativo: dice si lo que se ve es un cuadrado inclinado o un
    rectangulo. La homografia sale de `_homografia` (float64): `getPerspectiveTransform` trabaja
    en float32 y deja ~1e-6. ValueError si no trae 4 esquinas o son degeneradas."""
    ref = np.asarray(esq_ref_px, dtype=np.float64).reshape(-1, 2)
    if ref.shape[0] != 4:
        raise ValueError(f"la referencia tiene que traer 4 esquinas, no {ref.shape[0]}")
    H = _homografia(np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]), _normalizadas(ref, K, dist))
    h1, h2 = H[:, 0], H[:, 1]
    n1, n2 = float(np.linalg.norm(h1)), float(np.linalg.norm(h2))
    if not (n1 > 0 and n2 > 0):
        raise ValueError("las esquinas de la referencia son degeneradas")
    return n1 / n2, math.degrees(math.acos(float(np.clip(h1 @ h2 / (n1 * n2), -1.0, 1.0))))


def _normal_hacia_camara(R: np.ndarray, tv: np.ndarray) -> np.ndarray:
    """La normal del plano z = 0 de una pose (`R[:, 2]`), con el signo que mira a la camara."""
    n = np.asarray(R, dtype=np.float64)[:, 2]
    return -n if float(n @ tv) > 0 else n.copy()


def coplanaridad(R_tab: np.ndarray, t_tab: np.ndarray, R_ref: np.ndarray, t_ref: np.ndarray, lado_mm: float,
                 altura_mm: float) -> dict:
    """Cuanto se aparta la referencia de estar paralela al tablero y cuanto mete eso en el lado
    (P88). Entran la pose del tablero (`pose_tablero`), la de la referencia (`pose_referencia`,
    hecha con `lado_mm`) y `altura_mm` (la cara de la referencia sobre la del tablero).

    - `angulo_normales_deg`: el angulo entre las dos normales, las dos mirando a la camara.
    - `vista_deg`: el angulo entre el rayo al centro de la referencia y la normal del tablero (la
      oblicuidad con que se la ve).
    - `sesgo_mm`: lo que la inclinacion mete en el lado. El plano de la medida es el paralelo al
      tablero a `altura_mm` hacia la camara (donde tiene que estar el centro de la referencia).
      Las 4 esquinas de la pose IPPE se llevan por sus rayos a ese plano y se toma su lado
      medio; se le resta el del mismo cuadrado sin inclinar (paralelo al tablero, con el mismo
      centro), llevado igual: `lado_coplanar_mm`. Los dos estan en la escala del tablero, la del
      lado medido, y no dependen de `lado_mm` (la pose IPPE escala entera con el). A primer
      orden vale theta x L x tan(vista) x cos(phi) / 2, con phi el angulo entre la pendiente y la
      vista sobre el plano: |sesgo| <= theta x L x tan(vista) / 2 (y por tanto <= .../raiz(2)).
    - `lado_coplanar_mm`: el lado que pone el centro de la referencia en ese plano, `lado_mm` x
      lambda / |t_ref| (el contraste IPPE del diagnostico de P9). Depende de la profundidad de la
      pose, que es su eje debil: informativo.

    ValueError si `lado_mm` no es > 0 o si algun rayo no corta el plano delante de la camara."""
    if not float(lado_mm) > 0:
        raise ValueError(f"lado_mm tiene que ser > 0, no {lado_mm}")
    R_t, t_t = np.asarray(R_tab, dtype=np.float64), np.asarray(t_tab, dtype=np.float64).reshape(3)
    R_r, t_r = np.asarray(R_ref, dtype=np.float64), np.asarray(t_ref, dtype=np.float64).reshape(3)
    n_t, n_r = _normal_hacia_camara(R_t, t_t), _normal_hacia_camara(R_r, t_r)
    dist_ref = float(np.linalg.norm(t_r))
    c = float(n_t @ t_t) + float(altura_mm)           # el plano de la medida: n_t . X = c (c < 0: delante de la camara)
    h = float(lado_mm) / 2.0
    obj = np.array([[-h, h, 0.0], [h, h, 0.0], [h, -h, 0.0], [-h, -h, 0.0]])
    X = (R_r @ obj.T).T + t_r
    den = np.append(X @ n_t, float(n_t @ t_r))
    if not (c < 0 and dist_ref > 0 and np.all(den < 0)):
        raise ValueError("el plano de la medida no queda delante de la camara en los rayos de la referencia")
    P = X * (c / den[:4])[:, None]
    lado_proyectado = float(np.mean([np.linalg.norm(P[(i + 1) % 4] - P[i]) for i in range(4)]))
    lado_coplanar = float(lado_mm) * (c / den[4])     # lambda / |t_ref|, con lambda sobre el rayo al centro
    return {"angulo_normales_deg": math.degrees(math.acos(float(np.clip(n_t @ n_r, -1.0, 1.0)))),
            "vista_deg": math.degrees(math.acos(min(1.0, abs(float(n_t @ t_r)) / dist_ref))),
            "sesgo_mm": lado_proyectado - lado_coplanar, "lado_coplanar_mm": lado_coplanar}


def encierro_mm(esq_ref_mm: np.ndarray, ids_tab: np.ndarray, t: TableroCharuco) -> float:
    """Cuanto queda la referencia dentro de las esquinas leidas del tablero (P87, "encerrada"): la
    menor distancia con signo, en mm, de sus 4 esquinas ya en mm del tablero (`esquinas_mm` de
    `lados_en_plano`) al borde de la envolvente convexa de las esquinas `ids_tab`
    (`puntos_objeto`, `convexHull`, `pointPolygonTest` con `measureDist`). Positiva dentro: la
    homografia interpola; negativa fuera: extrapola. No corrige la altura: con la referencia a
    2.8 mm sobre el tablero, sus esquinas caen hasta altura x tan(vista) corridas (< 3 mm a
    45 grados). ValueError con menos de 3 esquinas del tablero o si la referencia no trae 4."""
    ref = np.asarray(esq_ref_mm, dtype=np.float64).reshape(-1, 2)
    ids = np.asarray(ids_tab).flatten().astype(int)
    if ref.shape[0] != 4:
        raise ValueError(f"la referencia tiene que traer 4 esquinas, no {ref.shape[0]}")
    if ids.size < 3:
        raise ValueError(f"hacen falta >= 3 esquinas del tablero para la envolvente, no {ids.size}")
    hull = cv2.convexHull(np.ascontiguousarray(chb.puntos_objeto(t, ids)[:, :2].astype(np.float32)))
    return float(min(cv2.pointPolygonTest(hull, (float(x), float(y)), True) for x, y in ref))


def corregir_altura(lados_mm: np.ndarray, d_mm: float, altura_mm: float) -> np.ndarray:
    """`lados_mm` x (`d_mm` - `altura_mm`) / `d_mm`: los lados reales de una figura que esta
    `altura_mm` mas cerca de la camara que el plano en que se midio (`altura_mm` > 0 si la cara de
    la referencia queda mas alta que la del tablero). ValueError si |altura_mm| >= d_mm."""
    d, h = float(d_mm), float(altura_mm)
    if not d > 0 or abs(h) >= d:
        raise ValueError(f"la altura ({h:g} mm) tiene que ser menor que la distancia al plano ({d:g} mm), y esta > 0")
    return np.asarray(lados_mm, dtype=np.float64) * (d - h) / d


# ----------------------------------------------------------------------------
# Un frame y una carpeta
# ----------------------------------------------------------------------------

CAMPOS_7C4 = ("angulo_normales_deg", "sesgo_mm", "vista_deg", "lado_coplanar_mm", "razon_ippe", "aspecto",
              "angulo_propio_deg", "encierro_mm", "centro_tablero_mm", "giro_deg", "conjunto_xy_px")


def medir_frame(gray: np.ndarray, det_ref, ref_id: int, det_tab, t: TableroCharuco, K, dist, altura_mm: float,
                min_esquinas: int, radio_max_px: float, lado_nominal_mm: float, *,
                min_encierro_mm: float = MIN_ENCIERRO_MM) -> dict:
    """El lado de la referencia en un frame en gris.

    La referencia se detecta con el detector del perfil (`vision.detection.detect(det_ref, gray,
    {ref_id})`: la misma lista blanca y el mismo refinado que el tracker) y el tablero con
    `charuco_board.detectar_charuco`. Devuelve `lado_mm` (la media de los cuatro lados, con la
    altura corregida), `lados_mm` (4), `diagonales_mm` (2), `d_mm`, `residuo_px`, `radio_px` (del
    centro de la referencia al centro de la imagen), `conjunto_px` (del centro de la caja que
    encierra las esquinas leidas del tablero y las de la referencia al centro de la imagen: un
    numero, no descarta) y `conjunto_xy_px` (ese desplazamiento, x e y), `n_esquinas` y `motivo`.

    Desde la fase 7c4 (P87, P88), ademas: la pose IPPE de la referencia con `lado_nominal_mm` (el
    `size_mm` del perfil) y la del tablero dan `angulo_normales_deg`, `sesgo_mm`, `vista_deg` y
    `lado_coplanar_mm` (`coplanaridad`) y `razon_ippe`; `aspecto` y `angulo_propio_deg`
    (`aspecto_propio`); `encierro_mm` (`encierro_mm`), `centro_tablero_mm` (x, y: el centro de la
    referencia en mm del tablero) y `giro_deg` (el angulo del lado 0 de la referencia frente al eje
    x del tablero, de -180 a 180).

    `motivo`: `None` si vale, o, por este orden, `"sin_tablero"` (menos de `min_esquinas`
    esquinas), `"sin_referencia"` (o su pose no sale), `"referencia_repetida"` (el ID dos o mas
    veces: B39), `"fuera_del_tablero"` (`encierro_mm` < `min_encierro_mm`: la homografia
    extrapola; P87 a) o `"descentrada"` (`radio_px` > `radio_max_px`). Los dos ultimos se miden
    igual, pero no cuentan. `min_encierro_mm` = -inf apaga la puerta (la geometria de la 7c3, con
    la referencia al lado del tablero). Lo que no se pudo medir queda en `None`.
    """
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("el frame no es una imagen en gris de 8 bits")
    out: dict = {"motivo": None, "lado_mm": None, "lados_mm": None, "diagonales_mm": None, "d_mm": None,
                 "residuo_px": None, "radio_px": None, "conjunto_px": None, "n_esquinas": 0, "n_referencias": 0,
                 **{c: None for c in CAMPOS_7C4}}
    r = chb.detectar_charuco(gray, det_tab, t, min_esquinas)
    if r is not None:
        out["n_esquinas"] = int(len(r[1]))
    corners, ids = detect(det_ref, gray, {int(ref_id)})
    n_ref = 0 if ids is None else int(len(ids))
    out["n_referencias"] = n_ref
    if n_ref >= 1:
        h, w = gray.shape
        centro = np.asarray(corners[0], dtype=np.float64).reshape(4, 2).mean(axis=0)
        if n_ref == 1:
            out["radio_px"] = float(np.linalg.norm(centro - np.array([(w - 1) / 2.0, (h - 1) / 2.0])))
    if r is None:
        out["motivo"] = "sin_tablero"
        return out
    if n_ref == 0:
        out["motivo"] = "sin_referencia"
        return out
    if n_ref >= 2:
        out["motivo"] = "referencia_repetida"
        return out
    esq_tab, ids_tab = r
    esq_ref = np.asarray(corners[0], dtype=np.float64).reshape(4, 2)
    todos = np.vstack([esq_tab, esq_ref])
    desplazado = (todos.min(axis=0) + todos.max(axis=0)) / 2.0 - np.array([(gray.shape[1] - 1) / 2.0, (gray.shape[0] - 1) / 2.0])
    out["conjunto_px"] = float(np.linalg.norm(desplazado))
    out["conjunto_xy_px"] = [float(desplazado[0]), float(desplazado[1])]
    try:
        m = lados_en_plano(esq_ref, esq_tab, ids_tab, t, K, dist)
        R_tab, t_tab = pose_tablero(esq_tab, ids_tab, t, K, dist)
    except ValueError:
        out["motivo"] = "sin_tablero"
        return out
    d_mm = float(abs(R_tab[:, 2] @ t_tab))
    lados = corregir_altura(m["lados_mm"], d_mm, altura_mm)
    p = m["esquinas_mm"]
    out.update({"lado_mm": float(lados.mean()), "lados_mm": [float(x) for x in lados],
                "diagonales_mm": [float(x) for x in corregir_altura(m["diagonales_mm"], d_mm, altura_mm)],
                "d_mm": d_mm, "residuo_px": float(m["residuo_px"]),
                "encierro_mm": encierro_mm(p, ids_tab, t),
                "centro_tablero_mm": [float(m["centro_mm"][0]), float(m["centro_mm"][1])],
                "giro_deg": math.degrees(math.atan2(float(p[1, 1] - p[0, 1]), float(p[1, 0] - p[0, 0])))})
    try:
        R_ref, t_ref, razon = pose_referencia(esq_ref, lado_nominal_mm, K, dist)
        cop = coplanaridad(R_tab, t_tab, R_ref, t_ref, lado_nominal_mm, altura_mm)
        asp, ang = aspecto_propio(esq_ref, K, dist)
    except ValueError:
        out["motivo"] = "sin_referencia"
        return out
    out.update({**{k: float(v) for k, v in cop.items()}, "razon_ippe": float(razon) if math.isfinite(razon) else None, "aspecto": float(asp),
                "angulo_propio_deg": float(ang)})
    if out["encierro_mm"] < min_encierro_mm:
        out["motivo"] = "fuera_del_tablero"
    elif out["radio_px"] > radio_max_px:
        out["motivo"] = "descentrada"
    return out


def frames_de(carpeta: Path) -> list[Path]:
    """Los `frame_*.png` de `carpeta`, ordenados."""
    return sorted(Path(carpeta).glob("frame_*.png"))


def error_mediana(sd_mm: float | None, n: int) -> float | None:
    """El error tipico de la mediana de `n` frames con sd `sd_mm` entre ellos (P89 a):
    `FACTOR_MEDIANA` x sd / raiz(n), el de una normal. None con n < 2 o sin sd."""
    if sd_mm is None or int(n) < 2:
        return None
    return FACTOR_MEDIANA * float(sd_mm) / math.sqrt(int(n))


def _giro_medio(giros: list[float]) -> float:
    """La media circular de unos angulos en grados (de -180 a 180): la mediana no vale cerca de +-180."""
    a = np.radians(np.asarray(giros, dtype=np.float64))
    return math.degrees(math.atan2(float(np.mean(np.sin(a))), float(np.mean(np.cos(a)))))


def _medianas_7c4(frames: list[dict]) -> dict:
    """Las medianas de los campos de la fase 7c4 sobre `frames` (los que los traen); `giro_deg`, la
    media circular; `n_esquinas`, la mediana de todos."""
    out: dict = {"n_esquinas": float(np.median([f["n_esquinas"] for f in frames])) if frames else None}
    for c in CAMPOS_7C4:
        v = [f[c] for f in frames if f.get(c) is not None]
        if not v:
            out[c] = None
        elif c == "giro_deg":
            out[c] = _giro_medio(v)
        elif c in ("centro_tablero_mm", "conjunto_xy_px"):
            out[c] = [float(x) for x in np.median(np.asarray(v, dtype=np.float64), axis=0)]
        else:
            out[c] = float(np.median(v))
    return out


def _resumen(frames: list[dict]) -> dict:
    """El resumen de los frames validos (`motivo` None) de una colocacion; desde la fase 7c4, con
    `error_mediana_mm` (P89) y las medianas de los campos nuevos (`_medianas_7c4`), sobre los validos."""
    validos = [f for f in frames if f["motivo"] is None]
    motivos = {m: sum(1 for f in frames if f["motivo"] == m) for m in MOTIVOS}
    out = {"n_frames": len(frames), "n_validos": len(validos), "motivos": motivos,
           "lado_mediana_mm": None, "sd_frames_mm": None, "error_mediana_mm": None, "lados_medios_mm": None,
           "sd_lados_mm": None, "dif_diagonales_mm": None, "d_mm": None, "radio_px": None, "conjunto_px": None,
           "residuo_px": None, **_medianas_7c4(validos)}
    if not validos:
        return out
    lado = np.array([f["lado_mm"] for f in validos])
    lados = np.array([f["lados_mm"] for f in validos])
    diag = np.array([f["diagonales_mm"] for f in validos])
    medios = lados.mean(axis=0)
    out.update({
        "lado_mediana_mm": float(np.median(lado)),
        "sd_frames_mm": float(lado.std(ddof=1)) if len(validos) >= 2 else None,
        "lados_medios_mm": [float(x) for x in medios],
        "sd_lados_mm": float(medios.std(ddof=1)),
        "dif_diagonales_mm": float(diag[:, 0].mean() - diag[:, 1].mean()),
        "d_mm": float(np.median([f["d_mm"] for f in validos])),
        "radio_px": float(np.median([f["radio_px"] for f in validos])),
        "conjunto_px": float(np.median([f["conjunto_px"] for f in validos])),
        "residuo_px": float(np.percentile([f["residuo_px"] for f in validos], 95)),
    })
    out["error_mediana_mm"] = error_mediana(out["sd_frames_mm"], len(validos))
    return out


def medir_carpeta(dir_frames: Path, perfil: dict, t: TableroCharuco, altura_mm: float, min_esquinas: int,
                  radio_max_px: float, clock=time.perf_counter, tope_s: float | None = None, *,
                  min_encierro_mm: float = MIN_ENCIERRO_MM) -> dict:
    """`medir_frame` sobre los `frame_*.png` de `dir_frames`, con el perfil ya cargado
    (`profiles.load`): el ID de la referencia y su `size_mm` (el lado de la pose IPPE) salen de
    `profiles.reference_marker`, el detector de `markers` y K y dist de `camera.calibration_file`.

    Devuelve `frames` (uno por PNG, con su `nombre` y su `motivo`), `motivos` (cuantos de cada
    uno), `n_frames`, `n_validos` y el resumen de los validos: `lado_mediana_mm`, `sd_frames_mm`
    (sd entre frames, n - 1), `lados_medios_mm` (4) y `sd_lados_mm` (la sd de esos cuatro),
    `dif_diagonales_mm` (la cuadratura: media de la diagonal 0-2 menos la de la 1-3), `d_mm`,
    `radio_px` y `conjunto_px` (medianas) y `residuo_px` (p95). ValueError si la carpeta no tiene PNG, el perfil
    no trae `calibration_file` o un PNG no es gris de 8 bits o no tiene la forma de los
    intrinsecos. Con `tope_s`, `TopeSuperado` (un `TimeoutError`) con lo hecho en `parcial`.
    """
    d = Path(dir_frames)
    pngs = frames_de(d) if d.is_dir() else []
    if not pngs:
        raise ValueError(f"no hay frame_*.png en {d}")
    cfg_markers = perfil.get("markers") or {}
    ref = profiles.reference_marker(cfg_markers.get("list"))
    ruta_k = (perfil.get("camera") or {}).get("calibration_file")
    if not ruta_k:
        raise ValueError("el perfil no trae camera.calibration_file")
    intr = leer_intrinsecos(ruta_k)
    K, dist = intr["K"], intr["dist"]
    with contextlib.redirect_stdout(io.StringIO()):          # create_detector imprime sus parametros
        det_ref = create_detector(cfg_markers)
    det_tab = chb.detector(t)
    base = {"carpeta": str(d), "ref_id": int(ref["id"]), "intrinsecos": Path(ruta_k).name,
            "altura_mm": float(altura_mm), "min_esquinas": int(min_esquinas), "radio_max_px": float(radio_max_px),
            "min_encierro_mm": float(min_encierro_mm) if math.isfinite(min_encierro_mm) else None,
            "lado_nominal_mm": float(ref["size_mm"])}
    frames: list[dict] = []
    t0 = clock()
    for k, png in enumerate(pngs):
        if tope_s is not None and clock() - t0 > tope_s:
            parcial = {**base, "completo": False, "frames_sin_leer": len(pngs) - k, "frames": frames, **_resumen(frames)}
            raise TopeSuperado(f"tope de {tope_s:g} s en {d.name}: {k} de {len(pngs)} frames leidos", parcial)
        gray = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
        if gray is None or gray.ndim != 2 or gray.dtype != np.uint8:
            raise ValueError(f"{png}: no es una imagen en gris de 8 bits")
        if intr["shape"] is not None and tuple(gray.shape[::-1]) != tuple(intr["shape"]):
            raise ValueError(f"{png.name} mide {gray.shape[1]} x {gray.shape[0]} y los intrinsecos "
                             f"({Path(ruta_k).name}) son de {intr['shape'][0]} x {intr['shape'][1]}")
        f = medir_frame(gray, det_ref, int(ref["id"]), det_tab, t, K, dist, altura_mm, min_esquinas, radio_max_px,
                        float(ref["size_mm"]), min_encierro_mm=min_encierro_mm)
        frames.append({"nombre": png.name, **f})
    return {**base, "completo": True, "frames_sin_leer": 0, "frames": frames, **_resumen(frames)}


# ----------------------------------------------------------------------------
# La regla de P77
# ----------------------------------------------------------------------------

def _a_decima(x: float) -> float:
    """`x` redondeado a 0.1 (el medio, hacia arriba)."""
    return math.floor(float(x) * 10.0 + 0.5) / 10.0


def decidir(por_camara: dict[str, list[dict]], nominal_mm: float, u_tablero_mm: float, min_frames: int,
            max_error_mediana_mm: float, max_dif_mm: float, max_sesgo_mm: float) -> dict:
    """La regla de P77, con P88 y P89 (fase 7c4), sobre los resumenes de `medir_carpeta`.
    `por_camara` da, por camara (la clave es su perfil), la lista de los resumenes de sus
    colocaciones (una, o dos con P80 a / P90 a).

    Cada camara da la media de las medianas de sus colocaciones (`lado_mm`) y, con dos, su
    diferencia como numero (`dif_colocaciones_mm`). `valida`: hay exactamente dos camaras; cada
    colocacion tiene >= `min_frames` frames validos, el error de su mediana (`error_mediana`, con
    `sd_frames_mm` y `n_validos`) <= `max_error_mediana_mm` (P89) y la mediana de su `sesgo_mm`
    en valor absoluto <= `max_sesgo_mm` (P88; "inclinada" si no, o "sin sesgo" si no lo trae);
    y las dos camaras difieren <= `max_dif_mm`. Si no, `motivo` dice por que. `valor_mm`: la media
    de las dos camaras, a 0.1 mm. `dif_camaras_mm`. `u_mm` = sqrt(`u_tablero_mm`^2 + (dif / 2)^2).
    `cambiar`: valida y |`valor_mm` - `nominal_mm`| > `u_mm`. Los numeros se dan tambien cuando
    no es valida, si se pueden calcular.
    """
    if not u_tablero_mm > 0 or not nominal_mm > 0:
        raise ValueError(f"u_tablero_mm y nominal_mm tienen que ser > 0, no {u_tablero_mm} y {nominal_mm}")
    motivos: list[str] = []
    camaras: dict[str, dict] = {}
    for cam, resumenes in por_camara.items():
        medianas, ns, sds, errores, sesgos = [], [], [], [], []
        for k, r in enumerate(resumenes):
            n, sd, med = int(r.get("n_validos") or 0), r.get("sd_frames_mm"), r.get("lado_mediana_mm")
            err, sesgo = error_mediana(sd, n), r.get("sesgo_mm")
            ns.append(n)
            sds.append(sd)
            errores.append(err)
            sesgos.append(sesgo)
            donde = f"{cam}, colocacion {k + 1}"
            if n < min_frames:
                motivos.append(f"{donde}: {n} frames validos (minimo {min_frames})")
            elif err is None or err > max_error_mediana_mm + _EPS:
                motivos.append(f"{donde}: error de la mediana {'-' if err is None else format(err, '.4f')} mm "
                               f"(n {n}, sd {'-' if sd is None else format(sd, '.3f')}; maximo {max_error_mediana_mm:g})")
            if n >= 1 and sesgo is None:
                motivos.append(f"{donde}: sin sesgo de coplanaridad")
            elif sesgo is not None and abs(sesgo) > max_sesgo_mm + _EPS:
                ang = r.get("angulo_normales_deg")
                motivos.append(f"{donde}: inclinada: sesgo {sesgo:+.3f} mm, angulo "
                               f"{'-' if ang is None else format(ang, '.2f')} grados (maximo {max_sesgo_mm:g} mm)")
            if med is not None:
                medianas.append(float(med))
        if not resumenes:
            motivos.append(f"{cam}: sin colocaciones")
        camaras[cam] = {"medianas_mm": medianas, "n_validos": ns, "sd_frames_mm": sds, "error_mediana_mm": errores,
                        "sesgo_mm": sesgos,
                        "lado_mm": float(np.mean(medianas)) if medianas and len(medianas) == len(resumenes) else None,
                        "dif_colocaciones_mm": float(max(medianas) - min(medianas)) if len(medianas) >= 2 else None}
    out = {"regla": "P77 (P88, P89)", "nominal_mm": float(nominal_mm), "u_tablero_mm": float(u_tablero_mm),
           "min_frames": int(min_frames), "max_error_mediana_mm": float(max_error_mediana_mm),
           "max_sesgo_mm": float(max_sesgo_mm), "max_dif_camaras_mm": float(max_dif_mm),
           "por_camara": camaras, "dif_camaras_mm": None, "valor_mm": None, "u_mm": None}
    lados = [c["lado_mm"] for c in camaras.values()]
    if len(camaras) != 2:
        motivos.append(f"hacen falta dos camaras (dos perfiles), no {len(camaras)}")
    elif None not in lados:
        dif = abs(lados[0] - lados[1])
        out["dif_camaras_mm"] = float(dif)
        out["valor_mm"] = _a_decima((lados[0] + lados[1]) / 2.0)
        out["u_mm"] = float(math.sqrt(u_tablero_mm ** 2 + (dif / 2.0) ** 2))
        if dif > max_dif_mm + _EPS:
            motivos.append(f"las dos camaras difieren {dif:.3f} mm (maximo {max_dif_mm:g})")
    out["valida"] = not motivos
    out["motivo"] = "; ".join(motivos) if motivos else None
    out["cambiar"] = bool(out["valida"] and abs(out["valor_mm"] - nominal_mm) > out["u_mm"])
    return out


def _direccion(dx: float, dy: float, minimo_px: float = 20.0) -> str:
    """Hacia donde queda un desplazamiento en la imagen (y hacia abajo), en palabras."""
    v = ("arriba" if dy < 0 else "abajo") if abs(dy) >= minimo_px else ""
    h = ("la izquierda" if dx < 0 else "la derecha") if abs(dx) >= minimo_px else ""
    return " a ".join(x for x in (v, h) if x) or "el centro"


def colocacion(resumen: dict, t: TableroCharuco) -> dict:
    """Lo que el script de P9 dice de una colocacion tras la vista previa (`--colocacion`): sobre
    los frames medidos de `resumen` (lo que da `medir_carpeta`, con `frames`; los que traen
    `lado_mm`, aunque se descarten por encierro o radio), las medianas de `giro_deg` (y su
    multiplo de 90 mas cercano, `giro_90`), `centro_tablero_mm` (y frente al centro del tablero
    `t`, `centro_rel_mm`), `conjunto_xy_px` (`conjunto_px`, su modulo, y `direccion`), `n_esquinas`
    (de todos los frames), `encierro_mm`, `angulo_normales_deg`, `sesgo_mm`, `vista_deg` y
    `radio_px`; y `vale` con sus `motivos`: esquinas (< `MIN_ESQUINAS`), encierro (<
    `MIN_ENCIERRO_MM`), sesgo (|.| > `MAX_SESGO_MM`), radio (> `RADIO_MAX_PX`) o sin medida."""
    frames = resumen.get("frames") or []
    medidos = [f for f in frames if f.get("lado_mm") is not None and f.get("sesgo_mm") is not None]
    med = _medianas_7c4(medidos)
    n_esq = float(np.median([f["n_esquinas"] for f in frames])) if frames else 0.0
    out: dict = {"n_frames": len(frames), "n_medidos": len(medidos), "n_esquinas": n_esq,
                 "motivos_frames": {m: sum(1 for f in frames if f["motivo"] == m) for m in MOTIVOS},
                 **{c: med[c] for c in ("giro_deg", "centro_tablero_mm", "conjunto_xy_px", "encierro_mm",
                                        "angulo_normales_deg", "sesgo_mm", "vista_deg", "lado_coplanar_mm")},
                 "giro_90": None, "centro_rel_mm": None, "conjunto_px": None, "direccion": None,
                 "radio_px": float(np.median([f["radio_px"] for f in medidos])) if medidos else None}
    motivos: list[str] = []
    if not medidos:
        desc = ", ".join(f"{m} {n}" for m, n in out["motivos_frames"].items() if n) or "ninguno"
        motivos.append(f"sin medida en {len(frames)} frames (descartes: {desc})")
    else:
        out["giro_90"] = int((round(out["giro_deg"] / 90.0) * 90 + 180) % 360 - 180)
        c = out["centro_tablero_mm"]
        out["centro_rel_mm"] = [c[0] - t.ancho_mm / 2.0, c[1] - t.alto_mm / 2.0]
        dx, dy = out["conjunto_xy_px"]
        out["conjunto_px"] = float(math.hypot(dx, dy))
        out["direccion"] = _direccion(dx, dy)
        if n_esq < MIN_ESQUINAS:
            motivos.append(f"esquinas {n_esq:g} (minimo {MIN_ESQUINAS})")
        if out["encierro_mm"] < MIN_ENCIERRO_MM:
            motivos.append(f"fuera del tablero: encierro {out['encierro_mm']:.1f} mm (minimo {MIN_ENCIERRO_MM:g})")
        if abs(out["sesgo_mm"]) > MAX_SESGO_MM + _EPS:
            motivos.append(f"inclinada: sesgo {out['sesgo_mm']:+.3f} mm, normales {out['angulo_normales_deg']:.2f} grados "
                           f"(maximo {MAX_SESGO_MM:g} mm)")
        if out["radio_px"] > RADIO_MAX_PX:
            motivos.append(f"descentrada: radio {out['radio_px']:.0f} px (maximo {RADIO_MAX_PX:g})")
    out["vale"] = not motivos
    out["motivos"] = motivos
    return out


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _reloj() -> float:
    """El reloj del tope de `main` (las pruebas lo sustituyen)."""
    return time.perf_counter()


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m calibration.medir_referencia",
        description="Mide el lado de la referencia sobre el plano del tablero ChArUco registrado, desde los PNG que "
                    "guarda el tracker, y aplica la regla de P77 con P88 y P89 (meta 006, fases 7c3 y 7c4; B55). No abre camara ni red.")
    ap.add_argument("--tablero", required=True, type=Path, help="El .yaml de medidas del tablero (data\\tablero_charuco.yaml).")
    ap.add_argument("--camara", required=True, nargs=3, action="append", metavar=("ETIQUETA", "PERFIL", "CARPETA"),
                    help="Una colocacion: su etiqueta, el perfil de la camara y la carpeta con sus frame_*.png. Se repite.")
    ap.add_argument("--altura-mm", required=True, type=float,
                    help="Cuanto mas alta queda la cara de la referencia que la del tablero, en mm (P78: 0).")
    ap.add_argument("--u-tablero-mm", required=True, type=float,
                    help="La incertidumbre de la escala del tablero sobre el lado, en mm (0.14).")
    ap.add_argument("--salida", required=True, type=Path, help="El .json de la medida (no se pisa).")
    ap.add_argument("--timeout", required=True, type=float, help="Tope en segundos (principio 9).")
    ap.add_argument("--colocacion", action="store_true",
                    help="Con un solo --camara: dice como esta la colocacion (giro, sitio, esquinas, encierro, normales, "
                         "sesgo, vista) y sale con 0 si vale y 1 si no; no aplica P77 (fase 7c4).")
    return ap


def _sha256(ruta) -> str:
    return chb.sha256_archivo(ruta)


def _sin_frames(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != "frames"}


def _linea_lado(c: dict) -> str:
    desc = ", ".join(f"{m} {n}" for m, n in c["motivos"].items() if n) or "ninguno"
    if c["lado_mediana_mm"] is None:
        return (f"[Lado] {c['etiqueta']} ({c['perfil']}): sin frames validos de {c['n_frames']}; descartados: {desc}")
    lados = ", ".join(f"{x:.3f}" for x in c["lados_medios_mm"])
    num = lambda x, nd, signo="": "-" if x is None else f"{x:{signo}.{nd}f}"      # noqa: E731
    return (f"[Lado] {c['etiqueta']} ({c['perfil']}): {c['lado_mediana_mm']:.3f} mm (mediana de {c['n_validos']} frames "
            f"validos de {c['n_frames']}; sd entre frames {num(c['sd_frames_mm'], 4)} mm; error de la mediana "
            f"{num(c.get('error_mediana_mm'), 4)} mm); lados {lados} (sd {c['sd_lados_mm']:.3f}); "
            f"diagonales {c['dif_diagonales_mm']:+.3f} mm; normales {num(c.get('angulo_normales_deg'), 2)} grados; "
            f"sesgo {num(c.get('sesgo_mm'), 3, '+')} mm; vista {num(c.get('vista_deg'), 1)} grados; "
            f"encierro {num(c.get('encierro_mm'), 1)} mm; esquinas {num(c.get('n_esquinas'), 0)}; "
            f"d {c['d_mm']:.0f} mm; radio {c['radio_px']:.0f} px; conjunto a {c['conjunto_px']:.0f} px del centro; "
            f"residuo p95 {c['residuo_px']:.3f} px; descartados: {desc}")


def _linea_colocacion(etiqueta: str, c: dict) -> str:
    num = lambda x, nd, signo="": "-" if x is None else f"{x:{signo}.{nd}f}"      # noqa: E731
    if not c["n_medidos"]:
        return f"[Colocacion] {etiqueta}: NO VALE; {'; '.join(c['motivos'])}"
    cx, cy = c["centro_tablero_mm"]
    rx, ry = c["centro_rel_mm"]
    return (f"[Colocacion] {etiqueta}: giro {c['giro_90']} grados ({c['giro_deg']:+.1f}), centro ({cx:.1f}, {cy:.1f}) mm del "
            f"tablero ({rx:+.1f}, {ry:+.1f} del suyo), conjunto a {c['conjunto_px']:.0f} px del centro hacia {c['direccion']}, "
            f"esquinas {c['n_esquinas']:g}, encierro {num(c['encierro_mm'], 1)} mm, normales {num(c['angulo_normales_deg'], 2)} "
            f"grados, sesgo {num(c['sesgo_mm'], 3, '+')} mm, vista {num(c['vista_deg'], 1)} grados, radio {num(c['radio_px'], 0)} px; "
            f"{'vale' if c['vale'] else 'NO VALE: ' + '; '.join(c['motivos'])}")


def _linea_decision(d: dict) -> str:
    cams = "; ".join(f"{cam} {'-' if c['lado_mm'] is None else format(c['lado_mm'], '.3f')}"
                     + ("" if c["dif_colocaciones_mm"] is None else f" (entre colocaciones {c['dif_colocaciones_mm']:.3f})")
                     for cam, c in d["por_camara"].items())
    num = lambda x, nd: "-" if x is None else f"{x:.{nd}f}"      # noqa: E731
    return (f"[Decision] valida: {'si' if d['valida'] else 'NO'}; valor {num(d['valor_mm'], 1)} mm; U {num(d['u_mm'], 3)} mm; "
            f"entre camaras {num(d['dif_camaras_mm'], 3)} mm; nominal {d['nominal_mm']:g} mm; cambiar: "
            f"{'si' if d['cambiar'] else 'no'}; por camara: {cams}" + (f"; motivo: {d['motivo']}" if d["motivo"] else ""))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    salida = Path(args.salida)
    try:
        if not args.timeout > 0:
            raise ValueError("--timeout tiene que ser > 0")
        if not args.u_tablero_mm > 0:
            raise ValueError("--u-tablero-mm tiene que ser > 0")
        if args.colocacion and len(args.camara) != 1:
            raise ValueError(f"--colocacion va con un solo --camara, no con {len(args.camara)}")
        if salida.exists():
            raise ValueError(f"la salida ya existe, no se pisa: {salida}")
        info_tablero = chb.describir_tablero(args.tablero)
        if not info_tablero["medido"]:
            raise ValueError(f"{Path(args.tablero).name}: el tablero no esta medido; hace falta el .yaml de `registrar` "
                             f"(la escala de la medida es su casilla)")
        t = chb.leer_tablero_charuco(args.tablero)
        etiquetas = [c[0] for c in args.camara]
        if len(set(etiquetas)) != len(etiquetas):
            raise ValueError(f"hay etiquetas de --camara repetidas: {etiquetas}")
        colocaciones = []
        for etiqueta, ruta_perfil, carpeta in args.camara:
            ruta_perfil, carpeta = Path(ruta_perfil), Path(carpeta)
            cfg = profiles.load(ruta_perfil)
            ref = profiles.reference_marker(cfg["markers"]["list"])
            ruta_k = (cfg.get("camera") or {}).get("calibration_file")
            if not ruta_k:
                raise ValueError(f"--camara {etiqueta}: el perfil {ruta_perfil.name} no trae camera.calibration_file")
            intr = leer_intrinsecos(ruta_k)
            if not carpeta.is_dir() or not frames_de(carpeta):
                raise ValueError(f"--camara {etiqueta}: no hay frame_*.png en {carpeta}")
            primero = cv2.imread(str(frames_de(carpeta)[0]), cv2.IMREAD_UNCHANGED)
            if primero is None or primero.ndim != 2 or primero.dtype != np.uint8:
                raise ValueError(f"--camara {etiqueta}: {frames_de(carpeta)[0]} no es una imagen en gris de 8 bits")
            if intr["shape"] is not None and tuple(primero.shape[::-1]) != tuple(intr["shape"]):
                raise ValueError(f"--camara {etiqueta}: los PNG miden {primero.shape[1]} x {primero.shape[0]} y los "
                                 f"intrinsecos de {ruta_perfil.name} son de {intr['shape'][0]} x {intr['shape'][1]}")
            colocaciones.append({"etiqueta": etiqueta, "ruta_perfil": ruta_perfil, "carpeta": carpeta, "cfg": cfg,
                                 "ref_id": int(ref["id"]), "size_mm": float(ref["size_mm"]), "ruta_k": Path(ruta_k)})
        nominales = sorted({c["size_mm"] for c in colocaciones})
        if len(nominales) != 1:
            raise ValueError(f"los perfiles no dicen el mismo size_mm de la referencia ({nominales}): es el mismo marker")
        if len({c["ref_id"] for c in colocaciones}) != 1:
            raise ValueError(f"los perfiles no dicen el mismo ID de la referencia ({sorted({c['ref_id'] for c in colocaciones})})")
    except (ValueError, OSError, KeyError, yaml.YAMLError) as e:
        print(f"{TAG} ERROR: {e}")
        return EXIT_USO
    nominal = nominales[0]
    datos: dict = {
        "formato": FORMATO, "generado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "argv": [str(a) for a in (sys.argv[1:] if argv is None else argv)], "opencv": cv2.__version__,
        "tablero": info_tablero, "altura_mm": float(args.altura_mm), "u_tablero_mm": float(args.u_tablero_mm),
        "nominal_mm": nominal, "ref_id": colocaciones[0]["ref_id"],
        "criterios": {"min_esquinas": MIN_ESQUINAS,
                      "min_encierro_mm": MIN_ENCIERRO_MM if math.isfinite(MIN_ENCIERRO_MM) else None, "radio_max_px": RADIO_MAX_PX,
                      "min_frames": MIN_FRAMES, "max_error_mediana_mm": MAX_ERROR_MEDIANA_MM,
                      "factor_mediana": FACTOR_MEDIANA, "max_sesgo_mm": MAX_SESGO_MM,
                      "max_dif_camaras_mm": MAX_DIF_CAMARAS_MM},
        "modo": "colocacion" if args.colocacion else "medida",
        "timeout_s": float(args.timeout), "completo": True, "colocaciones": [], "decision": None, "colocacion": None}
    t0 = _reloj()
    rc = None
    for c in colocaciones:
        cabecera = {"etiqueta": c["etiqueta"], "perfil": c["ruta_perfil"].name, "perfil_sha256": _sha256(c["ruta_perfil"]),
                    "intrinsecos_sha256": _sha256(c["ruta_k"])}
        try:
            restante = args.timeout - (_reloj() - t0)
            if restante <= 0:
                raise TopeSuperado(f"tope de {args.timeout:g} s antes de empezar {c['etiqueta']}", {"completo": False})
            m = medir_carpeta(c["carpeta"], c["cfg"], t, args.altura_mm, MIN_ESQUINAS, RADIO_MAX_PX,
                              clock=_reloj, tope_s=restante, min_encierro_mm=MIN_ENCIERRO_MM)
        except TopeSuperado as e:
            print(f"{TAG} TOPE: {e}", flush=True)
            datos["colocaciones"].append({**cabecera, **e.parcial})
            datos["completo"] = False
            rc = EXIT_TOPE
            break
        except ValueError as e:
            print(f"{TAG} ERROR: --camara {c['etiqueta']}: {e}")
            return EXIT_USO
        datos["colocaciones"].append({**cabecera, **m})
        if args.colocacion:
            datos["colocacion"] = colocacion(m, t)
            print(_linea_colocacion(c["etiqueta"], datos["colocacion"]), flush=True)
            rc = EXIT_OK if datos["colocacion"]["vale"] else EXIT_NO_VALIDA
        else:
            print(_linea_lado({**cabecera, **m}), flush=True)
    if rc is None:
        por_camara: dict[str, list[dict]] = {}
        for c in datos["colocaciones"]:
            por_camara.setdefault(c["perfil"], []).append(_sin_frames(c))
        datos["decision"] = decidir(por_camara, nominal, args.u_tablero_mm, MIN_FRAMES, MAX_ERROR_MEDIANA_MM,
                                    MAX_DIF_CAMARAS_MM, MAX_SESGO_MM)
        print(_linea_decision(datos["decision"]), flush=True)
        rc = EXIT_OK if datos["decision"]["valida"] else EXIT_NO_VALIDA
    datos["segundos"] = round(_reloj() - t0, 3)
    datos["codigo"] = rc
    try:
        salida.parent.mkdir(parents=True, exist_ok=True)
        with open(salida, "x", encoding="utf-8", newline="\n") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"{TAG} ERROR: no se pudo escribir {salida}: {e}")
        return EXIT_USO
    print(f"{TAG} salida: {salida}; {datos['segundos']:.1f} s"
          + ("; TOPE: no se decide" if rc == EXIT_TOPE else ""), flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
