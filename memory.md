# memory.md — estado de hoy

_Actualizado: 2026-10-29 (meta 007 · El tracker en la Jetson Orin Nano: fase 1 · El escaneo de la Jetson, solo lectura, hecha y pendiente del commit del autor; la meta 006 · Grafo de factores óptico-inercial queda en espera, y la 005 en pausa)._

Spec activo: `specs/007-jetson/`

Peticiones pendientes: 0

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`) commiteadas; la etapa 3 (hooks) queda para cuando haga falta. `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo:** cerrada el 2026-10-19 (ADR-021; P01 «pasa»).
- **Meta 002 · Calibración de las cámaras global shutter:** cerrada el 2026-10-23 (ADR-023 a ADR-025; P03 «pasa»). Detalle en `specs/002-*/`.
- **Meta 003 · Arquitectura y optimización del tracker:** cerrada el 2026-10-26 (ADR-026 a ADR-031; P04 «pasa»; fases en `specs/003-*/tasks.md`, de `b3679ca` a `26e724e`). Detalle en `specs/003-*/resultados.md`.
- **Meta 004 · Cómo funciona el tracker:** cerrada el 2026-10-26 con la fase 4 · Lectura con el autor y cierre de la meta: 0 dudas en §9.2 y §9.4 (P12). Todo en `docs/ARCHITECTURE.md` §9; si se edita el Mermaid de §9.1 o `explain_pose.format_markdown`, regenerar como dice §9 (ADR-032).

- **Meta 005 · Agente de consulta para el equipo y buzón de peticiones — en pausa** (`specs/005-equipo-consulta/`, plan autorizado el 2026-10-28; ADR-034 y principio 1 enmendado). El autor la pausó el 2026-10-29 para pasar a la meta 006. Hechas y commiteadas las fases 1 · El buzón `peticiones/` y los hooks, 2 · El agente `consulta` y su skill de peticiones, 3 · La guía `docs/EQUIPO.md` y 4 · El aviso de peticiones en `direccion` (`bc328b2` a `7d2ac24`; números en su `tasks.md`). `settings.json` no ganó los `allow` de la fase 4 (se le negaron al agente; el autor no los añadió): `direccion` pide permiso para el `git fetch` y el script al arrancar. Al retomarla: lo en vivo de las fases 1–4 (abajo), los usuarios de GitHub de Kike, Armando y el doctor Milton, invitarlos, el ruleset de `main`, y la fase 5 · Un compañero real instala, pregunta y envía una petición, con el cierre (recortar el arranque, hoy ~55.8 KB sobre 48 KB). Mientras siga en pausa, `direccion` sigue mirando las peticiones al arrancar.
- Sin verificar (`push` negado a los agentes): que `git push --dry-run origin HEAD:main` (paso 9 de `EQUIPO.md`) abra el navegador de Git Credential Manager con la copia al día; si no lo abre, la entrada a GitHub se hace en el comando 4 del primer envío.

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- **Estructura (ADR-027):** paquetes bajo `codigo/`, lanzados con `python -m` desde `codigo\`: `tracker.py` (el bucle, 395 líneas), `vision/`, `transport/` (`IgtlSender`), `camera/`, `calibration/`, `diagnostics/`, `gui/`, `profiles/` (rutas relativas a `codigo/`), `data/`, `slicer/`. Lo archivado, en `codigo/historico/iter4/` (índice en su `README.md`).
- Cámaras: dos SVPRO AR0234 global shutter, `profiles/tracker_config_gs1.yaml` (puerto 1, `focus` 500) y `_gs2.yaml` (puerto 2, 332), 1280×960 MJPG 90 fps (no tienen modo de 60: pedir 60 da ~29), `exposure_ms` 0.977, caja de luz al máximo (con menos luz bajan a 22–31 fps, B50), calibradas (`data/intrinsecos_gs{1,2}_1280x960.yml`). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 390; B36). La Femto está archivada.
- La cadena publica solo `Marker0ToTracker` (ADR-026), puerto 18944. Desde la fase 7 (ADR-028): captura en un hilo con el último frame (`camera/grabber.py`; `--sync-capture` para comparar), envío sin esperar (`wait=False`, 0.02 ms) y el tracker espera a Slicer hasta `--slicer-timeout` (30 s); si no llega, aborta y lo dice (código 3, sin abrir la cámara).
- Desde la fase 7b: `tracker --stop-stdin` (apagada por defecto) sale limpio con `q` o el fin de la entrada estándar; `diagnostics.identify_ids` exige `--timeout` y cierra en un `finally`; `--no-detect` es la vista previa, solo por CLI desde la 8a (P17 = a).
- Desde la fase 8a: el panel tiene «Verificar IDs y colocar la cámara» (IDs, cruz y fps de la cámara; `identify_ids` lee por `FrameGrabber`; desde la fase 2b de la meta 004 pone también el semáforo «Cámara» y ya no hay «Probar cámara»), «Arrancar tracker» (sin ventana, `--no-window --stop-stdin`), «Arrancar tracker con ventana», «Detener tracker» y «Detener proceso». A mano, `python -m tracker --config …` sigue con ventana; los perfiles no cambian.

## La suite

- `codigo/tests/`: **644 de 644**, 0 avisos; 42.5 s de pytest, 46 s de reloj (2026-10-29, cierre de la fase 1 de la meta 007: +3 en `test_escaneo_jetson.py`, que compila un `ssh.exe` falso con `Add-Type`). Antes, 641 en 44.0 s y 34.3 s al cerrar la meta 004. Niega la cámara real y el servidor pyigtl (fixture `no_real_camera`). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`; para ver los totales, `-o addopts="-p no:cacheprovider" -q`.
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

