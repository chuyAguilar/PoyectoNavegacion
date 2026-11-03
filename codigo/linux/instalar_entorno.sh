#!/usr/bin/env bash
# instalar_entorno.sh - el entorno de Python del tracker en la Jetson (meta 007, fase 3).
#
# Lo lanza el guardian con `ssh nav-jetson entorno instalar <repo|wip> [--gtsam]`, como la cuenta
# navagente, sin sudo, con PATH=/usr/bin:/bin y 1800 s de tope. Hace, en este orden:
#   1. uv: el binario de una version fija, bajado de GitHub Releases y comprobado contra el sha256
#      escrito aqui (no el que se baja), en ~/.local/share/nav-uv/<version>/uv. No toca el PATH
#      ni los perfiles del shell. Si ya esta y da su version, no se baja otra vez.
#   2. El venv ~/.venvs/navegacion con el CPython 3.11.9 gestionado por uv (clarify P21; el mismo
#      3.11.9 del PC). No usa ni toca el Python 3.10 del sistema. Si ya hay un venv con ese
#      Python, se reutiliza; si hay otro, se aparta como navegacion.anterior-<fecha>.
#   3. requirements-jetson.txt del mismo arbol (versiones del PC, con ==).
#   4. La comprobacion: Python 3.11.9, cada paquete con la version de requirements-jetson.txt y
#      un ArucoDetector que encuentra un marcador sintetico.
#   5. Con --gtsam: gtsam en un venv aparte (~/.venvs/prueba-gtsam), solo para saber si instala
#      (la meta 006 lo necesita); el venv del tracker no lo lleva. Si no instala, se dice y sigue.
#   6. El disco: MB de cada parte y lo libre que queda en /.
# Escribe solo dentro del HOME de la cuenta. Las lineas que empiezan por ENTORNO_ son el resumen.
#
# Codigos: 0 el entorno del tracker esta y pasa la comprobacion (gtsam aparte, en su linea);
#          2 una entrada no vale (opcion, root, arquitectura, falta requirements); 3 fallo un paso.
# Solo ASCII y LF (.gitattributes): llega a la Jetson tal cual por wip recibir o por el clon.

set -u
set -o pipefail

UV_VERSION="0.13.6"
UV_TRIPLE="uv-aarch64-unknown-linux-gnu"
UV_SHA256="229e194255c7958d86d56e8790d969a6f74736592133f0dfd0076f754c642c1d"
UV_URL="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${UV_TRIPLE}.tar.gz"
PYTHON_VERSION="3.11.9"
GTSAM_VERSION="4.3.0"
MIN_LIBRE_MB=3072

ARBOL="$(cd "$(dirname "$0")/.." && pwd)"
REQ="$ARBOL/requirements-jetson.txt"
VENV="$HOME/.venvs/navegacion"
VENV_GTSAM="$HOME/.venvs/prueba-gtsam"
UV_DIR="$HOME/.local/share/nav-uv/$UV_VERSION"
UV="$UV_DIR/uv"
DESCARGAS="$HOME/.cache/nav-entorno"

export UV_CACHE_DIR="$HOME/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$HOME/.local/share/uv/python"
export UV_NO_PROGRESS=1
export UV_NO_MODIFY_PATH=1

paso() { echo "=== $* ($(date +%H:%M:%S))"; }
falla() { echo "ENTORNO_FIN fallo: $*"; exit 3; }
entrada() { echo "ERROR: $*"; echo "ENTORNO_FIN entrada: $*"; exit 2; }

GTSAM=0
for a in "$@"; do
    case "$a" in
        --gtsam) GTSAM=1 ;;
        *) entrada "opcion que no vale: '$a' (solo --gtsam)" ;;
    esac
done

# ------------------------------------------------------------------ 0. entradas
paso "0. entradas"
[ "$(id -u)" != "0" ] || entrada "no se corre como root: es para la cuenta navagente, sin privilegios"
[ "$(uname -m)" = "aarch64" ] || entrada "la arquitectura es $(uname -m); el uv fijado es el de aarch64"
[ -f "$REQ" ] || entrada "no esta $REQ"
[ -n "$HOME" ] && [ -d "$HOME" ] || entrada "HOME no vale: '$HOME'"
libre_mb=$(df -Pm "$HOME" | awk 'NR==2 {print $4}')
[ "${libre_mb:-0}" -ge "$MIN_LIBRE_MB" ] || entrada "quedan ${libre_mb} MB libres (minimo $MIN_LIBRE_MB)"
echo "arbol: $ARBOL"
echo "cuenta: $(id -un)  home: $HOME  libre: ${libre_mb} MB"
T0=$SECONDS

