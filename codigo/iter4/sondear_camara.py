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

Con --verificar-orden --backend MSMF|DSHOW, en vez de lo anterior abre por ese
backend cada indice que enumera (Media Foundation o DirectShow) y da el brillo
medio del frame: el autor tapa una lente y comprueba que el indice oscuro es el
de la ruta de puerto de esa camara.

Modos de la fase 2a (identidad por puerto y controles por DSHOW; cada
medicion se guarda en el JSON al tenerla, B25):
  --puertos                 enumera MSMF y DSHOW con indice, instancia, ruta
                            del puerto y ubicacion;
  --leer --puerto R         lee los controles por DSHOW (capa de ajustes);
  --fijar "k=v,..." --puerto R [--forzar]
                            aplica por la capa (escribe solo lo que difiere,
                            relee) y los deja puestos; p. ej.
                            "exposure_ms=1.953,gain=11". Con --forzar escribe
                            cada control pedido aunque la lectura coincida y
                            relee: asi se da de alta la marca (sesion del
                            2026-10-22: el focus 332 de fabrica de la camara 2
                            saltaba sin escribir; escrito, quedo fijo 5 de 5);
  --tras-msmf --puerto R --modo 640x480:MJPG --fps 90 --segundos 10
                            lee por DSHOW, abre y captura por MSMF (testigo:
                            brillo, nitidez, FPS, tamano real), cierra y relee:
                            las diferencias dicen si MSMF piso lo escrito. Su
                            `fps_testigo` incluye calcular brillo y nitidez en
                            cada frame (36-42 a 1280x960 frente a 90 de
                            captura): no es la cadencia de la camara; para esa,
                            --modos.

Al importarse, camaras_uvc apaga la aceleracion HW de MSMF (ver alli); el JSON
guarda en `aceleracion_msmf` lo que vio cv2.

Todo lleva tope de tiempo (--timeout) y libera la camara (principio 9); si el
tope no alcanza para los modos pedidos, la sonda no empieza. Los argumentos van
explicitos (principio 7). Ejemplos:

    python iter4\\sondear_camara.py --source 0 --backend MSMF --controles no ^
        --fps 90 --modos 640x480:MJPG,1280x720:MJPG,1920x1200:MJPG ^
        --segundos 5 --salida "..\\Claude outputs\\camaras\\modos_gs1_msmf.json" ^
        --timeout 300
    python iter4\\sondear_camara.py --source 0 --backend DSHOW --controles probar ^
        --salida "..\\Claude outputs\\camaras\\controles_gs1_dshow.json" --timeout 180
    python iter4\\sondear_camara.py --puertos ^
        --salida "..\\Claude outputs\\camaras\\puertos_cam1_p1.json" --timeout 60
    python iter4\\sondear_camara.py --fijar "exposure_ms=1.953,gain=11" ^
        --puerto "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)" ^
        --salida "..\\Claude outputs\\camaras\\fijar_cam1.json" --timeout 60
    python iter4\\sondear_camara.py --fijar "focus=332" --forzar ^
        --puerto "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(4)" ^
        --salida "..\\Claude outputs\\camaras\\marca_gs2.json" --timeout 60
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

import camaras_uvc   # antes de cv2: apaga la aceleracion HW de MSMF (fase 2b, correccion)
import cv2

import ajustes_camara

# Nombre crudo del control -> propiedad de cv2 (los 12 que mide la sonda).
# Una sola fuente: ajustes_camara.CONTROLES_SONDA (fase 2a).
CONTROLES: dict[str, int] = ajustes_camara.CONTROLES_SONDA

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

