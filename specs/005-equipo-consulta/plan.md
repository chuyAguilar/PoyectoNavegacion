# Plan — Meta 005 · Agente de consulta para el equipo y buzón de peticiones

Lo escribe el agente de planificación con `/planear`, sin código. Lo que el autor autoriza es este archivo.

## Qué cambió en esta revisión (2026-10-28, segunda)

Ajustado con P14–P17 de `clarify.md`. Sale el script de envío `equipo/enviar_peticion.ps1`, con sus pruebas, sus códigos de salida y las dos negaciones que proponía para `settings.json` (P14): `settings.json` no gana ninguna negación. En su lugar, la secuencia de envío son cinco comandos de git que el compañero ejecuta uno por uno; está escrita una sola vez, en `peticiones/README.md` («Cómo se envía»), y la skill `peticion` se la da con el nombre de su archivo ya puesto, uno a uno, leyendo la salida de cada uno antes de dar el siguiente. Los comandos valen igual en PowerShell y en Git Bash, en una terminal aparte o con `!` en `consulta` (P15). Las comprobaciones que hacía el script se reparten: el hook activo, los commits locales sin empujar y el nombre ya usado en `origin` los comprueba `consulta` con git de lectura antes del primer comando; lo que llega a `origin` lo siguen filtrando `pre-commit` y `pre-push`. `consulta` se abre siempre con `claude --agent consulta` (P16). La cuenta de Claude Code queda fuera de la meta (P17): `EQUIPO.md` no la explica. Siguen 5 fases; la 1 sigue siendo la única pesada.

## Lo leído

- HEAD `c252259` («Anota las pruebas de la meta 004 · Cómo funciona el tracker y corrige una fuente de §9.5»). Árbol: `memory.md` modificado y `specs/005-equipo-consulta/` sin seguir; nada de `codigo/` ni `docs/`.
- `specs/005-equipo-consulta/spec.md`, `clarify.md` (P1–P17), `tasks.md` y el `plan.md` anterior, completos; `docs/constitution.md`, `memory.md`, `CLAUDE.md`, `docs/CONTEXT.md` §4 y §5.
- `docs/DECISIONS.md`: índice, ADR-019 (datos de paciente versionados; se reabre si el repo se abre fuera del equipo médico) y ADR-020. El último es ADR-033. `docs/BACKLOG.md`: índice (la última es B59) y B13. `docs/ARCHITECTURE.md` §6 (árbol del repo, cuatro agentes). `docs/PRUEBAS.md`: índice y formato (la última es P05).
- `.claude/settings.json` (niega `git commit` y `git push` en Bash y PowerShell, con las formas `git * commit *` y `git * push *`, y los datos de paciente; permite git de lectura —`log`, `status`, `diff`, `show`, `ls-files`— y las tres skills; no permite `git fetch`, `git config` ni `git ls-tree`), `.claude/agents/direccion.md`, las cabeceras de `planificacion.md` y `pruebas.md`, las de las tres skills de `.claude/skills/`, `.gitattributes` (`*.ps1` y `*.bat` en CRLF; nada para `*.sh` ni para archivos sin extensión como los hooks). `core.hooksPath` no está fijado en la máquina del autor.
- `codigo/`: no se lee más allá de su lugar en el árbol: la meta no lo toca.

### Lo consultado por Context7 (solo API; ninguna ruta ni dato clínico)

- **Claude Code** (`/websites/code_claude`, documentación oficial; consultado en la revisión anterior y vigente):
  - **El prefijo `!` (modo shell):** ejecuta el comando «sin pasar por Claude», sin que Claude lo interprete ni lo apruebe, y el comando y su salida se añaden a la conversación; Claude responde a esa salida salvo que `respondToBashCommands` sea `false`. Corre fuera del sandbox y no pasa por las reglas de permiso. Es una acción del compañero, no del agente: por eso las negaciones de commit y push no lo paran ni hace falta tocarlas.
  - **Qué shell usa `!`:** la clave `defaultShell`; por defecto `bash`, y en Windows `powershell` solo si no hay Bash. Con Git for Windows instalado, `!` corre en Git Bash: los comandos tienen que valer igual en Bash y en PowerShell (P15).
  - **Las reglas de permiso** son para las herramientas de Claude (`Bash(...)`, `PowerShell(...)`, `Edit(...)`, `Skill(...)`); `*` vale en cualquier posición.
  - **Skills:** `.claude/skills/<nombre>/SKILL.md`, con `name`, `description`, `argument-hint`, `disable-model-invocation`, `allowed-tools`, entre otros. Sin `disable-model-invocation`, Claude la puede invocar sola cuando la conversación lo pide (P10).
  - **Agentes:** la cabecera admite `tools`, `model`, `permissionMode`, `skills` (precarga la skill), `effort`, entre otros. La clave `agent` de settings fija el agente de la sesión principal; P16 la deja como opción explicada en `EQUIPO.md`.
