"""El nombre de la referencia y de su transform (meta 006, fase 7c2; P57 y P65). Sin camara.

Desde esta fase el marker de referencia se llama `Reference` en `markers.list` y el tracker
publica `ReferenceToTracker`; hasta entonces eran `Marker0` y `Marker0ToTracker`. Aqui:

1. `profiles.reference_marker`: da la entrada `Reference`; si no la hay, la que lleva el
   nombre de antes (`Marker0`: una grabacion vieja o la copia congelada de su perfil); con
   las dos o con ninguna, ValueError con los nombres que encontro. Los perfiles del repo
   llevan `Reference` y las copias congeladas, `Marker0`.
2. El nombre es lo unico que cambia en lo que el tracker manda: con la lista del perfil del
   repo y con la misma lista con el nombre de antes, las matrices son iguales byte a byte.
3. Quien buscaba «Marker0» por nombre lee igual una grabacion nueva y una vieja:
   `fusion.dataset.build_track` y `diagnostics.ruido_pose.serie_pose`.
4. La guarda: ningun `.py`, `.yaml`, `.yml`, `.md`, `.ps1`, `.sh` ni `.txt` de `codigo/`
   fuera de `historico/` nombra el transform de antes, salvo los de `HISTORIA` (cada uno
   con su porque), y `HISTORIA` no tiene archivos que ya no lo nombran. La busqueda es por
   texto y, en los `.py`, tambien por `ast` (un literal partido en dos lineas o sumado con
   `+` no sale en el texto). La guarda se prueba a si misma con un arbol falso.

`codigo/historico/` es archivo y no se mira. Las grabaciones (`.npz`, `.json`) conservan
el nombre con que se grabaron y tampoco se miran: el replay las compara con la copia
congelada de su perfil (`test_replay_marker0.py`).
"""
from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

import profiles
from diagnostics import pose_log, ruido_pose
from diagnostics.pose_log import PoseLog, load_recording
from fusion import dataset as ds
from fusion import geometry as g
from vision.pose import estimate_single_pose

from .conftest import CODIGO_DIR, PROFILES_DIR, TESTS_DATA_DIR
from .synthetic import REFERENCE_ID, REFERENCE_MM, render_marker
from .test_fusion_geometry import DIST, K, SIZE, marker_pose
from .test_referencia_id import _correr, _perfil_syn

NUEVO = "Reference"
VIEJO = "Marker0"
TRANSFORM_VIEJO = "Marker0ToTracker"
EXTENSIONES = (".py", ".yaml", ".yml", ".md", ".ps1", ".sh", ".txt")
CARPETAS_FUERA = ("historico", ".venv", "__pycache__", ".pytest_cache")

# Los archivos vivos que nombran el transform de antes, y por que (ruta desde codigo/, con /).
HISTORIA: dict[str, str] = {
    "slicer/receive_reference.py": "LEGACY_NAMES: comprueba que el nombre de antes no esta en la escena de Slicer",
    "slicer/README.md": "explica el cambio de nombre y la comprobacion de LEGACY_NAMES",
    "linux/README.md": "la nota de que los protocolos de la meta 007 se corrieron con el nombre de antes",
    "tests/test_nombre_referencia.py": "esta guarda",
    "tests/test_igtl_rate.py": "comprueba que LEGACY_NAMES del script de Slicer trae el nombre de antes",
    "tests/test_explain_pose.py": "el ejemplo sobre la grabacion vieja (copia congelada): el nombre que se envio entonces",
    "tests/test_transport.py": "un nombre de dispositivo cualquiera para IgtlSender",
    "tests/test_tegrastats_log.py": "las ordenes del protocolo P-7 de la meta 007, tal como se corrieron",
}


# ----------------------------------------------------------------------------
# 1. reference_marker
# ----------------------------------------------------------------------------

REF = {"id": 100, "name": NUEVO, "size_mm": 98.6}
ANTES = {"id": 0, "name": VIEJO, "size_mm": 80.0}
OTRO = {"id": 7, "name": "Otro", "size_mm": 40.0}


