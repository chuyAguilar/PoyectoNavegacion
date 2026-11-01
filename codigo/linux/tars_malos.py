"""Los tar que `wip recibir` tiene que negar, fabricados en memoria (meta 007, fase 2).

Los usan `tests/test_guardian.py` y `probar_barrera.ps1` (casos 17-20). Ninguno escribe en disco
lo que describe: un miembro `.nrrd` del tar es solo un nombre dentro del tar, y el enlace es un
`TarInfo` de tipo SYMTYPE, no un enlace real.

    python -m linux.tars_malos --destino <carpeta>

imprime `nombre<TAB>ruta` por cada tar escrito.
"""
from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path


def _tar(miembros: list) -> bytes:
    """`miembros`: [(nombre, contenido o None para carpeta, tipo o None), ...]."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for nombre, contenido, tipo in miembros:
            info = tarfile.TarInfo(nombre)
            if tipo == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            elif tipo == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = contenido
                tar.addfile(info)
            else:
                datos = contenido.encode("utf-8")
                info.size = len(datos)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(datos))
    return buf.getvalue()


def fabricar_bytes() -> dict:
    """Cada tar por su nombre: los cuatro de probar_barrera.ps1, dos mas para la suite y uno bueno."""
    return {
        "padre": _tar([("codigo/../fuera.txt", "x\n", None)]),
        "absoluta": _tar([("/etc/nav-malo.txt", "x\n", None)]),
        "enlace": _tar([("codigo/", None, "dir"), ("codigo/enlace", "/etc/passwd", "sym")]),
        "nrrd": _tar([("codigo/", None, "dir"), ("codigo/data/", None, "dir"),
                      ("codigo/data/volumen.nrrd", "no es un volumen\n", None)]),
        "dcm": _tar([("codigo/", None, "dir"), ("codigo/x.dcm", "no es un dicom\n", None)]),
        "fuera": _tar([("otro/", None, "dir"), ("otro/x.txt", "x\n", None)]),
        "bueno": _tar([("codigo/", None, "dir"), ("codigo/linux/", None, "dir"),
                       ("codigo/linux/__init__.py", '"""wip de prueba"""\n', None),
                       ("codigo/readme.md", "copia WIP de prueba\n", None)]),
    }


def fabricar(destino) -> dict:
    """Escribe los tar en `destino` (la crea) y devuelve {nombre: ruta}."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, datos in fabricar_bytes().items():
        ruta = destino / f"{nombre}.tar"
        ruta.write_bytes(datos)
        rutas[nombre] = ruta
    return rutas


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Fabrica los tar que wip recibir tiene que negar.")
    parser.add_argument("--destino", required=True, help="carpeta donde escribirlos")
    args = parser.parse_args(argv)
    for nombre, ruta in fabricar(args.destino).items():
        print(f"{nombre}\t{ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
