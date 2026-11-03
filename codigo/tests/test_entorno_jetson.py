"""El entorno de la Jetson (meta 007, fase 3 · El entorno en la Jetson).

- `requirements-jetson.txt` fija con == las versiones del venv que corre la suite (en el PC, las
  del PC; en la Jetson, las del venv que instalo `instalar_entorno.sh`), cumple los rangos de
  `requirements.txt` y no lleva lo que el tracker de la Jetson no usa.
- `instalar_entorno.sh` es ASCII y LF, no pide privilegios ni borra, fija uv con su sha256 y el
  mismo Python del PC, y para con 2 ante una opcion que no vale (sin bajar nada).
- `enviar_wip.ps1`, de punta a punta con un ssh.exe falso que calcula el sha256 de lo que recibe:
  manda un tar sin lo que no viaja, que el `recibir_wip` del guardian acepta con el mismo sha256;
  sale con 3 si los sha256 no coinciden o el guardian niega, y con 2 si una entrada no vale.
- En la Jetson (cuenta navagente), el clon disperso no tiene los datos de paciente.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import io
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

import pytest

from linux import guardian as g

from .conftest import CODIGO_DIR

LINUX_DIR = CODIGO_DIR / "linux"
REQ_JETSON = CODIGO_DIR / "requirements-jetson.txt"
REQ_PC = CODIGO_DIR / "requirements.txt"
INSTALAR = LINUX_DIR / "instalar_entorno.sh"
ENVIAR = LINUX_DIR / "enviar_wip.ps1"
PAQUETES = {"opencv-python", "numpy", "scipy", "pyyaml", "pyigtl", "pytest"}


def _activas(ruta: Path) -> list[str]:
    return [l.split("#", 1)[0].strip() for l in ruta.read_text(encoding="ascii").splitlines()
            if l.split("#", 1)[0].strip()]


def _fijadas() -> dict[str, str]:
    fijadas = {}
    for linea in _activas(REQ_JETSON):
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==(\S+)", linea)
        assert m, f"linea sin == en requirements-jetson.txt: {linea!r}"
        fijadas[m.group(1).lower()] = m.group(2)
    return fijadas


def _variable(nombre: str) -> str:
    m = re.search(rf'^{nombre}="([^"]+)"$', INSTALAR.read_text(encoding="ascii"), re.M)
    assert m, f"instalar_entorno.sh no define {nombre}"
    return m.group(1)


# ---------------------------------------------------------------- requirements-jetson.txt

def test_requirements_jetson_fija_las_versiones_del_venv_que_corre() -> None:
    fijadas = _fijadas()
    assert set(fijadas) == PAQUETES
    distintas = {n: (v, md.version(n)) for n, v in fijadas.items() if md.version(n) != v}
    assert not distintas, f"requirements-jetson.txt no coincide con este venv: {distintas}"


def test_requirements_jetson_cumple_requirements_txt_y_deja_fuera_lo_del_pc() -> None:
    from packaging.requirements import Requirement

    del_pc = {Requirement(l).name.lower(): Requirement(l) for l in _activas(REQ_PC)}
    for nombre, version in _fijadas().items():
        assert nombre in del_pc, f"{nombre} no esta en requirements.txt"
        assert del_pc[nombre].specifier.contains(version), f"{nombre}=={version} fuera de {del_pc[nombre]}"
    activas = " ".join(_activas(REQ_JETSON)).lower()
    for fuera in ("pyside6", "open3d", "pyorbbecsdk", "matplotlib", "gtsam"):
        assert fuera not in activas
    comentada = re.search(r"^#\s*gtsam==(\S+)", REQ_JETSON.read_text(encoding="ascii"), re.M)
    assert comentada and comentada.group(1) == _variable("GTSAM_VERSION")


# ---------------------------------------------------------------- instalar_entorno.sh

def test_instalar_entorno_es_ascii_lf_y_no_pide_privilegios_ni_borra() -> None:
    datos = INSTALAR.read_bytes()
    assert all(b < 128 for b in datos), "instalar_entorno.sh tiene bytes que no son ASCII"
    assert b"\r" not in datos, "instalar_entorno.sh tiene CR: bash lo leeria mal"
    assert datos.startswith(b"#!/usr/bin/env bash\n")
    codigo = "\n".join(l for l in datos.decode("ascii").splitlines() if not l.lstrip().startswith("#"))
    for prohibida in (r"\bsudo\b", r"\bsu\b", r"\bapt(-get)?\b", r"\bdpkg\b", r"\bsnap\b", r"\bsystemctl\b",
                      r"\bnvpmodel\b", r"\bjetson_clocks\b", r"\brm\b", r"\bcurl\b", r"\bwget\b",
                      r"\|\s*(ba)?sh\b", r"--system\b", r"--break-system-packages"):
        assert not re.search(prohibida, codigo), prohibida
    # todo pip pasa por el uv fijado, contra un venv con --python
    for linea in (l for l in codigo.splitlines() if re.search(r"\bpip\b", l)):
        assert '"$UV" pip install --python "$VENV' in linea, linea


def test_instalar_entorno_fija_uv_con_su_sha256_y_el_python_del_pc() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", _variable("UV_VERSION"))
    assert re.fullmatch(r"[0-9a-f]{64}", _variable("UV_SHA256"))
    assert _variable("UV_URL").startswith("https://github.com/astral-sh/uv/releases/download/")
    assert _variable("PYTHON_VERSION") == (CODIGO_DIR / ".python-version").read_text(encoding="ascii").strip()
    texto = INSTALAR.read_text(encoding="ascii")
    assert '"$sha" != "$UV_SHA256"' in texto                      # compara con el sha256 escrito aqui
    assert "--managed-python" in texto                           # nunca el Python del sistema


def test_el_guardian_lanza_este_script(tmp_path: Path) -> None:
    orden = g.decidir(["entorno", "instalar", "wip", "--gtsam"], tmp_path)
    assert orden.argv[0] == "bash" and orden.argv[2:] == ["--gtsam"]
    assert Path(orden.argv[1]).parts[-2:] == ("linux", "instalar_entorno.sh")


def _bash() -> str | None:
    """Un bash de verdad: Git for Windows en el PC, /bin/bash en Linux. Nunca el de WSL."""
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files"):
            candidato = Path(base) / "Git" / "usr" / "bin" / "bash.exe"
            if candidato.is_file():
                return str(candidato)
        return None
    return "/bin/bash" if Path("/bin/bash").is_file() else None


def test_instalar_entorno_para_con_2_ante_una_opcion_que_no_vale(tmp_path: Path) -> None:
    bash = _bash()
    if bash is None:
        pytest.skip("no hay un bash de Git for Windows ni de Linux")
    entorno = dict(os.environ, HOME=str(tmp_path))
    r = subprocess.run([bash, "--norc", "--noprofile", str(INSTALAR), "--otra"], capture_output=True,
                       timeout=60, env=entorno)
    assert r.returncode == 2, r.stdout + r.stderr
    assert b"ENTORNO_FIN entrada: opcion que no vale: '--otra'" in r.stdout
    assert not any(tmp_path.iterdir()), "no tenia que escribir nada"


@pytest.mark.skipif(platform.machine().lower() in ("aarch64", "arm64"), reason="en aarch64 instalaria de verdad")
def test_instalar_entorno_para_con_2_fuera_de_aarch64(tmp_path: Path) -> None:
    bash = _bash()
    if bash is None:
        pytest.skip("no hay un bash de Git for Windows ni de Linux")
    entorno = dict(os.environ, HOME=str(tmp_path))
    r = subprocess.run([bash, "--norc", "--noprofile", str(INSTALAR)], capture_output=True, timeout=60, env=entorno)
    assert r.returncode == 2, r.stdout + r.stderr
    assert b"el uv fijado es el de aarch64" in r.stdout
    assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------- enviar_wip.ps1

FALSO_CS = r"""
using System;
using System.IO;
using System.Security.Cryptography;
public static class WipFalso {
    public static int Main(string[] args) {
        MemoryStream m = new MemoryStream();
        Console.OpenStandardInput().CopyTo(m);
        byte[] datos = m.ToArray();
        File.WriteAllBytes(Environment.GetEnvironmentVariable("WIP_RECIBIDO"), datos);
        File.AppendAllText(Environment.GetEnvironmentVariable("WIP_LLAMADAS"), string.Join("|", args) + "\n");
        string modo = Environment.GetEnvironmentVariable("WIP_MODO");
        if (modo == "negado") { Console.Error.Write("NEGADO: por el falso\n"); return 126; }
        string hex = BitConverter.ToString(SHA256.Create().ComputeHash(datos)).Replace("-", "").ToLowerInvariant();
        if (modo == "malo") hex = new string('0', 64);
        Console.Out.Write("sha256 " + hex + "\n");
        return 0;
    }
}
"""

pytestmark_ps = pytest.mark.skipif(sys.platform != "win32", reason="enviar_wip.ps1 es de Windows PowerShell")


@pytest.fixture(scope="module")
def ssh_falso(tmp_path_factory) -> Path:
    if sys.platform != "win32":
        pytest.skip("enviar_wip.ps1 es de Windows PowerShell")
    carpeta = tmp_path_factory.mktemp("wip_falso")
    fuente = carpeta / "WipFalso.cs"
    fuente.write_bytes(FALSO_CS.encode("ascii"))
    exe = carpeta / "ssh.exe"
    orden = (f"Add-Type -TypeDefinition ([System.IO.File]::ReadAllText('{fuente}')) "
             f"-OutputAssembly '{exe}' -OutputType ConsoleApplication")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
                       capture_output=True, timeout=120)
    assert r.returncode == 0 and exe.is_file(), r.stdout + r.stderr
    return carpeta


def _arbol(raiz: Path) -> Path:
    """Un codigo/ de juguete con lo que viaja y lo que no."""
    codigo = raiz / "con espacio" / "codigo"
    for rel, texto in {
        "tracker.py": "print('hola')\n",
        "linux/instalar_entorno.sh": "#!/usr/bin/env bash\necho hola\n",
        "tests/data/uno.csv": "a,b\n1,2\n",
        "requirements-jetson.txt": "numpy==1.26.4\n",
        "historico/iter2/viejo.py": "x = 1\n",
        "historico/iter2/volumen.nrrd": "no es un volumen\n",
        ".venv/Lib/site.py": "x = 1\n",
        "__pycache__/tracker.cpython-311.pyc": "x\n",
        "vision/__pycache__/a.cpython-311.pyc": "x\n",
        ".pytest_cache/v/cache/nodeids": "[]\n",
        "data/suelto.dcm": "no es un dicom\n",
    }.items():
        archivo = codigo / rel
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(texto.encode("ascii"))       # write_text pondria CRLF en Windows
    return codigo


def _lanzar(ssh_falso: Path, tmp_path: Path, modo: str, *argumentos: str) -> subprocess.CompletedProcess:
    entorno = dict(os.environ)
    entorno["PATH"] = str(ssh_falso) + os.pathsep + entorno.get("PATH", "")
    entorno["WIP_RECIBIDO"] = str(tmp_path / "recibido.tar")
    entorno["WIP_LLAMADAS"] = str(tmp_path / "llamadas.txt")
    entorno["WIP_MODO"] = modo
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                           str(ENVIAR), *argumentos], capture_output=True, timeout=180, cwd=str(tmp_path),
                          env=entorno)


@pytestmark_ps
def test_enviar_wip_es_ascii_y_manda_por_start_process() -> None:
    datos = ENVIAR.read_bytes()
    assert all(b < 128 for b in datos), "enviar_wip.ps1 tiene bytes que no son ASCII (PowerShell 5.1)"
    texto = datos.decode("ascii")
    assert "Start-Process" in texto and "-RedirectStandardInput" in texto and "$null = $p.Handle" in texto
    assert not re.search(r"\|\s*&?\s*(ssh|\$ssh)", texto)
    assert "@($Alias, 'wip recibir')" in texto


@pytestmark_ps
def test_enviar_wip_manda_lo_que_el_guardian_acepta_con_el_mismo_sha256(ssh_falso: Path, tmp_path: Path) -> None:
    codigo = _arbol(tmp_path)
    r = _lanzar(ssh_falso, tmp_path, "ok", "-Alias", "nav-jetson", "-TopeS", "60", "-Codigo", str(codigo))
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 0, salida + r.stderr.decode("ascii", errors="replace")
    assert "sha256: coinciden" in salida
    assert (tmp_path / "llamadas.txt").read_text(encoding="ascii").splitlines() == ["nav-jetson|wip recibir"]
    datos = (tmp_path / "recibido.tar").read_bytes()
    assert f"sha256 local:  {hashlib.sha256(datos).hexdigest()}" in salida
    home = tmp_path / "home"
    assert g.recibir_wip(io.BytesIO(datos), home) == hashlib.sha256(datos).hexdigest()
    wip = home / "nav-wip" / "codigo"
    llegaron = sorted(p.relative_to(wip).as_posix() for p in wip.rglob("*") if p.is_file())
    assert llegaron == ["linux/instalar_entorno.sh", "requirements-jetson.txt", "tests/data/uno.csv", "tracker.py"]
    assert (wip / "linux" / "instalar_entorno.sh").read_bytes() == b"#!/usr/bin/env bash\necho hola\n"   # LF intacto


@pytestmark_ps
@pytest.mark.parametrize("modo, texto", [("malo", "los sha256 no coinciden"), ("negado", "NEGADO por el guardian")])
def test_enviar_wip_sale_con_3_si_no_coincide_o_lo_niegan(ssh_falso: Path, tmp_path: Path, modo: str,
                                                          texto: str) -> None:
    codigo = _arbol(tmp_path)
    r = _lanzar(ssh_falso, tmp_path, modo, "-Alias", "nav-jetson", "-TopeS", "60", "-Codigo", str(codigo))
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 3, salida
    assert texto in salida


@pytestmark_ps
@pytest.mark.parametrize("argumentos, motivo", [
    ((), "falta -Alias"),
    (("-Alias", "-oProxyCommand=calc", "-TopeS", "60"), "no vale"),
    (("-Alias", "nav-jetson"), "-TopeS tiene que ir de 10 a 600"),
    (("-Alias", "nav-jetson", "-TopeS", "601"), "-TopeS tiene que ir de 10 a 600"),
    (("-Alias", "nav-jetson", "-TopeS", "60", "-Codigo", "no-existe"), "no existe la carpeta"),
    (("-Alias", "nav-jetson", "-TopeS", "60", "-Codigo", "."), "tiene que llamarse codigo"),
])
def test_enviar_wip_para_con_2_antes_de_conectar(argumentos, motivo, tmp_path: Path) -> None:
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                        str(ENVIAR), *argumentos], capture_output=True, timeout=60, cwd=str(tmp_path))
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 2, salida + r.stderr.decode("ascii", errors="replace")
    assert motivo in salida, salida
    assert "Mandando" not in salida


# ---------------------------------------------------------------- en la Jetson

CLON = Path.home() / "nav" / "repo"


@pytest.mark.skipif(not (sys.platform.startswith("linux") and (CLON / ".git").is_dir()),
                    reason="solo en la Jetson, con el clon de `repo clonar`")
def test_el_clon_de_la_jetson_no_tiene_datos_de_paciente() -> None:
    assert not (CLON / "herramientas").exists()
    assert not (CLON / "documentos").exists()
    malos = []
    for raiz, carpetas, archivos in os.walk(CLON):
        carpetas[:] = [c for c in carpetas if c != ".git"]
        malos += [os.path.join(raiz, a) for a in archivos if a.lower().endswith((".nrrd", ".dcm"))]
    assert not malos, malos[:5]
