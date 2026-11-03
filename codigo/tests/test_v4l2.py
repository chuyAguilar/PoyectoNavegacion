"""camera.v4l2 y la rama Linux de camera.backend, sin camara (meta 007 · El tracker en la
Jetson Orin Nano, fase 5 · La capa V4L2 y cada camara en la Jetson).

Cubre, con las salidas reales de `v4l2-ctl` del escaneo de la fase 1 (tests/data/linux/):
el parser de `--list-ctrls-menus` (18 controles por camara, focus 500 y 332, exposicion
10, auto_exposure en Manual Mode); las conversiones (0.977 ms -> 10; enteros); la lista
de /dev/v4l/by-path con enlaces falsos y `resolver_dispositivo` con 0, 1 y 2
coincidencias (index1 no cuenta); `ejecutar_v4l2ctl` con un `subprocess.run` falso (argv
cerrado, tope, codigo != 0, sin v4l-utils); `CapaLinuxV4L2.leer` y `aplicar` (escribe
solo lo que difiere, en orden, relee, para si la camara no lo toma o si un valor cae
fuera del rango, `forzar`); `capa_para_plataforma("linux")`; el CLI con falsos; y
`WebcamBackend` en Linux: abre `/dev/videoN` con CAP_V4L2 tras listar, leer la marca y
aplicar, con las mismas llamadas a cv2 que en Windows; la marca de la otra camara para;
sin `usb_port_linux` ni `source` para; y en Windows `open()` hace exactamente las mismas
llamadas que antes aunque el perfil traiga `usb_port_linux` (principio 6: la cadena cambia
solo en la rama Linux).
"""
from __future__ import annotations

import subprocess
import sys

import cv2
import pytest
import yaml

from camera import backend as cb
from camera import controls as ac
from camera import v4l2 as cv4l2

from .conftest import PROFILES_DIR, TESTS_DATA_DIR, RealHardwareForbidden
from .test_camera_backend import CONTROLS, CapFalso, FOURCC_MJPG, PUERTO_1

LINUX_DATA = TESTS_DATA_DIR / "linux"
# Las funciones reales, tomadas al importar (antes de que el fixture B34 las niegue): aqui se
# prueban con una carpeta temporal y un `subprocess.run` falso, sin tocar hardware.
listar_camaras_v4l2_real = cv4l2.listar_camaras_v4l2
ejecutar_v4l2ctl_real = cv4l2.ejecutar_v4l2ctl
BYPATH_1 = "platform-3610000.usb-usb-0:2.1:1.0-video-index0"      # gs1 (focus 500)
BYPATH_2 = "platform-3610000.usb-usb-0:2.2:1.0-video-index0"      # gs2 (focus 332)
CONTROLS_GS = {**CONTROLS, "exposure_ms": 0.977}                  # lo que traen gs1 y gs2
# El orden de escritura esperado: el de NOMBRES (auto_exposure antes que la exposicion).
NATIVOS_GS = {"auto_exposure": 1, "exposure_time_absolute": 10, "gain": 11,
              "white_balance_automatic": 0, "brightness": 0, "contrast": 0, "saturation": 56,
              "sharpness": 0, "gamma": 110, "backlight_compensation": 54}


def _texto(nombre: str) -> str:
    return (LINUX_DATA / nombre).read_text(encoding="utf-8")


# ----------------------------------------------------------------------------
# Falsos
# ----------------------------------------------------------------------------

