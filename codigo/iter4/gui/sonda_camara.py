# -*- coding: utf-8 -*-
"""
sonda_camara.py — Chequeo corto de "camara disponible" (brief §5.4, Paso 8).

Corre como SUBPROCESO del panel (nunca en el proceso de la GUI: un driver
colgado no debe congelar la ventana; el panel lo mata via watchdog a los 20 s).

  webcam:    resuelve el indice (por la ruta del puerto si el perfil trae
             `usb_port_windows`; si no, `source`), abre cv2.VideoCapture con el
             backend y el modo del perfil (FOURCC, ancho, alto, FPS), lee UN
             frame, dice el tamano real frente al del perfil y al del .yml de
             intrinsecos, y LIBERA el dispositivo inmediatamente. NO aplica
             `controls` ni comprueba la `marca` (eso lo hace el backend al
             abrir; aqui cabe en los 20 s del vigilante). Meta 002, fase 2b.
             Importa camaras_uvc antes que cv2: apaga la aceleracion HW de
             MSMF (abrir+leer ~1 s en vez de >40 s; correccion de la 2b).
  femtobolt: enumera dispositivos via pyorbbecsdk Context().query_devices()
             SIN abrir pipeline (no le roba la camara a nadie).

Exit 0 = camara disponible y tamano coincide; exit 1 = no disponible, o el
tamano real no es el del perfil o el del .yml (detalle en stdout).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

# iter4\ en sys.path: camera_backend y camaras_uvc viven ahi, no en gui\.
_ITER4 = Path(__file__).resolve().parents[1]
if str(_ITER4) not in sys.path:
    sys.path.insert(0, str(_ITER4))


def _resolver_ruta(p, cfg_dir):
    """Como cargar_config() de los scripts: relativa al CWD y al directorio del config."""
    if not p:
        return None
    for cand in (Path(p), Path(cfg_dir) / p):
        if cand.exists():
            return cand
    return Path(p)


def probar_webcam(cam, cfg_dir="."):
    import camaras_uvc   # antes de cv2: apaga la aceleracion HW de MSMF (fase 2b, correccion)
    import cv2
    backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
    backend_nombre = str(cam.get("backend", "MSMF")).upper()
    backend = backends.get(backend_nombre, cv2.CAP_MSMF)
    puerto = cam.get("usb_port_windows")
    if backend_nombre in ("MSMF", "ANY"):
        print(f"[CAMARA] {camaras_uvc.describir_aceleracion_msmf()}", flush=True)
    if puerto:
        t0 = time.time()
        listar = (camaras_uvc.listar_camaras_dshow if backend_nombre == "DSHOW"
                  else camaras_uvc.listar_camaras_msmf)
        source = camaras_uvc.resolver_indice(str(puerto), listar())
        print(f"[CAMARA] puerto {puerto} -> indice {backend_nombre} {source} "
              f"({time.time()-t0:.2f}s)", flush=True)
    elif cam.get("source") is not None:
        source = int(cam.get("source"))
    else:
        print("[CAMARA] NO DISPONIBLE: el perfil no trae ni usb_port_windows ni source")
        return 1
    ancho, alto = int(cam.get("width", 640)), int(cam.get("height", 480))
    fps = int(cam.get("fps", 30))
    fourcc = str(cam.get("fourcc", "MJPG") or "")
    print(f"[CAMARA] probando webcam source={source} backend={backend_nombre} "
          f"modo {ancho}x{alto} {fourcc or '-'} @ {fps}...", flush=True)
    t0 = time.time()
    cap = cv2.VideoCapture(source, backend)
    try:
        if not cap.isOpened():
            print(f"[CAMARA] NO DISPONIBLE: no se pudo abrir source={source}")
            return 1
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        cap.set(cv2.CAP_PROP_FPS, fps)
        ok, frame = cap.read()
        if not ok or frame is None:
            print(f"[CAMARA] NO DISPONIBLE: abrio pero no entrega frames")
            return 1
        h, w = frame.shape[:2]
        dt = time.time() - t0
        if (w, h) != (ancho, alto):
            print(f"[CAMARA] TAMANO DISTINTO: entrega {w}x{h}, el perfil pide "
                  f"{ancho}x{alto} (abrir+leer {dt:.1f}s)")
            return 1
        yml = cam.get("calibration_file")
        if yml:
            from camera_backend import leer_tamano_yml
            ruta = _resolver_ruta(yml, cfg_dir)
            try:
                esperado = leer_tamano_yml(ruta)
            except FileNotFoundError:
                print(f"[CAMARA] NO DISPONIBLE: no existe el .yml de intrinsecos {ruta}")
                return 1
            if esperado is None:
                print(f"[CAMARA] OK (aviso): entrega {w}x{h} = perfil; el .yml "
                      f"{ruta.name} no declara image_width/image_height (abrir+leer {dt:.1f}s)")
                return 0
            if esperado != (w, h):
                print(f"[CAMARA] TAMANO DISTINTO: entrega {w}x{h} = perfil, pero el .yml "
                      f"{ruta.name} es de {esperado[0]}x{esperado[1]} (abrir+leer {dt:.1f}s)")
                return 1
            print(f"[CAMARA] OK: webcam source={source} entrega {w}x{h} = perfil = .yml "
                  f"{ruta.name} (abrir+leer {dt:.1f}s)")
            return 0
        print(f"[CAMARA] OK: webcam source={source} entrega {w}x{h} = perfil; sin .yml "
              f"de intrinsecos en el perfil (abrir+leer {dt:.1f}s)")
        return 0
    finally:
        cap.release()
        print("[CAMARA] dispositivo liberado", flush=True)


def probar_femtobolt():
    print("[CAMARA] enumerando dispositivos Orbbec (sin abrir pipeline)...",
          flush=True)
    from pyorbbecsdk import Context
    dispositivos = Context().query_devices()
    try:
        n = dispositivos.get_count()
    except AttributeError:
        n = len(dispositivos)
    if n < 1:
        print("[CAMARA] NO DISPONIBLE: 0 dispositivos Orbbec conectados")
        return 1
    print(f"[CAMARA] OK: {n} dispositivo(s) Orbbec conectado(s)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Sonda corta de camara del panel.")
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    ruta = Path(args.config)
    with open(ruta, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cam = (cfg or {}).get("camera", {}) or {}
    ctype = str(cam.get("camera_type", "")).lower()
    print(f"[CAMARA] perfil {ruta.name}: camera_type={ctype}", flush=True)

    try:
        if ctype == "webcam":
            sys.exit(probar_webcam(cam, ruta.resolve().parent))
        elif ctype == "femtobolt":
            sys.exit(probar_femtobolt())
        else:
            print(f"[CAMARA] camera_type desconocido: '{ctype}'")
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[CAMARA] NO DISPONIBLE: error al sondear: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
