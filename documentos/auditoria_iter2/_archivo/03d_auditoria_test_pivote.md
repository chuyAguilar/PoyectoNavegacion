# 03d — Auditoría de `test_pivote.py`

**Fase 3 de la auditoría de iteración 2 · Script de Etapa E (calibración de pivote).** Fecha: 2026-05-20.

## Resumen ejecutivo

- ✅ **Matemática correcta**: el método de la esfera + RANSAC + transformación al frame del dodecaedro es **matemáticamente equivalente** a la formulación AX=b clásica de PlusServer / Yaniv 2015.
- ✅ **Validado cuantitativamente con datos sintéticos** (2026-05-20): recupera offset con **0.27 mm de error** contra GT, con 10% outliers + ruido típico (σ_t=0.3 mm, σ_R=0.15°).
- ✅ **APIs verificadas con Context7**: `cv2.solvePnP(IPPE_SQUARE)` y `cv2.solvePnP(ITERATIVE)+solvePnPRefineLM` usadas correctamente. Filtro `N≥2 markers` evita ambigüedad planar.
- ⚠️ **STD reportada es pesimista**: la dispersión entre `tip_d` (típica 1-2 mm) **NO es estimación del error absoluto** (que es ~10× menor). Documentar esto en los criterios de aceptación.
- 📋 **Mejoras propuestas** (no bloquean uso): verbose=2, validación de prerrequisitos, metadata extensiva, generación automática del `.h5`, extraer código común con `tracker.py` a módulo.

**Veredicto**: el script está **listo para producción**. La auditoría matemática inicial (en `01_mapa_del_flujo.md` §6 punto 1) lo marcaba como "pieza con menos certeza" — la auditoría detallada y la validación sintética **descartan ese riesgo**.

---

## 1. Descripción del script

**Entrada:**
- `tracker_config.yaml` (config de cámara + ruta a calibración intrínseca + ruta a geometría calibrada).
- `--duracion 45` segundos por defecto.
- Físicamente: punta del stylus clavada en un cartón con orificio, movimiento de cono manteniendo punta fija.

**Pipeline:**
1. Carga `K`, `dist`, diccionario ArUco, geometría calibrada del dodecaedro.
2. Abre cámara (MSMF + MJPG + 640x480 + 30 FPS).
3. Loop de captura por `duracion` segundos:
   - Detecta ArUco con `cv2.aruco.ArucoDetector` (API nueva) + `CORNER_REFINE_SUBPIX`.
   - Filtra IDs por los del rigid body.
   - Si `len(detecciones) ≥ 2`: estima pose multi-marker con `SOLVEPNP_ITERATIVE + RefineLM`.
   - Acumula `poses[N, 4, 4]`.
4. Guarda poses como `.npy`.
5. RANSAC (1000 iter, sample_size=20, umbral=1.5 mm) → set de inliers.
6. Re-ajuste de esfera sobre todos los inliers → `centro_pivot`, `radio`, `rmse`.
7. Para cada pose inlier: `tip_d = pose_inv @ [centro_pivot, 1]`.
8. `offset = mean(tip_d)`, `std = std(tip_d)`.
9. Guarda `StylusTipToDodecaedro.npy` y `.txt` (matriz 4×4 con rotación identidad + traslación = offset).

**Salida:**
- `poses_pivote_dodecaedro.npy` — array (N, 4, 4) de poses crudas.
- `StylusTipToDodecaedro.npy` — matriz 4×4 final.
- `StylusTipToDodecaedro.txt` — matriz + metadata (offset, std, RMSE).
- **`.h5` NO se genera** (requiere paso manual en Slicer).

---

## 2. Auditoría matemática (paso por paso)

### Setup físico

Durante la captura:
- La **punta** (tip) está clavada en un cartón → fija en el espacio.
- La **cámara** está estática.
- El **stylus** rota alrededor de la punta (el dodecaedro hace de "cono").

Consecuencias:
- `tip_camara` = constante (porque la punta y la cámara están fijas).
- `tip_dodecaedro` = constante (porque la punta está rígidamente unida al stylus).
- El **centro del dodecaedro** (`pose[:3, 3]` = `t_i`) está siempre a distancia `r = ||tip − centro|| ` de la punta. Por lo tanto, traza una **esfera** centrada en la punta con radio `r`.

### Paso 1 — Pose multi-marker (✓ correcto)

