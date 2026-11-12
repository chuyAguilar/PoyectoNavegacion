"""El modo de una camara del asistente y `calibrate_camera --desde-asistente`, sin camara (meta 006, fase 7d · El
tablero ChArUco y los intrinsecos con el asistente de una camara).

Los puntos 1 a 5 y 10 del criterio de la fase (`plan.md`), con el tablero ChArUco renderizado por
`tablero_sintetico.renderizar_charuco` (K y distorsion conocidas) y un reloj falso:
  1. Un guion de 40 poses que cubre la rejilla 8 x 6: el asistente las toma, `calibrate_camera --desde-asistente`
     termina con 0 y recupera fx, fy, cx y cy a <= 0.5 px; las esquinas que el calculo lee de la carpeta son, bit a
     bit, las detectadas en los frames en memoria (la carpeta no cambio nada), y con 12 de ellas pasadas a
     `calibrar` a mano la K es la misma, diferencia 0.0. (La calibracion de 35 vistas tarda ~4.5 s en OpenCV 4.11
     y crece muy deprisa con las vistas, 27 s con 60: por eso la de 40 se hace una vez y la de mano, con 12.)
  2. La variedad: una vista que repite pose pero anade 2 celdas finas se toma; la que no anade ninguna, no.
  3. `--modo intrinsecos` con dos `--config` o `estereo` con uno: codigo 2. El tope, la camara que deja de dar
     frames (4) y `q` con el minimo (0), como en la fase 7a.
  4. `--max-std-px` y `--cobertura-fina-min`: una calibracion que no los cumple sale con 1 y lo dice.
  5. `comparar_intrinsecos`: un .yml consigo mismo, 0 y 0 sigmas; fx +11.08 px con desviaciones 0.59 y 1.091, +8.9.
 10. `calibrate_camera --patron charuco` sobre 40 vistas parciales a 1280 x 960 con la K de gs1 (el tablero llevado
     a los bordes): fx, fy, cx, cy a <= 0.5 px y cobertura 8 x 6 >= 0.95; a mano, 0.0.
La K con la que el asistente mide la variedad (`K_APROX`, sin distorsion) NO es la verdadera (`K_VERD`, con ella):
es la prueba de que el calculo no la usa. Ninguna prueba abre una camara ni una ventana.
"""
from __future__ import annotations

import json
import shutil
import threading
import time

import cv2
import numpy as np
import pytest

from calibration import calibrate_camera as cc
from calibration import calibrate_extrinsics as ce
from calibration import capture_stereo_board as csb
from calibration import charuco_board as chb

from . import tablero_sintetico as ts
from .conftest import DATA_DIR

T = chb.TableroCharuco((9, 7), 26.0, 19.5, "DICT_4X4_50")                  # el de P59
COLS, ROWS, SQ = 8, 6, 26.0                                                 # sus esquinas interiores y su casilla
CAM = "gs1"
SHAPE = (640, 480)
K_VERD = ts.K_de(602.0, 598.0, 325.0, 236.0)                                # la de la camara falsa
DIST_VERD = np.array([-0.08, 0.03, 0.0005, -0.0003, 0.0])
K_APROX = ts.K_de(600.0, 600.0, 320.0, 240.0)                               # la del perfil: aproximada y sin distorsion
INTR = {CAM: {"K": K_APROX, "dist": np.zeros(5), "shape": SHAPE}}
MARKERS_YAML = "markers:\n  dictionary: DICT_ARUCO_MIP_36h12\n  list:\n  - {id: 100, name: Reference, size_mm: 98.6}\n"
TICK = 0.125
GRIS = np.full((SHAPE[1], SHAPE[0]), 128, dtype=np.uint8)


@pytest.fixture(autouse=True)
def sin_camara_real(monkeypatch):
    def _prohibido(*_a, **_k):
        raise AssertionError("una prueba intento abrir una camara real (create_backend)")
    monkeypatch.setattr(csb, "create_backend", _prohibido)
    monkeypatch.setattr(cc, "create_backend", _prohibido)


@pytest.fixture(autouse=True)
def sin_ventanas(monkeypatch):
    visto = {"namedWindow": 0, "imshow": 0, "destroyAllWindows": 0}
    monkeypatch.setattr(csb.cv2, "namedWindow", lambda *a, **k: visto.__setitem__("namedWindow", visto["namedWindow"] + 1))
    monkeypatch.setattr(csb.cv2, "imshow", lambda *a, **k: visto.__setitem__("imshow", visto["imshow"] + 1))
    monkeypatch.setattr(csb.cv2, "destroyAllWindows", lambda: visto.__setitem__("destroyAllWindows", visto["destroyAllWindows"] + 1))
    monkeypatch.setattr(csb.cv2, "pollKey", lambda: -1)
    return visto


# ----------------------------------------------------------------------------
# El mundo falso de una camara
# ----------------------------------------------------------------------------

def _T(rvec, tvec) -> np.ndarray:
    M = np.eye(4)
    M[:3, :3] = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64))[0]
    M[:3, 3] = np.asarray(tvec, dtype=np.float64)
    return M


def guion_de_poses(n: int, K, dist, shape, columnas: int, filas: int, z_mm, semilla: int, margen_px: float) -> list[dict]:
    """`n` poses del tablero que recorren la imagen (una rejilla de `columnas` x `filas` objetivos que llega a
    `margen_px` de los bordes: el tablero queda en parte fuera), inclinadas hasta ~30 grados, cada una con
    >= 16 esquinas leidas y distinta de las anteriores con margen (12.5 grados o 50 mm): `rvec`, `tvec`, `T`,
    `img` y lo que se lee en ella (`esquinas`, `ids`)."""
    rng = np.random.default_rng(semilla)
    det = chb.detector(T)
    w, h = shape
    objetivos = [(x, y) for y in np.linspace(margen_px, h - margen_px, filas) for x in np.linspace(margen_px, w - margen_px, columnas)]
    poses: list[dict] = []
    for objetivo in objetivos[:n]:
        for _intento in range(40):
            rv = np.array([rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.6, 0.6)])
            tv = ts.pose_charuco_hacia(T, K, rv, objetivo, rng.uniform(*z_mm))
            M = _T(rv, tv)
            if not csb.es_distinta(M, [p["T"] for p in poses], COLS + 2, ROWS + 2, SQ, 12.5, 50.0):
                continue
            img = ts.renderizar_charuco(T, K, rv, tv, shape, dist)
            r = chb.detectar_charuco(img, det, T, 16)
            if r is not None:
                poses.append({"rvec": rv, "tvec": tv, "T": M, "img": img, "esquinas": r[0], "ids": r[1]})
                break
        else:
            raise AssertionError(f"ninguna pose vale para el objetivo {objetivo}")
    return poses


class Mundo:
    """Tramos `(nombre, duracion_s, imagen | None)` seguidos; el ultimo dura para siempre. El reloj avanza un
    `tick` por vuelta, 1/90 s por frame de la rafaga, y se para mientras el asistente comprueba (espera al hilo)."""

    def __init__(self, tramos, asistente, n_frames: int, tick: float = TICK) -> None:
        self.tramos, self.a, self.n_frames, self.tick = list(tramos), asistente, int(n_frames), float(tick)
        self.t, self._k = 0.0, 0
        self.fin = sum(d for _n, d, _img in self.tramos)

    def reloj(self) -> float:
        return self.t

    def frame(self) -> np.ndarray:
        t0 = 0.0
        for _nombre, dur, img in self.tramos:
            if self.t < t0 + dur:
                return GRIS if img is None else img
            t0 += dur
        img = self.tramos[-1][2]
        return GRIS if img is None else img

    def pedir(self):
        estado = self.a.estado
        if estado == "quieto" and self._k < self.n_frames:
            self._k += 1
            self.t += 1.0 / 90.0
        else:
            if estado != "quieto":
                self._k = 0
            if estado == "comprobando":
                for hilo in threading.enumerate():
                    if hilo.name == "comprobar-rafaga":
                        hilo.join(20.0)
            else:
                self.t += self.tick
        return self.frame(), self.t


