import cv2
import numpy as np
import csv
import time

# IDs de los dos marcadores a comparar
ID1 = 1
ID2 = 4

# Carga los parámetros de calibración
with np.load('parametros_calibracion.npz') as X:
    mtx, dist = [X[i] for i in ('mtx', 'dist')]

marker_length = 0.05  # 50 mm

cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Resolución reducida para pruebas
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

cv2.namedWindow('ArUco Distancia', cv2.WINDOW_NORMAL)

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()

# Prepara el archivo CSV
csv_file = open('poses_aruco_distancia.csv', mode='w', newline='')
csv_writer = csv.writer(csv_file)
csv_writer.writerow(['timestamp', 'marker_id', 'x', 'y', 'z', 'rvec_x', 'rvec_y', 'rvec_z', 'distancia_mm'])

if not cap.isOpened():
    print("No se pudo acceder a la cámara.")
else:
    print("¡Cámara detectada por OpenCV!")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo leer el frame.")
            break

        print("Procesando frame...")  # Depuración
        frame_undistorted = cv2.undistort(frame, mtx, dist, None, mtx)
        corners, ids, rejected = cv2.aruco.detectMarkers(frame_undistorted, aruco_dict, parameters=parameters)
        print("DetectMarkers ejecutado")  # Depuración

        tvec_dict = {}
        if ids is not None:
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(corners, marker_length, mtx, dist)
            frame_markers = cv2.aruco.drawDetectedMarkers(frame_undistorted.copy(), corners, ids)
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                tvec = tvecs[i][0]
                rvec = rvecs[i][0]
                tvec_dict[marker_id] = tvec
                cv2.drawFrameAxes(frame_markers, mtx, dist, rvecs[i], tvecs[i], marker_length/2)
                c = corners[i][0]
                x, y = int(c[0][0]), int(c[0][1]) - 10
                cv2.putText(
                    frame_markers,
                    f'ID: {marker_id}',
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (0, 255, 0),
                    3,
                    cv2.LINE_AA
                )
                # Inicialmente, distancia es vacía
                distancia_mm = ''
                # Si ambos marcadores están presentes, calcula la distancia
                if ID1 in tvec_dict and ID2 in tvec_dict:
                    d = np.linalg.norm(tvec_dict[ID1] - tvec_dict[ID2])
                    distancia_mm = d * 1000  # metros a milímetros
                    # Muestra la distancia en la ventana
                    cv2.putText(
                        frame_markers,
                        f'Distancia {ID1}-{ID2}: {distancia_mm:.1f} mm',
                        (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.2,
                        (0, 0, 255),
                        3,
                        cv2.LINE_AA
                    )
                # Guarda la pose y la distancia (si está disponible) en el CSV
                timestamp = time.time()
                csv_writer.writerow([timestamp, marker_id, tvec[0], tvec[1], tvec[2], rvec[0], rvec[1], rvec[2], distancia_mm])
                print(f"Guardado: ID={marker_id}, Pos=({tvec[0]:.3f}, {tvec[1]:.3f}, {tvec[2]:.3f}), Dist={distancia_mm}")
        else:
            frame_markers = frame_undistorted.copy()

        cv2.imshow('ArUco Distancia', frame_markers)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    csv_file.close()
    print("Archivo CSV guardado como 'poses_aruco_distancia.csv'")
