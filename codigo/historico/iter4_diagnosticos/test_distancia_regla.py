# -*- coding: utf-8 -*-
"""
Prueba de DISTANCIA CONOCIDA con REGLA — valida EXACTITUD del tip (iter 4).

Variante de test_distancia_conocida.py para cuando NO se tiene la placa con
divots. Se toca la punta del stylus en varias marcas de una regla (lecturas
en mm conocidas, p.ej. 0, 30, 60, 90) y se comprueba que el tip se MUEVE la
distancia esperada.

Marco de referencia (necesario para medir desplazamiento):
  - --ref-id N : marcador estatico (por defecto el ID 0 del hueso, 79.8 mm)
    puesto plano junto a la regla. El tip se mide EN SU FRAME -> inmune a que
    la camara se mueva. RECOMENDADO.
  - si el marcador de referencia no se detecta, cae a FRAME DE CAMARA: valido
    SOLO si la camara no se mueve entre toques (avisa).

Por que la regla sirve aunque sea menos fina que un divot:
  el tip es una esfera sobre una superficie plana -> su centro queda ~r por
  encima de la marca, igual en todas, asi que se cancela. El limite es la
  colocacion lateral a mano (~0.5-1 mm). Para compensar: usar BASE LARGA
  (0..90 mm) y/o repetir. Las marcas son colineales, asi que ademas se mide
  la RECTITUD (residual del ajuste de recta) como control de calidad.

Interpretacion:
  - Error de distancia < 1 mm en base larga -> sistema metricamente exacto.
  - Error que crece proporcional a la separacion -> error de ESCALA.
  - Residual de rectitud alto -> colocacion a mano ruidosa (repetir).

Uso (desde codigo\):
    python iter4\test_distancia_regla.py --marcas 0,30,60,90
    python iter4\test_distancia_regla.py --marcas 0,50,100 --ref-id 0 --ref-mm 79.8
    python iter4\test_distancia_regla.py --marcas 0,50,100 --ref-id -1   # frame camara

MODO INTERACTIVO:
    ESPACIO = capturar la marca actual (35 frames)
    s       = saltar a la siguiente marca
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


def log_info(m): print(f"[INFO] {m}")
def log_warn(m): print(f"[WARN] {m}")
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr)
def log_stats(m): print(f"[STATS] {m}")


SAMPLES_POR_MARCA = 35
MIN_SAMPLES = 15


def cargar_offset(ruta):
    M = np.load(ruta)
    assert M.shape == (4, 4), f"matriz inesperada: {M.shape}"
    return M[:3, 3].astype(float)


def rms_rectitud(puntos):
    """Residual RMS de los puntos respecto a la recta de mejor ajuste (mm)."""
    P = np.array(puntos)
    c = P.mean(axis=0)
    _u, _s, vh = np.linalg.svd(P - c)
    dir_ = vh[0]
    proy = c + np.outer((P - c) @ dir_, dir_)
    return float(np.sqrt(np.mean(np.sum((P - proy) ** 2, axis=1))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--offset", default="iter4/data/StylusTipToDodecaedro_divot.npy")
    parser.add_argument("--marcas", default="0,30,60,90",
                        help="lecturas de la regla en mm donde tocaras, p.ej. 0,30,60,90")
    parser.add_argument("--ref-id", type=int, default=0,
                        help="marcador estatico de referencia (-1 = usar frame de camara)")
    parser.add_argument("--ref-mm", type=float, default=79.8,
                        help="tamano del marcador de referencia en mm (ID 0 = 79.8)")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output", default="iter4/data/distancia_regla.npz")
    args = parser.parse_args()

    try:
        marcas = [float(x) for x in args.marcas.split(",")]
    except ValueError:
        log_error("--marcas debe ser numeros, p.ej. 0,30,60,90"); sys.exit(1)
    if len(marcas) < 2:
        log_error("Se necesitan >= 2 marcas."); sys.exit(1)

    offset = cargar_offset(args.offset)
    log_info(f"Offset tip (frame dodecaedro): {np.round(offset, 3)} mm <- {args.offset}")
    log_info(f"Marcas de regla (mm): {marcas}")
    usar_ref = args.ref_id >= 0
    if usar_ref:
        log_info(f"Referencia: marcador ID {args.ref_id} @ {args.ref_mm} mm (estatico).")
    else:
        log_warn("Referencia: FRAME DE CAMARA. La camara NO debe moverse entre toques.")

    cfg = cargar_config(args.config)
    rb_cfg = cfg["rigid_bodies"][0]
    rb_geom = cargar_rigid_body(rb_cfg["geometry_file"])
    min_markers = cfg.get("rigid_bodies_quality", {}).get("min_markers", 3)
    detector, _, _, _ = crear_detector(cfg["markers"])

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()

    print()
    log_info("ESPACIO = capturar marca | s = saltar | q = terminar")

    tip_por_marca = {}     # lectura(mm) -> (3,) posicion del tip
    ruido_por_marca = {}
    idx = 0
    capturando = False
    cap_tips = []
    ref_perdida = 0
    t_inicio = time.time()

    def marca_actual():
        return marcas[idx] if idx < len(marcas) else None

    try:
        while time.time() - t_inicio < args.timeout and idx < len(marcas):
            frame, _d, _ts = cam.read()
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            corners, ids, _ = detector.detectMarkers(gray)
            det_rb = {}
            corners_ref = None
            if ids is not None:
                for i, m in enumerate(ids.flatten().tolist()):
                    m = int(m)
                    if m in rb_geom:
                        det_rb[m] = corners[i]
                    if usar_ref and m == args.ref_id:
                        corners_ref = corners[i]

            # tip en el frame de referencia (o de camara).
            p_tip = None
            if len(det_rb) >= min_markers:
                pd = estimar_pose_rigid_body(det_rb, rb_geom, K, dist)
                if pd is not None:
                    T_dodec = rvec_tvec_a_matriz(pd[0], pd[1])
                    p_cam = T_dodec[:3, :3] @ offset + T_dodec[:3, 3]
                    if usar_ref:
                        if corners_ref is not None:
                            pr = estimar_pose_individual(corners_ref, args.ref_mm, K, dist)
                            if pr is not None:
                                T_ref = rvec_tvec_a_matriz(*pr)
                                Ti = np.linalg.inv(T_ref)
                                p_tip = Ti[:3, :3] @ p_cam + Ti[:3, 3]
                    else:
                        p_tip = p_cam

            m = marca_actual()
            ref_txt = (f"ref:{'si' if corners_ref is not None else 'NO'} "
                       if usar_ref else "")
            estado = f"MARCA {m} mm  {ref_txt}dodec:{len(det_rb)}/{min_markers}"

            if capturando:
                if p_tip is None:
                    if usar_ref and corners_ref is None:
                        ref_perdida += 1
                    estado = f"MARCA {m}: capturando... (sin deteccion)"
                else:
                    cap_tips.append(p_tip)
                    estado = f"MARCA {m}: capturando {len(cap_tips)}/{SAMPLES_POR_MARCA}"
                    if len(cap_tips) >= SAMPLES_POR_MARCA:
                        arr = np.array(cap_tips)
                        med = np.median(arr, axis=0)
                        mad = np.median(np.abs(arr - med), axis=0) * 1.4826 + 1e-6
                        ok = (np.abs(arr - med) < 3.0 * mad).all(axis=1)
                        if ok.sum() < MIN_SAMPLES:
                            log_warn(f"Marca {m} DESCARTADA: muy ruidosa "
                                     f"({ok.sum()} frames). Repetir.")
                        else:
                            tip = arr[ok].mean(axis=0)
                            std = arr[ok].std(axis=0)
                            tip_por_marca[m] = tip
                            ruido_por_marca[m] = std
                            log_info(f"Marca {m} mm OK: {ok.sum()}/{len(arr)} frames, "
                                     f"ruido=[{std[0]:.2f}, {std[1]:.2f}, {std[2]:.2f}] mm")
                            idx += 1
                        capturando, cap_tips = False, []

            display = frame.copy()
            cv2.putText(display, estado, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display, "ESPACIO=capturar  s=saltar  q=terminar", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow("distancia regla", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and not capturando and marca_actual() is not None:
                capturando, cap_tips = True, []
                log_info(f"Capturando marca {marca_actual()} mm...")
            elif key == ord("s"):
                log_warn(f"Marca {marca_actual()} saltada.")
                idx += 1
            elif key == ord("q"):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()

    print()
    if usar_ref and ref_perdida > 30:
        log_warn(f"El marcador de referencia se perdio en muchos frames "
                 f"({ref_perdida}). Asegura que ID {args.ref_id} este siempre visible.")

    medidas = sorted(tip_por_marca)
    if len(medidas) < 2:
        log_error("Menos de 2 marcas capturadas: nada que comparar."); sys.exit(1)

    log_stats(f"Marcas capturadas (mm): {medidas}")
    print()
    log_stats(f"{'par':>11} | {'medido':>9} | {'esperado':>9} | {'error':>8}")
    errores, filas = [], []
    for a, b in itertools.combinations(medidas, 2):
        d_med = float(np.linalg.norm(tip_por_marca[a] - tip_por_marca[b]))
        d_true = abs(b - a)
        err = d_med - d_true
        errores.append(err)
        filas.append((f"{a}-{b}", d_med, d_true, err))
        log_stats(f"{str(a)+'-'+str(b):>11} | {d_med:9.3f} | {d_true:9.3f} | {err:+8.3f}")

    err = np.array(errores)
    print()
    log_stats(f"Error medio (sesgo): {err.mean():+.3f} mm")
    log_stats(f"Error abs medio:     {np.abs(err).mean():.3f} mm")
    log_stats(f"Error abs maximo:    {np.abs(err).max():.3f} mm")
    log_stats(f"RMS de error:        {np.sqrt(np.mean(err**2)):.3f} mm")

    if len(medidas) >= 3:
        rect = rms_rectitud([tip_por_marca[m] for m in medidas])
        log_stats(f"Rectitud (residual a la recta): {rect:.3f} mm "
                  f"({'OK' if rect < 1.0 else 'colocacion ruidosa, repetir'})")

    signos = np.sign(err[err != 0])
    if len(signos) >= 2 and np.all(signos == signos[0]):
        log_info("Errores del MISMO signo -> posible error de ESCALA "
                 "(intrinsecos de camara o tamano de marker de referencia).")
    veredicto = ("EXACTO (FIABLE)" if np.abs(err).max() < 1.0 else
                 "ACEPTABLE" if np.abs(err).max() < 2.0 else "REVISAR")
    log_stats(f"[{veredicto}] error abs max = {np.abs(err).max():.3f} mm")

    np.savez_compressed(
        args.output,
        tips={k: v for k, v in tip_por_marca.items()},
        ruido={k: v for k, v in ruido_por_marca.items()},
        filas=np.array(filas, dtype=object),
        offset=offset, ref_id=args.ref_id)
    log_info(f"Guardado: {args.output}")


if __name__ == "__main__":
    main()
