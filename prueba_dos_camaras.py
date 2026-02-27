import cv2

print("Probando cámaras 1 y 3 al mismo tiempo...")

cap1 = cv2.VideoCapture(1)
cap2 = cv2.VideoCapture(3)

while True:
    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()
    if ret1:
        cv2.imshow('Camara 1', frame1)
    else:
        print("ERROR: No se pudo leer la cámara 1")
    if ret2:
        cv2.imshow('Camara 3', frame2)
    else:
        print("ERROR: No se pudo leer la cámara 3")
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap1.release()
cap2.release()
cv2.destroyAllWindows()
print("Prueba terminada")