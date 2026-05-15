# Sistema de Navegación Quirúrgica con Tracking Multi-Marker

## Documento Técnico de Avance — 4 Días de Desarrollo

**Proyecto**: Sistema de coherencia espacial para navegación quirúrgica ortopédica
**Hardware base**: Cámara SVPRO (sensor AR0234, M12, FOV 85°), 3D Slicer 5.4
**Stack final**: Python + OpenCV + pyigtl + 3D Slicer + SlicerIGT
**Estado**: Funcional. Calibración de pivote sub-2mm. Registración paired-point con RMS 3.46 mm.

---

## 1. Resumen Ejecutivo

El proyecto desarrolla un sistema de navegación quirúrgica que permite visualizar la posición espacial de instrumentos quirúrgicos respecto a un modelo 3D del hueso del paciente, en tiempo real. Después de 4 días de desarrollo iterativo, se logró:

- Reducir el error de calibración de pivote de **11 mm** (sistema inicial) a **1.7-2 mm** (sistema final).
- Lograr reproducibilidad sub-1mm entre calibraciones de pivote consecutivas.
- Implementar registración paired-point con RMS de 3.46 mm.
- Coherencia espacial visual funcional entre el modelo 3D y el objeto físico.

### Métricas comparativas

| Métrica | Sistema inicial | Sistema final | Mejora |
|---------|----------------|---------------|--------|
| Std calibración pivote | 11 mm | 1.7 mm | 6.5x |
| Reproducibilidad pivote (entre captures) | ±15 mm | <1 mm en XY | 15x |
| RMS registración paired-point | 29 mm | 3.46 mm | 8x |
| FPS de tracking | 5 FPS | 28-30 FPS | 6x |
| Marcadores detectados simultáneamente | 1 | 3-4 | 3-4x |

---

## 2. Arquitectura del Sistema

### 2.1. Componentes físicos

```
[Cámara SVPRO]──USB──→[PC]──TCP/IP→[3D Slicer]
       │
       ↓ ve
[Marker0 individual: hueso (ArUco 79.8mm)]
[Dodecaedro multi-marker: stylus (11 marcadores 16mm)]
[Hueso impreso 3D con cilindros de soporte]
[Stylus = tornillo Light_Arm_Screw + dodecaedro pegado encima]
```

### 2.2. Stack de software

```
Capa de aplicación:    3D Slicer 5.4 + SlicerIGT
                       ↑ OpenIGTLink (puerto 18944)
Capa de tracking:      tracker.py (Python custom)
                       ↓ usa
Capa de detección:     OpenCV 4.13 + ArUco + IPPE_SQUARE
                       ↓ usa
Capa de hardware:      cv2.VideoCapture (MSMF backend)
```

### 2.3. Diagrama de transformaciones

```
Tracker (sistema mundial = sistema de la cámara)
    │
    ├── Marker0ToTracker          (live, viene del tracker.py)
    │   │
    │   ├── DodecaedroToMarker0   (calculada en Slicer con Transform Processor)
    │   │   └── StylusTipToDodecaedro  (calibración de pivote, archivo .npy/.h5)
    │   │       └── StylusTip          (punto que representa la punta física)
    │   │
    │   └── BoneToMarker0         (calculada por Fiducial Registration Wizard)
    │       ├── Bone              (modelo STL del hueso)
    │       └── BoneSTL_Points    (puntos del modelo)
    │
    └── DodecaedroToTracker        (live, viene del tracker.py)

Physical_Points (suelto, en sistema del Tracker)
```

---

## 3. Calibración de Cámara

### 3.1. Procedimiento

Se utilizó **MRPT** (Mobile Robot Programming Toolkit) para calibrar la cámara con un patrón ajedrez 9x6 de 25mm/cuadro, capturando 30 imágenes desde distintas perspectivas a 1280x960 píxeles.

### 3.2. Resultados

