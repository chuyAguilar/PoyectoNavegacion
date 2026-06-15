# 06 — Workflow operativo de 3D Slicer (Etapas G + H + I)

**Manual paso a paso de qué pasa en Slicer después de ejecutar `tracker.py`.** Consolidación de la jerarquía validada en iter 1 + scripts de carga + procedimiento de paired-point.

**Audiencia**: Dr. Milton u otro operador del sistema. Listo para copiar/pegar comandos.

---

## ⚠️ ACTUALIZACIÓN ITER 4 (2026-06-15) — leer antes de seguir

El flujo de Slicer de abajo (jerarquía, Observer Python §J3, verificación §J4,
Reslice Driver, troubleshooting) **sigue válido sin cambios**. Solo cambian
estos datos respecto a iter 2/3:

| Dato | iter 2/3 (texto viejo) | iter 4 (usar esto) |
|---|---|---|
| **Archivo del tip** | `codigo\StylusTipToDodecaedro.npy` | `codigo\iter4\data\StylusTipToDodecaedro_viejo_dock.npy` |
| **Cómo se calibró el tip** | pivote clásico (`test_pivote.py`) | calibración por DOCK (`iter4\calibrar_tip_divot.py --divot DOCK`, spread 0.92 mm) |
| **Marker del paciente (Marker0)** | 60.8 mm | **80.0 mm** (`iter4\tracker_config.yaml`) |
| **Distancia centro_dod → tip (§J4)** | ~91 mm | **~93 mm** (magnitud del dock) |
| **Tracker** | `python tracker.py` | `python iter4\tracker.py --config iter4\tracker_config.yaml` |

En TODOS los snippets de Python de abajo, reemplazar la ruta del `.npy` por la
de iter 4. Los nombres de transforms (`Marker0ToTracker`, `DodecaedroToTracker`,
`StylusTipToDodecaedro`) NO cambian.

---

## 0. Prerequisitos (antes de abrir Slicer)

| Item | Cómo verificar |
|---|---|
| `tracker.py` corriendo en otra terminal | Ventana de OpenCV abierta, marca "Dodecaedro: N markers" con N≥3 |
| Calibración de pivote actualizada | `codigo/StylusTipToDodecaedro.npy` existe, fecha reciente |
| STL del hueso disponible | Archivo `.stl` que coincida con el paciente |
| Tomografía DICOM (si se va a usar) | Carpeta con archivos `.dcm` |

Asumimos también: dodecaedro físico armado, cámara enchufada y enfocada, marker 0 (referencia ósea) pegado al phantom, todos los markers visibles.

---

## 1. Etapa G1 — Conectar OpenIGTLink (recibir transformadas del tracker)

1. Abrir 3D Slicer.
2. Módulo: **`OpenIGTLink IF`** (busca con la lupa si no está visible).
3. En el panel del módulo:
   - Click **`+`** para agregar una conexión nueva.
   - Tipo: **Client**.
   - Hostname: `localhost`.
   - Port: `18944`.
4. Marcar el checkbox **Active**.
5. En la lista de la conexión deberían empezar a aparecer dos transforms recibidas en tiempo real:
   - `Marker0ToTracker`
   - `DodecaedroToTracker`

**Validación**: en `Data` module verifás que aparezcan ambos nodos. Sus valores se actualizan ~30 veces por segundo.

**Troubleshooting**:
- Si no conecta: confirmar que tracker.py está corriendo y que el firewall de Windows no bloquea el puerto 18944.
- Si conecta pero no aparecen transforms: probablemente `tracker.py` se cerró o no está enviando.

---

## 2. Etapa G2 — Cargar la calibración de pivote (StylusTipToDodecaedro)

Slicer no carga directamente `.npy`. Hay que usar Python para crear el `vtkMRMLLinearTransformNode` con la matriz.

Abrir **`View → Python Console`** y pegar:

```python
import numpy as np
import vtk

# Cargar la matriz desde el .npy generado por test_pivote.py
ruta = r"C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\StylusTipToDodecaedro.npy"
M = np.load(ruta)
print("Matriz cargada:")
print(M)

# Crear nodo en Slicer
node = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "StylusTipToDodecaedro"
)
m = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        m.SetElement(i, j, float(M[i, j]))
node.SetMatrixTransformToParent(m)
print(f"Transform creado: {node.GetName()}")
```

**Validación**: en `Data` module debería aparecer `StylusTipToDodecaedro` como Linear Transform.

---

## 3. Etapa G3 — Composición DodecaedroToMarker0 (Transform Processor)

Necesitamos llevar la pose del dodecaedro al **frame del paciente** (marker 0). Se calcula como:

