# MANUAL COMPLETO — Webcam global shutter (iter 4)

Sistema de navegación quirúrgica óptica. **Guía paso a paso, autocontenida.**
Cualquier persona puede seguirla sin conocimiento previo: solo ejecutar los
comandos y hacer los clicks en orden.

> Para la **cámara Orbbec Femto Bolt**, usar `MANUAL_femtobolt.md`. Todo es igual
> salvo la cámara y su calibración (secciones A y el `--config`).

**Convención**: los comandos PowerShell van en bloques ```powershell```. El
código que se pega en la **Consola Python de 3D Slicer** va en bloques
```python```. No mezclar: PowerShell es la terminal de Windows; la Consola Python
está DENTRO de Slicer (menú `View → Python Console`).

---

## ⚠️ Configuración del equipo (leer primero)

Cada equipo físico (cámara + dodecaedro + stylus) tiene su PROPIO config y sus
propios archivos de calibración, para que dos equipos compartiendo el mismo
repositorio NO se pisen las calibraciones.

Este manual ya usa el config **`iter4\tracker_config_doctor.yaml`** en todos
los comandos (webcam global shutter + dodecaedro IDs 151–161 + marker paciente
ID 0 de 60 mm). Si tu equipo es distinto, ajustá el `--config` y los IDs.

Datos de ese equipo (ya listos en el repo):
- Geometría teórica (semilla del BA): `iter4\data\reference_dodecaedro_doctor.txt`
  (IDs 151–161, arista 20 mm, marker 16 mm — **confirmar con calibrador**).
- Marker del paciente: ID 0, **60 mm**.
- La geometría CALIBRADA (`reference_dodecaedro_doctor_calibrado.txt`) y el tip
  los generás vos con las secciones B y C (no vienen en el repo: son de tu
  hardware físico).

Si tu webcam NO es la misma de iteraciones previas, además recalibrar la cámara
(sección A.3).

---

## ÍNDICE

- **A. Preparación** (una sola vez por equipo)
- **B. Calibración del rigid body** (solo si el dodecaedro es nuevo)
- **C. Calibración del tip por DOCK** (cada vez que se arma el stylus)
- **D. Tracker en vivo**
- **E. 3D Slicer: conexión y cadena de transforms**
- **F. 3D Slicer: registro del hueso (paired-point)**
- **G. 3D Slicer: navegación tomográfica** (opcional)
- **H. Checklist y solución de problemas**

---

# A. Preparación (una vez por equipo)

### A.1 — Hardware

- **Webcam global shutter** USB (ej. SVPRO AR0234) montada sobre el área de trabajo.
- Caja de luz Puluz para iluminación pareja (las capturas y el tracking se hacen
  dentro de la caja).
- Stylus: dodecaedro impreso con 11 markers ArUco (IDs **170–180**) + mango con
  punta. Marcadores **negro mate**.
