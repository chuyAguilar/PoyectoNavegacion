import cv2
import numpy as np
import trimesh

from project.camera.camera import Camera
from project.tracking.aruco_tracker import ArucoTracker
from pathlib import Path



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


def project_mesh(frame, vertices, faces, rvec, tvec, camera_matrix, dist):

    pts,_ = cv2.projectPoints(vertices, rvec, tvec, camera_matrix, dist)
    pts = pts.reshape(-1,2).astype(int)

    for face in faces:
        poly = pts[face]
        cv2.polylines(frame,[poly],True,(0,255,0),1)


def main():

    print("Alineación STL interactiva")
    print("Q/A -> rotar X")
    print("W/S -> rotar Y")
    print("E/D -> rotar Z")
    print("ENTER -> guardar")

    camera = Camera(index=0,width=1920,height=1080)

    calib = np.load("project/calibration/calibration.npz")
    camera_matrix = calib["mtx"]
    dist = calib["dist"]

    tracker = ArucoTracker(
        marker_length=0.045,
        camera_matrix=camera_matrix,
        dist_coeffs=dist
    )

    BASE_DIR = Path(__file__).resolve().parent.parent
    stl_path = BASE_DIR / "utilities" / "models" / "lezna.stl"
    print("Cargando STL desde:", stl_path)
    mesh = trimesh.load(stl_path)

    vertices = mesh.vertices.copy()
    faces = mesh.faces

    rx = ry = rz = 0
    step = np.deg2rad(1)

    while True:

        frame = camera.read()

        corners, ids, _ = cv2.aruco.detectMarkers(frame,tracker.aruco_dict)

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame,corners,ids)

        if ids is not None and 10 in ids.flatten():

            rvecs,tvecs,_ = cv2.aruco.estimatePoseSingleMarkers(
                corners,
                tracker.marker_length,
                camera_matrix,
                dist
            )

            idx = np.where(ids.flatten()==10)[0][0]

            rvec = rvecs[idx]
            tvec = tvecs[idx]

            R_manual = rotation_matrix(rx,ry,rz)

            verts = vertices @ R_manual.T

            project_mesh(frame,verts,faces,rvec,tvec,camera_matrix,dist)

        cv2.imshow("STL Alignment",frame)

        key = cv2.waitKey(1)

        if key==ord('q'): rx+=step
        elif key==ord('a'): rx-=step
        elif key==ord('w'): ry+=step
        elif key==ord('s'): ry-=step
        elif key==ord('e'): rz+=step
        elif key==ord('d'): rz-=step

        elif key==13:

            R_fix = rotation_matrix(rx,ry,rz)

            np.savez(
                "project/calibration/instrument_alignment.npz",
                R_correction=R_fix
            )

            print("Corrección guardada")

            break

        elif key==27:
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()