"""El lado de la referencia medido contra el tablero ChArUco (meta 006, fase 7c3 · El tamano de
la referencia medido con el tablero; B55, P76 a P80). Sin camara: escenas sinteticas de
`tablero_sintetico.escena_tablero_y_marker` a 1280 x 960 con la K y la distorsion de gs1, el
tablero registrado (25.95 mm) y una referencia de 100.50 mm a 10 mm a la derecha de su margen.

Lo que el plan pedia y lo que se obtiene (medido en la fase; los umbrales del plan van en las
constantes `PLAN_*` y cada prueba dice el suyo):

- La geometria del modulo es exacta: con las esquinas verdaderas (`projectPoints`), el lado sale
  a <= 1e-9 mm, con distorsion y con altura.
- Sobre el render, el lado medido queda ~0.10 mm POR DEBAJO del dibujado (de -0.04 a -0.13 mm
  en las seis poses), no a <= 0.05 mm como pedia el criterio 1. No es el modulo: el refinado
  `CORNER_REFINE_SUBPIX` del detector del perfil mete cada esquina del cuadro negro ~0.15 px
  hacia dentro sobre un borde suavizado (con las esquinas verdaderas del tablero y las
  detectadas de la referencia sale lo mismo), y la homografia, que extrapola fuera del tablero,
  anade hasta +-0.09 mm. Las pruebas fijan los dos numeros por separado.
- `RADIO_MAX_PX` sale del procedimiento del criterio 4 a 30 cm (382 px). A 40 y 55 cm el error
  por una K desviada pasa de 0.03 mm antes (295 y 315 px), y si el conjunto se corre hacia el
  lado del tablero crece sin que el radio de la referencia lo vea: una prueba lo deja escrito.

Fase 7c4 (P86 a P90), al final del archivo: la referencia ENCIMA del tablero. Las pruebas de la
7c3 siguen con la referencia al lado y por eso apagan la puerta "encerrada" (`AL_LADO`); las de
`decidir` usan la regla de P88 y P89 (sd real, error de la mediana y sesgo).
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

import profiles
from calibration import charuco_board as chb
from calibration import medir_referencia as mr
from calibration.calibrate_extrinsics import leer_intrinsecos
from vision.detection import create_detector, detect

from . import tablero_sintetico as ts
from .conftest import CODIGO_DIR, DATA_DIR, PROFILES_DIR

SHAPE = (1280, 960)
CENTRO = ((SHAPE[0] - 1) / 2.0, (SHAPE[1] - 1) / 2.0)
LADO = 100.50
SEPARACION_MM = 10.0                       # de la placa de la referencia al margen del tablero
T = chb.leer_tablero_charuco(DATA_DIR / "tablero_charuco.yaml")
IDS = np.arange(T.esquinas_interiores)
# Seis poses con el conjunto centrado: 30, 40 y 55 cm, de frente e inclinado 20-30 grados.
POSES = [((0.0, 0.0, 0.0), 300.0), ((0.35, 0.0, 0.0), 300.0), ((0.0, 0.0, 0.0), 400.0),
         ((0.3, -0.3, 0.0), 400.0), ((0.0, 0.0, 0.0), 550.0), ((0.4, 0.35, -0.1), 550.0)]
POSE_RUIDO = ((0.0, 0.0, 0.0), 400.0)
RUIDO_SD, N_RUIDO = 3.0, 30
N_OTROS = 6                                # frames con ruido de los lados de 99.80 y 101.00 (el plan decia 30: el tiempo)
DESVIO_K = (11.0, 11.0, -9.5, -7.3)        # fx, fy, cx, cy: la K "de hoy" del diagnostico frente a la del repo
AL_LADO = -math.inf                        # fase 7c4: la referencia al lado del tablero (la geometria de la 7c3), sin la puerta "encerrada"

# Los umbrales que pedia el plan (criterios 1 y 2) y los que se obtienen sobre el render.
PLAN_FRAME_MM, PLAN_MEDIANA_MM, PLAN_LADO_MM = 0.05, 0.03, 0.08
SESGO_DETECTOR_MM = (-0.15, -0.06)         # ref detectada, tablero verdadero: -0.097 a -0.120
MAX_ERROR_TABLERO_MM = 0.10                # ref verdadera, tablero detectado: hasta +0.083 (55 cm de frente)
MAX_FRAME_MM, MAX_LADO_MM = 0.16, 0.19     # obtenido: 0.133 y 0.162
MEDIANA_MM = (-0.14, -0.06)                # obtenido: -0.105


# ----------------------------------------------------------------------------
# Lo comun
# ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gs1() -> dict:
    return leer_intrinsecos(DATA_DIR / "intrinsecos_gs1_1280x960.yml")


@pytest.fixture(scope="module")
def detectores():
    cfg = profiles.load(PROFILES_DIR / "tracker_config_gs1.yaml")
    with contextlib.redirect_stdout(io.StringIO()):
        det_ref = create_detector(cfg["markers"])
    return det_ref, chb.detector(T), int(profiles.reference_marker(cfg["markers"]["list"])["id"])


def _x0(lado: float = LADO) -> float:
    return T.ancho_mm + ts.TABLERO_MARGEN_MM + SEPARACION_MM + ts.REF_MARGEN_MM


def _y0(lado: float = LADO) -> float:
    return (T.alto_mm - lado) / 2.0


def _pose_conjunto(K, rvec, z_mm: float, lado: float = LADO, corrido_px=(0.0, 0.0)) -> np.ndarray:
    """tvec que pone el centro del conjunto (tablero + referencia con sus margenes) en el centro
    de la imagen, a `z_mm`, y despues lo corre `corrido_px` en la imagen."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))
    c = np.array([(-ts.TABLERO_MARGEN_MM + _x0(lado) + lado + ts.REF_MARGEN_MM) / 2.0, T.alto_mm / 2.0, 0.0])
    u, v = CENTRO[0] + corrido_px[0], CENTRO[1] + corrido_px[1]
    return np.array([(u - K[0, 2]) / K[0, 0] * z_mm, (v - K[1, 2]) / K[1, 1] * z_mm, z_mm]) - R @ c


def _exactos(K, dist, rvec, tvec, lado: float = LADO, altura: float = 0.0):
    """Las esquinas verdaderas del tablero (48, 2) y de la referencia (4, 2), por `projectPoints`."""
    rv, tv = np.asarray(rvec, dtype=np.float64), np.asarray(tvec, dtype=np.float64)
    d = np.zeros(5) if dist is None else dist
    tab = cv2.projectPoints(chb.puntos_objeto(T, IDS).astype(np.float64), rv, tv, K, d)[0].reshape(-1, 2)
    x0, y0 = _x0(lado), _y0(lado)
    cuadro = np.array([[x0, y0, -altura], [x0 + lado, y0, -altura], [x0 + lado, y0 + lado, -altura], [x0, y0 + lado, -altura]])
    return tab, cv2.projectPoints(cuadro, rv, tv, K, d)[0].reshape(-1, 2)


def _k_desviada(K) -> np.ndarray:
    Kd = K.copy()
    Kd[0, 0] += DESVIO_K[0]
    Kd[1, 1] += DESVIO_K[1]
    Kd[0, 2] += DESVIO_K[2]
    Kd[1, 2] += DESVIO_K[3]
    return Kd


def _escena(gs1, rvec, z, lado=LADO, altura=0.0, corrido_px=(0.0, 0.0)):
    tv = _pose_conjunto(gs1["K"], rvec, z, lado, corrido_px)
    img, esq = ts.escena_tablero_y_marker(T, gs1["K"], gs1["dist"], rvec, tv, lado, _x0(lado), _y0(lado), altura, SHAPE)
    return img, esq, tv


def _medir(img, detectores, gs1, altura=0.0, K=None, radio=1e9) -> dict:
    det_ref, det_tab, ref_id = detectores
    return mr.medir_frame(img, det_ref, ref_id, det_tab, T, gs1["K"] if K is None else K, gs1["dist"], altura,
                          mr.MIN_ESQUINAS, radio, LADO, min_encierro_mm=AL_LADO)


class _Ruido:
    """Ruido gaussiano de sd `RUIDO_SD` niveles de gris: un campo por semilla, desplazado al azar
    en cada frame (otra realizacion en cada pixel sin generar 1.2 millones de numeros por frame)."""

    def __init__(self, semilla: int) -> None:
        self.rng = np.random.default_rng(semilla)
        self.campo = None

    def __call__(self, base: np.ndarray) -> np.ndarray:
        if self.campo is None:
            self.campo = self.rng.standard_normal(base.shape, dtype=np.float32) * np.float32(RUIDO_SD)
        dy, dx = (int(v) for v in self.rng.integers(0, base.shape))
        return np.clip(base.astype(np.float32) + np.roll(self.campo, (dy, dx), axis=(0, 1)), 0, 255).astype(np.uint8)


@pytest.fixture(scope="module")
def centradas(gs1, detectores) -> list[dict]:
    """Las seis escenas del criterio 1, sin ruido, con lo que mide el modulo en cada una."""
    out = []
    for rv, z in POSES:
        img, esq, tv = _escena(gs1, rv, z)
        out.append({"rv": rv, "z": z, "tv": tv, "img": img, "esq": esq, "f": _medir(img, detectores, gs1, radio=mr.RADIO_MAX_PX)})
    return out


