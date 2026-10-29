# Meta 005 — Agente de consulta para el equipo y buzón de peticiones

## Por qué

Hoy solo el autor trabaja en PoyectoNavegacion, con `direccion` y sus subagentes. El jefe y los compañeros necesitan saber qué se hace, qué sigue y cómo funciona, pero no se mueven bien en consola, git ni Claude Code. Lo que necesitan ya está escrito en el repo (`memory.md`, `docs/CONTEXT.md`, `docs/ARCHITECTURE.md` §9 «Cómo funciona el tracker», `docs/DECISIONS.md`, `docs/BACKLOG.md`), pero no saben llegar a ello.

Viene del autor (2026-10-27; borrador en su plan «Agente de consulta para el equipo y buzón de peticiones»). La pidió antes que el grafo de factores óptico-inercial, que pasa a ser la meta 006 y sigue esperando el GitHub MCP. Ahora es buen momento: la meta 004 dejó el «cómo funciona» escrito en llano, y no hay ninguna fase abierta.

## Qué se construye

Cada compañero clona el repo en su máquina y abre un agente propio, `consulta`, que se pone al día solo, responde en español llano y, si le piden algo, no lo implementa: lo deja como petición en un `.md`. Al arrancar, `direccion` avisa al autor de las peticiones nuevas y el autor decide.

1. **La regla nueva (ADR que enmienda el principio 1; principio 10).** Los compañeros pueden hacer commit y push solo de archivos nuevos en `peticiones/`; todo lo demás sigue siendo del autor, y ningún agente ejecuta `git commit` ni `git push` (la negación de `settings.json` se queda). Decisión del autor del 2026-10-27: son los compañeros quienes hacen su commit y su push, guiados por el agente.
2. **El buzón `peticiones/`.** Un `README.md` con el flujo y los estados; una plantilla; un archivo por petición, con un nombre que evite conflictos entre compañeros (p. ej. `AAAA-MM-DD-<usuario>-<tema>.md`). La plantilla recoge quién, cuándo, de parte de quién, qué se pide, para qué, la urgencia que percibe, lo que el agente encontró relacionado (meta, BACKLOG, ADR) y un bloque «Decisión del autor» (pendiente / aceptada → B-nn o meta NNN / rechazada, con motivo y fecha) que solo llena `direccion`.
3. **El agente `consulta`** (`.claude/agents/consulta.md`). Al arrancar trae lo último del repo; lee `memory.md`, `docs/CONTEXT.md`, los índices de `ARCHITECTURE`, `DECISIONS`, `BACKLOG` y `PRUEBAS`, y el `git log` reciente. Responde en llano, explicando la jerga, citando archivo y sección, y diciendo cuándo algo no está documentado. Nunca modifica nada fuera de `peticiones/`: una orden de cambiar código, docs o configuración la convierte en petición. Al recibir una petición hace pocas preguntas para completarla, busca si ya existe (BACKLOG, peticiones, specs) y lo dice, escribe el archivo y guía el envío un comando por vez, esperando el resultado del compañero, hasta comprobar que llegó a `origin`. Si la copia local está sucia, explica qué pasa y cómo dejarla limpia sin perder peticiones sin enviar.
4. **Las barandillas en la máquina del compañero.** Un hook de pre-commit versionado que rechaza, con un mensaje en español, un commit con algo fuera de `peticiones/` o que modifica o borra una petición existente; se activa solo en sus máquinas. Permisos locales de Claude Code que hacen de `consulta` el agente por defecto y le niegan escribir fuera de `peticiones/`. Las negaciones de `settings.json` (commit, push, datos de paciente) siguen valiendo.
5. **Instalar y usar sin saber de consola.** Un instalador de Windows que comprueba lo necesario, clona si falta, activa el hook y escribe los permisos locales; un acceso de doble clic que abre `consulta`; y `docs/EQUIPO.md`, una guía de una página: instalar una vez, abrir, preguntas de ejemplo, cómo pedir algo y qué pasa después con la petición.
6. **El aviso en `direccion`.** Al arrancar, después de leer `memory.md`, `direccion` mira en `origin` si hay peticiones nuevas y lista las que tienen «Decisión: pendiente» antes de cualquier otra cosa, y le recuerda al autor hacer `git pull` si hay commits nuevos. Cuando el autor decide, `direccion` llena el bloque de la petición y, si se acepta, crea la entrada del BACKLOG o el spec y los enlaza. `memory.md` lleva una línea «Peticiones pendientes: N». Cambian `.claude/agents/direccion.md`, `CLAUDE.md` §1 y §4 (cinco papeles) y los permisos de `settings.json` que haga falta.
7. **El riesgo conocido.** El repo es público y versiona el DICOM (ADR-019; decisión del autor de mantenerlo, 2026-10-27). Dar acceso de escritura a más personas no lo cambia, pero se anota como entrada del BACKLOG con la prioridad que diga el autor.

