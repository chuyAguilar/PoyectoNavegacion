"""
Hello World para Femto Bolt — K0 de iter 4.

Valida:
1. SDK pyorbbecsdk instalado y funcionando.
2. Conexion a la camara Femto Bolt.
3. RGB + Depth streams sincronizados.
4. Alineacion HW/SW de depth a color.
5. Deteccion de ArUco en RGB (mismo diccionario que iter 2/3).
6. Lectura de depth medida en las esquinas de markers detectados.

Salida esperada: ventana con video RGB + overlay de markers detectados +
profundidad medida (mm) en cada marker. Permite confirmar que la camara
funciona y que podemos integrarla al tracker.

Uso:
    python hello_femtobolt.py
    Presionar 'q' para salir.
"""
import sys
import time

import cv2
import numpy as np

try:
    from pyorbbecsdk import (
        Pipeline, Config, OBSensorType, OBFormat, OBStreamType,
        OBAlignMode, AlignFilter,
    )
except ImportError:
    print("[ERROR] pyorbbecsdk no instalado.")
    print("Instalar con: pip install pyorbbecsdk")
    print("Si esa falla, ver https://github.com/orbbec/pyorbbecsdk")
    sys.exit(1)

# ArUco: usamos el mismo diccionario que iter 2/3
DICT_NAME = "DICT_ARUCO_MIP_36h12"
aruco_dict = cv2.aruco.getPredefinedDictionary(
    getattr(cv2.aruco, DICT_NAME)
)
if hasattr(cv2.aruco, "ArucoDetector"):
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    USAR_API_NUEVA = True
else:
    params = cv2.aruco.DetectorParameters_create()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    USAR_API_NUEVA = False


