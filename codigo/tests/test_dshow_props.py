"""`camera.dshow_props` sin camara (meta 007, fase 7b · Las dos camaras a la vez en Windows, parte A).

La tabla `CONTROLES_COM` cubre los 10 de `controls.CONTROLES_CV2` en el mismo
orden y con los grupos y propiedades de `strmif.h`; `a_perfil` da lo mismo que
`controls.de_nativos_dshow` para los mismos valores crudos; `a_nativo` va y
vuelve; `CapaWindowsCOM.leer` con un dispositivo falso lee en unidades del
perfil, cierra siempre y no escribe nada; `aplicar` y `set` son la parte B
(NotImplementedError); `abrir_filtro` para con 0 o mas de 1 camara en el puerto
antes de tocar COM y fuera de Windows con OSError; y la suite niega
`abrir_filtro` (B34, conftest).
"""
from __future__ import annotations

import sys

import pytest

from camera import controls as ac
from camera import dshow_props as dp
from camera import uvc as cu

from .conftest import RealHardwareForbidden

PUERTO_1 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(3)"
PUERTO_2 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(4)"
# La funcion real, tomada al importar: la suite la sustituye en cada prueba (conftest, B34).
# Solo se llama aqui con casos que paran ANTES de tocar COM.
ABRIR_FILTRO_REAL = dp.abrir_filtro

# Lo que gs1 tenia en el P-7w (corta_gs1_tracker.txt, 2026-11-04), en crudo: (valor, flags).
CRUDOS_GS1 = {
    "exposure_ms": (-10, dp.FLAG_MANUAL), "gain": (11, dp.FLAG_MANUAL),
    "auto_white_balance": (4600, dp.FLAG_MANUAL), "brightness": (0, dp.FLAG_MANUAL),
    "contrast": (0, dp.FLAG_MANUAL), "saturation": (56, dp.FLAG_MANUAL),
    "sharpness": (0, dp.FLAG_MANUAL), "gamma": (110, dp.FLAG_MANUAL),
    "backlight": (54, dp.FLAG_MANUAL), "focus": (500, dp.FLAG_MANUAL),
}
LEIDOS_GS1 = {"exposure_ms": 0.9766, "gain": 11.0, "auto_white_balance": False, "brightness": 0.0,
              "contrast": 0.0, "saturation": 56.0, "sharpness": 0.0, "gamma": 110.0,
              "backlight": 54.0, "focus": 500.0}


class DispositivoFalso:
    """Un `Dispositivo` que recuerda lo que le piden; `crudos` es lo que 'tiene la camara'."""

    def __init__(self, crudos: dict[str, tuple[int, int]], sin: set[str] = frozenset()) -> None:
        self.valores = {dp.CONTROLES_COM[n]: v for n, v in crudos.items()}
        self.sin = {dp.CONTROLES_COM[n] for n in sin}
        self.gets: list[tuple[str, int]] = []
        self.sets: list[tuple] = []
        self.cerrado = 0

    def get(self, grupo: str, propiedad: int) -> dp.Lectura:
        self.gets.append((grupo, propiedad))
        if (grupo, propiedad) in self.sin:
            raise OSError(f"Get({propiedad}) fallo: HRESULT 0x80070490")
        valor, flags = self.valores[(grupo, propiedad)]
        return dp.Lectura(valor, bool(flags & dp.FLAG_AUTO), flags)

    def set(self, grupo: str, propiedad: int, valor: int, auto: bool) -> bool:
        self.sets.append((grupo, propiedad, valor, auto))
        return True

    def close(self) -> None:
        self.cerrado += 1


def _capa(dispositivo: DispositivoFalso) -> tuple[dp.CapaWindowsCOM, list[str]]:
    abiertos: list[str] = []

    def abrir(puerto: str):
        abiertos.append(puerto)
        return dispositivo
    return dp.CapaWindowsCOM(abrir=abrir), abiertos


# ----------------------------------------------------------------------------
# La tabla
# ----------------------------------------------------------------------------

def test_controles_com_son_los_10_de_cv2_en_el_mismo_orden() -> None:
    assert list(dp.CONTROLES_COM) == list(ac.CONTROLES_CV2)
    assert all(grupo in dp.GRUPOS for grupo, _ in dp.CONTROLES_COM.values())
    assert dp.CONTROLES_COM["exposure_ms"] == ("camara", 4) and dp.CONTROLES_COM["focus"] == ("camara", 6)
    assert dp.CONTROLES_COM["auto_white_balance"] == ("procamp", 7)
    assert dp.CONTROLES_COM["gain"] == ("procamp", 9) and dp.CONTROLES_COM["backlight"] == ("procamp", 8)
    assert dp.CONTROLES_COM["brightness"] == ("procamp", 0) and dp.CONTROLES_COM["gamma"] == ("procamp", 5)
    # Ninguna propiedad repetida dentro de su grupo.
    assert len(set(dp.CONTROLES_COM.values())) == 10


