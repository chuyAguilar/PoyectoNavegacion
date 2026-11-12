# memory.md — estado de hoy

_Actualizado: 2026-11-11 (meta 006 · Grafo de factores óptico-inercial, activa; replan autorizado el 2026-11-11 con las fases 7c a 7h y la 7d2 y 7d2b (P45–P74); la Fase 7d2 · Los IDs falsos del tablero en el detector del tracker, parte sin cámara hecha, pendiente del commit; la 7d, la 7c2 y la 7c, commiteadas; la Fase 7, parcial; la meta 007 · El tracker en la Jetson Orin Nano, en pausa, y la 005 también)._

Spec activo: `specs/006-grafo-factores/`

Peticiones pendientes: 0

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 y 2 commiteadas; la 3 (hooks) cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Metas 001 (limpieza, 2026-10-19) y 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker:** cerrada el 2026-10-26 (P12: 0 dudas). Todo en `docs/ARCHITECTURE.md` §9 (ADR-032).
- **Meta 005 · Agente de consulta para el equipo y buzón de peticiones — en pausa** (`specs/005-equipo-consulta/`; ADR-034). El autor la pausó el 2026-10-29. Fases 1 a 4 commiteadas (`bc328b2` a `7d2ac24`). Al retomarla: lo en vivo de las fases 1–4, los usuarios de GitHub de Kike, Armando y el doctor Milton, el ruleset de `main`, y su fase 5 · Un compañero real instala, pregunta y envía una petición. Mientras siga en pausa, `direccion` mira las peticiones al arrancar.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 418 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `ReferenceToTracker` (ADR-026; antes `Marker0ToTracker`), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta (código 3, sin abrir la cámara).
- `tracker --stop-stdin` sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout`; `--no-detect` es la vista previa, solo por CLI (P17 = a).
- El panel: «Verificar IDs y colocar la cámara», «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana.

## La suite

- `codigo/tests/`: **1460: 1449 pasan, 10 saltadas, 1 fallo esperado (`xfail(strict=True)`, el criterio 9 de la 7d, P67), 0 fallan**; 347.3 y 309.0 s (2026-11-11, meta 006 fase 7d2, sin cámara; antes 1418 en 301.9 y 294.3 s). Dos corridas del mismo árbol difieren ~25 %: es la carga de la máquina. `test_barrido_correccion.py` solo, ~10 s. El margen contra el tope de 600 s baja (B115); B130: dos pruebas de `test_referencia_id.py` pueden fallar sueltas con la CPU cargada (no fallaron). `test_probar_barrera.py` añade ~35 s (B72). Las 10 saltadas: 9 «solo Linux» y 1 solo en la Jetson. **En la Jetson** (`ssh nav-jetson suite wip`): la última corrida, fase 7b parte A, 1051: 993 pasan, 0 fallan, 58 saltadas (la parte B, sin correr); en Linux el replay admite 1e-3 mm/°/px (P22). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell (regla del autor, 2026-10-25).

## Meta 006 · Grafo de factores óptico-inercial (activa desde el 2026-11-05; replan autorizado el 2026-11-11)

- **Fases 1 y 2 hechas** (`a1a714b`, `ccfe803`; números en `tasks.md`): jitter −31.9 % (pose) / −63.1 % (PnP conjunto) fuera de línea; extrínsecos por Marker0 19.5 mm / 5.82° (Jetson) y 4.198 mm / 6.087° (PC, ¿a escala 0.81?): B94, alta, «se movió». Plan por P33: el PC detecta con las dos cámaras y fusiona (Fases 3 a 6 y 8).
- **Fase 7 · Los extrínsecos por tablero: parcial (`1cf90c3`).** `calibrate_extrinsics --desde-vistas`; distancia nominal 200.43 mm. Fase 7a · El asistente de captura (`238117e`): en la sesión del 2026-11-11 cumple (dos cámaras en un proceso, 90 fps, 20 vistas en 8.6 min) y el cálculo no (RMS 0.548 px, triangulada 0.908 mm).
- **Diagnóstico sin cámara (P45; `fase-7/diagnostico-20261111/reporte.md`):** las cámaras giraron 12° entre el 11-09 y el 11-11; la S2 del 11-11 fue con el marker de ~100 mm y el perfil en 80 (B55): con la escala corregida, criterio 1 0.87–1.12 mm, 5.4–6.6° (IPPE, B95). gs2 cambió de intrínsecos (4–7 σ); ~0.5 px por vista: el montaje de pinzas no es rígido.
- **Replan del 2026-11-11 (P46–P67):** referencia con ID 100 (~100 mm), `Reference`, cadena `ReferenceToTracker` (P57; ADR G7 propuesto); ChArUco 9×7 de 26 mm, `DICT_4X4_50`, para intrínsecos (7d, 7e) y extrínsecos (7f); «recalibrar y continuar» (P53, 7g; botón 7h): extrínsecos válidos para su sesión, 20 vistas en ~10 min (P60 c); la fusión no arranca con extrínsecos de otro día o > 12 h (P61); los grados del criterio 1, informativos (P54). La 7b se retira.
- **Fase 7c (`80e21a9`)** · el generador del marker ID 100 (`diagnostics/marker_image.py`, salida en `Claude outputs/fases/006/fase-7c/marker/`), `profiles.check_markers`, copias congeladas de los perfiles. **Fase 7c2 (`3b271df`)** · el perfil nombra `Reference`, la cadena publica `ReferenceToTracker` (matrices iguales byte a byte; replay 8/8 en 0.0), `slicer/receive_reference.py`. **Los perfiles siguen con ID 0 y 80 mm;** falta la sesión con Slicer (`fase-7c/protocolo.md`). ADR G7 en `fase-7c2-implementa.md`.
- **Fase 7d · El tablero ChArUco y los intrínsecos con el asistente de una cámara (`7d35af1`):** hecha sin cámara, criterio 9 a medias (P66): `calibration/charuco_board.py`, `stl_bicolor.py`, `capture_stereo_board --modo intrinsecos`, `calibrate_camera --desde-asistente`. Muestra y tablero generados en `Claude outputs/fases/006/fase-7d/` (`imprimir_y_medir.md`). El detector de los perfiles (36h12, tasa 0.6) lee IDs fantasma con el tablero a la vista, a veces el 100: B39 en alta. B129, B127.
- **Fase 7d2 · Los IDs falsos del tablero en el detector del tracker (B39): parte sin cámara hecha, pendiente del commit; la casilla sigue sin marcar.** `diagnostics/barrido_correccion.py` (`barrer`, `elegir` con P69 y P74, `perfil`; no toca la cadena ni `profiles/`). Sintético: referencia ID 100 leída en las 2028 poses con 0.40 a 0.20 (con 0.60, 1816); tablero solo, fantasmas 674 con 0.60 y 0 con 0.30. Con frames reales del Marker0 (ID 0, sin ChArUco), 0.60 ya da 32 fantasmas en 31 de 206 frames (0 de 0.45 abajo): B39 no es solo del ChArUco. Como mucho 0.30; la sesión decide entre 0.30, 0.20 o ninguna. B130 (prueba suelta de `test_referencia_id.py` con CPU cargada), B131, B132.
- **Lo siguiente, en orden:** commit de la 7d2 (parte sin cámara) → **7d2b · Un ID repetido no se publica (B39 c; toca la cadena; escribe el `correr.ps1` de la sesión)** → sesión conjunta 7c2 + 7d2b + 7d2 (P73 = b: sin copia de papel; pasa los perfiles a ID 100 y la tasa) → cierre de la 7d2 (prueba del criterio 9 sin `xfail`) → 7e · Recalibrar gs1 y gs2 → 7 parte sin cámara 2 → 7f → 7g → 7 sesión 2 → 7h; después las Fases 3 a 6 y 8. ADR G1 (el PC detecta y fusiona, P33) sin escribir desde el 2026-11-05.
- Qué es: GTSAM fusiona lo de gs1 y gs2; el IMU después. P1–P67 en `specs/006-*/clarify.md`.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- **Fases 1 a 7 hechas y commiteadas** (números en `tasks.md`; detalle en `docs/CONTEXT.md` §6). Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea). Pendientes: B85, B86, B91, el ADR J2.
- **Fase 7b · Las dos cámaras a la vez en Windows: B5 ya cumple** (`244d31e`, `ba3ed36`, `9d0a9fa`). B4 gs1 81.7 fps, **faltan los Hz de Slicer**. B5 cumple con gs2 en el frontal USB 3.0 (`…#USB(5)`), ~89–90 fps cada una (B97; CONTEXT §4.21).
- **Al retomarla:** cerrar la 7b (los Hz de B4, la parte C), Fase 8 · El panel del PC lanza y para el tracker de la Jetson, y Fase 9.

