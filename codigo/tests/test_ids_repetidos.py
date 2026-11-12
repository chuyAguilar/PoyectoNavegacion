"""Un ID repetido en un frame no se publica (meta 006, fase 7d2b; B39 opcion c; P70 b, P72 a). Sin camara.

Con una sola referencia fisica, dos detecciones de su ID en un frame son siempre un error y
no se sabe cual es la buena (B39: el tablero ChArUco dio un fantasma con el ID de la
referencia). Desde esta fase `vision.tracking.MarkerTracker` no da pose de un ID de
`markers.list` que sale dos o mas veces en un frame, no toca su 1-Euro y lo cuenta; los demas
IDs del frame salen como siempre. Aqui:

1. `ids_repetidos`, la funcion pura.
2. `process_corners`: el frame con el ID doble no da pose, cuenta y deja el 1-Euro como
   estaba; con otro marker en la lista, sale solo el otro (P72 a); con
   `descartar_repetidos=False`, las poses de antes del cambio (guardadas aqui, medidas con
   el codigo de antes); `reset()` pone los contadores a cero.
3. La equivalencia con el 1-Euro activo sobre una grabacion real (`tests/data/marker0_gs1.npz`
   con su copia congelada del perfil): con el ID duplicado en 50 frames, lo que se publica es,
   byte a byte, lo del replay sobre la misma grabacion con esos 50 frames sin detecciones. Y
   las grabaciones del repo no traen ningun doble: el contador da 0 en gs1 y en gs2.
4. El bucle de `tracker.main` con la camara falsa: 20 frames, 5 con dos copias del ID 100;
   la linea `[Repetidos]`, `repeated` en los metadatos y `pose_log.summarize`.
5. «No cambio» sin dobles: con hilo, con `--sync-capture` y con ventana, lo enviado es lo
   que da el paso de antes (`descartar_repetidos=False`) y la linea dice 0 frames.

Los frames sinteticos se eligen con el detector del perfil: con la tasa de hoy (0.60) el
detector lee algunos markers sinteticos con otro ID (B39), asi que cada frame se comprueba
antes de usarlo (uno solo: una lectura del ID; dos copias: dos lecturas).

En las pruebas del bucle con hilo de captura la camara falsa tarda mas por frame que en el
resto de la suite (B130: con la CPU cargada el bucle puede saltarse un frame).
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

import tracker
from diagnostics import pose_log
from vision.filtering import PositionFilter
from vision.pose import estimate_single_pose, rvec_tvec_to_matrix
from vision.tracking import MarkerTracker, ids_repetidos

from . import replay_util
from .conftest import CODIGO_DIR, PACKAGES, PROFILES_DIR, TESTS_DATA_DIR
from .synthetic import DIST_SYN, K_SYN, REFERENCE_ID, FakeCamera, FakeSender, fake_time, render_marker
from .test_referencia_id import _dos_markers, _perfil_syn

EN_LINUX = sys.platform.startswith("linux")
TOL = 1e-3 if EN_LINUX else 1e-9            # mm y adimensional; la del replay (P22 de la meta 007)
GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"

ID_REF, MM_REF = 100, 99.8                  # la referencia nueva y su lado medido (2026-11-11)
ID_OTRO, MM_OTRO = 7, 40.0
LISTA_REF = [{"id": ID_REF, "name": "Reference", "size_mm": MM_REF}]
MARKERS_FIJO = {"dictionary": "DICT_ARUCO_MIP_36h12", "list": LISTA_REF}
FILTRO_FIJO = {"enabled": True, "min_cutoff": 2.0, "beta": 0.05}

# Dos copias del mismo ID en un frame, en px: A y A corrida (200, 3). Fijas, no salen de un
# detector: las poses de abajo solo dependen de solvePnP.
ESQ_A = np.array([[150.25, 140.5], [262.75, 143.0], [259.5, 256.25], [147.0, 252.75]], dtype=np.float32)
ESQ_B = ESQ_A + np.array([200.0, 3.0], dtype=np.float32)
ESQ_C = ESQ_A * np.float32(0.5) + np.array([330.0, 260.0], dtype=np.float32)     # el otro marker
TIEMPOS = (1000.0, 1000.011)

# Lo que daba `process_corners` ANTES de esta fase (HEAD f6d7e1d, OpenCV 4.11.0, numpy 1.26.4,
# Windows) con MARKERS_FIJO, FILTRO_FIJO, K_SYN y DIST_SYN sobre [(100, ESQ_A), (100, ESQ_B)] en
# cada tiempo de TIEMPOS: dos poses por frame, y la segunda de cada frame pasa por el 1-Euro con
# el mismo `t` que la primera. Las 4x4 en float64, por filas, como `float.hex()`.
POSES_DE_ANTES = [
    ['0x1.ffba6a9b5196ap-1', '0x1.c4e61a3da87b6p-6', '-0x1.1a86cf669df1ep-6', '-0x1.97827e273020fp+6',
     '0x1.c28b531688456p-6', '-0x1.ffc9ad6d51448p-1', '-0x1.170ff6ca9722cp-7', '-0x1.2883abefd269ep+5',
     '-0x1.1e443ba796902p-6', '0x1.076033db12c8ep-7', '-0x1.ffe7c1c95f397p-1', '0x1.61c2e9617117ep+9',
     '0x0.0p+0', '0x0.0p+0', '0x0.0p+0', '0x1.0000000000000p+0'],
    ['0x1.ffca03ab810d4p-1', '0x1.af29afda8e00cp-6', '0x1.771e2ac211d2cp-7', '-0x1.b812fb55a5af9p+5',
     '0x1.aa880332b92e4p-6', '-0x1.ffad3e5e99f8cp-1', '0x1.8c262d0792ec9p-6', '-0x1.28219f1e01396p+5',
     '0x1.8bbb2f5083ffep-7', '-0x1.871a68d804509p-6', '-0x1.ffd116d23471ep-1', '0x1.61c4a759d577dp+9',
     '0x0.0p+0', '0x0.0p+0', '0x0.0p+0', '0x1.0000000000000p+0'],
    ['0x1.ffba6a9b5196ap-1', '0x1.c4e61a3da87b6p-6', '-0x1.1a86cf669df1ep-6', '-0x1.65a79a866af50p+6',
     '0x1.c28b531688456p-6', '-0x1.ffc9ad6d51448p-1', '-0x1.170ff6ca9722cp-7', '-0x1.28316d8ba24f0p+5',
     '-0x1.1e443ba796902p-6', '0x1.076033db12c8ep-7', '-0x1.ffe7c1c95f397p-1', '0x1.61c46ac0786bfp+9',
     '0x0.0p+0', '0x0.0p+0', '0x0.0p+0', '0x1.0000000000000p+0'],
    ['0x1.ffca03ab810d4p-1', '0x1.af29afda8e00cp-6', '0x1.771e2ac211d2cp-7', '-0x1.d7d5aeff5188bp+4',
     '0x1.aa880332b92e4p-6', '-0x1.ffad3e5e99f8cp-1', '0x1.8c262d0792ec9p-6', '-0x1.27b785ff782a4p+5',
     '0x1.8bbb2f5083ffep-7', '-0x1.871a68d804509p-6', '-0x1.ffd116d23471ep-1', '0x1.61c6561ddaac8p+9',
     '0x0.0p+0', '0x0.0p+0', '0x0.0p+0', '0x1.0000000000000p+0'],
]

N_DOBLES_REPLAY, SEMILLA_REPLAY, CORRIMIENTO_PX = 50, 20261111, 3.0
N_BUCLE, DOBLES_BUCLE = 20, (3, 4, 9, 14, 19)       # dos seguidos, sueltos y el ultimo frame
LINEA_PRIMERA = "[Repetidos] ID {mid} dos veces en un frame: no se publica ese frame (se cuenta; B39)"
LINEA_RESUMEN = "[Repetidos] {n} frames con un ID repetido, sin publicar ese ID (por ID: {por_id})"


def _a(esq: np.ndarray) -> np.ndarray:
    return esq.reshape(1, 4, 2)


def _doble() -> list:
    return [(ID_REF, _a(ESQ_A)), (ID_REF, _a(ESQ_B))]


def _estado(mt: MarkerTracker, mid: int) -> list:
    """El estado interno del 1-Euro de `mid`: (x_prev, dx_prev, t_prev) por eje."""
    return [(e.x_prev, e.dx_prev, e.t_prev) for e in mt.filters[mid].filters]


def _bytes(poses) -> bytes:
    return b"".join(np.ascontiguousarray(p.matrix, dtype=np.float64).tobytes() for p in poses)


# ----------------------------------------------------------------------------
# 1. ids_repetidos
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("ids, validos, esperado", [
    ([100, 100], {100}, {100}),
    ([100, 87, 100], {100}, {100}),
    ([87, 87], {100}, set()),
    ([], {100}, set()),
    ([100], {100}, set()),
    ([100, 100, 100], {100}, {100}),
    ([100, 7, 100, 7, 87, 87], {100, 7}, {100, 7}),
    ([100, 7], {100, 7}, set()),
    ([100, 100], set(), set()),
])
def test_ids_repetidos(ids, validos, esperado) -> None:
    assert ids_repetidos(ids, validos) == esperado
    assert ids_repetidos(iter(ids), validos) == esperado                 # un iterable de un solo uso
    assert ids_repetidos(np.asarray(ids, dtype=np.int32), validos) == esperado
    assert ids_repetidos(ids, {m: {} for m in validos}) == esperado      # `markers` del tracker: un dict por ID


def test_ids_repetidos_devuelve_enteros_de_python() -> None:
    rep = ids_repetidos(np.array([[100], [100]]).flatten(), {100})
    assert rep == {100} and all(type(m) is int for m in rep)


# ----------------------------------------------------------------------------
# 2. process_corners
# ----------------------------------------------------------------------------

def test_la_firma_y_que_el_tracker_no_lo_expone() -> None:
    p = inspect.signature(MarkerTracker.__init__).parameters["descartar_repetidos"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is True
    assert "descartar_repetidos" not in inspect.getsource(tracker)      # ninguna opcion de linea de ordenes
    # Nada vivo fuera de las pruebas pide el comportamiento de antes.
    vivos = [CODIGO_DIR / "tracker.py"] + [p for pkg in PACKAGES for p in (CODIGO_DIR / pkg).rglob("*.py")]
    assert len(vivos) > 30
    piden = [p.relative_to(CODIGO_DIR).as_posix() for p in vivos
             if "descartar_repetidos=False" in p.read_text(encoding="utf-8").replace(" ", "")
             and p.name != "tracking.py"]
    assert piden == []


def test_un_frame_con_el_id_doble_no_da_pose_cuenta_y_no_toca_el_filtro(capsys) -> None:
    mt = MarkerTracker(MARKERS_FIJO, FILTRO_FIJO)
    otro = MarkerTracker(MARKERS_FIJO, FILTRO_FIJO)                       # el que nunca ve el frame doble
    assert mt.descartar_repetidos is True and mt.frames_con_repetido == 0 and mt.repetidos_por_id == {}
    assert mt.resumen_repetidos() == {"frames": 0, "por_id": {}}

    # El doble en el primer frame: el filtro sigue sin estrenar.
    virgen = _estado(mt, ID_REF)
    assert mt.process_corners(_doble(), 999.9, K_SYN, DIST_SYN) == []
    assert _estado(mt, ID_REF) == virgen and all(e == (None, 0.0, None) for e in virgen)
    assert (mt.frames_con_repetido, mt.repetidos_por_id) == (1, {ID_REF: 1})

    (a,) = mt.process_corners([(ID_REF, _a(ESQ_A))], 1000.0, K_SYN, DIST_SYN)
    (a2,) = otro.process_corners([(ID_REF, _a(ESQ_A))], 1000.0, K_SYN, DIST_SYN)
    antes = _estado(mt, ID_REF)
    assert mt.process_corners(_doble(), 1000.011, K_SYN, DIST_SYN) == []
    assert mt.process_corners([(ID_REF, _a(ESQ_B)), (87, _a(ESQ_C)), (ID_REF, _a(ESQ_A)), (ID_REF, _a(ESQ_A))],
                              1000.022, K_SYN, DIST_SYN) == []           # tres veces, y un ID ajeno en medio
    assert _estado(mt, ID_REF) == antes == _estado(otro, ID_REF)
    assert (mt.frames_con_repetido, mt.repetidos_por_id) == (3, {ID_REF: 3})
    assert mt.resumen_repetidos() == {"frames": 3, "por_id": {str(ID_REF): 3}}

    # El frame siguiente sale como si los dobles no hubieran existido.
    (b,) = mt.process_corners([(ID_REF, _a(ESQ_B))], 1000.033, K_SYN, DIST_SYN)
    (b2,) = otro.process_corners([(ID_REF, _a(ESQ_B))], 1000.033, K_SYN, DIST_SYN)
    assert _bytes([a, b]) == _bytes([a2, b2]) and not np.array_equal(a.matrix, b.matrix)
    assert (otro.frames_con_repetido, otro.repetidos_por_id) == (0, {})

    # La linea de la primera vez sale una sola vez por ID.
    assert capsys.readouterr().out.count(LINEA_PRIMERA.format(mid=ID_REF)) == 1

    mt.reset()
    assert (mt.frames_con_repetido, mt.repetidos_por_id) == (0, {}) and _estado(mt, ID_REF) == virgen
    assert mt.resumen_repetidos() == {"frames": 0, "por_id": {}}


def test_lo_que_no_es_un_repetido_no_cuenta() -> None:
    mt = MarkerTracker(MARKERS_FIJO, FILTRO_FIJO)
    assert mt.process_corners([(87, _a(ESQ_A)), (87, _a(ESQ_B))], 1000.0, K_SYN, DIST_SYN) == []   # no es de la lista
    assert mt.process_corners([], 1000.01, K_SYN, DIST_SYN) == []
    assert len(mt.process_corners({ID_REF: _a(ESQ_A)}, 1000.02, K_SYN, DIST_SYN)) == 1           # un dict no repite
    assert len(mt.process_corners(iter([(87, _a(ESQ_B)), (ID_REF, _a(ESQ_A))]), 1000.03, K_SYN, DIST_SYN)) == 1
    assert len(mt.process_corners(zip([ID_REF], (_a(ESQ_B),)), 1000.04, K_SYN, DIST_SYN)) == 1    # como lo llama el bucle
    assert mt.resumen_repetidos() == {"frames": 0, "por_id": {}}


def test_con_otro_marker_en_la_lista_solo_deja_de_salir_el_repetido(capsys) -> None:
    """P72 (a): el ID repetido no se publica; los demas markers del frame, si."""
    markers = {"dictionary": "DICT_ARUCO_MIP_36h12",
               "list": LISTA_REF + [{"id": ID_OTRO, "name": "Otro", "size_mm": MM_OTRO}]}
    mt = MarkerTracker(markers, FILTRO_FIJO)
    solo = MarkerTracker(markers, FILTRO_FIJO)
    for k, t in enumerate(TIEMPOS):
        poses = mt.process_corners([(ID_REF, _a(ESQ_A)), (ID_OTRO, _a(ESQ_C + k)), (ID_REF, _a(ESQ_B))], t, K_SYN, DIST_SYN)
        (esperada,) = solo.process_corners([(ID_OTRO, _a(ESQ_C + k))], t, K_SYN, DIST_SYN)
        assert [p.name for p in poses] == ["Otro"] and _bytes(poses) == _bytes([esperada])
    assert mt.resumen_repetidos() == {"frames": 2, "por_id": {str(ID_REF): 2}}
    assert _estado(mt, ID_REF) == _estado(solo, ID_REF)                   # el 1-Euro de la referencia, sin estrenar

    # Los dos repetidos en el mismo frame: un frame mas, y cada ID con su cuenta.
    assert mt.process_corners([(ID_OTRO, _a(ESQ_C)), (ID_REF, _a(ESQ_A)), (ID_REF, _a(ESQ_B)), (ID_OTRO, _a(ESQ_C + 2))],
                              1000.05, K_SYN, DIST_SYN) == []
    assert mt.frames_con_repetido == 3 and mt.repetidos_por_id == {ID_REF: 3, ID_OTRO: 1}
    assert mt.resumen_repetidos() == {"frames": 3, "por_id": {str(ID_OTRO): 1, str(ID_REF): 3}}
    assert list(mt.resumen_repetidos()["por_id"]) == [str(ID_OTRO), str(ID_REF)]    # por ID, en orden
    out = capsys.readouterr().out
    assert out.count(LINEA_PRIMERA.format(mid=ID_REF)) == 1 and out.count(LINEA_PRIMERA.format(mid=ID_OTRO)) == 1

    # Solo el otro repetido: la referencia sale.
    poses = mt.process_corners([(ID_OTRO, _a(ESQ_C)), (ID_REF, _a(ESQ_A)), (ID_OTRO, _a(ESQ_C + 1))], 1000.06, K_SYN, DIST_SYN)
    assert [p.name for p in poses] == ["Reference"]


def _paso_de_antes(detecciones: list, tiempos, lista: list, filtro: dict) -> list[np.ndarray]:
    """El bucle de `process_corners` de antes de la fase, con las piezas de `vision/`: por cada
    deteccion, en su orden, la pose, el 1-Euro de su ID con el tiempo del frame y la 4x4."""
    info = {int(m["id"]): m for m in lista}
    filtros = {mid: PositionFilter(filtro["min_cutoff"], filtro["beta"]) for mid in info}
    salida = []
    for t in tiempos:
        for mid, esquinas in detecciones:
            rvec, tvec = estimate_single_pose(esquinas, info[mid]["size_mm"], K_SYN, DIST_SYN)
            salida.append(rvec_tvec_to_matrix(rvec, filtros[mid].filter(tvec, t)))
    return salida


def test_con_descartar_repetidos_false_salen_las_dos_poses_de_antes(capsys) -> None:
    """Criterio 2: el comportamiento de antes queda detras de `descartar_repetidos=False`. Byte a
    byte frente al paso de antes hecho con las piezas de `vision/`; y frente a las matrices
    guardadas (medidas con el codigo de antes del cambio), a 1e-9 (1e-3 en Linux, P22)."""
    mt = MarkerTracker(MARKERS_FIJO, FILTRO_FIJO, descartar_repetidos=False)
    poses = [p for t in TIEMPOS for p in mt.process_corners(_doble(), t, K_SYN, DIST_SYN)]
    assert len(poses) == 4 and {p.name for p in poses} == {"Reference"}
    esperadas = _paso_de_antes(_doble(), TIEMPOS, LISTA_REF, FILTRO_FIJO)
    assert _bytes(poses) == b"".join(M.tobytes() for M in esperadas)
    guardadas = np.array([[float.fromhex(x) for x in fila] for fila in POSES_DE_ANTES]).reshape(4, 4, 4)
    dif = float(np.max(np.abs(np.array([p.matrix for p in poses]) - guardadas)))
    assert dif <= TOL, dif
    assert np.max(np.abs(guardadas[1, :3, 3] - guardadas[0, :3, 3])) > 40.0     # son dos sitios distintos
    # Tambien cuenta, y lo dice de otra forma.
    assert mt.resumen_repetidos() == {"frames": 2, "por_id": {str(ID_REF): 2}}
    out = capsys.readouterr().out
    assert out.count(f"[Repetidos] ID {ID_REF} dos veces en un frame: se publican las dos") == 1
    assert "no se publica ese frame" not in out
    # Y el de ahora, con lo mismo, no da ninguna.
    con = MarkerTracker(MARKERS_FIJO, FILTRO_FIJO)
    assert [con.process_corners(_doble(), t, K_SYN, DIST_SYN) for t in TIEMPOS] == [[], []]


# ----------------------------------------------------------------------------
# 3. La equivalencia sobre una grabacion real, con el 1-Euro activo
# ----------------------------------------------------------------------------

def _grabacion(cam: str) -> tuple[Path, Path]:
    return TESTS_DATA_DIR / f"marker0_{cam}.npz", TESTS_DATA_DIR / f"marker0_{cam}_perfil.yaml"


def _variantes(origen: Path, carpeta: Path, elegidos: set[int], mid: int) -> tuple[Path, Path]:
    """Dos copias de la grabacion `origen`: en `dobles.npz`, los frames `elegidos` llevan la
    deteccion de `mid` dos veces (la copia, detras y corrida CORRIMIENTO_PX px); en
    `vacios.npz`, esos frames no llevan ninguna deteccion. Lo demas, igual."""
    with np.load(origen, allow_pickle=False) as d:
        tablas = {k: d[k] for k in d.files}
    off, ids, esquinas = tablas["frame_offsets"], tablas["marker_ids"], tablas["corners_2d"]
    dob: dict = {"ids": [], "esq": [], "off": [0]}
    vac: dict = {"ids": [], "esq": [], "off": [0]}
    for i in range(len(tablas["timestamps"])):
        a, b = int(off[i]), int(off[i + 1])
        del_frame = ids[a:b].tolist()
        dob["ids"] += del_frame
        dob["esq"] += [esquinas[j] for j in range(a, b)]
        if i in elegidos:
            dob["ids"].append(mid)
            dob["esq"].append(esquinas[a + del_frame.index(mid)] + np.float32(CORRIMIENTO_PX))
        else:
            vac["ids"] += del_frame
            vac["esq"] += [esquinas[j] for j in range(a, b)]
        dob["off"].append(len(dob["ids"]))
        vac["off"].append(len(vac["ids"]))
    rutas = []
    for nombre, v in (("dobles.npz", dob), ("vacios.npz", vac)):
        ruta = carpeta / nombre
        np.savez(ruta, **{**tablas, "frame_offsets": np.asarray(v["off"], dtype=np.int32),
                          "marker_ids": np.asarray(v["ids"], dtype=np.int32),
                          "corners_2d": np.asarray(v["esq"], dtype=np.float32).reshape(-1, 4, 2)})
        rutas.append(ruta)
    return rutas[0], rutas[1]


def _replay(dataset: Path, perfil: Path, nombre: str = "Marker0", **kw) -> tuple[dict, MarkerTracker]:
    """`replay_util.run_marker0_replay` devolviendo tambien el `MarkerTracker` (por sus contadores)."""
    rec = pose_log.load_recording(dataset)
    cfg = yaml.safe_load(perfil.read_text(encoding="utf-8"))
    mt = MarkerTracker(cfg["markers"], cfg.get("filtering"), **kw)
    off, ids, esquinas, ts = rec["frame_offsets"], rec["marker_ids"], rec["corners_2d"], rec["timestamps"]
    frames, matrices = [], []
    for i in range(len(ts)):
        dets = [(int(ids[j]), esquinas[j].reshape(1, 4, 2)) for j in range(int(off[i]), int(off[i + 1]))]
        for p in mt.process_corners(dets, float(ts[i]), rec["K"], rec["dist"]):
            if p.name == nombre:
                frames.append(i)
                matrices.append(p.matrix)
    return ({"sent_frame": np.asarray(frames, dtype=np.int32),
             "M": np.asarray(matrices, dtype=np.float64).reshape(-1, 4, 4)}, mt)


def _iguales_byte_a_byte(a: dict, b: dict) -> bool:
    return (np.array_equal(a["sent_frame"], b["sent_frame"]) and a["M"].dtype == b["M"].dtype == np.float64
            and a["M"].tobytes() == b["M"].tobytes())


def test_con_el_id_duplicado_en_50_frames_se_publica_lo_mismo_que_con_esos_frames_vacios(tmp_path: Path) -> None:
    """Criterio 3, con el 1-Euro del perfil activo."""
    origen, perfil = _grabacion("gs1")
    n = len(pose_log.load_recording(origen)["timestamps"])
    elegidos = set(int(i) for i in np.random.default_rng(SEMILLA_REPLAY).choice(n, N_DOBLES_REPLAY, replace=False))
    primero = min(elegidos)
    assert len(elegidos) == N_DOBLES_REPLAY and primero >= 5 and max(elegidos) < n
    dobles, vacios = _variantes(origen, tmp_path, elegidos, mid=0)
    rec_d = pose_log.load_recording(dobles)
    assert len(rec_d["marker_ids"]) == n + N_DOBLES_REPLAY and len(pose_log.load_recording(vacios)["marker_ids"]) == n - N_DOBLES_REPLAY

    filtrado, mt = _replay(dobles, perfil)
    referencia = replay_util.run_marker0_replay(vacios, perfil)
    assert _iguales_byte_a_byte(filtrado, referencia)
    assert _iguales_byte_a_byte(replay_util.run_marker0_replay(dobles, perfil), referencia)      # el replay hereda el filtro
    assert len(filtrado["sent_frame"]) == n - N_DOBLES_REPLAY
    assert set(filtrado["sent_frame"].tolist()).isdisjoint(elegidos)
    assert mt.resumen_repetidos() == {"frames": N_DOBLES_REPLAY, "por_id": {"0": N_DOBLES_REPLAY}}

    # Hasta el primer doble, lo de la grabacion original (lo que se envio en vivo).
    en_vivo = replay_util.recorded_marker0(origen)
    corte = lambda r: {"sent_frame": r["sent_frame"][r["sent_frame"] < primero], "M": r["M"][r["sent_frame"] < primero]}
    c = replay_util.compare_marker0(corte(filtrado), corte(en_vivo))
    assert c["sends"] == c["sends_reference"] == primero and c["frames_differ"] == 0, c
    assert c["max_diff_translation_mm"] <= TOL and c["max_diff_rotation_deg"] <= TOL, c
    # Y despues del primer doble ya no (el 1-Euro se salto un frame): la prueba no es vacia.
    assert not _iguales_byte_a_byte(filtrado, {"sent_frame": en_vivo["sent_frame"], "M": en_vivo["M"]})

    # Sin el filtro, esos 50 frames mandaban dos poses.
    sin, mt_sin = _replay(dobles, perfil, descartar_repetidos=False)
    assert len(sin["sent_frame"]) == n + N_DOBLES_REPLAY
    assert int(np.sum(np.bincount(sin["sent_frame"], minlength=n) == 2)) == N_DOBLES_REPLAY
    assert mt_sin.resumen_repetidos() == mt.resumen_repetidos()


@pytest.mark.parametrize("cam", ["gs1", "gs2"])
def test_las_grabaciones_del_repo_no_traen_dobles_y_el_replay_no_excluye_ningun_frame(cam: str) -> None:
    """Principio 6: el replay de la referencia sigue en 0.0 sin quitar frames; el contador da 0."""
    origen, perfil = _grabacion(cam)
    con, mt = _replay(origen, perfil)
    sin, mt_sin = _replay(origen, perfil, descartar_repetidos=False)
    assert mt.resumen_repetidos() == mt_sin.resumen_repetidos() == {"frames": 0, "por_id": {}}
    assert _iguales_byte_a_byte(con, sin) and _iguales_byte_a_byte(con, replay_util.run_marker0_replay(origen, perfil))
    assert len(con["sent_frame"]) == len(replay_util.recorded_marker0(origen)["sent_frame"]) > 900
    s = pose_log.summarize(origen, "Marker0")                             # una grabacion de antes: sin `repeated`
    assert s["repeated_tracker"] is None and s["frames_with_repeated_detection"] == 0
    assert s["frames_with_two_sends"] == 0 and s["fraction_with_pose"] == 1.0 and "sd_z_mm" in s
    assert pose_log.summarize(origen, "Reference")["frames_with_repeated_detection"] is None    # ese nombre no esta en sus metadatos


# ----------------------------------------------------------------------------
# pose_log.summarize con datos fijos
# ----------------------------------------------------------------------------

def test_summarize_cuenta_los_frames_con_el_id_de_la_referencia_repetido(tmp_path: Path) -> None:
    M = np.eye(4)
    M[:3, 3] = [10.0, -5.0, 700.0]
    por_frame = [[100], [100, 100], [100, 87, 100], [87, 87], [], [100, 100, 100], [100]]

    def grabar(nombre: str, meta: dict, como_antes: bool = False) -> Path:
        """`como_antes`: cada deteccion del 100 lleva su envio, como el tracker de antes del filtro."""
        log = pose_log.PoseLog(tmp_path / nombre)
        for i, ids in enumerate(por_frame):
            arr = np.array(ids, dtype=np.int32).reshape(-1, 1) if ids else None
            esquinas = tuple(_a(ESQ_A) + k for k in range(len(ids)))
            envios = ids.count(100) if como_antes else int(ids.count(100) == 1)
            log.add(1000.0 + 0.011 * i, arr, esquinas, [("Reference", M)] * envios, None)
        return log.save(K_SYN, DIST_SYN, meta)

    contado = {"frames": 3, "por_id": {"100": 3}}
    s = pose_log.summarize(grabar("a.npz", {"markers": LISTA_REF, "repeated": contado}), "Reference")
    assert s["frames_with_repeated_detection"] == 3 and s["repeated_tracker"] == contado
    assert s["frames_with_two_sends"] == 0 and s["sends_in_repeated_frames"] == 0
    assert s["frames_with_pose"] == 2 and s["frames"] == 7
    otro = pose_log.summarize(tmp_path / "a.npz", "Otro")                 # un nombre que no esta en los metadatos
    assert otro["frames_with_repeated_detection"] is None and otro["sends_in_repeated_frames"] is None
    assert otro["repeated_tracker"] == contado
    viejo = pose_log.summarize(grabar("b.npz", {"markers": [{"id": 87, "name": "Reference", "size_mm": 40.0}]}), "Reference")
    assert viejo["frames_with_repeated_detection"] == 1 and viejo["repeated_tracker"] is None    # [100, 87, 100] no; [87, 87] si
    assert viejo["sends_in_repeated_frames"] == 0
    sin_lista = pose_log.summarize(grabar("c.npz", {}), "Reference")
    assert sin_lista["frames_with_repeated_detection"] is None and sin_lista["repeated_tracker"] is None
    # Una grabacion del tracker de antes: los frames con el doble llevan sus envios, y se ve.
    antes = pose_log.summarize(grabar("d.npz", {"markers": LISTA_REF}, como_antes=True), "Reference")
    assert antes["frames_with_repeated_detection"] == 3 and antes["frames_with_two_sends"] == 3
    assert antes["sends_in_repeated_frames"] == 2 + 2 + 3 and antes["frames_with_pose"] == 5


def test_summarize_da_la_distancia_mayor_a_la_mediana(tmp_path: Path) -> None:
    """Con la referencia quieta, un fantasma publicado sale lejos de la mediana (sesion de la 7d2, P8)."""
    log = pose_log.PoseLog(tmp_path / "q.npz")
    sitios = [(10.0, -5.0, 700.0)] * 4 + [(13.0, -1.0, 712.0)] + [(10.0, -5.0, 700.5)] * 2
    for i, xyz in enumerate(sitios):
        M = np.eye(4)
        M[:3, 3] = xyz
        log.add(1000.0 + 0.011 * i, np.array([[100]]), (_a(ESQ_A),), [("Reference", M)], None)
    log.save(K_SYN, DIST_SYN, {"markers": LISTA_REF})
    s = pose_log.summarize(tmp_path / "q.npz", "Reference")
    assert s["max_dist_to_median_mm"] == pytest.approx(13.0)             # (3, 4, 12) desde la mediana (10, -5, 700)
    assert s["frames_with_repeated_detection"] == 0 and s["sends_in_repeated_frames"] == 0


# ----------------------------------------------------------------------------
# 4 y 5. El bucle de tracker.main con la camara falsa
# ----------------------------------------------------------------------------

def _correr_bucle(monkeypatch, frames: list, perfil: Path, extra: list[str], keys=None, loop: bool = False,
                  delay_s: float | None = None):
    """`tracker.main` con camara, emisor, reloj y ventana falsos: (codigo, emisor)."""
    cam = FakeCamera(frames, loop=loop, **({"delay_s": delay_s} if delay_s is not None else {}))
    FakeSender.instances = []
    FakeSender.connected = True
    monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: cam)
    monkeypatch.setattr(tracker, "IgtlSender", FakeSender)
    monkeypatch.setattr(tracker, "time", fake_time())
    teclas = iter(keys or [])
    monkeypatch.setattr(tracker.cv2, "imshow", lambda titulo, img: None)
    monkeypatch.setattr(tracker.cv2, "waitKey", lambda ms: next(teclas, -1))
    monkeypatch.setattr(tracker.cv2, "destroyAllWindows", lambda: None)
    rc = tracker.main(["--config", str(perfil), *extra])
    assert cam.opened and cam.closed and len(FakeSender.instances) == 1
    return rc, FakeSender.instances[0]


def _markers_gs1(lista: list) -> dict:
    markers = dict(yaml.safe_load(GS1.read_text(encoding="utf-8"))["markers"])
    markers["list"] = lista
    return markers


@pytest.fixture(scope="module")
def frames_bucle() -> list[np.ndarray]:
    """N_BUCLE frames BGR de 640x480 con la referencia ID 100: en los de DOBLES_BUCLE, dos copias
    lado a lado; en los demas, una. Cada uno, comprobado con el detector del perfil gs1 sin lista
    blanca: lee el 100 dos veces, o una, y ningun otro ID."""
    detector = MarkerTracker(_markers_gs1(LISTA_REF), None).detector

    def lee(bgr: np.ndarray) -> list[int]:
        ids = detector.detectMarkers(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))[1]
        return [] if ids is None else ids.flatten().tolist()

    unos, doses = [], []
    for k in range(60):
        if len(unos) < N_BUCLE - len(DOBLES_BUCLE):
            f = render_marker(500.0 + 0.5 * (k % 4), -40.0 + 2.0 * k, marker_id=ID_REF, size_mm=MM_REF, euler_xy=(180.0, 0.0))
            if lee(f) == [ID_REF]:
                unos.append(f)
        if len(doses) < len(DOBLES_BUCLE):
            f = _dos_markers(500.0, -8.0 + 1.0 * k, (ID_REF, MM_REF), (ID_REF, MM_REF))
            if lee(f) == [ID_REF, ID_REF]:
                doses.append(f)
    assert len(unos) == N_BUCLE - len(DOBLES_BUCLE) and len(doses) == len(DOBLES_BUCLE), (len(unos), len(doses))
    unos_it, doses_it = iter(unos), iter(doses)
    return [next(doses_it) if i in DOBLES_BUCLE else next(unos_it) for i in range(N_BUCLE)]


def test_el_bucle_no_envia_los_frames_con_el_id_doble_y_lo_cuenta(tmp_path: Path, monkeypatch, capsys, frames_bucle) -> None:
    """Criterio 4, con `--sync-capture` (el bucle lee cada frame de la camara falsa, sin saltos)."""
    perfil = _perfil_syn(tmp_path, LISTA_REF)
    npz = tmp_path / "bucle.npz"
    rc, emisor = _correr_bucle(monkeypatch, frames_bucle, perfil, ["--no-window", "--sync-capture", "--record", str(npz)],
                               delay_s=0.0)
    out = capsys.readouterr().out
    simples = [i for i in range(N_BUCLE) if i not in DOBLES_BUCLE]
    assert rc == 0 and [n for n, _ in emisor.sent] == ["ReferenceToTracker"] * len(simples)

    rec = pose_log.load_recording(npz)
    off = rec["frame_offsets"]
    por_frame = [rec["marker_ids"][off[i]:off[i + 1]].tolist() for i in range(N_BUCLE)]
    assert len(rec["timestamps"]) == N_BUCLE
    assert por_frame == [[ID_REF, ID_REF] if i in DOBLES_BUCLE else [ID_REF] for i in range(N_BUCLE)]   # se graba lo detectado
    assert rec["sent_frame"].tolist() == simples and rec["sent_name"].tolist() == ["Reference"] * len(simples)

    contado = {"frames": len(DOBLES_BUCLE), "por_id": {str(ID_REF): len(DOBLES_BUCLE)}}
    assert contado == {"frames": 5, "por_id": {"100": 5}}
    assert rec["metadata"]["repeated"] == contado
    resumen = LINEA_RESUMEN.format(n=5, por_id="{'100': 5}")
    assert out.count(resumen) == 1 and out.count("[Repetidos] 5 frames") == 1
    assert out.count(LINEA_PRIMERA.format(mid=ID_REF)) == 1
    assert out.index(LINEA_PRIMERA.format(mid=ID_REF)) < out.index(resumen) < out.index("[Captura] Camara") < out.index("[Salida limpia]")

    s = pose_log.summarize(npz, "Reference")
    assert s["frames_with_repeated_detection"] == 5 and s["frames_with_two_sends"] == 0 and s["sends_in_repeated_frames"] == 0
    assert s["repeated_tracker"] == rec["metadata"]["repeated"] and s["frames_with_pose"] == len(simples)

    # Lo enviado es lo que da el paso por frame sobre los 15 frames de una copia, con sus tiempos:
    # como si los 5 del doble no hubieran tenido detecciones.
    cfg = yaml.safe_load(perfil.read_text(encoding="utf-8"))
    mt = MarkerTracker(cfg["markers"], cfg["filtering"])
    for i, (_nombre, M) in zip(simples, emisor.sent):
        (p,) = mt.process(cv2.cvtColor(frames_bucle[i], cv2.COLOR_BGR2GRAY), float(rec["timestamps"][i]), K_SYN, DIST_SYN)
        assert M.dtype == np.float32 and M.tobytes() == p.matrix.astype(np.float32).tobytes()
    assert mt.frames_con_repetido == 0


def test_el_bucle_con_hilo_de_captura_tampoco_envia_los_dobles(tmp_path: Path, monkeypatch, capsys, frames_bucle) -> None:
    """Lo mismo con la captura por defecto (el hilo con el ultimo frame). Se comprueba frame a frame
    de lo grabado, asi que vale aunque el bucle se salte alguno (B130)."""
    npz = tmp_path / "hilo.npz"
    rc, emisor = _correr_bucle(monkeypatch, frames_bucle, _perfil_syn(tmp_path, LISTA_REF), ["--no-window", "--record", str(npz)],
                               delay_s=0.04)
    out = capsys.readouterr().out
    rec = pose_log.load_recording(npz)
    off = rec["frame_offsets"]
    n = len(rec["timestamps"])
    dobles = [i for i in range(n) if rec["marker_ids"][off[i]:off[i + 1]].tolist() == [ID_REF, ID_REF]]
    simples = [i for i in range(n) if rec["marker_ids"][off[i]:off[i + 1]].tolist() == [ID_REF]]
    assert rc == 0 and n >= N_BUCLE - 4 and len(dobles) + len(simples) == n and len(dobles) >= 2
    assert rec["sent_frame"].tolist() == simples and len(emisor.sent) == len(simples)
    assert rec["metadata"]["repeated"] == {"frames": len(dobles), "por_id": {str(ID_REF): len(dobles)}}
    assert LINEA_RESUMEN.format(n=len(dobles), por_id="{'100': %d}" % len(dobles)) in out
    s = pose_log.summarize(npz, "Reference")
    assert s["frames_with_repeated_detection"] == len(dobles) and s["frames_with_two_sends"] == 0
    assert s["sends_in_repeated_frames"] == 0


@pytest.mark.parametrize("modo", ["hilo", "sync", "ventana"])
def test_sin_dobles_el_bucle_envia_lo_de_antes_y_dice_cero(modo: str, tmp_path: Path, monkeypatch, capsys) -> None:
    """Criterio 5, «no cambio»: las tres corridas del criterio 1 de la fase 7c2 (8 frames con hilo, 8 con
    `--sync-capture`, 6 con ventana), con el perfil del repo. Lo enviado es, byte a byte, lo que da el
    paso de antes (`descartar_repetidos=False`) con los mismos frames y tiempos. El sha256 de estas
    matrices antes y despues del cambio se midio fuera de la suite (nota de la fase)."""
    frames = [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i) for i in range(8)]
    perfil = _perfil_syn(tmp_path)                                         # la `markers.list` del perfil gs1 tal cual
    npz = tmp_path / f"{modo}.npz"
    opciones = {"hilo": (["--no-window"], {"delay_s": 0.05}),
                "sync": (["--no-window", "--sync-capture"], {"delay_s": 0.0}),
                "ventana": ([], {"keys": [-1, -1, -1, -1, -1, ord("q")], "loop": True, "delay_s": 0.05})}[modo]
    rc, emisor = _correr_bucle(monkeypatch, frames, perfil, [*opciones[0], "--record", str(npz)], **opciones[1])
    out = capsys.readouterr().out
    esperados = 6 if modo == "ventana" else 8
    assert rc == 0 and [n for n, _ in emisor.sent] == ["ReferenceToTracker"] * esperados
    assert out.count(LINEA_RESUMEN.format(n=0, por_id="{}")) == 1 and "dos veces en un frame" not in out
    rec = pose_log.load_recording(npz)
    assert rec["metadata"]["repeated"] == {"frames": 0, "por_id": {}} and len(rec["timestamps"]) == esperados
    cfg = yaml.safe_load(perfil.read_text(encoding="utf-8"))
    antes = MarkerTracker(cfg["markers"], cfg["filtering"], descartar_repetidos=False)
    for i, (t, (_nombre, M)) in enumerate(zip(rec["timestamps"], emisor.sent)):
        (p,) = antes.process(cv2.cvtColor(frames[i % 8], cv2.COLOR_BGR2GRAY), float(t), K_SYN, DIST_SYN)
        assert p.id == REFERENCE_ID and M.tobytes() == p.matrix.astype(np.float32).tobytes()
    s = pose_log.summarize(npz, "Reference")
    assert s["frames_with_repeated_detection"] == 0 and s["repeated_tracker"] == {"frames": 0, "por_id": {}}
