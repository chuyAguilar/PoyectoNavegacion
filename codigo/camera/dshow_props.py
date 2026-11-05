# -*- coding: utf-8 -*-
"""
dshow_props.py -- Los controles de una camara UVC en Windows por COM, sobre el
filtro de captura de DirectShow, sin abrir video (meta 007, fase 7b, parte A).

Por que existe: `camera.controls.CapaWindowsDShow` lee y escribe los controles
con una apertura corta de `cv2.VideoCapture(i, CAP_DSHOW)`, que monta un grafo y
arranca un flujo de video con el formato por defecto de la camara. Con la otra
camara transmitiendo MJPG 1280x960 a ~88 fps por el mismo concentrador USB, esa
apertura falla («can't be used to capture by index», P-7w del 2026-11-04, P29) y
el tracker de la segunda camara no llega ni a leer la marca.

DirectShow expone los mismos controles en el propio filtro de captura:
`IAMVideoProcAmp` (brillo, contraste, saturacion, nitidez, gamma, balance de
blancos, contraluz, ganancia) e `IAMCameraControl` (exposicion y foco), con
`GetRange`, `Set` y `Get` y una bandera auto/manual. El filtro se obtiene del
mismo moniker que ya recorre `camera.uvc.listar_camaras_dshow`, con
`IMoniker::BindToObject(IBaseFilter)` en vez de `BindToStorage`: sin grafo, sin
pines conectados y sin flujo, asi que no reserva ancho de banda isocrono. Es la
misma via que usa OpenCV por dentro para `get`/`set` por DSHOW
(`cap_dshow.cpp`: `getVideoSettingFilter` y `getVideoSettingCamera`), solo que
sin arrancar el video.

Parte A (esta version): solo lectura. `abrir_filtro` y `CapaWindowsCOM.leer`;
`CapaWindowsCOM.aplicar` y la escritura del dispositivo COM llegan en la parte B
(ADR J7, si la parte A lo confirma) y hasta entonces levantan NotImplementedError.
La sonda (`diagnostics.probe_camera --capa com` y `--comparar-capas`) compara
esta lectura con la de `cv2` en vivo: la capa nueva tiene que leer lo mismo en
los 10 controles de cada camara (A0). El tracker sigue con `CapaWindowsDShow`.

Lo puro (la tabla `CONTROLES_COM`, `a_perfil`, `a_nativo` y `CapaWindowsCOM` con
un dispositivo falso) se prueba sin camara; lo COM es fino y se comprueba en vivo.
`tests/conftest.py` niega `abrir_filtro` a toda la suite (B34).

Valores de `strmif.h` del Windows SDK (Context7, 2026-11-04: `/opencv/opencv` y
el indice de Win32 `/websites/learn_microsoft_en-us_windows_win32_api` confirman
`IMoniker::BindToObject(pbc, pmkToLeft, riid, ppv)`; la documentacion de
`IAMVideoProcAmp`/`IAMCameraControl` no esta indexada): los IID, el orden de la
vtable (QueryInterface 0, AddRef 1, Release 2, GetRange 3, Set 4, Get 5), las
enumeraciones `VideoProcAmpProperty` y `CameraControlProperty` y las banderas
`*_Flags_Auto = 1`, `*_Flags_Manual = 2`. Si un valor estuviera mal, `Get`
devuelve un HRESULT de error y aqui se para (principio 7); A0 ata el resto.

Este modulo no usa cv2: las conversiones de unidades son las de
`camera.controls` (una sola fuente, principio 8).
"""
from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Callable, Protocol

from camera import uvc as camaras_uvc
from camera import controls as ajustes

# ----------------------------------------------------------------------------
# strmif.h
# ----------------------------------------------------------------------------
IID_IBASE_FILTER = "56a86895-0ad4-11ce-b03a-0020af0ba770"
IID_IAM_VIDEO_PROC_AMP = "c6e13360-30ac-11d0-a18c-00a0c9118956"
IID_IAM_CAMERA_CONTROL = "c6e13370-30ac-11d0-a18c-00a0c9118956"

# Vtables. IUnknown: 0 QueryInterface, 1 AddRef, 2 Release.
# IAMVideoProcAmp e IAMCameraControl: 3 GetRange, 4 Set, 5 Get.
# IMoniker (objidl.h): 8 BindToObject (9 es BindToStorage, el de camera.uvc).
VT_QUERY_INTERFACE = 0
VT_GET_RANGE = 3
VT_SET = 4
VT_GET = 5
VT_BIND_TO_OBJECT = 8

# VideoProcAmp_Flags_* y CameraControl_Flags_*: los mismos valores.
FLAG_AUTO = 0x0001
FLAG_MANUAL = 0x0002

