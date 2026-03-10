import cv2
import numpy as np

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker
from project.communication.igtl_sender import IGTLSender
from project.math3d.transforms import Transform
from scipy.spatial.transform import Rotation as R_scipy
from scipy.spatial.transform import Slerp

def main():

    # -----------------------------
    # Cámara
    # -----------------------------
    camera = Camera(index=0, width=1920, height=1080)

    # -----------------------------
    # Calibración real
    # -----------------------------
    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]

    # -----------------------------
    # Tracker
    # -----------------------------
    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
    )

    # -----------------------------
    # OpenIGTLink
    # -----------------------------
    igtl = IGTLSender("127.0.0.1", 18944)

    smoothed_distances = {}

    translations_x = []
    translations_y = []
    translations_z = []
    distances = []

    alpha = 0.7
    
    filtered_translation = None
    filtered_rotation = None
    filter_alpha = 0.85

    while True:

        frame = camera.read()

        transforms, corners, ids, rvecs = tracker.detect(frame)

        # Dibujar marcadores
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        # ---------------------------------
        # Información por marcador
        # ---------------------------------
        for marker_id, T in transforms.items():

            translation = T.translation()
            raw_distance_m = np.linalg.norm(translation)

            # suavizado solo para display
            if marker_id in smoothed_distances:
                smoothed_m = (
                    alpha * smoothed_distances[marker_id]
                    + (1 - alpha) * raw_distance_m
                )
            else:
                smoothed_m = raw_distance_m

            smoothed_distances[marker_id] = smoothed_m
            distance_mm = smoothed_m * 1000.0

            if isinstance(marker_id, int):
                y_pos = 80 + 40 * marker_id
                label = f"ID {marker_id} | Dist: {distance_mm:.1f} mm"
            else:
                y_pos = 80
                label = f"Instrument | Dist: {distance_mm:.1f} mm"

            cv2.putText(
                frame,
                label,
                (50, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )



        # ---------------------------------
        # Enviar transforms a Slicer
        # ---------------------------------
        reference_id = 0

        if reference_id in transforms:
            T_camera_reference = transforms[reference_id]

            igtl.send_transform(
                name="Reference",
                matrix=T_camera_reference.matrix(),
            )

        if reference_id in transforms and "instrument" in transforms:

            T_camera_reference = transforms[reference_id]
            T_camera_pointer = transforms["instrument"]

            R_board_to_instrument = R_scipy.from_euler("xyz", [0, 0, 0], degrees=True).as_matrix()

            T_board_to_instrument = Transform.from_rotation_translation(
                R_board_to_instrument,
                np.zeros(3)
            )

            T_camera_pointer = T_camera_pointer @ T_board_to_instrument
            
            T_tip = Transform.from_rotation_translation(
                np.eye(3),
                tracker.tip_offset
            )           
            T_camera_pointer = T_camera_pointer @ T_tip

            T_reference_pointer = T_camera_reference.inverse() @ T_camera_pointer
            
            translation = T_reference_pointer.translation()
            distance = np.linalg.norm(translation)

            # EMA filtering for translation
            if filtered_translation is None:
                filtered_translation = translation
            else:
                filtered_translation = (
                    filter_alpha * filtered_translation +
                    (1 - filter_alpha) * translation
                )
                
            # SLERP filtering for rotation
            R_current = R_scipy.from_matrix(T_reference_pointer.rotation())
            
            if filtered_rotation is None:
                filtered_rotation = R_current
            else:
                key_rots = R_scipy.from_quat(
                    np.vstack([
                        filtered_rotation.as_quat(),
                        R_current.as_quat()
                    ])
                )
                
                slerp_interp = Slerp([0, 1], key_rots)
                
                filtered_rotation = slerp_interp([1 - filter_alpha])[0]

            T_filtered = Transform.from_rotation_translation(
                filtered_rotation.as_matrix(),
                filtered_translation
            )

            if len(translations_x) >= 1000:
                translations_x.pop(0)
                translations_y.pop(0)
                translations_z.pop(0)
                distances.pop(0)

            translations_x.append(translation[0])
            translations_y.append(translation[1])
            translations_z.append(translation[2])
            distances.append(distance)

            igtl.send_transform(
                name="Pointer",
                matrix=T_filtered.matrix(),
            )
        else:
            filtered_translation = None
            filtered_rotation = None

        # ---------------------------------
        # Distancia entre marcadores
        # ---------------------------------
        if 0 in transforms and "instrument" in transforms:

            p0 = transforms[0].translation()
            p1 = transforms["instrument"].translation()

            dist_between_m = np.linalg.norm(p0 - p1)
            dist_between_mm = dist_between_m * 1000.0

            cv2.putText(
                frame,
                f"Dist 0-1: {dist_between_mm:.1f} mm",
                (50, 200),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )

        cv2.imshow("Tracking → 3D Slicer", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("a"):
            frames_analyzed = len(distances)
            if frames_analyzed > 0:
                mean_x = np.mean(translations_x)
                mean_y = np.mean(translations_y)
                mean_z = np.mean(translations_z)
                std_x = np.std(translations_x)
                std_y = np.std(translations_y)
                std_z = np.std(translations_z)
                
                mean_distance = np.mean(distances)
                std_distance = np.std(distances)
                max_deviation = np.max(np.abs(np.array(distances) - mean_distance))

                print("\n--- Stability Audit Report ---")
                print(f"Frames analyzed: {frames_analyzed}")
                print(f"Mean (X, Y, Z): ({mean_x:.4f}, {mean_y:.4f}, {mean_z:.4f})")
                print(f"Std (X, Y, Z): ({std_x:.4f}, {std_y:.4f}, {std_z:.4f})")
                print(f"Mean distance: {mean_distance:.4f}")
                print(f"Std distance: {std_distance:.4f}")
                print(f"Max deviation: {max_deviation:.4f}")
                print("------------------------------\n")
            else:
                print("\nNo data to analyze yet.\n")

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()