"""La sección §9 de docs/ARCHITECTURE.md es fiel al código (meta 004 · Cómo funciona el tracker, fase 1).

Lo que se comprueba, sin cámara ni Node:

- Toda referencia a código de §9 (entre `<!-- como-funciona:inicio -->` y
  `<!-- como-funciona:fin -->`), escrita como `<ruta>.py` o `<ruta>.py:<Símbolo>`
  con la ruta relativa a codigo/, existe en el árbol vivo (fuera de historico/) y
  el símbolo está definido. Se mira con `ast`, sin importar: así vale también
  para slicer/*.py, que importa `slicer`. Un `.yaml`/`.yml` solo tiene que existir.
- Cada caja `ID["…"]` del Mermaid de §9.1 lleva al menos una referencia.
- El sha256 del Mermaid de §9.1 es el que se guardó al exportar la imagen
  (`docs/img/004/mapa_proyecto.sha256`, lo escribe diagnostics/export_map.py) y la
  imagen existe y es un SVG que se lee (P9): si alguien cambia el Mermaid y no
  reexporta, falla.
- docs/img/004/ pesa menos de 200 KB (P6); el índice nombra §9.1–§9.5; ninguna
  línea de ARCHITECTURE.md pasa de 2 000 caracteres (CLAUDE.md §3).
- (fase 2) El bloque de §9.3 entre `<!-- ejemplo:inicio -->` y `<!-- ejemplo:fin -->`
  es la salida de `diagnostics/explain_pose.py` sobre gs1, frame 480, con 98.6 mm
  (`format_markdown(explain_frame(...))`), y la figura
  `docs/img/004/marker0_gs1_frame_00480.png` existe, se lee y es el recorte de
  `draw_example` (320×320).
- diagnostics/export_map.py, de punta a punta con un `mmdc` falso: le pasa la
  configuración de Mermaid con `-c`, quita el `@font-face` incrustado y no
  escribe un SVG de 200 KB o más.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from diagnostics import explain_pose, export_map

from .conftest import CODIGO_DIR, PROFILES_DIR, TESTS_DATA_DIR

ROOT = CODIGO_DIR.parent
ARCH = ROOT / "docs" / "ARCHITECTURE.md"
IMG_DIR = ROOT / "docs" / "img" / "004"
MAP_SVG = IMG_DIR / "mapa_proyecto.svg"
MAP_SHA = IMG_DIR / "mapa_proyecto.sha256"
EXAMPLE_PNG = IMG_DIR / "marker0_gs1_frame_00480.png"
EXAMPLE_CROP_PX = 320
SECTION_START = "<!-- como-funciona:inicio -->"
SECTION_END = "<!-- como-funciona:fin -->"
EXAMPLE_START = "<!-- ejemplo:inicio -->"
EXAMPLE_END = "<!-- ejemplo:fin -->"
MIN_REFS = 15
MAX_IMG_BYTES = 200 * 1024
MAX_LINE_CHARS = 2000

# `<ruta>.py[:Símbolo]` o `<ruta>.yaml|yml`, con o sin comillas invertidas; la ruta
# empieza en una palabra (no a mitad de otra ruta) y la extensión no sigue en otra palabra.
_REF_RE = re.compile(
    r"(?<![\w/.<])((?:[A-Za-z_]\w*/)*[A-Za-z_]\w*\.(?:py|yaml|yml))(?![\w])"
    r"(?::([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?))?")
_NODE_RE = re.compile(r'^\s*([A-Za-z_]\w*)\["(.*?)"\]\s*$')


def _doc_text() -> str:
    return ARCH.read_text(encoding="utf-8")


def section_text(doc_text: str) -> str:
    """§9: el texto entre las marcas `como-funciona` (falla si faltan)."""
    i = doc_text.find(SECTION_START)
    j = doc_text.find(SECTION_END)
    assert i >= 0 and j > i, f"faltan las marcas {SECTION_START} … {SECTION_END}"
    return doc_text[i + len(SECTION_START):j]


def find_code_refs(text: str) -> list[tuple[str, str | None]]:
    """Las referencias (ruta relativa a codigo/, símbolo o None) que hay en `text`."""
    return [(m.group(1), m.group(2)) for m in _REF_RE.finditer(text)]


def symbol_defined(path: Path, symbol: str) -> bool:
    """Por `ast`: función o clase de primer nivel, `Clase.método` (o atributo de
    clase), o nombre asignado en el módulo."""
    if not path.is_file():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def names(body) -> dict[str, ast.AST]:
        out: dict[str, ast.AST] = {}
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out[node.name] = node
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        out[t.id] = node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                out[node.target.id] = node
        return out

    head, _, rest = symbol.partition(".")
    node = names(tree.body).get(head)
    if node is None:
        return False
    if not rest:
        return True
    return isinstance(node, ast.ClassDef) and rest in names(node.body)


def ref_exists(rel: str, symbol: str | None) -> bool:
    """La referencia apunta al árbol vivo: el archivo existe fuera de historico/ y,
    si trae símbolo (solo .py), está definido."""
    if rel.startswith("historico/"):
        return False
    path = CODIGO_DIR / rel
    if not path.is_file():
        return False
    if symbol is None:
        return True
    return path.suffix == ".py" and symbol_defined(path, symbol)


def mermaid_nodes(text: str) -> list[str]:
    """Las etiquetas de las cajas `ID["…"]` del Mermaid de §9.1 (sin los títulos
    de los `subgraph`)."""
    source = export_map.extract_mermaid(text)
    labels = []
    for line in source.splitlines():
        if line.strip().startswith("subgraph"):
            continue
        m = _NODE_RE.match(line)
        if m:
            labels.append(m.group(2))
    return labels


# ---------------------------------------------------------------- fidelidad de §9

def test_las_referencias_de_la_seccion_existen():
    refs = find_code_refs(section_text(_doc_text()))
    missing = sorted({f"{r}:{s}" if s else r for r, s in refs if not ref_exists(r, s)})
    assert missing == [], f"referencias de §9 que no existen en HEAD: {missing}"
    assert len(refs) >= MIN_REFS, f"§9 tiene {len(refs)} referencias; se esperan al menos {MIN_REFS}"


def test_cada_caja_del_mapa_tiene_su_referencia():
    labels = mermaid_nodes(_doc_text())
    assert len(labels) >= 15, f"el mapa tiene {len(labels)} cajas"
    sin_ref = [lab for lab in labels if not find_code_refs(lab)]
    assert sin_ref == [], f"cajas sin archivo ni función: {sin_ref}"


def test_el_verificador_falla_con_un_nombre_inventado():
    assert not symbol_defined(CODIGO_DIR / "vision" / "pose.py", "no_existe")
    assert not ref_exists("vision/pose.py", "no_existe")
    assert not ref_exists("vision/no_existe.py", None)
    assert not ref_exists("transport/igtl.py", "IgtlSender.no_existe")
    assert not ref_exists("tracker.py", "main.algo")          # main no es una clase
    assert not ref_exists("profiles/tracker_config_gs1.yaml", "algo")   # un .yaml no lleva símbolo
    # Y acepta lo que sí existe (control positivo, por si el verificador lo rechaza todo).
    assert ref_exists("vision/pose.py", "estimate_single_pose")
    assert ref_exists("transport/igtl.py", "IgtlSender.wait_for_client")
    assert ref_exists("profiles/__init__.py", "load")
    assert ref_exists("data/intrinsecos_gs1_1280x960.yml", None)
    assert find_code_refs("ver `vision/pose.py:estimate_single_pose` y tracker.py") == [
        ("vision/pose.py", "estimate_single_pose"), ("tracker.py", None)]
    assert find_code_refs("`<ruta>.py:<Símbolo>`, foo.pyigtl, camera.calibration_file") == []


# ---------------------------------------------------------------- la imagen del mapa

def test_el_sha_del_mapa_es_el_de_la_imagen_exportada():
    source = export_map.extract_mermaid(_doc_text())
    assert MAP_SHA.is_file(), (f"falta {MAP_SHA.relative_to(ROOT)}: exporta el mapa con "
                               f"python -m diagnostics.export_map (docs/ARCHITECTURE.md §9.1)")
    sha, tool = export_map.read_sha_file(MAP_SHA)
    assert tool.startswith(export_map.TOOL + "@"), tool
    assert sha == export_map.mermaid_sha256(source), (
        "el Mermaid de §9.1 cambió y la imagen no se reexportó (python -m diagnostics.export_map)")
    assert MAP_SVG.is_file(), f"falta {MAP_SVG.relative_to(ROOT)}"
    assert export_map.is_svg(MAP_SVG.read_bytes()), f"{MAP_SVG.relative_to(ROOT)} no es un SVG"


def test_is_svg_reconoce_un_svg_y_rechaza_un_png():
    assert export_map.is_svg(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    assert export_map.is_svg(b'\xef\xbb\xbf<?xml version="1.0"?>\n<svg></svg>')
    assert not export_map.is_svg(b"\x89PNG\r\n\x1a\nfalso")
    assert not export_map.is_svg(b"<?xml version='1.0'?><html></html>")
    assert not export_map.is_svg(b"")


def test_el_sha_ignora_crlf_y_cambia_con_una_etiqueta():
    src = 'flowchart TD\n    A["uno"] --> B["dos"]\n'
    sha = export_map.mermaid_sha256(src)
    assert export_map.mermaid_sha256(src.replace("\n", "\r\n")) == sha
    assert export_map.mermaid_sha256(src.replace("\n", "  \n")) == sha
    assert export_map.mermaid_sha256(src.replace("dos", "tres")) != sha


def test_las_imagenes_pesan_menos_de_200_kb():
    total = sum(p.stat().st_size for p in IMG_DIR.glob("*") if p.is_file()) if IMG_DIR.is_dir() else 0
    assert total < MAX_IMG_BYTES, f"docs/img/004/ pesa {total} bytes"


# ---------------------------------------------------------------- el ejemplo de §9.3 (fase 2)

def example_block(doc_text: str) -> str:
    """El bloque generado de §9.3, entre las marcas `ejemplo` (falla si faltan)."""
    i = doc_text.find(EXAMPLE_START)
    j = doc_text.find(EXAMPLE_END)
    assert i >= 0 and j > i, f"faltan las marcas {EXAMPLE_START} … {EXAMPLE_END}"
    return doc_text[i + len(EXAMPLE_START):j]


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _example_result() -> dict:
    return explain_pose.explain_frame(TESTS_DATA_DIR / "marker0_gs1.npz",
                                      TESTS_DATA_DIR / "marker0_gs1_frames", 480,
                                      PROFILES_DIR / "tracker_config_gs1.yaml", alt_size_mm=98.6)


def test_el_bloque_del_ejemplo_es_la_salida_del_script():
    block = _lf(example_block(_doc_text())).strip("\n")
    want = _lf(explain_pose.format_markdown(_example_result())).strip("\n")
    assert block == want, ("el bloque de §9.3 no es la salida de diagnostics/explain_pose.py sobre gs1, frame 480: "
                           "regenerarlo con python -m diagnostics.explain_pose (ver su docstring)")
    assert block in section_text(_doc_text())                     # dentro de §9, con sus referencias


def test_la_figura_del_ejemplo_existe_y_es_el_recorte():
    assert EXAMPLE_PNG.is_file(), (f"falta {EXAMPLE_PNG.relative_to(ROOT)}: python -m diagnostics.explain_pose "
                                   f"... --output-image (docs/ARCHITECTURE.md §9.3)")
    img = cv2.imread(str(EXAMPLE_PNG), cv2.IMREAD_UNCHANGED)
    assert img is not None and img.shape == (EXAMPLE_CROP_PX, EXAMPLE_CROP_PX, 3), getattr(img, "shape", None)
    r = _example_result()
    gray = cv2.imread(str(TESTS_DATA_DIR / "marker0_gs1_frames" / r["png"]), cv2.IMREAD_UNCHANGED)
    want = explain_pose.draw_example(gray, r, r["intrinsics"]["K"], r["intrinsics"]["dist"], EXAMPLE_CROP_PX)
    # El mismo recorte del mismo frame: los píxeles sin dibujo coinciden (el trazo puede cambiar con OpenCV).
    same = np.mean(img == want)
    assert same > 0.95, f"solo el {same:.1%} de los píxeles coincide con draw_example"
    assert "img/004/marker0_gs1_frame_00480.png" in section_text(_doc_text())


# ---------------------------------------------------------------- el documento

def test_el_indice_nombra_la_seccion_9():
    text = _doc_text()
    i = text.find("## Índice")
    j = text.find("## 1. ")
    assert 0 <= i < j, "falta el índice antes de §1"
    indice = text[i:j]
    for sub in ("§9.1", "§9.2", "§9.3", "§9.4", "§9.5"):
        assert sub in indice, sub
    for n in range(1, 10):
        assert f"§{n} " in indice, f"§{n}"


def test_ninguna_linea_pasa_de_2000_caracteres():
    largas = [(n, len(ln)) for n, ln in enumerate(_doc_text().splitlines(), 1) if len(ln) > MAX_LINE_CHARS]
    assert largas == [], f"líneas de más de {MAX_LINE_CHARS} caracteres (línea, largo): {largas}"


# ---------------------------------------------------------------- export_map

_FAKE_MMDC = r'''
import json, sys, time
args = sys.argv[1:]
if "--dormir" in args:
    time.sleep(30)
if "-w" in args or "-H" in args:          # como mmdc 12.0.0: no existen
    print("error: unknown option")
    sys.exit(1)
if "-c" not in args:                      # export_map siempre pasa la configuracion de Mermaid
    print("mmdc falso: falta -c")
    sys.exit(1)
cfg = json.load(open(args[args.index("-c") + 1], encoding="utf-8"))
if cfg.get("htmlLabels") is not False or cfg.get("flowchart", {}).get("htmlLabels") is not False \
        or "arial" not in cfg.get("fontFamily", "") or "arial" not in cfg["themeVariables"]["fontFamily"]:
    print("mmdc falso: configuracion inesperada", cfg)
    sys.exit(1)
out = args[args.index("-o") + 1]
css = b'<style>#my-svg{font-family:arial,sans-serif;}</style>'
font = (b'<style>/* Copyright, SIL Open Font License */\n@font-face { font-family: "R"; src: url(data:font/woff2;base64,'
        + b"A" * 300_000 + b') format("woff2"); }</style>')
with open(out, "wb") as f:
    if "--png" in args:                   # para probar que export_map rechaza lo que no es SVG
        f.write(b"\x89PNG\r\n\x1a\n" + b"falso")
    elif "--fuente" in args:              # como mermaid-cli 12.0.0: la fuente en base64 (~300 KB)
        f.write(b'<svg xmlns="http://www.w3.org/2000/svg">' + css + font + b'<text>falso</text></svg>')
    elif "--grande" in args:              # pasa de 200 KB sin ninguna fuente
        f.write(b'<svg xmlns="http://www.w3.org/2000/svg">' + css + b"<text>x</text>" * 20_000 + b"</svg>")
    else:
        f.write(b'<svg xmlns="http://www.w3.org/2000/svg"><text>falso</text></svg>')
print("mmdc falso:", " ".join(args))
'''

_DOC = """# Doc
<!-- mapa:inicio -->
```mermaid
flowchart TD
    A["uno<br/>tracker.py:main"] --> B["dos"]
```
<!-- mapa:fin -->
"""


def _fake(tmp_path: Path, extra: str = "") -> str:
    script = tmp_path / "fake_mmdc.py"
    script.write_text(_FAKE_MMDC, encoding="utf-8")
    return f'"{sys.executable}" "{script}"{extra}'


def test_extract_mermaid_aborta_si_faltan_marcas_o_bloques():
    assert export_map.extract_mermaid(_DOC).startswith("flowchart TD")
    with pytest.raises(ValueError, match="inicio"):
        export_map.extract_mermaid("sin marcas")
    with pytest.raises(ValueError, match="hay 0"):
        export_map.extract_mermaid("<!-- mapa:inicio -->\nnada\n<!-- mapa:fin -->")
    doble = _DOC.replace("<!-- mapa:fin -->", "```mermaid\nflowchart LR\n```\n<!-- mapa:fin -->")
    with pytest.raises(ValueError, match="hay 2"):
        export_map.extract_mermaid(doble)


def test_split_command_y_argv_de_mmdc():
    cmd = export_map.split_command('"C:\\Program Files\\x\\node.exe" mmdc -y')
    assert cmd == ["C:\\Program Files\\x\\node.exe", "mmdc", "-y"]
    argv = export_map.build_mmdc_command(["mmdc"], Path("a.mmd"), Path("b.svg"), Path("p.json"), "white",
                                         mermaid_config=Path("m.json"))
    assert argv == ["mmdc", "-i", "a.mmd", "-o", "b.svg", "-b", "white", "-c", "m.json", "-p", "p.json"]
    con_size = export_map.build_mmdc_command(["mmdc"], Path("a"), Path("b"), None, "white", 800)
    assert con_size == ["mmdc", "-i", "a", "-o", "b", "-b", "white", "--size", "800"]
    assert "-w" not in argv and "-H" not in argv      # no existen en mermaid-cli 12.0.0
    # La configuración de Mermaid: letra arial y etiquetas <text> (sin foreignObject).
    cfg = export_map.MERMAID_CONFIG
    assert cfg["htmlLabels"] is False and cfg["flowchart"]["htmlLabels"] is False
    assert cfg["fontFamily"] == cfg["themeVariables"]["fontFamily"] == "arial, sans-serif"


def test_strip_embedded_fonts_quita_el_font_face_y_nada_mas():
    css = b'<style>#my-svg{font-family:arial,sans-serif;}</style>'
    lic = b'<style>/* Copyright\nSIL Open Font License */\n@font-face { font-family: "R"; src: url(data:x;base64,QUJD) format("woff2"); }\n@font-face { font-family: "R"; unicode-range: U+0-FF; }</style>'
    svg = b'<svg xmlns="http://www.w3.org/2000/svg">' + css + lic + b'<text>hola</text></svg>'
    out, n = export_map.strip_embedded_fonts(svg)
    assert n == 2
    assert out == b'<svg xmlns="http://www.w3.org/2000/svg">' + css + b'<text>hola</text></svg>'
    assert export_map.strip_embedded_fonts(svg) == (out, 2)          # determinista
    # Un <style> con CSS y @font-face: se queda el CSS, sin la regla.
    mixto = b'<svg><style>.a{fill:red;}@font-face{font-family:"R";src:url(x);}.b{x:1;}</style></svg>'
    assert export_map.strip_embedded_fonts(mixto) == (b'<svg><style>.a{fill:red;}.b{x:1;}</style></svg>', 1)
    # Sin fuentes: igual, byte a byte.
    assert export_map.strip_embedded_fonts(css) == (css, 0)
    assert export_map.strip_embedded_fonts(out) == (out, 0)


def test_export_map_escribe_imagen_y_sha(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(_DOC, encoding="utf-8")
    out = tmp_path / "img" / "mapa.svg"
    base = ["--doc", str(doc), "--output", str(out), "--mmdc", _fake(tmp_path),
            "--mmdc-version", "9.9.9", "--timeout", "60"]
    assert export_map.main(base) == 0
    assert export_map.is_svg(out.read_bytes())
    sha, tool = export_map.read_sha_file(out.with_suffix(".sha256"))
    assert sha == export_map.mermaid_sha256(export_map.extract_mermaid(_DOC))
    assert tool == "@mermaid-js/mermaid-cli@9.9.9"
    # No pisa sin --overwrite; con él, sí.
    assert export_map.main(base) == export_map.EXIT_BAD_INPUT
    assert export_map.main(base + ["--overwrite"]) == 0


def test_export_map_quita_la_fuente_y_respeta_el_tope(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(_DOC, encoding="utf-8")
    out = tmp_path / "mapa.svg"
    comun = ["--doc", str(doc), "--output", str(out), "--mmdc-version", "9.9.9", "--timeout", "60"]
    # mmdc deja ~300 KB con la fuente en base64; export_map la quita y el SVG queda pequeño.
    assert export_map.main(comun + ["--mmdc", _fake(tmp_path, " --fuente")]) == 0
    data = out.read_bytes()
    assert b"@font-face" not in data and b"Open Font License" not in data
    assert b"font-family:arial" in data and export_map.is_svg(data)
    assert len(data) < 1000
    assert out.with_suffix(".sha256").is_file()
    # Sin fuente y aun así > 200 KB: sale con 5 y no escribe nada.
    out.unlink()
    out.with_suffix(".sha256").unlink()
    assert export_map.main(comun + ["--mmdc", _fake(tmp_path, " --grande")]) == export_map.EXIT_TOO_BIG
    assert not out.exists() and not out.with_suffix(".sha256").exists()


def test_export_map_falla_fuerte(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(_DOC, encoding="utf-8")
    out = tmp_path / "mapa.svg"
    comun = ["--doc", str(doc), "--output", str(out), "--mmdc-version", "1.0.0"]
    # Lo que deja mmdc no es un SVG: sale con 1 y no escribe nada.
    assert export_map.main(comun + ["--mmdc", _fake(tmp_path, " --png"), "--timeout", "60"]) \
        == export_map.EXIT_MMDC_FAILED
    # Una salida que no es .svg (P9).
    with pytest.raises(SystemExit):
        export_map.main(["--doc", str(doc), "--output", str(tmp_path / "mapa.png"), "--mmdc", "x",
                         "--mmdc-version", "1.0.0", "--timeout", "60"])
    # Un navegador que no existe, un comando que no existe, un documento sin marcas.
    assert export_map.main(comun + ["--mmdc", _fake(tmp_path), "--timeout", "60",
                                    "--browser", str(tmp_path / "no_existe.exe")]) == export_map.EXIT_BAD_INPUT
    assert export_map.main(comun + ["--mmdc", "comando_que_no_existe_004", "--timeout", "60"]) \
        == export_map.EXIT_BAD_INPUT
    sin = tmp_path / "sin.md"
    sin.write_text("# nada\n", encoding="utf-8")
    assert export_map.main(["--doc", str(sin), "--output", str(out), "--mmdc", _fake(tmp_path),
                            "--mmdc-version", "1.0.0", "--timeout", "60"]) == export_map.EXIT_BAD_INPUT
    # El tope: el falso se duerme 30 s y el tope es 1 s.
    assert export_map.main(comun + ["--mmdc", _fake(tmp_path, " --dormir"), "--timeout", "1"]) \
        == export_map.EXIT_TIMEOUT
    assert not out.exists() and not out.with_suffix(".sha256").exists()
    with pytest.raises(SystemExit):
        export_map.main(comun + ["--mmdc", "x", "--timeout", "0"])