class Fuente:
    """La interfaz de `FrameGrabber` sobre el mundo falso."""

    def __init__(self, mundo: Mundo, muere_en: float | None = None) -> None:
        self.mundo, self.muere_en = mundo, muere_en
        self.failed = False
        self.frames_read = 0

    def next_frame(self, timeout: float):
        if self.muere_en is not None and self.mundo.t >= self.muere_en:
            self.mundo.t += timeout                     # el tiempo que el bucle espero en vano
            return None
        frame, t = self.mundo.pedir()
        self.frames_read += 1
        return frame, t, self.frames_read


def nuevo_asistente(objetivo: int, minimo: int, quieto_s: float = csb.QUIETO_S, min_muestras: int = csb.MIN_MUESTRAS_QUIETO,
                    **kw) -> csb.Asistente:
    args = dict(camaras=(CAM,), modo="intrinsecos", celdas=csb.CELDAS_FINAS, min_celdas_nuevas=csb.MIN_CELDAS_NUEVAS, tablero=T)
    args.update(kw)
    return csb.Asistente(COLS, ROWS, SQ, INTR, csb.UMBRAL_DEG, csb.UMBRAL_MM, quieto_s, csb.QUIETO_PX, objetivo, minimo,
                         csb.POSTURAS_INTR, min_muestras, **args)


def correr(tramos, carpeta, objetivo: int, minimo: int, n_frames: int = 2, limite: float | None = None,
           muere_en: float | None = None, q_al_final: bool = True, tick: float = TICK, **kw) -> dict:
    a = nuevo_asistente(objetivo, minimo, **kw)
    mundo = Mundo(tramos, a, n_frames, tick)
    pitidos, ventanas = [], []
    r = csb.capturar_sesion({CAM: Fuente(mundo, muere_en)}, INTR, a, carpeta, mundo.fin + 60.0 if limite is None else limite,
                            n_frames, 0.3, clock=mundo.reloj,
                            leer_tecla=lambda: ord("q") if (q_al_final and mundo.t >= mundo.fin) else 255,
                            mostrar=lambda img: ventanas.append(img.shape), pitido=pitidos.append, escala_previa=1.0,
                            meta={"prueba": True})
    return {"r": r, "a": a, "mundo": mundo, "pitidos": pitidos, "ventanas": ventanas,
            "sesion": json.loads((carpeta / "sesion.json").read_text(encoding="utf-8"))}


def _perfil(ruta, w: int, h: int, cal=None):
    ruta.write_text(f"camera:\n  camera_type: webcam\n  source: 1\n  width: {w}\n  height: {h}\n  fps: 90\n"
                    + (f"  calibration_file: '{str(cal).replace(chr(92), '/')}'\n" if cal is not None else "") + MARKERS_YAML, encoding="utf-8")
    return ruta


def _tablero_json(ruta):
    ruta.write_text(json.dumps({"casillas": [9, 7], "casilla_mm": 26.0, "marcador_mm": 19.5, "diccionario": "DICT_4X4_50",
                                "legacy": False, "medido": False, "muestra": False}), encoding="utf-8")
    return ruta


def _en_memoria(poses) -> tuple[list, list]:
    """(obj_points, img_points) de las esquinas detectadas en los frames en memoria (las del guion: `detectar_charuco`
    sobre la imagen renderizada), sin carpeta de por medio."""
    return ([chb.puntos_objeto(T, p["ids"]) for p in poses],
            [np.asarray(p["esquinas"], dtype=np.float32).reshape(-1, 1, 2) for p in poses])


@pytest.fixture()
def espia_calibrar(monkeypatch):
    """Apunta lo que `main` le pasa a `calibrar` (que corre de verdad)."""
    visto: dict = {}
    real = cc.calibrar

    def espia(obj_points, img_points, *a, **k):
        visto.update(objs=obj_points, imgs=img_points, args=a)
        return real(obj_points, img_points, *a, **k)

    monkeypatch.setattr(cc, "calibrar", espia)
    return visto


def _las_mismas_esquinas(visto: dict, poses) -> bool:
    """Lo que el calculo leyo de la carpeta y paso a `calibrar` es, bit a bit, lo detectado en memoria."""
    objs, imgs = _en_memoria(poses)
    return (len(visto["imgs"]) == len(poses)
            and all(np.array_equal(a, b) and a.dtype == b.dtype == np.float32 for a, b in zip(visto["imgs"], imgs))
            and all(np.array_equal(a, b) and a.dtype == b.dtype == np.float32 for a, b in zip(visto["objs"], objs)))


# ----------------------------------------------------------------------------
# 1. Cuarenta poses por el asistente y el calculo sobre su carpeta
# ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def poses40():
    return guion_de_poses(40, K_VERD, DIST_VERD, SHAPE, 8, 5, (300.0, 430.0), semilla=3, margen_px=50.0)


@pytest.fixture(scope="module")
def sesion40(tmp_path_factory, poses40):
    """La sesion de las 40 poses, una sola vez, y lo que hace falta para calcular sobre su carpeta."""
    base = tmp_path_factory.mktemp("intr40")
    carpeta = base / "datos"
    t0 = time.perf_counter()
    # Quietud de 0.5 s con 4 muestras y una vuelta cada 0.17 s (los valores por defecto los prueban las demas): ~5 vueltas por
    # pose. Tramos de 0.8 s: la cuarta muestra cae como tarde a 0.68 s y la rafaga acaba antes de que cambie la pose (con
    # tramos de 0.7 s una rafaga pillaba el cambio y el asistente la rechazaba, bien, por moverse 79 px).
    s = correr([(f"P{k:02d}", 0.8, p["img"]) for k, p in enumerate(poses40, start=1)], carpeta, 40, 30, q_al_final=False,
               tick=0.17, quieto_s=0.5, min_muestras=4)
    s["segundos"] = time.perf_counter() - t0
    yml = base / "intrinsecos_aprox.yml"
    cc.guardar_yml(yml, K_APROX, np.zeros(5), SHAPE[0], SHAPE[1], 0.1, 20, COLS, ROWS, SQ, {"detector": "sb"})
    return {**s, "carpeta": carpeta, "base": base, "perfil": _perfil(base / "perfil_gs1.yaml", 640, 480, yml), "yml": yml,
            "tablero": _tablero_json(base / "tablero.json")}


def _argv_calculo(s, salida, *extra: str) -> list[str]:
    return ["--config", str(s["perfil"]), "--desde-asistente", str(s["carpeta"]), "--camara", CAM, "--patron", "charuco",
            "--tablero-charuco", str(s["tablero"]), "--min-esquinas", "12", "--frames-por-vista", "2", "--max-movimiento-px", "0.3",
            "--min-vistas", "25", "--n-control", "5", "--semilla", "0", "--output", str(salida / "intrinsecos_gs1_propuesta.yml"),
            "--reporte", str(salida / "calculo.json"), "--timeout", "120", *extra]


