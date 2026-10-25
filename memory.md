# memory.md — estado de hoy

_Actualizado: 2026-10-25 (meta 003 · Arquitectura y optimización del tracker: fase 7b · Botones de tracker sin ventana y de vista previa para posicionar las cámaras, hecha y verificada en vivo; falta su commit, y después replanear la fase 8 · Cierre de la meta)._

Spec activo: `specs/003-arquitectura-tracker/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker** (plan autorizado el 2026-10-23): el paso 1, la arquitectura (fases 1–5), está en git (`b3679ca`, `c1409ad`, `78ce1af`, `9f500ca`, `34a8d4f`; ADR-026 y ADR-027). Fase 6 · Dónde se va el tiempo por frame: `ec259de`. Fase 7 · Subir los fps con ventana: `33d85c0` (ADR-028). **Fase 7b · Botones de tracker sin ventana y de vista previa para posicionar las cámaras** (autorizada el 2026-10-25, P12 y P13): hecha y en vivo el 2026-10-25, casilla marcada; falta su commit. Después, la fase 8 · Cierre de la meta.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout`, cierra en un `finally` y con `--no-detect` es la vista previa (imagen, cruz y fps de la cámara). El panel: «Vista previa (colocar la cámara)», «Arrancar tracker sin ventana» y «Detener tracker».

## La suite

- `codigo/tests/`: **514 pruebas, 514 pasan, 0 avisos**; 24.4 y 25.3 s de pytest (2026-10-25, fase 7b). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell, sin suponer que los saca de otro sitio (regla del autor, 2026-10-25).

## Meta 003 · Arquitectura y optimización del tracker

- Plan, P1–P16, casillas y números en `specs/003-*/` (`plan.md`, `clarify.md`, `tasks.md`, `resultados.md`). Línea base de la fase 1 (Marker0 quieto a ~37–38 cm): sd z 0.043 mm (gs1) y 0.039 mm (gs2); es la referencia de calidad (sd z ≤ 1.10 ×: ≤ 0.047 y ≤ 0.043 mm).
- **Fase 6 · Dónde se va el tiempo por frame** (`ec259de`): gris + detección + pose ~6.5 ms; ventana ~3.7 ms; el envío pesaba 9.1–12.5 ms (`pyigtl` `wait=True`).
- **Fase 7 · Subir los fps con ventana** (`33d85c0`, ADR-028): en vivo, caja al máximo, cámara a 90, con ventana: gs1 61.7 fps, sd z 0.033 mm, 56.9 Hz en Slicer (cumple); gs2 55.2 fps, sd z 0.034 mm, 50.4 Hz, que el autor acepta (P11). Con la cámara a 90 el límite es el bucle (detección 8–10 ms).
- **Fase 7b · Botones de tracker sin ventana y de vista previa para posicionar las cámaras:** P12 («Detener tracker», por dentro `--stop-stdin`) y P13 = c (`identify_ids --no-detect`, con tope y `finally`). Sin cámara: suite 514/514, replay 0.0 mm / 0.0°. **En vivo (2026-10-25, tabla en `resultados.md`):** sin ventana, bucle 89.9 (gs1) y 88.8 fps (gs2), sd z 0.037 y 0.030 mm, 99.96 % con pose, cierres limpios (exit 0); **Slicer cuenta ~66 Hz (65.8–67.4) frente a ~81 pedidos: no cumple, declarado.** B52 y B53 nuevos, bajas.
- **P14, P15 y P16 (autor, 2026-10-25):** P14 = b, el botón principal del panel lanza el tracker sin ventana y el otro pasa a «Arrancar tracker con ventana» (perfiles sin cambio); P15 = b, la fase 8 mide de dónde sale el techo de ~66 Hz en Slicer; P16 = b, un solo botón «Verificar IDs y colocar la cámara» (se quita «Vista previa»).
- Lo siguiente: el commit de la fase 7b; después, replanear la fase 8 · Cierre de la meta (P14, P15 y P16 entran en ella). B39 acotado (baja). B48, B49, B51 bajas; B50 media.

## Pendientes del autor

- El commit de la fase 7b, «Añade al panel la vista previa y el tracker sin ventana (Fase 7b)»; el `git add` va en `Claude outputs/fases/003/fase-7b.md` (más `docs/DECISIONS.md CLAUDE.md`). Antes, la dirección escribe ADR-029 en `docs/DECISIONS.md` con su índice, y el texto nuevo de `CLAUDE.md` §5 (el comando de `identify_ids` con `--timeout` y el de la vista previa; va en el reporte).
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"` (el `.gitattributes` lo normaliza, pero el árbol queda con CRLF).
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
