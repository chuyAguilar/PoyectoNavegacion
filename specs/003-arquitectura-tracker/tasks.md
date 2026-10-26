Plan autorizado por el autor el 2026-10-23

# Tareas — Meta 003 · Arquitectura y optimización del tracker

La primera línea dice si el plan está autorizado. Cuando el autor lo autoriza, pasa a «Plan autorizado por el autor el AAAA-MM-DD»; sin esa línea, `/fase` no hace nada.
Una casilla por fase; el criterio es el del plan (`plan.md`, «Fases») y aquí no se repite, para que el arranque pese poco. `/fase <n>` la marca con el número clave y la fecha; el detalle va a `resultados.md`. El commit lo añade `/cerrar-fase` o la fase siguiente, cuando ya está en git.

- [x] **Fase 1 · Línea base de Marker0 en vivo, antes de mover nada** (pesada). Sd z 0.043 (gs1) y 0.039 mm (gs2), 100 % con pose; replay 0.0. 2026-10-23. `b3679ca`.
- [x] **Fase 2 · La cadena solo con Marker0** (pesada). Slicer 19.1 / 31.4 Hz, `DodecaedroToTracker` ausente; replay 0.0. 2026-10-23. `c1409ad`.
- [x] **Fase 3 · La estructura nueva y el archivo** (ligera). 0 `.py` en `iter4/`; suite 392/392; replay 0.0; panel con exit=0. 2026-10-24. `78ce1af`.
- [x] **Fase 4 · El tracker en piezas** (pesada). Replay 0.0 por `MarkerTracker`; `tracker.py` 754 → 212 líneas; suite 463/463; B22, B27, B28, B34 cerrados. 2026-10-24. `9f500ca`.
- [x] **Fase 5 · Documentación del paso 1** (ligera). `iter4` solo histórico; suite 463/463; B21 cerrado. 2026-10-24. `34a8d4f`.
- [x] **Fase 6 · Dónde se va el tiempo por frame** (ligera). Envío 9.1–12.5 ms, detección + pose ~6.5, ventana ~3.7; suite 475/475. 2026-10-24. `ec259de`.
- [x] **Fase 7 · Subir los fps con ventana** (pesada). Con ventana, caja al máximo: gs1 61.7 fps, sd z 0.033 (cumple); gs2 55.2, aceptado (P11); envío 0.02 ms; suite 491/491; B32 cerrado. 2026-10-25. `33d85c0`.
- [x] **Fase 7b · Botones de tracker sin ventana y de vista previa para posicionar las cámaras** (ligera; P10, P12, P13). Sin ventana: 89.9 / 88.8 fps, sd z 0.037 / 0.030 mm, 99.96 % con pose, cierres limpios; **Hz en Slicer ~66 frente a ~81: no cumple, declarado (P15)**; suite 514/514. 2026-10-25. `1fe90f0`.
- La fase 8 · Cierre de la meta se replaneó el 2026-10-25 (P14, P15, P16) y se parte en tres. **Autorizada por el autor el 2026-10-25** (P17 = a, P18 = a: si la 8b da R1, se añade una fase 8b2 antes de la 8c).
- [x] **Fase 8a · Un botón por modo en el panel** (ligera; P14 = b, P16 = b, P17 = a). Sin cámara: suite 516/516; replay 0.0; selftest. **En vivo (gs1 y gs2): `camara X fps` 89.8–90.1 (≥ 85), cierres limpios con los tres botones, exit 0.** 2026-10-25. `01afef3`.
- [x] **Fase 8b · De dónde sale el techo de ~66 Hz en Slicer** (pesada; P15 = b). **R2: el techo es de Slicer** (emisor a 64 ráfagas/s, o 88 con timer de 1 ms, y Slicer sigue en 64.3 y 65.0 Hz; R3 y R4 descartados; sin fase 8b2 por P18); suite 555/555 en 33.1 y 33.6 s; replay 0.0. 2026-10-25. Commit: *—.*
- [ ] **Fase 8c · Cierre de la meta** (ligera). Número: *—.* Fecha: *—.* Commit: *—.*
