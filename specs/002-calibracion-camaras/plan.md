# Plan — Meta 002 · Calibración de las cámaras global shutter

Escrito por el agente de planificación con `/planear 002-calibracion-camaras` el 2026-10-20. Sin código. Lo que el autor autoriza es este archivo.
Revisión 1 (2026-10-20): ajustado a las respuestas P1–P8 de `clarify.md` y a `Claude outputs/planes/002/cambios_1.md`. Solo valen los perfiles nuevos: los anteriores no se adaptan; la Femto sale de las sesiones en vivo; la cadena en vivo llega hasta los dos transforms en Slicer, sin punta ni Observer; optimizar el tracker va al BACKLOG sin condición; luz en nivel 2; consultas a Context7 de cada API propuesta.

## Lo leído

- HEAD: `709a535 Anota las pruebas de la cámara 1`. Árbol con `.claude/agents/*.md` y `memory.md` modificados y `specs/002-calibracion-camaras/` sin seguimiento.
- `docs/constitution.md`, `memory.md`, `docs/CONTEXT.md` (completo; trampas §4.1–4.17), `specs/002-calibracion-camaras/spec.md`, `clarify.md` (P1–P8 respondidas) y la plantilla de `specs/_plantilla/`.
- `docs/PRUEBAS.md` P02 (cámara 1: cadena pasa; calibración no concluyente; 25.7 fps; sd z 1.38 mm a ~45 cm; hallazgos 1–6). `docs/BACKLOG.md` B10. `docs/DECISIONS.md` ADR-016 y el índice (último: ADR-021). `docs/ARCHITECTURE.md` §3.1–3.4.
- Código: `iter4/camera_backend.py` (completo), `iter4/calibrar_camara.py` (completo; usa `findChessboardCorners` + `cornerSubPix` y `calibrateCamera`), `iter4/tracker.py` (carga, detector `ArucoDetector`, `solvePnP`/`solvePnPGeneric`/`solvePnPRefineLM`, bucle principal, envío por `pyigtl`), `iter4/tracker_config_doctor.yaml`, `iter4/data/globalshutter.yml`, `iter4/gui/sonda_camara.py`, `iter4/gui/estado.py` (`listar_perfiles`, `chequear_intrinsecos`, `PUNTAS_PREFERIDAS`), `iter4/gui/recetas.py` (`SLUGS`, `receta_calibrar_camara`), `iter4/gui/panel.py` (`DialogoCalibrarCamara`), `iter4/gui/perfil_editor.py` (exige una sola línea `calibration_file:`), `tests/test_compilan.py`, `tests/test_gui_headless.py`, `tests/test_replay.py`, `tests/replay_util.py`, `.gitignore`.
- Grep de los perfiles viejos: ninguna prueba nombra `tracker_config_doctor.yaml` ni `globalshutter.yml`; `tracker_config.yaml` (Femto) sí: `test_replay.py`, `replay_util.py`, `tests/data/replay_v2_femto_referencia.json` y el `--selftest` del panel. En código, el doctor aparece en `recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS`, el `--config` por defecto de `calibrar_camara.py` y docstrings. `iter4/data/historico/` ya guarda perfiles archivados (`tracker_config_webcam.yaml`).
- Fuera de git: `Claude outputs/pruebas/camara-1/` (números del autor, perfiles por índice, `scripts/analizar_log_tracker.py`), `Claude outputs/tablero/` (STL 9×6 y 2×2) y `Claude outputs/planes/002/cambios_1.md`.

### Context7 (solo API; regla del autor)

