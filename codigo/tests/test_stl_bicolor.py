"""calibration.stl_bicolor (meta 006, fase 7d · El tablero ChArUco y los intrinsecos con el asistente de una camara).

Las dos piezas de un dibujo blanco y negro para la impresora multicolor, sin `cv2`: cada una es una
malla cerrada (cada arista dirigida, una vez, y su opuesta, una vez), entre las dos llenan la pieza
entera (los volumenes suman ancho x alto x altura) y la pieza mide lo pedido. La lista de rectangulos
puede traer solapes y rectangulos que solo se tocan en una esquina (con `comp_mm` > 0 quedan unidos).
"""
from __future__ import annotations

import ast

import pytest

from calibration import stl_bicolor as sb

from .conftest import CODIGO_DIR


def volumen(tri) -> float:
    """El volumen que encierra una malla cerrada y orientada hacia fuera (suma de tetraedros con el origen)."""
    v = 0.0
    for a, b, c in tri:
        v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return v


def test_malla_altura_de_un_bloque() -> None:
    tri = sb.malla_altura([0.0, 10.0], [0.0, 5.0], [[0.0]], [[2.0]])
    assert len(tri) == 12 and sb.comprobar_cerrada(tri) == 0
    assert volumen(tri) == pytest.approx(100.0) and sb.planta(tri) == (10.0, 5.0, 2.0)
    # Una celda vacia no emite nada. Un hueco en medio (un escalon que no llega al borde) se cierra con sus paredes.
    assert sb.malla_altura([0.0, 1.0], [0.0, 1.0], [[0.0]], [[None]]) == []
    c = [0.0, 1.0, 2.0, 3.0]
    hueco = sb.malla_altura(c, c, [[0.0] * 3 for _ in range(3)], [[3.0, 3.0, 3.0], [3.0, 1.0, 3.0], [3.0, 3.0, 3.0]])
    assert sb.comprobar_cerrada(hueco) == 0 and volumen(hueco) == pytest.approx(27.0 - 2.0)
    # Un escalon que llega al borde deja juntas en T en la pared de fuera: el volumen sale, pero no es una
    # malla cerrada por aristas, y `comprobar_cerrada` lo dice (por eso `piezas` pide margen alrededor).
    escalon = sb.malla_altura([0.0, 1.0, 2.0], [0.0, 1.0], [[0.0], [0.0]], [[1.0], [3.0]])
    assert sb.comprobar_cerrada(escalon) > 0 and volumen(escalon) == pytest.approx(4.0)
    # Sin una cara, la malla ya no es cerrada: lo dice.
    assert sb.comprobar_cerrada(tri[:-1]) > 0


def test_piezas_dos_negros_en_diagonal() -> None:
    """Dos casillas negras que solo se tocan en una esquina (como en un ajedrez)."""
    negros = [(10.0, 10.0, 20.0, 20.0), (20.0, 20.0, 30.0, 30.0)]
    blanco, negro = sb.piezas(negros, 40.0, 40.0, 0.4, 2.4, 0.6)
    assert sb.comprobar_cerrada(blanco) == 0 and sb.comprobar_cerrada(negro) == 0
    assert sb.planta(blanco) == pytest.approx((40.0, 40.0, 3.0))
    assert sb.planta(negro) == pytest.approx((20.8, 20.8, 0.6))                 # los dos, agrandados 0.4 por lado
    zs = {round(p[2], 6) for t in negro for p in t}
    assert zs == {2.4, 3.0}                                                     # el negro, solo en la capa de arriba
    area_negra = 2 * 10.8 ** 2 - 0.8 ** 2                                       # se solapan en un cuadrito de 0.8
    assert volumen(negro) == pytest.approx(area_negra * 0.6)
    assert volumen(blanco) + volumen(negro) == pytest.approx(40.0 * 40.0 * 3.0)  # entre las dos, la pieza entera
    # Sin compensacion, la arista de la esquina comun la comparten cuatro caras: no es una malla cerrada.
    _b0, n0 = sb.piezas(negros, 40.0, 40.0, 0.0, 2.4, 0.6)
    assert sb.comprobar_cerrada(n0) > 0


