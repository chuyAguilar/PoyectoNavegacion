# -*- coding: utf-8 -*-
"""
PRUEBA 3 - Aislar el hueso (phantom) del fondo y limpiar la nube.

Objetivo (dentro del marco de registro por superficie):
  Tomar la nube cruda (todo lo que ve la camara) y dejar SOLO el hueso, limpio
  de ruido, listo para registrarlo contra el STL.

Pipeline (cada paso imprime cuantos puntos quedan, para diagnosticar):
  1. Cargar la nube (la ultima .ply de prueba 1, o capturar una nueva con --capturar).
  2. RECORTE por profundidad: conservar solo puntos entre --zmin y --zmax.
  3. QUITAR OUTLIERS: remove_statistical_outlier elimina flying pixels y estelas.
  4. QUITAR LA MESA: segment_plane (RANSAC) detecta y elimina el plano dominante.
  5. QUEDARSE CON UN OBJETO: cluster_dbscan agrupa lo que queda. Por defecto
     conserva el grupo MAYOR; con --pick marcas el hueso con Shift+click.
  6. Guardar la nube aislada y (con --ver) mostrarla.

REGLAS: capturar fuera de la caja de luz, escena estatica, hueso a ~0.5-0.6 m
sobre mesa despejada y mas o menos centrado frente a la camara.

Uso (desde la carpeta del repo):
    python femto_pruebas\03_aislar_phantom.py --capturar --pick --ver
    python femto_pruebas\03_aislar_phantom.py --ply femto_pruebas\nubes\nube_XXXX.ply --pick --ver
    python femto_pruebas\03_aislar_phantom.py --zmin 0.40 --zmax 0.65 --no-plano --ver

Salida:
    femto_pruebas\nubes\phantom_YYYYmmdd_HHMMSS.ply
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import open3d as o3d

REPO = Path(__file__).resolve().parents[1]
ITER4 = REPO / "codigo" / "iter4"
sys.path.insert(0, str(ITER4))


def log(m):
    print(f"[P3] {m}", flush=True)


def capturar_nube(n_frames: int, zmin: float, zmax: float) -> o3d.geometry.PointCloud:
    """Captura una nube fresca de la Femto (promedio temporal de N frames)."""
    from camera_backend import FemtoBoltBackend

    log(f"Capturando {n_frames} frames de la Femto (escena ESTATICA)...")
    cam = FemtoBoltBackend()
    cam.open()
    K, _ = cam.get_intrinsics()
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]

    acc = cnt = rgb_last = None
    got = att = 0
    while got < n_frames and att < n_frames * 10:
        att += 1
        rgb, depth_mm, _ = cam.read()
        if rgb is None or depth_mm is None:
            continue
        if acc is None:
            H, W = depth_mm.shape[:2]
            acc = np.zeros((H, W), np.float64)
            cnt = np.zeros((H, W), np.int32)
        m = depth_mm > 0
        acc[m] += depth_mm[m]
        cnt[m] += 1
        rgb_last = rgb
        got += 1
        log(f"  frame {got}/{n_frames}")
    cam.close()
    if acc is None:
        log("ERROR: no se capturo depth.")
        sys.exit(1)

    depth_m = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0) / 1000.0
    H, W = depth_m.shape
    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    mask = (depth_m > zmin) & (depth_m < zmax)
    x = (uu - cx) * depth_m / fx
    y = (vv - cy) * depth_m / fy
    xyz = np.stack([x[mask], y[mask], depth_m[mask]], axis=1).astype(np.float64)
    rgb = (rgb_last[..., ::-1][mask].astype(np.float64) / 255.0)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    pcd.colors = o3d.utility.Vector3dVector(rgb)
    return pcd


def cargar_ultima_ply(outdir: Path) -> Path:
    plys = sorted(outdir.glob("nube_*.ply"))
    if not plys:
        log(f"ERROR: no hay nubes en {outdir}. Corre la prueba 1 o usa --capturar.")
        sys.exit(1)
    return plys[-1]


def pick_punto(pcd):
    """Visor para marcar UN punto sobre el hueso con Shift+click. Devuelve indice o None."""
    log("VENTANA DE SELECCION: gira con el mouse, haz SHIFT+CLICK sobre el hueso,")
    log("luego cierra la ventana (tecla Q o la X). Marca solo un punto.")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window(window_name="Shift+click sobre el HUESO, luego Q")
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    picks = vis.get_picked_points()
    return picks[-1] if picks else None


def recorte_z(pcd, zmin, zmax):
    z = np.asarray(pcd.points)[:, 2]
    idx = np.where((z > zmin) & (z < zmax))[0]
    return pcd.select_by_index(idx)


def main():
    ap = argparse.ArgumentParser(description="Prueba 3: aislar el hueso y limpiar.")
    ap.add_argument("--ply", default=None, help="Nube a procesar. Default: la ultima de nubes/.")
    ap.add_argument("--capturar", action="store_true", help="Capturar una nube nueva de la Femto.")
    ap.add_argument("--frames", type=int, default=10, help="Frames a promediar si --capturar.")
    ap.add_argument("--zmin", type=float, default=0.35, help="Profundidad min (m). Default 0.35.")
    ap.add_argument("--zmax", type=float, default=0.75, help="Profundidad max (m). Default 0.75.")
    ap.add_argument("--nb", type=int, default=20, help="Vecinos para outlier removal. Default 20.")
    ap.add_argument("--std", type=float, default=2.0, help="Umbral std outliers. Default 2.0.")
    ap.add_argument("--plano-mm", type=float, default=6.0, help="Grosor del plano mesa (mm). Default 6.")
    ap.add_argument("--frac-plano", type=float, default=0.25,
                    help="Solo quita la mesa si el plano es > esta fraccion. Default 0.25.")
    ap.add_argument("--altura-min-mm", type=float, default=12.0,
                    help="Conserva solo puntos a mas de esta altura sobre la mesa (mm). 0 = off.")
    ap.add_argument("--brillo-min", type=float, default=0.0,
                    help="Quita puntos mas oscuros que este umbral 0..1 (ej 0.30 quita el "
                         "marcador ArUco negro). 0 = off.")
    ap.add_argument("--no-plano", action="store_true", help="No quitar el plano de la mesa.")
    ap.add_argument("--eps-mm", type=float, default=12.0, help="Radio DBSCAN (mm). Default 12.")
    ap.add_argument("--min-pts", type=int, default=30, help="Min puntos por cluster. Default 30.")
    ap.add_argument("--no-cluster", action="store_true", help="No quedarse solo con un cluster.")
    ap.add_argument("--pick", action="store_true",
                    help="Marcar el hueso con Shift+click (si el cluster mayor no es el hueso).")
    ap.add_argument("--ver", action="store_true", help="Visualizar el resultado.")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "nubes"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # --- 1. Cargar / capturar ---
    if args.capturar:
        pcd = capturar_nube(args.frames, args.zmin, args.zmax)
    else:
        ruta = Path(args.ply) if args.ply else cargar_ultima_ply(outdir)
        log(f"Cargando {ruta}")
        pcd = o3d.io.read_point_cloud(str(ruta))
    n0 = len(pcd.points)
    log(f"Nube inicial: {n0:,} puntos")
    if n0 == 0:
        sys.exit(1)

    # --- 2. Recorte por profundidad ---
    pcd = recorte_z(pcd, args.zmin, args.zmax)
    log(f"Tras recorte Z [{args.zmin}-{args.zmax} m]: {len(pcd.points):,} puntos")
    if len(pcd.points) < args.min_pts:
        log("Quedan muy pocos puntos tras el recorte. Ajusta --zmin/--zmax.")
        sys.exit(1)

    # --- 3. Quitar outliers (flying pixels / estelas) ---
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=args.nb, std_ratio=args.std)
    log(f"Tras quitar outliers (nb={args.nb}, std={args.std}): {len(pcd.points):,} puntos")

    # --- 3b. Quitar puntos OSCUROS por color (ej. marcador ArUco negro) ---
    if args.brillo_min > 0 and pcd.has_colors():
        brillo = np.asarray(pcd.colors).mean(axis=1)
        keep = np.where(brillo > args.brillo_min)[0]
        pcd = pcd.select_by_index(keep)
        log(f"Filtro brillo (> {args.brillo_min}): quedan {len(pcd.points):,} (quita lo oscuro)")

    # --- 4. Quitar la mesa (plano dominante via RANSAC) + filtro de altura ---
    if not args.no_plano and len(pcd.points) > 100:
        plane_model, inliers = pcd.segment_plane(
            distance_threshold=args.plano_mm / 1000.0, ransac_n=3, num_iterations=1000)
        frac = len(inliers) / len(pcd.points)
        a, b, c, d = plane_model
        if frac >= args.frac_plano:
            pcd = pcd.select_by_index(inliers, invert=True)
            log(f"Mesa quitada: plano {a:.2f}x+{b:.2f}y+{c:.2f}z+{d:.2f}=0 "
                f"({frac*100:.0f}% de los puntos). Quedan {len(pcd.points):,}")
            # Filtro de ALTURA: conserva solo lo que sobresale del plano > altura_min.
            # Elimina arrugas del mantel que RANSAC no absorbio (mas robusto que solo
            # quitar inliers cuando la tela no es perfectamente plana).
            if args.altura_min_mm > 0 and len(pcd.points) > 0:
                nrm = np.array([a, b, c], dtype=np.float64)
                nn = nrm / np.linalg.norm(nrm)
                dd = d / np.linalg.norm(nrm)
                sd = np.asarray(pcd.points) @ nn + dd
                if np.median(sd) < 0:   # orientar normal hacia el lado del objeto
                    nn, dd, sd = -nn, -dd, -sd
                keep = np.where(sd > args.altura_min_mm / 1000.0)[0]
                pcd = pcd.select_by_index(keep)
                log(f"Filtro altura (> {args.altura_min_mm:.0f} mm sobre la mesa): "
                    f"quedan {len(pcd.points):,}")
        else:
            log(f"Plano dominante solo {frac*100:.0f}% (< {args.frac_plano*100:.0f}%): NO lo quito.")

    # --- 5. Quedarse con UN cluster: el hueso ---
    if not args.no_cluster and len(pcd.points) > args.min_pts:
        labels = np.array(pcd.cluster_dbscan(
            eps=args.eps_mm / 1000.0, min_points=args.min_pts, print_progress=False))
        pts_all = np.asarray(pcd.points)
        n_clusters = labels.max() + 1
        if n_clusters >= 1:
            tam = sorted(((int((labels == k).sum()), k) for k in range(n_clusters)), reverse=True)
            log(f"DBSCAN: {n_clusters} clusters. Los mayores (tamano | Z medio | extension mm):")
            for sz, k in tam[:8]:
                p = pts_all[labels == k]
                ext = (p.max(0) - p.min(0)) * 1000
                log(f"    cluster {k:2d}: {sz:7,d} pts | Z {p[:,2].mean():.3f} m | "
                    f"{ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f}")

            k_sel = None
            if args.pick:
                seed = pick_punto(pcd)
                if seed is not None and labels[seed] >= 0:
                    k_sel = int(labels[seed])
                    log(f"Marcaste el cluster {k_sel}.")
                else:
                    log("No marcaste un punto valido (o caiste en ruido): uso el mayor.")
            if k_sel is None:
                k_sel = tam[0][1]
                log(f"Conservo el cluster MAYOR ({tam[0][0]:,} pts). Si no es el hueso, usa --pick.")

            idx = np.where(labels == k_sel)[0]
            pcd = pcd.select_by_index(idx)
            log(f"Conservo cluster {k_sel}: {len(idx):,} puntos = hueso.")
        else:
            log("DBSCAN no encontro clusters (todo ruido). Revisa --eps-mm / --min-pts.")

    nf = len(pcd.points)
    log(f"=== RESULTADO: {nf:,} puntos ({100.0*nf/max(n0,1):.1f}% del original) ===")
    if nf:
        pts = np.asarray(pcd.points)
        log(f"  Caja del hueso: "
            f"X {pts[:,0].min():.3f}..{pts[:,0].max():.3f}  "
            f"Y {pts[:,1].min():.3f}..{pts[:,1].max():.3f}  "
            f"Z {pts[:,2].min():.3f}..{pts[:,2].max():.3f} m")
        ext = pts.max(axis=0) - pts.min(axis=0)
        log(f"  Tamano aprox: {ext[0]*1000:.0f} x {ext[1]*1000:.0f} x {ext[2]*1000:.0f} mm")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"phantom_{ts}.ply"
    o3d.io.write_point_cloud(str(out), pcd)
    log(f"Guardada: {out}")

    if args.ver:
        log("Abriendo visor (cierra la ventana para terminar)...")
        o3d.visualization.draw_geometries([pcd])


if __name__ == "__main__":
    main()
