# 05 — Reproducir desde cero (dodecaedro nuevo)

**Fecha**: 2026-05-20. Guía para usar el sistema MIRAI con un dodecaedro distinto al actual (otro tamaño, otros IDs, otro diccionario ArUco).

## ⚠️ ACTUALIZACIÓN ITER 4 (2026-06-15) — cambios respecto a esta guía

Esta guía es de iter 2 (webcam). Para iter 4 (Femto Bolt) cambia lo siguiente:

- **Todos los scripts están en `codigo\iter4\`** y el config es
  `iter4\tracker_config.yaml`. Anteponer `iter4\` a los comandos.
- **El paso 3.6 (pivote) quedó OBSOLETO.** El pivote clásico no reproduce con
  la cámara lateral del Femto Bolt. La calibración del tip ahora es por
  **DOCK / template** con la placa impresa `stl\placa_dock_v3\`:
  ```powershell
  python iter4\calibrar_tip_divot.py --divot DOCK --plate-id 2 --plate-mm 59.6 `
      --output-matriz iter4\data\StylusTipToDodecaedro_viejo_dock
  ```
  (Encajar el stylus en el dock, rotar el conjunto frente a la cámara, ESPACIO
  en 4-6 orientaciones, q. Buscar spread <1.5 mm. Ver `stl\placa_dock_v3\README.md`.)
- **El marker del paciente (Marker0) mide 80.0 mm**, no 60.8 (config iter 4).
- **Captura del BA: SIEMPRE fuera de la caja de luz** (multipath del depth ToF).
- La nota §7.2 (BA denso por bug de sparsity) ya NO aplica: en iter 4 el
  `jac_sparsity` está conectado y validado (default `--sparse` ON). Si un BA
  no converge, ver memoria `stylus-impreso-diagnostico-ba`.
- Pre-requisito: depende de `pyorbbecsdk2` (no el viejo `pyorbbecsdk`).

El resto del pipeline (generar geometría, captura, topología, BA) es conceptualmente igual.

## Resumen ejecutivo

**Sí, el sistema es replicable.** Todo lo que cambia entre dodecaedros está configurable por:
- CLI flags (scripts de calibración).
- `tracker_config.yaml` (tracker en vivo).

**Asunción crítica**: el dodecaedro nuevo es **regular pentagonal** (12 caras pentagonales). Si fuera otra forma (cubo, octaedro, dodecaedro romboidal) la matemática de `generar_reference_dodecaedro.py` NO aplica.

**Asunción adicional**: 11 markers (TOP + 5 anillo superior + 5 anillo inferior), base sin marker. Si tu dodecaedro tiene más o menos markers, el código no soporta esto sin cambios.

---

## 1. Datos que tenés que medir/anotar antes de empezar

Anotá estos valores para el dodecaedro nuevo:

| Dato | Cómo obtenerlo | Ejemplo iter 2 actual |
|---|---|---|
| **edge_mm** | Largo de una arista pentagonal del dodecaedro (con calibre) | 20.0 mm |
| **marker_mm** | Lado del marker ArUco impreso pegado (cuadrado) | 16.0 mm |
| **dictionary** | Diccionario ArUco usado | `DICT_ARUCO_MIP_36h12` |
| **id_top** | ID del marker en la cara superior (donde "apunta" el stylus hacia arriba) | 151 |
| **ids_superior** | 5 IDs en el anillo superior, en orden ciclico (CCW visto desde arriba) | 152,153,154,155,156 |
| **ids_inferior** | 5 IDs en el anillo inferior (orden ciclico, podés poner cualquiera — Etapa C.5 detecta el real) | 157,158,159,160,161 |
| **id_marker_referencia_paciente** | ID del marker individual pegado al hueso (NO al dodecaedro) | 0 (marker 60.8 mm) |
| **tamaño marker_referencia_mm** | Lado del marker individual | 60.8 mm |

---

## 2. Pre-requisito: calibración intrínseca de la cámara

**No cambia con el dodecaedro nuevo.** Si usás la misma cámara con el mismo foco/iluminación, el archivo `data/camera_calibration_caja_luz.yml` sigue siendo válido. Solo recalibrar si la óptica de la cámara cambia.

---

## 3. Pipeline de calibración (orden estricto)

### Paso 3.1 — Editar tracker_config.yaml

Abrir `codigo/tracker_config.yaml` y editar:

