# Estado de pausa — sesión iter 2 (2026-05-19)

> **ACTUALIZACIÓN 2026-05-19 (tarde)**: la pausa quedó RESUELTA. Bug aislado en `construir_jac_sparsity`. Default actual del script (sin sparse, sin x_scale) converge correctamente sobre dataset iter 1, idéntico a `ba_test_minimal.py` (Cost 14771 → 8235 en 19 iter, trayectoria idéntica). Comando recomendado: `python calibrar_rigid_body.py --max-frames 500 --max-nfev 3000`. Ver `project_etapa_d_ba_atorado.md` (memory) para detalles. El resto del documento se conserva como histórico del diagnóstico.

## Dónde estamos atorados

**Etapa D (Bundle Adjustment)** no logra convergencia con el script refactorizado, ni con el dataset nuevo de iter 2 ni con el dataset histórico de iter 1 (que originalmente convergía a RMSE 0.61 px).

## Lo que SABEMOS con certeza (evidencia)

1. **El dodecaedro físico es el mismo** que en iter 1 (confirmado por el usuario).
2. **La calibración intrínseca K es bit-a-bit idéntica** entre iter 1 e iter 2.
3. **La topología detectada por `calibrar_topologia.py`** es idéntica en ambos datasets: TOP=151, sup=[152..156], inf=[158, 159, 160, 161, 157]. Es decir, el cubo siempre estuvo bien armado, simplemente con etiquetado distinto al teorico antiguo.
4. **Iter 1 ORIGINAL convergía** con script propio, RMSE 0.61 px.
5. **Mi script refactorizado NO converge** sobre el mismo dataset de iter 1 (reducción del 0.6% al 27% según configuración, pero nunca llega cerca de 0.61 px).

## Hipótesis descartadas (con evidencia)

- ❌ Parametrización rígida vs libre — ambas dan resultados similares.
- ❌ Topología del cubo distinta — es idéntica en iter 1 e iter 2.
- ❌ Calibración intrínseca rota — bit-a-bit igual a iter 1.
- ❌ Dataset de iter 2 problemático — el mismo problema aparece sobre iter 1 dataset.
- ❌ Cantidad de frames — con 200, 500, o 2494 frames el comportamiento es similar.
- ❌ `jac_sparsity` solo — sin `x_scale` el optimizador no avanza pero las distancias son razonables.

## Estado actual del script

`calibrar_rigid_body.py` actualmente tiene (520 líneas):
- Parametrización libre (12 floats por marker).
- `jac_sparsity` activado por defecto (acelera, no rompe convergencia).
- `x_scale='jac'` **DESACTIVADO** por default (se confirmó que con huber loss empuja al optimizador a un mínimo local con desplazamientos de 25 mm).
- Flags: `--no-sparse`, `--x-scale-jac` (experimental), `--max-frames` para submuestreo, otros.

Estado: el optimizador no avanza eficientemente sin x_scale (0.6% reducción en 200 iteraciones).

## Hipótesis NO probada (siguiente sesión)

**Cambio de versión de SciPy entre iter 1 e iter 2 podría haber alterado el comportamiento de `least_squares(method='trf', loss='huber')`**.

Versiones a investigar:
- Iter 1 (cuándo se hizo): SciPy ≤ ¿1.13? (no confirmado).
- Iter 2 (ahora): SciPy 1.17.1.

Cambios relevantes entre versiones:
- SciPy 1.16/1.17 refactoró internos de `scipy.optimize`.
- Posibles cambios en cómo se maneja huber loss con TRF method.

## Recomendación para la próxima sesión

**Plan A** (más probable que funcione): revertir `calibrar_rigid_body.py` al estilo más cercano a iter 1, escribiéndolo desde cero como un script minimal. Conservar solo lo crítico:
- Validación de prerrequisitos
- Logging estructurado
- Lo demás idéntico a iter 1 (sin sparse, sin x_scale, sin metadata extensiva, sin RMSE por marker).

**Plan B** (si A falla): investigar versión de SciPy. Probar `pip install scipy==1.13` en el venv y ver si converge.

**Plan C** (si B falla): cambiar a otra librería de BA (e.g., `theseus`, `g2o-python`) o implementar BA con Levenberg-Marquardt manual.

## Archivos relevantes al retomar

- `codigo/calibrar_rigid_body.py` (520 líneas, BA refactorizado roto).
- `codigo/historico/iter1_2026-05-16/capturas_calibracion.npz` (dataset iter 1 que convergía).
- `codigo/capturas_calibracion.npz` (dataset iter 2 nuevo, 2494 frames).
- `codigo/calibrar_topologia.py` (herramienta opcional, validada que funciona).
- `documentos/auditoria_iter2/03c_auditoria_calibrar_rigid_body.md` (documento de auditoría).
- `documentos/auditoria_iter2/03b2_auditoria_calibrar_topologia.md` (calibración topológica como opcional).
- `codigo/historico/iter2_callejones_sin_salida/` (callejones sin salida documentados).

## Lo positivo de esta sesión

Aunque el BA quedó roto, esta sesión produjo cosas valiosas:

- ✅ Etapa B (geometría teórica): auditada, mejorada, con tests pytest, parametrizable por CLI. Estado: production-ready.
- ✅ Etapa C (captura): auditada, mejorada con metadata extensiva, validación de prereqs, widget de cobertura en tiempo real. Estado: production-ready.
- ✅ `calibrar_topologia.py`: herramienta opcional funcionando que infiere topología de adyacencias del dodecaedro.
- ✅ Suite de tests pytest creciendo (55+ tests).
- ✅ Comparación estadística de datasets iter 1 vs iter 2.
- ✅ Documentación de auditoría exhaustiva.

Lo único que quedó roto: el refactor del BA. Es una pieza acotada que se puede revertir con esfuerzo medible.