# ------------------------------------------------------------------ 1. uv
paso "1. uv $UV_VERSION"
if [ -x "$UV" ] && "$UV" --version 2>/dev/null | grep -q " $UV_VERSION"; then
    echo "ya estaba: $("$UV" --version)"
else
    mkdir -p "$DESCARGAS" "$UV_DIR" || falla "no se pudo crear $DESCARGAS o $UV_DIR"
    archivo="$DESCARGAS/${UV_TRIPLE}-${UV_VERSION}.tar.gz"
    echo "bajando $UV_URL"
    timeout -k 5 300 /usr/bin/python3 -I -c '
import shutil, sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=60) as r, open(sys.argv[2], "wb") as f:
    shutil.copyfileobj(r, f)
' "$UV_URL" "$archivo" || falla "no se pudo bajar $UV_URL"
    sha=$(sha256sum "$archivo" | awk '{print $1}')
    if [ "$sha" != "$UV_SHA256" ]; then
        falla "el sha256 de uv no coincide: esperado $UV_SHA256, llego $sha"
    fi
    echo "sha256 de uv: coincide ($sha)"
    tmpx="$DESCARGAS/extraer-$$"
    mkdir -p "$tmpx" || falla "no se pudo crear $tmpx"
    timeout -k 5 60 tar -xzf "$archivo" -C "$tmpx" --no-same-owner || falla "no se pudo extraer $archivo"
    [ -f "$tmpx/$UV_TRIPLE/uv" ] || falla "el tar de uv no trae $UV_TRIPLE/uv"
    mv -f "$tmpx/$UV_TRIPLE/uv" "$UV" || falla "no se pudo mover uv a $UV"
    chmod 0755 "$UV"
    "$UV" --version | grep -q " $UV_VERSION" || falla "$UV no da la version $UV_VERSION"
    echo "instalado: $("$UV" --version) en $UV"
fi
echo "ENTORNO_UV $UV_VERSION"

# ------------------------------------------------------------------ 2. el venv
paso "2. venv $VENV con CPython $PYTHON_VERSION"
version_de() { "$1" -I -c 'import sys; print(sys.version.split()[0])' 2>/dev/null; }
if [ -x "$VENV/bin/python" ] && [ "$(version_de "$VENV/bin/python")" = "$PYTHON_VERSION" ]; then
    echo "ya estaba, con Python $PYTHON_VERSION"
else
    if [ -e "$VENV" ]; then
        aparte="$VENV.anterior-$(date +%Y%m%d_%H%M%S)"
        mv "$VENV" "$aparte" || falla "no se pudo apartar $VENV"
        echo "el venv anterior no era $PYTHON_VERSION: queda en $aparte"
    fi
    mkdir -p "$(dirname "$VENV")"
    t=$SECONDS
    timeout -k 5 600 "$UV" venv --managed-python --python "$PYTHON_VERSION" "$VENV" \
        || falla "uv venv no pudo crear $VENV con Python $PYTHON_VERSION"
    echo "creado en $((SECONDS - t)) s"
fi
v=$(version_de "$VENV/bin/python")
[ "$v" = "$PYTHON_VERSION" ] || falla "el venv tiene Python '$v', no $PYTHON_VERSION"
echo "ENTORNO_PYTHON $v"

# ------------------------------------------------------------------ 3. paquetes
paso "3. requirements-jetson.txt"
t=$SECONDS
timeout -k 5 900 "$UV" pip install --python "$VENV/bin/python" -r "$REQ" \
    || falla "no se pudo instalar $REQ"
echo "instalado en $((SECONDS - t)) s"

# ------------------------------------------------------------------ 4. comprobacion
paso "4. comprobacion"
COMPROBAR='
import importlib.metadata as md
import re
import sys

req = sys.argv[1]
ok = True
for linea in open(req, encoding="ascii"):
    m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s#]+)", linea)
    if not m:
        continue
    nombre, esperada = m.group(1), m.group(2)
    try:
        obtenida = md.version(nombre)
    except md.PackageNotFoundError:
        obtenida = "no esta"
    igual = obtenida == esperada
    ok = ok and igual
    print("ENTORNO_PAQUETE %s %s %s" % (nombre, obtenida, "igual" if igual else "DISTINTA de " + esperada))

import cv2
import numpy as np
import pyigtl  # noqa: F401
import scipy  # noqa: F401
import yaml  # noqa: F401

dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marca = cv2.aruco.generateImageMarker(dic, 7, 200)
img = np.full((400, 400), 255, np.uint8)
img[100:300, 100:300] = marca
det = cv2.aruco.ArucoDetector(dic, cv2.aruco.DetectorParameters())
esquinas, ids, _ = det.detectMarkers(img)
aruco = ids is not None and [int(i) for i in ids.ravel()] == [7]
print("ENTORNO_ARUCO cv2 %s ArucoDetector %s" % (cv2.__version__, "encuentra el 7" if aruco else "NO lo encuentra"))
sys.exit(0 if ok and aruco else 1)
'
"$VENV/bin/python" -I -c "$COMPROBAR" "$REQ" || falla "la comprobacion del venv no paso (ver las lineas ENTORNO_)"

# ------------------------------------------------------------------ 5. gtsam (aparte)
if [ "$GTSAM" = "1" ]; then
    paso "5. gtsam $GTSAM_VERSION en $VENV_GTSAM (aparte del tracker)"
    gtsam_ok=1
    if ! { [ -x "$VENV_GTSAM/bin/python" ] && [ "$(version_de "$VENV_GTSAM/bin/python")" = "$PYTHON_VERSION" ]; }; then
        if [ -e "$VENV_GTSAM" ]; then
            mv "$VENV_GTSAM" "$VENV_GTSAM.anterior-$(date +%Y%m%d_%H%M%S)" || gtsam_ok=0
        fi
        [ "$gtsam_ok" = "1" ] && { timeout -k 5 600 "$UV" venv --managed-python --python "$PYTHON_VERSION" "$VENV_GTSAM" || gtsam_ok=0; }
    fi
    t=$SECONDS
    if [ "$gtsam_ok" = "1" ]; then
        timeout -k 5 600 "$UV" pip install --python "$VENV_GTSAM/bin/python" --only-binary gtsam \
            -r "$REQ" "gtsam==$GTSAM_VERSION" || gtsam_ok=0
    fi
    if [ "$gtsam_ok" = "1" ]; then
        "$VENV_GTSAM/bin/python" -I -c '
import importlib.metadata as md
import gtsam
import numpy as np
from gtsam.symbol_shorthand import X
g = gtsam.NonlinearFactorGraph()
g.add(gtsam.PriorFactorPose2(X(0), gtsam.Pose2(), gtsam.noiseModel.Diagonal.Sigmas(np.array([0.1, 0.1, 0.1]))))
v = gtsam.Values()
v.insert(X(0), gtsam.Pose2(0.2, -0.1, 0.05))
r = gtsam.LevenbergMarquardtOptimizer(g, v, gtsam.LevenbergMarquardtParams()).optimize().atPose2(X(0))
assert abs(r.x()) < 1e-6 and abs(r.y()) < 1e-6 and abs(r.theta()) < 1e-6, r
print("gtsam %s con numpy %s: el grafo de prueba converge" % (md.version("gtsam"), np.__version__))
' || gtsam_ok=0
    fi
    if [ "$gtsam_ok" = "1" ]; then
        echo "ENTORNO_GTSAM si $GTSAM_VERSION ($((SECONDS - t)) s)"
    else
        echo "ENTORNO_GTSAM no (ver arriba; el venv del tracker no cambia)"
    fi
fi

# ------------------------------------------------------------------ 6. disco
paso "6. disco"
mb() { if [ -e "$1" ]; then du -sm "$1" 2>/dev/null | awk '{print $1}'; else echo 0; fi; }
echo "ENTORNO_MB venv $(mb "$VENV")"
echo "ENTORNO_MB python_uv $(mb "$UV_PYTHON_INSTALL_DIR")"
echo "ENTORNO_MB cache_uv $(mb "$UV_CACHE_DIR")"
echo "ENTORNO_MB uv $(mb "$UV_DIR")"
echo "ENTORNO_MB descargas $(mb "$DESCARGAS")"
[ "$GTSAM" = "1" ] && echo "ENTORNO_MB venv_gtsam $(mb "$VENV_GTSAM")"
partes=("$VENV" "$UV_PYTHON_INSTALL_DIR" "$UV_CACHE_DIR" "$UV_DIR" "$DESCARGAS")
[ "$GTSAM" = "1" ] && partes+=("$VENV_GTSAM")
existen=()
for p in "${partes[@]}"; do [ -e "$p" ] && existen+=("$p"); done
total=$(du -smc "${existen[@]}" 2>/dev/null | awk 'END {print $1}')
echo "ENTORNO_MB total $total (sin contar dos veces lo enlazado desde la cache)"
echo "ENTORNO_LIBRE_MB $(df -Pm "$HOME" | awk 'NR==2 {print $4}')"
echo "ENTORNO_FIN ok en $((SECONDS - T0)) s"
exit 0
