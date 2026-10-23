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
    "comprobar_escala": "Comprobar escala - ESPACIO posicion, q salir",
    "enfocar": "medir_modos - q para interrumpir",     # medir_modos.VENTANA (P19)
}

# Slug corto por perfil para nombrar outputs (captura_ba_<slug>.npz, etc.).
SLUGS = {
    "tracker_config.yaml": "femto",
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
    calibrar_camara.lado_desde_medidas; gui\\ no importa iter4\\)."""
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
    """Calibracion intrinseca con tablero (iter4/calibrar_camara.py; meta 002,
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
    argv = [
        _python(), "-u", "iter4/calibrar_camara.py",
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
    """Comprobacion de escala con regla (iter4/comprobar_escala.py; meta 002,
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
    argv = [
        _python(), "-u", "iter4/comprobar_escala.py",
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
    """Enfocar el lente (iter4/medir_modos.py --enfocar; meta 002, fase 5,
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
    argv = [
        _python(), "-u", "iter4/medir_modos.py",
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
