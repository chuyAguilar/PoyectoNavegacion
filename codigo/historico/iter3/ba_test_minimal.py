"""BA TEST MINIMAL - autocontenido, replica iter 1 lo mas posible.

Uso:
    python ba_test_minimal.py [--input X.npz] [--loss linear|soft_l1|huber|cauchy] [--method trf|dogbox]

Objetivo: identificar si huber+trf+scipy 1.17 esta roto vs versiones anteriores.
"""
import argparse
import time
import numpy as np
import cv2
from scipy.optimize import least_squares


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
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="capturas_calibracion.npz")
    p.add_argument("--teorico", default="data/reference_dodecaedro.txt")
    p.add_argument("--ancla", type=int, default=151)
    p.add_argument("--max-frames", type=int, default=500)
    p.add_argument("--loss", default="huber",
                   choices=["linear", "soft_l1", "huber", "cauchy"])
    p.add_argument("--method", default="trf", choices=["trf", "dogbox"])
    p.add_argument("--f-scale", type=float, default=2.0)
    p.add_argument("--max-nfev", type=int, default=200)
    args = p.parse_args()

    print(f"--- BA TEST: loss={args.loss}, method={args.method}, max_frames={args.max_frames} ---")
    import scipy
    print(f"SciPy: {scipy.__version__}, NumPy: {np.__version__}, OpenCV: {cv2.__version__}")

    # Cargar dataset
    data = np.load(args.input, allow_pickle=True)
    frames = list(data["frames_data"])
    K = data["K"]
    dist = data["dist"]
    print(f"Frames: {len(frames)}")

    # Submuestreo
    if len(frames) > args.max_frames:
        idx = np.linspace(0, len(frames)-1, args.max_frames).astype(int)
        frames = [frames[i] for i in idx]
        print(f"Submuestreado a {len(frames)}")

    # Cargar geom teorica
    geom_teorica = cargar_referencia(args.teorico)
    ids_orden = sorted(geom_teorica.keys())
    ancla = args.ancla
    geom_anclada = geom_teorica[ancla].copy()

    # Poses iniciales con solvePnP
    poses_init = []
    frames_validos = []
    for fd in frames:
        obj_pts, img_pts = [], []
        for mid, c2d in fd["detecciones"].items():
            if mid in geom_teorica:
                obj_pts.append(geom_teorica[mid])
                img_pts.append(c2d.reshape(4, 2))
        if not obj_pts:
            continue
        obj_pts = np.concatenate(obj_pts).astype(np.float32)
        img_pts = np.concatenate(img_pts).astype(np.float32)
        if len(obj_pts) < 4:
            continue
        flag = cv2.SOLVEPNP_IPPE_SQUARE if len(obj_pts) == 4 else cv2.SOLVEPNP_ITERATIVE
        ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist, flags=flag)
        if ok:
            frames_validos.append(fd)
            poses_init.append((rvec.flatten(), tvec.flatten()))
    print(f"Frames con pose valida: {len(frames_validos)}")

    # Construir vector inicial de params (libre: 12 floats por marker no-ancla + 6 por pose)
    params = []
    offsets = {}
    for mid in ids_orden:
        if mid == ancla:
            continue
        offsets[mid] = len(params)
        params.extend(geom_teorica[mid].flatten().tolist())
    n_geom = len(params)
    for rvec, tvec in poses_init:
        params.extend(rvec.tolist())
        params.extend(tvec.tolist())
    params_init = np.array(params)
    print(f"Params: {len(params_init)} ({n_geom} geom + {len(params_init)-n_geom} pose)")

    # Funcion de residuos
    def residuos(p):
        geom_run = {ancla: geom_anclada}
        for mid in ids_orden:
            if mid == ancla:
                continue
            i = offsets[mid]
            geom_run[mid] = p[i:i+12].reshape(4, 3)
        res = []
        for f_idx, fd in enumerate(frames_validos):
            rvec = p[n_geom + f_idx*6 : n_geom + f_idx*6 + 3]
            tvec = p[n_geom + f_idx*6 + 3 : n_geom + f_idx*6 + 6]
            for mid, c2d in fd["detecciones"].items():
                if mid not in geom_run:
                    continue
                proy, _ = cv2.projectPoints(
                    geom_run[mid].astype(np.float64),
                    rvec.astype(np.float64), tvec.astype(np.float64), K, dist
                )
                res.append((proy.reshape(4, 2) - c2d).flatten())
        return np.concatenate(res)

    res_init = residuos(params_init)
    rmse_init = np.sqrt(np.mean(res_init**2))
    print(f"RMSE inicial: {rmse_init:.4f} px")

    # BA
    print(f"\nEjecutando least_squares...")
    t0 = time.time()
    r = least_squares(residuos, params_init, method=args.method, loss=args.loss,
                      f_scale=args.f_scale, max_nfev=args.max_nfev, verbose=2)
    t = time.time() - t0
    rmse_fin = np.sqrt(np.mean(r.fun**2))
    print(f"\nTiempo: {t:.1f}s")
    print(f"Status: {r.status} ({r.message})")
    print(f"Iteraciones (nfev): {r.nfev}")
    print(f"RMSE: {rmse_init:.4f} -> {rmse_fin:.4f} px ({100*(1-rmse_fin/rmse_init):.1f}% reduccion)")
    print(f"Success: {r.success}")


if __name__ == "__main__":
    main()
