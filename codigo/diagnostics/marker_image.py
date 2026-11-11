"""El marker ArUco para imprimir: SVG y PNG a escala, y el STL bicolor (meta 006 · Grafo de
factores optico-inercial, fase 7c · La referencia con su propio ID; B55, P48 y P50).

La referencia nueva es el ID 100 de `DICT_ARUCO_MIP_36h12`, de ~100 mm (P48): con otro ID
que los Marker0 de hoy (los dos son ID 0, uno de 80 mm y otro de ~100), el tracker ya no
puede tomar uno por otro. Este modulo saca los archivos para hacerla; no abre camara ni
red (solo `cv2` y `numpy`). Lo que mide el autor con calibrador, 5 medidas del lado
exterior negro, es lo que va a `size_mm` del perfil: el lado nominal de aqui no.

- `modulos`: la matriz de modulos del marker, de `cv2.aruco.generateImageMarker` a un
  pixel por modulo (8x8 para `DICT_ARUCO_MIP_36h12`: 6 de codigo y 1 de borde por lado).
- `marker_svg`: el SVG en mm exactos (un `rect` por modulo negro), con margen blanco y,
  debajo del margen, una regla de 50 mm (para comprobar la escala de la impresion) y el
  texto con el ID, el lado nominal y el diccionario. Ancho `lado + 2 * margen`; el alto
  suma la franja de la regla (`FRANJA_MM`).
- `marker_png`: el marker, el margen y la regla en pixeles a `ppp` puntos por pulgada,
  sin el texto; `png_bytes` lo codifica con su resolucion escrita (bloque pHYs), para que
  se imprima a escala. Sin texto porque las letras dan IDs fantasma: con el texto dibujado
  (fuente Hershey), el detector de los perfiles leia ademas del 100 un 20 o un 160 en 5 de
  56 resoluciones (50 a 600 ppp); sin el, 0 de 56 (medido el 2026-11-11). Por lo mismo, en
  una impresion en papel la franja de la regla y el texto se recorta despues de comprobar
  la escala: no se deja junto al marker.
- `marker_stl`: las dos piezas para la impresora 3D multicolor (Bambu Lab A1, cama de
  256 x 256 mm), como el tablero de la meta 002 (`Claude outputs/tablero/
  generar_tablero.py`, de donde sale la malla): `blanco` (la base entera y la capa de
  arriba donde no hay negro) y `negro` (la capa de arriba de los modulos negros), cada una
  una malla cerrada con el mismo origen. Cada modulo negro va agrandado `comp_mm` por
  lado, porque en la impresion multicolor el negro sale encogido (tablero: 0.40). Vista
  desde arriba (+z), la pieza es el marker tal cual, sin espejo.

Uso (desde codigo\\, con el venv y los argumentos explicitos, principio 7; la carpeta de
salida tiene que ser nueva o estar vacia: no pisa nada):

    python -m diagnostics.marker_image --diccionario DICT_ARUCO_MIP_36h12 --id 100 ^
        --lado-mm 100 --margen-mm 15 --ppp 600 ^
        --stl-comp-mm 0.40 --stl-base-mm 2.4 --stl-capa-mm 0.6 ^
        --salida "..\\Claude outputs\\fases\\006\\fase-7c\\marker" --timeout 60

Escribe `marker_<id>_<lado>mm.svg` y `.png` y, con las tres opciones `--stl-*`,
`marker_<id>_<lado>mm_blanco.stl` y `_negro.stl`. Antes de salir comprueba que el detector
ve en la PNG ese ID y solo ese. Codigos: 0; 1 si esa comprobacion falla; 2 si los
argumentos no valen, la carpeta tiene algo o salta el tope de tiempo.

Context7 (2026-11-11, `/websites/opencv`, documentacion 5.0; instalado 4.11):
`cv.aruco.generateImageMarker(dictionary, id, sidePixels[, img[, borderBits]]) -> img`
(la imagen canonica, lista para imprimir; el `id` tiene que ser del diccionario);
`cv.imencode(ext, img[, params]) -> retval, buf`; `ArucoDetector.detectMarkers(image) ->
corners, ids, rejectedImgPoints`.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import threading
import zlib
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from vision.detection import get_dictionary

TAG = "[marker_image]"
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USO = 2
REGLA_MM = 50.0             # la regla para comprobar la escala de la impresion
FRANJA_MM = 14.0            # la franja de la regla y el texto, debajo del margen
PPP_MIN, PPP_MAX = 50, 2400
PNG_FIRMA = b"\x89PNG\r\n\x1a\n"

Triangulo = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def modulos(dictionary: str, marker_id: int, border_bits: int = 1) -> np.ndarray:
    """La matriz de modulos del marker `marker_id` de `dictionary`, con su borde: uint8
    (n, n), 0 = negro y 255 = blanco, con n = bits del codigo + 2 * `border_bits`."""
    d = get_dictionary(dictionary)
    total = int(d.bytesList.shape[0])
    if isinstance(marker_id, bool) or not isinstance(marker_id, (int, np.integer)) \
            or not 0 <= int(marker_id) < total:
        raise ValueError(f"el ID {marker_id!r} no es de {dictionary} (0 a {total - 1})")
    if int(border_bits) < 1:
        raise ValueError(f"border_bits tiene que ser >= 1, no {border_bits}")
    n = int(d.markerSize) + 2 * int(border_bits)
    mod = cv2.aruco.generateImageMarker(d, int(marker_id), n, borderBits=int(border_bits))
    if mod.shape != (n, n) or not set(np.unique(mod).tolist()) <= {0, 255}:
        raise RuntimeError(f"generateImageMarker no dio una matriz {n}x{n} de 0 y 255")
    return mod


def etiqueta(dictionary: str, marker_id: int, side_mm: float) -> str:
    """El texto que acompana al marker en el SVG: `ID <n> · <lado> mm nominal · <diccionario>`."""
    return f"ID {int(marker_id)} · {side_mm:g} mm nominal · {dictionary}"


def _comprobar_medidas(side_mm: float, margin_mm: float) -> None:
    if not side_mm > 0:
        raise ValueError(f"el lado tiene que ser > 0 mm, no {side_mm}")
    if not margin_mm > 0:
        raise ValueError(f"el margen blanco tiene que ser > 0 mm, no {margin_mm} (el detector lo necesita)")


def _xml(texto: str) -> str:
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def marker_svg(dictionary: str, marker_id: int, side_mm: float, margin_mm: float, label: str) -> str:
    """El marker en SVG, en mm exactos (una unidad del `viewBox` es 1 mm): el fondo blanco,
    un `rect` por modulo negro, y bajo el margen la regla de `REGLA_MM` y `label`."""
    _comprobar_medidas(side_mm, margin_mm)
    mod = modulos(dictionary, marker_id)
    n = mod.shape[0]
    paso = side_mm / n
    ancho = side_mm + 2 * margin_mm
    alto = ancho + FRANJA_MM
    f = lambda v: f"{v:.4f}".rstrip("0").rstrip(".")       # noqa: E731
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(ancho)}mm" height="{f(alto)}mm" '
         f'viewBox="0 0 {f(ancho)} {f(alto)}">',
         f'  <rect id="fondo" x="0" y="0" width="{f(ancho)}" height="{f(alto)}" fill="#ffffff"/>',
         '  <g id="marker" fill="#000000" shape-rendering="crispEdges">']
    for r in range(n):
        for c in range(n):
            if mod[r, c] == 0:
                L.append(f'    <rect x="{f(margin_mm + c * paso)}" y="{f(margin_mm + r * paso)}" '
                         f'width="{f(paso)}" height="{f(paso)}"/>')
    L.append("  </g>")
    x0, y0 = margin_mm, ancho + 4.0
    L.append('  <g id="regla" stroke="#000000" stroke-width="0.2" fill="none">')
    L.append(f'    <line x1="{f(x0)}" y1="{f(y0)}" x2="{f(x0 + REGLA_MM)}" y2="{f(y0)}"/>')
    for k in range(int(REGLA_MM // 10) + 1):
        L.append(f'    <line x1="{f(x0 + 10 * k)}" y1="{f(y0 - 2)}" x2="{f(x0 + 10 * k)}" y2="{f(y0 + 2)}"/>')
    L.append("  </g>")
    L.append(f'  <text x="{f(x0 + REGLA_MM + 2)}" y="{f(y0 + 1.2)}" font-family="sans-serif" '
             f'font-size="3.5">{f(REGLA_MM)} mm</text>')
    L.append(f'  <text id="etiqueta" x="{f(x0)}" y="{f(y0 + 7.5)}" font-family="sans-serif" '
             f'font-size="3.5">{_xml(label)}</text>')
    L.append("</svg>")
    return "\n".join(L) + "\n"


def marker_png(dictionary: str, marker_id: int, side_mm: float, margin_mm: float, ppp: int) -> np.ndarray:
    """El marker en pixeles a `ppp` puntos por pulgada: uint8 en gris, con el margen blanco
    y, debajo, la regla de `REGLA_MM` con una marca cada 10 mm. Sin texto: las letras dan
    IDs fantasma con el detector de los perfiles (ver el docstring del modulo)."""
    _comprobar_medidas(side_mm, margin_mm)
    if isinstance(ppp, bool) or not isinstance(ppp, (int, np.integer)) or not PPP_MIN <= int(ppp) <= PPP_MAX:
        raise ValueError(f"ppp tiene que ser un entero de {PPP_MIN} a {PPP_MAX}, no {ppp!r}")
    mod = modulos(dictionary, marker_id)
    n = mod.shape[0]
    ppmm = int(ppp) / 25.4
    px = lambda mm: int(round(mm * ppmm))                   # noqa: E731
    ancho_mm = side_mm + 2 * margin_mm
    img = np.full((px(ancho_mm + FRANJA_MM), px(ancho_mm)), 255, np.uint8)
    cortes = [px(margin_mm + k * side_mm / n) for k in range(n + 1)]
    for r in range(n):
        for c in range(n):
            if mod[r, c] == 0:
                img[cortes[r]:cortes[r + 1], cortes[c]:cortes[c + 1]] = 0
    grosor = max(1, px(0.2))
    x0, y0 = px(margin_mm), px(ancho_mm + 4.0)
    cv2.line(img, (x0, y0), (x0 + px(REGLA_MM), y0), 0, grosor)
    for k in range(int(REGLA_MM // 10) + 1):
        x = x0 + px(10.0 * k)
        cv2.line(img, (x, y0 - px(2.0)), (x, y0 + px(2.0)), 0, grosor)
    return img


def png_bytes(img: np.ndarray, ppp: int) -> bytes:
    """`img` codificada en PNG con su resolucion escrita (bloque pHYs, en pixeles por metro),
    para que un programa de impresion la saque a escala. `cv2.imencode` no la escribe."""
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise RuntimeError("cv2.imencode no pudo codificar la PNG")
    data = buf.tobytes()
    fin_ihdr = len(PNG_FIRMA) + 4 + 4 + 13 + 4
    if data[:len(PNG_FIRMA)] != PNG_FIRMA or data[12:16] != b"IHDR" or b"pHYs" in data[:fin_ihdr + 64]:
        raise RuntimeError("la PNG de cv2.imencode no tiene la cabecera esperada")
    ppm = int(round(int(ppp) / 0.0254))
    cuerpo = b"pHYs" + struct.pack(">IIB", ppm, ppm, 1)
    bloque = struct.pack(">I", 9) + cuerpo + struct.pack(">I", zlib.crc32(cuerpo) & 0xFFFFFFFF)
    return data[:fin_ihdr] + bloque + data[fin_ihdr:]


def _quad(a, b, c, d) -> list[Triangulo]:
    """El cuadrilatero a-b-c-d (antihorario visto desde fuera) en dos triangulos."""
    return [(a, b, c), (a, c, d)]


def malla_altura(xs: list[float], ys: list[float], z_bajo: list[list], z_alto: list[list]) -> list[Triangulo]:
    """La malla cerrada de una funcion de altura por celdas (de `generar_tablero.py`, meta 002).

    `z_bajo[i][j]` y `z_alto[i][j]` son el suelo y el techo de la celda (`i` en x, `j` en
    y); `None` en `z_alto` es una celda vacia. Emite el techo y el suelo de cada celda y
    paredes solo donde el vecino no cubre su altura o en el borde; los vertices se
    comparten, asi que la pieza es una sola malla cerrada.
    """
    nx, ny = len(xs) - 1, len(ys) - 1
    tri: list[Triangulo] = []

    def celda(i: int, j: int):
        if 0 <= i < nx and 0 <= j < ny and z_alto[i][j] is not None:
            return z_bajo[i][j], z_alto[i][j]
        return None

    for i in range(nx):
        for j in range(ny):
            c = celda(i, j)
            if c is None:
                continue
            lo, hi = c
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            tri += _quad((x0, y0, hi), (x1, y0, hi), (x1, y1, hi), (x0, y1, hi))      # techo
            tri += _quad((x0, y0, lo), (x0, y1, lo), (x1, y1, lo), (x1, y0, lo))      # suelo
            vecinos = ((celda(i - 1, j), (x0, y1), (x0, y0)), (celda(i + 1, j), (x1, y0), (x1, y1)),
                       (celda(i, j - 1), (x0, y0), (x1, y0)), (celda(i, j + 1), (x1, y1), (x0, y1)))
            for v, (ax, ay), (bx, by) in vecinos:
                tramos = []                 # la parte de [lo, hi] que el vecino no cubre
                if v is None:
                    tramos.append((lo, hi))
                else:
                    vlo, vhi = v
                    if vlo > lo:
                        tramos.append((lo, min(vlo, hi)))
                    if vhi < hi:
                        tramos.append((max(vhi, lo), hi))
                for za, zb in tramos:
                    if zb - za > 1e-9:
                        tri += _quad((ax, ay, za), (bx, by, za), (bx, by, zb), (ax, ay, zb))
    return tri


def aristas_sin_pareja(tri: list[Triangulo]) -> int:
    """Cuantas aristas dirigidas no aparecen una vez con su opuesta una vez: 0 en una malla cerrada."""
    r = lambda p: tuple(round(v, 4) for v in p)             # noqa: E731
    aristas: Counter = Counter()
    for a, b, c in tri:
        a, b, c = r(a), r(b), r(c)
        for u, v in ((a, b), (b, c), (c, a)):
            aristas[(u, v)] += 1
    return sum(1 for k, n in aristas.items() if n != 1 or aristas.get((k[1], k[0]), 0) != 1)


def marker_stl(dictionary: str, marker_id: int, side_mm: float, margin_mm: float,
               comp_mm: float, base_mm: float, capa_mm: float) -> dict[str, list[Triangulo]]:
    """Las dos piezas del marker para la impresion multicolor: `{"blanco": ..., "negro": ...}`,
    cada una la lista de triangulos de una malla cerrada, con el mismo origen (x a la
    derecha, y hacia arriba, z la altura; desde +z se ve el marker tal cual).

    La pieza mide `lado + 2 * margen` de lado y `base_mm + capa_mm` de alto. El negro es la
    capa de arriba (`base_mm` a `base_mm + capa_mm`) de los modulos negros, cada uno
    agrandado `comp_mm` por lado con el mismo centro; el blanco, todo lo demas. `comp_mm`
    tiene que ser > 0 (une en la esquina los modulos negros vecinos en diagonal: sin eso la
    malla no es cerrada), menor que medio modulo y menor que el margen.
    """
    _comprobar_medidas(side_mm, margin_mm)
    mod = modulos(dictionary, marker_id)
    n = mod.shape[0]
    paso = side_mm / n
    if not 0 < comp_mm < paso / 2 or not comp_mm < margin_mm:
        raise ValueError(f"comp_mm tiene que ser > 0, menor que medio modulo ({paso / 2:g} mm) y menor "
                         f"que el margen ({margin_mm:g} mm), no {comp_mm}")
    if not base_mm > 0 or not capa_mm > 0:
        raise ValueError(f"base_mm y capa_mm tienen que ser > 0, no {base_mm} y {capa_mm}")
    lado_pieza = side_mm + 2 * margin_mm
    z0, z1 = float(base_mm), float(base_mm) + float(capa_mm)
    negras = []
    for r in range(n):
        for c in range(n):
            if mod[r, c] == 0:
                x0 = margin_mm + c * paso
                y0 = margin_mm + (n - 1 - r) * paso         # la fila 0 de la imagen, arriba (y maxima)
                negras.append((x0 - comp_mm, y0 - comp_mm, x0 + paso + comp_mm, y0 + paso + comp_mm))
    redondo = lambda v: round(float(v), 6)                  # noqa: E731
    xs = sorted({0.0, redondo(lado_pieza)} | {redondo(q[0]) for q in negras} | {redondo(q[2]) for q in negras})
    ys = sorted({0.0, redondo(lado_pieza)} | {redondo(q[1]) for q in negras} | {redondo(q[3]) for q in negras})
    nx, ny = len(xs) - 1, len(ys) - 1
    es_negra = [[False] * ny for _ in range(nx)]
    for i in range(nx):
        for j in range(ny):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            es_negra[i][j] = any(a < cx < c and b < cy < d for a, b, c, d in negras)
    bl_lo = [[0.0] * ny for _ in range(nx)]
    bl_hi = [[(z0 if es_negra[i][j] else z1) for j in range(ny)] for i in range(nx)]
    ne_lo = [[(z0 if es_negra[i][j] else None) for j in range(ny)] for i in range(nx)]
    ne_hi = [[(z1 if es_negra[i][j] else None) for j in range(ny)] for i in range(nx)]
    piezas = {"blanco": malla_altura(xs, ys, bl_lo, bl_hi), "negro": malla_altura(xs, ys, ne_lo, ne_hi)}
    for nombre, tri in piezas.items():
        malas = aristas_sin_pareja(tri)
        if malas:
            raise RuntimeError(f"la pieza {nombre} no es una malla cerrada ({malas} aristas sin pareja)")
    return piezas


def stl_ascii(triangulos: list[Triangulo], nombre: str) -> str:
    """Los triangulos en STL de texto (mm, 4 decimales), como los del tablero de la meta 002."""
    L = [f"solid {nombre}"]
    for t in triangulos:
        L.append("  facet normal 0 0 0")
        L.append("    outer loop")
        for p in t:
            L.append(f"      vertex {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}")
        L.append("    endloop")
        L.append("  endfacet")
    L.append(f"endsolid {nombre}")
    return "\n".join(L) + "\n"


def ids_en_imagen(dictionary: str, img: np.ndarray) -> list[int]:
    """Los IDs de `dictionary` que ve el detector ArUco (parametros por defecto) en `img`, ordenados."""
    detector = cv2.aruco.ArucoDetector(get_dictionary(dictionary), cv2.aruco.DetectorParameters())
    _corners, ids, _rej = detector.detectMarkers(img)
    return [] if ids is None else sorted(int(i) for i in ids.flatten())


def _vigilante(timeout_s: float) -> threading.Timer:
    """A los `timeout_s` segundos lo dice y termina el proceso con codigo 2 (principio 9)."""
    def disparar() -> None:
        print(f"{TAG} TIMEOUT a los {timeout_s:.0f} s: se sale sin terminar (la carpeta de salida "
              f"puede haber quedado a medias)", flush=True)
        os._exit(EXIT_USO)
    t = threading.Timer(timeout_s, disparar)
    t.daemon = True
    t.start()
    return t


def _nombre_base(marker_id: int, side_mm: float) -> str:
    return f"marker_{int(marker_id)}_{f'{side_mm:g}'.replace('.', 'p')}mm"


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m diagnostics.marker_image",
        description="Genera el marker ArUco para imprimir: SVG y PNG a escala y, con --stl-*, el STL bicolor.")
    ap.add_argument("--diccionario", required=True, help="El diccionario ArUco, p. ej. DICT_ARUCO_MIP_36h12.")
    ap.add_argument("--id", required=True, type=int, dest="marker_id", help="El ID del marker en el diccionario.")
    ap.add_argument("--lado-mm", required=True, type=float, help="Lado nominal del cuadrado negro exterior (mm).")
    ap.add_argument("--margen-mm", required=True, type=float, help="Margen blanco alrededor del marker (mm).")
    ap.add_argument("--ppp", required=True, type=int, help=f"Puntos por pulgada de la PNG ({PPP_MIN} a {PPP_MAX}).")
    ap.add_argument("--stl-comp-mm", type=float, default=None,
                    help="STL: cuanto se agranda cada modulo negro por lado (mm); el tablero uso 0.40.")
    ap.add_argument("--stl-base-mm", type=float, default=None, help="STL: alto de la base blanca (mm).")
    ap.add_argument("--stl-capa-mm", type=float, default=None, help="STL: alto de la capa de arriba, bicolor (mm).")
    ap.add_argument("--salida", required=True, type=Path, help="Carpeta de salida, nueva o vacia (no se pisa nada).")
    ap.add_argument("--timeout", required=True, type=float, help="Tope en segundos (principio 9).")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    stl = (args.stl_comp_mm, args.stl_base_mm, args.stl_capa_mm)
    if any(v is not None for v in stl) and any(v is None for v in stl):
        print(f"{TAG} el STL pide las tres: --stl-comp-mm, --stl-base-mm y --stl-capa-mm")
        return EXIT_USO
    if not args.timeout > 0:
        print(f"{TAG} --timeout tiene que ser > 0")
        return EXIT_USO
    salida = Path(args.salida)
    if salida.exists() and (not salida.is_dir() or any(salida.iterdir())):
        print(f"{TAG} la salida ya existe y tiene algo, no se pisa: {salida}")
        return EXIT_USO
    vig = _vigilante(args.timeout)
    try:
        dic, mid, lado, margen = args.diccionario, args.marker_id, args.lado_mm, args.margen_mm
        try:
            mod = modulos(dic, mid)
            svg = marker_svg(dic, mid, lado, margen, etiqueta(dic, mid, lado))
            png = marker_png(dic, mid, lado, margen, args.ppp)
            piezas = marker_stl(dic, mid, lado, margen, *stl) if stl[0] is not None else None
        except ValueError as e:
            print(f"{TAG} {e}")
            return EXIT_USO
        n = mod.shape[0]
        if margen < lado / n:
            print(f"{TAG} AVISO: el margen ({margen:g} mm) es menor que un modulo ({lado / n:g} mm); "
                  f"el detector necesita blanco alrededor")
        salida.mkdir(parents=True, exist_ok=True)
        base = _nombre_base(mid, lado)
        (salida / f"{base}.svg").write_text(svg, encoding="utf-8", newline="\n")
        (salida / f"{base}.png").write_bytes(png_bytes(png, args.ppp))
        ancho = lado + 2 * margen
        print(f"{TAG} {dic}, ID {mid}: {n}x{n} modulos de {lado / n:g} mm; lado nominal {lado:g} mm, "
              f"margen {margen:g} mm")
        print(f"{TAG} {base}.svg: {ancho:g} x {ancho + FRANJA_MM:g} mm (regla de {REGLA_MM:g} mm debajo)")
        print(f"{TAG} {base}.png: {png.shape[1]} x {png.shape[0]} px a {args.ppp} ppp")
        if piezas is not None:
            comp, base_mm, capa_mm = stl
            for nombre, tri in piezas.items():
                (salida / f"{base}_{nombre}.stl").write_text(stl_ascii(tri, f"{base}_{nombre}"),
                                                             encoding="ascii", newline="\n")
            print(f"{TAG} {base}_blanco.stl y _negro.stl: pieza de {ancho:g} x {ancho:g} x {base_mm + capa_mm:g} mm; "
                  f"negro de {lado + 2 * comp:g} mm de lado exterior en el STL (compensacion {comp:g} por lado); "
                  f"triangulos: blanco {len(piezas['blanco'])}, negro {len(piezas['negro'])}; mallas cerradas")
        vistos = ids_en_imagen(dic, png)
        if vistos != [mid]:
            print(f"{TAG} ERROR: en la PNG el detector ve {vistos} y tenia que ver solo [{mid}]")
            return EXIT_ERROR
        print(f"{TAG} comprobado: el detector ve en la PNG el ID {mid} y solo ese")
        print(f"{TAG} el lado que va a size_mm del perfil es el MEDIDO con calibrador (5 medidas del lado "
              f"negro exterior), no el nominal")
        print(f"{TAG} salida: {salida}")
        return EXIT_OK
    finally:
        vig.cancel()


if __name__ == "__main__":
    sys.exit(main())