- La meta 006 · Grafo de factores óptico-inercial, sobre la Jetson; la 005 sigue en pausa hasta su fase 5. Instrumento y punta con un transform nuevo (ADR-025) sigue pendiente. Los números de la meta 003 (con ventana 61.7 y 55.2 fps; sin ventana 89.9 y 88.8; Slicer recibe como mucho ~65 Hz, B54) están en `specs/003-*/resultados.md`. B50, B55, B58 y B71 medias; B39, B48, B49, B51–B54, B56, B57 y B59 bajas.

## Meta 006 · Grafo de factores óptico-inercial (en espera tras la meta 007; spec y plan escritos el 2026-10-29, plan sin autorizar; era la 005 hasta el 2026-10-27)

- **En espera (decisión del autor, 2026-10-29):** primero la meta 007 · El tracker en la Jetson Orin Nano; la 006 se construye después sobre la Jetson. Su plan (`specs/006-grafo-factores/plan.md`, P8–P18 contestadas en `clarify.md`, P19 y P20 abiertas) está hecho para Windows: al retomarla se rehace para la Jetson (P8, conda en Windows, cae: GTSAM tiene rueda de pip para Linux aarch64; fps, CPU y la elección entre un proceso y dos trackers se miden allí).

- Qué es: un grafo de factores (GTSAM) que fusiona las poses ArUco de gs1 y gs2; solo cámaras, el IMU (en el instrumento) va a una meta posterior. Las respuestas del autor (P1–P21, con los números de cierre: < 0.5 mm y < 0.2° entre cámaras, −30 % de sd en reposo, 5 s con una cámara tapada) están en `specs/006-*/clarify.md`. La estructura rígida de las dos cámaras la diseña el autor. El GitHub MCP, nunca con `--scope project` (el repo es público). Fuente del autor: `documentos/tecnicos/Factor Graphs for robot perception.pdf` (Dellaert y Kaess), sin seguir en git. Diagrama: `Claude outputs/006/mapa_hoy_y_fusion.svg`.

## Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (activa; plan autorizado el 2026-10-29)

- **Fase 1 · El escaneo de la Jetson, solo lectura: hecha** (2026-10-29, pendiente del commit del autor). `codigo/linux/escanear_jetson.sh`, `escanear.ps1`, `README.md` y `tests/test_escaneo_jetson.py` (25 pruebas); `.gitattributes` gana `*.sh text eol=lf`. El P-1 del autor (`Claude outputs/fases/007/escaneo/antes.txt`, fuera de git: trae IPs y procesos): 12 de 12 secciones en 11 s, 78 órdenes, 0 topes, 7 fallidas explicadas, `find` vacío. `escanear.ps1` fallaba en el resumen final (la variable `topes` era el parámetro `[int]$TopeS`: PowerShell no distingue mayúsculas); corregido y con prueba de punta a punta con un `ssh.exe` falso. No hace falta repetir el escaneo.
- Lo que dijo el escaneo, para las fases siguientes: Ubuntu 22.04.5, L4T 36.4.3 (JetPack 6.2; el metapaquete `nvidia-jetpack` no está), MAXN_SUPER sin root; Python del sistema 3.10.12 (glibc 2.35, `tarfile.data_filter` sí), sin 3.11; hay uv en `~/.local/bin` y `~/miniforge3` (ninguno en el PATH de un shell sin perfil). `v4l2-ctl` 1.22.1 instalado. Cámaras por `by-path`: puerto `usb-0:2.1` con `focus` 500 (gs1) y `usb-0:2.2` con 332 (gs2), las dos en el mismo hub USB 2.0 (480 Mbps); `by-id` choca (misma serie). 1280×960 MJPG a 90 fps (y 60) y los 11 controles del perfil con sus valores; la exposición se lee 10 en unidades de 100 µs (1.0 ms frente a 0.977: la conversión es de la fase 5). 19 GB libres en disco; 18944 libre; `ufw` inactivo (B71).
- Ningún agente se conecta a la Jetson hasta cumplir la fase 2 · La barrera de seguridad para los agentes y que el autor aplique sus reglas de `settings.json` (P8, J4). P19 y P20 contestadas en (a): el autor teclea lo que abre la cámara; su clave lleva frase de paso y su `sudo` pide contraseña.
- Lo siguiente: la dirección abre al autor la pregunta del método de Python 3.11 con los datos del escaneo (uv y miniforge ya están; no hay 3.11 del sistema); `v4l-utils` no hace falta instalarlo (P12). Después, la fase 2 · La barrera de seguridad para los agentes.

## Pendientes del autor

- **Meta 007:** el commit de la fase 1 · El escaneo de la Jetson, solo lectura, y contestar la pregunta del método de Python 3.11 que le abrirá la dirección.

- Meta 005 (aplazado por el autor hasta compartirlo con sus compañeros, 2026-10-28): la prueba en vivo de la fase 1 (7 casos), la de la fase 2 (2 envíos con `consulta`, uno con `!` y otro en terminal aparte, con un fallo «non-fast-forward» entre medias), la lectura de `docs/EQUIPO.md` de la fase 3 (10 pasos en una carpeta nueva, ~20 min: pasos sin nada que no esté escrito, minutos, MB del clon) y el circuito de la fase 4 (una petición de prueba a `origin` en GitHub, vista en `direccion` y cerrada como «rechazada: prueba», ~10 min), con sus protocolos en `Claude outputs/fases/005/`.
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
