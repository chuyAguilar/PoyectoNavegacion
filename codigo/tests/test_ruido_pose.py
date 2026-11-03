"""diagnostics.ruido_pose (meta 007 · El tracker en la Jetson Orin Nano, fase 5b · El ruido de
gs1 por V4L2, B77): los bloques sobre series sinteticas (una normal, una de dos valores, un
seno de frecuencia conocida, una deriva lineal, tiempos uniformes y en rafaga, esquinas con
ruido de escala y con ruido independiente, imagenes con un cuadrado negro) y, sobre el
dataset del replay de Marker0, que `refiltrar` con los tiempos grabados reproduce `sent_M`
(<= 1e-9 mm en Windows, <= 1e-3 mm en Linux, P22) y que los PNG guardados se analizan.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from diagnostics import ruido_pose as rp
from vision.filtering import PositionFilter

from .conftest import TESTS_DATA_DIR
from .test_replay_marker0 import TOL_MM

FS = 87.5
DATASET = TESTS_DATA_DIR / "marker0_gs1.npz"
FRAMES = TESTS_DATA_DIR / "marker0_gs1_frames"


def _rng() -> np.random.Generator:
    return np.random.default_rng(20261103)


def _t(n: int, fs: float = FS) -> np.ndarray:
    return np.arange(n) / fs


# ----------------------------------------------------------------------------- series


def test_intervalos_uniformes_y_en_rafaga() -> None:
    u = rp.intervalos(_t(900))
    assert u["n"] == 899 and u["p50_ms"] == pytest.approx(1000 / FS, rel=1e-6)
    assert u["fraccion_menor_2ms"] == 0.0 and u["fraccion_mayor_1p5_mediana"] == 0.0
    assert u["fps_media"] == pytest.approx(FS, rel=1e-6)
    # Pares de frames: 1 ms y luego 21.86 ms (la misma fps media).
    t = np.repeat(np.arange(450) * 2 / FS, 2)
    t[1::2] += 0.001
    r = rp.intervalos(t)
    assert r["fraccion_menor_2ms"] == pytest.approx(0.5, abs=0.01)
    assert r["fraccion_mayor_1p5_mediana"] == pytest.approx(0.5, abs=0.01)
    assert r["p1_ms"] == pytest.approx(1.0, abs=1e-6) and r["max_ms"] > 20
    assert rp.intervalos(np.array([1.0]))["n"] == 1


def test_bimodalidad_normal_frente_a_dos_valores() -> None:
    rng = _rng()
    normal = rp.bimodalidad(rng.normal(361.0, 0.04, 5000), paso=0.02)
    assert normal["sarle"] < 0.5
    assert normal["dos_grupos"]["separacion"] == pytest.approx(rp.SEPARACION_NORMAL, abs=0.15)
    assert sum(normal["histograma"]["cuentas"]) == 5000
    # Dos valores que alternan frame a frame: rachas de ~1.
    x = 361.0 + 0.1 * (np.arange(5000) % 2) + rng.normal(0, 0.005, 5000)
    alterna = rp.bimodalidad(x, paso=0.02)
    assert alterna["sarle"] > 0.9
    assert alterna["dos_grupos"]["separacion"] > 10
    assert sorted(alterna["dos_grupos"]["centros"]) == pytest.approx([361.0, 361.1], abs=0.005)
    assert alterna["dos_grupos"]["fraccion"] == pytest.approx([0.5, 0.5], abs=0.01)
    assert max(alterna["dos_grupos"]["racha_media"]) < 1.2
    # Los mismos dos valores por bloques de 10 frames: rachas de ~10.
    x = 361.0 + 0.1 * ((np.arange(5000) // 10) % 2) + rng.normal(0, 0.005, 5000)
    bloques = rp.bimodalidad(x, paso=0.02)
    assert min(bloques["dos_grupos"]["racha_media"]) > 8
    assert "dos_grupos" not in rp.bimodalidad(np.array([1.0, 2.0]), paso=0.1)


def test_espectro_encuentra_el_seno_y_separa_lo_lento() -> None:
    t = _t(4000)
    rng = _rng()
    x = 0.05 * np.sin(2 * np.pi * 5.0 * t) + rng.normal(0, 0.002, t.size)
    e = rp.espectro(x, FS)
    assert e["frecuencias_hz"][0] == pytest.approx(5.0, abs=e["resolucion_hz"])
    assert e["fraccion_potencia"][0] > 0.3 and sum(e["fraccion_potencia"]) > 0.8   # la ventana reparte el pico en ~3 bins
    assert e["fraccion_bajo_corte"] < 0.1 and e["corte_hz"] == 2.0
    lento = rp.espectro(0.05 * np.sin(2 * np.pi * 0.2 * t) + rng.normal(0, 0.002, t.size), FS)
    assert lento["fraccion_bajo_corte"] > 0.9
    assert rp.espectro(np.zeros(5), FS)["frecuencias_hz"] == []


def test_deriva_separa_la_pendiente_del_ruido() -> None:
    t = _t(5250)
    rng = _rng()
    x = 361.0 - 0.003 * t + rng.normal(0, 0.03, t.size)        # -3 um/s y 0.03 mm de ruido
    d = rp.deriva(t, x)
    assert d["pendiente_por_s"] == pytest.approx(-0.003, rel=0.15)
    assert d["sd_sin_recta"] == pytest.approx(0.03, rel=0.1)
    assert d["sd_rapida"] == pytest.approx(0.03, rel=0.1)
    assert d["pico_a_pico_lenta"] == pytest.approx(0.18, abs=0.03)
    assert d["sd_lenta"] > d["sd_rapida"] and len(d["medias_por_ventana"]) == 60
    quieto = rp.deriva(t, 361.0 + rng.normal(0, 0.03, t.size))
    assert abs(quieto["pendiente_por_s"]) < 0.0002 and quieto["sd_lenta"] < 0.01
    assert np.isnan(rp.deriva(t[:3], x[:3])["pendiente_por_s"])


def test_refiltrar_es_el_position_filter_y_atenua_el_ruido_blanco() -> None:
    t = _t(3000)
    rng = _rng()
    xyz = np.column_stack([rng.normal(0, 0.1, t.size) for _ in range(3)]) + [10.0, 20.0, 361.0]
    f = PositionFilter(2.0, 0.05)
    esperado = np.array([f.filter(xyz[k].reshape(3, 1), float(t[k])).reshape(3) for k in range(t.size)])
    obtenido = rp.refiltrar(t, xyz, 2.0, 0.05)
    assert np.array_equal(obtenido, esperado)
    # Ruido blanco a 87.5 fps con min_cutoff 2 Hz: alfa 0.126, la sd baja a ~0.26.
    sin_beta = rp.refiltrar(t, xyz, 2.0, 0.0)
    cociente = np.std(sin_beta[200:, 2]) / np.std(xyz[200:, 2])
    assert 0.2 < cociente < 0.35, cociente


def _cuadrado(lado: float, centro=(640.0, 480.0)) -> np.ndarray:
    h = lado / 2
    return np.array(centro) + np.array([[-h, -h], [h, -h], [h, h], [-h, h]])


def test_ruido_esquinas_distingue_escala_de_ruido_independiente() -> None:
    rng = _rng()
    n = 3000
    base = _cuadrado(180.0)
    escala = 1.0 + rng.normal(0, 1e-3, n)
    esq_escala = np.array([(base - base.mean(0)) * s + base.mean(0) for s in escala])
    z = 361.0 / escala
    r = rp.ruido_esquinas(esq_escala, z)
    assert r["correlacion_lado_z"] < -0.99
    assert r["lado_medio_px"] == pytest.approx(180.0, abs=0.01)
    assert r["sd_lado_px"] / r["sd_esquinas_media_px"] > 1.8          # las cuatro se abren juntas
    esq_indep = base[None, :, :] + rng.normal(0, 0.1, (n, 4, 2))
    i = rp.ruido_esquinas(esq_indep, z)
    assert abs(i["correlacion_lado_z"]) < 0.1
    assert i["sd_lado_px"] / i["sd_esquinas_media_px"] < 1.0
    assert i["sd_esquinas_media_px"] == pytest.approx(0.1, rel=0.1)
    assert len(i["sd_esquinas_px"]) == 4 and len(i["sd_centroide_px"]) == 2
    assert rp.ruido_esquinas(base[None]) == {"n": 1}
    assert rp.lado_aparente(base[None])[0] == pytest.approx(180.0)


# ----------------------------------------------------------------------------- imagen


def _imagenes(tmp_path: Path, n: int = 3, sigma_blur: float = 0.0) -> tuple[list[Path], list[np.ndarray]]:
    rng = _rng()
    esq = np.array([[70.0, 70.0], [170.0, 70.0], [170.0, 170.0], [70.0, 170.0]])
    tmp_path.mkdir(parents=True, exist_ok=True)
    pngs = []
    for k in range(n):
        img = np.full((240, 240), 220.0)
        img[70:170, 70:170] = 30.0
        if sigma_blur:
            img = cv2.GaussianBlur(img, (0, 0), sigma_blur)
        img = np.clip(img + rng.normal(0, 2.0, img.shape), 0, 255).astype(np.uint8)
        p = tmp_path / f"frame_{k * 600:05d}.png"
        assert cv2.imwrite(str(p), img)
        pngs.append(p)
    return pngs, [esq] * n


def test_ruido_imagen_sobre_un_cuadrado_negro(tmp_path: Path) -> None:
    pngs, esq = _imagenes(tmp_path)
    r = rp.ruido_imagen(pngs, esq)
    assert r["n_png"] == 3
    assert r["nivel_blanco"] == pytest.approx(220, abs=1) and r["nivel_negro"] == pytest.approx(30, abs=1)
    assert r["contraste"] == pytest.approx(190, abs=2)
    assert len(r["nivel_blanco_por_png"]) == 3 and r["nivel_negro_por_png"][0] == pytest.approx(30, abs=1)
    assert r["sd_pixel_blanco"] == pytest.approx(2.0, abs=0.5) and r["sd_pixel_negro"] == pytest.approx(2.0, abs=0.5)
    assert r["ancho_borde_px"] <= 1.5
    assert r["bloqueo_jpeg"] == pytest.approx(1.0, abs=0.15)
    assert r["movimiento_esquinas_px"] == 0.0
    borroso = rp.ruido_imagen(*_imagenes(tmp_path / "b", sigma_blur=2.0))
    assert borroso["ancho_borde_px"] > 3.0
    uno = rp.ruido_imagen(pngs[:1], esq[:1])
    assert uno["n_png"] == 1 and np.isnan(uno["sd_pixel_blanco"])
    assert rp.ruido_imagen([], []) == {"n_png": 0}
    with pytest.raises(ValueError, match="no se pudo leer"):
        rp.ruido_imagen([tmp_path / "no.png"], esq[:1])


# ----------------------------------------------------------------------------- la grabacion real


def test_analizar_el_dataset_del_replay_reproduce_lo_enviado() -> None:
    assert DATASET.is_file() and FRAMES.is_dir(), "falta la linea base de Marker0 (test_replay_marker0)"
    r = rp.analizar(DATASET, FRAMES)
    assert "error" not in r and r["frames_con_pose"] > 100
    assert r["max_diff_refiltrado_mm"] <= TOL_MM, r["max_diff_refiltrado_mm"]
    assert r["sd_z_refiltrada_grabada_mm"] == pytest.approx(r["sd_z_enviada_mm"], rel=1e-6)
    assert r["excluidos"]["varias_detecciones"] == 0 and r["excluidos"]["pose_invalida"] == 0
    assert r["frames_con_pose"] + sum(r["excluidos"].values()) == r["frames"]
    assert 0 < r["sd_z_enviada_mm"] < r["sd_z_cruda_mm"] < 1.0           # el filtro baja el ruido
    assert r["intervalos"]["fraccion_menor_2ms"] < 0.05
    assert r["esquinas"]["correlacion_lado_z"] < -0.3
    assert r["filtro"] == {"enabled": True, "min_cutoff": 2.0, "beta": 0.05}
    assert set(r["deriva_z_enviada"]) >= {"pendiente_por_s", "sd_lenta", "sd_rapida"}
    assert r["espectro_z_cruda"]["frecuencias_hz"] and 0 <= r["espectro_z_cruda"]["fraccion_bajo_corte"] <= 1
    im = r["imagen"]
    assert im["n_png"] == 3 and im["contraste"] > 30 and im["nivel_blanco"] > im["nivel_negro"]
    assert np.isfinite(im["ancho_borde_px"]) and np.isfinite(im["bloqueo_jpeg"])
    assert im["movimiento_esquinas_px"] < 5.0


def test_serie_pose_exige_el_marker() -> None:
    from diagnostics.pose_log import load_recording
    rec = load_recording(DATASET)
    with pytest.raises(ValueError, match="no tiene un marker"):
        rp.serie_pose(rec, "Dodecaedro")
    s = rp.serie_pose(rec)
    assert s["id"] == 0 and s["size_mm"] == 80.0
    assert s["esquinas"].shape == (len(s["frames"]), 4, 2) and s["xyz_crudo"].shape == (len(s["frames"]), 3)


# ----------------------------------------------------------------------------- comparar y CLI


def test_comparar_y_formato_markdown() -> None:
    res = {"W1": {"sd_z_enviada_mm": 0.04, "esquinas": {"sd_lado_px": 0.1, "sd_centroide_px": [0.1, 0.2]},
                  "filtro": {"enabled": True}, "config": "x", "lista": [1, 2, 3, 4, 5]},
           "J1": {"sd_z_enviada_mm": 0.08, "esquinas": {"sd_lado_px": 0.0, "sd_centroide_px": [0.2, 0.2]},
                  "filtro": {"enabled": True}, "config": "y", "extra": 3.0}}
    c = rp.comparar(res, "W1")
    assert c["referencia"] == "W1" and c["etiquetas"] == ["W1", "J1"]
    assert c["filas"]["sd_z_enviada_mm"]["cociente"]["J1"] == pytest.approx(2.0)
    assert c["filas"]["esquinas.sd_centroide_px[0]"]["cociente"]["J1"] == pytest.approx(2.0)
    assert c["filas"]["extra"]["cociente"]["J1"] is None and c["filas"]["extra"]["valores"]["W1"] is None
    assert "filtro.enabled" not in c["filas"] and "config" not in c["filas"] and "lista[0]" not in c["filas"]
    md = rp.formato_markdown(c)
    assert "| metrica | W1 (ref) | J1 |" in md and "0.08 (x2.00)" in md and "`extra`" in md
    with pytest.raises(ValueError, match="referencia"):
        rp.comparar(res, "Z")


def test_cli_escribe_json_y_markdown_y_no_pisa(tmp_path: Path, capsys) -> None:
    out, md = tmp_path / "b77" / "a.json", tmp_path / "b77" / "a.md"
    rc = rp.main(["--input", f"W1={DATASET}", "--input", f"J1={DATASET}", "--frames", f"J1={FRAMES}",
                  "--referencia", "W1", "--output", str(out), "--output-markdown", str(md)])
    assert rc == 0 and out.is_file() and md.is_file()
    datos = json.loads(out.read_text(encoding="utf-8"))
    assert set(datos) == {"resultados", "comparacion"} and set(datos["resultados"]) == {"W1", "J1"}
    assert datos["comparacion"]["filas"]["sd_z_enviada_mm"]["cociente"]["J1"] == pytest.approx(1.0)
    assert datos["resultados"]["J1"]["imagen"]["n_png"] == 3 and "imagen" not in datos["resultados"]["W1"]
    assert "| metrica | W1 (ref) | J1 |" in md.read_text(encoding="utf-8")
    assert "[ruido_pose] J1:" in capsys.readouterr().out
    rc = rp.main(["--input", f"W1={DATASET}", "--referencia", "W1", "--output", str(out), "--output-markdown", str(md)])
    assert rc == 2 and "no se pisa" in capsys.readouterr().err
    rc = rp.main(["--input", f"W1={DATASET}", "--referencia", "Z", "--output", str(tmp_path / "b.json"),
                  "--output-markdown", str(tmp_path / "b.md")])
    assert rc == 2 and not (tmp_path / "b.json").exists()
    rc = rp.main(["--input", f"W1={DATASET}", "--input", f"W1={DATASET}", "--referencia", "W1",
                  "--output", str(tmp_path / "c.json"), "--output-markdown", str(tmp_path / "c.md")])
    assert rc == 2
    with pytest.raises(SystemExit):
        rp.main(["--input", "sin_igual", "--referencia", "x", "--output", "a", "--output-markdown", "b"])
