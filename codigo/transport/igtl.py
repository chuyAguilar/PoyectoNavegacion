"""`IgtlSender`: el servidor OpenIGTLink del tracker y el envio de una transform.

Era el trozo de `tracker.main()` que creaba `pyigtl.OpenIGTLinkServer(port=...)`
y enviaba `pyigtl.TransformMessage(M, device_name=...)` (meta 003, fase 4).

Meta 003, fase 7 · Subir los fps con ventana (E1 de `clarify.md` P9): `send`
encola con `send_message(msg, wait=False)` y vuelve en ~0.05 ms. Con
`wait=True` (lo de antes) el bucle esperaba a que el hilo del servidor vaciara
la cola, y ese hilo despierta en el tic de 15.6 ms de Windows (su `recv` con
tope de 10 ms), asi que el envio costaba 9-12.5 ms por frame y enganchaba el
bucle al tic (fase 6). Los bytes, el orden y el `timestamp` de cada mensaje no
cambian: solo deja de esperarse. Mientras Slicer esta conectado nada se
pierde: el hilo vacia la cola (`deque(maxlen=100)`) en cada tic.

La guarda: sin cliente conectado (`is_connected()` falso) la cola no se
vaciaria nunca y, al llenarse, descartaria en silencio; por eso `send` no
encola, cuenta lo no enviado en `dropped` y lo dice en el log (principio 7).
`wait_for_client(timeout)` es lo que el tracker usa al arrancar para esperar a
Slicer con tope (clarify P9: sin Slicer, aborta y lo dice).

Meta 007, fase 6 · Slicer en el PC recibe de la Jetson (ADR J2 del plan; clarify
P10): `IgtlSender(port, iface=None)`. Sin `iface` el servidor escucha en
127.0.0.1 como siempre (`local_server=True`). Con `iface` (solo Linux: el nombre
de una interfaz de red de la maquina, p. ej. la de la LAN o `tailscale0`) se
crea con `local_server=False, iface=...` y pyigtl resuelve la IPv4 de esa
interfaz por `ioctl(SIOCGIFADDR)`; si la interfaz no existe o no tiene IPv4,
pyigtl intenta caer en silencio a 127.0.0.1 (en 0.3.1 esa caida falla: ver el
arreglo de abajo). Por eso aqui se comprueba a que direccion
quedo ligado el socket (`server_address`, lo que el sistema dio al `bind`) y, si
con `iface` sigue en loopback, se cierra y se lanza `IgtlInterfaceError`
(principio 7: fallar fuerte). `host` es esa direccion y el log la dice. En
Windows `iface` no vale (pyigtl ignoraria el nombre y usaria la IP del
hostname): `IgtlInterfaceError` antes de crear nada. Nombres, puerto, mensajes
y jerarquia no cambian (principio 6).

El arreglo de `--igtl-iface` en Linux (meta 007, fase 6, P-6 del 2026-11-03): pyigtl
empaqueta el nombre con `struct.pack('256s', iface[:15])`, que en Python 3 exige
`bytes`; con un `str` fallaba con `struct.error` antes de ligar nada. Aqui se le
pasa `os.fsencode(iface)`. Si la interfaz no existe o no tiene IPv4, el `ioctl` de
pyigtl falla, su `except` reintenta con `'lo'`, que es `str`, y vuelve a lanzar
`struct.error`: se captura (solo ese error, solo en esa llamada) y se convierte en
`IgtlInterfaceError`, con la causa del sistema en el mensaje. Si un pyigtl futuro
arregla su caida a `lo`, la comprobacion de loopback de abajo sigue cubriendolo.

Nagle: `TCP_NODELAY` (meta 007, fase 6, P-6 por la LAN del 2026-11-03): pyigtl 0.3.1
envia cada mensaje con `socket.sendall` y no toca las opciones del socket, asi que
Nagle sigue activo. En loopback no se nota (1.01 mensajes por `recv`), pero por la
red el emisor (Linux) retiene cada mensaje pequeno hasta el ACK, que el receptor
(Windows) retrasa ~40-50 ms: Slicer recibia rafagas de ~4 mensajes a 20 Hz con el
bucle a 88 fps. `_activar_nodelay(server)` pone `TCP_NODELAY` en el socket de cada
cliente aceptado, en las dos plataformas (el codigo no se bifurca): sustituye en la
instancia `verify_request(request, client_address)`, el gancho documentado de
`socketserver.BaseServer` (Python 3.11, Context7 `/python/cpython`) que recibe el
socket recien aceptado antes de `process_request`; `OpenIGTLinkServer` es un
`socketserver.TCPServer`. No depende de `TCPRequestHandler` ni de otros internos de
pyigtl. Para que ningun cliente se acepte antes de instalarlo (Slicer reintenta y
puede estar esperando), el servidor se crea con `start_now=False` y se arranca con
`start()` despues (las dos, API de pyigtl). Los bytes, el orden y los nombres de los
mensajes no cambian: solo se envian sin esperar al ACK (principio 6).

pyigtl 0.3.1 (leido del venv, 2026-10-24 y 2026-11-03; Context7 `/lassoan/pyigtl`
documenta `send_message(message, wait=True)`, que con `wait=False` vuelve tras
encolar, y el constructor `OpenIGTLinkServer(port=None, local_server=True,
iface=None, start_now=True)`: con `local_server=False` en Linux resuelve `iface`
(por defecto `eth0`) a su IP y cae a `lo` si falla): escucha en `(host, port)` y
arranca su hilo; `is_connected()` es True desde que un cliente entra en
`handle()` y False tras un error de envio o `stop()`; `TransformMessage(matrix,
timestamp, device_name)` exige una 4x4 y la guarda en float32; el servidor se
cierra con `stop()` (no tiene `close()`). `close()` llama a `stop()` con tope
(principio 9). `server_address` lo pone `socketserver.TCPServer.server_bind`
con `getsockname()` (Python 3.11, Context7 `/python/cpython`).
"""
from __future__ import annotations

