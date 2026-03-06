import cv2
import numpy as np

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker
from project.communication.igtl_sender import IGTLSender

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

    last_transforms = {}
    smoothed_distances = {}

    alpha = 0.7

    while True:

        frame = camera.read()

        transforms, corners, ids, rvecs = tracker.detect(frame)

        # Persistencia si se pierde un frame
        if transforms:
            last_transforms = transforms
        else:
            transforms = last_transforms

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

            text = f"ID {marker_id} | Dist: {distance_mm:.1f} mm"

            cv2.putText(
                frame,
                text,
                (50, 80 + 40 * marker_id),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            # ---------------------------------
            # Enviar transform real a Slicer
            # ---------------------------------
            matrix = T.matrix()

            igtl.send_transform(
                name="Pointer",
                matrix=matrix,
            )

        # ---------------------------------
        # Distancia entre marcadores
        # ---------------------------------
        if 0 in transforms and 1 in transforms:

            p0 = transforms[0].translation()
            p1 = transforms[1].translation()

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

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()