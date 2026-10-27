# -*- coding: utf-8 -*-
"""
status.py — Estado del proyecto para el panel GUI (brief-01; era gui/estado.py).

Chequeos de prerrequisitos ("semaforos") SIN Qt: este modulo es usable y
verificable desde consola, y lo consume panel.py para pintar los semaforos.

Los chequeos leen el ESTADO REAL del repo (archivos en disco) derivando las
rutas del YAML del perfil activo — no hardcodean nombres de artefactos.

Meta 003, fase 3 (ADR-027): los perfiles viven en codigo/profiles/ y sus rutas
son relativas a codigo/ (`profiles`). Se van los semaforos de la geometria del
rigid body y de la punta: el dodecaedro y la punta estan archivados en
codigo/historico/iter4/dodecahedron/ (ADR-026; vuelven con el instrumento
nuevo, en otra meta). Un perfil que todavia define `rigid_bodies`, o uno de la
Femto Bolt (archivada, ADR-025), queda en ROJO: el panel no arranca el tracker
con el.

Uso por consola (desde codigo\\, con el venv):
    python -m gui.status --perfil profiles/tracker_config_gs1.yaml
"""
from __future__ import annotations

import argparse
import importlib.util
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

import profiles

# codigo/ y sus carpetas (independiente del CWD), de `profiles`.
RAIZ_CODIGO = profiles.CODE_ROOT
DIR_PERFILES = profiles.PROFILES_DIR
DIR_DATA = profiles.DATA_DIR

VERDE, AMARILLO, ROJO, GRIS = "VERDE", "AMARILLO", "ROJO", "GRIS"

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
    """Rutas (absolutas) de los codigo/profiles/tracker_config*.yaml disponibles."""
    return profiles.list_profiles()


def resolver_ruta(p):
    """La ruta `p` de un perfil resuelta como la resuelve el tracker
    (profiles.resolve_path: relativa a codigo/), o None si no existe."""
    if not p:
        return None
    try:
        return profiles.resolve_path(p)
    except FileNotFoundError:
        return None


