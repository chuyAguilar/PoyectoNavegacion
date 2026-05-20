# 02 — Inventario de artefactos

**Fase 2 de la auditoría de iteración 2.** Estado a 2026-05-16.

Este documento lista exhaustivamente cada archivo en `codigo/`, `codigo/data/` y `herramientas/`: qué es, quién lo produjo, qué inputs consumió, en qué fecha, y su estado actual (vigente, archivado a histórico, o pendiente de regenerar).

---

## 1. Decisión del 2026-05-16

Al arrancar la segunda vuelta de iter 2 con setup físico intacto (cámara montada, dodecaedro 151–161 armado, stylus ensamblado, marker 0 fijo al phantom), se decidió:

- **Conservar** `camera_calibration_caja_luz.yml` por proceder de PLUS Toolkit (PerkLab, herramienta oficial del ecosistema SlicerIGT). Confianza alta.
- **Regenerar** todos los demás artefactos producidos por código propio para validar reproducibilidad y métricas.
- **Archivar** los artefactos previos en `codigo/historico/iter1_2026-05-16/` y `herramientas/historico/iter1_2026-05-16/` como referencia y comparación.

---

## 2. Inventario en `codigo/`

### Scripts Python (todos vigentes, a auditar en Fase 3)

| Archivo | Tamaño/líneas (aprox) | Etapa | Estado | Notas |
|---|---|---|---|---|
| `generar_reference_dodecaedro.py` | a inspeccionar | B | **Existe** | El mapa de Fase 1 lo daba por perdido — hay que actualizar §6 pto 8 |
| `captura_calibracion.py` | a inspeccionar | C | Vigente | Produce `capturas_calibracion.npz` |
| `calibrar_rigid_body.py` | a inspeccionar | D | Vigente | Bundle adjustment, ancla ID 151 |
| `test_pivote.py` | a inspeccionar | E | Vigente, **prioridad máxima** | Reemplaza PlusServer en pivote |
| `tracker.py` | a inspeccionar | F | Vigente | Pipeline en vivo, multi-marker |

### Configuración

| Archivo | Estado | Notas |
|---|---|---|
| `tracker_config.yaml` | Vigente | Cámara 640×480 MSMF+MJPG · DICT_ARUCO_MIP_36h12 · marker 0 size_mm=60.8 · rigid body Dodecaedro apunta a `data/reference_dodecaedro_calibrado.txt` · OpenIGTLink 18944 · `send_video: false` · filtrado 1-Euro off |
| `.python-version` | Vigente | Python 3.11 |
| `readme.md` | Vigente pero mínimo | Solo activa el venv |

### Artefactos de datos vigentes

| Archivo | Producido por | Estado |
|---|---|---|
| `data/camera_calibration_caja_luz.yml` | PLUS Toolkit (externo) | **Conservado** — único artefacto de confianza heredado de iter 1 |
| `data/recursos/calib_global_shutter_camera__32e4_0234__1280.json` | Calibración alternativa | Conservado como recurso |
| `data/recursos/calib_svpro_1280x960_plus.yml` | Calibración alternativa de PLUS | Conservado como recurso |
| `data/recursos/calibration_pattern_9x6_25mm.pdf` | Patrón usado por PLUS | Conservado como recurso |

### Artefactos archivados a histórico (2026-05-16)

Movidos a `codigo/historico/iter1_2026-05-16/`:

- `data/reference_dodecaedro.txt` → `historico/iter1_2026-05-16/data/`
- `data/reference_dodecaedro_calibrado.txt` → `historico/iter1_2026-05-16/data/`
- `capturas_calibracion.npz` → `historico/iter1_2026-05-16/`
- `poses_pivote_dodecaedro.npy` → `historico/iter1_2026-05-16/`
- `poses_pivot_ippe_1.npy` → `historico/iter1_2026-05-16/` (versión previa, dejada para trazabilidad)
- `StylusTipToDodecaedro.npy` → `historico/iter1_2026-05-16/`
- `StylusTipToDodecaedro.txt` → `historico/iter1_2026-05-16/`

Cada artefacto será regenerado durante la segunda vuelta. Las versiones nuevas se comparan contra las archivadas (ver `historico/iter1_2026-05-16/README.md`).

### Entorno

| Carpeta | Estado |
|---|---|
| `.venv/` | Vigente. Python 3.11, OpenCV `opencv-contrib-python` 4.13.0.92, NumPy 2.4.4, SciPy 1.17.1, pyigtl 0.3.1 |

