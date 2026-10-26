"""De donde sale el techo de ~66 Hz en Slicer (meta 003, fase 8b; `clarify.md` P15).

Dos herramientas, sin camara, para medir el ritmo al que salen los mensajes
OpenIGTLink del servidor de `pyigtl` que usa el tracker (`transport.igtl.IgtlSender`):

- `listen`: un receptor de control que **sustituye a Slicer** como cliente del
  tracker (el servidor de pyigtl atiende a un solo cliente). Es un cliente TCP
  propio, no `pyigtl.OpenIGTLinkClient`: ese guarda solo el ultimo mensaje por
  dispositivo y sondea cada 10 ms, asi que repetiria el agrupamiento que se
  quiere medir. Anota la llegada de **cada** mensaje (`perf_counter`), en que
  `recv` llego y el `timestamp` de su cabecera, y resume: mensajes/s,
  timestamps distintos/s, ráfagas/s (llegadas a menos de `gap_ms` una de otra
  cuentan como una), mensajes por rafaga, intervalo entre rafagas y latencia.
- `bench`: un `IgtlSender` real (la clase del tracker, sin cambio) en este
  proceso y un hilo que envia `hz` matrices por segundo; el cliente es `listen`
  en otro hilo (E1) o uno de fuera, Slicer (E3, `--external`). Con
  `--timer-1ms` pide 1 ms de resolucion al temporizador de Windows
  (`timeBeginPeriod(1)`, y `timeEndPeriod(1)` en un `finally`) para ver si el
  hilo de envio de pyigtl deja de despertar en el tic de 15.6 ms.

Hipotesis que se mide (plan, fase 8b): el hilo del servidor de pyigtl hace
`recv` con tope de 10 ms y, en Windows, despierta en el tic del sistema
(~15.6 ms); al volver vacia la cola de un golpe, asi que los mensajes salen en
**rafagas a ~64 por segundo**, y Slicer se queda con una modificacion del nodo
por rafaga.

Lo que no toca: `tracker.py`, `transport/`, `camera/` y `vision/`. No importa
`cv2` ni `camera`. El nombre del dispositivo del banco es otro a proposito
(`RateProbeToTracker`), nunca `Marker0ToTracker`.

Desde codigo\\, con el venv y los argumentos explicitos (principio 7), con tope
(principio 9):

    python -m diagnostics.igtl_rate listen --port 18944 --seconds 30 --timeout 60 --device Marker0ToTracker
    python -m diagnostics.igtl_rate bench --port 18950 --hz 90 --seconds 20 --device RateProbeToTracker --timeout 10
    python -m diagnostics.igtl_rate bench --port 18944 --hz 90 --seconds 30 --device RateProbeToTracker --timeout 60 --external --timer-1ms

Sale con 0; con 1 si no llego ningun mensaje; con 3 si nadie se conecto en el
tope (como el tracker sin Slicer).

pyigtl 0.3.1 (leido del venv, 2026-10-25; Context7 `/lassoan/pyigtl` solo
documenta el cliente y `TransformMessage`): la cabecera son 58 bytes
(`MessageBase.IGTL_HEADER_SIZE`) y `MessageBase.parse_header(bytes)` da
`message_type`, `device_name`, `timestamp` y `body_size`. Python 3.11 (Context7
`/python/cpython/v3.11.14`, HOWTO de sockets): `recv` puede devolver menos bytes
de los pedidos y `b''` es la conexion cerrada; por eso el receptor junta en un
bufer y saca mensajes completos. Win32 (Context7
`/websites/learn_microsoft_en-us_windows_win32_api`): `timeBeginPeriod` pide una
resolucion minima para los temporizadores y `timeEndPeriod` la deshace; 0 es
`TIMERR_NOERROR`.
"""
from __future__ import annotations

import argparse
import csv
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pyigtl

from transport.igtl import IgtlSender