# VideoProcAmpProperty (strmif.h).
PROCAMP: dict[str, int] = {
    "Brightness": 0, "Contrast": 1, "Hue": 2, "Saturation": 3, "Sharpness": 4,
    "Gamma": 5, "ColorEnable": 6, "WhiteBalance": 7, "BacklightCompensation": 8, "Gain": 9,
}
# CameraControlProperty (strmif.h).
CAMARA: dict[str, int] = {
    "Pan": 0, "Tilt": 1, "Roll": 2, "Zoom": 3, "Exposure": 4, "Iris": 5, "Focus": 6,
}

GRUPOS = ("procamp", "camara")
INTERFAZ_DE_GRUPO = {"procamp": "IAMVideoProcAmp", "camara": "IAMCameraControl"}

# Nombre del perfil -> (grupo, propiedad). Los 10 de controls.CONTROLES_CV2, en
# el mismo orden; `auto_white_balance` se lee y escribe por la bandera auto/manual
# de WhiteBalance (es lo que hace cv2 por DSHOW con CAP_PROP_AUTO_WB).
CONTROLES_COM: dict[str, tuple[str, int]] = {
    "exposure_ms": ("camara", CAMARA["Exposure"]),
    "gain": ("procamp", PROCAMP["Gain"]),
    "auto_white_balance": ("procamp", PROCAMP["WhiteBalance"]),
    "brightness": ("procamp", PROCAMP["Brightness"]),
    "contrast": ("procamp", PROCAMP["Contrast"]),
    "saturation": ("procamp", PROCAMP["Saturation"]),
    "sharpness": ("procamp", PROCAMP["Sharpness"]),
    "gamma": ("procamp", PROCAMP["Gamma"]),
    "backlight": ("procamp", PROCAMP["BacklightCompensation"]),
    "focus": ("camara", CAMARA["Focus"]),
}

PARTE_B = ("[dshow_props] la escritura por COM es la parte B de la fase 7b (meta 007); "
           "en la parte A la capa COM solo lee")


@dataclass
class Lectura:
    """Lo que devuelve `Get`: el valor crudo y si el control esta en automatico.

    `flags` son las banderas tal cual (1 auto, 2 manual); `auto` es `flags & 1`.
    """
    valor: int
    auto: bool
    flags: int = 0


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

def a_perfil(nombre: str, lectura: Lectura) -> float | bool:
    """Una lectura en las unidades del perfil: las mismas que `controls.de_nativos_dshow`.

    `exposure_ms` desde log2 de segundos (redondeada a 4 decimales, como alli);
    `auto_white_balance` desde la bandera auto; lo demas, el valor como float.
    """
    if nombre not in CONTROLES_COM:
        raise ValueError(f"'{nombre}' no se lee por COM; validos: {list(CONTROLES_COM)}")
    if nombre == "exposure_ms":
        return round(ajustes.dshow_a_exposicion_ms(lectura.valor), 4)
    if nombre == "auto_white_balance":
        return bool(lectura.auto)
    return float(lectura.valor)


def a_nativo(nombre: str, valor) -> tuple[int, bool]:
    """(valor, auto) para `Set`: la exposicion con `controls.exposicion_ms_a_dshow`.

    `auto_white_balance` da (0, True) o (0, False): quien escribe conserva el
    valor que tenga la camara y cambia solo la bandera (parte B). Todo lo demas
    va en manual con su valor entero.
    """
    if nombre not in CONTROLES_COM:
        raise ValueError(f"'{nombre}' no se escribe por COM; validos: {list(CONTROLES_COM)}")
    if nombre == "exposure_ms":
        return ajustes.exposicion_ms_a_dshow(float(valor)), False
    if nombre == "auto_white_balance":
        if not isinstance(valor, bool):
            raise ValueError(f"auto_white_balance tiene que ser true/false, no {valor!r}")
        return 0, valor
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"'{nombre}' tiene que ser un numero, no {valor!r}")
    entero = int(round(float(valor)))
    if abs(float(valor) - entero) > ajustes.TOLERANCIA:
        raise ValueError(f"'{nombre}' tiene que ser entero para COM, no {valor!r}")
    return entero, False


def nombres_validos(nombres: list[str]) -> list[str]:
    malos = [n for n in nombres if n not in CONTROLES_COM]
    if malos:
        raise ValueError(f"no se leen por COM: {malos}; validos: {list(CONTROLES_COM)}")
    return list(nombres)


# ----------------------------------------------------------------------------
# El dispositivo: lo que la capa necesita de la camara
# ----------------------------------------------------------------------------

class Dispositivo(Protocol):
    def get(self, grupo: str, propiedad: int) -> Lectura: ...

    def set(self, grupo: str, propiedad: int, valor: int, auto: bool) -> bool: ...

    def close(self) -> None: ...