---

## 3. Inventario en `herramientas/`

Carpeta histórica con archivos `.h5` (matrices 4×4 guardadas como Linear Transform de Slicer). Mezcla iteraciones.

### Vigente

(ninguno — todo lo de iter 1 se archivó o quedó como histórico)

### Archivado a histórico (2026-05-16)

- `StylusTipToDodecaedro.h5` → `historico/iter1_2026-05-16/` (la calibración de pivote cargada en Slicer durante iter 1)

### Restos de iteraciones previas (dejar como están, son contexto histórico)

| Archivo | Origen probable | Acción sugerida |
|---|---|---|
| `pivotLezna.h5` | Iteración con stylus tipo lezna previa al dodecaedro | Dejar; documentar en Fase 5 si se va a depurar |
| `pivot_lezna_2.h5` | Segundo intento del pivote con lezna | Dejar; documentar |
| `STL_Offset.h5` | Offset del STL aplicado en alguna versión | Dejar; documentar |
| `StylusTipToMarker_AVG.h5` | Promedio de varias calibraciones | Dejar; documentar |
| `stl_leznav2_offset.h5` | Offset del STL con lezna v2 | Dejar; documentar |

Comentario: en Fase 5 (mejoras), conviene decidir si estos `.h5` se mueven a `herramientas/historico/iteraciones_pre_dodecaedro/` para limpiar el directorio.

---

## 4. Inventario relevante en `documentos/`

| Archivo | Estado |
|---|---|
| `auditoria_iter2/01_mapa_del_flujo.md` | Vigente. Pendiente: actualizar §6 pto 8 (script B sí existe) y agregar la jerarquía final de Slicer en Etapa I con orden de operaciones |
| `auditoria_iter2/01_mapa_del_flujo.png` / `.svg` / `_HD.png` | Vigentes, renderizados del Mermaid |
| `auditoria_iter2/02_inventario_artefactos.md` | **Este documento** |
| `tecnicos/Documento_Tecnico_Navegacion_Quirurgica.md` | Pendiente de revisar — ¿qué contiene y se solapa con el mapa? |
| `tecnicos/Navegacion_Quirurgica_OpenSource.docx` | Pendiente de revisar |

---

## 5. Inventario en raíz del proyecto

| Archivo | Estado |
|---|---|
| `CLAUDE.md` | Vigente. Instrucciones para Claude — alineado con esta auditoría |
| `PROJECT_BRIEF.md` | Vigente. Para crear el Project en Cowork |

---

## 6. Riesgos detectados en este inventario

1. **El mapa de Fase 1 está desactualizado** sobre la existencia de `generar_reference_dodecaedro.py`. Cuando completemos su auditoría, hay que actualizar §6 pto 8 del mapa.
2. **`StylusTipToDodecaedro.h5` no es regenerable solo por código.** Hace falta paso manual en Slicer. En Fase 5 evaluar automatizar la escritura del `.h5` desde Python (h5py + formato Slicer).
3. **Mezcla de iteraciones en `herramientas/`.** Los `.h5` viejos de iteraciones con lezna confunden el directorio. Limpiar al final.
4. **Sin `requirements.txt` / `pyproject.toml` / `uv.lock` visible.** La reproducibilidad del entorno depende del `.venv/` actual. En Fase 5 generar un `requirements.txt` congelado o equivalente.
5. **`tracker_config.yaml` referencia `data/reference_dodecaedro_calibrado.txt`** — archivo que ahora está archivado. Hay que regenerarlo antes de poder ejecutar `tracker.py` o `test_pivote.py` para evitar `FileNotFoundError`.

---

## 7. Próximo paso

Fase 3 — Auditoría por script. Orden propuesto siguiendo el pipeline de generación (alternativa al orden del mapa original):

1. **`generar_reference_dodecaedro.py`** → regenera `data/reference_dodecaedro.txt`.
2. **`captura_calibracion.py`** → regenera `capturas_calibracion.npz`.
3. **`calibrar_rigid_body.py`** → regenera `data/reference_dodecaedro_calibrado.txt`.
4. **`test_pivote.py`** → regenera `StylusTipToDodecaedro.npy/.txt`. *(prioridad máxima de iter 2)*
5. **`tracker.py`** → ejecuta el pipeline en vivo a Slicer.

Cada auditoría tendrá su propio documento: `03a_auditoria_generar_reference_dodecaedro.md`, `03b_auditoria_captura_calibracion.md`, etc.
