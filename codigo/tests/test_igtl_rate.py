"""`diagnostics.igtl_rate` sin red real salvo un socket local de prueba (meta 003, fase 8b).

`split_messages` saca los mismos mensajes aunque lleguen partidos en trozos
arbitrarios; `summarize` da ~64 rafagas/s y 90 mensajes/s con llegadas en
rafagas cada 15.625 ms, y 90 y 90 con llegadas sueltas; `listen` contra un
servidor de prueba en 127.0.0.1 y puerto efimero (nunca el 18944) cuenta todos
los mensajes y sale al tope, filtra por dispositivo y para si el servidor
cierra; sin servidor, `ConnectionError` en menos del tope + 1 s y `main` da 3;
`send_at_rate` manda matrices distintas al ritmo pedido con un emisor falso;
`main` exige `--port`, `--timeout` y `--device`. `receive_marker0.py` solo corre
en Slicer: se mira con `ast` que `run` tiene `name=NAME` y que la primera
linea del reporte no cambio. Nada abre el servidor pyigtl (B34, conftest).
"""
from __future__ import annotations

import ast
import socket
import threading
import time

import numpy as np
import pyigtl
import pytest

from diagnostics import igtl_rate
from diagnostics.igtl_rate import IgtlArrival

from .conftest import CODIGO_DIR

RECEIVE_MARKER0 = CODIGO_DIR / "slicer" / "receive_marker0.py"


def _packed(n: int, device: str = "RateProbeToTracker", t0: float = 1_700_000_000.0) -> list[tuple[bytes, float]]:
    """N TransformMessage empaquetados, cada uno con su matriz y timestamp distintos."""
    out = []
    for i in range(n):
        M = np.eye(4)
        M[0, 3] = float(i)
        ts = t0 + i * 0.0111
        out.append((pyigtl.TransformMessage(M, timestamp=ts, device_name=device).pack(), ts))
    return out


def _unpack(header: dict, body: bytes) -> pyigtl.TransformMessage:
    msg = pyigtl.MessageBase.create_message(header["message_type"])
    msg.unpack(header, body)
    return msg


# ----------------------------------------------------------------------------
# split_messages
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("chunk", [1, 7, 30, 58, 59, 100, 10_000],
                         ids=["byte_a_byte", "mitad_cabecera_7", "mitad_cabecera_30", "cabecera_justa",
                              "cabecera_mas_1", "mitad_cuerpo", "tres_juntos"])
def test_split_messages_saca_los_mismos_mensajes_en_trozos_arbitrarios(chunk: int) -> None:
    packed = _packed(3)
    stream = b"".join(p for p, _ in packed)
    buffer = bytearray()
    got: list[tuple[dict, bytes]] = []
    for i in range(0, len(stream), chunk):
        buffer += stream[i:i + chunk]
        got += igtl_rate.split_messages(buffer)
    assert len(got) == 3 and buffer == b""
    for k, ((header, body), (_p, ts)) in enumerate(zip(got, packed)):
        assert header["device_name"] == "RateProbeToTracker"
        assert header["message_type"] == "TRANSFORM"
        assert abs(header["timestamp"] - ts) < 1e-6
        msg = _unpack(header, body)
        assert msg.matrix[0, 3] == float(k)


def test_split_messages_deja_un_cuerpo_a_medias_para_el_siguiente_recv() -> None:
    (p0, _), (p1, _) = _packed(2)
    buffer = bytearray(p0 + p1[:70])          # el segundo: cabecera entera y 12 bytes de cuerpo
    got = igtl_rate.split_messages(buffer)
    assert len(got) == 1 and buffer == p1[:70]
    buffer += p1[70:]
    got += igtl_rate.split_messages(buffer)
    assert len(got) == 2 and buffer == b""
    assert len(p0) == igtl_rate.HEADER_SIZE + 48          # TRANSFORM: 12 float32


def test_split_messages_con_cabecera_incompleta_no_saca_nada() -> None:
    (p0, _), = _packed(1)
    buffer = bytearray(p0[:20])
    assert igtl_rate.split_messages(buffer) == [] and buffer == p0[:20]


# ----------------------------------------------------------------------------
# summarize
# ----------------------------------------------------------------------------

def _arrival(t: float, ts: float, read_index: int, name: str = "Marker0ToTracker") -> IgtlArrival:
    return IgtlArrival(t_arrival=t, t_wall=t + 1e9, device_name=name, timestamp=ts + 1e9, read_index=read_index)


