"""sondear_camara.py sin camara: un VideoCapture falso (meta 002, fase 1)."""
from __future__ import annotations

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


def test_controles_son_los_12_del_plan() -> None:
    assert list(C) == ["exposure", "auto_exposure", "gain", "auto_wb", "wb_temperature",
                       "brightness", "contrast", "saturation", "sharpness", "gamma",
                       "backlight", "focus"]


def test_control_aceptado_y_restaurado() -> None:
    cap = CapFalso({C["exposure"]: -6.0}, {C["exposure"]})
    (fila,) = sc.sondear_controles(cap, ["exposure"])
    assert fila["inicial"] == -6.0
    assert fila["acepta"] is True
    assert [p["valor"] for p in fila["pruebas"]] == [-5.0, -7.0]
    assert all(p["coincide"] for p in fila["pruebas"])
    assert fila["restaurado"] is True and cap.get(C["exposure"]) == -6.0


def test_control_no_aceptado() -> None:
    cap = CapFalso({}, set())
    (fila,) = sc.sondear_controles(cap, ["focus"])
    assert fila["acepta"] is False
    assert all(not p["set_ok"] for p in fila["pruebas"])


def test_control_redondeado_no_coincide() -> None:
    cap = CapFalso({C["wb_temperature"]: 4600.0}, {C["wb_temperature"]},
                   redondeo={C["wb_temperature"]: 1000.0})
    (fila,) = sc.sondear_controles(cap, ["wb_temperature"])
    assert fila["acepta"] is False
    assert fila["pruebas"][0]["leido"] == 5000.0


def test_auto_usa_candidatos_y_se_restaura_al_final() -> None:
    cap = CapFalso({C["auto_exposure"]: 1.0, C["exposure"]: -5.0},
                   {C["auto_exposure"], C["exposure"]})
    filas = sc.sondear_controles(cap, ["auto_exposure", "exposure"])
    auto = filas[0]
    assert 1.0 not in [p["valor"] for p in auto["pruebas"]]
    assert auto["acepta"] is True
    # La restauracion final pone el auto despues de los numericos.
    ultimos = [prop for prop, _ in cap.sets[-2:]]
    assert ultimos == [C["exposure"], C["auto_exposure"]]
    assert all(f["restaurado"] for f in filas)


def test_solo_leer_no_llama_a_set() -> None:
    cap = CapFalso({C["gain"]: 12.0}, {C["gain"]})
    (fila,) = sc.sondear_controles(cap, ["gain"], solo_leer=True)
    assert cap.sets == []
    assert fila["inicial"] == 12.0 and fila["acepta"] is None


def test_control_desconocido() -> None:
    with pytest.raises(ValueError, match="desconocidos"):
        sc.sondear_controles(CapFalso({}, set()), ["iso"])


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


def test_main_exige_argumentos(tmp_path) -> None:
    with pytest.raises(SystemExit):
        sc.main(["--source", "0", "--salida", str(tmp_path / "s.json"), "--timeout", "10"])