- **OpenCV 4.13 `VideoCapture`** (`/websites/opencv_4_13_0`): la lista de `CAP_PROP_*` (`EXPOSURE`, `AUTO_EXPOSURE`, `GAIN`, `AUTO_WB`, `WB_TEMPERATURE`, `BRIGHTNESS`, `CONTRAST`, `SATURATION`, `SHARPNESS`, `GAMMA`, `BACKLIGHT`, `FOCUS`, `FOURCC`, `FRAME_WIDTH/HEIGHT`, `FPS`, `BUFFERSIZE`, `BACKEND`) es genérica: «only for those cameras that support». `AUTO_EXPOSURE` solo está documentada para DC1394: qué valores acepta por MSMF o DSHOW no está escrito, se mide en la fase 1. `CAP_PROP_SETTINGS` (diálogo del driver) solo con DSHOW. DirectShow está «deprecated in favor of MSMF»: el plan usa MSMF y DSHOW solo si la sonda mide que fija controles que MSMF no. Python admite `cv2.VideoCapture(index, apiPreference, params)`; se mantiene `set()` tras abrir, como hoy, y se lee de vuelta.
- **Media Foundation** (`/microsoft/media-foundation`): Context7 solo trae las muestras de MediaEngine y SourceReader; no documenta `MFEnumDeviceSources`, `MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID`, `MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK` ni `IMFActivate::GetAllocatedString`. La capa `ctypes` de `camaras_uvc.py` no queda contrastada por Context7: la fase 1 copia GUIDs y orden de la vtable de los encabezados del Windows SDK (`mfidl.h`, `mfobjects.h`, `mfapi.h`) citándolos en el código, y la verifica en vivo (orden igual al índice de OpenCV, abriendo cada índice).
- **`calibrateCameraExtended`** (OpenCV 4.13): en Python devuelve `retval, cameraMatrix, distCoeffs, rvecs, tvecs, stdDeviationsIntrinsics, stdDeviationsExtrinsics, perViewErrors`; `retval` es el RMS global. Confirma las firmas de `calibrar` de abajo.
- **`findChessboardCornersSB`**: según la documentación da esquinas subpíxel más exactas que `findChessboardCorners` + `cornerSubPix` y es más robusto al ruido. Se añade como opción y se compara en la fase 4 con las mismas vistas guardadas.
- **ArUco** (`ArucoDetector.detectMarkers`, `DetectorParameters`, `solvePnP` con `SOLVEPNP_IPPE_SQUARE`/`IPPE`): coincide con lo que usa `tracker.py`. El plan no propone API ArUco nueva: `medir_modos.py` importa las funciones del tracker.

### Lo que sale de leer

- `WebcamBackend.open()` pide FOURCC, ancho, alto y FPS, pero no lee qué obtuvo ni toca ningún control; carga K sin mirar `image_width`/`image_height` (P02, hallazgo 1). Es el único punto por el que abren la cámara `tracker.py`, `identificar_ids.py`, `captura_calibracion.py`, `calibrar_tip_divot.py` y `calibrar_camara.py`: la comprobación del tamaño y los ajustes van ahí y cubren a todos.
- `calibrar_camara.py` abre la cámara con el `calibration_file` del perfil y su `--config` por defecto es el perfil doctor. Con la comprobación del tamaño, calibrar a una resolución nueva pararía: el script tiene que abrir sin calibración, y `--config` pasa a obligatorio (principio 7).
- `calibrar_camara.py` trae `--square-mm 25.0` por defecto (el nominal) y el diálogo del panel solo admite un decimal: los dos contradicen «el medido, no el nominal».
- La instancia de la cámara 1 en P02 fue `USB\VID_32E4&PID_0234&MI_00\6&325DB0BA&1&0000`: sin número de serie, Windows la nombra por el puerto USB. Por P1, cada cámara va siempre a su puerto, etiquetado.
- `tracker.py` con `verbose: true` imprime una línea por frame; la medición de la fase 3 mide sin esa impresión y lo dice.
- El temblor de P02 se midió sobre la posición que imprime el tracker, tras el filtro 1-Euro. La fase 6 lo mide igual, con el mismo script.
- `estado.listar_perfiles()` toma todo `iter4/tracker_config*.yaml`: los perfiles nuevos aparecen solos en el panel.

## Archivos

