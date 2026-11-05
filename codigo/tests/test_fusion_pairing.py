"""fusion.pairing (meta 006, fase 1): `pair_by_time` empareja lo mas cercano dentro de la
tolerancia sin repetir; `estimate_offset` recupera un desfase conocido con el marker en
movimiento (50, 100 y 200 mm/s) a <= 0.5 ms y se niega en reposo.
"""
from __future__ import annotations

import numpy as np
import pytest

from fusion import geometry as g
from fusion import pairing as pr
from fusion.dataset import CameraTrack

from .test_fusion_geometry import DIST, K, SIZE, marker_pose, second_camera


def test_pair_by_time_mas_cercano_sin_repetir() -> None:
    ta = np.arange(0, 1.0, 0.016)
    tb = ta + 0.004
    p = pr.pair_by_time(ta, tb, 0.008)
    assert p.shape == (len(ta), 2) and np.array_equal(p[:, 0], p[:, 1])
    assert len(pr.pair_by_time(ta, tb, 0.003)) == 0
    assert len(pr.pair_by_time(ta, tb, 0.003, offset_s=-0.004)) == len(ta)
    # b al doble de frecuencia: cada a se lleva uno solo y ningun b se repite.
    tb2 = np.arange(0, 1.0, 0.008)
    p = pr.pair_by_time(ta, tb2, 0.008)
    assert len(p) == len(ta) and len(set(p[:, 1].tolist())) == len(p)
    # Dos a muy cerca de un mismo b: solo uno lo toma.
    p = pr.pair_by_time(np.array([0.0, 0.001]), np.array([0.0005]), 0.01)
    assert p.shape == (1, 2)
    assert pr.pair_by_time(np.zeros(0), tb, 0.01).shape == (0, 2)
    # Sale ordenado por el indice de a.
    p = pr.pair_by_time(ta, tb[::-1][::-1], 0.008)
    assert np.all(np.diff(p[:, 0]) > 0)


def _track(name: str, t: np.ndarray, Ts: np.ndarray) -> CameraTrack:
    n = len(t)
    return CameraTrack(name=name, t=t, T_raw=Ts, T_alt=np.full((n, 4, 4), np.nan), corners=np.full((n, 4, 2), np.nan),
                       reproj_px=np.zeros(n), reproj_alt_px=np.full(n, np.nan), T_sent=np.full((n, 4, 4), np.nan),
                       K=K, dist=DIST, size_mm=SIZE)


def _moving_tracks(speed_mm_s: float, delta_ms: float, fps_a: float = 63.0, fps_b: float = 66.0,
                   seconds: float = 20.0) -> tuple[CameraTrack, CameraTrack, np.ndarray]:
    """gs1 y gs2 ven el mismo marker que oscila a `speed` mm/s; la hora de gs2 llega `delta`
    ms tarde (hay que sumarle +delta para alinearla)."""
    T12 = second_camera(30.0)
    rng = np.random.default_rng(7)

    def pose_at(t: float) -> np.ndarray:
        amp = speed_mm_s / (2 * np.pi * 0.5)        # seno de 0.5 Hz con velocidad maxima `speed`
        return marker_pose(x=20.0 + amp * np.sin(2 * np.pi * 0.5 * t), y=5.0 + 0.3 * amp * np.cos(2 * np.pi * 0.5 * t))
    ta = np.arange(0, seconds, 1 / fps_a) + rng.uniform(0, 1 / fps_a)
    tb_real = np.arange(0, seconds, 1 / fps_b) + rng.uniform(0, 1 / fps_b)
    Ta = np.array([pose_at(t) for t in ta])
    Tb = np.array([g.inv(T12) @ pose_at(t) for t in tb_real])
    return _track("gs1", ta, Ta), _track("gs2", tb_real - delta_ms / 1000.0, Tb), T12


@pytest.mark.parametrize("speed", [50.0, 100.0, 200.0])
def test_estimate_offset_recupera_el_desfase(speed: float) -> None:
    a, b, T12 = _moving_tracks(speed, delta_ms=6.0)
    d = pr.estimate_offset(a, b, T12)
    assert d["ok"] and d["offset_ms"] == pytest.approx(6.0, abs=0.5), d
    assert d["rms_min_mm"] < d["rms_at_zero_mm"]
    assert d["speed_mm_s"] == pytest.approx(speed * 2 / np.pi, rel=0.15)      # la media de |seno|
    assert len(d["curve"]["delta_ms"]) == len(d["curve"]["rms_mm"]) == 81


def test_estimate_offset_se_niega_en_reposo_y_con_pocos_frames() -> None:
    a, b, T12 = _moving_tracks(0.0, delta_ms=6.0)
    d = pr.estimate_offset(a, b, T12)
    assert not d["ok"] and d["offset_ms"] is None and "sin movimiento" in d["note"]
    corto = _track("gs1", a.t[:5], a.T_raw[:5])
    assert "menos de 10" in pr.estimate_offset(corto, b, T12)["note"]
    lejos = _moving_tracks(100.0, delta_ms=25.0)
    d = pr.estimate_offset(*lejos)
    assert not d["ok"] and "borde" in d["note"]
