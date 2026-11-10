"""calibration.calibrate_extrinsics sin camara (meta 006, fase 7 · Los extrinsecos por tablero).

Dos camaras sinteticas con R, T conocidos y el tablero de 8x5 esquinas proyectado en las dos:
`calibrar_par` recupera R y T a < 0.01 mm y < 0.001 grados (el criterio del plan); la
reproyeccion cruzada de control y la distancia triangulada entre esquinas opuestas salen ~0
y se van del criterio si los extrinsecos estan mal; `emparejar_orden` deshace los cuatro
ordenes de las esquinas y aparta la vista en la que el tablero se movio entre camaras; las
carpetas de frames por posicion y camara (con intentos repetidos); `main --desde-vistas` de
punta a punta con vistas renderizadas (el `.yml`, que no se pisa, y sus codigos de salida);
y el criterio 1 con unos extrinsecos dados sobre el recorte de `tests/data/fusion_gs1_gs2/`.
"""
from __future__ import annotations

import json

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from calibration import calibrate_camera as cc
from calibration import calibrate_extrinsics as ce
from fusion import dataset as ds
from fusion import experiment as fx
from fusion import extrinsics as ex
from fusion import geometry as g

from . import tablero_sintetico as ts
from .conftest import DATA_DIR, TESTS_DATA_DIR

COLS, ROWS, SQ = 8, 5, 24.86
N = COLS * ROWS
NOMINAL = SQ * float(np.hypot(COLS - 1, ROWS - 1))          # 200.43 mm
SHAPE = (1280, 960)
K1 = ts.K_de(850.0, 849.0, 603.0, 489.0)
D1 = np.array([0.017, 0.011, 0.0028, -0.0009, -0.1065])
K2 = ts.K_de(846.0, 845.0, 640.0, 390.0)
D2 = np.array([0.02, -0.01, 0.001, 0.0005, -0.05])
RECORTE = TESTS_DATA_DIR / "fusion_gs1_gs2"
INTRINSICS = {"gs1": DATA_DIR / "intrinsecos_gs1_1280x960.yml", "gs2": DATA_DIR / "intrinsecos_gs2_1280x960.yml"}


def camara_2(angulo_deg: float = 41.5, centro=(-180.0, 15.0, 60.0)) -> np.ndarray:
    """`T_gs2<-gs1` (x2 = R x1 + T): gs2 con su centro en `centro` (frame de gs1) y girada
    `angulo_deg` hacia el eje de gs1, con un poco de giro en los otros dos ejes."""
    T = np.eye(4)
    T[:3, :3] = cv2.Rodrigues(np.array([0.02, np.radians(-angulo_deg), 0.03]))[0]
    T[:3, 3] = -T[:3, :3] @ np.asarray(centro, dtype=np.float64)
    return T


def escena(n: int, T_b_a: np.ndarray, Ka=K1, da=D1, Kb=K2, db=D2, shape=SHAPE, semilla: int = 3,
           z_mm=(380.0, 520.0), ang_max: float = 0.45, margen: int = 8, candidatas: int = 80):
    """`n` vistas del tablero validas en las dos camaras: `(objs, img_a, img_b, poses_a)`."""
    objs, img1, poses = ts.vistas_sinteticas(Ka, da, COLS, ROWS, SQ, shape, candidatas, semilla=semilla,
                                             z_mm=z_mm, ang_max=ang_max)
    o, a, b, pa = [], [], [], []
    for objp, i1, (rvec, tvec) in zip(objs, img1, poses):
        Ta = np.eye(4)
        Ta[:3, :3], Ta[:3, 3] = cv2.Rodrigues(rvec)[0], tvec
        Tb = T_b_a @ Ta
        i2 = ts.proyectar(objp, cv2.Rodrigues(Tb[:3, :3])[0], Tb[:3, 3], Kb, db)
        if Tb[2, 3] > 0 and ts.dentro(i1, shape, margen) and ts.dentro(i2, shape, margen):
            o.append(objp), a.append(i1), b.append(i2), pa.append(Ta)
        if len(o) == n:
            return o, a, b, pa
    raise RuntimeError(f"solo {len(o)} vistas validas en las dos camaras de {n}")


@pytest.fixture(scope="module")
def par():
    T = camara_2()
    return (T, *escena(18, T))


# ----------------------------------------------------------------------------
# El ajuste y su validacion
# ----------------------------------------------------------------------------

