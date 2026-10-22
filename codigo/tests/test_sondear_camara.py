"""sondear_camara.py sin camara: un VideoCapture falso (meta 002, fase 1)."""
from __future__ import annotations

import numpy as np
import pytest

import sondear_camara as sc


class CapFalso:
    """Acepta solo los controles de `aceptados`; los demas leen 0 y set da False.

    `redondeo` simula un driver que redondea al paso real del dispositivo.
    """

    def __init__(self, valores: dict[int, float], aceptados: set[int],
                 redondeo: dict[int, float] | None = None) -> None:
        self.valores = dict(valores)
        self.aceptados = aceptados
        self.redondeo = redondeo or {}
        self.sets: list[tuple[int, float]] = []

    def get(self, prop: int) -> float:
        return self.valores.get(prop, 0.0)

    def set(self, prop: int, valor: float) -> bool:
        self.sets.append((prop, valor))
        if prop not in self.aceptados:
            return False
        paso = self.redondeo.get(prop)
        self.valores[prop] = round(valor / paso) * paso if paso else valor
        return True


C = sc.CONTROLES


class CapMSMF:
    """Como se comporto OpenCV 4.11 por MSMF con la camara 1 (2026-10-20).

    get() devuelve siempre el valor por defecto, no el de la camara; set() da
    True y escribe en la camara; set(AUTO_EXPOSURE, v) escribe v como exposicion
    en manual. `real` es el estado de la camara (lo que ve AMCap).
    """

    def __init__(self) -> None:
        self.defecto = {C["exposure"]: -6.0, C["auto_exposure"]: 0.0}
        self.real = {"exposure": -6.0, "auto": False}

    def get(self, prop: int) -> float:
        return self.defecto.get(prop, 0.0)

    def set(self, prop: int, valor: float) -> bool:
        if prop == C["exposure"]:
            self.real = {"exposure": valor, "auto": False}
        elif prop == C["auto_exposure"]:
            self.real = {"exposure": valor, "auto": valor != 0}
        return True


def test_controles_son_los_12_del_plan() -> None:
    assert list(C) == ["exposure", "auto_exposure", "gain", "auto_wb", "wb_temperature",
                       "brightness", "contrast", "saturation", "sharpness", "gamma",
                       "backlight", "focus"]


def test_control_aceptado_y_restaurado() -> None:
    cap = CapFalso({C["exposure"]: -6.0}, {C["exposure"]})
    (fila,) = sc.sondear_controles(cap, ["exposure"])
    assert fila["inicial"] == -6.0
    assert fila["acepta"] is True and fila["escritura"] == "verificada"
    assert [p["valor"] for p in fila["pruebas"]] == [-5.0, -7.0]
    assert all(p["coincide"] for p in fila["pruebas"])
    assert fila["restaurado"] is True and cap.get(C["exposure"]) == -6.0


def test_control_no_aceptado() -> None:
    cap = CapFalso({}, set())
    (fila,) = sc.sondear_controles(cap, ["focus"])
    assert fila["acepta"] is False and fila["escritura"] == "rechazada"
    assert all(not p["set_ok"] for p in fila["pruebas"])


def test_control_redondeado_no_coincide() -> None:
    cap = CapFalso({C["wb_temperature"]: 4600.0}, {C["wb_temperature"]},
                   redondeo={C["wb_temperature"]: 1000.0})
    (fila,) = sc.sondear_controles(cap, ["wb_temperature"])
    assert fila["acepta"] is False and fila["escritura"] == "no coincide"
    assert fila["pruebas"][0]["leido"] == 5000.0


def test_lectura_que_no_cambia_es_no_verificable() -> None:
    """La firma de MSMF: set da True y get sigue en el inicial."""
    filas = sc.sondear_controles(CapMSMF(), ["exposure"])
    assert filas[0]["escritura"] == "no verificable" and filas[0]["acepta"] is False


