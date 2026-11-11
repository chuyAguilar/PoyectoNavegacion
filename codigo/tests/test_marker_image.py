"""El generador del marker para imprimir (meta 006, fase 7c · La referencia con su propio ID; B55, P50).

`diagnostics/marker_image.py`, sin camara: los modulos son los de `generateImageMarker`; la
PNG la detecta el detector de cada perfil del repo como el ID pedido, y solo ese, con las
esquinas donde tocan a esa escala, lleva su resolucion escrita y no trae texto (las letras
daban IDs fantasma: 5 de 56 resoluciones con el texto, 0 de 56 sin el); el SVG mide `lado + 2 *
margen` mm de ancho (el alto suma la franja de la regla) y sus `rect` son los modulos
negros; las dos piezas del STL son mallas cerradas, juntas llenan la pieza entera y, vistas
desde arriba, son el marker sin espejo; `main` escribe los archivos y no pisa una carpeta
con algo (codigo 2).
"""
from __future__ import annotations

import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import cv2
import numpy as np
import pytest

import profiles
from diagnostics import marker_image as mi
from vision.detection import create_detector, get_dictionary

from .conftest import CODIGO_DIR, PROFILES_DIR

DIC = "DICT_ARUCO_MIP_36h12"
ID_REF = 100                    # P48: la referencia nueva
LADO, MARGEN = 100.0, 15.0
SVG_NS = "{http://www.w3.org/2000/svg}"
PERFILES = ("tracker_config_gs1.yaml", "tracker_config_gs2.yaml")


@pytest.fixture(scope="module")
def detectores() -> dict:
    """El detector de cada perfil del repo (diccionario y parametros de `markers.detector`)."""
    return {n: create_detector(profiles.load(PROFILES_DIR / n)["markers"]) for n in PERFILES}


def _detectar(detector, img: np.ndarray) -> tuple[list[int], list[np.ndarray]]:
    corners, ids, _ = detector.detectMarkers(img)
    if ids is None:
        return [], []
    return [int(i) for i in ids.flatten()], [np.asarray(c, np.float64).reshape(4, 2) for c in corners]


# ----------------------------------------------------------------------------
# Los modulos
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("marker_id", [0, ID_REF, 249])
def test_los_modulos_son_los_de_generate_image_marker(marker_id: int) -> None:
    mod = mi.modulos(DIC, marker_id)
    assert mod.shape == (8, 8) and mod.dtype == np.uint8             # 6 bits de codigo + 1 de borde por lado
    assert set(np.unique(mod).tolist()) <= {0, 255}
    assert not mod[0].any() and not mod[-1].any() and not mod[:, 0].any() and not mod[:, -1].any()
    grande = cv2.aruco.generateImageMarker(get_dictionary(DIC), marker_id, 8 * 25)
    assert np.array_equal(np.kron(mod, np.ones((25, 25), np.uint8)), grande)


def test_los_modulos_de_dos_ids_no_son_los_mismos() -> None:
    assert not np.array_equal(mi.modulos(DIC, 0), mi.modulos(DIC, ID_REF))


@pytest.mark.parametrize("malo", [-1, 250, True, 1.5, "100"])
def test_un_id_que_no_es_del_diccionario_falla(malo) -> None:
    with pytest.raises(ValueError, match="no es de DICT_ARUCO_MIP_36h12"):
        mi.modulos(DIC, malo)


def test_un_diccionario_que_no_existe_falla() -> None:
    with pytest.raises(ValueError, match="no disponible"):
        mi.modulos("DICT_NO_EXISTE", 0)


# ----------------------------------------------------------------------------
# La PNG
# ----------------------------------------------------------------------------

# 200, 230, 350 y 400 ppp: donde, con el texto dibujado en la PNG, el detector leia ademas un 20 o un 160.
@pytest.mark.parametrize("ppp", [100, 200, 230, 300, 350, 400, 600])
@pytest.mark.parametrize("perfil", PERFILES)
def test_la_png_la_detecta_el_detector_del_perfil_como_ese_id_y_solo_ese(detectores, perfil: str, ppp: int) -> None:
    img = mi.marker_png(DIC, ID_REF, LADO, MARGEN, ppp)
    ppmm = ppp / 25.4
    assert img.dtype == np.uint8 and img.ndim == 2
    assert img.shape == (round((LADO + 2 * MARGEN + mi.FRANJA_MM) * ppmm), round((LADO + 2 * MARGEN) * ppmm))
    ids, corners = _detectar(detectores[perfil], img)
    assert ids == [ID_REF], ids
    # A escala: las esquinas (horario desde la superior izquierda) caen en el margen y a `lado` de distancia.
    a, b = MARGEN * ppmm, (MARGEN + LADO) * ppmm
    esperadas = np.array([[a, a], [b, a], [b, b], [a, b]])
    assert float(np.max(np.abs(corners[0] - esperadas))) <= 1.0, corners[0]


