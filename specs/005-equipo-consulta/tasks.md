Plan autorizado por el autor el 2026-10-28

# Tareas — Meta 005 · Agente de consulta para el equipo y buzón de peticiones

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

Antes de la fase 1, la dirección escribe ADR-034 y la enmienda del principio 1 (plan, «ADR que se proponen»).

- [x] **Fase 1 · El buzón `peticiones/` y los hooks** (pesada). Criterio: el del plan (8 de 8, 3 de 3, 3 de 3, 0 errores de sintaxis y los cinco comandos sin `--`, `&&`, `$` ni `\`; 7 de 7 en vivo, en PowerShell y en Git Bash). Número obtenido: agente 24 de 24 en 3 s (8/8, 3/3, 3/3, 4/4 sintaxis, 6/6 comandos); suite 618 de 618 (37.1 y 31.7 s); replay 8 de 8; `codigo/` sin cambios. En vivo (7 de 7): pendiente del autor. Fecha: 2026-10-28. Commit: `bc328b2`.
- [x] **Fase 2 · El agente `consulta` y su skill de peticiones** (ligera). Criterio: el del plan (5 de 5 del guion; solo `peticiones/` tocado y sin `git add`; el aviso del hook sin activar; en vivo, 2 de 2 llegadas, con `!` y en terminal aparte). Número obtenido: `probar_consulta.ps1` 11 de 11 (preguntas 5 de 5; orden con hooks 3 de 3; orden sin `core.hooksPath` 3 de 3), 7 llamadas a `claude -p` con sonnet, USD 0.96 y 605 s en total; suite 618 de 618 (33.0 y 33.8 s); replay 8 de 8; `codigo/` sin cambios. En vivo (2 de 2 llegadas): pendiente del autor. Fecha: 2026-10-28. Commit: `ae1e7ad`.
- [x] **Fase 3 · La guía `docs/EQUIPO.md` y la instalación guiada** (ligera). Criterio: el del plan (N de N pasos sin nada que no esté escrito; minutos y MB del clon). Número obtenido: `docs/EQUIPO.md` con 10 pasos de instalación (N = 10), el diálogo de confianza en el paso 10, 0 líneas de más de 2 000 caracteres; clon estimado en ~700 MB de descarga y ~1.3 GB en disco (árbol de HEAD 657 MB); suite 618 de 618 (32.9 s de pytest; 35.5 s de reloj en la otra corrida); replay 8 de 8; `codigo/` sin cambios. En vivo (pasos sin nada que no esté escrito, de 10; minutos totales y del clon; MB): pendiente del autor. Fecha: 2026-10-28. Commit: —.
- [ ] **Fase 4 · El aviso de peticiones en `direccion` y el circuito completo** (ligera). Criterio: el del plan (0 pendientes en el árbol; el circuito en vivo). Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · Un compañero real instala, pregunta y envía una petición** (ligera). Criterio: el del plan (minutos, ayudas en el envío, la petición en `origin/main`). Número obtenido: —. Fecha: —. Commit: —.