def test_summarize_rafagas_cada_tic_dan_64_rafagas_y_90_mensajes_por_segundo() -> None:
    """20 s: 64 rafagas/s cada 15.625 ms; en cada bloque de 64, 26 traen 2 mensajes y 38 traen 1 (= 90)."""
    tic = 0.015625
    arrivals: list[IgtlArrival] = []
    k = 0
    for i in range(20 * 64):
        t = i * tic
        n = 2 if (i % 64) < 26 else 1
        for j in range(n):
            arrivals.append(_arrival(t + j * 0.0001, k / 90.0, i + 1))
            k += 1
    res = igtl_rate.summarize(arrivals, gap_ms=1.0)
    assert res["messages"] == 1800
    assert res["messages_per_s"] == pytest.approx(90.0, abs=0.2)
    assert res["bursts"] == 1280 and res["bursts_per_s"] == pytest.approx(64.0, abs=0.1)
    assert res["messages_per_burst_mean"] == pytest.approx(1800 / 1280, abs=1e-6)
    assert res["messages_per_burst_max"] == 2
    assert res["burst_interval_ms_p50"] == pytest.approx(15.625, abs=0.01)
    assert res["burst_interval_ms_p95"] == pytest.approx(15.625, abs=0.01)
    assert res["burst_interval_ms_max"] == pytest.approx(15.625, abs=0.01)
    assert res["reads_with_messages"] == 1280 and res["distinct_timestamps"] == 1800
    assert res["distinct_timestamps_per_s"] == pytest.approx(90.0, abs=0.2)


def test_summarize_llegadas_sueltas_dan_90_y_90() -> None:
    arrivals = [_arrival(i / 90.0, i / 90.0, i + 1) for i in range(900)]
    res = igtl_rate.summarize(arrivals, gap_ms=1.0)
    assert res["messages_per_s"] == pytest.approx(90.0, abs=1e-6)
    assert res["bursts"] == 900 and res["bursts_per_s"] == pytest.approx(90.0, abs=1e-6)
    assert res["messages_per_burst_mean"] == 1.0 and res["messages_per_burst_max"] == 1
    assert res["burst_interval_ms_p50"] == pytest.approx(1000 / 90, abs=1e-6)
    assert res["latency_ms_p50"] == pytest.approx(0.0, abs=1e-3)


def test_summarize_sin_mensajes_y_con_uno() -> None:
    vacio = igtl_rate.summarize([])
    assert vacio["messages"] == 0 and vacio["messages_per_s"] is None and vacio["bursts"] == 0
    assert igtl_rate.format_summary(vacio).endswith("ningun mensaje recibido")
    uno = igtl_rate.summarize([_arrival(1.0, 1.0, 1)])
    assert uno["messages"] == 1 and uno["bursts"] == 1 and uno["messages_per_s"] is None
    assert uno["burst_interval_ms_p50"] is None
    texto = igtl_rate.format_summary(uno)
    assert "[igtl_rate] 1 mensajes" in texto and "rafagas" in texto


# ----------------------------------------------------------------------------
# listen, con un servidor de prueba local
# ----------------------------------------------------------------------------