```yaml
# calib_svpro_1280x960_plus.yml
camera_matrix:
  - [854.6334, 0.0, 629.9862]
  - [0.0, 851.7060, 473.3104]
  - [0.0, 0.0, 1.0]

distortion_coefficients:
  - 0.04262124
  - -0.04139516
  - 0.00361642
  - 0.00633257
  - -0.00848679

RMSE: 0.479 píxeles
```

**Para uso operativo**: la calibración se escaló a 640x480 (resolución de operación) dividiendo fx, fy, cx, cy entre 2.

### 3.3. Lección aprendida

La calibración con software académico (MRPT) supera consistentemente a la calibración integrada de OpenCV cuando se usa el mismo patrón. El RMSE de 0.479 px representa tracking sub-pixel preciso.

---

## 4. Detección de Marcadores

### 4.1. Especificaciones de marcadores

```yaml
Diccionario:    DICT_ARUCO_MIP_36h12 (76 IDs únicos disponibles)
Marker0 (hueso):
  ID: 0
  Tamaño impreso: 79.8 mm
  Función: referencia espacial del hueso

Dodecaedro (stylus):
  IDs: 151-161 (11 marcadores)
  Tamaño impreso: 16 mm (medido real, especificación 18 mm)
  Función: rigid body multi-marker para tracking del stylus
```

### 4.2. Pipeline de detección

```python
# Configuración del detector (en tracker.py)
params = cv2.aruco.DetectorParameters()
params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
detector = cv2.aruco.ArucoDetector(aruco_dict, params)

# Detección por frame
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
corners, ids, rejected = detector.detectMarkers(gray)
```

### 4.3. Estimación de pose

**Para marcador individual** (Marker0):
```python
# IPPE_SQUARE: óptimo para marcadores planares
ok, rvec, tvec = cv2.solvePnP(
    object_pts, image_pts, K, dist,
    flags=cv2.SOLVEPNP_IPPE_SQUARE
)
```

**Para rigid body multi-marker** (Dodecaedro):
```python
# Concatena puntos 3D-2D de TODOS los marcadores visibles
all_object_pts = np.concatenate([geom[mid] for mid in detecciones], axis=0)
all_image_pts = np.concatenate([corners_2d[mid] for mid in detecciones], axis=0)

# ITERATIVE para puntos no coplanares
ok, rvec, tvec = cv2.solvePnP(
    all_object_pts, all_image_pts, K, dist,
    flags=cv2.SOLVEPNP_ITERATIVE
)
# Refinamiento Levenberg-Marquardt
rvec, tvec = cv2.solvePnPRefineLM(all_object_pts, all_image_pts, K, dist, rvec, tvec)
```

### 4.4. Diagnóstico crítico del Día 1

**Problema identificado**: el detector ArUco antiguo del Plus 2.8 (versión usada inicialmente) NO usa IPPE_SQUARE y sufre de **ambigüedad planar** (flips de pose), causando std de 11 mm en pivote.

**Solución**: pipeline Python custom con OpenCV 4.13 + IPPE_SQUARE explícito.

---

## 5. Diseño del Stylus Multi-Marker

### 5.1. Decisión de diseño

El stylus inicial (lezna larga con 1 marcador a 22 cm de la punta) presentaba el problema fundamental:

```
error_tip = sin(error_angular) × distancia_palanca
error_tip = sin(2-3°) × 220mm ≈ 7-12 mm
```

Para reducir el error de palanca, se diseñó un nuevo stylus:

- **Tornillo Light_Arm_Screw** (19.80×19.80×71.30mm, cabeza esférica giratoria) como estructura base.
- **Dodecaedro impreso 3D** (Thingiverse modelo escalado 377%) sobre el tornillo.
- **11 marcadores ArUco DICT_ARUCO_MIP_36h12** pegados en las caras del dodecaedro (1 cara base sin marcador para conexión al tornillo).
- **Distancia tip-centro_dodecaedro**: ~9.6 cm (vs 22 cm original) → reducción de palanca de **2.3x**.