- Placa **dock v3** impresa (`stl\placa_dock_v3\`), con su marker **ID 2** negro.
- Marker del paciente: ArUco **ID 0**, pegado firme al phantom/hueso.

### A.2 — Abrir la terminal y activar el entorno

Abrir **PowerShell**. Ejecutar:

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate
```

Si aparece un error de permisos al activar, ejecutar primero:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\activate
```

Al activar, el prompt muestra `(.venv)` al inicio. **Todos los comandos
PowerShell de este manual se corren desde esta carpeta `codigo` con el venv
activado.**

### A.3 — Calibración intrínseca de la cámara

**A diferencia de la Femto Bolt, la webcam SÍ necesita calibración intrínseca**
(es propia de cada cámara/óptica). El config `iter4\tracker_config_doctor.yaml`
apunta a `iter4\data\camera_calibration_webcam.yml`.

- **Si usás la MISMA webcam de iteraciones anteriores** (mismo foco, misma
  resolución 640×480): el archivo ya existe y sirve. No hacer nada.
- **Si es OTRA webcam, o cambiaste la óptica/foco/resolución**: hay que
  recalibrar la cámara con un patrón de tablero de ajedrez y regenerar ese `.yml`.
  La calibración intrínseca vieja NO sirve para otra cámara (las distancias
  saldrían mal). Consultar el procedimiento de calibración de cámara
  (MRPT/OpenCV) usado en iteraciones previas.

Verificar que el archivo existe:
```powershell
Test-Path iter4\data\camera_calibration_webcam.yml
```

---

# B. Calibración del rigid body (solo si el dodecaedro es NUEVO)

> **Si ya existe la geometría calibrada del doctor
> (`iter4\data\reference_dodecaedro_doctor_calibrado.txt`) y el BA de esa corrida
> convergió bien, saltear toda la sección B e ir a la C.** Para verificar si
> existe:
> ```powershell
> Test-Path iter4\data\reference_dodecaedro_doctor_calibrado.txt
> ```
> Si dice `True` (y confiás en esa calibración), saltear a la sección C. Si tenés
> dudas de que el BA haya cerrado bien, rehacé la sección B.

Esta sección genera la "geometría" del dodecaedro (la posición 3D exacta de cada
marker), necesaria para que el tracker calcule la pose.

### B.1 — Medir el dodecaedro con calibrador

Anotar:
- **edge_mm**: largo de una arista pentagonal (ej. 17.5).
- **marker_mm**: lado del cuadrado negro de un marker (ej. 13.4).
- **IDs**: el del TOP (cara de arriba), los 5 del anillo superior, los 5 del inferior.

### B.2 — Generar la geometría teórica

> **Equipo IDs 151–161 (el del doctor)**: generá la semilla teórica con TU valor
> de marker medido con calibrador. En este equipo el marker midió **16.58 mm** y
> la arista **20 mm**:
> ```powershell
> python iter4\generar_reference_dodecaedro.py --id-top 151 --ids-superior 152,153,154,155,156 --ids-inferior 158,159,160,161,157 --edge-mm 20 --marker-mm 16.58 --output iter4\data\reference_dodecaedro_doctor.txt
> ```
>
> ✅ **ORDEN REAL CONFIRMADO (2026-06-22)**: el anillo inferior de ESTE dodecaedro
> está pegado como **`158,159,160,161,157`** (rotado una posición respecto al
> teórico `157,158,...`). Con ese orden el BA convergió (desplazamientos < 2.1 mm).
> Ya está puesto arriba. Si alguna vez se rearma el dodecaedro, reconfirmar con B.4.5.
>
> ⚠️ **REGLA DEL `marker_mm`**: el valor que uses acá (16.58) tiene que ser **el
> mismo** en B.4 (limpieza) y B.5 (BA). Si mezclás 16 y 16.58 entre pasos, la
> geometría queda inconsistente. En este manual ya está puesto 16.58 en los tres.
>
> ⚠️ **El orden de `--ids-inferior` importa.** Si el anillo de abajo estuviera en
> otra rotación, el BA no converge (anillo inferior desplazado ~23 mm = la
> distancia entre markers vecinos). Si pasa, NO adivines: corré **B.4.5** y
> regenerá con el orden que te indique.

Para un dodecaedro distinto, reemplazar los valores por los tuyos:

```powershell
python iter4\generar_reference_dodecaedro.py --id-top 170 --ids-superior 171,172,173,174,175 --ids-inferior 176,177,178,179,180 --edge-mm 17.5 --marker-mm 13.4 --output iter4\data\reference_dodecaedro.txt
```

Corre 11 validaciones matemáticas. Si todas dan `[PASS]`, el archivo se guardó.
Si hay `[FAIL]`, casi seguro `marker_mm` es muy grande para `edge_mm` (no cabe
en la cara): reducir `marker_mm`.

### B.3 — Capturar dataset para el bundle adjustment

Montar el dodecaedro dentro de la caja de luz, frente a la cámara.

> ⚠️ **OBLIGATORIO `--geometry-file`.** El script, si no le pasás esta bandera,
> usa por default `reference_dodecaedro.txt` (IDs **170–180**) y va a buscar los
> markers equivocados. Para el equipo del doctor hay que forzar su geometría:

```powershell
python iter4\captura_calibracion.py --config iter4\tracker_config_doctor.yaml --geometry-file iter4\data\reference_dodecaedro_doctor.txt --duracion 90 --output iter4\data\captura_ba.npz
```

Durante los 90 segundos, **rotar el dodecaedro lentamente** mostrando TODAS las
caras en muchas orientaciones.

> ⚠️ **COBERTURA PAREJA — el error más común.** El anillo **inferior** (157–161)
> es el que menos se ve y el que rompe el BA. Incliná el dodecaedro de modo que
> el anillo de abajo mire a la cámara **tanto como el de arriba**. Mientras corre,
> la ventana muestra la cobertura de cada ID a la derecha: **no termines hasta que
> los IDs 157–161 estén en verde** y con un conteo parecido a los de arriba.

Al terminar reporta cobertura por marker (todos deben decir `OK`) y "Frames
útiles". Buscar **>1500 frames útiles** y que **ningún ID quede con muchas menos
detecciones que el resto** (apuntá a que el anillo inferior tenga al menos la
mitad de detecciones que el superior; si quedan en ~60 vs ~180, recapturá).

### B.4 — (Si hubo IDs fantasma) limpiar la captura

El detector puede generar falsos positivos. Limpiarlos antes del BA. **Equipo del
doctor** (su geometría + su marker 16.58):

```powershell
python iter4\limpiar_captura_fantasmas.py --input iter4\data\captura_ba.npz --teorico iter4\data\reference_dodecaedro_doctor.txt --marker-mm 16.58 --output iter4\data\captura_ba_limpia.npz
```

> ⚠️ Usá **siempre** `reference_dodecaedro_doctor.txt` y `--marker-mm 16.58`. Si
> ponés la geometría genérica (`reference_dodecaedro.txt`, 170–180), ningún marker
> coincide, la lista queda vacía y el script crashea en `np.concatenate`.

(Si no querés limpiar, usar `captura_ba.npz` directamente en el paso B.5.)

### B.4.5 — (Diagnóstico) Verificar la topología del dodecaedro

**Cuándo correr esto**: solo si el BA (B.5) **no converge** y ves un anillo entero
con desplazamientos grandes (~23 mm). Sirve para saber si el problema es el
**orden de pegado** de los IDs o la **cobertura** de la captura. No cambia nada por
sí solo: es una medición.

Estima la pose de cada marker por separado y mide las distancias reales entre
ellos para reconstruir el orden físico de los anillos:

```powershell
python iter4\calibrar_topologia.py --input iter4\data\captura_ba_limpia.npz --id-top 151 --edge-mm 20 --marker-mm 16.58
```

**Cómo interpretar la salida:**

- **Los pares matchean dentro de ~3 mm, pero el orden detectado del anillo
  inferior NO es `157→158→159→160→161`** → están bien medidos pero pegados en otra
  rotación. Regenerá la geometría teórica (B.2) cambiando `--ids-inferior` por el
  orden que reporta el script, y volvé a correr B.5. **No hace falta recapturar.**
- **Las distancias NO matchean / el script se queja / faltan markers** → es
  problema de **cobertura o calidad** de la captura. Volvé a **B.3** y capturá de
  nuevo mostrando mejor el anillo flojo.

> ⚠️ Ojo: el "orden detectado" puede ser una elección cíclica arbitraria (ej.
> `[158,159,160,161,157]` es la misma topología que `[157,158,159,160,161]`). No
> tomes la diferencia con el teórico como error de pegado **a menos que las
> distancias entre pares confirmen el desfase**. Ante la duda, primero descartá
> cobertura (rehacer B.3); cambiar el orden sin confirmar no arregla un BA que
> falla por dataset malo.

### B.5 — Ejecutar el bundle adjustment

`--ancla` = ID del TOP, `--marker-mm` = tu valor:

**Equipo IDs 151–161 (el del doctor)** — ancla 151, marker 16.58, su geometría y
su salida:
```powershell
python iter4\calibrar_rigid_body.py --input iter4\data\captura_ba_limpia.npz --teorico iter4\data\reference_dodecaedro_doctor.txt --output iter4\data\reference_dodecaedro_doctor_calibrado.txt --ancla 151 --marker-mm 16.58 --no-depth --max-frames 800 --max-nfev 1000
```

Para otro dodecaedro (plantilla genérica):
```powershell
python iter4\calibrar_rigid_body.py --input iter4\data\captura_ba_limpia.npz --teorico iter4\data\reference_dodecaedro.txt --output iter4\data\reference_dodecaedro_calibrado.txt --ancla 170 --marker-mm 13.4 --no-depth --max-frames 800 --max-nfev 1000
```

**Cómo leer el resultado (no alcanza con que termine):**

1. **`RMSE 2D` final < 1.0 px.** Si dice `El BA NO converge satisfactoriamente` y
   el RMSE queda en 3 px o más, NO sirve: la geometría que generó está mal y el
   tip va a salir mal. No sigas a la sección C.
2. **`Desplazamientos respecto a geometria teorica` < 5 mm en TODOS los markers.**
   Si un anillo entero aparece con **~23 mm** de desplazamiento, es la firma de
   **anillo rotado** (orden de IDs equivocado) o de **mala cobertura** de ese
   anillo en la captura.
3. **Mirá el `n=` (detecciones) por marker.** Si un anillo tiene 3–4 veces menos
   detecciones que el otro (ej. inferior n≈60 vs superior n≈180), el problema es
   **cobertura**: rehacé la captura (B.3) mostrando mejor ese anillo.

**Si no converge, en este orden:**
- (a) ¿Cobertura despareja? → repetir **B.3** con el anillo flojo mejor expuesto.
- (b) ¿Cobertura pareja pero un anillo sigue a ~23 mm? → correr **B.4.5**
  (diagnóstico de topología) y regenerar la geometría con el orden real.

El archivo `reference_dodecaedro_doctor_calibrado.txt` queda generado **solo si el
BA cerró bien**.

> 🔧 **Nota (bug ya corregido).** Si en `[3/5] Estimando poses iniciales` aparece
> `TypeError: only 0-dimensional arrays can be converted to Python scalars`, es un
> bug de numpy 2.x ya arreglado en el repo (`calibrar_rigid_body.py`, uso de
> `tvec[2].item()`). Asegurate de tener el último `git pull`.

---

# C. Calibración del tip por DOCK (cada vez que se arma el stylus)

Reemplaza al pivote clásico. Es más fácil y reproducible: el stylus se **encaja**
en la placa dock y la pose queda definida por geometría.

### C.1 — Preparar la placa dock

Imprimir la placa **dock v3** (`stl\placa_dock_v3\`, blanco + marker negro mate).
Medir con calibrador su ancho (nominal 150 mm) y el lado del marker (nominal 60).
Si difieren, ajustar la escala en `iter4\calibrar_tip_divot.py` (ver el comentario
`DOCK` en el archivo). Con la placa actual ya está ajustado.

### C.2 — Ejecutar la calibración

```powershell
python iter4\calibrar_tip_divot.py --config iter4\tracker_config_doctor.yaml --divot DOCK --plate-id 2 --plate-mm 59.6 --output-matriz iter4\data\StylusTipToDodecaedro_dock
```

Se abre una ventana con la cámara. Procedimiento:

1. **Encajar el stylus en el dock**: la esfera de la punta entra en el cono, el
   eje apoya en la ranura en V. Asienta solo por gravedad.
2. **Tomar el conjunto entero en la mano** y ponerlo frente a la cámara a 50–70 cm.
3. Mirar el texto de la ventana. Cuando diga **`placa:si dodec:N/3`** (con N≥3) y
   **`listo - ESPACIO para capturar`**, presionar la **barra ESPACIADORA** y
   mantener el conjunto quieto ~2 segundos. La ventana muestra `capturando X/35`
   y luego `postura guardada`.
4. **Reorientar el conjunto entero** (inclinarlo/girarlo a otra posición) y volver
   a presionar ESPACIO. Repetir hasta tener **6 orientaciones distintas**.
5. Presionar **q** para terminar y calcular.

### C.3 — Verificar el resultado

En la terminal, al final, buscar:
- **`Spread maximo`**: debe ser **< 1.5 mm** (`[BUENO]` o `[EXCELENTE]`).
- **`magnitud`** del offset: debe parecerse a la distancia física centro→punta
  medida con calibrador (~93 mm para el stylus viejo).

Si alguna postura salió mala, el script la descarta sola (`Posturas outlier
descartadas`). Si el spread queda >1.5 mm, repetir la calibración con orientaciones
más variadas.

Queda generado **`iter4\data\StylusTipToDodecaedro_dock.npy`** (y `.txt`). Ese es
el archivo que carga Slicer.

---

# D. Tracker en vivo

> **IMPORTANTE**: el tracker se queda bloqueado si Slicer no está conectado.
> **Hacer primero la sección E.1 (conectar Slicer), y recién después correr el
> tracker.** Si lo corrés antes, se cuelga en el primer frame.

Con Slicer ya conectado (E.1), en PowerShell:

```powershell
python iter4\tracker.py --config iter4\tracker_config_doctor.yaml
```

Se abre una ventana de OpenCV mostrando la cámara con los markers detectados y el
texto **"Dodecaedro: N markers"** (N≥3). FPS estable 28–30.

> Si los FPS caen a ~5: el backend ignoró el codec. Verificar que el config tenga
> `backend: MSMF` y `fourcc: MJPG` (ya vienen por default).

El tracker envía por la red (OpenIGTLink, puerto 18944) dos transformaciones:
- **`Marker0ToTracker`** (el marker del paciente).
- **`DodecaedroToTracker`** (el stylus).

Dejar esta ventana abierta y el tracker corriendo durante todo el uso en Slicer.

---

# E. 3D Slicer: conexión y cadena de transforms

### E.1 — Conectar OpenIGTLink (HACER ANTES del tracker)

1. Abrir **3D Slicer**.
2. En la barra de módulos (arriba a la izquierda, lupa), buscar y abrir
   **`OpenIGTLink IF`**.
3. En el panel, click en el botón **`+`** para agregar una conexión.
4. Configurar:
   - **Type**: `Client`.
   - **Hostname**: `localhost`.
   - **Port**: `18944`.
5. Tildar el checkbox **`Active`**.
6. **Ahora sí, ir a PowerShell y correr el tracker (sección D).**
7. Volver a Slicer. En unos segundos, en el módulo `Data` deberían aparecer dos
   nodos que se actualizan en tiempo real: **`Marker0ToTracker`** y
   **`DodecaedroToTracker`**. Mové el stylus físico para confirmar que cambian.

Si no aparecen: confirmar que el tracker está corriendo y que el firewall de
Windows no bloquea el puerto 18944.

### E.2 — Cargar la calibración del tip

Abrir la **Consola Python** de Slicer: menú **`View → Python Console`** (o
`Ctrl+3`). Pegar este bloque y presionar Enter (ajustar la ruta del `.npy` si
usaste otro nombre):

```python
import numpy as np, vtk, glob, os

# --- Cargar la matriz del tip (busca el archivo mas reciente automaticamente,
#     asi funciona sin importar el nombre que le hayas puesto en la seccion C) ---
data_dir = r"C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\iter4\data"
candidatos = glob.glob(os.path.join(data_dir, "StylusTipToDodecaedro*.npy"))
if not candidatos:
    raise FileNotFoundError(
        "No hay ningun StylusTipToDodecaedro*.npy en " + data_dir +
        ". Corre la SECCION C (calibracion del tip) primero.")
ruta = max(candidatos, key=os.path.getmtime)   # el mas reciente
print("Usando el tip mas reciente:", os.path.basename(ruta))
M = np.load(ruta)
print("Matriz del tip cargada:\n", M)

# Crear el nodo de transform en Slicer
stylus = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "StylusTipToDodecaedro")
m = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        m.SetElement(i, j, float(M[i, j]))
stylus.SetMatrixTransformToParent(m)
print("OK: nodo StylusTipToDodecaedro creado.")
```

> El snippet carga automáticamente el `.npy` más reciente de la carpeta `data`.
> Si querés forzar uno específico, reemplazá la línea de `ruta =` por
> `ruta = r"C:\...\iter4\data\EL_NOMBRE_QUE_QUIERAS.npy"`.

### E.3 — Crear el punto de la punta (StylusTip)

Pegar en la Consola Python:

```python
# Punto en (0,0,0) del frame del tip = la punta fisica del stylus
tip = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "StylusTip")
tip.AddControlPoint(0.0, 0.0, 0.0, "Tip")
stylus = slicer.util.getNode("StylusTipToDodecaedro")
tip.SetAndObserveTransformNodeID(stylus.GetID())
print("OK: StylusTip creado y anidado bajo StylusTipToDodecaedro.")
```

### E.4 — Instalar el Observer Python (cálculo de DodecaedroToMarker0)

Esto lleva la pose del stylus al frame del paciente. **Usamos un Observer Python
en vez del módulo Transform Processor**, porque el Transform Processor a veces
deja de actualizarse solo. Pegar TODO este bloque en la Consola Python:

```python
import vtk

