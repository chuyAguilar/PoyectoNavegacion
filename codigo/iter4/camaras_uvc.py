# -*- coding: utf-8 -*-
"""
camaras_uvc.py -- Enumera las camaras de video por Media Foundation y por
DirectShow, con la ruta fisica de su puerto USB (meta 002, fases 1 y 2a).

Da, por cada camara, el indice (el mismo orden que usa cv2.CAP_MSMF o
cv2.CAP_DSHOW, segun la lista), el nombre y el enlace simbolico; de este saca
VID, PID e instancia USB, y por CfgMgr32 la ruta fisica del puerto
(DEVPKEY_Device_LocationPaths del nodo USB, p. ej.
`PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)`) y su ubicacion
(`Port_#0002.Hub_#0001`). El perfil identifica cada camara SVPRO por la ruta
del puerto (clarify.md P1 y revision 2 del plan): la instancia no sirve (la
primera conectada toma la de la serie en cualquier puerto) y la serie es
`01.00.00` en las dos.

Sin dependencia nueva: ctypes sobre ole32, mfplat, mf, cfgmgr32 y oleaut32.
No abre ninguna camara: solo enumera.

Por que el orden coincide con OpenCV: el backend MSMF de OpenCV abre la camara
`index` tomando el elemento `index` de MFEnumDeviceSources con el atributo
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = VIDCAP_GUID (listar_camaras_msmf); el
backend DSHOW toma el elemento `index` de ICreateDevEnum sobre
CLSID_VideoInputDeviceCategory (listar_camaras_dshow). Los dos se verifican en
vivo tapando una lente (sondear_camara.py --verificar-orden --backend ...).

Al importarse apaga la aceleracion por hardware de MSMF
(OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0, con setdefault: un valor puesto a
mano se respeta; solo en Windows). Fase 2b, correccion tras la sesion en vivo
del 2026-10-21/22: con ella encendida la apertura MSMF + set() tarda 43-51 s;
apagada, 3.6-4.0 s, con los mismos ~90 fps de captura a 640x480 y 1280x960.
Context7 (2026-10-22, OpenCV 4.13, env_reference): la variable (bool, por
defecto true) "may slow down camera probing process"; en Python va en
os.environ ANTES de `import cv2` ("variables set after this may not have
effect"). Comprobado con el cv2 4.11 del venv: cv2.pyd lleva el CRT estatico
(no importa ningun api-ms-win-crt-*.dll) y copia el entorno al cargarse: una
variable de OpenCV que se lee tarde (OPENCV_IO_ENABLE_OPENEXR) puesta antes de
`import cv2` vale y puesta despues no. Por eso este modulo (que no importa
cv2) se importa antes de cv2 en quien abre MSMF; si cv2 ya estaba cargado, la
variable no llega y describir_aceleracion_msmf() lo dice.

Uso (solo lista; no necesita argumentos):
    python iter4\\camaras_uvc.py
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
import uuid
from dataclasses import dataclass

# ----------------------------------------------------------------------------
# Aceleracion por hardware de MSMF (DXVA): apagada antes de que cv2 se cargue.
# ----------------------------------------------------------------------------
VAR_ACELERACION_MSMF = "OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"
# Como los lee OpenCV (utils::getConfigurationParameterBool).
_BOOL_FALSO = ("0", "false", "off")
_BOOL_CIERTO = ("1", "true", "on")


def apagar_aceleracion_msmf(environ=None, plataforma: str = sys.platform,
                            cv2_cargado: bool | None = None) -> dict:
    """Pone VAR_ACELERACION_MSMF=0 con setdefault (solo en Windows) y dice lo que vera cv2.

    Devuelve {"valor", "previo", "puesta_aqui", "cv2_cargado", "efectiva"}:
    `efectiva` es "apagada", "encendida", "no aplica" (fuera de Windows) o
    "desconocida" (valor que OpenCV no reconoce). Si cv2 ya estaba cargado y la
    variable no venia del entorno, cv2 no la ve: queda "encendida".
    """
    environ = os.environ if environ is None else environ
    cv2_cargado = ("cv2" in sys.modules) if cv2_cargado is None else bool(cv2_cargado)
    previo = environ.get(VAR_ACELERACION_MSMF)
    estado = {"valor": previo, "previo": previo, "puesta_aqui": False,
              "cv2_cargado": cv2_cargado, "efectiva": "no aplica"}
    if plataforma != "win32":
        return estado
    environ.setdefault(VAR_ACELERACION_MSMF, "0")
    estado["valor"] = environ.get(VAR_ACELERACION_MSMF)
    estado["puesta_aqui"] = previo is None
    visto = None if (estado["puesta_aqui"] and cv2_cargado) else estado["valor"]
    if visto is None:
        estado["efectiva"] = "encendida"          # el valor por defecto de OpenCV
    elif visto.strip().lower() in _BOOL_FALSO:
        estado["efectiva"] = "apagada"
    elif visto.strip().lower() in _BOOL_CIERTO:
        estado["efectiva"] = "encendida"
    else:
        estado["efectiva"] = "desconocida"
    return estado


def describir_aceleracion_msmf(estado: dict | None = None) -> str:
    """Una linea para el log: si la aceleracion HW de MSMF esta apagada o encendida, y por que."""
    e = ACELERACION_MSMF if estado is None else estado
    var = f"{VAR_ACELERACION_MSMF}={e['valor']}"
    if e["efectiva"] == "no aplica":
        return "Aceleracion HW de MSMF: no aplica (MSMF solo existe en Windows)"
    if e["efectiva"] == "apagada":
        origen = "puesta por el codigo" if e["puesta_aqui"] else "del entorno"
        return f"Aceleracion HW de MSMF apagada ({var}, {origen})"
    if e["efectiva"] == "desconocida":
        return (f"Aceleracion HW de MSMF: valor no reconocido por OpenCV ({var}); "
                f"usa 0 (apagada) o 1 (encendida)")
    if e["puesta_aqui"] and e["cv2_cargado"]:
        return (f"Aceleracion HW de MSMF ENCENDIDA: cv2 se cargo antes de poner "
                f"{VAR_ACELERACION_MSMF}=0 y no la ve (abrir tarda ~45 s en vez de ~4 s); "
                f"lanza con $env:{VAR_ACELERACION_MSMF}='0' o importa camaras_uvc antes que cv2")
    return (f"Aceleracion HW de MSMF encendida ({var}, del entorno): abrir tarda ~45 s "
            f"en vez de ~4 s")


ACELERACION_MSMF: dict = apagar_aceleracion_msmf()

# ----------------------------------------------------------------------------
# GUIDs y constantes. Valores de los encabezados del Windows SDK:
#   mfidl.h : MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
#             MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID,
#             MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME,
#             MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK
#   mfapi.h : MF_VERSION = (MF_SDK_VERSION << 16) | MF_API_VERSION = 0x00020070,
#             MFSTARTUP_FULL = 0
#   objbase.h: COINIT_MULTITHREADED = 0, CLSCTX_INPROC_SERVER = 1
# El SDK no esta instalado en BigDaddy (2026-10-20): los valores se comprueban
# en ejecucion (si un GUID estuviera mal, MFEnumDeviceSources o
# GetAllocatedString devuelven un HRESULT de error y aqui se para).
# ----------------------------------------------------------------------------
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = "c60ac5fe-252a-478f-a0ef-bc8fa5f7cad3"
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID = "8ac3587a-4ae7-42d8-99e0-0a6013eef90f"
MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME = "60d0e559-52f8-4fa2-bbce-acdb34a8ec01"
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK = "58f0aad8-22bf-4f8a-bb3d-d2c4978c6e2f"

MF_VERSION = 0x00020070
MFSTARTUP_FULL = 0
COINIT_MULTITHREADED = 0x0
CLSCTX_INPROC_SERVER = 0x1
RPC_E_CHANGED_MODE = 0x80010106
S_OK = 0
S_FALSE = 1

# Indices de la vtable (mfobjects.h, IMFAttributesVtbl; IMFActivate hereda de
# IMFAttributes, asi que los mismos indices valen para el IMFActivate):
#   0 QueryInterface, 1 AddRef, 2 Release, 3 GetItem, 4 GetItemType,
#   5 CompareItem, 6 Compare, 7 GetUINT32, 8 GetUINT64, 9 GetDouble,
#   10 GetGUID, 11 GetStringLength, 12 GetString, 13 GetAllocatedString,
#   14 GetBlobSize, 15 GetBlob, 16 GetAllocatedBlob, 17 GetUnknown,
#   18 SetItem, 19 DeleteItem, 20 DeleteAllItems, 21 SetUINT32,
#   22 SetUINT64, 23 SetDouble, 24 SetGUID, ...
VT_RELEASE = 2
VT_GET_ALLOCATED_STRING = 13
VT_SET_GUID = 24

# DirectShow (fase 2a). GUIDs de uuids.h / strmif.h / ocidl.h / oaidl.h; no
# contrastados por Context7 (2026-10-21: el indice de Win32 devolvio
# IMoniker::BindToStorage, IEnumMoniker::Next e IPropertyBag::Read, no
# ICreateDevEnum): se verifican en vivo tapando una lente.
CLSID_SYSTEM_DEVICE_ENUM = "62be5d10-60eb-11d0-bd3b-00a0c911ce86"
IID_ICREATE_DEV_ENUM = "29840822-5b84-11d0-bd3b-00a0c911ce86"
CLSID_VIDEO_INPUT_DEVICE_CATEGORY = "860bb310-5d01-11d0-bd3b-00a0c911ce86"
IID_IPROPERTY_BAG = "55272a00-42cb-11ce-8135-00aa004bb851"
# Vtables: ICreateDevEnum (strmif.h): 3 CreateClassEnumerator.
# IEnumMoniker (objidl.h): 3 Next, 4 Skip, 5 Reset, 6 Clone.
# IMoniker (objidl.h): IUnknown 0-2, IPersist 3 GetClassID, IPersistStream
#   4 IsDirty, 5 Load, 6 Save, 7 GetSizeMax, IMoniker 8 BindToObject,
#   9 BindToStorage, ...
# IPropertyBag (oaidl.h): 3 Read, 4 Write.
VT_CREATE_CLASS_ENUMERATOR = 3
VT_ENUM_NEXT = 3
VT_BIND_TO_STORAGE = 9
VT_BAG_READ = 3
VT_BSTR = 8

# CfgMgr32 (fase 2a). DEVPROPKEY de devpkey.h (fmtid, pid):
#   DEVPKEY_Device_InstanceId     {78c34fc8-104a-4aca-9ea4-524d52996e57}, 256
#   DEVPKEY_Device_LocationInfo   {a45c254e-df1c-4efd-8020-67d146a850e0}, 15
#   DEVPKEY_Device_LocationPaths  {a45c254e-df1c-4efd-8020-67d146a850e0}, 37
# Tipos (devpropdef.h): DEVPROP_TYPE_STRING = 0x12,
#   DEVPROP_TYPE_STRING_LIST = DEVPROP_TYPE_STRING | DEVPROP_TYPEMOD_LIST (0x2000).
# CONFIGRET (cfgmgr32.h): CR_SUCCESS = 0, CR_BUFFER_SMALL = 0x1A.
# Context7 (/microsoftdocs/windows-driver-docs, 2026-10-21): la cadena
# CM_Get_Device_Interface_Property(InstanceId) -> CM_Locate_DevNode ->
# CM_Get_DevNode_Property con el bucle por CR_BUFFER_SMALL es la del ejemplo
# oficial; los valores de las DEVPKEY no vienen en Context7 y se comprueban en
# ejecucion (un CONFIGRET distinto de CR_SUCCESS para).
DEVPKEY_DEVICE_INSTANCE_ID = ("78c34fc8-104a-4aca-9ea4-524d52996e57", 256)
DEVPKEY_DEVICE_LOCATION_INFO = ("a45c254e-df1c-4efd-8020-67d146a850e0", 15)
DEVPKEY_DEVICE_LOCATION_PATHS = ("a45c254e-df1c-4efd-8020-67d146a850e0", 37)
DEVPROP_TYPE_STRING = 0x12
DEVPROP_TYPE_STRING_LIST = 0x2012
CR_SUCCESS = 0
CR_BUFFER_SMALL = 0x1A
CM_LOCATE_DEVNODE_NORMAL = 0


@dataclass
class CamaraUVC:
    """Una camara tal como la enumera Media Foundation o DirectShow.

    `ruta_puerto`, `ubicacion` e `instancia_usb` (fase 2a) son del nodo USB
    (el padre del `MI_00` en un dispositivo compuesto); None si no es USB o
    no se pidieron.
    """
    indice: int
    nombre: str
    enlace: str
    vid: str | None
    pid: str | None
    instancia: str | None
    ruta_puerto: str | None = None
    ubicacion: str | None = None
    instancia_usb: str | None = None


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

# \\?\usb#vid_32e4&pid_0234&mi_00#6&325db0ba&1&0000#{e5323777-...}\global
_RE_USB = re.compile(
    r"usb#vid_([0-9a-f]{4})&pid_([0-9a-f]{4})[^#]*#([^#]+)#",
    re.IGNORECASE,
)


def extraer_ids(enlace: str) -> tuple[str | None, str | None, str | None]:
    """VID, PID e instancia (en mayusculas) desde el enlace simbolico.

    Para un enlace que no es USB (camara virtual, `root#`, `swd#`), devuelve
    (None, None, None).
    """
    if not enlace:
        return None, None, None
    m = _RE_USB.search(enlace)
    if m is None:
        return None, None, None
    return m.group(1).upper(), m.group(2).upper(), m.group(3).upper()


def primera_ruta(multi_sz: str | None) -> str | None:
    """El primer elemento no vacio de una DEVPROP_TYPE_STRING_LIST (separada por NUL)."""
    if not multi_sz:
        return None
    for trozo in multi_sz.split("\0"):
        if trozo.strip():
            return trozo.strip()
    return None


def resolver_indice(puerto: str, camaras: list[CamaraUVC]) -> int:
    """El indice de la unica camara cuya `ruta_puerto` es igual a `puerto`.

    Igualdad sin distinguir mayusculas, no subcadena: la ruta de un puerto es
    prefijo de la de un puerto de un hub colgado de el. ValueError si ninguna
    o mas de una coinciden (principio 7: no se adivina cual abrir).
    """
    if not puerto or not str(puerto).strip():
        raise ValueError("puerto vacio")
    buscado = str(puerto).strip().upper()
    hallados = [c for c in camaras
                if c.ruta_puerto is not None and c.ruta_puerto.strip().upper() == buscado]
    if len(hallados) == 1:
        return hallados[0].indice
    lista = "; ".join(f"{c.indice}: {c.nombre} [{c.ruta_puerto}]" for c in camaras) \
        or "ninguna camara enumerada"
    if not hallados:
        raise ValueError(f"el puerto '{puerto}' no coincide con ninguna camara "
                         f"conectada ({lista})")
    raise ValueError(f"el puerto '{puerto}' coincide con {len(hallados)} camaras "
                     f"({lista}); no puede ser")


# ----------------------------------------------------------------------------
# COM por ctypes (solo Windows)
# ----------------------------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


class DEVPROPKEY(ctypes.Structure):
    """devpropdef.h: {GUID fmtid; DEVPROPID pid;}."""
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]


class VARIANT(ctypes.Structure):
    """oaidl.h en x64: vt + 3 reservados (8 bytes) + union de 16 bytes (24 en total)."""
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort),
                ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("bstrVal", ctypes.c_void_p), ("r4", ctypes.c_void_p)]


def _guid(texto: str) -> GUID:
    u = uuid.UUID(texto)
    g = GUID()
    g.Data1 = u.time_low
    g.Data2 = u.time_mid
    g.Data3 = u.time_hi_version
    for i, b in enumerate(u.bytes[8:16]):
        g.Data4[i] = b
    return g


def _hr_ok(hr: int, que: str) -> None:
    if hr < 0:
        raise OSError(f"[camaras_uvc] {que} fallo: HRESULT 0x{hr & 0xFFFFFFFF:08X}")


def _metodo(obj, indice: int, restype, *argtypes):
    """La funcion `indice` de la vtable del objeto COM `obj` (c_void_p)."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtbl[indice])


