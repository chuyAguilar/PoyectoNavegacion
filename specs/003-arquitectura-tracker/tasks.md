Plan autorizado por el autor el 2026-10-23

# Tareas — Meta 003 · Arquitectura y optimización del tracker

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número obtenido y la fecha; el commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

- [x] **Fase 1 · Línea base de Marker0 en vivo, antes de mover nada** (pesada). Criterio: *el del plan.* Número obtenido: Marker0 quieto, 100 % con pose, sd z 0.043 (gs1) y 0.039 mm (gs2); replay 0.0 mm / 0.0°; suite 439 + 22 `xfail`; `tests/data/marker0_*` 2.17 MB; detalle en `resultados.md`. Fecha: 2026-10-23. Commit: `b3679ca`.
- [x] **Fase 2 · La cadena solo con Marker0** (pesada; antes, el ADR del principio 6). Criterio: *el del plan.* Número obtenido: en Slicer 19.1 Hz (gs1) y 31.4 Hz (gs2) frente a ~20 y ~31 del tracker, `DodecaedroToTracker` ausente, salida limpia; replay de Marker0 0.0 mm / 0.0°; perfiles −13 líneas c/u; suite 446 + 22 `xfail`; detalle en `resultados.md`. Fecha: 2026-10-23. Commit: `c1409ad`.
- [x] **Fase 3 · La estructura nueva y el archivo** (ligera). Criterio: *el del plan.* Número obtenido: 0 `.py` en `iter4/` (el autor borró `codigo\iter4` y `codigo\Log`); suite 392/392 en 18 s, sin `xfail`; replay de Marker0 0.0 mm / 0.0°; en vivo con gs1 por el panel: los 4 procesos (Probar cámara, Verificar IDs, Arrancar tracker) con exit=0, `[Whitelist] [0]`, selftest con los 3 argv `-m`; fps 16–22 (dato para B32); detalle en `resultados.md`. Fecha: 2026-10-24. Commit: `78ce1af`.
- [x] **Fase 4 · El tracker en piezas** (pesada). Criterio: *el del plan.* Número obtenido: replay de Marker0 por `MarkerTracker.process_corners` 0.0 mm / 0.0° (977 y 973 envíos), detección 0.0 px; `tracker.py` 754 → 212 líneas; suite 463/463 en 18.4 y 18.3 s, 0 avisos; B22, B27, B28 y B34 cerrados. En vivo (2026-10-24): a mano sin la variable de entorno la cámara abre en 0.4 s (B28; antes 40–50 s); Hz en Slicer 22.1 (gs1) y 30.9 (gs2) a mano, 28.6 y 22.8 desde el panel; servidor 18944 cerrado y `[Salida limpia]` en las cuatro corridas (y en el fallo de arranque); detalle en `resultados.md`. Fecha: 2026-10-24. Commit: *—.*
- [ ] **Fase 5 · Documentación del paso 1** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 6 · Dónde se va el tiempo por frame** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 7 · Subir los fps con ventana** (pesada). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
- [ ] **Fase 8 · Cierre de la meta** (ligera). Criterio: *el del plan.* Número obtenido: *—.* Fecha: *—.* Commit: *—.*
