# -*- coding: utf-8 -*-
"""
Prueba de DISTANCIA CONOCIDA — valida EXACTITUD del tip calibrado (iter 4).

Idea: el spread entre posturas mide PRECISION (repetibilidad), pero NO ve un
sesgo comun a todas las posturas (error en la geometria del dock, en la
referencia, etc.). Para medir EXACTITUD se necesita un ground truth metrico
independiente.

Aqui se usan los divots A/B/C de la placa v2 (placa_calibracion), cuyas
posiciones estan definidas por CAD y separadas 40/40/80 mm. Se toca la punta
en cada divot, se calcula la posicion del tip EN EL FRAME DE LA PLACA usando
el offset calibrado, y se comparan las distancias medidas vs las conocidas.

Por que es valido aunque la esfera asiente a cierta altura del apice:
  una esfera en un cono se auto-centra sobre el eje a una altura FIJA (misma
  para A, B, C porque son el mismo cono). Esa altura comun se cancela en las
  distancias entre divots coplanares -> la prueba mide la escala metrica real
  del sistema (tracking + geometria del rigid body + offset del tip), sin
  depender del caliper del stylus viejo.

Interpretacion:
  - Error de distancia < 1 mm  -> sistema metricamente exacto. FIABLE.
  - Error sistematico (todas largas/cortas por igual) -> error de escala
    (intrinsecos de camara o tamano de marker de la placa).
  - Error que crece con la separacion (A-C peor que A-B) -> idem escala.
  - Error aleatorio por par -> ruido de pose / asentamiento.

Uso (desde codigo\):
    python iter4\test_distancia_conocida.py
    python iter4\test_distancia_conocida.py --divots A,B,C
    python iter4\test_distancia_conocida.py --known-mm "A-B=39.9,B-C=39.8"

MODO INTERACTIVO:
    ESPACIO = capturar el divot actual (35 frames, tip en frame de la placa)
    s       = saltar al siguiente divot sin capturar
    q       = terminar y reportar
"""
from __future__ import annotations

import argparse
import itertools
import sys
import time

import cv2
import numpy as np

from camera_backend import create_backend
from captura_calibracion import cargar_config, crear_detector
from tracker import (cargar_rigid_body, estimar_pose_individual,
                     estimar_pose_rigid_body, rvec_tvec_a_matriz)
# Reusar geometria de divots y deteccion estricta de la placa del calibrador.
from calibrar_tip_divot import DIVOTS, crear_detector_placa, detectar_placa


def log_info(m): print(f"[INFO] {m}")
def log_warn(m): print(f"[WARN] {m}")
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr)
def log_stats(m): print(f"[STATS] {m}")


SAMPLES_POR_DIVOT = 35
MIN_SAMPLES = 15


def parse_known(s):
    """'A-B=39.9,B-C=39.8' -> {('A','B'):39.9, ('B','C'):39.8}."""
    out = {}
    if not s:
        return out
    for tok in s.split(","):
        par, val = tok.split("=")
        a, b = par.split("-")
        out[tuple(sorted((a.strip(), b.strip())))] = float(val)
    return out


