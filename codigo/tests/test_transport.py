"""`transport.igtl.IgtlSender` con un servidor pyigtl falso (meta 003, fase 4): el
servidor se crea en el puerto pedido, `send` manda un `TransformMessage` 4x4 con
su nombre (`Marker0ToTracker`), una matriz que no es 4x4 falla antes de enviar,
`close` para el servidor una sola vez y con tope.
"""
from __future__ import annotations

import time

import numpy as np
import pyigtl
import pytest

from transport import igtl


class FakeServer:
    instances: list["FakeServer"] = []

    def __init__(self, port=None, **kw) -> None:
        self.port, self.kw, self.messages, self.stopped = port, kw, [], 0
        self.hang_s = 0.0
        FakeServer.instances.append(self)

    def send_message(self, message, wait=True) -> bool:
        self.messages.append((message, wait))
        return True

    def is_connected(self) -> bool:
        return True

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
    assert "[OpenIGTLink] Transformadas en puerto 18944" in capsys.readouterr().out
    M = np.eye(4)
    M[:3, 3] = [1.5, -2.5, 450.25]
    s.send("Marker0ToTracker", M)
    (msg, wait), = fake_server.instances[0].messages
    assert isinstance(msg, pyigtl.TransformMessage)
    assert msg.device_name == "Marker0ToTracker" and wait is True      # espera a que la cola se vacie, como antes
    assert msg.matrix.dtype == np.float32 and np.array_equal(msg.matrix, M.astype(np.float32))
    assert s.sent == 1 and s.is_connected()


def test_sender_rechaza_lo_que_no_es_4x4(fake_server) -> None:
    s = igtl.IgtlSender(18944)
    with pytest.raises(ValueError, match="4x4"):
        s.send("Marker0ToTracker", np.eye(3))
    assert fake_server.instances[0].messages == [] and s.sent == 0


def test_close_para_el_servidor_una_vez(fake_server, capsys) -> None:
    s = igtl.IgtlSender(18944)
    s.close()
    s.close()
    assert fake_server.instances[0].stopped == 1
    assert "cerrado" in capsys.readouterr().out


def test_close_con_tope_si_el_servidor_no_termina(fake_server, monkeypatch, capsys) -> None:
    monkeypatch.setattr(igtl, "STOP_TIMEOUT_S", 0.2)
    s = igtl.IgtlSender(18944)
    fake_server.instances[0].hang_s = 1.0
    t0 = time.monotonic()
    s.close()
    assert time.monotonic() - t0 < 0.9
    assert "no cerro en 0 s" in capsys.readouterr().out
