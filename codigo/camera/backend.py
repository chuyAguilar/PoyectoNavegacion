"""
Backend abstracto de camara para tracker.py (camera/backend.py; era
iter4/camera_backend.py hasta la meta 003, fase 3).

Interfaz comun para el tracker; configurable por el perfil: camera_type. Desde
la meta 003, fase 3 (ADR-025, ADR-027) solo hay WebcamBackend (las SVPRO gs1 y
gs2); FemtoBoltBackend esta archivado en codigo/historico/iter4/femto/ y
`camera_type: femtobolt` aborta diciendolo.

Interfaz comun:
  - open():        abre la camara, hace warmup, carga calibracion intrinseca.
  - read():        devuelve (rgb_bgr, depth_mm_or_None, timestamp).
  - get_intrinsics(): K (3x3) + dist (5,) del color stream.
  - close():       libera recursos.

Tambien soporta context manager: `with create_backend(cfg) as cam: ...`.

Meta 002, fase 2b (2026-10-21): WebcamBackend identifica la camara por la
ruta fisica de su puerto USB (`usb_port_windows`, camaras_uvc), comprueba la
marca (`marca`, un control que no cambia la imagen y persiste en la camara:
delata un intercambio de camaras entre puertos), aplica los ajustes del perfil
(`controls`, ajustes_camara: DSHOW en una apertura corta ANTES del video por
MSMF) y, tras el warmup, para si el frame no tiene el tamano pedido o el del
`.yml` (principio 7). Sin esas tres claves hace las mismas llamadas a cv2 que
antes. FemtoBoltBackend, read() y get_intrinsics() no cambian.

Context7 (2026-10-21, OpenCV 4.13; instalado 4.11): VideoCapture.get(
CAP_PROP_FRAME_WIDTH/HEIGHT) y FileNode.empty()/real() para leer
image_width/image_height del .yml. El tamano real se toma del frame, no de
get(): por MSMF get(CAP_PROP_FOURCC) no es fiable (B26) y el frame es lo que
ve el detector.

Correccion de la fase 2b (2026-10-22): este modulo importa camaras_uvc antes
que nada, y camaras_uvc apaga la aceleracion por hardware de MSMF
(OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0, setdefault, solo Windows): la
apertura baja de 43-51 s a 3.6-4.0 s sin cambiar los fps. cv2 solo la ve si se
puso antes de cargarse (CRT estatico, ver camaras_uvc), asi que los scripts que
importan cv2 antes que este modulo la ponen ellos (import camaras_uvc antes de
cv2) o la heredan del entorno (el panel la pone a sus procesos). open() dice en
una linea si esta apagada o encendida.

Linux (meta 007 · El tracker en la Jetson Orin Nano, fase 5 · La capa V4L2 y cada
camara en la Jetson; ADR J1): `WebcamBackend(..., usb_port_linux=..., plataforma=...)`.
Fuera de Windows la identidad es `usb_port_linux` (el nombre bajo /dev/v4l/by-path),
la camara se lista y se resuelve con `camera.v4l2`, la marca y los `controls` van por
`CapaLinuxV4L2` (v4l2-ctl) y el video se abre con `cv2.VideoCapture(<dispositivo>,
cv2.CAP_V4L2)`, sea lo que diga `backend` en el perfil (MSMF solo existe en Windows).
Lo demas (FOURCC, tamano, fps, warmup, tamano real contra el perfil y el .yml, la
calibracion) son las mismas llamadas a cv2. En Windows nada cambia: `plataforma` es
`sys.platform` y `usb_port_linux` se ignora.
"""
from abc import ABC, abstractmethod
import sys
import time

from camera import uvc as camaras_uvc   # primero: apaga la aceleracion HW de MSMF antes de que se cargue cv2
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

def leer_tamano_yml(ruta):
    """(image_width, image_height) del .yml de intrinsecos, o None si no los trae.

    FileNotFoundError si el archivo no abre (mismo mensaje que _load_calibration).
    """
    import cv2
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"No se pudo abrir {ruta}")
    try:
        w = fs.getNode("image_width")
        h = fs.getNode("image_height")
        if w.empty() or h.empty():
            return None
        return int(w.real()), int(h.real())
    finally:
        fs.release()


