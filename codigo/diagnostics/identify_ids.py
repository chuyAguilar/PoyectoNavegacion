# -*- coding: utf-8 -*-
"""
IDENTIFICAR IDs de los markers en vivo, o VISTA PREVIA para colocar la camara.

Abre la camara con el perfil, igual que el tracker (`camera.backend.create_backend`
+ `open()`: puerto, marca, ajustes, modo y el .yml), y la lee por el mismo hilo de
captura (`camera.grabber.FrameGrabber`; meta 003, fase 8a): los fps de la camara
salen de los frames que entrega la camara (`frames_read`), no de las vueltas del
bucle, asi que con deteccion son los de la camara aunque el bucle vaya mas lento.
Tiene dos modos:

- Por defecto, IDs y colocar la camara (fase 8a; clarify.md P16 = b): dibuja el
  ID (numero grande) sobre cada marker detectado (Marker0, o cualquiera del
  diccionario del perfil), mas un punto rojo en la esquina 0 para ver su
  orientacion, y ademas la cruz fina en el centro y la linea con los fps de la
  camara. El detector ArUco decodifica la orientacion del patron, asi que el ID
  no se confunde 6<->9 ni por giro. Cada 5 s escribe `[IDs] camara X fps`.
- `--no-detect`, vista previa (meta 003, fase 7b; clarify.md P13 = c; desde la
  fase 8a solo para la linea de comandos, P17 = a): solo la imagen, la cruz y
  los fps de la camara. No detecta, no estima pose, no envia nada ni abre el
  puerto 18944. Cada 5 s escribe `[Vista previa] camara X fps` (con poca luz
  las SVPRO bajan de 90, B50).

Sale limpio (camara cerrada, ventana destruida y `[Salida limpia]`, en un
`finally`) con `q`, al cerrar la ventana con la X, al cumplirse `--timeout`, o
si la camara no entrega frames durante NO_FRAMES_S (codigo 1, y lo dice).

Uso (desde codigo\\, con el venv; --config y --timeout obligatorios, principios 7 y 9):
    python -m diagnostics.identify_ids --config profiles\\tracker_config_gs1.yaml --timeout 600
    python -m diagnostics.identify_ids --config profiles\\tracker_config_gs1.yaml --no-detect --timeout 600
Teclas:  q = salir

Context7 (2026-10-25): OpenCV 4.13, `getWindowProperty(win, WND_PROP_VISIBLE)`
dice si la ventana existe y es visible; `waitKey` atiende los eventos de
HighGUI. Python 3.11, `argparse.add_mutually_exclusive_group()` y un `type`
que lanza `ArgumentTypeError`. Context7 (2026-10-25, fase 8a): OpenCV 4.13,
`putText(img, text, org, ...)` con `org` la esquina inferior izquierda del texto
(por eso la linea de fps va en otra altura que la de IDs) y `line` pinta en el
mismo array.
"""
import argparse
import sys
import time
from pathlib import Path

from camera import uvc as camaras_uvc  # noqa: F401  (antes de cv2: apaga la aceleracion HW de MSMF; meta 002, fase 2b)
import cv2
import numpy as np

from camera.backend import create_backend
from camera.grabber import FrameGrabber
import profiles
from vision.detection import apply_detector_params   # el mismo mapeo del YAML que usa el tracker

# El panel manda 'q' a la ventana por su titulo exacto (gui/recipes.VENTANAS).
WINDOW_TITLE = "Identificar IDs - q para salir"
PREVIEW_WINDOW_TITLE = "Vista previa - q para salir"
NO_FRAMES_S = 10.0          # sin ningun frame en este tiempo, sale con codigo 1 (principio 9)
REPORT_EVERY_S = 5.0        # la linea `<tag> camara X fps` con los fps de la camara
IDS_PRINT_EVERY_S = 0.5     # la linea de IDs visibles en la consola (como antes)
READ_TIMEOUT_S = 0.1        # espera maxima por un frame nuevo en cada vuelta (la ventana sigue atendida)
PREVIEW_Y_WITH_IDS = 95     # con deteccion, la linea de fps va debajo de las dos de draw_ids (35 y 65)


def _positive_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"tiene que ser un numero de segundos, no {text!r}")
    if value <= 0:
        raise argparse.ArgumentTypeError(f"tiene que ser > 0, no {value:g}")
    return value


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Identificar IDs de los markers en vivo y colocar la camara (cruz y fps "
                    "de la camara), o solo la vista previa (--no-detect).")
    ap.add_argument("--config", required=True, help="Perfil, p. ej. profiles/tracker_config_gs1.yaml.")
    ap.add_argument("--timeout", required=True, type=_positive_seconds,
                    help="Tope de la corrida en segundos (> 0); al cumplirse sale limpio.")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--no-detect", action="store_true",
                      help="Vista previa: solo la imagen, una cruz en el centro y los fps de la camara.")
    modo.add_argument("--permisivo", action="store_true",
                      help="Usar el tuning permisivo del perfil (mas detecciones, mas falsos).")
    return ap.parse_args(argv)


def make_detector(cfg_markers: dict, permisive: bool) -> cv2.aruco.ArucoDetector:
    """El detector de siempre: estricto (sin falsos positivos) o el tuning del perfil."""
    dict_name = cfg_markers["dictionary"].upper()
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    if not permisive:
        # ESTRICTO: evita falsos positivos (IDs inventados en ruido/textura).
        params.minMarkerPerimeterRate = 0.05          # ignora blobs chicos
        params.polygonalApproxAccuracyRate = 0.03     # bordes mas rectos
        params.maxErroneousBitsInBorderRate = 0.10    # borde casi perfecto
        params.errorCorrectionRate = 0.35             # menos correccion = menos falsos
        params.minOtsuStdDev = 5.0                    # rechaza zonas de bajo contraste
        print("[IDs] Deteccion ESTRICTA (sin falsos positivos). --permisivo para aflojar.")
    else:
        # mismo tuning permisivo del tracker
        apply_detector_params(params, cfg_markers.get("detector", {}))
    return cv2.aruco.ArucoDetector(aruco_dict, params)


