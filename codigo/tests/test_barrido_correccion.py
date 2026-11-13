"""diagnostics.barrido_correccion sin camara (meta 006, fase 7d2 · Los IDs falsos del tablero en el detector del
tracker; B39, P66, P69). Los siete puntos del criterio de la parte sin camara (`plan.md`):

  1. `bits_efectivos` da 7, 6, 5, 4, 3, 2 para `TASAS` y es lo que corrige OpenCV; `detector_con_tasa` solo cambia
     `errorCorrectionRate` y no toca el dict de entrada.
  2. `barrer` sobre las vistas del punto 8 de la 7d: con 0.60 hay fantasmas; con 0.30, ninguno. Sobre 20 poses de
     la referencia, las esquinas leidas con 0.60 y con 0.30 son las mismas.
  3. `elegir` (la regla de P69, con P74: 0 fantasmas tambien en los frames de la referencia sola) con tablas hechas
     a mano.
  4. `perfil_con_tasa` sobre los dos perfiles del repo.
  5. «No cambio» con frames reales: el replay de deteccion de gs1 y gs2 con cada tasa.
  6. `main`: sus codigos (2, 4, 0 y 1) y lo que escribe.
  7. La regla mide el detector: el modulo no importa `vision.tracking`, y dos copias del ID 100 cuentan como repetido.

Las escenas salen de `escenas_b39.py`. Ninguna prueba abre una camara ni toca los perfiles del repo.
"""
from __future__ import annotations

import ast
import copy
import itertools
import json
import types
from pathlib import Path

import cv2
import numpy as np
import pytest

import profiles
from diagnostics import barrido_correccion as bc
from vision.detection import create_detector, get_dictionary

from . import escenas_b39 as esc
from . import replay_util
from .conftest import CODIGO_DIR, PROFILES_DIR, TESTS_DATA_DIR
from .test_charuco_board import VISTAS_8, vista

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"
GS2 = PROFILES_DIR / "tracker_config_gs2.yaml"
CAMERAS = ("gs1", "gs2")
DICC = "DICT_ARUCO_MIP_36h12"
ID_REF = esc.ID_REF


def _markers(perfil: Path = GS1) -> dict:
    return profiles.load(perfil)["markers"]


def _congelado(cam: str) -> Path:
    return TESTS_DATA_DIR / f"marker0_{cam}_perfil.yaml"


# ----------------------------------------------------------------------------
# 1. Los bits y el detector
# ----------------------------------------------------------------------------

def test_las_constantes_son_las_del_plan() -> None:
    assert bc.TASAS == (0.60, 0.50, 0.45, 0.40, 0.30, 0.20) and bc.BASE == 0.60 and bc.PERDIDA_MAX == 0.01
    assert bc.CATEGORIAS == ("referencia", "tablero", "tablero_con_referencia")
    assert [bc.clave_tasa(t) for t in bc.TASAS] == ["0.60", "0.50", "0.45", "0.40", "0.30", "0.20"]


def test_bits_efectivos_da_7_6_5_4_3_2() -> None:
    assert [bc.bits_efectivos(DICC, t) for t in bc.TASAS] == [7, 6, 5, 4, 3, 2]
    assert bc.bits_efectivos(DICC, 1.0) == 12 == get_dictionary(DICC).maxCorrectionBits
    for mala in (0, 0.0, 1.1, -0.3, True, "0.3", None, float("nan")):
        with pytest.raises(ValueError, match="la tasa"):
            bc.bits_efectivos(DICC, mala)
    with pytest.raises(ValueError, match="no disponible"):
        bc.bits_efectivos("DICT_NO_EXISTE", 0.3)


