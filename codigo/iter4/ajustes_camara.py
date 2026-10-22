# -*- coding: utf-8 -*-
"""
ajustes_camara.py -- Los ajustes de una camara UVC en un formato que no depende
del sistema operativo, su validacion, y la capa que los aplica (meta 002, fase 2a).

El perfil (`camera.controls`) declara los ajustes con nombres y unidades
propios: `exposure_manual` (bool), `exposure_ms` (milisegundos, P10),
`auto_white_balance` (bool) y, con el valor crudo de UVC, `gain`, `brightness`,
`contrast`, `saturation`, `sharpness`, `gamma`, `backlight` y `focus`. No admite
`auto_exposure` (por DSHOW no se verifica: get da siempre -1, fase 1) ni
`wb_temperature` (la camara lo rechaza, fase 1).

Una capa por sistema los aplica y los lee de vuelta:
  - Windows (CapaWindowsDShow): OpenCV con cv2.CAP_DSHOW, en una apertura corta
    antes del video por MSMF (por MSMF OpenCV 4.11 no lee ni escribe los
    controles). Resuelve el indice DSHOW por la ruta del puerto
    (camaras_uvc.listar_camaras_dshow), lee, escribe SOLO lo que difiere (los
    ajustes persisten en la camara), relee siempre y libera. La exposicion se
    convierte a log2 de segundos (3.906 ms -> -8) y para si el valor no es
    representable. `exposure_manual` no es un valor que se escriba: se cumple
    al escribir `exposure` (lo que la fase 2a mide en AMCap).
  - Linux (V4L2): sitio sin escribir (B23).

Context7 (2026-10-21): OpenCV 4.13 `VideoCapture.set/get` (CAP_PROP_EXPOSURE,
GAIN, AUTO_WB, ... "only for those cameras that support"; set True no asegura
que el dispositivo acepto el valor: por eso se relee siempre).
"""
from __future__ import annotations

import math
import sys
import time
from typing import Callable, Protocol

import cv2

import camaras_uvc

# Nombres del perfil, en el orden en que se escriben.
NOMBRES: tuple[str, ...] = (
    "exposure_manual", "exposure_ms", "gain", "auto_white_balance", "brightness",
    "contrast", "saturation", "sharpness", "gamma", "backlight", "focus",
)
BOOLEANOS: tuple[str, ...] = ("exposure_manual", "auto_white_balance")

# Nombre del perfil -> propiedad de cv2 (los 10 que se escriben; exposure_manual no).
CONTROLES_CV2: dict[str, int] = {
    "exposure_ms": cv2.CAP_PROP_EXPOSURE,
    "gain": cv2.CAP_PROP_GAIN,
    "auto_white_balance": cv2.CAP_PROP_AUTO_WB,
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast": cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "sharpness": cv2.CAP_PROP_SHARPNESS,
    "gamma": cv2.CAP_PROP_GAMMA,
    "backlight": cv2.CAP_PROP_BACKLIGHT,
    "focus": cv2.CAP_PROP_FOCUS,
}

# Lo que mide la sonda (sondear_camara.py --controles leer|probar): los 12 del
# plan de la fase 1, con los nombres crudos; una sola fuente para la sonda.
CONTROLES_SONDA: dict[str, int] = {
    "exposure": cv2.CAP_PROP_EXPOSURE,
    "auto_exposure": cv2.CAP_PROP_AUTO_EXPOSURE,
    "gain": cv2.CAP_PROP_GAIN,
    "auto_wb": cv2.CAP_PROP_AUTO_WB,
    "wb_temperature": cv2.CAP_PROP_WB_TEMPERATURE,
    "brightness": cv2.CAP_PROP_BRIGHTNESS,
    "contrast": cv2.CAP_PROP_CONTRAST,
    "saturation": cv2.CAP_PROP_SATURATION,
    "sharpness": cv2.CAP_PROP_SHARPNESS,
    "gamma": cv2.CAP_PROP_GAMMA,
    "backlight": cv2.CAP_PROP_BACKLIGHT,
    "focus": cv2.CAP_PROP_FOCUS,
}

# Nombres que el perfil NO admite, con el porque.
RECHAZADOS: dict[str, str] = {
    "auto_exposure": "no verificable por DSHOW (get da siempre -1; fase 1); "
                     "la exposicion es manual: exposure_manual: true + exposure_ms",
    "wb_temperature": "la camara lo rechaza (fase 1); usa auto_white_balance",
    "exposure": "usa exposure_ms (milisegundos) con exposure_manual: true (P10)",
    "auto_wb": "usa auto_white_balance",
}

TOLERANCIA = 1e-3


# ----------------------------------------------------------------------------
# Funciones puras (con prueba, sin camara)
# ----------------------------------------------------------------------------

