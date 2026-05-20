"""Diagnostico de topologia: detecta si los markers fisicos estan pegados
en posiciones que NO coinciden con la geometria teorica.

Estrategia: para cada par de markers que aparecen juntos en muchos frames,
estimar la distancia 3D real entre sus centros usando triangulacion estable,
y comparar con la distancia teorica.

Si las distancias coinciden, los IDs estan correctamente pegados.
Si no, hay IDs intercambiados/rotados respecto a la convencion teorica.
"""
from collections import defaultdict
from pathlib import Path

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
                [float(v[4+3*i]), float(v[5+3*i]), float(v[6+3*i])]
                for i in range(4)
            ])
    return geom


def main():
    print("=" * 78)
    print("DIAGNOSTICO TOPOLOGIA - cubo fisico vs geom teorica")
    print("=" * 78)

    d = np.load("capturas_calibracion.npz", allow_pickle=True)
    frames = list(d["frames_data"])
    K = d["K"]
    dist = d["dist"]
    geom_teorica = cargar_referencia("data/reference_dodecaedro.txt")
    ids_teoricos = sorted(geom_teorica.keys())

    # Para cada frame con >=2 markers, estimar pose de cada marker individualmente
    # con SOLVEPNP_IPPE_SQUARE (la cara plana). Tomar la pose que tiene tvec[2] > 0.
    # Luego calcular distancias entre centros en frame de camara.
    pares_distancias = defaultdict(list)
    for fi, fd in enumerate(frames[:300]):  # primeros 300 frames
        poses_individuales = {}
        for mid, corners_2d in fd["detecciones"].items():
            obj = geom_teorica[mid].astype(np.float64)
            img = corners_2d.reshape(4, 2).astype(np.float64)
            # IPPE_SQUARE devuelve dos soluciones, tomamos la fisica (tvec[2] > 0)
            retval, rvecs, tvecs, errors = cv2.solvePnPGeneric(
                obj, img, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            if retval < 1:
                continue
            # Filtrar la solucion con tvec[2] > 0 y menor error
            mejor = None
            for rv, tv, err in zip(rvecs, tvecs, errors):
                if tv[2, 0] > 0:
                    err_val = float(err[0]) if hasattr(err, "__len__") else float(err)
                    if mejor is None or err_val < mejor[2]:
                        mejor = (rv, tv, err_val)
            if mejor is not None:
                poses_individuales[mid] = mejor[1].flatten()  # tvec del centro del marker

        # Calcular distancias entre pares observados
        ids_vis = sorted(poses_individuales.keys())
        for i in range(len(ids_vis)):
            for j in range(i + 1, len(ids_vis)):
                a, b = ids_vis[i], ids_vis[j]
                d_real = np.linalg.norm(poses_individuales[a] - poses_individuales[b])
                pares_distancias[(a, b)].append(d_real)

    # Comparar con distancias teoricas
    print(f"\n{'Par':>10}  {'d_teorica':>10}  {'d_real_mean':>12}  {'std':>8}  {'n_frames':>8}  {'estado':>10}")
    print("-" * 78)
    diferencias_grandes = []
    for par, distancias in sorted(pares_distancias.items()):
        if len(distancias) < 5:
            continue
        a, b = par
        c_a_t = geom_teorica[a].mean(axis=0)
        c_b_t = geom_teorica[b].mean(axis=0)
        d_t = np.linalg.norm(c_a_t - c_b_t)
        d_r = np.mean(distancias)
        std = np.std(distancias)
        diff = abs(d_r - d_t)
        estado = "OK" if diff < 2 else ("WARN" if diff < 5 else "ERROR")
        if diff > 5:
            diferencias_grandes.append((par, d_t, d_r, diff))
        print(f"  {a:3d}-{b:3d}  {d_t:>10.2f}  {d_r:>12.2f}  {std:>8.2f}  "
              f"{len(distancias):>8}  {estado:>10}")

    if diferencias_grandes:
        print(f"\n{'='*78}")
        print(f"PARES CON DIFERENCIA > 5 MM (probables IDs mal pegados):")
        print(f"{'='*78}")
        for par, d_t, d_r, diff in sorted(diferencias_grandes, key=lambda x: -x[3]):
            print(f"  Par {par}: teorica={d_t:.1f} mm, real={d_r:.1f} mm, diff={diff:.1f} mm")
    else:
        print(f"\nTodos los pares dentro de tolerancia. La topologia del cubo MATCHEA la teorica.")


if __name__ == "__main__":
    main()
