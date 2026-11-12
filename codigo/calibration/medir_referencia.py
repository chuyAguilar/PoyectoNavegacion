# -*- coding: utf-8 -*-
"""
El lado de la referencia medido con la camara contra el tablero ChArUco registrado (meta 006 ·
Grafo de factores optico-inercial, fase 7c3 · El tamano de la referencia medido con el tablero;
B55, P76 a P80). Fuera de la cadena: no abre camara ni red y no importa `vision.tracking`; lee los
PNG en gris que guarda el tracker (`--save-frames`).

Por que: el `size_mm` de la referencia es la escala de toda la pose que se publica, y el calibrador
apoyado sobre una pieza impresa plana no lo da mejor que +-0.8 % (P76). El tablero si tiene una
escala fiable (su casilla se midio restando dos tramos, B - A). Con la referencia apoyada en la
misma mesa que el tablero, a su lado, la camara mide su lado en el plano del tablero.

Como: por homografia, no por pose. Las esquinas del tablero y las de la referencia se llevan a
coordenadas normalizadas sin distorsion (`undistortPointsIter`); la homografia tablero (mm) ->
normalizadas se ajusta con todas las esquinas del tablero (`findHomography`, minimos cuadrados) y
su inversa lleva las 4 esquinas de la referencia al plano del tablero, en mm. Es un cociente de
longitudes en un mismo plano: fx, fy, cx y cy los absorbe la homografia y solo entran por la
distorsion (por eso se descartan los frames con la referencia lejos del centro, `RADIO_MAX_PX`).
Lo que se mide es el borde que ve el detector del tracker (`vision.detection.detect` con el
detector del perfil, el mismo refinado), que es lo que `size_mm` tiene que valer.

La altura: si la cara de la referencia queda `altura_mm` mas cerca de la camara que la del
tablero (planos paralelos), su proyeccion sobre el plano del tablero desde el centro de la camara
es una homotecia de razon d / (d - altura), exacta con cualquier inclinacion; d es la distancia
del centro de la camara al plano del tablero (`distancia_al_plano`). `corregir_altura` la deshace.
En P9 las dos piezas miden 2.8 mm (P78): `--altura-mm 0`.

Constantes:
- `CRITERIO_UNDISTORT`: 100 iteraciones o 1e-12; las 5 iteraciones por defecto de
  `undistortPoints` dejan un error que aqui se veria.
- `MIN_ESQUINAS` = 30 de las 48 del tablero: la homografia se apoya en el tablero casi entero.
- `RADIO_MAX_PX` = 382: la distancia maxima, en px, del centro de la referencia al centro de la
  imagen. Sale del criterio 4 de la fase: a 30 cm de frente, con el conjunto corrido hacia una
  esquina, el radio en que una K desviada como la del diagnostico (fx y fy +11, cx -9.5, cy
  -7.3 px) mete mas de 0.03 mm (`tests/test_medir_referencia.py` lo recalcula). Es un tope
  grueso, no una garantia: a 40 y 55 cm ese error llega antes (295 y 315 px), y con el conjunto
  corrido hacia el lado del tablero crece aunque la referencia quede mas cerca del centro. Por
  eso cada frame da tambien `conjunto_px` (cuanto se aparta del centro de la imagen el centro de
  todo lo leido: ~0.001 mm de error por px con esa K a 30-40 cm) y la sesion pide centrar.

Lo que mide, medido en la fase sobre escenas sinteticas: el refinado `CORNER_REFINE_SUBPIX` del
detector mete cada esquina del cuadro negro ~0.15 px hacia dentro sobre un borde suavizado, asi
que el lado sale ~0.10 mm por debajo del dibujado (de -0.04 a -0.13 mm entre 30 y 55 cm). Es lo
que ve el tracker en cada frame; depende del desenfoque y de la distancia.
- `MIN_FRAMES` = 30, `MAX_SD_FRAMES_MM` = 0.05 y `MAX_DIF_CAMARAS_MM` = 0.3: la regla de P77.

La regla de P77 (`decidir`): la medida vale si cada colocacion de cada camara tiene >= 30 frames
validos con una sd entre frames <= 0.05 mm, y las dos camaras difieren <= 0.3 mm. El valor es la
media de las dos camaras, a 0.1 mm; se cambia el `size_mm` solo si se aparta del nominal mas que
U = sqrt(u_tablero^2 + (|gs1 - gs2| / 2)^2). `u_tablero_mm` va explicito (principio 7): 0.14 mm
sale de la resolucion del calibrador (0.1 mm: +-0.05 por lectura, +-0.07 la resta B - A) sobre
51.9 mm, +-0.13 % de la casilla, y eso en un lado de ~100 mm.

Uso (desde codigo\\, con el venv; argumentos explicitos, principio 7):
    python -m calibration.medir_referencia --tablero data\\tablero_charuco.yaml ^
        --camara gs1_d profiles\\tracker_config_gs1.yaml <PNG gs1, derecha> ^
        --camara gs1_i profiles\\tracker_config_gs1.yaml <PNG gs1, izquierda> ^
        --camara gs2_d profiles\\tracker_config_gs2.yaml <PNG gs2, derecha> ^
        --camara gs2_i profiles\\tracker_config_gs2.yaml <PNG gs2, izquierda> ^
        --altura-mm 0 --u-tablero-mm 0.14 --salida <json> --timeout 300

`--camara ETIQUETA PERFIL CARPETA` se repite, una por colocacion; `decidir` agrupa por perfil (una
camara = un perfil). El nominal es el `size_mm` de la referencia del perfil: todos tienen que
decir lo mismo. Escribe el `.json` (no pisa), una linea `[Lado]` por colocacion y una
`[Decision]`. Codigos: 0 medida valida (cambie o no); 1 no valida; 2 uso (la salida existe, una
carpeta sin PNG, un perfil sin `calibration_file`, un PNG de otra forma que la de los
intrinsecos, perfiles con distinto `size_mm`, el tablero sin medir): no escribe nada; 4 salto el
tope: escribe lo hecho y no decide.

Context7 (2026-11-12, `/websites/opencv`, documentacion 5.0; instalado 4.11.0, firmas comprobadas
con `__doc__`): `undistortPointsIter(src, cameraMatrix, distCoeffs, R, P, criteria) -> dst` (con
P vacia, coordenadas normalizadas; en 4.11 `undistortPoints` no admite `criteria` desde Python);
`findHomography(srcPoints, dstPoints[, method]) -> retval, mask` (metodo 0: minimos cuadrados
con todos los puntos, refinado con Levenberg-Marquardt; matriz vacia si no se puede estimar;
normalizada con h33 = 1); `solvePnP(objectPoints, imagePoints, cameraMatrix, distCoeffs, flags=
SOLVEPNP_IPPE) -> retval, rvec, tvec` (>= 4 puntos coplanares; imagePoints contiguos (N, 1, 2));
`perspectiveTransform(src (N, 1, 2), m 3x3) -> dst`.
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
MIN_ESQUINAS = 30               # de las 48 del tablero de P59
RADIO_MAX_PX = 382.0            # el criterio 4 de la fase, a 30 cm (ver el docstring y su prueba)
MIN_FRAMES = 30                 # P77
MAX_SD_FRAMES_MM = 0.05         # P77
MAX_DIF_CAMARAS_MM = 0.3        # P77
MOTIVOS = ("sin_tablero", "sin_referencia", "referencia_repetida", "descentrada")
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


def distancia_al_plano(esq_tab_px: np.ndarray, ids_tab: np.ndarray, t: TableroCharuco, K: np.ndarray,
                       dist: np.ndarray) -> float:
    """La distancia, en mm, del centro de la camara al plano del tablero: `solvePnP` con
    `SOLVEPNP_IPPE` y d = |R[:, 2] . tvec|. Solo entra en la correccion de altura (un 1 % de
    error en d mueve el lado 0.01 x altura x lado / d: nada). ValueError si no hay pose."""
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
    return float(abs(R[:, 2] @ np.asarray(tvec, dtype=np.float64).reshape(3)))


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

def medir_frame(gray: np.ndarray, det_ref, ref_id: int, det_tab, t: TableroCharuco, K, dist, altura_mm: float,
                min_esquinas: int, radio_max_px: float) -> dict:
    """El lado de la referencia en un frame en gris.

    La referencia se detecta con el detector del perfil (`vision.detection.detect(det_ref, gray,
    {ref_id})`: la misma lista blanca y el mismo refinado que el tracker) y el tablero con
    `charuco_board.detectar_charuco`. Devuelve `lado_mm` (la media de los cuatro lados, con la
    altura corregida), `lados_mm` (4), `diagonales_mm` (2), `d_mm`, `residuo_px`, `radio_px` (del
    centro de la referencia al centro de la imagen), `conjunto_px` (del centro de la caja que
    encierra las esquinas leidas del tablero y las de la referencia al centro de la imagen: un
    numero, no descarta), `n_esquinas` y `motivo`: `None` si vale, o
    `"sin_tablero"` (menos de `min_esquinas` esquinas), `"sin_referencia"`,
    `"referencia_repetida"` (el ID dos o mas veces: B39) o `"descentrada"` (`radio_px` >
    `radio_max_px`). Lo que no se pudo medir queda en `None`.
    """
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("el frame no es una imagen en gris de 8 bits")
    out: dict = {"motivo": None, "lado_mm": None, "lados_mm": None, "diagonales_mm": None, "d_mm": None,
                 "residuo_px": None, "radio_px": None, "conjunto_px": None, "n_esquinas": 0, "n_referencias": 0}
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
    out["conjunto_px"] = float(np.linalg.norm((todos.min(axis=0) + todos.max(axis=0)) / 2.0
                                              - np.array([(gray.shape[1] - 1) / 2.0, (gray.shape[0] - 1) / 2.0])))
    try:
        m = lados_en_plano(esq_ref, esq_tab, ids_tab, t, K, dist)
        d_mm = distancia_al_plano(esq_tab, ids_tab, t, K, dist)
    except ValueError:
        out["motivo"] = "sin_tablero"
        return out
    lados = corregir_altura(m["lados_mm"], d_mm, altura_mm)
    out.update({"lado_mm": float(lados.mean()), "lados_mm": [float(x) for x in lados],
                "diagonales_mm": [float(x) for x in corregir_altura(m["diagonales_mm"], d_mm, altura_mm)],
                "d_mm": float(d_mm), "residuo_px": float(m["residuo_px"])})
    if out["radio_px"] > radio_max_px:
        out["motivo"] = "descentrada"
    return out


def frames_de(carpeta: Path) -> list[Path]:
    """Los `frame_*.png` de `carpeta`, ordenados."""
    return sorted(Path(carpeta).glob("frame_*.png"))


def _resumen(frames: list[dict]) -> dict:
    """El resumen de los frames validos (`motivo` None) de una colocacion."""
    validos = [f for f in frames if f["motivo"] is None]
    motivos = {m: sum(1 for f in frames if f["motivo"] == m) for m in MOTIVOS}
    out = {"n_frames": len(frames), "n_validos": len(validos), "motivos": motivos,
           "lado_mediana_mm": None, "sd_frames_mm": None, "lados_medios_mm": None, "sd_lados_mm": None,
           "dif_diagonales_mm": None, "d_mm": None, "radio_px": None, "conjunto_px": None, "residuo_px": None}
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
    return out


def medir_carpeta(dir_frames: Path, perfil: dict, t: TableroCharuco, altura_mm: float, min_esquinas: int,
                  radio_max_px: float, clock=time.perf_counter, tope_s: float | None = None) -> dict:
    """`medir_frame` sobre los `frame_*.png` de `dir_frames`, con el perfil ya cargado
    (`profiles.load`): el ID de la referencia sale de `profiles.reference_marker`, el detector de
    `markers` y K y dist de `camera.calibration_file`.

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
            "altura_mm": float(altura_mm), "min_esquinas": int(min_esquinas), "radio_max_px": float(radio_max_px)}
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
        f = medir_frame(gray, det_ref, int(ref["id"]), det_tab, t, K, dist, altura_mm, min_esquinas, radio_max_px)
        frames.append({"nombre": png.name, **f})
    return {**base, "completo": True, "frames_sin_leer": 0, "frames": frames, **_resumen(frames)}


