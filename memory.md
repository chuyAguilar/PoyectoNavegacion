# memory.md — estado de hoy

_Actualizado: 2026-10-24 (meta 003 · Arquitectura y optimización del tracker: fase 4 · El tracker en piezas hecha, sin cámara y en vivo; falta su commit)._

Spec activo: `specs/003-arquitectura-tracker/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`: agentes `direccion`, `planificacion`, `desarrollo`, `pruebas`; skills `planear`, `fase`, `cerrar-fase`; `docs/PRUEBAS.md`) commiteadas. La etapa 3 (hooks) queda para cuando haga falta; hasta entonces cada papel lo limitan sus `tools` y su texto, y `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo** (B01–B06): cerrada el 2026-10-19 (`2ce4b5d`, `8f33b3a`, `30437e4`, `e52f58c`; ADR-021); P01 «pasa». Detalle en `specs/001-*/` y `docs/PRUEBAS.md`.
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (fases 1–6; P03 «pasa», 3 hallazgos menores arreglados en el cierre; ADR-023, ADR-024, ADR-025). Detalle abajo, en `specs/002-*/` y `docs/PRUEBAS.md`.
- **Meta 003 · Arquitectura y optimización del tracker** (plan autorizado el 2026-10-23; spec activo): fases 1 (`b3679ca`), 2 (`c1409ad`) y 3 (`78ce1af`, ADR-027 en `ad25bf2`) hechas; fase 4 · El tracker en piezas hecha (sin cámara y en vivo, 2026-10-24), pendiente de su commit. Siguiente: la fase 5 · Documentación del paso 1.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (desde la fase 3 de la meta 003, ADR-027):** el código vive en paquetes bajo `codigo/` y se lanza con `python -m` desde `codigo\`: `tracker.py` (solo el bucle, 212 líneas), `vision/` (detección, pose, 1-Euro, `MarkerTracker`) y `transport/` (`IgtlSender`) desde la fase 4, `camera/` (backend, uvc, controls), `calibration/` (calibrate_camera, check_scale), `diagnostics/` (probe_camera, measure_modes, identify_ids, pose_log), `gui/` (`python -m gui.panel`), `profiles/` (perfiles y `profiles.load`: rutas relativas a `codigo/`), `data/`, `slicer/`. El dodecaedro, la Femto y los perfiles viejos, en `codigo/historico/iter4/` (índice en su `README.md`). `codigo/iter4/` ya no tiene nada versionado.
- Cámaras: dos SVPRO AR0234 global shutter, perfiles `profiles/tracker_config_gs1.yaml` (puerto 1, marca `focus` 500) y `_gs2.yaml` (puerto 2, marca 332), 1280×960 MJPG 90 fps, `exposure_ms` 0.977, **las dos calibradas** (detector `sb`): `data/intrinsecos_gs1_1280x960.yml` y `data/intrinsecos_gs2_1280x960.yml`. **No girar ni sacar el lente de la cámara 2 sin recalibrar:** su punto principal queda 90 px sobre el centro (cy 390; B36). La Femto Bolt está archivada: `camera_type: femtobolt` aborta.
- La cadena publica solo `Marker0ToTracker` (ADR-026). La geometría del dodecaedro y la punta (`StylusTipToDodecaedro_femto_dock`) están archivadas en `codigo/historico/iter4/dodecahedron/data/`.
- Métricas de referencia: RMS de registro 2.80 mm (iter 3), 3.46 mm (iter 1). P02 (cámara 1 a 640×480): 25.7 fps con ventana, sd z 1.38 mm a ~45 cm.

## La suite

- `codigo/tests/`: en verde. Desde la fase 4 de la meta 003: **463 pruebas, 463 pasan, 0 `xfail`, 0 avisos**; 18.4 y 18.3 s de pytest, ~21 s de pared (dos corridas). La suite niega la cámara real y el servidor pyigtl (fixture `no_real_camera`, B34). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; `pytest.ini` pone `pythonpath = .` y `-q` (para ver la línea de totales, `-o addopts="-p no:cacheprovider" -q`).
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm/0.0°, detección 0.0 px; datos en `tests/data/marker0_*`, 2.17 MB) + `python -m gui.panel --selftest` (`tests/test_gui_headless.py`). El replay del dodecaedro se archivó con su código. Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (2026-10-20; ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen mejorados sobre gs1/gs2.
- **Optimizar el tracker** es la meta 003 (B32: la ventana es el cuello).
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va siempre con su nombre descriptivo junto al número; cada fase se presenta al autor antes de lanzarla.

## Meta 003 · Arquitectura y optimización del tracker

- Plan autorizado el 2026-10-23 (P1–P8 en `clarify.md`); ocho fases en `tasks.md`; números en `resultados.md`.
- **Fase 1 · Línea base de Marker0 en vivo, antes de mover nada:** hecha (`b3679ca`). Marker0 de 80 mm quieto a ~37–38 cm, las dos cámaras: 100 % de frames con pose, sd z 0.043 mm (gs1) y 0.039 mm (gs2), orientación 0.10–0.13°, 0 saltos > 5°. Replay 0.0 mm / 0.0° (977 y 973 envíos); detección 0.0 px. El tracker acepta `--record`, `--no-window`, `--save-frames`, `--frames-every`, `--duration` (apagadas).
- **Fase 2 · La cadena solo con Marker0:** hecha (`c1409ad`). Perfiles sin `rigid_bodies`; en vivo con Slicer 19.1 Hz (gs1) y 31.4 Hz (gs2), `DodecaedroToTracker` ausente, salida limpia. `codigo/slicer/receive_marker0.py` mide la cadena desde Slicer; el manual del dodecaedro está en `documentos/historico/`.
- **Fase 3 · La estructura nueva y el archivo:** hecha (sin cámara 2026-10-23; en vivo 2026-10-24; `78ce1af`). Lo de «Estructura» arriba; el tracker solo cambia imports y carga del perfil; replay 0.0. El panel ya no tiene asistente, dock ni semáforos de geometría y punta; un perfil con `rigid_bodies` o de la Femto queda en ROJO. Las recetas lanzan `python -u -m <modulo>`. B17, B37 y B38 cerrados; B40–B47 nuevos. En vivo con gs1 por el panel: Probar cámara, Verificar IDs y Arrancar tracker con exit=0, `[Whitelist] [0]`, Marker0 llega a Slicer, selftest con los 3 argv `-m`; fps 16–22 (dato para la fase 6, B32).
- **Fase 4 · El tracker en piezas:** hecha (sin cámara y en vivo, 2026-10-24), pendiente del commit. `tracker.py` 754 → 212 líneas; replay de Marker0 por `MarkerTracker.process_corners` 0.0 mm / 0.0° (977 y 973 envíos), detección 0.0 px. B22, B27, B28 y B34 cerrados. `measure_modes --modos` vuelve a correr con gs1/gs2; `--config` del tracker es obligatorio; `send_video: true` aborta. `IgtlSender.close()` cierra el servidor de verdad (antes `server_tx.close()` fallaba en silencio). En vivo, con gs1 y gs2 a mano y desde el panel: B28 cumple (a mano sin la variable, la cámara abre en 0.4 s, antes 40–50 s); Hz en Slicer 22.1 (gs1) y 30.9 (gs2) a mano, 28.6 y 22.8 por el panel (la ventana de 10 s cubrió arranque y cierre); «Servidor del puerto 18944 cerrado» y `[Salida limpia]` siempre, también en un fallo de arranque (cámaras en «Unknown» de Windows, reconectadas).
- **fps bimodales, ~20–21 o ~32–35, sin relación con la ventana** (causa sin aislar): dato para la fase 6 · Dónde se va el tiempo por frame (B32). B39 acotado: falta Marker0 inclinado 15–20° en vivo (baja).

## Meta 002 · Calibración de las cámaras global shutter (cerrada)

- Plan, respuestas (P1–P21), casillas y números en `specs/002-calibracion-camaras/`. Lo que dejó y sigue vigente: identidad por la ruta del puerto USB (las dos cuelgan de un hub: si cambia el hub, cambian las rutas); controles por DSHOW antes de abrir por MSMF; la marca `focus` solo es fiable escrita (`CONTEXT.md` §4.19); el código apaga la aceleración HW de MSMF (§4.18); captura ~90 fps en todos los modos y tracking con ventana 19–25 fps (B32); calibración del panel en tres pasos (enfocar, tablero de 24.86 mm, escala por medias); gs1 RMS 0.167 / control 0.146 px, gs2 0.154 / 0.150 px; escala +0.27 y −0.37 mm en 80 mm.

## Pendientes del autor

- El commit de la fase 4 (`Claude outputs/fases/003/fase-4.md` trae el título y el `git add`).
- Pasar a `CLAUDE.md` §1 y §5 y a `.claude/` los comandos nuevos con `python -m` (fase 5).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/` (el autor usa también Git Bash).

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
