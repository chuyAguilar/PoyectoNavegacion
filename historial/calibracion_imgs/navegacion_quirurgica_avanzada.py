"""
Navegacion 3D con OpenCV + ArUco (Reference + Tool)
- Estima T_cam_ref y T_cam_tool (fusion multi-marcador por rigid body)
- Calcula T_ref_tool = inv(T_cam_ref) @ T_cam_tool
- (Opcional) Envia transform a 3D Slicer via OpenIGTLink

Requisitos:
  pip install opencv-contrib-python numpy
Opcional:
  pip install pyigtl   (si usas esta libreria para OpenIGTLink)
"""

import time
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


# -----------------------------
# Utilidades de transformacion
# -----------------------------
def make_T(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R
    T[:3, 3] = t.reshape(3)
    return T


def inv_T(T: np.ndarray) -> np.ndarray:
    R = T[:3, :3]
    t = T[:3, 3]
    Ti = np.eye(4, dtype=np.float64)
    Ti[:3, :3] = R.T
    Ti[:3, 3] = -R.T @ t
    return Ti


def rodrigues_to_R(rvec: np.ndarray) -> np.ndarray:
    R, _ = cv2.Rodrigues(rvec)
    return R


def R_to_quat_wxyz(R: np.ndarray) -> np.ndarray:
    """Convierte matriz de rotacion a cuaternion (w,x,y,z)."""
    tr = np.trace(R)
    if tr > 0.0:
        S = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * S
        x = (R[2, 1] - R[1, 2]) / S
        y = (R[0, 2] - R[2, 0]) / S
        z = (R[1, 0] - R[0, 1]) / S
    else:
        if (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
            S = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
            w = (R[2, 1] - R[1, 2]) / S
            x = 0.25 * S
            y = (R[0, 1] + R[1, 0]) / S
            z = (R[0, 2] + R[2, 0]) / S
        elif R[1, 1] > R[2, 2]:
            S = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
            w = (R[0, 2] - R[2, 0]) / S
            x = (R[0, 1] + R[1, 0]) / S
            y = 0.25 * S
            z = (R[1, 2] + R[2, 1]) / S
        else:
            S = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
            w = (R[1, 0] - R[0, 1]) / S
            x = (R[0, 2] + R[2, 0]) / S
            y = (R[1, 2] + R[2, 1]) / S
            z = 0.25 * S

    q = np.array([w, x, y, z], dtype=np.float64)
    q = q / np.linalg.norm(q)
    return q


def quat_wxyz_to_R(q: np.ndarray) -> np.ndarray:
    """Cuaternion (w,x,y,z) -> matriz de rotacion 3x3"""
    w, x, y, z = q
    R = np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - z*w),     2*(x*z + y*w)],
        [    2*(x*y + z*w), 1 - 2*(x*x + z*z),     2*(y*z - x*w)],
        [    2*(x*z - y*w),     2*(y*z + x*w), 1 - 2*(x*x + y*y)]
    ], dtype=np.float64)
    return R


def average_quaternions(quats: List[np.ndarray], weights: List[float]) -> np.ndarray:
    """Promedio ponderado de cuaterniones con consistencia de signo."""
    assert len(quats) == len(weights) and len(quats) > 0
    q0 = quats[0]
    acc = np.zeros(4, dtype=np.float64)
    for q, w in zip(quats, weights):
        if np.dot(q, q0) < 0.0:
            q = -q
        acc += w * q
    acc_norm = np.linalg.norm(acc)
    if acc_norm < 1e-12:
        return q0
    return acc / acc_norm


def marker_object_points(marker_size: float) -> np.ndarray:
    """Esquinas 3D del marcador (origen en centro)."""
    s = float(marker_size)
    return np.array([
        [-s/2,  s/2, 0.0],
        [ s/2,  s/2, 0.0],
        [ s/2, -s/2, 0.0],
        [-s/2, -s/2, 0.0],
    ], dtype=np.float64)