def test_restauracion_no_deja_la_exposicion_cambiada_como_en_msmf() -> None:
    """La regresion de la sesion en vivo: antes la camara quedaba en exposicion 0."""
    cap = CapMSMF()
    sc.sondear_controles(cap, ["exposure", "auto_exposure"])
    assert cap.real == {"exposure": -6.0, "auto": False}


def test_auto_restaura_su_dependiente_y_va_primero_al_final() -> None:
    cap = CapFalso({C["auto_exposure"]: 1.0, C["exposure"]: -5.0},
                   {C["auto_exposure"], C["exposure"]})
    filas = sc.sondear_controles(cap, ["exposure", "auto_exposure"])
    auto = filas[1]
    assert 1.0 not in [p["valor"] for p in auto["pruebas"]]
    assert auto["acepta"] is True
    # Tras cada prueba del auto se reescribe la exposicion.
    i = cap.sets.index((C["auto_exposure"], 0.0))
    assert cap.sets[i + 1:i + 3] == [(C["auto_exposure"], 1.0), (C["exposure"], -5.0)]
    # La restauracion final: el auto antes que el numerico.
    assert [prop for prop, _ in cap.sets[-2:]] == [C["auto_exposure"], C["exposure"]]
    assert all(f["restaurado"] for f in filas)


def test_orden_restauracion() -> None:
    assert sc.orden_restauracion(["exposure", "gain", "auto_wb", "auto_exposure"]) == \
        ["auto_wb", "auto_exposure", "exposure", "gain"]


def test_solo_leer_no_llama_a_set() -> None:
    cap = CapFalso({C["gain"]: 12.0}, {C["gain"]})
    (fila,) = sc.sondear_controles(cap, ["gain"], solo_leer=True)
    assert cap.sets == []
    assert fila["inicial"] == 12.0 and fila["acepta"] is None


def test_tope_deja_de_probar_y_restaura() -> None:
    cap = CapFalso({C["gain"]: 12.0}, {C["gain"]})
    (fila,) = sc.sondear_controles(cap, ["gain"], limite=0.0)
    assert fila["escritura"] == "no probado: tope de tiempo" and fila["pruebas"] == []
    assert cap.sets == [(C["gain"], 12.0)] and fila["restaurado"] is True


def test_control_desconocido() -> None:
    with pytest.raises(ValueError, match="desconocidos"):
        sc.sondear_controles(CapFalso({}, set()), ["iso"])


@pytest.mark.parametrize("pruebas,esperado", [
    ([], None),
    ([{"set_ok": False, "leido": 0.0, "coincide": False}], "rechazada"),
    ([{"set_ok": True, "leido": 1.0, "coincide": True}], "verificada"),
    ([{"set_ok": True, "leido": 0.0, "coincide": False}], "no verificable"),
    ([{"set_ok": True, "leido": 2.0, "coincide": False}], "no coincide"),
])
def test_clasificar_escritura(pruebas, esperado) -> None:
    assert sc.clasificar_escritura(0.0, pruebas) == esperado


def test_comparar_testigos() -> None:
    antes = {"brillo": 100.0, "fps": 30.0}
    assert sc.comparar_testigos(antes, {"brillo": 105.0, "fps": 28.0}) == []
    difs = sc.comparar_testigos(antes, {"brillo": 160.0, "fps": 6.0})
    assert len(difs) == 2 and difs[0].startswith("brillo") and difs[1].startswith("fps")
    assert sc.comparar_testigos(antes, {"brillo": None, "fps": 30.0})[0].startswith("brillo")


def test_parsear_modos() -> None:
    assert sc.parsear_modos("640x480:mjpg, 1920x1200:YUY2") == \
        [(640, 480, "MJPG"), (1920, 1200, "YUY2")]


@pytest.mark.parametrize("texto", ["", "640x480", "640x480:MJP", "0x480:MJPG", "axb:MJPG"])
def test_parsear_modos_mal(texto: str) -> None:
    with pytest.raises(ValueError):
        sc.parsear_modos(texto)


