# memory.md — estado de hoy

_Actualizado: 2026-10-26 (meta 004 · Cómo funciona el tracker, fase 1 · El mapa del proyecto: hecha, a falta del commit)._

Spec activo: `specs/004-como-funciona/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»; fases en `specs/003-*/tasks.md`, de `b3679ca` a `26e724e`). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker** (plan autorizado el 2026-10-26; P1–P7 contestadas, P8 pendiente): la fase 1 · El mapa del proyecto está **parcial**: `docs/ARCHITECTURE.md` tiene índice nuevo y §9 (§9.1 el mapa en Mermaid, 20 cajas, con su tabla; §9.2–§9.5 vacías), `codigo/diagnostics/export_map.py` y `codigo/tests/test_como_funciona.py`. El primer PNG no se leía (P9, 2026-10-26): la imagen pasó a **SVG** (`docs/img/004/mapa_proyecto.svg`), el mapa a `flowchart LR` (grupos de izquierda a derecha, cada uno de arriba abajo; las flechas entre grupos van de grupo a grupo) y §9.1 nombra lo que queda fuera. El primer SVG pesó 237 917 bytes (la fuente Recursive incrustada, ~167 KB) y pasa del tope de 200 KB. `export_map` pasa ahora a `mmdc` una configuración con `-c` (arial, `htmlLabels: false`), quita el `@font-face` incrustado y sale con 5 si el SVG pasa de 200 KB. Falta reexportar con `--overwrite` (el permiso niega `npx` al agente): el comando está en `Claude outputs/fases/004/fase-1.md`, sección «Peso del SVG». Hasta entonces falla 1 prueba, la del peso.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout` y cierra en un `finally`; `--no-detect` es la vista previa, solo por CLI desde la 8a (P17 = a).
- Desde la fase 8a: el panel tiene «Verificar IDs y colocar la cámara» (IDs, cruz y fps de la cámara; `identify_ids` lee por `FrameGrabber`), «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana; los perfiles no cambian.

## La suite

- `codigo/tests/`: **572 de 572** tras reexportar el SVG del mapa (99 584 bytes), 0 avisos; ~33.5 s de pytest (2026-10-26, meta 004 fase 1). Antes, 555 de 555 (meta 003, fase 8c: 41.1 y 56.1 s). Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay de Marker0 (`tests/test_replay_marker0.py`, gs1 y gs2, 0.0 mm / 0.0°, detección 0.0 px) + `python -m gui.panel --selftest` (con `PYTHONIOENCODING=utf-8`, B49). Detalle en `docs/ARCHITECTURE.md` §6.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen sobre gs1/gs2.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va con su nombre junto al número; cada fase se presenta al autor antes de lanzarla.
- En vivo, cada corrida se le da al autor con los dos comandos juntos, el de Slicer (`exec(...)` y `run(...)`, una línea por vez) y el de PowerShell, sin suponer que los saca de otro sitio (regla del autor, 2026-10-25).

## Meta 003 · Arquitectura y optimización del tracker (cerrada)

- Con ventana: gs1 61.7 fps, gs2 55.2 (aceptado, P11); sin ventana: 89.9 y 88.8 fps, sd z 0.037 y 0.030 mm. Slicer recibe como mucho ~65 Hz: el techo es de Slicer (R2, B54). «Se mueve»: 49.6 mm reales por 50 de regla.
- **B55 (alta):** dos Marker0 con el mismo ID (80 y 100 mm); con el de 100, todo sale a escala 0.81 sin aviso.
- Lo siguiente: terminar la meta 004 · Cómo funciona el tracker (fase 1 hecha; sigue la fase 2 · El ejemplo resuelto con un frame real, pesada). Después, instrumento y punta con un transform nuevo (ADR-025). B39 acotado (baja). B48, B49, B51–B54, B56 y B57 bajas; B50 y B55 medias.

## Pendientes del autor

- El commit de la fase 1 · El mapa del proyecto (meta 004). Si se edita el Mermaid de §9.1, reexportar con el comando de `Claude outputs/fases/004/fase-1.md`, «Peso del SVG» (ADR-032).
- B55: decidido el 2026-10-26, se usa el Marker0 de 80 mm y el de 100 se guarda (media).
- **Usar el Marker0 de 80 mm** (el de los perfiles) mientras B55 siga abierto, y decidir qué se hace con el de 100.
- Decidir si B19 y B20 (alta) se cierran: su código y su punta se archivaron. Decidir si B35 entra en la meta.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`.

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
- En los heredocs de Bash, `\\` llega como `\` y los caracteres no ASCII se rompen: para editar con un script, escribirlo con la herramienta de escritura.
- `Path.write_text` en Windows escribe CRLF: para reescribir un `.py` con un script, `write_bytes` o `newline="\n"` (el `.gitattributes` lo normaliza, pero el árbol queda con CRLF).
- En Slicer, cerrar la escena antes de medir con `receive_marker0.py`: con «conector existente» la ventana empieza antes que el tracker (fase 6, gs2).
