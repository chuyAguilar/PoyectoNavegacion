r"""Exporta a SVG el mapa del proyecto de `docs/ARCHITECTURE.md` §9.1 (meta 004, fase 1).

El bloque Mermaid entre `<!-- mapa:inicio -->` y `<!-- mapa:fin -->` es la
fuente; la imagen se exporta de el con `mermaid-cli` (`mmdc`, de Node.js, fuera
del venv y de `requirements.txt`; ADR-032 propuesto) y nunca se edita a mano.
Junto a la imagen se escribe `<imagen>.sha256`: una linea con el sha256 del
bloque normalizado (finales LF, sin espacios al final de linea) y la version
de `mermaid-cli`. La suite (`tests/test_como_funciona.py`) compara ese sha con
el del Mermaid actual: si alguien cambia el Mermaid y no reexporta, falla.

La imagen es SVG (P9, `specs/004-como-funciona/clarify.md`): vectorial, se lee
a cualquier zoom; `mmdc` elige el formato por la extension de `-o`. Antes de
copiarla se comprueba que lo que dejo `mmdc` es un SVG.

El peso (tope de `docs/img/004/`: 200 KB, P6 y P9). A `mmdc` se le pasa con
`-c` un archivo de configuracion de Mermaid (`MERMAID_CONFIG`, escrito en el
temporal): letra `arial, sans-serif` (tambien en `themeVariables`) y
`htmlLabels: false`, global y en `flowchart` (el de `flowchart` esta obsoleto
desde Mermaid 11.12.3 y el global lo sustituye); asi las etiquetas salen como
`<text>` de SVG, sin `foreignObject`. Despues de exportar se QUITA del SVG, de
forma determinista, cada regla `@font-face` incrustada (`mermaid-cli` 12.0.0
mete la fuente Recursive en base64, ~167 KB, con su licencia OFL en un
comentario); un `<style>` que se queda sin mas que comentarios y espacios se
quita entero, con ese comentario. Lo demas del SVG no se toca. Si aun asi el
SVG y su `.sha256` pesan 200 KB o mas, no se escribe nada y sale con 5.

Solo hace falta correrlo al cambiar el Mermaid de §9.1. Se dibuja en local
(principio 5: no se usa mermaid.ink ni el editor web) con el navegador que se
le pase en `--browser` (Edge en BigDaddy); `PUPPETEER_SKIP_DOWNLOAD=1` en el
entorno del hijo para que no baje otro navegador (P8 = a, la recomendada).

Desde codigo\, con el venv y los argumentos explicitos (principio 7), con tope
(principio 9):

    python -m diagnostics.export_map --doc ..\docs\ARCHITECTURE.md ^
        --output ..\docs\img\004\mapa_proyecto.svg ^
        --mmdc "npx -y -p @mermaid-js/mermaid-cli@12.0.0 mmdc" --mmdc-version 12.0.0 ^
        --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
        --timeout 300

No pisa una imagen existente sin `--overwrite`. Sale con 0; 1 si `mmdc` falla
o no deja un SVG; 2 si una entrada no vale (marcas, bloque, salida que ya
existe o que no es .svg, comando o navegador que no existen); 4 si pasa el tope;
5 si el SVG pesa demasiado (no escribe nada).
No importa nada del tracker: solo la biblioteca estandar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAP_START = "<!-- mapa:inicio -->"
MAP_END = "<!-- mapa:fin -->"
TOOL = "@mermaid-js/mermaid-cli"
DEFAULT_BACKGROUND = "white"
KILL_TIMEOUT_S = 10.0
MAX_IMAGE_BYTES = 200 * 1024        # tope de docs/img/004/ (P6, P9): SVG + .sha256
FONT_FAMILY = "arial, sans-serif"
MERMAID_CONFIG = {                  # va a mmdc con -c
    "fontFamily": FONT_FAMILY,
    "themeVariables": {"fontFamily": FONT_FAMILY},
    "htmlLabels": False,                    # el global (Mermaid >= 11.12.3)
    "flowchart": {"htmlLabels": False},     # el obsoleto, por si la version lo lee aun
}

_BLOCK_RE = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_STYLE_RE = re.compile(rb"(<style\b[^>]*>)(.*?)(</style\s*>)", re.DOTALL | re.IGNORECASE)
_FONT_FACE_RE = re.compile(rb"@font-face\s*\{[^{}]*\}", re.IGNORECASE)
_CSS_EMPTY_RE = re.compile(rb"/\*.*?\*/|<!\[CDATA\[|\]\]>|\s+", re.DOTALL)

EXIT_OK = 0
EXIT_MMDC_FAILED = 1
EXIT_BAD_INPUT = 2
EXIT_TIMEOUT = 4
EXIT_TOO_BIG = 5


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_mermaid(doc_text: str, start: str = MAP_START, end: str = MAP_END) -> str:
    """El unico bloque ```mermaid``` entre las dos marcas (sin las vallas).

    Aborta con ValueError y un mensaje claro si falta una marca, si el fin va
    antes del inicio o si entre ellas hay cero o mas de un bloque (principio 7).
    """
    text = _lf(doc_text)
    i = text.find(start)
    if i < 0:
        raise ValueError(f"falta la marca de inicio del mapa: {start}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise ValueError(f"falta la marca de fin del mapa despues del inicio: {end}")
    if text.find(start, i + len(start), j) >= 0:
        raise ValueError(f"la marca de inicio del mapa aparece dos veces: {start}")
    blocks = _BLOCK_RE.findall(text[i + len(start):j])
    if len(blocks) != 1:
        raise ValueError(f"entre {start} y {end} tiene que haber un solo bloque ```mermaid```; "
                         f"hay {len(blocks)}")
    return blocks[0]


def mermaid_sha256(source: str) -> str:
    """sha256 del Mermaid normalizado: finales LF, sin espacios al final de cada
    linea y sin lineas vacias al principio ni al final. Un cambio de CRLF a LF no
    lo cambia; cambiar una etiqueta, si."""
    lines = [ln.rstrip() for ln in _lf(source).split("\n")]
    norm = "\n".join(lines).strip("\n") + "\n"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def split_command(text: str) -> list[str]:
    """El comando de `--mmdc` en argv, sin shell. Acepta comillas dobles (rutas de
    Windows con espacios) y conserva las barras invertidas."""
    parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p
             for p in shlex.split(text, posix=False)]
    if not parts or not parts[0]:
        raise ValueError("--mmdc esta vacio")
    return parts


def build_mmdc_command(mmdc: list[str], src: Path, out: Path, puppeteer_config: Path | None,
                       background: str, size: int | None = None,
                       mermaid_config: Path | None = None) -> list[str]:
    """El argv de `mmdc` (12.0.0): entrada, salida (la extension fija el formato),
    fondo, `--size` solo si se pide (maximo de alto o ancho, en px; `-w` y `-H` no
    existen), si hay, el archivo de configuracion de Mermaid (`-c`) y, si hay, el
    de puppeteer (`-p`, el navegador)."""
    cmd = list(mmdc) + ["-i", str(src), "-o", str(out), "-b", background]
    if size is not None:
        cmd += ["--size", str(int(size))]
    if mermaid_config is not None:
        cmd += ["-c", str(mermaid_config)]
    if puppeteer_config is not None:
        cmd += ["-p", str(puppeteer_config)]
    return cmd


def strip_embedded_fonts(data: bytes) -> tuple[bytes, int]:
    """(SVG sin fuentes incrustadas, cuantas reglas `@font-face` se quitaron).

    Quita cada `@font-face { ... }` de cada `<style>`; si el `<style>` se queda
    sin mas que comentarios, `CDATA` y espacios, lo quita entero (con el
    comentario de la licencia). El resto del SVG queda igual, byte a byte: la
    misma entrada da siempre la misma salida."""
    removed = 0

    def _one(m: re.Match) -> bytes:
        nonlocal removed
        body, n = _FONT_FACE_RE.subn(b"", m.group(2))
        if n == 0:
            return m.group(0)
        removed += n
        if not _CSS_EMPTY_RE.sub(b"", body):
            return b""
        return m.group(1) + body + m.group(3)

    return _STYLE_RE.sub(_one, data), removed


def is_svg(data: bytes) -> bool:
    """Lo que dejo `mmdc` es un SVG: empieza (tras un BOM o espacios) por `<svg` o
    `<?xml`, y contiene `<svg`."""
    head = data.lstrip(b"\xef\xbb\xbf").lstrip()
    return (head.startswith(b"<svg") or head.startswith(b"<?xml")) and b"<svg" in data


def sha_line(sha: str, version: str) -> str:
    """La linea del archivo `.sha256`: `<sha256> @mermaid-js/mermaid-cli@<version>`."""
    return f"{sha} {TOOL}@{version}\n"


def read_sha_file(path: Path) -> tuple[str, str]:
    """(sha256, herramienta@version) de un `.sha256` escrito por `main`."""
    parts = Path(path).read_text(encoding="utf-8").split()
    if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
        raise ValueError(f"{path}: se esperaba '<sha256> {TOOL}@<version>'")
    return parts[0], parts[1]


def _positive(text: str) -> float:
    v = float(text)
    if v <= 0:
        raise argparse.ArgumentTypeError("tiene que ser > 0")
    return v


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta a SVG el mapa de ARCHITECTURE.md §9.1 con mermaid-cli.")
    p.add_argument("--doc", required=True, help="docs/ARCHITECTURE.md")
    p.add_argument("--output", required=True, help="La imagen (.svg); el .sha256 va al lado.")
    p.add_argument("--mmdc", required=True,
                   help='El comando de mermaid-cli, p. ej. "npx -y -p @mermaid-js/mermaid-cli@12.0.0 mmdc".')
    p.add_argument("--mmdc-version", required=True, help="La version de mermaid-cli de --mmdc (va al .sha256).")
    p.add_argument("--timeout", required=True, type=_positive, help="Tope de la exportacion, en segundos.")
    p.add_argument("--browser", default=None,
                   help="Ruta de un Chromium ya instalado (Edge); se pasa a puppeteer como executablePath.")
    p.add_argument("--size", type=int, default=None,
                   help="Opcional: maximo de alto o ancho, en px (--size de mmdc). Sin el, "
                        "no se pasa a mmdc y el SVG lleva su tamano natural.")
    p.add_argument("--background", default=DEFAULT_BACKGROUND, help="Fondo (defecto white).")
    p.add_argument("--overwrite", action="store_true", help="Pisa la imagen y el .sha256 si ya existen.")
    args = p.parse_args(argv)
    if args.size is not None and args.size <= 0:
        p.error("--size tiene que ser > 0")
    if not re.fullmatch(r"[0-9A-Za-z.\-+]+", args.mmdc_version):
        p.error("--mmdc-version: solo la version, p. ej. 12.0.0")
    if Path(args.output).suffix.lower() != ".svg":
        p.error("--output tiene que terminar en .svg (P9)")
    return args


def _kill_tree(proc: subprocess.Popen) -> None:
    """Mata el hijo y sus descendientes (npx -> node -> navegador): principio 9."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=KILL_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        proc.kill()
        proc.wait(timeout=KILL_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _fail(msg: str, code: int) -> int:
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
    return code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    doc = Path(args.doc)
    out = Path(args.output)
    sha_path = out.with_suffix(".sha256")
    if not doc.is_file():
        return _fail(f"no existe el documento: {doc}", EXIT_BAD_INPUT)
    try:
        source = extract_mermaid(doc.read_text(encoding="utf-8"))
        mmdc = split_command(args.mmdc)
    except ValueError as e:
        return _fail(str(e), EXIT_BAD_INPUT)
    if not args.overwrite:
        for p in (out, sha_path):
            if p.exists():
                return _fail(f"ya existe, no se pisa sin --overwrite: {p}", EXIT_BAD_INPUT)
    exe = shutil.which(mmdc[0])
    if exe is None:
        return _fail(f"no se encuentra el comando de --mmdc: {mmdc[0]}", EXIT_BAD_INPUT)
    mmdc[0] = exe
    if args.browser is not None and not Path(args.browser).is_file():
        return _fail(f"no existe el navegador de --browser: {args.browser}", EXIT_BAD_INPUT)

    sha = mermaid_sha256(source)
    print(f"[Mapa] {doc}: bloque Mermaid de {len(source.splitlines())} lineas, sha256 {sha}", flush=True)
    with tempfile.TemporaryDirectory(prefix="export_map_") as tmp:
        tmp = Path(tmp)
        src = tmp / "mapa.mmd"
        src.write_text(source, encoding="utf-8", newline="\n")
        cfg = None
        if args.browser is not None:
            cfg = tmp / "puppeteer.json"
            cfg.write_text(json.dumps({"executablePath": str(Path(args.browser))}), encoding="utf-8")
        mermaid_cfg = tmp / "mermaid.json"
        mermaid_cfg.write_text(json.dumps(MERMAID_CONFIG), encoding="utf-8")
        tmp_out = tmp / "mapa.svg"
        cmd = build_mmdc_command(mmdc, src, tmp_out, cfg, args.background, args.size, mermaid_cfg)
        env = dict(os.environ)
        env["PUPPETEER_SKIP_DOWNLOAD"] = "1"    # P8 = a: no baja otro navegador
        print(f"[Mapa] {subprocess.list2cmdline(cmd)} (tope {args.timeout:.0f} s)", flush=True)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
        try:
            output, _ = proc.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            return _fail(f"mmdc no termino en {args.timeout:.0f} s; se detuvo", EXIT_TIMEOUT)
        if output:
            print(output.rstrip(), flush=True)
        if proc.returncode != 0:
            return _fail(f"mmdc salio con {proc.returncode}", EXIT_MMDC_FAILED)
        if not tmp_out.is_file() or tmp_out.stat().st_size == 0:
            return _fail("mmdc no dejo la imagen", EXIT_MMDC_FAILED)
        data = tmp_out.read_bytes()
    if not is_svg(data):
        return _fail("lo que dejo mmdc no es un SVG", EXIT_MMDC_FAILED)
    raw_size = len(data)
    data, n_fonts = strip_embedded_fonts(data)
    if n_fonts:
        print(f"[Mapa] se quitaron {n_fonts} @font-face incrustados: {raw_size} -> {len(data)} bytes",
              flush=True)
    line = sha_line(sha, args.mmdc_version)
    total = len(data) + len(line.encode("utf-8"))
    if total >= MAX_IMAGE_BYTES:
        return _fail(f"el SVG pesa {len(data)} bytes; con su .sha256, {total} >= {MAX_IMAGE_BYTES} "
                     f"(200 KB, tope de la imagen, P6/P9). No se escribio nada.", EXIT_TOO_BIG)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    sha_path.write_text(line, encoding="utf-8", newline="\n")
    print(f"[Mapa] {out} ({out.stat().st_size} bytes) y {sha_path.name} ({TOOL}@{args.mmdc_version})",
          flush=True)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