def test_el_asistente_toma_las_cuarenta_poses_del_guion(sesion40, poses40) -> None:
    r, a, ses = sesion40["r"], sesion40["a"], sesion40["sesion"]
    assert r["fin"] == "objetivo" and r["codigo"] == 0 and r["tomadas"] == 40 and r["rechazadas"] == 0
    assert r["posiciones"] == [f"T{k:02d}" for k in range(1, 41)] and a.terminado
    carpetas = sorted(p.name for p in sesion40["carpeta"].iterdir() if p.is_dir())
    assert carpetas == [f"T{k:02d}_gs1_frames" for k in range(1, 41)]                   # una camara: sin carpetas de gs2
    assert sorted(p.name for p in (sesion40["carpeta"] / "T01_gs1_frames").iterdir()) == ["frame_00000.png", "frame_00001.png"]
    assert np.array_equal(cv2.imread(str(sesion40["carpeta"] / "T07_gs1_frames" / "frame_00001.png"), cv2.IMREAD_UNCHANGED), poses40[6]["img"])
    # La cobertura que cuenta el asistente es la de las esquinas del guion (las mismas que lee el calculo).
    fina = cc.celdas_cubiertas([p["esquinas"] for p in poses40], SHAPE, csb.CELDAS_FINAS)
    assert a.celdas_cubiertas == fina and a.cobertura_fina == pytest.approx(len(fina) / 48.0) and a.cobertura_fina >= 0.95
    assert a.cobertura_gruesa == 1.0 and r["cobertura"]["fina"] == a.cobertura_fina
    # sesion.json: el modo, el patron, la K aproximada (solo para la variedad) y las dos coberturas.
    assert ses["modo"] == "intrinsecos" and ses["patron"] == "charuco" and ses["codigo"] == 0 and ses["fin"] == "objetivo"
    assert ses["tablero"] == {"cols": 8, "rows": 6, "square_mm": 26.0, "charuco": {
        "casillas": [9, 7], "casilla_mm": 26.0, "marcador_mm": 19.5, "diccionario": "DICT_4X4_50", "legacy": False}}
    assert np.allclose(ses["k_aproximada"][CAM]["K"], K_APROX) and ses["parametros"]["detector_final"] == "charuco"
    assert ses["parametros"]["celdas"] == [8, 6] and ses["parametros"]["min_celdas_nuevas"] == 2 and ses["parametros"]["min_esquinas"] == 12
    assert ses["cobertura"]["fina"] == pytest.approx(a.cobertura_fina) and ses["cobertura"]["gruesa"] == 1.0
    assert len(ses["cobertura"]["cubiertas_finas"]) == len(fina) and set(ses["fps"]) == {CAM}
    for t, p in zip(ses["tomadas"], poses40):
        m = t["camaras"][CAM]
        assert set(t["camaras"]) == {CAM} and t["emparejado"] == [] and t["dt_max_ms"] is None
        assert m["n_detectados"] == 2 and m["movimiento_px"] == 0.0 and "esquinas" not in m and m["ids"] == p["ids"].tolist()
        assert 0.0 < t["cobertura_fina"] <= 1.0
    # La pose que mide el asistente (con la K aproximada) queda cerca de la del guion: vale para la variedad.
    difs = [csb.diferencia_vistas(t["T"], p["T"], COLS + 2, ROWS + 2, SQ) for t, p in zip(a.tomadas, poses40)]
    assert max(d[0] for d in difs) < 8.0 and max(d[1] for d in difs) < 25.0, (max(d[0] for d in difs), max(d[1] for d in difs))
    assert all(v == (600 + csb.ALTO_FRANJA, csb.ANCHO_VISTA_INTR + csb.ANCHO_LADO_INTR, 3) for v in sesion40["ventanas"])
    print(f"[fase 7d] 40 poses por el asistente de una camara en {sesion40['segundos']:.1f} s ({len(sesion40['ventanas'])} vueltas); "
          f"cobertura 8x6 {a.cobertura_fina:.2f}, 4x3 {a.cobertura_gruesa:.2f}; esquinas por vista de "
          f"{min(len(p['ids']) for p in poses40)} a {max(len(p['ids']) for p in poses40)}")


def test_el_calculo_sobre_la_carpeta_recupera_la_k_y_a_mano_da_lo_mismo(sesion40, poses40, tmp_path, capsys, espia_calibrar) -> None:
    rc = cc.main(_argv_calculo(sesion40, tmp_path, "--celdas-finas", "8", "6", "--cobertura-fina-min", "0.85", "--max-std-px", "1.0",
                               "--comparar-con", str(sesion40["yml"])))
    e = json.loads((tmp_path / "calculo.json").read_text(encoding="utf-8"))
    res = e["resultado"]
    assert rc == 0, res["fallos"]
    assert e["vistas"]["total"] == 40 and e["vistas"]["detectadas"] == 40 and e["vistas"]["apartadas"] == [] and e["patron"] == "charuco"
    assert e["vistas"]["esquinas_por_vista"] == [len(p["ids"]) for p in poses40]
    assert res["n_vistas_usadas"] == 35 and len(res["indices_control"]) == 5 and res["cumple"] is True and res["detector"] == "charuco"
    Kc = np.asarray(res["K"])
    err = {n: abs(Kc[i, j] - K_VERD[i, j]) for n, (i, j) in {"fx": (0, 0), "fy": (1, 1), "cx": (0, 2), "cy": (1, 2)}.items()}
    assert max(err.values()) <= 0.5, err
    assert res["rms_px"] < 0.2 and res["rms_control_px"] < 0.2 and res["cobertura"] == 1.0 and res["cobertura_fina"] >= 0.85
    assert max(res["std_intrinsecos"].values()) <= 1.0 and set(res["std_distorsion"]) == {"k1", "k2", "p1", "p2", "k3"}
    assert e["criterio"]["cobertura_fina"] == 0.85 and e["criterio"]["max_std_px"] == 1.0 and e["tablero_charuco"]["medido"] is False
    # Las esquinas que leyo de la carpeta son, bit a bit, las detectadas en los frames en memoria: el formato no cambio nada.
    assert _las_mismas_esquinas(espia_calibrar, poses40) and espia_calibrar["args"] == (SHAPE, 5, 0)
    # La comparacion con el .yml del perfil (sin desviaciones: solo la diferencia) y el .yml escrito.
    comp = res["comparacion"]["parametros"]
    assert comp["fx"]["dif"] == pytest.approx(Kc[0, 0] - 600.0) and comp["fx"]["sigmas"] is None and res["comparacion"]["max_sigmas"] is None
    yml = cc.leer_intrinsecos_con_std(tmp_path / "intrinsecos_gs1_propuesta.yml")
    assert np.array_equal(yml["K"], Kc) and set(yml["std"]) == set(cc.PARAMETROS)
    intr = ce.leer_intrinsecos(tmp_path / "intrinsecos_gs1_propuesta.yml")
    assert intr["shape"] == SHAPE and intr["detector"] == "charuco" and intr["square_mm"] == 26.0
    fs = cv2.FileStorage(str(tmp_path / "intrinsecos_gs1_propuesta.yml"), cv2.FILE_STORAGE_READ)
    try:
        assert fs.getNode("patron").string() == "charuco" and fs.getNode("camara").string() == CAM
        assert fs.getNode("cobertura_fina").real() >= 0.85 and fs.getNode("criterio_cumplido").real() == 1
        assert fs.getNode("posiciones_control").size() == 5 and fs.getNode("tablero_charuco").getNode("diccionario").string() == "DICT_4X4_50"
    finally:
        fs.release()
    salida = capsys.readouterr().out
    assert "Tablero ChArUco: 9x7 casillas de 26 mm (NOMINAL, sin medir)" in salida and "frente a intrinsecos_aprox.yml, fx: 600.00 ->" in salida
    print(f"[fase 7d] calibrate_camera --desde-asistente, 40 vistas ChArUco a 640x480: error fx {err['fx']:.3f}, fy {err['fy']:.3f}, "
          f"cx {err['cx']:.3f}, cy {err['cy']:.3f} px; RMS {res['rms_px']:.4f}, control {res['rms_control_px']:.4f} px; desviaciones "
          f"{ {k: round(v, 3) for k, v in res['std_intrinsecos'].items()} }; cobertura fina {res['cobertura_fina']:.2f}; las esquinas de la carpeta, bit a bit las de memoria")


