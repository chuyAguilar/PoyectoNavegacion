"""
Auto-calibracion del rigid body (dodecaedro) por bundle adjustment.

Dado un dataset capturado por captura_calibracion.py:
- Optimiza las posiciones 3D de los 11 marcadores en el sistema del dodecaedro.
- Optimiza simultaneamente las poses del dodecaedro en cada frame.
- Minimiza el error de reproyeccion total sobre TODOS los frames.

Anclaje (gauge fixing):
- ID 151 (TOP) se mantiene fijo en su posicion teorica (centro en (0,0,r_in))
  alineado con los ejes X, Y para definir el sistema de coordenadas.

Output: reference_dodecaedro_calibrado.txt con la geometria real medida.

Uso:
    python calibrar_rigid_body.py --input capturas_calibracion.npz \\
                                   --teorico data/reference_dodecaedro.txt \\
                                   --output data/reference_dodecaedro_calibrado.txt
"""

import argparse
import sys

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


# ============================================================================
# UTILIDADES
# ============================================================================

def cargar_referencia(ruta):
    """Carga reference.txt y devuelve dict {tag_id: 4x3 esquinas} y centros."""
    geom = {}
    centros = {}
    with open(ruta, "r") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            vals = linea.split()
            if len(vals) < 16:
                continue
            tag_id = int(vals[0])
            centros[tag_id] = np.array([float(vals[1]), float(vals[2]), float(vals[3])])
            esquinas = np.array([
                [float(vals[4]), float(vals[5]), float(vals[6])],
                [float(vals[7]), float(vals[8]), float(vals[9])],
                [float(vals[10]), float(vals[11]), float(vals[12])],
                [float(vals[13]), float(vals[14]), float(vals[15])],
            ])
            geom[tag_id] = esquinas
    return geom, centros


def estimar_pose_inicial(detecciones, geom_teorica, K, dist):
    """Pose inicial usando geometria teorica con todos los marcadores visibles."""
    obj_pts = []
    img_pts = []
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


# ============================================================================
# PARAMETRIZACION DEL BUNDLE ADJUSTMENT
# ============================================================================
#
# Variables a optimizar:
#   1. Posiciones 3D de los marcadores (excepto 151, que esta anclado).
#      Para cada marcador no anclado, parametrizamos su esquina 0 (top-left).
#      Las otras 3 esquinas se derivan del centro y orientacion.
#
#      ALTERNATIVA SIMPLE (la que usamos):
#      Cada marcador tiene 12 numeros (4 esquinas x 3 coords).
#      Total: 10 marcadores no anclados x 12 = 120 parametros.
#
#   2. Pose del dodecaedro en cada frame: 6 parametros (rvec + tvec).
#      Total: N_frames x 6.
#
# Para 1760 frames: 120 + 1760*6 = 10680 parametros. Manejable.
#
# Residuos: error de reproyeccion 2D por cada esquina detectada.
#   Para cada deteccion: 4 esquinas x 2 coords = 8 residuos.
#   Total: ~3.29 markers/frame * 4 corners * 2 = ~26 residuos por frame
#          ~26 * 1760 = ~46,000 residuos.
#
# ============================================================================


def parametrizar_geom(geom_teorica, ids_orden, anclado_id):
    """Convierte la geometria a vector plano (excluyendo el ancla).

    Devuelve:
      params_geom: vector con las esquinas de los marcadores no anclados
      offsets: dict {tag_id: indice_inicio} para reconstruir
    """
    params = []
    offsets = {}
    for mid in ids_orden:
        if mid == anclado_id:
            continue
        offsets[mid] = len(params)
        params.extend(geom_teorica[mid].flatten().tolist())
    return np.array(params), offsets


def reconstruir_geom(params_geom, offsets, geom_anclada, ids_orden, anclado_id):
    """Reconstruye dict {tag_id: 4x3} desde el vector plano + el ancla fija."""
    geom = {anclado_id: geom_anclada.copy()}
    for mid in ids_orden:
        if mid == anclado_id:
            continue
        idx = offsets[mid]
        geom[mid] = params_geom[idx:idx+12].reshape(4, 3)
    return geom


def parametrizar_poses(poses_iniciales):
    """Convierte lista de (rvec, tvec) a vector plano."""
    params = []
    for rvec, tvec in poses_iniciales:
        params.extend(rvec.tolist())
        params.extend(tvec.tolist())
    return np.array(params)