class V4l2ctlFalso:
    """Un `ejecutar(args, timeout_s)` que simula v4l2-ctl sobre una camara con estado.

    `estado` arranca de la salida real del escaneo; `--set-ctrl=a=b` lo cambia (salvo los
    controles en `rechaza`, que fallan como v4l2-ctl: RuntimeError) y
    `--list-ctrls-menus` lo imprime con los valores de hoy.
    """

    def __init__(self, texto: str, rechaza: tuple = (), dispositivo: str = "/dev/video2") -> None:
        self.texto = texto
        self.rechaza = set(rechaza)
        self.dispositivo = dispositivo
        self.estado = {n: c["value"] for n, c in cv4l2.parsear_list_ctrls(texto).items()}
        self.llamadas: list = []

    def __call__(self, args, timeout_s):
        self.llamadas.append((list(args), timeout_s))
        assert args[0] == "-d" and args[1] == self.dispositivo, args
        if args[2] == "--list-ctrls-menus":
            return self._listado()
        assert args[2].startswith("--set-ctrl=") and len(args) == 3, args
        ctrl, valor = args[2][len("--set-ctrl="):].split("=")
        if ctrl in self.rechaza:
            raise RuntimeError(f"[v4l2] v4l2-ctl salio con 1: VIDIOC_S_EXT_CTRLS: failed ({ctrl})")
        self.estado[ctrl] = int(valor)
        return ""

    def _listado(self) -> str:
        import re
        lineas = []
        for linea in self.texto.splitlines():
            m = re.match(r"^(\s*)([a-z0-9_]+)(\s+0x[0-9a-f]+\s+\(\w+\)\s*:\s*.*?)value=-?\d+(.*)$", linea)
            if m and m.group(2) in self.estado:
                linea = f"{m.group(1)}{m.group(2)}{m.group(3)}value={self.estado[m.group(2)]}{m.group(4)}"
            lineas.append(linea)
        return "\n".join(lineas) + "\n"


def _camaras(*nombres: str) -> list[cv4l2.CamaraV4L2]:
    return [cv4l2.CamaraV4L2(n, f"/dev/video{i}") for i, n in enumerate(nombres)]


def _capa(texto: str = None, rechaza=(), camaras=None, dispositivo="/dev/video2"):
    falso = V4l2ctlFalso(texto if texto is not None else _texto("v4l2_list_ctrls_gs1.txt"),
                         rechaza, dispositivo)
    camaras = camaras if camaras is not None else [cv4l2.CamaraV4L2(BYPATH_1, "/dev/video2"),
                                                   cv4l2.CamaraV4L2(BYPATH_2, "/dev/video0")]
    return cv4l2.CapaLinuxV4L2(listar=lambda: camaras, ejecutar=falso), falso


# ----------------------------------------------------------------------------
# El parser, sobre las salidas reales
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("archivo,focus", [("v4l2_list_ctrls_gs1.txt", 500), ("v4l2_list_ctrls_gs2.txt", 332)])
def test_parsear_list_ctrls_del_escaneo(archivo: str, focus: int) -> None:
    c = cv4l2.parsear_list_ctrls(_texto(archivo))
    assert len(c) == 18                                   # 11 User Controls + 7 Camera Controls
    assert c["focus_absolute"] == {"id": 0x009a090a, "tipo": "int", "min": 0, "max": 1023, "step": 1,
                                   "default": 0, "value": focus}
    assert c["exposure_time_absolute"]["value"] == 10 and c["exposure_time_absolute"]["max"] == 10000
    assert c["auto_exposure"] == {"id": 0x009a0901, "tipo": "menu", "min": 0, "max": 3, "default": 3,
                                  "value": 1, "etiqueta": "Manual Mode"}
    assert c["white_balance_automatic"] == {"id": 0x0098090c, "tipo": "bool", "default": 1, "value": 0}
    assert c["gain"]["value"] == 11 and c["backlight_compensation"]["value"] == 54
    assert c["power_line_frequency"]["etiqueta"] == "60 Hz"
    # Los 11 controles del perfil existen en la camara (criterio 3 de la fase 1).
    assert set(cv4l2.CONTROLES_V4L2.values()) <= set(c)


def test_parsear_list_ctrls_salta_menus_titulos_y_flags() -> None:
    texto = ("User Controls\n\n"
             "   brightness 0x00980900 (int)    : min=-64 max=64 step=1 default=0 value=3 flags=inactive\n"
             "\t\t\t\t0: Disabled\n"
             "basura sin forma\n")
    c = cv4l2.parsear_list_ctrls(texto)
    assert list(c) == ["brightness"] and c["brightness"]["value"] == 3 and c["brightness"]["flags"] == "inactive"
    assert cv4l2.parsear_list_ctrls("") == {}