```
DodecaedroToMarker0 = inv(Marker0ToTracker) · DodecaedroToTracker
```

Slicer lo hace automáticamente con el módulo Transform Processor:

1. Módulo: **`Transform Processor`**.
2. Configuración:
   - **Processing mode**: `Compute Full Transform`.
   - **Reference (from)**: `Marker0ToTracker`.
   - **Movable (to)**: `DodecaedroToTracker`.
   - **Output transform**: click "Create new..." → nombre `DodecaedroToMarker0`.
3. Marcar **Update mode: Auto** (se recalcula en cada nuevo dato).
4. Click **Update** una vez para crear el nodo.

**Validación**: aparece `DodecaedroToMarker0` en la lista. Sus valores cambian con el movimiento del dodecaedro físico.

---

## 4. Etapa G4 — Anidar transformadas en cadena (importante)

Por default Slicer deja todos los nodos en root. Tenemos que armar la cadena correcta para que las posiciones sean coherentes en el frame Tracker.

En Python Console:

```python
# Cadena: Marker0ToTracker → DodecaedroToMarker0 → StylusTipToDodecaedro
marker0 = slicer.util.getNode("Marker0ToTracker")
dod_to_m0 = slicer.util.getNode("DodecaedroToMarker0")
stylus = slicer.util.getNode("StylusTipToDodecaedro")

dod_to_m0.SetAndObserveTransformNodeID(marker0.GetID())
stylus.SetAndObserveTransformNodeID(dod_to_m0.GetID())
print("Cadena armada: Marker0 ← DodecaedroToMarker0 ← StylusTipToDodecaedro")
```

**Validación**: en `Data` module, pestaña `Transform hierarchy`, debería verse:

```
Marker0ToTracker
  └── DodecaedroToMarker0
        └── StylusTipToDodecaedro
```

`DodecaedroToTracker` queda en root (no se anida — es input, no se transforma).

---

## 5. Etapa G5 — Crear StylusTip (punto en la punta del stylus)

```python
# Crear MarkupsFiducial en (0,0,0) del frame del stylus
tip_node = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLMarkupsFiducialNode", "StylusTip"
)
tip_node.AddControlPoint([0, 0, 0])
# Anidar bajo StylusTipToDodecaedro
stylus = slicer.util.getNode("StylusTipToDodecaedro")
tip_node.SetAndObserveTransformNodeID(stylus.GetID())
print("StylusTip creado y anidado")
```

**Validación**: mover el stylus físico → ver `StylusTip` moviéndose en la 3D View.

---

## 6. Etapa G6 — Cargar el modelo STL del hueso (Bone)

1. `File → Add Data` → seleccionar archivo `.stl` del hueso.
2. Aceptar opciones default (no marcar "Show options").
3. El nodo aparece como `Bone` (o el nombre del archivo) en root, sin transform padre.

**No le asignés transform padre todavía.** Eso viene después del paired-point.

---

## 7. Etapa G7 — Marcar BoneSTL_Points sobre el modelo STL

1. Módulo **`Markups`** → click **`+ Create new MarkupsFiducial`** (botón con icono de cruz roja).
2. Nombre: `BoneSTL_Points`.
3. **Dejarlo en root** (sin transform padre).
4. Click en el botón **`Place`** (lápiz rojo) o atajo `Ctrl+Shift+A`.
5. En la **3D View**, click sobre features anatómicas reconocibles del STL: vértices de procesos espinosos, esquinas de procesos articulares, etc.
6. Marcá **entre 6 y 9 puntos** distribuidos espacialmente (no todos cerca uno del otro).

**Criterio de elección de puntos**:
- Distribución 3D (no coplanares).
- Features identificables a OJO también en el hueso físico (no zonas suaves del modelo).
- Si el hueso físico tiene guías quirúrgicas encima, evitar zonas tapadas por guías.

---

## 8. Etapa G8 — Crear Physical_Points (vacío, anidado bajo Marker0ToTracker)

```python
phys = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLMarkupsFiducialNode", "Physical_Points"
)
m0 = slicer.util.getNode("Marker0ToTracker")
phys.SetAndObserveTransformNodeID(m0.GetID())
print("Physical_Points creado, anidado bajo Marker0ToTracker")
```

Importante: **NO marcar puntos todavía**. El nodo está vacío. Los puntos se van a capturar tocando con la punta del stylus físico.

---

## 9. Etapa G9 — Configurar Fiducial Registration Wizard