- **Git** (`/websites/git-scm`):
  - `git commit <pathspec>` (el `--only` por defecto) registra solo las rutas dadas, sin lo que ya estaba en el índice; esas otras rutas quedan para un commit posterior (consultado 2026-10-28). Un archivo sin seguir tiene que pasar antes por `git add`.
  - `pre-push` recibe por stdin `<local-ref> <local-oid> <remote-ref> <remote-oid>`, con `remote-oid` todo ceros si la rama remota no existe y `local-ref` = `(delete)` al borrar; si sale ≠ 0 no se empuja nada. `git pull --rebase` se niega con cambios locales salvo `--autostash`, que los guarda y los repone; un rebase se aborta sin daño con `git rebase --abort` (revisión anterior).
- **Sin verificar, y se mide en vivo:** si Windows PowerShell 5.1 pasa el separador `--` a un ejecutable nativo o se lo come. Para no depender de ello, los comandos de envío no usan `--`: la ruta de la petición es inequívoca (existe en el árbol). Y el mensaje del commit va sin tildes («Peticion: …») para no depender de la página de códigos de la consola de PowerShell 5.1.

## Respuestas a las preguntas del spec (al día con `clarify.md`)

- **Agente por defecto:** no (P16). `docs/EQUIPO.md` dice abrir siempre `claude --agent consulta` (principio 7) y explica, como opción, `{"agent": "consulta"}` en su `.claude/settings.local.json`.
- **Permisos por ruta:** fuera (P9). El compañero tiene libertad total en su máquina. Lo que sigue valiendo es `settings.json` versionado (niega commit, push y datos de paciente a cualquier agente) y, como único seguro de lo que llega a `origin`, los hooks de git versionados.
- **Qué impide que un compañero empuje otra cosa:** los hooks `pre-commit` y `pre-push` de `equipo/hooks/`, activados con `git config core.hooksPath equipo/hooks`. Se saltan con `--no-verify`, quitando `core.hooksPath` o empujando desde otra herramienta: va al BACKLOG como riesgo (P12). En el servidor, solo el ruleset de `main` que bloquea force-push y borrado (P5). Si las reglas cambian, se cambian los hooks y llegan con el siguiente `git pull`.
- **Los comandos de envío:** cinco comandos de git, sin script (P14), abajo en «El envío».
- **Modelo de `consulta`:** `sonnet`, `effort: medium` (P2). La cuenta, fuera de la meta (P17).
- **Probar `consulta` sin una persona:** `claude -p --agent consulta` en un clon de prueba del scratchpad (fase 2). Los hooks, dándoles las listas de cambios como entrada y con rangos del historial real; lo que exige `git commit` lo hace el autor en vivo.
- **El instalador:** no hay (P13). `docs/EQUIPO.md` lleva los pasos con los comandos exactos y el autor guía por consola. Sin `gh`: la autenticación la hace Git Credential Manager, que trae Git for Windows (el primer push abre el navegador).

### El envío (cinco comandos, en `peticiones/README.md` «Cómo se envía»)

**Antes del primer comando, lo comprueba `consulta`** (git de lectura; con `permissionMode: default` Claude Code le pide permiso al compañero para lo que `settings.json` no permite, como `git fetch`):
- `git config --get core.hooksPath` vale `equipo/hooks`. Si no, le da primero `git config core.hooksPath equipo/hooks`, le explica para qué sirve y vuelve a comprobar. Sin esto los hooks no corren y nada filtra el envío.
- `git fetch origin` y `git log origin/main..HEAD --oneline` vacío: no hay commits locales sin empujar. Si los hay, le explica cuáles son y que el push los llevaría; si alguno no es una petición nueva, `pre-push` rechazará el envío entero, y le dice que avise al autor antes de seguir (no propone `reset` ni nada que los borre).
- `git ls-tree --name-only origin/main peticiones/<archivo>.md` vacío: el nombre no está usado en `origin`. Si lo está, cambia el nombre del archivo antes de dar los comandos (así el rebase no puede chocar).
- `git status --porcelain`: si hay cambios fuera de `peticiones/`, le explica qué son y que el envío no los toca.

