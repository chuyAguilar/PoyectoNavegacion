"""El guardian de la cuenta `navagente` (meta 007, fase 2 · La barrera de seguridad para los agentes).

Sin Jetson: `decidir` da la `Orden` esperada para cada verbo permitido y lanza `Negado` para cada
caso prohibido (al menos uno por cada linea de «Lo prohibido» del plan); `partir` niega los
metacaracteres; `dentro_de` niega `..`, las rutas absolutas fuera y los enlaces; `recibir_wip`
niega los tar fabricados (`linux/tars_malos.py`) sin extraer nada; `entorno_limpio` no lleva
`LD_*` ni `PYTHONPATH`; `main` registra cada intento. Lo de tope y grupo de procesos corre solo
en Linux (en la Jetson, fase 4) y aqui se salta.

Tambien mira el texto de `instalar_guardian.sh` y `desinstalar_guardian.sh` (ASCII, LF, el drop-in
exacto, `sshd -t` antes de recargar) y los corre con `--ayuda` y sin argumentos, que paran antes
de pedir root.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

from linux import guardian as g
from linux import tars_malos

from .conftest import CODIGO_DIR

LINUX_DIR = CODIGO_DIR / "linux"
EN_LINUX = sys.platform.startswith("linux")


@pytest.fixture
def home(tmp_path: Path) -> Path:
    casa = tmp_path / "home" / "navagente"
    for partes in g.ARBOLES.values():
        casa.joinpath(*partes).mkdir(parents=True)
    (casa / "nav" / "repo" / ".git").mkdir()
    g.ruta_salidas(casa).mkdir()
    g.ruta_python(casa).parent.mkdir(parents=True)
    g.ruta_python(casa).write_text("", encoding="utf-8")
    return casa


# ---------------------------------------------------------------- partir

@pytest.mark.parametrize("orden", ["info red; id", "ayuda | cat", "ayuda && reboot", "info $(id)",
                                   "info `id`", "traer x > /etc/y", "traer < /etc/passwd", "ayuda\nreboot",
                                   "ayuda\x00", "info 'red"])
def test_partir_niega_metacaracteres_y_mal_formadas(orden: str) -> None:
    with pytest.raises(g.Negado):
        g.partir(orden)


def test_partir_niega_vacio_y_largo() -> None:
    for orden in ("", "   "):
        with pytest.raises(g.Negado, match="sin orden"):
            g.partir(orden)
    with pytest.raises(g.Negado, match="4096"):
        g.partir("ayuda " + "x" * 5000)


def test_partir_respeta_comillas() -> None:
    assert g.partir('suite wip -k "guardian and not tope"') == ["suite", "wip", "-k", "guardian and not tope"]
    assert g.partir("info  v4l2   platform-3610000.usb-usb-0:2.1:1.0-video-index0") == [
        "info", "v4l2", "platform-3610000.usb-usb-0:2.1:1.0-video-index0"]


# ---------------------------------------------------------------- dentro_de

def test_dentro_de_acepta_lo_que_cae_dentro(tmp_path: Path) -> None:
    raiz = tmp_path / "salidas"
    (raiz / "a").mkdir(parents=True)
    assert g.dentro_de("a/x.npz", [raiz]) == (raiz / "a" / "x.npz").resolve()
    assert g.dentro_de(str(raiz / "a"), [tmp_path / "otra", raiz]) == (raiz / "a").resolve()


def test_dentro_de_niega_padre_absoluta_fuera_y_nulo(tmp_path: Path) -> None:
    raiz = tmp_path / "salidas"
    raiz.mkdir()
    with pytest.raises(g.Negado, match=r"\.\."):
        g.dentro_de("a/../../x", [raiz])
    with pytest.raises(g.Negado, match="fuera"):
        g.dentro_de(str(tmp_path / "fuera.txt"), [raiz])
    with pytest.raises(g.Negado, match="fuera"):
        g.dentro_de(str(Path("/etc/passwd").resolve()), [raiz])
    with pytest.raises(g.Negado, match="nulo"):
        g.dentro_de("a\x00b", [raiz])


def test_dentro_de_niega_un_enlace_que_sale(tmp_path: Path) -> None:
    raiz = tmp_path / "salidas"
    raiz.mkdir()
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    try:
        os.symlink(str(fuera), str(raiz / "enlace"), target_is_directory=True)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"sin permiso para crear enlaces aqui: {e}")
    with pytest.raises(g.Negado, match="fuera"):
        g.dentro_de("enlace/x.txt", [raiz])


# ---------------------------------------------------------------- decidir: permitidos

def test_decidir_ayuda_e_internas(home: Path) -> None:
    o = g.decidir(["ayuda"], home)
    assert (o.verbo, o.argv, o.pesada, o.entrada) == ("ayuda", [], False, False)
    o = g.decidir(["wip", "recibir"], home)
    assert (o.verbo, o.argv, o.entrada, o.tope_s) == ("wip recibir", [], True, 120.0)
    assert g.decidir(["wip", "estado"], home).verbo == "wip estado"
    assert g.decidir(["repo", "clonar"], home).verbo == "repo clonar"
    assert g.decidir(["repo", "estado"], home).verbo == "repo estado"
    assert g.decidir(["registro"], home).extra == (50,)
    assert g.decidir(["registro", "200"], home).extra == (200,)
    assert g.decidir(["parar", "4321"], home).extra == (4321,)
    assert g.decidir(["info", "temperatura"], home).verbo == "info temperatura"


@pytest.mark.parametrize("consulta", sorted(g.CONSULTAS))
def test_decidir_info_consultas_fijas(home: Path, consulta: str) -> None:
    o = g.decidir(["info", consulta], home)
    assert o.argv == g.CONSULTAS[consulta]
    assert o.argv[0] not in ("sh", "bash", "sudo")
    assert (o.tope_s, o.pesada, o.entrada, o.cwd) == (10.0, False, False, "")
    with pytest.raises(g.Negado, match="uso"):
        g.decidir(["info", consulta, "extra"], home)


def test_decidir_info_v4l2_camara_y_puerto(home: Path) -> None:
    nombre = "platform-3610000.usb-usb-0:2.1:1.0-video-index0"
    o = g.decidir(["info", "v4l2", nombre], home)
    assert o.argv == ["v4l2-ctl", "-d", "/dev/v4l/by-path/" + nombre, "--info", "--list-formats-ext",
                      "--list-ctrls-menus"]
    assert not any(a.startswith("--set-") or a.startswith("--stream") for a in o.argv)
    assert g.decidir(["info", "camara-libre", nombre], home).argv == ["fuser", "-v", "/dev/v4l/by-path/" + nombre]
    assert g.decidir(["info", "puerto-libre", "18946"], home).argv == ["ss", "-ltn", "sport = :18946"]
    for malo in ("../../dev/sda", "/dev/video0", "video0", "platform-x-usb-0:2.1:1.0-video-index0/../x"):
        with pytest.raises(g.Negado):
            g.decidir(["info", "v4l2", malo], home)
    for puerto in ("22", "18943", "18951", "abc"):
        with pytest.raises(g.Negado):
            g.decidir(["info", "puerto-libre", puerto], home)


def test_decidir_repo_actualizar_es_ff_only(home: Path) -> None:
    o = g.decidir(["repo", "actualizar"], home)
    assert o.argv == ["git", "-C", str(g.ruta_repo(home)), "pull", "--ff-only"]
    assert not o.pesada


def test_decidir_entorno_instalar(home: Path) -> None:
    o = g.decidir(["entorno", "instalar", "wip", "--gtsam"], home)
    arbol = g.ruta_arbol(home, "wip")
    assert o.argv == ["bash", str(arbol / "linux" / "instalar_entorno.sh"), "--gtsam"]
    assert (o.cwd, o.tope_s, o.pesada) == (str(arbol), 1800.0, True)
    assert g.decidir(["entorno", "instalar", "repo"], home).argv[-1].endswith("instalar_entorno.sh")
    for malo in (["entorno"], ["entorno", "instalar"], ["entorno", "instalar", "otro"],
                 ["entorno", "instalar", "wip", "--sudo"], ["entorno", "borrar", "wip"]):
        with pytest.raises(g.Negado):
            g.decidir(malo, home)


def test_decidir_suite(home: Path) -> None:
    py = str(g.ruta_python(home))
    o = g.decidir(["suite", "wip", "-q"], home)
    assert o.argv == [py, "-m", "pytest", "tests", "-q"]
    assert (o.cwd, o.tope_s, o.pesada, o.entrada) == (str(g.ruta_arbol(home, "wip")), 900.0, True, True)
    o = g.decidir(["suite", "repo", "-k", "guardian and not tope", "tests/test_guardian.py"], home)
    assert o.argv == [py, "-m", "pytest", "tests/test_guardian.py", "-k", "guardian and not tope"]
    for malo in (["suite"], ["suite", "otro"], ["suite", "wip", "--pdb"], ["suite", "wip", "tests/../x"],
                 ["suite", "wip", "/etc"], ["suite", "wip", "-k", "a;b"], ["suite", "wip", "-k"]):
        with pytest.raises(g.Negado):
            g.decidir(malo, home)


@pytest.mark.parametrize("modulo", sorted(g.MODULOS))
def test_decidir_py_cada_modulo(home: Path, modulo: str) -> None:
    o = g.decidir(["py", "repo", modulo], home)
    assert o.argv == [str(g.ruta_python(home)), "-u", "-m", modulo]
    assert o.tope_s == g.MODULOS[modulo]
    assert o.pesada == (modulo in g.MODULOS_PESADOS)
    assert o.entrada is True
    assert o.cwd == str(g.ruta_arbol(home, "repo"))


def test_decidir_py_tracker_como_lo_lanza_el_panel(home: Path) -> None:
    o = g.decidir(["py", "repo", "tracker", "--config", "profiles/tracker_config_gs1.yaml", "--no-window",
                   "--stop-stdin", "--igtl-iface", "wlP1p1s0"], home)
    assert o.argv[4:] == ["--config", "profiles/tracker_config_gs1.yaml", "--no-window", "--stop-stdin",
                          "--igtl-iface", "wlP1p1s0"]
    assert o.tope_s == 7200.0 and o.pesada


def test_decidir_py_rutas_de_salida_solo_en_nav_salidas(home: Path) -> None:
    salidas = g.ruta_salidas(home)
    o = g.decidir(["py", "wip", "tracker", "--record", "~/nav-salidas/gs1.npz"], home)
    assert o.argv[-2:] == ["--record", str((salidas / "gs1.npz").resolve())]
    o = g.decidir(["py", "wip", "tracker", f"--record={salidas}/gs1.npz"], home)
    assert o.argv[-2:] == ["--record", str((salidas / "gs1.npz").resolve())]
    o = g.decidir(["py", "wip", "linux.perfil_temporal", "--salida", "~/nav-salidas/perfiles/gs2.yaml"], home)
    assert o.argv[-1] == str((salidas / "perfiles" / "gs2.yaml").resolve())
    for malos in (["--record", "/etc/x"], ["--record", "gs1.npz"], ["--record", "../x.npz"],
                  ["--output", "~/x.npz"], ["--salida", "/tmp/x"], ["--record"], ["--record", "~otro/x"]):
        with pytest.raises(g.Negado):
            g.decidir(["py", "wip", "tracker", *malos], home)


def test_decidir_py_rutas_de_entrada_dentro_del_arbol_o_salidas(home: Path) -> None:
    arbol = g.ruta_arbol(home, "wip")
    (arbol / "profiles").mkdir()
    o = g.decidir(["py", "wip", "diagnostics.igtl_rate", "listen", "--host", "127.0.0.1", "--log",
                   "~/nav-salidas/igtl.csv"], home)
    assert o.argv[-1] == str((g.ruta_salidas(home) / "igtl.csv").resolve())
    for malo in (["--config", "/etc/passwd"], ["--config", "../otro/x.yaml"], ["--x", ".."],
                 ["--config", str(home / "x.yaml")],
                 # `--opcion=valor`: el valor tambien se comprueba (hallazgo de «verifica»)
                 ["--config=/etc/passwd"], ["--config=/dev/sda"], ["--device=../../x"], ["-c=~otro/x"]):
        with pytest.raises(g.Negado):
            g.decidir(["py", "wip", "tracker", *malo], home)
    o = g.decidir(["py", "wip", "tracker", "--config=profiles/tracker_config_gs1.yaml"], home)
    assert o.argv[-1] == "--config=profiles/tracker_config_gs1.yaml"


def test_decidir_camara_rafaga(home: Path) -> None:
    nombre = "platform-3610000.usb-usb-0:2.2:1.0-video-index0"
    o = g.decidir(["camara", "rafaga", nombre, "900"], home)
    assert o.argv[:3] == ["v4l2-ctl", "-d", "/dev/v4l/by-path/" + nombre]
    assert "--set-fmt-video=width=1280,height=960,pixelformat=MJPG" in o.argv
    assert "--stream-count=900" in o.argv and "--stream-mmap" in o.argv
    assert (o.tope_s, o.pesada) == (60.0, True)
    for malo in (["camara", "rafaga", nombre, "1801"], ["camara", "rafaga", nombre, "0"],
                 ["camara", "rafaga", nombre], ["camara", "abrir", nombre, "10"],
                 ["camara", "rafaga", "/dev/video0", "10"]):
        with pytest.raises(g.Negado):
            g.decidir(malo, home)


def test_decidir_medir_tegrastats(home: Path) -> None:
    o = g.decidir(["medir", "tegrastats", "300"], home)
    assert o.argv == ["tegrastats", "--interval", "1000"]
    assert (o.tope_s, o.pesada, o.corte_esperado) == (300.0, True, True)
    assert Path(o.salida).parent == g.ruta_salidas(home) and Path(o.salida).name.startswith("tegrastats_")
    for malo in (["medir", "tegrastats", "901"], ["medir", "tegrastats"], ["medir", "cpu", "10"]):
        with pytest.raises(g.Negado):
            g.decidir(malo, home)


def test_decidir_traer_procesos_prueba_tope(home: Path) -> None:
    salidas = g.ruta_salidas(home)
    o = g.decidir(["traer", "~/nav-salidas/a/b.txt"], home)
    assert o.extra == (str((salidas / "a" / "b.txt").resolve()),)
    assert g.decidir(["traer", "a/b.txt"], home).extra == o.extra
    o = g.decidir(["procesos"], home)
    assert o.argv[:3] == ["ps", "-u", g.CUENTA]
    o = g.decidir(["prueba-tope"], home)
    assert (o.argv, o.tope_s, o.pesada) == (["sleep", "30"], 3.0, False)


# ---------------------------------------------------------------- decidir: lo prohibido

PROHIBIDAS = [
    # una por cada linea de «Lo prohibido» del plan, mas los casos 1-16 de probar_barrera.ps1
    [], ["sudo", "true"], ["su"], ["pkexec", "id"],
    ["apt", "install", "x"], ["apt-get", "install", "x"], ["dpkg", "-i", "x.deb"], ["snap", "install", "x"],
    ["pip", "install", "x"], ["python3", "-m", "pip", "install", "x"],
    ["reboot"], ["shutdown", "now"], ["poweroff"], ["systemctl", "stop", "ollama"], ["systemctl", "restart", "ssh"],
    ["nvpmodel", "-m", "0"], ["nvpmodel", "-q"], ["jetson_clocks"],
    ["nvbootctrl", "dump-slots-info"], ["efibootmgr"], ["fwupdmgr", "update"], ["flash.sh"],
    ["cat", "/boot/extlinux/extlinux.conf"], ["ls", "/boot/efi"],
    ["fdisk", "-l"], ["parted", "-l"], ["mkfs.ext4", "/dev/sda"], ["dd", "if=/dev/zero", "of=/dev/nvme0n1"],
    ["mount", "/dev/sda1", "/mnt"], ["ls", "/dev/nvme0n1"], ["ls", "/dev/mmcblk0"],
    ["systemctl", "--user", "start", "x"], ["loginctl", "enable-linger"],
    ["docker", "ps"], ["ollama", "list"], ["ollama", "run", "x"], ["crontab", "-l"], ["at", "now"],
    ["ssh", "otro"], ["scp", "x", "otro:"], ["touch", "/etc/x"], ["bash", "-c", "id"], ["sh"], ["python3"],
    ["git", "push"], ["git", "commit", "-m", "x"], ["repo", "push"], ["repo", "commit"],
    ["py", "wip", "os"], ["py", "wip", "subprocess"], ["py", "repo", "pip", "install", "x"],
    ["py", "wip", "tracker", "--record", "/etc/x"], ["traer", "../../etc/passwd"], ["traer", "/etc/passwd"],
    ["info", "red;", "id"], ["info"], ["info", "shell"], ["wip", "borrar"], ["registro", "201"],
    ["registro", "0"], ["parar", "1"], ["parar", "abc"], ["ayuda", "extra"], ["prueba-tope", "60"],
    ["AYUDA"], ["Info", "red"],
]


@pytest.mark.parametrize("argv", PROHIBIDAS, ids=[" ".join(a) or "(vacio)" for a in PROHIBIDAS])
def test_decidir_niega_lo_prohibido(home: Path, argv: list) -> None:
    with pytest.raises(g.Negado):
        g.decidir(argv, home)


def test_ningun_argv_permitido_invoca_un_shell(home: Path) -> None:
    permitidos = [["info", c] for c in g.CONSULTAS] + [["repo", "actualizar"], ["procesos"], ["prueba-tope"],
                                                        ["suite", "wip"], ["entorno", "instalar", "wip"],
                                                        ["camara", "rafaga", "platform-3610000.usb-usb-0:2.1:1.0-video-index0", "10"],
                                                        ["medir", "tegrastats", "10"]] + \
        [["py", "wip", m] for m in g.MODULOS]
    for argv in permitidos:
        o = g.decidir(argv, home)
        if o.argv:
            assert Path(o.argv[0]).name not in ("sh", "dash", "zsh", "sudo", "su", "env"), argv
            if o.argv[0] == "bash":
                assert o.argv[1].endswith("instalar_entorno.sh") and "-c" not in o.argv, argv


# ---------------------------------------------------------------- precondiciones

def _orden_pesada(home: Path) -> g.Orden:
    return g.decidir(["suite", "wip", "-q"], home)


def test_precondiciones_pasan_con_todo_en_orden(home: Path) -> None:
    g.precondiciones(_orden_pesada(home), home, leer_temp=lambda: 60.0, libre_gb=lambda: 19.0, pesadas=lambda: 2)
    g.precondiciones(g.decidir(["ayuda"], home), home)


def test_precondiciones_niegan_disco_temperatura_y_pesadas(home: Path) -> None:
    o = _orden_pesada(home)
    with pytest.raises(g.Negado, match="GB libres"):
        g.precondiciones(o, home, leer_temp=lambda: 60.0, libre_gb=lambda: 4.9, pesadas=lambda: 0)
    with pytest.raises(g.Negado, match="temperatura"):
        g.precondiciones(o, home, leer_temp=lambda: 85.5, libre_gb=lambda: 19.0, pesadas=lambda: 0)
    with pytest.raises(g.Negado, match="pesadas"):
        g.precondiciones(o, home, leer_temp=lambda: 60.0, libre_gb=lambda: 19.0, pesadas=lambda: 3)
    # sin temperatura legible no se niega por temperatura
    g.precondiciones(o, home, leer_temp=lambda: None, libre_gb=lambda: 19.0, pesadas=lambda: 0)
    # una orden ligera no mira nada de eso
    g.precondiciones(g.decidir(["info", "red"], home), home, leer_temp=lambda: 99.0, libre_gb=lambda: 0.1,
                     pesadas=lambda: 9)


def test_precondiciones_exigen_arbol_venv_y_clon(home: Path) -> None:
    shutil.rmtree(g.ruta_arbol(home, "wip"))
    with pytest.raises(g.Negado, match="no existe el arbol"):
        g.precondiciones(g.decidir(["suite", "wip"], home), home, leer_temp=lambda: 1.0, libre_gb=lambda: 99.0,
                         pesadas=lambda: 0)
    g.ruta_python(home).unlink()
    with pytest.raises(g.Negado, match="venv"):
        g.precondiciones(g.decidir(["suite", "repo"], home), home, leer_temp=lambda: 1.0, libre_gb=lambda: 99.0,
                         pesadas=lambda: 0)
    with pytest.raises(g.Negado, match="ya existe el clon"):
        g.precondiciones(g.decidir(["repo", "clonar"], home), home)
    shutil.rmtree(g.ruta_repo(home))
    with pytest.raises(g.Negado, match="no hay clon"):
        g.precondiciones(g.decidir(["repo", "estado"], home), home)
    g.precondiciones(g.decidir(["repo", "clonar"], home), home)


def test_pesadas_en_marcha_cuenta_solo_vivas(home: Path, monkeypatch) -> None:
    carpeta = g.ruta_activas(home)
    carpeta.mkdir(parents=True)
    (carpeta / "11.json").write_text(json.dumps({"pid": 11, "pesada": True}), encoding="utf-8")
    (carpeta / "12.json").write_text(json.dumps({"pid": 12, "pesada": False}), encoding="utf-8")
    (carpeta / "13.json").write_text(json.dumps({"pid": 13, "pesada": True}), encoding="utf-8")
    monkeypatch.setattr(g, "_pid_vivo", lambda pid: pid != 13)
    assert g.pesadas_en_marcha(home) == 1
    assert not (carpeta / "13.json").exists()          # la muerta se limpia


# ---------------------------------------------------------------- entorno limpio

def test_entorno_limpio_sin_ld_ni_pythonpath(home: Path) -> None:
    env = g.entorno_limpio(home, g.ruta_python(home).parent.parent)
    assert not any(k.startswith("LD_") for k in env)
    assert "PYTHONPATH" not in env and "PYTHONSTARTUP" not in env
    assert env["PATH"] == f"{g.ruta_python(home).parent}:/usr/bin:/bin"
    assert env["HOME"] == str(home) and env["LANG"] == "C.UTF-8" and env["PYTHONNOUSERSITE"] == "1"
    assert g.entorno_limpio(home)["PATH"] == "/usr/bin:/bin"


# ---------------------------------------------------------------- recibir_wip

@pytest.fixture
def tars() -> dict:
    return tars_malos.fabricar_bytes()


@pytest.mark.parametrize("nombre, motivo", [("padre", r"\.\."), ("absoluta", "absoluta"), ("enlace", "enlace"),
                                            ("nrrd", "paciente"), ("dcm", "paciente"), ("fuera", "fuera de codigo/")])
def test_recibir_wip_niega_cada_tar_malo_sin_extraer(home: Path, tars: dict, nombre: str, motivo: str) -> None:
    antes = sorted(p.relative_to(home) for p in home.rglob("*"))
    with pytest.raises(g.Negado, match=motivo):
        g.recibir_wip(io.BytesIO(tars[nombre]), home)
    assert sorted(p.relative_to(home) for p in home.rglob("*")) == antes, "extrajo o creo algo"
    assert not (g.ruta_wip(home) / "ESTADO.json").exists()


def test_recibir_wip_niega_mas_de_50_mb_sin_leerlo_entero(home: Path) -> None:
    class Fuente(io.RawIOBase):
        def __init__(self):
            self.pedidos = 0

        def readable(self):
            return True

        def read(self, n=-1):
            self.pedidos += 1
            return b"\0" * (n if n > 0 else 0)

    fuente = Fuente()
    with pytest.raises(g.Negado, match="50 MB"):
        g.recibir_wip(fuente, home)
    assert fuente.pedidos == 1
    assert not (g.ruta_wip(home) / "ESTADO.json").exists()
    with pytest.raises(g.Negado, match="no llego nada"):
        g.recibir_wip(io.BytesIO(b""), home)
    with pytest.raises(g.Negado, match="no es un tar"):
        g.recibir_wip(io.BytesIO(b"esto no es un tar" * 100), home)


def test_recibir_wip_exige_data_filter(home: Path, tars: dict, monkeypatch) -> None:
    monkeypatch.delattr(tarfile, "data_filter")
    with pytest.raises(g.Negado, match="data_filter"):
        g.recibir_wip(io.BytesIO(tars["bueno"]), home)


def test_recibir_wip_acepta_el_bueno_y_rota_el_anterior(home: Path, tars: dict) -> None:
    wip = g.ruta_wip(home)
    (wip / "codigo" / "viejo.txt").write_text("viejo\n", encoding="utf-8")
    import hashlib
    sha = g.recibir_wip(io.BytesIO(tars["bueno"]), home)
    assert sha == hashlib.sha256(tars["bueno"]).hexdigest()
    assert (wip / "codigo" / "linux" / "__init__.py").is_file()
    assert (wip / "codigo" / "readme.md").read_text(encoding="utf-8") == "copia WIP de prueba\n"
    assert not (wip / "codigo" / "viejo.txt").exists()
    assert (wip / "codigo.anterior" / "viejo.txt").is_file()
    estado = json.loads((wip / "ESTADO.json").read_text(encoding="utf-8"))
    assert estado["sha256"] == sha and estado["bytes"] == len(tars["bueno"]) and estado["miembros"] == 4
    assert not list(wip.glob(".nuevo-*"))
    # otra vez: el anterior se sustituye y no se acumulan copias
    g.recibir_wip(io.BytesIO(tars["bueno"]), home)
    assert sorted(p.name for p in wip.iterdir()) == ["ESTADO.json", "codigo", "codigo.anterior"]


def test_tars_malos_por_cli_escribe_los_siete(tmp_path: Path) -> None:
    assert tars_malos.main(["--destino", str(tmp_path / "t")]) == 0
    nombres = sorted(p.name for p in (tmp_path / "t").glob("*.tar"))
    assert nombres == ["absoluta.tar", "bueno.tar", "dcm.tar", "enlace.tar", "fuera.tar", "nrrd.tar", "padre.tar"]
    with tarfile.open(tmp_path / "t" / "enlace.tar") as t:
        assert any(m.issym() for m in t.getmembers())
    assert not list((tmp_path / "t").rglob("*.nrrd"))          # el .nrrd es solo un nombre dentro del tar


# ---------------------------------------------------------------- ejecutar (internas) y main

@pytest.fixture
def registro(home: Path) -> g.Registro:
    return g.Registro(g.ruta_registro(home), logger=False)


def test_ejecutar_internas_ayuda_registro_traer_y_wip_estado(home: Path, registro: g.Registro) -> None:
    salida = io.BytesIO()
    assert g.ejecutar(g.decidir(["ayuda"], home), registro, io.BytesIO(), salida) == 0
    assert "prueba-tope" in salida.getvalue().decode()
    for i in range(3):
        registro.escribir({"n": i})
    salida = io.BytesIO()
    assert g.ejecutar(g.decidir(["registro", "2"], home), registro, io.BytesIO(), salida) == 0
    assert salida.getvalue().decode().splitlines() == ['{"n": 1}', '{"n": 2}']
    (g.ruta_salidas(home) / "a").mkdir()
    (g.ruta_salidas(home) / "a" / "b.bin").write_bytes(b"\x00\x01datos")
    salida = io.BytesIO()
    assert g.ejecutar(g.decidir(["traer", "a/b.bin"], home), registro, io.BytesIO(), salida) == 0
    assert salida.getvalue() == b"\x00\x01datos"
    with pytest.raises(g.Negado, match="no existe"):
        g.ejecutar(g.decidir(["traer", "a/no.bin"], home), registro, io.BytesIO(), io.BytesIO())
    salida = io.BytesIO()
    assert g.ejecutar(g.decidir(["wip", "estado"], home), registro, io.BytesIO(), salida) == 0
    assert salida.getvalue() == b"sin copia WIP\n"


def test_ejecutar_parar_solo_lo_lanzado_por_el_guardian(home: Path, registro: g.Registro) -> None:
    with pytest.raises(g.Negado, match="no lo lanzo el guardian"):
        g.ejecutar(g.decidir(["parar", "4321"], home), registro, io.BytesIO(), io.BytesIO())


def _main(monkeypatch, home: Path, orden: str, cuenta: str = g.CUENTA, pty: bool = False) -> tuple:
    monkeypatch.setattr(g, "_cuenta_actual", lambda: cuenta)
    monkeypatch.setattr(g, "_hay_pty", lambda: pty)
    monkeypatch.setattr(sys, "argv", ["guardian"])
    monkeypatch.setattr(g.shutil, "which", lambda nombre: None)      # sin `logger` en el PC
    entorno = {"HOME": str(home), "SSH_CONNECTION": "192.0.2.10 55555 192.0.2.20 22"}
    if orden is not None:
        entorno["SSH_ORIGINAL_COMMAND"] = orden
    rc = g.main(entorno)
    lineas = [json.loads(l) for l in g.ruta_registro(home).read_text(encoding="utf-8").splitlines()]
    return rc, lineas[-1]


def test_main_niega_y_registra_cada_intento(home: Path, monkeypatch, capsys) -> None:
    rc, ev = _main(monkeypatch, home, None)
    assert rc == 126 and ev["permitido"] is False and "sin orden" in ev["motivo"] and ev["ip"] == "192.0.2.10"
    rc, ev = _main(monkeypatch, home, "sudo true")
    assert rc == 126 and ev["codigo"] == 126 and ev["orden"] == "sudo true" and "verbo desconocido" in ev["motivo"]
    assert "NEGADO" in capsys.readouterr().err
    rc, ev = _main(monkeypatch, home, "ayuda", cuenta="jetson")
    assert rc == 126 and "la cuenta es 'jetson'" in ev["motivo"]
    rc, ev = _main(monkeypatch, home, "ayuda", pty=True)
    assert rc == 126 and "pty" in ev["motivo"]
    rc, ev = _main(monkeypatch, home, "traer a/no.bin")
    assert rc == 126 and "no existe" in ev["motivo"] and ev["permitido"] is False


def test_main_permite_una_interna_y_la_registra(home: Path, monkeypatch, capsys) -> None:
    rc, ev = _main(monkeypatch, home, "ayuda")
    assert rc == 0
    assert ev["permitido"] is True and ev["codigo"] == 0 and ev["verbo"] == "ayuda" and ev["tope"] is False
    assert ev["duracion_s"] >= 0 and ev["pid"] == os.getpid()
    assert "ssh nav-jetson <verbo>" in capsys.readouterr().out
    assert g.ruta_salidas(home).is_dir() and g.ruta_activas(home).is_dir()


def test_main_autocomprobar(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["guardian", "--autocomprobar"])
    assert g.main({}) == 0
    assert f"nav-guardian {g.VERSION}" in capsys.readouterr().out


# ---------------------------------------------------------------- _parar_grupo, con un killpg falso

class _GrupoFalso:
    """Un grupo cuyo lider muere con el SIGTERM y queda zombi hasta que alguien lo recoge (`poll`).
    Como en Linux: mientras el zombi no se recoja, killpg(pgid, 0) da exito. `terco` es otro del
    grupo que ignora el SIGTERM y solo cae con el SIGKILL."""

    def __init__(self, terco: bool = False) -> None:
        self.muerto = False
        self.recogido = False
        self.terco = terco
        self.senales = []

    def poll(self):
        if self.muerto:
            self.recogido = True
            return -15
        return None

    def killpg(self, pgid: int, senal: int) -> None:
        self.senales.append(senal)
        if senal == signal.SIGTERM:
            self.muerto = True
        elif senal == 0:
            if self.recogido and not self.terco:
                raise ProcessLookupError(pgid)
        else:
            self.terco = False
            self.muerto = True


SIGKILL = getattr(signal, "SIGKILL", 9)


def test_parar_grupo_recoge_al_lider_y_no_espera_la_gracia() -> None:
    """P-2, caso 24: prueba-tope duro 8 s con un tope de 3. El lider (sleep) moria con el SIGTERM pero
    quedaba zombi sin recoger, killpg(pgid, 0) seguia dando exito y se esperaban los 5 s de gracia."""
    grupo = _GrupoFalso()
    t0 = time.monotonic()
    g._parar_grupo(4242, 5.0, proceso=grupo, killpg=grupo.killpg)
    assert time.monotonic() - t0 < 1.0
    assert grupo.recogido and SIGKILL not in grupo.senales


def test_parar_grupo_sin_recoger_al_lider_espera_la_gracia_entera() -> None:
    """La hipotesis del caso 24, reproducida: sin `proceso`, el zombi hace esperar toda la gracia."""
    grupo = _GrupoFalso()
    t0 = time.monotonic()
    g._parar_grupo(4242, 0.4, killpg=grupo.killpg)
    assert time.monotonic() - t0 >= 0.4
    assert grupo.senales[-1] == SIGKILL


def test_parar_grupo_sigue_mandando_sigkill_a_los_que_quedan() -> None:
    grupo = _GrupoFalso(terco=True)
    t0 = time.monotonic()
    g._parar_grupo(4242, 0.4, proceso=grupo, killpg=grupo.killpg)
    assert time.monotonic() - t0 >= 0.4
    assert grupo.recogido and grupo.senales[0] == signal.SIGTERM and grupo.senales[-1] == SIGKILL


# ---------------------------------------------------------------- solo Linux (en la Jetson, fase 4)

@pytest.mark.skipif(not EN_LINUX, reason="solo Linux: grupo de procesos, setsid y killpg")
def test_parar_grupo_de_verdad_no_espera_la_gracia() -> None:
    p = subprocess.Popen(["sleep", "30"], start_new_session=True)
    t0 = time.monotonic()
    g._parar_grupo(p.pid, 5.0, proceso=p)
    assert time.monotonic() - t0 < 1.5
    assert p.wait(timeout=5) == -signal.SIGTERM


@pytest.mark.skipif(not EN_LINUX, reason="solo Linux: grupo de procesos, setsid y killpg")
def test_externa_tope_de_prueba_tope_corta_sin_gracia(home: Path, registro: g.Registro) -> None:
    """Como el caso 24 del P-2, con un tope de 1 s: antes del arreglo duraba 1 + 5 s."""
    o = g.Orden("prueba", ["sleep", "30"], "", 1.0, False, False, str(home))
    t0 = time.monotonic()
    rc = g.ejecutar(o, registro, io.BytesIO(), io.BytesIO())
    assert rc == g.CODIGO_TOPE and time.monotonic() - t0 < 2.5


@pytest.mark.skipif(not EN_LINUX, reason="solo Linux: grupo de procesos, setsid y killpg")
def test_externa_tope_para_el_grupo(home: Path, registro: g.Registro) -> None:
    import time
    o = g.Orden("prueba", ["sh", "-c", "sleep 30 & sleep 30"], "", 1.0, False, False, str(home))
    t0 = time.monotonic()
    rc = g.ejecutar(o, registro, io.BytesIO(), io.BytesIO())
    assert rc == g.CODIGO_TOPE and time.monotonic() - t0 < 8
    assert not list(g.ruta_activas(home).glob("*.json"))


@pytest.mark.skipif(not EN_LINUX, reason="solo Linux: limites del hijo")
def test_externa_limites_y_entorno(home: Path, registro: g.Registro) -> None:
    salida = io.BytesIO()
    o = g.Orden("prueba", ["/usr/bin/python3", "-I", "-c",
                           "import os, resource; print(resource.getrlimit(resource.RLIMIT_CORE)); "
                           "print(sorted(k for k in os.environ if k.startswith('LD_') or k == 'PYTHONPATH'))"],
                "", 10.0, False, False, str(home))
    assert g.ejecutar(o, registro, io.BytesIO(), salida) == 0
    assert salida.getvalue().decode().splitlines() == ["(0, 0)", "[]"]


# ---------------------------------------------------------------- los scripts del autor

INSTALAR = LINUX_DIR / "instalar_guardian.sh"
DESINSTALAR = LINUX_DIR / "desinstalar_guardian.sh"
DROPIN = """Match User navagente
    AuthorizedKeysFile /etc/ssh/authorized_keys/%u
    ForceCommand /usr/local/lib/nav-guardian/guardian
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    DisableForwarding yes
    PermitTTY no
    PermitUserRC no
    PermitTunnel no
    AllowAgentForwarding no
    ClientAliveInterval 5
    ClientAliveCountMax 3