def _perfil_temporal(dir_: Path, nombre: str, size_mm: str = "99.8", con_k: bool = True) -> Path:
    """Una copia del perfil gs1 del repo en `dir_`, con la ruta de los intrinsecos absoluta."""
    texto = (PROFILES_DIR / "tracker_config_gs1.yaml").read_text(encoding="utf-8")
    viejo_k, viejo_lado = "calibration_file: data/intrinsecos_gs1_1280x960.yml", "size_mm: 99.8"
    assert texto.count(viejo_k) == 1 and texto.count(viejo_lado) == 1
    nuevo_k = f"calibration_file: {(DATA_DIR / 'intrinsecos_gs1_1280x960.yml').as_posix()}" if con_k else "calibration_file:"
    ruta = dir_ / nombre
    ruta.write_text(texto.replace(viejo_k, nuevo_k).replace(viejo_lado, f"size_mm: {size_mm}"), encoding="utf-8", newline="\n")
    return ruta


def _argv(salida: Path, camaras: list[tuple[str, Path, Path]], timeout: str = "300") -> list[str]:
    a = ["--tablero", str(DATA_DIR / "tablero_charuco.yaml")]
    for etiqueta, perfil, carpeta in camaras:
        a += ["--camara", etiqueta, str(perfil), str(carpeta)]
    return a + ["--altura-mm", "0", "--u-tablero-mm", "0.14", "--salida", str(salida), "--timeout", timeout]


@pytest.fixture(scope="module")
def corrida(tmp_path_factory, gs1) -> dict:
    """`main` de punta a punta, una vez: dos camaras (dos perfiles temporales con la K de gs1).
    La carpeta de gs1 lleva 30 PNG con ruido de sd 3; la de gs2, 30 copias del mismo frame sin
    ruido (el detector tarda la mitad en un frame limpio: el tiempo de la suite)."""
    raiz = tmp_path_factory.mktemp("medir_referencia")
    base, _esq, _tv = _escena(gs1, *POSE_RUIDO)
    carpetas = {"gs1": raiz / "P9_gs1_frames", "gs2": raiz / "P9_gs2_frames"}
    ruido = _Ruido(11)
    for cam, d in carpetas.items():
        d.mkdir()
        for i in range(N_RUIDO):
            assert cv2.imwrite(str(d / f"frame_{i:04d}.png"), ruido(base) if cam == "gs1" else base)
    perfiles = {cam: _perfil_temporal(raiz, f"{cam}.yaml") for cam in carpetas}
    salida = raiz / "P9_lado.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.MonkeyPatch.context() as mp:
        mp.setattr(mr, "MIN_ENCIERRO_MM", AL_LADO)          # la referencia al lado: la geometria de la 7c3
        rc = mr.main(_argv(salida, [(cam, perfiles[cam], carpetas[cam]) for cam in carpetas]))
    return {"rc": rc, "salida": salida, "texto": buf.getvalue(), "raiz": raiz, "carpetas": carpetas, "perfiles": perfiles,
            "base": base, "datos": json.loads(salida.read_text(encoding="utf-8")) if salida.exists() else None}


# ----------------------------------------------------------------------------
# La geometria, exacta
# ----------------------------------------------------------------------------

def test_puntos_exactos_sin_distorsion_la_homografia_absorbe_la_k() -> None:
    """Criterio 4, final: sobre puntos proyectados exactos y sin distorsion, con cualquier K (la
    que proyecto y otra distinta para medir), el lado sale con error <= 1e-9 mm."""
    rng = np.random.default_rng(1)
    peor = 0.0
    for _ in range(20):
        K = ts.K_de(rng.uniform(500, 1500), rng.uniform(500, 1500), rng.uniform(400, 900), rng.uniform(300, 700))
        otra = ts.K_de(rng.uniform(500, 1500), rng.uniform(500, 1500), rng.uniform(400, 900), rng.uniform(300, 700))
        rv = rng.uniform(-0.5, 0.5, 3)
        tab, ref = _exactos(K, None, rv, _pose_conjunto(K, rv, rng.uniform(300, 600)))
        m = mr.lados_en_plano(ref, tab, IDS, T, otra, None)
        peor = max(peor, float(np.abs(m["lados_mm"] - LADO).max()), float(np.abs(m["diagonales_mm"] - LADO * math.sqrt(2)).max()))
        assert m["residuo_px"] < 1e-6
    assert peor <= 1e-9, peor                                   # obtenido: 1.7e-13


def test_puntos_exactos_con_la_distorsion_de_gs1(gs1) -> None:
    K, dist = gs1["K"], gs1["dist"]
    for rv, z in POSES:
        tab, ref = _exactos(K, dist, rv, _pose_conjunto(K, rv, z))
        m = mr.lados_en_plano(ref, tab, IDS, T, K, dist)
        assert np.abs(m["lados_mm"] - LADO).max() <= 1e-9
        assert np.allclose(m["centro_mm"], [_x0() + LADO / 2, _y0() + LADO / 2], atol=1e-9)
        assert abs(mr.distancia_al_plano(tab, IDS, T, K, dist) - _distancia(rv, _pose_conjunto(K, rv, z))) < 1e-6


def _distancia(rvec, tvec) -> float:
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64).reshape(3, 1))
    return float(abs(R[:, 2] @ np.asarray(tvec, dtype=np.float64)))


def test_lados_en_plano_valida_sus_entradas(gs1) -> None:
    K, dist = gs1["K"], gs1["dist"]
    tab, ref = _exactos(K, dist, (0, 0, 0), _pose_conjunto(K, (0, 0, 0), 400.0))
    with pytest.raises(ValueError, match="4 esquinas del tablero"):
        mr.lados_en_plano(ref, tab[:3], IDS[:3], T, K, dist)
    with pytest.raises(ValueError, match="4 esquinas, no 3"):
        mr.lados_en_plano(ref[:3], tab, IDS, T, K, dist)
    with pytest.raises(ValueError, match="homografia"):         # ocho esquinas de una misma fila: en linea
        mr.lados_en_plano(ref, tab[:8], IDS[:8], T, K, dist)
    with pytest.raises(ValueError, match="4 esquinas del tablero"):
        mr.distancia_al_plano(tab[:3], IDS[:3], T, K, dist)


# ----------------------------------------------------------------------------
# Criterio 1: la exactitud sobre el render, y de donde sale el sesgo
# ----------------------------------------------------------------------------

def test_criterio_1_las_seis_poses_centradas(centradas) -> None:
    """El plan pedia cada frame a <= 0.05 mm de 100.50, la mediana a <= 0.03 y cada lado a <=
    0.08. Se obtiene -0.037 a -0.133 mm (mediana -0.105; lado peor 0.162): el detector ve el
    cuadro negro ~0.10 mm mas pequeno que el dibujado (la prueba siguiente dice por que)."""
    errores = []
    for e in centradas:
        f = e["f"]
        assert f["motivo"] is None, (e["rv"], e["z"], f["motivo"])
        assert f["n_esquinas"] == T.esquinas_interiores and f["radio_px"] <= mr.RADIO_MAX_PX
        assert abs(f["lado_mm"] - LADO) <= MAX_FRAME_MM, (e["rv"], e["z"], f["lado_mm"])
        assert np.abs(np.array(f["lados_mm"]) - LADO).max() <= MAX_LADO_MM
        assert abs(f["d_mm"] - _distancia(e["rv"], e["tv"])) < 1.0 and f["residuo_px"] < 0.1
        errores.append(f["lado_mm"] - LADO)
    assert MEDIANA_MM[0] <= float(np.median(errores)) <= MEDIANA_MM[1], errores
    assert max(abs(x) for x in errores) > PLAN_FRAME_MM          # el umbral del plan NO se cumple: si un dia si, se dice


def test_el_sesgo_es_del_refinado_del_detector_y_no_de_la_geometria(centradas, detectores, gs1) -> None:
    """Las mismas escenas, separando las dos fuentes: (a) la referencia DETECTADA sobre las
    esquinas VERDADERAS del tablero da el sesgo del detector, siempre hacia dentro; (b) la
    referencia VERDADERA sobre el tablero DETECTADO da el error de la homografia."""
    det_ref, det_tab, ref_id = detectores
    K, dist = gs1["K"], gs1["dist"]
    for e in centradas:
        corners, ids = detect(det_ref, e["img"], {ref_id})
        assert ids is not None and len(ids) == 1
        c = np.asarray(corners[0], dtype=np.float64).reshape(4, 2)
        centro = e["esq"].mean(axis=0)
        dentro = [float(np.dot(c[i] - e["esq"][i], (centro - e["esq"][i]) / np.linalg.norm(centro - e["esq"][i]))) for i in range(4)]
        assert 0.05 <= min(dentro) and max(dentro) <= 0.30, dentro      # px hacia dentro, las cuatro esquinas
        tab_verd, _ref = _exactos(K, dist, e["rv"], e["tv"])
        sesgo = float(mr.lados_en_plano(c, tab_verd, IDS, T, K, dist)["lados_mm"].mean() - LADO)
        assert SESGO_DETECTOR_MM[0] <= sesgo <= SESGO_DETECTOR_MM[1], (e["rv"], e["z"], sesgo)
        r = chb.detectar_charuco(e["img"], det_tab, T, mr.MIN_ESQUINAS)
        assert r is not None
        err_tab = float(mr.lados_en_plano(e["esq"], r[0], r[1], T, K, dist)["lados_mm"].mean() - LADO)
        assert abs(err_tab) <= MAX_ERROR_TABLERO_MM, (e["rv"], e["z"], err_tab)


# ----------------------------------------------------------------------------
# Criterio 2: la repetibilidad
# ----------------------------------------------------------------------------