# ----------------------------------------------------------------------------
# Conversiones
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("ms,esperado", [(0.977, 10), (1.0, 10), (3.906, 39), (0.1, 1), (15.625, 156), (1000.0, 10000)])
def test_exposicion_ms_a_v4l2(ms: float, esperado: int) -> None:
    assert cv4l2.exposicion_ms_a_v4l2(ms) == esperado


def test_exposicion_ms_a_v4l2_rechaza() -> None:
    with pytest.raises(ValueError, match="> 0"):
        cv4l2.exposicion_ms_a_v4l2(0)
    with pytest.raises(ValueError, match="por debajo de la unidad"):
        cv4l2.exposicion_ms_a_v4l2(0.04)
    assert cv4l2.v4l2_a_exposicion_ms(10) == 1.0 and cv4l2.v4l2_a_exposicion_ms(39) == 3.9


def test_a_nativos_v4l2_en_orden() -> None:
    nativos = cv4l2.a_nativos_v4l2(CONTROLS_GS)
    assert nativos == NATIVOS_GS and list(nativos) == list(NATIVOS_GS)
    assert list(nativos)[:2] == ["auto_exposure", "exposure_time_absolute"]
    assert cv4l2.a_nativos_v4l2({"auto_white_balance": True, "gain": 3}) == \
        {"gain": 3, "white_balance_automatic": 1}
    assert cv4l2.a_nativos_v4l2({"exposure_manual": False}) == {"auto_exposure": 3}
    assert all(isinstance(v, int) for v in nativos.values())


def test_a_nativos_v4l2_valida() -> None:
    with pytest.raises(ValueError, match="'auto_exposure' no se admite"):
        cv4l2.a_nativos_v4l2({"auto_exposure": 1})
    with pytest.raises(ValueError, match="no es entero"):
        cv4l2.a_nativos_v4l2({"gain": 11.5})


def test_de_nativos_v4l2() -> None:
    perfil = cv4l2.de_nativos_v4l2({"auto_exposure": 1, "exposure_time_absolute": 10, "gain": 11,
                                    "white_balance_automatic": 0, "focus_absolute": 500, "hue": 0})
    assert perfil == {"exposure_manual": True, "exposure_ms": 1.0, "gain": 11.0,
                      "auto_white_balance": False, "focus": 500.0, "hue": 0.0}
    assert cv4l2.de_nativos_v4l2({"auto_exposure": 3})["exposure_manual"] is False
    assert set(cv4l2.CONTROLES_V4L2) == set(ac.NOMBRES)


# ----------------------------------------------------------------------------
# /dev/v4l/by-path
# ----------------------------------------------------------------------------

def _by_path_falso(tmp_path):
    """La carpeta del escaneo (`ls -l /dev/v4l/by-path`): los nombres, un `resolver` que hace
    de realpath con lo que decia el `ls -l` y, en Linux, los archivos de verdad (en Windows un
    nombre con `:` no se puede crear: se inyectan los nombres)."""
    destinos = {}
    for linea in _texto("v4l2_by_path.txt").splitlines():
        if "->" not in linea:
            continue
        nombre, destino = linea.split(" -> ")
        nombre = nombre.split()[-1]
        destinos[nombre] = "/dev/" + destino.split("/")[-1]
    nombres = [*destinos, "otra-cosa"]
    if sys.platform != "win32":
        for n in nombres:
            (tmp_path / n).write_text("")
        nombres = None                       # que los liste de la carpeta
    return destinos, nombres, (lambda ruta: destinos[ruta.replace("\\", "/").split("/")[-1]])