@pytest.mark.parametrize("marker_id", [0, 7, 249])
def test_la_png_de_otro_id_se_detecta_como_ese(detectores, marker_id: int) -> None:
    ids, _ = _detectar(detectores[PERFILES[0]], mi.marker_png(DIC, marker_id, 80.0, 12.0, 150))
    assert ids == [marker_id]


def test_los_modulos_de_la_png_son_los_del_marker() -> None:
    ppp = 254                                                        # 10 px por mm
    img = mi.marker_png(DIC, ID_REF, LADO, MARGEN, ppp)
    mod = mi.modulos(DIC, ID_REF)
    paso = LADO / 8 * 10
    for r in range(8):
        for c in range(8):
            y0, x0 = round(MARGEN * 10 + r * paso), round(MARGEN * 10 + c * paso)
            bloque = img[y0:y0 + round(paso), x0:x0 + round(paso)]
            assert np.all(bloque == mod[r, c]), (r, c)
    fin = round((LADO + 2 * MARGEN) * 10)                            # donde acaba el margen de abajo
    m = round(MARGEN * 10)
    assert np.all(img[:m] == 255) and np.all(img[:fin, :m] == 255)   # el margen, blanco
    assert np.all(img[fin - m:fin] == 255) and np.all(img[:fin, fin - m:] == 255)
    franja = img[fin:]
    assert franja.min() == 0 and franja.max() == 255                 # la regla, bajo el margen
    assert np.all(franja[:, round((MARGEN + mi.REGLA_MM + 1) * 10):] == 255)   # y nada mas: sin texto
    fila = franja[round(4.0 * 10)]                                   # la linea de la regla: 50 mm
    negros = np.flatnonzero(fila == 0)
    assert negros[-1] - negros[0] == pytest.approx(mi.REGLA_MM * 10, abs=3)


@pytest.mark.parametrize("ppp", [10, 5000, 300.0, True])
def test_la_png_exige_una_resolucion_que_valga(ppp) -> None:
    with pytest.raises(ValueError, match="ppp"):
        mi.marker_png(DIC, ID_REF, LADO, MARGEN, ppp)


@pytest.mark.parametrize("lado,margen", [(0.0, 15.0), (-5.0, 15.0), (100.0, 0.0)])
def test_medidas_que_no_valen_fallan(lado: float, margen: float) -> None:
    with pytest.raises(ValueError, match="> 0 mm"):
        mi.marker_png(DIC, ID_REF, lado, margen, 300)
    with pytest.raises(ValueError, match="> 0 mm"):
        mi.marker_svg(DIC, ID_REF, lado, margen, "x")


def _bloques_png(data: bytes) -> list[tuple[bytes, bytes]]:
    assert data[:8] == mi.PNG_FIRMA
    out, i = [], 8
    while i < len(data):
        (n,) = struct.unpack(">I", data[i:i + 4])
        tipo, cuerpo = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        (crc,) = struct.unpack(">I", data[i + 8 + n:i + 12 + n])
        assert crc == zlib.crc32(tipo + cuerpo) & 0xFFFFFFFF, tipo
        out.append((tipo, cuerpo))
        i += 12 + n
    return out


@pytest.mark.parametrize("ppp", [300, 600])
def test_la_png_lleva_su_resolucion(ppp: int) -> None:
    img = mi.marker_png(DIC, ID_REF, LADO, MARGEN, ppp)
    data = mi.png_bytes(img, ppp)
    bloques = _bloques_png(data)
    assert [t for t, _ in bloques][:2] == [b"IHDR", b"pHYs"] and bloques[-1][0] == b"IEND"
    assert struct.unpack(">IIB", bloques[1][1]) == (round(ppp / 0.0254), round(ppp / 0.0254), 1)   # px por metro
    assert struct.unpack(">II", bloques[0][1][:8]) == (img.shape[1], img.shape[0])
    vuelta = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    assert np.array_equal(vuelta, img)                               # sin perdida