def test_los_nombres() -> None:
    assert profiles.REFERENCE_NAME == NUEVO and profiles.LEGACY_REFERENCE_NAMES == (VIEJO,)
    assert NUEVO not in profiles.LEGACY_REFERENCE_NAMES


@pytest.mark.parametrize("lista,esperada", [
    ([REF], REF), ([OTRO, REF], REF), ([ANTES], ANTES), ([ANTES, OTRO], ANTES),
    (["texto", REF, None], REF)])
def test_reference_marker_da_la_nueva_o_la_de_antes(lista, esperada) -> None:
    assert profiles.reference_marker(lista) is esperada


@pytest.mark.parametrize("lista,trozo", [
    ([REF, ANTES], "hay mas de una referencia"), ([ANTES, REF, OTRO], "hay mas de una referencia"),
    ([REF, dict(REF, id=101)], "hay mas de una referencia"), ([ANTES, dict(ANTES, id=1)], "hay mas de una referencia"),
    ([OTRO], "no hay referencia"), ([], "no hay referencia"), (None, "no hay referencia"),
    ([{"id": 0, "name": "marker0", "size_mm": 80.0}], "no hay referencia"),          # el nombre es exacto
    ([{"id": 0, "name": "ReferenceToTracker", "size_mm": 80.0}], "no hay referencia")])
def test_reference_marker_no_adivina(lista, trozo: str) -> None:
    with pytest.raises(ValueError, match=trozo) as e:
        profiles.reference_marker(lista)
    for m in lista or []:
        assert repr(m["name"]) in str(e.value)                       # dice lo que encontro
    assert "'Reference'" in str(e.value) and "'Marker0'" in str(e.value)


@pytest.mark.parametrize("cam", ["gs1", "gs2"])
def test_los_perfiles_del_repo_llevan_reference_y_las_copias_congeladas_marker0(cam: str) -> None:
    repo = profiles.load(PROFILES_DIR / f"tracker_config_{cam}.yaml")["markers"]["list"]
    ref = profiles.reference_marker(repo)
    assert ref["name"] == NUEVO and (ref["id"], ref["size_mm"]) == (REFERENCE_ID, REFERENCE_MM)
    assert [m["name"] for m in repo] == [NUEVO]                      # un solo transform: ReferenceToTracker
    copia = profiles.load(TESTS_DATA_DIR / f"marker0_{cam}_perfil.yaml")["markers"]["list"]
    assert profiles.reference_marker(copia) == ANTES and [m["name"] for m in copia] == [VIEJO]


# ----------------------------------------------------------------------------
# 2. El nombre es lo unico que cambia en lo que se manda
# ----------------------------------------------------------------------------

def test_con_el_nombre_nuevo_y_con_el_de_antes_las_matrices_son_las_mismas(tmp_path: Path, monkeypatch) -> None:
    """Criterio 1 de la fase: el perfil del repo manda solo `ReferenceToTracker`, un envio por
    frame, y la matriz es, byte a byte, la que mandaba con el nombre de antes."""
    frames = [render_marker(450.0 + 0.3 * (i % 3), 2.0 + 0.2 * i) for i in range(8)]
    repo = _perfil_syn(tmp_path, nombre="repo.yaml")                 # la `markers.list` del perfil gs1 tal cual
    antes = _perfil_syn(tmp_path, [{"id": REFERENCE_ID, "name": VIEJO, "size_mm": REFERENCE_MM}], nombre="antes.yaml")
    rc_a, s_a = _correr(monkeypatch, frames, repo, [])
    rc_b, s_b = _correr(monkeypatch, frames, antes, [])
    assert rc_a == rc_b == 0
    assert [n for n, _ in s_a.sent] == ["ReferenceToTracker"] * len(frames)
    assert [n for n, _ in s_b.sent] == [TRANSFORM_VIEJO] * len(frames)
    for (_, Ma), (_, Mb) in zip(s_a.sent, s_b.sent):
        assert Ma.dtype == Mb.dtype == np.float32 and Ma.tobytes() == Mb.tobytes()


# ----------------------------------------------------------------------------
# 3. Una grabacion nueva y una vieja se leen igual
# ----------------------------------------------------------------------------

