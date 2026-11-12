# -*- coding: utf-8 -*-
"""
Las dos piezas de un patron blanco y negro para la impresora 3D multicolor (meta 006 · Grafo de
factores optico-inercial, fase 7d · El tablero ChArUco y los intrinsecos con el asistente de una
camara; P51, P59).

Es la malla de `Claude outputs/tablero/generar_tablero.py` (el tablero 9x6 de la meta 002, que
salio bien en la Bambu Lab A1), pasada al repo para rectangulos negros cualesquiera: las casillas
del ajedrez y los modulos de los marcadores de un ChArUco. Sin `cv2` ni `numpy`: solo listas.

- `blanco`: la base entera (0 a `base_mm`) y la capa de arriba (`base_mm` a `base_mm + capa_mm`)
  donde no hay negro.
- `negro`: la capa de arriba de los rectangulos negros.

Cada pieza es UNA malla cerrada con el mismo origen (x a la derecha, y hacia arriba, z la altura).
En la impresion multicolor el negro sale encogido hacia dentro (meta 002: una casilla de 25 salia
de 24.1; con 0.40 por lado, de 24.7), asi que cada rectangulo negro se agranda `comp_mm` por lado
con el mismo centro. Dos negros que solo se tocan en una esquina quedan unidos por un cuadrito de
2 x `comp_mm`: sin el, la arista comun la comparten cuatro caras y la malla no es cerrada.

Construccion: una rejilla con todas las lineas de corte (los bordes de la pieza y los de cada
rectangulo agrandado); cada celda es negra o blanca; se emiten el techo y el suelo de cada celda
y paredes solo donde el vecino no cubre su altura o en el borde. Los vertices se comparten.

En Bambu Studio: importar las dos a la vez y aceptar «cargar como un objeto con varias partes»;
asignar filamento blanco y negro a cada parte.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

Triangulo = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Rectangulo = tuple[float, float, float, float]      # (x0, y0, x1, y1) en mm, x0 < x1 e y0 < y1
DECIMALES = 6                                       # los cortes se redondean a esto (1e-6 mm)


def _quad(a, b, c, d) -> list[Triangulo]:
    """El cuadrilatero a-b-c-d (antihorario visto desde fuera) en dos triangulos."""
    return [(a, b, c), (a, c, d)]


def malla_altura(xs: list[float], ys: list[float], z_bajo: list[list], z_alto: list[list]) -> list[Triangulo]:
    """La malla cerrada de una funcion de altura por celdas (la de `generar_tablero.py`, tal cual).

    `z_bajo[i][j]` y `z_alto[i][j]` son el suelo y el techo de la celda (`i` en x, `j` en y);
    `None` en `z_alto` es una celda vacia. Paredes donde dos celdas vecinas difieren (en suelo o
    en techo) o en el borde.
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