def test_constantes_de_strmif() -> None:
    assert dp.FLAG_AUTO == 1 and dp.FLAG_MANUAL == 2
    assert (dp.VT_QUERY_INTERFACE, dp.VT_GET_RANGE, dp.VT_SET, dp.VT_GET) == (0, 3, 4, 5)
    assert dp.VT_BIND_TO_OBJECT == 8 and cu.VT_BIND_TO_STORAGE == 9
    assert dp.PROCAMP["WhiteBalance"] == 7 and dp.PROCAMP["Gain"] == 9 and dp.CAMARA["Exposure"] == 4
    import uuid
    for iid in (dp.IID_IBASE_FILTER, dp.IID_IAM_VIDEO_PROC_AMP, dp.IID_IAM_CAMERA_CONTROL):
        uuid.UUID(iid)
    assert dp.IID_IAM_VIDEO_PROC_AMP != dp.IID_IAM_CAMERA_CONTROL


# ----------------------------------------------------------------------------
# Conversiones
# ----------------------------------------------------------------------------

def test_a_perfil_da_lo_mismo_que_de_nativos_dshow() -> None:
    """Los mismos valores crudos que leeria cv2 por DSHOW tienen que dar el mismo perfil (A0)."""
    nativos_cv2 = {n: float(v if n != "auto_white_balance" else (1 if f & dp.FLAG_AUTO else 0))
                   for n, (v, f) in CRUDOS_GS1.items()}
    esperado = ac.de_nativos_dshow(nativos_cv2)
    leido = {n: dp.a_perfil(n, dp.Lectura(v, bool(f & dp.FLAG_AUTO), f)) for n, (v, f) in CRUDOS_GS1.items()}
    assert leido == esperado == LEIDOS_GS1
    assert dp.a_perfil("exposure_ms", dp.Lectura(-8, False, 2)) == pytest.approx(3.9062)
    assert dp.a_perfil("auto_white_balance", dp.Lectura(4600, True, 1)) is True
    assert dp.a_perfil("auto_white_balance", dp.Lectura(4600, False, 2)) is False
    assert isinstance(dp.a_perfil("gain", dp.Lectura(11, False)), float)


def test_a_perfil_rechaza_lo_que_no_se_lee() -> None:
    with pytest.raises(ValueError, match="no se lee por COM"):
        dp.a_perfil("exposure_manual", dp.Lectura(1, False))


def test_a_nativo_ida_y_vuelta() -> None:
    assert dp.a_nativo("exposure_ms", 0.977) == (-10, False)
    assert dp.a_nativo("exposure_ms", 3.906) == (-8, False)
    assert dp.a_nativo("gain", 11.0) == (11, False) and dp.a_nativo("focus", 500) == (500, False)
    assert dp.a_nativo("auto_white_balance", True) == (0, True)
    assert dp.a_nativo("auto_white_balance", False) == (0, False)
    for n, v in LEIDOS_GS1.items():
        valor, auto = dp.a_nativo(n, v)
        assert dp.a_perfil(n, dp.Lectura(valor if n != "auto_white_balance" else 4600, auto)) == v


@pytest.mark.parametrize("nombre,valor", [("exposure_ms", 5.0), ("gain", 11.5), ("gain", "11"),
                                          ("gain", True), ("auto_white_balance", 1), ("iso", 1)])
def test_a_nativo_rechaza(nombre: str, valor) -> None:
    with pytest.raises(ValueError):
        dp.a_nativo(nombre, valor)


# ----------------------------------------------------------------------------
# CapaWindowsCOM con un dispositivo falso
# ----------------------------------------------------------------------------

def test_leer_en_unidades_del_perfil_y_cierra() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    leidos = capa.leer(PUERTO_1, list(ac.CONTROLES_CV2))
    assert leidos == LEIDOS_GS1
    assert abiertos == [PUERTO_1] and d.cerrado == 1 and d.sets == []
    assert d.gets == [dp.CONTROLES_COM[n] for n in ac.CONTROLES_CV2]     # en el orden del perfil


def test_leer_la_marca_sola_no_escribe_nada() -> None:
    """Lo que hace `WebcamBackend._comprobar_marca`: solo `focus`."""
    d = DispositivoFalso(CRUDOS_GS1)
    capa, _ = _capa(d)
    assert capa.leer(PUERTO_1, ["focus"]) == {"focus": 500.0}
    assert d.gets == [("camara", 6)] and d.sets == [] and d.cerrado == 1


def test_leer_nativos_trae_valor_auto_y_flags() -> None:
    d = DispositivoFalso({"auto_white_balance": (4600, dp.FLAG_AUTO), "gain": (11, dp.FLAG_MANUAL)})
    capa, _ = _capa(d)
    crudos = capa.leer_nativos(PUERTO_2, ["gain", "auto_white_balance"])
    assert crudos["auto_white_balance"] == dp.Lectura(4600, True, 1)
    assert crudos["gain"] == dp.Lectura(11, False, 2)
    assert capa.leer(PUERTO_2, ["auto_white_balance"]) == {"auto_white_balance": True}


