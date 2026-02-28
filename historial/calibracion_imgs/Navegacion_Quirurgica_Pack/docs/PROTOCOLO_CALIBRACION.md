# Protocolo de Calibración de Escala

Este documento describe el procedimiento detallado para calibrar el factor de conversión entre las unidades de triangulación de OpenCV y los milímetros de 3D Slicer.

## Objetivo

Determinar el factor de escala correcto para que **1 mm de movimiento físico = 1 mm de movimiento en Slicer**.

---

## Materiales Necesarios

- [ ] Marcador ArUco impreso (ID 0 o ID 1)
- [ ] Regla milimétrica o calibrador digital
- [ ] Superficie plana y estable
- [ ] Iluminación adecuada (sin reflejos)
- [ ] Cámaras estéreo calibradas
- [ ] Script `calibracion_escala.py`

---

## Preparación del Entorno

### 1. Configuración de Iluminación

- Usar luz difusa (evitar luz solar directa)
- Sin sombras fuertes sobre el marcador ArUco
- Iluminación uniforme en el área de trabajo

> [!TIP]
> Una lámpara LED con difusor colocada a 45° del área de trabajo funciona bien.

### 2. Posición de las Cámaras

```
Vista Superior:

        [Cámara Izq]  [Cámara Der]
              \           /
               \         /
                \       /
                 \     /
                  \   /
                   \ /
              [Área de trabajo]
                 (30-50 cm)
```

- Distancia a las cámaras: 30-50 cm
- Ángulo entre cámaras: 15-30°
- Ambas cámaras deben ver claramente el marcador

### 3. Preparación del Marcador

- Imprimir el marcador ArUco en papel de alta calidad
- Pegar sobre cartón rígido o foam board
- Asegurar que esté completamente plano (sin arrugas ni dobleces)
- Tamaño recomendado: 5 cm × 5 cm

---

## Procedimiento de Calibración

### Paso 1: Verificar Calibración Estéreo

Antes de calibrar la escala, asegúrate de que las cámaras estén calibradas correctamente.

```bash
# Verificar que existe el archivo de calibración
ls ../parametros_calibracion.npz
```

Si no existe, ejecuta primero el script de calibración estéreo.

### Paso 2: Ejecutar Script de Calibración

```bash
cd "c:\Users\USER\Desktop\VR VM\PROYECTO NAVEGACION\calibracion_imgs"
python calibracion_escala.py
```

### Paso 3: Capturar Posición Inicial

1. Colocar el marcador ArUco en el centro del área de trabajo

2. Asegurar que ambas cámaras detectan el marcador:
   - Ventana izquierda: debe mostrar "ArUco DETECTADO" en verde
   - Ventana derecha: debe mostrar el marcador con bordes dibujados

3. Presionar **ESPACIO** para capturar la posición inicial

4. El script mostrará:
   ```
   ✅ Posición inicial capturada: [x, y, z]
   ```

> [!IMPORTANT]
> No muevas las cámaras durante todo el proceso de calibración.

### Paso 4: Mover el Marcador Exactamente 100 mm

Este es el paso más crítico. Tienes dos opciones:

#### Opción A: Usar Regla Milimétrica

1. Colocar una regla milimétrica junto al marcador

2. Marcar la posición inicial del centro del marcador

3. Mover el marcador **exactamente 100 mm** en una dirección (preferiblemente horizontal)

4. Verificar la medición dos veces

#### Opción B: Usar Calibrador Digital (Recomendado)

1. Colocar el calibrador en modo de medición de distancias

2. Fijar un extremo del calibrador en la posición inicial

3. Mover el marcador hasta que el calibrador marque exactamente **100.0 mm**

> [!TIP]
> Mueve el marcador en el eje X (horizontal) para mayor precisión. Evita movimientos en diagonal.

### Paso 5: Capturar Posición Final

1. Con el marcador en la nueva posición (100 mm desplazado)

2. Verificar que ambas cámaras siguen detectando el marcador

3. Presionar **ESPACIO** para capturar la posición final

4. El script calculará automáticamente el factor de escala

### Paso 6: Verificar Resultados

El script mostrará algo como:

```
==================================================================
RESULTADOS DE CALIBRACIÓN
==================================================================
Distancia medida (unidades OpenCV): 0.098543
Distancia real (mm):                 100.00
Factor de escala calculado:          1014.79
==================================================================

Verificación:
  Distancia calculada: 100.02 mm
  Error: 0.02 mm (0.02%)
  ✅ Calibración EXITOSA (error < 5%)

✅ Configuración guardada en: config_calibracion.json
```

### Interpretación de Resultados

| Error | Interpretación | Acción |
|-------|----------------|--------|
| < 2% | Excelente | Usar este factor de escala |
| 2-5% | Aceptable | Usar, pero considera recalibrar |
| 5-10% | Marginal | Recalibrar con más cuidado |
| > 10% | Inaceptable | Revisar setup y recalibrar |

---

## Validación de la Calibración

Después de obtener el factor de escala, es importante validarlo.

### Prueba de Validación

1. Ejecutar nuevamente el script de calibración

2. Esta vez, mover el marcador **50 mm** (mitad de la distancia)

3. El script debería calcular un factor de escala similar (±5%)

4. Si los factores son consistentes, la calibración es confiable

### Ejemplo de Validación

