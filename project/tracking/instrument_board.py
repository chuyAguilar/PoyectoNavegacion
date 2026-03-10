import cv2
import numpy as np
import json
import os

def create_instrument_board():
    marker_size = 0.045  # metros
    half = marker_size / 2.0
    
    json_path = "project/calibration/instrument_marker_calibration.json"
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"No se encuentra el archivo de calibracion JSON en: {json_path}")
        
    with open(json_path, 'r') as f:
        calibrations = json.load(f)
        
    ids_list = sorted([int(k) for k in calibrations.keys()])
    ids = np.array(ids_list, dtype=np.int32)
    
    objectPoints = []
    
    for marker_id in ids_list:
        data = calibrations[str(marker_id)]
        center = np.array(data["translation"], dtype=np.float32)
        R = np.array(data["rotation"], dtype=np.float32)
        
        x_axis = R[:, 0]
        y_axis = R[:, 1]
        z_axis = R[:, 2]
        
        # Generar las esquinas siguiendo el orden OpenCV
        top_left = center - half * x_axis + half * y_axis
        top_right = center + half * x_axis + half * y_axis
        bottom_right = center + half * x_axis - half * y_axis
        bottom_left = center - half * x_axis - half * y_axis
        
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
