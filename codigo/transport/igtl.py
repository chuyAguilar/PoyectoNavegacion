"""`IgtlSender`: el servidor OpenIGTLink del tracker y el envio de una transform.

Era el trozo de `tracker.main()` que creaba `pyigtl.OpenIGTLinkServer(port=...)`
y enviaba `pyigtl.TransformMessage(M, device_name=...)` (meta 003, fase 4).
Las llamadas son las mismas: `send_message` con su `wait=True` por defecto, que
espera a que la cola se vacie; sin un cliente conectado no se vacia nunca, asi
que Slicer se conecta ANTES de arrancar el tracker (`docs/CONTEXT.md` 4.5).

pyigtl 0.3.1 (leido del venv, 2026-10-24; Context7 no lo tiene):
`OpenIGTLinkServer(port=None, local_server=True, iface=None, start_now=True)`
escucha en 127.0.0.1 y arranca su hilo; `TransformMessage(matrix, timestamp,
device_name)` exige una 4x4 y la guarda en float32; el servidor se cierra con
`stop()` (no tiene `close()`: el `server_tx.close()` del tracker de antes
lanzaba AttributeError dentro de un `except Exception: pass` y no cerraba nada).
`close()` llama a `stop()` con tope de tiempo (principio 9).
"""
from __future__ import annotations

import threading

import numpy as np
import pyigtl

STOP_TIMEOUT_S = 5.0


class IgtlSender:
    """Un servidor OpenIGTLink en `port` que envia transforms 4x4 por nombre."""

    def __init__(self, port: int) -> None:
        self.port = int(port)
        self._server = pyigtl.OpenIGTLinkServer(port=self.port)
        self.sent = 0
        print(f"[OpenIGTLink] Transformadas en puerto {self.port}")

    def is_connected(self) -> bool:
        return bool(self._server.is_connected())

    def send(self, device_name: str, matrix: np.ndarray) -> None:
        """Envia `matrix` (4x4) como la transform `device_name` (p. ej. Marker0ToTracker)."""
        M = np.asarray(matrix, dtype=np.float64)
        if M.shape != (4, 4):
            raise ValueError(f"[OpenIGTLink] {device_name}: la matriz tiene que ser 4x4, no {M.shape}")
        self._server.send_message(pyigtl.TransformMessage(M, device_name=device_name))
        self.sent += 1

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
            print(f"[OpenIGTLink] Servidor del puerto {self.port} cerrado")
