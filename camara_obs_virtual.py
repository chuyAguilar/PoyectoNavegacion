import cv2

cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

cv2.namedWindow('OBS VirtualCam', cv2.WINDOW_NORMAL)

if not cap.isOpened():
    print("No se pudo acceder a la cámara.")
else:
    print("¡Cámara detectada por OpenCV!")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo leer el frame.")
            break
        cv2.imshow('OBS VirtualCam', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()