# ----------------------------------------------------------------------------
# El SVG
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("lado,margen,ancho,alto", [(100.0, 15.0, "130mm", "144mm"), (98.6, 12.3, "123.2mm", "137.2mm")])
def test_el_svg_mide_el_lado_mas_dos_margenes(lado: float, margen: float, ancho: str, alto: str) -> None:
    raiz = ET.fromstring(mi.marker_svg(DIC, ID_REF, lado, margen, mi.etiqueta(DIC, ID_REF, lado)))
    assert raiz.tag == SVG_NS + "svg"
    assert raiz.get("width") == ancho and raiz.get("height") == alto
    assert raiz.get("viewBox") == f"0 0 {ancho[:-2]} {alto[:-2]}"    # una unidad = 1 mm
    assert float(alto[:-2]) == pytest.approx(float(ancho[:-2]) + mi.FRANJA_MM)
    assert float(ancho[:-2]) == pytest.approx(lado + 2 * margen)


def test_los_rect_del_svg_son_los_modulos_negros(detectores) -> None:
    lado, margen = 98.6, 12.3
    raiz = ET.fromstring(mi.marker_svg(DIC, ID_REF, lado, margen, "etiqueta"))
    grupo = [g for g in raiz.findall(SVG_NS + "g") if g.get("id") == "marker"]
    assert len(grupo) == 1 and grupo[0].get("fill") == "#000000"
    rects = grupo[0].findall(SVG_NS + "rect")
    mod = mi.modulos(DIC, ID_REF)
    assert len(rects) == int(np.sum(mod == 0))
    paso = lado / 8
    visto = np.full((8, 8), 255, np.uint8)
    for r in rects:
        x, y, w, h = (float(r.get(k)) for k in ("x", "y", "width", "height"))
        assert w == pytest.approx(paso, abs=1e-4) and h == pytest.approx(paso, abs=1e-4)
        c, f = (x - margen) / paso, (y - margen) / paso
        assert abs(c - round(c)) < 1e-3 and abs(f - round(f)) < 1e-3
        visto[round(f), round(c)] = 0
    assert np.array_equal(visto, mod)
    # Pintado a 4 px por mm, el detector del perfil ve ese ID.
    e = 4
    img = np.full((round((lado + 2 * margen) * e),) * 2, 255, np.uint8)
    for r in rects:
        x, y, w, h = (float(r.get(k)) for k in ("x", "y", "width", "height"))
        img[round(y * e):round((y + h) * e), round(x * e):round((x + w) * e)] = 0
    assert _detectar(detectores[PERFILES[0]], img)[0] == [ID_REF]


def test_el_svg_trae_la_regla_y_la_etiqueta_bajo_el_margen() -> None:
    texto = mi.etiqueta(DIC, ID_REF, LADO)
    assert texto == "ID 100 · 100 mm nominal · DICT_ARUCO_MIP_36h12"
    raiz = ET.fromstring(mi.marker_svg(DIC, ID_REF, LADO, MARGEN, texto))
    regla = [g for g in raiz.findall(SVG_NS + "g") if g.get("id") == "regla"][0]
    lineas = regla.findall(SVG_NS + "line")
    larga = lineas[0]
    assert float(larga.get("x2")) - float(larga.get("x1")) == pytest.approx(mi.REGLA_MM)
    assert len(lineas) == 1 + 6                                      # la regla y una marca cada 10 mm
    borde_margen = LADO + 2 * MARGEN
    assert all(float(ln.get("y1")) > borde_margen and float(ln.get("y2")) > borde_margen for ln in lineas)
    etiquetas = [t for t in raiz.findall(SVG_NS + "text") if t.get("id") == "etiqueta"]
    assert len(etiquetas) == 1 and etiquetas[0].text == texto and float(etiquetas[0].get("y")) > borde_margen


def test_la_etiqueta_del_svg_se_escapa() -> None:
    raiz = ET.fromstring(mi.marker_svg(DIC, ID_REF, LADO, MARGEN, "a < b & c"))
    assert [t.text for t in raiz.findall(SVG_NS + "text") if t.get("id") == "etiqueta"] == ["a < b & c"]


# ----------------------------------------------------------------------------
# El STL bicolor
# ----------------------------------------------------------------------------

COMP, BASE, CAPA = 0.40, 2.4, 0.6


def _volumen(tri) -> float:
    """El volumen con signo de una malla cerrada (positivo si las caras miran hacia fuera)."""
    return float(sum(np.dot(a, np.cross(b, c)) for a, b, c in np.asarray(tri, np.float64)) / 6.0)


@pytest.fixture(scope="module")
def piezas() -> dict:
    return mi.marker_stl(DIC, ID_REF, LADO, MARGEN, COMP, BASE, CAPA)


