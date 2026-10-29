# Plan — Meta 006 · Grafo de factores óptico-inercial (primero, las dos cámaras)

Escrito por el agente de planificación el 2026-10-29, sin código, y rehecho el mismo día con las respuestas del autor a P8–P18 (`clarify.md`). Lo que el autor autoriza es este archivo. Lo que cambió respecto a la primera versión: se prueban las dos arquitecturas y se elige con números antes de construir la fusión en vivo (P9, fases 2–4); los extrínsecos salen por dos métodos y se comparan (P12, fase 5); la sincronía se prueba de dos maneras y se compara (P13, fase 7); no se mueve ninguna cámara de puerto (P17); el lanzamiento es un solo comando con las dos arquitecturas (P10, fase 8). Las preguntas nuevas son P19 y P20.

## Lo leído

- HEAD: `7d2ac24 Avisa en dirección de las peticiones pendientes (meta 005, fase 4)`. Árbol: `memory.md` modificado, `specs/006-grafo-factores/` y el PDF sin seguimiento.
- `docs/constitution.md`, `memory.md` y `docs/CONTEXT.md` (§4: trampas 1–5, 10, 18–20; §6: los números de la meta 003). `spec.md`, `clarify.md` (P1–P18, todas contestadas) y `tasks.md`, completos.
- `docs/ARCHITECTURE.md` §3.1, §3.2, §3.3, §3.4, §3.5, §6 y §7. Índices de `DECISIONS.md` (hasta ADR-034), `BACKLOG.md` (B07–B65) y `PRUEBAS.md` (P01–P05). `specs/003-arquitectura-tracker/resultados.md`: sd x/y/z por cámara, fps con y sin ventana, B55.
- Código: `tracker.py` (395 líneas; `parse_args` y `main` releídos en esta versión), `transport/igtl.py` (entero: `IgtlSender.send(device_name, matrix)` crea `TransformMessage(M, device_name=…)` sin `timestamp`), `vision/tracking.py` (`MarkerTracker(cfg_markers, cfg_filtering)`: con `None`, sin 1-Euro), `vision/pose.py`, `camera/grabber.py`, `diagnostics/pose_log.py` (`PoseLog.add(t, ids, corners, …)`, `load_recording`, `summarize`, `Stopwatch`), `tests/replay_util.py`, `tests/synthetic.py`, `tests/test_tracker_loop.py`, `calibration/calibrate_camera.py` (firmas), `gui/recipes.py` (firmas), `profiles/tracker_config_gs1.yaml` y `_gs2.yaml`, `data/tablero_calibracion.yaml`, `requirements.txt`. Los dos perfiles publican en `transforms_port: 18944` y reservan `video_port: 18945`; gs1 cuelga de `…#USB(11)#USB(3)` y gs2 de `…#USB(11)#USB(4)`: el mismo hub (P17: no se mueven). En el venv: numpy 1.26.4, scipy 1.17.1, opencv-python 4.11.0.86, pyigtl 0.3.1; gtsam y psutil no están.
- Context7 (solo preguntas de API; no salió ninguna ruta ni dato del proyecto):
  - `/borglab/gtsam` (4.3a1): `IncrementalFixedLagSmoother(lag, ISAM2Params)` y `BatchFixedLagSmoother(lag)` con `update(factores, valores, {clave: tiempo})` y `calculateEstimate()`; `PriorFactorPose3`, `BetweenFactorPose3`; `noiseModel.Robust.Create(mEstimator.Huber(k), Gaussian.Covariance(S))`; `Pose3` con tangente `[ω, ρ]` y retracción por la derecha. Las ruedas de Python se construyen solo para Linux y macOS (P8).
  - `/websites/opencv`: `cv.stereoCalibrate(..., flags=CALIB_FIX_INTRINSIC)` → `R, T` (x2 = R·x1 + T) y `perViewErrors`; `stereoCalibrateExtended` da `rvecs, tvecs` por vista; `solvePnPGeneric` con `SOLVEPNP_IPPE_SQUARE` da las dos soluciones con su error.
  - `/lassoan/pyigtl` (consultado en esta versión, para la arquitectura de dos trackers): `TransformMessage(matrix, timestamp=None, device_name=None)` guarda la matriz en float32; `OpenIGTLinkClient(host, port)`; **el cliente guarda solo el último mensaje de cada `device_name`** (`incoming_messages[device_name] = message`, el nuevo pisa al anterior) y `wait_for_message` sondea con `time.sleep(0.01)`; `get_latest_messages()` da uno por dispositivo y vacía. Consecuencia: un fusionador que lea con el cliente tal cual perdería las medidas que llegan juntas en una ráfaga del tic de 15.6 ms (B54); hace falta un lector que no pise (fase 3). Las unidades exactas del `timestamp` (el docstring dice «milliseconds since 1970») se leen en el fuente instalado en la fase 3.
  - `/scipy/scipy`: `scipy.spatial.transform.Rotation.mean` (desde 1.4) para la media de rotaciones del método de Marker0 (fase 5).
- Índices de paquetes (consulta de solo lectura a PyPI y anaconda.org, 2026-10-29): gtsam no tiene rueda para Windows en PyPI; conda-forge tiene `gtsam 4.3.0` win-64 py311 (numpy 2). Respuesta del autor: P8 (a).
- Monografía de Dellaert y Kaess, solo §5.3.2 (ventana fija y marginalización) y §7.4 (funciones de error robustas).
- El GitHub MCP no está disponible en esta sesión. En la fase 7 `desarrollo` puede usarlo, si está, para implementaciones de referencia, con la regla del principio 5.

## La idea en una línea

Se construyen las dos maneras de tener las dos cámaras a la vez, (A) un proceso con las dos y (B) dos trackers que mandan su pose cruda con la hora de captura a un colector, y se mide en las dos lo mismo en una sesión; la que gana con los umbrales de la fase 4 lleva la fusión en vivo y va a un ADR. La fusión es la misma en las dos: las poses de gs2 llevadas a gs1 con los extrínsecos, en un grafo de ventana fija (GTSAM) con factores de pose y su covarianza, y la pose estimada se publica como `Marker0ToTracker` en el frame de gs1 (P11). Sin `--fusion`, el tracker hace lo de hoy.

