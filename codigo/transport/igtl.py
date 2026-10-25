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

pyigtl 0.3.1 (leido del venv, 2026-10-24; Context7 `/lassoan/pyigtl` solo
documenta la firma `send_message(message, wait=True)` y que con `wait=False`
vuelve tras encolar): `OpenIGTLinkServer(port=None, local_server=True,
iface=None, start_now=True)` escucha en 127.0.0.1 y arranca su hilo;
`is_connected()` es True desde que un cliente entra en `handle()` y False tras
un error de envio o `stop()`; `TransformMessage(matrix, timestamp,
device_name)` exige una 4x4 y la guarda en float32; el servidor se cierra con
`stop()` (no tiene `close()`). `close()` llama a `stop()` con tope (principio 9).
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pyigtl

STOP_TIMEOUT_S = 5.0
POLL_S = 0.05
DROP_LOG_AT = (1, 100, 1000)


class IgtlSender:
    """Un servidor OpenIGTLink en `port` que envia transforms 4x4 por nombre."""

    def __init__(self, port: int) -> None:
        self.port = int(port)
        self._server = pyigtl.OpenIGTLinkServer(port=self.port)
        self.sent = 0
        self.dropped = 0
        print(f"[OpenIGTLink] Transformadas en puerto {self.port}")

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
