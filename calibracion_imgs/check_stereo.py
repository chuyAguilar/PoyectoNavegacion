import cv2
import numpy as np
import cv2.aruco as aruco

def main():
    print("=== PRUEBA ESTÉREO CON CÁMARAS REALES (1 y 2) ===")
    print("Abriendo cámaras en índices 1 y 2...")
    print("Presiona 'q' para salir.\n")

    # Usar índices correctos (cámaras reales)
    cap_left = cv2.VideoCapture(1)
    cap_right = cv2.VideoCapture(2)

    if not cap_left.isOpened():
        print("❌ Error: No se pudo abrir cámara 1 (izquierda)")
    if not cap_right.isOpened():
        print("❌ Error: No se pudo abrir cámara 2 (derecha)")

    if not cap_left.isOpened() and not cap_right.isOpened():
        print("No hay cámaras disponibles.")
        return

    # Detector ArUco
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    params = aruco.DetectorParameters()
    detector = aruco.ArucoDetector(aruco_dict, params)

    while True:
        ret_l, frame_l = cap_left.read() if cap_left.isOpened() else (False, None)
        ret_r, frame_r = cap_right.read() if cap_right.isOpened() else (False, None)

        if not ret_l and not ret_r:
            print("No se capturaron frames.")
            break

        # Detectar en ambas cámaras
        if ret_l:
            gray_l = cv2.cvtColor(frame_l, cv2.COLOR_BGR2GRAY)
            corners_l, ids_l, _ = detector.detectMarkers(gray_l)
            if ids_l is not None:
                aruco.drawDetectedMarkers(frame_l, corners_l, ids_l)
            cv2.putText(frame_l, f"IDs: {ids_l.flatten() if ids_l is not None else 'Ninguno'}", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Camara IZQUIERDA (1)", frame_l)

        if ret_r:
            gray_r = cv2.cvtColor(frame_r, cv2.COLOR_BGR2GRAY)
            corners_r, ids_r, _ = detector.detectMarkers(gray_r)
            if ids_r is not None:
                aruco.drawDetectedMarkers(frame_r, corners_r, ids_r)
            cv2.putText(frame_r, f"IDs: {ids_r.flatten() if ids_r is not None else 'Ninguno'}", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Camara DERECHA (2)", frame_r)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