TAG = "[igtl_rate]"
HEADER_SIZE = pyigtl.MessageBase.IGTL_HEADER_SIZE          # 58
RECV_BYTES = 65536
RECV_TIMEOUT_S = 0.05        # tope de cada recv: solo para mirar el reloj y el fin
CONNECT_RETRY_S = 0.05       # el servidor puede arrancar despues que el receptor
NO_DATA_S = 5.0              # conectado y sin mensajes: para y lo dice
HOLD_S = 10.0                # tope de `hold` en listen (el banco cierra antes el servidor)
DEFAULT_GAP_MS = 1.0         # llegadas a menos de esto cuentan como una rafaga
EXTRA_SEND_S = 2.0           # el banco envia hasta que el receptor acaba, como mucho esto de mas
EXIT_OK, EXIT_NO_DATA, EXIT_NO_CONNECTION = 0, 1, 3


@dataclass
class IgtlArrival:
    """Un mensaje recibido: cuando llego y lo que dice su cabecera."""
    t_arrival: float        # perf_counter al volver el recv que lo completo
    t_wall: float           # time.time() en ese momento (para la latencia)
    device_name: str
    timestamp: float        # el de la cabecera (time.time() del emisor al crearlo)
    read_index: int         # en que recv (1, 2, ...) se completo


def _log(msg: str) -> None:
    print(f"{TAG} {msg}", flush=True)


# ----------------------------------------------------------------------------
# Mensajes
# ----------------------------------------------------------------------------

def split_messages(buffer: bytearray) -> list[tuple[dict, bytes]]:
    """Saca del bufer los mensajes completos (cabecera + cuerpo) y deja el resto.

    Cada elemento es `(cabecera, cuerpo)`, con la cabecera de `parse_header`. Un
    mensaje a medias (cabecera incompleta o cuerpo corto) se queda en `buffer`
    para el siguiente `recv`."""
    out: list[tuple[dict, bytes]] = []
    while len(buffer) >= HEADER_SIZE:
        header = pyigtl.MessageBase.parse_header(bytes(buffer[:HEADER_SIZE]))
        total = HEADER_SIZE + int(header["body_size"])
        if len(buffer) < total:
            break
        body = bytes(buffer[HEADER_SIZE:total])
        del buffer[:total]
        out.append((header, body))
    return out


# ----------------------------------------------------------------------------
# El receptor de control
# ----------------------------------------------------------------------------

def _connect(host: str, port: int, connect_timeout: float, stop: threading.Event | None,
             clock: Callable[[], float]) -> socket.socket:
    """Intenta conectar hasta `connect_timeout` s (el servidor puede no estar aun)."""
    deadline = clock() + float(connect_timeout)
    last_error: Exception | None = None
    while True:
        try:
            return socket.create_connection((host, int(port)), timeout=max(0.05, min(1.0, connect_timeout)))
        except OSError as e:
            last_error = e
        if (stop is not None and stop.is_set()) or clock() >= deadline:
            raise ConnectionError(
                f"{TAG} nadie escucha en {host}:{port} tras {connect_timeout:g} s ({last_error})")
        time.sleep(CONNECT_RETRY_S)


def listen(host: str, port: int, seconds: float, connect_timeout: float,
           device: str | None = None, stop: threading.Event | None = None,
           done: threading.Event | None = None, hold: threading.Event | None = None,
           clock: Callable[[], float] = time.perf_counter,
           wall: Callable[[], float] = time.time, log: Callable[[str], None] = _log) -> list[IgtlArrival]:
    """Se conecta como cliente a `host:port` y anota cada mensaje durante `seconds` s.

    La ventana de `seconds` empieza con el primer mensaje. Sin conexion en
    `connect_timeout`, `ConnectionError`. Conectado y sin datos durante
    `NO_DATA_S`, para y lo dice (devuelve lo que haya). Si el servidor cierra,
    para. Con `device`, solo cuenta ese dispositivo (los demas se leen y se
    tiran). `stop` (opcional) la para desde fuera; `done` se activa al acabar
    la ventana; con `hold`, el socket no se cierra hasta que se active (tope
    `HOLD_S`): el banco lo usa para que cierre primero el servidor y pyigtl no
    vea una conexion cortada."""
    sock = _connect(host, port, connect_timeout, stop, clock)
    log(f"conectado a {host}:{port}; esperando mensajes (sin datos en {NO_DATA_S:g} s, para)")
    arrivals: list[IgtlArrival] = []
    buffer = bytearray()
    read_index = 0
    others = 0
    t_first: float | None = None
    t_last_data = clock()
    try:
        sock.settimeout(RECV_TIMEOUT_S)
        while True:
            now = clock()
            if stop is not None and stop.is_set():
                break
            if t_first is not None and now >= t_first + float(seconds):
                break
            if now - t_last_data >= NO_DATA_S:
                log(f"sin datos durante {NO_DATA_S:g} s: paro ({len(arrivals)} mensajes)")
                break
            try:
                data = sock.recv(RECV_BYTES)
            except socket.timeout:
                continue
            if not data:
                log(f"el servidor cerro la conexion ({len(arrivals)} mensajes)")
                break
            t = clock()
            tw = wall()
            t_last_data = t
            read_index += 1
            buffer += data
            for header, _body in split_messages(buffer):
                name = header["device_name"]
                if device is not None and name != device:
                    others += 1
                    continue
                if t_first is None:
                    t_first = t
                arrivals.append(IgtlArrival(t, tw, name, float(header["timestamp"]), read_index))
    finally:
        if done is not None:
            done.set()
        if hold is not None:
            hold.wait(HOLD_S)
        try:
            sock.close()
        except OSError:
            pass
    if others:
        log(f"{others} mensajes de otros dispositivos, no contados")
    return arrivals