### 5.2. Geometría del dodecaedro

```python
# generar_reference_dodecaedro.py
phi = (1 + sqrt(5)) / 2          # razón áurea
a = 20.0                         # arista en mm (medida real)
r_in = a * phi**2 / (2 * sqrt(3 - phi))   # radio inscrito
theta = arccos(1/sqrt(5))        # ángulo polar de las caras

# 12 caras:
# - TOP:    centro en (0, 0, +r_in)
# - BASE:   centro en (0, 0, -r_in) (sin marcador, conecta al tornillo)
# - 5 caras del cinturón superior: azimuts 0, 72, 144, 216, 288°
# - 5 caras del cinturón inferior: azimuts 36, 108, 180, 252, 324° (offset 36°)
```

### 5.3. Convención de pegado

```
ID 151: cara TOP (opuesta a la base)
IDs 152-156: cinturón superior (en orden contrario al de las manecillas, vista desde TOP)
IDs 157-161: cinturón inferior (en orden contrario al de las manecillas, vista desde TOP)
```

**Validación**: ID 152 (Sup_0) e ID 157 (Inf_0) comparten arista, confirmando configuración antiprismática correcta (distancia entre centros: 23.4 mm = igual a distancia entre caras adyacentes).

---

## 6. Auto-Calibración del Rigid Body por Bundle Adjustment

### 6.1. Motivación

La geometría teórica del dodecaedro asume:
- Impresión perfecta (sin deformación).
- Pegado de marcadores perfectamente centrado.
- Caras planas y a ángulos exactos.

En realidad, hay errores de ±1-3 mm por marcador. Sin corregirlos, el tracking del rigid body tiene oscilación bimodal en Z (10 mm de variación con dodecaedro estático).

### 6.2. Procedimiento

**Paso 1: Captura de dataset**
```bash
python captura_calibracion.py --duracion 60
# Output: capturas_calibracion.npz (1760 frames con detecciones)
# 3.29 marcadores promedio por frame
# 44 pares únicos de marcadores observados juntos
# Conectividad completa: todos los 11 marcadores conectados
```

**Paso 2: Bundle adjustment**
```bash
python calibrar_rigid_body.py --max_frames 300
# Optimización con scipy.least_squares
# method='trf', loss='huber'
# 300 frames × 6 parámetros (poses) + 10 marcadores × 12 parámetros (esquinas) = 1920 parámetros
# ~9800 residuos
```

### 6.3. Resultados

```
RMSE de reproyección: 10.27 px → 0.61 px (94% reducción)

Desplazamientos respecto a geometría teórica:
- Cinturón superior (152-156): 5-7 mm
- Cinturón inferior (157-161): 27-28 mm (sistemático, no error individual)

Output: data/reference_dodecaedro_calibrado.txt
```

### 6.4. Validación: estabilidad estática

```
Test estático con dodecaedro inmóvil (90 muestras):

GEOMETRÍA TEÓRICA:
  X rango: 1.10 mm
  Y rango: 0.60 mm
  Z rango: 10.0 mm  (BIMODAL - oscilación entre clusters discretos)

GEOMETRÍA CALIBRADA:
  X rango: 0.80 mm
  Y rango: 0.20 mm
  Z rango: 2.80 mm  (ruido continuo, sin saltos)
```

La eliminación de la oscilación bimodal confirma que el bundle adjustment corrige la causa raíz del problema.

---

## 7. Calibración de Pivote

### 7.1. Procedimiento físico

1. Clavar la punta esférica del tornillo en un orificio fijo (cartón + base).
2. Pivotar el stylus haciendo conos amplios (40-60° de inclinación).
3. Mantener cámara con vista clara: 3-4 marcadores visibles simultáneamente.
4. Capturar 750+ poses durante 45 segundos.

### 7.2. Algoritmo