m0_node = slicer.util.getNode("Marker0ToTracker")
dt_node = slicer.util.getNode("DodecaedroToTracker")

# Crear el nodo de salida si no existe
try:
    d2m0_node = slicer.util.getNode("DodecaedroToMarker0")
except Exception:
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
print("OK: Observer Python instalado para DodecaedroToMarker0.")
```

### E.5 — Armar la cadena de transforms

Pegar en la Consola Python:

```python
# Cadena: Marker0ToTracker -> DodecaedroToMarker0 -> StylusTipToDodecaedro -> StylusTip
marker0 = slicer.util.getNode("Marker0ToTracker")
d2m0 = slicer.util.getNode("DodecaedroToMarker0")
stylus = slicer.util.getNode("StylusTipToDodecaedro")

d2m0.SetAndObserveTransformNodeID(marker0.GetID())
stylus.SetAndObserveTransformNodeID(d2m0.GetID())
print("OK: cadena armada (StylusTip ya cuelga de Marker0 via la cadena).")
```

### E.6 — VERIFICACIÓN OBLIGATORIA de coherencia

Pegar en la Consola Python. Los dos números deben dar lo esperado:

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
print(f"Check 2 (centro_dod -> tip): {np.linalg.norm(np.array(t_d)-np.array(pos_tip)):.1f} mm  -> debe ser ~93 mm (magnitud del tip)")
```