CATORCE = (1, 4, 8, 10, 13, 16, 19, 22, 25, 28, 32, 35, 37, 40)             # repartidas por toda la imagen


@pytest.fixture()
def doce(sesion40, tmp_path):
    """14 posiciones de la sesion (`CATORCE`), copiadas a otra carpeta: calibrar con 11 vistas tarda decimas de segundo."""
    carpeta = tmp_path / "doce"
    for k in CATORCE:
        shutil.copytree(sesion40["carpeta"] / f"T{k:02d}_gs1_frames", carpeta / f"T{k:02d}_gs1_frames")
    return {**sesion40, "carpeta": carpeta}


def _argv_doce(s, salida, *extra: str) -> list[str]:
    argv = _argv_calculo(s, salida, *extra)
    argv[argv.index("--min-vistas") + 1] = "9"
    argv[argv.index("--n-control") + 1] = "3"
    return argv


def test_a_mano_la_diferencia_es_cero(doce, poses40, tmp_path) -> None:
    """Con 14 vistas: `main` sobre la carpeta y `calibrar` a mano con las esquinas de los frames en memoria dan la
    misma K, la misma distorsion y el mismo RMS, bit a bit (diferencia 0.0)."""
    rc = cc.main(_argv_doce(doce, tmp_path))
    res = json.loads((tmp_path / "calculo.json").read_text(encoding="utf-8"))["resultado"]
    assert rc == 0, res["fallos"]
    objs, imgs = _en_memoria([poses40[k - 1] for k in CATORCE])
    mano = cc.calibrar(objs, imgs, SHAPE, 3, 0)
    assert res["n_vistas_usadas"] == 11 and res["indices_control"] == mano["indices_control"]
    assert np.array_equal(mano["K"], np.asarray(res["K"])) and np.array_equal(mano["dist"], np.asarray(res["dist"]))
    assert mano["rms_px"] == res["rms_px"] and mano["rms_control_px"] == res["rms_control_px"] and mano["std_intrinsecos"] == res["std_intrinsecos"]
    assert float(np.abs(mano["K"] - np.asarray(res["K"])).max()) == 0.0


def test_los_criterios_opcionales_y_las_vistas_que_faltan(doce, tmp_path, capsys) -> None:
    """Punto 4: con `--max-std-px` y `--cobertura-fina-min`, la que no cumple sale con 1 y lo dice (y guarda el veredicto)."""
    rc = cc.main(_argv_doce(doce, tmp_path, "--max-std-px", "0.001", "--celdas-finas", "40", "30", "--cobertura-fina-min", "0.85"))
    e = json.loads((tmp_path / "calculo.json").read_text(encoding="utf-8"))
    fallos = e["resultado"]["fallos"]
    assert rc == 1 and e["resultado"]["cumple"] is False and e["resultado"]["celdas_finas"] == [40, 30]
    assert any(f.startswith("cobertura fina") and "< 0.85" in f for f in fallos)
    assert [f.split()[2] for f in fallos if f.startswith("desviacion de")] == ["fx", "fy", "cx", "cy"]
    assert "Criterio NO cumplido" in capsys.readouterr().out
    fs = cv2.FileStorage(str(tmp_path / "intrinsecos_gs1_propuesta.yml"), cv2.FILE_STORAGE_READ)
    try:
        assert fs.getNode("criterio_cumplido").real() == 0 and fs.getNode("criterio_fallos").size() == len(fallos)
    finally:
        fs.release()
    # Sin las opciones nuevas, esos dos criterios no cuentan (lo de siempre).
    otro = tmp_path / "sin"
    otro.mkdir()
    assert cc.main(_argv_doce(doce, otro)) == 0
    assert "cobertura_fina" not in json.loads((otro / "calculo.json").read_text(encoding="utf-8"))["criterio"]
    # Menos vistas de las que hacen falta: 1, con el numero, y sin .yml.
    pocas = tmp_path / "pocas"
    pocas.mkdir()
    argv = _argv_doce(doce, pocas)
    argv[argv.index("--min-vistas") + 1] = "60"
    assert cc.main(argv) == 1
    assert "hacen falta 63 vistas usables" in json.loads((pocas / "calculo.json").read_text(encoding="utf-8"))["error"]
    assert not (pocas / "intrinsecos_gs1_propuesta.yml").exists()
    # Una camara que no esta en la carpeta, y un tablero que no existe: no calcula.
    argv = _argv_doce(doce, pocas)
    argv[argv.index("--camara") + 1] = "gs2"
    assert cc.main(argv) == 1 and "no hay ninguna posicion de gs2" in json.loads((pocas / "calculo.json").read_text(encoding="utf-8"))["error"]
    argv = _argv_doce(doce, pocas)
    argv[argv.index("--tablero-charuco") + 1] = str(tmp_path / "no_existe.yaml")
    assert cc.main(argv) == 2
    # Una posicion cuya rafaga se movio se aparta con su motivo, y el calculo sigue con las demas.
    f = doce["carpeta"] / "T40_gs1_frames" / "frame_00001.png"
    img = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
    cv2.imwrite(str(f), np.roll(img, 2, axis=1))                             # el segundo frame, 2 px corrido
    con_una_menos = tmp_path / "menos"
    con_una_menos.mkdir()
    argv = _argv_doce(doce, con_una_menos)
    argv[argv.index("--min-vistas") + 1] = "8"
    assert cc.main(argv) == 0
    v = json.loads((con_una_menos / "calculo.json").read_text(encoding="utf-8"))["vistas"]
    assert v["total"] == 14 and v["detectadas"] == 13 and v["apartadas"][0]["nombre"] == "T40" and "no estaba quieto" in v["apartadas"][0]["motivo"]


@pytest.mark.parametrize("quitar,anadir", [
    ("--camara", []),                                                       # --desde-asistente sin --camara
    ("--tablero-charuco", []),                                              # charuco sin su tablero
    ("--desde-asistente", []),                                              # charuco sin el asistente (y --camara suelta)
    (None, ["--cols", "8"]),                                                # con charuco sobran
    (None, ["--rows", "6"]),
    (None, ["--square-mm", "26"]),
    (None, ["--detector", "sb"]),
    (None, ["--medidas-mm", "208,208,208,208,208"]),
    (None, ["--desde-vistas", "v"]),                                        # excluyentes
    (None, ["--vistas-dir", "v"]),
    (None, ["--cobertura-fina-min", "1.5"]),
    (None, ["--max-std-px", "0"]),
    (None, ["--min-esquinas", "3"]),
    ("--patron", ["--square-mm", "26", "--detector", "ambos"]),             # ajedrez desde el asistente: clasico o sb
    ("--patron", ["--detector", "sb"]),                                     # ajedrez sin --square-mm (y con --tablero-charuco)
])
def test_calibrate_camera_exige_argumentos_coherentes(sesion40, tmp_path, quitar, anadir) -> None:
    argv = _argv_calculo(sesion40, tmp_path)
    if quitar is not None:
        i = argv.index(quitar)
        del argv[i:i + 2]
    with pytest.raises(SystemExit) as exc:
        cc.main(argv + anadir)
    assert exc.value.code == 2 and not (tmp_path / "intrinsecos_gs1_propuesta.yml").exists()


