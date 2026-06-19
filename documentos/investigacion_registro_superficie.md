# Registro por superficie con la Femto Bolt: reemplazar la captura manual de puntos

**Proyecto:** Navegación quirúrgica óptica (MIRAI / PoyectoNavegacion) — iteración 4
**Fecha:** 2026-06-15
**Objetivo:** Eliminar el registro paciente↔modelo por *paired-point* (tocar 6–9 landmarks con el stylus, RMS ~2.8 mm) y sustituirlo por **registro por superficie**: capturar la superficie del phantom real (vértebras L1–L5 impresas) con el depth de la Femto Bolt, generar una nube de puntos, y alinear automáticamente el STL del CT sobre esa nube para superponerlo sobre el objeto real, en el frame del tracker.

Este documento sintetiza investigación de cinco frentes (métodos de registro, herramientas/librerías, optimización del sensor, repositorios existentes, y precisión esperada). Todas las afirmaciones llevan fuente al final.

---

## 1. Resumen ejecutivo y recomendación

El hueso es **rígido**: no se deforma entre el CT y el quirófano. Eso simplifica el problema — no necesitas métodos deformables (CPD no-rígido, etc.); basta una transformación rígida de 6 grados de libertad (rotación + traslación). El problema real no es la deformación sino que la nube de la Femto es **parcial** (ves una cara del hueso, no las 360°), **ruidosa** (σ ToF) y sin inicialización conocida respecto al STL.

La solución estándar y madura para esto es un pipeline **coarse-to-fine** (grueso → fino):

1. **Captura y fusión multi-frame** del depth de la Femto (TSDF) para bajar el ruido.
2. **Preprocesado**: recorte al objeto, downsample por voxel, filtrado de outliers, estimación de normales.
3. **Alineación global gruesa** sin inicialización: descriptores **FPFH + RANSAC** (o Fast Global Registration). Da una pose aproximada partiendo de cero.
4. **Refinamiento fino**: **ICP point-to-plane** (o GICP). Lleva la pose gruesa a la solución submilimétrica de mínimos cuadrados.
5. **Transform 4×4 final** → inyectarla en el frame del tracker vía OpenIGTLink y superponer el STL en 3D Slicer.

**Entorno recomendado:** **Open3D** (Python). Es la única librería que cubre TODAS las etapas en un solo stack: captura RGBD, voxel downsample, FPFH+RANSAC, ICP robusto/colored, fusión TSDF y pose-graph multiway. Tu nivel de Python intermedio es suficiente; los tutoriales oficiales son copy-paste.

**Alternativa sin código:** si prefieres quedarte dentro de Slicer, **FastModelAlign** (extensión SlicerMorph) implementa por GUI exactamente la receta Open3D (RANSAC global + ICP) — útil como validación o como camino "sin programar". El módulo nativo *Surface Registration* / *SlicerIGT* hace solo ICP plano (sin alineación global), que cae en mínimos locales si la pose inicial es mala; sirve como **refinamiento final y visualización**, no como alineación desde cero.

**Precisión esperada:** la literatura de registro por superficie en columna/ortopedia con cámaras de profundidad reporta **~1.2–2.5 mm** de error. Es decir: igual o mejor que tu paired-point actual (~2.8 mm), y sin el factor humano de tocar landmarks. Ver §6.

---

## 2. Métodos de registro por superficie

### 2.1 La familia ICP (refinamiento fino)

**ICP (Iterative Closest Point)** alterna dos pasos: empareja cada punto de la nube con el más cercano del modelo, y calcula la transformación rígida que minimiza la distancia; repite hasta converger. Es el caballo de batalla del refinamiento, pero **solo converge bien si ya partes cerca de la solución** — por eso necesita una alineación gruesa previa.

- **Point-to-point**: minimiza distancia punto a punto. Simple, más lento de converger.
- **Point-to-plane**: minimiza la distancia del punto al *plano tangente* del modelo (usando normales). Converge en menos iteraciones y es más preciso en superficies — **es la opción recomendada para tu caso** (hueso = superficie). Requiere normales bien estimadas.
- **GICP (Generalized ICP)**: modela la incertidumbre local como una covarianza ("plane-to-plane"), más robusto a ruido y a nubes parciales. Buena alternativa al point-to-plane.
- **Colored ICP**: usa además el color RGB para guiar el emparejamiento. Útil si el phantom tiene textura/marcas; la Femto te da RGB+depth alineados.
- **Kernels robustos (Tukey/Huber)**: ICP con función de pérdida robusta descarta outliers automáticamente (p. ej. Tukey con k≈σ). Importante con depth ToF ruidoso.

