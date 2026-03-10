import cv2
import numpy as np
import json
import os
from scipy.spatial.transform import Rotation

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker


def main():

    print("Auto STL orientation calibration")
    print("Mantén el marcador 10 visible unos segundos")
    print("Se capturarán múltiples muestras para promediar")

    camera = Camera(index=0, width=1920, height=1080)

    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]

    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
    )

    target_id = 10

    offset_samples = []

    min_samples = 120

    while True:

        frame = camera.read()

        corners, ids, _ = cv2.aruco.detectMarkers(
            frame,
            tracker.aruco_dict
        )

        if ids is not None:

            ids_flat = ids.flatten()

            if target_id in ids_flat:

                idx = np.where(ids_flat == target_id)[0][0]

                marker_corners = np.array([corners[idx]])

                rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                    marker_corners,
                    tracker.marker_length,
                    camera_matrix,
                    dist_coeffs
                )

                rvec_marker = rvecs[0][0]
                tvec_marker = tvecs[0][0]

                R_marker, _ = cv2.Rodrigues(rvec_marker)

                # eje Z del marcador
                z_marker = R_marker[:, 2]

                # eje X del marcador
                x_marker = R_marker[:, 0]

                # ejes del STL
                z_stl = np.array([0.0, 0.0, 1.0])
                x_stl = np.array([1.0, 0.0, 0.0])

                # calcular rotación
                R_align, _ = Rotation.align_vectors(
                    [z_marker, x_marker],
                    [z_stl, x_stl]
                )

                R_offset = R_align.as_matrix()

                offset_samples.append(R_offset)

                cv2.putText(
                    frame,
                    f"Samples: {len(offset_samples)}",
                    (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0,255,0),
                    2
                )

        cv2.putText(
            frame,
            "ENTER: guardar calibracion",
            (20,80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255,255,255),
            1
        )

        cv2.putText(
            frame,
            "ESC: cancelar",
            (20,110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255,255,255),
            1
        )

        cv2.imshow("Auto Orientation Calibration", frame)

        key = cv2.waitKey(1)

        if key == 27:
            print("Cancelado")
            break

        if key == 13:

            if len(offset_samples) < min_samples:

                print("No hay suficientes muestras")

                continue

            rotations = Rotation.from_matrix(offset_samples)

            R_mean = rotations.mean().as_matrix()

            out_path = "project/calibration/instrument_alignment.json"

            data = {
                "marker_id": 10,
                "R_offset": R_mean.tolist()
            }

            with open(out_path, "w") as f:
                json.dump(data, f, indent=4)

            print("Calibración guardada en:", out_path)

            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()