# ----------------------------------------------------------------------------
# El resumen
# ----------------------------------------------------------------------------

def _pct(values: list[float] | np.ndarray, q: float) -> float | None:
    a = np.asarray(values, dtype=np.float64)
    return float(np.percentile(a, q)) if a.size else None


def _rate(count: int, span_s: float) -> float | None:
    """Eventos por segundo: `count` eventos cuyo primero y ultimo distan `span_s`."""
    return (count - 1) / span_s if count >= 2 and span_s > 0 else None


def summarize(arrivals: list[IgtlArrival], gap_ms: float = DEFAULT_GAP_MS) -> dict:
    """Mensajes/s, timestamps distintos/s, recv con mensaje/s, rafagas/s y sus intervalos."""
    n = len(arrivals)
    res: dict = {"messages": n, "gap_ms": float(gap_ms), "duration_s": None,
                 "messages_per_s": None, "distinct_timestamps": 0, "distinct_timestamps_per_s": None,
                 "reads_with_messages": 0, "reads_per_s": None,
                 "bursts": 0, "bursts_per_s": None, "messages_per_burst_mean": None,
                 "messages_per_burst_max": None, "burst_interval_ms_p50": None,
                 "burst_interval_ms_p95": None, "burst_interval_ms_max": None,
                 "latency_ms_p50": None, "latency_ms_p95": None}
    if n == 0:
        return res
    t = np.asarray([a.t_arrival for a in arrivals], dtype=np.float64)
    order = np.argsort(t, kind="stable")
    t = t[order]
    span = float(t[-1] - t[0])
    res["duration_s"] = span
    res["messages_per_s"] = _rate(n, span)
    stamps = {a.timestamp for a in arrivals}
    res["distinct_timestamps"] = len(stamps)
    res["distinct_timestamps_per_s"] = _rate(len(stamps), span)
    reads = {a.read_index for a in arrivals}
    res["reads_with_messages"] = len(reads)
    res["reads_per_s"] = _rate(len(reads), span)
    # Rafagas: una nueva empieza cuando la llegada dista mas de gap_ms de la anterior.
    gap = float(gap_ms) / 1000.0
    starts = [0] + [i for i in range(1, n) if t[i] - t[i - 1] > gap]
    sizes = np.diff(starts + [n])
    burst_t = t[starts]
    res["bursts"] = len(starts)
    res["bursts_per_s"] = _rate(len(starts), float(burst_t[-1] - burst_t[0]))
    res["messages_per_burst_mean"] = float(sizes.mean())
    res["messages_per_burst_max"] = int(sizes.max())
    if len(starts) >= 2:
        iv = np.diff(burst_t) * 1000.0
        res["burst_interval_ms_p50"] = _pct(iv, 50)
        res["burst_interval_ms_p95"] = _pct(iv, 95)
        res["burst_interval_ms_max"] = float(iv.max())
    lat = [(a.t_wall - a.timestamp) * 1000.0 for a in arrivals]
    res["latency_ms_p50"] = _pct(lat, 50)
    res["latency_ms_p95"] = _pct(lat, 95)
    return res


