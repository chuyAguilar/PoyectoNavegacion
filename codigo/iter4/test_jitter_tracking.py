# -*- coding: utf-8 -*-
"""
DIAGNOSTICO de JITTER del tracking (rigid body / dodecaedro).

Sosten el dodecaedro QUIETO frente a la camara. Mide cuanto tiembla la pose con
el objeto estatico => eso es jitter puro del tracking. Reporta:
  - std de posicion (mm) y de orientacion (grados).
  - error de reproyeccion POR MARCADOR (cual marcador esta corrompiendo la pose).
  - cuantos marcadores se usan por frame.
  - % de frames con pose valida.

Sirve para cuantificar el tracking ANTES y DESPUES de cada mejora de software.

Uso (desde codigo\):
    python iter4\test_jitter_tracking.py                                   # Femto
    python iter4\test_jitter_tracking.py --config iter4\tracker_config_doctor.yaml  # global shutter
    python iter4\test_jitter_tracking.py --n 300
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from camera_backend import create_backend
from captura_calibracion import crear_detector
from tracker import cargar_config, cargar_rigid_body, estimar_pose_rigid_body


def reproj_por_marcador(detecciones, geom, rvec, tvec, K, dist):
    """Error de reproyeccion (px) por marcador con la pose dada."""
    out = {}
    for tid, corners in detecciones.items():
        if tid not in geom:
            continue
        proj, _ = cv2.projectPoints(geom[tid], rvec, tvec, K, dist)
        proj = proj.reshape(4, 2)
        img = corners.reshape(4, 2)
        out[tid] = float(np.mean(np.linalg.norm(proj - img, axis=1)))
    return out


def main():
    ap = argparse.ArgumentParser(description="Diagnostico de jitter del tracking.")
    ap.add_argument("--config", default="iter4/tracker_config.yaml")
    ap.add_argument("--n", type=int, default=200, help="Frames a medir.")
    args = ap.parse_args()

    cfg = cargar_config(args.config)
    detector, usar_api, aruco_dict, params = crear_detector(cfg["markers"])
    geom_path = cfg["rigid_bodies"][0]["geometry_file"]
    if not Path(geom_path).exists():
        geom_path = str(Path(__file__).parent / geom_path)
    geom = cargar_rigid_body(geom_path)
    rb_ids = set(geom.keys())
    print(f"[Jitter] Rigid body IDs: {sorted(rb_ids)}")
    print("[Jitter] SOSTEN EL DODECAEDRO QUIETO. Midiendo...")

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()

    tvecs, rvecs, n_marks = [], [], []
    reproj_acc = {}
    frames_ok = 0
    intentos = 0
    while len(tvecs) < args.n and intentos < args.n * 8:
        intentos += 1
        frame, _, _ = cam.read()
        if frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if usar_api:
            corners, ids, _ = detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)
        if ids is None:
            continue
        det = {int(m): corners[i].reshape(1, 4, 2) for i, m in enumerate(ids.flatten())
               if int(m) in rb_ids}
        if len(det) < 1:
            continue
        res = estimar_pose_rigid_body(det, geom, K, dist)
        if res is None:
            continue
        rvec, tvec, n = res
        tvecs.append(tvec.flatten())
        rvecs.append(rvec.flatten())
        n_marks.append(n)
        frames_ok += 1
        for tid, e in reproj_por_marcador(det, geom, rvec, tvec, K, dist).items():
            reproj_acc.setdefault(tid, []).append(e)
    cam.close()

    if len(tvecs) < 10:
        print(f"[Jitter] Muy pocas poses validas ({len(tvecs)}). Revisa deteccion.")
        sys.exit(1)

    tvecs = np.array(tvecs)
    rots = Rotation.from_rotvec(np.array(rvecs))
    ref = rots.mean()
    ang_dev = (ref.inv() * rots).magnitude() * 180.0 / np.pi  # grados

    print("\n========== RESULTADO JITTER (objeto estatico) ==========")
    print(f"  Frames validos: {frames_ok}/{intentos}  ({100*frames_ok/intentos:.0f}%)")
    print(f"  Marcadores usados por frame: media {np.mean(n_marks):.1f}, "
          f"min {min(n_marks)}, max {max(n_marks)}")
    print(f"  --- JITTER DE POSICION (mm) ---")
    print(f"    std X={tvecs[:,0].std():.2f}  Y={tvecs[:,1].std():.2f}  Z={tvecs[:,2].std():.2f}")
    print(f"    std 3D (norma): {np.linalg.norm(tvecs.std(axis=0)):.2f} mm")
    print(f"  --- JITTER DE ORIENTACION (grados) ---")
    print(f"    std {ang_dev.std():.3f}  max desviacion {ang_dev.max():.3f}")
    print(f"  --- ERROR DE REPROYECCION POR MARCADOR (px) ---")
    filas = []
    for tid in sorted(reproj_acc):
        e = np.array(reproj_acc[tid])
        filas.append((np.mean(e), tid, len(e), np.max(e)))
    for mean_e, tid, cnt, max_e in sorted(filas, reverse=True):
        flag = "  <-- ALTO" if mean_e > 2.0 else ""
        print(f"    ID {tid:3d}: media {mean_e:.2f} px  (max {max_e:.2f}, n={cnt}){flag}")
    print("========================================================")
    print("Interpretacion:")
    print("  - Jitter posicion >1-2mm o orientacion >0.5 grados con objeto quieto = malo.")
    print("  - Un marcador con reproyeccion ALTA (>2px) esta corrompiendo la pose:")
    print("    el PnP actual NO lo rechaza -> mejora #1 = rechazo de outliers.")


if __name__ == "__main__":
    main()