## Criterio de cierre

- **El hook filtra bien:** en un clon temporal en el scratchpad, sin push, un commit con un archivo fuera de `peticiones/` se rechaza, uno que modifica una petición existente se rechaza y uno con una petición nueva pasa. 3 de 3.
- **`consulta` responde con fuente y no toca nada:** en un clon limpio, `claude --agent consulta` se pone al día y contesta 5 preguntas guion (qué se está haciendo, qué sigue, cómo sale la pose de 4 esquinas, qué es el BACKLOG, por qué se tomó un ADR concreto), cada una con su archivo y sección correctos: 5 de 5. A una orden de editar `codigo/` se niega y la convierte en petición; `git status` muestra solo `peticiones/` tocado.
- **El circuito completo:** una petición de prueba empujada desde otro clon aparece en la lista de `direccion` al arrancar, y se cierra como «rechazada: prueba».
- **Un compañero real, en vivo con el autor:** instala desde cero en su máquina, hace una pregunta y envía una petición; el autor la ve en `direccion`. Se anotan los minutos de la instalación, cuántas veces hubo que ayudarle (la meta pide que envíe la petición sin ayuda) y la petición en `git log origin/main`.
- La suite igual que al cerrar la meta 004: 618 de 618, con su tiempo; `codigo/` no cambia.
- Ninguna línea de `docs/`, `memory.md` o `specs/` pasa de 2 000 caracteres.

## Lo que no se toca

- `codigo/` entero, y con él la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6): su `git diff` sale vacío; la suite y el replay de Marker0 lo comprueban.
- Ningún agente ejecuta `git commit` ni `git push`, tampoco `consulta`: guía al compañero, que los ejecuta él. Las negaciones de `settings.json` no se relajan.
- Los datos de paciente (principio 5): `consulta` tampoco los lee, y ninguna petición ni la guía los nombra como algo que leer. Mover el DICOM o hacer el repo privado no entra en esta meta.
- El principio 4: ni `consulta` ni la guía llaman al sistema «listo para cirugía».
- La meta 006 · Grafo de factores óptico-inercial y su pendiente del GitHub MCP quedan como están.

## Preguntas que el plan tiene que contestar

- **Lo vigente de Claude Code, por Context7 o su documentación:** si un archivo de settings puede fijar el agente por defecto (la clave que usa el borrador, `agent`) o si basta el acceso directo con `claude --agent consulta`; la sintaxis de permisos por ruta que niega `Write` y `Edit` fuera de `peticiones/**`; y si `settings.local.json` es el sitio correcto en la máquina del compañero (el autor ya tiene el suyo y no se toca).
- **Qué impide de verdad que un compañero empuje otra cosa:** el hook local se puede saltar (`--no-verify`) y un colaborador con escritura puede empujar cualquier archivo. Qué ofrece GitHub del lado del servidor para un repo personal y público (reglas por ruta, protección de rama, CODEOWNERS) y qué cuesta; si no hay nada viable, decirlo y anotarlo como riesgo.
- **Los comandos de envío:** la secuencia exacta (estado, añadir, commit, traer con rebase, empujar, comprobar), qué hace el agente si el rebase o el push fallan, y cómo trata una copia local con cambios que no son peticiones.
- **El modelo de `consulta`:** el borrador dice sonnet por coste en máquinas ajenas; depende de quién paga (pregunta abierta para el autor).
- **Cómo se prueba `consulta` sin una persona:** cómo se corren las 5 preguntas guion en un clon temporal y se comprueban las fuentes, y si cabe una prueba automática del hook en la suite o en un script aparte (sin tocar `codigo/` si no hace falta).
- **El instalador:** qué comprueba (git, Claude Code; si `gh` hace falta: en la máquina del autor no está), cómo se autentica el compañero en GitHub, y qué hace si algo falta.
- **Las fases y su peso** (ADR-022). El borrador propone cuatro: ADR, principio 1, buzón y hook; `consulta`, permisos, guía e instalador; el aviso en `direccion`; la prueba con un compañero real.
- **Para el autor (van a `clarify.md`):** cuántos compañeros y quiénes tienen ya cuenta de GitHub (hay que invitarlos como colaboradores); quién paga Claude Code en sus máquinas; si el jefe usa también el agente o recibe un resumen periódico (p. ej. un `docs/ESTADO.md` que `direccion` actualice al cerrar cada meta; si no se pide ahora, al BACKLOG); la prioridad de la entrada del BACKLOG del repo público con el DICOM.
