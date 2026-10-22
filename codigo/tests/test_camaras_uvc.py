"""camaras_uvc.py sin camara: enlaces simbolicos y rutas de puerto de ejemplo (meta 002, fases 1 y 2a)."""
from __future__ import annotations

import pytest

import camaras_uvc as cu

# El de la camara 1 en P02 (instancia USB\VID_32E4&PID_0234&MI_00\6&325DB0BA&1&0000),
# en la forma en que Media Foundation da el enlace simbolico.
ENLACE_GS1 = (r"\\?\usb#vid_32e4&pid_0234&mi_00#6&325db0ba&1&0000"
              r"#{e5323777-f976-4f5b-9b55-b94699c46e44}\global")
ENLACE_GS2 = (r"\\?\usb#vid_32e4&pid_0234&mi_00#7&320abb2b&0&0000"
              r"#{e5323777-f976-4f5b-9b55-b94699c46e44}\global")
# Dispositivo no compuesto con numero de serie como instancia.
ENLACE_SERIE = (r"\\?\USB#VID_046D&PID_085C#SN0123ABC"
                r"#{65E8773D-8F56-11D0-A3B9-00A0C9223196}\GLOBAL")
ENLACE_VIRTUAL = r"\\?\root#image#0000#{e5323777-f976-4f5b-9b55-b94699c46e44}\global"

# Rutas fisicas de puerto (DEVPKEY_Device_LocationPaths, primer elemento), de ejemplo.
PUERTO_1 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)"
PUERTO_2 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)"
PUERTO_HUB = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)#USB(1)"   # un hub colgado del puerto 1


def test_extraer_ids_compuesto() -> None:
    assert cu.extraer_ids(ENLACE_GS1) == ("32E4", "0234", "6&325DB0BA&1&0000")


def test_extraer_ids_con_serie() -> None:
    assert cu.extraer_ids(ENLACE_SERIE) == ("046D", "085C", "SN0123ABC")


@pytest.mark.parametrize("enlace", [ENLACE_VIRTUAL, "", "basura"])
def test_extraer_ids_no_usb(enlace: str) -> None:
    assert cu.extraer_ids(enlace) == (None, None, None)


def _camara(i: int, enlace: str, puerto: str | None = None) -> cu.CamaraUVC:
    return cu.CamaraUVC(i, "Global Shutter Camera", enlace, *cu.extraer_ids(enlace),
                        ruta_puerto=puerto)


def test_camara_sin_puerto_sigue_valiendo() -> None:
    """Las construcciones de la fase 1 (6 campos) siguen valiendo: los nuevos son None."""
    c = cu.CamaraUVC(0, "x", ENLACE_GS1, *cu.extraer_ids(ENLACE_GS1))
    assert (c.ruta_puerto, c.ubicacion, c.instancia_usb) == (None, None, None)


CAMARAS = [_camara(0, ENLACE_GS1, PUERTO_1), _camara(1, ENLACE_GS2, PUERTO_2),
           _camara(2, ENLACE_VIRTUAL)]


def test_primera_ruta() -> None:
    assert cu.primera_ruta(f"{PUERTO_1}\0ACPI(_SB_)#ACPI(PCI0)#USB(2)\0\0") == PUERTO_1
    assert cu.primera_ruta(f"\0 {PUERTO_2} \0") == PUERTO_2
    assert cu.primera_ruta("") is None and cu.primera_ruta(None) is None
    assert cu.primera_ruta("\0\0") is None


def test_resolver_indice_una_coincidencia() -> None:
    assert cu.resolver_indice(PUERTO_1, CAMARAS) == 0
    assert cu.resolver_indice(PUERTO_2.lower(), CAMARAS) == 1   # sin distinguir mayusculas
    assert cu.resolver_indice(f"  {PUERTO_2}  ", CAMARAS) == 1


def test_resolver_indice_ninguna() -> None:
    with pytest.raises(ValueError, match="no coincide"):
        cu.resolver_indice("PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(9)", CAMARAS)


def test_resolver_indice_prefijo_no_coincide() -> None:
    """La ruta del puerto 1 es prefijo de la de un hub colgado de el: igualdad, no subcadena."""
    camaras = [_camara(0, ENLACE_GS1, PUERTO_HUB), _camara(1, ENLACE_GS2, PUERTO_2)]
    with pytest.raises(ValueError, match="no coincide"):
        cu.resolver_indice(PUERTO_1, camaras)
    assert cu.resolver_indice(PUERTO_HUB, camaras) == 0