def _release(obj) -> None:
    if obj:
        _metodo(obj, VT_RELEASE, ctypes.c_ulong)(obj)


def _ole32():
    ole32 = ctypes.WinDLL("ole32")
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole32.CoUninitialize.restype = None
    ole32.CoTaskMemFree.restype = None
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    return ole32


def _com_iniciar(ole32) -> bool:
    """CoInitializeEx; True si este hilo lo inicializo (y hay que cerrarlo)."""
    hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    # S_OK (0) o S_FALSE (1): este hilo lo inicializo y hay que cerrarlo.
    # RPC_E_CHANGED_MODE: COM ya estaba en otro modo; se usa tal cual.
    com_propio = hr in (S_OK, S_FALSE)
    if not com_propio and (hr & 0xFFFFFFFF) != RPC_E_CHANGED_MODE:
        _hr_ok(hr, "CoInitializeEx")
    return com_propio


# ----------------------------------------------------------------------------
# Enumeracion por Media Foundation
# ----------------------------------------------------------------------------

def _cadena(activate, guid_txt: str, ole32) -> str:
    valor = ctypes.c_wchar_p()
    largo = ctypes.c_uint32(0)
    clave = _guid(guid_txt)
    fn = _metodo(activate, VT_GET_ALLOCATED_STRING, ctypes.c_long,
                 ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p),
                 ctypes.POINTER(ctypes.c_uint32))
    hr = fn(activate, ctypes.byref(clave), ctypes.byref(valor), ctypes.byref(largo))
    _hr_ok(hr, f"GetAllocatedString({guid_txt})")
    try:
        return valor.value or ""
    finally:
        ole32.CoTaskMemFree(valor)


