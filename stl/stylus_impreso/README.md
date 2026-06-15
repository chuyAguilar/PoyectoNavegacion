# Stylus impreso v1 (2026-06-13)

Stylus 100% impreso con los markers MODELADOS en el CAD: la geometria del
rigid body se conoce exacta (sin pegado, sin topologia sorpresa, BA opcional).

Specs: arista 20 mm, marker 16 mm (celdas 2.0 mm en relieve 0.5), IDs 181-191
(TOP=181, sup 182-186, inf 187-191), punta cono 30 grados + ESFERA r=1.0 mm
(autocentrante en el divot).

Mangos disponibles (mismo dodecaedro y espiga):
- `mango_punta_150.stl` (RECOMENDADO, 2026-06-13): centro dodecaedro ->
  centro esfera = 150.0 mm, eje de 12 mm, agarre en el tercio inferior
  (la mano queda lejos de los markers). Trade-off aceptado: brazo de
  palanca mas largo amplifica el error angular de pose en la punta
  (~+0.5 mm vs el corto; leccion iter 1).
- `mango_punta.stl`: version corta original, 92.0 mm.

## ORDEN DE IMPRESION

1. **PRIMERO el cupon** (`cupon_prueba_blanco/negro.stl`, 10 min): importar
   ambos como UN objeto multiparte en Bambu Studio, blanco mate + negro mate,
   imprimir plano. Probar deteccion frente a la camara (debe leer ID 181).
   Si las celdas de 2.0 mm no detectan bien, NO imprimir el resto: avisar.
2. **Dodecaedro**: `dodecaedro_blanco.stl` + `dodecaedro_celdas_negras.stl`
   como objeto multiparte. Apoya naturalmente en su cara inferior (la del
   socket, sin marker). Capa 0.12-0.16 mm recomendada, relleno >=25%,
   SIN soporte (caras inferiores a 26 grados de la vertical, auto-soportadas).
3. **Mango** (`mango_punta.stl`): de pie, punta hacia ARRIBA, brim. Capa fina
   para la esfera de la punta. Relleno >=40% (rigidez).
4. **Espiga** (`espiga_dowel.stl`): acostada o de pie, cualquiera.

## Ensamble

Espiga con pegamento (cianoacrilato) en el socket del dodecaedro y del mango.
RIGIDO y permanente: si se vuelve a armar, recalibrar tip.

## Despues de imprimir

1. Medir con caliper: lado del marker TOP (nominal 16.0) y ancho entre caras
   opuestas... el dato clave es el marker. Anotar.
2. `codigo/iter4/data/reference_stylus_impreso.txt` es la geometria CAD
   exacta (mismo formato que siempre). Para usarla: cambiar `geometry_file`
   y `marker_mm: 16.0` en tracker_config.yaml (o un config nuevo).
3. Calibrar tip con la placa divot. OJO: la punta es una ESFERA r=1 mm.
   En el cono de 90 grados del divot, el CENTRO de la esfera queda a
   r/sin(45) = 1.41 mm del apice a lo largo de la normal de la placa:
   usar p_divot_z = -3.5 + 1.41 = -2.09 (flag --tip-r pendiente en
   calibrar_tip_divot.py, o ajustar DIVOTS).
4. Opcional: BA de refinamiento (captura + calibrar_rigid_body con
   --teorico reference_stylus_impreso.txt) para absorber el encogimiento
   de impresion. Con escala medida del cupon quiza ni haga falta.

## Por que este stylus

La calibracion divot del 2026-06-13 mostro que la punta ROSCADA del stylus
actual no define un punto: magnitud 92.0 vs 96.8 entre sesiones, spread X-Y
3-6 mm (la rosca asienta donde quiere). La esfera r1 se autocentra: el
contacto queda definido por geometria, no por suerte.
