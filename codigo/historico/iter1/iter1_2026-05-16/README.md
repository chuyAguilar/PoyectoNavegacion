# Histórico — Artefactos iteración 1 (snapshot 2026-05-16)

Artefactos generados durante iteración 1 del proyecto de navegación quirúrgica, archivados al inicio de la **segunda vuelta auditada** de iteración 2 (2026-05-16).

## Por qué están acá

- Iter 2 se planteó como auditoría y verificación de correctness antes de seguir iterando.
- La decisión del 2026-05-16 fue **regenerar todos los artefactos producidos por código propio** (geometrías, captura BA, calibración de pivote) para validar que los scripts son reproducibles.
- Estos archivos quedan guardados como **referencia histórica** y para comparar contra los nuevos generados en iter 2 (debe haber consistencia o desviaciones explicables).

## Lo que NO está acá (y por qué)

- `codigo/data/camera_calibration_caja_luz.yml` — **se conserva en su ubicación original**, no se regenera. Fue calibrada con PLUS Toolkit (PerkLab), herramienta oficial del ecosistema SlicerIGT, RMSE 0.479 px. Se considera artefacto de confianza.

## Inventario archivado

| Archivo | Etapa origen | Producido por | Métrica reportada (iter 1) |
|---|---|---|---|
| `data/reference_dodecaedro.txt` | B | `generar_reference_dodecaedro.py` | Geometría teórica, IDs 151–161 |
| `data/reference_dodecaedro_calibrado.txt` | D | `calibrar_rigid_body.py` | RMSE BA 0.61 px |
| `capturas_calibracion.npz` | C | `captura_calibracion.py` | ~1760 frames válidos |
| `poses_pivote_dodecaedro.npy` | E | `test_pivote.py` | N poses del pivote |
| `poses_pivot_ippe_1.npy` | E (versión previa) | `test_pivote.py` (versión anterior) | — |
| `StylusTipToDodecaedro.npy` | E | `test_pivote.py` | Offset ≈ [0.315, -0.258, -88.617] mm |
| `StylusTipToDodecaedro.txt` | E | `test_pivote.py` | Std [1.68, 1.45, 0.38] mm |
| `herramientas/historico/iter1_2026-05-16/StylusTipToDodecaedro.h5` | E (manual en Slicer) | Cargado en Slicer, guardado como Linear Transform | — |

## Comparación esperada contra iter 2

Cuando regeneremos cada artefacto, vamos a comparar:
- **`reference_dodecaedro.txt`**: debe ser bit-exact si los parámetros del generador no cambiaron.
- **`reference_dodecaedro_calibrado.txt`**: las posiciones de los marcadores deben quedar a ≤1–2 mm de las de iter 1 (depende del nuevo dataset).
- **`StylusTipToDodecaedro.*`**: el offset esperado es del orden de –88 mm en Z; cambios de >5 mm respecto a iter 1 son sospechosos y hay que investigar.
