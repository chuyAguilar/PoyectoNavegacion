# -*- coding: utf-8 -*-
"""
PRUEBA 2 - Captura multi-vista del hueso fusionada por el MARCADOR de referencia.

Idea (opcion 2): el STL es 360 grados pero una sola foto ve una cara, lo que deja
poco solape y el registro queda ambiguo. Solucion: capturar el hueso desde varios
angulos y FUSIONAR las nubes para reconstruir la cara superior completa.

Para fusionarlas sin que se desalineen usamos el MARCADOR 0 (pegado al hueso):
su pose en cada toma dice como giro el hueso. Transformando cada nube al FRAME DEL
MARCADOR, todas caen alineadas solas. (Esto es lo mismo que necesitamos para Slicer.)

Por vista:
  1. Promedia N frames (escena estatica) -> depth + RGB.
  2. Detecta el marcador 0 en RGB -> pose (R, t) por IPPE_SQUARE, en METROS.
  3. Construye la nube en el frame de la camara.
  4. La limpia (recorte Z, outliers, quita mesa, filtro altura, quita el marcador
     negro por brillo, se queda con el cluster mayor = hueso).
  5. Transforma el hueso al frame del marcador:  Xm = (Xc - t) @ R.
  6. Acumula.

Al final: fusiona, hace voxel downsample y guarda la nube en el frame del marcador.
Esa nube va directo a la prueba 5 (registro contra el STL).

Controles (ventana de preview):
  ESPACIO = capturar una vista     Q o ESC = terminar y fusionar

REGLAS: fuera de caja de luz, escena estatica por vista, marcador 0 SIEMPRE visible
y bien detectado (se dibuja en verde). Gira el hueso entre vistas (4-8 vistas).

Uso (desde la carpeta del repo):
    python femto_pruebas\02_captura_multivista.py --ver
    python femto_pruebas\02_captura_multivista.py --frames 20 --brillo-min 0.30 --ver

Salida:
    femto_pruebas\nubes\fusion_YYYYmmdd_HHMMSS.ply   (en el frame del marcador)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d

REPO = Path(__file__).resolve().parents[1]
ITER4 = REPO / "codigo" / "iter4"
sys.path.insert(0, str(ITER4))
from camera_backend import FemtoBoltBackend          # noqa: E402
from captura_calibracion import cargar_config, crear_detector  # noqa: E402


def log(m):
    print(f"[P2] {m}", flush=True)


def pose_marker(corners, K, dist, marker_m):
    """Pose del marcador por IPPE_SQUARE. Devuelve (R 3x3, t 3) en metros, o None."""
    h = marker_m / 2.0
    objp = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]], dtype=np.float64)
    imgp = corners.astype(np.float64).reshape(4, 1, 2)
    try:
        n, rvecs, tvecs, errs = cv2.solvePnPGeneric(
            objp, imgp, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    except cv2.error:
        return None
    cand = [(j, float(errs[j][0]) if errs is not None else 0.0)
            for j in range(n) if float(tvecs[j][2, 0]) > 0]
    if not cand:
        return None
    j = min(cand, key=lambda c: c[1])[0]
    R, _ = cv2.Rodrigues(rvecs[j])
    return R, tvecs[j].reshape(3)


def nube_desde_depth(depth_m, rgb_bgr, K, zmin, zmax):
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    H, W = depth_m.shape
    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    mask = (depth_m > zmin) & (depth_m < zmax)
    x = (uu - cx) * depth_m / fx
    y = (vv - cy) * depth_m / fy
    xyz = np.stack([x[mask], y[mask], depth_m[mask]], axis=1).astype(np.float64)
    rgb = (rgb_bgr[..., ::-1][mask].astype(np.float64) / 255.0)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    pcd.colors = o3d.utility.Vector3dVector(rgb)
    return pcd


def limpiar_hueso(pcd, zmin, zmax, brillo_min, plano_mm=6.0, altura_min_mm=12.0,
                  eps_mm=12.0, min_pts=30):
    """Aisla el hueso de una vista (en frame de camara). Devuelve PointCloud o None."""
    z = np.asarray(pcd.points)[:, 2]
    pcd = pcd.select_by_index(np.where((z > zmin) & (z < zmax))[0])
    if len(pcd.points) < min_pts:
        return None
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    # quitar el marcador negro por color
    if brillo_min > 0 and pcd.has_colors():
        b = np.asarray(pcd.colors).mean(axis=1)
        pcd = pcd.select_by_index(np.where(b > brillo_min)[0])
    if len(pcd.points) < 100:
        return None
    # quitar la mesa (plano) + filtro de altura
    plane, inliers = pcd.segment_plane(plano_mm / 1000.0, 3, 1000)
    if len(inliers) / len(pcd.points) >= 0.25:
        pcd = pcd.select_by_index(inliers, invert=True)
        a, b, c, d = plane
        nn = np.array([a, b, c]) / np.linalg.norm([a, b, c])
        dd = d / np.linalg.norm([a, b, c])
        sd = np.asarray(pcd.points) @ nn + dd
        if np.median(sd) < 0:
            sd = -sd
        pcd = pcd.select_by_index(np.where(sd > altura_min_mm / 1000.0)[0])
    if len(pcd.points) < min_pts:
        return None
    # cluster mayor = hueso
    labels = np.array(pcd.cluster_dbscan(eps_mm / 1000.0, min_pts, print_progress=False))
    if labels.max() < 0:
        return None
    k = max(range(labels.max() + 1), key=lambda i: int((labels == i).sum()))
    return pcd.select_by_index(np.where(labels == k)[0])


def limpiar_fusion(pcd, eps_mm=10.0, min_pts=40):
    """Quita las vistas dispersas (poses de marcador malas) y deja el hueso:
    outlier removal + se queda con el cluster DBSCAN mas grande (el nucleo denso
    donde coincidieron las vistas buenas)."""
    if len(pcd.points) < min_pts:
        return pcd
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    labels = np.array(pcd.cluster_dbscan(eps_mm / 1000.0, min_pts, print_progress=False))
    if labels.max() < 0:
        return pcd
    tam = [(int((labels == k).sum()), k) for k in range(labels.max() + 1)]
    tam.sort(reverse=True)
    log(f"Fusion: {len(tam)} clusters, tamanos {[t[0] for t in tam[:5]]}")
    k = tam[0][1]
    return pcd.select_by_index(np.where(labels == k)[0])


def icp_merge(modelo, vista, icp_voxel=0.004):
    """Refina la vista (ya colocada gruesa por el marcador) contra el modelo
    acumulado con ICP point-to-plane y la une. Esto 'cuaja' la superficie y
    corrige el error de la pose del marcador -> nube nitida en vez de borrosa."""
    reg = o3d.pipelines.registration
    modelo.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=icp_voxel * 2, max_nn=30))
    vista.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=icp_voxel * 2, max_nn=30))
    r = reg.registration_icp(
        vista, modelo, icp_voxel * 4, np.eye(4),
        reg.TransformationEstimationPointToPlane(),
        reg.ICPConvergenceCriteria(max_iteration=60))
    vista.transform(r.transformation)
    modelo += vista
    return modelo, r.fitness, r.inlier_rmse


def main():
    ap = argparse.ArgumentParser(description="Prueba 2: captura multi-vista fusionada por marcador.")
    ap.add_argument("--config", default="codigo/iter4/tracker_config.yaml")
    ap.add_argument("--marker-id", type=int, default=0, help="ID del marcador de referencia.")
    ap.add_argument("--marker-mm", type=float, default=80.0, help="Tamano del marcador (mm).")
    ap.add_argument("--frames", type=int, default=50, help="Frames a promediar por vista.")
    ap.add_argument("--zmin", type=float, default=0.35)
    ap.add_argument("--zmax", type=float, default=0.75)
    ap.add_argument("--brillo-min", type=float, default=0.30,
                    help="Quita el marcador negro por color (0..1). 0 = no quitar.")
    ap.add_argument("--voxel-mm", type=float, default=2.0, help="Voxel de la nube fusionada (mm).")
    ap.add_argument("--dist-min", type=float, default=0.45, help="Marcador: distancia min valida (m).")
    ap.add_argument("--dist-max", type=float, default=0.70, help="Marcador: distancia max valida (m).")
    ap.add_argument("--solo-limpiar", default=None, help="Limpiar un fusion_*.ply ya guardado (sin capturar).")
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "nubes"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    marker_m = args.marker_mm / 1000.0

    if args.solo_limpiar:
        f = o3d.io.read_point_cloud(args.solo_limpiar)
        log(f"Limpiando fusion existente: {len(f.points):,} pts")
        f = limpiar_fusion(f)
        pts = np.asarray(f.points); ext = (pts.max(0) - pts.min(0)) * 1000
        log(f"Tras limpiar: {len(f.points):,} pts. Tamano {ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm")
        out = Path(args.solo_limpiar).with_name(Path(args.solo_limpiar).stem + "_limpia.ply")
        o3d.io.write_point_cloud(str(out), f)
        log(f"Guardada: {out}")
        if args.ver:
            o3d.visualization.draw_geometries([f])
        return

    cfg = cargar_config(str(REPO / args.config))
    detector, _, _, _ = crear_detector(cfg["markers"])

    log("Controles:  ESPACIO = capturar vista   |   Q / ESC = terminar y fusionar")
    log("Marcador 0 debe verse VERDE (detectado). Gira el hueso entre vistas.")

    cam = FemtoBoltBackend()
    cam.open()
    K, dist = cam.get_intrinsics()

    modelo = None   # nube acumulada y refinada (frame del marcador)
    n_vistas = 0
    win = "Multivista - ESPACIO captura, Q termina"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while True:
        rgb, depth_mm, _ = cam.read()
        if rgb is None:
            continue
        prev = rgb.copy()
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        corners_all, ids_all, _ = detector.detectMarkers(gray)
        ref_corners = None
        if ids_all is not None:
            for i, mid in enumerate(ids_all.flatten()):
                if int(mid) == args.marker_id:
                    ref_corners = corners_all[i].reshape(4, 2)
                    cv2.polylines(prev, [ref_corners.astype(int).reshape(-1, 1, 2)],
                                  True, (0, 255, 0), 3)
        estado = "MARCADOR OK" if ref_corners is not None else "SIN MARCADOR"
        color = (0, 200, 0) if ref_corners is not None else (0, 0, 255)
        cv2.putText(prev, f"{estado} | vistas: {n_vistas} | ESPACIO captura, Q termina",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        cv2.imshow(win, prev)
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):
            break
        if key == ord(' '):
            if ref_corners is None:
                log("No hay marcador visible: no capturo esta vista.")
                continue
            # promediar N frames de depth (escena estatica)
            acc = np.zeros_like(depth_mm, dtype=np.float64)
            cnt = np.zeros_like(depth_mm, dtype=np.int32)
            rgb_v = rgb
            for _ in range(args.frames):
                r2, d2, _ = cam.read()
                if d2 is None:
                    continue
                m = d2 > 0
                acc[m] += d2[m]
                cnt[m] += 1
                rgb_v = r2
            depth_avg = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0) / 1000.0
            # re-detectar marcador en el frame promediado-rgb
            g2 = cv2.cvtColor(rgb_v, cv2.COLOR_BGR2GRAY)
            ca, ia, _ = detector.detectMarkers(g2)
            rc = None
            if ia is not None:
                for i, mid in enumerate(ia.flatten()):
                    if int(mid) == args.marker_id:
                        rc = ca[i].reshape(4, 2)
            if rc is None:
                log("Perdi el marcador al promediar: vista descartada.")
                continue
            pose = pose_marker(rc, K, dist, marker_m)
            if pose is None:
                log("No pude estimar la pose del marcador: vista descartada.")
                continue
            R, t = pose
            dist = float(np.linalg.norm(t))
            if not (args.dist_min <= dist <= args.dist_max):
                log(f"Marcador a {dist*100:.1f} cm (fuera de {args.dist_min*100:.0f}-"
                    f"{args.dist_max*100:.0f} cm): pose poco fiable, vista descartada.")
                continue
            nube_cam = nube_desde_depth(depth_avg, rgb_v, K, args.zmin, args.zmax)
            hueso = limpiar_hueso(nube_cam, args.zmin, args.zmax, args.brillo_min)
            if hueso is None or len(hueso.points) < 100:
                log("No pude aislar el hueso en esta vista: descartada.")
                continue
            # transformar al frame del marcador: Xm = (Xc - t) @ R
            P = np.asarray(hueso.points)
            Pm = (P - t) @ R
            hueso.points = o3d.utility.Vector3dVector(Pm)
            n_vistas += 1
            if modelo is None:
                modelo = hueso
                log(f"Vista {n_vistas} (referencia): {len(hueso.points):,} pts "
                    f"(marcador a {np.linalg.norm(t)*100:.1f} cm).")
            else:
                modelo, fit, rmse = icp_merge(modelo, hueso)
                log(f"Vista {n_vistas} fusionada por ICP: fit={fit:.2f} "
                    f"rmse={rmse*1000:.2f} mm -> modelo {len(modelo.points):,} pts.")

    cam.close()
    cv2.destroyAllWindows()

    if modelo is None:
        log("No capturaste ninguna vista. Nada que fusionar.")
        sys.exit(1)

    fusion = modelo
    log(f"Fusion cruda (ICP incremental): {len(fusion.points):,} pts de {n_vistas} vistas.")
    fusion = fusion.voxel_down_sample(args.voxel_mm / 1000.0)
    log(f"Tras voxel {args.voxel_mm} mm: {len(fusion.points):,} pts.")
    fusion = limpiar_fusion(fusion)
    log(f"Tras limpiar vistas dispersas: {len(fusion.points):,} pts.")
    pts = np.asarray(fusion.points)
    ext = (pts.max(0) - pts.min(0)) * 1000
    log(f"Tamano fusion: {ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} mm")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"fusion_{ts}.ply"
    o3d.io.write_point_cloud(str(out), fusion)
    log(f"Guardada (frame del marcador): {out}")
    log("Registra con:  python femto_pruebas\\05_registrar_stl.py --stl "
        '"stl\\Segmentation_Bone_CT.stl" --nube ' + str(out).replace(str(REPO) + "\\", "") + " --voxel-mm 3 --ver")

    if args.ver:
        o3d.visualization.draw_geometries([fusion])


if __name__ == "__main__":
    main()
