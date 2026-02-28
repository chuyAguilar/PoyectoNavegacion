import cv2

# Abre la cámara virtual de OBS (índice 3, ajusta si es necesario)
cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# Haz la ventana redimensionable
cv2.namedWindow('ArUco Detection', cv2.WINDOW_NORMAL)

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

        # Detección de marcadores ArUco
        corners, ids, rejected = cv2.aruco.detectMarkers(frame, aruco_dict, parameters=parameters)
        frame_markers = cv2.aruco.drawDetectedMarkers(frame.copy(), corners, ids)

        # Dibuja los IDs con texto grande y color verde
        if ids is not None:
            for i, corner in enumerate(corners):
                c = corner[0]
                # Coordenadas para el texto (esquina superior izquierda del marcador)
                x, y = int(c[0][0]), int(c[0][1]) - 10
                cv2.putText(
                    frame_markers,
                    f'ID: {ids[i][0]}',
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,            # Tamaño del texto
                    (0, 255, 0),    # Color (verde)
                    3,              # Grosor del texto
                    cv2.LINE_AA
                )

        cv2.imshow('ArUco Detection', frame_markers)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
