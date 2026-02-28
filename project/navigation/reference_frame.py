from math3d.transforms import Transform


class ReferenceFrame:
    """
    Maneja la conversión de transformaciones al sistema de referencia base.

    Convención:
    T_a_b transforma coordenadas expresadas en b hacia a.
    """

    def __init__(self, base_marker_id: int):
        self.base_marker_id = base_marker_id

    def compute_base_transform(self, transforms_cam: dict) -> dict:
        """
        transforms_cam:
            dict { marker_id: Transform }
            Cada Transform es T_cam_marker

        Retorna:
            dict { marker_id: Transform }
            Cada Transform es T_base_marker
        """

        if self.base_marker_id not in transforms_cam:
            return {}

        T_cam_base = transforms_cam[self.base_marker_id]
        T_base_cam = T_cam_base.inverse()

        transforms_base = {}

        for marker_id, T_cam_marker in transforms_cam.items():
            T_base_marker = T_base_cam @ T_cam_marker
            transforms_base[marker_id] = T_base_marker

        return transforms_base