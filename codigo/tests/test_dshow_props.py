"""`camera.dshow_props` sin camara (meta 007, fase 7b · Las dos camaras a la vez en Windows, partes A y B).

La tabla `CONTROLES_COM` cubre los 10 de `controls.CONTROLES_CV2` en el mismo
orden y con los grupos y propiedades de `strmif.h`; `a_perfil` da lo mismo que
`controls.de_nativos_dshow` para los mismos valores crudos; `a_nativo` va y
vuelve; `CapaWindowsCOM.leer` con un dispositivo falso lee en unidades del
perfil, cierra siempre y no escribe nada; `CapaWindowsCOM.aplicar` (parte B, J7)
escribe solo lo que difiere en valor o bandera, relee, devuelve las mismas claves
que `CapaWindowsDShow.aplicar`, respeta `forzar`, cambia solo la bandera de
`auto_white_balance`, anota `set_false` y lanza `AjustesNoAplicados`; desde la
parte B `capa_para_plataforma("win32")` es `CapaWindowsCOM`; `abrir_filtro` para
con 0 o mas de 1 camara en el puerto antes de tocar COM y fuera de Windows con
OSError; y la suite niega `abrir_filtro` (B34, conftest).
"""
from __future__ import annotations

import sys

import pytest

from camera import controls as ac
from camera import dshow_props as dp
from camera import uvc as cu

from .conftest import RealHardwareForbidden

PUERTO_1 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(3)"
PUERTO_2 = "PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(4)"
# La funcion real, tomada al importar: la suite la sustituye en cada prueba (conftest, B34).
# Solo se llama aqui con casos que paran ANTES de tocar COM.
ABRIR_FILTRO_REAL = dp.abrir_filtro

# Lo que gs1 tenia en el P-7w (corta_gs1_tracker.txt, 2026-11-04), en crudo: (valor, flags).
CRUDOS_GS1 = {
    "exposure_ms": (-10, dp.FLAG_MANUAL), "gain": (11, dp.FLAG_MANUAL),
    "auto_white_balance": (4600, dp.FLAG_MANUAL), "brightness": (0, dp.FLAG_MANUAL),
    "contrast": (0, dp.FLAG_MANUAL), "saturation": (56, dp.FLAG_MANUAL),
    "sharpness": (0, dp.FLAG_MANUAL), "gamma": (110, dp.FLAG_MANUAL),
    "backlight": (54, dp.FLAG_MANUAL), "focus": (500, dp.FLAG_MANUAL),
}
LEIDOS_GS1 = {"exposure_ms": 0.9766, "gain": 11.0, "auto_white_balance": False, "brightness": 0.0,
              "contrast": 0.0, "saturation": 56.0, "sharpness": 0.0, "gamma": 110.0,
              "backlight": 54.0, "focus": 500.0}


class DispositivoFalso:
    """Un `Dispositivo` que recuerda lo que le piden; `crudos` es lo que 'tiene la camara'.

    `rechaza`: controles cuyo `Set` devuelve False y no cambia nada (el driver lo
    rechaza); `ignora`: controles cuyo `Set` devuelve True pero la camara no lo
    toma (la relectura lo delata, como en la fase 2a con la marca sin escribir).
    """

    def __init__(self, crudos: dict[str, tuple[int, int]], sin: set[str] = frozenset(),
                 rechaza: set[str] = frozenset(), ignora: set[str] = frozenset()) -> None:
        self.valores = {dp.CONTROLES_COM[n]: v for n, v in crudos.items()}
        self.sin = {dp.CONTROLES_COM[n] for n in sin}
        self.rechaza = {dp.CONTROLES_COM[n] for n in rechaza}
        self.ignora = {dp.CONTROLES_COM[n] for n in ignora}
        self.gets: list[tuple[str, int]] = []
        self.sets: list[tuple] = []
        self.cerrado = 0
        self.indice = 0

    def get(self, grupo: str, propiedad: int) -> dp.Lectura:
        self.gets.append((grupo, propiedad))
        if (grupo, propiedad) in self.sin:
            raise OSError(f"Get({propiedad}) fallo: HRESULT 0x80070490")
        valor, flags = self.valores[(grupo, propiedad)]
        return dp.Lectura(valor, bool(flags & dp.FLAG_AUTO), flags)

    def set(self, grupo: str, propiedad: int, valor: int, auto: bool) -> bool:
        self.sets.append((grupo, propiedad, valor, auto))
        if (grupo, propiedad) in self.rechaza:
            return False
        if (grupo, propiedad) not in self.ignora:
            self.valores[(grupo, propiedad)] = (valor, dp.FLAG_AUTO if auto else dp.FLAG_MANUAL)
        return True

    def close(self) -> None:
        self.cerrado += 1


