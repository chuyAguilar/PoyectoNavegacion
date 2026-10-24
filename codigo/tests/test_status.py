"""Los semaforos del panel (`gui/estado.py`; `gui/status.py` desde la fase 3)
con un perfil sin rigid_bodies (meta 003, fase 2, ADR-026).

Sin Qt y sin camara: `estado` lee el YAML y el disco; el chequeo del puerto
18944 solo hace bind/close.
"""
from __future__ import annotations

import yaml

import estado

from .conftest import ITER4_DIR

GS1 = ITER4_DIR / "tracker_config_gs1.yaml"
GS2 = ITER4_DIR / "tracker_config_gs2.yaml"
FEMTO = ITER4_DIR / "tracker_config.yaml"


def _por_clave(chequeos) -> dict:
    return {c.clave: c for c in chequeos}


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


def test_geometria_y_punta_no_aplican_sin_rigid_bodies() -> None:
    cfg = estado.cargar_perfil(GS1)
    geo = estado.chequear_geometria(cfg, GS1)
    punta = estado.chequear_punta(cfg, GS1)
    assert geo.estado == estado.GRIS and "no aplica" in geo.detalle
    assert punta.estado == estado.GRIS and "no aplica" in punta.detalle


def test_apto_para_tracker_con_gs1_y_gs2() -> None:
    """Lo que el panel decide para «Arrancar tracker»: con los perfiles reales gs1 y gs2,
    entorno + config + intrinsecos + puerto en VERDE bastan (la geometria en GRIS no cuenta)."""
    for perfil in (GS1, GS2):
        chequeos, _cfg = estado.evaluar_todo(perfil)
        por = _por_clave(chequeos)
        assert por["geometria"].estado == estado.GRIS and por["punta"].estado == estado.GRIS
        ok, malos = estado.apto_para_tracker(chequeos)
        if por["puerto"].estado != estado.VERDE:   # un tracker vivo en la maquina: no es del perfil
            assert malos == ["puerto"], malos
        else:
            assert ok and malos == [], (perfil.name, [(c.clave, c.estado, c.detalle) for c in chequeos])


def test_apto_para_tracker_sigue_exigiendo_geometria_si_hay_rigid_bodies() -> None:
    """Con un perfil que define rigid_bodies (el Femto, hasta que se archive) la geometria sigue
    contando: en ROJO o AMARILLO bloquea, como antes de la meta 003."""
    chequeos, cfg = estado.evaluar_todo(FEMTO)
    assert cfg.get("rigid_bodies"), "tracker_config.yaml tiene que seguir trayendo el dodecaedro"
    por = _por_clave(chequeos)
    assert por["geometria"].estado != estado.GRIS
    mal = [estado.Chequeo("geometria", "Geometria del rigid body", estado.ROJO, "falta")
           if c.clave == "geometria" else c for c in chequeos]
    ok, malos = estado.apto_para_tracker(mal)
    assert not ok and "geometria" in malos


def test_apto_para_tracker_bloquea_por_intrinsecos_y_puerto() -> None:
    """La geometria GRIS no afloja lo demas: intrinsecos o puerto en ROJO siguen bloqueando."""
    base = [estado.Chequeo("entorno", "Entorno", estado.VERDE, ""),
            estado.Chequeo("config", "Config", estado.VERDE, ""),
            estado.Chequeo("geometria", "Geometria", estado.GRIS, "no aplica"),
            estado.Chequeo("intrinsecos", "Intrinsecos", estado.VERDE, ""),
            estado.Chequeo("punta", "Punta", estado.GRIS, "no aplica"),
            estado.Chequeo("puerto", "Puerto", estado.VERDE, ""),
            estado.Chequeo("camara", "Camara", estado.GRIS, "")]
    assert estado.apto_para_tracker(base) == (True, [])
    for clave in ("entorno", "config", "intrinsecos", "puerto"):
        rotos = [estado.Chequeo(c.clave, c.titulo, estado.ROJO, "x") if c.clave == clave else c for c in base]
        assert estado.apto_para_tracker(rotos) == (False, [clave])
