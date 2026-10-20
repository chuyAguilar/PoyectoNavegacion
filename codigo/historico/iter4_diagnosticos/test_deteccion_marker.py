# -*- coding: utf-8 -*-
"""
Prueba rapida de deteccion de un marker (cupon / placa / stylus).

Muestra en vivo si el marker objetivo se detecta, con que tasa y con que
nitidez (error de reproyeccion en px). Sirve para validar un marker impreso
ANTES de comprometerse con la impresion completa.

Uso (desde codigo\):
    python iter4\test_deteccion_marker.py --id 181 --mm 16
    python iter4\test_deteccion_marker.py --id 1  --mm 59.55   # placa v2
"""
import argparse
import time
import cv2
import numpy as np
from camera_backend import create_backend
from captura_calibracion import cargar_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="iter4/tracker_config.yaml")
    ap.add_argument("--id", type=int, default=181, help="ID del marker a buscar")
    ap.add_argument("--mm", type=float, default=16.0, help="lado del marker en mm")
    ap.add_argument("--duracion", type=int, default=60)
    args = ap.parse_args()

    cfg = cargar_config(args.config)
    ad = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_MIP_36h12)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(ad, params)

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()
    h = args.mm / 2.0
    objp = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]], np.float64)

    print(f"[INFO] Buscando marker ID {args.id} @ {args.mm} mm. q para salir.")
    n_total = n_hit = 0
    t0 = time.time()
    try:
        while time.time() - t0 < args.duracion:
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            n_total += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = detector.detectMarkers(gray)
            disp = frame.copy()
            hit = False
            dist_cam = reproj = float("nan")
            if ids is not None:
                il = ids.flatten().tolist()
                cv2.aruco.drawDetectedMarkers(disp, corners, ids)
                if args.id in il:
                    hit = True; n_hit += 1
                    c = corners[il.index(args.id)].reshape(4, 1, 2).astype(np.float64)
                    ok, rv, tv = cv2.solvePnP(objp, c, K, dist,
                                              flags=cv2.SOLVEPNP_IPPE_SQUARE)
                    if ok:
                        dist_cam = float(np.linalg.norm(tv))
                        pr, _ = cv2.projectPoints(objp, rv, tv, K, dist)
                        reproj = float(np.linalg.norm(
                            pr.reshape(4, 2) - c.reshape(4, 2), axis=1).mean())
            col = (0, 255, 0) if hit else (0, 0, 255)
            txt = (f"ID {args.id}: {'DETECTADO' if hit else 'no'}  "
                   f"tasa {100*n_hit/max(1,n_total):.0f}%")
            cv2.putText(disp, txt, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2)
            if hit:
                cv2.putText(disp, f"dist {dist_cam:.0f} mm  reproj {reproj:.2f} px",
                            (10, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.imshow("Test deteccion - q para salir", disp)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()
    print(f"[STATS] Tasa de deteccion ID {args.id}: {n_hit}/{n_total} "
          f"({100*n_hit/max(1,n_total):.1f}%)")


if __name__ == "__main__":
    main()
