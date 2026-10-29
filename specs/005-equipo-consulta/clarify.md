# Aclaraciones — Meta 005 · Agente de consulta para el equipo y buzón de peticiones

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

## P1 · Quiénes son los compañeros

- **Opciones:** cuántos, sus usuarios de GitHub (hay que invitarlos como colaboradores del repo) y si son del equipo médico. Si alguno no lo es, ADR-019 pide reabrir la decisión de mantener versionados los datos de paciente.
- **Respuesta del autor:** tres compañeros: Kike, Armando y el doctor Milton (el autor es Chuy). Los tres son del equipo médico (respuesta del 2026-10-28; encaja con ADR-019 y con el clon completo de P6). Sus usuarios de GitHub, pendientes: el autor los pasa antes de la fase 5.
- **Fecha:** 2026-10-28

## P2 · Quién paga Claude Code en sus máquinas y con qué modelo va `consulta`

- **Opciones:** (a) sonnet, `effort: medium` (propuesto: responde bien lecturas y guía comandos, coste bajo en máquinas ajenas); (b) opus (mejores respuestas, más caro); (c) haiku (lo más barato; riesgo de citar mal la fuente). Y quién paga: cuenta de cada compañero, o la del autor/equipo.
- **Respuesta del autor:** sonnet. Paga la cuenta el doctor Milton (respuesta del 2026-10-28).
- **Fecha:** 2026-10-27

## P3 · El jefe: agente propio o resumen periódico

- **Opciones:** (a) usa `consulta` como los demás y el resumen va al BACKLOG, baja (propuesto); (b) entra en esta meta un `docs/ESTADO.md` que `direccion` actualiza al cerrar cada meta (una fase ligera más); (c) las dos cosas.
- **Respuesta del autor:** (a) el jefe usa `consulta` como los demás; el resumen periódico (`docs/ESTADO.md`) va al BACKLOG, baja.
- **Fecha:** 2026-10-27

## P4 · Prioridad de la entrada del BACKLOG del repo público con el DICOM

- **Opciones:** (a) alta (propuesta: dato de paciente expuesto en un repo público, y ahora con más personas con escritura); (b) media; (c) baja. Mover el DICOM o hacer el repo privado no entra en esta meta en ningún caso.
- **Respuesta del autor:** (a) alta.
- **Fecha:** 2026-10-27

## P5 · Adónde empujan los compañeros

- **Opciones:** (a) a `main`, con un ruleset de GitHub que bloquea force-push y borrado de `main` (gratis en repo público; propuesto: es lo que pide el spec; que nada del servidor impida empujar fuera de `peticiones/` queda como riesgo en el BACKLOG); (b) a una rama propia (`peticiones/<usuario>`), con `main` restringido y el autor en la lista de excepción (impide de verdad; cada petición la fusiona el autor y `direccion` mira esas ramas); (c) a `main` más una GitHub Action que avisa cuando un push trae algo que no es una petición nueva (detecta, no impide). Los push rulesets por ruta no existen para un repo personal y público.
- **Respuesta del autor:** (a) a `main`, con un ruleset que bloquea force-push y borrado de `main`; lo de empujar fuera de `peticiones/` queda como riesgo en el BACKLOG.
- **Fecha:** 2026-10-27

## P6 · Cómo clonan los compañeros

- **Opciones:** (a) clon parcial y disperso que no baja ni pone en el árbol `herramientas/A/`, `documentos/VERONICA/`, `*.nrrd` ni `*.dcm` (propuesto: mucho más ligero que los ~700 MB y sin datos de paciente en máquinas ajenas; ADR-035); (b) clon completo (más simple; baja todo).
- **Respuesta del autor:** (b) clon completo. Sin clon parcial ni ADR-035.
- **Fecha:** 2026-10-27

## P7 · Cómo les llega el instalador

- **Opciones:** (a) una línea para pegar en PowerShell que lo baja del repo público: `irm https://raw.githubusercontent.com/chuyAguilar/PoyectoNavegacion/main/equipo/instalar.ps1 | iex` (propuesto: una sola copia, siempre al día); (b) el autor les manda `instalar.cmd` y `instalar.ps1` por correo o USB y hacen doble clic; (c) los bajan de la web de GitHub.
- **Respuesta del autor:** (c) los bajan de la web de GitHub.
- **Fecha:** 2026-10-27

## P8 · Dónde escribe el compañero los comandos de envío

- **Opciones:** (a) en una segunda ventana de PowerShell que abre el acceso directo en la carpeta del repo (propuesto: claro quién ejecuta qué); (b) dentro de Claude Code con `!` delante (más cómodo; la fase 2 tendría que comprobar que las negaciones de commit y push no lo paran y que no cuenta como acción del agente).
- **Respuesta del autor:** (a) en una segunda ventana de PowerShell en la carpeta del repo.
- **Fecha:** 2026-10-27

## P9 · Cuánto se limita a los compañeros (la dirección, tras leer el plan)

- **Opciones:** (a) restringirlos con los permisos de Claude Code (modo `dontAsk`, escribir solo en `peticiones/**`, hook `PreToolUse`), como proponía el plan; (b) libertad total en su máquina y el único seguro son los hooks de git versionados en el repo.
- **Respuesta del autor:** (b). Quiere que tengan libertad, incluso para abrir otros agentes sin el rol que se les da; su seguro son los hooks (`pre-commit` y `pre-push`), que son reglas del proyecto. No quiere tener que revocar permisos de GitHub a nadie después: si algo cambia, se cambian las reglas del proyecto. Fuera del plan: `dontAsk`, los `allow` limitados a `peticiones/**` y el hook `PreToolUse`. `settings.local.consulta.json` queda, si hace falta, solo para que `consulta` sea el agente por defecto.
- **Fecha:** 2026-10-28