## Las preguntas del spec, contestadas

- **Un proceso o tres (P9): se prueban los dos y decide la fase 4.**
  - **(A) Un proceso:** dos `FrameGrabber` (los de hoy) y un hilo de detección y PnP por cámara; las dos horas son del mismo `perf_counter`; OpenCV suelta el GIL en `cvtColor`, `detectMarkers` y `solvePnP`. Código nuevo en `fusion/`; `tracker.py` solo gana el desvío de `--fusion`.
  - **(B) Dos trackers y un colector:** cada tracker es el de hoy con una opción nueva, `--feed <puerto>`, que publica la pose cruda (sin 1-Euro) de su cámara con la hora de captura en el `timestamp` del mensaje, en un puerto propio (gs1 18946, gs2 18947; nunca 18944 ni 18945). El colector, en el proceso padre, se conecta a los dos como cliente con un lector que no pisa mensajes (ver Context7) y entrega las medidas a la fusión. La hora solo sirve si `perf_counter` es el mismo reloj en los tres procesos (en Windows es `QueryPerformanceCounter`, del sistema): se mide en la fase 3 y, si no, el colector corrige el desfase de cada hijo al arrancar.
  - **Qué se mide en las dos, en la misma sesión (fase 4):** fps de cada cámara; medidas por segundo que llegan a la entrada de la fusión y las que se pierden; |t1 − t2| de las parejas y el desfase δ moviendo el marker; la latencia de la hora de captura a la entrada de la fusión (p50, p95, máx.); la CPU de la máquina; la sd z cruda de cada cámara frente a la de una cámara sola; el arranque (procesos, puertos, segundos del comando a la primera pareja) y la parada limpia; las líneas que cambian en `tracker.py`.
  - **Con qué umbral se elige:** en «Fase 4». En corto: las dos tienen que pasar los mínimos; si las dos pasan, gana (B), la preferencia del autor, salvo que añada más de 10 ms de latencia p95, más del 30 % de CPU o más de 10 s de arranque frente a (A).
- **La sincronía (P13): los dos métodos, comparados en la fase 7.** (a) Emparejar por hora: la medida de gs2 más cercana a la de gs1 dentro de medio periodo (5.5 ms a 90 fps); la que queda sola entra sola; δ medido en la fase 6 y, si |δ| > 2 ms, corrección fija por cámara en el perfil. (b) Un nodo por medida: cada medida de cada cámara es una variable en su hora, unida a la anterior (de la cámara que sea) por el factor de movimiento; sin emparejar ni corregir δ más que con la hora. Moviéndose a 50 mm/s, 5.5 ms son 0.28 mm: (b) solo gana si se nota moviéndose; en reposo dan lo mismo.
- **Los extrínsecos (P12, P18): los dos métodos, comparados en las fases 5 y 6.** (1) `cv2.stereoCalibrate` con `CALIB_FIX_INTRINSIC` y el tablero de la meta 002 (9×6, 24.86 mm) visto por las dos a la vez, ≥ 15 parejas y 3 de control. (2) Marker0 quieto en 10 posiciones que no son las 5 de la validación (P16): por posición, T_gs1←gs2 = T_gs1←M · (T_gs2←M)⁻¹ con la pose media; luego la media de las 10 (rotación con `Rotation.mean`, traslación con la media) y su dispersión. Se comparan: ΔR, Δt y lo que cada uno mueve un punto a 37 cm. Se validan los dos con lo mismo, aparte de su ajuste: la distancia triangulada del tablero (independiente de Marker0) y el criterio 1 en las 5 posiciones (que no es independiente para el método 2: hereda la escala de cada cámara, B35). Archivo: `data/extrinsecos_gs1_gs2_pinzas.yml` (P18), con el método vigente arriba y el otro, con la comparación, en un bloque `alternativa`.
- **El modelo del grafo.** Con emparejado: una variable `X_k = T_gs1←Marker0` por pareja y, por cada cámara que vio el marker, un `PriorFactorPose3(X_k, T_gs1←cam · Z_cam)` con ruido `Robust(Huber, Gaussian.Covariance(Σ))`. Con un nodo por medida: una variable por medida con un solo factor de pose. Σ = σ_px² (JᵀJ)⁻¹, con J la jacobiana de la reproyección de las 4 esquinas del modelo respecto a una perturbación por la derecha de la pose: solo necesita la pose, el tamaño y los intrínsecos, así que sirve igual en (A) y en (B), que no manda esquinas. Por ser por la derecha, Σ no cambia al llevarla a gs1, y recoge que la profundidad es el eje débil de cada cámara. σ_px se ajusta en la fase 6 a la sd en reposo. Entre variables seguidas, un `BetweenFactorPose3` de identidad con ruido q·√Δt (q infinito lo apaga). Ventana fija de `lag` s (0.1 s) con `IncrementalFixedLagSmoother`.
- **Outliers y la ambigüedad de IPPE.** Antes de añadir una medida, su distancia de Mahalanobis a la última estimación: si pasa de χ²₆(0.999) = 22.5 se prueba la otra solución de IPPE, si la hay; si no, se descarta y se cuenta. En (A) la otra solución sale de `solvePnPGeneric` sobre las esquinas; en (B) no llega (el tracker manda una pose): se descarta. Cuánto importa se mide en la fase 7 sobre las grabaciones (que guardan las esquinas): la fracción de medidas que solo se salvan con la otra solución. Sin predicción (al arrancar o tras 0.5 s sin marker) se acepta y, con las dos cámaras, se exige que coincidan.
- **El 1-Euro con la fusión encendida (P14).** Las cámaras dan la pose cruda; la fusión suaviza con su factor de movimiento; el 1-Euro, después de la fusión y apagado por defecto. El 30 % se mide sin ningún suavizado temporal: fusión por instante (emparejado, sin factor de movimiento) frente a la mejor cámara cruda. Si gana el nodo por medida, ver P20.
- **El frame común (P11).** «Tracker» es el frame de gs1; `Marker0ToTracker`, el 18944 y la jerarquía no cambian; ADR y verificación en vivo con Slicer (fase 9).
- **El desarrollo fuera de línea.** Grabación doble: una carpeta con `gs1.npz` y `gs2.npz` en el formato de `PoseLog` de hoy (esquinas, poses crudas, horas de captura) y un `meta.json` con el reloj, la arquitectura y, en (B), las horas de llegada al colector. Las dos arquitecturas graban en ese formato: en (A) lo escribe `fusion.record`; en (B), cada tracker con su `--record` de hoy y el colector su `arrivals.npz`. Todo el grafo se mide antes sobre ellas con `python -m fusion.replay` (P4).
- **La dependencia (P8).** Entorno de conda-forge (miniforge) aparte con Python 3.11 y `gtsam 4.3.0`, medido en la fase 1 sin tocar `.venv`; las fases 2 a 6 no necesitan gtsam y van en `.venv`.
- **La estructura del autor.** No bloquea nada. Cuando llegue, la fase 5b repite las sesiones en vivo de las fases 5 y 6 sobre ella, sin código.

