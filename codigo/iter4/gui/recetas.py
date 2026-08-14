# -*- coding: utf-8 -*-
"""
recetas.py — Composicion de comandos para el panel GUI (brief-01). SIN Qt.

Cada receta devuelve el comando EXACTO (argv) para lanzar un script existente
como subproceso, con TODOS los argumentos explicitos. Motivo (sondeo 2026-08-13,
ver CONTEXT.md §4): varios defaults de los scripts apuntan al stylus VIEJO
(IDs 170-180) y usarlos con el perfil v2 (IDs 3-13) falla en silencio o pisa
artefactos vigentes:

  - captura_calibracion --geometry-file sin valor cae en reference_dodecaedro.txt
    (teorica vieja) porque ese archivo existe -> 0 frames utiles con el v2.
  - calibrar_rigid_body defaults: --ancla 170 --marker-mm 13.4 y un --output
    que pisaria reference_dodecaedro_calibrado.txt (del stylus viejo).
  - un dataset Femto trae depth y use_depth default=ON contradice ADR-008
    (BA solo-2D) -> se pasa --no-depth explicito.
  - ADR-009: el dataset del v2 requiere --no-sparse; ADR-008 fija el comando
    de referencia --max-frames 500 --max-nfev 3000.

El panel imprime el argv completo en el log ANTES de lanzar (auditable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

RAIZ_CODIGO = Path(__file__).resolve().parents[2]
VENV_PY = RAIZ_CODIGO / ".venv" / "Scripts" / "python.exe"

# Titulos EXACTOS de las ventanas OpenCV de cada script (verificados en codigo).
# Los usa procesos.py para el Detener graceful (PostMessage WM_CHAR 'q':
# camino nativo de los scripts, validado por la sonda del Paso 1).
VENTANAS = {
    "identificar_ids": "Identificar IDs - q para salir",
    "captura": "Captura calibracion iter4 - q para salir antes",
    "divot": "Calibracion divot iter4",
    "tracker": "Tracker Multi-Marker - q para salir",
    "ba": None,             # sin ventana (batch de consola)
    "generar": None,        # sin ventana (generacion instantanea, brief-02 M2)
    "calibrar_camara": "Calibracion camara iter4 - ESPACIO captura, q calibra",
}

# Slug corto por perfil para nombrar outputs (captura_ba_<slug>.npz, etc.).
SLUGS = {
    "tracker_config.yaml": "femto",
    "tracker_config_doctor.yaml": "doctor",
    "tracker_config_webcam.yaml": "webcam",
    "tracker_config_stylus_impreso.yaml": "stylus_impreso",
}

# Defaults del BA para el dodecaedro v2 compartido (ADR-009: IDs 3-13,
# ancla = cara superior ID 3, marker 14.6 mm; CONTEXT §4.13).
BA_V2 = {"ancla": 3, "marker_mm": 14.6, "max_frames": 500, "max_nfev": 3000}

# Defaults del dock del doctor (MANUAL_simplificado paso 2).
DOCK_DEFAULTS = {"divot": "DOCK", "plate_id": 2, "plate_mm": 59.6, "timeout": 600}


@dataclass
class Receta:
    clave: str               # identificar_ids | captura | ba | divot | tracker | sonda_camara
    descripcion: str
    argv: list = field(default_factory=list)
    cwd: str = str(RAIZ_CODIGO)
    ventana_titulo: str | None = None   # para Detener graceful ('q')
    usa_camara: bool = True
    outputs: list = field(default_factory=list)  # rutas que el script escribiria
    timeout_s: float | None = None      # watchdog (solo sondas cortas)

    def comando_legible(self):
        return " ".join(str(a) for a in self.argv)


def _python():
    """python del venv del proyecto; el del sistema jamas (deps del repo)."""
    if VENV_PY.exists():
        return str(VENV_PY)
    raise FileNotFoundError(
        f"No existe el python del venv: {VENV_PY} — crear el venv primero "
        f"(codigo\\readme.md)")


def _rel(p):
    """Ruta relativa a codigo\\ (CWD de los subprocesos) si es posible."""
    p = Path(p)
    try:
        return str(p.resolve().relative_to(RAIZ_CODIGO)) if p.is_absolute() else str(p)
    except ValueError:
        return str(p)


def slug_de_perfil(ruta_cfg):
    nombre = Path(ruta_cfg).name
    if nombre in SLUGS:
        return SLUGS[nombre]
    # tracker_config_<algo>.yaml -> <algo>; sino el stem completo
    stem = Path(nombre).stem
    return stem.replace("tracker_config_", "").replace("tracker_config", "perfil")


def receta_identificar_ids(ruta_cfg, permisivo=False):
    argv = [_python(), "-u", "iter4/identificar_ids.py", "--config", _rel(ruta_cfg)]
    if permisivo:
        argv.append("--permisivo")
    return Receta(
        clave="identificar_ids",
        descripcion="Verificar IDs y orientacion del dodecaedro (q para salir)",
        argv=argv,
        ventana_titulo=VENTANAS["identificar_ids"],
        usa_camara=True,
    )


def receta_captura(ruta_cfg, geometry_file, duracion=60, output=None,
                   min_markers=2):
    """geometry_file es OBLIGATORIO y explicito (trampa del default, ver arriba).
    Normalmente = la geometria del perfil; en el asistente = la teorica semilla."""
    if not geometry_file:
        raise ValueError("receta_captura: geometry_file es obligatorio "
                         "(el default del script apunta a la teorica vieja)")
    if output is None:
        output = f"iter4/data/captura_ba_{slug_de_perfil(ruta_cfg)}.npz"
    argv = [
        _python(), "-u", "iter4/captura_calibracion.py",
        "--config", _rel(ruta_cfg),
        "--geometry-file", _rel(geometry_file),
        "--duracion", str(int(duracion)),
        "--output", _rel(output),
        "--min-markers-per-frame", str(int(min_markers)),
    ]
    return Receta(
        clave="captura",
        descripcion=f"Capturar dataset para BA ({duracion}s; q corta antes)",
        argv=argv,
        ventana_titulo=VENTANAS["captura"],
        usa_camara=True,
        outputs=[_rel(output)],
    )


def receta_ba(input_npz, teorico, output, ancla=BA_V2["ancla"],
              marker_mm=BA_V2["marker_mm"], max_frames=BA_V2["max_frames"],
              max_nfev=BA_V2["max_nfev"], no_sparse=True, no_depth=True,
              sobrescribir=False):
    """Bundle adjustment OFFLINE (sin camara). Todos los args explicitos.
    Si el output pisaria una geometria *calibrado* ya existente, se rechaza
    salvo sobrescribir=True (la GUI pide confirmacion explicita antes)."""
    for nombre, v in (("input_npz", input_npz), ("teorico", teorico),
                      ("output", output)):
        if not v:
            raise ValueError(f"receta_ba: {nombre} es obligatorio")
    if Path(_rel(output)) == Path(_rel(teorico)):
        raise ValueError("receta_ba: output no puede pisar la teorica semilla")
    out_abs = Path(output)
    if not out_abs.is_absolute():
        out_abs = RAIZ_CODIGO / _rel(output)
    if (out_abs.exists() and "calibrado" in out_abs.name.lower()
            and not sobrescribir):
        raise ValueError(
            f"receta_ba: {out_abs.name} YA EXISTE y es una geometria CALIBRADA "
            f"(posiblemente vigente). Elegir otro nombre de salida, o confirmar "
            f"la sobrescritura explicitamente.")
    argv = [
        _python(), "-u", "iter4/calibrar_rigid_body.py",
        "--input", _rel(input_npz),
        "--teorico", _rel(teorico),
        "--output", _rel(output),
        "--ancla", str(int(ancla)),
        "--marker-mm", str(float(marker_mm)),
        "--max-frames", str(int(max_frames)),
        "--max-nfev", str(int(max_nfev)),
    ]
    if no_sparse:
        argv.append("--no-sparse")   # ADR-009: el dataset v2 lo exige
    if no_depth:
        argv.append("--no-depth")    # ADR-008: BA solo-2D
    return Receta(
        clave="ba",
        descripcion="Bundle adjustment de la geometria (offline, puede tardar minutos)",
        argv=argv,
        ventana_titulo=None,
        usa_camara=False,
        outputs=[_rel(output)],
    )


def receta_divot(ruta_cfg, output_matriz=None, divot=DOCK_DEFAULTS["divot"],
                 plate_id=DOCK_DEFAULTS["plate_id"],
                 plate_mm=DOCK_DEFAULTS["plate_mm"],
                 timeout=DOCK_DEFAULTS["timeout"]):
    """Calibracion de punta por dock/divot. OJO: el script se AUTOCIERRA a los
    --timeout segundos (default 600). Outputs: <output_matriz>.npy y .txt."""
    if output_matriz is None:
        output_matriz = (f"iter4/data/StylusTipToDodecaedro_"
                         f"{slug_de_perfil(ruta_cfg)}_dock")
    argv = [
        _python(), "-u", "iter4/calibrar_tip_divot.py",
        "--config", _rel(ruta_cfg),
        "--divot", str(divot),
        "--plate-id", str(int(plate_id)),
        "--plate-mm", str(float(plate_mm)),
        "--timeout", str(int(timeout)),
        "--output-matriz", _rel(output_matriz),
    ]
    return Receta(
        clave="divot",
        descripcion=(f"Calibrar punta ({divot}, placa ID {plate_id} @ {plate_mm} mm; "
                     f"ESPACIO=postura, q=terminar; autocierre {timeout}s)"),
        argv=argv,
        ventana_titulo=VENTANAS["divot"],
        usa_camara=True,
        outputs=[_rel(str(output_matriz) + ".npy"), _rel(str(output_matriz) + ".txt")],
    )


def receta_tracker(ruta_cfg):
    argv = [_python(), "-u", "iter4/tracker.py", "--config", _rel(ruta_cfg)]
    return Receta(
        clave="tracker",
        descripcion="Tracker en vivo (Slicer conectado ANTES; q para salir)",
        argv=argv,
        ventana_titulo=VENTANAS["tracker"],
        usa_camara=True,
    )


def receta_generar_teorica(output, id_top, ids_superior, ids_inferior,
                           edge_mm=17.5, marker_mm=BA_V2["marker_mm"]):
    """Genera la teorica semilla con generar_reference_dodecaedro.py (M2).

    OJO (trampa CONTEXT §4, detectada 2026-08-13): el --output default del
    script cae en codigo\\data\\ (relativo al CWD, carpeta equivocada que
    ademas crea en silencio) y sus IDs default son del stylus viejo (170-180)
    -> TODO explicito siempre. La validacion geometrica exhaustiva del script
    (11 invariantes) es la autoridad: si falla, aborta sin escribir.
    """
    if not output:
        raise ValueError("receta_generar_teorica: output es obligatorio "
                         "(el default del script cae en codigo\\data\\)")
    ids_superior = [int(x) for x in ids_superior]
    ids_inferior = [int(x) for x in ids_inferior]
    if len(ids_superior) != 5 or len(ids_inferior) != 5:
        raise ValueError("receta_generar_teorica: los anillos llevan 5 IDs "
                         f"cada uno (recibidos {len(ids_superior)} sup / "
                         f"{len(ids_inferior)} inf)")
    todos = [int(id_top)] + ids_superior + ids_inferior
    if len(set(todos)) != 11:
        raise ValueError(f"receta_generar_teorica: los 11 IDs deben ser "
                         f"unicos; recibidos {todos}")
    argv = [
        _python(), "-u", "iter4/generar_reference_dodecaedro.py",
        "--output", _rel(output),
        "--edge-mm", str(float(edge_mm)),
        "--marker-mm", str(float(marker_mm)),
        "--id-top", str(int(id_top)),
        "--ids-superior", ",".join(str(x) for x in ids_superior),
        "--ids-inferior", ",".join(str(x) for x in ids_inferior),
    ]
    return Receta(
        clave="generar",
        descripcion=(f"Generar teorica del dodecaedro (top {id_top}, "
                     f"sup {ids_superior}, inf {ids_inferior}; validacion "
                     f"geometrica incluida)"),
        argv=argv,
        ventana_titulo=None,
        usa_camara=False,
        outputs=[_rel(output)],
        timeout_s=30.0,
    )


def receta_calibrar_camara(ruta_cfg, output, cols=8, rows=5, square_mm=25.0,
                           min_vistas=12, timeout=900):
    """Calibracion intrinseca con tablero (M3b, iter4/calibrar_camara.py).
    Tablero del proyecto: 9x6 casillas -> esquinas interiores 8x5 @ 25 mm
    (codigo/readme.md §8). output SIEMPRE explicito (sin default-trampa)."""
    if not output:
        raise ValueError("receta_calibrar_camara: output es obligatorio")
    argv = [
        _python(), "-u", "iter4/calibrar_camara.py",
        "--config", _rel(ruta_cfg),
        "--output", _rel(output),
        "--cols", str(int(cols)),
        "--rows", str(int(rows)),
        "--square-mm", str(float(square_mm)),
        "--min-vistas", str(int(min_vistas)),
        "--timeout", str(int(timeout)),
    ]
    return Receta(
        clave="calibrar_camara",
        descripcion=(f"Calibrar camara con tablero {cols}x{rows} @ "
                     f"{square_mm} mm (ESPACIO=vista, q=calibrar; "
                     f"autocierre {timeout}s)"),
        argv=argv,
        ventana_titulo=VENTANAS["calibrar_camara"],
        usa_camara=True,
        outputs=[_rel(output)],
    )


def receta_sonda_camara(ruta_cfg):
    """Chequeo corto de camara bajo demanda (Paso 8): abre-lee-libera (webcam)
    o enumera dispositivos sin abrir pipeline (femtobolt). Con watchdog: si el
    driver se cuelga, el panel lo mata a los 20 s."""
    argv = [_python(), "-u", "iter4/gui/sonda_camara.py", "--config", _rel(ruta_cfg)]
    return Receta(
        clave="sonda_camara",
        descripcion="Probar camara (chequeo corto, libera el dispositivo al terminar)",
        argv=argv,
        ventana_titulo=None,
        usa_camara=True,
        timeout_s=20.0,
    )


if __name__ == "__main__":
    # Smoke check: imprime las recetas para el perfil canonico.
    cfg = "iter4/tracker_config.yaml"
    print("[recetas] comandos que compondria el panel (perfil canonico):")
    r1 = receta_identificar_ids(cfg)
    r2 = receta_captura(cfg, geometry_file="iter4/data/reference_dodecaedro_v2_calibrado.txt")
    r3 = receta_ba("iter4/data/captura_ba_femto.npz",
                   "iter4/data/reference_dodecaedro_v2.txt",
                   "iter4/data/reference_dodecaedro_v2_recalibrado.txt")
    r4 = receta_divot(cfg)
    r5 = receta_tracker(cfg)
    for r in (r1, r2, r3, r4, r5):
        print(f"\n  [{r.clave}] {r.descripcion}")
        print(f"    cwd={r.cwd}")
        print(f"    {r.comando_legible()}")
        if r.outputs:
            print(f"    outputs: {r.outputs}")
