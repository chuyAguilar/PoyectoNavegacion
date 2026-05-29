# 03a — Auditoría de `generar_reference_dodecaedro.py`

**Fase 3 de la auditoría de iteración 2 · Script de Etapa B.** Fecha: 2026-05-16.

## Resumen ejecutivo

- **Estado del script**: tiene un bug de convención en la orientación local de las caras del cinturón (IDs 152–161).
- **Impacto si se regenera el archivo con el script tal cual**: el `reference_dodecaedro.txt` resultante tiene las esquinas rotadas **90° CW** respecto al histórico para los 10 marcadores del cinturón. El ID 151 (TOP) es correcto.
- **El histórico de iter 1 es físicamente correcto.** El BA con RMSE 0.61 px y todo el pipeline downstream lo validan.
- **Fix propuesto y verificado matemáticamente**: corregir `construir_cara` para que la convención coincida con `label-hacia-+Z`. Con el fix, el script reproduce el histórico bit-a-bit (dentro del redondeo).

---

## 1. Convenciones verificadas

### OpenCV `detectMarkers` (4.13.0.92, confirmado vía Context7)

> *"`detectMarkers()` … `markerCorners` provides the coordinates of the four corners for each detected marker in a clockwise order starting from the top-left."*

→ Orden: **`[TL, TR, BR, BL]`** en sentido horario.

### `SOLVEPNP_IPPE_SQUARE` (4.13.0.92, confirmado vía Context7)

> Object points must be defined in this order:
> ```
> point 0: [-L/2,  L/2, 0]   ← TL
> point 1: [ L/2,  L/2, 0]   ← TR
> point 2: [ L/2, -L/2, 0]   ← BR
> point 3: [-L/2, -L/2, 0]   ← BL
> ```

### Convención del archivo histórico (`reference_dodecaedro.txt`)

Header dice: `c0=top-left c1=top-right c2=bottom-right c3=bottom-left` — coincide con OpenCV.

### Convención física del proyecto (skill `surgical-nav-project-context`)

> "ID label apuntando hacia la punta" — es decir, el `+y` del label apunta hacia la cara TOP (el lado donde está la punta del stylus).

---

## 2. Comparación numérica script vs histórico

Centro de cada marker: **idéntico hasta redondeo** (< 0.001 mm en todos los IDs).

Esquinas:

| ID | Mejor match | Error |
|---|---|---|
| 151 (TOP) | shift 0 | 0.000655 mm |
| 152 (belt) | shift +3 (equiv. histórico = roll(script, +1)) | 0.000735 mm |
| 153 | shift +3 | 0.000978 mm |
| 154 | shift +3 | 0.000737 mm |
| 155 | shift +3 | 0.000737 mm |
| 156 | shift +3 | 0.000978 mm |
| 157 | shift +3 | 0.000737 mm |
| 158 | shift +3 | 0.000978 mm |
| 159 | shift +3 | 0.000735 mm |
| 160 | shift +3 | 0.000978 mm |
| 161 | shift +3 | 0.000737 mm |

Detalle ID 152:

```
HISTORICO esquinas:               SCRIPT esquinas:
  c0: (+16.341, -8, +17.115)         c0: (+23.497, -8,  +2.804)
  c1: (+16.341, +8, +17.115)         c1: (+16.341, -8, +17.115)
  c2: (+23.497, +8,  +2.804)         c2: (+16.341, +8, +17.115)
  c3: (+23.497, -8,  +2.804)         c3: (+23.497, +8,  +2.804)
```

→ `historico[i] = script[(i+1) mod 4]`. Es una rotación cíclica +1 = rotación 90° CW alrededor de la normal saliente.

---

## 3. Causa raíz

En `construir_cara` (líneas 87–137), el frame local de la cara se construye así:

```python
# 1. Elegir x_local como proyeccion de +Z sobre el plano de la cara
x_local = z_global - dot(z_global, normal) * normal
x_local = x_local / norm(x_local)

# 2. y_local = cross(normal, x_local)
y_local = np.cross(normal, x_local)
y_local = y_local / norm(y_local)
```

