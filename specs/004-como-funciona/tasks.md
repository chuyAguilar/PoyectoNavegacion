Plan autorizado por el autor el 2026-10-26

# Tareas — Meta 004 · Cómo funciona el tracker

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git. El detalle de cada fase cerrada está en su reporte (`Claude outputs/fases/004/`).

- [x] **Fase 1 · El mapa del proyecto, su imagen y su prueba (ligera).** §9.1 con 20 cajas y 0 referencias inexistentes; `docs/img/004/mapa_proyecto.svg` de 99 584 bytes, apaisado (P9; ADR-032); suite 572 de 572. El autor: «se lee bien y se entiende». 2026-10-26. Commit: `f3a2d4b`.
- [x] **Fase 2 · El ejemplo resuelto con un frame real (pesada).** En los 6 frames, esquinas = grabadas a 0.0 px y 4×4 = enviada = replay a 0.0 mm / 0.0°; escala de B55: cociente 1.2325, misma rotación; reproyección 0.053–0.204 px; `docs/img/004/` 134 428 bytes; suite 606 de 606. 2026-10-26. Commit: `533989a`.
- [x] **Fase 2b · «Verificar IDs y colocar la cámara» marca la cámara en verde y se quita «Probar cámara» (ligera; P10).** Selftest sin el botón; código 0 → verde con los fps, otro → rojo con el error; B29 cerrado; suite 611 de 611. En vivo: verde; 30 fps la primera corrida y 89.8 la segunda (B50, sin investigar). 2026-10-26. Commit: `54c48a7`.
- [x] **Fase 2c · «Comprobar escala con regla» sin congelarse y con vista previa fluida (ligera; P11).** Vista previa con Marker0 y sin tablero (peor caso): 245–257 → 1.6–1.8 ms por frame de hilo principal (objetivo ≤ 33 ms); durante la medida se repinta en cada pose (0.07–0.2 s); los números de escala no cambian; B58 nuevo; suite 618 de 618. 2026-10-26. Commit: `16e7f35`.
- [x] **Fase 3 · La explicación y el glosario (ligera).** §9.2 en 11 pasos, §9.4 con 32 términos y §9.5 con 35 filas de fuentes; referencias de §9 de 77 a 130, 0 inexistentes; 0 líneas > 2 000; Mermaid sin tocar; B59 nuevo; suite 618 de 618. 2026-10-26. Commit: `354afe4`.
- [x] **Fase 4 · Lectura con el autor y cierre de la meta (ligera).** 0 dudas abiertas en §9.2 y §9.4 (alcance de P12), confirmado por el autor; §9 sin cambios y la imagen del mapa sin reexportar; nada nuevo al BACKLOG; suite 618 de 618 (34.29 s), replay 0.0 mm / 0.0°, selftest OK, `git diff` de la cadena vacío desde `63bbdd8`. Detalle en `resultados.md`. 2026-10-26. Commit: —.