```python
# test_pivote.py
1. Capturar N poses M_i (matrices 4x4 del dodecaedro respecto al tracker)
2. Extraer posiciones del centro: pos_i = M_i[:3, 3]
3. Aplicar RANSAC para identificar inliers (umbral 1.5 mm)
4. Ajustar esfera a inliers: scipy.least_squares
   Output: centro_pivot (mundial), radio
5. Transformar centro_pivot al sistema del dodecaedro:
   tip_en_dodecaedro_i = inv(M_i) × centro_pivot
6. Promediar y calcular std del offset
```

### 7.3. Resultados (Test 4, mejor)

```
Total poses: 755
Marcadores promedio por pose: 3.44
Inliers RANSAC: 755/755 (100%)

Ajuste a esfera:
  Centro pivot: [-10.22, +22.52, +234.40] mm (sistema cámara)
  Radio: 88.65 mm (= distancia centro_dodecaedro a punta)
  RMSE: 0.380 mm

Offset del tip (en frame del dodecaedro):
  Promedio: [+0.315, -0.258, -88.617] mm
  STD:      [1.679, 1.447, 0.383] mm
  Magnitud: 88.62 mm
```

### 7.4. Reproducibilidad

```
Test 3 vs Test 4 (mismo setup, distinto día):
  Δ X: 0.58 mm
  Δ Y: 0.07 mm
  Δ Z: 2.53 mm (cámara levemente movida entre tests)
```

X-Y son altamente reproducibles. Z varía ligeramente cuando se mueve la cámara, lo cual es esperado.

### 7.5. Carga en 3D Slicer

La matriz `StylusTipToDodecaedro.npy` (4x4) se carga en Slicer con el script:

```python
import numpy as np
import vtk

matriz = np.load(r'C:\Dev\PoyectoNavegacion\codigo\StylusTipToDodecaedro.npy')

nodo = slicer.mrmlScene.AddNewNodeByClass(
    'vtkMRMLLinearTransformNode',
    'StylusTipToDodecaedro'
)

vtk_matriz = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        vtk_matriz.SetElement(i, j, matriz[i, j])

nodo.SetMatrixTransformToParent(vtk_matriz)
```

Una vez cargada, se puede guardar en formato `.h5` desde la interfaz de Slicer para reutilización.

---

## 8. Tracking Multi-Marker en Vivo

### 8.1. Arquitectura del tracker.py

```python
def main():
    1. Cargar configuración YAML
    2. Cargar calibración de cámara (K, dist)
    3. Cargar geometría del rigid body (reference_dodecaedro_calibrado.txt)
    4. Inicializar detector ArUco con corner refinement subpixel
    5. Inicializar servidor OpenIGTLink (puerto 18944)
    6. Abrir cámara con backend MSMF + MJPG codec

    Loop principal (30 FPS):
        1. Capturar frame
        2. Detectar marcadores ArUco
        3. Para Marker0 (individual): SOLVEPNP_IPPE_SQUARE
        4. Para Dodecaedro (rigid body):
           - Filtrar marcadores que pertenecen al RB
           - Si N >= 1: SolvePnP con 4N puntos 3D-2D combinados
           - Refinamiento LM si N >= 2
        5. Enviar transformadas vía OpenIGTLink:
           - Marker0ToTracker
           - DodecaedroToTracker
        6. Visualizar localmente (cv2.imshow)
```

### 8.2. Configuración crítica para 30 FPS

```yaml
# tracker_config.yaml
camera:
  source: 0
  width: 640
  height: 480
  fps: 30
  backend: MSMF        # CRÍTICO: DSHOW da 5 FPS, MSMF da 30 FPS
  fourcc: MJPG         # CRÍTICO: sin esto la cámara da YUYV (lento)
  calibration_file: data/camera_calibration_caja_luz.yml

igtlink:
  transforms_port: 18944
  send_video: false    # CRÍTICO: enviar video colapsa FPS

rigid_bodies:
  - name: Dodecaedro
    geometry_file: data/reference_dodecaedro_calibrado.txt

markers:
  - id: 0
    name: Marker0
    size_mm: 79.8
```

