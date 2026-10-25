r"""
Tracker ArUco de Marker0 para navegacion quirurgica: el bucle camara -> vision
-> envio por OpenIGTLink -> ventana.

Desde la meta 003, fase 4 · El tracker en piezas (ADR-027), este archivo solo
tiene el bucle. Las piezas: `camera.backend` (la camara), `camera.grabber` (el
hilo de captura con el ultimo frame), `vision.tracking` (deteccion, pose
IPPE_SQUARE y 1-Euro de la posicion: `MarkerTracker`), `transport.igtl` (el
servidor OpenIGTLink: `IgtlSender`) y `profiles` (el perfil, con rutas
relativas a codigo/). La pose multi-marker del dodecaedro esta archivada en
codigo/historico/iter4/dodecahedron/pose_rigid_body.py.

Lo que publica (principio 6, ADR-026): solo `Marker0ToTracker`, en el puerto
`igtlink.transforms_port` (18944). `igtlink.send_video: true` aborta (P7).

Uso (desde codigo\, con el venv; --config obligatorio, principio 7):
    python -m tracker --config profiles\tracker_config_gs1.yaml

Tiempo por etapa (meta 003, fase 6; apagado por defecto):
    python -m tracker --config profiles\tracker_config_gs1.yaml --duration 30 ^
        --timing "<salida>.json"

Meta 003, fase 7 · Subir los fps con ventana (clarify.md P9):
  - Slicer se conecta como CLIENTE a localhost:18944 ANTES de arrancar. El
    tracker lo espera hasta --slicer-timeout segundos (30 por defecto) y, si no
    llega, aborta con codigo 3 y lo dice, sin abrir la camara.
  - El envio no espera (E1: `send_message(wait=False)` con guarda de conexion).
  - La captura va en un hilo propio (`camera.grabber.FrameGrabber`, C1): el
    bucle procesa siempre el ultimo frame; los que no alcanza a procesar se
    cuentan como saltados en la linea [FPS]. `--sync-capture` lee en el bucle,
    como hasta la fase 6, para medir una variable a la vez.
  - `t_now`, la entrada del 1-Euro, es la hora de captura por `time.perf_counter`
    (antes `time.time()`, con resolucion de 15.6 ms en este venv). Cambia la
    entrada del filtro: declarado en el plan; el replay usa los tiempos grabados.
Presiona 'q' en la ventana de video para salir.

B28: `import camera` va antes que `import cv2`, asi la aceleracion HW de MSMF
queda apagada tambien lanzado a mano (camera/__init__.py importa camera.uvc).
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

import camera  # noqa: F401  (primero: apaga la aceleracion HW de MSMF antes de cargar cv2; B28)
import cv2
import numpy as np

from camera import uvc as camaras_uvc
from camera.backend import create_backend
from camera.grabber import FrameGrabber, SyncGrabber
import profiles
from transport.igtl import IgtlSender
from vision.tracking import MarkerPose, MarkerTracker

# El panel manda 'q' a la ventana por su titulo exacto (gui/recipes.VENTANAS["tracker"]).
WINDOW_TITLE = "Tracker Multi-Marker - q para salir"
MAX_READ_FAILURES = 300
READ_TIMEOUT_S = 1.0            # espera maxima por un frame nuevo en cada vuelta del bucle
STALL_TIMEOUT_S = 10.0          # sin ningun frame en este tiempo, el tracker sale (principio 9)
DEFAULT_SLICER_TIMEOUT_S = 30.0
EXIT_NO_SLICER = 3


class SlicerNotConnected(RuntimeError):
    """Slicer no se conecto al puerto en el tope de tiempo."""


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def draw_poses(display: np.ndarray, poses: list[MarkerPose], K, dist) -> None:
    """Dibuja sobre `display` cada marker (contorno e ID) y sus ejes (lado/2), como antes."""
    for p in poses:
        cv2.aruco.drawDetectedMarkers(display, [p.corners.reshape(1, 4, 2).astype(np.float32)],
                                      np.array([[p.id]]))
        cv2.drawFrameAxes(display, K, dist, p.rvec, p.tvec, p.size_mm * 0.5)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tracker de Marker0: camara -> pose -> OpenIGTLink.")
    parser.add_argument("--config", required=True,
                        help="Perfil de la camara (profiles/tracker_config_gs1.yaml o _gs2.yaml).")
    # Linea base de Marker0 (meta 003, fase 1). Todas apagadas por defecto:
    # sin ellas el bucle hace las mismas llamadas.
    parser.add_argument("--record", default=None,
                        help="Graba ids, esquinas, tiempos y poses enviadas en este .npz (pose_log).")
    parser.add_argument("--no-window", action="store_true",
                        help="Sin ventana de video (pisa debug.show_window del perfil).")
    parser.add_argument("--save-frames", default=None,
                        help="Carpeta donde --record guarda 1 frame en gris de cada --frames-every (PNG).")
    parser.add_argument("--frames-every", type=int, default=30,
                        help="Con --save-frames, guarda 1 de cada N frames (defecto 30).")
    parser.add_argument("--duration", type=float, default=None,
                        help="Sale solo, limpio, a los N segundos de bucle (tope de la corrida).")
    # Tiempo por frame (meta 003, fase 6). Apagada por defecto: sin ella no se cronometra.
    parser.add_argument("--timing", default=None,
                        help="Cronometra cada etapa del bucle y escribe el resumen en este .json.")
    # Espera a Slicer (meta 003, fase 7): sin cliente en este tiempo, aborta y lo dice.
    parser.add_argument("--slicer-timeout", type=float, default=DEFAULT_SLICER_TIMEOUT_S,
                        help=f"Segundos que se espera a que Slicer se conecte antes de abortar "
                             f"(defecto {DEFAULT_SLICER_TIMEOUT_S:.0f}).")
    # Diagnostico (fase 7): la captura en el bucle, como hasta la fase 6, para medir E1 sin C1.
    parser.add_argument("--sync-capture", action="store_true",
                        help="Lee la camara en el bucle, sin hilo de captura (para medir una "
                             "variable a la vez; por defecto la captura va en un hilo).")
    args = parser.parse_args(argv)
    if args.save_frames and not args.record:
        parser.error("--save-frames necesita --record")
    if args.frames_every < 1:
        parser.error("--frames-every tiene que ser >= 1")
    if args.duration is not None and args.duration <= 0:
        parser.error("--duration tiene que ser > 0")
    if args.timing is not None and Path(args.timing).suffix != ".json":
        parser.error("--timing tiene que terminar en .json")
    if args.slicer_timeout <= 0:
        parser.error("--slicer-timeout tiene que ser > 0")
    return args


def _no_mark(_stage: str) -> None:
    """Sin --timing: las marcas del cronometro no hacen nada."""


def _no_end_frame() -> None:
    """Sin --timing: el cierre de frame del cronometro no hace nada."""


def _save_timing(sw, args: argparse.Namespace, argv, show_window: bool, n_frames: int,
                 t_start: float, t_end: float, capture: dict) -> None:
    """Escribe el JSON de --timing y su tabla en el log. El tiempo por frame que lo
    contrasta es el del promedio de [FPS] (perf_counter), medido aparte del cronometro."""
    from diagnostics.pose_log import format_timing
    fps = n_frames / (t_end - t_start) if t_end > t_start else None
    summary = sw.summary()
    frame_ms_fps = 1000.0 / fps if fps else None
    sum_ms = summary["sum_of_stage_means_ms"]
    meta = {
        "config": str(Path(args.config).resolve()),
        "argv": sys.argv if argv is None else list(argv),
        "show_window": bool(show_window),
        "record": bool(args.record),
        "frames_loop": n_frames,
        "fps_average": fps,
        "frame_ms_from_fps": frame_ms_fps,
        "sum_over_frame_ms_from_fps": (sum_ms / frame_ms_fps
                                       if sum_ms is not None and frame_ms_fps else None),
        "clock": "time.perf_counter",
        "capture": capture,
        "opencv": cv2.__version__, "numpy": np.__version__,
    }
    path = sw.save(Path(args.timing), meta)
    print(f"[Tiempos] Guardados en {path}\n{format_timing(summary)}")
    if meta["sum_over_frame_ms_from_fps"] is not None:
        print(f"[Tiempos] Frame por [FPS]: {frame_ms_fps:.3f} ms ({fps:.1f} fps); "
              f"suma de etapas / frame = {meta['sum_over_frame_ms_from_fps']:.3f}")


def _capture_stats(grabber, n_frames: int, elapsed: float) -> dict:
    """Lo que leyo la camara frente a lo que proceso el bucle (C0 dentro del tracker)."""
    if grabber is None:
        return {"mode": None, "frames_read": 0, "frames_skipped": 0,
                "fps_camera": None, "read_failures": 0}
    return {"mode": grabber.mode,
            "frames_read": grabber.frames_read,
            "frames_skipped": grabber.skipped,
            "fps_camera": grabber.frames_read / elapsed if elapsed > 0 else None,
            "read_failures": grabber.failures,
            "frames_loop": n_frames}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = profiles.load(args.config)
    print(f"[Tracker] {camaras_uvc.describir_aceleracion_msmf()}")

    cfg_igtl = cfg["igtlink"]
    if cfg_igtl.get("send_video"):
        # P7 (meta 003): el video por OpenIGTLink satura el pipeline (CONTEXT.md 4.4) y nadie lo usa.
        print(f"[ERROR] {Path(args.config).name}: igtlink.send_video es true y el tracker ya no "
              f"envia video por OpenIGTLink (meta 003, P7); ponlo en false.", file=sys.stderr)
        return 2

    # Grabacion: se crea antes de abrir la camara para fallar pronto si la salida ya existe.
    log = None
    if args.record:
        from diagnostics.pose_log import PoseLog
        log = PoseLog(Path(args.record),
                      Path(args.save_frames) if args.save_frames else None,
                      args.frames_every)
        print(f"[Grabacion] {args.record}"
              + (f" (frames cada {args.frames_every} en {args.save_frames})"
                 if args.save_frames else ""))
    if args.timing and Path(args.timing).exists():
        raise FileExistsError(f"La salida de tiempos ya existe, no se pisa: {args.timing}")

    # La camara se crea aqui y se abre despues de que Slicer se conecte al servidor.
    cam = create_backend(cfg["camera"])
    tracker = MarkerTracker(cfg["markers"], cfg.get("filtering"))
    port = int(cfg_igtl["transforms_port"])
    sender = IgtlSender(port)
    print(f"[Esperando] Conecta Slicer como cliente a ese puerto (tope {args.slicer_timeout:.0f} s).")
    print("Presiona 'q' en la ventana para salir.")

    show_window = bool(cfg.get("debug", {}).get("show_window", True)) and not args.no_window
    verbose = bool(cfg.get("debug", {}).get("verbose", False))
    clock = time.perf_counter      # el reloj del bucle y del 1-Euro (fase 7); time.time solo para metadatos
    n_frames = 0
    t_wall_start = time.time()
    t_start = last_fps_print = t_last_frame = 0.0     # se fijan al arrancar el bucle
    K = dist = None
    sw = None
    grabber = None
    rc = 0
    mark, end_frame = _no_mark, _no_end_frame
    try:
        t_wait = clock()
        if not sender.wait_for_client(args.slicer_timeout):
            raise SlicerNotConnected(
                f"Slicer no se conecto al puerto {port} en {args.slicer_timeout:.0f} s: abre su "
                f"conector OpenIGTLink (cliente, localhost:{port}) y vuelve a lanzar el tracker")
        print(f"[OpenIGTLink] Cliente conectado ({clock() - t_wait:.1f} s)")

        cam.open()          # el warmup va dentro de open()
        K, dist = cam.get_intrinsics()
        print(f"[Calibracion] K cargada de la camara:\n{K}")
        print(f"  dist = {dist}")
        if args.timing:
            # Su reloj es perf_counter, no time.time: no toca los tiempos del 1-Euro.
            from diagnostics.pose_log import Stopwatch
            sw = Stopwatch()
            mark, end_frame = sw.mark, sw.end_frame
            print(f"[Tiempos] Cronometrando cada etapa -> {args.timing}")

        t_wall_start = time.time()
        t_start = last_fps_print = t_last_frame = clock()
        Grabber = SyncGrabber if args.sync_capture else FrameGrabber
        grabber = Grabber(cam, clock=clock, max_failures=MAX_READ_FAILURES)
        grabber.start()
        print(f"[Captura] {'en el bucle (--sync-capture)' if args.sync_capture else 'en un hilo, ultimo frame'}")
        while True:
            got = grabber.next_frame(READ_TIMEOUT_S)
            if got is None:
                if grabber.failed:
                    print("[ERROR] Camara no entrega frames. Saliendo.")
                    break
                if clock() - t_last_frame > STALL_TIMEOUT_S:
                    print(f"[ERROR] Ningun frame en {STALL_TIMEOUT_S:.0f} s. Saliendo.")
                    break
                continue
            frame, t_now, _seq = got
            t_last_frame = t_now
            if n_frames == 0:
                print(f"[Camara] Primer frame OK: shape={frame.shape}, dtype={frame.dtype}")
            n_frames += 1
            mark("capture")         # desde el frame anterior: la espera por un frame nuevo

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mark("gray")
            corners, ids = tracker.detect(gray)
            mark("detect")
            poses = (tracker.process_corners(zip(ids.flatten().tolist(), corners), t_now, K, dist)
                     if ids is not None and len(ids) > 0 else [])
            mark("pose_filter")
            for p in poses:
                sender.send(f"{p.name}ToTracker", p.matrix)
                if verbose:
                    print(f"  [{p.name}] t=[{p.tvec[0, 0]:.1f}, {p.tvec[1, 0]:.1f}, {p.tvec[2, 0]:.1f}]")
            mark("send")

            if log is not None:
                log.add(t_now, ids, corners, [(p.name, p.matrix) for p in poses], gray)
                mark("record")

            if show_window:
                display = frame.copy()
                draw_poses(display, poses, K, dist)
                mark("draw")
                cv2.imshow(WINDOW_TITLE, display)
                mark("imshow")
                key = cv2.waitKey(1)
                mark("key")
                if key & 0xFF == ord("q"):
                    break

            if t_now - last_fps_print > 5.0:
                el = t_now - t_start
                print(f"[FPS] Promedio: {n_frames / el:.1f} (camara {grabber.frames_read / el:.1f} fps, "
                      f"saltados {grabber.skipped}, sin cliente {sender.dropped})")
                last_fps_print = t_now
            end_frame()

            if args.duration is not None and t_now - t_start >= args.duration:
                print(f"[Duracion] {args.duration:.0f} s cumplidos, saliendo.")
                break

    except SlicerNotConnected as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        rc = EXIT_NO_SLICER
    except KeyboardInterrupt:
        print("\n[Interrupcion del usuario]")
    finally:
        t_loop_end = clock()            # antes de cerrar nada
        if grabber is not None:
            grabber.stop()              # el hilo suelta la camara antes de cerrarla
        cam.close()
        if show_window:
            cv2.destroyAllWindows()
        sender.close()
        capture = _capture_stats(grabber, n_frames, t_loop_end - t_start)
        if log is not None and K is not None:
            t_wall_end = time.time()
            cal = (cfg.get("camera", {}) or {}).get("calibration_file")
            meta = {
                "config": str(Path(args.config).resolve()),
                "config_sha256": _sha256(args.config),
                "calibration_file": str(Path(cal).resolve()) if cal else None,
                "calibration_sha256": _sha256(cal) if cal and Path(cal).is_file() else None,
                "argv": sys.argv if argv is None else list(argv),
                "show_window": bool(show_window), "verbose": bool(verbose),
                "markers": cfg["markers"].get("list", []),
                "dictionary": cfg["markers"]["dictionary"],
                "detector": cfg["markers"].get("detector", {}) or {},
                "filtering": cfg.get("filtering"),
                "whitelist": sorted(int(x) for x in tracker.valid_ids),
                "t_start": t_wall_start, "t_end": t_wall_end, "frames": n_frames,
                "t_loop_start": t_start, "t_loop_end": t_loop_end,      # reloj de timestamps
                "fps_average": (n_frames / (t_loop_end - t_start)
                                if t_loop_end > t_start else None),
                "clock": "time.perf_counter", "capture": capture,
                "sent": sender.sent, "dropped": sender.dropped,
                "opencv": cv2.__version__, "numpy": np.__version__,
            }
            path = log.save(K, dist, meta)
            fps_txt = f"{meta['fps_average']:.1f}" if meta["fps_average"] is not None else "-"
            print(f"[Grabacion] Guardada {path}: {log.n_frames} frames, fps medio {fps_txt}")
        if sw is not None:
            _save_timing(sw, args, argv, show_window, n_frames, t_start, t_loop_end, capture)
        if grabber is not None and n_frames:
            el = t_loop_end - t_start
            fps_cam = f" ({capture['fps_camera']:.1f} fps)" if capture["fps_camera"] else ""
            fps_loop = f" ({n_frames / el:.1f} fps)" if el > 0 else ""
            print(f"[Captura] Camara {capture['frames_read']} frames{fps_cam}; bucle {n_frames}"
                  f"{fps_loop}; saltados {capture['frames_skipped']}")
        print("[Salida limpia]")
    return rc


if __name__ == "__main__":
    sys.exit(main())