def listar_camaras_msmf(con_puerto: bool = True) -> list[CamaraUVC]:
    """Las camaras de video de Media Foundation, en el orden del indice MSMF.

    Con `con_puerto`, cada camara USB lleva su ruta de puerto (datos_puerto).
    Falla fuerte (OSError) si COM, Media Foundation o CfgMgr32 fallan. No
    abre ninguna camara.
    """
    if sys.platform != "win32":
        raise OSError("[camaras_uvc] solo Windows (Media Foundation)")

    ole32 = _ole32()
    mfplat = ctypes.WinDLL("mfplat")
    mf = ctypes.WinDLL("mf")
    mfplat.MFStartup.restype = ctypes.c_long
    mfplat.MFStartup.argtypes = [ctypes.c_ulong, ctypes.c_uint32]
    mfplat.MFShutdown.restype = ctypes.c_long
    mfplat.MFCreateAttributes.restype = ctypes.c_long
    mfplat.MFCreateAttributes.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32]
    mf.MFEnumDeviceSources.restype = ctypes.c_long
    mf.MFEnumDeviceSources.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
        ctypes.POINTER(ctypes.c_uint32)]

    com_propio = _com_iniciar(ole32)
    try:
        _hr_ok(mfplat.MFStartup(MF_VERSION, MFSTARTUP_FULL), "MFStartup")
        try:
            camaras = _enumerar(ole32, mfplat, mf)
        finally:
            mfplat.MFShutdown()
    finally:
        if com_propio:
            ole32.CoUninitialize()
    if con_puerto:
        _anotar_puertos(camaras)
    return camaras


