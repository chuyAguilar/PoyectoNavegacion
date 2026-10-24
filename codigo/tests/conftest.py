"""Configuracion comun de la suite (meta 001, fase 1; meta 003, fase 3).

Desde la meta 003, fase 3 (ADR-027) el codigo vive en paquetes bajo codigo/
(camera, calibration, diagnostics, gui, profiles; tracker.py suelto) y los
tests lo importan por paquete (`from camera import backend`). `pytest.ini`
pone codigo/ en sys.path (`pythonpath = .`): aqui no se toca sys.path. Este
modulo solo expone las rutas que usan los tests.
"""
from __future__ import annotations

from pathlib import Path

CODIGO_DIR = Path(__file__).resolve().parents[1]
PROFILES_DIR = CODIGO_DIR / "profiles"
DATA_DIR = CODIGO_DIR / "data"
GUI_DIR = CODIGO_DIR / "gui"
TESTS_DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORICO_DIR = CODIGO_DIR / "historico"
HISTORICO_ITER1_DIR = HISTORICO_DIR / "iter1" / "iter1_2026-05-16"
DODECAHEDRON_DIR = HISTORICO_DIR / "iter4" / "dodecahedron"
# Los paquetes del codigo vivo (los recorren test_compilan y test_aceleracion_msmf).
PACKAGES = ("camera", "calibration", "diagnostics", "gui", "profiles")