def _capa(dispositivo: DispositivoFalso) -> tuple[dp.CapaWindowsCOM, list[str]]:
    abiertos: list[str] = []

    def abrir(puerto: str):
        abiertos.append(puerto)
        return dispositivo
    return dp.CapaWindowsCOM(abrir=abrir), abiertos


# ----------------------------------------------------------------------------
# La tabla
# ----------------------------------------------------------------------------

def test_controles_com_son_los_10_de_cv2_en_el_mismo_orden() -> None:
    assert list(dp.CONTROLES_COM) == list(ac.CONTROLES_CV2)
    assert all(grupo in dp.GRUPOS for grupo, _ in dp.CONTROLES_COM.values())
    assert dp.CONTROLES_COM["exposure_ms"] == ("camara", 4) and dp.CONTROLES_COM["focus"] == ("camara", 6)
    assert dp.CONTROLES_COM["auto_white_balance"] == ("procamp", 7)
    assert dp.CONTROLES_COM["gain"] == ("procamp", 9) and dp.CONTROLES_COM["backlight"] == ("procamp", 8)
    assert dp.CONTROLES_COM["brightness"] == ("procamp", 0) and dp.CONTROLES_COM["gamma"] == ("procamp", 5)
    # Ninguna propiedad repetida dentro de su grupo.
    assert len(set(dp.CONTROLES_COM.values())) == 10


def test_constantes_de_strmif() -> None:
    assert dp.FLAG_AUTO == 1 and dp.FLAG_MANUAL == 2
    assert (dp.VT_QUERY_INTERFACE, dp.VT_GET_RANGE, dp.VT_SET, dp.VT_GET) == (0, 3, 4, 5)
    assert dp.VT_BIND_TO_OBJECT == 8 and cu.VT_BIND_TO_STORAGE == 9
    assert dp.PROCAMP["WhiteBalance"] == 7 and dp.PROCAMP["Gain"] == 9 and dp.CAMARA["Exposure"] == 4
    import uuid
    for iid in (dp.IID_IBASE_FILTER, dp.IID_IAM_VIDEO_PROC_AMP, dp.IID_IAM_CAMERA_CONTROL):
        uuid.UUID(iid)
    assert dp.IID_IAM_VIDEO_PROC_AMP != dp.IID_IAM_CAMERA_CONTROL


# ----------------------------------------------------------------------------
# Conversiones
# ----------------------------------------------------------------------------

def test_a_perfil_da_lo_mismo_que_de_nativos_dshow() -> None:
    """Los mismos valores crudos que leeria cv2 por DSHOW tienen que dar el mismo perfil (A0)."""
    nativos_cv2 = {n: float(v if n != "auto_white_balance" else (1 if f & dp.FLAG_AUTO else 0))
                   for n, (v, f) in CRUDOS_GS1.items()}
    esperado = ac.de_nativos_dshow(nativos_cv2)
    leido = {n: dp.a_perfil(n, dp.Lectura(v, bool(f & dp.FLAG_AUTO), f)) for n, (v, f) in CRUDOS_GS1.items()}
    assert leido == esperado == LEIDOS_GS1
    assert dp.a_perfil("exposure_ms", dp.Lectura(-8, False, 2)) == pytest.approx(3.9062)
    assert dp.a_perfil("auto_white_balance", dp.Lectura(4600, True, 1)) is True
    assert dp.a_perfil("auto_white_balance", dp.Lectura(4600, False, 2)) is False
    assert isinstance(dp.a_perfil("gain", dp.Lectura(11, False)), float)


def test_a_perfil_rechaza_lo_que_no_se_lee() -> None:
    with pytest.raises(ValueError, match="no se lee por COM"):
        dp.a_perfil("exposure_manual", dp.Lectura(1, False))


def test_a_nativo_ida_y_vuelta() -> None:
    assert dp.a_nativo("exposure_ms", 0.977) == (-10, False)
    assert dp.a_nativo("exposure_ms", 3.906) == (-8, False)
    assert dp.a_nativo("gain", 11.0) == (11, False) and dp.a_nativo("focus", 500) == (500, False)
    assert dp.a_nativo("auto_white_balance", True) == (0, True)
    assert dp.a_nativo("auto_white_balance", False) == (0, False)
    for n, v in LEIDOS_GS1.items():
        valor, auto = dp.a_nativo(n, v)
        assert dp.a_perfil(n, dp.Lectura(valor if n != "auto_white_balance" else 4600, auto)) == v


