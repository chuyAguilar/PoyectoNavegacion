"""Configuracion comun de la suite (meta 001, fase 1; meta 003, fases 3 y 4).

Desde la meta 003, fase 3 (ADR-027) el codigo vive en paquetes bajo codigo/
(camera, vision, transport, calibration, diagnostics, gui, profiles;
tracker.py suelto) y los tests lo importan por paquete (`from camera import
backend`). `pytest.ini` pone codigo/ en sys.path (`pythonpath = .`): aqui no
se toca sys.path. Este modulo expone las rutas que usan los tests y el fixture
autouse de B34.

B34 (meta 003, fase 4): ninguna prueba puede abrir una camara real ni tomar el
puerto 18944 aunque cambie un perfil. `no_real_camera` niega a toda la suite
`cv2.VideoCapture`, la enumeracion de camaras (`camera.uvc.listar_camaras_*`),
`WebcamBackend.open` sin un `abrir` falso inyectado y
`pyigtl.OpenIGTLinkServer`. Las pruebas que quieren un falso lo ponen ellas con
`monkeypatch` (pisa a este, que se deshace al final). `test_no_real_camera.py`
comprueba que un perfil real no abre nada.

Linux (meta 007, fase 4 · La suite corre en Linux): `no_real_camera` vale igual en la
Jetson, porque niega `cv2.VideoCapture` sea cual sea el backend (V4L2 incluido). Desde la
fase 5 · La capa V4L2 y cada camara en la Jetson niega tambien `camera.v4l2.listar_camaras_v4l2`
(lee /dev/v4l/by-path) y `camera.v4l2.ejecutar_v4l2ctl` (lanza v4l2-ctl). Desde la fase 7b ·
Las dos camaras a la vez en Windows niega `camera.dshow_props.abrir_filtro` (COM sobre el
filtro de captura). Ademas,
fuera de Windows, `python_del_venv_fuera_de_windows` hace que las recetas del panel
(`gui.recipes`) usen el python que corre la suite: el panel corre en el PC (P16) y en la
Jetson el venv esta en `~/.venvs/navegacion`, no en `codigo/.venv/Scripts/python.exe`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

CODIGO_DIR = Path(__file__).resolve().parents[1]
PROFILES_DIR = CODIGO_DIR / "profiles"
DATA_DIR = CODIGO_DIR / "data"
GUI_DIR = CODIGO_DIR / "gui"
TESTS_DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORICO_DIR = CODIGO_DIR / "historico"
HISTORICO_ITER1_DIR = HISTORICO_DIR / "iter1" / "iter1_2026-05-16"
DODECAHEDRON_DIR = HISTORICO_DIR / "iter4" / "dodecahedron"
# Los paquetes del codigo vivo (los recorren test_compilan y test_aceleracion_msmf).
PACKAGES = ("camera", "vision", "transport", "calibration", "diagnostics", "gui", "profiles", "linux", "fusion")


class RealHardwareForbidden(AssertionError):
    """Una prueba intento abrir una camara real o el servidor OpenIGTLink (B34)."""


def _forbid(what: str):
    def _raise(*_args, **_kwargs):
        raise RealHardwareForbidden(
            f"{what}: la suite no abre camaras reales ni el puerto 18944 (B34); "
            f"inyecta un falso o usa monkeypatch")
    return _raise


@pytest.fixture(autouse=True)
def no_real_camera(monkeypatch):
    """B34: niega el hardware real a cada prueba; se deshace al terminar."""
    import cv2
    import pyigtl
    from camera import backend as cb
    from camera import dshow_props
    from camera import uvc as cu
    from camera import v4l2 as cv4l2

    monkeypatch.setattr(cv2, "VideoCapture", _forbid("cv2.VideoCapture"))
    monkeypatch.setattr(cu, "listar_camaras_msmf", _forbid("camera.uvc.listar_camaras_msmf"))
    monkeypatch.setattr(cu, "listar_camaras_dshow", _forbid("camera.uvc.listar_camaras_dshow"))
    # Meta 007, fase 7b: la unica funcion que toca COM de verdad (el filtro de captura).
    monkeypatch.setattr(dshow_props, "abrir_filtro", _forbid("camera.dshow_props.abrir_filtro"))
    monkeypatch.setattr(cv4l2, "listar_camaras_v4l2", _forbid("camera.v4l2.listar_camaras_v4l2"))
    monkeypatch.setattr(cv4l2, "ejecutar_v4l2ctl", _forbid("camera.v4l2.ejecutar_v4l2ctl"))
    monkeypatch.setattr(pyigtl, "OpenIGTLinkServer", _forbid("pyigtl.OpenIGTLinkServer"))

    real_open = cb.WebcamBackend.open

    def guarded_open(self):
        if self._abrir is None:
            raise RealHardwareForbidden(
                "WebcamBackend.open sin `abrir` falso: la suite no abre camaras reales (B34)")
        return real_open(self)
    monkeypatch.setattr(cb.WebcamBackend, "open", guarded_open)
    yield


@pytest.fixture(autouse=True)
def python_del_venv_fuera_de_windows(monkeypatch):
    """Fuera de Windows, `gui.recipes.VENV_PY` es el python de la suite (meta 007, fase 4).
    En Windows no toca nada: las recetas siguen exigiendo `codigo/.venv/Scripts/python.exe`."""
    if sys.platform != "win32":
        from gui import recipes
        monkeypatch.setattr(recipes, "VENV_PY", Path(sys.executable))
    yield