@pytest.mark.parametrize("tasa", [*bc.TASAS, 0.35, 0.25])
def test_bits_efectivos_es_lo_que_corrige_opencv(tasa: float) -> None:
    """`Dictionary.identify(bits, tasa)` reconoce el ID 100 con k bits cambiados si y solo si
    k <= `bits_efectivos`: OpenCV trunca `maxCorrectionBits * tasa` igual que la funcion."""
    d = get_dictionary(DICC)
    limpio = cv2.aruco.Dictionary.getBitsFromByteList(d.bytesList[ID_REF:ID_REF + 1], d.markerSize)
    rng = np.random.default_rng(0)
    bits = bc.bits_efectivos(DICC, tasa)
    for k in range(0, 10):
        for _ in range(400):                                # k bits cambiados sin acercarse a otro ID
            b = limpio.copy()
            for i in rng.choice(36, size=k, replace=False):
                b[i // 6, i % 6] ^= 1
            if min(d.getDistanceToId(b, m, True) for m in range(250) if m != ID_REF) > 8:
                break
        else:
            pytest.fail(f"sin un patron de {k} bits cambiados lejos de los demas IDs")
        ok, idx, _rot = d.identify(b, tasa)
        assert bool(ok) is (k <= bits), (tasa, k, bits)
        assert not ok or int(idx) == ID_REF


@pytest.mark.parametrize("perfil", [GS1, GS2], ids=lambda p: p.name)
def test_detector_con_tasa_solo_cambia_la_tasa(perfil: Path, capsys) -> None:
    cfg = _markers(perfil)
    # Desde el cierre de la 7d2 (2026-11-12, P84) los perfiles fijan 0.3; sin la clave, el valor por defecto de OpenCV.
    assert cfg["detector"]["error_correction_rate"] == 0.3
    sin_tasa = copy.deepcopy(cfg)
    sin_tasa["detector"].pop("error_correction_rate")
    antes = copy.deepcopy(cfg)
    capsys.readouterr()
    assert create_detector(cfg).getDetectorParameters().errorCorrectionRate == 0.3
    del_perfil = create_detector(sin_tasa).getDetectorParameters()
    assert del_perfil.errorCorrectionRate == 0.6 == bc.BASE                # el valor por defecto de OpenCV
    capsys.readouterr()
    atributos = [a for a in dir(del_perfil) if not a.startswith("_") and not callable(getattr(del_perfil, a))]
    assert "errorCorrectionRate" in atributos and len(atributos) >= 30
    for tasa in bc.TASAS:
        p = bc.detector_con_tasa(cfg, tasa).getDetectorParameters()
        distintos = [a for a in atributos if getattr(p, a) != getattr(del_perfil, a)]
        assert distintos == ([] if tasa == bc.BASE else ["errorCorrectionRate"]), (tasa, distintos)
        assert p.errorCorrectionRate == tasa
    assert cfg == antes                                                    # el dict de entrada sale igual
    assert capsys.readouterr().out == ""                                   # sin el volcado de create_detector
    with pytest.raises(ValueError, match="la tasa"):
        bc.detector_con_tasa(cfg, 0.0)


# ----------------------------------------------------------------------------
# 2. El barrido sobre las escenas
# ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def barrido_vistas_8() -> dict:
    grupos = {"tablero": ((f"v8_{k}", vista(z, rv)[0]) for k, (z, rv) in enumerate(VISTAS_8))}
    return bc.barrer(grupos, _markers(), ID_REF)


def test_barrer_las_vistas_del_tablero_con_060_da_fantasmas_y_con_030_ninguno(barrido_vistas_8: dict) -> None:
    r = barrido_vistas_8
    assert r["tasas"] == list(bc.TASAS) and r["id_ref"] == ID_REF and r["base"] == bc.BASE
    assert r["bits"] == {"0.60": 7, "0.50": 6, "0.45": 5, "0.40": 4, "0.30": 3, "0.20": 2}
    assert r["diccionario"] == DICC and r["detector"] == _markers()["detector"]
    c = r["categorias"]["tablero"]
    assert c["frames"] == len(VISTAS_8) == 9 and r["categorias"]["referencia"]["frames"] == 0
    f = {k: s["fantasmas"] for k, s in c["por_tasa"].items()}
    base = c["por_tasa"]["0.60"]
    assert f["0.60"] > 0 and base["frames_con_fantasma"] == 9 and len(base["frames_fantasma"]) == 9
    assert base["frames_fantasma"][0] == "v8_0"                            # el informe dice cuales
    assert sum(base["ajenos_por_id"].values()) + base["fantasmas_id_ref"] == f["0.60"]
    assert f["0.30"] == 0 == f["0.20"] and c["por_tasa"]["0.30"]["frames_fantasma"] == []
    assert f["0.60"] >= f["0.50"] >= f["0.45"] >= f["0.40"] >= f["0.30"]   # menos bits, menos fantasmas
    assert all(s["ref_doble"] == 0 and s["perdida"] is None for s in c["por_tasa"].values())
    print(f"[fase 7d2] vistas del punto 8 de la 7d (9, tablero solo), fantasmas por tasa: {f}; con 0.60, "
          f"{base['fantasmas_id_ref']} con el ID {ID_REF}")


def test_barrer_la_referencia_da_las_mismas_esquinas_con_060_y_con_030() -> None:
    r = bc.barrer({"referencia": esc.poses_referencia(20)}, _markers(), ID_REF, tasas=(0.60, 0.30))
    assert r["tasas"] == [0.60, 0.30]
    c = r["categorias"]["referencia"]
    s60, s30 = c["por_tasa"]["0.60"], c["por_tasa"]["0.30"]
    assert c["frames"] == 20 and s60["comunes"] == s30["comunes"] >= 15     # los que leen la referencia con las dos
    assert s30["max_dif_px"] == 0.0 and s30["frames_dif"] == 0             # la tasa no mueve las esquinas
    assert s60["base_lee"] == s30["base_lee"] == s60["ref_una"] and s60["perdidos"] == 0 == s60["ganados"]
    assert s30["perdida"] == s30["perdidos"] / s30["base_lee"]
    assert s30["ref_una"] == s60["ref_una"] - s30["perdidos"] + s30["ganados"]
    print(f"[fase 7d2] 20 poses de la referencia: con 0.60 la leen {s60['ref_una']} (como otro ID, {s60['ajenos']}); con 0.30, "
          f"{s30['ref_una']} (perdidos {s30['perdidos']}, ganados {s30['ganados']}); comunes {s30['comunes']}, dif max "
          f"{s30['max_dif_px']} px")


def test_barrer_mide_la_base_aunque_no_se_pida_y_valida_sus_entradas() -> None:
    cfg = _markers()
    nombre, gris = next(iter(esc.poses_referencia(1)))
    r = bc.barrer({"referencia": [(nombre, gris)]}, cfg, ID_REF, tasas=(0.30,))
    assert r["tasas"] == [0.60, 0.30] and set(r["categorias"]) == set(bc.CATEGORIAS)
    with pytest.raises(ValueError, match="categorias desconocidas"):
        bc.barrer({"otra": []}, cfg, ID_REF)
    with pytest.raises(ValueError, match="repetidas"):
        bc.barrer({"referencia": []}, cfg, ID_REF, tasas=(0.3, 0.30))
    with pytest.raises(ValueError, match="sin tasas"):
        bc.barrer({"referencia": []}, cfg, ID_REF, tasas=())
    with pytest.raises(ValueError, match="no es una imagen en gris"):
        bc.barrer({"referencia": [("bgr", cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR))]}, cfg, ID_REF)


