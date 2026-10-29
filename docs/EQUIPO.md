# EQUIPO.md — Guía para el equipo

Para Kike, Armando, el doctor Milton y el jefe: cómo instalar una vez el proyecto en tu máquina, preguntarle cosas al agente `consulta` y pedir un cambio. Sin saber de consola: copias cada comando tal cual, lo pegas y pulsas Enter.

PoyectoNavegacion es un prototipo de investigación que se prueba sobre un phantom impreso; no es un dispositivo clínico (`docs/constitution.md`, principio 4). La copia que bajas trae también los datos de un paciente (un DICOM y un volumen CT): vienen por decisión del autor (ADR-019), y nadie los abre ni los envía a ningún sitio; `consulta` tampoco.

## 1. Instalar (una vez, con el autor delante)

Hace falta una cuenta de GitHub y haber aceptado la invitación del autor al repo (llega por correo de GitHub). Los tiempos son aproximados.

1. **Abre PowerShell.** Menú Inicio, escribe `PowerShell` y pulsa Enter. La línea empieza por `PS C:\Users\…>`.
2. **Instala Git for Windows** (2–4 min). Si Windows pregunta si permites cambios en el equipo, di que sí.
   `winget install --id Git.Git -e --source winget`
   Si dice que `winget` no se reconoce, bájalo de <https://git-scm.com/downloads/win> y dale «Next» en todas las pantallas, sin cambiar nada.
3. **Instala Claude Code** (1–2 min; no enseña progreso mientras baja).
   `irm https://claude.ai/install.ps1 | iex`
4. **Cierra PowerShell y abre otro** (paso 1), para que encuentre lo que acabas de instalar. Comprueba los dos; cada uno tiene que dar un número de versión:
   `git --version`
   `claude --version`
5. **Crea la carpeta y entra en ella** (segundos):
   `mkdir C:\Dev -Force`
   `cd C:\Dev`
6. **Baja el repo completo** (2–15 min según la red; unos 700 MB de descarga y alrededor de 1.3 GB en disco):
   `git clone https://github.com/chuyAguilar/PoyectoNavegacion.git`
   `cd PoyectoNavegacion`
   Desde aquí la línea empieza por `PS C:\Dev\PoyectoNavegacion>`. Todo lo que sigue se hace en esta carpeta.
7. **Tu nombre y tu correo en esta copia** (segundos). El nombre, el que usa el equipo (de él sale el nombre de tus peticiones); el correo, el de tu cuenta de GitHub:
   `git config user.name "Kike"`
   `git config user.email "tu-correo@ejemplo.com"`
8. **Activa los hooks del proyecto** (segundos). Son las reglas que revisan que lo que envías sean solo peticiones nuevas:
   `git config core.hooksPath equipo/hooks`
   `git config --get core.hooksPath`
   El segundo tiene que responder `equipo/hooks`.
9. **Entra en GitHub desde git** (1–2 min):
   `git push --dry-run origin HEAD:main`
   No envía nada (`--dry-run` es un ensayo). Se abre el navegador: entra con tu cuenta de GitHub y autoriza a «Git Credential Manager». Al volver, tiene que decir `Everything up-to-date`. Si dice «403», «permission denied» o «Repository not found», todavía no eres colaborador o entraste con otra cuenta: díselo al autor. Si no se abre el navegador y sale `Everything up-to-date`, también vale.
10. **Abre `consulta` por primera vez** (2–3 min):
    `claude --agent consulta`
    - Claude Code te pide entrar con tu cuenta: eso lo resuelve el autor contigo (esta guía no lo explica).
    - Después pregunta si confías en esta carpeta («trust this folder»). **Di que sí.** Hasta que lo aceptes, Claude Code no aplica los permisos del proyecto (`.claude/settings.json`) que dejan a `consulta` usar los comandos de git que solo leen sin pedirte permiso a cada paso; las prohibiciones (hacer commit o push, abrir los datos de paciente) valen igual.
    - Si alguna vez ves «Ignoring … permissions.allow entries from .claude/settings.json: this workspace has not been trusted», sal con `/exit`, vuelve a abrir con `claude --agent consulta` y acepta el diálogo.
    - Hazle una pregunta, por ejemplo «¿Qué se está haciendo ahora en el proyecto?». Tiene que responder diciendo de qué archivo lo saca (p. ej. `memory.md`). Con eso, la instalación está hecha.

