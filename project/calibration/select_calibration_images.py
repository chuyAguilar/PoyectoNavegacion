import cv2
import glob
import os
import numpy as np

def main():
	images = glob.glob("project/calibration/images/*.jpg")
	total_original = len(images)
	valid_images = []
	
	if total_original == 0:
		print("No se encontraron imágenes en project/calibration/images/")
		return

	print(f"Evaluando un total de {total_original} imágenes originales...")
	
	for fname in images:
		img = cv2.imread(fname)
		if img is None:
			os.remove(fname)
			continue
			
		gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
		ret, corners = cv2.findChessboardCorners(gray, (8, 6), None)

		if not ret:
			try:
				os.remove(fname)
			except Exception as e:
				print(f"Error eliminando {fname}: {e}")
		else:
			corners = cv2.cornerSubPix(
				gray,
				corners,
				(11, 11),
				(-1, -1),
				criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
			)
			# Nitidez de la imagen usando varianza del Laplaciano
			sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
			# Tamaño real proyectado del tablero usando bounding box
			xs = corners[:, 0, 0]
			ys = corners[:, 0, 1]
			width = xs.max() - xs.min()
			height = ys.max() - ys.min()
			board_size = width * height
			
			score = sharpness * np.sqrt(board_size)
			valid_images.append((score, fname))

	total_valid = len(valid_images)

	# Ordenar por score descendente
	valid_images.sort(key=lambda x: x[0], reverse=True)

	# Conservar las mejores 30
	final_conserved = min(30, total_valid)
	top_images = valid_images[:final_conserved]
	discarded_images = valid_images[final_conserved:]

	# Eliminar las demás (que sí tenían chessboard pero su score es menor)
	for score, fname in discarded_images:
		try:
			os.remove(fname)
		except Exception as e:
			print(f"Error eliminando {fname}: {e}")

	total_eliminated = total_original - len(top_images)

	print("\n--- Resultados ---")
	print(f"Total imágenes originales: {total_original}")
	print(f"Imágenes válidas detectadas: {total_valid}")
	print(f"Imágenes finales conservadas (30): {final_conserved}")
	print(f"Imágenes eliminadas: {total_eliminated}")

if __name__ == "__main__":
	main()