Se crean:
- `codigo/iter4/camaras_uvc.py` (fase 1): enumera las cámaras de vídeo de Media Foundation en el orden que usa OpenCV con MSMF, con nombre y enlace simbólico (VID, PID e instancia), por `ctypes` sobre `mfplat`/`mf`/`ole32`, sin dependencia nueva (P1).
- `codigo/iter4/sondear_camara.py` (fase 1): sonda de una cámara: identidad, controles (se aceptan, se leen de vuelta, persisten) y modos (lo pedido frente al tamaño real del frame y los FPS de captura).
- `codigo/iter4/tracker_config_gs1.yaml` y `codigo/iter4/tracker_config_gs2.yaml` (fase 2): un perfil por cámara física (gs1 = la del puerto etiquetado 1; gs2 = la del 2), sin nada del perfil doctor: se escriben con la geometría del dodecaedro y los parámetros del detector que valieron en P02 (`Claude outputs/pruebas/camara-1/perfiles/`), Marker0 de 80 mm medido con calibrador (P3), `device_id`, `controls` y una sola línea `calibration_file:` (vacía hasta las fases 4 y 5). La resolución se fija en la fase 3.
- `codigo/iter4/medir_modos.py` (fase 3): recorre resolución × formato × backend y mide FPS de captura, FPS de tracking (con y sin ventana) y markers por vista; escribe un JSON y una tabla en Markdown.
- `codigo/iter4/comprobar_escala.py` (fase 4): comprobación de escala por desplazamiento conocido del tablero contra una regla.
- `codigo/iter4/data/intrinsecos_gs1_<W>x<H>.yml` (fase 4) y `codigo/iter4/data/intrinsecos_gs2_<W>x<H>.yml` (fase 5). Se versionan, como los perfiles (P4).
- Pruebas sin cámara: `codigo/tests/test_camaras_uvc.py` (fase 1), `codigo/tests/test_camera_backend.py` (fase 2), `codigo/tests/test_medir_modos.py` (fase 3), `codigo/tests/test_calibrar_camara.py` (fase 4).
- Fuera de git: `Claude outputs/camaras/` (JSON y tablas de la sonda y de la medición, vistas del tablero guardadas, logs del tracker) y los reportes de fase en `Claude outputs/fases/002/`.

Se modifican:
- `codigo/iter4/camera_backend.py` (fase 2): solo `WebcamBackend` y `create_backend`. Ajustes del perfil aplicados y leídos de vuelta, resolución de `device_id` a índice, lectura del modo obtenido y comprobación del tamaño del frame contra el `.yml`. `FemtoBoltBackend` no se toca.
- `codigo/iter4/gui/sonda_camara.py` (fase 2): «Probar cámara» abre con el modo del perfil y dice el tamaño real frente al del perfil y al del `.yml` (P02 hallazgo 5).
- `codigo/iter4/calibrar_camara.py` (fase 4): `--config` y `--square-mm` obligatorios, abre sin calibración, detector de esquinas a elegir (clásico o SB), guarda las vistas, errores por vista, vistas de control, cobertura y desviación de los intrínsecos; el `.yml` registra la cámara, el modo, los ajustes y el tamaño de casilla medido.
- `codigo/iter4/gui/panel.py` (fase 4): `DialogoCalibrarCamara` con dos decimales en el lado de la casilla y la nota «medido con calibrador»; el criterio de la nota pasa a 0.5 px. `gui/recetas.py` (fase 4): `receta_calibrar_camara` ya pasa `--config`; su `square_mm=25.0` por defecto (el nominal) pasa a obligatorio, como en el script.
- Los perfiles `tracker_config_gs1.yaml`/`gs2.yaml` (fases 3, 4 y 5): modo elegido y `calibration_file`.

Se mueven (fase 6, con `git mv`; ver la fase):
- `codigo/iter4/tracker_config_doctor.yaml` → `codigo/iter4/data/historico/tracker_config_doctor.yaml`.
- `codigo/iter4/data/globalshutter.yml` → `codigo/iter4/data/historico/globalshutter.yml`.

No se tocan: `tracker.py`, el envío por `pyigtl`, `FemtoBoltBackend`, `tracker_config.yaml` (Femto: lo usan el replay y el selftest, que son la línea base del «no cambió»), los scripts de Slicer, la punta y la geometría. Tampoco se adaptan `recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS` ni el runbook a gs1/gs2: se rehará con la punta (BACKLOG).

## Funciones y clases