def test_calibrar_par_recupera_R_y_T_sinteticos(par) -> None:
    T, objs, a, b, _pa = par
    r = ce.calibrar_par(objs, a, b, K1, D1, K2, D2, SHAPE, n_control=3, semilla=0)
    dmm, ddeg = g.pose_difference(r["T_b_a"], T)
    assert dmm < 0.01 and ddeg < 0.001, (dmm, ddeg)             # el criterio del plan, sin ruido
    assert dmm < 1e-3, dmm
    assert np.allclose(r["T_a_b"] @ r["T_b_a"], np.eye(4), atol=1e-12)
    assert np.allclose(r["R"], r["T_b_a"][:3, :3]) and np.allclose(r["T"], r["T_b_a"][:3, 3])
    assert r["n_vistas_usadas"] == 15 and r["n_control"] == 3 and len(r["errores_vista_px"]) == 15
    assert sorted(r["indices_fit"] + r["indices_control"]) == list(range(18))
    assert r["indices_control"] == cc.elegir_control(18, 3, 0)
    assert r["rms_px"] < 1e-3 and r["rms_control_px"] < 1e-2 and r["rms_control_inverso_px"] < 1e-2
    assert r["base_mm"] == pytest.approx(float(np.linalg.norm([-180.0, 15.0, 60.0])), abs=1e-3)
    assert r["angulo_deg"] == pytest.approx(ex.optical_axis_angle_deg(g.inv(T)), abs=1e-4)
    assert 41.0 < r["angulo_deg"] < 42.0


def test_calibrar_par_con_ruido_y_errores(par) -> None:
    T, objs, a, b, _pa = par
    rng = np.random.default_rng(7)
    an = [(x + rng.normal(0, 0.1, x.shape)).astype(np.float32) for x in a]
    bn = [(x + rng.normal(0, 0.1, x.shape)).astype(np.float32) for x in b]
    r = ce.calibrar_par(objs, an, bn, K1, D1, K2, D2, SHAPE, n_control=3, semilla=1)
    dmm, ddeg = g.pose_difference(r["T_b_a"], T)
    assert dmm < 0.3 and ddeg < 0.05, (dmm, ddeg)               # 0.1 px de ruido por esquina
    assert 0.05 < r["rms_px"] < 0.2 and r["rms_control_px"] < 0.75
    # La distancia entre dos esquinas sueltas es lo mas sensible al ruido: con 0.1 px por esquina
    # (una vista sin promediar frames) el peor error ya ronda los 0.3 mm del criterio (0.297 aqui).
    tri = ce.distancias_trianguladas([an[i] for i in r["indices_control"]], [bn[i] for i in r["indices_control"]],
                                     K1, D1, K2, D2, r["R"], r["T"], COLS, ROWS, SQ)
    assert 0.05 < tri["peor_error_mm"] < 0.5 and abs(tri["media_error_mm"]) < 0.2
    assert max(f["ajuste_rigido_rms_mm"] for f in tri["por_vista"]) < 0.5        # 0.228 medido
    with pytest.raises(ValueError):
        ce.calibrar_par(objs, a, b[:-1], K1, D1, K2, D2, SHAPE)
    with pytest.raises(ValueError):
        ce.calibrar_par(objs[:3], a[:3], b[:3], K1, D1, K2, D2, SHAPE, n_control=2)     # queda 1 para el ajuste


def test_distancias_trianguladas_y_criterio(par) -> None:
    T, _objs, a, b, pa = par
    R, t = T[:3, :3], T[:3, 3]
    tri = ce.distancias_trianguladas(a[:3], b[:3], K1, D1, K2, D2, R, t, COLS, ROWS, SQ)
    assert tri["nominal_mm"] == pytest.approx(NOMINAL) and NOMINAL == pytest.approx(200.4277, abs=1e-3)
    assert tri["n_vistas"] == 3 and tri["peor_error_mm"] < 0.01
    for fila, Ta in zip(tri["por_vista"], pa):
        assert fila["ajuste_rigido_rms_mm"] < 0.01 and len(fila["diagonales_mm"]) == 2
        assert fila["z_mm"] == pytest.approx(float((Ta @ np.array([3.5 * SQ, 2.0 * SQ, 0.0, 1.0]))[2]), abs=0.05)
    X = ce.triangular(a[0], b[0], K1, D1, K2, D2, R, t)
    esperado = (pa[0] @ np.c_[cc.construir_objp(COLS, ROWS, SQ).astype(np.float64), np.ones(N)].T).T[:, :3]
    assert np.abs(X - esperado).max() < 0.01
    # Sin lado no hay nominal ni error; con la base un 1 % larga, la escala se va ~2 mm en 200.
    sin = ce.distancias_trianguladas(a[:1], b[:1], K1, D1, K2, D2, R, t, COLS, ROWS)
    assert sin["nominal_mm"] is None and "peor_error_mm" not in sin
    mal = ce.distancias_trianguladas(a[:3], b[:3], K1, D1, K2, D2, R, 1.01 * t, COLS, ROWS, SQ)
    assert 1.5 < mal["peor_error_mm"] < 2.5 and mal["media_error_mm"] > 1.5
    r = {"n_vistas_usadas": 15, "rms_px": 0.2, "rms_control_px": 0.3}
    assert ce.evaluar_criterio(r, tri) == []
    assert any("triangulada" in f for f in ce.evaluar_criterio(r, mal))
    assert any("sin distancia" in f for f in ce.evaluar_criterio(r, None))
    assert len(ce.evaluar_criterio({"n_vistas_usadas": 14, "rms_px": 0.6, "rms_control_px": 0.8}, tri)) == 3
    assert any("sin vistas de control" in f for f in ce.evaluar_criterio({"n_vistas_usadas": 15, "rms_px": 0.1, "rms_control_px": None}, tri))


