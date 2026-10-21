# Plan — Meta 002 · Calibración de las cámaras global shutter

Escrito por el agente de planificación con `/planear 002-calibracion-camaras` el 2026-10-20. Sin código. Lo que el autor autoriza es este archivo.
Revisión 1 (2026-10-20): ajustado a las respuestas P1–P8 de `clarify.md` y a `Claude outputs/planes/002/cambios_1.md`. Solo valen los perfiles nuevos: los anteriores no se adaptan; la Femto sale de las sesiones en vivo; la cadena en vivo llega hasta los dos transforms en Slicer, sin punta ni Observer; optimizar el tracker va al BACKLOG sin condición; luz en nivel 2; consultas a Context7 de cada API propuesta.
Revisión 2 (2026-10-21): replanea la Fase 2 tras el cierre de la Fase 1 (`Claude outputs/fases/002/fase-1-cierre.md`) y los tres puntos que el autor aprobó (`Claude outputs/planes/002/cambios_2.md`): identidad por la ruta física del puerto USB; controles por DSHOW en una apertura corta antes de MSMF, con exposición manual; ajustes declarados sin depender del sistema operativo, con una capa para Windows y sitio para Linux. La Fase 2 se parte en **2a** (medir la identidad por puerto y los controles por DSHOW, sin tocar el backend) y **2b** (el backend y los perfiles). La Fase 3 elige la exposición, usa el umbral de 90 fps y anota la exposición leída junto a cada FPS. Las fases 4–6 solo cambian donde nombraban `device_id`. Cambian las firmas de `resolver_indice`, `_resolver_source` y la clave del perfil (`device_id` pasa a `usb_port_windows`), y el ADR propuesto de los perfiles (hoy ADR-024).
Revisión 3 (2026-10-21; `Claude outputs/planes/002/cambios_3.md`): peso de cada fase pendiente (ADR-022); los ADR propuestos pasan a ADR-023 (global shutter) y ADR-024 (un perfil por cámara física), porque el ADR-022 ya existe; P14 = parar y decidir (respuesta del autor), sin replanear por adelantado `IAMCameraControl`.

## Lo leído

- HEAD: `06619cf Cierra la fase 1 con la sesión en vivo de las cámaras`. Árbol limpio.
- Revisión 1: `docs/constitution.md`, `memory.md`, `docs/CONTEXT.md` (trampas §4.1–4.17), `spec.md`, `clarify.md`, la plantilla; `docs/PRUEBAS.md` P02; `docs/BACKLOG.md` B10; `docs/DECISIONS.md` ADR-016 y el índice; `docs/ARCHITECTURE.md` §3.1–3.4; y el código que nombra la revisión 1 (`camera_backend.py`, `calibrar_camara.py`, `tracker.py`, `tracker_config_doctor.yaml`, `data/globalshutter.yml`, `gui/sonda_camara.py`, `gui/estado.py`, `gui/recetas.py`, `gui/panel.py`, `gui/perfil_editor.py`, las pruebas y `.gitignore`).
- Revisión 2: `Claude outputs/planes/002/cambios_2.md`; `Claude outputs/fases/002/fase-1-cierre.md` (entero) y `fase-1-en-vivo.md`; `clarify.md` (enmienda del umbral: ≥ 90 fps); `tasks.md`; `memory.md`; `docs/BACKLOG.md` B23–B26; `docs/DECISIONS.md` (último escrito: ADR-021; el 022 y el 023 siguen propuestos); `codigo/iter4/camaras_uvc.py` y `sondear_camara.py` (completos), `camera_backend.py` (completo), `gui/sonda_camara.py`, `gui/recetas.py` (`receta_sonda_camara`: vigilante del panel a 20 s), `tests/test_camaras_uvc.py`, `tracker.py` (`abrir_camara`, que nadie llama: grep).
- Grep de `source`: `create_backend` lo lee con `cfg_camera["source"]` (obligatorio hoy); `gui/sonda_camara.py` con `get("source", 0)`; `tracker.abrir_camara` (muerta). Grep de `resolver_indice`: solo `camaras_uvc.py` y `test_camaras_uvc.py`.

### Context7 (solo API; regla del autor)

Revisión 1:
- **OpenCV 4.13 `VideoCapture`** (`/websites/opencv_4_13_0`): `CAP_PROP_*` genéricas, «only for those cameras that support»; `AUTO_EXPOSURE` solo documentada para DC1394; `CAP_PROP_SETTINGS` solo DSHOW; DirectShow «deprecated in favor of MSMF». `calibrateCameraExtended`, `findChessboardCornersSB` y ArUco, como en la revisión 1 (confirman las firmas de las fases 4 y 3).
- **Media Foundation** (`/microsoft/media-foundation`): no documentaba `MFEnumDeviceSources` ni sus atributos; `camaras_uvc.py` copió GUIDs y vtable de los encabezados del SDK y se verificó en vivo (orden MSMF = índice OpenCV, 2 de 2).

