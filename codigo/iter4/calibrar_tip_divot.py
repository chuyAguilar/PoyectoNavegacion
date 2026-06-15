# -*- coding: utf-8 -*-
"""
Calibracion del tip del stylus por DIVOT (template-based) — iter 4.

La punta se apoya QUIETA en un hoyuelo conico de posicion CONOCIDA respecto
al marker ID 1 de la placa de calibracion (stl/placa_calibracion/). Cada
frame da una ecuacion 3D completa:

    R_pd @ offset + t_pd = p_divot

donde (R_pd, t_pd) es la pose del dodecaedro EN EL FRAME DE LA PLACA
(T_placa^-1 @ T_dodec). El offset sale por minimos cuadrados lineales.

DETECCION EN DOS PASADAS (2026-06-13):
  - Dodecaedro: detector TUNEADO del config (permisivo, markers chicos a
    angulos rasantes). Sus falsos positivos en la escena son inofensivos.
  - Placa: detector ESTRICTO (defaults OpenCV) dedicado; si falla, segunda
    pasada a media resolucion (las micro-sombras del relieve impreso rompen
    el quad a maxima nitidez) + refinamiento subpixel.

CAPTURA POR POSTURAS (2026-06-13 v2):
  - El jitter frame a frame de la pose relativa es 1.5-4 mm AUNQUE todo este
    quieto (ruido de medicion con 3-4 markers). El gate de movimiento es
    solo para movimiento GRUESO (6 mm / 4 deg = levantar/reacomodar).
  - El ruido fino se filtra por mediana+MAD al cerrar cada postura, y se
    reporta el ruido de la postura.

MODO INTERACTIVO:
  ESPACIO = capturar postura (35 frames)
  f       = guardar snapshot crudo (diagnostico)
  q       = terminar y resolver

Uso (desde codigo\):
    python iter4\calibrar_tip_divot.py --divot B
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone

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


# Coordenadas del apice de cada divot en el frame del marker ID 1 (mm).
# AS-BUILT de la pieza impresa 2026-06-12 (Bambu A1, PLA blanco/negro):
#   placa midio 139.5 mm (nominal 140.0) -> escala XY 0.99643 aplicada.
#   z sin escalar. Si se reimprime: re-medir y actualizar.
ESCALA_XY = 139.5 / 140.0
DIVOTS = {
    "A": np.array([-40.0 * ESCALA_XY, -50.0 * ESCALA_XY, -3.5]),
    "B": np.array([0.0, -50.0 * ESCALA_XY, -3.5]),
    "C": np.array([40.0 * ESCALA_XY, -50.0 * ESCALA_XY, -3.5]),
    # DOCK de la placa v3 (template completo, stylus impreso con esfera r1):
    # CENTRO DE LA ESFERA en el frame del marker ID 2.
    # AS-BUILT pieza impresa 2026-06-15: placa midio 149.4 mm (nominal 150.0)
    # -> escala XY 0.99600 aplicada a X,Y. Z (altura de impresion) sin escalar.
    # Protocolo: stylus encajado fijo; entre posturas se reorienta el
    # CONJUNTO entero frente a la camara. Usar con --plate-id 2 --plate-mm 59.6.
    "DOCK": np.array([-48.718 * (149.4 / 150.0), -60.0 * (149.4 / 150.0), 20.598]),
}
PLACA_VERSION = "placa_calibracion_v2_impresa_2026-06-12"

SAMPLES_POR_POSTURA = 35
# Gate SOLO para movimiento grueso; el ruido fino se filtra por MAD despues.
QUIETO_MM = 6.0
QUIETO_DEG = 4.0
MIN_SAMPLES_POSTURA = 15
MIN_POSTURAS = 4


def angulo_entre(R1, R2):
    return float(np.degrees(np.arccos(np.clip((np.trace(R1 @ R2.T) - 1) / 2, -1, 1))))


def crear_detector_placa():
    """Detector ESTRICTO (defaults) para el marker grande de la placa."""
    ad = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_MIP_36h12)
    p = cv2.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(ad, p)


def detectar_placa(gray, detector_placa, plate_id):
    """Esquinas (4,2) del marker de la placa o None. 2 niveles + subpixel."""
    c, i, _ = detector_placa.detectMarkers(gray)
    if i is not None:
        il = i.flatten().tolist()
        if plate_id in il:
            return c[il.index(plate_id)].reshape(4, 2)
    half = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    c, i, _ = detector_placa.detectMarkers(half)
    if i is not None:
        il = i.flatten().tolist()
        if plate_id in il:
            pts = (c[il.index(plate_id)].reshape(4, 2) * 2.0).astype(np.float32)
            pts = pts.reshape(-1, 1, 2)
            cv2.cornerSubPix(
                gray, pts, (5, 5), (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01))
            return pts.reshape(4, 2)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--divot", default="B", choices=list(DIVOTS))
    parser.add_argument("--plate-id", type=int, default=1)
    # 59.55 = promedio caliper 59.5/59.6 de la pieza impresa.
    parser.add_argument("--plate-mm", type=float, default=59.55)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output-matriz", default="iter4/data/StylusTipToDodecaedro_divot")
    parser.add_argument("--output-samples", default="iter4/data/divot_samples.npz")
    args = parser.parse_args()

    p_divot = DIVOTS[args.divot]
    cfg = cargar_config(args.config)
    rb_cfg = cfg["rigid_bodies"][0]
    rb_geom = cargar_rigid_body(rb_cfg["geometry_file"])
    geom_sha = hashlib.sha256(open(rb_cfg["geometry_file"], "rb").read()).hexdigest()
    min_markers = cfg.get("rigid_bodies_quality", {}).get("min_markers", 3)
    detector_dodec, _, _, _ = crear_detector(cfg["markers"])
    detector_placa = crear_detector_placa()

    log_info(f"Placa: {PLACA_VERSION}, marker ID {args.plate_id} @ {args.plate_mm} mm")
    log_info(f"Divot {args.divot}: {np.round(p_divot, 3)} mm (frame del marker)")
    log_info(f"Rigid body: {rb_cfg['geometry_file']} (sha {geom_sha[:16]})")

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()

    print()
    log_info("ESPACIO = capturar postura | f = snapshot diagnostico | q = terminar")

    samples_R, samples_t = [], []
    posturas = []
    posturas_tilt = []
    capturando = False
    cap_R, cap_t = [], []
    estado = "esperando deteccion"
    n_snap = 0
    t_inicio = time.time()

    try:
        while time.time() - t_inicio < args.timeout:
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

            vis = (f"placa:{'si' if placa_corners is not None else 'NO'} "
                   f"dodec:{len(det_rb)}/{min_markers}")
            T_pd = None
            if placa_corners is not None and len(det_rb) >= min_markers:
                pp = estimar_pose_individual(placa_corners, args.plate_mm, K, dist)
                pd = estimar_pose_rigid_body(det_rb, rb_geom, K, dist)
                if pp is not None and pd is not None:
                    T_plate = rvec_tvec_a_matriz(*pp)
                    T_dodec = rvec_tvec_a_matriz(pd[0], pd[1])
                    M = np.linalg.inv(T_plate) @ T_dodec
                    T_pd = (M[:3, :3], M[:3, 3])

            if capturando:
                if T_pd is None:
                    estado = "capturando... (sin deteccion, esperando)"
                else:
                    R_pd, t_pd = T_pd
                    # gate de movimiento GRUESO: contra la mediana acumulada
                    if len(cap_t) >= 5:
                        med = np.median(np.array(cap_t), axis=0)
                        dt = float(np.linalg.norm(t_pd - med))
                        dR = angulo_entre(R_pd, cap_R[0])
                    else:
                        dt, dR = 0.0, 0.0
                    if dt > QUIETO_MM or dR > QUIETO_DEG:
                        log_warn(f"Postura {len(posturas)+1} ABORTADA: movimiento "
                                 f"grueso ({dt:.1f} mm / {dR:.1f} deg). ESPACIO de nuevo.")
                        capturando, cap_R, cap_t = False, [], []
                        estado = "ABORTADA (movimiento) - reintentar"
                    else:
                        cap_R.append(R_pd); cap_t.append(t_pd)
                        estado = f"capturando {len(cap_t)}/{SAMPLES_POR_POSTURA}"
                        if len(cap_t) >= SAMPLES_POR_POSTURA:
                            # filtro robusto por mediana + MAD (descarta outliers)
                            arr = np.array(cap_t)
                            med = np.median(arr, axis=0)
                            mad = np.median(np.abs(arr - med), axis=0) * 1.4826 + 1e-6
                            ok = (np.abs(arr - med) < 3.0 * mad).all(axis=1)
                            if ok.sum() < MIN_SAMPLES_POSTURA:
                                log_warn(f"Postura {len(posturas)+1} DESCARTADA: "
                                         f"demasiado ruidosa ({ok.sum()} frames utiles).")
                            else:
                                idx = []
                                for j in np.where(ok)[0]:
                                    idx.append(len(samples_R))
                                    samples_R.append(cap_R[j]); samples_t.append(cap_t[j])
                                posturas.append(idx)
                                std_p = arr[ok].std(axis=0)
                                # inclinacion del stylus vs normal de la placa:
                                # a >45 deg la punta NO asienta en el apice del
                                # cono de 90 deg (la rosca pega en el borde) y
                                # el tip aparente se corre varios mm (visto
                                # 2026-06-13: posturas rasantes con tip_z
                                # +4..+7 mm sobre la placa).
                                # eje del mango: +z del dodec apunta del tip
                                # hacia el dodecaedro (verificado 2026-06-13:
                                # con -z, vertical leia 130-180 en vez de ~0).
                                eje = np.mean([cap_R[j][:, 2] for j in np.where(ok)[0]], axis=0)
                                eje /= np.linalg.norm(eje)
                                tilt = float(np.degrees(np.arccos(np.clip(eje[2], -1, 1))))
                                # En modo DOCK el asiento esta garantizado
                                # por la cuna (eje fijo a ~65 deg de la normal):
                                # la regla de rasante NO aplica.
                                if args.divot == "DOCK":
                                    tilt = 0.0
                                posturas_tilt.append(tilt)
                                aviso = ""
                                if tilt > 45.0:
                                    aviso = ("  [!] RASANTE: se EXCLUYE del calculo. "
                                             "Repetir mas vertical.")
                                log_info(f"Postura {len(posturas)} OK: {ok.sum()}/{len(arr)} "
                                         f"frames, ruido [{std_p[0]:.2f}, {std_p[1]:.2f}, "
                                         f"{std_p[2]:.2f}] mm, inclinacion {tilt:.0f} deg{aviso}")
                            capturando, cap_R, cap_t = False, [], []
                            estado = "postura guardada - mover y ESPACIO"
            else:
                estado = ("listo - ESPACIO para capturar" if T_pd is not None
                          else "esperando deteccion")

            display = frame.copy()
            if det_rb:
                cv2.aruco.drawDetectedMarkers(
                    display, list(det_rb.values()),
                    np.array(sorted(det_rb.keys())).reshape(-1, 1))
            if placa_corners is not None:
                cv2.polylines(display, [placa_corners.astype(int).reshape(-1, 1, 2)],
                              True, (255, 0, 255), 3)
                cv2.putText(display, "PLACA", tuple(placa_corners.mean(axis=0).astype(int)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)
            cv2.putText(display, f"posturas: {len(posturas)} | {vis}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(display, estado,
                        (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(display, "ESPACIO=capturar  f=snapshot  q=terminar",
                        (10, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow("Calibracion divot iter4", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and not capturando and T_pd is not None:
                capturando, cap_R, cap_t = True, [], []
                log_info(f"Capturando postura {len(posturas)+1}...")
            elif key == ord("f"):
                n_snap += 1
                ruta = f"iter4/data/snapshot_divot_{n_snap:02d}.png"
                cv2.imwrite(ruta, frame)
                log_info(f"Snapshot crudo guardado: {ruta}")
            elif key == ord("q"):
                break
    finally:
        cam.close()
        cv2.destroyAllWindows()

    n_total = len(posturas)
    pares = [(p, t) for p, t in zip(posturas, posturas_tilt)
             if len(p) >= MIN_SAMPLES_POSTURA and t <= 45.0]
    posturas = [p for p, _t in pares]
    if len(posturas) < n_total:
        log_warn(f"{n_total - len(posturas)} postura(s) excluidas "
                 f"(rasantes >45 deg o con pocos samples).")
    print()
    log_stats(f"Posturas utiles: {len(posturas)} de {n_total} "
              f"({[len(p) for p in posturas]} samples)")
    if len(posturas) < MIN_POSTURAS:
        log_error(f"Menos de {MIN_POSTURAS} posturas: solucion debil. Repetir.")
        sys.exit(1)

    Rs = np.array(samples_R); ts = np.array(samples_t)

    def resolver(idx):
        A = np.concatenate([Rs[i] for i in idx], axis=0)
        b = np.concatenate([p_divot - ts[i] for i in idx], axis=0)
        x, _r, _k, _s = np.linalg.lstsq(A, b, rcond=None)
        rms = float(np.sqrt(np.mean((A @ x - b) ** 2)))
        return x, rms

    todos = [i for p in posturas for i in p]
    offset, rms = resolver(todos)
    log_stats(f"Offset tip (frame dodecaedro): [{offset[0]:+.3f}, {offset[1]:+.3f}, "
              f"{offset[2]:+.3f}] mm, magnitud {np.linalg.norm(offset):.2f} mm")
    log_stats(f"RMS residual global: {rms:.3f} mm")

    por_postura = np.array([resolver(p)[0] for p in posturas])
    spread = por_postura.std(axis=0)
    for k, (p, op) in enumerate(zip(posturas, por_postura)):
        log_info(f"  postura {k+1} (n={len(p)}): "
                 f"[{op[0]:+.3f}, {op[1]:+.3f}, {op[2]:+.3f}] mm")
    log_stats(f"Spread entre posturas: [{spread[0]:.3f}, {spread[1]:.3f}, "
              f"{spread[2]:.3f}] mm")
    smax = spread.max()
    nivel = ("EXCELENTE" if smax < 0.5 else "BUENO" if smax < 1.0 else
             "REGULAR" if smax < 2.0 else "INSUFICIENTE")
    log_stats(f"[{nivel}] Spread maximo: {smax:.2f} mm")
    log_info("Referencia: magnitud nominal por caliper ~92.4 mm (2026-06-12).")

    np.savez_compressed(args.output_samples, R=Rs, t=ts, divot=args.divot,
                        p_divot=p_divot,
                        posturas_inicio=[p[0] for p in posturas])
    chk = np.load(args.output_samples, allow_pickle=True)
    assert chk["R"].shape == Rs.shape
    matriz = np.eye(4); matriz[:3, 3] = offset
    np.save(args.output_matriz + ".npy", matriz)
    assert np.load(args.output_matriz + ".npy").shape == (4, 4)
    with open(args.output_matriz + ".txt", "w") as f:
        f.write("# Matriz StylusTipToDodecaedro 4x4 — calibracion por DIVOT (iter 4)\n")
        f.write(f"# Fecha UTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# Placa: {PLACA_VERSION}, marker ID {args.plate_id} @ {args.plate_mm} mm\n")
        f.write(f"# Divot {args.divot}: {np.round(p_divot, 3).tolist()} mm\n")
        f.write(f"# Geometria dodecaedro: {rb_cfg['geometry_file']} (sha {geom_sha[:16]})\n")
        f.write(f"# Samples: {len(todos)} en {len(posturas)} posturas\n")
        f.write(f"# Offset (mm): [{offset[0]:+.3f}, {offset[1]:+.3f}, {offset[2]:+.3f}]\n")
        f.write(f"# Magnitud: {np.linalg.norm(offset):.3f} mm\n")
        f.write(f"# RMS global: {rms:.3f} mm, spread: {np.round(spread, 3).tolist()} mm\n#\n")
        for fila in matriz:
            f.write(" ".join(f"{v:12.6f}" for v in fila) + "\n")
    log_info(f"Guardados: {args.output_matriz}.npy/.txt, {args.output_samples}")


if __name__ == "__main__":
    main()
