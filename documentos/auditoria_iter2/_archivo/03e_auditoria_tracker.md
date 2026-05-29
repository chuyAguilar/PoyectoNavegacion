# 03e — Auditoría de `tracker.py`

**Fase 3 de la auditoría iter 2 · Etapa F (tracking en vivo).** Fecha: 2026-05-20.

## Resumen ejecutivo

- ✅ **Matemática correcta**: `solvePnP` multi-marker con `IPPE_SQUARE` (N=1) o `ITERATIVE+RefineLM` (N≥2). API verificada en auditoría 03d.
- ✅ **Detección robusta**: ArUco con `CORNER_REFINE_SUBPIX`, API nueva `ArucoDetector` con fallback a vieja.
- ✅ **Threading-safe**: pyigtl maneja servidores TCP en background, el main thread solo encola mensajes.
- ✅ **Cierre limpio**: `try/finally` libera cámara, ventanas, sockets.
- ⚠️ **Filtro 1-Euro sólo en posición** (tvec), no rotación. El jitter rotacional (que es el dominante por el offset 91 mm del stylus) NO se filtra. Ver §3.
- ⚠️ **`min_markers: 3` como filtro de calidad** agregado 2026-05-20 → mejora sustancial del jitter. Ver §2.
- 📋 **Mejoras propuestas** (no bloquean uso): filtrar rotación con SLERP, validar prerrequisitos, useExtrinsicGuess, verbose toggleable.

**Veredicto**: el script está en producción y funciona. Las mejoras propuestas son polish.

---

## 1. Estructura del script

```
main()
├── Carga config YAML + calibración intrínseca (K, dist)
├── Configura diccionario ArUco + detector (API nueva o vieja)
├── Carga markers individuales (lista por config)
├── Carga rigid bodies (uno o más, cada uno con su geometry_file)
├── Inicializa filtros 1-Euro (si filtering.enabled)
├── Abre servidores OpenIGTLink (transforms en :18944, opcional video :18945)
├── Abre cámara (backend + FOURCC + resolución)
└── Loop principal:
    ├── cap.read() → frame BGR
    ├── cv2.aruco.detectMarkers() → corners + ids
    ├── Para cada rigid body:
    │     ├── Filtra markers detectados que pertenecen al rigid body
    │     ├── Si N_marcadores < min_markers: descartar (skip envío)
    │     ├── estimar_pose_rigid_body() → un solvePnP con todos los puntos
    │     ├── Aplicar filtro 1-Euro a tvec (si habilitado)
    │     ├── Construir matriz 4x4
    │     └── Enviar TransformMessage por OpenIGTLink
    ├── Para cada marker individual (no en rigid body):
    │     ├── estimar_pose_individual() con SOLVEPNP_IPPE_SQUARE
    │     ├── Filtro 1-Euro a tvec
    │     └── Enviar TransformMessage
    ├── Opcional: enviar frame de video por OpenIGTLink
    ├── Mostrar ventana de debug con detecciones + ejes
    └── Imprimir FPS cada 5s
```

## 2. Mejora aplicada 2026-05-20: filtro de calidad min_markers

**Problema observado**: jitter visible en `StylusTip` al replicar iter 1. Captura mostraba "Dodecaedro: 2 markers" frecuentemente.

**Causa**: con N=1 marker, IPPE_SQUARE tiene ambigüedad planar (2 soluciones casi simétricas, el optimizer "salta" entre ellas frame-a-frame). Con N=2, la rotación alrededor del eje común a las dos caras tiene error grande. Como el StylusTip está a 91 mm del centro del dodecaedro, **errores rotacionales se amplifican geométricamente** (1° de error → 1.6 mm de jitter en la punta).

**Fix**: parámetro `rigid_bodies_quality.min_markers` (default 3) en `tracker_config.yaml`. Si la detección visible tiene menos markers que ese umbral, el frame se descarta para ese rigid body. Marker individual no se ve afectado.

**Resultado** (validado por usuario): jitter notablemente reducido sin pérdida significativa de tasa de actualización.

## 3. Filtrado 1-Euro: limitaciones

