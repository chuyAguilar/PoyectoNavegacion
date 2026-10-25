"""B34 (meta 003, fase 4): la suite no puede abrir una camara real ni el puerto 18944
aunque cambie un perfil. El fixture autouse `no_real_camera` de conftest niega
`cv2.VideoCapture`, la enumeracion de camaras, `WebcamBackend.open` sin falso y
`pyigtl.OpenIGTLinkServer`; aqui se comprueba con los perfiles reales.
"""
from __future__ import annotations

import cv2
import pyigtl
import pytest

from camera import backend as cb
from camera import uvc as cu
import profiles
import tracker

from .conftest import PROFILES_DIR, RealHardwareForbidden


def test_videocapture_negado() -> None:
    with pytest.raises(RealHardwareForbidden, match="B34"):
        cv2.VideoCapture(0)
    with pytest.raises(RealHardwareForbidden):
        cv2.VideoCapture(1, cv2.CAP_MSMF)


def test_enumerar_camaras_negado() -> None:
    with pytest.raises(RealHardwareForbidden):
        cu.listar_camaras_msmf()
    with pytest.raises(RealHardwareForbidden):
        cu.listar_camaras_dshow()


@pytest.mark.parametrize("nombre", ["tracker_config_gs1.yaml", "tracker_config_gs2.yaml"])
def test_un_perfil_real_no_abre_la_camara(nombre: str) -> None:
    cfg = profiles.load(PROFILES_DIR / nombre)
    b = cb.create_backend(cfg["camera"])             # construir no toca hardware
    assert isinstance(b, cb.WebcamBackend) and b.cap is None
    with pytest.raises(RealHardwareForbidden, match="B34"):
        b.open()
    assert b.cap is None and b.indice is None        # paro antes de resolver el puerto


def test_servidor_openigtlink_negado() -> None:
    with pytest.raises(RealHardwareForbidden, match="18944"):
        pyigtl.OpenIGTLinkServer(port=18944)


def test_tracker_con_el_perfil_real_para_antes_del_hardware() -> None:
    with pytest.raises(RealHardwareForbidden):
        tracker.main(["--config", str(PROFILES_DIR / "tracker_config_gs1.yaml"), "--no-window"])