Revisión 2 (2026-10-21):
- **CfgMgr32** (`/microsoftdocs/windows-driver-docs`): `DEVPKEY_Device_LocationPaths` es `DEVPROP_TYPE_STRING_LIST`, de solo lectura, la pone Windows y se lee con `CM_Get_DevNode_Property`; el ejemplo oficial encadena `CM_Get_Device_Interface_Property(DEVPKEY_Device_InstanceId)` → `CM_Locate_DevNode` → `CM_Get_DevNode_Property`, con el bucle por `CR_BUFFER_SMALL`. `DEVPKEY_Device_Parent` da la instancia del padre (alternativa a `CM_Get_Parent`). Confirma la cadena de `ruta_puerto` de abajo. Los valores de las `DEVPKEY` (GUID y pid) no vienen en Context7: se copian de `devpkey.h` citándolo y se comprueban en ejecución (un `CONFIGRET` distinto de `CR_SUCCESS` para).
- **Win32 / Media Foundation** (`/websites/learn_microsoft_en-us_windows_win32`): `MFEnumDeviceSources` y sus atributos (confirma `camaras_uvc.py`). El ejemplo de `IMFCameraConfigurationManager` dice que, para fijar un valor de exposición, hay que poner el control en `KSPROPERTY_CAMERACONTROL_FLAGS_MANUAL` «para que la cámara no ignore el valor», y que no todo control admite manual. De ahí la medición de la Fase 2a: si escribir `exposure` por OpenCV DSHOW deja el Auto de AMCap desmarcado.
- **DirectShow** (`ICreateDevEnum`, `CLSID_VideoInputDeviceCategory`, `IPropertyBag` «DevicePath», `IAMCameraControl`/`IAMVideoProcAmp`): dos consultas al mismo índice de Win32 devolvieron solo material de Media Foundation. **No quedan contrastados por Context7.** La enumeración DSHOW de la Fase 2a copia CLSID, IID y orden de vtable de `strmif.h`/`uuids.h`/`ocidl.h`, citándolos, y se verifica en vivo (tapando la lente, como se hizo con MSMF).
- **OpenCV DSHOW** (`/websites/opencv_4_13_0`): no documenta en qué orden numera las cámaras ni con qué bandera (manual/auto) escribe `CAP_PROP_EXPOSURE`. Las dos cosas se miden en la Fase 2a; el plan no las da por sabidas.
- **V4L2:** no consultado: la capa de Linux no se escribe (B23). Se consulta cuando se escriba.

### Lo que sale de leer

- `WebcamBackend.open()` pide FOURCC, ancho, alto y FPS, no lee qué obtuvo ni toca controles, y carga K sin mirar `image_width`/`image_height` (P02, hallazgo 1). Es el único punto por el que abren la cámara `tracker.py`, `identificar_ids.py`, `captura_calibracion.py`, `calibrar_tip_divot.py` y `calibrar_camara.py`: identidad, ajustes y comprobación del tamaño van ahí y cubren a todos.
- La instancia USB no identifica el puerto: la primera cámara conectada toma `6&325DB0BA&1&0000` en cualquier puerto; la serie `01.00.00` es igual en las dos (cierre de la Fase 1). `resolver_indice` por instancia funcionaría y elegiría mal.
- La identidad por puerto es la del puerto, no la de la unidad: si se intercambian las cámaras de puerto, cada perfil abre la otra y le aplica sus intrínsecos sin aviso. Los ajustes viven en cada cámara (la 2 lee `focus` 332, la 1 lee 0): una marca escrita en un control que no cambie la imagen podría delatar el intercambio. Sin medir.
- Por MSMF, OpenCV 4.11 no lee ni escribe los controles; por DSHOW sí y lee el estado real (Fase 1). La unidad de la exposición por DSHOW es, por la definición de KS, log2 de segundos: −6 ≈ 15.6 ms no deja 90 fps (periodo 11.1 ms); −7 ≈ 7.8 ms y −8 ≈ 3.9 ms sí. No se sabe con qué exposición se midieron los ~90 fps de la Fase 1.
- `get(CAP_PROP_FOURCC)` por MSMF da `0x00000016` (B26): el formato no se comprueba así; el tamaño del frame sí.
- «Probar cámara» del panel corre `gui/sonda_camara.py` con un vigilante de 20 s (`recetas.receta_sonda_camara`); abrir por MSMF tarda ~10–11 s.
- `create_backend` exige `source`: con la identidad por puerto, `source` pasa a opcional solo cuando el perfil trae `usb_port_windows`.
- `tracker.abrir_camara` no la llama nadie (grep): no se toca; va al BACKLOG.

## Archivos

Se crean:
- `codigo/iter4/camaras_uvc.py` y `codigo/iter4/sondear_camara.py` (fase 1; ya en `e27049e`/`f1536cf`).
- `codigo/iter4/ajustes_camara.py` (fase 2a): los ajustes de cámara en un formato que no depende del sistema operativo (nombres y unidades propios), su validación, y la capa que los aplica en Windows (OpenCV DSHOW, en una apertura corta). Sitio para la capa de Linux (V4L2) sin escribirla.
- `codigo/iter4/tracker_config_gs1.yaml` y `codigo/iter4/tracker_config_gs2.yaml` (fase 2b): un perfil por puerto etiquetado (gs1 = puerto 1, gs2 = puerto 2), sin nada del perfil doctor: geometría del dodecaedro y detector que valieron en P02 (`Claude outputs/pruebas/camara-1/perfiles/`), Marker0 de 80 mm medido con calibrador (P3), `usb_port_windows`, `controls` y una sola línea `calibration_file:` (vacía hasta las fases 4 y 5). Modo provisional; la resolución y la exposición las fija la fase 3.
- `codigo/iter4/medir_modos.py` (fase 3), `codigo/iter4/comprobar_escala.py` (fase 4), `codigo/iter4/data/intrinsecos_gs1_<W>x<H>.yml` (fase 4) y `intrinsecos_gs2_<W>x<H>.yml` (fase 5), versionados (P4).
- Pruebas sin cámara: `test_camaras_uvc.py` (fase 1; se amplía en 2a), `codigo/tests/test_ajustes_camara.py` (fase 2a), `codigo/tests/test_camera_backend.py` (fase 2b), `test_medir_modos.py` (fase 3), `test_calibrar_camara.py` (fase 4).
- Fuera de git: `Claude outputs/camaras/` (JSON y tablas, vistas, logs) y los reportes en `Claude outputs/fases/002/`.

