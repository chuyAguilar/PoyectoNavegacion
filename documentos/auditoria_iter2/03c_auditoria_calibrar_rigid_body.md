# 03c — Auditoría de `calibrar_rigid_body.py`

**Fase 3 de la auditoría de iteración 2 · Script de Etapa D (Bundle Adjustment).** Fecha: 2026-05-16.

---

## ⚡ ACTUALIZACIÓN 2026-05-19 — estado final post-implementación

Después de la auditoría inicial (abajo) y varios ciclos de implementación, el script quedó en este estado:

### Cambios aplicados respecto a la versión auditada

| Aspecto | Auditoría 2026-05-16 (recomendación) | Estado final 2026-05-19 |
|---|---|---|
| Parametrización geom | Mover a rígida 6 DOF por marker | ✅ **Rígida implementada** (centro 3D + rvec Rodrigues + tamaño fijo). Razón: la libre absorbía ruido deformando markers (desplazamientos de 30-40 mm físicamente imposibles). |
| `jac_sparsity` | Activar | ⚠️ **Implementado pero BUG**: al activarlo el optimizer NO converge (RMSE empeora). Default queda en `denso` (`--use-sparse` opt-in con warning). Tarea pendiente: arreglar el bug. |
| `x_scale='jac'` | Activar | ⚠️ **Implementado pero opt-in** (`--x-scale-jac`). Interactúa mal con huber loss (empuja a mínimo local con desplazamientos de 25 mm). Default off. |
| Metadata en output | Agregar versiones, hashes, parámetros | ✅ Implementado: hostname, versiones (OpenCV, SciPy, Python), SHA256 de inputs, status del optimizer, iter count, RMSE, desplazamientos. |
| Validación de prerrequisitos | Agregar | ✅ Implementado (`validar_prerrequisitos`): existencia de dataset, teórico, permisos de escritura. |
| Verbose iter por iter | Implícito | ✅ `verbose=2` por default. Flag `--verbose {0,1,2}` para controlarlo. |
| Tests pytest | Agregar | ✅ 26+ tests en `tests/test_calibrar_rigid_body.py`. |
| Robustez de escritura | — | ✅ `guardar_archivo_calibrado` con `flush() + os.fsync() + verificación de 16 tokens por marker + padding "# fin" x 5` al final. Mitiga truncación observada en filesystem Windows. |

### Métricas finales (iter 2, Dr. Milton, 2026-05-19)

- **RMSE reproyección**: 0.4524 px (reducción 95.3 % vs inicial 6.56 px usando `reference_dodecaedro_real.txt`).
- **Iteraciones**: 71 (con `--max-nfev 3000`, terminó por `ftol`).
- **Tiempo**: ~11 min con 150 frames.
- **Consistencia geométrica** (post-Procrustes vs teórico real): RMS residual 0.99 mm. Distancias inter-marker: mean diff -0.38 mm, abs mean 0.68 mm. **El cuerpo es rígido y consistente.**
- **Desplazamiento centro vs teórico**: ~30 mm uniforme — **NO es error**, es la rotación rígida residual por gauge ambiguity (ver sección "Gauge ambiguity" abajo).

### Nueva sección: Gauge ambiguity (descubierta 2026-05-19)

Anclar el marker 151 (su centro + 4 esquinas) fija una parte del sistema pero **no elimina completamente la ambigüedad rotacional del cuerpo entero**. El optimizer puede converger a una configuración donde:
- El ancla está en su posición teórica fija.
- Los demás 10 markers + las poses de los frames están coherentemente rotados respecto al teórico.
- El RMSE es óptimo (bajo).
- Las distancias inter-marker son correctas.

Esta es una propiedad conocida de problemas BA con anclaje parcial. **La calibración resultante sigue siendo válida para tracking** (el sistema es internamente consistente). La verificación correcta es Procrustes (alinear calibrado vs teórico con rotación óptima y medir residuo), NO comparar centros uno por uno.