Para `N≥2` markers, el script concatena todos los puntos 3D del rigid body y sus correspondientes 2D, y resuelve un PnP único:

```python
ok, rvec, tvec = cv2.solvePnP(all_obj, all_img, K, dist,
                              flags=cv2.SOLVEPNP_ITERATIVE)
rvec, tvec = cv2.solvePnPRefineLM(all_obj, all_img, K, dist, rvec, tvec)
```

- `SOLVEPNP_ITERATIVE` arranca con DLT/EPnP interno y refina por LM.
- `solvePnPRefineLM` hace un segundo pase LM con criterio default (`EPS+COUNT, 20, FLT_EPSILON`).
- El filtro `N≥2` evita la **ambigüedad planar** de IPPE_SQUARE (cuando solo se ve 1 marker en plano).

### Paso 2 — Ajuste a esfera (✓ correcto)

`ajustar_esfera` ajusta 4 parámetros `(cx, cy, cz, r)` minimizando:

```
residuos_i = ||puntos_i - centro|| - r
```

con `scipy.optimize.least_squares` (TRF + linear loss). Inicialización: centroide + radio promedio. Esto es el patrón canónico de **sphere fitting**.

### Paso 3 — RANSAC (✓ correcto)

```python
for i in range(1000):
    sample = random.choice(N, 20)
    centro, radio = ajustar_esfera(posiciones[sample])
    inliers = |distancias - radio| < 1.5 mm
    if len(inliers) > len(mejor_inliers):
        mejor_inliers = inliers
```

- `seed=42` → reproducible.
- Patrón estándar de RANSAC robusto a outliers.
- Después del loop: re-ajuste de esfera sobre TODOS los inliers (no solo el sample).

### Paso 4 — Transformación al frame del dodecaedro (✓ correcto)

```python
for pose in poses[inliers]:
    tip_h = [centro_pivot_x, centro_pivot_y, centro_pivot_z, 1.0]
    tip_d = (np.linalg.inv(pose) @ tip_h)[:3]
    tips_d.append(tip_d)
offset = mean(tips_d)
std = std(tips_d)
```

Razonamiento:
- `pose_i = DodecaedroToCamera` lleva puntos del frame dodecaedro al frame cámara.
- `pose_i^(-1) = CameraToDodecaedro` lleva del frame cámara al frame dodecaedro.
- `centro_pivot` está en frame cámara (porque salió del ajuste de esfera sobre `t_i`, que están en frame cámara).
- Por lo tanto `pose_i^(-1) @ centro_pivot` da el tip en frame dodecaedro.

En el caso ideal sin ruido, ese resultado sería el mismo para todas las poses. Con ruido, varía y `offset = mean(tip_d)` es el estimador ML bajo ruido gaussiano.

---

## 3. Comparación con la formulación AX=b clásica (Yaniv 2015 / PlusServer)

El método AX=b plantea directamente las dos incógnitas (tip en cámara y tip en dodecaedro) como sistema lineal:

Para cada pose:
```
R_i · t_dod + t_i_translation = tip_camara  (constante)
```

Reordenado:
```
[R_i, -I] · [t_dod; tip_cam] = -t_i_translation
```

Apilando todas las poses:
```
A · x = b   con A ∈ R^(3N × 6), x = [t_dod; tip_cam] ∈ R^6
```

Resolver con `np.linalg.lstsq`.

### Comparación de los dos métodos

| Aspecto | Esfera + transform (script) | AX=b (clásico) |
|---|---|---|
| Estimación conjunta | No (dos pasos) | Sí |
| No-linealidad | LS no-lineal (4D) | Lineal (6D) |
| Manejo de outliers | RANSAC integrado | Necesita RANSAC externo |
| Sensibilidad a inicialización | Baja (centroide) | Ninguna (lineal cerrado) |
| Precisión en datos sintéticos | 0.27 mm error | 0.21 mm error |

Diferencia despreciable (~0.06 mm). El **RANSAC del método de esfera es una ventaja real** porque los outliers en pivot calibration son comunes (poses mal estimadas durante transiciones rápidas).

### Validación con datos sintéticos (2026-05-20)

Test ejecutado con N=300 poses sintéticas, 10% outliers, ruido σ_t=0.3 mm, σ_R=0.15°:

```
Ground truth:
  tip_camara: [100.0, 50.0, 600.0] mm
  offset GT:  [0.31, -0.26, -88.62] mm
  magnitud:   88.62 mm

Método de la esfera (script):
  RANSAC inliers: 271/300 (90.3%)  ← outliers correctamente detectados
  centro_pivot:   [99.94, 50.00, 600.13] mm  (error 0.15 mm)
  offset:         [0.43, -0.38, -88.42] mm   (error 0.27 mm)
  magnitud:       88.42 mm                    (error 0.20 mm)
  std reportada:  [1.86, 2.70, 1.11] mm     ← pesimista vs error real (0.27 mm)

Método AX=b clásico:
  offset:         [0.43, -0.39, -88.72] mm   (error 0.21 mm)
  tip_camara:     [100.16, 49.85, 599.80] mm (error 0.30 mm)
```

**Ambos métodos recuperan el ground truth con <0.3 mm de error.** La auditoría está cuantitativamente cerrada.

---

## 4. Auditoría de APIs (verificado con Context7 / docs.opencv.org/4.x)

| API | Uso en script | Verificación |
|---|---|---|
| `cv2.solvePnP(SOLVEPNP_ITERATIVE)` | N≥2 markers, sin `useExtrinsicGuess` | ✓ Correcto. LM desde solución DLT inicial. Sin guess → más robusto frame-a-frame en pivote con rotaciones grandes. |
| `cv2.solvePnP(SOLVEPNP_IPPE_SQUARE)` | N=1 marker (4 esquinas, plano) | ✓ Correcto. Requiere exactamente 4 puntos en orden TL, TR, BR, BL (lo que devuelve ArUco). |
| `cv2.solvePnPRefineLM` | Post-iterative, multi-marker | ✓ Default `TermCriteria(EPS+COUNT, 20, FLT_EPSILON)` razonable. |
| `cv2.aruco.ArucoDetector` (API nueva) + `CORNER_REFINE_SUBPIX` | Detección | ✓ API nueva (OpenCV ≥4.7). Fallback a API antigua si no disponible. |
| `scipy.optimize.least_squares` | Sphere fitting, 4 params | ✓ TRF default, sin loss especial (linear). Patrón canónico. |

Sin red flags. Las APIs se usan según docs.

---

## 5. Hallazgos

### ✅ Fortalezas
1. Matemática correcta y validada cuantitativamente.
2. RANSAC integrado robusto a outliers.
3. Filtro N≥2 evita ambigüedad planar de IPPE single.
4. Configuración de cámara (MSMF + MJPG) coherente con iter 1 (30 FPS).
5. Salida estructurada (.npy binario + .txt con metadata legible).

### ⚠️ Puntos de atención (no bloquean uso)

1. **STD reportada es pesimista**. La métrica `std(tip_d)` mide DISPERSIÓN, no SESGO. En el test sintético, std=2 mm pero error real=0.27 mm. Es válido como red flag (alta std = problemas en captura) pero NO debe interpretarse como precisión absoluta. **Acción**: documentar esto en los logs del script.

2. **Código duplicado con `tracker.py`**. Las funciones `cargar_calibracion`, `cargar_rigid_body`, `estimar_pose_rigid_body`, `rvec_tvec_a_matriz` están copiadas. Riesgo de divergencia. **Acción**: extraer a `dodecaedro_core.py` o similar.

3. **El `.h5` se genera manual en Slicer**. Riesgo: si se omite o se carga la matriz equivocada, falla silenciosamente. **Acción**: automatizar con `h5py` + formato Slicer Linear Transform.

4. **`scipy.optimize.least_squares` sin verbose**. Cuando el sphere fit toma >1 seg (datasets grandes), el usuario no ve progreso. **Acción**: agregar `verbose=2` en `ajustar_esfera` (la regla `feedback_verbose_iter_por_iter.md` aplica acá).

5. **Sin validación de prerrequisitos**. Si falta el archivo de calibración o el `reference_dodecaedro_calibrado.txt`, el script falla con stack trace feo en vez de mensaje claro. **Acción**: agregar `validar_prerrequisitos()` como en `calibrar_rigid_body.py`.

6. **Sin metadata extensiva en `.txt`**. Falta: versiones (OpenCV, SciPy, Python), SHA256 del input, hostname, fecha. **Acción**: estandarizar con `calibrar_rigid_body.py`.

7. **Std `EXCELENTE/BUENO/REGULAR/INSUFICIENTE` thresholds**. Útiles como guía pero deberían documentar la advertencia del punto #1 (std ≠ error absoluto).