**El problema**: `x_local` así definido **es físicamente el eje "up" del marker** (es la proyección de +Z, y por convención del proyecto el label apunta hacia +Z). Llamarlo `x_local` es incorrecto semánticamente. Y `y_local = cross(normal, x_local)` con esa nomenclatura termina apuntando al "left" físico del marker, no al "right".

Luego al construir las esquinas con:

```python
esquinas_locales = [
    (-half, +half, 0),  # rotulado c0=TL
    (+half, +half, 0),  # c1=TR
    (+half, -half, 0),  # c2=BR
    (-half, -half, 0),  # c3=BL
]
```

interpretadas en el frame `(x_local, y_local)`, el `c0=(-half,+half)` cae en la posición global que físicamente es **BL** del marker (porque `x_local` es realmente up y `y_local` es realmente -right). Por eso `script[c0] = historico[c3]` y todo el shift +1.

### Verificación para ID 151 (caso especial que SÍ matchea)

El script tiene una rama especial cuando la normal es paralela a ±Z:

```python
if abs(np.dot(normal, z_global)) > 0.99:
    x_ref = np.array([1, 0, 0])
```

En esa rama, `x_local = (1,0,0)` y `y_local = cross((0,0,1), (1,0,0)) = (0,1,0)`. Aquí sí `x_local` es horizontal y `y_local` es vertical en sentido físico. Por eso ID 151 matchea el histórico sin shift.

---

## 4. Fix propuesto

Reemplazar `construir_cara` con la siguiente versión (la matemática se verificó manualmente para ID 151 e ID 152 y reproduce el histórico):

```python
def construir_cara(centro, normal, rotacion_propia=0):
    """Construye las 4 esquinas de un marcador.

    Convencion del proyecto: el label del marker apunta hacia +Z (toward TOP),
    coherente con 'ID label apuntando hacia la punta'.

    Frame local del marker:
      y_marker: 'up' del label = proyeccion normalizada de +Z sobre el plano de la cara
                (caso especial: si la cara es TOP/BASE, usar +Y global)
      x_marker: 'right' del label = cross(y_marker, normal) -> right-handed con normal saliente
      z_marker: la normal saliente

    Orden de las esquinas (OpenCV): c0=TL, c1=TR, c2=BR, c3=BL
    """
    z_global = np.array([0, 0, 1])

    if abs(np.dot(normal, z_global)) > 0.99:
        # Cara TOP o BASE: no hay 'up' natural derivado de +Z; usar +Y global.
        y_marker = np.array([0, 1, 0])
    else:
        y_marker = z_global - np.dot(z_global, normal) * normal
        y_marker = y_marker / np.linalg.norm(y_marker)

    x_marker = np.cross(y_marker, normal)
    x_marker = x_marker / np.linalg.norm(x_marker)

    # Rotacion propia del marcador (alrededor de la normal saliente)
    if rotacion_propia != 0:
        R = rotation_matrix(normal, rotacion_propia)
        x_marker = R @ x_marker
        y_marker = R @ y_marker

    half = MARKER_MM / 2
    esquinas_locales = [
        np.array([-half,  half, 0]),  # c0 = TL
        np.array([ half,  half, 0]),  # c1 = TR
        np.array([ half, -half, 0]),  # c2 = BR
        np.array([-half, -half, 0]),  # c3 = BL
    ]

    R_local_to_global = np.column_stack([x_marker, y_marker, normal])
    esquinas_globales = np.array([
        centro + R_local_to_global @ esq for esq in esquinas_locales
    ])
    return esquinas_globales
```

**Verificación manual del fix:**