1. Módulo **`Fiducial Registration Wizard`**.
2. Configuración del wizard:
   - **From fiducials**: `BoneSTL_Points`.
   - **To fiducials**: `Physical_Points`.
   - **Place "From" fiducials in**: `None`.
   - **Place "To" fiducials in**: `StylusTipToDodecaedro` ← (la hoja de la cadena del stylus; es donde "vive" la punta).
   - **Output transform**: click "Create new..." → nombre `BoneToMarker0`.
   - **Transform type**: `Rigid`.
   - **Update mode**: `Manual` (después podés cambiarlo a Auto).
   - **Auto-update**: marcar ON.

---

## 10. Etapa G10 — Capturar Physical_Points

1. Con el wizard configurado, en la sección **"To fiducials"** debería haber un botón **`Record point`** (también puede aparecer como icono de cámara).
2. **Tocá con la punta del stylus físico el mismo feature anatómico que marcaste como BoneSTL_Points punto 1**, mantené firme, click **Record point**.
3. **Mismo orden**: BoneSTL_Points[1] ↔ Physical_Points[1], BoneSTL_Points[2] ↔ Physical_Points[2], etc.
4. Repetir hasta tener la misma cantidad de Physical_Points que BoneSTL_Points.

**Tip**: si te equivocás en un punto, podés borrarlo del nodo `Physical_Points` en el módulo `Markups` y volver a capturar.

---

## 11. Etapa G11 — Calcular el registro

1. Cuando ambos sets tengan la misma cantidad de puntos, en el wizard click **`Update Registration`**.
2. El wizard reporta el **RMS** del registro.

**Criterios**:
- RMS < 2 mm → **excelente**.
- RMS 2-4 mm → **bueno** (iter 1 fue 3.46 mm, iter 2 actual estaría en ese rango).
- RMS > 5 mm → algo está mal: puntos en orden distinto, puntos físicamente mal seleccionados, o problema upstream (BA, pivote).

Si RMS es alto, revisar antes de continuar.

---

## 12. Etapa G12 — JERARQUÍA FINAL (paso crítico aprendido de iter 1)

Una vez calculado `BoneToMarker0`, hay que **mover varios nodos** a sus padres correctos. **Este es el paso que costó horas en iter 1 hasta entenderlo.**

```python
# Get nodes
bone_to_marker = slicer.util.getNode("BoneToMarker0")
marker0 = slicer.util.getNode("Marker0ToTracker")
bone_stl = slicer.util.getNode("Bone")          # el modelo STL
bone_points = slicer.util.getNode("BoneSTL_Points")

# 1. BoneToMarker0 va bajo Marker0ToTracker (para que viaje con el paciente)
bone_to_marker.SetAndObserveTransformNodeID(marker0.GetID())

# 2. El modelo Bone va bajo BoneToMarker0
bone_stl.SetAndObserveTransformNodeID(bone_to_marker.GetID())

# 3. CRÍTICO: BoneSTL_Points TAMBIÉN va bajo BoneToMarker0
#    (si quedan sueltos en root, el STL se ve bien pero los puntos no, y el RMS
#    falsamente parece malo).
bone_points.SetAndObserveTransformNodeID(bone_to_marker.GetID())

# Physical_Points SE QUEDA bajo Marker0ToTracker (no se toca).

print("Jerarquía final armada.")
```

### Jerarquía final esperada

```
Marker0ToTracker                          ← live, del tracker
  ├── DodecaedroToMarker0                 ← del Transform Processor
  │     └── StylusTipToDodecaedro         ← carga de calibración de pivote
  │           └── StylusTip               ← MarkupsFiducial (0,0,0)
  │
  ├── BoneToMarker0                       ← del Fiducial Reg Wizard
  │     ├── Bone                          ← modelo STL del hueso
  │     └── BoneSTL_Points                ← CRÍTICO
  │
  └── Physical_Points                     ← se queda acá

DodecaedroToTracker                       ← root (input para Transform Processor)
```

---

## 13. Etapa G13 — Validación visual

Mirá la **3D View**:
- ¿El modelo `Bone` aparece sobre el hueso real del paciente (visualmente coherente)?
- ¿Cuando movés el stylus en el espacio, el `StylusTip` se mueve coherentemente sobre la superficie del modelo?
- ¿`BoneSTL_Points` y `Physical_Points` coinciden visualmente (o están cerca)?

Si las tres respuestas son sí, **el registro está funcional** y el sistema está listo para uso.

---

## 14. Operación normal

Una vez configurada la sesión, el sistema queda funcionando solo:
- Movés el stylus → `StylusTip` se actualiza en tiempo real.
- Movés el paciente (marker 0) → todo el modelo virtual lo sigue.

Para una sesión nueva (mismo paciente, mismo phantom):
- Bastaría salvar el `.mrml` de la escena actual y abrirlo.
- Re-conectar OpenIGTLink (puede que la conexión TCP no se restaure automáticamente).
- Verificar que la jerarquía siga intacta y que el RMS del registro no se rompió.

