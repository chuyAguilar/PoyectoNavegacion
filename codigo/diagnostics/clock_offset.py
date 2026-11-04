"""El desfase entre el reloj de la Jetson y el del PC (meta 007, fase 6; plan, hallazgo 5).

`diagnostics.igtl_rate listen` mide la latencia tracker -> cliente restando el
`timestamp` de cada mensaje (el `time.time()` del emisor) de la hora de llegada
(`time.time()` del receptor). Con el tracker en la Jetson y el cliente en el PC,
eso resta dos relojes distintos: hace falta medir su desfase aparte y pasarlo
con `--clock-offset-ms`. Esto es ese medidor: un eco por UDP con cuatro marcas
de tiempo, como NTP en pequeno:

- `serve`, en la Jetson: escucha datagramas en `--bind:--port` durante `--timeout`
  s y devuelve cada uno con dos marcas suyas, al recibir (t2) y al contestar (t3).
- `measure`, en el PC: manda `--samples` peticiones cada `--interval-ms`, anota al
  enviar (t1) y al recibir la respuesta (t4), y estima el desfase.

Por muestra: desfase = ((t2 - t1) + (t3 - t4)) / 2 y RTT = (t4 - t1) - (t3 - t2),
con el signo **reloj del servidor (Jetson) menos reloj de aqui (PC)**: es lo
que `igtl_rate listen --clock-offset-ms` suma a `t_wall - timestamp`. La
estimacion es la mediana del desfase de las muestras con menor RTT (el cuarto
mejor, al menos 3): el error de una muestra esta acotado por su RTT/2, y el RTT
minimo da la incertidumbre que se reporta (plan, fase 6: +-RTT min/2).

El reloj de pared de este modulo es `wall_ns()`: en Windows,
`GetSystemTimePreciseAsFileTime` (kernel32, precision < 1 us), porque
`time.time()` en este venv va por `GetSystemTimeAsFileTime` con resolucion de
15.625 ms (o 1 ms si otro programa pidio el temporizador fino), demasiado gruesa
para una latencia de red de pocos ms; en Linux, `time.time_ns()`. `igtl_rate`
lo usa tambien para la hora de llegada. Los `timestamp` que pone pyigtl en la
Jetson siguen siendo `time.time()` de Linux, que si es fino.

Solo biblioteca estandar; no abre camara ni toca el 18944. Desde codigo\\, con el
venv, argumentos explicitos (principio 7) y tope (principio 9):

    python -m diagnostics.clock_offset serve --bind 0.0.0.0 --port 18960 --timeout 300
    python -m diagnostics.clock_offset measure --host <IP de la Jetson> --port 18960 --samples 200 --interval-ms 20 --timeout 30 --output <salida>.json

`serve` sale con 0 si contesto algo y con 1 si nadie le hablo en el tope.
`measure` sale con 0; con 1 si hubo menos de 3 respuestas; con 3 si no hubo
ninguna (nadie escucha, como el tracker sin Slicer). `--output` no se pisa.

Context7 (2026-11-03): Python 3.11 (`/python/cpython/v3.11.14`): `socket.SOCK_DGRAM`
con `sendto`/`recvfrom` y `settimeout` para el eco; `struct` para el formato de
red (`!`). Win32 (`/websites/learn_microsoft_en-us_windows_win32_api`): FILETIME
son intervalos de 100 ns desde el 1 de enero de 1601 (UTC); la pagina de
`GetSystemTimePreciseAsFileTime` no la devolvio el indice, asi que su firma
(`void (LPFILETIME)`, kernel32, desde Windows 8) va por lo conocido y el codigo
comprueba que exista antes de usarla (si no, `time.time_ns()`).
"""
from __future__ import annotations

import argparse
import json
import socket
import statistics
import struct
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

TAG = "[clock_offset]"
MAGIC = b"NAVCLK1"
FORMAT = "!7sIqqq"                 # magic, seq, t1, t2, t3 (ns, enteros con signo)
SIZE = struct.calcsize(FORMAT)
RECV_BYTES = 256
SERVE_POLL_S = 0.2                 # cada cuanto mira el reloj el servidor mientras espera
DEFAULT_SAMPLES = 200
DEFAULT_INTERVAL_MS = 20.0
SAMPLE_TIMEOUT_S = 0.5             # espera por la respuesta de una muestra
MIN_GOOD = 3                       # muestras minimas para dar un desfase
BEST_FRACTION = 0.25               # el cuarto de menor RTT decide el desfase
EXIT_OK, EXIT_FEW, EXIT_NO_SERVER = 0, 1, 3
EPOCH_1601_TO_1970_100NS = 116444736000000000   # FILETIME del 1970-01-01T00:00:00Z


