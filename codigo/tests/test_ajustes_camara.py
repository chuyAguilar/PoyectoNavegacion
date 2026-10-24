"""ajustes_camara.py sin camara: validacion, conversiones y la capa DSHOW con falsos (meta 002, fase 2a)."""
from __future__ import annotations

import pytest

from camera import controls as ac
from camera import uvc as cu

PUERTO_1 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)"
PUERTO_2 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)"
# Lo que la camara 1 tenia el 2026-10-21 (leer_gs1_dshow_cambiado.json), en unidades del perfil.
PERFIL_GS1 = {"exposure_manual": True, "exposure_ms": 3.906, "gain": 12, "auto_white_balance": True,
              "brightness": 0, "contrast": 0, "saturation": 56, "sharpness": 0, "gamma": 110,
              "backlight": 54, "focus": 0}
P = ac.CONTROLES_CV2


# ----------------------------------------------------------------------------
# validar_controles
# ----------------------------------------------------------------------------

def test_validar_perfil_completo() -> None:
    v = ac.validar_controles(PERFIL_GS1)
    assert v["exposure_manual"] is True and v["gain"] == 12.0 and isinstance(v["gain"], float)
    assert list(v) == list(PERFIL_GS1)


def test_validar_desconocido() -> None:
    with pytest.raises(ValueError, match="'iso' desconocido"):
        ac.validar_controles({"iso": 100})


@pytest.mark.parametrize("nombre", ["auto_exposure", "wb_temperature", "exposure", "auto_wb"])
def test_validar_rechaza_con_el_porque(nombre: str) -> None:
    with pytest.raises(ValueError, match=f"'{nombre}' no se admite"):
        ac.validar_controles({nombre: 1})


def test_validar_exposure_ms_sin_manual() -> None:
    with pytest.raises(ValueError, match="exige exposure_manual: true"):
        ac.validar_controles({"exposure_ms": 3.906})
    with pytest.raises(ValueError, match="exige exposure_manual: true"):
        ac.validar_controles({"exposure_ms": 3.906, "exposure_manual": False})


def test_validar_manual_sin_exposure_ms() -> None:
    with pytest.raises(ValueError, match="sin exposure_ms"):
        ac.validar_controles({"exposure_manual": True})


def test_validar_tipos() -> None:
    with pytest.raises(ValueError, match="tiene que ser true/false"):
        ac.validar_controles({"auto_white_balance": 1})
    with pytest.raises(ValueError, match="tiene que ser un numero"):
        ac.validar_controles({"gain": True})
    with pytest.raises(ValueError, match="tiene que ser un numero"):
        ac.validar_controles({"gain": "12"})
    with pytest.raises(ValueError, match="> 0"):
        ac.validar_controles({"exposure_manual": True, "exposure_ms": 0})
    with pytest.raises(ValueError, match="dict"):
        ac.validar_controles([("gain", 1)])


def test_validar_junta_todos_los_problemas() -> None:
    with pytest.raises(ValueError) as e:
        ac.validar_controles({"iso": 1, "auto_exposure": 0, "gain": "x"})
    assert "'iso'" in str(e.value) and "'auto_exposure'" in str(e.value) and "'gain'" in str(e.value)


# ----------------------------------------------------------------------------
# Conversiones
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("ms,esperado", [(3.906, -8), (7.8125, -7), (3.90625, -8), (1.953, -9),
                                         (15.625, -6), (0.488, -11), (1000.0, 0)])
def test_exposicion_ms_a_dshow(ms: float, esperado: int) -> None:
    assert ac.exposicion_ms_a_dshow(ms) == esperado


def test_exposicion_ms_a_dshow_rechaza_con_los_validos_cercanos() -> None:
    with pytest.raises(ValueError) as e:
        ac.exposicion_ms_a_dshow(5.0)
    texto = str(e.value)
    assert "3.906 ms (-8)" in texto and "7.812 ms (-7)" in texto and "1.953 ms (-9)" in texto
    with pytest.raises(ValueError, match="> 0"):
        ac.exposicion_ms_a_dshow(0)


def test_exposicion_ida_y_vuelta() -> None:
    for k in range(-13, 1):
        assert ac.exposicion_ms_a_dshow(ac.dshow_a_exposicion_ms(k)) == k
    assert ac.dshow_a_exposicion_ms(-8) == pytest.approx(3.90625)


