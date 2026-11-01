"""La sonda de privilegios (meta 007, fase 2): sin Jetson, con las ordenes y los accesos falsos.

Comprueba que cada comprobacion da `pasa` con una cuenta sin privilegios y lo pierde con una que
los tenga, que el `touch` en /etc que si se crea se borra y se marca como fallo, que son >= 15
comprobaciones y que `main` sale con 0 solo si no encuentra ningun privilegio.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from linux import sonda_privilegios as s

from .conftest import CODIGO_DIR

SIN_PRIVILEGIOS = {
    ("sudo", "-n", "true"): (1, "sudo: a password is required"),
    ("crontab", "-l"): (1, "You (navagente) are not allowed to use this program (crontab)"),
    ("loginctl", "show-user", "navagente", "-p", "Linger"): (1, "Failed to get user: User ID 1001 is not logged in or lingering"),
    ("systemctl", "--no-ask-password", "restart", "nav-sonda-inexistente.service"): (
        1, "Failed to restart nav-sonda-inexistente.service: Interactive authentication required."),
    ("docker", "ps"): (1, "permission denied while trying to connect to the Docker daemon socket"),
}
GRUPOS_LIMPIOS = ["navagente", "video"]


def _ejecutar_falso(respuestas: dict):
    llamadas = []

    def ejecutar(argv: list) -> tuple:
        llamadas.append(list(argv))
        return respuestas.get(tuple(argv), (127, "no existe el programa"))

    ejecutar.llamadas = llamadas
    return ejecutar


@pytest.fixture
def etc(tmp_path: Path) -> Path:
    carpeta = tmp_path / "etc"
    carpeta.mkdir()
    (carpeta / "cron.deny").write_text("navagente\n", encoding="utf-8")
    (carpeta / "at.deny").write_text("otro\nnavagente\n", encoding="utf-8")
    return carpeta


def _abrir_sin_permiso(ruta, modo="r", *a, **k):
    """El open de un /etc de solo lectura: crear algo falla con PermissionError."""
    raise PermissionError(13, "Permission denied")


def _comprobar(etc: Path, acceso=None, grupos=None, uid=1001, respuestas=None, touch_falla=True, rutas=None):
    ejecutar = _ejecutar_falso(SIN_PRIVILEGIOS if respuestas is None else respuestas)
    if acceso is None:
        acceso = lambda ruta, modo: False  # noqa: E731
    r = s.comprobar(ejecutar=ejecutar, acceso=acceso, grupos=GRUPOS_LIMPIOS if grupos is None else grupos,
                    uid=uid, etc=etc, usuario="navagente", abrir=_abrir_sin_permiso if touch_falla else open,
                    rutas=rutas)
    return r, ejecutar


def test_sin_privilegios_todo_pasa_y_son_al_menos_15(etc: Path) -> None:
    r, ejecutar = _comprobar(etc)
    assert len(r) >= 15
    fallos = [c for c in r if not c["pasa"]]
    assert fallos == [], fallos
    assert {tuple(l) for l in ejecutar.llamadas} == set(SIN_PRIVILEGIOS)
    assert all(set(c) == {"nombre", "esperado", "obtenido", "pasa"} for c in r)
    assert "sudo -n true falla" in [c["nombre"] for c in r]


def test_cada_privilegio_se_ve(etc: Path) -> None:
    r, _ = _comprobar(etc, uid=0)
    assert [c["nombre"] for c in r if not c["pasa"]] == ["uid no es 0"]
    r, _ = _comprobar(etc, grupos=["navagente", "video", "docker", "sudo"])
    assert sorted(c["nombre"] for c in r if not c["pasa"]) == ["no esta en el grupo docker", "no esta en el grupo sudo"]
    # rutas que existen (el etc falso y su padre): W_OK verdadero en una de ellas es un privilegio
    r, _ = _comprobar(etc, acceso=lambda ruta, modo: ruta == str(etc), rutas=(str(etc), str(etc.parent)))
    assert [c["nombre"] for c in r if not c["pasa"]] == [f"sin escritura en {etc}"]
    con_sudo = dict(SIN_PRIVILEGIOS)
    con_sudo[("sudo", "-n", "true")] = (0, "")
    con_sudo[("crontab", "-l")] = (0, "")
    con_sudo[("docker", "ps")] = (0, "CONTAINER ID")
    con_sudo[("loginctl", "show-user", "navagente", "-p", "Linger")] = (0, "Linger=yes")
    r, _ = _comprobar(etc, respuestas=con_sudo)
    assert sorted(c["nombre"] for c in r if not c["pasa"]) == ["crontab -l negado", "docker ps negado",
                                                               "sin linger de systemd", "sudo -n true falla"]


def test_el_touch_que_si_se_crea_se_borra_y_es_fallo(etc: Path) -> None:
    r, _ = _comprobar(etc, touch_falla=False)
    touch = [c for c in r if c["nombre"] == "touch en /etc falla"][0]
    assert touch["pasa"] is False and "se creo" in touch["obtenido"]
    assert not list(etc.glob("nav-sonda-*")), "dejo la marca en /etc"


def test_cron_y_at_deny_sin_el_usuario_es_fallo(etc: Path) -> None:
    (etc / "at.deny").write_text("otro\n", encoding="utf-8")
    (etc / "cron.deny").unlink()
    r, _ = _comprobar(etc)
    nombres = sorted(c["nombre"] for c in r if not c["pasa"])
    assert nombres == ["navagente en /etc/at.deny", "navagente en /etc/cron.deny"]


def test_rutas_que_no_existen_pasan_sin_mirar_el_acceso(etc: Path) -> None:
    def acceso(ruta, modo):
        raise AssertionError(f"no deberia mirar {ruta}")
    # En el PC no existe ninguna de las rutas de Linux, asi que el acceso falso no se llama.
    if any(os.path.exists(r) for r in s.RUTAS_SIN_ESCRITURA):
        pytest.skip("esta maquina tiene rutas de Linux: la prueba es para el PC")
    r, _ = _comprobar(etc, acceso=acceso)
    assert sum(c["obtenido"] == "no existe" for c in r) == len(s.RUTAS_SIN_ESCRITURA)


def test_main_sale_con_0_solo_sin_privilegios(etc: Path, monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(s, "comprobar", lambda **k: [{"nombre": "a", "esperado": "x", "obtenido": "x", "pasa": True}])
    salida = tmp_path / "sonda.json"
    assert s.main(["--salida", str(salida)]) == 0
    informe = json.loads(salida.read_text(encoding="utf-8"))
    assert informe["comprobaciones"] == 1 and informe["privilegios_encontrados"] == 0
    monkeypatch.setattr(s, "comprobar", lambda **k: [{"nombre": "a", "esperado": "x", "obtenido": "y", "pasa": False}])
    assert s.main([]) == 1
    out, err = capsys.readouterr()
    assert json.loads(out)["privilegios_encontrados"] == 1
    assert "1 privilegios encontrados en 1 comprobaciones" in err


def test_la_sonda_corre_suelta_con_python_i(tmp_path: Path) -> None:
    """Como la lanza el autor la primera vez: `python3 -I sonda_privilegios.py`, sin paquete."""
    r = subprocess.run([sys.executable, "-I", str(CODIGO_DIR / "linux" / "sonda_privilegios.py"), "--salida",
                        str(tmp_path / "s.json")], capture_output=True, timeout=120, text=True)
    assert r.returncode in (0, 1), r.stderr
    informe = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert informe["comprobaciones"] >= 15
    assert "privilegios encontrados" in r.stderr