def test_las_dos_piezas_del_stl_son_mallas_cerradas_y_llenan_la_pieza(piezas) -> None:
    assert set(piezas) == {"blanco", "negro"}
    assert mi.aristas_sin_pareja(piezas["blanco"]) == 0 and mi.aristas_sin_pareja(piezas["negro"]) == 0
    bl, ne = np.asarray(piezas["blanco"]).reshape(-1, 3), np.asarray(piezas["negro"]).reshape(-1, 3)
    lado_pieza = LADO + 2 * MARGEN
    assert bl.min(axis=0).tolist() == [0.0, 0.0, 0.0]
    assert bl.max(axis=0) == pytest.approx([lado_pieza, lado_pieza, BASE + CAPA])
    assert ne.min(axis=0) == pytest.approx([MARGEN - COMP, MARGEN - COMP, BASE])        # el negro, agrandado
    assert ne.max(axis=0) == pytest.approx([MARGEN + LADO + COMP, MARGEN + LADO + COMP, BASE + CAPA])
    v_bl, v_ne = _volumen(piezas["blanco"]), _volumen(piezas["negro"])
    assert v_bl > 0 and v_ne > 0                                     # las caras miran hacia fuera
    assert v_bl + v_ne == pytest.approx(lado_pieza * lado_pieza * (BASE + CAPA), rel=1e-9)   # ni hueco ni solape
    negros = int(np.sum(mi.modulos(DIC, ID_REF) == 0))
    assert v_ne > negros * (LADO / 8) ** 2 * CAPA                    # mas que sin compensar


def test_el_stl_visto_desde_arriba_es_el_marker_sin_espejo(piezas, detectores) -> None:
    e = 4                                                            # px por mm
    lado_pieza = LADO + 2 * MARGEN
    n = round(lado_pieza * e)
    img = np.full((n, n), 255, np.uint8)
    techo = [t for t in np.asarray(piezas["negro"], np.float64) if np.allclose(t[:, 2], BASE + CAPA)]
    assert techo
    for t in techo:
        # x a la derecha; y hacia arriba en la pieza, hacia abajo en la imagen.
        pts = np.stack([t[:, 0] * e, (lado_pieza - t[:, 1]) * e], axis=1)
        cv2.fillConvexPoly(img, np.round(pts).astype(np.int32), 0)
    ids, corners = _detectar(detectores[PERFILES[0]], img)
    assert ids == [ID_REF], ids
    a, b = (MARGEN - COMP) * e, (MARGEN + LADO + COMP) * e
    assert float(np.max(np.abs(corners[0] - np.array([[a, a], [b, a], [b, b], [a, b]])))) <= 1.5
    assert _detectar(detectores[PERFILES[0]], cv2.flip(img, 1))[0] != [ID_REF]          # en espejo ya no es ese ID


@pytest.mark.parametrize("comp,base,capa,trozo", [
    (0.0, BASE, CAPA, "comp_mm"), (-0.1, BASE, CAPA, "comp_mm"), (6.25, BASE, CAPA, "comp_mm"),
    (COMP, 0.0, CAPA, "base_mm"), (COMP, BASE, 0.0, "base_mm")])
def test_el_stl_exige_medidas_que_valgan(comp: float, base: float, capa: float, trozo: str) -> None:
    with pytest.raises(ValueError, match=trozo):
        mi.marker_stl(DIC, ID_REF, LADO, MARGEN, comp, base, capa)
    with pytest.raises(ValueError, match="comp_mm"):
        mi.marker_stl(DIC, ID_REF, LADO, 0.3, COMP, BASE, CAPA)      # el margen no cubre la compensacion


def test_el_stl_de_texto(piezas) -> None:
    texto = mi.stl_ascii(piezas["negro"], "marker_negro")
    lineas = texto.splitlines()
    assert lineas[0] == "solid marker_negro" and lineas[-1] == "endsolid marker_negro" and texto.endswith("\n")
    assert texto.count("facet normal") == len(piezas["negro"]) and texto.count("vertex") == 3 * len(piezas["negro"])
    texto.encode("ascii")


def test_aristas_sin_pareja_ve_una_malla_abierta(piezas) -> None:
    assert mi.aristas_sin_pareja(piezas["negro"][:-1]) > 0


# ----------------------------------------------------------------------------
# La linea de comandos
# ----------------------------------------------------------------------------

def _args(salida: Path, *extra: str, marker_id: int = ID_REF, ppp: int = 300) -> list[str]:
    return ["--diccionario", DIC, "--id", str(marker_id), "--lado-mm", "100", "--margen-mm", "15",
            "--ppp", str(ppp), "--salida", str(salida), "--timeout", "60", *extra]


STL = ("--stl-comp-mm", "0.40", "--stl-base-mm", "2.4", "--stl-capa-mm", "0.6")