### 2.2 Alineación global gruesa (sin inicialización)

Es el paso que **reemplaza el "tocar puntos a mano"**: encuentra la pose aproximada desde cero.

- **FPFH + RANSAC**: calcula descriptores geométricos locales (Fast Point Feature Histograms) en ambos lados, empareja, y usa RANSAC para hallar la transformación consistente. Es el estándar de Open3D para *global registration*.
- **Fast Global Registration (FGR)**: usa los mismos FPFH pero sin RANSAC iterativo; más rápido, sin necesidad de validar/rechazar cientos de hipótesis.
- **TEASER++**: registro global **certificable** y extremadamente robusto a outliers (tolera hasta ~99% de correspondencias falsas). Es la opción más sólida cuando la nube es muy parcial o ruidosa; da garantías de optimalidad. Recomendado como alternativa robusta al RANSAC clásico.
- **Go-ICP**: ICP con búsqueda global (branch-and-bound) que garantiza el óptimo global. Lento; útil como referencia, no para tiempo real.

### 2.3 Métodos probabilísticos y deep learning

- **CPD (Coherent Point Drift)**: registro probabilístico (GMM). Su versión no-rígida es para tejidos deformables — **no la necesitas** porque el hueso es rígido. La versión rígida es una alternativa a ICP robusta a ruido, disponible en `probreg`.
- **Deep learning (estado del arte)**: para nubes de **bajo solape** (tu caso: ves solo una cara del hueso parcial) los métodos aprendidos modernos superan a FPFH: **GeoTransformer** y **PREDATOR** están diseñados específicamente para low-overlap; **DGR (Deep Global Registration)** y **FCGF** dan descriptores aprendidos que alimentan el paso grueso. Requieren GPU y son más complejos de montar — recomendados como **fase 2** si el pipeline clásico (FPFH+ICP) no alcanza la precisión deseada.

**Veredicto de métodos:** empieza con **FPFH+RANSAC (o FGR) → ICP point-to-plane**. Si la nube parcial da problemas de robustez, escala a **TEASER++** para el global. Reserva deep learning (GeoTransformer/PREDATOR) como mejora futura.

---

## 3. Pipeline concreto recomendado

```
[Femto Bolt depth+RGB]
   │  pyorbbecsdk2: NFOV unbinned 640x576, FUERA de la caja de luz
   ▼
[Fusión multi-frame TSDF]   Open3D ScalableTSDFVolume, ~30–100 frames estáticos
   │  → reduce ruido aleatorio por 1/√N
   ▼
[Nube de puntos del objeto]   volume.extract_point_cloud()
   │
   ▼
[Preprocesado]   recorte por profundidad al objeto → voxel_down_sample(2–3 mm)
   │             → remove_statistical_outlier (quita flying pixels)
   │             → estimate_normals
   ▼
[Alineación GLOBAL gruesa]   FPFH → registration_ransac_based_on_feature_matching
   │             (o Fast Global Registration; o TEASER++ si muy parcial)
   ▼
[Refinamiento FINO]   registration_icp point-to-plane, robust kernel (Tukey k=σ)
   │             → RegistrationResult.transformation = matriz 4×4 STL→nube
   ▼
[Transform al frame del tracker]   componer con la pose conocida del marker 0
   │             (referencia del paciente) → enviar por OpenIGTLink
   ▼
[3D Slicer]   STL superpuesto sobre el objeto real, sin tocar landmarks
```

Notas de implementación:

- El STL del CT está en milímetros y en el frame del CT; la nube de la Femto está en el frame de la cámara. La transform de ICP te da STL→nube_cámara. Para llevarlo al frame del paciente compón con la pose del **marker 0** (referencia del paciente) que ya rastreas con ArUco. Eso da la cadena completa que Slicer ya espera.
- **No reinventes la cadena de Slicer.** Tu jerarquía validada (`BoneToMarker0` en root, Observer Python) sigue valiendo; solo cambias *cómo* se calcula `BoneToMarker0`: antes por paired-point, ahora por ICP de superficie.
- Trabaja siempre en metros internamente en Open3D (su convención) y convierte a mm al exportar a Slicer.

---

## 4. Aprovechar al MÁXIMO la Femto Bolt

La Femto Bolt usa el **mismo sensor ToF del Azure Kinect**, así que toda la literatura de Azure Kinect aplica directamente. Claves cuantitativas para sacarle el máximo:

