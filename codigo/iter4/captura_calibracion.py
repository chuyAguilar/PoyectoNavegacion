"""
Captura un dataset de detecciones del dodecaedro para auto-calibracion (K4 iter 4).

Diferencias clave con iter 3:
  - Usa `camera_backend.create_backend()` -> soporta webcam o femtobolt.
  - Para femtobolt guarda profundidad muestreada en CADA esquina de CADA marker
    detectado: array (N_markers_total, 4) en mm. Permite residuales 3D en el BA.
  - Toma los DetectorParameters tuneados desde tracker_config.yaml (misma fuente
    que el tracker, evita inconsistencias entre captura y tracking en vivo).
  - Calibracion intrinseca sale del backend (factory K para femtobolt, archivo
    YAML para webcam).

Salida .npz tiene:
  - frames_data (object, compatible con calibrar_rigid_body iter 3)
  - K, dist, rb_ids
  - timestamps, frame_offsets, marker_ids, corners_2d (tabular sin pickle)
  - corners_depth_mm  [NUEVO en iter 4]  shape (N_markers_total, 4), mm
  - has_depth         [NUEVO en iter 4]  bool, True si backend dio depth en cada frame
  - metadata_json (YAML con versiones, hashes, settings reales)
"""
from __future__ import annotations

import argparse
import hashlib
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import yaml

# Backend abstracto de camara (iter 4)
from camera_backend import create_backend


DEFAULT_DURACION_SEG = 60
DEFAULT_MIN_MARKERS_PER_FRAME = 2
DEFAULT_WARNING_THRESHOLD_FRAMES = 100
DEFAULT_MIN_FRAMES_PER_MARKER = 50
DEFAULT_CAMERA_FAIL_TIMEOUT = 30
DEFAULT_OUTPUT = "iter4/data/captura_ba_femtobolt.npz"
DEFAULT_GEOMETRY_FOR_IDS = "iter4/data/reference_dodecaedro.txt"
DEPTH_SAMPLE_WIN = 3  # ventana NxN para muestrear depth en cada corner (mediana robusta)


def log_info(msg):  print(f"[INFO] {msg}")
def log_warn(msg):  print(f"[WARN] {msg}")
def log_error(msg): print(f"[ERROR] {msg}", file=sys.stderr)
def log_stats(msg): print(f"[STATS] {msg}")


# ============================================================================
# I/O helpers
# ============================================================================

