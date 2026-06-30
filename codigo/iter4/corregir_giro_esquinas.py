# -*- coding: utf-8 -*-
"""
Corrige el GIRO DE ESQUINAS por-marker de una geometria teorica del dodecaedro,
ajustandola a como estan FISICAMENTE pegados los marcadores en ESTA impresion.

Por que existe: generar_reference_dodecaedro.py asume una convencion de esquinas
(orden c0..c3) que puede NO coincidir con la fisica (p. ej. punto rojo abajo-derecha).
Si no coincide, solvePnP no cuadra: la limpieza descarta ~90% y el BA no converge.
El giro correcto puede ser DISTINTO por cara (la TOP suele ir distinto a los
laterales) y depende de COMO se pegaron los marcadores -> se DETECTA de los datos,
no se asume. (Lo descubrimos a mano en la calibracion del dodecaedro v2.)

Metodo:
  1. Bootstrap global: prueba giro global 0/90/180/270 en TODOS los markers y elige
     el de menor reproyeccion mediana (capta el giro dominante de los laterales).
  2. Refinamiento por-marker: con esa geometria, calcula la pose de cada frame bien
     ajustado y vota, por marker, que giro minimiza su reproyeccion. Itera.
  3. Escribe la geometria con las esquinas ya rotadas (drop-in para limpieza + BA).

Uso:
    python iter4\\corregir_giro_esquinas.py ^
        --input iter4\\data\\captura_ba.npz ^
        --teorico iter4\\data\\reference_dodecaedro_doctor_real.txt ^
        --marker-mm 16.0 ^
        --output iter4\\data\\reference_dodecaedro_doctor_fix.txt
"""
import argparse
import random
import numpy as np
import cv2


def log(m):
    print(f"[GIRO] {m}", flush=True)


