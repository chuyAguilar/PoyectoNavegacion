# -*- coding: utf-8 -*-
"""
IDENTIFICAR IDs de los marcadores en vivo.

Abre la camara y dibuja el ID (numero grande) sobre cada marcador detectado, mas
un punto en la esquina 0 (top-left del marcador) para ver su ORIENTACION. Sirve
para verificar el orden/colocacion de los marcadores del dodecaedro ANTES de
calibrar el rigid body entero.

Nota: el detector ArUco decodifica la orientacion del patron, asi que el ID NO se
confunde 6<->9 ni por giro. El numero que ves es el ID real.

Funciona en Femto o webcam (usa el camera_type del config).

Uso (desde codigo\):
    python iter4\identificar_ids.py                                     # Femto (default)
    python iter4\identificar_ids.py --config iter4\tracker_config_doctor.yaml  # webcam
Teclas:  q = salir
"""
import argparse
import time

import cv2
import numpy as np

from camera_backend import create_backend
from captura_calibracion import cargar_config


def main():
    ap = argparse.ArgumentParser(description="Identificar IDs de marcadores en vivo.")
    ap.add_argument("--config", default="iter4/tracker_config.yaml")
    ap.add_argument("--permisivo", action="store_true",
                    help="Usar el tuning permisivo del config (mas detecciones, mas falsos).")
    args = ap.parse_args()

    cfg = cargar_config(args.config)
    dict_name = cfg["markers"]["dictionary"].upper()
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if not args.permisivo:
        # ESTRICTO: evita falsos positivos (IDs inventados en ruido/textura).
        params.minMarkerPerimeterRate = 0.05          # ignora blobs chicos
        params.polygonalApproxAccuracyRate = 0.03     # bordes mas rectos
        params.maxErroneousBitsInBorderRate = 0.10    # borde casi perfecto
        params.errorCorrectionRate = 0.35             # menos correccion = menos falsos
        params.minOtsuStdDev = 5.0                    # rechaza zonas de bajo contraste
        print("[IDs] Deteccion ESTRICTA (sin falsos positivos). --permisivo para aflojar.")
    else:
        # mismo tuning permisivo del tracker
        from captura_calibracion import aplicar_detector_params
        aplicar_detector_params(params, cfg["markers"].get("detector", {}))
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    usar_api = True

    cam = create_backend(cfg["camera"])
    cam.open()
    print("[IDs] Apunta el dodecaedro a la camara. q = salir.")

    win = "Identificar IDs - q para salir"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    ultimo_print = 0.0

    while True:
        frame, _, _ = cam.read()
        if frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if usar_api:
            corners, ids, _ = detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)

        disp = frame.copy()
        visibles = []
        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(disp, corners)
            for i, mid in enumerate(ids.flatten()):
                c = corners[i].reshape(4, 2)
                centro = c.mean(axis=0).astype(int)
                # ID grande con contorno para legibilidad
                txt = str(int(mid))
                cv2.putText(disp, txt, tuple(centro), cv2.FONT_HERSHEY_SIMPLEX,
                            1.4, (0, 0, 0), 6)
                cv2.putText(disp, txt, tuple(centro), cv2.FONT_HERSHEY_SIMPLEX,
                            1.4, (0, 255, 0), 2)
                # esquina 0 (top-left del marcador) en rojo -> muestra orientacion
                cv2.circle(disp, tuple(c[0].astype(int)), 6, (0, 0, 255), -1)
                visibles.append(int(mid))

        visibles = sorted(visibles)
        cv2.putText(disp, f"IDs visibles ({len(visibles)}): {visibles}",
                    (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(disp, "punto rojo = esquina 0 (orientacion)",
                    (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)
        cv2.imshow(win, disp)

        # Imprime a consola cada 0.5 s (por si no miras la ventana)
        t = time.time()
        if t - ultimo_print > 0.5:
            print(f"  visibles: {visibles}")
            ultimo_print = t

        if (cv2.waitKey(1) & 0xFF) == ord('q'):
            break

    cam.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
