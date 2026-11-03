"""Un perfil temporal: copia de un perfil del tracker con unas pocas claves cambiadas
(meta 007 · El tracker en la Jetson Orin Nano; fase 5b · El ruido de gs1 por V4L2, P25;
lo usa tambien la fase 7 · Las dos camaras a la vez, P18).

Para medir una variable por vez sin tocar los perfiles del repo: el puerto OpenIGTLink
(dos trackers a la vez), el puerto USB de la camara (J4: gs1 en el puerto del hub de gs2)
o la exposicion (la sensibilidad del ruido). Solo se pueden cambiar las claves de
`CLAVES`; cualquier otra se niega (principio 7). La copia conserva los comentarios del
perfil base: se cambia la linea de la clave y nada mas, y despues se carga con yaml y se
comprueba que lo unico distinto del base son esas claves.

En la Jetson lo lanza el guardian (`ssh nav-jetson py <repo|wip> linux.perfil_temporal ...`,
tope 30 s): `--base` cae dentro del arbol y `--salida` solo en `~/nav-salidas/`. No abre
ninguna camara ni escribe en ella. Uso (desde codigo/, con el venv):

    python -m linux.perfil_temporal --base profiles/tracker_config_gs1.yaml \\
        --puerto 18945 --salida ~/nav-salidas/perfiles/gs1_18945.yaml
    python -m linux.perfil_temporal --base profiles/tracker_config_gs1.yaml \\
        --poner camera.usb_port_linux=platform-3610000.usb-usb-0:2.2:1.0-video-index0 \\
        --salida /home/navagente/nav-salidas/perfiles/gs1_puerto22.yaml
    python -m linux.perfil_temporal --base profiles/tracker_config_gs1.yaml \\
        --poner camera.controls.exposure_ms=0.9 --salida ...

`--puerto N` es el atajo de `--poner transforms_port=N`. `--poner` se repite. La salida no
se pisa si ya existe.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from camera.v4l2 import RE_BYPATH

PUERTOS_IGTL = range(18945, 18951)
EXPOSICION_MS = (0.1, 10.0)

# Las unicas claves que se pueden cambiar, con su tipo. La ruta es con puntos desde la raiz
# del YAML; `transforms_port` esta bajo `igtlink` en los perfiles, pero se nombra a secas
# (es como lo nombra el plan y como lo busca el guardian).
CLAVES: dict[str, type] = {
    "transforms_port": int,
    "camera.usb_port_linux": str,
    "camera.controls.exposure_ms": float,
}
RUTA_YAML: dict[str, tuple[str, ...]] = {
    "transforms_port": ("igtlink", "transforms_port"),
    "camera.usb_port_linux": ("camera", "usb_port_linux"),
    "camera.controls.exposure_ms": ("camera", "controls", "exposure_ms"),
}

_RE_LINEA = re.compile(r"^(?P<sangria>[ ]*)(?P<clave>[A-Za-z_][A-Za-z0-9_]*):(?P<resto>.*)$")
_RE_VALOR = re.compile(r"^(?P<espacio>\s*)(?P<valor>[^#]*?)(?P<coment>\s+#.*)?$")


def validar(clave: str, valor: object) -> object:
    """El valor convertido al tipo de `clave`, o ValueError con el motivo."""
    if clave not in CLAVES:
        raise ValueError(f"la clave {clave!r} no se puede cambiar; validas: {sorted(CLAVES)}")
    tipo = CLAVES[clave]
    if tipo is int:
        if isinstance(valor, bool) or not re.fullmatch(r"-?[0-9]+", str(valor).strip()):
            raise ValueError(f"{clave}={valor!r} tiene que ser un entero")
        n = int(str(valor).strip())
        if clave == "transforms_port" and n not in PUERTOS_IGTL:
            raise ValueError(f"transforms_port={n} fuera de {PUERTOS_IGTL.start}-"
                             f"{PUERTOS_IGTL.stop - 1} (el 18944 es el del tracker de siempre)")
        return n
    if tipo is float:
        try:
            x = float(str(valor).strip())
        except ValueError:
            raise ValueError(f"{clave}={valor!r} tiene que ser un numero") from None
        lo, hi = EXPOSICION_MS
        if not (lo <= x <= hi):
            raise ValueError(f"{clave}={x:g} fuera de [{lo:g}, {hi:g}] ms")
        return x
    texto = str(valor).strip()
    if clave == "camera.usb_port_linux" and not RE_BYPATH.match(texto):
        raise ValueError(f"{clave}={texto!r} no es un nombre by-path "
                         f"(p. ej. platform-3610000.usb-usb-0:2.2:1.0-video-index0)")
    return texto


def parsear_poner(texto: str) -> tuple[str, object]:
    """`CLAVE=VALOR` de `--poner` -> (clave, valor validado)."""
    if "=" not in texto:
        raise ValueError(f"--poner espera CLAVE=VALOR, no {texto!r}")
    clave, valor = texto.split("=", 1)
    clave = clave.strip()
    return clave, validar(clave, valor)


def _texto_valor(valor: object) -> str:
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def _sustituir(lineas: list[str], ruta: tuple[str, ...], valor: object) -> list[str]:
    """Cambia el valor de la linea cuya ruta de claves (por la sangria) es `ruta`.
    Conserva la sangria y el comentario de la linea. ValueError si no hay una sola."""
    pila: list[tuple[int, str]] = []
    hallados: list[int] = []
    for i, linea in enumerate(lineas):
        sin_fin = linea.rstrip("\r\n")
        if not sin_fin.strip() or sin_fin.lstrip().startswith("#") or sin_fin.lstrip().startswith("-"):
            continue
        m = _RE_LINEA.match(sin_fin)
        if m is None:
            continue
        sangria = len(m.group("sangria"))
        while pila and pila[-1][0] >= sangria:
            pila.pop()
        pila.append((sangria, m.group("clave")))
        if tuple(k for _, k in pila) == ruta:
            hallados.append(i)
    if len(hallados) != 1:
        raise ValueError(f"la clave {'.'.join(ruta)} aparece {len(hallados)} veces en el perfil "
                         f"base (tiene que aparecer una)")
    i = hallados[0]
    linea = lineas[i]
    fin = linea[len(linea.rstrip("\r\n")):]
    m = _RE_LINEA.match(linea.rstrip("\r\n"))
    v = _RE_VALOR.match(m.group("resto"))
    coment = v.group("coment") or ""
    lineas[i] = f"{m.group('sangria')}{m.group('clave')}: {_texto_valor(valor)}{coment}{fin}"
    return lineas


def _leer_ruta(cfg: dict, ruta: tuple[str, ...]):
    nodo = cfg
    for k in ruta:
        if not isinstance(nodo, dict) or k not in nodo:
            raise ValueError(f"el perfil base no tiene la clave {'.'.join(ruta)}")
        nodo = nodo[k]
    return nodo


def _poner_ruta(cfg: dict, ruta: tuple[str, ...], valor: object) -> None:
    nodo = cfg
    for k in ruta[:-1]:
        nodo = nodo[k]
    nodo[ruta[-1]] = valor


def crear(base: Path, salida: Path, cambios: dict[str, object]) -> Path:
    """Copia `base` en `salida` con solo las claves de `cambios` cambiadas.

    Niega una clave fuera de `CLAVES`, una que no exista en el base, un valor del tipo o
    rango equivocado y una salida que ya exista. Comprueba, cargando los dos YAML, que lo
    unico distinto es lo pedido; si no, borra la salida y falla.
    """
    base, salida = Path(base), Path(salida)
    if not cambios:
        raise ValueError("sin cambios: --puerto o --poner, al menos uno")
    validados = {clave: validar(clave, valor) for clave, valor in cambios.items()}
    if not base.is_file():
        raise FileNotFoundError(f"no existe el perfil base {base}")
    if salida.suffix not in (".yaml", ".yml"):
        raise ValueError(f"la salida tiene que terminar en .yaml: {salida}")
    if salida.exists():
        raise FileExistsError(f"la salida ya existe, no se pisa: {salida}")
    # Bytes tal cual: la copia conserva los fines de linea del base (CRLF en el arbol del PC,
    # LF en git y en la Jetson), asi `diff` solo muestra las lineas cambiadas.
    texto = base.read_bytes().decode("utf-8")
    cfg_base = yaml.safe_load(texto)
    if not isinstance(cfg_base, dict):
        raise ValueError(f"{base.name}: no es un YAML con secciones")
    esperado = yaml.safe_load(texto)
    for clave, valor in validados.items():
        _leer_ruta(cfg_base, RUTA_YAML[clave])
        _poner_ruta(esperado, RUTA_YAML[clave], valor)
    lineas = texto.splitlines(keepends=True)
    for clave, valor in validados.items():
        lineas = _sustituir(lineas, RUTA_YAML[clave], valor)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes("".join(lineas).encode("utf-8"))
    obtenido = yaml.safe_load(salida.read_bytes().decode("utf-8"))
    if obtenido != esperado:
        salida.unlink()
        raise ValueError("la copia no coincide con el base mas los cambios: se borro")
    return salida


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Copia un perfil del tracker cambiando solo el puerto OpenIGTLink, el puerto "
                    "USB de Linux o la exposicion (meta 007).")
    ap.add_argument("--base", required=True, type=Path, help="Perfil base (profiles/tracker_config_gs1.yaml).")
    ap.add_argument("--salida", required=True, type=Path, help="Perfil nuevo (.yaml; no se pisa).")
    ap.add_argument("--puerto", type=int, default=None,
                    help=f"transforms_port ({PUERTOS_IGTL.start}-{PUERTOS_IGTL.stop - 1}).")
    ap.add_argument("--poner", action="append", default=[], metavar="CLAVE=VALOR",
                    help=f"Una clave de {sorted(CLAVES)}; se repite.")
    args = ap.parse_args(argv)
    cambios: dict[str, object] = {}
    try:
        if args.puerto is not None:
            cambios["transforms_port"] = args.puerto
        for texto in args.poner:
            clave, valor = parsear_poner(texto)
            if clave in cambios:
                raise ValueError(f"la clave {clave} va dos veces")
            cambios[clave] = valor
        salida = crear(args.base, args.salida, cambios)
    except (ValueError, OSError) as e:
        print(f"[perfil_temporal] ERROR: {e}", file=sys.stderr)
        return 1
    print(f"[perfil_temporal] {salida}: copia de {args.base} con "
          + ", ".join(f"{k}={_texto_valor(validar(k, v))}" for k, v in cambios.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