`iter4/camaras_uvc.py` (fase 1):
- `@dataclass CamaraUVC(indice: int, nombre: str, enlace: str, vid: str | None, pid: str | None, instancia: str | None)`: una cámara tal como la enumera Media Foundation.
- `listar_camaras_msmf() -> list[CamaraUVC]`: `CoInitializeEx` + `MFStartup`, `MFCreateAttributes` con `MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE` = `VIDCAP_GUID`, `MFEnumDeviceSources`, y por cada `IMFActivate` `GetAllocatedString` del nombre y del enlace simbólico; libera y `MFShutdown`. Mismo orden que el índice de `cv2.CAP_MSMF` (se verifica en vivo). Falla fuerte si COM o MF no inicializan.
- `extraer_ids(enlace: str) -> tuple[str | None, str | None, str | None]`: VID, PID e instancia desde el enlace simbólico; pura, con prueba.
- `resolver_indice(device_id: str, camaras: list[CamaraUVC]) -> int`: el índice cuya instancia contiene `device_id`; `ValueError` si hay 0 o más de 1.

`iter4/sondear_camara.py` (fase 1):
- `CONTROLES: dict[str, int]`: nombre del perfil → propiedad de `cv2` (`exposure`, `auto_exposure`, `gain`, `auto_wb`, `wb_temperature`, `brightness`, `contrast`, `saturation`, `sharpness`, `gamma`, `backlight`, `focus`).
- `sondear_controles(cap, nombres: list[str]) -> list[dict]`: por control, valor leído, si `set` lo acepta (prueba con valor ± paso y vuelve al original) y si la lectura de vuelta coincide.
- `sondear_modos(source: int, backend: str, modos: list[tuple[int, int, str]], segundos: float) -> list[dict]`: por modo, lo pedido, lo que reporta `get`, el tamaño real del primer frame y los FPS de captura sola.
- `main(argv: list[str] | None = None) -> int`: `--source`, `--backend`, `--modos`, `--salida` (JSON), `--timeout`, todos explícitos.

`iter4/camera_backend.py` (fase 2):
- `WebcamBackend.__init__(self, source=0, width=640, height=480, fps=30, backend="MSMF", fourcc="MJPG", calibration_file=None, controls: dict | None = None, device_id: str | None = None)`: dos parámetros nuevos con `None` por defecto; sin ellos, el backend hace lo mismo que hoy.
- `WebcamBackend._resolver_source(self) -> int`: si hay `device_id`, el índice por `camaras_uvc.resolver_indice` (si el perfil también trae `source` y no coinciden, para); si no, `source`.
- `WebcamBackend._aplicar_controles(self) -> dict[str, tuple[float, float]]`: aplica cada control declarado y lo lee de vuelta; para con la lista si alguno no se acepta o no coincide. Deja lo leído en `self.ajustes_leidos` y lo imprime.
- `comparar_controles(declarados: dict, leidos: dict, tolerancia: float = 1e-6) -> list[str]`: los que no coinciden; pura, con prueba.
- `leer_tamano_yml(ruta) -> tuple[int, int] | None`: `image_width`/`image_height` del `.yml`.
- `WebcamBackend._comprobar_tamano(self, frame) -> None`: tras el warmup, compara el frame real con el modo pedido y con el `.yml`; si el `.yml` no coincide, `RuntimeError` con los dos tamaños (para; principio 7). Si el `.yml` no declara tamaño, aviso.
- `create_backend(cfg_camera)`: pasa `controls` y `device_id` cuando están.

`iter4/medir_modos.py` (fase 3):
- `medir_captura(cap, segundos: float) -> dict`: frames, FPS, tamaño real.
- `medir_tracking(cap, cfg: dict, segundos: float, ventana: bool) -> dict`: por frame, lo mismo que `tracker.main()` sin enviar (gris, detección, lista blanca, `tracker.estimar_pose_rigid_body`, 1-Euro), con las funciones de `tracker.py` importadas, sin copiarlas; FPS, mediana de markers del dodecaedro por vista y fracción de frames con pose. Con `ventana=True` suma `imshow` + `waitKey(1)` como el tracker (la cifra que cuenta, P2).
- `elegir_resolucion(filas_gs1: list[dict], filas_gs2: list[dict], fps_min: float = 60.0) -> dict | None`: la de más píxeles con FPS de tracking con ventana ≥ `fps_min` en las dos cámaras (P8).
- `tabla_markdown(filas: list[dict]) -> str`.
- `main(argv=None) -> int`: `--config`, `--modos`, `--backends`, `--segundos-captura`, `--segundos-tracking`, `--luz` (texto obligatorio: nivel de la caja y luz de la sala), `--salida`, `--timeout`.

