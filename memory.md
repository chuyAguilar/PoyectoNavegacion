# memory.md — estado de hoy

_Actualizado: 2026-11-12 (meta 006 · Grafo de factores óptico-inercial, activa: 7c4 sin cámara hecha, a la espera del commit; la 7c3 espera P9 en vivo; metas 007 y 005 en pausa)._

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
- La cadena publica solo `ReferenceToTracker` (ADR-036, que sustituye a ADR-026 en el nombre; antes `Marker0ToTracker`), puerto 18944. Un ID repetido en un frame no se publica (ADR-037). Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta (código 3, sin abrir la cámara).
- `tracker --stop-stdin` sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout`; `--no-detect` es la vista previa, solo por CLI (P17 = a).
- El panel: «Verificar IDs y colocar la cámara», «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana.

## La suite

- `codigo/tests/`: **1535: 1525 pasan, 10 saltadas, 0 xfail, 0 fallan**; 237 s y 313 s en dos corridas (2026-11-12, cierre de la 7c4: +15 pruebas; antes, 1520 en 222 s). El `pytest.ini` ya trae `-q`: con otro `-q` no sale la línea final (usar `-o addopts="-p no:cacheprovider"`). Dos corridas del mismo árbol difieren ~25 %: es la carga de la máquina; el margen contra el tope de 600 s baja (B115); B130: dos pruebas de `test_referencia_id.py` pueden fallar sueltas con la CPU cargada. Las 10 saltadas: 9 «solo Linux» y 1 solo en la Jetson. En la Jetson: `ssh nav-jetson suite wip` (P22). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`.
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

- **Hecho** (números en `tasks.md`; detalle en `docs/history/006_tasks_2026-11-1{1,2}.md`): Fases 1 parte A y 2; 7a; 7c y 7c2 (ADR-036); 7d (tablero 25.95 mm); 7d2 (tasa 0.3) y 7d2b (ADR-037), con la sesión conjunta del 2026-11-12 (P83–P84); 7c3 sin cámara; **7c4 sin cámara** (P91 a; B141). La Fase 7, parcial (P45). **P9 de la 7c3 no válida (P85):** los perfiles siguen en 99.8 mm; P4 dio 51.60 / 51.01 mm.
- **Lo siguiente, en orden:** 7e · Recalibrar gs1 y gs2, cuya sesión repite P9 (`fase-7c3/p9/correr.ps1`) y P4, y compara los intrínsecos con los dos detectores (B141) → cierre de la 7c3 → 7 parte sin cámara 2 → 7f → 7g → 7 sesión 2 → 7h; después las Fases 3 a 6 y 8.
- **Replan del 2026-11-11 (P46–P74):** ChArUco para intrínsecos (7d, 7e) y extrínsecos (7f); «recalibrar y continuar» (7g; botón 7h): 20 vistas en ~10 min (P60 c); la fusión no arranca con extrínsecos de otro día o > 12 h (P61). La 7c3 mide el borde que ve el detector (P81 a); su `size_mm` se cambia solo si la medida vale (P77).
- Qué es: GTSAM fusiona lo de gs1 y gs2; el IMU después. P1–P85 en `specs/006-*/clarify.md`.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- Fases 1 a 7 hechas (detalle en `specs/007-jetson/tasks.md`). Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea). Fase 7b: B5 cumple con gs2 en el frontal USB 3.0 (`…#USB(5)`, CONTEXT §4.21); faltan los Hz de Slicer de B4 y la parte C. Al retomarla: cerrar la 7b, Fases 8 y 9; pendientes B85, B86, B91 y el ADR J2.

## Pendientes del autor

- **Meta 006:** el commit de la 7c4. Los `correr.ps1` anteriores a la 7c2 piden `Marker0ToTracker` y no valen. La casilla del tablero solo se midió a lo ancho (P85). Miniforge, para la Fase 6.
- **Meta 007 (en pausa):** los Hz de Slicer de B4; `enviar_wip.ps1` y `ssh nav-jetson suite wip` con la parte B; la Wi-Fi de la Jetson (B86, con sudo); el cable directo (B85).
- Meta 005 (aplazado hasta compartirlo con los compañeros): las pruebas en vivo de las fases 1 a 4, con sus protocolos en `Claude outputs/fases/005/`.
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Abiertos

- **Regla de procedimiento (autor, P66, P71):** el tablero ChArUco, **fuera de la vista antes de arrancar el tracker**, en todo protocolo con la referencia; es la trampa `docs/CONTEXT.md` §4.22 (la tasa 0.3 no cubre toda luz y ángulo, y un 100 falso suelto se publicaría, B134).
- **El criterio de P3 de los scripts que lean nodos de Slicer** debe excluir los `Red/Green/Yellow Transform` de las vistas de corte (B138; el `verificar.ps1` de la 7e).

## Trampas de la sesión

- `.git`: 691 MB en objetos sueltos (0 packs) y un temporal basura: B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"`.
- En Slicer, cerrar la escena antes de medir con `receive_reference.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
