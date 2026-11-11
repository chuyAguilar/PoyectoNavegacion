# memory.md — estado de hoy

_Actualizado: 2026-11-10 (meta 006 · Grafo de factores óptico-inercial, activa: replan autorizado con la Fase 7a · El asistente de captura del tablero, P40–P44; la Fase 7 · Los extrínsecos por tablero, parcial, espera la sesión con el asistente; antes, la Fase 2 · S2 otra vez en Windows, y B94, hecha con «se movió»; la meta 007 · El tracker en la Jetson Orin Nano, en pausa, y la 005 también)._

Spec activo: `specs/006-grafo-factores/`

Peticiones pendientes: 0

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
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

- `codigo/tests/`: **1165: 1155 pasan, 10 saltadas, 0 fallan** (9 «solo Linux»: tope, grupo de procesos, `_parar_grupo` y el pyigtl real con `iface`; 1 solo en la Jetson: el clon sin datos de paciente); 152.3 y 146.8 s (2026-11-09, meta 006 fase 7, sin cámara; antes 1136 en 152.1 s). `test_probar_barrera.py` añade ~35 s (B72). **En la Jetson** (`ssh nav-jetson suite wip`): la última corrida, fase 7b parte A, 1051: 993 pasan, 0 fallan, 58 saltadas, 52.4 s (la parte B, sin correr); en Linux el replay admite 1e-3 mm/°/px (P22) y lo que solo vale en Windows o necesita `docs/` se salta con su motivo (`codigo/linux/README.md`, «La suite en Linux»). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell, sin suponer que los saca de otro sitio (regla del autor, 2026-10-25).

## Meta 006 · Grafo de factores óptico-inercial (activa desde el 2026-11-05; plan rehecho por P33 y autorizado el 2026-11-05)

