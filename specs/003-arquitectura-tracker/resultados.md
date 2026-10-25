# Resultados — Meta 003 · Arquitectura y optimización del tracker

Los números de cada fase, con su fecha. Las casillas de `tasks.md` remiten aquí.

## Fase 1 · Línea base de Marker0 en vivo, antes de mover nada (2026-10-23)

Marker0 de 80 mm quieto, de frente, a ~37–38 cm (no 45; la misma distancia en todas las corridas de cada cámara), caja de luz nivel 2, dodecaedro fuera de la vista, Slicer conectado antes (Client, localhost:18944), 1280×960 MJPG 90 fps, aceleración HW de MSMF apagada (B28). Tracker de hoy (`iter4/tracker.py`), sin cambios en lo que envía. Protocolo y sesión: `Claude outputs/fases/003/fase-1-en-vivo-protocolo.md` y `fase-1-en-vivo.md`. Grabaciones, resúmenes y logs: `Claude outputs/grabaciones/003/` (fuera de git).

| | gs1 (puerto 1) | gs2 (puerto 2) |
|---|---|---|
| Frames (con ventana, `--record`) | 977 | 973 |
| Fracción con pose de Marker0 (≥ 95 % esperado) | 100 % | 100 % |
| z media (mm) | 374.4 | 379.4 |
| sd x / y / z (mm) | 0.009 / 0.009 / **0.043** | 0.010 / 0.007 / **0.039** |
| Rango z (mm) | 0.31 | 0.39 |
| sd de la orientación (°, RMS al giro medio) | 0.13 (máx. 0.39) | 0.10 (máx. 0.29) |
| Saltos > 5° entre frames seguidos | 0 (paso máx. 0.58° y 0.11 mm) | 0 (paso máx. 0.38° y 0.16 mm) |
| fps con ventana, `--record` y frames (`fps` del resumen) | 32.5 | 32.4 |
| fps sin ventana, `--record` (`fps` del resumen) | 20.9 (628 frames; sd z 0.052) | 35.2 (1057 frames; sd z 0.039) |
| fps con ventana, tracker de hoy sin opciones (última `[FPS] Promedio`) | 33.0 | 20.7 |
| Replay de las esquinas frente a lo enviado en vivo (mm / °) | 0.0 / 0.0 (977 envíos, 0 distintos) | 0.0 / 0.0 (973 envíos, 0 distintos) |
| Detección sobre los 3 frames guardados (px) | 0.0 (3 de 3, ids iguales) | 0.0 (3 de 3, ids iguales) |
| `Marker0ToTracker` en Slicer (Hz, opcional) | llegó (autor); Hz no medidos | no medido |
| Salida limpia, ningún `python` del tracker vivo, 18944 libre | sí (las 6 corridas) | sí (las 6 corridas) |

La sd y el rango salen de las poses **enviadas** (filtradas por el 1-Euro de la posición, como las recibe Slicer); la orientación de Marker0 no se filtra hoy.

Lectura:

- La pose de Marker0 quieto es estable: sd z 0.04–0.05 mm y orientación 0.10–0.13° en las dos cámaras, sin saltos. El dodecaedro daba sd z 1.1–4.9 mm en la meta 002.
- Los fps son **bimodales**, ~20–21 o ~32–35, y no siguen a la ventana (gs1: con ventana 32.5, sin ventana 20.9, hoy 33.0; gs2: 32.4, 35.2, 20.7). Causa sin aislar (carga de otros procesos, temporizador de Windows, cadencia de la cámara); la línea base de fps de cada modo es «20–35, bimodal» y la fase 6 la mide. Quedó en B32.
- B39 (Marker0 sintético inclinado leído como ID 87/115): con Marker0 real de frente no apareció (100 % con pose, ID 0). Sin probar inclinado con imágenes reales; sigue abierto (baja).
- Lo que entra en git: `tests/data/marker0_*` pesa 2.17 MB (P3 estimaba ~2): dos grabaciones de 0.43 MB, dos referencias de 0.13 MB, 3 PNG por cámara de 0.57 MB y dos JSON de procedencia.
- `test_replay_marker0.py`: 8 pruebas en verde con tolerancia 1e-9 mm / 1e-9° frente a lo enviado en vivo y frente a la referencia.

