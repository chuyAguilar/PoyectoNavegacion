import cv2
import numpy as np
import os

# Diccionario ArUco (usa uno estándar)
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)

# ID del marcador
marker_id = 23

# Tamaño en pixeles
marker_size = 1000

# Generar marcador
marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)

# Guardar imagen en el directorio actual
output_file = "aruco_23.png"
cv2.imwrite(output_file, marker)

print(f"ArUco generado: {os.path.abspath(output_file)}")
