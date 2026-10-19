"""El panel importa y arranca sin camara (meta 001, fase 1).

- Los 8 modulos de codigo/iter4/gui/ importan.
- `panel.py --selftest` corre como subproceso con QT_QPA_PLATFORM=offscreen,
  CWD codigo/ y tope de 60 s: abre el panel, refresca los semaforos, imprime
  y se cierra solo. No sondea la camara (solo bajo demanda) y el chequeo del
  puerto 18944 solo hace bind/close.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time

import pytest

from .conftest import CODIGO_DIR, GUI_DIR

MODULOS_GUI = sorted(p.stem for p in GUI_DIR.glob("*.py"))
TOPE_SELFTEST_S = 60


@pytest.mark.parametrize("modulo", MODULOS_GUI)
def test_importan_modulos_gui(modulo: str) -> None:
    importlib.import_module(modulo)


def test_panel_selftest() -> None:
    entorno = dict(os.environ)
    entorno["QT_QPA_PLATFORM"] = "offscreen"
    entorno["PYTHONIOENCODING"] = "utf-8"
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(GUI_DIR / "panel.py"), "--selftest"],
        cwd=str(CODIGO_DIR), env=entorno, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        timeout=TOPE_SELFTEST_S,
    )
    dt = time.monotonic() - t0
    salida = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"rc={proc.returncode}\n{salida}"
    assert "[panel-selftest] cerrando OK" in salida, salida
    assert dt < TOPE_SELFTEST_S