Se modifican:
- `codigo/iter4/camaras_uvc.py` (fase 2a): la ruta física del puerto de cada cámara por CfgMgr32 (`ctypes` sobre `cfgmgr32.dll`, sin dependencia nueva), la enumeración DSHOW con su ruta, y `resolver_indice` por puerto en vez de por instancia.
- `codigo/iter4/sondear_camara.py` (fase 2a): modos nuevos para las mediciones de la 2a (identidad por puerto, orden DSHOW, fijar ajustes y dejarlos, controles antes y después de abrir por MSMF). `CONTROLES` pasa a importarse de `ajustes_camara.py` (una sola fuente).
- `codigo/iter4/camera_backend.py` (fase 2b): solo `WebcamBackend` y `create_backend`. Identidad por puerto, ajustes aplicados por la capa del sistema y leídos de vuelta, comprobación del tamaño del frame contra lo pedido y contra el `.yml`. `FemtoBoltBackend`, `read()` y `get_intrinsics()` no se tocan.
- `codigo/iter4/gui/sonda_camara.py` (fase 2b): «Probar cámara» resuelve el puerto, abre con el modo del perfil y dice el tamaño real frente al del perfil y al del `.yml` (P02, hallazgo 5). No aplica ajustes (cabe en los 20 s del vigilante).
- `codigo/iter4/gui/recetas.py` (fase 2b, solo si hace falta): `timeout_s` de `receta_sonda_camara` de 20 a 35 s si la medición en vivo de «Probar cámara» pasa de 15 s.
- `codigo/iter4/calibrar_camara.py`, `gui/panel.py`, `gui/recetas.py` (fase 4), y los perfiles gs1/gs2 (fases 3, 4 y 5), como en la revisión 1.

Se mueven (fase 6, con `git mv`): `tracker_config_doctor.yaml` y `data/globalshutter.yml` a `iter4/data/historico/`.

No se tocan: `tracker.py` (tampoco `abrir_camara`), el envío por `pyigtl`, `FemtoBoltBackend`, `tracker_config.yaml` (Femto: replay y selftest, la línea base del «no cambió»), los scripts de Slicer, la punta y la geometría. Tampoco `recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS` ni el runbook (se rehará con la punta; BACKLOG).

## Funciones y clases

`iter4/camaras_uvc.py` (fase 1, cambia en 2a):
- `@dataclass CamaraUVC(indice: int, nombre: str, enlace: str, vid: str | None, pid: str | None, instancia: str | None, ruta_puerto: str | None = None, ubicacion: str | None = None, instancia_usb: str | None = None)`: tres campos nuevos al final, con `None` por defecto (las construcciones de hoy siguen valiendo). `ruta_puerto` = primer elemento de `DEVPKEY_Device_LocationPaths` del nodo USB padre del `MI_00` (forma `PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(2)`); `ubicacion` = `DEVPKEY_Device_LocationInfo` del mismo nodo (`Port_#0002.Hub_#0001`), de apoyo; `instancia_usb` = instancia del padre.
- `datos_puerto(enlace: str) -> tuple[str | None, str | None, str | None]`: (`ruta_puerto`, `ubicacion`, `instancia_usb`) por `CM_Get_Device_Interface_PropertyW(DEVPKEY_Device_InstanceId)` → `CM_Locate_DevNodeW` → `CM_Get_Parent` → `CM_Get_Device_IDW` y `CM_Get_DevNode_PropertyW` (`LocationPaths`, `LocationInfo`). Vale para el enlace de MF y para el `DevicePath` de DSHOW. Si el nodo no es USB (cámara virtual), `(None, None, None)`; un `CONFIGRET` de error en una cámara USB levanta `OSError`.
- `primera_ruta(multi_sz: str) -> str | None`: el primer elemento no vacío de una `STRING_LIST`; pura, con prueba.
- `listar_camaras_msmf(con_puerto: bool = True) -> list[CamaraUVC]`: lo de hoy más `datos_puerto` de cada una.
- `listar_camaras_dshow() -> list[CamaraUVC]`: por `ctypes` COM: `CoCreateInstance(CLSID_SystemDeviceEnum, ICreateDevEnum)` → `CreateClassEnumerator(CLSID_VideoInputDeviceCategory)` (S_FALSE = ninguna) → `IEnumMoniker::Next` → `IMoniker::BindToStorage(IPropertyBag)` → `Read("FriendlyName")` y `Read("DevicePath")`; `indice` = orden de la enumeración (el que se supone que usa OpenCV DSHOW: se verifica en vivo); `enlace` = `DevicePath`; y `datos_puerto`. Falla fuerte si COM no inicializa.
- `resolver_indice(puerto: str, camaras: list[CamaraUVC]) -> int`: **cambia**: el índice de la única cámara cuya `ruta_puerto` es igual a `puerto` (sin distinguir mayúsculas; igualdad, no subcadena, porque una ruta es prefijo de la de un puerto de un hub colgado de ella). `ValueError` con la lista de cámaras y rutas si hay 0 o más de 1. La búsqueda por instancia se quita: elegiría mal (cierre de la Fase 1). Sus 5 pruebas se reescriben con rutas.
- `main()`: lista también la ruta y la ubicación, y la enumeración DSHOW.