def test_control_cruzado_delata_unos_extrinsecos_girados(par) -> None:
    T, objs, a, b, _pa = par
    assert ce.control_cruzado(objs[0], a[0], b[0], K1, D1, K2, D2, T) < 1e-2
    assert ce.control_cruzado(objs[0], b[0], a[0], K2, D2, K1, D1, g.inv(T)) < 1e-2
    girada = T.copy()
    girada[:3, :3] = Rotation.from_euler("y", 0.2, degrees=True).as_matrix() @ T[:3, :3]
    assert ce.control_cruzado(objs[0], a[0], b[0], K1, D1, K2, D2, girada) > 0.75       # 0.2 grados ~ 3 px


# ----------------------------------------------------------------------------
# El orden de las esquinas
# ----------------------------------------------------------------------------

def test_reordenar() -> None:
    x = np.arange(N * 2, dtype=np.float64).reshape(N, 2)
    assert np.array_equal(ce.reordenar(x, COLS, ROWS, "directo"), x)
    assert np.array_equal(ce.reordenar(x, COLS, ROWS, "invertido"), x[::-1])
    esp = ce.reordenar(x, COLS, ROWS, "espejo_columnas")
    assert np.array_equal(esp[0], x[COLS - 1]) and np.array_equal(esp[COLS - 1], x[0]) and np.array_equal(esp[COLS], x[2 * COLS - 1])
    fil = ce.reordenar(x, COLS, ROWS, "espejo_filas")
    assert np.array_equal(fil[0], x[N - COLS]) and np.array_equal(fil[N - 1], x[COLS - 1])
    for orden in ce.ORDENES:                                     # cada orden se deshace con el mismo
        assert np.array_equal(ce.reordenar(ce.reordenar(x, COLS, ROWS, orden), COLS, ROWS, orden), x)
        assert ce.reordenar(x.reshape(N, 1, 2), COLS, ROWS, orden).shape == (N, 2)
    with pytest.raises(ValueError):
        ce.reordenar(x, COLS, ROWS, "otro")


def test_emparejar_orden_deshace_los_cuatro_ordenes(par) -> None:
    T, objs, a, b, _pa = par
    aplicados = [ce.ORDENES[k % 4] for k in range(len(b))]
    revueltas = [ce.reordenar(x, COLS, ROWS, o).astype(np.float32).reshape(-1, 1, 2) for x, o in zip(b, aplicados)]
    e = ce.emparejar_orden(objs[0], a, revueltas, K1, D1, K2, D2, COLS, ROWS)
    assert e["ordenes"] == aplicados and all(e["coherente"]) and e["apoyo"] == len(b) - 1
    for x, y in zip(e["img_b"], b):
        assert x.shape == (N, 1, 2) and x.dtype == np.float32 and np.allclose(x, y, atol=1e-4)
    dmm, ddeg = g.pose_difference(e["T_b_a"], T)
    assert dmm < 0.05 and ddeg < 0.01
    r = ce.calibrar_par(objs, a, e["img_b"], K1, D1, K2, D2, SHAPE)
    assert g.pose_difference(r["T_b_a"], T)[0] < 0.01
    # Todas del reves a la vez: el orden comun tambien sale.
    todas = [ce.reordenar(x, COLS, ROWS, "invertido") for x in b]
    e2 = ce.emparejar_orden(objs[0], a, todas, K1, D1, K2, D2, COLS, ROWS)
    assert set(e2["ordenes"]) == {"invertido"} and all(e2["coherente"])
    with pytest.raises(ValueError):
        ce.emparejar_orden(objs[0], a[:1], b[:1], K1, D1, K2, D2, COLS, ROWS)
    with pytest.raises(ValueError):
        ce.emparejar_orden(objs[0], a, b[:-1], K1, D1, K2, D2, COLS, ROWS)


def test_emparejar_orden_aparta_la_vista_en_que_el_tablero_se_movio(par) -> None:
    _T, objs, a, b, _pa = par
    movida = list(b)
    movida[4] = b[9]                    # gs2 vio el tablero en otro sitio que gs1
    e = ce.emparejar_orden(objs[0], a, movida, K1, D1, K2, D2, COLS, ROWS)
    assert [k for k, ok in enumerate(e["coherente"]) if not ok] == [4]
    assert e["apoyo"] == len(b) - 2


# ----------------------------------------------------------------------------
# La comparacion con los de Marker0 y el criterio 1
# ----------------------------------------------------------------------------