def test_listar_camaras_v4l2_con_enlaces_falsos(tmp_path) -> None:
    destinos, nombres, resolver = _by_path_falso(tmp_path)
    camaras = listar_camaras_v4l2_real(tmp_path, resolver=resolver, nombres=nombres)
    assert [c.ruta_puerto for c in camaras] == sorted(destinos)      # 4: index0 e index1 de cada una
    assert {c.ruta_puerto: c.dispositivo for c in camaras} == destinos
    assert cv4l2.resolver_dispositivo(BYPATH_1, camaras) == "/dev/video2"
    assert cv4l2.resolver_dispositivo(BYPATH_2, camaras) == "/dev/video0"


def test_listar_camaras_v4l2_sin_carpeta(tmp_path) -> None:
    with pytest.raises(OSError, match="no existe"):
        listar_camaras_v4l2_real(tmp_path / "no")


def test_resolver_dispositivo_cero_y_dos() -> None:
    camaras = _camaras(BYPATH_1, BYPATH_1.replace("index0", "index1"))
    assert cv4l2.resolver_dispositivo(BYPATH_1, camaras) == "/dev/video0"      # index1 no cuenta
    with pytest.raises(ValueError, match="no coincide con ninguna"):
        cv4l2.resolver_dispositivo(BYPATH_2, camaras)
    with pytest.raises(ValueError, match="coincide con 2 camaras"):
        cv4l2.resolver_dispositivo(BYPATH_1, _camaras(BYPATH_1, BYPATH_1))
    with pytest.raises(ValueError, match="puerto vacio"):
        cv4l2.resolver_dispositivo("", camaras)
    with pytest.raises(ValueError, match="ninguna camara enumerada"):
        cv4l2.resolver_dispositivo(BYPATH_1, [])


# ----------------------------------------------------------------------------
# ejecutar_v4l2ctl, con un subprocess.run falso
# ----------------------------------------------------------------------------

class _Run:
    def __init__(self, rc=0, out="hola\n", err="", excepcion=None) -> None:
        self.rc, self.out, self.err, self.excepcion = rc, out, err, excepcion
        self.llamadas: list = []

    def __call__(self, argv, **kw):
        self.llamadas.append((argv, kw))
        if self.excepcion is not None:
            raise self.excepcion
        return subprocess.CompletedProcess(argv, self.rc, self.out, self.err)


def test_ejecutar_v4l2ctl_argv_cerrado_y_tope() -> None:
    run = _Run()
    assert ejecutar_v4l2ctl_real(["-d", "/dev/video2", "--list-ctrls-menus"], 2.5, ejecutar=run) == "hola\n"
    argv, kw = run.llamadas[0]
    assert argv == ["v4l2-ctl", "-d", "/dev/video2", "--list-ctrls-menus"]
    assert kw == {"capture_output": True, "text": True, "timeout": 2.5}      # sin shell


def test_ejecutar_v4l2ctl_falla_fuerte() -> None:
    with pytest.raises(RuntimeError, match="salio con 1: VIDIOC_S_EXT_CTRLS"):
        ejecutar_v4l2ctl_real(["--set-ctrl=gain=1"], ejecutar=_Run(rc=1, err="VIDIOC_S_EXT_CTRLS: failed\n"))
    with pytest.raises(RuntimeError, match="v4l-utils"):
        ejecutar_v4l2ctl_real(["--list-devices"], ejecutar=_Run(excepcion=FileNotFoundError()))
    with pytest.raises(RuntimeError, match="no respondio en 5 s"):
        ejecutar_v4l2ctl_real(["--list-devices"],
                              ejecutar=_Run(excepcion=subprocess.TimeoutExpired("v4l2-ctl", 5.0)))


# ----------------------------------------------------------------------------
# CapaLinuxV4L2
# ----------------------------------------------------------------------------

def test_leer_da_las_unidades_del_perfil() -> None:
    capa, falso = _capa()
    leidos = capa.leer(BYPATH_1, list(cv4l2.CONTROLES_V4L2))
    assert leidos == {"exposure_manual": True, "exposure_ms": 1.0, "gain": 11.0, "auto_white_balance": False,
                      "brightness": 0.0, "contrast": 0.0, "saturation": 56.0, "sharpness": 0.0,
                      "gamma": 110.0, "backlight": 54.0, "focus": 500.0}
    assert falso.llamadas == [(["-d", "/dev/video2", "--list-ctrls-menus"], cv4l2.TOPE_V4L2CTL_S)]
    assert capa.leer(BYPATH_1, ["focus"]) == {"focus": 500.0}