**Modo de profundidad.** Usa **NFOV unbinned: 640×576 @ 30 fps, rango 0.5–3.86 m**. Es la mejor precisión para tu objeto pequeño (~20 cm) a 0.5–0.7 m. WFOV (120°) añade campo que no necesitas y baja a 15 fps. Microsoft mismo dice que NFOV es "ideal para escenas con menor extensión en X-Y".

**Calentamiento (lo más importante y barato).** El sensor **deriva ~2 mm hacia arriba durante los primeros ~60 min** hasta estabilizarse térmicamente. Calienta la cámara **40–60 min** antes de cualquier captura que vayas a tomar como cuantitativa. Esto probablemente pesa más que cualquier filtro.

**Fusión multi-frame (la gran palanca).** Promediar N frames de una escena estática reduce el ruido aleatorio por **1/√N**: 4 frames → 2×, 16 → 4×, ~32 → ~5.7×. Como tu phantom está fijo, esto es ideal. La fusión TSDF de Open3D (ScalableTSDFVolume + `volume.integrate` por frame) hace justo esto y además rellena huecos de multipath capturando desde varias vistas. **Captura estático, fusiona 30–100 frames.**

**Distancia y ángulo.** Mantén el objeto a **0.5–0.7 m**, cara casi frontal y superficie **mate** (no brillante ni traslúcida). El ruido crece con la distancia y con el ángulo entre sensor y superficie. Medición independiente de laboratorio: la desviación del píxel central es **~0.5 mm a 0.8 m** (muy por debajo del peor caso de 17 mm de la spec) — confirma que tu σ empírico de 4.5 mm está dominado por **multipath de la caja de luz, no por ruido del sensor**.

**Multipath y flying pixels.** El multipath (un píxel integra luz reflejada de varios objetos) es la fuente sistemática dominante NO cubierta por la spec de ±11 mm. Por eso: **captura SIEMPRE fuera de la caja de luz** (ya lo tienes documentado: bias +57 mm dentro, −10 mm fuera). Los *flying pixels* en los bordes (mezcla de primer plano + fondo) se eliminan recortando por profundidad al objeto y aplicando `remove_statistical_outlier` / `remove_radius_outlier` en Open3D. Filtro bilateral guiado por RGB como pase espacial opcional antes de mallar.

**Obtener la nube en pyorbbecsdk2.** Directo del frameset: `points = frames.get_point_cloud(camera_param)` (XYZ) o `frames.get_color_point_cloud(camera_param)` (XYZRGB). Convertible a NumPy estructurado y guardable a `.ply`. Instala con `pip install pyorbbecsdk2` (no el viejo `pyorbbecsdk` 1.3.2, que está roto en Windows). Open3D también puede construir un `RGBDImage` desde los arrays depth/color y llamar `create_point_cloud_from_rgbd_image`.

---

## 5. Herramientas y librerías comparadas

| Herramienta | Cubre | Veredicto |
|---|---|---|
| **Open3D** (Python) | Captura RGBD, downsample, FPFH+RANSAC/FGR, ICP point-to-plane/colored/robusto, TSDF, multiway pose-graph | **Núcleo recomendado.** Única que cubre todo el pipeline en Python. Tutoriales copy-paste. |
| **FastModelAlign** (SlicerMorph) | RANSAC global + ICP, por GUI dentro de Slicer | **Alternativa sin código.** Misma receta Open3D pero en la interfaz. Buena para validar o si no quieres programar. |
| **SlicerIGT / Surface Registration** (Slicer nativo) | Solo ICP (sin global) | Para **refinamiento final y visualización**, no para alinear desde cero (cae en mínimos locales). Ya en tu stack. |
| **probreg** (Python) | CPD, FilterReg, GMMReg, Bayesian CPD; se integra con Open3D | Útil para el paso grueso robusto a nubes parciales/ruidosas. |
| **TEASER++** (C++/Python) | Registro global certificable, ~99% tolerancia a outliers | Mejor opción robusta para el global cuando la nube es muy parcial. |
| **PCL** (Point Cloud Library) | Registro 3D completo en C++ | Potente pero binding de Python débil; más fricción que Open3D. |
| **MeshLab** | Alineación manual/interactiva | Manual; útil para inspección puntual, no para automatizar. |

---

## 6. Precisión esperada y validación

Errores reportados en la literatura de registro por superficie con cámaras de profundidad, para columna/ortopedia/neurocirugía:

