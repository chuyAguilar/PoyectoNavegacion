import cv2
import cv2.aruco as aruco
import numpy as np

def main():
    print("=== DIAGNÓSTICO DE MARCADORES ARUCO ===")
    print("Este script intentará detectar marcadores usando varios diccionarios.")
    print("Presiona 'q' para salir.\n")

    # Diccionarios a probar
    dicts_to_test = [
        (aruco.DICT_4X4_50, "4x4_50 (Usado en Dodecaedro)"),
        (aruco.DICT_5X5_100, "5x5_100 (Usado en ID 23)"),
        (aruco.DICT_ARUCO_ORIGINAL, "Original"),
    ]

    # Configuración de detección
    params = aruco.DetectorParameters()
    
    current_cam_idx = 0
    cap = cv2.VideoCapture(current_cam_idx)
    if not cap.isOpened():
        print("Error: No se puede abrir la cámara.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        y_offset = 30
        
        found_any = False
        detection_info = []

        # Probar cada diccionario
        for dct_id, dct_name in dicts_to_test:
            aruco_dict = aruco.getPredefinedDictionary(dct_id)
            detector = aruco.ArucoDetector(aruco_dict, params)
            corners, ids, _ = detector.detectMarkers(gray)

            if ids is not None and len(ids) > 0:
                found_any = True
                aruco.drawDetectedMarkers(frame, corners, ids)
                
                # Recopilar info
                ids_flat = ids.flatten()
                info = f"[{dct_name}]: IDs detectados -> {ids_flat}"
                detection_info.append(info)
                print(info) # Imprimir en consola también para debug rápido

        # Mostrar info en pantalla
        cv2.putText(frame, "DIAGNOSTICO DE IDs (Presiona 'q' para salir)", (10, 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        for i, info in enumerate(detection_info):
            color = (0, 255, 0) # Verde
            cv2.putText(frame, info, (10, 50 + i*30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        if not found_any:
            cv2.putText(frame, "Buscando marcadores...", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Info de controles
        cv2.putText(frame, f"Camara Index: {current_cam_idx} (Presiona 'n' para cambiar)", (10, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow("Diagnostico ArUco", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('n'):
            # Cambiar camara
            print("Cambiando cámara...")
            cap.release()
            current_cam_idx += 1
            cap = cv2.VideoCapture(current_cam_idx)
            if not cap.isOpened():
                print(f"No se pudo abrir cámara {current_cam_idx}, volviendo a 0")
                current_cam_idx = 0
                cap = cv2.VideoCapture(current_cam_idx)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
