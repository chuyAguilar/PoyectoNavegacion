# memory.md — estado de hoy

_Actualizado: 2026-11-12 (meta 006 · Grafo de factores óptico-inercial, activa; la Fase 7c3 · El tamaño de la referencia medido con el tablero, parte sin cámara, pendiente del commit; replan autorizado el 2026-11-11 con las fases 7c a 7h, 7d2 y 7d2b (P45–P74); la Fase 7d2 · Los IDs falsos del tablero, parte sin cámara commiteada (`6cd759e`); la Fase 7d2b · Un ID repetido no se publica, sin cámara, commiteada (`26a23eb`); los perfiles gs1 y gs2 pasan al marker ID 100 de 99.8 mm (encargo corto de la Fase 7c · La referencia con su propio ID), pendiente del commit del autor; recorte de docs y ADR-035; la meta 007 · El tracker en la Jetson Orin Nano, en pausa, y la 005 también)._

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

- `codigo/tests/`: **1519: 1507 pasan, 10 saltadas, 2 fallos esperados (`xfail(strict=True)`: el criterio 9 de la 7d, P67, y el caso `[repo]` de `test_referencia_id.py`, P75), 0 fallan**; 234 y 220 s (2026-11-12, con la 7c3 sin cámara; antes, 224 s con 1486). El `pytest.ini` ya trae `-q`: con otro `-q` no sale la línea final (usar `-o addopts="-p no:cacheprovider"`). Dos corridas del mismo árbol difieren ~25 %: es la carga de la máquina; el margen contra el tope de 600 s baja (B115); B130: dos pruebas de `test_referencia_id.py` pueden fallar sueltas con la CPU cargada. Las 10 saltadas: 9 «solo Linux» y 1 solo en la Jetson. **En la Jetson** (`ssh nav-jetson suite wip`): la última, fase 7b parte A, 993 pasan, 0 fallan; en Linux el replay admite 1e-3 mm/°/px (P22). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`.
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

- **Hecho** (números en `tasks.md`; detalle hasta el 2026-11-11 en `docs/history/`): Fases 1 parte A y 2 (B94 «se movió»); 7a, el asistente de captura; 7c y 7c2 sin cámara (la referencia es `Reference`, ID 100, y la cadena publica `ReferenceToTracker`; **desde el 2026-11-12 los perfiles llevan el ID 100 de 99.8 mm** (las copias congeladas del replay siguen en ID 0 y 80 mm); el ADR G7, propuesto en `fase-7c2-implementa.md`); 7d sin cámara (ChArUco 9×7 de 26 mm, `DICT_4X4_50`; el asistente de una cámara; muestra y tablero en `Claude outputs/fases/006/fase-7d/`); 7d2 parte sin cámara (`6cd759e`, `diagnostics/barrido_correccion.py`: con la tasa 0.60 hay IDs fantasma con el tablero y sin él; la sesión elige 0.30, 0.20 o ninguna); 7d2b sin cámara (`26a23eb`; `MarkerTracker` no publica un ID que sale repetido en un frame y lo cuenta: `[Repetidos]` al salir y `repeated` en el `.npz`; con el 100 doble en 5 de 20 frames, 15 envíos y ninguno en esos 5; sin dobles, mismas matrices que antes; `pose_log` gana 4 claves; `fase-7c/correr.ps1` amplía la sesión conjunta). La Fase 7 (extrínsecos por tablero), parcial: la sesión del 2026-11-11 no cumplió; el diagnóstico (P45) halló las cámaras giradas, el marker de ~100 mm con el perfil en 80 (B55) y gs2 con otros intrínsecos; el montaje de pinzas no es rígido.
- **Replan del 2026-11-11 (P46–P74):** ChArUco para intrínsecos (7d, 7e) y extrínsecos (7f); «recalibrar y continuar» (7g; botón 7h): 20 vistas en ~10 min (P60 c); la fusión no arranca con extrínsecos de otro día o > 12 h (P61); los grados del criterio 1, informativos (P54); B39 con la tasa (7d2) y el filtro de IDs repetidos (7d2b; P70 b, P72 a; P73 b: sin copia de papel).
- **Fase 7c3 · El tamaño de la referencia medido con el tablero, parte sin cámara: hecha, pendiente del commit del autor** (`calibration/medir_referencia.py`, 31 pruebas, y P9 en `fase-7c/correr.ps1`; casilla sin marcar). Mide el borde que ve el detector (P81 a): sale ~0.10 mm por dentro del lado dibujado en el sintético. El tope de radio (382 px) y los 21 s de pruebas, aceptados (P82 a; B136, B135). El cierre (`size_mm` en los perfiles) va tras la sesión conjunta y el cierre de la 7d2; el ADR G7 dirá que el `size_mm` es el del borde que ve el detector.
- **Lo siguiente, en orden:** commit de la 7c3 sin cámara → sesión conjunta 7c2 + 7d2b + 7d2 + 7c3 (P9) con `fase-7c/correr.ps1` (la dirección lo revisa antes de dárselo al autor, y ahora también P9; el tablero ChArUco completo ya está impreso y registrado: falta la prueba de la luz) → cierre de la 7d2 y de la 7c3 → 7e · Recalibrar gs1 y gs2 → 7 parte sin cámara 2 → 7f → 7g → 7 sesión 2 → 7h; después las Fases 3 a 6 y 8. ADR-035 (el PC detecta y fusiona; era el G1) escrito el 2026-11-11.
- Qué es: GTSAM fusiona lo de gs1 y gs2; el IMU después. P1–P74 en `specs/006-*/clarify.md`.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (en pausa desde el 2026-11-05; plan autorizado el 2026-10-29)

- **Fases 1 a 7 hechas y commiteadas** (números en `tasks.md`; detalle en `docs/CONTEXT.md` §6). Los agentes entran solo por `ssh nav-jetson <verbo>` (un 126 es el guardián y no se rodea). Pendientes: B85, B86, B91, el ADR J2.
- **Fase 7b · Las dos cámaras a la vez en Windows: B5 ya cumple** (`244d31e`, `ba3ed36`, `9d0a9fa`). B4 gs1 81.7 fps, **faltan los Hz de Slicer**. B5 cumple con gs2 en el frontal USB 3.0 (`…#USB(5)`), ~89–90 fps cada una (B97; CONTEXT §4.21).
- **Al retomarla:** cerrar la 7b (los Hz de B4, la parte C), Fase 8 · El panel del PC lanza y para el tracker de la Jetson, y Fase 9.

