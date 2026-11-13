"""calibration.charuco_board sin camara (meta 006, fase 7d · El tablero ChArUco y los intrinsecos con el asistente de una camara).

Los puntos 7, 8 y 9 del criterio de la fase (`plan.md`):
  7. `rasterizar(rectangulos_negros(t))` e `imagen(t)` coinciden; las dos piezas del STL son mallas cerradas y
     su planta mide 250 x 198 mm; `--muestra` da 3 x 3 casillas; la carpeta con algo y un tablero de mas de
     250 mm, codigo 2.
  8. `detectar_charuco` sobre vistas sinteticas a 1280 x 960 con la K y la distorsion de gs1: a 30, 40 y 50 cm,
     de frente y a 45 grados, >= 40 de 48 esquinas a <= 0.1 px; con un 40 % del tablero fuera, las que quedan
     dentro con sus dos marcadores; en linea, None. Y el tiempo por frame a escala 1 y 0.5.
  9. Con la referencia (ID 100, 36h12) en la misma imagen: las mismas esquinas, y el detector del perfil solo ve
     el ID 100.
Ademas: la convencion de pixel de `detectBoard` (+0.5 px, lo que corrige `detectar_charuco`), el archivo de
medidas (`registrar`, `leer_tablero_charuco`), `esquinas_charuco_de_posicion` y `detectar` con una camara falsa.
Las vistas salen de `tablero_sintetico.renderizar_charuco` (con distorsion). Ninguna prueba abre una camara.
"""
from __future__ import annotations

import json
import time

import cv2
import numpy as np
import pytest

import profiles
from calibration import calibrate_extrinsics as ce
from calibration import charuco_board as chb
from calibration import stl_bicolor as sb
from vision.detection import create_detector, detect, get_dictionary

from . import tablero_sintetico as ts
from .conftest import CODIGO_DIR, DATA_DIR, PROFILES_DIR
from .test_stl_bicolor import volumen

T = chb.TableroCharuco((9, 7), 26.0, 19.5, "DICT_4X4_50")                  # el de P59
SHAPE = (1280, 960)
GS1 = ce.leer_intrinsecos(DATA_DIR / "intrinsecos_gs1_1280x960.yml")        # la K y la distorsion de gs1 (meta 002)
K, DIST = GS1["K"], GS1["dist"]
MARGEN, COMP, BASE, CAPA = 8.0, 0.40, 2.4, 0.6
ARGV_GENERAR = ["generar", "--casillas", "9", "7", "--casilla-mm", "26", "--marcador-mm", "19.5", "--diccionario", "DICT_4X4_50",
                "--margen-mm", "8", "--comp-mm", "0.40", "--base-mm", "2.4", "--capa-mm", "0.6", "--timeout", "120"]


def vista(z_mm: float, rvec=(0.0, 0.0, 0.0), objetivo=(640.0, 480.0), dist=DIST, t=T, shape=SHAPE, K_=K, **kw):
    """(imagen, rvec, tvec): el tablero con su centro en `objetivo` a `z_mm`."""
    rv = np.asarray(rvec, dtype=np.float64)
    tv = ts.pose_charuco_hacia(t, K_, rv, objetivo, z_mm)
    return ts.renderizar_charuco(t, K_, rv, tv, shape, dist, **kw), rv, tv


def verdaderas(ids, rv, tv, dist=DIST, t=T, K_=K) -> np.ndarray:
    d = np.zeros(5) if dist is None else dist
    return cv2.projectPoints(chb.puntos_objeto(t, ids).astype(np.float64), rv, tv, K_, d)[0].reshape(-1, 2)


@pytest.fixture(autouse=True)
def sin_camara_real(monkeypatch):
    def _prohibido(*_a, **_k):
        raise AssertionError("una prueba intento abrir una camara real (create_backend)")
    monkeypatch.setattr(chb, "create_backend", _prohibido)


@pytest.fixture(autouse=True)
def sin_ventanas(monkeypatch):
    visto = {"namedWindow": 0, "imshow": 0, "destroyAllWindows": 0}
    monkeypatch.setattr(chb.cv2, "namedWindow", lambda *a, **k: visto.__setitem__("namedWindow", visto["namedWindow"] + 1))
    monkeypatch.setattr(chb.cv2, "imshow", lambda *a, **k: visto.__setitem__("imshow", visto["imshow"] + 1))
    monkeypatch.setattr(chb.cv2, "destroyAllWindows", lambda: visto.__setitem__("destroyAllWindows", visto["destroyAllWindows"] + 1))
    monkeypatch.setattr(chb.cv2, "pollKey", lambda: -1)
    return visto


# ----------------------------------------------------------------------------
# La definicion y el dibujo (punto 7)
# ----------------------------------------------------------------------------

def test_el_tablero_de_p59() -> None:
    assert (T.esquinas_interiores, T.marcadores, T.ancho_mm, T.alto_mm) == (48, 31, 234.0, 182.0)
    b = T.board()
    assert b is T.board() and b.getLegacyPattern() is False                 # uno por definicion, patron nuevo
    assert np.asarray(b.getIds()).flatten().tolist() == list(range(31))     # IDs 0-30 de DICT_4X4_50
    assert chb.TableroCharuco([9, 7], 26, 19.5, "DICT_4X4_50") == T         # los tipos se normalizan
    for mal in (dict(casillas=(9, 2)), dict(casillas=(9,)), dict(marcador_mm=26.0), dict(marcador_mm=0.0),
                dict(casillas=(11, 10)), dict(diccionario="DICT_NO_EXISTE")):   # 11 x 10 pide 55 marcadores y hay 50
        with pytest.raises(ValueError):
            chb.TableroCharuco(**{**dict(casillas=(9, 7), casilla_mm=26.0, marcador_mm=19.5, diccionario="DICT_4X4_50"), **mal})