# ----------------------------------------------------------------------------
# La regla de P77
# ----------------------------------------------------------------------------

def _a_decima(x: float) -> float:
    """`x` redondeado a 0.1 (el medio, hacia arriba)."""
    return math.floor(float(x) * 10.0 + 0.5) / 10.0


def decidir(por_camara: dict[str, list[dict]], nominal_mm: float, u_tablero_mm: float, min_frames: int,
            max_sd_mm: float, max_dif_mm: float) -> dict:
    """La regla de P77 sobre los resumenes de `medir_carpeta`. `por_camara` da, por camara (la
    clave es su perfil), la lista de los resumenes de sus colocaciones (una, o dos con P80 a).

    Cada camara da la media de las medianas de sus colocaciones (`lado_mm`) y, con dos, su
    diferencia como numero (`dif_colocaciones_mm`). `valida`: hay exactamente dos camaras, cada
    colocacion tiene >= `min_frames` frames validos y `sd_frames_mm` <= `max_sd_mm`, y las dos
    camaras difieren <= `max_dif_mm`; si no, `motivo` dice por que. `valor_mm`: la media de las
    dos camaras, a 0.1 mm. `dif_camaras_mm`. `u_mm` = sqrt(`u_tablero_mm`^2 + (dif / 2)^2).
    `cambiar`: valida y |`valor_mm` - `nominal_mm`| > `u_mm`. Los numeros se dan tambien cuando
    no es valida, si se pueden calcular.
    """
    if not u_tablero_mm > 0 or not nominal_mm > 0:
        raise ValueError(f"u_tablero_mm y nominal_mm tienen que ser > 0, no {u_tablero_mm} y {nominal_mm}")
    motivos: list[str] = []
    camaras: dict[str, dict] = {}
    for cam, resumenes in por_camara.items():
        medianas, ns, sds = [], [], []
        for k, r in enumerate(resumenes):
            n, sd, med = int(r.get("n_validos") or 0), r.get("sd_frames_mm"), r.get("lado_mediana_mm")
            ns.append(n)
            sds.append(sd)
            donde = f"{cam}, colocacion {k + 1}"
            if n < min_frames:
                motivos.append(f"{donde}: {n} frames validos (minimo {min_frames})")
            elif sd is None or sd > max_sd_mm + _EPS:
                motivos.append(f"{donde}: sd entre frames {'-' if sd is None else format(sd, '.3f')} mm (maximo {max_sd_mm:g})")
            if med is not None:
                medianas.append(float(med))
        if not resumenes:
            motivos.append(f"{cam}: sin colocaciones")
        camaras[cam] = {"medianas_mm": medianas, "n_validos": ns, "sd_frames_mm": sds,
                        "lado_mm": float(np.mean(medianas)) if medianas and len(medianas) == len(resumenes) else None,
                        "dif_colocaciones_mm": float(max(medianas) - min(medianas)) if len(medianas) >= 2 else None}
    out = {"regla": "P77", "nominal_mm": float(nominal_mm), "u_tablero_mm": float(u_tablero_mm),
           "min_frames": int(min_frames), "max_sd_frames_mm": float(max_sd_mm), "max_dif_camaras_mm": float(max_dif_mm),
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
                    "guarda el tracker, y aplica la regla de P77 (meta 006, fase 7c3; B55). No abre camara ni red.")
    ap.add_argument("--tablero", required=True, type=Path, help="El .yaml de medidas del tablero (data\\tablero_charuco.yaml).")
    ap.add_argument("--camara", required=True, nargs=3, action="append", metavar=("ETIQUETA", "PERFIL", "CARPETA"),
                    help="Una colocacion: su etiqueta, el perfil de la camara y la carpeta con sus frame_*.png. Se repite.")
    ap.add_argument("--altura-mm", required=True, type=float,
                    help="Cuanto mas alta queda la cara de la referencia que la del tablero, en mm (P78: 0).")
    ap.add_argument("--u-tablero-mm", required=True, type=float,
                    help="La incertidumbre de la escala del tablero sobre el lado, en mm (0.14).")
    ap.add_argument("--salida", required=True, type=Path, help="El .json de la medida (no se pisa).")
    ap.add_argument("--timeout", required=True, type=float, help="Tope en segundos (principio 9).")
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
    sd = "-" if c["sd_frames_mm"] is None else f"{c['sd_frames_mm']:.4f}"
    return (f"[Lado] {c['etiqueta']} ({c['perfil']}): {c['lado_mediana_mm']:.3f} mm (mediana de {c['n_validos']} frames "
            f"validos de {c['n_frames']}; sd entre frames {sd} mm); lados {lados} (sd {c['sd_lados_mm']:.3f}); "
            f"diagonales {c['dif_diagonales_mm']:+.3f} mm; d {c['d_mm']:.0f} mm; radio {c['radio_px']:.0f} px; "
            f"conjunto a {c['conjunto_px']:.0f} px del centro; "
            f"residuo p95 {c['residuo_px']:.3f} px; descartados: {desc}")


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
        "criterios": {"min_esquinas": MIN_ESQUINAS, "radio_max_px": RADIO_MAX_PX, "min_frames": MIN_FRAMES,
                      "max_sd_frames_mm": MAX_SD_FRAMES_MM, "max_dif_camaras_mm": MAX_DIF_CAMARAS_MM},
        "timeout_s": float(args.timeout), "completo": True, "colocaciones": [], "decision": None}
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
                              clock=_reloj, tope_s=restante)
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
        print(_linea_lado({**cabecera, **m}), flush=True)
    if rc is None:
        por_camara: dict[str, list[dict]] = {}
        for c in datos["colocaciones"]:
            por_camara.setdefault(c["perfil"], []).append(_sin_frames(c))
        datos["decision"] = decidir(por_camara, nominal, args.u_tablero_mm, MIN_FRAMES, MAX_SD_FRAMES_MM, MAX_DIF_CAMARAS_MM)
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