import os
import socket
import struct
import sys
import threading
import time

import numpy as np
import pyigtl

STOP_TIMEOUT_S = 5.0
POLL_S = 0.05
DROP_LOG_AT = (1, 100, 1000)
LOOPBACK_PREFIX = "127."


class IgtlInterfaceError(RuntimeError):
    """`iface` no sirve: no es Linux, o la interfaz no existe o no tiene IPv4 (pyigtl cayo a loopback)."""


def _interface_message(iface: str, detalle: str) -> str:
    """El mensaje de una interfaz que no sirve (codigo 2 en el tracker, sin abrir la camara)."""
    return (f"[OpenIGTLink] la interfaz {iface!r} no existe o no tiene IPv4: {detalle} y Slicer "
            f"en otra maquina no podria conectarse; `ip -br addr` da los nombres validos. "
            f"No se abre la camara.")


def _bound_host(server, fallback: str) -> str:
    """La direccion a la que quedo ligado el servidor: `server_address` (lo que dio el `bind`),
    si no `host` (lo que pyigtl resolvio), si no `fallback`."""
    address = getattr(server, "server_address", None)
    if address:
        return str(address[0])
    return str(getattr(server, "host", fallback))


def _activar_nodelay(server) -> None:
    """Pone `TCP_NODELAY` en el socket de cada cliente que `server` acepte (Nagle fuera).

    Sustituye en la instancia `verify_request`, que `socketserver` llama con el socket recien
    aceptado; despues llama al de antes (el de `TCPServer` devuelve True). Si el sistema no deja
    poner la opcion, lo dice y la conexion sigue (con Nagle). Se llama antes de `start()`."""
    previo = getattr(server, "verify_request", None)
    if previo is None:
        print("[OpenIGTLink] AVISO: el servidor de pyigtl no tiene `verify_request` (ya no es un "
              "socketserver): TCP_NODELAY sin activar; por la red Slicer recibira en rafagas")
        return

    def verify_request(request, client_address) -> bool:
        try:
            request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print("[OpenIGTLink] Cliente aceptado, con TCP_NODELAY")
        except OSError as e:
            print(f"[OpenIGTLink] AVISO: no se pudo activar TCP_NODELAY ({e}); por la red "
                  f"Slicer recibira en rafagas")
        return previo(request, client_address)

    server.verify_request = verify_request


