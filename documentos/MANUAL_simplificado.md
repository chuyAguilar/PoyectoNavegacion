

Abrir **PowerShell** y activar el entorno (todos los comandos PowerShell se corren
desde aquí):

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate
git pull
```

Si al activar da error de permisos:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\activate
```

---

# Paso 1 — Verificar IDs y orientación del dodecaedro

Antes de usar el dodecaedro hay que confirmar que cada cara tiene el ID correcto
y la orientación correcta (clave para que la geometría compartida cuadre).

```powershell
python iter4\identificar_ids.py --config iter4\tracker_config_doctor.yaml
```

Se abre la cámara y sobre cada marcador detectado dibuja su **ID grande** y un
**punto ROJO en la esquina inferior** (la que define la orientación).

Qué verificar, mostrando el dodecaedro a la cámara:

- Los IDs son **3 al 13** (no debe aparecer ningún otro; la detección es
  estricta). El **6 y el 9** son los que más se confunden: revisalos bien.
- **Orientación:** el **punto rojo abajo-derecha** en las **10 caras laterales**
  (IDs 4–13). La cara **superior (ID 3)** va con orientación distinta (su "abajo"
  es ambiguo); es normal que su punto rojo no quede abajo-derecha.

Si todos los IDs salen correctos y la orientación de los laterales es consistente,
la geometría compartida va a cuadrar. Cerrar la ventana con **q**.

> Si ves IDs fuera de 3–13 o detecciones en stickers/texturas del fondo, es ruido
> del ambiente: despejá el fondo. El tracker igual los ignora (solo usa 3–13).

---

# Paso 2 — Calibración del tip por DOCK (tu stylus)

El largo de tu stylus es distinto, así que esta calibración es **tuya**. Reemplaza
al pivote clásico: el stylus se **encaja** en la placa dock y la pose queda
definida por geometría.

**Preparar la placa dock:** placa **dock v3** impresa (blanco + marcador **ID 2**
negro mate). Medí con calibrador el lado del marcador de la placa y ajustá
`--plate-mm` (nominal ~60).

```powershell
python iter4\calibrar_tip_divot.py --config iter4\tracker_config_doctor.yaml --divot DOCK --plate-id 2 --plate-mm 59.6 --output-matriz iter4\data\StylusTipToDodecaedro_doctor_dock
```

Procedimiento en la ventana:

1. **Encajar el stylus en el dock** (la esfera de la punta en el cono, el eje en
   la ranura en V; asienta solo por gravedad).
2. **Tomar el conjunto entero en la mano**, frente a la cámara a 50–70 cm.
3. Cuando diga **`placa:si dodec:N/3`** (N≥3) y **`listo - ESPACIO para
   capturar`**, presionar **ESPACIO** y mantener quieto ~2 s (`capturando X/35` →
   `postura guardada`).
4. **Reorientar el conjunto entero** y repetir hasta **6 orientaciones distintas**.
5. **q** para terminar y calcular.

**Verificar el resultado** (en la terminal, al final):

- **`Spread maximo` < 1.5 mm** (`[BUENO]` o `[EXCELENTE]`).
- **`magnitud`** del offset ≈ la distancia física **centro del dodecaedro → punta**
  medida con calibrador **de TU stylus** (no es el ~93 mm del stylus viejo; medí
  el tuyo). Si el spread queda >1.5 mm, repetir con orientaciones más variadas.

Queda generado **`iter4\data\StylusTipToDodecaedro_doctor_dock.npy`** (y `.txt`).

---

# Paso 3 — Tracker en vivo

> **IMPORTANTE**: el tracker se **bloquea** si Slicer no está conectado. Hacé
> primero el **Paso 4.1 (conectar OpenIGTLink)** y recién después corré el tracker.

Con Slicer ya conectado (Paso 4.1):

```powershell
python iter4\tracker.py --config iter4\tracker_config_doctor.yaml
```

Se abre una ventana de OpenCV con los markers detectados y **"Dodecaedro: N
markers"** (N≥3). FPS estable 28–30.

> Si los FPS caen a ~5: el backend ignoró el codec. Verificar `backend: MSMF` y
> `fourcc: MJPG` en el config (ya vienen por default).

El tracker envía por OpenIGTLink (puerto 18944): **`Marker0ToTracker`** (paciente)
y **`DodecaedroToTracker`** (stylus). Dejar esta ventana corriendo durante todo el
uso en Slicer.

---

# Paso 4 — 3D Slicer: conexión y cadena de transforms

### 4.1 — Conectar OpenIGTLink (HACER ANTES del tracker)

1. Abrir **3D Slicer**.
2. Buscar y abrir el módulo **`OpenIGTLink IF`**.
3. Click en **`+`** para agregar una conexión.
4. Configurar: **Type** `Client`, **Hostname** `localhost`, **Port** `18944`.
5. Tildar **`Active`**.
6. **Ahora sí, ir a PowerShell y correr el tracker (Paso 3).**
7. Volver a Slicer: en `Data` deben aparecer **`Marker0ToTracker`** y
   **`DodecaedroToTracker`** actualizándose. Mové el stylus para confirmar.

