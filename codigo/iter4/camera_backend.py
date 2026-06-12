"""
Backend abstracto de camara para tracker.py iter 4.

Permite intercambiar entre webcam (iter 1-3) y Femto Bolt (iter 4) sin modificar
el codigo del tracker. Configurable via tracker_config.yaml: camera_type.

Interfaz comun:
  - open():        abre la camara, hace warmup, carga calibracion intrinseca.
  - read():        devuelve (rgb_bgr, depth_mm_or_None, timestamp).
  - get_intrinsics(): K (3x3) + dist (5,) del color stream.
  - close():       libera recursos.

Tambien soporta context manager: `with create_backend(cfg) as cam: ...`.
"""
from abc import ABC, abstractmethod
import time

import numpy as np


# ============================================================================
# Interfaz abstracta
# ============================================================================

class CameraBackend(ABC):
    """Interfaz comun para captura de imagen RGB + (opcional) Depth."""

    @abstractmethod
    def open(self) -> None:
        """Abre la camara. Bloquea hasta que esta lista para capturar."""
        pass

    @abstractmethod
    def read(self):
        """Lee un frame.

        Returns:
            (rgb_bgr, depth_mm_or_None, timestamp)
            - rgb_bgr:  imagen BGR (H, W, 3) uint8.
            - depth_mm: depth en milimetros (H, W) float32, alineada al RGB.
                        None si el backend no provee depth.
            - timestamp: tiempo del frame en segundos (time.time()).
        Si la lectura falla, devuelve (None, None, None).
        """
        pass

    @abstractmethod
    def get_intrinsics(self):
        """Devuelve (K, dist) del color stream.

        K: matriz 3x3 numpy float64.
        dist: vector de 5 coefs [k1, k2, p1, p2, k3] numpy float64.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Cierra la camara y libera recursos."""
        pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================================
# Backend Webcam (legacy - iter 1-3)
# ============================================================================

class WebcamBackend(CameraBackend):
    """Wrap del cv2.VideoCapture clasico. Solo RGB (sin depth)."""

    def __init__(self, source=0, width=640, height=480, fps=30,
                 backend="MSMF", fourcc="MJPG", calibration_file=None):
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.backend_name = backend
        self.fourcc = fourcc
        self.calibration_file = calibration_file
        self.cap = None
        self._K = None
        self._dist = None

    def open(self):
        import cv2
        backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
        backend = backends.get(self.backend_name.upper(), cv2.CAP_MSMF)

        print(f"[Webcam] Abriendo source={self.source} backend={self.backend_name}...")
        t0 = time.time()
        self.cap = cv2.VideoCapture(int(self.source), backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"No se pudo abrir webcam source={self.source}")
        print(f"[Webcam] Abierta en {time.time()-t0:.1f}s")

        if self.fourcc:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.fourcc))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        print(f"[Webcam] Warmup (descartando 5 frames)...")
        for _ in range(5):
            self.cap.read()
        print(f"[Webcam] Lista para capturar.")

        if self.calibration_file:
            self._load_calibration()

    def _load_calibration(self):
        import cv2
        fs = cv2.FileStorage(str(self.calibration_file), cv2.FILE_STORAGE_READ)
        if not fs.isOpened():
            raise FileNotFoundError(f"No se pudo abrir {self.calibration_file}")
        self._K = np.asarray(fs.getNode("camera_matrix").mat(), dtype=np.float64)
        self._dist = np.asarray(fs.getNode("distortion_coefficients").mat(), dtype=np.float64).flatten()
        fs.release()
        print(f"[Webcam] Calibracion cargada de {self.calibration_file}")

    def read(self):
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None, None, None
        return frame, None, time.time()

    def get_intrinsics(self):
        if self._K is None:
            raise RuntimeError("No se cargo la calibracion intrinseca (calibration_file vacio)")
        return self._K, self._dist

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            print(f"[Webcam] Cerrada.")


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


# ============================================================================
# Factory
# ============================================================================

def create_backend(cfg_camera):
    """Crea el backend correcto segun cfg_camera['camera_type'].

    Args:
        cfg_camera: dict de configuracion (sub-seccion 'camera' de tracker_config.yaml).

    Returns:
        Instancia de CameraBackend (no abierto todavia).
    """
    camera_type = cfg_camera.get("camera_type", "webcam").lower()
    if camera_type == "webcam":
        return WebcamBackend(
            source=cfg_camera["source"],
            width=cfg_camera["width"],
            height=cfg_camera["height"],
            fps=cfg_camera.get("fps", 30),
            backend=cfg_camera.get("backend", "MSMF"),
            fourcc=cfg_camera.get("fourcc", "MJPG"),
            calibration_file=cfg_camera.get("calibration_file"),
        )
    elif camera_type == "femtobolt":
        return FemtoBoltBackend(
            calibration_file=cfg_camera.get("calibration_file"),
        )
    else:
        raise ValueError(f"camera_type desconocido: {camera_type}. "
                         f"Opciones: 'webcam', 'femtobolt'")