### 8.3. Razón matemática del multi-marker

Cuando se ven N marcadores del rigid body simultáneamente:

```
Sistema de ecuaciones para SolvePnP:
- N marcadores × 4 esquinas = 4N puntos 3D conocidos (en sistema del dodecaedro)
- 4N puntos 2D detectados (en imagen)
- 6 parámetros desconocidos: rotación (rvec) + translación (tvec)

Para N=3: 12 puntos 3D-2D para 6 incógnitas → sobredeterminado
- El error de cada esquina individual se promedia.
- La pose resultante es ~3x más precisa que con 1 solo marcador.
- La rotación se determina mejor porque hay puntos en distintas orientaciones.
```

---

## 9. Registración Paired-Point en 3D Slicer

### 9.1. Concepto

**Objetivo**: encontrar la transformación rígida T tal que:
```
T × BoneSTL_Points ≈ Physical_Points
```

Donde:
- `BoneSTL_Points`: puntos marcados manualmente en el modelo 3D del hueso.
- `Physical_Points`: puntos correspondientes capturados tocándolos con la lezna física.

### 9.2. Procedimiento (siguiendo regla de SlicerIGT)

**Setup inicial**:
```
1. Conectar Slicer al puerto 18944 (OpenIGTLinkIF Cliente)
2. Cargar STL del hueso
3. Cargar StylusTipToDodecaedro.h5
4. Crear DodecaedroToMarker0 con Transform Processor:
   - Mode: Compute Full Transform
   - From: DodecaedroToTracker
   - To: Marker0ToTracker
5. Crear MarkupsFiducial 'StylusTip' con punto en (0,0,0)
   y anidarlo bajo StylusTipToDodecaedro
```

**Jerarquía resultante**:
```
Marker0ToTracker
  └── DodecaedroToMarker0 (calculada con Transform Processor)
      └── StylusTipToDodecaedro (calibración de pivote)
          └── StylusTip (representa la punta física)
```

**Captura de puntos**:
```
1. Marcar 6-9 puntos en BoneSTL_Points sobre el modelo 3D del hueso
   (Bone debe estar suelto en este momento, sin transformaciones)
2. Configurar Fiducial Registration Wizard:
   - From fiducials: BoneSTL_Points
   - To fiducials: Physical_Points (vacío)
   - Place 'To': StylusTipToDodecaedro
   - Result transform: BoneToMarker0
   - Result type: Rigid
   - Auto-update: ON
3. Para cada punto físico:
   - Tocar el cilindro físico correspondiente con la punta
   - Click "Place 'To'"
4. El wizard calcula automáticamente BoneToMarker0
```

**Aplicación de la registración**:
```
Mover en jerarquía:
- BoneToMarker0 → bajo Marker0ToTracker
- Bone → bajo BoneToMarker0
- BoneSTL_Points → bajo BoneToMarker0  (CRÍTICO: para que se vean coincidiendo con Physical_Points)
- Physical_Points → suelto en raíz
```

### 9.3. Lección crítica del Día 4

**El descubrimiento clave**: tanto `Bone` como `BoneSTL_Points` deben anidarse bajo `BoneToMarker0`. Si solo se anida `Bone`, los puntos del modelo permanecen en su sistema STL nativo y no coinciden visualmente con los `Physical_Points`.

Cuando ambos están anidados:
- El modelo `Bone` se mueve al sistema de Marker0.
- Los `BoneSTL_Points` se transforman al mismo sistema.
- Visualmente coinciden (con el error de RMS) con los `Physical_Points`.

### 9.4. Resultados

```
RMS Error final: 3.46 mm (después de eliminar punto outlier)
RMS inicial: 8.0 mm
Mejora: 56.7%

Análisis de pares:
- Correlación entre distancias Bone vs Physical: 0.991
- Diferencias promedio: 1.82 mm
- Std diferencias: 1.5 mm

Punto P6 identificado como outlier por análisis sistemático:
- Diferencia con todos los demás: 5-16 mm
- Causa probable: cilindro pequeño difícil de localizar consistentemente
```