def _log(msg: str) -> None:
    print(f"{TAG} {msg}", flush=True)


# ----------------------------------------------------------------------------
# El reloj de pared fino
# ----------------------------------------------------------------------------

def _wall_ns_windows() -> Callable[[], int] | None:
    """`GetSystemTimePreciseAsFileTime` como ns desde 1970, o None si no esta."""
    import ctypes
    import ctypes.wintypes
    try:
        kernel32 = ctypes.windll.kernel32
        fn = getattr(kernel32, "GetSystemTimePreciseAsFileTime", None)
    except (AttributeError, OSError):
        return None
    if fn is None:
        return None
    fn.argtypes = [ctypes.POINTER(ctypes.wintypes.FILETIME)]
    fn.restype = None

    def wall() -> int:
        ft = ctypes.wintypes.FILETIME()          # uno por llamada: vale desde varios hilos
        fn(ctypes.byref(ft))
        t = (int(ft.dwHighDateTime) << 32) | int(ft.dwLowDateTime)
        return (t - EPOCH_1601_TO_1970_100NS) * 100
    return wall


def _make_wall_ns(plataforma: str = sys.platform) -> tuple[Callable[[], int], str]:
    if plataforma.startswith("win32"):
        fn = _wall_ns_windows()
        if fn is not None:
            return fn, "GetSystemTimePreciseAsFileTime"
    return time.time_ns, "time.time_ns"


wall_ns, WALL_CLOCK = _make_wall_ns()


def wall_s() -> float:
    """El mismo reloj, en segundos desde 1970 (lo que `igtl_rate` guarda en `t_wall`)."""
    return wall_ns() / 1e9


# ----------------------------------------------------------------------------
# Los datagramas
# ----------------------------------------------------------------------------

def pack(seq: int, t1_ns: int, t2_ns: int = 0, t3_ns: int = 0) -> bytes:
    return struct.pack(FORMAT, MAGIC, int(seq) & 0xFFFFFFFF, int(t1_ns), int(t2_ns), int(t3_ns))


def unpack(data: bytes) -> tuple[int, int, int, int] | None:
    """(seq, t1, t2, t3) de un datagrama nuestro; None si no lo es (tamano o marca)."""
    if len(data) != SIZE:
        return None
    magic, seq, t1, t2, t3 = struct.unpack(FORMAT, data)
    if magic != MAGIC:
        return None
    return int(seq), int(t1), int(t2), int(t3)


@dataclass
class Sample:
    """Una ida y vuelta: t1 y t4 son del reloj de aqui; t2 y t3, del servidor (ns)."""
    seq: int
    t1_ns: int
    t2_ns: int
    t3_ns: int
    t4_ns: int

    @property
    def offset_ms(self) -> float:
        """Reloj del servidor menos reloj de aqui."""
        return ((self.t2_ns - self.t1_ns) + (self.t3_ns - self.t4_ns)) / 2.0 / 1e6

    @property
    def rtt_ms(self) -> float:
        """La ida y vuelta sin el tiempo que el servidor tardo en contestar."""
        return ((self.t4_ns - self.t1_ns) - (self.t3_ns - self.t2_ns)) / 1e6


# ----------------------------------------------------------------------------
# La estimacion
# ----------------------------------------------------------------------------

def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def estimate_offset(samples: list[Sample]) -> dict:
    """El desfase (servidor - aqui, ms) y su incertidumbre a partir de las muestras.

    `offset_ms` es la mediana del desfase del cuarto de muestras con menor RTT (al
    menos `MIN_GOOD`); `uncertainty_ms` es la mitad del RTT minimo (el error de la
    mejor muestra no puede pasar de ahi); `offset_ms_min_rtt` es el desfase de esa
    muestra sola y `offset_ms_median_all` el de todas, para ver si el filtro cambia
    algo. Con menos de `MIN_GOOD` muestras, `offset_ms` es None."""
    n = len(samples)
    res: dict = {"samples": n, "offset_ms": None, "uncertainty_ms": None, "offset_ms_min_rtt": None,
                 "offset_ms_median_all": None, "best_samples": 0, "offset_ms_best_spread": None,
                 "rtt_ms_min": None, "rtt_ms_p50": None, "rtt_ms_p95": None, "rtt_ms_max": None,
                 "sign": "server_minus_local", "clock": WALL_CLOCK}
    if n == 0:
        return res
    by_rtt = sorted(samples, key=lambda s: s.rtt_ms)
    rtts = [s.rtt_ms for s in by_rtt]
    res["rtt_ms_min"] = rtts[0]
    res["rtt_ms_p50"] = _pct(rtts, 50)
    res["rtt_ms_p95"] = _pct(rtts, 95)
    res["rtt_ms_max"] = rtts[-1]
    res["offset_ms_min_rtt"] = by_rtt[0].offset_ms
    res["offset_ms_median_all"] = statistics.median(s.offset_ms for s in samples)
    res["uncertainty_ms"] = rtts[0] / 2.0
    if n < MIN_GOOD:
        return res
    k = max(MIN_GOOD, int(round(n * BEST_FRACTION)))
    best = [s.offset_ms for s in by_rtt[:k]]
    res["best_samples"] = len(best)
    res["offset_ms"] = statistics.median(best)
    res["offset_ms_best_spread"] = max(best) - min(best)
    return res


