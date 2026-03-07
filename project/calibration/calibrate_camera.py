import glob

import cv2
import numpy as np

pattern_size = (8, 6)
square_size = 22.2  # mm

images = glob.glob("project/calibration/images/*.jpg")

objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
objp[:, :2] = np.mgrid[0 : pattern_size[0], 0 : pattern_size[1]].T.reshape(-1, 2)
objp *= square_size

objpoints = []
imgpoints = []
image_size = None

print(f"Total imágenes encontradas: {len(images)}")

for fname in images:
    print(f"Procesando: {fname}")
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if image_size is None:
        image_size = gray.shape[::-1]

    ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)

    if ret:
        print("Chessboard detectado")
        objpoints.append(objp)

        corners2 = cv2.cornerSubPix(
            gray,
            corners,
            (11, 11),
            (-1, -1),
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
        )

        imgpoints.append(corners2)

        cv2.drawChessboardCorners(img, pattern_size, corners2, ret)
        cv2.imshow("Corners", img)
        cv2.waitKey(200)
    else:
        print("Chessboard NO detectado")

cv2.destroyAllWindows()

print(f"Imágenes válidas usadas para calibración: {len(objpoints)}")

if len(objpoints) == 0:
    print("ERROR: No se detectaron tableros en las imágenes.")
    exit()

print("Ejecutando calibración... esto puede tardar unos segundos")
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
    objpoints, imgpoints, image_size, None, None
)
print("Calibración terminada")

# Error de reproyección
mean_error = 0
for i in range(len(objpoints)):
    imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
    error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
    mean_error += error

print("Matriz intrínseca:\n", mtx)
print("Distorsión:\n", dist)
print("Error reproyección promedio:", mean_error / len(objpoints))

np.savez("project/calibration/calibration.npz", mtx=mtx, dist=dist)
print("Archivo guardado en project/calibration/calibration.npz")
