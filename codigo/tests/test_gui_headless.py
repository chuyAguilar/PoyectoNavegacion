"""El panel importa y arranca sin camara (meta 001, fase 1).

- Los modulos de codigo/gui/ importan como `gui.<modulo>` (7 + __init__ desde la meta 003,
  fase 3: sin el asistente del dodecaedro ni el monitor del BA, archivados).
- `python -m gui.panel --selftest` corre como subproceso con QT_QPA_PLATFORM=offscreen,
  CWD codigo/ y tope de 60 s: abre el panel, refresca los semaforos, imprime
  y se cierra solo. No sondea la camara (solo bajo demanda) y el chequeo del
  puerto 18944 solo hace bind/close.
- Desde la meta 003 (fase 2, ADR-026) el selftest se abre con el perfil gs1,
  que ya no trae rigid_bodies: «Arrancar tracker» tiene que quedar habilitado.
  Desde la fase 3 ya no hay semaforos de geometria ni de punta, ni botones del
  asistente o del dock, y las recetas lanzan `python -u -m <paquete>.<modulo>`.
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

MODULOS_GUI = sorted(f"gui.{p.stem}" for p in GUI_DIR.glob("*.py") if p.stem != "__init__")
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
        [sys.executable, "-m", "gui.panel", "--selftest", "--perfil", "tracker_config_gs1.yaml"],
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
    # Fase 3: sin semaforos de geometria ni de punta, sin botones del asistente ni del dock.
    for fuera in ("geometria=", "punta=", "boton_asistente", "boton_divot", "asistente_"):
        assert not any(ln.startswith(f"[panel-selftest] {fuera}") for ln in lineas), fuera
    assert linea("config").startswith("[panel-selftest] config=VERDE"), linea("config")
    assert linea("apto_tracker") == "[panel-selftest] apto_tracker=SI", linea("apto_tracker")
    assert linea("boton_tracker_habilitado") == "[panel-selftest] boton_tracker_habilitado=True"
    assert "[panel-selftest] calcam_lado=24.86" in salida, salida
    enfocar = linea("enfocar_argv")
    for trozo in ("-m diagnostics.measure_modes", "tracker_config_gs1.yaml", "--enfocar", "--modo 1280x960:MJPG",
                  "--fps 90", "enfoque_gs1.json", "--timeout 600"):
        assert trozo in enfocar, enfocar
    calcam = linea("calcam_argv")
    for trozo in ("-m calibration.calibrate_camera", "--square-mm 24.86", "--cols 8 --rows 5", "--detector ambos",
                  "--medidas-mm 149.1,149.1,149.1,149.1,149.4", "--casillas-por-medida 6", "--luz caja nivel 2",
                  "--reporte ", "calibracion_gs1_ambos.json", "intrinsecos_gs1_1280x960.yml"):
        assert trozo in calcam, calcam
    escala = linea("escala_argv")
    for trozo in ("-m calibration.check_scale", "tracker_config_gs1.yaml", "--desplazamientos-mm 0,80,0,80,0,80",
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
    # Meta 003, fase 8a (P14 = b, P16 = b): un boton por modo. «Verificar IDs y colocar la cámara»;
    # «Arrancar tracker» lanza sin ventana y «Arrancar tracker con ventana» el de siempre; «Detener
    # tracker» sin proceso, deshabilitado; ya no hay boton de vista previa ni «sin ventana».
    assert linea("boton_ids_habilitado").endswith("=True")
    assert linea("boton_tracker_con_ventana_habilitado").endswith("=True")
    assert linea("boton_detener_tracker_habilitado").endswith("=False")
    for fuera in ("boton_vista_previa", "boton_tracker_sin_ventana", "vista_previa_argv",
                  "tracker_sin_ventana_argv"):
        assert not any(ln.startswith(f"[panel-selftest] {fuera}") for ln in lineas), fuera
    gs1 = "tracker_config_gs1.yaml"
    ids = linea("ids_argv")
    assert ids.split("=", 1)[1].startswith("-m diagnostics.identify_ids --config ") and gs1 in ids
    assert ids.endswith(" --timeout 600") and "--no-detect" not in ids
    tracker = linea("tracker_argv").split("=", 1)[1]
    assert tracker.startswith("-m tracker --config ") and tracker.endswith(f"{gs1} --no-window --stop-stdin")
    from pathlib import Path
    con_ventana = linea("tracker_con_ventana_argv").split("=", 1)[1]
    assert con_ventana == f"-m tracker --config {Path('profiles') / gs1}", con_ventana
    textos_botones = linea("botones_textos").split("=", 1)[1].split(" | ")
    for esperado in ("ids:Verificar IDs y colocar la cámara", "tracker:Arrancar tracker",
                     "tracker_con_ventana:Arrancar tracker con ventana", "detener_tracker:Detener tracker"):
        assert esperado in textos_botones, textos_botones
    # Meta 004, fase 2b (P10): sin el boton de la sonda corta; «Verificar IDs y colocar la cámara»
    # pone el semaforo «Camara»: verde al cerrar con codigo 0, rojo con el motivo si no.
    assert not any(ln.startswith("[panel-selftest] boton_camara") for ln in lineas), lineas
    assert not any(t.startswith("camara:") or "Probar" in t for t in textos_botones), textos_botones
    assert linea("camara_antes").endswith("=GRIS"), linea("camara_antes")
    assert linea("camara").split(" :: ", 1)[1] == (
        "sin verificar — usar 'Verificar IDs y colocar la cámara' (no se sondea sola)")
    rc0 = linea("camara_tras_ids_rc0")
    assert rc0.startswith("[panel-selftest] camara_tras_ids_rc0=VERDE :: la del perfil: entrega 89.9 fps"), rc0
    rc1 = linea("camara_tras_ids_rc1")
    assert rc1.startswith("[panel-selftest] camara_tras_ids_rc1=ROJO :: Verificar IDs fallo (exit 1): "
                          "[ERROR] [IDs] la camara no entrega frames"), rc1


# ----------------------------------------------------------------------------
# Meta 003, fases 7b y 8a · Las recetas de los botones (P12, P13; P14 = b, P16 = b)
# ----------------------------------------------------------------------------

def test_recetas_de_los_botones() -> None:
    from pathlib import Path
    from gui import recipes
    gs1 = str(Path("profiles") / "tracker_config_gs1.yaml")
    ids = recipes.receta_identificar_ids(gs1)
    assert ids.argv[2:] == ["-m", "diagnostics.identify_ids", "--config", gs1, "--timeout", "600"]
    assert ids.ventana_titulo == recipes.VENTANAS["identificar_ids"] and not ids.stop_stdin
    assert ids.descripcion.startswith("Verificar IDs y colocar la camara (cruz y fps de la camara;")
    perm = recipes.receta_identificar_ids(gs1, permisivo=True, timeout=30)
    assert perm.argv[-3:] == ["--permisivo", "--timeout", "30"]
    # Fase 8a: la receta de la vista previa se va del panel (P16 = b); --no-detect queda en la CLI (P17 = a).
    assert not hasattr(recipes, "receta_vista_previa") and "vista_previa" not in recipes.VENTANAS
    tsv = recipes.receta_tracker_sin_ventana(gs1)
    assert tsv.clave == "tracker_sin_ventana" and tsv.stop_stdin and tsv.ventana_titulo is None
    assert tsv.argv[2:] == ["-m", "tracker", "--config", gs1, "--no-window", "--stop-stdin"]
    con = recipes.receta_tracker(gs1)
    assert con.clave == "tracker" and not con.stop_stdin and con.ventana_titulo == recipes.VENTANAS["tracker"]
    assert con.argv[2:] == ["-m", "tracker", "--config", gs1]


def test_titulos_de_ventana_iguales_a_los_del_script() -> None:
    """gui/ no importa diagnostics/ (carga cv2): los textos se comparan aqui."""
    from diagnostics import identify_ids
    from gui import recipes
    assert recipes.VENTANAS["identificar_ids"] == identify_ids.WINDOW_TITLE
    assert identify_ids.PREVIEW_WINDOW_TITLE == "Vista previa - q para salir"   # la CLI (P17 = a)


def test_linea_de_fps_de_identify_ids_la_que_lee_el_semaforo() -> None:
    """Meta 004, fase 2b (P10): `status.PREFIJO_FPS_IDS` es el comienzo de la linea de fps que
    escribe `identify_ids` con deteccion; si el script cambia su texto, el semaforo perderia los fps."""
    import inspect
    from diagnostics import identify_ids
    from gui import status
    fuente = inspect.getsource(identify_ids.main)
    assert 'tag = "[Vista previa]" if preview else "[IDs]"' in fuente
    assert 'print(f"{tag} camara {fps_camera:.1f} fps")' in fuente
    assert status.PREFIJO_FPS_IDS == "[IDs] camara "


_HIJO_LIMPIO = ("import sys\n"
                "print('[hijo] listo', flush=True)\n"
                "linea = sys.stdin.readline()\n"
                "print(f'[hijo] leyo {linea.strip()!r}', flush=True)\n"
                "print('[Salida limpia]', flush=True)\n")
_HIJO_SORDO = ("import time\n"
               "print('[hijo] listo', flush=True)\n"
               "time.sleep(60)\n")


def _lanzar_hijo(codigo: str):
    """Un Lanzador con un hijo real `python -c` que se detiene por la entrada estandar."""
    import threading
    from gui import processes, recipes
    lineas: list[str] = []
    fin = threading.Event()
    rcs: list[int] = []
    lz = processes.Lanzador(on_linea=lineas.append,
                            on_fin=lambda receta, rc: (rcs.append(rc), fin.set()))
    receta = recipes.Receta(clave="tracker_sin_ventana", descripcion="hijo de prueba",
                            argv=[sys.executable, "-u", "-c", codigo], cwd=str(CODIGO_DIR),
                            ventana_titulo=None, usa_camara=False, stop_stdin=True)
    assert lz.lanzar(receta) is None
    t0 = time.monotonic()
    while not any("[hijo] listo" in ln for ln in lineas):
        assert time.monotonic() - t0 < 20, lineas
        time.sleep(0.05)
    return lz, lineas, fin, rcs


def test_lanzador_detiene_por_la_entrada_estandar() -> None:
    lz, lineas, fin, rcs = _lanzar_hijo(_HIJO_LIMPIO)
    t0 = time.monotonic()
    msg = lz.detener()
    dt = time.monotonic() - t0
    assert msg == "cierre limpio (por la entrada estandar)", (msg, lineas)
    assert dt < 8.0
    assert fin.wait(5.0) and rcs == [0]
    assert "[hijo] leyo 'q'" in lineas and "[Salida limpia]" in lineas


def test_lanzador_sin_respuesta_cae_en_terminate(monkeypatch) -> None:
    from gui import processes
    monkeypatch.setattr(processes, "ESPERA_STDIN_S", 0.5)
    lz, lineas, fin, rcs = _lanzar_hijo(_HIJO_SORDO)
    msg = lz.detener()
    assert msg == "cerrado con terminate() (duro)", (msg, lineas)
    assert fin.wait(5.0) and rcs and rcs[0] != 0
    assert any("terminate()" in ln for ln in lineas)
