"""Deteccion ArUco: diccionario, parametros del detector y la lista blanca de IDs.

Era la parte de deteccion de `tracker.py` (meta 003, fase 4). `create_detector`
construye el `cv2.aruco.ArucoDetector` como lo hacia `tracker.main()`:
`CORNER_REFINE_SUBPIX` y los parametros de `markers.detector` del perfil
(`apply_detector_params`, el mismo mapeo YAML -> atributo). La rama de la API
vieja (`cv2.aruco.detectMarkers` sin `ArucoDetector`) se quita: OpenCV >= 4.7
siempre la tiene.

`detect` detecta y aplica la lista blanca: todo ID que no sea de un marker del
perfil (fantasmas de stickers o texturas) se descarta justo tras detectar, sin
tocar los DetectorParameters.

Context7 (2026-10-24, OpenCV 4.13; instalado 4.11): `ArucoDetector.detectMarkers`
devuelve `corners` (N arrays 1x4x2, esquinas en sentido horario desde la
superior izquierda) e `ids` (N x 1) en el mismo orden; no corrige la distorsion.
"""
from __future__ import annotations

import cv2
import numpy as np

# Claves YAML snake_case -> atributos de cv2.aruco.DetectorParameters camelCase.
# Solo los que tunear cambia algo real para nuestro caso (markers chicos,
# angulos grazing, iluminacion variable). El resto deja sus defaults.
DETECTOR_PARAM_KEYS = {
    "adaptive_thresh_win_size_min": "adaptiveThreshWinSizeMin",
    "adaptive_thresh_win_size_max": "adaptiveThreshWinSizeMax",
    "adaptive_thresh_win_size_step": "adaptiveThreshWinSizeStep",
    "adaptive_thresh_constant": "adaptiveThreshConstant",
    "min_marker_perimeter_rate": "minMarkerPerimeterRate",
    "max_marker_perimeter_rate": "maxMarkerPerimeterRate",
    "polygonal_approx_accuracy_rate": "polygonalApproxAccuracyRate",
    "min_corner_distance_rate": "minCornerDistanceRate",
    "min_distance_to_border": "minDistanceToBorder",
    "max_erroneous_bits_in_border_rate": "maxErroneousBitsInBorderRate",
    "error_correction_rate": "errorCorrectionRate",
    "corner_refinement_win_size": "cornerRefinementWinSize",
    "corner_refinement_max_iterations": "cornerRefinementMaxIterations",
    "corner_refinement_min_accuracy": "cornerRefinementMinAccuracy",
}


def get_dictionary(name: str):
    """El diccionario ArUco predefinido de nombre `name` (p. ej. DICT_ARUCO_MIP_36h12)."""
    name = name.upper()
    if not hasattr(cv2.aruco, name):
        available = [x for x in dir(cv2.aruco) if "DICT" in x]
        raise ValueError(f"Diccionario '{name}' no disponible.\nDisponibles: {available}")
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def apply_detector_params(params, cfg_det: dict | None) -> None:
    """Sobreescribe atributos de `params` (DetectorParameters) segun `cfg_det`.

    `cfg_det` son las claves bajo `markers.detector` del perfil. Si una clave no
    esta, queda el default. Imprime cada valor aplicado.
    """
    if not cfg_det:
        print("[Detector] Usando DetectorParameters por defecto.")
        return
    print("[Detector] Tuning DetectorParameters:")
    for yaml_key, attr_name in DETECTOR_PARAM_KEYS.items():
        if yaml_key in cfg_det:
            value = cfg_det[yaml_key]
            if hasattr(params, attr_name):
                setattr(params, attr_name, value)
                print(f"  {attr_name} = {value}")
            else:
                print(f"  [WARN] DetectorParameters no tiene atributo {attr_name}, ignorado.")


def create_detector(cfg_markers: dict):
    """El `ArucoDetector` del tracker: diccionario de `cfg_markers['dictionary']`,
    refinamiento SUBPIX y los parametros de `cfg_markers['detector']`."""
    dictionary = get_dictionary(cfg_markers["dictionary"])
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    apply_detector_params(params, cfg_markers.get("detector", {}) or {})
    return cv2.aruco.ArucoDetector(dictionary, params)


def detect(detector, gray: np.ndarray, valid_ids: set[int]) -> tuple[tuple, np.ndarray | None]:
    """Detecta en `gray` y descarta los IDs que no estan en `valid_ids`.

    Devuelve `(corners, ids)` como los da el detector (tupla de arrays 1x4x2 e
    ids N x 1), ya filtrados; `ids` es None si no queda ninguno.
    """
    corners, ids, _rejected = detector.detectMarkers(gray)
    if ids is not None and len(ids) > 0:
        keep = [i for i, mid in enumerate(ids.flatten().tolist()) if int(mid) in valid_ids]
        if len(keep) < len(ids):
            corners = tuple(corners[i] for i in keep)
            ids = ids[keep] if keep else None
    return corners, ids
