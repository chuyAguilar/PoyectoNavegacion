import cv2
print("Probando cámara índice 1...")
cap = cv2.VideoCapture(1)
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow('Camara 1', frame)
        print("Cámara 1 funcionando correctamente")
    else:
        print("ERROR: No se pudo leer la cámara 1")
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
print("Prueba terminada")