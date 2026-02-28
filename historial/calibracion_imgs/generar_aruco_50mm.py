import cv2
import numpy as np
from PIL import Image

# Configuración
MARKER_ID = 0
MARKER_SIZE_MM = 50  # 50mm x 50mm
DPI = 300  # Alta resolución para impresión

# Calcular tamaño en píxeles para 50mm a 300 DPI
# 1 pulgada = 25.4 mm
MARKER_SIZE_PIXELS = int(MARKER_SIZE_MM / 25.4 * DPI)

# Generar marcador ArUco ID 0
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker_img = cv2.aruco.generateImageMarker(aruco_dict, MARKER_ID, MARKER_SIZE_PIXELS)

# Agregar borde blanco (5mm)
BORDER_MM = 5
BORDER_PIXELS = int(BORDER_MM / 25.4 * DPI)
total_size = MARKER_SIZE_PIXELS + 2 * BORDER_PIXELS

canvas = np.ones((total_size, total_size), dtype=np.uint8) * 255
canvas[BORDER_PIXELS:BORDER_PIXELS+MARKER_SIZE_PIXELS, 
       BORDER_PIXELS:BORDER_PIXELS+MARKER_SIZE_PIXELS] = marker_img

# Convertir a PIL y guardar con DPI información
pil_img = Image.fromarray(canvas)
pil_img.save("aruco_id_0_50mm.png", dpi=(DPI, DPI))

print(f"✅ Marcador ArUco ID {MARKER_ID} generado")
print(f"   Tamaño: {MARKER_SIZE_MM}mm x {MARKER_SIZE_MM}mm")
print(f"   Archivo: aruco_id_0_50mm.png")
print(f"   DPI: {DPI}")
print(f"\n⚠️  IMPORTANTE: Al imprimir, asegúrate de:")
print("   - Escala: 100% (tamaño real)")
print("   - Sin ajustar a página")