def test_leer_frame_no_aplica_lista_blanca() -> None:
    cfg = _markers()
    det = bc.detector_con_tasa(cfg, bc.BASE)
    _n, gris = next(iter(esc.poses_referencia(1)))
    a = bc.leer_frame(gris, det, ID_REF)
    assert a["n_ref"] == 1 and a["ajenos"] == [] and a["esquinas_ref"][0].shape == (4, 2)
    b = bc.leer_frame(gris, det, 7)                                        # con otro ID de referencia, el 100 es ajeno
    assert b["n_ref"] == 0 and b["ajenos"] == [ID_REF] and b["esquinas_ref"] == []
    c = bc.leer_frame(np.full((480, 640), 128, np.uint8), det, ID_REF)
    assert c == {"n_ref": 0, "esquinas_ref": [], "ajenos": []}


# ----------------------------------------------------------------------------
# 3. La regla de P69, con tablas hechas a mano
# ----------------------------------------------------------------------------

def _celda(frames: int = 0, fantasmas: int = 0, doble: int = 0, base_lee: int = 0, perdidos: int = 0, ganados: int = 0,
           id_ref: int = 0) -> dict:
    s = bc._vacio()
    s.update(frames=frames, fantasmas=fantasmas, frames_con_fantasma=min(frames, fantasmas), fantasmas_id_ref=id_ref,
             ref_doble=doble, base_lee=base_lee, perdidos=perdidos, ganados=ganados,
             perdida=(perdidos / base_lee) if base_lee else None)
    return s


def _tabla(por_tasa: dict, tasas=bc.TASAS) -> dict:
    """Un resultado de `barrer` hecho a mano. `por_tasa[clave][categoria]` son los argumentos de `_celda`; lo que
    no se da queda en una celda limpia de 100 frames (en `referencia`, con 100 leidos por la base)."""
    limpio = {"referencia": dict(frames=100, base_lee=100), "tablero": dict(frames=100),
              "tablero_con_referencia": dict(frames=100, base_lee=100)}
    cats = {cat: {"frames": 100, "por_tasa": {}} for cat in bc.CATEGORIAS}
    for t in tasas:
        k = bc.clave_tasa(t)
        for cat in bc.CATEGORIAS:
            cats[cat]["por_tasa"][k] = _celda(**{**limpio[cat], **por_tasa.get(k, {}).get(cat, {})})
    return {"formato": bc.FORMATO, "id_ref": ID_REF, "base": bc.BASE, "tasas": list(tasas),
            "bits": {bc.clave_tasa(t): bc.bits_efectivos(DICC, t) for t in tasas}, "categorias": cats}


SUCIAS = {"0.60": {"tablero": dict(fantasmas=646)}, "0.50": {"tablero": dict(fantasmas=200)},
          "0.45": {"tablero": dict(fantasmas=41)}}                         # con fantasmas hasta 0.45; de 0.40 abajo, limpias


def test_elegir_la_tasa_mas_alta_que_cumple() -> None:
    elegida, razones = bc.elegir(_tabla(SUCIAS), _tabla(SUCIAS))
    assert elegida == 0.40
    assert len(razones) == len(bc.TASAS) + 1 and razones[-1] == "elegida: 0.40"
    assert [r.split(":")[0] for r in razones[:-1]] == ["0.60 (7 bits)", "0.50 (6 bits)", "0.45 (5 bits)", "0.40 (4 bits)",
                                                       "0.30 (3 bits)", "0.20 (2 bits)"]
    assert "no cumple" in razones[0] and "646 fantasmas" in razones[0] and "reales de 'tablero'" in razones[0]
    assert all(" cumple: 0 fantasmas" in r for r in razones[3:6])          # 0.30 y 0.20 tambien cumplen: gana la mas alta
    # Si la de hoy ya cumple, es la elegida: no hay nada que cambiar.
    assert bc.elegir(_tabla({}), _tabla({}))[0] == 0.60
    # Sin sinteticos, la regla se aplica a los reales y lo dice.
    elegida, razones = bc.elegir(_tabla(SUCIAS), None)
    assert elegida == 0.40 and "sin barrido sintetico" in razones[3]


