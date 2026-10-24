# -*- coding: utf-8 -*-
"""
ba_monitor.py — Monitor del BA para el panel (brief-02, M5). SIN Qt.

Dos piezas puras, verificables por consola:

  1) MonitorBA — parsea el verbose=2 de scipy.least_squares (metodo trf) linea
     a linea y detecta ESTANCAMIENTO: cost casi sin bajar + step norm sin
     achicarse durante una ventana de iteraciones. Degrada a "sin datos" si el
     formato no parsea (nunca corta por error de parseo).
  2) analizar_cobertura() — metricas de un dataset .npz de captura (frames por
     marker, pares unicos) ANTES de correr el BA. Evita "horas ciegas" sobre
     una captura floja (observado en vivo 2026-08-13: par (3,9) visto 1 vez,
     cost plano 2 h).

Umbrales como CONSTANTES visibles (aprobados 2026-08-13 como valores de
arranque; se calibran con el uso).

CLI (desde codigo\):
    python iter4\gui\ba_monitor.py --demo
    python iter4\gui\ba_monitor.py --archivo <log_del_ba.txt>
    python iter4\gui\ba_monitor.py --cobertura iter4/data/captura_ba_limpia.npz
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Umbrales de ESTANCAMIENTO (MonitorBA)
# ---------------------------------------------------------------------------
VENTANA_ITER = 6          # iteraciones que abarca la ventana de analisis
RED_COST_MIN_PCT = 0.5    # % minimo de reduccion del cost en la ventana
STEP_BAJA_MIN = 0.20      # el step norm debe bajar >20% en la ventana
ESTANCADAS_CORTE = 12     # iteraciones estancadas consecutivas -> auto-corte

# ---------------------------------------------------------------------------
# Umbrales de COBERTURA (analizar_cobertura)
# Calibracion 2026-08-13 contra captura_ba_limpia.npz (el dataset que produjo
# la geometria v2 VALIDADA): 1809 frames, min 408 frames/marker, 45/55 pares,
# par menos visto 52 veces. Nota geometrica: en un dodecaedro los pares de
# caras ~antipodas NUNCA son co-visibles -> el maximo real de pares es ~45-50
# de 55, no 55. VERDE queda anclado a ese dataset (0.80). La corrida fallida
# en vivo no fallo por pares AUSENTES sino por pares DEBILES (el (3,9) visto
# 1 vez) -> se agrega la señal de pares con menos de PAR_DEBIL_OBS vistas.
# ---------------------------------------------------------------------------
FRAMES_VERDE = 50         # frames minimos por marker para VERDE
FRAMES_AMARILLO = 20      # frames minimos por marker para AMARILLO
PARES_FRAC_VERDE = 0.80   # ~44/55 (la limpia validada tiene 45/55)
PARES_FRAC_AMARILLO = 0.60
PAR_DEBIL_OBS = 5         # un par visto < 5 veces es DEBIL (no ancla el grafo)


# ===========================================================================
# 1) Detector de estancamiento
# ===========================================================================

def _parsear_linea_scipy(linea):
    """Fila de iteracion del verbose=2 de trf -> dict o None.

    Formato esperado (whitespace): iter 0 tiene 4 columnas (Iteration, Total
    nfev, Cost, Optimality); las siguientes 6 (+ Cost reduction y Step norm).
    Cualquier cosa que no cuadre -> None (degradacion, no error).
    """
    tokens = linea.split()
    if len(tokens) not in (4, 6):
        return None
    try:
        it = int(tokens[0])
        nfev = int(tokens[1])
        cost = float(tokens[2])
        if len(tokens) == 4:
            return {"iter": it, "nfev": nfev, "cost": cost,
                    "cost_red": None, "step": None, "opt": float(tokens[3])}
        return {"iter": it, "nfev": nfev, "cost": cost,
                "cost_red": float(tokens[3]), "step": float(tokens[4]),
                "opt": float(tokens[5])}
    except ValueError:
        return None


class MonitorBA:
    """Acumula iteraciones del BA y evalua estancamiento por ventana."""

    def __init__(self):
        self.historial = []          # dicts de _parsear_linea_scipy
        self.estancadas = 0          # iteraciones estancadas CONSECUTIVAS
        self._max_estancadas = 0

    def feed(self, linea):
        """Procesa una linea de stdout del BA. Devuelve el registro parseado
        (dict) si era una fila de iteracion, si no None."""
        reg = _parsear_linea_scipy(linea)
        if reg is None:
            return None
        self.historial.append(reg)
        self._evaluar()
        return reg

    def _evaluar(self):
        if len(self.historial) < VENTANA_ITER + 1:
            return
        v0 = self.historial[-(VENTANA_ITER + 1)]
        v1 = self.historial[-1]
        if v0["cost"] <= 0:
            return
        red_pct = (v0["cost"] - v1["cost"]) / v0["cost"] * 100.0
        step0, step1 = v0["step"], v1["step"]
        step_estancado = (step0 is not None and step1 is not None
                          and step1 > (1.0 - STEP_BAJA_MIN) * step0)
        if red_pct < RED_COST_MIN_PCT and step_estancado:
            self.estancadas += 1
        else:
            self.estancadas = 0
        self._max_estancadas = max(self._max_estancadas, self.estancadas)

    def corte_recomendado(self):
        return self.estancadas >= ESTANCADAS_CORTE

    def resumen(self):
        """(estado, detalle) para la UI: 'sin datos' | 'convergiendo' |
        'estancado'."""
        if not self.historial:
            return ("sin datos", "aun sin filas de iteracion parseables")
        ult = self.historial[-1]
        base = (f"iter {ult['iter']}, cost {ult['cost']:.4e}"
                + (f", step {ult['step']:.2e}" if ult["step"] is not None else ""))
        if self.estancadas > 0:
            return ("estancado",
                    f"{base} — {self.estancadas} iter estancadas "
                    f"(corte a las {ESTANCADAS_CORTE})")
        return ("convergiendo", base)


# ===========================================================================
# 2) Analisis de cobertura de un dataset de captura
# ===========================================================================

def analizar_cobertura(ruta_npz):
    """Metricas de cobertura desde los campos TABULARES del .npz (sin pickle).

    Devuelve (veredicto, detalle, metrics):
      veredicto: 'VERDE' | 'AMARILLO' | 'ROJO'
      detalle:   texto multi-linea para la UI/log
      metrics:   dict con numeros crudos
    """
    ruta = Path(ruta_npz)
    if not ruta.exists():
        return ("ROJO", f"dataset no existe: {ruta}", {})
    try:
        data = np.load(ruta)   # sin allow_pickle: solo campos tabulares
        marker_ids = np.asarray(data["marker_ids"])
        offsets = np.asarray(data["frame_offsets"])
        rb_ids = sorted(int(x) for x in np.asarray(data["rb_ids"]))
    except (KeyError, OSError, ValueError) as e:
        return ("ROJO", f"dataset ilegible o sin campos tabulares: {e}", {})

    n_frames = max(0, len(offsets) - 1)
    if n_frames == 0:
        return ("ROJO", "dataset sin frames utiles (0 capturados)", {})

    conteo = {mid: int(np.sum(marker_ids == mid)) for mid in rb_ids}

    pares = {}
    for f in range(n_frames):
        mids = sorted(set(int(m) for m in marker_ids[offsets[f]:offsets[f + 1]]))
        for i in range(len(mids)):
            for j in range(i + 1, len(mids)):
                par = (mids[i], mids[j])
                pares[par] = pares.get(par, 0) + 1

    n_ids = len(rb_ids)
    n_pares_posibles = n_ids * (n_ids - 1) // 2
    n_pares_vistos = len(pares)
    pares_faltantes = [(a, b) for i, a in enumerate(rb_ids)
                       for b in rb_ids[i + 1:] if (a, b) not in pares]
    pares_debiles = {p: n for p, n in pares.items() if n < PAR_DEBIL_OBS}
    par_min = min(pares.items(), key=lambda kv: kv[1]) if pares else None

    min_frames = min(conteo.values()) if conteo else 0
    flojos = {m: n for m, n in conteo.items() if n < FRAMES_VERDE}

    frac_verde = PARES_FRAC_VERDE * n_pares_posibles
    frac_amarillo = PARES_FRAC_AMARILLO * n_pares_posibles
    if (min_frames >= FRAMES_VERDE and n_pares_vistos >= frac_verde
            and not pares_debiles):
        veredicto = "VERDE"
    elif min_frames >= FRAMES_AMARILLO and n_pares_vistos >= frac_amarillo:
        veredicto = "AMARILLO"
    else:
        veredicto = "ROJO"

    lineas = [
        f"frames utiles: {n_frames}",
        f"frames por marker: min {min_frames} "
        + (f"(flojos: {flojos})" if flojos else "(todos >= "
           f"{FRAMES_VERDE})"),
        f"pares unicos: {n_pares_vistos}/{n_pares_posibles} "
        f"(VERDE >= {frac_verde:.0f}, AMARILLO >= {frac_amarillo:.0f}; "
        f"los pares de caras opuestas son fisicamente in-co-visibles)",
    ]
    if pares_debiles:
        muestra = dict(list(pares_debiles.items())[:6])
        lineas.append(f"pares DEBILES (< {PAR_DEBIL_OBS} vistas, no anclan el "
                      f"grafo): {len(pares_debiles)} -> {muestra}"
                      + ("..." if len(pares_debiles) > 6 else ""))
    if pares_faltantes:
        muestra = pares_faltantes[:8]
        extra = "..." if len(pares_faltantes) > 8 else ""
        lineas.append(f"pares nunca vistos ({len(pares_faltantes)}, incluye "
                      f"caras opuestas imposibles): {muestra}{extra}")
    if par_min is not None:
        lineas.append(f"par menos visto: {par_min[0]} ({par_min[1]} veces)")
    if veredicto == "ROJO":
        lineas.append("COBERTURA FLOJA: el BA probablemente no converja — "
                      "recapturar mas largo y variando caras/orientaciones.")
    elif veredicto == "AMARILLO":
        lineas.append("cobertura justa: el BA puede costar — considerar "
                      "recapturar si no converge.")

    metrics = {
        "n_frames": n_frames, "conteo": conteo, "min_frames": min_frames,
        "n_pares_vistos": n_pares_vistos, "n_pares_posibles": n_pares_posibles,
        "pares_faltantes": pares_faltantes, "pares_debiles": pares_debiles,
        "par_min": par_min,
    }
    return (veredicto, "\n".join(lineas), metrics)


# ===========================================================================
# CLI de verificacion
# ===========================================================================

_DEMO_CONVERGIENDO = [
    "   Iteration     Total nfev        Cost      Cost reduction    Step norm     Optimality",
    "       0              1         3.1531e+05                                    1.05e+06",
    "       1              2         2.5000e+04      2.90e+05       1.34e+01       1.05e+05",
    "       2              3         8.1000e+03      1.69e+04       6.20e+00       2.10e+04",
    "       3              4         3.9000e+03      4.20e+03       2.80e+00       9.00e+03",
    "       4              5         2.1000e+03      1.80e+03       1.10e+00       4.10e+03",
    "       5              6         1.4000e+03      7.00e+02       6.00e-01       2.00e+03",
    "       6              7         1.1000e+03      3.00e+02       3.30e-01       9.00e+02",
    "       7              8         9.5000e+02      1.50e+02       1.80e-01       4.00e+02",
]

# Secuencia estancada: cost clavado y step norm constante (como la corrida en
# vivo 2026-08-13: step 0.35 fijo, cost casi sin bajar, 2 horas).
_DEMO_ESTANCADO = list(_DEMO_CONVERGIENDO) + [
    f"      {8 + k:2d}             {9 + k:2d}         9.4{900 - k:03d}e+02      1.00e-01       3.50e-01       1.00e+02"
    for k in range(20)
]


def _correr_demo():
    print("=== demo 1: secuencia CONVERGIENDO ===")
    m = MonitorBA()
    for ln in _DEMO_CONVERGIENDO:
        m.feed(ln)
    est, det = m.resumen()
    print(f"  filas parseadas: {len(m.historial)} | estado: {est} | {det}")
    print(f"  corte recomendado: {m.corte_recomendado()}  (esperado: False)")

    print("=== demo 2: secuencia ESTANCADA ===")
    m = MonitorBA()
    primera_estancada = None
    corte_en = None
    for ln in _DEMO_ESTANCADO:
        m.feed(ln)
        if m.estancadas == 1 and primera_estancada is None and m.historial:
            primera_estancada = m.historial[-1]["iter"]
        if m.corte_recomendado() and corte_en is None:
            corte_en = m.historial[-1]["iter"]
    est, det = m.resumen()
    print(f"  filas parseadas: {len(m.historial)} | estado: {est} | {det}")
    print(f"  primera iter estancada: {primera_estancada} | corte recomendado "
          f"en iter: {corte_en}  (esperado: no None)")

    print("=== demo 3: basura no parseable (degradacion) ===")
    m = MonitorBA()
    for ln in ["[INFO] cargando", "texto libre", "`ftol` termination condition"]:
        r = m.feed(ln)
        assert r is None
    est, det = m.resumen()
    print(f"  estado: {est} ({det})  (esperado: sin datos)")


def main():
    ap = argparse.ArgumentParser(description="Monitor/cobertura del BA (M5).")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--archivo", default=None,
                    help="Log del BA a parsear (verbose=2).")
    ap.add_argument("--cobertura", default=None,
                    help="Dataset .npz a analizar.")
    args = ap.parse_args()

    if args.demo:
        _correr_demo()
    if args.archivo:
        m = MonitorBA()
        n_total = 0
        with open(args.archivo, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                n_total += 1
                m.feed(ln.rstrip())
        est, det = m.resumen()
        print(f"[archivo] {args.archivo}: {n_total} lineas, "
              f"{len(m.historial)} filas de iteracion")
        print(f"[archivo] estado final: {est} | {det}")
        print(f"[archivo] max estancadas consecutivas: {m._max_estancadas} | "
              f"corte recomendado: {m.corte_recomendado()}")
    if args.cobertura:
        veredicto, detalle, _ = analizar_cobertura(args.cobertura)
        print(f"[cobertura] {args.cobertura} -> {veredicto}")
        for ln in detalle.splitlines():
            print(f"  {ln}")


if __name__ == "__main__":
    main()
