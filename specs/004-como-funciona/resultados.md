# Resultados — Meta 004 · Cómo funciona el tracker

Los números de cada fase y del criterio de cierre, con su fuente. Las casillas de `tasks.md` remiten aquí; el detalle de cada fase está en su reporte (`Claude outputs/fases/004/`).

## El criterio de cierre del spec (2026-10-26)

| Criterio | Número | Fuente | Estado |
|---|---|---|---|
| El gráfico es fiel al código | 0 referencias inexistentes; 130 referencias en §9 tras la fase 3 (77 antes de ella); §9.1 con 20 cajas | `tests/test_como_funciona.py`; fases 1 y 3 | Cumplido |
| El ejemplo resuelto reproduce la cadena | 0.0 mm / 0.0° frente al replay en los 6 frames (3 de gs1 y 3 de gs2); esquinas = grabadas a 0.0 px | `tests/test_explain_pose.py`; fase 2 | Cumplido |
| La explicación se entiende | 0 dudas abiertas en §9.2 y §9.4 (alcance de P12), confirmado por el autor el 2026-10-26 | `clarify.md`, P12; abajo, «La lectura» | Cumplido |
| Cada número de la explicación tiene su fuente | §9.5 con 35 filas; 0 números sin fuente | §9.5; revisado por la dirección el 2026-10-26 | Cumplido |
| La suite, el replay y el selftest | 618 de 618 en 34.29 s; replay de Marker0 (gs1 y gs2) 8 de 8, 0.0 mm / 0.0°, detección 0.0 px; pruebas de §9 y del replay 55 de 55; `python -m gui.panel --selftest` sale con 0 | corrida del cierre, 2026-10-26 | Cumplido |
| Sin tocar la cadena | `git diff --stat 63bbdd8` de `tracker.py`, `camera/`, `vision/`, `transport/`, `profiles/`, `data/` y `slicer/`: vacío | corrida del cierre, 2026-10-26 | Cumplido |

## La lectura (fase 4 · Lectura con el autor y cierre de la meta, 2026-10-26)

**El alcance** es el de P12 (`clarify.md`, respuesta 2): §9.2 (los 11 pasos) y §9.4 (el glosario). §9.1 la leyó el autor en la fase 1 («se lee bien y se entiende»); §9.3 y §9.5 quedan sin su lectura y las cubren sus pruebas (`tests/test_como_funciona.py`, `tests/test_explain_pose.py`).

**Las dudas:** 0. El autor, en el chat de dirección, el 2026-10-26: «no me queda ninguna duda al leer, si después surge algo lo trabajamos de nuevo».

| Duda | Dónde se contestó | Fecha |
|---|---|---|
| (ninguna) | — | 2026-10-26 |

Como no hubo dudas, §9 no cambió en esta fase y la imagen del mapa no se reexportó (la prueba del sha sigue en verde). La lectura no descubrió nada en la cadena: nada nuevo al BACKLOG.

## Las fases

| Fase | Número | Commit |
|---|---|---|
| Fase 1 · El mapa del proyecto, su imagen y su prueba | §9.1 con 20 cajas y 0 referencias inexistentes; `docs/img/004/mapa_proyecto.svg` de 99 584 bytes; el autor: «se lee bien y se entiende» | `f3a2d4b` |
| Fase 2 · El ejemplo resuelto con un frame real | 6 frames: esquinas = grabadas a 0.0 px; 4×4 = enviada = replay a 0.0 mm / 0.0°; escala de B55, cociente 1.2325 con la misma rotación; reproyección 0.053–0.204 px | `533989a` |
| Fase 3 · La explicación y el glosario | §9.2 en 11 pasos, §9.4 con 32 términos, §9.5 con 35 filas; referencias de §9: 130, 0 inexistentes | `354afe4` |
| Fase 4 · Lectura con el autor y cierre de la meta | 0 dudas en §9.2 y §9.4, confirmado por el autor; §9 sin cambios | — |

## Las fases extra 2b y 2c

Dos arreglos del panel que el autor pidió durante la meta (P10 y P11), fuera de la cadena:

- **Fase 2b · «Verificar IDs y colocar la cámara» marca la cámara en verde y se quita «Probar cámara»** (`54c48a7`, solo `gui/`): con código 0 el semáforo «Cámara» pasa a verde con los fps; con otro, a rojo con el error. En vivo: verde, 30 fps la primera corrida y 89.8 la segunda (B50, sin investigar). Cerró B29.
- **Fase 2c · «Comprobar escala con regla» sin congelarse y con vista previa fluida** (`16e7f35`, solo `calibration/check_scale.py`): la vista previa se detecta a la mitad y en otro hilo, de 245–257 a 1.6–1.8 ms por frame de hilo principal (peor caso: Marker0 delante y sin tablero); durante la medida se repinta en cada pose (0.07–0.2 s); los números de escala no cambian. Abrió B58 (la ventana de «Calibrar con tablero» tiene el mismo problema).

**Lo que quedó sin hacer en vivo:** la prueba con la regla de la fase 2c. El autor la dejó el 2026-10-26: se retoma solo si la ventana vuelve a congelarse o ir lenta (protocolo en `Claude outputs/fases/004/fase-2c.md`).