@pytest.mark.parametrize("donde,cat,celda,trozo", [
    ("real", "tablero", dict(fantasmas=1), "1 fantasmas en 1 de 100 frames reales de 'tablero'"),
    ("real", "tablero_con_referencia", dict(fantasmas=1, base_lee=100), "frames reales de 'tablero_con_referencia'"),
    ("sintetico", "tablero", dict(fantasmas=1, id_ref=1), "frames sinteticos de 'tablero' (1 con el ID de la referencia)"),
    ("sintetico", "tablero_con_referencia", dict(fantasmas=1, base_lee=100), "frames sinteticos de 'tablero_con_referencia'"),
    ("real", "referencia", dict(doble=1, base_lee=100), "dos o mas veces en 1 de 100 frames reales de 'referencia'"),
    ("real", "tablero_con_referencia", dict(doble=1, base_lee=100), "dos o mas veces en 1 de 100 frames reales"),
    ("sintetico", "referencia", dict(doble=1, base_lee=100), "dos o mas veces en 1 de 100 frames sinteticos"),
    # P74: tambien los fantasmas de los frames de la referencia sola.
    ("real", "referencia", dict(fantasmas=1, base_lee=100), "1 fantasmas en 1 de 100 frames reales de 'referencia'"),
    ("sintetico", "referencia", dict(fantasmas=1, base_lee=100), "1 fantasmas en 1 de 100 frames sinteticos de 'referencia'"),
])
def test_un_fantasma_o_un_doble_en_un_solo_frame_descarta_la_tasa(donde: str, cat: str, celda: dict, trozo: str) -> None:
    mala = {**SUCIAS, "0.40": {cat: celda}}
    real, sint = (_tabla(mala), _tabla(SUCIAS)) if donde == "real" else (_tabla(SUCIAS), _tabla(mala))
    elegida, razones = bc.elegir(real, sint)
    assert elegida == 0.30                                                 # 0.40 cae por un solo frame
    assert "0.40 (4 bits): no cumple" in razones[3] and trozo in razones[3]


def test_un_fantasma_en_un_solo_frame_de_la_referencia_sola_descarta_la_tasa() -> None:
    """P74: la regla exige 0 fantasmas en todos los frames, tambien en los de la referencia sola (P5). Un frame de
    10000 con un ID ajeno descarta la tasa aunque la referencia se lea en todos y el tablero este limpio."""
    def con(fantasmas: int, cat: str = "referencia", tasa: str = "0.40") -> tuple:
        t = {**SUCIAS, tasa: {cat: dict(frames=10000, base_lee=10000, fantasmas=fantasmas)}}
        return bc.elegir(_tabla(t), _tabla(SUCIAS))
    elegida, razones = con(1)
    assert elegida == 0.30
    assert razones[3] == ("0.40 (4 bits): no cumple: 1 fantasmas en 1 de 10000 frames reales de 'referencia' "
                          "(0 con el ID de la referencia)")
    assert con(0)[0] == 0.40                                               # sin el fantasma, la misma tabla elige 0.40
    # Tambien con la de hoy: si 0.60 deja un fantasma en un frame de la referencia sola, ya no es la elegida.
    elegida, razones = bc.elegir(_tabla({"0.60": {"referencia": dict(frames=100, base_lee=100, fantasmas=1)}}), _tabla({}))
    assert elegida == 0.50 and "frames reales de 'referencia'" in razones[0]
    # La razon de la que cumple cuenta los frames de las tres categorias, reales y sinteticos (6 x 100).
    assert "cumple: 0 fantasmas en 600 frames (las tres categorias)" in bc.elegir(_tabla({}), _tabla({}))[1][0]
    # Un barrido sintetico sin frames de la referencia sola no falla: esos los da la sesion.
    sint = _tabla({})
    sint["categorias"]["referencia"] = {"frames": 0, "por_tasa": {bc.clave_tasa(t): bc._vacio() for t in bc.TASAS}}
    assert bc.elegir(_tabla({}), sint)[0] == 0.60


def test_la_perdida_de_1_01_por_ciento_descarta_y_la_de_1_00_no() -> None:
    def con_perdida(perdidos: int, base_lee: int):
        t = {**SUCIAS, "0.40": {"referencia": dict(frames=base_lee, base_lee=base_lee, perdidos=perdidos, ganados=3)}}
        return bc.elegir(_tabla(t), _tabla(SUCIAS))
    elegida, razones = con_perdida(100, 10000)                             # 1.00 %
    assert elegida == 0.40 and "perdida 1.00 % (100 de 10000 frames reales; ganados 3)" in razones[3]
    elegida, razones = con_perdida(101, 10000)                             # 1.01 %
    assert elegida == 0.30 and "perdida 1.01 % (101 de 10000 frames reales; ganados 3) > 1.00 %" in razones[3]
    assert con_perdida(1, 100)[0] == 0.40 and con_perdida(2, 100)[0] == 0.30
    # Los ganados no compensan los perdidos: la regla mira lo que deja de leerse.
    t = {**SUCIAS, "0.40": {"referencia": dict(frames=100, base_lee=100, perdidos=2, ganados=50)}}
    assert bc.elegir(_tabla(t), None)[0] == 0.30
    # La perdida sintetica es informativa: no decide.
    sint = {**SUCIAS, "0.40": {"referencia": dict(frames=100, base_lee=100, perdidos=60)}}
    assert bc.elegir(_tabla(SUCIAS), _tabla(sint))[0] == 0.40
    # Otro umbral.
    t = {**SUCIAS, "0.40": {"referencia": dict(frames=1000, base_lee=1000, perdidos=6)}}
    assert bc.elegir(_tabla(t), None, perdida_max=0.005)[0] == 0.30 and bc.elegir(_tabla(t), None, perdida_max=0.006)[0] == 0.40
    with pytest.raises(ValueError, match="perdida_max"):
        bc.elegir(_tabla(t), None, perdida_max=1.0)