def test_leer_rechaza_nombres_y_puerto() -> None:
    capa, falso = _capa()
    with pytest.raises(ValueError, match="no se leen por V4L2"):
        capa.leer(BYPATH_1, ["hue"])
    with pytest.raises(ValueError, match="no coincide con ninguna"):
        capa.leer("platform-x.usb-usb-0:9:1.0-video-index0", ["focus"])
    assert falso.llamadas == []


def test_leer_un_control_que_la_camara_no_tiene_para() -> None:
    capa, _ = _capa(texto="   gain 0x00980913 (int)    : min=0 max=1023 step=1 default=0 value=11\n")
    with pytest.raises(RuntimeError, match=r"no tiene los controles \['focus_absolute'\]"):
        capa.leer(BYPATH_1, ["focus"])


def test_aplicar_sin_diferencias_no_escribe() -> None:
    capa, falso = _capa()
    r = capa.aplicar(BYPATH_1, CONTROLS_GS)
    assert r["escritos"] == [] and r["set_false"] == [] and r["diferencias"] == []
    assert r["dispositivo"] == "/dev/video2" and r["forzado"] is False
    assert r["leidos_nativos"] == NATIVOS_GS and r["antes_nativos"] == NATIVOS_GS
    assert r["leidos"]["exposure_ms"] == 1.0 and r["leidos"]["exposure_manual"] is True
    assert [a[0][2] for a in falso.llamadas] == ["--list-ctrls-menus", "--list-ctrls-menus"]


def test_aplicar_escribe_solo_lo_que_difiere_y_en_orden() -> None:
    capa, falso = _capa()
    falso.estado["auto_exposure"] = 3                  # la camara venia en automatico
    falso.estado["exposure_time_absolute"] = 156
    falso.estado["gain"] = 0
    r = capa.aplicar(BYPATH_1, CONTROLS_GS)
    assert r["escritos"] == ["auto_exposure", "exposure_time_absolute", "gain"]
    sets = [a[0][2] for a in falso.llamadas if a[0][2].startswith("--set-ctrl=")]
    assert sets == ["--set-ctrl=auto_exposure=1", "--set-ctrl=exposure_time_absolute=10", "--set-ctrl=gain=11"]
    assert r["antes"]["exposure_manual"] is False and r["antes"]["exposure_ms"] == 15.6
    assert r["leidos_nativos"] == NATIVOS_GS and r["diferencias"] == []


def test_aplicar_para_si_la_camara_no_lo_toma() -> None:
    capa, falso = _capa(rechaza=("gain",))
    falso.estado["gain"] = 0
    with pytest.raises(ac.AjustesNoAplicados, match="gain: declarado 11, leido 0") as e:
        capa.aplicar(BYPATH_1, CONTROLS_GS)
    r = e.value.resultado
    assert r["escritos"] == ["gain"] and r["set_false"] == ["gain"] and "gain" in r["errores"]
    assert r["leidos_nativos"]["gain"] == 0


def test_aplicar_fuera_de_rango_no_escribe_nada() -> None:
    capa, falso = _capa()
    with pytest.raises(ValueError, match=r"gain=2000 fuera de \[0, 1023\]: no se escribe nada"):
        capa.aplicar(BYPATH_1, {**CONTROLS_GS, "gain": 2000})
    assert [a[0][2] for a in falso.llamadas] == ["--list-ctrls-menus"]


def test_aplicar_forzar_escribe_todo() -> None:
    capa, falso = _capa()
    r = capa.aplicar(BYPATH_1, CONTROLS_GS, forzar=True)
    assert r["escritos"] == list(NATIVOS_GS) and r["forzado"] is True and r["diferencias"] == []
    assert len([a for a in falso.llamadas if a[0][2].startswith("--set-ctrl=")]) == 10


