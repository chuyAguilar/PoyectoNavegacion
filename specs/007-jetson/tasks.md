Plan autorizado por el autor el 2026-10-29

# Tareas — Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.
Ningún agente usa `ssh nav-jetson` hasta que la fase 2 esté cumplida y el autor haya aplicado las reglas de `settings.json` (plan, § «La barrera»).

- [x] **Fase 1 · El escaneo de la Jetson, solo lectura** (ligera). Criterio: el del plan. Número obtenido: P-1 con 12 de 12 secciones en 11 s (tope 180), 78 órdenes, 0 cortadas por tope, 7 fallidas y explicadas (ninguna es un fallo del escaneo), `find` vacío y los 9 puntos del criterio 3 reportados; `escanear.ps1` corregido (la variable `topes` pisaba `[int]$TopeS`) con 3 casos nuevos, 25 de 25. Fecha: 2026-10-29. Commit: —.
- [ ] **Fase 2 · La barrera de seguridad para los agentes** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 3 · El entorno en la Jetson** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 4 · La suite corre en Linux** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · La capa V4L2 y cada cámara en la Jetson** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 7 · Las dos cámaras a la vez en la Jetson** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 8 · El panel del PC lanza y para el tracker de la Jetson** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 9 · Cómo se trabaja con la Jetson y cierre de la meta** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