Para un paciente nuevo o ensamblaje físico nuevo:
- Re-correr el pipeline completo de calibración (BA + pivote) antes.
- Re-marcar BoneSTL_Points + capturar Physical_Points + recalcular BoneToMarker0.

---

## 15. Lo que NO se debe hacer (errores típicos)

| Error | Consecuencia | Cómo evitarlo |
|---|---|---|
| Dejar `BoneSTL_Points` sin transform padre después del registro | Modelo bien alineado pero puntos sueltos, parece error del RMS | Aplicar paso G12 punto 3 |
| Anidar `Physical_Points` bajo `BoneToMarker0` | Doble transformación, RMS infla | Dejarlos bajo Marker0ToTracker |
| Capturar Physical_Points sin tocar firme | Movimiento durante captura inyecta ruido | Apoyar la punta y esperar 1 seg antes del Record |
| Capturar puntos en distinto orden | Wizard hace mapping 1-a-1, descoloca todo | Mantener mismo orden estricto |
| Olvidar marcar "Place 'To' fiducials in: StylusTipToDodecaedro" | Los Physical_Points se ubican en el frame equivocado | Verificar antes de empezar a capturar |
| Mover el marker 0 durante la captura de Physical_Points | El frame Marker0 cambia mid-captura, registro queda inconsistente | Asegurar que marker 0 esté pegado firme y no se mueva |

---

## Anexo: Snippet completo para reproducir la sesión rápido

Una vez que tenés todo configurado, este script en Python Console reconstruye TODO el setup base (asumiendo que tracker.py ya está corriendo y la conexión OpenIGTLink ya está activa):

```python
import numpy as np, vtk

# 1. Cargar pivote
M = np.load(r"C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\StylusTipToDodecaedro.npy")
stylus = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "StylusTipToDodecaedro")
m = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        m.SetElement(i, j, float(M[i, j]))
stylus.SetAndObserveTransformNodeID(None)  # asegurar que no tiene padre antes de setear matriz
stylus.SetMatrixTransformToParent(m)

# 2. StylusTip
tip = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "StylusTip")
tip.AddControlPoint([0, 0, 0])
tip.SetAndObserveTransformNodeID(stylus.GetID())

# 3. Physical_Points vacío bajo Marker0ToTracker (asumiendo que ya está recibido)
m0 = slicer.util.getNode("Marker0ToTracker")
phys = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "Physical_Points")
phys.SetAndObserveTransformNodeID(m0.GetID())

print("Setup base listo. Falta: Transform Processor (G3), cargar STL (G6), marcar BoneSTL_Points (G7), wizard (G9-G11), reanidar (G12).")
```

Los pasos G3 (Transform Processor), G6-G7 (STL + puntos), y G9-G11 (wizard) son GUI — no se pueden scriptear cómodamente.

---

# ITER 3 — Visualización tomográfica navegada

**Objetivo cumplido 2026-05-22**: las 3 vistas 2D de Slicer (Red/Yellow/Green = axial/sagital/coronal) muestran cortes del CT del paciente que **se actualizan en tiempo real para pasar por la punta del stylus**.

Esta sección consolida el flujo de iter 3, con scripts listos para copiar/pegar.

## ITER 3 — Prerequisitos adicionales

Además de los de Etapa F (tracker corriendo, calibración pivote disponible, STL del hueso), iter 3 requiere:
- **STL del hueso generado desde el mismo DICOM del paciente** (sin transforms aplicados al exportar). Ver §J0 abajo.
- **Carpeta DICOM** del paciente importable en Slicer.

## J0 — Generar STL del hueso desde el DICOM (una vez por paciente)

Si el STL existente NO coincide con el DICOM al cargarlos (lo detectás comparando centros con script de §J2), hay que generar uno nuevo. Se hace **en una escena aparte de Slicer** para no contaminar la sesión de tracking:

1. Abrí una escena nueva de Slicer.
2. Cargá el DICOM del paciente (`Modules → DICOM → Import → seleccionar carpeta → Load serie de mayor cantidad de cortes axiales`).
3. Módulo `Segment Editor`:
   - Source volume: la serie cargada.
   - `+ Add` → renombrar a `Bone_CT`.
   - `Threshold` → range `200` a `3000` HU (o hasta el máximo si el CT no llega a 3000) → `Apply`.
   - `Islands` → mode `Keep largest island` → `Apply` (elimina ruido del intestino y huesos no conectados).
   - `Scissors` → recortar regiones no deseadas (costillas, fémures, etc.). Dejar solo L1-L5 + sacro.
   - `Smoothing` → method `Median`, kernel 2 mm → `Apply` (opcional, suaviza superficies).
