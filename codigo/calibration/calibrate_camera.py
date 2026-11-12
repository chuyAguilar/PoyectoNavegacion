# -*- coding: utf-8 -*-
"""
Calibracion intrinseca de una camara con tablero de ajedrez — iter 4.

Nacio en el brief-02 (M3b) como alternativa con OpenCV puro a MRPT; la meta 002
(fase 4, 2026-10-22) la rehace para calibrar las SVPRO global shutter por su
perfil (tracker_config_gs1.yaml / gs2.yaml) a la resolucion elegida.

Tablero: impreso en 3D por el autor (`Claude outputs/tablero/`, bicolor): 9x6
casillas de 25 mm nominales = 8x5 esquinas interiores. Los cuadros negros se
agrandaron 0.40 mm por lado alrededor del mismo centro (compensacion de la
impresion), asi que el paso no cambia. El lado que se pasa en --square-mm es el
MEDIDO con calibrador (media de >= 5 medidas de 4 casillas, dividida entre 4),
nunca el nominal; con --medidas-mm el script lo comprueba.

Que hace:
  1. Abre la camara SIEMPRE por su perfil (camera_backend: puerto, marca,
     ajustes y tamano) y sin .yml (un .yml vale para un solo tamano y aqui se
     esta creando). Este modulo importa camaras_uvc antes que cv2 (aceleracion
     HW de MSMF apagada, CONTEXT.md 4.18).
  2. Ventana: ESPACIO captura una vista (se detectan las esquinas con el
     --detector elegido y se guarda el frame en --vistas-dir como PNG), u quita
     la ultima, q termina. Dibuja la rejilla 4x3 de cobertura: las celdas con
     esquinas ya capturadas en verde.
  3. Aparta --n-control vistas (al azar con --semilla, reproducible), calibra
     con el resto (cv2.calibrateCameraExtended: RMS global, error por vista y
     desviacion de fx, fy, cx, cy) y mide el RMS de reproyeccion de las vistas
     de control con solvePnP + projectPoints (no entran al ajuste: un RMS bajo
     con una K mala no las engana, principio 3).
  4. Criterio (plan de la meta 002, fase 4): RMS <= 0.5 px con >= 15 vistas en
     el ajuste, RMS de control <= 0.75 px y cobertura >= 0.8 de las celdas 4x3.
     El .yml se guarda siempre (con el veredicto dentro); el codigo de salida
     es 1 si el criterio no se cumple.
  5. --desde-vistas DIR: sin camara, recalibra con las vistas guardadas (para
     comparar `clasico` y `sb` sobre las mismas imagenes). Si en DIR esta el
     captura.json que dejo la captura, el .yml hereda el puerto, el modo y los
     ajustes leidos de la camara.
  6. --detector ambos (P18, 2026-10-22): lo de la sesion en vivo de la fase 4
     en un solo proceso. Captura con el clasico (con camara) o toma las vistas
     de --desde-vistas, calibra con `clasico` y con `sb` sobre las mismas
     vistas guardadas (cada uno con las que detecta, como dos corridas
     --desde-vistas) y gana el de menor RMS de control entre los que cumplen
     el criterio (si ninguno cumple, el de menor control, y sale con 1). Solo
     el ganador se escribe en --output; los dos van al --reporte y el log dice
     los dos RMS de control y cual gano. Exige --n-control >= 1.

El .yml (formato OpenCV que leen los backends: camera_matrix y
distortion_coefficients) declara ademas image_width/image_height (el backend
para si el frame real no coincide), el detector, el RMS de control, la
cobertura, las desviaciones, el lado medido y las medidas del calibrador, el
perfil, el puerto USB, el modo y los ajustes leidos.

Detectores (Context7, OpenCV 4.13; instalado 4.11): `clasico` =
findChessboardCorners (ADAPTIVE_THRESH + NORMALIZE_IMAGE) + cornerSubPix
(ventana 11x11, 30 iteraciones / 0.001); `sb` = findChessboardCornersSB
(NORMALIZE_IMAGE + EXHAUSTIVE + ACCURACY), que segun la documentacion da la
posicion subpixel directamente y mas exacta que cornerSubPix; pide un borde
blanco de ~una casilla alrededor del tablero (el impreso tiene 10 mm).
calibrateCameraExtended devuelve en Python (retval, K, dist, rvecs, tvecs,
stdDeviationsIntrinsics, stdDeviationsExtrinsics, perViewErrors); retval es el
RMS global y stdDeviationsIntrinsics empieza por fx, fy, cx, cy.

Uso (desde codigo\\, con el venv; argumentos explicitos, principio 7):
    python -m calibration.calibrate_camera --config profiles\\tracker_config_gs1.yaml ^
        --output data\\intrinsecos_gs1_1280x960.yml ^
        --square-mm 24.97 --medidas-mm 99.90,99.85,99.92,99.88,99.86 ^
        --cols 8 --rows 5 --detector clasico ^
        --vistas-dir "..\\Claude outputs\\camaras\\vistas_gs1" ^
        --min-vistas 15 --n-control 3 --luz "caja nivel 2" ^
        --reporte "..\\Claude outputs\\camaras\\calibracion_gs1_clasico.json" --timeout 900
    python -m calibration.calibrate_camera --config profiles\\tracker_config_gs1.yaml ^
        --output "..\\Claude outputs\\camaras\\intrinsecos_gs1_sb.yml" --square-mm 24.97 ^
        --cols 8 --rows 5 --detector sb --desde-vistas "..\\Claude outputs\\camaras\\vistas_gs1" ^
        --min-vistas 15 --n-control 3 --reporte "..\\Claude outputs\\camaras\\calibracion_gs1_sb.json" --timeout 600
    python -m calibration.calibrate_camera --config profiles\\tracker_config_gs2.yaml ^
        --output data\\intrinsecos_gs2_1280x960.yml --square-mm 24.86 ^
        --medidas-mm 149.1,149.1,149.1,149.1,149.4 --casillas-por-medida 6 ^
        --cols 8 --rows 5 --detector ambos --vistas-dir "..\\Claude outputs\\camaras\\vistas_gs2" ^
        --min-vistas 15 --n-control 3 --luz "caja nivel 2" ^
        --reporte "..\\Claude outputs\\camaras\\calibracion_gs2_ambos.json" --timeout 900
Teclas: ESPACIO = capturar vista | u = quitar la ultima | q = calibrar y guardar

Desde la meta 006, fase 7d (El tablero ChArUco y los intrinsecos con el asistente de una camara;
P47, P51, P52):
  7. --desde-asistente DIR --camara CAM: sin camara, calibra con la carpeta que dejo
     `python -m calibration.capture_stereo_board --modo intrinsecos` (`<pos>_<cam>[_rN]_frames`):
     por posicion, la media de las esquinas de su rafaga (`vistas_del_asistente`). Excluye a
     --desde-vistas y a la captura con ESPACIO.
  8. --patron charuco --tablero-charuco data\\tablero_charuco.yaml --min-esquinas 12: las vistas
     son del tablero ChArUco (`calibration.charuco_board`): cada una trae las esquinas que se
     ven, con su ID, asi que las listas son de distinto largo (`calibrateCameraExtended` lo
     admite) y el tablero puede estar en parte fuera de la imagen. --cols, --rows, --square-mm y
     --detector sobran (los da el archivo; si se pasan, codigo 2). Solo con --desde-asistente.
  9. Criterios opcionales (P52), que se suman a los de siempre: --cobertura-fina-min sobre la
     rejilla --celdas-finas (8 6) y --max-std-px (la desviacion de fx, fy, cx y cy que da
     `calibrateCameraExtended`). --comparar-con YML: la diferencia de cada parametro con otro
     .yml y, donde los dos traen su desviacion, en sigmas combinadas (`comparar_intrinsecos`).
    python -m calibration.calibrate_camera --config profiles\\tracker_config_gs1.yaml ^
        --desde-asistente "<carpeta del asistente>" --camara gs1 --patron charuco ^
        --tablero-charuco data\\tablero_charuco.yaml --min-esquinas 12 --frames-por-vista 5 ^
        --max-movimiento-px 0.3 --min-vistas 25 --n-control 5 --semilla 0 --celdas-finas 8 6 ^
        --cobertura-fina-min 0.85 --max-std-px 1.0 --comparar-con data\\intrinsecos_gs1_1280x960.yml ^
        --output "..\\Claude outputs\\fases\\006\\fase-7e\\intrinsecos_gs1_propuesta.yml" ^
        --reporte "<json>" --timeout 600
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from camera import uvc as camaras_uvc  # noqa: F401  (antes de cv2: apaga la aceleracion HW de MSMF; meta 002, fase 2b)
import cv2
import numpy as np

from camera.backend import create_backend
import profiles
from diagnostics.probe_camera import _vigilante

TITULO_VENTANA = "Calibracion camara - ESPACIO captura, q calibra"
DETECTORES = ("clasico", "sb")
MODOS_DETECTOR = DETECTORES + ("ambos",)   # --detector; comprobar_escala usa solo DETECTORES
DETECTOR_CAPTURA_AMBOS = "clasico"         # con --detector ambos se captura con este (el de la sesion en vivo)
# Criterio de la fase 4 (plan de la meta 002): RMS, RMS de control, cobertura y vistas usadas.
CRITERIO = {"rms_px": 0.5, "rms_control_px": 0.75, "cobertura": 0.8, "min_vistas": 15}
CELDAS_COBERTURA = (4, 3)          # columnas x filas de la rejilla de cobertura
CRITERIOS_SUBPIX = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
EXT_VISTAS = (".png", ".jpg", ".jpeg", ".bmp")
ARCHIVO_CAPTURA = "captura.json"
PATRONES = ("ajedrez", "charuco")
CELDAS_FINAS = (8, 6)              # la rejilla fina de cobertura (fase 7d de la meta 006; P52)
PARAMETROS = ("fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2", "k3")   # los que compara `comparar_intrinsecos`
MARGEN_CALIBRAR_S = 300.0         # tras el tope de captura, lo que se deja a la calibracion
ANTIRREBOTE_S = 0.5


def log_info(m): print(f"[INFO] {m}", flush=True)
def log_warn(m): print(f"[WARN] {m}", flush=True)
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr, flush=True)
def log_stats(m): print(f"[STATS] {m}", flush=True)


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

def construir_objp(cols, rows, square_mm):
    """Puntos 3D del tablero (z=0), en mm."""
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_mm
    return objp


def lado_desde_medidas(medidas_mm: list[float], casillas_por_medida: int = 4) -> float:
    """El lado de la casilla: media de las medidas del calibrador entre las casillas que abarca cada una."""
    if len(medidas_mm) < 1:
        raise ValueError("sin medidas del calibrador")
    if casillas_por_medida < 1:
        raise ValueError(f"casillas_por_medida tiene que ser >= 1, no {casillas_por_medida}")
    if any(m <= 0 for m in medidas_mm):
        raise ValueError(f"una medida no es positiva: {medidas_mm}")
    return round(statistics.mean(medidas_mm) / casillas_por_medida, 2)


def comprobar_lado(square_mm: float, medidas_mm: list[float], casillas_por_medida: int = 4,
                   tolerancia_mm: float = 0.01, min_medidas: int = 5) -> float:
    """El lado derivado de las medidas; ValueError si hay menos de min_medidas o no coincide con square_mm."""
    if len(medidas_mm) < min_medidas:
        raise ValueError(f"hacen falta al menos {min_medidas} medidas del calibrador, hay {len(medidas_mm)}")
    lado = lado_desde_medidas(medidas_mm, casillas_por_medida)
    if abs(lado - square_mm) > tolerancia_mm + 1e-9:
        raise ValueError(f"--square-mm {square_mm:.2f} no coincide con las medidas: media "
                         f"{statistics.mean(medidas_mm):.3f} mm / {casillas_por_medida} = {lado:.2f} mm")
    return lado


def celdas_cubiertas(img_points, shape, celdas=CELDAS_COBERTURA) -> set:
    """Celdas (ix, iy) de la rejilla celdas = (columnas, filas) sobre una imagen shape = (w, h)
    con al menos una esquina de alguna vista."""
    w, h = int(shape[0]), int(shape[1])
    cx, cy = int(celdas[0]), int(celdas[1])
    if w <= 0 or h <= 0 or cx <= 0 or cy <= 0:
        raise ValueError(f"shape {shape} y celdas {celdas} tienen que ser positivos")
    ocupadas = set()
    for pts in img_points:
        p = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        if p.size == 0:
            continue
        ix = np.clip(np.floor(p[:, 0] * cx / w).astype(int), 0, cx - 1)
        iy = np.clip(np.floor(p[:, 1] * cy / h).astype(int), 0, cy - 1)
        ocupadas.update(zip(ix.tolist(), iy.tolist()))
    return ocupadas


def cobertura(img_points, shape, celdas=CELDAS_COBERTURA) -> float:
    """Fraccion de celdas de la rejilla con alguna esquina (0.0 sin vistas)."""
    return len(celdas_cubiertas(img_points, shape, celdas)) / float(celdas[0] * celdas[1])


def elegir_control(n_vistas: int, n_control: int, semilla: int = 0) -> list[int]:
    """Indices de las vistas de control (al azar, reproducible por la semilla), ordenados."""
    if n_control < 0 or n_control >= n_vistas:
        raise ValueError(f"n_control tiene que estar entre 0 y {n_vistas - 1} (hay {n_vistas} vistas), "
                         f"no {n_control}")
    if n_control == 0:
        return []
    return sorted(random.Random(semilla).sample(range(n_vistas), n_control))


def _error_vista(objp, imgp, K, dist, rvec, tvec) -> float:
    """RMS (px) de reproyeccion de una vista con una pose dada."""
    proy, _j = cv2.projectPoints(objp, rvec, tvec, K, dist)
    d = proy.reshape(-1, 2) - np.asarray(imgp, dtype=np.float64).reshape(-1, 2)
    return float(np.sqrt(np.mean(np.sum(d * d, axis=1))))


def errores_control(obj_points, img_points, K, dist) -> list[float]:
    """RMS (px) por vista de control: solvePnP con la K calibrada y reproyeccion."""
    errores = []
    for objp, imgp in zip(obj_points, img_points):
        ok, rvec, tvec = cv2.solvePnP(np.asarray(objp, dtype=np.float32),
                                      np.asarray(imgp, dtype=np.float32).reshape(-1, 1, 2),
                                      K, dist, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            raise RuntimeError("solvePnP no resolvio una vista de control")
        errores.append(_error_vista(objp, imgp, K, dist, rvec, tvec))
    return errores


def rms_control(obj_points, img_points, K, dist) -> float:
    """RMS (px) de todas las esquinas de las vistas de control (vistas del mismo tamano)."""
    e = errores_control(obj_points, img_points, K, dist)
    if not e:
        raise ValueError("sin vistas de control")
    return float(np.sqrt(np.mean(np.square(e))))


def calibrar(obj_points, img_points, shape, n_control: int = 3, semilla: int = 0, flags: int = 0) -> dict:
    """Aparta n_control vistas, calibra con el resto y mide el RMS de las de control.

    shape = (w, h). Devuelve K, dist (5), rms_px, errores_vista_px (del ajuste, en el orden
    de indices_fit), indices_fit, indices_control, errores_control_px, rms_control_px,
    std_intrinsecos (fx, fy, cx, cy), n_vistas_usadas, rvecs y tvecs del ajuste.
    """
    n = len(img_points)
    if n != len(obj_points):
        raise ValueError(f"obj_points ({len(obj_points)}) e img_points ({n}) no casan")
    if n < 2:
        raise ValueError(f"hacen falta al menos 2 vistas, hay {n}")
    idx_control = elegir_control(n, n_control, semilla)
    idx_fit = [i for i in range(n) if i not in idx_control]
    if len(idx_fit) < 2:
        raise ValueError(f"quedan {len(idx_fit)} vistas para el ajuste tras apartar {n_control} de control")
    objs = [np.asarray(obj_points[i], dtype=np.float32) for i in idx_fit]
    imgs = [np.asarray(img_points[i], dtype=np.float32).reshape(-1, 1, 2) for i in idx_fit]
    rms, K, dist, rvecs, tvecs, std_int, _std_ext, per_view = cv2.calibrateCameraExtended(
        objs, imgs, (int(shape[0]), int(shape[1])), None, None, flags=flags)
    K = np.asarray(K, dtype=np.float64)
    dist = np.asarray(dist, dtype=np.float64).flatten()
    std_int = np.asarray(std_int, dtype=np.float64).flatten()
    e_control = errores_control([obj_points[i] for i in idx_control],
                                [img_points[i] for i in idx_control], K, dist) if idx_control else []
    return {
        "K": K, "dist": dist, "rms_px": float(rms),
        "errores_vista_px": [float(e) for e in np.asarray(per_view).flatten()],
        "indices_fit": idx_fit, "indices_control": idx_control,
        "errores_control_px": e_control,
        "rms_control_px": float(np.sqrt(np.mean(np.square(e_control)))) if e_control else None,
        "std_intrinsecos": {"fx": float(std_int[0]), "fy": float(std_int[1]),
                            "cx": float(std_int[2]), "cy": float(std_int[3])},
        "std_distorsion": {n: float(std_int[4 + k]) for k, n in enumerate(PARAMETROS[4:]) if 4 + k < len(std_int)},
        "n_vistas_usadas": len(idx_fit), "n_control": len(idx_control),
        "rvecs": [np.asarray(r).flatten() for r in rvecs], "tvecs": [np.asarray(t).flatten() for t in tvecs],
    }


def evaluar_criterio(resultado: dict, cob: float, criterio: dict = CRITERIO, cob_fina: float | None = None,
                     cob_fina_min: float | None = None, max_std_px: float | None = None) -> list[str]:
    """Lo que no cumple el criterio de la fase 4 (vacia = cumple). Con `cob_fina_min`, ademas la
    cobertura de la rejilla fina (`cob_fina`) >= ese minimo; con `max_std_px`, ademas la desviacion
    de fx, fy, cx y cy <= ese tope (P52; meta 006, fase 7d). Sin ellos, lo de siempre."""
    fallos = []
    if resultado["n_vistas_usadas"] < criterio["min_vistas"]:
        fallos.append(f"vistas usadas {resultado['n_vistas_usadas']} < {criterio['min_vistas']}")
    if resultado["rms_px"] > criterio["rms_px"]:
        fallos.append(f"RMS {resultado['rms_px']:.3f} px > {criterio['rms_px']}")
    rc = resultado.get("rms_control_px")
    if rc is None:
        fallos.append("sin vistas de control")
    elif rc > criterio["rms_control_px"]:
        fallos.append(f"RMS de control {rc:.3f} px > {criterio['rms_control_px']}")
    if cob < criterio["cobertura"]:
        fallos.append(f"cobertura {cob:.2f} < {criterio['cobertura']}")
    if cob_fina_min is not None:
        if cob_fina is None:
            fallos.append("sin cobertura fina que comparar")
        elif cob_fina < cob_fina_min:
            fallos.append(f"cobertura fina {cob_fina:.2f} < {cob_fina_min:g}")
    if max_std_px is not None:
        std = resultado.get("std_intrinsecos") or {}
        for nombre in PARAMETROS[:4]:
            if nombre not in std:
                fallos.append(f"sin desviacion de {nombre}")
            elif not std[nombre] <= max_std_px:
                fallos.append(f"desviacion de {nombre} {std[nombre]:.2f} px > {max_std_px:g}")
    return fallos


def parametros_intrinsecos(K, dist) -> dict:
    """fx, fy, cx, cy, k1, k2, p1, p2 y k3 de una K y su distorsion (los que falten en `dist`, 0)."""
    K = np.asarray(K, dtype=np.float64).reshape(3, 3)
    d = np.asarray(dist, dtype=np.float64).flatten()
    d = np.concatenate([d, np.zeros(max(0, 5 - len(d)))])[:5]
    return dict(zip(PARAMETROS, [float(K[0, 0]), float(K[1, 1]), float(K[0, 2]), float(K[1, 2])] + [float(x) for x in d]))


def comparar_intrinsecos(nuevo: dict, viejo: dict) -> dict:
    """Unos intrinsecos frente a otros: por parametro (`PARAMETROS`), `nuevo`, `viejo`, la diferencia
    `dif` (nuevo - viejo) y, si los dos traen su desviacion, `sd_combinada` (la raiz de la suma de
    cuadrados) y `sigmas` (dif / sd_combinada; 0 si no hay diferencia; None si las dos desviaciones
    son 0 y la hay). `nuevo` y `viejo`:
    `{"K", "dist", "std": {parametro: desviacion}}` (`std` puede faltar o venir a medias).
    Ademas `max_sigmas`: [parametro, sigmas] del que mas se aparta, o None si ninguno trae desviacion."""
    pn, pv = parametros_intrinsecos(nuevo["K"], nuevo["dist"]), parametros_intrinsecos(viejo["K"], viejo["dist"])
    sn, sv = nuevo.get("std") or {}, viejo.get("std") or {}
    out: dict = {"parametros": {}, "max_sigmas": None}
    for nombre in PARAMETROS:
        fila = {"nuevo": pn[nombre], "viejo": pv[nombre], "dif": pn[nombre] - pv[nombre],
                "sd_nuevo": sn.get(nombre), "sd_viejo": sv.get(nombre), "sd_combinada": None, "sigmas": None}
        if fila["sd_nuevo"] is not None and fila["sd_viejo"] is not None:
            comb = float(np.hypot(fila["sd_nuevo"], fila["sd_viejo"]))
            fila["sd_combinada"] = comb
            if fila["dif"] == 0:
                fila["sigmas"] = 0.0
            elif comb > 0:
                fila["sigmas"] = fila["dif"] / comb
            if fila["sigmas"] is not None and (out["max_sigmas"] is None or abs(fila["sigmas"]) > abs(out["max_sigmas"][1])):
                out["max_sigmas"] = [nombre, fila["sigmas"]]
        out["parametros"][nombre] = fila
    return out


def leer_intrinsecos_con_std(ruta) -> dict:
    """K, dist y las desviaciones que traiga el `.yml` (`std_intrinsecos`: fx, fy, cx, cy;
    `std_distorsion`: k1, k2, p1, p2, k3, desde la fase 7d), con la forma que pide `comparar_intrinsecos`."""
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"no se pudo abrir el .yml de intrinsecos: {ruta}")
    try:
        K, d = fs.getNode("camera_matrix").mat(), fs.getNode("distortion_coefficients").mat()
        if K is None or d is None or np.asarray(K).shape != (3, 3):
            raise ValueError(f"{Path(ruta).name}: sin camera_matrix o distortion_coefficients")
        std = {}
        for mapa in ("std_intrinsecos", "std_distorsion"):
            nodo = fs.getNode(mapa)
            if nodo.empty() or not nodo.isMap():
                continue
            for nombre in PARAMETROS:
                if not nodo.getNode(nombre).empty():
                    std[nombre] = float(nodo.getNode(nombre).real())
        return {"K": np.asarray(K, dtype=np.float64), "dist": np.asarray(d, dtype=np.float64).flatten(), "std": std}
    finally:
        fs.release()


def elegir_ganador(resultados: dict) -> str:
    """El detector que gana con --detector ambos.

    resultados: detector -> {"rms_control_px": float | None, "cumple": bool}. Gana el de menor
    RMS de control entre los que cumplen el criterio; si ninguno cumple, entre todos los que
    tienen RMS de control. Empate: el primero en DETECTORES. ValueError si ninguno tiene control.
    """
    con_control = [d for d, v in resultados.items() if v.get("rms_control_px") is not None]
    if not con_control:
        raise ValueError("ningun detector tiene RMS de control: no hay con que elegir")
    candidatos = [d for d in con_control if resultados[d].get("cumple")] or con_control
    orden = {d: i for i, d in enumerate(DETECTORES)}
    return min(candidatos, key=lambda d: (resultados[d]["rms_control_px"], orden.get(d, len(orden))))


# ----------------------------------------------------------------------------
# Esquinas y vistas
# ----------------------------------------------------------------------------

def detectar_esquinas(gray, cols: int, rows: int, metodo: str, rapido: bool = False):
    """Esquinas interiores (cols*rows, 1, 2) float32 o None. `rapido` solo para la vista previa
    (FAST_CHECK en el clasico; sin EXHAUSTIVE en sb)."""
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    if metodo == "clasico":
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        if rapido:
            flags |= cv2.CALIB_CB_FAST_CHECK
        ok, corners = cv2.findChessboardCorners(gray, (cols, rows), flags)
        if not ok or corners is None or len(corners) != cols * rows:
            return None
        return cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), CRITERIOS_SUBPIX)
    if metodo == "sb":
        flags = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_ACCURACY
        if not rapido:
            flags |= cv2.CALIB_CB_EXHAUSTIVE
        ok, corners = cv2.findChessboardCornersSB(gray, (cols, rows), flags)
        if not ok or corners is None or len(corners) != cols * rows:
            return None
        return np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2)
    raise ValueError(f"detector desconocido: {metodo!r} (validos: {DETECTORES})")


def listar_vistas(directorio) -> list[Path]:
    d = Path(directorio)
    if not d.is_dir():
        raise FileNotFoundError(f"no existe la carpeta de vistas: {d}")
    return sorted(p for p in d.iterdir() if p.suffix.lower() in EXT_VISTAS)


def cargar_vistas(directorio) -> list[np.ndarray]:
    """Las vistas guardadas, en gris y en orden de nombre; todas del mismo tamano (si no, ValueError)."""
    vistas = []
    for p in listar_vistas(directorio):
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if g is None:
            raise ValueError(f"no se pudo leer la vista {p}")
        vistas.append(g)
    if not vistas:
        raise ValueError(f"no hay vistas ({'/'.join(EXT_VISTAS)}) en {directorio}")
    tamanos = {v.shape[::-1] for v in vistas}
    if len(tamanos) != 1:
        raise ValueError(f"las vistas no son todas del mismo tamano: {sorted(tamanos)}")
    return vistas


def detectar_vistas(vistas: list[np.ndarray], cols: int, rows: int, metodo: str) -> tuple[list, list[int]]:
    """Esquinas de cada vista con el detector; devuelve (img_points, indices de las vistas detectadas)."""
    img_points, indices = [], []
    for i, g in enumerate(vistas):
        c = detectar_esquinas(g, cols, rows, metodo)
        if c is None:
            log_warn(f"vista {i + 1}: el detector {metodo} no encontro el tablero; se descarta")
            continue
        img_points.append(c)
        indices.append(i)
    return img_points, indices


def vistas_del_asistente(carpeta, camara: str, cols: int, rows: int, detector: str, n_frames: int, max_mov_px: float,
                         patron: str = "ajedrez", tablero=None, min_esquinas: int = 12) -> dict:
    """Las vistas de una camara en la carpeta del asistente (`capture_stereo_board --modo intrinsecos`).

    Por posicion (`calibrate_extrinsics.listar_posiciones(carpeta, (camara,))`, el ultimo intento),
    las esquinas medias de su rafaga y si vale: con `patron="ajedrez"`,
    `calibrate_extrinsics.esquinas_de_posicion` (`cols`, `rows`, `detector`); con `"charuco"`,
    `charuco_board.esquinas_charuco_de_posicion` sobre `tablero` (>= `min_esquinas` comunes a los
    frames) y `puntos_objeto`: listas de distinto largo por vista, que `calibrar` acepta.
    Devuelve `nombres`, `img_points`, `obj_points` (None con el ajedrez: los pone quien llama con el
    lado medido), `ids` (charuco), `shape` (w, h), `movimiento_px` y `apartadas` (nombre y motivo).
    Importa `calibrate_extrinsics` y `charuco_board` aqui dentro: los dos importan este modulo."""
    from calibration import calibrate_extrinsics as ce
    from calibration import charuco_board as chb
    if patron not in PATRONES:
        raise ValueError(f"patron desconocido: {patron!r} (validos: {PATRONES})")
    if patron == "charuco" and tablero is None:
        raise ValueError("con patron='charuco' hace falta el tablero (TableroCharuco)")
    posiciones = ce.listar_posiciones(carpeta, (camara,))
    if not posiciones:
        raise ValueError(f"no hay ninguna posicion de {camara} (<pos>_{camara}_frames) en {carpeta}")
    det = chb.detector(tablero) if patron == "charuco" else None
    out: dict = {"camara": camara, "patron": patron, "nombres": [], "img_points": [], "obj_points": [] if det is not None else None,
                 "ids": [], "movimiento_px": [], "apartadas": [], "shape": None}
    shapes = set()
    for nombre, info in posiciones.items():
        d = info["carpetas"][camara]
        if det is None:
            e = ce.esquinas_de_posicion(d, cols, rows, detector, n_frames, max_mov_px)
        else:
            e = chb.esquinas_charuco_de_posicion(d, tablero, det, n_frames, max_mov_px, min_esquinas)
        if e["shape"] is not None:
            shapes.add(tuple(e["shape"]))
        if e["esquinas"] is None:
            out["apartadas"].append({"nombre": nombre, "motivo": e["motivo"]})
            continue
        out["nombres"].append(nombre)
        out["img_points"].append(np.asarray(e["esquinas"], dtype=np.float32).reshape(-1, 1, 2))
        out["movimiento_px"].append(e["movimiento_px"])
        if det is not None:
            out["obj_points"].append(chb.puntos_objeto(tablero, e["ids"]))
            out["ids"].append([int(i) for i in e["ids"]])
    if len(shapes) > 1:
        raise ValueError(f"los frames de {camara} en {carpeta} no son todos del mismo tamano: {sorted(shapes)}")
    out["shape"] = shapes.pop() if shapes else None
    return out


def leer_captura_json(directorio) -> dict | None:
    p = Path(directorio) / ARCHIVO_CAPTURA
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def guardar_captura_json(directorio, info: dict) -> Path:
    p = Path(directorio) / ARCHIVO_CAPTURA
    p.write_text(json.dumps(info, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return p


# ----------------------------------------------------------------------------
# El .yml
# ----------------------------------------------------------------------------

def _escribir_nodo(fs, nombre: str, valor) -> None:
    """Escribe un escalar, un dict (mapa) o una lista (secuencia) en el FileStorage."""
    if isinstance(valor, dict):
        fs.startWriteStruct(nombre, cv2.FileNode_MAP)
        for k, v in valor.items():
            _escribir_nodo(fs, str(k), v)
        fs.endWriteStruct()
    elif isinstance(valor, (list, tuple, np.ndarray)):
        fs.startWriteStruct(nombre, cv2.FileNode_SEQ)
        for v in valor:
            _escribir_nodo(fs, "", v)
        fs.endWriteStruct()
    elif valor is None:
        fs.write(nombre, "")
    elif isinstance(valor, bool):
        fs.write(nombre, int(valor))
    elif isinstance(valor, (int, np.integer)):
        fs.write(nombre, int(valor))
    elif isinstance(valor, (float, np.floating)):
        fs.write(nombre, float(valor))
    else:
        fs.write(nombre, str(valor))


def guardar_yml(output_path, K, dist, width, height, rmse, n_vistas,
                cols, rows, square_mm, extra: dict | None = None):
    """Exporta el YAML OpenCV con las claves que leen los backends
    (WebcamBackend._load_calibration y el override del FemtoBoltBackend
    esperan `camera_matrix` + `distortion_coefficients`), image_width/height
    (los comprueba el backend) y, en `extra`, lo demas (detector, control,
    cobertura, desviaciones, perfil, puerto, modo, ajustes leidos, medidas)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fs = cv2.FileStorage(str(output_path), cv2.FILE_STORAGE_WRITE)
    fs.write("camera_matrix", np.asarray(K, dtype=np.float64))
    fs.write("distortion_coefficients",
             np.asarray(dist, dtype=np.float64).reshape(-1, 1))
    fs.write("image_width", int(width))
    fs.write("image_height", int(height))
    fs.write("rms_reprojection_px", float(rmse))
    fs.write("n_views", int(n_vistas))
    fs.write("board", f"{cols}x{rows} inner corners @ {square_mm} mm")
    fs.write("square_mm", float(square_mm))
    fs.write("generated_by", "calibration/calibrate_camera.py")
    fs.write("generated_at_utc", datetime.now(timezone.utc).isoformat())
    for k, v in (extra or {}).items():
        _escribir_nodo(fs, str(k), v)
    fs.release()
    # Verificacion de lectura (el formato que consumen los backends)
    fs = cv2.FileStorage(str(output_path), cv2.FILE_STORAGE_READ)
    K_chk = fs.getNode("camera_matrix").mat()
    d_chk = fs.getNode("distortion_coefficients").mat()
    w_chk = fs.getNode("image_width")
    fs.release()
    if K_chk is None or d_chk is None or K_chk.shape != (3, 3) or w_chk.empty():
        raise IOError(f"verificacion de lectura FALLO en {output_path}")