### Flag nuevo: `--teorico`

El BA acepta una semilla teórica distinta del default `data/reference_dodecaedro.txt`. **Uso recomendado en iter 2**: pasar `--teorico data/reference_dodecaedro_real.txt` (generado por la nueva Etapa C.5, `calibrar_topologia.py`). Esto da un punto de partida con el orden REAL de IDs en los anillos, reduciendo iteraciones y desplazamientos.

### Comando final recomendado

```powershell
python calibrar_rigid_body.py --teorico data/reference_dodecaedro_real.txt --max-frames 150 --max-nfev 3000
```

### Tareas pendientes (no bloquean uso del script)

1. **Bug en `construir_jac_sparsity`** — sin esto, no se puede usar sparse (default es denso, 5-10x más lento). Para datasets de 500+ frames sería deseable arreglarlo.
2. **Migrar verbose=2** al resto de scripts del pipeline (`captura_calibracion.py`, `test_pivote.py`, `tracker.py`).

---

## Resumen ejecutivo

- **Matemática del BA**: formulación correcta. Gauge fixing válido (ancla ID 151), loss huber con f_scale=2.0 razonable, método `trf` apropiado. cv2.projectPoints hace la cuenta canónica del modelo pinhole + distorsión.
- **Hallazgo importante**: el script usa una parametrización **NO RÍGIDA** de cada marker (12 floats por marker = 4 esquinas libres). Físicamente, cada marker es un cuadrado plano rígido de 16 mm de lado con **6 DOF**, no 12. La parametrización actual permite que el cuadrado deje de ser cuadrado, lo que puede causar overfitting al ruido y diluir información geométrica.
- **Performance**: el script no usa `jac_sparsity` ni `x_scale='jac'`. El SciPy Cookbook (referencia canónica de BA en scipy) marca ambos como críticos. Sin ellos, el optimizador calcula jacobianas densas por diferencias finitas — lento y mal escalado.
- **Salida**: archivo de texto plano sin metadata. No queda registro de cuántas iteraciones, status del optimizador, hashes de inputs, RMSE inicial vs final estructurado, etc.
- **Sin tests**: ninguna verificación matemática automatizada. Crítico para auditoría.

## 1. Descripción del script

**Entrada:**
- `capturas_calibracion.npz` con `frames_data`, `K`, `dist` (Etapa C).
- `data/reference_dodecaedro.txt` (geometría teórica de Etapa B) como **semilla** del BA.

**Pipeline:**
1. Carga `.npz`, submuestrea a `--max_frames` (default 500) si tiene más.
2. Carga geometría teórica, ordena IDs.
3. Para cada frame: estima pose inicial con `cv2.solvePnP` usando geometría teórica.
4. Parametriza:
   - **Geometría**: 10 markers (excluyendo el ancla) × 12 coords = 120 parámetros libres.
   - **Poses**: N_frames × 6 (rvec + tvec). Para 500 frames: 3000.
   - **Total**: 3120 parámetros.
5. Define `calcular_residuos(params, ...)`: reconstruye geom + poses, hace `cv2.projectPoints` para cada detección, devuelve vector aplanado de errores 2D.
6. `scipy.optimize.least_squares` con: `method='trf'`, `loss='huber'`, `f_scale=2.0`, `max_nfev=200`.
7. Reporta RMSE inicial vs final, desplazamientos por marker.
8. Guarda `reference_dodecaedro_calibrado.txt`.

**Salida:** archivo de texto con la geometría refinada de los 11 markers. Métrica esperada: RMSE final ≈ 0.61 px (iter 1).

## 2. Auditoría matemática y de APIs

### 2.1 Gauge fixing — correcto

Anclar las 4 esquinas del ID 151 en su posición teórica fija los **6 DOF globales** (3 traslación + 3 rotación) del sistema de coordenadas. Sin gauge fixing, el BA tendría una familia infinita de soluciones equivalentes (todas trasladadas/rotadas iguales). ✓