def reconstruir_poses(params_poses, n_frames):
    """Devuelve lista de (rvec, tvec) desde vector plano."""
    poses = []
    for i in range(n_frames):
        idx = i * 6
        rvec = params_poses[idx:idx+3]
        tvec = params_poses[idx+3:idx+6]
        poses.append((rvec, tvec))
    return poses


# ============================================================================
# FUNCION DE RESIDUOS
# ============================================================================

def calcular_residuos(params, frames_data, ids_orden, anclado_id, geom_anclada,
                     n_geom_params, K, dist):
    """Calcula los residuos de reproyeccion para todos los frames."""
    params_geom = params[:n_geom_params]
    params_poses = params[n_geom_params:]

    # Reconstruir geometria
    offsets_geom = {}
    idx = 0
    for mid in ids_orden:
        if mid == anclado_id:
            continue
        offsets_geom[mid] = idx
        idx += 12

    geom = {anclado_id: geom_anclada}
    for mid in ids_orden:
        if mid == anclado_id:
            continue
        i = offsets_geom[mid]
        geom[mid] = params_geom[i:i+12].reshape(4, 3)

    # Reconstruir poses
    poses = reconstruir_poses(params_poses, len(frames_data))

    # Calcular residuos por frame
    todos_residuos = []
    for fd, (rvec, tvec) in zip(frames_data, poses):
        for mid, corners_2d_obs in fd["detecciones"].items():
            if mid not in geom:
                continue
            obj_pts = geom[mid].astype(np.float64)
            # Proyectar las 4 esquinas en la imagen
            proy, _ = cv2.projectPoints(obj_pts, rvec.astype(np.float64),
                                          tvec.astype(np.float64), K, dist)
            proy = proy.reshape(4, 2)
            # Residuo: diferencia con detecciones observadas (8 valores: 4 corners x 2 coords)
            residuos_marker = (proy - corners_2d_obs).flatten()
            todos_residuos.append(residuos_marker)

    return np.concatenate(todos_residuos)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="capturas_calibracion.npz")
    parser.add_argument("--teorico", default="data/reference_dodecaedro.txt")
    parser.add_argument("--output", default="data/reference_dodecaedro_calibrado.txt")
    parser.add_argument("--ancla", type=int, default=151,
                        help="ID del marcador anclado en su posicion teorica")
    parser.add_argument("--max_frames", type=int, default=500,
                        help="Maximo numero de frames a usar (para velocidad)")
    args = parser.parse_args()

    # Cargar dataset
    print(f"[1/5] Cargando dataset {args.input}...")
    data = np.load(args.input, allow_pickle=True)
    frames_full = list(data['frames_data'])
    K = data['K']
    dist = data['dist']
    print(f"      Frames cargados: {len(frames_full)}")

    # Reducir frames si son demasiados (acelera la optimizacion)
    if len(frames_full) > args.max_frames:
        # Submuestreo uniforme
        idx = np.linspace(0, len(frames_full)-1, args.max_frames).astype(int)
        frames = [frames_full[i] for i in idx]
        print(f"      Submuestreado a {len(frames)} frames para velocidad")
    else:
        frames = frames_full

    # Cargar geometria teorica
    print(f"\n[2/5] Cargando geometria teorica {args.teorico}...")
    geom_teorica, centros_teoricos = cargar_referencia(args.teorico)
    ids_orden = sorted(geom_teorica.keys())
    print(f"      IDs en geometria: {ids_orden}")

    if args.ancla not in geom_teorica:
        print(f"ERROR: ID ancla {args.ancla} no esta en la geometria teorica")
        sys.exit(1)
    geom_anclada = geom_teorica[args.ancla].copy()
    print(f"      Marcador ancla: ID {args.ancla} (fijo en posicion teorica)")

    # Estimar poses iniciales con geometria teorica
    print(f"\n[3/5] Estimando poses iniciales...")
    frames_validos = []
    poses_iniciales = []
    for fd in frames:
        pose = estimar_pose_inicial(fd["detecciones"], geom_teorica, K, dist)
        if pose is not None:
            frames_validos.append(fd)
            poses_iniciales.append(pose)
    print(f"      Frames con pose valida: {len(frames_validos)}/{len(frames)}")

    if len(frames_validos) < 50:
        print("ERROR: muy pocos frames con pose valida. Recapturar dataset.")
        sys.exit(1)

    # Parametrizar
    print(f"\n[4/5] Configurando bundle adjustment...")
    params_geom_init, offsets_geom = parametrizar_geom(geom_teorica, ids_orden, args.ancla)
    params_poses_init = parametrizar_poses(poses_iniciales)
    n_geom_params = len(params_geom_init)
    n_pose_params = len(params_poses_init)
    params_init = np.concatenate([params_geom_init, params_poses_init])

    print(f"      Parametros de geometria: {n_geom_params} ({len(ids_orden)-1} marcadores libres x 12)")
    print(f"      Parametros de poses:     {n_pose_params} ({len(frames_validos)} frames x 6)")
    print(f"      Total parametros:        {len(params_init)}")

    # Calcular numero de residuos
    n_residuos = sum(len(fd["detecciones"]) * 8 for fd in frames_validos)
    print(f"      Total residuos:          {n_residuos}")

    # Residuos iniciales
    res_init = calcular_residuos(params_init, frames_validos, ids_orden, args.ancla,
                                   geom_anclada, n_geom_params, K, dist)
    rmse_init = np.sqrt(np.mean(res_init**2))
    print(f"      RMSE de reproyeccion INICIAL: {rmse_init:.4f} pixeles")

    # Bundle adjustment
    print(f"\n[5/5] Ejecutando bundle adjustment (puede tardar 30-120 segundos)...")
    resultado = least_squares(
        calcular_residuos, params_init,
        args=(frames_validos, ids_orden, args.ancla, geom_anclada,
              n_geom_params, K, dist),
        method="trf",
        loss="huber",  # robusto a outliers
        f_scale=2.0,    # umbral para considerar outlier (en pixeles)
        max_nfev=200,
        verbose=1,
    )

    rmse_final = np.sqrt(np.mean(resultado.fun**2))
    print(f"\n      RMSE de reproyeccion FINAL:   {rmse_final:.4f} pixeles")
    print(f"      Reduccion: {rmse_init:.4f} -> {rmse_final:.4f} ({100*(1-rmse_final/rmse_init):.1f}%)")

    # Reconstruir geometria optimizada
    geom_calibrada = reconstruir_geom(
        resultado.x[:n_geom_params], offsets_geom, geom_anclada, ids_orden, args.ancla
    )

    # Calcular desplazamientos respecto a la geometria teorica
    print(f"\n[Comparacion teorica vs calibrada]")
    print(f"  Marcador | Desplazamiento centro (mm)  | Desplazamiento esquina max (mm)")
    print(f"  ---------|----------------------------|--------------------------------")
    desplazamientos = []
    for mid in ids_orden:
        c_teorico = centros_teoricos[mid]
        c_calib = geom_calibrada[mid].mean(axis=0)
        desp_centro = np.linalg.norm(c_calib - c_teorico)

        # desplazamiento maximo de cualquier esquina
        desp_corners = np.linalg.norm(geom_calibrada[mid] - geom_teorica[mid], axis=1)
        desp_max = desp_corners.max()

        marcador_str = f"  {mid:6d}  | {desp_centro:6.3f}                    | {desp_max:6.3f}"
        if mid == args.ancla:
            marcador_str += "  (ancla, fijo)"
        print(marcador_str)
        desplazamientos.append(desp_centro)

    print(f"\n  Desplazamiento promedio centro: {np.mean(desplazamientos):.3f} mm")
    print(f"  Desplazamiento maximo centro:   {np.max(desplazamientos):.3f} mm")

    # Guardar archivo calibrado
    print(f"\n[Guardando] {args.output}")
    with open(args.output, "w") as f:
        f.write(f"# Geometria CALIBRADA del dodecaedro (auto-calibracion BA)\n")
        f.write(f"# RMSE de reproyeccion final: {rmse_final:.4f} pixeles\n")
        f.write(f"# Frames usados: {len(frames_validos)}\n")
        f.write(f"# Marcador ancla (fijo): ID {args.ancla}\n")
        f.write(f"# Formato: tag_id  cx cy cz  c0x c0y c0z  c1x c1y c1z  c2x c2y c2z  c3x c3y c3z\n")
        f.write(f"#\n")
        for mid in ids_orden:
            esquinas = geom_calibrada[mid]
            centro = esquinas.mean(axis=0)
            valores = list(centro) + list(esquinas.flatten())
            linea = f"{mid:3d}   " + "  ".join(f"{v:+8.3f}" for v in valores)
            f.write(linea + "\n")

    print(f"\n[OK] Calibracion completa.")
    print(f"\nProximos pasos:")
    print(f"  1. Cambiar el config para usar {args.output}.")
    print(f"  2. Ejecutar tracker.py y verificar estabilidad estatica mejorada.")


if __name__ == "__main__":
    main()