```yaml
markers:
  dictionary: DICT_ARUCO_MIP_36h12  # ← el diccionario nuevo
  list:
    - id: 0                          # ← ID del marker del paciente
      name: Marker0
      size_mm: 60.8                  # ← tamaño nuevo
rigid_bodies:
  - name: Dodecaedro
    geometry_file: data/reference_dodecaedro_calibrado.txt
```

El resto del config (filtering, igtlink, debug, min_markers) puede quedar igual.

### Paso 3.2 — Generar geometría teórica del dodecaedro nuevo

```powershell
python generar_reference_dodecaedro.py `
    --id-top 1 `
    --ids-superior 2,3,4,5,6 `
    --ids-inferior 7,8,9,10,11 `
    --edge-mm 25 `
    --marker-mm 20 `
    --output data/reference_dodecaedro.txt
```

Reemplaza valores con los tuyos. Va a correr 11 chequeos de validación matemática y guardar el archivo.

Si algún `[FAIL]` aparece: probablemente `marker_mm` es muy grande para `edge_mm` (no cabe en la cara pentagonal). Reducir `marker_mm` o aumentar `edge_mm`.

### Paso 3.3 — Captura de dataset para BA

Montá el dodecaedro en la mesa, rotalo libremente frente a la cámara durante 60s cubriendo todas las orientaciones:

```powershell
python captura_calibracion.py --duracion 60 --output capturas_calibracion.npz
```

Esperado: 1000-2500 frames con ≥2 markers detectados.

### Paso 3.4 — Detección de topología real (RECOMENDADO)

Sirve para que el BA arranque con el orden REAL de IDs (los anillos podrían estar rotados respecto a tu suposición):

```powershell
python calibrar_topologia.py --id-top 1 --edge-mm 25
```

Genera `data/reference_dodecaedro_real.txt`. Si `--id-top` o `--edge-mm` no son los tuyos, ajustar.

**Nota**: si las distancias inter-marker matcheen dentro de 3 mm con `edge_mm`, el dodecaedro físico está bien construido. Si no, revisar las medidas físicas.

### Paso 3.5 — Bundle Adjustment

```powershell
python calibrar_rigid_body.py `
    --teorico data/reference_dodecaedro_real.txt `
    --ancla 1 `
    --marker-mm 20 `
    --max-frames 150 `
    --max-nfev 3000
```

Reemplazá `--ancla` con tu `id_top` y `--marker-mm` con el tuyo.

Esperado: RMSE final ~0.4-0.6 px, status `2` (`ftol`), Procrustes RMS <2 mm.

### Paso 3.6 — Calibración de pivote

Ensamblá el stylus (dodecaedro + barra + punta). Clavá la punta en el cartón. Pivoteá 60s:

```powershell
python test_pivote.py --duracion 60
```

Esperado:
- Inliers RANSAC >85%.
- Diferencia esfera vs AX=b <1 mm (calibración robusta).
- STD por eje <2 mm.
- Genera `StylusTipToDodecaedro.npy` y `.txt`.

**Nota sobre umbral RANSAC**: el script usa `umbral_inlier=1.5` mm. Para un dodecaedro/stylus considerablemente más grande (digamos stylus de 200 mm en lugar de 88 mm), considerar subir a 2-3 mm editando línea 298 de `test_pivote.py`.

---

## 4. Pipeline live (tracker + Slicer)

### Paso 4.1 — Tracker en vivo

```powershell
python tracker.py --config tracker_config.yaml
```

Esperado: 28-30 FPS, mostrando "Dodecaedro: N markers" con N≥3.

### Paso 4.2 — Conectar Slicer

1. Abrir 3D Slicer. Módulo `OpenIGTLinkIF`. Conectar como CLIENT a `localhost:18944`.
2. Verificar que llegan `Marker0ToTracker` y `DodecaedroToTracker`.

### Paso 4.3 — Cargar StylusTip en Slicer (Python Console)

```python
import numpy as np
import vtk
M = np.load(r"C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\StylusTipToDodecaedro.npy")
node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "StylusTipToDodecaedro")
m = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        m.SetElement(i, j, float(M[i, j]))
node.SetMatrixTransformToParent(m)

