# -*- coding: utf-8 -*-
"""
PRUEBA 8 - Fusion multi-vista por VOLUMEN TSDF (estilo KinectFusion).

Mejor que apilar nubes (prueba 2): integra las imagenes de profundidad de cada
vista en un volumen TSDF, que promedia en el dominio del volumen -> superficie
suave y denoisada, sin el efecto "doble/borroso" de apilar nubes mal alineadas.

Bonus: como el hueso esta FIJO al marcador (frame del volumen) pero la mesa se
mueve respecto al marcador entre vistas, la mesa NO forma superficie consistente
y se cancela sola; el hueso se integra nitido.

Por vista:
  1. Promedia N frames -> depth (m) + RGB.
  2. Detecta marcador 0 -> pose (R,t) en metros = extrinseca (marcador->camara).
  3. Enmascara (pone a 0) los pixeles del marcador en el depth (para que el
     marcador no se integre como superficie).
  4. Integra la RGBD en el volumen TSDF con esa extrinseca.

Al final: extrae nube + malla, limpia (outliers + cluster mayor = hueso), guarda.

Controles:  ESPACIO captura vista | Q/ESC termina e integra.
REGLAS: fuera de caja de luz, escena estatica por vista, marcador 0 visible,
giros PEQUENOS entre vistas, camara caliente (30-40 min) para minimo ruido.

Uso:
    python femto_pruebas\08_fusion_tsdf.py --ver
    python femto_pruebas\08_fusion_tsdf.py --voxel-mm 1.5 --frames 50 --ver

Salida:
    femto_pruebas\nubes\tsdf_YYYYmmdd_HHMMSS.ply       (nube)
    femto_pruebas\nubes\tsdf_YYYYmmdd_HHMMSS_malla.ply (malla)
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
    print(f"[P8] {m}", flush=True)


def pose_marker(corners, K, dist, marker_m):
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


def mask_marker(depth_m, corners, escala=1.8):
    """Pone a 0 el depth dentro del marcador (dilatado) para no integrarlo."""
    c = corners.mean(axis=0)
    exp = ((corners - c) * escala + c).astype(np.int32)
    mask = np.zeros(depth_m.shape, np.uint8)
    cv2.fillConvexPoly(mask, exp, 1)
    out = depth_m.copy()
    out[mask > 0] = 0.0
    return out


def aislar_bone_depth(depth_m, K, zmin, zmax, plano_mm=6.0, altura_min_mm=12.0,
                      eps_mm=12.0, min_pts=150):
    """Devuelve un depth donde SOLO quedan los pixeles del hueso (mesa y fondo a 0).
    Reusa: recorte Z -> quitar plano (mesa) -> filtro de altura -> cluster mayor.
    Hacerlo ANTES de integrar evita meter la mesa en el volumen TSDF."""
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    H, W = depth_m.shape
    vv, uu = np.mgrid[0:H, 0:W]
    valido = (depth_m > zmin) & (depth_m < zmax)
    if valido.sum() < min_pts:
        return None
    us = uu[valido]; vs = vv[valido]; z = depth_m[valido]
    pts = np.stack([(us - cx) * z / fx, (vs - cy) * z / fy, z], axis=1)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)
    keep = np.ones(len(pts), dtype=bool)
    plane, inl = pcd.segment_plane(plano_mm / 1000.0, 3, 1000)
    if len(inl) / len(pts) >= 0.25:
        a, b, c, d = plane
        nn = np.array([a, b, c]) / np.linalg.norm([a, b, c])
        dd = d / np.linalg.norm([a, b, c])
        sd = pts @ nn + dd
        if np.median(sd) < 0:
            sd = -sd
        keep = sd > altura_min_mm / 1000.0
    idx = np.where(keep)[0]
    if len(idx) < min_pts:
        return None
    sub = pcd.select_by_index(idx)
    labels = np.array(sub.cluster_dbscan(eps_mm / 1000.0, 40, print_progress=False))
    if labels.max() < 0:
        return None
    big = max(range(labels.max() + 1), key=lambda i: int((labels == i).sum()))
    local = idx[labels == big]
    mask2d = np.zeros((H, W), dtype=bool)
    mask2d[vs[local], us[local]] = True
    return np.where(mask2d, depth_m, 0.0).astype(np.float32)


def limpiar(pcd, eps_mm=8.0, min_pts=40):
    if len(pcd.points) < min_pts:
        return pcd
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    labels = np.array(pcd.cluster_dbscan(eps_mm / 1000.0, min_pts, print_progress=False))
    if labels.max() < 0:
        return pcd
    tam = sorted(((int((labels == k).sum()), k) for k in range(labels.max() + 1)), reverse=True)
    log(f"Clusters: {[t[0] for t in tam[:5]]}")
    return pcd.select_by_index(np.where(labels == tam[0][1])[0])


def main():
    ap = argparse.ArgumentParser(description="Prueba 8: fusion multi-vista por TSDF.")
    ap.add_argument("--config", default="codigo/iter4/tracker_config.yaml")
    ap.add_argument("--marker-id", type=int, default=0)
    ap.add_argument("--marker-mm", type=float, default=80.0)
    ap.add_argument("--frames", type=int, default=50, help="Frames a promediar por vista.")
    ap.add_argument("--voxel-mm", type=float, default=1.5, help="Tamano de voxel TSDF (mm).")
    ap.add_argument("--zmin", type=float, default=0.40, help="Profundidad min del hueso (m).")
    ap.add_argument("--zmax", type=float, default=0.80, help="Profundidad max integrada (m).")
    ap.add_argument("--dist-min", type=float, default=0.45)
    ap.add_argument("--dist-max", type=float, default=0.72)
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "nubes"))
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    marker_m = args.marker_mm / 1000.0
    voxel = args.voxel_mm / 1000.0

    cfg = cargar_config(str(REPO / args.config))
    detector, _, _, _ = crear_detector(cfg["markers"])

    log("ESPACIO captura | Q termina. Marcador verde = detectado. Giros pequenos.")
    cam = FemtoBoltBackend()
    cam.open()
    K, dist = cam.get_intrinsics()
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]

    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel, sdf_trunc=voxel * 5,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8)
    n_vistas = 0
    win = "TSDF - ESPACIO captura, Q termina"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while True:
        rgb, depth_mm, _ = cam.read()
        if rgb is None:
            continue
        prev = rgb.copy()
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        ca, ia, _ = detector.detectMarkers(gray)
        rc = None
        if ia is not None:
            for i, mid in enumerate(ia.flatten()):
                if int(mid) == args.marker_id:
                    rc = ca[i].reshape(4, 2)
                    cv2.polylines(prev, [rc.astype(int).reshape(-1, 1, 2)], True, (0, 255, 0), 3)
        est = "MARCADOR OK" if rc is not None else "SIN MARCADOR"
        col = (0, 200, 0) if rc is not None else (0, 0, 255)
        cv2.putText(prev, f"{est} | vistas: {n_vistas} | ESPACIO captura, Q termina",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2)
        cv2.imshow(win, prev)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        if key == ord(' '):
            if rc is None:
                log("Sin marcador: no capturo."); continue
            acc = np.zeros_like(depth_mm, dtype=np.float64)
            cnt = np.zeros_like(depth_mm, dtype=np.int32)
            rgb_v = rgb
            for _ in range(args.frames):
                r2, d2, _ = cam.read()
                if d2 is None:
                    continue
                m = d2 > 0
                acc[m] += d2[m]; cnt[m] += 1; rgb_v = r2
            depth_avg = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0) / 1000.0  # metros
            g2 = cv2.cvtColor(rgb_v, cv2.COLOR_BGR2GRAY)
            ca2, ia2, _ = detector.detectMarkers(g2)
            rc2 = None
            if ia2 is not None:
                for i, mid in enumerate(ia2.flatten()):
                    if int(mid) == args.marker_id:
                        rc2 = ca2[i].reshape(4, 2)
            if rc2 is None:
                log("Perdi marcador al promediar: descartada."); continue
            pose = pose_marker(rc2, K, dist, marker_m)
            if pose is None:
                log("Pose fallo: descartada."); continue
            R, t = pose
            d = float(np.linalg.norm(t))
            if not (args.dist_min <= d <= args.dist_max):
                log(f"Marcador a {d*100:.1f} cm (fuera de rango): descartada."); continue
            depth_masked = mask_marker(depth_avg, rc2)
            depth_bone = aislar_bone_depth(depth_masked, K, args.zmin, args.zmax)
            if depth_bone is None:
                log("No pude aislar el hueso en esta vista: descartada."); continue
            color_o3d = o3d.geometry.Image(cv2.cvtColor(rgb_v, cv2.COLOR_BGR2RGB).copy())
            depth_o3d = o3d.geometry.Image(depth_bone)
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color_o3d, depth_o3d, depth_scale=1.0, depth_trunc=args.zmax,
                convert_rgb_to_intensity=False)
            H, W = depth_avg.shape
            intr = o3d.camera.PinholeCameraIntrinsic(W, H, fx, fy, cx, cy)
            extr = np.eye(4); extr[:3, :3] = R; extr[:3, 3] = t  # marcador->camara
            volume.integrate(rgbd, intr, extr)
            n_vistas += 1
            log(f"Vista {n_vistas} integrada (marcador a {d*100:.1f} cm).")

    cam.close()
    cv2.destroyAllWindows()

    if n_vistas == 0:
        log("No integraste ninguna vista."); sys.exit(1)

    log(f"Extrayendo superficie de {n_vistas} vistas...")
    pcd = volume.extract_point_cloud()
    log(f"Nube TSDF cruda: {len(pcd.points):,} pts")
    pcd = limpiar(pcd)
    pts = np.asarray(pcd.points); ext = (pts.max(0) - pts.min(0)) * 1000
    log(f"Hueso: {len(pcd.points):,} pts, {ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"tsdf_{ts}.ply"
    o3d.io.write_point_cloud(str(out), pcd)
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    mesh = mesh.crop(pcd.get_axis_aligned_bounding_box())
    out_mesh = outdir / f"tsdf_{ts}_malla.ply"
    o3d.io.write_triangle_mesh(str(out_mesh), mesh)
    log(f"Guardado: {out}  +  {out_mesh.name}")
    log("Registra con:  python femto_pruebas\\06_registro_semilla.py --stl "
        '"stl\\Segmentation_Bone_CT.stl" --nube ' + str(out).split("PoyectoNavegacion\\")[-1] + " --ver")

    if args.ver:
        o3d.visualization.draw_geometries([pcd])


if __name__ == "__main__":
    main()
