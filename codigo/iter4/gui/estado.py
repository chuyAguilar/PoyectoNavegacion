# -*- coding: utf-8 -*-
"""
estado.py — Estado del proyecto para el panel GUI (brief-01).

Chequeos de prerrequisitos ("semaforos") SIN Qt: este modulo es usable y
verificable desde consola, y lo consume panel.py para pintar los semaforos.

Los chequeos leen el ESTADO REAL del repo (archivos en disco) derivando las
rutas del YAML del perfil activo — no hardcodean nombres de artefactos.

Uso por consola (desde codigo\):
    python iter4\gui\estado.py                                    # perfil canonico
    python iter4\gui\estado.py --perfil iter4/tracker_config_doctor.yaml
    python iter4\gui\estado.py --puntas    # coherencia de TODAS las puntas vs el perfil
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# gui/ -> iter4/ -> codigo/   (independiente del CWD)
RAIZ_CODIGO = Path(__file__).resolve().parents[2]
DIR_ITER4 = RAIZ_CODIGO / "iter4"
DIR_DATA = DIR_ITER4 / "data"

VERDE, AMARILLO, ROJO, GRIS = "VERDE", "AMARILLO", "ROJO", "GRIS"

# Punta preferida por perfil (ADR-015 fija femto_dock como vigente del contexto
# canonico; el manual del doctor genera _doctor_dock). Si el perfil no esta o
# el archivo falta, se evalua la mas reciente por mtime (que es la que cargaria
# el snippet de Slicer del MANUAL_simplificado §4.2).
PUNTAS_PREFERIDAS = {
    "tracker_config.yaml": "StylusTipToDodecaedro_femto_dock.npy",
    "tracker_config_doctor.yaml": "StylusTipToDodecaedro_doctor_dock.npy",
}

MODULOS_BASE = ["cv2", "numpy", "scipy", "yaml", "pyigtl"]


@dataclass
class Chequeo:
    clave: str
    titulo: str
    estado: str      # VERDE | AMARILLO | ROJO | GRIS
    detalle: str


# ============================================================================
# Perfiles
# ============================================================================

def listar_perfiles():
    """Rutas (absolutas) de los iter4/tracker_config*.yaml disponibles."""
    return sorted(DIR_ITER4.glob("tracker_config*.yaml"))


def resolver_ruta(p, cfg_dir):
    """Misma semantica que cargar_config() de los scripts: prueba la ruta tal
    cual relativa a codigo\\ y luego relativa al directorio del config."""
    if not p:
        return None
    for cand in (RAIZ_CODIGO / p, Path(cfg_dir) / p):
        if cand.exists():
            return cand.resolve()
    return None


def cargar_perfil(ruta_cfg):
    """Carga el YAML del perfil. Lanza excepcion si no parsea (fail-loud)."""
    with open(ruta_cfg, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# Chequeos individuales — cada uno devuelve un Chequeo
# ============================================================================

def chequear_config(ruta_cfg):
    """Config del perfil: existe, parsea y tiene las secciones minimas."""
    ruta_cfg = Path(ruta_cfg)
    if not ruta_cfg.exists():
        return Chequeo("config", "Config del perfil", ROJO,
                       f"no existe: {ruta_cfg}"), None
    try:
        cfg = cargar_perfil(ruta_cfg)
    except Exception as e:
        return Chequeo("config", "Config del perfil", ROJO,
                       f"YAML invalido: {e}"), None
    faltan = [s for s in ("camera", "markers", "rigid_bodies", "igtlink")
              if s not in (cfg or {})]
    if faltan:
        return Chequeo("config", "Config del perfil", ROJO,
                       f"faltan secciones: {faltan}"), cfg
    ctype = str(cfg["camera"].get("camera_type", "")).lower()
    if ctype not in ("webcam", "femtobolt"):
        return Chequeo("config", "Config del perfil", ROJO,
                       f"camera_type desconocido: '{ctype}'"), cfg
    return Chequeo("config", "Config del perfil", VERDE,
                   f"{ruta_cfg.name} (camera_type={ctype})"), cfg


def chequear_entorno(cfg):
    """venv + modulos importables. pyorbbecsdk solo si el perfil es femtobolt.
    Usa find_spec (no ejecuta los modulos: no toca camara ni drivers)."""
    detalles = []
    estado = VERDE
    v = sys.version_info
    if (v.major, v.minor) != (3, 11):
        estado = AMARILLO
        detalles.append(f"Python {v.major}.{v.minor} (esperado 3.11)")
    else:
        detalles.append(f"Python {v.major}.{v.minor}.{v.micro}")
    modulos = list(MODULOS_BASE)
    if cfg and str(cfg.get("camera", {}).get("camera_type", "")).lower() == "femtobolt":
        modulos.append("pyorbbecsdk")
    faltan = [m for m in modulos if importlib.util.find_spec(m) is None]
    if faltan:
        estado = ROJO
        detalles.append(f"modulos FALTANTES: {faltan}")
    else:
        detalles.append(f"modulos OK: {modulos}")
    return Chequeo("entorno", "Entorno (venv y modulos)", estado, "; ".join(detalles))


def parsear_geometria(ruta):
    """Lee un reference_*.txt. Devuelve lista de IDs (lineas de >=16 tokens)."""
    ids = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            vals = linea.split()
            if len(vals) >= 16:
                ids.append(int(vals[0]))
    return ids


def geometria_del_perfil(cfg, ruta_cfg):
    """Ruta resuelta del geometry_file del primer rigid body (o None)."""
    rbs = (cfg or {}).get("rigid_bodies") or []
    if not rbs:
        return None
    return resolver_ruta(rbs[0].get("geometry_file"), Path(ruta_cfg).parent)


def chequear_geometria(cfg, ruta_cfg):
    """Geometria del rigid body: existe, parsea, y es CALIBRADA (CONTEXT §4.8:
    la teorica no se usa para operar una vez hecho el BA)."""
    rbs = (cfg or {}).get("rigid_bodies") or []
    if not rbs:
        return Chequeo("geometria", "Geometria del rigid body", ROJO,
                       "el perfil no define rigid_bodies")
    declarada = rbs[0].get("geometry_file", "")
    ruta = geometria_del_perfil(cfg, ruta_cfg)
    if ruta is None:
        return Chequeo("geometria", "Geometria del rigid body", ROJO,
                       f"no existe: {declarada}")
    try:
        ids = parsear_geometria(ruta)
    except Exception as e:
        return Chequeo("geometria", "Geometria del rigid body", ROJO,
                       f"{ruta.name}: ilegible ({e})")
    if not ids:
        return Chequeo("geometria", "Geometria del rigid body", ROJO,
                       f"{ruta.name}: sin lineas validas (archivo vacio/corrupto)")
    base = f"{ruta.name}: {len(ids)} markers, IDs {min(ids)}-{max(ids)}"
    if "calibrado" not in ruta.name.lower():
        return Chequeo("geometria", "Geometria del rigid body", AMARILLO,
                       base + " — TEORICA (sin calibrar): no operar el tracker con esta")
    return Chequeo("geometria", "Geometria del rigid body", VERDE, base)


def chequear_intrinsecos(cfg, ruta_cfg):
    """Intrinsecos de camara. Femto: fabrica del SDK => VERDE con
    calibration_file vacio (ajuste aprobado #2); si esta seteado debe existir.
    Webcam: el .yml debe existir y tener camera_matrix + distortion."""
    cam = (cfg or {}).get("camera", {}) or {}
    ctype = str(cam.get("camera_type", "")).lower()
    declarada = cam.get("calibration_file") or ""
    if ctype == "femtobolt":
        if not declarada:
            return Chequeo("intrinsecos", "Intrinsecos de camara", VERDE,
                           "calibracion de fabrica del SDK (calibration_file vacio)")
        ruta = resolver_ruta(declarada, Path(ruta_cfg).parent)
        if ruta is None:
            return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                           f"override declarado pero no existe: {declarada}")
        return Chequeo("intrinsecos", "Intrinsecos de camara", VERDE,
                       f"override: {ruta.name}")
    # webcam
    if not declarada:
        return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                       "webcam sin calibration_file en el perfil")
    ruta = resolver_ruta(declarada, Path(ruta_cfg).parent)
    if ruta is None:
        return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                       f"no existe: {declarada}")
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                       f"{ruta.name}: ilegible ({e})")
    faltan = [k for k in ("camera_matrix", "distortion_coefficients")
              if k not in texto]
    if faltan:
        return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                       f"{ruta.name}: faltan claves {faltan}")
    return Chequeo("intrinsecos", "Intrinsecos de camara", VERDE, ruta.name)


def _sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def shas_de_geometria(ruta_geom):
    """(sha16 crudo, sha16 con EOL normalizado CRLF->LF). El fallback cubre el
    caso de que git haya renormalizado el .txt despues de calculado el sha
    del header de la punta (riesgo detectado en el plan)."""
    raw = Path(ruta_geom).read_bytes()
    return _sha16(raw), _sha16(raw.replace(b"\r\n", b"\n"))


RE_HEADER_GEOM = re.compile(
    r"Geometria dodecaedro:\s*(\S+)\s*\(sha\s*([0-9a-fA-F]{8,})\)")
RE_MAGNITUD = re.compile(r"Magnitud:\s*([\d.]+)")
RE_SPREAD = re.compile(r"spread:\s*\[([^\]]+)\]")


def coherencia_punta(ruta_npy, ruta_geom):
    """Evalua la coherencia punta<->geometria por el sha16 del header del .txt
    (escrito por calibrar_tip_divot.py). Devuelve (estado, detalle)."""
    txt = Path(ruta_npy).with_suffix(".txt")
    if not txt.exists():
        return AMARILLO, "sin .txt de metadata (calibracion legacy): coherencia no verificable"
    contenido = txt.read_text(encoding="utf-8", errors="replace")
    m = RE_HEADER_GEOM.search(contenido)
    extras = []
    mm = RE_MAGNITUD.search(contenido)
    if mm:
        extras.append(f"magnitud {mm.group(1)} mm")
    ms = RE_SPREAD.search(contenido)
    if ms:
        extras.append(f"spread [{ms.group(1)}] mm")
    extra = (" | " + ", ".join(extras)) if extras else ""
    if not m:
        return AMARILLO, "el .txt no referencia geometria (formato viejo)" + extra
    ref_path, ref_sha = m.group(1), m.group(2)[:16].lower()
    if ruta_geom is None or not Path(ruta_geom).exists():
        return ROJO, "no hay geometria en el perfil contra la cual verificar"
    sha_raw, sha_norm = shas_de_geometria(ruta_geom)
    if ref_sha in (sha_raw, sha_norm):
        return VERDE, f"COHERENTE con {Path(ruta_geom).name} (sha {ref_sha})" + extra
    if Path(ref_path).name == Path(ruta_geom).name:
        return AMARILLO, (f"referencia {Path(ref_path).name} por nombre pero el sha difiere "
                          f"({ref_sha} vs {sha_raw}) — ¿geometria regenerada despues de "
                          f"calibrar la punta?") + extra
    return ROJO, (f"punta de OTRO ensamble (calibrada contra {Path(ref_path).name}); "
                  f"no usar con este perfil") + extra


def listar_puntas():
    """Todas las puntas .npy en data\\, ordenadas por mtime descendente.
    Mismo glob que el snippet de Slicer del manual (§4.2), SIN guion bajo,
    para evaluar exactamente lo que Slicer cargaria."""
    return sorted(DIR_DATA.glob("StylusTipToDodecaedro*.npy"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def chequear_punta(cfg, ruta_cfg):
    """Punta activa del perfil + coherencia con la geometria del perfil.
    Evalua la punta PREFERIDA del perfil si existe; si no, la mas reciente
    (comportamiento del snippet de Slicer del manual). Avisa si la mas
    reciente por mtime NO es la evaluada (Slicer cargaria esa otra)."""
    puntas = listar_puntas()
    if not puntas:
        return Chequeo("punta", "Calibracion de punta", ROJO,
                       f"no hay StylusTipToDodecaedro_*.npy en {DIR_DATA}")
    preferida_nombre = PUNTAS_PREFERIDAS.get(Path(ruta_cfg).name)
    evaluada = None
    nota = ""
    falta_preferida = False
    if preferida_nombre:
        cand = DIR_DATA / preferida_nombre
        if cand.exists():
            evaluada = cand
        else:
            # La punta propia del perfil no existe: aunque el fallback sea
            # coherente con la geometria, el LARGO es propio de cada stylus
            # -> nunca VERDE en este caso.
            falta_preferida = True
            nota = (f"preferida del perfil ({preferida_nombre}) NO existe "
                    f"(calibrar con el dock); ")
    if evaluada is None:
        evaluada = puntas[0]
        nota += "evaluando la mas reciente por fecha; "
    ruta_geom = geometria_del_perfil(cfg, ruta_cfg)
    estado, detalle = coherencia_punta(evaluada, ruta_geom)
    if falta_preferida and estado == VERDE:
        estado = AMARILLO
    mas_reciente = puntas[0]
    if mas_reciente != evaluada:
        nota += (f"OJO: la mas reciente es {mas_reciente.name} — el snippet de "
                 f"Slicer (manual §4.2) cargaria ESA; ")
        if estado == VERDE:
            estado = AMARILLO
    return Chequeo("punta", "Calibracion de punta", estado,
                   f"{evaluada.name}: {nota}{detalle}")


def chequear_puerto(cfg):
    """Puerto OpenIGTLink libre (nadie escuchando = se puede lanzar tracker)."""
    puerto = int(((cfg or {}).get("igtlink") or {}).get("transforms_port", 18944))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", puerto))
        s.close()
        return Chequeo("puerto", f"Puerto OpenIGTLink {puerto}", VERDE, "libre")
    except OSError:
        return Chequeo("puerto", f"Puerto OpenIGTLink {puerto}", ROJO,
                       "EN USO — ¿ya hay un tracker corriendo?")
    finally:
        try:
            s.close()
        except OSError:
            pass


def chequear_camara_placeholder():
    """La camara no se sondea automaticamente (no robarle el dispositivo a un
    proceso). Sondeo bajo demanda: boton 'Probar camara' (Paso 8)."""
    return Chequeo("camara", "Camara", GRIS,
                   "sin verificar — usar 'Probar camara' (no se sondea sola)")


def evaluar_todo(ruta_cfg):
    """Corre todos los chequeos para el perfil dado. Orden estable para la UI."""
    chk_config, cfg = chequear_config(ruta_cfg)
    resultados = [
        chequear_entorno(cfg),
        chk_config,
        chequear_geometria(cfg, ruta_cfg),
        chequear_intrinsecos(cfg, ruta_cfg),
        chequear_punta(cfg, ruta_cfg),
        chequear_puerto(cfg),
        chequear_camara_placeholder(),
    ]
    return resultados, cfg


def apto_para_tracker(chequeos):
    """Gating duro del tracker (brief §6): entorno + config + geometria
    CALIBRADA + intrinsecos + puerto en VERDE. Los intrinsecos bloquean por
    ajuste aprobado 2026-08-13: en el contexto webcam, un .yml faltante
    arrancaria el tracker con intrinsecos malos -> poses erroneas en silencio.
    Devuelve (bool, [claves malas])."""
    requeridos = ("entorno", "config", "geometria", "intrinsecos", "puerto")
    malos = [c.clave for c in chequeos
             if c.clave in requeridos and c.estado != VERDE]
    return (not malos), malos


# ============================================================================
# CLI de verificacion (sin GUI)
# ============================================================================

def _imprimir_chequeos(chequeos):
    for c in chequeos:
        print(f"  [{c.estado:8s}] {c.titulo}: {c.detalle}")


def main():
    ap = argparse.ArgumentParser(description="Semaforos del panel (sin GUI).")
    ap.add_argument("--perfil", default="iter4/tracker_config.yaml",
                    help="Ruta del config, relativa a codigo\\ o absoluta.")
    ap.add_argument("--puntas", action="store_true",
                    help="Ademas, coherencia de TODAS las puntas vs el perfil.")
    args = ap.parse_args()

    ruta_cfg = Path(args.perfil)
    if not ruta_cfg.is_absolute():
        ruta_cfg = RAIZ_CODIGO / args.perfil

    print(f"[estado] raiz codigo: {RAIZ_CODIGO}")
    print(f"[estado] perfiles disponibles: {[p.name for p in listar_perfiles()]}")
    print(f"[estado] perfil evaluado: {ruta_cfg}")
    chequeos, cfg = evaluar_todo(ruta_cfg)
    _imprimir_chequeos(chequeos)
    ok, malos = apto_para_tracker(chequeos)
    print(f"[estado] apto para lanzar tracker: {'SI' if ok else 'NO'}"
          + ("" if ok else f" (bloquean: {malos})"))

    if args.puntas:
        print("[estado] coherencia de todas las puntas vs geometria del perfil:")
        ruta_geom = geometria_del_perfil(cfg, ruta_cfg)
        for p in listar_puntas():
            estado, detalle = coherencia_punta(p, ruta_geom)
            print(f"  [{estado:8s}] {p.name}: {detalle}")


if __name__ == "__main__":
    main()