def test_fourcc_texto() -> None:
    import cv2
    assert sc.fourcc_texto(cv2.VideoWriter_fourcc(*"MJPG")) == "MJPG"
    assert sc.fourcc_texto(0) == ""
    assert sc.fourcc_texto(22) == "0x00000016"   # lo que dio MSMF en vivo


def test_resumir_modos() -> None:
    filas = [{"fps_captura": 6.7, "tamano_coincide": True},
             {"fps_captura": 6.7, "tamano_coincide": False},
             {"error": "abre pero no entrega frames"},
             {"error": "no abre source=0 backend=MSMF"},
             {"error": "no medido: tope de tiempo"}]
    assert sc.resumir_modos(filas) == {"pedidos": 5, "medidos": 2, "sin_frames": 1,
                                       "no_abre": 1, "sin_medir_tope": 1, "tamano_distinto": 1}


def test_estimar_segundos_cabe_en_el_tope() -> None:
    base = sc.IDENTIDAD_S + 20 * (sc.ABRIR_S + 5 + sc.MARGEN_MODO_S)
    assert sc.estimar_segundos(20, 5, "no") == base
    assert sc.estimar_segundos(0, 0, "probar") > sc.estimar_segundos(0, 0, "leer") > \
        sc.estimar_segundos(0, 0, "no")


class VCSinFrames:
    """Un VideoCapture que abre pero no entrega frames; cuenta las lecturas."""
    lecturas = 0

    def __init__(self, *a) -> None:
        pass

    def isOpened(self) -> bool:
        return True

    def set(self, *a) -> bool:
        return True

    def get(self, *a) -> float:
        return 0.0

    def read(self):
        VCSinFrames.lecturas += 1
        return False, None

    def release(self) -> None:
        pass


def test_modo_sin_frames_se_deja_al_primer_fallo(monkeypatch) -> None:
    VCSinFrames.lecturas = 0
    monkeypatch.setattr(sc.cv2, "VideoCapture", VCSinFrames)
    (fila,) = sc.sondear_modos(0, "MSMF", [(800, 600, "MJPG")], 1.0, 30.0)
    assert fila["error"] == "abre pero no entrega frames" and VCSinFrames.lecturas == 1
    assert "total_s" in fila


def test_modos_sin_tiempo_quedan_sin_medir(monkeypatch) -> None:
    monkeypatch.setattr(sc.cv2, "VideoCapture", VCSinFrames)
    filas = sc.sondear_modos(0, "MSMF", [(640, 480, "MJPG")] * 3, 5.0, 30.0, limite=0.0)
    assert sc.resumir_modos(filas)["sin_medir_tope"] == 3


def test_main_mide_modos_antes_de_tocar_controles(monkeypatch, tmp_path) -> None:
    eventos: list[str] = []

    class VC:
        def __init__(self, *a) -> None:
            pass

        def isOpened(self) -> bool:
            return True

        def read(self):
            return True, np.full((4, 4, 3), 100, np.uint8)

        def get(self, prop) -> float:
            return 0.0

        def set(self, prop, valor) -> bool:
            eventos.append("set")
            return True

        def release(self) -> None:
            pass

    def modos_falso(*a, **k):
        eventos.append("modos")
        return [{"fps_captura": 30.0, "tamano_coincide": True}]

    monkeypatch.setattr(sc.cv2, "VideoCapture", VC)
    monkeypatch.setattr(sc, "sondear_modos", modos_falso)
    monkeypatch.setattr(sc, "identidad", lambda s: {"camaras": [], "esta": None})
    monkeypatch.setattr(sc, "testigo", lambda cap, s: {"frames": 60, "fps": 30.0, "brillo": 100.0})
    rc = sc.main(["--source", "0", "--backend", "DSHOW", "--controles", "probar",
                  "--modos", "640x480:MJPG", "--fps", "30", "--segundos", "1",
                  "--salida", str(tmp_path / "s.json"), "--timeout", "600"])
    assert rc == 0
    assert eventos[0] == "modos" and "set" in eventos