- ID 151 (TOP, normal=(0,0,1)): caso especial → `y_marker=(0,1,0)`, `x_marker = cross(y_marker, normal) = cross((0,1,0),(0,0,1)) = (1,0,0)`. Corners idénticos al script original (y al histórico). ✓
- ID 152 (belt, normal=(0.8944, 0, 0.4472)): `y_marker = (-0.447, 0, 0.894)`, `x_marker = cross(y_marker, normal) = (0, 1, 0)`. Corner c0 = centro + (-x_m + y_m)·half = (19.919, 0, 9.957) + (0, -8, 0) + (-3.578, 0, 7.155) = (16.341, -8, 17.112). Matchea histórico c0=(16.341, -8, +17.115). ✓

---

## 5. Validación adicional sobre la convención de orientación

Una ligera duda: ¿la regla "label apunta hacia +Z" es realmente la que se siguió al pegar los markers en iter 1, o el histórico se generó con otra convención y el sistema funcionó de casualidad?

Argumentos de que es la regla correcta:
1. Convención documentada en el skill `surgical-nav-project-context`: "ID label apuntando hacia la punta".
2. El BA de iter 1 convergió a 0.61 px RMSE → seed muy cercano al óptimo geométrico → la convención del seed coincide con la real.
3. Pivote alcanzó std 1.7 mm — eso sería imposible si la convención del frame del dodecaedro estuviera 90° rotada y eso no se propagara consistentemente.
4. Visualización en Slicer coherente con el setup físico (registro 3.46 mm RMS).

Riesgo: si en alguna cara el marker se pegó "al revés" (label rotado 90° respecto a la regla), el BA habría compensado moviendo esa esquina en el calibrado. Habría que mirar `reference_dodecaedro_calibrado.txt` y comparar marker por marker contra el teórico para ver si alguno tiene un offset anómalo en orientación. **Acción pendiente: revisar en la auditoría de Etapa D.**

---

## 6. Búsqueda en GitHub (regla de memoria)

Aplicando la regla `feedback_verificar_apis_antes_de_codigo`:

- **`scikit-surgerybard`** (referenciado en el header del histórico): librería de UCL/Wellcome EPSRC para AR quirúrgica. Pendiente: confirmar si tiene una utilidad de generación de geometría de dodecaedro que podríamos usar como referencia/reemplazo.
- **`opencv-aruco-dodecahedron`** / **`pose-estimation-multi-marker`**: pendiente buscar.
- **Pieza canónica del problema**: "rigid body multi-marker geometry generator" — pendiente.

Acción: hacer una búsqueda dirigida después de aplicar el fix, no antes (no bloqueante).

---

## 7. Decisión y plan de acción

Recomendación:

1. **Aplicar el fix a `generar_reference_dodecaedro.py`** y actualizar su docstring (sacar la advertencia y dejar nota del fix con fecha).
2. **Regenerar `codigo/data/reference_dodecaedro.txt`** con el script corregido.
3. **Validar por comparación bit-a-bit** con el archivo histórico (`historico/iter1_2026-05-16/data/reference_dodecaedro.txt`). Tolerancia esperada: < 0.001 mm en cada componente (solo redondeo).
4. Si la validación pasa: dar el script por auditado, marcar Etapa B como completada, pasar a Etapa C.
5. Si la validación falla en algún ID: revisar la matemática de ese ID antes de continuar.

Riesgos del fix:
- Mínimos. El cambio es semántico/de nomenclatura + la dirección de cálculo de `x_marker`. La matemática se verificó a mano para TOP y belt antes de proponerlo.
- El TOP queda equivalente al original (ambas convenciones dan el mismo resultado allí gracias a la rama del caso especial).

Riesgos de NO aplicar el fix:
- Para iter 2 con IDs 151–161 podríamos seguir usando el histórico (copia inversa al data/), pero al migrar a IDs 1–11 el script estaría disponible y produciría geometría con esquinas mal orientadas — bug latente.
- Sin fix, la procedencia del archivo `reference_dodecaedro.txt` queda manual (recuperación de chat) y no reproducible — viola el objetivo de iter 2.

---

## 8. Resultado final (2026-05-16)

**Fix aplicado y validado.** El script corregido regenera `data/reference_dodecaedro.txt` bit-a-bit idéntico al histórico:

