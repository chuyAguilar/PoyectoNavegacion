# CLAUDE.md — instrucciones para Claude Code en PoyectoNavegacion

Instrucción de herramienta: cómo se trabaja en este repo. No es documentación del proyecto ni repite sus principios.
Los principios están en `docs/constitution.md`, que manda sobre este archivo; aquí se remite a ellos por su número.
El conocimiento técnico detallado está en las skills `surgical-navigation-aruco`, `slicer-igt-workflow` y `surgical-nav-project-context`.

## 1. Al arrancar

En este orden:

1. Lee completos `docs/constitution.md`, `memory.md` y `docs/CONTEXT.md`.
   **La dirección,** justo después de `memory.md` y antes de cualquier otra cosa, corre `powershell -NoProfile -ExecutionPolicy Bypass -File equipo/peticiones_pendientes.ps1 -Ref origin/main` y le presenta al autor las peticiones del equipo con `Decisión: pendiente` y, si hay commits nuevos en `origin/main`, el recordatorio de `git pull --rebase origin main` (ADR-034; el detalle, en `.claude/agents/direccion.md`). Los subagentes no lo corren.
2. Lee completos, del spec activo, `spec.md` y `tasks.md`, los que existan. El spec activo es el que nombra `memory.md`, siempre con las mismas palabras: «Spec activo: `specs/NNN-nombre/`» (o «Spec activo: ningún spec activo»).
3. Consulta `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/BACKLOG.md` y `docs/PRUEBAS.md` por sección: primero su índice, después solo la sección que haga falta.
4. `docs/history/` solo cuando haga falta saber cómo se llegó a algo. Es copia literal y no se edita.

Antes de escribir código, lee el que ya existe en `codigo/` (paquetes y `tracker.py`; `historico/` es archivo). No reinventes lo que hay.
Si al retomar el estado es ambiguo, una sola pregunta al autor y se sigue.

## 2. El flujo de una meta

Quién hace cada cosa está en el principio 1. Los pasos:

1. **El spec.** `specs/NNN-nombre/spec.md` trae el qué, el porqué y el criterio de cierre medible (principio 3). La plantilla está en `specs/_plantilla/`.
2. **El plan.** `plan.md`: los archivos que se crean o modifican, las funciones con su firma, las fases con su criterio, lo que irá al BACKLOG, los ADR propuestos y las preguntas abiertas. Sin código.
3. **Las respuestas.** Van en `clarify.md`: la pregunta, las opciones, la respuesta del autor y la fecha.
4. **La autorización.** Cuando el autor autoriza el plan, la primera línea de `tasks.md` dice «Plan autorizado por el autor el AAAA-MM-DD». Sin esa línea no se implementa nada (principio 2).
5. **Las fases.** Una casilla por fase en `tasks.md`. Se implementa solo esa fase, se mide su criterio y se marca la casilla con el número obtenido y la fecha.
6. **El commit.** Uno por fase, y lo hace el autor con el título y el `git add` que se le proponen. La fase siguiente empieza después de su commit.

Una decisión que no es trivial se propone como ADR en `plan.md`. Una dependencia nueva se propone en el plan con su porqué: solo vale lo que declara `codigo/requirements.txt`.

## 3. Cerrar una fase

En el mismo cambio que la fase, antes de que el autor haga el commit:

- **`memory.md`:** la meta y la fase, lo siguiente, lo abierto y los pendientes del autor. Como máximo 12 KB.
- **`docs/BACKLOG.md`:** la entrada se escribe cuando se decide no hacerlo ahora. Dice qué es, por qué queda, de dónde viene, qué haría falta y su prioridad (alta: puede dar un resultado equivocado o impide usar el sistema; media: mejora clara sin riesgo; baja: espera datos o solo si estorba). Lo cerrado pasa a «Cerrados» con la fecha y qué lo cerró.
- **Los índices:** quien añade, cierra o cambia una entrada de `docs/DECISIONS.md` o `docs/BACKLOG.md` actualiza su índice en el mismo cambio.
- **`docs/ARCHITECTURE.md`,** si cambió la estructura o un contrato, en presente y con su fecha. **`docs/CONTEXT.md` §6,** si cambió el estado hecho/pausa/WIP.
- **Las líneas:** ninguna línea de `docs/` (fuera de `history/`), de `memory.md` ni de `specs/` pasa de 2 000 caracteres.

## 4. Reglas de operación

- **Los roles.** Cinco archivos en `.claude/agents/`: `direccion` (la sesión principal; el autor la abre con `claude --agent direccion`); `planificacion`, `desarrollo` y `pruebas`, subagentes que solo lanza la dirección, uno a la vez y con su propio contexto; y `consulta`, el de los compañeros del equipo, que cada uno abre en su clon con `claude --agent consulta`: responde con la fuente, no cambia nada fuera de `peticiones/` y no ejecuta ningún comando de envío (ADR-034). Las rutinas son cuatro skills en `.claude/skills/`: `planear` (la usa `planificacion`), `fase` y `cerrar-fase` (las usa `desarrollo`) y `peticion` (la usa `consulta`); la dirección no tiene `Skill` y se las encarga.
  Los subagentes no preguntan: si algo los para, devuelven una sola línea, «Parado: por qué». `pruebas` no escribe código y solo escribe `docs/PRUEBAS.md` (al final) y `Claude outputs/pruebas/`; lo que necesita hardware lo deja como protocolo para el autor.
