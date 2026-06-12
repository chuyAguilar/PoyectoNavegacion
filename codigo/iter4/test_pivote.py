# -*- coding: utf-8 -*-
"""
Calibracion de pivote del dodecaedro — iter 4 (Femto Bolt, solo 2D).

Captura poses del dodecaedro durante un pivote, aplica RANSAC + ajuste a
esfera, cross-check con AX=b (Yaniv 2015), y reporta el offset del tip con
su std (la metrica que importa).

Cambios vs iter 3:
  - Camara via camera_backend.create_backend (webcam | femtobolt).
  - K/dist desde el backend (calibracion de fabrica del SDK para femtobolt).
  - DetectorParameters tuneados desde tracker_config.yaml (mismos que tracker
    y captura_calibracion).
  - Pose multi-marker reutilizada de tracker.py (incluye filtro z<=0).
  - min_markers desde rigid_bodies_quality (default 3).
  - Outputs en iter4/data/ con metadata (fecha UTC, sha256 de la geometria).
  - El depth NO se usa para el pivote: descartado por multipath/bias
    (ver memoria multipath-tof-caja-luz, 2026-06-11).

Uso (desde codigo\):
    python iter4\test_pivote.py --duracion 45

INSTRUCCIONES DURANTE LA CAPTURA:
  - Clava la punta en un punto fijo (carton con orificio).
  - Pivotea haciendo conos amplios pero suaves; la punta NO se mueve.
  - Cubre la mayor variedad de orientaciones posible.
  - Dodecaedro siempre visible. FUERA de la caja de luz no es necesario
    para pivote (no usamos depth), pero distancia 50-70 cm si.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from datetime import datetime, timezone

import cv2
import numpy as np
from scipy.optimize import least_squares

from camera_backend import create_backend
from captura_calibracion import cargar_config, crear_detector
from tracker import cargar_rigid_body, estimar_pose_rigid_body, rvec_tvec_a_matriz


def log_info(m): print(f"[INFO] {m}")
def log_warn(m): print(f"[WARN] {m}")
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr)
def log_stats(m): print(f"[STATS] {m}")


# ============================================================================
# Ajuste de esfera y RANSAC (igual que iter 3)
# ============================================================================

def ajustar_esfera(puntos):
    """Ajuste least-squares a esfera. Devuelve (centro, radio, rmse)."""
    centro_inicial = puntos.mean(axis=0)
    radio_inicial = np.linalg.norm(puntos - centro_inicial, axis=1).mean()
    params = [*centro_inicial, radio_inicial]

    def residuos(p, pts):
        cx, cy, cz, r = p
        return np.linalg.norm(pts - np.array([cx, cy, cz]), axis=1) - r

    res = least_squares(residuos, params, args=(puntos,))
    cx, cy, cz, r = res.x
    centro = np.array([cx, cy, cz])
    distancias = np.linalg.norm(puntos - centro, axis=1)
    rmse = np.sqrt(np.mean((distancias - r) ** 2))
    return centro, r, rmse


def ransac_pivote(poses, n_iter=1000, sample_size=20, umbral_inlier=1.5, verbose=True):
    posiciones = poses[:, :3, 3]
    N = len(posiciones)
    np.random.seed(42)
    mejor_inliers = []
    for i in range(n_iter):
        idx = np.random.choice(N, min(sample_size, N), replace=False)
        try:
            centro, radio, _ = ajustar_esfera(posiciones[idx])
        except Exception:
            continue
        distancias = np.linalg.norm(posiciones - centro, axis=1)
        errores = np.abs(distancias - radio)
        inliers = np.where(errores < umbral_inlier)[0]
        if len(inliers) > len(mejor_inliers):
            mejor_inliers = inliers
        if verbose and (i + 1) % 200 == 0:
            print(f"    RANSAC {i+1}/{n_iter}: mejor inlier set = {len(mejor_inliers)}/{N}")
    return mejor_inliers


def ajustar_pivote_axb(poses):
    """Pivote AX=b clasico (Yaniv 2015). Devuelve (offset_dod, tip_cam, rmse)."""
    N = len(poses)
    A = np.zeros((3 * N, 6))
    b = np.zeros(3 * N)
    for k, pose in enumerate(poses):
        A[3*k:3*k+3, :3] = pose[:3, :3]
        A[3*k:3*k+3, 3:6] = -np.eye(3)
        b[3*k:3*k+3] = -pose[:3, 3]
    x, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    offset_dod, tip_cam = x[:3], x[3:6]
    rmse = float(np.sqrt(np.mean((A @ x - b) ** 2)))
    return offset_dod, tip_cam, rmse


def guardar_npy_verificado(ruta, arr):
    """np.save + fsync + relectura (leccion: np.save trunca en Windows)."""
    if os.path.exists(ruta):
        os.remove(ruta)
    np.save(ruta, arr)
    with open(ruta, "rb+") as f:
        f.flush()
        os.fsync(f.fileno())
    releido = np.load(ruta)
    if releido.shape != arr.shape:
        log_error(f"{ruta} se trunco al guardar: esperaba {arr.shape}, hay {releido.shape}")
        sys.exit(1)


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--duracion", type=int, default=45)
    parser.add_argument("--output-poses", default="iter4/data/poses_pivote_dodecaedro.npy")
    parser.add_argument("--output-matriz", default="iter4/data/StylusTipToDodecaedro")
    parser.add_argument("--umbral-inlier", type=float, default=1.5)
    args = parser.parse_args()

    cfg = cargar_config(args.config)

    rb_cfg = cfg["rigid_bodies"][0]
    geom_path = rb_cfg["geometry_file"]
    rb_geom = cargar_rigid_body(geom_path)
    geom_sha = sha256_archivo(geom_path)
    log_info(f"Rigid body: {len(rb_geom)} markers {sorted(rb_geom)} de {geom_path}")
    log_info(f"  sha256 geometria: {geom_sha[:16]}...")
    if "calibrado" not in str(geom_path):
        log_warn("La geometria NO parece ser la calibrada (post-BA). Verificar config.")

    min_markers = cfg.get("rigid_bodies_quality", {}).get("min_markers", 3)
    detector, _, _, _ = crear_detector(cfg["markers"])

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()
    log_info(f"Backend: {type(cam).__name__}, K {K.shape}")

    print()
    log_info("INSTRUCCIONES:")
    log_info("  1. Punta clavada en el carton con orificio. NO se mueve.")
    log_info("  2. Conos amplios y suaves, maxima variedad de orientaciones.")
    log_info("  3. Dodecaedro siempre visible, a 50-70 cm.")
    log_info("  4. 'q' en la ventana para terminar antes.")
    log_info(f"Duracion: {args.duracion}s. Comenzando en 5 segundos...")
    time.sleep(5)
    log_info("CAPTURANDO!")

    poses = []
    n_markers_por_pose = []
    t_inicio = time.time()
    n_frames = 0
    last_print = t_inicio

    try:
        while True:
            t_now = time.time()
            if t_now - t_inicio > args.duracion:
                break
            frame, _depth, _ts = cam.read()
            if frame is None:
                continue
            n_frames += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = detector.detectMarkers(gray)

            if ids is not None:
                detecciones = {}
                for i, mid in enumerate(ids.flatten().tolist()):
                    if int(mid) in rb_geom:
                        detecciones[int(mid)] = corners[i]
                if len(detecciones) >= min_markers:
                    resultado = estimar_pose_rigid_body(detecciones, rb_geom, K, dist)
                    if resultado is not None:
                        rvec, tvec, n_usados = resultado
                        poses.append(rvec_tvec_a_matriz(rvec, tvec))
                        n_markers_por_pose.append(n_usados)

            display = frame.copy()
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(display, corners, ids)
            elapsed = t_now - t_inicio
            cv2.putText(display, f"Pivote: {elapsed:.1f}s / {args.duracion}s",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(display, f"Poses: {len(poses)}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Pivote iter4 - q para parar", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            if t_now - last_print > 5.0:
                log_info(f"  [{elapsed:.0f}s] {len(poses)} poses, "
                         f"markers/pose prom {np.mean(n_markers_por_pose):.2f}"
                         if n_markers_por_pose else f"  [{elapsed:.0f}s] 0 poses")
                last_print = t_now
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print()
    log_stats(f"Frames: {n_frames}, poses validas: {len(poses)} "
              f"({100.0*len(poses)/max(1,n_frames):.0f}%)")
    if n_markers_por_pose:
        log_stats(f"Markers por pose: promedio {np.mean(n_markers_por_pose):.2f}, "
                  f"min {min(n_markers_por_pose)}")
    if len(poses) < 50:
        log_error("Muy pocas poses para calibrar (<50). Recapturar.")
        sys.exit(1)

    poses = np.array(poses)
    guardar_npy_verificado(args.output_poses, poses)
    log_info(f"Poses guardadas y verificadas: {args.output_poses}")

    # === RANSAC + esfera ===
    print()
    log_info("Procesamiento RANSAC...")
    posiciones = poses[:, :3, 3]
    N = len(posiciones)
    inliers = ransac_pivote(poses, umbral_inlier=args.umbral_inlier)
    log_stats(f"Inliers: {len(inliers)}/{N} ({100.0*len(inliers)/N:.1f}%)")

    centro_pivot, radio, rmse = ajustar_esfera(posiciones[inliers])
    log_stats(f"Esfera: centro [{centro_pivot[0]:+.2f}, {centro_pivot[1]:+.2f}, "
              f"{centro_pivot[2]:+.2f}] mm, radio {radio:.2f} mm, RMSE {rmse:.3f} mm")

    tips = []
    for pose in poses[inliers]:
        tips.append((np.linalg.inv(pose) @ np.append(centro_pivot, 1.0))[:3])
    tips = np.array(tips)
    offset = tips.mean(axis=0)
    std = tips.std(axis=0)
    log_stats(f"Offset tip (frame dodecaedro): [{offset[0]:+.3f}, {offset[1]:+.3f}, "
              f"{offset[2]:+.3f}] mm, magnitud {np.linalg.norm(offset):.2f} mm")
    log_stats(f"STD: [{std[0]:.3f}, {std[1]:.3f}, {std[2]:.3f}] mm")

    # === Cross-check AX=b ===
    offset_axb, tip_cam_axb, axb_rmse = ajustar_pivote_axb(poses[inliers])
    diff_norm = float(np.linalg.norm(offset_axb - offset))
    log_stats(f"AX=b: offset [{offset_axb[0]:+.3f}, {offset_axb[1]:+.3f}, "
              f"{offset_axb[2]:+.3f}] mm, RMSE {axb_rmse:.3f} mm")
    log_stats(f"Diferencia esfera vs AX=b: {diff_norm:.3f} mm")
    if diff_norm > 2.0:
        log_warn("DISCREPANCIA > 2 mm entre metodos: punta movida, juego mecanico,")
        log_warn("o pocos markers/pose. Re-clavar la punta y re-capturar.")
    elif diff_norm > 0.5:
        log_info("Pequena discrepancia entre metodos, aceptable por ruido.")
    else:
        log_info("Ambos metodos coinciden: calibracion robusta.")

    # === Evaluacion ===
    std_max = std.max()
    nivel = ("EXCELENTE" if std_max < 1.0 else
             "BUENO" if std_max < 2.0 else
             "REGULAR" if std_max < 5.0 else "INSUFICIENTE")
    log_stats(f"[{nivel}] Std maximo: {std_max:.2f} mm "
              f"(iter 2 logro 1.35 mm; objetivo <=1.35)")
    if np.mean(n_markers_por_pose) < 3.0:
        log_warn(f"Promedio markers/pose {np.mean(n_markers_por_pose):.2f} < 3.")

    # === Guardar matriz con metadata ===
    matriz = np.eye(4)
    matriz[:3, 3] = offset
    ruta_npy = args.output_matriz + ".npy"
    ruta_txt = args.output_matriz + ".txt"
    guardar_npy_verificado(ruta_npy, matriz)
    with open(ruta_txt, "w") as f:
        f.write("# Matriz StylusTipToDodecaedro 4x4 — iter 4\n")
        f.write(f"# Fecha UTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# Geometria: {geom_path} (sha256 {geom_sha[:16]})\n")
        f.write(f"# Poses: {len(inliers)} inliers de {N} ({100.0*len(inliers)/N:.1f}%)\n")
        f.write(f"# Markers/pose promedio: {np.mean(n_markers_por_pose):.2f}\n")
        f.write("#\n# METODO PRINCIPAL (esfera + transform):\n")
        f.write(f"#   Offset (mm): [{offset[0]:+.3f}, {offset[1]:+.3f}, {offset[2]:+.3f}]\n")
        f.write(f"#   Magnitud:    {np.linalg.norm(offset):.3f} mm\n")
        f.write(f"#   Std (mm):    [{std[0]:.3f}, {std[1]:.3f}, {std[2]:.3f}]\n")
        f.write(f"#   RMSE esfera: {rmse:.3f} mm\n")
        f.write("#\n# CROSS-CHECK (AX=b, Yaniv 2015):\n")
        f.write(f"#   Offset (mm): [{offset_axb[0]:+.3f}, {offset_axb[1]:+.3f}, {offset_axb[2]:+.3f}]\n")
        f.write(f"#   AX=b RMSE:   {axb_rmse:.3f} mm\n")
        f.write(f"#   Diff vs esfera: {diff_norm:.3f} mm\n#\n")
        for fila in matriz:
            f.write(" ".join(f"{v:12.6f}" for v in fila) + "\n")
    log_info(f"Guardados: {ruta_npy}, {ruta_txt}")


if __name__ == "__main__":
    main()