def test_comparar_extrinsecos_y_alternativas(par) -> None:
    T12 = g.inv(par[0])
    delta = np.eye(4)
    delta[:3, :3] = Rotation.from_euler("y", 0.5, degrees=True).as_matrix()
    delta[:3, 3] = [2.0, 0.0, 0.0]
    otro = T12 @ delta
    c = ce.comparar_extrinsecos(T12, otro)
    assert c["dt_mm"] == pytest.approx(2.0, abs=1e-9) and c["dR_deg"] == pytest.approx(0.5, abs=1e-9)
    p = np.array([0.0, 0.0, 370.0, 1.0])
    assert c["punto_a_mm"] == 370.0
    assert c["punto_se_mueve_mm"] == pytest.approx(float(np.linalg.norm((delta @ p - p)[:3])), abs=1e-9)
    assert 5.0 < c["punto_se_mueve_mm"] < 5.5                    # 2 mm + 370 mm x 0.5 grados
    igual = ce.comparar_extrinsecos(T12, T12)
    assert igual["dt_mm"] == 0.0 and igual["punto_se_mueve_mm"] == 0.0 and igual["dbase_mm"] == 0.0
    rep = {"datos": "20261109-163350", "extrinsecos": {"T_ref_other": otro.tolist(), "spread_mm": 15.4, "spread_deg": 2.6, "angle_deg": 41.5},
           "criterio_1": {"peor_mm": 4.198, "peor_deg": 6.087, "cumple": False},
           "consistencia": {"bundle": {"T_ref_other": T12.tolist(), "rms_px": 0.298, "angle_deg": 41.0}}}
    alts = ce.alternativas_de_resultados(rep)
    assert set(alts) == {"marker0", "bundle"} and alts["marker0"]["method"] == "marker0"
    assert np.allclose(alts["marker0"]["T_ref_other"], otro) and alts["marker0"]["criterio_1_peor_mm"] == 4.198
    assert alts["bundle"]["rms_px"] == 0.298 and alts["marker0"]["criterio_1_cumple"] is False
    del rep["consistencia"]
    assert set(ce.alternativas_de_resultados(rep)) == {"marker0"}
    with pytest.raises(ValueError):
        ce.alternativas_de_resultados({"criterio_1": {}})


def test_criterio_1_con_unos_extrinsecos_dados(tmp_path) -> None:
    """Sobre el recorte de la grabacion: por posicion de S2, lo mismo que `agreement_stats` a mano."""
    T = fx.run_experiment(RECORTE, INTRINSICS, None, ("numpy_pose",), log=lambda *_a: None)["extrinsecos"]["T_ref_other"]
    c1 = ce.criterio_1_con(T, RECORTE, INTRINSICS)
    assert [r["segmento"] for r in c1["por_posicion"]] == [f"S2_pos{k}" for k in range(1, 6)] and c1["fuera"] == []
    assert c1["posiciones"] == 5 and c1["datos"] == RECORTE.name and not any(r["repetida"] for r in c1["por_posicion"])
    for r in c1["por_posicion"]:
        tracks = ds.load_segment(RECORTE, r["segmento"])
        pairs, _tol = fx.pairs_of(tracks)
        agr = ex.agreement_stats(tracks["gs1"].T_raw[pairs[:, 0]], ex.apply_extrinsics(T, tracks["gs2"].T_raw[pairs[:, 1]]))
        assert r["mean_mm"] == agr["mean_mm"] and r["mean_deg"] == agr["mean_deg"] and r["n"] == len(pairs)
    assert c1["peor_mm"] == max(r["mean_mm"] for r in c1["por_posicion"])
    assert c1["peor_deg"] == max(r["mean_deg"] for r in c1["por_posicion"])
    assert c1["cumple"] is False and c1["umbral_mm"] == 0.5 and c1["umbral_deg"] == 0.2     # B94: la grabacion de la Jetson
    # Otros intrinsecos que los grabados: el segmento queda fuera, con su motivo.
    otro = tmp_path / "otro.yml"
    otro.write_bytes(INTRINSICS["gs2"].read_bytes() + b"\n# otro\n")
    fuera = ce.criterio_1_con(T, RECORTE, {"gs1": INTRINSICS["gs1"], "gs2": otro})
    assert fuera["cumple"] is None and len(fuera["fuera"]) == 5 and fuera["por_posicion"] == []
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    assert ce.criterio_1_con(T, vacia, INTRINSICS)["cumple"] is None
    with pytest.raises(FileNotFoundError):
        ce.criterio_1_con(T, tmp_path / "no_existe", INTRINSICS)


# ----------------------------------------------------------------------------
# Las carpetas de frames
# ----------------------------------------------------------------------------

K_640 = ts.K_de(600.0, 600.0, 320.0, 240.0)
K2_640 = ts.K_de(590.0, 592.0, 310.0, 250.0)
SHAPE_640 = (640, 480)
SIN_DIST = np.zeros(5)
RVEC_1 = np.array([0.25, -0.2, 0.1])
TVEC_1 = ts.pose_hacia(K_640, RVEC_1, (330.0, 235.0), 600.0, COLS, ROWS, SQ)


def _guardar(carpeta, imagenes) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    for k, img in enumerate(imagenes):
        assert cv2.imwrite(str(carpeta / f"frame_{30 * k:05d}.png"), img)