@pytest.mark.parametrize("nombre,valor", [("exposure_ms", 5.0), ("gain", 11.5), ("gain", "11"),
                                          ("gain", True), ("auto_white_balance", 1), ("iso", 1)])
def test_a_nativo_rechaza(nombre: str, valor) -> None:
    with pytest.raises(ValueError):
        dp.a_nativo(nombre, valor)


# ----------------------------------------------------------------------------
# CapaWindowsCOM con un dispositivo falso
# ----------------------------------------------------------------------------

def test_leer_en_unidades_del_perfil_y_cierra() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    leidos = capa.leer(PUERTO_1, list(ac.CONTROLES_CV2))
    assert leidos == LEIDOS_GS1
    assert abiertos == [PUERTO_1] and d.cerrado == 1 and d.sets == []
    assert d.gets == [dp.CONTROLES_COM[n] for n in ac.CONTROLES_CV2]     # en el orden del perfil


def test_leer_la_marca_sola_no_escribe_nada() -> None:
    """Lo que hace `WebcamBackend._comprobar_marca`: solo `focus`."""
    d = DispositivoFalso(CRUDOS_GS1)
    capa, _ = _capa(d)
    assert capa.leer(PUERTO_1, ["focus"]) == {"focus": 500.0}
    assert d.gets == [("camara", 6)] and d.sets == [] and d.cerrado == 1


def test_leer_nativos_trae_valor_auto_y_flags() -> None:
    d = DispositivoFalso({"auto_white_balance": (4600, dp.FLAG_AUTO), "gain": (11, dp.FLAG_MANUAL)})
    capa, _ = _capa(d)
    crudos = capa.leer_nativos(PUERTO_2, ["gain", "auto_white_balance"])
    assert crudos["auto_white_balance"] == dp.Lectura(4600, True, 1)
    assert crudos["gain"] == dp.Lectura(11, False, 2)
    assert capa.leer(PUERTO_2, ["auto_white_balance"]) == {"auto_white_balance": True}


def test_leer_cierra_si_get_revienta() -> None:
    d = DispositivoFalso(CRUDOS_GS1, sin={"gamma"})
    capa, _ = _capa(d)
    with pytest.raises(OSError, match="0x80070490"):
        capa.leer(PUERTO_1, ["gain", "gamma", "focus"])
    assert d.cerrado == 1 and d.sets == []


def test_leer_rechaza_nombres_antes_de_abrir() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    with pytest.raises(ValueError, match="no se leen por COM"):
        capa.leer(PUERTO_1, ["exposure_manual"])
    assert abiertos == [] and d.cerrado == 0


# ----------------------------------------------------------------------------
# CapaWindowsCOM.aplicar (parte B, J7): el contrato de CapaWindowsDShow.aplicar
# ----------------------------------------------------------------------------

# El perfil de gs1 (los controls y la marca), en unidades del perfil.
CONTROLS_GS1 = {"exposure_manual": True, "exposure_ms": 0.977, "gain": 11, "auto_white_balance": False,
                "brightness": 0, "contrast": 0, "saturation": 56, "sharpness": 0, "gamma": 110,
                "backlight": 54}
CLAVES_APLICAR = {"indice", "antes", "leidos", "antes_nativos", "leidos_nativos", "escritos",
                  "set_false", "diferencias", "forzado", "segundos"}


def test_aplicar_sin_diferencias_no_escribe_nada_y_relee() -> None:
    """Lo del tracker en el PC con la camara ya puesta: `Ajustes aplicados (escritos: ninguno)`."""
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    r = capa.aplicar(PUERTO_1, CONTROLS_GS1)
    assert r["escritos"] == [] and r["set_false"] == [] and r["diferencias"] == []
    assert d.sets == [] and abiertos == [PUERTO_1] and d.cerrado == 1
    assert r["forzado"] is False and r["indice"] == 0 and isinstance(r["segundos"], float)
    # Las 9 del perfil (exposure_manual no se lee), en unidades del perfil, como las da cv2.
    esperado = {n: v for n, v in LEIDOS_GS1.items() if n != "focus"}
    assert r["leidos"] == esperado and r["antes"] == esperado
    assert r["leidos_nativos"] == {n: float(CRUDOS_GS1[n][0]) if n != "auto_white_balance" else 0.0
                                   for n in esperado}
    assert r["leidos_flags"] == {n: dp.FLAG_MANUAL for n in esperado}
    # Dos lecturas (antes y despues) de los 9, en el orden del perfil.
    assert d.gets == 2 * [dp.CONTROLES_COM[n] for n in esperado]