def cargar_config(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_rb_ids(ruta_geometria):
    """Lee los tag_id del archivo reference_dodecaedro*.txt."""
    rb_ids = set()
    with open(ruta_geometria, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            vals = linea.split()
            if len(vals) >= 16:
                rb_ids.add(int(vals[0]))
    return rb_ids


def hash_sha256(ruta):
    if not Path(ruta).exists():
        return "NO_EXISTE"
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ============================================================================
# DetectorParameters (mismo mapeo que tracker.py)
# ============================================================================

_DETECTOR_PARAM_KEYS = {
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


def aplicar_detector_params(params, cfg_det):
    if not cfg_det:
        log_info("DetectorParameters: defaults de OpenCV.")
        return
    log_info("DetectorParameters tuneados:")
    for yaml_key, attr_name in _DETECTOR_PARAM_KEYS.items():
        if yaml_key in cfg_det and hasattr(params, attr_name):
            setattr(params, attr_name, cfg_det[yaml_key])
            print(f"  {attr_name} = {cfg_det[yaml_key]}")


def crear_detector(cfg_markers):
    dict_name = cfg_markers["dictionary"].upper()
    if not hasattr(cv2.aruco, dict_name):
        log_error(f"Diccionario ArUco '{dict_name}' no disponible")
        sys.exit(1)
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    cfg_det = cfg_markers.get("detector", {}) or {}
    if hasattr(cv2.aruco, "ArucoDetector"):
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        aplicar_detector_params(params, cfg_det)
        return cv2.aruco.ArucoDetector(aruco_dict, params), True, aruco_dict, params
    params = cv2.aruco.DetectorParameters_create()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    aplicar_detector_params(params, cfg_det)
    return None, False, aruco_dict, params


# ============================================================================
# Validacion de prerrequisitos
# ============================================================================

def resolver_geometry_path(args_geometry_file, cfg):
    if args_geometry_file:
        return Path(args_geometry_file)
    default_teorico = Path(DEFAULT_GEOMETRY_FOR_IDS)
    if default_teorico.exists():
        return default_teorico
    rigid_bodies = cfg.get("rigid_bodies", [])
    if rigid_bodies:
        return Path(rigid_bodies[0].get("geometry_file", ""))
    return Path("")


def validar_prerrequisitos(cfg, output_path, geometry_path):
    errores = []
    if not geometry_path.exists():
        errores.append(f"Archivo de geometria no existe: {geometry_path}")
    if not cfg.get("rigid_bodies"):
        errores.append("No hay rigid_bodies definidos en la config")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_path, "ab") as f:
            f.write(b"")
    except OSError as e:
        errores.append(f"No se puede escribir en {output_path}: {e}")
    if errores:
        log_error("Prerrequisitos no cumplidos:")
        for e in errores:
            log_error(f"  - {e}")
        sys.exit(1)


# ============================================================================
# Filtros y muestreo de profundidad
# ============================================================================

def filtrar_detecciones(corners_all, ids_all, rb_ids):
    """Devuelve {tag_id: corners(4,2)} solo de markers en rb_ids."""
    detecciones = {}
    if ids_all is None:
        return detecciones
    for i, mid in enumerate(ids_all.flatten().tolist()):
        if mid in rb_ids:
            detecciones[int(mid)] = corners_all[i].reshape(4, 2).copy()
    return detecciones


def muestrear_depth_corners(corners_2d, depth_mm, win=DEPTH_SAMPLE_WIN):
    """Para cada esquina (x, y) toma la mediana de la ventana win*win alrededor
    en depth_mm. Ignora ceros (depth invalido). Devuelve array (4,) en mm o
    0.0 donde no hay informacion.

    Notas:
      - depth_mm se asume alineado a color (D2C del backend).
      - Mediana > promedio porque depth tiene outliers de fondo.
    """
    out = np.zeros(4, dtype=np.float32)
    if depth_mm is None:
        return out
    H, W = depth_mm.shape[:2]
    half = win // 2
    for k in range(4):
        x, y = corners_2d[k]
        xi, yi = int(round(x)), int(round(y))
        x0 = max(0, xi - half); x1 = min(W, xi + half + 1)
        y0 = max(0, yi - half); y1 = min(H, yi + half + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        patch = depth_mm[y0:y1, x0:x1]
        validos = patch[patch > 0]
        if validos.size == 0:
            continue
        out[k] = float(np.median(validos))
    return out


def actualizar_cobertura(cobertura, detecciones):
    for mid in detecciones:
        cobertura[mid] = cobertura.get(mid, 0) + 1


def reportar_cobertura(cobertura, rb_ids, threshold_warn, n_frames_utiles):
    lineas = ["[STATS] Cobertura por marker:"]
    for mid in sorted(rb_ids):
        n = cobertura.get(mid, 0)
        pct = 100.0 * n / max(1, n_frames_utiles)
        if n == 0:
            estado = "ERROR (no detectado)"
        elif n < threshold_warn:
            estado = f"WARN (< {threshold_warn}, BA con alta incertidumbre)"
        else:
            estado = "OK"
        lineas.append(f"  ID {mid}: {n} frames ({pct:.1f}%)  {estado}")
    return lineas


def frames_a_tabular(frames_data):
    """Lista de dicts -> arrays separados sin pickle, incluye corners_depth_mm."""
    timestamps, offsets, mids, corners_list, depth_list = [], [0], [], [], []
    for fd in frames_data:
        timestamps.append(fd["timestamp"])
        for mid, c in fd["detecciones"].items():
            mids.append(int(mid))
            corners_list.append(c)
            d = fd.get("corners_depth_mm", {}).get(mid, np.zeros(4, dtype=np.float32))
            depth_list.append(d)
        offsets.append(len(mids))
    return {
        "timestamps": np.asarray(timestamps, dtype=np.float64),
        "frame_offsets": np.asarray(offsets, dtype=np.int32),
        "marker_ids": np.asarray(mids, dtype=np.int32),
        "corners_2d": (np.asarray(corners_list, dtype=np.float32)
                       if corners_list else np.zeros((0, 4, 2), dtype=np.float32)),
        "corners_depth_mm": (np.asarray(depth_list, dtype=np.float32)
                             if depth_list else np.zeros((0, 4), dtype=np.float32)),
    }


# ============================================================================
# Metadata y guardado
# ============================================================================

def construir_metadata(cfg_path, geom_path, dict_name, backend_info,
                       rb_ids, min_markers, duracion, has_depth,
                       refinement_method="CORNER_REFINE_SUBPIX"):
    return {
        "schema_version": "2.0",  # +1 vs iter 3 por depth
        "script": "iter4/captura_calibracion.py",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "config_path": str(cfg_path),
        "config_sha256": hash_sha256(cfg_path),
        "geometry_path": str(geom_path),
        "geometry_sha256": hash_sha256(geom_path),
        "aruco_dictionary": dict_name,
        "corner_refinement_method": refinement_method,
        "rigid_body_ids": sorted(rb_ids),
        "min_markers_per_frame": min_markers,
        "duracion_seg": duracion,
        "backend": backend_info,
        "has_depth": bool(has_depth),
        "depth_sample_win": DEPTH_SAMPLE_WIN,
    }


def guardar_dataset(output_path, frames_data, K, dist, rb_ids, metadata, tabular):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        frames_data=np.array(frames_data, dtype=object),
        K=K, dist=dist,
        rb_ids=np.asarray(sorted(rb_ids), dtype=np.int32),
        timestamps=tabular["timestamps"],
        frame_offsets=tabular["frame_offsets"],
        marker_ids=tabular["marker_ids"],
        corners_2d=tabular["corners_2d"],
        corners_depth_mm=tabular["corners_depth_mm"],
        metadata_json=np.array(yaml.safe_dump(metadata), dtype=object),
    )


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Captura dataset de detecciones del dodecaedro para BA iter 4 "
                    "(con muestreo de depth si el backend lo provee).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--duracion", type=int, default=DEFAULT_DURACION_SEG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--min-markers-per-frame", type=int, default=DEFAULT_MIN_MARKERS_PER_FRAME)
    parser.add_argument("--warning-threshold", type=int, default=DEFAULT_WARNING_THRESHOLD_FRAMES)
    parser.add_argument("--min-frames-per-marker", type=int, default=DEFAULT_MIN_FRAMES_PER_MARKER)
    parser.add_argument("--camera-fail-timeout", type=int, default=DEFAULT_CAMERA_FAIL_TIMEOUT)
    parser.add_argument("--geometry-file", default=None,
                        help=f"Override del archivo de geometria. Default: {DEFAULT_GEOMETRY_FOR_IDS}.")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    output_path = Path(args.output)

    log_info(f"Config: {cfg_path}")
    cfg = cargar_config(cfg_path)

    geom_path = resolver_geometry_path(args.geometry_file, cfg)
    log_info(f"Archivo de geometria (solo para IDs): {geom_path}")

    validar_prerrequisitos(cfg, output_path, geom_path)

    # === Camara via backend (webcam | femtobolt) ===
    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()
    log_info(f"Backend de camara: {type(cam).__name__}")
    log_info(f"Calibracion intrinseca de backend: K {K.shape}, dist shape {np.asarray(dist).shape}")

    backend_info = {
        "type": type(cam).__name__,
        "config": dict(cfg["camera"]),
    }

    dict_name = cfg["markers"]["dictionary"]
    detector, usar_api_nueva, aruco_dict, params = crear_detector(cfg["markers"])
    log_info(f"Detector ArUco: {dict_name}, refinement=SUBPIX")

    rb_ids = cargar_rb_ids(geom_path)
    log_info(f"Rigid body IDs ({len(rb_ids)}): {sorted(rb_ids)}")

    print()
    log_info("INSTRUCCIONES:")
    log_info("  1. Dodecaedro a 50-70 cm de la camara (enfoque fijo Femto Bolt: 0.5-5 m).")
    log_info("  2. Rota lentamente mostrando TODAS las caras.")
    log_info("  3. Vari las combinaciones de markers visibles.")
    log_info("  4. Buena iluminacion, sin reflejos.")
    log_info("  5. 'q' en la ventana para salir antes.")
    log_info(f"Duracion: {args.duracion}s. Comenzando en 3 segundos...")
    time.sleep(3)
    log_info("CAPTURANDO!")

    frames_data = []
    cobertura = {mid: 0 for mid in rb_ids}
    t_inicio = time.time()
    n_frames = 0
    n_utiles = 0
    n_con_depth = 0
    fallos = 0
    last_print = t_inicio

    try:
        while True:
            t_now = time.time()
            if t_now - t_inicio > args.duracion:
                break
            frame, depth_mm, ts = cam.read()
            if frame is None:
                fallos += 1
                if fallos > args.camera_fail_timeout:
                    log_error(f"{fallos} frames fallidos consecutivos. Abortando.")
                    break
                continue
            fallos = 0
            n_frames += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if usar_api_nueva:
                corners_all, ids_all, _ = detector.detectMarkers(gray)
            else:
                corners_all, ids_all, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)

            detecciones = filtrar_detecciones(corners_all, ids_all, rb_ids)

            if len(detecciones) >= args.min_markers_per_frame:
                # Muestrear depth en los 4 corners de cada marker detectado
                corners_depth = {}
                if depth_mm is not None:
                    n_con_depth += 1
                    for mid, c in detecciones.items():
                        corners_depth[mid] = muestrear_depth_corners(c, depth_mm)
                frames_data.append({
                    "timestamp": t_now - t_inicio,
                    "detecciones": detecciones,
                    "corners_depth_mm": corners_depth,
                })
                actualizar_cobertura(cobertura, detecciones)
                n_utiles += 1

            display = frame.copy()
            if ids_all is not None:
                cv2.aruco.drawDetectedMarkers(display, corners_all, ids_all)
            elapsed = t_now - t_inicio
            depth_tag = "+depth" if depth_mm is not None else ""
            cv2.putText(display,
                        f"Frame {n_frames} | {len(detecciones)} markers | Cap: {n_utiles} {depth_tag}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(display, f"Tiempo: {elapsed:.1f}s / {args.duracion}s",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)


            y = 30
            cv2.putText(display, "Cobertura:", (display.shape[1] - 180, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            for mid in sorted(rb_ids):
                y += 18
                n = cobertura.get(mid, 0)
                color = (0, 0, 255) if n == 0 else ((0, 200, 255) if n < args.min_frames_per_marker else (0, 255, 0))
                cv2.putText(display, f"ID {mid}: {n}",
                            (display.shape[1] - 180, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            cv2.imshow("Captura calibracion iter4 - q para salir antes", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                log_info("Salida solicitada por usuario.")
                break

            if t_now - last_print > 5.0:
                pct_depth = 100.0 * n_con_depth / max(1, n_utiles)
                log_info(f"  [{elapsed:.0f}s] {n_utiles} utiles, {n_frames} totales, "
                         f"{pct_depth:.0f}% con depth")
                last_print = t_now
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print()
    log_stats(f"Frames totales: {n_frames}")
    log_stats(f"Frames utiles: {n_utiles}")
    log_stats(f"Frames con depth valido: {n_con_depth} "
              f"({100.0*n_con_depth/max(1,n_utiles):.1f}%)")

    if n_utiles < args.warning_threshold:
        log_warn(f"Pocos frames utiles. Considera repetir o aumentar --duracion.")

    for linea in reportar_cobertura(cobertura, rb_ids, args.min_frames_per_marker, n_utiles):
        print(linea)

    # Pares observados (info adicional para diagnosticar conectividad del grafo del BA)
    pares = {}
    for fd in frames_data:
        ids_v = sorted(fd["detecciones"].keys())
        for i in range(len(ids_v)):
            for j in range(i + 1, len(ids_v)):
                par = (ids_v[i], ids_v[j])
                pares[par] = pares.get(par, 0) + 1
    pares_sorted = sorted(pares.items(), key=lambda x: -x[1])
    log_stats(f"Pares unicos: {len(pares_sorted)}")
    if pares_sorted:
        log_stats(f"  Mas frecuente: {pares_sorted[0][0]} ({pares_sorted[0][1]})")
        log_stats(f"  Menos frecuente: {pares_sorted[-1][0]} ({pares_sorted[-1][1]})")

    has_depth = (n_con_depth > 0)
    metadata = construir_metadata(
        cfg_path=cfg_path, geom_path=geom_path, dict_name=dict_name,
        backend_info=backend_info, rb_ids=rb_ids,
        min_markers=args.min_markers_per_frame, duracion=args.duracion,
        has_depth=has_depth,
    )
    tabular = frames_a_tabular(frames_data)
    guardar_dataset(output_path, frames_data, K, dist, rb_ids, metadata, tabular)
    log_info(f"Guardado: {output_path} ({n_utiles} frames utiles, has_depth={has_depth})")


if __name__ == "__main__":
    main()