def cargar_perfil(ruta_cfg):
    """Carga el YAML del perfil. Lanza excepcion si no parsea (fail-loud)."""
    with open(ruta_cfg, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# Chequeos individuales — cada uno devuelve un Chequeo
# ============================================================================

def chequear_config(ruta_cfg):
    """Config del perfil: existe, parsea, tiene las secciones minimas, es de
    webcam y no define rigid_bodies (el dodecaedro esta archivado)."""
    ruta_cfg = Path(ruta_cfg)
    if not ruta_cfg.exists():
        return Chequeo("config", "Config del perfil", ROJO,
                       f"no existe: {ruta_cfg}"), None
    try:
        cfg = cargar_perfil(ruta_cfg)
    except Exception as e:
        return Chequeo("config", "Config del perfil", ROJO,
                       f"YAML invalido: {e}"), None
    faltan = [s for s in ("camera", "markers", "igtlink")
              if s not in (cfg or {})]
    if faltan:
        return Chequeo("config", "Config del perfil", ROJO,
                       f"faltan secciones: {faltan}"), cfg
    ctype = str(cfg["camera"].get("camera_type", "")).lower()
    if ctype == "femtobolt":
        return Chequeo("config", "Config del perfil", ROJO,
                       "camera_type femtobolt: la Femto Bolt esta archivada "
                       "(codigo/historico/iter4/femto/, ADR-025)"), cfg
    if ctype != "webcam":
        return Chequeo("config", "Config del perfil", ROJO,
                       f"camera_type desconocido: '{ctype}'"), cfg
    if cfg.get("rigid_bodies"):
        return Chequeo("config", "Config del perfil", ROJO,
                       "define rigid_bodies: el dodecaedro esta archivado (ADR-026); "
                       "el tracker sigue solo Marker0 (markers.list)"), cfg
    return Chequeo("config", "Config del perfil", VERDE,
                   f"{ruta_cfg.name} (camera_type={ctype})"), cfg


def chequear_entorno(cfg):
    """venv + modulos importables. Usa find_spec (no ejecuta los modulos: no
    toca camara ni drivers)."""
    detalles = []
    estado = VERDE
    v = sys.version_info
    if (v.major, v.minor) != (3, 11):
        estado = AMARILLO
        detalles.append(f"Python {v.major}.{v.minor} (esperado 3.11)")
    else:
        detalles.append(f"Python {v.major}.{v.minor}.{v.micro}")
    modulos = list(MODULOS_BASE)
    faltan = [m for m in modulos if importlib.util.find_spec(m) is None]
    if faltan:
        estado = ROJO
        detalles.append(f"modulos FALTANTES: {faltan}")
    else:
        detalles.append(f"modulos OK: {modulos}")
    return Chequeo("entorno", "Entorno (venv y modulos)", estado, "; ".join(detalles))


def chequear_intrinsecos(cfg, ruta_cfg):
    """Intrinsecos de camara: el .yml del perfil (relativo a codigo/) existe y
    tiene camera_matrix + distortion_coefficients."""
    cam = (cfg or {}).get("camera", {}) or {}
    declarada = cam.get("calibration_file") or ""
    if not declarada:
        return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                       "webcam sin calibration_file en el perfil")
    ruta = resolver_ruta(declarada)
    if ruta is None:
        return Chequeo("intrinsecos", "Intrinsecos de camara", ROJO,
                       f"no existe: {declarada} (relativa a codigo/)")
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
    proceso). Se verifica bajo demanda con «Verificar IDs y colocar la cámara»
    (meta 004, fase 2b; P10): al cerrar bien, el panel la pone en verde
    (`chequeo_camara_tras_receta`)."""
    return Chequeo("camara", "Camara", GRIS,
                   "sin verificar — usar 'Verificar IDs y colocar la cámara' "
                   "(no se sondea sola)")


# Recetas cuyo fin dice algo de la camara. «Verificar IDs y colocar la cámara»
# abre con el backend entero (marca y ajustes del perfil, como el tracker); la
# sonda corta (`gui.camera_probe`) ya no tiene boton, pero su receta sigue.
CLAVES_CAMARA = ("identificar_ids", "sonda_camara")
# La linea de fps de `diagnostics.identify_ids` («[IDs] camara 89.9 fps»): gui/ no
# importa diagnostics/ (carga cv2), asi que el texto se fija aqui y la prueba lo compara.
PREFIJO_FPS_IDS = "[IDs] camara "


def _motivo_del_fallo(lineas):
    """La ultima linea que explica un fallo: la de «[ERROR]» o, si no hay, la
    ultima no vacia que no sea «[Salida limpia]» (p. ej. la del traceback)."""
    for ln in reversed(lineas):
        if ln.strip().startswith("[ERROR]"):
            return ln.strip()
    for ln in reversed(lineas):
        s = ln.strip()
        if s and s != "[Salida limpia]":
            return s
    return "sin salida"


def chequeo_camara_tras_receta(clave, rc, lineas, hora):
    """El semaforo «Camara» tras terminar una receta (meta 004, fase 2b; P10).

    `clave` y `rc`: la receta y su codigo de salida; `lineas`: lo que escribio;
    `hora`: «HH:MM:SS». Devuelve None si la receta no dice nada de la camara.
    Con «Verificar IDs y colocar la cámara»: codigo 0 = VERDE con los ultimos fps
    de la camara; otro codigo = ROJO con el motivo (fallar fuerte)."""
    if clave not in CLAVES_CAMARA:
        return None
    if clave == "sonda_camara":
        detalle = ""
        for ln in reversed(lineas):
            if ln.startswith("[CAMARA]"):
                detalle = ln.replace("[CAMARA] ", "")
                break
        est = VERDE if rc == 0 else ROJO
        return Chequeo("camara", "Camara", est, f"{detalle} (sondeada {hora})")
    if rc == 0:
        fps = [ln.strip() for ln in lineas
               if ln.strip().startswith(PREFIJO_FPS_IDS) and ln.strip().endswith(" fps")]
        medida = (f"entrega {fps[-1][len(PREFIJO_FPS_IDS):]}" if fps
                  else "abrio y cerro bien (sin medida de fps: se cerro antes de 5 s)")
        return Chequeo("camara", "Camara", VERDE,
                       f"la del perfil: {medida} (Verificar IDs, {hora})")
    return Chequeo("camara", "Camara", ROJO,
                   f"Verificar IDs fallo (exit {rc}): {_motivo_del_fallo(lineas)} ({hora})")


def evaluar_todo(ruta_cfg):
    """Corre todos los chequeos para el perfil dado. Orden estable para la UI."""
    chk_config, cfg = chequear_config(ruta_cfg)
    resultados = [
        chequear_entorno(cfg),
        chk_config,
        chequear_intrinsecos(cfg, ruta_cfg),
        chequear_puerto(cfg),
        chequear_camara_placeholder(),
    ]
    return resultados, cfg


def apto_para_tracker(chequeos):
    """Gating duro del tracker (brief §6): entorno + config + intrinsecos +
    puerto en VERDE. Los intrinsecos bloquean por ajuste aprobado 2026-08-13:
    un .yml faltante arrancaria el tracker con intrinsecos malos -> poses
    erroneas en silencio. Devuelve (bool, [claves malas])."""
    requeridos = ["entorno", "config", "intrinsecos", "puerto"]
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
    ap.add_argument("--perfil", required=True,
                    help="Ruta del perfil, relativa a codigo\\ o absoluta "
                         "(p. ej. profiles/tracker_config_gs1.yaml).")
    args = ap.parse_args()

    ruta_cfg = Path(args.perfil)
    if not ruta_cfg.is_absolute():
        ruta_cfg = RAIZ_CODIGO / args.perfil

    print(f"[estado] raiz codigo: {RAIZ_CODIGO}")
    print(f"[estado] perfiles disponibles: {[p.name for p in listar_perfiles()]}")
    print(f"[estado] perfil evaluado: {ruta_cfg}")
    chequeos, _cfg = evaluar_todo(ruta_cfg)
    _imprimir_chequeos(chequeos)
    ok, malos = apto_para_tracker(chequeos)
    print(f"[estado] apto para lanzar tracker: {'SI' if ok else 'NO'}"
          + ("" if ok else f" (bloquean: {malos})"))


if __name__ == "__main__":
    main()