- **Check 1 < 1 mm** y **Check 2 ≈ 93 mm**: todo bien, seguir.
- Si Check 1 es grande o Check 2 muy lejos de 93: el Observer no está activo o la
  cadena está mal. Repetir E.4 y E.5.

En la **3D View** de Slicer ya deberías ver un punto (StylusTip) que se mueve
cuando movés el stylus físico.

### E.7 — (Opcional) Entender el "locator" y verificar la punta

En la 3D View vas a ver un **locator**: un cilindro/aguja que representa el
stylus. **OJO: el locator es DECORATIVO y mide 100 mm de largo FIJO** (default de
SlicerIGT). NO es la longitud real de tu stylus ni la posición de la punta. Es
normal que el StylusTip (el punto rojo) caiga **cerca pero no encima** de la
punta del locator: son cosas independientes.

Para verlo con números, pegar en la Consola Python:

```python
import numpy as np, vtk

# Centro del dodecaedro en el mundo (origen del frame DodecaedroToTracker)
m_dt = vtk.vtkMatrix4x4()
slicer.util.getNode("DodecaedroToTracker").GetMatrixTransformToWorld(m_dt)
centro = np.array([m_dt.GetElement(i, 3) for i in range(3)])

# StylusTip en el mundo
tip = slicer.util.getNode("StylusTip")
pt = [0, 0, 0]; tip.GetNthControlPointPositionWorld(0, pt)
d_tip = np.linalg.norm(np.array(pt) - centro)

# Punto del locator MAS LEJANO del centro = su "punta"
loc = slicer.util.getNode("Locator_DodecaedroToTracker")
poly = loc.GetPolyData()
m_loc = vtk.vtkMatrix4x4()
tnode = loc.GetParentTransformNode()
if tnode:
    tnode.GetMatrixTransformToWorld(m_loc)
pts = poly.GetPoints()
maxd = 0.0
for i in range(pts.GetNumberOfPoints()):
    p = list(pts.GetPoint(i)) + [1.0]
    pw = [0, 0, 0, 0]; m_loc.MultiplyPoint(p, pw)
    maxd = max(maxd, np.linalg.norm(np.array(pw[:3]) - centro))

print(f"centro_dodecaedro -> StylusTip      : {d_tip:.1f} mm")
print(f"centro_dodecaedro -> punta locator  : {maxd:.1f} mm")
print(f"El StylusTip esta {maxd - d_tip:+.1f} mm respecto a la punta del locator.")
```

