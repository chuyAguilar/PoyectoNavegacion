"""`diagnostics.clock_offset` sin red real salvo un eco UDP local en puerto efimero
(meta 007, fase 6 · Slicer en el PC recibe de la Jetson).

El datagrama va y vuelve entero y se rechaza lo que no es nuestro; `Sample` da el
desfase y el RTT de NTP; `estimate_offset` recupera un desfase conocido con
muestras sinteticas (ruido de red asimetrico incluido), da la incertidumbre
RTT min/2 y no da desfase con menos de 3 muestras; `serve` + `measure` en
127.0.0.1 dan un desfase de ~0 ms (el mismo reloj en los dos lados) con todas
las muestras; sin servidor, `measure` vuelve vacio dentro del tope y `main` da
3; `main` exige `--port`, `--timeout` y `--host`, no pisa `--output` y guarda el
JSON. `wall_ns` es fino (mas de 10 valores distintos en 40 lecturas separadas
por 1 ms) y esta en el epoch de `time.time_ns()`. Nada toca el 18944 ni abre
una camara (B34, conftest).
"""
from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from diagnostics import clock_offset as co
from diagnostics.clock_offset import Sample


# ----------------------------------------------------------------------------
# Los datagramas y la muestra
# ----------------------------------------------------------------------------

def test_pack_unpack_van_y_vuelven_enteros() -> None:
    t1, t2, t3 = 1_700_000_000_123_456_789, 1_700_000_000_123_457_000, 1_700_000_000_123_458_111
    data = co.pack(7, t1, t2, t3)
    assert len(data) == co.SIZE == 35
    assert co.unpack(data) == (7, t1, t2, t3)
    assert co.unpack(co.pack(0xFFFFFFFF, -5)) == (0xFFFFFFFF, -5, 0, 0)


@pytest.mark.parametrize("data", [b"", b"x" * 34, b"x" * 36, b"NAVCLK0" + b"\0" * 28, b"\0" * 35],
                         ids=["vacio", "corto", "largo", "otra_marca", "ceros"])
def test_unpack_rechaza_lo_que_no_es_nuestro(data: bytes) -> None:
    assert co.unpack(data) is None


def test_sample_da_el_desfase_y_el_rtt_de_ntp() -> None:
    # El servidor va 50 ms por delante; la ida tarda 2 ms, la vuelta 4 ms, y contesta en 1 ms.
    ms = 1_000_000
    t1 = 1000 * ms
    t2 = t1 + 2 * ms + 50 * ms
    t3 = t2 + 1 * ms
    t4 = t1 + 2 * ms + 1 * ms + 4 * ms
    s = Sample(1, t1, t2, t3, t4)
    assert s.rtt_ms == pytest.approx(6.0)
    assert s.offset_ms == pytest.approx(50.0 - 1.0)        # (ida - vuelta)/2 = -1 ms de sesgo


# ----------------------------------------------------------------------------
# La estimacion
# ----------------------------------------------------------------------------

def _samples(offset_ms: float, n: int = 100, base_rtt_ms: float = 1.0, seed: int = 3) -> list[Sample]:
    """Muestras con un desfase fijo y colas de red asimetricas (algunas idas muy lentas)."""
    import random
    rnd = random.Random(seed)
    out = []
    t = 1_700_000_000_000_000_000
    for i in range(n):
        ida = base_rtt_ms / 2 + (rnd.random() * 30 if i % 7 == 0 else rnd.random() * 0.2)
        vuelta = base_rtt_ms / 2 + rnd.random() * 0.2
        t1 = t + i * 20_000_000
        t2 = t1 + int(ida * 1e6) + int(offset_ms * 1e6)
        t3 = t2 + 50_000
        t4 = t1 + int((ida + vuelta) * 1e6) + 50_000
        out.append(Sample(i, t1, t2, t3, t4))
    return out


def test_estimate_offset_recupera_el_desfase_y_da_la_incertidumbre() -> None:
    res = co.estimate_offset(_samples(-37.25))
    assert res["samples"] == 100 and res["best_samples"] == 25
    assert res["offset_ms"] == pytest.approx(-37.25, abs=0.15)          # dentro de RTT min/2 + ruido
    assert res["uncertainty_ms"] == pytest.approx(res["rtt_ms_min"] / 2)
    assert 1.0 <= res["rtt_ms_min"] < 1.5 and res["rtt_ms_max"] > 10.0
    assert res["rtt_ms_p50"] <= res["rtt_ms_p95"] <= res["rtt_ms_max"]
    assert abs(res["offset_ms_min_rtt"] - (-37.25)) <= res["uncertainty_ms"] + 1e-6
    # La mediana de todas sufre las idas lentas (sesgo positivo): el filtro por RTT lo quita.
    assert res["offset_ms_median_all"] > res["offset_ms"] - 0.01
    assert res["offset_ms_best_spread"] < 0.5
    assert res["sign"] == "server_minus_local" and res["clock"] == co.WALL_CLOCK