# Testigo de que la camara quedo igual: brillo medio, nitidez y FPS antes y despues.
TESTIGO_S = 2.0
TOL_BRILLO = 0.10   # relativa
TOL_FPS = 0.20      # relativa
# La marca en `focus` (plan, fase 2a): el testigo no cambia si brillo y nitidez
# quedan dentro del 2 % y los FPS dentro del 20 %.
TOL_MARCA_BRILLO = 0.02
TOL_MARCA_NITIDEZ = 0.02
TOL_MARCA_FPS = 0.20
CALENTAR_FRAMES = 6
# --tras-msmf: el FPS de su testigo no es el de la camara (sesion del 2026-10-21/22).
NOTA_FPS_TESTIGO = ("fps_testigo = frames leidos por segundo calculando brillo y nitidez "
                    "(Laplaciano CV_64F) en cada frame: captura + proceso, no la cadencia de "
                    "la camara (1280x960: 36-42 frente a 90 de captura); para esa, --modos")


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


def nitidez(imagen) -> float:
    """Varianza del laplaciano (en gris): sube con el enfoque; para la marca de la fase 2a."""
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    return float(cv2.Laplacian(gris, cv2.CV_64F).var())


def testigo(cap, segundos: float) -> dict:
    """Brillo medio, nitidez, FPS y tamano real durante `segundos`: la huella de la camara."""
    medias, nitideces, tamano, t0 = [], [], None, time.monotonic()
    while time.monotonic() - t0 < segundos:
        ok, frame = cap.read()
        if ok and frame is not None:
            medias.append(float(frame.mean()))
            nitideces.append(nitidez(frame))
            tamano = {"ancho": int(frame.shape[1]), "alto": int(frame.shape[0])}
    dt = time.monotonic() - t0
    return {"frames": len(medias),
            "fps": round(len(medias) / dt, 2) if dt > 0 else 0.0,
            "brillo": round(sum(medias) / len(medias), 2) if medias else None,
            "nitidez": round(sum(nitideces) / len(nitideces), 2) if nitideces else None,
            "real": tamano}


def comparar_testigos(antes: dict, despues: dict, tol_brillo: float = TOL_BRILLO,
                      tol_fps: float = TOL_FPS, tol_nitidez: float | None = None) -> list[str]:
    """Diferencias entre dos testigos fuera de tolerancia (relativa); vacia si quedo igual.

    La nitidez solo se compara si se da `tol_nitidez` (los testigos de la fase 1 no la traen).
    """
    claves = [("brillo", tol_brillo), ("fps", tol_fps)]
    if tol_nitidez is not None:
        claves.append(("nitidez", tol_nitidez))
    difs = []
    for clave, tol in claves:
        a, d = antes.get(clave), despues.get(clave)
        if a is None or d is None:
            difs.append(f"{clave}: sin dato (antes {a}, despues {d})")
        elif abs(d - a) > tol * max(abs(a), 1e-9):
            difs.append(f"{clave}: {a:g} -> {d:g} (tolerancia {tol:.0%})")
    return difs


def comparar_marca(antes: dict, despues: dict) -> list[str]:
    """El criterio de la marca en `focus`: brillo y nitidez dentro del 2 %, FPS dentro del 20 %."""
    return comparar_testigos(antes, despues, TOL_MARCA_BRILLO, TOL_MARCA_FPS, TOL_MARCA_NITIDEZ)


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
    try:
        camaras = camaras_uvc.listar_camaras_msmf()
    except OSError as e:
        return {"error": str(e), "camaras": []}
    propia = next((c for c in camaras if c.indice == source), None)
    return {"camaras": [asdict(c) for c in camaras],
            "source": source,
            "esta": asdict(propia) if propia else None}


def _listar(backend: str) -> list:
    return camaras_uvc.listar_camaras_msmf() if backend.upper() == "MSMF" \
        else camaras_uvc.listar_camaras_dshow()


def puertos() -> dict:
    """Las camaras por MSMF y por DSHOW, con indice, instancia, ruta del puerto y ubicacion."""
    salida: dict = {}
    for backend in BACKENDS:
        try:
            salida[backend] = [asdict(c) for c in _listar(backend)]
        except OSError as e:
            salida[backend] = {"error": str(e)}
    return salida


