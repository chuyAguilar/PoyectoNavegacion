"""
Lee las calibraciones de fabrica de la Femto Bolt (K1 + K2 de iter 4).

Extrae del SDK:
  - Intrinseca de RGB (color)         -> K1 (reemplaza camera_calibration_caja_luz.yml)
  - Intrinseca de Depth               -> calibracion del sensor depth
  - Distorsiones de RGB y Depth       -> coeficientes Brown-Conrady
  - Extrinseca Depth -> Color         -> K2 (transformacion entre sensores)

Despues hace un test de reproyeccion: detecta un marker ArUco, hace solvePnP
con la K de fabrica, calcula error de reproyeccion. Si RMS < 0.5 px, la
calibracion de fabrica es buena (caso A del camino C).

Salida:
  data/femtobolt_calibration.yml   <- formato compatible con scripts del proyecto

Uso:
    python iter4/leer_calibracion_femtobolt.py --marker-mm 13.4

NOTA: el --marker-mm es CRITICO para el test de reproyeccion. Si el marker
fisico real difiere del valor pasado, el RMSE va a salir artificialmente alto
aunque la calibracion sea buena.
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

try:
    from pyorbbecsdk import (
        Pipeline, Config, OBSensorType, OBFormat, OBStreamType,
        OBAlignMode, AlignFilter,
    )
except ImportError:
    print("[ERROR] pyorbbecsdk2 no instalado.")
    sys.exit(1)


# ============================================================
# Helpers
# ============================================================

def intrinsic_to_K(intr):
    """Convierte un OBCameraIntrinsic a matriz K 3x3 compatible con OpenCV."""
    K = np.array([
        [intr.fx,        0, intr.cx],
        [       0, intr.fy, intr.cy],
        [       0,        0,        1],
    ], dtype=np.float64)
    return K


def distortion_to_array(dist):
    """Convierte un OBCameraDistortion a array [k1, k2, p1, p2, k3] de OpenCV."""
    return np.array([dist.k1, dist.k2, dist.p1, dist.p2, dist.k3], dtype=np.float64)


def extrinsic_to_matrix(ext):
    """Convierte un OBExtrinsic (rotacion + traslacion) a matriz 4x4 homogenea.

    El nombre del campo de traslacion varia entre versiones del SDK.
    Probamos varios nombres comunes hasta encontrar el correcto.
    """
    # Rotacion: el nombre 'rot' parece estable
    if hasattr(ext, "rot"):
        R = np.array(ext.rot).reshape(3, 3)
    elif hasattr(ext, "rotation"):
        R = np.array(ext.rotation).reshape(3, 3)
    else:
        print(f"[WARN] No encuentro campo de rotacion en OBExtrinsic. Atributos disponibles:")
        print(f"  {[a for a in dir(ext) if not a.startswith('_')]}")
        R = np.eye(3)

    # Traslacion: el campo se llama 'transform' en pyorbbecsdk v2.
    # Puede ser un array de 3 elementos (translation pura) o una matriz 4x4 completa.
    t = np.zeros(3)
    if hasattr(ext, "transform"):
        tv = np.array(ext.transform).flatten()
        if tv.size == 3:
            t = tv
            print(f"[INFO] ext.transform es vector de traslacion (3 floats)")
        elif tv.size == 16:
            # Matriz 4x4 completa. Extraer la columna de traslacion.
            M = np.array(ext.transform).reshape(4, 4)
            t = M[:3, 3]
            print(f"[INFO] ext.transform es matriz 4x4 completa")
        elif tv.size == 12:
            # Matriz 3x4 (R|t). Extraer la columna 4.
            M = np.array(ext.transform).reshape(3, 4)
            t = M[:, 3]
            print(f"[INFO] ext.transform es matriz 3x4 (R|t)")
        else:
            print(f"[WARN] ext.transform tiene shape inesperado: {tv.size} elementos. Contenido:")
            print(f"  {tv}")
    else:
        for name in ("trans", "translation", "t", "tvec"):
            if hasattr(ext, name):
                t = np.array(getattr(ext, name)).reshape(3, 1).flatten()
                print(f"[INFO] Campo traslacion encontrado como '{name}'")
                break

    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def imprimir_intrinseca(nombre, intr, dist):
    K = intrinsic_to_K(intr)
    d = distortion_to_array(dist)
    print(f"\n=== {nombre} ===")
    print(f"  Resolucion: {intr.width}x{intr.height}")
    print(f"  Focal:      fx={intr.fx:.2f}, fy={intr.fy:.2f}")
    print(f"  Centro:     cx={intr.cx:.2f}, cy={intr.cy:.2f}")
    print(f"  K =\n{K}")
    print(f"  dist =      [k1={d[0]:.6f}, k2={d[1]:.6f}, p1={d[2]:.6f}, p2={d[3]:.6f}, k3={d[4]:.6f}]")
    return K, d


def main():
    parser = argparse.ArgumentParser(description="Lee calibracion de fabrica de la Femto Bolt + test de reproyeccion.")
    parser.add_argument("--marker-mm", type=float, default=13.4,
                        help="Lado fisico del marker ArUco en mm (default 13.4 = iter 4)")
    parser.add_argument("--duracion-test", type=int, default=10,
                        help="Segundos del test de reproyeccion (default 10)")
    args = parser.parse_args()

    print(f"[K1+K2 iter 4] Leyendo calibraciones de la Femto Bolt...")
    print(f"  marker_mm para test reproyeccion: {args.marker_mm}")

    # ============================================================
    # 1. Inicializar pipeline y obtener perfiles
    # ============================================================
    pipeline = Pipeline()
    config = Config()

    try:
        color_profiles = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        color_profile = color_profiles.get_default_video_stream_profile()
        config.enable_stream(color_profile)
    except Exception as e:
        print(f"[ERROR] No se pudo obtener color profile: {e}")
        sys.exit(1)

    try:
        depth_profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        depth_profile = depth_profiles.get_default_video_stream_profile()
        config.enable_stream(depth_profile)
    except Exception as e:
        print(f"[ERROR] No se pudo obtener depth profile: {e}")
        sys.exit(1)

    # ============================================================
    # 2. Leer calibraciones
    # ============================================================
    color_intr = color_profile.get_intrinsic()
    color_dist = color_profile.get_distortion()
    depth_intr = depth_profile.get_intrinsic()
    depth_dist = depth_profile.get_distortion()
    extrinsic_depth_to_color = depth_profile.get_extrinsic_to(color_profile)

    K_color, dist_color = imprimir_intrinseca("Color (RGB)", color_intr, color_dist)
    K_depth, dist_depth = imprimir_intrinseca("Depth", depth_intr, depth_dist)

    T_depth_to_color = extrinsic_to_matrix(extrinsic_depth_to_color)
    print(f"\n=== Extrinseca Depth -> Color ===")
    print(f"  T =\n{T_depth_to_color}")

    # ============================================================
    # 3. Guardar en YAML compatible con el proyecto
    # ============================================================
    output_path = Path(__file__).resolve().parent.parent / "data" / "femtobolt_calibration.yml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    calib_dict = {
        "source": "Femto Bolt - calibracion de fabrica (SDK)",
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "color": {
            "width": int(color_intr.width),
            "height": int(color_intr.height),
            "K": K_color.tolist(),
            "dist": dist_color.tolist(),
        },
        "depth": {
            "width": int(depth_intr.width),
            "height": int(depth_intr.height),
            "K": K_depth.tolist(),
            "dist": dist_depth.tolist(),
        },
        "extrinsic_depth_to_color": T_depth_to_color.tolist(),
    }

    with open(output_path, "w") as f:
        yaml.dump(calib_dict, f, default_flow_style=False, sort_keys=False)
    print(f"\n[Guardado] {output_path}")

    # ============================================================
    # 4. Test de reproyeccion con un marker ArUco visible
    # ============================================================
    print("\n[Test de reproyeccion] Capturando frames con marker ArUco visible...")
    print("  Mostrale al SDK un marker ArUco del dodecaedro durante 10 segundos.")
    print("  Vamos a medir el error de reproyeccion con la K de fabrica.\n")

    pipeline.enable_frame_sync()
    pipeline.start(config)

    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, "DICT_ARUCO_MIP_36h12")
    )
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)

    # Esquinas 3D del marker fisico (parametrizado por --marker-mm)
    half = args.marker_mm / 2.0
    obj_points = np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0],
    ], dtype=np.float32)

    rmse_acumulado = []
    t_inicio = time.time()
    n_frames = 0

    while time.time() - t_inicio < args.duracion_test:
        frames = pipeline.wait_for_frames(1000)
        if frames is None:
            continue
        color_frame = frames.get_color_frame()
        if not color_frame:
            continue

        # Decodificar color (MJPG es lo mas comun)
        color_data = np.asanyarray(color_frame.get_data())
        if color_frame.get_format() == OBFormat.MJPG:
            rgb = cv2.imdecode(color_data, cv2.IMREAD_COLOR)
        elif color_frame.get_format() == OBFormat.RGB:
            rgb = color_data.reshape(color_frame.get_height(), color_frame.get_width(), 3)
            rgb = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        else:
            continue

        n_frames += 1
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)

        if ids is None or len(ids) == 0:
            continue

        # Para cada marker: solvePnP IPPE_SQUARE y medir error de reproyeccion
        for i, mid in enumerate(ids.flatten().tolist()):
            img_pts = corners[i].reshape(4, 2).astype(np.float32)
            ok, rvec, tvec = cv2.solvePnP(
                obj_points, img_pts, K_color, dist_color,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            if not ok:
                continue
            proy, _ = cv2.projectPoints(obj_points, rvec, tvec, K_color, dist_color)
            err = np.linalg.norm(proy.reshape(4, 2) - img_pts, axis=1)
            rmse = np.sqrt(np.mean(err**2))
            rmse_acumulado.append(rmse)

    pipeline.stop()

    if rmse_acumulado:
        rmse_global = np.sqrt(np.mean(np.array(rmse_acumulado)**2))
        print(f"\n=== Test reproyeccion ({len(rmse_acumulado)} markers en {n_frames} frames) ===")
        print(f"  RMSE promedio: {rmse_global:.3f} px")
        print(f"  RMSE max:      {max(rmse_acumulado):.3f} px")
        print(f"  RMSE min:      {min(rmse_acumulado):.3f} px")

        if rmse_global < 0.5:
            print(f"\n  [EXCELENTE] Calibracion de fabrica buena (RMSE < 0.5 px).")
            print(f"  Caso A confirmado: usamos K de fabrica sin recalibrar.")
        elif rmse_global < 1.0:
            print(f"\n  [BUENO] Calibracion de fabrica aceptable (RMSE < 1 px).")
            print(f"  Recomendado: aceptar K de fabrica.")
        else:
            print(f"\n  [REGULAR/MALO] Calibracion de fabrica con RMSE > 1 px.")
            print(f"  Caso B recomendado: calibrar nosotros con ChAruco/checkerboard.")
    else:
        print(f"\n  No se detectaron markers ArUco en {n_frames} frames.")
        print(f"  Mostrale el dodecaedro a la camara y volve a correr.")


if __name__ == "__main__":
    main()
