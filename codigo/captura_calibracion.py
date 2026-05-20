"""
Captura un dataset de detecciones del dodecaedro para auto-calibracion (Etapa C).

Por default los IDs del rigid body se leen de data/reference_dodecaedro.txt
(el teorico generado en Etapa B). Override con --geometry-file.

Salida .npz tiene:
  - frames_data (object, compatible con Etapa D)
  - K, dist, rb_ids
  - timestamps, frame_offsets, marker_ids, corners_2d (tabular, sin pickle)
  - metadata_json (YAML con versiones, hashes, settings reales de camara)

Auditoria: documentos/auditoria_iter2/03b_auditoria_captura_calibracion.md
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


DEFAULT_DURACION_SEG = 60
DEFAULT_MIN_MARKERS_PER_FRAME = 2
DEFAULT_WARNING_THRESHOLD_FRAMES = 100
DEFAULT_MIN_FRAMES_PER_MARKER = 50
DEFAULT_CAMERA_FAIL_TIMEOUT = 30
DEFAULT_OUTPUT = "capturas_calibracion.npz"
DEFAULT_GEOMETRY_FOR_IDS = "data/reference_dodecaedro.txt"


def log_info(msg):  print(f"[INFO] {msg}")
def log_warn(msg):  print(f"[WARN] {msg}")
def log_error(msg): print(f"[ERROR] {msg}", file=sys.stderr)
def log_stats(msg): print(f"[STATS] {msg}")


# --- I/O helpers ---

def cargar_config(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_calibracion(ruta):
    """Lee K, dist del YAML de OpenCV."""
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"No se pudo abrir calibracion: {ruta}")
    K_node = fs.getNode("camera_matrix")
    dist_node = fs.getNode("distortion_coefficients")
    if K_node.empty():
        raise ValueError(f"'{ruta}' no contiene 'camera_matrix'")
    if dist_node.empty():
        raise ValueError(f"'{ruta}' no contiene 'distortion_coefficients'")
    K = K_node.mat()
    dist = dist_node.mat()
    fs.release()
    return K, dist


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
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def fourcc_int_a_str(fourcc_int):
    return "".join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4))


# --- Validacion de prerrequisitos ---

def resolver_geometry_path(args_geometry_file, cfg):
    """Decide que archivo de geometria usar para leer los rb_ids.

    Prioridad:
      1. --geometry-file si se paso.
      2. data/reference_dodecaedro.txt si existe (preferencia para Etapa C).
      3. El geometry_file del config (fallback).
    """
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
    calib_path = Path(cfg["camera"]["calibration_file"])
    if not calib_path.exists():
        errores.append(f"Calibracion intrinseca no existe: {calib_path}")
    if not geometry_path.exists():
        errores.append(f"Archivo de geometria no existe: {geometry_path}")
        # Sugerencia: revisa si esta el teorico
        teorico = Path(DEFAULT_GEOMETRY_FOR_IDS)
        if teorico.exists() and teorico != geometry_path:
            log_info(f"Sugerencia: el teorico {teorico} existe; "
                     f"podes correr con --geometry-file {teorico}")
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


# --- Camara ---

def abrir_camara(cam_cfg):
    backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
    backend_name = cam_cfg.get("backend", "MSMF").upper()
    backend = backends.get(backend_name, cv2.CAP_MSMF)
    cap = cv2.VideoCapture(int(cam_cfg["source"]), backend)
    if not cap.isOpened():
        log_error(f"No se pudo abrir la camara source={cam_cfg['source']} backend={backend_name}")
        sys.exit(1)
    fourcc_str = cam_cfg.get("fourcc", "MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc_str))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg["height"])
    cap.set(cv2.CAP_PROP_FPS, cam_cfg.get("fps", 30))
    info = {
        "backend_solicitado": backend_name, "fourcc_solicitado": fourcc_str,
        "width_solicitado": cam_cfg["width"], "height_solicitado": cam_cfg["height"],
        "fps_solicitado": cam_cfg.get("fps", 30),
        "width_real": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height_real": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps_real": float(cap.get(cv2.CAP_PROP_FPS)),
        "fourcc_real": fourcc_int_a_str(int(cap.get(cv2.CAP_PROP_FOURCC))),
    }
    log_info(f"Camara: {info['width_real']}x{info['height_real']} @ "
             f"{info['fps_real']:.1f} FPS, FOURCC={info['fourcc_real']}, backend={backend_name}")
    if (info["width_real"], info["height_real"]) != (info["width_solicitado"], info["height_solicitado"]):
        log_warn(f"Resolucion real difiere de la solicitada. "
                 f"VERIFICAR calibracion intrinseca.")
    if info["fourcc_real"] != info["fourcc_solicitado"]:
        log_warn(f"FOURCC real '{info['fourcc_real']}' difiere del solicitado.")
    return cap, info


def crear_detector(dict_name):
    dict_name = dict_name.upper()
    if not hasattr(cv2.aruco, dict_name):
        log_error(f"Diccionario ArUco '{dict_name}' no disponible")
        sys.exit(1)
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    if hasattr(cv2.aruco, "ArucoDetector"):
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        return cv2.aruco.ArucoDetector(aruco_dict, params), True, aruco_dict, params
    params = cv2.aruco.DetectorParameters_create()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return None, False, aruco_dict, params


# --- Deteccion, filtros, cobertura ---

def filtrar_detecciones(corners_all, ids_all, rb_ids):
    """Devuelve {tag_id: corners(4,2)} solo de markers en rb_ids."""
    detecciones = {}
    if ids_all is None:
        return detecciones
    for i, mid in enumerate(ids_all.flatten().tolist()):
        if mid in rb_ids:
            detecciones[int(mid)] = corners_all[i].reshape(4, 2).copy()
    return detecciones


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
    """Convierte lista de dicts a arrays separados sin pickle."""
    timestamps, offsets, mids, corners_list = [], [0], [], []
    for fd in frames_data:
        timestamps.append(fd["timestamp"])
        for mid, c in fd["detecciones"].items():
            mids.append(int(mid))
            corners_list.append(c)
        offsets.append(len(mids))
    return {
        "timestamps": np.asarray(timestamps, dtype=np.float64),
        "frame_offsets": np.asarray(offsets, dtype=np.int32),
        "marker_ids": np.asarray(mids, dtype=np.int32),
        "corners_2d": (np.asarray(corners_list, dtype=np.float32)
                       if corners_list else np.zeros((0, 4, 2), dtype=np.float32)),
    }


# --- Metadata y guardado ---

def construir_metadata(cfg_path, calib_path, geom_path, dict_name, cam_info,
                       rb_ids, min_markers, duracion,
                       refinement_method="CORNER_REFINE_SUBPIX"):
    return {
        "schema_version": "1.0",
        "script": "captura_calibracion.py",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "config_path": str(cfg_path),
        "config_sha256": hash_sha256(cfg_path),
        "calibration_path": str(calib_path),
        "calibration_sha256": hash_sha256(calib_path),
        "geometry_path": str(geom_path),
        "geometry_sha256": hash_sha256(geom_path),
        "aruco_dictionary": dict_name,
        "corner_refinement_method": refinement_method,
        "rigid_body_ids": sorted(rb_ids),
        "min_markers_per_frame": min_markers,
        "duracion_seg": duracion,
        "camera": cam_info,
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
        metadata_json=np.array(yaml.safe_dump(metadata), dtype=object),
    )


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Captura dataset de detecciones del dodecaedro para bundle adjustment.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default="tracker_config.yaml")
    parser.add_argument("--duracion", type=int, default=DEFAULT_DURACION_SEG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--min-markers-per-frame", type=int, default=DEFAULT_MIN_MARKERS_PER_FRAME)
    parser.add_argument("--warning-threshold", type=int, default=DEFAULT_WARNING_THRESHOLD_FRAMES)
    parser.add_argument("--min-frames-per-marker", type=int, default=DEFAULT_MIN_FRAMES_PER_MARKER)
    parser.add_argument("--camera-fail-timeout", type=int, default=DEFAULT_CAMERA_FAIL_TIMEOUT)
    parser.add_argument("--geometry-file", default=None,
                        help=f"Override del archivo de geometria para leer IDs. "
                             f"Default: {DEFAULT_GEOMETRY_FOR_IDS}.")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    output_path = Path(args.output)

    log_info(f"Config: {cfg_path}")
    cfg = cargar_config(cfg_path)

    geom_path = resolver_geometry_path(args.geometry_file, cfg)
    log_info(f"Archivo de geometria (solo para IDs): {geom_path}")

    validar_prerrequisitos(cfg, output_path, geom_path)

    K, dist = cargar_calibracion(Path(cfg["camera"]["calibration_file"]))
    log_info(f"Calibracion intrinseca cargada (K {K.shape}, dist {dist.shape})")

    dict_name = cfg["markers"]["dictionary"]
    detector, usar_api_nueva, aruco_dict, params = crear_detector(dict_name)
    log_info(f"Detector ArUco: {dict_name}, refinement=SUBPIX")

    rb_ids = cargar_rb_ids(geom_path)
    log_info(f"Rigid body IDs ({len(rb_ids)}): {sorted(rb_ids)}")

    cap, cam_info = abrir_camara(cfg["camera"])

    print()
    log_info("INSTRUCCIONES:")
    log_info("  1. Dodecaedro a 30-50 cm de la camara.")
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
    fallos = 0
    last_print = t_inicio

    while True:
        t_now = time.time()
        if t_now - t_inicio > args.duracion:
            break
        ret, frame = cap.read()
        if not ret:
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
            frames_data.append({"timestamp": t_now - t_inicio, "detecciones": detecciones})
            actualizar_cobertura(cobertura, detecciones)
            n_utiles += 1

        display = frame.copy()
        if ids_all is not None:
            cv2.aruco.drawDetectedMarkers(display, corners_all, ids_all)
        elapsed = t_now - t_inicio
        cv2.putText(display,
                    f"Frame {n_frames} | {len(detecciones)} markers | Cap: {n_utiles}",
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

        cv2.imshow("Captura calibracion - q para salir antes", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            log_info("Salida solicitada por usuario.")
            break

        if t_now - last_print > 5.0:
            log_info(f"  [{elapsed:.0f}s] {n_utiles} utiles, {n_frames} totales")
            last_print = t_now

    cap.release()
    cv2.destroyAllWindows()

    print()
    log_stats(f"Frames totales: {n_frames}")
    log_stats(f"Frames utiles: {n_utiles}")

    if n_utiles < args.warning_threshold:
        log_warn(f"Pocos frames utiles. Considera repetir o aumentar --duracion.")

    for linea in reportar_cobertura(cobertura, rb_ids, args.min_frames_per_marker, n_utiles):
        print(linea)

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

    metadata = construir_metadata(
        cfg_path=cfg_path,
        calib_path=Path(cfg["camera"]["calibration_file"]),
        geom_path=geom_path,
        dict_name=dict_name, cam_info=cam_info, rb_ids=rb_ids,
        min_markers=args.min_markers_per_frame, duracion=args.duracion,
    )
    tabular = frames_a_tabular(frames_data)
    guardar_dataset(output_path, frames_data, K, dist, rb_ids, metadata, tabular)
    log_info(f"Guardado: {output_path} ({n_utiles} frames utiles)")


if __name__ == "__main__":
    main()