`iter4/calibrar_camara.py` (fase 4):
- `detectar_esquinas(gray, cols: int, rows: int, metodo: str) -> np.ndarray | None`: `"clasico"` (`findChessboardCorners` + `cornerSubPix`, lo de hoy) o `"sb"` (`findChessboardCornersSB`).
- `calibrar(obj_points, img_points, shape, n_control: int, semilla: int) -> dict`: aparta `n_control` vistas, calibra con el resto (`cv2.calibrateCameraExtended`), devuelve K, dist, RMS, error por vista (`perViewErrors`), RMS de las vistas de control y desviación de fx, fy, cx, cy (`stdDeviationsIntrinsics`).
- `rms_control(obj_points, img_points, K, dist) -> float`: `solvePnP` por vista de control y su RMS de reproyección.
- `cobertura(img_points, shape, celdas: tuple[int, int] = (4, 3)) -> float`: fracción de celdas de la imagen con esquinas.
- `cargar_vistas(dir) -> list[np.ndarray]` y `--desde-vistas DIR`: recalibrar sin cámara a partir de las imágenes guardadas.
- `guardar_yml(output_path, K, dist, width, height, rmse, n_vistas, cols, rows, square_mm, extra: dict)`: `extra` añade `rms_control_px`, `cobertura`, `std_intrinsecos`, `detector`, `device_id`, modo, backend, ajustes leídos y las medidas del calibrador.

`iter4/comprobar_escala.py` (fase 4):
- `pose_tablero(gray, cols: int, rows: int, square_mm: float, K, dist) -> tuple[np.ndarray, np.ndarray] | None`.
- `errores_escala(tvecs: list[np.ndarray], desplazamientos_mm: list[float]) -> list[float]`: distancia medida por la cámara entre posiciones menos la de la regla; pura, con prueba.
- `main(argv=None) -> int`: `--config`, `--cols`, `--rows`, `--square-mm`, `--desplazamientos-mm`, `--frames-por-posicion`, `--timeout`.

## Fases

Comunes a todas: la suite en verde con su tiempo; las 100 pruebas de la línea base siguen igual (78 pasan, 22 `xfail`) y las nuevas pasan (cada `.py` nuevo de `iter4/` suma una prueba de `test_compilan.py`); replay 0.0 mm / 0.0°; `panel.py --selftest` rc 0 con `tracker_config.yaml`. Ese es el «no cambió» de la Femto: suite, replay y selftest, sin cámara; no hay sesión en vivo con la Femto en esta meta. Tras cada `.py` editado, `py_compile` y conteo de líneas. Toda corrida con cámara lleva `--timeout` y libera la cámara (principio 9). Luz de todas las sesiones con cámara: la caja en **nivel 2** (P7), con la luz de la sala como el autor diga; cada medición lo anota en `--luz` o en el reporte.

### Fase 1 · Sonda de controles, modos e identidad (sin tocar el backend)

- **Entrega:** `camaras_uvc.py`, `sondear_camara.py`, `test_camaras_uvc.py` (enlaces simbólicos de ejemplo, sin cámara). Una sesión en vivo con el autor, primero la cámara 1 sola, luego la 2 sola, luego las dos.
- **El autor, en vivo:** etiqueta los dos puertos USB y conecta cada cámara al suyo; anota los modos que lista AMCap (para `--modos`); corre la sonda por MSMF y por DSHOW; cambia un control con AMCap, desenchufa y vuelve a enchufar, y corre la sonda otra vez (persistencia); con las dos conectadas, las intercambia de puerto una vez y las devuelve.
- **Criterio:** por cada cámara y backend, una tabla de controles con «se acepta / se lee de vuelta / persiste tras desenchufar» para los 12 de `CONTROLES`; la lista de modos con el tamaño real; y la identidad: si las dos dan instancias distintas y estables en su puerto (sí/no), si alguna trae número de serie (sí/no), si el intercambio de puerto intercambia las instancias (sí/no) y si el orden de `listar_camaras_msmf()` coincide con el índice de OpenCV (sí/no, abriendo cada índice). Con eso se fija el `device_id` de cada perfil y qué controles van al perfil.
- **Cadena:** no se toca.

