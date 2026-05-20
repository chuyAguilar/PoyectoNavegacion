"""Diagnostico rapido para entender por que RMSE inicial es 15 px.

Ejecutar:
    python diagnostico_etapa_d.py
"""
from pathlib import Path
import sys

import cv2
import numpy as np


def cargar_referencia(ruta):
    geom = {}
    with open(ruta) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            v = linea.split()
            if len(v) < 16:
                continue
            geom[int(v[0])] = np.array([
                [float(v[4]),  float(v[5]),  float(v[6])],
                [float(v[7]),  float(v[8]),  float(v[9])],
                [float(v[10]), float(v[11]), float(v[12])],
                [float(v[13]), float(v[14]), float(v[15])],
            ])
    return geom


def main():
    print("=" * 78)
    print("DIAGNOSTICO ETAPA D")
    print("=" * 78)

    # Cargar dataset
    d = np.load("capturas_calibracion.npz", allow_pickle=True)
    frames = list(d["frames_data"])
    K = d["K"]
    dist = d["dist"]
    print(f"\nFrames: {len(frames)}")
    print(f"K =\n{K}")
    print(f"dist = {dist.flatten()}")

    # Cargar geom teorica
    geom_teorica = cargar_referencia("data/reference_dodecaedro.txt")
    print(f"\nIDs en geom teorica: {sorted(geom_teorica.keys())}")

    # Inspeccionar primer frame
    fd0 = frames[0]
    ids_visibles = sorted(fd0["detecciones"].keys())
    print(f"\n--- FRAME 0 ---")
    print(f"Markers detectados: {ids_visibles}")

    # Primer marker visible
    primer_mid = ids_visibles[0]
    corners_2d = fd0["detecciones"][primer_mid]
    print(f"\nID {primer_mid} corners 2D (orden c0=TL, c1=TR, c2=BR, c3=BL):")
    for i, c in enumerate(corners_2d):
        print(f"  c{i}: ({c[0]:7.2f}, {c[1]:7.2f})")

    # Probar solvePnP con UN solo marker
    obj = geom_teorica[primer_mid].astype(np.float32)
    img = corners_2d.reshape(4, 2).astype(np.float32)
    ok, rvec, tvec = cv2.solvePnP(obj, img, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    print(f"\nsolvePnP UN marker ({primer_mid}): ok={ok}")
    print(f"  rvec = {rvec.flatten()}")
    print(f"  tvec = {tvec.flatten()} (norma {np.linalg.norm(tvec):.1f} mm)")

    proy, _ = cv2.projectPoints(obj, rvec, tvec, K, dist)
    proy = proy.reshape(4, 2)
    print(f"  Reproyeccion:")
    for i in range(4):
        diff = proy[i] - corners_2d[i]
        print(f"    c{i}: detect=({corners_2d[i][0]:7.2f}, {corners_2d[i][1]:7.2f}), "
              f"proy=({proy[i][0]:7.2f}, {proy[i][1]:7.2f}), err={np.linalg.norm(diff):.2f}px")

    # Probar solvePnP con TODOS los markers visibles juntos
    obj_pts = []
    img_pts = []
    for mid in ids_visibles:
        obj_pts.append(geom_teorica[mid])
        img_pts.append(fd0["detecciones"][mid].reshape(4, 2))
    obj_pts = np.concatenate(obj_pts).astype(np.float32)
    img_pts = np.concatenate(img_pts).astype(np.float32)
    ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist,
                                    flags=cv2.SOLVEPNP_ITERATIVE)
    print(f"\nsolvePnP TODOS los markers ({len(ids_visibles)}): ok={ok}")
    print(f"  rvec = {rvec.flatten()}")
    print(f"  tvec = {tvec.flatten()} (norma {np.linalg.norm(tvec):.1f} mm)")

    # RMSE de reproyeccion por marker con esta pose
    print(f"\n  RMSE por marker con pose multi-marker:")
    for mid in ids_visibles:
        proy, _ = cv2.projectPoints(geom_teorica[mid].astype(np.float64),
                                      rvec, tvec, K, dist)
        proy = proy.reshape(4, 2)
        diff = (proy - fd0["detecciones"][mid]).flatten()
        rmse = np.sqrt(np.mean(diff**2))
        print(f"    ID {mid}: RMSE = {rmse:7.2f} px")

    # Refinar con LM y recalcular
    if ok:
        rvec_ref, tvec_ref = cv2.solvePnPRefineLM(obj_pts, img_pts, K, dist, rvec, tvec)
        print(f"\n  Despues de RefineLM:")
        for mid in ids_visibles:
            proy, _ = cv2.projectPoints(geom_teorica[mid].astype(np.float64),
                                          rvec_ref, tvec_ref, K, dist)
            proy = proy.reshape(4, 2)
            diff = (proy - fd0["detecciones"][mid]).flatten()
            rmse = np.sqrt(np.mean(diff**2))
            print(f"    ID {mid}: RMSE = {rmse:7.2f} px")

    # Estadisticas globales: RMSE por frame para los primeros 20
    print(f"\n--- RMSE de reproyeccion por frame (primeros 20) ---")
    for fi, fd in enumerate(frames[:20]):
        obj_pts, img_pts = [], []
        for mid in fd["detecciones"]:
            obj_pts.append(geom_teorica[mid])
            img_pts.append(fd["detecciones"][mid].reshape(4, 2))
        obj_pts = np.concatenate(obj_pts).astype(np.float32)
        img_pts = np.concatenate(img_pts).astype(np.float32)
        ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist,
                                        flags=cv2.SOLVEPNP_ITERATIVE)
        rvec, tvec = cv2.solvePnPRefineLM(obj_pts, img_pts, K, dist, rvec, tvec)
        proy, _ = cv2.projectPoints(obj_pts.astype(np.float64), rvec, tvec, K, dist)
        proy = proy.reshape(-1, 2)
        rmse = np.sqrt(np.mean((proy - img_pts)**2))
        print(f"  Frame {fi}: {len(fd['detecciones'])} markers, RMSE={rmse:6.2f} px")


if __name__ == "__main__":
    main()