def test_piezas_con_solapes_y_uno_dentro_de_otro() -> None:
    negros = [(5.0, 5.0, 15.0, 15.0), (10.0, 10.0, 20.0, 20.0), (6.0, 6.0, 8.0, 8.0)]
    blanco, negro = sb.piezas(negros, 30.0, 25.0, 0.5, 1.0, 0.5)
    assert sb.comprobar_cerrada(blanco) == 0 and sb.comprobar_cerrada(negro) == 0
    area = 2 * 11.0 ** 2 - 6.0 ** 2                                             # la union: el tercero queda dentro del primero
    assert volumen(negro) == pytest.approx(area * 0.5)
    assert volumen(blanco) == pytest.approx(30.0 * 25.0 * 1.5 - area * 0.5)


@pytest.mark.parametrize("negros,ancho,alto,comp,base,capa", [
    ([], 10.0, 10.0, 0.4, 2.4, 0.6),                            # nada que dibujar
    ([(1.0, 1.0, 2.0, 2.0)], 0.0, 10.0, 0.4, 2.4, 0.6),         # sin ancho
    ([(1.0, 1.0, 2.0, 2.0)], 10.0, 10.0, 0.4, 0.0, 0.6),        # sin base
    ([(1.0, 1.0, 2.0, 2.0)], 10.0, 10.0, 0.4, 2.4, -1.0),       # capa negativa
    ([(1.0, 1.0, 2.0, 2.0)], 10.0, 10.0, -0.1, 2.4, 0.6),       # compensacion negativa
    ([(2.0, 1.0, 1.0, 2.0)], 10.0, 10.0, 0.4, 2.4, 0.6),        # x0 > x1
    ([(0.2, 1.0, 2.0, 2.0)], 10.0, 10.0, 0.4, 2.4, 0.6),        # agrandado, se sale por la izquierda
    ([(1.0, 1.0, 9.8, 2.0)], 10.0, 10.0, 0.4, 2.4, 0.6),        # agrandado, se sale por la derecha
    ([(0.4, 1.0, 2.0, 2.0)], 10.0, 10.0, 0.4, 2.4, 0.6),        # agrandado, toca el borde (junta en T)
])
def test_piezas_rechaza_lo_que_no_vale(negros, ancho, alto, comp, base, capa) -> None:
    with pytest.raises(ValueError):
        sb.piezas(negros, ancho, alto, comp, base, capa)


def test_escribir_stl_no_pisa(tmp_path) -> None:
    blanco, _negro = sb.piezas([(2.0, 2.0, 4.0, 4.0)], 10.0, 8.0, 0.4, 2.4, 0.6)
    ruta = sb.escribir_stl(tmp_path / "pieza_blanco.stl", blanco, "pieza_blanco")
    texto = ruta.read_text(encoding="ascii")
    lineas = texto.splitlines()
    assert lineas[0] == "solid pieza_blanco" and lineas[-1] == "endsolid pieza_blanco" and "\r" not in ruta.read_bytes().decode("ascii")
    assert texto.count("facet normal 0 0 0") == len(blanco) and texto.count("vertex ") == 3 * len(blanco)
    assert "      vertex 10.0000 8.0000 3.0000" in lineas
    with pytest.raises(FileExistsError):
        sb.escribir_stl(ruta, blanco, "otra")
    assert ruta.read_text(encoding="ascii") == texto                           # intacto
    with pytest.raises(ValueError):
        sb.escribir_stl(tmp_path / "vacia.stl", [], "vacia")
    assert not (tmp_path / "vacia.stl").exists()
    with pytest.raises(ValueError):
        sb.planta([])


def test_el_modulo_no_usa_cv2_ni_numpy() -> None:
    arbol = ast.parse((CODIGO_DIR / "calibration" / "stl_bicolor.py").read_text(encoding="utf-8"))
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            importados.add((nodo.module or "").split(".")[0])
    assert importados <= {"__future__", "collections", "pathlib"}, importados