def validar_controles(controls: dict) -> dict:
    """Los controles del perfil, validados y normalizados (bool o float).

    ValueError con la lista de problemas: nombre desconocido o rechazado, tipo
    equivocado, exposure_ms <= 0, exposure_ms sin exposure_manual: true, o
    exposure_manual: true sin exposure_ms (no habria nada que escribir).
    """
    if not isinstance(controls, dict):
        raise ValueError(f"controls tiene que ser un dict, no {type(controls).__name__}")
    problemas: list[str] = []
    salida: dict = {}
    for nombre, valor in controls.items():
        if nombre in RECHAZADOS:
            problemas.append(f"'{nombre}' no se admite: {RECHAZADOS[nombre]}")
        elif nombre not in NOMBRES:
            problemas.append(f"'{nombre}' desconocido; validos: {list(NOMBRES)}")
        elif nombre in BOOLEANOS:
            if not isinstance(valor, bool):
                problemas.append(f"'{nombre}' tiene que ser true/false, no {valor!r}")
            else:
                salida[nombre] = valor
        elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
            problemas.append(f"'{nombre}' tiene que ser un numero, no {valor!r}")
        else:
            salida[nombre] = float(valor)
    if "exposure_ms" in salida:
        if salida["exposure_ms"] <= 0:
            problemas.append(f"exposure_ms tiene que ser > 0, no {salida['exposure_ms']}")
        if salida.get("exposure_manual") is not True:
            problemas.append("exposure_ms exige exposure_manual: true")
    elif salida.get("exposure_manual") is True:
        problemas.append("exposure_manual: true sin exposure_ms: no hay exposicion que fijar")
    if problemas:
        raise ValueError("controls del perfil: " + "; ".join(problemas))
    return salida


def dshow_a_exposicion_ms(valor: int | float) -> float:
    """El valor de exposicion de DSHOW (log2 de segundos, definicion de KS) en ms."""
    return 1000.0 * (2.0 ** float(valor))


def exposicion_ms_a_dshow(ms: float, tolerancia: float = 0.02) -> int:
    """`ms` como log2 de segundos entero; ValueError si no es 1000*2^k dentro de `tolerancia`."""
    if ms is None or ms <= 0:
        raise ValueError(f"exposure_ms tiene que ser > 0, no {ms}")
    k = int(round(math.log2(ms / 1000.0)))
    exacto = dshow_a_exposicion_ms(k)
    if abs(ms - exacto) > tolerancia * exacto:
        cercanos = ", ".join(f"{dshow_a_exposicion_ms(j):.4g} ms ({j})"
                             for j in (k - 1, k, k + 1))
        raise ValueError(f"exposure_ms={ms} no es 1000*2^k (DSHOW escribe log2 de segundos); "
                         f"validos cercanos: {cercanos}")
    return k


def a_nativos_dshow(controls: dict) -> dict[str, float]:
    """Nombre del perfil -> valor para cv2.CAP_PROP_* por DSHOW (exposicion convertida)."""
    validos = validar_controles(controls)
    nativos: dict[str, float] = {}
    for nombre in CONTROLES_CV2:
        if nombre not in validos:
            continue
        valor = validos[nombre]
        if nombre == "exposure_ms":
            nativos[nombre] = float(exposicion_ms_a_dshow(valor))
        elif nombre in BOOLEANOS:
            nativos[nombre] = 1.0 if valor else 0.0
        else:
            nativos[nombre] = float(valor)
    return nativos


def de_nativos_dshow(nativos: dict[str, float]) -> dict:
    """Lo leido por DSHOW en las unidades del perfil (exposicion en ms, bool para los auto)."""
    perfil: dict = {}
    for nombre, valor in nativos.items():
        if nombre == "exposure_ms":
            perfil[nombre] = round(dshow_a_exposicion_ms(valor), 4)
        elif nombre in BOOLEANOS:
            perfil[nombre] = bool(round(float(valor)))
        else:
            perfil[nombre] = float(valor)
    return perfil


def comparar_controles(declarados: dict, leidos: dict, tolerancia: float = TOLERANCIA) -> list[str]:
    """Los declarados que no coinciden con lo leido (`exposure_manual` no se lee)."""
    difs: list[str] = []
    for nombre, valor in declarados.items():
        if nombre == "exposure_manual":
            continue
        leido = leidos.get(nombre)
        if leido is None:
            difs.append(f"{nombre}: sin lectura (declarado {valor})")
        elif abs(float(leido) - float(valor)) > tolerancia:
            difs.append(f"{nombre}: declarado {valor:g}, leido {float(leido):g}")
    return difs


# ----------------------------------------------------------------------------
# La capa por sistema
# ----------------------------------------------------------------------------