---

## 10. Estructura del Código

### 10.1. Directorio del proyecto

```
C:\Dev\PoyectoNavegacion\codigo\
├── .venv\                                    # Python 3.11.9 virtual env
├── tracker.py                                # Tracker principal multi-marker
├── tracker_config.yaml                       # Configuración del tracker
├── captura_calibracion.py                    # Captura dataset para BA
├── calibrar_rigid_body.py                    # Bundle adjustment del rigid body
├── test_pivote.py                            # Calibración de pivote standalone
├── captura_manual_puntos.py                  # Helper Python para Slicer
├── generar_reference_dodecaedro.py           # Genera geometría teórica
├── generar_pdfs.py                           # Genera PDFs de marcadores ArUco
├── data\
│   ├── camera_calibration_caja_luz.yml       # Calibración intrínseca cámara
│   ├── reference_dodecaedro.txt              # Geometría teórica
│   ├── reference_dodecaedro_calibrado.txt    # Geometría auto-calibrada (BA)
│   └── ...
├── capturas_calibracion.npz                  # Dataset BA (1760 frames)
├── poses_pivote_dodecaedro.npy               # Última calibración pivote
├── StylusTipToDodecaedro.npy                 # Matriz pivote (formato numpy)
├── StylusTipToDodecaedro.txt                 # Matriz pivote (texto + metadatos)
└── StylusTipToDodecaedro.h5                  # Matriz pivote (formato Slicer)
```

### 10.2. Dependencias Python

```bash
pip install opencv-contrib-python==4.13.0.92
pip install pyigtl==0.3.1
pip install numpy
pip install PyYAML
pip install scipy
```

---

## 11. Procedimiento Completo de Reproducción

### 11.1. Setup inicial (una sola vez)

**Paso 1**: Imprimir físicamente:
- Hueso impreso 3D (con cilindros de soporte como rasgos identificables).
- Dodecaedro escalado 377% (arista 20mm).
- Tornillo Light_Arm_Screw modificado (cabeza esférica giratoria).
- Patrón de calibración 9x6 cuadros de 25mm.

**Paso 2**: Imprimir marcadores ArUco:
```bash
python generar_pdfs.py  # Output: marcadores_ARUCO_MIP_36h12.pdf
```
Imprimir tamaño 16mm para los IDs 151-161 (dodecaedro) y tamaño 79.8mm para el ID 0 (Marker0).

**Paso 3**: Pegar marcadores:
- ID 151 en cara TOP del dodecaedro (opuesta a la base).
- IDs 152-156 en cinturón superior.
- IDs 157-161 en cinturón inferior.
- Convención: ID hacia abajo (hacia la punta del stylus).
- Validar que IDs 152 y 157 comparten una arista.

### 11.2. Calibración de cámara (una sola vez por configuración óptica)

```bash
# Capturar 30+ imágenes del patrón ajedrez desde distintas perspectivas
# Procesar con MRPT a 1280x960
# Output: data/camera_calibration_caja_luz.yml
# Verificar: RMSE < 1 píxel
```

### 11.3. Auto-calibración del rigid body (una sola vez por dodecaedro)

```bash
cd C:\Dev\PoyectoNavegacion\codigo
.\.venv\Scripts\activate

# Captura dataset (60 segundos rotando dodecaedro)
python captura_calibracion.py --duracion 60
# Output: capturas_calibracion.npz

# Bundle adjustment (3-10 min)
python calibrar_rigid_body.py --max_frames 300
# Output: data/reference_dodecaedro_calibrado.txt
# Verificar: RMSE final < 1 px
```

### 11.4. Calibración de pivote (cada vez que se ensambla el stylus)

