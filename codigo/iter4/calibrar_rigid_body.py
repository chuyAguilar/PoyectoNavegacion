"""
Auto-calibracion del rigid body (dodecaedro) por bundle adjustment - ITER 4.

Cambio matematico clave vs iter 3:
  Minimiza residuos 2D + 3D conjuntamente.
    - r_2d = (proyectar(P_dodec, pose_frame, K) - obs_pixel) / sigma_2d
    - r_3d = (z_predicho - depth_observado) / sigma_3d   (solo donde depth>0)
  El depth se muestrea en cada esquina detectada al momento de la captura
  (corners_depth_mm en el .npz de iter4/captura_calibracion.py).

Por que: en iter 3, el BA puede equivocarse en la escala global (depth) porque
solo tiene info 2D. El Femto Bolt da depth absoluto en mm con sigma ~5 mm.
Combinar ambas fuentes da convergencia mas robusta y geometria con escala fija.

Defaults sigma:
  sigma_2d = 1.0 px  (ArUco subpix, valor canonico)
  sigma_3d = 5.0 mm  (medido empiricamente con medir_sigma_depth.py, ver memoria
                     'sigma-depth-femtobolt-empirico')

Compatible con datasets de iter 3 (sin depth): si has_depth=False en el .npz,
se desactivan los residuos 3D automaticamente y el BA opera como iter 3.
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
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation


# ============================================================================
# Defaults iter 4
# ============================================================================

DEFAULT_INPUT = "iter4/data/captura_ba_femtobolt.npz"
DEFAULT_TEORICO = "iter4/data/reference_dodecaedro.txt"
DEFAULT_OUTPUT = "iter4/data/reference_dodecaedro_calibrado.txt"
DEFAULT_ANCLA = 170                # TOP marker en iter 4 (antes 151)
DEFAULT_MARKER_MM = 13.4           # nuevo tamano fisico iter 4 (antes 16)
DEFAULT_SIGMA_2D = 1.0             # px, ArUco SUBPIX
DEFAULT_SIGMA_3D = 5.0             # mm, Femto Bolt @ 0.5-1m
DEFAULT_HUBER_F_SCALE = 2.0
DEFAULT_MAX_NFEV = 200
DEFAULT_MIN_FRAMES_VALIDOS = 50


def log_info(msg):  print(f"[INFO] {msg}")
def log_warn(msg):  print(f"[WARN] {msg}")
def log_error(msg): print(f"[ERROR] {msg}", file=sys.stderr)
def log_stats(msg): print(f"[STATS] {msg}")


# ============================================================================
# I/O helpers
# ============================================================================

def hash_sha256(ruta):
    if not Path(ruta).exists():
        return "NO_EXISTE"
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def cargar_referencia(ruta):
    """Carga reference.txt. Devuelve dict {tag_id: 4x3 esquinas}."""
    geom = {}
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            vals = linea.split()
            if len(vals) < 16:
                continue
            tag_id = int(vals[0])
            geom[tag_id] = np.array([
                [float(vals[4]),  float(vals[5]),  float(vals[6])],
                [float(vals[7]),  float(vals[8]),  float(vals[9])],
                [float(vals[10]), float(vals[11]), float(vals[12])],
                [float(vals[13]), float(vals[14]), float(vals[15])],
            ])
    return geom


def cargar_dataset(npz_path):
    """Carga el .npz de captura_calibracion (iter 3 o iter 4).

    Devuelve (frames_data, K, dist, rb_ids, has_depth).

    frames_data: lista de dicts con 'timestamp', 'detecciones'={mid: (4,2)},
                 y opcionalmente 'corners_depth_mm'={mid: (4,)} si has_depth.
    """
    data = np.load(npz_path, allow_pickle=True)
    frames_data = list(data["frames_data"])
    K = data["K"]
    dist = data["dist"]
    rb_ids = set(int(x) for x in data["rb_ids"])

    # Detectar si el dataset tiene depth (iter 4 schema_version 2.0)
    has_depth = False
    try:
        import yaml
        meta = yaml.safe_load(str(data["metadata_json"]))
        has_depth = bool(meta.get("has_depth", False))
    except Exception:
        # Fallback: chequear si los frames ya traen 'corners_depth_mm' poblado
        for fd in frames_data[:5]:
            if "corners_depth_mm" in fd and fd["corners_depth_mm"]:
                has_depth = True
                break

    return frames_data, K, dist, rb_ids, has_depth


def validar_prerrequisitos(input_path, teorico_path, output_path, ancla):
    errores = []
    if not Path(input_path).exists():
        errores.append(f"Dataset no existe: {input_path}")
    if not Path(teorico_path).exists():
        errores.append(f"Geometria teorica no existe: {teorico_path}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(out, "ab") as f:
            f.write(b"")
    except OSError as e:
        errores.append(f"No se puede escribir en {out}: {e}")
    if errores:
        log_error("Prerrequisitos no cumplidos:")
        for e in errores:
            log_error(f"  - {e}")
        sys.exit(1)


# ============================================================================
# Parametrizacion RIGIDA (6 DOF por marker + tamano fijo, igual que iter 3)
# ============================================================================

def marker_pose_a_esquinas(centro, rvec, marker_mm):
    """Centro 3D + rvec Rodrigues + marker_mm -> 4 esquinas (4,3)."""
    half = marker_mm / 2.0
    corners_local = np.array([
        [-half,  half, 0.0],
        [ half,  half, 0.0],
        [ half, -half, 0.0],
        [-half, -half, 0.0],
    ])
    R = Rotation.from_rotvec(rvec).as_matrix()
    return centro + corners_local @ R.T


def esquinas_a_marker_pose(corners, marker_mm):
    """4 esquinas -> (centro, rvec). Usado para inicializacion."""
    centro = corners.mean(axis=0)
    x_axis = corners[1] - corners[0]
    y_axis = corners[0] - corners[3]
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)
    z_axis = z_axis / np.linalg.norm(z_axis)
    y_axis = np.cross(z_axis, x_axis)
    R_mat = np.column_stack([x_axis, y_axis, z_axis])
    rvec = Rotation.from_matrix(R_mat).as_rotvec()
    return centro, rvec


def parametrizar_geometria(geom_teorica, ids_orden, ancla_id, marker_mm):
    """Ancla: centro fijo, rvec libre (3 params). Otros: 6 params."""
    params = []
    offsets = {}
    _, rvec_ancla = esquinas_a_marker_pose(geom_teorica[ancla_id], marker_mm)
    offsets[ancla_id] = len(params)
    params.extend(rvec_ancla.tolist())
    for mid in ids_orden:
        if mid == ancla_id:
            continue
        centro, rvec = esquinas_a_marker_pose(geom_teorica[mid], marker_mm)
        offsets[mid] = len(params)
        params.extend(centro.tolist())
        params.extend(rvec.tolist())
    return np.array(params), offsets


def reconstruir_geometria(params, offsets, geom_anclada, ids_orden, ancla_id, marker_mm):
    geom = {}
    centro_ancla = geom_anclada.mean(axis=0)
    for mid in ids_orden:
        i = offsets[mid]
        if mid == ancla_id:
            rvec_ancla = np.asarray(params[i:i+3])
            geom[mid] = marker_pose_a_esquinas(centro_ancla, rvec_ancla, marker_mm)
        else:
            centro = np.asarray(params[i:i+3])
            rvec = np.asarray(params[i+3:i+6])
            geom[mid] = marker_pose_a_esquinas(centro, rvec, marker_mm)
    return geom


def estimar_pose_inicial(detecciones, geom_teorica, K, dist):
    obj_pts, img_pts = [], []
    for mid, corners_2d in detecciones.items():
        if mid not in geom_teorica:
            continue
        obj_pts.append(geom_teorica[mid])
        img_pts.append(corners_2d.reshape(4, 2))
    if not obj_pts:
        return None
    obj_pts = np.concatenate(obj_pts, axis=0).astype(np.float32)
    img_pts = np.concatenate(img_pts, axis=0).astype(np.float32)
    if len(obj_pts) < 4:
        return None
    flag = cv2.SOLVEPNP_IPPE_SQUARE if len(obj_pts) == 4 else cv2.SOLVEPNP_ITERATIVE
    ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist, flags=flag)
    if not ok:
        return None
    # Filtro Z<0: poses con tvec[2]<=0 son la solucion espejada (iter 4 lecciones)
    if float(tvec[2]) <= 0:
        return None
    return rvec.flatten(), tvec.flatten()


def parametrizar_poses(poses):
    params = []
    for rvec, tvec in poses:
        params.extend(rvec.tolist())
        params.extend(tvec.tolist())
    return np.array(params)


def reconstruir_poses(params, n_frames):
    poses = []
    for i in range(n_frames):
        idx = i * 6
        poses.append((params[idx:idx+3], params[idx+3:idx+6]))
    return poses


# ============================================================================
# RESIDUOS 3D-2D MIXTOS (cambio clave de iter 4)
# ============================================================================

def calcular_residuos(params, frames, ids_orden, ancla_id, geom_anclada,
                     offsets_geom, n_geom_params, marker_mm, K, dist,
                     use_depth, sigma_2d, sigma_3d):
    """Residuos concatenados [r_2d_normalizados; r_3d_normalizados].

    r_2d = (proyectar(esquina_3d, pose_frame, K) - corner_obs) / sigma_2d
    r_3d = (z_predicho_en_camara - depth_observado) / sigma_3d

    Si use_depth=False o el dataset no tiene depth, solo se devuelve r_2d.
    Los depth_obs == 0 se saltean (no hay info de ToF en ese pixel).
    """
    geom = reconstruir_geometria(
        params[:n_geom_params], offsets_geom, geom_anclada,
        ids_orden, ancla_id, marker_mm,
    )
    poses = reconstruir_poses(params[n_geom_params:], len(frames))

    r2d_chunks = []
    r3d_chunks = []

    for fd, (rvec, tvec) in zip(frames, poses):
        # R_frame: rotacion del dodecaedro en sistema de la camara
        R_frame = Rotation.from_rotvec(np.asarray(rvec)).as_matrix()
        t_frame = np.asarray(tvec).reshape(3)

        for mid, corners_2d_obs in fd["detecciones"].items():
            if mid not in geom:
                continue
            P_dodec = geom[mid].astype(np.float64)  # (4,3)

            # --- Bloque 2D: residuos de reproyeccion (igual que iter 3) ---
            proy, _ = cv2.projectPoints(
                P_dodec, np.asarray(rvec, dtype=np.float64),
                np.asarray(tvec, dtype=np.float64), K, dist,
            )
            r2d = (proy.reshape(4, 2) - corners_2d_obs).flatten() / sigma_2d
            r2d_chunks.append(r2d)

            # --- Bloque 3D: residuos de profundidad ---
            if use_depth:
                depths_obs = fd.get("corners_depth_mm", {}).get(mid, None)
                if depths_obs is not None:
                    # P_camara[i] = R_frame @ P_dodec[i] + t_frame
                    P_cam = (R_frame @ P_dodec.T).T + t_frame  # (4,3)
                    z_pred = P_cam[:, 2]                       # (4,) en mm
                    z_obs = np.asarray(depths_obs, dtype=np.float64)
                    # Solo donde el depth es valido (>0)
                    mask = z_obs > 0
                    if mask.any():
                        r3d = (z_pred[mask] - z_obs[mask]) / sigma_3d
                        r3d_chunks.append(r3d)

    if not r2d_chunks:
        return np.zeros(0)
    todo = np.concatenate(r2d_chunks)
    if use_depth and r3d_chunks:
        todo = np.concatenate([todo, np.concatenate(r3d_chunks)])
    return todo


def contar_residuos_3d(frames, use_depth):
    """Cuenta cuantos residuos 3D va a generar el dataset (corners con depth>0)."""
    if not use_depth:
        return 0
    n = 0
    for fd in frames:
        depths = fd.get("corners_depth_mm", {})
        for mid in fd["detecciones"]:
            d = depths.get(mid, None)
            if d is not None:
                n += int(np.sum(np.asarray(d) > 0))
    return n


def construir_jac_sparsity(frames, ids_orden, ancla_id, offsets_geom,
                           n_geom_params, n_pose_params, use_depth):
    """Sparsity para residuos 2D + 3D.

    Layout final: primero todos los residuos 2D (8 por deteccion), despues los 3D
    (1 por corner con depth>0). Misma estructura de columnas para ambos bloques:
    cada residuo depende de los params del marker correspondiente y la pose del
    frame.
    """
    # === Conteo de filas ===
    n_2d = sum(len(fd["detecciones"]) * 8 for fd in frames)
    n_3d = contar_residuos_3d(frames, use_depth)
    n_residuos = n_2d + n_3d
    n_total = n_geom_params + n_pose_params
    A = lil_matrix((n_residuos, n_total), dtype=int)

    # === Filas 2D ===
    row = 0
    for f_idx, fd in enumerate(frames):
        pose_offset = n_geom_params + f_idx * 6
        for mid in fd["detecciones"]:
            for r in range(8):
                for c in range(6):
                    A[row + r, pose_offset + c] = 1
                if mid in offsets_geom:
                    marker_offset = offsets_geom[mid]
                    n_marker_params = 3 if mid == ancla_id else 6
                    for c in range(n_marker_params):
                        A[row + r, marker_offset + c] = 1
            row += 8

    # === Filas 3D (solo donde depth>0) ===
    if use_depth:
        for f_idx, fd in enumerate(frames):
            pose_offset = n_geom_params + f_idx * 6
            depths = fd.get("corners_depth_mm", {})
            for mid in fd["detecciones"]:
                d = depths.get(mid, None)
                if d is None:
                    continue
                for k in range(4):
                    if d[k] <= 0:
                        continue
                    for c in range(6):
                        A[row, pose_offset + c] = 1
                    if mid in offsets_geom:
                        marker_offset = offsets_geom[mid]
                        n_marker_params = 3 if mid == ancla_id else 6
                        for c in range(n_marker_params):
                            A[row, marker_offset + c] = 1
                    row += 1
    return A


# ============================================================================
# Reporte de RMSE por marker (separado 2D px y 3D mm)
# ============================================================================

def rmse_por_marker(residuos, frames, ids_orden, ancla_id, use_depth, sigma_2d, sigma_3d):
    """Separa residuos en 2D (px) y 3D (mm) por marker.

    El vector 'residuos' ya viene NORMALIZADO por las sigmas. Para reportar
    en unidades fisicas (px y mm), des-normalizamos multiplicando por la sigma
    correspondiente.

    Devuelve dict {mid: {'rmse_2d_px': float, 'n_2d': int,
                          'rmse_3d_mm': float (o None), 'n_3d': int}}
    """
    # === Reconstruir el orden de los residuos exactamente como en calcular_residuos ===
    # Bloque 2D primero (8 por deteccion), luego 3D (variable, depende de depth>0).
    bloque_2d = {mid: [] for mid in ids_orden}
    bloque_3d = {mid: [] for mid in ids_orden}
    n_2d_por_mid = {mid: 0 for mid in ids_orden}
    n_3d_por_mid = {mid: 0 for mid in ids_orden}

    # 2D
    idx = 0
    for fd in frames:
        for mid in fd["detecciones"]:
            if mid in bloque_2d:
                bloque_2d[mid].extend(residuos[idx:idx+8] * sigma_2d)
                n_2d_por_mid[mid] += 1
            idx += 8

    # 3D
    if use_depth:
        for fd in frames:
            depths = fd.get("corners_depth_mm", {})
            for mid in fd["detecciones"]:
                d = depths.get(mid, None)
                if d is None:
                    continue
                for k in range(4):
                    if d[k] <= 0:
                        continue
                    if mid in bloque_3d:
                        bloque_3d[mid].append(residuos[idx] * sigma_3d)
                        n_3d_por_mid[mid] += 1
                    idx += 1

    out = {}
    for mid in ids_orden:
        r2 = np.asarray(bloque_2d[mid]) if bloque_2d[mid] else np.zeros(0)
        r3 = np.asarray(bloque_3d[mid]) if bloque_3d[mid] else np.zeros(0)
        out[mid] = {
            "rmse_2d_px": float(np.sqrt(np.mean(r2**2))) if r2.size else None,
            "n_2d": int(n_2d_por_mid[mid]),
            "rmse_3d_mm": float(np.sqrt(np.mean(r3**2))) if r3.size else None,
            "n_3d": int(n_3d_por_mid[mid]),
        }
    return out


def rmse_global_separado(residuos, n_2d_total, sigma_2d, sigma_3d, use_depth):
    """Calcula RMSE global 2D (px) y 3D (mm) por separado."""
    r2 = residuos[:n_2d_total] * sigma_2d
    rmse_2d = float(np.sqrt(np.mean(r2**2))) if r2.size else 0.0
    rmse_3d = None
    if use_depth and len(residuos) > n_2d_total:
        r3 = residuos[n_2d_total:] * sigma_3d
        rmse_3d = float(np.sqrt(np.mean(r3**2))) if r3.size else None
    return rmse_2d, rmse_3d


# ============================================================================
# Metadata y guardado (igual estructura que iter 3, agrego campos 3D)
# ============================================================================

def construir_metadata(args, input_path, teorico_path, n_frames_total,
                       n_frames_validos, marker_mm, rmse_init_2d, rmse_init_3d,
                       resultado, desplazamientos, has_depth,
                       n_2d_total, n_3d_total):
    rmse_final_2d, rmse_final_3d = rmse_global_separado(
        resultado.fun, n_2d_total, args.sigma_2d, args.sigma_3d, has_depth and args.use_depth,
    )
    return {
        "schema_version": "3.0",  # +1 por residuos 3D
        "script": "iter4/calibrar_rigid_body.py (residuos 2D+3D)",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "scipy_version": __import__("scipy").__version__,
        "python_version": sys.version.split()[0],
        "input_dataset": str(input_path),
        "input_dataset_sha256": hash_sha256(input_path),
        "teorico_path": str(teorico_path),
        "teorico_sha256": hash_sha256(teorico_path),
        "ancla_id": args.ancla,
        "marker_mm": marker_mm,
        "sigma_2d_px": args.sigma_2d,
        "sigma_3d_mm": args.sigma_3d,
        "use_depth": bool(has_depth and args.use_depth),
        "n_residuos_2d": n_2d_total,
        "n_residuos_3d": n_3d_total,
        "n_frames_dataset": n_frames_total,
        "n_frames_usados_ba": n_frames_validos,
        "huber_f_scale": args.huber_f_scale,
        "max_nfev": args.max_nfev,
        "ba_status": int(resultado.status),
        "ba_status_message": resultado.message,
        "ba_n_iter": int(resultado.nfev),
        "ba_success": bool(resultado.success),
        "rmse_inicial_2d_px": float(rmse_init_2d),
        "rmse_final_2d_px": float(rmse_final_2d),
        "rmse_inicial_3d_mm": float(rmse_init_3d) if rmse_init_3d is not None else None,
        "rmse_final_3d_mm": float(rmse_final_3d) if rmse_final_3d is not None else None,
        "desplazamiento_centro_max_mm": float(np.max(desplazamientos)),
        "desplazamiento_centro_mean_mm": float(np.mean(desplazamientos)),
    }


def guardar_archivo_calibrado(output_path, geom, ids_orden, metadata):
    """Escribe archivo de calibracion con flush+fsync y verificacion."""
    import os
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lineas = []
    lineas.append("# Geometria CALIBRADA del dodecaedro (BA iter 4 con residuos 2D+3D)")
    lineas.append("# Generado: " + metadata["generated_at_utc"])
    lineas.append("# Hostname: " + metadata["hostname"])
    lineas.append("# Versiones: OpenCV " + metadata["opencv_version"]
                  + ", SciPy " + metadata["scipy_version"]
                  + ", Python " + metadata["python_version"])
    lineas.append("# Input dataset: " + metadata["input_dataset"]
                  + " (sha256: " + metadata["input_dataset_sha256"] + ")")
    lineas.append("# Teorico semilla: " + metadata["teorico_path"]
                  + " (sha256: " + metadata["teorico_sha256"] + ")")
    lineas.append("# Frames usados: %d / %d" %
                  (metadata["n_frames_usados_ba"], metadata["n_frames_dataset"]))
    lineas.append("# Ancla: ID %d (centro fijo, rvec libre)" % metadata["ancla_id"])
    lineas.append("# Marker size: %.3f mm (rigido)" % metadata["marker_mm"])
    lineas.append("# Use depth: %s (sigma_2d=%.2f px, sigma_3d=%.2f mm)" %
                  (str(metadata["use_depth"]), metadata["sigma_2d_px"], metadata["sigma_3d_mm"]))
    lineas.append("# Residuos: %d 2D + %d 3D" %
                  (metadata["n_residuos_2d"], metadata["n_residuos_3d"]))
    lineas.append("# BA status: %d (%s), iter %d" %
                  (metadata["ba_status"], metadata["ba_status_message"], metadata["ba_n_iter"]))
    lineas.append("# RMSE 2D inicial -> final: %.4f -> %.4f px" %
                  (metadata["rmse_inicial_2d_px"], metadata["rmse_final_2d_px"]))
    if metadata["rmse_final_3d_mm"] is not None:
        lineas.append("# RMSE 3D inicial -> final: %.4f -> %.4f mm" %
                      (metadata["rmse_inicial_3d_mm"], metadata["rmse_final_3d_mm"]))
    lineas.append("# Desplazamiento centro: mean=%.3f mm, max=%.3f mm" %
                  (metadata["desplazamiento_centro_mean_mm"], metadata["desplazamiento_centro_max_mm"]))
    lineas.append("# Convencion esquinas: c0=TL c1=TR c2=BR c3=BL")
    lineas.append("# Formato: tag_id  cx cy cz  c0x c0y c0z  c1x c1y c1z  c2x c2y c2z  c3x c3y c3z")
    lineas.append("#")
    for mid in ids_orden:
        esquinas = geom[mid]
        centro = esquinas.mean(axis=0)
        valores = list(centro) + list(esquinas.flatten())
        linea = ("%3d   " % mid) + "  ".join("%+8.3f" % v for v in valores)
        lineas.append(linea)
    for _ in range(5):
        lineas.append("# fin")
    contenido = "\n".join(lineas) + "\n"

    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)
        f.flush()
        os.fsync(f.fileno())

    with open(out, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            tokens = linea.split()
            if len(tokens) != 16:
                raise IOError("Archivo " + str(out) + " corrupto: linea con %d tokens" % len(tokens))


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BA del dodecaedro con residuos 2D + 3D (iter 4).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--teorico", default=DEFAULT_TEORICO)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--ancla", type=int, default=DEFAULT_ANCLA)
    parser.add_argument("--marker-mm", type=float, default=DEFAULT_MARKER_MM)
    parser.add_argument("--sigma-2d", type=float, default=DEFAULT_SIGMA_2D,
                        help="Sigma de residuos 2D (px). Defecto 1.0 (ArUco SUBPIX).")
    parser.add_argument("--sigma-3d", type=float, default=DEFAULT_SIGMA_3D,
                        help="Sigma de residuos 3D (mm). Defecto 5.0 (Femto Bolt @ 0.5-1m).")
    parser.add_argument("--use-depth", dest="use_depth", action="store_true", default=True,
                        help="Usar residuos 3D si el dataset tiene depth (default ON).")
    parser.add_argument("--no-depth", dest="use_depth", action="store_false",
                        help="Forzar BA solo 2D (modo iter 3).")
    parser.add_argument("--huber-f-scale", type=float, default=DEFAULT_HUBER_F_SCALE)
    parser.add_argument("--max-nfev", type=int, default=DEFAULT_MAX_NFEV)
    parser.add_argument("--min-frames-validos", type=int, default=DEFAULT_MIN_FRAMES_VALIDOS)
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Submuestreo a N frames (0=todos).")
    parser.add_argument("--sparse", dest="sparse", action="store_true", default=True,
                        help="jac_sparsity + tr_solver lsmr (default ON). Sin esto, "
                             "el Jacobiano denso es inviable con >500 frames.")
    parser.add_argument("--no-sparse", dest="sparse", action="store_false",
                        help="Jacobiano denso (modo iter 3; solo con --max-frames <=500).")
    parser.add_argument("--loss", default="huber",
                        choices=["linear", "soft_l1", "huber", "cauchy", "arctan"])
    parser.add_argument("--method", default="trf", choices=["trf", "dogbox", "lm"])
    parser.add_argument("--verbose", type=int, default=2, choices=[0, 1, 2])
    args = parser.parse_args()

    validar_prerrequisitos(args.input, args.teorico, args.output, args.ancla)

    log_info("[1/5] Cargando dataset " + args.input + "...")
    frames_full, K, dist, rb_ids, has_depth = cargar_dataset(args.input)
    log_info("      Frames cargados: %d" % len(frames_full))
    log_info("      Rigid body IDs: " + str(sorted(rb_ids)))
    log_info("      has_depth (del .npz): %s, use_depth (CLI): %s" % (str(has_depth), str(args.use_depth)))
    use_depth = bool(has_depth and args.use_depth)
    if has_depth and not args.use_depth:
        log_warn("      Dataset tiene depth pero --no-depth activado: solo residuos 2D.")
    if not has_depth and args.use_depth:
        log_warn("      Dataset SIN depth (iter 3 schema?): residuos 3D desactivados.")

    if args.max_frames > 0 and len(frames_full) > args.max_frames:
        idx = np.linspace(0, len(frames_full)-1, args.max_frames).astype(int)
        frames_full = [frames_full[i] for i in idx]
        log_info("      Submuestreado a %d frames" % len(frames_full))

    log_info("[2/5] Cargando geometria teorica " + args.teorico + "...")
    geom_teorica = cargar_referencia(args.teorico)
    ids_orden = sorted(geom_teorica.keys())
    if args.ancla not in geom_teorica:
        log_error("ID ancla %d no esta en la geometria teorica" % args.ancla)
        sys.exit(1)
    geom_anclada = geom_teorica[args.ancla].copy()
    log_info("      Ancla: ID %d (centro fijo)" % args.ancla)

    # Consistencia residuos/sparsity/conteos: descartar detecciones cuyo ID
    # no este en la geometria (calcular_residuos las saltea, pero los conteos
    # de residuos y el patron de sparsity las contarian).
    n_drop = 0
    for fd in frames_full:
        malos = [m for m in fd["detecciones"] if m not in geom_teorica]
        for m in malos:
            del fd["detecciones"][m]
            if "corners_depth_mm" in fd:
                fd["corners_depth_mm"].pop(m, None)
            n_drop += 1
    if n_drop:
        log_warn("      %d detecciones con ID fuera de la geometria, descartadas." % n_drop)

    log_info("[3/5] Estimando poses iniciales...")
    frames_validos, poses_iniciales = [], []
    for fd in frames_full:
        pose = estimar_pose_inicial(fd["detecciones"], geom_teorica, K, dist)
        if pose is not None:
            frames_validos.append(fd)
            poses_iniciales.append(pose)
    log_info("      Frames con pose valida: %d/%d" % (len(frames_validos), len(frames_full)))
    if len(frames_validos) < args.min_frames_validos:
        log_error("Muy pocos frames validos (< %d). Recapturar." % args.min_frames_validos)
        sys.exit(1)

    log_info("[4/5] Configurando bundle adjustment...")
    params_geom_init, offsets_geom = parametrizar_geometria(
        geom_teorica, ids_orden, args.ancla, args.marker_mm,
    )
    params_poses_init = parametrizar_poses(poses_iniciales)
    n_geom_params = len(params_geom_init)
    n_pose_params = len(params_poses_init)
    params_init = np.concatenate([params_geom_init, params_poses_init])

    n_2d_total = sum(len(fd["detecciones"]) * 8 for fd in frames_validos)
    n_3d_total = contar_residuos_3d(frames_validos, use_depth)
    log_info("      Geom params: %d, Pose params: %d, Total: %d" %
             (n_geom_params, n_pose_params, len(params_init)))
    log_info("      Residuos: %d 2D + %d 3D = %d total" %
             (n_2d_total, n_3d_total, n_2d_total + n_3d_total))
    log_info("      Sigmas: 2D=%.2f px, 3D=%.2f mm" % (args.sigma_2d, args.sigma_3d))

    res_init = calcular_residuos(
        params_init, frames_validos, ids_orden, args.ancla, geom_anclada,
        offsets_geom, n_geom_params, args.marker_mm, K, dist,
        use_depth, args.sigma_2d, args.sigma_3d,
    )
    rmse_init_2d, rmse_init_3d = rmse_global_separado(
        res_init, n_2d_total, args.sigma_2d, args.sigma_3d, use_depth,
    )
    log_info("      RMSE inicial 2D: %.4f px" % rmse_init_2d)
    if rmse_init_3d is not None:
        log_info("      RMSE inicial 3D: %.4f mm" % rmse_init_3d)

    log_info("[5/5] Ejecutando bundle adjustment...")
    log_info("      Method: %s, Loss: %s, f_scale: %.2f, sparse: %s" %
             (args.method, args.loss, args.huber_f_scale, str(args.sparse)))
    extra_ls = {}
    if args.sparse:
        # Sin sparsity, scipy estima el Jacobiano denso por diferencias
        # finitas: n_params+1 evaluaciones por iteracion + O(n_res*n_params)
        # de RAM. Con 2300 frames eso son ~14k evaluaciones y ~13 GB -> se
        # "cuelga" (leccion 2026-06-11). Con jac_sparsity, scipy agrupa
        # columnas estructuralmente ortogonales y baja a ~100 evaluaciones.
        log_info("      Construyendo jac_sparsity...")
        A = construir_jac_sparsity(frames_validos, ids_orden, args.ancla,
                                   offsets_geom, n_geom_params, n_pose_params,
                                   use_depth)
        if A.shape != (len(res_init), len(params_init)):
            log_error("jac_sparsity inconsistente: %s vs (%d, %d). "
                      "Correr con --no-sparse y reportar." %
                      (str(A.shape), len(res_init), len(params_init)))
            sys.exit(1)
        log_info("      Sparsity OK: %s, nnz=%d" % (str(A.shape), A.nnz))
        extra_ls = dict(jac_sparsity=A, tr_solver="lsmr", x_scale="jac")
    t0 = time.time()
    resultado = least_squares(
        calcular_residuos, params_init,
        args=(frames_validos, ids_orden, args.ancla, geom_anclada,
              offsets_geom, n_geom_params, args.marker_mm, K, dist,
              use_depth, args.sigma_2d, args.sigma_3d),
        method=args.method, loss=args.loss, f_scale=args.huber_f_scale,
        max_nfev=args.max_nfev, verbose=args.verbose,
        **extra_ls,
    )
    t_ba = time.time() - t0

    rmse_final_2d, rmse_final_3d = rmse_global_separado(
        resultado.fun, n_2d_total, args.sigma_2d, args.sigma_3d, use_depth,
    )
    log_stats("Tiempo BA: %.1f s" % t_ba)
    log_stats("Status: %d (%s)" % (resultado.status, resultado.message))
    log_stats("Iteraciones: %d" % resultado.nfev)
    log_stats("RMSE 2D: %.4f -> %.4f px (reduccion %.1f%%)" %
              (rmse_init_2d, rmse_final_2d, 100*(1-rmse_final_2d/max(rmse_init_2d, 1e-9))))
    if rmse_final_3d is not None:
        log_stats("RMSE 3D: %.4f -> %.4f mm (reduccion %.1f%%)" %
                  (rmse_init_3d, rmse_final_3d, 100*(1-rmse_final_3d/max(rmse_init_3d, 1e-9))))
    if not resultado.success:
        log_warn("El BA NO converge satisfactoriamente.")

    geom_calibrada = reconstruir_geometria(
        resultado.x[:n_geom_params], offsets_geom, geom_anclada,
        ids_orden, args.ancla, args.marker_mm,
    )

    rmse_marker = rmse_por_marker(
        resultado.fun, frames_validos, ids_orden, args.ancla,
        use_depth, args.sigma_2d, args.sigma_3d,
    )
    log_stats("RMSE por marker:")
    for mid in ids_orden:
        info = rmse_marker.get(mid, {})
        s2 = ("%.3f px" % info["rmse_2d_px"]) if info.get("rmse_2d_px") is not None else "N/A"
        s3 = ("%.3f mm" % info["rmse_3d_mm"]) if info.get("rmse_3d_mm") is not None else "N/A"
        marca = " (ancla)" if mid == args.ancla else ""
        log_stats("  ID %3d: 2D %s (n=%d), 3D %s (n=%d)%s" %
                  (mid, s2, info.get("n_2d", 0), s3, info.get("n_3d", 0), marca))

    log_stats("Desplazamientos respecto a geometria teorica:")
    log_stats("  %6s  %11s  %12s" % ("Marker", "centro (mm)", "esq_max (mm)"))
    desplazamientos = []
    for mid in ids_orden:
        c_t = geom_teorica[mid].mean(axis=0)
        c_c = geom_calibrada[mid].mean(axis=0)
        d_c = float(np.linalg.norm(c_c - c_t))
        d_e = float(np.max(np.linalg.norm(geom_calibrada[mid] - geom_teorica[mid], axis=1)))
        marca = " (ancla)" if mid == args.ancla else ""
        log_stats("  %6d  %11.3f  %12.3f%s" % (mid, d_c, d_e, marca))
        desplazamientos.append(d_c)

    metadata = construir_metadata(
        args, args.input, args.teorico, len(frames_full), len(frames_validos),
        args.marker_mm, rmse_init_2d, rmse_init_3d, resultado, desplazamientos,
        has_depth, n_2d_total, n_3d_total,
    )
    guardar_archivo_calibrado(args.output, geom_calibrada, ids_orden, metadata)
    log_info("Guardado: " + args.output)


if __name__ == "__main__":
    main()