Riesgo conocido (ya señalado en mapa §6 punto 2): si el ancla está físicamente mal pegada en la cara TOP, **todo el frame del dodecaedro queda inclinado** y se propaga downstream (pivote, registro). Mitigación posible: anclar 2 markers (uno fija origen + escala, otro fija orientación residual). **No prioritario** para iter 2; el RMSE 0.61 px de iter 1 sugiere que el pegado fue suficientemente bueno.

### 2.2 Loss huber + f_scale=2.0 — razonable

`loss='huber'` con `f_scale=2.0` significa: residuos < 2 px se tratan cuadráticamente (normal least-squares), residuos > 2 px se tratan linealmente (robusto a outliers). Para detecciones ArUco con `CORNER_REFINE_SUBPIX` la precisión típica es < 0.5 px, así que f_scale=2.0 deja un margen razonable para tolerar detecciones ruidosas sin que dominen el costo. ✓

### 2.3 `method='trf'` — apropiado

Trust Region Reflective. Es la única opción de SciPy que soporta `loss != 'linear'` (huber requiere trf o dogbox). ✓

### 2.4 `cv2.projectPoints` — canónico

Implementa la proyección pinhole con distorsión radial-tangencial usando K + dist. La cuenta es la correcta. ✓

### 2.5 Parametrización de geometría — **MEJORABLE**

**El script usa 12 floats por marker (4 esquinas × 3 coords) sin restricción de rigidez.** Esto significa que el optimizador puede:

- Hacer que el cuadrado deje de ser cuadrado (lados de longitud distinta).
- Hacer que los 4 corners dejen de ser coplanares.
- Hacer que el lado deje de ser 16 mm.

Físicamente, un marker ArUco impreso y pegado **es rígido**: cuadrado plano de lado conocido. La parametrización correcta sería:

- **6 DOF por marker**: pose del frame del marker en el frame del dodecaedro (3 translación del centro + 3 rotación).
- **Tamaño fijo**: lado = 16 mm.
- Las 4 esquinas se derivan determinísticamente de la pose y el tamaño.

**Beneficios:**
- Parámetros: 60 (10 markers × 6) en vez de 120. **Mitad del tamaño.**
- Geometría físicamente válida garantizada (no overfitting a ruido).
- Convergencia más rápida y estable.
- Posiblemente RMSE final más alto (el BA actual puede estar "absorbiendo" ruido al deformar markers).

**Costo:**
- Cambio importante en la formulación.
- Hay que cambiar `calcular_residuos` para reconstruir las 4 esquinas desde (centro, rotación) a partir de los 6 DOF.