### Fase 2 · Ajustes fijos, identidad y comprobación del tamaño al abrir

- **Entrega:** los cambios de `camera_backend.py` y `sonda_camara.py`; los perfiles `tracker_config_gs1.yaml` y `tracker_config_gs2.yaml` con `device_id` y `controls` (solo los que la fase 1 midió como aceptados), modo provisional 640×480 MJPG MSMF y `calibration_file` vacío; `test_camera_backend.py` con un `VideoCapture` falso (controles que coinciden, que no se aceptan, que no coinciden; tamaño del frame igual y distinto del `.yml`; `.yml` sin tamaño; `device_id` con 0, 1 y 2 coincidencias; sin `controls` ni `device_id`, las mismas llamadas a `cv2` que hoy).
- **Criterio sin cámara:** las pruebas nuevas pasan; `create_backend` con la sección `camera` de `tracker_config.yaml` construye lo mismo que hoy (prueba); suite, replay y selftest como la línea base.
- **Criterio en vivo, por cámara:** dos aperturas seguidas con su perfil dan los mismos valores leídos en todos los controles declarados (0 diferencias); una copia temporal del perfil (en `Claude outputs/camaras/`, fuera de `iter4/`) con un `.yml` de otro tamaño hace parar al abrir con el mensaje de los dos tamaños; «Probar cámara» del panel dice el tamaño real; con las dos cámaras conectadas, cada perfil abre la suya (se comprueba tapando una lente).
- **Cadena (principio 6):** `tracker.py` no cambia; el diff de `camera_backend.py` no toca `FemtoBoltBackend` ni la interfaz `read()`/`get_intrinsics()`; suite, replay 0.0 mm / 0.0° y selftest. Sin sesión con Slicer en esta fase: los perfiles nuevos aún no tienen intrínsecos; la verificación en vivo de la cadena es la de la fase 6.

### Fase 3 · Enfoque y medición de resolución × formato

- **Entrega:** `medir_modos.py` y `test_medir_modos.py` (elección de resolución con dos cámaras y tabla, con filas sintéticas). Sesión en vivo por cámara.
- **El autor, en vivo:** enfoca la lente a 50–70 cm con el tablero a 60 cm y la mira de nitidez del script (varianza del laplaciano sobre el tablero, en pantalla) y fija la rosca; pone el dodecaedro quieto a ~60 cm; caja de luz en nivel 2.
- **Medición:** por cámara, cada modo de la fase 1 en MJPG y YUY2, por el backend que la fase 1 dio como bueno (y el otro si fija controles distintos): captura sola 10 s; tracking 30 s sin ventana y 30 s con ventana. Tope global por cámara: `--timeout 1500`. Es también la línea base de la optimización del tracker: captura y tracking por separado, con y sin ventana, guardada en `Claude outputs/camaras/`.
- **Criterio:** la tabla de cada cámara existe con, por modo, tamaño real, FPS de captura, FPS de tracking sin y con ventana, mediana de markers por vista y fracción con pose; la resolución elegida es la mayor con FPS de tracking con ventana ≥ 60 sostenidos 30 s en las dos cámaras (P2, P8). Si ninguna llega y alguna sí de captura, se reporta como hallazgo y el autor elige con la tabla. Los perfiles gs1/gs2 quedan con el modo elegido, el mismo en los dos.
- **Cadena:** no se toca (el script importa funciones de `tracker.py` sin modificarlo y no abre `pyigtl`).

### Fase 4 · Calibración de la cámara 1 y comprobación de escala