`iter4/ajustes_camara.py` (fase 2a):
- El formato del perfil (`camera.controls`), independiente del sistema: `exposure_manual: bool`, `exposure_ms: float`, `gain`, `auto_white_balance: bool`, `brightness`, `contrast`, `saturation`, `sharpness`, `gamma`, `backlight`, `focus` (estos, el valor crudo de UVC). No admite `auto_exposure` ni `wb_temperature`: los rechaza con el porqué (Fase 1: no verificable y rechazado).
- `NOMBRES: tuple[str, ...]` y `CONTROLES_CV2: dict[str, int]` (el `CONTROLES` de la sonda, movido aquí).
- `validar_controles(controls: dict) -> dict`: nombres conocidos, tipos, `exposure_ms` > 0, y `exposure_manual: true` obligatorio si hay `exposure_ms`; `ValueError` con la lista. Pura.
- `exposicion_ms_a_dshow(ms: float, tolerancia: float = 0.02) -> int` y `dshow_a_exposicion_ms(valor: int) -> float`: log2 de segundos; si `ms` no es 1000·2^k dentro de la tolerancia, `ValueError` con los valores válidos cercanos (… 1.953, 3.906, 7.813, 15.625 ms). Puras.
- `a_nativos_dshow(controls: dict) -> dict[str, float]`: nombre del perfil → valor para `cv2.CAP_PROP_*` por DSHOW (la exposición convertida; `exposure_manual` no es un valor: se cumple al escribir `exposure`, lo que mide la 2a). Pura.
- `comparar_controles(declarados: dict, leidos: dict, tolerancia: float = 1e-3) -> list[str]`: los que no coinciden. Pura.
- `class CapaAjustes(Protocol)`: `leer(self, puerto: str, nombres: list[str]) -> dict[str, float]` y `aplicar(self, puerto: str, controls: dict) -> dict`; `aplicar` devuelve `{"leidos": …, "escritos": [...], "segundos": …}` y levanta `RuntimeError` con la lista si algo no coincide tras escribir.
- `class CapaWindowsDShow(CapaAjustes)`: `__init__(self, listar=camaras_uvc.listar_camaras_dshow, abrir=None)` (inyectables para las pruebas); resuelve el índice DSHOW por el puerto, abre `cv2.VideoCapture(i, cv2.CAP_DSHOW)`, lee, **escribe solo lo que difiere** (los ajustes persisten en la cámara), relee siempre, libera. Sin `set` de FOURCC, tamaño ni FPS.
- `capa_para_plataforma(plataforma: str = sys.platform) -> CapaAjustes`: `win32` → `CapaWindowsDShow`; otro → `NotImplementedError("capa V4L2: B23")`.

`iter4/sondear_camara.py` (fase 2a; lo de la fase 1 no cambia):
- `--puertos`: enumera MSMF y DSHOW con índice, instancia, `ruta_puerto` y `ubicacion`; JSON.
- `--verificar-orden --backend DSHOW`: lo de hoy, por DSHOW y con la ruta de cada índice.
- `--fijar "exposure_ms=3.906,gain=12,..."` con `--puerto`: aplica por `CapaWindowsDShow` y deja los valores (para el Auto de AMCap y la marca).
- `--tras-msmf` con `--puerto` y `--modo 640x480:MJPG --fps 90 --segundos 10`: lee por DSHOW, abre y captura por MSMF, cierra, lee otra vez; JSON con las dos lecturas y las diferencias.
- `nitidez(gray) -> float` (varianza del laplaciano) y `testigo` con nitidez, para la medición de la marca.
- Todo con `--timeout` y `--salida` obligatorios, como hoy; cada medición guarda su resultado en el `estado` del vigilante al tenerlo (B25 no se repite en lo nuevo).

`iter4/camera_backend.py` (fase 2b):
- `WebcamBackend.__init__(self, source=None, width=640, height=480, fps=30, backend="MSMF", fourcc="MJPG", calibration_file=None, controls: dict | None = None, usb_port_windows: str | None = None, marca: dict | None = None)`. Sin los tres nuevos, el backend hace las mismas llamadas a `cv2` que hoy (prueba).
- `WebcamBackend._resolver_source(self) -> int`: **cambia**: con `usb_port_windows`, `camaras_uvc.resolver_indice(puerto, listar_camaras_msmf())`; si el perfil trae también `source` y no coinciden, para con los dos; sin puerto, `int(source)` (y `source` ausente, `ValueError`).
- `WebcamBackend._aplicar_controles(self) -> dict`: `validar_controles`, `capa_para_plataforma().aplicar(puerto, controls)` **antes** de abrir por MSMF; deja `self.ajustes_leidos` y lo imprime con el tiempo que tardó. Exige `usb_port_windows` si hay `controls` (la capa abre por puerto).
- `WebcamBackend._comprobar_marca(self) -> None` (solo si la 2a la valida y el autor lo decide, P13): el control de `marca` leído en la apertura DSHOW debe valer lo declarado; si no, `RuntimeError` («la cámara de este puerto no es la del perfil: ¿se intercambiaron?»).
- `leer_tamano_yml(ruta) -> tuple[int, int] | None`: `image_width`/`image_height` del `.yml`.
- `WebcamBackend._comprobar_tamano(self, frame) -> None`: tras el warmup, el frame real contra el modo pedido (si difiere, `RuntimeError`: p. ej. 1600×1200 entrega 1280×960) y contra el `.yml` (si difiere, `RuntimeError` con los dos tamaños; principio 7). `.yml` sin tamaño: aviso. No usa `get(CAP_PROP_FOURCC)` (B26).
- `create_backend(cfg_camera)`: `source` con `get`; pasa `controls`, `usb_port_windows` y `marca` cuando están.