def _enumerar(ole32, mfplat, mf) -> list[CamaraUVC]:
    attrs = ctypes.c_void_p()
    _hr_ok(mfplat.MFCreateAttributes(ctypes.byref(attrs), 1), "MFCreateAttributes")
    arreglo = ctypes.POINTER(ctypes.c_void_p)()
    n = ctypes.c_uint32(0)
    try:
        clave = _guid(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE)
        valor = _guid(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID)
        set_guid = _metodo(attrs, VT_SET_GUID, ctypes.c_long,
                           ctypes.c_void_p, ctypes.c_void_p)
        _hr_ok(set_guid(attrs, ctypes.byref(clave), ctypes.byref(valor)),
               "IMFAttributes::SetGUID")
        _hr_ok(mf.MFEnumDeviceSources(attrs, ctypes.byref(arreglo), ctypes.byref(n)),
               "MFEnumDeviceSources")
        camaras = []
        try:
            for i in range(n.value):
                act = ctypes.c_void_p(arreglo[i])
                nombre = _cadena(act, MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME, ole32)
                enlace = _cadena(act, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK,
                                 ole32)
                vid, pid, inst = extraer_ids(enlace)
                camaras.append(CamaraUVC(i, nombre, enlace, vid, pid, inst))
        finally:
            for i in range(n.value):
                _release(ctypes.c_void_p(arreglo[i]))
            if arreglo:
                ole32.CoTaskMemFree(ctypes.cast(arreglo, ctypes.c_void_p))
        return camaras
    finally:
        _release(attrs)


