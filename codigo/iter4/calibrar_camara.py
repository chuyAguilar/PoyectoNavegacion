# -*- coding: utf-8 -*-
"""
Calibracion intrinseca de camara con tablero de ajedrez — iter 4 (brief-02 M3b).

Alternativa con OpenCV puro a MRPT camera-calib (codigo/readme.md §8, que ya
la contempla). Tablero del proyecto: data/recursos/calibration_pattern_9x6_25mm.pdf
-> 9x6 casillas = esquinas interiores 8x5, celda 25 mm, impreso al 100% sobre
superficie plana y rigida.

Captura vistas del tablero (variar posicion, inclinacion y distancia), corre
cv2.calibrateCamera y exporta el YAML OpenCV con las claves que leen los
backends (`camera_matrix`, `distortion_coefficients`).

Criterio (readme §8): RMSE de reproyeccion < 1 px (referencia historica
0.479 px). Si sale mayor se guarda igual PERO con advertencia fuerte:
descartar vistas malas y recapturar.

Uso (desde codigo\):
    python iter4\calibrar_camara.py --config iter4\tracker_config_doctor.yaml \
        --output iter4\data\camera_calibration_nueva.yml
Teclas:  ESPACIO = capturar vista (15-30 recomendadas)  |  q = calibrar y guardar
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from camera_backend import create_backend
from captura_calibracion import cargar_config

TITULO_VENTANA = "Calibracion camara iter4 - ESPACIO captura, q calibra"


def log_info(m): print(f"[INFO] {m}", flush=True)
def log_warn(m): print(f"[WARN] {m}", flush=True)
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr, flush=True)
def log_stats(m): print(f"[STATS] {m}", flush=True)


def construir_objp(cols, rows, square_mm):
    """Puntos 3D del tablero (z=0), en mm."""
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_mm
    return objp


def guardar_yml(output_path, K, dist, width, height, rmse, n_vistas,
                cols, rows, square_mm):
    """Exporta el YAML OpenCV con las claves que leen los backends
    (WebcamBackend._load_calibration y el override del FemtoBoltBackend
    esperan `camera_matrix` + `distortion_coefficients`)."""
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
    fs.write("generated_by", "iter4/calibrar_camara.py")
    fs.write("generated_at_utc", datetime.now(timezone.utc).isoformat())
    fs.release()
    # Verificacion de lectura (el formato que consumen los backends)
    fs = cv2.FileStorage(str(output_path), cv2.FILE_STORAGE_READ)
    K_chk = fs.getNode("camera_matrix").mat()
    d_chk = fs.getNode("distortion_coefficients").mat()
    fs.release()
    if K_chk is None or d_chk is None or K_chk.shape != (3, 3):
        raise IOError(f"verificacion de lectura FALLO en {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Calibracion intrinseca con tablero (OpenCV).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default="iter4/tracker_config_doctor.yaml",
                        help="Perfil del que tomar la camara (backend/source).")
    parser.add_argument("--output", required=True,
                        help="Ruta del .yml de salida (obligatoria, sin "
                             "default-trampa).")
    parser.add_argument("--cols", type=int, default=8,
                        help="Esquinas interiores horizontales.")
    parser.add_argument("--rows", type=int, default=5,
                        help="Esquinas interiores verticales.")
    parser.add_argument("--square-mm", type=float, default=25.0)
    parser.add_argument("--min-vistas", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=900,
                        help="Autocierre en segundos (calibra con lo que haya).")
    args = parser.parse_args()

    cfg = cargar_config(args.config)
    log_info(f"Config: {args.config} (camera_type="
             f"{cfg['camera'].get('camera_type')})")
    log_info(f"Tablero: {args.cols}x{args.rows} esquinas interiores @ "
             f"{args.square_mm} mm  (patron del repo: 9x6 casillas)")
    log_info(f"Salida: {args.output}")

    objp = construir_objp(args.cols, args.rows, args.square_mm)
    criterios_subpix = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                        30, 0.001)

    cam = create_backend(cfg["camera"])
    cam.open()

    obj_points, img_points = [], []
    shape_img = None
    t_inicio = time.time()
    ultima_captura = 0.0

    log_info("ESPACIO = capturar vista (variar posicion/inclinacion/distancia)"
             " | q = calibrar y guardar")
    cv2.namedWindow(TITULO_VENTANA, cv2.WINDOW_NORMAL)
    try:
        while time.time() - t_inicio < args.timeout:
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            shape_img = gray.shape[::-1]  # (w, h)

            ok, corners = cv2.findChessboardCorners(
                gray, (args.cols, args.rows),
                cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_FAST_CHECK
                | cv2.CALIB_CB_NORMALIZE_IMAGE)

            disp = frame.copy()
            if ok:
                cv2.drawChessboardCorners(disp, (args.cols, args.rows),
                                          corners, ok)
            color = (0, 255, 0) if ok else (0, 0, 255)
            cv2.putText(disp, f"vistas: {len(img_points)}/{args.min_vistas} "
                        f"| tablero: {'DETECTADO' if ok else 'no visto'}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(disp, "ESPACIO=capturar  q=calibrar y guardar",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 255), 1)
            cv2.imshow(TITULO_VENTANA, disp)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and ok:
                if time.time() - ultima_captura < 0.5:
                    continue  # anti-rebote
                corners_fino = cv2.cornerSubPix(gray, corners, (11, 11),
                                                (-1, -1), criterios_subpix)
                obj_points.append(objp.copy())
                img_points.append(corners_fino)
                ultima_captura = time.time()
                log_info(f"vista {len(img_points)} capturada "
                         f"({len(corners_fino)} esquinas)")
            elif key == ord("q"):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print()
    log_stats(f"Vistas capturadas: {len(img_points)}")
    if len(img_points) < args.min_vistas:
        log_error(f"Menos de {args.min_vistas} vistas: calibracion debil. "
                  f"Recapturar (15-30 vistas variadas).")
        sys.exit(1)

    log_info("Calibrando (cv2.calibrateCamera)...")
    rmse, K, dist, _rvecs, _tvecs = cv2.calibrateCamera(
        obj_points, img_points, shape_img, None, None)

    log_stats(f"RMSE de reproyeccion: {rmse:.4f} px "
              f"(criterio: < 1 px; referencia historica 0.479 px)")
    log_stats(f"K =\n{K}")
    log_stats(f"dist = {dist.flatten()}")
    if rmse >= 1.0:
        log_warn("RMSE >= 1 px: calibracion FLOJA. Se guarda igual, pero lo "
                 "recomendado es recapturar descartando vistas borrosas o "
                 "extremas.")

    guardar_yml(args.output, K, dist, shape_img[0], shape_img[1], rmse,
                len(img_points), args.cols, args.rows, args.square_mm)
    log_info(f"Guardado y verificado: {args.output}")
    log_info("Para usarlo: apuntar camera.calibration_file del perfil a este "
             "archivo (el panel lo hace con backup, brief-02 M3).")


if __name__ == "__main__":
    main()
