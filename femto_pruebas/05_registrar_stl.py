# -*- coding: utf-8 -*-
"""
PRUEBA 5 - Registro de superficie: alinear el STL (del CT) sobre la nube de la Femto.

Es el corazon del nuevo metodo: en lugar de tocar puntos a mano, alineamos
automaticamente el STL contra la nube de puntos del objeto real.

Pipeline coarse-to-fine (lo recomendado por la investigacion):
  1. STL -> nube de puntos (muestreo). OJO: el STL del CT esta en MILIMETROS; la
     nube de la Femto esta en METROS. Convertimos el STL a metros (x0.001).
  2. Preprocesar ambos: voxel downsample + normales + descriptores FPFH.
  3. Alineacion GLOBAL gruesa: RANSAC sobre features FPFH (sin pose inicial).
  4. Refinamiento FINO: ICP point-to-plane.
  5. Resultado: matriz 4x4 que lleva el STL sobre la nube + fitness + RMSE.

MODO AUTOTEST (--autotest): valida el pipeline SIN camara ni objeto real.
  Toma el STL, le aplica una transformacion y ruido CONOCIDOS, simula una vista
  parcial (como la camara cenital que solo ve la cara de arriba), y comprueba que
  el registro recupera esa transformacion. Reporta error de rotacion (grados) y
  traslacion (mm). Si esos errores son chicos, el algoritmo es correcto.

Uso:
    # Validar el algoritmo (sin hardware), con un STL del repo:
    python femto_pruebas\05_registrar_stl.py --autotest --stl "stl\Segmentation_Bone_CT.stl"
    # Sin STL usa una figura sintetica asimetrica:
    python femto_pruebas\05_registrar_stl.py --autotest
    # Registro REAL: STL contra una nube ya aislada (prueba 3):
    python femto_pruebas\05_registrar_stl.py --stl "stl\Segmentation_Bone_CT.stl" --nube femto_pruebas\nubes\phantom_XXXX.ply --ver

Salida (registro real):
    femto_pruebas\transforms\T_stl_a_nube_YYYYmmdd_HHMMSS.npy
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

REG = o3d.pipelines.registration


def log(m):
    print(f"[P5] {m}", flush=True)


# ---------------------------------------------------------------------------
# Bloques del pipeline
# ---------------------------------------------------------------------------

def preprocess(pcd, voxel):
    """Downsample + normales + FPFH. Devuelve (nube_down, fpfh)."""
    down = pcd.voxel_down_sample(voxel)
    down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2.0, max_nn=30))
    fpfh = REG.compute_fpfh_feature(
        down, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5.0, max_nn=100))
    return down, fpfh


def global_ransac(src_d, tgt_d, src_f, tgt_f, voxel):
    """Alineacion global gruesa con RANSAC sobre FPFH (sin pose inicial)."""
    dist = voxel * 1.5
    return REG.registration_ransac_based_on_feature_matching(
        src_d, tgt_d, src_f, tgt_f, True, dist,
        REG.TransformationEstimationPointToPoint(False), 3,
        [REG.CorrespondenceCheckerBasedOnEdgeLength(0.9),
         REG.CorrespondenceCheckerBasedOnDistance(dist)],
        REG.RANSACConvergenceCriteria(100000, 0.999))


def refine_icp_multiescala(src, tgt, voxel, init):
    """ICP point-to-plane multiescala: afloja el umbral y lo aprieta por pasos.
    Mas robusto al ruido que un solo ICP estricto. Requiere normales en ambos."""
    T = init
    for escala, max_it in [(1.5, 100), (0.8, 100), (0.4, 60)]:
        dist = voxel * escala
        ri = REG.registration_icp(
            src, tgt, dist, T, REG.TransformationEstimationPointToPlane(),
            REG.ICPConvergenceCriteria(max_iteration=max_it))
        T = ri.transformation
        log(f"  ICP x{escala:.1f} (dist {dist*1000:.1f} mm): "
            f"fitness={ri.fitness:.3f}  rmse={ri.inlier_rmse*1000:.2f} mm")
    return T


def registrar(src_pcd, tgt_pcd, voxel, n_global=8):
    """Pipeline completo. Devuelve (T 4x4, fitness, rmse) evaluados a umbral fijo."""
    src_d, src_f = preprocess(src_pcd, voxel)
    tgt_d, tgt_f = preprocess(tgt_pcd, voxel)
    log(f"Downsample (voxel {voxel*1000:.1f} mm): STL {len(src_d.points):,} pts, "
        f"nube {len(tgt_d.points):,} pts")

    # Global ROBUSTO: RANSAC es estocastico y con nube parcial (una sola cara) una
    # corrida es inestable. Hacemos n_global corridas + FGR y nos quedamos con la
    # de mejor fitness tras un ICP corto. Esto evita caer en poses mediocres.
    log(f"Alineacion global: {n_global} corridas RANSAC + FGR, eligiendo la mejor...")
    candidatos = []
    for _ in range(n_global):
        r = global_ransac(src_d, tgt_d, src_f, tgt_f, voxel)
        candidatos.append(("RANSAC", r.transformation))
    try:
        fgr = REG.registration_fgr_based_on_feature_matching(
            src_d, tgt_d, src_f, tgt_f,
            REG.FastGlobalRegistrationOption(maximum_correspondence_distance=voxel * 1.5))
        candidatos.append(("FGR", fgr.transformation))
    except Exception as exc:
        log(f"  (FGR no disponible: {exc})")
    mejor = None
    for nombre, T0 in candidatos:
        ri = REG.registration_icp(
            src_d, tgt_d, voxel * 1.5, T0,
            REG.TransformationEstimationPointToPlane(),
            REG.ICPConvergenceCriteria(max_iteration=30))
        ev = REG.evaluate_registration(src_d, tgt_d, voxel * 1.5, ri.transformation)
        if mejor is None or ev.fitness > mejor[0]:
            mejor = (ev.fitness, ri.transformation, nombre)
    log(f"  mejor global: {mejor[2]} (fitness sobre STL completo={mejor[0]:.3f})")

    log("Refinamiento ICP point-to-plane (multiescala)...")
    T = refine_icp_multiescala(src_d, tgt_d, voxel, mejor[1])

    # Recorte al SOLAPE visible: el STL es 360 grados pero la nube es una sola
    # cara. Nos quedamos con la parte del STL cercana a la nube y afinamos/medimos
    # SOLO ahi -> fitness honesto (sobre la cara vista) y RMSE = error real.
    src_mov = o3d.geometry.PointCloud(src_d)
    src_mov.transform(T)
    dists = np.asarray(src_mov.compute_point_cloud_distance(tgt_d))
    idx_vis = np.where(dists < voxel * 2.0)[0]
    frac_vis = len(idx_vis) / max(len(src_d.points), 1)
    if len(idx_vis) > 50:
        src_vis = src_d.select_by_index(idx_vis)
        rf = REG.registration_icp(
            src_vis, tgt_d, voxel * 1.0, T,
            REG.TransformationEstimationPointToPlane(),
            REG.ICPConvergenceCriteria(max_iteration=60))
        T = rf.transformation
        ev = REG.evaluate_registration(src_vis, tgt_d, voxel * 1.5, T)
        log(f"Solape visible: {frac_vis*100:.0f}% del STL toca la nube. "
            f"Afinado en zona visible: fitness={ev.fitness:.3f}  "
            f"rmse={ev.inlier_rmse*1000:.2f} mm")
        return T, ev.fitness, ev.inlier_rmse
    ev = REG.evaluate_registration(src_d, tgt_d, voxel * 1.5, T)
    return T, ev.fitness, ev.inlier_rmse


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def stl_a_nube(path_stl, n_puntos, stl_en_mm=True):
    mesh = o3d.io.read_triangle_mesh(str(path_stl))
    if len(mesh.vertices) == 0:
        log(f"ERROR: STL vacio o ilegible: {path_stl}")
        sys.exit(1)
    if stl_en_mm:
        mesh.scale(0.001, center=(0, 0, 0))  # mm -> m
    mesh.compute_vertex_normals()
    pcd = mesh.sample_points_poisson_disk(number_of_points=n_puntos)
    return pcd


def figura_sintetica(n_puntos):
    """Figura asimetrica (caja + esfera + cilindro) en metros, para autotest sin STL."""
    box = o3d.geometry.TriangleMesh.create_box(0.08, 0.05, 0.03)
    sph = o3d.geometry.TriangleMesh.create_sphere(0.02).translate((0.09, 0.025, 0.015))
    cyl = o3d.geometry.TriangleMesh.create_cylinder(0.008, 0.06).translate((0.02, 0.07, 0.015))
    mesh = box + sph + cyl
    mesh.compute_vertex_normals()
    return mesh.sample_points_poisson_disk(number_of_points=n_puntos)


def transform_aleatoria(max_giro_deg=35.0, max_trasl_m=0.05, seed=0):
    rng = np.random.default_rng(seed)
    eje = rng.normal(size=3); eje /= np.linalg.norm(eje)
    ang = np.radians(rng.uniform(15, max_giro_deg))
    R = Rotation.from_rotvec(eje * ang).as_matrix()
    t = rng.uniform(-max_trasl_m, max_trasl_m, size=3)
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = t
    return T


def vista_parcial(pcd, fraccion=0.6):
    """Simula vista cenital: conserva los puntos mas cercanos a la camara (menor Z)."""
    z = np.asarray(pcd.points)[:, 2]
    umbral = np.quantile(z, fraccion)
    idx = np.where(z <= umbral)[0]
    return pcd.select_by_index(idx)


def errores(T_est, T_known):
    dT = np.linalg.inv(T_known) @ T_est
    R = dT[:3, :3]
    ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)))
    trasl_mm = np.linalg.norm(dT[:3, 3]) * 1000.0
    return ang, trasl_mm


def ver_overlay(src_pcd, tgt_pcd, T):
    s = o3d.geometry.PointCloud(src_pcd); s.paint_uniform_color([1.0, 0.6, 0.0]); s.transform(T)
    t = o3d.geometry.PointCloud(tgt_pcd); t.paint_uniform_color([0.0, 0.5, 1.0])
    log("Naranja = STL registrado, Azul = nube real. Cierra la ventana para terminar.")
    o3d.visualization.draw_geometries([s, t])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Prueba 5: registro STL <-> nube de superficie.")
    ap.add_argument("--stl", default=None, help="Ruta al STL (del CT, en mm).")
    ap.add_argument("--nube", default=None, help="Nube real aislada (.ply de prueba 3).")
    ap.add_argument("--autotest", action="store_true", help="Validar el pipeline sin hardware.")
    ap.add_argument("--voxel-mm", type=float, default=4.0, help="Tamano de voxel (mm). Default 4.")
    ap.add_argument("--n-puntos", type=int, default=8000, help="Puntos a muestrear del STL.")
    ap.add_argument("--ruido-mm", type=float, default=1.5, help="Ruido gaussiano en autotest (mm).")
    ap.add_argument("--n-global", type=int, default=8, help="Corridas de RANSAC global (best-of-N).")
    ap.add_argument("--parcial", type=float, default=0.6,
                    help="Fraccion conservada como vista parcial en autotest. 1.0 = completa.")
    ap.add_argument("--stl-metros", action="store_true", help="El STL ya esta en metros (no escalar).")
    ap.add_argument("--ver", action="store_true", help="Visualizar el overlay final.")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "transforms"))
    args = ap.parse_args()

    voxel = args.voxel_mm / 1000.0

    # ---------------- AUTOTEST ----------------
    if args.autotest:
        if args.stl:
            log(f"Autotest con STL: {args.stl}")
            base = stl_a_nube(args.stl, args.n_puntos, stl_en_mm=not args.stl_metros)
        else:
            log("Autotest con figura sintetica asimetrica (sin STL).")
            base = figura_sintetica(args.n_puntos)
        ext = (np.asarray(base.points).max(0) - np.asarray(base.points).min(0)) * 1000
        log(f"Objeto: {len(base.points):,} pts, tamano {ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm")

        T_known = transform_aleatoria(seed=1)
        target = o3d.geometry.PointCloud(base)
        target.transform(T_known)
        # ruido gaussiano realista de la Femto
        pts = np.asarray(target.points)
        pts += np.random.default_rng(2).normal(0, args.ruido_mm / 1000.0, pts.shape)
        target.points = o3d.utility.Vector3dVector(pts)
        # vista parcial (cenital ve solo una cara)
        if args.parcial < 1.0:
            target = vista_parcial(target, args.parcial)
        log(f"Target simulado: {len(target.points):,} pts "
            f"(ruido {args.ruido_mm} mm, parcial {args.parcial*100:.0f}%)")

        source = o3d.geometry.PointCloud(base)
        T_est, fit, rmse = registrar(source, target, voxel, args.n_global)
        ang, trasl = errores(T_est, T_known)
        log("=== RESULTADO AUTOTEST ===")
        log(f"  Error de rotacion:   {ang:.2f} grados")
        log(f"  Error de traslacion: {trasl:.2f} mm")
        log(f"  fitness final: {fit:.3f}  | inlier RMSE: {rmse*1000:.2f} mm")
        ok = ang < 3.0 and trasl < 3.0
        log(f"  {'OK: el pipeline recupera la pose.' if ok else 'ATENCION: error alto, revisar voxel/parcialidad.'}")
        if args.ver:
            ver_overlay(source, target, T_est)
        return

    # ---------------- REGISTRO REAL ----------------
    if not args.stl or not args.nube:
        log("Para registro real necesitas --stl y --nube. (O usa --autotest para validar.)")
        sys.exit(1)

    log(f"STL:  {args.stl}")
    log(f"Nube: {args.nube}")
    source = stl_a_nube(args.stl, args.n_puntos, stl_en_mm=not args.stl_metros)
    target = o3d.io.read_point_cloud(args.nube)
    target.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2.0, max_nn=30))
    if len(target.points) == 0:
        log("ERROR: nube vacia."); sys.exit(1)

    T_est, fit, rmse = registrar(source, target, voxel, args.n_global)
    log("=== TRANSFORMACION STL -> NUBE (4x4, metros) ===")
    for fila in T_est:
        log("  [" + "  ".join(f"{v: .5f}" for v in fila) + "]")
    log(f"  fitness {fit:.3f}  | inlier RMSE {rmse*1000:.2f} mm")
    if fit < 0.3:
        log("  AVISO: fitness bajo: la alineacion puede no ser fiable "
            "(nube muy parcial, voxel mal, o poca superposicion).")

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"T_stl_a_nube_{ts}.npy"
    np.save(out, T_est)
    log(f"Guardada: {out}")
    if args.ver:
        ver_overlay(source, target, T_est)


if __name__ == "__main__":
    main()