def test_estimate_offset_con_pocas_muestras_no_da_desfase() -> None:
    assert co.estimate_offset([])["offset_ms"] is None and co.estimate_offset([])["samples"] == 0
    res = co.estimate_offset(_samples(5.0, n=2))
    assert res["samples"] == 2 and res["offset_ms"] is None and res["best_samples"] == 0
    assert res["rtt_ms_min"] is not None and res["offset_ms_min_rtt"] is not None
    assert "menos de 3 muestras" in co.format_estimate(res)
    tres = co.estimate_offset(_samples(5.0, n=3))
    assert tres["best_samples"] == 3 and tres["offset_ms"] == pytest.approx(5.0, abs=0.2)
    assert "--clock-offset-ms" in co.format_estimate(tres)
    assert co.format_estimate(co.estimate_offset([])).endswith("no hay desfase")


# ----------------------------------------------------------------------------
# El reloj
# ----------------------------------------------------------------------------

def test_wall_ns_es_fino_y_esta_en_el_epoch() -> None:
    assert abs(co.wall_ns() - time.time_ns()) < 1_000_000_000          # mismo epoch, < 1 s
    assert abs(co.wall_s() - time.time()) < 1.0
    vistos = set()
    for _ in range(40):
        vistos.add(co.wall_ns())
        time.sleep(0.001)
    assert len(vistos) > 10                   # time.time() de Windows daria ~3 valores en 15.6 ms
    a, b = co.wall_ns(), co.wall_ns()
    assert b >= a


def test_make_wall_ns_fuera_de_windows_es_time_ns() -> None:
    fn, nombre = co._make_wall_ns("linux")
    assert fn is time.time_ns and nombre == "time.time_ns"


# ----------------------------------------------------------------------------
# serve + measure en local
# ----------------------------------------------------------------------------

class Eco:
    """Un `serve` en 127.0.0.1 y puerto efimero, en un hilo; `fin()` lo para y da su resultado."""

    def __init__(self, timeout_s: float = 10.0) -> None:
        sock = co.make_server_socket("127.0.0.1", 0)
        self.port = sock.getsockname()[1]
        self.logs: list[str] = []
        self.stop = threading.Event()
        self.holder: dict = {}

        def run() -> None:
            self.holder["res"] = co.serve(sock, timeout_s=timeout_s, log=self.logs.append, stop=self.stop)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def fin(self) -> dict:
        self.stop.set()
        self.thread.join(5.0)
        assert not self.thread.is_alive()
        return self.holder["res"]


@pytest.fixture
def eco():
    e = Eco()
    yield e
    e.fin()


def test_serve_y_measure_en_local_dan_desfase_cero(eco: Eco) -> None:
    mlogs: list[str] = []
    t0 = time.perf_counter()
    samples = co.measure("127.0.0.1", eco.port, samples=40, interval_s=0.002, timeout_s=5.0, log=mlogs.append)
    assert len(samples) == 40 and [s.seq for s in samples] == list(range(40))
    assert time.perf_counter() - t0 < 3.0
    res = co.estimate_offset(samples)
    assert res["offset_ms"] == pytest.approx(0.0, abs=2.0)              # el mismo reloj en los dos lados
    assert 0.0 <= res["rtt_ms_min"] < 50.0 and res["uncertainty_ms"] < 25.0
    assert all(s.t2_ns <= s.t3_ns for s in samples)
    assert any("40 respuestas de 40" in m for m in mlogs)
    # El servidor para y cuenta lo contestado.
    r = eco.fin()
    assert r["answered"] == 40 and r["ignored"] == 0 and list(r["clients"].values()) == [40]
    assert any("eco en 127.0.0.1" in m for m in eco.logs) and any("fin: 40 contestados" in m for m in eco.logs)


def test_serve_acaba_solo_en_su_tope() -> None:
    sock = co.make_server_socket("127.0.0.1", 0)
    t0 = time.perf_counter()
    r = co.serve(sock, timeout_s=0.5, log=lambda m: None)
    assert 0.4 <= time.perf_counter() - t0 < 1.5 and r["answered"] == 0


def test_serve_ignora_lo_que_no_es_nuestro_y_measure_tira_un_seq_viejo(eco: Eco) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    sock.sendto(b"hola", ("127.0.0.1", eco.port))                   # se ignora: sin respuesta
    with pytest.raises(socket.timeout):
        sock.recvfrom(256)
    sock.sendto(co.pack(99, 5), ("127.0.0.1", eco.port))             # valido: vuelve con t2 y t3
    data, _ = sock.recvfrom(256)
    seq, t1, t2, t3 = co.unpack(data)
    assert (seq, t1) == (99, 5) and 0 < t2 <= t3
    sock.close()
    samples = co.measure("127.0.0.1", eco.port, samples=5, interval_s=0.0, timeout_s=3.0, log=lambda m: None)
    assert [s.seq for s in samples] == [0, 1, 2, 3, 4]
    r = eco.fin()
    assert r["ignored"] == 1 and r["answered"] == 6