def _f(x: float | None, nd: int = 1) -> str:
    return "-" if x is None else f"{x:.{nd}f}"


def format_summary(res: dict) -> str:
    """Las lineas `[igtl_rate] ...` del resumen."""
    if res["messages"] == 0:
        return f"{TAG} ningun mensaje recibido"
    lines = [
        f"{TAG} {res['messages']} mensajes en {_f(res['duration_s'], 2)} s = "
        f"{_f(res['messages_per_s'])} mensajes/s; {res['distinct_timestamps']} timestamps distintos "
        f"({_f(res['distinct_timestamps_per_s'])}/s); {res['reads_with_messages']} recv con mensaje "
        f"({_f(res['reads_per_s'])}/s)",
        f"{TAG} rafagas (hueco > {res['gap_ms']:g} ms): {res['bursts']} = {_f(res['bursts_per_s'])} rafagas/s; "
        f"mensajes por rafaga media {_f(res['messages_per_burst_mean'], 2)} max {res['messages_per_burst_max']}; "
        f"intervalo entre rafagas (ms) p50 {_f(res['burst_interval_ms_p50'], 2)} "
        f"p95 {_f(res['burst_interval_ms_p95'], 2)} max {_f(res['burst_interval_ms_max'], 2)}",
        f"{TAG} latencia t_wall - timestamp (ms): p50 {_f(res['latency_ms_p50'], 2)} "
        f"p95 {_f(res['latency_ms_p95'], 2)} (time.get_clock_info('time').resolution = "
        f"{time.get_clock_info('time').resolution * 1000:.3f} ms)",
    ]
    return "\n".join(lines)


def write_csv(arrivals: list[IgtlArrival], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(IgtlArrival.__dataclass_fields__))
        w.writeheader()
        for a in arrivals:
            w.writerow(asdict(a))


# ----------------------------------------------------------------------------
# El banco sin camara
# ----------------------------------------------------------------------------

def send_at_rate(sender, device: str, hz: float, seconds: float, stop: threading.Event | None = None,
                 clock: Callable[[], float] = time.perf_counter,
                 sleep: Callable[[float], None] = time.sleep,
                 wall: Callable[[], float] = time.time) -> dict:
    """Envia `hz` matrices por segundo durante `seconds` s por `sender.send(device, M)`.

    Cada matriz es distinta (identidad con la traslacion x = n). El ritmo va contra
    objetivos absolutos de `clock` (no se acumula el error del sleep) y sin
    espera activa, para no quitarle el GIL al hilo del servidor ni al receptor.
    Devuelve `sent`, `calls`, `duration_s`, `calls_per_s` y cuantos valores
    distintos dio `wall()` (lo que pyigtl pone de timestamp) por segundo."""
    period = 1.0 / float(hz)
    t0 = clock()
    deadline = t0 + float(seconds)
    next_t = t0
    calls = sent = 0
    stamps: set[float] = set()
    while True:
        now = clock()
        if now >= deadline or (stop is not None and stop.is_set()):
            break
        if now < next_t:
            sleep(next_t - now)
            continue
        M = np.eye(4)
        M[0, 3] = float(calls)
        stamps.add(wall())
        if sender.send(device, M):
            sent += 1
        calls += 1
        next_t += period
        if next_t < now - period:       # muy atrasado: no intenta recuperar a golpes
            next_t = now
    dt = clock() - t0
    return {"sent": sent, "calls": calls, "duration_s": dt,
            "calls_per_s": calls / dt if dt > 0 else None,
            "wall_distinct_per_s": len(stamps) / dt if dt > 0 else None}


