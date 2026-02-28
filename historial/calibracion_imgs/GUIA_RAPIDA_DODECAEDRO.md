# Guía Rápida: Sistema de Navegación Quirúrgica con Dodecaedro ArUco

## 🎯 Resumen del Sistema

Tu sistema ahora está optimizado para navegación quirúrgica profesional:

- **Columna**: Marcador ArUco único (ID 0) - 10x10 cm
- **Lezna**: Dodecaedro ArUco (IDs 1-12) - Tracking en cualquier orientación
- **Cámaras**: Estéreo (índices 1 y 3) con triangulación 3D real
- **Salida**: 3D Slicer vía OpenIGTLink + CSV

---

## 📋 Pasos para Implementar

### Paso 1: Generar Marcadores ArUco (5 min)

```bash
cd "c:\Users\USER\Desktop\VR VM\PROYECTO NAVEGACION\calibracion_imgs"
python generar_dodecaedro_aruco.py
```

**Resultado:**
- Carpeta `dodecaedro_aruco/` con:
  - `plantilla_marcador_columna.png` → Imprimir en A4
  - `plantilla_dodecaedro_lezna.png` → Imprimir en A4
  - `INSTRUCCIONES_ENSAMBLAJE.txt` → Leer antes de armar
  - 13 archivos PNG individuales (IDs 0-12)

---

### Paso 2: Imprimir y Armar (30 min)

#### Marcador de la Columna:
1. Imprimir `plantilla_marcador_columna.png` en papel mate
2. Recortar y pegar en cartón rígido
3. Fijar en la columna vertebral (modelo físico)

#### Dodecaedro de la Lezna:

**Opción A - Cubo Simplificado (Recomendado para empezar):**
1. Usar solo 6 de los 12 marcadores (IDs 1-6)
2. Armar un cubo simple
3. Pegar en el mango de la lezna

**Opción B - Dodecaedro Completo (Óptimo):**
1. Buscar plantilla de dodecaedro 3D en internet
2. Pegar los 12 marcadores en las 12 caras
3. Requiere más tiempo pero mejor cobertura

---

### Paso 3: Calibración Estéreo (10-15 min)

```bash
python calibracion_stereo_adaptada.py
```

**Proceso:**
1. Coloca el tablero de ajedrez frente a ambas cámaras
2. Presiona 'c' para capturar (mínimo 15 imágenes)
3. Mueve el tablero a diferentes posiciones y ángulos
4. Presiona 'q' cuando tengas suficientes imágenes
5. El script generará `parametros_calibracion_stereo.npz`

**Criterios de Éxito:**
- Error de reproyección < 0.5
- Mínimo 15 pares de imágenes válidas
- Distancia entre cámaras razonable (10-50 cm)

---

### Paso 4: Navegación Quirúrgica (¡Listo!)

```bash
python navegacion_dodecaedro.py
```

**Funcionalidad:**
- Detecta automáticamente la cara más visible del dodecaedro
- Calcula posición 3D real mediante triangulación estéreo
- Navegación relativa (Lezna respecto a Columna)
- Envía transformaciones a 3D Slicer
- Guarda datos en CSV

**Controles:**
- `q` → Salir
- `r` → Reiniciar filtro de suavizado

---

## 🔧 Opciones Avanzadas

### Modo de Prueba (sin Slicer)
```bash
python navegacion_dodecaedro.py --test-mode
```

### Sin Filtro de Suavizado
```bash
python navegacion_dodecaedro.py --no-filter
```

### Sin Guardar CSV
```bash
python navegacion_dodecaedro.py --no-csv
```

---

## 📊 Archivos Generados

| Archivo | Descripción |
|---------|-------------|
| `parametros_calibracion_stereo.npz` | Calibración de cámaras estéreo |
| `navegacion_dodecaedro.csv` | Datos de navegación (posiciones, distancias) |
| `dodecaedro_aruco/` | Carpeta con marcadores y plantillas |

---

## 🎓 Ventajas del Dodecaedro vs Cubo

| Característica | Cubo (6 caras) | Dodecaedro (12 caras) |
|----------------|----------------|----------------------|
| Cobertura angular | 60° por cara | 36° por cara |
| Probabilidad de detección | Buena | **Excelente** |
| Rotaciones libres | Limitado | **Total** |
| Ideal para | Movimientos moderados | **Perforación quirúrgica** |

---

## 🔍 Cómo Funciona la Detección Automática

El script `navegacion_dodecaedro.py` detecta automáticamente la cara más visible:

```python
# Detecta todas las caras visibles (IDs 1-12)
# Calcula cuál está más frontal a la cámara
# Usa esa cara para calcular la posición 3D
# Si la lezna rota, automáticamente cambia a otra cara
```

**Ventaja:** Tracking continuo sin importar cómo rotes la lezna durante la perforación.

---

## ⚠️ Solución de Problemas

### "No se encontró parametros_calibracion_stereo.npz"
→ Ejecuta primero `calibracion_stereo_adaptada.py`

### "No se pudieron abrir las cámaras"
→ Verifica que las cámaras 1 y 3 estén conectadas
→ Ejecuta `prueba_dos_camaras.py` para confirmar

### "Lezna NO DETECTADA"
→ Asegúrate de que al menos una cara del dodecaedro sea visible en AMBAS cámaras
→ Mejora la iluminación (luz difusa, sin reflejos)

### "Error de calibración alto (>0.5)"
→ Captura más imágenes del tablero de ajedrez
→ Asegúrate de cubrir diferentes ángulos y posiciones
→ Verifica que el tablero esté plano (sin arrugas)

---

## 📝 Próximos Pasos

1. ✅ Generar marcadores
2. ✅ Imprimir y armar dodecaedro
3. ✅ Calibrar cámaras estéreo
4. ✅ Probar navegación
5. ⏭️ Configurar 3D Slicer (ver `GUIA_CONFIGURACION_SLICER.md`)
6. ⏭️ Realizar registro TAC-Mundo real
7. ⏭️ Pruebas de precisión

---

## 🎯 Configuración Recomendada

### Para la Columna:
- Marcador plano grande (10 cm x 10 cm)
- ID 0
- Pegado firmemente en la columna vertebral
- Orientado hacia las cámaras

### Para la Lezna:
- Dodecaedro o cubo con IDs 1-12 (o 1-6 para cubo)
- Pegado en el mango de la lezna
- Tamaño: 5 cm de lado
- Permite rotación libre durante la perforación

---

## 📞 Ayuda Adicional

Si tienes problemas, revisa:
- `PROTOCOLO_CALIBRACION.md` → Detalles de calibración
- `GUIA_CONFIGURACION_SLICER.md` → Configuración de Slicer
- `dodecaedro_aruco/INSTRUCCIONES_ENSAMBLAJE.txt` → Cómo armar el dodecaedro

---

**¡Tu sistema de navegación quirúrgica está listo!** 🎉
