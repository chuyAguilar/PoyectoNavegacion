# memory.md — estado de hoy

_Actualizado: 2026-11-11 (meta 006 · Grafo de factores óptico-inercial, activa: replan autorizado el 2026-11-11 con las fases 7c a 7h (P45–P65); la Fase 7c · La referencia con su propio ID, hecha sin cámara (pendiente del commit); lo siguiente, la 7c2 · `Reference` y `ReferenceToTracker`; la 7a, hecha y commiteada; la Fase 7, parcial; la meta 007 · El tracker en la Jetson Orin Nano, en pausa, y la 005 también)._

Spec activo: `specs/006-grafo-factores/`

Peticiones pendientes: 0

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 y 2 commiteadas; la 3 (hooks) cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Metas 001 (limpieza, 2026-10-19) y 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker:** cerrada el 2026-10-26 (P12: 0 dudas). Todo en `docs/ARCHITECTURE.md` §9 (ADR-032).

- **Meta 005 · Agente de consulta para el equipo y buzón de peticiones — en pausa** (`specs/005-equipo-consulta/`; ADR-034). El autor la pausó el 2026-10-29. Fases 1 a 4 commiteadas (`bc328b2` a `7d2ac24`). Al retomarla: lo en vivo de las fases 1–4 (abajo), los usuarios de GitHub de Kike, Armando y el doctor Milton, el ruleset de `main`, y su fase 5 · Un compañero real instala, pregunta y envía una petición. Mientras siga en pausa, `direccion` mira las peticiones al arrancar.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout` y cierra en un `finally`; `--no-detect` es la vista previa, solo por CLI desde la 8a (P17 = a).
- Desde la fase 8a: el panel tiene «Verificar IDs y colocar la cámara» (IDs, cruz y fps de la cámara; `identify_ids` lee por `FrameGrabber`; desde la fase 2b de la meta 004 pone también el semáforo «Cámara» y ya no hay «Probar cámara»), «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana; los perfiles no cambian.

## La suite

- `codigo/tests/`: **1313: 1303 pasan, 10 saltadas, 0 fallan** (9 «solo Linux»: tope, grupo de procesos, `_parar_grupo` y el pyigtl real con `iface`; 1 solo en la Jetson: el clon sin datos de paciente); 286.9 y 346.3 s (2026-11-11, meta 006 fase 7c, sin cámara; antes 1199 en 182.8 y 201.6 s: las 114 pruebas nuevas solas tardan ~5 s, el resto es carga de la máquina; con 346 s el margen contra el tope de 600 s baja, vigilar B115). `test_probar_barrera.py` añade ~35 s (B72). **En la Jetson** (`ssh nav-jetson suite wip`): la última corrida, fase 7b parte A, 1051: 993 pasan, 0 fallan, 58 saltadas, 52.4 s (la parte B, sin correr); en Linux el replay admite 1e-3 mm/°/px (P22) y lo que solo vale en Windows o necesita `docs/` se salta con su motivo (`codigo/linux/README.md`, «La suite en Linux»). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell, sin suponer que los saca de otro sitio (regla del autor, 2026-10-25).

## Meta 006 · Grafo de factores óptico-inercial (activa desde el 2026-11-05; replan autorizado el 2026-11-11)

- **Fase 1 · parte A (sin gtsam): hecha (`a1a714b`).** `codigo/fusion/` fuera de línea, sobre la Jetson: jitter −31.9 % (pose) / −63.1 % (PnP conjunto); extrínsecos por Marker0 19.5 mm / 5.82° (B94, alta). B95, B96.
- **Fase 2 · S2 otra vez en Windows, y B94: hecha (`ccfe803`), «se movió».** `grabacion-pc/datos/20261109-163350`; criterio 1 4.198 mm / 6.087° (¿a escala 0.81?, nota en `tasks.md`); criterio 2 62.4 / 61.1 %. B100, B102. Reporte: `Claude outputs/fases/006/fase-2.md`.
- **Plan por P33 (2026-11-05):** el PC detecta con las dos cámaras y fusiona: Fases 3 · Cada tracker envía sus esquinas al fusionador; 4 · El fusionador del PC, sin GTSAM; 5 · La fusión en vivo con Slicer; 6 · El grafo con GTSAM; 8 · Cierre.
- **Fase 7 · Los extrínsecos por tablero: parcial (sin cámara, `1cf90c3`).** `calibrate_extrinsics --desde-vistas`; distancia nominal 200.43 mm. B104, B105.
- **Fase 7c · La referencia con su propio ID: hecha sin cámara (pendiente del commit).** `diagnostics/marker_image.py` (SVG, PNG y STL bicolor del ID 100 de ~100 mm, listos en `Claude outputs/fases/006/fase-7c/marker/`), `profiles.check_markers` y las copias congeladas `tests/data/marker0_gs{1,2}_perfil.yaml`; **los perfiles siguen con ID 0 y 80 mm** hasta las 5 medidas del autor. Replay 8/8 en 0.0. B39 ampliada, B127.
- **Fase 7a · El asistente de captura del tablero: hecha (`238117e`).** `calibration/capture_stereo_board.py`. La prueba de 20 poses da 0.294 mm (no < 0.01) por esquinas renderizadas; el formato, igual (0.0). B114, B115.
- **Sesión con el asistente (2026-11-11, `fase-7/asistente/correr_20261111-124742`):** el asistente cumple (dos cámaras en un proceso, 90 fps, 20 vistas en 8.6 min, 9 % rechazadas); el cálculo no (RMS 0.548 px, control 1.611, triangulada 0.908 mm). Base del tablero 236.6 mm; el autor mide ~25 cm. S2 repetida sin tocar nada: `grabacion-pc/datos/20261111-131000`.
- **Diagnóstico sin cámara (P45 a; `fase-7/diagnostico-20261111/reporte.md`):** las cámaras giraron 12° entre el 11-09 y el 11-11; la S2 del 11-11 fue con el **marker de ~100 mm y el perfil en 80 (B55, ahora alta)**: lado triangulado 98.3–98.6 mm; con la escala corregida, criterio 1 0.87–1.12 mm, pero 5.4–6.6° con cualquier extrínseco (IPPE, B95). gs2 cambió de intrínsecos (fx +11, cx −9.5, cy −7.3 px; 4–7 σ). Queda ~0.5 px por vista agrupado en el tiempo: el montaje de pinzas no es rígido (el autor lo confirma). El autor cree probable que la S2 del 11-09 también fuera con el de 100: los mm de la Fase 2 estarían a escala 0.81 (nota en `tasks.md`).
- **Replan del 2026-11-11, autorizado ese día (P46–P65):** la referencia pasa a ID 100 (~100 mm), se llama `Reference` y la cadena publica `ReferenceToTracker` (P57; ADR G7, enmienda el principio 6); ChArUco 9×7 de 26 mm, `DICT_4X4_50`, para intrínsecos (7d, 7e) y extrínsecos (7f); «recalibrar y continuar» (P53): los extrínsecos valen para su sesión, `python -m calibration.recalibrar` con 20 vistas en ~10 min (P60 c) y botón del panel; la fusión no arranca con extrínsecos de otro día o > 12 h y en vivo avisa (P61); los grados del criterio 1, informativos (P54). La 7b se retira. B116–B126 anotadas.
- **Lo siguiente, en orden:** 7c2 · `Reference` y `ReferenceToTracker` (sesión con Slicer) → 7d · El tablero ChArUco y los intrínsecos (avisar para imprimir la muestra 3×3 y el tablero) → 7e → 7 parte sin cámara 2 → 7f → 7g → 7 sesión 2 → 7h; después las Fases 3 a 6 y 8. ADR G1 (la meta 006 es «el PC detecta y fusiona», P33) sigue sin escribir desde el 2026-11-05.
- Qué es: GTSAM fusiona lo de gs1 y gs2; el IMU después. P1–P65 en `specs/006-*/clarify.md`.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- **Fases 1 a 7 hechas y commiteadas** (números y commits en `tasks.md`; detalle en `docs/CONTEXT.md` §6). Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea). Pendientes: B85, B86, B91, el ADR J2.
- **Fase 7b · Las dos cámaras a la vez en Windows: B5 ya cumple.** Partes A `244d31e` y B `ba3ed36`; commit `9d0a9fa`. B4 gs1 81.7 fps, **faltan los Hz de Slicer**. B5 falló con las dos en el concentrador Genesys (USB 2.0) y cumple con gs2 en el frontal USB 3.0 (`…#USB(5)`), ~89–90 fps cada una (B97; el perfil de gs2 ya lo lleva; CONTEXT §4.21).
- **Al retomarla:** cerrar la 7b (los Hz de B4, la parte C con gs2 en `USB(5)`), Fase 8 · El panel del PC lanza y para el tracker de la Jetson, y Fase 9.

## Pendientes del autor

- **Meta 006:** imprimir el marker ID 100 (`Claude outputs/fases/006/fase-7c/imprimir_y_medir.md`; dar las 5 medidas con calibrador) y el ChArUco cuando salga su generador (7d); ninguna sesión con Marker0 vale hasta cerrar la 7c2. Miniforge, para la Fase 6.
- **Meta 007 (en pausa):** los Hz de Slicer de B4; `enviar_wip.ps1` y `ssh nav-jetson suite wip` con la parte B (esperado 0 fallos); hacer persistente el ahorro de energía de la Wi-Fi de la Jetson (B86, con sudo); el cable directo (B85) antes de llevarla.

- Meta 005 (aplazado hasta compartirlo con los compañeros, 2026-10-28): las pruebas en vivo de las fases 1 a 4, con sus protocolos en `Claude outputs/fases/005/`.
- B55: decidido el 2026-10-26, se usa el Marker0 de 80 mm y el de 100 se guarda (media).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git`: 691 MB en objetos sueltos (0 packs) y un temporal basura: B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"` (el `.gitattributes` lo normaliza, pero el árbol queda con CRLF).
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
