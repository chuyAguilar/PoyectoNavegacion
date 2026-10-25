"""Hilo de captura con el ultimo frame (meta 003, fase 7 · Subir los fps con
ventana; ADR-028 propuesto).

`FrameGrabber` llama a `cam.read()` sin parar en un hilo propio y guarda el
ultimo frame con su hora de captura (`clock`, por defecto `time.perf_counter`)
y un numero de secuencia. El bucle del tracker pide `next_frame(timeout)`: el
ultimo frame que todavia no ha visto o, si no hay ninguno nuevo, espera en una
`threading.Condition` hasta `timeout` segundos y devuelve None (principio 9:
ninguna espera sin tope). Lo que la camara entrega mientras el bucle trabaja se
pisa: se procesa siempre el frame mas reciente, y `skipped` cuenta los leidos
que no se procesaron. Asi la lectura (~8 ms a 90 fps) no se suma al trabajo
del bucle y la latencia no crece aunque el bucle vaya mas lento que la camara.

Solo el hilo toca `cam`: la API de `VideoCapture` es sincrona y la clase no es
thread-safe (OpenCV 4.13, nota del tutorial Orbbec/OpenNI; instalado 4.11).
Por eso `stop()` para el hilo y espera a que termine ANTES de que el tracker
llame a `cam.close()`.

Fallos: una lectura que devuelve None cuenta como fallo consecutivo (avisos en
1, 30, 100 y `max_failures`, como hacia el bucle); al pasar de `max_failures`
seguidos el hilo para y `failed` queda en True. Una excepcion dentro de
`cam.read()` se guarda y `next_frame` la relanza en el hilo del tracker, asi
que un error del backend (o el `KeyboardInterrupt` de la camara falsa de las
pruebas) llega al bucle como antes, despues del ultimo frame leido.

`SyncGrabber` es la captura de antes (leer en el bucle) con la misma interfaz:
`tracker --sync-capture` la usa para medir una variable a la vez (principio 3).

Context7 (2026-10-24): `threading.Condition.wait_for(predicate, timeout)`
devuelve el ultimo valor del predicado (False si vencio el tope);
`time.perf_counter` es el reloj de mayor resolucion y solo valen diferencias
(CPython 3.11).
"""
from __future__ import annotations

import threading
import time
from typing import Callable

JOIN_TIMEOUT_S = 2.0
WARN_AT = (1, 30, 100)


class _GrabberBase:
    """Lo comun a las dos capturas: contadores, avisos de fallo y `skipped`."""

    mode = ""

    def __init__(self, cam, clock: Callable[[], float] = time.perf_counter,
                 max_failures: int = 300) -> None:
        self._cam = cam
        self._clock = clock
        self.max_failures = int(max_failures)
        self._seq = 0              # frames leidos con exito
        self.delivered = 0
        self.failed = False
        self.failures = 0
        self.consecutive_failures = 0

    @property
    def frames_read(self) -> int:
        """Frames que la camara entrego (con exito) desde `start`."""
        return self._seq

    @property
    def skipped(self) -> int:
        """Frames leidos que el bucle no proceso (pisados por uno mas nuevo; al
        parar, como mucho uno esta todavia pendiente)."""
        return self._seq - self.delivered

    def _count_failure(self) -> bool:
        """Un None de `cam.read()`: avisa en WARN_AT y en max_failures; True si ya son demasiados."""
        self.failures += 1
        self.consecutive_failures += 1
        n = self.consecutive_failures
        if n in WARN_AT or n == self.max_failures:
            print(f"[WARN] cam.read() retornando None ({n} consecutivos)")
        if n > self.max_failures:
            self.failed = True
        return self.failed

    def _count_success(self) -> None:
        if self.consecutive_failures:
            print(f"[Camara] Recuperada tras {self.consecutive_failures} fallos")
            self.consecutive_failures = 0
        self._seq += 1


class SyncGrabber(_GrabberBase):
    """La captura de antes de la fase 7, con la interfaz de `FrameGrabber`: `next_frame`
    llama a `cam.read()` en el hilo del bucle (bloquea lo que bloquee la camara; el
    `timeout` no aplica). Es `tracker --sync-capture`: sirve para medir una variable a la
    vez (el envio sin esperar, E1, sin el hilo de captura, C1) y para comparar."""

    mode = "sync"

    @property
    def running(self) -> bool:
        return False

    def start(self) -> None:
        """No hay hilo que arrancar."""

    def next_frame(self, timeout: float):
        frame, _depth, _ts = self._cam.read()
        if frame is None:
            self._count_failure()
            return None
        t = self._clock()
        self._count_success()
        self.delivered += 1
        return frame, t, self._seq

    def stop(self, timeout: float = JOIN_TIMEOUT_S) -> bool:
        return True


class FrameGrabber(_GrabberBase):
    """Lee `cam.read()` en un hilo y entrega siempre el ultimo frame."""

    mode = "thread"

    def __init__(self, cam, clock: Callable[[], float] = time.perf_counter,
                 max_failures: int = 300) -> None:
        super().__init__(cam, clock, max_failures)
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame = None
        self._t = 0.0
        self._delivered_seq = 0    # secuencia del ultimo que devolvio next_frame
        self._error: BaseException | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- el hilo ----------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("FrameGrabber ya arrancado")
        self._thread = threading.Thread(target=self._run, name="capture", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                frame, _depth, _ts = self._cam.read()
                if frame is None:
                    self._on_failure()
                    continue
                t = self._clock()
                with self._cond:
                    self._count_success()
                    self._frame, self._t = frame, t
                    self._cond.notify_all()
        except BaseException as e:  # noqa: BLE001  (se relanza en el hilo del tracker)
            with self._cond:
                self._error = e
                self._cond.notify_all()

    def _on_failure(self) -> None:
        with self._cond:
            if self._count_failure():
                self._stop.set()
                self._cond.notify_all()

    def _ready(self) -> bool:
        return self._seq > self._delivered_seq or self._error is not None or self.failed

    # ---- lo que usa el bucle ---------------------------------------------

    def next_frame(self, timeout: float):
        """`(frame, t, seq)` del ultimo frame no entregado; None si no llego ninguno
        en `timeout` s o si la camara se dio por perdida (`failed`). Relanza la
        excepcion que haya parado al hilo, una sola vez, despues del ultimo frame."""
        with self._cond:
            self._cond.wait_for(self._ready, timeout)
            if self._seq > self._delivered_seq:
                self._delivered_seq = self._seq
                self.delivered += 1
                return self._frame, self._t, self._seq
            if self._error is not None:
                e, self._error = self._error, None
                raise e
            return None

    def stop(self, timeout: float = JOIN_TIMEOUT_S) -> bool:
        """Pide parar y espera al hilo hasta `timeout` s. True si termino. Si
        `cam.read()` sigue bloqueado lo dice y devuelve False: quien cierra la
        camara decide (principio 9: no se espera sin fin)."""
        self._stop.set()
        t = self._thread
        if t is None:
            return True
        t.join(timeout)
        if t.is_alive():
            print(f"[Camara] AVISO: el hilo de captura no termino en {timeout:.0f} s "
                  f"(cam.read() sigue bloqueado)")
            return False
        return True
