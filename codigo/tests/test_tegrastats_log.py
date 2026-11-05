"""diagnostics.tegrastats_log (meta 007 · El tracker en la Jetson Orin Nano, fase 7 · Las
dos camaras a la vez en la Jetson): el resumen sobre el log real de `tegrastats` de los
dos escaneos (fase 1 y fase 5b; las lineas, copiadas tal cual del escaneo, sin datos de
paciente ni de la red), los casos del formato que el escaneo no trae (nucleo `off`,
`CPU [...]@Z`, `GR3D_FREQ X%@[...]`, zona sin lectura, linea cortada, sin hora), la
ventana, el CLI y que el guardian acepta las ordenes del P-7 tal cual.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from diagnostics import tegrastats_log as tl
from linux import guardian as g

DATOS = Path(__file__).parent / "data" / "linux"
FASE1 = DATOS / "tegrastats_escaneo_fase1.txt"
FASE5B = DATOS / "tegrastats_escaneo_fase5b.txt"

LINEA = ("10-30-2026 06:34:37 RAM 2709/7620MB (lfb 5x4MB) SWAP 0/12002MB (cached 0MB) "
         "CPU [7%@1728,7%@1728,6%@1728,31%@1728,6%@729,7%@729] GR3D_FREQ 0% cpu@53.281C "
         "soc2@51.812C soc0@52.5C gpu@52.062C tj@54.937C soc1@54.937C VDD_IN 5308mW/4785mW "
         "VDD_CPU_GPU_CV 1119mW/694mW VDD_SOC 1492mW/1462mW")


# ------------------------------------------------------------------ una linea

def test_parsear_linea_real() -> None:
    m = tl.parsear_linea(LINEA)
    assert m is not None
    assert m.t.isoformat() == "2026-10-30T06:34:37"
    assert (m.ram_mb, m.ram_total_mb, m.swap_mb, m.swap_total_mb) == (2709, 7620, 0, 12002)
    assert m.cpu_pct == [7.0, 7.0, 6.0, 31.0, 6.0, 7.0]
    assert m.cpu_mhz == [1728, 1728, 1728, 1728, 729, 729]
    assert m.gpu_pct == 0.0
    assert m.temps_c == {"cpu": 53.281, "soc2": 51.812, "soc0": 52.5, "gpu": 52.062,
                         "tj": 54.937, "soc1": 54.937}
    assert m.potencia_mw == {"VDD_IN": 5308, "VDD_CPU_GPU_CV": 1119, "VDD_SOC": 1492}


def test_parsear_linea_formatos_de_la_guia_de_nvidia() -> None:
    """`off`, la frecuencia comun tras el corchete, `GR3D_FREQ X%@[...]`, una zona en 0 C
    (sin lectura) y una linea sin hora."""
    m = tl.parsear_linea("RAM 4601/63895MB (lfb 3x64MB) CPU [12%,off,3%]@1510 "
                         "GR3D_FREQ 99%@[1098,1098] cv0@0C cpu@45.062C tj@-256C gpu@44C "
                         "VDD_GPU_SOC 3065mW/3065mW")
    assert m is not None and m.t is None and m.swap_mb is None
    assert m.cpu_pct == [12.0, None, 3.0]
    assert m.cpu_mhz == [1510, None, 1510]
    assert m.gpu_pct == 99.0
    assert m.temps_c == {"cpu": 45.062, "gpu": 44.0}          # cv0 y tj sin lectura
    assert m.potencia_mw == {"VDD_GPU_SOC": 3065}


@pytest.mark.parametrize("linea", [
    "$ tegrastats --interval 1000",
    "[fin esperado: se corta a los 10 s a proposito]",
    LINEA[:120],                                   # cortada dentro de CPU [...]
    LINEA[:LINEA.index("cpu@")] + "cpu@53.2",      # cortada antes de la primera C
    LINEA.replace("31%@1728", "31x@1728"),         # un nucleo que no se entiende
    "",
])
def test_parsear_linea_descarta(linea: str) -> None:
    assert tl.parsear_linea(linea) is None


# ------------------------------------------------------------------ el log real

def test_el_log_del_escaneo_de_la_fase_1() -> None:
    """Valores sacados a mano de las 9 lineas. La media de VDD_IN instantanea (4692 mW) es
    la misma que la media que da el propio tegrastats en su ultima linea (4692 mW)."""
    muestras, descartadas = tl.leer(FASE1)
    assert len(muestras) == 9 and descartadas == 2     # la orden y el «fin esperado»
    r = tl.resumir(muestras)
    assert r["span_s"] == 8.0 and r["huecos"] == 0
    assert r["inicio"] == "2026-10-30 06:34:34" and r["fin"] == "2026-10-30 06:34:42"
    assert r["ram_mb"] == {"p50": 2695, "max": 2709, "total": 7620}
    assert r["swap_mb"] == {"max": 0, "total": 12002}
    n0, n3 = r["cpu"]["nucleos"][0], r["cpu"]["nucleos"][3]
    assert n0["media_pct"] == pytest.approx(14 / 9) and n0["max_pct"] == 7.0
    assert n3["media_pct"] == pytest.approx(46 / 9) and n3["max_pct"] == 31.0
    assert n0["max_mhz"] == 1728 and r["cpu"]["nucleos"][5]["max_mhz"] == 729
    assert all(n["apagado"] == 0 for n in r["cpu"]["nucleos"])
    assert r["cpu"]["max_pct"] == 31.0
    assert r["gpu_pct"] == {"media": 0.0, "max": 0.0}
    t = r["temp_c"]
    assert t["max"] == 55.156 and t["zona_max"] in ("tj", "soc1")
    assert t["por_zona"]["cpu"] == 53.281
    assert not t["llego_al_umbral"] and t["primer_cruce_s"] is None
    assert r["potencia_mw"]["VDD_IN"]["max"] == 5308
    assert round(r["potencia_mw"]["VDD_IN"]["media"]) == 4692


def test_el_log_del_escaneo_de_la_fase_5b() -> None:
    muestras, descartadas = tl.leer(FASE5B)
    assert len(muestras) == 9 and descartadas == 2
    r = tl.resumir(muestras)
    assert r["ram_mb"]["max"] == 2912 and r["ram_mb"]["p50"] == 2906
    assert r["cpu"]["nucleos"][1]["max_pct"] == 32.0
    assert r["cpu"]["nucleos"][4]["max_mhz"] == 1728     # 3%@1728 en la segunda linea
    assert r["temp_c"]["max"] == 55.937


def test_umbral_de_corte() -> None:
    muestras, _ = tl.leer(FASE1)
    r = tl.resumir(muestras, umbral_c=55.0)
    assert r["temp_c"]["llego_al_umbral"] and r["temp_c"]["primer_cruce_s"] == 0.0
    r = tl.resumir(muestras, umbral_c=55.1)
    assert r["temp_c"]["primer_cruce_s"] == 4.0          # 06:34:38, tj@55.156C


def test_nucleos_distintos_se_descartan() -> None:
    texto = LINEA + "\n" + LINEA.replace("CPU [7%@1728,", "CPU [")
    muestras, descartadas = tl.parsear(texto)
    assert len(muestras) == 1 and descartadas == 1


def test_huecos_entre_lineas() -> None:
    texto = "\n".join([LINEA, LINEA.replace("06:34:37", "06:34:38"),
                       LINEA.replace("06:34:37", "06:34:41")])
    muestras, _ = tl.parsear(texto)
    assert tl.resumir(muestras)["huecos"] == 1


# ------------------------------------------------------------------ la ventana

def test_ventana_por_la_hora() -> None:
    muestras, _ = tl.leer(FASE1)
    dentro, info = tl.ventana(muestras, saltar_s=2, segundos=5)
    assert [m.t.second for m in dentro] == [36, 37, 38, 39, 40]
    assert info["completa"] and (info["desde_s"], info["hasta_s"]) == (2.0, 6.0)
    r = tl.resumir(dentro)
    assert r["ram_mb"]["max"] == 2709 and r["cpu"]["nucleos"][3]["max_pct"] == 31.0


def test_ventana_incompleta_y_vacia() -> None:
    muestras, _ = tl.leer(FASE1)
    dentro, info = tl.ventana(muestras, saltar_s=5, segundos=60)
    assert len(dentro) == 4 and not info["completa"] and info["log_s"] == 8.0
    dentro, info = tl.ventana(muestras, saltar_s=30, segundos=0)
    assert dentro == [] and not info["completa"]
    with pytest.raises(ValueError):
        tl.ventana(muestras, saltar_s=-1)


def test_ventana_sin_hora_va_por_indice() -> None:
    sin_hora = "\n".join(LINEA[20:] for _ in range(5))
    muestras, _ = tl.parsear(sin_hora)
    assert all(m.t is None for m in muestras)
    dentro, info = tl.ventana(muestras, saltar_s=1, segundos=2)
    assert len(dentro) == 2 and info["completa"]


# ------------------------------------------------------------------ el CLI

def test_main_escribe_el_json_y_no_pisa(tmp_path: Path, capsys) -> None:
    salida = tmp_path / "p7" / "parado.json"
    rc = tl.main(["--input", str(FASE1), "--saltar-s", "2", "--segundos", "5",
                  "--etiqueta", "ollama-parado", "--output", str(salida)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "5 muestras" in out and "temperatura max 55.2 C" in out and "llego a 90 C: no" in out
    assert "AVISO" not in out
    res = json.loads(salida.read_text(encoding="utf-8"))
    assert res["etiqueta"] == "ollama-parado" and res["resumen"]["muestras"] == 5
    assert res["log_entero"]["muestras"] == 9
    rc = tl.main(["--input", str(FASE1), "--output", str(salida)])
    assert rc == 1 and "no se pisa" in capsys.readouterr().err


def test_main_avisa_y_falla_fuerte(tmp_path: Path, capsys) -> None:
    rc = tl.main(["--input", str(FASE1), "--saltar-s", "60", "--segundos", "300"])
    assert rc == 1 and "queda vacia" in capsys.readouterr().err
    rc = tl.main(["--input", str(FASE1), "--saltar-s", "5", "--segundos", "300"])
    assert rc == 0 and "AVISO" in capsys.readouterr().out
    vacio = tmp_path / "vacio.txt"
    vacio.write_text("$ tegrastats --interval 1000\n", encoding="utf-8")
    rc = tl.main(["--input", str(vacio)])
    assert rc == 1 and "ninguna linea" in capsys.readouterr().err
    rc = tl.main(["--input", str(tmp_path / "no_existe.txt")])
    assert rc == 1


# ------------------------------------------------------------------ el guardian y el P-7

@pytest.fixture
def home(tmp_path: Path) -> Path:
    casa = tmp_path / "home" / "navagente"
    for partes in g.ARBOLES.values():
        casa.joinpath(*partes).mkdir(parents=True)
    g.ruta_salidas(casa).mkdir()
    g.ruta_python(casa).parent.mkdir(parents=True)
    g.ruta_python(casa).write_text("", encoding="utf-8")
    return casa


def test_el_guardian_acepta_las_ordenes_del_p7(home: Path) -> None:
    """Las ordenes de la Jetson del protocolo P-7, tal cual: ninguna da 126."""
    bp1 = "platform-3610000.usb-usb-0:2.1:1.0-video-index0"
    bp2 = "platform-3610000.usb-usb-0:2.2:1.0-video-index0"
    perfil2 = str(g.ruta_salidas(home) / "perfiles" / "gs2_18946.yaml")   # /home/navagente/... en la Jetson
    ordenes = [
        ["py", "wip", "linux.perfil_temporal", "--base", "profiles/tracker_config_gs2.yaml",
         "--puerto", "18946", "--salida", "~/nav-salidas/perfiles/gs2_18946.yaml"],
        ["py", "wip", "diagnostics.igtl_rate", "listen", "--host", "127.0.0.1", "--port", "18944",
         "--seconds", "600", "--timeout", "60", "--device", "Marker0ToTracker",
         "--csv", "~/nav-salidas/p7/parado_gs1_llegadas.csv"],
        ["py", "wip", "tracker", "--config", "profiles/tracker_config_gs1.yaml", "--no-window",
         "--duration", "450"],
        ["py", "wip", "tracker", "--config", perfil2, "--no-window", "--duration", "450"],
        ["medir", "tegrastats", "390"],
        ["py", "wip", "diagnostics.tegrastats_log", "--input",
         "~/nav-salidas/tegrastats_20261104_120000_390s.txt", "--saltar-s", "60", "--segundos", "300",
         "--etiqueta", "ollama-parado", "--output", "~/nav-salidas/p7/parado_tegrastats.json"],
        ["traer", "~/nav-salidas/p7/parado_tegrastats.json"],
        ["camara", "rafaga", bp1, "900"], ["camara", "rafaga", bp2, "900"],
        ["info", "camara-libre", bp2], ["info", "puerto-libre", "18946"], ["info", "temperatura"],
        ["procesos"],
    ]
    decididas = [g.decidir(o, home) for o in ordenes]
    tl_orden = decididas[5]
    assert tl_orden.tope_s == g.MODULOS["diagnostics.tegrastats_log"] == 60.0
    assert not tl_orden.pesada and not decididas[1].pesada          # analisis y listener, ligeros
    assert [d.pesada for d in decididas[2:5]] == [True, True, True]
    assert tl_orden.argv[-1].endswith("parado_tegrastats.json")


def test_dos_trackers_y_tegrastats_caben_en_el_guardian(home: Path) -> None:
    """Con los dos trackers en marcha, `medir tegrastats` es la tercera pesada y pasa; una
    cuarta (otra rafaga, otro tracker) se niega. Los listeners no cuentan."""
    medir = g.decidir(["medir", "tegrastats", "390"], home)
    ok = dict(leer_temp=lambda: 60.0, libre_gb=lambda: 20.0)
    g.precondiciones(medir, home, pesadas=lambda: 2, **ok)
    with pytest.raises(g.Negado, match="pesadas"):
        g.precondiciones(medir, home, pesadas=lambda: 3, **ok)
    with pytest.raises(g.Negado, match="temperatura"):
        g.precondiciones(medir, home, pesadas=lambda: 0, leer_temp=lambda: 86.0,
                         libre_gb=lambda: 20.0)