- **Entrega:** los cambios de `calibrar_camara.py`, del diálogo del panel y de la receta; `comprobar_escala.py`; `test_calibrar_camara.py` (vistas sintéticas proyectadas con una K conocida: `calibrar` la recupera con fx/fy dentro del 0.1 % y RMS < 0.05 px; `cobertura`; `errores_escala` con desplazamientos sintéticos); `intrinsecos_gs1_<W>x<H>.yml`; `tracker_config_gs1.yaml` apuntado a él.
- **El autor, en vivo:** mide la pieza 2×2 y luego el tablero con calibrador (al menos 5 medidas sobre casillas distintas, en mm con dos decimales) y las dicta; captura 20–30 vistas variadas (bordes y esquinas de la imagen, inclinaciones de hasta ~45°, 40–80 cm), con la caja en nivel 2; para la escala, apoya el tablero sobre una base rígida que desliza contra una regla y lo pone en 0, 100 y 200 mm.
- **Criterio:** el lado medido (media de ≥ 5 medidas, dos decimales) queda en `clarify.md` y en el `.yml`; RMS de reproyección ≤ 0.5 px con ≥ 15 vistas usadas, RMS de las 3 vistas de control ≤ 0.75 px y cobertura ≥ 0.8 de las celdas, a la resolución elegida; el `.yml` declara esa resolución y el backend lo acepta al abrir; escala: |error| ≤ 1.0 mm en cada desplazamiento de 100 mm (P6). Se calibra con `--square-mm` medido. Detector: se recalibra con `--desde-vistas` con `clasico` y con `sb` y se queda el de menor RMS de control (se reportan los dos).
- **Por qué 0.5 px y las vistas de control:** 0.5 px es lo que pide el spec y lo que dio la referencia histórica (0.479 px); el RMS que devuelve `calibrateCamera` es de las vistas con las que se ajusta y puede ser bajo con una K mala (principio 3), así que se mide aparte con vistas que no entran al ajuste. La reproyección no ve un error de escala del tablero; por eso la escala se comprueba con una regla.
- **Cadena:** no se toca (el tracker no cambia; el `.yml` nuevo entra por el perfil gs1).

### Fase 5 · Calibración de la cámara 2

- **Entrega:** `intrinsecos_gs2_<W>x<H>.yml` y `tracker_config_gs2.yaml` apuntado a él, con los scripts de la fase 4 sin cambios. Sesión en vivo, caja en nivel 2.
- **Criterio:** los mismos de la fase 4 con la cámara 2 (RMS ≤ 0.5 px, ≥ 15 vistas, control ≤ 0.75 px, cobertura ≥ 0.8, escala ≤ 1.0 mm en 100 mm), con el detector que eligió la fase 4. B10: la parte de `calibrar_camara.py` se cierra con los números de las fases 4 y 5; lo demás de B10 sigue abierto o se marca «se rehará» por la dirección.
- **Cadena:** no se toca.

### Fase 6 · Comparación contra P02 y archivo de los perfiles viejos

- **Entrega:** sin código salvo que salga un fallo. Una sesión en vivo por cámara, con Slicer conectado antes (OpenIGTLink IF, puerto 18944) y su perfil gs1 o gs2 (con `verbose: true` solo en esta sesión, como en P02, en una copia fuera de `iter4/`). Después, con `git mv`, `tracker_config_doctor.yaml` y `data/globalshutter.yml` pasan a `iter4/data/historico/`, donde ya están los perfiles archivados.
- **Medición:** el dodecaedro quieto a ~45 cm y 30 s, caja en nivel 2; sd x, y, z y rango z con `Claude outputs/pruebas/camara-1/scripts/analizar_log_tracker.py`, el mismo método que P02 (posición tras el filtro 1-Euro); FPS medio del log.
- **Criterio:** por cada cámara, sd z < 1.38 mm (se reporta el número); `Marker0ToTracker` y `DodecaedroToTracker` aparecen en Slicer y se mueven al mover el Marker0 y el dodecaedro (sin punta ni Observer); FPS medio del tracker frente al de la fase 3. Tras el archivo: suite, replay y selftest como la línea base, y `listar_perfiles()` da `tracker_config.yaml`, `tracker_config_gs1.yaml` y `tracker_config_gs2.yaml`.
- **Por qué el archivo cabe aquí sin riesgo:** ninguna prueba ni el replay nombran esos dos archivos (grep); el selftest usa `tracker_config.yaml`; las referencias que quedan son nombres en `recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS` y docstrings, que no fallan si el archivo falta. `docs/ARCHITECTURE.md` y `docs/CONTEXT.md` §6 se ponen al día en el cierre de fase; `DECISIONS.md` y `PRUEBAS.md` son registro y no se tocan. Si el autor prefiere no archivar en esta meta, el movimiento sale de la fase y pasa al BACKLOG.
- **Cadena (principio 6):** es la verificación en vivo de la meta con las dos cámaras: los dos transforms, puerto 18944; puerto libre y ningún python vivo al cerrar.

