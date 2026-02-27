import cv2
print("Probando cámara índice 3...")
cap = cv2.VideoCapture(3)
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow('Camara 3', frame)
        print("Cámara 3 funcionando correctamente")
    else:
        print("ERROR: No se pudo leer la cámara 3")
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
print("Prueba terminada")