def test_a_nativos_dshow() -> None:
    nativos = ac.a_nativos_dshow(PERFIL_GS1)
    assert "exposure_manual" not in nativos
    assert nativos["exposure_ms"] == -8.0 and nativos["auto_white_balance"] == 1.0
    assert nativos["gain"] == 12.0 and nativos["focus"] == 0.0
    assert list(nativos) == [n for n in ac.CONTROLES_CV2 if n in PERFIL_GS1]
    assert ac.a_nativos_dshow({"auto_white_balance": False, "gain": 3}) == \
        {"gain": 3.0, "auto_white_balance": 0.0}


def test_a_nativos_dshow_valida() -> None:
    with pytest.raises(ValueError):
        ac.a_nativos_dshow({"exposure_ms": 5.0, "exposure_manual": True})


def test_de_nativos_dshow() -> None:
    perfil = ac.de_nativos_dshow({"exposure_ms": -8.0, "auto_white_balance": 1.0, "gain": 12.0})
    assert perfil == {"exposure_ms": 3.9062, "auto_white_balance": True, "gain": 12.0}


def test_comparar_controles() -> None:
    declarados = {"exposure_manual": True, "exposure_ms": -8.0, "gain": 12.0, "focus": 0.0}
    assert ac.comparar_controles(declarados, {"exposure_ms": -8.0, "gain": 12.0, "focus": 0.0}) == []
    difs = ac.comparar_controles(declarados, {"exposure_ms": -6.0, "gain": 12.0})
    assert difs == ["exposure_ms: declarado -8, leido -6", "focus: sin lectura (declarado 0.0)"]


# ----------------------------------------------------------------------------
# CapaWindowsDShow con un VideoCapture y un listar falsos
# ----------------------------------------------------------------------------

class CapFalso:
    def __init__(self, valores: dict[int, float], rechazar: set[int] = frozenset(),
                 abre: bool = True) -> None:
        self.valores = dict(valores)
        self.rechazar = set(rechazar)
        self.abre = abre
        self.sets: list[tuple[int, float]] = []
        self.gets = 0
        self.liberado = 0

    def isOpened(self) -> bool:
        return self.abre

    def get(self, prop: int) -> float:
        self.gets += 1
        return self.valores.get(prop, 0.0)

    def set(self, prop: int, valor: float) -> bool:
        self.sets.append((prop, valor))
        if prop in self.rechazar:
            return False
        self.valores[prop] = valor
        return True

    def release(self) -> None:
        self.liberado += 1


def _camaras(*puertos: str) -> list[cu.CamaraUVC]:
    return [cu.CamaraUVC(i, "Global Shutter Camera", f"\\\\?\\usb#vid_32e4&pid_0234&mi_00#{i}#x",
                         "32E4", "0234", str(i), ruta_puerto=p) for i, p in enumerate(puertos)]


def _capa(cap: CapFalso, puertos=(PUERTO_1, PUERTO_2)) -> tuple[ac.CapaWindowsDShow, list[int]]:
    abiertos: list[int] = []

    def abrir(i: int):
        abiertos.append(i)
        return cap
    return ac.CapaWindowsDShow(listar=lambda: _camaras(*puertos), abrir=abrir), abiertos


def _nativos_gs1() -> dict[int, float]:
    return {P[n]: v for n, v in ac.a_nativos_dshow(PERFIL_GS1).items()}


def test_aplicar_escribe_solo_lo_que_difiere_y_relee() -> None:
    valores = _nativos_gs1()
    valores[P["gain"]] = 0.0            # la camara tiene gain 0; el perfil pide 12
    valores[P["exposure_ms"]] = -6.0    # y exposicion -6; el perfil pide -8
    cap = CapFalso(valores)
    capa, abiertos = _capa(cap)
    r = capa.aplicar(PUERTO_2, PERFIL_GS1)
    assert abiertos == [1]                       # el indice DSHOW del puerto 2
    assert r["indice"] == 1
    assert cap.sets == [(P["exposure_ms"], -8.0), (P["gain"], 12.0)]
    assert r["escritos"] == ["exposure_ms", "gain"] and r["set_false"] == []
    assert r["antes"]["gain"] == 0.0 and r["leidos"]["gain"] == 12.0
    assert r["leidos"]["exposure_ms"] == pytest.approx(3.90625, abs=1e-3)
    assert r["diferencias"] == [] and r["segundos"] >= 0
    assert cap.liberado == 1
    assert cap.gets == 2 * len(ac.a_nativos_dshow(PERFIL_GS1))   # lee antes y relee siempre


def test_aplicar_sin_diferencias_no_escribe_pero_relee() -> None:
    cap = CapFalso(_nativos_gs1())
    capa, _ = _capa(cap)
    r = capa.aplicar(PUERTO_1, PERFIL_GS1)
    assert cap.sets == [] and r["escritos"] == []
    assert cap.gets == 2 * len(r["leidos"]) and cap.liberado == 1
    assert r["forzado"] is False