def cargar_geom(ruta):
    g = {}
    for line in open(ruta, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        v = s.split()
        if len(v) < 16:
            continue
        vals = np.array([float(x) for x in v[1:16]]).reshape(5, 3)
        g[int(v[0])] = vals[1:]  # 4 esquinas (4,3)
    return g


def pose_frame(geom_roll, det, K, dist, min_markers=4):
    op, ip, ids = [], [], []
    for m, c in det.items():
        if m in geom_roll:
            op.append(geom_roll[m])
            ip.append(c.reshape(4, 2))
            ids.append(m)
    if len(ids) < min_markers:
        return None
    op = np.concatenate(op).astype(np.float64)
    ip = np.concatenate(ip).astype(np.float64)
    ok, rv, tv = cv2.solvePnP(op, ip.reshape(-1, 1, 2), K, dist,
                              flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None
    return rv, tv, ids, op, ip


def reproj_mediana(base, roll, frames, K, dist, sample):
    geom_roll = {m: np.roll(base[m], roll[m], axis=0) for m in base}
    errs = []
    for fd in sample:
        r = pose_frame(geom_roll, fd["detecciones"], K, dist)
        if r is None:
            continue
        rv, tv, ids, op, ip = r
        proj, _ = cv2.projectPoints(op, rv, tv, K, dist)
        errs.append(np.linalg.norm(proj.reshape(-1, 2) - ip, axis=1).mean())
    return float(np.median(errs)) if errs else 1e9


def main():
    ap = argparse.ArgumentParser(description="Corrige el giro de esquinas por-marker.")
    ap.add_argument("--input", required=True, help=".npz de captura_calibracion")
    ap.add_argument("--teorico", required=True, help="geometria teorica reference_*.txt")
    ap.add_argument("--marker-mm", type=float, required=True,
                    help="(informativo: la geometria ya trae la escala)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--frame-thr-px", type=float, default=6.0)
    ap.add_argument("--max-iter", type=int, default=6)
    args = ap.parse_args()

    d = np.load(args.input, allow_pickle=True)
    K, dist = d["K"], d["dist"]
    frames = list(d["frames_data"])
    base = cargar_geom(args.teorico)
    ids_all = sorted(base.keys())
    log(f"Markers en geometria: {ids_all}")
    log(f"Frames en captura: {len(frames)}")

    random.seed(0)
    cand = [fd for fd in frames if len(fd["detecciones"]) >= 4]
    if not cand:
        log("ERROR: ningun frame con >=4 markers. Captura insuficiente.")
        raise SystemExit(1)
    sample = random.sample(cand, min(400, len(cand)))
    log(f"Frames con >=4 markers: {len(cand)} (muestreo {len(sample)})")

    log("Paso 1: bootstrap del giro global (0/90/180/270 en todos)...")
    mejor_g, mejor_med = 0, 1e9
    for g in range(4):
        med = reproj_mediana(base, {m: g for m in ids_all}, frames, K, dist, sample)
        log(f"  giro global {g*90:3d} deg -> reproyeccion mediana {med:6.2f} px")
        if med < mejor_med:
            mejor_g, mejor_med = g, med
    log(f"  giro global elegido: {mejor_g*90} deg (mediana {mejor_med:.2f} px)")
    roll = {m: mejor_g for m in ids_all}

    log("Paso 2: refinamiento por-marker (votacion, leave-one-out)...")
    votos = {m: [0, 0, 0, 0] for m in ids_all}
    for it in range(args.max_iter):
        geom_roll = {m: np.roll(base[m], roll[m], axis=0) for m in base}
        votos = {m: [0, 0, 0, 0] for m in ids_all}
        for fd in frames:
            det = fd["detecciones"]
            present = [m for m in det if m in base]
            if len(present) < 5:
                continue
            for m in present:
                # pose con los OTROS markers (no m): el voto de m no depende de su
                # propio giro -> evita que un marker mal-rotado se quede sin votos.
                otros = [x for x in present if x != m]
                if len(otros) < 4:
                    continue
                op = np.concatenate([geom_roll[x] for x in otros]).astype(np.float64)
                ip = np.concatenate([det[x].reshape(4, 2) for x in otros]).astype(np.float64)
                ok, rv, tv = cv2.solvePnP(op, ip.reshape(-1, 1, 2), K, dist,
                                          flags=cv2.SOLVEPNP_ITERATIVE)
                if not ok:
                    continue
                proj, _ = cv2.projectPoints(op, rv, tv, K, dist)
                if np.linalg.norm(proj.reshape(-1, 2) - ip, axis=1).mean() > args.frame_thr_px:
                    continue
                cc = det[m].reshape(4, 2)
                best, berr = 0, 1e9
                for rr in range(4):
                    pj, _ = cv2.projectPoints(np.roll(base[m], rr, axis=0), rv, tv, K, dist)
                    e = np.linalg.norm(pj.reshape(4, 2) - cc, axis=1).mean()
                    if e < berr:
                        best, berr = rr, e
                votos[m][best] += 1
        nuevo = {m: (int(np.argmax(votos[m])) if sum(votos[m]) else roll[m]) for m in ids_all}
        cambios = {m: (roll[m] * 90, nuevo[m] * 90) for m in ids_all if nuevo[m] != roll[m]}
        log(f"  iter {it}: cambios = {cambios if cambios else 'ninguno'}")
        roll = nuevo
        if not cambios:
            break

    log("Giro final por marker (grados):")
    for m in ids_all:
        log(f"  ID {m:3d}: {roll[m]*90:3d} deg   votos={votos[m]}")

    geom_fix = {m: np.roll(base[m], roll[m], axis=0) for m in base}
    per = {}
    for fd in frames:
        r = pose_frame(geom_fix, fd["detecciones"], K, dist)
        if r is None:
            continue
        rv, tv, ids, op, ip = r
        for m in ids:
            pj, _ = cv2.projectPoints(geom_fix[m], rv, tv, K, dist)
            err = np.linalg.norm(pj.reshape(4, 2) - fd["detecciones"][m].reshape(4, 2), axis=1)
            per.setdefault(m, []).extend(err.tolist())
    log("Reproyeccion por marker tras el giro (mediana):")
    allv = []
    for m in sorted(per):
        a = np.array(per[m]); allv += a.tolist()
        log(f"  ID {m:3d}: mediana {np.median(a):5.2f} px  p90 {np.percentile(a,90):6.2f}  n={len(a)}")
    allv = np.array(allv)
    med_glob = float(np.median(allv)) if len(allv) else 1e9
    log(f"GLOBAL mediana {med_glob:.2f} px, <=8px {100*(allv<=8).mean():.1f}%")
    if med_glob > 6:
        log("[WARN] mediana alta tras el giro: revisa marker_mm, topologia (orden de "
            "anillos) o cobertura/calidad de la captura.")
    else:
        log("[OK] geometria lista para limpieza + BA.")

    out = [
        "# Geometria del dodecaedro con esquinas rotadas por-marker (corregir_giro_esquinas)",
        f"# Origen teorico: {args.teorico}",
        "# Giro por marker (grados): " + ", ".join(f"{m}:{roll[m]*90}" for m in ids_all),
        "# Formato: tag_id  cx cy cz  c0..c3  (OpenCV TL,TR,BR,BL ya rotadas)",
        "#",
    ]
    for m in sorted(geom_fix.keys()):
        c = geom_fix[m]
        centro = c.mean(axis=0)
        row = list(centro) + list(c.flatten())
        out.append(f"{m:3d}   " + "  ".join(f"{v:+8.3f}" for v in row))
    open(args.output, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    log(f"Guardado: {args.output}")
    log("Siguiente: limpiar_captura_fantasmas.py --teorico <salida> --umbral-px 12  ->  "
        "calibrar_rigid_body.py --teorico <salida> --no-depth --no-sparse")


if __name__ == "__main__":
    main()