## Archivos

Se crean (los de (B) llevan «B»; si (B) pierde, P19):

- `codigo/fusion/__init__.py` — el paquete; no importa gtsam al cargarse (solo `fusion.graph` lo hace).
- `codigo/fusion/config.py` — el perfil de fusión: arquitectura (`proceso` o `trackers`), los dos perfiles de cámara, los puertos de los hijos (B), los extrínsecos, el método de sincronía (`pareja` o `nodo_por_medida`), tolerancia y desfases, σ_px, k del Huber, q, lag, umbral de Mahalanobis, el 1-Euro de salida y los topes de tiempo. Valida y aborta con el campo y el archivo (principio 7).
- `codigo/fusion/dual_log.py` — el formato de la grabación doble, leerla y escribir su `meta.json`; lo usan las dos arquitecturas.
- `codigo/fusion/capture.py` — (A) las dos cámaras en un proceso: un `FrameGrabber` y un hilo de detección por cámara, abiertas en orden. Queda aunque (A) pierda: la usa `calibrate_extrinsics` para las parejas del tablero.
- `codigo/fusion/feeds.py` — B: lanza y para los dos trackers hijos (`python -m tracker --config … --feed … --no-window --stop-stdin`), con tope y `terminate()` (principio 9).
- `codigo/fusion/collector.py` — B: el lector de los dos puertos, que no pisa mensajes, con la hora de llegada.
- `codigo/fusion/clockcheck.py` — B: CLI que mide si `perf_counter` es el mismo reloj en dos procesos.
- `codigo/fusion/record.py` — CLI: graba las dos cámaras con la arquitectura del perfil, sin Slicer y sin fusión, con `--duration` obligatorio.
- `codigo/fusion/archcompare.py` — CLI: resume las corridas de la fase 4 y aplica los umbrales; escribe el JSON de la decisión.
- `codigo/fusion/extrinsics.py` — leer y escribir el `.yml` de extrínsecos con el sha256 de los intrínsecos.
- `codigo/fusion/extrinsics_marker.py` — CLI: los extrínsecos por Marker0 desde grabaciones dobles en N posiciones, y la comparación con los del tablero.
- `codigo/fusion/measurements.py`, `pairing.py`, `sync.py`, `metrics.py` — la medida y su covarianza, el emparejado, el desfase δ, las métricas de los criterios.
- `codigo/fusion/sources.py`, `graph.py` — la fuente de factores y el grafo, con los dos métodos de sincronía.
- `codigo/fusion/replay.py` — CLI: la fusión sobre una grabación doble, con tapado simulado.
- `codigo/fusion/runner.py` — el bucle en vivo de la arquitectura elegida (fase 8).
- `codigo/calibration/calibrate_extrinsics.py` — CLI: parejas del tablero, `stereoCalibrate`, las validaciones; `--desde-vistas` sin cámara.
- `codigo/profiles/fusion_gs1_gs2.yaml`; `codigo/data/extrinsecos_gs1_gs2_pinzas.yml` (fase 5).
- `codigo/tests/test_fusion_*.py` (config, dual_log, capture, feeds, collector, archcompare, extrinsics, measurements, pairing, sync, graph, replay, runner) y `test_calibrate_extrinsics.py`, sin cámara: dos cámaras sintéticas con verdad conocida (sobre `tests/synthetic.py`), trackers hijos falsos y un servidor OpenIGTLink local para el colector.
- `codigo/tests/data/fusion_gs1_gs2/` — una grabación doble corta (~10 s, < 1 MB, sin frames) y la referencia de su fusión.

Se modifican:

- `codigo/tracker.py` — fase 3 (B): `--feed <puerto>`, que exige `--config`, rechaza 18944 y el `video_port` del perfil, crea el `MarkerTracker` sin filtrado y manda la hora de captura en el `timestamp`; fase 8: `--fusion <perfil>`, excluyente con `--config`, y `main` delega en `fusion.runner.run` antes de leer ningún perfil. Sin las dos opciones, el bucle no cambia.
- `codigo/transport/igtl.py` — fase 3 (B): `send(device_name, matrix, timestamp=None)`; con `None`, el mensaje es el de hoy.
- `codigo/requirements.txt` — la nota del entorno de conda-forge y gtsam (fase 8, con el ADR del entorno).
- `codigo/tests/test_tracker_loop.py` y `tests/test_igtl*.py` (el que haya) — casos nuevos para `--feed`, `timestamp` y `--fusion`; los de hoy, sin tocar.
- Al cerrar (fase 10): `docs/ARCHITECTURE.md` §3, §6 y §7, `docs/CONTEXT.md` §6, `codigo/readme.md`; los ADR y el BACKLOG, la dirección; `docs/PRUEBAS.md`, el agente `pruebas`.

No se tocan: `vision/`, `camera/`, `profiles/tracker_config_gs{1,2}.yaml` (ni su `usb_port_windows`, P17), los intrínsecos, `codigo/slicer/` ni `gui/` (el botón de la fusión, al BACKLOG).