def test_capa_resuelve_los_falsos_al_llamar() -> None:
    """Sin inyeccion, la capa llega al modulo (que la suite niega, B34)."""
    capa = cv4l2.CapaLinuxV4L2()
    with pytest.raises(RealHardwareForbidden):
        capa.dispositivo(BYPATH_1)
    with pytest.raises(RealHardwareForbidden):
        capa.controles("/dev/video2")


# ----------------------------------------------------------------------------
# El CLI
# ----------------------------------------------------------------------------

def test_main_listar_y_leer(monkeypatch, capsys) -> None:
    camaras = [cv4l2.CamaraV4L2(BYPATH_1, "/dev/video2"), cv4l2.CamaraV4L2(BYPATH_2, "/dev/video0")]
    monkeypatch.setattr(cv4l2, "listar_camaras_v4l2", lambda: camaras)
    assert cv4l2.main(["--listar"]) == 0
    out = capsys.readouterr().out
    assert "2 enlace(s)" in out and f"{BYPATH_1} -> /dev/video2" in out
    monkeypatch.setattr(cv4l2, "ejecutar_v4l2ctl", V4l2ctlFalso(_texto("v4l2_list_ctrls_gs1.txt")))
    assert cv4l2.main(["--leer", "--puerto", BYPATH_1]) == 0
    out = capsys.readouterr().out
    assert "focus = 500.0" in out and "exposure_ms = 1.0" in out and "/dev/video2" in out


def test_main_aplicar_con_el_perfil_gs1(monkeypatch, capsys) -> None:
    camaras = [cv4l2.CamaraV4L2(BYPATH_1, "/dev/video2"), cv4l2.CamaraV4L2(BYPATH_2, "/dev/video0")]
    monkeypatch.setattr(cv4l2, "listar_camaras_v4l2", lambda: camaras)
    falso = V4l2ctlFalso(_texto("v4l2_list_ctrls_gs1.txt"))
    monkeypatch.setattr(cv4l2, "ejecutar_v4l2ctl", falso)
    assert cv4l2.main(["--aplicar", "--config", str(PROFILES_DIR / "tracker_config_gs1.yaml")]) == 0
    assert "Marca comprobada" in capsys.readouterr().out
    # La camara del otro puerto (focus 332) con el perfil gs1: para por la marca, sin escribir.
    monkeypatch.setattr(cv4l2, "ejecutar_v4l2ctl",
                        V4l2ctlFalso(_texto("v4l2_list_ctrls_gs2.txt"), dispositivo="/dev/video2"))
    assert cv4l2.main(["--aplicar", "--config", str(PROFILES_DIR / "tracker_config_gs1.yaml")]) == 1
    assert "no es la del perfil" in capsys.readouterr().err


def test_main_argumentos() -> None:
    with pytest.raises(SystemExit):
        cv4l2.main(["--leer"])                                  # sin --puerto
    with pytest.raises(SystemExit):
        cv4l2.main(["--leer", "--puerto", "/dev/video0"])       # no es by-path
    with pytest.raises(SystemExit):
        cv4l2.main(["--aplicar"])                               # sin --config
    with pytest.raises(SystemExit):
        cv4l2.main([])


# ----------------------------------------------------------------------------
# WebcamBackend en Linux
# ----------------------------------------------------------------------------

class EscenarioLinux:
    """Un backend con plataforma linux y todo falso; `orden` junta las llamadas."""

    def __init__(self, cap=None, texto_ctrls="v4l2_list_ctrls_gs1.txt", camaras=None, **kw):
        self.cap = cap if cap is not None else CapFalso(tamano=(1280, 960))
        self.orden: list = []
        self.capa, self.v4l2ctl = _capa(_texto(texto_ctrls), camaras=camaras)
        leer, aplicar = self.capa.leer, self.capa.aplicar
        self.capa.leer = lambda p, n: (self.orden.append("leer"), leer(p, n))[1]
        self.capa.aplicar = lambda p, c: (self.orden.append("aplicar"), aplicar(p, c))[1]

        def listar():
            self.orden.append("listar")
            return self.capa._camaras()

        def abrir(i, b):
            self.orden.append(("abrir", i, b))
            return self.cap
        kw.setdefault("width", 1280)
        kw.setdefault("height", 960)
        kw.setdefault("fps", 90)
        self.backend = cb.WebcamBackend(abrir=abrir, listar=listar, capa=self.capa,
                                        plataforma="linux", **kw)


