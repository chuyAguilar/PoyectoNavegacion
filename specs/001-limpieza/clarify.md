# Aclaraciones — Meta 001 · limpieza y orden del repo

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

## P1 · Qué se hace con las ~10 pruebas desfasadas al repuntar la suite a `iter4/`

- **Opciones:** (a) recomendada: caracterizar, que esperen lo que el código hace hoy (IDs 170–180, firma nueva de `construir_metadata`, `cargar_calibracion` desde `tracker`, `resolver_geometry_path` de hoy con un comentario a `CONTEXT.md` §4.14; `test_iter2_ids_1_11` y `test_matches_historico_iter1` con IDs y medidas explícitos), borrar `test_fourcc_int_a_str_mjpg` (la función no existe) y marcar `test_validar_prereqs_falla_calibracion` como `xfail(strict=True)` con entrada en el BACKLOG; vigila lo que hay. (b) `xfail(strict=True)` para todas, con una entrada de BACKLOG; deja visible lo perdido pero vigila menos. (c) Borrarlas.
- **Respuesta del autor:** (b) `xfail(strict=True)` para todas las pruebas desfasadas, con una entrada en el BACKLOG.
- **Fecha:** 2026-10-19

## P2 · Qué dataset usa el replay

- **Opciones:** (a) recomendada: recorte de `captura_ba.npz` (crudo, dodecaedro v2, Femto) con paso 6: ~300 frames, ≤ 150 KB, versionado en `codigo/tests/data/`; ejercita el rechazo de outliers. (b) Recorte de `captura_ba_limpia.npz` (el que produjo la geometría vigente; ejercita menos el rechazo). (c) `captura_ba.npz` entero (803 KB, con depth).
- **Respuesta del autor:** (a) recorte de `captura_ba.npz` con paso 6, ~300 frames, ≤ 150 KB, versionado en `codigo/tests/data/`.
- **Fecha:** 2026-10-19

## P3 · Cómo se respalda la punta vigente (`StylusTipToDodecaedro_femto_dock`)

- **Opciones:** (A') recomendada: copia versionada en `iter4/data/respaldo_puntas/` con excepción en `.gitignore`; historia en git sin que el glob del snippet de Slicer ni `estado.py` la vean; cuesta una copia duplicada y el ADR-021. (A) Versionarla en su sitio con `!`, como la geometría v2: en la máquina del doctor un `git pull` la dejaría como la más reciente y el snippet de Slicer la cargaría en vez de la suya; ADR. (B) Fuera de git (OneDrive, USB) con el sha256 en `ARCHITECTURE.md` §3.4: no toca la política, depende de que alguien la copie y no tiene historia.
- **Respuesta del autor:** (A') copia versionada en `iter4/data/respaldo_puntas/` con excepción en `.gitignore`, fuera del glob de Slicer y de `estado.py`; con ADR-021.
- **Fecha:** 2026-10-19

## P4 · Qué pasa con `tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml`

- **Opciones:** (a) recomendada: moverlos los dos a `iter4/data/historico/` (el de webcam apunta a la geometría del stylus viejo y su contexto lo reemplazó el doctor, ADR-016; el otro es de B14); el panel pasa de 4 a 2 perfiles. (b) Mover solo el de webcam y dejar el del stylus impreso hasta decidir B14. (c) Dejar los dos.
- **Respuesta del autor:** (a) mover los dos a `iter4/data/historico/`; el panel pasa de 4 a 2 perfiles.
- **Fecha:** 2026-10-19

## P5 · Qué cuenta como doc vivo y si se corrigen las rutas viejas en los históricos

- **Opciones:** vivos: `docs/` (sin `history/`), `CLAUDE.md`, `memory.md`, `codigo/readme.md`, `documentos/MANUAL_*.md`, `GUIA_calibrar_dodecaedro_propio.md`, `convencion_dodecaedro_compartido.md`; históricos: `docs/history/`, `codigo/historico/`, `documentos/auditoria_iter2/`, `documentos/tecnicos/` y los ADR (no cuentan para las menciones de B01). Para las rutas de B06: (a) recomendada, corregir también el prefijo en los 11 históricos versionados (reemplazo mecánico, las rutas ya no existen); (b) excluirlos del grep y dejarlos literales.
- **Respuesta del autor:** (b) los históricos quedan literales y se excluyen del grep de B06; la clasificación vivo/histórico, la propuesta.
- **Fecha:** 2026-10-19

## P6 · Si la fase 4 espera la prueba del snippet en Slicer

- **Opciones:** (a) recomendada: la fase 4 se cierra con las comprobaciones headless y la prueba en Slicer (traslación esperada [+0.904, +5.471, −201.808] mm, magnitud 201.884 mm) queda en B10 para la próxima sesión con Slicer. (b) La fase 4 queda «parcial» hasta que el autor pegue el snippet.
- **Respuesta del autor:** (a) la fase 4 se cierra con las comprobaciones headless; la prueba del snippet en Slicer va a B10.
- **Fecha:** 2026-10-19
