# -*- coding: utf-8 -*-
"""
Calibracion del tip del stylus por DIVOT (template-based) — iter 4.

Alternativa al pivote clasico: la punta se apoya QUIETA en un hoyuelo conico
de posicion CONOCIDA respecto al marker ID 1 de la placa de calibracion
(stl/placa_calibracion/). Cada frame da una ecuacion 3D completa:

    R_pd @ offset + t_pd = p_divot

donde (R_pd, t_pd) es la pose del dodecaedro EN EL FRAME DE LA PLACA
(T_placa^-1 @ T_dodec) y p_divot son las coordenadas del apice del divot en
el frame del marker de la placa. El offset sale por minimos cuadrados
lineales. Ventajas vs pivote:
  - Sin tecnica de movimiento (la falla tipica del pivote).
  - El bias de profundidad de la camara afecta a ambas poses por igual y se
    cancela a primer orden (todo es relativo placa<->dodecaedro).
  - La dispersion entre orientaciones es la metrica de calidad, impresa.

PROCEDIMIENTO:
  1. Placa apoyada/inclinada mirando a la camara (el angulo NO importa,
     se mide solo). Marker ID 1 pegado en el recess, esquina TL en la muesca.
  2. Punta del stylus en el divot elegido (A/B/C; B=2 puntos es el central).
  3. Sostener QUIETO ~4 s, cambiar de orientacion, repetir 6-10 veces.
     Inclinar el stylus hacia los lados/abajo, no sobre el marker.
  4. El script junta solo los frames quietos y agrupa por orientacion.

Uso (desde codigo\):
    python iter4\calibrar_tip_divot.py --divot B --duracion 90
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

from camera_backend import create_backend
from captura_calibracion import cargar_config, crear_detector
from tracker import (cargar_rigid_body, estimar_pose_individual,
                     estimar_pose_rigid_body, rvec_tvec_a_matriz)


def log_info(m): print(f"[INFO] {m}")
def log_warn(m): print(f"[WARN] {m}")
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr)
def log_stats(m): print(f"[STATS] {m}")


# Coordenadas del apice de cada divot en el frame del marker ID 1 (mm).
# Fuente: stl/placa_calibracion/README.md (v1). NO cambiar sin reimprimir.
DIVOTS = {
    "A": np.array([-40.0, -50.0, -3.5]),
    "B": np.array([0.0, -50.0, -3.5]),
    "C": np.array([40.0, -50.0, -3.5]),
}
PLACA_VERSION = "placa_calibracion_v1"

# Filtro de quietud: el sample se acepta si la pose relativa se movio menos
# que esto respecto al frame anterior (descarta transiciones entre posturas).
QUIETO_MM = 0.8
QUIETO_DEG = 0.8
# Clustering secuencial de orientaciones: nueva postura si rota mas que esto.
CLUSTER_DEG = 8.0
MIN_SAMPLES_CLUSTER = 10


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--divot", default="B", choices=list(DIVOTS))
    parser.add_argument("--duracion", type=int, default=90)
    parser.add_argument("--plate-id", type=int, default=1)
    parser.add_argument("--plate-mm", type=float, default=60.0)
    parser.add_argument("--output-matriz", default="iter4/data/StylusTipToDodecaedro_divot")
    parser.add_argument("--output-samples", default="iter4/data/divot_samples.npz")
    args = parser.parse_args()

    p_divot = DIVOTS[args.divot]
    cfg = cargar_config(args.config)
    rb_cfg = cfg["rigid_bodies"][0]
    rb_geom = cargar_rigid_body(rb_cfg["geometry_file"])
    geom_sha = hashlib.sha256(open(rb_cfg["geometry_file"], "rb").read()).hexdigest()
    min_markers = cfg.get("rigid_bodies_quality", {}).get("min_markers", 3)
    detector, _, _, _ = crear_detector(cfg["markers"])

    log_info(f"Placa: {PLACA_VERSION}, marker ID {args.plate_id} @ {args.plate_mm} mm")
    log_info(f"Divot {args.divot}: {p_divot} mm (frame del marker de la placa)")
    log_info(f"Rigid body: {rb_cfg['geometry_file']} (sha {geom_sha[:16]})")

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()

    print()
    log_info("PROCEDIMIENTO: punta en el divot, QUIETO ~4 s por orientacion,")
    log_info("cambiar de orientacion (6-10 posturas distintas), 'q' para terminar.")
    log_info(f"Comenzando en 5 segundos...")
    time.sleep(5)
    log_info("CAPTURANDO!")

    samples_R, samples_t = [], []
    prev = None
    n_frames = n_ambos = 0
    t_inicio = time.time()
    last_print = t_inicio

    try:
        while True:
            t_now = time.time()
            if t_now - t_inicio > args.duracion:
                break
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            n_frames += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = detector.detectMarkers(gray)

            estado = "buscando..."
            if ids is not None:
                idlist = ids.flatten().tolist()
                det_rb = {int(m): corners[i] for i, m in enumerate(idlist)
                          if int(m) in rb_geom}
                plate_idx = [i for i, m in enumerate(idlist)
                             if int(m) == args.plate_id]
                if plate_idx and len(det_rb) >= min_markers:
                    pp = estimar_pose_individual(
                        corners[plate_idx[0]], args.plate_mm, K, dist)
                    pd = estimar_pose_rigid_body(det_rb, rb_geom, K, dist)
                    if pp is not None and pd is not None:
                        n_ambos += 1
                        T_plate = rvec_tvec_a_matriz(*pp)
                        T_dodec = rvec_tvec_a_matriz(pd[0], pd[1])
                        T_pd = np.linalg.inv(T_plate) @ T_dodec
                        R_pd, t_pd = T_pd[:3, :3], T_pd[:3, 3]
                        # filtro de quietud
                        if prev is not None:
                            dt = np.linalg.norm(t_pd - prev[1])
                            dR = np.degrees(np.arccos(np.clip(
                                (np.trace(R_pd @ prev[0].T) - 1) / 2, -1, 1)))
                            if dt < QUIETO_MM and dR < QUIETO_DEG:
                                samples_R.append(R_pd)
                                samples_t.append(t_pd)
                                estado = f"QUIETO ok ({len(samples_R)})"
                            else:
                                estado = "moviendose"
                        prev = (R_pd, t_pd)
                    else:
                        estado = "pose invalida"
                else:
                    estado = (f"placa:{'si' if plate_idx else 'NO'} "
                              f"dodec:{len(det_rb)}/{min_markers}")

            display = frame.copy()
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(display, corners, ids)
            cv2.putText(display, f"{t_now - t_inicio:.0f}s/{args.duracion}s  "
                        f"samples: {len(samples_R)}  [{estado}]",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("Divot iter4 - q para terminar", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if t_now - last_print > 5.0:
                log_info(f"  [{t_now - t_inicio:.0f}s] {len(samples_R)} samples quietos "
                         f"({n_ambos} frames con placa+dodec)")
                last_print = t_now
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print()
    log_stats(f"Frames: {n_frames}, con placa+dodec: {n_ambos}, "
              f"samples quietos: {len(samples_R)}")
    if len(samples_R) < 30:
        log_error("Muy pocos samples (<30). Sostener mas tiempo quieto por postura.")
        sys.exit(1)

    Rs = np.array(samples_R); ts = np.array(samples_t)

    # === clustering secuencial por orientacion ===
    clusters = [[0]]
    for i in range(1, len(Rs)):
        R_ref = Rs[clusters[-1][0]]
        ang = np.degrees(np.arccos(np.clip((np.trace(Rs[i] @ R_ref.T) - 1) / 2, -1, 1)))
        if ang < CLUSTER_DEG:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    clusters = [c for c in clusters if len(c) >= MIN_SAMPLES_CLUSTER]
    log_stats(f"Posturas (clusters de orientacion) utiles: {len(clusters)} "
              f"({[len(c) for c in clusters]})")
    if len(clusters) < 4:
        log_warn("Menos de 4 posturas distintas: la solucion queda debil. "
                 "Repetir cubriendo mas orientaciones.")

    # === LSQ global: R_i @ offset = p_divot - t_i ===
    def resolver(idx):
        A = np.concatenate([Rs[i] for i in idx], axis=0)
        b = np.concatenate([p_divot - ts[i] for i in idx], axis=0)
        x, _res, _rk, _sv = np.linalg.lstsq(A, b, rcond=None)
        rms = float(np.sqrt(np.mean((A @ x - b) ** 2)))
        return x, rms

    todos = [i for c in clusters for i in c]
    offset, rms = resolver(todos)
    log_stats(f"Offset tip (frame dodecaedro): [{offset[0]:+.3f}, {offset[1]:+.3f}, "
              f"{offset[2]:+.3f}] mm, magnitud {np.linalg.norm(offset):.2f} mm")
    log_stats(f"RMS residual global: {rms:.3f} mm")

    # === consistencia entre posturas (la metrica de verdad) ===
    por_cluster = np.array([resolver(c)[0] for c in clusters])
    spread = por_cluster.std(axis=0)
    log_stats(f"Offset por postura (std entre posturas): "
              f"[{spread[0]:.3f}, {spread[1]:.3f}, {spread[2]:.3f}] mm")
    for k, (c, oc) in enumerate(zip(clusters, por_cluster)):
        log_info(f"  postura {k+1} (n={len(c)}): "
                 f"[{oc[0]:+.3f}, {oc[1]:+.3f}, {oc[2]:+.3f}] mm")
    smax = spread.max()
    nivel = ("EXCELENTE" if smax < 0.5 else "BUENO" if smax < 1.0 else
             "REGULAR" if smax < 2.0 else "INSUFICIENTE")
    log_stats(f"[{nivel}] Spread maximo entre posturas: {smax:.2f} mm")
    log_info("Referencia: magnitud nominal por caliper ~92.4 mm (2026-06-12).")

    # === guardar ===
    np.savez_compressed(args.output_samples, R=Rs, t=ts,
                        divot=args.divot, p_divot=p_divot,
                        clusters_inicio=[c[0] for c in clusters])
    chk = np.load(args.output_samples, allow_pickle=True)
    assert chk["R"].shape == Rs.shape
    matriz = np.eye(4); matriz[:3, 3] = offset
    np.save(args.output_matriz + ".npy", matriz)
    rel = np.load(args.output_matriz + ".npy")
    assert rel.shape == (4, 4)
    with open(args.output_matriz + ".txt", "w") as f:
        f.write("# Matriz StylusTipToDodecaedro 4x4 — calibracion por DIVOT (iter 4)\n")
        f.write(f"# Fecha UTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# Placa: {PLACA_VERSION}, marker ID {args.plate_id} @ {args.plate_mm} mm\n")
        f.write(f"# Divot {args.divot}: {p_divot.tolist()} mm\n")
        f.write(f"# Geometria dodecaedro: {rb_cfg['geometry_file']} (sha {geom_sha[:16]})\n")
        f.write(f"# Samples: {len(todos)} en {len(clusters)} posturas\n")
        f.write(f"# Offset (mm): [{offset[0]:+.3f}, {offset[1]:+.3f}, {offset[2]:+.3f}]\n")
        f.write(f"# Magnitud: {np.linalg.norm(offset):.3f} mm\n")
        f.write(f"# RMS global: {rms:.3f} mm, spread entre posturas: {spread.tolist()} mm\n#\n")
        for fila in matriz:
            f.write(" ".join(f"{v:12.6f}" for v in fila) + "\n")
    log_info(f"Guardados: {args.output_matriz}.npy/.txt, {args.output_samples}")


if __name__ == "__main__":
    main()
