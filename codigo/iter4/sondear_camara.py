# -*- coding: utf-8 -*-
"""
sondear_camara.py -- Sonda de una camara UVC (meta 002, fase 1).

Mide, sin tocar camera_backend.py ni el tracker:
  - identidad: las camaras que enumera Media Foundation (camaras_uvc.py), con
    su instancia USB, y cual es la del --source;
  - controles: por cada uno de CONTROLES, el valor leido, si `set` lo acepta
    (prueba con valor +/- paso y vuelve al original) y si la lectura de vuelta
    coincide; con --solo-leer, solo lee (para ver si un ajuste hecho con AMCap
    persiste tras desenchufar sin que la sonda lo toque);
  - modos: por cada modo pedido, lo que reporta `get`, el tamano real del
    primer frame y los FPS de captura sola (sin deteccion ni ventana).

Con --verificar-orden, en vez de lo anterior abre por MSMF cada indice que
enumera Media Foundation y da el brillo medio del frame: el autor tapa una
lente y comprueba que el indice oscuro es el de la instancia de esa camara.

Todo lleva tope de tiempo (--timeout) y libera la camara (principio 9). Los
argumentos van explicitos (principio 7). Ejemplo:

    python iter4\\sondear_camara.py --source 0 --backend MSMF --fps 60 ^
        --modos 640x480:MJPG,1280x720:MJPG,1920x1200:MJPG,640x480:YUY2 ^
        --segundos 5 --salida "..\\Claude outputs\\camaras\\sonda_gs1_msmf.json" ^
        --timeout 300
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path

import cv2

# Nombre del control (el que usara el perfil) -> propiedad de cv2.
CONTROLES: dict[str, int] = {
    "exposure": cv2.CAP_PROP_EXPOSURE,
    "auto_exposure": cv2.CAP_PROP_AUTO_EXPOSURE,
    "gain": cv2.CAP_PROP_GAIN,
    "auto_wb": cv2.CAP_PROP_AUTO_WB,
    "wb_temperature": cv2.CAP_PROP_WB_TEMPERATURE,
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast": cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "sharpness": cv2.CAP_PROP_SHARPNESS,
    "gamma": cv2.CAP_PROP_GAMMA,
    "backlight": cv2.CAP_PROP_BACKLIGHT,
    "focus": cv2.CAP_PROP_FOCUS,
}

# Paso de prueba de los controles numericos. Si el paso no es multiplo del
# paso real del dispositivo, el driver redondea y la lectura no coincide: eso
# se reporta tal cual, con el valor leido.
PASOS: dict[str, float] = {
    "exposure": 1.0,         # MSMF/DSHOW: log2 de segundos (-13..-1 tipico)
    "gain": 1.0,
    "wb_temperature": 100.0,
    "brightness": 1.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "sharpness": 1.0,
    "gamma": 1.0,
    "backlight": 1.0,
    "focus": 1.0,
}
# Controles de encendido/apagado: valores candidatos (convenciones distintas
# segun backend; la sonda mide cual acepta).
CANDIDATOS_AUTO: dict[str, list[float]] = {
    "auto_exposure": [0.0, 1.0, 0.25, 0.75, 3.0],
    "auto_wb": [0.0, 1.0],
}
TOLERANCIA = 1e-3

BACKENDS = ("MSMF", "DSHOW")


def _backend_cv2(nombre: str) -> int:
    return {"MSMF": cv2.CAP_MSMF, "DSHOW": cv2.CAP_DSHOW}[nombre.upper()]


def _coincide(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= TOLERANCIA


def valores_de_prueba(nombre: str, inicial: float) -> list[float]:
    """Los valores que la sonda intenta poner en el control `nombre`."""
    if nombre in CANDIDATOS_AUTO:
        return [v for v in CANDIDATOS_AUTO[nombre] if not _coincide(v, inicial)]
    paso = PASOS.get(nombre, 1.0)
    return [inicial + paso, inicial - paso]


def sondear_controles(cap, nombres: list[str], solo_leer: bool = False) -> list[dict]:
    """Por control: valor leido, si `set` lo acepta y si la lectura coincide.

    Lee primero todos los valores iniciales; prueba cada control y lo devuelve
    a su valor; al final restaura todos (los numericos antes que los auto,
    porque poner una exposicion puede apagar la autoexposicion) y relee.
    """
    props = CONTROLES
    desconocidos = [n for n in nombres if n not in props]
    if desconocidos:
        raise ValueError(f"controles desconocidos: {desconocidos}; validos: {list(props)}")

    iniciales = {n: float(cap.get(props[n])) for n in nombres}
    filas = []
    for n in nombres:
        fila = {"control": n, "prop": props[n], "inicial": iniciales[n],
                "pruebas": [], "acepta": None, "restaurado": None}
        if not solo_leer:
            aceptado = False
            for v in valores_de_prueba(n, iniciales[n]):
                set_ok = bool(cap.set(props[n], v))
                leido = float(cap.get(props[n]))
                coincide = _coincide(leido, v)
                fila["pruebas"].append({"valor": v, "set_ok": set_ok,
                                        "leido": leido, "coincide": coincide})
                aceptado = aceptado or (set_ok and coincide)
                cap.set(props[n], iniciales[n])
            fila["acepta"] = aceptado
        filas.append(fila)

    if not solo_leer:
        orden = [n for n in nombres if n not in CANDIDATOS_AUTO] + \
                [n for n in nombres if n in CANDIDATOS_AUTO]
        for n in orden:
            cap.set(props[n], iniciales[n])
        for fila in filas:
            final = float(cap.get(props[fila["control"]]))
            fila["final"] = final
            fila["restaurado"] = _coincide(final, fila["inicial"])
    return filas


def parsear_modos(texto: str) -> list[tuple[int, int, str]]:
    """'640x480:MJPG,1280x720:YUY2' -> [(640, 480, 'MJPG'), (1280, 720, 'YUY2')]."""
    modos = []
    for trozo in [t.strip() for t in texto.split(",") if t.strip()]:
        try:
            tam, fourcc = trozo.split(":")
            w, h = tam.lower().split("x")
            modo = (int(w), int(h), fourcc.strip().upper())
        except ValueError:
            raise ValueError(f"modo mal escrito: '{trozo}' (forma: 1280x720:MJPG)")
        if len(modo[2]) != 4 or modo[0] <= 0 or modo[1] <= 0:
            raise ValueError(f"modo mal escrito: '{trozo}' (forma: 1280x720:MJPG)")
        modos.append(modo)
    if not modos:
        raise ValueError("--modos vacio")
    return modos


def fourcc_texto(valor: float) -> str:
    v = int(valor)
    if v <= 0:
        return ""
    return "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))


def sondear_modos(source: int, backend: str, modos: list[tuple[int, int, str]],
                  segundos: float, fps: float, limite: float | None = None) -> list[dict]:
    """Por modo: lo pedido, lo que reporta `get`, el tamano real y los FPS.

    Abre la camara de nuevo para cada modo (como lo hara el backend) y la
    libera al terminar. `limite` es un time.monotonic() tope: si se pasa, los
    modos que faltan quedan marcados como no medidos.
    """
    filas = []
    for (w, h, fcc) in modos:
        fila = {"pedido": {"ancho": w, "alto": h, "fourcc": fcc, "fps": fps}}
        if limite is not None and time.monotonic() + segundos + 10 > limite:
            fila["error"] = "no medido: tope de tiempo"
            filas.append(fila)
            continue
        t0 = time.monotonic()
        cap = cv2.VideoCapture(int(source), _backend_cv2(backend))
        try:
            if not cap.isOpened():
                fila["error"] = f"no abre source={source} backend={backend}"
                filas.append(fila)
                continue
            fila["abrir_s"] = round(time.monotonic() - t0, 2)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fcc))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_FPS, fps)
            fila["get"] = {
                "ancho": cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                "alto": cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "fourcc": fourcc_texto(cap.get(cv2.CAP_PROP_FOURCC)),
            }
            for _ in range(5):
                cap.read()
            ok, frame = cap.read()
            if not ok or frame is None:
                fila["error"] = "abre pero no entrega frames"
                filas.append(fila)
                continue
            fila["real"] = {"ancho": int(frame.shape[1]), "alto": int(frame.shape[0])}
            fila["tamano_coincide"] = (frame.shape[1], frame.shape[0]) == (w, h)
            n, fallos = 0, 0
            t1 = time.monotonic()
            while time.monotonic() - t1 < segundos:
                ok, frame = cap.read()
                if ok and frame is not None:
                    n += 1
                else:
                    fallos += 1
            dt = time.monotonic() - t1
            fila["frames"] = n
            fila["fallos"] = fallos
            fila["fps_captura"] = round(n / dt, 2) if dt > 0 else 0.0
        finally:
            cap.release()
        filas.append(fila)
        print(f"[sonda] modo {w}x{h} {fcc}: real {fila.get('real')} "
              f"fps_captura {fila.get('fps_captura')} {fila.get('error', '')}", flush=True)
    return filas


def identidad(source: int) -> dict:
    """Lo que enumera Media Foundation y cual es la camara `source`."""
    import camaras_uvc
    try:
        camaras = camaras_uvc.listar_camaras_msmf()
    except OSError as e:
        return {"error": str(e), "camaras": []}
    propia = next((c for c in camaras if c.indice == source), None)
    return {"camaras": [asdict(c) for c in camaras],
            "source": source,
            "esta": asdict(propia) if propia else None}


def verificar_orden(segundos_por_indice: float = 2.0) -> list[dict]:
    """Abre por MSMF cada indice enumerado y da el brillo medio del frame."""
    import camaras_uvc
    filas = []
    for c in camaras_uvc.listar_camaras_msmf():
        fila = {"indice": c.indice, "nombre": c.nombre, "instancia": c.instancia}
        cap = cv2.VideoCapture(c.indice, cv2.CAP_MSMF)
        try:
            if not cap.isOpened():
                fila["error"] = "no abre"
            else:
                medias = []
                t0 = time.monotonic()
                while time.monotonic() - t0 < segundos_por_indice:
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        medias.append(float(frame.mean()))
                fila["brillo_medio"] = round(sum(medias) / len(medias), 1) if medias else None
        finally:
            cap.release()
        filas.append(fila)
        print(f"[sonda] indice {c.indice} [{c.instancia}]: brillo medio "
              f"{fila.get('brillo_medio')} {fila.get('error', '')}", flush=True)
    return filas


def _vigilante(timeout: float, estado: dict, salida: Path | None) -> threading.Timer:
    """A los `timeout` s escribe lo medido y termina el proceso (el SO libera la camara)."""
    def disparar():
        print(f"[sonda] TIMEOUT a los {timeout:.0f} s: se guarda lo medido y se sale", flush=True)
        estado["timeout"] = True
        if salida is not None:
            try:
                salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
            except OSError:
                pass
        os._exit(2)
    t = threading.Timer(timeout, disparar)
    t.daemon = True
    t.start()
    return t


def imprimir_controles(filas: list[dict]) -> None:
    print("\n| control | inicial | acepta | pruebas (valor -> leido) | restaurado |")
    print("|---|---|---|---|---|")
    for f in filas:
        pruebas = "; ".join(f"{p['valor']:g}->{p['leido']:g}{'' if p['set_ok'] else ' (set False)'}"
                            for p in f["pruebas"]) or "-"
        print(f"| {f['control']} | {f['inicial']:g} | {f['acepta']} | {pruebas} | "
              f"{f['restaurado']} |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sonda de controles, modos e identidad de una camara UVC.")
    ap.add_argument("--source", type=int, help="indice de la camara (orden MSMF)")
    ap.add_argument("--backend", choices=BACKENDS, help="MSMF o DSHOW")
    ap.add_argument("--modos", help="lista 'AnchoxAlto:FOURCC' separada por comas")
    ap.add_argument("--fps", type=float, help="FPS que se piden en cada modo")
    ap.add_argument("--segundos", type=float, help="segundos de captura por modo")
    ap.add_argument("--solo-leer", action="store_true",
                    help="solo lee los controles, no los cambia (prueba de persistencia)")
    ap.add_argument("--verificar-orden", action="store_true",
                    help="abre cada indice MSMF y da su brillo medio (tapar una lente)")
    ap.add_argument("--salida", required=True, help="JSON de salida")
    ap.add_argument("--timeout", type=float, required=True, help="tope en segundos")
    args = ap.parse_args(argv)

    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv}

    if args.verificar_orden:
        vig = _vigilante(args.timeout, estado, salida)
        estado["verificar_orden"] = verificar_orden()
        vig.cancel()
        salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[sonda] guardado {salida}")
        if not estado["verificar_orden"]:
            print("[sonda] ERROR: Media Foundation no enumera ninguna camara de video")
            return 1
        return 0

    necesarios = ("source", "backend") if args.solo_leer else \
        ("source", "backend", "modos", "fps", "segundos")
    faltan = [n for n in necesarios if getattr(args, n) is None]
    if faltan:
        ap.error("faltan argumentos explicitos: " + ", ".join("--" + f for f in faltan))
    modos = None if args.solo_leer else parsear_modos(args.modos)
    limite = time.monotonic() + args.timeout
    vig = _vigilante(args.timeout, estado, salida)
    try:
        estado["opencv"] = cv2.__version__
        estado["backend"] = args.backend
        estado["identidad"] = identidad(args.source)
        if args.backend != "MSMF":
            estado["identidad"]["nota"] = ("la identidad es del orden MSMF; con "
                                           f"{args.backend} el indice puede ser otro")
        esta = estado["identidad"].get("esta")
        print(f"[sonda] source={args.source} backend={args.backend}: "
              f"{esta['nombre'] + ' [' + str(esta['instancia']) + ']' if esta else 'sin identidad MSMF'}",
              flush=True)

        cap = cv2.VideoCapture(args.source, _backend_cv2(args.backend))
        try:
            if not cap.isOpened():
                print(f"[sonda] ERROR: no abre source={args.source} backend={args.backend}")
                return 1
            for _ in range(5):
                cap.read()
            estado["solo_leer"] = args.solo_leer
            estado["controles"] = sondear_controles(cap, list(CONTROLES), args.solo_leer)
        finally:
            cap.release()
        imprimir_controles(estado["controles"])

        if not args.solo_leer:
            estado["modos"] = sondear_modos(args.source, args.backend, modos,
                                            args.segundos, args.fps, limite)
    finally:
        vig.cancel()
    salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sonda] guardado {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