Si no aparecen: confirmar que el tracker corre y que el firewall no bloquea el
puerto 18944.

### 4.2 — Cargar la calibración del tip

Abrir **`View → Python Console`** (`Ctrl+3`). Pegar:

```python
import numpy as np, vtk, glob, os

# Carga el StylusTipToDodecaedro*.npy mas reciente de la carpeta data
data_dir = r"C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\iter4\data"
candidatos = glob.glob(os.path.join(data_dir, "StylusTipToDodecaedro*.npy"))
if not candidatos:
    raise FileNotFoundError("No hay StylusTipToDodecaedro*.npy en " + data_dir +
                            ". Corre el Paso 2 (calibracion del tip) primero.")
ruta = max(candidatos, key=os.path.getmtime)
print("Usando el tip mas reciente:", os.path.basename(ruta))
M = np.load(ruta)

stylus = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "StylusTipToDodecaedro")
m = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        m.SetElement(i, j, float(M[i, j]))
stylus.SetMatrixTransformToParent(m)
print("OK: nodo StylusTipToDodecaedro creado.")
```

### 4.3 — Crear el punto de la punta (StylusTip)

```python
tip = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "StylusTip")
tip.AddControlPoint(0.0, 0.0, 0.0, "Tip")
stylus = slicer.util.getNode("StylusTipToDodecaedro")
tip.SetAndObserveTransformNodeID(stylus.GetID())
print("OK: StylusTip creado bajo StylusTipToDodecaedro.")
```

### 4.4 — Instalar el Observer Python (calcula DodecaedroToMarker0)

Lleva la pose del stylus al frame del paciente. Usamos un **Observer Python** (no
el Transform Processor, que a veces deja de actualizarse). Pegar todo el bloque:

```python
import vtk

m0_node = slicer.util.getNode("Marker0ToTracker")
dt_node = slicer.util.getNode("DodecaedroToTracker")

try:
    d2m0_node = slicer.util.getNode("DodecaedroToMarker0")
except Exception:
    d2m0_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "DodecaedroToMarker0")

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
print("OK: Observer Python instalado para DodecaedroToMarker0.")
```

### 4.5 — Armar la cadena del stylus

```python
# Marker0ToTracker -> DodecaedroToMarker0 -> StylusTipToDodecaedro -> StylusTip
marker0 = slicer.util.getNode("Marker0ToTracker")
d2m0 = slicer.util.getNode("DodecaedroToMarker0")
stylus = slicer.util.getNode("StylusTipToDodecaedro")

d2m0.SetAndObserveTransformNodeID(marker0.GetID())
stylus.SetAndObserveTransformNodeID(d2m0.GetID())
print("OK: cadena del stylus armada.")
```

### 4.6 — Verificación obligatoria de coherencia

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
print(f"Check 1 (coherencia cadena): {np.linalg.norm(np.array(t_d)-np.array(t_c)):.3f} mm  -> debe ser < 1 mm")
tip = slicer.util.getNode("StylusTip")
pos_tip = [0,0,0]; tip.GetNthControlPointPositionWorld(0, pos_tip)
print(f"Check 2 (centro_dod -> tip): {np.linalg.norm(np.array(t_d)-np.array(pos_tip)):.1f} mm  -> debe ser ~ la magnitud de TU tip")
```

- **Check 1 < 1 mm** y **Check 2 ≈ la magnitud de tu calibración del Paso 2**: todo
  bien. Si Check 1 es grande o Check 2 está muy lejos de tu magnitud: el Observer
  no está activo o la cadena está mal → repetir 4.4 y 4.5.

En la 3D View ya deberías ver el **StylusTip** moviéndose con el stylus físico.

> **Locator decorativo:** en la 3D View aparece un cilindro/aguja (el "locator")
> que mide **100 mm fijos** (default de SlicerIGT). NO es tu stylus real; es normal
> que el StylusTip no caiga exacto sobre su punta. Para ocultarlo:
> ```python
> slicer.util.getNode("Locator_DodecaedroToTracker").GetDisplayNode().SetVisibility(False)
> ```
> La verificación REAL es física: apoyar la punta en un punto fijo y girar el
> stylus alrededor; el StylusTip debe quedarse quieto sobre ese punto.

---

# Paso 5 — 3D Slicer: registro del hueso (paired-point)

Alinea el modelo 3D del hueso con el hueso físico.

### 5.1 — Cargar el STL del hueso

1. **`File → Add Data`** → `Choose File(s) to Add` → el `.stl` del hueso → `OK`.
2. Aparece como nodo `Bone` (o el nombre del archivo). **No le pongas transform
   padre todavía.**

### 5.2 — Marcar puntos sobre el modelo (BoneSTL_Points)

1. Módulo **`Markups`** → `Create new MarkupsFiducial`. Renombrarlo a
   **`BoneSTL_Points`**. **Dejarlo en la raíz** (sin transform padre).
2. Botón **`Place`** y hacer click sobre **6 a 9 puntos** en features
   reconocibles del modelo (procesos espinosos, esquinas de carillas). Bien
   distribuidos (no coplanares) e **identificables también en el hueso físico**.
3. Anotá mentalmente el ORDEN: lo vas a repetir con el stylus.

### 5.3 — Crear lista vacía de puntos físicos (Physical_Points)

```python
phys = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "Physical_Points")
print("OK: Physical_Points creado, VACIO, en raiz. NO marcar puntos a mano.")
```

### 5.4 — Configurar el Fiducial Registration Wizard

1. Módulo **`Fiducial Registration Wizard`**.
2. Configurar:
   - **From fiducials**: `BoneSTL_Points`.
   - **To fiducials**: `Physical_Points`.
   - **Place "From" fiducials in**: `None`.
   - **Place "To" fiducials in**: **`StylusTipToDodecaedro`** (ahí "vive" la punta).
   - **Output transform**: `Create new...` → **`BoneToMarker0`**.
   - **Transform type**: `Rigid`. **Update mode**: `Manual`. **Auto-update**: tildado.

### 5.5 — Capturar los puntos físicos con el stylus

Para cada punto, **en el mismo orden** que BoneSTL_Points:

1. Tocar con la **punta física** el mismo feature anatómico.
2. Mantener firme ~1 s.
3. En el wizard, **`Record point`** en "To fiducials". Verificar que aparece en
   `Physical_Points`.
4. Repetir todos, **mismo orden**. Desde el 3er punto el wizard calcula
   `BoneToMarker0` y muestra el **RMS**.

### 5.6 — Leer el RMS

- **RMS < 1.5 mm**: excelente. **1.5–3 mm**: aceptable. **> 5 mm**: algo está mal
  (puntos en distinto orden, mal elegidos, o calibración) → revisar.

### 5.7 — Armar la jerarquía final (PASO CRÍTICO)

La jerarquía correcta: **`Marker0ToTracker`, `DodecaedroToTracker` y
`BoneToMarker0` quedan los tres al mismo nivel bajo la escena (raíz).**
`Physical_Points` queda en la raíz sin relación con nadie. El **modelo STL** y
**`BoneSTL_Points`** son **hijos de `BoneToMarker0`**. Pegar:

```python
bone_to_m0 = slicer.util.getNode("BoneToMarker0")
bone_points = slicer.util.getNode("BoneSTL_Points")