def test_linux_abre_el_dispositivo_por_v4l2_tras_marca_y_ajustes() -> None:
    e = EscenarioLinux(usb_port_linux=BYPATH_1, controls=CONTROLS_GS, marca={"focus": 500})
    e.backend.open()
    assert e.orden == ["listar", "leer", "aplicar", ("abrir", "/dev/video2", cv2.CAP_V4L2)]
    assert e.backend.indice == "/dev/video2" and e.backend.puerto == BYPATH_1
    assert e.backend.clave_puerto == "usb_port_linux" and e.backend.linux is True
    # Las mismas llamadas a cv2 que en Windows (FOURCC, tamano, fps, 5 lecturas).
    assert e.cap.llamadas == [
        ("isOpened",),
        ("set", cv2.CAP_PROP_FOURCC, FOURCC_MJPG),
        ("set", cv2.CAP_PROP_FRAME_WIDTH, 1280),
        ("set", cv2.CAP_PROP_FRAME_HEIGHT, 960),
        ("set", cv2.CAP_PROP_FPS, 90),
    ] + [("read",)] * 5
    assert e.backend.tamano_real == (1280, 960)
    assert e.backend.ajustes_leidos["focus"] if "focus" in e.backend.ajustes_leidos else True
    assert e.backend.ajustes_leidos["exposure_ms"] == 1.0 and e.backend.ajustes_leidos["gain"] == 11.0
    e.backend.close()
    assert e.cap.llamadas[-1] == ("release",)


def test_linux_dice_que_el_backend_del_perfil_no_se_usa(capsys) -> None:
    e = EscenarioLinux(usb_port_linux=BYPATH_1, backend="MSMF")
    e.backend.open()
    out = capsys.readouterr().out
    assert "Linux: backend V4L2 (el perfil dice MSMF" in out
    assert "backend=V4L2" in out and "Aceleracion HW de MSMF" not in out


def test_linux_con_el_perfil_de_la_otra_camara_para_por_la_marca() -> None:
    """La corrida c) del protocolo P-5: el perfil gs1 sobre el puerto de gs2 no abre ni escribe."""
    e = EscenarioLinux(usb_port_linux=BYPATH_1, controls=CONTROLS_GS, marca={"focus": 500},
                       texto_ctrls="v4l2_list_ctrls_gs2.txt")
    with pytest.raises(RuntimeError, match="no es la del perfil .*focus: declarado 500, leido 332"):
        e.backend.open()
    assert e.orden == ["listar", "leer"] and e.cap.llamadas == []
    assert all(not a[0][2].startswith("--set-ctrl=") for a in e.v4l2ctl.llamadas)


def test_linux_puerto_sin_coincidencia_para_antes_de_abrir() -> None:
    e = EscenarioLinux(usb_port_linux=BYPATH_1, camaras=[cv4l2.CamaraV4L2(BYPATH_2, "/dev/video0")])
    with pytest.raises(ValueError, match="no coincide con ninguna"):
        e.backend.open()
    assert e.orden == ["listar"] and e.cap.llamadas == []


def test_linux_source_solo_abre_el_indice_por_v4l2() -> None:
    e = EscenarioLinux(source=2)
    e.backend.open()
    assert e.orden == [("abrir", 2, cv2.CAP_V4L2)]


def test_linux_source_y_puerto_que_no_coinciden_para() -> None:
    e = EscenarioLinux(usb_port_linux=BYPATH_1, source=0)
    with pytest.raises(RuntimeError, match="source=0 .* es /dev/video2"):
        e.backend.open()
    ok = EscenarioLinux(usb_port_linux=BYPATH_1, source=2)
    ok.backend.open()
    assert ok.backend.indice == "/dev/video2"


