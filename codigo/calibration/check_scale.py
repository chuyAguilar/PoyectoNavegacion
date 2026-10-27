# -*- coding: utf-8 -*-
"""
comprobar_escala.py -- Comprobacion de escala de una calibracion intrinseca con
el tablero desplazado una distancia conocida (meta 002, fase 4).

Por que: el RMS de reproyeccion no ve un error de escala (un --square-mm
equivocado da la misma reproyeccion con una K distinta), asi que la escala se
mide aparte, contra una regla (clarify.md P6: |error| <= 1.0 mm por cada 100 mm).

Como: el tablero va sobre una base rigida que desliza contra una regla; el
autor lo pone en cada desplazamiento (p. ej. 0, 100 y 200 mm) y pulsa ESPACIO;
el script detecta las esquinas (calibrar_camara.detectar_esquinas, el mismo
detector que la calibracion), resuelve la pose del tablero con los intrinsecos
del perfil (solvePnP, SOLVEPNP_IPPE: puntos coplanares, >= 4) sobre
--frames-por-posicion frames y guarda la mediana de la traslacion. Al final,
la distancia que mide la camara entre posiciones menos la de la regla:
  - con posiciones repetidas (la misma lectura de la regla varias veces, p. ej.
    0,80,0,80,0,80; P20, 2026-10-23): el criterio es por MEDIAS. Se agrupan las
    posiciones por lectura, se toma la media de las traslaciones de cada grupo
    y se juzga la distancia entre las medias de lecturas seguidas contra la
    diferencia de la regla (1.0 mm por 100 mm). Cada grupo trae su
    repetibilidad (distancia maxima de una posicion a la media de su grupo):
    mide la colocacion a mano, no la escala de la camara;
  - sin repeticiones (0,100,200): el criterio es por paso, entre posiciones
    seguidas, cada uno con su tolerancia 1.0 mm por 100 mm de paso;
  - los pasos sueltos y los acumulados (cada posicion contra la primera) van
    siempre en la tabla y en el JSON, como informacion.
--desde-json recalcula el criterio sin camara sobre un JSON ya guardado (sus
posiciones medidas) y escribe el resultado en --salida.

Abre la camara SIEMPRE por su perfil, que ya tiene que apuntar al .yml (el
backend comprueba el tamano y entrega K y dist). Este modulo importa
camaras_uvc antes que cv2 (aceleracion HW de MSMF apagada, CONTEXT.md 4.18).
Todo con --timeout (vigilante) y la camara se libera (principio 9).

Context7 (2026-10-22, OpenCV 4.13; instalado 4.11): solvePnP con
SOLVEPNP_IPPE exige puntos coplanares y >= 4; imagePoints contiguos (N,1,2).

La ventana no se congela ni va lenta (meta 004, fase 2c, P11): la vista previa
detecta con el detector rapido sobre el frame reducido a ESCALA_PREVIA
(detectar_previa; solo para pintar) y en otro hilo (PreviaEnHilo: la ventana se
pinta al ritmo de la camara aunque detectar cueste mas, como con Marker0 delante,
sin tablero, el peor caso), y mientras se juntan las poses de una
posicion la ventana se repinta con "Midiendo k de N" y atiende las teclas en
cada frame (`refrescar`: imshow + pollKey; q cancela). La medida no cambia:
mismo detector (--detector), frame completo y mediana. Context7 (2026-10-26,
OpenCV 4.13; instalado 4.11): waitKey y pollKey son las unicas funciones de
HighGUI que atienden los eventos de la ventana; pollKey no espera y da -1 sin
tecla.

Uso (desde codigo\\, con el venv):
    python -m calibration.check_scale --config profiles\\tracker_config_gs1.yaml ^
        --cols 8 --rows 5 --square-mm 24.97 --detector clasico ^
        --desplazamientos-mm 0,100,200 --frames-por-posicion 30 --luz "caja nivel 2" ^
        --salida "..\\Claude outputs\\camaras\\escala_gs1.json" --timeout 600
    python -m calibration.check_scale --desde-json "..\\Claude outputs\\camaras\\escala_gs2.json" ^
        --salida "..\\Claude outputs\\camaras\\escala_gs2.json"
Teclas: ESPACIO = medir esta posicion | q = salir antes
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from camera import uvc as camaras_uvc  # noqa: F401  (antes de cv2: apaga la aceleracion HW de MSMF)
import cv2
import numpy as np

from calibration.calibrate_camera import DETECTORES, construir_objp, detectar_esquinas
from camera.backend import create_backend
import profiles
from diagnostics.probe_camera import _vigilante

TOLERANCIA_MM_POR_100 = 1.0       # P6
VENTANA = "Comprobar escala - ESPACIO posicion, q salir"
SEGUNDOS_POR_POSICION = 15.0      # tope para juntar los frames de una posicion
MARGEN_S = 2.0
ESCALA_PREVIA = 0.5               # la vista previa detecta sobre el frame a la mitad (fase 2c, P11)


def log_info(m): print(f"[INFO] {m}", flush=True)
def log_warn(m): print(f"[WARN] {m}", flush=True)
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr, flush=True)
def log_stats(m): print(f"[STATS] {m}", flush=True)


# ----------------------------------------------------------------------------
# Funciones puras (con prueba)
# ----------------------------------------------------------------------------

def tolerancia_mm(paso_mm: float, por_100: float = TOLERANCIA_MM_POR_100) -> float:
    """1.0 mm por cada 100 mm de paso (P6), proporcional al paso."""
    return abs(float(paso_mm)) / 100.0 * por_100


def errores_escala(tvecs, desplazamientos_mm) -> list[float]:
    """Distancia medida por la camara entre cada posicion y la primera, menos la de la regla.

    tvecs: traslaciones (3,) del tablero en la camara, una por posicion; desplazamientos_mm:
    la lectura de la regla en cada posicion. Devuelve len(tvecs) - 1 errores (mm), con signo
    (positivo = la camara mide mas que la regla).
    """
    t = [np.asarray(v, dtype=np.float64).flatten() for v in tvecs]
    d = [float(x) for x in desplazamientos_mm]
    if len(t) != len(d):
        raise ValueError(f"{len(t)} traslaciones y {len(d)} desplazamientos: tienen que ser los mismos")
    if len(t) < 2:
        raise ValueError("hacen falta al menos 2 posiciones")
    if any(v.shape != (3,) for v in t):
        raise ValueError("cada traslacion tiene que tener 3 componentes")
    return [float(np.linalg.norm(t[i] - t[0]) - abs(d[i] - d[0])) for i in range(1, len(t))]


def errores_pasos(tvecs, desplazamientos_mm) -> list[dict]:
    """Entre posiciones seguidas: paso de la regla, distancia medida, error y si cumple la tolerancia."""
    t = [np.asarray(v, dtype=np.float64).flatten() for v in tvecs]
    d = [float(x) for x in desplazamientos_mm]
    if len(t) != len(d) or len(t) < 2:
        raise ValueError("hacen falta al menos 2 posiciones, con su desplazamiento cada una")
    pasos = []
    for i in range(1, len(t)):
        regla = abs(d[i] - d[i - 1])
        medido = float(np.linalg.norm(t[i] - t[i - 1]))
        err = medido - regla
        tol = tolerancia_mm(regla)
        pasos.append({"de_mm": d[i - 1], "a_mm": d[i], "paso_regla_mm": regla,
                      "paso_medido_mm": round(medido, 3), "error_mm": round(err, 3),
                      "tolerancia_mm": round(tol, 3), "cumple": abs(err) <= tol + 1e-9})
    return pasos


def _clave_lectura(d) -> float:
    """La lectura de la regla con que se agrupa (0 y 0.0 son la misma)."""
    return round(float(d), 6)


def hay_repeticiones(desplazamientos_mm) -> bool:
    """True si alguna lectura de la regla se repite (entonces el criterio es por medias, P20)."""
    claves = [_clave_lectura(d) for d in desplazamientos_mm]
    return len(set(claves)) < len(claves)


def agrupar_por_lectura(tvecs, desplazamientos_mm) -> list[dict]:
    """Un grupo por lectura de la regla, en orden de lectura: las posiciones (indices), la media
    de sus traslaciones y la repetibilidad (distancia maxima de una posicion a la media)."""
    t = [np.asarray(v, dtype=np.float64).flatten() for v in tvecs]
    if len(t) != len(desplazamientos_mm) or len(t) < 2:
        raise ValueError("hacen falta al menos 2 posiciones, con su desplazamiento cada una")
    if any(v.shape != (3,) for v in t):
        raise ValueError("cada traslacion tiene que tener 3 componentes")
    indices: dict[float, list[int]] = {}
    for i, d in enumerate(desplazamientos_mm):
        indices.setdefault(_clave_lectura(d), []).append(i)
    grupos = []
    for lectura in sorted(indices):
        a = np.asarray([t[i] for i in indices[lectura]])
        media = a.mean(axis=0)
        dist = [float(np.linalg.norm(v - media)) for v in a]
        grupos.append({"lectura_mm": lectura, "n": len(dist), "posiciones": indices[lectura],
                       "media_mm": media.round(3).tolist(), "_media": media,
                       "distancias_a_la_media_mm": [round(x, 3) for x in dist],
                       "repetibilidad_mm": round(max(dist), 3)})
    return grupos


def errores_medias(tvecs, desplazamientos_mm) -> tuple[list[dict], list[dict]]:
    """(grupos, comparaciones): entre las medias de lecturas seguidas de la regla, la distancia
    medida, la de la regla, el error y si cumple 1.0 mm por 100 mm (P20)."""
    grupos = agrupar_por_lectura(tvecs, desplazamientos_mm)
    if len(grupos) < 2:
        raise ValueError("hacen falta al menos dos lecturas distintas de la regla")
    comparaciones = []
    for a, b in zip(grupos, grupos[1:]):
        regla = abs(b["lectura_mm"] - a["lectura_mm"])
        medido = float(np.linalg.norm(b["_media"] - a["_media"]))
        err = medido - regla
        tol = tolerancia_mm(regla)
        comparaciones.append({"de_mm": a["lectura_mm"], "a_mm": b["lectura_mm"], "n_de": a["n"], "n_a": b["n"],
                              "paso_regla_mm": regla, "paso_medido_mm": round(medido, 3),
                              "error_mm": round(err, 3), "tolerancia_mm": round(tol, 3),
                              "cumple": abs(err) <= tol + 1e-9})
    for g in grupos:
        del g["_media"]
    return grupos, comparaciones


def juzgar_escala(tvecs, desplazamientos_mm) -> dict:
    """Todo lo que se guarda del juicio: los pasos y los acumulados (informacion), y el criterio
    -- por medias si hay lecturas repetidas, por paso si no (P20) --, con `cumple`, la comparacion
    peor (`peor`, la de mayor |error|) y su error (`error_criterio_mm`)."""
    pasos = errores_pasos(tvecs, desplazamientos_mm)
    r: dict = {"pasos": pasos,
               "errores_acumulados_mm": [round(e, 3) for e in errores_escala(tvecs, desplazamientos_mm)],
               "cumple_por_pasos": all(p["cumple"] for p in pasos)}
    if hay_repeticiones(desplazamientos_mm):
        r["grupos"], r["medias"] = errores_medias(tvecs, desplazamientos_mm)
        r["criterio"] = "medias"
        juzgadas = r["medias"]
    else:
        r["criterio"] = "pasos"
        juzgadas = pasos
    r["cumple"] = all(c["cumple"] for c in juzgadas)
    r["peor"] = max(juzgadas, key=lambda c: abs(c["error_mm"]))
    r["error_criterio_mm"] = r["peor"]["error_mm"]
    return r


def resumir_posicion(tvecs: list[np.ndarray]) -> dict:
    """Mediana y desviacion por eje de las traslaciones de una posicion."""
    if not tvecs:
        raise ValueError("sin poses en esta posicion")
    a = np.asarray([np.asarray(t, dtype=np.float64).flatten() for t in tvecs])
    return {"n": int(a.shape[0]), "mediana_mm": np.median(a, axis=0).round(3).tolist(),
            "sd_mm": a.std(axis=0).round(3).tolist() if a.shape[0] > 1 else [0.0, 0.0, 0.0],
            "distancia_mm": round(float(np.linalg.norm(np.median(a, axis=0))), 2)}


# ----------------------------------------------------------------------------
# Pose del tablero
# ----------------------------------------------------------------------------

def centro_tablero_mm(cols: int, rows: int, square_mm: float) -> np.ndarray:
    """El centro de las esquinas interiores, en el sistema del tablero (mm)."""
    return np.array([(cols - 1) / 2.0 * square_mm, (rows - 1) / 2.0 * square_mm, 0.0])


def pose_tablero(gray, cols: int, rows: int, square_mm: float, K, dist, metodo: str = "clasico"):
    """(rvec, t_centro) del tablero en la camara, o None si no se detecta.

    t_centro es la traslacion del CENTRO de las esquinas interiores, no del origen de objp:
    un tablero 8x5 admite dos ordenes de esquinas (girado 180 grados) y los detectores no
    siempre dan el mismo; el centro es el mismo en los dos, el origen no. rvec queda con
    esa ambiguedad (no se usa para la escala).
    """
    corners = detectar_esquinas(gray, cols, rows, metodo)
    if corners is None:
        return None
    objp = construir_objp(cols, rows, square_mm)
    ok, rvec, tvec = cv2.solvePnP(objp, np.ascontiguousarray(corners, dtype=np.float32).reshape(-1, 1, 2),
                                  np.asarray(K, dtype=np.float64), np.asarray(dist, dtype=np.float64),
                                  flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rvec)
    t_centro = R @ centro_tablero_mm(cols, rows, square_mm) + np.asarray(tvec, dtype=np.float64).flatten()
    return np.asarray(rvec, dtype=np.float64).flatten(), t_centro


def textos_ventana(i: int, total: int, lectura_mm: float, visto: bool) -> tuple[str, str]:
    """Las dos lineas que se pintan sobre la imagen, en lenguaje llano (P21) y sin acentos:
    la fuente de cv2.putText (Hershey) pinta '??' en lugar de una letra con acento."""
    estado = "Tablero: lo veo" if visto else "Tablero: NO lo veo"
    return (f"Posicion {i + 1} de {total}: lleva el tablero a la marca de {lectura_mm:g} mm y pulsa ESPACIO",
            f"{estado}   |   sin girarlo entre una marca y otra   |   q = salir")


def texto_midiendo(i: int, total: int, lectura_mm: float, k: int, n: int, sin_tablero: int = 0) -> str:
    """La linea que se pinta mientras se juntan las poses de una posicion (sin acentos, P21)."""
    falta = f" (sin tablero en {sin_tablero} frames)" if sin_tablero else ""
    return (f"Midiendo posicion {i + 1} de {total} ({lectura_mm:g} mm): {k} de {n} poses{falta}"
            f" - no muevas el tablero | q = salir")


def detectar_previa(gray, cols: int, rows: int, escala: float = ESCALA_PREVIA):
    """Esquinas de la vista previa, en px del frame completo, o None. Solo para pintar: el
    detector rapido (clasico con FAST_CHECK) sobre el frame reducido por `escala` (INTER_AREA),
    y las esquinas llevadas al frame completo. La medida (ESPACIO) no la usa (fase 2c, P11)."""
    if not 0.0 < float(escala) <= 1.0:
        raise ValueError(f"escala de la vista previa fuera de (0, 1]: {escala}")
    if escala == 1.0:
        return detectar_esquinas(gray, cols, rows, "clasico", rapido=True)
    peque = cv2.resize(gray, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    c = detectar_esquinas(peque, cols, rows, "clasico", rapido=True)
    if c is None:
        return None
    return ((c + 0.5) / escala - 0.5).astype(np.float32)    # centro de pixel a centro de pixel


class PreviaEnHilo:
    """La deteccion de la vista previa en otro hilo, para que la ventana se pinte al ritmo de la
    camara aunque detectar cueste mas que un frame (con Marker0 delante, sin tablero, ~75 ms a la
    mitad; fase 2c). `enviar(gray)` deja el frame mas reciente (sin cola: si el hilo esta ocupado,
    el anterior pendiente se descarta); `ultimas()` da las ultimas esquinas que el hilo termino
    (o None) y relanza aqui un error del hilo (principio 7); `cerrar()` para el hilo con tope."""

    def __init__(self, cols: int, rows: int, escala: float = ESCALA_PREVIA, detectar=None):
        if not 0.0 < float(escala) <= 1.0:
            raise ValueError(f"escala de la vista previa fuera de (0, 1]: {escala}")
        self.cols, self.rows, self.escala = cols, rows, float(escala)
        self._detectar = detectar if detectar is not None else detectar_previa
        self._lock = threading.Lock()
        self._evento = threading.Event()
        self._pendiente = None
        self._esquinas = None
        self._error: BaseException | None = None
        self._parar = False
        self.hechas = 0
        self._hilo = threading.Thread(target=self._bucle, name="previa-escala", daemon=True)
        self._hilo.start()

    def enviar(self, gray) -> None:
        with self._lock:
            self._pendiente = gray
            self._evento.set()

    def ultimas(self):
        with self._lock:
            if self._error is not None:
                raise RuntimeError(f"vista previa: {self._error}") from self._error
            return self._esquinas

    def _bucle(self) -> None:
        while True:
            self._evento.wait(0.1)
            with self._lock:
                if self._parar:
                    return
                gray, self._pendiente = self._pendiente, None
                self._evento.clear()
            if gray is None:
                continue
            try:
                c = self._detectar(gray, self.cols, self.rows, self.escala)
            except Exception as e:      # se relanza en el hilo principal (ultimas)
                with self._lock:
                    self._error = e
                return
            with self._lock:
                self._esquinas = c
                self.hechas += 1

    def vivo(self) -> bool:
        return self._hilo.is_alive()

    def cerrar(self, tope_s: float = 2.0) -> None:
        with self._lock:
            self._parar = True
            self._evento.set()
        self._hilo.join(tope_s)


def _refrescar_ventana(img) -> int:
    """Pinta y atiende los eventos de la ventana sin esperar; la tecla (& 0xFF) o 255 sin tecla."""
    cv2.imshow(VENTANA, img)
    return cv2.pollKey() & 0xFF


def medir_posiciones(cam, cols: int, rows: int, square_mm: float, K, dist, metodo: str,
                     desplazamientos_mm: list[float], frames_por_posicion: int, limite: float,
                     leer_tecla=None, segundos_por_posicion: float = SEGUNDOS_POR_POSICION,
                     refrescar=None, escala_previa: float = ESCALA_PREVIA) -> list[dict]:
    """Ventana: por cada desplazamiento, ESPACIO junta hasta frames_por_posicion poses (o
    segundos_por_posicion) y guarda la mediana. q sale antes. `leer_tecla()` se inyecta en las
    pruebas (por defecto cv2.waitKey(1) & 0xFF). La vista previa detecta en otro hilo
    (PreviaEnHilo) y pinta las ultimas esquinas que tiene. Mientras junta las poses,
    `refrescar(img)` pinta "Midiendo k de N" y atiende las teclas en cada frame (por defecto
    imshow + pollKey); si da q, la posicion no se guarda y se sale. Devuelve una fila por
    posicion medida."""
    leer_tecla = leer_tecla if leer_tecla is not None else (lambda: cv2.waitKey(1) & 0xFF)
    refrescar = refrescar if refrescar is not None else _refrescar_ventana
    filas: list[dict] = []
    i = 0
    hilo_previa = PreviaEnHilo(cols, rows, escala_previa)
    try:
        cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
        while i < len(desplazamientos_mm) and time.monotonic() < limite:
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            hilo_previa.enviar(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            previa = hilo_previa.ultimas()
            disp = frame.copy()
            if previa is not None:
                cv2.drawChessboardCorners(disp, (cols, rows), previa, True)
            color = (0, 255, 0) if previa is not None else (0, 0, 255)
            linea1, linea2 = textos_ventana(i, len(desplazamientos_mm), desplazamientos_mm[i], previa is not None)
            cv2.putText(disp, linea1, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(disp, linea2, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow(VENTANA, disp)
            tecla = leer_tecla()
            if tecla == ord("q"):
                break
            if tecla != ord(" "):
                continue
            poses, fallos, cancelada = [], 0, False
            t0 = time.monotonic()
            while (len(poses) < frames_por_posicion and time.monotonic() - t0 < segundos_por_posicion
                   and time.monotonic() < limite):
                frame, _d, _ts = cam.read()
                if frame is None:
                    continue
                p = pose_tablero(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cols, rows, square_mm, K, dist, metodo)
                if p is None:
                    fallos += 1
                else:
                    poses.append(p[1])
                disp = frame.copy()
                cv2.putText(disp, texto_midiendo(i, len(desplazamientos_mm), desplazamientos_mm[i], len(poses),
                                                 frames_por_posicion, fallos), (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 255), 2)
                if refrescar(disp) == ord("q"):
                    cancelada = True
                    break
            if cancelada:
                log_warn(f"posicion {desplazamientos_mm[i]:g} mm: q durante la medida; no se guarda y se sale")
                break
            if not poses:
                log_warn(f"posicion {desplazamientos_mm[i]:g} mm: sin pose en {fallos} frames; vuelve a pulsar ESPACIO")
                continue
            fila = {"desplazamiento_mm": float(desplazamientos_mm[i]), "frames_sin_pose": fallos,
                    "segundos": round(time.monotonic() - t0, 2)}
            fila.update(resumir_posicion(poses))
            filas.append(fila)
            log_info(f"posicion {desplazamientos_mm[i]:g} mm: {fila['n']} poses, mediana {fila['mediana_mm']} mm "
                     f"(sd {fila['sd_mm']}), distancia {fila['distancia_mm']} mm")
            i += 1
    finally:
        hilo_previa.cerrar()
        cv2.destroyAllWindows()
    return filas


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _parsear_lista(texto: str) -> list[float]:
    try:
        v = [float(t) for t in texto.split(",") if t.strip()]
    except ValueError:
        raise ValueError(f"--desplazamientos-mm mal escrito: {texto!r} (forma: 0,100,200)")
    if len(v) < 2:
        raise ValueError("--desplazamientos-mm necesita al menos 2 posiciones")
    if len({_clave_lectura(d) for d in v}) < 2:
        raise ValueError("--desplazamientos-mm necesita al menos dos lecturas distintas de la regla")
    return v


def _guardar(estado: dict, salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def evaluar(estado: dict) -> int:
    """Juzga las posiciones de `estado` (P20), lo anota en `estado`, imprime las tablas y
    devuelve el exit (0 cumple, 1 no). RuntimeError con menos de 2 posiciones."""
    filas = estado.get("posiciones") or []
    if len(filas) < 2:
        raise RuntimeError(f"solo {len(filas)} posiciones medidas: hacen falta al menos 2")
    tv = [f["mediana_mm"] for f in filas]
    ds = [f["desplazamiento_mm"] for f in filas]
    for vieja in ("grupos", "medias"):
        estado.pop(vieja, None)
    estado.update(juzgar_escala(tv, ds))
    estado["tolerancia_mm_por_100"] = TOLERANCIA_MM_POR_100
    print(f"\nPasos entre posiciones seguidas ({'informacion' if estado['criterio'] == 'medias' else 'el criterio'}):")
    print("| de (mm) | a (mm) | paso regla | paso medido | error | tolerancia | cumple |")
    print("|---|---|---|---|---|---|---|")
    for p in estado["pasos"]:
        print(f"| {p['de_mm']:g} | {p['a_mm']:g} | {p['paso_regla_mm']:g} | {p['paso_medido_mm']:.3f} | "
              f"{p['error_mm']:+.3f} | {p['tolerancia_mm']:.2f} | {'si' if p['cumple'] else 'NO'} |")
    log_stats(f"errores acumulados contra la primera posicion: {estado['errores_acumulados_mm']} mm")
    if estado["criterio"] == "medias":
        print("\nPosiciones repetidas, por lectura de la regla (repetibilidad = distancia maxima a la media):")
        print("| lectura (mm) | posiciones | repetibilidad (mm) |")
        print("|---|---|---|")
        for g in estado["grupos"]:
            print(f"| {g['lectura_mm']:g} | {g['n']} | {g['repetibilidad_mm']:.3f} |")
        print("\nEntre las medias (el criterio, P20):")
        print("| de (mm) | a (mm) | regla | medido | error | tolerancia | cumple |")
        print("|---|---|---|---|---|---|---|")
        for m in estado["medias"]:
            print(f"| {m['de_mm']:g} | {m['a_mm']:g} | {m['paso_regla_mm']:g} | {m['paso_medido_mm']:.3f} | "
                  f"{m['error_mm']:+.3f} | {m['tolerancia_mm']:.2f} | {'si' if m['cumple'] else 'NO'} |")
    que = "entre las medias de las posiciones repetidas" if estado["criterio"] == "medias" else "en todos los pasos"
    if estado["cumple"]:
        log_info(f"Escala: cumple (|error| <= {TOLERANCIA_MM_POR_100} mm por 100 mm {que}; "
                 f"error {estado['error_criterio_mm']:+.3f} mm)")
        return 0
    log_warn(f"Escala: NO cumple {que} (error {estado['error_criterio_mm']:+.3f} mm); revisar --square-mm "
             f"(medida del calibrador), la regla y la base")
    return 1


def recalcular_desde_json(entrada: Path, salida: Path) -> int:
    """Sin camara: vuelve a juzgar las posiciones de un JSON guardado con el criterio de hoy y
    escribe el resultado en `salida` (las posiciones, la K y el resto se conservan)."""
    try:
        estado = json.loads(Path(entrada).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log_error(f"no se puede leer {entrada}: {e}")
        return 1
    estado["recalculado"] = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "desde_json": str(entrada),
                             "criterio_antes": estado.get("criterio", "pasos"), "cumple_antes": estado.get("cumple")}
    log_info(f"recalculando sin camara desde {entrada} ({len(estado.get('posiciones') or [])} posiciones)")
    try:
        rc = evaluar(estado)
    except (RuntimeError, ValueError, KeyError) as e:
        log_error(f"{entrada}: {e}")
        return 1
    _guardar(estado, salida)
    log_info(f"guardado {salida}")
    return rc


def main(argv: list[str] | None = None, abrir=None) -> int:
    ap = argparse.ArgumentParser(description="Comprobacion de escala de los intrinsecos con el tablero desplazado contra una regla.")
    ap.add_argument("--config", help="perfil con calibration_file apuntando al .yml que se comprueba")
    ap.add_argument("--cols", type=int, default=8, help="esquinas interiores horizontales")
    ap.add_argument("--rows", type=int, default=5, help="esquinas interiores verticales")
    ap.add_argument("--square-mm", type=float, help="lado de la casilla medido (el mismo que en la calibracion)")
    ap.add_argument("--detector", choices=DETECTORES, help="el detector con que se calibro")
    ap.add_argument("--desplazamientos-mm", help="lecturas de la regla, p. ej. 0,100,200")
    ap.add_argument("--frames-por-posicion", type=int, default=30, help="poses que se juntan por posicion (mediana)")
    ap.add_argument("--luz", help="nivel de la caja de luz y luz de la sala (P7)")
    ap.add_argument("--desde-json", help="sin camara: recalcula el criterio sobre un JSON ya guardado")
    ap.add_argument("--salida", required=True, help="JSON de salida")
    ap.add_argument("--timeout", type=float, help="tope en segundos (con camara)")
    args = ap.parse_args(argv)

    con_camara = ("config", "square_mm", "detector", "desplazamientos_mm", "timeout")
    if args.desde_json:
        sobran = [n for n in con_camara + ("luz",) if getattr(args, n) is not None]
        if sobran:
            ap.error("con --desde-json no se abre la camara: sobran " + ", ".join("--" + n.replace("_", "-") for n in sobran))
        return recalcular_desde_json(Path(args.desde_json), Path(args.salida))
    faltan = [n for n in con_camara if getattr(args, n) is None]
    if faltan:
        ap.error("faltan argumentos explicitos: " + ", ".join("--" + n.replace("_", "-") for n in faltan))

    try:
        desplazamientos = _parsear_lista(args.desplazamientos_mm)
    except ValueError as e:
        ap.error(str(e))
    if args.square_mm <= 0 or args.frames_por_posicion < 1:
        ap.error("--square-mm > 0 y --frames-por-posicion >= 1")

    cfg = profiles.load(args.config)
    cam_cfg = cfg["camera"]
    if not cam_cfg.get("calibration_file"):
        ap.error(f"el perfil {args.config} no tiene calibration_file: calibra primero (calibrar_camara.py) y apunta el perfil")
    salida = Path(args.salida)
    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": sys.argv[1:] if argv is None else argv,
                    "opencv": cv2.__version__, "perfil": args.config, "calibration_file": cam_cfg.get("calibration_file"),
                    "puerto": cam_cfg.get("usb_port_windows"), "detector": args.detector, "square_mm": args.square_mm,
                    "desplazamientos_mm": desplazamientos, "frames_por_posicion": args.frames_por_posicion,
                    "luz": args.luz, "tolerancia_mm_por_100": TOLERANCIA_MM_POR_100, "posiciones": []}
    log_info(f"Config: {args.config} ({cam_cfg.get('calibration_file')}); tablero {args.cols}x{args.rows} @ "
             f"{args.square_mm} mm; detector {args.detector}; regla en {desplazamientos} mm")
    vig = _vigilante(args.timeout, estado, salida)
    rc = 0
    cam = None
    try:
        cam = (abrir or (lambda c: create_backend(c)))(cam_cfg)
        cam.open()
        K, dist = cam.get_intrinsics()
        estado["K"] = np.asarray(K).tolist()
        estado["dist"] = np.asarray(dist).flatten().tolist()
        log_info("ESPACIO = medir la posicion que dice la ventana (tablero quieto sobre la base) | q = salir")
        filas = medir_posiciones(cam, args.cols, args.rows, args.square_mm, K, dist, args.detector,
                                 desplazamientos, args.frames_por_posicion, time.monotonic() + args.timeout - MARGEN_S)
        estado["posiciones"] = filas
        rc = evaluar(estado)
    except (RuntimeError, ValueError, OSError) as e:
        estado["error"] = str(e)
        log_error(str(e))
        rc = 1
    finally:
        vig.cancel()
        if cam is not None:
            cam.close()
        _guardar(estado, salida)
        log_info(f"guardado {salida}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
