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


def ransac_pivote(poses, n_iter=1000, sample_size=20, umbral_inlier=1.5, verbose=True):
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
        if verbose and (i + 1) % 200 == 0:
            print(f"    RANSAC {i+1}/{n_iter}: mejor inlier set = {len(mejor_inliers)}/{N}")

    return mejor_inliers


def ajustar_pivote_axb(poses):
    """Pivote por la formulacion AX=b clasica (Yaniv 2015 / PlusServer).

    Para cada pose i: R_i * t_dod + t_i = tip_cam (constante)
    Apilando: [R_i, -I] @ [t_dod; tip_cam] = -t_i  para todo i.
    Resuelve con least squares lineal cerrado.

    Devuelve (offset_dod, tip_cam, rmse).
    """
    N = len(poses)
    A = np.zeros((3 * N, 6))
    b = np.zeros(3 * N)
    for k, pose in enumerate(poses):
        A[3*k:3*k+3, :3] = pose[:3, :3]
        A[3*k:3*k+3, 3:6] = -np.eye(3)
        b[3*k:3*k+3] = -pose[:3, 3]
    x, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    offset_dod, tip_cam = x[:3], x[3:6]
    rmse = float(np.sqrt(np.mean((A @ x - b) ** 2)))
    return offset_dod, tip_cam, rmse


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
    backend_name = cam_cfg.get("backend", "MSMF").upper()
    backend = backends.get(backend_name, cv2.CAP_MSMF)
    print(f"[Camara] Abriendo source={cam_cfg['source']} backend={backend_name}...")
    t0 = time.time()
    cap = cv2.VideoCapture(int(cam_cfg["source"]), backend)
    if not cap.isOpened():
        print("ERROR: no se pudo abrir la camara")
        sys.exit(1)
    print(f"[Camara] Abierta en {time.time()-t0:.1f}s")

    print(f"[Camara] Configurando FOURCC={cam_cfg.get('fourcc','MJPG')} "
          f"{cam_cfg['width']}x{cam_cfg['height']} @ {cam_cfg.get('fps',30)} FPS...")
    fourcc = cv2.VideoWriter_fourcc(*cam_cfg.get("fourcc", "MJPG"))
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg["height"])
    cap.set(cv2.CAP_PROP_FPS, cam_cfg.get("fps", 30))
    # Warmup: leer 3 frames descartables para que la camara se estabilice
    print(f"[Camara] Warmup (descartando 3 frames iniciales)...")
    for _ in range(3):
        cap.read()
    print(f"[Camara] Lista para capturar.")

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
    # Guardado robusto: borrar archivo previo, escribir, fsync, verificar
    import os
    if os.path.exists(args.output):
        os.remove(args.output)
    np.save(args.output, poses)
    # Forzar flush a disco
    with open(args.output, "rb+") as f:
        f.flush()
        os.fsync(f.fileno())
    # Verificar que se guardo correctamente
    poses_releidas = np.load(args.output)
    if poses_releidas.shape != poses.shape:
        print(f"[ERROR] {args.output} se truncó al guardar: "
              f"esperaba shape {poses.shape}, encontré {poses_releidas.shape}")
        sys.exit(1)
    print(f"  Guardadas en: {args.output} ({poses_releidas.shape[0]} poses, verificadas)")

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

    # ========================================================================
    # CROSS-CHECK: AX=b clasico (Yaniv) sobre los mismos inliers
    # ========================================================================
    print(f"\n{'='*60}")
    print(f"  CROSS-CHECK: AX=b (Yaniv 2015) sobre inliers")
    print(f"{'='*60}\n")
    offset_axb, tip_cam_axb, axb_rmse = ajustar_pivote_axb(poses[inliers])
    print(f"  Offset (AX=b):      [{offset_axb[0]:+.3f}, {offset_axb[1]:+.3f}, {offset_axb[2]:+.3f}] mm")
    print(f"  Tip cam (AX=b):     [{tip_cam_axb[0]:+.3f}, {tip_cam_axb[1]:+.3f}, {tip_cam_axb[2]:+.3f}] mm")
    print(f"  Magnitud:           {np.linalg.norm(offset_axb):.3f} mm")
    print(f"  AX=b RMSE:          {axb_rmse:.3f} mm")

    diff_offset = offset_axb - offset
    diff_norm = float(np.linalg.norm(diff_offset))
    print(f"\n  Diferencia esfera vs AX=b: {diff_norm:.3f} mm")
    if diff_norm > 2.0:
        print(f"  [!] DISCREPANCIA > 2 mm entre metodos. Probable causa fisica:")
        print(f"      - Punta no perfectamente fija (se deslizo en el carton).")
        print(f"      - Barra entre dodecaedro y punta con juego/flexion.")
        print(f"      - Pocos markers/pose (objetivo >=3).")
        print(f"  Considera re-clavar mejor la punta y re-capturar.")
    elif diff_norm > 0.5:
        print(f"  [ok] Pequena discrepancia, dentro de lo aceptable por ruido.")
    else:
        print(f"  [excelente] Ambos metodos coinciden, calibracion robusta.")

    # ========================================================================
    # EVALUACION
    # ========================================================================
    print(f"\n{'='*60}")
    print(f"  EVALUACION")
    print(f"{'='*60}")
    std_max = std.max()
    if std_max < 1.0:
        print(f"\n  [EXCELENTE] Std maximo: {std_max:.2f} mm < 1 mm")
    elif std_max < 2.0:
        print(f"\n  [BUENO]     Std maximo: {std_max:.2f} mm < 2 mm")
    elif std_max < 5.0:
        print(f"\n  [REGULAR]   Std maximo: {std_max:.2f} mm")
    else:
        print(f"\n  [INSUFICIENTE] Std maximo: {std_max:.2f} mm")
    if np.mean(n_markers_promedio) < 3.0:
        print(f"\n  [!] Promedio de markers/pose = {np.mean(n_markers_promedio):.2f} (objetivo >=3).")
    print(f"\n  Nota: la STD mide DISPERSION entre poses, NO error absoluto.")
    print(f"        Si los dos metodos (esfera y AX=b) coinciden, la calibracion es buena.")

    # Guardar matriz StylusTipToDodecaedro
    matriz = np.eye(4)
    matriz[:3, 3] = offset
    np.save("StylusTipToDodecaedro.npy", matriz)

    with open("StylusTipToDodecaedro.txt", "w") as f:
        f.write(f"# Matriz StylusTipToDodecaedro 4x4\n")
        f.write(f"# Offset del tip respecto al centro del dodecaedro\n")
        f.write(f"# Calculada con {n_inliers} poses (RANSAC + sphere fit)\n")
        f.write(f"# Markers promedio por pose: {np.mean(n_markers_promedio):.2f}\n")
        f.write(f"#\n")
        f.write(f"# METODO PRINCIPAL (esfera + transform):\n")
        f.write(f"#   Offset (mm): [{offset[0]:+.3f}, {offset[1]:+.3f}, {offset[2]:+.3f}]\n")
        f.write(f"#   Magnitud:    {np.linalg.norm(offset):.3f} mm\n")
        f.write(f"#   Std (mm):    [{std[0]:.3f}, {std[1]:.3f}, {std[2]:.3f}]\n")
        f.write(f"#   RMSE esfera: {rmse:.3f} mm\n")
        f.write(f"#\n")
        f.write(f"# CROSS-CHECK (AX=b clasico, Yaniv 2015):\n")
        f.write(f"#   Offset (mm): [{offset_axb[0]:+.3f}, {offset_axb[1]:+.3f}, {offset_axb[2]:+.3f}]\n")
        f.write(f"#   Magnitud:    {np.linalg.norm(offset_axb):.3f} mm\n")
        f.write(f"#   AX=b RMSE:   {axb_rmse:.3f} mm\n")
        f.write(f"#   Diff vs esfera: {diff_norm:.3f} mm\n")
        f.write(f"#\n")
        for fila in matriz:
            f.write(" ".join(f"{v:12.6f}" for v in fila) + "\n")

    print(f"\n[Guardados]")
    print(f"  StylusTipToDodecaedro.npy")
    print(f"  StylusTipToDodecaedro.txt")


if __name__ == "__main__":
    main()