```
ID    err_centro    err_max_esq    estado
-----------------------------------------
151    0.000000      0.000000        OK
152    0.000000      0.000000        OK
...
161    0.000000      0.000000        OK
-----------------------------------------
Resumen: 11/11 markers OK
```

Error máximo en TODOS los componentes: **0.000000 mm** (precisión completa de float64, no solo dentro de la tolerancia de 0.001 mm).

**Cambios aplicados al script:**
1. Reemplazada la advertencia del docstring por nota de historia + fix.
2. `construir_cara` reescrita con nomenclatura semántica (`x_marker`, `y_marker`) y convención `y_marker = proyección +Z`.
3. `__main__` ahora acepta `--output` (default `data/reference_dodecaedro.txt`) y crea el directorio si no existe.

**Notas operativas para el usuario:**

- Para ejecutarlo en su máquina:
  ```powershell
  cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
  .\.venv\Scripts\activate
  python generar_reference_dodecaedro.py
  ```
  El archivo queda en `codigo/data/reference_dodecaedro.txt` directamente listo para Etapa C.

- Si se cambia a IDs 1-11 (iter 2 futura), basta editar las constantes `ID_TOP`, `IDS_SUPERIOR`, `IDS_INFERIOR` en el script (líneas 71-79). La matemática queda intacta.

- Sobre cachés Python: en el filesystem del proyecto, los `.pyc` pueden quedar desincronizados respecto a los `.py` (mtime stale). Si después de editar un script el comportamiento no cambia, hacer `touch` al `.py` (PowerShell: `(Get-Item script.py).LastWriteTime = Get-Date`) o eliminar `__pycache__/`.

**Etapa B (recuperación + fix): CERRADA. Auditada y reproducible.**

---

## 9. AUDITORÍA REAL: oportunidades de mejora (2026-05-16)

Lo anterior fue restauración. La auditoría de calidad sigue acá. Consultados: Context7 (OpenCV 4.x, SciPy), búsqueda en GitHub (SciKit-Surgery, opencv_contrib/aruco, repos de pose-estimation multi-marker). Verificada toda la matemática del dodecaedro contra fórmulas canónicas — pasa con error 0.

### 9.1 Correctness matemática — IMPECABLE

Validación contra Wikipedia/Wolfram/derivaciones manuales:

| Constante | Valor del script | Canónico (verificado) | Diff |
|---|---|---|---|
| PHI = (1+√5)/2 | 1.6180339887 | 1.6180339887 | 0 |
| PHI² − PHI − 1 = 0 | — | — | True |
| Inradius r = a·φ²/(2√(3−φ)) | 22.270327 mm | igual a (a/2)·√(5/2 + 11√5/10) | 3.5e-15 mm |
| THETA = arccos(1/√5) | 63.4349° | igual a π − dihedral(116.565°) | 0 |
| d(TOP, cinturón) | 23.416408 mm | 2r·sin(θ/2) = 23.416408 | 0 |
| d(152, 157) | 23.416408 mm | igual al anterior (arista compartida) | 0 |
| Suma de las 12 normales | (≈0, 0, ≈0) | 0 por simetría | 5e-16 |
| Marker 16 mm vs cara Ø34.03 mm | margen 9.01 mm | OK | — |

**Conclusión: la matemática del script es correcta hasta precisión de máquina. No hay cambios de correctness a proponer.**

### 9.2 Mejoras de robustez y código (propuestas)

Las catalogo por impacto. El usuario decide cuáles aplicar.

#### 9.2.1 [ALTA] Validación exhaustiva de la geometría

`validar_geometria()` actualmente chequea solo UNA distancia (ID 152 ↔ ID 157). Para una auditoría seria conviene validar:

- PHI, R_IN, THETA contra fórmulas canónicas.
- TODAS las distancias centro-a-centro entre caras adyacentes (deben ser iguales).
- Que todas las caras estén a `r_in` del origen.
- Que todas las normales tengan norma 1.
- Que la suma de las 12 normales (incluyendo BASE virtual) sea ≈ 0 (simetría).
- Que el tamaño del marker quepa en la cara pentagonal con margen razonable.
- Reporte tipo PASS/FAIL por cada chequeo + valor numérico + tolerancia.