class _DispositivoCOM:
    """El filtro de captura de una camara con sus dos interfaces; `close()` lo suelta todo."""

    def __init__(self, indice: int, filtro, procamp, camara, ole32, com_propio: bool) -> None:
        self.indice = indice
        self._filtro = filtro
        self._if = {"procamp": procamp, "camara": camara}
        self._ole32 = ole32
        self._com_propio = com_propio
        self._cerrado = False

    def get(self, grupo: str, propiedad: int) -> Lectura:
        obj = self._if.get(grupo)
        nombre = INTERFAZ_DE_GRUPO.get(grupo, grupo)
        if grupo not in self._if:
            raise ValueError(f"[dshow_props] grupo {grupo!r}; validos: {GRUPOS}")
        if not obj:
            raise OSError(f"[dshow_props] la camara no expone {nombre}")
        valor = ctypes.c_long(0)
        flags = ctypes.c_long(0)
        fn = camaras_uvc._metodo(obj, VT_GET, ctypes.c_long, ctypes.c_long,
                                 ctypes.POINTER(ctypes.c_long), ctypes.POINTER(ctypes.c_long))
        hr = fn(obj, int(propiedad), ctypes.byref(valor), ctypes.byref(flags))
        camaras_uvc._hr_ok(hr, f"{nombre}::Get({propiedad})")
        return Lectura(int(valor.value), bool(flags.value & FLAG_AUTO), int(flags.value))

    def set(self, grupo: str, propiedad: int, valor: int, auto: bool) -> bool:
        raise NotImplementedError(PARTE_B)

    def close(self) -> None:
        if self._cerrado:
            return
        self._cerrado = True
        for clave in ("procamp", "camara"):
            camaras_uvc._release(self._if[clave])
            self._if[clave] = None
        camaras_uvc._release(self._filtro)
        self._filtro = None
        if self._com_propio:
            self._ole32.CoUninitialize()


def _moniker_de_indice(indice: int, ole32, oleaut32):
    """El moniker `indice` de CLSID_VideoInputDeviceCategory, en el orden de DSHOW, y su DevicePath."""
    dev_enum = ctypes.c_void_p()
    clsid = camaras_uvc._guid(camaras_uvc.CLSID_SYSTEM_DEVICE_ENUM)
    iid = camaras_uvc._guid(camaras_uvc.IID_ICREATE_DEV_ENUM)
    camaras_uvc._hr_ok(
        ole32.CoCreateInstance(ctypes.byref(clsid), None, camaras_uvc.CLSCTX_INPROC_SERVER,
                               ctypes.byref(iid), ctypes.byref(dev_enum)),
        "CoCreateInstance(SystemDeviceEnum)")
    enum_mk = ctypes.c_void_p()
    try:
        categoria = camaras_uvc._guid(camaras_uvc.CLSID_VIDEO_INPUT_DEVICE_CATEGORY)
        crear = camaras_uvc._metodo(dev_enum, camaras_uvc.VT_CREATE_CLASS_ENUMERATOR, ctypes.c_long,
                                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32)
        hr = crear(dev_enum, ctypes.byref(categoria), ctypes.byref(enum_mk), 0)
        camaras_uvc._hr_ok(hr, "ICreateDevEnum::CreateClassEnumerator")
        if hr == camaras_uvc.S_FALSE or not enum_mk:
            raise OSError("[dshow_props] DirectShow no enumera ninguna camara de video")
        siguiente = camaras_uvc._metodo(enum_mk, camaras_uvc.VT_ENUM_NEXT, ctypes.c_long, ctypes.c_ulong,
                                        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong))
        i = 0
        while True:
            moniker = ctypes.c_void_p()
            traidos = ctypes.c_ulong(0)
            hr = siguiente(enum_mk, 1, ctypes.byref(moniker), ctypes.byref(traidos))
            camaras_uvc._hr_ok(hr, "IEnumMoniker::Next")
            if hr != camaras_uvc.S_OK or traidos.value != 1 or not moniker:
                raise OSError(f"[dshow_props] DirectShow enumera {i} camara(s): no hay indice {indice}")
            if i == indice:
                try:
                    _nombre, enlace = camaras_uvc._propiedades_moniker(moniker, oleaut32)
                except OSError:
                    camaras_uvc._release(moniker)
                    raise
                return moniker, enlace
            camaras_uvc._release(moniker)
            i += 1
    finally:
        camaras_uvc._release(enum_mk)
        camaras_uvc._release(dev_enum)