def test_los_rectangulos_son_el_dibujo_de_opencv() -> None:
    rects = chb.rectangulos_negros(T, MARGEN)
    assert len(rects) > 32 + 31 and all(x0 < x1 and y0 < y1 for x0, y0, x1, y1 in rects)
    assert rects[0] == (8.0, 8.0, 34.0, 34.0)                              # la casilla de arriba a la izquierda, negra
    a10 = chb.imagen(T, MARGEN, 10)
    b10 = chb.rasterizar(rects, 250.0, 198.0, 10)
    assert a10.shape == b10.shape == (1980, 2500) and set(np.unique(a10).tolist()) == {0, 255}
    frac = chb.coincidencia(T, MARGEN, 10)
    assert frac == pytest.approx(float(np.mean(a10 == b10))) and frac >= 0.995, frac
    # Lo que difiere esta solo en los bordes de los rectangulos (OpenCV coloca los marcadores redondeando a pixeles).
    bordes = cv2.morphologyEx(b10, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    assert int(((a10 != b10) & ~bordes).sum()) == 0
    # A 8 px/mm el modulo del marcador mide 26 px justos: coinciden pixel a pixel.
    assert chb.coincidencia(T, MARGEN, 8) == 1.0
    print(f"[fase 7d] rasterizar frente a generateImage: {100 * frac:.2f} % a 10 px/mm ({int((a10 != b10).sum())} px, todos en "
          f"bordes); 100 % a 8 px/mm")
    with pytest.raises(ValueError):
        chb.imagen(T, MARGEN, 7.3)                                          # la casilla no mide pixeles enteros
    with pytest.raises(ValueError):
        chb.rectangulos_negros(T, -1.0)
    s = chb.svg(T, MARGEN, "prueba <&>")
    assert s.count("<rect ") == 1 + len(rects) and 'width="250mm" height="198mm" viewBox="0 0 250 198"' in s
    assert "<text" not in s and "prueba &lt;&amp;&gt;" in s                 # sin texto visible


@pytest.fixture(scope="module")
def generado(tmp_path_factory):
    """El tablero completo generado una vez (STL, SVG, PNG y tablero.json)."""
    salida = tmp_path_factory.mktemp("charuco") / "completo"
    t0 = time.perf_counter()
    r = chb.generar(T, MARGEN, COMP, BASE, CAPA, salida)
    r["segundos"] = time.perf_counter() - t0
    return r


def test_las_piezas_del_stl_son_cerradas_y_miden_250_por_198(generado) -> None:
    p = generado["piezas"]
    assert sb.comprobar_cerrada(p["blanco"]) == 0 and sb.comprobar_cerrada(p["negro"]) == 0
    ancho, alto, z = sb.planta(p["blanco"])
    assert ancho == pytest.approx(250.0, abs=0.01) and alto == pytest.approx(198.0, abs=0.01) and z == pytest.approx(3.0)
    assert sb.planta(p["negro"]) == pytest.approx((234.0 + 2 * COMP, 182.0 + 2 * COMP, CAPA))
    assert volumen(p["blanco"]) + volumen(p["negro"]) == pytest.approx(250.0 * 198.0 * 3.0, rel=1e-9)
    # El techo del negro, visto desde arriba (+z) y con la y hacia arriba, es el dibujo de los rectangulos agrandados
    # tal cual, sin espejo: pintado celda a celda (cada triangulo del techo ocupa media celda) da la misma imagen.
    agrandados = [(x0 - COMP, y0 - COMP, x1 + COMP, y1 + COMP) for x0, y0, x1, y1 in chb.rectangulos_negros(T, MARGEN)]
    esperada = chb.rasterizar(agrandados, 250.0, 198.0, 10)
    techo = [t for t in p["negro"] if all(abs(v[2] - 3.0) < 1e-9 for v in t)]
    celdas = [(min(v[0] for v in t), 198.0 - max(v[1] for v in t), max(v[0] for v in t), 198.0 - min(v[1] for v in t)) for t in techo]
    desde_arriba = chb.rasterizar(celdas, 250.0, 198.0, 10)
    igual = float(np.mean(desde_arriba == esperada))                        # difieren solo redondeos de medio pixel en bordes
    volteadas = max(float(np.mean(desde_arriba == esperada[::-1])), float(np.mean(desde_arriba == esperada[:, ::-1])))
    print(f"[fase 7d] techo del negro frente a los rectangulos agrandados: {100 * igual:.3f} % igual; volteado, {100 * volteadas:.1f} %")
    assert igual >= 0.999 and volteadas < 0.98, (igual, volteadas)      # volteado solo cambian los marcadores (el ajedrez de 9 x 7 es simetrico)
    assert volumen(p["negro"]) / CAPA == pytest.approx(float((esperada == 0).sum()) / 100.0, rel=5e-3)     # el area, a 10 px/mm
    with pytest.raises(ValueError):
        chb.piezas_stl(T, MARGEN, 0.0, BASE, CAPA)                          # sin compensacion no es cerrada
    with pytest.raises(ValueError):
        chb.piezas_stl(T, MARGEN, 1.7, BASE, CAPA)                          # mas de medio modulo (1.625)
    print(f"[fase 7d] STL del 9x7: blanco {len(p['blanco'])} y negro {len(p['negro'])} triangulos, cerradas; planta "
          f"{ancho:.2f} x {alto:.2f} x {z:.1f} mm; generar tardo {generado['segundos']:.1f} s")


def test_generar_escribe_los_archivos_y_el_detector_lee_la_png(generado) -> None:
    salida, base = generado["salida"], generado["base"]
    assert base == "charuco_9x7_26mm" and generado["leidas"] == 48 and generado["coincidencia"] == 1.0 and generado["ppmm"] == 8
    assert sorted(p.name for p in salida.iterdir()) == sorted([f"{base}_blanco.stl", f"{base}_negro.stl", f"{base}.svg",
                                                               f"{base}.png", "tablero.json"])
    info = json.loads((salida / "tablero.json").read_text(encoding="utf-8"))
    assert info["casillas"] == [9, 7] and info["casilla_mm"] == 26.0 and info["marcador_mm"] == 19.5 and info["medido"] is False
    assert info["muestra"] is False and info["pieza"]["ancho_mm"] == 250.0 and info["pieza"]["alto_mm"] == 198.0
    assert set(info["archivos"]) == {f"{base}_blanco.stl", f"{base}_negro.stl", f"{base}.svg", f"{base}.png"}
    assert info["archivos"][f"{base}.png"] == chb.sha256_archivo(salida / f"{base}.png")
    assert chb.leer_tablero_charuco(salida / "tablero.json") == T
    d = chb.describir_tablero(salida / "tablero.json")
    assert d["medido"] is False and d["esquinas_interiores"] == 48 and len(d["sha256"]) == 64
    png = (salida / f"{base}.png").read_bytes()
    i = png.index(b"pHYs")                                                  # 8 px/mm = 8000 px por metro
    assert int.from_bytes(png[i + 4:i + 8], "big") == 8000 and int.from_bytes(png[i + 8:i + 12], "big") == 8000
    img = cv2.imread(str(salida / f"{base}.png"), cv2.IMREAD_GRAYSCALE)
    assert img.shape == (198 * 8, 250 * 8)
    stl = (salida / f"{base}_negro.stl").read_text(encoding="ascii")
    assert stl.startswith(f"solid {base}_negro\n") and stl.count("endfacet") == len(generado["piezas"]["negro"])
    with pytest.raises(FileExistsError):
        chb.generar(T, MARGEN, COMP, BASE, CAPA, salida)                    # no pisa


def test_main_generar_la_muestra_y_sus_codigos(tmp_path, capsys) -> None:
    m = tmp_path / "muestra"
    assert chb.main(ARGV_GENERAR + ["--muestra", "--salida", str(m)]) == 0
    base = "muestra_charuco_3x3_26mm"
    info = json.loads((m / "tablero.json").read_text(encoding="utf-8"))
    assert info["muestra"] is True and info["casillas"] == [3, 3] and info["esquinas_interiores"] == 4 and info["marcadores"] == 4
    assert info["pieza"]["ancho_mm"] == 94.0 and info["pieza"]["alto_mm"] == 94.0
    assert {p.name for p in m.iterdir()} == {f"{base}_blanco.stl", f"{base}_negro.stl", f"{base}.svg", f"{base}.png", "tablero.json"}
    salida = capsys.readouterr().out
    assert "MUESTRA de 3 x 3 casillas" in salida and "lee en la PNG las 4 esquinas" in salida and "mallas cerradas" in salida
    # `detectar --imagen` sobre su PNG: lee las 4 esquinas de la pieza (codigo 0); en una imagen sin tablero, 1.
    rep = tmp_path / "det.json"
    assert chb.main(["detectar", "--imagen", str(m / f"{base}.png"), "--tablero", str(m / "tablero.json"), "--salida", str(rep),
                     "--timeout", "30"]) == 0
    e = json.loads(rep.read_text(encoding="utf-8"))
    assert e["resultado"]["frames"][0] == {"esquinas": 4, "ids": [0, 1, 2, 3]} and e["resultado"]["cumple"] is True and e["codigo"] == 0
    assert e["tablero"]["muestra"] is True
    gris = tmp_path / "gris.png"
    cv2.imwrite(str(gris), np.full((300, 300), 128, np.uint8))
    assert chb.main(["detectar", "--imagen", str(gris), "--tablero", str(m / "tablero.json"), "--salida", str(tmp_path / "d2.json"),
                     "--timeout", "30"]) == 1
    # No pisa su reporte, y sin imagen que leer no empieza.
    assert chb.main(["detectar", "--imagen", str(gris), "--tablero", str(m / "tablero.json"), "--salida", str(rep), "--timeout", "30"]) == 2
    assert chb.main(["detectar", "--imagen", str(tmp_path / "no.png"), "--tablero", str(m / "tablero.json"),
                     "--salida", str(tmp_path / "d3.json"), "--timeout", "30"]) == 2
    assert chb.main(["detectar", "--tablero", str(m / "tablero.json"), "--salida", str(tmp_path / "d4.json"), "--timeout", "30"]) == 2
    # La carpeta con algo, un tablero de mas de 250 mm y una compensacion que no vale: codigo 2, sin escribir.
    assert chb.main(ARGV_GENERAR + ["--muestra", "--salida", str(m)]) == 2
    grande = [a if a != "26" else "30" for a in ARGV_GENERAR]              # 9 x 30 + 16 = 286 mm
    assert chb.main(grande + ["--salida", str(tmp_path / "grande")]) == 2 and not (tmp_path / "grande").exists()
    assert "la cama admite 250" in capsys.readouterr().out
    gorda = [a if a != "0.40" else "2.0" for a in ARGV_GENERAR]
    assert chb.main(gorda + ["--salida", str(tmp_path / "gorda")]) == 2 and not (tmp_path / "gorda").exists()
    for quitar in ("--timeout", "--comp-mm", "--salida", "--diccionario"):   # argumentos explicitos (principio 7)
        argv = ARGV_GENERAR + ["--salida", str(tmp_path / "x")]
        i = argv.index(quitar)
        with pytest.raises(SystemExit) as exc:
            chb.main(argv[:i] + argv[i + 2:])
        assert exc.value.code == 2


# ----------------------------------------------------------------------------
# El archivo de medidas
# ----------------------------------------------------------------------------

def test_registrar_escribe_el_archivo_de_medidas(generado, tmp_path, capsys) -> None:
    tj = generado["salida"] / "tablero.json"
    ruta = tmp_path / "data" / "tablero_charuco.yaml"
    argv = ["registrar", "--tablero", str(tj), "--medidas", "208.1", "208.0", "208.1", "208.2", "208.0", "--casillas-por-medida", "8",
            "--fuente", "calibrador, prueba", "--salida", str(ruta), "--timeout", "30"]
    assert chb.main(argv) == 0
    assert "casilla medida: 26.01 mm" in capsys.readouterr().out
    t = chb.leer_tablero_charuco(ruta)
    assert t == chb.TableroCharuco((9, 7), 26.01, 19.5, "DICT_4X4_50") and t.board().getSquareLength() == pytest.approx(26.01)
    d = chb.describir_tablero(ruta)
    assert d["medido"] is True and d["casilla_mm"] == 26.01 and d["marcador_mm"] == 19.5
    texto = ruta.read_text(encoding="utf-8")
    assert "lado_mm: 26.01" in texto and "medidas_mm: [208.1, 208, 208.1, 208.2, 208]" in texto and "casillas_por_medida: 8" in texto
    assert "esquinas_horizontales: 8" in texto and "esquinas_verticales: 6" in texto and 'fuente: "calibrador, prueba"' in texto
    assert chb.main(argv) == 2 and ruta.read_text(encoding="utf-8") == texto                # no pisa
    otra = lambda *cambios: [dict(cambios).get(a, a) for a in argv[:-4]] + ["--salida", str(tmp_path / "otra.yaml"), "--timeout", "30"]   # noqa: E731
    assert chb.main(otra(("8", "7"))) == 2                                  # impar: orillas de casillas de distinto color
    assert chb.main(otra(("8", "6"))) == 2                                  # 208 / 6 = 34.7: lejos de la nominal
    assert chb.main(["registrar", "--tablero", str(tj), "--medidas", "208.1", "208.0", "--casillas-por-medida", "8",
                     "--fuente", "x", "--salida", str(tmp_path / "pocas.yaml"), "--timeout", "30"]) == 2     # < 5 medidas
    assert chb.main(["registrar", "--tablero", str(ruta), "--medidas", "208", "208", "208", "208", "208", "--casillas-por-medida", "8",
                     "--fuente", "x", "--salida", str(tmp_path / "deyaml.yaml"), "--timeout", "30"]) == 2    # no es el tablero.json
    assert not (tmp_path / "pocas.yaml").exists() and not (tmp_path / "deyaml.yaml").exists()
    # Un archivo que no cuadra no se lee (principio 7).
    mal = tmp_path / "mal.yaml"
    mal.write_text(texto.replace("lado_mm: 26.01", "lado_mm: 25.00"), encoding="utf-8")
    with pytest.raises(ValueError, match="de sus medidas sale 26.01"):
        chb.leer_tablero_charuco(mal)
    mal.write_text(texto.replace("esquinas_horizontales: 8", "esquinas_horizontales: 9"), encoding="utf-8")
    with pytest.raises(ValueError):
        chb.leer_tablero_charuco(mal)
    mal.write_text("casillas_horizontales: 9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="faltan"):
        chb.leer_tablero_charuco(mal)
    with pytest.raises(FileNotFoundError):
        chb.leer_tablero_charuco(tmp_path / "no_existe.yaml")
    with pytest.raises(ValueError):
        chb.leer_tablero_charuco(generado["salida"] / "charuco_9x7_26mm.svg")
    with pytest.raises(ValueError):
        chb.escribir_tablero_charuco(tmp_path / "v.yaml", T, [208.0] * 5, 8, "", "x")      # sin fecha
    with pytest.raises(ValueError):
        chb.escribir_tablero_charuco(tmp_path / "v.yaml", T, [208.8] * 5, 8, "2026-11-11", "x")    # 26.1 no es el casilla_mm de T


# ----------------------------------------------------------------------------
# La deteccion (puntos 8 y 9)
# ----------------------------------------------------------------------------

VISTAS_8 = [(z, rv) for z in (300.0, 400.0, 500.0) for rv in ((0.0, 0.0, 0.0), (0.0, np.radians(45.0), 0.0), (np.radians(45.0), 0.0, 0.0))]


@pytest.fixture(scope="module")
def vistas_8():
    return [(z, *vista(z, rv)) for z, rv in VISTAS_8]


def test_detectar_charuco_a_30_40_y_50_cm_de_frente_y_a_45_grados(vistas_8) -> None:
    det = chb.detector(T)
    peor, filas = 0.0, []
    for z, img, rv, tv in vistas_8:
        e, ids = chb.detectar_charuco(img, det, T, chb.MIN_ESQUINAS)
        err = np.linalg.norm(e - verdaderas(ids, rv, tv), axis=1)
        buenas = int((err <= 0.1).sum())
        assert len(ids) == 48 and ids.tolist() == list(range(48)) and buenas >= 40, (z, rv, len(ids), buenas, err.max())
        peor = max(peor, float(err.max()))
        filas.append(f"z {z:.0f} rv {np.degrees(rv).round().astype(int).tolist()}: {buenas}/48, max {err.max():.3f}")
    print("[fase 7d] detectar_charuco, 1280x960 con la K y la distorsion de gs1: " + "; ".join(filas) + f"; peor {peor:.3f} px")


def test_7c4_el_detector_lee_los_bits_con_8_pixeles_por_celda(vistas_8) -> None:
    """Fase 7c4, criterio 1: `detector` pone `perspectiveRemovePixelPerCell` = 8 (OpenCV trae 4), y en
    las vistas sinteticas de la 7d da las mismas esquinas que con 4, a <= 0.01 px una a una
    (obtenido: 0.0 px: las esquinas salen de `cornerSubPix`, no de la lectura de bits)."""
    assert chb.PIXELES_POR_CELDA == 8 and cv2.aruco.DetectorParameters().perspectiveRemovePixelPerCell == 4
    det8 = chb.detector(T)
    assert det8.getDetectorParameters().perspectiveRemovePixelPerCell == 8
    dp4 = det8.getDetectorParameters()
    dp4.perspectiveRemovePixelPerCell = 4
    det4 = cv2.aruco.CharucoDetector(T.board(), det8.getCharucoParameters(), dp4, det8.getRefineParameters())
    peor, comunes = 0.0, 0
    for z, img, _rv, _tv in vistas_8:
        a, b = chb.detectar_charuco(img, det4, T, chb.MIN_ESQUINAS), chb.detectar_charuco(img, det8, T, chb.MIN_ESQUINAS)
        assert a is not None and b is not None and a[1].tolist() == b[1].tolist(), z
        comunes += len(b[1])
        peor = max(peor, float(np.abs(a[0] - b[0]).max()))
    assert comunes == 9 * 48 and peor <= 0.01, peor
    print(f"[fase 7c4] detector con 8 px por celda frente a 4, vistas de la 7d: {comunes} esquinas, peor {peor:.4f} px")


def test_detectboard_va_medio_pixel_corrido_y_detectar_charuco_lo_corrige(vistas_8) -> None:
    """Lo medido en la fase (OpenCV 4.11): `detectBoard` da las esquinas +0.5 px en x y en y respecto a
    `projectPoints` y `cornerSubPix`. Si una version nueva de OpenCV lo cambia, esta prueba lo dice y hay que
    revisar `CONVENCION_PX`."""
    det = chb.detector(T)
    medias, crudas_buenas = [], []
    for _z, img, rv, tv in vistas_8:
        c, ids, _mc, _mi = det.detectBoard(img)
        ids = ids.flatten()
        d = c.reshape(-1, 2) - verdaderas(ids, rv, tv)
        medias.append(d.mean(axis=0))
        crudas_buenas.append(int((np.linalg.norm(d - chb.CONVENCION_PX, axis=1) <= 0.1).sum()))
    media = np.mean(medias, axis=0)
    assert chb.CONVENCION_PX == 0.5 and media == pytest.approx([0.5, 0.5], abs=0.06), media
    # En la imagen que dibuja OpenCV, lo mismo: la esquina entre los pixeles 339 y 340 (centro 339.5) sale en 340.
    img = chb.imagen(T, MARGEN, 10)
    c, ids, _mc, _mi = det.detectBoard(img)
    esperadas = chb.puntos_objeto(T, ids.flatten())[:, :2] * 10 + 80 - 0.5
    assert (c.reshape(-1, 2) - esperadas).mean(axis=0) == pytest.approx([0.5, 0.5], abs=0.02)
    e, i2 = chb.detectar_charuco(img, det, T, 12)
    assert np.abs(e - (chb.puntos_objeto(T, i2)[:, :2] * 10 + 80 - 0.5)).max() < 0.05
    # Sin el refinado de `detectar_charuco`, solo con el medio pixel restado, a 45 grados no llegan a 40 de 48.
    print(f"[fase 7d] detectBoard - verdad: media {media.round(3).tolist()} px; con solo restar 0.5, esquinas a <= 0.1 px por "
          f"vista: {crudas_buenas} de 48")
    assert min(crudas_buenas) < 40


def test_el_tiempo_por_frame_fija_la_escala_de_la_vista_previa(vistas_8) -> None:
    """La mas rapida que lea >= 40 esquinas a 50 cm con p95 <= 40 ms: 0.5. Con ruido (sd 3 niveles de gris y
    contraste 0.8, mas parecido a la camara), que es cuando la deteccion a escala 1 se alarga."""
    det = chb.detector(T)
    rng = np.random.default_rng(0)
    ms: dict = {1.0: [], 0.5: []}
    leidas: dict = {1.0: [], 0.5: []}
    for z, limpia, rv, tv in vistas_8:
        img = np.clip(limpia.astype(np.float64) * 0.8 + 20.0 + rng.normal(0.0, 3.0, limpia.shape), 0, 255).astype(np.uint8)
        for escala in (1.0, 0.5):
            tiempos, r = [], None
            for _ in range(3):
                t0 = time.perf_counter()
                r = chb.detectar_charuco(img, det, T, chb.MIN_ESQUINAS, escala=escala)
                tiempos.append((time.perf_counter() - t0) * 1000.0)
            ms[escala].append(min(tiempos))                                 # el mejor de 3: no depende de la carga de la maquina
            assert r is not None
            err = np.linalg.norm(r[0] - verdaderas(r[1], rv, tv), axis=1)
            assert float(np.sqrt(np.mean(err ** 2))) < 0.12, (z, escala)    # con ruido, RMS <= ~0.07 px a las dos escalas
            if z == 500.0:
                leidas[escala].append(len(r[1]))
    p95 = {e: float(np.percentile(v, 95)) for e, v in ms.items()}
    print(f"[fase 7d] detectar_charuco con ruido, 1280x960: escala 1 p95 {p95[1.0]:.1f} ms (mediana {np.median(ms[1.0]):.1f}), a 50 cm lee "
          f"{leidas[1.0]}; escala 0.5 p95 {p95[0.5]:.1f} ms (mediana {np.median(ms[0.5]):.1f}), a 50 cm lee {leidas[0.5]}")
    assert min(leidas[0.5]) >= 40 and p95[0.5] <= 40.0                      # la escala de la vista previa: 0.5


def _marcadores_enteros(rv, tv, margen: float = 6.0) -> set[int]:
    """Los IDs de los marcadores del tablero que caen enteros dentro de la imagen (con `margen` px)."""
    b = T.board()
    dentro = set()
    for mid, obj in zip(np.asarray(b.getIds()).flatten().tolist(), b.getObjPoints()):
        p = cv2.projectPoints(np.asarray(obj, dtype=np.float64), rv, tv, K, DIST)[0].reshape(-1, 2)
        if (p[:, 0] > margen).all() and (p[:, 0] < SHAPE[0] - 1 - margen).all() and (p[:, 1] > margen).all() and (p[:, 1] < SHAPE[1] - 1 - margen).all():
            dentro.add(int(mid))
    return dentro


def _marcadores_de_la_esquina(i: int) -> set[int]:
    """Los dos marcadores que rodean a la esquina interior `i`: los de las dos casillas blancas de las cuatro que la tocan."""
    b = T.board()
    en_casilla = {}
    for mid, obj in zip(np.asarray(b.getIds()).flatten().tolist(), b.getObjPoints()):
        c = np.asarray(obj).reshape(4, 3).mean(axis=0)
        en_casilla[(int(c[0] // T.casilla_mm), int(c[1] // T.casilla_mm))] = int(mid)
    cx, cy = i % (T.casillas[0] - 1), i // (T.casillas[0] - 1)
    out = {en_casilla[q] for q in ((cx, cy), (cx + 1, cy), (cx, cy + 1), (cx + 1, cy + 1)) if q in en_casilla}
    assert len(out) == 2
    return out


def test_con_el_tablero_en_parte_fuera_y_con_las_esquinas_en_linea() -> None:
    det = chb.detector(T)
    # El centro del tablero a un 10 % de su ancho del borde derecho: un 40 % queda fuera de la imagen.
    ancho_px = T.ancho_mm * K[0, 0] / 400.0
    img, rv, tv = vista(400.0, objetivo=(SHAPE[0] - 0.1 * ancho_px, 480.0))
    todas = verdaderas(np.arange(48), rv, tv)
    en_imagen = {int(i) for i in np.flatnonzero((todas[:, 0] > 5) & (todas[:, 0] < SHAPE[0] - 6) & (todas[:, 1] > 5) & (todas[:, 1] < SHAPE[1] - 6))}
    enteros = _marcadores_enteros(rv, tv)
    con_vecinos = {i for i in en_imagen if _marcadores_de_la_esquina(i) <= enteros}
    e, ids = chb.detectar_charuco(img, det, T, 4)
    leidas = set(ids.tolist())
    assert 20 <= len(con_vecinos) < len(en_imagen) < 48                     # hay esquinas dentro sin sus dos marcadores
    assert con_vecinos <= leidas <= en_imagen, (sorted(con_vecinos - leidas), sorted(leidas - en_imagen))
    assert np.linalg.norm(e - todas[ids], axis=1).max() <= 0.1
    assert chb.detectar_charuco(img, det, T, len(leidas) + 1) is None       # menos de las pedidas
    print(f"[fase 7d] con el 40 % del tablero fuera: {len(en_imagen)} esquinas en la imagen, {len(con_vecinos)} con sus dos "
          f"marcadores, leidas {len(leidas)}")
    # Solo dos columnas de casillas a la vista: las 6 esquinas de la linea entre ellas, en linea -> None.
    img2, rv2, tv2 = vista(400.0)
    limites = verdaderas(np.array([3, 5]), rv2, tv2)                        # las columnas de esquinas 3 y 5 (x = 4 y 6 casillas)
    x0, x1 = int(limites[0, 0]) + 3, int(limites[1, 0]) - 3
    tapada = np.full_like(img2, 128)
    tapada[:, x0:x1] = img2[:, x0:x1]
    c, ids_crudos, _mc, _mi = det.detectBoard(tapada)
    assert ids_crudos is not None and sorted(ids_crudos.flatten().tolist()) == [4, 12, 20, 28, 36, 44]     # la columna 4
    assert T.board().checkCharucoCornersCollinear(ids_crudos) is True
    assert chb.detectar_charuco(tapada, det, T, 4) is None
    assert chb.detectar_charuco(np.full((960, 1280), 128, np.uint8), det, T, 1) is None                    # sin tablero
    with pytest.raises(ValueError):
        chb.detectar_charuco(img2, det, T, 4, escala=1.5)


def test_la_referencia_y_el_tablero_no_se_cruzan() -> None:
    """Punto 9: la referencia (ID 100, DICT_ARUCO_MIP_36h12, 100 mm) en el mismo plano, al lado del tablero."""
    rv = np.array([0.15, -0.2, 0.05])
    tv = ts.pose_charuco_hacia(T, K, rv, (520.0, 480.0), 600.0)
    solo = ts.renderizar_charuco(T, K, rv, tv, SHAPE, DIST)
    lado, borde, ppmm = 100.0, 15.0, 4.0
    plano = np.full((int((lado + 2 * borde) * ppmm),) * 2, 255, np.uint8)
    b = int(borde * ppmm)
    plano[b:b + int(lado * ppmm), b:b + int(lado * ppmm)] = cv2.aruco.generateImageMarker(get_dictionary("DICT_ARUCO_MIP_36h12"), 100, int(lado * ppmm))
    plano = cv2.GaussianBlur(plano, (0, 0), 0.4 * ppmm)
    # La esquina del plano de la referencia, en mm del tablero: a su derecha, a 10 mm del margen.
    x0, y0 = T.ancho_mm + MARGEN + 10.0, 20.0
    juntos = ts.renderizar_plano(plano, (-x0 * ppmm, -y0 * ppmm), ppmm, K, rv, tv, SHAPE, DIST, sobre=solo)
    assert not np.array_equal(juntos, solo)
    det = chb.detector(T)
    e1, i1 = chb.detectar_charuco(solo, det, T, 12)
    e2, i2 = chb.detectar_charuco(juntos, det, T, 12)
    assert len(i1) == 48 and np.array_equal(i1, i2) and np.abs(e1 - e2).max() <= 0.02, np.abs(e1 - e2).max()
    _cc, _ci, _mc, mi = det.detectBoard(juntos)
    assert sorted(mi.flatten().tolist()) == list(range(31))                 # el detector del tablero, ningun marcador de mas
    # El tracker, con la referencia en su lista blanca: una sola deteccion, la del ID 100, en su sitio.
    cfg = profiles.load(PROFILES_DIR / "tracker_config_gs1.yaml")
    del_perfil = create_detector(cfg["markers"])
    corners, ids = detect(del_perfil, juntos, {100})
    assert ids is not None and ids.flatten().tolist() == [100]
    lado_mod = lado / 8.0
    esquinas_mm = np.array([[x0 + borde, y0 + borde, 0.0], [x0 + borde + lado, y0 + borde, 0.0],
                            [x0 + borde + lado, y0 + borde + lado, 0.0], [x0 + borde, y0 + borde + lado, 0.0]])
    verd = cv2.projectPoints(esquinas_mm, rv, tv, K, DIST)[0].reshape(-1, 2)
    assert np.linalg.norm(corners[0].reshape(-1, 2) - verd, axis=1).max() < 1.0 and lado_mod == 12.5
    crudos = del_perfil.detectMarkers(juntos)[1].flatten().tolist()
    print(f"[fase 7d] con la referencia en la imagen: las mismas 48 esquinas (dif max {np.abs(e1 - e2).max():.4f} px); el tracker, con "
          f"su lista blanca, ve [100]; sin ella, el detector del perfil lee {len(crudos)} IDs de 36h12: {sorted(crudos)} (B39)")


def test_criterio_9_el_detector_del_perfil_solo_ve_el_id_100() -> None:
    """El punto 9 del criterio de la fase 7d, tal como lo dice el plan. Con la tasa 0.6 no se cumplia (medido el
    2026-11-11: sobre 60 vistas del tablero solo, 646 IDs fantasma y el 100 en una de ellas; B39) y fue un fallo
    esperado y estricto (P67). Desde el cierre de la 7d2 (2026-11-12, P84) los perfiles fijan
    `error_correction_rate: 0.3` y se cumple."""
    cfg = profiles.load(PROFILES_DIR / "tracker_config_gs1.yaml")
    del_perfil = create_detector(cfg["markers"])
    fantasmas = 0
    for z, rv in VISTAS_8[:3]:
        img, _rv, _tv = vista(z, rv)
        ids = del_perfil.detectMarkers(img)[1]
        fantasmas += 0 if ids is None else len(ids)
    assert fantasmas == 0, f"{fantasmas} IDs de 36h12 leidos en 3 vistas del tablero ChArUco solo"


def test_puntos_objeto_es_lo_que_da_matchimagepoints() -> None:
    ids = np.array([0, 7, 8, 20, 47])
    obj = chb.puntos_objeto(T, ids)
    assert obj.dtype == np.float32 and obj.tolist() == [[26.0, 26.0, 0.0], [208.0, 26.0, 0.0], [26.0, 52.0, 0.0], [130.0, 78.0, 0.0], [208.0, 156.0, 0.0]]
    esquinas = np.arange(10, dtype=np.float32).reshape(5, 1, 2)
    o2, i2 = T.board().matchImagePoints(esquinas, ids.astype(np.int32).reshape(-1, 1))
    assert np.array_equal(o2.reshape(-1, 3), obj) and np.array_equal(i2.reshape(-1, 2), esquinas.reshape(-1, 2))
    medido = chb.TableroCharuco((9, 7), 26.01, 19.5, "DICT_4X4_50")         # la casilla medida escala los puntos
    assert chb.puntos_objeto(medido, [47])[0].tolist() == pytest.approx([208.08, 156.06, 0.0], abs=1e-4)
    with pytest.raises(ValueError):
        chb.puntos_objeto(T, [48])


def test_esquinas_charuco_de_posicion(tmp_path) -> None:
    K6 = ts.K_de(600.0, 600.0, 320.0, 240.0)
    rv = np.array([0.2, -0.25, 0.1])
    tv = ts.pose_charuco_hacia(T, K6, rv, (330.0, 235.0), 420.0)
    img = ts.renderizar_charuco(T, K6, rv, tv, (640, 480), None)
    movida = ts.renderizar_charuco(T, K6, rv, tv + np.array([420.0 / 600.0, 0.0, 0.0]), (640, 480), None)       # 1 px
    parcial = ts.renderizar_charuco(T, K6, rv, ts.pose_charuco_hacia(T, K6, rv, (560.0, 235.0), 420.0), (640, 480), None)
    det = chb.detector(T)

    def carpeta(nombre: str, frames) -> object:
        d = tmp_path / nombre
        d.mkdir()
        for k, f in enumerate(frames):
            cv2.imwrite(str(d / f"frame_{k:05d}.png"), f)
        return d

    r = chb.esquinas_charuco_de_posicion(carpeta("T01_gs1_frames", [img, img, img]), T, det, 5, 0.3, 12)
    assert r["motivo"] is None and r["n_frames"] == 3 and r["n_detectados"] == 3 and r["movimiento_px"] == 0.0 and r["shape"] == (640, 480)
    assert r["esquinas"].shape == (48, 1, 2) and r["esquinas"].dtype == np.float32 and r["ids"].tolist() == list(range(48))
    verd = cv2.projectPoints(chb.puntos_objeto(T, r["ids"]).astype(np.float64), rv, tv, K6, np.zeros(5))[0].reshape(-1, 2)
    assert np.linalg.norm(r["esquinas"].reshape(-1, 2) - verd, axis=1).max() <= 0.1
    # Solo los ultimos n_frames; un frame movido 1 px: no estaba quieto.
    assert chb.esquinas_charuco_de_posicion(tmp_path / "T01_gs1_frames", T, det, 2, 0.3, 12)["n_frames"] == 2
    m = chb.esquinas_charuco_de_posicion(carpeta("T02_gs1_frames", [img, movida, img]), T, det, 5, 0.3, 12)
    assert m["esquinas"] is None and "no estaba quieto" in m["motivo"] and 0.3 < m["movimiento_px"] < 1.0
    # Un frame con el tablero en parte fuera: valen las esquinas comunes a todos.
    c = chb.esquinas_charuco_de_posicion(carpeta("T03_gs1_frames", [parcial, parcial]), T, det, 5, 0.3, 12)
    assert c["motivo"] is None and 12 <= len(c["ids"]) < 48 and c["n_comunes"] == len(c["ids"]) == len(c["esquinas"])
    assert chb.esquinas_charuco_de_posicion(tmp_path / "T03_gs1_frames", T, det, 5, 0.3, 47)["motivo"] is not None      # piden mas de las que hay
    # Sin tablero en bastantes frames, sin frames, y con un solo frame (vale con 1).
    gris = np.full((480, 640), 128, np.uint8)
    s = chb.esquinas_charuco_de_posicion(carpeta("T04_gs1_frames", [img, gris, gris]), T, det, 5, 0.3, 12)
    assert s["esquinas"] is None and "en 1 de 3 frames" in s["motivo"]
    assert "sin frames" in chb.esquinas_charuco_de_posicion(tmp_path / "no_hay", T, det, 5, 0.3, 12)["motivo"]
    u = chb.esquinas_charuco_de_posicion(carpeta("T05_gs1_frames", [img]), T, det, 5, 0.3, 12)
    assert u["motivo"] is None and u["movimiento_px"] is None and len(u["ids"]) == 48
    with pytest.raises(ValueError, match="mismo tamano"):
        chb.esquinas_charuco_de_posicion(carpeta("T06_gs1_frames", [img, gris[:240]]), T, det, 5, 0.3, 12)


# ----------------------------------------------------------------------------
# `detectar` con una camara falsa (la prueba de la muestra impresa)
# ----------------------------------------------------------------------------

class CamFalsa:
    """Un backend falso: `read()` da el frame cada ~4 ms."""

    def __init__(self, frame, falla_al_abrir: bool = False) -> None:
        self.frame, self.falla_al_abrir = frame, falla_al_abrir
        self.abierta = self.cerrada = False

    def open(self) -> None:
        if self.falla_al_abrir:
            raise RuntimeError("No se pudo abrir webcam source=1")
        self.abierta = True

    def read(self):
        time.sleep(0.004)
        return self.frame, None, time.time()

    def close(self) -> None:
        self.cerrada = True


def test_detectar_con_camara_falsa_la_muestra(tmp_path, monkeypatch, sin_ventanas) -> None:
    muestra = chb.TableroCharuco((3, 3), 26.0, 19.5, "DICT_4X4_50")
    chb.generar(muestra, MARGEN, COMP, BASE, CAPA, tmp_path / "m", muestra=True)
    K6 = ts.K_de(600.0, 600.0, 320.0, 240.0)
    rv = np.array([0.1, 0.2, 0.0])
    frame = ts.a_bgr(ts.renderizar_charuco(muestra, K6, rv, ts.pose_charuco_hacia(muestra, K6, rv, (320.0, 240.0), 250.0), (640, 480), None))
    perfil = tmp_path / "perfil.yaml"
    perfil.write_text("camera:\n  camera_type: webcam\n  source: 1\n  width: 640\n  height: 480\n  fps: 90\n"
                      "markers:\n  dictionary: DICT_ARUCO_MIP_36h12\n  list:\n  - {id: 100, name: Reference, size_mm: 98.6}\n", encoding="utf-8")
    cam = CamFalsa(frame)
    monkeypatch.setattr(chb, "create_backend", lambda cfg: cam)
    rep = tmp_path / "det.json"
    argv = ["detectar", "--config", f"gs1={perfil}", "--tablero", str(tmp_path / "m" / "tablero.json"), "--segundos", "0.6",
            "--salida", str(rep), "--timeout", "30"]
    assert chb.main(argv) == 0
    e = json.loads(rep.read_text(encoding="utf-8"))
    r = e["resultado"]
    assert cam.abierta and cam.cerrada and sin_ventanas["namedWindow"] == 1
    assert r["fin"] == "tiempo" and r["esperadas"] == 4 and r["n_frames"] == len(r["frames"]) >= 5 and r["fraccion"] == 1.0 and r["cumple"] is True
    assert all(f["esquinas"] == 4 and f["ids"] == [0, 1, 2, 3] for f in r["frames"]) and e["camara"] == "gs1" and e["codigo"] == 0
    assert sin_ventanas["imshow"] == len(r["frames"]) and sin_ventanas["destroyAllWindows"] == 1
    # La pieza que no se lee (aqui, un frame gris): codigo 1. La camara que no abre: 2, sin ventana.
    cam2 = CamFalsa(np.full((480, 640, 3), 128, np.uint8))
    monkeypatch.setattr(chb, "create_backend", lambda cfg: cam2)
    assert chb.main(argv[:-4] + ["--salida", str(tmp_path / "d2.json"), "--timeout", "30"]) == 1 and cam2.cerrada
    assert json.loads((tmp_path / "d2.json").read_text(encoding="utf-8"))["resultado"]["completos"] == 0
    cam3 = CamFalsa(frame, falla_al_abrir=True)
    monkeypatch.setattr(chb, "create_backend", lambda cfg: cam3)
    antes = sin_ventanas["namedWindow"]
    assert chb.main(argv[:-4] + ["--salida", str(tmp_path / "d3.json"), "--timeout", "30"]) == 2 and sin_ventanas["namedWindow"] == antes
    assert "no se pudo abrir la camara" in json.loads((tmp_path / "d3.json").read_text(encoding="utf-8"))["error"]
    # Con camara hacen falta los segundos, y menos que el tope; --config e --imagen a la vez, no.
    for mal in (argv[:5] + ["--salida", str(tmp_path / "d4.json"), "--timeout", "30"],
                argv[:5] + ["--segundos", "40", "--salida", str(tmp_path / "d4.json"), "--timeout", "30"],
                argv + ["--imagen", "x.png"]):
        with pytest.raises(SystemExit) as exc:
            chb.main(mal)
        assert exc.value.code == 2
    # resumen_deteccion: el 90 % justo cumple; menos, no.
    assert chb.resumen_deteccion([4] * 9 + [3], 4)["cumple"] is True and chb.resumen_deteccion([4] * 8 + [3, 0], 4)["cumple"] is False
    assert chb.resumen_deteccion([], 4) == {"n_frames": 0, "esperadas": 4, "completos": 0, "fraccion": 0.0, "con_alguna": 0,
                                            "mediana": None, "minimo": None, "cumple": False, "criterio_fraccion": 0.9}


def test_el_modulo_importa_camera_antes_que_cv2() -> None:
    fuente = (CODIGO_DIR / "calibration" / "charuco_board.py").read_text(encoding="utf-8")
    assert fuente.index("from calibration import calibrate_camera") < fuente.index("import cv2")       # ese importa camera.uvc
