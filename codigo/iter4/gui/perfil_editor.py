# -*- coding: utf-8 -*-
"""
perfil_editor.py — Edicion QUIRURGICA del YAML del perfil (brief-02 M3a,
ADR-018). SIN Qt.

La UNICA mutacion permitida sobre un tracker_config*.yaml es la linea
`calibration_file:` (seccion camera). Reglas no negociables:

  1. Reemplazo TEXTUAL de esa unica linea — un round-trip de PyYAML
     destruiria todos los comentarios del config (documentan el tuning).
  2. Backup timestampeado (.bak-YYYYMMDD-HHMMSS) ANTES de escribir.
  3. Si el patron no aparece EXACTAMENTE una vez -> ValueError, no se toca
     nada (fail-loud).
  4. EOLs preservados byte-exacto (lectura/escritura con newline='': un
     archivo CRLF sigue CRLF; cero diff fantasma).

Nota: si la linea original traia un comentario inline (p.ej. "# vacio =
fabrica"), ese comentario describia el VALOR viejo y se reemplaza junto con
el; la confirmacion de la GUI muestra el antes/despues exacto.
"""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

# ^(indent + clave)(resto de la linea sin EOL). Sin $: [^\r\n]* ya se detiene
# en el fin de linea y no toca los EOL (CRLF preservado).
RE_LINEA = re.compile(r"^(\s*calibration_file:)([^\r\n]*)", re.MULTILINE)

CLAVES_YML = ("camera_matrix", "distortion_coefficients")


def validar_yml_intrinsecos(ruta_yml):
    """None si el .yml parece una calibracion valida; si no, el motivo."""
    ruta = Path(ruta_yml)
    if not ruta.exists():
        return f"no existe: {ruta}"
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"ilegible: {e}"
    faltan = [k for k in CLAVES_YML if k not in texto]
    if faltan:
        return f"{ruta.name}: faltan claves {faltan} (no parece una calibracion OpenCV)"
    return None


def _leer_exacto(ruta_cfg):
    with open(ruta_cfg, "r", encoding="utf-8", newline="") as f:
        return f.read()


def previsualizar_cambio(ruta_cfg, nuevo_valor):
    """(linea_actual, linea_nueva) SIN tocar nada.
    ValueError si 'calibration_file:' no aparece exactamente 1 vez."""
    texto = _leer_exacto(ruta_cfg)
    ocurrencias = RE_LINEA.findall(texto)
    if len(ocurrencias) != 1:
        raise ValueError(
            f"{Path(ruta_cfg).name}: se esperaba EXACTAMENTE 1 linea "
            f"'calibration_file:' y hay {len(ocurrencias)} — no se edita "
            f"nada (fail-loud).")
    prefijo, resto = ocurrencias[0]
    linea_actual = prefijo + resto
    linea_nueva = f"{prefijo} {nuevo_valor}".rstrip()
    return linea_actual, linea_nueva


def aplicar_cambio(ruta_cfg, nuevo_valor):
    """Backup + reemplazo de la unica linea. Devuelve
    (ruta_backup, linea_actual, linea_nueva)."""
    ruta_cfg = Path(ruta_cfg)
    linea_actual, linea_nueva = previsualizar_cambio(ruta_cfg, nuevo_valor)

    marca = time.strftime("%Y%m%d-%H%M%S")
    backup = ruta_cfg.with_name(ruta_cfg.name + f".bak-{marca}")
    shutil.copy2(ruta_cfg, backup)

    texto = _leer_exacto(ruta_cfg)
    # repl como FUNCION: evita el template de re (backslashes de rutas
    # Windows o secuencias tipo \1 jamas se interpretan).
    nuevo, n = RE_LINEA.subn(lambda _m: linea_nueva, texto, count=1)
    if n != 1:
        raise ValueError(f"reemplazo inesperado (n={n}); no se escribio nada "
                         f"(el backup {backup.name} queda igual que el original)")
    with open(ruta_cfg, "w", encoding="utf-8", newline="") as f:
        f.write(nuevo)

    # Verificacion post-escritura: la linea nueva esta y es unica.
    verif = RE_LINEA.findall(_leer_exacto(ruta_cfg))
    if len(verif) != 1 or (verif[0][0] + verif[0][1]).rstrip() != linea_nueva:
        raise ValueError(
            f"verificacion post-escritura FALLO — restaurar a mano desde el "
            f"backup: {backup}")
    return backup, linea_actual, linea_nueva


def valor_para_perfil(ruta_yml, dir_data):
    """Valor a escribir en el YAML: 'data/<nombre>' si el .yml vive en
    iter4\\data (convencion del repo), si no la ruta absoluta."""
    ruta = Path(ruta_yml).resolve()
    dir_data = Path(dir_data).resolve()
    if ruta.parent == dir_data:
        return f"data/{ruta.name}"
    return str(ruta)
