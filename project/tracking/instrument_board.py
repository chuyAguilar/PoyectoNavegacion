import cv2
import numpy as np

def create_instrument_board():
	marker_size = 0.0146  # metros
	target_a = 0.0222     # metros
	
	phi = (1.0 + np.sqrt(5.0)) / 2.0
	inv_phi = 1.0 / phi
	
	# 3. Definir explícitamente los 20 vértices del dodecaedro
	verts = np.array([
		[1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1],
		[-1, 1, 1], [-1, 1, -1], [-1, -1, 1], [-1, -1, -1],
		[0, inv_phi, phi], [0, inv_phi, -phi], [0, -inv_phi, phi], [0, -inv_phi, -phi],
		[inv_phi, phi, 0], [inv_phi, -phi, 0], [-inv_phi, phi, 0], [-inv_phi, -phi, 0],
		[phi, 0, inv_phi], [phi, 0, -inv_phi], [-phi, 0, inv_phi], [-phi, 0, -inv_phi]
	], dtype=np.float32)
	
	# Normalizar y escalar
	# Arista actual entre (1,1,1) y (0, 1/phi, phi) (índices 0 y 8)
	current_a = np.linalg.norm(verts[0] - verts[8])
	scale = target_a / current_a
	verts *= scale
	
	# 4. Definir las 12 caras pentagonales mediante índices conocidos
	faces = [
		[0, 8, 4, 14, 12],
		[0, 12, 1, 17, 16],
		[0, 16, 2, 10, 8],
		[1, 12, 14, 5, 9],
		[1, 9, 11, 3, 17],
		[2, 16, 17, 3, 13],
		[2, 13, 15, 6, 10],
		[3, 11, 7, 15, 13],
		[4, 8, 10, 6, 18],
		[4, 18, 19, 5, 14],
		[5, 19, 7, 11, 9],
		[6, 15, 7, 19, 18]
	]
	
	# Orientar el dodecaedro para que la cara 0 (lezna) apunte a +Z
	c0 = np.mean(verts[faces[0]], axis=0)
	n0 = c0 / np.linalg.norm(c0)
	
	z_axis = np.array([0.0, 0.0, 1.0])
	v = np.cross(n0, z_axis)
	c = np.dot(n0, z_axis)
	s = np.linalg.norm(v)
	
	if s < 1e-6:
		if c > 0:
			rot = np.eye(3)
		else:
			rot = np.diag([1, -1, -1])
	else:
		kmat = np.array([
			[0, -v[2], v[1]],
			[v[2], 0, -v[0]],
			[-v[1], v[0], 0]
		])
		rot = np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c) / (s ** 2))
		
	verts = np.dot(verts, rot.T)
	
	objectPoints = []
	# 7. Usar los IDs [10..20] y descartar una cara para la lezna (cara 0)
	ids = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], dtype=np.int32)
	half = marker_size / 2.0
	
	# 5. Para cada cara... (usamos las 11 restantes)
	for f_idx in faces[1:]:
		face_v = verts[f_idx]
		
		# calcular centro
		center = np.mean(face_v, axis=0)
		
		# calcular normal (hacia afuera)
		v0, v1, v2 = face_v[0], face_v[1], face_v[2]
		normal = np.cross(v1 - v0, v2 - v0)
		normal = normal / np.linalg.norm(normal)
		
		# construir sistema local (x,y,z)
		global_up = np.array([0.0, 0.0, 1.0])
		x_loc = np.cross(global_up, normal)
		
		# Si la normal es muy paralela al global_up, usar otra referencia
		if np.linalg.norm(x_loc) < 1e-6:
			global_ref = np.array([1.0, 0.0, 0.0])
			x_loc = np.cross(global_ref, normal)
			
		x_loc = x_loc / np.linalg.norm(x_loc)
		y_loc = np.cross(normal, x_loc)
		y_loc = y_loc / np.linalg.norm(y_loc)
		
		# 6. Generar las esquinas del marcador respetando el orden OpenCV
		top_left = center - half * x_loc + half * y_loc
		top_right = center + half * x_loc + half * y_loc
		bottom_right = center + half * x_loc - half * y_loc
		bottom_left = center - half * x_loc - half * y_loc
		
		corners_3d = np.array([
			top_left,
			top_right,
			bottom_right,
			bottom_left
		], dtype=np.float32)
		
		objectPoints.append(corners_3d)
		
	if hasattr(cv2.aruco, "getPredefinedDictionary"):
		aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
	else:
		aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_6X6_250)
		
	if hasattr(cv2.aruco, "Board"):
		board = cv2.aruco.Board(np.array(objectPoints), aruco_dict, ids)
	else:
		board = cv2.aruco.Board_create(np.array(objectPoints), aruco_dict, ids)
		
	tip_offset = np.array([0.0, 0.0, 0.2013], dtype=np.float32)
	
	return board, tip_offset
