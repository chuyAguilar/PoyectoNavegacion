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
pyigtl cae en silencio a 127.0.0.1. Por eso aqui se comprueba a que direccion
quedo ligado el socket (`server_address`, lo que el sistema dio al `bind`) y, si
con `iface` sigue en loopback, se cierra y se lanza `IgtlInterfaceError`
(principio 7: fallar fuerte). `host` es esa direccion y el log la dice. En
Windows `iface` no vale (pyigtl ignoraria el nombre y usaria la IP del
hostname): `IgtlInterfaceError` antes de crear nada. Nombres, puerto, mensajes
y jerarquia no cambian (principio 6).

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


def _bound_host(server, fallback: str) -> str:
    """La direccion a la que quedo ligado el servidor: `server_address` (lo que dio el `bind`),
    si no `host` (lo que pyigtl resolvio), si no `fallback`."""
    address = getattr(server, "server_address", None)
    if address:
        return str(address[0])
    return str(getattr(server, "host", fallback))


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
            self._server = pyigtl.OpenIGTLinkServer(port=self.port)
            self.host = _bound_host(self._server, "127.0.0.1")
            print(f"[OpenIGTLink] Transformadas en {self.host}:{self.port}")
            return
        if not str(plataforma).startswith("linux"):
            raise IgtlInterfaceError(
                f"[OpenIGTLink] --igtl-iface {iface!r} solo existe en Linux (aqui {plataforma}); "
                f"en Windows el servidor escucha en 127.0.0.1:{self.port}, sin la opcion")
        self._server = pyigtl.OpenIGTLinkServer(port=self.port, local_server=False, iface=iface)
        self.host = _bound_host(self._server, "")
        if not self.host or self.host.startswith(LOOPBACK_PREFIX):
            self.close()
            raise IgtlInterfaceError(
                f"[OpenIGTLink] la interfaz {iface!r} no existe o no tiene IPv4: pyigtl cayo a "
                f"loopback ({self.host or 'sin direccion'}) y Slicer en otra maquina no podria "
                f"conectarse; `ip -br addr` da los nombres validos. No se abre la camara.")
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
        """Encola `matrix` (4x4) como la transform `device_name` (p. ej. Marker0ToTracker)
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
