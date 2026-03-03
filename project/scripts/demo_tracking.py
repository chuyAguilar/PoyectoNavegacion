import cv2
import numpy as np
from camera.camera import Camera
from filters.smoothing import smooth_vector
from navigation.reference_frame import ReferenceFrame
from navigation.roles import MarkerRoles
from tracking.aruco_tracker import ArucoTracker
from visualization.overlay import draw_relative_distance


def main():

    camera = Camera(index=0, width=1920, height=1080)

    # Cargar calibración real
    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]

    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
    )

    roles = MarkerRoles()
    base_id = roles.get_base_id()

    reference_frame = ReferenceFrame(base_marker_id=base_id)

    last_transforms = {}
    smoothed_vectors = {}
    alpha = 0.85

    while True:
        frame = camera.read()

        transforms, corners, ids, _ = tracker.detect(frame)

        if transforms:
            last_transforms = transforms
        else:
            transforms = last_transforms

        relative_transforms = reference_frame.compute_relative_transforms(transforms)

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        processed_transforms = {}

        for marker_id, T in relative_transforms.items():
            role_name = roles.get_role(marker_id)

            translation = T.translation()

            smoothed = smooth_vector(
                marker_id,
                translation,
                smoothed_vectors,
                alpha,
            )

            processed_transforms[marker_id] = smoothed

            # Convertir a mm
            x_mm = smoothed[0] * 1000.0
            y_mm = smoothed[1] * 1000.0
            z_mm = smoothed[2] * 1000.0

            text = f"{role_name} | X:{x_mm:.1f} Y:{y_mm:.1f} Z:{z_mm:.1f} mm"

            cv2.putText(
                frame,
                text,
                (50, 80 + 50 * marker_id),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        draw_relative_distance(frame, processed_transforms)

        cv2.imshow("Demo Tracking - Reference Frame", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