# Crear punto StylusTip
tip = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "StylusTip")
tip.AddControlPoint([0, 0, 0])
tip.SetAndObserveTransformNodeID(node.GetID())
```

### Paso 4.4 — Configurar jerarquía y Transform Processor

Ver memory `project_jerarquia_final_slicer.md` para el orden exacto de operaciones validado.

### Paso 4.5 — Registro paired-point

Ver memory `project_jerarquia_final_slicer.md` punto 5 en adelante.

---

## 5. Qué se ajusta automáticamente vs qué requiere atención

### Se ajusta automático (no tocar código)

| Cambio | Mecanismo |
|---|---|
| IDs distintos | CLI flags |
| edge_mm distinto | CLI flag `--edge-mm` |
| marker_mm distinto | CLI flag `--marker-mm` |
| Diccionario ArUco distinto | `tracker_config.yaml: markers.dictionary` |
| Marker de referencia paciente distinto | `tracker_config.yaml: markers.list` |
| Más/menos rigor en min_markers | `tracker_config.yaml: rigid_bodies_quality.min_markers` |

### Requiere atención (revisar/ajustar)

| Caso | Acción |
|---|---|
| Stylus muy largo (>200 mm) | Considerar subir `umbral_inlier` en `test_pivote.py` línea ~298 (1.5 → 3.0) |
| Marker individual tracker en otro tamaño | Asegurar que `markers.list[i].size_mm` está correcto |
| Iluminación pobre → pocos markers detectados | Bajar `min_markers` a 2 temporalmente o mejorar luz |
| Captura con muy pocos frames (<100) | Re-capturar con más duración |

### NO funciona sin cambio mayor de código

| Caso | Por qué |
|---|---|
| Dodecaedro NO regular (cubo, octaedro) | La matemática en `generar_reference_dodecaedro.py` asume dodecaedro regular pentagonal |
| Menos de 11 markers o más de 11 | `calibrar_topologia.py` espera estructura 1+5+5; `cargar_rigid_body` espera lecturas con 16 tokens |
| Distintos IDs Tracker vs Slicer | Los nombres de TransformMessage son fijos por `name` del config — Slicer-side hay que adaptar nombres |
| Diccionario que no existe en cv2.aruco | `obtener_diccionario` falla con error claro listando disponibles |

---

## 6. Checklist rápido para próximo dodecaedro

```
[ ] Medir edge_mm y marker_mm con calibre.
[ ] Anotar IDs del TOP, anillo superior, anillo inferior.
[ ] Anotar ID y tamaño del marker individual (paciente).
[ ] Editar tracker_config.yaml (dictionary, markers.list, geometry_file).
[ ] Generar teorico:     python generar_reference_dodecaedro.py --id-top ... --ids-superior ... --ids-inferior ... --edge-mm ... --marker-mm ...
[ ] Capturar dataset:    python captura_calibracion.py --duracion 60
[ ] Detectar topologia:  python calibrar_topologia.py --id-top ... --edge-mm ...
[ ] BA:                   python calibrar_rigid_body.py --teorico data/reference_dodecaedro_real.txt --ancla ... --marker-mm ... --max-frames 150 --max-nfev 3000
[ ] Pivote:               python test_pivote.py --duracion 60
[ ] Validar BA: RMSE <1 px, Procrustes <2 mm
[ ] Validar pivote: STD <2 mm, diff esfera/AX=b <1 mm
[ ] Tracker:              python tracker.py --config tracker_config.yaml
[ ] Slicer: conectar OpenIGTLink, cargar StylusTipToDodecaedro.npy, configurar jerarquia.
[ ] Validacion final: RMS paired-point <3 mm.
```

**Tiempo total estimado (sin contar setup físico y registro Slicer)**: 30-40 minutos de procesamiento de scripts.

---

## 7. Limitaciones conocidas

1. **Filesystem de Windows con OneDrive trunca archivos al escribir**. Los scripts críticos (`calibrar_rigid_body.py`, `test_pivote.py`) tienen validación + fsync, pero `np.save` puede fallar silenciosamente en otros casos. Si un archivo de salida parece más chico de lo esperado, re-correr.

2. **Bug en `construir_jac_sparsity` del BA** (tarea pendiente #22 en memory). Workaround: usar BA denso (default). Lento para 500+ frames pero correcto.

3. **Filtro 1-Euro sólo en posición**. Para jitter rotacional severo, ajustar `min_markers` hacia arriba en lugar de tocar el filtro.

4. **Ancla del BA tiene rotación libre (3 DOF)**. Soluciona sesgo de inclinación del marker ancla físico, pero introduce gauge ambiguity rotacional residual menor. Para pipeline actual no es problema.

5. **`.h5` para Slicer se genera por Python Console** (no automatizado). Si querés `.h5` directamente desde el script, hay que agregar `h5py` con formato Slicer Transform.
