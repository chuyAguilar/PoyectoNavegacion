# memory.md — estado de hoy

_Actualizado: 2026-11-12 (meta 006 · Grafo de factores óptico-inercial, activa; cierre tras la sesión conjunta del 2026-11-12 de la Fase 7c2 · `Reference` y `ReferenceToTracker`, la Fase 7d2b · Un ID repetido no se publica y la Fase 7d2 · Los IDs falsos del tablero: la tasa 0.3 en los perfiles, pendiente del commit del autor; la Fase 7c3 · El tamaño de la referencia medido con el tablero, sin cámara commiteada (`503a0d0`), P9 no válida (P85); la meta 007 · El tracker en la Jetson Orin Nano, en pausa, y la 005 también)._

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

- `codigo/tests/`: **1520: 1510 pasan, 10 saltadas, 0 xfail, 0 fallan**; 222 s (2026-11-12, cierre de la 7d2: sin los dos `xfail` de P67 y P75 y una prueba nueva; antes, 1507 + 2 xfail en 220–234 s). El `pytest.ini` ya trae `-q`: con otro `-q` no sale la línea final (usar `-o addopts="-p no:cacheprovider"`). Dos corridas del mismo árbol difieren ~25 %: es la carga de la máquina; el margen contra el tope de 600 s baja (B115); B130: dos pruebas de `test_referencia_id.py` pueden fallar sueltas con la CPU cargada. Las 10 saltadas: 9 «solo Linux» y 1 solo en la Jetson. **En la Jetson** (`ssh nav-jetson suite wip`): la última, fase 7b parte A, 993 pasan, 0 fallan; en Linux el replay admite 1e-3 mm/°/px (P22). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`.
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

- **Hecho** (números en `tasks.md`; detalle hasta el 2026-11-11 en `docs/history/`): Fases 1 parte A y 2 (B94 «se movió»); 7a, el asistente de captura; 7c y 7c2 (la referencia es `Reference`, el ID 100 de 99.8 mm, y la cadena publica `ReferenceToTracker`; las copias congeladas del replay siguen en ID 0 y 80 mm); 7d sin cámara (ChArUco 9×7, casilla medida 25.95 mm); 7d2b (`26a23eb`: un ID repetido en un frame no se publica y se cuenta); 7c3 sin cámara (`503a0d0`, `calibration/medir_referencia.py`). La Fase 7 (extrínsecos por tablero), parcial: la sesión del 2026-11-11 no cumplió (P45: cámaras giradas, B55, gs2 con otros intrínsecos, montaje no rígido).
- **Sesión conjunta del 2026-11-12** (`Claude outputs/fases/006/fase-7c/correr_20261112-171751`; P83–P85): 7c2 cerrada en vivo (90.0 / 89.8 fps, Slicer 64 / 62 Hz; P3 «NO» falso por las vistas de corte de Slicer, B138; «se mueve 50 mm» 51.60 / 51.01, se vuelve a medir tras la 7e y la 7c3); 7d2b en vivo (2 dobles del 100 en P7 gs2, contados y sin envío); **7d2 cerrada: `error_correction_rate: 0.3` en los dos perfiles** (0 falsos en P5–P8 y sintético; 0 de 1072 perdidos; con el tablero a la vista 52–66 fps, B137); B39 cerrada; sin `xfail` en la suite. **P9 de la 7c3 no válida** (gs2 casi sin el tablero entero; gs1 con lados ~3 mm distintos y colocaciones 98.5 / 100.4): los perfiles siguen en 99.8.
- **Lo siguiente, en orden:** commit de este cierre → diagnóstico corto sobre los PNG de P9 (encuadre, planitud o geometría del tablero; P85 a) → 7e · Recalibrar gs1 y gs2, cuya sesión repite P9 y P4 → cierre de la 7c3 → 7 parte sin cámara 2 → 7f → 7g → 7 sesión 2 → 7h; después las Fases 3 a 6 y 8. Los ADR G7 y G11, los escribe la dirección.
- **Replan del 2026-11-11 (P46–P74):** ChArUco para intrínsecos (7d, 7e) y extrínsecos (7f); «recalibrar y continuar» (7g; botón 7h): 20 vistas en ~10 min (P60 c); la fusión no arranca con extrínsecos de otro día o > 12 h (P61). La 7c3 mide el borde que ve el detector (P81 a); su `size_mm` se cambia solo si la medida vale (P77).
- Qué es: GTSAM fusiona lo de gs1 y gs2; el IMU después. P1–P74 en `specs/006-*/clarify.md`.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- **Fases 1 a 7 hechas y commiteadas** (números en `tasks.md`; detalle en `docs/CONTEXT.md` §6). Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea). Pendientes: B85, B86, B91, el ADR J2.
- **Fase 7b · Las dos cámaras a la vez en Windows: B5 ya cumple** (`244d31e`, `ba3ed36`, `9d0a9fa`). B4 gs1 81.7 fps, **faltan los Hz de Slicer**. B5 cumple con gs2 en el frontal USB 3.0 (`…#USB(5)`), ~89–90 fps cada una (B97; CONTEXT §4.21).
- **Al retomarla:** cerrar la 7b (los Hz de B4, la parte C), Fase 8 · El panel del PC lanza y para el tracker de la Jetson, y Fase 9.

## Pendientes del autor

- **Meta 006:** el commit de este cierre (la tasa 0.3 y las casillas). Los `correr.ps1` anteriores a la 7c2 piden `Marker0ToTracker` y no valen. La casilla del tablero solo se midió a lo ancho (P85). Miniforge, para la Fase 6.
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
