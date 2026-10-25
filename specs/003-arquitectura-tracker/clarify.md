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

## P10 · Tracker sin ventana y vista previa para posicionar las cámaras

- **Propuesta del autor:** una opción para arrancar el tracker sin ventana, para subir los fps, y un paso para abrir la cámara sin tracking que sirva para colocarla; después, todo el tracking sin ventana.
- **Dónde. Opciones:** a) una fase nueva después de la 7, la 7b, con los dos botones en el panel y los fps sin ventana medidos (recomendada); b) dentro de la fase 7; c) al BACKLOG. **Respuesta del autor:** a) la fase 7b; se autoriza al presentarla.
- **El criterio. Opciones:** a) se mantiene «≥ 60 fps con ventana» y, con los números de la fase 7, el autor decide si el modo normal pasa a ser sin ventana (recomendada); b) sin ventana desde ya (cambia el spec); c) con ventana, como está. **Respuesta del autor:** a) se decide tras medir.
- **Fecha:** 2026-10-24

## P11 · Cómo se cierra la fase 7 (tras la sesión en vivo)

- **Datos:** con la caja al máximo y la cámara a 90, gs1 61.7 fps con ventana (sd z 0.033 mm) y gs2 55.2 (cámara 88.8; el bucle limita: detección 9.7 ms). Pedir 60 fps a la cámara dio 29 en gs1 con la caja al máximo: la SVPRO no tiene modo de 60 a 1280×960 y MSMF baja al de 30.
- **Opciones:** a) perfiles a 90 y la ventana en uno de cada dos frames, y se repiten las corridas (recomendada); b) perfiles a 90 y cerrar con lo que hay: gs1 cumple, gs2 se queda en 55 y lo demás va a la fase 7b (sin ventana).
- **Respuesta del autor:** b) perfiles a 90 y cerrar con lo que hay.
- **Fecha:** 2026-10-25

## P12 · Cómo se detiene limpio el tracker sin ventana desde el panel (fase 7b)

- **Opciones:** a) `--stop-stdin`: el panel escribe `q` por la entrada estándar del tracker y la cierra; el fin de la entrada también lo detiene (recomendada: se prueba sin cámara con un hijo real y no depende de una consola ni de una ventana); b) un archivo de parada (`--stop-file <ruta>`) que el bucle mira: si algo falla queda el archivo, y hay que elegir dónde; c) CTRL_BREAK con un manejador de `SIGBREAK` en el tracker: solo llega si el panel comparte consola con el hijo, y la sonda del 2026-08-13 lo vio matar en duro; d) `terminate()`: no corre el `finally` (la cámara y el puerto pueden quedar tomados, principio 9).
- **Respuesta del autor:** «un botón para eso en el panel». La dirección lo lee así: un botón propio en el panel para detener el tracker sin ventana, limpio; por dentro, el mecanismo que el plan elija para que ese botón cierre limpio (la recomendación era a) `--stop-stdin`).
- **Fecha:** 2026-10-25

## P13 · Con qué se hace la vista previa (fase 7b)

- **Opciones:** a) un módulo nuevo y corto, `diagnostics/preview.py`, que abre la cámara como el tracker (puerto, marca, ajustes, modo y `.yml`) y muestra solo la imagen, los fps de la cámara y una cruz en el centro (recomendada); b) `measure_modes --enfocar`: ya tiene ventana y tope, pero pisa el modo del perfil, no comprueba el `.yml`, exige `--salida` y pinta la nitidez; c) `identify_ids` con una opción para no detectar: no tiene tope ni cierra en un `finally`, y ya es otro botón. Si no se quiere la cruz, se quita.
- **Respuesta del autor:** c) `identify_ids` sin detección. Le faltan el tope y el cierre en un `finally`, que el plan añade.
- **Fecha:** 2026-10-25. Ese mismo día el autor autorizó la fase 7b en el chat, con estas respuestas.

## P14 · Si el modo normal del tracker pasa a ser sin ventana (se contesta con los números de la fase 7b)

- **Opciones:** a) no: «Arrancar tracker» sigue con ventana y «sin ventana» queda como la opción para más fps; b) sí: en la fase 8 el botón principal del panel lanza sin ventana y el otro pasa a «Arrancar tracker con ventana», sin tocar los perfiles; c) sí, y además `debug.show_window: false` en los dos perfiles, para que a mano también arranque sin ventana (cambia el contenido de los perfiles). Recomendación: decidir tras medir; si sin ventana da ≥ 60 fps en las dos cámaras y la vista previa basta para colocarlas, b).
- **Datos (en vivo, 2026-10-25, caja al máximo):** sin ventana, bucle 89.9 / 89.7 fps (gs1) y 88.8 / 89.6 (gs2), sd z 0.037 y 0.030 mm, 99.96 % con pose; con ventana desde el panel, gs1 ~82 fps. Detalle en `resultados.md` (fase 7b).
- **Respuesta del autor:** b) en la fase 8, el botón principal del panel lanza el tracker sin ventana y el otro pasa a «Arrancar tracker con ventana»; los perfiles no cambian.
- **Fecha:** 2026-10-25

## P15 · El techo de ~66 Hz en Slicer sin ventana (tras la sesión en vivo de la fase 7b)

- **Datos:** con el tracker a ~89–90 fps sin ventana, `receive_marker0.py` cuenta 65.8–67.4 Hz en las cuatro corridas, con las dos cámaras; el plan pedía ≥ los fps − 10 % (~81). El tracker envía ~90/s (envíos / duración). Hipótesis sin confirmar: el ritmo al que el conector de Slicer importa los mensajes o cómo cuenta `receive_marker0`.
- **Opciones:** a) cerrar la fase 7b con 66 Hz y una entrada del BACKLOG (baja); b) la fase 7b se cierra con ese criterio sin cumplir y declarado, y la fase 8 mide de dónde sale el techo antes de cerrar la meta.
- **Respuesta del autor:** b) se investiga en la fase 8.
- **Fecha:** 2026-10-25

## P16 · Uno o dos botones para verificar IDs y colocar la cámara (observación del autor en la sesión en vivo de la fase 7b)

- **Opciones:** a) dejar los dos, «Verificar IDs» y «Vista previa (colocar la cámara)»; b) un solo botón: se quita «Vista previa» y «Verificar IDs» muestra también la cruz y los fps de la cámara, con el nombre «Verificar IDs y colocar la cámara».
- **Respuesta del autor:** b) un solo botón, en la fase 8.
- **Fecha:** 2026-10-25