Beneficio: al cambiar a IDs 1–11 o cualquier futura modificación, basta correr el script para tener evidencia de que la geometría no se rompió. Es la "test suite" del script.

#### 9.2.2 [ALTA] Tests automatizados (pytest)

Crear `tests/test_generar_reference_dodecaedro.py` con:

- `test_phi_identity`: PHI² = PHI + 1.
- `test_inradius_canonical`: dos fórmulas equivalentes coinciden.
- `test_dodecahedron_symmetry`: suma de las 12 normales ≈ 0.
- `test_all_faces_equidistant`: todas las caras a r_in.
- `test_marker_fits_in_face`: MARKER_MM < diámetro circunscrito de la cara.
- `test_corner_convention_opencv`: el frame local es right-handed con normal saliente, y c0=TL=-x+y, etc.
- `test_regenerate_matches_historico`: corre el script y compara contra `historico/iter1_2026-05-16/data/reference_dodecaedro.txt` con tolerancia 0.001 mm.

Beneficio: CI lo corre en cada commit; cualquier regresión se caza al toque.

#### 9.2.3 [ALTA] Parametrizar IDs y geometría por CLI

Hoy `ID_TOP=151`, `IDS_SUPERIOR=[152..156]`, `IDS_INFERIOR=[157..161]`, `EDGE_MM=20`, `MARKER_MM=16` están hardcoded. Propuesta: aceptar como argparse con defaults actuales, o leer un YAML opcional. Para la futura migración a IDs 1–11 no hay que tocar código fuente.

Ejemplo:
```powershell
python generar_reference_dodecaedro.py `
    --id-top 1 --ids-superior 2,3,4,5,6 --ids-inferior 7,8,9,10,11 `
    --edge-mm 20 --marker-mm 16 `
    --output data/reference_dodecaedro_iter2.txt
```

Beneficio: cambio de IDs queda trazable en el comando, no en un diff del archivo .py. Reduce riesgo de inconsistencia entre `tracker_config.yaml`, `reference_dodecaedro.txt` y el script.

#### 9.2.4 [MEDIA] Reemplazar `rotation_matrix` manual por `scipy.spatial.transform.Rotation`

El script implementa Rodrigues a mano (líneas 75–84). SciPy 1.17 (instalado en el venv) tiene `Rotation.from_rotvec(axis * angle)` que es:
- más legible,
- testeado por la comunidad SciPy,
- compatible con composición, slerp, conversión a cuaternión, etc.,
- soporta `degrees=True` para evitar confusión.

Cambio mínimo:
```python
from scipy.spatial.transform import Rotation as R
# en lugar de:  R_rot = rotation_matrix(normal, rotacion_propia)
R_rot = R.from_rotvec(normal * rotacion_propia).as_matrix()
```

Beneficio: una función menos de mantener, una librería estándar más. Riesgo: ~0 (el campo `rotacion_propia` no se usa en la geometría actual; está disponible para uso futuro).

#### 9.2.5 [MEDIA] Validar inputs antes de generar

Agregar al inicio de `construir_dodecaedro()`:

```python
if EDGE_MM <= 0 or MARKER_MM <= 0:
    raise ValueError("EDGE_MM y MARKER_MM deben ser positivos")
diametro_cara = EDGE_MM / np.sin(np.radians(36))
if MARKER_MM >= diametro_cara:
    raise ValueError(
        f"MARKER_MM={MARKER_MM} >= diametro_cara={diametro_cara:.2f}; "
        f"el marker no cabe en la cara pentagonal del dodecaedro de arista {EDGE_MM}"
    )
