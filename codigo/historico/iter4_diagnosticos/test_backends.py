"""Smoke test de camera_backend.py: probar ambos backends por separado.

Uso:
    python iter4/test_backends.py --tipo femtobolt
    python iter4/test_backends.py --tipo webcam --source 0
"""
import argparse
import time

import cv2

from camera_backend import create_backend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tipo", choices=["webcam", "femtobolt"], default="femtobolt")
    parser.add_argument("--source", type=int, default=0, help="Source para webcam")
    parser.add_argument("--duracion", type=int, default=10, help="Segundos del test")
    args = parser.parse_args()

    # Construir cfg sintetica
    if args.tipo == "webcam":
        cfg = {
            "camera_type": "webcam",
            "source": args.source,
            "width": 640,
            "height": 480,
            "fps": 30,
            "backend": "MSMF",
            "fourcc": "MJPG",
        }
    else:
        cfg = {"camera_type": "femtobolt"}

    print(f"\n[Test backend: {args.tipo}]\n")
    cam = create_backend(cfg)

    with cam:
        # Mostrar info de calibracion
        try:
            K, dist = cam.get_intrinsics()
            print(f"\nK (color):\n{K}\ndist: {dist}")
        except Exception as e:
            print(f"\n[INFO] get_intrinsics() fallo: {e}")

        if isinstance(cam, type(cam)) and hasattr(cam, "get_depth_intrinsics"):
            try:
                K_d, dist_d = cam.get_depth_intrinsics()
                print(f"\nK_depth:\n{K_d}")
                print(f"T_depth_to_color:\n{cam.get_extrinsic_depth_to_color()}")
            except Exception as e:
                print(f"[INFO] get_depth_intrinsics() N/A para este backend")

        print(f"\nLeyendo frames durante {args.duracion} segundos. Presiona 'q' para salir antes.\n")
        n_frames = 0
        t_inicio = time.time()
        last_print = t_inicio

        while time.time() - t_inicio < args.duracion:
            rgb, depth, ts = cam.read()
            if rgb is None:
                continue
            n_frames += 1

            # Visualizar
            display = rgb.copy()
            if depth is not None:
                d_vis = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                d_vis = cv2.applyColorMap(d_vis, cv2.COLORMAP_JET)
                if d_vis.shape[:2] != rgb.shape[:2]:
                    d_vis = cv2.resize(d_vis, (rgb.shape[1], rgb.shape[0]))
                display = cv2.hconcat([display, d_vis])

            fps = n_frames / (time.time() - t_inicio)
            label = f"Backend: {args.tipo}  FPS: {fps:.1f}  Frames: {n_frames}"
            cv2.putText(display, label, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow(f"Test {args.tipo} - q salir", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            t_now = time.time()
            if t_now - last_print > 3.0:
                print(f"  [{t_now - t_inicio:.0f}s] FPS={fps:.1f}, frames={n_frames}")
                last_print = t_now

    cv2.destroyAllWindows()
    print(f"\n[OK] Test {args.tipo} terminado. {n_frames} frames en {time.time()-t_inicio:.1f}s.")


if __name__ == "__main__":
    main()