`iter4/medir_modos.py` (fase 3; cambia respecto a la revisión 1):
- `medir_captura(cap, segundos: float) -> dict` y `medir_tracking(cap, cfg: dict, segundos: float, ventana: bool) -> dict`: como en la revisión 1 (funciones de `tracker.py` importadas, sin copiarlas).
- `fraccion_saturada(gray, esquinas: list[np.ndarray], margen_px: int = 10) -> float`: fracción de píxeles a 255 dentro de la envolvente de los markers del dodecaedro detectados, con margen. Pura, con prueba.
- `medir_exposicion(puerto: str, cfg: dict, exposiciones_ms: list[float], modo, segundos: float) -> list[dict]`: por exposición, la fija con la capa, abre por MSMF, mide FPS de captura, `fraccion_saturada`, brillo medio y mediana de markers; anota la exposición leída por DSHOW.
- `elegir_exposicion(filas: list[dict], fps_min: float, max_saturada: float) -> dict | None`: entre las que cumplen FPS de captura ≥ `fps_min` y saturada ≤ `max_saturada`, la de más markers; empate, la mayor exposición.
- `elegir_resolucion(filas_gs1: list[dict], filas_gs2: list[dict], fps_min: float = 90.0, tolerancia: float = 0.02) -> dict | None`: la de más píxeles con FPS de tracking con ventana ≥ `fps_min·(1 − tolerancia)` en las dos cámaras (P8, enmienda, P11).
- `tabla_markdown(filas: list[dict]) -> str`: con la columna de la exposición leída.
- `main(argv=None) -> int`: `--config`, `--exposiciones-ms`, `--modos`, `--segundos-captura`, `--segundos-tracking`, `--luz`, `--salida`, `--timeout`. Cada fila se escribe en el JSON al medirla (B25), y el presupuesto por modo es el medido (~50 s de apertura y fallos por MSMF).

`iter4/calibrar_camara.py` y `iter4/comprobar_escala.py` (fase 4): como en la revisión 1, salvo que `guardar_yml(..., extra)` registra `usb_port_windows` (en vez de `device_id`) y los ajustes leídos con la exposición en ms.

## Fases

Comunes a todas: la suite en verde con su tiempo (hoy 147: 125 pasan, 22 `xfail`); las 100 de la línea base siguen igual (78 pasan, 22 `xfail`) y las nuevas pasan; replay 0.0 mm / 0.0°; `panel.py --selftest` rc 0 con `tracker_config.yaml`. Ese es el «no cambió» de la Femto, sin cámara. Tras cada `.py` editado, `py_compile` y conteo de líneas. Toda corrida con cámara lleva `--timeout` y libera la cámara (principio 9). Caja de luz en **nivel 2** (P7), anotado en `--luz` o en el reporte. PowerLine en 60 Hz en AMCap antes de cada sesión (B24). AMCap cerrado durante cada corrida.

### Fase 1 · Sonda de controles, modos e identidad (sin tocar el backend)

Hecha (2026-10-21; `e27049e`, `f1536cf`, `06619cf`). Criterio y números en `tasks.md` y en `Claude outputs/fases/002/fase-1-cierre.md`.

### Fase 2a · Identidad por puerto y controles por DSHOW, medidos con las dos cámaras

- **Entrega:** los cambios de `camaras_uvc.py` y `sondear_camara.py`; `ajustes_camara.py`; pruebas sin cámara: `primera_ruta`, `resolver_indice` por ruta (0, 1 y 2 coincidencias; prefijo de un hub que no debe coincidir; mayúsculas), `validar_controles` (desconocido, `auto_exposure` y `wb_temperature` rechazados, `exposure_ms` sin `exposure_manual`), `exposicion_ms_a_dshow` (3.906 → −8, 7.8125 → −7, 5.0 rechazado con los válidos cercanos), `a_nativos_dshow`, `comparar_controles`, y `CapaWindowsDShow` con un `VideoCapture` y un `listar` falsos (escribe solo lo que difiere; relee siempre; para si no coincide; para si el puerto no está; libera siempre). Sin cámara no se toca el backend.
- **El autor, en vivo** (puertos 1 y 2 etiquetados, cámaras etiquetadas en cuerpo y cable):
  1. Identidad: `--puertos` con la cámara 1 sola en el puerto 1, luego en el 2; la cámara 2 sola en el 1, luego en el 2; las dos conectadas, primero la 1 y luego la 2, y al revés. Seis enumeraciones.
  2. Orden DSHOW: con las dos conectadas, en los dos órdenes, `--verificar-orden --backend DSHOW` tapando una lente.
  3. MSMF frente a DSHOW: por cámara, `--fijar` con valores distintos de los de AMCap (p. ej. `exposure_ms=1.953,gain=11`), luego `--tras-msmf` a 640×480 MJPG 90 fps.
  4. El Auto de AMCap: el autor marca Auto en exposición en AMCap y lo cierra; `--fijar exposure_ms=3.906`; abre AMCap y mira la casilla y el valor.
  5. El coste: `--fijar` con los valores ya puestos (no escribe nada) tres veces por cámara; se toma la mediana de `segundos`.
  6. Opcional, la marca: por cámara, testigo (brillo, nitidez, FPS) con la escena quieta; `--fijar focus=<valor lejano al actual>`; testigo otra vez; desenchufar y enchufar; leer. Y un `leer` de la cámara 2 tras desenchufar (persistencia de la 2, B24).
