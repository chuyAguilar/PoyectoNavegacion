# -*- coding: utf-8 -*-
"""
Limpia detecciones fantasma de un .npz de captura para el BA.

El detector tuneado (permisivo) de captura_calibracion.py genera falsos
positivos: IDs del rigid body detectados en regiones random de la imagen
(verificado 2026-06-15 con el stylus impreso: markers 183/187/188 con
RMSE 4-8 px en el BA, justo los de menos detecciones).

Metodo: por frame, estima la pose multi-marker robusta del rigid body con
la geometria teorica; descarta las detecciones cuyo error de reproyeccion
supere un umbral (default 3 px). Una deteccion fantasma cae lejos de donde
la pose del frame la predice, asi que se elimina. Guarda un .npz nuevo con
la MISMA estructura (tabular + frames_data) que espera calibrar_rigid_body.

Uso (desde codigo\):
    python iter4\limpiar_captura_fantasmas.py ^
        --input iter4\data\captura_ba_stylus_impreso.npz ^
        --teorico iter4\data\reference_stylus_impreso.txt ^
        --marker-mm 16.0 ^
        --output iter4\data\captura_ba_stylus_impreso_limpio.npz
"""
import argparse
import numpy as np
import cv2


def cargar_geom(ruta):
    geom = {}
    for line in open(ruta, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        v = s.split()
        geom[int(v[0])] = np.array([float(x) for x in v[1:]]).reshape(5, 3)[1:]
    return geom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--teorico", required=True)
    ap.add_argument("--marker-mm", type=float, default=16.0)
    ap.add_argument("--umbral-px", type=float, default=3.0)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    d = np.load(args.input, allow_pickle=True)
    K, dist = d["K"], d["dist"]
    frames = list(d["frames_data"])
    geom = cargar_geom(args.teorico)
    rb_ids = set(int(x) for x in d["rb_ids"])

    n_in = n_out = 0
    descartes = {}
    frames_limpios = []
    for fd in frames:
        det = fd["detecciones"]
        n_in += len(det)
        if len(det) < 4:
            # con <4 markers no se puede validar robusto; conservar tal cual
            frames_limpios.append(fd)
            continue
        # pose multi-marker del frame con la geometria teorica
        op, ip, ids = [], [], []
        for m, c in det.items():
            if m in geom:
                op.append(geom[m]); ip.append(c.reshape(4, 2)); ids.append(m)
        op = np.concatenate(op).astype(np.float64)
        ip = np.concatenate(ip).astype(np.float64)
        ok, rv, tv = cv2.solvePnP(op, ip.reshape(-1, 1, 2), K, dist,
                                  flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            frames_limpios.append(fd)
            continue
        # reproyeccion por marker; descartar los outliers
        det_lim = {}
        dep_lim = {}
        dep_in = fd.get("corners_depth_mm", {})
        for m in ids:
            proj, _ = cv2.projectPoints(geom[m], rv, tv, K, dist)
            err = np.linalg.norm(proj.reshape(4, 2) - det[m].reshape(4, 2), axis=1).mean()
            if err <= args.umbral_px:
                det_lim[m] = det[m]
                if m in dep_in:
                    dep_lim[m] = dep_in[m]
            else:
                n_out += 1
                descartes[m] = descartes.get(m, 0) + 1
        nuevo = dict(fd)
        nuevo["detecciones"] = det_lim
        nuevo["corners_depth_mm"] = dep_lim
        frames_limpios.append(nuevo)

    print(f"[STATS] Detecciones: {n_in} -> {n_in - n_out} ({n_out} descartadas)")
    print("[STATS] Descartes por marker (fantasmas / misdetecciones):")
    for m in sorted(descartes):
        print(f"  ID {m}: {descartes[m]}")

    # reconstruir estructura tabular (como captura_calibracion)
    mids, c2d, cdep, offsets = [], [], [], [0]
    for fd in frames_limpios:
        for m, c in fd["detecciones"].items():
            mids.append(int(m))
            c2d.append(np.asarray(c, dtype=np.float32).reshape(4, 2))
            dep = fd.get("corners_depth_mm", {}).get(m, np.zeros(4, np.float32))
            cdep.append(np.asarray(dep, dtype=np.float32))
        offsets.append(len(mids))

    out = {
        "frames_data": np.array(frames_limpios, dtype=object),
        "K": d["K"], "dist": d["dist"], "rb_ids": d["rb_ids"],
        "timestamps": d["timestamps"],
        "frame_offsets": np.array(offsets, dtype=np.int32),
        "marker_ids": np.array(mids, dtype=np.int32),
        "corners_2d": (np.asarray(c2d, dtype=np.float32)
                       if c2d else np.zeros((0, 4, 2), np.float32)),
        "corners_depth_mm": (np.asarray(cdep, dtype=np.float32)
                             if cdep else np.zeros((0, 4), np.float32)),
        "metadata_json": d["metadata_json"],
    }
    np.savez_compressed(args.output, **out)
    chk = np.load(args.output, allow_pickle=True)
    assert len(chk["marker_ids"]) == len(mids)
    print(f"[INFO] Guardado y verificado: {args.output} "
          f"({len(frames_limpios)} frames, {len(mids)} detecciones)")


if __name__ == "__main__":
    main()
