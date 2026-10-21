---
name: fase
description: Implementa solo la fase n de tasks.md del spec activo, con la suite en verde, marca su casilla con el número obtenido y devuelve el resumen de seis líneas. La invoca el agente de desarrollo cuando la dirección lo lanza con «/fase n».
argument-hint: "<n> [implementa|verifica]"
---

Implementa la fase $ARGUMENTS del spec activo (el que nombra `memory.md`), y solo esa.

**Los dos tiempos (ADR-022).** El argumento es «n», «n implementa» o «n verifica».
- **«n implementa»:** los pasos 1 a 4, más las pruebas de la fase (no la suite completa) y el criterio medido. Deja una nota en `Claude outputs/fases/<NNN>/<fase>-implementa.md` con lo hecho, el número obtenido y lo que falta verificar, y devuelve «Implementada: criterio y número» o «Parado: por qué». No marcas la casilla ni haces el cierre.
- **«n verifica»:** partes del árbol que dejó «implementa»: lee esa nota y el `git diff`. Haces los pasos 5 a 8, con la suite completa dos veces y la equivalencia (replay). Un arreglo pequeño lo haces tú; si un fallo pide diseño, no lo tocas: devuelve «Parado: falla X».
- **Solo «n»:** todos los pasos.

1. **La marca.** La primera línea de `tasks.md` tiene que decir «Plan autorizado por el autor el AAAA-MM-DD». Si no lo dice, no hagas nada: devuelve «Parado: el plan no está autorizado».
2. **La casilla.** Busca en `tasks.md` la de la fase $ARGUMENTS.
   Si no existe o ya está marcada, dilo y para.
   Si la fase anterior está marcada pero su commit no está en git (`git --no-optional-locks log --oneline -10`, desde PowerShell), dilo y para: una fase empieza después del commit de la anterior. Si está en git y a su casilla le falta, pon el commit.
3. **Lo que se lee.** De `plan.md`, lo de esta fase; `clarify.md`; y el código que toca.
4. **La implementación.** Solo lo de esta fase.
   Lo que encuentres y no sea de ella va a `docs/BACKLOG.md` en el momento. Si es de prioridad alta, devuelve «Parado: …» antes de seguir.
5. **La verificación.**
   - Cada `.py` tocado: `py_compile` y conteo de líneas contra el original (principio 9).
   - La suite en verde, con tiempo límite y con su tiempo: `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q` por Bash. Si `memory.md` dice que la suite está rota y esta fase no es la que la arregla, dilo en el reporte con su salida.
   - El criterio de la fase, medido, con su número.
   - Si la fase toca la cadena (principio 6), el replay que nombra `memory.md`, si ya existe, y el protocolo en vivo para el autor.
6. **La casilla, marcada:** `[x]`, el número obtenido y la fecha.
7. **El cierre:** lo de la skill `cerrar-fase` (`.claude/skills/cerrar-fase/SKILL.md`).
8. **El reporte,** con el formato de `CLAUDE.md` §6, completo en `Claude outputs/fases/<NNN>/<fase>.md` (fuera de git), con el título del commit y el `git add` exacto (rutas desde la raíz, solo lo de la fase).
   Lo que devuelves, y lo único que la dirección verá, es el resumen de seis líneas como mucho: «Fase N: hecha» (o «parcial: qué falta»); el criterio clave con su número; la suite (cuántas, cuánto) y el «no cambió»; lo que fue al BACKLOG, si hay; el título del commit y el `git add`; «Reporte: `Claude outputs/fases/<NNN>/<fase>.md`». No hagas commit.
   Si algo te para antes, devuelve una sola línea, «Parado: por qué», y termina: no esperes respuestas.
