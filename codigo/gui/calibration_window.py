# -*- coding: utf-8 -*-
"""
calibration_window.py — Lo que hay detras de la ventana "Calibrar camara" del
panel (meta 002, fase 5; P19, P20, P21; era gui/calibracion.py). SIN Qt, para
poder probarlo sin pantalla.

La ventana tiene tres pasos sin campos: 1 enfocar el lente, 2 calibrar con el
tablero, 3 comprobar la escala con la regla. Todo lo fijo vive aqui y no se
ve en la ventana: las esquinas del tablero, el detector "ambos", las vistas
minimas y de control, la luz, las salidas por perfil y modo, los autocierres.
Los argumentos siguen yendo explicitos a los scripts (principio 7).

El tablero se guarda en un archivo versionado, data/tablero_calibracion.yaml
(P17: 9x6 casillas, medidas 149.1 x4 y 149.4 sobre 6 casillas, 24.86 mm). La
calibracion lo usa siempre; "Volver a medir el tablero..." lo reescribe.

"Ultima ..." de cada paso sale de los JSON/.yml que ya existen para el perfil,
en lenguaje llano (P21): sin "RMS", "control" ni "detector" a la vista.

Context7 (2026-10-23): PyYAML 6.0 (/yaml/pyyaml): safe_load devuelve tipos
basicos de Python; el archivo del tablero se escribe como texto con su
cabecera de comentarios (safe_dump los perderia).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

import profiles
from gui import recipes as recetas

RUTA_TABLERO = profiles.DATA_DIR / "tablero_calibracion.yaml"
DIR_CAMARAS = "../Claude outputs/camaras"      # relativo a codigo\ (CWD de los procesos)

# Lo fijo de la ventana (P21): no se ve, va en los argumentos.
DETECTOR = "ambos"            # calibra con los dos y gana el de menor error en las fotos de control
MIN_VISTAS = 15
N_CONTROL = 3
TIMEOUT_CALIBRAR = 900
TIMEOUT_ESCALA = 900
TIMEOUT_ENFOCAR = 600
RECORRIDO_MM = 80             # la caja de luz deja 80 mm (fase 4)
IDAS_Y_VUELTAS = 3            # 0,80,0,80,0,80
LIMITE_ERROR_PX = 0.75        # calibrar_camara.CRITERIO["rms_control_px"] (una prueba lo ata)
MEDIDAS_TABLERO = recetas.MIN_MEDIDAS
MAX_CASILLAS_POR_MEDIDA = 9

OK, MAL = "✔", "✘"   # ✔ ✘


# ----------------------------------------------------------------------------
# El tablero guardado
# ----------------------------------------------------------------------------

@dataclass
class Tablero:
    casillas: tuple            # (horizontales, verticales)
    medidas_mm: list
    casillas_por_medida: int
    lado_mm: float
    fecha: str = ""
    fuente: str = ""

    @property
    def esquinas(self):
        """Esquinas interiores (cols, rows) = casillas - 1."""
        return (self.casillas[0] - 1, self.casillas[1] - 1)


def _entero(d, clave):
    v = d.get(clave)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"tablero: {clave} tiene que ser un entero, no {v!r}")
    return v


def validar_tablero(d) -> Tablero:
    """Del dict leido al Tablero, comprobando todo (ValueError con el motivo)."""
    if not isinstance(d, dict):
        raise ValueError("el archivo del tablero no es un mapa clave: valor")
    ch, cv = _entero(d, "casillas_horizontales"), _entero(d, "casillas_verticales")
    if not (3 <= ch <= 30 and 3 <= cv <= 30):
        raise ValueError(f"tablero: casillas {ch}x{cv} fuera de rango (3-30)")
    if (d.get("esquinas_horizontales"), d.get("esquinas_verticales")) != (ch - 1, cv - 1):
        raise ValueError(f"tablero: las esquinas interiores tienen que ser {ch - 1}x{cv - 1} "
                         f"(las casillas menos una)")
    medidas = d.get("medidas_mm")
    if not isinstance(medidas, list):
        raise ValueError("tablero: medidas_mm tiene que ser una lista de numeros")
    medidas = recetas.parsear_medidas([str(m) for m in medidas])
    if len(medidas) < MEDIDAS_TABLERO:
        raise ValueError(f"tablero: hacen falta al menos {MEDIDAS_TABLERO} medidas, hay {len(medidas)}")
    casillas = _entero(d, "casillas_por_medida")
    if not (1 <= casillas <= max(ch, cv)):
        raise ValueError(f"tablero: casillas_por_medida {casillas} fuera de rango (1-{max(ch, cv)})")
    lado = recetas.lado_de_medidas(medidas, casillas)
    try:
        declarado = float(d.get("lado_mm"))
    except (TypeError, ValueError):
        raise ValueError(f"tablero: lado_mm tiene que ser un numero, no {d.get('lado_mm')!r}")
    if abs(declarado - lado) > recetas.TOLERANCIA_LADO_MM + 1e-9:
        raise ValueError(f"tablero: lado_mm {declarado} no sale de las medidas ({lado:.2f} mm)")
    recetas._validar_lado(lado, "tablero")
    return Tablero((ch, cv), medidas, casillas, lado, str(d.get("fecha") or ""), str(d.get("fuente") or ""))


def leer_tablero(ruta=RUTA_TABLERO) -> Tablero:
    """El tablero guardado. OSError si no se puede leer; ValueError si no vale."""
    texto = Path(ruta).read_text(encoding="utf-8")
    try:
        d = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise ValueError(f"{Path(ruta).name} no es YAML valido: {e}")
    return validar_tablero(d)


CABECERA = """# Tablero de calibracion de camara (meta 002). Lo lee la ventana
# "Calibrar camara" del panel y lo reescribe "Volver a medir el tablero...".
# Medidas con calibrador digital, de la orilla de arriba de un cuadro negro a
# la orilla de arriba de otro (la misma orilla: el engrosamiento se cancela).
# lado_mm = media de las medidas / casillas_por_medida, con dos decimales.
# Las esquinas interiores son las casillas menos una en cada eje.
"""


def texto_tablero(t: Tablero) -> str:
    medidas = ", ".join(recetas._num(m) for m in t.medidas_mm)
    return (CABECERA
            + f"casillas_horizontales: {t.casillas[0]}\n"
            + f"casillas_verticales: {t.casillas[1]}\n"
            + f"esquinas_horizontales: {t.esquinas[0]}\n"
            + f"esquinas_verticales: {t.esquinas[1]}\n"
            + f"medidas_mm: [{medidas}]\n"
            + f"casillas_por_medida: {t.casillas_por_medida}\n"
            + f"lado_mm: {t.lado_mm:.2f}\n"
            + f'fecha: "{t.fecha}"\n'
            + f'fuente: "{t.fuente}"\n')


def escribir_tablero(ruta, medidas, casillas_por_medida, casillas=None, fecha=None,
                     fuente="panel") -> Tablero:
    """Reescribe el tablero con medidas nuevas (las casillas del tablero se conservan si el
    archivo existe y vale; si no, 9x6). Valida ANTES de escribir; escribe a un temporal y lo
    cambia por el archivo (nunca queda a medias). Devuelve el Tablero escrito."""
    ruta = Path(ruta)
    if casillas is None:
        try:
            casillas = leer_tablero(ruta).casillas
        except (OSError, ValueError):
            casillas = (9, 6)
    medidas = recetas.parsear_medidas(medidas)
    casillas_por_medida = int(casillas_por_medida)
    if not (1 <= casillas_por_medida <= MAX_CASILLAS_POR_MEDIDA):
        raise ValueError(f"los cuadros entre las dos puntas tienen que ser de 1 a "
                         f"{MAX_CASILLAS_POR_MEDIDA}, no {casillas_por_medida}")
    if len(medidas) < MEDIDAS_TABLERO:
        raise ValueError(f"hacen falta {MEDIDAS_TABLERO} medidas; hay {len(medidas)}")
    lado = recetas.lado_de_medidas(medidas, casillas_por_medida)
    t = Tablero(tuple(int(c) for c in casillas), medidas, casillas_por_medida, lado,
                fecha or time.strftime("%Y-%m-%d"), fuente)
    texto = texto_tablero(t)
    validar_tablero(yaml.safe_load(texto))          # lo que se escribe se vuelve a leer igual
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8", newline="\n")
    os.replace(tmp, ruta)
    return t


# ----------------------------------------------------------------------------
# Las salidas por perfil y las tres recetas
# ----------------------------------------------------------------------------

def _cam(cfg):
    return ((cfg or {}).get("camera") or {})


def modo_del_perfil(cfg) -> str:
    """'1280x960' del perfil, o ValueError si no lo declara."""
    cam = _cam(cfg)
    if not cam.get("width") or not cam.get("height"):
        raise ValueError("el perfil no declara camera.width y camera.height")
    return f"{int(cam['width'])}x{int(cam['height'])}"


def salidas_del_perfil(ruta_cfg, cfg) -> dict:
    """Las rutas fijas de cada paso para el perfil (relativas a codigo\\)."""
    slug = recetas.slug_de_perfil(ruta_cfg)
    vistas = f"{DIR_CAMARAS}/vistas_{slug}"
    return {
        "slug": slug,
        "yml": f"data/intrinsecos_{slug}_{modo_del_perfil(cfg)}.yml",
        "vistas": vistas,
        "reporte": recetas.reporte_por_defecto(vistas, slug, DETECTOR),
        "escala": f"{DIR_CAMARAS}/escala_{slug}.json",
        "enfoque": f"{DIR_CAMARAS}/enfoque_{slug}.json",
    }


def receta_enfocar_perfil(ruta_cfg, cfg):
    """Paso 1 (P19): medir_modos.py --enfocar con el modo y los fps del perfil."""
    cam = _cam(cfg)
    if not cam.get("usb_port_windows"):
        raise ValueError("el perfil no dice en que puerto USB esta la camara (usb_port_windows)")
    return recetas.receta_enfocar(ruta_cfg, cam.get("width"), cam.get("height"), cam.get("fourcc"),
                                  cam.get("fps"), salidas_del_perfil(ruta_cfg, cfg)["enfoque"],
                                  luz=recetas.LUZ_POR_DEFECTO, timeout=TIMEOUT_ENFOCAR)


def receta_calibrar_perfil(ruta_cfg, cfg, tablero: Tablero):
    """Paso 2: calibrar_camara.py con el tablero guardado y todo lo fijo."""
    s = salidas_del_perfil(ruta_cfg, cfg)
    cols, rows = tablero.esquinas
    return recetas.receta_calibrar_camara(
        ruta_cfg, output=s["yml"], square_mm=tablero.lado_mm, vistas_dir=s["vistas"],
        cols=cols, rows=rows, detector=DETECTOR, min_vistas=MIN_VISTAS, n_control=N_CONTROL,
        timeout=TIMEOUT_CALIBRAR, luz=recetas.LUZ_POR_DEFECTO, medidas_mm=tablero.medidas_mm,
        casillas_por_medida=tablero.casillas_por_medida, reporte=s["reporte"])


def posiciones_ida_vuelta(recorrido_mm, idas_y_vueltas) -> list:
    """80 y 3 -> [0, 80, 0, 80, 0, 80]: cada ida y vuelta, una lectura en cada marca."""
    try:
        recorrido, n = float(recorrido_mm), int(idas_y_vueltas)
    except (TypeError, ValueError):
        raise ValueError("la distancia y las veces tienen que ser numeros")
    if recorrido <= 0:
        raise ValueError("la distancia entre las dos marcas tiene que ser mayor que 0")
    if n < 1:
        raise ValueError("hay que ir y volver al menos una vez")
    return [0.0, recorrido] * n


def receta_escala_perfil(ruta_cfg, ruta_yml, tablero: Tablero, recorrido_mm=RECORRIDO_MM,
                         idas_y_vueltas=IDAS_Y_VUELTAS):
    """Paso 3: comprobar_escala.py con el lado y el detector que declara el .yml del perfil
    (los de la calibracion) y las posiciones de ida y vuelta."""
    from gui.profile_editor import leer_campos_yml
    campos = leer_campos_yml(ruta_yml)
    detector = campos.get("detector")
    if detector not in recetas.DETECTORES_ESCALA:
        raise ValueError(f"{Path(ruta_yml).name} no dice con que detector se calibro: "
                         f"vuelve a calibrar (paso 2)")
    try:
        lado = round(float(campos.get("square_mm")), 2)
    except (TypeError, ValueError):
        raise ValueError(f"{Path(ruta_yml).name} no dice cuanto mide cada cuadro: vuelve a calibrar (paso 2)")
    cols, rows = tablero.esquinas
    slug = recetas.slug_de_perfil(ruta_cfg)
    return recetas.receta_comprobar_escala(
        ruta_cfg, square_mm=lado, detector=detector,
        desplazamientos_mm=posiciones_ida_vuelta(recorrido_mm, idas_y_vueltas),
        salida=f"{DIR_CAMARAS}/escala_{slug}.json", cols=cols, rows=rows,
        frames_por_posicion=recetas.FRAMES_POR_POSICION, luz=recetas.LUZ_POR_DEFECTO,
        timeout=TIMEOUT_ESCALA)


# ----------------------------------------------------------------------------
# "Ultima ..." de cada paso, en lenguaje llano
# ----------------------------------------------------------------------------

def _abs(ruta):
    p = Path(ruta)
    return p if p.is_absolute() else recetas.RAIZ_CODIGO / p


def dia_mes(fecha) -> str:
    """'2026-10-23 14:05:49' -> '23-10'. Una fecha con zona ('2026-10-23T04:25:00+00:00', la UTC
    del .yml) se pasa antes a la hora local: la calibracion de las 22:25 del 22 es el 22, no el 23.
    '' si no se entiende."""
    f = str(fecha or "")
    try:
        d = datetime.fromisoformat(f)
    except ValueError:
        d = None
    if d is not None and d.tzinfo is not None:
        d = d.astimezone()
        return f"{d.day:02d}-{d.month:02d}"
    if len(f) >= 10 and f[4] == "-" and f[7] == "-":
        return f"{f[8:10]}-{f[5:7]}"
    return ""


def _leer_json(ruta):
    try:
        return json.loads(_abs(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ultima_nitidez(ruta_json) -> str:
    """'nitidez 156 (22-10)', o '—' si no hay medida."""
    d = _leer_json(ruta_json)
    if not d:
        return "—"
    if d.get("error"):
        return f"no se pudo medir ({dia_mes(d.get('fecha'))}); el motivo está en el registro del panel"
    n = (d.get("enfoque") or {}).get("nitidez")
    if n is None:
        return "—"
    return f"nitidez {float(n):.0f} ({dia_mes(d.get('fecha'))})"


def _calibracion_desde_reporte(d):
    fecha = dia_mes(d.get("fecha"))
    r = d.get("resultado") or {}
    if "rms_control_px" not in r:
        return f"La última calibración ({fecha}) no terminó; el motivo está en el registro del panel", False
    limite = float((d.get("criterio") or {}).get("rms_control_px", LIMITE_ERROR_PX))
    return _texto_calibracion(fecha, float(r["rms_control_px"]), limite, bool(r.get("cumple")))


def _texto_calibracion(fecha, error_px, limite, ok):
    texto = f"Calibrada el {fecha} · error {error_px:.2f} píxeles (aceptable hasta {limite:.2f})"
    if not ok:
        texto += " · no salió bien; el detalle está en el registro"
    return texto, ok


def _calibracion_desde_yml(ruta):
    from gui.profile_editor import leer_campos_yml
    try:
        c = leer_campos_yml(ruta)
    except OSError:
        return None
    try:
        error_px = float(c.get("rms_control_px"))
    except (TypeError, ValueError):
        return None
    return _texto_calibracion(dia_mes(c.get("generated_at_utc")), error_px, LIMITE_ERROR_PX,
                              c.get("criterio_cumplido") == "1")


def ultima_calibracion(ruta_reporte, ruta_yml):
    """(texto, ok) de la calibracion mas reciente del perfil: el reporte JSON o el .yml, el que
    sea mas nuevo. ('—', None) si no hay ninguno."""
    candidatos = [p for p in (_abs(ruta_reporte), _abs(ruta_yml)) if p.is_file()]
    for p in sorted(candidatos, key=lambda p: p.stat().st_mtime, reverse=True):
        if p.suffix.lower() == ".json":
            d = _leer_json(p)
            if d:
                return _calibracion_desde_reporte(d)
        else:
            r = _calibracion_desde_yml(p)
            if r:
                return r
    return "—", None


def ultima_escala(ruta_json):
    """(texto, ok) de la ultima comprobacion de escala del perfil. ('—', None) si no hay."""
    d = _leer_json(ruta_json)
    if not d:
        return "—", None
    fecha = dia_mes(d.get("fecha"))
    p = d.get("peor")
    if d.get("criterio") and p:
        ok = bool(d.get("cumple"))
        texto = (f"La cámara midió {float(p['paso_medido_mm']):.1f} mm donde la regla dice "
                 f"{float(p['paso_regla_mm']):g} (diferencia {abs(float(p['error_mm'])):.1f} mm; "
                 f"aceptable hasta {float(p['tolerancia_mm']):.1f})")
        return texto, ok
    if d.get("error"):
        return f"La última comprobación ({fecha}) no terminó; el motivo está en el registro del panel", False
    if "cumple" in d:
        return (f"Comprobada el {fecha} con la cuenta anterior "
                f"({'salía bien' if d['cumple'] else 'no salía bien'}); vuelve a comprobarla"), None
    return "—", None


def marca(ok) -> str:
    """' ✔', ' ✘' o '' (sin criterio o sin dato)."""
    return "" if ok is None else (f" {OK}" if ok else f" {MAL}")