- **Surface-matching vs CBCT en columna: 1.20 ± 0.42 mm** (a 1.94 ± 0.64 mm según método).
- **Topográfico óptico: ~1.67 mm.**
- **Coarse + ICP + refinamiento DL: ~1.58 mm.**
- **EasyREG (markerless ToF, HoloLens): 3.77 mm** en registro estático, 4.82 mm bajo tracking dinámico.
- **Benchmark de cámaras comerciales (neurocirugía):** mejores cámaras (RealSense D405, ZED-M+) logran **TRE 2.36 ± 0.46 mm** y **2.49 ± 0.35 mm** con ICP / Deep Global Registration.

**Conclusión:** el rango realista es **~1.2–2.5 mm** con cámaras de buena calidad y pipeline coarse-to-fine — comparable o mejor que tu paired-point actual (~2.8 mm), eliminando el factor humano. La Femto, con buen calentamiento + fusión multi-frame + captura fuera de la caja, debería entrar en ese rango.

**Cómo validar (cuantitativo, una variable a la vez):**

1. Imprime el phantom L1–L5 cuyo STL ya tienes (ground truth conocido).
2. Coloca puntos de verificación físicos (divots) cuya posición en el STL conoces.
3. Tras el registro por superficie, toca esos divots con el stylus calibrado y mide el error (TRE) entre la punta y la posición esperada en el STL.
4. Compara contra el RMS del paired-point en el mismo phantom. Reporta media ± std sobre varias capturas.
5. Repite variando: nº de frames fusionados, distancia, con/sin calentamiento — para aislar qué aporta cada factor.

---

## 7. Repositorios para clonar y estudiar

**Lo más parecido a tu objetivo (arquitectura coarse→fine en Open3D):**

- **HL2SS-Depth-Registration** — captura nube de profundidad, fusión multi-frame, registro coarse+fine con **Open3D** para overlay del modelo preop en tiempo real; canal Python↔Unity. La lógica de registro es trasplantable casi tal cual cambiando la fuente de cámara (HoloLens → Orbbec). https://github.com/Enzo-Kerkhof/HL2SS-Depth-Registration
- **End2Reg** — registro markerless RGB-D para cirugía de columna, con código + datasets (SpineDepth, SpineAlign). Deep learning, requiere GPU. https://github.com/lorenzopettinari/End2Reg · proyecto: https://lorenzopettinari.github.io/end-2-reg/

**Tu propio stack (registro dentro de Slicer):**

- **SlicerIGT — FiducialsToModelRegistration** (ICP markups→malla): https://github.com/SlicerIGT/SlicerIGT
- **SlicerOpenIGTLink** (puente Slicer↔cámara/tracker): https://github.com/openigtlink/SlicerOpenIGTLink
- **FastModelAlign / SlicerMorph** (RANSAC+ICP por GUI): extensión de SlicerMorph.

**Motores de registro (bloques de construcción):**

- **Open3D** — tutoriales oficiales ICP y global registration: https://github.com/isl-org/Open3D · https://www.open3d.org/docs/release/tutorial/pipelines/icp_registration.html
- **probreg** — CPD/FilterReg/GMMReg, integra con Open3D: https://github.com/neka-nat/probreg
- **TEASER++** — registro global robusto certificable: https://github.com/MIT-SPARK/TEASER-plusplus
- **FCGF** / **DeepGlobalRegistration** — descriptores y registro global aprendido (GPU): https://github.com/chrischoy/FCGF · https://github.com/chrischoy/DeepGlobalRegistration
- **GeoTransformer** / **PREDATOR** — estado del arte low-overlap (GPU): buscar en GitHub por nombre.

**Curadurías:**

- awesome-point-cloud-registration: https://github.com/XuyangBai/awesome-point-cloud-registration

**Datasets RGB-D de columna (para validar sin imprimir):**

- **SpineDepth** (RGB-D + ground truth L1–L5, 10 cadáveres): https://rocs.balgrist.ch/en/open-access/spinedepth/
- **SpineAlign** (in-vivo): https://huggingface.co/datasets/zcbecda/SpineAlign

---

## 8. Plan de arranque sugerido

