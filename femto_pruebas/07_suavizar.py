# -*- coding: utf-8 -*-
"""
PRUEBA 7 - Suavizar y completar la nube fusionada (reconstruccion de superficie).

La fusion multi-vista deja una superficie con ruido y huecos. Para que sea facil
reconocer la anatomia (y marcar puntos) y para un registro mas estable, convertimos
la nube en una MALLA LISA por reconstruccion de Poisson, recortando lo mal soportado,
y la re-muestreamos como nube limpia.

Flujo:
  1. Carga la nube fusionada (.ply).
  2. Quita outliers.
  3. Estima y ORIENTA normales (Poisson lo necesita).
  4. Reconstruccion de Poisson -> malla.
  5. Recorta vertices de baja densidad (zonas inventadas en huecos) y recorta a la
     caja de la nube original (Poisson tiende a inflar los bordes abiertos).
  6. Guarda malla suave (.ply) + nube limpia resampleada (.ply).

Uso:
    python femto_pruebas\07_suavizar.py femto_pruebas\nubes\fusion_XXXX.ply --ver
    python femto_pruebas\07_suavizar.py femto_pruebas\nubes\fusion_XXXX.ply --depth 9 --quantile 0.05 --ver

Salida:
    <entrada>_malla.ply   (malla lisa)
    <entrada>_suave.ply   (nube limpia resampleada, para registrar/pickear)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import open3d as o3d


def log(m):
    print(f"[P7] {m}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Suavizar fusion por reconstruccion de Poisson.")
    ap.add_argument("entrada", help="Nube fusionada .ply")
    ap.add_argument("--depth", type=int, default=9, help="Profundidad de Poisson (8-10). Default 9.")
    ap.add_argument("--quantile", type=float, default=0.04,
                    help="Recorta este percentil de vertices de menor densidad. Default 0.04.")
    ap.add_argument("--n-puntos", type=int, default=40000, help="Puntos de la nube resampleada.")
    ap.add_argument("--normal-k", type=int, default=30, help="Vecinos para orientar normales.")
    ap.add_argument("--ver", action="store_true")
    args = ap.parse_args()

    pcd = o3d.io.read_point_cloud(args.entrada)
    log(f"Nube cargada: {len(pcd.points):,} pts")
    if len(pcd.points) < 100:
        log("Nube demasiado pequena."); return

    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    log(f"Tras outliers: {len(pcd.points):,} pts")

    # Normales orientadas de forma consistente (clave para Poisson)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=args.normal_k))
    pcd.orient_normals_consistent_tangent_plane(args.normal_k)
    log("Normales estimadas y orientadas.")

    # Reconstruccion de Poisson
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=args.depth)
    densities = np.asarray(densities)
    log(f"Malla Poisson: {len(mesh.vertices):,} vertices")

    # Recortar vertices de baja densidad (huecos inventados)
    umbral = np.quantile(densities, args.quantile)
    mesh.remove_vertices_by_mask(densities < umbral)
    # Recortar a la caja de la nube original (Poisson infla los bordes)
    mesh = mesh.crop(pcd.get_axis_aligned_bounding_box())
    mesh.compute_vertex_normals()
    log(f"Tras recorte (densidad < {args.quantile*100:.0f}% + caja): "
        f"{len(mesh.vertices):,} vertices")

    base = Path(args.entrada)
    out_mesh = base.with_name(base.stem + "_malla.ply")
    o3d.io.write_triangle_mesh(str(out_mesh), mesh)
    log(f"Malla guardada: {out_mesh}")

    # Nube limpia resampleada desde la malla
    nube = mesh.sample_points_poisson_disk(number_of_points=args.n_puntos)
    out_pcd = base.with_name(base.stem + "_suave.ply")
    o3d.io.write_point_cloud(str(out_pcd), nube)
    pts = np.asarray(nube.points); ext = (pts.max(0) - pts.min(0)) * 1000
    log(f"Nube suave guardada: {out_pcd} ({len(nube.points):,} pts, "
        f"{ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm)")

    if args.ver:
        mesh.paint_uniform_color([0.7, 0.7, 0.75])
        log("Mostrando malla lisa. Cierra la ventana para terminar.")
        o3d.visualization.draw_geometries([mesh])


if __name__ == "__main__":
    main()
