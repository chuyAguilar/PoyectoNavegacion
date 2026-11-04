"""`transport.igtl.IgtlSender` con un servidor pyigtl falso (meta 003, fases 4 y 7): el
servidor se crea en el puerto pedido, `send` encola un `TransformMessage` 4x4 con
su nombre (`Marker0ToTracker`) sin esperar (`wait=False`, E1 de la fase 7), sin
cliente no encola y lo cuenta (la guarda), `wait_for_client` espera con tope, una
matriz que no es 4x4 falla antes de enviar, `close` para el servidor una sola vez
y con tope.

Meta 007, fase 6 (`iface`): sin interfaz el servidor es `local_server` y el log dice
`127.0.0.1:18944`; con una interfaz en Linux se crea con `local_server=False,
iface=...` y `host` es la direccion a la que quedo ligado; si pyigtl cae a
loopback (la interfaz no existe o no tiene IPv4), `IgtlInterfaceError` y el
servidor se para; en Windows, `IgtlInterfaceError` antes de crear nada. El falso
imita a pyigtl: resuelve `iface` con la tabla `ifaces` y, si no esta, 127.0.0.1.
"""
from __future__ import annotations

import time

import numpy as np
import pyigtl
import pytest

from transport import igtl

DOC_IP = "192.0.2.10"           # RFC 5737, direccion de documentacion: no es de ninguna red real


class FakeServer:
    instances: list["FakeServer"] = []
    ifaces: dict[str, str] = {"ifaz0": DOC_IP}

    def __init__(self, port=None, local_server=True, iface=None, **kw) -> None:
        self.port, self.kw, self.messages, self.stopped = port, kw, [], 0
        self.local_server, self.iface = local_server, iface
        # Como pyigtl: local -> loopback; si no, la IP de la interfaz, y si no existe, `lo`.
        self.host = "127.0.0.1" if local_server else FakeServer.ifaces.get(iface or "eth0", "127.0.0.1")
        self.server_address = (self.host, port)
        self.hang_s = 0.0
        self.connected = True
        self.connect_after_calls = 0      # is_connected pasa a True tras N consultas
        self.calls = 0
        FakeServer.instances.append(self)

    def send_message(self, message, wait=True) -> bool:
        self.messages.append((message, wait))
        return True

    def is_connected(self) -> bool:
        self.calls += 1
        if self.connect_after_calls and self.calls >= self.connect_after_calls:
            self.connected = True
        return self.connected

    def stop(self) -> None:
        if self.hang_s:
            time.sleep(self.hang_s)
        self.stopped += 1


@pytest.fixture
def fake_server(monkeypatch) -> type[FakeServer]:
    FakeServer.instances = []
    monkeypatch.setattr(igtl.pyigtl, "OpenIGTLinkServer", FakeServer)
    return FakeServer


def test_sender_crea_el_servidor_en_el_puerto_y_manda_transforms(fake_server, capsys) -> None:
    s = igtl.IgtlSender(18944)
    assert len(fake_server.instances) == 1 and fake_server.instances[0].port == 18944
    srv = fake_server.instances[0]
    assert srv.local_server is True and srv.iface is None          # sin iface: loopback, como siempre
    assert s.host == "127.0.0.1" and s.iface is None
    assert "[OpenIGTLink] Transformadas en 127.0.0.1:18944" in capsys.readouterr().out
    M = np.eye(4)
    M[:3, 3] = [1.5, -2.5, 450.25]
    assert s.send("Marker0ToTracker", M) is True
    (msg, wait), = fake_server.instances[0].messages
    assert isinstance(msg, pyigtl.TransformMessage)
    assert msg.device_name == "Marker0ToTracker" and wait is False     # fase 7, E1: encola y vuelve
    assert msg.matrix.dtype == np.float32 and np.array_equal(msg.matrix, M.astype(np.float32))
    assert s.sent == 1 and s.dropped == 0 and s.is_connected()


def test_sender_rechaza_lo_que_no_es_4x4(fake_server) -> None:
    s = igtl.IgtlSender(18944)
    with pytest.raises(ValueError, match="4x4"):
        s.send("Marker0ToTracker", np.eye(3))
    assert fake_server.instances[0].messages == [] and s.sent == 0


def test_sin_cliente_no_encola_cuenta_y_avisa(fake_server, capsys) -> None:
    s = igtl.IgtlSender(18944)
    srv = fake_server.instances[0]
    srv.connected = False
    for _ in range(3):
        assert s.send("Marker0ToTracker", np.eye(4)) is False
    assert srv.messages == [] and s.sent == 0 and s.dropped == 3
    out = capsys.readouterr().out
    assert out.count("sin cliente conectado") == 1          # avisa en el 1.o, no en cada frame
    srv.connected = True
    assert s.send("Marker0ToTracker", np.eye(4)) is True and s.sent == 1 and len(srv.messages) == 1
    s.close()
    assert "1 envios; 3 envios sin cliente" in capsys.readouterr().out