**Los comandos,** uno por vez; el compañero pega cada uno (en su terminal o con `!` en `consulta`) y `consulta` lee la salida antes de dar el siguiente. Rutas con `/`, comillas dobles, sin `--`, sin `&&` ni `$`: valen igual en PowerShell y en Git Bash.
1. `git add peticiones/<archivo>.md`: solo su petición.
2. `git commit -m "Peticion: <tema> (<usuario>)" peticiones/<archivo>.md`: con la ruta en el comando entra solo ese archivo aunque haya otras cosas en el índice. El hook `pre-commit` lo revisa.
3. `git pull --rebase --autostash origin main`: trae lo nuevo; los cambios locales del compañero se guardan y se reponen solos.
4. `git push origin HEAD:main`: el hook `pre-push` lo revisa. La primera vez abre el navegador para entrar en GitHub.
5. `git log origin/main --oneline -1 peticiones/<archivo>.md`: si sale el commit, llegó (el push pone al día `origin/main` en su copia). `consulta` puede confirmarlo con `git fetch origin` y el mismo `git log`.

**Si uno falla** (la tabla va en el README y la skill la sigue; nunca `reset --hard`, `checkout --`, `clean`, `--force` ni `--no-verify`):
- 1 dice que la ruta no existe: el nombre está mal escrito; `consulta` le da la ruta exacta.
- 2 lo rechaza `pre-commit`: el mensaje del hook dice qué archivo y por qué; si es la petición misma (falta `Decisión: pendiente`), `consulta` la corrige y se repite 2. «nothing to commit»: ya estaba hecho; se mira `git log origin/main..HEAD --oneline` y se sigue en 3.
- 3 con conflicto: `git rebase --abort` (deja la copia como antes del 3) y avisar al autor. Con el chequeo del nombre no debería pasar. Si `--autostash` no puede reponer los cambios, quedan guardados en `git stash list`: no se pierden; avisar al autor.
- 4 rechazado por «non-fast-forward» o «fetch first»: alguien empujó entre medias; repetir 3 y 4 (hasta tres veces). Rechazado por `pre-push`: el mensaje dice qué commit trae algo que no es una petición nueva; avisar al autor. «403», «permission denied» o «Repository not found»: no es colaborador o entró con otra cuenta; avisar al autor.
- 5 no sale nada: `git fetch origin` y repetir 5; si sigue sin salir, el push no llegó: volver a 4.

## Archivos

Se crean:
- `peticiones/README.md`: el flujo (preguntar → la skill escribe la petición → el compañero ejecuta los comandos → el autor decide en `direccion`), los estados (pendiente; aceptada → B-nn o meta NNN; rechazada, con motivo), el nombre `AAAA-MM-DD-<usuario>-<tema>.md` (`<tema>` en minúsculas, sin tildes ni espacios), que una petición enviada no se edita (para corregirla, otra nueva que la cite) y «Cómo se envía»: las comprobaciones previas, los cinco comandos y la tabla de fallos de arriba.
- `peticiones/_plantilla.md`: arriba, la nota visible «> Petición escrita por el agente de consulta para <nombre> (<usuario>), el AAAA-MM-DD» (P10); quién, cuándo, de parte de quién, qué se pide, para qué, urgencia percibida (baja/media/alta), lo relacionado que encontró (meta, B-nn, ADR, otra petición), y el bloque «Decisión del autor» con la línea literal `Decisión: pendiente`, que solo llena `direccion`.
- `equipo/hooks/revisar_peticiones.sh`: la regla, en `sh` (Git for Windows lo trae; no hace falta Python en la máquina del compañero).
- `equipo/hooks/pre-commit` y `equipo/hooks/pre-push`.
- `.claude/agents/consulta.md`: el quinto papel.
- `.claude/skills/peticion/SKILL.md`: la skill de peticiones de `consulta` (P10).
- `equipo/peticiones_pendientes.ps1`: lo que corre `direccion` al arrancar.
- `equipo/pruebas/probar_hooks.ps1`, `equipo/pruebas/probar_consulta.ps1`, `equipo/pruebas/guion_consulta.json`.
- `docs/EQUIPO.md`: la guía de una página, con los pasos de instalación (P13).

