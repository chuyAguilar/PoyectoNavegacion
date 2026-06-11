"""
Auto-calibracion del rigid body (dodecaedro) por bundle adjustment.

Etapa D del pipeline. Refactor completo (auditoria iter 2, 2026-05-16).

Cambios respecto a iter 1:
- Parametrizacion RIGIDA por marker: 6 DOF (centro 3D + rvec Rodrigues) + tamano
  fijo `marker_mm`. Cada marker es un cuadrado fisico real. Esto evita que el
  optimizer absorba ruido deformando la geometria (problema observado el
  2026-05-19 con parametrizacion libre: desplazamientos de 30-40 mm para un
  RMSE de 0.43 px, fisicamente imposible).
- jac_sparsity disponible via --use-sparse pero NO recomendado (tiene un bug
  pendiente, ver tarea #22). Default es denso (sin sparse), estilo iter 1.
- Reporte de convergencia completo (status, iter, RMSE inicial/final por marker).
- Validacion de prerrequisitos antes de empezar.
- Metadata extensiva en archivo de salida (versiones, hashes, parametros).
- Logging estructurado con verbose=2 por default (iter por iter).

Auditoria: documentos/auditoria_iter2/03c_auditoria_calibrar_rigid_body.md
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


# --- Defaults ---

DEFAULT_INPUT = "capturas_calibracion.npz"
DEFAULT_TEORICO = "data/reference_dodecaedro.txt"
DEFAULT_OUTPUT = "data/reference_dodecaedro_calibrado.txt"
DEFAULT_ANCLA = 151
DEFAULT_MARKER_MM = 16.0
DEFAULT_HUBER_F_SCALE = 2.0
DEFAULT_MAX_NFEV = 200
DEFAULT_MIN_FRAMES_VALIDOS = 50


def log_info(msg):  print(f"[INFO] {msg}")
def log_warn(msg):  print(f"[WARN] {msg}")
def log_error(msg): print(f"[ERROR] {msg}", file=sys.stderr)
def log_stats(msg): print(f"[STATS] {msg}")


# --- I/O helpers ---

def hash_sha256(ruta):
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
    """Carga el .npz de captura_calibracion. Devuelve (frames_data, K, dist, rb_ids)."""
    data = np.load(npz_path, allow_pickle=True)
    frames_data = list(data["frames_data"])
    K = data["K"]
    dist = data["dist"]
    rb_ids = set(int(x) for x in data["rb_ids"])
    return frames_data, K, dist, rb_ids


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


# --- Parametrizacion RIGIDA (6 DOF por marker + tamano fijo) ---

def marker_pose_a_esquinas(centro, rvec, marker_mm):
    """Dado centro 3D + rvec (Rodrigues) + marker_mm, devuelve las 4 esquinas (4, 3).

    Convencion OpenCV ArUco: c0=TL, c1=TR, c2=BR, c3=BL.
    En el frame local del marker: z=normal saliente, x=right, y=up.
    """
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
    """Estima (centro, rvec) que mejor describe las 4 esquinas. Usado para inicializacion."""
    centro = corners.mean(axis=0)
    # Ejes locales: x=c1-c0 (right), y=c0-c3 (up), z=cross(x, y)
    x_axis = corners[1] - corners[0]
    y_axis = corners[0] - corners[3]
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = y_axis / np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)
    z_axis = z_axis / np.linalg.norm(z_axis)
    # Re-ortogonalizar y (por si hay ruido)
    y_axis = np.cross(z_axis, x_axis)
    R_mat = np.column_stack([x_axis, y_axis, z_axis])
    rvec = Rotation.from_matrix(R_mat).as_rotvec()
    return centro, rvec


def parametrizar_geometria(geom_teorica, ids_orden, ancla_id, marker_mm):
    """Parametrizacion RIGIDA con ancla rotacional.

    - ANCLA: 3 floats (rvec Rodrigues). El centro queda fijo en su posicion teorica;
      la orientacion se optimiza. Esto evita el sesgo de inclinacion que aparece
      cuando el ancla queda con orientacion fija (descubierto 2026-05-20 en pivote).
    - OTROS MARKERS: 6 floats (centro 3D + rvec).
    - Tamano fisico (marker_mm) FIJO en todos los markers.
    """
    params = []
    offsets = {}
    # Primero el ancla: solo rvec (3 params). El centro queda fijo en geom_teorica.
    _, rvec_ancla = esquinas_a_marker_pose(geom_teorica[ancla_id], marker_mm)
    offsets[ancla_id] = len(params)
    params.extend(rvec_ancla.tolist())
    # Resto: 6 params cada uno
    for mid in ids_orden:
        if mid == ancla_id:
            continue
        centro, rvec = esquinas_a_marker_pose(geom_teorica[mid], marker_mm)
        offsets[mid] = len(params)
        params.extend(centro.tolist())
        params.extend(rvec.tolist())
    return np.array(params), offsets


def reconstruir_geometria(params, offsets, geom_anclada, ids_orden, ancla_id, marker_mm):
    """Reconstruye dict {tag_id: (4, 3)} desde params rigidos.

    - ANCLA: 3 params (rvec), centro tomado del centroide de geom_anclada.
    - OTROS: 6 params (centro + rvec).
    """
    geom = {}
    # Centro fijo del ancla = centroide de las esquinas teoricas
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


# --- Poses y residuos ---

def estimar_pose_inicial(detecciones, geom_teorica, K, dist):
    """Pose inicial del dodecaedro usando geom teorica + detecciones."""
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


def calcular_residuos(params, frames, ids_orden, ancla_id, geom_anclada,
                     offsets_geom, n_geom_params, marker_mm, K, dist):
    """Residuos de reproyeccion 2D para todos los frames."""
    geom = reconstruir_geometria(
        params[:n_geom_params], offsets_geom, geom_anclada,
        ids_orden, ancla_id, marker_mm,
    )
    poses = reconstruir_poses(params[n_geom_params:], len(frames))
    todos = []
    for fd, (rvec, tvec) in zip(frames, poses):
        for mid, corners_2d_obs in fd["detecciones"].items():
            if mid not in geom:
                continue
            proy, _ = cv2.projectPoints(
                geom[mid].astype(np.float64),
                rvec.astype(np.float64), tvec.astype(np.float64),
                K, dist,
            )
            todos.append((proy.reshape(4, 2) - corners_2d_obs).flatten())
    return np.concatenate(todos)


def construir_jac_sparsity(frames, ids_orden, ancla_id, offsets_geom,
                           n_geom_params, n_pose_params):
    """Construye la matriz de sparsity del jacobiano.

    Cada deteccion produce 8 residuos (4 corners x 2 coords).
    - ANCLA (3 params, solo rvec): los 8 residuos dependen de esos 3 params.
    - OTROS (6 params, centro+rvec): los 8 residuos dependen de los 6 params.
    - Pose del frame: 6 params, todos los residuos dependen.
    """
    total_residuos = sum(len(fd["detecciones"]) * 8 for fd in frames)
    n_total = n_geom_params + n_pose_params
    A = lil_matrix((total_residuos, n_total), dtype=int)

    row = 0
    for f_idx, fd in enumerate(frames):
        pose_offset = n_geom_params + f_idx * 6
        for mid in fd["detecciones"]:
            for r in range(8):
                # Pose del frame (6 params)
                for c in range(6):
                    A[row + r, pose_offset + c] = 1
                # Params del marker
                if mid in offsets_geom:
                    marker_offset = offsets_geom[mid]
                    n_marker_params = 3 if mid == ancla_id else 6
                    for c in range(n_marker_params):
                        A[row + r, marker_offset + c] = 1
            row += 8
    return A


# --- Reporte de RMSE por marker ---

def rmse_por_marker(residuos, frames):
    """Agrupa residuos por tag_id y computa RMSE de cada uno.

    Cada deteccion aporta 8 valores residuos. Las detecciones estan en
    el mismo orden que se generaron en calcular_residuos.
    """
    por_marker = {}
    n_dets = {}
    idx = 0
    for fd in frames:
        for mid in fd["detecciones"]:
            por_marker.setdefault(mid, []).extend(residuos[idx:idx+8])
            n_dets[mid] = n_dets.get(mid, 0) + 1
            idx += 8
    return {mid: (float(np.sqrt(np.mean(np.asarray(r)**2))), n_dets[mid])
            for mid, r in por_marker.items()}


# --- Metadata y guardado ---

def construir_metadata(args, input_path, teorico_path, n_frames_total,
                       n_frames_validos, marker_mm, rmse_init, resultado,
                       desplazamientos):
    return {
        "schema_version": "2.0",
        "script": "calibrar_rigid_body.py (auditado iter 2)",
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
        "n_frames_dataset": n_frames_total,
        "n_frames_usados_ba": n_frames_validos,
        "huber_f_scale": args.huber_f_scale,
        "max_nfev": args.max_nfev,
        "ba_status": int(resultado.status),
        "ba_status_message": resultado.message,
        "ba_n_iter": int(resultado.nfev),
        "ba_success": bool(resultado.success),
        "rmse_inicial_px": float(rmse_init),
        "rmse_final_px": float(np.sqrt(np.mean(resultado.fun**2))),
        "desplazamiento_centro_max_mm": float(np.max(desplazamientos)),
        "desplazamiento_centro_mean_mm": float(np.mean(desplazamientos)),
    }


def guardar_archivo_calibrado(output_path, geom, ids_orden, metadata):
    """Escribe archivo de calibracion con flush+fsync y verificacion post-escritura.

    Nota: el sistema de archivos puede truncar los ultimos bytes al cerrar (visto
    en Windows con OneDrive/antivirus). Por eso forzamos fsync y verificamos que
    cada linea de marker tenga exactamente 16 tokens (id + 3 centro + 12 esquinas).
    """
    import os
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Construir contenido completo en memoria primero
    lineas = []
    lineas.append("# Geometria CALIBRADA del dodecaedro (auto-calibracion BA)")
    lineas.append(f"# Generado: {metadata['generated_at_utc']}")
    lineas.append(f"# Hostname: {metadata['hostname']}")
    lineas.append(f"# Versiones: OpenCV {metadata['opencv_version']}, "
                  f"SciPy {metadata['scipy_version']}, Python {metadata['python_version']}")
    lineas.append(f"# Input dataset: {metadata['input_dataset']} (sha256: {metadata['input_dataset_sha256']})")
    lineas.append(f"# Teorico semilla: {metadata['teorico_path']} (sha256: {metadata['teorico_sha256']})")
    lineas.append(f"# Frames usados: {metadata['n_frames_usados_ba']} / {metadata['n_frames_dataset']}")
    lineas.append(f"# Ancla: ID {metadata['ancla_id']} (fijo en posicion teorica)")
    lineas.append(f"# Marker size: {metadata['marker_mm']} mm (rigido)")
    lineas.append("# Parametrizacion: 6 DOF rigidos por marker (centro 3D + rvec Rodrigues, tamano fijo)")
    lineas.append(f"# Optimizer: TRF + Huber (f_scale={metadata['huber_f_scale']}), denso (sin jac_sparsity)")
    lineas.append(f"# Status: {metadata['ba_status']} ({metadata['ba_status_message']})")
    lineas.append(f"# Iteraciones: {metadata['ba_n_iter']}")
    lineas.append(f"# RMSE inicial -> final: {metadata['rmse_inicial_px']:.4f} -> {metadata['rmse_final_px']:.4f} px")
    lineas.append(f"# Desplazamiento centro: mean={metadata['desplazamiento_centro_mean_mm']:.3f} mm, "
                  f"max={metadata['desplazamiento_centro_max_mm']:.3f} mm")
    lineas.append("# Convencion esquinas: c0=TL c1=TR c2=BR c3=BL")
    lineas.append("# Formato: tag_id  cx cy cz  c0x c0y c0z  c1x c1y c1z  c2x c2y c2z  c3x c3y c3z")
    lineas.append("#")
    for mid in ids_orden:
        esquinas = geom[mid]
        centro = esquinas.mean(axis=0)
        valores = list(centro) + list(esquinas.flatten())
        lineas.append(f"{mid:3d}   " + "  ".join(f"{v:+8.3f}" for v in valores))
    # Padding final para protegerse de truncacion del filesystem (5 lineas)
    for _ in range(5):
        lineas.append("# fin")
    contenido = "\n".join(lineas) + "\n"

    # Escribir con fsync explicito
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)
        f.flush()
        os.fsync(f.fileno())

    # Verificar post-escritura: cada marker debe tener 16 tokens
    with open(out, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            tokens = linea.split()
            if len(tokens) != 16:
                raise IOError(f"Archivo {out} corrupto: linea con {len(tokens)} tokens "
                              f"(esperaba 16): {linea[:80]}")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Bundle adjustment del dodecaedro multi-marker (Etapa D).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--teorico", default=DEFAULT_TEORICO)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--ancla", type=int, default=DEFAULT_ANCLA)
    parser.add_argument("--marker-mm", type=float, default=DEFAULT_MARKER_MM)
    parser.add_argument("--huber-f-scale", type=float, default=DEFAULT_HUBER_F_SCALE)
    parser.add_argument("--max-nfev", type=int, default=DEFAULT_MAX_NFEV)
    parser.add_argument("--min-frames-validos", type=int, default=DEFAULT_MIN_FRAMES_VALIDOS)
    parser.add_argument("--max-frames", type=int, default=0,
                        help="Submuestreo a N frames (0=todos). Iter 1 usaba 500.")
    parser.add_argument("--use-sparse", action="store_true",
                        help="OPT-IN: activar jac_sparsity. NO USAR: tiene un bug que "
                             "impide convergencia. Default es sin sparse (estilo iter 1).")
    parser.add_argument("--x-scale-jac", action="store_true",
                        help="Activar x_scale='jac' (experimental, interactua mal con huber loss).")
    parser.add_argument("--loss", default="huber",
                        choices=["linear", "soft_l1", "huber", "cauchy", "arctan"],
                        help="Loss function de least_squares. Iter 1 usaba huber.")
    parser.add_argument("--method", default="trf", choices=["trf", "dogbox", "lm"],
                        help="Metodo de least_squares. lm no soporta loss != linear.")
    parser.add_argument("--verbose", type=int, default=2, choices=[0, 1, 2],
                        help="Verbosidad de least_squares. 2=iter por iter (default, util sin sparse).")
    args = parser.parse_args()

    validar_prerrequisitos(args.input, args.teorico, args.output, args.ancla)

    log_info(f"[1/5] Cargando dataset {args.input}...")
    frames_full, K, dist, rb_ids = cargar_dataset(args.input)
    log_info(f"      Frames cargados: {len(frames_full)}")
    log_info(f"      Rigid body IDs: {sorted(rb_ids)}")

    # Submuestreo opcional (estilo iter 1)
    if args.max_frames > 0 and len(frames_full) > args.max_frames:
        idx = np.linspace(0, len(frames_full)-1, args.max_frames).astype(int)
        frames_full = [frames_full[i] for i in idx]
        log_info(f"      Submuestreado a {len(frames_full)} frames (--max-frames {args.max_frames})")

    log_info(f"[2/5] Cargando geometria teorica {args.teorico}...")
    geom_teorica = cargar_referencia(args.teorico)
    ids_orden = sorted(geom_teorica.keys())
    if args.ancla not in geom_teorica:
        log_error(f"ID ancla {args.ancla} no esta en la geometria teorica")
        sys.exit(1)
    geom_anclada = geom_teorica[args.ancla].copy()
    log_info(f"      Ancla: ID {args.ancla} (fijo)")

    log_info(f"[3/5] Estimando poses iniciales...")
    frames_validos, poses_iniciales = [], []
    for fd in frames_full:
        pose = estimar_pose_inicial(fd["detecciones"], geom_teorica, K, dist)
        if pose is not None:
            frames_validos.append(fd)
            poses_iniciales.append(pose)
    log_info(f"      Frames con pose valida: {len(frames_validos)}/{len(frames_full)}")
    if len(frames_validos) < args.min_frames_validos:
        log_error(f"Muy pocos frames validos (< {args.min_frames_validos}). Recapturar.")
        sys.exit(1)

    log_info(f"[4/5] Configurando bundle adjustment...")
    params_geom_init, offsets_geom = parametrizar_geometria(
        geom_teorica, ids_orden, args.ancla, args.marker_mm,
    )
    params_poses_init = parametrizar_poses(poses_iniciales)
    n_geom_params = len(params_geom_init)
    n_pose_params = len(params_poses_init)
    params_init = np.concatenate([params_geom_init, params_poses_init])

    log_info(f"      Geom params: {n_geom_params} ({len(ids_orden)-1} markers x 6 DOF rigidos)")
    log_info(f"      Pose params: {n_pose_params} ({len(frames_validos)} frames x 6)")
    log_info(f"      Total params: {len(params_init)}")

    A_sparse = construir_jac_sparsity(
        frames_validos, ids_orden, args.ancla, offsets_geom,
        n_geom_params, n_pose_params,
    )
    n_residuos = A_sparse.shape[0]
    sparsity_pct = 100.0 * A_sparse.nnz / (A_sparse.shape[0] * A_sparse.shape[1])
    log_info(f"      Residuos: {n_residuos}")
    log_info(f"      Sparsity: {A_sparse.nnz} no-cero ({sparsity_pct:.3f}% denso)")

    res_init = calcular_residuos(
        params_init, frames_validos, ids_orden, args.ancla, geom_anclada,
        offsets_geom, n_geom_params, args.marker_mm, K, dist,
    )
    rmse_init = float(np.sqrt(np.mean(res_init**2)))
    log_info(f"      RMSE inicial: {rmse_init:.4f} px")

    log_info(f"[5/5] Ejecutando bundle adjustment...")
    if args.use_sparse:
        log_warn("      Modo --use-sparse: jac_sparsity tiene un bug pendiente, "
                 "el BA puede NO converger.")
    else:
        log_info("      Default: sin jac_sparsity (estilo iter 1, converge correctamente)")
    t0 = time.time()
    ls_kwargs = dict(
        args=(frames_validos, ids_orden, args.ancla, geom_anclada,
              offsets_geom, n_geom_params, args.marker_mm, K, dist),
        method=args.method,
        loss=args.loss,
        f_scale=args.huber_f_scale,
        max_nfev=args.max_nfev,
        verbose=args.verbose,
    )
    log_info(f"      Method: {args.method}, Loss: {args.loss}, f_scale: {args.huber_f_scale}")
    if args.use_sparse:
        ls_kwargs["jac_sparsity"] = A_sparse
        # NOTA: x_scale='jac' interactua mal con loss='huber' (oscila y no
        # converge). Removido por defecto. Iter 1 convergia sin el.
        # Para experimentar, activar manualmente con --x-scale-jac.
    if getattr(args, "x_scale_jac", False):
        ls_kwargs["x_scale"] = "jac"
    resultado = least_squares(calcular_residuos, params_init, **ls_kwargs)
    t_ba = time.time() - t0

    rmse_final = float(np.sqrt(np.mean(resultado.fun**2)))
    log_stats(f"Tiempo BA: {t_ba:.1f}s")
    log_stats(f"Status: {resultado.status} ({resultado.message})")
    log_stats(f"Iteraciones: {resultado.nfev}")
    log_stats(f"RMSE: {rmse_init:.4f} -> {rmse_final:.4f} px "
              f"(reduccion {100*(1-rmse_final/rmse_init):.1f}%)")
    if not resultado.success:
        log_warn("El BA NO converge satisfactoriamente. Revisar.")

    geom_calibrada = reconstruir_geometria(
        resultado.x[:n_geom_params], offsets_geom, geom_anclada,
        ids_orden, args.ancla, args.marker_mm,
    )

    # RMSE por marker
    # RMSE por marker
    rmse_marker = rmse_por_marker(resultado.fun, frames_validos)
    log_stats("RMSE de reproyeccion por marker:")
    for mid in ids_orden:
        if mid in rmse_marker:
            rmse_m, n_det = rmse_marker[mid]
            estado = "(ancla)" if mid == args.ancla else "OK"
            log_stats(f"  ID {mid}: {rmse_m:.3f} px ({n_det} detecciones) {estado}")

    # Desplazamientos respecto al teorico
    log_stats("Desplazamientos respecto a geometria teorica:")
    log_stats(f"  {'Marker':>6}  {'centro (mm)':>11}  {'esq_max (mm)':>12}")
    desplazamientos = []
    for mid in ids_orden:
        c_t = geom_teorica[mid].mean(axis=0)
        c_c = geom_calibrada[mid].mean(axis=0)
        d_c = float(np.linalg.norm(c_c - c_t))
        d_e = float(np.max(np.linalg.norm(geom_calibrada[mid] - geom_teorica[mid], axis=1)))
        marca = " (ancla)" if mid == args.ancla else ""
        log_stats(f"  {mid:>6}  {d_c:>11.3f}  {d_e:>12.3f}{marca}")
        desplazamientos.append(d_c)

    metadata = construir_metadata(
        args, args.input, args.teorico, len(frames_full), len(frames_validos),
        args.marker_mm, rmse_init, resultado, desplazamientos,
    )
    guardar_archivo_calibrado(args.output, geom_calibrada, ids_orden, metadata)
    log_info(f"Guardado: {args.output}")


if __name__ == "__main__":
    main()
