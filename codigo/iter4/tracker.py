"""
Tracker ArUco con IPPE_SQUARE para navegacion quirurgica.
Soporta marcadores individuales Y rigid bodies multi-marker (ej: dodecaedro).

Cuando se ven multiples marcadores del mismo rigid body, calcula UNA sola pose
optima usando todos los puntos 3D-2D combinados con cv2.solvePnP.

Uso:
    python tracker.py --config tracker_config.yaml

Slicer debe conectarse como CLIENTE a:
    - localhost:18944 para transformadas
    - localhost:18945 para video (si send_video=true)

Presiona 'q' en la ventana de video para salir.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation as _Rot
import pyigtl
import yaml

# Backend abstracto de camara (iter 4): permite webcam o femtobolt via config.
from camera_backend import create_backend


# ============================================================================
# CARGA DE CONFIGURACION Y CALIBRACION
# ============================================================================

def cargar_config(ruta):
    """Carga el YAML de config y resuelve las rutas de archivos (geometry_file,
    calibration_file) probando relativas al cwd y al directorio del config.
    Asi el tracker corre desde cualquier carpeta (codigo\\ o codigo\\iter4\\)."""
    cfg_dir = Path(ruta).resolve().parent
    with open(ruta, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    def _resolver(p):
        if not p:
            return p
        for cand in (Path(p), cfg_dir / p):
            if cand.exists():
                return str(cand)
        return p

    for rb in cfg.get("rigid_bodies", []) or []:
        if rb.get("geometry_file"):
            rb["geometry_file"] = _resolver(rb["geometry_file"])
    cam = cfg.get("camera", {}) or {}
    if cam.get("calibration_file"):
        cam["calibration_file"] = _resolver(cam["calibration_file"])
    return cfg


def cargar_calibracion(ruta):
    """Lee el archivo de calibracion OpenCV YAML y devuelve (K, dist)."""
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"No se pudo abrir el archivo de calibracion: {ruta}")

    K_node = fs.getNode("camera_matrix")
    if K_node.empty():
        raise ValueError("El archivo no contiene 'camera_matrix'")
    K = K_node.mat()

    dist_node = fs.getNode("distortion_coefficients")
    if dist_node.empty():
        raise ValueError("El archivo no contiene 'distortion_coefficients'")
    dist = dist_node.mat()

    fs.release()

    print(f"[Calibracion] Cargada de: {ruta}")
    print(f"  K = \n{K}")
    print(f"  dist = {dist.flatten()}")
    return K, dist


def cargar_rigid_body(ruta):
    """Carga el archivo de geometria del rigid body.

    Formato: cada linea con tag_id, centro (3), 4 esquinas (12 valores)
    Devuelve dict {tag_id: array(4, 3) con las 4 esquinas en 3D}
    """
    rigid_body = {}
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            valores = linea.split()
            if len(valores) < 16:
                continue
            tag_id = int(valores[0])
            # valores[1:4] = centro (no lo usamos directamente, lo derivamos)
            # valores[4:7]   = c0 (top-left)
            # valores[7:10]  = c1 (top-right)
            # valores[10:13] = c2 (bottom-right)
            # valores[13:16] = c3 (bottom-left)
            esquinas = np.array([
                [float(valores[4]),  float(valores[5]),  float(valores[6])],
                [float(valores[7]),  float(valores[8]),  float(valores[9])],
                [float(valores[10]), float(valores[11]), float(valores[12])],
                [float(valores[13]), float(valores[14]), float(valores[15])],
            ], dtype=np.float32)
            rigid_body[tag_id] = esquinas

    print(f"[Rigid body] Cargados {len(rigid_body)} marcadores de {ruta}")
    return rigid_body


# ============================================================================
# DICCIONARIO ARUCO
# ============================================================================

def obtener_diccionario(nombre):
    """Devuelve el objeto diccionario ArUco segun el nombre."""
    nombre = nombre.upper()
    if not hasattr(cv2.aruco, nombre):
        disponibles = [x for x in dir(cv2.aruco) if "DICT" in x]
        raise ValueError(
            f"Diccionario '{nombre}' no disponible.\n"
            f"Disponibles: {disponibles}"
        )
    constante = getattr(cv2.aruco, nombre)
    return cv2.aruco.getPredefinedDictionary(constante)


# Mapeo de claves YAML snake_case -> atributos de cv2.aruco.DetectorParameters camelCase.
# Solo incluimos los que tunear cambia algo real para nuestro caso (markers chicos,
# angulos grazing, iluminacion variable). El resto deja sus defaults.
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
    """Sobreescribe atributos del DetectorParameters segun cfg_det (dict).

    cfg_det son las claves bajo cfg['markers']['detector'] en el YAML.
    Si una clave no esta, queda el default. Imprime cada valor aplicado.
    """
    if not cfg_det:
        print("[Detector] Usando DetectorParameters por defecto.")
        return
    print("[Detector] Tuning DetectorParameters:")
    for yaml_key, attr_name in _DETECTOR_PARAM_KEYS.items():
        if yaml_key in cfg_det:
            valor = cfg_det[yaml_key]
            if hasattr(params, attr_name):
                setattr(params, attr_name, valor)
                print(f"  {attr_name} = {valor}")
            else:
                print(f"  [WARN] DetectorParameters no tiene atributo {attr_name}, ignorado.")


# ============================================================================
# CONFIGURAR LA CAMARA
# ============================================================================

def abrir_camara(cfg_cam):
    """Abre la camara con los parametros indicados."""
    backends = {
        "DSHOW": cv2.CAP_DSHOW,
        "MSMF": cv2.CAP_MSMF,
        "ANY": cv2.CAP_ANY,
    }
    backend = backends.get(cfg_cam.get("backend", "DSHOW").upper(), cv2.CAP_DSHOW)

    cap = cv2.VideoCapture(int(cfg_cam["source"]), backend)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir la camara source={cfg_cam['source']}")

    fourcc_str = cfg_cam.get("fourcc", None)
    if fourcc_str:
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg_cam["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg_cam["height"])
    cap.set(cv2.CAP_PROP_FPS, cfg_cam.get("fps", 30))

    fourcc_real = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str_real = "".join([chr((fourcc_real >> 8 * i) & 0xFF) for i in range(4)])
    print(f"[Camara] Abierta:")
    print(f"  Resolucion: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"  FPS reportado: {cap.get(cv2.CAP_PROP_FPS):.1f}")
    print(f"  FOURCC: {fourcc_str_real}")
    return cap


# ============================================================================
# ESTIMACION DE POSE
# ============================================================================

def construir_object_points(size_mm):
    """4 esquinas de un marcador individual centrado en su origen local."""
    half = size_mm / 2.0
    return np.array(
        [
            [-half,  half, 0],   # c0 = top-left
            [ half,  half, 0],   # c1 = top-right
            [ half, -half, 0],   # c2 = bottom-right
            [-half, -half, 0],   # c3 = bottom-left
        ],
        dtype=np.float32,
    )


def estimar_pose_individual(corners_2d, size_mm, K, dist):
    """Pose de un marcador individual con SOLVEPNP_IPPE_SQUARE.

    IPPE_SQUARE devuelve la mejor de las DOS soluciones posibles para un
    marker planar (espejada en el plano de imagen). A veces el ranking de
    OpenCV elige la solucion equivocada, que termina con la marker DETRAS
    de la camara (tvec[2] < 0). Filtramos esos casos como invalidos en
    lugar de propagarlos a Slicer.

    Devuelve (rvec, tvec) o None si falla o si la pose es invalida (z<=0).
    """
    object_pts = construir_object_points(size_mm)
    image_pts = corners_2d.reshape(4, 2).astype(np.float32)

    ok, rvec, tvec = cv2.solvePnP(
        object_pts, image_pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE
    )
    if not ok:
        return None
    if float(tvec[2, 0]) <= 0:
        # Marker fisicamente DETRAS de la camara: ambiguedad planar de IPPE,
        # la solucion correcta es la espejada que no estamos pidiendo aca.
        return None
    return rvec, tvec


def estimar_pose_rigid_body(detecciones, rigid_body_geom, K, dist):
    """Pose conjunta de un rigid body usando todos los marcadores visibles.

    detecciones: dict {tag_id: corners_2d (shape 1x4x2)}
    rigid_body_geom: dict {tag_id: esquinas_3d (shape 4x3)}

    Combina los puntos 3D-2D de todos los marcadores visibles del rigid body
    y resuelve cv2.solvePnP con todos ellos. Esto es matematicamente optimo:
    aprovecha toda la informacion disponible para una sola estimacion robusta.

    Devuelve (rvec, tvec, n_marcadores_usados) o None si no se pudo resolver.
    """
    object_pts_list = []
    image_pts_list = []
    n_usados = 0

    for tag_id, corners_2d in detecciones.items():
        if tag_id not in rigid_body_geom:
            continue
        # Esquinas 3D en sistema del dodecaedro (4x3)
        obj_3d = rigid_body_geom[tag_id]
        # Esquinas 2D en imagen (4x2)
        img_2d = corners_2d.reshape(4, 2).astype(np.float32)
        object_pts_list.append(obj_3d)
        image_pts_list.append(img_2d)
        n_usados += 1

    if n_usados == 0:
        return None

    # Concatenar todos los puntos: shape (4*N, 3) y (4*N, 2)
    all_object_pts = np.concatenate(object_pts_list, axis=0).astype(np.float32)
    all_image_pts = np.concatenate(image_pts_list, axis=0).astype(np.float32)

    if n_usados == 1:
        # Con un solo marcador, IPPE_SQUARE devuelve las 2 soluciones espejadas.
        # solvePnPGeneric nos da ambas y elegimos la de menor reprojection error
        # CON tvec[2] > 0 (la otra suele tener el marker detras de la camara).
        n_sol, rvecs, tvecs, errors = cv2.solvePnPGeneric(
            all_object_pts, all_image_pts, K, dist,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if n_sol == 0:
            return None
        # Filtrar soluciones invalidas (z<=0)
        candidatos = [(i, errors[i][0] if errors is not None else 0.0)
                      for i in range(n_sol)
                      if float(tvecs[i][2, 0]) > 0]
        if not candidatos:
            return None
        # Tomar la de menor error de reproyeccion
        i_best = min(candidatos, key=lambda c: c[1])[0]
        rvec = rvecs[i_best]
        tvec = tvecs[i_best]
        ok = True
    else:
        # Con multiples marcadores no coplanares, ITERATIVE da mejor resultado
        # (IPPE_SQUARE es solo para puntos planares)
        ok, rvec, tvec = cv2.solvePnP(
            all_object_pts, all_image_pts, K, dist,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        if ok:
            # Refinamiento iterativo Levenberg-Marquardt
            rvec, tvec = cv2.solvePnPRefineLM(
                all_object_pts, all_image_pts, K, dist, rvec, tvec
            )

            # --- RECHAZO DE OUTLIERS (iter 5) ---
            # Un marcador mal detectado (esquina equivocada, casi coplanar,
            # intermitente) corrompe el PnP conjunto. Calculamos el error de
            # reproyeccion POR MARCADOR, descartamos los que se salen y
            # re-resolvemos solo con los buenos. Quita los picos de orientacion
            # que metia un marcador con reproyeccion alta (diagnostico estatico).
            errs = np.array([
                float(np.mean(np.linalg.norm(
                    cv2.projectPoints(obj_m, rvec, tvec, K, dist)[0].reshape(4, 2)
                    - img_m, axis=1)))
                for obj_m, img_m in zip(object_pts_list, image_pts_list)
            ])
            umbral = max(2.0, 2.5 * float(np.median(errs)))
            inliers = errs <= umbral
            # Requiere >=3 inliers (2 casi coplanares dan pose degenerada).
            if 3 <= int(inliers.sum()) < n_usados:
                obj_in = np.concatenate(
                    [object_pts_list[i] for i in range(n_usados) if inliers[i]],
                    axis=0).astype(np.float32)
                img_in = np.concatenate(
                    [image_pts_list[i] for i in range(n_usados) if inliers[i]],
                    axis=0).astype(np.float32)
                ok2, rvec2, tvec2 = cv2.solvePnP(
                    obj_in, img_in, K, dist, rvec.copy(), tvec.copy(),
                    useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
                if ok2:
                    rvec2, tvec2 = cv2.solvePnPRefineLM(obj_in, img_in, K, dist, rvec2, tvec2)
                    # ACEPTAR SOLO si la pose refinada esta CERCA de la original.
                    # Quitar un marcador malo refina (mm/grados), NO salta. Un salto
                    # grande = re-solve degenerado -> revertir a la pose con todos.
                    R1, _ = cv2.Rodrigues(rvec)
                    R2, _ = cv2.Rodrigues(rvec2)
                    d_ang = np.degrees(np.arccos(np.clip(
                        (np.trace(R1.T @ R2) - 1.0) / 2.0, -1.0, 1.0)))
                    d_t = float(np.linalg.norm(tvec2.flatten() - tvec.flatten()))
                    if d_ang < 15.0 and d_t < 20.0:
                        rvec, tvec = rvec2, tvec2
                        n_usados = int(inliers.sum())

    if not ok:
        return None

    # Filtro final: descartar poses con z<=0 (marker detras de la camara).
    # Aparece cuando los markers usados son casi coplanares y la solucion
    # se invierte (visto en log iter 4: t=[..., ..., -589.8] con 4 markers
    # del anillo inferior).
    if float(tvec[2, 0]) <= 0:
        return None

    return rvec, tvec, n_usados


def rvec_tvec_a_matriz(rvec, tvec):
    """Convierte rvec/tvec a matriz homogenea 4x4."""
    R, _ = cv2.Rodrigues(rvec)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = tvec.flatten()
    return M


# ============================================================================
# 1-EURO FILTER (opcional)
# ============================================================================

class OneEuroFilter:
    """Filtro 1-Euro para suavizado adaptativo."""

    def __init__(self, min_cutoff=1.0, beta=0.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filtrar(self, x, t):
        if self.t_prev is None:
            self.t_prev = t
            self.x_prev = x
            return x
        dt = max(t - self.t_prev, 1e-3)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(1.0, dt)
        dx_smooth = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * np.abs(dx_smooth)
        a = self._alpha(cutoff, dt)
        x_smooth = a * x + (1 - a) * self.x_prev
        self.x_prev = x_smooth
        self.dx_prev = dx_smooth
        self.t_prev = t
        return x_smooth


# ============================================================================
# LOOP PRINCIPAL
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="tracker_config.yaml")
    args = parser.parse_args()

    cfg = cargar_config(args.config)

    # === Backend de camara (iter 4: webcam o femtobolt) ===
    # Se crea aca pero se abre mas adelante (despues del setup de OpenIGTLink).
    cam = create_backend(cfg["camera"])

    # === Diccionario ArUco ===
    aruco_dict = obtener_diccionario(cfg["markers"]["dictionary"])

    cfg_det = cfg["markers"].get("detector", {}) or {}
    if hasattr(cv2.aruco, "ArucoDetector"):
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        aplicar_detector_params(params, cfg_det)
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        usar_api_nueva = True
    else:
        detector = None
        params = cv2.aruco.DetectorParameters_create()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        aplicar_detector_params(params, cfg_det)
        usar_api_nueva = False

    # === Marcadores individuales (no rigid body) ===
    markers_individuales = {m["id"]: m for m in cfg["markers"].get("list", [])}
    print(f"[Marcadores individuales] IDs: {list(markers_individuales.keys())}")

    # === Rigid bodies ===
    rigid_bodies = {}
    rigid_body_ids = set()
    for rb_cfg in cfg.get("rigid_bodies", []):
        nombre = rb_cfg["name"]
        ruta_geom = rb_cfg["geometry_file"]
        rb_geom = cargar_rigid_body(ruta_geom)
        rigid_bodies[nombre] = rb_geom
        rigid_body_ids.update(rb_geom.keys())
        print(f"[Rigid body '{nombre}'] IDs: {sorted(rb_geom.keys())}")

    # === Whitelist de IDs ===
    # IDs que el tracker realmente usa (rigid body + marcadores individuales).
    # Todo lo demas (fantasmas de stickers/texturas que el detector permisivo
    # decodifica como IDs ajenos) se descarta justo tras detectar. No toca los
    # DetectorParameters; independiente de camara, sirve igual al doctor.
    ids_conocidos = set(rigid_body_ids) | set(markers_individuales.keys())
    print(f"[Whitelist] IDs aceptados: {sorted(ids_conocidos)}")

    # === Filtros (opcional) ===
    filtros_individuales = {}
    filtros_rigid_bodies = {}
    filtros_rigid_bodies_rot = {}
    prev_quat = {}
    if cfg["filtering"]["enabled"]:
        for mid in markers_individuales:
            filtros_individuales[mid] = [
                OneEuroFilter(cfg["filtering"]["min_cutoff"],
                              cfg["filtering"]["beta"]) for _ in range(3)
            ]
        for nombre in rigid_bodies:
            filtros_rigid_bodies[nombre] = [
                OneEuroFilter(cfg["filtering"]["min_cutoff"],
                              cfg["filtering"]["beta"]) for _ in range(3)
            ]
            filtros_rigid_bodies_rot[nombre] = [
                OneEuroFilter(cfg["filtering"]["min_cutoff"],
                              cfg["filtering"]["beta"]) for _ in range(4)
            ]
        print("[Filtrado] 1-Euro filter activado.")

    # === Servidores OpenIGTLink ===
    server_tx = pyigtl.OpenIGTLinkServer(port=cfg["igtlink"]["transforms_port"])
    print(f"[OpenIGTLink] Transformadas en puerto {cfg['igtlink']['transforms_port']}")

    server_video = None
    if cfg["igtlink"]["send_video"]:
        server_video = pyigtl.OpenIGTLinkServer(port=cfg["igtlink"]["video_port"])
        print(f"[OpenIGTLink] Video en puerto {cfg['igtlink']['video_port']}")

    print("[Esperando] Conecta Slicer como cliente a estos puertos.")
    print("Presiona 'q' en la ventana para salir.")

    # === Camara (iter 4: abre webcam o femtobolt segun config) ===
    # El warmup se hace dentro de cam.open(), no aca.
    cam.open()
    K, dist = cam.get_intrinsics()
    print(f"[Calibracion] K cargada de la camara:\n{K}")
    print(f"  dist = {dist}")

    # === Loop principal ===
    show_window = cfg.get("debug", {}).get("show_window", True)
    verbose = cfg.get("debug", {}).get("verbose", False)
    n_frames = 0
    t_inicio = time.time()
    last_fps_print = t_inicio

    try:
        n_fail_consec = 0
        while True:
            frame, depth_mm, ts = cam.read()
            if frame is None:
                n_fail_consec += 1
                if n_fail_consec in (1, 30, 100, 300):
                    print(f"[WARN] cam.read() retornando None ({n_fail_consec} consecutivos)")
                if n_fail_consec > 300:
                    print("[ERROR] Camara no entrega frames. Saliendo.")
                    break
                continue
            if n_frames == 0:
                print(f"[Camara] Primer frame OK: shape={frame.shape}, dtype={frame.dtype}")
            if n_fail_consec > 0:
                print(f"[Camara] Recuperada tras {n_fail_consec} fallos")
                n_fail_consec = 0
            n_frames += 1
            t_now = time.time()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if usar_api_nueva:
                corners, ids, rejected = detector.detectMarkers(gray)
            else:
                corners, ids, rejected = cv2.aruco.detectMarkers(
                    gray, aruco_dict, parameters=params
                )

            # Whitelist: descarta IDs ajenos (fantasmas) antes de procesar.
            if ids is not None and len(ids) > 0:
                keep = [i for i, mid in enumerate(ids.flatten().tolist())
                        if int(mid) in ids_conocidos]
                if len(keep) < len(ids):
                    corners = tuple(corners[i] for i in keep)
                    ids = ids[keep] if keep else None

            display = frame.copy() if show_window else None

            if ids is not None and len(ids) > 0:
                ids_flat = ids.flatten().tolist()

                # === Procesar rigid bodies ===
                min_markers_rb = cfg.get("rigid_bodies_quality", {}).get("min_markers", 1)
                for nombre, rb_geom in rigid_bodies.items():
                    detecciones_rb = {}
                    for i, mid in enumerate(ids_flat):
                        if mid in rb_geom:
                            detecciones_rb[mid] = corners[i]

                    if len(detecciones_rb) < min_markers_rb:
                        # Pose con pocos markers es inestable (jitter rotacional).
                        # Descartar para no enviar transformadas ruidosas a Slicer.
                        if show_window and len(detecciones_rb) > 0:
                            cv2.putText(display,
                                f"{nombre}: solo {len(detecciones_rb)} markers (req >= {min_markers_rb})",
                                (10, 30 + len(rigid_bodies)*25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 255), 2)
                        continue

                    resultado = estimar_pose_rigid_body(detecciones_rb, rb_geom, K, dist)
                    if resultado is None:
                        continue
                    rvec, tvec, n_usados = resultado

                    # Filtrar posicion
                    if nombre in filtros_rigid_bodies:
                        f = filtros_rigid_bodies[nombre]
                        tvec_flat = tvec.flatten()
                        tvec_filt = np.array(
                            [f[j].filtrar(tvec_flat[j], t_now) for j in range(3)]
                        )
                        tvec = tvec_filt.reshape(3, 1)

                    # Filtrar ROTACION (cuaternion 1-Euro, con continuidad de signo).
                    # Antes solo se filtraba la posicion -> la orientacion temblaba.
                    if nombre in filtros_rigid_bodies_rot:
                        fr = filtros_rigid_bodies_rot[nombre]
                        q = _Rot.from_rotvec(rvec.flatten()).as_quat()  # [x,y,z,w]
                        pq = prev_quat.get(nombre)
                        if pq is not None and float(np.dot(q, pq)) < 0.0:
                            q = -q   # hemisferio consistente, evita saltos de signo
                        qf = np.array([fr[j].filtrar(float(q[j]), t_now) for j in range(4)])
                        nq = float(np.linalg.norm(qf))
                        if nq > 1e-9:
                            qf = qf / nq
                            prev_quat[nombre] = qf
                            rvec = _Rot.from_quat(qf).as_rotvec().reshape(3, 1)

                    M = rvec_tvec_a_matriz(rvec, tvec)
                    msg = pyigtl.TransformMessage(M, device_name=f"{nombre}ToTracker")
                    server_tx.send_message(msg)

                    # Visualizacion
                    if show_window:
                        for mid in detecciones_rb:
                            i = ids_flat.index(mid)
                            cv2.aruco.drawDetectedMarkers(display, [corners[i]],
                                                          np.array([[mid]]))
                        # Dibujar ejes del rigid body en su origen (centro del dodecaedro)
                        cv2.drawFrameAxes(display, K, dist, rvec, tvec, 30.0)
                        # Texto con info
                        cv2.putText(display, f"{nombre}: {n_usados} markers",
                                    (10, 30 + len(rigid_bodies)*25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                    if verbose:
                        ids_del_rb = sorted(detecciones_rb.keys())
                        print(f"  [{nombre}] {n_usados} markers IDs={ids_del_rb}, "
                              f"t=[{tvec[0,0]:.1f}, {tvec[1,0]:.1f}, {tvec[2,0]:.1f}]")

                # === Procesar marcadores individuales (que NO pertenecen a rigid bodies) ===
                for i, mid in enumerate(ids_flat):
                    if mid in rigid_body_ids:
                        continue  # ya procesado como rigid body
                    if mid not in markers_individuales:
                        continue

                    info = markers_individuales[mid]
                    size_mm = info["size_mm"]
                    name = info["name"]

                    pose = estimar_pose_individual(corners[i], size_mm, K, dist)
                    if pose is None:
                        continue
                    rvec, tvec = pose

                    if mid in filtros_individuales:
                        f = filtros_individuales[mid]
                        tvec_flat = tvec.flatten()
                        tvec_filt = np.array(
                            [f[j].filtrar(tvec_flat[j], t_now) for j in range(3)]
                        )
                        tvec = tvec_filt.reshape(3, 1)

                    M = rvec_tvec_a_matriz(rvec, tvec)
                    msg = pyigtl.TransformMessage(M, device_name=f"{name}ToTracker")
                    server_tx.send_message(msg)

                    if show_window:
                        cv2.aruco.drawDetectedMarkers(display, [corners[i]],
                                                      np.array([[mid]]))
                        cv2.drawFrameAxes(display, K, dist, rvec, tvec, size_mm * 0.5)

            # Enviar video
            if server_video is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                msg_img = pyigtl.ImageMessage(rgb, device_name="Image")
                server_video.send_message(msg_img)

            if show_window:
                cv2.imshow("Tracker Multi-Marker - q para salir", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if t_now - last_fps_print > 5.0:
                fps = n_frames / (t_now - t_inicio)
                print(f"[FPS] Promedio: {fps:.1f}")
                last_fps_print = t_now

    except KeyboardInterrupt:
        print("\n[Interrupcion del usuario]")
    finally:
        cam.close()
        if show_window:
            cv2.destroyAllWindows()
        try:
            server_tx.close()
        except Exception:
            pass
        if server_video is not None:
            try:
                server_video.close()
            except Exception:
                pass
        print("[Salida limpia]")


if __name__ == "__main__":
    main()
