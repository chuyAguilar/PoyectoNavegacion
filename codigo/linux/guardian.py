#!/usr/bin/python3 -I
"""El guardian de la cuenta `navagente` en la Jetson (meta 007, fase 2 - La barrera de seguridad).

`sshd` lo fuerza (`ForceCommand`) para esa cuenta y solo para ella: cada `ssh nav-jetson <orden>`
llega aqui con la orden en `SSH_ORIGINAL_COMMAND`. El guardian la parte sin shell, la compara con
su lista blanca de verbos (`decidir`), comprueba disco, temperatura y cuantas ordenes pesadas van
(`precondiciones`) y la ejecuta en su propio grupo de procesos, con entorno limpio, limites y tope
(`ejecutar`). Todo lo que no esta en la lista se niega con 126 y queda registrado; un tope sale
con 124; un error del propio guardian, con 125.

Reglas del archivo:
- Solo biblioteca estandar y Python >= 3.8: en la Jetson corre con `/usr/bin/python3 -I`
  (el 3.10 del sistema), no con el venv, que es de la cuenta y la cuenta podria cambiarlo.
- Lo que solo existe en Linux (`pwd`, `resource`, `os.killpg`, `start_new_session`) se importa o
  se usa dentro de las funciones, para que la suite pruebe lo demas en Windows.
- Ningun verbo invoca un shell; los argumentos se validan uno a uno.

La barrera dura es la cuenta (sin sudo ni docker, solo su carpeta): el guardian filtra y registra,
pero lo que impide el dano es que `navagente` no pueda hacerlo. El plan de la meta
(`specs/007-jetson/plan.md`, seccion 'La barrera') tiene el diseno completo.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

VERSION = "1 (2026-10-29)"
CUENTA = "navagente"
CODIGO_NEGADO = 126
CODIGO_TOPE = 124
CODIGO_ERROR = 125
MAX_ORDEN = 4096
WIP_MAX_BYTES = 50 * 2 ** 20
METACARACTERES = frozenset(";|&$`<>")
URL_ORIGEN = "https://github.com/chuyAguilar/PoyectoNavegacion.git"
PATRONES_SPARSE = ("/*", "!/herramientas/", "!/documentos/", "!*.nrrd", "!*.dcm")
PUERTOS = range(18944, 18951)
MAX_FRAMES = 1800
MAX_SEGUNDOS_TEGRASTATS = 900
MAX_LINEAS_REGISTRO = 200
MIN_LIBRE_GB = 5.0
MAX_TEMP_C = 85.0
MAX_PESADAS = 3
GRACIA_S = 5.0            # entre SIGTERM y SIGKILL al grupo
RE_BYPATH = re.compile(r"^platform-[A-Za-z0-9.]+-usb-[0-9:.]+-video-index[0-9]+$")
RE_EXPR_K = re.compile(r"^[A-Za-z0-9_ ().-]+$")
RE_ARBOL = re.compile(r"^(repo|wip)$")

# Los arboles de codigo de la cuenta, relativos a su HOME: el clon disperso y la copia WIP.
ARBOLES = {"repo": ("nav", "repo", "codigo"), "wip": ("nav-wip", "codigo")}

# `info <consulta>`: cada consulta con su argv cerrado. `temperatura` la resuelve el guardian.
CONSULTAS = {
    "sistema": ["cat", "/etc/os-release", "/etc/nv_tegra_release", "/proc/version"],
    "python": ["/usr/bin/python3", "-I", "-c",
               "import platform, sys, tarfile; print(sys.version); "
               "print('glibc', platform.libc_ver()[1]); "
               "print('tarfile.data_filter', hasattr(tarfile, 'data_filter'))"],
    "cpu": ["lscpu"],
    "memoria": ["free", "-m"],
    "disco": ["df", "-h", "/"],
    "usb": ["lsusb", "-t"],
    "red": ["ip", "-br", "addr"],
    "puertos": ["ss", "-ltnp"],
    "servicios": ["systemctl", "list-units", "--type=service", "--state=running",
                  "--no-pager", "--no-legend"],
    "energia": ["nvpmodel", "-q"],
}
TOPE_INFO_S = 10.0

# `py <arbol> <modulo>`: los modulos que se pueden lanzar y su tope en segundos.
MODULOS = {
    "tracker": 7200.0,
    "camera.v4l2": 60.0,
    "diagnostics.igtl_rate": 900.0,
    "diagnostics.clock_offset": 600.0,
    "diagnostics.tegrastats_log": 60.0,
    "linux.perfil_temporal": 30.0,
    "linux.sonda_privilegios": 60.0,
}
MODULOS_PESADOS = frozenset({"tracker", "camera.v4l2"})
OPCIONES_SALIDA = ("--record", "--output", "--salida")

AYUDA = f"""nav-guardian {VERSION}: la cuenta {CUENTA} solo ejecuta estos verbos (ssh nav-jetson <verbo>).
  ayuda
  info <sistema|python|cpu|memoria|disco|usb|red|puertos|servicios|energia|temperatura>
  info v4l2 <nombre by-path>  |  info camara-libre <nombre by-path>  |  info puerto-libre <18944-18950>
  repo clonar  |  repo actualizar  |  repo estado
  wip recibir (un tar de codigo/ por la entrada, <= 50 MB)  |  wip estado
  entorno instalar <repo|wip> [--gtsam]
  suite <repo|wip> [-q] [-k EXPR] [ruta bajo tests/]
  py <repo|wip> <modulo> [args]   modulos: {", ".join(sorted(MODULOS))}
  camara rafaga <nombre by-path> <frames <= {MAX_FRAMES}>
  medir tegrastats <segundos <= {MAX_SEGUNDOS_TEGRASTATS}>
  traer <ruta bajo ~/nav-salidas/>
  procesos  |  parar <pid>  |  registro [n <= {MAX_LINEAS_REGISTRO}]  |  prueba-tope