def test_si_ninguna_cumple_none_y_una_razon_por_tasa() -> None:
    todas = {bc.clave_tasa(t): {"tablero": dict(fantasmas=1)} for t in bc.TASAS}
    elegida, razones = bc.elegir(_tabla(todas), _tabla({}))
    assert elegida is None and len(razones) == len(bc.TASAS) + 1
    assert all("no cumple" in r for r in razones[:-1]) and razones[-1].startswith("elegida: ninguna")
    # Sin frames reales de una categoria (la sesion con -SinTablero), la regla no se puede comprobar: no elige.
    for cat in bc.CATEGORIAS:
        real = _tabla({})
        real["categorias"][cat] = {"frames": 0, "por_tasa": {bc.clave_tasa(t): bc._vacio() for t in bc.TASAS}}
        elegida, razones = bc.elegir(real, _tabla({}))
        assert elegida is None and all(f"sin frames reales de '{cat}'" in r for r in razones[:-1])
    # La base no lee la referencia en ningun frame: la perdida no se puede medir.
    real = _tabla({bc.clave_tasa(t): {"referencia": dict(frames=50, base_lee=0)} for t in bc.TASAS})
    elegida, razones = bc.elegir(real, None)
    assert elegida is None and "la perdida no se puede medir" in razones[0]
    # El barrido cortado por el tope no elige.
    real = _tabla({})
    real["completo"] = False
    elegida, razones = bc.elegir(real, None)
    assert elegida is None and "se corto por el tope" in razones[0]
    # A los sinteticos les falta una tasa.
    sint = _tabla({})
    del sint["categorias"]["tablero"]["por_tasa"]["0.60"]
    elegida, razones = bc.elegir(_tabla({}), sint)
    assert elegida == 0.50 and "el barrido sintetico no trae la tasa 0.60" in razones[0]
    # Un barrido sintetico sin frames del tablero no comprueba nada: no elige.
    sint = _tabla({})
    sint["categorias"]["tablero"] = {"frames": 0, "por_tasa": {bc.clave_tasa(t): bc._vacio() for t in bc.TASAS}}
    elegida, razones = bc.elegir(_tabla({}), sint)
    assert elegida is None and all("el barrido sintetico no trae frames de 'tablero'" in r for r in razones[:-1])


# ----------------------------------------------------------------------------
# 4. El perfil temporal con la tasa
# ----------------------------------------------------------------------------

