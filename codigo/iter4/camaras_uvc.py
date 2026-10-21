# -*- coding: utf-8 -*-
"""
camaras_uvc.py -- Enumera las camaras de video de Media Foundation (meta 002, fase 1).

Da, por cada camara, el indice (el mismo orden que usa cv2.CAP_MSMF), el
nombre y el enlace simbolico, y de este saca VID, PID e instancia USB. Sirve
para identificar cada camara SVPRO por su instancia (puerto USB fijo y
etiquetado; clarify.md P1) en vez de confiar en el indice.

Sin dependencia nueva: ctypes sobre ole32, mfplat y mf. No abre ninguna
camara: solo enumera (no activa el IMFActivate).

Por que el orden coincide con OpenCV: el backend MSMF de OpenCV abre la camara
`index` tomando el elemento `index` de MFEnumDeviceSources con el atributo
MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = VIDCAP_GUID, que es lo que hace aqui
listar_camaras_msmf(). Se verifica en vivo (sondear_camara.py --verificar-orden).

Uso (solo lista; no necesita argumentos):
    python iter4\\camaras_uvc.py
"""
from __future__ import annotations

import re
import sys
import uuid
from dataclasses import dataclass

# ----------------------------------------------------------------------------
# GUIDs y constantes. Valores de los encabezados del Windows SDK:
#   mfidl.h : MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
#             MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID,
#             MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME,
#             MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK
#   mfapi.h : MF_VERSION = (MF_SDK_VERSION << 16) | MF_API_VERSION = 0x00020070,
#             MFSTARTUP_FULL = 0
#   objbase.h: COINIT_MULTITHREADED = 0
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
RPC_E_CHANGED_MODE = 0x80010106

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


@dataclass
class CamaraUVC:
    """Una camara tal como la enumera Media Foundation."""
    indice: int
    nombre: str
    enlace: str
    vid: str | None
    pid: str | None
    instancia: str | None


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


def resolver_indice(device_id: str, camaras: list[CamaraUVC]) -> int:
    """El indice de la unica camara cuya instancia contiene `device_id`.

    La comparacion no distingue mayusculas. ValueError si ninguna o mas de una
    coinciden (principio 7: no se adivina cual abrir).
    """
    if not device_id or not str(device_id).strip():
        raise ValueError("device_id vacio")
    buscado = str(device_id).strip().upper()
    hallados = [c for c in camaras
                if c.instancia is not None and buscado in c.instancia.upper()]
    if len(hallados) == 1:
        return hallados[0].indice
    lista = "; ".join(f"{c.indice}: {c.nombre} [{c.instancia}]" for c in camaras) \
        or "ninguna camara enumerada"
    if not hallados:
        raise ValueError(f"device_id '{device_id}' no coincide con ninguna "
                         f"camara conectada ({lista})")
    raise ValueError(f"device_id '{device_id}' coincide con {len(hallados)} "
                     f"camaras ({lista}); hace falta un trozo mas largo")


# ----------------------------------------------------------------------------
# Enumeracion por Media Foundation (ctypes, solo Windows)
# ----------------------------------------------------------------------------

def _guid(texto: str):
    import ctypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

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
    import ctypes
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return proto(vtbl[indice])


def _release(obj) -> None:
    import ctypes
    if obj:
        _metodo(obj, VT_RELEASE, ctypes.c_ulong)(obj)


def _cadena(activate, guid_txt: str, ole32) -> str:
    import ctypes
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


def listar_camaras_msmf() -> list[CamaraUVC]:
    """Las camaras de video de Media Foundation, en el orden del indice MSMF.

    Falla fuerte (OSError) si COM o Media Foundation no inicializan o si una
    llamada devuelve error. No abre ninguna camara.
    """
    if sys.platform != "win32":
        raise OSError("[camaras_uvc] solo Windows (Media Foundation)")
    import ctypes

    ole32 = ctypes.WinDLL("ole32")
    mfplat = ctypes.WinDLL("mfplat")
    mf = ctypes.WinDLL("mf")
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole32.CoUninitialize.restype = None
    ole32.CoTaskMemFree.restype = None
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    mfplat.MFStartup.restype = ctypes.c_long
    mfplat.MFStartup.argtypes = [ctypes.c_ulong, ctypes.c_uint32]
    mfplat.MFShutdown.restype = ctypes.c_long
    mfplat.MFCreateAttributes.restype = ctypes.c_long
    mfplat.MFCreateAttributes.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32]
    mf.MFEnumDeviceSources.restype = ctypes.c_long
    mf.MFEnumDeviceSources.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
        ctypes.POINTER(ctypes.c_uint32)]

    hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    # S_OK (0) o S_FALSE (1): este hilo lo inicializo y hay que cerrarlo.
    # RPC_E_CHANGED_MODE: COM ya estaba en otro modo; se usa tal cual.
    com_propio = hr in (0, 1)
    if not com_propio and (hr & 0xFFFFFFFF) != RPC_E_CHANGED_MODE:
        _hr_ok(hr, "CoInitializeEx")
    try:
        _hr_ok(mfplat.MFStartup(MF_VERSION, MFSTARTUP_FULL), "MFStartup")
        try:
            return _enumerar(ole32, mfplat, mf)
        finally:
            mfplat.MFShutdown()
    finally:
        if com_propio:
            ole32.CoUninitialize()


def _enumerar(ole32, mfplat, mf) -> list[CamaraUVC]:
    import ctypes
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


def main() -> int:
    try:
        camaras = listar_camaras_msmf()
    except OSError as e:
        print(f"[camaras_uvc] ERROR: {e}")
        return 1
    print(f"[camaras_uvc] {len(camaras)} camara(s) de video (orden del indice MSMF):")
    for c in camaras:
        print(f"  {c.indice}: {c.nombre}  VID={c.vid} PID={c.pid} instancia={c.instancia}")
        print(f"      enlace: {c.enlace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