Match all
"""


@pytest.mark.parametrize("script", [INSTALAR, DESINSTALAR, LINUX_DIR / "guardian.py", LINUX_DIR / "sonda_privilegios.py"])
def test_los_scripts_de_la_jetson_son_ascii_y_lf(script: Path) -> None:
    datos = script.read_bytes()
    assert datos and b"\r" not in datos, f"{script.name} con CR"
    assert all(b < 128 for b in datos), f"{script.name} con bytes que no son ASCII"
    if script.suffix == ".sh":
        assert datos.startswith(b"#!/usr/bin/env bash\n")
    if script.name == "guardian.py":
        assert datos.startswith(b"#!/usr/bin/python3 -I\n")   # el instalador lo copia tal cual, 0755


def test_el_instalador_escribe_el_dropin_exacto_y_comprueba_antes_de_recargar() -> None:
    texto = INSTALAR.read_text(encoding="ascii")
    assert DROPIN in texto
    # el orden de las ordenes (no de los comentarios): sshd -T antes, la cuenta, sshd -t, el diff y el reload
    assert texto.index("\nsshd -T -C") < texto.index("hacer adduser") < texto.index("if ! sshd -t") \
        < texto.index("if ! diff ") < texto.index("hacer systemctl reload ssh")
    assert texto.count("hacer systemctl reload ssh") == 1
    assert 'restrict,from="$DESDE"' in texto
    assert "set -euo pipefail" in texto
    # los grupos suplementarios, exactamente video (P-2: adduser con ADD_EXTRA_GROUPS), comprobados
    # antes de instalar la clave y el drop-in, y otra vez en el resumen
    assert "GRUPO_SUPLEMENTARIO=video\n" in texto
    assert 'hacer usermod -G "$GRUPO_SUPLEMENTARIO" "$CUENTA"' in texto
    assert "usermod -aG" not in texto and "GRUPOS_PROHIBIDOS" not in texto
    assert texto.index("hacer adduser") < texto.index("hacer usermod -G") \
        < texto.index('grupos_exactos "$CUENTA" ||') < texto.index('escribir "$CLAVE_DESTINO"')
    assert texto.count('grupos_exactos "$CUENTA" ||') == 2
    assert "cron.deny" in texto and "at.deny" in texto and "disable-linger" in texto
    assert "chmod 0750" in texto
    assert "0755" in texto.split("install -o root -g root -m")[1].split("\n")[0]
    assert "rm -f \"$DROPIN\"" in texto                     # al fallar sshd -t o la comparacion
    assert "systemctl restart" not in texto and "reboot" not in texto.lower().replace("# ", "")


def test_el_desinstalador_recarga_tras_sshd_t_y_solo_borra_la_cuenta_con_la_opcion() -> None:
    texto = DESINSTALAR.read_text(encoding="ascii")
    assert texto.index("sshd -t") < texto.index("systemctl reload ssh")
    assert "--borrar-cuenta" in texto and 'if [ "$BORRAR_CUENTA" -eq 1 ]' in texto
    assert texto.index("deluser --remove-home") > texto.index('if [ "$BORRAR_CUENTA" -eq 1 ]')
    assert "set -euo pipefail" in texto


def _bash() -> str | None:
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files"):
            candidato = Path(base) / "Git" / "usr" / "bin" / "bash.exe"
            if candidato.is_file():
                return str(candidato)
        return None
    return shutil.which("bash")


@pytest.mark.parametrize("script", [INSTALAR, DESINSTALAR])
def test_los_scripts_del_autor_compilan_y_paran_antes_de_root(script: Path, tmp_path: Path) -> None:
    bash = _bash()
    if bash is None:
        pytest.skip("sin bash de Git for Windows ni de Linux")
    entorno = {"PATH": str(Path(bash).parent), "HOME": str(tmp_path)}
    if sys.platform == "win32":
        entorno["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    r = subprocess.run([bash, "-n", str(script)], capture_output=True, timeout=30, env=entorno)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([bash, str(script), "--ayuda"], capture_output=True, timeout=30, env=entorno)
    assert r.returncode == 0 and b"sudo bash" in r.stdout, r.stdout + r.stderr
    r = subprocess.run([bash, str(script), "--loquesea"], capture_output=True, timeout=30, env=entorno)
    assert r.returncode == 2 and b"desconocido" in r.stderr
    if script == INSTALAR:
        r = subprocess.run([bash, str(script)], capture_output=True, timeout=30, env=entorno)
        assert r.returncode == 2 and b"falta --clave" in r.stderr
        r = subprocess.run([bash, str(script), "--clave", "k.pub", "--desde", "10.0.0.0/8", "--autor", "x",
                            "--pc", "10.0.0.2"], capture_output=True, timeout=30, env=entorno)
        assert r.returncode == 1 and b"sudo" in r.stderr                 # para en el id -u, sin tocar nada
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("grupos, codigo, texto", [
    ("navagente video", 0, "grupos de navagente: exactamente {navagente, video}"),
    ("video navagente", 0, "exactamente {navagente, video}"),
    # lo que dejo el adduser de la Jetson Yahboom en el P-2 (2026-11-02)
    ("navagente adm audio gdm gpio i2c render video weston-launch", 1,
     "sobran: adm audio gdm gpio i2c render weston-launch; faltan: ninguno"),
    ("navagente sudo video", 1, "sobran: sudo; faltan: ninguno"),
    ("navagente", 1, "sobran: ninguno; faltan: video"),
    ("", 1, "sobran: ninguno; faltan: navagente video"),
])
def test_el_instalador_exige_los_grupos_exactos(grupos: str, codigo: int, texto: str) -> None:
    """La funcion `grupos_exactos` del instalador, sacada tal cual y corrida con un `id` falso."""
    bash = _bash()
    if bash is None:
        pytest.skip("sin bash de Git for Windows ni de Linux")
    fuente = INSTALAR.read_text(encoding="ascii")
    inicio = fuente.index("grupos_exactos() {")
    funcion = fuente[inicio:fuente.index("\n}\n", inicio) + 3]
    guion = ("set -euo pipefail\nGRUPO_SUPLEMENTARIO=video\n" + funcion
             + 'id() { echo "$GRUPOS_FALSOS"; }\ngrupos_exactos navagente\n')
    entorno = {"PATH": str(Path(bash).parent), "GRUPOS_FALSOS": grupos}
    if sys.platform == "win32":
        entorno["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    r = subprocess.run([bash, "-c", guion], capture_output=True, timeout=30, env=entorno)
    salida = r.stdout.decode("ascii").strip()
    assert r.returncode == codigo, salida + r.stderr.decode("ascii", errors="replace")
    assert texto in salida, salida


def test_el_guardian_no_importa_nada_fuera_de_la_biblioteca_estandar() -> None:
    texto = (LINUX_DIR / "guardian.py").read_text(encoding="ascii")
    importados = set(re.findall(r"^(?:import|from) ([A-Za-z_][\w.]*)", texto, re.M))
    importados |= set(re.findall(r"^\s+import ([A-Za-z_]\w*)$", texto, re.M))
    permitidos = {"datetime", "hashlib", "io", "json", "os", "re", "shlex", "shutil", "signal", "subprocess",
                  "sys", "tarfile", "time", "dataclasses", "pathlib", "pwd", "resource", "__future__"}
    assert importados <= permitidos, importados - permitidos
    assert "removeprefix" not in texto and "is_relative_to" not in texto     # son de Python 3.9
