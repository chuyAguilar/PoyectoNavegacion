"""Replay de Marker0 sobre la linea base grabada en vivo (meta 003, fase 1).

La comprobacion de «no cambio» de la pose de Marker0 para el resto de la meta:
las esquinas grabadas con `tracker.py --record` (una grabacion por camara,
Marker0 quieto a ~45 cm) pasadas por la pose y el 1-Euro de hoy tienen que dar
las matrices que se enviaron en vivo y la referencia guardada; la deteccion
sobre 3 frames guardados tiene que dar las esquinas grabadas.

Si faltan los datos, falla: no se generan solos. Se graban en la sesion en
vivo (`Claude outputs/fases/003/fase-1-en-vivo-protocolo.md`) y la referencia
se genera a mano con `replay_util.py reference-marker0`.

La tolerancia depende de la plataforma (meta 007, fase 4 · La suite corre en Linux):
en Windows, la de siempre (clarify P14 de la meta 007: 1e-9 mm, 1e-9°, 1e-6 px); en
Linux, la que decidio el autor tras medir la Jetson (P22, 2026-11-02: 1e-3 mm, 1e-3° y
1e-3 px). Medido en la Jetson (ARM, 2026-11-02): la pose sobre las esquinas grabadas da
2.3e-13 mm y 4.4e-13°; la deteccion sobre los PNG difiere de lo grabado en el PC en
6.1e-05 px como mucho, y la 4x4 del ejemplo de `test_explain_pose.py` (con esas esquinas) en
3.3e-05 mm y 1.1e-04°. El ruido con Marker0 quieto es ~0.03 mm.
"""
from __future__ import annotations

import json
import sys

import pytest

from . import replay_util
from .conftest import PROFILES_DIR, TESTS_DATA_DIR

CAMERAS = ("gs1", "gs2")
EN_LINUX = sys.platform.startswith("linux")
TOL_MM = 1e-3 if EN_LINUX else 1e-9
TOL_DEG = 1e-3 if EN_LINUX else 1e-9
TOL_PX = 1e-3 if EN_LINUX else 1e-6


def _paths(cam: str) -> dict:
    return {
        "dataset": TESTS_DATA_DIR / f"marker0_{cam}.npz",
        "reference": TESTS_DATA_DIR / f"marker0_{cam}_reference.npz",
        "provenance": TESTS_DATA_DIR / f"marker0_{cam}_reference.json",
        "frames": TESTS_DATA_DIR / f"marker0_{cam}_frames",
        "profile": PROFILES_DIR / f"tracker_config_{cam}.yaml",
    }


def _require(cam: str) -> dict:
    p = _paths(cam)
    for k in ("dataset", "reference", "provenance"):
        if not p[k].is_file():
            pytest.fail(f"Falta {p[k].name}: la linea base de Marker0 se graba en vivo "
                        "y su referencia no se genera sola (replay_util.py reference-marker0).")
    if not p["frames"].is_dir() or len(list(p["frames"].glob("frame_*.png"))) != 3:
        pytest.fail(f"Faltan los 3 frames de {p['frames'].name} (replay_util.py copy-frames).")
    return p


@pytest.mark.parametrize("cam", CAMERAS)
def test_dataset_es_el_registrado(cam: str) -> None:
    p = _require(cam)
    with open(p["provenance"], encoding="utf-8") as f:
        proc = json.load(f)
    assert replay_util.sha256(p["dataset"]) == proc["dataset_sha256"], \
        "La grabacion no es la que produjo la referencia."
    assert replay_util.marker0_params(p["profile"]) == proc["params"], \
        "Cambio el tamano, el diccionario, el detector o el filtro de Marker0 en el perfil."


@pytest.mark.parametrize("cam", CAMERAS)
def test_replay_da_lo_enviado_en_vivo(cam: str) -> None:
    p = _require(cam)
    obtenido = replay_util.run_marker0_replay(p["dataset"], p["profile"])
    c = replay_util.compare_marker0(obtenido, replay_util.recorded_marker0(p["dataset"]))
    assert c["sends"] == c["sends_reference"] and c["sends"] > 0, c
    assert c["frames_differ"] == 0, c
    assert c["max_diff_translation_mm"] <= TOL_MM, c
    assert c["max_diff_rotation_deg"] <= TOL_DEG, c


@pytest.mark.parametrize("cam", CAMERAS)
def test_replay_coincide_con_referencia(cam: str) -> None:
    p = _require(cam)
    obtenido = replay_util.run_marker0_replay(p["dataset"], p["profile"])
    c = replay_util.compare_marker0(obtenido, replay_util.load_marker0_reference(p["reference"]))
    assert c["sends"] == c["sends_reference"], c
    assert c["frames_differ"] == 0, c
    assert c["max_diff_translation_mm"] <= TOL_MM, c
    assert c["max_diff_rotation_deg"] <= TOL_DEG, c


@pytest.mark.parametrize("cam", CAMERAS)
def test_deteccion_sobre_los_frames_guardados(cam: str) -> None:
    p = _require(cam)
    d = replay_util.compare_detection(p["dataset"], p["frames"], p["profile"])
    assert d["frames"] == 3 and d["frames_ids_differ"] == 0, d
    assert d["detections"] >= 3, d
    assert d["max_diff_px"] <= TOL_PX, d
