# 03b2 — Herramienta opcional: Calibración Topológica del Dodecaedro

**Fase 3 de la auditoría de iteración 2 · Herramienta de verificación.** Fecha: 2026-05-16, actualizado 2026-05-19.

> **ACTUALIZACIÓN 2026-05-19**: este script se planteó originalmente como
> Etapa C.5 obligatoria del pipeline. Después de ejecutarlo sobre el
> dataset de iter 2 y comparar resultados con el archivo teórico original,
> **no aporta diferencia material** al RMSE final del BA (ambos archivos
> dan RMSE ~11 px, sin convergencia). El problema real del BA estaba en
> el **dataset capturado**, no en la topología del cubo.
>
> Por eso, **queda reposicionado como HERRAMIENTA OPCIONAL de verificación**,
> NO como paso obligatorio del pipeline. Útil para:
>
> - Verificar el orden de pegado de un dodecaedro nuevo.
> - Confirmar que la topología física matchea un dodecaedro regular.
> - Documentar el orden real de IDs en un cubo armado.
>
> Lecciones aprendidas en `historico/iter2_callejones_sin_salida/README.md`.

## Motivación

Durante la auditoría de Etapa D se descubrió que **el dodecaedro físico armado en iter 2 tiene markers pegados en posiciones distintas a las asumidas por `generar_reference_dodecaedro.py`**. Concretamente, las distancias 3D medidas entre pares de markers en el dataset capturado no coinciden con las distancias teóricas para muchos pares (errores hasta 4×).

Esto genera:
- RMSE inicial alto (~15 px vs ~1 px esperado).
- Bundle adjustment que no converge.
- Desplazamientos sistemáticos en la geometría calibrada (~28 mm en el cinturón inferior).

### Por qué importa para reproducibilidad

Cada vez que alguien quiera replicar este proyecto:
- Arma físicamente el dodecaedro (imprime, pega 11 markers, atornilla mango).
- **Es muy fácil cometer errores de pegado**: orden de IDs alrededor del anillo, qué ID va arriba vs abajo, orientación del label (rotación de 0/90/180/270°).
- Imponer una convención manual estricta es frágil: el sistema debería ser **robusto** al error humano.

**Solución propuesta**: una etapa de calibración topológica que infiere la geometría real del dodecaedro físico a partir del dataset capturado, sin requerir que el usuario haya seguido una convención de pegado específica.

## 1. Algoritmo de calibración topológica

### Inputs
- `capturas_calibracion.npz` (Etapa C).
- Calibración intrínseca (K, dist) — viene del .npz.
- Parámetros físicos conocidos: **arista del dodecaedro**, **tamaño del marker** (para la geometría canónica).

### Output
- `data/reference_dodecaedro_real.txt`: geometría calibrada al dodecaedro físico, en el mismo formato que el teórico. Drop-in replacement para `calibrar_rigid_body.py`.

### Pipeline

#### Paso 1: Estimación de pose individual por marker

Para cada frame y cada marker detectado:
- Usar `cv2.solvePnPGeneric(obj, img, K, dist, flags=SOLVEPNP_IPPE_SQUARE)` que devuelve hasta 2 soluciones (la ambigüedad planar característica de IPPE).
- Filtrar la solución con `tvec[2] > 0` (físicamente válida: marker delante de la cámara).
- Si hay dos soluciones válidas, elegir la de menor error de reproyección.

Como geometría del marker se usa un cuadrado de `marker_mm` lado en el plano XY local (no se necesita la geometría del dodecaedro completa para esto, solo el marker individual).

Almacenar por cada marker: lista de `(rvec, tvec)` para todos los frames donde se vio.

#### Paso 2: Cálculo de distancias entre pares

Para cada frame con ≥2 markers visibles, calcular la distancia 3D entre cada par de centros. Acumular las medidas por par.

Estadística robusta por par: **mediana** (no media, para tolerar outliers de IPPE).

#### Paso 3: Clasificación de adyacencias

En un dodecaedro regular de arista `edge_mm` con r_in = `edge_mm * φ² / (2√(3-φ))`:

| Categoría | Distancia centro-centro | Multiplicidad por cara |
|---|---|---|
| Misma cara (no aplica entre pares) | 0 | — |
| Adyacente (comparten arista) | `2·r_in·sin(θ/2)` ≈ 23.4 mm para edge=20 | 5 |
| Segundo vecino | varía según geometría | varía |
| Cara opuesta | `2·r_in` ≈ 44.5 mm | 1 |