class LocalServer:
    """Un servidor TCP en 127.0.0.1 y puerto efimero que manda lo que se le pide."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.release = threading.Event()
        self.thread: threading.Thread | None = None
        self.error: Exception | None = None

    def serve(self, chunks: list[bytes], gap_s: float, close_after: bool) -> None:
        def run() -> None:
            conn = None
            try:
                self.sock.settimeout(5.0)
                conn, _ = self.sock.accept()
                for c in chunks:
                    conn.sendall(c)
                    if gap_s:
                        time.sleep(gap_s)
                if not close_after:
                    self.release.wait(10.0)
            except Exception as e:                   # pragma: no cover - se ve en la prueba
                self.error = e
            finally:
                if conn is not None:
                    conn.close()
                self.sock.close()
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def finish(self) -> None:
        self.release.set()
        if self.thread is not None:
            self.thread.join(5.0)
        assert self.error is None


@pytest.fixture
def server():
    s = LocalServer()
    yield s
    s.finish()


def test_listen_cuenta_todos_los_mensajes_y_sale_al_tope(server: LocalServer) -> None:
    packed = _packed(30)
    # 10 recv de 3 mensajes cada uno, separados 5 ms: llegan agrupados.
    chunks = [b"".join(p for p, _ in packed[i:i + 3]) for i in range(0, 30, 3)]
    server.serve(chunks, gap_s=0.005, close_after=False)
    logs: list[str] = []
    t0 = time.perf_counter()
    arrivals = igtl_rate.listen("127.0.0.1", server.port, seconds=0.4, connect_timeout=2.0, log=logs.append)
    dt = time.perf_counter() - t0
    assert len(arrivals) == 30
    assert 0.4 <= dt < 2.0                           # la ventana desde el primer mensaje, y nada mas
    assert [a.device_name for a in arrivals] == ["RateProbeToTracker"] * 30
    assert [round(a.timestamp - packed[0][1], 4) for a in arrivals] == [round(i * 0.0111, 4) for i in range(30)]
    assert len({a.read_index for a in arrivals}) <= 10
    assert all(a.t_arrival >= t0 for a in arrivals) and all(abs(a.t_wall - time.time()) < 5 for a in arrivals)
    res = igtl_rate.summarize(arrivals)
    assert res["messages"] == 30 and res["bursts"] <= 10
    assert any("conectado a 127.0.0.1" in m for m in logs)


def test_listen_filtra_por_dispositivo(server: LocalServer) -> None:
    mine = _packed(5, device="Marker0ToTracker")
    other = _packed(5, device="RateProbeToTracker")
    server.serve([p for p, _ in mine] + [p for p, _ in other], gap_s=0.0, close_after=False)
    logs: list[str] = []
    arrivals = igtl_rate.listen("127.0.0.1", server.port, 0.3, 2.0, device="Marker0ToTracker", log=logs.append)
    assert len(arrivals) == 5 and {a.device_name for a in arrivals} == {"Marker0ToTracker"}
    assert any("5 mensajes de otros dispositivos" in m for m in logs)


def test_listen_para_si_el_servidor_cierra(server: LocalServer) -> None:
    packed = _packed(4)
    server.serve([p for p, _ in packed], gap_s=0.0, close_after=True)
    logs: list[str] = []
    t0 = time.perf_counter()
    arrivals = igtl_rate.listen("127.0.0.1", server.port, seconds=30.0, connect_timeout=2.0, log=logs.append)
    assert len(arrivals) == 4 and time.perf_counter() - t0 < 5.0
    assert any("cerro la conexion" in m for m in logs)


def test_listen_para_sin_datos(server: LocalServer, monkeypatch) -> None:
    monkeypatch.setattr(igtl_rate, "NO_DATA_S", 0.3)
    server.serve([], gap_s=0.0, close_after=False)
    logs: list[str] = []
    t0 = time.perf_counter()
    arrivals = igtl_rate.listen("127.0.0.1", server.port, seconds=30.0, connect_timeout=2.0, log=logs.append)
    assert arrivals == [] and 0.3 <= time.perf_counter() - t0 < 2.0
    assert any("sin datos durante" in m for m in logs)


def test_listen_done_y_hold(server: LocalServer) -> None:
    packed = _packed(3)
    server.serve([p for p, _ in packed], gap_s=0.0, close_after=False)
    done, hold = threading.Event(), threading.Event()
    out: dict = {}

    def run() -> None:
        out["arrivals"] = igtl_rate.listen("127.0.0.1", server.port, 0.2, 2.0, done=done, hold=hold, log=lambda m: None)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    assert done.wait(3.0)
    assert th.is_alive()                              # sigue con el socket abierto hasta hold
    hold.set()
    th.join(3.0)
    assert not th.is_alive() and len(out["arrivals"]) == 3


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_listen_sin_servidor_falla_con_tope() -> None:
    port = _free_port()
    t0 = time.perf_counter()
    with pytest.raises(ConnectionError, match="nadie escucha"):
        igtl_rate.listen("127.0.0.1", port, seconds=1.0, connect_timeout=0.3, log=lambda m: None)
    assert time.perf_counter() - t0 < 1.3


def test_main_listen_sin_servidor_devuelve_3(capsys) -> None:
    port = _free_port()
    rc = igtl_rate.main(["listen", "--port", str(port), "--seconds", "1", "--timeout", "0.3"])
    assert rc == 3
    assert "nadie escucha" in capsys.readouterr().out


def test_main_listen_cuenta_y_guarda_csv(server: LocalServer, tmp_path, capsys) -> None:
    packed = _packed(6)
    server.serve([p for p, _ in packed], gap_s=0.0, close_after=False)
    csv_path = tmp_path / "llegadas.csv"
    rc = igtl_rate.main(["listen", "--port", str(server.port), "--seconds", "0.3", "--timeout", "2",
                         "--device", "RateProbeToTracker", "--csv", str(csv_path)])
    out = capsys.readouterr().out
    assert rc == 0 and "[igtl_rate] 6 mensajes" in out and "rafagas" in out
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "t_arrival,t_wall,device_name,timestamp,read_index" and len(lines) == 7


def test_main_listen_sin_mensajes_devuelve_1(server: LocalServer, monkeypatch, capsys) -> None:
    monkeypatch.setattr(igtl_rate, "NO_DATA_S", 0.2)
    server.serve([], gap_s=0.0, close_after=False)
    rc = igtl_rate.main(["listen", "--port", str(server.port), "--seconds", "5", "--timeout", "2"])
    assert rc == 1 and "ningun mensaje recibido" in capsys.readouterr().out


# ----------------------------------------------------------------------------
# send_at_rate, con un emisor falso
# ----------------------------------------------------------------------------

class FakeSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, np.ndarray]] = []
        self.dropped = 0

    def send(self, device: str, M: np.ndarray) -> bool:
        self.calls.append((device, np.array(M)))
        return True


def test_send_at_rate_manda_matrices_distintas_al_ritmo_pedido() -> None:
    s = FakeSender()
    res = igtl_rate.send_at_rate(s, "RateProbeToTracker", hz=200.0, seconds=0.3)
    assert res["sent"] == res["calls"] == len(s.calls)
    assert 45 <= res["calls"] <= 62                      # 60 nominales; el sleep de Windows puede atrasar
    assert res["calls_per_s"] == pytest.approx(res["calls"] / res["duration_s"])
    assert all(d == "RateProbeToTracker" for d, _ in s.calls)
    xs = [M[0, 3] for _, M in s.calls]
    assert xs == [float(i) for i in range(len(xs))]      # cada matriz distinta y creciente
    assert all(np.array_equal(M[:3, :3], np.eye(3)) for _, M in s.calls)


def test_send_at_rate_para_con_el_evento() -> None:
    s = FakeSender()
    stop = threading.Event()
    threading.Timer(0.15, stop.set).start()
    t0 = time.perf_counter()
    res = igtl_rate.send_at_rate(s, "RateProbeToTracker", hz=100.0, seconds=10.0, stop=stop)
    assert time.perf_counter() - t0 < 1.0 and 5 <= res["calls"] <= 25


# ----------------------------------------------------------------------------
# main: argumentos
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [
    [],
    ["listen"],
    ["listen", "--seconds", "1", "--timeout", "1"],                               # sin --port
    ["listen", "--port", "18950", "--seconds", "1"],                              # sin --timeout
    ["listen", "--port", "18950", "--seconds", "0", "--timeout", "1"],            # seconds 0
    ["listen", "--port", "18950", "--seconds", "1", "--timeout", "0"],            # timeout 0
    ["listen", "--port", "70000", "--seconds", "1", "--timeout", "1"],            # puerto fuera de rango
    ["bench", "--port", "18950", "--hz", "90", "--seconds", "1", "--timeout", "1"],     # sin --device
    ["bench", "--port", "18950", "--hz", "90", "--seconds", "1", "--device", "X"],      # sin --timeout
    ["bench", "--port", "18950", "--hz", "0", "--seconds", "1", "--device", "X", "--timeout", "1"],
], ids=["nada", "listen_solo", "sin_port", "sin_timeout", "seconds_0", "timeout_0", "puerto_70000",
        "bench_sin_device", "bench_sin_timeout", "bench_hz_0"])
def test_main_exige_los_argumentos(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as e:
        igtl_rate.main(argv)
    assert e.value.code == 2


def test_main_no_pisa_el_csv(tmp_path) -> None:
    existente = tmp_path / "ya.csv"
    existente.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        igtl_rate.main(["listen", "--port", "18950", "--seconds", "1", "--timeout", "1", "--csv", str(existente)])
    assert e.value.code == 2


def test_timer_resolution_apagado_no_toca_nada() -> None:
    with igtl_rate.TimerResolution(1, enabled=False) as t:
        assert t._winmm is None


# ----------------------------------------------------------------------------
# receive_marker0.py (solo corre en Slicer): la forma, por ast
# ----------------------------------------------------------------------------

def _funcion(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def test_receive_marker0_run_tiene_name_con_default_NAME() -> None:
    src = RECEIVE_MARKER0.read_text(encoding="utf-8")
    tree = ast.parse(src)
    run = _funcion(tree, "run")
    args = [a.arg for a in run.args.args]
    assert args == ["seconds", "host", "port", "name"]
    defaults = run.args.defaults
    assert isinstance(defaults[-1], ast.Name) and defaults[-1].id == "NAME"
    assert [d.id for d in defaults[:-1]] == ["SECONDS", "HOST", "PORT"]
    constantes = {n.targets[0].id: n.value.value for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
    assert constantes["NAME"] == "Marker0ToTracker" and constantes["PORT"] == 18944


def test_receive_marker0_primera_linea_del_reporte_no_cambio_y_tiene_intervalos() -> None:
    src = RECEIVE_MARKER0.read_text(encoding="utf-8")
    assert "{report['node']}: {report['updates']} actualizaciones en {report['seconds']} s = " in src
    assert "{report['hz']} Hz; ultima posicion (mm) {report['last_position_mm']}; " in src
    assert "conector {report['connector_state']}" in src
    for key in ("interval_ms_p50", "interval_ms_p95", "interval_ms_max"):
        assert f'"{key}"' in src
    for key in ("node", "seconds", "updates", "hz", "last_position_mm", "connector_state", "legacy_present"):
        assert f'"{key}":' in src