4. Módulo `Segmentations` → sección `Export to files`:
   - Destination folder: carpeta del proyecto (ej: `C:\Dev\Dr.Milton\PoyectoNavegacion\stl\`).
   - Reference volume: la serie del CT (CRÍTICO para preservar coordenadas).
   - File format: STL.
   - Coordinate system: LPS (default DICOM, Slicer lo lee bien).
   - Click `Export`.
5. Cargar el STL nuevo en la misma escena para verificar que coincide visualmente con el volumen.
6. Cerrar esa escena (guardarla si querés) y abrir una limpia para la sesión de tracking.

**Validación**: el STL nuevo se carga **sin transform padre** y debe verse alineado al volumen DICOM en la 3D View. Si no coincide, la segmentación tiene un transform aplicado o se exportó mal.

## J1 — Importar DICOM en la escena de tracking

Una vez la escena de tracking armada (Etapas G1-G12), agregar el volumen DICOM:

1. Módulo `DICOM` → `Import DICOM files` → seleccionar la carpeta raíz del paciente.
2. Click sobre el paciente para que aparezcan los estudios.
3. Click sobre el estudio para que aparezcan las series.
4. Identificar la serie útil para navegación (mayor cantidad de cortes axiales, e.g. "AXIAL 301 slices").
5. Doble click sobre la serie → cargar.

## J2 — Verificar coincidencia STL ↔ DICOM (opcional pero recomendado)

```python
# Comparar bounds y centros para confirmar que STL y volumen comparten frame
import numpy as np
volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
volume = volumes[0] if volumes else None
bone = slicer.util.getNodesByClass("vtkMRMLModelNode")
bone = bone[0] if bone else None
if volume and bone:
    parent_orig = bone.GetParentTransformNode().GetID() if bone.GetParentTransformNode() else None
    bone.SetAndObserveTransformNodeID(None)  # quitar transform padre temporalmente
    vb = [0]*6; volume.GetRASBounds(vb)
    bb = [0]*6; bone.GetRASBounds(bb)
    cv = np.array([(vb[0]+vb[1])/2, (vb[2]+vb[3])/2, (vb[4]+vb[5])/2])
    cb = np.array([(bb[0]+bb[1])/2, (bb[2]+bb[3])/2, (bb[4]+bb[5])/2])
    print(f"Distancia centros: {np.linalg.norm(cv - cb):.1f} mm")
    if parent_orig:
        bone.SetAndObserveTransformNodeID(parent_orig)
```

Si la distancia entre centros es <50 mm y el STL está dentro de los bounds del volumen, coinciden.
Si la distancia es >150 mm o el STL se sale del volumen, hay que regenerar el STL (volver a §J0).

## J3 — Observer Python para Transform Processor (PARCHE OBLIGATORIO)

**Lección aprendida iter 3**: el módulo `Transform Processor` puede dejar de auto-actualizar a pesar de tener el checkbox tildado. Resultado: `DodecaedroToMarker0` queda con valores viejos y todo el sistema queda inconsistente.

**Solución robusta**: reemplazar Transform Processor por un observer Python. Pegar SIEMPRE este snippet después de armar la cadena (Etapa G4):

```python
import vtk

m0_node = slicer.util.getNode("Marker0ToTracker")
dt_node = slicer.util.getNode("DodecaedroToTracker")

# Crear el nodo de salida si no existe
try:
    d2m0_node = slicer.util.getNode("DodecaedroToMarker0")
except:
    d2m0_node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLinearTransformNode", "DodecaedroToMarker0")

def recompute_d2m0(caller=None, event=None):
    m_inv = vtk.vtkMatrix4x4()
    m0_node.GetMatrixTransformToWorld(m_inv)
    vtk.vtkMatrix4x4.Invert(m_inv, m_inv)
    m_dt = vtk.vtkMatrix4x4()
    dt_node.GetMatrixTransformToWorld(m_dt)
    m_new = vtk.vtkMatrix4x4()
    vtk.vtkMatrix4x4.Multiply4x4(m_inv, m_dt, m_new)
    d2m0_node.SetMatrixTransformToParent(m_new)

recompute_d2m0()
dt_node.AddObserver(slicer.vtkMRMLLinearTransformNode.TransformModifiedEvent, recompute_d2m0)
m0_node.AddObserver(slicer.vtkMRMLLinearTransformNode.TransformModifiedEvent, recompute_d2m0)
print("Observer Python instalado para DodecaedroToMarker0")
```

## J4 — Verificación obligatoria de coherencia ANTES de avanzar

```python
import vtk, numpy as np
m_dt = vtk.vtkMatrix4x4()
slicer.util.getNode("DodecaedroToTracker").GetMatrixTransformToWorld(m_dt)
m_m0 = vtk.vtkMatrix4x4()
slicer.util.getNode("Marker0ToTracker").GetMatrixTransformToWorld(m_m0)
m_d2m0 = vtk.vtkMatrix4x4()
slicer.util.getNode("DodecaedroToMarker0").GetMatrixTransformToParent(m_d2m0)
m_comp = vtk.vtkMatrix4x4()
vtk.vtkMatrix4x4.Multiply4x4(m_m0, m_d2m0, m_comp)
t_d = [m_dt.GetElement(i,3) for i in range(3)]
t_c = [m_comp.GetElement(i,3) for i in range(3)]
print(f"Diff Marker0*DodToM0 vs DodToTracker: {np.linalg.norm(np.array(t_d) - np.array(t_c)):.3f} mm  (debe ser < 1 mm)")
tip = slicer.util.getNode("StylusTip")
pos_tip = [0,0,0]; tip.GetNthControlPointPositionWorld(0, pos_tip)
dist = np.linalg.norm(np.array(t_d) - np.array(pos_tip))
print(f"Distancia centro_dod -> tip: {dist:.1f} mm  (esperado ~91 mm, valor del pivote)")
```

Si ambos checks pasan → seguir. Si fallan → revisar J3 y volver a aplicarlo.

## J5 — Jerarquía iter 3 (corregida, validada visualmente)

Después del Fiducial Registration Wizard (que crea `BoneToMarker0`), la jerarquía final que **funciona en iter 3** es:

```
Marker0ToTracker (live, root)
  ├── Locator_Marker0ToTracker
  └── DodecaedroToMarker0
        └── StylusTipToDodecaedro
              └── StylusTip

DodecaedroToTracker (live, root)
  └── Locator_DodecaedroToTracker

BoneToMarker0 (root)             <- NO bajo Marker0ToTracker en iter 3
  ├── Segmentation_Bone_CT       <- el STL nuevo del paciente
  ├── BoneSTL_Points
  └── 202: AXIAL                 <- el volumen DICOM

Physical_Points (root)            <- NO bajo Marker0ToTracker en iter 3
```

**Diferencia respecto a iter 1/2**: en iter 1 el memory documenta `BoneToMarker0` bajo `Marker0ToTracker` y `Physical_Points` bajo `Marker0ToTracker`. En iter 3, lo que funcionó es **ambos en root**. La diferencia es la convención de en qué frame se calcularon los `Physical_Points`:
- Si `Physical_Points` se crea **bajo Marker0ToTracker**, el wizard calcula `BoneToMarker0` como Bone → Marker0, y debe anidarse bajo Marker0ToTracker para componer correctamente.
- Si `Physical_Points` se crea **en root**, el wizard calcula `BoneToMarker0` como Bone → World, y debe quedar en root (sin padre).

Ambas convenciones funcionan. Iter 3 usó la segunda. **Mantener la consistencia es lo importante** — no mezclar.

Script para armar la jerarquía final de iter 3 (Physical_Points en root):

```python
m0 = slicer.util.getNode("Marker0ToTracker")
bone_to_m0 = slicer.util.getNode("BoneToMarker0")

# Detectar STL y volumen dinamicamente
bone_stl_nodes = [n for n in slicer.util.getNodesByClass("vtkMRMLModelNode")
                  if "Bone" in n.GetName() or "Segment" in n.GetName()]
volume_nodes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
bone_points = slicer.util.getNode("BoneSTL_Points")

# BoneToMarker0 queda en root (sin padre)
bone_to_m0.SetAndObserveTransformNodeID(None)

# STL, BoneSTL_Points, y volumen DICOM bajo BoneToMarker0
for n in bone_stl_nodes:
    n.SetAndObserveTransformNodeID(bone_to_m0.GetID())
bone_points.SetAndObserveTransformNodeID(bone_to_m0.GetID())
for n in volume_nodes:
    n.SetAndObserveTransformNodeID(bone_to_m0.GetID())

# Physical_Points en root (asegurar)
phys = slicer.util.getNode("Physical_Points")
phys.SetAndObserveTransformNodeID(None)

print("Jerarquía iter 3 armada.")
```

## J6 — Cambiar layout a Four-Up y asignar volumen a las 3 vistas

```python
# Layout Four-Up (3 slices + 3D)
slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)