## Funciones y clases

`fusion/config.py`
- `@dataclass(frozen=True) class FusionConfig` — `architecture: str` (`"proceso"` | `"trackers"`), `camera_profiles: dict[str, Path]`, `feed_ports: dict[str, int]`, `reference: str` (`"gs1"`), `extrinsics_file: Path | None` (None solo para `fusion.record`), `sync_mode: str` (`"pareja"` | `"nodo_por_medida"`), `pair_tolerance_s: float`, `time_offset_s: dict[str, float]`, `sigma_px: dict[str, float]`, `huber_k: float`, `motion_sigma_rot_deg_sqrt_s: float | None`, `motion_sigma_mm_sqrt_s: float | None`, `lag_s: float`, `mahalanobis_gate: float`, `lost_after_s: float`, `output_filter: dict | None`, `update_budget_ms: float`, `publish_name: str` (`"Marker0"`).
- `load_fusion_profile(path: Path, need_extrinsics: bool = True) -> FusionConfig`.

`fusion/dual_log.py`
- `write_meta(folder: Path, info: dict) -> Path`; `load_dual_recording(folder: Path) -> dict` (las dos `load_recording` de hoy, el `meta.json` y, si está, `arrivals.npz`).

`fusion/capture.py` (A)
- `class CameraPipeline(name: str, profile_path: Path)` — su backend, su `FrameGrabber` y su `MarkerTracker(cfg["markers"], None)`; un hilo detecta y mide; deja `(t_capture, t_ready, ids, corners, gray | None, pose | None)` en una cola acotada; `start()`, `stop(timeout_s) -> bool`, contadores.
- `class DualCapture(cfg: FusionConfig)` — dos `CameraPipeline` abiertas en orden; `start()`, `get(timeout_s)`, `stop()` en un `finally`.

`fusion/feeds.py` (B)
- `child_command(name: str, profile: Path, port: int, record: Path | None) -> list[str]`.
- `class TrackerFeeds(cfg: FusionConfig, record_dir: Path | None)` — `start()`, `alive() -> dict[str, bool]`, `stop(timeout_s: float) -> dict[str, int]` («q» por la entrada estándar, espera con tope, `terminate()`, `kill()`; devuelve los códigos de salida).

`fusion/collector.py` (B)
- `@dataclass class FeedMessage` — `camera: str`, `t_capture: float`, `t_arrival: float`, `matrix: np.ndarray`.
- `class FeedCollector(ports: dict[str, int], connect_timeout_s: float)` — un cliente por puerto que encola cada mensaje en vez de pisarlo (subclase de `pyigtl.OpenIGTLinkClient` en el punto donde guarda el mensaje entrante; el nombre del método se confirma en el fuente instalado); `start() -> bool`, `get(timeout_s) -> FeedMessage | None`, `stop()`, contadores `received`.
- `fusion/clockcheck.py`: `measure_offset(n: int = 1000) -> dict` — lanza un hijo que devuelve su `perf_counter` por la tubería; offset = t_hijo − (t_ida + t_vuelta)/2, con p50 y máx.; `main(argv) -> int`.

`fusion/record.py`
- `main(argv: list[str] | None = None) -> int` — `--fusion`, `--output <carpeta>`, `--duration` (obligatorio), `--save-frames`, `--frames-every`, `--architecture` (pisa la del perfil, para la fase 4).

`fusion/archcompare.py`
- `summarize_run(folder: Path, cpu_csv: Path | None) -> dict` — las medidas de «Fase 4».
- `decide(runs: dict[str, list[dict]], thresholds: dict) -> dict` — mínimos, umbrales y el ganador, con el porqué.
- `main(argv) -> int` — `--runs`, `--cpu`, `--output <json>`.

`fusion/extrinsics.py`
- `@dataclass(frozen=True) class Extrinsics` — `T_ref_other: np.ndarray` (4×4, mm), `reference`, `other`, `method: str` (`"tablero"` | `"marker0"`), `rms_px: float | None`, `mount: str`, `intrinsics_sha256: dict[str, str]`, `validation: dict`, `alternative: dict | None`.
- `load_extrinsics(path: Path, intrinsics_files: dict[str, Path]) -> Extrinsics` — aborta si un sha256 no coincide; `save_extrinsics(path: Path, ext: Extrinsics) -> Path` — no pisa uno existente.

`fusion/extrinsics_marker.py`
- `from_positions(recordings: list[Path]) -> dict` — T por posición, la media y la dispersión (mm y °).
- `compare(T_a: np.ndarray, T_b: np.ndarray, points_mm: np.ndarray) -> dict` — ΔR, Δt y el desplazamiento de cada punto.
- `main(argv) -> int` — `--inputs`, `--tablero <yml>`, `--output`.

`calibration/calibrate_extrinsics.py`
- `calibrar_par(obj_points, img_a, img_b, K_a, d_a, K_b, d_b, shape, n_control: int = 3, semilla: int = 0) -> dict`; `distancias_trianguladas(img_a, img_b, K_a, d_a, K_b, d_b, R, T, cols, rows) -> dict`; `capturar_parejas(dual: DualCapture, cols, rows, limite_s, vistas_dir) -> list`; `main(argv) -> int` (`--fusion`, `--output`, `--vistas-dir`, `--desde-vistas`, `--timeout`, `--montaje`).

`fusion/measurements.py`
- `@dataclass class CameraMeasurement` — `camera`, `t`, `T_cam_marker` (4×4), `cov` (6×6, `[ω, ρ]`), `reproj_px: float | None`, `alternative: np.ndarray | None`.
- `ippe_solutions(corners, size_mm, K, dist) -> list[tuple[np.ndarray, float]]`; `pose_covariance(T_cam_marker, size_mm, K, dist, sigma_px) -> np.ndarray`; `from_corners(camera, t, corners, size_mm, K, dist, sigma_px) -> CameraMeasurement | None` (A); `from_pose(camera, t, T, size_mm, K, dist, sigma_px) -> CameraMeasurement` (B).

