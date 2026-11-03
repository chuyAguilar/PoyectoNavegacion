Plan autorizado por el autor el 2026-10-29

# Tareas — Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.
La fase 2 está cumplida y el autor aplicó las reglas de `settings.json` (2026-11-02): los agentes entran a la Jetson solo por `ssh nav-jetson <verbo>` (plan, § «La barrera»).

- [x] **Fase 1 · El escaneo de la Jetson, solo lectura** (ligera). Criterio: el del plan. Número obtenido: P-1 con 12 de 12 secciones en 11 s (tope 180), 78 órdenes, 0 cortadas por tope, 7 fallidas y explicadas (ninguna es un fallo del escaneo), `find` vacío y los 9 puntos del criterio 3 reportados; `escanear.ps1` corregido (la variable `topes` pisaba `[int]$TopeS`) con 3 casos nuevos, 25 de 25. Fecha: 2026-10-29. Commit: `e71dea4`.
- [x] **Fase 2 · La barrera de seguridad para los agentes** (pesada). Criterio: el del plan. Número obtenido en la Jetson (P-2 del autor, 2026-11-02, guardián 2): `--autocomprobar` «nav-guardian 2 (2026-11-02)»; sonda de `navagente` 0 privilegios en 28 comprobaciones; `probar_barrera.ps1 -Salida "Claude outputs/fases/007/barrera" -TopeS 30` 30 de 30 con la ruta con espacio, y el caso 24 (`prueba-tope`, tope de 3 s) en 3.51 s de cliente y 3.109 s en el registro (antes 8.0 s; esperado ≤ 4); criterio 2: `registro 200` 121 líneas contra `journalctl -t nav-guardian --since today | wc -l` 122, la diferencia es la propia orden `registro`, que se anota al terminar (al repetir, 122: coinciden); en el primer P-2: `sshd -t` bien y 0 líneas de diff para `jetson`, escaneo de después 12 de 12 con el HOME sin escribir, corte con `Permission denied (publickey)`. En el PC: suite 820 (814 pasan, 4 saltadas «solo Linux» y 2 que fallan por el fin de línea del `intrinsecos_gs1` restaurado, ajeno) en 79.6 s; replay de Marker0 8 de 8 en 1.0 s; `gui.panel --selftest` bien. «Verifica» (2026-10-29) arregló `--opcion=valor` en `_args_py`. Fecha: 2026-11-02. Commit: `d2f3632` (parcial) y el de este cierre.
- [ ] **Fase 3 · El entorno en la Jetson** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 4 · La suite corre en Linux** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · La capa V4L2 y cada cámara en la Jetson** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 7 · Las dos cámaras a la vez en la Jetson** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 8 · El panel del PC lanza y para el tracker de la Jetson** (pesada). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 9 · Cómo se trabaja con la Jetson y cierre de la meta** (ligera). Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