```bash
python test_pivote.py --duracion 45
# Pivotar con punta clavada y 3-4 marcadores visibles
# Output: StylusTipToDodecaedro.npy + .txt
# Verificar: std XY < 2 mm
```

Importar a Slicer manualmente o convertir a .h5.

### 11.5. Sesión de uso (cada vez que se navega)

**Paso 1**: Lanzar tracker
```bash
python tracker.py --config tracker_config.yaml
```

**Paso 2**: Configurar Slicer
```
1. Abrir Slicer 5.4
2. OpenIGTLinkIF: Cliente localhost:18944, Active
3. File → Add Data: cargar STL del hueso
4. File → Add Data: cargar StylusTipToDodecaedro.h5
5. Transform Processor: crear DodecaedroToMarker0 (Compute Full Transform)
6. Consola Python: crear nodo StylusTip y anidarlo
7. Construir jerarquía:
   Marker0ToTracker
     └─ DodecaedroToMarker0
         └─ StylusTipToDodecaedro
             └─ StylusTip
```

**Paso 3**: Marcar puntos del modelo
```
1. Crear MarkupsFiducial BoneSTL_Points (Bone debe estar suelto)
2. Marcar 6-9 puntos sobre cilindros del modelo 3D
3. Crear MarkupsFiducial Physical_Points (vacío)
```

**Paso 4**: Registración
```
1. Fiducial Registration Wizard:
   - From: BoneSTL_Points
   - To: Physical_Points
   - Place To: StylusTipToDodecaedro
   - Result: BoneToMarker0 (crear nuevo)
2. Tocar puntos físicos uno por uno con la lezna
3. Click Place To para cada uno
4. Verificar RMS Error < 5 mm
```

**Paso 5**: Aplicar registración
```
En módulo Data:
- Mover BoneToMarker0 bajo Marker0ToTracker
- Mover Bone bajo BoneToMarker0
- Mover BoneSTL_Points bajo BoneToMarker0
- Dejar Physical_Points suelto
```

**Paso 6**: Verificar coherencia espacial
```
- Mover el hueso físicamente: el modelo virtual debe seguirlo
- Tocar un cilindro físico con la lezna: el punto Tip virtual debe coincidir con el cilindro virtual correspondiente
```

---

## 12. Aprendizajes Clave

### 12.1. Sobre detección de marcadores

1. **La ambigüedad planar mata la calibración**. Detector ArUco antiguo de Plus 2.8 sufre de flips de pose. Usar SOLVEPNP_IPPE_SQUARE explícito.

2. **MSMF >> DSHOW en Windows** para webcams UVC. DSHOW ignora cv2.CAP_PROP_FOURCC silenciosamente, dando 5 FPS en lugar de 30.

3. **Corner refinement subpixel** es esencial. Sin esto, std de pose es 2-3x peor.

### 12.2. Sobre rigid body multi-marker

1. **3+ marcadores visibles** es la condición para tracking sub-milimétrico. Con 1-2 marcadores hay ruido grande.

2. **Bundle adjustment es necesario** para corregir errores de pegado. Sin él, oscilación bimodal en eje Z.

3. **Anclar 1 marcador** durante el BA es necesario para evitar deriva del sistema de coordenadas global.

### 12.3. Sobre calibración de pivote

1. **Reducir la palanca** entre marcador y punta es crítico. Cada cm de palanca multiplica el error angular del detector.

2. **RANSAC para outliers** en pivote: el ajuste a esfera puede ser engañado por poses con marcadores parcialmente ocultos.

3. **Reproducibilidad entre captures** es la métrica que importa, no solo el std de una captura.

### 12.4. Sobre 3D Slicer y SlicerIGT

1. **Transform Processor** es esencial para convertir de sistema de tracker a sistema de referencia (Marker0).

2. **Fiducial Registration Wizard ignora padres de fiducials**. Los puntos se guardan en sistema mundial al momento de la captura.

