"""El paso por frame del tracker: deteccion -> pose -> filtro, sin camara ni envio.

`MarkerTracker` reune lo que `tracker.main()` construia antes del bucle
(detector, lista blanca, filtros) y lo que hacia por frame con los markers
sueltos (meta 003, fase 4). Lo usan el tracker (`tracker.py`), el replay
(`tests/replay_util.run_marker0_replay`, a traves de `process_corners`) y
`diagnostics.measure_modes` (que antes repetia el bucle, B32).

El orden es el de antes: por cada deteccion, en el orden del detector,
IPPE_SQUARE con z > 0, el 1-Euro de la posicion con el tiempo del frame y la
matriz 4x4. La pose que sale es la que se envia como `<name>ToTracker`.

Meta 006, fase 7d2b (B39, opcion c; P70 b, P72 a): un ID de `markers.list` que
sale dos o mas veces en un frame no se publica ese frame ni alimenta su 1-Euro,
y se cuenta (`frames_con_repetido`, `repetidos_por_id`). Cada ID de la lista es
un objeto fisico unico: dos detecciones son siempre un error y no se sabe cual
es la buena. Los demas IDs del frame se publican. No cubre un fantasma suelto
del ID (sin la referencia a la vista): eso es de la tasa del detector (7d2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Container, Iterable, Mapping

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


def ids_repetidos(ids: Iterable[int], validos: Container[int]) -> set[int]:
    """Los IDs de `validos` que salen dos o mas veces en `ids`; los que no estan
    en `validos` no cuentan."""
    vistos: set[int] = set()
    repetidos: set[int] = set()
    for mid in ids:
        mid = int(mid)
        if mid not in validos:
            continue
        if mid in vistos:
            repetidos.add(mid)
        vistos.add(mid)
    return repetidos


class MarkerTracker:
    """Detector + lista blanca + pose + 1-Euro de los markers de `cfg_markers['list']`.

    `cfg_markers` es la seccion `markers` del perfil (dictionary, detector,
    list); `cfg_filtering`, la seccion `filtering` (enabled, min_cutoff, beta).

    `descartar_repetidos` (True; fase 7d2b de la meta 006): un ID de la lista que
    sale dos o mas veces en un frame no da pose ese frame. Con False queda el
    comportamiento de antes (una pose por deteccion), solo para las pruebas y
    para comparar fuera de linea: el tracker no lo expone. Los contadores
    `frames_con_repetido` (frames con algun ID repetido) y `repetidos_por_id`
    ({id: en cuantos frames salio repetido}) cuentan siempre.
    """

    def __init__(self, cfg_markers: dict, cfg_filtering: dict | None, *,
                 descartar_repetidos: bool = True) -> None:
        self.detector = create_detector(cfg_markers)
        self.markers: dict[int, dict] = {int(m["id"]): m for m in cfg_markers.get("list", []) or []}
        print(f"[Marcadores individuales] IDs: {list(self.markers.keys())}")
        # Lista blanca: solo los IDs que el tracker usa. Todo lo demas (fantasmas de
        # stickers o texturas que el detector permisivo decodifica como IDs ajenos)
        # se descarta justo tras detectar.
        self.valid_ids: set[int] = set(self.markers)
        print(f"[Whitelist] IDs aceptados: {sorted(self.valid_ids)}")
        self.cfg_filtering = dict(cfg_filtering or {})
        self.descartar_repetidos = bool(descartar_repetidos)
        self.filters: dict[int, PositionFilter] = {}
        self.frames_con_repetido = 0
        self.repetidos_por_id: dict[int, int] = {}
        self.reset()
        if self.filters:
            print("[Filtrado] 1-Euro filter activado.")

    def reset(self) -> None:
        """Filtros y contadores de repetidos de cero (el estado que tiene el tracker al arrancar)."""
        self.frames_con_repetido = 0
        self.repetidos_por_id = {}
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
        orden del detector. `t` es el tiempo del frame (segundos) para el 1-Euro.

        Un ID de la lista que viene dos o mas veces en la secuencia no da pose
        en este frame ni toca su 1-Euro (el filtro queda como si el frame no lo
        hubiera visto), y se cuenta; los demas IDs salen como siempre (fase
        7d2b). La primera vez que un ID sale repetido se escribe una linea.
        Con `descartar_repetidos=False` sale una pose por deteccion, como antes.
        """
        items = list(detections.items() if isinstance(detections, Mapping) else detections)
        repetidos = ids_repetidos((mid for mid, _corners in items), self.markers)
        if repetidos:
            self.frames_con_repetido += 1
            for mid in sorted(repetidos):
                if mid not in self.repetidos_por_id:
                    print(f"[Repetidos] ID {mid} dos veces en un frame: "
                          + ("no se publica ese frame (se cuenta; B39)" if self.descartar_repetidos
                             else "se publican las dos (descartar_repetidos=False; se cuenta)"))
                self.repetidos_por_id[mid] = self.repetidos_por_id.get(mid, 0) + 1
        poses: list[MarkerPose] = []
        for mid, corners in items:
            mid = int(mid)
            info = self.markers.get(mid)
            if info is None:
                continue
            if self.descartar_repetidos and mid in repetidos:
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

    def resumen_repetidos(self) -> dict:
        """Los contadores de repetidos como van a los metadatos de la grabacion:
        `{"frames": int, "por_id": {str(id): int}}`."""
        return {"frames": int(self.frames_con_repetido),
                "por_id": {str(mid): int(n) for mid, n in sorted(self.repetidos_por_id.items())}}

    def process(self, gray: np.ndarray, t: float, K, dist) -> list[MarkerPose]:
        """Deteccion + lista blanca + pose + filtro de un frame en gris."""
        corners, ids = self.detect(gray)
        if ids is None or len(ids) == 0:
            return []
        return self.process_corners(zip(ids.flatten().tolist(), corners), t, K, dist)