def test_main_exige_argumentos(tmp_path) -> None:
    with pytest.raises(SystemExit):
        sc.main(["--source", "0", "--salida", str(tmp_path / "s.json"), "--timeout", "10"])


@pytest.mark.parametrize("controles", ["leer", "probar"])
def test_main_msmf_no_escribe_ni_lee_controles(tmp_path, controles) -> None:
    with pytest.raises(SystemExit):
        sc.main(["--source", "0", "--backend", "MSMF", "--controles", controles,
                 "--salida", str(tmp_path / "s.json"), "--timeout", "600"])
    assert not (tmp_path / "s.json").exists()


def test_main_controles_no_exige_modos(tmp_path) -> None:
    with pytest.raises(SystemExit):
        sc.main(["--source", "0", "--backend", "MSMF", "--controles", "no",
                 "--salida", str(tmp_path / "s.json"), "--timeout", "600"])


def test_main_para_si_el_tope_no_alcanza(tmp_path, capsys) -> None:
    modos = ",".join(["640x480:MJPG"] * 20)
    with pytest.raises(SystemExit):
        sc.main(["--source", "0", "--backend", "MSMF", "--controles", "no",
                 "--modos", modos, "--fps", "90", "--segundos", "5",
                 "--salida", str(tmp_path / "s.json"), "--timeout", "300"])
    assert "el tope no alcanza" in capsys.readouterr().err


# ----------------------------------------------------------------------------
# Fase 2a: nitidez, marca, --puertos, --leer, --fijar, --tras-msmf, --verificar-orden
# ----------------------------------------------------------------------------

PUERTO_1 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)"
PUERTO_2 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)"


def _json(ruta):
    import json
    return json.loads(ruta.read_text(encoding="utf-8"))


def _camara(indice: int, puerto: str, nombre: str = "Global Shutter Camera"):
    import camaras_uvc as cu
    return cu.CamaraUVC(indice, nombre, "x", "32E4", "0234", "6&1", puerto,
                        "Port_#0002.Hub_#0001", "USB_VID_32E4_PID_0234_01.00.00")


def test_controles_vienen_de_ajustes_camara() -> None:
    import ajustes_camara
    assert sc.CONTROLES is ajustes_camara.CONTROLES_SONDA


def test_nitidez_sube_con_el_detalle() -> None:
    lisa = np.full((64, 64, 3), 100, np.uint8)
    rayas = lisa.copy()
    rayas[:, ::2] = 200
    assert sc.nitidez(lisa) == 0.0
    assert sc.nitidez(rayas) > 100.0
    assert sc.nitidez(rayas[:, :, 0]) == pytest.approx(sc.nitidez(rayas), rel=0.05)


class VCTestigo:
    """Entrega n frames con rayas (brillo 150) y luego nada."""

    def __init__(self, *a, n: int = 5) -> None:
        self.n = n

    def isOpened(self) -> bool:
        return True

    def set(self, *a) -> bool:
        return True

    def get(self, *a) -> float:
        return 0.0

    def read(self):
        if self.n <= 0:
            return False, None
        self.n -= 1
        f = np.full((8, 16, 3), 100, np.uint8)
        f[:, ::2] = 200
        return True, f

    def release(self) -> None:
        pass


def test_testigo_trae_nitidez_y_tamano() -> None:
    t = sc.testigo(VCTestigo(), 0.05)
    assert t["frames"] == 5 and t["brillo"] == 150.0 and t["nitidez"] > 0
    assert t["real"] == {"ancho": 16, "alto": 8}