def detectar_aruco(rgb):
    """Detecta markers ArUco en imagen RGB. Devuelve (corners, ids)."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
    if USAR_API_NUEVA:
        corners, ids, _ = detector.detectMarkers(gray)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)
    return corners, ids


def main():
    print(f"[Hello Femto Bolt - K0 iter 4]")
    print(f"Iniciando pipeline...")

    # 1. Crear pipeline
    pipeline = Pipeline()
    config = Config()

    # 2. Configurar stream COLOR (RGB)
    try:
        color_profiles = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        color_profile = color_profiles.get_default_video_stream_profile()
        config.enable_stream(color_profile)
        print(f"  Color: {color_profile.get_width()}x{color_profile.get_height()} "
              f"@ {color_profile.get_fps()} FPS, formato {color_profile.get_format()}")
    except Exception as e:
        print(f"[ERROR] No se pudo configurar color stream: {e}")
        sys.exit(1)

    # 3. Configurar stream DEPTH
    try:
        depth_profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        depth_profile = depth_profiles.get_default_video_stream_profile()
        config.enable_stream(depth_profile)
        print(f"  Depth: {depth_profile.get_width()}x{depth_profile.get_height()} "
              f"@ {depth_profile.get_fps()} FPS")
    except Exception as e:
        print(f"[ERROR] No se pudo configurar depth stream: {e}")
        sys.exit(1)

    # 4. Habilitar sincronizacion de frames
    pipeline.enable_frame_sync()

    # 5. Configurar alineacion: probar HW primero, fallback SW
    use_sw_align = True
    try:
        hw_d2c = pipeline.get_d2c_depth_profile_list(color_profile, OBAlignMode.HW_MODE)
        if len(hw_d2c) > 0:
            config.set_align_mode(OBAlignMode.HW_MODE)
            use_sw_align = False
            print(f"  Alineacion: HW (mejor)")
        else:
            config.set_align_mode(OBAlignMode.SW_MODE)
            print(f"  Alineacion: SW (HW no disponible)")
    except Exception:
        config.set_align_mode(OBAlignMode.SW_MODE)
        print(f"  Alineacion: SW (fallback)")

    sw_align_filter = AlignFilter(align_to_stream=OBStreamType.COLOR_STREAM) if use_sw_align else None

    # 6. Iniciar pipeline
    try:
        pipeline.start(config)
        print(f"  Pipeline iniciado OK.")
    except Exception as e:
        print(f"[ERROR] No se pudo iniciar pipeline: {e}")
        sys.exit(1)

    print(f"\nCapturando frames... (presionar 'q' en la ventana para salir)\n")

    n_frames = 0
    n_con_markers = 0
    t_inicio = time.time()
    last_print = t_inicio

    try:
        while True:
            frames = pipeline.wait_for_frames(1000)
            if frames is None:
                continue

            # Aplicar alineacion SW si corresponde
            if sw_align_filter is not None:
                frames = sw_align_filter.process(frames)
                if not frames:
                    continue
                frames = frames.as_frame_set()

            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            # Decodificar RGB
            color_data = np.asanyarray(color_frame.get_data())
            fmt = color_frame.get_format()
            if fmt == OBFormat.RGB:
                rgb = color_data.reshape(color_frame.get_height(), color_frame.get_width(), 3)
                rgb = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            elif fmt == OBFormat.MJPG:
                rgb = cv2.imdecode(color_data, cv2.IMREAD_COLOR)
            elif fmt == OBFormat.YUYV:
                # Si viene en YUYV decodificar
                rgb = cv2.cvtColor(
                    color_data.reshape(color_frame.get_height(), color_frame.get_width(), 2),
                    cv2.COLOR_YUV2BGR_YUYV
                )
            else:
                print(f"[WARN] Formato color desconocido: {fmt}. Saltando.")
                continue

            # Decodificar Depth (en mm, multiplicando por depth_scale)
            depth_data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
            depth_data = depth_data.reshape(depth_frame.get_height(), depth_frame.get_width())
            depth_scale = depth_frame.get_depth_scale()
            depth_mm = depth_data.astype(np.float32) * depth_scale

            n_frames += 1

            # Detectar ArUco en RGB
            corners, ids = detectar_aruco(rgb)

            display = rgb.copy()

            if ids is not None and len(ids) > 0:
                n_con_markers += 1
                cv2.aruco.drawDetectedMarkers(display, corners, ids)

                # Para cada marker, leer la depth en su centro
                for i, mid in enumerate(ids.flatten().tolist()):
                    pts = corners[i].reshape(4, 2)
                    cx, cy = int(pts[:, 0].mean()), int(pts[:, 1].mean())
                    if 0 <= cy < depth_mm.shape[0] and 0 <= cx < depth_mm.shape[1]:
                        z_mm = depth_mm[cy, cx]
                        cv2.putText(display, f"ID {mid}: {z_mm:.0f}mm",
                                    (cx + 10, cy),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # Info en pantalla
            now = time.time()
            fps = n_frames / (now - t_inicio)
            cv2.putText(display, f"FPS: {fps:.1f}  Markers: {0 if ids is None else len(ids)}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Visualizar depth como overlay
            depth_vis = cv2.normalize(depth_mm, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_vis = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
            if depth_vis.shape[:2] != display.shape[:2]:
                depth_vis = cv2.resize(depth_vis, (display.shape[1], display.shape[0]))
            combined = np.hstack([display, depth_vis])

            cv2.imshow("Femto Bolt - RGB (izq) + Depth (der) - 'q' para salir", combined)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            if now - last_print > 5.0:
                pct = 100.0 * n_con_markers / max(1, n_frames)
                print(f"  [{now-t_inicio:.0f}s] FPS={fps:.1f}, "
                      f"{n_con_markers}/{n_frames} frames con markers ({pct:.0f}%)")
                last_print = now

    except KeyboardInterrupt:
        print("\n[Interrupcion del usuario]")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
        print(f"\n[Terminado] Total {n_frames} frames procesados.")
        print(f"  Frames con markers: {n_con_markers} ({100.0*n_con_markers/max(1,n_frames):.0f}%)")
        if n_frames > 0:
            print(f"  FPS promedio: {n_frames / (time.time() - t_inicio):.1f}")


if __name__ == "__main__":
    main()
