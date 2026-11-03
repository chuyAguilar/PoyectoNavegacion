"""linux.perfil_temporal (meta 007 · El tracker en la Jetson Orin Nano, fase 5b · El ruido de
gs1 por V4L2, P25): la copia de un perfil con solo el puerto OpenIGTLink, el puerto USB de
Linux o la exposicion cambiados, conservando comentarios y fines de linea; lo que niega
(clave fuera de la lista, valor fuera de rango, clave que el base no tiene, salida que
existe, sin cambios); el CLI; y que el guardian acepta la orden de J4 tal cual.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from linux import guardian as g
from linux import perfil_temporal as pt

from .conftest import PROFILES_DIR

GS1 = PROFILES_DIR / "tracker_config_gs1.yaml"
BYPATH_2 = "platform-3610000.usb-usb-0:2.2:1.0-video-index0"


def _carga(p: Path) -> dict:
    return yaml.safe_load(p.read_bytes().decode("utf-8"))


def _lineas_distintas(a: Path, b: Path) -> list[tuple[str, str]]:
    la = a.read_bytes().decode("utf-8").splitlines(keepends=True)
    lb = b.read_bytes().decode("utf-8").splitlines(keepends=True)
    assert len(la) == len(lb), "la copia tiene otro numero de lineas"
    return [(x, y) for x, y in zip(la, lb) if x != y]


def test_puerto_cambia_solo_transforms_port(tmp_path: Path) -> None:
    salida = pt.crear(GS1, tmp_path / "gs1_18945.yaml", {"transforms_port": 18945})
    base, copia = _carga(GS1), _carga(salida)
    assert copia["igtlink"]["transforms_port"] == 18945
    copia["igtlink"]["transforms_port"] = base["igtlink"]["transforms_port"]
    assert copia == base
    dist = _lineas_distintas(GS1, salida)
    assert len(dist) == 1 and dist[0][1].strip() == "transforms_port: 18945", dist
    # video_port: 18945 (otra clave con el mismo numero) no se toca.
    assert copia["igtlink"]["video_port"] == base["igtlink"]["video_port"]


def test_poner_usb_port_linux_conserva_comentarios_y_fin_de_linea(tmp_path: Path) -> None:
    salida = pt.crear(GS1, tmp_path / "gs1_puerto22.yaml", {"camera.usb_port_linux": BYPATH_2})
    assert _carga(salida)["camera"]["usb_port_linux"] == BYPATH_2
    dist = _lineas_distintas(GS1, salida)
    assert len(dist) == 1, dist
    antes, despues = dist[0]
    assert antes.startswith("  usb_port_linux: ") and despues.startswith("  usb_port_linux: ")
    assert antes[-2:] == despues[-2:]        # el mismo fin de linea (CRLF o LF)
    assert GS1.read_bytes().count(b"#") == salida.read_bytes().count(b"#")


def test_poner_exposicion_conserva_el_comentario_de_la_linea(tmp_path: Path) -> None:
    salida = pt.crear(GS1, tmp_path / "gs1_exp.yaml", {"camera.controls.exposure_ms": "0.9"})
    assert _carga(salida)["camera"]["controls"]["exposure_ms"] == pytest.approx(0.9)
    dist = _lineas_distintas(GS1, salida)
    assert len(dist) == 1
    assert dist[0][1].rstrip("\r\n") == "    exposure_ms: 0.9          # -10 por DSHOW (log2 de segundos)"


def test_dos_cambios_a_la_vez(tmp_path: Path) -> None:
    salida = pt.crear(GS1, tmp_path / "gs1_dos.yaml",
                      {"transforms_port": "18950", "camera.usb_port_linux": BYPATH_2})
    c = _carga(salida)
    assert c["igtlink"]["transforms_port"] == 18950 and c["camera"]["usb_port_linux"] == BYPATH_2
    assert len(_lineas_distintas(GS1, salida)) == 2


@pytest.mark.parametrize("cambios, motivo", [
    ({"igtlink.video_port": 18946}, "no se puede cambiar"),
    ({"camera.marca.focus": 332}, "no se puede cambiar"),
    ({"transforms_port": 18944}, "fuera de 18945-18950"),
    ({"transforms_port": 18951}, "fuera de 18945-18950"),
    ({"transforms_port": "18945.0"}, "entero"),
    ({"camera.usb_port_linux": "/dev/video0"}, "by-path"),
    ({"camera.usb_port_linux": "platform-3610000.usb-usb-0:2.2:1.0-video-index0/../x"}, "by-path"),
    ({"camera.controls.exposure_ms": 0.05}, "fuera de"),
    ({"camera.controls.exposure_ms": 20}, "fuera de"),
    ({"camera.controls.exposure_ms": "rapida"}, "numero"),
    ({}, "sin cambios"),
])
def test_niega_claves_y_valores(tmp_path: Path, cambios: dict, motivo: str) -> None:
    salida = tmp_path / "x.yaml"
    with pytest.raises(ValueError, match=motivo):
        pt.crear(GS1, salida, cambios)
    assert not salida.exists()


def test_niega_clave_que_el_base_no_tiene(tmp_path: Path) -> None:
    base = tmp_path / "sin_linux.yaml"
    texto = GS1.read_bytes().decode("utf-8")
    base.write_bytes("".join(l for l in texto.splitlines(keepends=True)
                             if not l.lstrip().startswith("usb_port_linux:")).encode("utf-8"))
    with pytest.raises(ValueError, match="no tiene la clave camera.usb_port_linux"):
        pt.crear(base, tmp_path / "x.yaml", {"camera.usb_port_linux": BYPATH_2})
    assert not (tmp_path / "x.yaml").exists()


def test_no_pisa_una_salida_que_existe(tmp_path: Path) -> None:
    salida = tmp_path / "ya.yaml"
    salida.write_text("x: 1\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        pt.crear(GS1, salida, {"transforms_port": 18945})
    assert salida.read_text(encoding="utf-8") == "x: 1\n"
    with pytest.raises(ValueError, match="yaml"):
        pt.crear(GS1, tmp_path / "x.txt", {"transforms_port": 18945})
    with pytest.raises(FileNotFoundError):
        pt.crear(tmp_path / "no.yaml", tmp_path / "y.yaml", {"transforms_port": 18945})


def test_parsear_poner() -> None:
    assert pt.parsear_poner("transforms_port=18946") == ("transforms_port", 18946)
    assert pt.parsear_poner("camera.controls.exposure_ms=0.9") == ("camera.controls.exposure_ms", 0.9)
    with pytest.raises(ValueError, match="CLAVE=VALOR"):
        pt.parsear_poner("transforms_port")


def test_cli_crea_y_devuelve_1_si_niega(tmp_path: Path, capsys) -> None:
    salida = tmp_path / "perfiles" / "gs1_puerto22.yaml"
    rc = pt.main(["--base", str(GS1), "--salida", str(salida), "--puerto", "18945",
                  "--poner", f"camera.usb_port_linux={BYPATH_2}"])
    assert rc == 0 and salida.is_file()
    out = capsys.readouterr().out
    assert "transforms_port=18945" in out and BYPATH_2 in out
    c = _carga(salida)
    assert c["igtlink"]["transforms_port"] == 18945 and c["camera"]["usb_port_linux"] == BYPATH_2
    rc = pt.main(["--base", str(GS1), "--salida", str(salida), "--puerto", "18946"])
    assert rc == 1 and "no se pisa" in capsys.readouterr().err
    rc = pt.main(["--base", str(GS1), "--salida", str(tmp_path / "z.yaml"), "--poner", "debug.verbose=true"])
    assert rc == 1 and "no se puede cambiar" in capsys.readouterr().err
    rc = pt.main(["--base", str(GS1), "--salida", str(tmp_path / "w.yaml"), "--puerto", "18945",
                  "--poner", "transforms_port=18946"])
    assert rc == 1 and "dos veces" in capsys.readouterr().err
    rc = pt.main(["--base", str(GS1), "--salida", str(tmp_path / "v.yaml")])
    assert rc == 1 and "sin cambios" in capsys.readouterr().err


def test_el_guardian_acepta_la_orden_de_j4(tmp_path: Path) -> None:
    """La orden del protocolo P-5b (J4): el perfil base dentro del arbol, --poner sin ruta y
    --salida en ~/nav-salidas/. El tope es el de `linux.perfil_temporal` (30 s)."""
    home = tmp_path
    o = g.decidir(["py", "wip", "linux.perfil_temporal", "--base", "profiles/tracker_config_gs1.yaml",
                   "--poner", f"camera.usb_port_linux={BYPATH_2}",
                   "--salida", "~/nav-salidas/perfiles/gs1_puerto22.yaml"], home)
    assert o.verbo == "py linux.perfil_temporal" and o.tope_s == g.MODULOS["linux.perfil_temporal"]
    assert not o.pesada
    assert o.argv[2:5] == ["-m", "linux.perfil_temporal", "--base"]
    assert f"camera.usb_port_linux={BYPATH_2}" in o.argv
    assert o.argv[-2] == "--salida" and o.argv[-1].endswith("gs1_puerto22.yaml")
    with pytest.raises(g.Negado):
        g.decidir(["py", "wip", "linux.perfil_temporal", "--base", "profiles/tracker_config_gs1.yaml",
                   "--puerto", "18945", "--salida", "/tmp/x.yaml"], home)