def _sin_tasa(cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    cfg["markers"]["detector"].pop("error_correction_rate", None)
    return cfg


@pytest.mark.parametrize("cam", CAMERAS)
def test_perfil_con_tasa_sobre_los_perfiles_del_repo(cam: str, tmp_path: Path) -> None:
    """Desde el cierre de la 7d2 los perfiles del repo ya traen la clave (0.3): la copia la cambia en su linea. La
    copia congelada del replay no la trae: la copia la anade al final del bloque del detector."""
    perfil = PROFILES_DIR / f"tracker_config_{cam}.yaml"
    antes = perfil.read_bytes()
    base = profiles.load(perfil)
    for tasa in (0.30, 0.45):
        salida = tmp_path / f"{perfil.stem}_{bc.clave_tasa(tasa)}.yaml"
        assert bc.perfil_con_tasa(perfil, tasa, salida) == salida
        copia = profiles.load(salida)                                      # carga, con sus intrinsecos y su markers.list
        assert copia["markers"]["detector"]["error_correction_rate"] == tasa
        assert _sin_tasa(copia) == _sin_tasa(base) and (copia == base) is (tasa == 0.30)   # solo difiere esa clave
        assert create_detector(copia["markers"]).getDetectorParameters().errorCorrectionRate == tasa
        assert set(replay_util.profile_diff(perfil, salida)) == (set() if tasa == 0.30 else {"detector"})
        # En el texto: las mismas lineas, y solo la de la clave puede cambiar.
        a, b = antes.decode("utf-8").splitlines(), salida.read_bytes().decode("utf-8").splitlines()
        assert len(b) == len(a) and [x for x, y in zip(a, b) if x != y] == ([] if tasa == 0.30 else ["    error_correction_rate: 0.3"])
        assert f"    error_correction_rate: {tasa:g}" in b
        assert (b"\r\n" in salida.read_bytes()) == (b"\r\n" in antes)       # los fines de linea del base
    assert perfil.read_bytes() == antes                                    # el perfil del repo, sin tocar
    # Sobre la copia congelada, sin la clave: tres lineas de mas (dos de comentario y la clave), al final del detector.
    congelado = _congelado(cam)
    antes_c = congelado.read_bytes()
    for tasa in (0.30, 0.45):
        salida = tmp_path / f"{congelado.stem}_{bc.clave_tasa(tasa)}.yaml"
        assert bc.perfil_con_tasa(congelado, tasa, salida) == salida
        copia = profiles.load(salida)
        assert copia["markers"]["detector"]["error_correction_rate"] == tasa
        assert _sin_tasa(copia) == _sin_tasa(profiles.load(congelado))
        a, b = antes_c.decode("utf-8").splitlines(), salida.read_bytes().decode("utf-8").splitlines()
        nuevas = [linea for linea in b if linea not in a]
        assert len(b) == len(a) + 3 and len(nuevas) == 3 and nuevas[2] == f"    error_correction_rate: {tasa:g}"
        assert nuevas[0].startswith("    # error_correction_rate: copia temporal") and "bits" in nuevas[1]
        assert b[b.index(nuevas[2]) - 3].strip() == "corner_refinement_win_size: 7"
        assert (b"\r\n" in salida.read_bytes()) == (b"\r\n" in antes_c)
    assert congelado.read_bytes() == antes_c
    # Sobre una copia que ya trae la clave, la cambia en su linea (y conserva el comentario de esa linea).
    con = tmp_path / "con_tasa.yaml"
    con.write_bytes(salida.read_bytes().replace(b"error_correction_rate: 0.45", b"error_correction_rate: 0.45   # nota"))
    otra = bc.perfil_con_tasa(con, 0.2, tmp_path / "otra.yaml")
    assert profiles.load(otra)["markers"]["detector"]["error_correction_rate"] == 0.2
    assert "    error_correction_rate: 0.2   # nota" in otra.read_text(encoding="utf-8").splitlines()
    assert len(otra.read_bytes().splitlines()) == len(con.read_bytes().splitlines())


def test_perfil_con_tasa_no_pisa_ni_escribe_en_profiles(tmp_path: Path, capsys) -> None:
    antes = sorted(p.name for p in PROFILES_DIR.iterdir())
    existente = tmp_path / "ya.yaml"
    existente.write_text("algo\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="no se pisa"):
        bc.perfil_con_tasa(GS1, 0.3, existente)
    for dentro in (PROFILES_DIR / "tracker_config_tmp.yaml", PROFILES_DIR / "sub" / "x.yaml", GS1):
        with pytest.raises(ValueError, match="solo van los perfiles del repo"):
            bc.perfil_con_tasa(GS1, 0.3, dentro)
    with pytest.raises(ValueError, match="la tasa"):
        bc.perfil_con_tasa(GS1, 1.5, tmp_path / "t.yaml")
    with pytest.raises(ValueError, match="terminar en .yaml"):
        bc.perfil_con_tasa(GS1, 0.3, tmp_path / "t.txt")
    with pytest.raises(FileNotFoundError):
        bc.perfil_con_tasa(tmp_path / "no_esta.yaml", 0.3, tmp_path / "t.yaml")
    # Un perfil sin el bloque markers.detector: no se adivina donde va.
    texto = GS1.read_text(encoding="utf-8")
    ini, fin = texto.index("  detector:\n"), texto.index("  # Reference, la referencia")
    sin = tmp_path / "sin_detector.yaml"
    sin.write_text(texto[:ini] + texto[fin:], encoding="utf-8")
    with pytest.raises(ValueError, match="no trae el bloque markers.detector"):
        bc.perfil_con_tasa(sin, 0.3, tmp_path / "t.yaml")
    # Por la orden `perfil`: codigo 2 y nada escrito; con una salida nueva, 0.
    capsys.readouterr()
    assert bc.main(["perfil", "--base", str(GS1), "--tasa", "0.3", "--salida", str(existente)]) == 2
    assert bc.main(["perfil", "--base", str(GS1), "--tasa", "0.3", "--salida", str(PROFILES_DIR / "tracker_config_tmp.yaml")]) == 2
    assert bc.main(["perfil", "--base", str(GS1), "--tasa", "0", "--salida", str(tmp_path / "t.yaml")]) == 2
    assert capsys.readouterr().out.count("[barrido] ERROR:") == 3
    assert existente.read_text(encoding="utf-8") == "algo\n" and not (tmp_path / "t.yaml").exists()
    assert sorted(p.name for p in PROFILES_DIR.iterdir()) == antes
    assert bc.main(["perfil", "--base", str(GS2), "--tasa", "0.30", "--salida", str(tmp_path / "nuevo" / "gs2.yaml")]) == 0
    assert profiles.load(tmp_path / "nuevo" / "gs2.yaml")["markers"]["detector"]["error_correction_rate"] == 0.3
    assert "markers.detector.error_correction_rate = 0.3" in capsys.readouterr().out


# ----------------------------------------------------------------------------
# 5. «No cambio» con frames reales: el replay de deteccion con cada tasa
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("cam", CAMERAS)
def test_el_replay_de_deteccion_no_cambia_con_ninguna_tasa(cam: str, tmp_path: Path) -> None:
    dataset, frames = TESTS_DATA_DIR / f"marker0_{cam}.npz", TESTS_DATA_DIR / f"marker0_{cam}_frames"
    filas = []
    for tasa in bc.TASAS:
        perfil = bc.perfil_con_tasa(_congelado(cam), tasa, tmp_path / f"{cam}_{bc.clave_tasa(tasa)}.yaml")
        assert set(replay_util.profile_diff(_congelado(cam), perfil)) == {"detector"}
        d = replay_util.compare_detection(dataset, frames, perfil)
        assert d["frames"] == 3 and d["detections"] == 3
        assert d["frames_ids_differ"] == 0 and d["max_diff_px"] == 0.0, (cam, tasa, d)
        filas.append(f"{bc.clave_tasa(tasa)}: {d['frames_ids_differ']:.0f} / {d['max_diff_px']} px")
    print(f"[fase 7d2] replay de deteccion de {cam} (3 frames reales, ID 0) por tasa, frames distintos / dif max: " + "; ".join(filas))


# ----------------------------------------------------------------------------
# 6. `main`: sus codigos y lo que escribe
# ----------------------------------------------------------------------------

def _carpeta(ruta: Path, frames) -> Path:
    ruta.mkdir(parents=True)
    for k, (_nombre, gris) in enumerate(frames):
        assert cv2.imwrite(str(ruta / f"frame_{k:05d}.png"), gris)
    return ruta


@pytest.fixture(scope="module")
def carpetas(tmp_path_factory) -> dict:
    """Carpetas de frames como las de `tracker --save-frames`, con las escenas sinteticas: 6 de la referencia,
    y 2 del tablero solo y 2 con la referencia."""
    raiz = tmp_path_factory.mktemp("frames_b39")
    return {"referencia": _carpeta(raiz / "P5_gs1_frames", esc.poses_referencia(6, semilla=1)),
            "tablero": _carpeta(raiz / "P6_gs1_frames", esc.vistas_tablero(2, False, semilla=1)),
            "tablero_con_referencia": _carpeta(raiz / "P7_gs1_frames", esc.vistas_tablero(2, True, semilla=1))}


def _argv(carpetas: dict, salida: Path, *extra: str, timeout: str = "120") -> list[str]:
    return ["barrer", "--config", str(GS1), "--id", str(ID_REF), "--referencia", str(carpetas["referencia"]),
            "--tablero", str(carpetas["tablero"]), "--tablero-con-referencia", str(carpetas["tablero_con_referencia"]),
            "--salida", str(salida), "--timeout", timeout, *extra]


def test_main_barrer_elige_y_escribe_el_informe(carpetas: dict, tmp_path: Path, capsys) -> None:
    # El barrido sintetico que lee la sesion: aqui, uno corto, guardado como lo guarda `sintetico.py`.
    sint = bc.barrer({"tablero": esc.vistas_tablero(2, False, semilla=2), "tablero_con_referencia": esc.vistas_tablero(1, True, semilla=2)},
                     _markers(), ID_REF)
    sinteticos = tmp_path / "sinteticos.json"
    sinteticos.write_text(json.dumps(sint), encoding="utf-8")
    salida = tmp_path / "barrido"
    rc = bc.main(_argv(carpetas, salida, "--sinteticos", str(sinteticos)))
    out = capsys.readouterr().out
    datos = json.loads((salida / "barrido.json").read_text(encoding="utf-8"))
    real = datos["real"]
    assert sorted(p.name for p in salida.iterdir()) == ["barrido.json", "barrido.md"]
    assert datos["completo"] is True and real["completo"] is True and real["frames_sin_leer"] == 0
    assert [real["categorias"][c]["frames"] for c in bc.CATEGORIAS] == [6, 2, 2]
    assert real["carpetas"]["referencia"] == [str(carpetas["referencia"])]
    assert real["categorias"]["tablero"]["por_tasa"]["0.60"]["frames_fantasma"][0] == "P6_gs1_frames/frame_00000.png"
    assert datos["sintetico"] == sint and datos["perdida_max"] == 0.01 and datos["perfil"] == str(GS1)
    assert datos["regla"] == bc.REGLA == "P69, P74"
    # Lo elegido es lo que da la regla sobre las tablas escritas, y el codigo lo dice.
    elegida, razones = bc.elegir(real, sint)
    assert datos["elegida"] == elegida and datos["razones"] == razones
    assert rc == (0 if elegida is not None else 1)
    assert elegida is not None and elegida < bc.BASE                       # con 0.60 el tablero da fantasmas
    assert real["categorias"]["tablero"]["por_tasa"]["0.60"]["fantasmas"] > 0
    assert real["categorias"]["tablero"]["por_tasa"][bc.clave_tasa(elegida)]["fantasmas"] == 0
    md = (salida / "barrido.md").read_text(encoding="utf-8")
    assert f"**Elegida: {bc.clave_tasa(elegida)}**" in md and "### Frames reales" in md and "### Frames sinteticos" in md
    assert f"elegida: {bc.clave_tasa(elegida)}" in out and "tasa 0.30: 3 bits" in out
    assert "AVISO: el ID 100 no esta en markers.list" in out or ID_REF in [m["id"] for m in _markers()["list"]]
    # Con una tasa sola que no cumple (0.60), codigo 1: ninguna cumple.
    salida1 = tmp_path / "barrido_1"
    assert bc.main(_argv(carpetas, salida1, "--tasas", "0.6")) == 1
    d1 = json.loads((salida1 / "barrido.json").read_text(encoding="utf-8"))
    assert d1["elegida"] is None and d1["sintetico"] is None and "**Elegida: ninguna**" in (salida1 / "barrido.md").read_text(encoding="utf-8")


def test_main_barrer_codigo_2_con_entradas_malas(carpetas: dict, tmp_path: Path, capsys) -> None:
    vacia = tmp_path / "sin_frames"
    vacia.mkdir()
    (vacia / "otra_cosa.png").write_bytes(b"x")
    salida = tmp_path / "barrido"
    casos = {
        "no hay frame_*.png": _argv({**carpetas, "tablero": vacia}, salida),
        "no existe la carpeta": _argv({**carpetas, "referencia": tmp_path / "no_esta"}, salida),
        "--timeout tiene que ser > 0": _argv(carpetas, salida, timeout="0"),
        "la tasa tiene que estar": _argv(carpetas, salida, "--tasas", "0.3", "1.2"),
        "--perdida-max": _argv(carpetas, salida, "--perdida-max", "1.0"),
        "no existe el barrido sintetico": _argv(carpetas, salida, "--sinteticos", str(tmp_path / "no.json")),
    }
    for trozo, argv in casos.items():
        assert bc.main(argv) == 2, trozo
        assert trozo in capsys.readouterr().out and not salida.exists()
    # La salida existente y con algo: codigo 2, sin tocarla. Vacia, vale.
    ocupada = tmp_path / "ocupada"
    ocupada.mkdir()
    (ocupada / "barrido.json").write_text("{}", encoding="utf-8")
    assert bc.main(_argv(carpetas, ocupada)) == 2
    assert "ya existe y tiene algo" in capsys.readouterr().out and (ocupada / "barrido.json").read_text(encoding="utf-8") == "{}"
    # Un barrido sintetico de otro ID, de otro detector o sin una tasa: codigo 2.
    sint = bc.barrer({"tablero": [], "tablero_con_referencia": []}, _markers(), ID_REF)
    malos = {"se hizo con el ID 7": {**sint, "id_ref": 7},
             "otros parametros del detector": {**sint, "detector": {**sint["detector"], "min_marker_perimeter_rate": 0.03}},
             "no es un barrido de formato": {**sint, "formato": 99},
             "no trae la tasa 0.60 en 'tablero'": {**sint, "categorias": {**sint["categorias"], "tablero": {"frames": 0, "por_tasa": {}}}}}
    malos["no trae frames de 'tablero'"] = sint                              # vacio: no comprobaria nada
    lleno = bc.barrer({"tablero": [("gris", np.full((48, 64), 128, np.uint8))],
                       "tablero_con_referencia": [("gris", np.full((48, 64), 128, np.uint8))]}, _markers(), ID_REF)
    malos["es un barrido cortado por el tope"] = {**lleno, "completo": False}
    for trozo, s in malos.items():
        ruta = tmp_path / "sint_malo.json"
        ruta.write_text(json.dumps(s), encoding="utf-8")
        assert bc.main(_argv(carpetas, salida, "--sinteticos", str(ruta))) == 2, trozo
        assert trozo in capsys.readouterr().out and not salida.exists()
    # Un PNG que no es gris de 8 bits, a mitad del barrido: codigo 2 y nada escrito.
    color = _carpeta(tmp_path / "color_frames", [("c", np.zeros((48, 64, 3), np.uint8))])
    assert bc.main(_argv({**carpetas, "tablero": color}, salida)) == 2
    assert "no es una imagen en gris" in capsys.readouterr().out and not salida.exists()
    with pytest.raises(SystemExit) as e:                                   # sin --timeout: argparse, codigo 2
        bc.main(_argv(carpetas, salida)[:-2])
    assert e.value.code == 2


def test_main_barrer_con_el_tope_da_codigo_4_y_escribe_lo_hecho(carpetas: dict, tmp_path: Path, monkeypatch, capsys) -> None:
    reloj = itertools.count()
    monkeypatch.setattr(bc, "time", types.SimpleNamespace(monotonic=lambda: 10.0 * next(reloj)))   # 10 s por lectura del reloj
    salida = tmp_path / "barrido"
    assert bc.main(_argv(carpetas, salida, timeout="25")) == 4
    out = capsys.readouterr().out
    datos = json.loads((salida / "barrido.json").read_text(encoding="utf-8"))
    real = datos["real"]
    assert datos["completo"] is False and datos["elegida"] is None and real["tope_s"] == 25.0
    assert [real["categorias"][c]["frames"] for c in bc.CATEGORIAS] == [2, 0, 0]     # lo hecho: 2 frames antes del tope
    assert real["frames_sin_leer"] == 8
    assert "TOPE de 25 s" in out and "quedaron 8 frames sin leer; no se elige" in out
    assert all("se corto por el tope" in r for r in datos["razones"][:-1])
    assert "barrido cortado por el tope de 25 s" in (salida / "barrido.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="el tope"):
        bc.barrer_carpetas({"referencia": [carpetas["referencia"]]}, _markers(), ID_REF, bc.TASAS, 0.0)


# ----------------------------------------------------------------------------
# 7. La regla mide el detector, no lo publicado
# ----------------------------------------------------------------------------

def test_el_modulo_no_importa_el_paso_del_tracker() -> None:
    fuente = (CODIGO_DIR / "diagnostics" / "barrido_correccion.py").read_text(encoding="utf-8")
    importados: set[str] = set()
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Import):
            importados |= {a.name for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom):
            assert nodo.level == 0, "sin imports relativos"
            importados.add(nodo.module)
            importados |= {f"{nodo.module}.{a.name}" for a in nodo.names}
    assert "vision.detection" in importados and "vision.detection.create_detector" in importados   # reusa, no copia
    prohibidos = {m for m in importados if m == "tracker" or m.startswith("tracker.") or m == "vision"
                  or m.startswith("vision.tracking") or m.startswith("vision.pose") or m.startswith("vision.filtering")}
    assert prohibidos == set(), prohibidos
    assert "MarkerTracker(" not in fuente and "process_corners(" not in fuente


def test_dos_copias_del_id_100_cuentan_como_repetido_con_060_y_con_030() -> None:
    nombre, gris = esc.dos_copias_referencia()
    r = bc.barrer({"referencia": [(nombre, gris)]}, _markers(), ID_REF)
    c = r["categorias"]["referencia"]["por_tasa"]
    for clave in ("0.60", "0.30"):
        s = c[clave]
        assert s["frames"] == 1 and s["ref_doble"] == 1 and s["ref_una"] == 0 and s["ref_detecciones"] == 2
        assert s["frames_doble"] == ["dos_copias"] and s["fantasmas_id_ref"] == 1 and s["comunes"] == 0
    # Y la regla descarta todas las tasas: dos referencias a la vista no las arregla ninguna tasa.
    real = bc.barrer({"referencia": [(nombre, gris)], "tablero": [("gris", np.full((480, 640), 128, np.uint8))],
                      "tablero_con_referencia": [(nombre, gris)]}, _markers(), ID_REF)
    elegida, razones = bc.elegir(real, None)
    assert elegida is None and all("dos o mas veces" in r for r in razones[:-1])
