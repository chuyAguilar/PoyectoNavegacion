import cv2

cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)  # Usa el índice 3 y backend DirectShow

if not cap.isOpened():
    print("No se pudo acceder a la cámara.")
else:
    print("¡Cámara detectada por OpenCV!")
    ret, frame = cap.read()
    if not ret:
        print("No se pudo leer el frame.")
    else:
        print("Frame recibido, dimensiones:", frame.shape)
        cv2.imshow('OBS VirtualCam', frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    cap.release()