# -*- coding: utf-8 -*-
"""
PRUEBA 1 - Nube de puntos de "todo lo que ve" la Femto Bolt.

Objetivo (dentro del marco de registro por superficie):
  Convertir el mapa de profundidad de la Femto en una nube de puntos XYZ+color
  en el frame de la camara, y guardarla como .ply. Es el primer ladrillo: sin
  una buena nube no hay registro posible.

Lo que hace:
  1. Abre la Femto reusando FemtoBoltBackend (camera_backend.py de iter4), que ya
     entrega depth alineado al color + la calibracion intrinseca de fabrica.
  2. Promedia N frames de una escena ESTATICA (reduce ruido del ToF por ~1/sqrt(N)).
  3. Reproyecta cada pixel valido a 3D con la intrinseca del color: el resultado
     es una nube en METROS, en el frame de la camara color.
  4. La guarda como .ply binario (abrible en MeshLab / 3D Slicer / Open3D).

Lo que NO hace todavia (eso es prueba 2 y 3):
  - No recorta el objeto del fondo (sale TODO lo que ve: mesa, manos, etc.).
  - No filtra outliers / flying pixels.
  - No registra contra ningun STL.

REGLAS DEL PROYECTO que importan aqui:
  - Capturar SIEMPRE fuera de la caja de luz (el multipath de las paredes mete
    bias +57 mm dentro de la caja; fuera baja a ~-10 mm).
  - Calentar la camara idealmente 40-60 min antes de una captura que vayas a
    tomar como cuantitativa (el sensor deriva ~2 mm en frio).
  - Escena ESTATICA durante la captura (el promedio temporal asume que nada se
    mueve; si se mueve, sale borroso).

Uso (desde la carpeta del repo):
    python femto_pruebas\01_nube_de_puntos.py
    python femto_pruebas\01_nube_de_puntos.py --frames 20 --zmin 0.30 --zmax 1.20
    python femto_pruebas\01_nube_de_puntos.py --ver          (visualiza si hay open3d)

Salida:
    femto_pruebas\nubes\nube_YYYYmmdd_HHMMSS.ply
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# --- Reusar el backend probado de iter4 (no reimplementar el SDK) ---
REPO = Path(__file__).resolve().parents[1]
ITER4 = REPO / "codigo" / "iter4"
sys.path.insert(0, str(ITER4))
from camera_backend import FemtoBoltBackend  # noqa: E402


def log(m):
    print(f"[P1] {m}", flush=True)


def guardar_ply(path: Path, xyz: np.ndarray, rgb: np.ndarray):
    """Escribe un .ply binario (little-endian) con color. Sin dependencias."""
    n = len(xyz)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    dt = np.dtype([
        ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
        ("red", "u1"), ("green", "u1"), ("blue", "u1"),
    ])
    arr = np.empty(n, dtype=dt)
    arr["x"], arr["y"], arr["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    arr["red"], arr["green"], arr["blue"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(arr.tobytes())


def main():
    ap = argparse.ArgumentParser(description="Prueba 1: nube de puntos cruda de la Femto Bolt.")
    ap.add_argument("--frames", type=int, default=10,
                    help="Frames a promediar (escena estatica). Default 10.")
    ap.add_argument("--zmin", type=float, default=0.20,
                    help="Profundidad minima en metros a conservar. Default 0.20.")
    ap.add_argument("--zmax", type=float, default=1.50,
                    help="Profundidad maxima en metros a conservar. Default 1.50.")
    ap.add_argument("--ver", action="store_true",
                    help="Visualizar la nube al final (requiere open3d).")
    ap.add_argument("--outdir", default=str(Path(__file__).parent / "nubes"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    log("RECORDATORIO: captura FUERA de la caja de luz, escena ESTATICA, "
        "objeto a 0.5-0.7 m.")
    log(f"Abriendo Femto Bolt y promediando {args.frames} frames...")

    cam = FemtoBoltBackend()
    cam.open()
    K, dist = cam.get_intrinsics()  # intrinseca del COLOR (el depth viene alineado al color)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    log(f"Intrinseca color: fx={fx:.1f} fy={fy:.1f} cx={cx:.1f} cy={cy:.1f}")

    # --- Acumular depth de N frames (promedio temporal sobre pixeles validos) ---
    acc = None
    cnt = None
    rgb_last = None
    obtenidos = 0
    intentos = 0
    while obtenidos < args.frames and intentos < args.frames * 10:
        intentos += 1
        rgb, depth_mm, _ = cam.read()
        if rgb is None or depth_mm is None:
            continue
        if acc is None:
            H, W = depth_mm.shape[:2]
            acc = np.zeros((H, W), dtype=np.float64)
            cnt = np.zeros((H, W), dtype=np.int32)
        valido = depth_mm > 0
        acc[valido] += depth_mm[valido]
        cnt[valido] += 1
        rgb_last = rgb
        obtenidos += 1
        log(f"  frame {obtenidos}/{args.frames}  (pixeles con depth: {int(valido.sum())})")
    cam.close()

    if acc is None or obtenidos == 0:
        log("ERROR: no se obtuvo ningun frame con depth. "
            "Revisar conexion / que la camara entregue depth.")
        sys.exit(1)

    # Profundidad promedio en METROS (0 donde nunca hubo dato)
    depth_m = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0) / 1000.0
    H, W = depth_m.shape

    # --- Reproyeccion pixel -> 3D (frame de la camara color, metros) ---
    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    z = depth_m
    mask = (z > args.zmin) & (z < args.zmax)
    x = (uu - cx) * z / fx
    y = (vv - cy) * z / fy

    xyz = np.stack([x[mask], y[mask], z[mask]], axis=1).astype(np.float32)
    # rgb_last es BGR (OpenCV) -> a RGB para el .ply
    rgb = rgb_last[..., ::-1][mask].astype(np.uint8)

    log(f"Nube generada: {len(xyz):,} puntos "
        f"({100.0 * len(xyz) / (H * W):.1f}% de {W}x{H} pixeles).")
    if len(xyz):
        log(f"  Rango Z: {xyz[:, 2].min():.3f} - {xyz[:, 2].max():.3f} m "
            f"(mediana {np.median(xyz[:, 2]):.3f} m)")
        log(f"  Extension X: {xyz[:, 0].min():.3f} - {xyz[:, 0].max():.3f} m | "
            f"Y: {xyz[:, 1].min():.3f} - {xyz[:, 1].max():.3f} m")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ply_path = outdir / f"nube_{ts}.ply"
    guardar_ply(ply_path, xyz, rgb)
    log(f"Guardada: {ply_path}")

    if args.ver:
        try:
            import open3d as o3d
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(xyz.astype(np.float64))
            pcd.colors = o3d.utility.Vector3dVector(rgb.astype(np.float64) / 255.0)
            log("Abriendo visor de Open3D (cierra la ventana para terminar)...")
            o3d.visualization.draw_geometries([pcd])
        except ImportError:
            log("open3d no instalado: omito visualizacion. "
                "Instala con  pip install open3d  o abre el .ply en MeshLab/Slicer.")


if __name__ == "__main__":
    main()