Se modifican:
- `docs/constitution.md` principio 1 y `docs/DECISIONS.md` (ADR-034 con su índice): los escribe la dirección antes de la fase 1.
- `.gitattributes`: `equipo/hooks/* text eol=lf` (un `sh` con CRLF falla en Git Bash).
- `.claude/settings.json`, solo en `allow` y solo git de lectura: `Bash(git config --get *)`, `PowerShell(git config --get *)`, `Bash(git --no-optional-locks ls-tree *)`, `PowerShell(git --no-optional-locks ls-tree *)` (fase 2, para las comprobaciones de `consulta`); `Bash(git fetch origin*)`, `PowerShell(git fetch origin*)` y la forma de lanzar `equipo/peticiones_pendientes.ps1` (fase 4, para `direccion`). Ninguna negación se añade ni se relaja (P14).
- `.claude/agents/direccion.md`: el aviso al arrancar, cómo se decide una petición y el `git pull --rebase` del autor antes de su push.
- `CLAUDE.md` §1 (el paso de las peticiones tras leer `memory.md`) y §4 (cinco papeles; la skill `peticion` la usa `consulta`; los compañeros envían sus peticiones nuevas con los comandos de `peticiones/README.md`, ADR-034).
- `memory.md`: la línea «Peticiones pendientes: N».
- `docs/ARCHITECTURE.md` §6 (el árbol: `peticiones/`, `equipo/`, cinco agentes, cuatro skills), `docs/CONTEXT.md` §5 (quién commitea) y §6 si cambia el estado, `docs/BACKLOG.md` (entradas nuevas e índice, las escribe la dirección).

No se toca: `codigo/` entero, `.claude/settings.local.json` del autor, las tres skills que hay, `planificacion.md`, `desarrollo.md`, `pruebas.md`.

## Funciones y clases

Ninguna en `codigo/`. Scripts:
- `revisar_peticiones.sh`: lee de stdin líneas `<estado>\t<ruta>`; sale 0 si todas son `A peticiones/<nombre>.md` (sin `README.md` ni `_plantilla.md`), 1 con una línea en español por cada ruta rechazada («`docs/x.md`: solo se pueden enviar peticiones nuevas en `peticiones/`»; «`peticiones/y.md`: una petición enviada no se modifica ni se borra; escribe otra»). Sin entrada, 0.
- `pre-commit`: `git diff --cached --name-status --no-renames` → `revisar_peticiones.sh`; y, por cada petición nueva, `git show :<ruta>` tiene que traer la línea `Decisión: pendiente` (si no: «la decisión la escribe el autor»). Con `git commit <ruta>`, git le pasa al hook un índice temporal con solo esa ruta sobre HEAD, así que lo demás que el compañero tenga en el índice no lo hace fallar (se mide en vivo, caso f).
- `pre-push <remoto> <url>`: por cada línea de stdin, rechaza `(delete)`; si `remote-oid` es todo ceros usa `origin/main..<local-oid>`, si no `<remote-oid>..<local-oid>`; `git diff --name-status --no-renames` de ese rango → `revisar_peticiones.sh`. Atrapa un commit hecho con `--no-verify` y los commits locales que no son peticiones.
- `peticiones_pendientes.ps1 -Ref <ref> [-SinFetch]`: `git fetch origin` (salvo `-SinFetch`); lista `peticiones/*.md` de `<ref>` (sin `README.md` ni `_plantilla.md`) con `Decisión: pendiente`, como «archivo · quién · fecha · qué», y al final «Peticiones pendientes: N» y «Commits nuevos en origin/main: M» (`git rev-list --count HEAD..origin/main`). Lee con `git show <ref>:<ruta>`, sin tocar el árbol. `-Ref` explícito (principio 7).
- `probar_hooks.ps1 -Trabajo <dir>` y `probar_consulta.ps1 -Clon <dir> -Guion <json> -TopeSegundos <s>`: imprimen caso / esperado / obtenido y «N de M»; código ≠ 0 si falla alguno; todo con tope (principio 9).

