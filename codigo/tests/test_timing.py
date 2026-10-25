"""El tiempo por frame, sin camara (meta 003, fase 6 · Donde se va el tiempo por frame).

`pose_log.Stopwatch` con un reloj falso (etapas, `other`, la suma igual al
frame); `tracker --timing` con camara, emisor y ventana falsos (escribe el
JSON con las etapas del bucle y lo enviado es lo mismo que sin la opcion); y
`diagnostics.measure_window` con las funciones de HighGUI sustituidas (no se
abre ninguna ventana). Ninguna prueba abre una camara ni un puerto (B34).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from diagnostics import measure_window
from diagnostics import pose_log
from diagnostics.pose_log import Stopwatch, timing_stats
import tracker

from .conftest import PROFILES_DIR, TESTS_DATA_DIR
from .synthetic import FakeCamera, FakeSender, fake_time, render_marker

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"
FRAME_GS1 = TESTS_DATA_DIR / "marker0_gs1_frames" / "frame_00240.png"


class FakeClock:
    """Reloj que avanza solo cuando se le dice (segundos)."""

    def __init__(self, t0: float = 10.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, ms: float) -> None:
        self.t += ms / 1000.0


# ---------------------------------------------------------------------------
# Stopwatch
# ---------------------------------------------------------------------------

def test_stopwatch_etapas_other_y_suma() -> None:
    clk = FakeClock()
    sw = Stopwatch(clock=clk)
    for capture, detect in [(11.0, 3.0), (12.0, 5.0), (10.0, 4.0)]:
        clk.advance(capture)
        sw.mark("capture")
        clk.advance(detect)
        sw.mark("detect")
        clk.advance(0.5)                 # sin marca: va a other
        sw.end_frame()
    s = sw.summary()
    assert s["frames"] == 3 and sw.stages() == ["capture", "detect", "other"]
    assert s["stages"]["capture"]["mean_ms"] == pytest.approx(11.0)
    assert s["stages"]["capture"]["p50_ms"] == pytest.approx(11.0)
    assert s["stages"]["detect"]["max_ms"] == pytest.approx(5.0)
    assert s["stages"]["other"]["mean_ms"] == pytest.approx(0.5)
    assert s["frame"]["mean_ms"] == pytest.approx((14.5 + 17.5 + 14.5) / 3)
    assert s["sum_of_stage_means_ms"] == pytest.approx(s["frame"]["mean_ms"])
    assert s["sum_over_frame_mean"] == pytest.approx(1.0)
    assert s["fps_from_frame_mean"] == pytest.approx(1000.0 / s["frame"]["mean_ms"])


def test_stopwatch_etapa_ausente_cuenta_cero_y_se_acumula() -> None:
    clk = FakeClock()
    sw = Stopwatch(clock=clk)
    clk.advance(10.0)
    sw.mark("capture")
    sw.end_frame()
    clk.advance(10.0)
    sw.mark("capture")
    clk.advance(2.0)
    sw.mark("key")
    clk.advance(3.0)
    sw.mark("key")                       # dos marcas de la misma etapa se suman
    sw.end_frame()
    pf = sw.per_frame()
    assert pf["key"] == [0.0, pytest.approx(5.0)]
    assert pf["frame"] == [pytest.approx(10.0), pytest.approx(15.0)]
    assert sw.summary()["stages"]["key"]["mean_ms"] == pytest.approx(2.5)


def test_stopwatch_vacio_y_no_pisa(tmp_path: Path) -> None:
    sw = Stopwatch(clock=FakeClock())
    s = sw.summary()
    assert s["frames"] == 0 and s["frame"]["mean_ms"] is None and s["sum_of_stage_means_ms"] is None
    out = sw.save(tmp_path / "t.json", {"x": 1})
    assert json.loads(out.read_text(encoding="utf-8"))["metadata"] == {"x": 1}
    with pytest.raises(FileExistsError):
        sw.save(tmp_path / "t.json", {})
    assert timing_stats([]) == {"mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    assert "FRAME" in pose_log.format_timing(s)


# ---------------------------------------------------------------------------
# tracker --timing con camara, emisor y ventana falsos
# ---------------------------------------------------------------------------

@pytest.fixture
def profile_syn(tmp_path: Path) -> Path:
    gs1 = yaml.safe_load(GS1.read_text(encoding="utf-8"))
    cfg = {"camera": {"camera_type": "webcam"}, "markers": gs1["markers"],
           "igtlink": {"transforms_port": 18944, "video_port": 18945, "send_video": False},
           "filtering": gs1["filtering"], "debug": {"show_window": True, "verbose": False}}
    ruta = tmp_path / "perfil_syn.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return ruta


@pytest.fixture(scope="module")
def frames_syn() -> list[np.ndarray]:
    return [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i) for i in range(6)]


def _run(monkeypatch, frames, profile: Path, extra: list[str]):
    cam = FakeCamera(frames)
    FakeSender.instances = []
    monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: cam)
    monkeypatch.setattr(tracker, "IgtlSender", FakeSender)
    monkeypatch.setattr(tracker, "time", fake_time())       # fase 7: perf_counter falso, 11 ms por llamada
    monkeypatch.setattr(tracker.cv2, "imshow", lambda title, img: None)
    monkeypatch.setattr(tracker.cv2, "waitKey", lambda ms: -1)
    monkeypatch.setattr(tracker.cv2, "destroyAllWindows", lambda: None)
    assert tracker.main(["--config", str(profile), *extra]) == 0
    return cam, FakeSender.instances[0]


def test_timing_con_ventana_escribe_las_etapas(tmp_path: Path, monkeypatch, frames_syn,
                                               profile_syn, capsys) -> None:
    out = tmp_path / "t" / "timing.json"
    cam, srv = _run(monkeypatch, frames_syn, profile_syn, ["--timing", str(out)])
    assert cam.closed and srv.closed
    data = json.loads(out.read_text(encoding="utf-8"))
    s = data["summary"]
    # La camara falsa lanza KeyboardInterrupt en la lectura del 7.o frame: 6 frames cerrados.
    assert s["frames"] == len(frames_syn)
    assert list(s["stages"]) == ["capture", "gray", "detect", "pose_filter", "send",
                                 "draw", "imshow", "key", "other"]
    assert s["sum_over_frame_mean"] == pytest.approx(1.0)
    assert len(data["per_frame_ms"]["frame"]) == len(frames_syn)
    meta = data["metadata"]
    assert meta["show_window"] is True and meta["frames_loop"] == len(frames_syn)
    assert meta["fps_average"] > 0 and meta["clock"] == "time.perf_counter"
    assert meta["capture"]["mode"] == "thread" and meta["capture"]["frames_read"] >= len(frames_syn)
    log = capsys.readouterr().out
    assert "[Tiempos] Guardados en" in log and "FRAME" in log and "[Salida limpia]" in log


def test_timing_sin_ventana_y_con_record(tmp_path: Path, monkeypatch, frames_syn,
                                         profile_syn) -> None:
    out = tmp_path / "timing.json"
    _run(monkeypatch, frames_syn, profile_syn,
         ["--no-window", "--record", str(tmp_path / "g.npz"), "--timing", str(out)])
    s = json.loads(out.read_text(encoding="utf-8"))["summary"]
    assert list(s["stages"]) == ["capture", "gray", "detect", "pose_filter", "send",
                                 "record", "other"]


def test_timing_no_cambia_lo_que_se_envia(tmp_path: Path, monkeypatch, frames_syn,
                                          profile_syn) -> None:
    _, a = _run(monkeypatch, frames_syn, profile_syn, [])
    _, b = _run(monkeypatch, frames_syn, profile_syn, ["--timing", str(tmp_path / "t.json")])
    assert [n for n, _ in a.sent] == [n for n, _ in b.sent] == ["Marker0ToTracker"] * len(frames_syn)
    for (_, ma), (_, mb) in zip(a.sent, b.sent):
        assert np.array_equal(ma, mb)


def test_timing_no_pisa_y_no_abre_la_camara(tmp_path: Path, monkeypatch, profile_syn) -> None:
    (tmp_path / "t.json").write_text("{}", encoding="utf-8")

    def _prohibido(cfg_cam):
        raise AssertionError("no tenia que llegar a crear la camara")
    monkeypatch.setattr(tracker, "create_backend", _prohibido)
    with pytest.raises(FileExistsError):
        tracker.main(["--config", str(profile_syn), "--timing", str(tmp_path / "t.json")])
    with pytest.raises(SystemExit):
        tracker.main(["--config", str(profile_syn), "--timing", str(tmp_path / "t.txt")])


# ---------------------------------------------------------------------------
# measure_window sin ventana real
# ---------------------------------------------------------------------------

@pytest.fixture
def highgui_falso(monkeypatch):
    """Sustituye la ventana de HighGUI; cuenta las llamadas."""
    n = {"imshow": 0, "waitKey": 0, "pollKey": 0, "named": 0, "destroy": 0}

    def cuenta(nombre, ret=None):
        def f(*_a, **_k):
            n[nombre] += 1
            return ret
        return f
    monkeypatch.setattr(measure_window.cv2, "imshow", cuenta("imshow"))
    monkeypatch.setattr(measure_window.cv2, "waitKey", cuenta("waitKey", -1))
    monkeypatch.setattr(measure_window.cv2, "pollKey", cuenta("pollKey", -1))
    monkeypatch.setattr(measure_window.cv2, "namedWindow", cuenta("named"))
    monkeypatch.setattr(measure_window.cv2, "destroyWindow", cuenta("destroy"))
    return n


def test_measure_window_dos_modos(tmp_path: Path, highgui_falso, capsys) -> None:
    out = tmp_path / "w.json"
    rc = measure_window.main(["--frame", str(FRAME_GS1), "--iterations", "25",
                              "--timeout", "30", "--output", str(out)])
    assert rc == 0
    res = json.loads(out.read_text(encoding="utf-8"))
    assert [m["mode"] for m in res["modes"]] == ["waitKey(1)", "pollKey()"]
    assert all(m["iterations"] == 25 and not m["truncated"] for m in res["modes"])
    assert res["shape"] == [960, 1280, 3] and res["truncated"] is False
    w = measure_window.WARMUP
    assert highgui_falso["imshow"] == 2 * (25 + w)
    assert highgui_falso["waitKey"] == 25 + w
    assert highgui_falso["pollKey"] == 25 + w + 2          # + el cierre de cada modo
    assert highgui_falso["named"] == highgui_falso["destroy"] == 2
    assert "waitKey(1)" in capsys.readouterr().out
    with pytest.raises(SystemExit):                          # no pisa
        measure_window.main(["--frame", str(FRAME_GS1), "--iterations", "1",
                             "--timeout", "5", "--output", str(out)])


def test_measure_window_tope_de_tiempo(highgui_falso, monkeypatch) -> None:
    clk = FakeClock()
    monkeypatch.setattr(measure_window, "WARMUP", 0)
    monkeypatch.setattr(measure_window.cv2, "imshow", lambda *a, **k: clk.advance(300.0))
    res = measure_window.run(FRAME_GS1, iterations=100, timeout_s=1.0, clock=clk)
    assert res["truncated"] is True
    n = [m["iterations"] for m in res["modes"]]
    assert n == [4, 0]                      # 4 vueltas de 300 ms y el tope corta el resto
    assert res["modes"][0]["imshow"]["mean_ms"] == pytest.approx(300.0)
    assert res["modes"][1]["fps_equivalent"] is None
    assert "tope de tiempo" in measure_window.format_result(res)


def test_measure_window_frame_inexistente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        measure_window.load_frame(tmp_path / "no.png")
    assert cv2.imread(str(FRAME_GS1), cv2.IMREAD_COLOR).shape == (960, 1280, 3)
