# Plan — Meta 003 · Arquitectura y optimización del tracker

Lo escribe el agente de planificación con `/planear`, sin código. Lo que el autor autoriza es este archivo. Primera versión: 2026-10-23. Revisión del 2026-10-23 con las respuestas del autor (`clarify.md`, P1–P8): cambian P8 (nombres en inglés) y P5 (el manual se mueve); lo demás, como se recomendaba.

## Lo leído

- HEAD: `b191e61 Cierra la meta 002 · Calibración de las cámaras global shutter`. Árbol: `memory.md` modificado y `specs/003-arquitectura-tracker/` sin seguir.
- El spec y `diagrama.md` de esta carpeta; `clarify.md` con P1–P8 respondidas; `docs/constitution.md`, `memory.md`, `docs/CONTEXT.md` (§3, §4 trampas 1–19, §6).
- `docs/ARCHITECTURE.md` §3.2–3.7, §4 y §6; `docs/BACKLOG.md` B17, B18, B22, B27, B28, B32, B34, B37, B38; `docs/DECISIONS.md` índice y ADR-022; `docs/PRUEBAS.md` índice.
- Código: `iter4/tracker.py` entero (703 líneas); `camera_backend.py` (interfaz, `open`, `read`, `create_backend`); los imports y las rutas de los 16 scripts de `iter4/` y los 9 de `gui/` (grep); `captura_calibracion.cargar_config` (igual que `tracker.cargar_config`); `medir_modos.preparar_tracking`/`medir_tracking` (repite el bucle con el dodecaedro); `gui/estado.evaluar_todo`/`apto_para_tracker` (exige la geometría en verde) y `listar_perfiles` (`glob("tracker_config*.yaml")`); `gui/recetas` (el nombre corto del perfil sale de quitar `tracker_config_` al nombre del archivo); `gui/procesos.entorno_hijo`; `panel.py --selftest`.
- Pruebas: `conftest.py` (pone `iter4/` y `gui/` en `sys.path`), `pytest.ini` (`testpaths = tests`), `test_replay.py` y `replay_util.py` (replay del dodecaedro con el perfil Femto), `test_gui_headless.py`, `test_aceleracion_msmf.py` (fija B28), `test_compilan.py`.
- `git ls-files codigo`: lo versionado de `iter4/` y `iter4/data/`; lo local (npz, npy, `*_calibrado.txt` salvo el v2, puntas) está fuera de git por `.gitignore`. **`codigo/historico/` ya existe** (iter1, iter2, iter2_callejones_sin_salida, iter3, iter4_diagnosticos) y dentro de `historico/iter2/` hay un `*.nrrd` (solo se vio su nombre en `git ls-files`; no se abrió).
- Referencias a `iter4` fuera del código: `CLAUDE.md` (7), `docs/ARCHITECTURE.md` (10), `BACKLOG.md` (17), `CONTEXT.md` (5), `DECISIONS.md` (6, aditivo: quedan como históricas), `PRUEBAS.md` (5), y una en cada uno de `.claude/agents/{desarrollo,direccion,planificacion}.md` y `.claude/skills/planear/SKILL.md`.
- `documentos/`: `MANUAL_simplificado.md` (encabezados y las líneas del Observer y del puerto; §4.1–4.6 dependen de `DodecaedroToMarker0`); `documentos/historico/` no existe. Lo nombran: `iter4/gui/{estado,panel,recetas}.py` (una línea cada uno, todas en código del dodecaedro que se quita), `docs/ARCHITECTURE.md` (líneas 78, 162 y 301), `docs/BACKLOG.md` (51, 65, 135, 277), `docs/CONTEXT.md` (192), y textos históricos (`DECISIONS.md`, `docs/history/`, specs 001 y 002), que no se tocan.
- **Choques de nombres (2026-10-23):** `importlib.util.find_spec` con el venv (`-I`, desde fuera de `codigo\`) para `camera`, `vision`, `transport`, `calibration`, `diagnostics`, `gui`, `slicer`, `profiles`, `data`, `archive`, `historico`, `tracker`, `tests`, `config`, `paths`, `detection`, `pose`, `tracking`, `filtering`, `backend`, `uvc`: ninguno existe. **`profile` sí choca:** es el módulo de la biblioteca estándar (`Lib\profile.py`, lo importa `cProfile`); por eso el cargador de perfiles no se llama `profile.py`.

**Context7 (2026-10-23), solo API:**
- OpenCV 4.13 (`/websites/opencv_4_13_0`): `waitKey(delay)` espera *al menos* `delay` ms según el planificador del sistema; `pollKey()` atiende los eventos de la ventana sin esperar; uno de los dos tiene que llamarse para que la ventana viva. `SOLVEPNP_IPPE_SQUARE` exige las 4 esquinas en el orden (−s/2, s/2), (s/2, s/2), (s/2, −s/2), (−s/2, −s/2): es el de `construir_object_points`. `solvePnPGeneric` da todas las soluciones con su error.
- Qt for Python 6 (`/websites/doc_qt_io_qtforpython-6`): el ejemplo oficial con OpenCV pasa `QImage` desde un `QThread` por señal y pinta con `QPixmap.fromImage` en el hilo de la GUI.
- 3D Slicer (`/websites/slicer_readthedocs_io_en`): observar `vtkMRMLTransformNode.TransformModifiedEvent` y leer `GetMatrixTransformToWorld`.
- pytest (`/websites/pytest_en_stable`): la opción `pythonpath` de `pytest.ini` añade carpetas, relativas al rootdir, a la cabeza de `sys.path`.
- pyigtl: Context7 no lo tiene. El plan no cambia sus llamadas (`OpenIGTLinkServer(port=)`, `TransformMessage(M, device_name=)`, `send_message`, `close`); la fase 4 las contrasta con el código instalado en el venv.
- La revisión no añade ninguna API: los nombres en inglés y `git mv` no la necesitan; `find_spec` es de la biblioteca estándar.

## La respuesta a las preguntas del spec

1. **Estructura (P8 = b: carpetas, paquetes y módulos en inglés).** Paquetes por responsabilidad bajo `codigo/`:
   - `camera/`: `backend.py` (era `camera_backend.py`), `uvc.py` (`camaras_uvc.py`), `controls.py` (`ajustes_camara.py`).
   - `vision/`: `detection.py`, `pose.py`, `filtering.py` (no `filter.py`, para no confundirlo con la función `filter`), `tracking.py` (el paso por frame: detección → pose → filtro).
   - `transport/`: `igtl.py`.
   - `tracker.py`: solo el bucle cámara → visión → envío → ventana.
   - `profiles/`: los perfiles YAML y, en `profiles/__init__.py`, la raíz del código, las carpetas y la carga de un perfil (una sola copia; hoy hay dos `cargar_config` iguales). No hay `profile.py`: choca con la biblioteca estándar.
   - `calibration/`: `calibrate_camera.py` (`calibrar_camara.py`), `check_scale.py` (`comprobar_escala.py`).
   - `diagnostics/`: `probe_camera.py` (`sondear_camara.py`), `measure_modes.py` (`medir_modos.py`), `identify_ids.py` (`identificar_ids.py`), `pose_log.py` (fase 1), `measure_window.py` (fase 6).
   - `gui/`: `panel.py`, `recipes.py` (`recetas.py`), `processes.py` (`procesos.py`), `status.py` (`estado.py`), `calibration_window.py` (`gui/calibracion.py`; otro nombre que el paquete `calibration` para no confundirlos), `profile_editor.py` (`perfil_editor.py`), `camera_probe.py` (`sonda_camara.py`). Sin el asistente del dodecaedro.
   - `slicer/`: los scripts de la consola de Slicer y su `README.md`.
   - **Los perfiles conservan su nombre:** `profiles/tracker_config_gs1.yaml` y `profiles/tracker_config_gs2.yaml`. Ya están en inglés; el panel los lista con `tracker_config*.yaml` y las recetas sacan de ahí el nombre corto `gs1`/`gs2`; renombrarlos no gana nada y cambia esas dos reglas.
   - `data/`: `intrinsecos_gs1_1280x960.yml`, `intrinsecos_gs2_1280x960.yml`, `tablero_calibracion.yaml`, con su nombre de hoy: el spec manda que los perfiles no cambien de contenido, y su `calibration_file: data/intrinsecos_gs1_1280x960.yml` no cambia de texto solo si el `.yml` conserva el nombre. Nada más en `data/`.
   - **El archivo se queda en `codigo/historico/`, no pasa a `archive/`:** la carpeta ya existe con cuatro iteraciones, y renombrarla movería el `*.nrrd` de `historico/iter2/`, que el spec y el principio 5 dejan quieto. Lo de esta meta va a `historico/iter4/`, con subcarpetas en inglés: `dodecahedron/`, `femto/`, `old_profiles/`, y su `README.md` (B38).
   - **Lo que no se renombra:** las funciones y variables de los módulos que solo se mueven (fase 3: cambia el sitio, no el cuerpo) y los nombres de los archivos de prueba que ya existen (los nombra `docs/PRUEBAS.md`). Lo nuevo de esta meta (módulos, clases, funciones, opciones de línea de comandos, pruebas) nace en inglés, y también las funciones que la fase 4 saca de `tracker.py`, que cambian de sitio y de llamadas de todos modos. Lo que queda en español va al BACKLOG.
   - **Cómo se lanzan (P1 = a):** `python -m <paquete>.<modulo>` desde `codigo\`, con el venv. `python -m tracker --config profiles\tracker_config_gs1.yaml`; `python -m gui.panel`; `python -m calibration.calibrate_camera ...`; `python -m calibration.check_scale ...`; `python -m diagnostics.identify_ids --config profiles\tracker_config_gs1.yaml`; `python -m diagnostics.probe_camera ...`; `python -m diagnostics.measure_modes ...`. `python -m` pone `codigo\` en `sys.path`; ningún script toca `sys.path`. La suite lo hace con `pythonpath = .` en `pytest.ini`.
   - **Cómo encuentran perfiles y `data/`:** `profiles.CODE_ROOT = Path(__file__).resolve().parent.parent`; toda ruta de un perfil es relativa a `codigo/`, nunca al CWD ni a la carpeta del perfil. Si la ruta no existe, se aborta con el nombre del perfil y la ruta (principio 7).
   - **La aceleración de MSMF:** `camera/__init__.py` importa `camera.uvc`, que la apaga. Todo punto de entrada que abre la cámara importa `camera` antes que nada que cargue cv2; una prueba lo comprueba en subproceso para cada uno (B28 queda cerrado también a mano).
2. **Qué va a `historico/` y qué se borra (P2 = a):** la lista de «Archivos», apartados «Se archivan» y «Se borran».
3. **Línea base y replay de Marker0 (P3 = a).** El tracker actual gana en la fase 1 dos opciones apagadas por defecto: `--record <npz>` (por frame: tiempo, ids y esquinas detectadas, y la pose de Marker0 que se envía) y `--no-window`. Con ellas se graban 30 s por cámara con Marker0 quieto a ~45 cm. El `.npz` tiene el formato de tablas del replay actual (`timestamps`, `frame_offsets`, `marker_ids`, `corners_2d`, `K`, `dist`) más las poses enviadas: ~2 700 frames pesan ~150 KB. Además se guarda un frame en gris de cada 30, sin pérdida (PNG), en `Claude outputs/grabaciones/003/` (fuera de git; ~90 por cámara, ~60 MB); de esos, 3 por cámara van a `tests/data/` (~2 MB en total, a confirmar con el tamaño real) para probar la detección. El replay corre la pose y el 1-Euro sobre las esquinas con los tiempos grabados y compara contra la referencia que da el código de hoy; la detección se compara sobre los 3 frames.
4. **El tiempo por frame (P6 del spec):** se mide en la fase 6, por etapa. Las opciones de la ventana, en el orden en que se probarían (una variable a la vez, principio 3):
   - a) `pollKey()` en vez de `waitKey(1)`: `waitKey` espera *al menos* 1 ms y en Windows lo normal es más (la hipótesis, sin medir: un tic del temporizador del sistema, ~15 ms, que con ~30 ms de trabajo da los ~21 fps de la meta 002);
   - b) mostrar a ritmo fijo (≤ 30 Hz) y atender el teclado en cada frame;
   - c) mostrar la imagen reducida (640×480) y dibujar menos;
   - d) un hilo de captura que deja siempre el último frame (la lectura espera ~11 ms a 90 fps y hoy no se solapa con el resto);
   - e) la ventana en un hilo propio que la crea y la atiende (HighGUI no admite repartir una ventana entre hilos);
   - f) `--no-window` como modo de operación (Slicer es la pantalla real);
   - g) ventana Qt (PySide6, `QImage` por señal): no se recomienda, mete Qt en el proceso del tracker.
5. **La pose de Marker0 (P6 = a):** se deja como está (IPPE_SQUARE, z > 0, 1-Euro solo en la posición, como hoy para un marker suelto). La línea base mide además la sd de la orientación y los saltos de más de 5° entre frames seguidos; si aparecen, va al BACKLOG.
6. **Slicer (P5 = b):** `codigo/slicer/receive_marker0.py`: crea (o reutiliza) el conector OpenIGTLink cliente a `localhost:18944`, espera `Marker0ToTracker`, cuenta sus `TransformModifiedEvent` durante N s y escribe su frecuencia, la última posición y si existe un nodo `DodecaedroToTracker`. `codigo/slicer/README.md`: cómo pegarlo. `documentos/MANUAL_simplificado.md` se mueve con `git mv` a `documentos/historico/MANUAL_simplificado.md` en la fase 2 (la misma que deja de enviar `DodecaedroToTracker`), sin tocar su texto; las referencias vivas a su ruta se ponen al día en la fase 5.
7. **Fases:** ocho, abajo; la línea base va primero.

## Archivos

**Se crean**
- `codigo/profiles/__init__.py`, `codigo/camera/__init__.py`, `codigo/vision/{__init__,detection,pose,filtering,tracking}.py`, `codigo/transport/{__init__,igtl}.py`, `codigo/calibration/__init__.py`, `codigo/diagnostics/__init__.py`, `codigo/gui/__init__.py`.
- `codigo/diagnostics/pose_log.py` (nace en la fase 1 como `iter4/pose_log.py`); `codigo/diagnostics/measure_window.py` (fase 6).
- `codigo/slicer/receive_marker0.py`, `codigo/slicer/README.md` (fase 2).
- `codigo/historico/iter4/README.md` (B38).
- `codigo/tests/data/marker0_gs1.npz`, `marker0_gs2.npz`, sus `_reference.npz` y `.json`, y `marker0_gs{1,2}_frames/` (3 PNG cada una).
- Pruebas: `test_pose_log.py`, `test_replay_marker0.py`, `test_vision.py`, `test_transport.py`, `test_tracker_loop.py`, `test_profiles.py`.
- `specs/003-arquitectura-tracker/resultados.md`: la línea base y los números de cada fase.

**Se mueven con `git mv`** (fase 3 salvo el manual; la lógica no cambia, solo imports y rutas)
- `iter4/tracker.py` → `tracker.py`; `iter4/camera_backend.py` → `camera/backend.py`; `iter4/camaras_uvc.py` → `camera/uvc.py`; `iter4/ajustes_camara.py` → `camera/controls.py`.
- `iter4/calibrar_camara.py` → `calibration/calibrate_camera.py`; `iter4/comprobar_escala.py` → `calibration/check_scale.py`.
- `iter4/sondear_camara.py` → `diagnostics/probe_camera.py`; `iter4/medir_modos.py` → `diagnostics/measure_modes.py`; `iter4/identificar_ids.py` → `diagnostics/identify_ids.py`; `iter4/pose_log.py` → `diagnostics/pose_log.py`.
- `iter4/gui/panel.py` → `gui/panel.py`; `recetas.py` → `gui/recipes.py`; `procesos.py` → `gui/processes.py`; `estado.py` → `gui/status.py`; `calibracion.py` → `gui/calibration_window.py`; `perfil_editor.py` → `gui/profile_editor.py`; `sonda_camara.py` → `gui/camera_probe.py`.
- `iter4/tracker_config_gs1.yaml`, `_gs2.yaml` → `profiles/` con el mismo nombre (cambia solo el comentario «Ruta relativa a iter4\» y, desde la fase 2, sin el bloque del dodecaedro).
- `iter4/data/intrinsecos_gs{1,2}_1280x960.yml`, `tablero_calibracion.yaml` → `data/`, con el mismo nombre.
- `documentos/MANUAL_simplificado.md` → `documentos/historico/MANUAL_simplificado.md` (fase 2; P5 = b).
- Los archivos de prueba que ya existen conservan su nombre; solo cambian sus imports.

**Se archivan** en `codigo/historico/iter4/` (fase 3; con `git mv` lo versionado y con `Move-Item` lo local, que sigue fuera de git; los archivos conservan su nombre de hoy: son registro)
- `dodecahedron/`: `captura_calibracion.py`, `calibrar_rigid_body.py`, `calibrar_topologia.py`, `generar_reference_dodecaedro.py`, `corregir_giro_esquinas.py`, `limpiar_captura_fantasmas.py`, `calibrar_tip_divot.py`, `gui/asistente.py`, `gui/ba_monitor.py`. Por qué: solo existen por el dodecaedro o el stylus, descartados.
- `dodecahedron/data/`: los 8 `reference_*.txt` versionados (v2, v2 calibrado, v2_fix, v2_real, real, doctor, teórica, stylus impreso), `respaldo_puntas/` y, locales, las `captura_ba*.npz`, `smoke_captura.npz`, `divot_samples.npz`, `poses_pivote*.npy`, las `StylusTipToDodecaedro*` y los `*_calibrado.txt`.
- `dodecahedron/tests/`: `test_calibrar_rigid_body.py`, `test_captura_calibracion.py`, `test_generar_reference_dodecaedro.py` (las 22 `xfail` de B17 están todas aquí), `test_replay.py` y `data/replay_v2_femto*`. Quedan como registro: pytest ya no los recoge (`testpaths = tests`) y sus imports no se reescriben.
- `dodecahedron/pose_rigid_body.py` (fase 4): `estimar_pose_rigid_body` y `cargar_rigid_body`, sacados de `tracker.py` con su nombre de hoy. Por qué: son la pose multi-marker; el instrumento nuevo de otra meta puede partir de aquí.
- `femto/`: `tracker_config.yaml`, `data/femtobolt_calibration.yml`, `data/diag_d2c/` y `data/diag_d2c_fuera/` (PNG), y `femto_backend.py` con la clase `FemtoBoltBackend` sacada de `camera_backend.py`. Por qué: ADR-025, solo valen gs1 y gs2; el replay y el selftest que la necesitaban se reemplazan.
- `old_profiles/`: los 5 de `iter4/data/historico/` y `data/camera_calibration_webcam.yml`.

**Se borran:** `iter4/Log/` y `codigo/Log/` (logs del SDK de Orbbec, ignorados); el `.bak` local del perfil gs2 pasa a `profiles/` (sigue ignorado). Nada versionado se borra.

**Se modifican**
- `iter4/tracker.py` (fase 1: `--record`, `--no-window`, `--save-frames`, `--frames-every`; fase 3: se mueve; fase 4: se parte; fase 6: `--timing`; fase 7: la ventana).
- `iter4/tracker_config_gs1.yaml` y `_gs2.yaml` (fase 2): fuera `rigid_bodies` y `rigid_bodies_quality`; lo demás (puerto, marca, controles, modo, `.yml`, markers, igtlink, filtro, debug) igual byte a byte.
- `gui/estado.py` → `gui/status.py`: la geometría y la punta dejan de contar para «Arrancar tracker» cuando el perfil no tiene `rigid_bodies` (fase 2); fuera los semáforos de geometría y punta, `DIR_ITER4` → `profiles` (fase 3).
- `gui/panel.py`: fuera «Asistente: dodecaedro nuevo…», «Calibrar punta (dock)…» y `DialogoDivot`; el selftest sin asistente y con gs1 desde `profiles/`.
- `gui/recetas.py` → `gui/recipes.py`: `-m` con los nombres nuevos en vez de rutas; fuera `receta_captura`, `receta_ba`, `receta_divot`, `receta_generar_teorica` y `BA_V2`; el selftest de recetas con gs1.
- `gui/calibration_window.py`, `gui/profile_editor.py`, `gui/camera_probe.py`: rutas por `profiles`.
- `diagnostics/measure_modes.py`: el tracking que mide usa `vision.tracking` con Marker0, no el dodecaedro (fase 4; B32 pedía no repetir el bucle).
- `camera/backend.py`: fuera `FemtoBoltBackend`; `create_backend` con `camera_type: femtobolt` aborta diciendo que está archivado. Lo de la webcam, igual.
- `tests/conftest.py`, `pytest.ini` (`pythonpath = .`), y todas las pruebas que importan por nombre suelto o leen `ITER4_DIR`; `test_aceleracion_msmf.py` (B28: el tracker la ve apagada); `test_compilan.py` (recorre los paquetes); `test_gui_headless.py`.
- `.gitignore`: las excepciones del v2 calibrado y de `respaldo_puntas` a su ruta nueva (`codigo/historico/iter4/dodecahedron/data/...`); `codigo/profiles/*.bak-*`.
- `codigo/readme.md`: los comandos nuevos.
- Docs (fase 5 y 8, por `cerrar-fase`): `docs/ARCHITECTURE.md` §3.2, §3.3, §3.4, §3.7, §4, §6 (con la ruta nueva del manual en sus líneas 78, 162 y 301); `docs/CONTEXT.md` §3, §4 (las trampas 13–17 pasan a decir que son del dodecaedro archivado), §6 (y la línea 192 del manual); `docs/BACKLOG.md` (las entradas abiertas que nombran el manual: 51, 65, 135). `CLAUDE.md` §1 y §5 y los cuatro archivos de `.claude/` que nombran `iter4`: los escribe la dirección o el autor con el texto que deja la fase 5.

## Funciones y clases

**Fase 1 (en `iter4/`)**
- `pose_log.PoseLog(path: Path, frames_dir: Path | None, frames_every: int)`: `add(t: float, ids: np.ndarray | None, corners: tuple, poses: dict[str, np.ndarray], gray: np.ndarray | None) -> None`; `save(K, dist, metadata: dict) -> Path`. Escribe el `.npz` de tablas y los PNG.
- `pose_log.summarize(npz_path: Path, name: str = "Marker0") -> dict`: frames, fps, fracción con pose, sd x/y/z, rango z, sd de orientación (°), saltos > 5°.
- `tracker.main()`: cuatro argumentos opcionales; sin ellos hace lo mismo que hoy.
- `tests/replay_util.py`: `run_marker0_replay(dataset: Path, profile: Path) -> dict` (pose individual + 1-Euro con los tiempos grabados, con las funciones del tracker) y `compare_marker0(result: dict, reference: dict) -> dict`; CLI `reference-marker0 --dataset --config --output [--overwrite]`.

**Fase 3**
- `profiles.CODE_ROOT`, `PROFILES_DIR`, `DATA_DIR`; `profiles.resolve_path(p: str) -> Path` (relativa a `codigo/`; `FileNotFoundError` si no existe); `profiles.load(path: str | Path) -> dict` (reemplaza a los dos `cargar_config`); `profiles.list_profiles() -> list[Path]`.

**Fase 4**
- `vision.detection.get_dictionary(name: str)`; `apply_detector_params(params, cfg_det: dict) -> None`; `create_detector(cfg_markers: dict) -> cv2.aruco.ArucoDetector` (con `CORNER_REFINE_SUBPIX`, como hoy; sin la rama de la API vieja, que OpenCV 4.11 no usa); `detect(detector, gray: np.ndarray, valid_ids: set[int]) -> tuple[tuple, np.ndarray | None]` (detecta y aplica la lista blanca).
- `vision.pose.build_object_points(size_mm: float) -> np.ndarray`; `estimate_single_pose(corners_2d, size_mm, K, dist) -> tuple | None`; `rvec_tvec_to_matrix(rvec, tvec) -> np.ndarray`. Cuerpos de `construir_object_points`, `estimar_pose_individual` y `rvec_tvec_a_matriz` sin cambios; solo el nombre.
- `vision.filtering.OneEuroFilter(min_cutoff=1.0, beta=0.0)` con `filter(x: float, t: float) -> float` (el cálculo de hoy); `PositionFilter(min_cutoff: float, beta: float)` con `filter(tvec: np.ndarray, t: float) -> np.ndarray` (los tres 1-Euro de hoy).
- `vision.tracking.MarkerPose` (dataclass: `id: int`, `name: str`, `size_mm: float`, `rvec`, `tvec`, `matrix: np.ndarray`, `corners: np.ndarray`).
- `vision.tracking.MarkerTracker(cfg_markers: dict, cfg_filtering: dict)`: `process(gray, t: float, K, dist) -> list[MarkerPose]`; `process_corners(detections: dict[int, np.ndarray], t: float, K, dist) -> list[MarkerPose]` (lo usan el replay y `measure_modes`).
- `transport.igtl.IgtlSender(port: int)`: `send(device_name: str, matrix: np.ndarray) -> None`; `close() -> None`. Con `send_video: true` el tracker aborta y dice por qué (CONTEXT §4.4; P7 = a).
- `tracker.main(argv: list[str] | None = None) -> int`: `--config` obligatorio (principio 7), `--record`, `--no-window`, `--save-frames`, `--frames-every`; `tracker.draw_poses(display, poses: list[MarkerPose], K, dist) -> None`. Se va `abrir_camara` (B27).
- `historico/iter4/dodecahedron/pose_rigid_body.py`: `estimar_pose_rigid_body` y `cargar_rigid_body`, tal cual.

**Fase 6**
- `diagnostics.pose_log.Stopwatch()`: `mark(stage: str) -> None`, `end_frame() -> None`, `summary() -> dict` (ms medio, p50 y p95 por etapa: captura, gris, detección, pose y filtro, envío, dibujo, imshow, teclado). `tracker --timing <json>`.

**Fase 7:** las funciones dependen de las opciones que elija el autor tras la fase 6; si es la a) + b), `tracker.Window(title: str, hz: float)` con `show(display) -> None` y `key() -> int`.

## Fases

Paso 1 es la arquitectura (fases 1–5); paso 2, la optimización (6–8). «No cambió» en todas: la suite en verde con su número y su tiempo, el selftest del panel y el replay de Marker0 (desde la fase 1).

### Fase 1 · Línea base de Marker0 en vivo, antes de mover nada — pesada
- Entrega: `iter4/pose_log.py`; las cuatro opciones de `tracker.py`; `replay_util` y `test_replay_marker0.py`; `test_pose_log.py`; los datasets y referencias de las dos cámaras; `resultados.md` con la tabla.
- En vivo con el autor, por cámara (gs1 y gs2), caja de luz nivel 2, Marker0 de 80 mm quieto a ~45 cm, Slicer conectado antes: 30 s con ventana y `--record`; 30 s `--no-window` y `--record`; y 30 s con ventana sin opciones (los fps del tracker de hoy, de su línea `[FPS] Promedio`).
- Criterio: por cámara, sd x, y, z, rango z, sd de orientación, saltos > 5°, fracción de frames con pose (≥ 95 % esperado) y fps con y sin ventana, en `resultados.md`; el replay de las esquinas grabadas da las poses que se enviaron en vivo, 0.0 mm / 0.0°; la detección sobre los 3 frames da las esquinas grabadas, 0.0 px; `test_replay.py` (dodecaedro) sigue igual; Slicer recibe `Marker0ToTracker` como antes.
- La cadena: las opciones vienen apagadas; sin ellas el bucle hace las mismas llamadas. Se comprueba con la suite, `test_replay.py` y la sesión en vivo con Slicer.

### Fase 2 · La cadena solo con Marker0 — pesada
- Requiere antes: el ADR del cambio del principio 6, escrito por la dirección.
- Entrega: perfiles gs1 y gs2 sin el bloque del dodecaedro; `estado.apto_para_tracker` sin la geometría cuando no hay `rigid_bodies`; `codigo/slicer/receive_marker0.py` y su `README.md` (nacen ya en su sitio: no los importa nada de `iter4/`); `git mv documentos/MANUAL_simplificado.md documentos/historico/MANUAL_simplificado.md`, sin tocar su texto.
- Criterio, en vivo con Slicer y cada cámara, con el dodecaedro a la vista a propósito: `Marker0ToTracker` llega y se mueve (el script de Slicer da su frecuencia, ≥ los fps con ventana de la fase 1 menos 10 %); no existe ni se crea `DodecaedroToTracker` en una escena nueva; al cerrar con `q`, «[Salida limpia]», ningún `python` del tracker vivo y el 18944 libre (`Get-NetTCPConnection`). Sin cámara: el replay de Marker0 en 0.0; el diff de cada perfil es solo el bloque quitado; el selftest deja «Arrancar tracker» habilitado con gs1; `git status` muestra el manual como renombrado (R100) y `documentos/MANUAL_simplificado.md` ya no existe.

### Fase 3 · La estructura nueva y el archivo — ligera (mover código), con las comprobaciones de la cadena
- Entrega: los movimientos de «Archivos» con `git mv`, con los nombres en inglés; `profiles/__init__.py`; imports por paquete; `-m` en las recetas; `pytest.ini` y `conftest.py`; `.gitignore`; `historico/iter4/README.md` (B38); `codigo/readme.md`.
- Antes de crear las carpetas: `importlib.util.find_spec` con el venv, desde fuera de `codigo\`, de `camera`, `vision`, `transport`, `calibration`, `diagnostics`, `gui`, `slicer`, `profiles`, `data`, `tracker` y `tests`: los once dan `None` (así dieron el 2026-10-23). Si alguno deja de dar `None` (paquete instalado después), la fase para y lo reporta.
- Criterio: `codigo/iter4/` no existe; `git grep -n iter4 -- codigo` solo da líneas dentro de `codigo/historico/` y textos que dicen de dónde viene algo (se listan con su número); los once nombres siguen sin chocar, y con `codigo\` en `sys.path` cada `find_spec` apunta a `codigo\` (ningún paquete instalado los tapa ni ellos tapan uno: `profile` no se usa); suite en verde (las 22 `xfail` se van con su código: `xfail` = 0); replay de Marker0 en 0.0; selftest; en vivo con el autor (~10 min): el panel lista gs1 y gs2, lanza el tracker (Slicer recibe `Marker0ToTracker`), «Verificar IDs», «Probar cámara» y la ventana de calibración compone sus tres recetas; cada proceso se detiene limpio.
- La cadena: el tracker se mueve sin tocar su cuerpo; replay, suite y la prueba en vivo con Slicer.

### Fase 4 · El tracker en piezas — pesada
- Entrega: `vision/`, `transport/`, el bucle nuevo de `tracker.py`, `pose_rigid_body.py` archivado, `measure_modes` sobre `MarkerTracker`; B27, B28, B22 y B34.
- Criterio: replay de Marker0 a través de `MarkerTracker.process_corners` en 0.0 mm / 0.0° (tolerancia de la prueba 1e-9 mm y 1e-9°: el mismo cálculo, solo cambia de sitio; si da distinto de 0.0 exacto se reporta el número); detección por `vision.detection` sobre los 3 frames, 0.0 px; pruebas sin cámara de cada pieza (pose recuperada de un cuadrado proyectado con K real < 1e-6 mm; 1-Euro igual al de antes sobre una serie fija; `IgtlSender` con un servidor falso manda `Marker0ToTracker` 4×4; el bucle con una cámara y un emisor falsos sale con `q` y cierra todo); B34: un fixture de `conftest.py` niega `create_backend` y `cv2.VideoCapture` a la suite, con su prueba; B22: 0 avisos de secuencia de escape; B28: `python -m tracker` a mano escribe «Aceleracion HW de MSMF apagada» y `test_aceleracion_msmf.py` lo fija; en vivo con Slicer, cada cámara, lanzado a mano y desde el panel: Marker0 llega y se mueve, salida limpia, puerto libre.
- La cadena: mismo nombre, mismo puerto, misma matriz (el replay compara la matriz que se envía); la sesión en vivo con Slicer.

### Fase 5 · Documentación del paso 1 — ligera
- Entrega: `ARCHITECTURE.md` con la estructura nueva (§3, §4 y §6, con fecha); `CONTEXT.md` §3, §4 y §6; el BACKLOG al día; las referencias vivas a `documentos/MANUAL_simplificado.md` apuntan a `documentos/historico/`; el texto propuesto para `CLAUDE.md` §1 y §5 y para `.claude/` en el reporte de la fase.
- Criterio: `git grep -n iter4 -- codigo CLAUDE.md docs ':!docs/history'` solo da referencias históricas (ADR, entradas cerradas, PRUEBAS, `historico/`), contadas y listadas en el reporte; `git grep -n "documentos/MANUAL_simplificado" -- docs/ARCHITECTURE.md docs/CONTEXT.md codigo` da 0 líneas; ninguna línea > 2 000 caracteres; los comandos de `CLAUDE.md` §5 corren con `--help` sin error.

### Fase 6 · Dónde se va el tiempo por frame — ligera (instrumentación apagada por defecto; no cambia lo que se envía)
- Entrega: `Stopwatch` y `tracker --timing`; un script sin cámara, `diagnostics/measure_window.py`, que cronometra `imshow` + `waitKey(1)` frente a `imshow` + `pollKey()` sobre un frame guardado (300 vueltas, con tope de tiempo); la propuesta de opciones para la fase 7.
- Criterio: en vivo, cada cámara, 30 s con ventana y 30 s sin ella, Slicer conectado: tabla de ms por etapa (media, p50, p95) cuya suma queda a ±10 % del tiempo por frame medido; `measure_window.py` con su número; replay en 0.0. El autor elige las opciones de la fase 7 a la vista de la tabla (se anota en `clarify.md`); si la tabla muestra que 60 fps no se alcanzan sin tocar la pose, el plan propone otro número y lo decide el autor.

### Fase 7 · Subir los fps con ventana — pesada
- Entrega: las opciones elegidas, aplicadas y medidas de una en una, en el orden de la pregunta 4.
- Criterio, en vivo con cada cámara a 1280×960, Marker0 quieto a ~45 cm, Slicer conectado: **≥ 60 fps de media en 30 s con ventana** (o el número que fije el autor tras la fase 6); sd z ≤ 1.10 × la de la fase 1, en cada cámara, medida con `--record` y `pose_log.summarize`; el script de Slicer da la frecuencia de `Marker0ToTracker`; replay en 0.0 (ninguna opción de la lista cambia la pose; si alguna lo hace, se declara antes). Salida limpia y puerto libre.
- La cadena: replay, la frecuencia medida dentro de Slicer y la salida limpia.

### Fase 8 · Cierre de la meta — ligera
- Entrega: `ARCHITECTURE.md` y `CONTEXT.md` §6 con el paso 2; `resultados.md` completo; el BACKLOG.
- Criterio: la lista del criterio de cierre del spec, punto por punto, con su número: suite y su tiempo, selftest, B28 a mano y desde el panel, en vivo con Slicer y cada cámara, salida limpia (ningún `python` del tracker vivo y el 18944 libre).

## Lo que va al BACKLOG

Se cierran: B17 (sus 22 pruebas se archivan con su código; fase 3), B18 (el replay de Marker0 cubre el 1-Euro; fase 1), B22, B27, B28 y B34 (fase 4), B32 (fase 7), B37 (por decisión del spec, al archivar el dodecaedro; fase 3), B38 (fase 3).

Entradas nuevas:
- **Instrumento y punta con un transform de nombre nuevo:** es la meta que el spec deja para después; `pose_rigid_body.py` archivado es el punto de partida. Prioridad media.
- **Runbook de Slicer con Marker0 y el registro nuevo:** el manual se archiva en `documentos/historico/` (P5 = b) y `codigo/slicer/README.md` solo cubre recibir Marker0; los runbooks se rehacen (ADR-025). Media.
- **Otros documentos del dodecaedro y la Femto en `documentos/`** (`GUIA_calibrar_dodecaedro_propio.md`, `convencion_dodecaedro_compartido.md`, `MANUAL_femtobolt.md`): siguen en su sitio; moverlos a `documentos/historico/` si estorban. Baja.
- **Identificadores en español dentro de los módulos que solo se movieron** (funciones, variables, mensajes de `camera/`, `calibration/`, `diagnostics/`, `gui/`) y los nombres de las pruebas que ya existían: `CLAUDE.md` pide identificadores en inglés; renombrarlos es un cambio aparte, con la suite como red. Baja.
- **Las pruebas archivadas en `historico/iter4/dodecahedron/tests/` no corren:** solo registro. Baja.
- **`femto_pruebas/`, `open3d` y `pyorbbecsdk2`:** siguen en el repo y en `requirements.txt` aunque el backend Femto se archive (P4 = a). Baja.
- **Detección en una región de interés tras el primer frame:** solo si la fase 7 no llega al número sin ella; cambia las esquinas y exige declararlo en el replay. Baja.
- **`calibration/` importa `_vigilante` de `diagnostics/probe_camera.py`:** dependencia cruzada heredada; moverla si estorba. Baja.
- Lo que la línea base muestre de la orientación de Marker0 (saltos de IPPE), si aparece. Prioridad según el número.

## ADR que se proponen

- **ADR-026 · La cadena publica solo `Marker0ToTracker`.** `DodecaedroToTracker` deja de enviarse; puerto 18944 y nombre de Marker0 iguales; los scripts de Slicer se versionan en `codigo/slicer/`; `MANUAL_simplificado.md` pasa a `documentos/historico/`. Cambia el principio 6, así que la dirección actualiza su texto en `docs/constitution.md` en el mismo cambio. Se escribe antes de la fase 2.
- **ADR-027 · El código vive en `codigo/` por responsabilidad, con nombres en inglés, y se lanza con `python -m`.** Paquetes `camera`, `vision`, `transport`, `calibration`, `diagnostics`, `gui`, `slicer`, `profiles`, y `data/`; rutas de los perfiles relativas a `codigo/`; `codigo/iter4/` desaparece; el dodecaedro y la Femto pasan a `codigo/historico/iter4/` (la carpeta del archivo conserva su nombre: renombrarla movería un `*.nrrd`); perfiles y `.yml` con su nombre de hoy. Consecuencia de ADR-025 y de las decisiones del autor del 2026-10-23 (P1, P2, P8). Antes de la fase 3.
- **ADR-028 (si hace falta) · Cómo muestra la ventana el tracker:** solo si la fase 7 adopta algo más que `pollKey` (un hilo, un ritmo fijo o ventana opcional por defecto). Al cerrar la fase 7.

## Preguntas abiertas

Ninguna. P1–P8 están respondidas en `clarify.md` (2026-10-23). Lo que esta revisión decide sin preguntar, por si el autor quiere otra cosa: el archivo sigue en `codigo/historico/` (no `archive/`); los perfiles y los `.yml` conservan su nombre; las funciones de los módulos que solo se mueven no se renombran (va al BACKLOG).

## Títulos de commit

1. «Graba la línea base de Marker0 y su replay (Fase 1)»
2. «Deja la cadena solo con Marker0 y archiva el manual del dodecaedro (Fase 2)»
3. «Ordena el código por responsabilidad y archiva el dodecaedro (Fase 3)»
4. «Parte el tracker en piezas con pruebas (Fase 4)»
5. «Documenta la estructura nueva (Fase 5)»
6. «Mide el tiempo por frame del tracker (Fase 6)»
7. «Sube los fps del tracker con ventana (Fase 7)»
8. «Cierra la meta 003 · Arquitectura y optimización del tracker»