def _f(x: float | None, nd: int = 3) -> str:
    return "-" if x is None else f"{x:.{nd}f}"


def format_estimate(res: dict) -> str:
    if res["samples"] == 0:
        return f"{TAG} ninguna respuesta: no hay desfase"
    lines = [
        f"{TAG} {res['samples']} muestras; RTT (ms) min {_f(res['rtt_ms_min'])} "
        f"p50 {_f(res['rtt_ms_p50'])} p95 {_f(res['rtt_ms_p95'])} max {_f(res['rtt_ms_max'])}",
        f"{TAG} desfase servidor - aqui: {_f(res['offset_ms'])} ms +- {_f(res['uncertainty_ms'])} "
        f"(mediana de las {res['best_samples']} de menor RTT, dispersion {_f(res['offset_ms_best_spread'])}; "
        f"la de menor RTT sola {_f(res['offset_ms_min_rtt'])}; mediana de todas "
        f"{_f(res['offset_ms_median_all'])}); reloj local {res['clock']}",
    ]
    if res["offset_ms"] is None:
        lines.append(f"{TAG} menos de {MIN_GOOD} muestras: el desfase no se da (se reporta lo que hay)")
    else:
        lines.append(f"{TAG} para igtl_rate listen: --clock-offset-ms {res['offset_ms']:.3f}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# El servidor (la Jetson)
# ----------------------------------------------------------------------------

def make_server_socket(bind: str, port: int) -> socket.socket:
    """Un socket UDP ligado a `bind:port` (`port` 0 da uno efimero: lo dice `getsockname()`)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind, int(port)))
    return sock


def serve(sock: socket.socket, timeout_s: float, wall: Callable[[], int] = wall_ns,
          clock: Callable[[], float] = time.monotonic, log: Callable[[str], None] = _log,
          stop: threading.Event | None = None) -> dict:
    """Contesta cada datagrama valido con t2 (al recibir) y t3 (al contestar) durante
    `timeout_s` s (o hasta `stop`); lo que no es nuestro se cuenta en `ignored`. Cierra el
    socket al salir."""
    host, port = sock.getsockname()[:2]
    log(f"eco en {host}:{port} durante {timeout_s:g} s")
    answered = ignored = 0
    clients: dict[str, int] = {}
    deadline = clock() + float(timeout_s)
    sock.settimeout(SERVE_POLL_S)
    try:
        while clock() < deadline and not (stop is not None and stop.is_set()):
            try:
                data, addr = sock.recvfrom(RECV_BYTES)
            except socket.timeout:
                continue
            except OSError as e:                     # un ICMP de vuelta, p. ej.
                log(f"recvfrom: {e}")
                continue
            t2 = wall()
            parsed = unpack(data)
            if parsed is None:
                ignored += 1
                continue
            seq, t1, _t2, _t3 = parsed
            key = f"{addr[0]}:{addr[1]}"
            if key not in clients:
                log(f"primer datagrama de {key}")
            clients[key] = clients.get(key, 0) + 1
            sock.sendto(pack(seq, t1, t2, wall()), addr)
            answered += 1
    finally:
        sock.close()
    log(f"fin: {answered} contestados, {ignored} ignorados, {len(clients)} clientes")
    return {"answered": answered, "ignored": ignored, "clients": clients, "host": host, "port": port}


# ----------------------------------------------------------------------------
# El cliente (el PC)
# ----------------------------------------------------------------------------

def measure(host: str, port: int, samples: int, interval_s: float, timeout_s: float,
            sample_timeout_s: float = SAMPLE_TIMEOUT_S, wall: Callable[[], int] = wall_ns,
            clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
            log: Callable[[str], None] = _log) -> list[Sample]:
    """Manda `samples` peticiones a `host:port`, una cada `interval_s`, y devuelve las que
    volvieron. `timeout_s` es el tope de toda la medida; `sample_timeout_s`, la espera por
    cada respuesta. Una respuesta de otra peticion (seq distinto) se tira."""
    out: list[Sample] = []
    lost = 0
    deadline = clock() + float(timeout_s)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(min(sample_timeout_s, 0.05))
        for seq in range(int(samples)):
            if clock() >= deadline:
                log(f"tope de {timeout_s:g} s: paro en la muestra {seq}")
                break
            t1 = wall()
            try:
                sock.sendto(pack(seq, t1), (host, int(port)))
            except OSError as e:
                raise ConnectionError(f"{TAG} no se pudo enviar a {host}:{port} ({e})") from e
            got = None
            sample_deadline = clock() + float(sample_timeout_s)
            while clock() < sample_deadline and got is None:
                try:
                    data, _addr = sock.recvfrom(RECV_BYTES)
                except socket.timeout:
                    continue
                except OSError:                      # ICMP "puerto inalcanzable" en Windows
                    break
                t4 = wall()
                parsed = unpack(data)
                if parsed is None or parsed[0] != seq:
                    continue
                got = Sample(seq, parsed[1], parsed[2], parsed[3], t4)
            if got is None:
                lost += 1
            else:
                out.append(got)
            if interval_s > 0:
                sleep(interval_s)
    finally:
        sock.close()
    log(f"{len(out)} respuestas de {samples} peticiones a {host}:{port}; {lost} perdidas")
    return out


def write_json(res: dict, samples: list[Sample], path: Path, meta: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {**meta, "estimate": res, "samples": [asdict(s) for s in samples]}
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _positive(ap: argparse.ArgumentParser, name: str, value: float) -> None:
    if value <= 0:
        ap.error(f"{name} tiene que ser > 0")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Mide el desfase entre el reloj de la Jetson y el del PC con un eco UDP (meta 007, fase 6).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("serve", help="el eco, en la Jetson")
    ps.add_argument("--bind", default="0.0.0.0",
                    help="direccion local del eco; 0.0.0.0 vale para las tres redes (defecto)")
    ps.add_argument("--port", required=True, type=int, help="puerto UDP (p. ej. 18960)")
    ps.add_argument("--timeout", required=True, type=float, help="cuanto dura el eco, s (tope)")
    pm = sub.add_parser("measure", help="el medidor, en el PC")
    pm.add_argument("--host", required=True, help="IP de la Jetson en la red que se mide")
    pm.add_argument("--port", required=True, type=int)
    pm.add_argument("--timeout", required=True, type=float, help="tope de toda la medida, s")
    pm.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    pm.add_argument("--interval-ms", type=float, default=DEFAULT_INTERVAL_MS)
    pm.add_argument("--output", type=Path, default=None, help="JSON con la estimacion y las muestras (no se pisa)")
    args = ap.parse_args(argv)

    _positive(ap, "--timeout", args.timeout)
    if not 1 <= args.port <= 65535:
        ap.error("--port tiene que estar entre 1 y 65535")

    if args.cmd == "serve":
        try:
            sock = make_server_socket(args.bind, args.port)
        except OSError as e:
            print(f"{TAG} no se pudo escuchar en {args.bind}:{args.port} ({e})")
            return EXIT_FEW
        res = serve(sock, args.timeout)
        return EXIT_OK if res["answered"] else EXIT_FEW

    _positive(ap, "--samples", args.samples)
    if args.interval_ms < 0:
        ap.error("--interval-ms tiene que ser >= 0")
    if args.output is not None and args.output.exists():
        ap.error(f"la salida ya existe, no se pisa: {args.output}")
    t_wall_start = time.time()
    try:
        samples = measure(args.host, args.port, args.samples, args.interval_ms / 1000.0, args.timeout)
    except ConnectionError as e:
        print(e)
        return EXIT_NO_SERVER
    res = estimate_offset(samples)
    print(format_estimate(res))
    if args.output is not None:
        meta = {"host": args.host, "port": args.port, "requested": args.samples,
                "interval_ms": args.interval_ms, "t_wall_start": t_wall_start, "clock": WALL_CLOCK,
                "argv": sys.argv if argv is None else list(argv)}
        path = write_json(res, samples, args.output, meta)
        _log(f"guardado {path}")
    if not samples:
        print(f"{TAG} nadie contesta en {args.host}:{args.port}: esta `serve` en marcha en la Jetson?")
        return EXIT_NO_SERVER
    return EXIT_OK if len(samples) >= MIN_GOOD else EXIT_FEW


if __name__ == "__main__":
    sys.exit(main())