## Pendientes del autor

- **Meta 006:** Tablero completo registrado: casilla 25.95 mm (B − A en 5 filas), plano, 2026-11-12 (`codigo/data/tablero_charuco.yaml`, Fase 7d · El tablero ChArUco y los intrínsecos); falta la prueba de la luz, en la sesión conjunta; el marker ID 100 está impreso y medido (cinco medidas de 99.8 mm, cuadrado) y ya está en los perfiles. Ninguna sesión con la referencia vale hasta cerrar la 7c2; los `correr.ps1` viejos piden `Marker0ToTracker` y no valen. Miniforge, para la Fase 6.
- **Meta 007 (en pausa):** los Hz de Slicer de B4; `enviar_wip.ps1` y `ssh nav-jetson suite wip` con la parte B; la Wi-Fi de la Jetson (B86, con sudo); el cable directo (B85).
- Meta 005 (aplazado hasta compartirlo con los compañeros): las pruebas en vivo de las fases 1 a 4, con sus protocolos en `Claude outputs/fases/005/`.
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Abiertos

- **Regla de procedimiento (autor, 2026-11-11, P66, P71; B39):** el tablero ChArUco, **fuera de la vista antes de arrancar el tracker**, en todo protocolo con la referencia; sigue después de la 7d2 como trampa de `docs/CONTEXT.md` §4. La prueba del criterio 9 (`xfail(strict=True)`, P67) la quita el cierre de la 7d2.
- **Segundo xfail (P75, 2026-11-12):** con los perfiles en ID 100, `test_referencia_id.py::test_con_el_viejo_y_el_nuevo_a_la_vista_se_envia_solo_el_de_la_lista[repo]` falla por B39 (la tasa 0.60 lee el ID 100 sintético de 99.8 mm como 149 en 1 de 6 frames; con 0.40 o menos, 6 de 6): queda en `xfail(strict=True)` y se quita en el cierre de la 7d2, con la tasa elegida en los perfiles.

## Trampas de la sesión

- `.git`: 691 MB en objetos sueltos (0 packs) y un temporal basura: B13.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"`.
- En Slicer, cerrar la escena antes de medir con `receive_reference.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
