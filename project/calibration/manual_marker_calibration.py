import cv2
import numpy as np
import trimesh
import json
import os
from scipy.spatial.transform import Rotation as R_scipy

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker

def main():
    print("Iniciando calibración manual de marcadores...")
    
    camera = Camera(index=0, width=1920, height=1080)
    
    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]
    
    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
    )
    
    stl_path = "project/utilities/models/lezna.stl"
    if not os.path.exists(stl_path):
        print(f"Error: No se encuentra el modelo {stl_path}")
        return
        
    mesh = trimesh.load(stl_path)
    vertices = mesh.vertices * 0.001  # Convertir mm a metros
    faces = mesh.faces
    
    ids_to_calibrate = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    current_idx = 0
    target_id = ids_to_calibrate[current_idx]
    
    t_off = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    rot_off = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    
    trans_inc = 0.001
    rot_inc = 1.0
    
    calibrations = {}
    
    while True:
        frame = camera.read()
        
        corners, ids, rejected = cv2.aruco.detectMarkers(
            frame,
            tracker.aruco_dict
        )
        
        target_detected = False
        
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            
            ids_flat = ids.flatten()
            if target_id in ids_flat:
                target_detected = True
                
                idx = np.where(ids_flat == target_id)[0][0]
                marker_corners = np.array([corners[idx]])
                
                rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                    marker_corners,
                    tracker.marker_length,
                    camera_matrix,
                    dist_coeffs
                )
                
                rvec = rvecs[0][0]
                tvec = tvecs[0][0]
                
                R_marker, _ = cv2.Rodrigues(rvec)
                T_marker = np.eye(4)
                T_marker[:3, :3] = R_marker
                T_marker[:3, 3] = tvec
                
                R_off = R_scipy.from_euler('xyz', rot_off, degrees=True).as_matrix()
                T_off = np.eye(4)
                T_off[:3, :3] = R_off
                T_off[:3, 3] = t_off
                
                T_stl = T_marker @ T_off
                rvec_stl, _ = cv2.Rodrigues(T_stl[:3, :3])
                tvec_stl = T_stl[:3, 3]
                
                imgpts, _ = cv2.projectPoints(vertices, rvec_stl, tvec_stl, camera_matrix, dist_coeffs)
                imgpts = np.int32(imgpts).reshape(-1, 2)
                
                V_cam = (T_stl[:3, :3] @ vertices.T).T + T_stl[:3, 3]
                face_centroids_z = np.mean(V_cam[faces, 2], axis=1)
                sorted_faces = faces[np.argsort(face_centroids_z)[::-1]]
                
                overlay = frame.copy()
                for face in sorted_faces:
                    pts = imgpts[face]
                    cv2.fillPoly(overlay, [pts], (150, 150, 255))
                    cv2.polylines(overlay, [pts], True, (50, 50, 200), 1)
                    
                cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                
        cv2.putText(frame, f"Marcador Actual: {target_id} ({current_idx+1}/{len(ids_to_calibrate)})", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Detectado: {'SI' if target_detected else 'NO'}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if target_detected else (0, 0, 255), 2)
        
        cv2.putText(frame, f"Traslacion (m): X={t_off[0]:.3f} Y={t_off[1]:.3f} Z={t_off[2]:.3f}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(frame, f"Rotacion (deg): X={rot_off[0]:.1f} Y={rot_off[1]:.1f} Z={rot_off[2]:.1f}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        cv2.putText(frame, "Controles:", (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, "N/P : Siguiente/Anterior | ENTER : Guardar", (20, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, "J/L : Mov X | U/O : Mov Y | I/K : Mov Z", (20, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, "Q/A : Rot X | W/S : Rot Y | E/D : Rot Z", (20, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, "ESC : Salir y Guardar JSON", (20, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Manual Calibration", frame)
        
        key = cv2.waitKey(1)
        if key == 27:
            break
        elif key == 13:
            R_off = R_scipy.from_euler('xyz', rot_off, degrees=True).as_matrix()
            calibrations[str(target_id)] = {
                "translation": t_off.tolist(),
                "rotation": R_off.tolist()
            }
            print(f"Calibración guardada para el marcador {target_id}.")
            
        elif key in [110, 78]:
            current_idx = (current_idx + 1) % len(ids_to_calibrate)
            target_id = ids_to_calibrate[current_idx]
            if str(target_id) in calibrations:
                t_off = np.array(calibrations[str(target_id)]["translation"], dtype=np.float32)
                R_off = np.array(calibrations[str(target_id)]["rotation"], dtype=np.float32)
                rot_off = R_scipy.from_matrix(R_off).as_euler('xyz', degrees=True).astype(np.float32)
            else:
                t_off = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                rot_off = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                
        elif key in [112, 80]:
            current_idx = (current_idx - 1) % len(ids_to_calibrate)
            target_id = ids_to_calibrate[current_idx]
            if str(target_id) in calibrations:
                t_off = np.array(calibrations[str(target_id)]["translation"], dtype=np.float32)
                R_off = np.array(calibrations[str(target_id)]["rotation"], dtype=np.float32)
                rot_off = R_scipy.from_matrix(R_off).as_euler('xyz', degrees=True).astype(np.float32)
            else:
                t_off = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                rot_off = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        elif key in [106, 74]: t_off[0] -= trans_inc
        elif key in [108, 76]: t_off[0] += trans_inc
        elif key in [117, 85]: t_off[1] -= trans_inc
        elif key in [111, 79]: t_off[1] += trans_inc
        elif key in [105, 73]: t_off[2] += trans_inc
        elif key in [107, 75]: t_off[2] -= trans_inc

        elif key in [113, 81]: rot_off[0] += rot_inc
        elif key in [97, 65]:  rot_off[0] -= rot_inc
        elif key in [119, 87]: rot_off[1] += rot_inc
        elif key in [115, 83]: rot_off[1] -= rot_inc
        elif key in [101, 69]: rot_off[2] += rot_inc
        elif key in [100, 68]: rot_off[2] -= rot_inc

    camera.release()
    cv2.destroyAllWindows()
    
    out_path = "project/calibration/instrument_marker_calibration.json"
    if calibrations:
        with open(out_path, 'w') as f:
            json.dump(calibrations, f, indent=4)
        print(f"Resultados guardados en: {out_path}")
    else:
        print("No se guardó ninguna calibración porque no se ingresaron datos.")

if __name__ == "__main__":
    main()
