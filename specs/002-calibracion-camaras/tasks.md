Plan autorizado por el autor el 2026-10-20

# Tareas — Meta 002 · Calibración de las cámaras global shutter

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

- [ ] **Fase 1 · Sonda de controles, modos e identidad.** Criterio: el del plan. Parcial (2026-10-20): código y pruebas sin cámara hechos; falta la sesión en vivo con el autor (protocolo en `Claude outputs/fases/002/fase-1.md`), que da las tablas de controles, los modos y la identidad. Sin cámara: suite 128, 106 pasan, 22 `xfail` (las 100 de la línea base iguales, 28 nuevas), 3.9 s de pytest; replay ≤ 1e-6 mm/°; selftest en verde; capa `ctypes` de Media Foundation comprobada sin cámara (VIDCAP aceptado, GUID falso → `E_INVALIDARG`, `GetAllocatedString` lee los 2 micrófonos); el GUID del enlace simbólico solo se comprueba con una cámara. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 2 · Ajustes fijos, identidad y comprobación del tamaño al abrir.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 3 · Enfoque y medición de resolución × formato.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 4 · Calibración de la cámara 1 y comprobación de escala.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · Calibración de la cámara 2.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 6 · Comparación contra P02 y archivo de los perfiles viejos.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