def draw_ids(display: np.ndarray, corners, ids) -> list[int]:
    """Dibuja cada marker (contorno, ID grande, punto rojo en la esquina 0) y la
    linea de IDs visibles. Devuelve los IDs visibles ordenados."""
    visibles = []
    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(display, corners)
        for i, mid in enumerate(ids.flatten()):
            c = corners[i].reshape(4, 2)
            centro = tuple(int(v) for v in c.mean(axis=0))
            # ID grande con contorno para legibilidad
            txt = str(int(mid))
            cv2.putText(display, txt, centro, cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 6)
            cv2.putText(display, txt, centro, cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 2)
            # esquina 0 (top-left del marker) en rojo -> muestra orientacion
            cv2.circle(display, tuple(int(v) for v in c[0]), 6, (0, 0, 255), -1)
            visibles.append(int(mid))
    visibles = sorted(visibles)
    cv2.putText(display, f"IDs visibles ({len(visibles)}): {visibles}",
                (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(display, "punto rojo = esquina 0 (orientacion)",
                (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)
    return visibles


def draw_preview(display: np.ndarray, fps_camera: float | None, profile_name: str,
                 y: int = 35) -> None:
    """Una linea con el perfil, los fps de la camara y «q = salir» (a la altura `y`;
    con deteccion va en PREVIEW_Y_WITH_IDS para no pisar la de IDs), y una cruz fina
    en el centro. Sin deteccion, sin pose, sin envio."""
    h, w = display.shape[:2]
    cx, cy = w // 2, h // 2
    color = (0, 255, 255)
    cv2.line(display, (0, cy), (w - 1, cy), color, 1)
    cv2.line(display, (cx, 0), (cx, h - 1), color, 1)
    fps_txt = f"{fps_camera:.1f}" if fps_camera is not None else "-"
    cv2.putText(display, f"{profile_name} | camara {fps_txt} fps | q = salir",
                (15, int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
    cv2.putText(display, f"{profile_name} | camara {fps_txt} fps | q = salir",
                (15, int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = profiles.load(args.config)
    preview = args.no_detect
    tag = "[Vista previa]" if preview else "[IDs]"
    win = PREVIEW_WINDOW_TITLE if preview else WINDOW_TITLE
    profile_name = Path(args.config).name
    detector = None if preview else make_detector(cfg["markers"], args.permisivo)

    # El reloj del bucle es este; el hilo de captura usa el suyo (por defecto perf_counter):
    # sus horas de captura no se usan aqui, solo su contador `frames_read`.
    clock = time.perf_counter
    cam = create_backend(cfg["camera"])
    grabber = None
    rc = 0
    try:
        cam.open()
        if preview:
            print(f"{tag} Coloca la camara: imagen, cruz en el centro y fps de la camara. "
                  f"q o la X = salir (tope {args.timeout:.0f} s).")
        else:
            print(f"{tag} Apunta los markers (Marker0) a la camara y colocala con la cruz "
                  f"y los fps de la camara. q o la X = salir (tope {args.timeout:.0f} s).")
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        grabber = FrameGrabber(cam)
        grabber.start()
        t_start = t_last_frame = t_report = clock()
        frames_at_report = grabber.frames_read
        t_print = float("-inf")         # la primera linea de IDs sale con el primer frame, como antes
        fps_camera = None
        shown = False
        while True:
            got = grabber.next_frame(READ_TIMEOUT_S)
            t = clock()
            if got is not None:
                frame = got[0]
                t_last_frame = t
                if t - t_report >= REPORT_EVERY_S:
                    read_now = grabber.frames_read
                    fps_camera = (read_now - frames_at_report) / (t - t_report)
                    print(f"{tag} camara {fps_camera:.1f} fps")
                    t_report, frames_at_report = t, read_now
                disp = frame.copy()
                if preview:
                    draw_preview(disp, fps_camera, profile_name)
                else:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    corners, ids, _ = detector.detectMarkers(gray)
                    draw_preview(disp, fps_camera, profile_name, y=PREVIEW_Y_WITH_IDS)
                    visibles = draw_ids(disp, corners, ids)
                    if t - t_print > IDS_PRINT_EVERY_S:   # por si no miras la ventana
                        print(f"  visibles: {visibles}")
                        t_print = t
                cv2.imshow(win, disp)
                shown = True
            elif t - t_last_frame > NO_FRAMES_S:
                print(f"[ERROR] {tag} la camara no entrega frames desde hace {NO_FRAMES_S:.0f} s. "
                      f"Saliendo.", file=sys.stderr)
                rc = 1
                break

            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                print(f"{tag} q: saliendo.")
                break
            if shown and cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                print(f"{tag} ventana cerrada: saliendo.")
                break
            if t - t_start >= args.timeout:
                print(f"{tag} tope de {args.timeout:.0f} s: saliendo.")
                break
    finally:
        if grabber is not None:
            grabber.stop()              # el hilo suelta la camara antes de cerrarla (como el tracker)
        cam.close()
        cv2.destroyAllWindows()
        print("[Salida limpia]")
    return rc


if __name__ == "__main__":
    sys.exit(main())
