# Meta 003 — Arquitectura y optimización del tracker

## Por qué

Al cerrar la meta 002 (2026-10-23) el autor pidió ordenar el proyecto antes de optimizar: hoy no sabe dónde está la cámara, la matemática ni la pose. Todo vive en `codigo/iter4/`, una carpeta plana de 17 scripts, y `tracker.py` (703 líneas) hace casi todo: perfil, detección, pose, filtro, envío y ventana. La foto de partida está en `diagrama.md`, en esta misma carpeta.

Decisiones del autor del 2026-10-23:
- **Una sola meta, en dos pasos:** primero la arquitectura, sin cambiar el comportamiento; después la optimización.
- **Se descarta el dodecaedro.** Por ahora el tracker sigue **solo Marker0**. El instrumento y la punta vuelven en otra meta, con un transform de **nombre nuevo** y su ADR. `DodecaedroToTracker` deja de enviarse (cambia el principio 6: hace falta un ADR y una verificación en vivo con Slicer).
- **Lo más simple posible, sin sacrificar calidad en el tracking.**
- **Nada bajo `iter4/`:** todo el código queda directamente bajo `codigo/`.
- **Después de esta meta,** en otra aparte: un gráfico del proyecto, y entender la lógica entre detección y pose.

Del BACKLOG entran:
- B32 · Optimizar el tracker: la ventana limita a 19–25 fps en cualquier resolución.
- B28 · `tracker.py` lanzado a mano abre MSMF con la aceleración HW encendida.
- B27 · `tracker.abrir_camara`, función que nadie llama.
- B38 · `iter4/data/historico/` sin índice de qué es cada archivo.
- B22 · Secuencias de escape inválidas en docstrings de `iter4\`.

B37 · La pose del dodecaedro salta 11–25 mm cuando entra o sale un marker visto de lado se cierra por decisión: el dodecaedro se descarta.

## Qué se construye

**Paso 1 · La arquitectura.** El comportamiento de Marker0 no cambia.
- El código pasa de `codigo/iter4/` a carpetas por responsabilidad bajo `codigo/`: cámara, visión (detección, pose y filtro), envío, el bucle del tracker, calibración de la lente y la escala, diagnóstico, panel, perfiles y datos.
- Lo que el tracker hace hoy en un solo archivo se separa en piezas con pruebas sin cámara.
- El dodecaedro y lo que solo existe por él va a `historico/`: geometrías, BA, topología, captura de calibración, punta por dock, asistente «dodecaedro nuevo» y puntas viejas. Lo mismo con lo que ya no se usa: Femto y perfiles viejos, si el plan lo propone y el autor lo aprueba.
- `data/` queda solo con lo vigente.
- El panel, los comandos de `CLAUDE.md`, la documentación y las pruebas apuntan a la estructura nueva.

**Paso 2 · La optimización.**
- Medir dónde se va el tiempo por frame: captura, detección, pose, filtro, envío y ventana.
- Subir los fps del tracker con ventana a 1280×960, sin empeorar la pose de Marker0.

**El cambio del principio 6.**
- Un ADR, escrito por la dirección, deja la cadena con solo `Marker0ToTracker`, en el puerto 18944.
- Los scripts de Slicer que haga falta se versionan dentro del código, como mínimo para recibir Marker0.

## Criterio de cierre

- **Estructura:**
  - no queda nada en `codigo/iter4/`;
  - `git grep` de `iter4` en `codigo/`, `CLAUDE.md` y `docs/` (fuera de `history/`) solo da referencias históricas;
  - el panel arranca, lista los perfiles gs1 y gs2 y lanza el tracker, la calibración y el diagnóstico desde la estructura nueva.
- **Línea base de Marker0, antes de mover nada:** una grabación con cada cámara (Marker0 quieto a ~45 cm, 30 s), que sirve de dataset de replay para la pose de Marker0. Hoy el replay usa el dodecaedro y el perfil Femto. Se reporta:
  - sd x, y, z;
  - el rango z;
  - los fps con y sin ventana.
- **Paso 1, equivalencia:** la pose de Marker0 sobre ese dataset es la misma antes y después de mover el código (0.0 mm / 0.0°, o la tolerancia numérica que el plan justifique).
- **Paso 2, velocidad:** el tracker con ventana a 1280×960 da **≥ 60 fps** de media en 30 s con Marker0 a la vista (en la meta 002 daba 19–25). El plan puede proponer otro número si la medición del paso 2 muestra un límite real; lo decide el autor.
- **Paso 2, calidad:** con Marker0 quieto a ~45 cm, la sd z no empeora más de un 10 % frente a la línea base, en cada cámara. En el replay, la pose cambia solo si el plan lo declara, por ejemplo con otro filtro.
- **Slicer, en vivo:** `Marker0ToTracker` llega a Slicer y se mueve, en el puerto 18944, con cada cámara; `DodecaedroToTracker` ya no se envía. Al cerrar, salida limpia, ningún Python del tracker vivo y el puerto libre.
- **B28:** el tracker lanzado a mano y desde el panel abre con la aceleración HW de MSMF apagada.
- **Suite:**
  - en verde, con su número y su tiempo, y el selftest del panel;
  - las pruebas del dodecaedro, del BA y de la punta se van con su código a `historico/`, o se borran si el plan lo justifica;
  - ninguna prueba abre una cámara real (B34).
- **Documentación:**
  - `docs/ARCHITECTURE.md` describe la estructura nueva;
  - `CLAUDE.md` §5 tiene los comandos nuevos;
  - `CONTEXT.md` §6 al día;
  - `historico/` con un índice de qué es cada cosa (B38).

## Lo que no se toca

- Las cámaras y su calibración: los perfiles gs1 y gs2 en su contenido (identidad por puerto, marca, ajustes, modo, `.yml`), los `.yml` de intrínsecos y el tablero. Se mueven de carpeta, pero no cambian.
- Lo que hace hoy `camera_backend.py`: puerto, marca, ajustes por DSHOW, MSMF sin aceleración y comprobación de tamaño.
- La pose de Marker0 en el paso 1 (replay).
- El puerto 18944 y el nombre `Marker0ToTracker`. El único cambio de la cadena es que deja de enviarse `DodecaedroToTracker`, con su ADR.
- Los datos de paciente (principio 5): `herramientas/A/`, `*.nrrd` y `documentos/VERONICA/` no se mueven ni se leen.
- La historia: `git mv` para mover, sin reescribir el historial.

## Preguntas que el plan tiene que contestar

1. **La estructura de carpetas.** Los nombres y qué va en cada una, partiendo de la propuesta de `diagrama.md`. Cómo se lanzan los scripts después: `python -m`, rutas o un punto de entrada único. Y cómo encontrarán los perfiles y `data/` el panel y los scripts.
2. **Qué va a `historico/` y qué se borra.** La lista archivo por archivo, con su porqué. Femto: el backend, `tracker_config.yaml`, `femto_pruebas/` y las capturas viejas, ¿se archivan? Hoy el replay y el selftest dependen de `tracker_config.yaml`.
3. **La línea base y el replay de Marker0.** Cómo se graba el dataset (frames o vídeo, dónde se guarda y cuánto pesa) y cómo el replay compara la pose de Marker0. El replay y el selftest actuales usan el dodecaedro y el perfil Femto.
4. **Dónde se va el tiempo por frame,** medido, y qué opciones hay para la ventana:
   - dibujar menos;
   - mostrar un frame de cada N;
   - mostrar en otro hilo;
   - una ventana opcional;
   - otras.

   La consulta a Context7 es obligatoria para lo que se diga de OpenCV (`imshow`, `waitKey`, hilos) y de PySide6.
5. **La pose de Marker0 con un solo marker:** si conviene cambiar algo para no perder calidad (`SOLVEPNP_IPPE_SQUARE`, refinamiento, filtro) y cómo se mide.
6. **Slicer:** qué scripts mínimos hacen falta para recibir Marker0 y dónde se versionan. Qué pasa con `MANUAL_simplificado.md` y con lo que hoy depende de `DodecaedroToMarker0`.
7. **Las fases y su peso** (ADR-022), dentro de los dos pasos. Antes de mover nada, la fase de la línea base en vivo.