def test_resolver_indice_dos() -> None:
    camaras = [_camara(0, ENLACE_GS1, PUERTO_1), _camara(1, ENLACE_GS2, PUERTO_1)]
    with pytest.raises(ValueError, match="coincide con 2"):
        cu.resolver_indice(PUERTO_1, camaras)


def test_resolver_indice_vacio() -> None:
    with pytest.raises(ValueError, match="vacio"):
        cu.resolver_indice("  ", CAMARAS)


def test_resolver_indice_sin_camaras() -> None:
    with pytest.raises(ValueError, match="ninguna camara enumerada"):
        cu.resolver_indice(PUERTO_1, [])


def test_resolver_indice_ya_no_busca_por_instancia() -> None:
    """La instancia elegiria mal (cierre de la fase 1): un trozo de instancia no resuelve."""
    with pytest.raises(ValueError, match="no coincide"):
        cu.resolver_indice("6&325DB0BA&1", CAMARAS)


def test_guid_bytes() -> None:
    """El GUID de ctypes tiene los bytes de Windows (little-endian en los 3 primeros campos)."""
    import ctypes
    import uuid
    g = cu._guid(cu.MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID)
    assert bytes(ctypes.string_at(ctypes.addressof(g), 16)) == \
        uuid.UUID(cu.MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID).bytes_le


def test_estructuras_com_tienen_el_tamano_de_windows_x64() -> None:
    import ctypes
    assert ctypes.sizeof(cu.GUID) == 16
    assert ctypes.sizeof(cu.DEVPROPKEY) == 20
    assert ctypes.sizeof(cu.VARIANT) == 24
    k = cu._CfgMgr._clave(cu.DEVPKEY_DEVICE_LOCATION_PATHS)
    assert k.pid == 37
    assert cu.DEVPROP_TYPE_STRING_LIST == cu.DEVPROP_TYPE_STRING | 0x2000


def test_datos_puerto_no_usb_sin_cfgmgr(monkeypatch) -> None:
    """Una camara virtual no llama a CfgMgr32: (None, None, None)."""
    monkeypatch.setattr(cu, "_CfgMgr", lambda: (_ for _ in ()).throw(AssertionError("no debia")))
    monkeypatch.setattr(cu.sys, "platform", "win32")
    assert cu.datos_puerto(ENLACE_VIRTUAL) == (None, None, None)


def test_datos_puerto_va_al_padre_del_mi_00(monkeypatch) -> None:
    """Con un enlace compuesto (MI_00), la ruta es la del nodo USB padre; sin MI, la del propio nodo."""
    llamadas: list[str] = []

    class CfgFalso:
        def instancia_de_interfaz(self, enlace):
            llamadas.append("interfaz")
            return (r"USB\VID_32E4&PID_0234&MI_00\6&325DB0BA&1&0000" if "mi_00" in enlace
                    else r"USB\VID_046D&PID_085C\SN0123ABC")

        def nodo(self, instancia):
            llamadas.append("nodo")
            return 10

        def padre(self, dev):
            llamadas.append("padre")
            return 20

        def instancia(self, dev):
            return {10: r"USB\VID_046D&PID_085C\SN0123ABC",
                    20: r"USB\VID_32E4&PID_0234\01.00.00"}[dev]

        def propiedad_nodo(self, dev, devpkey, que):
            if devpkey == cu.DEVPKEY_DEVICE_LOCATION_PATHS:
                return {10: f"{PUERTO_2}\0\0", 20: f"{PUERTO_1}\0ACPI(x)\0\0"}[dev]
            return {10: "Port_#0003.Hub_#0001\0", 20: "Port_#0002.Hub_#0001\0"}[dev]

    monkeypatch.setattr(cu, "_CfgMgr", CfgFalso)
    monkeypatch.setattr(cu.sys, "platform", "win32")
    assert cu.datos_puerto(ENLACE_GS1) == (PUERTO_1, "Port_#0002.Hub_#0001",
                                           r"USB\VID_32E4&PID_0234\01.00.00")
    assert llamadas == ["interfaz", "nodo", "padre"]
    llamadas.clear()
    assert cu.datos_puerto(ENLACE_SERIE) == (PUERTO_2, "Port_#0003.Hub_#0001",
                                             r"USB\VID_046D&PID_085C\SN0123ABC")
    assert llamadas == ["interfaz", "nodo"]