def piezas(negros: list[Rectangulo], ancho_mm: float, alto_mm: float, comp_mm: float,
           base_mm: float, capa_mm: float) -> tuple[list[Triangulo], list[Triangulo]]:
    """`(blanco, negro)`: las dos mallas cerradas de una pieza de `ancho_mm` x `alto_mm` x
    (`base_mm` + `capa_mm`) cuyo dibujo son los rectangulos `negros` (x0, y0, x1, y1 en mm, con
    la y hacia arriba: quien llama ya dio la vuelta a la imagen), cada uno agrandado `comp_mm`
    por lado. La union de los que se solapan la resuelve la rejilla de cortes.

    ValueError (principio 7) si una medida no es positiva, `comp_mm` es negativo, no hay ningun
    rectangulo, alguno esta mal formado o, ya agrandado, toca el borde de la pieza o se sale (un
    escalon que llega al borde deja una junta en T en la pared de fuera). Que cada pieza sea
    una malla cerrada lo dice `comprobar_cerrada`: con `comp_mm` = 0 y dos negros que se tocan en
    una esquina no lo es.
    """
    if not ancho_mm > 0 or not alto_mm > 0 or not base_mm > 0 or not capa_mm > 0:
        raise ValueError(f"ancho, alto, base y capa tienen que ser > 0 mm, no {ancho_mm}, {alto_mm}, {base_mm} y {capa_mm}")
    if comp_mm < 0:
        raise ValueError(f"comp_mm no puede ser negativo, no {comp_mm}")
    if not negros:
        raise ValueError("sin rectangulos negros: no hay nada que dibujar")
    r = lambda v: round(float(v), DECIMALES)                # noqa: E731
    agrandados = []
    for q in negros:
        x0, y0, x1, y1 = (float(v) for v in q)
        if not (x0 < x1 and y0 < y1):
            raise ValueError(f"rectangulo mal formado (x0 < x1 e y0 < y1): {q}")
        a = (r(x0 - comp_mm), r(y0 - comp_mm), r(x1 + comp_mm), r(y1 + comp_mm))
        if a[0] <= 0 or a[1] <= 0 or a[2] >= r(ancho_mm) or a[3] >= r(alto_mm):
            raise ValueError(f"el rectangulo {q}, agrandado {comp_mm:g} mm por lado, toca el borde o se sale de la pieza de "
                             f"{ancho_mm:g} x {alto_mm:g} mm: hace falta margen blanco alrededor")
        agrandados.append(a)
    xs = sorted({0.0, r(ancho_mm)} | {a[0] for a in agrandados} | {a[2] for a in agrandados})
    ys = sorted({0.0, r(alto_mm)} | {a[1] for a in agrandados} | {a[3] for a in agrandados})
    ix, iy = {x: i for i, x in enumerate(xs)}, {y: j for j, y in enumerate(ys)}
    nx, ny = len(xs) - 1, len(ys) - 1
    es_negra = [[False] * ny for _ in range(nx)]
    for x0, y0, x1, y1 in agrandados:           # sus bordes son cortes: cada celda queda dentro o fuera
        for i in range(ix[x0], ix[x1]):
            fila = es_negra[i]
            for j in range(iy[y0], iy[y1]):
                fila[j] = True
    z0, z1 = float(base_mm), float(base_mm) + float(capa_mm)
    bl_lo = [[0.0] * ny for _ in range(nx)]
    bl_hi = [[(z0 if es_negra[i][j] else z1) for j in range(ny)] for i in range(nx)]
    ne_lo = [[(z0 if es_negra[i][j] else None) for j in range(ny)] for i in range(nx)]
    ne_hi = [[(z1 if es_negra[i][j] else None) for j in range(ny)] for i in range(nx)]
    return malla_altura(xs, ys, bl_lo, bl_hi), malla_altura(xs, ys, ne_lo, ne_hi)


def comprobar_cerrada(tri: list[Triangulo]) -> int:
    """Cuantas aristas dirigidas no aparecen una vez con su opuesta una vez: 0 en una malla cerrada
    (la de `generar_tablero.py`)."""
    r = lambda p: tuple(round(v, 4) for v in p)             # noqa: E731
    aristas: Counter = Counter()
    for a, b, c in tri:
        a, b, c = r(a), r(b), r(c)
        aristas[(a, b)] += 1
        aristas[(b, c)] += 1
        aristas[(c, a)] += 1
    return sum(1 for k, n in aristas.items() if n != 1 or aristas.get((k[1], k[0]), 0) != 1)


def planta(tri: list[Triangulo]) -> tuple[float, float, float]:
    """(ancho, alto, altura) en mm de la caja que contiene la malla."""
    if not tri:
        raise ValueError("malla vacia")
    xs = [p[0] for t in tri for p in t]
    ys = [p[1] for t in tri for p in t]
    zs = [p[2] for t in tri for p in t]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def escribir_stl(ruta, tri: list[Triangulo], nombre: str) -> Path:
    """Los triangulos en STL de texto (mm, 4 decimales), como los del tablero de la meta 002.
    No pisa: si `ruta` existe, FileExistsError."""
    ruta = Path(ruta)
    if ruta.exists():
        raise FileExistsError(f"el STL ya existe, no se pisa: {ruta}")
    if not tri:
        raise ValueError(f"malla vacia: no se escribe {ruta.name}")
    L = [f"solid {nombre}"]
    for t in tri:
        L.append("  facet normal 0 0 0\n    outer loop")
        for p in t:
            L.append(f"      vertex {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}")
        L.append("    endloop\n  endfacet")
    L.append(f"endsolid {nombre}")
    with open(ruta, "x", encoding="ascii", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return ruta
