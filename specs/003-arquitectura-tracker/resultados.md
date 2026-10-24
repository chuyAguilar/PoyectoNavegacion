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