**Interpretación**: el `StylusTip` debe dar la magnitud de tu calibración
(~93 mm) y la punta del locator ~100 mm. Si el StylusTip da tu magnitud
correcta, **todo está bien** — la diferencia con el locator es solo porque el
locator mide 100 mm fijos.

Para que el locator no confunda, se puede ocultar:

```python
slicer.util.getNode("Locator_DodecaedroToTracker").GetDisplayNode().SetVisibility(False)
```

La verificación REAL de la punta no es visual contra el locator, sino la
**prueba física**: apoyar la punta del stylus en un punto fijo conocido (un divot
de la placa, o un feature del hueso) y, girando el stylus alrededor de esa punta,
ver que el StylusTip se queda quieto sobre ese punto. Eso confirma la calibración
mejor que cualquier comparación con el locator.

---

# F. 3D Slicer: registro del hueso (paired-point)

Hace que el modelo 3D del hueso se alinee con el hueso físico.

### F.1 — Cargar el STL del hueso

1. Menú **`File → Add Data`**.
2. Click **`Choose File(s) to Add`**, seleccionar el `.stl` del hueso del paciente.
3. Click **`OK`** (sin tildar "Show Options").
4. El modelo aparece en la 3D View y como nodo `Bone` (o el nombre del archivo).
   **No le pongas transform padre todavía.**