- **Git.** Ningún agente ejecuta `git commit` ni `git push` (principio 1): `.claude/settings.json` lo niega. Git de lectura, `git mv` y `git rm --cached` sí, y **siempre desde PowerShell**, nunca desde un sandbox Linux (principio 9). No se reescribe el historial.
  Los compañeros del equipo hacen commit y push solo de archivos nuevos en `peticiones/`, ejecutando ellos los cinco comandos de `peticiones/README.md` («Cómo se envía»); en sus máquinas los filtran los hooks versionados de `equipo/hooks/` (`git config core.hooksPath equipo/hooks`; en la del autor no están activos). Una petición enviada no se edita (ADR-034).
- **Datos de paciente (principio 5).** No se leen ni se editan `herramientas/A/`, `*.nrrd`, `*.dcm` ni `documentos/VERONICA/`; `settings.json` lo niega. Una negación no se rodea: se dice en el reporte.
- **La cadena (principio 6).** Una fase que toque `tracker.py`, `camera/`, `vision/`, `transport/` o los scripts de Slicer dice en su plan cómo verifica que la cadena sigue igual.
- **Verificación.** Antes de dar una fase por terminada: la suite en verde, con su tiempo, y la comprobación de «no cambió» que fije el spec (suite + replay sobre un dataset grabado, cuando exista). Lo que necesita cámara o Slicer se verifica en vivo con el autor y se reporta el número.
- **Tras editar** un `.py`: `py_compile` y conteo de líneas (Edit/Write han truncado archivos antes).
- **Lo que corre el autor en vivo va en un solo `.ps1`** (regla del autor, 2026-11-05). Junto al `.md` del protocolo (qué mide y qué se espera), un script `correr.ps1` en la misma carpeta de `Claude outputs/` (fuera de git) hace todos los pasos en orden, y el autor lanza solo ese. Las reglas del script:
  - **Simula primero.** Con `-Simular` imprime cada comando sin ejecutar nada. Sin él, muestra el plan y espera «s» antes de empezar. Un paso que necesita una mano (Slicer, mover una cámara) para con el texto exacto de lo que hay que hacer y espera Enter.
  - **Solo lo del proyecto.** Ejecuta solo `codigo\.venv\Scripts\python.exe -m <módulo del repo>`, los `.ps1` del repo o de `Claude outputs/` y `ssh nav-jetson <verbo>`. Nunca: administrador (`-Verb RunAs`, `sudo`), instalar (`pip`, `uv`, `winget`), registro, servicios, firewall, red, energía o drivers, `Set-ExecutionPolicy` (solo `-ExecutionPolicy Bypass` por llamada), descargas (`Invoke-WebRequest`, `curl`), `Invoke-Expression`, ni `git` que escriba.
  - **Solo escribe en su carpeta de salida** y no borra nada (`Remove-Item`, `Move-Item`): una corrida nueva escribe con otro nombre. Lo único que cambia en el equipo es lo que el protocolo nombra (p. ej. un control de la cámara), y lo devuelve a su valor al terminar o si falla. No nombra datos de paciente (principio 5).
  - **Comprueba antes y después.** Antes: la raíz, el venv, y que los puertos y las cámaras están libres; si no, no empieza. Después: que todo lo que lanzó terminó y todo quedó libre.
  - **Topes (principio 9).** Cada proceso tiene su tope. Si se pasa, falla un paso crítico o el autor pulsa Ctrl+C (`try/finally`), para solo los procesos que él lanzó, por su PID y nunca por nombre, se detiene en ese paso y dice qué falló.
  - **Deja constancia.** Un registro con la hora, el comando y el código de cada paso, y al final la tabla esperado / obtenido. Lo que solo ve el autor (los Hz de Slicer) lo pide por teclado y lo escribe en la tabla.
  - **La dirección lo revisa antes de dárselo**, contra esta lista y buscando en el texto lo prohibido, y le dice al autor que lo revisó y con qué resultado.
- **Hardware.** Slicer (OpenIGTLink IF activo) se conecta ANTES de arrancar el tracker: si no llega en `--slicer-timeout` (30 s), el tracker aborta sin abrir la cámara (ADR-028). Webcam con backend MSMF + MJPG. El resto de trampas, en `docs/CONTEXT.md` §4.
- **Idioma.** Español para las personas (docs, reportes, mensajes); inglés para los identificadores. Directo y honesto, incluida la incertidumbre.
- **Alcance.** Lo que convendría hacer y no se pidió va al BACKLOG o a las sugerencias del reporte, no al código.
- **Sin memoria privada.** Lo que haya que recordar va a `memory.md` o a `docs/`, nunca a la memoria privada de Claude Code (`autoMemoryEnabled: false`).

## 5. Entorno