# ----------------------------------------------------------------------------
# Enumeracion por DirectShow (fase 2a)
# ----------------------------------------------------------------------------

def listar_camaras_dshow(con_puerto: bool = True) -> list[CamaraUVC]:
    """Las camaras de video de DirectShow, en el orden del indice DSHOW de OpenCV.

    ICreateDevEnum -> CreateClassEnumerator(CLSID_VideoInputDeviceCategory) ->
    IEnumMoniker::Next -> IMoniker::BindToStorage(IPropertyBag) ->
    Read("FriendlyName") y Read("DevicePath"). `enlace` es el DevicePath.
    Falla fuerte (OSError) si COM falla. No abre ninguna camara.
    """
    if sys.platform != "win32":
        raise OSError("[camaras_uvc] solo Windows (DirectShow)")

    ole32 = _ole32()
    oleaut32 = ctypes.WinDLL("oleaut32")
    oleaut32.VariantClear.restype = ctypes.c_long
    oleaut32.VariantClear.argtypes = [ctypes.c_void_p]

    com_propio = _com_iniciar(ole32)
    try:
        camaras = _enumerar_dshow(ole32, oleaut32)
    finally:
        if com_propio:
            ole32.CoUninitialize()
    if con_puerto:
        _anotar_puertos(camaras)
    return camaras