def test_leer_cierra_si_get_revienta() -> None:
    d = DispositivoFalso(CRUDOS_GS1, sin={"gamma"})
    capa, _ = _capa(d)
    with pytest.raises(OSError, match="0x80070490"):
        capa.leer(PUERTO_1, ["gain", "gamma", "focus"])
    assert d.cerrado == 1 and d.sets == []


def test_leer_rechaza_nombres_antes_de_abrir() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    with pytest.raises(ValueError, match="no se leen por COM"):
        capa.leer(PUERTO_1, ["exposure_manual"])
    assert abiertos == [] and d.cerrado == 0


def test_aplicar_y_set_son_la_parte_b() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    with pytest.raises(NotImplementedError, match="parte B"):
        capa.aplicar(PUERTO_1, {"gain": 12})
    assert abiertos == []
    with pytest.raises(NotImplementedError, match="parte B"):
        dp._DispositivoCOM(0, None, None, None, None, False).set("procamp", 9, 12, False)


def test_capa_cumple_el_protocolo_de_controls() -> None:
    assert callable(getattr(dp.CapaWindowsCOM, "leer")) and callable(getattr(dp.CapaWindowsCOM, "aplicar"))
    import inspect
    assert list(inspect.signature(dp.CapaWindowsCOM.leer).parameters) == \
        list(inspect.signature(ac.CapaWindowsDShow.leer).parameters)
    assert list(inspect.signature(dp.CapaWindowsCOM.aplicar).parameters) == \
        list(inspect.signature(ac.CapaWindowsDShow.aplicar).parameters)


def test_la_capa_sin_falso_no_toca_com(monkeypatch) -> None:
    """B34: `abrir_filtro` esta negado a la suite; `CapaWindowsCOM()` a secas lo llamaria."""
    with pytest.raises(RealHardwareForbidden, match="dshow_props.abrir_filtro"):
        dp.CapaWindowsCOM().leer(PUERTO_1, ["focus"])
    # El tracker en Windows sigue con la capa de cv2: la parte A no cambia la cadena.
    assert isinstance(ac.capa_para_plataforma("win32"), ac.CapaWindowsDShow)


def test_dispositivo_com_close_es_idempotente() -> None:
    class Ole32:
        llamadas = 0

        def CoUninitialize(self):
            Ole32.llamadas += 1
    d = dp._DispositivoCOM(0, None, None, None, Ole32(), com_propio=True)
    d.close()
    d.close()
    assert Ole32.llamadas == 1
    with pytest.raises(ValueError, match="grupo"):
        d.get("otro", 0)
    with pytest.raises(OSError, match="no expone IAMCameraControl"):
        d.get("camara", 4)


# ----------------------------------------------------------------------------
# abrir_filtro: lo que para antes de COM
# ----------------------------------------------------------------------------

def _camaras(*puertos: str) -> list[cu.CamaraUVC]:
    return [cu.CamaraUVC(i, "Global Shutter Camera", f"\\\\?\\usb#vid_32e4&pid_0234&mi_00#{i}#x",
                         "32E4", "0234", str(i), ruta_puerto=p) for i, p in enumerate(puertos)]


def test_abrir_filtro_para_si_el_puerto_tiene_0_camaras() -> None:
    with pytest.raises(ValueError, match="no coincide con ninguna"):
        ABRIR_FILTRO_REAL(PUERTO_2, listar=lambda: _camaras(PUERTO_1))


def test_abrir_filtro_para_si_el_puerto_tiene_2_camaras() -> None:
    with pytest.raises(ValueError, match="coincide con 2 camaras"):
        ABRIR_FILTRO_REAL(PUERTO_1, listar=lambda: _camaras(PUERTO_1, PUERTO_1))


def test_abrir_filtro_fuera_de_windows_es_oserror(monkeypatch) -> None:
    monkeypatch.setattr(dp.sys, "platform", "linux")
    with pytest.raises(OSError, match="solo Windows"):
        ABRIR_FILTRO_REAL(PUERTO_1, listar=lambda: _camaras(PUERTO_1))


def test_abrir_filtro_por_defecto_lista_por_dshow() -> None:
    """Sin `listar`, enumera con `camera.uvc.listar_camaras_dshow` (negado en la suite: B34)."""
    with pytest.raises(RealHardwareForbidden, match="listar_camaras_dshow"):
        ABRIR_FILTRO_REAL(PUERTO_1)
    assert dp.abrir_filtro is not ABRIR_FILTRO_REAL      # la suite lo tiene sustituido


def test_el_modulo_no_importa_cv2_por_su_cuenta() -> None:
    """Lo COM va por ctypes y `camera.uvc`; las unidades, por `camera.controls` (una sola fuente)."""
    from pathlib import Path
    src = Path(dp.__file__).read_text(encoding="utf-8")
    assert "import cv2" not in src and "from camera import uvc" in src and "from camera import controls" in src
    assert sys.platform  # el modulo importa en cualquier sistema; solo abrir_filtro exige Windows
