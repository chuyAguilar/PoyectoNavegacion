"""camaras_uvc.py sin camara: enlaces simbolicos de ejemplo (meta 002, fase 1)."""
from __future__ import annotations

import pytest

import camaras_uvc as cu

# El de la camara 1 en P02 (instancia USB\VID_32E4&PID_0234&MI_00\6&325DB0BA&1&0000),
# en la forma en que Media Foundation da el enlace simbolico.
ENLACE_GS1 = (r"\\?\usb#vid_32e4&pid_0234&mi_00#6&325db0ba&1&0000"
              r"#{e5323777-f976-4f5b-9b55-b94699c46e44}\global")
ENLACE_GS2 = (r"\\?\usb#vid_32e4&pid_0234&mi_00#6&1a2b3c4d&0&0000"
              r"#{e5323777-f976-4f5b-9b55-b94699c46e44}\global")
# Dispositivo no compuesto con numero de serie como instancia.
ENLACE_SERIE = (r"\\?\USB#VID_046D&PID_085C#SN0123ABC"
                r"#{65E8773D-8F56-11D0-A3B9-00A0C9223196}\GLOBAL")
ENLACE_VIRTUAL = r"\\?\root#image#0000#{e5323777-f976-4f5b-9b55-b94699c46e44}\global"


def test_extraer_ids_compuesto() -> None:
    assert cu.extraer_ids(ENLACE_GS1) == ("32E4", "0234", "6&325DB0BA&1&0000")


def test_extraer_ids_con_serie() -> None:
    assert cu.extraer_ids(ENLACE_SERIE) == ("046D", "085C", "SN0123ABC")


@pytest.mark.parametrize("enlace", [ENLACE_VIRTUAL, "", "basura"])
def test_extraer_ids_no_usb(enlace: str) -> None:
    assert cu.extraer_ids(enlace) == (None, None, None)


def _camara(i: int, enlace: str) -> cu.CamaraUVC:
    return cu.CamaraUVC(i, "Global Shutter Camera", enlace, *cu.extraer_ids(enlace))


CAMARAS = [_camara(0, ENLACE_GS1), _camara(1, ENLACE_GS2), _camara(2, ENLACE_VIRTUAL)]


def test_resolver_indice_una_coincidencia() -> None:
    assert cu.resolver_indice("6&325DB0BA&1", CAMARAS) == 0
    assert cu.resolver_indice("6&1a2b3c4d", CAMARAS) == 1  # sin distinguir mayusculas


def test_resolver_indice_ninguna() -> None:
    with pytest.raises(ValueError, match="no coincide"):
        cu.resolver_indice("6&DEADBEEF", CAMARAS)


def test_resolver_indice_dos() -> None:
    with pytest.raises(ValueError, match="coincide con 2"):
        cu.resolver_indice("&0000", CAMARAS)


def test_resolver_indice_vacio() -> None:
    with pytest.raises(ValueError, match="vacio"):
        cu.resolver_indice("  ", CAMARAS)


def test_resolver_indice_sin_camaras() -> None:
    with pytest.raises(ValueError, match="ninguna camara enumerada"):
        cu.resolver_indice("6&325DB0BA", [])


def test_guid_bytes() -> None:
    """El GUID de ctypes tiene los bytes de Windows (little-endian en los 3 primeros campos)."""
    import ctypes
    import uuid
    g = cu._guid(cu.MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID)
    assert bytes(ctypes.string_at(ctypes.addressof(g), 16)) == \
        uuid.UUID(cu.MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID).bytes_le