# Asignar el volumen DICOM como background de las 3 vistas 2D
volume = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")[0]
for slice_name in ["Red", "Yellow", "Green"]:
    composite = slicer.app.layoutManager().sliceWidget(slice_name).mrmlSliceCompositeNode()
    composite.SetBackgroundVolumeID(volume.GetID())
    logic = slicer.app.layoutManager().sliceWidget(slice_name).sliceLogic()
    logic.FitSliceToAll()
print("Vistas configuradas.")
```

## J7 — Configurar Volume Reslice Driver

Módulo `Volume Reslice Driver`. Configurar las 3 filas:

| Vista | Driver | Mode |
|---|---|---|
| **R** (Red) | `StylusTipToDodecaedro` | `Axial` (o `Position` si Axial no existe) |
| **Y** (Yellow) | `StylusTipToDodecaedro` | `Sagittal` |
| **G** (Green) | `StylusTipToDodecaedro` | `Coronal` |

**Nota**: en versiones donde solo aparece `Inplane`/`Position`, usar `Position` para las 3 — eso mantiene las orientaciones default (Red=axial, Yellow=sagital, Green=coronal) y solo mueve el punto de corte al driver.

## J8 — Validación final iter 3

Mover físicamente la punta del stylus a distintas vértebras del phantom:
- Tocar L3 → las 3 vistas centradas en L3.
- Mover a L5 → las 3 vistas se actualizan a L5.
- Mover al sacro → vistas actualizadas al sacro.

Si las vistas siguen la punta coherentemente, **iter 3 está cumplido**.

## Métricas finales iter 3 (validadas 2026-05-22)

- RMS registro paired-point: **2.806 mm** (mejor que iter 1 = 3.46, dentro del objetivo <3 mm).
- Distancia centro_dodecaedro -> tip post-calibración: **91.4 mm** (consistente con magnitud del pivote).
- Diff Marker0*DodToM0 vs DodToTracker: **0.000 mm** (observer Python funciona perfecto).
- Tiempo total iter 3 (segmentación + impresión + flujo Slicer): ~12 horas.

## Cosas críticas aprendidas en iter 3 (no repetir errores)

1. **Transform Processor de Slicer puede no auto-actualizar**. Usar siempre el Observer Python (§J3).

2. **STL del hueso debe venir del MISMO DICOM**. Si viene de otra fuente o tiene transforms aplicados, no coincide y hay que registrar paired-point STL↔DICOM (paso extra). Más simple: segmentar nosotros del DICOM (§J0).

3. **Si las 3 vistas del Volume Reslice Driver muestran lo mismo**, es porque están en mode `Inplane` con el mismo driver. Cambiar a `Axial`/`Sagittal`/`Coronal` o `Position`.

4. **pyigtl bloquea sin cliente Slicer**. Conectar OpenIGTLink ANTES de correr tracker.py (ver memory `project_pyigtl_bloquea_sin_cliente.md`).

5. **Jerarquía con BoneToMarker0 en root**: si Physical_Points se crea en root, BoneToMarker0 va en root. Si Physical_Points se anida bajo Marker0ToTracker, BoneToMarker0 también. Mantener consistencia.

---

## ITER 3 — Troubleshooting consolidado (lecciones de la primera reproducción)

Esta sección documenta los fixes específicos descubiertos al reproducir el flujo de iter 3 por primera vez. Cada fix es respuesta a un síntoma observable, NO un capricho. Si reproducís el flujo y aparece el síntoma, aplicá el fix.

### Síntoma 1 — StylusTip aparece muy lejos del dodecaedro virtual

**Indicador**: en la 3D View ves el `StylusTip` (punto rojo) separado del extremo del locator del stylus (línea cyan). Cuando movés el stylus, el punto se mueve pero NO sobre la punta física.

**Causa real (no es del script del StylusTip)**: la cadena de transforms `Marker0ToTracker · DodecaedroToMarker0 · StylusTipToDodecaedro` está inconsistente con la transform directa `DodecaedroToTracker`. El script de crear el StylusTip está bien — el problema está aguas arriba.

**Sub-causas posibles**:
- **A**: `DodecaedroToMarker0` está en root, debería estar bajo `Marker0ToTracker`.
- **B**: El Observer Python que recalcula `DodecaedroToMarker0` no está activo (se perdió al reiniciar la escena o cerrar el módulo Transform Processor).

**Diagnóstico** (siempre correr antes de cualquier fix):

```python
import vtk, numpy as np
m_dt = vtk.vtkMatrix4x4()
slicer.util.getNode("DodecaedroToTracker").GetMatrixTransformToWorld(m_dt)
centro_dod = [m_dt.GetElement(i,3) for i in range(3)]
tip = slicer.util.getNode("StylusTip")
pos_tip = [0,0,0]; tip.GetNthControlPointPositionWorld(0, pos_tip)
dist = np.linalg.norm(np.array(centro_dod) - np.array(pos_tip))
print(f"Distancia centro_dod -> tip: {dist:.1f} mm  (esperado ~91 mm)")
```

- Si distancia ≈ 91 mm: todo bien, problema es solo cosmético del locator visual.
- Si distancia >> 91 mm: aplicar fix.

**Fix**:

```python
# Verificar y corregir jerarquía
dod = slicer.util.getNode("DodecaedroToMarker0")
if dod.GetParentTransformNode() is None or dod.GetParentTransformNode().GetName() != "Marker0ToTracker":
    m0 = slicer.util.getNode("Marker0ToTracker")
    dod.SetAndObserveTransformNodeID(m0.GetID())
    print("DodecaedroToMarker0 reanidado bajo Marker0ToTracker")