def test_listar_posiciones_con_intentos(tmp_path) -> None:
    for nombre in ("T01_gs1_frames", "T01_gs2_frames", "T02_gs1_frames", "T03_gs1_frames", "T03_gs2_frames",
                   "T03_gs1_r2_frames", "T03_gs2_r2_frames", "T04_gs1_frames", "T04_gs2_frames", "T04_gs1_r2_frames",
                   "M1_gs1_frames_viejo", "otra_cosa"):
        (tmp_path / nombre).mkdir()
    (tmp_path / "T09_gs1_frames").write_text("no es una carpeta", encoding="utf-8")
    pos = ce.listar_posiciones(tmp_path)
    assert list(pos) == ["T01", "T02", "T03", "T04"]
    assert pos["T01"]["intento"] == 1 and set(pos["T01"]["carpetas"]) == {"gs1", "gs2"}
    assert set(pos["T02"]["carpetas"]) == {"gs1"}
    assert pos["T03"]["intento"] == 2 and pos["T03"]["carpetas"]["gs2"].name == "T03_gs2_r2_frames"
    assert pos["T04"]["intento"] == 1 and set(pos["T04"]["carpetas"]) == {"gs1", "gs2"}     # el r2 no tiene las dos
    with pytest.raises(FileNotFoundError):
        ce.listar_posiciones(tmp_path / "no_existe")


def test_esquinas_de_posicion(tmp_path) -> None:
    vista = ts.renderizar_vista(K_640, RVEC_1, TVEC_1, COLS, ROWS, SQ, SHAPE_640)
    movida = ts.renderizar_vista(K_640, RVEC_1, TVEC_1 + np.array([1.0, 0.0, 0.0]), COLS, ROWS, SQ, SHAPE_640)   # 1 mm = 1 px
    gris = np.full((480, 640), 128, dtype=np.uint8)
    _guardar(tmp_path / "quieta", [gris, vista, vista, vista])
    e = ce.esquinas_de_posicion(tmp_path / "quieta", COLS, ROWS, "clasico", n_frames=3)
    assert e["n_frames"] == 3 and e["n_detectados"] == 3 and e["movimiento_px"] == 0.0 and e["motivo"] is None
    assert e["shape"] == SHAPE_640 and e["esquinas"].shape == (N, 1, 2) and e["esquinas"].dtype == np.float32
    verdad = ts.proyectar(cc.construir_objp(COLS, ROWS, SQ), RVEC_1, TVEC_1, K_640).reshape(-1, 2)
    d = min(np.abs(ce.reordenar(e["esquinas"], COLS, ROWS, o) - verdad).max() for o in ce.ORDENES)
    assert d < 1.0, d
    # Los 4 ultimos incluyen el frame sin tablero: con 3 de 4 sigue valiendo.
    assert ce.esquinas_de_posicion(tmp_path / "quieta", COLS, ROWS, "clasico", n_frames=4)["n_detectados"] == 3
    _guardar(tmp_path / "movida", [vista, vista, movida])
    m = ce.esquinas_de_posicion(tmp_path / "movida", COLS, ROWS, "clasico", n_frames=3, max_mov_px=0.3)
    assert m["esquinas"] is None and "se movio" in m["motivo"] and 0.4 < m["movimiento_px"] < 0.9
    assert ce.esquinas_de_posicion(tmp_path / "movida", COLS, ROWS, "clasico", n_frames=3, max_mov_px=2.0)["esquinas"] is not None
    _guardar(tmp_path / "nada", [gris, gris, vista])
    n = ce.esquinas_de_posicion(tmp_path / "nada", COLS, ROWS, "clasico", n_frames=3)
    assert n["esquinas"] is None and "1 de 3" in n["motivo"]
    _guardar(tmp_path / "una", [vista])
    u = ce.esquinas_de_posicion(tmp_path / "una", COLS, ROWS, "clasico")
    assert u["esquinas"] is not None and u["movimiento_px"] is None and u["n_frames"] == 1
    (tmp_path / "vacia").mkdir()
    assert "sin frames" in ce.esquinas_de_posicion(tmp_path / "vacia", COLS, ROWS, "clasico")["motivo"]
    assert "sin frames" in ce.esquinas_de_posicion(tmp_path / "no_existe", COLS, ROWS, "clasico")["motivo"]
    _guardar(tmp_path / "mezcla", [vista, np.full((240, 320), 128, dtype=np.uint8)])
    with pytest.raises(ValueError):
        ce.esquinas_de_posicion(tmp_path / "mezcla", COLS, ROWS, "clasico")


# ----------------------------------------------------------------------------
# main, de punta a punta, con vistas renderizadas (sin distorsion: la homografia es exacta)
# ----------------------------------------------------------------------------

N_POS = 8


def _yml(ruta, K, w: int = 640, h: int = 480, detector: str = "clasico"):
    cc.guardar_yml(ruta, K, SIN_DIST, w, h, 0.1, 20, COLS, ROWS, SQ, {"detector": detector})
    return ruta


@pytest.fixture(scope="module")
def sesion(tmp_path_factory):
    """Una carpeta como la de `correr.ps1`: N_POS posiciones, dos frames por camara, 640x480."""
    base = tmp_path_factory.mktemp("tablero")
    T = camara_2(30.0, (-250.0, 10.0, 60.0))
    _objs, _a, _b, poses = escena(N_POS, T, K_640, SIN_DIST, K2_640, SIN_DIST, SHAPE_640, semilla=5,
                                  z_mm=(420.0, 520.0), ang_max=0.35, margen=70, candidatas=400)
    vistas = base / "datos"
    for k, Ta in enumerate(poses, start=1):
        Tb = T @ Ta
        for cam, K, Tc in (("gs1", K_640, Ta), ("gs2", K2_640, Tb)):
            img = ts.renderizar_vista(K, cv2.Rodrigues(Tc[:3, :3])[0].flatten(), Tc[:3, 3], COLS, ROWS, SQ, SHAPE_640)
            _guardar(vistas / f"T{k:02d}_{cam}_frames", [img, img])
    intr = {"gs1": _yml(base / "intrinsecos_gs1.yml", K_640), "gs2": _yml(base / "intrinsecos_gs2.yml", K2_640)}
    return {"base": base, "vistas": vistas, "T_b_a": T, "intr": intr}


