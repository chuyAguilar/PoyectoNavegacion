class ReferenceFrame:
    """
    Define un sistema de referencia basado en un marcador base fijo.
    """

    def __init__(self, base_marker_id: int):
        self.base_marker_id = base_marker_id

    def compute_relative_transforms(self, transforms_dict):
        """
        Recibe dict: {marker_id: Transform}
        Devuelve dict con transformaciones relativas al marcador base.
        """

        if self.base_marker_id not in transforms_dict:
            return {}

        T_cam_base = transforms_dict[self.base_marker_id]

        T_base_cam = T_cam_base.inverse()

        relative_transforms = {}

        for marker_id, T_cam_marker in transforms_dict.items():
            T_base_marker = T_base_cam @ T_cam_marker

            relative_transforms[marker_id] = T_base_marker

        return relative_transforms
