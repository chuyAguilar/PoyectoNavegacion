"""Cada .py de codigo/iter4/, codigo/iter4/gui/ y codigo/slicer/ compila (meta 001, fase 1;
los scripts de Slicer desde la meta 003, fase 2: solo compilan, importan `slicer` y `qt`).

El .pyc va a tmp_path: no ensucia los __pycache__ del arbol.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

import pytest

from .conftest import CODIGO_DIR, GUI_DIR, ITER4_DIR

SCRIPTS = (sorted(ITER4_DIR.glob("*.py")) + sorted(GUI_DIR.glob("*.py"))
           + sorted((CODIGO_DIR / "slicer").glob("*.py")))


@pytest.mark.parametrize(
    "ruta", SCRIPTS, ids=[str(p.relative_to(CODIGO_DIR)) for p in SCRIPTS]
)
def test_compila(ruta: Path, tmp_path: Path) -> None:
    py_compile.compile(str(ruta), cfile=str(tmp_path / (ruta.stem + ".pyc")),
                       doraise=True)