class TimerResolution:
    """`timeBeginPeriod(1)` al entrar y `timeEndPeriod(1)` al salir (Win32, winmm)."""

    def __init__(self, period_ms: int = 1, enabled: bool = True) -> None:
        self.period_ms = int(period_ms)
        self.enabled = bool(enabled)
        self._winmm = None

    def __enter__(self):
        if not self.enabled:
            return self
        if not sys.platform.startswith("win32"):
            raise RuntimeError(f"{TAG} --timer-1ms solo existe en Windows (timeBeginPeriod)")
        import ctypes
        self._winmm = ctypes.windll.winmm
        rc = int(self._winmm.timeBeginPeriod(self.period_ms))
        if rc != 0:
            self._winmm = None
            raise RuntimeError(f"{TAG} timeBeginPeriod({self.period_ms}) devolvio {rc} (0 = TIMERR_NOERROR)")
        _log(f"timeBeginPeriod({self.period_ms}) = 0: resolucion de {self.period_ms} ms pedida para este proceso")
        return self

    def __exit__(self, *exc) -> None:
        if self._winmm is not None:
            rc = int(self._winmm.timeEndPeriod(self.period_ms))
            _log(f"timeEndPeriod({self.period_ms}) = {rc}")
            self._winmm = None


def bench(port: int, hz: float, seconds: float, device: str, external_client: bool,
          timer_1ms: bool, connect_timeout: float, gap_ms: float = DEFAULT_GAP_MS,
          log: Callable[[str], None] = _log) -> dict:
    """Un `IgtlSender` real en `port` y un hilo que envia `hz`/s durante `seconds` s.

    Con `external_client=False`, `listen` en otro hilo de este proceso es el
    cliente y su resumen va en `summary`. Con `True`, espera a que se conecte
    uno de fuera (Slicer) y `summary` es None: el numero lo da Slicer. Sin
    cliente en `connect_timeout`, `ConnectionError`. El emisor se cierra en un
    `finally` (puerto libre)."""
    res: dict = {"port": int(port), "hz": float(hz), "seconds": float(seconds), "device": device,
                 "external_client": bool(external_client), "timer_1ms": bool(timer_1ms),
                 "time_resolution_ms": time.get_clock_info("time").resolution * 1000.0,
                 "sender": None, "summary": None}
    stop, done, hold = threading.Event(), threading.Event(), threading.Event()
    holder: dict = {}

    def run_listener() -> None:
        try:
            holder["arrivals"] = listen("127.0.0.1", port, seconds, connect_timeout, device,
                                        stop=stop, done=done, hold=hold, log=log)
        except Exception as e:                       # se reporta en el hilo principal
            holder["error"] = e
            done.set()

    with TimerResolution(1, enabled=timer_1ms):
        sender = IgtlSender(port)
        listener: threading.Thread | None = None
        try:
            if not external_client:
                listener = threading.Thread(target=run_listener, name="igtl_rate.listen", daemon=True)
                listener.start()
            else:
                log(f"esperando un cliente de fuera (Slicer) en el puerto {port} hasta {connect_timeout:g} s...")
            if not sender.wait_for_client(connect_timeout):
                stop.set()
                raise ConnectionError(f"{TAG} nadie se conecto al puerto {port} en {connect_timeout:g} s")
            log(f"cliente conectado; enviando {device} a {hz:g}/s durante {seconds:g} s"
                + ("" if external_client else " (o hasta que el receptor acabe su ventana)"))
            if external_client:
                res["sender"] = send_at_rate(sender, device, hz, seconds)
            else:
                res["sender"] = send_at_rate(sender, device, hz, float(seconds) + EXTRA_SEND_S, stop=done)
            res["sender"]["dropped"] = sender.dropped
        finally:
            stop.set()                               # por si el receptor sigue leyendo
            sender.close()                           # primero el servidor...
            hold.set()                               # ...y despues el receptor suelta su socket
            if listener is not None:
                listener.join(HOLD_S + 2.0)
    if "error" in holder:
        raise holder["error"]
    if "arrivals" in holder:
        res["summary"] = summarize(holder["arrivals"], gap_ms)
        res["arrivals"] = holder["arrivals"]
    return res