def test_evaluar_criterio_con_los_opcionales() -> None:
    bien = {"n_vistas_usadas": 35, "rms_px": 0.2, "rms_control_px": 0.3, "std_intrinsecos": {"fx": 0.6, "fy": 0.6, "cx": 0.9, "cy": 1.0}}
    assert cc.evaluar_criterio(bien, 1.0) == [] and cc.evaluar_criterio(bien, 1.0, cc.CRITERIO, 0.9, 0.85, 1.0) == []
    assert cc.evaluar_criterio(bien, 1.0, cob_fina=0.5) == []                             # sin minimo, la fina no cuenta
    assert cc.evaluar_criterio(bien, 1.0, cob_fina=0.84, cob_fina_min=0.85) == ["cobertura fina 0.84 < 0.85"]
    assert cc.evaluar_criterio(bien, 1.0, cob_fina_min=0.85) == ["sin cobertura fina que comparar"]
    assert cc.evaluar_criterio(bien, 1.0, max_std_px=0.95) == ["desviacion de cy 1.00 px > 0.95"]
    sin = dict(bien, std_intrinsecos={"fx": 0.1, "fy": float("nan")})
    assert cc.evaluar_criterio(sin, 1.0, max_std_px=1.0) == ["desviacion de fy nan px > 1", "sin desviacion de cx", "sin desviacion de cy"]


# ----------------------------------------------------------------------------
# 5. comparar_intrinsecos
# ----------------------------------------------------------------------------

def test_comparar_intrinsecos(tmp_path) -> None:
    dist = np.array([0.017, 0.011, 0.0028, -0.0009, -0.107])
    viejo = {"K": ts.K_de(836.72, 836.0, 620.0, 400.0), "dist": dist, "std": {"fx": 1.091, "fy": 1.0, "cx": 0.9, "cy": 0.8}}
    mismo = cc.comparar_intrinsecos(viejo, viejo)
    assert all(f["dif"] == 0.0 for f in mismo["parametros"].values()) and list(mismo["parametros"]) == list(cc.PARAMETROS)
    assert all(mismo["parametros"][n]["sigmas"] == 0.0 for n in ("fx", "fy", "cx", "cy")) and mismo["max_sigmas"] == ["fx", 0.0]
    assert mismo["parametros"]["k1"]["sigmas"] is None and mismo["parametros"]["k1"]["viejo"] == 0.017       # sin desviacion: solo la diferencia
    # El de la sesion del 2026-11-11 (`p3_intrinsecos.out.txt`): fx 836.72 -> 847.80 con desviaciones 0.59 y 1.091.
    nuevo = {"K": ts.K_de(847.80, 836.0, 610.5, 392.7), "dist": dist, "std": {"fx": 0.59, "fy": 1.0, "cx": 0.9, "cy": 0.8, "k1": 0.01}}
    c = cc.comparar_intrinsecos(nuevo, viejo)
    fx = c["parametros"]["fx"]
    assert fx["dif"] == pytest.approx(11.08) and fx["sd_combinada"] == pytest.approx(1.2403, abs=1e-4) and fx["sigmas"] == pytest.approx(8.93, abs=0.01)
    assert round(fx["sigmas"], 1) == 8.9 and c["parametros"]["cx"]["sigmas"] == pytest.approx(-9.5 / np.hypot(0.9, 0.9))
    assert c["max_sigmas"][0] == "fx" and c["parametros"]["k1"]["sigmas"] is None                     # k1: solo uno trae desviacion
    assert cc.comparar_intrinsecos({"K": nuevo["K"], "dist": dist[:4]}, viejo)["parametros"]["k3"]["dif"] == pytest.approx(0.107)
    # Dos desviaciones a cero y una diferencia: sin sigmas (no un infinito en el reporte).
    cero = {"K": viejo["K"], "dist": dist, "std": {"fx": 0.0}}
    assert cc.comparar_intrinsecos({"K": nuevo["K"], "dist": dist, "std": {"fx": 0.0}}, cero)["parametros"]["fx"]["sigmas"] is None
    # Un .yml consigo mismo, leido del disco con sus desviaciones: 0 y 0 sigmas. El de gs1 de la meta 002 trae las de fx, fy, cx y cy.
    yml = tmp_path / "k.yml"
    cc.guardar_yml(yml, nuevo["K"], dist, 1280, 960, 0.2, 30, 8, 6, 26.0,
                   {"std_intrinsecos": {"fx": 0.59, "fy": 1.0, "cx": 0.9, "cy": 0.8}, "std_distorsion": {"k1": 0.01, "k2": 0.02}})
    leido = cc.leer_intrinsecos_con_std(yml)
    assert leido["std"] == {"fx": 0.59, "fy": 1.0, "cx": 0.9, "cy": 0.8, "k1": 0.01, "k2": 0.02} and np.array_equal(leido["K"], nuevo["K"])
    c2 = cc.comparar_intrinsecos(leido, leido)
    assert all(f["dif"] == 0.0 for f in c2["parametros"].values()) and c2["parametros"]["k2"]["sigmas"] == 0.0
    gs1 = cc.leer_intrinsecos_con_std(DATA_DIR / "intrinsecos_gs1_1280x960.yml")
    assert set(gs1["std"]) == {"fx", "fy", "cx", "cy"} and gs1["std"]["fx"] == pytest.approx(0.6747, abs=1e-3)
    with pytest.raises(FileNotFoundError):
        cc.leer_intrinsecos_con_std(tmp_path / "no.yml")


# ----------------------------------------------------------------------------
# 2. La variedad: por pose (P41) o por celdas nuevas de la rejilla fina
# ----------------------------------------------------------------------------

def _vista_falsa(M: np.ndarray, celdas: list[tuple[int, int]], n: int = 12) -> dict:
    """Una vista ya medida (trae `T`): `n` esquinas con ID repartidas por los centros de las `celdas` (ix, iy) de la 8 x 6."""
    esquinas = np.array([[(celdas[k % len(celdas)][0] + 0.3 + 0.03 * k) * 80.0, (celdas[k % len(celdas)][1] + 0.3 + 0.02 * k) * 80.0]
                         for k in range(n)])
    return {"esquinas": esquinas, "ids": np.arange(n), "T": M, "z_mm": float(M[2, 3]), "inclinacion_deg": 0.0,
            "centro_mm": [0.0, 0.0, float(M[2, 3])], "rms_pnp_px": 0.0}


def _quieto(a: csb.Asistente, t0: float, vista: dict | None, segundos: float = 1.3) -> tuple[float, list[str]]:
    salidas, t = [], t0
    while t <= t0 + segundos + 1e-9:
        salidas.append(a.observar(t, {CAM: vista}))
        t += 0.1
    return t, salidas