class WebcamBackend(CameraBackend):
    """Wrap del cv2.VideoCapture clasico. Solo RGB (sin depth).

    Fase 2b: `usb_port_windows` (ruta fisica del puerto, p. ej.
    `PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(3)`) identifica la camara;
    `controls` (formato de ajustes_camara) se aplica por la capa del sistema
    antes de abrir el video; `marca` ({control: valor}) se lee antes de
    escribir nada y para si no es la declarada. `abrir`, `listar` y `capa`
    son inyectables para las pruebas sin camara: abrir(indice, backend_cv2)
    da un VideoCapture; listar() da las camaras (camaras_uvc.CamaraUVC, o
    camera.v4l2.CamaraV4L2 en Linux); capa es un ajustes_camara.CapaAjustes.

    Meta 007, fase 5: `usb_port_linux` (nombre by-path) es la identidad fuera de
    Windows y `plataforma` (por defecto `sys.platform`) elige la rama; `puerto` y
    `clave_puerto` son la identidad de la plataforma en uso.
    """

    def __init__(self, source=None, width=640, height=480, fps=30,
                 backend="MSMF", fourcc="MJPG", calibration_file=None,
                 controls=None, usb_port_windows=None, marca=None, usb_port_linux=None,
                 *, plataforma=sys.platform, abrir=None, listar=None, capa=None):
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        self.backend_name = backend
        self.fourcc = fourcc
        self.calibration_file = calibration_file
        self.plataforma = str(plataforma)
        self.linux = self.plataforma.startswith("linux")
        self.usb_port_windows = str(usb_port_windows).strip() if usb_port_windows else None
        self.usb_port_linux = str(usb_port_linux).strip() if usb_port_linux else None
        # La identidad de esta plataforma (fase 5 de la meta 007): en Linux, by-path.
        self.clave_puerto = "usb_port_linux" if self.linux else "usb_port_windows"
        self.puerto = self.usb_port_linux if self.linux else self.usb_port_windows
        self.controls = self._validar_controles(controls)
        self.marca = self._validar_marca(marca)
        self._abrir = abrir
        self._listar = listar
        self._capa = capa
        self.cap = None
        self.indice = None            # indice resuelto al abrir (en Linux, el /dev/videoN)
        self.ajustes_leidos = None    # lo que la capa leyo de la camara (fase 2b)
        self.tamano_real = None       # (w, h) del frame tras el warmup
        self._K = None
        self._dist = None
        if self.source is None and self.puerto is None:
            raise ValueError(f"[Webcam] el perfil no trae ni {self.clave_puerto} ni source: "
                             f"no se sabe que camara abrir")
        if self.puerto and not self.linux and self.backend_name.upper() not in ("MSMF", "DSHOW"):
            raise ValueError(f"[Webcam] con usb_port_windows el backend tiene que ser MSMF "
                             f"o DSHOW (el indice se resuelve por su enumeracion), "
                             f"no {self.backend_name!r}")

    # ---- validacion del perfil (sin camara) -------------------------------

    def _validar_controles(self, controls):
        if not controls:
            return None
        from camera.controls import validar_controles
        validos = validar_controles(controls)
        if not self.puerto:
            raise ValueError(f"[Webcam] camera.controls exige {self.clave_puerto}: la capa de "
                             f"ajustes abre la camara por su puerto")
        return validos

    def _validar_marca(self, marca):
        if not marca:
            return None
        from camera.controls import CONTROLES_CV2
        if not isinstance(marca, dict):
            raise ValueError(f"[Webcam] camera.marca tiene que ser un dict, no "
                             f"{type(marca).__name__}")
        problemas = []
        salida = {}
        for nombre, valor in marca.items():
            if nombre not in CONTROLES_CV2 or nombre == "exposure_ms":
                problemas.append(f"'{nombre}' no sirve de marca; validos: "
                                 f"{[n for n in CONTROLES_CV2 if n != 'exposure_ms']}")
            elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
                problemas.append(f"'{nombre}' tiene que ser un numero, no {valor!r}")
            elif self.controls and nombre in self.controls:
                problemas.append(f"'{nombre}' esta en controls y en marca: la marca no se "
                                 f"escribe, solo se lee (quitalo de controls)")
            else:
                salida[nombre] = float(valor)
        if problemas:
            raise ValueError("[Webcam] camera.marca: " + "; ".join(problemas))
        if not self.puerto:
            raise ValueError(f"[Webcam] camera.marca exige {self.clave_puerto}: se lee por el "
                             f"puerto antes de abrir el video")
        return salida

    # ---- identidad, ajustes y tamano -------------------------------------

    def _listar_camaras(self):
        if self._listar is not None:
            return self._listar()
        if self.linux:
            from camera import v4l2
            return v4l2.listar_camaras_v4l2()
        from camera import uvc as camaras_uvc
        if self.backend_name.upper() == "DSHOW":
            return camaras_uvc.listar_camaras_dshow()
        return camaras_uvc.listar_camaras_msmf()

    def _resolver_source(self):
        """Lo que se abre: por el puerto si el perfil lo trae (en Windows el indice MSMF o
        DSHOW; en Linux el /dev/videoN del enlace by-path); si no, source."""
        if self.puerto is None:
            return int(self.source)
        t0 = time.time()
        camaras = self._listar_camaras()
        if self.linux:
            from camera import v4l2
            dispositivo = v4l2.resolver_dispositivo(self.puerto, camaras)
            print(f"[Webcam] Puerto {self.puerto} -> {dispositivo} (V4L2, {time.time()-t0:.2f}s)")
            if self.source is not None and str(self.source) not in (dispositivo, dispositivo[len("/dev/video"):]):
                raise RuntimeError(f"[Webcam] el perfil dice source={self.source} pero la camara "
                                   f"del puerto {self.puerto} es {dispositivo}: quita source del "
                                   f"perfil o corrigelo")
            return dispositivo
        from camera import uvc as camaras_uvc
        indice = camaras_uvc.resolver_indice(self.puerto, camaras)
        print(f"[Webcam] Puerto {self.puerto} -> indice {self.backend_name} "
              f"{indice} ({time.time()-t0:.2f}s)")
        if self.source is not None and int(self.source) != indice:
            raise RuntimeError(f"[Webcam] el perfil dice source={self.source} pero la camara "
                               f"del puerto {self.puerto} es el indice {indice}: "
                               f"quita source del perfil o corrigelo")
        return indice

    def _capa_ajustes(self):
        if self._capa is None:
            from camera.controls import capa_para_plataforma
            self._capa = capa_para_plataforma(self.plataforma)
        return self._capa

    def _comprobar_marca(self):
        """La marca leida por la capa (sin escribir nada) debe ser la declarada."""
        if not self.marca:
            return
        t0 = time.time()
        leidos = self._capa_ajustes().leer(self.puerto, list(self.marca))
        difs = [f"{n}: declarado {v:g}, leido {leidos.get(n)}" for n, v in self.marca.items()
                if leidos.get(n) is None or abs(float(leidos[n]) - v) > 1e-3]
        if difs:
            raise RuntimeError(f"[Webcam] la camara del puerto {self.puerto} no es "
                               f"la del perfil ({'; '.join(difs)}): se intercambiaron las "
                               f"camaras de puerto? No se escribe ningun ajuste.")
        print(f"[Webcam] Marca comprobada ({', '.join(f'{n}={v:g}' for n, v in self.marca.items())}) "
              f"en {time.time()-t0:.2f}s")

    def _aplicar_controles(self):
        """Aplica `controls` por la capa del sistema y deja lo leido en ajustes_leidos."""
        if not self.controls:
            return None
        t0 = time.time()
        r = self._capa_ajustes().aplicar(self.puerto, self.controls)
        self.ajustes_leidos = r["leidos"]
        print(f"[Webcam] Ajustes aplicados en {time.time()-t0:.2f}s "
              f"(escritos: {r.get('escritos') or 'ninguno'}): {self.ajustes_leidos}")
        return r

    def _comprobar_tamano(self, frame):
        """El frame real contra el modo pedido y contra el .yml (RuntimeError si difieren)."""
        if frame is None:
            raise RuntimeError(f"[Webcam] la camara no entrego ningun frame en el warmup: "
                               f"no se puede comprobar el tamano (modo pedido "
                               f"{self.width}x{self.height} {self.fourcc} @ {self.fps})")
        h, w = frame.shape[:2]
        self.tamano_real = (int(w), int(h))
        if (w, h) != (int(self.width), int(self.height)):
            raise RuntimeError(f"[Webcam] el frame real es {w}x{h} y el perfil pide "
                               f"{self.width}x{self.height}: ese modo no lo entrega la "
                               f"camara (B26); corrige width/height del perfil")
        if self.calibration_file:
            esperado = leer_tamano_yml(self.calibration_file)
            if esperado is None:
                print(f"[Webcam] AVISO: {self.calibration_file} no declara image_width/"
                      f"image_height; no se puede comprobar contra el frame ({w}x{h})")
            elif esperado != (w, h):
                raise RuntimeError(f"[Webcam] el frame real es {w}x{h} y el .yml "
                                   f"{self.calibration_file} es de {esperado[0]}x{esperado[1]}: "
                                   f"los intrinsecos no valen para este modo")
        print(f"[Webcam] Tamano real {w}x{h}: coincide con el perfil"
              + (" y con el .yml" if self.calibration_file else ""))

    def open(self):
        import cv2
        backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "ANY": cv2.CAP_ANY}
        # Linux (meta 007, fase 5): siempre V4L2, diga lo que diga el perfil (ADR J1).
        backend = cv2.CAP_V4L2 if self.linux else backends.get(self.backend_name.upper(), cv2.CAP_MSMF)
        nombre_backend = "V4L2" if self.linux else self.backend_name
        abrir = self._abrir if self._abrir is not None else \
            (lambda i, b: cv2.VideoCapture(i if isinstance(i, str) else int(i), b))

        # Fase 2b: identidad, marca y ajustes ANTES de abrir el video por MSMF.
        self.indice = self._resolver_source()
        self._comprobar_marca()
        self._aplicar_controles()

        if self.linux:
            if self.backend_name.upper() != "V4L2":
                print(f"[Webcam] Linux: backend V4L2 (el perfil dice {self.backend_name}, "
                      f"que solo existe en Windows)")
        elif self.backend_name.upper() in ("MSMF", "ANY"):
            print(f"[Webcam] {camaras_uvc.describir_aceleracion_msmf()}")
        print(f"[Webcam] Abriendo source={self.indice} backend={nombre_backend}...")
        t0 = time.time()
        self.cap = abrir(self.indice, backend)
        try:
            if not self.cap.isOpened():
                raise RuntimeError(f"No se pudo abrir webcam source={self.indice}")
            print(f"[Webcam] Abierta en {time.time()-t0:.1f}s")

            if self.fourcc:
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.fourcc))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            print(f"[Webcam] Warmup (descartando 5 frames)...")
            frame = None
            for _ in range(5):
                ret, f = self.cap.read()
                if ret and f is not None:
                    frame = f
            self._comprobar_tamano(frame)
            print(f"[Webcam] Lista para capturar.")

            if self.calibration_file:
                self._load_calibration()
        except BaseException:
            self.close()      # principio 9: la camara no queda tomada si open() falla
            raise

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
        # Fase 2b: `source` es opcional si el perfil trae `usb_port_windows`;
        # `controls` y `marca` solo cuando estan (el backend valida al construir).
        # Meta 007, fase 5: `usb_port_linux` es la identidad fuera de Windows.
        return WebcamBackend(
            source=cfg_camera.get("source"),
            width=cfg_camera["width"],
            height=cfg_camera["height"],
            fps=cfg_camera.get("fps", 30),
            backend=cfg_camera.get("backend", "MSMF"),
            fourcc=cfg_camera.get("fourcc", "MJPG"),
            calibration_file=cfg_camera.get("calibration_file"),
            controls=cfg_camera.get("controls"),
            usb_port_windows=cfg_camera.get("usb_port_windows"),
            marca=cfg_camera.get("marca"),
            usb_port_linux=cfg_camera.get("usb_port_linux"),
        )
    elif camera_type == "femtobolt":
        # Meta 003, fase 3 (ADR-025, ADR-027): solo valen las SVPRO gs1 y gs2.
        raise ValueError("camera_type 'femtobolt': el backend de la Femto Bolt esta archivado "
                         "en codigo/historico/iter4/femto/femto_backend.py (ADR-025); "
                         "usa un perfil webcam (profiles/tracker_config_gs1.yaml o _gs2.yaml)")
    else:
        raise ValueError(f"camera_type desconocido: {camera_type}. "
                         f"Opcion: 'webcam' (la Femto Bolt esta archivada)")