def test_criterio_2_repetibilidad_en_la_carpeta_de_100_50(corrida, detectores, gs1) -> None:
    """30 frames con ruido de sd 3: `sd_frames_mm` <= 0.02 (el del plan). La mediana queda a <=
    0.01 mm de lo que da el mismo frame sin ruido; frente a 100.50, con el sesgo del detector."""
    limpio = _medir(corrida["base"], detectores, gs1)["lado_mm"]
    assert corrida["datos"]["colocaciones"][0]["sd_frames_mm"] > 0.003          # la de gs1 lleva ruido de verdad
    for c in corrida["datos"]["colocaciones"]:
        assert c["n_frames"] == N_RUIDO and c["n_validos"] >= mr.MIN_FRAMES
        assert c["sd_frames_mm"] <= 0.02, c["sd_frames_mm"]
        assert abs(c["lado_mediana_mm"] - limpio) <= 0.01
        assert MEDIANA_MM[0] - 0.02 <= c["lado_mediana_mm"] - LADO <= MEDIANA_MM[1] + 0.02


@pytest.fixture(scope="module")
def otros_lados(gs1, detectores) -> dict:
    out = {}
    for lado in (99.80, 101.00):
        base, _esq, _tv = _escena(gs1, *POSE_RUIDO, lado=lado)
        ruido = _Ruido(int(lado * 100))
        out[lado] = [_medir(ruido(base), detectores, gs1) for _ in range(N_OTROS)]
    return out


def test_criterio_2_el_modulo_no_se_pega_a_un_valor(otros_lados, corrida) -> None:
    """Con lados de 99.80 y de 101.00, lo mismo (con 6 frames cada uno); y las diferencias entre
    las tres medianas son las de los lados dibujados (0.70 y 0.50 mm) a +-0.06: el sesgo del
    detector cambia unas centesimas con el sitio en que cae cada esquina dentro de su pixel."""
    medianas = {LADO: corrida["datos"]["colocaciones"][0]["lado_mediana_mm"]}
    for lado, frames in otros_lados.items():
        validos = np.array([f["lado_mm"] for f in frames if f["motivo"] is None])
        assert len(validos) >= N_OTROS - 1, [f["motivo"] for f in frames]
        assert validos.std(ddof=1) <= 0.02
        medianas[lado] = float(np.median(validos))
        assert MEDIANA_MM[0] - 0.02 <= medianas[lado] - lado <= MEDIANA_MM[1] + 0.02
    assert abs((medianas[LADO] - medianas[99.80]) - 0.70) <= 0.06
    assert abs((medianas[101.00] - medianas[LADO]) - 0.50) <= 0.06


# ----------------------------------------------------------------------------
# Criterio 3: la altura
# ----------------------------------------------------------------------------

def test_corregir_altura_es_la_razon_exacta() -> None:
    lados = np.array([100.0, 100.5, 99.8, 101.25])
    assert np.abs(mr.corregir_altura(lados, 400.0, 1.0) - lados * 399.0 / 400.0).max() <= 1e-12
    assert np.abs(mr.corregir_altura(lados, 400.0, 0.0) - lados).max() == 0.0
    assert np.abs(mr.corregir_altura(lados, 350.0, -2.0) - lados * 352.0 / 350.0).max() <= 1e-12
    for d, h in ((400.0, 400.0), (400.0, -400.0), (10.0, 25.0), (0.0, 0.0)):
        with pytest.raises(ValueError, match="altura"):
            mr.corregir_altura(lados, d, h)


def test_criterio_3_la_altura_con_puntos_exactos_fija_el_signo(gs1) -> None:
    """La referencia 1.0 mm mas cerca de la camara que el tablero (z = -1 en mm del tablero): sin
    corregir sale lado x d / (d - 1); con `altura_mm` = 1.0, exacto, tambien con el plano inclinado."""
    K, dist = gs1["K"], gs1["dist"]
    for rv, z in POSES:
        tv = _pose_conjunto(K, rv, z)
        tab, ref = _exactos(K, dist, rv, tv, altura=1.0)
        d = mr.distancia_al_plano(tab, IDS, T, K, dist)
        lados = mr.lados_en_plano(ref, tab, IDS, T, K, dist)["lados_mm"]
        assert np.abs(lados - LADO * d / (d - 1.0)).max() <= 1e-9
        assert np.abs(mr.corregir_altura(lados, d, 1.0) - LADO).max() <= 1e-9


def test_criterio_3_la_altura_sobre_el_render(gs1, detectores, centradas) -> None:
    """La escena de 40 cm de frente con la referencia pintada 1.0 mm mas alta. Frente a la misma
    escena a la misma altura (que lleva el sesgo del detector): corregida, a <= 0.02 mm; sin
    corregir, +100.50 / d (~ +0.25 mm) a +-0.03 (el del plan). Las esquinas verdaderas que da la
    escena llevan la altura."""
    rv, z = POSES[2]
    misma = centradas[2]["f"]["lado_mm"]
    img, esq, tv = _escena(gs1, rv, z, altura=1.0)
    _tab, ref = _exactos(gs1["K"], gs1["dist"], rv, tv, altura=1.0)
    assert np.abs(esq - ref).max() < 1e-9
    corregida, sin_corregir = _medir(img, detectores, gs1, altura=1.0), _medir(img, detectores, gs1, altura=0.0)
    assert corregida["motivo"] is None and sin_corregir["motivo"] is None
    assert abs(corregida["lado_mm"] - misma) <= 0.02                       # obtenido: 0.0014
    esperado = LADO / corregida["d_mm"]
    assert 0.24 < esperado < 0.26
    assert abs((sin_corregir["lado_mm"] - misma) - esperado) <= 0.03       # obtenido: 0.0016


# ----------------------------------------------------------------------------
# Criterio 4: los intrinsecos y el radio
# ----------------------------------------------------------------------------

def test_criterio_4_k_desviada_con_el_conjunto_centrado(centradas, detectores, gs1) -> None:
    """Las seis escenas medidas con la K desviada (fx y fy +11, cx -9.5, cy -7.3) y la distorsion
    de gs1: el error extra frente a la K exacta <= 0.03 mm (obtenido: de -0.005 a +0.023)."""
    Kd = _k_desviada(gs1["K"])
    for e in centradas:
        g = _medir(e["img"], detectores, gs1, K=Kd)
        assert g["motivo"] is None
        assert abs(g["lado_mm"] - e["f"]["lado_mm"]) <= 0.03, (e["rv"], e["z"], g["lado_mm"] - e["f"]["lado_mm"])


def _cruce(gs1, rv, z, direccion=(1.0, 1.0), umbral=0.03, max_px=300):
    """Corriendo el conjunto de 1 en 1 px en `direccion`, el primer paso en que el error extra por
    la K desviada pasa de `umbral`, sobre puntos exactos: (paso, radio de la referencia, extra)."""
    K, dist, Kd = gs1["K"], gs1["dist"], _k_desviada(gs1["K"])
    for paso in range(max_px):
        tv = _pose_conjunto(K, rv, z, corrido_px=(direccion[0] * paso, direccion[1] * paso))
        tab, ref = _exactos(K, dist, rv, tv)
        extra = float(mr.lados_en_plano(ref, tab, IDS, T, Kd, dist)["lados_mm"].mean()
                      - mr.lados_en_plano(ref, tab, IDS, T, K, dist)["lados_mm"].mean())
        if abs(extra) > umbral:
            return paso, float(np.linalg.norm(ref.mean(axis=0) - np.array(CENTRO))), extra
    return None


def test_criterio_4_radio_max_px_sale_del_procedimiento_a_30_cm(gs1) -> None:
    """`RADIO_MAX_PX`: a 30 cm de frente (la distancia mas corta del criterio 1, donde la
    referencia queda mas lejos del centro), con la referencia corrida hacia la esquina de abajo a
    la derecha, el radio en que el error extra pasa de 0.03 mm, redondeado hacia abajo."""
    paso, radio, extra = _cruce(gs1, *POSES[0])
    assert 5 <= paso <= 30 and 0.03 < extra < 0.035
    assert mr.RADIO_MAX_PX == math.floor(radio), (radio, mr.RADIO_MAX_PX)      # 382.56 -> 382


def test_criterio_4_el_frame_mas_alla_del_radio_sale_descentrada(gs1, detectores) -> None:
    img, _esq, _tv = _escena(gs1, *POSES[0], corrido_px=(40.0, 40.0))
    f = _medir(img, detectores, gs1, radio=mr.RADIO_MAX_PX)
    assert f["motivo"] == "descentrada" and f["radio_px"] > mr.RADIO_MAX_PX
    assert f["lado_mm"] is not None and f["n_esquinas"] == T.esquinas_interiores    # se mide, pero no cuenta
    assert _medir(img, detectores, gs1, radio=1e9)["motivo"] is None


