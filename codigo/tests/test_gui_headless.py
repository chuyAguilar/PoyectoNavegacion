"""El panel importa y arranca sin camara (meta 001, fase 1).

- Los modulos de codigo/iter4/gui/ importan (9 desde la fase 5 de la meta 002: calibracion.py).
- `panel.py --selftest` corre como subproceso con QT_QPA_PLATFORM=offscreen,
  CWD codigo/ y tope de 60 s: abre el panel, refresca los semaforos, imprime
  y se cierra solo. No sondea la camara (solo bajo demanda) y el chequeo del
  puerto 18944 solo hace bind/close.
- Desde la meta 003 (fase 2, ADR-026) el selftest se abre con el perfil gs1,
  que ya no trae rigid_bodies: «Arrancar tracker» tiene que quedar habilitado
  con la geometria y la punta en GRIS (no aplican).
"""
from __future__ import annotations

import importlib
import os
import re
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
        [sys.executable, str(GUI_DIR / "panel.py"), "--selftest", "--perfil", "tracker_config_gs1.yaml"],
        cwd=str(CODIGO_DIR), env=entorno, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        timeout=TOPE_SELFTEST_S,
    )
    dt = time.monotonic() - t0
    salida = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"rc={proc.returncode}\n{salida}"
    assert "[panel-selftest] cerrando OK" in salida, salida
    assert dt < TOPE_SELFTEST_S
    # P18/P19/P21 (meta 002, fases 4 y 5): la ventana de tres pasos compone sus recetas con el tablero
    # guardado (data/tablero_calibracion.yaml) y lo fijo, sin campos.
    lineas = salida.splitlines()

    def linea(clave: str) -> str:
        return next(ln for ln in lineas if ln.startswith(f"[panel-selftest] {clave}="))

    # Meta 003, fase 2 (ADR-026): con gs1, sin rigid_bodies, el tracker se puede arrancar.
    assert linea("perfil") == "[panel-selftest] perfil=tracker_config_gs1.yaml"
    assert linea("geometria").startswith("[panel-selftest] geometria=GRIS"), linea("geometria")
    assert linea("punta").startswith("[panel-selftest] punta=GRIS"), linea("punta")
    assert linea("apto_tracker") == "[panel-selftest] apto_tracker=SI", linea("apto_tracker")
    assert linea("boton_tracker_habilitado") == "[panel-selftest] boton_tracker_habilitado=True"
    assert "[panel-selftest] calcam_lado=24.86" in salida, salida
    enfocar = linea("enfocar_argv")
    for trozo in ("iter4/medir_modos.py", "tracker_config_gs1.yaml", "--enfocar", "--modo 1280x960:MJPG",
                  "--fps 90", "enfoque_gs1.json", "--timeout 600"):
        assert trozo in enfocar, enfocar
    calcam = linea("calcam_argv")
    for trozo in ("--square-mm 24.86", "--cols 8 --rows 5", "--detector ambos",
                  "--medidas-mm 149.1,149.1,149.1,149.1,149.4", "--casillas-por-medida 6", "--luz caja nivel 2",
                  "--reporte ", "calibracion_gs1_ambos.json", "intrinsecos_gs1_1280x960.yml"):
        assert trozo in calcam, calcam
    escala = linea("escala_argv")
    for trozo in ("iter4/comprobar_escala.py", "tracker_config_gs1.yaml", "--desplazamientos-mm 0,80,0,80,0,80",
                  "--frames-por-posicion 30", "--luz caja nivel 2", "escala_gs1.json"):
        assert trozo in escala, escala
    for clave in ("enfocar_ultima", "calcam_ultima", "escala_ultima"):
        assert linea(clave).split("=", 1)[1].startswith("Última: "), linea(clave)
    assert linea("medir_lado").endswith("Cada cuadro mide: 24.86 mm")
    # P21: lo que se ve en la ventana y en «Volver a medir el tablero…» no lleva jerga.
    textos = linea("calcam_textos")
    for trozo in ("Tablero medido: cada cuadro mide 24.86 mm", "Volver a medir el tablero…", "1 · Enfocar lente",
                  "2 · Calibrar con tablero", "3 · Comprobar escala con regla",
                  "Distancia entre tus dos marcas en la regla:", "Veces que vas y vuelves:",
                  "Solo hace falta si imprimes un tablero nuevo.", "la impresora nunca es exacta",
                  "2. Una punta en el borde de ARRIBA de un cuadro negro.",
                  "Cuenta cuántos cuadros avanzaste.", "Repítelo 5 veces en otras columnas.",
                  "Ejemplo: 6 cuadros → 149.1 mm", "Cuadros que avanzaste:", "Lo que marcó (5 veces):",
                  "Calibrar cámara (enfocar, tablero, escala)…", "Cerrar", "Guardar"):
        assert trozo in textos, trozo
    for jerga in (r"\bRMS\b", r"\bdetector", r"\bvistas?\b", r"\bcobertura\b", r"\bcontrol\b", r"\bpx\b",
                  r"\blado\b", r"\bluz\b", r"\breporte\b", r"\bsb\b", r"cl[aá]sico", r"\bcasillas?\b",
                  r"\.yml\b", r"\bClose\b", r"\bSave\b", r"\bCancel\b"):
        assert not re.search(jerga, textos, re.IGNORECASE), f"jerga {jerga!r} a la vista: {textos}"