- **Fase 1 · parte A (sin gtsam): hecha el 2026-11-05 (`a1a714b`).** Paquete `codigo/fusion/` (fuera de línea). Sobre la grabación de la Jetson `20261105-120826`: fusionar baja el jitter −31.9 % (pose) / −63.1 % (PnP conjunto), pero **los extrínsecos por Marker0 no coinciden: 19.5 mm / 5.82° frente a < 0.5 mm / 0.2°** (**B94, alta**: una cámara se movió, o error sistemático de inclinación en la pose). B95 (IPPE más ruidoso), B96 (δ no se ve en S4). Reporte: `Claude outputs/fases/006/fase-1a.md`.
- **Fase 2 · S2 otra vez en Windows, y B94: hecha el 2026-11-09, veredicto «se movió»** (sin cámara `be78d55`: `half_split`, `repeat_check`, `b94_verdict`, `fusion.extrinsics guardar`). Grabación del PC `grabacion-pc/datos/20261109-163350` (6 tramos de 40 s, pose 99.9–100 %); experimento en `fase-2/corrida-pc-01`: pos1 frente a pos1_fin 0.703 mm / 0.151° (marker devuelto a 2.56 mm / 1.41°), mitades de S2_pos2 0.952 mm (gs2 salta entre dos soluciones de IPPE), las demás ≤ 0.315; ajuste conjunto 0.298 px (cabe; Jetson 5.58); criterio 1 4.198 mm / 6.087° (Jetson 19.5 / 5.82); criterio 2 62.4 / 61.1 %. B94 sigue alta; B100 con los números del PC; B102 (parejas reales 1284–2343, bajo las 2000 de P16 en 3 de 5). Reporte: `Claude outputs/fases/006/fase-2.md`.
- **Plan rehecho por P33 (2026-11-05, Windows primero; P34–P39 la recomendada):** el PC detecta con las dos cámaras y fusiona; dos trackers con `--feed` (P38) y un fusionador que publica `Marker0ToTracker` con `numpy_reproj` (P39). Fases: 3 · Cada tracker envía sus esquinas al fusionador; 4 · El fusionador del PC, sin GTSAM; 5 · La fusión en vivo con Slicer; 6 · El grafo con GTSAM; 7 · Los extrínsecos por tablero (adelantada, P36); 7a · El asistente de captura del tablero; 7b · Sobre la estructura; 8 · Cierre.
- **Fase 7 · Los extrínsecos por tablero: parcial (sin cámara, `1cf90c3`).** `calibration/calibrate_extrinsics.py --desde-vistas`: sintético ΔT 9.5e-06 mm, ΔR 1.4e-06°; distancia nominal 200.43 mm, no 198.88. Falta lo en vivo (RMS, control, distancia, comparación con Marker0, criterio 1); sin eso no se cierra B94. B104 y B105 anotadas.
- **Sesión del tablero cortada (2026-11-10):** `fase-7/correr_20261110-180748` se detuvo en T04 por el tope de 15 min de la mano, 3 vistas usables y casi iguales (planas), equipo limpio. Las cámaras miran de arriba abajo; el tablero va sobre la mesa con cuñas (`fase-7/guia_posturas.md`). **P40 (a):** asistente en vivo; P41–P44 la recomendada (10° o 40 mm de variedad, objetivo 20 y mínimo 18, sesión de 45 min, la guía orienta). Replan autorizado el 2026-11-10. B111–B113 anotadas.
- **Lo siguiente:** Fase 7a · El asistente de captura del tablero (`calibration/capture_stereo_board.py`; pesada, Fable implementa); después la sesión con `fase-7/asistente/correr.ps1`, que cierra la Fase 7 y decide B94; la fusión en vivo (Fases 3 a 5) espera.
- Qué es: GTSAM fusiona lo de gs1 y gs2; solo cámaras, el IMU después. P1–P39 en `specs/006-*/clarify.md`. El GitHub MCP, nunca con `--scope project`. Fuente: `documentos/tecnicos/Factor Graphs for robot perception.pdf`, sin seguir en git.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- **Fases 1 a 7 hechas y commiteadas** (números y commits en `tasks.md`). La Jetson: Ubuntu 22.04.5, L4T 36.4.3; gs1 en `usb-0:2.1` (focus 500), gs2 en `usb-0:2.2` (332), mismo hub USB 2.0. Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea); el autor teclea lo que abre la cámara. Fase 6: Slicer en el PC 84.0 Hz por la LAN; cable directo sin probar (B85); Wi-Fi sin persistir (B86); falta el ADR J2. Fase 7: las dos a la vez, bucle 63.2; CPU 95.5 % (B91). Detalle en `docs/CONTEXT.md` §6.
- **Fase 7b · Las dos cámaras a la vez en Windows: B5 ya cumple.** Partes A `244d31e` y B `ba3ed36`; commit `9d0a9fa`. B4 gs1 81.7 fps, **faltan los Hz de Slicer**. B5 falló con las dos en el concentrador Genesys (USB 2.0) y cumple con gs2 en el frontal USB 3.0 (`…#USB(5)`), ~89–90 fps cada una (B97; el perfil de gs2 ya lo lleva; CONTEXT §4.21).
- **Al retomarla:** cerrar la 7b (los Hz de B4, la parte C con gs2 en `USB(5)`), Fase 8 · El panel del PC lanza y para el tracker de la Jetson, y Fase 9.

## Pendientes del autor

- **Meta 006:** no mover las cámaras hasta grabar el tablero; la sesión se hará con el asistente de la Fase 7a (`fase-7/asistente/correr.ps1`, con `-Simular` primero), no con `fase-7/correr.ps1`. Si las cámaras se movieron desde la Fase 2, repetir S2 justo después (`grabacion-pc\correr.ps1 -SinMirilla -SinVentana`, ~10 min). Miniforge, para la Fase 6.
- **Meta 007 (en pausa):** los Hz de Slicer de B4; `enviar_wip.ps1` y `ssh nav-jetson suite wip` con la parte B (esperado 0 fallos); hacer persistente el ahorro de energía de la Wi-Fi de la Jetson (B86, con sudo); el cable directo (B85) antes de llevarla.

- Meta 005 (aplazado por el autor hasta compartirlo con sus compañeros, 2026-10-28): la prueba en vivo de la fase 1 (7 casos), la de la fase 2 (2 envíos con `consulta`), la lectura de `docs/EQUIPO.md` de la fase 3 (10 pasos, ~20 min) y el circuito de la fase 4 (una petición de prueba a `origin`, ~10 min), con sus protocolos en `Claude outputs/fases/005/`.
- B55: decidido el 2026-10-26, se usa el Marker0 de 80 mm y el de 100 se guarda (media).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git`: 691 MB en objetos sueltos (0 packs) y un temporal basura: B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"` (el `.gitattributes` lo normaliza, pero el árbol queda con CRLF).
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