# ----------------------------------------------------------------------------
# Captura con la camara
# ----------------------------------------------------------------------------

def _dibujar_rejilla(disp, shape, cubiertas, celdas=CELDAS_COBERTURA) -> None:
    w, h = shape
    cx, cy = celdas
    for ix in range(cx):
        for iy in range(cy):
            x0, y0 = int(ix * w / cx), int(iy * h / cy)
            x1, y1 = int((ix + 1) * w / cx) - 1, int((iy + 1) * h / cy) - 1
            color = (0, 200, 0) if (ix, iy) in cubiertas else (0, 0, 180)
            cv2.rectangle(disp, (x0, y0), (x1, y1), color, 1)


def textos_ventana(fotos: int, minimo: int, zonas: int, total_zonas: int, visto: bool) -> tuple[str, str]:
    """Las dos lineas que se pintan sobre la imagen, en lenguaje llano (P21) y sin acentos:
    la fuente de cv2.putText (Hershey) pinta '??' en lugar de una letra con acento."""
    tablero = "Tablero: lo veo" if visto else "Tablero: NO lo veo"
    return (f"Fotos: {fotos} (minimo {minimo})  |  zonas cubiertas {zonas} de {total_zonas}  |  {tablero}",
            "ESPACIO = tomar foto   u = borrar la ultima   q = terminar y calcular")