def verificar_orden(backend: str, segundos_por_indice: float = 2.0,
                    filas: list[dict] | None = None) -> list[dict]:
    """Abre por `backend` cada indice que enumera y da el brillo medio del frame.

    `filas` es la lista del `estado` del vigilante: cada fila se anade al tenerla (B25).
    """
    filas = filas if filas is not None else []
    for c in _listar(backend):
        fila = {"indice": c.indice, "nombre": c.nombre, "instancia": c.instancia,
                "ruta_puerto": c.ruta_puerto, "ubicacion": c.ubicacion}
        cap = cv2.VideoCapture(c.indice, _backend_cv2(backend))
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
        print(f"[sonda] {backend} indice {c.indice} [{c.ruta_puerto}]: brillo medio "
              f"{fila.get('brillo_medio')} {fila.get('error', '')}", flush=True)
    return filas


def parsear_fijar(texto: str) -> dict:
    """'exposure_ms=1.953,gain=11,auto_white_balance=false' -> controles del perfil.

    true/false son bool; lo demas, numero. Si hay exposure_ms y no se dio
    exposure_manual, se pone true (es lo que exige validar_controles).
    """
    controls: dict = {}
    for trozo in [t.strip() for t in texto.split(",") if t.strip()]:
        if "=" not in trozo:
            raise ValueError(f"--fijar mal escrito: '{trozo}' (forma: nombre=valor)")
        nombre, valor = (p.strip() for p in trozo.split("=", 1))
        if valor.lower() in ("true", "false"):
            controls[nombre] = valor.lower() == "true"
        else:
            try:
                controls[nombre] = float(valor)
            except ValueError:
                raise ValueError(f"--fijar: '{nombre}' tiene que ser un numero o true/false, no '{valor}'")
    if not controls:
        raise ValueError("--fijar vacio")
    if "exposure_ms" in controls and "exposure_manual" not in controls:
        controls["exposure_manual"] = True
    validos = ajustes_camara.validar_controles(controls)
    ajustes_camara.a_nativos_dshow(validos)   # para aqui si la exposicion no es representable
    return validos


def leer_controles(puerto: str, capa=None) -> dict:
    """Los controles de la camara del puerto por la capa (DSHOW), en unidades del perfil."""
    capa = capa if capa is not None else ajustes_camara.CapaWindowsDShow()
    t0 = time.monotonic()
    leidos = capa.leer(puerto, list(ajustes_camara.CONTROLES_CV2))
    return {"puerto": puerto, "leidos": leidos, "segundos": round(time.monotonic() - t0, 2)}


def fijar(puerto: str, controls: dict, capa=None, forzar: bool = False) -> dict:
    """Aplica `controls` por la capa y los deja puestos; el resultado trae lo leido y lo escrito.

    Con `forzar`, la capa escribe cada control aunque la lectura coincida (y
    relee): para dar de alta la marca, que solo es fiable si se escribio.
    """
    capa = capa if capa is not None else ajustes_camara.CapaWindowsDShow()
    if forzar:
        return capa.aplicar(puerto, controls, forzar=True)
    return capa.aplicar(puerto, controls)