`fusion/pairing.py`
- `@dataclass class Pair` — `t`, `measurements: dict[str, CameraMeasurement]`; `class Pairer(tolerance_s, offsets_s)` con `push(m) -> list[Pair]` y `flush()`; `pair_batch(a, b, tolerance_s, offsets_s) -> list[Pair]`.

`fusion/sync.py`
- `pair_residuals(t_a, t_b, tolerance_s) -> dict`; `estimate_offset(t_a, P_a, t_b, P_b_in_a, search_ms: float, step_ms: float) -> dict`.

`fusion/metrics.py`
- `agreement(pairs, T_ref_other) -> dict`; `rest_sd(poses) -> dict`; `occlusion_jumps(fused, t_start, t_end) -> dict`; `update_times(fused) -> dict`; `latency(t_capture, t_ready) -> dict`; `motion_residuals(fused, measurements) -> dict` (RMS por cámara de cada medida frente a la trayectoria fusionada interpolada, para la fase 7).

`fusion/sources.py`
- `class FactorSource(Protocol)` — `name: str`; `factors(key: int, m) -> list`. `class ArucoPoseSource(name: str, T_ref_cam: np.ndarray, huber_k: float)`.

`fusion/graph.py`
- `@dataclass class FusedPose` — `t`, `matrix` (4×4), `cov | None`, `used`, `rejected`, `update_ms`.
- `class FusionGraph(cfg: FusionConfig, sources: dict[str, FactorSource])` — `update_pair(pair: Pair) -> FusedPose | None` (pareja); `update_measurement(m: CameraMeasurement) -> FusedPose | None` (nodo por medida); `reset()`; contadores `n_updates`, `n_rejected`, `n_rescued_ippe`, `n_resets`, `n_over_budget`.
- `mahalanobis(T_pred, cov_pred, T_meas, cov_meas) -> float`.

`fusion/replay.py`
- `run_fusion_replay(folder: Path, cfg: FusionConfig, drop: dict[str, tuple[float, float]] | None = None, sync_mode: str | None = None) -> dict`; `main(argv) -> int` (`--input`, `--fusion`, `--drop gs2:12.0-17.0`, `--sync-mode`, `--output <json>`).

`fusion/runner.py`
- `run(args: argparse.Namespace, argv: list[str] | None) -> int` — espera a Slicer en el 18944 antes de abrir ninguna cámara o lanzar ningún hijo (ADR-028: sin Slicer, código 3); luego (A) `DualCapture` o (B) `TrackerFeeds` + `FeedCollector`; emparejar o no, fusionar, enviar; `--duration`, `--stop-stdin`, `--timing`, `--record`, ventana opcional (A: una con las dos vistas a media resolución; B: sin vídeo, la ventana muestra solo la pose y los contadores).

`transport/igtl.py`
- `IgtlSender.send(device_name: str, matrix: np.ndarray, timestamp: float | None = None) -> bool`.

`tracker.py`
- `parse_args(argv)` — `--feed PORT` (fase 3) y `--fusion PERFIL` (fase 8, en un grupo excluyente con `--config`; uno obligatorio; `--feed` exige `--config`). Sin ellas, el `Namespace` tiene los campos de hoy más `feed=None` y `fusion=None`.
- `main(argv)` — primera línea nueva (fase 8): `if args.fusion: return fusion.runner.run(args, argv)` (import dentro del `if`). Con `--feed` (fase 3): el puerto es el de `--feed`, el `MarkerTracker` va sin filtrado y `sender.send(..., timestamp=t_capture)`; sin `--feed`, las mismas llamadas de hoy.

## Fases

Cada fase se presenta al autor antes de lanzarla. Lo que necesita cámara o Slicer se mide en una sesión en vivo con él, con los comandos de Slicer y de PowerShell juntos (regla del 2026-10-25), caja de luz al máximo, Marker0 de 80 mm (B55), a ~35–40 cm, las cámaras en sus puertos de siempre (P17). «No cambió» es siempre: suite en verde con su tiempo, replay de Marker0 de gs1 y gs2 en 0.0 mm / 0.0° (detección 0.0 px) y `python -m gui.panel --selftest`. La CPU se mide desde PowerShell con `Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples <s>` durante la corrida, más 30 s en reposo antes (sin dependencia nueva; psutil no está).

### Fase 1 · La dependencia: gtsam en Windows (ligera)

- **Qué:** P8 (a). Entorno de conda-forge (miniforge) en una carpeta aparte, Python 3.11, `gtsam 4.3.0` de conda-forge y el resto de `requirements.txt` por pip; `.venv` no se toca. Un script de humo fuera de `codigo/` (en `Claude outputs/fases/006/`).
- **Criterio:** `import gtsam` y las clases del plan existen; la suite pasa entera (618) con su tiempo y el replay de Marker0 da 0.0 mm / 0.0°; el humo (dos factores de pose y uno de movimiento por paso, lag 0.1 s, 10 000 pasos) da p95 ≤ 1 ms por actualización, y el mismo humo con un nodo por medida (dos variables por paso) p95 ≤ 1 ms. Lo que falle, con el paquete y la versión (numpy 2, open3d o pyorbbecsdk2, B45).
- **Cómo se mide:** comandos con tope de tiempo, sin cámara. El autor decide con el número si el proyecto pasa a ese entorno (ADR-038) antes de la fase 7.
- **Cadena:** no se toca.

### Fase 2 · Arquitectura A: las dos cámaras en un proceso (pesada)

- **Qué:** `fusion/config.py`, `fusion/dual_log.py`, `fusion/capture.py`, `fusion/record.py` (arquitectura `proceso`), `profiles/fusion_gs1_gs2.yaml` (sin extrínsecos todavía) y sus pruebas sin cámara.
- **Criterio (en vivo, 60 s sin ventana, Marker0 quieto visto por las dos):** cada cámara ≥ 85 fps y cada hilo de detección ≥ 85 Hz; ≥ 99 % de frames con pose en cada una; p95 de |t1 − t2| ≤ 5.6 ms; se cierran limpias (sin `python` vivo, las cámaras libres) con `--duration` y con Ctrl+C. Suite en verde.
- **Si no llega a 85 fps (P17):** no se mueve nada. Se mide una variable a la vez (solo captura de las dos; captura y detección) y la fase para con el número; decide el autor.
- **Cadena:** no se toca (archivos nuevos). «No cambió» completo.