def _argv(sesion, *extra: str, intr: dict | None = None) -> list[str]:
    i = intr or sesion["intr"]
    return ["--desde-vistas", str(sesion["vistas"]), "--intrinsecos", f"gs1={i['gs1']}", f"gs2={i['gs2']}",
            "--cols", str(COLS), "--rows", str(ROWS), "--square-mm", f"{SQ}", "--detector", "clasico",
            "--frames-por-vista", "2", "--min-vistas", "6", "--n-control", "2", "--timeout", "120", *extra]


def test_main_de_punta_a_punta(sesion, tmp_path) -> None:
    T12 = g.inv(sesion["T_b_a"])
    delta = np.eye(4)
    delta[:3, 3] = [3.0, 0.0, 0.0]
    resultados = tmp_path / "resultados.json"
    resultados.write_text(json.dumps({"datos": "S2-falsa", "extrinsecos": {"T_ref_other": (T12 @ delta).tolist(), "spread_mm": 15.4},
                                      "criterio_1": {"peor_mm": 4.2, "peor_deg": 6.1, "cumple": False}}), encoding="utf-8")
    yml, reporte = tmp_path / "extrinsecos_gs1_gs2_pinzas.yml", tmp_path / "rep.json"
    rc = ce.main(_argv(sesion, "--montaje", "pinzas", "--output", str(yml), "--reporte", str(reporte),
                       "--comparar-con", str(resultados)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    r = e["resultado"]
    assert rc == 0, r["fallos"]
    assert e["usables"] == N_POS and r["n_vistas_usadas"] == N_POS - 2 and len(r["posiciones_control"]) == 2 and r["cumple"] is True
    assert sorted(r["posiciones_ajuste"] + r["posiciones_control"]) == [f"T{k:02d}" for k in range(1, N_POS + 1)]
    assert r["rms_px"] < 0.5 and r["rms_control_px"] < 0.75 and r["triangulada_control"]["peor_error_mm"] < 0.3
    assert r["triangulada_control"]["nominal_mm"] == pytest.approx(NOMINAL)
    dmm, ddeg = g.pose_difference(np.asarray(r["T_ref_other"]), T12)
    assert dmm < 1.0 and ddeg < 0.2, (dmm, ddeg)        # esquinas detectadas en vistas renderizadas, no proyectadas
    assert e["orden"]["incoherentes"] == [] and set(e["orden"]["por_posicion"]) == set(r["posiciones"])
    assert e["comparacion"]["marker0"]["frente_al_tablero"]["dt_mm"] == pytest.approx(3.0, abs=1.0)
    assert set(e["cobertura"]) == {"gs1", "gs2"} and e["modo"] == "calibrar"
    ext = ex.load_extrinsics(yml, sesion["intr"])
    assert ext.method == "tablero" and ext.mount == "pinzas" and ext.reference == "gs1" and ext.other == "gs2"
    assert np.allclose(ext.T_ref_other, np.asarray(r["T_ref_other"]))
    assert ext.intrinsics_sha256 == {c: ds.sha256_file(p) for c, p in sesion["intr"].items()}
    assert ext.alternative["method"] == "marker0" and ext.alternative["criterio_1_peor_mm"] == 4.2
    assert ext.validation["rms_px"] == r["rms_px"] and ext.validation["criterio_1"] is None
    assert ext.validation["posiciones_control"] == r["posiciones_control"] and ext.angle_deg == pytest.approx(r["angulo_deg"])
    # No se pisa: la segunda corrida no empieza.
    antes = yml.read_bytes()
    assert ce.main(_argv(sesion, "--montaje", "pinzas", "--output", str(yml))) == 2
    assert yml.read_bytes() == antes
    # Sin --output corre igual y no escribe nada.
    assert ce.main(_argv(sesion, "--montaje", "pinzas")) == 0


def test_main_con_el_criterio_1(sesion, tmp_path) -> None:
    """`--criterio-1-datos` con el recorte: el numero va al reporte y al `.yml`, y no decide si se escribe.
    (Los frames son de 640x480 y el recorte es de las camaras reales: solo vale para ver el paso.)"""
    intr = {c: _yml(tmp_path / f"i_{c}.yml", K) for c, K in (("gs1", K_640), ("gs2", K2_640))}
    yml, reporte = tmp_path / "ext.yml", tmp_path / "rep.json"
    rc = ce.main(_argv(sesion, "--montaje", "estructura", "--output", str(yml), "--reporte", str(reporte),
                       "--criterio-1-datos", str(RECORTE), intr=intr))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 0 and yml.is_file()
    assert e["criterio_1"]["cumple"] is None and len(e["criterio_1"]["fuera"]) == 5      # otros intrinsecos que los grabados
    assert ex.load_extrinsics(yml, intr).validation["criterio_1"]["cumple"] is None
    assert ex.load_extrinsics(yml, intr).mount == "estructura" and ex.load_extrinsics(yml, intr).alternative is None


def test_main_con_los_intrinsecos_de_data_y_el_criterio_1(tmp_path) -> None:
    """Frames de 1280x960 con los `.yml` de `data/`: el criterio 1 se evalua sobre el recorte (son los
    intrinsecos con que se grabo). Las vistas se renderizan sin distorsion y los intrinsecos la tienen:
    ese desajuste de ~1 px basta para sacar la distancia triangulada del criterio (codigo 1, sin `.yml`)."""
    i1, i2 = ce.leer_intrinsecos(INTRINSICS["gs1"]), ce.leer_intrinsecos(INTRINSICS["gs2"])
    assert i1["shape"] == SHAPE and i1["detector"] == "sb" and i1["square_mm"] == pytest.approx(SQ) and i2["dist"].shape == (5,)
    T = camara_2()
    _o, _a, _b, poses = escena(8, T, i1["K"], SIN_DIST, i2["K"], SIN_DIST, SHAPE, semilla=5, z_mm=(400.0, 520.0),
                               ang_max=0.35, margen=140, candidatas=4000)
    vistas = tmp_path / "datos"
    for k, Ta in enumerate(poses, start=1):
        for cam, K, Tc in (("gs1", i1["K"], Ta), ("gs2", i2["K"], T @ Ta)):
            img = ts.renderizar_vista(K, cv2.Rodrigues(Tc[:3, :3])[0].flatten(), Tc[:3, 3], COLS, ROWS, SQ, SHAPE)
            _guardar(vistas / f"T{k:02d}_{cam}_frames", [img, img])
    yml, reporte = tmp_path / "ext.yml", tmp_path / "rep.json"
    rc = ce.main(["--desde-vistas", str(vistas), "--intrinsecos", f"gs1={INTRINSICS['gs1']}", f"gs2={INTRINSICS['gs2']}",
                  "--cols", str(COLS), "--rows", str(ROWS), "--square-mm", f"{SQ}", "--detector", "clasico",
                  "--frames-por-vista", "2", "--min-vistas", "6", "--n-control", "2", "--montaje", "pinzas",
                  "--criterio-1-datos", str(RECORTE), "--output", str(yml), "--reporte", str(reporte), "--timeout", "120"])
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 1 and not yml.exists() and e["resultado"]["cumple"] is False
    assert any("triangulada" in f for f in e["resultado"]["fallos"]) and e["resultado"]["triangulada_control"]["peor_error_mm"] > 0.3
    c1 = e["criterio_1"]
    assert c1["cumple"] is False and c1["posiciones"] == 5 and c1["fuera"] == [] and c1["datos"] == RECORTE.name
    assert c1["peor_mm"] == max(r["mean_mm"] for r in c1["por_posicion"]) and c1["min_parejas"] > 100


def test_main_solo_comprobar(sesion, tmp_path) -> None:
    reporte = tmp_path / "comprobar.json"
    assert ce.main(_argv(sesion, "--solo-comprobar", "--posiciones", "T03", "--reporte", str(reporte))) == 0
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert e["modo"] == "comprobar" and e["usables"] == 1 and [p["nombre"] for p in e["posiciones"]] == ["T03"]
    p = e["posiciones"][0]
    assert p["usable"] is True and p["motivo"] is None and set(p["camaras"]) == {"gs1", "gs2"}
    for cam in ("gs1", "gs2"):
        c = p["camaras"][cam]
        assert c["n_frames"] == 2 and c["n_detectados"] == 2 and c["movimiento_px"] == 0.0 and "esquinas" not in c
        assert 350.0 < c["z_mm"] < 650.0 and 0.0 <= c["inclinacion_deg"] < 60.0 and c["rms_pnp_px"] < 0.5
    assert "resultado" not in e
    # Una posicion sin tablero en gs2: codigo 1 y su motivo; las demas siguen usables.
    (sesion["base"] / "malas").mkdir(exist_ok=True)
    malas = sesion["base"] / "malas"
    gris = np.full((480, 640), 128, dtype=np.uint8)
    buena = cv2.imread(str(sorted((sesion["vistas"] / "T01_gs1_frames").glob("*.png"))[0]), cv2.IMREAD_GRAYSCALE)
    if not (malas / "T01_gs1_frames").exists():
        _guardar(malas / "T01_gs1_frames", [buena, buena])
        _guardar(malas / "T01_gs2_frames", [gris, gris])
        _guardar(malas / "T02_gs1_frames", [buena, buena])
    argv = _argv(sesion, "--solo-comprobar", "--reporte", str(reporte))
    argv[1] = str(malas)
    assert ce.main(argv) == 1
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert e["usables"] == 0 and "gs2: el detector clasico vio el tablero en 0 de 2" in e["posiciones"][0]["motivo"]
    assert "falta la carpeta de frames de gs2" in e["posiciones"][1]["motivo"]


def test_main_falla_fuerte(sesion, tmp_path) -> None:
    yml, reporte = tmp_path / "ext.yml", tmp_path / "rep.json"
    # Pocas posiciones para lo pedido: corrio y no cumple (1), sin .yml.
    argv = _argv(sesion, "--montaje", "pinzas", "--output", str(yml), "--reporte", str(reporte))
    argv[argv.index("--min-vistas") + 1] = "15"
    assert ce.main(argv) == 1 and not yml.exists()
    assert "hacen falta 17 posiciones usables" in json.loads(reporte.read_text(encoding="utf-8"))["error"]
    # Excluir a mano deja menos de las necesarias.
    assert ce.main(_argv(sesion, "--montaje", "pinzas", "--output", str(yml), "--excluir", "T01")) == 1 and not yml.exists()
    # Unos intrinsecos de gs2 con otra focal: el ajuste no cabe, codigo 1 y nada escrito.
    K_mala = K2_640.copy()
    K_mala[0, 0] *= 1.03
    mal = {"gs1": sesion["intr"]["gs1"], "gs2": _yml(tmp_path / "gs2_mala.yml", K_mala)}
    assert ce.main(_argv(sesion, "--montaje", "pinzas", "--output", str(yml), "--reporte", str(reporte), intr=mal)) == 1
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert e["resultado"]["cumple"] is False and e["resultado"]["fallos"] and not yml.exists()
    # Lo que no deja empezar: 2.
    otro_tamano = {"gs1": sesion["intr"]["gs1"], "gs2": _yml(tmp_path / "gs2_1280.yml", K2_640, 1280, 960)}
    assert ce.main(_argv(sesion, "--montaje", "pinzas", intr=otro_tamano)) == 2
    assert ce.main(_argv(sesion, "--montaje", "pinzas", intr={"gs1": sesion["intr"]["gs1"], "gs2": tmp_path / "no.yml"})) == 2
    assert ce.main(_argv(sesion, "--montaje", "pinzas", "--posiciones", "T99")) == 2
    assert ce.main(_argv(sesion, "--montaje", "pinzas", "--comparar-con", str(tmp_path / "no.json"))) == 2
    assert ce.main(_argv(sesion, "--montaje", "pinzas", "--criterio-1-datos", str(tmp_path / "no_hay"))) == 2
    argv = _argv(sesion, "--montaje", "pinzas")
    argv[1] = str(tmp_path / "sin_vistas")
    assert ce.main(argv) == 2
    (tmp_path / "sin_posiciones").mkdir()
    argv[1] = str(tmp_path / "sin_posiciones")
    assert ce.main(argv) == 2


def test_el_estado_que_escribiria_el_vigilante_es_json(sesion, tmp_path, monkeypatch) -> None:
    """Si salta el tope, `_vigilante` escribe `estado` con `json.dumps` a secas y sale con 2: con
    un ndarray dentro lanzaria en su hilo y el tope no pararia nada. `estado` solo lleva tipos de JSON."""
    visto: dict = {}
    real = ce._vigilante

    def espia(timeout, estado, salida):
        visto.update(timeout=timeout, estado=estado, salida=salida)
        return real(timeout, estado, salida)

    monkeypatch.setattr(ce, "_vigilante", espia)
    resultados = tmp_path / "resultados.json"
    resultados.write_text(json.dumps({"datos": "S2-falsa", "extrinsecos": {"T_ref_other": np.eye(4).tolist()},
                                      "consistencia": {"bundle": {"T_ref_other": np.eye(4).tolist(), "rms_px": 0.3}}}), encoding="utf-8")
    reporte = tmp_path / "rep.json"
    rc = ce.main(_argv(sesion, "--montaje", "pinzas", "--comparar-con", str(resultados), "--criterio-1-datos", str(RECORTE),
                       "--reporte", str(reporte)))
    assert rc == 0 and visto["timeout"] == 120.0 and visto["salida"] == reporte
    assert {"resultado", "comparacion", "criterio_1", "posiciones", "orden", "cobertura", "intrinsecos"} <= set(visto["estado"])
    assert json.loads(json.dumps(visto["estado"]))["resultado"]["cumple"] is True       # sin default= ni conversion


@pytest.mark.parametrize("quitar,anadir", [
    ("--timeout", []), ("--detector", []), ("--square-mm", []), ("--cols", []), ("--rows", []),
    ("--intrinsecos", []), ("--desde-vistas", []),
    (None, []),                                         # calibrar sin --montaje
    (None, ["--montaje", "pinzas", "--n-control", "0"]),
    ("--cols", ["--cols", "5"]),                        # tablero cuadrado: 5x5
])
def test_main_exige_argumentos_explicitos(sesion, quitar, anadir) -> None:
    argv = _argv(sesion)
    if quitar is not None:
        i = argv.index(quitar)
        fin = i + 1
        while fin < len(argv) and not argv[fin].startswith("--"):
            fin += 1
        del argv[i:fin]
    with pytest.raises(SystemExit) as exc:
        ce.main(argv + anadir)
    assert exc.value.code == 2