# -----------------------------------
# Modelo de rigid body (Ref o Tool)
# -----------------------------------
@dataclass
class RigidBodyModel:
    name: str
    marker_size: float
    # p_body = T_body_marker @ p_marker
    T_body_marker: Dict[int, np.ndarray]


def load_rigid_body_from_json(path: str) -> RigidBodyModel:
    """
    JSON sugerido:
    {
      "name": "REF",
      "marker_size": 20.0,
      "markers": [
        {"id": 1, "T_body_marker": [[...4...],[...],[...],[...]]}
      ]
    }
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    T_map = {}
    for m in data["markers"]:
        mid = int(m["id"])
        T = np.array(m["T_body_marker"], dtype=np.float64)
        assert T.shape == (4, 4)
        T_map[mid] = T
    return RigidBodyModel(name=data["name"], marker_size=float(data["marker_size"]), T_body_marker=T_map)


# -----------------------------------
# Pose estimation + fusion multi-marker
# -----------------------------------
def estimate_marker_pose_pnp(
    corners_2d: np.ndarray,
    marker_size: float,
    K: np.ndarray,
    dist: np.ndarray
) -> Tuple[Optional[np.ndarray], float]:
    """Devuelve T_cam_marker y error reproyeccion RMS (px)."""
    objp = marker_object_points(marker_size)
    imgp = corners_2d.reshape(4, 2).astype(np.float64)

    pnp_flag = cv2.SOLVEPNP_IPPE_SQUARE if hasattr(cv2, "SOLVEPNP_IPPE_SQUARE") else cv2.SOLVEPNP_ITERATIVE
    ok, rvec, tvec = cv2.solvePnP(objp, imgp, K, dist, flags=pnp_flag)
    if not ok:
        return None, float("inf")

    proj, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
    proj = proj.reshape(4, 2)
    err = np.sqrt(np.mean(np.sum((proj - imgp) ** 2, axis=1)))

    R = rodrigues_to_R(rvec)
    T_cam_marker = make_T(R, tvec.reshape(3))
    return T_cam_marker, float(err)


def fuse_rigid_body_pose(
    corners_list: List[np.ndarray],
    ids_list: List[int],
    model: RigidBodyModel,
    K: np.ndarray,
    dist: np.ndarray,
    max_reproj_err_px: float = 2.0
) -> Tuple[Optional[np.ndarray], dict]:
    Ts = []
    weights = []
    errs = []

    for corners_2d, mid in zip(corners_list, ids_list):
        if mid not in model.T_body_marker:
            continue

        T_cam_marker, err = estimate_marker_pose_pnp(corners_2d, model.marker_size, K, dist)
        if T_cam_marker is None:
            continue
        if err > max_reproj_err_px:
            continue

        T_body_marker = model.T_body_marker[mid]
        T_cam_body_i = T_cam_marker @ inv_T(T_body_marker)

        Ts.append(T_cam_body_i)
        errs.append(err)
        weights.append(1.0 / (err * err + 1e-9))

    dbg = {
        "markers_total": float(len(ids_list)),
        "markers_used": float(len(Ts)),
        "mean_err_px": float(np.mean(errs)) if errs else float("inf"),
    }

    if len(Ts) < 1:
        return None, dbg

    W = float(np.sum(weights))
    t = np.sum([w * T[:3, 3] for w, T in zip(weights, Ts)], axis=0) / max(W, 1e-12)

    quats = [R_to_quat_wxyz(T[:3, :3]) for T in Ts]
    q_avg = average_quaternions(quats, weights)
    R_avg = quat_wxyz_to_R(q_avg)

    T_cam_body = make_T(R_avg, t)
    return T_cam_body, dbg


# -----------------------------------
# Pivot calibration
# -----------------------------------
def pivot_calibration(T_ref_tool_list: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """Resuelve p_tip_tool y c_pivot_ref por minimos cuadrados."""
    A_blocks = []
    b_blocks = []
    I = np.eye(3, dtype=np.float64)

    for T in T_ref_tool_list:
        R = T[:3, :3]
        t = T[:3, 3]
        A_blocks.append(np.hstack([R, -I]))
        b_blocks.append((-t).reshape(3, 1))

    A = np.vstack(A_blocks)
    b = np.vstack(b_blocks).reshape(-1)

    x, *_ = np.linalg.lstsq(A, b, rcond=None)
    p_tip_tool = x[:3]
    c_pivot_ref = x[3:]
    return p_tip_tool, c_pivot_ref


# -----------------------------------
# OpenIGTLink sender (opcional)
# -----------------------------------
def send_transform_openigtlink(host: str, port: int, name: str, T_4x4: np.ndarray) -> None:
    try:
        import pyigtl  # type: ignore
    except Exception:
        return

    try:
        client = pyigtl.OpenIGTLinkClient(host=host, port=port)
        client.send_transform(name, T_4x4)
    except Exception:
        pass


# -----------------------------------
# MAIN
# -----------------------------------
def main():
    # Reemplaza con tus intrinsecos reales
    K = np.array([
        [1400.0, 0.0, 960.0],
        [0.0, 1400.0, 540.0],
        [0.0, 0.0, 1.0]
    ], dtype=np.float64)

    dist = np.zeros((5, 1), dtype=np.float64)

    try:
        ref_model = load_rigid_body_from_json("ref_rigidbody.json")
        tool_model = load_rigid_body_from_json("tool_rigidbody.json")
    except FileNotFoundError:
        print("Error: No se encontraron los archivos JSON de configuracion (ref_rigidbody.json, tool_rigidbody.json).")
        return

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir la camara")

    pivot_mode = False
    pivot_samples: List[np.ndarray] = []

    igtl_host = "127.0.0.1"
    igtl_port = 18944
    igtl_name = "REF_TO_TOOL"

    print("Iniciando. Teclas: q=salir, p=toggle pivot mode, c=calcular pivot")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)

        if ids is None or len(ids) == 0:
            cv2.imshow("frame", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        ids_flat = [int(i) for i in ids.flatten()]
        corners_list = [c.reshape(4, 2) for c in corners]

        T_cam_ref, _ = fuse_rigid_body_pose(corners_list, ids_flat, ref_model, K, dist)
        T_cam_tool, _ = fuse_rigid_body_pose(corners_list, ids_flat, tool_model, K, dist)

        cv2.aruco.drawDetectedMarkers(frame, corners, ids)

        if T_cam_ref is not None and T_cam_tool is not None:
            T_ref_tool = inv_T(T_cam_ref) @ T_cam_tool

            if pivot_mode:
                pivot_samples.append(T_ref_tool.copy())

            send_transform_openigtlink(igtl_host, igtl_port, igtl_name, T_ref_tool)
            
            # Mostrar info en pantalla
            cv2.putText(frame, "Tracking: OK", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Mostrar posicion relativa
            pos = T_ref_tool[:3, 3]
            cv2.putText(frame, f"Pos: [{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}]", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        if pivot_mode:
             cv2.putText(frame, f"PIVOT MODE: {len(pivot_samples)} samples", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.imshow("frame", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('p'):
            pivot_mode = not pivot_mode
            print("pivot_mode =", pivot_mode, "(samples:", len(pivot_samples), ")")
        if key == ord('c'):
            if len(pivot_samples) >= 20:
                p_tip_tool, c_pivot_ref = pivot_calibration(pivot_samples)
                print("Pivot calibration:")
                print("  p_tip_tool (mm) =", p_tip_tool)
                print("  c_pivot_ref (mm) =", c_pivot_ref)
            else:
                print("Necesitas >=20 muestras. Actualmente:", len(pivot_samples))

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
