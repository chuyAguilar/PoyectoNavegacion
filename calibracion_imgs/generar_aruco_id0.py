import cv2
import numpy as np

# Generar marcador ArUco ID 0
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker_id = 0
marker_size = 500  # pixels

marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)

# Agregar borde blanco
border = 50
marker_with_border = np.ones((marker_size + 2*border, marker_size + 2*border), dtype=np.uint8) * 255
marker_with_border[border:border+marker_size, border:border+marker_size] = marker_img

# Agregar texto
cv2.putText(marker_with_border, f"ArUco ID: {marker_id}", (10, marker_size + 2*border - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 2)

# Guardar
cv2.imwrite("aruco_id_0.png", marker_with_border)
print("Marcador guardado en: aruco_id_0.png")
print("Imprime este marcador a 5cm x 5cm (50mm x 50mm)")
