"""El escaneo de la Jetson es de solo lectura y con tope (meta 007, fase 1 · El escaneo de la Jetson, solo lectura).

`codigo/linux/escanear_jetson.sh` lo corre el autor en la Jetson con `codigo/linux/escanear.ps1`
(protocolo P-1), por ssh y con su cuenta. Estas pruebas no tocan la Jetson:

- leen el texto del script: ASCII y LF, ninguna orden que cambie algo (`sudo`, `su`, `apt`,
  `dpkg -i`, `rm`, `tee`, una redireccion a un archivo, `systemctl` con un verbo que cambia,
  `nvpmodel -m`, `jetson_clocks`, `--set-ctrl`...), ninguna tuberia y cada orden externa por
  `run`, `run_durante` o `hay`, que le ponen `timeout`;
- lo ejecutan con bash y un PATH que solo tiene un `timeout` falso: si alguna orden no pasara
  por `timeout`, bash no la encontraria y la prueba lo ve. Asi no corre ninguna orden real;
- y comprueban las entradas de `escanear.ps1`, que para con 2 antes de conectar a nada.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import CODIGO_DIR

REPO_DIR = CODIGO_DIR.parent
LINUX_DIR = CODIGO_DIR / "linux"
ESCANEO = LINUX_DIR / "escanear_jetson.sh"
LANZADOR = LINUX_DIR / "escanear.ps1"

SECCIONES = ["sistema", "python", "cpu y gpu", "memoria", "disco", "usb", "v4l2", "red",
             "servicios", "energia", "temperatura", "cuenta"]

# Lo que no puede aparecer en ninguna linea de codigo del script (las comillas incluidas).
PROHIBIDAS = [
    (r"\bsudo\b", "sudo"), (r"\bsu\b", "su"), (r"\bpkexec\b", "pkexec"),
    (r"\bapt(-get)?\b", "apt"), (r"\bdpkg\s+(-i|--install|-r|--remove|-P|--purge)\b", "dpkg -i"),
    (r"\bsnap\b", "snap"), (r"\bpip3?\s+install\b", "pip install"),
    (r"-m\s+pip\s+(?!--version\b)", "python -m pip (salvo --version)"),
    (r"\brm\b", "rm"), (r"\btee\b", "tee"), (r"\bmv\b", "mv"), (r"\bcp\b", "cp"),
    (r"\bdd\b", "dd"), (r"\bmkfs", "mkfs"), (r"\btouch\b", "touch"), (r"\bmkdir\b", "mkdir"),
    (r"\bln\b", "ln"), (r"\bchmod\b", "chmod"), (r"\bchown\b", "chown"),
    (r"\breboot\b", "reboot"), (r"\bshutdown\b", "shutdown"), (r"\bpoweroff\b", "poweroff"),
    (r"\bjetson_clocks\b", "jetson_clocks"), (r"\bnvpmodel\s+(?!-q\b)", "nvpmodel -m"),
    (r"--set-", "--set-ctrl"), (r"--stream", "--stream-*"),
    (r"\s-delete\b", "find -delete"), (r"\s-exec(dir)?\b", "find -exec"), (r"\s-fprint", "find -fprint"),
    (r"\beval\b", "eval"), (r"\bsource\b", "source"), (r"^\s*\.\s", ". (source)"),
    (r"\bcurl\b", "curl"), (r"\bwget\b", "wget"), (r"\bkill(all)?\b", "kill"), (r"\bpkill\b", "pkill"),
    (r"\bcrontab\b", "crontab"), (r"\bmount\b", "mount"), (r"\bnohup\b", "nohup"),
    (r"\bopen\(", "open( de Python"), (r"\.write", ".write"), (r"\bsubprocess\b", "subprocess"),
    (r"\bos\.(system|remove|unlink|rename|popen)", "os.*"), (r"\bshutil\b", "shutil"),
    (r"`", "comilla invertida"),
]
VERBOS_SYSTEMCTL = {"list-units", "is-active", "is-enabled", "show", "status"}
VERBOS_OLLAMA = {"ps", "list"}
VERBOS_TAILSCALE = {"status", "ip"}
OPCIONES_V4L2CTL = {"-d", "--info", "--list-formats-ext", "--list-ctrls-menus", "--list-devices",
                    "--version"}
# La primera palabra de cada trozo de codigo: las ayudas que ponen timeout, builtins que no
# lanzan nada y las palabras de control de bash.
PERMITIDAS = {"run", "run_durante", "hay", "seccion", "_orden", "echo", "printf", "local", "readonly",
              "export", "return", "continue", "shift", "main", "timeout", "[", "{", "}", "fi",
              "done"}
PREFIJOS = {"if", "elif", "then", "else", "do", "while", "!"}


def _texto() -> str:
    return ESCANEO.read_bytes().decode("ascii")


def _lineas_de_codigo() -> list[tuple[int, str]]:
    """Las lineas que no estan vacias ni son comentarios (el script no usa comentarios al final de linea)."""
    return [(n, linea) for n, linea in enumerate(_texto().split("\n"), 1)
            if linea.strip() and not linea.lstrip().startswith("#")]


def _partir(linea: str) -> tuple[list[str], str]:
    """Parte una linea por `;`, `&&`, `||` y `|` fuera de comillas.

    Devuelve los trozos y el texto que queda fuera de comillas (con `|` si habia una tuberia).
    """
    trozos: list[str] = []
    actual = ""
    fuera = ""
    comilla = ""
    i = 0
    while i < len(linea):
        c = linea[i]
        if comilla:
            actual += c
            if c == "\\" and comilla == '"' and i + 1 < len(linea):
                actual += linea[i + 1]
                i += 2
                continue
            if c == comilla:
                comilla = ""
            i += 1
            continue
        if c in "'\"":
            comilla = c
            actual += c
            i += 1
            continue
        if c == "\\" and i + 1 < len(linea):
            actual += linea[i:i + 2]
            fuera += linea[i:i + 2]
            i += 2
            continue
        if linea[i:i + 2] in ("&&", "||"):
            trozos.append(actual)
            actual = ""
            fuera += " "
            i += 2
            continue
        if c in ";|":
            fuera += " | " if c == "|" else " "
            trozos.append(actual)
            actual = ""
            i += 1
            continue
        actual += c
        fuera += c
        i += 1
    assert not comilla, f"comilla sin cerrar: {linea!r}"
    trozos.append(actual)
    return [t.strip() for t in trozos if t.strip()], fuera


# ---------------------------------------------------------------- el texto del script

def test_el_script_es_ascii_y_lf() -> None:
    datos = ESCANEO.read_bytes()
    assert datos, "escanear_jetson.sh esta vacio"
    assert b"\r" not in datos, "escanear_jetson.sh tiene CR: bash lo leeria mal (tiene que ser LF)"
    assert all(b < 128 for b in datos), "escanear_jetson.sh tiene bytes que no son ASCII"
    assert datos.startswith(b"#!/usr/bin/env bash\n")
    assert datos.endswith(b"\n")


def test_gitattributes_deja_los_sh_en_lf() -> None:
    """Con core.autocrlf=true, sin esta regla el arbol de Windows tendria CRLF y bash fallaria."""
    reglas = (REPO_DIR / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert any(re.fullmatch(r"\*\.sh\s+text\s+eol=lf", r.strip()) for r in reglas)


def test_ninguna_orden_prohibida() -> None:
    hallazgos = []
    for n, linea in _lineas_de_codigo():
        for patron, nombre in PROHIBIDAS:
            if re.search(patron, linea):
                hallazgos.append(f"linea {n}: {nombre}: {linea.strip()}")
    assert not hallazgos, "\n".join(hallazgos)


def test_systemctl_ollama_tailscale_y_nmcli_solo_consultan() -> None:
    hallazgos = []
    for n, linea in _lineas_de_codigo():
        for verbo in re.findall(r"\bsystemctl\s+(\S+)", linea):
            if verbo not in VERBOS_SYSTEMCTL:
                hallazgos.append(f"linea {n}: systemctl {verbo}")
        for verbo in re.findall(r"\bollama\s+([a-z]+)", linea):
            if verbo not in VERBOS_OLLAMA:
                hallazgos.append(f"linea {n}: ollama {verbo}")
        for verbo in re.findall(r"\btailscale\s+([a-z]+)", linea):
            if verbo not in VERBOS_TAILSCALE:
                hallazgos.append(f"linea {n}: tailscale {verbo}")
        if re.search(r"\bnmcli\b.*\b(up|down|modify|add|delete|connect|disconnect|radio|networking"
                     r"|reload|edit|set)\b", linea):
            hallazgos.append(f"linea {n}: nmcli que cambia algo")
        if re.search(r"\bip\b(\s+-\S+)*\s+(link|addr|address|route)\s+(set|add|del|delete|flush"
                     r"|change|replace)\b", linea):
            hallazgos.append(f"linea {n}: ip que cambia algo")
        if re.search(r"(?<![/\w.-])ssh\s+(?!-V\b)", linea):
            hallazgos.append(f"linea {n}: ssh solo puede ir con -V")
    assert not hallazgos, "\n".join(hallazgos)


def test_v4l2ctl_solo_con_opciones_de_lectura() -> None:
    usos = 0
    for n, linea in _lineas_de_codigo():
        if "v4l2-ctl" not in linea or not re.search(r"\brun\s+v4l2-ctl\b", linea):
            continue
        usos += 1
        resto = linea.split("v4l2-ctl", 1)[1].split()
        opciones = [t for t in resto if t.startswith("-")]
        raras = [o for o in opciones if o not in OPCIONES_V4L2CTL]
        assert not raras, f"linea {n}: v4l2-ctl con {raras}"
    assert usos >= 4, "faltan las consultas de v4l2-ctl (--info, --list-formats-ext, --list-ctrls-menus)"


def test_ninguna_redireccion_a_un_archivo_ni_tuberia() -> None:
    hallazgos = []
    for n, linea in _lineas_de_codigo():
        _, fuera = _partir(linea)
        if " | " in fuera:
            hallazgos.append(f"linea {n}: tuberia")
        for m in re.finditer(r"(>>?|<)\s*(\S*)", fuera):
            signo, destino = m.group(1), m.group(2)
            vale = destino.startswith("/dev/null") or (signo == ">" and re.match(r"&\d", destino))
            if not vale:
                hallazgos.append(f"linea {n}: redireccion {signo}{destino}")
    assert not hallazgos, "\n".join(hallazgos)


def test_cada_orden_pasa_por_timeout() -> None:
    """Cada trozo de codigo empieza por una ayuda con timeout, un builtin o una palabra de control."""
    hallazgos = []
    for n, linea in _lineas_de_codigo():
        if "$(" in linea.replace("$((", "") and not re.search(r"\$\(timeout\s", linea):
            hallazgos.append(f"linea {n}: $(...) sin timeout")
        trozos, _ = _partir(linea)
        for trozo in trozos:
            palabras = trozo.split()
            while palabras and palabras[0] in PREFIJOS:
                palabras.pop(0)
            if not palabras or palabras[0] == "for":
                continue
            primera = palabras[0]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", primera):
                continue                                   # asignacion; su $(...) ya se miro arriba
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\(\)", primera):
                continue                                   # definicion de una funcion
            if primera not in PERMITIDAS:
                hallazgos.append(f"linea {n}: '{primera}' sin timeout: {trozo}")
    assert not hallazgos, "\n".join(hallazgos)


def test_las_ayudas_ponen_timeout() -> None:
    texto = _texto()
    orden = re.search(r"^_orden\(\) \{\n(.*?)^\}", texto, re.S | re.M)
    assert orden and re.search(r'timeout -k 2 "\$tope" "\$@" </dev/null 2>&1', orden.group(1))
    hay = re.search(r"^hay\(\) \{\n(.*?)^\}", texto, re.S | re.M)
    assert hay and "timeout -k 2 5 which" in hay.group(1)
    assert re.search(r"readonly TOPE_ORDEN=10\b", texto)
    assert re.search(r"readonly ARRANQUE_MAX=90\b", texto)


def test_las_12_secciones_en_orden() -> None:
    encontradas = re.findall(r'^\s*seccion (\d+) "([^"]+)"$', _texto(), re.M)
    assert [int(n) for n, _ in encontradas] == list(range(1, 13))
    assert [nombre for _, nombre in encontradas] == SECCIONES


def test_comprueba_al_final_que_no_escribio_nada() -> None:
    texto = _texto()
    assert re.search(r'find "\$HOME" -maxdepth 2 -newermt "@\$INICIO"', texto)
    assert "printf -v INICIO '%(%s)T' -1" in texto       # la hora de inicio sin escribir una marca
    codigo = [linea for _, linea in _lineas_de_codigo()]
    assert codigo[-1] == 'main "$@" </dev/null', "main tiene que ir al final, con </dev/null"


# ---------------------------------------------------------------- el script, ejecutado sin ordenes reales

def _bash() -> str | None:
    """Un bash de verdad: Git for Windows en el PC, /bin/bash en Linux. Nunca el de WSL."""
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files"):
            candidato = Path(base) / "Git" / "usr" / "bin" / "bash.exe"
            if candidato.is_file():
                return str(candidato)
        return None
    for candidato in ("/bin/bash", "/usr/bin/bash"):
        if Path(candidato).is_file():
            return candidato
    return shutil.which("bash")


TIMEOUT_FALSO = """#!/bin/sh
echo "FALSO timeout $*"
case "$*" in
  "-k 2 10 uptime") exit 124 ;;
  "-k 2 10 tegrastats --interval 1000") exit 124 ;;
  "-k 2 10 lsusb -t") exit 3 ;;
