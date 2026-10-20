# -*- coding: utf-8 -*-
"""
Diagnostico de alineacion D2C (depth-to-color) con escena ESTATICA.

Contexto (2026-06-11): el BA mixto 2D+3D mostro que el depth muestreado en las
esquinas de los markers lee +58 mm (mediana) DETRAS del plano predicho por IPPE.
La corrida 1 de este script demostro que el centro de la cara esta igual de mal
que el borde y que no hay shift chico que lo arregle: el overlay mostro la
silueta del depth corrida decenas de px respecto al objeto -> la alineacion SW
del SDK esta produciendo un mapeo espacial incorrecto.

Esta version (corrida 2) ademas:
  - Guarda el depth CRUDO 640x576 (pre-align) + K_depth + dist_depth + T_d2c
    para poder implementar y validar una alineacion manual offline.
  - Enumera si hay HW D2C disponible en otros perfiles de color.

Analisis por frame:
  1. Pose IPPE -> plano predicho por marker.
  2. Depth en grilla 9x9 sobre la cara -> error por region (centro/medio/borde).
  3. Busqueda de shift (du, dv) en +-12 px que minimiza error interior.

Salidas en iter4/data/diag_d2c/:
  - diag_d2c_frames.npz  (color + depth alineado + depth crudo + calibracion)
  - overlay_NN.png       (bordes del depth en rojo sobre color, markers verde)

Uso (desde codigo\):
    python iter4\test_alineacion_d2c.py
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from camera_backend import create_backend
from captura_calibracion import cargar_config, crear_detector


def log_info(m): print(f"[INFO] {m}")
def log_warn(m): print(f"[WARN] {m}")
def log_stats(m): print(f"[STATS] {m}")


MARKER_MM_DEFAULT = 13.4
RB_IDS = set(range(170, 181))
GRID_N = 9
FRAC_MAX = 0.45
FRAC_INTERIOR = 0.30
SHIFT_MAX = 12
SHIFT_STEP = 2


def pose_ippe(corners, K, dist, marker_mm):
    h = marker_mm / 2.0
    objp = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]], dtype=np.float64)
    imgp = corners.astype(np.float64).reshape(4, 1, 2)
    try:
        n_sol, rvecs, tvecs, errors = cv2.solvePnPGeneric(
            objp, imgp, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    except cv2.error:
        return None
    cand = [(j, float(errors[j][0]) if errors is not None else 0.0)
            for j in range(n_sol) if float(tvecs[j][2, 0]) > 0]
    if not cand:
        return None
    j, _ = min(cand, key=lambda t: t[1])
    return rvecs[j], tvecs[j]


def grilla_marker(rvec, tvec, K, dist, marker_mm):
    f = np.linspace(-FRAC_MAX, FRAC_MAX, GRID_N)
    fx, fy = np.meshgrid(f, f)
    frac = np.column_stack([fx.ravel(), fy.ravel()])
    pts_obj = np.column_stack([frac * marker_mm, np.zeros(len(frac))])
    R, _ = cv2.Rodrigues(rvec)
    pts_cam = (R @ pts_obj.T).T + tvec.ravel()
    pix, _ = cv2.projectPoints(pts_obj, rvec, tvec, K, dist)
    return pix.reshape(-1, 2), pts_cam[:, 2], frac


def muestrear(depth_mm, pix, du=0, dv=0):
    H, W = depth_mm.shape[:2]
    u = np.round(pix[:, 0] + du).astype(int)
    v = np.round(pix[:, 1] + dv).astype(int)
    ok = (u >= 0) & (u < W) & (v >= 0) & (v < H)
    z = np.zeros(len(pix), dtype=np.float32)
    z[ok] = depth_mm[v[ok], u[ok]]
    return z


def analizar_frame(detecciones, depth_mm, K, dist, marker_mm):
    grillas = []
    for mid, corners in detecciones.items():
        p = pose_ippe(corners, K, dist, marker_mm)
        if p is None:
            continue
        grillas.append((mid,) + grilla_marker(p[0], p[1], K, dist, marker_mm))
    if not grillas:
        return None

    regiones = {"centro (|f|<=0.15)": 0.15, "medio (0.15-0.30)": 0.30,
                "borde (0.30-0.45)": FRAC_MAX + 1e-9}
    errs_region = {r: [] for r in regiones}
    for mid, pix, z_pred, frac in grillas:
        z_obs = muestrear(depth_mm, pix)
        val = z_obs > 0
        fmax = np.abs(frac).max(axis=1)
        prev = 0.0
        for r, lim in regiones.items():
            sel = val & (fmax > prev) & (fmax <= lim)
            errs_region[r].extend((z_obs[sel] - z_pred[sel]).tolist())
            prev = lim

    mejores = None
    err00 = float("nan")
    for du in range(-SHIFT_MAX, SHIFT_MAX + 1, SHIFT_STEP):
        for dv in range(-SHIFT_MAX, SHIFT_MAX + 1, SHIFT_STEP):
            errs = []
            for mid, pix, z_pred, frac in grillas:
                sel = np.abs(frac).max(axis=1) <= FRAC_INTERIOR
                z_obs = muestrear(depth_mm, pix[sel], du, dv)
                v = z_obs > 0
                errs.extend(np.abs(z_obs[v] - z_pred[sel][v]).tolist())
            if len(errs) < 10:
                continue
            med = float(np.median(errs))
            if du == 0 and dv == 0:
                err00 = med
            if mejores is None or med < mejores[2]:
                mejores = (du, dv, med)
    return errs_region, mejores, err00, len(grillas)


def guardar_overlay(frame, depth_mm, detecciones, ruta):
    d = np.clip((depth_mm - 300.0) / 600.0 * 255.0, 0, 255).astype(np.uint8)
    edges = cv2.Canny(d, 30, 90)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    out = frame.copy()
    out[edges > 0] = (0, 0, 255)
    for mid, c in detecciones.items():
        cv2.polylines(out, [c.astype(int).reshape(-1, 1, 2)], True, (0, 255, 0), 2)
        cv2.putText(out, str(mid), tuple(c.mean(axis=0).astype(int)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imwrite(str(ruta), out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="iter4/tracker_config.yaml")
    parser.add_argument("--n-frames", type=int, default=15)
    parser.add_argument("--marker-mm", type=float, default=MARKER_MM_DEFAULT)
    parser.add_argument("--outdir", default="iter4/data/diag_d2c")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cfg = cargar_config(args.config)
    detector, _, _, _ = crear_detector(cfg["markers"])

    log_info("IMPORTANTE: dodecaedro ESTATICO (apoyado/sujetado mecanicamente,")
    log_info("NO en la mano), a 50-70 cm, con varios markers visibles.")

    cam = create_backend(cfg["camera"])
    cam.open()
    K, dist = cam.get_intrinsics()
    try:
        K_depth, dist_depth = cam.get_depth_intrinsics()
        T_d2c = cam.get_extrinsic_depth_to_color()
    except AttributeError:
        K_depth = dist_depth = T_d2c = None

    # Enumerar disponibilidad de HW D2C por perfil de color (informativo)
    try:
        from pyorbbecsdk import OBSensorType, OBAlignMode
        plist = cam.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        log_info("Disponibilidad HW D2C por perfil de color:")
        for i in range(min(plist.get_count(), 12)):
            p = plist.get_video_stream_profile_by_index(i) if hasattr(
                plist, "get_video_stream_profile_by_index") else plist[i]
            try:
                n_hw = len(cam.pipeline.get_d2c_depth_profile_list(p, OBAlignMode.HW_MODE))
            except Exception:
                n_hw = -1
            log_info(f"  {p.get_width()}x{p.get_height()} @{p.get_fps()} "
                     f"{p.get_format()}: {n_hw} perfiles HW")
    except Exception as exc:
        log_warn(f"No se pudo enumerar HW D2C: {exc}")

    log_info("Comenzando en 5 segundos...")
    time.sleep(5)

    capturados = []  # (frame, depth_alineado, detecciones, depth_raw)
    intentos = 0
    while len(capturados) < args.n_frames and intentos < args.n_frames * 10:
        intentos += 1
        frame, depth_mm, _ = cam.read()
        if frame is None or depth_mm is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners_all, ids_all, _ = detector.detectMarkers(gray)
        if ids_all is None:
            continue
        det = {int(m): corners_all[i].reshape(4, 2).copy()
               for i, m in enumerate(ids_all.flatten()) if int(m) in RB_IDS}
        if len(det) < 3:
            continue
        capturados.append((frame, depth_mm, det, getattr(cam, "last_depth_raw", None)))
        log_info(f"  frame {len(capturados)}/{args.n_frames}: {len(det)} markers {sorted(det)}")
    cam.close()

    if not capturados:
        log_warn("No se capturo nada util. Revisar markers visibles / iluminacion.")
        sys.exit(1)

    # === Analisis ===
    todos_region = {}
    shifts = []
    for idx, (frame, depth_mm, det, _) in enumerate(capturados):
        r = analizar_frame(det, depth_mm, K, dist, args.marker_mm)
        if r is None:
            continue
        errs_region, mejor, err00, n_mk = r
        shifts.append(mejor[:2])
        log_stats(f"frame {idx}: {n_mk} markers | err interior s/shift: "
                  f"{err00:.1f} mm | mejor shift ({mejor[0]:+d},{mejor[1]:+d}) px "
                  f"-> {mejor[2]:.1f} mm")
        for reg, e in errs_region.items():
            todos_region.setdefault(reg, []).extend(e)

    print()
    log_stats("=== ERROR depth - z_pred POR REGION (todos los frames, mm) ===")
    for reg, e in todos_region.items():
        e = np.array(e)
        if len(e):
            log_stats(f"  {reg:>20}: n={len(e):5d} mediana={np.median(e):+7.1f} "
                      f"p25={np.percentile(e, 25):+7.1f} p75={np.percentile(e, 75):+7.1f}")

    shifts = np.array(shifts)
    log_stats(f"=== SHIFT OPTIMO: mediana du={np.median(shifts[:, 0]):+.0f} px, "
              f"dv={np.median(shifts[:, 1]):+.0f} px "
              f"(std {shifts[:, 0].std():.1f}, {shifts[:, 1].std():.1f}) ===")

    # === Guardar para analisis offline ===
    n_save = min(4, len(capturados))
    npz_path = outdir / "diag_d2c_frames.npz"
    extra = {}
    if all(c[3] is not None for c in capturados[:n_save]):
        extra["depth_raw"] = np.stack(
            [c[3].astype(np.uint16) for c in capturados[:n_save]])
        log_info(f"depth_raw incluido: {extra['depth_raw'].shape}")
    else:
        log_warn("depth_raw NO disponible (backend sin instrumentacion?)")
    if K_depth is not None:
        extra["K_depth"] = K_depth
        extra["dist_depth"] = np.asarray(dist_depth)
        extra["T_d2c"] = T_d2c
    np.savez_compressed(
        npz_path,
        color=np.stack([c[0] for c in capturados[:n_save]]),
        depth_mm=np.stack([c[1].astype(np.uint16) for c in capturados[:n_save]]),
        K=K, dist=np.asarray(dist),
        marker_mm=args.marker_mm,
        **extra,
    )
    chk = np.load(npz_path)
    assert chk["color"].shape[0] == n_save and chk["depth_mm"].shape[0] == n_save
    log_info(f"Guardado y verificado: {npz_path} ({n_save} frames, "
             f"claves: {sorted(chk.files)})")

    for idx in range(n_save):
        frame, depth_mm, det, _ = capturados[idx]
        guardar_overlay(frame, depth_mm, det, outdir / f"overlay_{idx:02d}.png")
    log_info(f"Overlays guardados en {outdir}\\overlay_*.png")


if __name__ == "__main__":
    main()