def test_la_variedad_por_celdas_nuevas() -> None:
    a = nuevo_asistente(40, 30)
    M = _T((0.0, 0.0, 0.0), (0.0, 0.0, 400.0))
    A = _vista_falsa(M, [(0, 0), (1, 0)])
    t, s = _quieto(a, 0.0, A)
    assert s.count("capturar") == 1 and s[-1] == "nada" and a.estado == "comprobando" and a.celdas_nuevas == 2
    a.aceptar("T01", {CAM: {k: v for k, v in A.items() if k != "esquinas"}}, esquinas=A["esquinas"])
    assert a.celdas_cubiertas == {(0, 0), (1, 0)} and a.cobertura_fina == pytest.approx(2 / 48) and a.cobertura_gruesa == pytest.approx(1 / 12)
    # La misma pose y las mismas celdas: repetida. No se toma.
    t, s = _quieto(a, t, _vista_falsa(M, [(0, 0), (1, 0)], n=10))
    assert "capturar" not in s and a.estado == "repetida" and a.celdas_nuevas == 0
    # La misma pose (ni 10 grados ni 40 mm) y UNA celda nueva: tampoco (hacen falta 2).
    t, s = _quieto(a, t, _vista_falsa(M, [(0, 0), (1, 0), (2, 0)]))
    assert "capturar" not in s and a.estado == "repetida" and a.celdas_nuevas == 1
    # La misma pose y DOS celdas nuevas: se toma.
    B = _vista_falsa(M, [(1, 0), (2, 0), (3, 0)])
    t, s = _quieto(a, t, B)
    assert s.count("capturar") == 1 and a.celdas_nuevas == 2
    a.aceptar("T02", {CAM: {k: v for k, v in B.items() if k != "esquinas"}}, esquinas=B["esquinas"])
    assert a.celdas_cubiertas == {(0, 0), (1, 0), (2, 0), (3, 0)} and a.cobertura_fina == pytest.approx(4 / 48) and len(a.tomadas) == 2
    # Sin celdas nuevas pero a 50 mm: distinta por P41, como en el modo estereo.
    lejos = _vista_falsa(_T((0.0, 0.0, 0.0), (50.0, 0.0, 400.0)), [(0, 0), (1, 0)])
    t, s = _quieto(a, t, lejos)
    assert s.count("capturar") == 1 and a.celdas_nuevas == 0
    a.rechazar("T03", "prueba")
    # Con min_celdas_nuevas = 0 las celdas no cuentan: la que anade dos y repite pose no se toma.
    b = nuevo_asistente(40, 30, min_celdas_nuevas=0)
    _t, s = _quieto(b, 0.0, A)
    b.aceptar("T01", {CAM: A}, esquinas=A["esquinas"])
    _t, s = _quieto(b, 2.0, B)
    assert "capturar" not in s and b.estado == "repetida" and b.celdas_nuevas == 2
    # Las esquinas que entran y salen (pocas comunes entre muestras): no esta quieto, no se toma.
    c = nuevo_asistente(40, 30)
    salidas = []
    for k in range(16):
        v = _vista_falsa(M, [(4, 3), (5, 3)])
        v["ids"] = np.arange(12) + (12 if k % 2 else 0)                     # ningun ID comun entre una muestra y la siguiente
        salidas.append(c.observar(0.1 * k, {CAM: v}))
    assert "capturar" not in salidas and c.estado == "moviendo"
    # Lo que no vale al construirlo (principio 7).
    for kw in (dict(camaras=("gs1", "gs2")), dict(celdas=(0, 6)), dict(min_celdas_nuevas=-1), dict(modo="otro"), dict(min_esquinas=3)):
        with pytest.raises((ValueError, KeyError)):
            nuevo_asistente(40, 30, **kw)
    with pytest.raises(ValueError):                                         # el tablero no es el de cols, rows y square_mm
        csb.Asistente(8, 5, 24.86, INTR, 10.0, 40.0, 1.0, 0.5, 40, 30, camaras=(CAM,), modo="intrinsecos", tablero=T)
    with pytest.raises(ValueError):                                         # sin el tamano de la imagen no hay rejilla
        csb.Asistente(COLS, ROWS, SQ, {CAM: {"K": K_APROX, "dist": np.zeros(5)}}, 10.0, 40.0, 1.0, 0.5, 40, 30,
                      camaras=(CAM,), modo="intrinsecos", tablero=T)


def test_quietud_con_ids() -> None:
    q = csb.Quietud(1.0, 0.5, 8, COLS, ROWS)
    base = np.array([[100.0 + 10 * k, 200.0 + 5 * k] for k in range(20)])
    for k in range(12):                                                     # 20 esquinas quietas, con IDs 0-19
        q.push_ids(0.1 * k, np.arange(20), base)
    assert q.quieto(1.1) and q.movimiento_px(1.1) == 0.0 and q.progreso(1.1) == 1.0
    q.push_ids(1.2, np.arange(5, 25), base + 0.0)                           # otras 20: las comunes (5-19) se movieron 50 px
    assert not q.quieto(1.2) and q.movimiento_px(1.2) > 10.0
    q.reset()
    for k in range(12):                                                     # el tablero entra en la imagen: cada vez mas esquinas
        q.push_ids(0.1 * k, np.arange(10 + k), base[:10 + k] if 10 + k <= 20 else np.vstack([base, base[:k - 10] + 300.0]))
    assert q.quieto(1.1)                                                    # las comunes a todas (0-9) no se movieron
    q.push_ids(1.2, np.arange(40, 44), base[:4])                            # sin 4 comunes con las anteriores: no se sabe
    assert not q.quieto(1.2) and q.movimiento_px(1.2) == float("inf")
    q.push_ids(1.3, None, None)
    assert q.movimiento_px(1.3) is None and not q.quieto(1.3)
    for ids, e in ((np.arange(3), base[:4]), (np.array([0, 48]), base[:2]), (np.array([1, 1]), base[:2])):
        with pytest.raises(ValueError):
            q.push_ids(2.0, ids, e)


# ----------------------------------------------------------------------------
# 3. Topes y salidas del bucle, y `main`
# ----------------------------------------------------------------------------

def test_el_tope_la_camara_que_se_para_y_q(tmp_path, poses40) -> None:
    A, B, C = (p["img"] for p in poses40[:3])
    # El tope de la sesion, sin llegar al minimo: 1, con su sesion.json.
    s = correr([("A", 1.3, A), ("nada", 5.0, None)], tmp_path / "tope", 5, 2, limite=3.0)
    assert s["r"]["fin"] == "tope" and s["r"]["codigo"] == 1 and s["r"]["tomadas"] == 1 and s["sesion"]["estado"] == "terminada"
    assert s["a"].estado == "sin_tablero" and s["pitidos"] == ["tomada"]
    # La camara deja de dar frames: 4 a los 5 s, con lo tomado hasta entonces guardado.
    s = correr([("A", 1.3, A), ("B", 1.3, B), ("C", 30.0, C)], tmp_path / "muere", 5, 2, muere_en=2.0)
    assert s["r"]["fin"] == "camara_estancada" and s["r"]["codigo"] == 4 and s["r"]["camara"] == CAM and s["r"]["tomadas"] == 1
    assert s["sesion"]["camara_estancada"]["camara"] == CAM and s["mundo"].t >= 2.0 + csb.ESTANCADA_S
    # q con el minimo: 0.
    s = correr([("A", 1.3, A), ("B", 1.3, B), ("fin", 0.3, None)], tmp_path / "q", 5, 2)
    assert s["r"]["fin"] == "q" and s["r"]["codigo"] == 0 and s["r"]["tomadas"] == 2 and s["r"]["posiciones"] == ["T01", "T02"]
    assert s["pitidos"] == ["tomada", "tomada"]


