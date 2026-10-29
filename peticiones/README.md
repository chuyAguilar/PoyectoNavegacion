# peticiones/ — el buzón del equipo

Aquí dejan los compañeros del equipo lo que le piden al proyecto: un archivo por petición. Es la única carpeta del repo en la que alguien que no es el autor hace commit y push, y solo de archivos nuevos (ADR-034; `docs/constitution.md`, principio 1). Todo lo demás (código, docs, specs, configuración) lo cambia el autor.

## El flujo

1. **Preguntas.** En tu clon abres el agente `consulta` (`claude --agent consulta`) y le preguntas lo que quieras del proyecto. Si de la charla sale una propuesta, o le pides un cambio, él no lo hace: lo convierte en petición con su skill `peticion`.
2. **La petición se escribe.** La skill te hace dos o tres preguntas (qué, para qué, qué urgencia le ves), busca si ya existe algo parecido (`docs/BACKLOG.md`, esta carpeta, `specs/`) y te lo dice, y escribe el archivo desde `_plantilla.md`.
3. **La envías tú.** La skill te da, uno por uno, los cinco comandos de «Cómo se envía» con el nombre de tu archivo ya puesto. Los ejecutas tú, en una terminal aparte o con `!` delante en la conversación; ningún agente hace commit ni push.
4. **El autor decide.** Al arrancar, `direccion` le muestra al autor las peticiones con `Decisión: pendiente`. El autor decide y `direccion` llena el bloque «Decisión del autor» del archivo. Si se acepta, nace una entrada del BACKLOG (`B-nn`) o un spec (`specs/NNN-nombre/`) y la petición queda enlazada a ellos.

## Los estados

Los lleva la línea `Decisión: …` del bloque «Decisión del autor», que solo escribe `direccion`:

- `Decisión: pendiente`: recién enviada; el autor no la ha visto o no ha decidido.
- `Decisión: aceptada → B-nn` o `Decisión: aceptada → meta NNN`: entra al BACKLOG o se convierte en meta; se enlaza en los dos sentidos.
- `Decisión: rechazada`: con el motivo y la fecha en las líneas de abajo.

## El nombre del archivo

`AAAA-MM-DD-<usuario>-<tema>.md`, por ejemplo `2026-10-28-kike-regla-de-escala.md`.

- `AAAA-MM-DD` es la fecha de hoy.
- `<usuario>` sale de tu `git config user.name`, en minúsculas, sin tildes ni espacios.
- `<tema>` son dos o tres palabras en minúsculas, unidas con `-`, sin tildes, sin `ñ` y sin espacios.

Así dos compañeros no chocan nunca en el mismo nombre, y el `git pull` del paso 3 no puede dar conflicto.

## Una petición enviada no se edita

Ni se modifica ni se borra: el hook la rechaza. Si quieres corregir o ampliar una, escribes otra nueva que la cite por su nombre de archivo. El único que escribe en una petición enviada es `direccion`, en el bloque «Decisión del autor».

## Cómo se envía

Los comandos valen igual en PowerShell y en Git Bash, en una terminal abierta en la carpeta del repo o con `!` delante en la conversación de `consulta`. Van con rutas con `/`, comillas dobles y sin el separador `--`, sin `&&` ni `$`, ni `\`. El mensaje del commit va sin tildes a propósito («Peticion: …»), para que se lea bien en cualquier consola.

### Antes del primer comando (lo comprueba `consulta`, con git de lectura)

- `git config --get core.hooksPath` tiene que decir `equipo/hooks`. Si no, primero `git config core.hooksPath equipo/hooks`: activa los hooks del proyecto en tu copia, que son los que revisan que el envío lleve solo peticiones nuevas. Sin esto nada filtra el envío.
- `git fetch origin` y `git log origin/main..HEAD --oneline` tiene que salir vacío: no hay commits tuyos sin empujar. Si los hay, `consulta` te explica cuáles son y que el push los llevaría; si alguno no es una petición nueva, el hook `pre-push` rechazará el envío entero: avisa al autor antes de seguir. No se propone `reset` ni nada que los borre.
- `git ls-tree --name-only origin/main peticiones/<archivo>.md` tiene que salir vacío: el nombre no está usado en `origin`. Si lo está, se cambia el nombre antes de dar los comandos.
- `git status --porcelain`: si hay cambios tuyos fuera de `peticiones/`, `consulta` te explica qué son y que el envío no los toca.

### Los cinco comandos, uno por vez

Pegas cada uno y `consulta` lee la salida antes de darte el siguiente. `<archivo>`, `<tema>` y `<usuario>` ya van sustituidos cuando te los da.

1. `git add peticiones/<archivo>.md` — solo tu petición entra al índice.
2. `git commit -m "Peticion: <tema> (<usuario>)" peticiones/<archivo>.md` — con la ruta en el comando entra solo ese archivo, aunque tengas otras cosas en el índice. El hook `pre-commit` lo revisa.
3. `git pull --rebase --autostash origin main` — trae lo nuevo del repo; tus cambios locales se guardan y se reponen solos.
4. `git push origin HEAD:main` — el hook `pre-push` lo revisa. La primera vez abre el navegador para entrar en GitHub.
5. `git log origin/main --oneline -1 peticiones/<archivo>.md` — si sale tu commit, llegó (el push pone al día `origin/main` en tu copia). `consulta` puede confirmarlo con `git fetch origin` y el mismo `git log`.

### Si uno falla

Nunca `reset --hard`, `checkout --`, `clean`, `--force` ni `--no-verify`: ninguno hace falta y los cuatro primeros pueden perder trabajo.

| Comando | Qué sale | Qué se hace |
|---|---|---|
| 1 | «did not match any files» o que la ruta no existe | El nombre está mal escrito; `consulta` te da la ruta exacta y se repite el 1. |
| 2 | Lo rechaza `pre-commit` | Su mensaje dice qué archivo y por qué. Si es la petición misma (le falta `Decisión: pendiente`), `consulta` la corrige y se repiten 1 y 2. Si es otro archivo, ese no entra: se revisa el comando 2, que debe llevar solo la ruta de tu petición. |
| 2 | «nothing to commit» | Ya estaba hecho. Se mira `git log origin/main..HEAD --oneline` y se sigue en el 3. |
| 3 | «CONFLICT» | `git rebase --abort` deja tu copia como antes del 3. Avisa al autor. Con la comprobación del nombre no debería pasar. |
| 3 | No pudo reponer tus cambios («autostash») | Quedan guardados en `git stash list`: no se pierden. Avisa al autor antes de tocar nada. |
| 4 | «non-fast-forward», «fetch first» o «rejected» | Alguien empujó entre medias. Se repiten 3 y 4, hasta tres veces. |
| 4 | Lo rechaza `pre-push` | Su mensaje dice qué commit trae algo que no es una petición nueva. Avisa al autor. |
| 4 | «403», «permission denied», «Repository not found» | No eres colaborador del repo o entraste en GitHub con otra cuenta. Avisa al autor. |
| 5 | No sale nada | `git fetch origin` y se repite el 5. Si sigue sin salir, el push no llegó: se vuelve al 4. |

## Qué pasa después

El autor ve tu petición la próxima vez que abre `direccion` y decide. Verás la decisión en el bloque «Decisión del autor» de tu archivo después de un `git pull --rebase --autostash origin main`, y, si se aceptó, la entrada del BACKLOG o el spec que la enlaza.
