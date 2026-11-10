# -*- coding: utf-8 -*-
"""
Los extrinsecos de gs2 respecto a gs1 por tablero, independientes de Marker0
(meta 006 · Grafo de factores optico-inercial, fase 7; P12 a, P36).

El tablero de la meta 002 (9x6 casillas = 8x5 esquinas interiores, lado medido
24.86 mm) quieto en >= 18 posiciones vistas por las dos camaras. No abre ninguna
camara: lee los frames en gris que guardaron los dos trackers del PC con
`--record --save-frames` (una carpeta por posicion y camara). Como el tablero
esta quieto, las dos vistas de una posicion no tienen que ser simultaneas.

Carpeta de `--desde-vistas` (la escribe `Claude outputs/fases/006/fase-7/correr.ps1`):

    <carpeta>/T01_gs1_frames/frame_00000.png ...      T01_gs2_frames/frame_*.png
    <carpeta>/T05_gs1_r2_frames/ ...                  (un intento repetido: gana el ultimo)

Que hace:
  1. Por posicion y camara, detecta las esquinas en los ultimos `--frames-por-vista`
     frames (el mismo detector de los intrinsecos, `sb`) y toma su media; si entre
     frames se mueven mas de `--max-movimiento-px`, el tablero no estaba quieto y
     la posicion queda fuera, con su motivo.
  2. El orden de las esquinas: OpenCV no garantiza el mismo origen en las dos
     vistas (medido el 2026-11-09: `sb` y `clasico` devuelven ordenes opuestos
     sobre la misma imagen). `emparejar_orden` prueba los cuatro ordenes de gs2
     frente a gs1 y se queda, por vista, con el que da un `T_gs2<-gs1` coherente
     con las demas vistas (la pose de cada camara por solvePnP); una vista sin
     ningun orden coherente queda fuera, con su motivo.
  3. Aparta `--n-control` vistas (al azar con `--semilla`) y calibra con el resto:
     `cv2.stereoCalibrateExtended` con `CALIB_FIX_INTRINSIC` (los intrinsecos de
     `data/` no se tocan). R, T llevan puntos de gs1 a gs2 (x2 = R x1 + T); el
     `.yml` guarda la inversa, `T_gs1<-gs2`, como el resto de `fusion/`.
  4. Lo valida aparte del ajuste, con las vistas de control: la reproyeccion
     cruzada (la pose del tablero vista por gs1 sola, llevada a gs2 con R, T y
     proyectada, frente a las esquinas de gs2) y la distancia triangulada entre
     las esquinas opuestas del tablero frente a la nominal.
  5. Con `--comparar-con <resultados.json>` (el de `python -m fusion.experiment`)
     compara con los extrinsecos por Marker0: giro, traslacion y cuanto mueven un
     punto a 37 cm. Con `--criterio-1-datos <carpeta de S2>` repite el criterio 1
     del spec con los del tablero (gs2 llevada a gs1 frente a gs1, la peor posicion).
  6. Criterio (plan, fase 7): RMS <= 0.5 px con >= 15 vistas en el ajuste, control
     <= 0.75 px y distancia triangulada a <= 0.3 mm de la nominal. Solo si cumple
     y hay `--output` escribe el `.yml` (`fusion.extrinsics.save_extrinsics`, no
     pisa): metodo `tablero`, el sha256 de los dos intrinsecos, la validacion y, en
     `alternative`, los de Marker0. El criterio 1 va dentro como numero: no decide
     si se escribe (dice si la pose de una camara sola casa, no si R, T estan bien).

La distancia nominal sale del tablero: lado * hypot(cols - 1, rows - 1); con 8x5 y
24.86 mm, 200.43 mm. (El plan escribio 198.88 mm = 8 x 24.86, que no es la
distancia entre ningun par de esquinas interiores de este tablero.)

Context7 (2026-11-09, `/websites/opencv`; instalado 4.11.0, firmas comprobadas con
`__doc__`): `stereoCalibrateExtended(objectPoints, imagePoints1, imagePoints2, K1, d1,
K2, d2, imageSize, R, T[, E, F, rvecs, tvecs, perViewErrors, flags, criteria]) ->
retval, K1, d1, K2, d2, R, T, E, F, rvecs, tvecs, perViewErrors` (flags por defecto
CALIB_FIX_INTRINSIC; perViewErrors es N x 2, una columna por camara);
`triangulatePoints(P1, P2, pts1 2xN, pts2 2xN) -> 4xN` homogeneas;
`undistortPointsIter(src, K, d, R, P, criteria)` (en 4.11 `undistortPoints` no admite
`criteria` desde Python); `findChessboardCornersSB`: el origen comun entre vistas solo
lo da el marcador (`CALIB_CB_MARKER`), que este tablero no tiene.

Uso (desde codigo\\, con el venv; argumentos explicitos, principio 7):
    python -m calibration.calibrate_extrinsics ^
        --desde-vistas "..\\Claude outputs\\fases\\006\\fase-7\\datos\\<fecha>" ^
        --intrinsecos gs1=data\\intrinsecos_gs1_1280x960.yml gs2=data\\intrinsecos_gs2_1280x960.yml ^
        --cols 8 --rows 5 --square-mm 24.86 --detector sb --frames-por-vista 5 ^
        --max-movimiento-px 0.3 --min-vistas 15 --n-control 3 --semilla 0 --montaje pinzas ^
        --comparar-con "..\\Claude outputs\\fases\\006\\fase-2\\corrida-pc-01\\resultados.json" ^
        --criterio-1-datos "..\\Claude outputs\\fases\\006\\grabacion-pc\\datos\\20261109-163350" ^
        --tolerancia-ancla-ms 20 --output data\\extrinsecos_gs1_gs2_pinzas.yml ^
        --reporte "..\\Claude outputs\\fases\\006\\fase-7\\extrinsecos_tablero.json" --timeout 600
Con `--solo-comprobar` (y `--posiciones T05` para una sola) no calibra: dice, por
posicion y camara, si el tablero se ve y si estaba quieto (lo usa `correr.ps1`).

Codigo de salida: 0 cumple; 1 corrio y no cumple (el reporte dice que); 2 no pudo empezar.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from calibration import calibrate_camera as cc   # antes de cv2: apaga la aceleracion HW de MSMF (CONTEXT 4.18)
import cv2
import numpy as np

from diagnostics.probe_camera import _vigilante
from fusion import extrinsics as ex
from fusion.dataset import sha256_file
from fusion.geometry import inv, pose_difference

REF, OTHER = "gs1", "gs2"
ORDENES = ("directo", "invertido", "espejo_columnas", "espejo_filas")
# Criterio de la fase 7 (plan de la meta 006): RMS del ajuste, control, distancia triangulada y vistas.
CRITERIO = {"rms_px": 0.5, "rms_control_px": 0.75, "triangulada_mm": 0.3, "min_vistas": 15}
ORDEN_TOL_MM = 25.0            # dos vistas dan el mismo T_gs2<-gs1 si difieren menos que esto;
ORDEN_TOL_DEG = 5.0            # un orden equivocado se va a cientos de mm y decenas de grados
MAX_MOVIMIENTO_PX = 0.3
FRAMES_POR_VISTA = 5
PUNTO_COMPARACION_MM = 370.0   # «lo que mueven un punto a 37 cm» (plan)
CRITERIOS_ESTEREO = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 200, 1e-12)
CRITERIOS_UNDISTORT = (cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 50, 1e-12)

log_info, log_warn, log_error, log_stats = cc.log_info, cc.log_warn, cc.log_error, cc.log_stats


class PocasVistas(ValueError):
    """No hay bastantes posiciones usables para el ajuste y el control: corrio y no cumple (codigo 1)."""


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

def leer_intrinsecos(ruta) -> dict:
    """K, dist, shape (w, h) o None, detector y square_mm del `.yml` de intrinsecos de `data/`."""
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"no se pudo abrir el .yml de intrinsecos: {ruta}")
    try:
        K = fs.getNode("camera_matrix").mat()
        d = fs.getNode("distortion_coefficients").mat()
        w, h = fs.getNode("image_width"), fs.getNode("image_height")
        det, sq = fs.getNode("detector"), fs.getNode("square_mm")
        if K is None or d is None or np.asarray(K).shape != (3, 3):
            raise ValueError(f"{Path(ruta).name}: sin camera_matrix o distortion_coefficients")
        return {"K": np.asarray(K, dtype=np.float64), "dist": np.asarray(d, dtype=np.float64).flatten(),
                "shape": None if (w.empty() or h.empty()) else (int(w.real()), int(h.real())),
                "detector": None if det.empty() else str(det.string()),
                "square_mm": None if sq.empty() else float(sq.real())}
    finally:
        fs.release()


def reordenar(esquinas, cols: int, rows: int, orden: str) -> np.ndarray:
    """Las esquinas (cols*rows, 2), fila a fila, en otro de los cuatro ordenes posibles del
    mismo tablero: `invertido` (giro de 180 grados), `espejo_columnas` y `espejo_filas`."""
    g = np.asarray(esquinas, dtype=np.float64).reshape(rows, cols, 2)
    if orden == "directo":
        out = g
    elif orden == "invertido":
        out = g[::-1, ::-1]
    elif orden == "espejo_columnas":
        out = g[:, ::-1]
    elif orden == "espejo_filas":
        out = g[::-1, :]
    else:
        raise ValueError(f"orden desconocido: {orden!r} (validos: {ORDENES})")
    return np.ascontiguousarray(out).reshape(-1, 2)


def pose_tablero(objp, imgp, K, dist) -> tuple[np.ndarray, float]:
    """`T_cam<-tablero` (4x4, mm) por solvePnP y su RMS de reproyeccion (px)."""
    o = np.asarray(objp, dtype=np.float64).reshape(-1, 3)
    p = np.asarray(imgp, dtype=np.float64).reshape(-1, 1, 2)
    ok, rvec, tvec = cv2.solvePnP(o, p, np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64),
                                  flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        raise RuntimeError("solvePnP no resolvio la pose del tablero")
    T = np.eye(4)
    T[:3, :3] = cv2.Rodrigues(rvec)[0]
    T[:3, 3] = np.asarray(tvec, dtype=np.float64).flatten()
    proy, _j = cv2.projectPoints(o, rvec, tvec, np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64))
    d = proy.reshape(-1, 2) - p.reshape(-1, 2)
    return T, float(np.sqrt(np.mean(np.sum(d * d, axis=1))))


def _proyectar(objp, T_cam_tablero, K, dist) -> np.ndarray:
    rvec = cv2.Rodrigues(np.asarray(T_cam_tablero)[:3, :3])[0]
    p, _j = cv2.projectPoints(np.asarray(objp, dtype=np.float64).reshape(-1, 3), rvec,
                              np.asarray(T_cam_tablero)[:3, 3].reshape(3, 1),
                              np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64))
    return p.reshape(-1, 2)


def emparejar_orden(objp, img_a, img_b, K_a, d_a, K_b, d_b, cols: int, rows: int,
                    tol_mm: float = ORDEN_TOL_MM, tol_deg: float = ORDEN_TOL_DEG) -> dict:
    """Pone las esquinas de cada vista de `b` en el orden de las de `a`.

    Por vista y por cada uno de los cuatro ordenes de `b` calcula `T_b<-a = T_b<-tablero .
    T_a<-tablero^-1` con la pose de cada camara sola. El candidato con mas vistas de acuerdo
    (a menos de `tol_mm` y `tol_deg`) es la referencia; cada vista se queda con su orden mas
    cercano a ella, y es `coherente` si cae dentro de la tolerancia. Devuelve `img_b` (ya
    reordenadas, (N, 1, 2) float32), `ordenes`, `coherente`, `apoyo` y `T_b_a` (la referencia).
    """
    n = len(img_a)
    if n != len(img_b):
        raise ValueError(f"img_a ({n}) e img_b ({len(img_b)}) no casan")
    if n < 2:
        raise ValueError(f"hacen falta al menos 2 vistas para decidir el orden, hay {n}")
    cand = []                                   # cand[k][o] = T_b<-a de la vista k con el orden o
    for k in range(n):
        Ta, _e = pose_tablero(objp, img_a[k], K_a, d_a)
        fila = []
        for orden in ORDENES:
            Tb, _e = pose_tablero(objp, reordenar(img_b[k], cols, rows, orden), K_b, d_b)
            fila.append(Tb @ inv(Ta))
        cand.append(fila)

    def cerca(T1, T2) -> float:
        dmm, ddeg = pose_difference(T1, T2)
        return max(dmm / tol_mm, ddeg / tol_deg)        # <= 1: de acuerdo

    mejor, apoyo = (0, 0), -1
    for o in range(len(ORDENES)):               # con empate gana `directo` y la primera vista
        for k in range(n):
            s = sum(1 for k2 in range(n) if k2 != k and min(cerca(cand[k][o], c) for c in cand[k2]) <= 1.0)
            if s > apoyo:
                mejor, apoyo = (k, o), s
    ref = cand[mejor[0]][mejor[1]]
    ordenes, coherente, salida = [], [], []
    for k in range(n):
        d = [cerca(ref, c) for c in cand[k]]
        o = int(np.argmin(d))
        ordenes.append(ORDENES[o])
        coherente.append(bool(d[o] <= 1.0))
        salida.append(reordenar(img_b[k], cols, rows, ORDENES[o]).astype(np.float32).reshape(-1, 1, 2))
    return {"img_b": salida, "ordenes": ordenes, "coherente": coherente, "apoyo": int(apoyo), "T_b_a": ref}


def control_cruzado(objp, img_src, img_dst, K_src, d_src, K_dst, d_dst, T_dst_src) -> float:
    """RMS (px) en `dst` de la pose del tablero vista por `src` sola, llevada a `dst` con
    `T_dst<-src` y proyectada, frente a las esquinas detectadas en `dst`."""
    T_src, _e = pose_tablero(objp, img_src, K_src, d_src)
    d = _proyectar(objp, np.asarray(T_dst_src) @ T_src, K_dst, d_dst) - np.asarray(img_dst, dtype=np.float64).reshape(-1, 2)
    return float(np.sqrt(np.mean(np.sum(d * d, axis=1))))


def calibrar_par(obj_points, img_a, img_b, K_a, d_a, K_b, d_b, shape, n_control: int = 3,
                 semilla: int = 0) -> dict:
    """Aparta `n_control` vistas, ajusta R, T con el resto (stereoCalibrate, intrinsecos fijos)
    y mide la reproyeccion cruzada de las de control. `img_b` ya en el orden de `img_a`.

    Devuelve R, T (x_b = R x_a + T), T_b_a, T_a_b (4x4), rms_px, errores_vista_px (por vista del
    ajuste, [a, b]), indices_fit, indices_control, errores_control_px y rms_control_px (a -> b),
    errores_control_inverso_px y rms_control_inverso_px (b -> a), n_vistas_usadas, n_control,
    angulo_deg (entre ejes opticos) y base_mm.
    """
    n = len(obj_points)
    if not (n == len(img_a) == len(img_b)):
        raise ValueError(f"obj_points ({n}), img_a ({len(img_a)}) e img_b ({len(img_b)}) no casan")
    idx_control = cc.elegir_control(n, n_control, semilla)
    idx_fit = [i for i in range(n) if i not in idx_control]
    if len(idx_fit) < 2:
        raise ValueError(f"quedan {len(idx_fit)} vistas para el ajuste tras apartar {n_control} de control")
    K_a, K_b = np.asarray(K_a, dtype=np.float64), np.asarray(K_b, dtype=np.float64)
    d_a, d_b = np.asarray(d_a, dtype=np.float64).flatten(), np.asarray(d_b, dtype=np.float64).flatten()
    objs = [np.asarray(obj_points[i], dtype=np.float32).reshape(-1, 3) for i in idx_fit]
    ia = [np.asarray(img_a[i], dtype=np.float32).reshape(-1, 1, 2) for i in idx_fit]
    ib = [np.asarray(img_b[i], dtype=np.float32).reshape(-1, 1, 2) for i in idx_fit]
    (rms, _K1, _d1, _K2, _d2, R, T, _E, _F, _rv, _tv, per_view) = cv2.stereoCalibrateExtended(
        objs, ia, ib, K_a.copy(), d_a.copy(), K_b.copy(), d_b.copy(), (int(shape[0]), int(shape[1])), None, None,
        flags=cv2.CALIB_FIX_INTRINSIC, criteria=CRITERIOS_ESTEREO)
    R = np.asarray(R, dtype=np.float64)
    T = np.asarray(T, dtype=np.float64).flatten()
    T_b_a = np.eye(4)
    T_b_a[:3, :3], T_b_a[:3, 3] = R, T
    T_a_b = inv(T_b_a)
    e_ab = [control_cruzado(obj_points[i], img_a[i], img_b[i], K_a, d_a, K_b, d_b, T_b_a) for i in idx_control]
    e_ba = [control_cruzado(obj_points[i], img_b[i], img_a[i], K_b, d_b, K_a, d_a, T_a_b) for i in idx_control]
    return {
        "R": R, "T": T, "T_b_a": T_b_a, "T_a_b": T_a_b, "rms_px": float(rms),
        "errores_vista_px": [[float(x) for x in fila] for fila in np.asarray(per_view, dtype=np.float64).reshape(-1, 2)],
        "indices_fit": idx_fit, "indices_control": idx_control,
        "errores_control_px": e_ab, "rms_control_px": float(np.sqrt(np.mean(np.square(e_ab)))) if e_ab else None,
        "errores_control_inverso_px": e_ba,
        "rms_control_inverso_px": float(np.sqrt(np.mean(np.square(e_ba)))) if e_ba else None,
        "n_vistas_usadas": len(idx_fit), "n_control": len(idx_control),
        "angulo_deg": ex.optical_axis_angle_deg(T_a_b), "base_mm": float(np.linalg.norm(T_a_b[:3, 3])),
    }


def triangular(img_a, img_b, K_a, d_a, K_b, d_b, R, T) -> np.ndarray:
    """Los puntos 3D (N, 3), en el frame de `a`, de las esquinas de una vista vistas por las dos."""
    na = cv2.undistortPointsIter(np.asarray(img_a, dtype=np.float64).reshape(-1, 1, 2), np.asarray(K_a, dtype=np.float64),
                                 np.asarray(d_a, dtype=np.float64), None, None, CRITERIOS_UNDISTORT).reshape(-1, 2)
    nb = cv2.undistortPointsIter(np.asarray(img_b, dtype=np.float64).reshape(-1, 1, 2), np.asarray(K_b, dtype=np.float64),
                                 np.asarray(d_b, dtype=np.float64), None, None, CRITERIOS_UNDISTORT).reshape(-1, 2)
    P1 = np.hstack([np.eye(3), np.zeros((3, 1))])
    P2 = np.hstack([np.asarray(R, dtype=np.float64).reshape(3, 3), np.asarray(T, dtype=np.float64).reshape(3, 1)])
    X = cv2.triangulatePoints(P1, P2, np.ascontiguousarray(na.T), np.ascontiguousarray(nb.T))
    return (X[:3] / X[3]).T


def _ajuste_rigido_rms(X: np.ndarray, modelo: np.ndarray) -> float:
    """RMS (mm) de los puntos triangulados frente al modelo del tablero tras el mejor ajuste rigido."""
    a = modelo - modelo.mean(axis=0)
    b = X - X.mean(axis=0)
    U, _s, Vt = np.linalg.svd(a.T @ b)
    D = np.diag([1.0, 1.0, np.sign(np.linalg.det(Vt.T @ U.T))])
    Rk = Vt.T @ D @ U.T
    r = (Rk @ a.T).T - b
    return float(np.sqrt(np.mean(np.sum(r * r, axis=1))))


def distancias_trianguladas(img_a, img_b, K_a, d_a, K_b, d_b, R, T, cols: int, rows: int,
                            square_mm: float | None = None) -> dict:
    """Por vista, la distancia triangulada entre las esquinas opuestas del tablero (las dos
    diagonales, mm). Con `square_mm`, ademas la nominal `lado * hypot(cols-1, rows-1)`, el error
    de cada diagonal, el peor en valor absoluto y el RMS del ajuste rigido de las esquinas
    trianguladas al modelo del tablero (mm). R, T llevan de `a` a `b`."""
    n = cols * rows
    nominal = None if square_mm is None else float(square_mm) * float(np.hypot(cols - 1, rows - 1))
    modelo = None if square_mm is None else cc.construir_objp(cols, rows, float(square_mm)).astype(np.float64)
    filas = []
    for va, vb in zip(img_a, img_b):
        X = triangular(va, vb, K_a, d_a, K_b, d_b, R, T)
        if len(X) != n:
            raise ValueError(f"una vista tiene {len(X)} esquinas y el tablero {n}")
        diag = [float(np.linalg.norm(X[0] - X[n - 1])), float(np.linalg.norm(X[cols - 1] - X[n - cols]))]
        fila = {"diagonales_mm": diag, "z_mm": float(X[:, 2].mean())}
        if nominal is not None:
            fila["error_mm"] = [d - nominal for d in diag]
            fila["ajuste_rigido_rms_mm"] = _ajuste_rigido_rms(X, modelo)
        filas.append(fila)
    out = {"por_vista": filas, "nominal_mm": nominal, "n_vistas": len(filas)}
    if nominal is not None and filas:
        errores = [e for f in filas for e in f["error_mm"]]
        out["peor_error_mm"] = float(max(abs(e) for e in errores))
        out["media_error_mm"] = float(np.mean(errores))
    return out


def evaluar_criterio(r: dict, tri_control: dict | None, criterio: dict = CRITERIO) -> list[str]:
    """Lo que no cumple el criterio de la fase 7 (vacia = cumple)."""
    fallos = []
    if r["n_vistas_usadas"] < criterio["min_vistas"]:
        fallos.append(f"vistas en el ajuste {r['n_vistas_usadas']} < {criterio['min_vistas']}")
    if r["rms_px"] > criterio["rms_px"]:
        fallos.append(f"RMS de stereoCalibrate {r['rms_px']:.3f} px > {criterio['rms_px']}")
    rc = r.get("rms_control_px")
    if rc is None:
        fallos.append("sin vistas de control")
    elif rc > criterio["rms_control_px"]:
        fallos.append(f"reproyeccion de control {rc:.3f} px > {criterio['rms_control_px']}")
    peor = (tri_control or {}).get("peor_error_mm")
    if peor is None:
        fallos.append("sin distancia triangulada de control")
    elif peor > criterio["triangulada_mm"]:
        fallos.append(f"distancia triangulada a {peor:.3f} mm de la nominal > {criterio['triangulada_mm']}")
    return fallos


def comparar_extrinsecos(T_a: np.ndarray, T_b: np.ndarray, distancia_mm: float = PUNTO_COMPARACION_MM) -> dict:
    """Dos `T_ref<-other`: la diferencia de traslacion (mm) y de giro (grados), la de la base y
    la del angulo entre ejes, y cuanto se separan al llevar a `ref` un punto a `distancia_mm`
    delante de `other` (en su eje optico)."""
    T_a, T_b = np.asarray(T_a, dtype=np.float64).reshape(4, 4), np.asarray(T_b, dtype=np.float64).reshape(4, 4)
    dmm, ddeg = pose_difference(T_a, T_b)
    p = np.array([0.0, 0.0, float(distancia_mm), 1.0])
    return {"dt_mm": float(dmm), "dR_deg": float(ddeg),
            "dt_xyz_mm": [float(x) for x in (T_a[:3, 3] - T_b[:3, 3])],
            "dbase_mm": float(np.linalg.norm(T_a[:3, 3]) - np.linalg.norm(T_b[:3, 3])),
            "dangulo_deg": float(ex.optical_axis_angle_deg(T_a) - ex.optical_axis_angle_deg(T_b)),
            "punto_a_mm": float(distancia_mm), "punto_se_mueve_mm": float(np.linalg.norm((T_a @ p - T_b @ p)[:3]))}


def alternativas_de_resultados(rep: dict) -> dict:
    """Los extrinsecos por Marker0 (`marker0`) y los del ajuste conjunto (`bundle`) de un
    `resultados.json` de `python -m fusion.experiment`, con sus numeros. ValueError si no los trae."""
    ext = rep.get("extrinsecos") or {}
    if not ext.get("T_ref_other"):
        raise ValueError("ese resultados.json no trae extrinsecos (extrinsecos.T_ref_other)")
    c1 = rep.get("criterio_1") or {}
    out = {"marker0": {"method": "marker0", "T_ref_other": np.asarray(ext["T_ref_other"], dtype=np.float64).reshape(4, 4),
                       "spread_mm": ext.get("spread_mm"), "spread_deg": ext.get("spread_deg"),
                       "angle_deg": ext.get("angle_deg"), "datos": rep.get("datos"),
                       "criterio_1_peor_mm": c1.get("peor_mm"), "criterio_1_peor_deg": c1.get("peor_deg"),
                       "criterio_1_cumple": c1.get("cumple")}}
    bundle = (rep.get("consistencia") or {}).get("bundle")
    if bundle and bundle.get("T_ref_other"):
        out["bundle"] = {"method": "bundle", "T_ref_other": np.asarray(bundle["T_ref_other"], dtype=np.float64).reshape(4, 4),
                         "rms_px": bundle.get("rms_px"), "angle_deg": bundle.get("angle_deg"), "datos": rep.get("datos")}
    return out


def criterio_1_con(T_ref_other: np.ndarray, data_dir, intrinsics: dict[str, Path],
                   anchor_tol_ms: float = 1.0) -> dict:
    """El criterio 1 del spec con unos extrinsecos dados (los del tablero no dependen de Marker0,
    asi que no hace falta validacion cruzada): por cada posicion de S2 de la grabacion, la pose de
    gs2 llevada a gs1 frente a la de gs1 (media de la diferencia, mm y grados); cuenta la peor de
    las posiciones de S2 (P16). `S2_pos1_fin` se da aparte (`repetida`), sin contar."""
    from fusion import dataset as ds
    from fusion import experiment as fx
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"no existe la carpeta de la grabacion de S2: {data_dir}")
    out: dict = {"datos": data_dir.name, "tolerancia_ancla_ms": float(anchor_tol_ms), "por_posicion": [], "fuera": [],
                 "umbral_mm": fx.THRESH["agreement_mm"], "umbral_deg": fx.THRESH["agreement_deg"]}
    for seg, info in fx.SEGMENTS.items():
        if info.get("role") not in ("S2", "S2_rep"):
            continue
        try:
            ds.segment_file(data_dir, seg, REF)
        except FileNotFoundError:
            continue
        tracks = ds.load_segment(data_dir, seg, (REF, OTHER))
        check = ds.check_segment(tracks, intrinsics, ds.expected_duration(tracks[REF].meta), anchor_tol_ms=anchor_tol_ms)
        pairs, _tol = fx.pairs_of(tracks)
        if not check["ok"] or len(pairs) == 0:
            out["fuera"].append({"segmento": seg, "motivos": list(check["reasons"]) or ["sin parejas"]})
            continue
        agr = ex.agreement_stats(tracks[REF].T_raw[pairs[:, 0]],
                                 ex.apply_extrinsics(T_ref_other, tracks[OTHER].T_raw[pairs[:, 1]]))
        out["por_posicion"].append({"segmento": seg, "repetida": info.get("role") == "S2_rep", **agr,
                                    "cumple": bool(agr["mean_mm"] < out["umbral_mm"] and agr["mean_deg"] < out["umbral_deg"])})
    cuentan = [r for r in out["por_posicion"] if not r["repetida"]]
    if not cuentan:
        out.update({"cumple": None, "nota": "ninguna posicion de S2 usable en esa carpeta: el criterio 1 queda sin evaluar"})
        return out
    out.update({"peor_mm": float(max(r["mean_mm"] for r in cuentan)), "peor_deg": float(max(r["mean_deg"] for r in cuentan)),
                "posiciones": len(cuentan), "min_parejas": int(min(r["n"] for r in cuentan))})
    out["cumple"] = bool(out["peor_mm"] < out["umbral_mm"] and out["peor_deg"] < out["umbral_deg"])
    return out


# ----------------------------------------------------------------------------
# Las vistas: una carpeta de frames por posicion y camara
# ----------------------------------------------------------------------------

def listar_posiciones(carpeta, camaras: tuple[str, ...] = (REF, OTHER)) -> dict[str, dict]:
    """`{posicion: {"intento": n, "carpetas": {camara: Path}}}` de `<pos>_<cam>[_rN]_frames`.
    De una posicion repetida gana el ultimo intento que tenga las dos camaras; una posicion a
    la que le falta una camara queda con `carpetas` incompleto (quien llama lo dice)."""
    d = Path(carpeta)
    if not d.is_dir():
        raise FileNotFoundError(f"no existe la carpeta de vistas: {d}")
    patron = re.compile(r"^(?P<pos>.+)_(?P<cam>" + "|".join(re.escape(c) for c in camaras) + r")(?:_r(?P<n>\d+))?_frames$")
    por: dict[str, dict[int, dict[str, Path]]] = {}
    for p in sorted(d.iterdir()):
        m = patron.match(p.name) if p.is_dir() else None
        if not m:
            continue
        por.setdefault(m.group("pos"), {}).setdefault(int(m.group("n") or 1), {})[m.group("cam")] = p
    out = {}
    for pos in sorted(por):
        completos = [n for n, c in por[pos].items() if all(cam in c for cam in camaras)]
        n = max(completos) if completos else max(por[pos])
        out[pos] = {"intento": n, "carpetas": por[pos][n]}
    return out


def esquinas_de_posicion(dir_frames, cols: int, rows: int, detector: str, n_frames: int = FRAMES_POR_VISTA,
                         max_mov_px: float = MAX_MOVIMIENTO_PX) -> dict:
    """Las esquinas del tablero en una carpeta de frames de una camara: la media sobre los
    ultimos `n_frames` `frame_*.png` (cada uno puesto en el orden del primero) y cuanto se
    mueven entre frames (`movimiento_px`, la mayor distancia de una esquina a su media).
    `esquinas` es None, con `motivo`, si el tablero no se ve en bastantes frames (2, o 1 si
    solo hay uno) o si se movio mas de `max_mov_px`."""
    d = Path(dir_frames)
    frames = sorted(d.glob("frame_*.png"))[-int(n_frames):] if d.is_dir() else []
    out: dict = {"carpeta": d.name, "n_frames": len(frames), "n_detectados": 0, "movimiento_px": None,
                 "shape": None, "esquinas": None, "motivo": None}
    if not frames:
        out["motivo"] = f"sin frames (frame_*.png) en {d.name}"
        return out
    det, shapes = [], set()
    for p in frames:
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if g is None:
            raise ValueError(f"no se pudo leer el frame {p}")
        shapes.add(g.shape[::-1])
        c = cc.detectar_esquinas(g, cols, rows, detector)
        if c is None:
            continue
        c = c.reshape(-1, 2).astype(np.float64)
        if det:                                 # en el orden del primero
            c = min((reordenar(c, cols, rows, o) for o in ORDENES),
                    key=lambda x: float(np.max(np.linalg.norm(x - det[0], axis=1))))
        det.append(c)
    if len(shapes) != 1:
        raise ValueError(f"los frames de {d.name} no son todos del mismo tamano: {sorted(shapes)}")
    out["shape"] = tuple(int(x) for x in shapes.pop())
    out["n_detectados"] = len(det)
    minimo = 2 if len(frames) >= 2 else 1
    if len(det) < minimo:
        out["motivo"] = f"el detector {detector} vio el tablero en {len(det)} de {len(frames)} frames (minimo {minimo})"
        return out
    media = np.mean(det, axis=0)
    if len(det) >= 2:
        out["movimiento_px"] = float(max(np.max(np.linalg.norm(c - media, axis=1)) for c in det))
        if out["movimiento_px"] > max_mov_px:
            out["motivo"] = (f"el tablero se movio {out['movimiento_px']:.2f} px entre frames "
                             f"(tope {max_mov_px:g}): no estaba quieto")
            return out
    out["esquinas"] = media.astype(np.float32).reshape(-1, 1, 2)
    return out


def detectar_posiciones(carpeta, intr: dict[str, dict], cols: int, rows: int, square_mm: float, detector: str,
                        n_frames: int, max_mov_px: float, solo: list[str] | None = None,
                        excluir: list[str] | None = None) -> list[dict]:
    """Una fila por posicion de la carpeta: `nombre`, `intento`, `usable`, `motivo` y, por camara,
    lo de `esquinas_de_posicion` mas la pose del tablero vista por ella sola (`z_mm`,
    `inclinacion_deg`, `rms_pnp_px`). Aborta si un frame no es del tamano de sus intrinsecos."""
    objp = cc.construir_objp(cols, rows, square_mm)
    posiciones = listar_posiciones(carpeta, (REF, OTHER))
    for nombre in list(solo or []) + list(excluir or []):
        if nombre not in posiciones:
            raise ValueError(f"la posicion {nombre!r} no esta en {carpeta} (hay: {', '.join(posiciones) or 'ninguna'})")
    filas = []
    for nombre, info in posiciones.items():
        if solo and nombre not in solo:
            continue
        fila: dict = {"nombre": nombre, "intento": info["intento"], "usable": True, "motivo": None, "camaras": {}}
        if excluir and nombre in excluir:
            fila.update({"usable": False, "motivo": "excluida con --excluir"})
            filas.append(fila)
            continue
        for cam in (REF, OTHER):
            if cam not in info["carpetas"]:
                fila.update({"usable": False, "motivo": f"falta la carpeta de frames de {cam}"})
                continue
            e = esquinas_de_posicion(info["carpetas"][cam], cols, rows, detector, n_frames, max_mov_px)
            if e["shape"] is not None and intr[cam]["shape"] is not None and tuple(e["shape"]) != tuple(intr[cam]["shape"]):
                raise ValueError(f"{e['carpeta']}: los frames son de {e['shape'][0]}x{e['shape'][1]} y los intrinsecos de "
                                 f"{cam} de {intr[cam]['shape'][0]}x{intr[cam]['shape'][1]}")
            if e["esquinas"] is None:
                fila["usable"] = False
                fila["motivo"] = (fila["motivo"] + "; " if fila["motivo"] else "") + f"{cam}: {e['motivo']}"
            else:
                T, rms = pose_tablero(objp, e["esquinas"], intr[cam]["K"], intr[cam]["dist"])
                e.update({"z_mm": float(T[2, 3]), "rms_pnp_px": rms,
                          "inclinacion_deg": float(np.degrees(np.arccos(min(1.0, abs(float(T[2, 2]))))))})
            fila["camaras"][cam] = e
        filas.append(fila)
    return filas


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, Path):
        return str(x)
    return x


def _cam_path(texto: str) -> tuple[str, Path]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera CAMARA=RUTA, no {texto!r}")
    c, r = texto.split("=", 1)
    return c.strip(), Path(r.strip())


def _fila_reporte(fila: dict) -> dict:
    """La fila de una posicion sin las esquinas (para el reporte)."""
    return {**{k: v for k, v in fila.items() if k != "camaras"},
            "camaras": {c: {k: v for k, v in e.items() if k != "esquinas"} for c, e in fila["camaras"].items()}}


def _log_posiciones(filas: list[dict]) -> None:
    for f in filas:
        partes = []
        for cam in (REF, OTHER):
            e = f["camaras"].get(cam)
            if e is None:
                partes.append(f"{cam}: sin carpeta")
            elif e.get("esquinas") is None:
                partes.append(f"{cam}: NO ({e['n_detectados']} de {e['n_frames']} frames)")
            else:
                mov = "-" if e["movimiento_px"] is None else f"{e['movimiento_px']:.3f}"
                partes.append(f"{cam}: {e['n_detectados']} de {e['n_frames']} frames, movimiento {mov} px, "
                              f"z {e['z_mm']:.0f} mm, inclinacion {e['inclinacion_deg']:.0f} grados, PnP {e['rms_pnp_px']:.3f} px")
        log_stats(f"{f['nombre']}{'' if f['intento'] == 1 else ' (intento ' + str(f['intento']) + ')'}: "
                  f"{'usable' if f['usable'] else 'FUERA'} | " + " | ".join(partes)
                  + (f" | motivo: {f['motivo']}" if f["motivo"] else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extrinsecos de gs2 respecto a gs1 por tablero (stereoCalibrate, intrinsecos fijos).")
    ap.add_argument("--desde-vistas", required=True, type=Path,
                    help="carpeta con <pos>_<cam>[_rN]_frames/frame_*.png (los frames de tracker --record --save-frames)")
    ap.add_argument("--intrinsecos", required=True, nargs="+", type=_cam_path, metavar="CAM=YML",
                    help="gs1=<yml> gs2=<yml>: los intrinsecos de data/ (no se tocan; su sha256 va al .yml)")
    ap.add_argument("--cols", type=int, required=True, help="esquinas interiores horizontales (9x6 casillas = 8)")
    ap.add_argument("--rows", type=int, required=True, help="esquinas interiores verticales (9x6 casillas = 5)")
    ap.add_argument("--square-mm", type=float, required=True, help="lado de la casilla medido (data/tablero_calibracion.yaml: 24.86)")
    ap.add_argument("--detector", choices=cc.DETECTORES, required=True, help="el de los intrinsecos (sb)")
    ap.add_argument("--frames-por-vista", type=int, default=FRAMES_POR_VISTA, help="ultimos frames de cada carpeta que se promedian")
    ap.add_argument("--max-movimiento-px", type=float, default=MAX_MOVIMIENTO_PX,
                    help="tope de lo que se mueve una esquina entre frames para dar el tablero por quieto")
    ap.add_argument("--min-vistas", type=int, default=CRITERIO["min_vistas"], help="vistas minimas en el ajuste (sin las de control)")
    ap.add_argument("--n-control", type=int, default=3, help="vistas apartadas para la validacion")
    ap.add_argument("--semilla", type=int, default=0, help="semilla de la eleccion de las vistas de control")
    ap.add_argument("--posiciones", nargs="*", default=[], metavar="POS", help="solo estas posiciones (por defecto, todas)")
    ap.add_argument("--excluir", nargs="*", default=[], metavar="POS", help="posiciones que se dejan fuera, a mano")
    ap.add_argument("--solo-comprobar", action="store_true", help="no calibra: dice si el tablero se ve y esta quieto en cada posicion")
    ap.add_argument("--montaje", choices=["pinzas", "estructura"], help="obligatorio para calibrar (va al .yml)")
    ap.add_argument("--output", type=Path, help="el .yml de extrinsecos (no se pisa); solo se escribe si el criterio cumple")
    ap.add_argument("--comparar-con", type=Path, help="resultados.json de fusion.experiment: los extrinsecos por Marker0")
    ap.add_argument("--criterio-1-datos", type=Path, help="carpeta de la grabacion de S2: repite el criterio 1 con los del tablero")
    ap.add_argument("--tolerancia-ancla-ms", type=float, default=1.0, help="la de fusion.experiment (20 para las grabaciones del PC)")
    ap.add_argument("--reporte", type=Path, help="JSON con el detalle")
    ap.add_argument("--timeout", type=float, required=True, help="tope en segundos (principio 9)")
    args = ap.parse_args(argv)

    if args.cols < 2 or args.rows < 2 or args.cols == args.rows:
        ap.error("--cols y --rows >= 2 y distintos (un tablero cuadrado tiene mas ordenes ambiguos)")
    if args.square_mm <= 0 or args.frames_por_vista < 1 or args.max_movimiento_px <= 0 or args.timeout <= 0:
        ap.error("--square-mm, --max-movimiento-px y --timeout > 0; --frames-por-vista >= 1")
    if args.n_control < 1 or args.min_vistas < 2:
        ap.error("--n-control >= 1 (la validacion va aparte del ajuste) y --min-vistas >= 2")
    if not args.solo_comprobar and not args.montaje:
        ap.error("para calibrar hace falta --montaje")
    intr_rutas = dict(args.intrinsecos)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": [str(a) for a in (sys.argv[1:] if argv is None else argv)],
                    "opencv": cv2.__version__, "vistas": str(args.desde_vistas), "detector": args.detector,
                    "tablero": {"cols": args.cols, "rows": args.rows, "square_mm": args.square_mm},
                    "criterio": dict(CRITERIO, min_vistas=args.min_vistas), "modo": "comprobar" if args.solo_comprobar else "calibrar"}
    try:
        for cam in (REF, OTHER):
            if cam not in intr_rutas or not intr_rutas[cam].is_file():
                raise FileNotFoundError(f"faltan los intrinsecos de {cam} (--intrinsecos {cam}=<yml>)")
        intr = {cam: leer_intrinsecos(intr_rutas[cam]) for cam in (REF, OTHER)}
        if not args.desde_vistas.is_dir():
            raise FileNotFoundError(f"no existe la carpeta de vistas: {args.desde_vistas}")
        if args.output is not None and args.output.exists():
            raise FileExistsError(f"los extrinsecos ya existen, no se pisan: {args.output}")
        if args.comparar_con is not None and not args.comparar_con.is_file():
            raise FileNotFoundError(f"no existe el resultados.json de --comparar-con: {args.comparar_con}")
        if args.criterio_1_datos is not None and not args.criterio_1_datos.is_dir():
            raise FileNotFoundError(f"no existe la carpeta de la grabacion de S2: {args.criterio_1_datos}")
    except (OSError, ValueError) as e:
        log_error(str(e))
        return 2
    estado["intrinsecos"] = {cam: {"archivo": intr_rutas[cam].name, "sha256": sha256_file(intr_rutas[cam]),
                                   "detector": intr[cam]["detector"], "square_mm": intr[cam]["square_mm"]} for cam in intr}
    for cam in intr:
        if intr[cam]["detector"] and intr[cam]["detector"] != args.detector:
            log_warn(f"los intrinsecos de {cam} se calibraron con el detector {intr[cam]['detector']} y aqui se usa {args.detector}")
        if intr[cam]["square_mm"] and abs(intr[cam]["square_mm"] - args.square_mm) > 0.011:
            log_warn(f"los intrinsecos de {cam} se calibraron con un lado de {intr[cam]['square_mm']:.2f} mm y aqui se da {args.square_mm:.2f}")

    vig = _vigilante(args.timeout, estado, args.reporte)
    rc = 0
    try:
        log_info(f"Vistas: {args.desde_vistas} | tablero {args.cols}x{args.rows} esquinas @ {args.square_mm} mm | detector {args.detector} | "
                 f"{args.frames_por_vista} frames por vista, movimiento <= {args.max_movimiento_px:g} px")
        t0 = time.monotonic()
        filas = detectar_posiciones(args.desde_vistas, intr, args.cols, args.rows, args.square_mm, args.detector,
                                    args.frames_por_vista, args.max_movimiento_px, args.posiciones, args.excluir)
        if not filas:
            raise ValueError(f"no hay ninguna posicion (<pos>_<cam>_frames) en {args.desde_vistas}")
        _log_posiciones(filas)
        usables = [f for f in filas if f["usable"]]
        estado["posiciones"] = [_fila_reporte(f) for f in filas]
        estado["usables"] = len(usables)
        estado["cobertura"] = {cam: cc.cobertura([f["camaras"][cam]["esquinas"] for f in usables], intr[cam]["shape"])
                               for cam in intr if usables and intr[cam]["shape"]}
        log_stats(f"Posiciones: {len(filas)}, usables en las dos camaras {len(usables)} "
                  f"(cobertura {', '.join(f'{c} {v:.2f}' for c, v in estado['cobertura'].items()) or '-'}) en {time.monotonic() - t0:.1f} s")
        if args.solo_comprobar:
            return 0 if len(usables) == len(filas) else 1

        necesarias = args.min_vistas + args.n_control
        if len(usables) < necesarias:
            raise PocasVistas(f"hacen falta {necesarias} posiciones usables ({args.min_vistas} de ajuste + {args.n_control} de "
                              f"control) y hay {len(usables)}: grabar mas posiciones")
        objp = cc.construir_objp(args.cols, args.rows, args.square_mm)
        Ka, da, Kb, db = intr[REF]["K"], intr[REF]["dist"], intr[OTHER]["K"], intr[OTHER]["dist"]
        img_a = [f["camaras"][REF]["esquinas"] for f in usables]
        orden = emparejar_orden(objp, img_a, [f["camaras"][OTHER]["esquinas"] for f in usables], Ka, da, Kb, db,
                                args.cols, args.rows)
        estado["orden"] = {"apoyo": orden["apoyo"], "por_posicion": {f["nombre"]: o for f, o in zip(usables, orden["ordenes"])},
                           "incoherentes": [f["nombre"] for f, ok in zip(usables, orden["coherente"]) if not ok]}
        log_stats(f"Orden de las esquinas de {OTHER} frente a {REF}: " +
                  ", ".join(f"{o} x{orden['ordenes'].count(o)}" for o in ORDENES if o in orden["ordenes"]) +
                  f"; vistas de acuerdo con la referencia: {orden['apoyo'] + 1} de {len(usables)}")
        for nombre in estado["orden"]["incoherentes"]:
            log_warn(f"{nombre}: ningun orden de sus esquinas casa con las demas vistas (el tablero se movio entre "
                     f"las dos camaras o una deteccion es mala); queda fuera")
        buenas = [k for k, ok in enumerate(orden["coherente"]) if ok]
        if len(buenas) < necesarias:
            raise PocasVistas(f"tras quitar las vistas incoherentes quedan {len(buenas)} y hacen falta {necesarias}")
        nombres = [usables[k]["nombre"] for k in buenas]
        ia = [img_a[k] for k in buenas]
        ib = [orden["img_b"][k] for k in buenas]
        objs = [objp.copy() for _ in buenas]

        log_info(f"Calibrando (cv2.stereoCalibrateExtended, CALIB_FIX_INTRINSIC) con {len(buenas) - args.n_control} vistas "
                 f"y {args.n_control} de control (semilla {args.semilla})...")
        r = calibrar_par(objs, ia, ib, Ka, da, Kb, db, usables[0]["camaras"][REF]["shape"], args.n_control, args.semilla)
        ctrl = r["indices_control"]
        tri_control = distancias_trianguladas([ia[i] for i in ctrl], [ib[i] for i in ctrl], Ka, da, Kb, db, r["R"], r["T"],
                                              args.cols, args.rows, args.square_mm)
        tri_ajuste = distancias_trianguladas([ia[i] for i in r["indices_fit"]], [ib[i] for i in r["indices_fit"]],
                                             Ka, da, Kb, db, r["R"], r["T"], args.cols, args.rows, args.square_mm)
        fallos = evaluar_criterio(r, tri_control, estado["criterio"])
        T_ref_other = r["T_a_b"]
        log_stats(f"RMS de stereoCalibrate: {r['rms_px']:.4f} px con {r['n_vistas_usadas']} vistas (criterio <= {CRITERIO['rms_px']})")
        peores = sorted(((max(e), nombres[i]) for e, i in zip(r["errores_vista_px"], r["indices_fit"])), reverse=True)[:3]
        log_stats(f"peores vistas del ajuste: {[(n, round(e, 3)) for e, n in peores]} (posicion, px)")
        log_stats(f"Control ({[nombres[i] for i in ctrl]}): {REF} -> {OTHER} {r['rms_control_px']:.4f} px (criterio <= "
                  f"{CRITERIO['rms_control_px']}), por vista {[round(e, 3) for e in r['errores_control_px']]}; "
                  f"{OTHER} -> {REF} {r['rms_control_inverso_px']:.4f} px (informativo)")
        log_stats(f"Distancia triangulada entre esquinas opuestas (control): nominal {tri_control['nominal_mm']:.2f} mm, peor error "
                  f"{tri_control['peor_error_mm']:.3f} mm (criterio <= {CRITERIO['triangulada_mm']}), media {tri_control['media_error_mm']:+.3f} mm; "
                  f"en las del ajuste, peor {tri_ajuste['peor_error_mm']:.3f} mm")
        log_stats(f"T_{REF}<-{OTHER}: base {r['base_mm']:.2f} mm, angulo entre ejes {r['angulo_deg']:.2f} grados, "
                  f"t = {np.round(T_ref_other[:3, 3], 2).tolist()} mm")
        # `estado` solo lleva tipos de JSON: el vigilante lo escribe tal cual si salta el tope.
        estado["resultado"] = _jsonable({**r, "T_ref_other": T_ref_other, "posiciones": nombres,
                                         "posiciones_ajuste": [nombres[i] for i in r["indices_fit"]],
                                         "posiciones_control": [nombres[i] for i in ctrl],
                                         "triangulada_control": tri_control, "triangulada_ajuste": tri_ajuste,
                                         "fallos": fallos, "cumple": not fallos})

        alternativa = None
        if args.comparar_con is not None:
            alts = alternativas_de_resultados(json.loads(args.comparar_con.read_text(encoding="utf-8")))
            estado["comparacion"] = {}
            for nombre, alt in alts.items():
                c = comparar_extrinsecos(T_ref_other, alt["T_ref_other"])
                estado["comparacion"][nombre] = _jsonable({**alt, "frente_al_tablero": c})
                log_stats(f"Frente a los de {nombre} ({alt.get('datos')}): dt {c['dt_mm']:.2f} mm, dR {c['dR_deg']:.2f} grados, "
                          f"base {c['dbase_mm']:+.2f} mm, angulo {c['dangulo_deg']:+.2f} grados; un punto a "
                          f"{c['punto_a_mm']:.0f} mm se mueve {c['punto_se_mueve_mm']:.2f} mm")
            alternativa = estado["comparacion"]["marker0"]
        c1 = None
        if args.criterio_1_datos is not None:
            c1 = criterio_1_con(T_ref_other, args.criterio_1_datos, intr_rutas, args.tolerancia_ancla_ms)
            estado["criterio_1"] = c1
            if c1["cumple"] is None:
                log_warn(f"criterio 1 sin evaluar: {c1['nota']}")
            else:
                for fila in c1["por_posicion"]:
                    log_stats(f"  {fila['segmento']}{' (repetida, no cuenta)' if fila['repetida'] else ''}: "
                              f"{fila['mean_mm']:.3f} mm / {fila['mean_deg']:.3f} grados con {fila['n']} parejas")
                log_stats(f"Criterio 1 con los extrinsecos del tablero ({c1['datos']}): peor {c1['peor_mm']:.3f} mm / "
                          f"{c1['peor_deg']:.3f} grados frente a < {c1['umbral_mm']} mm y < {c1['umbral_deg']} grados: "
                          f"{'cumple' if c1['cumple'] else 'NO cumple'}")

        if fallos:
            log_warn("Criterio de la fase 7 NO cumplido: " + "; ".join(fallos) + ". No se escribe el .yml.")
            rc = 1
        else:
            log_info("Criterio de la fase 7 cumplido (RMS, control, distancia triangulada y vistas).")
            if args.output is not None:
                validacion = {"rms_px": r["rms_px"], "rms_control_px": r["rms_control_px"],
                              "rms_control_inverso_px": r["rms_control_inverso_px"],
                              "n_vistas": r["n_vistas_usadas"], "n_control": r["n_control"],
                              "triangulada_nominal_mm": tri_control["nominal_mm"],
                              "triangulada_peor_error_mm": tri_control["peor_error_mm"],
                              "base_mm": r["base_mm"], "detector": args.detector, "square_mm": args.square_mm,
                              "vistas": args.desde_vistas.name, "posiciones_ajuste": estado["resultado"]["posiciones_ajuste"],
                              "posiciones_control": estado["resultado"]["posiciones_control"],
                              "criterio": estado["criterio"],
                              "criterio_1": None if c1 is None else {k: c1.get(k) for k in ("datos", "peor_mm", "peor_deg", "cumple", "posiciones", "min_parejas")},
                              "frente_al_ajuste_conjunto": (estado.get("comparacion", {}).get("bundle") or {}).get("frente_al_tablero")}
                ext = ex.Extrinsics(T_ref_other=T_ref_other, reference=REF, other=OTHER, method="tablero", mount=args.montaje,
                                    intrinsics_sha256={cam: estado["intrinsecos"][cam]["sha256"] for cam in (REF, OTHER)},
                                    angle_deg=r["angulo_deg"], validation=_jsonable(validacion), alternative=alternativa)
                ex.save_extrinsics(args.output, ext)
                ex.load_extrinsics(args.output, intr_rutas)        # verificacion de lectura
                estado["output"] = str(args.output)
                log_info(f"Guardado y verificado: {args.output} (metodo tablero, montaje {args.montaje})")
    except (RuntimeError, ValueError, OSError, cv2.error) as e:
        estado["error"] = str(e)
        log_error(str(e))
        rc = 1 if isinstance(e, PocasVistas) else 2
    finally:
        vig.cancel()
        if args.reporte is not None:
            args.reporte.parent.mkdir(parents=True, exist_ok=True)
            args.reporte.write_text(json.dumps(_jsonable(estado), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            log_info(f"Reporte: {args.reporte}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