def test_wait_for_client_vuelve_cuando_se_conecta(fake_server) -> None:
    s = igtl.IgtlSender(18944)
    srv = fake_server.instances[0]
    srv.connected = False
    srv.connect_after_calls = 4
    t0 = time.monotonic()
    assert s.wait_for_client(5.0, poll_s=0.01) is True
    assert time.monotonic() - t0 < 1.0 and srv.calls >= 4


def test_wait_for_client_con_tope_si_nadie_llega(fake_server) -> None:
    s = igtl.IgtlSender(18944)
    fake_server.instances[0].connected = False
    t0 = time.monotonic()
    assert s.wait_for_client(0.2, poll_s=0.01) is False
    dt = time.monotonic() - t0
    assert 0.15 <= dt < 1.0


def test_close_para_el_servidor_una_vez(fake_server, capsys) -> None:
    s = igtl.IgtlSender(18944)
    s.close()
    s.close()
    assert fake_server.instances[0].stopped == 1
    assert "cerrado" in capsys.readouterr().out
    assert s.is_connected() is False                         # cerrado: sin servidor


def test_close_con_tope_si_el_servidor_no_termina(fake_server, monkeypatch, capsys) -> None:
    monkeypatch.setattr(igtl, "STOP_TIMEOUT_S", 0.2)
    s = igtl.IgtlSender(18944)
    fake_server.instances[0].hang_s = 1.0
    t0 = time.monotonic()
    s.close()
    assert time.monotonic() - t0 < 0.9
    assert "no cerro en 0 s" in capsys.readouterr().out


# ----------------------------------------------------------------------------
# iface (meta 007, fase 6; ADR J2)
# ----------------------------------------------------------------------------

def test_con_iface_en_linux_escucha_en_esa_interfaz_y_lo_dice(fake_server, capsys) -> None:
    s = igtl.IgtlSender(18944, iface="ifaz0", plataforma="linux")
    srv, = fake_server.instances
    assert srv.port == 18944 and srv.local_server is False and srv.iface == "ifaz0"
    assert s.host == DOC_IP and s.iface == "ifaz0"
    assert f"[OpenIGTLink] Transformadas en {DOC_IP}:18944 (interfaz ifaz0)" in capsys.readouterr().out
    assert s.send("Marker0ToTracker", np.eye(4)) is True           # el envio es el mismo
    (msg, wait), = srv.messages
    assert msg.device_name == "Marker0ToTracker" and wait is False
    s.close()
    assert srv.stopped == 1


def test_con_iface_que_pyigtl_no_resuelve_aborta_y_para_el_servidor(fake_server, capsys) -> None:
    with pytest.raises(igtl.IgtlInterfaceError, match="'noexiste0' no existe o no tiene IPv4"):
        igtl.IgtlSender(18944, iface="noexiste0", plataforma="linux")
    srv, = fake_server.instances
    assert srv.local_server is False and srv.host == "127.0.0.1"       # pyigtl cayo a `lo`
    assert srv.stopped == 1                                            # y se paro: el puerto queda libre
    assert "Transformadas en" not in capsys.readouterr().out


def test_iface_sin_ip_en_server_address_tambien_aborta(fake_server) -> None:
    fake_server.ifaces = {**FakeServer.ifaces, "sinip0": ""}
    try:
        with pytest.raises(igtl.IgtlInterfaceError, match="sin direccion"):
            igtl.IgtlSender(18944, iface="sinip0", plataforma="linux")
    finally:
        fake_server.ifaces = {"ifaz0": DOC_IP}
    assert fake_server.instances[0].stopped == 1


def test_con_iface_en_windows_aborta_antes_de_crear_nada(fake_server) -> None:
    with pytest.raises(igtl.IgtlInterfaceError, match="solo existe en Linux"):
        igtl.IgtlSender(18944, iface="ifaz0", plataforma="win32")
    assert fake_server.instances == []


def test_plataforma_por_defecto_es_la_de_aqui(fake_server) -> None:
    import sys
    if sys.platform.startswith("linux"):
        s = igtl.IgtlSender(18944, iface="ifaz0")
        assert s.host == DOC_IP
    else:
        with pytest.raises(igtl.IgtlInterfaceError):
            igtl.IgtlSender(18944, iface="ifaz0")
        assert fake_server.instances == []


def test_bound_host_prefiere_server_address() -> None:
    class Srv:
        server_address = (DOC_IP, 18944)
        host = "127.0.0.1"
    assert igtl._bound_host(Srv(), "x") == DOC_IP

    class SoloHost:
        host = "198.51.100.7"
    assert igtl._bound_host(SoloHost(), "x") == "198.51.100.7"
    assert igtl._bound_host(object(), "127.0.0.1") == "127.0.0.1"