def test_aplicar_forzado_escribe_aunque_coincida_y_relee() -> None:
    """La marca de fabrica sin escribir saltaba (2026-10-22): --fijar --forzar la escribe igual."""
    valores = {P["focus"]: 332.0}
    cap = CapFalso(valores)
    capa, abiertos = _capa(cap)
    r = capa.aplicar(PUERTO_2, {"focus": 332}, forzar=True)
    assert abiertos == [1] and cap.sets == [(P["focus"], 332.0)]
    assert r["escritos"] == ["focus"] and r["forzado"] is True
    assert r["antes"] == {"focus": 332.0} and r["leidos"] == {"focus": 332.0}
    assert cap.gets == 2 and cap.liberado == 1          # lee antes, relee despues
    # Sin forzar, lo mismo no escribe nada (el backend sigue asi).
    cap2 = CapFalso(dict(valores))
    capa2, _ = _capa(cap2)
    assert capa2.aplicar(PUERTO_2, {"focus": 332})["escritos"] == [] and cap2.sets == []


def test_aplicar_para_si_no_coincide_tras_escribir() -> None:
    valores = _nativos_gs1()
    valores[P["gain"]] = 0.0
    cap = CapFalso(valores, rechazar={P["gain"]})
    capa, _ = _capa(cap)
    with pytest.raises(ac.AjustesNoAplicados, match="gain: declarado 12, leido 0") as e:
        capa.aplicar(PUERTO_1, PERFIL_GS1)
    assert e.value.resultado["set_false"] == ["gain"] and e.value.resultado["escritos"] == ["gain"]
    assert isinstance(e.value, RuntimeError)
    assert cap.liberado == 1


def test_aplicar_para_si_el_puerto_no_esta() -> None:
    cap = CapFalso(_nativos_gs1())
    capa, abiertos = _capa(cap, puertos=(PUERTO_1,))
    with pytest.raises(ValueError, match="no coincide"):
        capa.aplicar(PUERTO_2, PERFIL_GS1)
    assert abiertos == [] and cap.sets == []


def test_aplicar_para_si_no_abre_y_libera() -> None:
    cap = CapFalso(_nativos_gs1(), abre=False)
    capa, _ = _capa(cap)
    with pytest.raises(RuntimeError, match="no abre el indice DSHOW 0"):
        capa.aplicar(PUERTO_1, PERFIL_GS1)
    assert cap.liberado == 1 and cap.sets == []


def test_aplicar_libera_si_get_revienta() -> None:
    class CapRoto(CapFalso):
        def get(self, prop):
            raise OSError("se fue la camara")
    cap = CapRoto({})
    capa, _ = _capa(cap)
    with pytest.raises(OSError):
        capa.aplicar(PUERTO_1, PERFIL_GS1)
    assert cap.liberado == 1


def test_aplicar_valida_antes_de_abrir() -> None:
    cap = CapFalso(_nativos_gs1())
    capa, abiertos = _capa(cap)
    with pytest.raises(ValueError, match="no se admite"):
        capa.aplicar(PUERTO_1, {"auto_exposure": 0})
    assert abiertos == []


def test_leer_en_unidades_del_perfil() -> None:
    cap = CapFalso(_nativos_gs1())
    capa, abiertos = _capa(cap)
    leidos = capa.leer(PUERTO_1, ["exposure_ms", "gain", "auto_white_balance", "focus"])
    assert leidos == {"exposure_ms": 3.9062, "gain": 12.0, "auto_white_balance": True, "focus": 0.0}
    assert abiertos == [0] and cap.sets == [] and cap.liberado == 1


def test_leer_rechaza_nombres_que_no_se_leen() -> None:
    cap = CapFalso({})
    capa, abiertos = _capa(cap)
    with pytest.raises(ValueError, match="no se leen por DSHOW"):
        capa.leer(PUERTO_1, ["exposure_manual"])
    assert abiertos == []


def test_capa_para_plataforma() -> None:
    assert isinstance(ac.capa_para_plataforma("win32"), ac.CapaWindowsDShow)
    with pytest.raises(NotImplementedError, match="V4L2"):
        ac.capa_para_plataforma("linux")
    with pytest.raises(NotImplementedError):
        ac.capa_para_plataforma("darwin")


def test_controles_sonda_son_los_12_y_los_del_perfil_10() -> None:
    assert len(ac.CONTROLES_SONDA) == 12 and len(ac.CONTROLES_CV2) == 10
    assert set(ac.NOMBRES) == set(ac.CONTROLES_CV2) | {"exposure_manual"}
    assert set(ac.RECHAZADOS) & set(ac.NOMBRES) == set()
