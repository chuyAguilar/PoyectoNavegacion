import cv2
import numpy as np

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker


def rotation_matrix(rx, ry, rz):
    Rx = np.array([
        [1,0,0],
        [0,np.cos(rx),-np.sin(rx)],
        [0,np.sin(rx),np.cos(rx)]
    ])

    Ry = np.array([
        [np.cos(ry),0,np.sin(ry)],
        [0,1,0],
        [-np.sin(ry),0,np.cos(ry)]
    ])

    Rz = np.array([
        [np.cos(rz),-np.sin(rz),0],
        [np.sin(rz),np.cos(rz),0],
        [0,0,1]
    ])

    return Rz @ Ry @ Rx


def main():

    print("Alineación manual del instrumento")
    print("Controles:")
    print("Q/A -> rotar X")
    print("W/S -> rotar Y")
    print("E/D -> rotar Z")
    print("ENTER -> guardar")
    print("ESC -> salir")

    camera = Camera(index=0, width=1920, height=1080)

    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist_coeffs = calib["dist"]

    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs
    )

    rx = 0
    ry = 0
    rz = 0

    step = np.deg2rad(1)

    while True:

        frame = camera.read()

        transforms, corners, ids, rvecs = tracker.detect(frame)

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        if ids is not None and 10 in ids.flatten():

            idx = np.where(ids.flatten()==10)[0][0]

            rvec = rvecs[idx]
            R_cam_marker, _ = cv2.Rodrigues(rvec)

            R_manual = rotation_matrix(rx, ry, rz)

            R_total = R_cam_marker @ R_manual

            text = f"rx:{np.rad2deg(rx):.1f} ry:{np.rad2deg(ry):.1f} rz:{np.rad2deg(rz):.1f}"
            cv2.putText(frame,text,(40,40),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,0),2)

        cv2.imshow("Manual Alignment",frame)

        key = cv2.waitKey(1)

        if key == ord('q'):
            rx += step
        elif key == ord('a'):
            rx -= step

        elif key == ord('w'):
            ry += step
        elif key == ord('s'):
            ry -= step

        elif key == ord('e'):
            rz += step
        elif key == ord('d'):
            rz -= step

        elif key == 13:

            R_fix = rotation_matrix(rx,ry,rz)

            np.savez(
                "project/calibration/instrument_alignment.npz",
                R_correction=R_fix
            )

            print("Corrección guardada")
            break

        elif key == 27:
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()