def test_comparar_marca() -> None:
    antes = {"brillo": 100.0, "fps": 90.0, "nitidez": 200.0}
    assert sc.comparar_marca(antes, {"brillo": 101.5, "fps": 80.0, "nitidez": 203.0}) == []
    difs = sc.comparar_marca(antes, {"brillo": 103.0, "fps": 89.0, "nitidez": 190.0})
    assert [d.split(":")[0] for d in difs] == ["brillo", "nitidez"]
    # Sin tol_nitidez (los testigos de la fase 1), la nitidez no se compara.
    assert sc.comparar_testigos(antes, {"brillo": 100.0, "fps": 90.0}) == []


def test_parsear_fijar() -> None:
    c = sc.parsear_fijar("exposure_ms=1.953, gain=11,auto_white_balance=false")
    assert c == {"exposure_ms": 1.953, "gain": 11.0, "auto_white_balance": False,
                 "exposure_manual": True}
    assert sc.parsear_fijar("focus=200") == {"focus": 200.0}


@pytest.mark.parametrize("texto", ["", "gain", "gain=x", "auto_exposure=0", "exposure_ms=5.0"])
def test_parsear_fijar_mal(texto: str) -> None:
    with pytest.raises(ValueError):
        sc.parsear_fijar(texto)


def test_main_un_modo_de_la_2a_por_corrida(tmp_path) -> None:
    with pytest.raises(SystemExit):
        sc.main(["--puertos", "--leer", "--puerto", PUERTO_1,
                 "--salida", str(tmp_path / "s.json"), "--timeout", "10"])


def test_main_verificar_orden_exige_backend(tmp_path) -> None:
    with pytest.raises(SystemExit):
        sc.main(["--verificar-orden", "--salida", str(tmp_path / "s.json"), "--timeout", "10"])


@pytest.mark.parametrize("modo", ["--leer", "--tras-msmf"])
def test_main_leer_y_tras_msmf_exigen_puerto(tmp_path, modo: str) -> None:
    with pytest.raises(SystemExit):
        sc.main([modo, "--salida", str(tmp_path / "s.json"), "--timeout", "10"])


def test_main_puertos(monkeypatch, tmp_path) -> None:
    import camaras_uvc as cu
    cam = _camara(0, PUERTO_1)
    monkeypatch.setattr(cu, "listar_camaras_msmf", lambda con_puerto=True: [cam])
    monkeypatch.setattr(cu, "listar_camaras_dshow", lambda con_puerto=True: [cam])
    rc = sc.main(["--puertos", "--salida", str(tmp_path / "p.json"), "--timeout", "10"])
    assert rc == 0
    d = _json(tmp_path / "p.json")
    assert d["modo"] == "puertos"
    assert d["puertos"]["MSMF"][0]["ruta_puerto"] == PUERTO_1
    assert d["puertos"]["DSHOW"][0]["instancia_usb"].endswith("01.00.00")


def test_main_puertos_con_error_de_un_backend(monkeypatch, tmp_path) -> None:
    import camaras_uvc as cu
    monkeypatch.setattr(cu, "listar_camaras_msmf", lambda con_puerto=True: [])

    def roto(con_puerto=True):
        raise OSError("COM no inicializa")
    monkeypatch.setattr(cu, "listar_camaras_dshow", roto)
    rc = sc.main(["--puertos", "--salida", str(tmp_path / "p.json"), "--timeout", "10"])
    assert rc == 1
    d = _json(tmp_path / "p.json")
    assert d["puertos"]["DSHOW"] == {"error": "COM no inicializa"} and d["puertos"]["MSMF"] == []


class CapaFalsa:
    """Una capa de ajustes que recuerda lo que le piden; `estado` es lo que 'tiene la camara'."""

    def __init__(self, estado: dict) -> None:
        self.estado = dict(estado)
        self.aplicados: list[dict] = []
        self.lecturas = 0

    def leer(self, puerto, nombres):
        self.lecturas += 1
        return {n: self.estado.get(n, 0.0) for n in nombres}

    def aplicar(self, puerto, controls):
        import ajustes_camara
        self.aplicados.append(dict(controls))
        v = ajustes_camara.validar_controles(controls)
        escritos = [n for n in v if n != "exposure_manual" and self.estado.get(n) != v[n]]
        self.estado.update({n: v[n] for n in escritos})
        return {"indice": 0, "antes": {}, "leidos": dict(self.estado), "escritos": escritos,
                "set_false": [], "diferencias": [], "segundos": 0.5}


