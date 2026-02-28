import cv2

print("Probando índices de cámaras (0 a 3)...")
for i in range(4):
    cap = cv2.VideoCapture(i)
    ret, frame = cap.read()
    if ret:
        print(f"Cámara detectada en índice {i}")
        cv2.imshow(f'Camara {i}', frame)
        cv2.waitKey(1000)  # Muestra la imagen 1 segundo
        cv2.destroyAllWindows()
    else:
        print(f"No hay cámara en índice {i}")
    cap.release()
print("Prueba terminada.")
