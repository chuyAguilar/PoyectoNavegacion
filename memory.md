# memory.md — estado de hoy

_Actualizado: 2026-10-24 (meta 003 · Arquitectura y optimización del tracker: fase 6 · Dónde se va el tiempo por frame, hecha; falta el commit del autor)._

Spec activo: `specs/003-arquitectura-tracker/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker** (plan autorizado el 2026-10-23): el paso 1, la arquitectura (fases 1–5), está en git (`b3679ca`, `c1409ad`, `78ce1af`, `9f500ca`, `34a8d4f`; ADR-026 y ADR-027). Fase 6 · Dónde se va el tiempo por frame: hecha el 2026-10-24, sin commit. Lo siguiente: el autor elige las opciones de la fase 7 · Subir los fps con ventana (se anotan en `clarify.md`).

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 282 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps, `exposure_ms` 0.977, calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944.

## La suite

- `codigo/tests/`: **475 pruebas, 475 pasan, 0 avisos**; 18.9 y 18.5 s de pytest (2026-10-24). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest`. Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.

## Meta 003 · Arquitectura y optimización del tracker

- Plan, P1–P8, casillas y números en `specs/003-*/` (`plan.md`, `clarify.md`, `tasks.md`, `resultados.md`). Línea base de la fase 1 (Marker0 quieto a ~37–38 cm): sd z 0.043 mm (gs1) y 0.039 mm (gs2); es la referencia de calidad de la fase 7 (sd z ≤ 1.10 ×).
- **Fase 6 · Dónde se va el tiempo por frame:** hecha (2026-10-24). `tracker --timing <json>` (`diagnostics.pose_log.Stopwatch`, apagado por defecto) y `diagnostics/measure_window.py`. En vivo, gs1 y gs2, con y sin ventana: suma de etapas / frame 0.984–0.989. Gris + detección + pose ~6.5 ms; ventana ~3.7 ms; **envío 9.1–12.5 ms**; captura ~8 ms y **32 ms en el modo lento** (gs1 con ventana, 19.5 fps).
- **Por qué tarda el envío:** `pyigtl` 0.3.1 `send_message(wait=True)` espera a que su hilo vacíe la cola, y ese hilo hace antes un `recv` con tope de 10 ms que en Windows dura el tic (15.5 ms medidos). Engancha el bucle al tic: cada frame dura ~1, 2, 3 o 4 tics de 15.625 ms.
- **Propuesta para la fase 7** (`Claude outputs/fases/003/fase-6.md`): envío sin esperar (`wait=False`) o envío propio; hilo de captura con el último frame; antes, medir el modo lento de gs1 con la captura sola. Si el bucle pasa de 64 fps, `t_now` tiene que dejar `time.time()` (resolución 15.6 ms en este venv), que cambia la entrada del 1-Euro.
- fps bimodales (~20 o ~32–37): el modo lento es la captura, no la ventana (B32). B39 acotado (baja).

## Pendientes del autor

- El commit de la fase 6: «Mide el tiempo por frame del tracker (Fase 6)»; el `git add` está en `Claude outputs/fases/003/fase-6.md`.
- Elegir las opciones de la fase 7 a la vista de la propuesta (y si el objetivo sigue en 60 fps con ventana).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