def test_main_fijar_guarda_lo_escrito(monkeypatch, tmp_path) -> None:
    import ajustes_camara
    capa = CapaFalsa({"exposure_ms": 3.9062, "gain": 12.0})
    monkeypatch.setattr(ajustes_camara, "CapaWindowsDShow", lambda: capa)
    rc = sc.main(["--fijar", "exposure_ms=1.953,gain=12", "--puerto", PUERTO_1,
                  "--salida", str(tmp_path / "f.json"), "--timeout", "10"])
    assert rc == 0
    d = _json(tmp_path / "f.json")
    assert d["fijar"]["controls"] == {"exposure_ms": 1.953, "gain": 12.0, "exposure_manual": True}
    assert d["fijar"]["escritos"] == ["exposure_ms"] and d["fijar"]["segundos"] == 0.5
    assert capa.aplicados == [d["fijar"]["controls"]]


def test_main_fijar_que_no_aplica_devuelve_1_y_guarda(monkeypatch, tmp_path) -> None:
    import ajustes_camara

    class CapaQueFalla(CapaFalsa):
        def aplicar(self, puerto, controls):
            raise ajustes_camara.AjustesNoAplicados(
                "gain: declarado 12, leido 0",
                {"leidos": {"gain": 0.0}, "escritos": ["gain"], "set_false": ["gain"], "segundos": 0.4})
    monkeypatch.setattr(ajustes_camara, "CapaWindowsDShow", lambda: CapaQueFalla({}))
    rc = sc.main(["--fijar", "gain=12", "--puerto", PUERTO_1,
                  "--salida", str(tmp_path / "f.json"), "--timeout", "10"])
    assert rc == 1
    d = _json(tmp_path / "f.json")
    assert d["fijar"]["set_false"] == ["gain"] and "declarado 12" in d["fijar"]["error"]


def test_main_leer(monkeypatch, tmp_path) -> None:
    import ajustes_camara
    capa = CapaFalsa({"exposure_ms": 3.9062, "gain": 12.0, "focus": 332.0})
    monkeypatch.setattr(ajustes_camara, "CapaWindowsDShow", lambda: capa)
    rc = sc.main(["--leer", "--puerto", PUERTO_2, "--salida", str(tmp_path / "l.json"), "--timeout", "10"])
    assert rc == 0
    d = _json(tmp_path / "l.json")
    assert d["leer"]["leidos"]["focus"] == 332.0 and d["leer"]["puerto"] == PUERTO_2
    assert set(d["leer"]["leidos"]) == set(ajustes_camara.CONTROLES_CV2)


def _preparar_tras_msmf(monkeypatch, capa, vc) -> None:
    import ajustes_camara
    import camaras_uvc as cu
    monkeypatch.setattr(ajustes_camara, "CapaWindowsDShow", lambda: capa)
    monkeypatch.setattr(cu, "listar_camaras_msmf", lambda con_puerto=True: [_camara(1, PUERTO_1)])
    monkeypatch.setattr(sc.cv2, "VideoCapture", vc)


def test_tras_msmf_sin_diferencias(monkeypatch, tmp_path) -> None:
    capa = CapaFalsa({"exposure_ms": 3.9062, "gain": 12.0})
    abiertos: list[tuple] = []

    class VC(VCTestigo):
        def __init__(self, *a) -> None:
            abiertos.append(a)
            super().__init__(n=20)
    _preparar_tras_msmf(monkeypatch, capa, VC)
    rc = sc.main(["--tras-msmf", "--puerto", PUERTO_1, "--modo", "640x480:MJPG", "--fps", "90",
                  "--segundos", "0.05", "--salida", str(tmp_path / "t.json"), "--timeout", "10"])
    assert rc == 0
    assert abiertos == [(1, sc.cv2.CAP_MSMF)]        # el indice MSMF del puerto, por MSMF
    t = _json(tmp_path / "t.json")["tras_msmf"]
    assert t["antes"] == t["despues"] and t["diferencias"] == [] and capa.lecturas == 2
    assert t["msmf"]["pedido"] == {"ancho": 640, "alto": 480, "fourcc": "MJPG", "fps": 90.0}
    assert t["msmf"]["testigo"]["real"] == {"ancho": 16, "alto": 8} and "total_s" in t["msmf"]


