# memory.md — estado de hoy

_Actualizado: 2026-10-25 (meta 003 · Arquitectura y optimización del tracker: fase 7 · Subir los fps con ventana, cerrada con lo medido (P11) y perfiles de vuelta a 90 fps; falta el commit del autor)._

Spec activo: `specs/003-arquitectura-tracker/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker** (plan autorizado el 2026-10-23): el paso 1, la arquitectura (fases 1–5), está en git (`b3679ca`, `c1409ad`, `78ce1af`, `9f500ca`, `34a8d4f`; ADR-026 y ADR-027). Fase 6 · Dónde se va el tiempo por frame: `ec259de`. Fase 7 · Subir los fps con ventana: hecha el 2026-10-25 (casilla marcada; falta el commit del autor). Después, la fase 7b (botones del panel, P10; la autoriza el autor en el chat) y la fase 8 · Cierre de la meta.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 282 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).

## La suite

- `codigo/tests/`: **491 pruebas, 491 pasan, 0 avisos**; 25.9 y 24.6 s de pytest (2026-10-25, cierre de la fase 7). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
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
- **Fase 6 · Dónde se va el tiempo por frame:** hecha (`ec259de`). `tracker --timing <json>` y `diagnostics/measure_window.py`. En vivo: gris + detección + pose ~6.5 ms; ventana ~3.7 ms; **envío 9.1–12.5 ms** (`pyigtl` `wait=True` espera el tic de 15.6 ms de Windows); captura ~8 ms y **32 ms en el modo lento** (gs1 con ventana, 19.5 fps).
- **Fase 7 · Subir los fps con ventana (ADR-028 propuesto; lo escribe la dirección):** el autor eligió E1 (envío sin esperar, con guarda de conexión y `--slicer-timeout` 30 s, salida 3 sin abrir la cámara), C1 (`camera/grabber.py`: hilo de captura con el último frame; `--sync-capture` para comparar) y `t_now` por `perf_counter`. Sin cámara: banco con el servidor pyigtl real y cámara simulada a 90 fps: 88.6 fps con ventana, 90.1 sin ella, el cliente recibe todo; `send_message` 0.03 ms con `wait=False` (4.5 ms con `wait=True`); replay 0.0 mm / 0.0°. **En vivo (2026-10-25, `Claude outputs/fases/003/fase-7-en-vivo.md`, partes 1 y 2; tabla en `resultados.md`):** caja al máximo, cámara a 90, con ventana: gs1 61.7 fps, sd z 0.033 mm, 56.9 Hz en Slicer (cumple); gs2 55.2 fps (cámara 88.8), sd z 0.034 mm, 50.4 Hz: no llega a 60 y el autor lo acepta (`clarify.md` P11). Envío 0.02 ms. Sin Slicer aborta y lo dice. Con la cámara a 90 el límite es el bucle (la detección sube a 8–10 ms). Pedir 60 fps dio 29 (la cámara no tiene ese modo): los perfiles siguen a 90. B32 cerrado; lo que falta (sin ventana) va a la fase 7b.
- Lo siguiente: la fase 7b · Botones de tracker sin ventana y de vista previa para posicionar las cámaras (P10; el autor la autoriza al presentarla), y después la fase 8 · Cierre de la meta. B39 acotado (baja). B48 (cola de `pyigtl` al reconectar) y B49 (selftest del panel se cuelga con salida no UTF-8) nuevos, bajas. B50 (las SVPRO bajan los fps con poca luz, media) y B51 (5.8 Hz en Slicer con `--sync-capture`, baja), de la parte 1.

## Pendientes del autor

- El commit de la fase 7, «Sube los fps del tracker con ventana (Fase 7)»; el `git add` va en `Claude outputs/fases/003/fase-7.md` (incluye `tasks.md`, `clarify.md` con P9–P11 y `resultados.md`). Antes, la dirección escribe ADR-028 en `docs/DECISIONS.md` con su índice (texto en `Claude outputs/fases/003/fase-7-implementa.md`).
- Texto de `CLAUDE.md` §4 «Hardware» (dice «`pyigtl` bloquea»): lo cambia la dirección; el nuevo: «Slicer se conecta antes; el tracker lo espera hasta `--slicer-timeout` (30 s) y, si no llega, aborta con código 3».
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