### Fase 3 · Arquitectura B: dos trackers y un colector (pesada)

- **Qué:** `--feed` en `tracker.py`, `timestamp` en `IgtlSender.send`, `fusion/feeds.py`, `fusion/collector.py`, `fusion/clockcheck.py`, la arquitectura `trackers` de `fusion/record.py`, y sus pruebas (hijos falsos; un servidor local que manda 1 000 mensajes en ráfagas y el colector los recibe todos; el `timestamp` va y vuelve a ≤ 1 µs).
- **Criterio:** en la suite: sin `--feed`, los casos de hoy de `test_tracker_loop.py` sin tocar y el mensaje de `send` sin `timestamp` igual byte a byte al de hoy; `clockcheck` da |offset| p50 ≤ 0.1 ms (si no, el colector corrige el desfase de cada hijo y la fase lo dice). En vivo (60 s sin ventana, Marker0 quieto): cada tracker hijo ≥ 85 fps; el colector recibe ≥ 99.9 % de lo que mandan los hijos; ≥ 99 % de frames con pose; p95 de |t1 − t2| ≤ 5.6 ms con las horas de captura; parada limpia 3 de 3 (hijos cerrados, 18946 y 18947 libres, cámaras libres) con `--duration` y con Ctrl+C. Si no llega a 85 fps: como en la fase 2, sin mover nada.
- **Cadena (principio 6):** toca `tracker.py` y `transport/`. Sin `--feed`, el bucle hace las mismas llamadas: lo fijan los casos de hoy, el replay (0.0 mm / 0.0°) y el selftest. En vivo con Slicer, gs1 sin opciones: `Marker0ToTracker` en la raíz, sus Hz de la meta 003 (sin ventana ~65) y su pose; ningún nodo nuevo.

### Fase 4 · Elegir la arquitectura con números (ligera)

- **Qué:** `fusion/archcompare.py` y su prueba; una sesión en vivo con las dos, alternadas A, B, A, B (para que la luz o el calor no favorezcan a una), cada corrida 60 s sin ventana con Marker0 quieto más 20 s moviéndolo a mano; antes, 60 s de gs1 sola sin 1-Euro como referencia de sd. Los números van a `resultados.md` y la dirección escribe el ADR-035 con ellos.
- **Se mide en las dos:** fps de cada cámara; medidas/s a la entrada de la fusión y pérdidas; p95 de |t1 − t2| y δ (fase 6 lo afina); latencia de la hora de captura a la entrada de la fusión (A: hasta que el hilo principal la saca de la cola; B: hasta que llega al colector), p50, p95 y máx.; CPU media de la máquina menos la de reposo; sd z cruda de cada cámara frente a la de gs1 sola; procesos, puertos y segundos del comando a la primera pareja; parada limpia; líneas cambiadas en `tracker.py` (`git diff --stat`).
- **Mínimos (la que no los pasa queda fuera):** cada cámara ≥ 85 fps; ≥ 85 parejas/s a la entrada de la fusión; ≥ 99.9 % de las medidas llegan; p95 de |t1 − t2| ≤ 5.6 ms; sd z de cada cámara ≤ 1.10 × la de gs1 sola; parada limpia en todas las corridas.
- **Umbral de elección:** si las dos pasan los mínimos, gana B (la preferencia del autor: reusa el tracker de hoy) salvo que, frente a A, su latencia p95 sea más de 10 ms mayor, su CPU más de 1.3 veces la de A o su arranque pase de 10 s; entonces gana A. Los 10 ms: menos de un refresco de Slicer (~15 ms a 65 Hz, B54) y, moviendo la mano a 50 mm/s, 0.5 mm, el salto que admite el spec. Si solo una pasa los mínimos, gana esa. Si ninguna, la fase para con los números y decide el autor.
- **Criterio de la fase:** el JSON de `archcompare` con todas las medidas de las cuatro corridas, el ganador y el porqué; la diferencia entre las dos corridas de una misma arquitectura anotada (si una medida varía más que la diferencia entre A y B, se dice).
- **Si pierde B:** P19. **Cadena:** no se toca (si se retira `--feed`, fase 4b).

### Fase 4b · Retirar lo de la arquitectura que perdió (ligera; solo si pierde B y P19 lo pide)

- **Qué:** quitar `--feed`, el `timestamp` de `send`, `feeds.py`, `collector.py`, `clockcheck.py` y sus pruebas (`git rm` lo nuevo; `tracker.py` y `transport/igtl.py` vuelven al texto de HEAD antes de la fase 3). Si pierde A, no hay 4b: `capture.py` queda para la calibración del tablero y `record`.
- **Criterio:** `git diff` de `tracker.py` y `transport/igtl.py` contra el commit anterior a la fase 3 vacío; «no cambió» completo.

### Fase 5 · Los extrínsecos por los dos métodos (pesada)

- **Qué:** `calibration/calibrate_extrinsics.py`, `fusion/extrinsics.py`, `fusion/extrinsics_marker.py` y sus pruebas (dos cámaras sintéticas con R, T conocidos: el tablero y Marker0 en 10 posiciones). En vivo: las parejas del tablero (con `DualCapture`) y Marker0 quieto en 10 posiciones, 10 s cada una, distintas de las 5 de la fase 6 (con `fusion.record`).
- **Criterio:** en la suite, los dos métodos recuperan R y T sintéticos a < 0.01 mm y < 0.001° sin ruido. En vivo, tablero: RMS de `stereoCalibrate` ≤ 0.5 px con ≥ 15 parejas; reproyección de las 3 de control en gs2 ≤ 0.75 px; distancia triangulada entre esquinas opuestas de las vistas de control a ≤ 0.3 mm de 198.88 mm. Marker0: dispersión de las 10 estimaciones (sd) anotada en mm y °. La comparación: ΔR, Δt y el desplazamiento de las 5 posiciones de validación de un método al otro; y la distancia triangulada del tablero calculada también con los extrínsecos de Marker0. El `.yml` guarda el método del tablero arriba (provisional) y el de Marker0 en `alternativa`, con el sha256 de los dos intrínsecos; la fase 6 fija el vigente.
- **Cadena:** no se toca. «No cambió» completo.

