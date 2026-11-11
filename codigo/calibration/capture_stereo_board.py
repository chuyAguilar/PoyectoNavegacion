# -*- coding: utf-8 -*-
"""
El asistente de captura del tablero con las dos camaras a la vez (meta 006 · Grafo de
factores optico-inercial, fase 7a · El asistente de captura del tablero; P40 a, P41-P44).

Sustituye a la grabacion por turnos con los dos trackers (`fase-7/correr.ps1`, que se corto
en T04 el 2026-11-10). Abre gs1 y gs2 en UN proceso, por sus perfiles y como el tracker
(`create_backend`: identidad por el puerto USB, marca `focus` y ajustes por COM sin video,
MSMF + MJPG, warmup, intrinsecos del `calibration_file`), con un `FrameGrabber` por camara,
y ensena una ventana con las dos vistas. No usa el tracker ni la cadena (principio 6) y no
calcula nada: escribe las vistas en el formato que ya lee
`python -m calibration.calibrate_extrinsics --desde-vistas`.

Que hace, por vuelta del bucle:
  1. El ultimo frame de cada camara y su vista previa: el tablero (8x5 esquinas) con el
     detector rapido a escala reducida (`--detector-previa`, `--escala-previa`; medido con
     `--medir-desde`), su pose por camara (`pose_tablero`): `z` del centro e inclinacion.
  2. La quietud: en cada camara, cuanto se mueven las esquinas de la vista previa en el
     ultimo segundo (`Quietud`: la mayor distancia de una esquina a su media).
  3. La variedad (P41): frente a cada vista ya tomada, el giro del tablero y lo que se movio
     su centro, medidos en gs1 (no dependen de la camara ni del orden de las esquinas, que el
     detector puede dar empezando por cualquiera de las dos esquinas opuestas).
  4. Cuando las dos ven el tablero entero, llevan `--quieto-s` quietas (<= `--quieto-px`) y
     la vista es distinta (>= `--umbral-deg` o >= `--umbral-mm` frente a todas): la rafaga,
     `--frames-por-vista` frames nuevos de cada camara, alternando, con su hora de captura.
     Se guarda en gris como `<pos>_<cam>[_rN]_frames/frame_0000k.png` y se comprueba en un
     hilo con `calibrate_extrinsics.esquinas_de_posicion` (`sb`, <= `--max-movimiento-px`):
     lo mismo que hara el calculo. Si vale, pitido y la postura siguiente; si no, la carpeta
     queda como intento (el siguiente lleva `_r2`...; nunca se borra ni se pisa), con su
     motivo en la ventana y en `sesion.json`, y no se vuelve a intentar hasta que el tablero
     se mueva.
  5. Termina sola al llegar a `--objetivo` (P42), con `q`, en el tope de la sesion
     (`--timeout`, P43; no hay tope por postura) o si una camara deja de dar frames 5 s.
     `n` salta la postura de la guia, que solo orienta (P44): vale cualquier vista distinta.

Escribe solo en `--salida` (carpeta nueva): las carpetas de frames y `sesion.json` (tras cada
rafaga, a un temporal y `os.replace`): las vistas tomadas y rechazadas con su motivo, sus
medidas por camara, el emparejado por hora, los fps de cada camara y de la ventana por
tramos de 5 s, la variedad lograda y los sha256 de los perfiles y los intrinsecos.

`z_mm` es la z del CENTRO del tablero en la camara (no la de su primera esquina, que es lo
que da `calibrate_extrinsics --solo-comprobar`): no cambia si el detector invierte el orden.

Context7 (2026-11-10; instalado opencv 4.11.0, firmas comprobadas con `__doc__`):
`/websites/opencv`: `pollKey() -> retval` no espera y da -1 sin tecla; `waitKey` y `pollKey`
son las unicas que procesan los eventos de HighGUI y hace falta una ventana creada;
`drawChessboardCorners(image, patternSize, corners, patternWasFound)` pide imagen de color de
8 bits; `findChessboardCorners` con `CALIB_CB_FAST_CHECK` y `findChessboardCornersSB`
(`NORMALIZE_IMAGE`, `EXHAUSTIVE`, `ACCURACY`; borde blanco de una casilla) son los de
`calibrate_camera.detectar_esquinas`, sin cambio. `/python/cpython/v3.11.14`:
`winsound.Beep(frequency, duration)` (37-32767 Hz, ms; bloquea lo que dura, por eso va en un
hilo) y `os.replace` (pisa el destino). La comprobacion de una rafaga va en un
`threading.Thread(daemon=True)`: un detector colgado no impide salir (principio 9).

Uso (desde codigo\\, con el venv; argumentos explicitos, principio 7):
    python -m calibration.capture_stereo_board ^
        --config gs1=profiles\\tracker_config_gs1.yaml gs2=profiles\\tracker_config_gs2.yaml ^
        --cols 8 --rows 5 --square-mm 24.86 ^
        --salida "..\\Claude outputs\\fases\\006\\fase-7\\asistente\\datos\\<fecha>" ^
        --objetivo 20 --minimo 18 --umbral-deg 10 --umbral-mm 40 --quieto-s 1.0 --quieto-px 0.5 ^
        --frames-por-vista 5 --max-movimiento-px 0.3 --detector-previa clasico --escala-previa 0.5 ^
        --reporte "..\\Claude outputs\\fases\\006\\fase-7\\asistente\\asistente.json" --timeout 2700
Sin camara, la medida que fija la vista previa (tiempos, ruido con el tablero quieto):
    python -m calibration.capture_stereo_board --medir-desde "<carpeta de vistas>" ^
        --config gs1=... gs2=... --cols 8 --rows 5 --square-mm 24.86 --timeout 300
Teclas: q = terminar | n = saltar la postura de la guia

Codigo de salida: 0 con >= `--minimo` vistas tomadas; 1 si termino (q o tope) con menos;
2 si no pudo empezar; 4 si una camara dejo de dar frames.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from calibration import calibrate_camera as cc   # antes de cv2: apaga la aceleracion HW de MSMF (CONTEXT 4.18)
from calibration import calibrate_extrinsics as ce
import cv2
import numpy as np

import profiles
from camera.backend import create_backend
from camera.grabber import FrameGrabber
from diagnostics.probe_camera import _vigilante
from fusion.dataset import sha256_file

REF, OTHER = ce.REF, ce.OTHER
TITULO_VENTANA = "Tablero con las dos camaras - q termina, n salta la postura"
UMBRAL_DEG = 10.0              # P41: una vista es distinta si el tablero giro esto...
UMBRAL_MM = 40.0               # ...o su centro se movio esto, frente a cada vista tomada
QUIETO_S = 1.0                 # la puerta de la vista previa: este tiempo...
# ...sin que una esquina se aparte mas que esto de su media. Medido con --medir-desde sobre la sesion
# cortada del 2026-11-10 (44 PNG de 1280x960, `clasico` a escala 0.5): el ruido de la vista previa en
# ventanas de 1 s (3 PNG seguidos) da p95 0.249 px, y el plan pide >= 2 x p95 = 0.498. En la carpeta
# entera (4 s) sale 0.468 porque en T01 el tablero se deslizaba de verdad (0.58 px, igual con `sb`).
QUIETO_PX = 0.5
MIN_MUESTRAS_QUIETO = 8        # vistas previas minimas en ese tiempo (la ventana a >= ~8 Hz)
FRAMES_POR_VISTA = ce.FRAMES_POR_VISTA
MAX_MOVIMIENTO_PX = ce.MAX_MOVIMIENTO_PX     # la comprobacion final, la del calculo
OBJETIVO = 20                  # P42: termina sola al llegar
MINIMO = 18                    # P42: con q, codigo 0 desde aqui
TOPE_COMPROBACION_S = 30.0     # P43: la comprobacion de una rafaga
ESTANCADA_S = 5.0              # P43: una camara sin frames este tiempo para la sesion (codigo 4)
ESPERA_FRAME_S = 0.2           # por vuelta, lo que se espera a un frame nuevo de cada camara
ESPERA_RAFAGA_S = 1.0          # en la rafaga, lo que se espera a cada frame
TRAMO_FPS_S = 5.0              # los fps de camara y de la ventana se anotan por tramos de esto
MAX_FALLOS_LECTURA = 300       # como el tracker (MAX_READ_FAILURES)
DETECTOR_FINAL = "sb"          # el de los intrinsecos y el del calculo
VARIEDAD_ESPERADA = {"inclinacion_min_deg": 10.0, "inclinacion_max_deg": 30.0, "z_recorrido_mm": 60.0}   # P44, en gs1
PREVIA_MAX_MS = 50.0           # criterio de la fase 7a: p95 de la vista previa de las dos camaras, por vuelta
COMPROBAR_MAX_S = 5.0          # criterio de la fase 7a: p95 de comprobar_rafaga (5 + 5 frames)
ALTO_FRANJA = 236

log_info, log_warn, log_error, log_stats = cc.log_info, cc.log_warn, cc.log_error, cc.log_stats


@dataclass(frozen=True)
class Postura:
    """Una postura de la guia. `texto` y `cuna` sin acentos: la fuente Hershey no los pinta."""
    codigo: str
    texto: str
    cuna: str


# Las 20 de `Claude outputs/fases/006/fase-7/guia_posturas.md` para el montaje real: las camaras
# arriba mirando hacia abajo y el tablero sobre la mesa, con cunas de 5-6, 8-9.5 y 11 cm y una
# pila de 8 cm. Las cuatro primeras se rehacen en plano (las de la sesion cortada no se reutilizan).
POSTURAS: tuple[Postura, ...] = (
    Postura("G01", "Plano sobre la mesa, en el CENTRO", "-"),
    Postura("G02", "Plano, ~6 cm a la IZQUIERDA", "-"),
    Postura("G03", "Plano, ~6 cm a la DERECHA", "-"),
    Postura("G04", "Plano, ~6 cm hacia ATRAS", "-"),
    Postura("G05", "Centro; levanta el borde largo de DELANTE", "6 cm"),
    Postura("G06", "Centro; levanta el borde largo de ATRAS", "6 cm"),
    Postura("G07", "Centro; levanta el borde corto IZQUIERDO", "9.5 cm"),
    Postura("G08", "Centro; levanta el borde corto DERECHO", "9.5 cm"),
    Postura("G09", "Plano, sobre la pila (mas cerca de las camaras)", "pila 8 cm"),
    Postura("G10", "Plano, girado ~30 grados sobre la mesa (como una hoja torcida)", "-"),
    Postura("G11", "Plano, girado ~30 grados al otro lado", "-"),
    Postura("G12", "Plano, girado 90 grados (el lado largo hacia ti)", "-"),
    Postura("G13", "~6 cm a la izquierda; levanta el borde corto derecho", "8 cm"),
    Postura("G14", "~6 cm a la derecha; levanta el borde corto izquierdo", "8 cm"),
    Postura("G15", "Sobre la pila; levanta el borde largo de delante", "5 cm (sobre la pila)"),
    Postura("G16", "Sobre la pila; levanta el borde largo de atras", "5 cm (sobre la pila)"),
    Postura("G17", "Girado ~30 grados (como G10); levanta un borde corto", "11 cm"),
    Postura("G18", "Girado 90 grados (como G12); levanta un borde largo", "6 cm"),
    Postura("G19", "~5 cm hacia delante; levanta el borde corto izquierdo", "11 cm"),
    Postura("G20", "~5 cm hacia atras; levanta el borde largo de delante", "7.5 cm"),
)
POSTURA_LIBRE = Postura("libre", "Otra postura DISTINTA: desplazado + cuna, o girado + cuna", "-")
_RZ180 = np.diag([-1.0, -1.0, 1.0])


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

def _centro(cols: int, rows: int, square_mm: float) -> np.ndarray:
    return np.array([(cols - 1) / 2.0 * square_mm, (rows - 1) / 2.0 * square_mm, 0.0, 1.0])


def medidas_tablero(esquinas, objp, K, dist, cols: int, rows: int, square_mm: float) -> dict:
    """La pose del tablero vista por una camara sola: `T` (`T_cam<-tablero`, por `pose_tablero`),
    `centro_mm` (el centro del tablero en la camara), `z_mm` (su z), `inclinacion_deg`
    (`arccos|R33|`, como `detectar_posiciones`) y `rms_pnp_px`."""
    T, rms = ce.pose_tablero(objp, esquinas, K, dist)
    c = (T @ _centro(cols, rows, square_mm))[:3]
    return {"T": T, "z_mm": float(c[2]), "centro_mm": [float(x) for x in c], "rms_pnp_px": float(rms),
            "inclinacion_deg": float(np.degrees(np.arccos(min(1.0, abs(float(T[2, 2]))))))}


def _angulo_deg(R: np.ndarray) -> float:
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))))


def diferencia_vistas(T_a, T_b, cols: int, rows: int, square_mm: float) -> tuple[float, float]:
    """(giro en grados, distancia entre los centros del tablero en mm) entre dos `T_cam<-tablero`
    de la misma camara. El giro es el menor entre el orden directo y el invertido de las esquinas
    (el mismo tablero con el origen en la esquina opuesta); el centro no depende del orden. Las
    dos son del solido rigido: no dependen de la camara que lo mire."""
    Ta, Tb = np.asarray(T_a, dtype=np.float64).reshape(4, 4), np.asarray(T_b, dtype=np.float64).reshape(4, 4)
    R = Ta[:3, :3].T @ Tb[:3, :3]
    c = _centro(cols, rows, square_mm)
    return min(_angulo_deg(R), _angulo_deg(R @ _RZ180)), float(np.linalg.norm((Ta @ c - Tb @ c)[:3]))


def vista_mas_cercana(T, tomadas: list, cols: int, rows: int, square_mm: float, *,
                      escala_deg: float = UMBRAL_DEG, escala_mm: float = UMBRAL_MM) -> tuple[int | None, float, float]:
    """(indice, giro, distancia) de la vista tomada mas parecida a `T`: la de menor
    max(giro / `escala_deg`, distancia / `escala_mm`), que es < 1 solo si es una repeticion.
    (None, inf, inf) si no hay ninguna."""
    mejor, puntos = (None, float("inf"), float("inf")), float("inf")
    for k, Tk in enumerate(tomadas):
        deg, mm = diferencia_vistas(T, Tk, cols, rows, square_mm)
        p = max(deg / escala_deg, mm / escala_mm)
        if p < puntos:
            mejor, puntos = (k, deg, mm), p
    return mejor


def es_distinta(T, tomadas: list, cols: int, rows: int, square_mm: float, umbral_deg: float, umbral_mm: float) -> bool:
    """Distinta si, frente a TODAS las tomadas, el giro >= `umbral_deg` o la distancia >= `umbral_mm` (P41)."""
    _k, deg, mm = vista_mas_cercana(T, tomadas, cols, rows, square_mm, escala_deg=umbral_deg, escala_mm=umbral_mm)
    return bool(deg >= umbral_deg or mm >= umbral_mm)


class Quietud:
    """Cuanto se mueven las esquinas de la vista previa de UNA camara. Cada muestra se pone en el
    orden de la anterior (como `esquinas_de_posicion`); una sin tablero vacia la ventana.
    Quieto: el tramo mas reciente cuyas muestras no se apartan mas de `max_px` de su media dura
    al menos `ventana_s` y tiene `min_muestras`."""

    def __init__(self, ventana_s: float, max_px: float, min_muestras: int, cols: int, rows: int) -> None:
        self.ventana_s, self.max_px, self.min_muestras = float(ventana_s), float(max_px), int(min_muestras)
        self.cols, self.rows = int(cols), int(rows)
        self._t: list[float] = []
        self._c: list[np.ndarray] = []
        self._tramo = (0.0, 0)          # (duracion, muestras) del tramo quieto mas reciente

    def reset(self) -> None:
        self._t, self._c, self._tramo = [], [], (0.0, 0)

    @staticmethod
    def _movimiento(muestras) -> float:
        a = np.asarray(muestras)
        return float(np.max(np.linalg.norm(a - a.mean(axis=0), axis=2)))

    def push(self, t: float, esquinas) -> None:
        if esquinas is None:
            self.reset()
            return
        c = np.asarray(esquinas, dtype=np.float64).reshape(-1, 2)
        if len(c) != self.cols * self.rows:
            raise ValueError(f"{len(c)} esquinas y el tablero tiene {self.cols * self.rows}")
        if self._c:
            c = min((ce.reordenar(c, self.cols, self.rows, o) for o in ce.ORDENES),
                    key=lambda x: float(np.max(np.linalg.norm(x - self._c[-1], axis=1))))
        self._t.append(float(t))
        self._c.append(c)
        while len(self._t) > 1 and self._t[0] < t - 2.0 * self.ventana_s:
            self._t.pop(0)
            self._c.pop(0)
        n = 1
        for k in range(2, len(self._c) + 1):
            if self._movimiento(self._c[-k:]) > self.max_px:
                break
            n = k
        self._tramo = (self._t[-1] - self._t[-n], n)

    def movimiento_px(self, t: float) -> float | None:
        """La mayor distancia de una esquina a su media en la ultima `ventana_s`; None con < 2 muestras."""
        v = [c for ts, c in zip(self._t, self._c) if ts >= t - self.ventana_s]
        return self._movimiento(v) if len(v) >= 2 else None

    def _al_dia(self, t: float) -> bool:
        return bool(self._t) and t - self._t[-1] <= self.ventana_s

    def quieto(self, t: float) -> bool:
        return self._al_dia(t) and self._tramo[0] >= self.ventana_s and self._tramo[1] >= self.min_muestras

    def progreso(self, t: float) -> float:
        """0-1: cuanto del tiempo de quietud lleva el tramo quieto (para la barra)."""
        return min(1.0, self._tramo[0] / self.ventana_s) if self._al_dia(t) else 0.0


def emparejar_por_hora(t_ref: list[float], t_otra: list[float]) -> list[dict]:
    """Por cada frame de la referencia, el de la otra camara mas cercano en hora: `i`, `j`, `dt_ms` (otra - ref)."""
    out = []
    for i, t in enumerate(t_ref if t_otra else []):
        j = min(range(len(t_otra)), key=lambda k: abs(t_otra[k] - t))
        out.append({"i": i, "j": j, "dt_ms": float((t_otra[j] - t) * 1000.0)})
    return out


def siguiente_intento(carpeta, posicion: str, camaras: tuple[str, ...]) -> str:
    """El sufijo libre (`""`, `"_r2"`, `"_r3"`...) para que ningun intento pise a otro;
    `listar_posiciones` se queda con el ultimo que tenga las dos camaras."""
    d = Path(carpeta)
    n = 1
    while True:
        suf = "" if n == 1 else f"_r{n}"
        if not any((d / f"{posicion}_{c}{suf}_frames").exists() for c in camaras):
            return suf
        n += 1


def guardar_rafaga(carpeta, posicion: str, sufijo: str, rafaga: dict[str, list[tuple[np.ndarray, float]]]) -> dict:
    """Escribe la rafaga, en gris, como `<pos>_<cam><sufijo>_frames/frame_0000k.png` (lo que lee
    `--desde-vistas`). No pisa: si una carpeta existe, FileExistsError antes de escribir nada.
    Devuelve `carpetas`, `horas` (de captura, por camara) y `emparejado` (por hora, frente a la primera)."""
    d = Path(carpeta)
    carpetas = {c: d / f"{posicion}_{c}{sufijo}_frames" for c in rafaga}
    for p in carpetas.values():
        if p.exists():
            raise FileExistsError(f"la carpeta de la rafaga ya existe, no se pisa: {p}")
    for c, frames in rafaga.items():
        carpetas[c].mkdir(parents=True)
        for k, (frame, _t) in enumerate(frames):
            gris = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ok, buf = cv2.imencode(".png", gris)
            if not ok:
                raise IOError(f"no se pudo codificar el frame {k} de {c}")
            (carpetas[c] / f"frame_{k:05d}.png").write_bytes(buf.tobytes())
    horas = {c: [float(t) for _f, t in frames] for c, frames in rafaga.items()}
    cams = list(rafaga)
    return {"carpetas": carpetas, "horas": horas,
            "emparejado": emparejar_por_hora(horas[cams[0]], horas[cams[1]]) if len(cams) > 1 else []}


def comprobar_rafaga(carpetas: dict[str, Path], cols: int, rows: int, n_frames: int, max_mov_px: float, *,
                     intr: dict[str, dict] | None = None, square_mm: float | None = None,
                     detector: str = DETECTOR_FINAL) -> dict:
    """`esquinas_de_posicion` en la carpeta de cada camara, exactamente lo que hara el calculo:
    `usable` y, si no, `motivo`; por camara, lo que da `esquinas_de_posicion` y, con `intr` y
    `square_mm`, las `medidas_tablero` (dentro de `camaras[cam]`, con las esquinas)."""
    out: dict = {"usable": True, "motivo": None, "camaras": {}}
    objp = None if square_mm is None else cc.construir_objp(cols, rows, square_mm)
    for cam, d in carpetas.items():
        e = ce.esquinas_de_posicion(d, cols, rows, detector, n_frames, max_mov_px)
        if e["esquinas"] is not None and intr is not None and objp is not None:
            forma = intr[cam].get("shape")
            if forma is not None and e["shape"] is not None and tuple(forma) != tuple(e["shape"]):
                e["motivo"], e["esquinas"] = f"frames de {e['shape']} e intrinsecos de {tuple(forma)}", None
            else:
                e.update(medidas_tablero(e["esquinas"], objp, intr[cam]["K"], intr[cam]["dist"], cols, rows, square_mm))
        if e["esquinas"] is None:
            out["usable"] = False
            out["motivo"] = (out["motivo"] + "; " if out["motivo"] else "") + f"{cam}: {e['motivo']}"
        out["camaras"][cam] = e
    return out


def variedad(tomadas: list[dict], camara: str = REF) -> dict:
    """La variedad lograda en `camara` (P44): inclinacion minima y maxima y recorrido de `z`."""
    m = [t["medidas"][camara] for t in tomadas]
    if not m:
        return {"camara": camara, "n": 0, "cumple": False}
    inc, z = [x["inclinacion_deg"] for x in m], [x["z_mm"] for x in m]
    out = {"camara": camara, "n": len(m), "inclinacion_min_deg": float(min(inc)), "inclinacion_max_deg": float(max(inc)),
           "z_min_mm": float(min(z)), "z_max_mm": float(max(z)), "z_recorrido_mm": float(max(z) - min(z)),
           "esperada": dict(VARIEDAD_ESPERADA)}
    out["cumple"] = bool(out["inclinacion_min_deg"] <= VARIEDAD_ESPERADA["inclinacion_min_deg"]
                         and out["inclinacion_max_deg"] >= VARIEDAD_ESPERADA["inclinacion_max_deg"]
                         and out["z_recorrido_mm"] >= VARIEDAD_ESPERADA["z_recorrido_mm"])
    return out


# ----------------------------------------------------------------------------
# La maquina de estados (sin E/S ni reloj propio)
# ----------------------------------------------------------------------------

class Asistente:
    """Decide cuando capturar. `observar(t, vistas)` devuelve "capturar" cuando las dos camaras ven
    el tablero entero, llevan `quieto_s` quietas y la vista es distinta de las tomadas; si no,
    "nada". Tras "capturar" queda en "comprobando" hasta `aceptar` o `rechazar`. Tras un rechazo
    no vuelve a capturar hasta que el tablero se mueva o deje de verse (`estado` "rechazada").
    `estado`: "sin_tablero", "moviendo", "quieto", "repetida", "comprobando" o "rechazada"."""

    def __init__(self, cols: int, rows: int, square_mm: float, intr: dict[str, dict], umbral_deg: float,
                 umbral_mm: float, quieto_s: float, quieto_px: float, objetivo: int, minimo: int,
                 posturas: tuple[Postura, ...] = POSTURAS, min_muestras: int = MIN_MUESTRAS_QUIETO) -> None:
        if minimo < 1 or objetivo < minimo:
            raise ValueError(f"objetivo ({objetivo}) >= minimo ({minimo}) >= 1")
        self.cols, self.rows, self.square_mm, self.intr = int(cols), int(rows), float(square_mm), intr
        self.umbral_deg, self.umbral_mm = float(umbral_deg), float(umbral_mm)
        self.objetivo, self.minimo, self.posturas = int(objetivo), int(minimo), tuple(posturas)
        self.camaras = tuple(intr)
        self.ref = REF if REF in intr else self.camaras[0]
        self.objp = cc.construir_objp(cols, rows, square_mm)
        self.quietud = {c: Quietud(quieto_s, quieto_px, min_muestras, cols, rows) for c in self.camaras}
        self.estado = "sin_tablero"
        self.tomadas: list[dict] = []           # {"posicion", "T" (en la referencia), "medidas" {camara: ...}}
        self.rechazadas: list[dict] = []        # {"posicion" (con su sufijo), "motivo"}
        self.medidas: dict = {c: None for c in self.camaras}
        self.cercana: tuple = (None, float("inf"), float("inf"))
        self.progreso = 0.0
        self.ultimo_motivo: str | None = None
        self.t: float | None = None
        self.t_ultima_captura: float | None = None
        self._i_postura = 0
        self._pendiente = False
        self._espera_movimiento = False

    @property
    def postura(self) -> Postura:
        return self.posturas[self._i_postura] if self._i_postura < len(self.posturas) else POSTURA_LIBRE

    @property
    def posicion_siguiente(self) -> str:
        return f"T{len(self.tomadas) + 1:02d}"

    @property
    def terminado(self) -> bool:
        return len(self.tomadas) >= self.objetivo

    def observar(self, t: float, vistas: dict) -> str:
        self.t = float(t)
        for c in self.camaras:
            v = vistas.get(c)
            if v is not None and "T" not in v:
                v = {**v, **medidas_tablero(v["esquinas"], self.objp, self.intr[c]["K"], self.intr[c]["dist"],
                                            self.cols, self.rows, self.square_mm)}
            self.medidas[c] = v
            self.quietud[c].push(t, None if v is None else v["esquinas"])
        self.progreso = min(q.progreso(t) for q in self.quietud.values())
        ref = self.medidas[self.ref]
        Ts = [x["T"] for x in self.tomadas]
        self.cercana = (None, float("inf"), float("inf")) if ref is None else \
            vista_mas_cercana(ref["T"], Ts, self.cols, self.rows, self.square_mm,
                              escala_deg=self.umbral_deg, escala_mm=self.umbral_mm)
        if self._pendiente:
            self.estado = "comprobando"
            return "nada"
        if any(m is None for m in self.medidas.values()):
            self.estado, self._espera_movimiento = "sin_tablero", False
            return "nada"
        if not all(q.quieto(t) for q in self.quietud.values()):
            if any((q.movimiento_px(t) or 0.0) > q.max_px for q in self.quietud.values()):
                self._espera_movimiento = False
            self.estado = "rechazada" if self._espera_movimiento else "moviendo"
            return "nada"
        if self._espera_movimiento:
            self.estado = "rechazada"
            return "nada"
        if not es_distinta(ref["T"], Ts, self.cols, self.rows, self.square_mm, self.umbral_deg, self.umbral_mm):
            self.estado = "repetida"
            return "nada"
        self.estado, self._pendiente = "quieto", True
        return "capturar"

    def aceptar(self, posicion: str, medidas: dict) -> None:
        """La rafaga de `posicion` vale: `medidas[camara]` trae al menos `T`, `z_mm` e `inclinacion_deg`."""
        self.tomadas.append({"posicion": posicion, "T": np.asarray(medidas[self.ref]["T"], dtype=np.float64),
                             "medidas": medidas})
        self._pendiente, self._espera_movimiento, self.ultimo_motivo = False, False, None
        self._i_postura += 1
        self.t_ultima_captura = self.t
        self.estado = "repetida"

    def rechazar(self, posicion: str, motivo: str) -> None:
        self.rechazadas.append({"posicion": posicion, "motivo": motivo})
        self._pendiente, self._espera_movimiento, self.ultimo_motivo = False, True, motivo
        self.estado = "rechazada"

    def saltar_postura(self) -> None:
        self._i_postura += 1


# ----------------------------------------------------------------------------
# La ventana
# ----------------------------------------------------------------------------

_TEXTO_ESTADO = {       # texto (sin acentos) y color BGR
    "sin_tablero": ("NO VEO EL TABLERO ENTERO EN LAS DOS CAMARAS", (60, 60, 255)),
    "moviendo": ("ESPERANDO A QUE ESTE QUIETO", (0, 220, 255)),
    "quieto": ("QUIETO: CAPTURANDO, NO LO TOQUES", (80, 255, 80)),
    "comprobando": ("COMPROBANDO LA RAFAGA...", (255, 220, 80)),
    "repetida": ("YA TOMADA: CAMBIA LA POSTURA", (0, 165, 255)),
    "rechazada": ("RECHAZADA: MUEVE EL TABLERO Y VUELVE A DEJARLO", (60, 60, 255)),
}


def _txt(img, texto: str, y: int, color=(255, 255, 255), escala: float = 0.6, grosor: int = 1, x: int = 10) -> None:
    # El texto grueso, sin antialias: con LINE_AA y grosor 2 una linea larga cuesta 1.7 ms (medido), 0.3 sin el.
    cv2.putText(img, texto, (x, y), cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA if grosor == 1 else cv2.LINE_8)


def _num(x, fmt: str = ".1f") -> str:
    return "-" if x is None else format(x, fmt)


def componer_ventana(frames: dict, vistas: dict, asistente: Asistente, fps: dict, restante_s: float,
                     ancho_vista: int = 640) -> np.ndarray:
    """La imagen de la ventana: las dos vistas reducidas lado a lado con las esquinas y, por camara,
    `z` e inclinacion; debajo, una franja con las vistas tomadas, el estado y la barra de quietud,
    la vista mas parecida, la postura siguiente con su cuna, los fps, el tiempo restante y las
    teclas. `fps`: {camara: fps, "ventana": Hz} (None = sin medir aun). Texto sin acentos."""
    a = asistente
    paneles = []
    for cam in a.camaras:
        f = frames.get(cam)
        if f is None:
            panel = np.zeros((ancho_vista * 3 // 4, ancho_vista, 3), dtype=np.uint8)
            _txt(panel, f"{cam}: sin imagen", 28, (60, 60, 255), 0.7, 2)
            paneles.append(panel)
            continue
        esc = ancho_vista / f.shape[1]
        panel = cv2.resize(f, (ancho_vista, int(round(f.shape[0] * esc))), interpolation=cv2.INTER_AREA)
        if panel.ndim == 2:
            panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
        v = vistas.get(cam)
        m = v if (v is None or "z_mm" in v) else a.medidas.get(cam)
        cv2.rectangle(panel, (0, 0), (ancho_vista, 40), (0, 0, 0), -1)        # el texto, sobre fondo oscuro
        if v is not None:
            e = ((np.asarray(v["esquinas"], dtype=np.float64).reshape(-1, 2) + 0.5) * esc - 0.5).astype(np.float32)
            cv2.drawChessboardCorners(panel, (a.cols, a.rows), e.reshape(-1, 1, 2), True)
        if m is not None:
            _txt(panel, f"{cam}   z {m['z_mm']:.0f} mm   inclinacion {m['inclinacion_deg']:.0f} grados", 28, (80, 255, 80), 0.7, 2)
        else:
            _txt(panel, f"{cam}   NO veo el tablero entero", 28, (60, 60, 255), 0.7, 2)
        paneles.append(panel)
    alto = max(p.shape[0] for p in paneles)
    paneles = [p if p.shape[0] == alto else cv2.copyMakeBorder(p, 0, alto - p.shape[0], 0, 0, cv2.BORDER_CONSTANT)
               for p in paneles]
    arriba = np.hstack(paneles)
    ancho = arriba.shape[1]
    franja = np.zeros((ALTO_FRANJA, ancho, 3), dtype=np.uint8)
    texto, color = _TEXTO_ESTADO[a.estado]
    _txt(franja, f"Vistas: {len(a.tomadas)} de {a.objetivo} (minimo {a.minimo})", 34, (255, 255, 255), 0.9, 2)
    _txt(franja, texto, 34, color, 0.8, 2, x=520)
    cv2.rectangle(franja, (10, 48), (ancho - 10, 62), (90, 90, 90), 1)
    cv2.rectangle(franja, (10, 48), (10 + int((ancho - 20) * max(0.0, min(1.0, a.progreso))), 62), color, -1)
    k, deg, mm = a.cercana
    if k is None:
        cerca = "La mas parecida: -" if a.tomadas else "Aun no hay ninguna vista tomada: la primera vale en cuanto este quieta"
    else:
        cerca = (f"La mas parecida: {a.tomadas[k]['posicion']}, a {deg:.0f} grados y {mm:.0f} mm "
                 f"(distinta desde {a.umbral_deg:g} grados o {a.umbral_mm:g} mm)")
    _txt(franja, cerca, 88)
    p = a.postura
    _txt(franja, f"Siguiente ({p.codigo}): {p.texto}   |   cuna: {p.cuna}", 116, (255, 255, 160), 0.65, 2)
    if a.ultimo_motivo and a.rechazadas:
        _txt(franja, f"Rechazada {a.rechazadas[-1]['posicion']}: {a.ultimo_motivo}"[:125], 144, (60, 60, 255), 0.55)
    r = max(0, int(restante_s))
    desde = None if (a.t is None or a.t_ultima_captura is None) else (a.t - a.t_ultima_captura) / 60.0
    _txt(franja, "   |   ".join([f"{c} {_num(fps.get(c))} fps" for c in a.camaras] + [
        f"ventana {_num(fps.get('ventana'))} Hz", f"quedan {r // 60}:{r % 60:02d}",
        f"ultima captura hace {_num(desde)} min"]), 176, (200, 200, 200), 0.55)
    _txt(franja, f"q = terminar (vale desde {a.minimo} vistas)      n = saltar la postura de la guia", 210, (200, 200, 200), 0.55)
    return np.vstack([arriba, franja])


# ----------------------------------------------------------------------------
# El bucle
# ----------------------------------------------------------------------------

class _Tramos:
    """Un ritmo (fps, Hz) por tramos de `periodo` s a partir de un contador que crece."""

    def __init__(self, t0: float, periodo: float = TRAMO_FPS_S) -> None:
        self.t0, self.c0, self.periodo = float(t0), 0, float(periodo)
        self.tramos: list[float] = []

    def medir(self, t: float, contador: int) -> None:
        if t - self.t0 >= self.periodo:
            self.tramos.append(round((contador - self.c0) / (t - self.t0), 2))
            self.t0, self.c0 = float(t), int(contador)

    @property
    def ultimo(self) -> float | None:
        return self.tramos[-1] if self.tramos else None

    def resumen(self) -> dict:
        v = self.tramos
        return {"tramos": len(v), "mediana": float(np.median(v)) if v else None, "min": float(min(v)) if v else None}


def vista_previa(frame, cols: int, rows: int, objp, K, dist, square_mm: float, detector: str, escala: float) -> dict | None:
    """El tablero en un frame, rapido: detecta a `escala` (`detectar_esquinas(..., rapido=True)`),
    lleva las esquinas al tamano real y calcula `medidas_tablero`. None si no se ve entero."""
    gris = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    g = gris if escala == 1.0 else cv2.resize(gris, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    c = cc.detectar_esquinas(g, cols, rows, detector, rapido=True)
    if c is None:
        return None
    e = c.reshape(-1, 2).astype(np.float64)
    if escala != 1.0:
        e = (e + 0.5) / escala - 0.5
    try:
        return {"esquinas": e, **medidas_tablero(e, objp, K, dist, cols, rows, square_mm)}
    except (RuntimeError, cv2.error):
        return None


def _escribir_json(ruta: Path, datos: dict) -> None:
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(json.dumps(ce._jsonable(datos), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ruta)


def _sin_esquinas(e: dict) -> dict:
    return {k: v for k, v in e.items() if k != "esquinas"}


def capturar_sesion(fuentes: dict, intr: dict[str, dict], asistente: Asistente, carpeta, limite: float,
                    n_frames: int, max_mov_px: float, clock=time.perf_counter, leer_tecla=None, mostrar=None,
                    pitido=None, detector_previa: str = "clasico", escala_previa: float = 0.5,
                    meta: dict | None = None) -> dict:
    """El bucle de la sesion. `fuentes[c]` tiene la interfaz de `FrameGrabber` (`next_frame(timeout)`,
    `failed`, `frames_read`). Sale con `asistente.terminado`, `q`, `limite` (en el reloj `clock`) o una
    camara sin frames `ESTANCADA_S`. Escribe `sesion.json` en `carpeta` tras cada rafaga y al salir.
    Devuelve `codigo` (0 con >= minimo; 1 con menos; 4 camara estancada), `fin`, `tomadas`, `rechazadas`,
    `variedad`, `fps`, `hz_ventana`, `dt_max_ms`, `sesion`. `mostrar(img)`, `leer_tecla()` y
    `pitido(tipo)` se inyectan en las pruebas; por defecto, la ventana de cv2 y `pollKey`."""
    a = asistente
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    camaras = tuple(fuentes)
    if mostrar is None:
        cv2.namedWindow(TITULO_VENTANA, cv2.WINDOW_NORMAL)
        mostrar = lambda img: cv2.imshow(TITULO_VENTANA, img)      # noqa: E731
    leer_tecla = leer_tecla if leer_tecla is not None else (lambda: cv2.pollKey() & 0xFF)
    pitido = pitido if pitido is not None else (lambda tipo: None)
    t0 = clock()
    ultimo: dict = {c: None for c in camaras}
    t_frame = {c: t0 for c in camaras}
    ritmo = {c: _Tramos(t0) for c in camaras}
    ritmo_ventana, vueltas = _Tramos(t0), 0
    sesion = carpeta / "sesion.json"
    reg: dict = {"version": 1, "meta": meta or {}, "estado": "en curso", "fin": None, "codigo": None,
                 "tablero": {"cols": a.cols, "rows": a.rows, "square_mm": a.square_mm},
                 "parametros": {"umbral_deg": a.umbral_deg, "umbral_mm": a.umbral_mm, "objetivo": a.objetivo,
                                "minimo": a.minimo, "quieto_s": a.quietud[a.ref].ventana_s,
                                "quieto_px": a.quietud[a.ref].max_px, "frames_por_vista": int(n_frames),
                                "max_movimiento_px": float(max_mov_px), "detector_previa": detector_previa,
                                "escala_previa": float(escala_previa), "detector_final": DETECTOR_FINAL},
                 "tomadas": [], "rechazadas": []}

    def volcar() -> None:
        reg["fps"] = {c: list(ritmo[c].tramos) for c in camaras}
        reg["hz_ventana"] = list(ritmo_ventana.tramos)
        reg["variedad"] = variedad(a.tomadas, a.ref)
        _escribir_json(sesion, reg)

    def rechazar(pos: str, suf: str, motivo: str, extra: dict | None = None) -> None:
        a.rechazar(pos + suf, motivo)
        reg["rechazadas"].append({"posicion": pos, "sufijo": suf, "motivo": motivo, "t_s": clock() - t0, **(extra or {})})
        log_warn(f"{pos}{suf} RECHAZADA: {motivo}")
        pitido("rechazada")
        volcar()

    def resolver(p: dict) -> None:
        r, pos, suf = p["resultado"], p["posicion"], p["sufijo"]
        if "error" in r or "comprobacion" not in r:
            rechazar(pos, suf, r.get("error", "la comprobacion no dio resultado"))
            return
        g, comp = r["guardado"], r["comprobacion"]
        fila = {"carpetas": {c: d.name for c, d in g["carpetas"].items()}, "horas": g["horas"], "emparejado": g["emparejado"],
                "dt_max_ms": max((abs(x["dt_ms"]) for x in g["emparejado"]), default=None),
                "camaras": {c: _sin_esquinas(e) for c, e in comp["camaras"].items()},
                "postura_guia": p["postura"], "comprobacion_s": r.get("segundos")}
        if not comp["usable"]:
            rechazar(pos, suf, comp["motivo"], fila)
            return
        a.aceptar(pos, {c: _sin_esquinas(e) for c, e in comp["camaras"].items()})
        reg["tomadas"].append({"posicion": pos, "sufijo": suf, "t_s": clock() - t0, **fila})
        m = comp["camaras"][a.ref]
        log_info(f"{pos}{suf} tomada ({len(a.tomadas)} de {a.objetivo}): {a.ref} z {m['z_mm']:.0f} mm, inclinacion "
                 f"{m['inclinacion_deg']:.0f} grados; dt max {_num(fila['dt_max_ms'], '.2f')} ms; "
                 f"comprobada en {_num(fila['comprobacion_s'])} s")
        pitido("tomada")
        volcar()

    def lanzar(pos: str, suf: str, rafaga: dict) -> dict:
        p = {"posicion": pos, "sufijo": suf, "postura": a.postura.codigo, "t0": clock(), "resultado": {}}

        def trabajo() -> None:
            t_ini = time.perf_counter()
            try:
                p["resultado"]["guardado"] = guardar_rafaga(carpeta, pos, suf, rafaga)
                p["resultado"]["comprobacion"] = comprobar_rafaga(
                    p["resultado"]["guardado"]["carpetas"], a.cols, a.rows, n_frames, max_mov_px,
                    intr=intr, square_mm=a.square_mm)
            except Exception as e:  # noqa: BLE001  (va al motivo del rechazo, en el hilo del bucle)
                p["resultado"]["error"] = f"{type(e).__name__}: {e}"
            p["resultado"]["segundos"] = time.perf_counter() - t_ini

        p["hilo"] = threading.Thread(target=trabajo, name="comprobar-rafaga", daemon=True)
        p["hilo"].start()
        return p

    objp = a.objp
    pendiente, fin, camara_mala, error_camara = None, None, None, None
    try:
        while fin is None:
            t = clock()
            if pendiente is None and a.terminado:
                fin = "objetivo"
                break
            if t >= limite:
                fin = "tope"
                break
            vistas: dict = {}
            for c in camaras:
                try:
                    got = fuentes[c].next_frame(ESPERA_FRAME_S)
                except Exception as e:  # noqa: BLE001  (un error del backend en el hilo de captura)
                    got, camara_mala, error_camara = None, c, f"{type(e).__name__}: {e}"
                if got is not None:
                    ultimo[c], t_frame[c] = got[0], clock()
                    vistas[c] = vista_previa(got[0], a.cols, a.rows, objp, intr[c]["K"], intr[c]["dist"], a.square_mm,
                                             detector_previa, escala_previa)
                else:
                    vistas[c] = None
                    if getattr(fuentes[c], "failed", False) or clock() - t_frame[c] >= ESTANCADA_S:
                        camara_mala = camara_mala or c
            if camara_mala is not None:
                fin = "camara_estancada"
                break
            t = clock()
            if a.observar(t, vistas) == "capturar":
                pos = a.posicion_siguiente
                suf = siguiente_intento(carpeta, pos, camaras)
                rafaga: dict = {c: [] for c in camaras}
                falta = None
                for _k in range(int(n_frames)):
                    for c in camaras:
                        got = None if falta else fuentes[c].next_frame(ESPERA_RAFAGA_S)
                        if got is None:
                            falta = falta or c
                        else:
                            rafaga[c].append((got[0], float(got[1])))
                            ultimo[c], t_frame[c] = got[0], clock()
                if falta:
                    rechazar(pos, suf, f"rafaga incompleta: {falta} no dio un frame nuevo en {ESPERA_RAFAGA_S:g} s (no se guardo)")
                else:
                    pendiente = lanzar(pos, suf, rafaga)
            if pendiente is not None:
                if not pendiente["hilo"].is_alive():
                    resolver(pendiente)
                    pendiente = None
                elif clock() - pendiente["t0"] > TOPE_COMPROBACION_S:
                    rechazar(pendiente["posicion"], pendiente["sufijo"],
                             f"la comprobacion paso de {TOPE_COMPROBACION_S:g} s (la carpeta queda como intento)")
                    pendiente = None
            t = clock()
            vueltas += 1
            for c in camaras:
                ritmo[c].medir(t, int(getattr(fuentes[c], "frames_read", 0)))
            ritmo_ventana.medir(t, vueltas)
            fps = {**{c: ritmo[c].ultimo for c in camaras}, "ventana": ritmo_ventana.ultimo}
            mostrar(componer_ventana(ultimo, vistas, a, fps, limite - t))
            tecla = leer_tecla()
            if tecla == ord("q"):
                fin = "q"
            elif tecla == ord("n"):
                a.saltar_postura()
    except KeyboardInterrupt:
        fin = "interrumpida"
    if pendiente is not None:               # la ultima rafaga cuenta si su comprobacion acaba en su tope
        pendiente["hilo"].join(TOPE_COMPROBACION_S)
        if pendiente["hilo"].is_alive():
            rechazar(pendiente["posicion"], pendiente["sufijo"], f"la comprobacion paso de {TOPE_COMPROBACION_S:g} s al terminar")
        else:
            resolver(pendiente)
    codigo = 4 if fin == "camara_estancada" else (0 if len(a.tomadas) >= a.minimo else 1)
    reg.update({"estado": "terminada", "fin": fin, "codigo": codigo, "duracion_s": clock() - t0})
    if camara_mala is not None:
        reg["camara_estancada"] = {"camara": camara_mala, "error": error_camara}
    volcar()
    dts = [x["dt_max_ms"] for x in reg["tomadas"] if x["dt_max_ms"] is not None]
    return {"codigo": codigo, "fin": fin, "camara": camara_mala, "error_camara": error_camara,
            "tomadas": len(a.tomadas), "rechazadas": len(a.rechazadas),
            "posiciones": [x["posicion"] + x["sufijo"] for x in reg["tomadas"]],
            "variedad": reg["variedad"], "fps": {c: ritmo[c].resumen() for c in camaras},
            "hz_ventana": ritmo_ventana.resumen(), "dt_max_ms": max(dts) if dts else None,
            "duracion_s": reg["duracion_s"], "sesion": str(sesion)}


# ----------------------------------------------------------------------------
# La medida sin camara (fija la vista previa)
# ----------------------------------------------------------------------------

def _p(v: list[float]) -> dict:
    return {"mediana": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(max(v))} if v else {}


def medir_desde_vistas(carpeta, intr: dict[str, dict], cols: int, rows: int, square_mm: float, *,
                       ventana_frames: int = 3, repeticiones: int = 3) -> dict:
    """Sin camara, sobre frames ya grabados (`<pos>_<cam>_frames`, el tablero quieto): por cada opcion
    de vista previa (`clasico` y `sb` rapidos, a escala 1 y 0.5), si ve el tablero; el tiempo por
    frame, el de la vista previa de las dos camaras (`ms_previa`, el del criterio) y el de la vuelta
    entera (`ms_vuelta`: mas `observar` y `componer_ventana`, sin `imshow`), sobre `repeticiones`
    pasadas; y el ruido de sus esquinas con `Quietud.movimiento_px`: en ventanas de `ventana_frames`
    frames seguidos (`ruido_px`; en la sesion del 2026-11-10 hay un PNG cada 45 frames, asi que 3 son
    el segundo de `QUIETO_S`) y en la carpeta entera (`ruido_carpeta_px`, 4 s: incluye lo que el
    tablero se mueva de verdad). Ademas, el tiempo de `comprobar_rafaga`. `recomendada`: la opcion
    mas rapida que ve el tablero en todos los frames; `quieto_px_minimo`: 2 x el p95 de su `ruido_px`."""
    posiciones = {p: i for p, i in ce.listar_posiciones(carpeta, (REF, OTHER)).items() if len(i["carpetas"]) == 2}
    if not posiciones:
        raise ValueError(f"no hay ninguna posicion con las dos camaras (<pos>_<cam>_frames) en {carpeta}")
    objp = cc.construir_objp(cols, rows, square_mm)
    imgs = {}
    for pos, info in posiciones.items():
        for cam, d in info["carpetas"].items():
            imgs[(pos, cam)] = [cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) for f in sorted(d.glob("frame_*.png"))]
            if not imgs[(pos, cam)] or any(g is None for g in imgs[(pos, cam)]):
                raise ValueError(f"no se pudieron leer los frames de {d}")
    n_total = sum(len(v) for v in imgs.values())

    def ruido_de(esquinas: list, n: int | None) -> list[float]:
        """`movimiento_px` de cada ventana de `n` muestras seguidas (None: todas en una)."""
        n = len(esquinas) if n is None else n
        out = []
        for i in range(0, max(0, len(esquinas) - n) + 1):
            q = Quietud(1e9, 1e9, 2, cols, rows)
            for k, e in enumerate(esquinas[i:i + n]):
                q.push(float(k), e)
            m = q.movimiento_px(1e9)
            if m is not None:
                out.append(m)
        return out

    opciones = []
    for detector in cc.DETECTORES:
        for escala in (1.0, 0.5):
            primera = next(iter(imgs.values()))[0]
            vista_previa(primera, cols, rows, objp, intr[REF]["K"], intr[REF]["dist"], square_mm, detector, escala)   # calienta
            ms_frame, ms_previa, ms_vuelta, vistos = [], [], [], 0
            esquinas: dict = {clave: [] for clave in imgs}
            for rep in range(int(repeticiones)):
                for pos in posiciones:
                    a = Asistente(cols, rows, square_mm, intr, UMBRAL_DEG, UMBRAL_MM, QUIETO_S, QUIETO_PX, OBJETIVO, MINIMO)
                    for k in range(max(len(imgs[(pos, c)]) for c in (REF, OTHER))):
                        t_v, vistas, frames = 0.0, {}, {}
                        for c in (REF, OTHER):
                            if k >= len(imgs[(pos, c)]):
                                continue
                            frames[c] = imgs[(pos, c)][k]
                            t1 = time.perf_counter()
                            vistas[c] = vista_previa(frames[c], cols, rows, objp, intr[c]["K"], intr[c]["dist"], square_mm, detector, escala)
                            dt = (time.perf_counter() - t1) * 1000.0
                            ms_frame.append(dt)
                            t_v += dt
                            if rep == 0:
                                vistos += vistas[c] is not None
                                if vistas[c] is not None:
                                    esquinas[(pos, c)].append(vistas[c]["esquinas"])
                        if len(frames) == 2:
                            t1 = time.perf_counter()
                            a.observar(k * 0.1, vistas)
                            componer_ventana(frames, vistas, a, {}, 0.0)
                            ms_previa.append(t_v)
                            ms_vuelta.append(t_v + (time.perf_counter() - t1) * 1000.0)
            ventanas = [m for e in esquinas.values() for m in ruido_de(e, ventana_frames)]
            carpetas = {f"{pos}_{c}": (ruido_de(e, None) or [None])[0] for (pos, c), e in esquinas.items()}
            opciones.append({"detector": detector, "escala": escala, "frames": n_total, "detectados": int(vistos),
                             "ms_frame": _p(ms_frame), "ms_previa": _p(ms_previa), "ms_vuelta": _p(ms_vuelta),
                             "ruido_px": {"ventana_frames": int(ventana_frames), "n": len(ventanas), **_p(ventanas)},
                             "ruido_carpeta_px": {"por_carpeta": carpetas, **_p([x for x in carpetas.values() if x is not None])}})
    t_comp, usables = [], 0
    for pos, info in posiciones.items():
        t1 = time.perf_counter()
        c = comprobar_rafaga(info["carpetas"], cols, rows, FRAMES_POR_VISTA, MAX_MOVIMIENTO_PX, intr=intr, square_mm=square_mm)
        t_comp.append(time.perf_counter() - t1)
        usables += c["usable"]
    validas = [o for o in opciones if o["detectados"] == o["frames"] and o["ms_previa"]]
    rec = min(validas, key=lambda o: o["ms_previa"]["p95"]) if validas else None
    out = {"carpeta": str(carpeta), "posiciones": list(posiciones), "frames": n_total, "repeticiones": int(repeticiones),
           "opciones": opciones, "comprobar_rafaga_s": {**_p(t_comp), "usables": int(usables), "n": len(t_comp)},
           "recomendada": None if rec is None else {"detector": rec["detector"], "escala": rec["escala"]},
           "quieto_px_minimo": None if rec is None or "p95" not in rec["ruido_px"] else 2.0 * rec["ruido_px"]["p95"],
           "criterio": {"previa_p95_ms": PREVIA_MAX_MS, "comprobar_p95_s": COMPROBAR_MAX_S}}
    out["cumple_previa"] = bool(rec is not None and rec["ms_previa"]["p95"] <= PREVIA_MAX_MS)
    out["cumple_comprobar"] = bool(t_comp and out["comprobar_rafaga_s"]["p95"] <= COMPROBAR_MAX_S)
    return out


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def _pitido(tipo: str) -> None:
    """Un pitido corto en un hilo (`winsound.Beep` bloquea lo que dura): agudo si la vista se tomo, grave si no."""
    def sonar() -> None:
        try:
            import winsound
            winsound.Beep(*((880, 150) if tipo == "tomada" else (330, 400)))
        except (ImportError, RuntimeError):
            print("\a", end="", flush=True)
    threading.Thread(target=sonar, name="pitido", daemon=True).start()


def _comando_calculo(salida: Path, cals: dict[str, str], args) -> str:
    return (f'python -m calibration.calibrate_extrinsics --desde-vistas "{salida}" --intrinsecos '
            + " ".join(f'{c}="{cals[c]}"' for c in (REF, OTHER))
            + f" --cols {args.cols} --rows {args.rows} --square-mm {args.square_mm:g} --detector {DETECTOR_FINAL} "
              f"--frames-por-vista {args.frames_por_vista} --max-movimiento-px {args.max_movimiento_px:g} --min-vistas 15 "
              f"--n-control 3 --semilla 0 --montaje <pinzas|estructura> --reporte <json> --timeout 600")


def _log_medida(m: dict) -> None:
    for o in m["opciones"]:
        log_stats(f"vista previa {o['detector']} x{o['escala']:g}: ve el tablero en {o['detectados']} de {o['frames']} frames; "
                  f"por frame {_num(o['ms_frame'].get('mediana'))} ms (p95 {_num(o['ms_frame'].get('p95'))}); las dos camaras "
                  f"{_num(o['ms_previa'].get('mediana'))} ms (p95 {_num(o['ms_previa'].get('p95'))}, max {_num(o['ms_previa'].get('max'))}); "
                  f"la vuelta entera {_num(o['ms_vuelta'].get('mediana'))} ms (p95 {_num(o['ms_vuelta'].get('p95'))}); ruido en ventanas de "
                  f"{o['ruido_px']['ventana_frames']} frames p95 {_num(o['ruido_px'].get('p95'), '.3f')} px (max {_num(o['ruido_px'].get('max'), '.3f')}); "
                  f"en la carpeta entera p95 {_num(o['ruido_carpeta_px'].get('p95'), '.3f')} px")
    c = m["comprobar_rafaga_s"]
    log_stats(f"comprobar_rafaga ({FRAMES_POR_VISTA} + {FRAMES_POR_VISTA} frames, {DETECTOR_FINAL}): mediana {_num(c.get('mediana'), '.2f')} s, "
              f"p95 {_num(c.get('p95'), '.2f')} s, usables {c['usables']} de {c['n']} (criterio <= {COMPROBAR_MAX_S:g} s)")
    if m["recomendada"] is None:
        log_warn("ninguna opcion de vista previa ve el tablero en todos los frames")
    else:
        log_stats(f"recomendada: --detector-previa {m['recomendada']['detector']} --escala-previa {m['recomendada']['escala']:g} "
                  f"(las dos camaras, p95 <= {PREVIA_MAX_MS:g} ms: {'cumple' if m['cumple_previa'] else 'NO cumple'}); "
                  f"QUIETO_PX >= {_num(m['quieto_px_minimo'], '.3f')} px (2 x el p95 del ruido en ventanas)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Asistente de captura del tablero con las dos camaras a la vez (para calibrate_extrinsics --desde-vistas).")
    ap.add_argument("--config", required=True, nargs="+", type=ce._cam_path, metavar="CAM=PERFIL",
                    help="gs1=<perfil> gs2=<perfil>: los intrinsecos salen del calibration_file de cada perfil")
    ap.add_argument("--cols", type=int, required=True, help="esquinas interiores horizontales (9x6 casillas = 8)")
    ap.add_argument("--rows", type=int, required=True, help="esquinas interiores verticales (9x6 casillas = 5)")
    ap.add_argument("--square-mm", type=float, required=True, help="lado de la casilla medido (data/tablero_calibracion.yaml: 24.86)")
    ap.add_argument("--salida", type=Path, help="carpeta nueva para las vistas y sesion.json (si existe y no esta vacia, codigo 2)")
    ap.add_argument("--medir-desde", type=Path, help="sin camara: mide la vista previa sobre una carpeta de vistas ya grabadas")
    ap.add_argument("--objetivo", type=int, default=OBJETIVO, help="vistas con las que termina sola (P42)")
    ap.add_argument("--minimo", type=int, default=MINIMO, help="vistas desde las que la salida es 0 (P42)")
    ap.add_argument("--umbral-deg", type=float, default=UMBRAL_DEG, help="giro que hace distinta una vista (P41)")
    ap.add_argument("--umbral-mm", type=float, default=UMBRAL_MM, help="desplazamiento del centro que hace distinta una vista (P41)")
    ap.add_argument("--quieto-s", type=float, default=QUIETO_S, help="tiempo que el tablero tiene que llevar quieto")
    ap.add_argument("--quieto-px", type=float, default=QUIETO_PX, help="movimiento maximo de la vista previa en ese tiempo")
    ap.add_argument("--frames-por-vista", type=int, default=FRAMES_POR_VISTA, help="frames de cada camara en la rafaga")
    ap.add_argument("--max-movimiento-px", type=float, default=MAX_MOVIMIENTO_PX, help="el tope de la comprobacion final (el del calculo)")
    ap.add_argument("--detector-previa", choices=cc.DETECTORES, default="clasico", help="detector de la vista previa (medido con --medir-desde)")
    ap.add_argument("--escala-previa", type=float, default=0.5, help="escala a la que detecta la vista previa")
    ap.add_argument("--sin-pitido", action="store_true", help="ningun pitido al tomar o rechazar una vista")
    ap.add_argument("--reporte", type=Path, help="JSON con el resumen (o con la medida de --medir-desde)")
    ap.add_argument("--timeout", type=float, required=True, help="tope de la sesion en segundos (principio 9; el vigilante, 60 s despues)")
    args = ap.parse_args(argv)

    if args.cols < 2 or args.rows < 2 or args.cols == args.rows:
        ap.error("--cols y --rows >= 2 y distintos")
    if min(args.square_mm, args.timeout, args.umbral_deg, args.umbral_mm, args.quieto_s, args.quieto_px, args.max_movimiento_px) <= 0:
        ap.error("--square-mm, --timeout, --umbral-deg, --umbral-mm, --quieto-s, --quieto-px y --max-movimiento-px > 0")
    if args.minimo < 1 or args.objetivo < args.minimo or args.frames_por_vista < 2 or not 0.1 <= args.escala_previa <= 1.0:
        ap.error("--objetivo >= --minimo >= 1; --frames-por-vista >= 2; --escala-previa entre 0.1 y 1")
    if (args.salida is None) == (args.medir_desde is None):
        ap.error("hace falta --salida (la sesion con las camaras) o --medir-desde (sin camara), una de las dos")
    rutas = dict(args.config)
    if set(rutas) != {REF, OTHER}:
        ap.error(f"--config {REF}=<perfil> {OTHER}=<perfil>, los dos y solo esos")

    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": [str(x) for x in (sys.argv[1:] if argv is None else argv)],
                    "opencv": cv2.__version__, "modo": "medir" if args.medir_desde is not None else "sesion",
                    "tablero": {"cols": args.cols, "rows": args.rows, "square_mm": args.square_mm}}
    try:
        cfgs, intr, cals = {}, {}, {}
        for cam in (REF, OTHER):
            cfgs[cam] = profiles.load(rutas[cam])
            cal = (cfgs[cam].get("camera") or {}).get("calibration_file")
            if not cal:
                raise ValueError(f"el perfil de {cam} ({rutas[cam].name}) no trae camera.calibration_file")
            intr[cam], cals[cam] = ce.leer_intrinsecos(cal), str(cal)
            modo = (int(cfgs[cam]["camera"]["width"]), int(cfgs[cam]["camera"]["height"]))
            if intr[cam]["shape"] is not None and tuple(intr[cam]["shape"]) != modo:
                raise ValueError(f"los intrinsecos de {cam} son de {intr[cam]['shape']} y su perfil pide {modo}")
        if args.medir_desde is not None and not args.medir_desde.is_dir():
            raise FileNotFoundError(f"no existe la carpeta de --medir-desde: {args.medir_desde}")
        if args.salida is not None and args.salida.exists() and (not args.salida.is_dir() or any(args.salida.iterdir())):
            raise FileExistsError(f"la carpeta de salida ya tiene algo, no se pisa: {args.salida}")
    except (OSError, ValueError, KeyError) as e:
        log_error(str(e))
        return 2
    estado["perfiles"] = {c: {"archivo": Path(rutas[c]).name, "sha256": sha256_file(rutas[c])} for c in (REF, OTHER)}
    estado["intrinsecos"] = {c: {"archivo": Path(cals[c]).name, "sha256": sha256_file(cals[c])} for c in (REF, OTHER)}

    t_inicio = time.perf_counter()
    vig = _vigilante(args.timeout + (0.0 if args.medir_desde is not None else 60.0), estado, args.reporte)
    rc = 0
    cams: dict = {}
    grabbers: dict = {}
    try:
        if args.medir_desde is not None:
            log_info(f"Midiendo la vista previa sobre {args.medir_desde} (sin camara)...")
            m = medir_desde_vistas(args.medir_desde, intr, args.cols, args.rows, args.square_mm)
            estado["medida"] = ce._jsonable(m)
            _log_medida(m)
            return 0 if m["cumple_previa"] else 1
        try:
            for cam in (REF, OTHER):            # el orden del P-7b5: gs1 y despues gs2
                log_info(f"Abriendo {cam} ({Path(rutas[cam]).name})...")
                b = create_backend(cfgs[cam]["camera"])
                b.open()
                cams[cam] = b
                real = getattr(b, "tamano_real", None)
                if real is not None and intr[cam]["shape"] is not None and tuple(real) != tuple(intr[cam]["shape"]):
                    raise RuntimeError(f"{cam}: el frame real es {real} y los intrinsecos de {intr[cam]['shape']}")
        except (RuntimeError, ValueError, OSError, cv2.error) as e:
            estado["error"] = f"no se pudieron abrir las dos camaras: {e}"
            log_error(estado["error"])
            return 2
        for cam in (REF, OTHER):
            grabbers[cam] = FrameGrabber(cams[cam], clock=time.perf_counter, max_failures=MAX_FALLOS_LECTURA)
            grabbers[cam].start()
        asistente = Asistente(args.cols, args.rows, args.square_mm, intr, args.umbral_deg, args.umbral_mm,
                              args.quieto_s, args.quieto_px, args.objetivo, args.minimo, POSTURAS)
        log_info(f"Las dos camaras abiertas en {time.perf_counter() - t_inicio:.1f} s. Objetivo {args.objetivo} vistas "
                 f"(minimo {args.minimo}); tope {args.timeout:.0f} s. Teclas en la ventana: q termina, n salta la postura.")
        r = capturar_sesion(grabbers, intr, asistente, args.salida, t_inicio + args.timeout, args.frames_por_vista,
                            args.max_movimiento_px, pitido=None if args.sin_pitido else _pitido,
                            detector_previa=args.detector_previa, escala_previa=args.escala_previa,
                            meta={k: estado[k] for k in ("fecha", "argv", "opencv", "perfiles", "intrinsecos")})
        estado["resultado"] = ce._jsonable(r)
        rc = r["codigo"]
        v = r["variedad"]
        log_stats(f"Fin ({r['fin']}): {r['tomadas']} vistas tomadas y {r['rechazadas']} rechazadas en {r['duracion_s']:.0f} s; "
                  f"dt max entre camaras {_num(r['dt_max_ms'], '.2f')} ms")
        for cam in (REF, OTHER):
            log_stats(f"{cam}: fps de camara mediana {_num(r['fps'][cam]['mediana'])}, minimo {_num(r['fps'][cam]['min'])} "
                      f"({r['fps'][cam]['tramos']} tramos de {TRAMO_FPS_S:g} s)")
        log_stats(f"ventana: mediana {_num(r['hz_ventana']['mediana'])} Hz, minimo {_num(r['hz_ventana']['min'])}")
        if v.get("n"):
            log_stats(f"Variedad en {v['camara']}: inclinacion de {v['inclinacion_min_deg']:.0f} a {v['inclinacion_max_deg']:.0f} grados, "
                      f"z de {v['z_min_mm']:.0f} a {v['z_max_mm']:.0f} mm ({v['z_recorrido_mm']:.0f} de recorrido)")
        if rc == 4:
            log_error(f"la camara {r['camara']} dejo de dar frames ({r['error_camara'] or f'{ESTANCADA_S:g} s sin ninguno'})")
        elif rc == 1:
            log_warn(f"termino con {r['tomadas']} vistas y hacen falta {args.minimo}")
        log_info(f"Sesion: {r['sesion']}")
        log_info("El calculo, despues (desde codigo\\, con el venv):")
        log_info("  " + _comando_calculo(args.salida, cals, args))
    except (RuntimeError, ValueError, OSError, cv2.error) as e:
        estado["error"] = str(e)
        log_error(str(e))
        rc = 2
    finally:
        for g in grabbers.values():
            g.stop()                    # el hilo suelta la camara antes de cerrarla
        for b in cams.values():
            b.close()
        if args.medir_desde is None:
            cv2.destroyAllWindows()
        vig.cancel()
        if args.reporte is not None:
            args.reporte.parent.mkdir(parents=True, exist_ok=True)
            args.reporte.write_text(json.dumps(ce._jsonable(estado), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            log_info(f"Reporte: {args.reporte}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
