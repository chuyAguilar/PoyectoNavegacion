"""El paso por frame del tracker: deteccion -> pose -> filtro, sin camara ni envio.

`MarkerTracker` reune lo que `tracker.main()` construia antes del bucle
(detector, lista blanca, filtros) y lo que hacia por frame con los markers
sueltos (meta 003, fase 4). Lo usan el tracker (`tracker.py`), el replay
(`tests/replay_util.run_marker0_replay`, a traves de `process_corners`) y
`diagnostics.measure_modes` (que antes repetia el bucle, B32).

El orden es el de antes: por cada deteccion, en el orden del detector,
IPPE_SQUARE con z > 0, el 1-Euro de la posicion con el tiempo del frame y la
matriz 4x4. La pose que sale es la que se envia como `<name>ToTracker`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np

from vision.detection import create_detector, detect
from vision.filtering import PositionFilter
from vision.pose import estimate_single_pose, rvec_tvec_to_matrix


@dataclass
class MarkerPose:
    """La pose de un marker en un frame: lo que se envia y lo que se dibuja."""
    id: int
    name: str
    size_mm: float
    rvec: np.ndarray        # 3x1, sin filtrar (la orientacion no se filtra)
    tvec: np.ndarray        # 3x1, filtrada si el filtro esta activo
    matrix: np.ndarray      # 4x4 float64 = rvec_tvec_to_matrix(rvec, tvec)
    corners: np.ndarray     # las esquinas 2D con que se estimo


class MarkerTracker:
    """Detector + lista blanca + pose + 1-Euro de los markers de `cfg_markers['list']`.

    `cfg_markers` es la seccion `markers` del perfil (dictionary, detector,
    list); `cfg_filtering`, la seccion `filtering` (enabled, min_cutoff, beta).
    """

    def __init__(self, cfg_markers: dict, cfg_filtering: dict | None) -> None:
        self.detector = create_detector(cfg_markers)
        self.markers: dict[int, dict] = {int(m["id"]): m for m in cfg_markers.get("list", []) or []}
        print(f"[Marcadores individuales] IDs: {list(self.markers.keys())}")
        # Lista blanca: solo los IDs que el tracker usa. Todo lo demas (fantasmas de
        # stickers o texturas que el detector permisivo decodifica como IDs ajenos)
        # se descarta justo tras detectar.
        self.valid_ids: set[int] = set(self.markers)
        print(f"[Whitelist] IDs aceptados: {sorted(self.valid_ids)}")
        self.cfg_filtering = dict(cfg_filtering or {})
        self.filters: dict[int, PositionFilter] = {}
        self.reset()
        if self.filters:
            print("[Filtrado] 1-Euro filter activado.")

    def reset(self) -> None:
        """Filtros de cero (el estado que tiene el tracker al arrancar)."""
        self.filters = {}
        if self.cfg_filtering.get("enabled"):
            for mid in self.markers:
                self.filters[mid] = PositionFilter(self.cfg_filtering["min_cutoff"],
                                                   self.cfg_filtering["beta"])

    def detect(self, gray: np.ndarray) -> tuple[tuple, np.ndarray | None]:
        """`(corners, ids)` del frame en gris, ya con la lista blanca aplicada."""
        return detect(self.detector, gray, self.valid_ids)

    def process_corners(self, detections: Mapping[int, np.ndarray] | Iterable[tuple[int, np.ndarray]],
                        t: float, K, dist) -> list[MarkerPose]:
        """Pose y filtro de las detecciones ya hechas, en su orden.

        `detections`: {id: esquinas} o una secuencia de (id, esquinas), con las
        esquinas como las da el detector (1x4x2 o 4x2). La secuencia conserva el
        orden del detector y admite dos detecciones del mismo ID, como el bucle
        de antes. `t` es el tiempo del frame (segundos) para el 1-Euro.
        """
        items = detections.items() if isinstance(detections, Mapping) else detections
        poses: list[MarkerPose] = []
        for mid, corners in items:
            mid = int(mid)
            info = self.markers.get(mid)
            if info is None:
                continue
            size_mm = info["size_mm"]
            pose = estimate_single_pose(corners, size_mm, K, dist)
            if pose is None:
                continue
            rvec, tvec = pose
            f = self.filters.get(mid)
            if f is not None:
                tvec = f.filter(tvec, t)
            poses.append(MarkerPose(id=mid, name=str(info["name"]), size_mm=size_mm,
                                    rvec=rvec, tvec=tvec,
                                    matrix=rvec_tvec_to_matrix(rvec, tvec),
                                    corners=np.asarray(corners)))
        return poses

    def process(self, gray: np.ndarray, t: float, K, dist) -> list[MarkerPose]:
        """Deteccion + lista blanca + pose + filtro de un frame en gris."""
        corners, ids = self.detect(gray)
        if ids is None or len(ids) == 0:
            return []
        return self.process_corners(zip(ids.flatten().tolist(), corners), t, K, dist)