esac
exit 0
"""


@pytest.fixture
def corrida(tmp_path: Path) -> subprocess.CompletedProcess:
    bash = _bash()
    if bash is None:
        pytest.skip("no hay un bash de Git for Windows ni de Linux")
    falsos = tmp_path / "falsos"
    falsos.mkdir()
    timeout_falso = falsos / "timeout"
    timeout_falso.write_bytes(TIMEOUT_FALSO.encode("ascii"))
    timeout_falso.chmod(0o755)
    casa = tmp_path / "casa"
    casa.mkdir()
    entorno = {"PATH": str(falsos), "HOME": str(casa), "USER": "prueba"}
    if sys.platform == "win32":
        entorno["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return subprocess.run([bash, "--norc", "--noprofile", "-s"], input=ESCANEO.read_bytes(),
                          capture_output=True, env=entorno, timeout=60, cwd=str(tmp_path))


def test_corre_entero_sin_ninguna_orden_real(corrida: subprocess.CompletedProcess) -> None:
    salida = corrida.stdout.decode("ascii", errors="replace").replace("\r\n", "\n")
    errores = corrida.stderr.decode("ascii", errors="replace")
    assert corrida.returncode == 0, errores
    assert errores.strip() == "", errores                 # ni un "command not found"
    assert "not found" not in salida and "no encontrad" not in salida
    cabeceras = re.findall(r"^=== \[(\d+)/12\] (.+) ===$", salida, re.M)
    assert [int(n) for n, _ in cabeceras] == list(range(1, 13))
    assert [nombre for _, nombre in cabeceras] == SECCIONES
    ordenes = re.findall(r"^\$ (.+)$", salida, re.M)
    # El find final (tope 15) va por $(timeout ...) y sin "$ ": se mira en la prueba siguiente.
    falsas = [(tope, orden) for tope, orden in re.findall(r"^FALSO timeout -k 2 (\d+) (.+)$", salida, re.M)
              if tope != "15"]
    # Cada "$ orden" llego al timeout falso con su tope; ninguna orden corrio por fuera.
    assert len(ordenes) >= 70
    assert [orden for _, orden in falsas] == ordenes
    assert all(int(tope) <= 10 for tope, _ in falsas)
    fin = re.search(r"^ESCANEO_FIN segundos=\d+ ordenes=(\d+) fallidas=(\d+) topes=(\d+) saltadas=(\d+)$",
                    salida, re.M)
    assert fin, salida[-2000:]
    assert int(fin.group(1)) == len(ordenes)
    assert (int(fin.group(2)), int(fin.group(3)), int(fin.group(4))) == (1, 1, 0)
    assert re.search(r"^TOPES: \[uptime\]$", salida, re.M)          # tegrastats se corta a proposito
    assert "[fin esperado: se corta a los 10 s a proposito]" in salida
    assert "[codigo 3]" in salida


def test_la_comprobacion_final_va_por_timeout(corrida: subprocess.CompletedProcess) -> None:
    salida = corrida.stdout.decode("ascii", errors="replace").replace("\r\n", "\n")
    assert re.search(r"^FALSO timeout -k 2 15 find .+ -maxdepth 2 -newermt @\d+$", salida, re.M)
    assert "find: NO vacio" in salida                    # el falso imprime: se ve que llego


# ---------------------------------------------------------------- escanear.ps1

def test_el_lanzador_es_ascii_y_usa_start_process_con_tope() -> None:
    datos = LANZADOR.read_bytes()
    assert all(b < 128 for b in datos), "escanear.ps1 tiene bytes que no son ASCII (PowerShell 5.1)"
    texto = datos.decode("ascii")
    assert "timeout -k 5 120 bash --norc --noprofile -s" in texto
    for trozo in ("Start-Process", "-RedirectStandardInput", "-RedirectStandardOutput",
                  "WaitForExit($TopeS * 1000)", "$p.Kill()", "$null = $p.Handle"):
        assert trozo in texto, trozo
    assert not re.search(r"\|\s*&?\s*(ssh|\$ssh)", texto), "una tuberia hacia ssh corrompe el script"
    assert not re.search(r"\b(scp|sftp)\b", texto)
    assert not re.search(r"\bgit\s+(commit|push|add)\b", texto)


def _lanzar(*argumentos: str, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-File", str(LANZADOR), *argumentos],
                          capture_output=True, timeout=60, cwd=str(cwd), env=env)


def test_el_lanzador_no_pisa_sus_parametros() -> None:
    """En PowerShell los nombres de variable no distinguen mayusculas: `$topes = ...` escribe en el
    parametro `[int]$TopeS` y para con "No se puede convertir ... a System.Int32" (P-1, 2026-10-29).
    Una variable puede reasignar su parametro a proposito, pero con el mismo nombre exacto."""
    texto = LANZADOR.read_bytes().decode("ascii")
    bloque = re.search(r"^param\((.*?)^\)", texto, re.S | re.M)
    assert bloque, "escanear.ps1 sin bloque param"
    parametros = re.findall(r"\]\s*\$([A-Za-z_]\w*)", bloque.group(1))
    assert {p.lower() for p in parametros} == {"alias", "salida", "topes", "script"}
    usadas = set(re.findall(r"\$([A-Za-z_]\w*)", texto[bloque.end():]))
    choques = sorted(v for v in usadas for p in parametros if v.lower() == p.lower() and v != p)
    assert not choques, f"variables que pisan un parametro (PowerShell no distingue mayusculas): {choques}"


SSH_FALSO_CS = r"""
using System;
using System.IO;
public static class SshFalso {
    public static int Main(string[] args) {
        Console.OpenStandardInput().CopyTo(Stream.Null);
        File.WriteAllText(Environment.GetEnvironmentVariable("ESCANEO_ARGS"), string.Join("\n", args));
        byte[] datos = File.ReadAllBytes(Environment.GetEnvironmentVariable("ESCANEO_FALSO"));
        using (Stream salida = Console.OpenStandardOutput()) { salida.Write(datos, 0, datos.Length); }
        return 0;
    }
}
"""


@pytest.fixture(scope="module")
def ssh_falso(tmp_path_factory) -> Path:
    """Un ssh.exe falso (compilado con Add-Type): se traga el script y devuelve un escaneo dado."""
    if sys.platform != "win32":
        pytest.skip("escanear.ps1 es de Windows PowerShell")
    carpeta = tmp_path_factory.mktemp("ssh_falso")
    fuente = carpeta / "SshFalso.cs"
    fuente.write_bytes(SSH_FALSO_CS.encode("ascii"))
    exe = carpeta / "ssh.exe"
    orden = (f"Add-Type -TypeDefinition ([System.IO.File]::ReadAllText('{fuente}')) "
             f"-OutputAssembly '{exe}' -OutputType ConsoleApplication")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
                       capture_output=True, timeout=120)
    assert r.returncode == 0 and exe.is_file(), r.stdout + r.stderr
    return carpeta


def _escaneo_completo(linea_topes: str) -> bytes:
    lineas = ["ESCANEO_INICIO formato=1 epoch=1793313272"]
    for n, nombre in enumerate(SECCIONES, 1):
        lineas += ["", f"=== [{n}/12] {nombre} ===", "$ hostname", "yahboom"]
    lineas += ["", "=== comprobacion final: lo que cambio en el HOME desde el inicio ===",
               "find: vacio (el escaneo no escribio nada en el HOME)", "",
               "ESCANEO_FIN segundos=11 ordenes=78 fallidas=7 topes=0 saltadas=0", linea_topes]
    return ("\n".join(lineas) + "\n").encode("ascii")


@pytest.mark.parametrize("linea_topes", ["TOPES: ninguno", "TOPES: [uptime] [lsusb -t]"])
def test_el_lanzador_resume_un_escaneo_completo(ssh_falso: Path, linea_topes: str, tmp_path: Path) -> None:
    """De punta a punta con un ssh falso: el resumen final (el que fallo en el P-1) sale con 0."""
    escaneo = _escaneo_completo(linea_topes)
    (tmp_path / "falso.txt").write_bytes(escaneo)
    entorno = dict(os.environ)
    entorno["PATH"] = str(ssh_falso) + os.pathsep + entorno.get("PATH", "")
    entorno["ESCANEO_FALSO"] = str(tmp_path / "falso.txt")
    entorno["ESCANEO_ARGS"] = str(tmp_path / "args.txt")
    r = _lanzar("-Alias", "yahboom", "-Salida", "s.txt", "-TopeS", "60", cwd=tmp_path, env=entorno)
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 0, salida + r.stderr.decode("ascii", errors="replace")
    assert str(ssh_falso / "ssh.exe") in salida                # uso el falso, no el ssh real
    assert "Secciones: 12 de 12" in salida
    assert "ESCANEO_FIN segundos=11 ordenes=78 fallidas=7 topes=0 saltadas=0" in salida
    assert linea_topes in salida
    assert "find: vacio" in salida
    assert (tmp_path / "s.txt").read_bytes() == escaneo
    argumentos = (tmp_path / "args.txt").read_text(encoding="ascii").split("\n")
    assert argumentos[:4] == ["-T", "-o", "ConnectTimeout=15", "yahboom"]
    assert " ".join(argumentos[4:]) == "timeout -k 5 120 bash --norc --noprofile -s"


@pytest.mark.skipif(sys.platform != "win32", reason="escanear.ps1 es de Windows PowerShell")
@pytest.mark.parametrize("argumentos, motivo", [
    ((), "falta -Alias"),
    (("-Alias", "-oProxyCommand=calc", "-Salida", "s.txt", "-TopeS", "180"), "no vale"),
    (("-Alias", "yah boom", "-Salida", "s.txt", "-TopeS", "180"), "no vale"),
    (("-Alias", "yahboom", "-TopeS", "180"), "falta -Salida"),
    (("-Alias", "yahboom", "-Salida", "s.txt"), "-TopeS tiene que ir de 60 a 900"),
    (("-Alias", "yahboom", "-Salida", "s.txt", "-TopeS", "5000"), "-TopeS tiene que ir de 60 a 900"),
    (("-Alias", "yahboom", "-Salida", "ya.txt", "-TopeS", "180"), "no se pisa"),
    (("-Alias", "yahboom", "-Salida", "s.txt", "-TopeS", "180", "-Script", "no_existe.sh"), "no existe"),
    (("-Alias", "yahboom", "-Salida", "s.txt", "-TopeS", "180", "-Script", "crlf.sh"), "CRLF"),
])
def test_el_lanzador_para_con_2_antes_de_conectar(argumentos, motivo, tmp_path: Path) -> None:
    (tmp_path / "ya.txt").write_bytes(b"de antes\n")
    (tmp_path / "crlf.sh").write_bytes(b"#!/usr/bin/env bash\r\necho hola\r\n")
    r = _lanzar(*argumentos, cwd=tmp_path)
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 2, salida + r.stderr.decode("ascii", errors="replace")
    assert motivo in salida, salida
    assert "Escaneando" not in salida                     # no llego a lanzar ssh
    assert not (tmp_path / "s.txt").exists()
    assert (tmp_path / "ya.txt").read_bytes() == b"de antes\n"
