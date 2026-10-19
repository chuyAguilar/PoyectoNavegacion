"""Configuracion comun de la suite (meta 001, fase 1).

Pone codigo/iter4/ y codigo/iter4/gui/ en sys.path para que los tests importen
los scripts activos por su nombre (p.ej. `import tracker`), y expone las rutas
que usan los tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

CODIGO_DIR = Path(__file__).resolve().parents[1]
ITER4_DIR = CODIGO_DIR / "iter4"
GUI_DIR = ITER4_DIR / "gui"
DATA_DIR = ITER4_DIR / "data"
TESTS_DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORICO_ITER1_DIR = CODIGO_DIR / "historico" / "iter1" / "iter1_2026-05-16"

for _p in (GUI_DIR, ITER4_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