def _enumerar_dshow(ole32, oleaut32) -> list[CamaraUVC]:
    dev_enum = ctypes.c_void_p()
    clsid = _guid(CLSID_SYSTEM_DEVICE_ENUM)
    iid = _guid(IID_ICREATE_DEV_ENUM)
    _hr_ok(ole32.CoCreateInstance(ctypes.byref(clsid), None, CLSCTX_INPROC_SERVER,
                                  ctypes.byref(iid), ctypes.byref(dev_enum)),
           "CoCreateInstance(SystemDeviceEnum)")
    enum_mk = ctypes.c_void_p()
    try:
        categoria = _guid(CLSID_VIDEO_INPUT_DEVICE_CATEGORY)
        crear = _metodo(dev_enum, VT_CREATE_CLASS_ENUMERATOR, ctypes.c_long,
                        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32)
        hr = crear(dev_enum, ctypes.byref(categoria), ctypes.byref(enum_mk), 0)
        _hr_ok(hr, "ICreateDevEnum::CreateClassEnumerator")
        if hr == S_FALSE or not enum_mk:
            return []    # ninguna camara en la categoria
        siguiente = _metodo(enum_mk, VT_ENUM_NEXT, ctypes.c_long, ctypes.c_ulong,
                            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong))
        camaras = []
        i = 0
        while True:
            moniker = ctypes.c_void_p()
            traidos = ctypes.c_ulong(0)
            hr = siguiente(enum_mk, 1, ctypes.byref(moniker), ctypes.byref(traidos))
            _hr_ok(hr, "IEnumMoniker::Next")
            if hr != S_OK or traidos.value != 1 or not moniker:
                break
            try:
                nombre, enlace = _propiedades_moniker(moniker, oleaut32)
            finally:
                _release(moniker)
            vid, pid, inst = extraer_ids(enlace)
            camaras.append(CamaraUVC(i, nombre, enlace, vid, pid, inst))
            i += 1
        return camaras
    finally:
        _release(enum_mk)
        _release(dev_enum)