8. **El offset asume rotación identidad**. Esto es **correcto** si "StylusTip" se interpreta como un PUNTO (consistente con Slicer + MarkupsFiducial en (0,0,0)). Si en el futuro se quisiera un frame con orientación del stylus, habría que cambiar el modelo.

### ❌ Problemas reales encontrados

**Ninguno.** El script funciona correctamente. Los puntos de atención son mejoras de calidad de vida.

---

## 6. Mejoras propuestas (priorizadas)

### Alta prioridad (recomendado antes de uso en producción)

- **M1**: Validación de prerrequisitos al arrancar (existencia de archivos, permisos de escritura, formato del config).
- **M2**: Metadata extensiva en `StylusTipToDodecaedro.txt` (versiones, hashes, hostname, fecha) similar a `calibrar_rigid_body.py`.
- **M3**: Mensaje aclaratorio sobre std vs error absoluto en la sección EVALUACION.

### Media prioridad (limpieza)

- **M4**: Extraer código común con `tracker.py` a `dodecaedro_core.py`.
- **M5**: `verbose=2` en `ajustar_esfera` y print cada 100 iter del RANSAC (regla del proyecto).
- **M6**: Generar el `.h5` automáticamente desde Python (h5py + formato Slicer).

### Baja prioridad (futuro)

- **M7**: Implementar AX=b como alternativa para validación cruzada (`--method ax-b` flag).
- **M8**: Robustez extra al sphere fit usando Huber loss en lugar de RANSAC (para validar).
- **M9**: Suite de tests pytest con datos sintéticos (ya validado, falta automatizar).

---

## 7. Comando recomendado y métricas esperadas

### Setup físico

1. Clavá la punta del tornillo en un cartón con orificio (sobre la mesa).
2. El dodecaedro tiene que estar visible para la cámara durante todo el movimiento.
3. Pivotes amplios (cono ~30° de apertura), suaves, variando azimut.

### Comando

```powershell
python test_pivote.py --duracion 45
```

### Output esperado durante captura

```
[Calibracion intrinseca cargada]
[Rigid body cargado] 11 marcadores: [151, 152, ..., 161]
...
CAPTURANDO!
  [5s] 145 poses capturadas
  [10s] 295 poses capturadas
  ...
[Captura terminada]
  Total poses: ~1200
  Marcadores promedio por pose: ~3.5
```

### Output esperado post-procesamiento

```
Inliers: ~1080/~1200 (~90%)

Ajuste a esfera:
  Centro pivot: en frame camara (aprox donde clavaste la punta)
  Radio: ~88 mm
  RMSE: <1 mm

Offset del tip (en frame dodecaedro):
  Promedio: ~88 mm de magnitud (distribución entre X/Y/Z depende de la
            rotación del calibrado por gauge ambiguity del BA — ver §6 del
            mapa de flujo)
  STD: <2 mm por eje (objetivo iter 2)
  Magnitud: 88 ± 1 mm

[EXCELENTE] o [BUENO]
```

### Criterios de aceptación

| Métrica | Excelente | Aceptable | Inaceptable |
|---|---|---|---|
| Total poses capturadas | >500 | >100 | <50 |
| % inliers RANSAC | >85% | >70% | <50% |
| RMSE esfera | <0.5 mm | <1 mm | >2 mm |
| STD offset por eje | <1 mm | <2 mm | >5 mm |
| Magnitud offset | 85-92 mm | 80-95 mm | <70 o >100 mm |

**Importante**: la `STD` es pesimista (mide dispersión, no sesgo). En el test sintético, std=2 mm correspondía a error real de 0.27 mm. Si la std queda <2 mm el calibrado es bueno; si pasa de 5 mm investigar (probablemente captura corta o pivoteo poco variado).

### Próximo paso

Cargar `StylusTipToDodecaedro.npy` en 3D Slicer como Linear Transform y guardarlo como `.h5` (paso manual). Después continuar con Etapa F (tracker.py) → Etapa H (registro paired-point).

---

## 8. Estado de la auditoría

**Etapa E queda CERRADA** con esta auditoría. Las mejoras propuestas (§6) no bloquean uso en producción — son polish/mantenibilidad.

Pendientes que SI bloquearían (ninguno actual):
- Si la validación con datos reales (post-corrida en Windows) muestra std >5 mm consistente → reabrir auditoría.
- Si Slicer rechaza el `.h5` por formato → automatizar generación.

Avanza siguiente: **Etapa F (`tracker.py`)**.