class CapaAjustes(Protocol):
    def leer(self, puerto: str, nombres: list[str]) -> dict[str, float]: ...

    def aplicar(self, puerto: str, controls: dict) -> dict: ...


class AjustesNoAplicados(RuntimeError):
    """Algun control no quedo en lo declarado tras escribirlo; `resultado` trae lo leido."""

    def __init__(self, mensaje: str, resultado: dict) -> None:
        super().__init__(mensaje)
        self.resultado = resultado


class CapaWindowsDShow:
    """Aplica y lee los controles por OpenCV DSHOW, en una apertura corta por puerto.

    `listar` y `abrir` se inyectan en las pruebas: `listar()` da las camaras
    DSHOW (camaras_uvc.CamaraUVC con `ruta_puerto`); `abrir(indice)` da un
    VideoCapture. No pone FOURCC, tamano ni FPS: solo controles.
    """

    def __init__(self, listar: Callable[[], list] | None = None,
                 abrir: Callable[[int], object] | None = None) -> None:
        self._listar = listar if listar is not None else camaras_uvc.listar_camaras_dshow
        self._abrir = abrir if abrir is not None else \
            (lambda i: cv2.VideoCapture(int(i), cv2.CAP_DSHOW))

    def indice(self, puerto: str) -> int:
        """El indice DSHOW de la camara del puerto (ValueError si 0 o mas de 1)."""
        return camaras_uvc.resolver_indice(puerto, self._listar())

    def _abrir_cap(self, puerto: str):
        i = self.indice(puerto)
        cap = self._abrir(i)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"[ajustes_camara] no abre el indice DSHOW {i} del puerto {puerto}")
        return i, cap

    @staticmethod
    def _leer_nativos(cap, nombres: list[str]) -> dict[str, float]:
        return {n: float(cap.get(CONTROLES_CV2[n])) for n in nombres}

    @staticmethod
    def _nombres_validos(nombres: list[str]) -> list[str]:
        malos = [n for n in nombres if n not in CONTROLES_CV2]
        if malos:
            raise ValueError(f"no se leen por DSHOW: {malos}; validos: {list(CONTROLES_CV2)}")
        return list(nombres)

    def leer(self, puerto: str, nombres: list[str]) -> dict[str, float]:
        """Lo que la camara del puerto tiene hoy, en las unidades del perfil."""
        nombres = self._nombres_validos(nombres)
        _i, cap = self._abrir_cap(puerto)
        try:
            nativos = self._leer_nativos(cap, nombres)
        finally:
            cap.release()
        return de_nativos_dshow(nativos)

    def aplicar(self, puerto: str, controls: dict) -> dict:
        """Escribe solo lo que difiere, relee y compara. AjustesNoAplicados si algo no coincide.

        Devuelve {"indice", "antes", "leidos", "escritos", "set_false", "segundos"}:
        `antes` y `leidos` en las unidades del perfil; `leidos_nativos` y
        `antes_nativos` tal como los da cv2.
        """
        t0 = time.monotonic()
        nativos = a_nativos_dshow(controls)
        nombres = list(nativos)
        i, cap = self._abrir_cap(puerto)
        escritos: list[str] = []
        set_false: list[str] = []
        try:
            antes = self._leer_nativos(cap, nombres)
            for nombre, valor in nativos.items():
                if abs(antes[nombre] - valor) <= TOLERANCIA:
                    continue
                escritos.append(nombre)
                if not cap.set(CONTROLES_CV2[nombre], valor):
                    set_false.append(nombre)
            despues = self._leer_nativos(cap, nombres)
        finally:
            cap.release()
        difs = comparar_controles(nativos, despues)
        resultado = {
            "indice": i,
            "antes": de_nativos_dshow(antes),
            "leidos": de_nativos_dshow(despues),
            "antes_nativos": antes,
            "leidos_nativos": despues,
            "escritos": escritos,
            "set_false": set_false,
            "diferencias": difs,
            "segundos": round(time.monotonic() - t0, 2),
        }
        if difs:
            raise AjustesNoAplicados(
                f"[ajustes_camara] la camara del puerto {puerto} (DSHOW {i}) no quedo en lo "
                f"declarado: {'; '.join(difs)} (escritos: {escritos or 'ninguno'}; "
                f"set False: {set_false or 'ninguno'})", resultado)
        return resultado


def capa_para_plataforma(plataforma: str = sys.platform) -> CapaAjustes:
    """La capa del sistema: win32 -> CapaWindowsDShow; linux -> V4L2, sin escribir (B23)."""
    if plataforma == "win32":
        return CapaWindowsDShow()
    if plataforma.startswith("linux"):
        raise NotImplementedError("capa V4L2 sin escribir (B23, Explorar el tracker en una Jetson)")
    raise NotImplementedError(f"sin capa de ajustes para {plataforma!r}")
