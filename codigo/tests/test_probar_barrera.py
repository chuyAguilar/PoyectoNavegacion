"""`probar_barrera.ps1` de punta a punta con un ssh.exe y un sftp.exe falsos (meta 007, fase 2).

El falso (compilado con Add-Type, una vez por modulo) responde a cada llamada segun un archivo de
reglas: por la orden exacta que va detras del alias (`igual`) o por un texto en los argumentos
(`contiene`), con su codigo, su espera, su salida y su error; lo que no casa con ninguna regla sale
con 126, como el guardian. Asi se comprueba, sin Jetson, que el script lanza los 30 casos con los
argumentos del plan, lee bien cada respuesta, escribe la tabla y sale con 0 solo si los 30 dan lo
esperado (y con 1 si uno falla). Tambien que para con 2 antes de conectar si una entrada no vale.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import CODIGO_DIR

LANZADOR = CODIGO_DIR / "linux" / "probar_barrera.ps1"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="probar_barrera.ps1 es de Windows PowerShell")

FALSO_CS = r"""
using System;
using System.IO;
using System.Threading;
public static class BarreraFalso {
    public static int Main(string[] args) {
        Console.OpenStandardInput().CopyTo(Stream.Null);
        string alias = Environment.GetEnvironmentVariable("BARRERA_ALIAS");
        string todo = string.Join(" ", args);
        int i = Array.IndexOf(args, alias);
        string orden = i >= 0 ? string.Join(" ", args, i + 1, args.Length - i - 1) : "";
        File.AppendAllText(Environment.GetEnvironmentVariable("BARRERA_LLAMADAS"),
            Path.GetFileName(Environment.GetCommandLineArgs()[0]) + "\t" + todo + "\t" + args.Length + "\n");
        int codigo = 126; int ms = 0; string salida = ""; string error = "NEGADO: por defecto del falso\n";
        foreach (string linea in File.ReadAllLines(Environment.GetEnvironmentVariable("BARRERA_REGLAS"))) {
            if (linea.Trim().Length == 0) continue;
            string[] t = linea.Split('\t');
            bool casa = t[0] == "igual" ? orden == t[1] : todo.Contains(t[1]);
            if (!casa) continue;
            codigo = int.Parse(t[2]); ms = int.Parse(t[3]);
            salida = t[4].Replace("\\n", "\n"); error = t[5].Replace("\\n", "\n");
            break;
        }
        if (ms > 0) Thread.Sleep(ms);
        Console.Out.Write(salida); Console.Out.Flush();
        Console.Error.Write(error); Console.Error.Flush();
        return codigo;
    }
}
"""

REGISTRO_TOPE = ('{"codigo": 124, "duracion_s": 3.004, "hora": "2026-10-29T20:00:00+08:00", "ip": "192.0.2.10", '
                 '"orden": "prueba-tope", "permitido": true, "pid": 4242, "tope": true, "verbo": "prueba-tope"}')
PROCESOS = "    PID    PGID     ELAPSED %CPU   RSS COMMAND\\n   4300    4300       00:00  0.0  3000 ps -u navagente\\n"


def _reglas(ayuda_codigo: int = 0) -> str:
    filas = [
        # el -tt va antes que `ayuda`: la primera regla que casa gana
        ("contiene", "-tt", 0, 0, "nav-guardian 1\\n", "PTY allocation request failed on channel 0\\n"),
        ("igual", "ayuda", ayuda_codigo, 0, "nav-guardian 1: la cuenta navagente solo ejecuta estos verbos\\n", ""),
        ("igual", "info sistema", 0, 0, "PRETTY_NAME=Ubuntu 22.04.5 LTS\\n", ""),
        ("igual", "info red", 0, 0, "lo UNKNOWN 127.0.0.1/8\\n", ""),
        ("igual", "procesos", 0, 0, PROCESOS, ""),
        ("igual", "registro 50", 0, 0, REGISTRO_TOPE + "\\n", ""),
        ("igual", "registro 1", 0, 0, REGISTRO_TOPE + "\\n", ""),
        ("igual", "wip estado", 0, 0, "sin copia WIP\\n", ""),
        ("igual", "prueba-tope", 124, 3000, "", "TOPE: cortada a los 3 s\\n"),
        ("contiene", "sftp_lote.txt", 255, 0, "", "Connection closed.\\nConnection closed\\n"),
    ]
    return "\n".join("\t".join(str(c) for c in f) for f in filas) + "\n"


@pytest.fixture(scope="module")
def falsos(tmp_path_factory) -> Path:
    carpeta = tmp_path_factory.mktemp("barrera_falsos")
    fuente = carpeta / "BarreraFalso.cs"
    fuente.write_bytes(FALSO_CS.encode("ascii"))
    exe = carpeta / "ssh.exe"
    orden = (f"Add-Type -TypeDefinition ([System.IO.File]::ReadAllText('{fuente}')) "
             f"-OutputAssembly '{exe}' -OutputType ConsoleApplication")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
                       capture_output=True, timeout=120)
    assert r.returncode == 0 and exe.is_file(), r.stdout + r.stderr
    (carpeta / "sftp.exe").write_bytes(exe.read_bytes())
    return carpeta


def _lanzar(falsos: Path, tmp_path: Path, reglas: str, *argumentos: str) -> subprocess.CompletedProcess:
    (tmp_path / "reglas.txt").write_text(reglas, encoding="ascii")
    entorno = dict(os.environ)
    entorno["PATH"] = str(falsos) + os.pathsep + entorno.get("PATH", "")
    entorno["BARRERA_REGLAS"] = str(tmp_path / "reglas.txt")
    entorno["BARRERA_LLAMADAS"] = str(tmp_path / "llamadas.txt")
    entorno["BARRERA_ALIAS"] = "nav-jetson"
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                           str(LANZADOR), *argumentos], capture_output=True, timeout=300, cwd=str(tmp_path),
                          env=entorno)


def test_el_lanzador_es_ascii_y_no_lleva_opciones_de_ssh_salvo_los_casos_21_y_22() -> None:
    datos = LANZADOR.read_bytes()
    assert all(b < 128 for b in datos), "probar_barrera.ps1 tiene bytes que no son ASCII (PowerShell 5.1)"
    texto = datos.decode("ascii")
    assert "Start-Process" in texto and "-RedirectStandardInput" in texto and "$null = $p.Handle" in texto
    assert not re.search(r"\|\s*&?\s*(ssh|\$ssh)", texto)
    assert texto.count("'git push'") == 1 and "git commit" not in texto and "git add" not in texto   # solo el caso 16
    opciones = re.findall(r"@\('(-[A-Za-z]+)'", texto)
    assert sorted(set(opciones)) == ["-b", "-m", "-o", "-tt"]     # -o/-L (caso 21), -tt (22), sftp -b (23), python -m
    assert "'-L', '9999:127.0.0.1:22'" in texto and "'ClearAllForwardings=no'" in texto
    assert "scp" not in texto.replace("Las opciones", "")


def test_los_30_casos_dan_lo_esperado_con_el_guardian_falso(falsos: Path, tmp_path: Path) -> None:
    r = _lanzar(falsos, tmp_path, _reglas(), "-Alias", "nav-jetson", "-Salida", "salida", "-TopeS", "20")
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 0, salida + r.stderr.decode("ascii", errors="replace")
    assert "Casos: 30 de 30" in salida
    tablas = list((tmp_path / "salida").glob("barrera_*.md"))
    assert len(tablas) == 1
    tabla = tablas[0].read_text(encoding="utf-8")
    filas = [l for l in tabla.splitlines() if re.match(r"\| \d+ \|", l)]
    assert len(filas) == 30 and all(l.endswith("| si |") for l in filas)
    assert sorted(p.name for p in (tmp_path / "salida" / "casos").glob("[0-9][0-9].txt")) == [f"{n:02d}.txt" for n in range(1, 31)]
    llamadas = (tmp_path / "llamadas.txt").read_text(encoding="utf-8").splitlines()
    ordenes = [l.split("\t")[1] for l in llamadas]
    # los 16 negados, con sus argumentos exactos (el 12 llega entero, con sus comillas)
    for esperada in ("nav-jetson", "nav-jetson sudo true", "nav-jetson apt-get install x", "nav-jetson reboot",
                     "nav-jetson systemctl stop ollama", "nav-jetson nvpmodel -m 0", "nav-jetson jetson_clocks",
                     "nav-jetson bash -c id", "nav-jetson py wip os", "nav-jetson py wip tracker --record /etc/x",
                     "nav-jetson traer ../../etc/passwd", 'nav-jetson info "red; id"', "nav-jetson docker ps",
                     "nav-jetson ollama list", "nav-jetson crontab -l", "nav-jetson git push",
                     "-o ClearAllForwardings=no -L 9999:127.0.0.1:22 nav-jetson prueba-tope", "-tt nav-jetson ayuda",
                     "nav-jetson prueba-tope", "nav-jetson registro 1", "nav-jetson procesos", "nav-jetson ayuda",
                     "nav-jetson info sistema", "nav-jetson info red", "nav-jetson registro 50"):
        assert esperada in ordenes, esperada
    assert ordenes.count("nav-jetson wip recibir") == 4 and ordenes.count("nav-jetson wip estado") == 5
    assert ordenes.count("nav-jetson prueba-tope") == 2                  # casos 24 y 25 (el 21 lleva -L)
    assert any(l.startswith("sftp.exe\t-b ") and l.endswith(" nav-jetson\t3") for l in llamadas)
    # cada orden llega a ssh como un solo argumento detras del alias: "sudo true" no se parte
    assert "ssh.exe\tnav-jetson sudo true\t2" in llamadas and 'ssh.exe\tnav-jetson info "red; id"\t2' in llamadas
    assert (tmp_path / "salida" / "casos" / "tars" / "nrrd.tar").is_file()


def test_una_salida_con_espacio_llega_entera(falsos: Path, tmp_path: Path) -> None:
    """P-2, 2026-11-02: con -Salida "Claude outputs/...", Start-Process partia la ruta y tars_malos paraba."""
    r = _lanzar(falsos, tmp_path, _reglas(), "-Alias", "nav-jetson", "-Salida", "con espacio/sal ida", "-TopeS", "20")
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 0, salida + r.stderr.decode("ascii", errors="replace")
    assert "Casos: 30 de 30" in salida
    casos = tmp_path / "con espacio" / "sal ida" / "casos"
    assert all((casos / "tars" / f"{n}.tar").is_file() for n in ("padre", "absoluta", "enlace", "nrrd"))
    llamadas = (tmp_path / "llamadas.txt").read_text(encoding="utf-8").splitlines()
    lote = str(casos / "sftp_lote.txt")
    assert f"sftp.exe\t-b {lote} nav-jetson\t3" in llamadas, [l for l in llamadas if l.startswith("sftp")]


def test_un_caso_que_no_da_lo_esperado_sale_con_1(falsos: Path, tmp_path: Path) -> None:
    r = _lanzar(falsos, tmp_path, _reglas(ayuda_codigo=126), "-Alias", "nav-jetson", "-Salida", "salida", "-TopeS", "20")
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 1, salida + r.stderr.decode("ascii", errors="replace")
    assert "Casos: 29 de 30" in salida
    tabla = next((tmp_path / "salida").glob("barrera_*.md")).read_text(encoding="utf-8")
    assert re.search(r"^\| 26 \| ayuda \| codigo 0 \| codigo 126 \| NO \|$", tabla, re.M)


@pytest.mark.parametrize("argumentos, motivo", [
    ((), "falta -Alias"),
    (("-Alias", "-oProxyCommand=calc", "-Salida", "s", "-TopeS", "30"), "no vale"),
    (("-Alias", "nav-jetson", "-TopeS", "30"), "falta -Salida"),
    (("-Alias", "nav-jetson", "-Salida", "s"), "-TopeS tiene que ir de 10 a 300"),
    (("-Alias", "nav-jetson", "-Salida", "s", "-TopeS", "5"), "-TopeS tiene que ir de 10 a 300"),
])
def test_el_lanzador_para_con_2_antes_de_conectar(argumentos, motivo, tmp_path: Path) -> None:
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                        str(LANZADOR), *argumentos], capture_output=True, timeout=60, cwd=str(tmp_path))
    salida = r.stdout.decode("ascii", errors="replace")
    assert r.returncode == 2, salida + r.stderr.decode("ascii", errors="replace")
    assert motivo in salida, salida
    assert "Probando" not in salida
    assert not (tmp_path / "s").exists()
