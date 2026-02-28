import cv2
import numpy as np
import glob

# Parámetros del tablero de ajedrez
num_cuadros_x = 9  # Número de cuadros internos en horizontal
num_cuadros_y = 6  # Número de cuadros internos en vertical
tam_cuadro = 25.0  # Tamaño de cada cuadro en mm (ajusta según tu impresión)

# Crea los puntos 3D del tablero de ajedrez
objp = np.zeros((num_cuadros_y * num_cuadros_x, 3), np.float32)
objp[:, :2] = np.mgrid[0:num_cuadros_x, 0:num_cuadros_y].T.reshape(-1, 2)
objp *= tam_cuadro

objpoints = []  # Puntos 3D en el mundo real
imgpoints = []  # Puntos 2D en la imagen

# Lee todas las imágenes de la carpeta
imagenes = glob.glob('calibracion_imgs/*.jpg')

for fname in imagenes:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Encuentra las esquinas del tablero de ajedrez
    ret, corners = cv2.findChessboardCorners(gray, (num_cuadros_x, num_cuadros_y), None)

    if ret:
        objpoints.append(objp)
        imgpoints.append(corners)
        # Dibuja y muestra las esquinas
        cv2.drawChessboardCorners(img, (num_cuadros_x, num_cuadros_y), corners, ret)
        cv2.imshow('Esquinas detectadas', img)
        cv2.waitKey(200)
    else:
        print(f"No se detectaron esquinas en {fname}")

cv2.destroyAllWindows()

# Calibra la cámara
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

print("\nMatriz de la cámara (mtx):\n", mtx)
print("\nCoeficientes de distorsión (dist):\n", dist)
print("\nError de reproyección:", ret)

# Guarda los parámetros en un archivo
np.savez('parametros_calibracion.npz', mtx=mtx, dist=dist, rvecs=rvecs, tvecs=tvecs)
print("\nParámetros guardados en 'parametros_calibracion.npz'")