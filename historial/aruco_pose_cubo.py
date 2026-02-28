import cv2
import numpy as np

# Carga los parámetros de calibración
with np.load('parametros_calibracion.npz') as X:
    mtx, dist = [X[i] for i in ('mtx', 'dist')]

# Tamaño real del marcador en metros (50 mm = 0.05 m)
marker_length = 0.05

# Abre la cámara virtual de OBS (ajusta el índice si es necesario)
cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

cv2.namedWindow('ArUco Pose Cubo', cv2.WINDOW_NORMAL)

# Carga el diccionario de marcadores ArUco
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parameters = cv2.aruco.DetectorParameters()

if not cap.isOpened():
    print("No se pudo acceder a la cámara.")
else:
    print("¡Cámara detectada por OpenCV!")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo leer el frame.")
            break

        # Corrige la distorsión de la imagen
        frame_undistorted = cv2.undistort(frame, mtx, dist, None, mtx)

        # Detección de marcadores ArUco en la imagen corregida
        corners, ids, rejected = cv2.aruco.detectMarkers(frame_undistorted, aruco_dict, parameters=parameters)

        if ids is not None:
            # Estima la pose de cada marcador
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(corners, marker_length, mtx, dist)
            frame_markers = cv2.aruco.drawDetectedMarkers(frame_undistorted.copy(), corners, ids)
            for i in range(len(ids)):
                # Dibuja los ejes XYZ sobre cada marcador
                cv2.drawFrameAxes(frame_markers, mtx, dist, rvecs[i], tvecs[i], marker_length/2)
                # Dibuja el ID grande
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
        else:
            frame_markers = frame_undistorted.copy()

        cv2.imshow('ArUco Pose Cubo', frame_markers)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