def test_main_escribe_los_archivos_y_no_pisa(tmp_path: Path, detectores, capsys) -> None:
    salida = tmp_path / "marker"
    assert mi.main(_args(salida, *STL)) == 0
    nombres = sorted(p.name for p in salida.iterdir())
    assert nombres == ["marker_100_100mm.png", "marker_100_100mm.svg",
                       "marker_100_100mm_blanco.stl", "marker_100_100mm_negro.stl"]
    out = capsys.readouterr().out
    assert "comprobado: el detector ve en la PNG el ID 100 y solo ese" in out and "MEDIDO con calibrador" in out
    png = cv2.imread(str(salida / "marker_100_100mm.png"), cv2.IMREAD_UNCHANGED)
    assert np.array_equal(png, mi.marker_png(DIC, ID_REF, 100.0, 15.0, 300))
    for perfil in PERFILES:
        assert _detectar(detectores[perfil], png)[0] == [ID_REF]
    assert (salida / "marker_100_100mm.svg").read_text(encoding="utf-8") == \
        mi.marker_svg(DIC, ID_REF, 100.0, 15.0, mi.etiqueta(DIC, ID_REF, 100.0))
    assert (salida / "marker_100_100mm_negro.stl").read_bytes().startswith(b"solid marker_100_100mm_negro\n")
    antes = {p.name: p.read_bytes() for p in salida.iterdir()}
    assert mi.main(_args(salida, *STL)) == 2                          # la carpeta tiene algo: no se pisa
    assert "no se pisa" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in salida.iterdir()} == antes


def test_main_sin_stl_escribe_solo_svg_y_png_en_una_carpeta_vacia(tmp_path: Path) -> None:
    salida = tmp_path / "vacia"
    salida.mkdir()
    assert mi.main(_args(salida)) == 0
    assert sorted(p.name for p in salida.iterdir()) == ["marker_100_100mm.png", "marker_100_100mm.svg"]


def test_main_con_un_lado_con_decimales_lo_pone_en_el_nombre(tmp_path: Path) -> None:
    salida = tmp_path / "m"
    args = ["--diccionario", DIC, "--id", "7", "--lado-mm", "98.6", "--margen-mm", "15", "--ppp", "150",
            "--salida", str(salida), "--timeout", "60"]
    assert mi.main(args) == 0
    assert sorted(p.name for p in salida.iterdir()) == ["marker_7_98p6mm.png", "marker_7_98p6mm.svg"]


@pytest.mark.parametrize("extra,kw,trozo", [
    (("--stl-comp-mm", "0.4"), {}, "las tres"),                       # el STL a medias
    ((), {"marker_id": 250}, "no es de"),                             # un ID fuera del diccionario
    ((), {"ppp": 10}, "ppp"),
    (("--stl-comp-mm", "0", "--stl-base-mm", "2.4", "--stl-capa-mm", "0.6"), {}, "comp_mm")])
def test_main_con_argumentos_que_no_valen_da_2_y_no_escribe(tmp_path: Path, capsys, extra, kw, trozo: str) -> None:
    salida = tmp_path / "m"
    assert mi.main(_args(salida, *extra, **kw)) == 2
    assert trozo in capsys.readouterr().out
    assert not salida.exists()


def test_main_exige_sus_argumentos(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        mi.main(["--diccionario", DIC, "--id", "100", "--lado-mm", "100", "--margen-mm", "15", "--ppp", "300",
                 "--salida", str(tmp_path / "m")])                    # sin --timeout
    assert mi.main(_args(tmp_path / "m")[:-1] + ["0"]) == 2          # --timeout 0


def test_main_si_el_detector_no_ve_el_id_da_1(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mi, "ids_en_imagen", lambda dic, img: [0, 100])
    assert mi.main(_args(tmp_path / "m")) == 1
    assert "ERROR: en la PNG el detector ve [0, 100]" in capsys.readouterr().out


def test_el_vigilante_corta_con_codigo_2(monkeypatch, capsys) -> None:
    salidas: list[int] = []
    monkeypatch.setattr(mi.os, "_exit", salidas.append)
    t = mi._vigilante(0.01)
    limite = time.monotonic() + 5.0
    while not salidas and time.monotonic() < limite:
        time.sleep(0.01)
    t.cancel()
    assert salidas == [2] and "TIMEOUT" in capsys.readouterr().out


def test_el_modulo_no_importa_camara_ni_red() -> None:
    codigo = ("import sys; import diagnostics.marker_image; "
              "malos = [m for m in sys.modules if m.split('.')[0] in ('camera', 'pyigtl', 'transport', 'tracker')]; "
              "print(malos); sys.exit(1 if malos else 0)")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=str(CODIGO_DIR), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