## Fase 2 · La cadena solo con Marker0 (2026-10-23)

ADR-026 y el principio 6 ya cambiados (`8969c77`). Los perfiles `tracker_config_gs1.yaml` y `_gs2.yaml` pierden el bloque del dodecaedro (13 líneas cada uno, 0 añadidas); `gui/estado.py` no exige la geometría si el perfil no la define; `codigo/slicer/receive_marker0.py` y su `README.md`; `documentos/MANUAL_simplificado.md` pasa a `documentos/historico/` (R100). En vivo con el autor: Slicer con escena nueva, el dodecaedro a la vista a propósito, `receive_marker0.run(seconds=10)`, caja de luz nivel 2. Sesión: `Claude outputs/fases/003/fase-2-en-vivo.md`.

| | gs1 | gs2 |
|---|---|---|
| Lista blanca del tracker | `[0]` | `[0]` |
| `Marker0ToTracker` en Slicer (Hz, 10 s) | 19.1 (191 eventos, CONNECTED) | 31.4 (314 eventos, CONNECTED) |
| `[FPS] Promedio` del tracker en la misma corrida | 20.1, 20.1, 19.9, 23.3, 25.5 (los 10 s medidos, en el modo ~20) | 29.6, 31.2, 31.5, 31.9, 32.1 |
| Criterio: Hz en Slicer ≥ fps − 10 % | cumple (≥ 18) | cumple (≥ 28) |
| `DodecaedroToTracker` en la escena nueva | no existe | no existe |
| «[Salida limpia]», ningún `tracker.py` vivo, 18944 sin `Listen` | sí | sí |
| Replay de Marker0 (envíos; mm / °) | 977; 0.0 / 0.0 | 973; 0.0 / 0.0 |
| Detección sobre los 3 frames (px) | 0.0 | 0.0 |

- Sin cámara: diff de cada perfil = 13 líneas quitadas, 0 añadidas; selftest con gs1: geometría y punta en GRIS «no aplica», `apto_tracker=SI`, «Arrancar tracker» habilitado; `git status` muestra el manual como R100 y `documentos/MANUAL_simplificado.md` ya no existe.
- Suite completa: 468 pruebas, **446 pasan, 22 `xfail`**, 7 avisos (B22); 19.86 s y 19.95 s de pytest, 22 y 24 s de pared (dos corridas). Antes (fase 1): 461 y 439; las 7 nuevas son `test_status.py`.
- Los fps siguen bimodales (gs1 empezó en ~20 y subió a ~33): B32, fase 6. No se probó el arranque desde el panel (opción 4 del protocolo); la fase 4 lo hace.
- `medir_modos.py --modos` y `--exposiciones-ms` paran con gs1/gs2 («el perfil tiene que traer un solo rigid body») hasta que la fase 4 los pase a Marker0; `--enfocar` (el del panel) no cambió.

## Fase 3 · La estructura nueva y el archivo (2026-10-23 sin cámara; 2026-10-24 en vivo)