def test_limite_conocido_el_radio_no_cubre_todas_las_distancias_ni_el_lado_del_tablero(gs1) -> None:
    """Lo que `RADIO_MAX_PX` NO garantiza, medido sobre puntos exactos con la K desviada: a 40 y
    55 cm el error extra pasa de 0.03 mm a un radio menor que `RADIO_MAX_PX` (295 y 315 px), y con
    el conjunto corrido 150 px hacia el lado del tablero pasa de 0.05 mm con la referencia MAS
    cerca del centro. Por eso el modulo da tambien `conjunto_px` y la sesion pide centrar."""
    for pose, (lo, hi) in ((POSES[2], (285, 305)), (POSES[4], (305, 325))):
        _paso, radio, _extra = _cruce(gs1, *pose)
        assert lo <= radio <= hi and radio < mr.RADIO_MAX_PX, radio
    K, dist, Kd = gs1["K"], gs1["dist"], _k_desviada(gs1["K"])
    rv, z = POSES[2]
    tv = _pose_conjunto(K, rv, z, corrido_px=(-150.0, 0.0))
    tab, ref = _exactos(K, dist, rv, tv)
    assert tab.min() > 10 and np.linalg.norm(ref.mean(axis=0) - np.array(CENTRO)) < 150
    extra = float(mr.lados_en_plano(ref, tab, IDS, T, Kd, dist)["lados_mm"].mean() - mr.lados_en_plano(ref, tab, IDS, T, K, dist)["lados_mm"].mean())
    assert extra < -0.05, extra


# ----------------------------------------------------------------------------
# Criterio 5: lo que se descarta
# ----------------------------------------------------------------------------

def _descartes(gs1, centradas) -> dict:
    K, dist = gs1["K"], gs1["dist"]
    rv, z, tv = centradas[2]["rv"], centradas[2]["z"], centradas[2]["tv"]
    buena = centradas[2]["img"]
    # una segunda copia del ID 100 (de 40 mm) pintada sobre el fondo, debajo de la referencia
    plano, ppmm = ts.plano_marker(ts.REF_DICCIONARIO, ts.REF_ID, 40.0, 6.0)
    m = (plano.shape[0] - round(40.0 * ppmm)) / 2.0
    R, _ = cv2.Rodrigues(np.asarray(rv, dtype=np.float64).reshape(3, 1))
    tv2 = tv + R @ np.array([_x0() + 20.0, _y0() + LADO + ts.REF_MARGEN_MM + 12.0, 0.0])
    repetida = ts.renderizar_plano(plano, (m, m), ppmm, K, np.asarray(rv, dtype=np.float64), tv2, SHAPE, dist, sobre=buena)
    sin_ref = ts.renderizar_charuco(T, K, rv, tv, SHAPE, dist, ppmm=20.0, margen_mm=ts.TABLERO_MARGEN_MM)
    tapado = buena.copy()                                   # el tablero tapado salvo sus dos ultimas columnas de casillas
    tab, _ref = _exactos(K, dist, rv, tv)
    corte = int(tab.reshape(6, 8, 2)[:, 6, 0].max() + 10)   # 7c4: con MIN_ESQUINAS 10, quedan 6 esquinas en linea
    tapado[:, :corte] = 128
    return {"buena": buena, "repetida": repetida, "sin_ref": sin_ref, "tapado": tapado}


def test_criterio_5_lo_que_se_descarta_no_entra_en_el_resumen(gs1, detectores, centradas, tmp_path) -> None:
    imgs = _descartes(gs1, centradas)
    esperado = {"buena": None, "repetida": "referencia_repetida", "sin_ref": "sin_referencia", "tapado": "sin_tablero"}
    for nombre, motivo in esperado.items():
        f = _medir(imgs[nombre], detectores, gs1, radio=mr.RADIO_MAX_PX)
        assert f["motivo"] == motivo, (nombre, f["motivo"], f["n_esquinas"], f["n_referencias"])
    assert _medir(imgs["repetida"], detectores, gs1)["n_referencias"] == 2
    assert _medir(imgs["tapado"], detectores, gs1)["n_esquinas"] == 0       # quedan 6, en linea: menos de MIN_ESQUINAS
    orden = ["buena", "repetida", "sin_ref", "tapado", "buena"]
    for i, nombre in enumerate(orden):
        assert cv2.imwrite(str(tmp_path / f"frame_{i:04d}.png"), imgs[nombre])
    perfil = profiles.load(PROFILES_DIR / "tracker_config_gs1.yaml")
    r = mr.medir_carpeta(tmp_path, perfil, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX, min_encierro_mm=AL_LADO)
    assert [f["motivo"] for f in r["frames"]] == [esperado[n] for n in orden]
    assert r["n_frames"] == 5 and r["n_validos"] == 2 and r["completo"] is True
    assert r["motivos"] == {"sin_tablero": 1, "sin_referencia": 1, "referencia_repetida": 1, "fuera_del_tablero": 0, "descentrada": 0}
    # Con la puerta "encerrada" (fase 7c4), la referencia al lado del tablero sale fuera_del_tablero.
    con = mr.medir_carpeta(tmp_path, perfil, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX)
    assert [f["motivo"] for f in con["frames"]][0] == "fuera_del_tablero" and con["frames"][0]["encierro_mm"] < -100
    assert abs(r["lado_mediana_mm"] - centradas[2]["f"]["lado_mm"]) < 1e-9 and r["sd_frames_mm"] < 1e-9
    assert len(r["lados_medios_mm"]) == 4 and r["ref_id"] == 100 and r["conjunto_px"] < 40


def test_medir_carpeta_valida_sus_entradas(tmp_path, gs1) -> None:
    perfil = profiles.load(PROFILES_DIR / "tracker_config_gs1.yaml")
    with pytest.raises(ValueError, match="no hay frame_"):
        mr.medir_carpeta(tmp_path, perfil, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX)
    assert cv2.imwrite(str(tmp_path / "frame_0000.png"), np.full((480, 640), 128, np.uint8))
    with pytest.raises(ValueError, match="640 x 480"):
        mr.medir_carpeta(tmp_path, perfil, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX)
    sin_k = {**perfil, "camera": {k: v for k, v in perfil["camera"].items() if k != "calibration_file"}}
    with pytest.raises(ValueError, match="calibration_file"):
        mr.medir_carpeta(tmp_path, sin_k, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX)
    assert cv2.imwrite(str(tmp_path / "frame_0000.png"), np.full((960, 1280, 3), 128, np.uint8))
    with pytest.raises(ValueError, match="gris de 8 bits"):
        mr.medir_carpeta(tmp_path, perfil, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX)


# ----------------------------------------------------------------------------
# Criterio 6: la regla de P77, con tablas hechas a mano
# ----------------------------------------------------------------------------

def _res(mediana: float, n: int = 200, sd: float = 0.15, sesgo: float | None = 0.0) -> dict:
    """Un resumen hecho a mano. Desde la fase 7c4 (P89), la sd por defecto es la real (0.08-0.21 mm) y
    n el de 30 s por colocacion: error de la mediana 1.2533 x 0.15 / raiz(200) = 0.0133 mm."""
    return {"n_validos": n, "sd_frames_mm": sd, "lado_mediana_mm": mediana, "sesgo_mm": sesgo, "angulo_normales_deg": 0.0}


def _decidir(por_camara: dict) -> dict:
    return mr.decidir(por_camara, 99.8, 0.14, mr.MIN_FRAMES, mr.MAX_ERROR_MEDIANA_MM, mr.MAX_DIF_CAMARAS_MM, mr.MAX_SESGO_MM)


def test_criterio_6_decidir_cambia_cuando_se_aparta_mas_que_u() -> None:
    d = _decidir({"gs1.yaml": [_res(100.52)], "gs2.yaml": [_res(100.44)]})
    assert d["valida"] is True and d["motivo"] is None
    assert d["valor_mm"] == 100.5 and abs(d["dif_camaras_mm"] - 0.08) < 1e-9
    assert abs(d["u_mm"] - math.sqrt(0.14 ** 2 + 0.04 ** 2)) < 1e-12 and round(d["u_mm"], 3) == 0.146
    assert d["cambiar"] is True


def test_criterio_6_decidir_no_cambia_dentro_de_u() -> None:
    d = _decidir({"gs1.yaml": [_res(99.85)], "gs2.yaml": [_res(99.80)]})
    assert d["valida"] is True and d["valor_mm"] == 99.8 and d["cambiar"] is False
    d = _decidir({"gs1.yaml": [_res(99.95)], "gs2.yaml": [_res(99.90)]})       # 99.9: a 0.1 del nominal, U 0.142
    assert d["valida"] is True and d["valor_mm"] == 99.9 and d["cambiar"] is False


@pytest.mark.parametrize("por_camara,texto", [
    ({"gs1.yaml": [_res(100.52)], "gs2.yaml": [_res(100.21)]}, "difieren 0.310 mm"),
    ({"gs1.yaml": [_res(100.52, n=29)], "gs2.yaml": [_res(100.44)]}, "gs1.yaml, colocacion 1: 29 frames validos"),
    ({"gs1.yaml": [_res(100.52)], "gs2.yaml": [_res(100.44, n=30)]}, "gs2.yaml, colocacion 1: error de la mediana 0.0343 mm (n 30, sd 0.150"),
    ({"gs1.yaml": [_res(100.52, sesgo=0.06)], "gs2.yaml": [_res(100.44)]}, "gs1.yaml, colocacion 1: inclinada: sesgo +0.060"),
    ({"gs1.yaml": [_res(100.52, sesgo=None)], "gs2.yaml": [_res(100.44)]}, "gs1.yaml, colocacion 1: sin sesgo"),
    ({"gs1.yaml": [_res(100.52)]}, "hacen falta dos camaras"),
    ({"gs1.yaml": [_res(100.52), {"n_validos": 0, "sd_frames_mm": None, "lado_mediana_mm": None}], "gs2.yaml": [_res(100.44)]},
     "gs1.yaml, colocacion 2: 0 frames validos"),
])
def test_criterio_6_decidir_no_valida_dice_el_motivo(por_camara, texto) -> None:
    d = _decidir(por_camara)
    assert d["valida"] is False and d["cambiar"] is False and texto in d["motivo"], d["motivo"]


