Plan autorizado por el autor el 2026-10-19

# Tareas — Meta 001 · limpieza y orden del repo

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

- [x] **Fase 1 · suite y replay (B02).** Criterio: el del plan. Número obtenido: 110 pruebas, 88 pasan y 22 `xfail` (el plan esperaba 112/101/11: los 3 archivos de mayo son 70 pruebas, no 72, y las desfasadas son 22, no 11; B17), 0 fallos, 0 `XPASS`, 0 saltadas, ~6 s; replay 302 frames, 275 con pose, mediana 4 markers, diferencia 0.0 mm y 0.0° en dos corridas; recorte 54 892 B; selftest rc 0 en ~3 s. Fecha: 2026-10-19. Commit: —.
- [ ] **Fase 2 · respaldo de la punta (B03).** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 3 · movimientos (B01, B05).** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 4 · textos (B04, B06).** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
