"""
Mide el ruido empirico del depth del Femto Bolt apuntando a una superficie
plana (pared de caja de luz). Da el sigma_3d que va a usar el BA en K4.3.

Como funciona:
  - Captura ~50 frames a la distancia que vos elijas (50-70 cm tipico).
  - Toma una ROI central (default 200x200 px) del depth alineado a color.
  - Por cada frame mide:
      * distancia media z_mean (mm)  -> a que distancia esta la pared
      * std espacial planeidad (mm)  -> que tan "ruidosa" es una sola foto
      * std temporal del pixel central (mm) -> cuanto fluctua frame-a-frame
  - Reporta sigma_3d empirico = sqrt(spacial_std^2 + temporal_std^2)
    (descomposicion de Pythagoras: dos fuentes de ruido independientes).

Uso:
    python iter4/medir_sigma_depth.py --duracion 5 --roi 200
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from camera_backend import create_backend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duracion", type=int, default=5,
                        help="Segundos de captura (default 5 = ~75 frames @ 15 fps efectivos)")
    parser.add_argument("--roi", type=int, default=200,
                        help="Lado del ROI cuadrado central en pixeles RGB (default 200)")
    parser.add_argument("--config", default="iter4/tracker_config.yaml",
                        help="Config con camera_type: femtobolt")
    args = parser.parse_args()

    import yaml
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    cam = create_backend(cfg["camera"])
    cam.open()
    print(f"[Sigma] Backend: {type(cam).__name__}")
    print(f"[Sigma] ROI central: {args.roi}x{args.roi} px")
    print(f"[Sigma] Apunta a la PARED PLANA durante {args.duracion} s. Sin movimiento.")
    print(f"[Sigma] Empezando en 3 segundos...")
    time.sleep(3)
    print(f"[Sigma] MIDIENDO...")

    z_means_per_frame = []      # distancia media de cada frame
    z_stds_per_frame = []       # std espacial dentro de cada frame
    z_center_per_frame = []     # depth del pixel central (para std temporal)
    n_frames = 0
    t_start = time.time()

    try:
        while time.time() - t_start < args.duracion:
            frame, depth_mm, ts = cam.read()
            if depth_mm is None:
                continue
            H, W = depth_mm.shape[:2]
            cx, cy = W // 2, H // 2
            half = args.roi // 2
            roi = depth_mm[cy-half:cy+half, cx-half:cx+half]
            validos = roi[roi > 0]
            if validos.size < 100:
                continue
            z_means_per_frame.append(float(np.mean(validos)))
            z_stds_per_frame.append(float(np.std(validos)))
            # Pixel central para std temporal
            z_c = depth_mm[cy, cx]
            if z_c > 0:
                z_center_per_frame.append(float(z_c))
            n_frames += 1
    finally:
        cam.close()

    if n_frames < 10:
        print(f"[ERROR] Solo {n_frames} frames validos. Recortar muy cerca o muy lejos?")
        sys.exit(1)

    z_means = np.array(z_means_per_frame)
    z_stds = np.array(z_stds_per_frame)
    z_center = np.array(z_center_per_frame)

    dist_media = float(np.mean(z_means))
    spatial_std_mean = float(np.mean(z_stds))     # ruido dentro del frame (planeidad)
    spatial_std_max = float(np.max(z_stds))
    temporal_std = float(np.std(z_center))         # ruido frame-a-frame en un punto fijo
    sigma_3d = float(np.sqrt(spatial_std_mean**2 + temporal_std**2))

    print()
    print(f"=== Resultados ({n_frames} frames) ===")
    print(f"  Distancia media a la pared:    {dist_media:.1f} mm  ({dist_media/10:.1f} cm)")
    print(f"  Std espacial PROMEDIO:          {spatial_std_mean:.2f} mm")
    print(f"    (planeidad de la pared en un solo frame)")
    print(f"  Std espacial MAX:               {spatial_std_max:.2f} mm")
    print(f"  Std temporal:                   {temporal_std:.2f} mm")
    print(f"    (jitter frame-a-frame en el pixel central)")
    print()
    print(f"  >>> sigma_3d empirico recomendado: {sigma_3d:.1f} mm <<<")
    print()
    if sigma_3d < 3:
        print(f"  Femto Bolt en condiciones EXCELENTES (sigma <3 mm).")
    elif sigma_3d < 7:
        print(f"  Femto Bolt en rango ESPERADO (3-7 mm a 0.5-1 m).")
    else:
        print(f"  Femto Bolt con ruido MAS ALTO de lo esperado. Posibles causas:")
        print(f"    - Pared con material reflectivo o muy oscuro (ToF lo odia)")
        print(f"    - Distancia <0.5 m (fuera del rango de enfoque)")
        print(f"    - Interferencia con otras camaras ToF cerca")


if __name__ == "__main__":
    main()