def test_linux_sin_usb_port_linux_ni_source_para_al_construir() -> None:
    with pytest.raises(ValueError, match="ni usb_port_linux ni source"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, plataforma="linux")      # solo la de Windows
    with pytest.raises(ValueError, match="controls exige usb_port_linux"):
        cb.WebcamBackend(source=0, controls=CONTROLS_GS, plataforma="linux")
    with pytest.raises(ValueError, match="marca exige usb_port_linux"):
        cb.WebcamBackend(source=0, marca={"focus": 500}, plataforma="linux")
    # En Linux `backend: MSMF` no estorba (se ignora); en Windows seguiria exigiendo MSMF o DSHOW.
    assert cb.WebcamBackend(usb_port_linux=BYPATH_1, backend="MSMF", plataforma="linux").linux


def test_linux_capa_por_defecto_es_v4l2() -> None:
    b = cb.WebcamBackend(usb_port_linux=BYPATH_1, plataforma="linux")
    assert isinstance(b._capa_ajustes(), cv4l2.CapaLinuxV4L2)
    w = cb.WebcamBackend(usb_port_windows=PUERTO_1, plataforma="win32")
    assert isinstance(w._capa_ajustes(), ac.CapaWindowsDShow)


def test_linux_con_los_perfiles_reales_no_abre_nada() -> None:
    """B34 tambien en la rama Linux: construir con el perfil y abrir sin falsos se niega."""
    for nombre in ("tracker_config_gs1.yaml", "tracker_config_gs2.yaml"):
        with open(PROFILES_DIR / nombre, encoding="utf-8") as f:
            cam = yaml.safe_load(f)["camera"]
        b = cb.WebcamBackend(width=cam["width"], height=cam["height"], fps=cam["fps"],
                             controls=cam["controls"], marca=cam["marca"],
                             usb_port_linux=cam["usb_port_linux"], plataforma="linux")
        with pytest.raises(RealHardwareForbidden):
            b.open()
        assert b.cap is None and b.indice is None


# ----------------------------------------------------------------------------
# Windows no cambia (principio 6: la cadena cambia solo en la rama Linux)
# ----------------------------------------------------------------------------

def test_en_windows_open_hace_las_mismas_llamadas_con_o_sin_usb_port_linux() -> None:
    from .test_camera_backend import Escenario
    con = Escenario(usb_port_windows=PUERTO_1, controls=CONTROLS_GS, marca={"focus": 500},
                    lecturas={"focus": 500.0}, usb_port_linux=BYPATH_1)
    sin = Escenario(usb_port_windows=PUERTO_1, controls=CONTROLS_GS, marca={"focus": 500},
                    lecturas={"focus": 500.0})
    con.backend.open()
    sin.backend.open()
    assert con.orden == sin.orden == ["listar", "leer", "aplicar", ("abrir", 0, cv2.CAP_MSMF)]
    assert con.cap.llamadas == sin.cap.llamadas
    assert con.capa.llamadas == sin.capa.llamadas == [("leer", PUERTO_1, ["focus"]),
                                                      ("aplicar", PUERTO_1, ac.validar_controles(CONTROLS_GS))]
    assert con.backend.puerto == PUERTO_1 and con.backend.clave_puerto == "usb_port_windows"
    assert con.backend.usb_port_linux == BYPATH_1 and con.backend.linux is False


def test_create_backend_lleva_usb_port_linux_de_los_perfiles() -> None:
    for nombre, esperado in (("tracker_config_gs1.yaml", BYPATH_1), ("tracker_config_gs2.yaml", BYPATH_2)):
        with open(PROFILES_DIR / nombre, encoding="utf-8") as f:
            cam = yaml.safe_load(f)["camera"]
        b = cb.create_backend(cam)
        assert b.usb_port_linux == esperado
        assert cv4l2.RE_BYPATH.match(esperado)                  # el guardian lo acepta tal cual