def format_bench(res: dict) -> str:
    s = res["sender"] or {}
    lines = [f"{TAG} banco: puerto {res['port']}, {res['hz']:g} Hz pedidos, {res['seconds']:g} s, "
             f"dispositivo {res['device']}, cliente {'de fuera' if res['external_client'] else 'propio'}, "
             f"timer 1 ms {'si' if res['timer_1ms'] else 'no'}; "
             f"get_clock_info('time').resolution = {res['time_resolution_ms']:.3f} ms"]
    if s:
        lines.append(f"{TAG} emisor: {s['sent']} enviados de {s['calls']} llamadas en {_f(s['duration_s'], 2)} s = "
                     f"{_f(s['calls_per_s'])} llamadas/s; {s.get('dropped', 0)} sin cliente; "
                     f"time.time() dio {_f(s['wall_distinct_per_s'])} valores distintos/s")
    if res["summary"] is not None:
        lines.append(format_summary(res["summary"]))
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _positive(ap: argparse.ArgumentParser, name: str, value: float) -> None:
    if value <= 0:
        ap.error(f"{name} tiene que ser > 0")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Mide el ritmo de los mensajes OpenIGTLink del tracker, sin camara (meta 003, fase 8b).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("listen", help="receptor de control en lugar de Slicer")
    pl.add_argument("--host", default="127.0.0.1")
    pl.add_argument("--port", required=True, type=int)
    pl.add_argument("--seconds", required=True, type=float, help="ventana desde el primer mensaje")
    pl.add_argument("--timeout", required=True, type=float, help="tope de la espera de la conexion, s")
    pl.add_argument("--device", default=None, help="solo este dispositivo (p. ej. Marker0ToTracker)")
    pl.add_argument("--gap-ms", type=float, default=DEFAULT_GAP_MS)
    pl.add_argument("--csv", type=Path, default=None, help="guarda cada llegada (no se pisa)")
    pb = sub.add_parser("bench", help="emisor real en este proceso, sin camara")
    pb.add_argument("--port", required=True, type=int, help="18950 en E1; 18944 solo con Slicer y el tracker parado")
    pb.add_argument("--hz", required=True, type=float)
    pb.add_argument("--seconds", required=True, type=float)
    pb.add_argument("--device", required=True, help="RateProbeToTracker (nunca Marker0ToTracker)")
    pb.add_argument("--timeout", required=True, type=float, help="tope de la espera del cliente, s")
    pb.add_argument("--external", action="store_true", help="el cliente es de fuera (Slicer)")
    pb.add_argument("--timer-1ms", action="store_true", help="timeBeginPeriod(1) mientras dura el banco")
    pb.add_argument("--gap-ms", type=float, default=DEFAULT_GAP_MS)
    pb.add_argument("--csv", type=Path, default=None, help="guarda cada llegada del receptor propio (no se pisa)")
    args = ap.parse_args(argv)

    _positive(ap, "--seconds", args.seconds)
    _positive(ap, "--timeout", args.timeout)
    _positive(ap, "--gap-ms", args.gap_ms)
    if not 1 <= args.port <= 65535:
        ap.error("--port tiene que estar entre 1 y 65535")
    if args.csv is not None and args.csv.exists():
        ap.error(f"la salida ya existe, no se pisa: {args.csv}")

    if args.cmd == "listen":
        try:
            arrivals = listen(args.host, args.port, args.seconds, args.timeout, args.device)
        except ConnectionError as e:
            print(e)
            return EXIT_NO_CONNECTION
        print(format_summary(summarize(arrivals, args.gap_ms)))
        if args.csv is not None and arrivals:
            write_csv(arrivals, args.csv)
            _log(f"guardado {args.csv}")
        return EXIT_OK if arrivals else EXIT_NO_DATA

    _positive(ap, "--hz", args.hz)
    try:
        res = bench(args.port, args.hz, args.seconds, args.device, args.external, args.timer_1ms,
                    args.timeout, args.gap_ms)
    except ConnectionError as e:
        print(e)
        return EXIT_NO_CONNECTION
    print(format_bench(res))
    if args.csv is not None and res.get("arrivals"):
        write_csv(res["arrivals"], args.csv)
        _log(f"guardado {args.csv}")
    if res["external_client"]:
        return EXIT_OK if res["sender"]["sent"] else EXIT_NO_DATA
    return EXIT_OK if res["summary"]["messages"] else EXIT_NO_DATA


if __name__ == "__main__":
    sys.exit(main())