El `OneEuroFilter` actual filtra **sólo `tvec`** (posición), no `rvec` (orientación). Para un rigid body como el dodecaedro montado en un stylus, la fuente principal de jitter visual es **la rotación amplificada por el offset del tip**:

- 0.5° de error rotacional en pose del dodecaedro → ~0.8 mm en StylusTip a 91 mm.
- 1.0° → ~1.6 mm.
- 2.0° → ~3.2 mm.

El filtro de tvec ayuda pero el efecto principal queda sin filtrar. **Mejora propuesta** (M3 abajo): filtrar también la orientación con SLERP o low-pass exponencial sobre rvec.

Por ahora, el filtro `min_markers` + 1-Euro sobre tvec es suficiente — usuario validó.

## 4. Auditoría de APIs

| API | Uso | Verdict |
|---|---|---|
| `cv2.aruco.ArucoDetector + CORNER_REFINE_SUBPIX` | API nueva ≥4.7, con fallback | ✓ Correcto |
| `cv2.solvePnP(SOLVEPNP_IPPE_SQUARE)` | N=1 marker o individual | ✓ Correcto (exactamente 4 ptos coplanares) |
| `cv2.solvePnP(SOLVEPNP_ITERATIVE) + solvePnPRefineLM` | N≥2 markers | ✓ Patrón canónico |
| `cv2.Rodrigues + matriz homogénea 4x4` | Construir transform para OpenIGTLink | ✓ Correcto |
| `pyigtl.OpenIGTLinkServer + TransformMessage` | Comunicación con Slicer | ✓ Patrón estándar SlicerIGT |

Sin red flags. Configuración cámara MSMF+MJPG coherente con iter 1 (28-30 FPS).

## 5. Hallazgos

### ✅ Fortalezas
1. Matemática validada (compartida con `test_pivote.py`).
2. Detección robusta con subpíxel.
3. API nueva con fallback automático.
4. Filtro 1-Euro implementación clásica correcta.
5. Cierre limpio con `try/finally`.
6. Visualización con `drawFrameAxes` útil para debug.
7. Configurable: dictionary, IDs, tamaños, filtros, min_markers — todo por YAML.

### ⚠️ Mejoras propuestas (priorizadas)

**Alta prioridad**:
- **M1**: Validación de prerrequisitos al arrancar (existencia de config, calibración, geometry files).
- **M2**: Verbose toggleable con flag CLI (`--verbose` o `-v`) en lugar de solo config.

**Media prioridad**:
- **M3**: Filtrar también orientación (rvec) con SLERP o low-pass exponencial. Mayor impacto en jitter visual del stylus.
- **M4**: `useExtrinsicGuess=True` con pose previa para acelerar y estabilizar `solvePnP` frame-a-frame.
- **M5**: Logging de métricas de tracking (drift, std rotacional) cada N segundos.

**Baja prioridad**:
- **M6**: Extraer código común con `test_pivote.py` a `dodecaedro_core.py` (mencionado en auditoría inicial).
- **M7**: Detectar y warning si los markers detectados NO pertenecen al diccionario configurado.

### ❌ Problemas reales encontrados

**Ninguno bloquea uso**. El script está en producción exitosa post-fix de `min_markers`.

## 6. Comando recomendado y métricas esperadas

```powershell
python tracker.py --config tracker_config.yaml
```

**Métricas esperadas con config actual** (iter 2, dodecaedro 11 markers, ID 0 ósea):
- FPS sostenido: 28-30.
- Markers por pose del dodecaedro: 3-5 cuando la captura es buena.
- Latencia tracker→Slicer: <50ms (TCP local).
- Jitter visual del StylusTip: <2 mm en condiciones estables.

**Si FPS cae <20**: revisar `send_video: false` en config (debe estar false), backend (MSMF), FOURCC (MJPG).

**Si jitter aumenta**: subir `min_markers` a 4 (más estricto). O activar M3 (filtrar rotación).

## 7. Estado de la auditoría

**Etapa F queda CERRADA** con esta auditoría. El tracker funciona correctamente con las mejoras de 2026-05-20. Las mejoras M1-M7 son polish y no bloquean uso clínico (en el alcance del proyecto MIRAI).

Próximo: documentación de replicabilidad para nuevos dodecaedros (`05_reproducir_desde_cero.md`).
