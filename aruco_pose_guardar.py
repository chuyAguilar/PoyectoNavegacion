import cv2
import numpy as np
import csv
import time

# Carga los parámetros de calibración
with np.load('parametros_calibracion.npz') as X:
    mtx, dist = [X[i] for i in ('mtx', 'dist')]

marker_length = 0.05  # 50 mm

cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

cv2.namedWindow('ArUco Pose Guardar', cv2.WINDOW_NORMAL)

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()

# Prepara el archivo CSV
csv_file = open('poses_aruco.csv', mode='w', newline='')
csv_writer = csv.writer(csv_file)
csv_writer.writerow(['timestamp', 'marker_id', 'x', 'y', 'z', 'rvec_x', 'rvec_y', 'rvec_z'])

if not cap.isOpened():
    print("No se pudo acceder a la cámara.")
else:
    print("¡Cámara detectada por OpenCV!")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo leer el frame.")
            break

        frame_undistorted = cv2.undistort(frame, mtx, dist, None, mtx)
        corners, ids, rejected = cv2.aruco.detectMarkers(frame_undistorted, aruco_dict, parameters=parameters)

        if ids is not None:
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(corners, marker_length, mtx, dist)
            frame_markers = cv2.aruco.drawDetectedMarkers(frame_undistorted.copy(), corners, ids)
            for i in range(len(ids)):
                cv2.drawFrameAxes(frame_markers, mtx, dist, rvecs[i], tvecs[i], marker_length/2)
                c = corners[i][0]
                x, y = int(c[0][0]), int(c[0][1]) - 10
                cv2.putText(
                    frame_markers,
                    f'ID: {ids[i][0]}',
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (0, 255, 0),
                    3,
                    cv2.LINE_AA
                )
                # Guarda la pose en el CSV y muestra en la terminal
                timestamp = time.time()
                marker_id = int(ids[i][0])
                tvec = tvecs[i][0]  # x, y, z
                rvec = rvecs[i][0]  # rotación en vector de Rodrigues
                csv_writer.writerow([timestamp, marker_id, tvec[0], tvec[1], tvec[2], rvec[0], rvec[1], rvec[2]])
                print(f"Guardado: ID={marker_id}, Pos=({tvec[0]:.3f}, {tvec[1]:.3f}, {tvec[2]:.3f})")
        else:
            frame_markers = frame_undistorted.copy()

        cv2.imshow('ArUco Pose Guardar', frame_markers)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    csv_file.close()
    print("Archivo CSV guardado como 'poses_aruco.csv'")
