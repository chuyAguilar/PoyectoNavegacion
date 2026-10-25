"""`vision/` sin camara (meta 003, fase 4): deteccion con lista blanca, pose de un
cuadrado proyectado con la K real de gs1, el 1-Euro igual al de antes sobre una
serie fija, y `MarkerTracker` (dict o secuencia, orden, filtros de cero).
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

import profiles
from vision import detection, filtering, pose, tracking

from .conftest import DATA_DIR, PROFILES_DIR
from .synthetic import DIST_SYN, K_SYN, render_marker

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"


def _cfg():
    return profiles.load(GS1)


def _k_real():
    fs = cv2.FileStorage(str(DATA_DIR / "intrinsecos_gs1_1280x960.yml"), cv2.FILE_STORAGE_READ)
    K = fs.getNode("camera_matrix").mat()
    dist = fs.getNode("distortion_coefficients").mat()
    fs.release()
    return K, dist


# ----------------------------------------------------------------------------
# detection
# ----------------------------------------------------------------------------

def test_get_dictionary_y_params() -> None:
    d = detection.get_dictionary("dict_aruco_mip_36h12")
    assert isinstance(d, cv2.aruco.Dictionary)
    with pytest.raises(ValueError, match="no disponible"):
        detection.get_dictionary("DICT_NO_EXISTE")
    p = cv2.aruco.DetectorParameters()
    detection.apply_detector_params(p, {"corner_refinement_win_size": 7, "min_marker_perimeter_rate": 0.02,
                                        "clave_desconocida": 1})
    assert p.cornerRefinementWinSize == 7 and p.minMarkerPerimeterRate == pytest.approx(0.02)
    detection.apply_detector_params(p, None)        # sin tuning: no falla


def test_create_detector_con_el_perfil_gs1() -> None:
    det = detection.create_detector(_cfg()["markers"])
    assert isinstance(det, cv2.aruco.ArucoDetector)
    p = det.getDetectorParameters()
    assert p.cornerRefinementMethod == cv2.aruco.CORNER_REFINE_SUBPIX
    assert p.adaptiveThreshWinSizeMax == 35 and p.cornerRefinementWinSize == 7


def test_detect_aplica_la_lista_blanca() -> None:
    det = detection.create_detector(_cfg()["markers"])
    frame0 = render_marker(450.0, 0.0, marker_id=0)
    frame7 = render_marker(450.0, 0.0, marker_id=7)
    gray0 = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY)
    gray7 = cv2.cvtColor(frame7, cv2.COLOR_BGR2GRAY)
    corners, ids = detection.detect(det, gray0, {0})
    assert ids is not None and ids.flatten().tolist() == [0]
    assert len(corners) == 1 and corners[0].shape == (1, 4, 2)
    corners7, ids7 = detection.detect(det, gray7, {0})           # 7 se ve pero no es del perfil
    assert ids7 is None and corners7 == ()
    _c, ids_all = detection.detect(det, gray7, {0, 7})
    assert ids_all.flatten().tolist() == [7]
    _c, ids_none = detection.detect(det, np.full((100, 100), 110, np.uint8), {0})
    assert ids_none is None


# ----------------------------------------------------------------------------
# pose
# ----------------------------------------------------------------------------

def test_build_object_points_orden_ippe_square() -> None:
    o = pose.build_object_points(80.0)
    assert o.dtype == np.float32 and o.shape == (4, 3)
    assert o.tolist() == [[-40, 40, 0], [40, 40, 0], [40, -40, 0], [-40, -40, 0]]


@pytest.mark.parametrize("tvec,euler", [([12.0, -30.0, 450.0], [182.0, 6.0, 3.0]),
                                        ([-80.0, 40.0, 380.0], [170.0, -12.0, 20.0]),
                                        ([0.0, 0.0, 600.0], [178.0, 2.0, 0.0])])
def test_estimate_single_pose_recupera_un_cuadrado_proyectado_con_K_real(tvec, euler) -> None:
    """Un cuadrado de 80 mm proyectado con la K y la distorsion reales de gs1: la pose
    vuelve con error < 1e-3 mm y < 1e-2 grados. El plan pedia < 1e-6 mm; el suelo
    real es el float32 de las esquinas (la funcion, como la de antes, las pasa a
    float32: ~1e-4 px a 1000 px dan 2.6e-5 mm a 450 mm y 1.4e-4 mm en z a 600 mm,
    medido 2026-10-24). De frente exacto (180, 0, 0) las dos soluciones de IPPE
    coinciden y la orientacion queda mal condicionada (1.4e-3 mm, 0.03 grados,
    medido): por eso el tercer caso va 2 grados ladeado."""
    K, dist = _k_real()
    rvec = Rotation.from_euler("xyz", euler, degrees=True).as_rotvec().reshape(3, 1)
    t = np.array(tvec, dtype=np.float64).reshape(3, 1)
    img, _ = cv2.projectPoints(pose.build_object_points(80.0).astype(np.float64), rvec, t, K, dist)
    r = pose.estimate_single_pose(img.reshape(1, 4, 2), 80.0, K, dist)
    assert r is not None
    rvec_hat, tvec_hat = r
    assert np.linalg.norm(tvec_hat.flatten() - t.flatten()) < 1e-3
    R_true, _ = cv2.Rodrigues(rvec)
    R_hat, _ = cv2.Rodrigues(rvec_hat)
    ang = np.degrees(np.arccos(np.clip((np.trace(R_true.T @ R_hat) - 1) / 2, -1, 1)))
    assert ang < 1e-2


def test_estimate_single_pose_descarta_z_no_positiva(monkeypatch) -> None:
    def pnp_detras(*a, **k):
        return True, np.zeros((3, 1)), np.array([[0.0], [0.0], [-400.0]])
    monkeypatch.setattr(pose.cv2, "solvePnP", pnp_detras)
    assert pose.estimate_single_pose(np.zeros((1, 4, 2), np.float32), 80.0, K_SYN, DIST_SYN) is None
    monkeypatch.setattr(pose.cv2, "solvePnP", lambda *a, **k: (False, None, None))
    assert pose.estimate_single_pose(np.zeros((1, 4, 2), np.float32), 80.0, K_SYN, DIST_SYN) is None


def test_rvec_tvec_to_matrix() -> None:
    rvec = np.array([[0.1], [-0.2], [0.3]])
    tvec = np.array([[1.0], [2.0], [3.0]])
    M = pose.rvec_tvec_to_matrix(rvec, tvec)
    R, _ = cv2.Rodrigues(rvec)
    assert M.shape == (4, 4) and M.dtype == np.float64
    assert np.array_equal(M[:3, :3], R) and M[:3, 3].tolist() == [1.0, 2.0, 3.0]
    assert M[3].tolist() == [0.0, 0.0, 0.0, 1.0]


# ----------------------------------------------------------------------------
# filtering: el 1-Euro de antes, copiado aqui como referencia
# ----------------------------------------------------------------------------

class _OneEuroAntes:
    """`tracker.OneEuroFilter.filtrar` tal como estaba hasta la fase 3 (referencia fija)."""

    def __init__(self, min_cutoff=1.0, beta=0.0):
        self.min_cutoff, self.beta = min_cutoff, beta
        self.x_prev, self.dx_prev, self.t_prev = None, 0.0, None

    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filtrar(self, x, t):
        if self.t_prev is None:
            self.t_prev, self.x_prev = t, x
            return x
        dt = max(t - self.t_prev, 1e-3)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(1.0, dt)
        dx_smooth = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * np.abs(dx_smooth)
        a = self._alpha(cutoff, dt)
        x_smooth = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_smooth, dx_smooth, t
        return x_smooth


def _serie():
    rng = np.random.default_rng(3)
    t = 1000.0 + np.cumsum(np.full(200, 0.03) + rng.uniform(-0.01, 0.01, 200))
    t[50] = t[49]                                   # dt = 0 -> el minimo de 1e-3
    x = 450.0 + 0.05 * rng.standard_normal(200) + np.where(np.arange(200) > 120, 8.0, 0.0)
    return t, x


def test_one_euro_igual_al_de_antes_bit_a_bit() -> None:
    t, x = _serie()
    nuevo, viejo = filtering.OneEuroFilter(2.0, 0.05), _OneEuroAntes(2.0, 0.05)
    out = [nuevo.filter(xi, ti) for xi, ti in zip(x, t)]
    ref = [viejo.filtrar(xi, ti) for xi, ti in zip(x, t)]
    assert out == ref                               # igualdad exacta, no approx
    assert out[0] == x[0] and abs(out[-1] - 458.0) < 0.5 and out[121] < 456.0   # suaviza el salto


def test_position_filter_son_tres_one_euro() -> None:
    t, x = _serie()
    pf = filtering.PositionFilter(2.0, 0.05)
    refs = [_OneEuroAntes(2.0, 0.05) for _ in range(3)]
    for k, (ti, xi) in enumerate(zip(t[:40], x[:40])):
        tv = np.array([[xi], [xi * 0.5], [-xi]])
        out = pf.filter(tv, ti)
        assert out.shape == (3, 1)
        esperado = [refs[j].filtrar(tv.flatten()[j], ti) for j in range(3)]
        assert out.flatten().tolist() == esperado


# ----------------------------------------------------------------------------
# tracking
# ----------------------------------------------------------------------------

def test_marker_tracker_con_gs1_detecta_y_estima_marker0() -> None:
    cfg = _cfg()
    mt = tracking.MarkerTracker(cfg["markers"], cfg["filtering"])
    assert mt.valid_ids == {0} and set(mt.filters) == {0}
    gray = cv2.cvtColor(render_marker(450.0, 2.0), cv2.COLOR_BGR2GRAY)
    poses = mt.process(gray, 1000.0, K_SYN, DIST_SYN)
    assert len(poses) == 1
    p = poses[0]
    assert isinstance(p, tracking.MarkerPose)
    assert (p.id, p.name, p.size_mm) == (0, "Marker0", 80.0)
    assert p.matrix.shape == (4, 4) and 440.0 < p.matrix[2, 3] < 460.0
    assert np.array_equal(p.matrix, pose.rvec_tvec_to_matrix(p.rvec, p.tvec))
    assert p.corners.shape == (1, 4, 2)
    assert mt.process(np.full((100, 100), 110, np.uint8), 1000.1, K_SYN, DIST_SYN) == []


def test_process_corners_dict_o_secuencia_en_orden_y_filtro_de_cero() -> None:
    cfg = _cfg()
    cfg["markers"]["list"].append({"id": 7, "name": "Otro", "size_mm": 40.0})
    gray0 = cv2.cvtColor(render_marker(450.0, 0.0, 0), cv2.COLOR_BGR2GRAY)
    gray7 = cv2.cvtColor(render_marker(500.0, 0.0, 7, size_mm=40.0), cv2.COLOR_BGR2GRAY)
    mt = tracking.MarkerTracker(cfg["markers"], {"enabled": False})
    c0, _ = mt.detect(gray0)
    c7, _ = mt.detect(gray7)
    sin_filtro = mt.process_corners([(7, c7[0]), (0, c0[0]), (99, c0[0])], 1000.0, K_SYN, DIST_SYN)
    assert [p.name for p in sin_filtro] == ["Otro", "Marker0"]      # orden de entrada; 99 fuera
    por_dict = mt.process_corners({0: c0[0], 7: c7[0]}, 1000.0, K_SYN, DIST_SYN)
    assert [p.name for p in por_dict] == ["Marker0", "Otro"]
    assert np.array_equal(por_dict[0].matrix, sin_filtro[1].matrix)

    con = tracking.MarkerTracker(cfg["markers"], cfg["filtering"])
    a = con.process_corners([(0, c0[0])], 1000.0, K_SYN, DIST_SYN)[0]
    b = con.process_corners([(0, c0[0])], 1000.5, K_SYN, DIST_SYN)[0]
    assert np.array_equal(a.tvec, sin_filtro[1].tvec)              # la primera muestra sale tal cual
    assert np.allclose(b.tvec, a.tvec)
    con.reset()
    c = con.process_corners([(0, c0[0])], 1000.6, K_SYN, DIST_SYN)[0]
    assert np.array_equal(c.tvec, a.tvec)                          # tras reset, primera muestra otra vez
    assert con.process_corners([], 1000.7, K_SYN, DIST_SYN) == []
