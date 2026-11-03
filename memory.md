# memory.md — estado de hoy

_Actualizado: 2026-11-03 (meta 007 · El tracker en la Jetson Orin Nano: fases 1 a 5 commiteadas, fase 5b · El ruido de gs1 por V4L2 con la parte A hecha y la parte B en vivo del autor pendiente; la meta 006 · Grafo de factores óptico-inercial en espera, y la 005 en pausa)._

Spec activo: `specs/007-jetson/`

Peticiones pendientes: 0

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker:** cerrada el 2026-10-26 (P12: 0 dudas). Todo en `docs/ARCHITECTURE.md` §9 (ADR-032).

- **Meta 005 · Agente de consulta para el equipo y buzón de peticiones — en pausa** (`specs/005-equipo-consulta/`; ADR-034). El autor la pausó el 2026-10-29. Hechas y commiteadas las fases 1 a 4 (`bc328b2` a `7d2ac24`). `settings.json` no ganó los `allow` de la fase 4: `direccion` pide permiso para el `git fetch` y el script al arrancar. Al retomarla: lo en vivo de las fases 1–4 (abajo), los usuarios de GitHub de Kike, Armando y el doctor Milton, el ruleset de `main`, y su fase 5 · Un compañero real instala, pregunta y envía una petición, con el cierre. Mientras siga en pausa, `direccion` mira las peticiones al arrancar.
- Sin verificar: que `git push --dry-run origin HEAD:main` (paso 9 de `EQUIPO.md`) abra Git Credential Manager.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout` y cierra en un `finally`; `--no-detect` es la vista previa, solo por CLI desde la 8a (P17 = a).
- Desde la fase 8a: el panel tiene «Verificar IDs y colocar la cámara» (IDs, cruz y fps de la cámara; `identify_ids` lee por `FrameGrabber`; desde la fase 2b de la meta 004 pone también el semáforo «Cámara» y ya no hay «Probar cámara»), «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana; los perfiles no cambian.

## La suite

- `codigo/tests/`: **920: 915 pasan y 5 saltadas** (4 «solo Linux»: tope, grupo de procesos y `_parar_grupo`; 1 solo en la Jetson: el clon sin datos de paciente); 98.9 y 93.3 s de pytest (2026-11-03, fase 5b de la meta 007; `test_probar_barrera.py` añade ~35 s, B72). **En la Jetson** (`ssh nav-jetson suite wip`): 920: 862 pasan, 0 fallan, 58 saltadas, 45.2 s; en Linux el replay admite 1e-3 mm/°/px (P22) y lo que solo vale en Windows o necesita `docs/` se salta con su motivo (`codigo/linux/README.md`, «La suite en Linux»). Antes, 885 en 104.9 y 91.2 s (fase 5) y 641 en 44.0 s al cerrar la meta 004. Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell, sin suponer que los saca de otro sitio (regla del autor, 2026-10-25).

## Después de la meta 007

- La meta 006 · Grafo de factores óptico-inercial, sobre la Jetson; la 005 sigue en pausa hasta su fase 5. Instrumento y punta con un transform nuevo (ADR-025) sigue pendiente. Slicer recibe como mucho ~65 Hz (B54; `specs/003-*/resultados.md`).

## Meta 006 · Grafo de factores óptico-inercial (en espera tras la meta 007; spec y plan escritos el 2026-10-29, plan sin autorizar; era la 005 hasta el 2026-10-27)

- **En espera (decisión del autor, 2026-10-29):** primero la meta 007 · El tracker en la Jetson Orin Nano; la 006 se construye después sobre la Jetson. Su plan (`specs/006-grafo-factores/plan.md`, P8–P18 contestadas en `clarify.md`, P19 y P20 abiertas) está hecho para Windows: al retomarla se rehace para la Jetson (P8, conda en Windows, cae: GTSAM tiene rueda de pip para Linux aarch64; fps, CPU y la elección entre un proceso y dos trackers se miden allí).

- Qué es: un grafo de factores (GTSAM) que fusiona las poses ArUco de gs1 y gs2; solo cámaras. Las respuestas del autor (P1–P21) están en `specs/006-*/clarify.md`. El GitHub MCP, nunca con `--scope project` (el repo es público). Fuente: `documentos/tecnicos/Factor Graphs for robot perception.pdf`, sin seguir en git.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (activa; plan autorizado el 2026-10-29)

- **Fases 1 a 4: hechas y commiteadas** (`e71dea4`; `d2f3632`, `107a89e`; `24b046f`, `efbd138`, `56a4337`; `34d5941`; números en `tasks.md`, detalle en `Claude outputs/fases/007/`). La Jetson: Ubuntu 22.04.5, L4T 36.4.3, `v4l2-ctl` 1.22.1; gs1 en `usb-0:2.1` con `focus` 500 y gs2 en `usb-0:2.2` con 332, las dos en el mismo hub USB 2.0; 18944 libre, `ufw` inactivo (B71). **La regla ya vale** (2026-11-02): los agentes entran solo por `ssh nav-jetson <verbo>`; un 126 es el guardián y no se rodea; el autor teclea lo que abre la cámara (P19, P20 en (a)). Entorno: uv, CPython 3.11.9, `~/.venvs/navegacion`, clon sin datos de paciente. La suite corre en Linux con 0 fallos (P22: 1e-3).
- **Fase 5 · La capa V4L2 y cada cámara en la Jetson: hecha** (2026-11-03; `89712d6` y el cierre `76117f3`). `camera/v4l2.py` (`CamaraV4L2`, `CapaLinuxV4L2` con `v4l2-ctl`; CLI `--listar|--leer|--aplicar`); `WebcamBackend` en Linux abre `/dev/videoN` con `CAP_V4L2` por el by-path (`usb_port_linux` en los perfiles); Windows hace las mismas llamadas. **P-5 del autor** (sin ventana, caja de luz al máximo): bucle 87.5 fps (gs1) y 87.8 (gs2), cámara 88.5; sd z 0.074 y 0.040 mm; pose en el 99.7 y el 99.5 %; marca cruzada para con código 1; sin cliente, código 3 a los 10 s; PC con Slicer 67.6 Hz. Con ventana, sin medir (B80). La sd z de gs1 duplica la de MSMF (0.032–0.043): B77. Sus 8 hallazgos: B77 a B84. Detalle en `Claude outputs/fases/007/fase-5.md`.
- **Lo lanzado tras el P-5:** `ssh nav-jetson repo actualizar` dejó el clon en `89712d6`; `suite repo -q` lo negó el clasificador de permisos al agente y lo corrió el autor (2026-11-03): código 0, 0 fallos, 39.4 s (`-q` no da el recuento).
- **Fase 5b · El ruido de gs1 por V4L2 (B77): parte A hecha, parte B pendiente** (2026-11-03; autorizada por P23, P24 = (a), P25 = (a); plan en `e379655`). Entregado, pendiente del commit parcial: `diagnostics/ruido_pose.py`, `linux/perfil_temporal.py` (cierra B81) y sus 31 pruebas. Lectura de la parte A sobre las tres grabaciones del P-5: la sd z de gs1 (0.074 mm) es casi toda lenta (deriva monótona de −3.9 µm/s, 0.23 mm en 60 s; residuo rápido 0.022); no es el filtro (0 % de dt < 2 ms) ni dos valores (Sarle 0.38): apunta a calor, mecánica o luz, no a un control. La casilla sigue sin marcar. **Falta la parte B, del autor:** el protocolo P-5b en `Claude outputs/fases/007/p5b.md` (J1–J4 en la Jetson, W1 y W2 en el PC, los `info v4l2`). Después, el agente trae los archivos, corre `ruido_pose` y escribe la puerta (causa clara o «sin causa clara»).
- **Lo siguiente:** el autor corre el P-5b; luego la dirección le propone confirmar los mínimos de P13 (87.5 fps de bucle y 99.5 % de pose, el ≥ 60 se cumple) y la fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes.

## Pendientes del autor

- **Meta 007:** correr el P-5b de la fase 5b (`Claude outputs/fases/007/p5b.md`; cables de gs1 y gs2 intercambiados en J4). Confirmar los mínimos de P13 y decidir B77 con sus números antes de la fase 6.

- Meta 005 (aplazado por el autor hasta compartirlo con sus compañeros, 2026-10-28): la prueba en vivo de la fase 1 (7 casos), la de la fase 2 (2 envíos con `consulta`), la lectura de `docs/EQUIPO.md` de la fase 3 (10 pasos, ~20 min) y el circuito de la fase 4 (una petición de prueba a `origin`, ~10 min), con sus protocolos en `Claude outputs/fases/005/`.
- Instalar el GitHub MCP (lo configura el autor) antes de planear la meta 006 · Grafo de factores óptico-inercial.
- La prueba en vivo de la regla (fase 2c, meta 004) la dejó el autor; si vuelve a congelarse, se retoma (`Claude outputs/fases/004/fase-2c.md`).
- B55: decidido el 2026-10-26, se usa el Marker0 de 80 mm y el de 100 se guarda (media).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"` (el `.gitattributes` lo normaliza, pero el árbol queda con CRLF).
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