def _query_interface(obj, iid_txt: str, que: str):
    """QueryInterface; None si la camara no expone esa interfaz (E_NOINTERFACE), OSError si otro error."""
    iid = camaras_uvc._guid(iid_txt)
    salida = ctypes.c_void_p()
    qi = camaras_uvc._metodo(obj, VT_QUERY_INTERFACE, ctypes.c_long, ctypes.c_void_p,
                             ctypes.POINTER(ctypes.c_void_p))
    hr = qi(obj, ctypes.byref(iid), ctypes.byref(salida))
    if (hr & 0xFFFFFFFF) == 0x80004002:          # E_NOINTERFACE
        return None
    camaras_uvc._hr_ok(hr, f"QueryInterface({que})")
    return salida


def abrir_filtro(puerto: str, listar: Callable[[], list] | None = None) -> Dispositivo:
    """El filtro de captura de la unica camara DSHOW del puerto, con sus dos interfaces.

    `listar()` da las camaras DSHOW con `ruta_puerto` (por defecto
    `camera.uvc.listar_camaras_dshow`; se inyecta en las pruebas). ValueError si
    el puerto tiene 0 o mas de 1 camara (antes de tocar COM); OSError fuera de
    Windows o si COM falla, con el HRESULT. No construye grafo ni abre video.
    El moniker del indice se vuelve a enumerar y su DevicePath tiene que ser el
    de la camara listada: si la enumeracion cambio entre medias, se para.
    """
    listar = listar if listar is not None else camaras_uvc.listar_camaras_dshow
    camaras = listar()
    indice = camaras_uvc.resolver_indice(puerto, camaras)
    esperado = next(c.enlace for c in camaras if c.indice == indice)
    if sys.platform != "win32":
        raise OSError("[dshow_props] solo Windows (DirectShow)")

    ole32 = camaras_uvc._ole32()
    oleaut32 = ctypes.WinDLL("oleaut32")
    oleaut32.VariantClear.restype = ctypes.c_long
    oleaut32.VariantClear.argtypes = [ctypes.c_void_p]
    com_propio = camaras_uvc._com_iniciar(ole32)
    filtro = None
    try:
        moniker, enlace = _moniker_de_indice(indice, ole32, oleaut32)
        try:
            if (enlace or "").strip().lower() != (esperado or "").strip().lower():
                raise OSError(f"[dshow_props] la enumeracion DSHOW cambio: el indice {indice} ya no es "
                              f"la camara del puerto {puerto} ({enlace!r} frente a {esperado!r})")
            iid = camaras_uvc._guid(IID_IBASE_FILTER)
            salida = ctypes.c_void_p()
            bind = camaras_uvc._metodo(moniker, VT_BIND_TO_OBJECT, ctypes.c_long, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            camaras_uvc._hr_ok(bind(moniker, None, None, ctypes.byref(iid), ctypes.byref(salida)),
                               "IMoniker::BindToObject(IBaseFilter)")
            filtro = salida
        finally:
            camaras_uvc._release(moniker)
        procamp = _query_interface(filtro, IID_IAM_VIDEO_PROC_AMP, "IAMVideoProcAmp")
        camara = _query_interface(filtro, IID_IAM_CAMERA_CONTROL, "IAMCameraControl")
        return _DispositivoCOM(indice, filtro, procamp, camara, ole32, com_propio)
    except BaseException:
        camaras_uvc._release(filtro)
        if com_propio:
            ole32.CoUninitialize()
        raise


# ----------------------------------------------------------------------------
# La capa (cumple controls.CapaAjustes; en la parte A, solo `leer`)
# ----------------------------------------------------------------------------

class CapaWindowsCOM:
    """Lee los controles por COM sobre el filtro de captura, sin abrir video.

    `abrir(puerto)` da un `Dispositivo`; se inyecta en las pruebas (por defecto
    `abrir_filtro`, que la suite niega). Mismo contrato de `leer` que
    `CapaWindowsDShow`: las unidades del perfil, y ValueError para un nombre que
    no se lee. `aplicar` es la parte B y por ahora levanta NotImplementedError.
    """

    def __init__(self, abrir: Callable[[str], Dispositivo] | None = None) -> None:
        self._abrir = abrir if abrir is not None else abrir_filtro

    def leer_nativos(self, puerto: str, nombres: list[str]) -> dict[str, Lectura]:
        """Las lecturas crudas (valor, auto, flags) de la camara del puerto; libera el filtro."""
        nombres = nombres_validos(nombres)
        dispositivo = self._abrir(puerto)
        try:
            return {n: dispositivo.get(*CONTROLES_COM[n]) for n in nombres}
        finally:
            dispositivo.close()

    def leer(self, puerto: str, nombres: list[str]) -> dict[str, float]:
        """Lo que la camara del puerto tiene hoy, en las unidades del perfil."""
        return {n: a_perfil(n, l) for n, l in self.leer_nativos(puerto, nombres).items()}

    def aplicar(self, puerto: str, controls: dict, *, forzar: bool = False) -> dict:
        raise NotImplementedError(PARTE_B)
