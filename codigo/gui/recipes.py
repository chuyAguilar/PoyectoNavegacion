# -*- coding: utf-8 -*-
"""
recipes.py — Composicion de comandos para el panel GUI (brief-01; era
gui/recetas.py). SIN Qt.

Cada receta devuelve el comando EXACTO (argv) para lanzar un script existente
como subproceso, con TODOS los argumentos explicitos (principio 7): varios
defaults de los scripts viejos apuntaban al stylus VIEJO y fallaban en
silencio o pisaban artefactos vigentes (CONTEXT.md §4.13-17).

Meta 003, fase 3 (ADR-027): los scripts se lanzan como modulos,
`python -u -m <paquete>.<modulo>`, con CWD codigo\\; se van las recetas del
dodecaedro y la punta (captura, BA, divot, teorica), archivadas con su codigo
en codigo/historico/iter4/dodecahedron/.

El panel imprime el argv completo en el log ANTES de lanzar (auditable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

RAIZ_CODIGO = Path(__file__).resolve().parents[1]   # gui/ -> codigo/
VENV_PY = RAIZ_CODIGO / ".venv" / "Scripts" / "python.exe"

# Titulos EXACTOS de las ventanas OpenCV de cada script (verificados en codigo).
# Los usa procesos.py para el Detener graceful (PostMessage WM_CHAR 'q':
# camino nativo de los scripts, validado por la sonda del Paso 1).
VENTANAS = {
    "identificar_ids": "Identificar IDs - q para salir",
    # (la vista previa, identify_ids --no-detect, queda solo para la linea de comandos desde la
    # meta 003, fase 8a: P16 = b, P17 = a; el panel ya no la lanza)
    "tracker": "Tracker Multi-Marker - q para salir",
    "calibrar_camara": "Calibracion camara - ESPACIO captura, q calibra",   # calibrate_camera.TITULO_VENTANA
    "comprobar_escala": "Comprobar escala - ESPACIO posicion, q salir",
    "enfocar": "medir_modos - q para interrumpir",     # measure_modes.VENTANA (P19)
}

# El modulo que lanza cada receta (python -m, desde codigo/; meta 003, fase 3).
MODULOS = {
    "identificar_ids": "diagnostics.identify_ids",
    "tracker": "tracker",
    "calibrar_camara": "calibration.calibrate_camera",
    "comprobar_escala": "calibration.check_scale",
    "enfocar": "diagnostics.measure_modes",
    "sonda_camara": "gui.camera_probe",
}

@dataclass
class Receta:
    clave: str               # identificar_ids | tracker | tracker_sin_ventana | calibrar_camara | comprobar_escala | enfocar | sonda_camara
    descripcion: str
    argv: list = field(default_factory=list)
    cwd: str = str(RAIZ_CODIGO)
    ventana_titulo: str | None = None   # para Detener graceful ('q')
    usa_camara: bool = True
    outputs: list = field(default_factory=list)  # rutas que el script escribiria
    timeout_s: float | None = None      # watchdog (solo sondas cortas)
    stop_stdin: bool = False            # se detiene por la entrada estandar (tracker --stop-stdin; fase 7b)

    def comando_legible(self):
        return " ".join(str(a) for a in self.argv)


def _python():
    """python del venv del proyecto; el del sistema jamas (deps del repo)."""
    if VENV_PY.exists():
        return str(VENV_PY)
    raise FileNotFoundError(
        f"No existe el python del venv: {VENV_PY} — crear el venv primero "
        f"(codigo\\readme.md)")


def _modulo(clave):
    """[python, -u, -m, <modulo>]: el comienzo del argv de la receta `clave`."""
    return [_python(), "-u", "-m", MODULOS[clave]]


def _rel(p):
    """Ruta relativa a codigo\\ (CWD de los subprocesos) si es posible."""
    p = Path(p)
    try:
        return str(p.resolve().relative_to(RAIZ_CODIGO)) if p.is_absolute() else str(p)
    except ValueError:
        return str(p)


def slug_de_perfil(ruta_cfg):
    nombre = Path(ruta_cfg).name
    # tracker_config_<algo>.yaml -> <algo>; sino el stem completo
    stem = Path(nombre).stem
    return stem.replace("tracker_config_", "").replace("tracker_config", "perfil")


# Tope de "Verificar IDs y colocar la camara" (identify_ids --timeout, obligatorio
# desde la meta 003, fase 7b: principio 9).
IDS_TIMEOUT_S = 600


def receta_identificar_ids(ruta_cfg, permisivo=False, timeout: int = IDS_TIMEOUT_S):
    """«Verificar IDs y colocar la camara» (meta 003, fase 8a; P16 = b): identify_ids
    con deteccion, que desde la 8a dibuja tambien la cruz y los fps de la camara.
    El argv y el titulo de la ventana, los de la fase 7b."""
    argv = _modulo("identificar_ids") + ["--config", _rel(ruta_cfg)]
    if permisivo:
        argv.append("--permisivo")
    argv += ["--timeout", str(int(timeout))]
    return Receta(
        clave="identificar_ids",
        descripcion=(f"Verificar IDs y colocar la camara (cruz y fps de la camara; q para salir; "
                     f"autocierre {int(timeout)}s)"),
        argv=argv,
        ventana_titulo=VENTANAS["identificar_ids"],
        usa_camara=True,
    )


def receta_tracker(ruta_cfg):
    argv = _modulo("tracker") + ["--config", _rel(ruta_cfg)]
    return Receta(
        clave="tracker",
        descripcion="Tracker en vivo (Slicer conectado ANTES; q para salir)",
        argv=argv,
        ventana_titulo=VENTANAS["tracker"],
        usa_camara=True,
    )


def receta_tracker_sin_ventana(ruta_cfg):
    """El tracker sin ventana (meta 003, fase 7b; P10, P12): se detiene por la
    entrada estandar ('Detener tracker' escribe q y la cierra)."""
    argv = _modulo("tracker") + ["--config", _rel(ruta_cfg), "--no-window", "--stop-stdin"]
    return Receta(
        clave="tracker_sin_ventana",
        descripcion="Tracker en vivo sin ventana (Slicer conectado ANTES; 'Detener tracker' para salir)",
        argv=argv,
        ventana_titulo=None,
        usa_camara=True,
        stop_stdin=True,
    )


# Calibracion de camara (meta 002, fase 4; P18): "ambos" calibra con los dos
# detectores sobre las mismas vistas y se queda el de menor RMS de control
# (calibrar_camara.py --detector ambos). La escala se comprueba con el detector
# ganador, que el .yml declara (clasico o sb).
DETECTORES_CALIBRACION = ("ambos", "clasico", "sb")
DETECTORES_ESCALA = ("clasico", "sb")
MIN_MEDIDAS = 5                   # medidas del calibrador (calibrar_camara.comprobar_lado)
TOLERANCIA_LADO_MM = 0.01         # la misma que calibrar_camara.comprobar_lado
LUZ_POR_DEFECTO = "caja nivel 2"  # P7
POSICIONES_ESCALA = "0,80,0,80,0,80"   # sesion en vivo de la fase 4: la caja deja 80 mm
FRAMES_POR_POSICION = 30


def _parsear_numeros(texto, nombre):
    """'149.1, 149.1; 149.4' -> [149.1, 149.1, 149.4]. Separadores: coma,
    punto y coma o espacio; el decimal es el punto. ValueError si un trozo no
    es un numero."""
    if isinstance(texto, (list, tuple)):
        trozos = [str(t) for t in texto]
    else:
        trozos = str(texto or "").replace(";", ",").replace(",", " ").split()
    try:
        return [float(t) for t in trozos]
    except ValueError:
        raise ValueError(f"{nombre} mal escrito: {texto!r} (numeros con punto "
                         f"decimal, separados por comas)")


def _num(x):
    """Un numero como texto, sin perder decimales: 80.0 -> '80', 149.1 -> '149.1'."""
    x = float(x)
    return str(int(x)) if x.is_integer() else repr(x)


def parsear_medidas(texto):
    """Las medidas del calibrador (mm, positivas)."""
    medidas = _parsear_numeros(texto, "medidas del calibrador")
    if any(m <= 0 for m in medidas):
        raise ValueError(f"una medida del calibrador no es positiva: {medidas}")
    return medidas


def lado_de_medidas(medidas, casillas_por_medida):
    """El lado de la casilla con dos decimales: media de las medidas entre las
    casillas que abarca cada una (la misma cuenta que
    calibrate_camera.lado_desde_medidas; gui/ no importa calibration/, que carga cv2)."""
    if not medidas:
        raise ValueError("sin medidas del calibrador")
    casillas = int(casillas_por_medida)
    if casillas < 1:
        raise ValueError(f"casillas por medida tiene que ser >= 1, no {casillas}")
    return round(sum(medidas) / len(medidas) / casillas, 2)


def reporte_por_defecto(vistas_dir, slug, detector):
    """El JSON de la calibracion, junto a la carpeta de vistas."""
    return (Path(vistas_dir).parent / f"calibracion_{slug}_{detector}.json").as_posix()


def valor_arg(argv, bandera):
    """El valor que sigue a `bandera` en argv (None si no esta)."""
    argv = [str(a) for a in argv]
    if bandera in argv and argv.index(bandera) + 1 < len(argv):
        return argv[argv.index(bandera) + 1]
    return None


def _validar_lado(square_mm, quien):
    try:
        square_mm = float(square_mm)
    except (TypeError, ValueError):
        raise ValueError(f"{quien}: square_mm tiene que ser un "
                         f"numero (medido con calibrador), no {square_mm!r}")
    if not (5.0 <= square_mm <= 100.0):
        raise ValueError(f"{quien}: square_mm {square_mm} fuera "
                         f"de rango (5-100 mm): mide el lado con calibrador")
    return square_mm


def receta_calibrar_camara(ruta_cfg, output, square_mm, vistas_dir, cols=8, rows=5,
                           detector="clasico", min_vistas=15, n_control=3, timeout=900,
                           luz=None, medidas_mm=None, casillas_por_medida=4,
                           reporte=None):
    """Calibracion intrinseca con tablero (calibration/calibrate_camera.py; meta 002,
    fase 4). Tablero impreso en 3D: 9x6 casillas -> esquinas interiores 8x5,
    25 mm NOMINALES: square_mm es el lado MEDIDO con calibrador (obligatorio,
    sin default: el nominal daria una escala equivocada que el RMS no ve).
    Con medidas_mm (>= 5) se pasan --medidas-mm y --casillas-por-medida y el
    lado tiene que salir de ellas (el script lo vuelve a comprobar).
    vistas_dir guarda las vistas para recalibrar con --desde-vistas. output
    SIEMPRE explicito (sin default-trampa). detector "ambos": gana el de
    menor RMS de control (exige n_control >= 1)."""
    if not output:
        raise ValueError("receta_calibrar_camara: output es obligatorio")
    if not vistas_dir:
        raise ValueError("receta_calibrar_camara: vistas_dir es obligatorio "
                         "(las vistas se guardan para recalibrar sin camara)")
    square_mm = _validar_lado(square_mm, "receta_calibrar_camara")
    if detector not in DETECTORES_CALIBRACION:
        raise ValueError(f"receta_calibrar_camara: detector {detector!r} no es "
                         f"uno de {DETECTORES_CALIBRACION}")
    if detector == "ambos" and int(n_control) < 1:
        raise ValueError("receta_calibrar_camara: con los dos detectores gana el "
                         "de menor RMS de control: hacen falta vistas de control (>= 1)")
    medidas = None
    if medidas_mm is not None and medidas_mm != "" and medidas_mm != []:
        medidas = parsear_medidas(medidas_mm)
        if len(medidas) < MIN_MEDIDAS:
            raise ValueError(f"receta_calibrar_camara: hacen falta al menos "
                             f"{MIN_MEDIDAS} medidas del calibrador, hay {len(medidas)}")
        lado = lado_de_medidas(medidas, casillas_por_medida)
        if abs(lado - square_mm) > TOLERANCIA_LADO_MM + 1e-9:
            raise ValueError(f"receta_calibrar_camara: square_mm {square_mm:.2f} no "
                             f"coincide con las medidas ({lado:.2f} mm)")
    argv = _modulo("calibrar_camara") + [
        "--config", _rel(ruta_cfg),
        "--output", _rel(output),
        "--square-mm", f"{square_mm:.2f}",
        "--cols", str(int(cols)),
        "--rows", str(int(rows)),
        "--detector", str(detector),
        "--vistas-dir", _rel(vistas_dir),
        "--min-vistas", str(int(min_vistas)),
        "--n-control", str(int(n_control)),
        "--timeout", str(int(timeout)),
    ]
    if medidas is not None:
        argv += ["--medidas-mm", ",".join(_num(m) for m in medidas),
                 "--casillas-por-medida", str(int(casillas_por_medida))]
    if luz:
        argv += ["--luz", str(luz)]
    outputs = [_rel(output)]
    if reporte:
        argv += ["--reporte", _rel(reporte)]
        outputs.append(_rel(reporte))
    return Receta(
        clave="calibrar_camara",
        descripcion=(f"Calibrar camara con tablero {cols}x{rows} @ "
                     f"{square_mm:.2f} mm medidos, detector {detector} "
                     f"(ESPACIO=vista, u=quitar, q=calibrar; "
                     f"autocierre {timeout}s)"),
        argv=argv,
        ventana_titulo=VENTANAS["calibrar_camara"],
        usa_camara=True,
        outputs=outputs,
    )


def receta_comprobar_escala(ruta_cfg, square_mm, detector, desplazamientos_mm,
                            salida, cols=8, rows=5,
                            frames_por_posicion=FRAMES_POR_POSICION, luz=None,
                            timeout=900):
    """Comprobacion de escala con regla (calibration/check_scale.py; meta 002,
    fase 4, P18). El perfil tiene que apuntar ya al .yml (el script para si
    no). square_mm y detector: los de la calibracion (el .yml los declara).
    desplazamientos_mm: lecturas de la regla, texto '0,80,0,80' o lista, >= 2.
    Todo explicito (principio 7)."""
    quien = "receta_comprobar_escala"
    if not salida:
        raise ValueError(f"{quien}: salida es obligatoria")
    square_mm = _validar_lado(square_mm, quien)
    if detector not in DETECTORES_ESCALA:
        raise ValueError(f"{quien}: detector {detector!r} no es uno de "
                         f"{DETECTORES_ESCALA} (el ganador de la calibracion)")
    posiciones = _parsear_numeros(desplazamientos_mm, "posiciones de la regla")
    if len(posiciones) < 2:
        raise ValueError(f"{quien}: hacen falta al menos 2 posiciones de la "
                         f"regla, hay {len(posiciones)}")
    if int(frames_por_posicion) < 1:
        raise ValueError(f"{quien}: frames_por_posicion >= 1")
    argv = _modulo("comprobar_escala") + [
        "--config", _rel(ruta_cfg),
        "--cols", str(int(cols)),
        "--rows", str(int(rows)),
        "--square-mm", f"{square_mm:.2f}",
        "--detector", str(detector),
        "--desplazamientos-mm", ",".join(_num(p) for p in posiciones),
        "--frames-por-posicion", str(int(frames_por_posicion)),
    ]
    if luz:
        argv += ["--luz", str(luz)]
    argv += ["--salida", _rel(salida), "--timeout", str(int(timeout))]
    return Receta(
        clave="comprobar_escala",
        descripcion=(f"Comprobar escala con regla en {','.join(_num(p) for p in posiciones)} mm "
                     f"(tablero {cols}x{rows} @ {square_mm:.2f} mm, detector {detector}; "
                     f"ESPACIO en cada posicion, q=salir; autocierre {timeout}s)"),
        argv=argv,
        ventana_titulo=VENTANAS["comprobar_escala"],
        usa_camara=True,
        outputs=[_rel(salida)],
    )


def receta_enfocar(ruta_cfg, ancho, alto, fourcc, fps, salida, luz=None,
                   timeout=600):
    """Enfocar el lente (diagnostics/measure_modes.py --enfocar; meta 002, fase 5,
    P19): la ventana con el numero de nitidez de la fase 3, en el modo del
    perfil. q termina; el JSON guarda la nitidez final y la maxima. Todo
    explicito (principio 7)."""
    quien = "receta_enfocar"
    if not salida:
        raise ValueError(f"{quien}: salida es obligatoria")
    try:
        ancho, alto, fps = int(ancho), int(alto), float(fps)
    except (TypeError, ValueError):
        raise ValueError(f"{quien}: el perfil tiene que declarar width, height "
                         f"y fps numericos (hay {ancho!r}, {alto!r}, {fps!r})")
    if ancho <= 0 or alto <= 0 or fps <= 0:
        raise ValueError(f"{quien}: width, height y fps tienen que ser > 0")
    fourcc = str(fourcc or "")
    if len(fourcc) != 4:
        raise ValueError(f"{quien}: fourcc de 4 letras (MJPG), no {fourcc!r}")
    argv = _modulo("enfocar") + [
        "--config", _rel(ruta_cfg),
        "--enfocar",
        "--modo", f"{ancho}x{alto}:{fourcc}",
        "--fps", _num(fps),
    ]
    if luz:
        argv += ["--luz", str(luz)]
    argv += ["--salida", _rel(salida), "--timeout", str(int(timeout))]
    return Receta(
        clave="enfocar",
        descripcion=(f"Enfocar el lente en {ancho}x{alto} {fourcc} {_num(fps)} fps "
                     f"(gira el lente hasta la nitidez mas alta; q=terminar; "
                     f"autocierre {timeout}s)"),
        argv=argv,
        ventana_titulo=VENTANAS["enfocar"],
        usa_camara=True,
        outputs=[_rel(salida)],
    )


def receta_sonda_camara(ruta_cfg):
    """Chequeo corto de camara bajo demanda (Paso 8): abre-lee-libera (webcam)
    o enumera dispositivos sin abrir pipeline (femtobolt). Con watchdog: si el
    driver se cuelga, el panel lo mata a los 20 s."""
    argv = _modulo("sonda_camara") + ["--config", _rel(ruta_cfg)]
    return Receta(
        clave="sonda_camara",
        descripcion="Probar camara (chequeo corto, libera el dispositivo al terminar)",
        argv=argv,
        ventana_titulo=None,
        usa_camara=True,
        timeout_s=20.0,
    )


if __name__ == "__main__":
    # Smoke check: imprime las recetas que no necesitan medidas para el perfil gs1.
    cfg = "profiles/tracker_config_gs1.yaml"
    print("[recetas] comandos que compondria el panel (perfil gs1):")
    for r in (receta_identificar_ids(cfg), receta_tracker_sin_ventana(cfg), receta_tracker(cfg),
              receta_sonda_camara(cfg)):
        print(f"\n  [{r.clave}] {r.descripcion}")
        print(f"    cwd={r.cwd}")
        print(f"    {r.comando_legible()}")
