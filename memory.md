# memory.md — estado de hoy

_Actualizado: 2026-11-05 (meta 007 · El tracker en la Jetson Orin Nano, fase 7b: B5 cumple con gs2 en el frontal USB 3.0; la meta 006 · Grafo de factores óptico-inercial, activa; la 005, en pausa)._

Spec activo: `specs/006-grafo-factores/`

Peticiones pendientes: 0

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker:** cerrada el 2026-10-26 (P12: 0 dudas). Todo en `docs/ARCHITECTURE.md` §9 (ADR-032).

- **Meta 005 · Agente de consulta para el equipo y buzón de peticiones — en pausa** (`specs/005-equipo-consulta/`; ADR-034). El autor la pausó el 2026-10-29. Hechas y commiteadas las fases 1 a 4 (`bc328b2` a `7d2ac24`). `settings.json` no ganó los `allow` de la fase 4: `direccion` pide permiso para el `git fetch` y el script al arrancar. Al retomarla: lo en vivo de las fases 1–4 (abajo), los usuarios de GitHub de Kike, Armando y el doctor Milton, el ruleset de `main`, y su fase 5 · Un compañero real instala, pregunta y envía una petición, con el cierre. Mientras siga en pausa, `direccion` mira las peticiones al arrancar.
- Sin verificar: que `git push --dry-run` (paso 9 de `EQUIPO.md`) abra Git Credential Manager.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout` y cierra en un `finally`; `--no-detect` es la vista previa, solo por CLI desde la 8a (P17 = a).
- Desde la fase 8a: el panel tiene «Verificar IDs y colocar la cámara» (IDs, cruz y fps de la cámara; `identify_ids` lee por `FrameGrabber`; desde la fase 2b de la meta 004 pone también el semáforo «Cámara» y ya no hay «Probar cámara»), «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana; los perfiles no cambian.

## La suite

- `codigo/tests/`: **1128: 1118 pasan, 10 saltadas, 0 fallan** (9 «solo Linux»: tope, grupo de procesos, `_parar_grupo` y el pyigtl real con `iface`; 1 solo en la Jetson: el clon sin datos de paciente); 129.9 s (2026-11-05, el perfil de gs2 en `USB(5)`; antes 135.1 y 132.1 s en la meta 006 fase 1 parte A; antes 1071 en 108.5 s: sumó `test_fusion_*`). `test_probar_barrera.py` añade ~35 s (B72). **En la Jetson** (`ssh nav-jetson suite wip`): la última corrida, fase 7b parte A, 1051: 993 pasan, 0 fallan, 58 saltadas, 52.4 s (la parte B, sin correr); en Linux el replay admite 1e-3 mm/°/px (P22) y lo que solo vale en Windows o necesita `docs/` se salta con su motivo (`codigo/linux/README.md`, «La suite en Linux»). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell, sin suponer que los saca de otro sitio (regla del autor, 2026-10-25).

## Meta 006 · Grafo de factores óptico-inercial (activa desde el 2026-11-05; plan rehecho y autorizado)

- **Fase 1 · parte A (sin gtsam): hecha el 2026-11-05, pendiente del commit del autor.** Paquete `codigo/fusion/` (fuera de línea; la cadena sin tocar). Sobre la grabación `20261105-120826` (corrida en `Claude outputs/fases/006/fase-1/corrida-02/`, 180 s, reproducible byte a byte): fusionar baja el jitter −31.9 % (pose) / −63.1 % (PnP conjunto), pero **los extrínsecos por Marker0 no coinciden: 19.5 mm / 5.82° frente a < 0.5 mm / 0.2°**, y las 5 posiciones de S2 no caben en dos cámaras rígidas (**B94, alta**: mover una cámara o error sistemático de inclinación en la pose de un marker). Antes de la parte B: regrabar S2 sin tocar nada con pos1 al principio y al final, y la fase 2 (tablero). B95 (IPPE más ruidoso), B96 (δ no se ve en S4). Reporte: `Claude outputs/fases/006/fase-1a.md`.
- **Retomada el 2026-11-05 (P22, P23):** la arquitectura es **«la Jetson detecta, el PC fusiona»**. La Jetson abre gs1 y gs2 y llega, por cámara, a las esquinas y el PnP; el PC fusiona (GTSAM) y le publica a Slicer. La fase 1 tiene que ser ver si sirve: grabación con las dos en la Jetson (`--record`, lo que ya existe; se graba ya, antes del plan) y un experimento fuera de línea en el PC con el jitter fusionado frente a cada cámara sola. El plan de 2026-10-29 (hecho para Windows; P19 y P20 abiertas) lo rehace `planificacion`. Sin verificar: si `gtsam` instala en Windows (en la Jetson, 4.3.0 en un venv aparte).
- El PC ya puede con las dos cámaras a la vez (P-7b5); si P22 sigue valiendo lo decide el autor.
- Qué es: GTSAM fusiona lo de gs1 y gs2; solo cámaras, el IMU después. P1–P23 en `specs/006-*/clarify.md`. El GitHub MCP, nunca con `--scope project`. Fuente: `documentos/tecnicos/Factor Graphs for robot perception.pdf`, sin seguir en git.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- **Fases 1 a 7 hechas y commiteadas** (números y commits en `tasks.md`). La Jetson: Ubuntu 22.04.5, L4T 36.4.3; gs1 en `usb-0:2.1` (focus 500), gs2 en `usb-0:2.2` (332), mismo hub USB 2.0. Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea); el autor teclea lo que abre la cámara. Entorno: uv, CPython 3.11.9, `~/.venvs/navegacion`. Fase 5 (V4L2): bucle 87.5 / 87.8 fps, sd z 0.074 / 0.040 mm (gs1: deriva lenta, B77 baja). Fase 6: Slicer en el PC 84.0 Hz por la LAN (añadida p95 7.62 ms), 82.0 por Tailscale; `--igtl-iface`, `TCP_NODELAY`, `clock_offset`; cable directo sin probar (B85); el ahorro de energía de la Wi-Fi no persiste (B86); falta el ADR J2. Fase 7 (P-7, 450 s): las dos a la vez, cámara 86.2 fps, bucle 63.2 cada una; CPU 95.5 %, GPU 0 %, 69.9 °C (B91).
- **Fase 7b · Las dos cámaras a la vez en Windows: B5 ya cumple.** Parte A `244d31e`, parte B `ba3ed36` (marca y ajustes por COM). P-7b-B (2026-11-04): B1–B3 cumplen; B4 gs1 81.7 fps, **faltan los Hz de Slicer**; B5 fallaba con las dos en el concentrador Genesys `05E3:0608` (`HS11`, USB 2.0): la segunda no daba frames, `0x800718CF` «sin ancho de banda». **P-7b5 (2026-11-05): con gs2 en el frontal USB 3.0 (`…#USB(5)`, fuera del Genesys; la única variable cambiada) B5 cumple en los dos órdenes, ~89–90 fps de cámara y ~89 mensajes/s cada una.** La causa: dos reservas isócronas MJPG en un mismo enlace USB 2.0; cuánto reserva cada una, sin medir (B97). El perfil de gs2 ya lleva `USB(5)` y CONTEXT §4.21 dice la regla (una cámara por enlace USB 2.0). Análisis: `Claude outputs/fases/007/por-que-atorados-7b.md`. Pendiente del commit del autor.
- **Al retomarla:** cerrar la 7b (los Hz de B4, la parte C con gs2 en `USB(5)`), Fase 8 · El panel del PC lanza y para el tracker de la Jetson, y Fase 9.