def test_aplicar_escribe_solo_lo_que_difiere_y_lo_relee() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, _ = _capa(d)
    r = capa.aplicar(PUERTO_1, {**CONTROLS_GS1, "gain": 12, "exposure_ms": 3.906})
    assert r["escritos"] == ["exposure_ms", "gain"] and r["set_false"] == []
    assert d.sets == [("camara", 4, -8, False), ("procamp", 9, 12, False)]
    assert r["antes"]["gain"] == 11.0 and r["leidos"]["gain"] == 12.0
    assert r["antes"]["exposure_ms"] == 0.9766 and r["leidos"]["exposure_ms"] == 3.9062
    assert r["leidos_nativos"]["exposure_ms"] == -8.0 and r["antes_nativos"]["exposure_ms"] == -10.0
    assert d.cerrado == 1


def test_aplicar_devuelve_las_mismas_claves_que_la_capa_de_cv2() -> None:
    """`camera.backend` lee `leidos` y `escritos`; el resto es para la sonda. Nada de menos."""
    d = DispositivoFalso(CRUDOS_GS1)
    capa, _ = _capa(d)
    r = capa.aplicar(PUERTO_1, {**CONTROLS_GS1, "gain": 12})
    assert CLAVES_APLICAR <= set(r)
    assert set(r) - CLAVES_APLICAR == {"leidos_flags"}
    import json
    json.dumps(r)        # el JSON de la sonda (--fijar) lo guarda tal cual


def test_aplicar_escribe_si_solo_difiere_la_bandera() -> None:
    """La camara tiene el valor correcto pero en automatico: hay que escribirlo en manual."""
    crudos = {**CRUDOS_GS1, "exposure_ms": (-10, dp.FLAG_AUTO)}
    d = DispositivoFalso(crudos)
    capa, _ = _capa(d)
    r = capa.aplicar(PUERTO_1, CONTROLS_GS1)
    assert r["escritos"] == ["exposure_ms"] and d.sets == [("camara", 4, -10, False)]
    assert r["leidos_flags"]["exposure_ms"] == dp.FLAG_MANUAL


def test_aplicar_auto_white_balance_cambia_solo_la_bandera() -> None:
    """true: `Set(WhiteBalance, <el valor que tenga la camara>, Auto)`; false, lo mismo con Manual."""
    d = DispositivoFalso(CRUDOS_GS1)
    capa, _ = _capa(d)
    r = capa.aplicar(PUERTO_1, {**CONTROLS_GS1, "auto_white_balance": True})
    assert r["escritos"] == ["auto_white_balance"]
    assert d.sets == [("procamp", 7, 4600, True)]          # 4600: el valor de la camara, no 0
    assert r["leidos"]["auto_white_balance"] is True and r["antes"]["auto_white_balance"] is False
    assert r["leidos_nativos"]["auto_white_balance"] == 1.0
    # Y de vuelta a manual, conservando el valor.
    r2 = capa.aplicar(PUERTO_1, CONTROLS_GS1)
    assert d.sets[-1] == ("procamp", 7, 4600, False) and r2["leidos"]["auto_white_balance"] is False


def test_aplicar_forzar_escribe_todo_aunque_coincida() -> None:
    """La marca se da de alta con `--fijar focus=500 --forzar` (CONTEXT §4.19): se escribe igual."""
    d = DispositivoFalso(CRUDOS_GS1)
    capa, _ = _capa(d)
    r = capa.aplicar(PUERTO_1, {"focus": 500}, forzar=True)
    assert r["escritos"] == ["focus"] and r["forzado"] is True and r["diferencias"] == []
    assert d.sets == [("camara", 6, 500, False)] and r["leidos"] == {"focus": 500.0}
    r2 = capa.aplicar(PUERTO_1, CONTROLS_GS1, forzar=True)
    assert len(r2["escritos"]) == 9 and r2["diferencias"] == []