def test_criterio_6_decidir_en_el_limite_y_con_dos_colocaciones() -> None:
    sd_limite = 0.02 * math.sqrt(30) / mr.FACTOR_MEDIANA                                   # error de la mediana 0.02 justo
    d = _decidir({"gs1.yaml": [_res(100.50, n=30, sd=sd_limite, sesgo=-0.05)], "gs2.yaml": [_res(100.20)]})  # 30, 0.02, 0.05 y 0.3
    assert d["valida"] is True, d["motivo"]
    assert _decidir({"gs1.yaml": [_res(100.50, n=200, sd=0.15)], "gs2.yaml": [_res(100.44)]})["valida"] is True     # criterio 5 (7c4)
    d = _decidir({"gs1.yaml": [_res(100.56), _res(100.48)], "gs2.yaml": [_res(100.40), _res(100.48)]})   # P80 a
    assert d["valida"] is True and d["cambiar"] is True
    assert abs(d["por_camara"]["gs1.yaml"]["lado_mm"] - 100.52) < 1e-9 and abs(d["por_camara"]["gs2.yaml"]["lado_mm"] - 100.44) < 1e-9
    assert abs(d["por_camara"]["gs1.yaml"]["dif_colocaciones_mm"] - 0.08) < 1e-9 and d["valor_mm"] == 100.5
    assert _decidir({"gs1.yaml": [_res(100.52)], "gs2.yaml": [_res(100.44)]})["por_camara"]["gs1.yaml"]["dif_colocaciones_mm"] is None
    with pytest.raises(ValueError):
        mr.decidir({}, 99.8, 0.0, 30, 0.02, 0.3, 0.05)


# ----------------------------------------------------------------------------
# Criterio 7: main
# ----------------------------------------------------------------------------

def test_criterio_7_main_codigo_0_y_el_json(corrida) -> None:
    assert corrida["rc"] == mr.EXIT_OK, corrida["texto"]
    d = corrida["datos"]
    assert d["codigo"] == 0 and d["completo"] is True and d["nominal_mm"] == 99.8 and d["ref_id"] == 100
    assert d["altura_mm"] == 0.0 and d["u_tablero_mm"] == 0.14 and d["tablero"]["medido"] is True and d["tablero"]["casilla_mm"] == 25.95
    assert d["criterios"] == {"min_esquinas": 10, "min_encierro_mm": None, "radio_max_px": mr.RADIO_MAX_PX, "min_frames": 30,
                              "max_error_mediana_mm": 0.02, "factor_mediana": 1.2533, "max_sesgo_mm": 0.05,
                              "max_dif_camaras_mm": 0.3}
    assert d["modo"] == "medida" and d["colocacion"] is None
    c0 = d["colocaciones"][0]
    assert c0["error_mediana_mm"] is not None and c0["sesgo_mm"] is not None and c0["lado_nominal_mm"] == 99.8
    assert all(k in c0["frames"][0] for k in mr.CAMPOS_7C4)
    assert [c["etiqueta"] for c in d["colocaciones"]] == ["gs1", "gs2"] and [c["perfil"] for c in d["colocaciones"]] == ["gs1.yaml", "gs2.yaml"]
    assert all(len(c["frames"]) == N_RUIDO and len(c["perfil_sha256"]) == 64 for c in d["colocaciones"])
    dec = d["decision"]
    assert dec["valida"] is True and set(dec["por_camara"]) == {"gs1.yaml", "gs2.yaml"}
    assert dec["dif_camaras_mm"] <= 0.02 and abs(dec["u_mm"] - 0.14) < 1e-3         # el mismo frame, con y sin ruido
    # El sintetico dibuja 100.50 y el detector ve ~100.40: a 0.6 de 99.8, mas que U -> cambiar.
    assert dec["valor_mm"] == 100.4 and dec["cambiar"] is True
    lineas = corrida["texto"].splitlines()
    assert sum(1 for x in lineas if x.startswith("[Lado] ")) == 2 and sum(1 for x in lineas if x.startswith("[Decision] ")) == 1
    assert "cambiar: si" in corrida["texto"]


def test_criterio_7_main_codigo_2_y_nada_escrito(corrida, tmp_path, capsys) -> None:
    carpeta, p1, p2 = corrida["carpetas"]["gs1"], corrida["perfiles"]["gs1"], corrida["perfiles"]["gs2"]
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    otra_forma = tmp_path / "otra_forma"
    otra_forma.mkdir()
    assert cv2.imwrite(str(otra_forma / "frame_0000.png"), np.full((480, 640), 128, np.uint8))
    distinto = _perfil_temporal(tmp_path, "gs2_otro_lado.yaml", size_mm="99.9")
    sin_k = _perfil_temporal(tmp_path, "sin_k.yaml", con_k=False)
    casos = {
        "existe": (_argv(corrida["salida"], [("gs1", p1, carpeta), ("gs2", p2, carpeta)]), "ya existe"),
        "sin_png": (_argv(tmp_path / "a.json", [("gs1", p1, vacia), ("gs2", p2, carpeta)]), "no hay frame_"),
        "no_carpeta": (_argv(tmp_path / "a.json", [("gs1", p1, tmp_path / "no_esta"), ("gs2", p2, carpeta)]), "no hay frame_"),
        "otra_forma": (_argv(tmp_path / "a.json", [("gs1", p1, otra_forma), ("gs2", p2, carpeta)]), "640 x 480"),
        "distinto_lado": (_argv(tmp_path / "a.json", [("gs1", p1, carpeta), ("gs2", distinto, carpeta)]), "size_mm"),
        "sin_k": (_argv(tmp_path / "a.json", [("gs1", sin_k, carpeta), ("gs2", p2, carpeta)]), "calibration_file"),
        "etiqueta_repetida": (_argv(tmp_path / "a.json", [("gs1", p1, carpeta), ("gs1", p2, carpeta)]), "repetidas"),
        "timeout": (_argv(tmp_path / "a.json", [("gs1", p1, carpeta), ("gs2", p2, carpeta)], timeout="0"), "--timeout"),
    }
    antes = corrida["salida"].read_bytes()
    for nombre, (argv, texto) in casos.items():
        assert mr.main(argv) == mr.EXIT_USO, nombre
        assert texto in capsys.readouterr().out, nombre
        assert not (tmp_path / "a.json").exists(), nombre
    assert corrida["salida"].read_bytes() == antes
    nominal = tmp_path / "tablero.json"                      # el tablero sin medir (el de `generar`) no vale: la escala es la casilla
    nominal.write_text(json.dumps({"casillas": [9, 7], "casilla_mm": 26.0, "marcador_mm": 19.5, "diccionario": "DICT_4X4_50"}), encoding="utf-8")
    argv = _argv(tmp_path / "a.json", [("gs1", p1, carpeta), ("gs2", p2, carpeta)])
    argv[1] = str(nominal)
    assert mr.main(argv) == mr.EXIT_USO and "no esta medido" in capsys.readouterr().out and not (tmp_path / "a.json").exists()


def test_criterio_7_main_no_valida_con_una_sola_camara(corrida, tmp_path, capsys, monkeypatch) -> None:
    """Un solo perfil: mide, escribe el json y sale con 1 (no valida), sin cambiar."""
    monkeypatch.setattr(mr, "MIN_ENCIERRO_MM", AL_LADO)
    pocos = tmp_path / "pocos"
    pocos.mkdir()
    for i in range(3):
        (pocos / f"frame_{i:04d}.png").write_bytes((corrida["carpetas"]["gs1"] / f"frame_{i:04d}.png").read_bytes())
    salida = tmp_path / "una.json"
    assert mr.main(_argv(salida, [("gs1", corrida["perfiles"]["gs1"], pocos)])) == mr.EXIT_NO_VALIDA
    d = json.loads(salida.read_text(encoding="utf-8"))
    assert d["codigo"] == 1 and d["decision"]["valida"] is False and d["decision"]["cambiar"] is False
    assert "3 frames validos (minimo 30)" in d["decision"]["motivo"] and "hacen falta dos camaras" in d["decision"]["motivo"]
    assert "[Decision] valida: NO" in capsys.readouterr().out


def test_criterio_7_main_el_tope_da_4_y_escribe_lo_hecho(corrida, tmp_path, monkeypatch, capsys) -> None:
    reloj = iter(range(0, 100000, 10))                       # cada lectura del reloj, 10 s despues
    monkeypatch.setattr(mr, "_reloj", lambda: float(next(reloj)))
    salida = tmp_path / "tope.json"
    carpeta = corrida["carpetas"]["gs1"]
    rc = mr.main(_argv(salida, [("gs1", corrida["perfiles"]["gs1"], carpeta), ("gs2", corrida["perfiles"]["gs2"], carpeta)], timeout="25"))
    assert rc == mr.EXIT_TOPE and "TOPE" in capsys.readouterr().out
    d = json.loads(salida.read_text(encoding="utf-8"))
    assert d["codigo"] == 4 and d["completo"] is False and d["decision"] is None
    assert len(d["colocaciones"]) == 1 and d["colocaciones"][0]["completo"] is False
    assert len(d["colocaciones"][0]["frames"]) == 1 and d["colocaciones"][0]["frames_sin_leer"] == N_RUIDO - 1


