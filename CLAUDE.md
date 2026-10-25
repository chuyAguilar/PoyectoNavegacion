# CLAUDE.md — instrucciones para Claude Code en PoyectoNavegacion

Instrucción de herramienta: cómo se trabaja en este repo. No es documentación del proyecto ni repite sus principios.
Los principios están en `docs/constitution.md`, que manda sobre este archivo; aquí se remite a ellos por su número.
El conocimiento técnico detallado está en las skills `surgical-navigation-aruco`, `slicer-igt-workflow` y `surgical-nav-project-context`.

## 1. Al arrancar

En este orden:

1. Lee completos `docs/constitution.md`, `memory.md` y `docs/CONTEXT.md`.
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

- **Los roles.** Cuatro archivos en `.claude/agents/`: `direccion` (la sesión principal; el autor la abre con `claude --agent direccion`), y `planificacion`, `desarrollo` y `pruebas`, subagentes que solo lanza la dirección, uno a la vez y con su propio contexto. Las rutinas son skills en `.claude/skills/`: `planear` (la usa `planificacion`), `fase` y `cerrar-fase` (las usa `desarrollo`); la dirección no tiene `Skill` y se las encarga.
  Los subagentes no preguntan: si algo los para, devuelven una sola línea, «Parado: por qué». `pruebas` no escribe código y solo escribe `docs/PRUEBAS.md` (al final) y `Claude outputs/pruebas/`; lo que necesita hardware lo deja como protocolo para el autor.
- **Git.** Ningún agente ejecuta `git commit` ni `git push` (principio 1): `.claude/settings.json` lo niega. Git de lectura, `git mv` y `git rm --cached` sí, y **siempre desde PowerShell**, nunca desde un sandbox Linux (principio 9). No se reescribe el historial.
- **Datos de paciente (principio 5).** No se leen ni se editan `herramientas/A/`, `*.nrrd`, `*.dcm` ni `documentos/VERONICA/`; `settings.json` lo niega. Una negación no se rodea: se dice en el reporte.
- **La cadena (principio 6).** Una fase que toque `tracker.py`, `camera/`, `vision/`, `transport/` o los scripts de Slicer dice en su plan cómo verifica que la cadena sigue igual.
- **Verificación.** Antes de dar una fase por terminada: la suite en verde, con su tiempo, y la comprobación de «no cambió» que fije el spec (suite + replay sobre un dataset grabado, cuando exista). Lo que necesita cámara o Slicer se verifica en vivo con el autor y se reporta el número.
- **Tras editar** un `.py`: `py_compile` y conteo de líneas (Edit/Write han truncado archivos antes).
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
python -m diagnostics.identify_ids --config profiles\tracker_config_gs1.yaml
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