def test_la_ventana_de_una_camara(poses40) -> None:
    textos = [p.texto + p.cuna for p in csb.POSTURAS_INTR + (csb.POSTURA_LIBRE_INTR,)] + [t for t, _c in csb._TEXTO_ESTADO_INTR.values()]
    assert all(ord(ch) < 128 for t in textos for ch in t) and len({p.codigo for p in csb.POSTURAS_INTR}) == len(csb.POSTURAS_INTR) == 20
    assert (csb.MODOS, csb.OBJETIVO_INTR, csb.MINIMO_INTR, csb.CELDAS_FINAS, csb.MIN_CELDAS_NUEVAS, csb.COBERTURA_FINA_MIN) == \
        (("estereo", "intrinsecos"), 40, 30, (8, 6), 2, 0.85)                           # P52
    a = nuevo_asistente(40, 30)
    assert a.postura.codigo == "I01" and a.patron == "charuco" and a.ref == CAM and a.shape == SHAPE
    det = chb.detector(T)
    p = poses40[0]
    v = csb.vista_previa_charuco(p["img"], T, det, K_APROX, np.zeros(5), 1.0, 12)
    assert v["ids"].tolist() == p["ids"].tolist() and np.array_equal(v["esquinas"], p["esquinas"]) and v["T"].shape == (4, 4)
    assert max(csb.diferencia_vistas(v["T"], p["T"], COLS + 2, ROWS + 2, SQ)) < 20.0 and 250.0 < v["z_mm"] < 480.0
    assert csb.vista_previa_charuco(GRIS, T, det, K_APROX, np.zeros(5), 1.0, 12) is None
    for estado in csb._TEXTO_ESTADO_INTR:
        a.observar(0.0, {CAM: v})
        a.estado = estado
        img = csb.componer_ventana({CAM: p["img"]}, {CAM: v}, a, {CAM: 89.9, "ventana": 21.0}, 1234.0)
        assert img.shape == (600 + csb.ALTO_FRANJA, 1280, 3) and img.dtype == np.uint8
    # Con una vista tomada (sus celdas, en verde), sin tablero, sin frame y con todas las celdas cubiertas: no se rompe.
    a.aceptar("T01", {CAM: {k: x for k, x in v.items() if k != "esquinas"}}, esquinas=v["esquinas"])
    a.rechazar("T02", "el tablero se movio 0.61 px entre frames (tope 0.3): no estaba quieto")
    a.observar(1.0, {CAM: None})
    con = csb.componer_ventana({CAM: ts.a_bgr(p["img"])}, {CAM: None}, a, {}, -3.0)
    sin = csb.componer_ventana({CAM: None}, {CAM: None}, a, {}, 0.0)
    assert con.shape == sin.shape == (600 + csb.ALTO_FRANJA, 1280, 3)
    assert int((con[:600, :800] == (0, 200, 0)).all(axis=2).sum()) > 500        # hay celdas pintadas de verde
    a._fina = {(ix, iy) for ix in range(8) for iy in range(6)}
    assert csb.componer_ventana({CAM: p["img"]}, {CAM: v}, a, {}, 10.0).shape == con.shape
    # La celda libre mas cercana a un punto.
    assert csb.celda_libre_mas_cercana(set(), (8, 6), SHAPE, (10.0, 10.0)) == (0, 0)
    assert csb.celda_libre_mas_cercana({(0, 0)}, (8, 6), SHAPE, (10.0, 10.0)) in {(1, 0), (0, 1)}
    assert csb.celda_libre_mas_cercana({(ix, iy) for ix in range(8) for iy in range(6)}, (8, 6), SHAPE, (10.0, 10.0)) is None
    # La ventana del modo estereo, la de siempre, no pasa por aqui: un asistente estereo no tiene `tablero`.
    assert csb.Asistente(8, 5, 24.86, {"gs1": INTR[CAM], "gs2": INTR[CAM]}, 10.0, 40.0, 1.0, 0.5, 20, 18).modo == "estereo"


class CamFalsa:
    """Un backend falso: `read()` da el frame cada ~4 ms."""

    def __init__(self, frame) -> None:
        self.frame = frame
        self.abierta = self.cerrada = False
        self.tamano_real = (frame.shape[1], frame.shape[0])

    def open(self) -> None:
        self.abierta = True

    def read(self):
        time.sleep(0.004)
        return self.frame, None, time.time()

    def close(self) -> None:
        self.cerrada = True


def _argv_asistente(perfil, salida, *extra: str) -> list[str]:
    return ["--modo", "intrinsecos", "--config", f"{CAM}={perfil}", "--salida", str(salida), "--objetivo", "1", "--minimo", "1",
            "--frames-por-vista", "2", "--quieto-s", "0.4", "--escala-previa", "1.0", "--sin-pitido", "--timeout", "20", *extra]


def test_main_con_una_camara_falsa_charuco_y_ajedrez(tmp_path, poses40, monkeypatch, sin_ventanas, capsys) -> None:
    yml = tmp_path / "intrinsecos_aprox.yml"
    cc.guardar_yml(yml, K_APROX, np.zeros(5), 640, 480, 0.1, 20, COLS, ROWS, SQ, {"detector": "sb"})
    perfil = _perfil(tmp_path / "perfil_gs1.yaml", 640, 480, yml)
    tablero = _tablero_json(tmp_path / "tablero.json")
    cam = CamFalsa(ts.a_bgr(poses40[0]["img"]))
    monkeypatch.setattr(csb, "create_backend", lambda cfg: cam)
    rep = tmp_path / "rep.json"
    rc = csb.main(_argv_asistente(perfil, tmp_path / "datos", "--patron", "charuco", "--tablero-charuco", str(tablero), "--reporte", str(rep)))
    e = json.loads(rep.read_text(encoding="utf-8"))
    assert rc == 0, e
    assert cam.abierta and cam.cerrada and sin_ventanas["namedWindow"] == 1 and sin_ventanas["destroyAllWindows"] == 1
    assert e["modo"] == "sesion" and e["modo_asistente"] == "intrinsecos" and e["patron"] == "charuco" and set(e["perfiles"]) == {CAM}
    assert e["tablero_charuco"]["sha256"] == chb.sha256_archivo(tablero) and e["tablero"] == {"cols": 8, "rows": 6, "square_mm": 26.0}
    assert e["resultado"]["fin"] == "objetivo" and e["resultado"]["posiciones"] == ["T01"] and 0.0 < e["resultado"]["cobertura"]["fina"] < 1.0
    ses = json.loads((tmp_path / "datos" / "sesion.json").read_text(encoding="utf-8"))
    assert ses["meta"]["tablero_charuco"] == e["tablero_charuco"] and ses["modo"] == "intrinsecos" and ses["patron"] == "charuco"
    assert len(list((tmp_path / "datos" / "T01_gs1_frames").glob("frame_*.png"))) == 2
    salida = capsys.readouterr().out
    assert "python -m calibration.calibrate_camera --config" in salida and f'--desde-asistente "{tmp_path / "datos"}" --camara gs1' in salida
    assert "--patron charuco --tablero-charuco" in salida and "--cobertura-fina-min 0.85 --max-std-px 1.0" in salida
    assert "La camara abierta en" in salida and "Cobertura 8x6:" in salida
    # El mismo modo con el tablero de ajedrez (8 x 5 de 24.86 mm): la carpeta la lee `vistas_del_asistente`.
    K6 = ts.K_de(600.0, 600.0, 320.0, 240.0)
    rv = np.array([0.1, -0.15, 0.05])
    ajedrez = ts.renderizar_vista(K6, rv, ts.pose_hacia(K6, rv, (320.0, 240.0), 480.0, 8, 5, 24.86), 8, 5, 24.86, SHAPE)
    cam2 = CamFalsa(ts.a_bgr(ajedrez))
    monkeypatch.setattr(csb, "create_backend", lambda cfg: cam2)
    assert csb.main(_argv_asistente(perfil, tmp_path / "datos_aj", "--patron", "ajedrez", "--cols", "8", "--rows", "5",
                                    "--square-mm", "24.86")) == 0
    ses = json.loads((tmp_path / "datos_aj" / "sesion.json").read_text(encoding="utf-8"))
    assert ses["patron"] == "ajedrez" and ses["tablero"] == {"cols": 8, "rows": 5, "square_mm": 24.86} and ses["parametros"]["detector_final"] == "sb"
    v = cc.vistas_del_asistente(tmp_path / "datos_aj", CAM, 8, 5, "sb", 2, 0.3)
    assert v["nombres"] == ["T01"] and v["obj_points"] is None and v["img_points"][0].shape == (40, 1, 2) and v["shape"] == SHAPE
    assert "--patron ajedrez --cols 8 --rows 5 --square-mm 24.86 --detector sb" in capsys.readouterr().out
    with pytest.raises(ValueError):
        cc.vistas_del_asistente(tmp_path / "datos_aj", CAM, 8, 5, "sb", 2, 0.3, patron="charuco")      # sin tablero
    # Lo que no deja empezar: un tablero que no existe, o mas esquinas minimas de las que tiene.
    monkeypatch.setattr(csb, "create_backend", lambda cfg: (_ for _ in ()).throw(AssertionError("no tenia que abrir")))
    assert csb.main(_argv_asistente(perfil, tmp_path / "d3", "--patron", "charuco", "--tablero-charuco", str(tmp_path / "no.json"))) == 2
    assert csb.main(_argv_asistente(perfil, tmp_path / "d3", "--patron", "charuco", "--tablero-charuco", str(tablero),
                                    "--min-esquinas", "49")) == 2
    assert not (tmp_path / "d3").exists()