def test_aplicar_que_no_queda_lanza_ajustes_no_aplicados_con_el_resultado() -> None:
    d = DispositivoFalso(CRUDOS_GS1, ignora={"gain"})
    capa, _ = _capa(d)
    with pytest.raises(ac.AjustesNoAplicados, match="gain: declarado 12, leido 11") as ei:
        capa.aplicar(PUERTO_1, {**CONTROLS_GS1, "gain": 12})
    r = ei.value.resultado
    assert r["escritos"] == ["gain"] and r["set_false"] == [] and r["diferencias"] == ["gain: declarado 12, leido 11"]
    assert "escritos: ['gain']" in str(ei.value) and "[dshow_props]" in str(ei.value)
    assert d.cerrado == 1


def test_aplicar_set_false_se_anota_y_la_relectura_decide() -> None:
    d = DispositivoFalso(CRUDOS_GS1, rechaza={"gamma"})
    capa, _ = _capa(d)
    with pytest.raises(ac.AjustesNoAplicados, match="set False: \\['gamma'\\]") as ei:
        capa.aplicar(PUERTO_1, {**CONTROLS_GS1, "gamma": 120})
    assert ei.value.resultado["set_false"] == ["gamma"] and ei.value.resultado["escritos"] == ["gamma"]


def test_aplicar_valida_antes_de_abrir() -> None:
    d = DispositivoFalso(CRUDOS_GS1)
    capa, abiertos = _capa(d)
    with pytest.raises(ValueError, match="exige exposure_manual"):
        capa.aplicar(PUERTO_1, {"exposure_ms": 0.977})
    with pytest.raises(ValueError, match="no es 1000\\*2\\^k"):
        capa.aplicar(PUERTO_1, {"exposure_manual": True, "exposure_ms": 1.5})
    with pytest.raises(ValueError, match="'iso' desconocido"):
        capa.aplicar(PUERTO_1, {"iso": 1})
    assert abiertos == [] and d.sets == [] and d.cerrado == 0


def test_aplicar_cierra_si_get_revienta() -> None:
    d = DispositivoFalso(CRUDOS_GS1, sin={"gamma"})
    capa, _ = _capa(d)
    with pytest.raises(OSError, match="0x80070490"):
        capa.aplicar(PUERTO_1, CONTROLS_GS1)
    assert d.cerrado == 1 and d.sets == []


def test_nativos_para_escribir_y_como_cv2() -> None:
    n = dp.nativos_para_escribir(CONTROLS_GS1)
    assert list(n) == [k for k in ac.CONTROLES_CV2 if k != "focus"]       # el orden del perfil
    assert n["exposure_ms"] == (-10, False) and n["auto_white_balance"] == (0, False)
    assert dp.como_cv2("auto_white_balance", dp.Lectura(4600, True, 1)) == 1.0
    assert dp.como_cv2("gain", dp.Lectura(11, False, 2)) == 11.0
    # Las unidades nativas que compara `aplicar` son las de `controls.a_nativos_dshow`.
    assert {k: dp.como_cv2(k, dp.Lectura(v, a)) for k, (v, a) in n.items()} == ac.a_nativos_dshow(CONTROLS_GS1)


def test_capa_cumple_el_protocolo_de_controls() -> None:
    assert callable(getattr(dp.CapaWindowsCOM, "leer")) and callable(getattr(dp.CapaWindowsCOM, "aplicar"))
    import inspect
    assert list(inspect.signature(dp.CapaWindowsCOM.leer).parameters) == \
        list(inspect.signature(ac.CapaWindowsDShow.leer).parameters)
    assert list(inspect.signature(dp.CapaWindowsCOM.aplicar).parameters) == \
        list(inspect.signature(ac.CapaWindowsDShow.aplicar).parameters)


def test_la_capa_sin_falso_no_toca_com(monkeypatch) -> None:
    """B34: `abrir_filtro` esta negado a la suite; `CapaWindowsCOM()` a secas lo llamaria."""
    with pytest.raises(RealHardwareForbidden, match="dshow_props.abrir_filtro"):
        dp.CapaWindowsCOM().leer(PUERTO_1, ["focus"])
    with pytest.raises(RealHardwareForbidden, match="dshow_props.abrir_filtro"):
        dp.CapaWindowsCOM().aplicar(PUERTO_1, {"gain": 11})


def test_capa_para_plataforma_win32_es_la_com_desde_la_parte_b() -> None:
    """J7: el tracker en Windows lee la marca y aplica los ajustes por COM, sin abrir video.
    `CapaWindowsDShow` sigue existiendo para la sonda (`--capa cv2`, `--comparar-capas`)."""
    assert isinstance(ac.capa_para_plataforma("win32"), dp.CapaWindowsCOM)
    assert ac.capa_para_plataforma("win32")._abrir is dp.abrir_filtro      # el de verdad (negado en la suite)
    assert callable(ac.CapaWindowsDShow.aplicar)


