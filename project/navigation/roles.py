class MarkerRoles:
    """
    Define el significado semántico de cada ID.
    """

    def __init__(self):
        self.role_map = {
            0: "BASE",
            1: "TOOL",
        }

    def get_role(self, marker_id: int) -> str:
        return self.role_map.get(marker_id, f"ID {marker_id}")

    def get_base_id(self) -> int:
        return 0

    def get_tool_id(self) -> int:
        return 1
