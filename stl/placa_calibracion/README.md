# Placa de calibración por divot — v1 (2026-06-12)

Calibración del tip del stylus por template/divot (método de los sistemas
comerciales). Reemplaza al pivote clásico como método estándar del kit:
sin técnica de movimiento, autovalidante, y la misma placa sirve como
ground truth para validar el sistema completo.

## Piezas

| Archivo | Qué es | Impresión |
|---|---|---|
| `placa_calibracion_v2_marker_integrado.stl` | **RECOMENDADA.** Placa con el marker ID 1 modelado en relieve (una pieza, sin papel) | Ver instrucciones v2 abajo |
| `placa_calibracion_v1.stl` | Variante con recess para marker de papel | PLANA sobre la cama, 0.2 mm de capa |
| `cuna_soporte_40deg.stl` | Cuña opcional 40° con ranura para la placa | Cualquier orientación |
| `marker_id1_60mm_A4.pdf` | Marker ID 1 en papel (solo para la v1) | **AL 100%**, sin "ajustar a página" |
| `placa_calibracion_v1_diagrama.png` | Diagrama acotado (válido para ambas) | — |
| `placa_v2_validacion_marker.png` | Patrón del relieve vs referencia cv2 | — |

## Impresión de la v2 (marker integrado)

1. PLANA sobre la cama (cara del marker hacia ARRIBA), capa 0.2 mm,
   4+ perímetros, relleno ≥40%. Altura total: 6.0 mm.
2. Filamento **BLANCO MATE** de base. En el slicer, agregar **cambio de
   color a NEGRO MATE en z = 5.5 mm** (las últimas ~3 capas).
   - Las celdas del marker están en relieve de 0.5 mm sobre un campo
     rehundido: el cambio de color pinta solo celdas + superficie general.
   - PrusaSlicer/Bambu/Cura: "Add color change" / M600 a 5.5 mm.
3. Evitar filamentos brillantes (reflejos especulares matan la detección).
4. Ventaja vs papel: registro marker↔divots perfecto (misma pieza),
   sin pegado, sin escala de impresora. El frame y las coordenadas de los
   divots son idénticos a la v1 (mismo script, sin cambios).

## Armado (una sola vez)

1. Imprimir el PDF y **verificar con regla que la barra mida 100.0 mm**.
   Si no mide eso, la impresora escaló: corregir antes de seguir.
2. Cortar el marker por la línea punteada (70×70 mm).
3. Pegarlo en el recess de la placa, **esquina TL contra la muesca
   triangular** (arriba-izquierda). Pegamento en barra, sin burbujas.
4. Listo. La placa no se recalibra: la geometría es del CAD.

## Coordenadas (frame del marker ID 1)

Origen = centro del marker, +X derecha, +Y arriba, +Z saliendo de la placa.
Ápice de cada cono (lo que toca la punta del stylus):

| Divot | Identificador | x (mm) | y (mm) | z (mm) |
|---|---|---|---|---|
| A | 1 punto  | −40.0 | −50.0 | −3.5 |
| B | 2 puntos |   0.0 | −50.0 | −3.5 |
| C | 3 puntos | +40.0 | −50.0 | −3.5 |

Estas constantes viven en `codigo/iter4/calibrar_tip_divot.py` (`DIVOTS`).
**Si se reimprime la placa con otra geometría, versionar (v2) y actualizar
ambas.**

## Uso (cada vez que se calibra un stylus)

1. Placa inclinada mirando a la cámara (la cuña o cualquier apoyo: el
   ángulo NO importa, se mide solo). Todo el marker visible y nítido.
2. ```powershell
   cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
   python iter4\calibrar_tip_divot.py --divot B --duracion 90
   ```
3. Punta en el divot, **quieto ~4 s**, cambiar de orientación, repetir
   6–10 posturas (inclinar hacia los lados/abajo, no tapar el marker).
4. Leer el reporte: `spread entre posturas` es la métrica de calidad
   (EXCELENTE <0.5 mm, BUENO <1.0 mm). Si da REGULAR, repetir con más
   posturas o revisar que la punta asiente en el ápice.

## Validación cruzada

- Calibrar con divot B y verificar tocando A y C: el tip predicho debe
  caer en sus coordenadas conocidas (script de verificación pendiente).
- Magnitud nominal del stylus actual (caliper, 2026-06-12): **~92.4 mm**.

## Por qué este método

- El pivote depende de la técnica de movimiento (cono completo, presión,
  punto que no cede) — todo lo que falló el 2026-06-11/12.
- El divot da una ecuación 3D completa por frame y el bias de profundidad
  de la cámara se cancela a primer orden (todo es relativo placa↔dodecaedro).
- Referencias: Yaniv "Which pivot calibration?" (SPIE 2015); UCL MPHY0026,
  Template-based tool calibration.