Umbral de adyacencia: `2·r_in·sin(θ/2) ± tolerancia` (default tol = ±5 mm).

Para cada par con distancia mediana en el umbral de adyacencia → marcar como adyacente.

Resultado: dict `adyacencias = {mid: set[mids_adyacentes]}`.

#### Paso 4: Validación de la estructura

Para un dodecaedro válido (12 caras, 11 markers + base):

- 1 cara central (TOP) con **5 vecinos** (todos adyacentes a TOP).
- 5 caras del cinturón superior, cada una adyacente a:
  - TOP (1)
  - 2 vecinos en el mismo cinturón
  - 2 caras del cinturón inferior (compartiendo aristas distintas)
  - Total: 5 vecinos
- 5 caras del cinturón inferior, cada una adyacente a:
  - 2 caras del cinturón superior
  - 2 vecinos en el mismo cinturón inferior
  - **BASE** (sin marker) — no aparece en el grafo
  - Total: 4 vecinos VISIBLES (pero teóricamente 5)

Validaciones:
- Total de markers = 11 ± 0.
- 1 marker con 5 vecinos (TOP).
- 5 markers con 5 vecinos (cinturón superior, cuentan TOP + 2 sup + 2 inf).
- 5 markers con 4 vecinos visibles (cinturón inferior, faltan vínculo a BASE).

Si la estructura **no matchea**:
- Markers extra/faltantes → reportar.
- Más de un nodo con 5 adyacencias → falla; pedir confirmación del TOP físico.
- Grafo desconectado → faltan adyacencias por mala cobertura del dataset.

#### Paso 5: Identificación del TOP

Estrategia robusta:
1. Si el usuario pasa `--id-top`, usarlo (default: 151).
2. Si no, elegir el marker con mayor grado en el grafo y reportar.

Verificar que el marker designado como TOP tiene exactamente 5 vecinos. Si no, error claro.

#### Paso 6: Ordenamiento cíclico del anillo superior

Los 5 vecinos del TOP forman un anillo cíclico (cada uno adyacente a 2 de los otros 4).

Algoritmo:
- Partir desde un vecino arbitrario.
- Seguir el ciclo: el "siguiente" es el vecino que NO es el "anterior".

Resultado: lista ordenada `[sup_0, sup_1, sup_2, sup_3, sup_4]`.

**Dirección del orden (CW vs CCW)**: arbitraria por ahora. Se ajustará en paso 9 al alinear con la geometría 3D real.

#### Paso 7: Ordenamiento del anillo inferior

Los 5 markers restantes forman el cinturón inferior. Cada `inf_i` es adyacente:
- A 2 `sup_*` (vecinos antiprismáticos: el del anillo superior con misma azimut + el de azimut adyacente).
- A 2 `inf_*` (vecinos cíclicos del propio anillo inferior).

Algoritmo:
- Para cada `sup_i`, identificar sus 2 vecinos del cinturón inferior.
- Asignar `inf_i` = el vecino inferior común entre `sup_i` y `sup_{i+1}`.

Resultado: lista `[inf_0, inf_1, inf_2, inf_3, inf_4]` con `inf_i` "debajo" del segmento `sup_i ↔ sup_{i+1}`.

#### Paso 8: Generación de posiciones canónicas

Conocidos `id_top`, `[sup_0..sup_4]`, `[inf_0..inf_4]`, generar la geometría canónica de un dodecaedro regular:

- Centro TOP: `(0, 0, r_in)`, normal `(0, 0, 1)`.
- Centros sup_i: `(sin(θ)·cos(az_i), sin(θ)·sin(az_i), cos(θ))·r_in`, con `az_i = i·72°`.
- Centros inf_i: `(sin(θ)·cos(az_i + 36°), sin(θ)·sin(az_i + 36°), -cos(θ))·r_in`.

Los 4 corners de cada marker se generan con la misma lógica que `construir_cara` (label hacia +Z, c0=TL, c1=TR, c2=BR, c3=BL).

#### Paso 9: Detección de orientación del label

Para cada marker, comparar la pose detectada con la pose canónica. Si el "right" del label no coincide con el "right" canónico, hay una rotación de 0/90/180/270°.

Estrategia:
- Calcular pose promedio de cada marker en frame del dodecaedro (post-estimación de poses del dodecaedro completo).
- Comparar el R_local del marker detectado con el R_local de la posición canónica.
- Si difieren por una rotación de k·90° alrededor del normal → aplicar la rotación residual en los corners canónicos.

