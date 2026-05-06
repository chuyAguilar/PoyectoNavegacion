"""
Test rapido de calibracion de pivote del dodecaedro.

Captura poses del dodecaedro durante un pivote, aplica RANSAC, y reporta:
- Offset del tip respecto al centro del dodecaedro.
- RMSE del ajuste a esfera.
- Std del offset entre poses (la metrica que de verdad importa).

Este script es STANDALONE: no necesita Slicer, ni el tracker.py.
Usa la misma deteccion ArUco + IPPE_SQUARE + multi-marker que el tracker.

Uso:
    # 1. Calibracion de pivote (default)
    python test_pivote.py --duracion 45

    # 2. Para validar offset existente, repite la prueba multiple veces
    #    y verifica que el offset sea consistente entre captures.

INSTRUCCIONES DURANTE LA CAPTURA:
- Clava la punta del tornillo en un punto fijo (cartón con orificio).
- Pivotea el stylus haciendo conos amplios pero suaves.
- Cubre la mayor variedad de orientaciones posible (sin que la punta se mueva).
- Mantén el dodecaedro siempre visible para la cámara.
"""

import argparse
import time
import sys

import cv2
import numpy as np
import yaml
from scipy.optimize import least_squares


# ============================================================================
# UTILIDADES (compartidas con tracker.py)
# ============================================================================

def cargar_calibracion(ruta):
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    K = fs.getNode("camera_matrix").mat()
    dist = fs.getNode("distortion_coefficients").mat()
    fs.release()
    return K, dist


def cargar_rigid_body(ruta):
    """Carga reference.txt y devuelve dict {tag_id: 4x3 esquinas}."""
    geom = {}
    with open(ruta, "r") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            vals = linea.split()
            if len(vals) < 16:
                continue
            tag_id = int(vals[0])
            esquinas = np.array([
                [float(vals[4]),  float(vals[5]),  float(vals[6])],
                [float(vals[7]),  float(vals[8]),  float(vals[9])],
                [float(vals[10]), float(vals[11]), float(vals[12])],
                [float(vals[13]), float(vals[14]), float(vals[15])],
            ], dtype=np.float32)
            geom[tag_id] = esquinas
    return geom


def estimar_pose_rigid_body(detecciones, rb_geom, K, dist):
    """Pose conjunta multi-marker (igual que en tracker.py)."""
    obj_pts_list = []
    img_pts_list = []
    for tag_id, corners_2d in detecciones.items():
        if tag_id not in rb_geom:
            continue
        obj_pts_list.append(rb_geom[tag_id])
        img_pts_list.append(corners_2d.reshape(4, 2).astype(np.float32))
    if not obj_pts_list:
        return None
    all_obj = np.concatenate(obj_pts_list, axis=0).astype(np.float32)
    all_img = np.concatenate(img_pts_list, axis=0).astype(np.float32)

    if len(obj_pts_list) == 1:
        ok, rvec, tvec = cv2.solvePnP(all_obj, all_img, K, dist,
                                        flags=cv2.SOLVEPNP_IPPE_SQUARE)
    else:
        ok, rvec, tvec = cv2.solvePnP(all_obj, all_img, K, dist,
                                        flags=cv2.SOLVEPNP_ITERATIVE)
        if ok:
            rvec, tvec = cv2.solvePnPRefineLM(all_obj, all_img, K, dist, rvec, tvec)
    if not ok:
        return None
    return rvec, tvec


def rvec_tvec_a_matriz(rvec, tvec):
    R, _ = cv2.Rodrigues(rvec)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = tvec.flatten()
    return M


# ============================================================================
# AJUSTE DE ESFERA Y RANSAC
# ============================================================================

def ajustar_esfera(puntos):
    """Ajuste least-squares a esfera. Devuelve (centro, radio, rmse)."""
    centro_inicial = puntos.mean(axis=0)
    radio_inicial = np.linalg.norm(puntos - centro_inicial, axis=1).mean()
    params = [*centro_inicial, radio_inicial]

    def residuos(p, pts):
        cx, cy, cz, r = p
        return np.linalg.norm(pts - np.array([cx, cy, cz]), axis=1) - r

    res = least_squares(residuos, params, args=(puntos,))
    cx, cy, cz, r = res.x
    centro = np.array([cx, cy, cz])
    distancias = np.linalg.norm(puntos - centro, axis=1)
    rmse = np.sqrt(np.mean((distancias - r)**2))
    return centro, r, rmse


