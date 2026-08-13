# -*- coding: utf-8 -*-
"""
sonda_camara.py — Chequeo corto de "camara disponible" (brief §5.4, Paso 8).

Corre como SUBPROCESO del panel (nunca en el proceso de la GUI: un driver
colgado no debe congelar la ventana; el panel lo mata via watchdog a los 20 s).

  webcam:    abre cv2.VideoCapture con el backend/source del perfil, lee UN
             frame y LIBERA el dispositivo inmediatamente.
  femtobolt: enumera dispositivos via pyorbbecsdk Context().query_devices()
             SIN abrir pipeline (no le roba la camara a nadie).

Exit 0 = camara disponible; exit 1 = no disponible (detalle en stdout).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def probar_webcam(cam):
    import cv2
    backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
    backend = backends.get(str(cam.get("backend", "MSMF")).upper(), cv2.CAP_MSMF)
    source = int(cam.get("source", 0))
    print(f"[CAMARA] probando webcam source={source} "
          f"backend={cam.get('backend', 'MSMF')}...", flush=True)
    cap = cv2.VideoCapture(source, backend)
    try:
        if not cap.isOpened():
            print(f"[CAMARA] NO DISPONIBLE: no se pudo abrir source={source}")
            return 1
        ok, frame = cap.read()
        if not ok or frame is None:
            print(f"[CAMARA] NO DISPONIBLE: abrio pero no entrega frames")
            return 1
        h, w = frame.shape[:2]
        print(f"[CAMARA] OK: webcam source={source} entrega {w}x{h}")
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
            sys.exit(probar_webcam(cam))
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