(Esto requiere una primera estimación de la pose del dodecaedro completo, lo cual depende de paso 8. Es iterativo, pero converge en 2-3 pasadas).

**Simplificación inicial**: asumir orientación consistente del label (label hacia +Z según convención del proyecto). Si fallan los tests, agregar detección de orientación.

#### Paso 10: Escribir `reference_dodecaedro_real.txt`

Mismo formato que el teórico ideal, con header indicando:
- Que es geometría calibrada al dodecaedro físico.
- Mapeo: `ID físico → posición canónica`.
- Adyacencias detectadas.
- Hash del .npz input.

### Validaciones automáticas

Después de generar el archivo, **verificar**:
- Distancias entre pares calibrados vs distancias teóricas: deberían matchear con < 1 mm.
- Si no, abortar con mensaje claro indicando los pares problemáticos.

## 2. Edge cases y robustez

| Caso | Comportamiento esperado |
|---|---|
| Marker no aparece nunca en el dataset | Reportar y abortar (no se puede inferir su posición). |
| Marker aparece pero nunca con otros (siempre solo) | Reportar warning, posición indeterminada. |
| Hay más de 11 markers detectados | Detector falso-positivo. Reportar y ignorar IDs extra. |
| Hay menos de 11 markers detectados | Insufficient. Pedir captura mejor. |
| El grafo de adyacencias es inconsistente | Reportar pares problemáticos. Sugerir verificar si algún marker se pegó al revés (label rotado 90°). |
| El usuario armó el dodecaedro al revés (TOP donde debería ser BASE) | Detección con `--id-top` debería resolverlo, o intentar ambas opciones. |

## 3. Integración con el pipeline

```
A: Calibración cámara (1 vez)
B: Geometría teórica IDEAL (1 vez) ← solo como referencia, no como input al BA
C: Captura dataset (1 vez por dodecaedro armado)
C.5: Calibración TOPOLÓGICA (1 vez por dodecaedro armado) ← NUEVA
       Input: capturas_calibracion.npz, --id-top (opcional)
       Output: data/reference_dodecaedro_real.txt
D: Bundle adjustment (1 vez por dodecaedro armado)
       Input: capturas_calibracion.npz, data/reference_dodecaedro_real.txt
       Output: data/reference_dodecaedro_calibrado.txt
E: Calibración pivote
F: Tracking en vivo
```

### Cambios en otros scripts

- **`calibrar_rigid_body.py`** (Etapa D): aceptar `--teorico` con default cambiado a `data/reference_dodecaedro_real.txt` (resultado de C.5 en vez del teórico ideal de B).
- **`tracker.py`** (Etapa F): NO cambia. Sigue usando `data/reference_dodecaedro_calibrado.txt` (output de D).
- **`generar_reference_dodecaedro.py`** (Etapa B): queda como referencia para casos donde el dodecaedro está armado siguiendo estrictamente la convención teórica (no recomendado, pero válido como fallback).

## 4. Criterio de éxito

Una vez implementado C.5 y re-corrido el BA:

| Métrica | Criterio |
|---|---|
| RMSE inicial del BA | < 3 px (vs 15.5 px con archivo teórico mal mapeado) |
| RMSE final del BA | ≤ 1 px (idealmente ≤ 0.7 px como iter 1) |
| Status del BA | 1 o 2 (ftol/xtol satisfecho) |
| Desplazamiento por marker después del BA | < 5 mm (vs 28 mm actual) |
| Reproducibilidad | Re-armar un dodecaedro con cualquier orden de IDs → calibración topológica + BA convergen igual |

## 5. Tests pytest planeados

`tests/test_calibrar_topologia.py`:

- **`test_grafo_adyacencias_canonico`**: dodecaedro sintético perfecto, recupera adyacencias correctas (cada cara tiene 5 vecinos).
- **`test_identifica_top`**: detecta correctamente el marker designado como TOP.
- **`test_ordena_anillo_superior_ciclico`**: el orden recuperado es cíclico válido.
- **`test_permutacion_arbitraria_se_recupera`**: dodecaedro sintético con permutación aleatoria de IDs → al ejecutar calibración topológica, las distancias en `reference_dodecaedro_real.txt` matchean las teóricas dentro de 1 mm.
- **`test_marker_faltante_aborta`**: si falta 1 marker en el dataset → error claro.
- **`test_marker_extra_se_ignora`**: detección extra (e.g., ID 216 espuria) → ignorada.

## 6. Próximo paso

Implementar `calibrar_topologia.py` siguiendo este diseño. Después, tests, integración con BA, validación con el dataset real del usuario.
