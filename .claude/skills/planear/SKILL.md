---
name: planear
description: Escribe plan.md del spec que se le indica, o del activo, sin código, y espera la autorización del autor. La invoca el agente de planificación cuando la dirección lo lanza con «/planear NNN-nombre».
argument-hint: "[NNN-nombre]"
---

Planea la meta. No escribas código ni toques `codigo/`, `docs/` ni `memory.md`.

1. **La carpeta.** Es `specs/$ARGUMENTS/`; si no se dio, la del spec activo que nombra `memory.md`. Si no existe o no tiene `spec.md`, dilo y para.
2. **Lo que se lee.** Completos, `spec.md` y, si existen, `clarify.md` y `tasks.md`.
   De `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/BACKLOG.md` y `docs/PRUEBAS.md`, las secciones que la meta toca, buscadas por su índice. Las trampas de `docs/CONTEXT.md` §4. Y el código de `codigo/iter4/` que va a cambiar, con lo que lo importa o lo nombra (grep).
3. **`plan.md`,** con las secciones de `specs/_plantilla/plan.md`:
   - lo leído, con el commit de HEAD (`git --no-optional-locks log --oneline -1`);
   - los archivos que crearás, modificarás o moverás;
   - las funciones y clases nuevas o cambiadas, con su firma;
   - las fases, cada una con su criterio de cierre medible (principio 3) y cómo se mide: suite, replay o sesión en vivo con el autor;
   - si una fase toca la cadena tracker → OpenIGTLink → Slicer, cómo se verifica que sigue igual (principio 6);
   - lo que irá a `docs/BACKLOG.md`, con su prioridad;
   - los ADR que propones, si hay una decisión no trivial (no los escribas);
   - las preguntas abiertas;
   - un título de commit por fase.
4. **`clarify.md`:** copia al final las preguntas abiertas, una por bloque, con el formato de `specs/_plantilla/clarify.md` y «Respuesta del autor: pendiente». Si no existe, créalo desde la plantilla.
5. **`tasks.md`:** desde la plantilla, con una casilla por fase. La primera línea dice «Plan pendiente de autorización.».
   Esa línea pasa a «Plan autorizado por el autor el AAAA-MM-DD» solo cuando el autor autoriza: la cambia él, o la dirección cuando él se lo dice en el chat, con su fecha.
6. **Si `plan.md` ya existe,** no lo borres: aplica lo que cambia y dilo en lo que devuelves.
7. **Las líneas:** ninguna de `plan.md`, `clarify.md` ni `tasks.md` pasa de 2 000 caracteres.
8. **Al terminar,** di dónde está el plan, cuántos bytes mide, cuáles son las preguntas y los títulos de commit, y para. No implementes nada.