def ransac_pivote(poses, n_iter=1000, sample_size=20, umbral_inlier=1.5):
    """RANSAC para identificar inliers y ajustar esfera robustamente."""
    posiciones = poses[:, :3, 3]
    N = len(posiciones)

    np.random.seed(42)
    mejor_inliers = []
    for i in range(n_iter):
        idx = np.random.choice(N, min(sample_size, N), replace=False)
        try:
            centro, radio, _ = ajustar_esfera(posiciones[idx])
        except Exception:
            continue
        distancias = np.linalg.norm(posiciones - centro, axis=1)
        errores = np.abs(distancias - radio)
        inliers = np.where(errores < umbral_inlier)[0]
        if len(inliers) > len(mejor_inliers):
            mejor_inliers = inliers

    return mejor_inliers


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="tracker_config.yaml")
    parser.add_argument("--duracion", type=int, default=45,
                        help="Duracion del pivote en segundos")
    parser.add_argument("--output", default="poses_pivote_dodecaedro.npy",
                        help="Archivo donde guardar las poses capturadas")
    args = parser.parse_args()

    # Cargar config
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    K, dist = cargar_calibracion(cfg["camera"]["calibration_file"])
    print(f"[Calibracion intrinseca cargada]")

    # Diccionario
    dict_name = cfg["markers"]["dictionary"].upper()
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))

    # Geometria del rigid body
    rb_cfg = cfg["rigid_bodies"][0]
    rb_geom = cargar_rigid_body(rb_cfg["geometry_file"])
    print(f"[Rigid body cargado] {len(rb_geom)} marcadores: {sorted(rb_geom.keys())}")
    print(f"[Geometria] {rb_cfg['geometry_file']}")

    # Detector
    if hasattr(cv2.aruco, "ArucoDetector"):
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        usar_api_nueva = True
    else:
        detector = None
        params = cv2.aruco.DetectorParameters_create()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        usar_api_nueva = False

    # Camara
    backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
    cam_cfg = cfg["camera"]
    backend = backends.get(cam_cfg.get("backend", "MSMF").upper(), cv2.CAP_MSMF)
    cap = cv2.VideoCapture(int(cam_cfg["source"]), backend)
    if not cap.isOpened():
        print("ERROR: no se pudo abrir la camara")
        sys.exit(1)

    fourcc = cv2.VideoWriter_fourcc(*cam_cfg.get("fourcc", "MJPG"))
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg["height"])
    cap.set(cv2.CAP_PROP_FPS, cam_cfg.get("fps", 30))

    print(f"\n{'='*60}")
    print(f"  CAPTURA DE PIVOTE - Dodecaedro multi-marker")
    print(f"{'='*60}")
    print(f"\nINSTRUCCIONES:")
    print(f"  1. Clava la punta del tornillo en el carton con orificio.")
    print(f"  2. Mantén la PUNTA FIJA, pivotea solo el stylus.")
    print(f"  3. Cubre la mayor variedad de orientaciones (cono amplio).")
    print(f"  4. Movimientos suaves, sin tirones.")
    print(f"  5. El dodecaedro siempre visible a la cámara.")
    print(f"\nDuracion: {args.duracion} segundos")
    print(f"Comenzando en 5 segundos...")
    time.sleep(5)
    print("CAPTURANDO!")

    # Captura
    poses = []
    n_markers_promedio = []
    t_inicio = time.time()
    n_frames = 0
    last_print = t_inicio

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        n_frames += 1
        t_now = time.time()

        if t_now - t_inicio > args.duracion:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if usar_api_nueva:
            corners, ids, _ = detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)

        if ids is not None:
            detecciones = {}
            for i, mid in enumerate(ids.flatten().tolist()):
                if mid in rb_geom:
                    detecciones[int(mid)] = corners[i]
            if len(detecciones) >= 2:
                resultado = estimar_pose_rigid_body(detecciones, rb_geom, K, dist)
                if resultado is not None:
                    rvec, tvec = resultado
                    M = rvec_tvec_a_matriz(rvec, tvec)
                    poses.append(M)
                    n_markers_promedio.append(len(detecciones))

        # Visualizacion
        display = frame.copy()
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(display, corners, ids)
        elapsed = t_now - t_inicio
        cv2.putText(display, f"Pivote: {elapsed:.1f}s / {args.duracion}s",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(display, f"Poses: {len(poses)}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Pivote - q para parar antes", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        if t_now - last_print > 5.0:
            print(f"  [{elapsed:.0f}s] {len(poses)} poses capturadas")
            last_print = t_now

    cap.release()
    cv2.destroyAllWindows()

    print(f"\n[Captura terminada]")
    print(f"  Total poses: {len(poses)}")
    print(f"  Marcadores promedio por pose: {np.mean(n_markers_promedio):.2f}")

    if len(poses) < 50:
        print(f"\n[ERROR] Muy pocas poses para calibrar. Recapturar.")
        sys.exit(1)

    poses = np.array(poses)
    np.save(args.output, poses)
    print(f"  Guardadas en: {args.output}")

    # ========================================================================
    # PROCESAR CON RANSAC
    # ========================================================================
    print(f"\n{'='*60}")
    print(f"  PROCESAMIENTO RANSAC")
    print(f"{'='*60}\n")

    posiciones = poses[:, :3, 3]
    N = len(posiciones)

    inliers = ransac_pivote(poses, n_iter=1000, sample_size=20, umbral_inlier=1.5)
    n_inliers = len(inliers)
    pct_inliers = 100.0 * n_inliers / N
    print(f"Inliers: {n_inliers}/{N} ({pct_inliers:.1f}%)")

    posiciones_in = posiciones[inliers]
    centro_pivot, radio, rmse = ajustar_esfera(posiciones_in)
    print(f"\nAjuste a esfera (con inliers):")
    print(f"  Centro pivot (en frame camara): [{centro_pivot[0]:+.2f}, {centro_pivot[1]:+.2f}, {centro_pivot[2]:+.2f}] mm")
    print(f"  Radio: {radio:.2f} mm  (= distancia centro_dodecaedro a punta)")
    print(f"  RMSE: {rmse:.3f} mm")

    # Calcular offset del tip en frame del dodecaedro
    tips_en_dodecaedro = []
    for pose in poses[inliers]:
        pose_inv = np.linalg.inv(pose)
        tip_h = np.append(centro_pivot, 1.0)
        tip_d = (pose_inv @ tip_h)[:3]
        tips_en_dodecaedro.append(tip_d)
    tips_en_dodecaedro = np.array(tips_en_dodecaedro)

    offset = tips_en_dodecaedro.mean(axis=0)
    std = tips_en_dodecaedro.std(axis=0)
    print(f"\nOffset del tip (en frame del dodecaedro):")
    print(f"  Promedio: [{offset[0]:+.3f}, {offset[1]:+.3f}, {offset[2]:+.3f}] mm")
    print(f"  STD:      [{std[0]:.3f}, {std[1]:.3f}, {std[2]:.3f}] mm")
    print(f"  Magnitud: {np.linalg.norm(offset):.2f} mm")

    print(f"\n{'='*60}")
    print(f"  EVALUACION")
    print(f"{'='*60}")
    std_max = std.max()
    if std_max < 1.0:
        print(f"\n  [EXCELENTE] Std maximo: {std_max:.2f} mm < 1 mm")
        print(f"              Calibracion sub-milimetrica lograda.")
    elif std_max < 2.0:
        print(f"\n  [BUENO]     Std maximo: {std_max:.2f} mm < 2 mm")
        print(f"              Aceptable para navegacion quirurgica.")
    elif std_max < 5.0:
        print(f"\n  [REGULAR]   Std maximo: {std_max:.2f} mm")
        print(f"              Mejor que setup anterior pero no clinico.")
    else:
        print(f"\n  [INSUFICIENTE] Std maximo: {std_max:.2f} mm")
        print(f"                 Setup necesita mas ajuste.")

    # Guardar matriz StylusTipToDodecaedro
    matriz = np.eye(4)
    matriz[:3, 3] = offset
    np.save("StylusTipToDodecaedro.npy", matriz)

    with open("StylusTipToDodecaedro.txt", "w") as f:
        f.write(f"# Matriz StylusTipToDodecaedro 4x4\n")
        f.write(f"# Offset del tip respecto al centro del dodecaedro\n")
        f.write(f"# Calculada con {n_inliers} poses (RANSAC)\n")
        f.write(f"# Offset (mm): [{offset[0]:.3f}, {offset[1]:.3f}, {offset[2]:.3f}]\n")
        f.write(f"# Std (mm):    [{std[0]:.3f}, {std[1]:.3f}, {std[2]:.3f}]\n")
        f.write(f"# RMSE: {rmse:.3f} mm\n\n")
        for fila in matriz:
            f.write(" ".join(f"{v:12.6f}" for v in fila) + "\n")

    print(f"\n[Guardados]")
    print(f"  StylusTipToDodecaedro.npy")
    print(f"  StylusTipToDodecaedro.txt")


if __name__ == "__main__":
    main()