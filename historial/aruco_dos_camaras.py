import cv2
import cv2.aruco as aruco
import numpy as np
import time
import csv

# IDs de los marcadores a comparar
ID1 = 0
ID2 = 4

# Parámetros de la cámara (ajusta si tienes calibración)
camera_matrix = np.array([[1000, 0, 640],
                          [0, 1000, 360],
                          [0, 0, 1]], dtype=np.float32)
dist_coeffs = np.zeros((5, 1))

# Usa los índices detectados (en tu caso, 1 y 3)
indice_cam1 = 1  # Primera cámara detectada
indice_cam2 = 3  # Segunda cámara detectada

cap1 = cv2.VideoCapture(indice_cam1)
cap2 = cv2.VideoCapture(indice_cam2)

csv_files = ['poses_aruco_distancia_cam1.csv', 'poses_aruco_distancia_cam2.csv']
caps = [cap1, cap2]

# Inicializa los archivos CSV
for csv_file in csv_files:
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'marker_id', 'x', 'y', 'z', 'rvec_x', 'rvec_y', 'rvec_z', 'distancia_mm'])

print("Iniciando tracking con dos cámaras...")
print("Presiona 'q' para salir")

while True:
    for i, cap in enumerate(caps):
        ret, frame = cap.read()
        if not ret:
            print(f"No se pudo leer la cámara {i+1}")
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()
        corners, ids, rejected = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

        distancia = ''
        posiciones = {}

        if ids is not None:
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners, 0.03, camera_matrix, dist_coeffs)
            for idx, marker_id in enumerate(ids.flatten()):
                tvec = tvecs[idx][0]
                rvec = rvecs[idx][0]
                posiciones[marker_id] = tvec
                # Dibuja los ejes del marcador (LÍNEA CORREGIDA)
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, 0.02)
                # Guarda datos individuales
                with open(csv_files[i], 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([time.time(), marker_id, tvec[0], tvec[1], tvec[2], rvec[0], rvec[1], rvec[2], ''])

            # Si ambos marcadores están presentes, calcula distancia
            if ID1 in posiciones and ID2 in posiciones:
                d = np.linalg.norm(posiciones[ID1] - posiciones[ID2]) * 1000  # mm
                distancia = d
                # Muestra la distancia en la ventana
                cv2.putText(frame, f'Distancia {ID1}-{ID2}: {distancia:.1f} mm', 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                # Guarda distancia en el CSV
                with open(csv_files[i], 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([time.time(), f'{ID1}-{ID2}', '', '', '', '', '', '', distancia])

        cv2.imshow(f'Camara {i+1}', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap1.release()
cap2.release()
cv2.destroyAllWindows()
print("Tracking terminado. Archivos CSV guardados.")
