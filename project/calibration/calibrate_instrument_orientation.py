import cv2
import numpy as np
from scipy.spatial.transform import Rotation as R_scipy

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker

def main():
    print("Iniciando calibración del instrumento.")
    print("Mueve el instrumento libremente frente a la cámara.")

    # 1. Cámara
    camera = Camera(index=0, width=1920, height=1080)

    # 2. Calibración real
    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]

    # 3. Tracker
    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
    )

    rotations_list = []
    min_poses = 200
    poses_captured = 0

    while True:
        frame = camera.read()

        transforms, corners, ids, rvecs = tracker.detect(frame)

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        # Verificar si "instrument" fue detectado y 10 está en ids directamente
        if ids is not None and np.any(ids == 10) and transforms is not None and "instrument" in transforms:
            
            # 1. Obtener T_camera_board
            T_camera_board = transforms["instrument"]
            R_camera_board = T_camera_board.rotation()

            # 2. Obtener la pose individual del marcador 10 usando estimatePoseSingleMarkers
            idx = np.where(ids.flatten() == 10)[0][0]
            corner_10 = corners[idx]

            R_camera_10 = None
            valid_pose = False
            if hasattr(cv2.aruco, 'estimatePoseSingleMarkers'):
                rvec_10, tvec_10, _ = cv2.aruco.estimatePoseSingleMarkers(
                    [corner_10], tracker.marker_length, tracker.camera_matrix, tracker.dist_coeffs
                )
                if rvec_10 is not None:
                    R_camera_10, _ = cv2.Rodrigues(rvec_10[0][0])
                    valid_pose = True
            else:
                # Fallback para OpenCV 4.7+ si estimatePoseSingleMarkers no está disponible
                half_l = tracker.marker_length / 2.0
                obj_points = np.array([
                    [-half_l,  half_l, 0],
                    [ half_l,  half_l, 0],
                    [ half_l, -half_l, 0],
                    [-half_l, -half_l, 0]
                ], dtype=np.float32)
                success, rvec_10, tvec_10 = cv2.solvePnP(
                    obj_points, corner_10, tracker.camera_matrix, tracker.dist_coeffs, flags=cv2.SOLVEPNP_IPPE_SQUARE
                )
                if success:
                    R_camera_10, _ = cv2.Rodrigues(rvec_10)
                    valid_pose = True

            if valid_pose and R_camera_10 is not None:
                # 3. Calcular la normal del marcador 10 en coordenadas de cámara
                normal_camera_10 = R_camera_10[:, 2]

                # 4. Transformar esa normal al sistema del board
                normal_board_10 = R_camera_board.T @ normal_camera_10

                # 5. El eje del instrumento es el negativo de la normal del marcador 10
                z_instr = -normal_board_10
                z_instr = z_instr / np.linalg.norm(z_instr)

                # Usar el eje X del board como referencia
                x_board = np.array([1.0, 0.0, 0.0])
                
                # Proyectarlo para que sea ortogonal a z_instr
                x_instr = x_board - np.dot(x_board, z_instr) * z_instr
                
                # Fallback en caso de que x_board sea casi paralelo a z_instr
                if np.linalg.norm(x_instr) < 1e-6:
                    y_board = np.array([0.0, 1.0, 0.0])
                    x_instr = y_board - np.dot(y_board, z_instr) * z_instr
                    
                x_instr = x_instr / np.linalg.norm(x_instr)

                # Calcular y_instr con el producto cruz
                y_instr = np.cross(z_instr, x_instr)

                # Construir R_i evaluado contra x_instr, y_instr, z_instr
                R_i = np.column_stack((x_instr, y_instr, z_instr))

                # Guardar cada R_i
                rotations_list.append(R_i)
                poses_captured += 1

        if poses_captured > 0:
            cv2.putText(
                frame,
                f"Pose valida: {poses_captured}",
                (50, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

        if poses_captured >= min_poses:
            cv2.putText(
                frame,
                "Presiona ENTER para calcular calibracion.",
                (50, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

        cv2.imshow("Calibracion Orientacion", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 13 and poses_captured >= min_poses:  # ENTER key
            break
        elif key == ord('q'):
            print("Calibración cancelada.")
            camera.release()
            cv2.destroyAllWindows()
            return

    camera.release()
    cv2.destroyAllWindows()

    if poses_captured == 0:
        print("No se capturaron poses.")
        return

    print("Calculando calibración...")

    # Calcular la rotación promedio usando scipy.spatial.transform.Rotation
    rotations_array = np.array(rotations_list)
    R_obj = R_scipy.from_matrix(rotations_array)
    
    # Calcular promedio
    R_mean = R_obj.mean()
    R_board_instrument = R_mean.as_matrix()

    # Construir T_board_instrument (4x4)
    T_board_instrument = np.eye(4)
    T_board_instrument[:3, :3] = R_board_instrument

    print("\nMatriz R_board_instrument calculada:")
    print(R_board_instrument)

    save_path = "project/tracking/instrument_calibration.npz"
    np.savez(
        save_path,
        R_board_instrument=R_board_instrument,
        T_board_instrument=T_board_instrument
    )

    print(f"\nCalibración guardada en {save_path}\n")

if __name__ == "__main__":
    main()
