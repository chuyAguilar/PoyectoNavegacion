"""La referencia con su propio ID (meta 006, fase 7c; B55, P48 y P49). Sin camara.

B55: el autor tiene dos Marker0 con el ID 0, de 80 mm y de ~100 mm, y el tracker no puede
distinguirlos; con el de ~100 y el perfil en 80, todo sale a escala 0.81 sin aviso. La
referencia nueva es el ID 100 (P48) y el perfil lista solo ese (P49): el ID 0 sale de la
lista blanca. Aqui se comprueba:

1. Con un marker viejo (ID 0) y el nuevo (ID 100) en el mismo frame, el tracker manda un
   solo `ReferenceToTracker` por frame y es la pose del nuevo, con su tamano; con solo un
   ID 0 a la vista (el de 80 o el de ~100), no manda nada. Lo mismo con el perfil del
   repo tal como este: el marker de su lista y uno que no es de ella.
2. Las mismas esquinas con 80 mm y con el tamano nuevo dan la misma rotacion y una `t` en
   la razon de los tamanos: equivocarse de tamano es exactamente un error de escala.
3. `profiles.check_markers`: nombres o IDs repetidos, un `size_mm` que no vale, ninguna
   referencia o mas de una paran la carga con el nombre del perfil; los perfiles del repo
   y las copias congeladas pasan.
4. `replay_util.profile_diff` entre la copia congelada (el perfil con que se grabo
   `tests/data/marker0_<cam>.npz`: ID 0, 80 mm, `name: Marker0`) y el perfil del repo:
   solo difiere `markers`: el nombre (fase 7c2) y, cuando el autor mida, el ID y el tamano.
5. Los dos perfiles del repo llevan la misma entrada, y su ID y su tamano van juntos: el
   ID 0 con 80 mm (hasta que el autor mida la referencia nueva) o el ID 100 con ~100 mm.

Desde la fase 7c2 (P57) el `name` del perfil es `Reference` y se publica
`ReferenceToTracker`; las copias congeladas conservan `Marker0`. El nombre, sus alias y
la guarda del nombre de antes se prueban en `test_nombre_referencia.py`.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

import profiles
import tracker
from diagnostics import pose_log
from vision import pose
from vision.tracking import MarkerTracker

from . import replay_util
from .conftest import PROFILES_DIR, TESTS_DATA_DIR
from .synthetic import (DIST_SYN, K_SYN, REFERENCE_ID, REFERENCE_MM, FakeCamera, FakeSender, fake_time,
                        render_marker)

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"
GS2 = PROFILES_DIR / "tracker_config_gs2.yaml"
CAMERAS = ("gs1", "gs2")
ID_VIEJO, MM_VIEJO = 0, 80.0            # el Marker0 de siempre
MM_VIEJO_GRANDE = 98.6                  # el otro Marker0 con ID 0 (B55)
REF = profiles.REFERENCE_NAME           # "Reference": el nombre de la referencia en el perfil (P57)
DEVICE = f"{REF}ToTracker"              # lo que publica el tracker
ID_NUEVO, MM_NUEVO = 100, 98.6          # la referencia nueva (P48); su lado, un ejemplo hasta que se mida
N_FRAMES = 6
TOL_MM, TOL_DEG, TOL_REL = 1e-9, 1e-9, 1e-9
DE_FRENTE, TZ_DOS = (180.0, 0.0), 500.0
LISTA_DEL_REPO = object()               # `_perfil_syn` sin tocar `markers.list`


def _congelado(cam: str) -> Path:
    return TESTS_DATA_DIR / f"marker0_{cam}_perfil.yaml"


def _perfil_syn(tmp_path: Path, lista=LISTA_DEL_REPO, nombre: str = "perfil_syn.yaml") -> Path:
    """El perfil gs1 sin camara real (el backend se inyecta); con `lista`, esa `markers.list`."""
    gs1 = yaml.safe_load(GS1.read_text(encoding="utf-8"))
    markers = dict(gs1["markers"])
    if lista is not LISTA_DEL_REPO:
        markers["list"] = lista
    cfg = {"camera": {"camera_type": "webcam"}, "markers": markers,
           "igtlink": {"transforms_port": 18944, "video_port": 18945, "send_video": False},
           "filtering": gs1["filtering"], "debug": {"show_window": True, "verbose": False}}
    ruta = tmp_path / nombre
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return ruta


def _dos_markers(tz: float, dx: float, a: tuple[int, float], b: tuple[int, float]) -> np.ndarray:
    """Un frame con el marker `a` (id, mm) a la izquierda (x = -85 + dx mm) y el `b` a la derecha
    (x = 85 + dx), los dos a `tz` mm y de frente. El fondo de `render_marker` es gris 110.

    De frente y a ~500 mm porque ahi el detector de los perfiles lee bien los dos markers
    sinteticos en todos los frames (36 de 36 con x de 80 a 95 mm); con el giro por defecto de
    `render_marker`, a 450 mm, lee el ID 0 de 80 mm como 87 en parte de ellos (B39: pasa con
    imagenes sinteticas, no se ha visto con las reales)."""
    izq = render_marker(tz, -85.0 + dx, marker_id=a[0], size_mm=a[1], euler_xy=DE_FRENTE)
    der = render_marker(tz, 85.0 + dx, marker_id=b[0], size_mm=b[1], euler_xy=DE_FRENTE)
    assert not np.any((izq != 110) & (der != 110)), "los dos markers se pisan"
    return np.where(der != 110, der, izq)


def _correr(monkeypatch, frames: list, profile: Path, extra: list[str]):
    """`tracker.main` sin ventana, con camara, emisor y reloj falsos: (codigo, emisor)."""
    cam = FakeCamera(frames)
    FakeSender.instances = []
    monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: cam)
    monkeypatch.setattr(tracker, "IgtlSender", FakeSender)
    monkeypatch.setattr(tracker, "time", fake_time())

    def _sin_ventana(*_a, **_k):
        raise AssertionError("con --no-window no se abre ventana")
    monkeypatch.setattr(tracker.cv2, "imshow", _sin_ventana)
    rc = tracker.main(["--config", str(profile), "--no-window", *extra])
    assert cam.opened and cam.closed and len(FakeSender.instances) == 1
    return rc, FakeSender.instances[0]


def _casos() -> dict:
    """`lista`: la `markers.list` del perfil; `listado` e `intrusos`: (id, mm)."""
    otro = (ID_NUEVO, MM_NUEVO) if REFERENCE_ID == ID_VIEJO else (ID_VIEJO, MM_VIEJO)
    return {
        "id100": {"lista": [{"id": ID_NUEVO, "name": REF, "size_mm": MM_NUEVO}],
                  "listado": (ID_NUEVO, MM_NUEVO),
                  "intrusos": [(ID_VIEJO, MM_VIEJO), (ID_VIEJO, MM_VIEJO_GRANDE)]},
        "repo": {"lista": LISTA_DEL_REPO, "listado": (REFERENCE_ID, REFERENCE_MM), "intrusos": [otro]},
    }


# ----------------------------------------------------------------------------
# 1. El tracker sigue solo al marker de la lista
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("caso", ["id100", "repo"])
def test_con_el_viejo_y_el_nuevo_a_la_vista_se_envia_solo_el_de_la_lista(caso: str, tmp_path: Path, monkeypatch) -> None:
    c = _casos()[caso]
    mid, mm = c["listado"]
    profile = _perfil_syn(tmp_path, c["lista"])
    for k, intruso in enumerate(c["intrusos"]):
        frames = [_dos_markers(TZ_DOS + 0.3 * (i % 3), 0.2 * i, intruso, (mid, mm)) for i in range(N_FRAMES)]
        det = replay_util.build_detector(profile)
        for f in frames:                           # los dos se ven: un detector sin lista blanca lee los dos IDs
            _c, ids, _ = det.detectMarkers(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
            assert ids is not None and sorted(ids.flatten().tolist()) == sorted([intruso[0], mid])
        rec_path = tmp_path / f"dos_{k}.npz"
        rc, sender = _correr(monkeypatch, frames, profile, ["--record", str(rec_path)])
        assert rc == 0
        assert DEVICE == "ReferenceToTracker"
        assert [n for n, _ in sender.sent] == [DEVICE] * N_FRAMES                  # un solo envio por frame
        rec = pose_log.load_recording(rec_path)
        assert rec["metadata"]["whitelist"] == [mid]
        assert rec["marker_ids"].tolist() == [mid] * N_FRAMES                      # el intruso ni se graba
        assert rec["sent_name"].tolist() == [REF] * N_FRAMES
        assert rec["sent_frame"].tolist() == list(range(N_FRAMES))
        # La pose enviada es la del marker de la lista: la de `estimate_single_pose` de sus esquinas
        # con su tamano. El giro no se filtra; la posicion pasa por el 1-Euro (la primera sale tal cual).
        for i in range(N_FRAMES):
            M = rec["sent_M"][i]
            assert np.array_equal(M.astype(np.float32), sender.sent[i][1])
            rvec, tvec = pose.estimate_single_pose(rec["corners_2d"][i], mm, K_SYN, DIST_SYN)
            R, _ = cv2.Rodrigues(rvec)
            assert replay_util._angle_deg(R, M[:3, :3]) <= TOL_DEG
            if i == 0:
                assert float(np.linalg.norm(M[:3, 3] - tvec.flatten())) <= TOL_MM
            assert float(np.linalg.norm(M[:3, 3] - tvec.flatten())) < 2.0               # el filtro apenas la mueve
            assert abs(M[0, 3] - (85.0 + 0.2 * i)) < 2.0 and abs(M[2, 3] - TZ_DOS) < 3.0   # esta donde el de la lista
        # Y es lo que da el paso por frame del tracker sobre lo grabado, envio a envio.
        r = replay_util.compare_marker0(replay_util.run_marker0_replay(rec_path, profile, name=REF),
                                        replay_util.recorded_marker0(rec_path, name=REF))
        assert r["sends"] == N_FRAMES and r["frames_differ"] == 0
        assert r["max_diff_translation_mm"] <= TOL_MM and r["max_diff_rotation_deg"] <= TOL_DEG


@pytest.mark.parametrize("caso", ["id100", "repo"])
def test_con_solo_un_marker_que_no_es_de_la_lista_no_se_envia_nada(caso: str, tmp_path: Path, monkeypatch) -> None:
    c = _casos()[caso]
    profile = _perfil_syn(tmp_path, c["lista"])
    for k, (mid, mm) in enumerate(c["intrusos"]):
        frames = [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i, marker_id=mid, size_mm=mm)
                  for i in range(N_FRAMES)]
        # El marker se ve (un detector sin lista blanca lo lee en todos los frames): es la lista quien lo deja fuera.
        det = replay_util.build_detector(profile)
        for f in frames:
            _c, ids, _ = det.detectMarkers(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
            assert ids is not None and ids.flatten().tolist() == [mid]
        rec_path = tmp_path / f"solo_{k}.npz"
        rc, sender = _correr(monkeypatch, frames, profile, ["--record", str(rec_path)])
        assert rc == 0 and sender.sent == []                                       # 0 envios
        rec = pose_log.load_recording(rec_path)
        assert len(rec["timestamps"]) == N_FRAMES and len(rec["marker_ids"]) == 0 and len(rec["sent_frame"]) == 0


# ----------------------------------------------------------------------------
# 2. Otro tamano es exactamente otra escala
# ----------------------------------------------------------------------------

POSES = [((185.0, 5.0), (2.0, 5.0, 450.0)), ((170.0, 20.0), (-60.0, 30.0, 380.0)),
         ((200.0, -15.0), (40.0, -20.0, 520.0)), ((185.0, 35.0), (0.0, 0.0, 400.0))]


def _esquinas(mm: float, euler_xy: tuple[float, float], t: tuple[float, float, float]) -> np.ndarray:
    from scipy.spatial.transform import Rotation
    rvec = Rotation.from_euler("xy", list(euler_xy), degrees=True).as_rotvec()
    img, _ = cv2.projectPoints(pose.build_object_points(mm).astype(np.float64), rvec, np.array(t), K_SYN, DIST_SYN)
    return img.reshape(1, 4, 2).astype(np.float32)


@pytest.mark.parametrize("mm_nuevo", [MM_NUEVO, 100.0, 99.875])
@pytest.mark.parametrize("euler_xy,t", POSES)
def test_otro_tamano_con_las_mismas_esquinas_es_exactamente_otra_escala(euler_xy, t, mm_nuevo: float) -> None:
    esquinas = _esquinas(mm_nuevo, euler_xy, t)
    r80, t80 = pose.estimate_single_pose(esquinas, MM_VIEJO, K_SYN, DIST_SYN)
    rn, tn = pose.estimate_single_pose(esquinas, mm_nuevo, K_SYN, DIST_SYN)
    assert float(np.linalg.norm(tn.flatten() - np.array(t))) < 0.05              # la pose con que se proyecto
    # `build_object_points` guarda el medio lado en float32: la razon exacta es la de esos dos numeros.
    razon = float(np.float32(mm_nuevo / 2.0)) / float(np.float32(MM_VIEJO / 2.0))
    assert abs(razon / (mm_nuevo / MM_VIEJO) - 1.0) <= 1e-7
    assert float(np.linalg.norm(tn - razon * t80) / np.linalg.norm(tn)) <= TOL_REL
    R80, _ = cv2.Rodrigues(r80)
    Rn, _ = cv2.Rodrigues(rn)
    assert replay_util._angle_deg(R80, Rn) <= TOL_DEG
    # Lo mismo por el paso del tracker, sin filtro: dos perfiles que solo difieren en el size_mm.
    lista = lambda mm: {"dictionary": "DICT_ARUCO_MIP_36h12",                    # noqa: E731
                        "list": [{"id": ID_NUEVO, "name": REF, "size_mm": mm}]}
    (p80,) = MarkerTracker(lista(MM_VIEJO), {"enabled": False}).process_corners(
        [(ID_NUEVO, esquinas)], 0.0, K_SYN, DIST_SYN)
    (pn,) = MarkerTracker(lista(mm_nuevo), {"enabled": False}).process_corners(
        [(ID_NUEVO, esquinas)], 0.0, K_SYN, DIST_SYN)
    assert np.array_equal(p80.matrix[:3, :3], R80) and np.array_equal(pn.matrix[:3, :3], Rn)
    assert float(np.linalg.norm(pn.matrix[:3, 3] - razon * p80.matrix[:3, 3]) / np.linalg.norm(pn.matrix[:3, 3])) <= TOL_REL
    # B55 en numeros: con el marker de `mm_nuevo` delante y el perfil en 80, la distancia sale a 80 / mm_nuevo.
    assert p80.matrix[2, 3] == pytest.approx(t[2] * MM_VIEJO / mm_nuevo, abs=0.05)


# ----------------------------------------------------------------------------
# 3. check_markers
# ----------------------------------------------------------------------------

BUENA = {"id": ID_NUEVO, "name": REF, "size_mm": MM_NUEVO}
VIEJA = {"id": ID_VIEJO, "name": "Marker0", "size_mm": MM_VIEJO}         # la entrada de las copias congeladas


@pytest.mark.parametrize("lista,trozo", [
    ([BUENA, {"id": 0, "name": REF, "size_mm": 80.0}], "el nombre 'Reference' ya esta"),         # dos envios con el mismo nombre por frame
    ([VIEJA, {"id": ID_NUEVO, "name": "Marker0", "size_mm": MM_NUEVO}], "el nombre 'Marker0' ya esta"),
    ([BUENA, VIEJA], "hay mas de una referencia"),                                              # fase 7c2: la nueva y la de antes a la vez
    ([{"id": 7, "name": "Otro", "size_mm": 40.0}], "no hay referencia"),
    ([BUENA, {"id": ID_NUEVO, "name": "Otro", "size_mm": 80.0}], "el id 100 ya esta"),
    ([{**BUENA, "size_mm": 0.0}], "size_mm"), ([{**BUENA, "size_mm": -98.6}], "size_mm"),
    ([{**BUENA, "size_mm": "98.6"}], "size_mm"), ([{**BUENA, "size_mm": True}], "size_mm"),
    ([{**BUENA, "size_mm": float("nan")}], "size_mm"),
    ([{"id": ID_NUEVO, "name": REF}], "size_mm"),
    ([{**BUENA, "id": -1}], "id"), ([{**BUENA, "id": 1.5}], "id"), ([{**BUENA, "id": True}], "id"),
    ([{**BUENA, "id": "100"}], "id"), ([{"name": REF, "size_mm": 98.6}], "id"),
    ([{**BUENA, "name": ""}], "name"), ([{**BUENA, "name": 7}], "name"), ([{"id": 1, "size_mm": 98.6}], "name"),
    ([REF], "id, name y size_mm"),
    ([], "falta o esta vacia"), (None, "falta o esta vacia"), ({"id": 1}, "falta o esta vacia")])
def test_check_markers_para_con_el_nombre_del_perfil(lista, trozo: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=trozo) as e:
        profiles.check_markers({"markers": {"list": lista}}, "tracker_config_x.yaml")
    assert "perfil tracker_config_x.yaml" in str(e.value)
    # Y `load` lo llama: un perfil asi no se carga.
    ruta = _perfil_syn(tmp_path, lista, nombre="tracker_config_malo.yaml")
    with pytest.raises(ValueError, match="perfil tracker_config_malo.yaml"):
        profiles.load(ruta)


def test_check_markers_sin_la_seccion_markers(tmp_path: Path) -> None:
    for cfg in ({}, {"markers": None}, {"markers": {"dictionary": "DICT_ARUCO_MIP_36h12"}}, {"markers": []}):
        with pytest.raises(ValueError, match="perfil p.yaml: markers.list falta o esta vacia"):
            profiles.check_markers(cfg, "p.yaml")
    ruta = tmp_path / "tracker_config_sin.yaml"
    ruta.write_text("camera:\n  camera_type: webcam\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tracker_config_sin.yaml: markers.list"):
        profiles.load(ruta)


def test_el_tracker_no_arranca_con_dos_entradas_del_mismo_nombre(tmp_path: Path, monkeypatch) -> None:
    """P49 (c): con el viejo y el nuevo los dos como `Reference`, el tracker mandaria dos
    `ReferenceToTracker` por frame. No llega a crear la camara ni el emisor. Tampoco con
    la referencia nueva y la de antes (`Marker0`) a la vez (fase 7c2): serian dos
    transforms de referencia, uno con cada nombre."""
    creados: list[str] = []
    monkeypatch.setattr(tracker, "create_backend", lambda cfg_cam: creados.append("camara"))
    monkeypatch.setattr(tracker, "IgtlSender", lambda *a, **k: creados.append("emisor"))
    dos = [BUENA, {"id": ID_VIEJO, "name": REF, "size_mm": MM_VIEJO}]
    ruta = _perfil_syn(tmp_path, dos, nombre="tracker_config_dos.yaml")
    with pytest.raises(ValueError, match="tracker_config_dos.yaml.*el nombre 'Reference' ya esta"):
        tracker.main(["--config", str(ruta), "--no-window"])
    ruta = _perfil_syn(tmp_path, [BUENA, VIEJA], nombre="tracker_config_dos_nombres.yaml")
    with pytest.raises(ValueError, match="tracker_config_dos_nombres.yaml.*hay mas de una referencia"):
        tracker.main(["--config", str(ruta), "--no-window"])
    assert creados == []


def test_check_markers_acepta_lo_que_vale() -> None:
    profiles.check_markers({"markers": {"list": [BUENA]}}, "p.yaml")
    profiles.check_markers({"markers": {"list": [BUENA, {"id": 7, "name": "Otro", "size_mm": 40}]}}, "p.yaml")
    profiles.check_markers({"markers": {"list": [VIEJA]}}, "p.yaml")           # una copia congelada: la de antes, sola


@pytest.mark.parametrize("ruta", [GS1, GS2, _congelado("gs1"), _congelado("gs2")], ids=lambda p: p.name)
def test_los_perfiles_del_repo_y_las_copias_congeladas_pasan(ruta: Path) -> None:
    cfg = profiles.load(ruta)
    profiles.check_markers(cfg, ruta.name)
    esperado = "Marker0" if ruta.parent == TESTS_DATA_DIR else REF               # la copia congelada conserva su nombre
    assert [m["name"] for m in cfg["markers"]["list"]] == [esperado]             # un solo envio por frame


# ----------------------------------------------------------------------------
# 4. La copia congelada y el perfil del repo
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("cam", CAMERAS)
def test_la_copia_congelada_es_el_perfil_de_las_grabaciones(cam: str) -> None:
    p = replay_util.marker0_params(_congelado(cam))
    assert p["markers"] == [{"id": ID_VIEJO, "name": "Marker0", "size_mm": MM_VIEJO}]
    assert p["dictionary"] == "DICT_ARUCO_MIP_36h12"
    cfg = profiles.load(_congelado(cam))
    yml = Path(cfg["camera"]["calibration_file"])
    assert yml == (profiles.DATA_DIR / f"intrinsecos_{cam}_1280x960.yml").resolve()   # los de la meta 002
    assert replay_util.profile_diff(_congelado(cam), _congelado(cam)) == {}


@pytest.mark.parametrize("cam", CAMERAS)
def test_el_perfil_del_repo_solo_difiere_de_la_copia_en_markers(cam: str) -> None:
    """Desde la fase 7c2 difieren siempre en el nombre; el ID y el tamano, cuando el autor mida."""
    repo = PROFILES_DIR / f"tracker_config_{cam}.yaml"
    d = replay_util.profile_diff(_congelado(cam), repo)
    assert set(d) == {"markers"}, d                    # diccionario, detector, filtro e intrinsecos, iguales
    (antes,), (ahora,) = d["markers"]
    assert antes == VIEJA
    assert ahora == {"id": REFERENCE_ID, "name": REF, "size_mm": REFERENCE_MM}


def test_profile_diff_dice_cada_cosa_que_cambia(tmp_path: Path) -> None:
    texto = _congelado("gs1").read_text(encoding="utf-8")
    viejo = "    - id: 0\n      name: Marker0\n      size_mm: 80.0\n"
    assert texto.count(viejo) == 1

    def copia(nombre: str, a: str, b: str) -> Path:
        assert texto.count(a) == 1
        ruta = tmp_path / nombre
        ruta.write_text(texto.replace(a, b), encoding="utf-8")
        return ruta
    # Como quedara el perfil del repo con la referencia nueva: solo cambia `markers` (el ID y el tamano).
    nuevo = copia("nuevo.yaml", viejo, f"    - id: {ID_NUEVO}\n      name: {REF}\n      size_mm: {MM_NUEVO}\n")
    assert replay_util.profile_diff(_congelado("gs1"), nuevo) == {
        "markers": ([VIEJA], [{"id": ID_NUEVO, "name": REF, "size_mm": MM_NUEVO}])}
    detector = copia("detector.yaml", "    min_marker_perimeter_rate: 0.02\n", "    min_marker_perimeter_rate: 0.03\n")
    assert set(replay_util.profile_diff(_congelado("gs1"), detector)) == {"detector"}
    filtro = copia("filtro.yaml", "  min_cutoff: 2.0\n", "  min_cutoff: 1.0\n")
    assert set(replay_util.profile_diff(_congelado("gs1"), filtro)) == {"filtering"}
    yml = copia("yml.yaml", "  calibration_file: data/intrinsecos_gs1_1280x960.yml\n",
                "  calibration_file: data/intrinsecos_gs2_1280x960.yml\n")
    assert replay_util.profile_diff(_congelado("gs1"), yml) == {
        "calibration_file": ("data/intrinsecos_gs1_1280x960.yml", "data/intrinsecos_gs2_1280x960.yml")}
    assert set(replay_util.profile_diff(_congelado("gs1"), _congelado("gs2"))) == {"calibration_file"}


# ----------------------------------------------------------------------------
# 5. El ID y el tamano del perfil van juntos
# ----------------------------------------------------------------------------

def test_los_perfiles_del_repo_llevan_la_misma_entrada_y_su_id_va_con_su_tamano() -> None:
    listas = [yaml.safe_load(p.read_text(encoding="utf-8"))["markers"]["list"] for p in (GS1, GS2)]
    assert listas[0] == listas[1] and len(listas[0]) == 1
    m = listas[0][0]
    assert (m["id"], m["size_mm"]) == (REFERENCE_ID, REFERENCE_MM) and m["name"] == REF == "Reference"
    if m["id"] == ID_VIEJO:
        assert m["size_mm"] == MM_VIEJO, "el ID 0 es el marker de 80 mm (B55)"
    else:
        assert m["id"] == ID_NUEVO, "la referencia nueva es el ID 100 (P48)"
        assert 95.0 <= m["size_mm"] <= 105.0, "el lado medido de la referencia de ~100 mm"