def tras_msmf(puerto: str, modo: tuple[int, int, str], fps: float, segundos: float,
              capa=None, resultado: dict | None = None) -> dict:
    """Lee por DSHOW, abre y captura por MSMF con `modo`, cierra y relee.

    `resultado` es el dict del `estado` del vigilante: se rellena paso a paso
    (antes, msmf, despues, diferencias). Las diferencias (en unidades del
    perfil) dicen si abrir por MSMF piso lo escrito por DSHOW.
    """
    capa = capa if capa is not None else ajustes_camara.CapaWindowsDShow()
    r = resultado if resultado is not None else {}
    nombres = list(ajustes_camara.CONTROLES_CV2)
    r["puerto"] = puerto
    r["antes"] = capa.leer(puerto, nombres)
    print(f"[sonda] DSHOW antes: {r['antes']}", flush=True)
    indice = camaras_uvc.resolver_indice(puerto, camaras_uvc.listar_camaras_msmf())
    w, h, fcc = modo
    msmf: dict = {"indice": indice, "pedido": {"ancho": w, "alto": h, "fourcc": fcc, "fps": fps}}
    r["msmf"] = msmf
    t0 = time.monotonic()
    cap = cv2.VideoCapture(indice, cv2.CAP_MSMF)
    try:
        if not cap.isOpened():
            msmf["error"] = f"no abre el indice MSMF {indice}"
        else:
            msmf["abrir_s"] = round(time.monotonic() - t0, 2)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fcc))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_FPS, fps)
            for _ in range(CALENTAR_FRAMES):
                ok, _f = cap.read()
                if not ok:
                    break
            t = testigo(cap, segundos)
            t["fps_testigo"] = t.pop("fps")
            msmf["testigo"] = t
            msmf["nota_fps"] = NOTA_FPS_TESTIGO
    finally:
        cap.release()
        msmf["total_s"] = round(time.monotonic() - t0, 2)
    print(f"[sonda] MSMF {w}x{h} {fcc}: {msmf.get('testigo')} {msmf.get('error', '')}", flush=True)
    r["despues"] = capa.leer(puerto, nombres)
    r["diferencias"] = ajustes_camara.comparar_controles(r["antes"], r["despues"])
    print(f"[sonda] DSHOW despues: {r['despues']}; diferencias: {r['diferencias'] or 'ninguna'}",
          flush=True)
    return r


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


