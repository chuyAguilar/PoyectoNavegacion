# -*- coding: utf-8 -*-
"""
camera/v4l2.py -- La capa de Linux para las camaras UVC: identidad por el puerto
USB (`/dev/v4l/by-path/`) y los controles por `v4l2-ctl` (meta 007 · El tracker
en la Jetson Orin Nano, fase 5 · La capa V4L2 y cada camara en la Jetson; ADR J1).

Es el equivalente en Linux de `camera.uvc` (la identidad) y de
`camera.controls.CapaWindowsDShow` (los ajustes), con el mismo formato de
`controls` del perfil (clarify P11 y P12):

  - La identidad es `camera.usb_port_linux`: el nombre del enlace bajo
    `/dev/v4l/by-path/` (p. ej. `platform-3610000.usb-usb-0:2.1:1.0-video-index0`).
    Lo fija el puerto USB fisico, no el orden de conexion; `by-id` no sirve porque
    las dos SVPRO tienen la misma serie (`01.00.00`, escaneo de la fase 1). El
    enlace apunta al `/dev/videoN` del momento, que es lo que se abre.
  - Los controles van por `v4l2-ctl` en un subproceso con tope (P12): se leen
    todos con `--list-ctrls-menus`, se escribe SOLO lo que difiere con
    `--set-ctrl=<control>=<valor>` (uno por llamada, en el orden del perfil:
    `auto_exposure` antes que `exposure_time_absolute`), se relee y se compara
    en las unidades de la camara. Ningun shell: argv cerrado.
  - La exposicion: `exposure_time_absolute` va en unidades de 100 us. Los
    0.977 ms del perfil (1/1024 s, el -10 de DSHOW) la camara los entrega como 10
    (escaneo de la fase 1: `value=10`); por eso la comparacion es en unidades
    nativas y `exposure_ms` leido vuelve como 1.0.
  - `exposure_manual: true` SI se escribe aqui: es `auto_exposure=1` (Manual
    Mode); false es 3 (Aperture Priority). En Windows no hacia falta porque
    DSHOW lo pone al escribir la exposicion.

Nada de este modulo abre un flujo de video: `v4l2-ctl` abre el nodo para leer o
escribir controles y lo cierra. Lo que abre la camara es `WebcamBackend.open`
(`cv2.VideoCapture(<dispositivo>, cv2.CAP_V4L2)`), que llama a esta capa antes.

La suite (B34) niega `listar_camaras_v4l2` y `ejecutar_v4l2ctl`: las pruebas
inyectan `listar` y `ejecutar` falsos y leen las salidas reales de `v4l2-ctl`
del escaneo en `tests/data/linux/`.

Context7 (2026-11-02, OpenCV 4.13/5.0; instalado 4.11.0.86): `VideoCapture(filename,
apiPreference)` acepta el nombre del dispositivo con `CAP_V4L2`; `set()` True no
asegura que la camara acepto el valor (por eso se relee todo). `v4l2-ctl` no es una
libreria y no esta en Context7: su salida se toma del escaneo de la fase 1.

Uso (desde codigo/, con el venv; en la Jetson por `ssh nav-jetson py <repo|wip>
camera.v4l2 ...`):
    python -m camera.v4l2 --listar
    python -m camera.v4l2 --leer --puerto platform-3610000.usb-usb-0:2.1:1.0-video-index0
    python -m camera.v4l2 --aplicar --config profiles/tracker_config_gs1.yaml [--forzar]
`--aplicar` escribe en la camara (lo que hace el tracker al abrir): lo teclea el autor (P19).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from camera import controls as ajustes_camara

RUTA_BY_PATH = "/dev/v4l/by-path"
V4L2CTL = "v4l2-ctl"
TOPE_V4L2CTL_S = 5.0
# El mismo patron que el guardian de la Jetson (linux/guardian.py, RE_BYPATH).
RE_BYPATH = re.compile(r"^platform-[A-Za-z0-9.]+-usb-[0-9:.]+-video-index[0-9]+$")

# Nombre del perfil -> control V4L2 (los nombres que da uvcvideo en --list-ctrls).
CONTROLES_V4L2: dict[str, str] = {
    "exposure_manual": "auto_exposure",
    "exposure_ms": "exposure_time_absolute",
    "gain": "gain",
    "auto_white_balance": "white_balance_automatic",
    "brightness": "brightness",
    "contrast": "contrast",
    "saturation": "saturation",
    "sharpness": "sharpness",
    "gamma": "gamma",
    "backlight": "backlight_compensation",
    "focus": "focus_absolute",
}
PERFIL_DE_V4L2: dict[str, str] = {v: k for k, v in CONTROLES_V4L2.items()}
AUTO_EXPOSURE_MANUAL = 1        # "Manual Mode" en el menu de auto_exposure (UVC)
AUTO_EXPOSURE_APERTURE = 3      # "Aperture Priority Mode"
UNIDAD_EXPOSICION_MS = 0.1      # exposure_time_absolute: unidades de 100 us

# `brightness 0x00980900 (int)    : min=-64 max=64 step=1 default=0 value=0`
# `auto_exposure 0x009a0901 (menu)   : min=0 max=3 default=3 value=1 (Manual Mode)`
_RE_CTRL = re.compile(r"^\s*([a-z0-9_]+)\s+0x([0-9a-fA-F]+)\s+\((\w+)\)\s*:\s*(.*)$")
_RE_CAMPO = re.compile(r"([a-z]+)=(-?[0-9]+|[a-z-]+)")
_RE_ETIQUETA = re.compile(r"value=-?[0-9]+\s+\(([^)]*)\)")


@dataclass
class CamaraV4L2:
    """Un enlace de `/dev/v4l/by-path/`: su nombre (la identidad del perfil) y el
    `/dev/videoN` al que apunta hoy."""
    ruta_puerto: str
    dispositivo: str


# ----------------------------------------------------------------------------
# La identidad: /dev/v4l/by-path
# ----------------------------------------------------------------------------

def listar_camaras_v4l2(carpeta: str | os.PathLike = RUTA_BY_PATH,
                        resolver: Callable[[str], str] | None = None,
                        nombres: list[str] | None = None) -> list[CamaraV4L2]:
    """Los enlaces `*-video-index*` de `carpeta`, en orden de nombre, con su destino.

    `resolver(ruta) -> ruta real` es `os.path.realpath` y `nombres` son las entradas de la
    carpeta (por defecto se listan); los dos se inyectan en las pruebas: en Windows no hay
    enlaces y un nombre by-path (lleva `:`) ni siquiera se puede crear. OSError si la
    carpeta no existe (sin camaras UVC, o no es Linux). No abre ninguna camara.
    """
    carpeta = Path(carpeta)
    resolver = os.path.realpath if resolver is None else resolver
    if not carpeta.is_dir():
        raise OSError(f"[v4l2] no existe {carpeta}: sin camaras UVC conectadas, o no es Linux")
    if nombres is None:
        nombres = [p.name for p in carpeta.iterdir()]
    camaras = []
    for nombre in sorted(nombres):
        if "-video-index" not in nombre:
            continue
        camaras.append(CamaraV4L2(nombre, str(resolver(str(carpeta / nombre)))))
    return camaras


def resolver_dispositivo(puerto: str, camaras: list[CamaraV4L2]) -> str:
    """El `/dev/videoN` de la unica camara cuyo `ruta_puerto` es igual a `puerto`.

    Igualdad exacta (los nombres by-path distinguen mayusculas y `index0` de
    `index1`). ValueError si ninguna o mas de una coinciden (principio 7).
    """
    if not puerto or not str(puerto).strip():
        raise ValueError("puerto vacio")
    buscado = str(puerto).strip()
    hallados = [c for c in camaras if c.ruta_puerto.strip() == buscado]
    if len(hallados) == 1:
        return hallados[0].dispositivo
    lista = "; ".join(f"{c.ruta_puerto} -> {c.dispositivo}" for c in camaras) \
        or "ninguna camara enumerada"
    if not hallados:
        raise ValueError(f"el puerto '{puerto}' no coincide con ninguna camara "
                         f"conectada ({lista})")
    raise ValueError(f"el puerto '{puerto}' coincide con {len(hallados)} camaras "
                     f"({lista}); no puede ser")


# ----------------------------------------------------------------------------
# v4l2-ctl por subproceso, con tope
# ----------------------------------------------------------------------------

def ejecutar_v4l2ctl(args: list[str], timeout_s: float = TOPE_V4L2CTL_S,
                     ejecutar: Callable = subprocess.run) -> str:
    """`v4l2-ctl <args>` sin shell y con tope; devuelve su salida estandar.

    RuntimeError si no esta instalado (hace falta `v4l-utils`, P12: lo instala el
    autor), si no responde en `timeout_s` o si sale con un codigo distinto de 0
    (con su stderr). `ejecutar` es `subprocess.run` (inyectable en las pruebas).
    """
    argv = [V4L2CTL, *[str(a) for a in args]]
    try:
        r = ejecutar(argv, capture_output=True, text=True, timeout=float(timeout_s))
    except FileNotFoundError:
        raise RuntimeError(f"[v4l2] {V4L2CTL} no esta instalado: pide al autor "
                           f"`sudo apt install v4l-utils` (P12)") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"[v4l2] {V4L2CTL} no respondio en {timeout_s:g} s: "
                           f"{' '.join(argv)}") from None
    if r.returncode != 0:
        raise RuntimeError(f"[v4l2] {' '.join(argv)} salio con {r.returncode}: "
                           f"{(r.stderr or r.stdout or '').strip()}")
    return r.stdout or ""


def parsear_list_ctrls(texto: str) -> dict[str, dict]:
    """La salida de `v4l2-ctl --list-ctrls[-menus]` como {control: {campos}}.

    Cada control lleva `id` (int), `tipo` (`int`, `bool`, `menu`, ...) y los campos
    `min`, `max`, `step`, `default`, `value` que traiga (int); `flags` si lo trae
    (str), y `etiqueta` con el texto entre parentesis del valor de un menu
    (`Manual Mode`). Las lineas de los elementos del menu y los titulos se saltan.
    """
    controles: dict[str, dict] = {}
    for linea in texto.splitlines():
        m = _RE_CTRL.match(linea)
        if m is None:
            continue
        nombre, ident, tipo, resto = m.groups()
        campos: dict = {"id": int(ident, 16), "tipo": tipo}
        for clave, valor in _RE_CAMPO.findall(resto):
            campos[clave] = int(valor) if re.fullmatch(r"-?[0-9]+", valor) else valor
        e = _RE_ETIQUETA.search(resto)
        if e is not None:
            campos["etiqueta"] = e.group(1)
        controles[nombre] = campos
    return controles


# ----------------------------------------------------------------------------
# Conversiones (puras, con prueba)
# ----------------------------------------------------------------------------

def exposicion_ms_a_v4l2(ms: float) -> int:
    """`ms` en unidades de 100 us de `exposure_time_absolute`, redondeado al entero.

    ValueError si no es > 0 o si queda por debajo de una unidad (0.1 ms). 0.977 ms
    (el perfil, 1/1024 s) da 10, lo mismo que la camara entrega (escaneo, fase 1).
    """
    if ms is None or ms <= 0:
        raise ValueError(f"exposure_ms tiene que ser > 0, no {ms}")
    n = int(round(float(ms) / UNIDAD_EXPOSICION_MS))
    if n < 1:
        raise ValueError(f"exposure_ms={ms} queda por debajo de la unidad de V4L2 "
                         f"({UNIDAD_EXPOSICION_MS:g} ms)")
    return n


def v4l2_a_exposicion_ms(valor: int | float) -> float:
    """`exposure_time_absolute` (unidades de 100 us) en ms."""
    return round(float(valor) * UNIDAD_EXPOSICION_MS, 4)


def a_nativos_v4l2(controls: dict) -> dict[str, int]:
    """Control V4L2 -> valor entero, en el orden del perfil (`exposure_manual` primero:
    `auto_exposure` tiene que escribirse antes que `exposure_time_absolute`).

    Valida con `controls.validar_controles`; ademas, un control entero de V4L2 no
    admite un valor con decimales (ValueError).
    """
    validos = ajustes_camara.validar_controles(controls)
    nativos: dict[str, int] = {}
    for nombre in ajustes_camara.NOMBRES:
        if nombre not in validos:
            continue
        valor = validos[nombre]
        ctrl = CONTROLES_V4L2[nombre]
        if nombre == "exposure_manual":
            nativos[ctrl] = AUTO_EXPOSURE_MANUAL if valor else AUTO_EXPOSURE_APERTURE
        elif nombre == "exposure_ms":
            nativos[ctrl] = exposicion_ms_a_v4l2(valor)
        elif nombre in ajustes_camara.BOOLEANOS:
            nativos[ctrl] = 1 if valor else 0
        else:
            if abs(valor - round(valor)) > 1e-9:
                raise ValueError(f"controls del perfil: '{nombre}'={valor} no es entero y "
                                 f"{ctrl} de V4L2 solo admite enteros")
            nativos[ctrl] = int(round(valor))
    return nativos


def de_nativos_v4l2(nativos: dict[str, int | float]) -> dict:
    """Lo leido por V4L2 en las unidades y los nombres del perfil (exposicion en ms,
    bool para `exposure_manual` y `auto_white_balance`). Un control que el perfil
    no conoce se devuelve con su nombre de V4L2 y su valor tal cual."""
    perfil: dict = {}
    for ctrl, valor in nativos.items():
        nombre = PERFIL_DE_V4L2.get(ctrl, ctrl)
        if nombre == "exposure_manual":
            perfil[nombre] = int(valor) == AUTO_EXPOSURE_MANUAL
        elif nombre == "exposure_ms":
            perfil[nombre] = v4l2_a_exposicion_ms(valor)
        elif nombre in ajustes_camara.BOOLEANOS:
            perfil[nombre] = bool(int(valor))
        else:
            perfil[nombre] = float(valor)
    return perfil


# ----------------------------------------------------------------------------
# La capa (camera.controls.CapaAjustes para Linux)
# ----------------------------------------------------------------------------

class CapaLinuxV4L2:
    """Lee y aplica los `controls` del perfil por `v4l2-ctl`, por el puerto by-path.

    `listar()` da las camaras (`listar_camaras_v4l2`) y `ejecutar(args, timeout_s)`
    corre `v4l2-ctl` (`ejecutar_v4l2ctl`); los dos se inyectan en las pruebas y se
    resuelven al llamar, asi el fixture B34 de la suite los niega. No pone formato,
    tamano ni fps: solo controles (eso lo hace `WebcamBackend.open` por cv2).
    """

    def __init__(self, listar: Callable[[], list] | None = None,
                 ejecutar: Callable[[list, float], str] | None = None,
                 timeout_s: float = TOPE_V4L2CTL_S) -> None:
        self._listar = listar
        self._ejecutar = ejecutar
        self.timeout_s = float(timeout_s)

    # ---- plomeria ----------------------------------------------------------

    def _camaras(self) -> list[CamaraV4L2]:
        return (self._listar or listar_camaras_v4l2)()

    def _v4l2ctl(self, args: list[str]) -> str:
        return (self._ejecutar or ejecutar_v4l2ctl)(args, self.timeout_s)

    def dispositivo(self, puerto: str) -> str:
        """El `/dev/videoN` de la camara del puerto (ValueError si 0 o mas de 1)."""
        return resolver_dispositivo(puerto, self._camaras())

    def controles(self, dispositivo: str) -> dict[str, dict]:
        """Todos los controles de la camara, parseados de `--list-ctrls-menus`."""
        return parsear_list_ctrls(self._v4l2ctl(["-d", dispositivo, "--list-ctrls-menus"]))

    @staticmethod
    def _nombres_validos(nombres: list[str]) -> list[str]:
        malos = [n for n in nombres if n not in CONTROLES_V4L2]
        if malos:
            raise ValueError(f"no se leen por V4L2: {malos}; validos: {list(CONTROLES_V4L2)}")
        return list(nombres)

    @staticmethod
    def _valores(controles: dict[str, dict], ctrls: list[str], dispositivo: str) -> dict[str, int]:
        faltan = [c for c in ctrls if c not in controles or "value" not in controles[c]]
        if faltan:
            raise RuntimeError(f"[v4l2] {dispositivo} no tiene los controles {faltan} "
                               f"(tiene: {sorted(controles)})")
        return {c: int(controles[c]["value"]) for c in ctrls}

    # ---- la interfaz CapaAjustes -------------------------------------------

    def leer(self, puerto: str, nombres: list[str]) -> dict:
        """Lo que la camara del puerto tiene hoy, en las unidades del perfil. No escribe."""
        nombres = self._nombres_validos(nombres)
        dev = self.dispositivo(puerto)
        ctrls = [CONTROLES_V4L2[n] for n in nombres]
        return de_nativos_v4l2(self._valores(self.controles(dev), ctrls, dev))

    def aplicar(self, puerto: str, controls: dict, *, forzar: bool = False) -> dict:
        """Escribe solo lo que difiere (en el orden del perfil), relee y compara en
        unidades nativas. AjustesNoAplicados si algo no coincide; ValueError si un
        valor cae fuera del rango que declara la camara (antes de escribir nada).

        Devuelve {"dispositivo", "antes", "leidos", "antes_nativos", "leidos_nativos",
        "escritos", "set_false", "diferencias", "forzado", "segundos"}: `antes` y
        `leidos` con los nombres y unidades del perfil; `*_nativos` con los de V4L2.
        `set_false` son los controles cuyo `--set-ctrl` fallo (v4l2-ctl salio != 0).
        """
        t0 = time.monotonic()
        nativos = a_nativos_v4l2(controls)
        dev = self.dispositivo(puerto)
        todos = self.controles(dev)
        antes = self._valores(todos, list(nativos), dev)
        fuera = [f"{c}={v} fuera de [{todos[c].get('min')}, {todos[c].get('max')}]"
                 for c, v in nativos.items()
                 if todos[c].get("tipo") in ("int", "menu") and "min" in todos[c]
                 and not (todos[c]["min"] <= v <= todos[c]["max"])]
        if fuera:
            raise ValueError(f"[v4l2] {dev}: {'; '.join(fuera)}: no se escribe nada")
        escritos: list[str] = []
        set_false: list[str] = []
        errores: dict[str, str] = {}
        for ctrl, valor in nativos.items():
            if not forzar and antes[ctrl] == valor:
                continue
            escritos.append(ctrl)
            try:
                self._v4l2ctl(["-d", dev, f"--set-ctrl={ctrl}={valor}"])
            except RuntimeError as e:
                set_false.append(ctrl)
                errores[ctrl] = str(e)
        despues = self._valores(self.controles(dev), list(nativos), dev)
        difs = ajustes_camara.comparar_controles(nativos, despues)
        resultado = {
            "dispositivo": dev,
            "antes": de_nativos_v4l2(antes),
            "leidos": de_nativos_v4l2(despues),
            "antes_nativos": antes,
            "leidos_nativos": despues,
            "escritos": escritos,
            "set_false": set_false,
            "errores": errores,
            "diferencias": difs,
            "forzado": forzar,
            "segundos": round(time.monotonic() - t0, 2),
        }
        if difs:
            raise ajustes_camara.AjustesNoAplicados(
                f"[v4l2] la camara del puerto {puerto} ({dev}) no quedo en lo declarado: "
                f"{'; '.join(difs)} (escritos: {escritos or 'ninguno'}; "
                f"set False: {set_false or 'ninguno'})", resultado)
        return resultado


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="La capa V4L2: lista las camaras por by-path, lee o aplica los controles de un perfil.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--listar", action="store_true", help="Los enlaces de /dev/v4l/by-path y su /dev/videoN.")
    g.add_argument("--leer", action="store_true", help="Los 11 controles del perfil de la camara de --puerto.")
    g.add_argument("--aplicar", action="store_true",
                   help="Comprueba la marca y aplica camera.controls del perfil de --config (escribe en la camara).")
    ap.add_argument("--puerto", default=None, help="Nombre by-path (con --leer).")
    ap.add_argument("--config", default=None, help="Perfil (con --aplicar).")
    ap.add_argument("--forzar", action="store_true", help="Con --aplicar: escribe aunque la lectura coincida.")
    ap.add_argument("--timeout", type=float, default=TOPE_V4L2CTL_S,
                    help=f"Tope en s de cada llamada a v4l2-ctl (defecto {TOPE_V4L2CTL_S:g}).")
    args = ap.parse_args(argv)
    if args.leer and not args.puerto:
        ap.error("--leer necesita --puerto <nombre by-path>")
    if args.aplicar and not args.config:
        ap.error("--aplicar necesita --config <perfil>")
    if args.puerto and not RE_BYPATH.match(args.puerto):
        ap.error(f"--puerto no parece un nombre by-path: {args.puerto!r}")
    if args.timeout <= 0:
        ap.error("--timeout tiene que ser > 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    capa = CapaLinuxV4L2(timeout_s=args.timeout)
    try:
        if args.listar:
            camaras = listar_camaras_v4l2()
            print(f"[v4l2] {len(camaras)} enlace(s) en {RUTA_BY_PATH}:")
            for c in camaras:
                print(f"  {c.ruta_puerto} -> {c.dispositivo}")
            return 0
        if args.leer:
            leidos = capa.leer(args.puerto, list(CONTROLES_V4L2))
            dev = capa.dispositivo(args.puerto)
            print(f"[v4l2] {args.puerto} -> {dev}")
            for nombre, valor in leidos.items():
                print(f"  {nombre} = {valor}   ({CONTROLES_V4L2[nombre]})")
            return 0
        import profiles
        cfg = profiles.load(args.config)["camera"]
        puerto = cfg.get("usb_port_linux")
        if not puerto:
            print(f"[v4l2] ERROR: {args.config} no trae camera.usb_port_linux", file=sys.stderr)
            return 2
        marca = cfg.get("marca") or {}
        if marca:
            leidos = capa.leer(puerto, list(marca))
            difs = [f"{n}: declarado {v:g}, leido {leidos.get(n)}" for n, v in marca.items()
                    if leidos.get(n) is None or abs(float(leidos[n]) - float(v)) > 1e-3]
            if difs:
                print(f"[v4l2] ERROR: la camara del puerto {puerto} no es la del perfil "
                      f"({'; '.join(difs)}): no se escribe nada", file=sys.stderr)
                return 1
            print(f"[v4l2] Marca comprobada: {marca}")
        r = capa.aplicar(puerto, cfg.get("controls") or {}, forzar=args.forzar)
        print(f"[v4l2] {r['dispositivo']}: escritos {r['escritos'] or 'ninguno'} en {r['segundos']} s")
        print(f"  leidos: {r['leidos']}")
        return 0
    except ajustes_camara.AjustesNoAplicados as e:
        print(f"[v4l2] ERROR: {e}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError) as e:
        print(f"[v4l2] ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
