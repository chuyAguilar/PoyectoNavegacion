import cv2
import numpy as np
import time
from scipy.spatial.transform import Rotation as R_scipy

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker

def main():

    print("Reconstrucción automática del board del instrumento")
    print("Mueve el instrumento lentamente frente a la cámara")

    camera = Camera(index=0, width=1920, height=1080)

    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]

    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
    )

    relative_edges = {}
    last_capture = 0
    capture_interval = 0.2

    while True:

        frame = camera.read()

        corners, ids, rejected = cv2.aruco.detectMarkers(
            frame,
            tracker.aruco_dict
        )

        if ids is not None and len(ids) >= 2:

            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners,
                tracker.marker_length,
                camera_matrix,
                dist_coeffs
            )

            now = time.time()
            if now - last_capture > capture_interval:
                
                # Precalcular transformaciones para todos los marcadores detectados en este frame
                T_cameras = {}
                for i, marker_id in enumerate(ids.flatten()):
                    marker_id = int(marker_id)
                    rvec = rvecs[i][0]
                    tvec = tvecs[i][0]

                    R, _ = cv2.Rodrigues(rvec)

                    T_camera_marker = np.eye(4)
                    T_camera_marker[:3, :3] = R
                    T_camera_marker[:3, 3] = tvec
                    
                    T_cameras[marker_id] = T_camera_marker

                # Calcular transformaciones relativas entre cada par de marcadores visibles
                marcadores_presentes = list(T_cameras.keys())
                for i in range(len(marcadores_presentes)):
                    for j in range(i + 1, len(marcadores_presentes)):
                        id_i = marcadores_presentes[i]
                        id_j = marcadores_presentes[j]
                        
                        T_camera_i = T_cameras[id_i]
                        T_camera_j = T_cameras[id_j]
                        
                        T_i_j = np.linalg.inv(T_camera_i) @ T_camera_j
                        
                        if (id_i, id_j) not in relative_edges:
                            relative_edges[(id_i, id_j)] = []
                            
                        relative_edges[(id_i, id_j)].append(T_i_j)

                last_capture = now
                
            cv2.putText(
                frame,
                f"Capturando datos relativos...",
                (50, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

        cv2.imshow("Reconstruction", frame)

        key = cv2.waitKey(1)

        if key == 13:  # ENTER
            break

    camera.release()
    cv2.destroyAllWindows()

    if not relative_edges:
        print("No se observaron suficientes pares de marcadores. Saliendo...")
        return
        
    print("\nCalculando transformaciones promedio...")

    avg_edges = {}
    nodes = set()
    
    for edge, T_list in relative_edges.items():
        T_arr = np.array(T_list)
        
        # 1. Extraer las rotaciones y calcular su media
        R_obj = R_scipy.from_matrix(T_arr[:, :3, :3])
        R_mean = R_obj.mean().as_matrix()
        
        # 2. Calcular la media de las traslaciones
        t_mean = np.mean(T_arr[:, :3, 3], axis=0)
        
        # 3. Construir la matriz homogénea final
        T_avg = np.eye(4)
        T_avg[:3, :3] = R_mean
        T_avg[:3, 3] = t_mean
        
        avg_edges[edge] = T_avg
        nodes.add(edge[0])
        nodes.add(edge[1])

    if not nodes:
        return

    # Construir un grafo de marcadores y elegir arbitrariamente un marcador raíz
    root_id = min(nodes)
    print(f"Marcador raíz seleccionado: {root_id}")
    
    T_root_marker = {root_id: np.eye(4)}
    visited = {root_id}
    queue = [root_id]
    
    # Propagar transformaciones a lo largo del grafo (BFS)
    while queue:
        current = queue.pop(0)
        
        for neighbor in nodes:
            if neighbor not in visited:
                if (current, neighbor) in avg_edges:
                    T_root_marker[neighbor] = T_root_marker[current] @ avg_edges[(current, neighbor)]
                    visited.add(neighbor)
                    queue.append(neighbor)
                elif (neighbor, current) in avg_edges:
                    # Si no tenemos el T_current_neighbor directo (aunque deberiamos por como los guardamos), usamos el inverso
                    T_root_marker[neighbor] = T_root_marker[current] @ np.linalg.inv(avg_edges[(neighbor, current)])
                    visited.add(neighbor)
                    queue.append(neighbor)

    print("\nCentros estimados:")
    for marker_id in sorted(T_root_marker.keys()):
        center = T_root_marker[marker_id][:3, 3]
        print(f"{marker_id} -> {center}")

if __name__ == "__main__":
    main()