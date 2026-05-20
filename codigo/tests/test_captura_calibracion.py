"""Tests para captura_calibracion.py.

Cubre todas las funciones puras (sin hardware de camara).
Ejecutar: python -m pytest tests/test_captura_calibracion.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
CODIGO_DIR = HERE.parent
sys.path.insert(0, str(CODIGO_DIR))

import captura_calibracion as cc


def _crear_geometria_mock(path, ids):
    lines = ["# Mock geometry\n"]
    for tid in ids:
        valores = "  ".join([f"+{v:.3f}" for v in [0.0] * 15])
        lines.append(f"{tid:3d}   {valores}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _crear_calibracion_mock(path):
    import cv2
    K = np.eye(3, dtype=np.float64)
    K[0, 0] = K[1, 1] = 500.0
    K[0, 2] = 320.0
    K[1, 2] = 240.0
    dist = np.zeros((1, 5), dtype=np.float64)
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_WRITE)
    fs.write("camera_matrix", K)
    fs.write("distortion_coefficients", dist)
    fs.release()


def _cfg_minimo(calib_path, geom_path):
    return {
        "camera": {"source": 0, "calibration_file": str(calib_path),
                   "width": 640, "height": 480, "fps": 30},
        "markers": {"dictionary": "DICT_ARUCO_MIP_36h12"},
        "rigid_bodies": [{"name": "Dodecaedro", "geometry_file": str(geom_path)}],
    }


# --- cargar_rb_ids ---

def test_cargar_rb_ids_archivo_sintetico(tmp_path):
    path = tmp_path / "g.txt"
    _crear_geometria_mock(path, [1, 2, 3, 100])
    assert cc.cargar_rb_ids(path) == {1, 2, 3, 100}


def test_cargar_rb_ids_ignora_comentarios(tmp_path):
    path = tmp_path / "g.txt"
    path.write_text(
        "# header\n"
        "151   " + "  ".join(["+0.000"] * 15) + "\n"
        "# medio\n"
        "152   " + "  ".join(["+0.000"] * 15) + "\n",
        encoding="utf-8",
    )
    assert cc.cargar_rb_ids(path) == {151, 152}


def test_cargar_rb_ids_archivo_real():
    geom = CODIGO_DIR / "data" / "reference_dodecaedro.txt"
    if not geom.exists():
        pytest.skip("data/reference_dodecaedro.txt no existe")
    ids = cc.cargar_rb_ids(geom)
    assert ids == set(range(151, 162))


# --- cargar_calibracion ---

def test_cargar_calibracion_ok(tmp_path):
    path = tmp_path / "c.yml"
    _crear_calibracion_mock(path)
    K, dist = cc.cargar_calibracion(path)
    assert K.shape == (3, 3)
    assert K[0, 0] == 500.0


def test_cargar_calibracion_archivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        cc.cargar_calibracion(tmp_path / "no_existe.yml")


# --- filtrar_detecciones ---

def test_filtrar_detecciones_solo_rb():
    corners = [np.zeros((1, 4, 2), dtype=np.float32) for _ in range(3)]
    corners[0][0] = [[1, 1], [2, 1], [2, 2], [1, 2]]
    corners[1][0] = [[3, 3], [4, 3], [4, 4], [3, 4]]
    corners[2][0] = [[5, 5], [6, 5], [6, 6], [5, 6]]
    ids = np.array([[151], [152], [999]])
    out = cc.filtrar_detecciones(corners, ids, {151, 152, 153})
    assert set(out.keys()) == {151, 152}
    assert out[151].shape == (4, 2)


def test_filtrar_detecciones_ids_none():
    assert cc.filtrar_detecciones([], None, {1, 2, 3}) == {}


def test_filtrar_detecciones_ninguno_en_rb():
    corners = [np.zeros((1, 4, 2), dtype=np.float32)]
    ids = np.array([[999]])
    assert cc.filtrar_detecciones(corners, ids, {1, 2, 3}) == {}


# --- cobertura ---

def test_actualizar_cobertura_incrementa():
    cov = {1: 0, 2: 0, 3: 0}
    cc.actualizar_cobertura(cov, {1: np.zeros((4, 2)), 2: np.zeros((4, 2))})
    assert cov == {1: 1, 2: 1, 3: 0}
    cc.actualizar_cobertura(cov, {2: np.zeros((4, 2)), 3: np.zeros((4, 2))})
    assert cov == {1: 1, 2: 2, 3: 1}


def test_actualizar_cobertura_marker_nuevo():
    cov = {1: 0}
    cc.actualizar_cobertura(cov, {1: np.zeros((4, 2)), 99: np.zeros((4, 2))})
    assert cov == {1: 1, 99: 1}


def test_reportar_cobertura_estados():
    cov = {1: 0, 2: 30, 3: 1000}
    lineas = cc.reportar_cobertura(cov, {1, 2, 3}, threshold_warn=50, n_frames_utiles=1000)
    assert any("ID 1" in l and "ERROR" in l for l in lineas)
    assert any("ID 2" in l and "WARN" in l for l in lineas)
    assert any("ID 3" in l and "OK" in l for l in lineas)


# --- frames_a_tabular ---

def test_frames_a_tabular_estructura():
    frames = [
        {"timestamp": 1.0, "detecciones": {151: np.zeros((4, 2), dtype=np.float32),
                                           152: np.ones((4, 2), dtype=np.float32)}},
        {"timestamp": 2.5, "detecciones": {151: np.full((4, 2), 2.0, dtype=np.float32)}},
    ]
    tab = cc.frames_a_tabular(frames)
    assert tab["timestamps"].tolist() == [1.0, 2.5]
    assert tab["frame_offsets"].tolist() == [0, 2, 3]
    assert tab["corners_2d"].shape == (3, 4, 2)


def test_frames_a_tabular_vacio():
    tab = cc.frames_a_tabular([])
    assert tab["timestamps"].shape == (0,)
    assert tab["frame_offsets"].tolist() == [0]
    assert tab["marker_ids"].shape == (0,)
    assert tab["corners_2d"].shape == (0, 4, 2)


# --- validar_prerrequisitos ---

def test_validar_prereqs_ok(tmp_path):
    calib = tmp_path / "c.yml"
    geom = tmp_path / "g.txt"
    _crear_calibracion_mock(calib)
    _crear_geometria_mock(geom, [151, 152])
    cfg = _cfg_minimo(calib, geom)
    cc.validar_prerrequisitos(cfg, tmp_path / "out.npz", geom)


def test_validar_prereqs_falla_calibracion(tmp_path):
    geom = tmp_path / "g.txt"
    _crear_geometria_mock(geom, [151])
    cfg = _cfg_minimo(tmp_path / "noexiste.yml", geom)
    with pytest.raises(SystemExit):
        cc.validar_prerrequisitos(cfg, tmp_path / "out.npz", geom)


def test_validar_prereqs_falla_geometria(tmp_path):
    calib = tmp_path / "c.yml"
    _crear_calibracion_mock(calib)
    geom_no = tmp_path / "noexiste.txt"
    cfg = _cfg_minimo(calib, geom_no)
    with pytest.raises(SystemExit):
        cc.validar_prerrequisitos(cfg, tmp_path / "out.npz", geom_no)


def test_validar_prereqs_falla_sin_rb(tmp_path):
    calib = tmp_path / "c.yml"
    geom = tmp_path / "g.txt"
    _crear_calibracion_mock(calib)
    _crear_geometria_mock(geom, [151])
    cfg = _cfg_minimo(calib, geom)
    cfg["rigid_bodies"] = []
    with pytest.raises(SystemExit):
        cc.validar_prerrequisitos(cfg, tmp_path / "out.npz", geom)


# --- resolver_geometry_path ---

def test_resolver_usa_override(tmp_path):
    cfg = {"rigid_bodies": [{"geometry_file": "del_config.txt"}]}
    out = cc.resolver_geometry_path(str(tmp_path / "override.txt"), cfg)
    assert out == tmp_path / "override.txt"


def test_resolver_prefiere_teorico(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    teorico = tmp_path / "data" / "reference_dodecaedro.txt"
    teorico.write_text("# mock\n", encoding="utf-8")
    cfg = {"rigid_bodies": [{"geometry_file": "data/calibrado.txt"}]}
    out = cc.resolver_geometry_path(None, cfg)
    assert Path(out).name == "reference_dodecaedro.txt"


def test_resolver_fallback_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"rigid_bodies": [{"geometry_file": "data/calibrado.txt"}]}
    out = cc.resolver_geometry_path(None, cfg)
    assert out == Path("data/calibrado.txt")


# --- hash, fourcc, metadata, guardar ---

def test_hash_sha256_estable(tmp_path):
    p1 = tmp_path / "a.txt"; p1.write_text("contenido", encoding="utf-8")
    p2 = tmp_path / "b.txt"; p2.write_text("contenido", encoding="utf-8")
    assert cc.hash_sha256(p1) == cc.hash_sha256(p2)


def test_hash_sha256_distinto(tmp_path):
    p1 = tmp_path / "a.txt"; p1.write_text("A", encoding="utf-8")
    p2 = tmp_path / "b.txt"; p2.write_text("B", encoding="utf-8")
    assert cc.hash_sha256(p1) != cc.hash_sha256(p2)


def test_fourcc_int_a_str_mjpg():
    import cv2
    assert cc.fourcc_int_a_str(cv2.VideoWriter_fourcc(*"MJPG")) == "MJPG"


def test_construir_metadata_keys(tmp_path):
    calib = tmp_path / "c.yml"; _crear_calibracion_mock(calib)
    geom = tmp_path / "g.txt"; _crear_geometria_mock(geom, [151, 152])
    cfg_path = tmp_path / "cfg.yaml"; cfg_path.write_text("x", encoding="utf-8")
    cam_info = {"width_real": 640, "height_real": 480, "fps_real": 30.0,
                "fourcc_real": "MJPG", "backend_solicitado": "MSMF",
                "fourcc_solicitado": "MJPG", "width_solicitado": 640,
                "height_solicitado": 480, "fps_solicitado": 30}
    meta = cc.construir_metadata(
        cfg_path=cfg_path, calib_path=calib, geom_path=geom,
        dict_name="DICT_ARUCO_MIP_36h12", cam_info=cam_info,
        rb_ids={151, 152}, min_markers=2, duracion=60,
    )
    for k in ["schema_version", "captured_at_utc", "opencv_version",
              "config_sha256", "rigid_body_ids", "camera"]:
        assert k in meta
    assert meta["rigid_body_ids"] == [151, 152]


def test_guardar_dataset_retrocompatible(tmp_path):
    frames = [
        {"timestamp": 0.5, "detecciones": {151: np.zeros((4, 2), dtype=np.float32)}},
    ]
    K = np.eye(3, dtype=np.float64)
    dist = np.zeros((1, 5), dtype=np.float64)
    metadata = {"schema_version": "1.0"}
    tabular = cc.frames_a_tabular(frames)
    out = tmp_path / "test.npz"
    cc.guardar_dataset(out, frames, K, dist, {151}, metadata, tabular)
    assert out.exists()
    data = np.load(out, allow_pickle=True)
    fd = list(data["frames_data"])
    assert len(fd) == 1
    assert fd[0]["timestamp"] == 0.5
    np.testing.assert_array_equal(data["K"], K)


def test_guardar_dataset_tabular_sin_pickle(tmp_path):
    frames = [
        {"timestamp": 1.0, "detecciones": {151: np.zeros((4, 2), dtype=np.float32)}},
    ]
    K = np.eye(3, dtype=np.float64)
    dist = np.zeros((1, 5), dtype=np.float64)
    metadata = {"schema_version": "1.0"}
    tabular = cc.frames_a_tabular(frames)
    out = tmp_path / "test.npz"
    cc.guardar_dataset(out, frames, K, dist, {151}, metadata, tabular)
    data = np.load(out, allow_pickle=False)
    for key in ["K", "dist", "rb_ids", "timestamps", "frame_offsets",
                "marker_ids", "corners_2d"]:
        assert key in data.files
