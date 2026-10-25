r"""
Tracker ArUco de Marker0 para navegacion quirurgica: el bucle camara -> vision
-> envio por OpenIGTLink -> ventana.

Desde la meta 003, fase 4 · El tracker en piezas (ADR-027), este archivo solo
tiene el bucle. Las piezas: `camera.backend` (la camara), `vision.tracking`
(deteccion, pose IPPE_SQUARE y 1-Euro de la posicion: `MarkerTracker`),
`transport.igtl` (el servidor OpenIGTLink: `IgtlSender`) y `profiles` (el
perfil, con rutas relativas a codigo/). La pose multi-marker del dodecaedro
esta archivada en codigo/historico/iter4/dodecahedron/pose_rigid_body.py.

Lo que publica (principio 6, ADR-026): solo `Marker0ToTracker`, en el puerto
`igtlink.transforms_port` (18944). `igtlink.send_video: true` aborta (P7).

Uso (desde codigo\, con el venv; --config obligatorio, principio 7):
    python -m tracker --config profiles\tracker_config_gs1.yaml

Slicer se conecta como CLIENTE a localhost:18944 ANTES de arrancar: pyigtl
espera a que se vacie la cola de envio y sin cliente bloquea (CONTEXT.md 4.5).
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
import profiles
from transport.igtl import IgtlSender
from vision.tracking import MarkerPose, MarkerTracker

# El panel manda 'q' a la ventana por su titulo exacto (gui/recipes.VENTANAS["tracker"]).
WINDOW_TITLE = "Tracker Multi-Marker - q para salir"
MAX_READ_FAILURES = 300


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
    args = parser.parse_args(argv)
    if args.save_frames and not args.record:
        parser.error("--save-frames necesita --record")
    if args.frames_every < 1:
        parser.error("--frames-every tiene que ser >= 1")
    if args.duration is not None and args.duration <= 0:
        parser.error("--duration tiene que ser > 0")
    return args


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

    # La camara se crea aqui y se abre despues del servidor OpenIGTLink (como antes).
    cam = create_backend(cfg["camera"])
    tracker = MarkerTracker(cfg["markers"], cfg.get("filtering"))
    sender = IgtlSender(cfg_igtl["transforms_port"])
    print("[Esperando] Conecta Slicer como cliente a ese puerto.")
    print("Presiona 'q' en la ventana para salir.")

    show_window = bool(cfg.get("debug", {}).get("show_window", True)) and not args.no_window
    verbose = bool(cfg.get("debug", {}).get("verbose", False))
    n_frames = 0
    t_start = time.time()
    last_fps_print = t_start
    K = dist = None
    try:
        cam.open()          # el warmup va dentro de open()
        K, dist = cam.get_intrinsics()
        print(f"[Calibracion] K cargada de la camara:\n{K}")
        print(f"  dist = {dist}")
        t_start = last_fps_print = time.time()

        n_fail_consec = 0
        while True:
            frame, _depth, _ts = cam.read()
            if frame is None:
                n_fail_consec += 1
                if n_fail_consec in (1, 30, 100, MAX_READ_FAILURES):
                    print(f"[WARN] cam.read() retornando None ({n_fail_consec} consecutivos)")
                if n_fail_consec > MAX_READ_FAILURES:
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
            corners, ids = tracker.detect(gray)
            poses = (tracker.process_corners(zip(ids.flatten().tolist(), corners), t_now, K, dist)
                     if ids is not None and len(ids) > 0 else [])
            for p in poses:
                sender.send(f"{p.name}ToTracker", p.matrix)
                if verbose:
                    print(f"  [{p.name}] t=[{p.tvec[0, 0]:.1f}, {p.tvec[1, 0]:.1f}, {p.tvec[2, 0]:.1f}]")

            if log is not None:
                log.add(t_now, ids, corners, [(p.name, p.matrix) for p in poses], gray)

            if show_window:
                display = frame.copy()
                draw_poses(display, poses, K, dist)
                cv2.imshow(WINDOW_TITLE, display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if t_now - last_fps_print > 5.0:
                print(f"[FPS] Promedio: {n_frames / (t_now - t_start):.1f}")
                last_fps_print = t_now

            if args.duration is not None and t_now - t_start >= args.duration:
                print(f"[Duracion] {args.duration:.0f} s cumplidos, saliendo.")
                break

    except KeyboardInterrupt:
        print("\n[Interrupcion del usuario]")
    finally:
        cam.close()
        if show_window:
            cv2.destroyAllWindows()
        sender.close()
        if log is not None and K is not None:
            t_end = time.time()
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
                "t_start": t_start, "t_end": t_end, "frames": n_frames,
                "fps_average": n_frames / (t_end - t_start) if t_end > t_start else None,
                "opencv": cv2.__version__, "numpy": np.__version__,
            }
            path = log.save(K, dist, meta)
            fps_txt = f"{meta['fps_average']:.1f}" if meta["fps_average"] is not None else "-"
            print(f"[Grabacion] Guardada {path}: {log.n_frames} frames, fps medio {fps_txt}")
        print("[Salida limpia]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
