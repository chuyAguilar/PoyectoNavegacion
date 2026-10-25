"""`profiles` (meta 003, fase 3; prueba de la fase 4): rutas relativas a codigo/, la
carga de gs1 y gs2 con su .yml resuelto, el fallo con nombre de perfil si una ruta
no existe, `missing_ok` y la lista de perfiles.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import profiles

from .conftest import CODIGO_DIR, PROFILES_DIR


def test_rutas_del_codigo() -> None:
    assert profiles.CODE_ROOT == CODIGO_DIR
    assert profiles.PROFILES_DIR == PROFILES_DIR and profiles.DATA_DIR == CODIGO_DIR / "data"


def test_resolve_path_relativa_a_codigo_y_absoluta(tmp_path: Path) -> None:
    p = profiles.resolve_path("data/intrinsecos_gs1_1280x960.yml")
    assert p.is_absolute() and p == (CODIGO_DIR / "data" / "intrinsecos_gs1_1280x960.yml").resolve()
    f = tmp_path / "x.yml"
    f.write_text("x", encoding="utf-8")
    assert profiles.resolve_path(f) == f.resolve()
    with pytest.raises(FileNotFoundError, match="relativas a"):
        profiles.resolve_path("data/no_existe.yml")


@pytest.mark.parametrize("nombre", ["tracker_config_gs1.yaml", "tracker_config_gs2.yaml"])
def test_load_resuelve_el_yml_de_cada_perfil(nombre: str) -> None:
    cfg = profiles.load(PROFILES_DIR / nombre)
    yml = Path(cfg["camera"]["calibration_file"])
    assert yml.is_absolute() and yml.is_file() and yml.parent == (CODIGO_DIR / "data").resolve()
    assert "rigid_bodies" not in cfg
    assert [m["name"] for m in cfg["markers"]["list"]] == ["Marker0"]


def test_load_falla_con_el_nombre_del_perfil_si_falta_una_ruta(tmp_path: Path) -> None:
    cfg = yaml.safe_load((PROFILES_DIR / "tracker_config_gs1.yaml").read_text(encoding="utf-8"))
    cfg["camera"]["calibration_file"] = "data/no_existe.yml"
    ruta = tmp_path / "tracker_config_roto.yaml"
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="tracker_config_roto.yaml: camera.calibration_file"):
        profiles.load(ruta)
    laxo = profiles.load(ruta, missing_ok=True)
    assert laxo["camera"]["calibration_file"] == str(CODIGO_DIR / "data" / "no_existe.yml")
    cfg["camera"]["calibration_file"] = "data/intrinsecos_gs1_1280x960.yml"
    cfg["rigid_bodies"] = [{"name": "X", "geometry_file": "data/geom_no.txt"}]
    ruta.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="rigid body X"):
        profiles.load(ruta)


def test_load_exige_un_yaml_con_secciones(tmp_path: Path) -> None:
    ruta = tmp_path / "tracker_config_lista.yaml"
    ruta.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="secciones"):
        profiles.load(ruta)


def test_list_profiles_da_gs1_y_gs2() -> None:
    nombres = [p.name for p in profiles.list_profiles()]
    assert "tracker_config_gs1.yaml" in nombres and "tracker_config_gs2.yaml" in nombres
    assert nombres == sorted(nombres) and all(n.endswith(".yaml") for n in nombres)