- Windows 11 (máquina BigDaddy, RTX 3060). Shell: PowerShell para git; Git Bash disponible.
- Raíz: `C:\Dev\OrtoMeta\PoyectoNavegacion`. Código activo: `codigo\`, en paquetes por responsabilidad, lanzado con `python -m` desde `codigo\` (ADR-027). Python 3.11.9 en `codigo\.venv`; dependencias en `codigo\requirements.txt`.
- Las pruebas: `codigo\.venv\Scripts\python.exe -m pytest codigo\tests -q`; cuántas son, cuánto tardan y su estado, en `memory.md`.
- 3D Slicer 5.x + SlicerIGT corre aparte: no se controla directo; se le pasan scripts para su consola Python.

Comandos de operación (desde `codigo\`, con el venv). Los argumentos van explícitos (principio 7):

```powershell
python -m gui.panel                                              # panel: compone y lanza lo demás
python -m tracker --config profiles\tracker_config_gs1.yaml      # Slicer conectado ANTES
python -m tracker --config profiles\tracker_config_gs1.yaml --no-window --stop-stdin   # sin ventana; q + Enter para salir
python -m diagnostics.identify_ids --config profiles\tracker_config_gs1.yaml --timeout 600
```

## 6. Cómo reportar

Al final de cada fase, el reporte completo va a `Claude outputs/fases/<NNN>/<fase>.md`, fuera de git. Corto y sin adjetivos:

- qué archivos cambiaron;
- qué criterio se verificó y con qué número;
- la suite con su tiempo, y que lo que no debía cambiar no cambió;
- qué quedó pendiente o dudoso, y qué se anotó en el BACKLOG;
- las sugerencias fuera de alcance;
- el título del commit (en español, en imperativo, corto y sin coautor) y el `git add` exacto, con la forma `git -C C:\Dev\OrtoMeta\PoyectoNavegacion add …`.

Lo que `desarrollo` devuelve a la dirección, y lo único que esta ve, es un resumen de seis líneas como mucho: «Fase N: hecha» (o «parcial: qué falta»); el criterio clave con su número; la suite (cuántas, cuánto) y el «no cambió»; lo que fue al BACKLOG, si hay; el título del commit y el `git add`; «Reporte: `Claude outputs/fases/<NNN>/<fase>.md`». La dirección lee el reporte en el disco y se lo resume al autor.


## Epistemic Calibration & Intellectual Honesty

### 1. Truth Stance & Confidence Grading
Do not project false authority or deliver unverified assumptions as facts. When stating technical claims, proposals, or architecture decisions, adhere to explicit epistemic markers:
- `[Verified]`: Confirmed against the local codebase, executed command output, or direct tool inspection.
- `[Hypothesis / High Prob]`: Plausible industry pattern or statistical default, but unconfirmed in this specific environment.
- `[Speculative / Assumption]`: Guessing due to missing context or incomplete parameters. State explicitly what data is missing to verify it.

### 2. Radical Self-Correction & Adversarial Check
- Before presenting a solution or code implementation, run an internal sanity check:
  - What are the unstated assumptions here?
  - What would break this in a real edge-case?
  - Is this factually accurate or just syntactically convincing?
- If your confidence in a proposed solution or answer is below ~90%, do not guess or bluff. Explicitly state the uncertainty, declare what you don't know, and ask the user for confirmation or verify with tools before proceeding.

### 3. Verification Protocol Over Assertion
- Never state "this will work" without showing the rationale, test condition, or limitation.
- Distinguish between **fact** (observable in the workspace/code), **convention** (standard best practice), and **model prior** (pattern training memory that might be hallucinated or outdated).
- When correcting a mistake, do not offer servile apologies. State what was wrong, the source of the misjudgment, and provide the calibrated correction immediately.

### 4. Communication Dynamic
- Speak as a critical technical collaborator, not a sycophantic chatbot.
- If the user's premise has a flaw, counter it constructively with reasons rather than nodding along.
- Answer technical queries directly, stripping corporate filler, decorative greetings, and redundant introductory summaries.

## Relationship Dynamic: Transparent Thinker

- **Role**: Co-desarrollador que verbaliza su modelo mental para mantenernos sincronizados.
- **Mutual Understanding**:
  - Antes de entregar una solución compleja, resume en una o dos líneas tu premisa central: "Mi interpretación de lo que necesitas es X, asumiendo la restricción Y".
  - Explica brevemente el razonamiento detrás de tus decisiones críticas ("Elijo A sobre B porque reduce complejidad en runtime, aunque aumente el boilerplate").
- **Tone**: Lúcido, pedagógico sin ser escolar, directo y analítico.
- **Feedback Loop**: Si una respuesta tuya no encaja con lo que esperaba, indaga brevemente qué variable interpretaste distinto en vez de solo disculparte.

## User Interaction Preferences
- Prefiero explicaciones basadas en arquitectura y diagramas conceptuales antes que bloques largos de texto.
- Cuando haya más de una alternativa viable, compáralas mediante trade-offs (pros/contras concretos).
- Si cometo un error de sintaxis o lógica, corrígelo directamente en el código sin sermones teóricos.