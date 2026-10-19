"""Replay sin camara contra la referencia guardada (meta 001, fase 1).

La comprobacion de «no cambio» de la pose: el recorte de `captura_ba.npz`
(dodecaedro v2, Femto) pasado por `tracker.estimar_pose_rigid_body` con la
config del contexto principal tiene que dar, frame a frame, la pose guardada.
Si falta la referencia, falla: nunca la genera (se genera a mano con
`replay_util.py referencia`, ver su docstring).
"""
from __future__ import annotations

import json

import pytest

from . import replay_util
from .conftest import ITER4_DIR, TESTS_DATA_DIR

DATASET = TESTS_DATA_DIR / "replay_v2_femto.npz"
REFERENCIA = TESTS_DATA_DIR / "replay_v2_femto_referencia.npz"
PROCEDENCIA = REFERENCIA.with_suffix(".json")
CONFIG = ITER4_DIR / "tracker_config.yaml"
TOL_MM = 1e-6
TOL_GRADOS = 1e-6


def _procedencia() -> dict:
    for p in (DATASET, REFERENCIA, PROCEDENCIA):
        if not p.is_file():
            pytest.fail(f"Falta {p.name}: la referencia del replay no se genera "
                        "sola (replay_util.py referencia, a mano).")
    with open(PROCEDENCIA, encoding="utf-8") as f:
        return json.load(f)


def test_dataset_es_el_registrado() -> None:
    proc = _procedencia()
    assert replay_util.sha256(DATASET) == proc["dataset_sha256"], \
        "El dataset del replay no es el que produjo la referencia."
    geom = replay_util.ruta_geometria(CONFIG)
    assert replay_util.sha256(geom) == proc["geometria_sha256"], \
        f"La geometria {geom.name} cambio desde que se genero la referencia."
    assert replay_util.min_markers(CONFIG) == proc["min_markers"], \
        "rigid_bodies_quality.min_markers cambio desde la referencia."


def test_replay_coincide_con_referencia() -> None:
    _procedencia()
    referencia = replay_util.cargar_referencia(REFERENCIA)
    obtenido = replay_util.correr_replay(DATASET, CONFIG)
    c = replay_util.comparar(obtenido, referencia)
    assert c["frames_validez_distinta"] == 0, c
    assert c["max_dif_n_usados"] == 0, c
    assert c["max_dif_traslacion_mm"] <= TOL_MM, c
    assert c["max_dif_rotacion_grados"] <= TOL_GRADOS, c