def _crear_servidor(**kwargs):
    """`pyigtl.OpenIGTLinkServer(**kwargs)` sin arrancar, con `TCP_NODELAY` instalado, y arrancado."""
    server = pyigtl.OpenIGTLinkServer(start_now=False, **kwargs)
    _activar_nodelay(server)
    server.start()
    return server


class IgtlSender:
    """Un servidor OpenIGTLink en `port` que envia transforms 4x4 por nombre.

    `iface` (solo Linux) es la interfaz de red en la que escucha; sin ella, 127.0.0.1.
    `host` es la direccion real a la que quedo ligado (se comprueba, principio 7)."""

    def __init__(self, port: int, iface: str | None = None, *, plataforma: str = sys.platform) -> None:
        self.port = int(port)
        self.iface = iface
        self.sent = 0
        self.dropped = 0
        self._server = None
        if iface is None:
            self._server = _crear_servidor(port=self.port)
            self.host = _bound_host(self._server, "127.0.0.1")
            print(f"[OpenIGTLink] Transformadas en {self.host}:{self.port}")
            return
        if not str(plataforma).startswith("linux"):
            raise IgtlInterfaceError(
                f"[OpenIGTLink] --igtl-iface {iface!r} solo existe en Linux (aqui {plataforma}); "
                f"en Windows el servidor escucha en 127.0.0.1:{self.port}, sin la opcion")
        try:
            # pyigtl hace struct.pack('256s', iface[:15]): en Python 3 el nombre va en bytes.
            self._server = _crear_servidor(port=self.port, local_server=False,
                                           iface=os.fsencode(iface))
        except struct.error as e:
            # La interfaz no dio IPv4 y pyigtl reintento con 'lo' como str: su struct.pack fallo.
            causa = e.__context__ if e.__context__ is not None else e
            raise IgtlInterfaceError(_interface_message(iface, f"el sistema no le da IPv4 ({causa})")) from e
        self.host = _bound_host(self._server, "")
        if not self.host or self.host.startswith(LOOPBACK_PREFIX):
            self.close()
            raise IgtlInterfaceError(_interface_message(
                iface, f"pyigtl cayo a loopback ({self.host or 'sin direccion'})"))
        print(f"[OpenIGTLink] Transformadas en {self.host}:{self.port} (interfaz {iface})")

    def is_connected(self) -> bool:
        return self._server is not None and bool(self._server.is_connected())

    def wait_for_client(self, timeout_s: float, poll_s: float = POLL_S) -> bool:
        """Espera a que un cliente (Slicer) se conecte, hasta `timeout_s`. True si llego."""
        deadline = time.monotonic() + float(timeout_s)
        while not self.is_connected():
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_s)
        return True

    def send(self, device_name: str, matrix: np.ndarray) -> bool:
        """Encola `matrix` (4x4) como la transform `device_name` (p. ej. ReferenceToTracker)
        sin esperar al envio. False, y cuenta en `dropped`, si no hay cliente conectado."""
        M = np.asarray(matrix, dtype=np.float64)
        if M.shape != (4, 4):
            raise ValueError(f"[OpenIGTLink] {device_name}: la matriz tiene que ser 4x4, no {M.shape}")
        if not self.is_connected():
            self.dropped += 1
            if self.dropped in DROP_LOG_AT or self.dropped % 10000 == 0:
                print(f"[OpenIGTLink] AVISO: sin cliente conectado; {self.dropped} envios no encolados")
            return False
        self._server.send_message(pyigtl.TransformMessage(M, device_name=device_name), wait=False)
        self.sent += 1
        return True

    def close(self) -> None:
        """Para el servidor (libera el puerto). Con tope: si no termina en
        STOP_TIMEOUT_S lo dice y sigue; el proceso lo libera al salir."""
        server, self._server = self._server, None
        if server is None:
            return
        t = threading.Thread(target=server.stop, daemon=True)
        t.start()
        t.join(STOP_TIMEOUT_S)
        if t.is_alive():
            print(f"[OpenIGTLink] AVISO: el servidor del puerto {self.port} no cerro en "
                  f"{STOP_TIMEOUT_S:.0f} s; el puerto se libera al salir del proceso")
        else:
            extra = f"; {self.dropped} envios sin cliente" if self.dropped else ""
            print(f"[OpenIGTLink] Servidor del puerto {self.port} cerrado ({self.sent} envios{extra})")
