Plan autorizado por el autor el 2026-10-20

# Tareas — Meta 002 · Calibración de las cámaras global shutter

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

- [ ] **Fase 1 · Sonda de controles, modos e identidad.** Criterio: el del plan. Parcial (2026-10-20): código y pruebas sin cámara hechos (commit `e27049e`). La sesión en vivo con la cámara 1 se paró: la sonda, por MSMF, dejó la exposición en 0 y todas sus cifras de FPS (`sonda_gs1_msmf.json`, `diag_*.json`) no valen. Corregida el mismo día (`Claude outputs/fases/002/fase-1-correccion-hecha.md`): los modos se miden antes de tocar controles, por defecto no se escribe ninguno (`--controles no|leer|probar`), por MSMF solo `no`, la escritura se clasifica (verificada, rechazada, no verificable, no coincide) con un testigo de brillo y FPS, y la sonda no empieza si el tope no alcanza. Sin cámara: suite 147, 125 pasan, 22 `xfail` (las 100 de la línea base iguales), 3.7 s de pytest; replay ≤ 1e-6 mm/°; selftest en verde. Falta la sesión en vivo con el protocolo nuevo. Número obtenido: —. Fecha: —. Commit: `e27049e` (código parcial); la corrección, pendiente.
- [ ] **Fase 2 · Ajustes fijos, identidad y comprobación del tamaño al abrir.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 3 · Enfoque y medición de resolución × formato.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 4 · Calibración de la cámara 1 y comprobación de escala.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 5 · Calibración de la cámara 2.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
- [ ] **Fase 6 · Comparación contra P02 y archivo de los perfiles viejos.** Criterio: el del plan. Número obtenido: —. Fecha: —. Commit: —.
