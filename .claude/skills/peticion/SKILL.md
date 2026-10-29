---
name: peticion
description: La skill de peticiones del agente `consulta` (ADR-034). Se usa cuando de una duda sale una propuesta, o cuando el compañero pide un cambio (en el código, los docs, el panel, Slicer o la configuración): en vez de hacerlo, escribe un archivo nuevo en `peticiones/` desde la plantilla y guía al compañero, un comando por vez, para que él lo envíe. No la usan los agentes del autor.
argument-hint: "[tema]"
---

Convierte en petición lo que el compañero quiere que cambie, y guíalo para que él la envíe. El tema, si lo hay: $ARGUMENTS.

Tú solo escribes el archivo de la petición. Los comandos de git los ejecuta el compañero: tú se los das y lees su salida. Todo lo que cuentas del envío sale de `peticiones/README.md`, que lee antes de empezar.

1. **Completa la petición.** Hacen falta tres cosas: qué se pide, para qué (qué problema resuelve o qué permitiría), y qué urgencia le ve el compañero (baja, media o alta) y por qué; y, si lo pide de parte de alguien (el doctor, el jefe), de quién. Lo que el compañero ya dijo no se vuelve a preguntar. Lo que falte, en dos o tres preguntas cortas como mucho, todas en un mensaje, y esperas la respuesta. Si te dice que no quiere más preguntas, completas con lo que hay y lo marcas «(no lo dijo)».
2. **Busca si ya existe.** En `docs/BACKLOG.md` (índice y entrada), en `peticiones/` (las otras peticiones) y en `specs/` (las metas). Si hay algo igual o muy cercano, se lo dices con su fuente y le propones citarlo en la petición en vez de duplicarlo; la escribe igual si quiere.
3. **El nombre del archivo:** `AAAA-MM-DD-<usuario>-<tema>.md`, con la fecha de hoy.
   - `<usuario>`: de `git config --get user.name`, en minúsculas, sin tildes, sin `ñ` y sin espacios (los espacios, fuera; «Kike Pérez» da `kikeperez`). Si sale vacío, se lo preguntas.
   - `<tema>`: dos o tres palabras en minúsculas unidas con `-`, sin tildes ni `ñ` («puerto-slicer», «regla-de-escala»).
   - Si ese nombre ya existe en `peticiones/`, añade `-2` al tema.
4. **Escribe el archivo** en `peticiones/` copiando `peticiones/_plantilla.md` y llenando cada `<…>`. La primera línea es la nota visible, con su nombre, su usuario y la fecha: «> Petición escrita por el agente de consulta para <nombre> (<usuario>), el AAAA-MM-DD.». El bloque «Decisión del autor» queda tal cual, con la línea `Decisión: pendiente`: no lo llenas tú. Sin datos de paciente (principio 5) y sin decir que el sistema está «listo para cirugía» (principio 4). No escribes ningún otro archivo.
5. **Enséñale el texto** de la petición y dile que, si quiere cambiar algo, lo diga antes de enviarla: después de enviada ya no se edita (se escribe otra que la cite).
6. **Las comprobaciones previas** de «Cómo se envía», con git de lectura y sin cambiar nada:
   - `git config --get core.hooksPath` tiene que decir `equipo/hooks`. Si no, antes que nada le das `git config core.hooksPath equipo/hooks`, le explicas en una frase que activa los hooks del proyecto en su copia (son los que comprueban que el envío lleve solo peticiones nuevas), esperas su salida y lo vuelves a comprobar. Sin esto no se da el comando 1.
   - `git fetch origin` y `git --no-optional-locks log origin/main..HEAD --oneline`: tiene que salir vacío. Si hay commits, le explicas cuáles son y que el push los llevaría; si alguno no es una petición nueva, el hook `pre-push` rechazará el envío entero: que avise al autor antes de seguir. No propones `reset` ni nada que los borre.
   - `git --no-optional-locks ls-tree --name-only origin/main peticiones/<archivo>.md`: tiene que salir vacío. Si sale el nombre, cambias el nombre del archivo (paso 3) antes de dar los comandos.
   - `git --no-optional-locks status --porcelain`: si hay cambios fuera de `peticiones/`, le dices qué son y que el envío no los toca.
7. **Los cinco comandos, uno por vez.** Pregúntale dónde los va a ejecutar, si no lo dijo: en una terminal aparte (PowerShell o Git Bash, abierta en la carpeta del repo) o aquí mismo con `!` delante. Los comandos son los mismos en los dos sitios. Le das solo el comando 1, con el nombre de su archivo, su tema y su usuario ya puestos, y esperas. Con `!` ves la salida en la conversación; en la terminal le pides que te la pegue. Lees la salida y, si salió bien, le das el siguiente. Nunca le das los cinco de golpe.
   1. `git add peticiones/<archivo>.md`
   2. `git commit -m "Peticion: <tema> (<usuario>)" peticiones/<archivo>.md`
   3. `git pull --rebase --autostash origin main`
   4. `git push origin HEAD:main`
   5. `git log origin/main --oneline -1 peticiones/<archivo>.md`

   El mensaje del commit va sin tildes («Peticion»), a propósito. Los comandos van tal cual, sin `--`, sin `&&` y con `/`: valen igual en PowerShell y en Git Bash. Al dar el 4, le avisas de que la primera vez se abre el navegador para entrar en GitHub.
8. **Si uno falla,** sigues la tabla «Si uno falla» de `peticiones/README.md` al pie de la letra: le dices qué pasó en una frase y qué comando sigue. Nunca propones `reset --hard`, `checkout --`, `clean`, `--force` ni `--no-verify`. Cuando la tabla dice «avisa al autor», paras ahí y se lo dices.
9. **Termina** cuando la salida del 5 muestra su commit: le dices que llegó, que el autor la verá la próxima vez que abra `direccion`, y que la decisión aparecerá en el bloque «Decisión del autor» de su archivo después de un `git pull --rebase --autostash origin main`.
