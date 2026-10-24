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
        "n_vistas_usadas": len(idx_fit), "n_control": len(idx_control),
        "rvecs": [np.asarray(r).flatten() for r in rvecs], "tvecs": [np.asarray(t).flatten() for t in tvecs],
    }


def evaluar_criterio(resultado: dict, cob: float, criterio: dict = CRITERIO) -> list[str]:
    """Lo que no cumple el criterio de la fase 4 (vacia = cumple)."""
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
    return fallos


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
    fallos = evaluar_criterio(r, cob, criterio)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Calibracion intrinseca con tablero (OpenCV), por el perfil de la camara.")
    ap.add_argument("--config", required=True, help="perfil de la camara (tracker_config_gs1.yaml o gs2)")
    ap.add_argument("--output", required=True, help="ruta del .yml de salida (obligatoria, sin default-trampa)")
    ap.add_argument("--square-mm", type=float, required=True,
                    help="lado de la casilla MEDIDO con calibrador (media de >= 5 medidas / casillas por medida)")
    ap.add_argument("--medidas-mm", help="las medidas del calibrador en mm, 'a,b,c,d,e' (se comprueban contra --square-mm)")
    ap.add_argument("--casillas-por-medida", type=int, default=4, help="casillas que abarca cada medida")
    ap.add_argument("--cols", type=int, default=8, help="esquinas interiores horizontales (9x6 casillas = 8)")
    ap.add_argument("--rows", type=int, default=5, help="esquinas interiores verticales (9x6 casillas = 5)")
    ap.add_argument("--detector", choices=MODOS_DETECTOR, required=True,
                    help="clasico (findChessboardCorners+cornerSubPix), sb, o ambos (gana el de menor RMS de control)")
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

    if args.square_mm <= 0:
        ap.error(f"--square-mm tiene que ser positivo, no {args.square_mm}")
    if args.desde_vistas is None and not args.vistas_dir:
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

    cfg = profiles.load(args.config, missing_ok=True)   # el .yml del perfil se esta creando: no tiene que existir
    cam_cfg = cfg["camera"]
    modo = _modo_del_perfil(cam_cfg)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv,
                    "opencv": cv2.__version__, "perfil": args.config, "puerto": cam_cfg.get("usb_port_windows"),
                    "modo": modo, "detector": args.detector, "square_mm": args.square_mm,
                    "medidas_calibrador_mm": medidas, "casillas_por_medida": args.casillas_por_medida,
                    "luz": args.luz, "criterio": dict(CRITERIO, min_vistas=args.min_vistas)}
    reporte = Path(args.reporte) if args.reporte else None
    log_info(f"Config: {args.config} (camera_type={cam_cfg.get('camera_type')}; modo "
             f"{modo['width']}x{modo['height']} {modo['fourcc']} @ {modo['fps']} {modo['backend']})")
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
            "std_intrinsecos": r["std_intrinsecos"],
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
