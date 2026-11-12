"""Frames sinteticos y falsos para las pruebas del tracker sin camara (meta 003, fases 1, 4 y 7).

pytest no recoge este archivo (no empieza por `test_`).

Fase 7: el tracker lee la camara en un hilo (`camera.grabber.FrameGrabber`) y
procesa siempre el ultimo frame. Para que una prueba vea todos los frames de la
camara falsa en orden, `FakeCamera` tarda `delay_s` en entregar cada uno (20 ms
por defecto: el bucle procesa un frame de 640x480 en ~3 ms, asi que alcanza a
procesar cada frame antes de que llegue el siguiente); las lecturas fallidas
(None) no tardan. `fake_time()` da el modulo `time` falso que el tracker usa
(`perf_counter` avanza un paso fijo por llamada; `time` tambien, aparte).

Meta 006, fase 7c (B55): `render_marker` dibuja por defecto la referencia del perfil gs1
del repo (`REFERENCE_ID`, `REFERENCE_MM`, leidos al importar), no el ID 0 de 80 mm: las
pruebas que pasan un frame sintetico por el perfil del repo siguen al perfil. Fase 7c2
(P57): la referencia es la entrada `Reference` (`profiles.reference_marker`); hasta
entonces las constantes se llamaban `MARKER0_ID` y `MARKER0_MM`.
"""
from __future__ import annotations

import itertools
import time
import types

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

import profiles

K_SYN = np.array([[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]])
DIST_SYN = np.zeros((1, 5))
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_MIP_36h12)
FAKE_DELAY_S = 0.02
FAKE_STEP_S = 0.011


def _referencia_del_perfil() -> tuple[int, float]:
    """El ID y el lado (mm) de la referencia del perfil gs1 del repo."""
    perfil = profiles.PROFILES_DIR / "tracker_config_gs1.yaml"
    ref = profiles.reference_marker(profiles.load(perfil)["markers"]["list"])
    if ref["name"] != profiles.REFERENCE_NAME:
        raise ValueError(f"{perfil.name}: la referencia se llama {ref['name']!r}, no {profiles.REFERENCE_NAME!r}")
    return int(ref["id"]), float(ref["size_mm"])


REFERENCE_ID, REFERENCE_MM = _referencia_del_perfil()


def render_marker(tz: float, tx: float, marker_id: int = REFERENCE_ID, size_mm: float = REFERENCE_MM,
                  K: np.ndarray = K_SYN, dist: np.ndarray = DIST_SYN,
                  shape: tuple[int, int] = (480, 640), euler_xy=(185.0, 5.0)) -> np.ndarray:
    """Un marker del diccionario del tracker proyectado con `K` a (tx, 5, tz) mm,
    de frente a la camara (giro 185 grados en x y 5 en y), sobre fondo gris. BGR."""
    side, pad = 240, 48
    canvas = np.full((side + 2 * pad, side + 2 * pad), 255, np.uint8)
    canvas[pad:pad + side, pad:pad + side] = cv2.aruco.generateImageMarker(DICT, marker_id, side)
    half = (side / 2 + pad) * size_mm / side
    obj = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]])
    rvec = Rotation.from_euler("xy", list(euler_xy), degrees=True).as_rotvec()
    img_pts, _ = cv2.projectPoints(obj, rvec, np.array([tx, 5.0, tz]), K, dist)
    w = float(side + 2 * pad)
    src = np.array([[0, 0], [w, 0], [w, w], [0, w]], np.float32)
    H = cv2.getPerspectiveTransform(src, img_pts.reshape(4, 2).astype(np.float32))
    gray = cv2.warpPerspective(canvas, H, (shape[1], shape[0]), borderValue=110)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def fake_time(step_s: float = FAKE_STEP_S, t0: float = 1000.0) -> types.SimpleNamespace:
    """Un `time` falso para `tracker`: `perf_counter` avanza `step_s` por llamada desde `t0`
    (es el reloj del bucle y del 1-Euro); `time` avanza igual, aparte, desde 1.7e9."""
    perf = itertools.count()
    wall = itertools.count()
    return types.SimpleNamespace(perf_counter=lambda: t0 + step_s * next(perf),
                                 time=lambda: 1.7e9 + step_s * next(wall))


