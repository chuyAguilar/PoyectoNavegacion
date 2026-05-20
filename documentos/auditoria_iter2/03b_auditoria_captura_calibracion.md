# 03b — Auditoría de `captura_calibracion.py`

**Fase 3 de la auditoría de iteración 2 · Script de Etapa C.** Fecha: 2026-05-16.

## Resumen ejecutivo

- **Funcionalidad principal**: correcta. Captura frames de video con la cámara configurada, detecta markers ArUco con `cv2.aruco`, filtra los del rigid body, guarda detecciones 2D con timestamp en `capturas_calibracion.npz` para que el bundle adjustment (Etapa D) las consuma.
- **Matemática**: no aplica matemática compleja, solo orquesta detección + serialización. No hay bugs de correctness.
- **Sin embargo**: hay múltiples áreas de mejora en **robustez, reproducibilidad, metadata, UX y código**. Lista categorizada en §3.

## 1. Descripción del script

**Entrada:** `tracker_config.yaml` + el `reference_dodecaedro.txt` (default) o `reference_dodecaedro_calibrado.txt` (según config) — solo para leer los IDs del rigid body. Lee también `camera_calibration_caja_luz.yml` para K, dist.

**Pipeline en runtime:**
1. Carga config YAML y calibración intrínseca.
2. Crea diccionario ArUco según `markers.dictionary` de la config.
3. Lee del archivo de geometría los IDs del rigid body (rb_ids).
4. Configura `cv2.aruco.ArucoDetector` con `CORNER_REFINE_SUBPIX`. Fallback a la API legacy si `ArucoDetector` no existe.
5. Abre la cámara con backend MSMF (Windows) + FOURCC MJPG + resolución 640×480 @ 30 FPS.
6. Loop durante `--duracion` segundos:
   - Lee frame, convierte a gris.
   - Detecta markers (todos los del diccionario).
   - Filtra solo los que están en `rb_ids`.
   - Si hay ≥ 2 markers del rigid body en el frame, lo guarda (timestamp + dict{id: corners 4×2}).
   - Renderiza preview con texto.
7. Al terminar: imprime estadísticas (frames totales, frames útiles, pares de markers más/menos frecuentes).
8. Guarda `capturas_calibracion.npz` con: `frames_data` (object array), `K`, `dist`, `rb_ids`.

**Salida:** `capturas_calibracion.npz` que será semilla del bundle adjustment.

## 2. Auditoría matemática y de APIs

### 2.1 Filtros de frame válido — correctos

- **`if mid in rb_ids`**: filtra detecciones que NO pertenecen al rigid body (por ejemplo, el marker 0 del hueso). Correcto: los markers no-rigid-body no aportan al BA del dodecaedro.
- **`if len(detecciones) >= 2`**: requiere al menos 2 markers del rigid body para guardar el frame. Correcto: con 1 solo marker no hay relación geométrica entre markers visibles, no aporta restricciones al BA del rigid body. Con 2 ya hay relación.

### 2.2 API `cv2.aruco.ArucoDetector` — verificada con Context7

OpenCV 4.13 tiene la API nueva `cv2.aruco.ArucoDetector(dict, params)` con `detectMarkers(image)` que es la forma canónica desde 4.7+. El script la usa con fallback correcto a la API legacy. ✓

### 2.3 `CORNER_REFINE_SUBPIX` — adecuado pero hay alternativas

OpenCV ofrece 4 métodos de refinamiento de esquinas:

| Método | Velocidad | Precisión | Notas |
|---|---|---|---|
| `CORNER_REFINE_NONE` | Rápido | Baja (precisión píxel) | Solo para preview o no-PnP |
| `CORNER_REFINE_SUBPIX` ✓ (actual) | Rápido | Razonable (sub-pixel via `cornerSubPix`) | Lucas-Kanade clásico |
| `CORNER_REFINE_CONTOUR` | Medio | Alta en algunos casos | Usa contornos de la cara del marker |
| `CORNER_REFINE_APRILTAG` | Más lento | Más alta | Estilo AprilTag, robust a iluminación |