def _propiedades_moniker(moniker, oleaut32) -> tuple[str, str]:
    """FriendlyName y DevicePath del IPropertyBag de un moniker de DirectShow."""
    bag = ctypes.c_void_p()
    iid = _guid(IID_IPROPERTY_BAG)
    bind = _metodo(moniker, VT_BIND_TO_STORAGE, ctypes.c_long, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    _hr_ok(bind(moniker, None, None, ctypes.byref(iid), ctypes.byref(bag)),
           "IMoniker::BindToStorage(IPropertyBag)")
    leer = _metodo(bag, VT_BAG_READ, ctypes.c_long, ctypes.c_wchar_p,
                   ctypes.POINTER(VARIANT), ctypes.c_void_p)
    try:
        valores = []
        for propiedad in ("FriendlyName", "DevicePath"):
            var = VARIANT()
            hr = leer(bag, propiedad, ctypes.byref(var), None)
            try:
                if hr < 0:
                    valores.append("")   # una camara virtual puede no tener DevicePath
                elif var.vt != VT_BSTR or not var.bstrVal:
                    raise OSError(f"[camaras_uvc] IPropertyBag::Read({propiedad}) "
                                  f"no devolvio un BSTR (vt={var.vt})")
                else:
                    valores.append(ctypes.wstring_at(var.bstrVal))
            finally:
                oleaut32.VariantClear(ctypes.byref(var))
        return valores[0], valores[1]
    finally:
        _release(bag)


# ----------------------------------------------------------------------------
# La ruta fisica del puerto por CfgMgr32 (fase 2a)
# ----------------------------------------------------------------------------

def _anotar_puertos(camaras: list[CamaraUVC]) -> None:
    for c in camaras:
        c.ruta_puerto, c.ubicacion, c.instancia_usb = datos_puerto(c.enlace)


class _CfgMgr:
    """Las llamadas de cfgmgr32.dll que hacen falta, con sus prototipos."""

    def __init__(self) -> None:
        ct = ctypes
        dll = ct.WinDLL("cfgmgr32")
        dll.CM_Get_Device_Interface_PropertyW.restype = ct.c_uint32
        dll.CM_Get_Device_Interface_PropertyW.argtypes = [
            ct.c_wchar_p, ct.c_void_p, ct.POINTER(ct.c_uint32), ct.c_void_p,
            ct.POINTER(ct.c_uint32), ct.c_uint32]
        dll.CM_Locate_DevNodeW.restype = ct.c_uint32
        dll.CM_Locate_DevNodeW.argtypes = [ct.POINTER(ct.c_uint32), ct.c_wchar_p, ct.c_uint32]
        dll.CM_Get_Parent.restype = ct.c_uint32
        dll.CM_Get_Parent.argtypes = [ct.POINTER(ct.c_uint32), ct.c_uint32, ct.c_uint32]
        dll.CM_Get_Device_ID_Size.restype = ct.c_uint32
        dll.CM_Get_Device_ID_Size.argtypes = [ct.POINTER(ct.c_uint32), ct.c_uint32, ct.c_uint32]
        dll.CM_Get_Device_IDW.restype = ct.c_uint32
        dll.CM_Get_Device_IDW.argtypes = [ct.c_uint32, ct.c_wchar_p, ct.c_uint32, ct.c_uint32]
        dll.CM_Get_DevNode_PropertyW.restype = ct.c_uint32
        dll.CM_Get_DevNode_PropertyW.argtypes = [
            ct.c_uint32, ct.c_void_p, ct.POINTER(ct.c_uint32), ct.c_void_p,
            ct.POINTER(ct.c_uint32), ct.c_uint32]
        self.dll = dll

    @staticmethod
    def _clave(devpkey: tuple[str, int]) -> DEVPROPKEY:
        k = DEVPROPKEY()
        k.fmtid = _guid(devpkey[0])
        k.pid = devpkey[1]
        return k

    def _propiedad(self, llamar, devpkey: tuple[str, int], que: str) -> str:
        """Una propiedad STRING o STRING_LIST (como str con NUL) con el bucle por CR_BUFFER_SMALL."""
        clave = self._clave(devpkey)
        tipo = ctypes.c_uint32(0)
        tam = ctypes.c_uint32(0)
        cr = llamar(ctypes.byref(clave), ctypes.byref(tipo), None, ctypes.byref(tam))
        if cr != CR_BUFFER_SMALL:
            raise OSError(f"[camaras_uvc] {que}: CONFIGRET 0x{cr:02X} al pedir el tamano")
        buf = ctypes.create_unicode_buffer(max(tam.value // 2, 1) + 1)
        tam = ctypes.c_uint32(ctypes.sizeof(buf))
        cr = llamar(ctypes.byref(clave), ctypes.byref(tipo), buf, ctypes.byref(tam))
        if cr != CR_SUCCESS:
            raise OSError(f"[camaras_uvc] {que}: CONFIGRET 0x{cr:02X}")
        if tipo.value not in (DEVPROP_TYPE_STRING, DEVPROP_TYPE_STRING_LIST):
            raise OSError(f"[camaras_uvc] {que}: tipo DEVPROP 0x{tipo.value:X}, no STRING")
        return buf[:tam.value // 2]

    def instancia_de_interfaz(self, enlace: str) -> str:
        """DEVPKEY_Device_InstanceId del enlace simbolico (con o sin el sufijo `\\global`)."""
        dll = self.dll
        intentos = [enlace]
        if enlace.lower().endswith("\\global"):
            intentos.append(enlace[:-len("\\global")])
        ultimo = None
        for ruta in intentos:
            try:
                return self._propiedad(
                    lambda k, t, b, s: dll.CM_Get_Device_Interface_PropertyW(ruta, k, t, b, s, 0),
                    DEVPKEY_DEVICE_INSTANCE_ID, "CM_Get_Device_Interface_PropertyW(InstanceId)"
                ).rstrip("\0")
            except OSError as e:
                ultimo = e
        raise OSError(f"{ultimo} (enlace {enlace!r})")

    def nodo(self, instancia: str) -> int:
        dev = ctypes.c_uint32(0)
        cr = self.dll.CM_Locate_DevNodeW(ctypes.byref(dev), instancia, CM_LOCATE_DEVNODE_NORMAL)
        if cr != CR_SUCCESS:
            raise OSError(f"[camaras_uvc] CM_Locate_DevNodeW({instancia!r}): CONFIGRET 0x{cr:02X}")
        return dev.value

    def padre(self, dev: int) -> int:
        p = ctypes.c_uint32(0)
        cr = self.dll.CM_Get_Parent(ctypes.byref(p), dev, 0)
        if cr != CR_SUCCESS:
            raise OSError(f"[camaras_uvc] CM_Get_Parent: CONFIGRET 0x{cr:02X}")
        return p.value

    def instancia(self, dev: int) -> str:
        n = ctypes.c_uint32(0)
        cr = self.dll.CM_Get_Device_ID_Size(ctypes.byref(n), dev, 0)
        if cr != CR_SUCCESS:
            raise OSError(f"[camaras_uvc] CM_Get_Device_ID_Size: CONFIGRET 0x{cr:02X}")
        buf = ctypes.create_unicode_buffer(n.value + 1)
        cr = self.dll.CM_Get_Device_IDW(dev, buf, n.value + 1, 0)
        if cr != CR_SUCCESS:
            raise OSError(f"[camaras_uvc] CM_Get_Device_IDW: CONFIGRET 0x{cr:02X}")
        return buf.value

    def propiedad_nodo(self, dev: int, devpkey: tuple[str, int], que: str) -> str:
        dll = self.dll
        return self._propiedad(
            lambda k, t, b, s: dll.CM_Get_DevNode_PropertyW(dev, k, t, b, s, 0), devpkey, que)


def datos_puerto(enlace: str) -> tuple[str | None, str | None, str | None]:
    """(ruta_puerto, ubicacion, instancia_usb) del nodo USB de un enlace simbolico.

    Vale para el enlace de Media Foundation y para el DevicePath de DirectShow.
    El nodo USB es el padre del `MI_00` (dispositivo compuesto) o el propio nodo
    si no es compuesto. Si el enlace no es USB (camara virtual), (None, None,
    None); un CONFIGRET de error en una camara USB levanta OSError.
    """
    if sys.platform != "win32":
        raise OSError("[camaras_uvc] solo Windows (CfgMgr32)")
    vid, _pid, _inst = extraer_ids(enlace)
    if vid is None:
        return None, None, None
    cm = _CfgMgr()
    instancia = cm.instancia_de_interfaz(enlace)
    dev = cm.nodo(instancia)
    if "&MI_" in instancia.upper():
        dev = cm.padre(dev)
    instancia_usb = cm.instancia(dev)
    rutas = cm.propiedad_nodo(dev, DEVPKEY_DEVICE_LOCATION_PATHS, "DEVPKEY_Device_LocationPaths")
    ubicacion = cm.propiedad_nodo(dev, DEVPKEY_DEVICE_LOCATION_INFO, "DEVPKEY_Device_LocationInfo")
    return primera_ruta(rutas), ubicacion.rstrip("\0") or None, instancia_usb


def main() -> int:
    rc = 0
    try:
        camaras = listar_camaras_msmf()
    except OSError as e:
        print(f"[camaras_uvc] ERROR (MSMF): {e}")
        return 1
    print(f"[camaras_uvc] {len(camaras)} camara(s) de video (orden del indice MSMF):")
    for c in camaras:
        print(f"  {c.indice}: {c.nombre}  VID={c.vid} PID={c.pid} instancia={c.instancia}")
        print(f"      puerto: {c.ruta_puerto}  ubicacion: {c.ubicacion}  usb: {c.instancia_usb}")
        print(f"      enlace: {c.enlace}")
    try:
        dshow = listar_camaras_dshow()
    except OSError as e:
        print(f"[camaras_uvc] ERROR (DSHOW): {e}")
        return 1
    print(f"[camaras_uvc] {len(dshow)} camara(s) de video (orden del indice DSHOW):")
    for c in dshow:
        print(f"  {c.indice}: {c.nombre}  instancia={c.instancia}  puerto: {c.ruta_puerto}")
        print(f"      enlace: {c.enlace}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