3. **Para visualización correcta**: tanto el modelo como sus puntos deben anidarse bajo la transformada output del wizard.

### 12.5. Sobre el flujo de trabajo

1. **Validar cuantitativamente cada paso** ahorra tiempo: detectar problemas pronto evita debuggear capas más arriba.

2. **Test estático antes de dinámico**: si el sistema oscila estando quieto, no funcionará en uso.

3. **El demo visual no es el test**: ojo humano puede no ver 5 mm de error, pero los datos numéricos lo capturan.

---

## 13. Limitaciones Actuales y Trabajo Futuro

### 13.1. Limitaciones identificadas

1. **Resolución de cámara 640x480** limita la precisión sub-pixel.
2. **Punta esférica del tornillo** introduce ambigüedad de 3-5 mm al tocar cilindros.
3. **Marcadores de 16 mm** podrían ser más grandes para mejor detección a distancia.
4. **FOV de 85°** introduce distorsión radial que limita precisión en bordes.

### 13.2. Mejoras propuestas

1. **Subir resolución a 1280x960**: probablemente bajaría std de pivote a < 1 mm.
2. **Punta cónica afilada**: tocaría exactamente el centro del cilindro.
3. **Marcadores de 20-25 mm**: mejor precisión a distancias de operación.
4. **Cámara con FOV 50-60°**: menos distorsión, más resolución por mm.
5. **1-Euro filter en tracking**: reducir jitter sin lag.
6. **Múltiples cámaras**: triangulación stereoscópica para Z más preciso.
7. **Marcadores AprilTag** (mejor robustez que ArUco MIP).

### 13.3. Iteración inmediata

Para la próxima sesión, los pasos lógicos son:

1. Capturar puntos físicos con técnica más estricta (mejorar el RMS de 3.46 mm).
2. Probar con punta cónica si se puede obtener.
3. Subir resolución de operación a 1280x960 manteniendo el pipeline actual.
4. Implementar visualización en tiempo real de coherencia espacial (no solo registración estática).

---

## Apéndice A: Archivos Generados

| Archivo | Descripción | Origen |
|---------|-------------|--------|
| `data/camera_calibration_caja_luz.yml` | Calibración intrínseca cámara | MRPT con patrón 9x6 |
| `data/reference_dodecaedro.txt` | Geometría teórica del rigid body | `generar_reference_dodecaedro.py` |
| `data/reference_dodecaedro_calibrado.txt` | Geometría auto-calibrada | `calibrar_rigid_body.py` (BA) |
| `capturas_calibracion.npz` | Dataset 1760 frames para BA | `captura_calibracion.py` |
| `StylusTipToDodecaedro.npy` | Matriz 4x4 calibración pivote | `test_pivote.py` |
| `StylusTipToDodecaedro.h5` | Misma matriz, formato Slicer | Slicer (export) |
| `marcadores_ARUCO_MIP_36h12.pdf` | PDF imprimible con marcadores | `generar_pdfs.py` |

## Apéndice B: Estado Final Validado

```
Sistema funcional:
✓ Tracking 30 FPS con multi-marker
✓ Detección estable 3-4 marcadores promedio
✓ Calibración pivote sub-2mm reproducible
✓ Auto-calibración rigid body con RMSE 0.61 px
✓ Registración paired-point RMS 3.46 mm
✓ Coherencia espacial visual demostrada en 3D Slicer
✓ Pipeline completo documentado y reproducible

Datos cuantitativos del estado final:
- Calibración cámara RMSE: 0.479 px
- Bundle adjustment RMSE: 0.61 px
- Calibración pivote std: [1.68, 1.45, 0.38] mm
- Reproducibilidad pivote ΔXY: < 1 mm
- Registración paired-point: RMS 3.46 mm
- Frames per second: 28-30 FPS estables
```

---

**Documento generado**: Día 4 del proyecto
**Estado**: Sistema operativo, listo para presentación de revisión
**Siguiente fase**: Iteración para mejorar precisión y robustez