- Movimientos con `git mv` (R100 los que solo cambian de sitio): 17 `.py` vivos a `tracker.py`, `camera/`, `calibration/`, `diagnostics/` y `gui/`; los perfiles gs1 y gs2 a `profiles/` (cambian solo comentarios: el YAML cargado es igual al de HEAD); los dos `.yml` de intrínsecos y el tablero a `data/`, sin cambiar. Al archivo `codigo/historico/iter4/`: 9 scripts del dodecaedro, 8 geometrías, `respaldo_puntas/`, 4 pruebas y el replay del dodecaedro; el perfil, la calibración y los PNG de la Femto; los 5 archivos versionados de los perfiles viejos. Lo local (capturas, puntas, `*_calibrado.txt`), con `Move-Item`. Nuevos: `profiles/__init__.py` (una sola carga de perfil, rutas relativas a `codigo/`), los `__init__.py` de los paquetes, `historico/iter4/femto/femto_backend.py` y `historico/iter4/README.md` (B38).
- `codigo/iter4/` ya no tiene nada versionado; en el disco quedan solo `__pycache__/` y `Log/OrbbecSDK.log.txt` (ignorados): borrarlos lo niega el permiso de los agentes y queda para el autor, con `codigo/Log/`.
- `git grep -n iter4 -- codigo ':!codigo/historico'`: 30 líneas: 7 dicen de dónde viene un módulo, 15 nombran el archivo `historico/iter4/`, 6 son datos de procedencia (`generated_by` de los `.yml`, las `.json` de la referencia), 1 es la prueba de que `iter4/tracker.py` ya no existe y 1 el rótulo de `requirements.txt`.
- Nombres: los once `find_spec` dan `None` sin `codigo/` en `sys.path`; con él, los nueve que existen apuntan a `codigo/` (`vision` y `transport` llegan en la fase 4).
- Replay de Marker0: 0.0 mm / 0.0° frente a lo enviado en vivo (977 y 973 envíos) y frente a la referencia; detección sobre los 3 frames, 0.0 px, en gs1 y gs2. El tracker solo cambia sus imports y la carga del perfil (`profiles.load`).
- Suite: **392 pruebas, 392 pasan, 0 `xfail`, 0 avisos**; 18.21 s y 18.29 s de pytest, ~22 s de pared. Antes: 468 (446 + 22 `xfail`, 7 avisos); se fueron las 4 pruebas archivadas, sus `py_compile` y los dos módulos del asistente; `test_status.py`, reescrita sin geometría ni punta, tiene 8.
- Cada punto de entrada responde a `python -m <modulo> --help` (12 de 12).

### Parte en vivo (2026-10-24, con el autor; perfil gs1, caja de luz nivel 2, Marker0 de 80 mm)