def _grabacion(path: Path, nombres: list[str], enviado: str) -> Path:
    """Un `.npz` de `PoseLog` de 40 frames: `metadata.markers` con una entrada por cada nombre
    de `nombres` (IDs 0, 1...), las esquinas del ID 0 y su pose enviada como `enviado`."""
    log = PoseLog(path)
    t = 1000.0 + np.arange(40) / 60.0
    for i, ti in enumerate(t):
        T = marker_pose(x=20.0 + 0.05 * i)
        c = g.project_corners(T, SIZE, K, DIST).astype(np.float32)
        rvec, tvec = estimate_single_pose(c, SIZE, K, DIST)
        M = np.eye(4)
        M[:3, :3] = cv2.Rodrigues(rvec)[0]
        M[:3, 3] = tvec.ravel()
        log.add(float(ti), np.array([[0]]), (c.reshape(1, 4, 2),), [(enviado, M)], None)
    meta = {"markers": [{"id": k, "name": n, "size_mm": SIZE} for k, n in enumerate(nombres)],
            "t_start": 1.7e9, "t_loop_start": 1000.0, "filtering": {"enabled": False}}
    return log.save(K, DIST, meta)


def test_build_track_lee_igual_una_grabacion_nueva_y_una_vieja(tmp_path: Path) -> None:
    nueva = load_recording(_grabacion(tmp_path / "nueva.npz", [NUEVO], NUEVO))
    vieja = load_recording(_grabacion(tmp_path / "vieja.npz", [VIEJO], VIEJO))
    a, b = ds.build_track(nueva, "gs1"), ds.build_track(vieja, "gs1")
    assert a.valid.all() and len(a.t) == 40 and a.size_mm == b.size_mm == SIZE
    for campo in ("t", "T_raw", "T_alt", "corners", "reproj_px", "reproj_alt_px", "T_sent"):
        assert np.array_equal(getattr(a, campo), getattr(b, campo), equal_nan=True), campo
    assert np.isfinite(a.T_sent[:, 3, 3]).all()                      # lo enviado se encontro con los dos nombres
    # Con el nombre explicito, el de siempre; uno que no esta, ValueError.
    assert np.array_equal(ds.build_track(vieja, "gs1", name=VIEJO).T_raw, b.T_raw)
    with pytest.raises(ValueError, match="no tiene un marker"):
        ds.build_track(nueva, "gs1", name=VIEJO)
    # Sin referencia, o con la nueva y la de antes a la vez, no se adivina.
    dos = load_recording(_grabacion(tmp_path / "dos.npz", [NUEVO, VIEJO], NUEVO))
    with pytest.raises(ValueError, match="hay mas de una referencia"):
        ds.build_track(dos, "gs1")
    ninguna = load_recording(_grabacion(tmp_path / "ninguna.npz", ["Otro"], "Otro"))
    with pytest.raises(ValueError, match="no hay referencia"):
        ds.build_track(ninguna, "gs1")
    assert "MARKER_NAME" not in vars(ds)                             # ya no hay un nombre fijo


def test_ruido_pose_y_pose_log_con_los_dos_nombres(tmp_path: Path) -> None:
    nueva = _grabacion(tmp_path / "nueva.npz", [NUEVO], NUEVO)
    vieja = _grabacion(tmp_path / "vieja.npz", [VIEJO], VIEJO)
    a, b = ruido_pose.serie_pose(load_recording(nueva)), ruido_pose.serie_pose(load_recording(vieja))
    assert len(a["frames"]) == 40 and np.array_equal(a["xyz_crudo"], b["xyz_crudo"])
    assert np.isfinite(a["xyz_enviado"]).all() and np.array_equal(a["xyz_enviado"], b["xyz_enviado"])
    with pytest.raises(ValueError, match="no tiene un marker"):
        ruido_pose.serie_pose(load_recording(nueva), VIEJO)
    # pose_log.summarize pide el nombre siempre (principio 7): sin valor por defecto.
    assert inspect.signature(pose_log.summarize).parameters["name"].default is inspect.Parameter.empty
    s_n, s_v = pose_log.summarize(nueva, NUEVO), pose_log.summarize(vieja, VIEJO)
    assert s_n["fraction_with_pose"] == s_v["fraction_with_pose"] == 1.0
    assert s_n["mean_z_mm"] == s_v["mean_z_mm"]


