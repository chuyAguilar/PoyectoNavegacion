"""Replay de Marker0 sobre la linea base grabada en vivo (meta 003, fase 1).

La comprobacion de «no cambio» de la pose de Marker0 para el resto de la meta:
las esquinas grabadas con `tracker.py --record` (una grabacion por camara,
Marker0 quieto a ~45 cm) pasadas por la pose y el 1-Euro de hoy tienen que dar
las matrices que se enviaron en vivo y la referencia guardada; la deteccion
sobre 3 frames guardados tiene que dar las esquinas grabadas.

Si faltan los datos, falla: no se generan solos. Se graban en la sesion en
vivo (`Claude outputs/fases/003/fase-1-en-vivo-protocolo.md`) y la referencia
se genera a mano con `replay_util.py reference-marker0`.
"""
from __future__ import annotations

import json

import pytest

from . import replay_util
from .conftest import ITER4_DIR, TESTS_DATA_DIR

CAMERAS = ("gs1", "gs2")
TOL_MM = 1e-9
TOL_DEG = 1e-9
TOL_PX = 1e-6


def _paths(cam: str) -> dict:
    return {
        "dataset": TESTS_DATA_DIR / f"marker0_{cam}.npz",
        "reference": TESTS_DATA_DIR / f"marker0_{cam}_reference.npz",
        "provenance": TESTS_DATA_DIR / f"marker0_{cam}_reference.json",
        "frames": TESTS_DATA_DIR / f"marker0_{cam}_frames",
        "profile": ITER4_DIR / f"tracker_config_{cam}.yaml",
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