## P10 · Cómo se hace una petición

- **Opciones:** (a) el agente escribe el archivo y guía al compañero comando por comando en otra ventana, como proponía el plan; (b) una skill de peticiones en `consulta`, parecida a las que usa el proyecto, que se usa en la propia conversación cuando de una duda sale una propuesta.
- **Respuesta del autor:** (b). La skill completa la petición, busca si ya existe (BACKLOG, peticiones, specs) y escribe el archivo con una nota visible de que la petición viene del agente de consulta (y de qué compañero), para que `direccion` la note y el autor la valore.
- **Fecha:** 2026-10-28

## P11 · Quién envía la petición (commit y push)

- **Opciones:** (a) el agente, por un script único (`equipo/enviar_peticion.ps1`) permitido en `settings.json`, con un ADR que cambia el principio 1 para los agentes; (b) el compañero, pegando una sola línea (ese mismo script) que le da la skill.
- **Respuesta del autor:** (b). Ningún agente hace commit ni push; el principio 1 no cambia para los agentes y la negación de `settings.json` se queda. Sigue haciendo falta el ADR que permite a los compañeros commit y push solo de peticiones nuevas. El plan propone dónde se pega la línea (en Claude Code con `!` o en PowerShell); esto revisa P8, que suponía guiarlo comando por comando.
- **Fecha:** 2026-10-28

## P12 · Aviso del lado de GitHub

- **Opciones:** (a) solo los hooks; (b) además, una GitHub Action que avisa cuando un push trae algo que no es una petición nueva (detecta, no impide).
- **Respuesta del autor:** (a) solo los hooks. Que se puedan saltar (`--no-verify`, push a mano) va al BACKLOG como riesgo.
- **Fecha:** 2026-10-28

## P13 · El instalador

- **Opciones:** (a) `equipo/instalar.ps1` con su `.cmd` de doble clic y su prueba, como proponía el plan; (b) sin instalador: el autor guía a cada compañero por consola con los pasos de `docs/EQUIPO.md` (instalar Git y Claude Code, clonar, `git config core.hooksPath`, abrir `claude --agent consulta`).
- **Respuesta del autor:** (b). Se quita el instalador; los pasos van en `docs/EQUIPO.md` con los comandos exactos. P7 deja de aplicar.
- **Fecha:** 2026-10-28

## P14 · Negarles a los agentes el script de envío en `settings.json`

- **Opciones:** (a) añadir `Bash(*enviar_peticion*)` y `PowerShell(*enviar_peticion*)` a `deny` (propuesto: sin ella, un agente que lanzara `equipo/enviar_peticion.ps1` estaría haciendo commit y push por un rodeo; no relaja nada y no alcanza al `!` del compañero, que no pasa por los permisos); (b) solo la instrucción en `consulta.md` y en la skill `peticion`.
- **Respuesta del autor:** sin script. Fuera `equipo/enviar_peticion.ps1`: la skill le da al compañero los comandos de git (añadir solo su petición, commit, traer con rebase, push, comprobar) para que los ejecute él. Como no hay script, no hay nada que negar en `settings.json`; la negación de commit y push a los agentes sigue como está.
- **Fecha:** 2026-10-28

## P15 · Dónde pega el compañero la línea de envío

- **Opciones:** (a) en la conversación de `consulta`, con `!` delante (propuesto: una sola ventana; `consulta` ve la salida y le confirma si llegó; con Git for Windows `!` corre en Git Bash y la línea, `powershell -NoProfile -ExecutionPolicy Bypass -File equipo/enviar_peticion.ps1 -Archivo peticiones/<archivo>.md`, vale igual en Bash y en PowerShell); (b) en una ventana de PowerShell aparte, en la carpeta del repo (lo que decía P8). La fase 2 mide la (a) y deja la (b) como respaldo en `docs/EQUIPO.md`.
- **Respuesta del autor:** los dos sitios valen (aclarado tras chocar con P14): en una terminal aparte (PowerShell o Git Bash en la carpeta del repo) o con `!` en la conversación de `consulta`. `docs/EQUIPO.md` explica las dos y cada compañero elige; los comandos tienen que servir igual en las dos.
- **Fecha:** 2026-10-28

## P16 · `consulta` como agente por defecto en la máquina del compañero

- **Opciones:** (a) no: `docs/EQUIPO.md` dice abrir siempre `claude --agent consulta` y explica, como opción, `{"agent": "consulta"}` en su `.claude/settings.local.json` (propuesto: argumentos explícitos, principio 7, y la libertad de P9); (b) un paso fijo de la instalación que escribe ese archivo.
- **Respuesta del autor:** no: se abre siempre con `claude --agent consulta`; `docs/EQUIPO.md` explica la opción de dejarlo por defecto.
- **Fecha:** 2026-10-28

## P17 · Las cuentas de Claude Code que paga el doctor Milton

- **Opciones:** (a) una cuenta por compañero, pagadas por el doctor Milton (propuesto: cada uno entra con la suya; si las condiciones de Anthropic permiten compartir una cuenta no lo verifiqué, lo confirma el autor); (b) una sola cuenta compartida. Cambia el paso de la cuenta en `docs/EQUIPO.md`.
- **Respuesta del autor:** fuera de esta meta: el autor lo ignora por ahora.
- **Fecha:** 2026-10-28
