"""La aceleracion por hardware de MSMF, apagada por el codigo (meta 002, fase 2b, correccion).

Sin camara. Cubre: camaras_uvc.apagar_aceleracion_msmf (pone 0 con setdefault
solo en Windows, respeta un valor explicito, dice lo que ve cv2 si ya estaba
cargado), su linea de log, que en esta misma sesion queda puesta, que cada
script que abre MSMF la deja apagada al importarse en un proceso nuevo (y que
tracker.py, que importa cv2 antes, no: B28), y el entorno de los procesos del
panel (procesos.entorno_hijo).
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

import camaras_uvc as cu
import procesos

from .conftest import ITER4_DIR

VAR = "OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"
PY = sys.executable


# ----------------------------------------------------------------------------
# La funcion, con un entorno de prueba
# ----------------------------------------------------------------------------

def test_pone_cero_en_windows_si_no_estaba() -> None:
    env: dict = {}
    e = cu.apagar_aceleracion_msmf(env, "win32", cv2_cargado=False)
    assert env == {VAR: "0"}
    assert e == {"valor": "0", "previo": None, "puesta_aqui": True, "cv2_cargado": False,
                 "efectiva": "apagada"}
    assert cu.describir_aceleracion_msmf(e) == f"Aceleracion HW de MSMF apagada ({VAR}=0, puesta por el codigo)"


@pytest.mark.parametrize("valor,efectiva", [("1", "encendida"), ("true", "encendida"),
                                            ("0", "apagada"), ("OFF", "apagada"),
                                            ("quizas", "desconocida")])
def test_no_pisa_un_valor_explicito(valor: str, efectiva: str) -> None:
    env = {VAR: valor}
    e = cu.apagar_aceleracion_msmf(env, "win32", cv2_cargado=True)
    assert env == {VAR: valor}                      # setdefault: lo puesto a mano se respeta
    assert e["valor"] == valor and e["puesta_aqui"] is False and e["efectiva"] == efectiva


def test_fuera_de_windows_no_toca_nada() -> None:
    env: dict = {}
    e = cu.apagar_aceleracion_msmf(env, "linux", cv2_cargado=False)
    assert env == {} and e["efectiva"] == "no aplica"
    assert "no aplica" in cu.describir_aceleracion_msmf(e)


def test_si_cv2_ya_estaba_cargado_no_llega_y_lo_dice() -> None:
    env: dict = {}
    e = cu.apagar_aceleracion_msmf(env, "win32", cv2_cargado=True)
    assert env == {VAR: "0"} and e["efectiva"] == "encendida"
    linea = cu.describir_aceleracion_msmf(e)
    assert linea.startswith("Aceleracion HW de MSMF ENCENDIDA: cv2 se cargo antes")
    assert f"$env:{VAR}='0'" in linea


def test_encendida_del_entorno_lo_dice() -> None:
    e = cu.apagar_aceleracion_msmf({VAR: "1"}, "win32", cv2_cargado=False)
    assert cu.describir_aceleracion_msmf(e).startswith(f"Aceleracion HW de MSMF encendida ({VAR}=1, del entorno)")


@pytest.mark.skipif(sys.platform != "win32", reason="MSMF solo existe en Windows")
def test_en_esta_sesion_queda_puesta() -> None:
    assert VAR in os.environ
    assert cu.ACELERACION_MSMF["valor"] == os.environ[VAR]


# ----------------------------------------------------------------------------
# Cada script que abre MSMF, importado en un proceso nuevo (sin la variable)
# ----------------------------------------------------------------------------

MODULOS_MSMF = ["camera_backend", "camaras_uvc", "ajustes_camara", "sondear_camara",
                "identificar_ids", "calibrar_camara", "calibrar_tip_divot", "captura_calibracion"]
# (modulo, valor de la variable al lanzar o None si no esta)
CASOS = [(m, None) for m in MODULOS_MSMF] + [("tracker", None), ("tracker", "0"),
                                             ("camera_backend", "1")]


@pytest.fixture(scope="module")
def importados() -> dict:
    """Importa cada modulo en un proceso nuevo (todos a la vez, para no alargar la suite).

    Devuelve {(modulo, valor): [efectiva, valor, puesta_aqui, os.environ del proceso]}.
    """
    if sys.platform != "win32":
        pytest.skip("MSMF solo existe en Windows")
    procs = {}
    for modulo, valor in CASOS:
        env = {k: v for k, v in os.environ.items() if k != VAR}
        if valor is not None:
            env[VAR] = valor
        codigo = (f"import {modulo}, camaras_uvc as c, os; e = c.ACELERACION_MSMF; "
                  f"print(e['efectiva'], e['valor'], e['puesta_aqui'], os.environ.get({VAR!r}))")
        procs[(modulo, valor)] = subprocess.Popen(
            [PY, "-c", codigo], cwd=str(ITER4_DIR), env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    salida = {}
    for clave, p in procs.items():
        try:
            out, err = p.communicate(timeout=90)      # principio 9: con tope
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
        assert p.returncode == 0, f"{clave}: {err[-2000:]}"
        salida[clave] = out.strip().splitlines()[-1].split()
    return salida


@pytest.mark.parametrize("modulo", MODULOS_MSMF)
def test_cada_script_la_deja_apagada(importados: dict, modulo: str) -> None:
    assert importados[(modulo, None)] == ["apagada", "0", "True", "0"]


def test_tracker_importa_cv2_antes_y_no_la_ve(importados: dict) -> None:
    """tracker.py no se toca (principio 6): lanzado a mano necesita la variable en el entorno (B28)."""
    assert importados[("tracker", None)] == ["encendida", "0", "True", "0"]
    assert importados[("tracker", "0")] == ["apagada", "0", "False", "0"]


def test_un_uno_explicito_se_respeta_en_proceso_nuevo(importados: dict) -> None:
    assert importados[("camera_backend", "1")] == ["encendida", "1", "False", "1"]


# ----------------------------------------------------------------------------
# Los procesos del panel
# ----------------------------------------------------------------------------

def test_entorno_hijo_del_panel() -> None:
    assert procesos.VAR_ACELERACION_MSMF == cu.VAR_ACELERACION_MSMF
    base = {"PATH": "x"}
    env = procesos.entorno_hijo(base, "win32")
    assert env == {"PATH": "x", "PYTHONIOENCODING": "utf-8", VAR: "0"} and base == {"PATH": "x"}
    assert procesos.entorno_hijo({VAR: "1"}, "win32")[VAR] == "1"
    assert VAR not in procesos.entorno_hijo({}, "linux")
