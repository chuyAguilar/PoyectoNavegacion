"""Los semaforos del panel (`gui/status.py`, era `gui/estado.py`) con los perfiles gs1 y gs2.

Meta 003, fase 2 (ADR-026): los perfiles no traen rigid_bodies. Fase 3 (ADR-027): se van los
semaforos de geometria y de punta (el dodecaedro y la punta se archivaron), los perfiles se listan
de codigo/profiles/ y sus rutas son relativas a codigo/; un perfil con rigid_bodies o de la Femto
(archivada) queda en ROJO.

Sin Qt y sin camara: `status` lee el YAML y el disco; el chequeo del puerto 18944 solo hace
bind/close.
"""
from __future__ import annotations

import yaml

from gui import status as estado

from .conftest import CODIGO_DIR, HISTORICO_DIR, PROFILES_DIR

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"
GS2 = PROFILES_DIR / "tracker_config_gs2.yaml"
FEMTO = HISTORICO_DIR / "iter4" / "femto" / "tracker_config.yaml"


def _por_clave(chequeos) -> dict:
    return {c.clave: c for c in chequeos}


def test_lista_los_perfiles_de_profiles() -> None:
    assert [p.name for p in estado.listar_perfiles()] == ["tracker_config_gs1.yaml", "tracker_config_gs2.yaml"]
    assert estado.RAIZ_CODIGO == CODIGO_DIR and estado.DIR_PERFILES == PROFILES_DIR


def test_config_sin_rigid_bodies_es_verde() -> None:
    for perfil in (GS1, GS2):
        chk, cfg = estado.chequear_config(perfil)
        assert chk.estado == estado.VERDE, chk
        assert "rigid_bodies" not in cfg and "rigid_bodies_quality" not in cfg


def test_config_sigue_exigiendo_camera_markers_igtlink(tmp_path) -> None:
    ruta = tmp_path / "tracker_config_roto.yaml"
    ruta.write_text(yaml.safe_dump({"camera": {"camera_type": "webcam"}, "igtlink": {}}), encoding="utf-8")
    chk, _cfg = estado.chequear_config(ruta)
    assert chk.estado == estado.ROJO and "markers" in chk.detalle and "rigid_bodies" not in chk.detalle


def test_config_con_rigid_bodies_o_femto_es_rojo(tmp_path) -> None:
    """El dodecaedro y la Femto estan archivados: su perfil no deja arrancar el tracker."""
    chk, cfg = estado.chequear_config(FEMTO)
    assert chk.estado == estado.ROJO and "archivada" in chk.detalle, chk
    gs1 = yaml.safe_load(GS1.read_text(encoding="utf-8"))
    gs1["rigid_bodies"] = [{"name": "Dodecaedro", "geometry_file": "data/x.txt"}]
    ruta = tmp_path / "tracker_config_con_rb.yaml"
    ruta.write_text(yaml.safe_dump(gs1), encoding="utf-8")
    chk, _cfg = estado.chequear_config(ruta)
    assert chk.estado == estado.ROJO and "rigid_bodies" in chk.detalle, chk


def test_sin_semaforos_de_geometria_ni_punta() -> None:
    chequeos, _cfg = estado.evaluar_todo(GS1)
    assert [c.clave for c in chequeos] == ["entorno", "config", "intrinsecos", "puerto", "camara"]
    assert not hasattr(estado, "chequear_geometria") and not hasattr(estado, "chequear_punta")


def test_intrinsecos_relativos_a_codigo() -> None:
    """calibration_file: data/intrinsecos_gs1_1280x960.yml se lee de codigo/data/, sin importar el CWD."""
    cfg = estado.cargar_perfil(GS1)
    chk = estado.chequear_intrinsecos(cfg, GS1)
    assert chk.estado == estado.VERDE and chk.detalle == "intrinsecos_gs1_1280x960.yml", chk
    cfg["camera"]["calibration_file"] = "data/no_existe.yml"
    chk = estado.chequear_intrinsecos(cfg, GS1)
    assert chk.estado == estado.ROJO and "no existe" in chk.detalle


def test_apto_para_tracker_con_gs1_y_gs2() -> None:
    """Lo que el panel decide para «Arrancar tracker»: con los perfiles reales gs1 y gs2,
    entorno + config + intrinsecos + puerto en VERDE bastan."""
    for perfil in (GS1, GS2):
        chequeos, _cfg = estado.evaluar_todo(perfil)
        por = _por_clave(chequeos)
        ok, malos = estado.apto_para_tracker(chequeos)
        if por["puerto"].estado != estado.VERDE:   # un tracker vivo en la maquina: no es del perfil
            assert malos == ["puerto"], malos
        else:
            assert ok and malos == [], (perfil.name, [(c.clave, c.estado, c.detalle) for c in chequeos])


def test_apto_para_tracker_bloquea_por_cada_requerido() -> None:
    """Entorno, config, intrinsecos o puerto en ROJO bloquean; la camara GRIS no."""
    base = [estado.Chequeo("entorno", "Entorno", estado.VERDE, ""),
            estado.Chequeo("config", "Config", estado.VERDE, ""),
            estado.Chequeo("intrinsecos", "Intrinsecos", estado.VERDE, ""),
            estado.Chequeo("puerto", "Puerto", estado.VERDE, ""),
            estado.Chequeo("camara", "Camara", estado.GRIS, "")]
    assert estado.apto_para_tracker(base) == (True, [])
    for clave in ("entorno", "config", "intrinsecos", "puerto"):
        rotos = [estado.Chequeo(c.clave, c.titulo, estado.ROJO, "x") if c.clave == clave else c for c in base]
        assert estado.apto_para_tracker(rotos) == (False, [clave])