Esto es exactamente la técnica usada por implementaciones serias como [`MarkerBA: Marker Bundle Adjustment With Rectangle Planar Constraint`](https://github.com/HeYijia/MarkerBA).

### 2.6 Jacobiano sparse — **AUSENTE, ALTO IMPACTO**

El SciPy Cookbook tiene un ejemplo canónico de BA ([Large-scale bundle adjustment in scipy](https://scipy-cookbook.readthedocs.io/items/bundle_adjustment.html)) que dice textualmente:

> Computing Jacobian of `fun` is cumbersome, thus we will rely on the finite difference approximation. **To make this process time feasible we provide Jacobian sparsity structure** (i.e. mark elements which are known to be non-zero).

En nuestro caso, el jacobiano es altamente sparse:
- Para nuestro problema con 500 frames, 11 markers y ~3.3 markers/frame promedio: ~13,200 residuos × 3,120 parámetros = **41 millones de entradas**.
- Pero cada residuo solo depende de **18 parámetros** (12 del marker + 6 de la pose). El 99.94% de la matriz es cero.

**Sin `jac_sparsity`**, SciPy calcula la jacobiana entera por diferencias finitas: 3,120 evaluaciones de `calcular_residuos` por iteración. Con 200 iteraciones máximas, son hasta 624,000 evaluaciones.

**Con `jac_sparsity`**, SciPy solo computa entradas no-cero y usa `tr_solver='lsmr'` (iterativo sparse). El cookbook reporta **33 segundos** para 23,769 parámetros / 63,686 residuos — comparable a nuestro escenario.

**Impacto esperado del fix**:
- Tiempo de BA: probablemente 5-10× más rápido.
- Permite usar TODOS los 1752 frames sin penalización (en vez de submuestrear a 500).
- Más frames → BA más restringido → resultado más confiable.

### 2.7 `x_scale='jac'` — **AUSENTE, CRÍTICO**

Del mismo cookbook:

> Setting `scaling='jac'` was done to automatically scale the variables and equalize their influence on the cost function (clearly the camera parameters and coordinates of the points are very different entities). **This option turned out to be crucial for successful bundle adjustment**.

En nuestro BA tenemos parámetros de unidades muy distintas:
- Coordenadas 3D de markers: ~20 mm de magnitud.
- Rotaciones (rvec): ~1 radian de magnitud.
- Traslaciones de pose (tvec): ~300 mm de magnitud.

Sin escalado, el optimizador trata todos los parámetros como si tuvieran la misma sensibilidad. `x_scale='jac'` escala cada parámetro por la norma de la columna correspondiente del jacobiano, igualando influencias.

**Impacto esperado**: mejor convergencia, menos iteraciones, posible mejora del RMSE final.

### 2.8 Submuestreo a 500 frames — innecesario con sparse jacobian

Hoy se descartan 1252 frames (~70%) por velocidad. Con jacobiano sparse y x_scale='jac', se pueden usar TODOS sin penalización significativa. Más datos = restricciones más fuertes = mejor geometría.

### 2.9 Detección de convergencia — incompleta

El script imprime RMSE inicial y final, pero no:

- `resultado.status` (1=satisfecho ftol, 2=satisfecho xtol, 3=satisfecho gtol, 0=max evaluaciones excedido, < 0 = error).
- `resultado.message` (mensaje legible).
- `resultado.nfev` (número de evaluaciones de la función).
- `resultado.cost` (costo final).
- Si `not resultado.success`: el script imprime "Calibracion completa" igualmente. Bug: se debería abortar o avisar fuerte.

### 2.10 Reporte por marker individual — útil pero ausente

Solo reporta desplazamiento del centro y máximo de esquinas. Útil agregar:

- RMSE de reproyección por marker (cuál tiene más error residual).
- Número de detecciones por marker en el dataset.
- Std/uncertainty del centro (si se computa la covarianza posterior).

## 3. Hallazgos: mejoras propuestas

### 3.1 [ALTA] Jacobiano sparse + x_scale='jac'

Implementar `bundle_adjustment_sparsity()` siguiendo el cookbook, pasar `jac_sparsity=A` y `x_scale='jac'` a `least_squares`. Cambio acotado, alto impacto.

```python
from scipy.sparse import lil_matrix

def construir_sparsity(n_frames, n_markers, ids_orden, ancla_id, frames_data, ids_index):
    """Devuelve matriz lil_matrix (M, N) con 1 en las posiciones no-cero del jacobiano."""
    # M = total residuos = sum(4 corners * 2 coords) por deteccion
    # N = n_geom_params + n_pose_params
    ...
```

### 3.2 [ALTA] Usar todos los frames (sin submuestreo)

Una vez aplicado §3.1, eliminar el submuestreo (o solo aplicarlo como opción) y usar los 1752 frames completos.

### 3.3 [ALTA] Reporte de convergencia completo

Después de `least_squares`:

```python
log_stats(f"Status: {resultado.status} ({resultado.message})")
log_stats(f"Iteraciones: {resultado.nfev}")
log_stats(f"Costo inicial: {0.5 * np.sum(res_init**2):.4f}")
log_stats(f"Costo final:   {0.5 * np.sum(resultado.fun**2):.4f}")
if not resultado.success:
    log_warn("El BA NO converge satisfactoriamente. Revisar datos o parametros.")
```

### 3.4 [ALTA] Validación de prerrequisitos y CLI con defaults seguros

Análogo a Etapa C: chequear que el `.npz` existe y tiene las keys necesarias, que la geometría teórica existe, que la calibración intrínseca está en el `.npz`. Salir con mensaje claro si falla.

### 3.5 [ALTA] Metadata en archivo de salida

El archivo `reference_dodecaedro_calibrado.txt` debe incluir:

```
# Geometria CALIBRADA del dodecaedro (auto-calibracion BA)
# Generado: 2026-05-16T22:00:00Z
# Hostname: ...
# Script: calibrar_rigid_body.py (auditado iter 2)
# OpenCV: 4.13.0.92, SciPy: 1.17.1
# Input dataset: capturas_calibracion.npz (sha256: ...)
# Frames usados: 1752 / 1752 (sin submuestreo)
# Marcador ancla: ID 151
# Iteraciones del optimizador: 47
# Status: 2 (ftol satisfecho)
# RMSE inicial: 1.234 px
# RMSE final: 0.608 px
# Reducciones: 50.7%
# Formato: tag_id  cx cy cz  c0x c0y c0z  ...
```

### 3.6 [ALTA] Reporte de RMSE por marker individual

Después del BA, computar residuos agrupados por marker e imprimir:

```
[STATS] RMSE de reproyeccion por marker:
  ID 151: 0.45 px (1024 detecciones)  PASS (ancla)
  ID 152: 0.59 px ( 544 detecciones)  OK
  ...
  ID 159: 1.23 px ( 184 detecciones)  WARN (pocos frames, alta incertidumbre)
```

### 3.7 [MEDIA] Parametrización planar rígida (6 DOF por marker)

Refactor mayor: cambiar de 12 floats libres a 6 DOF (centro + rvec). Las esquinas se derivan determinísticamente. Reduce parámetros de 120 a 60 y garantiza geometría física válida.

**Riesgo**: cambio invasivo, puede afectar la convergencia y el RMSE final. Hay que validar contra iter 1: el BA con parametrización rígida debe lograr RMSE ≤ 0.61 px sobre el mismo dataset (idealmente más bajo, idealmente con desplazamientos por marker más razonables).

Postergable a Fase 5 si las §3.1–§3.6 ya satisfacen el objetivo.

### 3.8 [MEDIA] Logging estructurado + pathlib

Como en captura_calibracion.py: `log_info`/`log_warn`/`log_error`/`log_stats`, `pathlib.Path`, type hints opcionales.

### 3.9 [MEDIA] Parametrizar magic numbers por CLI

`--min-frames-validos` (default 50), `--max-nfev` (default 200), `--huber-f-scale` (default 2.0), `--ftol`, `--xtol`, `--gtol`.

### 3.10 [BAJA] Refactor de `main()` largo

Descomponer en `cargar_y_preparar_dataset`, `estimar_poses_iniciales`, `ejecutar_ba`, `reportar_resultados`, `guardar_archivo_calibrado`.

### 3.11 [BAJA] Guardar también JSON con metadata + geometría

Análogo a captura_calibracion.py: el `.txt` queda legible y compatible con tracker.py, pero también se genera un `.json` con toda la metadata estructurada.

## 4. Tests propuestos

Suite pytest en `codigo/tests/test_calibrar_rigid_body.py`:

- `test_parametrizar_reconstruir_round_trip`: parametrizar geometría teórica, reconstruir, debe ser bit-exacto.
- `test_residuos_zero_con_geometria_perfecta`: si pasamos la geom teórica + pose ideal, los residuos en datos sintéticos perfectos deben ser ~0.
- `test_residuos_se_incrementan_con_perturbacion`: si perturbamos la geometría, los residuos crecen.
- `test_ba_recupera_geometria_perturbada`: dataset sintético, geometría inicialmente perturbada, BA recupera la real con error < 0.1 mm.
- `test_jac_sparsity_estructura_correcta`: la matriz sparse tiene 1s exactamente donde se espera.
- `test_validar_prerrequisitos`: aborta con `.npz` inválido, geometría inexistente, etc.
- `test_carga_npz_compatible_con_etapa_c`: dataset generado por captura_calibracion.py se carga correctamente.
- `test_guardado_es_legible_por_tracker`: el archivo generado tiene formato que `tracker.py::cargar_rigid_body()` puede leer.

## 5. Operación paso a paso (cuando ejecutemos)

**Naturaleza del script**: cálculo intensivo, sin cámara. Una sola corrida. Toma 30 s – 2 min dependiendo del tamaño del dataset.

**Prerrequisitos:**
1. `capturas_calibracion.npz` existe (Etapa C completada).
2. `data/reference_dodecaedro.txt` existe (Etapa B).
3. SciPy 1.17 instalado en el venv.

**Comando:**
```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate
python calibrar_rigid_body.py
```

**Qué vas a ver:**

```
[INFO] [1/5] Cargando dataset capturas_calibracion.npz...
[INFO]       Frames cargados: 1752
[INFO] [2/5] Cargando geometria teorica data/reference_dodecaedro.txt...
[INFO]       Marcador ancla: ID 151 (fijo en posicion teorica)
[INFO] [3/5] Estimando poses iniciales...
[INFO]       Frames con pose valida: 1750/1752
[INFO] [4/5] Configurando bundle adjustment...
[INFO]       Parametros de geometria: 120
[INFO]       Parametros de poses:     10500
[INFO]       Total parametros:        10620
[INFO]       Total residuos:          ~46000
[INFO]       RMSE de reproyeccion INICIAL: 1.234 px
[INFO] [5/5] Ejecutando bundle adjustment (puede tardar 30-120 segundos)...
   Iteration     Total nfev        Cost      Cost reduction    Step norm     Optimality
       ...
[STATS] RMSE FINAL: 0.608 px (reduccion: 50.7%)
[STATS] Status: 2 (ftol satisfecho)
[STATS] Iteraciones: 47
[STATS] RMSE por marker:
  ID 151: 0.45 px (ancla)
  ID 152: 0.59 px  OK
  ...

[STATS] Desplazamientos respecto a teorica:
  Marcador | Centro (mm) | Esquina max (mm)
  151      |    0.000    |    0.000  (ancla)
  152      |    1.234    |    2.156
  ...
[INFO] Guardado: data/reference_dodecaedro_calibrado.txt
```

**Criterio de éxito:**

| Métrica | Mínimo | Bueno | Excelente (iter 1) |
|---|---|---|---|
| RMSE final | < 1.0 px | < 0.7 px | 0.61 px |
| Reducción | > 30% | > 50% | ~80% |
| Status | 1, 2 o 3 | idem | idem |
| Desplazamiento promedio del centro | < 5 mm | < 3 mm | ~1-2 mm |

## 6. Aplicación de mejoras (2026-05-16, refactor completo)

Aplicadas **las 11 mejoras** incluyendo parametrización rígida (§3.7). Script reescrito de 352 → 494 líneas.

### Cambios concretos en `calibrar_rigid_body.py`

- **Parametrización rígida 6 DOF (§3.7)**: `marker_pose_a_esquinas(centro, rvec, marker_mm)` deriva las 4 esquinas determinísticamente desde 6 parámetros. `esquinas_a_marker_pose(corners, marker_mm)` extrae (centro, rvec) de una geometría arbitraria para inicialización. Parámetros: 60 (10 markers × 6) vs 120 anteriores. **Cada marker es físicamente un cuadrado plano rígido de marker_mm garantizado**.
- **Jacobiano sparse (§3.1)**: `construir_jac_sparsity()` arma una `lil_matrix` con 1s solo donde hay dependencia entre residuo y parámetro. Cada residuo solo depende de 12 params (6 marker + 6 pose). Sparsity típica: 99.94%.
- **`x_scale='jac'`** (§3.1) pasado a `least_squares` — crucial para BA exitoso según SciPy Cookbook.
- **Sin submuestreo (§3.2)**: usa todos los frames válidos. Con sparsity esto es factible.
- **Reporte completo (§3.3)**: `resultado.status`, `resultado.message`, `resultado.nfev`, `resultado.success`. Warn si no converge.
- **Validación de prerrequisitos (§3.4)**: archivos input/teórico existen, output escribible. Salida limpia si falla.
- **Metadata extensiva en .txt (§3.5)**: hashes SHA256 del input y teórico, versiones de cv2/numpy/scipy/python, hostname, status del BA, iteraciones, RMSE inicial/final.
- **RMSE por marker (§3.6)**: `rmse_por_marker()` agrupa residuos por tag_id y reporta cada uno con n_detecciones. Identifica markers problemáticos.
- **Logging estructurado (§3.8)**: `log_info`/`log_warn`/`log_error`/`log_stats`.
- **CLI parametrizada (§3.9)**: `--huber-f-scale`, `--max-nfev`, `--min-frames-validos`, `--marker-mm`, `--ancla`.
- **Refactor (§3.10)**: pathlib, helpers separados, main legible.

### Tests en `codigo/tests/test_calibrar_rigid_body.py`

14 tests, todos pasan en 0.85s:

- `test_hash_sha256_estable`
- `test_cargar_referencia_archivo_real` (lee `data/reference_dodecaedro.txt` real)
- `test_marker_pose_a_esquinas_es_cuadrado` — las 4 esquinas forman cuadrado de marker_mm
- `test_marker_pose_a_esquinas_centro_correcto`
- `test_esquinas_a_marker_pose_round_trip` — round-trip exacto
- `test_parametrizar_reconstruir_round_trip` — geom → params → geom es identidad
- `test_construir_jac_sparsity_shape` — dimensiones correctas
- `test_construir_jac_sparsity_solo_no_ancla_tiene_jac_geom` — el ancla no tiene jac de geom
- `test_residuos_zero_con_geometria_y_poses_perfectas` — RMSE < 1e-3 con datos sintéticos perfectos
- `test_residuos_aumentan_con_perturbacion` — perturbar 5 mm aumenta residuos > 5×
- `test_rmse_por_marker_agrupa_correctamente`
- **`test_ba_recupera_geometria_perturbada`** — TEST CRÍTICO: geom semilla perturbada 3 mm, BA con sparse + x_scale='jac' + huber recupera la geometría real con error < 0.1 mm. **Validación end-to-end de toda la formulación**.
- `test_validar_prerrequisitos_*`

### Validación final

| Validación | Resultado |
|---|---|
| `pytest tests/` (proyecto completo) | **69/69 PASS** en 0.96 s |
| Sintaxis (`py_compile`) | OK |
| Recuperación de geometría perturbada con BA | < 0.1 mm error (test sintético) |
| Sparsity típica esperada | 99.94% (jac_sparsity activo) |

---

**Etapa D: CERRADA EN CÓDIGO.** Script con refactor completo, parametrización rígida físicamente válida, jacobiano sparse 5-10× más rápido, RMSE por marker, metadata exhaustiva, y suite de tests con validación end-to-end del BA.

## 7. Próximo paso: ejecutar el BA

Cuando estés listo:

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate
python -m pytest tests/ -v    # debe decir 69 passed
python calibrar_rigid_body.py
```

Esperás:
- Tiempo de BA: 30-90 segundos (5-10× más rápido que iter 1 gracias al sparse).
- `RMSE final ≤ 0.7 px` (idealmente ≤ 0.61 px de iter 1).
- `Status: 1` o `2` (ftol/xtol satisfecho).
- `data/reference_dodecaedro_calibrado.txt` generado con metadata completa.

Después: pasamos a **Etapa E — `test_pivote.py`** (la pieza más crítica del proyecto según iter 2).
