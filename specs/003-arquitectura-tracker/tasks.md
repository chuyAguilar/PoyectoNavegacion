Plan autorizado por el autor el 2026-10-23

# Tareas — Meta 003 · Arquitectura y optimización del tracker

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

- [x] **Fase 1 · Línea base de Marker0 en vivo, antes de mover nada** (pesada). Criterio: *el del plan.* Número obtenido: Marker0 quieto, 100 % con pose, sd z 0.043 (gs1) y 0.039 mm (gs2); replay 0.0 mm / 0.0°; suite 439 + 22 `xfail`; `tests/data/marker0_*` 2.17 MB; detalle en `resultados.md`. Fecha: 2026-10-23. Commit: `b3679ca`.
- [x] **Fase 2 · La cadena solo con Marker0** (pesada; antes, el ADR del principio 6). Criterio: *el del plan.* Número obtenido: en Slicer 19.1 Hz (gs1) y 31.4 Hz (gs2) frente a ~20 y ~31 del tracker, `DodecaedroToTracker` ausente, salida limpia; replay de Marker0 0.0 mm / 0.0°; perfiles −13 líneas c/u; suite 446 + 22 `xfail`; detalle en `resultados.md`. Fecha: 2026-10-23. Commit: *—.*
- [ ] **Fase 3 · La estructura nueva y el archivo** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 4 · El tracker en piezas** (pesada). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 5 · Documentación del paso 1** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 6 · Dónde se va el tiempo por frame** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 7 · Subir los fps con ventana** (pesada). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 8 · Cierre de la meta** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
