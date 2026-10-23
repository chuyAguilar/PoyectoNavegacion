# -*- coding: utf-8 -*-
"""
medir_modos.py -- Enfoque, exposicion y medicion de resolucion x formato de una
camara SVPRO por su perfil (meta 002, fase 3).

Abre la camara SIEMPRE por su perfil (camera_backend: puerto, marca, ajustes y
tamano); la exposicion candidata va en los `controls` de una copia en memoria
del perfil, asi la capa DSHOW (ajustes_camara) la escribe y la relee antes de
abrir el video por MSMF, y cada fila anota esa lectura (`exposicion_leida_ms`).
Este modulo importa camaras_uvc antes que cv2: la aceleracion HW de MSMF queda
apagada (CONTEXT.md 4.18) y el JSON lo registra en `aceleracion_msmf`.

Cuatro modos, uno por corrida (todos con --config, --salida y --timeout):

  --enfocar [--modo WxH:FOURCC --fps N]
      Ventana con la nitidez (varianza del laplaciano) del frame y su maximo:
      el autor gira la rosca del lente con el tablero a ~60 cm y la fija donde
      la nitidez es mayor. q para terminar. El JSON guarda la nitidez final y
      la maxima.

  --exposiciones-ms 7.813,3.906,1.953,0.977,0.488 --modo 1280x960:MJPG --fps 90
      --segundos-captura 10 --fov-grados 84 --luz "..."
      Medicion 1: por candidata, FPS de captura (solo leyendo frames), y sobre
      una muestra de esos frames (uno cada MUESTRA_CADA_S) el brillo medio, la
      fraccion saturada sobre el dodecaedro y la mediana de markers. Elige la
      exposicion (elegir_exposicion) y dice si la exposicion pedida cambia de
      verdad el brillo (exposicion_cambia_brillo).

  --modos 320x240:MJPG,640x480:MJPG,... [--modos-solo-captura 1920x1080:MJPG,...]
      --fps 90 --segundos-captura 10 --segundos-tracking 30 --fov-grados 84
      --luz "..." [--exposicion-ms 3.906]
      Medicion 2: por modo, tamano real, exposicion leida, FPS de captura, FPS
      de tracking sin y con ventana (deteccion + lista blanca + pose del
      dodecaedro + 1-Euro, con las funciones de tracker.py; sin pyigtl),
      mediana de markers y fraccion de frames con pose. Los de
      --modos-solo-captura solo captura (y la muestra). Con --intrinsecos
      RUTA.yml (fase 4, B33) la pose usa la K real del backend (el modo tiene
      que ser el del .yml) y --fov-grados sobra.

  --elegir A.json B.json
      Sin camara: con los JSON de las dos camaras de la misma medicion, la
      exposicion comun (elegir_exposicion_comun) o la resolucion
      (elegir_resolucion: la de mas pixeles con FPS de tracking con ventana
      >= 90 * (1 - 0.02) en las dos, P8/P11) y las tablas.

Los FPS de captura se miden solo leyendo frames (sesion del 2026-10-21/22:
calcular brillo o nitidez por frame en el mismo bucle baja la cifra a 36-42 a
1280x960 frente a 90 de captura): brillo, saturacion y markers se calculan
despues sobre la muestra. Los FPS de tracking si incluyen todo el trabajo por
frame, como en el tracker (es la cifra que cuenta, P2).

Los intrinsecos: los perfiles gs1/gs2 no tienen .yml hasta las fases 4 y 5, y
un .yml vale para un solo tamano; aqui la pose usa una K nominal por modo
(k_nominal: fx = fy = (W/2) / tan(fov/2), centro en el medio, sin distorsion)
con --fov-grados explicito (SVPRO: lente de ~83-85 grados). Sirve para el
tiempo por frame y para saber si solvePnP resuelve; la pose en mm no vale.

Cada fila se escribe en el JSON al medirla (B25); todo lleva --timeout y la
camara se libera (principio 9); los argumentos van explicitos (principio 7).

Context7 (2026-10-22, OpenCV 4.13; instalado 4.11): ArucoDetector.detectMarkers
(corners Nx4 en sentido horario, ids N), Dictionary.generateImageMarker (para
las pruebas), convexHull, fillConvexPoly, dilate + getStructuringElement
(la envolvente con margen de fraccion_saturada).

Ejemplos (desde codigo\\, con el venv):

    python iter4\\medir_modos.py --config iter4\\tracker_config_gs1.yaml --enfocar ^
        --modo 1280x960:MJPG --fps 90 ^
        --salida "..\\Claude outputs\\camaras\\enfoque_gs1.json" --timeout 600
    python iter4\\medir_modos.py --config iter4\\tracker_config_gs1.yaml ^
        --exposiciones-ms 7.813,3.906,1.953,0.977,0.488 --modo 1280x960:MJPG --fps 90 ^
        --segundos-captura 10 --fov-grados 84 --luz "caja nivel 2" ^
        --salida "..\\Claude outputs\\camaras\\exposicion_gs1.json" --timeout 600
    python iter4\\medir_modos.py --config iter4\\tracker_config_gs1.yaml ^
        --modos 320x240:MJPG,640x480:MJPG,960x720:MJPG,1280x720:MJPG,1280x960:MJPG ^
        --modos-solo-captura 1920x1080:MJPG,1920x1200:MJPG,640x480:YUY2,1280x720:YUY2 ^
        --fps 90 --segundos-captura 10 --segundos-tracking 30 --fov-grados 84 ^
        --luz "caja nivel 2" --exposicion-ms 3.906 ^
        --salida "..\\Claude outputs\\camaras\\modos_gs1.json" --timeout 1800
    python iter4\\medir_modos.py --config iter4\\tracker_config_gs1.yaml ^
        --elegir "..\\Claude outputs\\camaras\\modos_gs1.json" "..\\Claude outputs\\camaras\\modos_gs2.json" ^
        --salida "..\\Claude outputs\\camaras\\eleccion_modos.json" --timeout 60
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

import camaras_uvc   # antes de cv2: apaga la aceleracion HW de MSMF (CONTEXT.md 4.18)
import cv2
import numpy as np

import ajustes_camara
from camera_backend import create_backend
from sondear_camara import _vigilante, nitidez, parsear_modos
import tracker

# Umbrales de la eleccion (clarify.md P11 y P12).
FPS_MIN = 90.0
TOLERANCIA_FPS = 0.02
MAX_SATURADA = 0.01
MARGEN_SATURADA_PX = 10
# Muestra para brillo, saturacion y markers (fuera del bucle de FPS).
MUESTRA_CADA_S = 0.5
# Presupuesto por fila (apertura por perfil: capa 2.6-3.0 s + MSMF 0.4-0.5 s + warmup;
# con margen para una apertura que falle).
APERTURA_S = 10.0
MARGEN_FILA_S = 5.0
# Cuanto tiene que bajar el brillo entre dos candidatas seguidas para decir
# que la exposicion pedida cambia la imagen (a la mitad de exposicion, sin
# saturar, el brillo baja ~50 %).
BAJADA_BRILLO_MIN = 0.15
VENTANA = "medir_modos - q para interrumpir"


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

def k_nominal(ancho: int, alto: int, fov_grados: float) -> tuple[np.ndarray, np.ndarray]:
    """K con fx = fy = (W/2) / tan(fov/2) (fov horizontal), centro en el medio; dist = 0."""
    if not (0 < fov_grados < 180):
        raise ValueError(f"fov_grados tiene que estar entre 0 y 180, no {fov_grados}")
    f = (ancho / 2.0) / math.tan(math.radians(fov_grados) / 2.0)
    K = np.array([[f, 0.0, ancho / 2.0], [0.0, f, alto / 2.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    return K, np.zeros(5, dtype=np.float64)


def fraccion_saturada(gray: np.ndarray, esquinas: list, margen_px: int = MARGEN_SATURADA_PX) -> float | None:
    """Fraccion de pixeles a 255 dentro de la envolvente convexa de `esquinas`, con margen.

    `esquinas`: las esquinas (4x2 o 1x4x2) de los markers del dodecaedro
    detectados. Sin esquinas devuelve None (no hay sobre que medir).
    """
    if not esquinas:
        return None
    puntos = np.concatenate([np.asarray(e, dtype=np.float32).reshape(-1, 2) for e in esquinas])
    hull = cv2.convexHull(puntos).astype(np.int32)
    mascara = np.zeros(gray.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mascara, hull, 255)
    if margen_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * margen_px + 1, 2 * margen_px + 1))
        mascara = cv2.dilate(mascara, k)
    dentro = mascara > 0
    n = int(dentro.sum())
    if n == 0:
        return None
    return float((gray[dentro] >= 255).sum()) / n


def _cumple_exposicion(f: dict, fps_min: float, max_saturada: float) -> bool:
    fps = f.get("fps_captura")
    sat = f.get("saturada")
    return (fps is not None and fps >= fps_min and sat is not None and sat <= max_saturada
            and f.get("markers_mediana") is not None)


def elegir_exposicion(filas: list[dict], fps_min: float = FPS_MIN * (1 - TOLERANCIA_FPS),
                      max_saturada: float = MAX_SATURADA) -> dict | None:
    """Entre las candidatas con FPS de captura >= fps_min y saturada <= max_saturada,
    la de mas markers (mediana); empate, la mayor exposicion. None si ninguna cumple."""
    validas = [f for f in filas if _cumple_exposicion(f, fps_min, max_saturada)]
    if not validas:
        return None
    return max(validas, key=lambda f: (f["markers_mediana"], f["exposicion_ms"]))


def elegir_exposicion_comun(filas_a: list[dict], filas_b: list[dict],
                            fps_min: float = FPS_MIN * (1 - TOLERANCIA_FPS),
                            max_saturada: float = MAX_SATURADA) -> dict | None:
    """La misma exposicion para las dos camaras (P8): la que cumple en las dos con
    mas markers (el minimo de las dos medianas); empate, la mayor exposicion."""
    por_a = {f["exposicion_ms"]: f for f in filas_a if _cumple_exposicion(f, fps_min, max_saturada)}
    por_b = {f["exposicion_ms"]: f for f in filas_b if _cumple_exposicion(f, fps_min, max_saturada)}
    comunes = sorted(set(por_a) & set(por_b))
    if not comunes:
        return None
    mejor = max(comunes, key=lambda e: (min(por_a[e]["markers_mediana"], por_b[e]["markers_mediana"]), e))
    return {"exposicion_ms": mejor, "a": por_a[mejor], "b": por_b[mejor]}


def exposicion_cambia_brillo(filas: list[dict], bajada_min: float = BAJADA_BRILLO_MIN) -> dict:
    """Si la exposicion pedida cambia de verdad el brillo (duda de la fase 1: -6 por
    defecto dio ~90 fps). Ordena por exposicion de mayor a menor y mira cada paso."""
    con = sorted([f for f in filas if f.get("brillo") is not None and f.get("exposicion_ms") is not None],
                 key=lambda f: -f["exposicion_ms"])
    pasos = []
    for de, a in zip(con, con[1:]):
        b0, b1 = de["brillo"], a["brillo"]
        pasos.append({"de_ms": de["exposicion_ms"], "a_ms": a["exposicion_ms"],
                      "brillo_de": b0, "brillo_a": b1,
                      "bajada": round(1.0 - b1 / b0, 3) if b0 > 0 else None})
    bajadas = [p["bajada"] for p in pasos if p["bajada"] is not None]
    return {"cambia": any(b >= bajada_min for b in bajadas),
            "monotona": all(b >= -0.02 for b in bajadas) if bajadas else False,
            "pasos": pasos}


def _clave_modo(f: dict) -> tuple:
    p = f["pedido"]
    return (int(p["ancho"]), int(p["alto"]), str(p["fourcc"]).upper())


def elegir_resolucion(filas_gs1: list[dict], filas_gs2: list[dict], fps_min: float = FPS_MIN,
                      tolerancia: float = TOLERANCIA_FPS) -> dict | None:
    """El modo de mas pixeles cuyo FPS de tracking con ventana es >= fps_min*(1-tolerancia)
    en las dos camaras (P8, P11). None si ninguno."""
    umbral = fps_min * (1.0 - tolerancia)

    def validas(filas):
        return {_clave_modo(f): f for f in filas
                if f.get("fps_tracking_ventana") is not None and f["fps_tracking_ventana"] >= umbral}
    a, b = validas(filas_gs1), validas(filas_gs2)
    comunes = set(a) & set(b)
    if not comunes:
        return None
    w, h, fcc = max(comunes, key=lambda m: (m[0] * m[1], m[0]))
    return {"modo": {"ancho": w, "alto": h, "fourcc": fcc}, "umbral_fps": round(umbral, 2),
            "gs1": a[(w, h, fcc)], "gs2": b[(w, h, fcc)]}


COLUMNAS = [
    ("modo", "modo"), ("real", "real"), ("exposicion_ms", "exp. pedida ms"),
    ("exposicion_leida_ms", "exp. leida ms"), ("fps_captura", "fps captura"),
    ("fps_tracking", "fps tracking"), ("fps_tracking_ventana", "fps tracking ventana"),
    ("markers_mediana", "markers (mediana)"), ("fraccion_pose", "fraccion con pose"),
    ("brillo", "brillo"), ("saturada", "saturada"), ("error", "error"),
]


def _celda(f: dict, clave: str) -> str:
    if clave == "modo":
        p = f.get("pedido")
        return f"{p['ancho']}x{p['alto']} {p['fourcc']}" if p else "-"
    if clave == "real":
        r = f.get("real")
        return f"{r['ancho']}x{r['alto']}" if r else "-"
    v = f.get(clave)
    if v is None:
        return "-"
    if clave in ("saturada", "fraccion_pose"):
        return f"{100 * v:.1f} %"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def tabla_markdown(filas: list[dict]) -> str:
    """Tabla con las columnas que alguna fila trae (vale para las dos mediciones)."""
    if not filas:
        return "(sin filas)"
    presentes = [(c, t) for c, t in COLUMNAS
                 if any(f.get(c) is not None or (c == "modo" and f.get("pedido")) for f in filas)]
    lineas = ["| " + " | ".join(t for _c, t in presentes) + " |",
              "|" + "---|" * len(presentes)]
    for f in filas:
        lineas.append("| " + " | ".join(_celda(f, c) for c, _t in presentes) + " |")
    return "\n".join(lineas)


def estimar_segundos(n_filas: int, segundos_captura: float, n_tracking: int,
                     segundos_tracking: float) -> float:
    """Tiempo que necesitan las filas: apertura + captura (+ dos pases de tracking)."""
    return (n_filas * (APERTURA_S + segundos_captura + MARGEN_FILA_S)
            + n_tracking * 2 * segundos_tracking)


# ----------------------------------------------------------------------------
# Medir con la camara abierta
# ----------------------------------------------------------------------------

def medir_captura(cam, segundos: float, muestra_cada_s: float = MUESTRA_CADA_S) -> tuple[dict, list]:
    """FPS de captura solo leyendo frames; guarda una muestra (una referencia cada
    `muestra_cada_s`, sin procesar) para brillo, saturacion y markers despues."""
    n, fallos, muestra, real = 0, 0, [], None
    t0 = time.monotonic()
    t_muestra = t0 - muestra_cada_s
    while True:
        t = time.monotonic()
        if t - t0 >= segundos:
            break
        frame, _d, _ts = cam.read()
        if frame is None:
            fallos += 1
            continue
        n += 1
        if t - t_muestra >= muestra_cada_s:
            muestra.append(frame)
            t_muestra = t
        if real is None:
            real = {"ancho": int(frame.shape[1]), "alto": int(frame.shape[0])}
    dt = time.monotonic() - t0
    return ({"frames": n, "fallos": fallos, "fps_captura": round(n / dt, 2) if dt > 0 else 0.0,
             "real": real, "frames_muestra": len(muestra)}, muestra)


def preparar_tracking(cfg: dict) -> dict:
    """Lo que el tracker construye antes del bucle: detector, lista blanca, geometria, filtros."""
    aruco_dict = tracker.obtener_diccionario(cfg["markers"]["dictionary"])
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    tracker.aplicar_detector_params(params, cfg["markers"].get("detector", {}) or {})
    rbs = cfg.get("rigid_bodies", []) or []
    if len(rbs) != 1:
        raise ValueError(f"el perfil tiene que traer un solo rigid body (el dodecaedro), no {len(rbs)}")
    geometria = tracker.cargar_rigid_body(rbs[0]["geometry_file"])
    individuales = {m["id"] for m in cfg["markers"].get("list", []) or []}
    return {
        "detector": cv2.aruco.ArucoDetector(aruco_dict, params),
        "geometria": geometria,
        "ids_rb": set(geometria),
        "ids_conocidos": set(geometria) | individuales,
        "min_markers": int((cfg.get("rigid_bodies_quality") or {}).get("min_markers", 1)),
        "filtering": cfg.get("filtering") or {"enabled": False},
    }


def _detectar_rb(ctx: dict, gray: np.ndarray) -> dict:
    """{id: esquinas} de los markers del dodecaedro en el frame (lista blanca aplicada)."""
    corners, ids, _rej = ctx["detector"].detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return {}
    return {int(mid): corners[i] for i, mid in enumerate(ids.flatten().tolist())
            if int(mid) in ctx["ids_rb"]}


def analizar_muestra(muestra: list, ctx: dict) -> dict:
    """Brillo medio, fraccion saturada sobre el dodecaedro y mediana de markers de la muestra."""
    brillos, saturadas, markers = [], [], []
    for frame in muestra:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        brillos.append(float(gray.mean()))
        det = _detectar_rb(ctx, gray)
        markers.append(len(det))
        if det:
            s = fraccion_saturada(gray, list(det.values()))
            if s is not None:
                saturadas.append(s)
    return {
        "brillo": round(statistics.mean(brillos), 2) if brillos else None,
        "saturada": round(statistics.mean(saturadas), 4) if saturadas else None,
        "markers_mediana": statistics.median(markers) if markers else None,
        "frames_con_markers": sum(1 for m in markers if m > 0),
    }


def _filtros(ctx: dict):
    f = ctx["filtering"]
    if not f.get("enabled"):
        return None, None
    return ([tracker.OneEuroFilter(f["min_cutoff"], f["beta"]) for _ in range(3)],
            [tracker.OneEuroFilter(f["min_cutoff"], f["beta"]) for _ in range(4)])


def medir_tracking(cam, ctx: dict, segundos: float, ventana: bool,
                   K: np.ndarray, dist: np.ndarray) -> dict:
    """FPS haciendo por frame lo del tracker sin enviar: gris, deteccion, lista blanca,
    pose del dodecaedro (tracker.estimar_pose_rigid_body) y 1-Euro; con `ventana`,
    tambien el dibujo, imshow y waitKey(1). q en la ventana interrumpe el pase."""
    from scipy.spatial.transform import Rotation as Rot
    f_pos, f_rot = _filtros(ctx)
    prev_q = None
    n, fallos, con_pose, markers, interrumpida = 0, 0, 0, [], False
    t0 = time.monotonic()
    while True:
        t_now = time.monotonic()
        if t_now - t0 >= segundos:
            break
        frame, _d, _ts = cam.read()
        if frame is None:
            fallos += 1
            continue
        n += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        det = _detectar_rb(ctx, gray)
        markers.append(len(det))
        display = frame.copy() if ventana else None
        pose = None
        if len(det) >= ctx["min_markers"]:
            r = tracker.estimar_pose_rigid_body(det, ctx["geometria"], K, dist)
            if r is not None:
                rvec, tvec, _n = r
                if f_pos is not None:
                    tv = tvec.flatten()
                    tvec = np.array([f_pos[j].filtrar(tv[j], t_now) for j in range(3)]).reshape(3, 1)
                    q = Rot.from_rotvec(rvec.flatten()).as_quat()
                    if prev_q is not None and float(np.dot(q, prev_q)) < 0.0:
                        q = -q
                    qf = np.array([f_rot[j].filtrar(float(q[j]), t_now) for j in range(4)])
                    nq = float(np.linalg.norm(qf))
                    if nq > 1e-9:
                        qf = qf / nq
                        prev_q = qf
                        rvec = Rot.from_quat(qf).as_rotvec().reshape(3, 1)
                pose = (rvec, tvec)
                con_pose += 1
        if ventana:
            if det:
                cv2.aruco.drawDetectedMarkers(display, list(det.values()),
                                              np.array([[i] for i in det], dtype=np.int32))
            if pose is not None:
                cv2.drawFrameAxes(display, K, dist, pose[0], pose[1], 30.0)
            cv2.putText(display, f"Dodecaedro: {len(det)} markers", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow(VENTANA, display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                interrumpida = True
                break
    dt = time.monotonic() - t0
    if ventana:
        cv2.destroyAllWindows()
    return {"frames": n, "fallos": fallos, "fps": round(n / dt, 2) if dt > 0 else 0.0,
            "markers_mediana": statistics.median(markers) if markers else None,
            "fraccion_pose": round(con_pose / n, 4) if n else None,
            "interrumpida": interrumpida}


# ----------------------------------------------------------------------------
# Abrir por el perfil, una fila por modo o exposicion
# ----------------------------------------------------------------------------

def cfg_camara_para(cfg_camera: dict, modo: tuple[int, int, str], fps: float,
                    exposicion_ms: float | None, calibration_file: str | None = None) -> dict:
    """Copia de `camera` del perfil con el modo pedido, con el .yml que se pase (por defecto
    ninguno: un .yml vale para un tamano) y, si se da, la exposicion candidata en `controls`
    (la escribe la capa). Fase 4: con `calibration_file`, el backend comprueba que el modo es
    el del .yml y entrega la K real (B33)."""
    c = dict(cfg_camera)
    w, h, fcc = modo
    c.update({"width": w, "height": h, "fourcc": fcc, "fps": fps, "calibration_file": calibration_file})
    if exposicion_ms is not None:
        controls = dict(c.get("controls") or {})
        controls["exposure_manual"] = True
        controls["exposure_ms"] = float(exposicion_ms)
        c["controls"] = controls
    return c


def abrir_por_perfil(cfg_camera: dict):
    """create_backend + open(); el backend ya comprobo marca, ajustes y tamano."""
    cam = create_backend(cfg_camera)
    cam.open()
    return cam


def medir_fila(cfg: dict, ctx: dict | None, modo: tuple[int, int, str], fps: float,
               exposicion_ms: float | None, segundos_captura: float, segundos_tracking: float,
               fov_grados: float | None, abrir=None, intrinsecos: str | None = None) -> dict:
    """Una fila: abre por el perfil, captura, muestra y (si segundos_tracking > 0) los
    dos pases de tracking. Libera la camara siempre. Un fallo queda en `error`.
    `abrir(cfg_camera)` se inyecta en las pruebas; por defecto, abrir_por_perfil.
    Con `intrinsecos` (ruta de un .yml) la pose usa la K real del backend en vez de la
    nominal por `fov_grados` (fase 4, B33)."""
    abrir = abrir if abrir is not None else abrir_por_perfil
    w, h, fcc = modo
    fila: dict = {"pedido": {"ancho": w, "alto": h, "fourcc": fcc, "fps": fps},
                  "exposicion_ms": exposicion_ms, "intrinsecos": intrinsecos}
    t0 = time.monotonic()
    cam = None
    try:
        cam = abrir(cfg_camara_para(cfg["camera"], modo, fps, exposicion_ms, intrinsecos))
        fila["abrir_s"] = round(time.monotonic() - t0, 2)
        leidos = getattr(cam, "ajustes_leidos", None) or {}
        fila["exposicion_leida_ms"] = leidos.get("exposure_ms")
        fila["ajustes_leidos"] = leidos or None
        cap, muestra = medir_captura(cam, segundos_captura)
        fila.update(cap)
        print(f"[medir] {w}x{h} {fcc}: fps_captura {fila['fps_captura']} "
              f"(exposicion leida {fila['exposicion_leida_ms']} ms)", flush=True)
        if ctx is not None:
            fila.update(analizar_muestra(muestra, ctx))
            print(f"[medir]   muestra {len(muestra)}: brillo {fila['brillo']}, saturada "
                  f"{fila['saturada']}, markers {fila['markers_mediana']}", flush=True)
            if segundos_tracking > 0 and fila["real"]:
                if intrinsecos:
                    K, dist = cam.get_intrinsics()
                    fila["K"] = np.asarray(K).round(3).tolist()
                else:
                    K, dist = k_nominal(fila["real"]["ancho"], fila["real"]["alto"], fov_grados)
                sin = medir_tracking(cam, ctx, segundos_tracking, False, K, dist)
                fila["fps_tracking"] = sin["fps"]
                fila["tracking_sin_ventana"] = sin
                print(f"[medir]   tracking sin ventana: {sin['fps']} fps, markers "
                      f"{sin['markers_mediana']}, pose {sin['fraccion_pose']}", flush=True)
                con = medir_tracking(cam, ctx, segundos_tracking, True, K, dist)
                fila["fps_tracking_ventana"] = con["fps"]
                fila["tracking_con_ventana"] = con
                fila["markers_mediana"] = con["markers_mediana"]
                fila["fraccion_pose"] = con["fraccion_pose"]
                print(f"[medir]   tracking con ventana: {con['fps']} fps, markers "
                      f"{con['markers_mediana']}, pose {con['fraccion_pose']}", flush=True)
    except (RuntimeError, ValueError, OSError) as e:
        fila["error"] = str(e)
        print(f"[medir] {w}x{h} {fcc}: ERROR {e}", flush=True)
    finally:
        if cam is not None:
            cam.close()
        fila["total_s"] = round(time.monotonic() - t0, 2)
    return fila


def textos_enfoque(nitidez_ahora: float, nitidez_max: float) -> tuple[str, str]:
    """Las dos lineas que se pintan sobre la imagen al enfocar, en lenguaje llano (P21) y sin
    acentos: la fuente de cv2.putText (Hershey) pinta '??' en lugar de una letra con acento."""
    return (f"Nitidez: {nitidez_ahora:.0f}   (la mas alta hasta ahora: {nitidez_max:.0f})",
            "Gira el lente hasta que el numero sea el mas alto.   q = terminar")


def enfocar(cfg: dict, modo: tuple[int, int, str], fps: float, limite: float,
            abrir=None) -> dict:
    """Ventana con la nitidez del frame (varianza del laplaciano) y su maximo, hasta q."""
    abrir = abrir if abrir is not None else abrir_por_perfil
    cam = abrir(cfg_camara_para(cfg["camera"], modo, fps, None))
    r: dict = {"frames": 0, "nitidez": None, "nitidez_max": None, "interrumpida": False}
    ultimo = 0.0
    try:
        while time.monotonic() < limite:
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            v = nitidez(gray)
            r["frames"] += 1
            r["nitidez"] = round(v, 1)
            r["nitidez_max"] = round(max(v, r["nitidez_max"] or 0.0), 1)
            display = frame.copy()
            linea1, linea2 = textos_enfoque(v, r["nitidez_max"])
            cv2.putText(display, linea1, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(display, linea2, (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow(VENTANA, display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                r["interrumpida"] = True
                break
            if time.monotonic() - ultimo > 0.5:
                print(f"[enfocar] nitidez {v:.0f} (max {r['nitidez_max']:.0f})", flush=True)
                ultimo = time.monotonic()
    finally:
        cam.close()
        cv2.destroyAllWindows()
    return r


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _parsear_lista_ms(texto: str) -> list[float]:
    valores = []
    for t in [x.strip() for x in texto.split(",") if x.strip()]:
        ms = float(t)
        ajustes_camara.exposicion_ms_a_dshow(ms)   # para aqui si no es 1000*2^k
        valores.append(ms)
    if not valores:
        raise ValueError("--exposiciones-ms vacio")
    return valores


def _guardar(estado: dict, salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _elegir(a: Path, b: Path, estado: dict) -> int:
    ea = json.loads(a.read_text(encoding="utf-8"))
    eb = json.loads(b.read_text(encoding="utf-8"))
    if ea.get("modo") != eb.get("modo") or ea.get("modo") not in ("exposicion", "modos"):
        print(f"[elegir] los dos JSON tienen que ser de la misma medicion (exposicion o modos): "
              f"{ea.get('modo')!r} y {eb.get('modo')!r}")
        return 1
    estado["de"] = {"a": {"archivo": str(a), "perfil": ea.get("perfil")},
                    "b": {"archivo": str(b), "perfil": eb.get("perfil")}}
    fa, fb = ea.get("filas", []), eb.get("filas", [])
    print(f"[elegir] {ea.get('perfil')}:\n{tabla_markdown(fa)}\n[elegir] {eb.get('perfil')}:\n{tabla_markdown(fb)}")
    if ea["modo"] == "exposicion":
        estado["eleccion"] = elegir_exposicion_comun(fa, fb)
        print(f"[elegir] exposicion comun: "
              f"{estado['eleccion']['exposicion_ms'] if estado['eleccion'] else 'NINGUNA cumple en las dos'}")
    else:
        estado["eleccion"] = elegir_resolucion(fa, fb)
        m = estado["eleccion"]["modo"] if estado["eleccion"] else None
        texto = f"{m['ancho']}x{m['alto']} {m['fourcc']}" if m else "NINGUNA sostiene el umbral en las dos"
        print(f"[elegir] resolucion: {texto}")
    return 0 if estado["eleccion"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enfoque, exposicion y resolucion x formato de una SVPRO por su perfil.")
    ap.add_argument("--config", required=True, help="perfil (tracker_config_gs1.yaml o gs2)")
    ap.add_argument("--enfocar", action="store_true", help="ventana con la nitidez para enfocar el lente")
    ap.add_argument("--exposiciones-ms", help="Medicion 1: candidatas, p. ej. 7.813,3.906,1.953,0.977,0.488")
    ap.add_argument("--modos", help="Medicion 2: modos con tracking, 'AnchoxAlto:FOURCC,...'")
    ap.add_argument("--modos-solo-captura", help="Medicion 2: modos sin tracking (no llegan a 90)")
    ap.add_argument("--elegir", nargs=2, metavar="JSON", help="sin camara: los JSON de las dos camaras")
    ap.add_argument("--modo", help="un modo 'AnchoxAlto:FOURCC' (--enfocar, --exposiciones-ms)")
    ap.add_argument("--fps", type=float, help="FPS que se piden")
    ap.add_argument("--exposicion-ms", type=float, help="Medicion 2: exposicion elegida (si no, la del perfil)")
    ap.add_argument("--segundos-captura", type=float, help="segundos de captura sola por fila")
    ap.add_argument("--segundos-tracking", type=float, help="segundos de cada pase de tracking por modo")
    ap.add_argument("--fov-grados", type=float, help="FOV horizontal del lente para la K nominal (SVPRO ~84)")
    ap.add_argument("--intrinsecos", help="Medicion 2: .yml de intrinsecos reales (fase 4, B33); el modo tiene que ser el "
                                          "del .yml y entonces --fov-grados no hace falta")
    ap.add_argument("--luz", help="nivel de la caja de luz y luz de la sala (P7)")
    ap.add_argument("--salida", required=True, help="JSON de salida")
    ap.add_argument("--timeout", type=float, required=True, help="tope en segundos")
    args = ap.parse_args(argv)

    modos_main = [n for n in ("enfocar", "exposiciones_ms", "modos", "elegir") if getattr(args, n)]
    if len(modos_main) != 1:
        ap.error("uno solo de --enfocar, --exposiciones-ms, --modos o --elegir por corrida")
    (que,) = modos_main
    salida = Path(args.salida)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "argv": sys.argv[1:] if argv is None else argv,
                    "opencv": cv2.__version__,
                    "aceleracion_msmf": dict(camaras_uvc.ACELERACION_MSMF),
                    "perfil": args.config, "luz": args.luz}

    if que == "elegir":
        estado["modo"] = "elegir"
        rc = _elegir(Path(args.elegir[0]), Path(args.elegir[1]), estado)
        _guardar(estado, salida)
        print(f"[medir] guardado {salida}")
        return rc

    cfg = tracker.cargar_config(args.config)
    if not (cfg.get("camera") or {}).get("usb_port_windows"):
        ap.error(f"el perfil {args.config} no trae camera.usb_port_windows: esta medicion abre por el puerto")
    estado["puerto"] = cfg["camera"]["usb_port_windows"]
    estado["controls_perfil"] = cfg["camera"].get("controls")

    if que == "enfocar":
        if args.modo is None or args.fps is None:
            ap.error("--enfocar exige --modo y --fps")
        try:
            (modo,) = parsear_modos(args.modo)
        except ValueError as e:
            ap.error(str(e))
        estado["modo"] = "enfocar"
        estado["pedido"] = {"ancho": modo[0], "alto": modo[1], "fourcc": modo[2], "fps": args.fps}
        print(f"[medir] {camaras_uvc.describir_aceleracion_msmf()}", flush=True)
        vig = _vigilante(args.timeout, estado, salida)
        rc = 0
        try:
            estado["enfoque"] = enfocar(cfg, modo, args.fps, time.monotonic() + args.timeout - 2)
            print(f"[enfocar] nitidez final {estado['enfoque']['nitidez']} (max {estado['enfoque']['nitidez_max']})")
        except (RuntimeError, ValueError, OSError) as e:
            estado["error"] = str(e)
            print(f"[medir] ERROR: {e}")
            rc = 1
        finally:
            vig.cancel()
        _guardar(estado, salida)
        print(f"[medir] guardado {salida}")
        return rc

    # Mediciones 1 y 2: argumentos explicitos.
    faltan = [n for n in ("fps", "segundos_captura", "luz") if getattr(args, n) is None]
    if args.fov_grados is None and not (que == "modos" and args.intrinsecos):
        faltan.append("fov_grados")
    if que == "modos" and args.segundos_tracking is None:
        faltan.append("segundos_tracking")
    if args.intrinsecos and (que != "modos" or not Path(args.intrinsecos).is_file()):
        ap.error(f"--intrinsecos solo vale en la Medicion 2 (--modos) y tiene que existir: {args.intrinsecos}")
    if que == "exposiciones_ms" and args.modo is None:
        faltan.append("modo")
    if faltan:
        ap.error("faltan argumentos explicitos: " + ", ".join("--" + f.replace("_", "-") for f in faltan))
    try:
        if que == "exposiciones_ms":
            exposiciones = _parsear_lista_ms(args.exposiciones_ms)
            (modo,) = parsear_modos(args.modo)
            filas_pedidas = [(modo, e, True) for e in exposiciones]
            segundos_tracking = 0.0
        else:
            con = parsear_modos(args.modos)
            solo = parsear_modos(args.modos_solo_captura) if args.modos_solo_captura else []
            if args.exposicion_ms is not None:
                ajustes_camara.exposicion_ms_a_dshow(args.exposicion_ms)
            filas_pedidas = [(m, args.exposicion_ms, True) for m in con] + \
                            [(m, args.exposicion_ms, False) for m in solo]
            segundos_tracking = args.segundos_tracking
    except ValueError as e:
        ap.error(str(e))
    n_tracking = sum(1 for _m, _e, t in filas_pedidas if t) if que == "modos" else 0
    estimado = estimar_segundos(len(filas_pedidas), args.segundos_captura, n_tracking, segundos_tracking)
    if estimado > args.timeout:
        ap.error(f"el tope no alcanza: {len(filas_pedidas)} filas x ~{APERTURA_S + args.segundos_captura + MARGEN_FILA_S:.0f} s"
                 f" + {n_tracking} x 2 x {segundos_tracking:.0f} s de tracking = ~{estimado:.0f} s > --timeout "
                 f"{args.timeout:.0f}; sube --timeout o quita modos")

    estado.update({"modo": "exposicion" if que == "exposiciones_ms" else "modos",
                   "fov_grados": args.fov_grados, "intrinsecos": args.intrinsecos, "fps_pedidos": args.fps,
                   "segundos_captura": args.segundos_captura, "segundos_tracking": segundos_tracking,
                   "umbrales": {"fps_min": round(FPS_MIN * (1 - TOLERANCIA_FPS), 2),
                                "max_saturada": MAX_SATURADA, "margen_px": MARGEN_SATURADA_PX},
                   "estimado_s": round(estimado, 1), "filas": []})
    print(f"[medir] {camaras_uvc.describir_aceleracion_msmf()}", flush=True)
    ctx = preparar_tracking(cfg)
    limite = time.monotonic() + args.timeout
    vig = _vigilante(args.timeout, estado, salida)
    rc = 0
    try:
        for modo, exposicion, con_tracking in filas_pedidas:
            necesita = APERTURA_S + args.segundos_captura + (2 * segundos_tracking if con_tracking else 0)
            if time.monotonic() + necesita > limite:
                estado["filas"].append({"pedido": {"ancho": modo[0], "alto": modo[1], "fourcc": modo[2],
                                                   "fps": args.fps}, "exposicion_ms": exposicion,
                                        "error": "no medido: tope de tiempo"})
                continue
            fila = medir_fila(cfg, ctx, modo, args.fps, exposicion, args.segundos_captura,
                              segundos_tracking if con_tracking else 0.0, args.fov_grados,
                              intrinsecos=args.intrinsecos)
            estado["filas"].append(fila)
            _guardar(estado, salida)      # B25: cada fila al tenerla
        if que == "exposiciones_ms":
            estado["eleccion"] = elegir_exposicion(estado["filas"])
            estado["brillo_responde"] = exposicion_cambia_brillo(estado["filas"])
            print(f"[medir] la exposicion pedida cambia el brillo: "
                  f"{'si' if estado['brillo_responde']['cambia'] else 'NO'} "
                  f"(monotona: {estado['brillo_responde']['monotona']})")
            print(f"[medir] exposicion elegida para este perfil: "
                  f"{estado['eleccion']['exposicion_ms'] if estado['eleccion'] else 'NINGUNA cumple'} ms")
        else:
            estado["umbral_resolucion_fps"] = round(FPS_MIN * (1 - TOLERANCIA_FPS), 2)
            cumplen = [f for f in estado["filas"] if (f.get("fps_tracking_ventana") or 0) >= estado["umbral_resolucion_fps"]]
            estado["modos_que_cumplen"] = [_celda(f, "modo") for f in cumplen]
            print(f"[medir] modos con tracking con ventana >= {estado['umbral_resolucion_fps']}: "
                  f"{estado['modos_que_cumplen'] or 'ninguno'} (la eleccion final es con las dos camaras: --elegir)")
        print("\n" + tabla_markdown(estado["filas"]))
        if any("error" in f for f in estado["filas"]):
            rc = 1
    except (OSError, ValueError, RuntimeError) as e:
        estado["error"] = str(e)
        print(f"[medir] ERROR: {e}")
        rc = 1
    finally:
        vig.cancel()
    _guardar(estado, salida)
    print(f"[medir] guardado {salida}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