# Reinstalar Observer Python
import vtk
m0_node = slicer.util.getNode("Marker0ToTracker")
dt_node = slicer.util.getNode("DodecaedroToTracker")
d2m0_node = slicer.util.getNode("DodecaedroToMarker0")
def recompute_d2m0(caller=None, event=None):
    m_inv = vtk.vtkMatrix4x4()
    m0_node.GetMatrixTransformToWorld(m_inv)
    vtk.vtkMatrix4x4.Invert(m_inv, m_inv)
    m_dt = vtk.vtkMatrix4x4()
    dt_node.GetMatrixTransformToWorld(m_dt)
    m_new = vtk.vtkMatrix4x4()
    vtk.vtkMatrix4x4.Multiply4x4(m_inv, m_dt, m_new)
    d2m0_node.SetMatrixTransformToParent(m_new)
recompute_d2m0()
dt_node.AddObserver(slicer.vtkMRMLLinearTransformNode.TransformModifiedEvent, recompute_d2m0)
m0_node.AddObserver(slicer.vtkMRMLLinearTransformNode.TransformModifiedEvent, recompute_d2m0)
print("Observer Python reinstalado.")
```

### Síntoma 2 — BoneSTL_Points NO se superponen a Physical_Points

**Indicador**: después de Update Registration el RMS es bajo (< 3 mm), pero al armar la jerarquía visualmente los puntos del STL y los Physical_Points están separados varias decenas de mm.

**Causa**: jerarquía de `BoneToMarker0` mal armada. La transform existe pero está aplicada en un frame incorrecto.

**Fix dependiendo de dónde se creó Physical_Points**:

- Si `Physical_Points` está en **ROOT** (sin padre) → `BoneToMarker0` debe quedar en **ROOT** también, con `Segmentation_Bone_CT`, `BoneSTL_Points` y `202: AXIAL` como hijos.

- Si `Physical_Points` está bajo **Marker0ToTracker** → `BoneToMarker0` debe ir **bajo Marker0ToTracker**, con los mismos hijos.

**Verificación**:

```python
import numpy as np
b = slicer.util.getNode("BoneSTL_Points")
p = slicer.util.getNode("Physical_Points")
n = min(b.GetNumberOfControlPoints(), p.GetNumberOfControlPoints())
errors = []
for i in range(n):
    bp = [0,0,0]; b.GetNthControlPointPositionWorld(i, bp)
    pp = [0,0,0]; p.GetNthControlPointPositionWorld(i, pp)
    errors.append(np.linalg.norm(np.array(bp) - np.array(pp)))
