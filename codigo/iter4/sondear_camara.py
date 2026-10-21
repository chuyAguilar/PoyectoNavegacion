# -*- coding: utf-8 -*-
"""
sondear_camara.py -- Sonda de una camara UVC (meta 002, fase 1).

Mide, sin tocar camera_backend.py ni el tracker:
  - identidad: las camaras que enumera Media Foundation (camaras_uvc.py), con
    su instancia USB, y cual es la del --source;
  - modos: por cada modo pedido, lo que reporta `get`, el tamano real del
    primer frame y los FPS de captura sola (sin deteccion ni ventana). Se miden
    SIEMPRE antes de escribir ningun control, con la camara como la dejo el
    autor;
  - controles, segun --controles:
      no      no los lee ni los escribe (solo modos);
      leer    los lee sin escribir (prueba de persistencia tras desenchufar);
      probar  los escribe (valor +/- paso), lee de vuelta, mira el efecto en la
              imagen (brillo medio) y los devuelve a su valor; antes y despues,
              un testigo (brillo medio y FPS) dice si la camara quedo igual.

Por que los controles solo por DSHOW (sesion en vivo del 2026-10-20, camara 1):
por MSMF, get() de los controles no refleja la camara (la sonda dejo la
exposicion en 0 y get seguia leyendo -6, el valor por defecto), y
set(CAP_PROP_AUTO_EXPOSURE, v) escribe v como valor de la exposicion. Por DSHOW,
OpenCV lee el valor actual (cap_dshow.cpp: IAMCameraControl::GetRange y luego
Get). Ademas, la escritura que no cambia la lectura se marca "no verificable".

Con --verificar-orden, en vez de lo anterior abre por MSMF cada indice que
enumera Media Foundation y da el brillo medio del frame: el autor tapa una
lente y comprueba que el indice oscuro es el de la instancia de esa camara.

Todo lleva tope de tiempo (--timeout) y libera la camara (principio 9); si el
tope no alcanza para los modos pedidos, la sonda no empieza. Los argumentos van
explicitos (principio 7). Ejemplos:

    python iter4\\sondear_camara.py --source 0 --backend MSMF --controles no ^
        --fps 90 --modos 640x480:MJPG,1280x720:MJPG,1920x1200:MJPG ^
        --segundos 5 --salida "..\\Claude outputs\\camaras\\modos_gs1_msmf.json" ^
        --timeout 300
    python iter4\\sondear_camara.py --source 0 --backend DSHOW --controles probar ^
        --salida "..\\Claude outputs\\camaras\\controles_gs1_dshow.json" --timeout 180
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
    "exposure": 1.0,         # IAMCameraControl (MSMF y DSHOW): log2 de segundos
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
# Escribir un control auto puede pisar el valor numerico que gobierna (en MSMF,
# set(AUTO_EXPOSURE, v) escribe v como exposicion): tras devolver el auto a su
# valor se reescribe el numerico, y en la restauracion final los auto van
# primero y los numericos despues.
DEPENDIENTES: dict[str, list[str]] = {
    "auto_exposure": ["exposure"],
    "auto_wb": ["wb_temperature"],
}
TOLERANCIA = 1e-3

BACKENDS = ("MSMF", "DSHOW")
MODOS_CONTROLES = ("no", "leer", "probar")
MOTIVO_MSMF = (
    "por MSMF los controles no se leen ni se prueban: get() no refleja la camara "
    "(sesion del 2026-10-20: la sonda dejo la exposicion en 0 y get seguia leyendo -6) "
    "y set(CAP_PROP_AUTO_EXPOSURE, v) escribe v como exposicion. Usa --backend DSHOW "
    "para --controles leer|probar; por MSMF solo --controles no.")

# Presupuesto de tiempo (medido en vivo, 2026-10-20: abrir por MSMF tarda
# 9.5-13 s). Si el tope no alcanza, la sonda no empieza. Lo que tarda una
# lectura fallida no se ha medido: cada modo guarda su total_s para ajustarlo.
ABRIR_S = 12.0
MARGEN_MODO_S = 4.0
IDENTIDAD_S = 5.0
CONTROLES_LEER_S = ABRIR_S + 5.0
CONTROLES_PROBAR_S = ABRIR_S + 60.0
RESERVA_RESTAURAR_S = 15.0

# Testigo de que la camara quedo igual: brillo medio y FPS antes y despues.
TESTIGO_S = 2.0
TOL_BRILLO = 0.10   # relativa
TOL_FPS = 0.20      # relativa


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


def orden_restauracion(nombres: list[str]) -> list[str]:
    """Los auto primero y los numericos despues: el ultimo que escribe la exposicion es su valor."""
    return [n for n in nombres if n in CANDIDATOS_AUTO] + \
           [n for n in nombres if n not in CANDIDATOS_AUTO]


def clasificar_escritura(inicial: float, pruebas: list[dict]) -> str | None:
    """Que se sabe de la escritura de un control, a partir de sus pruebas.

    verificada      set True y la lectura coincide con lo escrito (al menos una);
    rechazada       set False en todas;
    no verificable  set True pero la lectura sigue en el inicial (no refleja la camara);
    no coincide     la lectura cambia pero no al valor escrito (p. ej. el driver redondea).
    """
    if not pruebas:
        return None
    aceptadas = [p for p in pruebas if p["set_ok"]]
    if not aceptadas:
        return "rechazada"
    if any(p["coincide"] for p in aceptadas):
        return "verificada"
    if all(_coincide(p["leido"], inicial) for p in aceptadas):
        return "no verificable"
    return "no coincide"


def brillo(cap, descartar: int = 2) -> float | None:
    """Brillo medio de un frame, tras descartar `descartar` (para que el cambio llegue)."""
    for _ in range(descartar):
        ok, _f = cap.read()
        if not ok:
            return None
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    return round(float(frame.mean()), 2)


def testigo(cap, segundos: float) -> dict:
    """Brillo medio y FPS durante `segundos`: la huella de como esta la camara."""
    medias, t0 = [], time.monotonic()
    while time.monotonic() - t0 < segundos:
        ok, frame = cap.read()
        if ok and frame is not None:
            medias.append(float(frame.mean()))
    dt = time.monotonic() - t0
    return {"frames": len(medias),
            "fps": round(len(medias) / dt, 2) if dt > 0 else 0.0,
            "brillo": round(sum(medias) / len(medias), 2) if medias else None}


def comparar_testigos(antes: dict, despues: dict, tol_brillo: float = TOL_BRILLO,
                      tol_fps: float = TOL_FPS) -> list[str]:
    """Diferencias entre dos testigos fuera de tolerancia (relativa); vacia si quedo igual."""
    difs = []
    for clave, tol in (("brillo", tol_brillo), ("fps", tol_fps)):
        a, d = antes.get(clave), despues.get(clave)
        if a is None or d is None:
            difs.append(f"{clave}: sin dato (antes {a}, despues {d})")
        elif abs(d - a) > tol * max(abs(a), 1e-9):
            difs.append(f"{clave}: {a:g} -> {d:g} (tolerancia {tol:.0%})")
    return difs


def sondear_controles(cap, nombres: list[str], solo_leer: bool = False,
                      con_brillo: bool = False, limite: float | None = None) -> list[dict]:
    """Por control: valor leido y, si no es solo_leer, que pasa al escribirlo.

    Lee primero todos los valores iniciales; prueba cada control y lo devuelve
    a su valor (y a sus dependientes, si es un auto); al final restaura todos,
    los auto antes que los numericos, y relee. Con `con_brillo`, anota el
    brillo medio tras cada escritura (el efecto en la imagen, independiente de
    get). Si se acerca `limite` (time.monotonic()), deja de probar y restaura.
    """
    props = CONTROLES
    desconocidos = [n for n in nombres if n not in props]
    if desconocidos:
        raise ValueError(f"controles desconocidos: {desconocidos}; validos: {list(props)}")

    iniciales = {n: float(cap.get(props[n])) for n in nombres}
    filas = []
    for n in nombres:
        fila = {"control": n, "prop": props[n], "inicial": iniciales[n],
                "pruebas": [], "acepta": None, "escritura": None, "restaurado": None}
        if not solo_leer:
            if limite is not None and time.monotonic() > limite - RESERVA_RESTAURAR_S:
                fila["escritura"] = "no probado: tope de tiempo"
                filas.append(fila)
                continue
            for v in valores_de_prueba(n, iniciales[n]):
                set_ok = bool(cap.set(props[n], v))
                leido = float(cap.get(props[n]))
                prueba = {"valor": v, "set_ok": set_ok, "leido": leido,
                          "coincide": _coincide(leido, v)}
                if con_brillo:
                    prueba["brillo"] = brillo(cap)
                fila["pruebas"].append(prueba)
                cap.set(props[n], iniciales[n])
                for d in DEPENDIENTES.get(n, []):
                    if d in iniciales:
                        cap.set(props[d], iniciales[d])
            fila["escritura"] = clasificar_escritura(iniciales[n], fila["pruebas"])
            fila["acepta"] = fila["escritura"] == "verificada"
        filas.append(fila)

    if not solo_leer:
        for n in orden_restauracion(nombres):
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
    """El FOURCC como texto; si no son 4 caracteres imprimibles (MSMF da otro codigo), en hex."""
    v = int(valor)
    if v <= 0:
        return ""
    texto = "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))
    return texto if all(32 < ord(c) < 127 for c in texto) else f"0x{v:08X}"


def estimar_segundos(n_modos: int, segundos: float, controles: str) -> float:
    """Tiempo que necesita la sonda, con el presupuesto medido en vivo."""
    total = IDENTIDAD_S + n_modos * (ABRIR_S + segundos + MARGEN_MODO_S)
    if controles == "leer":
        total += CONTROLES_LEER_S
    elif controles == "probar":
        total += CONTROLES_PROBAR_S + 2 * TESTIGO_S
    return total


def resumir_modos(filas: list[dict]) -> dict:
    """Cuantos modos se pidieron, se midieron, no entregaron frames, no abrieron o quedaron sin medir."""
    errores = [f.get("error", "") for f in filas]
    return {
        "pedidos": len(filas),
        "medidos": sum(1 for f in filas if "fps_captura" in f),
        "sin_frames": sum(1 for e in errores if e.startswith("abre pero")),
        "no_abre": sum(1 for e in errores if e.startswith("no abre")),
        "sin_medir_tope": sum(1 for e in errores if e.startswith("no medido")),
        "tamano_distinto": sum(1 for f in filas if f.get("tamano_coincide") is False),
    }


def sondear_modos(source: int, backend: str, modos: list[tuple[int, int, str]],
                  segundos: float, fps: float, limite: float | None = None) -> list[dict]:
    """Por modo: lo pedido, lo que reporta `get`, el tamano real y los FPS.

    Abre la camara de nuevo para cada modo (como lo hara el backend) y la
    libera al terminar. No escribe ningun control. `limite` es un
    time.monotonic() tope: si no alcanza para un modo, los que faltan quedan
    marcados como no medidos. Un modo que no entrega el primer frame se deja
    al primer fallo (cada lectura fallida puede tardar segundos).
    """
    filas = []
    for (w, h, fcc) in modos:
        fila = {"pedido": {"ancho": w, "alto": h, "fourcc": fcc, "fps": fps}}
        if limite is not None and time.monotonic() + ABRIR_S + segundos > limite:
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
            frame = None
            for _ in range(6):
                ok, frame = cap.read()
                if not ok or frame is None:
                    frame = None
                    break
            if frame is None:
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
            fila["total_s"] = round(time.monotonic() - t0, 2)  # para ajustar ABRIR_S/MARGEN_MODO_S
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
    print("\n| control | inicial | escritura | pruebas (valor -> leido [brillo]) | restaurado |")
    print("|---|---|---|---|---|")
    for f in filas:
        pruebas = "; ".join(
            f"{p['valor']:g}->{p['leido']:g}{'' if p['set_ok'] else ' (set False)'}"
            f"{' [' + format(p['brillo'], 'g') + ']' if p.get('brillo') is not None else ''}"
            for p in f["pruebas"]) or "-"
        print(f"| {f['control']} | {f['inicial']:g} | {f['escritura']} | {pruebas} | "
              f"{f['restaurado']} |")


def imprimir_resumen_modos(r: dict) -> None:
    print(f"[sonda] modos: {r['pedidos']} pedidos, {r['medidos']} medidos, "
          f"{r['sin_frames']} sin frames, {r['no_abre']} no abren, "
          f"{r['sin_medir_tope']} sin medir por el tope, "
          f"{r['tamano_distinto']} con tamano real distinto del pedido", flush=True)


def _controles(args, estado: dict, limite: float) -> int:
    """Lee o prueba los controles por DSHOW; 0 si la camara quedo igual, 1 si no."""
    probar = args.controles == "probar"
    cap = cv2.VideoCapture(args.source, _backend_cv2(args.backend))
    rc = 0
    try:
        if not cap.isOpened():
            print(f"[sonda] ERROR: no abre source={args.source} backend={args.backend}")
            return 1
        for _ in range(5):
            ok, _f = cap.read()
            if not ok:
                break
        if probar:
            estado["testigo_antes"] = testigo(cap, TESTIGO_S)
        estado["controles"] = sondear_controles(cap, list(CONTROLES), solo_leer=not probar,
                                                con_brillo=probar, limite=limite)
        if probar:
            estado["testigo_despues"] = testigo(cap, TESTIGO_S)
            difs = comparar_testigos(estado["testigo_antes"], estado["testigo_despues"])
            no_rest = [f["control"] for f in estado["controles"] if f["restaurado"] is False]
            estado["camara_quedo_igual"] = not difs and not no_rest
            estado["diferencias_testigo"] = difs
            if difs or no_rest:
                rc = 1
    finally:
        cap.release()
    imprimir_controles(estado["controles"])
    if probar:
        print(f"[sonda] testigo antes {estado['testigo_antes']} despues {estado['testigo_despues']}")
        if rc:
            print("[sonda] ATENCION: la camara puede haber quedado cambiada "
                  f"(testigo: {estado['diferencias_testigo'] or 'igual'}; "
                  f"no restaurados por get: {no_rest or 'ninguno'}). "
                  "Revisa AMCap y pon Predeterminado antes de seguir.", flush=True)
        else:
            print("[sonda] la camara quedo igual (get y testigo); confirmalo en AMCap.")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sonda de controles, modos e identidad de una camara UVC.")
    ap.add_argument("--source", type=int, help="indice de la camara (orden MSMF)")
    ap.add_argument("--backend", choices=BACKENDS, help="MSMF o DSHOW")
    ap.add_argument("--controles", choices=MODOS_CONTROLES,
                    help="no: ni lee ni escribe; leer: solo lee; probar: escribe y restaura (solo DSHOW)")
    ap.add_argument("--modos", help="lista 'AnchoxAlto:FOURCC' separada por comas")
    ap.add_argument("--fps", type=float, help="FPS que se piden en cada modo")
    ap.add_argument("--segundos", type=float, help="segundos de captura por modo")
    ap.add_argument("--verificar-orden", action="store_true",
                    help="abre cada indice MSMF y da su brillo medio (tapar una lente)")
    ap.add_argument("--salida", required=True, help="JSON de salida")
    ap.add_argument("--timeout", type=float, required=True, help="tope en segundos")
    args = ap.parse_args(argv)

    salida = Path(args.salida)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv}

    if args.verificar_orden:
        salida.parent.mkdir(parents=True, exist_ok=True)
        vig = _vigilante(args.timeout, estado, salida)
        estado["verificar_orden"] = verificar_orden()
        vig.cancel()
        salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[sonda] guardado {salida}")
        if not estado["verificar_orden"]:
            print("[sonda] ERROR: Media Foundation no enumera ninguna camara de video")
            return 1
        return 0

    faltan = [n for n in ("source", "backend", "controles") if getattr(args, n) is None]
    if faltan:
        ap.error("faltan argumentos explicitos: " + ", ".join("--" + f for f in faltan))
    de_modos = [n for n in ("modos", "fps", "segundos") if getattr(args, n) is not None]
    if de_modos and len(de_modos) < 3:
        ap.error("--modos, --fps y --segundos van juntos")
    if args.controles == "no" and not de_modos:
        ap.error("con --controles no hacen falta --modos, --fps y --segundos (si no, no hay nada que medir)")
    if args.backend == "MSMF" and args.controles != "no":
        ap.error(MOTIVO_MSMF)
    try:
        modos = parsear_modos(args.modos) if de_modos else []
    except ValueError as e:
        ap.error(str(e))
    estimado = estimar_segundos(len(modos), args.segundos or 0.0, args.controles)
    if estimado > args.timeout:
        ap.error(f"el tope no alcanza: {len(modos)} modos x ~{ABRIR_S + (args.segundos or 0) + MARGEN_MODO_S:.0f} s"
                 f" + controles '{args.controles}' = ~{estimado:.0f} s > --timeout {args.timeout:.0f};"
                 " sube --timeout o quita modos")

    salida.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + args.timeout
    vig = _vigilante(args.timeout, estado, salida)
    rc = 0
    try:
        estado["opencv"] = cv2.__version__
        estado["backend"] = args.backend
        estado["controles_modo"] = args.controles
        estado["estimado_s"] = round(estimado, 1)
        estado["identidad"] = identidad(args.source)
        if args.backend != "MSMF":
            estado["identidad"]["nota"] = ("la identidad es del orden MSMF; con "
                                           f"{args.backend} el indice puede ser otro")
        esta = estado["identidad"].get("esta")
        print(f"[sonda] source={args.source} backend={args.backend}: "
              f"{esta['nombre'] + ' [' + str(esta['instancia']) + ']' if esta else 'sin identidad MSMF'}",
              flush=True)

        # Los modos, siempre antes de escribir ningun control.
        if modos:
            reserva = CONTROLES_PROBAR_S if args.controles == "probar" else \
                CONTROLES_LEER_S if args.controles == "leer" else 0.0
            estado["modos"] = sondear_modos(args.source, args.backend, modos,
                                            args.segundos, args.fps, limite - reserva)
            estado["resumen_modos"] = resumir_modos(estado["modos"])
            imprimir_resumen_modos(estado["resumen_modos"])

        if args.controles != "no":
            estado["lectura_controles"] = (
                "DSHOW: get() lee el valor actual (cap_dshow.cpp: GetRange y luego Get); "
                "se confirma con el testigo y con AMCap")
            rc = _controles(args, estado, limite)
    finally:
        vig.cancel()
    salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sonda] guardado {salida}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