### F.2 — Marcar puntos sobre el modelo (BoneSTL_Points)

1. Abrir el módulo **`Markups`**.
2. Click **`Create new MarkupsFiducial`** (icono cruz). Renombrarlo a
   **`BoneSTL_Points`** (doble click sobre el nombre).
3. **Dejarlo suelto en la raíz** (sin transform padre).
4. Click en el botón **`Place`** (lápiz/flecha roja) para activar colocación.
5. En la **3D View**, hacer click sobre **6 a 9 puntos** en features reconocibles
   del modelo (puntas de procesos espinosos, esquinas de carillas articulares).
   Que estén **bien distribuidos en el espacio** (no todos juntos, no coplanares),
   y que sean **identificables a ojo también en el hueso físico**.
6. Anotá mentalmente el ORDEN en que los marcaste — lo vas a repetir igual con el
   stylus.

### F.3 — Crear lista vacía de puntos físicos (Physical_Points)

Pegar en la Consola Python:

```python
phys = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "Physical_Points")
print("OK: Physical_Points creado, VACIO, en root. NO marcar puntos a mano.")
```

> Lo dejamos en root (sin padre). Más abajo el wizard captura los puntos en el
> frame correcto y todo queda consistente.

### F.4 — Configurar el Fiducial Registration Wizard

