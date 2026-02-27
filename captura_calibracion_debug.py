import cv2
import os

cap = cv2.VideoCapture(3, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

cv2.namedWindow('Captura Calibración', cv2.WINDOW_NORMAL)

output_dir = "calibracion_imgs"
os.makedirs(output_dir, exist_ok=True)
img_count = 0

print("Presiona 'c' para capturar una imagen, 'q' para salir.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("No se pudo leer el frame.")
        break

    cv2.imshow('Captura Calibración', frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('c'):
        img_path = os.path.join(output_dir, f"calib_{img_count:02d}.jpg")
        success = cv2.imwrite(img_path, frame)
        if success:
            print(f"Imagen guardada: {img_path}")
        else:
            print(f"Error al guardar: {img_path}")
        img_count += 1
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()