- **Criterio (números):**
  - Identidad: en las 6 enumeraciones, cada puerto da siempre la misma `ruta_puerto` (sea cual sea la cámara y el orden) y los dos puertos dan rutas distintas: 6 de 6. Se anotan las dos rutas y su `ubicacion`.
  - Orden DSHOW: `listar_camaras_dshow()` da las dos con su ruta, y el índice DSHOW tapado es el de la ruta de esa cámara: 2 de 2 en cada orden (4 de 4).
  - MSMF no pisa lo escrito por DSHOW: 0 diferencias entre la lectura de antes y la de después, por cámara.
  - Exposición manual: escribir `exposure` desmarca el Auto de AMCap (sí/no) y AMCap muestra el valor escrito (sí/no).
  - Coste: segundos de la capa por arranque (mediana de 3), por cámara; se reporta. Si pasa de 15 s se plantea al autor.
  - Marca (si se mide): el testigo no cambia (brillo y nitidez dentro del 2 %, FPS dentro del 20 %) y el valor de `focus` persiste tras desenchufar (sí/no), por cámara.
- **Si algo falla:** identidad no estable → para y se replantea (la propuesta 2 del cierre, deducir por la instancia de puerto, queda como plan B). MSMF pisa los controles, o el Auto no se desmarca → la 2a lo mide y, si pasa, la meta se para y el autor decide con los datos (P14, respuesta b); no se replantea nada por adelantado. El backend no se toca hasta que esto pase.
- **Peso: pesada.** Lógica nueva (CfgMgr32 y COM de DSHOW por `ctypes`, sin contraste en Context7), una medición en vivo cuyo fallo para la meta.
- **Cadena:** no se toca.

### Fase 2b · Perfiles por cámara: identidad, ajustes y tamaño al abrir

- **Entrega:** los cambios de `camera_backend.py`, `gui/sonda_camara.py` (y `recetas.py` si hace falta); `tracker_config_gs1.yaml` y `tracker_config_gs2.yaml` con `usb_port_windows` (las rutas medidas en 2a), `controls` (`exposure_manual: true`, `exposure_ms` provisional 3.906 —la elige la fase 3—, `gain` y los demás con los valores que la cámara tiene hoy, leídos en 2a; `auto_white_balance: false`), `marca` si P13 lo decide, modo provisional 640×480 MJPG 90 fps MSMF y `calibration_file` vacío. `test_camera_backend.py` con `VideoCapture`, `listar` y capa falsos: sin `controls` ni `usb_port_windows`, las mismas llamadas a `cv2` y en el mismo orden que hoy; puerto con 0, 1 y 2 coincidencias; puerto y `source` que no coinciden; `controls` sin puerto; capa que para; tamaño igual y distinto del pedido y del `.yml`; `.yml` sin tamaño; marca que coincide y que no.
- **Criterio sin cámara:** las pruebas nuevas pasan; `create_backend` con la sección `camera` de `tracker_config.yaml` construye lo mismo que hoy (prueba); suite, replay y selftest como la línea base.
- **Criterio en vivo, por cámara:**
  - Dos aperturas seguidas con su perfil: 0 diferencias en los controles leídos; la segunda no escribe nada.
  - Una copia temporal del perfil (en `Claude outputs/camaras/`, fuera de `iter4/`) con un `.yml` de otro tamaño para al abrir con el mensaje de los dos tamaños.
  - «Probar cámara» del panel dice el tamaño real y termina dentro del vigilante (se anota cuánto tarda).
  - Con las dos conectadas, en los dos órdenes, cada perfil abre la suya (tapando una lente): 4 de 4.
  - Con las cámaras intercambiadas de puerto: si hay marca, el backend para con el mensaje (2 de 2); si no, se anota «no detectable» y la mitigación son las etiquetas.
  - El tiempo que la capa añade al arranque.
- **Peso: pesada.** Toca `camera_backend.py`, el punto por el que abren la cámara todos los scripts (principio 6), con identidad, ajustes y comprobación de tamaño nuevos.
- **Cadena (principio 6):** `tracker.py` no cambia; el diff de `camera_backend.py` no toca `FemtoBoltBackend` ni `read()`/`get_intrinsics()`; suite, replay 0.0 mm / 0.0° y selftest. Sin sesión con Slicer en esta fase (los perfiles nuevos aún no tienen intrínsecos): la verificación en vivo de la cadena es la de la fase 6.

### Fase 3 · Enfoque, exposición y medición de resolución × formato

