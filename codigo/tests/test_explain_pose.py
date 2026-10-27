"""El ejemplo resuelto reproduce la cadena (meta 004 · Cómo funciona el tracker, fase 2).

`diagnostics/explain_pose.py` sobre los 3 frames guardados de gs1 y los 3 de gs2
(`tests/data/`), sin cámara ni Slicer:

- las esquinas detectadas en el PNG son las grabadas en vivo (≤ 1e-6 px, la
  tolerancia del replay);
- la 4×4 filtrada es la que se envió en vivo en ese frame y la de la referencia
  del replay (`TOL_MM` y `TOL_DEG` de `test_replay_marker0.py`);
- la reproyección de la pose cruda, por esquina, queda por debajo de `MAX_REPROJ_PX`
  (medido en la fase 2: 0.05–0.20 px en los 6 frames, del orden del RMS de la
  calibración, 0.167 y 0.154 px);
- con 98.6 mm, la misma rotación (≤ 1e-6°) y una t 98.6/80 veces la de 80 (error
  relativo ≤ 1e-6): la propiedad que hace invisible B55;
- el sha256 de la K de la grabación es el del `.yml` del perfil, y K y dist coinciden.

Además, `format_markdown` es determinista, `draw_example` recorta al tamaño pedido
y la CLI falla fuerte (frame sin PNG, salida que ya existe, perfil sin el marker).
"""
from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from diagnostics import explain_pose

from . import replay_util
from .conftest import PROFILES_DIR, TESTS_DATA_DIR
from .test_replay_marker0 import TOL_DEG, TOL_MM, TOL_PX

CAMERAS = ("gs1", "gs2")
FRAMES = (240, 480, 720)
ALT_SIZE_MM = 98.6
MAX_REPROJ_PX = 0.3
TOL_RATIO = 1e-6
TOL_ROT_DEG = 1e-6


def _paths(cam: str) -> dict:
    return {"dataset": TESTS_DATA_DIR / f"marker0_{cam}.npz",
            "frames": TESTS_DATA_DIR / f"marker0_{cam}_frames",
            "reference": TESTS_DATA_DIR / f"marker0_{cam}_reference.npz",
            "profile": PROFILES_DIR / f"tracker_config_{cam}.yaml"}


@pytest.fixture(scope="module")
def results() -> dict:
    """`explain_frame` de los 6 frames, una vez por módulo (cada uno pasa ~480–720 frames por el filtro)."""
    out = {}
    for cam in CAMERAS:
        p = _paths(cam)
        for frame in FRAMES:
            out[(cam, frame)] = explain_pose.explain_frame(p["dataset"], p["frames"], frame, p["profile"],
                                                          alt_size_mm=ALT_SIZE_MM)
    return out


@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("cam", CAMERAS)
def test_las_esquinas_detectadas_son_las_grabadas(results, cam: str, frame: int) -> None:
    d = results[(cam, frame)]["detection"]
    assert d["ids_detected"] == [0], d["ids_detected"]
    assert d["max_diff_px"] <= TOL_PX, d["max_diff_px"]
    assert len(d["corners_px"]) == 4 and all(len(c) == 2 for c in d["corners_px"])


@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("cam", CAMERAS)
def test_la_matriz_filtrada_es_la_enviada_en_vivo_y_la_referencia(results, cam: str, frame: int) -> None:
    r = results[(cam, frame)]
    x = r["matrix"]
    assert x["device_name"] == "Marker0ToTracker"
    assert x["live_diff_translation_mm"] <= TOL_MM, x
    assert x["live_diff_rotation_deg"] <= TOL_DEG, x
    ref = replay_util.load_marker0_reference(_paths(cam)["reference"])
    k = int(np.flatnonzero(ref["sent_frame"] == frame)[0])
    M, M_ref = np.asarray(x["M"]), ref["M"][k]
    assert float(np.linalg.norm(M[:3, 3] - M_ref[:3, 3])) <= TOL_MM
    assert replay_util._angle_deg(M_ref[:3, :3], M[:3, :3]) <= TOL_DEG
    # La 4×4 es R (de rvec) y la tvec filtrada; en float32 (pyigtl) cambia menos de 1e-3 mm.
    R, _ = cv2.Rodrigues(np.asarray(r["raw_pose"]["rvec_rad"]))
    assert np.allclose(M[:3, :3], R, atol=1e-12) and np.allclose(M[:3, 3], r["filter"]["tvec_filtered_mm"])
    assert M[3].tolist() == [0.0, 0.0, 0.0, 1.0]
    assert x["float32_max_diff_mm"] < 1e-3


@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("cam", CAMERAS)
def test_la_pose_cruda_reproyecta_las_esquinas(results, cam: str, frame: int) -> None:
    p = results[(cam, frame)]["raw_pose"]
    assert len(p["reproj_err_px"]) == 4
    assert max(p["reproj_err_px"]) <= MAX_REPROJ_PX, p["reproj_err_px"]
    assert p["reproj_max_px"] == max(p["reproj_err_px"])
    assert 0.0 < p["reproj_rms_px"] <= p["reproj_max_px"]
    assert p["tvec_mm"][2] > 0 and p["R"][2][2] < 0          # delante de la cámara, mirándola
    assert 0.0 <= p["tilt_deg"] < 90.0
    # El centro proyectado con distorsión queda a menos de 2 px del pinhole puro.
    c, c0 = np.asarray(p["center_projected_px"]), np.asarray(p["center_pinhole_px"])
    assert float(np.linalg.norm(c - c0)) < 2.0