# ----------------------------------------------------------------------------
# 4. La guarda del nombre de antes
# ----------------------------------------------------------------------------

def _plegar(node: ast.AST) -> str | None:
    """El texto de un literal de cadena, tambien si esta sumado con `+` o es una f-string
    (cada `{...}` cuenta como un corte); None si `node` no es una cadena."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _plegar(node.left), _plegar(node.right)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "\x00"
                       for v in node.values)
    return None


def nombra_el_transform_viejo(path: Path) -> bool:
    """True si el archivo nombra el transform de antes: en su texto o, si es un `.py`, en
    alguna cadena de su arbol sintactico (literales pegados, sumados o en f-string)."""
    texto = path.read_text(encoding="utf-8", errors="replace")
    if TRANSFORM_VIEJO in texto:
        return True
    if path.suffix != ".py":
        return False
    try:
        tree = ast.parse(texto)
    except SyntaxError:
        return False
    return any(TRANSFORM_VIEJO in (s or "") for s in map(_plegar, ast.walk(tree)))


def buscar(raiz: Path) -> set[str]:
    """Los archivos de `raiz` (por extension, fuera de `CARPETAS_FUERA`) que nombran el
    transform de antes, como rutas relativas con /."""
    raiz = Path(raiz)
    hallados: set[str] = set()
    for carpeta, subcarpetas, archivos in os.walk(raiz):
        subcarpetas[:] = [d for d in subcarpetas if d not in CARPETAS_FUERA]
        for nombre in archivos:
            p = Path(carpeta) / nombre
            if p.suffix.lower() in EXTENSIONES and nombra_el_transform_viejo(p):
                hallados.add(p.relative_to(raiz).as_posix())
    return hallados


def revisar(raiz: Path, historia: dict[str, str]) -> dict[str, list[str]]:
    """`nuevos`: lo nombran y no estan en `historia`; `sobran`: estan en `historia` y ya no lo nombran."""
    hallados = buscar(raiz)
    return {"nuevos": sorted(hallados - set(historia)), "sobran": sorted(set(historia) - hallados)}


def test_ningun_archivo_vivo_nombra_el_transform_de_antes() -> None:
    r = revisar(CODIGO_DIR, HISTORIA)
    assert r["nuevos"] == [], (f"{r['nuevos']} nombran {TRANSFORM_VIEJO}: el transform se llama ReferenceToTracker "
                               "(meta 006, fase 7c2). Si es historia a proposito, a HISTORIA con su porque.")
    assert r["sobran"] == [], f"{r['sobran']} estan en HISTORIA y ya no nombran {TRANSFORM_VIEJO}: quitarlos de la lista"
    assert all(isinstance(v, str) and v.strip() for v in HISTORIA.values())      # cada uno con su porque
    assert not any(k.startswith(("historico/", ".venv/")) for k in HISTORIA)


def test_lo_que_corre_no_esta_en_la_lista_de_historia() -> None:
    """La cadena y lo que el autor lanza en vivo no pueden estar en `HISTORIA`: solo el script
    de Slicer (que lo nombra para comprobar que no esta), documentacion y pruebas."""
    for ruta in HISTORIA:
        assert ruta.startswith(("tests/", "slicer/")) or ruta.endswith(".md"), ruta
    for vivo in ("tracker.py", "transport/igtl.py", "transport/__init__.py", "vision/tracking.py",
                 "profiles/__init__.py", "profiles/tracker_config_gs1.yaml", "profiles/tracker_config_gs2.yaml",
                 "diagnostics/igtl_rate.py", "gui/panel.py", "readme.md"):
        assert (CODIGO_DIR / vivo).is_file() and not nombra_el_transform_viejo(CODIGO_DIR / vivo), vivo


def _arbol_falso(raiz: Path) -> dict[str, str]:
    """Un `codigo/` de mentira limpio, con su lista de historia."""
    archivos = {
        "tracker.py": 'NOMBRE = "ReferenceToTracker"\n',
        "profiles/perfil.yaml": "markers:\n  list:\n    - {id: 100, name: Reference, size_mm: 98.6}\n",
        "LEEME.md": "El tracker publica `ReferenceToTracker`.\n",
        "slicer/receive_reference.py": f'LEGACY_NAMES = ("DodecaedroToTracker", "{TRANSFORM_VIEJO}")\n',
        "historico/viejo.py": f'NOMBRE = "{TRANSFORM_VIEJO}"\n',                 # archivo: no se mira
        ".venv/lib/x.py": f'NOMBRE = "{TRANSFORM_VIEJO}"\n',                     # el entorno: no se mira
        "tests/data/grabacion.json": f'{{"device": "{TRANSFORM_VIEJO}"}}\n',     # una grabacion: no se mira
    }
    for rel, texto in archivos.items():
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")
    return {"slicer/receive_reference.py": "comprueba que no esta en la escena"}


def test_la_guarda_se_pone_en_rojo_con_un_nombre_viejo_en_lo_vivo(tmp_path: Path) -> None:
    historia = _arbol_falso(tmp_path)
    assert revisar(tmp_path, historia) == {"nuevos": [], "sobran": []}
    # Un `.py`, un `.yaml` y un `.md` vivos que lo nombran: los tres salen.
    (tmp_path / "tracker.py").write_text(f'NOMBRE = "{TRANSFORM_VIEJO}"\n', encoding="utf-8")
    assert revisar(tmp_path, historia)["nuevos"] == ["tracker.py"]
    (tmp_path / "profiles" / "perfil.yaml").write_text(f"# publica {TRANSFORM_VIEJO}\n", encoding="utf-8")
    (tmp_path / "LEEME.md").write_text(f"`--device {TRANSFORM_VIEJO}`\n", encoding="utf-8")
    (tmp_path / "correr.ps1").write_text(f"--device {TRANSFORM_VIEJO}\n", encoding="utf-8")
    assert revisar(tmp_path, historia) == {
        "nuevos": ["LEEME.md", "correr.ps1", "profiles/perfil.yaml", "tracker.py"], "sobran": []}


def test_la_guarda_ve_por_ast_lo_que_el_texto_no(tmp_path: Path) -> None:
    historia = _arbol_falso(tmp_path)
    casos = {
        "pegado.py": 'NOMBRE = ("Marker0"\n          "ToTracker")\n',                # dos literales pegados, en dos lineas
        "sumado.py": 'NOMBRE = "Marker0" + "ToTracker"\n',
        "fstring.py": 'def f(puerto):\n    return f"{puerto}: Marker0" + "ToTracker"\n',
    }
    for nombre, texto in casos.items():
        assert TRANSFORM_VIEJO not in texto                                         # el texto solo no lo ve
        (tmp_path / "gui").mkdir(exist_ok=True)
        (tmp_path / "gui" / nombre).write_text(texto, encoding="utf-8")
    assert revisar(tmp_path, historia)["nuevos"] == ["gui/fstring.py", "gui/pegado.py", "gui/sumado.py"]
    # Lo que no es el nombre no salta: el nombre del marker solo, o el transform nuevo.
    (tmp_path / "gui" / "bien.py").write_text(
        'VIEJO = "Marker0"\nNUEVO = "Reference" + "ToTracker"\n\n\ndef f(n):\n    return f"{n}ToTracker"\n', encoding="utf-8")
    assert "gui/bien.py" not in revisar(tmp_path, historia)["nuevos"]


def test_la_lista_de_historia_no_guarda_archivos_que_ya_no_lo_nombran(tmp_path: Path) -> None:
    historia = _arbol_falso(tmp_path)
    historia["LEEME.md"] = "ya no lo nombra"
    historia["no_existe.py"] = "se borro"
    assert revisar(tmp_path, historia) == {"nuevos": [], "sobran": ["LEEME.md", "no_existe.py"]}