def test_medir_carpeta_con_tope_lleva_lo_hecho(corrida) -> None:
    perfil = profiles.load(corrida["perfiles"]["gs1"])
    reloj = iter(range(0, 100000, 10))
    with pytest.raises(TimeoutError) as e:
        mr.medir_carpeta(corrida["carpetas"]["gs1"], perfil, T, 0.0, mr.MIN_ESQUINAS, mr.RADIO_MAX_PX,
                         clock=lambda: float(next(reloj)), tope_s=25.0, min_encierro_mm=AL_LADO)
    assert len(e.value.parcial["frames"]) == 2 and e.value.parcial["n_validos"] == 2 and e.value.parcial["completo"] is False


# ----------------------------------------------------------------------------
# La cadena y el dibujo sintetico
# ----------------------------------------------------------------------------

def test_no_importa_vision_tracking_ni_abre_nada() -> None:
    """Mide lo que ve el detector, no lo que publica el tracker (principio 6): ni `vision.tracking`,
    ni `tracker`, ni `transport`, ni la camara."""
    arbol = ast.parse((CODIGO_DIR / "calibration" / "medir_referencia.py").read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
            modulos.update(f"{nodo.module}.{a.name}" for a in nodo.names)
    prohibidos = [m for m in modulos if m.split(".")[0] in ("tracker", "transport", "camera", "pyigtl")
                  or m.startswith("vision.tracking")]
    assert not prohibidos, prohibidos
    assert "vision.detection" in modulos


def test_plano_marker_y_la_escena(gs1, detectores) -> None:
    det_ref, _det_tab, ref_id = detectores
    plano, ppmm = ts.plano_marker(ts.REF_DICCIONARIO, ts.REF_ID, 100.5, 14.0)
    assert abs(ppmm - 400.0 / 100.5) < 1e-12 and plano.shape[0] == plano.shape[1] == 400 + 2 * math.ceil(14.0 * ppmm)
    assert plano.dtype == np.uint8 and plano[0, 0] == 255
    nitido, _ = ts.plano_marker(ts.REF_DICCIONARIO, ts.REF_ID, 100.5, 14.0, desenfoque_mm=0.0)
    m = (nitido.shape[0] - 400) // 2
    assert nitido[m, m] == 0 and nitido[m - 1, m - 1] == 255 and nitido[m + 399, m + 399] == 0 and nitido[m + 400, m + 400] == 255
    corners, ids = detect(det_ref, plano, {ref_id})
    assert ids is not None and ids.flatten().tolist() == [ref_id]
    assert np.abs(corners[0].reshape(4, 2) - (np.array([[0, 0], [400, 0], [400, 400], [0, 400]]) + m - 0.5)).max() < 1.0
    with pytest.raises(ValueError):
        ts.plano_marker(ts.REF_DICCIONARIO, ts.REF_ID, 0.0, 14.0)
    rv, z = POSES[2]
    tv = _pose_conjunto(gs1["K"], rv, z)
    limpia, esq = ts.escena_tablero_y_marker(T, gs1["K"], gs1["dist"], rv, tv, LADO, _x0(), _y0(), 0.0, SHAPE)
    ruidosa, esq2 = ts.escena_tablero_y_marker(T, gs1["K"], gs1["dist"], rv, tv, LADO, _x0(), _y0(), 0.0, SHAPE,
                                               ruido_sd=RUIDO_SD, rng=np.random.default_rng(3))
    assert limpia.shape == (SHAPE[1], SHAPE[0]) and limpia.dtype == np.uint8 and np.array_equal(esq, esq2)
    dif = ruidosa.astype(np.float64) - limpia.astype(np.float64)
    medio = (limpia > 20) & (limpia < 235)                    # donde el recorte a 0-255 no toca el ruido
    assert 2.7 < dif[medio].std() < 3.3
    _tab, ref = _exactos(gs1["K"], gs1["dist"], rv, tv)
    assert np.abs(esq - ref).max() < 1e-9


# ----------------------------------------------------------------------------
# Fase 7c4 · P9 con la referencia sobre el tablero (P86 a P90)
# ----------------------------------------------------------------------------
# La referencia de 100.50 mm encima del tablero y centrada, su cara 2.8 mm mas alta (P78), con
# el tablero centrado en la imagen. Lo medido en la fase (numeros en el reporte):
# - encima se leen 12 esquinas (las columnas 0 y 7) en las seis poses; encierro 12.5-14.4 mm;
# - el lado encima, a <= 0.004 mm del de la misma referencia al lado en la misma pose;
# - el angulo entre normales, a <= 0.041 grados del dibujado a 15 y 45 grados de vista; DE FRENTE
#   (vista ~3 grados) la pose IPPE de un marker suelto da 0.2-0.45 grados de angulo espurio, pero
#   el sesgo que mete es pequeno porque tan(vista) lo es: por eso la puerta va sobre el sesgo (P88);
# - el sesgo predice el error del lado a +-(20 % + 0.02 mm) a 15 grados; a 45 grados tiene un
#   suelo de ~-0.025 mm con la referencia plana (un angulo espurio de ~0.03 grados del detector),
#   y quitado ese suelo predice a <= 0.01 mm.

ALTURA = 2.8                               # P78: la referencia y el tablero miden los dos 2.8 mm
X0_ENCIMA, Y0_ENCIMA = T.ancho_mm / 2.0 - LADO / 2.0, T.alto_mm / 2.0 - LADO / 2.0
POSES_ENCIMA = [((0.0, 0.0, 0.0), z) for z in (300.0, 400.0, 550.0)] + [((math.radians(30.0), 0.0, 0.0), z) for z in (300.0, 400.0, 550.0)]
VISTAS_C3 = (15.0, 45.0)
INCLINACIONES = (0.0, 0.25, 0.5, 1.0)
PLAN_ANGULO_DEG = 0.05                     # criterio 3: el angulo, a <= 0.05 grados del dibujado
SUELO_45_MM = (-0.035, -0.015)             # obtenido: -0.026 / -0.023 (sin y con ruido)
PLAN_K_ANGULO_DEG, PLAN_K_SESGO_MM = 0.10, 0.03
K_SESGO_45_MM = 0.04                       # obtenido con la K desviada a 45 grados: -0.033 (el plan pedia <= 0.03)


def _pose_tablero_centrado(K, rvec, z: float) -> np.ndarray:
    return ts.pose_charuco_hacia(T, K, np.asarray(rvec, dtype=np.float64), CENTRO, z)


def _medir_encima(img, detectores, gs1, altura=ALTURA, K=None, radio=1e9, encierro=None) -> dict:
    det_ref, det_tab, ref_id = detectores
    return mr.medir_frame(img, det_ref, ref_id, det_tab, T, gs1["K"] if K is None else K, gs1["dist"], altura,
                          mr.MIN_ESQUINAS, radio, LADO, min_encierro_mm=mr.MIN_ENCIERRO_MM if encierro is None else encierro)


def _escena_encima(gs1, rvec, tv, **kw):
    return ts.escena_tablero_y_marker(T, gs1["K"], gs1["dist"], rvec, tv, LADO, X0_ENCIMA, Y0_ENCIMA, ALTURA, SHAPE, **kw)


def test_7c4_la_escena_sin_inclinar_es_la_de_la_7c3_byte_a_byte(gs1) -> None:
    rv = np.zeros(3)
    tv = _pose_tablero_centrado(gs1["K"], rv, 400.0)
    a, ea = _escena_encima(gs1, rv, tv)
    b, eb = _escena_encima(gs1, rv, tv, inclinacion_deg=(0.0, 0.0), giro_deg=0.0)
    assert np.array_equal(a, b) and np.array_equal(ea, eb)
    c, ec = _escena_encima(gs1, rv, tv, giro_deg=360.0)           # el otro camino, con un giro que no gira
    assert np.abs(ec - ea).max() < 1e-6 and np.abs(c.astype(int) - a.astype(int)).max() <= 1
    _d, ed = _escena_encima(gs1, rv, tv, giro_deg=90.0)           # un cuarto de vuelta: la esquina 0 pasa arriba a la derecha
    assert np.abs(ed[0] - ea[1]).max() < 1e-6 and np.abs(ed[1] - ea[2]).max() < 1e-6


@pytest.fixture(scope="module")
def encima(gs1, detectores) -> list[dict]:
    """Criterio 2: las seis poses con la referencia encima y centrada, y la misma referencia al lado
    del tablero en la misma pose del tablero (la del conjunto de la 7c3, que cabe a 30 cm)."""
    out = []
    for rv, z in POSES_ENCIMA:
        tv = _pose_conjunto(gs1["K"], rv, z)
        img, esq = _escena_encima(gs1, rv, tv)
        lado, _e2, _tv = _escena(gs1, rv, z)
        out.append({"rv": rv, "z": z, "tv": tv, "img": img, "esq": esq, "f": _medir_encima(img, detectores, gs1),
                    "al_lado": _medir(lado, detectores, gs1)})
    return out


def test_7c4_criterio_2_encima_se_leen_12_esquinas_y_queda_encerrada(encima) -> None:
    ns = []
    for e in encima:
        f = e["f"]
        assert f["motivo"] is None, (e["rv"], e["z"], f["motivo"], f["n_esquinas"], f["encierro_mm"])
        assert f["encierro_mm"] > mr.MIN_ENCIERRO_MM, f["encierro_mm"]
        ns.append(f["n_esquinas"])
    assert min(ns) == 12 and mr.MIN_ESQUINAS == min(ns) - 2, ns


def test_7c4_criterio_2_el_lado_encima_es_el_de_al_lado(encima, gs1, detectores) -> None:
    """Con `--altura-mm 2.8`, el lado encima frente al de la misma referencia al lado del tablero en
    la misma pose (los dos con el mismo sesgo del detector, P81 a). El plan pedia <= 0.03 mm; sale
    <= 0.03 en cuatro de las seis poses, y 0.055 y 0.031 a 55 cm. El exceso es del lado de "al
    lado": su homografia extrapola (lo que la 7c3 ya midio, hasta +0.083 mm). Para separarlo, cada
    una se compara tambien con su referencia DETECTADA sobre las esquinas VERDADERAS del tablero
    (solo el sesgo del detector): encima, a <= 0.03 mm en las seis; y la
    diferencia encima - al lado la explica la extrapolacion de al lado. Con puntos exactos, encima
    a <= 1e-9 mm de lo dibujado."""
    K, dist = gs1["K"], gs1["dist"]
    det_ref, _det_tab, ref_id = detectores

    def solo_detector(img, rv, tv, altura) -> float:
        corners, ids = detect(det_ref, img, {ref_id})
        assert ids is not None and len(ids) == 1
        tab = cv2.projectPoints(chb.puntos_objeto(T, IDS).astype(np.float64), np.asarray(rv, dtype=np.float64), tv, K, dist)[0].reshape(-1, 2)
        lados = mr.lados_en_plano(np.asarray(corners[0], dtype=np.float64).reshape(4, 2), tab, IDS, T, K, dist)["lados_mm"]
        return float(mr.corregir_altura(lados, mr.distancia_al_plano(tab, IDS, T, K, dist), altura).mean())

    difs, interpolas = [], []
    for e in encima:
        assert e["al_lado"]["motivo"] is None
        dif = e["f"]["lado_mm"] - e["al_lado"]["lado_mm"]
        difs.append(abs(dif))
        extrapola = e["al_lado"]["lado_mm"] - solo_detector(_escena(gs1, e["rv"], e["z"])[0], e["rv"], e["tv"], 0.0)
        interpola = e["f"]["lado_mm"] - solo_detector(e["img"], e["rv"], e["tv"], ALTURA)
        interpolas.append(abs(interpola))
        assert abs(interpola) <= 0.03, (e["rv"], e["z"], interpola)
        assert abs(dif) <= 0.03 + abs(extrapola), (e["rv"], e["z"], dif, extrapola)
        tab = cv2.projectPoints(chb.puntos_objeto(T, IDS).astype(np.float64), np.asarray(e["rv"], dtype=np.float64), e["tv"], K, dist)[0].reshape(-1, 2)
        lados = mr.lados_en_plano(e["esq"], tab, IDS, T, K, dist)["lados_mm"]
        assert np.abs(mr.corregir_altura(lados, mr.distancia_al_plano(tab, IDS, T, K, dist), ALTURA) - LADO).max() <= 1e-9
    assert sum(d <= 0.03 for d in difs) >= 4 and max(difs) <= 0.06, difs
    print(f"[fase 7c4] |encima - al lado| por pose: {[round(d, 4) for d in difs]} mm; |encima - solo el detector|: "
          f"{[round(d, 4) for d in interpolas]} mm")


def test_7c4_criterio_2_corrida_26_mm_a_lo_alto_sale_fuera_del_tablero(gs1, detectores) -> None:
    rv = np.zeros(3)
    tv = _pose_tablero_centrado(gs1["K"], rv, 400.0)
    img, _esq = ts.escena_tablero_y_marker(T, gs1["K"], gs1["dist"], rv, tv, LADO, X0_ENCIMA, Y0_ENCIMA + 26.0, ALTURA, SHAPE)
    f = _medir_encima(img, detectores, gs1)
    assert f["motivo"] == "fuera_del_tablero" and f["encierro_mm"] < 0 and f["lado_mm"] is not None


@pytest.fixture(scope="module")
def inclinadas(gs1, detectores) -> dict:
    """Criterio 3: a 40 cm, con la vista a ~15 y ~45 grados, la referencia inclinada 0, 0.25, 0.5 y
    1.0 grados alrededor de cada eje del tablero: el frame limpio y la mediana de 6 con ruido."""
    out: dict = {}
    for vista in VISTAS_C3:
        rv = np.array([math.radians(vista), 0.0, 0.0])
        tv = _pose_tablero_centrado(gs1["K"], rv, 400.0)
        for eje in ("x", "y"):
            for ang in INCLINACIONES:
                if ang == 0.0 and eje == "y":
                    out[(vista, "y", 0.0)] = out[(vista, "x", 0.0)]
                    continue
                img, _esq = _escena_encima(gs1, rv, tv, inclinacion_deg=(ang, 0.0) if eje == "x" else (0.0, ang))
                ruido = _Ruido(int(vista * 100 + ang * 10) + (0 if eje == "x" else 7))
                fs = [_medir_encima(ruido(img), detectores, gs1) for _ in range(6)]
                out[(vista, eje, ang)] = {"img": img, "f": _medir_encima(img, detectores, gs1),
                                          "angulo": float(np.median([g["angulo_normales_deg"] for g in fs])),
                                          "sesgo": float(np.median([g["sesgo_mm"] for g in fs]))}
        out[(vista, "K")] = _medir_encima(out[(vista, "x", 0.0)]["img"], detectores, gs1, K=_k_desviada(gs1["K"]))
    return out


def test_7c4_criterio_3_el_angulo_entre_normales(inclinadas) -> None:
    peor = 0.0
    for vista in VISTAS_C3:
        for eje in ("x", "y"):
            for ang in INCLINACIONES:
                r = inclinadas[(vista, eje, ang)]
                assert abs(r["f"]["vista_deg"] - vista) < 1.0
                peor = max(peor, abs(r["angulo"] - ang))
                assert abs(r["angulo"] - ang) <= PLAN_ANGULO_DEG, (vista, eje, ang, r["angulo"])
    print(f"[fase 7c4] angulo entre normales: peor {peor:.3f} grados del dibujado")


def test_7c4_criterio_3_el_sesgo_predice_el_error_del_lado(inclinadas) -> None:
    """A 15 grados, a +-(20 % + 0.02 mm), como pedia el plan. A 45, con la referencia plana el sesgo
    no es 0 sino ~-0.025 mm (el suelo); el plan no se cumple ahi por 0.003-0.007 mm, y quitado el
    suelo predice a +-(20 % + 0.02) (obtenido: <= 0.009 mm)."""
    for vista in VISTAS_C3:
        cero = inclinadas[(vista, "x", 0.0)]
        if vista == 45.0:
            assert SUELO_45_MM[0] <= cero["sesgo"] <= SUELO_45_MM[1], cero["sesgo"]
            assert abs(cero["sesgo"]) > 0.02                                   # el plan no se cumple a 0 grados: si un dia si, se dice
        suelo = cero["sesgo"] if vista == 45.0 else 0.0
        for eje in ("x", "y"):
            for ang in INCLINACIONES:
                r = inclinadas[(vista, eje, ang)]
                error = r["f"]["lado_mm"] - cero["f"]["lado_mm"]
                assert abs(r["sesgo"] - suelo - error) <= 0.2 * abs(error) + 0.02, (vista, eje, ang, r["sesgo"], error)


def test_7c4_criterio_3_decidir_para_la_inclinada_y_deja_la_plana(inclinadas) -> None:
    def res(r):
        return {"n_validos": 200, "sd_frames_mm": 0.15, "lado_mediana_mm": r["f"]["lado_mm"], "sesgo_mm": r["sesgo"],
                "angulo_normales_deg": r["angulo"]}
    plana, inclinada = res(inclinadas[(45.0, "x", 0.0)]), res(inclinadas[(45.0, "x", 1.0)])
    assert _decidir({"gs1.yaml": [plana], "gs2.yaml": [plana]})["valida"] is True
    d = _decidir({"gs1.yaml": [inclinada], "gs2.yaml": [plana]})
    assert d["valida"] is False and "colocacion 1: inclinada: sesgo -0.8" in d["motivo"], d["motivo"]


def test_7c4_criterio_3_con_la_k_desviada(inclinadas) -> None:
    """La referencia plana con la K desviada de la 7c3: el angulo <= 0.10 grados y el sesgo <= 0.03 mm
    (el plan). A 45 grados el sesgo sale -0.033: con esa K la puerta no es fiable a 45 grados por
    0.003 mm; P9 va con los intrinsecos de la 7e."""
    for vista in VISTAS_C3:
        g = inclinadas[(vista, "K")]
        assert g["motivo"] is None and abs(g["angulo_normales_deg"]) <= PLAN_K_ANGULO_DEG, (vista, g["angulo_normales_deg"])
        assert abs(g["sesgo_mm"]) <= (PLAN_K_SESGO_MM if vista == 15.0 else K_SESGO_45_MM), (vista, g["sesgo_mm"])
    assert abs(inclinadas[(45.0, "K")]["sesgo_mm"]) > PLAN_K_SESGO_MM          # el plan no se cumple a 45: si un dia si, se dice


def test_7c4_aspecto_propio_pose_referencia_y_encierro(gs1) -> None:
    K = gs1["K"]
    cuadrado = cv2.projectPoints(np.array([[-50.0, 50, 0], [50, 50, 0], [50, -50, 0], [-50, -50, 0]]), np.array([0.3, -0.2, 0.1]),
                                 np.array([10.0, -5.0, 400.0]), K, None)[0].reshape(4, 2)
    razon, angulo = mr.aspecto_propio(cuadrado, K, None)
    assert abs(razon - 1.0) <= 1e-6 and abs(angulo - 90.0) <= 1e-4
    R, tv, r = mr.pose_referencia(cuadrado, 100.0, K, None)
    assert np.abs(tv - [10.0, -5.0, 400.0]).max() < 1e-6 and r > 1.0
    for malo, texto in (((cuadrado[:3], 100.0), "4 esquinas"), ((cuadrado, 0.0), "lado_mm")):
        with pytest.raises(ValueError, match=texto):
            mr.pose_referencia(malo[0], malo[1], K, None)
    ids = np.array([0, 7, 40, 47])                       # las cuatro esquinas de los extremos: la envolvente es su rectangulo
    p0 = chb.puntos_objeto(T, ids)[:, :2]
    x0, y0, x1, y1 = p0[:, 0].min(), p0[:, 1].min(), p0[:, 0].max(), p0[:, 1].max()
    dentro = np.array([[x0 + 8, y0 + 6], [x1 - 9, y0 + 6], [x1 - 9, y1 - 7], [x0 + 8, y1 - 7]], dtype=np.float64)
    assert abs(mr.encierro_mm(dentro, ids, T) - 6.0) < 1e-3
    assert abs(mr.encierro_mm(dentro + [0.0, -10.0], ids, T) - (-4.0)) < 1e-3
    with pytest.raises(ValueError, match=">= 3"):
        mr.encierro_mm(dentro, ids[:2], T)


def test_7c4_criterio_4_el_ruido_parecido_al_real(gs1, detectores) -> None:
    """`ruido_esquinas` sobre puntos exactos en la geometria de gs1_d de P9 (al lado, ~46 grados de
    vista, ~470 mm): la sd del lado en 200 tiradas, entre 0.07 y 0.25 mm (la real, 0.084). Con ese
    ruido, encima a 40 cm de frente: la sd y el error de la mediana con n = 200 (<= 0.02 mm)."""
    K, dist = gs1["K"], gs1["dist"]
    rng = np.random.default_rng(7)

    def sd_lado(rv, tv, ids, x0, y0, altura) -> float:
        tab = cv2.projectPoints(chb.puntos_objeto(T, ids).astype(np.float64), rv, tv, K, dist)[0].reshape(-1, 2)
        cuadro = np.array([[x0, y0, -altura], [x0 + LADO, y0, -altura], [x0 + LADO, y0 + LADO, -altura], [x0, y0 + LADO, -altura]])
        ref = cv2.projectPoints(cuadro, rv, tv, K, dist)[0].reshape(-1, 2)
        d = mr.distancia_al_plano(tab, ids, T, K, dist)
        lados = [mr.corregir_altura(mr.lados_en_plano(ts.ruido_esquinas(ref, ts.RUIDO_REFERENCIA_PX, rng),
                                                      ts.ruido_esquinas(tab, ts.RUIDO_TABLERO_PX, rng), ids, T, K, dist)["lados_mm"],
                                    d, altura).mean() for _ in range(200)]
        return float(np.std(lados, ddof=1))

    rv = np.array([math.radians(45.8), 0.0, 0.0])
    al_lado = sd_lado(rv, _pose_conjunto(K, rv, 470.0), IDS, _x0(), _y0(), 0.0)
    assert 0.07 <= al_lado <= 0.25, al_lado                                     # obtenido: 0.096
    rv0 = np.zeros(3)
    tv0 = _pose_tablero_centrado(K, rv0, 400.0)
    img, _esq = _escena_encima(gs1, rv0, tv0)
    r = chb.detectar_charuco(img, detectores[1], T, 1)
    assert r is not None and r[1].tolist() == [0, 7, 8, 15, 16, 23, 24, 31, 32, 39, 40, 47]
    sd_encima = sd_lado(rv0, tv0, r[1], X0_ENCIMA, Y0_ENCIMA, ALTURA)
    err = mr.error_mediana(sd_encima, 200)
    print(f"[fase 7c4] ruido {ts.RUIDO_TABLERO_PX} / {ts.RUIDO_REFERENCIA_PX} px: sd del lado al lado (gs1_d) {al_lado:.3f} mm; "
          f"encima a 40 cm {sd_encima:.3f} mm, error de la mediana con n 200 {err:.4f} mm")
    assert sd_encima < al_lado and err <= mr.MAX_ERROR_MEDIANA_MM                # obtenido: 0.036 y 0.0032
    assert mr.error_mediana(None, 200) is None and mr.error_mediana(0.1, 1) is None
    assert abs(mr.error_mediana(0.15, 200) - 0.01329) < 1e-5


@pytest.fixture(scope="module")
def colocaciones(tmp_path_factory, gs1) -> dict:
    """Criterio 6: carpetas de 3 PNG iguales de cuatro escenas encima (a 40 cm): plana de frente,
    plana girada un cuarto de vuelta, y plana e inclinada 1.0 grado con la vista a 45 grados."""
    raiz = tmp_path_factory.mktemp("colocacion")
    escenas = {}
    rv0 = np.zeros(3)
    tv0 = _pose_tablero_centrado(gs1["K"], rv0, 400.0)
    escenas["plana"] = _escena_encima(gs1, rv0, tv0)[0]
    escenas["girada"] = _escena_encima(gs1, rv0, tv0, giro_deg=90.0)[0]
    rv45 = np.array([math.radians(45.0), 0.0, 0.0])
    escenas["inclinada"] = _escena_encima(gs1, rv45, _pose_tablero_centrado(gs1["K"], rv45, 400.0), inclinacion_deg=(1.0, 0.0))[0]
    carpetas = {}
    for nombre, img in escenas.items():
        d = raiz / f"P9_{nombre}_frames"
        d.mkdir()
        for i in range(3):
            assert cv2.imwrite(str(d / f"frame_{i:04d}.png"), img)
        carpetas[nombre] = d
    return {"raiz": raiz, "carpetas": carpetas, "perfil": _perfil_temporal(raiz, "gs1.yaml")}


def _argv_colocacion(salida: Path, camaras, altura: str = "2.8") -> list[str]:
    a = _argv(salida, camaras, timeout="60") + ["--colocacion"]
    a[a.index("--altura-mm") + 1] = altura
    return a


def test_7c4_criterio_6_main_colocacion(colocaciones, tmp_path, capsys) -> None:
    perfil, c = colocaciones["perfil"], colocaciones["carpetas"]
    rcs, lineas, datos = {}, {}, {}
    for nombre in ("plana", "girada", "inclinada"):
        salida = tmp_path / f"{nombre}.json"
        rcs[nombre] = mr.main(_argv_colocacion(salida, [("gs1_a", perfil, c[nombre])]))
        lineas[nombre] = [x for x in capsys.readouterr().out.splitlines() if x.startswith("[Colocacion] ")]
        datos[nombre] = json.loads(salida.read_text(encoding="utf-8"))
    assert rcs == {"plana": 0, "girada": 0, "inclinada": 1}, (rcs, lineas)
    assert all(len(v) == 1 for v in lineas.values())
    assert "giro 0 grados" in lineas["plana"][0] and lineas["plana"][0].endswith("vale")
    assert "giro 90 grados" in lineas["girada"][0] and "esquinas 12" in lineas["girada"][0]
    assert "NO VALE: inclinada: sesgo -0.8" in lineas["inclinada"][0], lineas["inclinada"]
    d = datos["plana"]
    assert d["modo"] == "colocacion" and d["decision"] is None and d["codigo"] == 0
    col = d["colocacion"]
    assert col["vale"] is True and col["giro_90"] == 0 and col["n_esquinas"] == 12 and col["encierro_mm"] > mr.MIN_ENCIERRO_MM
    assert np.allclose(col["centro_rel_mm"], [0.0, 0.0], atol=0.5) and col["conjunto_px"] < 30
    assert datos["girada"]["colocacion"]["giro_90"] == 90
    assert datos["inclinada"]["colocacion"]["vale"] is False and datos["inclinada"]["codigo"] == 1
    salida = tmp_path / "dos.json"
    assert mr.main(_argv_colocacion(salida, [("gs1_a", perfil, c["plana"]), ("gs1_b", perfil, c["girada"])])) == mr.EXIT_USO
    assert "un solo --camara" in capsys.readouterr().out and not salida.exists()


def test_7c4_criterio_6_la_medida_con_dos_colocaciones_encima(colocaciones, tmp_path, capsys) -> None:
    """Sin `--colocacion`, las lineas `[Lado]` traen normales, sesgo y error de la mediana; con 3
    frames por colocacion no vale (minimo 30) y sale con 1."""
    perfil, c = colocaciones["perfil"], colocaciones["carpetas"]
    salida = tmp_path / "medida.json"
    argv = _argv(salida, [("gs1_a", perfil, c["plana"]), ("gs1_b", perfil, c["girada"])])
    argv[argv.index("--altura-mm") + 1] = "2.8"
    assert mr.main(argv) == mr.EXIT_NO_VALIDA
    out = capsys.readouterr().out
    lados = [x for x in out.splitlines() if x.startswith("[Lado] ")]
    assert len(lados) == 2 and all("normales" in x and "sesgo" in x and "error de la mediana" in x for x in lados)
    d = json.loads(salida.read_text(encoding="utf-8"))
    assert [round(x["giro_deg"]) for x in d["colocaciones"]] == [0, 90]
    assert d["decision"]["max_sesgo_mm"] == 0.05 and d["decision"]["max_error_mediana_mm"] == 0.02
