"""Cada .py del codigo vivo compila sin avisos (meta 001, fase 1; meta 003, fases 3 y 4):
tracker.py, los paquetes de codigo/ (camera, vision, transport, calibration,
diagnostics, gui, profiles), codigo/slicer/ (solo compilan, importan `slicer` y
`qt`) y los propios tests. Lo archivado en codigo/historico/ no se recorre.

B22: una secuencia de escape invalida en un docstring (`"\\)"`) da
DeprecationWarning al compilar en 3.11 y SyntaxWarning en 3.12+; aqui los
avisos son errores, asi que la prueba falla si vuelve a aparecer una.

El .pyc va a tmp_path: no ensucia los __pycache__ del arbol.
"""
from __future__ import annotations

import py_compile
import warnings
from pathlib import Path

import pytest

from .conftest import CODIGO_DIR, PACKAGES

SCRIPTS = ([CODIGO_DIR / "tracker.py"]
           + [p for pkg in PACKAGES for p in sorted((CODIGO_DIR / pkg).glob("*.py"))]
           + sorted((CODIGO_DIR / "slicer").glob("*.py"))
           + sorted((CODIGO_DIR / "tests").glob("*.py")))


def test_estan_los_paquetes() -> None:
    """Ningun paquete vacio por un movimiento a medias (fases 3 y 4)."""
    for pkg in PACKAGES:
        assert (CODIGO_DIR / pkg / "__init__.py").is_file(), pkg
    for modulo in ("vision/detection.py", "vision/pose.py", "vision/filtering.py",
                   "vision/tracking.py", "transport/igtl.py"):
        assert (CODIGO_DIR / modulo).is_file(), modulo
    assert not (CODIGO_DIR / "iter4").joinpath("tracker.py").exists()


@pytest.mark.parametrize(
    "ruta", SCRIPTS, ids=[str(p.relative_to(CODIGO_DIR)) for p in SCRIPTS]
)
def test_compila_sin_avisos(ruta: Path, tmp_path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # B22: un aviso de compilacion es un fallo
        py_compile.compile(str(ruta), cfile=str(tmp_path / (ruta.stem + ".pyc")),
                           doraise=True)
