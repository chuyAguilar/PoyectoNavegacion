"""calibration.capture_stereo_board sin camara (meta 006, fase 7a · El asistente de captura del tablero).

Dos fuentes falsas de frames sinteticos a 640x480 (`tablero_sintetico.renderizar_vista`, con las dos
camaras de `test_calibrate_extrinsics`) y un reloj falso que solo avanza cuando el bucle pide un frame:
  - un guion de tramos (en movimiento, quieto en A, moviendose, quieto en B, otra vez A, C fuera de la
    vista de gs2, D solo 0.6 s, E, y F con una rafaga sacudida): toma A, B y E (T01-T03), rechaza la
    rafaga sacudida (queda como T04) y la repeticion va a T04_r2, que es la que lee el calculo;
  - de punta a punta: 20 poses por el asistente y despues `calibrate_extrinsics.main --desde-vistas`
    sobre su carpeta (la prueba de que el formato no cambio);
  - las funciones puras (`diferencia_vistas`, `Quietud`, `emparejar_por_hora`, la maquina de estados);
  - los topes y las salidas: el tope de la sesion, una camara que deja de dar frames, la comprobacion
    que no vuelve, la segunda camara que no abre, la salida que ya tiene algo y `q`.
Ninguna prueba abre una camara (`no_real_camera` y `sin_camara_real`) ni una ventana (`sin_ventanas`).
Mientras una rafaga se comprueba (en un hilo), las fuentes falsas paran su reloj y esperan al hilo: el
guion no depende de lo que tarde el detector.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import cv2
import numpy as np
import pytest

from calibration import calibrate_camera as cc
from calibration import calibrate_extrinsics as ce
from calibration import capture_stereo_board as csb
from fusion import geometry as g

from . import tablero_sintetico as ts
from . import test_calibrate_extrinsics as tce
from .conftest import CODIGO_DIR

COLS, ROWS, SQ = 8, 5, 24.86
SHAPE = tce.SHAPE_640
KS = {"gs1": tce.K_640, "gs2": tce.K2_640}
INTR = {c: {"K": K, "dist": tce.SIN_DIST, "shape": SHAPE} for c, K in KS.items()}
OBJP = cc.construir_objp(COLS, ROWS, SQ)
T_21 = tce.camara_2(30.0, (-250.0, 10.0, 60.0))        # T_gs2<-gs1, la de la sesion de test_calibrate_extrinsics
TICK = 1.0 / 12.0                                       # una vuelta del bucle en el reloj falso
DT_GS2_MS = 1000.0 / 90.0 - 4.0                         # en la rafaga falsa, lo que tarda gs2 tras gs1


@pytest.fixture(autouse=True)
def sin_camara_real(monkeypatch):
    """Ninguna prueba de este modulo llega a `create_backend` con un perfil real (como en test_calibrar_camara)."""
    def _prohibido(*_a, **_k):
        raise AssertionError("una prueba intento abrir una camara real (create_backend)")
    monkeypatch.setattr(csb, "create_backend", _prohibido)


@pytest.fixture(autouse=True)
def sin_ventanas(monkeypatch):
    """Ninguna ventana: lo que se llamaria queda apuntado. `teclas` es lo que devuelve `pollKey`."""
    visto = {"namedWindow": 0, "imshow": 0, "destroyAllWindows": 0, "teclas": []}
    monkeypatch.setattr(csb.cv2, "namedWindow", lambda *a, **k: visto.__setitem__("namedWindow", visto["namedWindow"] + 1))
    monkeypatch.setattr(csb.cv2, "imshow", lambda *a, **k: visto.__setitem__("imshow", visto["imshow"] + 1))
    monkeypatch.setattr(csb.cv2, "destroyAllWindows", lambda: visto.__setitem__("destroyAllWindows", visto["destroyAllWindows"] + 1))
    monkeypatch.setattr(csb.cv2, "pollKey", lambda: visto["teclas"].pop(0) if visto["teclas"] else -1)
    return visto


# ----------------------------------------------------------------------------
# El mundo falso: poses, guion, reloj y fuentes
# ----------------------------------------------------------------------------

def poses_distintas(n: int, semilla: int = 5) -> list[np.ndarray]:
    """`n` poses `T_gs1<-tablero` vistas enteras por las dos camaras y distintas entre si con margen
    (12 grados o 48 mm: la pose medida no es exactamente la del guion)."""
    _o, _a, _b, poses = tce.escena(3 * n, T_21, KS["gs1"], tce.SIN_DIST, KS["gs2"], tce.SIN_DIST, SHAPE, semilla=semilla,
                                   z_mm=(420.0, 520.0), ang_max=0.35, margen=70, candidatas=1500)
    out: list[np.ndarray] = []
    for Ta in poses:
        if csb.es_distinta(Ta, out, COLS, ROWS, SQ, 1.2 * csb.UMBRAL_DEG, 1.2 * csb.UMBRAL_MM):
            out.append(Ta)
    assert len(out) >= n, len(out)
    return out[:n]


def render(cam: str, Ta: np.ndarray) -> np.ndarray:
    Tc = Ta if cam == "gs1" else T_21 @ Ta
    return ts.renderizar_vista(KS[cam], cv2.Rodrigues(Tc[:3, :3])[0].flatten(), Tc[:3, 3], COLS, ROWS, SQ, SHAPE)


def movida(Ta: np.ndarray, dx_mm: float) -> np.ndarray:
    T = Ta.copy()
    T[0, 3] += dx_mm
    return T


def _previa(cam: str, Ta: np.ndarray):
    return csb.vista_previa(render(cam, Ta), COLS, ROWS, OBJP, KS[cam], tce.SIN_DIST, SQ, "clasico", 1.0)


def fuera_de_gs2(Ta: np.ndarray) -> np.ndarray:
    """La pose `Ta` desplazada hasta que gs1 sigue viendo el tablero entero y gs2 ya no."""
    for dx in [s * d for d in range(20, 400, 10) for s in (1.0, -1.0)]:
        if _previa("gs1", movida(Ta, dx)) is not None and _previa("gs2", movida(Ta, dx)) is None:
            return movida(Ta, dx)
    raise AssertionError("ninguna pose desplazada queda entera en gs1 y fuera de gs2")


class Mundo:
    """El guion: tramos `(nombre, duracion_s, T | None, velocidad_mm_s)` seguidos; el ultimo dura para
    siempre. `sacudir[nombre] = n` mueve 1 px el tablero en los frames impares de las `n` primeras rafagas
    de ese tramo. El reloj avanza un `tick` por vuelta (lo pide la primera camara) y se para mientras el
    asistente comprueba (`congelar`). En la rafaga cada camara va a 90 fps y gs2 llega `DT_GS2_MS` despues
    de gs1 (7.11 ms; al gs1 siguiente le faltan 4)."""

    def __init__(self, tramos, asistente, n_frames: int, tick: float = TICK, congelar: bool = True, sacudir=None) -> None:
        self.tramos, self.a, self.n_frames, self.tick, self.congelar = list(tramos), asistente, int(n_frames), float(tick), congelar
        self.sacudir = dict(sacudir or {})
        self.t = 0.0
        self._cache: dict = {}
        self._k = {"gs1": 0, "gs2": 0}
        self.fin = sum(d for _n, d, _T, _v in self.tramos)

    def reloj(self) -> float:
        return self.t

    def tramo(self, t: float):
        t0 = 0.0
        for nombre, dur, T, vel in self.tramos:
            if t < t0 + dur:
                return nombre, T, vel, t - t0
            t0 += dur
        nombre, dur, T, vel = self.tramos[-1]
        return nombre, T, 0.0, dur

    def frame(self, cam: str, rafaga_k: int | None) -> np.ndarray:
        nombre, T, vel, dt = self.tramo(self.t)
        if T is None:
            return np.full((SHAPE[1], SHAPE[0]), 128, dtype=np.uint8)
        if vel:
            return render(cam, movida(T, vel * dt))
        sacudida = rafaga_k is not None and rafaga_k % 2 == 1 and self.sacudir.get(nombre, 0) > 0
        clave = (nombre, cam, sacudida)
        if clave not in self._cache:
            self._cache[clave] = render(cam, movida(T, T[2, 3] / 600.0) if sacudida else T)     # ~1 px en gs1
        return self._cache[clave]

    def pedir(self, cam: str):
        estado = self.a.estado
        rafaga_k = None
        if estado == "quieto" and self._k[cam] < self.n_frames:
            rafaga_k = self._k[cam]
            self._k[cam] += 1
            self.t += 0.004 if cam == "gs1" else 1.0 / 90.0 - 0.004
        else:
            if estado != "quieto" and any(self._k.values()):
                nombre = self.tramo(self.t)[0]
                if self.sacudir.get(nombre, 0) > 0:
                    self.sacudir[nombre] -= 1
                self._k = {"gs1": 0, "gs2": 0}
            if estado == "comprobando" and self.congelar:
                for hilo in threading.enumerate():      # el mundo espera a que acabe la comprobacion
                    if hilo.name == "comprobar-rafaga":
                        hilo.join(20.0)
            elif cam == "gs1":
                self.t += self.tick
        return self.frame(cam, rafaga_k), self.t


class Fuente:
    """La interfaz de `FrameGrabber` sobre el mundo falso."""

    def __init__(self, cam: str, mundo: Mundo, muere_en: float | None = None) -> None:
        self.cam, self.mundo, self.muere_en = cam, mundo, muere_en
        self.failed = False
        self.frames_read = 0

    def next_frame(self, timeout: float):
        if self.muere_en is not None and self.mundo.t >= self.muere_en:
            return None
        frame, t = self.mundo.pedir(self.cam)
        self.frames_read += 1
        return frame, t, self.frames_read


def nuevo_asistente(objetivo: int, minimo: int) -> csb.Asistente:
    return csb.Asistente(COLS, ROWS, SQ, INTR, csb.UMBRAL_DEG, csb.UMBRAL_MM, csb.QUIETO_S, csb.QUIETO_PX, objetivo, minimo)


def correr(tramos, carpeta, objetivo: int, minimo: int, n_frames: int = 5, limite: float | None = None, tick: float = TICK,
           sacudir=None, congelar: bool = True, muere=None, q_al_final: bool = True) -> dict:
    """Una sesion entera con el mundo falso. Devuelve el resultado, el asistente, el mundo y lo que sono."""
    a = nuevo_asistente(objetivo, minimo)
    mundo = Mundo(tramos, a, n_frames, tick, congelar, sacudir)
    fuentes = {c: Fuente(c, mundo, (muere or {}).get(c)) for c in ("gs1", "gs2")}
    pitidos, ventanas = [], []
    r = csb.capturar_sesion(fuentes, INTR, a, carpeta, mundo.fin + 60.0 if limite is None else limite, n_frames, 0.3,
                            clock=mundo.reloj, leer_tecla=lambda: ord("q") if (q_al_final and mundo.t >= mundo.fin) else 255,
                            mostrar=lambda img: ventanas.append(img.shape), pitido=pitidos.append,
                            detector_previa="clasico", escala_previa=1.0, meta={"prueba": True})
    return {"r": r, "a": a, "mundo": mundo, "pitidos": pitidos, "ventanas": ventanas,
            "sesion": json.loads((carpeta / "sesion.json").read_text(encoding="utf-8"))}


@pytest.fixture(scope="module")
def poses():
    return poses_distintas(20)


@pytest.fixture(scope="module")
def guion(tmp_path_factory, poses):
    """La sesion del guion del plan, una sola vez: A, B y E se toman; F se rechaza (sacudida) y se repite."""
    A, B, D, E, F, M = poses[:6]
    C = fuera_de_gs2(A)
    v = 30.0 * M[2, 3] / 600.0                         # mm/s que son ~30 px/s en gs1
    # Quieto 1.4 s donde el plan dice 1.2: con un tick de 1/12 s la captura cae entre 1.0 y 1.25 s del tramo.
    tramos = [("mov1", 0.8, M, v), ("A", 1.4, A, 0.0), ("mov2", 0.6, M, -v), ("B", 1.4, B, 0.0), ("A2", 1.4, A, 0.0),
              ("C", 1.4, C, 0.0), ("D", 0.6, D, 0.0), ("E", 1.4, E, 0.0), ("F", 2.0, F, 0.0), ("mov3", 0.5, M, v),
              ("F2", 1.4, F, 0.0), ("fin", 0.3, None, 0.0)]
    carpeta = tmp_path_factory.mktemp("guion") / "datos"
    s = correr(tramos, carpeta, objetivo=10, minimo=4, n_frames=5, sacudir={"F": 1})
    return {**s, "carpeta": carpeta, "verdad": {"T01": A, "T02": B, "T03": E, "T04": F}}


# ----------------------------------------------------------------------------
# El guion: lo que se toma y lo que no
# ----------------------------------------------------------------------------

def test_el_guion_toma_solo_A_B_y_E_y_repite_la_sacudida(guion) -> None:
    r, a, ses = guion["r"], guion["a"], guion["sesion"]
    assert r["fin"] == "q" and r["codigo"] == 0 and r["tomadas"] == 4 and r["rechazadas"] == 1      # q con >= minimo
    assert [t["posicion"] for t in a.tomadas] == ["T01", "T02", "T03", "T04"] and r["posiciones"] == ["T01", "T02", "T03", "T04_r2"]
    # Ni durante el movimiento, ni la A repetida, ni C (gs2 no la ve), ni D (0.6 s): cada tomada es la pose que toca.
    for t in a.tomadas:
        deg, mm = csb.diferencia_vistas(t["T"], guion["verdad"][t["posicion"]], COLS, ROWS, SQ)
        assert deg < 1.0 and mm < 1.0, (t["posicion"], deg, mm)
    assert [x["posicion"] + x["sufijo"] for x in ses["rechazadas"]] == ["T04"]
    assert "se movio" in ses["rechazadas"][0]["motivo"] and "no estaba quieto" in a.rechazadas[0]["motivo"]
    assert guion["pitidos"] == ["tomada", "tomada", "tomada", "rechazada", "tomada"]
    assert a.estado in ("sin_tablero", "repetida") and not a.terminado and a.posicion_siguiente == "T05"
    assert set(guion["ventanas"]) == {(480 + csb.ALTO_FRANJA, 1280, 3)}


def test_el_guion_escribe_el_formato_del_calculo(guion) -> None:
    carpeta = guion["carpeta"]
    nombres = sorted(p.name for p in carpeta.iterdir() if p.is_dir())
    assert nombres == sorted([f"T0{k}_{c}_frames" for k in (1, 2, 3, 4) for c in ("gs1", "gs2")]
                             + ["T04_gs1_r2_frames", "T04_gs2_r2_frames"])
    for n in nombres:                                   # 5 PNG en gris por camara y vista, tambien la rechazada
        pngs = sorted((carpeta / n).glob("*.png"))
        assert [p.name for p in pngs] == [f"frame_{k:05d}.png" for k in range(5)]
        assert cv2.imread(str(pngs[0]), cv2.IMREAD_UNCHANGED).shape == (480, 640)
    pos = ce.listar_posiciones(carpeta)
    assert list(pos) == ["T01", "T02", "T03", "T04"] and pos["T04"]["intento"] == 2
    assert pos["T04"]["carpetas"]["gs2"].name == "T04_gs2_r2_frames" and pos["T01"]["intento"] == 1
    filas = ce.detectar_posiciones(carpeta, INTR, COLS, ROWS, SQ, "sb", 2, 0.3)       # los 2 ultimos: los 5, en sesion.json
    assert [f["nombre"] for f in filas] == ["T01", "T02", "T03", "T04"] and all(f["usable"] for f in filas)
    assert all(f["camaras"][c]["n_detectados"] == 2 and f["camaras"][c]["movimiento_px"] == 0.0 for f in filas for c in ("gs1", "gs2"))
    # La rechazada, mirada como la mira el calculo, tampoco vale (y por eso gana la _r2).
    mala = ce.esquinas_de_posicion(carpeta / "T04_gs1_frames", COLS, ROWS, "sb", 5, 0.3)
    assert mala["esquinas"] is None and 0.3 < mala["movimiento_px"] < 1.0
    # Los frames guardados son los de la fuente, sin perdida.
    assert np.array_equal(cv2.imread(str(carpeta / "T01_gs1_frames" / "frame_00000.png"), cv2.IMREAD_UNCHANGED),
                          render("gs1", guion["verdad"]["T01"]))


def test_el_guion_deja_sesion_json(guion) -> None:
    ses, r = guion["sesion"], guion["r"]
    assert ses["estado"] == "terminada" and ses["fin"] == "q" and ses["codigo"] == 0 and ses["meta"] == {"prueba": True}
    assert ses["tablero"] == {"cols": COLS, "rows": ROWS, "square_mm": SQ} and ses["parametros"]["detector_final"] == "sb"
    assert [t["posicion"] + t["sufijo"] for t in ses["tomadas"]] == ["T01", "T02", "T03", "T04_r2"]
    for t in ses["tomadas"]:
        assert set(t["camaras"]) == {"gs1", "gs2"} and t["carpetas"]["gs1"] == f"{t['posicion']}_gs1{t['sufijo']}_frames"
        for c in ("gs1", "gs2"):
            m = t["camaras"][c]
            assert m["n_detectados"] == 5 and m["movimiento_px"] == 0.0 and "esquinas" not in m
            assert 380.0 < m["z_mm"] < 620.0 and 0.0 <= m["inclinacion_deg"] < 40.0 and m["rms_pnp_px"] < 0.5 and len(m["T"]) == 4
        # La rafaga del reloj falso: gs2 llega 7.11 ms despues de su gs1 y 4 ms antes del siguiente, asi
        # que el mas cercano en hora al frame i de gs1 es el i - 1 de gs2 (salvo el primero).
        assert [(e["i"], e["j"]) for e in t["emparejado"]] == [(0, 0), (1, 0), (2, 1), (3, 2), (4, 3)]
        assert [e["dt_ms"] for e in t["emparejado"]] == pytest.approx([DT_GS2_MS, -4.0, -4.0, -4.0, -4.0], abs=1e-6)
        assert t["dt_max_ms"] == pytest.approx(DT_GS2_MS, abs=1e-6) and len(t["horas"]["gs2"]) == 5
    assert r["dt_max_ms"] == pytest.approx(DT_GS2_MS, abs=1e-6) and r["sesion"].endswith("sesion.json")
    assert ses["variedad"]["n"] == 4 and ses["variedad"]["camara"] == "gs1" and ses["variedad"] == r["variedad"]
    assert set(ses["fps"]) == {"gs1", "gs2"} and len(ses["hz_ventana"]) >= 1
    assert ses["hz_ventana"][0] >= 11.0         # 12 por el tick, mas las vueltas con el reloj parado


# ----------------------------------------------------------------------------
# De punta a punta: 20 poses por el asistente y el calculo sobre su carpeta
# ----------------------------------------------------------------------------

def test_veinte_poses_y_el_calculo_sobre_su_carpeta(tmp_path, poses) -> None:
    """Con 2 frames por vista en los dos lados (el plan lo admite, por el tiempo de la suite). R y T salen
    de esquinas detectadas (`sb`) en vistas renderizadas, no proyectadas: la cota es la de la prueba de
    punta a punta de la fase 7 (< 1 mm, < 0.2 grados), no el 0.01 mm de las esquinas sinteticas exactas."""
    tramos = [(f"P{k:02d}", 1.3, T, 0.0) for k, T in enumerate(poses, start=1)]
    carpeta = tmp_path / "datos"
    s = correr(tramos, carpeta, objetivo=20, minimo=18, n_frames=2, tick=0.125, q_al_final=False)
    r = s["r"]
    assert r["fin"] == "objetivo" and r["codigo"] == 0 and r["tomadas"] == 20 and r["rechazadas"] == 0
    assert r["posiciones"] == [f"T{k:02d}" for k in range(1, 21)] and s["a"].terminado
    for t, T in zip(s["a"].tomadas, poses):
        deg, mm = csb.diferencia_vistas(t["T"], T, COLS, ROWS, SQ)
        assert deg < 1.0 and mm < 1.0
    intr = {c: tce._yml(tmp_path / f"intrinsecos_{c}.yml", KS[c], detector="sb") for c in ("gs1", "gs2")}
    reporte = tmp_path / "rep.json"
    rc = ce.main(["--desde-vistas", str(carpeta), "--intrinsecos", f"gs1={intr['gs1']}", f"gs2={intr['gs2']}",
                  "--cols", str(COLS), "--rows", str(ROWS), "--square-mm", f"{SQ}", "--detector", "sb",
                  "--frames-por-vista", "2", "--max-movimiento-px", "0.3", "--min-vistas", "15", "--n-control", "3",
                  "--semilla", "0", "--montaje", "pinzas", "--reporte", str(reporte), "--timeout", "120"])
    e = json.loads(reporte.read_text(encoding="utf-8"))
    res = e["resultado"]
    assert rc == 0, res["fallos"]
    assert e["usables"] == 20 and res["n_vistas_usadas"] == 17 and res["n_control"] == 3 and e["orden"]["incoherentes"] == []
    assert res["rms_px"] < 0.5 and res["rms_control_px"] < 0.75 and res["triangulada_control"]["peor_error_mm"] < 0.3
    dmm, ddeg = g.pose_difference(np.asarray(res["T_ref_other"]), g.inv(T_21))
    assert dmm < 1.0 and ddeg < 0.2, (dmm, ddeg)
    print(f"[fase 7a] 20 poses por el asistente: dT {dmm:.4f} mm, dR {ddeg:.5f} grados, RMS {res['rms_px']:.4f} px, "
          f"control {res['rms_control_px']:.4f} px, triangulada {res['triangulada_control']['peor_error_mm']:.4f} mm")


# ----------------------------------------------------------------------------
# Las funciones puras
# ----------------------------------------------------------------------------

def _T(rvec, tvec) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = cv2.Rodrigues(np.asarray(rvec, dtype=np.float64))[0], tvec
    return T


def test_diferencia_vistas_y_variedad() -> None:
    T0 = _T(tce.RVEC_1, tce.TVEC_1)
    esquinas = ts.proyectar(OBJP, tce.RVEC_1, tce.TVEC_1, KS["gs1"]).reshape(-1, 2)
    m = csb.medidas_tablero(esquinas, OBJP, KS["gs1"], tce.SIN_DIST, COLS, ROWS, SQ)
    assert g.pose_difference(m["T"], T0)[0] < 1e-3 and m["rms_pnp_px"] < 1e-3
    centro = T0 @ np.array([3.5 * SQ, 2.0 * SQ, 0.0, 1.0])
    assert m["z_mm"] == pytest.approx(600.0, abs=1e-2) and m["centro_mm"] == pytest.approx(list(centro[:3]), abs=1e-2)
    assert m["inclinacion_deg"] == pytest.approx(np.degrees(np.arccos(abs(T0[2, 2]))), abs=1e-3)
    # La misma pose con las esquinas en orden invertido (el origen en la esquina opuesta): 0 grados y 0 mm.
    inv = csb.medidas_tablero(ce.reordenar(esquinas, COLS, ROWS, "invertido"), OBJP, KS["gs1"], tce.SIN_DIST, COLS, ROWS, SQ)
    assert g.pose_difference(inv["T"], T0)[1] > 170.0                      # la pose cruda si cambia
    deg, mm = csb.diferencia_vistas(T0, inv["T"], COLS, ROWS, SQ)
    assert deg < 0.01 and mm < 0.01, (deg, mm)
    assert inv["z_mm"] == pytest.approx(m["z_mm"], abs=1e-2) and inv["inclinacion_deg"] == pytest.approx(m["inclinacion_deg"], abs=1e-2)

    def girada(grados: float) -> np.ndarray:           # inclinada sobre el eje x del tablero, por su centro
        c = np.array([3.5 * SQ, 2.0 * SQ, 0.0])
        G = np.eye(4)
        G[:3, :3] = cv2.Rodrigues(np.array([np.radians(grados), 0.0, 0.0]))[0]
        G[:3, 3] = c - G[:3, :3] @ c
        return T0 @ G

    def desplazada(mm_: float) -> np.ndarray:
        T = T0.copy()
        T[:3, 3] += np.array([mm_, 0.0, 0.0])
        return T

    d12 = csb.diferencia_vistas(T0, girada(12.0), COLS, ROWS, SQ)
    assert d12[0] == pytest.approx(12.0, abs=1e-6) and d12[1] < 1e-6
    assert csb.diferencia_vistas(T0, desplazada(39.0), COLS, ROWS, SQ) == pytest.approx((0.0, 39.0), abs=1e-4)
    args = (COLS, ROWS, SQ, csb.UMBRAL_DEG, csb.UMBRAL_MM)
    assert csb.es_distinta(T0, [], *args)                                   # la primera siempre vale
    assert csb.es_distinta(girada(12.0), [T0], *args) and not csb.es_distinta(girada(9.0), [T0], *args)
    assert not csb.es_distinta(desplazada(39.0), [T0], *args) and csb.es_distinta(desplazada(41.0), [T0], *args)
    assert not csb.es_distinta(desplazada(41.0), [T0, desplazada(60.0)], *args)      # distinta de una, repetida de otra
    assert csb.es_distinta(desplazada(105.0), [T0, desplazada(60.0)], *args)
    k, deg, mm = csb.vista_mas_cercana(desplazada(50.0), [T0, desplazada(60.0), girada(30.0)], COLS, ROWS, SQ)
    assert k == 1 and deg == pytest.approx(0.0, abs=1e-4) and mm == pytest.approx(10.0, abs=1e-6)
    assert csb.vista_mas_cercana(T0, [], COLS, ROWS, SQ) == (None, float("inf"), float("inf"))
    # La variedad lograda (P44), en gs1.
    tomadas = [{"medidas": {"gs1": {"inclinacion_deg": i, "z_mm": z}}} for i, z in ((8.0, 400.0), (31.0, 330.0), (20.0, 395.0))]
    v = csb.variedad(tomadas)
    assert v["cumple"] and v["z_recorrido_mm"] == 70.0 and (v["inclinacion_min_deg"], v["inclinacion_max_deg"]) == (8.0, 31.0)
    assert not csb.variedad(tomadas[:1])["cumple"] and csb.variedad([]) == {"camara": "gs1", "n": 0, "cumple": False}


def test_quietud() -> None:
    rng = np.random.default_rng(1)
    base = ts.proyectar(OBJP, tce.RVEC_1, tce.TVEC_1, KS["gs1"]).reshape(-1, 2).astype(np.float64)
    q = csb.Quietud(1.0, 0.5, 8, COLS, ROWS)
    assert not q.quieto(0.0) and q.progreso(0.0) == 0.0 and q.movimiento_px(0.0) is None
    # Con 0.1 px de ruido: quieta al cumplir 1.0 s, no antes.
    primera = None
    for k in range(25):
        t = k * 0.07
        q.push(t, base + rng.normal(0.0, 0.1, base.shape))
        if q.quieto(t) and primera is None:
            primera = t
        assert 0.0 <= q.progreso(t) <= 1.0
    assert primera == pytest.approx(1.05, abs=1e-9) and q.progreso(t) == 1.0 and 0.1 < q.movimiento_px(t) < 0.5
    # Un frame con el orden invertido no la rompe; uno sin tablero la vacia.
    q.push(t + 0.07, ce.reordenar(base, COLS, ROWS, "invertido"))
    assert q.quieto(t + 0.07) and q.movimiento_px(t + 0.07) < 0.5
    q.push(t + 0.14, None)
    assert not q.quieto(t + 0.14) and q.progreso(t + 0.14) == 0.0 and q.movimiento_px(t + 0.14) is None
    # Sin muestras recientes deja de estar quieta (la camara dejo de ver el tablero sin avisar).
    for k in range(20):
        q.push(10.0 + k * 0.07, base)
    assert q.quieto(11.33) and not q.quieto(12.5) and q.progreso(12.5) == 0.0
    # Con una deriva de 1.2 px/s nunca (con 1 px/s justa, el tramo de 1 s se queda en el borde de 0.5 px).
    for px_s in (1.2, 3.0):
        d = csb.Quietud(1.0, 0.5, 8, COLS, ROWS)
        for k in range(60):
            d.push(k * 0.07, base + np.array([px_s * k * 0.07, 0.0]))
            assert not d.quieto(k * 0.07)
        assert d.progreso(59 * 0.07) < 1.0
    # Pocas muestras en el segundo (la ventana va lenta): no cuenta como quieta.
    lenta = csb.Quietud(1.0, 0.5, 8, COLS, ROWS)
    for k in range(8):
        lenta.push(k * 0.3, base)
    assert not lenta.quieto(2.1) and lenta.progreso(2.1) == 1.0
    # Se mueve, se para: quieta 1 s despues de pararse.
    m = csb.Quietud(1.0, 0.5, 8, COLS, ROWS)
    for k in range(40):
        t = k * 0.07
        m.push(t, base + np.array([30.0 * min(t, 0.7), 0.0]))
        assert m.quieto(t) == (t >= 0.7 + 1.0 - 1e-9), t
    with pytest.raises(ValueError):
        q.push(0.0, base[:10])


def test_emparejar_por_hora_e_intentos(tmp_path) -> None:
    e = csb.emparejar_por_hora([0.000, 0.011, 0.022], [0.005, 0.016, 0.040])
    assert [(x["i"], x["j"]) for x in e] == [(0, 0), (1, 1), (2, 1)]
    assert [x["dt_ms"] for x in e] == pytest.approx([5.0, 5.0, -6.0])
    assert csb.emparejar_por_hora([0.0, 1.0], []) == [] and csb.emparejar_por_hora([], [0.0]) == []
    cams = ("gs1", "gs2")
    assert csb.siguiente_intento(tmp_path, "T04", cams) == ""
    (tmp_path / "T04_gs2_frames").mkdir()                                   # basta una camara para no pisar
    assert csb.siguiente_intento(tmp_path, "T04", cams) == "_r2"
    (tmp_path / "T04_gs1_r2_frames").mkdir()
    assert csb.siguiente_intento(tmp_path, "T04", cams) == "_r3" and csb.siguiente_intento(tmp_path, "T05", cams) == ""


def test_guardar_y_comprobar_rafaga(tmp_path) -> None:
    Ta = _T(tce.RVEC_1, tce.TVEC_1)
    f1, f2 = render("gs1", Ta), render("gs2", Ta)
    rafaga = {"gs1": [(ts.a_bgr(f1), 0.000), (f1, 0.011)], "gs2": [(f2, 0.005), (ts.a_bgr(f2), 0.016)]}      # BGR y gris
    gd = csb.guardar_rafaga(tmp_path, "T07", "_r2", rafaga)
    assert {c: p.name for c, p in gd["carpetas"].items()} == {"gs1": "T07_gs1_r2_frames", "gs2": "T07_gs2_r2_frames"}
    assert gd["horas"] == {"gs1": [0.0, 0.011], "gs2": [0.005, 0.016]} and [x["dt_ms"] for x in gd["emparejado"]] == pytest.approx([5.0, 5.0])
    leido = cv2.imread(str(gd["carpetas"]["gs1"] / "frame_00000.png"), cv2.IMREAD_UNCHANGED)
    assert leido.shape == (480, 640) and np.array_equal(leido, f1)
    with pytest.raises(FileExistsError):                                    # no pisa, ni a medias
        csb.guardar_rafaga(tmp_path, "T07", "_r2", rafaga)
    assert len(list(gd["carpetas"]["gs2"].glob("*.png"))) == 2
    c = csb.comprobar_rafaga(gd["carpetas"], COLS, ROWS, 2, 0.3, intr=INTR, square_mm=SQ)
    assert c["usable"] and c["motivo"] is None
    for cam, Tc in (("gs1", Ta), ("gs2", T_21 @ Ta)):
        m = c["camaras"][cam]
        assert m["n_detectados"] == 2 and m["movimiento_px"] == 0.0 and m["esquinas"].shape == (COLS * ROWS, 1, 2)
        assert max(csb.diferencia_vistas(m["T"], Tc, COLS, ROWS, SQ)) < 1.0 and m["rms_pnp_px"] < 0.5
    # Sin intrinsecos solo dice si vale; con una camara sin tablero, el motivo es el de esquinas_de_posicion.
    assert "T" not in csb.comprobar_rafaga(gd["carpetas"], COLS, ROWS, 2, 0.3)["camaras"]["gs1"]
    gris = np.full((480, 640), 128, dtype=np.uint8)
    gm = csb.guardar_rafaga(tmp_path, "T08", "", {"gs1": [(f1, 0.0), (f1, 0.01)], "gs2": [(gris, 0.0), (gris, 0.01)]})
    mala = csb.comprobar_rafaga(gm["carpetas"], COLS, ROWS, 2, 0.3, intr=INTR, square_mm=SQ)
    assert not mala["usable"] and mala["motivo"] == "gs2: el detector sb vio el tablero en 0 de 2 frames (minimo 2)"
    otra = {c: {**INTR[c], "shape": (1280, 960)} for c in INTR}
    assert "intrinsecos de (1280, 960)" in csb.comprobar_rafaga(gd["carpetas"], COLS, ROWS, 2, 0.3, intr=otra, square_mm=SQ)["motivo"]


def _vistas(Ta: np.ndarray | None, solo: str | None = None) -> dict:
    """Las vistas previas de las dos camaras para una pose (solo esquinas: el asistente calcula lo demas)."""
    out: dict = {}
    for cam in ("gs1", "gs2"):
        if Ta is None or (solo is not None and cam != solo):
            out[cam] = None
            continue
        Tc = Ta if cam == "gs1" else T_21 @ Ta
        out[cam] = {"esquinas": ts.proyectar(OBJP, cv2.Rodrigues(Tc[:3, :3])[0], Tc[:3, 3], KS[cam]).reshape(-1, 2).astype(np.float64)}
    return out


def _quieto(a: csb.Asistente, t0: float, Ta: np.ndarray, segundos: float = 1.2) -> tuple[float, list[str]]:
    acciones, t = [], t0
    for _k in range(int(round(segundos / 0.07))):
        t += 0.07
        acciones.append(a.observar(t, _vistas(Ta)))
    return t, acciones


def test_asistente_maquina_de_estados(poses) -> None:
    A, B = poses[0], poses[1]
    a = csb.Asistente(COLS, ROWS, SQ, INTR, 10.0, 40.0, 1.0, 0.5, objetivo=2, minimo=1)
    assert (a.estado, a.posicion_siguiente, a.postura.codigo, a.terminado) == ("sin_tablero", "T01", "G01", False)
    assert a.observar(0.0, _vistas(None)) == "nada" and a.estado == "sin_tablero" and a.progreso == 0.0
    assert a.observar(0.07, _vistas(A, solo="gs1")) == "nada" and a.estado == "sin_tablero"     # gs2 no lo ve
    assert a.medidas["gs1"]["z_mm"] > 0 and a.medidas["gs2"] is None
    t, acc = _quieto(a, 0.07, A)
    assert acc.count("capturar") == 1 and acc[-1] == "nada" and acc.index("capturar") == 15      # 16 muestras: 1.05 s
    assert a.estado == "comprobando" and a.cercana[0] is None                # tras "capturar" no vuelve a pedirla
    medidas = {c: csb.medidas_tablero(_vistas(A)[c]["esquinas"], OBJP, KS[c], tce.SIN_DIST, COLS, ROWS, SQ) for c in INTR}
    a.aceptar("T01", medidas)
    assert (a.estado, a.posicion_siguiente, a.postura.codigo, len(a.tomadas)) == ("repetida", "T02", "G02", 1)
    assert a.t_ultima_captura == pytest.approx(t)
    # La misma pose, quieta: repetida, con la mas parecida a 0.
    t, acc = _quieto(a, t, A)
    assert set(acc) == {"nada"} and a.estado == "repetida" and a.cercana[0] == 0 and a.cercana[1] < 0.01 and a.cercana[2] < 0.01
    # Otra pose: mientras no lleva 1 s, moviendo; despues captura, y un rechazo espera a que se mueva.
    assert a.observar(t + 0.07, _vistas(B)) == "nada" and a.estado == "moviendo"
    t, acc = _quieto(a, t + 0.07, B)
    assert acc.count("capturar") == 1
    a.rechazar("T02", "gs1: el tablero se movio 0.61 px entre frames (tope 0.3): no estaba quieto")
    assert a.estado == "rechazada" and a.posicion_siguiente == "T02" and a.postura.codigo == "G02" and a.ultimo_motivo
    t, acc = _quieto(a, t, B, 2.0)
    assert set(acc) == {"nada"} and a.estado == "rechazada"                 # sigue quieto en B: no lo reintenta
    assert a.observar(t + 0.07, _vistas(None)) == "nada" and a.estado == "sin_tablero"          # lo levantan
    t, acc = _quieto(a, t + 0.07, B)
    assert acc.count("capturar") == 1
    a.aceptar("T02", {c: csb.medidas_tablero(_vistas(B)[c]["esquinas"], OBJP, KS[c], tce.SIN_DIST, COLS, ROWS, SQ) for c in INTR})
    assert a.terminado and a.ultimo_motivo is None and [r["posicion"] for r in a.rechazadas] == ["T02"]
    # Tras un rechazo tambien vale moverlo sin que deje de verse.
    b = csb.Asistente(COLS, ROWS, SQ, INTR, 10.0, 40.0, 1.0, 0.5, objetivo=2, minimo=1)
    t, acc = _quieto(b, 0.0, A)
    b.rechazar("T01", "motivo")
    t, acc = _quieto(b, t, A, 0.5)
    assert b.estado == "rechazada"
    assert b.observar(t + 0.07, _vistas(movida(A, 5.0))) == "nada" and b.estado == "moviendo"
    t, acc = _quieto(b, t + 0.07, movida(A, 5.0))
    assert acc.count("capturar") == 1
    # La guia: n salta; tras la ultima, la postura libre. Y los argumentos imposibles.
    for _k in range(25):
        b.saltar_postura()
    assert b.postura is csb.POSTURA_LIBRE
    with pytest.raises(ValueError):
        csb.Asistente(COLS, ROWS, SQ, INTR, 10.0, 40.0, 1.0, 0.5, objetivo=17, minimo=18)


def test_posturas_y_ventana(poses) -> None:
    assert len(csb.POSTURAS) == 20 and len({p.codigo for p in csb.POSTURAS}) == 20
    textos = [p.texto + p.cuna for p in csb.POSTURAS + (csb.POSTURA_LIBRE,)] + [t for t, _c in csb._TEXTO_ESTADO.values()] + [csb.TITULO_VENTANA]
    assert all(ord(ch) < 128 for t in textos for ch in t)                   # la fuente Hershey no pinta acentos
    assert (csb.UMBRAL_DEG, csb.UMBRAL_MM, csb.OBJETIVO, csb.MINIMO) == (10.0, 40.0, 20, 18)          # P41 y P42
    assert (csb.TOPE_COMPROBACION_S, csb.ESTANCADA_S, csb.QUIETO_S) == (30.0, 5.0, 1.0)               # P43
    assert (csb.FRAMES_POR_VISTA, csb.MAX_MOVIMIENTO_PX, csb.DETECTOR_FINAL) == (ce.FRAMES_POR_VISTA, ce.MAX_MOVIMIENTO_PX, "sb")
    a = nuevo_asistente(20, 18)
    A = poses[0]
    frames = {"gs1": render("gs1", A), "gs2": ts.a_bgr(render("gs2", A))}
    # La vista previa a escala 0.5 devuelve las esquinas al tamano real sin sesgo (camara de 1280x960).
    K_g = ts.K_de(1200.0, 1200.0, 640.0, 480.0)
    tvec = ts.pose_hacia(K_g, tce.RVEC_1, (660.0, 470.0), 600.0, COLS, ROWS, SQ)
    grande = ts.renderizar_vista(K_g, tce.RVEC_1, tvec, COLS, ROWS, SQ, (1280, 960))
    v1, v05 = (csb.vista_previa(grande, COLS, ROWS, OBJP, K_g, tce.SIN_DIST, SQ, "clasico", e) for e in (1.0, 0.5))
    d = min((ce.reordenar(v05["esquinas"], COLS, ROWS, o) for o in ce.ORDENES), key=lambda x: np.abs(x - v1["esquinas"]).max()) - v1["esquinas"]
    assert np.abs(d).max() < 0.5 and np.abs(d.mean(axis=0)).max() < 0.1, (np.abs(d).max(), d.mean(axis=0))
    assert max(csb.diferencia_vistas(v05["T"], _T(tce.RVEC_1, tvec), COLS, ROWS, SQ)) < 1.0 and v05["z_mm"] == pytest.approx(600.0, abs=1.0)
    assert csb.vista_previa(np.full((480, 640, 3), 128, dtype=np.uint8), COLS, ROWS, OBJP, KS["gs1"], tce.SIN_DIST, SQ, "clasico", 0.5) is None
    vistas = {c: csb.vista_previa(frames[c], COLS, ROWS, OBJP, KS[c], tce.SIN_DIST, SQ, "clasico", 1.0) for c in frames}
    for estado in csb._TEXTO_ESTADO:
        a.observar(0.0, vistas)
        a.estado = estado
        img = csb.componer_ventana(frames, vistas, a, {"gs1": 89.9, "gs2": None, "ventana": 21.0}, 1234.0)
        assert img.shape == (480 + csb.ALTO_FRANJA, 1280, 3) and img.dtype == np.uint8
    # Sin frame de una camara, sin tablero en la otra, con una tomada y un rechazo: no se rompe.
    a.aceptar("T01", {c: vistas[c] for c in vistas})
    a.rechazar("T02", "gs2: el detector sb vio el tablero en 0 de 5 frames (minimo 2)")
    a.observar(1.0, {"gs1": vistas["gs1"], "gs2": None})
    img = csb.componer_ventana({"gs1": frames["gs1"], "gs2": None}, {"gs1": vistas["gs1"], "gs2": None}, a, {}, -3.0, ancho_vista=320)
    assert img.shape == (240 + csb.ALTO_FRANJA, 640, 3)


# ----------------------------------------------------------------------------
# Topes y salidas del bucle (reloj falso)
# ----------------------------------------------------------------------------

def test_el_tope_de_la_sesion_termina_con_1_y_deja_sesion_json(tmp_path, poses) -> None:
    A, B = poses[0], poses[1]
    v = 30.0 * B[2, 3] / 600.0
    s = correr([("A", 1.4, A, 0.0), ("mov", 60.0, B, v / 2.0)], tmp_path / "datos", objetivo=20, minimo=18, n_frames=2,
               limite=3.0, q_al_final=False)
    assert s["r"]["fin"] == "tope" and s["r"]["codigo"] == 1 and s["r"]["tomadas"] == 1
    assert 3.0 <= s["mundo"].t < 3.0 + 2 * TICK                              # paro en el tope, no despues
    assert s["sesion"]["estado"] == "terminada" and s["sesion"]["fin"] == "tope" and s["sesion"]["codigo"] == 1
    assert [t["posicion"] for t in s["sesion"]["tomadas"]] == ["T01"]
    assert not (tmp_path / "datos" / "sesion.json.tmp").exists()


def test_q_con_menos_del_minimo_y_n_salta_la_postura(tmp_path, poses) -> None:
    a = nuevo_asistente(20, 18)
    mundo = Mundo([("A", 5.0, poses[0], 0.0)], a, 2)
    teclas = iter([255, ord("n"), 255, ord("n"), ord("x"), ord("q")])
    r = csb.capturar_sesion({c: Fuente(c, mundo) for c in ("gs1", "gs2")}, INTR, a, tmp_path / "d", 100.0, 2, 0.3,
                            clock=mundo.reloj, leer_tecla=lambda: next(teclas), mostrar=lambda img: None,
                            detector_previa="clasico", escala_previa=1.0)
    assert r["fin"] == "q" and r["codigo"] == 1 and r["tomadas"] == 0 and a.postura.codigo == "G03"
    assert json.loads((tmp_path / "d" / "sesion.json").read_text(encoding="utf-8"))["variedad"] == {"camara": "gs1", "n": 0, "cumple": False}


def test_una_camara_que_deja_de_dar_frames_es_un_4(tmp_path, poses) -> None:
    s = correr([("A", 60.0, poses[0], 0.0)], tmp_path / "datos", objetivo=20, minimo=1, n_frames=2, muere={"gs2": 0.5},
               q_al_final=False)
    r = s["r"]
    assert r["fin"] == "camara_estancada" and r["codigo"] == 4 and r["camara"] == "gs2" and r["tomadas"] == 0
    assert 0.5 - TICK + csb.ESTANCADA_S <= s["mundo"].t < 0.5 + csb.ESTANCADA_S + 2 * TICK       # a los 5 s (P43)
    assert s["sesion"]["camara_estancada"] == {"camara": "gs2", "error": None} and s["a"].estado == "sin_tablero"
    # `failed` (el hilo de captura se rindio) lo corta sin esperar; y un error del backend llega con su texto.
    a = nuevo_asistente(20, 1)
    mundo = Mundo([("A", 60.0, poses[0], 0.0)], a, 2)
    fuentes = {"gs1": Fuente("gs1", mundo, muere_en=0.5), "gs2": Fuente("gs2", mundo)}
    fuentes["gs1"].failed = True
    mundo.t = 0.5
    r = csb.capturar_sesion(fuentes, INTR, a, tmp_path / "d2", 100.0, 2, 0.3, clock=mundo.reloj, leer_tecla=lambda: 255,
                            mostrar=lambda img: None, detector_previa="clasico", escala_previa=1.0)
    assert r["codigo"] == 4 and r["camara"] == "gs1" and mundo.t == 0.5

    class Rota(Fuente):
        def next_frame(self, timeout: float):
            raise RuntimeError("el backend se cayo")
    a = nuevo_asistente(20, 1)
    mundo = Mundo([("A", 60.0, poses[0], 0.0)], a, 2)
    r = csb.capturar_sesion({"gs1": Fuente("gs1", mundo), "gs2": Rota("gs2", mundo)}, INTR, a, tmp_path / "d3", 100.0, 2, 0.3,
                            clock=mundo.reloj, leer_tecla=lambda: 255, mostrar=lambda img: None, detector_previa="clasico", escala_previa=1.0)
    assert r["codigo"] == 4 and r["camara"] == "gs2" and r["error_camara"] == "RuntimeError: el backend se cayo"


def test_la_comprobacion_que_no_vuelve_se_rechaza_en_su_tope(tmp_path, poses, monkeypatch) -> None:
    """Un detector colgado no para la ventana ni la salida (principio 9): la rafaga se rechaza a los
    `TOPE_COMPROBACION_S` del reloj del bucle y la sesion sigue."""
    soltar = threading.Event()
    real = csb.comprobar_rafaga

    def colgada(*a, **k):
        soltar.wait(20.0)
        return real(*a, **k)

    monkeypatch.setattr(csb, "comprobar_rafaga", colgada)
    monkeypatch.setattr(csb, "TOPE_COMPROBACION_S", 2.0)
    try:
        s = correr([("A", 60.0, poses[0], 0.0)], tmp_path / "datos", objetivo=20, minimo=1, n_frames=2, limite=4.0,
                   congelar=False, q_al_final=False)
    finally:
        soltar.set()
    r = s["r"]
    assert r["fin"] == "tope" and r["codigo"] == 1 and r["tomadas"] == 0 and r["rechazadas"] == 1
    assert "la comprobacion paso de 2 s" in s["sesion"]["rechazadas"][0]["motivo"]
    assert (tmp_path / "datos" / "T01_gs1_frames").is_dir() and s["pitidos"] == ["rechazada"]
    assert s["a"].estado == "rechazada"                                      # quieto en A: no lo reintenta solo


def test_una_rafaga_incompleta_no_guarda_nada(tmp_path, poses) -> None:
    a = nuevo_asistente(20, 1)
    mundo = Mundo([("A", 60.0, poses[0], 0.0)], a, 3)

    class SeCorta(Fuente):
        def next_frame(self, timeout: float):
            if self.mundo.a.estado == "quieto" and self.mundo._k[self.cam] >= 1:
                return None
            return super().next_frame(timeout)

    r = csb.capturar_sesion({"gs1": Fuente("gs1", mundo), "gs2": SeCorta("gs2", mundo)}, INTR, a, tmp_path / "d", 2.5, 3, 0.3,
                            clock=mundo.reloj, leer_tecla=lambda: 255, mostrar=lambda img: None, detector_previa="clasico", escala_previa=1.0)
    assert r["tomadas"] == 0 and r["rechazadas"] == 1 and "rafaga incompleta: gs2" in a.rechazadas[0]["motivo"]
    assert [p.name for p in (tmp_path / "d").iterdir()] == ["sesion.json"]


# ----------------------------------------------------------------------------
# main, con camaras falsas y el FrameGrabber de verdad
# ----------------------------------------------------------------------------

class CamFalsa:
    """Un backend falso: `read()` da el frame cada ~4 ms; desde `muere_tras` lecturas, None."""

    def __init__(self, frame, falla_al_abrir: bool = False, muere_tras: int | None = None) -> None:
        self.frame, self.falla_al_abrir, self.muere_tras = frame, falla_al_abrir, muere_tras
        self.abierta = self.cerrada = False
        self.lecturas = 0
        self.tamano_real = (frame.shape[1], frame.shape[0])

    def open(self) -> None:
        if self.falla_al_abrir:
            raise RuntimeError("No se pudo abrir webcam source=2")
        self.abierta = True

    def read(self):
        time.sleep(0.004)
        self.lecturas += 1
        if self.muere_tras is not None and self.lecturas > self.muere_tras:
            return None, None, None
        return self.frame, None, time.time()

    def close(self) -> None:
        self.cerrada = True


@pytest.fixture()
def montaje(tmp_path, poses, monkeypatch):
    """Dos perfiles temporales (640x480, con su .yml de intrinsecos) y dos camaras falsas que ven la pose A."""
    perfiles = {}
    for k, cam in enumerate(("gs1", "gs2"), start=1):
        yml = tce._yml(tmp_path / f"intrinsecos_{cam}.yml", KS[cam], detector="sb")
        perfiles[cam] = tmp_path / f"perfil_{cam}.yaml"
        perfiles[cam].write_text("camera:\n  camera_type: webcam\n  source: %d\n  width: 640\n  height: 480\n  fps: 90\n"
                                 "  calibration_file: '%s'\n" % (k, str(yml).replace("\\", "/")), encoding="utf-8")
    cams = {"gs1": CamFalsa(ts.a_bgr(render("gs1", poses[0]))), "gs2": CamFalsa(ts.a_bgr(render("gs2", poses[0])))}
    pedidas = []

    def crear(cfg):
        pedidas.append(int(cfg["source"]))
        return cams["gs1" if int(cfg["source"]) == 1 else "gs2"]

    monkeypatch.setattr(csb, "create_backend", crear)
    return {"perfiles": perfiles, "cams": cams, "pedidas": pedidas, "tmp": tmp_path}


def _argv(montaje, *extra: str, salida=None) -> list[str]:
    p = montaje["perfiles"]
    base = ["--config", f"gs1={p['gs1']}", f"gs2={p['gs2']}", "--cols", str(COLS), "--rows", str(ROWS), "--square-mm", f"{SQ}",
            "--frames-por-vista", "2", "--quieto-s", "0.4", "--detector-previa", "clasico", "--escala-previa", "1.0", "--sin-pitido",
            "--timeout", "20"]
    return base + (["--salida", str(salida if salida is not None else montaje["tmp"] / "datos")] if "--medir-desde" not in extra else []) + list(extra)


def test_main_de_punta_a_punta_con_camaras_falsas(montaje, sin_ventanas, monkeypatch, capsys) -> None:
    visto: dict = {}
    real = csb._vigilante

    def espia(timeout, estado, salida):
        visto.update(timeout=timeout, estado=estado, salida=salida)
        return real(timeout, estado, salida)

    monkeypatch.setattr(csb, "_vigilante", espia)
    reporte = montaje["tmp"] / "rep.json"
    rc = csb.main(_argv(montaje, "--objetivo", "1", "--minimo", "1", "--reporte", str(reporte)))
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert rc == 0, e
    assert montaje["pedidas"] == [1, 2]                                      # gs1 y despues gs2
    assert all(c.abierta and c.cerrada for c in montaje["cams"].values())
    assert sin_ventanas["namedWindow"] == 1 and sin_ventanas["imshow"] >= 8 and sin_ventanas["destroyAllWindows"] == 1
    r = e["resultado"]
    assert r["fin"] == "objetivo" and r["tomadas"] == 1 and r["posiciones"] == ["T01"] and e["modo"] == "sesion"
    assert set(e["perfiles"]) == {"gs1", "gs2"} and len(e["intrinsecos"]["gs2"]["sha256"]) == 64
    datos = montaje["tmp"] / "datos"
    assert len(list((datos / "T01_gs2_frames").glob("frame_*.png"))) == 2
    ses = json.loads((datos / "sesion.json").read_text(encoding="utf-8"))
    assert ses["meta"]["perfiles"] == e["perfiles"] and ses["tomadas"][0]["dt_max_ms"] < 50.0
    # El tope de la sesion mas 60 s para el vigilante, y un estado que es JSON sin ayuda (lo escribe tal cual).
    assert visto["timeout"] == 80.0 and visto["salida"] == reporte
    assert json.loads(json.dumps(visto["estado"]))["resultado"]["codigo"] == 0
    salida = capsys.readouterr().out
    assert "python -m calibration.calibrate_extrinsics --desde-vistas" in salida and "--detector sb --frames-por-vista 2" in salida


def test_main_la_segunda_camara_no_abre(montaje, sin_ventanas) -> None:
    montaje["cams"]["gs2"].falla_al_abrir = True
    reporte = montaje["tmp"] / "rep.json"
    assert csb.main(_argv(montaje, "--reporte", str(reporte))) == 2
    assert montaje["cams"]["gs1"].abierta and montaje["cams"]["gs1"].cerrada and not montaje["cams"]["gs2"].abierta
    assert sin_ventanas["namedWindow"] == 0 and sin_ventanas["imshow"] == 0             # ninguna ventana
    assert "no se pudieron abrir las dos camaras" in json.loads(reporte.read_text(encoding="utf-8"))["error"]
    assert not (montaje["tmp"] / "datos").exists()


def test_main_una_camara_deja_de_dar_frames(montaje, monkeypatch) -> None:
    monkeypatch.setattr(csb, "ESTANCADA_S", 0.5)
    monkeypatch.setattr(csb, "ESPERA_FRAME_S", 0.05)
    montaje["cams"]["gs2"].muere_tras = 20
    reporte = montaje["tmp"] / "rep.json"
    assert csb.main(_argv(montaje, "--objetivo", "20", "--minimo", "18", "--quieto-s", "5", "--reporte", str(reporte))) == 4
    assert all(c.cerrada for c in montaje["cams"].values())                  # las dos, cerradas
    r = json.loads(reporte.read_text(encoding="utf-8"))["resultado"]
    assert r["fin"] == "camara_estancada" and r["camara"] == "gs2" and r["codigo"] == 4


def test_main_no_empieza(montaje, sin_ventanas) -> None:
    ocupada = montaje["tmp"] / "ocupada"
    ocupada.mkdir()
    (ocupada / "algo.txt").write_text("x", encoding="utf-8")
    assert csb.main(_argv(montaje, salida=ocupada)) == 2                     # la salida ya tiene algo
    vacia = montaje["tmp"] / "vacia"
    vacia.mkdir()
    a = _argv(montaje)
    a[2] = f"gs2={montaje['tmp'] / 'no_existe.yaml'}"
    assert csb.main(a) == 2                                                  # un perfil que no existe
    sin_cal = montaje["tmp"] / "sin_cal.yaml"
    sin_cal.write_text("camera:\n  camera_type: webcam\n  source: 2\n  width: 640\n  height: 480\n", encoding="utf-8")
    a = _argv(montaje)
    a[2] = f"gs2={sin_cal}"
    assert csb.main(a) == 2                                                  # sin calibration_file
    otro = montaje["tmp"] / "otro_tamano.yaml"
    otro.write_text(montaje["perfiles"]["gs2"].read_text(encoding="utf-8").replace("width: 640", "width: 1280"), encoding="utf-8")
    a = _argv(montaje)
    a[2] = f"gs2={otro}"
    assert csb.main(a) == 2                                                  # intrinsecos de otro tamano
    assert csb.main(_argv(montaje, "--medir-desde", str(montaje["tmp"] / "no_hay"))) == 2
    assert montaje["pedidas"] == [] and sin_ventanas["namedWindow"] == 0     # nada de eso llego a una camara
    # Una camara cuyo frame real no es el de sus intrinsecos: 2, y cerrada.
    montaje["cams"]["gs1"].tamano_real = (1280, 960)
    assert csb.main(_argv(montaje, salida=vacia)) == 2 and montaje["cams"]["gs1"].cerrada


@pytest.mark.parametrize("quitar,anadir", [
    ("--timeout", []),                                  # sin tope
    ("--config", []),
    ("--square-mm", []),
    ("--salida", []),                                   # ni --salida ni --medir-desde
    (None, ["--medir-desde", "x"]),                     # las dos
    (None, ["--objetivo", "5", "--minimo", "6"]),
    (None, ["--frames-por-vista", "1"]),
    (None, ["--escala-previa", "2"]),
    (None, ["--quieto-px", "0"]),
    ("--cols", ["--cols", "5"]),                        # tablero cuadrado
    ("--config", ["--config", "gs1=a.yaml"]),           # falta gs2
])
def test_main_exige_argumentos_explicitos(montaje, quitar, anadir) -> None:
    argv = _argv(montaje)
    if quitar is not None:
        i = argv.index(quitar)
        fin = i + 1
        while fin < len(argv) and not argv[fin].startswith("--"):
            fin += 1
        del argv[i:fin]
    with pytest.raises(SystemExit) as exc:
        csb.main(argv + anadir)
    assert exc.value.code == 2
    assert montaje["pedidas"] == []


def test_medir_desde_vistas_y_main_sin_camara(montaje, sin_ventanas, poses, monkeypatch) -> None:
    vistas = montaje["tmp"] / "grabadas"
    for cam in ("gs1", "gs2"):
        img = render(cam, poses[0])
        tce._guardar(vistas / f"T01_{cam}_frames", [img, img, img, img])
    m = csb.medir_desde_vistas(vistas, INTR, COLS, ROWS, SQ, repeticiones=1)
    assert m["posiciones"] == ["T01"] and m["frames"] == 8 and len(m["opciones"]) == 4 and m["repeticiones"] == 1
    assert {(o["detector"], o["escala"]) for o in m["opciones"]} == {("clasico", 1.0), ("clasico", 0.5), ("sb", 1.0), ("sb", 0.5)}
    for o in m["opciones"]:
        assert o["frames"] == 8 and 0 <= o["detectados"] <= 8 and o["ms_frame"]["p95"] >= o["ms_frame"]["mediana"] > 0
        assert o["ms_vuelta"]["mediana"] > o["ms_previa"]["mediana"] > 0
        if o["detectados"] == 8:                                            # los mismos frames: sin ruido
            assert o["ruido_px"] == {"ventana_frames": 3, "n": 4, "mediana": 0.0, "p95": 0.0, "max": 0.0}
            assert o["ruido_carpeta_px"]["por_carpeta"] == {"T01_gs1": 0.0, "T01_gs2": 0.0}
    assert m["recomendada"] is not None and m["quieto_px_minimo"] == 0.0 and isinstance(m["cumple_previa"], bool)
    assert m["comprobar_rafaga_s"]["n"] == 1 and m["comprobar_rafaga_s"]["usables"] == 1 and m["cumple_comprobar"] is True
    assert json.loads(json.dumps(ce._jsonable(m)))["criterio"] == {"previa_p95_ms": 50.0, "comprobar_p95_s": 5.0}
    with pytest.raises(ValueError):
        csb.medir_desde_vistas(montaje["tmp"], INTR, COLS, ROWS, SQ)
    # main --medir-desde: sin camara ni ventana; el codigo dice si la vista previa cabe en su tiempo.
    pedido: dict = {}

    def medida(carpeta, intr, cols, rows, square_mm):
        pedido.update(carpeta=carpeta, camaras=sorted(intr), tablero=(cols, rows, square_mm), forma=intr["gs1"]["shape"])
        return {**m, "cumple_previa": pedido.get("cumple", True)}

    monkeypatch.setattr(csb, "medir_desde_vistas", medida)
    reporte = montaje["tmp"] / "medida.json"
    assert csb.main(_argv(montaje, "--medir-desde", str(vistas), "--reporte", str(reporte))) == 0
    e = json.loads(reporte.read_text(encoding="utf-8"))
    assert e["modo"] == "medir" and e["medida"]["frames"] == 8 and "resultado" not in e
    assert pedido["carpeta"] == vistas and pedido["camaras"] == ["gs1", "gs2"] and pedido["tablero"] == (COLS, ROWS, SQ) and pedido["forma"] == (640, 480)
    pedido["cumple"] = False
    assert csb.main(_argv(montaje, "--medir-desde", str(vistas))) == 1
    assert montaje["pedidas"] == [] and sin_ventanas["namedWindow"] == 0 and sin_ventanas["destroyAllWindows"] == 0


@pytest.mark.skipif(sys.platform != "win32", reason="MSMF solo existe en Windows")
def test_el_modulo_deja_apagada_la_aceleracion_de_msmf() -> None:
    """Abre MSMF: como los demas, importa `camera` antes que `cv2` (CONTEXT 4.18), en un proceso nuevo."""
    var = "OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"
    env = {k: v for k, v in os.environ.items() if k != var}
    codigo = ("import calibration.capture_stereo_board, os; import camera.uvc as c; e = c.ACELERACION_MSMF; "
              f"print(e['efectiva'], e['valor'], e['puesta_aqui'], os.environ.get({var!r}))")
    p = subprocess.run([sys.executable, "-c", codigo], cwd=str(CODIGO_DIR), env=env, text=True, capture_output=True, timeout=90)
    assert p.returncode == 0, p.stderr[-2000:]
    assert p.stdout.strip().splitlines()[-1].split() == ["apagada", "0", "True", "0"]