Textos:
- `consulta.md` (cabecera): `tools: Read, Glob, Grep, Write, Edit, Bash, PowerShell, Skill`; `permissionMode: default`; `model: sonnet`; `effort: medium`; `skills: [peticion]`. Al arrancar, `git pull --ff-only` (si falla, explica por qué y sigue con lo que hay, diciéndolo); lee `memory.md`, `docs/CONTEXT.md`, los índices de `ARCHITECTURE`, `DECISIONS`, `BACKLOG` y `PRUEBAS`, y `git log --oneline -15`. Responde en llano, explica la jerga (remite al glosario de `ARCHITECTURE.md` §9.4), cita archivo y sección y dice «no está documentado» cuando no lo está. No escribe fuera de `peticiones/`: una orden de cambiar código, docs o configuración la convierte en petición con la skill. No ejecuta ninguno de los cinco comandos de envío (tampoco `git add`): los da y espera la salida. No llama al sistema «listo para cirugía» (principio 4) ni lee ni propone leer los datos de paciente (principio 5).
- `peticion/SKILL.md` (cabecera: `name: peticion`, `description` que dice que es de `consulta` y cuándo se usa: cuando de una duda sale una propuesta o el compañero pide un cambio; `argument-hint: "[tema]"`): (1) dos o tres preguntas para completar qué, para qué y la urgencia; (2) busca si ya existe en `docs/BACKLOG.md`, `peticiones/` y `specs/` y lo dice (si existe, propone citarla en vez de duplicarla); (3) el usuario sale de `git config user.name` en minúsculas, sin tildes ni espacios, y el nombre `AAAA-MM-DD-<usuario>-<tema>.md`; (4) escribe el archivo desde `_plantilla.md`, con la nota visible; (5) le enseña el texto; (6) hace las comprobaciones previas de «El envío»; (7) le pregunta dónde los va a ejecutar (terminal aparte o `!`) y le da los cinco comandos uno por vez con el nombre ya puesto, leyendo cada salida (con `!` la ve en la conversación; en la terminal le pide que la pegue); (8) si uno falla, sigue la tabla de `peticiones/README.md`; (9) termina cuando el 5 muestra el commit, y le dice qué pasa después.

## Fases

### Antes de la fase 1 (la dirección)

La dirección escribe ADR-034 y la enmienda del principio 1 (texto propuesto abajo), y van en el commit de la fase 1. Sin ellos la fase 1 no empieza (principio 10).

### Fase 1 · El buzón `peticiones/` y los hooks — pesada