class FakeCamera:
    """Entrega `frames` en orden, uno cada `delay_s`; al acabarse lanza KeyboardInterrupt
    (como Ctrl-C) salvo que `loop` sea True (vuelve a empezar). None en la lista cuenta
    como lectura fallida y no tarda."""

    def __init__(self, frames: list, loop: bool = False,
                 K: np.ndarray = K_SYN, dist: np.ndarray = DIST_SYN,
                 delay_s: float = FAKE_DELAY_S) -> None:
        self.frames, self.i, self.loop = list(frames), 0, loop
        self.K, self.dist = K, dist
        self.delay_s = float(delay_s)
        self.opened = self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self):
        if self.i >= len(self.frames):
            if not self.loop:
                raise KeyboardInterrupt
            self.i = 0
        f = self.frames[self.i]
        self.i += 1
        if f is None:
            return None, None, None
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        return f, None, 0.0

    def get_intrinsics(self):
        return self.K.copy(), self.dist.copy()

    def close(self) -> None:
        self.closed = True


class FakeSender:
    """Un `transport.igtl.IgtlSender` falso: guarda (nombre, matriz float32), como pyigtl.
    `connected` (True por defecto) es lo que responde `wait_for_client`; con False el
    tracker aborta por falta de Slicer. `iface` y `host` como el real (meta 007, fase 6):
    sin interfaz, 127.0.0.1; con una que este en `ifaces`, su IP; con otra,
    `IgtlInterfaceError` (lo que el real hace cuando pyigtl cae a loopback)."""
    instances: list["FakeSender"] = []
    connected: bool = True
    ifaces: dict[str, str] = {}

    def __init__(self, port: int, iface: str | None = None) -> None:
        from transport.igtl import IgtlInterfaceError
        self.port, self.sent, self.closed = int(port), [], False
        self.waited: list[float] = []
        self.dropped = 0
        self.iface = iface
        if iface is None:
            self.host = "127.0.0.1"
        elif iface in FakeSender.ifaces:
            self.host = FakeSender.ifaces[iface]
        else:
            raise IgtlInterfaceError(f"[OpenIGTLink] la interfaz {iface!r} no existe o no tiene IPv4")
        FakeSender.instances.append(self)

    def wait_for_client(self, timeout_s: float) -> bool:
        self.waited.append(float(timeout_s))
        return FakeSender.connected

    def is_connected(self) -> bool:
        return FakeSender.connected

    def send(self, device_name: str, matrix) -> bool:
        self.sent.append((device_name, np.asarray(matrix, dtype=np.float32)))
        return True

    def close(self) -> None:
        self.closed = True


def servidor_pyigtl_sin_puerto() -> type:
    """El `OpenIGTLinkServer` real de pyigtl, con su `__init__` tal cual (la resolucion de
    `iface` incluida), pero sin ligar ni escuchar ningun puerto ni arrancar sus hilos, y
    devolviendo los manejadores de senal que pyigtl instala (meta 007, fase 6: el arreglo de
    `--igtl-iface`). `server_address` queda en el `(host, port)` que pyigtl resolvio. Se usa
    con `monkeypatch.setattr(pyigtl, "OpenIGTLinkServer", ...)`, que pisa al de `conftest`."""
    import signal

    from pyigtl import comm

    class ServidorSinPuerto(comm.OpenIGTLinkServer):
        instances: list = []

        def __init__(self, *args, **kwargs) -> None:
            self.stopped = 0
            super().__init__(*args, **kwargs)
            for signum, previo in self._previous_signal_handlers.items():
                if previo is not None:
                    signal.signal(signum, previo)
            ServidorSinPuerto.instances.append(self)

        def server_bind(self) -> None:          # sin bind: no se toma el puerto
            pass

        def server_activate(self) -> None:      # sin listen
            pass

        def start(self) -> None:                # sin serve_forever ni el hilo que imprime
            pass

        def stop(self) -> None:                 # sin shutdown(): no hay serve_forever que parar
            self.server_close()
            self.stopped += 1

    return ServidorSinPuerto