# Detectar el modelo del hueso (excluir cortes de slice y locators)
modelos = [n for n in slicer.util.getNodesByClass("vtkMRMLModelNode")
           if "Slice" not in n.GetName() and "Locator" not in n.GetName()]
bone_stl = modelos[0] if modelos else None

# BoneToMarker0 queda en la RAIZ (al mismo nivel que Marker0ToTracker y
# DodecaedroToTracker). NO se anida bajo Marker0ToTracker.
bone_to_m0.SetAndObserveTransformNodeID(None)

# El modelo del hueso y los puntos del STL son HIJOS de BoneToMarker0
if bone_stl:
    bone_stl.SetAndObserveTransformNodeID(bone_to_m0.GetID())
bone_points.SetAndObserveTransformNodeID(bone_to_m0.GetID())

# Physical_Points se queda en la raiz, sin padre (no se toca).
print("OK: jerarquia final. BoneToMarker0 en raiz; STL y BoneSTL_Points como hijos.")
```

### 5.8 — Validación visual

En la 3D View: ¿el modelo `Bone` queda sobre el hueso físico? ¿al mover el stylus,
el `StylusTip` se desliza sobre la superficie del modelo? ¿`BoneSTL_Points` y
`Physical_Points` coinciden o están muy cerca? Si las tres son sí, **el registro
funciona**.

---

# Paso 6 — 3D Slicer: navegación tomográfica (opcional)

Hace que los cortes del CT sigan a la punta. Requiere el DICOM del paciente.

### 6.1 — Importar el DICOM

Módulo **`DICOM`** → `Import DICOM files` → carpeta del paciente → doble click en
la serie axial con más cortes.

### 6.2 — Anidar el volumen bajo BoneToMarker0

```python
bone_to_m0 = slicer.util.getNode("BoneToMarker0")
vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
for v in vols:
    v.SetAndObserveTransformNodeID(bone_to_m0.GetID())
print(f"OK: {len(vols)} volumen(es) anidado(s) bajo BoneToMarker0.")
```

### 6.3 — Layout y vistas (a mano)

Cambiá el layout a **Four-Up** desde la barra de layouts y asigná el volumen del
paciente a las vistas Red/Yellow/Green **a mano** (como fondo). No hace falta
ningún script para esto.

### 6.4 — Configurar el Volume Reslice Driver

1. Módulo **`Volume Reslice Driver`** (extensión SlicerIGT).
2. Para cada vista:

   | Vista | Driver | Mode |
   |---|---|---|
   | **Red** | `StylusTipToDodecaedro` | `Axial` (o `Position`) |
   | **Yellow** | `StylusTipToDodecaedro` | `Sagittal` (o `Position`) |
   | **Green** | `StylusTipToDodecaedro` | `Coronal` (o `Position`) |

   Si solo aparece `Position`, usar `Position` en las tres.