print(f"Errores por punto (mm): {[round(e,1) for e in errors]}")
print(f"RMS: {np.sqrt(np.mean([e**2 for e in errors])):.2f} mm")
```

Si RMS > 5 mm después de armar la jerarquía → revisar paternidad.

### Síntoma 3 — Volumen DICOM no aparece en las vistas

**Causa común**: el volumen no está asignado como background de las slices Red/Yellow/Green.

**Fix**: ver §J6.

### Síntoma 4 — Las 3 vistas (R/Y/G) muestran el MISMO corte

**Causa**: Volume Reslice Driver configurado con `Mode = Inplane` en las 3 vistas → todas se alinean al plano XY del driver.

**Fix**: cambiar Mode a:
- Red → `Axial` (o `Position` si no existe).
- Yellow → `Sagittal` (o `Position`).
- Green → `Coronal` (o `Position`).

### Mantenimiento del Observer Python

El Observer Python puede perderse en estos eventos:
- Cerrar/reabrir Slicer.
- Cerrar la escena (`File → Close Scene`).
- Reset del módulo Transform Processor.
- Operaciones que reinstancian los nodos `Marker0ToTracker` o `DodecaedroToTracker`.

**Regla de oro**: si en cualquier momento la distancia centro_dod → tip deja de dar ~91 mm, re-aplicar §J3 y volver a verificar.

**Verificación periódica recomendada**: correr el script de §J4 cada vez que reabras la sesión, antes de hacer cualquier paired-point o navegación.
