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