- **Entrega:** `medir_modos.py` y `test_medir_modos.py` (`fraccion_saturada` con una imagen sintética; `elegir_exposicion`; `elegir_resolucion` con dos cámaras, umbral 90 y tolerancia; la tabla). Sesión en vivo por cámara.
- **El autor, en vivo:** enfoca la lente a 50–70 cm con el tablero a 60 cm y la mira de nitidez del script (varianza del laplaciano, en pantalla) y fija la rosca; pone el dodecaedro quieto a ~60 cm; caja en nivel 2.
- **Medición 1, la exposición** (por cámara, a 1280×960 MJPG, el modo mayor de ~90 fps en las dos): candidatas 7.813, 3.906, 1.953, 0.977 y 0.488 ms (−7 a −11 por DSHOW); por cada una 10 s de captura con FPS, `fraccion_saturada`, brillo medio y markers. La ganancia y los demás, los del perfil.
- **Medición 2, los modos** (por cámara, con la exposición elegida): MJPG 320×240, 640×480, 960×720, 1280×720 y 1280×960 (los que dan ~90 en las dos; 1024×768 no, porque la cámara 2 no da frames; 800×600 y 1600×1200 no sirven, B26): captura 10 s, tracking 30 s sin ventana y 30 s con ventana. MJPG 1920×1080 y 1920×1200, y YUY2: solo captura (no llegan a 90). Cada fila con la exposición leída por DSHOW antes de medir. `--timeout 1800` por cámara. Es también la línea base de la optimización del tracker.
- **Criterio:**
  - Exposición: la elegida cumple FPS de captura ≥ 88.2 (90 con la tolerancia de P11) y fracción saturada ≤ 1 % (P12) en las dos cámaras; se reporta la fila de cada candidata. La misma en las dos (P8); si no hay una común, el autor elige con la tabla.
  - Modos: la tabla de cada cámara existe con, por modo, tamaño real, exposición leída, FPS de captura, FPS de tracking sin y con ventana, mediana de markers y fracción con pose. La resolución elegida es la mayor con FPS de tracking con ventana ≥ 88.2 sostenidos 30 s en las dos cámaras. Si ninguna llega y alguna sí de captura, es hallazgo para la meta de optimizar el tracker y el autor elige con la tabla.
  - Los perfiles gs1/gs2 quedan con el modo y la `exposure_ms` elegidos, los mismos en los dos.
- **Peso: pesada.** Script de medición nuevo con lógica de elección y sesiones largas con cámara cuyo fallo es difícil de aislar.
- **Cadena:** no se toca (importa funciones de `tracker.py` sin modificarlo y no abre `pyigtl`).

### Fase 4 · Calibración de la cámara 1 y comprobación de escala

- **Entrega:** los cambios de `calibrar_camara.py`, del diálogo del panel y de la receta; `comprobar_escala.py`; `test_calibrar_camara.py` (vistas sintéticas proyectadas con una K conocida: `calibrar` la recupera con fx/fy dentro del 0.1 % y RMS < 0.05 px; `cobertura`; `errores_escala`); `intrinsecos_gs1_<W>x<H>.yml`; `tracker_config_gs1.yaml` apuntado a él.
- **El autor, en vivo:** mide la pieza 2×2 y luego el tablero con calibrador (al menos 5 medidas sobre casillas distintas, en mm con dos decimales) y las dicta; captura 20–30 vistas variadas (bordes y esquinas de la imagen, inclinaciones de hasta ~45°, 40–80 cm), caja en nivel 2; para la escala, apoya el tablero sobre una base rígida que desliza contra una regla y lo pone en 0, 100 y 200 mm.
- **Criterio:** el lado medido (media de ≥ 5 medidas, dos decimales) queda en `clarify.md` y en el `.yml`; RMS ≤ 0.5 px con ≥ 15 vistas usadas, RMS de las 3 vistas de control ≤ 0.75 px y cobertura ≥ 0.8, a la resolución elegida; el `.yml` declara esa resolución, el puerto y los ajustes leídos, y el backend lo acepta al abrir; escala: |error| ≤ 1.0 mm en cada desplazamiento de 100 mm (P6). Detector: `clasico` y `sb` con `--desde-vistas`; se queda el de menor RMS de control (se reportan los dos).
- **Peso: pesada.** Calibración y comprobación de escala nuevas (`calibrar`, `cobertura`, `errores_escala`); un error de escala no se ve en el RMS.
- **Por qué 0.5 px y las vistas de control:** 0.5 px lo pide el spec y lo dio la referencia histórica (0.479 px); el RMS de `calibrateCamera` es de las vistas del ajuste y puede ser bajo con una K mala (principio 3); la reproyección no ve un error de escala del tablero, por eso la regla.
- **Cadena:** no se toca.

### Fase 5 · Calibración de la cámara 2

- **Entrega:** `intrinsecos_gs2_<W>x<H>.yml` y `tracker_config_gs2.yaml` apuntado a él, con los scripts de la fase 4 sin cambios. Sesión en vivo, caja en nivel 2.
- **Criterio:** los de la fase 4 con la cámara 2, con el detector que eligió la fase 4. B10: la parte de `calibrar_camara.py` se cierra con los números de las fases 4 y 5.
- **Peso: ligera.** Los scripts de la fase 4 sin cambios; solo una sesión en vivo con la otra cámara y un `.yml`.
- **Cadena:** no se toca.

### Fase 6 · Comparación contra P02 y archivo de los perfiles viejos

- **Entrega:** sin código salvo que salga un fallo. Una sesión en vivo por cámara, con Slicer conectado antes (OpenIGTLink IF, puerto 18944) y su perfil gs1 o gs2 (con `verbose: true` solo en esta sesión, en una copia fuera de `iter4/`). Después, con `git mv`, `tracker_config_doctor.yaml` y `data/globalshutter.yml` pasan a `iter4/data/historico/`.
- **Medición:** el dodecaedro quieto a ~45 cm y 30 s, caja en nivel 2; sd x, y, z y rango z con `Claude outputs/pruebas/camara-1/scripts/analizar_log_tracker.py` (posición tras el 1-Euro, como P02); FPS medio del log.
- **Criterio:** por cámara, sd z < 1.38 mm (se reporta el número); `Marker0ToTracker` y `DodecaedroToTracker` aparecen en Slicer y se mueven (sin punta ni Observer); FPS medio frente al de la fase 3. Tras el archivo: suite, replay y selftest como la línea base, y `listar_perfiles()` da `tracker_config.yaml`, `tracker_config_gs1.yaml` y `tracker_config_gs2.yaml`.
- **Por qué el archivo cabe aquí sin riesgo:** ninguna prueba ni el replay nombran esos dos archivos (grep); el selftest usa `tracker_config.yaml`; lo que queda son nombres en `recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS` y docstrings, que no fallan si el archivo falta. Si el autor prefiere no archivar en esta meta, pasa al BACKLOG.
- **Peso: pesada.** Es la verificación de la cadena tracker → OpenIGTLink → Slicer (principio 6) con las dos cámaras, y el archivo con `git mv`.
- **Cadena (principio 6):** la verificación en vivo de la meta con las dos cámaras: los dos transforms, puerto 18944; puerto libre y ningún python vivo al cerrar.

