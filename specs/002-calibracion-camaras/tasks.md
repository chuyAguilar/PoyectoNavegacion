Plan autorizado por el autor el 2026-10-21 (revisión 2; la revisión 1 se autorizó el 2026-10-20)

# Tareas — Meta 002 · Calibración de las cámaras global shutter

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git. Una casilla cerrada se deja corta (número clave, fecha y commit); su texto completo pasa a `resultados.md`, que no se lee al arrancar.

- [x] **Fase 1 · Sonda de controles, modos e identidad.** Modos MSMF MJPG ~90 fps de 320×240 a 1280×960 (con la aceleración HW encendida); controles por DSHOW 10 de 12; serie `01.00.00` igual en las dos. Suite 147. Fecha: 2026-10-21. Commit: `e27049e`, `f1536cf`; cierre `06619cf`. Detalle: `resultados.md`.
- [x] **Fase 2a · Identidad por puerto y controles por DSHOW, medidos con las dos cámaras — pesada.** Identidad por la ruta del puerto 6 de 6; orden DSHOW 4 de 4; MSMF no pisa DSHOW (0 diferencias); marca `focus` válida. Suite 212. Fecha: 2026-10-21. Commit: `4b548cb`. Detalle: `resultados.md`.
- [x] **Fase 2b · Perfiles por cámara: identidad, ajustes y tamaño al abrir — pesada.** Los seis puntos en vivo pasan (4 de 4 cada perfil la suya; 2 de 2 intercambiadas); el código apaga la aceleración HW de MSMF (apertura 43–51 s → 0.4–0.5 s); la marca solo es fiable escrita (`--forzar`). Suite 267. Fecha: 2026-10-22. Commit: `0e14bc8`. Detalle: `resultados.md`.
- [x] **Fase 3 · Enfoque, exposición y medición de resolución × formato — pesada.** El criterio de modos NO se cumple (con ventana 19–25 fps en cualquier modo; la ventana es el cuello, B32); elige el autor: 1280×960 MJPG 90 fps (P16) y 0.977 ms (P15) en las dos; captura ~90 en todos los modos. Perfiles comprobados en vivo a 1280×960. Suite 306. Fecha: 2026-10-22. Commit: `e42061f`. Detalle: `resultados.md`.
- [ ] **Fase 4 · Calibración de la cámara 1 y comprobación de escala — pesada.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · Calibración de la cámara 2 — ligera.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 6 · Comparación contra P02 y archivo de los perfiles viejos — pesada.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
