"""FemtoBoltBackend, archivado (meta 003, fase 3; ADR-025, ADR-027).

Sacado tal cual de `iter4/camera_backend.py` (hoy `codigo/camera/backend.py`),
que desde la meta 003 solo sirve la webcam: `create_backend` con
`camera_type: femtobolt` aborta y dice que esta aqui. Es registro: no lo
importa nada vivo ni lo recoge la suite. Para revivirlo haria falta el SDK
(`pyorbbecsdk2`, sigue en requirements.txt) y volver a registrarlo en
`create_backend`.
"""
import time

import numpy as np

from camera.backend import CameraBackend


# ============================================================================
# Backend Femto Bolt (iter 4)
# ============================================================================

class FemtoBoltBackend(CameraBackend):
    """Wrap del pipeline pyorbbecsdk con depth + RGB sincronizado y alineado."""

    def __init__(self, calibration_file=None):
        # calibration_file es opcional: el SDK provee la calibracion de fabrica.
        # Si se pasa, la usamos en lugar de la de fabrica.
        self.calibration_file = calibration_file
        self.pipeline = None
        self.align_filter = None
        self._K_color = None
        self._dist_color = None
        self._K_depth = None
        self._dist_depth = None
        self._T_d2c = None

    def open(self):
        from pyorbbecsdk import (
            Pipeline, Config, OBSensorType, OBStreamType,
            OBAlignMode, AlignFilter,
        )

        print(f"[FemtoBolt] Inicializando pipeline...")
        self.pipeline = Pipeline()
        config = Config()

        color_profiles = self.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        color_profile = color_profiles.get_default_video_stream_profile()
        config.enable_stream(color_profile)
        print(f"[FemtoBolt] Color: {color_profile.get_width()}x{color_profile.get_height()} "
              f"@ {color_profile.get_fps()} FPS")

        depth_profiles = self.pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        depth_profile = depth_profiles.get_default_video_stream_profile()
        config.enable_stream(depth_profile)
        print(f"[FemtoBolt] Depth: {depth_profile.get_width()}x{depth_profile.get_height()} "
              f"@ {depth_profile.get_fps()} FPS")

        self.pipeline.enable_frame_sync()

        # Alineacion HW si disponible, sino SW
        try:
            hw_d2c = self.pipeline.get_d2c_depth_profile_list(color_profile, OBAlignMode.HW_MODE)
            if len(hw_d2c) > 0:
                config.set_align_mode(OBAlignMode.HW_MODE)
                self.align_filter = None
                print(f"[FemtoBolt] Alineacion: HW")
            else:
                raise Exception("HW no disponible")
        except Exception:
            config.set_align_mode(OBAlignMode.SW_MODE)
            self.align_filter = AlignFilter(align_to_stream=OBStreamType.COLOR_STREAM)
            print(f"[FemtoBolt] Alineacion: SW (HW no disponible)")

        # Leer calibracion del SDK (antes de start, los perfiles son estables)
        self._load_calibration_from_sdk(color_profile, depth_profile)

        # Si el usuario paso calibration_file, sobrescribir con esa (para overrides)
        if self.calibration_file:
            self._load_calibration_from_file()

        self.pipeline.start(config)
        print(f"[FemtoBolt] Pipeline iniciado. Warmup (5 frames)...")
        for _ in range(5):
            self.pipeline.wait_for_frames(1000)
        print(f"[FemtoBolt] Lista para capturar.")

    def _load_calibration_from_sdk(self, color_profile, depth_profile):
        ci = color_profile.get_intrinsic()
        cd = color_profile.get_distortion()
        di = depth_profile.get_intrinsic()
        dd = depth_profile.get_distortion()
        ext = depth_profile.get_extrinsic_to(color_profile)

        self._K_color = np.array([
            [ci.fx, 0, ci.cx],
            [0, ci.fy, ci.cy],
            [0, 0, 1],
        ], dtype=np.float64)
        self._dist_color = np.array([cd.k1, cd.k2, cd.p1, cd.p2, cd.k3], dtype=np.float64)
        self._K_depth = np.array([
            [di.fx, 0, di.cx],
            [0, di.fy, di.cy],
            [0, 0, 1],
        ], dtype=np.float64)
        self._dist_depth = np.array([dd.k1, dd.k2, dd.p1, dd.p2, dd.k3], dtype=np.float64)

        R = np.array(ext.rot).reshape(3, 3)
        t = np.array(ext.transform).flatten()
        T = np.eye(4)
        T[:3, :3] = R
        if t.size == 3:
            T[:3, 3] = t
        self._T_d2c = T
        print(f"[FemtoBolt] Calibracion de fabrica cargada (K_color, K_depth, T_d2c).")

    def _load_calibration_from_file(self):
        import yaml
        with open(self.calibration_file) as f:
            calib = yaml.safe_load(f)
        if "color" in calib:
            self._K_color = np.array(calib["color"]["K"], dtype=np.float64)
            self._dist_color = np.array(calib["color"]["dist"], dtype=np.float64)
        if "depth" in calib:
            self._K_depth = np.array(calib["depth"]["K"], dtype=np.float64)
            self._dist_depth = np.array(calib["depth"]["dist"], dtype=np.float64)
        if "extrinsic_depth_to_color" in calib:
            self._T_d2c = np.array(calib["extrinsic_depth_to_color"], dtype=np.float64)
        print(f"[FemtoBolt] Calibracion overrideada desde {self.calibration_file}")

    def read(self):
        import cv2
        from pyorbbecsdk import OBFormat

        frames = self.pipeline.wait_for_frames(1000)
        if frames is None:
            return None, None, None

        # Instrumentacion diagnostico D2C (2026-06-11): guardar el depth CRUDO
        # (640x576, frame del sensor depth) ANTES de alinear, para poder
        # comparar offline la alineacion del SDK contra una alineacion manual
        # con la calibracion de fabrica. No afecta el flujo normal.
        self.last_depth_raw = None
        raw_df = frames.get_depth_frame()
        if raw_df is not None:
            raw = np.frombuffer(raw_df.get_data(), dtype=np.uint16)
            raw = raw.reshape(raw_df.get_height(), raw_df.get_width())
            self.last_depth_raw = raw.astype(np.float32) * raw_df.get_depth_scale()

        if self.align_filter is not None:
            frames = self.align_filter.process(frames)
            if not frames:
                return None, None, None
            frames = frames.as_frame_set()

        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if not color_frame:
            return None, None, None

        color_data = np.asanyarray(color_frame.get_data())
        fmt = color_frame.get_format()
        if fmt == OBFormat.MJPG:
            rgb = cv2.imdecode(color_data, cv2.IMREAD_COLOR)
        elif fmt == OBFormat.RGB:
            h, w = color_frame.get_height(), color_frame.get_width()
            rgb = color_data.reshape(h, w, 3)
            rgb = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        else:
            return None, None, None

        depth_mm = None
        if depth_frame is not None:
            d_data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
            d_data = d_data.reshape(depth_frame.get_height(), depth_frame.get_width())
            d_scale = depth_frame.get_depth_scale()
            depth_mm = d_data.astype(np.float32) * d_scale

        return rgb, depth_mm, time.time()

    def get_intrinsics(self):
        return self._K_color, self._dist_color

    def get_depth_intrinsics(self):
        """Especifica del Femto Bolt: K y dist del sensor depth."""
        return self._K_depth, self._dist_depth

    def get_extrinsic_depth_to_color(self):
        """Especifica del Femto Bolt: matriz 4x4 que lleva del frame depth al frame color."""
        return self._T_d2c

    def close(self):
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
            print(f"[FemtoBolt] Pipeline detenido.")

