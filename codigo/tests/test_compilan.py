"""Cada .py de codigo/iter4/ y codigo/iter4/gui/ compila (meta 001, fase 1).

El .pyc va a tmp_path: no ensucia los __pycache__ del arbol.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

import pytest

from .conftest import GUI_DIR, ITER4_DIR

SCRIPTS = sorted(ITER4_DIR.glob("*.py")) + sorted(GUI_DIR.glob("*.py"))


@pytest.mark.parametrize(
    "ruta", SCRIPTS, ids=[str(p.relative_to(ITER4_DIR)) for p in SCRIPTS]
)
def test_compila(ruta: Path, tmp_path: Path) -> None:
    py_compile.compile(str(ruta), cfile=str(tmp_path / (ruta.stem + ".pyc")),
                       doraise=True)
