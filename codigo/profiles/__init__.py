"""Los perfiles del tracker y las rutas del codigo (meta 003, fase 3; ADR-027).

Una sola copia de la carga de un perfil: antes habia dos `cargar_config`
iguales (tracker.py y captura_calibracion.py) que probaban la ruta relativa al
CWD y a la carpeta del perfil. Ahora toda ruta de un perfil (`geometry_file`
de un rigid body, `camera.calibration_file`) es relativa a `codigo/`
(`CODE_ROOT`), nunca al CWD ni a la carpeta del perfil, y si no existe se
aborta con el nombre del perfil y la ruta (principio 7).

Los perfiles viven en `codigo/profiles/` (`tracker_config_gs1.yaml`,
`tracker_config_gs2.yaml`) y los datos que nombran en `codigo/data/`. Este
modulo no importa cv2: lo usan tambien el panel y sus procesos.

Uso (desde `codigo/`, con el venv): `import profiles; cfg = profiles.load(...)`.
"""
from __future__ import annotations

from pathlib import Path

import yaml

CODE_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = CODE_ROOT / "profiles"
DATA_DIR = CODE_ROOT / "data"

PROFILE_GLOB = "tracker_config*.yaml"


def resolve_path(p: str | Path) -> Path:
    """La ruta `p` de un perfil, absoluta: tal cual si ya lo es; si no, relativa a `codigo/`.

    FileNotFoundError si no existe (con la ruta declarada y la resuelta).
    """
    declared = Path(p)
    path = declared if declared.is_absolute() else CODE_ROOT / declared
    if not path.exists():
        raise FileNotFoundError(f"no existe {p} (las rutas de un perfil son relativas a {CODE_ROOT})")
    return path.resolve()


def check_markers(cfg: dict, profile_name: str) -> None:
    """Valida `markers.list` del perfil; ValueError con el perfil y la entrada si algo no cuadra.

    Meta 006, fase 7c (B55; principio 7): la lista no puede estar vacia; cada entrada trae
    `id` (entero >= 0), `name` (texto) y `size_mm` (> 0); ni los IDs ni los nombres se
    repiten. El tracker publica `<name>ToTracker` por cada marker de la lista con pose: con
    dos entradas del mismo nombre mandaria dos transforms con ese nombre por frame, y con un
    `size_mm` que no es el del marker la pose sale a otra escala sin avisar.
    """
    markers = cfg.get("markers")
    lista = markers.get("list") if isinstance(markers, dict) else None
    if not isinstance(lista, list) or not lista:
        raise ValueError(f"perfil {profile_name}: markers.list falta o esta vacia")
    ids: dict[int, int] = {}
    nombres: dict[str, int] = {}
    for n, m in enumerate(lista):
        donde = f"perfil {profile_name}: markers.list[{n}] = {m!r}"
        if not isinstance(m, dict):
            raise ValueError(f"{donde}: tiene que traer id, name y size_mm")
        mid, nombre, lado = m.get("id"), m.get("name"), m.get("size_mm")
        if isinstance(mid, bool) or not isinstance(mid, int) or mid < 0:
            raise ValueError(f"{donde}: id tiene que ser un entero >= 0")
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError(f"{donde}: name tiene que ser un texto")
        if isinstance(lado, bool) or not isinstance(lado, (int, float)) or not lado > 0:
            raise ValueError(f"{donde}: size_mm tiene que ser un numero > 0")
        if mid in ids:
            raise ValueError(f"{donde}: el id {mid} ya esta en markers.list[{ids[mid]}]")
        if nombre in nombres:
            raise ValueError(f"{donde}: el nombre '{nombre}' ya esta en markers.list[{nombres[nombre]}]")
        ids[mid], nombres[nombre] = n, n


def load(path: str | Path, *, missing_ok: bool = False) -> dict:
    """Carga el YAML del perfil `path` y deja absolutas sus rutas de archivo.

    Valida `markers.list` con `check_markers` (ValueError con el nombre del perfil). Resuelve `camera.calibration_file` y el `geometry_file` de cada rigid body
    con `resolve_path`. Si una no existe, FileNotFoundError con el nombre del
    perfil; con `missing_ok=True` (quien va a crear ese archivo, p. ej. la
    calibracion de la camara) la deja absoluta aunque no exista.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"perfil {path.name}: no es un YAML con secciones")
    check_markers(cfg, path.name)

    def _resolve(p, what):
        if not p:
            return p
        try:
            return str(resolve_path(p))
        except FileNotFoundError as e:
            if missing_ok:
                q = Path(p)
                return str(q if q.is_absolute() else CODE_ROOT / q)
            raise FileNotFoundError(f"perfil {path.name}: {what}: {e}") from None

    for rb in cfg.get("rigid_bodies", []) or []:
        if rb.get("geometry_file"):
            rb["geometry_file"] = _resolve(rb["geometry_file"], f"rigid body {rb.get('name', '?')}")
    cam = cfg.get("camera", {}) or {}
    if cam.get("calibration_file"):
        cam["calibration_file"] = _resolve(cam["calibration_file"], "camera.calibration_file")
    return cfg


def list_profiles() -> list[Path]:
    """Los perfiles disponibles (`codigo/profiles/tracker_config*.yaml`), ordenados."""
    return sorted(PROFILES_DIR.glob(PROFILE_GLOB))
