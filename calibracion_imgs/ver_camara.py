import cv2
import sys

cam_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
print(f"Abriendo camara {cam_id}...")

cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
if not cap.isOpened():
    print(f"No se pudo abrir la camara {cam_id}")
    sys.exit(1)

print(f"Mostrando camara {cam_id}. Presiona 'q' para cerrar.")
while True:
    ret, frame = cap.read()
    if not ret:
        print("Error leyendo frame")
        break
    cv2.putText(frame, f"CAMARA {cam_id}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
    cv2.imshow(f"Camara {cam_id}", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