- **Entrega:** `peticiones/README.md` (con «Cómo se envía»), `peticiones/_plantilla.md`, `equipo/hooks/{revisar_peticiones.sh,pre-commit,pre-push}`, `equipo/pruebas/probar_hooks.ps1`, `.gitattributes`, y la regla en `CLAUDE.md` §4 (Git) y `docs/CONTEXT.md` §5.
- **Criterio (agente), `probar_hooks.ps1`:** (1) `revisar_peticiones.sh` con 8 listas: `A peticiones/2026-10-28-kike-x.md` pasa; `A codigo/x.py`, `M peticiones/y.md`, `D peticiones/y.md`, `A peticiones/README.md`, `M peticiones/_plantilla.md`, `A peticiones/x.txt` y la mezcla `A peticiones/ok.md` + `M docs/BACKLOG.md` se rechazan, cada una con su mensaje: **8 de 8**. (2) `pre-commit` en un repo temporal del scratchpad (`git init`, `core.hooksPath`, `git add`, sin commit): petición nueva con `Decisión: pendiente` → 0; archivo fuera → 1; petición nueva sin esa línea → 1: **3 de 3**. (3) `pre-push` con líneas de stdin armadas con commits del historial real (solo lectura): un rango que toca `docs/` o `specs/` → 1; `(delete)` → 1; `remote-oid` en ceros → usa `origin/main..` y rechaza lo que no sea petición: **3 de 3**. (4) La sintaxis de `probar_hooks.ps1` con el parser de PowerShell y la de los `sh` con `sh -n`: 0 errores. (5) Los cinco comandos de «Cómo se envía» no llevan `--`, `&&`, `$` ni `\`: lo comprueba el script leyendo el README.
- **Criterio (en vivo, el autor, ~15 min):** en un repo de juguete del scratchpad (solo `equipo/` y `peticiones/` copiados, sin datos de paciente) con un remoto desnudo también en el scratchpad, nunca GitHub, con `core.hooksPath equipo/hooks`, siguiendo «Cómo se envía» al pie de la letra: (a) los cinco comandos en PowerShell con una petición nueva → el 5 muestra el commit y el mensaje se lee bien en `git log` del remoto; (b) lo mismo en Git Bash con otra petición; (c) modificar una petición enviada y commitear → `pre-commit` la rechaza; (d) commit de un archivo fuera de `peticiones/` → rechazado; (e) ese commit con `--no-verify` y `git push --dry-run` → `pre-push` lo rechaza; (f) con un cambio en el índice y otro sin añadir en otros archivos, los cinco comandos envían solo la petición y los dos cambios siguen en la copia; (g) con un push hecho antes desde un segundo clon de juguete, el 4 sale «non-fast-forward» y repetir 3 y 4 lo resuelve, como dice la tabla: **7 de 7** (c, d y la petición de a son el 3 de 3 del spec). Los comandos exactos van en el reporte.
- **No cambió:** suite 618 de 618 con su tiempo, replay de Marker0 0.0 mm / 0.0°, `git diff --stat c252259 -- codigo/` vacío. Líneas < 2 000.
- **Peso:** pesada: los hooks son la única barrera de la regla nueva (P9, P12) y la secuencia de envío corre en máquinas ajenas; un fallo deja pasar lo que no debe, bloquea a quien sí puede o le pierde cambios al compañero.

### Fase 2 · El agente `consulta` y su skill de peticiones — ligera

- **Entrega:** `.claude/agents/consulta.md`, `.claude/skills/peticion/SKILL.md`, `equipo/pruebas/probar_consulta.ps1`, `equipo/pruebas/guion_consulta.json`; los cuatro `allow` de lectura de la fase 2 en `.claude/settings.json`; `CLAUDE.md` §4 (cinco papeles, cuatro skills). Si editar `.claude/` le pide permiso al agente y no se lo dan, «Parado» y lo hace la dirección.
- **Criterio (agente), `probar_consulta.ps1`:** en un clon de prueba del scratchpad hecho desde el repo local sin poner en el árbol `herramientas/A/`, `documentos/VERONICA/`, `*.nrrd` ni `*.dcm` (es una prueba del agente, no el clon de un compañero), con `origin` apuntando a un remoto desnudo del scratchpad, con `claude -p --agent consulta --output-format json --max-turns 15 --max-budget-usd 1` y tope por pregunta: (1) las 5 preguntas guion (qué se está haciendo → `memory.md`; qué sigue → `memory.md` o `docs/BACKLOG.md`; cómo sale la pose de 4 esquinas → `docs/ARCHITECTURE.md` §9.2; qué es el BACKLOG → `docs/BACKLOG.md` o constitución principio 8; por qué ADR-028 → `docs/DECISIONS.md` ADR-028), cada respuesta con su archivo y sección (cadenas fijas en el JSON del guion): **5 de 5**. (2) La orden «edita `codigo/tracker.py` y cambia el puerto a 18945», con `--allowedTools` solo para `Write`/`Edit` de `peticiones/**`, `Skill(peticion)` y los `allow` de lectura: no edita, usa la skill, escribe una petición con la nota visible y `Decisión: pendiente`, y su respuesta trae el comando 1 con el nombre del archivo y no los cinco de golpe; `git status --porcelain` lista solo `?? peticiones/…` (sin añadir: no ejecutó `git add`). (3) Lo mismo con `core.hooksPath` sin fijar en el clon: la respuesta da `git config core.hooksPath equipo/hooks` antes del comando 1. Se anotan el coste (`total_cost_usd`) y el tiempo por pregunta.
- **Si `claude -p` no se puede lanzar desde el agente** (anidado, cuenta, permisos): (1)–(3) pasan a protocolo en vivo para el autor con los comandos exactos, y la fase queda «parcial» hasta sus números.
- **Criterio (en vivo, el autor, ~15 min):** en ese clon de prueba, con `core.hooksPath` activo, `claude --agent consulta`: pide un cambio; se anota cuántas preguntas hizo la skill y si encontró algo relacionado. Envía una petición con `!` y otra en una terminal aparte (P15); en las dos `consulta` da los comandos uno por vez, lee cada salida y confirma que llegó. Antes de la segunda, el autor empuja algo al remoto desde otro clon, para que el 4 falle por «non-fast-forward»: `consulta` lo resuelve con la tabla. Se anotan: 2 de 2 llegadas, el shell en que corrió `!`, y si la guía ante el fallo fue la de la tabla.
- **No cambió:** como en la fase 1.
- **Peso:** ligera: textos de un agente y una skill y un script de prueba; lo que puede fallar (citar mal, no usar la skill, dar mal un comando) lo miden el guion y la sesión en vivo.

### Fase 3 · La guía `docs/EQUIPO.md` y la instalación guiada — ligera

- **Entrega:** `docs/EQUIPO.md`, una página: (1) instalar una vez, con los comandos exactos y cuánto tarda cada uno: Git for Windows, Claude Code, clonar completo (P6) en una carpeta fija, `git config user.name` y `user.email` en ese clon, `git config core.hooksPath equipo/hooks`, la primera entrada en GitHub con el autor delante (la cuenta de Claude Code no se explica: P17); (2) abrir: `claude --agent consulta` en la carpeta del repo y, como opción, dejarlo por defecto con `{"agent": "consulta"}` en `.claude/settings.local.json` (P16); (3) cinco preguntas de ejemplo; (4) cómo pedir algo y dónde ejecutar los comandos: con `!` en `consulta` o en una terminal aparte (PowerShell o Git Bash) abierta en la carpeta del repo, cómo se abre cada una, y que los comandos son los mismos (P15); (5) qué pasa después con la petición; (6) qué hacer si un comando falla: remite a la tabla de `peticiones/README.md` y a quién avisar. Sin «listo para cirugía»; los datos de paciente se nombran solo para decir que vienen en el clon y que nadie los abre ni los envía.
- **Criterio (en vivo, el autor, ~20 min):** sigue `EQUIPO.md` al pie de la letra en una carpeta nueva de su máquina (ese clon sirve para la fase 4): cuántos pasos de N salen sin nada que no esté escrito (se espera N de N; lo que falte se corrige en la fase), los minutos totales y los del clon, el tamaño en MB del clon, `git config core.hooksPath` = `equipo/hooks`, y `consulta` abre y responde una pregunta con su fuente. Líneas de `EQUIPO.md` < 2 000.
- **No cambió:** como en la fase 1.
- **Peso:** ligera: un documento y su lectura guiada.

### Fase 4 · El aviso de peticiones en `direccion` y el circuito completo — ligera

- **Entrega:** `equipo/peticiones_pendientes.ps1`; `.claude/agents/direccion.md` (al arrancar, después de leer `memory.md`, corre `peticiones_pendientes.ps1 -Ref origin/main` y lista las pendientes antes de cualquier otra cosa, con la nota de qué compañero la envió; si hay commits nuevos en `origin/main`, le recuerda al autor `git pull --rebase`, también antes de cada push suyo; al decidir, llena el bloque «Decisión del autor» con la fecha y, si se acepta, crea la entrada B-nn o el spec y los enlaza en los dos sentidos); `CLAUDE.md` §1; los `allow` de la fase 4 en `.claude/settings.json`; `memory.md` con «Peticiones pendientes: N»; `docs/ARCHITECTURE.md` §6. Si editar `.claude/` le pide permiso al agente y no se lo dan, «Parado» y lo hace la dirección.
- **Criterio:** (1) `peticiones_pendientes.ps1 -Ref HEAD -SinFetch` sobre el árbol: 0 pendientes (solo `README.md` y `_plantilla.md`). (2) **El circuito, en vivo con el autor (~10 min):** desde el clon de la fase 3, el autor pide algo a `consulta` y envía la petición con los cinco comandos, esta vez a `origin` en GitHub; en su clon principal abre `claude --agent direccion` y la lista sale primero, con 1 pendiente, su nota y el aviso de `git pull`; tras el `git pull`, `direccion` la cierra como «rechazada: prueba» y, tras el commit del autor, el script da 0. Se anotan la petición en `git log origin/main`, el tiempo hasta verla y si hubo que intervenir.
- **No cambió:** como en la fase 1.
- **Peso:** ligera: un script de lectura y textos de instrucciones.

### Fase 5 · Un compañero real instala, pregunta y envía una petición — ligera

- **Antes (el autor):** los usuarios de GitHub de Kike, Armando y el doctor Milton, y si son del equipo médico (lo que queda de P1); invitarlos como colaboradores; el ruleset de `main` (P5; GitHub, Settings → Rules); que el compañero tenga ya con qué entrar en Claude Code (P17, fuera de la meta).
- **Criterio, en vivo con el autor:** el compañero instala con el autor guiándolo por `EQUIPO.md`, hace una pregunta y envía una petición sin ayuda, en el sitio que elija (P15); el autor la ve en `direccion`. Se anotan los minutos de la instalación, las veces que hubo que ayudarle en el envío (la meta pide 0), dónde ejecutó los comandos, la petición en `git log origin/main` y lo que no entendió (va a `EQUIPO.md` o a `peticiones/README.md` en esta fase, o al BACKLOG).
- **Cierre de la meta:** `memory.md`, BACKLOG, índices, `CONTEXT.md` §6; suite 618 de 618 con su tiempo, replay 0.0 mm / 0.0°, `git diff --stat c252259 -- codigo/` vacío; ninguna línea de `docs/`, `memory.md` o `specs/` > 2 000. La dirección encarga las pruebas de la meta a `pruebas` (los scripts de `equipo/pruebas/` sobre HEAD).
- **Peso:** ligera: medición y textos.

### La cadena (principio 6)

Ninguna fase toca `codigo/`, ni por tanto `tracker.py`, `camera/`, `vision/`, `transport/`, `pyigtl` ni los scripts de Slicer. Cada fase lo comprueba con `git diff --stat c252259 -- codigo/` vacío, la suite (618 de 618) y el replay de Marker0 (gs1 y gs2, 0.0 mm / 0.0°). No hace falta sesión con Slicer.

## Lo que va al BACKLOG

Los números y el texto los pone la dirección (la última es B59).
- **El repo es público y versiona el DICOM; ahora más personas tienen escritura y el clon completo (P6) lo pone en sus máquinas** (ADR-019, que pide reabrirse si alguno no es del equipo médico; lo dirá lo que queda de P1). Alta (P4). Mover el DICOM o hacer el repo privado no entra en esta meta.
- **Los hooks se pueden saltar** (`--no-verify`, quitar `core.hooksPath`, editar el hook, empujar desde otra herramienta) y nada del servidor impide por ruta lo que llega a `main` (los push rulesets no existen en un repo personal y público). Con libertad total (P9), `consulta` u otro agente pueden cambiar archivos en la copia del compañero si él lo aprueba; el hook impide enviarlos, no hacerlos. Que el hook esté activo lo comprueba `consulta` antes de cada envío, pero un envío sin `consulta` no pasa por esa comprobación. Qué haría falta: ramas por compañero con `main` restringido, una Action que avise (P12 la deja fuera) o un repo de organización privado. Media.
- **El envío son cinco comandos a mano** (P14): si en las fases 2 y 5 el compañero necesitó ayuda o se equivocó de comando, un alias de git versionado o un script lanzado por él lo acortaría. Baja: espera los números de la fase 5.
- **El resumen periódico para el jefe** (`docs/ESTADO.md` que `direccion` actualiza al cerrar cada meta; P3). Baja.
- **Las pruebas de `equipo/` corren fuera de la suite** (`probar_*.ps1`); integrarlas en pytest pediría tocar `codigo/tests`. Baja.
- **El guion de `consulta` cuesta dinero en cada corrida** (`claude -p`): no se corre en cada fase. Baja, informativa, con el coste medido en la fase 2.

## ADR que se proponen

- **ADR-034 · Los compañeros envían peticiones: commit y push solo de archivos nuevos en `peticiones/`, y lo hacen ellos** (enmienda el principio 1 y matiza ADR-020). Decisiones del autor del 2026-10-27 y 2026-10-28 (P9–P16). Texto propuesto para el principio 1, como tercer punto: «**Los compañeros del equipo** hacen commit y push solo de archivos nuevos en `peticiones/`, ejecutando ellos los comandos de `peticiones/README.md` que les da, uno por uno, la skill `peticion` de `consulta`; una petición enviada no se edita. Ningún agente ejecuta `git commit` ni `git push`, tampoco `consulta` (ADR-034).» Consecuencias: el único seguro son los hooks versionados `pre-commit` y `pre-push`, que se activan con `core.hooksPath` en sus máquinas y cambian con las reglas del proyecto, sin tocar permisos de GitHub; en su máquina tienen libertad total con Claude Code (P9); saltarse los hooks queda como riesgo en el BACKLOG (P12); no hay script de envío ni negación nueva en `settings.json` (P14); el autor hace `git pull --rebase` antes de su push.

## Preguntas abiertas

Lo que queda de P1 (usuarios de GitHub de Kike, Armando y el doctor Milton, y si los tres son del equipo médico, por ADR-019) sigue en su bloque de `clarify.md`; hace falta antes de la fase 5. No hay preguntas nuevas: P14–P17 están contestadas y aplicadas.

## Títulos de commit

- Fase 1: «Abre el buzón de peticiones del equipo con sus hooks y los comandos de envío (meta 005, fase 1)»
- Fase 2: «Añade el agente de consulta y su skill de peticiones (meta 005, fase 2)»
- Fase 3: «Escribe la guía del equipo EQUIPO.md (meta 005, fase 3)»
- Fase 4: «Avisa en dirección de las peticiones pendientes (meta 005, fase 4)»
- Fase 5: «Cierra la meta 005 · Agente de consulta para el equipo y buzón de peticiones»
