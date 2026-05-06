"""
Captura un dataset de detecciones del dodecaedro para auto-calibracion.

Durante 30-60 segundos, graba para cada frame:
- Que marcadores se detectan
- Las posiciones 2D de sus 4 esquinas en la imagen

Despues, calibrar_rigid_body.py usa estos datos para resolver el bundle adjustment
y deducir las posiciones REALES de los marcadores en el dodecaedro.

Uso:
    python captura_calibracion.py --duracion 60

Output: capturas_calibracion.npz con todos los datos.
"""

import argparse
import time
import sys

import cv2
import numpy as np
import yaml


def cargar_calibracion(ruta):
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    K = fs.getNode("camera_matrix").mat()
    dist = fs.getNode("distortion_coefficients").mat()
    fs.release()
    return K, dist


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="tracker_config.yaml")
    parser.add_argument("--duracion", type=int, default=60,
                        help="Duracion de captura en segundos")
    parser.add_argument("--output", default="capturas_calibracion.npz")
    args = parser.parse_args()

    # Cargar config
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    K, dist = cargar_calibracion(cfg["camera"]["calibration_file"])
    print(f"[Calibracion intrinseca cargada]")

    # Diccionario
    dict_name = cfg["markers"]["dictionary"].upper()
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))

    # IDs del rigid body
    rb_ids = set()
    for rb_cfg in cfg.get("rigid_bodies", []):
        with open(rb_cfg["geometry_file"], "r") as fg:
            for linea in fg:
                linea = linea.strip()
                if not linea or linea.startswith("#"):
                    continue
                vals = linea.split()
                if len(vals) >= 16:
                    rb_ids.add(int(vals[0]))
    print(f"[Rigid body IDs] {sorted(rb_ids)}")

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

    print(f"\nINSTRUCCIONES:")
    print(f"  1. El dodecaedro debe estar a 30-50 cm de la camara.")
    print(f"  2. Rota lentamente el dodecaedro mostrando TODAS las caras.")
    print(f"  3. Trata de mostrar combinaciones distintas de marcadores juntos.")
    print(f"  4. Mantenlo siempre dentro del frame, bien iluminado.")
    print(f"\nDuracion: {args.duracion} segundos")
    print(f"Comenzando en 3 segundos...")
    time.sleep(3)
    print("CAPTURANDO!")

    # Datos a guardar
    frames_data = []  # lista de dicts {timestamp, detecciones: {tag_id: corners(4,2)}}

    t_inicio = time.time()
    n_frames = 0
    n_frames_con_rb = 0
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

        # Filtrar solo marcadores del rigid body
        detecciones = {}
        if ids is not None:
            for i, mid in enumerate(ids.flatten().tolist()):
                if mid in rb_ids:
                    # corners[i] tiene shape (1, 4, 2)
                    detecciones[int(mid)] = corners[i].reshape(4, 2).copy()

        if len(detecciones) >= 2:  # solo guardar frames con >=2 marcadores (necesario para BA)
            frames_data.append({
                "timestamp": t_now - t_inicio,
                "detecciones": detecciones,
            })
            n_frames_con_rb += 1

        # Visualizacion
        display = frame.copy()
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(display, corners, ids)
        cv2.putText(display,
                    f"Frame {n_frames} | {len(detecciones)} markers | "
                    f"Capturados: {n_frames_con_rb}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        elapsed = t_now - t_inicio
        cv2.putText(display,
                    f"Tiempo: {elapsed:.1f}s / {args.duracion}s",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow("Captura calibracion - q para salir antes", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        if t_now - last_print > 5.0:
            print(f"  [{elapsed:.0f}s] {n_frames_con_rb} frames utiles capturados")
            last_print = t_now

    cap.release()
    cv2.destroyAllWindows()

    print(f"\n[Captura terminada]")
    print(f"  Frames totales: {n_frames}")
    print(f"  Frames utiles (>=2 marcadores): {n_frames_con_rb}")

    if n_frames_con_rb < 50:
        print(f"\n[ADVERTENCIA] Pocos frames utiles. Recomiendo al menos 100-200")
        print(f"  para una calibracion robusta. Considera repetir la captura.")

    # Estadisticas: cuantas veces se vio cada par de marcadores juntos
    pares_count = {}
    for fd in frames_data:
        ids = sorted(fd["detecciones"].keys())
        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                par = (ids[i], ids[j])
                pares_count[par] = pares_count.get(par, 0) + 1

    print(f"\n[Pares de marcadores observados juntos]")
    pares_ordenados = sorted(pares_count.items(), key=lambda x: -x[1])
    print(f"  Total pares unicos: {len(pares_ordenados)}")
    if pares_ordenados:
        print(f"  Mas frecuente: {pares_ordenados[0][0]} ({pares_ordenados[0][1]} frames)")
        print(f"  Menos frecuente: {pares_ordenados[-1][0]} ({pares_ordenados[-1][1]} frames)")

    # Guardar
    np.savez_compressed(args.output,
                        frames_data=np.array(frames_data, dtype=object),
                        K=K, dist=dist,
                        rb_ids=sorted(rb_ids))
    print(f"\n[Guardado] {args.output}")


if __name__ == "__main__":
    main()