## 2. Abrir `consulta` (cada vez)

En PowerShell (paso 1):

`cd C:\Dev\PoyectoNavegacion`
`claude --agent consulta`

Al arrancar trae solo lo último del repo y te dice en qué está el proyecto. Para salir, `/exit`.

Si Claude Code te pide permiso para un comando de git que solo lee (`git fetch origin`, `git pull --ff-only`, `git log`, `git status`) o para escribir en `peticiones/`, puedes aceptarlo. `consulta` no debería pedirte nada más; si lo hace, di que no y avísale al autor.

Opcional: para que `claude` solo abra ya `consulta`, crea en la carpeta del repo el archivo `.claude/settings.local.json` con `{"agent": "consulta"}` (es tuyo, no se envía). La guía sigue diciendo `claude --agent consulta`, que vale con o sin ese archivo.

## 3. Preguntas de ejemplo

- ¿Qué se está haciendo ahora y qué sigue?
- ¿Cómo sale la posición del marcador a partir de sus 4 esquinas?
- ¿Qué es el BACKLOG y qué hay pendiente con prioridad alta?
- ¿Por qué el tracker espera a Slicer antes de abrir la cámara?
- ¿Qué precisión tienen las cámaras y cómo se midió?

Cada respuesta dice de dónde sale (archivo y sección). Si algo no está escrito, te lo dice.

## 4. Cómo pedir algo

Díselo a `consulta` («quiero pedir que…»), o acepta cuando él te proponga convertir una idea en petición. `consulta` no cambia nada del proyecto: los cambios los decide y los hace el autor. Lo que hace es escribir tu petición, con su skill `peticion`:

1. Te hace dos o tres preguntas (qué, para qué, qué urgencia le ves).
2. Busca si ya existe algo parecido y te lo dice.
3. Escribe el archivo `peticiones/AAAA-MM-DD-<usuario>-<tema>.md` y te enseña el texto. Si quieres cambiar algo, dilo ahora: una petición enviada ya no se edita.
4. Te da cinco comandos de git, **uno por vez**, con el nombre de tu archivo ya puesto. Los ejecutas tú (ningún agente hace commit ni push) y él lee lo que salió antes de darte el siguiente. La primera vez que envías, el comando 4 puede abrir el navegador para entrar en GitHub.

Dónde ejecutar los comandos, como prefieras; los comandos son los mismos en los dos sitios:

- **Aquí mismo, con `!` delante.** En la conversación de `consulta` escribes `!`, pegas el comando y pulsas Enter. `consulta` ve la salida solo.
- **En una terminal aparte**, abierta en la carpeta del repo, y le pegas a `consulta` lo que salió:
  - PowerShell: menú Inicio, `PowerShell`, Enter, y `cd C:\Dev\PoyectoNavegacion`.
  - Git Bash: menú Inicio, `Git Bash`, Enter, y `cd /c/Dev/PoyectoNavegacion`.

La secuencia completa y por qué es así está en `peticiones/README.md`, «Cómo se envía». Si cambias a mano algún archivo fuera de `peticiones/`, no se puede enviar: los hooks lo rechazan. Para eso está la petición.

## 5. Qué pasa después

El autor ve tu petición la próxima vez que abre su agente `direccion`, y decide. La decisión queda escrita en tu archivo, en el bloque «Decisión del autor»: `aceptada → B-nn` (una entrada del BACKLOG), `aceptada → meta NNN` (un trabajo nuevo) o `rechazada`, con el motivo y la fecha. Para verla, abre `consulta` (trae lo último al arrancar) y pregúntale «¿qué pasó con mi petición?».

## 6. Si algo falla

- **Un comando del envío:** `consulta` sigue la tabla «Si uno falla» de `peticiones/README.md` y te dice qué hacer. Nunca uses `reset --hard`, `checkout --`, `clean`, `--force` ni `--no-verify`, aunque lo leas en internet: ninguno hace falta y pueden perder trabajo o saltarse las reglas.
- **La instalación:** si `git` o `claude` «no se reconoce» después de instalarlos, cierra PowerShell y abre otro (paso 4). Si sigue, o si falla otra cosa, para ahí.
- **A quién avisar:** al autor (Chuy), con la salida del comando copiada tal cual. Cuando `consulta` o la tabla dicen «avisa al autor», no sigas con más comandos.