1. Abrir el módulo **`Fiducial Registration Wizard`**.
2. Configurar:
   - **From fiducials**: `BoneSTL_Points`.
   - **To fiducials**: `Physical_Points`.
   - **Place "From" fiducials in**: `None`.
   - **Place "To" fiducials in**: **`StylusTipToDodecaedro`** (la hoja de la cadena
     del stylus: ahí "vive" la punta física).
   - **Output transform**: click `Create new...` → nombrarlo **`BoneToMarker0`**.
   - **Transform type**: `Rigid`.
   - **Update mode**: `Manual`.
   - **Auto-update**: tildado.

### F.5 — Capturar los puntos físicos con el stylus

Para cada punto, **en el mismo orden** que BoneSTL_Points:

1. Tocar con la **punta física del stylus** el mismo feature anatómico que
   marcaste como BoneSTL_Points punto 1.
2. Mantener firme la punta ~1 segundo (sin moverla).
3. En el wizard, click **`Record point`** (o el icono de cámara) en la sección
   "To fiducials".
4. Verificar que aparece un punto nuevo en `Physical_Points`.
5. Repetir para todos los puntos, **mismo orden**.

A partir del 3er punto, el wizard calcula `BoneToMarker0` y muestra el **RMS**.

### F.6 — Leer el RMS

- **RMS < 1.5 mm**: excelente (objetivo iter 4).
- **RMS 1.5–3 mm**: aceptable.
- **RMS > 5 mm**: algo está mal (puntos en distinto orden, mal elegidos, o
  problema de calibración). Ver sección H.

### F.7 — Armar la jerarquía final (PASO CRÍTICO)

Pegar en la Consola Python. Esto alinea el modelo Y los puntos:

```python
m0 = slicer.util.getNode("Marker0ToTracker")
bone_to_m0 = slicer.util.getNode("BoneToMarker0")
bone_points = slicer.util.getNode("BoneSTL_Points")

# Detectar el modelo del hueso automaticamente
modelos = [n for n in slicer.util.getNodesByClass("vtkMRMLModelNode")
           if "Slice" not in n.GetName()]
bone_stl = modelos[0] if modelos else None

# 1. BoneToMarker0 va bajo Marker0ToTracker (viaja con el paciente)
bone_to_m0.SetAndObserveTransformNodeID(m0.GetID())
# 2. El modelo del hueso va bajo BoneToMarker0
if bone_stl:
    bone_stl.SetAndObserveTransformNodeID(bone_to_m0.GetID())
# 3. CRITICO: BoneSTL_Points TAMBIEN va bajo BoneToMarker0
bone_points.SetAndObserveTransformNodeID(bone_to_m0.GetID())
# Physical_Points se queda en root (no se toca).
print("OK: jerarquia final armada. Modelo y puntos alineados al hueso fisico.")
```

### F.8 — Validación visual

Mirar la **3D View**:
- ¿El modelo `Bone` queda sobre el hueso físico (coherente)?
- ¿Al mover el stylus, el `StylusTip` se desliza sobre la superficie del modelo?
- ¿`BoneSTL_Points` y `Physical_Points` coinciden o están muy cerca?

Si las tres son sí, **el registro funciona**. El sistema está listo para navegar.

---

# G. 3D Slicer: navegación tomográfica (opcional)

Hace que los cortes del CT sigan a la punta del stylus en tiempo real. Requiere
el DICOM del paciente.

### G.1 — Importar el DICOM

1. Módulo **`DICOM`** → `Import DICOM files` → seleccionar la carpeta del paciente.
2. Click en el paciente → estudio → series.
3. Doble click en la serie axial con más cortes para cargarla.

### G.2 — Anidar el volumen bajo BoneToMarker0

Pegar en la Consola Python:

```python
bone_to_m0 = slicer.util.getNode("BoneToMarker0")
vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
for v in vols:
    v.SetAndObserveTransformNodeID(bone_to_m0.GetID())
print(f"OK: {len(vols)} volumen(es) anidado(s) bajo BoneToMarker0.")
```

### G.3 — Layout Four-Up y asignar el volumen a las 3 vistas

Pegar en la Consola Python:

```python
slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
volume = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")[0]
for s in ["Red", "Yellow", "Green"]:
    comp = slicer.app.layoutManager().sliceWidget(s).mrmlSliceCompositeNode()
    comp.SetBackgroundVolumeID(volume.GetID())
    slicer.app.layoutManager().sliceWidget(s).sliceLogic().FitSliceToAll()
print("OK: volumen asignado a Red/Yellow/Green.")
```

### G.4 — Configurar el Volume Reslice Driver

1. Abrir el módulo **`Volume Reslice Driver`** (extensión SlicerIGT).
2. Para cada una de las 3 vistas, configurar:

   | Vista | Driver | Mode |
   |---|---|---|
   | **Red** | `StylusTipToDodecaedro` | `Axial` (o `Position`) |
   | **Yellow** | `StylusTipToDodecaedro` | `Sagittal` (o `Position`) |
   | **Green** | `StylusTipToDodecaedro` | `Coronal` (o `Position`) |

   Si solo aparece `Inplane`/`Position`, usar **`Position`** en las tres.