### Fase 5b · Extrínsecos sobre la estructura del autor (ligera; opcional, cuando llegue)

- Repite las sesiones en vivo de las fases 5 y 6 sobre la estructura, con `--montaje estructura` y `data/extrinsecos_gs1_gs2_estructura.yml`; el perfil de fusión pasa a nombrarlo. Sin código. Si llega después del cierre, al BACKLOG.

### Fase 6 · Coincidencia, sincronía y ruido medidos (pesada)

- **Qué:** `fusion/measurements.py`, `pairing.py`, `sync.py`, `metrics.py`, la parte de `replay.py` que no necesita el grafo, y sus pruebas. En vivo, con la arquitectura ganadora: Marker0 quieto en 5 posiciones (P16: centro y cuatro a ~8 cm, dos inclinadas ~30°), 30 s cada una, y 3 corridas de 30 s moviéndolo a mano (lento, medio, rápido; quedan para la fase 7).
- **Criterio 1 del spec, con los dos extrínsecos:** en cada posición (≥ 2000 parejas), la media de la diferencia entre gs1 y gs2 llevada a gs1 **< 0.5 mm y < 0.2°**; cuenta la peor posición; pose cruda, sin filtros. **Vigente:** el que cumple el criterio 1 y da la distancia triangulada del tablero a ≤ 0.3 mm; si los dos, el del tablero (su validación es independiente de Marker0); si solo el de Marker0 cumple el criterio 1, se usa y se anota que su validación no es independiente (B35).
- **Además (números):** δ con resolución de 0.5 ms (sin corrección si |δ| ≤ 2 ms); σ_px por cámara y la sd predicha frente a la medida en las 5 posiciones (dentro de un factor 1.5); en la suite, `pair_batch` y `Pairer` dan lo mismo y la covarianza por la jacobiana coincide con la de Monte Carlo a ±10 %.
- **Si ninguno cumple el criterio 1:** se para y se diagnostica (principio 3): extrínsecos frente a la escala de cada cámara (B35: +0.27 y −0.37 mm en 80 mm, que a 37 cm puede dar ~1 mm en profundidad). Es el riesgo principal de la meta.
- **Cadena:** no se toca. «No cambió» completo.

### Fase 7 · La fusión fuera de línea, con los dos métodos de sincronía (pesada)

- **Qué:** `fusion/sources.py`, `graph.py` (los dos métodos), el resto de `replay.py`, `test_fusion_graph.py` y `test_fusion_replay.py`, en el entorno de la fase 1. q y lag se ajustan sobre las grabaciones de la fase 6.
- **Criterios (sobre las grabaciones de la fase 6):** criterio 2: en reposo, la sd de la posición fusionada por instante (emparejado, sin factor de movimiento ni 1-Euro, P14) **≥ 30 % menor** que la de la mejor cámara cruda, en las 5 posiciones; criterio 3 simulado, con los dos métodos: quitando las medidas de cada cámara 5 s (tres veces por cámara), la pose no se pierde y no salta **más de 0.5 mm**; p95 de la actualización ≤ 2 ms y máx. ≤ 5 ms con los dos; en la suite, la fusión recupera la verdad a < 0.01 mm sin ruido y la compuerta rechaza la solución de IPPE equivocada; el replay de la grabación corta reproduce su referencia a 0.0 mm / 0.0°. La fracción de medidas que solo salva la otra solución de IPPE, anotada (si gana B no se puede usar).
- **La comparación de la sincronía (P13):** en la suite, dos cámaras sintéticas con trayectoria conocida, un desfase δ conocido y velocidades de 50, 100 y 200 mm/s: error RMS frente a la verdad con cada método. En vivo: en las 3 corridas en movimiento, el RMS de los residuos de cada cámara frente a la trayectoria fusionada (`motion_residuals`), y en reposo, la sd publicada. **Gana el nodo por medida solo si** baja el error sintético a 100 mm/s y el residuo real al menos un 20 % cada uno, con p95 ≤ 2 ms y los criterios 2 y 3 cumplidos; si no, el emparejado (más simple). La decisión va a un ADR (ADR-036).
- **Cadena:** no se toca. «No cambió» completo.

### Fase 8 · La fusión en el tracker, apagada por defecto (pesada)

- **Qué:** `fusion/runner.py` con la arquitectura y la sincronía elegidas, `--fusion` en `tracker.py`, `requirements.txt` (P8, ADR-038), `test_fusion_runner.py` (cámaras o hijos falsos, emisor falso, tapado de una) y el caso nuevo de `test_tracker_loop.py`. Un solo comando con las dos arquitecturas (P10): `python -m tracker --fusion profiles\fusion_gs1_gs2.yaml`; con B, el runner espera a Slicer, lanza los dos hijos con `--feed`, los lee con el colector y los para al salir.
- **Criterio:** suite en verde con su tiempo; los casos de hoy de `test_tracker_loop.py` y el replay de Marker0 de gs1 y gs2, sin cambios, en 0.0 mm / 0.0°; el selftest del panel; con cámaras (o hijos) falsos, lo que el runner envía como `Marker0ToTracker` es lo que da `fusion.replay` sobre lo que grabó (0.0 mm / 0.0°); con `--fusion` y sin Slicer, código 3 sin abrir ninguna cámara ni lanzar ningún hijo; `--help` muestra `--fusion`; un perfil de fusión mal formado aborta con el campo; con B, tras Ctrl+C, «q» y `--duration`, ningún proceso hijo vivo.
- **Cadena (principio 6):** sin `--fusion` (y sin `--feed`) el bucle no cambia: lo fijan los casos de hoy y el replay; nombre, puerto y jerarquía, los mismos. La verificación en vivo con Slicer, en la fase 9.