1. **Montar Open3D** en el venv de iter4 (`pip install open3d`). Validar con un PLY de prueba.
2. **Script de captura+fusión TSDF** con pyorbbecsdk2: NFOV unbinned, fuera de la caja, ~50 frames, exportar nube `.ply`. Verbose iter-por-iter.
3. **Script de registro** Open3D: cargar STL (muestrear a nube), cargar nube capturada, preprocesar, FPFH+RANSAC global, ICP point-to-plane, imprimir fitness/RMSE de `RegistrationResult` y la matriz 4×4.
4. **Validar cuantitativamente** sobre el phantom impreso (TRE en divots) antes de tocar Slicer.
5. **Inyectar la transform** en Slicer vía OpenIGTLink reusando la jerarquía validada (solo cambia el origen de `BoneToMarker0`).
6. Si la precisión no alcanza: probar TEASER++ para el global, o colored ICP, o subir frames de fusión.

Clona **HL2SS-Depth-Registration** primero como referencia de arquitectura; usa **Open3D + probreg** como motor; conéctalo a **SlicerIGT + SlicerOpenIGTLink**.

---

## Fuentes

**Métodos de registro**
- Open3D — Global registration (FPFH/RANSAC/FGR): https://www.open3d.org/docs/release/tutorial/pipelines/global_registration.html
- Open3D — ICP registration (point-to-point / point-to-plane / robust kernels): https://www.open3d.org/docs/release/tutorial/pipelines/icp_registration.html
- Open3D — Colored point cloud registration: https://www.open3d.org/docs/release/tutorial/pipelines/colored_pointcloud_registration.html
- Open3D — Multiway registration (pose graph): https://www.open3d.org/docs/release/tutorial/pipelines/multiway_registration.html
- TEASER++ (registro global certificable, robusto a outliers): https://github.com/MIT-SPARK/TEASER-plusplus
- GeoTransformer (low-overlap SOTA): https://arxiv.org/abs/2202.06688
- PREDATOR (registro low-overlap): https://arxiv.org/abs/2011.13005

**Sensor / Femto Bolt — depth**
- Orbbec Femto Bolt (producto): https://www.orbbec.com/products/tof-camera/femto-bolt/
- Orbbec Femto Bolt datasheet: https://d1cd332k3pgc17.cloudfront.net/wp-content/uploads/2023/08/ORBBEC_Datasheet_Femto-Bolt-1.pdf
- Azure Kinect DK depth camera (modos NFOV/WFOV, multipath, error sistemático): https://learn.microsoft.com/en-us/azure/kinect-dk/depth-camera
- Evaluation of the Azure Kinect (Sensors 2021, ruido por píxel, calentamiento): https://pmc.ncbi.nlm.nih.gov/articles/PMC7827245/
- pyorbbecsdk — guardar nube de puntos: https://github.com/orbbec/pyorbbecsdk/blob/main/examples/save_pointcloud_to_disk.py
- pyorbbecsdk QuickStart: https://orbbec.github.io/pyorbbecsdk/source/3_QuickStarts/QuickStart.html
- Azure Kinect con Open3D: https://www.open3d.org/docs/release/tutorial/sensor/azure_kinect.html

**Repositorios / proyectos**
- HL2SS-Depth-Registration: https://github.com/Enzo-Kerkhof/HL2SS-Depth-Registration (paper: https://doi.org/10.1007/s11548-025-03328-x)
- End2Reg: https://github.com/lorenzopettinari/End2Reg · https://lorenzopettinari.github.io/end-2-reg/ · https://arxiv.org/abs/2512.13402
- SlicerIGT: https://github.com/SlicerIGT/SlicerIGT
- SlicerOpenIGTLink: https://github.com/openigtlink/SlicerOpenIGTLink
- probreg: https://github.com/neka-nat/probreg
- Open3D: https://github.com/isl-org/Open3D
- FCGF: https://github.com/chrischoy/FCGF
- DeepGlobalRegistration: https://github.com/chrischoy/DeepGlobalRegistration
- awesome-point-cloud-registration: https://github.com/XuyangBai/awesome-point-cloud-registration

**Precisión / validación**
- Surface-matching vs CBCT en columna: https://pmc.ncbi.nlm.nih.gov/articles/PMC11428421/
- Optical topographic registration (Nature Sci Rep): https://www.nature.com/articles/s41598-018-32424-z
- Registro markerless RGB-D columna (Liebmann et al.): https://www.sciencedirect.com/science/article/pii/S1361841523002876 · https://arxiv.org/abs/2308.02917
- EasyREG (markerless depth, HoloLens): https://arxiv.org/abs/2504.09498
- Benchmark cámaras de profundidad para registro intraoperatorio: https://link.springer.com/article/10.1007/s11548-025-03416-y
- SpineDepth dataset: https://rocs.balgrist.ch/en/open-access/spinedepth/