Panel abierto con `.\.venv\Scripts\python.exe -m gui.panel` desde `codigo\`. Sesión y log: `Claude outputs/fases/003/fase-3-en-vivo.md`.

| Botón del panel | Comando (cwd `codigo\`) | Resultado |
|---|---|---|
| Semáforos | — | «apto para tracker: SI» al abrir y tras cada proceso |
| Probar cámara | `-u -m gui.camera_probe --config profiles\tracker_config_gs1.yaml` | puerto USB(3) → índice MSMF 0; entrega 1280x960 = perfil = `intrinsecos_gs1_1280x960.yml`; `exit=0` |
| Verificar IDs | `-u -m diagnostics.identify_ids --config profiles\tracker_config_gs1.yaml` | focus=500 comprobado; «visibles: [0]» en todas las líneas; `exit=0` |
| Arrancar tracker | `-u -m tracker --config profiles\tracker_config_gs1.yaml` | `[Whitelist] IDs aceptados: [0]`; K y dist de `codigo\data\`; `[Salida limpia]`; `exit=0` |

- Los 4 procesos del panel, `exit=0`. El autor vio moverse `Marker0ToTracker` en Slicer; los Hz no se midieron en esta corrida.
- Selftest (`-m gui.panel --selftest --perfil tracker_config_gs1.yaml`): las tres recetas de la ventana de calibración salen con `-m diagnostics.measure_modes`, `-m calibration.calibrate_camera` y `-m calibration.check_scale`; «cerrando OK». La ventana de calibración no se abrió en vivo: la cubre el selftest.
- Restos: el autor borró `codigo\iter4` y `codigo\Log` (`Test-Path` False y False). Sin `-m tracker|diagnostics|calibration` vivo y sin `Listen` en 18944 al terminar.
- **fps de esta corrida, para la fase 6 · Dónde se va el tiempo por frame (B32):** `[FPS] Promedio` 22.3, 15.9 y 20.3 en ~65 s, es decir 16–22, por debajo de los modos ~20 y ~32 de las fases 1 y 2. El tracker solo cambió imports y la carga del perfil, y el panel estaba abierto (carga extra); la causa sigue sin aislar.
- Veredicto: cumple la parte en vivo de la fase 3.

## Fase 4 · El tracker en piezas (2026-10-24, sin cámara y en vivo)

- Piezas: `vision/` (detection, pose, filtering, tracking: `MarkerTracker`), `transport/igtl.py` (`IgtlSender`); `tracker.py` 754 → 212 líneas (solo el bucle); `measure_modes` sobre `MarkerTracker` (vuelve a correr con gs1/gs2). `pose_rigid_body.py` archivado en `historico/iter4/dodecahedron/`.
- Replay de Marker0 a través de `MarkerTracker.process_corners`: gs1 977 envíos y gs2 973, 0 frames distintos, **0.0 mm / 0.0°** frente a lo enviado en vivo y frente a la referencia (tolerancia 1e-9). Detección por `vision.detection` sobre los 3 frames por cámara: **0.0 px**.
- Pose de un cuadrado proyectado con la K real de gs1: 2.6e-5 mm / 1e-4° a 450 y 380 mm; 1.4e-4 mm / 2e-3° a 600 mm casi de frente. No llega a 1e-6 mm del plan (suelo: `astype(float32)` de las esquinas, ya estaba así); la prueba fija < 1e-3 mm y < 1e-2°.
- 1-Euro igual bit a bit sobre una serie fija de 200 muestras; `IgtlSender` manda `Marker0ToTracker` 4×4 float32 con un servidor falso; el bucle con cámara y emisor falsos sale con `q` y cierra todo.
- B34: el fixture `no_real_camera` niega la cámara real y el servidor pyigtl a toda la suite. B22: 55 archivos de `codigo/` compilan con los avisos como errores, 0 avisos. B28: `import tracker` apaga la aceleración HW y lo dice (prueba). B27: `abrir_camara` ya no existe.
- Suite: **463 pruebas, 463 pasan, 0 avisos**; 18.40 s y 18.28 s de pytest, ~21 s de pared (dos corridas en «verifica»). Antes, 392. `py_compile` con `-W error` de los 19 `.py` tocados o nuevos, sin error.

### Parte en vivo (2026-10-24, con el autor; caja de luz nivel 2, Marker0 de 80 mm)

Protocolo `Claude outputs/fases/003/fase-4-en-vivo-protocolo.md`; sesión `fase-4-en-vivo.md`. Slicer con *Close Scene* y `codigo/slicer/receive_marker0.py` (`run(seconds=10)`) antes de cada corrida. Logs a mano: `Claude outputs/grabaciones/003/fase4_gs1_mano.log` y `fase4_gs2_mano.log`.

| corrida | aceleración MSMF | `Abierta en` | Hz en Slicer (10 s) | último `[FPS] Promedio` | servidor 18944 cerrado | salida |
|---|---|---|---|---|---|---|
| a mano gs1, sin la variable | «puesta por el codigo» | 0.4 s | **22.1** (CONNECTED) | 21.9 (20.8–24.9) | sí | `[Salida limpia]` |
| a mano gs2, sin la variable | «puesta por el codigo» | 0.4 s | **30.9** (CONNECTED) | 32.7 | sí | `[Salida limpia]` |
| panel gs1 | «del entorno» | 0.4 s | **28.6** (CONNECTED) | 34.1 (31.8–34.1) | sí | `[Salida limpia]`, `exit=0 OK` |
| panel gs2 | «del entorno» | 0.5 s | **22.8** (conector WAIT al final) | 32.2 | sí | `[Salida limpia]`, `exit=0 OK` |

- Primer intento a mano con gs1: `ValueError` («el puerto '…USB(3)' no coincide con ninguna camara conectada»); Windows tenía las cámaras en estado «Unknown». El autor las reconectó. El tracker falló fuerte y aun así cerró el servidor del 18944 y salió con `[Salida limpia]`.
- En las cuatro corridas: `[Whitelist] IDs aceptados: [0]` y `DodecaedroToTracker` ausente (correcto, ADR-026). El autor movió Marker0 y la posición cambió en Slicer.
- **B28 cumple:** a mano, sin la variable de entorno, la cámara abre en 0.4 s (antes 40–50 s).
- **Lo nuevo cumple:** «[OpenIGTLink] Servidor del puerto 18944 cerrado» en las cinco salidas, incluida la del fallo.
- Los Hz del panel salen por debajo de los fps porque las corridas duraron 16 s (gs1) y 12 s (gs2) y la ventana de 10 s de Slicer cubrió el arranque y, en gs2, el cierre. En las corridas a mano, más largas, Slicer recibe lo que se envía (22.1 frente a 21.9; 30.9 frente a 32.7).
- Limpieza tras cada corrida: ningún `-m tracker` vivo y el 18944 sin `Listen`; al final solo seguía el panel abierto.
- fps bimodales otra vez (gs1 ~22 a mano, ~34 desde el panel): dato para la fase 6 · Dónde se va el tiempo por frame (B32). No se corrió el paso 4 opcional (`measure_modes`).
- Veredicto: cumple la parte en vivo de la fase 4.

## Fase 5 · Documentación del paso 1 (2026-10-24, sin cámara)

- Docs al día: `docs/ARCHITECTURE.md` §2, §3 (3.1–3.7), §4 y §6, con notas de «referencia» en §5, §7 y §8; `docs/CONTEXT.md` §3, §4 (13–17 marcadas como del dodecaedro archivado, 18 y 19) y §6; BACKLOG: B08, B10, B14, B20, B25, B29, B31 y B35 con las rutas nuevas; B21 cerrado (texto alineado con `opencv-python` 4.11).
- `git grep -n iter4 -- codigo CLAUDE.md docs ':!docs/history'`: **184 líneas**. 87 en `codigo/historico/`; 32 en el código vivo (procedencia «era `iter4/…`», rutas a `codigo/historico/iter4/`, metadatos grabados en `tests/data/*_reference.json` y en los `.yml` de intrínsecos, la prueba de que `iter4/tracker.py` no existe); 9 en ADR de `DECISIONS.md`; 5 en `PRUEBAS.md`; 22 en el BACKLOG (rutas a `historico/iter4/`, entradas cerradas, la procedencia de B46); 14 en `ARCHITECTURE.md` y 8 en `CONTEXT.md` (rutas a `historico/iter4/`, la nota de reestructuración, «Antes, …» y las trampas 14 y 17 bajo su nota). **Las 7 de `CLAUDE.md` no son históricas:** §1 y §5; su texto nuevo está en el reporte de la fase para la dirección o el autor.
- `git grep -n "documentos/MANUAL_simplificado" -- docs/ARCHITECTURE.md docs/CONTEXT.md codigo`: **0 líneas**.
- Líneas de más de 2 000 caracteres en `docs/` (sin `history/`), `memory.md` y `specs/`: **0** (la más larga, 1 832).
- Los 8 comandos `python -m` propuestos para `CLAUDE.md` §5 (`tracker`, `gui.panel`, `diagnostics.identify_ids`, `diagnostics.probe_camera`, `diagnostics.measure_modes`, `calibration.calibrate_camera`, `calibration.check_scale`, `tests.replay_util`) con `--help` desde `codigo\`: **exit 0** los 8.
- Suite: **463/463** en 18.02 s y 17.63 s de pytest (21 s de pared); replay de Marker0 y selftest del panel 16/16. Ningún `.py` cambió.

## Fase 6 · Dónde se va el tiempo por frame (2026-10-24, sin cámara y en vivo)

- Entrega: `diagnostics.pose_log.Stopwatch` (`mark`, `end_frame`, `summary`, `save`; reloj `perf_counter`), `tracker --timing <json>` (apagado por defecto; etapas `capture`, `gray`, `detect`, `pose_filter`, `send`, `record`, `draw`, `imshow`, `key`, `other`) y `diagnostics/measure_window.py`. `tracker.py` 212 → 282 líneas; `pose_log.py` 239 → 358; `measure_window.py` 151; `tests/test_timing.py` 245 (12 pruebas).
- **`measure_window.py`** (300 vueltas por modo, 10 de calentamiento, tope 60 s, frame de 1280×960 de `tests/data/`; JSON en `Claude outputs/grabaciones/003/fase6_measure_window_*.json`), ms por vuelta:

| corrida | modo | `imshow` | tecla | total (media) | p50 | p95 | fps equivalentes |
|---|---|---|---|---|---|---|---|
| gs1 (a) | `waitKey(1)` | 0.431 | 1.765 | 2.196 | 1.911 | 2.803 | 455 |
| gs1 (a) | `pollKey()` | 0.453 | 1.574 | 2.026 | 1.938 | 2.610 | 494 |
| gs2 | `waitKey(1)` | 0.469 | 1.888 | 2.357 | 2.013 | 3.417 | 424 |
| gs2 | `pollKey()` | 0.440 | 1.540 | 1.980 | 1.964 | 2.443 | 505 |
| gs1 (b) | `waitKey(1)` | 0.469 | 1.579 | 2.048 | 1.993 | 2.508 | 488 |
| gs1 (b) | `pollKey()` | 0.460 | 1.555 | 2.015 | 1.970 | 2.364 | 496 |

- **La hipótesis a) del plan no se sostiene en esta máquina:** `waitKey(1)` no espera un tic de ~15 ms; cuesta 1.6–1.9 ms, y `pollKey()` ahorra 0.0–0.35 ms de media. La ventana entera (`imshow` + tecla) son ~2 ms por frame.
- Aparte, sin cámara (script de trabajo fuera del repo, 100 vueltas sobre los 3 frames guardados de cada cámara, `MarkerTracker` del perfil, 12 hilos de OpenCV): gris 0.47–0.53 ms, detección 5.6–5.8 ms (p95 6.5–6.7), pose y filtro 0.17 ms, copia del frame para dibujar 0.84–0.86 ms. Con la ventana, ~10 ms por frame: el proceso daría ~100 fps. A 20–33 fps (30–50 ms por frame), lo que falta estaría en la captura (`cam.read()` esperando el frame); es la hipótesis que la tabla en vivo confirma o descarta.
- Replay de Marker0 en 0.0 mm / 0.0° (en la suite). `--timing` no cambia lo enviado (prueba con cámara y emisor falsos: las mismas matrices con y sin la opción).
- Suite: **475/475** en 18.06 s y 17.94 s de pytest, 0 avisos.

### Parte en vivo (2026-10-24, con el autor; caja de luz nivel 2, Marker0 de 80 mm quieto a ~37–38 cm)

Protocolo `Claude outputs/fases/003/fase-6-en-vivo-protocolo.md`; sesión `fase-6-en-vivo.md`. Por cámara, 30 s con ventana y 30 s `--no-window`, con `--duration 30 --timing <json>`, panel cerrado, Slicer conectado antes con `codigo/slicer/receive_marker0.py` (`run(seconds=20)`). JSON y logs: `Claude outputs/grabaciones/003/fase6_{gs1,gs2}_{ventana,sinventana}_timing.json` y `.log`.

ms por etapa, **media / p50 / p95** (reloj `perf_counter`):

| etapa | gs1 con ventana | gs1 sin ventana | gs2 con ventana | gs2 sin ventana |
|---|---|---|---|---|
| `capture` | **32.09** / 28.43 / 44.08 | 8.64 / 8.48 / 11.84 | 7.87 / 8.00 / 9.98 | 8.59 / 8.46 / 11.94 |
| `gray` | 0.50 / 0.48 / 0.60 | 0.49 / 0.48 / 0.61 | 0.49 / 0.47 / 0.58 | 0.46 / 0.46 / 0.54 |
| `detect` | 5.75 / 5.85 / 6.98 | 5.85 / 6.19 / 7.01 | 5.98 / 6.30 / 7.14 | 5.58 / 6.04 / 6.61 |
| `pose_filter` | 0.17 / 0.17 / 0.21 | 0.17 / 0.17 / 0.22 | 0.18 / 0.18 / 0.23 | 0.17 / 0.17 / 0.21 |
| `send` | 9.07 / 9.17 / 11.21 | **12.53 / 15.02 / 19.69** | 12.53 / 12.72 / 15.93 | **12.20 / 15.19 / 19.99** |
| `draw` | 1.17 / 1.13 / 1.46 | — | 1.19 / 1.16 / 1.50 | — |
| `imshow` | 0.76 / 0.67 / 0.84 | — | 0.72 / 0.66 / 0.83 | — |
| `key` (`waitKey(1)`) | 1.86 / 1.75 / 2.37 | — | 1.76 / 1.65 / 2.39 | — |
| `other` | 0.005 | 0.004 | 0.005 | 0.004 |
| **frame** | **51.36** / 47.60 / 63.37 | 27.69 / 30.90 / 33.17 | 30.72 / 31.20 / 33.29 | 27.00 / 30.86 / 33.24 |
| frames | 576 | 1 072 | 967 | 1 099 |
| fps (media del frame / `[FPS]` de toda la corrida) | 19.5 / 19.2 | 36.1 / 35.7 | 32.6 / 32.2 | 37.0 / 36.6 |
| suma de etapas / frame de `[FPS]` | **0.984** | **0.988** | **0.989** | **0.988** |
| Hz en Slicer (20 s) | 19.4 | 36.2 | 8.3 (no vale\*) | 12.5 (no vale\*) |

\* En gs2 la escena de Slicer no se cerró y el script dijo «conector existente»: la ventana de 20 s empezó antes que el tracker. En gs1 (escena nueva) Slicer recibió lo enviado (19.4 frente a 19.2; 36.2 frente a 35.7).

- **Criterio: cumple.** La suma de las etapas queda entre −1.1 % y −1.6 % del tiempo por frame de `[FPS] Promedio` (tolerancia ±10 %). Las cuatro corridas: «Servidor del puerto 18944 cerrado», `[Salida limpia]` y limpieza vacía.
- **El proceso propio es ~6.5 ms** (gris + detección + pose y filtro), como en el banco sin cámara; la ventana entera ~3.7–3.8 ms (dibujo 1.2, `imshow` 0.7, `waitKey(1)` 1.8). Lo que pesa son el **envío** (9–12.5 ms de media en las cuatro) y, en el modo lento, la **captura** (gs1 con ventana: 32 ms; en las otras tres, 7.9–8.6 ms).
- **El bucle va enganchado al tic del reloj de Windows (15.625 ms).** La duración de cada frame cae cerca de un múltiplo del tic: distancia media al múltiplo más cercano 0.96–1.07 ms (sería ~3.9 ms sin enganche). gs1 con ventana: 392 frames de 3 tics y 175 de 4; las otras tres, 2 tics la mayoría (765–926) y 1 tic el resto (40–322). Lo que no es envío suma 14.8–18.2 ms en las tres corridas rápidas y 42.3 ms en la lenta; el envío completa hasta el siguiente tic.
- **Por qué el envío tarda (leído de `pyigtl/comm.py` 0.3.1 en el venv; Context7 `/lassoan/pyigtl` no documenta el hilo):** `send_message(msg, wait=True)` mete el mensaje en una cola (`deque(maxlen=100)`) y espera a que se vacíe con `time.sleep(0.001)`. La cola la vacía el hilo del servidor (`TCPRequestHandler.handle`), que en cada vuelta hace primero un `recv` con `settimeout(0.01)`: Slicer no le manda nada, así que espera el tope entero, y en Windows ese tope de 10 ms acaba en el tic. Micro-banco sin cámara ni puerto 18944 (un `socketpair` con el mismo tope, 60 vueltas, dos corridas): **15.5–15.6 ms** de media (p5 14.8–15.0, p95 16.1); `time.sleep(0.001)` dura 1.53–1.55 ms. El envío espera, pues, hasta que el hilo despierta en el siguiente tic: de ~0 a un tic, más si el bucle de recepción da otra vuelta (máximo visto 24.5 ms).
- **El modo lento es la captura, no la ventana:** en la misma sesión gs2 con ventana capturó en 7.9 ms y gs1 sin ventana en 8.6 ms. Con 32 ms de captura y ~19 ms del resto, gs1 iba atado a ~19.5 fps. Si es la cámara o MSMF entregando menos frames, o la lectura que espera otra cosa, no se puede separar con estos datos (no se corrió el paso 5 opcional, `measure_modes`).
- **Aviso para la fase 7:** `t_now` del bucle sale de `time.time()`, que en este venv tiene resolución de 15.625 ms (`time.get_clock_info('time')`: `GetSystemTimeAsFileTime`). Hoy no estorba porque cada frame dura al menos un tic; por encima de 64 fps dos frames compartirían `t_now` y el 1-Euro tomaría `dt = 1e-3` (su mínimo), con `beta` 0.05 en los perfiles. Si la fase 7 suelta el bucle del tic, `t_now` tiene que pasar a `perf_counter` o a la marca del frame (cambia la entrada del 1-Euro: se declara).
- Suite al cerrar: **475/475** en 18.89 s y 18.51 s de pytest; replay de Marker0 0.0 mm / 0.0° dentro de ella. Ningún `.py` cambió en esta parte.