### G.5 — Validar

Tocar con la punta distintas vértebras del phantom. Las 3 vistas 2D deben
re-centrarse en la zona que tocás. Si siguen la punta, la navegación funciona.

---

# H. Checklist y solución de problemas

### Checklist rápido

```
[ ] git pull al dia (incluye fixes de codigo).
[ ] PowerShell en codigo\ con (.venv) activado.
[ ] B.2: reference_dodecaedro_doctor.txt regenerado con marker 16.58.
[ ] B.3: captura con --geometry-file; anillo inferior (157-161) en verde.
[ ] B.5: reference_dodecaedro_doctor_calibrado.txt existe Y el BA convergio
        (RMSE 2D < 1 px, desplazamientos < 5 mm). Si no, B.4.5 o recapturar.
[ ] Tip calibrado por DOCK (seccion C): spread < 1.5 mm.
[ ] Slicer: OpenIGTLink conectado ANTES de correr el tracker.
[ ] Tracker corriendo (--config tracker_config_doctor.yaml): N >= 3 markers.
[ ] E.2-E.6: tip cargado, Observer instalado, Check1 < 1mm, Check2 ~ magnitud tip.
[ ] F: STL cargado, puntos marcados, RMS < 1.5 mm, jerarquia armada.
[ ] (Opcional) G: navegacion tomografica.
```

> **Recordá el `marker_mm` del doctor**: en B.2, B.4 y B.5 usá **16.58** (no 16).
> Y en todo comando del manual que diga `reference_dodecaedro.txt` o
> `--marker-mm 13.4`, cambialo por `reference_dodecaedro_doctor.txt` y `16.58`.

### Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| La captura busca IDs **170–180** aunque tu stylus sea 151–161 | Falta `--geometry-file`; el script usa por default `reference_dodecaedro.txt` | Agregar `--geometry-file iter4\data\reference_dodecaedro_doctor.txt` (B.3) |
| La cámara "abre 3 s y se cierra" sin imagen | La cámara no entrega frames (30 lecturas vacías → aborta) | Cerrar todo programa que use la webcam (Slicer/Zoom/Cámara), revisar `source: 0` en el config |
| `limpiar_captura_fantasmas.py` crashea en `np.concatenate` | `--teorico` con geometría equivocada (170–180): ningún marker coincide | Usar `reference_dodecaedro_doctor.txt` y `--marker-mm 16.58` (B.4) |
| BA: `TypeError: only 0-dimensional arrays...` en `estimar_pose_inicial` | Bug numpy 2.x (`float(tvec[2])`) | Ya corregido en el repo (`tvec[2].item()`): hacer `git pull` |
| BA `NO converge`, un anillo con desplazamientos **~23 mm** | Cobertura despareja de ese anillo, o IDs pegados en otra rotación | (a) recapturar B.3 mostrando ese anillo; (b) si la cobertura es pareja, correr B.4.5 y regenerar la geometría con el orden real |
| El tracker se cuelga en el primer frame | Slicer no conectado | Conectar OpenIGTLink (E.1) ANTES de correr el tracker |
| `FileNotFoundError: ...reference_dodecaedro_doctor_calibrado.txt` | Falta la geometría calibrada | Correr la sección B completa (genera ese archivo) |
| Pocos markers / detección intermitente | Distancia o luz | Acercar a 50–60 cm, mejorar luz, marcadores negros mate |
| Check 2 ≠ 93 mm | Observer no activo | Repetir E.4 y E.5 |
| StylusTip lejos del stylus virtual | Cadena rota o Observer caído | Repetir E.4, E.5, verificar E.6 |
| RMS registro > 5 mm | Puntos en distinto orden o mal elegidos | Re-capturar Physical_Points en el orden correcto |
| BoneSTL_Points no coinciden con Physical_Points | Falta el paso F.7 punto 3 | Anidar BoneSTL_Points bajo BoneToMarker0 |
| Las 3 vistas muestran lo mismo | Reslice Driver en `Inplane` | Cambiar a Axial/Sagittal/Coronal o Position |
| El Observer dejó de andar tras cerrar/reabrir | Se pierde al recargar la escena | Volver a pegar E.4 |

### Regla de oro del Observer Python

El Observer (E.4) se pierde si cerrás/reabrís Slicer o la escena. **Cada vez que
reabras la sesión, volvé a pegar E.4 y corré la verificación E.6** antes de
navegar. Si en cualquier momento el Check 2 deja de dar ~93 mm, re-pegá E.4.
