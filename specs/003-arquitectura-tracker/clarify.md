# Aclaraciones — Meta 003 · Arquitectura y optimización del tracker

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

## P1 · Cómo se lanzan los scripts después de la reorganización

- **Opciones:** a) `python -m paquete.modulo` desde `codigo\` con el venv; ningún script toca `sys.path` y la suite usa `pythonpath = .` (recomendada); b) rutas (`python camara\backend.py`), cada script añadiendo `codigo\` a `sys.path`; c) un punto de entrada único (`python -m nav tracker ...`), una capa más que mantener.
- **Respuesta del autor:** a) `python -m` desde `codigo\`.
- **Fecha:** 2026-10-23

## P2 · La lista de lo que se archiva y se borra, Femto incluida

- **Opciones:** a) la de `plan.md` («Archivos»): dodecaedro, stylus, Femto (backend, `tracker_config.yaml`, calibración, diagnósticos) y perfiles viejos a `codigo/historico/iter4/`; solo se borran los logs del SDK (recomendada); b) igual, pero el backend Femto sigue activo en `camara/backend.py`; c) igual, pero los archivos locales del dodecaedro (npz, npy, puntas) se borran en vez de moverse.
- **Respuesta del autor:** a) la lista de `plan.md`.
- **Fecha:** 2026-10-23

## P3 · Qué del dataset de Marker0 entra en git

- **Opciones:** a) las tablas de las dos cámaras (~150 KB cada una) y 3 frames en gris por cámara (~2 MB en total, a confirmar con el tamaño real) para probar la detección (recomendada); b) solo las tablas; la detección se comprueba fuera de la suite con los frames locales; c) más frames (≥ 30 por cámara, ~20 MB).
- **Respuesta del autor:** a) las tablas y 3 frames por cámara.
- **Fecha:** 2026-10-23

## P4 · `femto_pruebas/` y sus dependencias

- **Opciones:** a) no se tocan en esta meta y van al BACKLOG; siguen «en pausa» (ADR-014) (recomendada); b) `femto_pruebas/` a `historico/` y fuera `open3d` y `pyorbbecsdk2` de `requirements.txt`.
- **Respuesta del autor:** a) no se tocan; al BACKLOG.
- **Fecha:** 2026-10-23

## P5 · Qué pasa con `MANUAL_simplificado.md`

- **Opciones:** a) un aviso al principio: es del dodecaedro, descartado en la meta 003; para recibir Marker0, `codigo/slicer/LEEME.md` (recomendada); b) moverlo a `documentos/historico/`; c) no tocarlo.
- **Respuesta del autor:** b) se mueve a `documentos/historico/`.
- **Fecha:** 2026-10-23

## P6 · La pose de Marker0 con un solo marker

- **Opciones:** a) no cambia en esta meta (IPPE_SQUARE, z > 0, 1-Euro solo en la posición); la línea base mide la sd de la orientación y los saltos > 5°, y lo que salga va al BACKLOG (recomendada); b) además, filtrar la orientación de Marker0 en la fase 7, declarado como cambio en el replay.
- **Respuesta del autor:** a) no cambia en esta meta.
- **Fecha:** 2026-10-23

## P7 · El envío de vídeo por OpenIGTLink

- **Opciones:** a) se quita: con `send_video: true` el tracker aborta y dice por qué (CONTEXT §4.4; nadie lo usa) (recomendada); b) se conserva como hoy.
- **Respuesta del autor:** a) se quita; `send_video: true` aborta con un mensaje.
- **Fecha:** 2026-10-23

## P8 · Los nombres de carpetas y perfiles

- **Opciones:** a) los del diagrama, en español (`camara`, `vision`, `envio`, `calibracion`, `diagnostico`, `gui`, `slicer`, `perfiles`, `data`, `historico`), y los perfiles con su nombre de hoy (`tracker_config_gs1.yaml`, `_gs2.yaml`) (recomendada: el código ya está en español); b) carpetas en inglés, como pide `CLAUDE.md` para los identificadores; c) a), pero los perfiles pasan a `gs1.yaml` y `gs2.yaml`.
- **Respuesta del autor:** b) carpetas en inglés, como pide `CLAUDE.md` para los identificadores (p. ej. `camera`, `vision`, `transport`, `calibration`, `diagnostics`, `gui`, `slicer`, `profiles`, `data`, `historico` → el plan propone el nombre de cada una). Los perfiles los nombra el plan con el mismo criterio.
- **Fecha:** 2026-10-23

## P9 · Las opciones de la fase 7 · Subir los fps con ventana (tras la tabla de la fase 6)

- **Envío. Opciones:** E1 `send_message(wait=False)` con guarda de conexión (recomendada); E3 envío propio (ADR-028); E4 hilo con el último (cambia lo que se envía). **Respuesta del autor:** E1, sin esperar y con guarda.
- **Sin Slicer al arrancar. Opciones:** a) el tracker espera a que Slicer se conecte, con tope de tiempo, y si no llega aborta y lo dice (recomendada); b) arranca sin Slicer, no envía y cuenta lo no enviado. **Respuesta del autor:** a) espera a Slicer con tope.
- **Captura. Opciones:** C0 + C1, primero medir la captura sola en el modo lento de gs1 y después un hilo de captura con el último frame (ADR-028; calidad sd z ≤ 1.10 × la de la fase 1) (recomendada); C1 sin medir; no tocar la captura. **Respuesta del autor:** C0 y después C1.
- **El objetivo. Opciones:** mantener ≥ 60 fps con ventana y revisarlo tras C0 (recomendada); bajar a 45. **Respuesta del autor:** 60, y se revisa tras C0.
- Va con la fase 7 sea cual sea la opción: `t_now` deja `time.time()` (`perf_counter` o la hora de captura de C1), declarado porque cambia la entrada del 1-Euro.
- **Fecha:** 2026-10-24