## Pendientes del autor

- **Meta 006:** imprimir la muestra 3×3 del ChArUco, medir con calibrador el lado de una casilla negra (25.8–26.2 mm; B129), y después el tablero y sus 5 medidas (`Claude outputs/fases/006/fase-7d/imprimir_y_medir.md`); el marker ID 100 ya está impreso y medido (2026-11-11): cinco medidas de 99.8 mm, `size_mm` 99.8, cuadrado; va a los perfiles con `id: 100` al preparar la sesión conjunta; ninguna sesión con la referencia vale hasta cerrar la 7c2; los `correr.ps1` viejos piden `Marker0ToTracker` y no valen. Miniforge, para la Fase 6.
- **Meta 007 (en pausa):** los Hz de Slicer de B4; `enviar_wip.ps1` y `ssh nav-jetson suite wip` con la parte B; la Wi-Fi de la Jetson (B86, con sudo); el cable directo (B85).
- Meta 005 (aplazado hasta compartirlo con los compañeros): las pruebas en vivo de las fases 1 a 4, con sus protocolos en `Claude outputs/fases/005/`.
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Abiertos

- **Regla de procedimiento (autor, 2026-11-11, P66; B39):** el tablero ChArUco, **fuera de la vista antes de arrancar el tracker**, en todo protocolo con la referencia (7e, 7g, sesión 2) hasta que la fase de `error_correction_rate` lo cierre. La prueba del criterio 9 (`xfail(strict=True)`, P67) la quita esa fase.
- B55: se usa el Marker0 de 80 mm hasta la sesión conjunta (las medidas del de 100 ya están: 99.8 mm).

## Trampas de la sesión

- `.git`: 691 MB en objetos sueltos (0 packs) y un temporal basura: B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"`.
- En Slicer, cerrar la escena antes de medir con `receive_reference.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
