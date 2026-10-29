# memory.md — estado de hoy

_Actualizado: 2026-10-28 (meta 005 · Agente de consulta para el equipo y buzón de peticiones: fase 3 · La guía `docs/EQUIPO.md` y la instalación guiada, hecha sin la lectura en vivo y pendiente del commit del autor. El grafo de factores es la meta 006, por decisión del autor del 2026-10-27)._

Spec activo: `specs/005-equipo-consulta/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»; fases en `specs/003-*/tasks.md`, de `b3679ca` a `26e724e`). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker:** cerrada el 2026-10-26 con la fase 4 · Lectura con el autor y cierre de la meta (pendiente del commit del autor): 0 dudas en §9.2 y §9.4 (P12). Fases en `specs/004-*/tasks.md` (de `f3a2d4b` a `354afe4`); números en `specs/004-*/resultados.md`; todo en `docs/ARCHITECTURE.md` §9. Si se edita el Mermaid de §9.1, reexportar con `diagnostics.export_map` (ADR-032); si cambia `explain_pose.format_markdown`, regenerar el bloque con el comando de §9.3.

- **Meta 005 · Agente de consulta para el equipo y buzón de peticiones** (`specs/005-equipo-consulta/`, plan autorizado el 2026-10-28; ADR-034 y principio 1 enmendado): la fase 1 · El buzón `peticiones/` y los hooks está commiteada (`bc328b2`; `probar_hooks.ps1` 24 de 24) y espera la prueba en vivo de 7 casos del autor (protocolo en `Claude outputs/fases/005/fase-1-implementa.md`). La fase 2 · El agente `consulta` y su skill de peticiones está commiteada (`ae1e7ad`; `probar_consulta.ps1` 11 de 11, USD 0.96 y 605 s) y espera su prueba en vivo (2 envíos, con `!` y en terminal aparte; protocolo en `Claude outputs/fases/005/fase-2-en-vivo.md`). La fase 3 · La guía `docs/EQUIPO.md` y la instalación guiada está hecha (10 pasos de instalación; el paso 10 dice aceptar el diálogo de confianza, sin el cual `settings.json` pierde sus `allow`) y pendiente del commit del autor y de su lectura en vivo (protocolo en `Claude outputs/fases/005/fase-3.md`; ese clon sirve para la fase 4). Sigue la fase 4 · El aviso de peticiones en `direccion` y el circuito completo; luego la 5. El BACKLOG de la meta lo escribe la dirección (B60–B65).
- Sin verificar (los `push` están negados también en el scratchpad): que `git push --dry-run origin HEAD:main` (paso 9 de `EQUIPO.md`) abra el navegador de Git Credential Manager con la copia al día; si no lo abre, la entrada a GitHub se hace en el comando 4 del primer envío.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout` y cierra en un `finally`; `--no-detect` es la vista previa, solo por CLI desde la 8a (P17 = a).
- Desde la fase 8a: el panel tiene «Verificar IDs y colocar la cámara» (IDs, cruz y fps de la cámara; `identify_ids` lee por `FrameGrabber`; desde la fase 2b de la meta 004 pone también el semáforo «Cámara» y ya no hay «Probar cámara»), «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana; los perfiles no cambian.

## La suite

- `codigo/tests/`: **618 de 618**, 0 avisos; 32.9 s de pytest y 35.5 s de reloj (2026-10-28, fase 3 de la meta 005, dos corridas; `codigo/` sin cambios); 33.0 y 33.8 s en la fase 2, 37.1 y 31.7 s en la fase 1. Antes, 34.3 s al cerrar la meta 004. Al cerrar la meta 003, 555 de 555. Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
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
- **B55 (media desde el 2026-10-26):** dos Marker0 con el mismo ID (80 y 100 mm); con el de 100, todo sale a escala 0.81 sin aviso.
- Lo siguiente: la meta 005 · Agente de consulta para el equipo y buzón de peticiones (en curso, fase 4 · El aviso de peticiones en `direccion` y el circuito completo); después, la meta 006 · Grafo de factores óptico-inercial (abajo). Instrumento y punta con un transform nuevo (ADR-025) sigue pendiente. B39 acotado (baja). B48, B49, B51–B54, B56, B57 y B59 bajas; B50, B55 y B58 medias.

## Meta 006 · Grafo de factores óptico-inercial (decidida, sin spec; era la 005 hasta el 2026-10-27)

- Propuesta del autor (2026-10-26): un grafo de factores (GTSAM; Ceres no tiene bindings oficiales de Python) que fusione las poses ArUco de gs1/gs2 con un IMU, modular para pasar más adelante a puntos IR por PnP. Primero solo cámaras. Respuestas del autor del 2026-10-26: **el IMU va en el instrumento** (cámaras fijas: es tracking óptico-inercial, no VIO de la cámara); **empieza después de cerrar la meta 004**; fuentes: **GitHub MCP + Context7 + artículos**; sandbox: **scripts con prueba o notebooks, según haga falta**.
- Pendiente para el spec: los números de cierre (convergencia en mm, oclusión de Y s con error < Z mm) y el mecanismo de sincronización (las SVPRO no dan hora de hardware: hoy `perf_counter` tras decodificar). Estas respuestas pasan a `specs/006-*/clarify.md` al crearlo.

## Pendientes del autor

- Meta 005: la prueba en vivo de la fase 1 (7 casos), la de la fase 2 (2 envíos con `consulta`, uno con `!` y otro en terminal aparte, con un fallo «non-fast-forward» entre medias) y la lectura de `docs/EQUIPO.md` de la fase 3 (10 pasos en una carpeta nueva, ~20 min: pasos sin nada que no esté escrito, minutos, MB del clon), con sus protocolos en `Claude outputs/fases/005/`.
- Instalar el GitHub MCP (lo configura el autor) antes de planear la meta 006 · Grafo de factores óptico-inercial.
- La prueba en vivo con la regla de la fase 2c no se hizo: el autor (2026-10-26) la deja; si vuelve a congelarse o ir lento, se retoma (protocolo en `Claude outputs/fases/004/fase-2c.md`).
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
