"""camera_backend.WebcamBackend sin camara: VideoCapture, listar y capa falsos (meta 002, fase 2b).

Cubre: sin controls ni usb_port_windows, las mismas llamadas a cv2 y en el mismo
orden que antes; create_backend con los perfiles del repo; puerto con 0, 1 y 2
coincidencias; puerto y source que no coinciden; controls o marca sin puerto;
capa que para; marca que coincide y que no (y que no se escribe nada); tamano
igual y distinto del pedido y del .yml; .yml sin tamano; sin frame en el warmup.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest
import yaml

import ajustes_camara as ac
import camaras_uvc as cu
import camera_backend as cb

from .conftest import ITER4_DIR

PUERTO_1 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(3)"
PUERTO_2 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(4)"
CONTROLS = {"exposure_manual": True, "exposure_ms": 3.906, "gain": 11,
            "auto_white_balance": False, "brightness": 0, "contrast": 0,
            "saturation": 56, "sharpness": 0, "gamma": 110, "backlight": 54}
FOURCC_MJPG = cv2.VideoWriter_fourcc(*"MJPG")


# ----------------------------------------------------------------------------
# Falsos
# ----------------------------------------------------------------------------

class CapFalso:
    """Registra las llamadas; read() entrega frames de `tamano` (w, h) o ninguno."""

    def __init__(self, tamano=(640, 480), abre=True, frames=5) -> None:
        self.tamano = tamano
        self.abre = abre
        self.frames = frames
        self.llamadas: list = []

    def isOpened(self) -> bool:
        self.llamadas.append(("isOpened",))
        return self.abre

    def set(self, prop, valor) -> bool:
        self.llamadas.append(("set", prop, valor))
        return True

    def read(self):
        self.llamadas.append(("read",))
        if self.frames <= 0:
            return False, None
        self.frames -= 1
        w, h = self.tamano
        return True, np.zeros((h, w, 3), dtype=np.uint8)

    def release(self) -> None:
        self.llamadas.append(("release",))


class CapaFalsa:
    """Una CapaAjustes que devuelve lo que se le dice y registra el orden."""

    def __init__(self, lecturas: dict | None = None, falla_aplicar: Exception | None = None):
        self.lecturas = dict(lecturas or {})
        self.falla_aplicar = falla_aplicar
        self.llamadas: list = []

    def leer(self, puerto, nombres):
        self.llamadas.append(("leer", puerto, list(nombres)))
        return {n: self.lecturas[n] for n in nombres if n in self.lecturas}

    def aplicar(self, puerto, controls):
        self.llamadas.append(("aplicar", puerto, dict(controls)))
        if self.falla_aplicar is not None:
            raise self.falla_aplicar
        leidos = ac.de_nativos_dshow(ac.a_nativos_dshow(controls))
        return {"indice": 0, "leidos": leidos, "escritos": [], "segundos": 0.01}


def _camaras(*puertos: str) -> list[cu.CamaraUVC]:
    return [cu.CamaraUVC(i, "Global Shutter Camera", f"\\\\?\\usb#vid_32e4&pid_0234&mi_00#{i}#x",
                         "32E4", "0234", str(i), ruta_puerto=p) for i, p in enumerate(puertos)]


class Escenario:
    """Un backend con todo falso; `orden` junta las llamadas en el orden real."""

    def __init__(self, cap: CapFalso | None = None, puertos=(PUERTO_1, PUERTO_2),
                 lecturas=None, falla_aplicar=None, **kw):
        self.cap = cap if cap is not None else CapFalso()
        self.orden: list = []
        self.capa = CapaFalsa(lecturas, falla_aplicar)
        capa_orig_leer, capa_orig_aplicar = self.capa.leer, self.capa.aplicar

        def leer(p, n):
            self.orden.append("leer")
            return capa_orig_leer(p, n)

        def aplicar(p, c):
            self.orden.append("aplicar")
            return capa_orig_aplicar(p, c)
        self.capa.leer, self.capa.aplicar = leer, aplicar

        def listar():
            self.orden.append("listar")
            return _camaras(*puertos)

        def abrir(i, b):
            self.orden.append(("abrir", i, b))
            return self.cap
        self.backend = cb.WebcamBackend(abrir=abrir, listar=listar, capa=self.capa, **kw)


# ----------------------------------------------------------------------------
# Sin lo nuevo: lo mismo que antes
# ----------------------------------------------------------------------------

def test_sin_puerto_ni_controls_mismas_llamadas_que_antes() -> None:
    e = Escenario(source=1, width=640, height=480, fps=30)
    e.backend.open()
    assert e.orden == [("abrir", 1, cv2.CAP_MSMF)]        # ni listar ni capa
    assert e.cap.llamadas == [
        ("isOpened",),
        ("set", cv2.CAP_PROP_FOURCC, FOURCC_MJPG),
        ("set", cv2.CAP_PROP_FRAME_WIDTH, 640),
        ("set", cv2.CAP_PROP_FRAME_HEIGHT, 480),
        ("set", cv2.CAP_PROP_FPS, 30),
    ] + [("read",)] * 5
    assert e.backend.indice == 1 and e.backend.tamano_real == (640, 480)
    assert e.backend.ajustes_leidos is None
    e.backend.close()
    assert e.cap.llamadas[-1] == ("release",)


def test_backend_dshow_y_sin_fourcc(capsys) -> None:
    e = Escenario(source=0, backend="DSHOW", fourcc=None)
    e.backend.open()
    assert e.orden == [("abrir", 0, cv2.CAP_DSHOW)]
    assert ("set", cv2.CAP_PROP_FOURCC, FOURCC_MJPG) not in e.cap.llamadas
    assert "Aceleracion HW de MSMF" not in capsys.readouterr().out   # DSHOW no la usa


def test_msmf_dice_en_una_linea_si_la_aceleracion_esta_apagada(capsys) -> None:
    e = Escenario(source=0)
    e.backend.open()
    lineas = [l for l in capsys.readouterr().out.splitlines() if "Aceleracion HW de MSMF" in l]
    assert lineas == [f"[Webcam] {cu.describir_aceleracion_msmf()}"]
    assert cb.camaras_uvc is cu       # camera_backend importa camaras_uvc (que la apaga)


def test_sin_source_ni_puerto_para_al_construir() -> None:
    with pytest.raises(ValueError, match="ni usb_port_windows ni source"):
        cb.WebcamBackend()


def test_no_abre_para_y_libera() -> None:
    e = Escenario(cap=CapFalso(abre=False), source=0)
    with pytest.raises(RuntimeError, match="No se pudo abrir"):
        e.backend.open()
    assert e.cap.llamadas[-1] == ("release",) and e.backend.cap is None


# ----------------------------------------------------------------------------
# create_backend con los perfiles del repo
# ----------------------------------------------------------------------------

def _camera(nombre: str) -> dict:
    with open(ITER4_DIR / nombre, encoding="utf-8") as f:
        return yaml.safe_load(f)["camera"]


def test_create_backend_femto_como_antes() -> None:
    b = cb.create_backend(_camera("tracker_config.yaml"))
    assert isinstance(b, cb.FemtoBoltBackend) and b.calibration_file is None


def test_create_backend_doctor_como_antes() -> None:
    b = cb.create_backend(_camera("tracker_config_doctor.yaml"))
    assert isinstance(b, cb.WebcamBackend)
    assert (b.source, b.width, b.height, b.fps, b.backend_name, b.fourcc) == \
        (1, 640, 480, 30, "MSMF", "MJPG")
    assert b.calibration_file == "data/globalshutter.yml"
    assert b.controls is None and b.usb_port_windows is None and b.marca is None


@pytest.mark.parametrize("nombre,puerto,focus", [("tracker_config_gs1.yaml", PUERTO_1, 500.0),
                                                 ("tracker_config_gs2.yaml", PUERTO_2, 332.0)])
def test_create_backend_gs(nombre: str, puerto: str, focus: float) -> None:
    b = cb.create_backend(_camera(nombre))
    assert isinstance(b, cb.WebcamBackend)
    assert b.source is None and b.usb_port_windows == puerto
    assert b.marca == {"focus": focus}
    assert b.controls == ac.validar_controles(CONTROLS)
    assert (b.width, b.height, b.fps, b.backend_name, b.fourcc) == (640, 480, 90, "MSMF", "MJPG")
    assert not b.calibration_file


def test_perfiles_gs1_gs2_contrato() -> None:
    """Lo que el plan pide de los perfiles nuevos, y lo que no cambia (principio 6)."""
    perfiles = {}
    for nombre in ("tracker_config_gs1.yaml", "tracker_config_gs2.yaml"):
        with open(ITER4_DIR / nombre, encoding="utf-8") as f:
            perfiles[nombre] = yaml.safe_load(f)
    g1, g2 = perfiles.values()
    assert g1["camera"]["usb_port_windows"] != g2["camera"]["usb_port_windows"]
    assert g1["camera"]["marca"]["focus"] != g2["camera"]["marca"]["focus"]
    for cfg in (g1, g2):
        cam = cfg["camera"]
        assert cam["camera_type"] == "webcam" and "source" not in cam
        assert "focus" not in cam["controls"]           # la marca no se escribe
        assert cam["controls"]["exposure_manual"] is True
        assert cam["controls"]["auto_white_balance"] is False
        assert cfg["markers"]["list"][0]["size_mm"] == 80.0
        assert cfg["rigid_bodies"][0]["geometry_file"] == "data/reference_dodecaedro_v2_calibrado.txt"
        assert cfg["rigid_bodies"][0]["marker_mm"] == 14.6
        assert cfg["rigid_bodies_quality"]["min_markers"] == 3
        assert cfg["igtlink"] == {"transforms_port": 18944, "video_port": 18945, "send_video": False}
        assert cfg["markers"]["detector"]["min_marker_perimeter_rate"] == 0.02
    assert (ITER4_DIR / "data" / "reference_dodecaedro_v2_calibrado.txt").exists()


# ----------------------------------------------------------------------------
# Identidad por puerto
# ----------------------------------------------------------------------------

def test_puerto_una_coincidencia_abre_ese_indice() -> None:
    e = Escenario(usb_port_windows=PUERTO_2)
    e.backend.open()
    assert e.orden == ["listar", ("abrir", 1, cv2.CAP_MSMF)] and e.backend.indice == 1


def test_puerto_sin_coincidencia_para_antes_de_abrir() -> None:
    e = Escenario(puertos=(PUERTO_1,), usb_port_windows=PUERTO_2)
    with pytest.raises(ValueError, match="no coincide con ninguna"):
        e.backend.open()
    assert e.orden == ["listar"] and e.cap.llamadas == []


def test_puerto_dos_coincidencias_para() -> None:
    e = Escenario(puertos=(PUERTO_1, PUERTO_1), usb_port_windows=PUERTO_1)
    with pytest.raises(ValueError, match="coincide con 2 camaras"):
        e.backend.open()
    assert e.cap.llamadas == []


def test_puerto_y_source_que_no_coinciden_para() -> None:
    e = Escenario(usb_port_windows=PUERTO_2, source=0)
    with pytest.raises(RuntimeError, match="source=0 .* indice 1"):
        e.backend.open()
    assert e.cap.llamadas == []
    ok = Escenario(usb_port_windows=PUERTO_2, source=1)
    ok.backend.open()
    assert ok.backend.indice == 1


def test_puerto_con_backend_any_para_al_construir() -> None:
    with pytest.raises(ValueError, match="MSMF o DSHOW"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, backend="ANY")


# ----------------------------------------------------------------------------
# Controles y marca
# ----------------------------------------------------------------------------

def test_controls_sin_puerto_para_al_construir() -> None:
    with pytest.raises(ValueError, match="controls exige usb_port_windows"):
        cb.WebcamBackend(source=0, controls=CONTROLS)


def test_controls_invalidos_paran_al_construir() -> None:
    with pytest.raises(ValueError, match="'auto_exposure' no se admite"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, controls={"auto_exposure": 0})


def test_controls_se_aplican_antes_de_abrir_y_quedan_leidos() -> None:
    e = Escenario(usb_port_windows=PUERTO_1, controls=CONTROLS)
    e.backend.open()
    assert e.orden == ["listar", "aplicar", ("abrir", 0, cv2.CAP_MSMF)]
    assert e.capa.llamadas == [("aplicar", PUERTO_1, ac.validar_controles(CONTROLS))]
    assert e.backend.ajustes_leidos["exposure_ms"] == pytest.approx(3.906, abs=1e-3)
    assert e.backend.ajustes_leidos["gain"] == 11.0
    assert e.backend.ajustes_leidos["auto_white_balance"] is False


def test_capa_que_para_no_abre_el_video() -> None:
    falla = ac.AjustesNoAplicados("gain: declarado 11, leido 0", {"escritos": ["gain"]})
    e = Escenario(usb_port_windows=PUERTO_1, controls=CONTROLS, falla_aplicar=falla)
    with pytest.raises(ac.AjustesNoAplicados, match="gain"):
        e.backend.open()
    assert e.orden == ["listar", "aplicar"] and e.cap.llamadas == []


def test_marca_sin_puerto_y_marca_invalida_paran_al_construir() -> None:
    with pytest.raises(ValueError, match="marca exige usb_port_windows"):
        cb.WebcamBackend(source=0, marca={"focus": 500})
    with pytest.raises(ValueError, match="'exposure_ms' no sirve de marca"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, marca={"exposure_ms": 3.906})
    with pytest.raises(ValueError, match="'iso' no sirve de marca"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, marca={"iso": 1})
    with pytest.raises(ValueError, match="tiene que ser un numero"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, marca={"focus": True})
    with pytest.raises(ValueError, match="esta en controls y en marca"):
        cb.WebcamBackend(usb_port_windows=PUERTO_1, marca={"focus": 500},
                         controls={**CONTROLS, "focus": 500})


def test_marca_que_coincide_se_lee_antes_de_aplicar() -> None:
    e = Escenario(usb_port_windows=PUERTO_1, controls=CONTROLS, marca={"focus": 500},
                  lecturas={"focus": 500.0})
    e.backend.open()
    assert e.orden == ["listar", "leer", "aplicar", ("abrir", 0, cv2.CAP_MSMF)]
    assert e.capa.llamadas[0] == ("leer", PUERTO_1, ["focus"])


def test_marca_que_no_coincide_para_sin_escribir_ni_abrir() -> None:
    e = Escenario(usb_port_windows=PUERTO_1, controls=CONTROLS, marca={"focus": 500},
                  lecturas={"focus": 332.0})
    with pytest.raises(RuntimeError, match="no es la del perfil .*focus: declarado 500, leido 332"):
        e.backend.open()
    assert e.orden == ["listar", "leer"] and e.cap.llamadas == []


def test_marca_sin_lectura_para() -> None:
    e = Escenario(usb_port_windows=PUERTO_1, marca={"focus": 500}, lecturas={})
    with pytest.raises(RuntimeError, match="leido None"):
        e.backend.open()


# ----------------------------------------------------------------------------
# Tamano del frame y del .yml
# ----------------------------------------------------------------------------

def _escribir_yml(ruta, tamano=None) -> str:
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_WRITE)
    fs.write("camera_matrix", np.eye(3))
    fs.write("distortion_coefficients", np.zeros((5, 1)))
    if tamano is not None:
        fs.write("image_width", int(tamano[0]))
        fs.write("image_height", int(tamano[1]))
    fs.release()
    return str(ruta)


def test_leer_tamano_yml(tmp_path) -> None:
    assert cb.leer_tamano_yml(_escribir_yml(tmp_path / "a.yml", (1280, 960))) == (1280, 960)
    assert cb.leer_tamano_yml(_escribir_yml(tmp_path / "b.yml")) is None
    assert cb.leer_tamano_yml(ITER4_DIR / "data" / "globalshutter.yml") == (640, 480)
    with pytest.raises(FileNotFoundError):
        cb.leer_tamano_yml(tmp_path / "no_existe.yml")


def test_tamano_distinto_del_pedido_para_y_libera() -> None:
    e = Escenario(cap=CapFalso(tamano=(1280, 960)), source=0, width=1600, height=1200)
    with pytest.raises(RuntimeError, match="1280x960 y el perfil pide 1600x1200"):
        e.backend.open()
    assert e.cap.llamadas[-1] == ("release",)


def test_sin_frames_en_el_warmup_para() -> None:
    e = Escenario(cap=CapFalso(frames=0), source=0)
    with pytest.raises(RuntimeError, match="no entrego ningun frame"):
        e.backend.open()
    assert e.cap.llamadas[-1] == ("release",)


def test_tamano_igual_al_yml_carga_K(tmp_path) -> None:
    yml = _escribir_yml(tmp_path / "k.yml", (640, 480))
    e = Escenario(source=0, calibration_file=yml)
    e.backend.open()
    K, dist = e.backend.get_intrinsics()
    assert K.shape == (3, 3) and dist.shape == (5,)


def test_tamano_distinto_del_yml_para(tmp_path) -> None:
    yml = _escribir_yml(tmp_path / "k.yml", (1280, 960))
    e = Escenario(source=0, calibration_file=yml)
    with pytest.raises(RuntimeError, match="640x480 y el .yml .* 1280x960"):
        e.backend.open()
    assert e.cap.llamadas[-1] == ("release",)


def test_yml_sin_tamano_avisa_y_sigue(tmp_path, capsys) -> None:
    yml = _escribir_yml(tmp_path / "k.yml")
    e = Escenario(source=0, calibration_file=yml)
    e.backend.open()
    assert "AVISO" in capsys.readouterr().out and e.backend._K is not None
