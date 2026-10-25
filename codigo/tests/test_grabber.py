"""`camera.grabber.FrameGrabber` con una camara falsa controlada por eventos (meta 003,
fase 7 · Subir los fps con ventana): entrega el ultimo frame y cuenta los saltados,
espera con tope y devuelve None sin frame, se da por perdida tras `max_failures`
lecturas fallidas seguidas, relanza en el hilo del bucle la excepcion de `cam.read()`
y `stop` espera al hilo con tope. Ninguna prueba abre una camara (B34).
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from camera import grabber as gr
from camera.grabber import FrameGrabber


class GatedCamera:
    """Entrega `frames` sin tardar y, al acabarse, se queda bloqueada en `gate` (como una
    camara que no entrega mas) hasta que la prueba la suelta. `drained` avisa de que ya
    entrego todo. `error` se lanza en vez del primer frame si se da."""

    def __init__(self, frames, error: BaseException | None = None) -> None:
        self.frames = list(frames)
        self.i = 0
        self.gate = threading.Event()
        self.drained = threading.Event()
        self.error = error
        self.reads = 0

    def read(self):
        self.reads += 1
        if self.error is not None:
            e, self.error = self.error, None
            raise e
        if self.i < len(self.frames):
            f = self.frames[self.i]
            self.i += 1
            return (f, None, 0.0) if f is not None else (None, None, None)
        self.drained.set()
        self.gate.wait(5.0)
        self.gate.clear()
        return None, None, None


class StepClock:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> float:
        self.n += 1
        return 100.0 + 0.01 * self.n


def _frames(n: int) -> list[np.ndarray]:
    return [np.full((4, 4, 3), i, np.uint8) for i in range(1, n + 1)]


def _stopped(g: FrameGrabber, cam: GatedCamera) -> None:
    cam.gate.set()
    assert g.stop(timeout=2.0) is True


def test_entrega_el_ultimo_frame_y_cuenta_los_saltados() -> None:
    cam = GatedCamera(_frames(5))
    clk = StepClock()
    g = FrameGrabber(cam, clock=clk, max_failures=3)
    g.start()
    assert cam.drained.wait(2.0)                       # el hilo leyo los 5 antes de que nadie pida
    frame, t, seq = g.next_frame(0.5)
    assert int(frame[0, 0, 0]) == 5 and seq == 5 and t == pytest.approx(100.05)
    assert g.frames_read == 5 and g.delivered == 1 and g.skipped == 4
    assert g.next_frame(0.05) is None                  # nada nuevo: tope y None, sin fallo
    assert g.failed is False and g.running
    _stopped(g, cam)
    assert not g.running


def test_el_bucle_al_ritmo_de_la_camara_ve_todos_los_frames() -> None:
    """Si el consumidor pide antes de cada lectura, no se salta ninguno: la camara espera
    en la compuerta entre frames."""
    cam = GatedCamera([])                              # bloqueada desde la primera lectura
    g = FrameGrabber(cam, clock=StepClock())
    g.start()
    assert cam.drained.wait(2.0)
    vistos = []
    for k in range(1, 4):
        cam.frames.append(np.full((2, 2, 3), k, np.uint8))
        cam.drained.clear()
        cam.gate.set()                                 # suelta una lectura: entrega el frame k
        got = g.next_frame(1.0)
        assert got is not None
        vistos.append(int(got[0][0, 0, 0]))
        assert cam.drained.wait(2.0)                   # y vuelve a esperar
    assert vistos == [1, 2, 3] and g.skipped == 0 and g.delivered == 3
    _stopped(g, cam)


def test_se_da_por_perdida_tras_max_failures_y_avisa(capsys) -> None:
    cam = GatedCamera([None] * 10)
    g = FrameGrabber(cam, clock=StepClock(), max_failures=3)
    g.start()
    t0 = time.monotonic()
    assert g.next_frame(2.0) is None
    assert time.monotonic() - t0 < 1.5                 # no espero el tope: el fallo despierta
    assert g.failed is True and g.consecutive_failures == 4 and g.failures == 4
    assert g.stop(timeout=2.0) is True and cam.reads == 4   # paro solo, sin agotar la lista
    out = capsys.readouterr().out
    assert "[WARN] cam.read() retornando None (1 consecutivos)" in out
    assert "(3 consecutivos)" in out and "(2 consecutivos)" not in out


def test_se_recupera_tras_fallos_y_lo_dice(capsys) -> None:
    cam = GatedCamera([None, None, np.zeros((2, 2, 3), np.uint8)])
    g = FrameGrabber(cam, clock=StepClock(), max_failures=10)
    g.start()
    got = g.next_frame(2.0)
    assert got is not None and g.consecutive_failures == 0 and g.failures == 2 and not g.failed
    assert "[Camara] Recuperada tras 2 fallos" in capsys.readouterr().out
    _stopped(g, cam)


class Boom(RuntimeError):
    pass


class BoomCamera:
    """Dos frames y, al agotarse, una excepcion en `read()` (un error del backend)."""

    def __init__(self) -> None:
        self.frames, self.i = _frames(2), 0

    def read(self):
        if self.i < len(self.frames):
            f = self.frames[self.i]
            self.i += 1
            return f, None, 0.0
        raise Boom("usb")


def test_la_excepcion_de_read_llega_al_bucle_una_vez() -> None:
    g = FrameGrabber(BoomCamera(), clock=StepClock())
    g.start()
    got = g.next_frame(2.0)                            # el ultimo frame leido llega antes del error
    assert got is not None and got[2] == 2
    with pytest.raises(Boom, match="usb"):
        g.next_frame(2.0)
    assert g.next_frame(0.05) is None                  # la excepcion se relanza una sola vez
    assert g.stop(timeout=2.0) is True and not g.running


def test_keyboard_interrupt_de_la_camara_falsa_se_relanza() -> None:
    cam = GatedCamera([], error=KeyboardInterrupt())
    g = FrameGrabber(cam, clock=StepClock())
    g.start()
    with pytest.raises(KeyboardInterrupt):
        g.next_frame(2.0)
    assert g.stop(timeout=2.0) is True


def test_stop_con_tope_si_read_sigue_bloqueado(capsys) -> None:
    cam = GatedCamera([])
    g = FrameGrabber(cam, clock=StepClock())
    g.start()
    assert cam.drained.wait(2.0)
    t0 = time.monotonic()
    assert g.stop(timeout=0.2) is False                # read() sigue en la compuerta
    assert 0.15 <= time.monotonic() - t0 < 1.5
    assert "no termino en 0 s" in capsys.readouterr().out
    cam.gate.set()
    assert g.stop(timeout=2.0) is True
    with pytest.raises(RuntimeError, match="ya arrancado"):
        g.start()


def test_sin_arrancar_stop_es_inocuo_y_constantes() -> None:
    g = FrameGrabber(GatedCamera([]), clock=StepClock())
    assert g.stop() is True and not g.running and g.frames_read == 0 and g.skipped == 0
    assert g.mode == "thread" and gr.SyncGrabber.mode == "sync"
    assert gr.JOIN_TIMEOUT_S == 2.0 and gr.WARN_AT == (1, 30, 100)


def test_sync_grabber_lee_en_el_hilo_del_bucle(capsys) -> None:
    """`SyncGrabber`: misma interfaz, sin hilo; cada `next_frame` es un `cam.read()`."""
    cam = GatedCamera([None, *_frames(3)])
    g = gr.SyncGrabber(cam, clock=StepClock(), max_failures=1)
    g.start()
    assert not g.running
    assert g.next_frame(0.1) is None and g.failures == 1 and not g.failed
    vistos = [int(g.next_frame(0.1)[0][0, 0, 0]) for _ in range(3)]
    assert vistos == [1, 2, 3] and g.frames_read == 3 and g.delivered == 3 and g.skipped == 0
    assert cam.reads == 4
    out = capsys.readouterr().out
    assert "(1 consecutivos)" in out and "Recuperada tras 1 fallos" in out
    assert g.stop() is True
    g2 = gr.SyncGrabber(GatedCamera([None, None, None]), clock=StepClock(), max_failures=1)
    assert g2.next_frame(0.1) is None and g2.next_frame(0.1) is None and g2.failed is True
