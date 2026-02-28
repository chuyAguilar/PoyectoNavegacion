import cv2
import numpy as np

# =========================
# CONFIGURACIÓN
# =========================

square_size_mm = 25
aruco_size_mm = 50

dpi = 300  # alta calidad impresión

# Chessboard config
inner_corners_x = 8
inner_corners_y = 6

# =========================
# FUNCIONES
# =========================

def mm_to_pixels(mm, dpi):
    return int(mm / 25.4 * dpi)

def generate_chessboard():
    squares_x = inner_corners_x + 1
    squares_y = inner_corners_y + 1

    square_px = mm_to_pixels(square_size_mm, dpi)

    width = squares_x * square_px
    height = squares_y * square_px

    board = np.zeros((height, width), dtype=np.uint8)

    for y in range(squares_y):
        for x in range(squares_x):
            if (x + y) % 2 == 0:
                cv2.rectangle(
                    board,
                    (x * square_px, y * square_px),
                    ((x + 1) * square_px, (y + 1) * square_px),
                    255,
                    -1
                )

    cv2.imwrite("chessboard.png", board)

def generate_aruco(marker_id):
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_px = mm_to_pixels(aruco_size_mm, dpi)
    marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_px)
    cv2.imwrite(f"aruco_{marker_id}.png", marker)


# =========================
# GENERAR
# =========================

generate_chessboard()
generate_aruco(0)
generate_aruco(1)

print("Archivos generados:")
print(" - chessboard.png")
print(" - aruco_0.png")
print(" - aruco_1.png")