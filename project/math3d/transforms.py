import numpy as np
import cv2


class Transform:
    """
    Convención:
    T_a_b transforma coordenadas expresadas en b hacia a.
    Vectores columna.
    Composición: T_a_c = T_a_b @ T_b_c
    """

    def __init__(self, matrix: np.ndarray):
        if matrix.shape != (4, 4):
            raise ValueError("Matrix must be 4x4.")
        self._T = matrix.astype(np.float64)

    @staticmethod
    def identity():
        return Transform(np.eye(4, dtype=np.float64))

    @staticmethod
    def from_rvec_tvec(rvec, tvec):
        R, _ = cv2.Rodrigues(rvec)
        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = R
        T[:3, 3] = tvec.reshape(3)
        return Transform(T)

    @staticmethod
    def from_rotation_translation(R: np.ndarray, t: np.ndarray):
        if R.shape != (3, 3):
            raise ValueError("Rotation must be 3x3.")
        if t.shape not in [(3,), (3, 1)]:
            raise ValueError("Translation must be 3D.")

        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = R
        T[:3, 3] = t.reshape(3)
        return Transform(T)

    def inverse(self):
        R = self._T[:3, :3]
        t = self._T[:3, 3]

        R_inv = R.T
        t_inv = -R_inv @ t

        T_inv = np.eye(4, dtype=np.float64)
        T_inv[:3, :3] = R_inv
        T_inv[:3, 3] = t_inv

        return Transform(T_inv)

    def __matmul__(self, other: "Transform"):
        return Transform(self._T @ other._T)

    def rotation(self):
        return self._T[:3, :3].copy()

    def translation(self):
        return self._T[:3, 3].copy()

    def matrix(self):
        return self._T.copy()