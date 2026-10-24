"""Cada .py del codigo vivo compila (meta 001, fase 1): tracker.py y los paquetes
de codigo/ (camera, calibration, diagnostics, gui, profiles; meta 003, fase 3)
y codigo/slicer/ (desde la meta 003, fase 2: solo compilan, importan `slicer`
y `qt`). Lo archivado en codigo/historico/ no se recorre.

El .pyc va a tmp_path: no ensucia los __pycache__ del arbol.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

import pytest

from .conftest import CODIGO_DIR, PACKAGES

SCRIPTS = ([CODIGO_DIR / "tracker.py"]
           + [p for pkg in PACKAGES for p in sorted((CODIGO_DIR / pkg).glob("*.py"))]
           + sorted((CODIGO_DIR / "slicer").glob("*.py")))


def test_estan_los_paquetes() -> None:
    """Ningun paquete vacio por un movimiento a medias (fase 3)."""
    for pkg in PACKAGES:
        assert (CODIGO_DIR / pkg / "__init__.py").is_file(), pkg
    assert not (CODIGO_DIR / "iter4").joinpath("tracker.py").exists()


@pytest.mark.parametrize(
    "ruta", SCRIPTS, ids=[str(p.relative_to(CODIGO_DIR)) for p in SCRIPTS]
)
def test_compila(ruta: Path, tmp_path: Path) -> None:
    py_compile.compile(str(ruta), cfile=str(tmp_path / (ruta.stem + ".pyc")),
                       doraise=True)
