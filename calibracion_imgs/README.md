# Sistema de Navegación Quirúrgica con ArUcos

Sistema de navegación quirúrgica en tiempo real usando marcadores ArUco, visión estéreo y 3D Slicer.

## 🎯 Características

- ✅ **Navegación Relativa**: Usa dos ArUcos (referencia + instrumento) para estabilidad
- ✅ **Calibración de Escala**: Conversión precisa entre unidades OpenCV y milímetros
- ✅ **Filtro de Suavizado**: Reduce temblor y ruido en la visualización
- ✅ **Comunicación OpenIGTLink**: Integración en tiempo real con 3D Slicer
- ✅ **Detección Estéreo**: Triangulación 3D precisa con dos cámaras

## 📁 Archivos del Proyecto

### Scripts Python

| Archivo | Descripción |
|---------|-------------|
| `calibracion_escala.py` | Calibra el factor de conversión OpenCV → Slicer |
| `aruco_navegacion_relativa.py` | Sistema principal de navegación con detección dual |

### Documentación

| Archivo | Descripción |
|---------|-------------|
| `GUIA_CONFIGURACION_SLICER.md` | Configuración paso a paso de 3D Slicer |
| `PROTOCOLO_CALIBRACION.md` | Procedimiento detallado de calibración de escala |
| `README.md` | Este archivo |

### Archivos de Configuración

| Archivo | Descripción |
|---------|-------------|
| `config_calibracion.json` | Factor de escala calibrado (generado automáticamente) |
| `../parametros_calibracion.npz` | Parámetros de calibración estéreo |

## 🚀 Inicio Rápido

### 1. Requisitos

```bash
pip install opencv-python numpy pyigtl
```

- **3D Slicer** 5.0+ con extensión **SlicerIGT**
- Dos cámaras USB calibradas en estéreo
- Marcadores ArUco impresos (ID 0 y ID 1)

### 2. Calibrar Escala

```bash
python calibracion_escala.py
```

Sigue las instrucciones en pantalla para mover el marcador exactamente 100 mm.

### 3. Configurar Slicer

Consulta [`GUIA_CONFIGURACION_SLICER.md`](GUIA_CONFIGURACION_SLICER.md) para:
- Configurar OpenIGTLink
- Crear jerarquía de transformaciones
- Realizar registro

### 4. Ejecutar Navegación

```bash
python aruco_navegacion_relativa.py
```

## 🏗️ Arquitectura del Sistema

```
Cámaras Estéreo
      ↓
Detección ArUco (ID 0: Columna, ID 1: Lezna)
      ↓
Triangulación 3D
      ↓
Transformación Relativa (Lezna → Columna)
      ↓
Aplicar Escala (OpenCV → mm)
      ↓
Filtro de Suavizado (EMA)
      ↓
OpenIGTLink → 3D Slicer
```

## 📊 Jerarquía de Nodos en Slicer

```
ArUco_Columna (Transform)
└── Modelo_Columna (TAC)

LeznaToColumna (Transform - desde Python)
└── Modelo_Lezna (LEZNA.STL)
```

## ⚙️ Configuración

### IDs de Marcadores ArUco

Por defecto:
- **ID 0**: Columna (referencia fija)
- **ID 1**: Lezna (instrumento móvil)

Para cambiar, edita en `aruco_navegacion_relativa.py`:
```python
ARUCO_ID_COLUMNA = 0
ARUCO_ID_LEZNA = 1
```

### Filtro de Suavizado

Ajusta el parámetro `ALPHA_FILTER` en `aruco_navegacion_relativa.py`:
```python
ALPHA_FILTER = 0.3  # 0 = máximo suavizado, 1 = sin suavizado
```

### Puerto OpenIGTLink

Por defecto: `18944`. Para cambiar:
```python
IGTL_PORT = 18944
```

## 🧪 Modo de Prueba

Para ejecutar sin enviar datos a Slicer:

```bash
python aruco_navegacion_relativa.py --test-mode
```

Para desactivar el filtro de suavizado:

```bash
python aruco_navegacion_relativa.py --no-filter
```

## 🔧 Solución de Problemas

### La lezna no se mueve en Slicer

1. Verificar que OpenIGTLink Connector esté activo (modo Server, puerto 18944)
2. Verificar que `LEZNA.STL` esté bajo la transformación `LeznaToColumna`
3. Verificar que ambos ArUcos sean detectados (ventana de Python debe mostrar "NAVEGANDO")

### Escala incorrecta

1. Ejecutar `calibracion_escala.py` nuevamente
2. Usar calibrador digital para medir exactamente 100 mm
3. Verificar que el error de calibración sea < 5%

### La lezna "salta" o tiembla

1. Verificar que ambos ArUcos sean visibles simultáneamente
2. Mejorar iluminación (evitar reflejos)
3. Reducir `ALPHA_FILTER` para más suavizado (ej: 0.2)

### Error de registro alto (> 3 mm)

1. Usar más puntos fiduciales (5-7 en lugar de 3)
2. Verificar que los puntos en el TAC coincidan exactamente con los físicos
3. Medir las coordenadas físicas con mayor precisión

## 📖 Documentación Completa

- **[GUIA_CONFIGURACION_SLICER.md](GUIA_CONFIGURACION_SLICER.md)**: Configuración detallada de 3D Slicer
- **[PROTOCOLO_CALIBRACION.md](PROTOCOLO_CALIBRACION.md)**: Procedimiento de calibración de escala

## 🎓 Conceptos Clave

### Navegación Relativa

En lugar de enviar la posición absoluta de la lezna (respecto a las cámaras), se envía la posición **relativa** (respecto a la columna):

```
T_relativa = T_columna^-1 × T_lezna
```

**Ventaja**: Si las cámaras se mueven, ambos marcadores se mueven igual, por lo que la distancia relativa permanece estable.

### Factor de Escala

OpenCV triangula en unidades arbitrarias (típicamente metros). Slicer trabaja en milímetros. El factor de escala convierte entre ambos:

```
distancia_slicer (mm) = distancia_opencv × factor_escala
```

### Filtro EMA (Exponential Moving Average)

Suaviza las transformaciones para reducir temblor:

```
T_filtrada = α × T_nueva + (1 - α) × T_anterior
```

- `α = 1`: Sin suavizado (rápido, pero con temblor)
- `α = 0`: Máximo suavizado (lento, pero estable)
- `α = 0.3`: Balance recomendado

## 📝 Notas Importantes

> [!IMPORTANT]
> - Ambos marcadores ArUco deben ser visibles simultáneamente
> - Calibrar la escala cada vez que cambies la configuración de las cámaras
> - El error de registro debe ser < 3 mm para navegación quirúrgica

> [!WARNING]
> - Este sistema es para investigación y desarrollo
> - No usar en procedimientos quirúrgicos reales sin validación clínica
> - Siempre verificar la precisión antes de confiar en el sistema

## 🛠️ Desarrollo Futuro

- [ ] Soporte para más de 2 marcadores
- [ ] Registro automático usando puntos anatómicos
- [ ] Grabación de trayectorias
- [ ] Interfaz gráfica para configuración
- [ ] Detección de oclusiones parciales

## 📄 Licencia

Este proyecto es para uso educativo y de investigación.

## 👤 Autor

Sistema de Navegación Quirúrgica - 2025

---

**¿Necesitas ayuda?** Consulta la documentación completa o revisa la sección de solución de problemas.
