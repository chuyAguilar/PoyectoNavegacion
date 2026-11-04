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

import socket
import struct
import sys
import time

import numpy as np
import pyigtl
import pytest

from transport import igtl

from .synthetic import servidor_pyigtl_sin_puerto

DOC_IP = "192.0.2.10"           # RFC 5737, direccion de documentacion: no es de ninguna red real


class FakeServer:
    instances: list["FakeServer"] = []
    ifaces: dict[str, str] = {"ifaz0": DOC_IP}
    caida_a_lo_rota: bool = True      # pyigtl 0.3.1: su reintento con 'lo' (str) lanza struct.error

    def __init__(self, port=None, local_server=True, iface=None, **kw) -> None:
        self.port, self.kw, self.messages, self.stopped = port, kw, [], 0
        self.local_server, self.iface = local_server, iface
        # Como pyigtl 0.3.1 en Linux: local -> loopback; si no, struct.pack('256s', iface[:15])
        # exige bytes; la IP de la interfaz, y si no la tiene, reintenta con 'lo' (str) y falla.
        if local_server:
            self.host = "127.0.0.1"
        else:
            nombre = iface if iface is not None else b"eth0"
            if not isinstance(nombre, bytes):
                raise struct.error("argument for 's' must be a bytes object")
            if nombre.decode() in FakeServer.ifaces:
                self.host = FakeServer.ifaces[nombre.decode()]
            elif FakeServer.caida_a_lo_rota:
                try:
                    raise OSError(19, "No such device")
                except OSError:
                    raise struct.error("argument for 's' must be a bytes object")
            else:
                self.host = "127.0.0.1"          # un pyigtl que si cayera a `lo`
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
    monkeypatch.setattr(FakeServer, "caida_a_lo_rota", True)
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
    assert srv.port == 18944 and srv.local_server is False and srv.iface == b"ifaz0"   # bytes a pyigtl
    assert s.host == DOC_IP and s.iface == "ifaz0"
    assert f"[OpenIGTLink] Transformadas en {DOC_IP}:18944 (interfaz ifaz0)" in capsys.readouterr().out
    assert s.send("Marker0ToTracker", np.eye(4)) is True           # el envio es el mismo
    (msg, wait), = srv.messages
    assert msg.device_name == "Marker0ToTracker" and wait is False
    s.close()
    assert srv.stopped == 1


def test_el_falso_falla_como_pyigtl_con_un_str(fake_server) -> None:
    """El fallo del P-6 (2026-11-03): pyigtl 0.3.1 con el nombre como `str` lanza struct.error."""
    with pytest.raises(struct.error, match="bytes"):
        FakeServer(port=18944, local_server=False, iface="ifaz0")


def test_con_iface_que_no_existe_pyigtl_031_lanza_struct_error_y_se_convierte(fake_server, capsys) -> None:
    """pyigtl 0.3.1: la interfaz no da IPv4, su reintento con 'lo' (str) lanza struct.error;
    `IgtlSender` lo convierte en `IgtlInterfaceError` (el tracker sale con 2) con la causa."""
    with pytest.raises(igtl.IgtlInterfaceError, match="'noexiste0' no existe o no tiene IPv4") as e:
        igtl.IgtlSender(18944, iface="noexiste0", plataforma="linux")
    assert "No such device" in str(e.value) and "No se abre la camara" in str(e.value)
    assert isinstance(e.value.__cause__, struct.error)
    assert fake_server.instances == []                     # no llego a crearse: nada que parar
    assert "Transformadas en" not in capsys.readouterr().out


def test_con_iface_que_pyigtl_no_resuelve_aborta_y_para_el_servidor(fake_server, capsys) -> None:
    fake_server.caida_a_lo_rota = False                    # un pyigtl que si cae a `lo`
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


# ----------------------------------------------------------------------------
# El `__init__` real de pyigtl en Linux (el arreglo de `--igtl-iface`, P-6 del 2026-11-03).
# Sin puerto ni hilos (`servidor_pyigtl_sin_puerto`); corren en la Jetson con `suite wip`.
# ----------------------------------------------------------------------------

solo_linux = pytest.mark.skipif(not sys.platform.startswith("linux"),
                                reason="solo Linux: pyigtl resuelve la interfaz por ioctl(SIOCGIFADDR)")


def _una_interfaz_con_ipv4() -> tuple[str, str] | None:
    """Una interfaz de esta maquina que no es loopback y tiene IPv4, con su IP (o None)."""
    import fcntl  # solo Linux
    for _, nombre in socket.if_nameindex():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915,
                                                  struct.pack("256s", nombre.encode()[:15]))[20:24])
            except OSError:
                continue
        if not ip.startswith("127."):
            return nombre, ip
    return None


@pytest.fixture
def servidor_real(monkeypatch) -> type:
    clase = servidor_pyigtl_sin_puerto()
    clase.instances = []
    monkeypatch.setattr(igtl.pyigtl, "OpenIGTLinkServer", clase)
    return clase


@solo_linux
def test_pyigtl_real_con_el_nombre_en_str_falla_como_en_el_p6(servidor_real) -> None:
    """Lo que hacia `IgtlSender` antes del arreglo: el nombre como `str` -> struct.error."""
    with pytest.raises(struct.error, match="bytes"):
        servidor_real(port=18944, local_server=False, iface="lo")


@solo_linux
def test_pyigtl_real_con_lo_da_loopback_y_aborta(servidor_real) -> None:
    """Con el arreglo `lo` se resuelve (127.0.0.1) y `IgtlSender` aborta: Slicer en el PC no llegaria.
    Sin el arreglo, struct.error (no `IgtlInterfaceError`): la prueba fallaria."""
    with pytest.raises(igtl.IgtlInterfaceError, match=r"pyigtl cayo a loopback \(127\.0\.0\.1\)"):
        igtl.IgtlSender(18944, iface="lo")
    srv, = servidor_real.instances
    assert srv.server_address == ("127.0.0.1", 18944) and srv.stopped == 1


@solo_linux
def test_pyigtl_real_con_una_interfaz_que_no_existe_aborta(servidor_real) -> None:
    with pytest.raises(igtl.IgtlInterfaceError, match="'noexiste0' no existe o no tiene IPv4: el sistema") as e:
        igtl.IgtlSender(18944, iface="noexiste0")
    assert isinstance(e.value.__cause__, struct.error)
    assert servidor_real.instances == []


@solo_linux
def test_pyigtl_real_con_una_interfaz_con_ipv4_se_liga_a_su_ip(servidor_real, capsys) -> None:
    hallada = _una_interfaz_con_ipv4()
    if hallada is None:
        pytest.skip("esta maquina no tiene una interfaz con IPv4 fuera de loopback")
    nombre, ip = hallada
    s = igtl.IgtlSender(18944, iface=nombre)
    srv, = servidor_real.instances
    assert s.host == ip and srv.server_address == (ip, 18944)
    assert f"Transformadas en {ip}:18944 (interfaz {nombre})" in capsys.readouterr().out
    s.close()
    assert srv.stopped == 1