```

Beneficio: catch temprano de errores físicos.

#### 9.2.6 [BAJA] Mover `from pathlib import Path` arriba

Hoy está dentro del `if __name__ == "__main__":`. Mover al bloque de imports al principio del archivo. Cosmético.

#### 9.2.7 [BAJA] Output JSON con metadata además del .txt

El archivo actual es texto plano sin schema. Propuesta: opcionalmente generar también un `reference_dodecaedro.json` con:

```json
{
  "schema_version": "1.0",
  "generated_by": "generar_reference_dodecaedro.py",
  "generated_at": "2026-05-16T20:42:48Z",
  "params": {"edge_mm": 20.0, "marker_mm": 16.0, "id_top": 151, ...},
  "convention": {
    "corner_order": "OpenCV: c0=TL, c1=TR, c2=BR, c3=BL",
    "label_direction": "label apunta hacia +Z (regla: hacia la punta)",
    "frame": "origen en centro del dodecaedro, +Z hacia TOP"
  },
  "validation": {"r_in_mm": 22.27, "dihedral_deg": 116.565, ...},
  "markers": [
    {"id": 151, "center": [0, 0, 22.270], "corners": [[-8,8,22.27], ...]},
    ...
  ]
}
```

Beneficio: trazabilidad, machine-readable, fácil de comparar versiones. Es la pieza que pediría el reviewer/CI más serio.

#### 9.2.8 [FUTURO] Migrar a `cv2.aruco.Board` nativo

OpenCV ya tiene `cv2.aruco.Board(objPoints, dictionary, ids)` que **acepta cualquier layout 3D** (no solo planar), y `Board.matchImagePoints()` empareja automáticamente detecciones 2D con puntos 3D. Hoy `tracker.py` hace ese matching y la concatenación 3D-2D a mano.

Camino futuro (NO para iter 2 inmediato — requiere tocar tracker.py):
- `generar_reference_dodecaedro.py` produce un `Board` y lo serializa con `cv2.FileStorage` o pickle.
- `tracker.py` carga el `Board`, usa `Board.matchImagePoints()` + `solvePnP` (sin concat manual).

Beneficio: menos código propio que mantener, API canónica de OpenCV, compatible con `refineDetectedMarkers` (que mejora detecciones a partir de la geometría conocida).

Riesgo: cambio de arquitectura, afecta tracker.py y calibrar_rigid_body.py. Postergar a Fase 5 (mejoras post-auditoría).

### 9.3 Sobre SciKit-SurgeryBARD

El header del archivo histórico decía "para SciKit-SurgeryBARD". Investigación:

- **SciKit-SurgeryBARD** (UCL Wellcome EPSRC, BSD-3): demo de AR quirúrgica que usa ArUco markers. Test Python 3.6 (versión vieja).
- **SciKit-SurgeryArUcoTracker** (mismo grupo): wrapper de `cv2.aruco`, lee rigid bodies por filename.
- Ninguno de los dos repos contiene un generador de geometría de dodecaedro. El header histórico solo indica que el formato del .txt fue pensado para alimentar a esos trackers, pero no usan código de ellos.

Conclusión: no hay deuda de compatibilidad activa con SciKit-Surgery. Si en el futuro se quiere integrar, basta con que el formato siga siendo `tag_id + 12 floats` o JSON estructurado.

### 9.4 Recomendación final

Aplicar en orden de prioridad:

1. **9.2.1 + 9.2.2** (validación exhaustiva + tests pytest): es lo que cierra el "verificar correctness" del objetivo de iter 2.
2. **9.2.3** (parametrizar IDs): habilita la migración futura a 1–11 sin tocar el .py.
3. **9.2.5** (validar inputs): catch temprano de errores.
4. **9.2.4 + 9.2.6 + 9.2.7** (scipy Rotation + imports + JSON): cosméticos y de calidad, opcional.
5. **9.2.8** (cv2.aruco.Board): postergar a Fase 5.

---

## 10. Aplicación de mejoras (2026-05-16, segunda pasada)

Aplicadas las 3 mejoras de alta prioridad: validación exhaustiva, tests pytest en `codigo/tests/`, parametrización CLI completa.

### Cambios concretos en `generar_reference_dodecaedro.py`

- Refactorizado: `construir_cara`, `construir_dodecaedro`, `validar_geometria`, `guardar_archivo` aceptan ahora todos los parámetros (`edge_mm`, `marker_mm`, `id_top`, `ids_superior`, `ids_inferior`). Defaults reproducen iter 1.
- `validar_geometria` reescrita: ahora chequea 11 invariantes (PHI, THETA, dos fórmulas de inradius, equidistancia, simetría de normales, adyacencias TOP-cinturón y antiprismática, marker fit en cara, esquinas cuadradas). Devuelve `bool` para uso en tests. Reporte estilo PASS/FAIL.
- Rodrigues manual reemplazado por `scipy.spatial.transform.Rotation.from_rotvec` (solo en código de `rotacion_propia`, no afecta geometría default).
- `_validar_inputs` agregada: errores controlados con `ValueError` para inputs inválidos (edge≤0, marker no cabe en cara, IDs duplicados, etc.).
- CLI completa: `--edge-mm`, `--marker-mm`, `--id-top`, `--ids-superior`, `--ids-inferior`, `--output`, `--no-validate`.

### Tests en `codigo/tests/test_generar_reference_dodecaedro.py`

29 tests, todos pasan en 0.25s. Cubren:

- Identidades matemáticas (PHI, THETA, dihedral).
- Inradius vía dos fórmulas equivalentes para varias aristas (parametrizado).
- Estructura: 11 markers, IDs default, esquinas 4×3, cuadrado de lado marker_mm, diagonales correctas.
- Invariantes geométricos: equidistancia, simetría de normales, adyacencias.
- Frame OpenCV right-handed con normal saliente.
- **Reproducibilidad bit-a-bit contra histórico** (test_matches_historico_iter1).
- **Migración iter 2 (IDs 1-11)**: geometría idéntica permutada, validación pasa.
- Inputs inválidos: 4 tests de `ValueError` controlado.

### Validación final

| Validación | Resultado |
|---|---|
| `pytest tests/` | **29/29 PASS** en 0.25s |
| `validar_geometria` (iter 1) | **11/11 PASS** (todos los chequeos en 0.000 mm) |
| `validar_geometria` (iter 2 IDs 1-11) | **11/11 PASS** |
| Bit-a-bit `data/reference_dodecaedro.txt` vs histórico | **11/11 PASS**, max_err 0.000000 mm |
| Migración IDs 1-11 (CLI) | Genera archivo correcto sin tocar el .py |

### Comandos de uso

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate

# Generar iter 1 (default, IDs 151-161)
python generar_reference_dodecaedro.py

# Migrar a iter 2 (IDs 1-11) sin tocar el código
python generar_reference_dodecaedro.py `
    --id-top 1 --ids-superior 2,3,4,5,6 --ids-inferior 7,8,9,10,11 `
    --output data/reference_dodecaedro_iter2.txt

# Correr la suite de tests
pip install pytest    # solo la primera vez
pytest tests/ -v

# Generar otro tamaño (futuro impreso distinto)
python generar_reference_dodecaedro.py --edge-mm 25 --marker-mm 20
```

### Mejoras NO aplicadas (deuda diferida)

Por decisión del usuario quedan postergadas (Fase 5 o más adelante):

- §9.2.6 Imports al tope del archivo (cosmético).
- §9.2.7 Output JSON con metadata (nice-to-have, no bloquea).
- §9.2.8 Migración a `cv2.aruco.Board` nativo (cambio mayor que afecta tracker.py y calibrar_rigid_body.py — para Fase 5).

---

**Etapa B: CERRADA COMPLETA.** Script auditado, mejorado, parametrizado, con suite de tests automatizados. Reproducibilidad y correctness validadas tanto matemáticamente como contra el histórico.

**Siguiente:** `03b_auditoria_captura_calibracion.md` — auditoría de `captura_calibracion.py` (Etapa C).