## Lo que va al BACKLOG

- **Optimizar el tracker** («se hará tras la meta 002»): media, sin condición. Línea base: la tabla de la fase 3.
- **Nivel de luz óptimo de la caja** (P7): baja.
- **Panel y runbook con los nombres de los perfiles viejos** (`recetas.SLUGS`, `estado.PUNTAS_PREFERIDAS`, `MANUAL_simplificado.md`, docstrings): baja, «se rehará».
- **El perfil Femto y la línea base del replay:** baja, «se rehará»; archivarlo pide antes un replay grabado con gs1 o gs2.
- **Las dos cámaras a la vez (estéreo o multicámara):** baja.
- **B10:** se acota (la parte de `calibrar_camara.py` se cierra en la fase 5).
- **B23 · Jetson** (al día, revisión 2): la capa de ajustes V4L2 (`ajustes_camara.capa_para_plataforma("linux")`) y la identidad por `/dev/v4l/by-path` (`usb_port_linux`) quedan por escribir; el formato de `controls` ya no depende del sistema.
- **B24** (al día en la 2a): persistencia de PowerLine en la cámara 2.
- **B25:** sigue en la sonda vieja; lo nuevo de la 2a y `medir_modos.py` guardan cada resultado al tenerlo.
- **Identidad de la unidad física con la serie idéntica** (nueva, solo si la marca de la 2a no sirve o el autor no la quiere): alta (un intercambio de puerto da intrínsecos de la otra cámara sin aviso). Mitigación hasta entonces: etiquetas en cámara, cable y puerto.
- **Controles por `IAMCameraControl` directo** (nueva, solo si la 2a muestra que OpenCV DSHOW no deja la exposición en manual o tarda demasiado): media; es una opción que el autor decide entonces con los datos (P14), no un plan.
- **`tracker.abrir_camara`, función que nadie llama** (nueva): baja.

## ADR que se proponen

- **ADR-023 · La SVPRO AR0234 es global shutter.** Lo escribe la dirección. La sonda no aportó evidencia del obturador; la serie idéntica no va aquí.
- **ADR-024 · Un perfil por cámara física (identificada por su puerto USB), con ajustes fijos independientes del sistema y comprobación del tamaño** (revisado). La cámara se identifica por la ruta física de su puerto (`DEVPKEY_Device_LocationPaths` del nodo USB padre, CfgMgr32 por `ctypes`), no por la instancia: la serie `01.00.00` es la misma en las dos SVPRO y la primera conectada toma la instancia de la serie en cualquier puerto. La identidad es la del puerto, no la de la unidad: se mitiga con etiquetas y, si la 2a lo valida, con una marca en `focus`. Los ajustes se declaran en el perfil con nombres y unidades propios (exposición en ms), y una capa por sistema los aplica y lee de vuelta: en Windows, OpenCV DSHOW en una apertura corta antes del vídeo por MSMF (por MSMF OpenCV no los lee ni escribe), escribiendo solo lo que difiere; Linux (V4L2) queda con sitio. Sin `auto_exposure` (no verificable) ni `wb_temperature` (rechazado). El vídeo, por MSMF; el backend para si el frame no tiene el tamaño pedido o el del `.yml`. Los perfiles van por cámara, no por contexto. Se escribe al cerrar la 2b y se completa (resolución y exposición) en la fase 3; no reescribe ADR-016 ni ADR-018.
- El ADR del rumbo («se rescata el tracking») lo escribe la dirección aparte.

## Preguntas abiertas

P1–P8 y la enmienda del umbral, respondidas. Nuevas, en `clarify.md`:
- **P9** · Si la Fase 2 se parte en 2a (medir) y 2b (backend), con un commit cada una.
- **P10** · Si la exposición se declara en ms (física) o en el valor nativo de cada sistema.
- **P11** · La tolerancia del umbral de 90 fps.
- **P12** · El criterio de saturación para elegir la exposición.
- **P13** · Si la marca en `focus`, si la 2a la valida, se usa al abrir.
- **P14** · Qué se hace si la 2a muestra que MSMF pisa los controles o que el Auto no se desmarca. Respondidas P9–P14 (en `clarify.md`); el plan coincide con ellas.

## Títulos de commit

1. Fase 1: «Añade la sonda de controles, modos e identidad de las cámaras» (hecho; cierre: «Cierra la fase 1 con la sesión en vivo de las cámaras»)
2. Fase 2a: «Identifica las cámaras por su puerto USB y fija sus ajustes por DSHOW»
3. Fase 2b: «Abre cada webcam por su puerto con sus ajustes y comprueba el tamaño»
4. Fase 3: «Elige exposición y resolución de las dos cámaras»
5. Fase 4: «Calibra la cámara 1 y comprueba la escala»
6. Fase 5: «Calibra la cámara 2»
7. Fase 6: «Compara las cámaras contra P02 y archiva los perfiles viejos»
