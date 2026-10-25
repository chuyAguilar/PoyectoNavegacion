"""Frames sinteticos y falsos para las pruebas del tracker sin camara (meta 003, fases 1 y 4).

pytest no recoge este archivo (no empieza por `test_`).
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

K_SYN = np.array([[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]])
DIST_SYN = np.zeros((1, 5))
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_MIP_36h12)


def render_marker(tz: float, tx: float, marker_id: int = 0, size_mm: float = 80.0,
                  K: np.ndarray = K_SYN, dist: np.ndarray = DIST_SYN,
                  shape: tuple[int, int] = (480, 640), euler_xy=(185.0, 5.0)) -> np.ndarray:
    """Un marker del diccionario del tracker proyectado con `K` a (tx, 5, tz) mm,
    de frente a la camara (giro 185 grados en x y 5 en y), sobre fondo gris. BGR."""
    side, pad = 240, 48
    canvas = np.full((side + 2 * pad, side + 2 * pad), 255, np.uint8)
    canvas[pad:pad + side, pad:pad + side] = cv2.aruco.generateImageMarker(DICT, marker_id, side)
    half = (side / 2 + pad) * size_mm / side
    obj = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]])
    rvec = Rotation.from_euler("xy", list(euler_xy), degrees=True).as_rotvec()
    img_pts, _ = cv2.projectPoints(obj, rvec, np.array([tx, 5.0, tz]), K, dist)
    w = float(side + 2 * pad)
    src = np.array([[0, 0], [w, 0], [w, w], [0, w]], np.float32)
    H = cv2.getPerspectiveTransform(src, img_pts.reshape(4, 2).astype(np.float32))
    gray = cv2.warpPerspective(canvas, H, (shape[1], shape[0]), borderValue=110)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


class FakeCamera:
    """Entrega `frames` en orden; al acabarse lanza KeyboardInterrupt (como Ctrl-C) salvo
    que `loop` sea True (vuelve a empezar). None en la lista cuenta como lectura fallida."""

    def __init__(self, frames: list, loop: bool = False,
                 K: np.ndarray = K_SYN, dist: np.ndarray = DIST_SYN) -> None:
        self.frames, self.i, self.loop = list(frames), 0, loop
        self.K, self.dist = K, dist
        self.opened = self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self):
        if self.i >= len(self.frames):
            if not self.loop:
                raise KeyboardInterrupt
            self.i = 0
        f = self.frames[self.i]
        self.i += 1
        if f is None:
            return None, None, None
        return f, None, 0.0

    def get_intrinsics(self):
        return self.K.copy(), self.dist.copy()

    def close(self) -> None:
        self.closed = True


class FakeSender:
    """Un `transport.igtl.IgtlSender` falso: guarda (nombre, matriz float32), como pyigtl."""
    instances: list["FakeSender"] = []

    def __init__(self, port: int) -> None:
        self.port, self.sent, self.closed = int(port), [], False
        FakeSender.instances.append(self)

    def send(self, device_name: str, matrix) -> None:
        self.sent.append((device_name, np.asarray(matrix, dtype=np.float32)))

    def close(self) -> None:
        self.closed = True
