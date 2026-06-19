# -*- coding: utf-8 -*-
"""
CAMINO B - Registro por SEMILLA (3 puntos) + ICP de superficie.

TU das el empujon inicial marcando 3+ puntos correspondientes; el ICP refina.
NO altera el STL ni sus coordenadas: los puntos solo CALCULAN la transform 4x4.

Mejoras de usabilidad (v2):
  - El STL se muestra como MALLA SOLIDA -> al hacer SHIFT+CLICK siempre cae un
    vertice cercano de la superficie (ya no "captura al fondo").
  - Los puntos de la nube se dibujan grandes para acertar mejor.
  - SHIFT+CLICK DERECHO deshace el ultimo punto. Cierra con Q.
  - La pose inicial se calcula de las coordenadas de los puntos (Kabsch), no por
    indices -> mas robusto.

Flujo:
  1. Carga STL (CT, mm->m) y la nube (prueba 8).
  2. Ventana 1: marca 3-4 puntos reconocibles en la MALLA del STL. Q.
  3. Ventana 2: marca los MISMOS puntos, en el MISMO orden, en la nube. Q.
  4. Pose inicial (Kabsch) -> ICP point-to-plane multiescala.
  5. Reporta fitness/RMSE en zona de solape y guarda la transform 4x4.

Uso:
    python femto_pruebas\06_registro_semilla.py --stl "stl\Segmentation_Bone_CT.stl" \
        --nube femto_pruebas\nubes\tsdf_XXXX.ply --ver

Salida:
    femto_pruebas\transforms\T_semilla_YYYYmmdd_HHMMSS.npy
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import open3d as o3d

REG = o3d.pipelines.registration


def log(m):
    print(f"[B] {m}", flush=True)


def cargar_malla(path_stl, stl_en_mm=True):
    mesh = o3d.io.read_triangle_mesh(str(path_stl))
    if len(mesh.vertices) == 0:
        log(f"ERROR: STL vacio o ilegible: {path_stl}")
        sys.exit(1)
    if stl_en_mm:
        mesh.scale(0.001, center=(0, 0, 0))
    mesh.compute_vertex_normals()
    return mesh


def pick_xyz(geom, titulo, point_size=1.0):
    """Visor para marcar puntos con Shift+click. Devuelve coords (N,3) en metros."""
    log(f"VENTANA: {titulo}")
    log("  SHIFT+CLICK marca | SHIFT+CLICK DERECHO deshace el ultimo | Q cierra")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window(window_name=titulo)
    vis.add_geometry(geom)
    try:
        vis.get_render_option().point_size = point_size
    except Exception:
        pass
    vis.run()
    vis.destroy_window()
    idx = vis.get_picked_points()
    pts = np.asarray(geom.vertices) if hasattr(geom, "vertices") else np.asarray(geom.points)
    return pts[idx] if len(idx) else np.zeros((0, 3))


def kabsch(P, Q):
    """Transform rigida 4x4 que lleva P -> Q (ambos Nx3, mismo orden)."""
    Pc, Qc = P.mean(0), Q.mean(0)
    H = (P - Pc).T @ (Q - Qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = Qc - R @ Pc
    return T


def refine_icp_multiescala(src, tgt, init, voxel):
    T = init
    for escala, it in [(3.0, 80), (1.5, 80), (0.6, 60)]:
        dist = voxel * escala
        r = REG.registration_icp(
            src, tgt, dist, T, REG.TransformationEstimationPointToPlane(),
            REG.ICPConvergenceCriteria(max_iteration=it))
        T = r.transformation
        log(f"  ICP x{escala:.1f} (dist {dist*1000:.1f} mm): "
            f"fitness={r.fitness:.3f}  rmse={r.inlier_rmse*1000:.2f} mm")
    return T


def ver_overlay(src, tgt, T):
    s = o3d.geometry.PointCloud(src); s.paint_uniform_color([1.0, 0.6, 0.0]); s.transform(T)
    t = o3d.geometry.PointCloud(tgt); t.paint_uniform_color([0.0, 0.5, 1.0])
    log("Naranja = STL registrado, Azul = nube. Cierra la ventana para terminar.")
    o3d.visualization.draw_geometries([s, t])


def main():
    ap = argparse.ArgumentParser(description="Camino B: registro por semilla de 3 puntos + ICP.")
    ap.add_argument("--stl", required=True, help="STL del CT (mm).")
    ap.add_argument("--nube", required=True, help="Nube fusionada/aislada (.ply).")
    ap.add_argument("--n-puntos", type=int, default=20000, help="Puntos a muestrear del STL para ICP.")
    ap.add_argument("--voxel-mm", type=float, default=2.0, help="Voxel para el ICP (mm).")
    ap.add_argument("--point-size", type=float, default=6.0, help="Tamano de punto de la nube al picar.")
    ap.add_argument("--stl-metros", action="store_true", help="El STL ya esta en metros.")
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "transforms"))
    args = ap.parse_args()

    voxel = args.voxel_mm / 1000.0
    mesh = cargar_malla(args.stl, stl_en_mm=not args.stl_metros)
    source = mesh.sample_points_poisson_disk(number_of_points=args.n_puntos)  # para ICP
    # Nube DENSA del STL para picar (el visor de Open3D solo pica point clouds, NO mallas)
    stl_pick = o3d.geometry.PointCloud()
    stl_pick.points = mesh.vertices
    stl_pick = stl_pick.voxel_down_sample(0.0015)
    target = o3d.io.read_point_cloud(args.nube)
    if len(target.points) == 0:
        log("ERROR: nube vacia."); sys.exit(1)
    log(f"STL malla: {len(mesh.vertices):,} verts | nube: {len(target.points):,} pts")

    # --- Semilla: marcar correspondencias (STL en MALLA solida) ---
    log("Paso 1/2: marca 3-4 puntos reconocibles en el STL (nube densa).")
    src_pts = pick_xyz(stl_pick, "STL - marca 3+ puntos (shift+click), luego Q",
                       point_size=args.point_size)
    log("Paso 2/2: marca los MISMOS puntos, en el MISMO orden, en la nube.")
    tgt_pts = pick_xyz(target, "NUBE - marca los MISMOS puntos en el mismo orden, luego Q",
                       point_size=args.point_size)

    n = min(len(src_pts), len(tgt_pts))
    if n < 3:
        log(f"Necesitas >=3 puntos en cada uno (marcaste {len(src_pts)} y {len(tgt_pts)}).")
        sys.exit(1)
    if len(src_pts) != len(tgt_pts):
        log(f"AVISO: distinto numero ({len(src_pts)} vs {len(tgt_pts)}); uso los primeros {n}.")
    T_init = kabsch(src_pts[:n], tgt_pts[:n])
    log(f"Pose inicial por {n} correspondencias (Kabsch) calculada.")

    # --- Refinamiento ICP point-to-plane ---
    src_d = source.voxel_down_sample(voxel)
    tgt_d = target.voxel_down_sample(voxel)
    src_d.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2, max_nn=30))
    tgt_d.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2, max_nn=30))
    log("Refinamiento ICP point-to-plane (multiescala)...")
    T = refine_icp_multiescala(src_d, tgt_d, T_init, voxel)

    # --- Metrica honesta sobre la zona visible ---
    src_mov = o3d.geometry.PointCloud(src_d); src_mov.transform(T)
    dists = np.asarray(src_mov.compute_point_cloud_distance(tgt_d))
    idx_vis = np.where(dists < voxel * 2.0)[0]
    frac = len(idx_vis) / max(len(src_d.points), 1)
    if len(idx_vis) > 50:
        ev = REG.evaluate_registration(src_d.select_by_index(idx_vis), tgt_d, voxel * 1.5, T)
        log(f"Solape visible: {frac*100:.0f}% del STL. fitness={ev.fitness:.3f}  "
            f"rmse={ev.inlier_rmse*1000:.2f} mm")

    log("=== TRANSFORMACION STL -> NUBE (4x4, metros) ===")
    for fila in T:
        log("  [" + "  ".join(f"{v: .5f}" for v in fila) + "]")

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"T_semilla_{ts}.npy"
    np.save(out, T)
    log(f"Guardada: {out}")
    if args.ver:
        ver_overlay(src_d, tgt_d, T)


if __name__ == "__main__":
    main()