@pytest.mark.parametrize("argv", [
    ["--modo", "intrinsecos", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "gs2=b.yaml"],     # dos camaras
    ["--modo", "estereo", "--config", "gs1=a.yaml", "--cols", "8", "--rows", "5", "--square-mm", "24.86"],                      # una sola
    ["--modo", "intrinsecos", "--config", "gs1=a.yaml", "--cols", "8", "--rows", "5", "--square-mm", "24.86"],                  # sin --patron
    ["--modo", "intrinsecos", "--patron", "charuco", "--config", "gs1=a.yaml"],                                                  # sin tablero
    ["--modo", "intrinsecos", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "--cols", "8"],   # sobra
    ["--modo", "intrinsecos", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "--square-mm", "26"],
    ["--modo", "intrinsecos", "--patron", "ajedrez", "--config", "gs1=a.yaml", "--cols", "8", "--rows", "5"],                    # falta el lado
    ["--modo", "intrinsecos", "--patron", "ajedrez", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "--cols", "8",
     "--rows", "5", "--square-mm", "24.86"],
    ["--modo", "estereo", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "gs2=b.yaml"],        # fase 7f
    ["--modo", "intrinsecos", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs 1=a.yaml"],                  # nombre raro
    ["--modo", "intrinsecos", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "--celdas", "0", "6"],
    ["--modo", "intrinsecos", "--patron", "charuco", "--tablero-charuco", "t.json", "--config", "gs1=a.yaml", "--min-esquinas", "3"],
])
def test_main_del_asistente_exige_argumentos_coherentes(tmp_path, argv) -> None:
    with pytest.raises(SystemExit) as exc:
        csb.main(argv + ["--salida", str(tmp_path / "datos"), "--timeout", "20"])
    assert exc.value.code == 2 and not (tmp_path / "datos").exists()


def test_main_intrinsecos_no_mide_desde_vistas(tmp_path) -> None:
    with pytest.raises(SystemExit) as exc:
        csb.main(["--modo", "intrinsecos", "--patron", "ajedrez", "--config", "gs1=a.yaml", "--cols", "8", "--rows", "5",
                  "--square-mm", "24.86", "--medir-desde", str(tmp_path), "--timeout", "20"])
    assert exc.value.code == 2


# ----------------------------------------------------------------------------
# 10. calibrate_camera --patron charuco sobre 40 vistas parciales a 1280 x 960 con la K de gs1
# ----------------------------------------------------------------------------

def test_cuarenta_vistas_parciales_a_1280x960_con_la_k_de_gs1(tmp_path, espia_calibrar) -> None:
    gs1 = ce.leer_intrinsecos(DATA_DIR / "intrinsecos_gs1_1280x960.yml")
    K, dist, shape = gs1["K"], gs1["dist"], (1280, 960)
    t0 = time.perf_counter()
    poses = guion_de_poses(40, K, dist, shape, 8, 5, (330.0, 480.0), semilla=7, margen_px=90.0)
    carpeta = tmp_path / "datos"
    for k, p in enumerate(poses, start=1):
        d = carpeta / f"T{k:02d}_gs1_frames"
        d.mkdir(parents=True)
        cv2.imwrite(str(d / "frame_00000.png"), p["img"])
    parciales = sum(1 for p in poses if len(p["ids"]) < 48)
    assert parciales >= 12                                                  # el tablero llevado a los bordes: en parte fuera
    s = {"perfil": _perfil(tmp_path / "perfil_gs1.yaml", 1280, 960), "carpeta": carpeta, "tablero": _tablero_json(tmp_path / "tablero.json")}
    argv = _argv_calculo(s, tmp_path, "--cobertura-fina-min", "0.95", "--max-std-px", "1.0",
                         "--comparar-con", str(DATA_DIR / "intrinsecos_gs1_1280x960.yml"))
    argv[argv.index("--frames-por-vista") + 1] = "1"
    rc = cc.main(argv)
    e = json.loads((tmp_path / "calculo.json").read_text(encoding="utf-8"))
    res = e["resultado"]
    assert rc == 0, res["fallos"]
    Kc = np.asarray(res["K"])
    err = {n: abs(Kc[i, j] - K[i, j]) for n, (i, j) in {"fx": (0, 0), "fy": (1, 1), "cx": (0, 2), "cy": (1, 2)}.items()}
    assert max(err.values()) <= 0.5, err
    assert res["cobertura_fina"] >= 0.95 and res["cobertura"] == 1.0 and res["n_vistas_usadas"] == 35 and e["vistas"]["detectadas"] == 40
    assert np.abs(np.asarray(res["dist"]) - dist).max() < 0.02 and res["rms_px"] < 0.2
    assert _las_mismas_esquinas(espia_calibrar, poses)                      # las que leyo de la carpeta, bit a bit las de memoria
    # Frente al .yml de la meta 002 (la K con la que se renderizo): dentro de pocas sigmas combinadas.
    comp = res["comparacion"]
    assert comp["max_sigmas"] is not None and abs(comp["parametros"]["fx"]["dif"]) == pytest.approx(err["fx"])
    print(f"[fase 7d] calibrate_camera --patron charuco, 40 vistas a 1280x960 con la K de gs1 ({parciales} parciales, esquinas de "
          f"{min(len(p['ids']) for p in poses)} a 48): error fx {err['fx']:.3f}, fy {err['fy']:.3f}, cx {err['cx']:.3f}, cy {err['cy']:.3f} px; "
          f"RMS {res['rms_px']:.4f}, control {res['rms_control_px']:.4f}; cobertura 8x6 {res['cobertura_fina']:.2f}; desviaciones "
          f"{ {k: round(v, 3) for k, v in res['std_intrinsecos'].items()} }; max {comp['max_sigmas'][1]:+.1f} sigmas ({comp['max_sigmas'][0]}); "
          f"todo en {time.perf_counter() - t0:.1f} s")