Según docs y benchmarks de la comunidad, **`APRILTAG`** suele dar mejor precisión sub-pixel a costa de ~2-3× más tiempo de CPU. Para BA donde queremos sub-mm en el resultado final, sería interesante **comparar** ambos con la misma escena: capturar dos datasets idénticos (uno con SUBPIX, uno con APRILTAG) y ver cuál da mejor RMSE en el BA.

**Nota relevante**: OpenCV tiene un issue conocido ([opencv#24113](https://github.com/opencv/opencv/issues/24113)) sobre comportamiento incorrecto de `CORNER_REFINE_SUBPIX` en algunos casos de aruco boards. No afecta detecciones individuales (que es lo nuestro), pero conviene tenerlo presente.

### 2.4 Parámetros adicionales del detector — no se tocan

El script usa defaults de OpenCV para:
- `cornerRefinementWinSize` (default 5)
- `cornerRefinementMaxIterations` (default 30)
- `cornerRefinementMinAccuracy` (default 0.1)
- `adaptiveThreshWinSizeMin/Max/Step` (defaults para preprocesamiento)
- `minMarkerPerimeterRate`, `maxMarkerPerimeterRate` (rangos de tamaño)

Para markers de 16 mm a 30-50 cm de distancia, los defaults probablemente están bien. Si se quisiera optimizar, valdría la pena hacer un sweep paramétrico, pero no es prioritario.

### 2.5 Formato de salida `np.array(dtype=object)` — fuente de fricción a futuro

```python
np.savez_compressed(args.output,
                    frames_data=np.array(frames_data, dtype=object),
                    ...)
```

`frames_data` es una lista de dicts Python. Al meterla en `np.array(dtype=object)`, NumPy serializa con pickle internamente. **NumPy 2.x emite warning y al cargar con `np.load` requiere `allow_pickle=True` explícito** (deshabilitado por defecto por razones de seguridad). El script de BA (Etapa D) muy probablemente lo cargue con `allow_pickle=True`, así que funciona, pero es un anti-patrón.

Mejor estructura tabular (sin pickle):
- `timestamps`: array float (N,)
- `frame_ids`: array int (M,) — un índice por detección
- `marker_ids`: array int (M,) — el ID del marker detectado
- `corners`: array float (M, 4, 2) — las 4 esquinas 2D de cada detección
- `frame_starts`: array int (N+1,) — offsets para indexar `marker_ids` y `corners` por frame

Esto se carga sin `allow_pickle`, es más rápido, y es portable a otros lenguajes (HDF5, Parquet).

## 3. Hallazgos: mejoras propuestas

### 3.1 [ALTA] Validación de prerrequisitos antes de capturar

Hoy, si:
- el archivo de geometría no existe → `FileNotFoundError` feo en línea 56 (en medio del loop de lectura).
- la calibración intrínseca no existe → `cv2.error` feo.
- la cámara no abre → SÍ tiene mensaje claro y `sys.exit(1)`. ✓
- el path de salida no es escribible → falla AL FINAL después de haber capturado 60s. **Pierde todo el dataset.**

Propuesta: agregar `_validar_prerrequisitos()` antes del countdown, que:
- Verifica que `cfg["camera"]["calibration_file"]` existe y tiene `camera_matrix` + `distortion_coefficients`.
- Verifica que cada `rigid_bodies[i].geometry_file` existe.
- Hace `touch` o `open(..., 'w')` al `--output` para verificar permisos antes de empezar.
- Si algo falla, mensaje claro y `sys.exit(1)` ANTES del countdown.

### 3.2 [ALTA] Verificación post-configuración de la cámara

Hoy:
```python
cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg["width"])
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg["height"])
cap.set(cv2.CAP_PROP_FPS, cam_cfg.get("fps", 30))
```

Si la cámara no soporta esos modos, OpenCV los acepta sin error pero entrega frames a otra resolución/FPS. No nos enteramos.

Propuesta: tras los `set`, hacer:
```python
w_real = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h_real = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps_real = cap.get(cv2.CAP_PROP_FPS)
fourcc_real = int(cap.get(cv2.CAP_PROP_FOURCC))
print(f"[Camara real] {w_real}x{h_real} @ {fps_real:.1f} FPS, FOURCC={...}")
if (w_real, h_real) != (cam_cfg["width"], cam_cfg["height"]):
    print(f"[WARN] Resolucion solicitada {cam_cfg['width']}x{cam_cfg['height']} != real")
```

Y guardar **estos valores reales** en el `.npz`. Si después la calibración intrínseca es para 640×480 pero la cámara entregó 1280×720, el BA fallará silenciosamente.

### 3.3 [ALTA] Metadata extensiva en el .npz

Hoy guarda: `frames_data`, `K`, `dist`, `rb_ids`. **Le falta** información crítica para reproducibilidad y debugging:

- Versión de OpenCV (`cv2.__version__`).
- Versión de Python.
- Nombre del diccionario ArUco (`"DICT_ARUCO_MIP_36h12"`).
- Backend de cámara real (`"MSMF"`).
- Resolución real (`640, 480`).
- FPS reportado por cámara (`30.0`).
- FOURCC real (`"MJPG"`).
- Método de refinamiento de esquinas (`"CORNER_REFINE_SUBPIX"`).
- Path del archivo de geometría usado para extraer `rb_ids`.
- Timestamp absoluto del inicio de la captura (UTC ISO 8601).
- Hostname del equipo (para auditoría de qué máquina hizo qué captura).
- Hash SHA256 del config YAML usado.
- Hash SHA256 del archivo de calibración intrínseca usado.

Con esto, dado un `.npz` cualquiera, podemos reconstruir exactamente qué versión del software, qué hardware y qué config produjo ese dataset.

### 3.4 [ALTA] Cobertura por marker individual, no solo por par

Hoy reporta solo pares de markers vistos juntos. Útil pero incompleto. Mejor también:

```
[Cobertura por marker]
  ID 151: 1234 frames (78.5%)  OK
  ID 152: 982 frames (62.4%)   OK
  ...
  ID 159: 42 frames (2.7%)     WARN (< 100, geometria del BA tendra alta incertidumbre)
  ID 161: 0 frames (0.0%)      ERROR (no se detecto NUNCA, BA fallara)
```

Y mostrar **en tiempo real durante la captura** un widget tipo "barras" en el preview indicando qué markers se han visto cuántas veces, para guiar al usuario a rotar el dodecaedro buscando las caras infra-observadas.

### 3.5 [ALTA] Reemplazar `frames_data` por estructura tabular

Como expliqué en §2.5. Permite cargar sin `allow_pickle`, es más rápido, más portable, y deja el `.npz` legible para otras herramientas (Matlab, R, viewer estándar).

### 3.6 [MEDIA] Timeout en lectura de cámara

```python
while True:
    ret, frame = cap.read()
    if not ret:
        continue
```

Si `ret` siempre es `False` (cámara desconectada en medio de la captura), loop infinito. Propuesta: contar fallos consecutivos y abortar con mensaje si superan un umbral (ej. 30 fallos consecutivos = ~1 segundo a 30 FPS).

### 3.7 [MEDIA] Parametrizar magic numbers

- `>= 2` markers/frame para guardar → `--min-markers-per-frame` (default 2).
- `< 50` frames como warning → `--warning-threshold` (default 100, alineado con la guía de la comunidad de ≥ 40-100 frames útiles).
- Cuenta de frames de cobertura por marker para warning → `--min-frames-per-marker` (default 50).

### 3.8 [MEDIA] Logging estructurado

Reemplazar prints sueltos por `logging` module o al menos formato consistente:
- `[INFO]` para progreso normal.
- `[WARN]` para advertencias.
- `[ERROR]` para errores.
- `[STATS]` para reportes finales.

Más fácil de filtrar después con `grep`.

### 3.9 [BAJA] Refactor de código

- Separar imports stdlib/third-party.
- Usar `pathlib.Path` consistentemente para paths.
- Descomponer `main()` (165 líneas) en funciones más chicas: `_abrir_camara`, `_capturar_frames`, `_reportar_cobertura`, `_guardar_dataset`.
- Type hints opcionales pero ayudan.

### 3.10 [BAJA] Guardar snapshots de preview

Cada N frames (configurable), guardar la imagen con los markers dibujados a una subcarpeta `capturas_preview/` para revisión post-captura. Útil para debugging cuando el BA da RMSE alto.

### 3.11 [FUTURO] Comparativa SUBPIX vs APRILTAG

Hacer un experimento: capturar dos datasets de ~60s con la misma escena, uno con `SUBPIX` y otro con `APRILTAG`, correr BA en ambos, comparar RMSE. Si APRILTAG da consistentemente mejor RMSE, cambiar default. Si SUBPIX es comparable, dejarlo (más rápido). **Postergar a Fase 5 (mejoras post-auditoría).**

## 4. Tests propuestos

Suite pytest en `codigo/tests/test_captura_calibracion.py`:

- `test_validar_prerrequisitos_archivo_geom_inexistente`: pasa path inválido, debe `sys.exit` con mensaje claro.
- `test_validar_prerrequisitos_calibracion_inexistente`: idem.
- `test_validar_prerrequisitos_output_no_escribible`: idem.
- `test_carga_rb_ids`: dado un archivo de geometría conocido, devuelve el set de IDs correcto.
- `test_filtro_min_markers`: dado un frame mock con 0/1/2/3 markers detectados, decide correctamente si guardar.
- `test_filtro_solo_rigid_body`: dado un frame con markers del rigid body + uno externo, solo guarda los del rigid body.
- `test_formato_npz_compatible_con_calibrar_rigid_body`: genera un .npz sintético y verifica que tiene todas las keys que el script de Etapa D espera.

Tests de hardware (cámara real) quedan fuera de pytest porque requieren cámara conectada; pueden ir a un `test_smoke_captura.py` que se corre manualmente.

## 5. Operación paso a paso (para cuando llegue el momento de capturar)

**Naturaleza del script:** captura física con la cámara. Abre ventana de video, requiere interacción del usuario (rotar dodecaedro), 30-60 segundos de duración.

**Prerrequisitos físicos:**

1. Cámara montada y enfocada dentro de la caja de luz Puluz.
2. Dodecaedro armado con todos los 11 markers pegados (no falta ninguno).
3. Iluminación uniforme, sin reflejos brillantes sobre los markers.
4. **`data/reference_dodecaedro.txt` ya generado** (Etapa B completada) — el script lee los IDs de ahí.
5. **`data/camera_calibration_caja_luz.yml` presente** — calibración intrínseca de cámara (PLUS Toolkit en iter 1).

**Comando:**

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate
python captura_calibracion.py --duracion 60
```

**Qué vas a ver:**

1. Texto de instrucciones en consola (rotar lentamente, distancia 30-50 cm).
2. Countdown de 3 segundos.
3. **Se abre una ventana titulada "Captura calibracion - q para salir antes"** mostrando el video de la cámara en vivo.
4. En la ventana, los markers detectados aparecen marcados con cuadrados verdes y sus IDs.
5. Overlay de texto en la ventana:
   - `Frame {N} | {M} markers | Capturados: {K}`
   - `Tiempo: {t}s / 60s`
6. Cada ~5 segundos, en consola: `[Xs] N frames utiles capturados`.

**Qué hacer durante la captura:**

- Tomar el dodecaedro con la mano.
- Mantenerlo a **30-50 cm** de la cámara (no muy cerca, no muy lejos).
- **Rotarlo lentamente** mostrando todas las caras una por una, y combinaciones de caras.
- Variar orientación: inclinarlo, girarlo, mostrarlo desde distintos ángulos.
- Asegurarse de que la cara TOP (marker 151) se vea sola al menos algunas veces.
- Idem para cada cara de los cinturones — el objetivo es que cada marker se vea muchas veces y con muchos vecinos distintos.
- **No moverlo demasiado rápido**: el motion blur arruina detecciones y la precisión sub-pixel cae.

**Criterio de éxito:**

| Métrica | Mínimo aceptable | Bueno | Excelente (iter 1) |
|---|---|---|---|
| Frames útiles (≥ 2 markers) | 100 | 500 | ~1760 |
| Markers vistos en al menos 50 frames cada uno | 9 de 11 | 11 de 11 | 11 de 11 |
| Pares únicos observados | 30 | 50 | 60+ |

Al final, el script imprime:
```
[Captura terminada]
  Frames totales: NNNN
  Frames utiles (>=2 marcadores): MMMM

[Pares de marcadores observados juntos]
  Total pares unicos: XX
  Mas frecuente: (id_a, id_b) (N frames)
  Menos frecuente: (id_x, id_y) (M frames)

[Guardado] capturas_calibracion.npz
```

Si `Frames utiles < 50`, hay warning y conviene **repetir la captura**.

**Qué hacer si falla:**

- "ERROR: no se pudo abrir la camara" → cámara no conectada, otro programa la tiene tomada, o backend equivocado.
- Ventana abierta pero frame negro → exposición/ganancia mal, o la cámara no aceptó la resolución (verificar resolución real reportada).
- Detecta 0 markers todo el tiempo → diccionario equivocado en config (verificar `DICT_ARUCO_MIP_36h12`).
- Detecta markers pero ninguno del rigid body → IDs equivocados en `reference_dodecaedro.txt` o config inconsistente con el cubo físico.

**Después de la captura:**

```powershell
# Verificar que el archivo se generó
Get-ChildItem capturas_calibracion.npz

# Inspección rápida del contenido (cuántos frames quedaron)
python -c "import numpy as np; d = np.load('capturas_calibracion.npz', allow_pickle=True); print(f'frames: {len(d[\"frames_data\"])}'); print(f'rb_ids: {d[\"rb_ids\"]}')"
```

## 6. Aplicación de mejoras (2026-05-16, segunda pasada)

Aplicadas las **8 mejoras de alta + media prioridad** (§3.1–§3.8). Quedaron postergadas las de baja (refactor cosmético, snapshots preview) y el experimento APRILTAG (Fase 5).

### Cambios concretos en `captura_calibracion.py`

El script pasó de 197 líneas a 538, totalmente reescrito en módulos:

- **`validar_prerrequisitos`** verifica antes del countdown: archivo de calibración existe y tiene K/dist, archivos de geometría existen, output_path es escribible. Si falla, mensaje claro y `sys.exit(1)` **antes** de capturar.
- **`abrir_camara`** reporta y guarda los valores reales (resolución, FPS, FOURCC) después de `cap.set(...)`. Advierte si difieren de lo solicitado — crítico para detectar configuraciones de cámara que la calibración intrínseca no soporta.
- **Metadata extensiva** guardada en `metadata_json` como YAML serializado: versión OpenCV, NumPy, Python, plataforma, hostname, timestamp UTC, hashes SHA256 del config/calibración/geometría, settings reales de cámara, parámetros del detector, IDs del rigid body, configuración de la corrida.
- **`actualizar_cobertura` + `reportar_cobertura`** computan cuántas veces se vio cada marker individual. Reporta PASS/WARN/ERROR al final. **Widget en tiempo real** en la ventana de preview: lista a la derecha con `ID N: K` en color rojo si N=0, amarillo si N<threshold, verde si N≥threshold.
- **`frames_a_tabular`** convierte `frames_data` a estructura tabular (arrays separados `timestamps`, `frame_offsets`, `marker_ids`, `corners_2d`). Guardada como keys adicionales del `.npz`, legibles sin `allow_pickle`. Formato futuro-compatible.
- **Timeout de cámara**: contador de `fallos_consecutivos`, aborta si supera `--camera-fail-timeout` (default 30 frames).
- **CLI parametrizada**: `--duracion`, `--min-markers-per-frame`, `--warning-threshold`, `--min-frames-per-marker`, `--camera-fail-timeout`, `--output`, `--config`.
- **Logging estructurado**: helpers `log_info`, `log_warn`, `log_error`, `log_stats` con prefijos `[INFO]`/`[WARN]`/etc.
- **Retrocompatibilidad TOTAL**: el `.npz` nuevo sigue conteniendo `frames_data` (object array de dicts) + `K`, `dist`, `rb_ids` exactamente como antes. La Etapa D (`calibrar_rigid_body.py`) lo lee sin cambios. Lo nuevo son keys adicionales.

### Tests en `codigo/tests/test_captura_calibracion.py`

25 tests, todos pasan en 0.5s. Cubren:

- `cargar_rb_ids` con archivos reales y sintéticos, incluyendo edge cases (comentarios, líneas vacías).
- `cargar_calibracion`: devuelve K, dist correctos; error claro si el archivo no existe.
- `filtrar_detecciones`: pasa los del rigid body, ignora externos, maneja `ids=None`.
- `actualizar_cobertura` y `reportar_cobertura`: comportamiento por marker, clasificación PASS/WARN/ERROR.
- `frames_a_tabular`: estructura correcta y caso vacío.
- `validar_prerrequisitos`: pasa con archivos válidos, aborta con calibración/geometría/rigid_bodies faltantes.
- `hash_sha256`: estable e inyectivo.
- `fourcc_int_a_str`: round-trip de MJPG, YUY2.
- `construir_metadata`: contiene todas las keys esperadas.
- **`guardar_dataset_retrocompatible`**: el `.npz` nuevo tiene `frames_data`/`K`/`dist`/`rb_ids` con el mismo formato que esperaba Etapa D.
- `guardar_dataset_incluye_tabular`: arrays tabulares legibles sin `allow_pickle`.
- `guardar_dataset_metadata_legible`: la metadata YAML se carga y deserializa bien.

### Validación final

| Validación | Resultado |
|---|---|
| `pytest tests/` (suite completa proyecto) | **54/54 PASS** en 0.5 s |
| Sintaxis (`py_compile`) | OK |
| Retrocompatibilidad con Etapa D | OK (test específico) |
| .npz tabular legible sin `allow_pickle` | OK |

### Mejoras NO aplicadas (deuda diferida)

- §3.9 Refactor de código (`pathlib`, type hints, descomponer `main`) — cosmético.
- §3.10 Snapshots de preview cada N frames — nice-to-have.
- §3.11 Experimento APRILTAG vs SUBPIX — Fase 5 (requiere capturar dos veces y comparar RMSE del BA).

---

**Etapa C: CERRADA EN CÓDIGO.** Script auditado, mejorado, parametrizado, con suite de tests. Falta solo la captura física en tu Windows.

## 7. Próximo paso: ejecutar la captura

Cuando estés listo, seguí los pasos de §5 de este documento. Una vez tengas `capturas_calibracion.npz` con ≥ 100 frames útiles y cobertura razonable (todos los markers con ≥ 50 frames cada uno idealmente), pasamos a **Etapa D — `calibrar_rigid_body.py`** (bundle adjustment).
