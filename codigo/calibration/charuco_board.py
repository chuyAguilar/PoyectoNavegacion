# -*- coding: utf-8 -*-
"""
El tablero ChArUco del proyecto: su definicion, su archivo de medidas, su deteccion y los archivos
para imprimirlo (meta 006 · Grafo de factores optico-inercial, fase 7d · El tablero ChArUco y los
intrinsecos con el asistente de una camara; P51, P59).

Por que ChArUco: cada esquina del ajedrez lleva su ID (lo dan los dos marcadores que la rodean),
asi que el tablero se detecta aunque una parte quede fuera de la imagen. Es lo que cubre los bordes
de la imagen en los intrinsecos (el diagnostico del 2026-11-11: cobertura 0.83 con el 8x5, sin
esquinas en los ~150 px laterales). El tablero de P59: 9 x 7 casillas de 26 mm, marcadores de
19.5 mm, `DICT_4X4_50`, patron nuevo (`legacy = false`); 48 esquinas interiores y 31 marcadores.
No se cruza con la referencia del tracker (`DICT_ARUCO_MIP_36h12`): son diccionarios distintos.

- `TableroCharuco`: la definicion. `casilla_mm` es la MEDIDA con calibrador una vez impreso
  (`registrar`); `marcador_mm` se queda en el nominal: OpenCV solo lo usa para interpolar, y los
  puntos que entran en la calibracion son las esquinas del ajedrez (`puntos_objeto`).
- `leer_tablero_charuco` / `escribir_tablero_charuco`: `tablero.json` (lo que deja `generar`,
  nominal) y `data/tablero_charuco.yaml` (medido, con el formato y la regla de medida de
  `data/tablero_calibracion.yaml`).
- `rectangulos_negros`: las casillas negras y los modulos negros de cada marcador, en mm, en el
  sitio que les da `board.getObjPoints()`. De ahi salen el STL bicolor (`stl_bicolor.piezas`) y
  el SVG. `imagen` es el dibujo de OpenCV (`generateImage`) y `rasterizar` el de esos
  rectangulos: tienen que coincidir (prueba), asi el STL es el tablero que OpenCV detecta.
- `detector` y `detectar_charuco`: `CharucoDetector` con `tryRefineMarkers` y
  `CORNER_REFINE_CONTOUR`, y despues `cornerSubPix` con ventana corta sobre la imagen entera.

**La convencion de pixel (medido en la fase, OpenCV 4.11).** `CharucoDetector.detectBoard`
devuelve las esquinas desplazadas +0.5 px en x y en y respecto a `cornerSubPix`,
`findChessboardCorners` y `projectPoints` (media +0.487 / +0.488 px sobre vistas sinteticas y
+0.498 sobre la imagen de `generateImage`). El tracker detecta la referencia con
`CORNER_REFINE_SUBPIX`, que es la otra convencion: unos intrinsecos calibrados con las esquinas
tal como salen de `detectBoard` llevarian cx y cy 0.5 px corridos. `detectar_charuco` resta ese
0.5 y refina con `cornerSubPix` (ventana 7 x 7, `VENTANA_SUBPIX` = 3): sobre vistas sinteticas de
1280 x 960 a 30, 40 y 50 cm, de frente y a 45 grados, las 48 esquinas quedan a <= 0.1 px de las
verdaderas; sin ese refinado, entre 22 y 48 (el refinado propio de OpenCV usa ventanas que a 45
grados alcanzan el borde de los marcadores). Con ventana 11 x 11, a 50 cm y 45 grados vuelven a
fallar (0.15-0.2 px): por eso la corta. Como el refinado va sobre la imagen entera, la deteccion
puede hacerse a escala reducida (`escala`) sin perder precision: es lo que usa la vista previa.

Uso (desde codigo\\, con el venv; argumentos explicitos, principio 7):
    python -m calibration.charuco_board generar --casillas 9 7 --casilla-mm 26 --marcador-mm 19.5 ^
        --diccionario DICT_4X4_50 --margen-mm 8 --comp-mm 0.40 --base-mm 2.4 --capa-mm 0.6 ^
        --salida "..\\Claude outputs\\fases\\006\\fase-7d\\tablero\\completo" --timeout 120
    (con --muestra: una pieza de 3 x 3 casillas con sus marcadores, la prueba de impresion)
    python -m calibration.charuco_board registrar --tablero "<...>\\tablero.json" ^
        --medidas 208.1 208.0 208.1 208.2 208.0 --casillas-por-medida 8 ^
        --fuente "calibrador, autor, 2026-11-12" --salida data\\tablero_charuco.yaml --timeout 30
    python -m calibration.charuco_board detectar --config gs1=profiles\\tracker_config_gs1.yaml ^
        --tablero "<...>\\tablero.json" --segundos 15 --salida "<...>\\detectar.json" --timeout 60
    (con --imagen <png> en vez de --config: lo mismo sobre un archivo, sin camara)

Codigos: `generar` 0; 1 si una pieza no es una malla cerrada o el detector no lee el tablero en su
PNG; 2 si los argumentos no valen, la salida tiene algo o el tablero no cabe en la cama.
`registrar` 0; 2 si algo no vale. `detectar` 0 si leyo todas las esquinas de la pieza en >= 90 %
de los frames; 1 si no; 2 si no pudo empezar.

Context7 (2026-11-11, `/websites/opencv`, documentacion 5.0; instalado 4.11.0, firmas comprobadas
con `__doc__`): `cv.aruco.CharucoBoard(size, squareLength, markerLength, dictionary)`;
`generateImage(outSize[, img[, marginSize[, borderBits]]]) -> img`; `getObjPoints()`, `getIds()`,
`getChessboardCorners()`, `setLegacyPattern(bool)`; `matchImagePoints(detectedCorners,
detectedIds) -> objPoints, imgPoints`; `checkCharucoCornersCollinear(charucoIds) -> retval` (True
tambien con <= 2 esquinas); `CharucoParameters` (`tryRefineMarkers`, `minMarkers` = 2,
`cameraMatrix`, `distCoeffs`); `CharucoDetector(board, charucoParams, detectorParams,
refineParams).detectBoard(image) -> charucoCorners, charucoIds, markerCorners, markerIds` (solo
devuelve una esquina si encontro los dos marcadores que la rodean). La buena practica del
tutorial de calibracion multivista: `tryRefineMarkers = True`, `CORNER_REFINE_CONTOUR` y
`cornerSubPix` sobre las esquinas devueltas.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import struct
import sys
import threading
import time
import zlib
from dataclasses import dataclass, replace
from pathlib import Path

from calibration import calibrate_camera as cc   # antes de cv2: apaga la aceleracion HW de MSMF (CONTEXT 4.18)
import cv2
import numpy as np
import yaml

import profiles
from camera.backend import create_backend
from camera.grabber import FrameGrabber

from calibration import stl_bicolor
from vision.detection import get_dictionary

TAG = "[charuco_board]"
EXIT_OK, EXIT_NO_CUMPLE, EXIT_USO = 0, 1, 2
CAMA_MAX_MM = 250.0            # la Bambu Lab A1 tiene 256 x 256: la pieza con su margen no pasa de esto
MUESTRA_CASILLAS = (3, 3)      # --muestra: la prueba de impresion (como la mini_2x2 de la meta 002)
PPMM_PNG = (8, 10, 20, 40, 100)   # la PNG, a la primera escala en que casilla y margen son pixeles enteros
VENTANA_SUBPIX = 3             # cornerSubPix con ventana 7 x 7 (medido: ver el docstring)
CRITERIOS_SUBPIX = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
MAX_CORRECCION_PX = 2.0        # una esquina que el refinado mueve mas que esto (a escala 1) se descarta
CONVENCION_PX = 0.5            # lo que detectBoard suma respecto a cornerSubPix (medido, OpenCV 4.11)
MIN_ESQUINAS = 12              # esquinas minimas para que una vista valga en la calibracion
FRACCION_DETECTAR = 0.90       # `detectar`: fraccion de frames con todas las esquinas de la pieza
TOLERANCIA_NOMINAL = 0.02      # `registrar`: la casilla medida no se aparta mas que esto de la nominal
ESPERA_FRAME_S = 0.2
MAX_FALLOS_LECTURA = 300
TITULO_VENTANA = "Tablero ChArUco - q termina"
PNG_FIRMA = b"\x89PNG\r\n\x1a\n"

log_info, log_warn, log_error, log_stats = cc.log_info, cc.log_warn, cc.log_error, cc.log_stats


# ----------------------------------------------------------------------------
# La definicion
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class TableroCharuco:
    """Un tablero ChArUco: `casillas` (x, y), el lado de la casilla (el medido), el del marcador,
    el diccionario y si es el patron de antes de OpenCV 4.6 (`legacy`)."""
    casillas: tuple[int, int]
    casilla_mm: float
    marcador_mm: float
    diccionario: str
    legacy: bool = False

    def __post_init__(self) -> None:
        try:
            nx, ny = (int(v) for v in self.casillas)
        except (TypeError, ValueError):
            raise ValueError(f"casillas tiene que ser (x, y), no {self.casillas!r}")
        if tuple(self.casillas) != (nx, ny) or min(nx, ny) < 3:
            raise ValueError(f"casillas tiene que ser dos enteros >= 3, no {self.casillas!r}")
        object.__setattr__(self, "casillas", (nx, ny))
        object.__setattr__(self, "casilla_mm", float(self.casilla_mm))
        object.__setattr__(self, "marcador_mm", float(self.marcador_mm))
        object.__setattr__(self, "legacy", bool(self.legacy))
        if not 0 < self.marcador_mm < self.casilla_mm:
            raise ValueError(f"0 < marcador_mm < casilla_mm, no {self.marcador_mm} y {self.casilla_mm}")
        total = int(get_dictionary(self.diccionario).bytesList.shape[0])
        if self.marcadores > total:
            raise ValueError(f"el tablero de {nx} x {ny} pide {self.marcadores} marcadores y {self.diccionario} tiene {total}")

    @property
    def esquinas_interiores(self) -> int:
        return (self.casillas[0] - 1) * (self.casillas[1] - 1)

    @property
    def marcadores(self) -> int:
        return (self.casillas[0] * self.casillas[1]) // 2

    @property
    def ancho_mm(self) -> float:
        return self.casillas[0] * self.casilla_mm

    @property
    def alto_mm(self) -> float:
        return self.casillas[1] * self.casilla_mm

    def board(self):
        """El `cv2.aruco.CharucoBoard` de este tablero (uno por definicion; no se modifica)."""
        return _board(self)


@functools.lru_cache(maxsize=16)
def _board(t: TableroCharuco):
    b = cv2.aruco.CharucoBoard(t.casillas, t.casilla_mm, t.marcador_mm, get_dictionary(t.diccionario))
    b.setLegacyPattern(t.legacy)
    if len(b.getChessboardCorners()) != t.esquinas_interiores or len(b.getIds()) != t.marcadores:
        raise RuntimeError(f"CharucoBoard dio {len(b.getChessboardCorners())} esquinas y {len(b.getIds())} marcadores; "
                           f"se esperaban {t.esquinas_interiores} y {t.marcadores}")
    return b


def sha256_archivo(ruta) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------
# El archivo del tablero
# ----------------------------------------------------------------------------

def _datos_tablero(ruta) -> dict:
    """El contenido de `tablero.json` o de `tablero_charuco.yaml`, con las claves del JSON."""
    p = Path(ruta)
    if not p.is_file():
        raise FileNotFoundError(f"no existe el archivo del tablero ChArUco: {p}")
    try:
        if p.suffix.lower() == ".json":
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                raise ValueError("no es un objeto")
            faltan = [k for k in ("casillas", "casilla_mm", "marcador_mm", "diccionario") if k not in d]
            if faltan:
                raise ValueError(f"faltan {faltan}")
            return {"casillas": tuple(d["casillas"]), "casilla_mm": d["casilla_mm"], "marcador_mm": d["marcador_mm"],
                    "diccionario": d["diccionario"], "legacy": d.get("legacy", False), "medido": bool(d.get("medido", False)),
                    "muestra": bool(d.get("muestra", False)), "medidas_mm": None, "casillas_por_medida": None}
        if p.suffix.lower() in (".yaml", ".yml"):
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                raise ValueError("no es un mapa")
            faltan = [k for k in ("casillas_horizontales", "casillas_verticales", "lado_mm", "marcador_mm", "diccionario",
                                  "medidas_mm", "casillas_por_medida") if k not in d]
            if faltan:
                raise ValueError(f"faltan {faltan}")
            nx, ny = int(d["casillas_horizontales"]), int(d["casillas_verticales"])
            for clave, n in (("esquinas_horizontales", nx - 1), ("esquinas_verticales", ny - 1)):
                if clave in d and int(d[clave]) != n:
                    raise ValueError(f"{clave} = {d[clave]} y con {nx} x {ny} casillas son {n}")
            medidas = [float(m) for m in d["medidas_mm"]]
            lado = cc.lado_desde_medidas(medidas, int(d["casillas_por_medida"]))
            if abs(lado - float(d["lado_mm"])) > 0.005 + 1e-9:
                raise ValueError(f"lado_mm = {d['lado_mm']} y de sus medidas sale {lado:.2f}")
            return {"casillas": (nx, ny), "casilla_mm": d["lado_mm"], "marcador_mm": d["marcador_mm"],
                    "diccionario": d["diccionario"], "legacy": d.get("legacy", False), "medido": True, "muestra": False,
                    "medidas_mm": medidas, "casillas_por_medida": int(d["casillas_por_medida"])}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"{p.name}: no es un archivo de tablero ChArUco valido ({e})")
    raise ValueError(f"{p.name}: el archivo del tablero tiene que ser .json (el de `generar`) o .yaml (el de `registrar`)")


def leer_tablero_charuco(ruta) -> TableroCharuco:
    """El tablero de `tablero.json` (nominal, el de `generar`) o de `data/tablero_charuco.yaml`
    (medido, el de `registrar`). ValueError si falta una clave o los numeros no cuadran."""
    d = _datos_tablero(ruta)
    try:
        return TableroCharuco(d["casillas"], d["casilla_mm"], d["marcador_mm"], str(d["diccionario"]), bool(d["legacy"]))
    except (ValueError, TypeError) as e:
        raise ValueError(f"{Path(ruta).name}: {e}")


def describir_tablero(ruta) -> dict:
    """Lo que se apunta de un archivo de tablero en un reporte: el archivo, su sha256, si esta
    medido y la definicion."""
    d = _datos_tablero(ruta)
    t = leer_tablero_charuco(ruta)
    return {"archivo": Path(ruta).name, "sha256": sha256_archivo(ruta), "medido": d["medido"], "muestra": d["muestra"],
            "casillas": list(t.casillas), "casilla_mm": t.casilla_mm, "marcador_mm": t.marcador_mm,
            "diccionario": t.diccionario, "legacy": t.legacy, "esquinas_interiores": t.esquinas_interiores}


def escribir_tablero_charuco(ruta, t: TableroCharuco, medidas_mm: list[float], casillas_por_medida: int,
                             fecha: str, fuente: str) -> Path:
    """Escribe el archivo de medidas (`data/tablero_charuco.yaml`), como `tablero_calibracion.yaml`.

    La regla de medida: de una orilla de una casilla negra a la MISMA orilla de otra casilla negra,
    `casillas_por_medida` casillas mas alla en la misma hilera (la misma orilla: lo que engorda o
    encoge el negro al imprimirse se cancela), >= 5 medidas en hileras distintas;
    `t.casilla_mm` tiene que ser su media entre `casillas_por_medida`, con dos decimales.
    No pisa (FileExistsError) y valida antes de escribir (principio 7): `casillas_por_medida` par
    (con un numero impar las dos orillas son de casillas de distinto color y no se cancela) y que
    quepa en el tablero.
    """
    ruta = Path(ruta)
    n = int(casillas_por_medida)
    if n < 2 or n % 2 or n > max(t.casillas) - 1:
        raise ValueError(f"casillas_por_medida tiene que ser par (de una casilla negra a otra negra de la misma hilera) y "
                         f"entre 2 y {max(t.casillas) - 1}, no {casillas_por_medida}")
    medidas = [float(m) for m in medidas_mm]
    lado = cc.comprobar_lado(t.casilla_mm, medidas, n, tolerancia_mm=0.005)
    if not str(fecha).strip() or not str(fuente).strip():
        raise ValueError("fecha y fuente no pueden ir vacias")
    if ruta.exists():
        raise FileExistsError(f"el archivo de medidas ya existe, no se pisa: {ruta}")
    nx, ny = t.casillas
    texto = "\n".join([
        "# Tablero ChArUco de calibracion (meta 006, fase 7d; P51, P59). Lo escribe",
        "# `python -m calibration.charuco_board registrar` y lo leen el asistente",
        "# (`capture_stereo_board --patron charuco`) y `calibrate_camera --patron charuco`.",
        "# Medidas con calibrador digital, de una orilla de una casilla negra a la MISMA",
        "# orilla de otra casilla negra, casillas_por_medida casillas mas alla en la misma",
        "# hilera (la misma orilla: el engrosamiento se cancela).",
        "# lado_mm = media de las medidas / casillas_por_medida, con dos decimales.",
        "# marcador_mm es el nominal: OpenCV solo lo usa para interpolar las esquinas.",
        f"casillas_horizontales: {nx}",
        f"casillas_verticales: {ny}",
        f"esquinas_horizontales: {nx - 1}",
        f"esquinas_verticales: {ny - 1}",
        f"diccionario: {t.diccionario}",
        f"legacy: {'true' if t.legacy else 'false'}",
        f"marcador_mm: {t.marcador_mm:g}",
        f"medidas_mm: [{', '.join(f'{m:g}' for m in medidas)}]",
        f"casillas_por_medida: {n}",
        f"lado_mm: {lado:.2f}",
        f"fecha: {json.dumps(str(fecha), ensure_ascii=False)}",
        f"fuente: {json.dumps(str(fuente), ensure_ascii=False)}",
    ]) + "\n"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "x", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    leido = leer_tablero_charuco(ruta)
    if leido != replace(t, casilla_mm=lado):
        raise IOError(f"verificacion de lectura FALLO en {ruta}: se escribio {t} y se lee {leido}")
    return ruta


# ----------------------------------------------------------------------------
# El dibujo: rectangulos negros, imagen, SVG y STL
# ----------------------------------------------------------------------------

def rectangulos_negros(t: TableroCharuco, margen_mm: float) -> list[tuple[float, float, float, float]]:
    """Los rectangulos negros del tablero, `(x0, y0, x1, y1)` en mm con el origen en la esquina de
    arriba a la izquierda de la pieza (el tablero mas `margen_mm` por lado) y la y hacia abajo,
    como la imagen: las casillas negras (las que no llevan marcador) y los modulos negros de cada
    marcador (`generateImageMarker` a un pixel por modulo; los seguidos de una fila van en un solo
    rectangulo), en el sitio que les da `board.getObjPoints()`."""
    if margen_mm < 0:
        raise ValueError(f"margen_mm no puede ser negativo, no {margen_mm}")
    b = t.board()
    nx, ny = t.casillas
    sq, m = t.casilla_mm, float(margen_mm)
    dic = get_dictionary(t.diccionario)
    n_mod = int(dic.markerSize) + 2
    blancas: set[tuple[int, int]] = set()
    rects: list[tuple[float, float, float, float]] = []
    for mid, obj in zip(np.asarray(b.getIds()).flatten().tolist(), b.getObjPoints()):
        c = np.asarray(obj, dtype=np.float64).reshape(4, 3)
        x0, y0, x1, y1 = c[0, 0], c[0, 1], c[2, 0], c[2, 1]
        derecho = (abs(c[1, 0] - x1) < 1e-6 and abs(c[1, 1] - y0) < 1e-6 and abs(c[3, 0] - x0) < 1e-6
                   and abs(c[3, 1] - y1) < 1e-6 and x1 > x0 and y1 > y0 and np.allclose(c[:, 2], 0.0))
        if not derecho:
            raise RuntimeError(f"el marcador {mid} no esta derecho en el tablero (getObjPoints): {c.tolist()}")
        blancas.add((int((x0 + x1) / 2 // sq), int((y0 + y1) / 2 // sq)))
        mod = cv2.aruco.generateImageMarker(dic, int(mid), n_mod, borderBits=1)
        px, py = (x1 - x0) / n_mod, (y1 - y0) / n_mod
        for r in range(n_mod):
            k = 0
            while k < n_mod:
                if mod[r, k] != 0:
                    k += 1
                    continue
                k0 = k
                while k < n_mod and mod[r, k] == 0:
                    k += 1
                rects.append((m + x0 + k0 * px, m + y0 + r * py, m + x0 + k * px, m + y0 + (r + 1) * py))
    if len(blancas) != t.marcadores:
        raise RuntimeError(f"{len(blancas)} casillas con marcador y se esperaban {t.marcadores}")
    casillas = [(m + i * sq, m + j * sq, m + (i + 1) * sq, m + (j + 1) * sq)
                for j in range(ny) for i in range(nx) if (i, j) not in blancas]
    return casillas + rects


def _px_entero(mm: float, ppmm: float, que: str) -> int:
    v = mm * ppmm
    if abs(v - round(v)) > 1e-6:
        raise ValueError(f"{que} ({mm:g} mm) no mide un numero entero de pixeles a {ppmm:g} px/mm: elige otra escala")
    return int(round(v))


def imagen(t: TableroCharuco, margen_mm: float, ppmm: float) -> np.ndarray:
    """El tablero dibujado por OpenCV (`board.generateImage`) a `ppmm` pixeles por mm, con
    `margen_mm` de blanco alrededor: uint8 en gris. La casilla y el margen tienen que medir un
    numero entero de pixeles a esa escala (si no, ValueError): asi las esquinas del ajedrez caen
    exactas. Los marcadores los coloca OpenCV redondeando a pixeles."""
    sq, m = _px_entero(t.casilla_mm, ppmm, "la casilla"), _px_entero(margen_mm, ppmm, "el margen")
    nx, ny = t.casillas
    img = t.board().generateImage((nx * sq + 2 * m, ny * sq + 2 * m), marginSize=m, borderBits=1)
    if img.shape != (ny * sq + 2 * m, nx * sq + 2 * m):
        raise RuntimeError(f"generateImage dio {img.shape[::-1]} y se pidio {(nx * sq + 2 * m, ny * sq + 2 * m)}")
    return img


def rasterizar(rects, ancho_mm: float, alto_mm: float, ppmm: float) -> np.ndarray:
    """Los rectangulos negros (mm, y hacia abajo) pintados sobre blanco a `ppmm` pixeles por mm."""
    px = lambda mm: int(round(mm * ppmm))                   # noqa: E731
    img = np.full((px(alto_mm), px(ancho_mm)), 255, np.uint8)
    for x0, y0, x1, y1 in rects:
        img[px(y0):px(y1), px(x0):px(x1)] = 0
    return img


def coincidencia(t: TableroCharuco, margen_mm: float, ppmm: float) -> float:
    """La fraccion de pixeles en que `rasterizar(rectangulos_negros(t))` e `imagen(t)` coinciden."""
    a = imagen(t, margen_mm, ppmm)
    b = rasterizar(rectangulos_negros(t, margen_mm), t.ancho_mm + 2 * margen_mm, t.alto_mm + 2 * margen_mm, ppmm)
    if a.shape != b.shape:
        raise RuntimeError(f"la imagen de OpenCV mide {a.shape[::-1]} y la de los rectangulos {b.shape[::-1]}")
    return float(np.mean(a == b))


def svg(t: TableroCharuco, margen_mm: float, titulo: str) -> str:
    """El tablero en SVG, en mm exactos (una unidad del `viewBox` es 1 mm): fondo blanco y un
    `rect` por rectangulo negro. Sin texto visible (las letras dan IDs fantasma, fase 7c)."""
    ancho, alto = t.ancho_mm + 2 * margen_mm, t.alto_mm + 2 * margen_mm
    f = lambda v: f"{v:.4f}".rstrip("0").rstrip(".")       # noqa: E731
    x = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")   # noqa: E731
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(ancho)}mm" height="{f(alto)}mm" viewBox="0 0 {f(ancho)} {f(alto)}">',
         f"  <title>{x(titulo)}</title>",
         f'  <rect id="fondo" x="0" y="0" width="{f(ancho)}" height="{f(alto)}" fill="#ffffff"/>',
         '  <g id="negro" fill="#000000" shape-rendering="crispEdges">']
    for x0, y0, x1, y1 in rectangulos_negros(t, margen_mm):
        L.append(f'    <rect x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" height="{f(y1 - y0)}"/>')
    L += ["  </g>", "</svg>"]
    return "\n".join(L) + "\n"


def piezas_stl(t: TableroCharuco, margen_mm: float, comp_mm: float, base_mm: float, capa_mm: float) -> dict[str, list]:
    """`{"blanco": ..., "negro": ...}`: las dos mallas cerradas del tablero para la impresion
    multicolor (`stl_bicolor.piezas`). Vista desde arriba (+z) la pieza es el tablero tal cual,
    sin espejo: la fila de arriba de la imagen es la de y maxima. `comp_mm` tiene que ser > 0
    (une los negros que solo se tocan en una esquina), menor que el margen y menor que medio
    modulo de marcador. RuntimeError si una pieza no sale cerrada."""
    modulo = t.marcador_mm / (int(get_dictionary(t.diccionario).markerSize) + 2)
    if not 0 < comp_mm < modulo / 2 or not comp_mm < margen_mm:
        raise ValueError(f"comp_mm tiene que ser > 0, menor que medio modulo ({modulo / 2:g} mm) y menor que el margen "
                         f"({margen_mm:g} mm), no {comp_mm}")
    ancho, alto = t.ancho_mm + 2 * margen_mm, t.alto_mm + 2 * margen_mm
    negros = [(x0, alto - y1, x1, alto - y0) for x0, y0, x1, y1 in rectangulos_negros(t, margen_mm)]
    blanco, negro = stl_bicolor.piezas(negros, ancho, alto, comp_mm, base_mm, capa_mm)
    for nombre, tri in (("blanco", blanco), ("negro", negro)):
        malas = stl_bicolor.comprobar_cerrada(tri)
        if malas:
            raise RuntimeError(f"la pieza {nombre} no es una malla cerrada ({malas} aristas sin pareja)")
    return {"blanco": blanco, "negro": negro}


def png_con_escala(img: np.ndarray, ppmm: float) -> bytes:
    """`img` en PNG con su resolucion escrita (bloque pHYs, pixeles por metro), para que se
    imprima a escala (`cv2.imencode` no la escribe)."""
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise RuntimeError("cv2.imencode no pudo codificar la PNG")
    data = buf.tobytes()
    fin_ihdr = len(PNG_FIRMA) + 4 + 4 + 13 + 4
    if data[:len(PNG_FIRMA)] != PNG_FIRMA or data[12:16] != b"IHDR" or b"pHYs" in data[:fin_ihdr + 64]:
        raise RuntimeError("la PNG de cv2.imencode no tiene la cabecera esperada")
    ppm = int(round(ppmm * 1000.0))
    cuerpo = b"pHYs" + struct.pack(">IIB", ppm, ppm, 1)
    return data[:fin_ihdr] + struct.pack(">I", 9) + cuerpo + struct.pack(">I", zlib.crc32(cuerpo) & 0xFFFFFFFF) + data[fin_ihdr:]


# ----------------------------------------------------------------------------
# La deteccion
# ----------------------------------------------------------------------------

def detector(t: TableroCharuco, K: np.ndarray | None = None, dist: np.ndarray | None = None):
    """El `CharucoDetector` del tablero, con `tryRefineMarkers = True` y `CORNER_REFINE_CONTOUR`
    (la buena practica de la documentacion). Con `K` y `dist` interpola por pose aproximada; sin
    ellas, por homografia local (lo que usan la calibracion y la vista previa: la K es lo que se
    esta midiendo). Un detector por hilo."""
    cp = cv2.aruco.CharucoParameters()
    cp.tryRefineMarkers = True
    if K is not None:
        cp.cameraMatrix = np.asarray(K, dtype=np.float64)
        cp.distCoeffs = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64)
    dp = cv2.aruco.DetectorParameters()
    dp.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_CONTOUR
    return cv2.aruco.CharucoDetector(t.board(), cp, dp, cv2.aruco.RefineParameters())


def detectar_charuco(gray: np.ndarray, det, t: TableroCharuco, min_esquinas: int, *,
                     escala: float = 1.0) -> tuple[np.ndarray, np.ndarray] | None:
    """Las esquinas del ajedrez que se ven en `gray`: `(esquinas (N, 2) float64, ids (N,) int)`,
    ordenadas por ID y en la convencion de `cornerSubPix` y `projectPoints` (ver el docstring del
    modulo: a `detectBoard` se le resta 0.5 px y se refina con `cornerSubPix` sobre `gray`).
    `escala` < 1 detecta sobre la imagen reducida (mas rapido) y refina igual sobre la entera.
    Se descartan las esquinas a menos de `VENTANA_SUBPIX` + 2 px del borde (la ventana no cabe) y
    las que el refinado mueve mas de `MAX_CORRECCION_PX` / `escala`. None si quedan menos de
    `min_esquinas` o estan en linea (`checkCharucoCornersCollinear`: tampoco vale con <= 2)."""
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    if not 0.1 <= escala <= 1.0:
        raise ValueError(f"escala entre 0.1 y 1, no {escala}")
    g = gray if escala == 1.0 else cv2.resize(gray, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    c, ids, _mc, _mi = det.detectBoard(g)
    minimo = max(int(min_esquinas), 1)
    if ids is None or len(ids) < minimo:
        return None
    e = np.asarray(c, dtype=np.float64).reshape(-1, 2) / escala - CONVENCION_PX
    ids = np.asarray(ids).flatten().astype(int)
    h, w = gray.shape[:2]
    borde = VENTANA_SUBPIX + 2
    dentro = (e[:, 0] >= borde) & (e[:, 0] <= w - 1 - borde) & (e[:, 1] >= borde) & (e[:, 1] <= h - 1 - borde)
    e, ids = e[dentro], ids[dentro]
    if len(ids) < minimo:
        return None
    ref = cv2.cornerSubPix(gray, e.astype(np.float32).reshape(-1, 1, 2).copy(), (VENTANA_SUBPIX, VENTANA_SUBPIX),
                           (-1, -1), CRITERIOS_SUBPIX).reshape(-1, 2).astype(np.float64)
    vale = np.linalg.norm(ref - e, axis=1) <= MAX_CORRECCION_PX / escala
    ref, ids = ref[vale], ids[vale]
    if len(ids) < minimo or t.board().checkCharucoCornersCollinear(ids.astype(np.int32).reshape(-1, 1)):
        return None
    orden = np.argsort(ids)
    return ref[orden], ids[orden]


def puntos_objeto(t: TableroCharuco, ids) -> np.ndarray:
    """Los puntos del tablero (N, 3) float32, en mm, de las esquinas `ids`: los de
    `board.getChessboardCorners()`, que es lo que da `matchImagePoints` (prueba). El origen es la
    esquina exterior del tablero; la esquina interior (i, j) esta en ((i + 1), (j + 1)) x casilla."""
    i = np.asarray(ids).flatten().astype(int)
    if i.size and (i.min() < 0 or i.max() >= t.esquinas_interiores):
        raise ValueError(f"IDs de esquina fuera del tablero (0 a {t.esquinas_interiores - 1}): {i.tolist()}")
    return np.asarray(t.board().getChessboardCorners(), dtype=np.float32).reshape(-1, 3)[i]


def esquinas_charuco_de_posicion(dir_frames, t: TableroCharuco, det, n_frames: int, max_mov_px: float,
                                 min_esquinas: int) -> dict:
    """Como `calibrate_extrinsics.esquinas_de_posicion`, pero con los IDs: sobre los ultimos
    `n_frames` `frame_*.png` de la carpeta, las esquinas que salen en todos los frames en que el
    tablero se detecto, su media (`esquinas`, (N, 1, 2) float32, con `ids` (N,)) y cuanto se
    mueven entre frames (`movimiento_px`). `esquinas` es None, con `motivo`, si el tablero no se
    detecta en bastantes frames (2, o 1 si solo hay uno), si las comunes son menos de
    `min_esquinas` o estan en linea, o si se movio mas de `max_mov_px`."""
    d = Path(dir_frames)
    frames = sorted(d.glob("frame_*.png"))[-int(n_frames):] if d.is_dir() else []
    out: dict = {"carpeta": d.name, "n_frames": len(frames), "n_detectados": 0, "movimiento_px": None,
                 "shape": None, "esquinas": None, "ids": None, "motivo": None}
    if not frames:
        out["motivo"] = f"sin frames (frame_*.png) en {d.name}"
        return out
    det_frames, shapes = [], set()
    for p in frames:
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if g is None:
            raise ValueError(f"no se pudo leer el frame {p}")
        shapes.add(g.shape[::-1])
        r = detectar_charuco(g, det, t, min_esquinas)
        if r is not None:
            det_frames.append(dict(zip(r[1].tolist(), r[0])))
    if len(shapes) != 1:
        raise ValueError(f"los frames de {d.name} no son todos del mismo tamano: {sorted(shapes)}")
    out["shape"] = tuple(int(x) for x in shapes.pop())
    out["n_detectados"] = len(det_frames)
    minimo = 2 if len(frames) >= 2 else 1
    if len(det_frames) < minimo:
        out["motivo"] = (f"el tablero ChArUco se detecto (>= {min_esquinas} esquinas) en {len(det_frames)} de "
                         f"{len(frames)} frames (minimo {minimo})")
        return out
    comunes = sorted(set.intersection(*(set(f) for f in det_frames)))
    out["n_comunes"] = len(comunes)
    if len(comunes) < max(int(min_esquinas), 1) or \
            t.board().checkCharucoCornersCollinear(np.asarray(comunes, dtype=np.int32).reshape(-1, 1)):
        out["motivo"] = f"solo {len(comunes)} esquinas salen en todos los frames (minimo {min_esquinas}), o estan en linea"
        return out
    pila = np.array([[f[i] for i in comunes] for f in det_frames], dtype=np.float64)      # (frames, N, 2)
    media = pila.mean(axis=0)
    if len(det_frames) >= 2:
        out["movimiento_px"] = float(np.max(np.linalg.norm(pila - media, axis=2)))
        if out["movimiento_px"] > max_mov_px:
            out["motivo"] = (f"el tablero se movio {out['movimiento_px']:.2f} px entre frames "
                             f"(tope {max_mov_px:g}): no estaba quieto")
            return out
    out["esquinas"] = media.astype(np.float32).reshape(-1, 1, 2)
    out["ids"] = np.asarray(comunes, dtype=int)
    return out


def dibujar_esquinas(img_bgr: np.ndarray, esquinas, escala: float = 1.0, color=(0, 255, 0)) -> None:
    """Un circulo por esquina sobre `img_bgr` (una imagen a `escala` de la original)."""
    for x, y in np.asarray(esquinas, dtype=np.float64).reshape(-1, 2):
        cv2.circle(img_bgr, (int(round((x + 0.5) * escala - 0.5)), int(round((y + 0.5) * escala - 0.5))), 4, color, 1, cv2.LINE_AA)


# ----------------------------------------------------------------------------
# main: generar, registrar, detectar
# ----------------------------------------------------------------------------

def _vigilante(timeout_s: float) -> threading.Timer:
    """A los `timeout_s` segundos lo dice y termina el proceso con codigo 2 (principio 9)."""
    def disparar() -> None:
        print(f"{TAG} TIMEOUT a los {timeout_s:.0f} s: se sale sin terminar", flush=True)
        os._exit(EXIT_USO)
    v = threading.Timer(timeout_s, disparar)
    v.daemon = True
    v.start()
    return v


def nombre_base(t: TableroCharuco, muestra: bool) -> str:
    lado = f"{t.casilla_mm:g}".replace(".", "p")
    return f"{'muestra_' if muestra else ''}charuco_{t.casillas[0]}x{t.casillas[1]}_{lado}mm"


def generar(t: TableroCharuco, margen_mm: float, comp_mm: float, base_mm: float, capa_mm: float, salida,
            muestra: bool = False) -> dict:
    """Escribe en `salida` (nueva o vacia) `<nombre>_blanco.stl`, `<nombre>_negro.stl`, `.svg`,
    `.png` y `tablero.json`, y comprueba que el detector lee en la PNG todas las esquinas.
    ValueError si algo no vale o la pieza no cabe en la cama; FileExistsError si la salida tiene
    algo. Devuelve lo escrito y lo comprobado (`leidas`, `coincidencia`)."""
    salida = Path(salida)
    ancho, alto = t.ancho_mm + 2 * margen_mm, t.alto_mm + 2 * margen_mm
    if not margen_mm > 0:
        raise ValueError(f"el margen blanco tiene que ser > 0 mm, no {margen_mm} (el detector lo necesita)")
    if max(ancho, alto) > CAMA_MAX_MM + 1e-9:
        raise ValueError(f"la pieza mide {ancho:g} x {alto:g} mm con el margen y la cama admite {CAMA_MAX_MM:g} por lado")
    if salida.exists() and (not salida.is_dir() or any(salida.iterdir())):
        raise FileExistsError(f"la salida ya existe y tiene algo, no se pisa: {salida}")
    piezas = piezas_stl(t, margen_mm, comp_mm, base_mm, capa_mm)
    ppmm = next((p for p in PPMM_PNG if abs(t.casilla_mm * p - round(t.casilla_mm * p)) < 1e-6
                 and abs(margen_mm * p - round(margen_mm * p)) < 1e-6), None)
    if ppmm is None:
        raise ValueError(f"la casilla ({t.casilla_mm:g} mm) y el margen ({margen_mm:g} mm) no miden pixeles enteros a "
                         f"ninguna de las escalas {PPMM_PNG} px/mm")
    img = imagen(t, margen_mm, ppmm)
    base = nombre_base(t, muestra)
    salida.mkdir(parents=True, exist_ok=True)
    archivos = {}
    for nombre, tri in piezas.items():
        archivos[f"{base}_{nombre}.stl"] = stl_bicolor.escribir_stl(salida / f"{base}_{nombre}.stl", tri, f"{base}_{nombre}")
    archivos[f"{base}.svg"] = salida / f"{base}.svg"
    archivos[f"{base}.svg"].write_text(svg(t, margen_mm, f"{base}: {t.diccionario}, casilla {t.casilla_mm:g} mm, "
                                                         f"marcador {t.marcador_mm:g} mm"), encoding="utf-8", newline="\n")
    archivos[f"{base}.png"] = salida / f"{base}.png"
    archivos[f"{base}.png"].write_bytes(png_con_escala(img, ppmm))
    r = detectar_charuco(img, detector(t), t, 1)
    leidas = 0 if r is None else int(len(r[1]))
    info = {"formato": 1, "generado_por": "calibration/charuco_board.py", "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "opencv": cv2.__version__, "muestra": bool(muestra), "medido": False,
            "casillas": list(t.casillas), "casilla_mm": t.casilla_mm, "marcador_mm": t.marcador_mm,
            "diccionario": t.diccionario, "legacy": t.legacy,
            "esquinas_interiores": t.esquinas_interiores, "marcadores": t.marcadores,
            "pieza": {"margen_mm": margen_mm, "ancho_mm": ancho, "alto_mm": alto, "comp_mm": comp_mm,
                      "base_mm": base_mm, "capa_mm": capa_mm, "alto_total_mm": base_mm + capa_mm},
            "png_px_por_mm": ppmm, "triangulos": {k: len(v) for k, v in piezas.items()},
            "archivos": {n: sha256_archivo(p) for n, p in archivos.items()}}
    (salida / "tablero.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"base": base, "salida": salida, "ancho_mm": ancho, "alto_mm": alto, "ppmm": ppmm, "piezas": piezas,
            "leidas": leidas, "coincidencia": coincidencia(t, margen_mm, ppmm), "info": info}


def _cmd_generar(args) -> int:
    try:
        t = TableroCharuco(MUESTRA_CASILLAS if args.muestra else tuple(args.casillas), args.casilla_mm, args.marcador_mm,
                           args.diccionario)
        r = generar(t, args.margen_mm, args.comp_mm, args.base_mm, args.capa_mm, args.salida, muestra=args.muestra)
    except (ValueError, FileExistsError) as e:
        print(f"{TAG} {e}")
        return EXIT_USO
    except RuntimeError as e:
        print(f"{TAG} ERROR: {e}")
        return EXIT_NO_CUMPLE
    modulo = t.marcador_mm / (int(get_dictionary(t.diccionario).markerSize) + 2)
    b = r["base"]
    print(f"{TAG} {'MUESTRA de ' if args.muestra else ''}{t.casillas[0]} x {t.casillas[1]} casillas de {t.casilla_mm:g} mm, "
          f"marcadores de {t.marcador_mm:g} mm ({t.diccionario}, modulos de {modulo:g} mm): {t.esquinas_interiores} esquinas "
          f"interiores y {t.marcadores} marcadores")
    print(f"{TAG} {b}_blanco.stl y _negro.stl: pieza de {r['ancho_mm']:g} x {r['alto_mm']:g} x {args.base_mm + args.capa_mm:g} mm; "
          f"cada negro agrandado {args.comp_mm:g} mm por lado (el modulo blanco mas pequeno queda en "
          f"{modulo - 2 * args.comp_mm:g} mm en el STL); triangulos: blanco {len(r['piezas']['blanco'])}, negro "
          f"{len(r['piezas']['negro'])}; mallas cerradas")
    print(f"{TAG} {b}.svg (mm exactos) y {b}.png ({r['ppmm']} px/mm, con su resolucion escrita)")
    print(f"{TAG} los rectangulos del STL y el dibujo de OpenCV coinciden en el {100 * r['coincidencia']:.2f} % de los pixeles "
          f"a {r['ppmm']} px/mm")
    if r["leidas"] != t.esquinas_interiores:
        print(f"{TAG} ERROR: en la PNG el detector lee {r['leidas']} esquinas y el tablero tiene {t.esquinas_interiores}")
        return EXIT_NO_CUMPLE
    print(f"{TAG} comprobado: el detector lee en la PNG las {r['leidas']} esquinas")
    if args.muestra:
        print(f"{TAG} la muestra se imprime antes que el tablero: si `detectar` no lee sus {t.esquinas_interiores} esquinas, "
              f"se ajusta --comp-mm")
    else:
        print(f"{TAG} una vez impreso se mide con calibrador y se registra (`registrar`): la casilla de la calibracion es la "
              f"MEDIDA, no la nominal")
    print(f"{TAG} salida: {r['salida']}")
    return EXIT_OK


def _cmd_registrar(args) -> int:
    try:
        d = _datos_tablero(args.tablero)
        if Path(args.tablero).suffix.lower() != ".json" or d["muestra"]:
            raise ValueError("--tablero tiene que ser el tablero.json del tablero completo (no el de la muestra ni un .yaml)")
        t = leer_tablero_charuco(args.tablero)
        lado = cc.lado_desde_medidas([float(m) for m in args.medidas], args.casillas_por_medida)
        if abs(lado - t.casilla_mm) > TOLERANCIA_NOMINAL * t.casilla_mm:
            raise ValueError(f"de las medidas sale una casilla de {lado:.2f} mm y la nominal es {t.casilla_mm:g}: se aparta mas "
                             f"de un {100 * TOLERANCIA_NOMINAL:g} % (revisa las medidas y --casillas-por-medida)")
        ruta = escribir_tablero_charuco(args.salida, replace(t, casilla_mm=lado), args.medidas, args.casillas_por_medida,
                                        time.strftime("%Y-%m-%d"), args.fuente)
    except (ValueError, OSError) as e:
        print(f"{TAG} {e}")
        return EXIT_USO
    print(f"{TAG} casilla medida: {lado:.2f} mm (nominal {t.casilla_mm:g}; media de {len(args.medidas)} medidas / "
          f"{args.casillas_por_medida}); marcador {t.marcador_mm:g} mm (nominal)")
    print(f"{TAG} escrito: {ruta}")
    return EXIT_OK


def resumen_deteccion(conteos: list[int], esperadas: int) -> dict:
    """De las esquinas leidas en cada frame: cuantos frames (`n_frames`), en cuantos se leyeron todas, la
    fraccion y si cumple (`FRACCION_DETECTAR`)."""
    n = len(conteos)
    completos = sum(1 for c in conteos if c >= esperadas)
    return {"n_frames": n, "esperadas": int(esperadas), "completos": completos, "fraccion": (completos / n) if n else 0.0,
            "con_alguna": sum(1 for c in conteos if c > 0), "mediana": float(np.median(conteos)) if n else None,
            "minimo": int(min(conteos)) if n else None,
            "cumple": bool(n > 0 and completos / n >= FRACCION_DETECTAR), "criterio_fraccion": FRACCION_DETECTAR}


def detectar_en_vivo(fuente, t: TableroCharuco, segundos: float, clock=time.perf_counter, mostrar=None,
                     leer_tecla=None) -> dict:
    """Lee frames de `fuente` (la interfaz de `FrameGrabber`) durante `segundos` y apunta, por
    frame, las esquinas leidas y sus IDs. `q` termina antes. `mostrar(img)` y `leer_tecla()` se
    inyectan en las pruebas; por defecto, la ventana de cv2."""
    det = detector(t)
    if mostrar is None:
        cv2.namedWindow(TITULO_VENTANA, cv2.WINDOW_NORMAL)
        mostrar = lambda img: cv2.imshow(TITULO_VENTANA, img)      # noqa: E731
    leer_tecla = leer_tecla if leer_tecla is not None else (lambda: cv2.pollKey() & 0xFF)
    t0 = clock()
    frames: list[dict] = []
    sin_frame = 0.0
    fin = "tiempo"
    while clock() - t0 < segundos:
        t1 = clock()
        got = fuente.next_frame(ESPERA_FRAME_S)
        if got is None:
            sin_frame += clock() - t1
            if getattr(fuente, "failed", False) or sin_frame >= 5.0:
                fin = "camara_estancada"
                break
            continue
        sin_frame = 0.0
        frame = got[0]
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        r = detectar_charuco(gray, det, t, 1)
        ids = [] if r is None else r[1].tolist()
        frames.append({"t_s": clock() - t0, "esquinas": len(ids), "ids": ids})
        disp = frame.copy() if frame.ndim == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if r is not None:
            dibujar_esquinas(disp, r[0])
        todas = len(ids) >= t.esquinas_interiores
        cv2.putText(disp, f"esquinas {len(ids)} de {t.esquinas_interiores}", (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (80, 255, 80) if todas else (60, 60, 255), 2)
        mostrar(disp)
        if leer_tecla() == ord("q"):
            fin = "q"
            break
    return {"fin": fin, "duracion_s": clock() - t0, "frames": frames,
            **resumen_deteccion([f["esquinas"] for f in frames], t.esquinas_interiores)}


def _cmd_detectar(args) -> int:

    estado: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "opencv": cv2.__version__,
                    "argv": [str(a) for a in (args.argv or [])]}
    try:
        if (args.config is None) == (args.imagen is None):
            raise ValueError("hace falta --config CAM=<perfil> (con camara) o --imagen <png> (sin camara), una de las dos")
        if args.salida.exists():
            raise FileExistsError(f"la salida ya existe, no se pisa: {args.salida}")
        t = leer_tablero_charuco(args.tablero)
        estado["tablero"] = describir_tablero(args.tablero)
        if args.imagen is not None:
            img = cv2.imread(str(args.imagen), cv2.IMREAD_GRAYSCALE) if Path(args.imagen).is_file() else None
            if img is None:
                raise FileNotFoundError(f"no se pudo leer la imagen: {args.imagen}")
        else:
            cam, ruta = args.config
            cfg = profiles.load(ruta)
            estado["camara"], estado["perfil"] = cam, Path(ruta).name
    except (ValueError, OSError, KeyError) as e:
        log_error(str(e))
        return EXIT_USO
    rc = EXIT_USO
    backend = grabber = None
    try:
        if args.imagen is not None:
            r = detectar_charuco(img, detector(t), t, 1)
            ids = [] if r is None else r[1].tolist()
            estado["imagen"] = str(args.imagen)
            estado["resultado"] = {"fin": "imagen", "frames": [{"esquinas": len(ids), "ids": ids}],
                                   **resumen_deteccion([len(ids)], t.esquinas_interiores)}
        else:
            log_info(f"Abriendo {cam} ({Path(ruta).name})...")
            try:
                backend = create_backend(cfg["camera"])
                backend.open()
            except (RuntimeError, ValueError, OSError, cv2.error) as e:
                estado["error"] = f"no se pudo abrir la camara: {e}"
                log_error(estado["error"])
                return EXIT_USO
            grabber = FrameGrabber(backend, clock=time.perf_counter, max_failures=MAX_FALLOS_LECTURA)
            grabber.start()
            log_info(f"Leyendo {args.segundos:g} s. Pon la pieza delante de la camara, quieta y entera. q termina.")
            estado["resultado"] = detectar_en_vivo(grabber, t, args.segundos)
        res = estado["resultado"]
        log_stats(f"frames {res['n_frames']}; con las {res['esperadas']} esquinas de la pieza: {res['completos']} "
                  f"({100 * res['fraccion']:.1f} %; criterio >= {100 * FRACCION_DETECTAR:g} %); con alguna: {res['con_alguna']}; "
                  f"mediana {res['mediana']}, minimo {res['minimo']}")
        if res["fin"] == "camara_estancada":
            log_error("la camara dejo de dar frames")
        rc = EXIT_OK if (res["cumple"] and res["fin"] != "camara_estancada") else EXIT_NO_CUMPLE
        log_info("CUMPLE: el detector lee la pieza" if rc == EXIT_OK else "NO cumple: el detector no lee todas las esquinas")
    except (RuntimeError, ValueError, OSError, cv2.error) as e:
        estado["error"] = str(e)
        log_error(str(e))
        rc = EXIT_USO
    finally:
        if grabber is not None:
            grabber.stop()
        if backend is not None:
            backend.close()
            cv2.destroyAllWindows()
        estado["codigo"] = rc
        try:
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            with open(args.salida, "x", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(estado, indent=2, ensure_ascii=False, default=str) + "\n")
            log_info(f"Reporte: {args.salida}")
        except OSError as e:
            log_error(f"no se pudo escribir {args.salida}: {e}")
            rc = EXIT_USO
    return rc


def _cam_path(texto: str) -> tuple[str, Path]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera CAMARA=RUTA, no {texto!r}")
    c, r = texto.split("=", 1)
    return c.strip(), Path(r.strip())


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m calibration.charuco_board",
                                 description="El tablero ChArUco: generar los archivos para imprimirlo, registrar sus medidas y probar su deteccion.")
    sub = ap.add_subparsers(dest="orden", required=True)
    g = sub.add_parser("generar", help="STL bicolor, SVG, PNG y tablero.json en una carpeta nueva")
    g.add_argument("--casillas", required=True, type=int, nargs=2, metavar=("X", "Y"), help="casillas a lo ancho y a lo alto (9 7)")
    g.add_argument("--casilla-mm", required=True, type=float, help="lado nominal de la casilla (26)")
    g.add_argument("--marcador-mm", required=True, type=float, help="lado nominal del marcador (19.5)")
    g.add_argument("--diccionario", required=True, help="el diccionario ArUco de los marcadores (DICT_4X4_50)")
    g.add_argument("--margen-mm", required=True, type=float, help="margen blanco alrededor (8)")
    g.add_argument("--comp-mm", required=True, type=float, help="cuanto se agranda cada negro por lado en el STL (0.40)")
    g.add_argument("--base-mm", required=True, type=float, help="alto de la base blanca (2.4)")
    g.add_argument("--capa-mm", required=True, type=float, help="alto de la capa de arriba, bicolor (0.6)")
    g.add_argument("--muestra", action="store_true", help=f"solo una pieza de {MUESTRA_CASILLAS[0]} x {MUESTRA_CASILLAS[1]} casillas (la prueba de impresion)")
    g.add_argument("--salida", required=True, type=Path, help="carpeta de salida, nueva o vacia (no se pisa nada)")
    g.add_argument("--timeout", required=True, type=float, help="tope en segundos (principio 9)")
    g.set_defaults(func=_cmd_generar)
    r = sub.add_parser("registrar", help="escribe el archivo de medidas (data/tablero_charuco.yaml)")
    r.add_argument("--tablero", required=True, type=Path, help="el tablero.json que dejo `generar`")
    r.add_argument("--medidas", required=True, type=float, nargs="+", metavar="MM", help=">= 5 medidas del calibrador, en mm")
    r.add_argument("--casillas-por-medida", required=True, type=int, help="casillas que abarca cada medida (par: 8)")
    r.add_argument("--fuente", required=True, help="quien midio y con que (va al archivo)")
    r.add_argument("--salida", required=True, type=Path, help="el .yaml de medidas (no se pisa)")
    r.add_argument("--timeout", required=True, type=float, help="tope en segundos (principio 9)")
    r.set_defaults(func=_cmd_registrar)
    d = sub.add_parser("detectar", help="lee el tablero (o la muestra) con una camara o en una imagen")
    d.add_argument("--config", type=_cam_path, metavar="CAM=PERFIL", help="la camara, por su perfil (gs1=profiles\\tracker_config_gs1.yaml)")
    d.add_argument("--imagen", type=Path, help="sin camara: una imagen en la que buscar el tablero")
    d.add_argument("--tablero", required=True, type=Path, help="tablero.json (el de `generar`) o el .yaml de medidas")
    d.add_argument("--segundos", type=float, default=None, help="con camara: cuanto tiempo lee")
    d.add_argument("--salida", required=True, type=Path, help="JSON con lo leido en cada frame (no se pisa)")
    d.add_argument("--timeout", required=True, type=float, help="tope en segundos (principio 9)")
    d.set_defaults(func=_cmd_detectar)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _parser()
    args = ap.parse_args(argv)
    args.argv = sys.argv[1:] if argv is None else list(argv)
    if not args.timeout > 0:
        ap.error("--timeout tiene que ser > 0")
    if args.orden == "detectar":
        if args.config is not None and (args.segundos is None or not 0 < args.segundos < args.timeout):
            ap.error("con --config hace falta --segundos > 0 y menor que --timeout")
        if args.config is not None and args.imagen is not None:
            ap.error("--config (con camara) o --imagen (sin camara), no las dos")
    vig = _vigilante(args.timeout)
    try:
        return args.func(args)
    finally:
        vig.cancel()


if __name__ == "__main__":
    sys.exit(main())