def cargar_offset(ruta):
    """Lee StylusTipToDodecaedro (4x4) y devuelve el vector offset (3,)."""
    M = np.load(ruta)
    assert M.shape == (4, 4), f"matriz inesperada: {M.shape}"
    return M[:3, 3].astype(float)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--offset", default="iter4/data/StylusTipToDodecaedro_divot.npy")
    # La placa v2 con los divots A/B/C lleva el marker ID 1.
    parser.add_argument("--plate-id", type=int, default=1)
    parser.add_argument("--plate-mm", type=float, default=59.55)
    parser.add_argument("--divots", default="A,B,C",
                        help="orden de divots a tocar, p.ej. A,B,C")
    parser.add_argument("--known-mm", default="",
                        help="distancias caliper reales, p.ej. 'A-B=39.9,B-C=39.8'. "
                             "Si se omite, se usan las del CAD as-built (DIVOTS).")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", default="iter4/data/distancia_conocida.npz")
    args = parser.parse_args()

    secuencia = [d.strip().upper() for d in args.divots.split(",")]
    for d in secuencia:
        if d not in DIVOTS:
            log_error(f"Divot '{d}' no existe. Opciones: {list(DIVOTS)}"); sys.exit(1)
    if len(secuencia) < 2:
        log_error("Se necesitan >= 2 divots para medir distancias."); sys.exit(1)

    offset = cargar_offset(args.offset)
    log_info(f"Offset tip (frame dodecaedro): {np.round(offset, 3)} mm "
             f"(|{np.linalg.norm(offset):.2f}| mm) <- {args.offset}")

    cfg = cargar_config(args.config)
    rb_cfg = cfg["rigid_bodies"][0]
    rb_geom = cargar_rigid_body(rb_cfg["geometry_file"])
    min_markers = cfg.get("rigid_bodies_quality", {}).get("min_markers", 3)
    detector_dodec, _, _, _ = crear_detector(cfg["markers"])
    detector_placa = crear_detector_placa()

    # Ground truth de las distancias (CAD as-built desde DIVOTS, o caliper).
    known_user = parse_known(args.known_mm)
    log_info(f"Secuencia de divots: {secuencia}")
    log_info(f"Placa marker ID {args.plate_id} @ {args.plate_mm} mm")

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()

    print()
    log_info("ESPACIO = capturar divot | s = saltar | q = terminar")

    tip_por_divot = {}     # divot -> (3,) posicion mediana del tip en frame placa
    ruido_por_divot = {}   # divot -> (3,) std del tip
    idx_seq = 0
    capturando = False
    cap_tips = []
    t_inicio = time.time()

    def divot_actual():
        return secuencia[idx_seq] if idx_seq < len(secuencia) else None

    try:
        while time.time() - t_inicio < args.timeout and idx_seq < len(secuencia):
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            corners_d, ids_d, _ = detector_dodec.detectMarkers(gray)
            det_rb = {}
            if ids_d is not None:
                for i, m in enumerate(ids_d.flatten().tolist()):
                    if int(m) in rb_geom:
                        det_rb[int(m)] = corners_d[i]
            placa_corners = detectar_placa(gray, detector_placa, args.plate_id)

            # tip en frame de la placa: T_pd = inv(T_plate) @ T_dodec ; p = R@off + t
            p_tip = None
            if placa_corners is not None and len(det_rb) >= min_markers:
                pp = estimar_pose_individual(placa_corners, args.plate_mm, K, dist)
                pd = estimar_pose_rigid_body(det_rb, rb_geom, K, dist)
                if pp is not None and pd is not None:
                    T_plate = rvec_tvec_a_matriz(*pp)
                    T_dodec = rvec_tvec_a_matriz(pd[0], pd[1])
                    M = np.linalg.inv(T_plate) @ T_dodec
                    p_tip = M[:3, :3] @ offset + M[:3, 3]

            d = divot_actual()
            estado = (f"DIVOT {d}  placa:{'si' if placa_corners is not None else 'NO'} "
                      f"dodec:{len(det_rb)}/{min_markers}")

            if capturando:
                if p_tip is None:
                    estado = f"DIVOT {d}: capturando... (sin deteccion)"
                else:
                    cap_tips.append(p_tip)
                    estado = f"DIVOT {d}: capturando {len(cap_tips)}/{SAMPLES_POR_DIVOT}"
                    if len(cap_tips) >= SAMPLES_POR_DIVOT:
                        arr = np.array(cap_tips)
                        med = np.median(arr, axis=0)
                        mad = np.median(np.abs(arr - med), axis=0) * 1.4826 + 1e-6
                        ok = (np.abs(arr - med) < 3.0 * mad).all(axis=1)
                        if ok.sum() < MIN_SAMPLES:
                            log_warn(f"Divot {d} DESCARTADO: muy ruidoso "
                                     f"({ok.sum()} frames). Repetir.")
                        else:
                            tip = arr[ok].mean(axis=0)
                            std = arr[ok].std(axis=0)
                            tip_por_divot[d] = tip
                            ruido_por_divot[d] = std
                            log_info(f"Divot {d} OK: {ok.sum()}/{len(arr)} frames, "
                                     f"tip={np.round(tip, 2)} mm, "
                                     f"ruido=[{std[0]:.2f}, {std[1]:.2f}, {std[2]:.2f}] mm")
                            idx_seq += 1
                        capturando, cap_tips = False, []

            display = frame.copy()
            cv2.putText(display, estado, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display, "ESPACIO=capturar  s=saltar  q=terminar", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow("distancia conocida", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and not capturando and divot_actual() is not None:
                capturando, cap_tips = True, []
                log_info(f"Capturando divot {divot_actual()}...")
            elif key == ord("s"):
                log_warn(f"Divot {divot_actual()} saltado.")
                idx_seq += 1
            elif key == ord("q"):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print()
    medidos = sorted(tip_por_divot)
    if len(medidos) < 2:
        log_error("Menos de 2 divots capturados: no hay distancias que comparar.")
        sys.exit(1)

    log_stats(f"Divots capturados: {medidos}")
    print()
    log_stats(f"{'par':>7} | {'medido':>9} | {'conocido':>9} | {'error':>8} | fuente")
    errores = []
    filas = []
    for a, b in itertools.combinations(medidos, 2):
        d_med = float(np.linalg.norm(tip_por_divot[a] - tip_por_divot[b]))
        clave = tuple(sorted((a, b)))
        if clave in known_user:
            d_true, fuente = known_user[clave], "caliper"
        else:
            d_true = float(np.linalg.norm(DIVOTS[a] - DIVOTS[b]))
            fuente = "CAD"
        err = d_med - d_true
        errores.append(err)
        filas.append((f"{a}-{b}", d_med, d_true, err, fuente))
        log_stats(f"{a+'-'+b:>7} | {d_med:9.3f} | {d_true:9.3f} | "
                  f"{err:+8.3f} | {fuente}")

    err = np.array(errores)
    print()
    log_stats(f"Error medio (sesgo): {err.mean():+.3f} mm")
    log_stats(f"Error abs medio:     {np.abs(err).mean():.3f} mm")
    log_stats(f"Error abs maximo:    {np.abs(err).max():.3f} mm")
    log_stats(f"RMS de error:        {np.sqrt(np.mean(err**2)):.3f} mm")

    # Diagnostico: sesgo constante vs error de escala.
    if np.all(np.abs(err) > 0):
        signos = np.sign(err)
        if np.all(signos == signos[0]) and len(err) >= 2:
            log_info("Todos los errores tienen el MISMO signo -> posible error de "
                     "ESCALA (intrinsecos de camara o tamano de marker de la placa).")
    veredicto = ("EXACTO (FIABLE)" if np.abs(err).max() < 1.0 else
                 "ACEPTABLE" if np.abs(err).max() < 2.0 else "REVISAR")
    log_stats(f"[{veredicto}] error abs max = {np.abs(err).max():.3f} mm")

    np.savez_compressed(
        args.output,
        tips={k: v for k, v in tip_por_divot.items()},
        ruido={k: v for k, v in ruido_por_divot.items()},
        filas=np.array(filas, dtype=object),
        offset=offset, offset_file=args.offset)
    log_info(f"Guardado: {args.output}")


if __name__ == "__main__":
    main()