## Pendientes del autor

- **Meta 006:** plan rehecho autorizado el 2026-11-05 (P24–P28 contestadas). Grabación hecha el 2026-11-05: `Claude outputs/fases/006/grabacion/datos/20261105-120826/`, 18 `.npz`; 8 de 9 tramos cumplen (S4_movimiento, gs2 con pose 71.6 %). Sd z en reposo, cada cámara sola: 0.046 / 0.043 mm. Falta instalar miniforge para la parte B y decidir sobre B94 (regrabar S2).
- **Meta 007 (en pausa):** los Hz de Slicer de B4; `enviar_wip.ps1` y `ssh nav-jetson suite wip` con la parte B (esperado 0 fallos); hacer persistente el ahorro de energía de la Wi-Fi de la Jetson (B86, con sudo); el cable directo (B85) antes de llevarla.

- Meta 005 (aplazado por el autor hasta compartirlo con sus compañeros, 2026-10-28): la prueba en vivo de la fase 1 (7 casos), la de la fase 2 (2 envíos con `consulta`), la lectura de `docs/EQUIPO.md` de la fase 3 (10 pasos, ~20 min) y el circuito de la fase 4 (una petición de prueba a `origin`, ~10 min), con sus protocolos en `Claude outputs/fases/005/`.
- Instalar el GitHub MCP (lo configura el autor) si `planificacion` lo necesita para la meta 006.
- La prueba en vivo de la regla (fase 2c, meta 004) la dejó el autor; si vuelve a congelarse, se retoma (`Claude outputs/fases/004/fase-2c.md`).
- B55: decidido el 2026-10-26, se usa el Marker0 de 80 mm y el de 100 se guarda (media).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git`: 691 MB en objetos sueltos (0 packs) y un temporal basura: B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"` (el `.gitattributes` lo normaliza, pero el árbol queda con CRLF).
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