def _fase_2a(ap, args, estado: dict, salida: Path) -> int:
    """Los modos de la fase 2a: --puertos, --verificar-orden, --leer, --fijar, --tras-msmf.

    Uno por corrida; cada medicion queda en `estado` al tenerla, y el vigilante
    la guarda si salta el tope. 0 si se midio; 1 si algo fallo (el JSON dice que).
    """
    modos = [n for n in ("puertos", "verificar_orden", "leer", "fijar", "tras_msmf") if getattr(args, n)]
    if len(modos) != 1:
        ap.error("uno solo de --puertos, --verificar-orden, --leer, --fijar o --tras-msmf por corrida")
    (modo,) = modos
    if modo == "verificar_orden" and args.backend is None:
        ap.error("--verificar-orden exige --backend MSMF|DSHOW explicito")
    if modo in ("leer", "fijar", "tras_msmf") and not args.puerto:
        ap.error(f"--{modo.replace('_', '-')} exige --puerto (la ruta_puerto que da --puertos)")
    if args.forzar and modo != "fijar":
        ap.error("--forzar solo va con --fijar")
    controls = None
    if modo == "fijar":
        try:
            controls = parsear_fijar(args.fijar)
        except ValueError as e:
            ap.error(str(e))
    modo_msmf = None
    if modo == "tras_msmf":
        if args.modo is None or args.fps is None or args.segundos is None:
            ap.error("--tras-msmf exige --modo, --fps y --segundos")
        try:
            (modo_msmf,) = parsear_modos(args.modo)
        except ValueError as e:
            ap.error(str(e))

    salida.parent.mkdir(parents=True, exist_ok=True)
    estado["opencv"] = cv2.__version__
    estado["aceleracion_msmf"] = dict(camaras_uvc.ACELERACION_MSMF)
    estado["modo"] = modo
    vig = _vigilante(args.timeout, estado, salida)
    rc = 0
    try:
        if modo == "puertos":
            estado["puertos"] = puertos()
            for backend, lista in estado["puertos"].items():
                if isinstance(lista, dict):
                    print(f"[sonda] {backend}: ERROR {lista['error']}")
                    rc = 1
                    continue
                print(f"[sonda] {backend}: {len(lista)} camara(s)")
                for c in lista:
                    print(f"  {c['indice']}: {c['nombre']} [{c['instancia']}] puerto {c['ruta_puerto']} "
                          f"({c['ubicacion']}; usb {c['instancia_usb']})")
        elif modo == "verificar_orden":
            estado["backend"] = args.backend
            estado["verificar_orden"] = []
            verificar_orden(args.backend, filas=estado["verificar_orden"])
            if not estado["verificar_orden"]:
                print(f"[sonda] ERROR: {args.backend} no enumera ninguna camara de video")
                rc = 1
        elif modo == "leer":
            estado["leer"] = leer_controles(args.puerto)
            print(f"[sonda] leidos ({estado['leer']['segundos']} s): {estado['leer']['leidos']}")
        elif modo == "fijar":
            estado["fijar"] = {"puerto": args.puerto, "controls": controls, "forzar": args.forzar}
            try:
                estado["fijar"].update(fijar(args.puerto, controls, forzar=args.forzar))
                print(f"[sonda] fijados{' (forzado)' if args.forzar else ''} en "
                      f"{estado['fijar']['segundos']} s; escritos "
                      f"{estado['fijar']['escritos'] or 'ninguno'}; leidos {estado['fijar']['leidos']}")
            except ajustes_camara.AjustesNoAplicados as e:
                estado["fijar"].update(e.resultado)
                estado["fijar"]["error"] = str(e)
                print(f"[sonda] ERROR: {e}")
                rc = 1
        else:
            print(f"[sonda] {camaras_uvc.describir_aceleracion_msmf()}", flush=True)
            estado["tras_msmf"] = {}
            tras_msmf(args.puerto, modo_msmf, args.fps, args.segundos, resultado=estado["tras_msmf"])
            if estado["tras_msmf"]["diferencias"] or "error" in estado["tras_msmf"]["msmf"]:
                rc = 1
    except (OSError, ValueError, RuntimeError) as e:
        estado["error"] = str(e)
        print(f"[sonda] ERROR: {e}")
        rc = 1
    finally:
        vig.cancel()
    salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sonda] guardado {salida}")
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
                    help="abre cada indice del --backend y da su brillo medio (tapar una lente)")
    ap.add_argument("--puertos", action="store_true",
                    help="enumera MSMF y DSHOW con la ruta del puerto de cada camara")
    ap.add_argument("--puerto", help="ruta del puerto (ruta_puerto de --puertos) para --leer, --fijar y --tras-msmf")
    ap.add_argument("--leer", action="store_true", help="lee los controles por DSHOW (capa de ajustes)")
    ap.add_argument("--fijar", help="controles a aplicar y dejar: 'exposure_ms=1.953,gain=11'")
    ap.add_argument("--forzar", action="store_true",
                    help="con --fijar: escribe cada control pedido aunque la lectura coincida y "
                         "relee (dar de alta la marca: 'focus=332')")
    ap.add_argument("--tras-msmf", action="store_true",
                    help="lee por DSHOW, captura por MSMF (--modo, --fps, --segundos) y relee; "
                         "su fps_testigo incluye calcular brillo y nitidez por frame: no es la "
                         "cadencia de la camara (para esa, --modos)")
    ap.add_argument("--modo", help="un modo 'AnchoxAlto:FOURCC' para --tras-msmf")
    ap.add_argument("--salida", required=True, help="JSON de salida")
    ap.add_argument("--timeout", type=float, required=True, help="tope en segundos")
    args = ap.parse_args(argv)

    salida = Path(args.salida)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv}

    if args.puertos or args.verificar_orden or args.leer or args.fijar or args.tras_msmf:
        return _fase_2a(ap, args, estado, salida)
    if args.forzar:
        ap.error("--forzar solo va con --fijar")

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
        estado["aceleracion_msmf"] = dict(camaras_uvc.ACELERACION_MSMF)
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