def capturar_vistas(cam, cols: int, rows: int, metodo: str, limite: float, vistas_dir,
                    min_total: int, celdas=CELDAS_COBERTURA, leer_tecla=None) -> list[Path]:
    """Bucle con ventana hasta q o `limite` (time.monotonic). ESPACIO detecta con `metodo` y
    guarda el frame como PNG en vistas_dir; u quita la ultima. Devuelve las rutas guardadas.
    `leer_tecla()` se inyecta en las pruebas (por defecto cv2.waitKey(1) & 0xFF)."""
    vistas_dir = Path(vistas_dir)
    vistas_dir.mkdir(parents=True, exist_ok=True)
    leer_tecla = leer_tecla if leer_tecla is not None else (lambda: cv2.waitKey(1) & 0xFF)
    rutas: list[Path] = []
    esquinas: list[np.ndarray] = []
    shape = None
    ultima = 0.0
    cv2.namedWindow(TITULO_VENTANA, cv2.WINDOW_NORMAL)
    try:
        while time.monotonic() < limite:
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            shape = gray.shape[::-1]
            previa = detectar_esquinas(gray, cols, rows, "clasico", rapido=True)
            disp = frame.copy()
            if previa is not None:
                cv2.drawChessboardCorners(disp, (cols, rows), previa, True)
            cubiertas = celdas_cubiertas(esquinas, shape, celdas)
            _dibujar_rejilla(disp, shape, cubiertas, celdas)
            color = (0, 255, 0) if previa is not None else (0, 0, 255)
            linea1, linea2 = textos_ventana(len(rutas), min_total, len(cubiertas), celdas[0] * celdas[1],
                                            previa is not None)
            cv2.putText(disp, linea1, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(disp, linea2, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow(TITULO_VENTANA, disp)
            tecla = leer_tecla()
            if tecla == ord(" "):
                if time.monotonic() - ultima < ANTIRREBOTE_S:
                    continue
                ultima = time.monotonic()
                c = detectar_esquinas(gray, cols, rows, metodo)
                if c is None:
                    log_warn(f"el detector {metodo} no encontro el tablero en este frame: no se captura")
                    continue
                ruta = vistas_dir / f"vista_{len(rutas) + 1:02d}.png"
                if not cv2.imwrite(str(ruta), frame):
                    raise IOError(f"no se pudo guardar {ruta}")
                rutas.append(ruta)
                esquinas.append(c)
                log_info(f"vista {len(rutas)} capturada ({len(c)} esquinas) -> {ruta.name}; "
                         f"cobertura {cobertura(esquinas, shape, celdas):.2f}")
            elif tecla == ord("u") and rutas:
                r = rutas.pop()
                esquinas.pop()
                r.unlink(missing_ok=True)
                log_info(f"vista quitada: {r.name} (quedan {len(rutas)})")
            elif tecla == ord("q"):
                break
    finally:
        cv2.destroyAllWindows()
    return rutas


def abrir_sin_yml(cfg_camera: dict):
    """create_backend + open() con una copia del perfil sin calibration_file (se esta creando)."""
    c = dict(cfg_camera)
    c["calibration_file"] = None
    cam = create_backend(c)
    cam.open()
    return cam


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _parsear_medidas(texto: str) -> list[float]:
    try:
        return [float(t) for t in texto.split(",") if t.strip()]
    except ValueError:
        raise ValueError(f"--medidas-mm mal escrito: {texto!r} (forma: 99.90,99.85,...)")


def _modo_del_perfil(cam: dict) -> dict:
    return {"width": int(cam.get("width", 0)), "height": int(cam.get("height", 0)),
            "fps": cam.get("fps"), "fourcc": cam.get("fourcc"), "backend": cam.get("backend")}


def _calibrar_con(detector: str, vistas: list, shape, args, criterio: dict, registro: dict,
                  etiqueta: str = "") -> dict:
    """Detecta las esquinas de las vistas con `detector`, calibra y mide el criterio, con su log.

    Deja registro["vistas"] (total, detectadas, indices) antes de calibrar (para el reporte aunque
    falle). Devuelve {"r": calibrar(...), "cob", "fallos", "vistas", "indices"}. `etiqueta` antepone
    el detector a cada linea del log con --detector ambos (vacia: el log de siempre)."""
    img_points, indices = detectar_vistas(vistas, args.cols, args.rows, detector)
    registro["vistas"] = {"total": len(vistas), "detectadas": len(img_points), "indices_detectados": indices}
    log_stats(f"{etiqueta}Vistas: {len(vistas)} guardadas, {len(img_points)} con tablero ({detector})")
    if len(img_points) < args.min_vistas + args.n_control:
        raise ValueError(f"hacen falta {args.min_vistas + args.n_control} vistas con tablero "
                         f"({args.min_vistas} de ajuste + {args.n_control} de control) y hay {len(img_points)}: "
                         f"recapturar (bordes, esquinas, inclinaciones)")
    objp = construir_objp(args.cols, args.rows, args.square_mm)
    obj_points = [objp.copy() for _ in img_points]

    log_info(f"{etiqueta}Calibrando (cv2.calibrateCameraExtended)...")
    t0 = time.monotonic()
    r = calibrar(obj_points, img_points, shape, args.n_control, args.semilla)
    cob = cobertura([img_points[i] for i in r["indices_fit"]], shape)
    cob_fina = None if args.cobertura_fina_min is None else cobertura([img_points[i] for i in r["indices_fit"]], shape,
                                                                      tuple(args.celdas_finas))
    fallos = evaluar_criterio(r, cob, criterio, cob_fina=cob_fina, cob_fina_min=args.cobertura_fina_min,
                              max_std_px=args.max_std_px)
    if cob_fina is not None:
        log_stats(f"{etiqueta}Cobertura fina {cob_fina:.2f} de {args.celdas_finas[0]}x{args.celdas_finas[1]} celdas "
                  f"(criterio >= {args.cobertura_fina_min:g})")
    fx, fy, cx, cy = r["K"][0, 0], r["K"][1, 1], r["K"][0, 2], r["K"][1, 2]
    log_stats(f"{etiqueta}RMS de reproyeccion: {r['rms_px']:.4f} px con {r['n_vistas_usadas']} vistas "
              f"(criterio <= {criterio['rms_px']} px; referencia historica 0.479 px) en {time.monotonic() - t0:.1f} s")
    rc_txt = "-" if r["rms_control_px"] is None else f"{r['rms_control_px']:.4f}"
    log_stats(f"{etiqueta}RMS de control ({r['n_control']} vistas fuera del ajuste): {rc_txt} px "
              f"(criterio <= {criterio['rms_control_px']}); por vista "
              f"{[round(e, 3) for e in r['errores_control_px']]}")
    log_stats(f"{etiqueta}Cobertura {cob:.2f} de {CELDAS_COBERTURA[0]}x{CELDAS_COBERTURA[1]} celdas "
              f"(criterio >= {criterio['cobertura']})")
    log_stats(f"{etiqueta}fx {fx:.2f} +- {r['std_intrinsecos']['fx']:.2f} | fy {fy:.2f} +- {r['std_intrinsecos']['fy']:.2f} | "
              f"cx {cx:.2f} +- {r['std_intrinsecos']['cx']:.2f} | cy {cy:.2f} +- {r['std_intrinsecos']['cy']:.2f}")
    log_stats(f"{etiqueta}dist = {np.round(r['dist'], 5).tolist()}")
    log_stats(f"{etiqueta}error por vista (ajuste): {[round(e, 3) for e in r['errores_vista_px']]}")
    peores = sorted(zip(r["errores_vista_px"], r["indices_fit"]), reverse=True)[:3]
    log_stats(f"{etiqueta}peores vistas: {[(indices[i] + 1, round(e, 3)) for e, i in peores]} (numero de archivo, px)")
    return {"r": r, "cob": cob, "fallos": fallos, "vistas": registro["vistas"], "indices": indices}


def _resultado_json(corrida: dict, shape) -> dict:
    """Lo que va al reporte de una calibracion (la de _calibrar_con)."""
    r, cob, fallos = corrida["r"], corrida["cob"], corrida["fallos"]
    return {
        "K": r["K"].tolist(), "dist": r["dist"].tolist(), "rms_px": r["rms_px"],
        "rms_control_px": r["rms_control_px"], "errores_control_px": r["errores_control_px"],
        "errores_vista_px": r["errores_vista_px"], "indices_fit": r["indices_fit"],
        "indices_control": r["indices_control"], "std_intrinsecos": r["std_intrinsecos"],
        "n_vistas_usadas": r["n_vistas_usadas"], "cobertura": cob, "shape": list(shape),
        "fallos": fallos, "cumple": not fallos,
    }


def _calibrar_desde_asistente(args, cam_cfg: dict, modo: dict, estado: dict, tablero, medidas) -> int:
    """--desde-asistente: calibra con la carpeta de `capture_stereo_board --modo intrinsecos`, mide el
    criterio (con los opcionales de P52), compara con --comparar-con y escribe el .yml y lo del reporte.
    Devuelve el codigo: 0 cumple, 1 no. ValueError o RuntimeError si no puede calibrar."""
    from calibration import charuco_board as chb
    carpeta = Path(args.desde_asistente)
    charuco = tablero is not None
    criterio = estado["criterio"]
    log_info(f"Sin camara: vistas del asistente en {carpeta} (camara {args.camara}, patron {args.patron})")
    v = vistas_del_asistente(carpeta, args.camara, args.cols, args.rows, args.detector, args.frames_por_vista,
                             args.max_movimiento_px, args.patron, tablero, args.min_esquinas)
    n = len(v["img_points"])
    por_vista = [int(len(x)) for x in v["img_points"]]
    estado["vistas_dir"] = str(carpeta)
    estado["vistas"] = {"total": n + len(v["apartadas"]), "detectadas": n, "nombres": v["nombres"],
                        "apartadas": v["apartadas"], "esquinas_por_vista": por_vista}
    for a in v["apartadas"]:
        log_warn(f"{a['nombre']}: apartada ({a['motivo']})")
    log_stats(f"Vistas: {n + len(v['apartadas'])} posiciones, {n} usables"
              + (f"; esquinas por vista de {min(por_vista)} a {max(por_vista)} (mediana {statistics.median(por_vista):g})" if por_vista else ""))
    if v["shape"] is None:
        raise ValueError(f"ninguna posicion de {args.camara} en {carpeta} tiene frames")
    shape = tuple(v["shape"])
    if (modo["width"], modo["height"]) != shape:
        raise ValueError(f"las vistas son de {shape[0]}x{shape[1]} y el perfil pide {modo['width']}x{modo['height']}: "
                         f"el .yml no valdria para este perfil")
    if n < args.min_vistas + args.n_control:
        raise ValueError(f"hacen falta {args.min_vistas + args.n_control} vistas usables ({args.min_vistas} de ajuste + "
                         f"{args.n_control} de control) y hay {n}: repetir la sesion del asistente")
    obj_points = v["obj_points"] if charuco else [construir_objp(args.cols, args.rows, args.square_mm).copy() for _ in range(n)]
    log_info("Calibrando (cv2.calibrateCameraExtended)...")
    t0 = time.monotonic()
    try:
        r = calibrar(obj_points, v["img_points"], shape, args.n_control, args.semilla)
    except cv2.error as e:
        raise RuntimeError(f"calibrateCameraExtended fallo: {e}")
    fit = [v["img_points"][i] for i in r["indices_fit"]]
    celdas = tuple(args.celdas_finas)
    cob, cob_fina = cobertura(fit, shape), cobertura(fit, shape, celdas)
    fallos = evaluar_criterio(r, cob, criterio, cob_fina=cob_fina, cob_fina_min=args.cobertura_fina_min,
                              max_std_px=args.max_std_px)
    fx, fy, cx, cy = r["K"][0, 0], r["K"][1, 1], r["K"][0, 2], r["K"][1, 2]
    sd = r["std_intrinsecos"]
    log_stats(f"RMS de reproyeccion: {r['rms_px']:.4f} px con {r['n_vistas_usadas']} vistas (criterio <= {criterio['rms_px']} px) "
              f"en {time.monotonic() - t0:.1f} s")
    rc_txt = "-" if r["rms_control_px"] is None else f"{r['rms_control_px']:.4f}"
    log_stats(f"RMS de control ({r['n_control']} vistas fuera del ajuste): {rc_txt} px (criterio <= {criterio['rms_control_px']})")
    log_stats(f"Cobertura {cob:.2f} de {CELDAS_COBERTURA[0]}x{CELDAS_COBERTURA[1]} celdas (criterio >= {criterio['cobertura']}); "
              f"fina {cob_fina:.2f} de {celdas[0]}x{celdas[1]}"
              + ("" if args.cobertura_fina_min is None else f" (criterio >= {args.cobertura_fina_min:g})"))
    log_stats(f"fx {fx:.2f} +- {sd['fx']:.2f} | fy {fy:.2f} +- {sd['fy']:.2f} | cx {cx:.2f} +- {sd['cx']:.2f} | cy {cy:.2f} +- {sd['cy']:.2f}"
              + ("" if args.max_std_px is None else f" (criterio: desviacion <= {args.max_std_px:g} px)"))
    log_stats(f"dist = {np.round(r['dist'], 5).tolist()}")
    peores = sorted(zip(r["errores_vista_px"], r["indices_fit"]), reverse=True)[:3]
    log_stats(f"peores vistas: {[(v['nombres'][i], round(e, 3)) for e, i in peores]} (posicion, px)")
    comparacion = None
    if args.comparar_con:
        comparacion = comparar_intrinsecos({"K": r["K"], "dist": r["dist"], "std": {**sd, **r["std_distorsion"]}},
                                           leer_intrinsecos_con_std(args.comparar_con))
        for nombre in PARAMETROS[:4]:
            f = comparacion["parametros"][nombre]
            sig = "sin desviacion en uno de los dos" if f["sigmas"] is None else f"{f['sigmas']:+.1f} sigmas combinadas"
            log_stats(f"frente a {Path(args.comparar_con).name}, {nombre}: {f['viejo']:.2f} -> {f['nuevo']:.2f} ({f['dif']:+.2f} px; {sig})")
    extra = {
        "detector": "charuco" if charuco else args.detector, "patron": args.patron,
        "rms_control_px": r["rms_control_px"], "n_control": r["n_control"],
        "errores_control_px": r["errores_control_px"], "errores_vista_px": r["errores_vista_px"],
        "cobertura": round(cob, 4), "cobertura_celdas": f"{CELDAS_COBERTURA[0]}x{CELDAS_COBERTURA[1]}",
        "cobertura_fina": round(cob_fina, 4), "cobertura_fina_celdas": f"{celdas[0]}x{celdas[1]}",
        "std_intrinsecos": sd, "std_distorsion": r["std_distorsion"],
        "square_mm_medido": args.square_mm, "medidas_calibrador_mm": medidas or [],
        "casillas_por_medida": args.casillas_por_medida,
        "perfil": Path(args.config).name, "usb_port_windows": cam_cfg.get("usb_port_windows") or "",
        "modo": modo, "ajustes_declarados": cam_cfg.get("controls") or {},
        "luz": args.luz or "", "vistas_dir": str(carpeta), "desde_asistente": True, "camara": args.camara,
        "posiciones_ajuste": [v["nombres"][i] for i in r["indices_fit"]],
        "posiciones_control": [v["nombres"][i] for i in r["indices_control"]],
        "frames_por_vista": args.frames_por_vista, "max_movimiento_px": args.max_movimiento_px,
        "criterio": criterio, "criterio_cumplido": not fallos, "criterio_fallos": fallos, "opencv": cv2.__version__,
    }
    if charuco:
        extra["tablero_charuco"] = chb.describir_tablero(args.tablero_charuco)
        extra["min_esquinas"] = args.min_esquinas
    guardar_yml(args.output, r["K"], r["dist"], shape[0], shape[1], r["rms_px"], r["n_vistas_usadas"],
                args.cols, args.rows, args.square_mm, extra)
    estado["resultado"] = dict(_resultado_json({"r": r, "cob": cob, "fallos": fallos}, shape), detector=extra["detector"],
                               output=str(args.output), cobertura_fina=cob_fina, celdas_finas=list(celdas),
                               std_distorsion=r["std_distorsion"], posiciones_ajuste=extra["posiciones_ajuste"],
                               posiciones_control=extra["posiciones_control"], comparacion=comparacion)
    log_info(f"Guardado y verificado: {args.output}")
    if fallos:
        log_warn("Criterio NO cumplido: " + "; ".join(fallos) + ". El .yml queda guardado con el veredicto dentro; "
                 "no apuntar el perfil a el.")
        return 1
    log_info("Criterio cumplido (RMS, control, coberturas, desviaciones y vistas).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Calibracion intrinseca con tablero (OpenCV), por el perfil de la camara.")
    ap.add_argument("--config", required=True, help="perfil de la camara (tracker_config_gs1.yaml o gs2)")
    ap.add_argument("--output", required=True, help="ruta del .yml de salida (obligatoria, sin default-trampa)")
    ap.add_argument("--square-mm", type=float, default=None,
                    help="lado de la casilla MEDIDO con calibrador (media de >= 5 medidas / casillas por medida); obligatorio con el ajedrez")
    ap.add_argument("--medidas-mm", help="las medidas del calibrador en mm, 'a,b,c,d,e' (se comprueban contra --square-mm)")
    ap.add_argument("--casillas-por-medida", type=int, default=4, help="casillas que abarca cada medida")
    ap.add_argument("--cols", type=int, default=None, help="esquinas interiores horizontales (9x6 casillas = 8, el valor por defecto con el ajedrez)")
    ap.add_argument("--rows", type=int, default=None, help="esquinas interiores verticales (9x6 casillas = 5, el valor por defecto con el ajedrez)")
    ap.add_argument("--detector", choices=MODOS_DETECTOR, default=None,
                    help="clasico (findChessboardCorners+cornerSubPix), sb, o ambos (gana el de menor RMS de control); obligatorio con el ajedrez")
    ap.add_argument("--patron", choices=PATRONES, default="ajedrez", help="ajedrez (el de siempre) o charuco (solo con --desde-asistente)")
    ap.add_argument("--tablero-charuco", help="con --patron charuco: data\\tablero_charuco.yaml (o el tablero.json nominal)")
    ap.add_argument("--min-esquinas", type=int, default=12, help="charuco: esquinas minimas (comunes a los frames) para que una vista valga")
    ap.add_argument("--desde-asistente", help="sin camara: calibra con la carpeta del asistente (capture_stereo_board --modo intrinsecos)")
    ap.add_argument("--camara", help="con --desde-asistente: la camara de esa carpeta (gs1 o gs2)")
    ap.add_argument("--frames-por-vista", type=int, default=5, help="con --desde-asistente: frames de cada rafaga que se promedian")
    ap.add_argument("--max-movimiento-px", type=float, default=0.3, help="con --desde-asistente: tope del movimiento de las esquinas en la rafaga")
    ap.add_argument("--celdas-finas", type=int, nargs=2, default=list(CELDAS_FINAS), metavar=("COLS", "FILAS"),
                    help="la rejilla fina de cobertura (8 6)")
    ap.add_argument("--cobertura-fina-min", type=float, default=None, help="criterio opcional (P52): cobertura minima de la rejilla fina (0.85)")
    ap.add_argument("--max-std-px", type=float, default=None, help="criterio opcional (P52): desviacion maxima de fx, fy, cx y cy (1.0)")
    ap.add_argument("--comparar-con", help="otro .yml de intrinsecos: la diferencia por parametro y en sigmas combinadas")
    ap.add_argument("--vistas-dir", help="carpeta donde se guardan las vistas capturadas (obligatoria con camara)")
    ap.add_argument("--desde-vistas", help="sin camara: recalibra con las vistas de esta carpeta")
    ap.add_argument("--min-vistas", type=int, default=CRITERIO["min_vistas"], help="vistas minimas en el ajuste (sin contar las de control)")
    ap.add_argument("--n-control", type=int, default=3, help="vistas apartadas para el RMS de control")
    ap.add_argument("--semilla", type=int, default=0, help="semilla de la eleccion de las vistas de control")
    ap.add_argument("--luz", help="nivel de la caja de luz y luz de la sala (P7)")
    ap.add_argument("--reporte", help="JSON con el detalle (errores por vista, control, cobertura, criterio)")
    ap.add_argument("--timeout", type=float, required=True,
                    help=f"tope de la captura en segundos (la calibracion tiene {MARGEN_CALIBRAR_S:.0f} s mas)")
    args = ap.parse_args(argv)

    charuco = args.patron == "charuco"
    if charuco:
        if args.desde_asistente is None:
            ap.error("--patron charuco va con --desde-asistente (la captura con ESPACIO es del tablero de ajedrez)")
        if not args.tablero_charuco:
            ap.error("con --patron charuco hace falta --tablero-charuco <yaml o json>")
        if args.cols is not None or args.rows is not None or args.square_mm is not None or args.detector is not None:
            ap.error("con --patron charuco sobran --cols, --rows, --square-mm y --detector: los da --tablero-charuco")
        if args.medidas_mm:
            ap.error("--medidas-mm es del tablero de ajedrez: las del ChArUco van en su archivo (charuco_board registrar)")
    else:
        if args.tablero_charuco:
            ap.error("--tablero-charuco va con --patron charuco")
        if args.square_mm is None:
            ap.error("hace falta --square-mm (el lado MEDIDO de la casilla)")
        if args.detector is None:
            ap.error("hace falta --detector (clasico, sb o ambos)")
        args.cols = 8 if args.cols is None else args.cols
        args.rows = 5 if args.rows is None else args.rows
        if args.square_mm <= 0:
            ap.error(f"--square-mm tiene que ser positivo, no {args.square_mm}")
    if args.desde_asistente is not None:
        if not args.camara:
            ap.error("con --desde-asistente hace falta --camara (gs1 o gs2)")
        if args.desde_vistas is not None or args.vistas_dir:
            ap.error("--desde-asistente excluye a --desde-vistas y a --vistas-dir")
        if args.detector == "ambos":
            ap.error("con --desde-asistente, --detector clasico o sb (no ambos)")
    elif args.camara:
        ap.error("--camara va con --desde-asistente")
    if args.frames_por_vista < 1 or args.max_movimiento_px <= 0 or args.min_esquinas < 4 or min(args.celdas_finas) < 1:
        ap.error("--frames-por-vista >= 1; --max-movimiento-px > 0; --min-esquinas >= 4; --celdas-finas >= 1")
    if args.cobertura_fina_min is not None and not 0 < args.cobertura_fina_min <= 1:
        ap.error("--cobertura-fina-min entre 0 y 1")
    if args.max_std_px is not None and not args.max_std_px > 0:
        ap.error("--max-std-px > 0")
    if args.desde_asistente is None and args.desde_vistas is None and not args.vistas_dir:
        ap.error("con camara hace falta --vistas-dir (las vistas se guardan para recalibrar con --desde-vistas)")
    if args.n_control < 0 or args.min_vistas < 2:
        ap.error("--n-control >= 0 y --min-vistas >= 2")
    if args.detector == "ambos" and args.n_control < 1:
        ap.error("--detector ambos elige por el RMS de control: hace falta --n-control >= 1")
    medidas = None
    if args.medidas_mm:
        try:
            medidas = _parsear_medidas(args.medidas_mm)
            comprobar_lado(args.square_mm, medidas, args.casillas_por_medida)
        except ValueError as e:
            ap.error(str(e))

    tablero = None
    if charuco:                                         # el tablero da las esquinas y la casilla (medida)
        from calibration import charuco_board as chb
        try:
            tablero = chb.leer_tablero_charuco(args.tablero_charuco)
            if args.min_esquinas > tablero.esquinas_interiores:
                raise ValueError(f"--min-esquinas {args.min_esquinas} y el tablero tiene {tablero.esquinas_interiores} esquinas")
            if args.comparar_con and not Path(args.comparar_con).is_file():
                raise FileNotFoundError(f"no existe el .yml de --comparar-con: {args.comparar_con}")
        except (OSError, ValueError) as e:
            log_error(str(e))
            return 2
        args.cols, args.rows, args.square_mm = tablero.casillas[0] - 1, tablero.casillas[1] - 1, tablero.casilla_mm
        args.detector = "charuco"
    cfg = profiles.load(args.config, missing_ok=True)   # el .yml del perfil se esta creando: no tiene que existir
    cam_cfg = cfg["camera"]
    modo = _modo_del_perfil(cam_cfg)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv,
                    "opencv": cv2.__version__, "perfil": args.config, "puerto": cam_cfg.get("usb_port_windows"),
                    "modo": modo, "detector": args.detector, "square_mm": args.square_mm,
                    "medidas_calibrador_mm": medidas, "casillas_por_medida": args.casillas_por_medida,
                    "luz": args.luz, "criterio": dict(CRITERIO, min_vistas=args.min_vistas)}
    estado["patron"] = args.patron
    if args.cobertura_fina_min is not None:
        estado["criterio"].update(cobertura_fina=args.cobertura_fina_min, celdas_finas=f"{args.celdas_finas[0]}x{args.celdas_finas[1]}")
    if args.max_std_px is not None:
        estado["criterio"]["max_std_px"] = args.max_std_px
    if tablero is not None:
        estado["tablero_charuco"] = chb.describir_tablero(args.tablero_charuco)
    reporte = Path(args.reporte) if args.reporte else None
    log_info(f"Config: {args.config} (camera_type={cam_cfg.get('camera_type')}; modo "
             f"{modo['width']}x{modo['height']} {modo['fourcc']} @ {modo['fps']} {modo['backend']})")
    if tablero is not None:
        d_t = estado["tablero_charuco"]
        log_info(f"Tablero ChArUco: {tablero.casillas[0]}x{tablero.casillas[1]} casillas de {tablero.casilla_mm:g} mm "
                 f"({'medida' if d_t['medido'] else 'NOMINAL, sin medir'}), marcadores de {tablero.marcador_mm:g} mm, "
                 f"{tablero.diccionario}; {d_t['archivo']}")
    else:
        log_info(f"Tablero: {args.cols}x{args.rows} esquinas interiores @ {args.square_mm} mm (medido con calibrador"
                 f"{'' if medidas is None else f': {medidas} / {args.casillas_por_medida}'})")
    ambos = args.detector == "ambos"
    detector_captura = DETECTOR_CAPTURA_AMBOS if ambos else args.detector
    if ambos:
        log_info(f"Detector: ambos (captura con {detector_captura}; se calibra con {' y '.join(DETECTORES)} sobre las "
                 f"mismas vistas y gana el de menor RMS de control) | control: {args.n_control} vistas "
                 f"(semilla {args.semilla}) | salida: {args.output}")
    else:
        log_info(f"Detector: {args.detector} | control: {args.n_control} vistas (semilla {args.semilla}) | salida: {args.output}")

    vig = _vigilante(args.timeout + MARGEN_CALIBRAR_S, estado, reporte)
    rc = 0
    try:
        if args.desde_asistente is not None:
            return _calibrar_desde_asistente(args, cam_cfg, modo, estado, tablero, medidas)
        if args.desde_vistas:
            vistas_dir = Path(args.desde_vistas)
            captura = leer_captura_json(vistas_dir)
            log_info(f"Sin camara: vistas de {vistas_dir}" + ("" if captura else " (sin captura.json: el .yml lleva los ajustes del perfil, no leidos)"))
        else:
            vistas_dir = Path(args.vistas_dir)
            if not cam_cfg.get("usb_port_windows"):
                log_warn("el perfil no trae usb_port_windows: se abre por source (sin identidad ni ajustes)")
            cam = abrir_sin_yml(cam_cfg)
            try:
                tamano_real = getattr(cam, "tamano_real", None)
                ajustes = getattr(cam, "ajustes_leidos", None)
                log_info("ESPACIO = capturar vista (bordes y esquinas de la imagen, inclinaciones hasta ~45 grados, "
                         "40-80 cm) | u = quitar la ultima | q = calibrar y guardar")
                rutas = capturar_vistas(cam, args.cols, args.rows, detector_captura, time.monotonic() + args.timeout,
                                        vistas_dir, args.min_vistas + args.n_control)
            finally:
                cam.close()
            captura = {"fecha": estado["fecha"], "perfil": args.config, "puerto": cam_cfg.get("usb_port_windows"),
                       "modo": modo, "tamano_real": list(tamano_real) if tamano_real else None,
                       "ajustes_leidos": ajustes, "luz": args.luz, "n_vistas": len(rutas),
                       "detector_captura": detector_captura, "square_mm": args.square_mm,
                       "medidas_calibrador_mm": medidas, "opencv": cv2.__version__}
            guardar_captura_json(vistas_dir, captura)
            log_info(f"{len(rutas)} vistas guardadas en {vistas_dir} (+ {ARCHIVO_CAPTURA})")
        estado["vistas_dir"] = str(vistas_dir)
        estado["captura"] = captura

        vistas = cargar_vistas(vistas_dir)
        shape = vistas[0].shape[::-1]
        if (modo["width"], modo["height"]) != tuple(shape):
            raise ValueError(f"las vistas son de {shape[0]}x{shape[1]} y el perfil pide {modo['width']}x{modo['height']}: "
                             f"el .yml no valdria para este perfil")
        if ambos:
            corridas: dict = {}
            for det in DETECTORES:
                registro: dict = {}
                try:
                    corridas[det] = _calibrar_con(det, vistas, shape, args, estado["criterio"], registro,
                                                  etiqueta=f"[{det}] ")
                except (RuntimeError, ValueError, cv2.error) as e:
                    log_warn(f"[{det}] no calibra: {e}; queda fuera de la comparacion")
                    corridas[det] = {"error": str(e), "vistas": registro.get("vistas")}
            comparables = {d: {"rms_control_px": c["r"]["rms_control_px"], "cumple": not c["fallos"]}
                           for d, c in corridas.items() if "r" in c}
            if not comparables:
                raise ValueError("ningun detector pudo calibrar: " +
                                 "; ".join(f"{d}: {c['error']}" for d, c in corridas.items()))
            ganador = elegir_ganador(comparables)
            estado["detectores"] = {d: ({"error": c["error"], "vistas": c["vistas"]} if "error" in c else
                                        dict(_resultado_json(c, shape), vistas=c["vistas"]))
                                    for d, c in corridas.items()}
            estado["ganador"] = ganador
            textos = [f"{d} {c['r']['rms_control_px']:.4f} px" + ("" if not c["fallos"] else " (no cumple)")
                      if "r" in c else f"{d} sin resultado" for d, c in corridas.items()]
            log_stats(f"Detectores, RMS de control: {', '.join(textos)} -> gana {ganador}")
            detectadas = {d: tuple(c["vistas"]["indices_detectados"]) for d, c in corridas.items() if "r" in c}
            if len(set(detectadas.values())) > 1:
                log_warn("los detectores no encontraron el tablero en las mismas vistas: las vistas de control "
                         "pueden no ser las mismas imagenes (ver 'detectores' en el reporte)")
            log_info(f"Detector ganador: {ganador} (solo el se escribe en {args.output})")
        else:
            ganador = args.detector
            corridas = {ganador: _calibrar_con(ganador, vistas, shape, args, estado["criterio"], estado)}
        c = corridas[ganador]
        r, cob, fallos = c["r"], c["cob"], c["fallos"]
        estado["vistas"] = c["vistas"]

        extra = {
            "detector": ganador, "rms_control_px": r["rms_control_px"], "n_control": r["n_control"],
            "errores_control_px": r["errores_control_px"], "errores_vista_px": r["errores_vista_px"],
            "cobertura": round(cob, 4), "cobertura_celdas": f"{CELDAS_COBERTURA[0]}x{CELDAS_COBERTURA[1]}",
            "std_intrinsecos": r["std_intrinsecos"], "std_distorsion": r["std_distorsion"],
            "square_mm_medido": args.square_mm, "medidas_calibrador_mm": medidas or [],
            "casillas_por_medida": args.casillas_por_medida,
            "perfil": Path(args.config).name, "usb_port_windows": cam_cfg.get("usb_port_windows") or "",
            "modo": modo, "ajustes_leidos": (captura or {}).get("ajustes_leidos") or {},
            "ajustes_declarados": cam_cfg.get("controls") or {},
            "luz": args.luz or "", "vistas_dir": str(vistas_dir), "fecha_captura": (captura or {}).get("fecha") or "",
            "criterio": estado["criterio"], "criterio_cumplido": not fallos,
            "criterio_fallos": fallos, "opencv": cv2.__version__,
        }
        if ambos:
            extra["detector_captura"] = detector_captura
            extra["detector_comparacion"] = {d: ("" if "r" not in cc_ else cc_["r"]["rms_control_px"])
                                             for d, cc_ in corridas.items()}
        guardar_yml(args.output, r["K"], r["dist"], shape[0], shape[1], r["rms_px"], r["n_vistas_usadas"],
                    args.cols, args.rows, args.square_mm, extra)
        estado["resultado"] = dict(_resultado_json(c, shape), detector=ganador, output=str(args.output))
        log_info(f"Guardado y verificado: {args.output}")
        if fallos:
            log_warn("Criterio de la fase 4 NO cumplido: " + "; ".join(fallos) + ". El .yml queda guardado con el "
                     "veredicto dentro; recapturar o recalibrar antes de apuntar el perfil.")
            rc = 1
        else:
            log_info("Criterio de la fase 4 cumplido (RMS, control, cobertura y vistas).")
        log_info("Para usarlo: apuntar camera.calibration_file del perfil a este archivo "
                 "(el panel lo hace con backup, ADR-018).")
    except (RuntimeError, ValueError, OSError) as e:
        estado["error"] = str(e)
        log_error(str(e))
        rc = 1
    finally:
        vig.cancel()
        if reporte is not None:
            reporte.parent.mkdir(parents=True, exist_ok=True)
            reporte.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            log_info(f"Reporte: {reporte}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