def test_tras_msmf_con_diferencias_devuelve_1(monkeypatch, tmp_path) -> None:
    class CapaQueMSMFPisa(CapaFalsa):
        def leer(self, puerto, nombres):
            r = super().leer(puerto, nombres)
            self.estado["exposure_ms"] = 15.625     # la "camara" vuelve a -6 tras la primera lectura
            return r
    _preparar_tras_msmf(monkeypatch, CapaQueMSMFPisa({"exposure_ms": 3.9062, "gain": 12.0}), VCTestigo)
    rc = sc.main(["--tras-msmf", "--puerto", PUERTO_1, "--modo", "640x480:MJPG", "--fps", "90",
                  "--segundos", "0.05", "--salida", str(tmp_path / "t.json"), "--timeout", "10"])
    assert rc == 1
    t = _json(tmp_path / "t.json")["tras_msmf"]
    assert t["diferencias"] == ["exposure_ms: declarado 3.9062, leido 15.625"]


def test_tras_msmf_deja_lo_medido_en_el_estado_del_vigilante(monkeypatch, tmp_path) -> None:
    """B25 no se repite: el estado del vigilante ya trae `antes` y `msmf` si la captura se cuelga."""
    import json
    capa = CapaFalsa({"exposure_ms": 3.9062})
    visto: dict = {}

    class VigilanteFalso:
        def cancel(self) -> None:
            pass

    def vigilante(timeout, estado, salida):
        visto["estado"] = estado
        return VigilanteFalso()

    class VCColgado(VCTestigo):
        def read(self):
            raise KeyboardInterrupt    # la captura no vuelve; el vigilante haria os._exit
    _preparar_tras_msmf(monkeypatch, capa, VCColgado)
    monkeypatch.setattr(sc, "_vigilante", vigilante)
    with pytest.raises(KeyboardInterrupt):
        sc.main(["--tras-msmf", "--puerto", PUERTO_1, "--modo", "640x480:MJPG", "--fps", "90",
                 "--segundos", "1", "--salida", str(tmp_path / "t.json"), "--timeout", "10"])
    t = visto["estado"]["tras_msmf"]
    assert t["antes"]["exposure_ms"] == 3.9062 and t["msmf"]["indice"] == 1
    assert "despues" not in t
    json.dumps(visto["estado"])     # serializable tal cual, como lo escribiria el vigilante


def test_verificar_orden_dshow_con_ruta(monkeypatch) -> None:
    import camaras_uvc as cu
    cams = [_camara(0, PUERTO_1, "A"), _camara(1, PUERTO_2, "B")]
    pedidos: list[tuple] = []

    class VC(VCTestigo):
        def __init__(self, *a) -> None:
            pedidos.append(a)
            super().__init__(n=3)
    monkeypatch.setattr(cu, "listar_camaras_dshow", lambda con_puerto=True: cams)
    monkeypatch.setattr(sc.cv2, "VideoCapture", VC)
    filas: list[dict] = []
    sc.verificar_orden("DSHOW", 0.01, filas)
    assert pedidos == [(0, sc.cv2.CAP_DSHOW), (1, sc.cv2.CAP_DSHOW)]
    assert [f["ruta_puerto"] for f in filas] == [PUERTO_1, PUERTO_2]
    assert all(f["brillo_medio"] == 150.0 for f in filas)