@pytest.mark.parametrize("frame", FRAMES)
@pytest.mark.parametrize("cam", CAMERAS)
def test_otro_tamano_escala_la_traslacion_y_no_gira(results, cam: str, frame: int) -> None:
    s = results[(cam, frame)]["alt_size"]
    assert s["size_mm"] == ALT_SIZE_MM and s["expected_ratio"] == pytest.approx(ALT_SIZE_MM / 80.0)
    assert s["max_rel_err"] <= TOL_RATIO, s
    assert s["rotation_diff_deg"] <= TOL_ROT_DEG, s
    assert all(abs(q / s["expected_ratio"] - 1.0) <= TOL_RATIO for q in s["ratio"])


@pytest.mark.parametrize("cam", CAMERAS)
def test_la_k_de_la_grabacion_es_la_del_yml_del_perfil(results, cam: str) -> None:
    k = results[(cam, 480)]["intrinsics"]
    assert k["sha_matches"], (k["yml_sha256"], k["recording_sha256"])
    assert k["yml_sha256"] == replay_util.sha256(PROFILES_DIR.parent / "data" / k["calibration_file"])
    assert k["max_diff_K_vs_yml"] == 0.0 and k["max_diff_dist_vs_yml"] == 0.0
    assert len(k["dist"]) == 5 and k["fx"] > 0 and k["fy"] > 0


def test_la_distancia_a_mano_se_parece_a_la_de_la_pose(results) -> None:
    for r in results.values():
        h = r["hand_check"]
        # fx·lado_mm/lado_px frente a la Z de la pose: con el marker inclinado ~20°, a menos del 5 %.
        assert abs(h["diff_mm"]) / h["z_pose_mm"] < 0.05, h
        assert h["diff_mm"] == pytest.approx(h["z_from_side_mm"] - h["z_pose_mm"])


def test_format_markdown_es_determinista_y_vale_para_json(results) -> None:
    r = results[("gs1", 480)]
    md = explain_pose.format_markdown(r)
    assert md == explain_pose.format_markdown(json.loads(json.dumps(r)))
    assert md.endswith("\n") and "\r" not in md
    assert "**8 · La escala" in md and "frame_00480.png" in md and "Marker0ToTracker" in md
    assert max(len(ln) for ln in md.splitlines()) < 2000
    sin_alt = {k: v for k, v in r.items() if k != "alt_size"}
    assert "**8 · La escala" not in explain_pose.format_markdown(sin_alt)


def test_draw_example_recorta_alrededor_del_marker(results) -> None:
    r = results[("gs1", 480)]
    gray = cv2.imread(str(TESTS_DATA_DIR / "marker0_gs1_frames" / r["png"]), cv2.IMREAD_UNCHANGED)
    k = r["intrinsics"]
    img = explain_pose.draw_example(gray, r, k["K"], k["dist"], 320)
    assert img.shape == (320, 320, 3) and img.dtype == np.uint8
    assert not np.array_equal(img[..., 0], img[..., 1])        # algo de color dibujado
    assert explain_pose.draw_example(gray, r, k["K"], k["dist"], 200).shape == (200, 200, 3)
    with pytest.raises(ValueError):
        explain_pose.draw_example(gray, r, k["K"], k["dist"], 8)


def test_la_cli_escribe_y_no_pisa(tmp_path) -> None:
    p = _paths("gs1")
    out_md, out_png, out_json = tmp_path / "e.md", tmp_path / "e.png", tmp_path / "e.json"
    base = ["--dataset", str(p["dataset"]), "--frames-dir", str(p["frames"]), "--frame", "480",
            "--config", str(p["profile"]), "--alt-size-mm", "98.6"]
    assert explain_pose.main(base + ["--output-markdown", str(out_md), "--output-image", str(out_png),
                                     "--output-json", str(out_json), "--crop-px", "160"]) == 0
    assert out_md.read_text(encoding="utf-8").startswith("_Generado por")
    assert cv2.imread(str(out_png), cv2.IMREAD_UNCHANGED).shape == (160, 160, 3)
    assert json.loads(out_json.read_text(encoding="utf-8"))["frame"] == 480
    with pytest.raises(SystemExit):                              # no pisa
        explain_pose.main(base + ["--output-markdown", str(out_md)])
    with pytest.raises(SystemExit):                              # la figura tiene que ser .png
        explain_pose.main(base + ["--output-image", str(tmp_path / "e.jpg")])
    with pytest.raises(FileNotFoundError):                       # un frame sin PNG
        explain_pose.explain_frame(p["dataset"], p["frames"], 481, p["profile"])
    with pytest.raises(ValueError, match="markers.list"):        # un perfil sin ese marker
        explain_pose.explain_frame(p["dataset"], p["frames"], 480, p["profile"], name="NoExiste")
