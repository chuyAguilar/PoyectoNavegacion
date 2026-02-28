import cv2
import cv2.aruco as aruco

cap = cv2.VideoCapture(0)  # Usa 0 si solo tienes una cámara conectada

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
parameters = aruco.DetectorParameters()

while True:
    ret, frame = cap.read()
    if not ret:
        break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
    if ids is not None:
        print(f"Detectados: {ids.flatten()}")
        frame = aruco.drawDetectedMarkers(frame, corners, ids)
    else:
        print("No se detectaron marcadores en este frame.")
    cv2.imshow('Aruco Detection', frame)
    if cv2.waitKey(1) & 0xFF == 27:  # Presiona ESC para salir
        break

cap.release()
cv2.destroyAllWindows()