```
Primera calibración (100 mm):  Factor = 1014.79
Segunda calibración (50 mm):   Factor = 1018.32
Diferencia: 0.35% ✅ CONSISTENTE
```

---

## Solución de Problemas

### Problema: "ArUco NO detectado"

**Causas posibles:**
- Iluminación insuficiente o con reflejos
- Marcador arrugado o dañado
- Cámaras desenfocadas
- Distancia incorrecta

**Soluciones:**
- Ajustar iluminación
- Imprimir nuevo marcador
- Ajustar distancia a 30-50 cm
- Limpiar lentes de las cámaras

### Problema: Error de calibración > 10%

**Causas posibles:**
- Medición física imprecisa
- Marcador movido en diagonal
- Cámaras movidas durante el proceso
- Calibración estéreo incorrecta

**Soluciones:**
- Usar calibrador digital en lugar de regla
- Mover solo en eje X (horizontal)
- Fijar las cámaras firmemente
- Recalibrar sistema estéreo

### Problema: Resultados inconsistentes

**Causas posibles:**
- Vibración de la superficie
- Movimiento de las cámaras
- Cambios en la iluminación

**Soluciones:**
- Usar superficie más estable
- Fijar cámaras con trípode
- Mantener iluminación constante

---

## Recalibración

### ¿Cuándo recalibrar?

- Cada vez que cambies la configuración de las cámaras
- Si cambias la distancia de trabajo
- Si los resultados de navegación parecen incorrectos
- Cada 1-2 semanas para aplicaciones críticas

### Proceso de Recalibración

1. Ejecutar `calibracion_escala.py`

2. Presionar **ESPACIO** cuando el script esté en estado "COMPLETADO"

3. El script se reiniciará automáticamente

4. Repetir el proceso de calibración

---

## Archivo de Configuración

El script guarda el factor de escala en `config_calibracion.json`:

```json
{
    "factor_escala": 1014.79,
    "fecha_calibracion": "2025-11-24 23:15:30",
    "distancia_prueba_mm": 100.0,
    "distancia_medida_unidades": 0.098543,
    "distancia_calculada_mm": 100.02,
    "aruco_id_usado": 0,
    "notas": "Calibración de escala para navegación quirúrgica"
}
```

Este archivo es leído automáticamente por `aruco_navegacion_relativa.py`.

---

## Checklist de Calibración

Antes de considerar la calibración completa, verifica:

- [ ] Error de calibración < 5%
- [ ] Validación con distancia diferente (50 mm) es consistente
- [ ] Archivo `config_calibracion.json` generado correctamente
- [ ] Factor de escala es un número razonable (típicamente 500-2000)
- [ ] Iluminación y setup documentados para futuras calibraciones

---

## Mejores Prácticas

1. **Calibrar en condiciones similares a las de uso**
   - Misma iluminación
   - Misma distancia de trabajo
   - Mismo tipo de superficie

2. **Realizar múltiples calibraciones**
   - Hacer 3 calibraciones
   - Usar el promedio de los factores
   - Descartar valores atípicos

3. **Documentar el setup**
   - Tomar fotos de la configuración
   - Anotar distancia de las cámaras
   - Registrar condiciones de iluminación

4. **Validar regularmente**
   - Hacer pruebas de precisión semanales
   - Comparar con mediciones físicas
   - Recalibrar si hay desviaciones

---

## Ejemplo de Sesión Completa

```
$ python calibracion_escala.py

======================================================================
CALIBRACIÓN DE ESCALA - NAVEGACIÓN QUIRÚRGICA
======================================================================

✅ Parámetros de calibración cargados correctamente
📹 Inicializando cámaras...
✅ Cámaras inicializadas

======================================================================
INSTRUCCIONES:
======================================================================
1. Coloca el marcador ArUco ID 0 en una posición inicial
2. Presiona ESPACIO para capturar la posición inicial
3. Mueve el marcador EXACTAMENTE 100 mm (usa regla/calibrador)
4. Presiona ESPACIO para capturar la posición final
5. El script calculará automáticamente el factor de escala

Presiona 'q' para salir
======================================================================

[Usuario coloca marcador y presiona ESPACIO]

✅ Posición inicial capturada: [0.245, -0.132, 0.487]
   Ahora mueve el marcador EXACTAMENTE 100 mm

[Usuario mueve marcador 100 mm y presiona ESPACIO]

✅ Posición final capturada: [0.343, -0.128, 0.485]

======================================================================
RESULTADOS DE CALIBRACIÓN
======================================================================
Distancia medida (unidades OpenCV): 0.098543
Distancia real (mm):                 100.00
Factor de escala calculado:          1014.79
======================================================================

Verificación:
  Distancia calculada: 100.02 mm
  Error: 0.02 mm (0.02%)
  ✅ Calibración EXITOSA (error < 5%)

✅ Configuración guardada en: config_calibracion.json

Presiona 'q' para salir o ESPACIO para recalibrar

[Usuario presiona 'q']

✅ Calibración finalizada
```

---

## Próximos Pasos

Después de completar la calibración exitosamente:

1. Ejecutar `aruco_navegacion_relativa.py` para verificar que el factor de escala se carga correctamente

2. Realizar pruebas de precisión moviendo la lezna distancias conocidas

3. Ajustar el filtro de suavizado si es necesario

4. Proceder con el registro en 3D Slicer