## Lo que va al BACKLOG

- **Optimizar el tracker** («se hará tras la meta 002»): media, sin condición. Línea base: la tabla de la fase 3 (captura y tracking por separado, con y sin ventana). Incluye medir el coste de la impresión por frame con `verbose: true`.
- **Nivel de luz óptimo de la caja** (P7): baja; con las cámaras ya calibradas, después de esta meta.
- **Panel y runbook con los nombres de los perfiles viejos** (`recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS`, `MANUAL_simplificado.md`, docstrings de `panel.py`, `estado.py` e `identificar_ids.py`): baja, «se rehará» con la punta, el registro y la navegación en las metas siguientes.
- **El perfil Femto (`tracker_config.yaml`) y la línea base del replay:** baja, «se rehará». Queda en `iter4/` porque el replay, `replay_v2_femto_referencia.json` y el selftest dependen de él; archivarlo pide antes un replay grabado con gs1 o gs2.
- **Control de frecuencia de la red eléctrica (50/60 Hz) de UVC**, que OpenCV no expone, si la fase 1 o la 3 ve parpadeo atribuible a la luz: baja.
- **Las dos cámaras a la vez (estéreo o multicámara):** baja; el spec lo deja fuera.
- **B10:** se acota (la parte de `calibrar_camara.py` se cierra en la fase 5).
- Quitadas respecto a la versión anterior: «`PUNTAS_PREFERIDAS` no conoce gs1/gs2» y «el runbook no nombra gs1/gs2» quedan dentro de la entrada «Panel y runbook…» como «se rehará»; «optimizar el tracker solo si no llega a 60 fps» pasa a sin condición.

## ADR que se proponen

- **ADR-022 · La SVPRO AR0234 es global shutter.** La ficha, el sensor AR0234 de onsemi y Windows («Global Shutter Camera», VID 32E4 PID 0234) dicen global shutter; ADR-016 la llamó rolling shutter. ADR-016 no se reescribe: el nuevo corrige su contexto. Se propone escribirlo al cerrar la fase 1, con la evidencia de la sonda.
- **ADR-023 · Un perfil por cámara física, con identidad, ajustes fijos y comprobación de tamaño.** El backend webcam aplica y lee de vuelta los controles del perfil y para si no coinciden; identifica la cámara por `device_id` (instancia USB enumerada por Media Foundation, puerto fijo y etiquetado; P1) en vez de confiar en el índice; para si el frame no tiene el tamaño del `.yml`; MSMF como backend (DSHOW está en desuso según OpenCV) salvo lo que mida la fase 1; la resolución, la misma para las dos, se elige con la tabla de la fase 3. Los perfiles van por cámara, no por contexto (sin «doctor»). Se propone escribirlo al cerrar la fase 2 y completarlo (resolución) en la fase 3; no reescribe ADR-016 ni ADR-018.
- El ADR del rumbo («se rescata el tracking») lo escribe la dirección aparte; no está aquí.

## Preguntas abiertas

P1–P8 respondidas el 2026-10-20 (`clarify.md`). No quedan preguntas nuevas. El archivo de los perfiles viejos en la fase 6 sigue la respuesta de P5 («archivar el viejo»); si el autor no lo quiere en esta meta, lo dice al autorizar y pasa al BACKLOG.

## Títulos de commit

1. Fase 1: «Añade la sonda de controles, modos e identidad de las cámaras»
2. Fase 2: «Fija los ajustes y comprueba el tamaño al abrir la webcam»
3. Fase 3: «Mide resolución y formato de las dos cámaras»
4. Fase 4: «Calibra la cámara 1 y comprueba la escala»
5. Fase 5: «Calibra la cámara 2»
6. Fase 6: «Compara las cámaras contra P02 y archiva los perfiles viejos»