### Fase 9 · La fusión en vivo, con Slicer (ligera)

- **Qué:** solo medir, con el autor; lo que falle abre una fase nueva.
- **Criterios:** criterio 2 en vivo (por instante, como en la fase 7): ≥ 30 % menor que la mejor cámara cruda, misma sesión y posición, 60 s, y aparte la sd publicada; criterio 3 en vivo: tapar con la mano cada cámara 5 s, tres veces cada una: sin pérdida y salto ≤ 0.5 mm al tapar y al destapar; tiempo real (P15): sin ventana ≥ 85 poses fusionadas/s con las dos cámaras ≥ 85 fps y p95 de la actualización ≤ 3 ms (máx. 5 ms); con ventana ≥ 50/s; Slicer ≥ 50 Hz (techo ~65, B54).
- **Cadena (principio 6):** en Slicer, `receive_marker0.py` con la escena cerrada: gs1 sola (sin `--fusion`) da sus Hz de la meta 003 y su pose; con la fusión, el mismo nodo `Marker0ToTracker` en la raíz, ningún nodo nuevo, sus Hz, y la media de la pose fusionada a < 0.5 mm y < 0.2° de la de gs1 sola con el marker quieto; al salir, 18944 (y con B, 18946 y 18947) libres y las dos cámaras libres.

### Fase 10 · Cierre de la meta (ligera)

- **Qué:** `specs/006-grafo-factores/resultados.md` con todos los números (las dos arquitecturas, los dos extrínsecos, los dos métodos de sincronía); `docs/ARCHITECTURE.md` §3, §6 y §7; `docs/CONTEXT.md` §6; `codigo/readme.md`; `memory.md`. La dirección escribe los ADR y el BACKLOG; `pruebas`, su ronda.
- **Criterio:** cada criterio del spec con su número y «cumple» o no; «no cambió» completo con su tiempo; 0 líneas de más de 2 000 caracteres.

## Lo que va al BACKLOG

- **Extrínsecos sobre la estructura del autor** (media), si llega después del cierre: la fase 5b.
- **Factores de reproyección de las esquinas en vez de factores de pose** (media): sin la aproximación gaussiana del PnP ni la ambigüedad de IPPE; un `CustomFactor` y medir su coste. Con B, además, los hijos tendrían que mandar las esquinas.
- **El botón de la fusión en el panel** (media): una receta en `gui/recipes.py` y el semáforo de extrínsecos; con B, que «Detener» pare también a los hijos.
- **La otra solución de IPPE con B** (baja; según la fracción de la fase 7): que el hijo la mande como segundo mensaje.
- **El método de sincronía que pierda en la fase 7** (baja): con su número, por si cambian las cámaras o la velocidad de uso.
- **La arquitectura que pierda en la fase 4** (baja): sus números en `resultados.md`; volver a ella solo si cambia lo que la hizo perder (p. ej. más cámaras o una cámara en otra máquina, que favorecen a B).
- **Los extrínsecos como variable del grafo, o su incertidumbre en Σ** (baja).
- **La latencia absoluta cámara → Slicer** (baja): la fase 4 mide hasta la entrada de la fusión, no hasta Slicer.
- **Sincronía por hardware (disparo externo)** (baja): las SVPRO no lo dan.

## ADR que se proponen

- **ADR-035 · La arquitectura de las dos cámaras** (un proceso, o dos trackers con `--feed` y un colector), con los números y los umbrales de la fase 4; si gana B, también los puertos 18946 y 18947 y la hora de captura en el `timestamp`.
- **ADR-036 · La fusión de gs1 y gs2 en un grafo de factores de ventana fija (GTSAM),** con factores de pose y covarianza por la jacobiana, en `fusion/`, y el método de sincronía elegido en la fase 7; el tracker sin `--fusion` no cambia y no importa gtsam.
- **ADR-037 · Con la fusión encendida, «Tracker» es el frame de gs1;** `Marker0ToTracker`, el 18944 y la jerarquía no cambian (principio 6), con su verificación en vivo (fase 9).
- **ADR-038 · El entorno de gtsam en Windows** (P8, fase 1): el entorno de conda-forge; cambia `CLAUDE.md` §5 y `docs/EQUIPO.md`.
- **ADR-039 · Los extrínsecos son un dato versionado por montaje,** con el método vigente, el otro como alternativa, el sha256 de los intrínsecos y su validación aparte del ajuste; si un intrínseco cambia, la fusión no arranca.

## Preguntas abiertas

P19 y P20, al final de `clarify.md`. P19 para la fase 4b; P20, la fase 7. P8–P18 están contestadas y no se reabren.

## Títulos de commit

- Fase 1: «Comprueba gtsam en Windows en un entorno aparte (meta 006, fase 1)» — si la fase no deja archivos en git, no hay commit y se dice.
- Fase 2: «Captura las dos cámaras en un proceso y graba en doble (meta 006, fase 2)»
- Fase 3: «Añade los trackers que alimentan un colector con la hora de captura (meta 006, fase 3)»
- Fase 4: «Elige la arquitectura de las dos cámaras con números (meta 006, fase 4)»
- Fase 4b: «Retira la arquitectura de dos trackers (meta 006, fase 4b)»
- Fase 5: «Calibra los extrínsecos de gs2 por tablero y por Marker0 (meta 006, fase 5)»
- Fase 5b: «Calibra los extrínsecos sobre la estructura de las cámaras (meta 006, fase 5b)»
- Fase 6: «Mide la coincidencia, la sincronía y el ruido de las dos cámaras (meta 006, fase 6)»
- Fase 7: «Fusiona las dos cámaras fuera de línea y compara la sincronía (meta 006, fase 7)»
- Fase 8: «Añade la fusión al tracker, apagada por defecto (meta 006, fase 8)»
- Fase 9: «Anota la fusión en vivo con Slicer (meta 006, fase 9)»
- Fase 10: «Cierra la meta 006 · Grafo de factores con las dos cámaras»