def _free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_measure_sin_servidor_vuelve_vacio_dentro_del_tope() -> None:
    port = _free_udp_port()
    t0 = time.perf_counter()
    samples = co.measure("127.0.0.1", port, samples=3, interval_s=0.0, timeout_s=2.0,
                         sample_timeout_s=0.2, log=lambda m: None)
    assert samples == [] and time.perf_counter() - t0 < 2.5


def test_measure_para_en_el_tope_total() -> None:
    port = _free_udp_port()
    logs: list[str] = []
    t0 = time.perf_counter()
    samples = co.measure("127.0.0.1", port, samples=1000, interval_s=0.0, timeout_s=0.5,
                         sample_timeout_s=0.1, log=logs.append)
    assert samples == [] and time.perf_counter() - t0 < 1.5
    assert any("tope de 0.5 s" in m for m in logs)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def test_main_measure_sin_servidor_devuelve_3(capsys, monkeypatch) -> None:
    monkeypatch.setattr(co, "SAMPLE_TIMEOUT_S", 0.1)
    port = _free_udp_port()
    rc = co.main(["measure", "--host", "127.0.0.1", "--port", str(port), "--samples", "2",
                  "--interval-ms", "0", "--timeout", "2"])
    assert rc == 3
    assert "nadie contesta" in capsys.readouterr().out


def test_main_measure_contra_el_eco_guarda_el_json(eco: Eco, tmp_path, capsys) -> None:
    salida = tmp_path / "desfase.json"
    rc = co.main(["measure", "--host", "127.0.0.1", "--port", str(eco.port), "--samples", "20",
                  "--interval-ms", "1", "--timeout", "5", "--output", str(salida)])
    out = capsys.readouterr().out
    assert rc == 0 and "20 muestras" in out and "--clock-offset-ms" in out and "guardado" in out
    doc = json.loads(salida.read_text(encoding="utf-8"))
    assert doc["host"] == "127.0.0.1" and doc["port"] == eco.port and doc["requested"] == 20
    assert doc["estimate"]["samples"] == 20 and len(doc["samples"]) == 20
    assert set(doc["samples"][0]) == {"seq", "t1_ns", "t2_ns", "t3_ns", "t4_ns"}
    assert doc["clock"] == co.WALL_CLOCK and doc["t_wall_start"] > 1.7e9


def test_main_serve_sin_clientes_devuelve_1(capsys) -> None:
    port = _free_udp_port()
    t0 = time.perf_counter()
    rc = co.main(["serve", "--bind", "127.0.0.1", "--port", str(port), "--timeout", "0.5"])
    assert rc == 1 and 0.4 <= time.perf_counter() - t0 < 2.0
    assert "0 contestados" in capsys.readouterr().out


def test_main_serve_con_el_puerto_tomado_lo_dice(capsys) -> None:
    sock = co.make_server_socket("127.0.0.1", 0)
    port = sock.getsockname()[1]
    try:
        rc = co.main(["serve", "--bind", "127.0.0.1", "--port", str(port), "--timeout", "1"])
    finally:
        sock.close()
    assert rc == 1 and "no se pudo escuchar" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    [],
    ["serve"],
    ["serve", "--port", "18960"],                                           # sin --timeout
    ["serve", "--timeout", "1"],                                            # sin --port
    ["serve", "--port", "0", "--timeout", "1"],                             # puerto 0
    ["serve", "--port", "18960", "--timeout", "0"],                         # tope 0
    ["measure", "--port", "18960", "--timeout", "1"],                       # sin --host
    ["measure", "--host", "127.0.0.1", "--timeout", "1"],                   # sin --port
    ["measure", "--host", "127.0.0.1", "--port", "18960"],                  # sin --timeout
    ["measure", "--host", "127.0.0.1", "--port", "18960", "--timeout", "1", "--samples", "0"],
    ["measure", "--host", "127.0.0.1", "--port", "18960", "--timeout", "1", "--interval-ms", "-1"],
], ids=["nada", "serve_solo", "serve_sin_timeout", "serve_sin_port", "puerto_0", "tope_0",
        "measure_sin_host", "measure_sin_port", "measure_sin_timeout", "samples_0", "intervalo_negativo"])
def test_main_exige_los_argumentos(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as e:
        co.main(argv)
    assert e.value.code == 2


def test_main_no_pisa_la_salida(tmp_path) -> None:
    existente = tmp_path / "ya.json"
    existente.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        co.main(["measure", "--host", "127.0.0.1", "--port", "18960", "--timeout", "1", "--output", str(existente)])
    assert e.value.code == 2