Lo demas se niega con 126 y queda en ~/nav-registro/guardian.jsonl y en journalctl -t nav-guardian.
"""


class Negado(Exception):
    """La orden no pasa la lista blanca; lleva el motivo."""


@dataclass(frozen=True)
class Orden:
    """Lo que se va a ejecutar.

    `argv` vacio quiere decir que la resuelve el propio guardian (`ayuda`, `traer`, `wip`...),
    con lo que haga falta en `extra`. `entrada` dice si el hijo recibe la entrada estandar;
    `salida`, si su salida va a ese archivo; `corte_esperado`, si llegar al tope es el final
    normal (medir tegrastats).
    """
    verbo: str
    argv: list
    cwd: str
    tope_s: float
    pesada: bool
    entrada: bool
    home: str
    extra: tuple = ()
    salida: str = ""
    corte_esperado: bool = False


# ------------------------------------------------------------------ rutas de la cuenta

def ruta_arbol(home: Path, nombre: str) -> Path:
    if not RE_ARBOL.match(nombre):
        raise Negado(f"el arbol tiene que ser repo o wip, no {nombre!r}")
    return Path(home).joinpath(*ARBOLES[nombre])


def ruta_repo(home: Path) -> Path:
    return Path(home) / "nav" / "repo"


def ruta_wip(home: Path) -> Path:
    return Path(home) / "nav-wip"


def ruta_salidas(home: Path) -> Path:
    return Path(home) / "nav-salidas"


def ruta_registro(home: Path) -> Path:
    return Path(home) / "nav-registro" / "guardian.jsonl"


def ruta_activas(home: Path) -> Path:
    return Path(home) / "nav-registro" / "activas"


def ruta_python(home: Path) -> Path:
    return Path(home) / ".venvs" / "navegacion" / "bin" / "python"


# ------------------------------------------------------------------ partir y validar

def partir(original: str) -> list:
    """`shlex.split` de la orden, negando lo que un shell interpretaria.

    No hay shell detras, pero asi ninguna orden lleva `;|&$\\`<>` ni caracteres de control, y la
    lista blanca se compara con palabras limpias.
    """
    if not original or not original.strip():
        raise Negado("sin orden: el guardian no abre un shell; `ayuda` da la lista")
    if len(original) > MAX_ORDEN:
        raise Negado(f"orden de mas de {MAX_ORDEN} caracteres")
    for c in original:
        if ord(c) < 32 or ord(c) == 127:
            raise Negado("la orden lleva un caracter de control")
        if c in METACARACTERES:
            raise Negado(f"la orden lleva el metacaracter {c!r}")
    try:
        palabras = shlex.split(original, posix=True)
    except ValueError as e:
        raise Negado(f"orden mal formada: {e}")
    if not palabras:
        raise Negado("sin orden: el guardian no abre un shell; `ayuda` da la lista")
    return palabras


def dentro_de(arg: str, raices: list) -> Path:
    """Resuelve `arg` (relativo a la primera raiz) y niega si cae fuera de todas las raices.

    `..` se niega siempre, y un enlace que apunte fuera tambien (se resuelve antes de comparar).
    """
    if "\x00" in arg:
        raise Negado("ruta con un byte nulo")
    p = Path(arg)
    if ".." in p.parts:
        raise Negado(f"ruta con '..': {arg}")
    if not p.is_absolute() and not arg.startswith("/"):     # en Windows "/etc" no cuenta como absoluta
        p = Path(raices[0]) / p
    try:
        real = p.resolve()
    except (OSError, RuntimeError) as e:
        raise Negado(f"ruta que no se puede resolver: {arg} ({e})")
    for raiz in raices:
        try:
            real.relative_to(Path(raiz).resolve())
            return real
        except ValueError:
            continue
    raise Negado(f"ruta fuera de {', '.join(str(r) for r in raices)}: {arg}")


def _expandir(arg: str, home: Path) -> str:
    if arg == "~":
        return str(home)
    if arg.startswith("~/"):
        return str(Path(home) / arg[2:])
    return arg


def _exactos(resto: list, n: int, uso: str) -> None:
    if len(resto) != n:
        raise Negado(f"uso: {uso}")


def _bypath(nombre: str) -> str:
    if not RE_BYPATH.match(nombre) or "/" in nombre or ".." in nombre:
        raise Negado(f"nombre by-path que no vale: {nombre!r} (p. ej. platform-3610000.usb-usb-0:2.1:1.0-video-index0)")
    return "/dev/v4l/by-path/" + nombre


def _entero(texto: str, minimo: int, maximo: int, que: str) -> int:
    if not re.fullmatch(r"[0-9]{1,8}", texto):
        raise Negado(f"{que} tiene que ser un entero, no {texto!r}")
    n = int(texto)
    if n < minimo or n > maximo:
        raise Negado(f"{que} tiene que ir de {minimo} a {maximo} (llego {n})")
    return n


def _args_py(args: list, arbol: Path, salidas: Path, home: Path) -> list:
    """Los argumentos de `py`: toda ruta cae dentro del arbol o de ~/nav-salidas/, y las de
    salida (--record, --output, --salida) solo en ~/nav-salidas/, absolutas o con ~/."""
    limpios = []
    i = 0
    while i < len(args):
        arg = args[i]
        opcion = next((o for o in OPCIONES_SALIDA if arg == o or arg.startswith(o + "=")), None)
        if opcion is not None:
            if "=" in arg:
                valor = arg.split("=", 1)[1]
                i += 1
            else:
                if i + 1 >= len(args):
                    raise Negado(f"{opcion} sin valor")
                valor = args[i + 1]
                i += 2
            valor = _expandir(valor, home)
            if not Path(valor).is_absolute():
                raise Negado(f"{opcion} tiene que ir a ~/nav-salidas/... (llego {valor!r})")
            real = dentro_de(valor, [salidas])
            limpios += [opcion, str(real)]
            continue
        if arg == "..":
            raise Negado("argumento '..'")
        if arg.startswith("~"):
            arg = _expandir(arg, home)
            if arg.startswith("~"):
                raise Negado(f"argumento con ~ de otro usuario: {args[i]!r}")
        # `--opcion=valor`: se comprueba el valor, no la palabra entera (si no, `--config=/etc/x`
        # contaria como una ruta relativa al arbol y pasaria).
        ruta = arg.split("=", 1)[1] if arg.startswith("-") and "=" in arg else arg
        if ruta.startswith("~"):
            ruta = _expandir(ruta, home)
            if ruta.startswith("~"):
                raise Negado(f"argumento con ~ de otro usuario: {args[i]!r}")
        if "/" in ruta or os.sep in ruta or Path(ruta).is_absolute():
            dentro_de(ruta, [arbol, salidas])
        limpios.append(arg)
        i += 1
    return limpios


# ------------------------------------------------------------------ decidir

def decidir(argv: list, home) -> Orden:
    """La lista blanca: de las palabras de la orden a la `Orden` que se ejecuta. Lanza `Negado`."""
    home = Path(home)
    if not argv:
        raise Negado("sin orden: el guardian no abre un shell; `ayuda` da la lista")
    verbo, resto = argv[0], argv[1:]
    salidas = ruta_salidas(home)

    def interna(nombre: str, tope: float, extra: tuple = (), pesada: bool = False,
                entrada: bool = False) -> Orden:
        return Orden(nombre, [], "", tope, pesada, entrada, str(home), extra)

    if verbo == "ayuda":
        _exactos(resto, 0, "ayuda")
        return interna("ayuda", 5.0)

    if verbo == "info":
        if not resto:
            raise Negado("uso: info <consulta>; `ayuda` da la lista")
        consulta = resto[0]
        if consulta in CONSULTAS:
            _exactos(resto, 1, f"info {consulta}")
            return Orden(f"info {consulta}", list(CONSULTAS[consulta]), "", TOPE_INFO_S, False,
                         False, str(home))
        if consulta == "temperatura":
            _exactos(resto, 1, "info temperatura")
            return interna("info temperatura", 5.0)
        if consulta == "v4l2":
            _exactos(resto, 2, "info v4l2 <nombre by-path>")
            dev = _bypath(resto[1])
            return Orden("info v4l2", ["v4l2-ctl", "-d", dev, "--info", "--list-formats-ext",
                                       "--list-ctrls-menus"], "", TOPE_INFO_S, False, False, str(home))
        if consulta == "camara-libre":
            _exactos(resto, 2, "info camara-libre <nombre by-path>")
            dev = _bypath(resto[1])
            return Orden("info camara-libre", ["fuser", "-v", dev], "", TOPE_INFO_S, False, False,
                         str(home))
        if consulta == "puerto-libre":
            _exactos(resto, 2, "info puerto-libre <puerto>")
            puerto = _entero(resto[1], PUERTOS.start, PUERTOS.stop - 1, "el puerto")
            return Orden("info puerto-libre", ["ss", "-ltn", f"sport = :{puerto}"], "", TOPE_INFO_S,
                         False, False, str(home))
        raise Negado(f"consulta desconocida: {consulta!r}; `ayuda` da la lista")

    if verbo == "repo":
        _exactos(resto, 1, "repo <clonar|actualizar|estado>")
        if resto[0] == "clonar":
            return interna("repo clonar", 600.0)
        if resto[0] == "actualizar":
            repo = ruta_repo(home)
            return Orden("repo actualizar", ["git", "-C", str(repo), "pull", "--ff-only"], str(home),
                         300.0, False, False, str(home))
        if resto[0] == "estado":
            return interna("repo estado", 30.0)
        raise Negado(f"repo {resto[0]!r} no existe: clonar, actualizar o estado")

    if verbo == "wip":
        _exactos(resto, 1, "wip <recibir|estado>")
        if resto[0] == "recibir":
            return interna("wip recibir", 120.0, entrada=True)
        if resto[0] == "estado":
            return interna("wip estado", 10.0)
        raise Negado(f"wip {resto[0]!r} no existe: recibir o estado")

    if verbo == "entorno":
        if len(resto) < 2 or resto[0] != "instalar":
            raise Negado("uso: entorno instalar <repo|wip> [--gtsam]")
        arbol = ruta_arbol(home, resto[1])
        opciones = resto[2:]
        if opciones not in ([], ["--gtsam"]):
            raise Negado("entorno instalar solo admite --gtsam")
        argv_ = ["bash", str(arbol / "linux" / "instalar_entorno.sh"), *opciones]
        return Orden("entorno instalar", argv_, str(arbol), 1800.0, True, False, str(home))

    if verbo == "suite":
        if not resto:
            raise Negado("uso: suite <repo|wip> [-q] [-k EXPR] [ruta bajo tests/]")
        arbol = ruta_arbol(home, resto[0])
        argv_ = [str(ruta_python(home)), "-m", "pytest"]
        ruta = "tests"
        i = 1
        while i < len(resto):
            if resto[i] == "-q":
                argv_.append("-q")
                i += 1
            elif resto[i] == "-k":
                if i + 1 >= len(resto) or not RE_EXPR_K.match(resto[i + 1]):
                    raise Negado("-k necesita una expresion de letras, cifras, espacios, (), - y _")
                argv_ += ["-k", resto[i + 1]]
                i += 2
            elif resto[i].startswith("tests/") and ".." not in Path(resto[i]).parts:
                ruta = resto[i]
                i += 1
            else:
                raise Negado(f"argumento de suite que no vale: {resto[i]!r}")
        argv_.insert(3, ruta)
        return Orden("suite", argv_, str(arbol), 900.0, True, True, str(home))

    if verbo == "py":
        if len(resto) < 2:
            raise Negado("uso: py <repo|wip> <modulo> [args]")
        arbol = ruta_arbol(home, resto[0])
        modulo = resto[1]
        if modulo not in MODULOS:
            raise Negado(f"modulo fuera de la lista blanca: {modulo!r} ({', '.join(sorted(MODULOS))})")
        args = _args_py(resto[2:], arbol, salidas, home)
        argv_ = [str(ruta_python(home)), "-u", "-m", modulo, *args]
        return Orden(f"py {modulo}", argv_, str(arbol), MODULOS[modulo], modulo in MODULOS_PESADOS,
                     True, str(home))

    if verbo == "camara":
        if len(resto) != 3 or resto[0] != "rafaga":
            raise Negado("uso: camara rafaga <nombre by-path> <frames>")
        dev = _bypath(resto[1])
        frames = _entero(resto[2], 1, MAX_FRAMES, "frames")
        argv_ = ["v4l2-ctl", "-d", dev, "--set-fmt-video=width=1280,height=960,pixelformat=MJPG",
                 "--set-parm=90", "--stream-mmap", f"--stream-count={frames}"]
        return Orden("camara rafaga", argv_, "", 60.0, True, False, str(home))

    if verbo == "medir":
        if len(resto) != 2 or resto[0] != "tegrastats":
            raise Negado("uso: medir tegrastats <segundos>")
        segundos = _entero(resto[1], 1, MAX_SEGUNDOS_TEGRASTATS, "segundos")
        marca = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        salida = salidas / f"tegrastats_{marca}_{segundos}s.txt"
        return Orden("medir tegrastats", ["tegrastats", "--interval", "1000"], "", float(segundos),
                     True, False, str(home), salida=str(salida), corte_esperado=True)

    if verbo == "traer":
        _exactos(resto, 1, "traer <ruta bajo ~/nav-salidas/>")
        real = dentro_de(_expandir(resto[0], home), [salidas])
        return interna("traer", 60.0, (str(real),))

    if verbo == "procesos":
        _exactos(resto, 0, "procesos")
        return Orden("procesos", ["ps", "-u", CUENTA, "-o", "pid,pgid,etime,pcpu,rss,args"], "",
                     TOPE_INFO_S, False, False, str(home))

    if verbo == "parar":
        _exactos(resto, 1, "parar <pid>")
        pid = _entero(resto[0], 2, 4194304, "el pid")
        return interna("parar", 15.0, (pid,))

    if verbo == "registro":
        if len(resto) > 1:
            raise Negado("uso: registro [n]")
        n = _entero(resto[0], 1, MAX_LINEAS_REGISTRO, "n") if resto else 50
        return interna("registro", 5.0, (n,))

    if verbo == "prueba-tope":
        _exactos(resto, 0, "prueba-tope")
        return Orden("prueba-tope", ["sleep", "30"], "", 3.0, False, False, str(home))

    raise Negado(f"verbo desconocido: {verbo!r}; `ayuda` da la lista")


# ------------------------------------------------------------------ precondiciones

def leer_temperaturas() -> dict:
    """Las zonas termicas de /sys que se pueden leer, en grados C (las que no responden, fuera)."""
    zonas = {}
    base = Path("/sys/class/thermal")
    if not base.is_dir():
        return zonas
    for zona in sorted(base.glob("thermal_zone*")):
        try:
            tipo = (zona / "type").read_text().strip()
            temp = int((zona / "temp").read_text().strip()) / 1000.0
        except (OSError, ValueError):
            continue
        zonas[tipo] = temp
    return zonas


def _temp_maxima() -> float:
    zonas = leer_temperaturas()
    return max(zonas.values()) if zonas else None


def _libre_gb(home: Path) -> float:
    return shutil.disk_usage(str(home)).free / 2 ** 30


def _pid_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def pesadas_en_marcha(home: Path) -> int:
    """Cuantas ordenes pesadas lanzadas por el guardian siguen vivas (por ~/nav-registro/activas/)."""
    n = 0
    carpeta = ruta_activas(home)
    if not carpeta.is_dir():
        return 0
    for archivo in carpeta.glob("*.json"):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not _pid_vivo(int(datos.get("pid", 0))):
            try:
                archivo.unlink()
            except OSError:
                pass
            continue
        if datos.get("pesada"):
            n += 1
    return n


def precondiciones(orden: Orden, home, leer_temp=None, libre_gb=None, pesadas=None) -> None:
    """Lo que tiene que cumplirse antes de ejecutar: arboles y venv presentes y, si la orden es
    pesada, disco, temperatura y numero de pesadas en marcha. Lanza `Negado`."""
    home = Path(home)
    python = str(ruta_python(home))
    if orden.cwd and not Path(orden.cwd).is_dir():
        raise Negado(f"no existe el arbol {orden.cwd}: `repo clonar` o `wip recibir` primero")
    if orden.argv and orden.argv[0] == python and not Path(python).exists():
        raise Negado("no hay venv en ~/.venvs/navegacion: `entorno instalar` primero")
    repo = ruta_repo(home)
    if orden.verbo == "repo clonar" and repo.exists():
        raise Negado(f"ya existe el clon {repo}: `repo actualizar`")
    if orden.verbo in ("repo actualizar", "repo estado") and not (repo / ".git").exists():
        raise Negado(f"no hay clon en {repo}: `repo clonar` primero")
    if not orden.pesada:
        return
    libre = libre_gb() if libre_gb else _libre_gb(home)
    if libre < MIN_LIBRE_GB:
        raise Negado(f"quedan {libre:.1f} GB libres (minimo {MIN_LIBRE_GB:.0f})")
    temp = leer_temp() if leer_temp else _temp_maxima()
    if temp is not None and temp > MAX_TEMP_C:
        raise Negado(f"temperatura {temp:.1f} C (maximo {MAX_TEMP_C:.0f})")
    n = pesadas() if pesadas else pesadas_en_marcha(home)
    if n >= MAX_PESADAS:
        raise Negado(f"ya hay {n} ordenes pesadas en marcha (maximo {MAX_PESADAS})")


# ------------------------------------------------------------------ entorno y limites

def entorno_limpio(home, venv=None) -> dict:
    """PATH fijo (mas el bin del venv), HOME, LANG y PYTHONNOUSERSITE. Sin LD_* ni PYTHONPATH."""
    ruta = "/usr/bin:/bin"
    if venv is not None:
        ruta = str(Path(venv) / "bin") + ":" + ruta
    return {
        "PATH": ruta,
        "HOME": str(home),
        "USER": CUENTA,
        "LOGNAME": CUENTA,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONIOENCODING": "utf-8",
        "TMPDIR": "/tmp",
    }


def limites_hijo() -> None:
    """El `preexec_fn`: archivo <= 2 GiB, 512 procesos, sin volcado de memoria y oom_score_adj 500,
    para que, si falta memoria, el sistema mate antes lo del agente que Ollama o el escritorio."""
    import resource
    gib2 = 2 * 2 ** 30
    resource.setrlimit(resource.RLIMIT_FSIZE, (gib2, gib2))
    resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("500")
    except OSError:
        pass


# ------------------------------------------------------------------ registro

class Registro:
    """Una linea JSON por intento en `ruta` y, si `logger`, la misma en el diario del sistema
    (`logger -t nav-guardian`), que la cuenta no puede borrar."""

    def __init__(self, ruta, logger: bool = True):
        self.ruta = Path(ruta)
        self.logger = logger

    def escribir(self, evento: dict) -> None:
        linea = json.dumps(evento, ensure_ascii=False, sort_keys=True)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
        if self.logger and shutil.which("logger"):
            try:
                subprocess.run(["logger", "-t", "nav-guardian", linea], timeout=5, check=False)
            except (OSError, subprocess.SubprocessError):
                pass

    def ultimas(self, n: int) -> list:
        if not self.ruta.is_file():
            return []
        lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        return lineas[-n:]


# ------------------------------------------------------------------ ejecutar

def _parar_grupo(pgid: int, gracia_s: float = GRACIA_S) -> None:
    """SIGTERM al grupo; si a los `gracia_s` sigue alguien, SIGKILL."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        return
    fin = time.monotonic() + gracia_s
    while time.monotonic() < fin:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _anotar_activa(home: Path, pid: int, orden: Orden) -> Path:
    carpeta = ruta_activas(home)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{pid}.json"
    archivo.write_text(json.dumps({"pid": pid, "verbo": orden.verbo, "pesada": orden.pesada,
                                   "inicio": _ahora()}), encoding="utf-8")
    return archivo


def _ahora() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _externa(orden: Orden, entrada=None, salida=None) -> int:
    """Lanza `orden.argv` en su propio grupo de procesos, con entorno limpio y limites, y espera
    con tope. Si el padre (la sesion de sshd) desaparece, para el grupo. Solo Linux."""
    home = Path(orden.home)
    venv = ruta_python(home).parent.parent
    env = entorno_limpio(home, venv if venv.is_dir() else None)
    stdin = None if orden.entrada else subprocess.DEVNULL
    stdout = open(orden.salida, "wb") if orden.salida else salida
    ppid0 = os.getppid()
    estado = {"corte": ""}

    try:
        p = subprocess.Popen(orden.argv, cwd=orden.cwd or str(home), env=env, stdin=stdin,
                             stdout=stdout, start_new_session=True, preexec_fn=limites_hijo)
    except OSError as e:
        if orden.salida and stdout is not None:
            stdout.close()
        print(f"ERROR: no se pudo lanzar {orden.argv[0]}: {e}", file=sys.stderr)
        return CODIGO_ERROR

    def parar(*_args):
        if not estado["corte"]:
            estado["corte"] = "senal"
        _parar_grupo(p.pid)

    anteriores = {}
    for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        anteriores[s] = signal.signal(s, parar)
    archivo = _anotar_activa(home, p.pid, orden)
    fin = time.monotonic() + orden.tope_s
    try:
        while True:
            try:
                rc = p.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() >= fin:
                estado["corte"] = estado["corte"] or "tope"
                _parar_grupo(p.pid)
                rc = p.wait()
                break
            if os.getppid() != ppid0:
                estado["corte"] = estado["corte"] or "desconexion"
                _parar_grupo(p.pid)
                rc = p.wait()
                break
    finally:
        for s, h in anteriores.items():
            signal.signal(s, h)
        try:
            archivo.unlink()
        except OSError:
            pass
        if orden.salida and stdout is not None:
            stdout.close()
    if estado["corte"] == "tope":
        if orden.corte_esperado:
            print(f"FIN: {orden.tope_s:.0f} s cumplidos" + (f"; salida en {orden.salida}" if orden.salida else ""),
                  file=sys.stderr)
            return 0
        print(f"TOPE: cortada a los {orden.tope_s:.0f} s (SIGTERM al grupo y SIGKILL a los {GRACIA_S:.0f})",
              file=sys.stderr)
        return CODIGO_TOPE
    if estado["corte"]:
        print(f"CORTE: {estado['corte']}: se paro el grupo de procesos", file=sys.stderr)
        return CODIGO_TOPE
    if orden.salida:
        print(f"salida en {orden.salida}", file=sys.stderr)
    return rc


def _sub(orden: Orden, verbo: str, argv: list, cwd: str, tope_s: float) -> Orden:
    return Orden(verbo, argv, cwd, tope_s, orden.pesada, False, orden.home)


def _interna(orden: Orden, registro: Registro, entrada, salida) -> int:
    home = Path(orden.home)
    if orden.verbo == "ayuda":
        salida.write(AYUDA.encode("utf-8"))
        return 0
    if orden.verbo == "info temperatura":
        zonas = leer_temperaturas()
        if not zonas:
            salida.write(b"sin zonas termicas legibles\n")
            return 1
        for tipo, temp in zonas.items():
            salida.write(f"{tipo} {temp:.1f} C\n".encode("utf-8"))
        return 0
    if orden.verbo == "repo clonar":
        repo = ruta_repo(home)
        repo.parent.mkdir(parents=True, exist_ok=True)
        rc = _externa(_sub(orden, "repo clonar", ["git", "clone", "--filter=blob:none", "--sparse",
                                                  URL_ORIGEN, str(repo)], str(repo.parent), 600.0),
                      None, salida)
        if rc != 0:
            return rc
        for clave, valor in (("core.sparseCheckout", "true"), ("core.sparseCheckoutCone", "false")):
            rc = _externa(_sub(orden, "repo clonar", ["git", "-C", str(repo), "config", clave, valor],
                               str(repo), 30.0), None, salida)
            if rc != 0:
                return rc
        (repo / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (repo / ".git" / "info" / "sparse-checkout").write_text("\n".join(PATRONES_SPARSE) + "\n",
                                                                encoding="utf-8")
        return _externa(_sub(orden, "repo clonar", ["git", "-C", str(repo), "sparse-checkout", "reapply"],
                             str(repo), 300.0), None, salida)
    if orden.verbo == "repo estado":
        repo = str(ruta_repo(home))
        peor = 0
        for argv in (["git", "-C", repo, "log", "--oneline", "-1"],
                     ["git", "-C", repo, "status", "--short"],
                     ["git", "-C", repo, "sparse-checkout", "list"],
                     ["git", "-C", repo, "count-objects", "-vH"]):
            rc = _externa(_sub(orden, "repo estado", argv, repo, 30.0), None, salida)
            peor = peor or rc
        return peor
    if orden.verbo == "wip recibir":
        sha = recibir_wip(entrada, home)
        salida.write(f"sha256 {sha}\n".encode("utf-8"))
        return 0
    if orden.verbo == "wip estado":
        estado = ruta_wip(home) / "ESTADO.json"
        if not estado.is_file():
            salida.write(b"sin copia WIP\n")
            return 0
        salida.write(estado.read_bytes())
        return 0
    if orden.verbo == "traer":
        ruta = Path(orden.extra[0])
        if not ruta.is_file():
            raise Negado(f"no existe el archivo {ruta}")
        with open(ruta, "rb") as f:
            shutil.copyfileobj(f, salida)
        return 0
    if orden.verbo == "parar":
        pid = int(orden.extra[0])
        archivo = ruta_activas(home) / f"{pid}.json"
        if not archivo.is_file():
            raise Negado(f"el pid {pid} no lo lanzo el guardian (no esta en ~/nav-registro/activas/)")
        _parar_grupo(pid)
        try:
            archivo.unlink()
        except OSError:
            pass
        salida.write(f"parado el grupo {pid}\n".encode("utf-8"))
        return 0
    if orden.verbo == "registro":
        for linea in registro.ultimas(int(orden.extra[0])):
            salida.write((linea + "\n").encode("utf-8"))
        return 0
    raise Negado(f"accion interna desconocida: {orden.verbo}")


def ejecutar(orden: Orden, registro: Registro, entrada=None, salida=None) -> int:
    """Ejecuta la `Orden`: las internas las resuelve el guardian; las demas van por `_externa`."""
    if entrada is None:
        entrada = sys.stdin.buffer
    if salida is None:
        salida = sys.stdout.buffer
    try:
        if not orden.argv:
            rc = _interna(orden, registro, entrada, salida)
        else:
            rc = _externa(orden, entrada, salida)
    finally:
        try:
            salida.flush()
        except (OSError, ValueError):
            pass
    return rc


# ------------------------------------------------------------------ la copia WIP

def _comprobar_miembro(m: tarfile.TarInfo) -> None:
    nombre = m.name
    if nombre.startswith("./"):
        nombre = nombre[2:]
    partes = Path(nombre).parts
    if m.name.startswith("/") or m.name.startswith("\\") or (len(m.name) > 1 and m.name[1] == ":"):
        raise Negado(f"ruta absoluta en el tar: {m.name!r}")
    if ".." in partes:
        raise Negado(f"ruta con '..' en el tar: {m.name!r}")
    if not partes or partes[0] != "codigo":
        raise Negado(f"miembro fuera de codigo/: {m.name!r}")
    if m.issym() or m.islnk():
        raise Negado(f"enlace en el tar: {m.name!r} -> {m.linkname!r}")
    if not (m.isfile() or m.isdir()):
        raise Negado(f"miembro que no es archivo ni carpeta: {m.name!r}")
    bajo = nombre.lower()
    if bajo.endswith(".nrrd") or bajo.endswith(".dcm"):
        raise Negado(f"datos de paciente en el tar: {m.name!r}")
    for prohibida in ("historico", ".venv", "__pycache__", ".pytest_cache"):
        if prohibida in partes[1:]:
            raise Negado(f"{prohibida}/ no viaja en la copia WIP: {m.name!r}")


def recibir_wip(entrada, home, max_bytes: int = WIP_MAX_BYTES) -> str:
    """Lee un tar de `codigo/` por `entrada` (<= `max_bytes`), lo valida entero y, solo si todo
    vale, lo extrae con `filter="data"` y sustituye ~/nav-wip/codigo (la anterior queda como
    codigo.anterior). Enlaza historico/ al del clon, que no viaja. Devuelve el sha256 de lo
    recibido. Lanza `Negado` sin extraer nada si algun miembro no vale."""
    home = Path(home)
    if not hasattr(tarfile, "data_filter"):
        raise Negado("este python3 no tiene tarfile.data_filter: no se extrae nada")
    datos = entrada.read(max_bytes + 1)
    if len(datos) > max_bytes:
        raise Negado(f"la copia pasa de {max_bytes // 2 ** 20} MB")
    if not datos:
        raise Negado("no llego nada por la entrada")
    sha = hashlib.sha256(datos).hexdigest()
    try:
        tar = tarfile.open(fileobj=io.BytesIO(datos), mode="r:*")
    except tarfile.TarError as e:
        raise Negado(f"no es un tar que se pueda leer: {e}")
    with tar:
        miembros = tar.getmembers()
        if not miembros:
            raise Negado("tar vacio")
        for m in miembros:
            _comprobar_miembro(m)
        wip = ruta_wip(home)
        wip.mkdir(parents=True, exist_ok=True)
        nuevo = wip / f".nuevo-{os.getpid()}"
        if nuevo.exists():
            shutil.rmtree(nuevo)
        nuevo.mkdir()
        try:
            tar.extractall(path=str(nuevo), filter="data")
        except (tarfile.TarError, OSError) as e:
            shutil.rmtree(nuevo, ignore_errors=True)
            raise Negado(f"la extraccion fallo y se deshizo: {e}")
    if not (nuevo / "codigo").is_dir():
        shutil.rmtree(nuevo, ignore_errors=True)
        raise Negado("el tar no trae la carpeta codigo/")
    actual = wip / "codigo"
    anterior = wip / "codigo.anterior"
    if anterior.exists():
        shutil.rmtree(anterior)
    if actual.exists():
        actual.rename(anterior)
    (nuevo / "codigo").rename(actual)
    shutil.rmtree(nuevo, ignore_errors=True)
    historico_repo = ruta_repo(home) / "codigo" / "historico"
    aviso = ""
    if historico_repo.is_dir() and not (actual / "historico").exists():
        try:
            os.symlink(str(historico_repo), str(actual / "historico"), target_is_directory=True)
        except OSError as e:
            aviso = f"sin enlace a historico/: {e}"
    estado = {"sha256": sha, "bytes": len(datos), "miembros": len(miembros), "hora": _ahora(),
              "aviso": aviso}
    (wip / "ESTADO.json").write_text(json.dumps(estado, indent=1, sort_keys=True) + "\n",
                                     encoding="utf-8")
    return sha


# ------------------------------------------------------------------ main

def _cuenta_actual() -> str:
    import pwd
    return pwd.getpwuid(os.getuid()).pw_name


def _hay_pty() -> bool:
    try:
        return sys.stdin.isatty() or sys.stdout.isatty()
    except (OSError, ValueError):
        return False


def _ip_origen(entorno) -> str:
    for clave in ("SSH_CONNECTION", "SSH_CLIENT"):
        valor = entorno.get(clave, "")
        if valor.split():
            return valor.split()[0]
    return "?"


def main(entorno=None) -> int:
    """Lee SSH_ORIGINAL_COMMAND del entorno, decide, ejecuta y registra. Devuelve el codigo."""
    if entorno is None:
        entorno = dict(os.environ)
    if len(sys.argv) > 1 and sys.argv[1] == "--autocomprobar":
        print(f"nav-guardian {VERSION}; python {sys.version.split()[0]}; "
              f"tarfile.data_filter {hasattr(tarfile, 'data_filter')}; {len(MODULOS)} modulos")
        print(AYUDA, end="")
        return 0
    home = Path(entorno.get("HOME") or os.path.expanduser("~"))
    registro = Registro(ruta_registro(home), logger=True)
    original = entorno.get("SSH_ORIGINAL_COMMAND", "")
    evento = {"hora": _ahora(), "ip": _ip_origen(entorno), "orden": original, "pid": os.getpid(),
              "permitido": False, "codigo": CODIGO_ERROR, "tope": False}
    t0 = time.monotonic()
    try:
        for carpeta in (ruta_salidas(home), ruta_activas(home)):
            carpeta.mkdir(parents=True, exist_ok=True)
        cuenta = _cuenta_actual()
        if cuenta != CUENTA:
            raise Negado(f"la cuenta es {cuenta!r}, no {CUENTA!r}")
        if _hay_pty():
            raise Negado("con pty no: el guardian no es un shell")
        orden = decidir(partir(original), home)
        precondiciones(orden, home)
        evento.update(verbo=orden.verbo, pesada=orden.pesada)
        rc = ejecutar(orden, registro)
        evento.update(permitido=True, codigo=rc, tope=(rc == CODIGO_TOPE))
    except Negado as e:
        print(f"NEGADO: {e}", file=sys.stderr)
        evento.update(permitido=False, motivo=str(e), codigo=CODIGO_NEGADO)
    except BrokenPipeError:
        evento.update(motivo="se corto la salida (BrokenPipe)", codigo=CODIGO_TOPE)
    except Exception as e:  # noqa: BLE001 - el guardian nunca muere sin registrar
        print(f"ERROR del guardian: {type(e).__name__}: {e}", file=sys.stderr)
        evento.update(motivo=f"{type(e).__name__}: {e}", codigo=CODIGO_ERROR)
    finally:
        evento["duracion_s"] = round(time.monotonic() - t0, 3)
        try:
            registro.escribir(evento)
        except OSError as e:
            print(f"ERROR: no se pudo escribir el registro: {e}", file=sys.stderr)
    return int(evento["codigo"])


if __name__ == "__main__":
    sys.exit(main())
