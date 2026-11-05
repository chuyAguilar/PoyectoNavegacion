Plan autorizado por el autor el 2026-11-05

# Tareas — Meta 006 · Grafo de factores óptico-inercial (primero, las dos cámaras)

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.
Rehecho el 2026-11-05 para «la Jetson detecta, el PC fusiona» (P22). Las fases 3 a 6 se replanean con los números de las fases 1 y 2 antes de empezar la 3, y el autor las autoriza otra vez.

- [x] **Fase 1 · Verlo: el experimento fuera de línea sobre la grabación de la Jetson, parte A · Los números sin gtsam** (pesada). Criterio: el del plan. Número obtenido: la corrida real (`python -m fusion.experiment`, código 1 por S4) en 180 s y dos corridas idénticas byte a byte; suite 1118 pasan, 10 saltadas, 0 fallan (135.1 y 132.1 s); replay de Marker0 gs1 y gs2 8/8, selftest del panel OK, la cadena sin tocar. Resultado: extrínsecos 19.5 mm / 5.82° frente a < 0.5 mm / 0.2° (no cumple, B94); fusión −31.9 % (`numpy_pose`) y −63.1 % (`numpy_reproj`). Fecha: 2026-11-05. Commit: —.
- [ ] **Fase 1 · Verlo, parte B · El grafo con GTSAM** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 2 · Los extrínsecos por tablero, independientes de Marker0** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 3 · La Jetson envía al PC** (pesada; toca la cadena; se replanea antes). Criterio: el del replan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 4 · El fusionador en el PC** (pesada; toca la cadena; se replanea antes). Criterio: el del replan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · La fusión en vivo con Slicer** (ligera). Criterio: el del replan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5b · Extrínsecos sobre la estructura del autor** (ligera; cuando llegue). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 6 · Cierre de la meta** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
