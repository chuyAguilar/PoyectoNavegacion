"""
Tests para generar_reference_dodecaedro.py.

Ejecutar:
    python -m pytest tests/ -v

Cubren:
  - Identidades matematicas del dodecaedro regular (PHI, r_in, theta).
  - Invariantes geometricos (equidistancia, simetria, marker fit).
  - Convencion OpenCV de las esquinas (c0=TL, c1=TR, c2=BR, c3=BL).
  - Reproducibilidad bit-a-bit contra el archivo historico de iter 1.
  - Reproducibilidad bajo cambio de IDs (iter 2 con IDs 1-11).
  - Validacion de inputs (errores controlados).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
CODIGO_DIR = HERE.parent
sys.path.insert(0, str(CODIGO_DIR))

import generar_reference_dodecaedro as gen


# --- Identidades matematicas ---

def test_phi_identity():
    assert abs(gen.PHI**2 - gen.PHI - 1.0) < 1e-12


def test_phi_value():
    assert abs(gen.PHI - (1.0 + np.sqrt(5.0)) / 2.0) < 1e-12


def test_theta_equals_pi_minus_dihedral():
    dihedral = np.arccos(-1.0 / np.sqrt(5.0))
    assert abs(gen.THETA - (np.pi - dihedral)) < 1e-12


def test_dihedral_deg_canonical():
    assert abs(gen.DIHEDRAL_DEG - 116.56505117707799) < 1e-9


# --- Inradius ---

@pytest.mark.parametrize("edge_mm", [10.0, 20.0, 50.0, 100.0])
def test_inradius_alternate_formula(edge_mm):
    r1 = gen.inradius(edge_mm)
    r2 = (edge_mm / 2.0) * np.sqrt(2.5 + 1.1 * np.sqrt(5.0))
    assert abs(r1 - r2) < 1e-9


def test_inradius_iter1():
    """Para arista 20 mm el inradius es ~22.2703 mm."""
    assert abs(gen.inradius(20.0) - 22.2703) < 1e-3


# --- Geometria del dodecaedro ---

@pytest.fixture
def geometria_default():
    return gen.construir_dodecaedro()


def test_construir_dodecaedro_tiene_11_markers(geometria_default):
    assert len(geometria_default) == 11


def test_ids_default_son_iter1(geometria_default):
    ids = set(geometria_default.keys())
    esperados = {151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161}
    assert ids == esperados


def test_cada_marker_tiene_4_esquinas_3d(geometria_default):
    for tag, esq in geometria_default.items():
        assert esq.shape == (4, 3), f"ID {tag}: shape {esq.shape}"


def test_todas_las_caras_a_r_in_del_origen(geometria_default):
    r_in = gen.inradius(gen.DEFAULT_EDGE_MM)
    for tag, esq in geometria_default.items():
        c = esq.mean(axis=0)
        d = np.linalg.norm(c)
        assert abs(d - r_in) < 1e-9, f"ID {tag}: |c|={d}, esperado {r_in}"


def test_simetria_normales(geometria_default):
    normales = []
    for esq in geometria_default.values():
        c = esq.mean(axis=0)
        normales.append(c / np.linalg.norm(c))
    normales.append(np.array([0.0, 0.0, -1.0]))
    suma = np.sum(normales, axis=0)
    assert np.linalg.norm(suma) < 1e-10


def test_distancia_top_cinturones_uniforme(geometria_default):
    r_in = gen.inradius(gen.DEFAULT_EDGE_MM)
    d_adj = 2.0 * r_in * np.sin(gen.THETA / 2.0)
    c_top = geometria_default[151].mean(axis=0)
    for tid in [152, 153, 154, 155, 156]:
        d = np.linalg.norm(c_top - geometria_default[tid].mean(axis=0))
        assert abs(d - d_adj) < 1e-9


def test_adyacencia_antiprismatica(geometria_default):
    r_in = gen.inradius(gen.DEFAULT_EDGE_MM)
    d_adj = 2.0 * r_in * np.sin(gen.THETA / 2.0)
    sups = [152, 153, 154, 155, 156]
    infs = [157, 158, 159, 160, 161]
    for s, i in zip(sups, infs):
        d = np.linalg.norm(
            geometria_default[s].mean(axis=0) - geometria_default[i].mean(axis=0)
        )
        assert abs(d - d_adj) < 1e-9


def test_esquinas_forman_cuadrado(geometria_default):
    L = gen.DEFAULT_MARKER_MM
    for tag, esq in geometria_default.items():
        for i in range(4):
            lado = np.linalg.norm(esq[i] - esq[(i + 1) % 4])
            assert abs(lado - L) < 1e-9


def test_marker_cabe_en_cara_default():
    diam = gen.diametro_cara_pentagonal(gen.DEFAULT_EDGE_MM)
    assert gen.DEFAULT_MARKER_MM < diam


def test_validar_geometria_pasa(geometria_default):
    ok = gen.validar_geometria(geometria_default, verbose=False)
    assert ok


# --- Convencion OpenCV de las esquinas ---

def test_frame_right_handed_top(geometria_default):
    esq = geometria_default[151]
    x_axis = esq[1] - esq[0]
    y_axis = esq[0] - esq[3]
    z_axis = np.cross(x_axis, y_axis)
    assert z_axis[2] > 0


def test_corner_layout_opencv(geometria_default):
    L = gen.DEFAULT_MARKER_MM
    for tag, esq in geometria_default.items():
        d02 = np.linalg.norm(esq[0] - esq[2])
        d13 = np.linalg.norm(esq[1] - esq[3])
        assert abs(d02 - L * np.sqrt(2)) < 1e-9
        assert abs(d13 - L * np.sqrt(2)) < 1e-9


# --- Reproducibilidad bit-a-bit contra historico ---

HISTORICO = (
    Path(__file__).resolve().parent.parent
    / "historico" / "iter1_2026-05-16" / "data" / "reference_dodecaedro.txt"
)


def _cargar_referencia(ruta):
    rb = {}
    with open(ruta) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            v = linea.split()
            if len(v) < 16:
                continue
            tag = int(v[0])
            corners = np.array([
                [float(v[4]),  float(v[5]),  float(v[6])],
                [float(v[7]),  float(v[8]),  float(v[9])],
                [float(v[10]), float(v[11]), float(v[12])],
                [float(v[13]), float(v[14]), float(v[15])],
            ])
            rb[tag] = corners
    return rb


@pytest.mark.skipif(not HISTORICO.exists(), reason="Historico no disponible")
def test_matches_historico_iter1(tmp_path):
    out = tmp_path / "reference_dodecaedro.txt"
    geom = gen.construir_dodecaedro()
    gen.guardar_archivo(geom, out)
    nuevo = _cargar_referencia(out)
    hist = _cargar_referencia(HISTORICO)
    assert set(nuevo.keys()) == set(hist.keys())
    for tag in nuevo:
        for i in range(4):
            d = np.linalg.norm(nuevo[tag][i] - hist[tag][i])
            assert d < 1e-3


# --- Iter 2: migracion a IDs 1-11 ---

def test_iter2_ids_1_11():
    geom_iter1 = gen.construir_dodecaedro()
    geom_iter2 = gen.construir_dodecaedro(
        id_top=1,
        ids_superior=[2, 3, 4, 5, 6],
        ids_inferior=[7, 8, 9, 10, 11],
    )
    assert len(geom_iter2) == 11
    mapeo = {1: 151, 2: 152, 3: 153, 4: 154, 5: 155, 6: 156,
             7: 157, 8: 158, 9: 159, 10: 160, 11: 161}
    for nuevo_id, viejo_id in mapeo.items():
        np.testing.assert_allclose(
            geom_iter2[nuevo_id], geom_iter1[viejo_id], atol=1e-12
        )


def test_iter2_pasa_validacion():
    geom = gen.construir_dodecaedro(
        id_top=1,
        ids_superior=[2, 3, 4, 5, 6],
        ids_inferior=[7, 8, 9, 10, 11],
    )
    ok = gen.validar_geometria(
        geom,
        id_top=1,
        ids_superior=[2, 3, 4, 5, 6],
        ids_inferior=[7, 8, 9, 10, 11],
        verbose=False,
    )
    assert ok


# --- Validacion de inputs ---

def test_rechaza_edge_negativo():
    with pytest.raises(ValueError, match="edge_mm"):
        gen.construir_dodecaedro(edge_mm=-1.0)


def test_rechaza_marker_negativo():
    with pytest.raises(ValueError, match="marker_mm"):
        gen.construir_dodecaedro(marker_mm=-1.0)


def test_rechaza_marker_mayor_que_cara():
    with pytest.raises(ValueError, match="cabe"):
        gen.construir_dodecaedro(edge_mm=10.0, marker_mm=20.0)


def test_rechaza_ids_duplicados():
    with pytest.raises(ValueError, match="unicos"):
        gen.construir_dodecaedro(
            id_top=1,
            ids_superior=[2, 3, 4, 5, 6],
            ids_inferior=[1, 7, 8, 9, 10],
        )


def test_rechaza_cantidad_ids_incorrecta():
    with pytest.raises(ValueError, match="5 IDs"):
        gen.construir_dodecaedro(
            id_top=1,
            ids_superior=[2, 3, 4],
            ids_inferior=[7, 8, 9, 10, 11],
        )