def test_dispositivo_com_set_llama_a_la_vtable_con_la_bandera(monkeypatch) -> None:
    """`Set(Property, lValue, Flags)` en el indice 4 de la vtable, con Manual (2) o Auto (1)."""
    llamadas: list = []

    def metodo(obj, indice, restype, *argtypes):
        def fn(o, *args):
            llamadas.append((obj, indice, args))
            return 0 if args[0] != 99 else -2147024809     # E_INVALIDARG para la propiedad 99
        return fn
    monkeypatch.setattr(cu, "_metodo", metodo)
    d = dp._DispositivoCOM(1, None, 11, 22, None, False)     # 11 y 22 hacen de punteros
    assert d.set("procamp", 9, 12, False) is True
    assert d.set("camara", 4, -10, False) is True
    assert d.set("procamp", 7, 4600, True) is True
    assert d.set("procamp", 99, 0, False) is False and d.ultimo_hr == -2147024809
    assert llamadas == [(11, dp.VT_SET, (9, 12, dp.FLAG_MANUAL)), (22, dp.VT_SET, (4, -10, dp.FLAG_MANUAL)),
                        (11, dp.VT_SET, (7, 4600, dp.FLAG_AUTO)), (11, dp.VT_SET, (99, 0, dp.FLAG_MANUAL))]
    with pytest.raises(ValueError, match="grupo"):
        d.set("otro", 0, 0, False)
    with pytest.raises(OSError, match="no expone IAMCameraControl"):
        dp._DispositivoCOM(1, None, 11, None, None, False).set("camara", 4, 0, False)


def test_dispositivo_com_close_es_idempotente() -> None:
    class Ole32:
        llamadas = 0

        def CoUninitialize(self):
            Ole32.llamadas += 1
    d = dp._DispositivoCOM(0, None, None, None, Ole32(), com_propio=True)
    d.close()
    d.close()
    assert Ole32.llamadas == 1
    with pytest.raises(ValueError, match="grupo"):
        d.get("otro", 0)
    with pytest.raises(OSError, match="no expone IAMCameraControl"):
        d.get("camara", 4)


# ----------------------------------------------------------------------------
# abrir_filtro: lo que para antes de COM
# ----------------------------------------------------------------------------

def _camaras(*puertos: str) -> list[cu.CamaraUVC]:
    return [cu.CamaraUVC(i, "Global Shutter Camera", f"\\\\?\\usb#vid_32e4&pid_0234&mi_00#{i}#x",
                         "32E4", "0234", str(i), ruta_puerto=p) for i, p in enumerate(puertos)]


def test_abrir_filtro_para_si_el_puerto_tiene_0_camaras() -> None:
    with pytest.raises(ValueError, match="no coincide con ninguna"):
        ABRIR_FILTRO_REAL(PUERTO_2, listar=lambda: _camaras(PUERTO_1))


def test_abrir_filtro_para_si_el_puerto_tiene_2_camaras() -> None:
    with pytest.raises(ValueError, match="coincide con 2 camaras"):
        ABRIR_FILTRO_REAL(PUERTO_1, listar=lambda: _camaras(PUERTO_1, PUERTO_1))


def test_abrir_filtro_fuera_de_windows_es_oserror(monkeypatch) -> None:
    monkeypatch.setattr(dp.sys, "platform", "linux")
    with pytest.raises(OSError, match="solo Windows"):
        ABRIR_FILTRO_REAL(PUERTO_1, listar=lambda: _camaras(PUERTO_1))


def test_abrir_filtro_por_defecto_lista_por_dshow() -> None:
    """Sin `listar`, enumera con `camera.uvc.listar_camaras_dshow` (negado en la suite: B34)."""
    with pytest.raises(RealHardwareForbidden, match="listar_camaras_dshow"):
        ABRIR_FILTRO_REAL(PUERTO_1)
    assert dp.abrir_filtro is not ABRIR_FILTRO_REAL      # la suite lo tiene sustituido


def test_el_modulo_no_importa_cv2_por_su_cuenta() -> None:
    """Lo COM va por ctypes y `camera.uvc`; las unidades, por `camera.controls` (una sola fuente)."""
    from pathlib import Path
    src = Path(dp.__file__).read_text(encoding="utf-8")
    assert "import cv2" not in src and "from camera import uvc" in src and "from camera import controls" in src
    assert sys.platform  # el modulo importa en cualquier sistema; solo abrir_filtro exige Windows
