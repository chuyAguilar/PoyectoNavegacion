# BACKLOG — lo que falta

Lo que se decidió no hacer ahora, con su porqué. Prioridades: **alta**, puede dar un resultado equivocado o impide usar el sistema; **media**, mejora clara sin riesgo; **baja**, espera datos o solo si estorba. Lo cerrado pasa a «Cerrados» con la fecha y qué lo cerró. Quien toca una entrada actualiza el índice en el mismo cambio.

## Índice

| # | Qué | Prioridad | Destino |
|---|---|---|---|
| B01 | Scripts legacy y de diagnóstico sueltos en `iter4\` | Media | spec 001 |
| B02 | La suite está rota y no hay comprobación de «no cambió» | Alta | spec 001 |
| B03 | La calibración de punta vigente no tiene respaldo | Alta | spec 001 |
| B04 | Docs viejas o duplicadas en la raíz (`PROJECT_BRIEF.md`, `briefs/`) | Media | spec 001 |
| B05 | Ruido local y archivos muertos en `iter4\data\` | Baja | spec 001 |
| B06 | Rutas viejas (`Dr.Milton`, `C:\dev\PoyectoNavegacion`) fuera de `docs\` | Media | spec 001 |
| B07 | Marker0 rígido y corto (brazo de palanca) | Alta | — |
| B08 | Runbook para el contexto Femto | Media | — |
| B09 | FPS ~16–17 con la Femto en modo RGB | Media | — |
| B10 | Verificaciones en vivo pendientes del brief-02 | Media | — |
| B11 | Binarios pesados versionados (`.ply`, PDF, PPTX, `.h5`) | Media | — |
| B12 | Detección de 3–4 markers por vista | Baja | — |
| B13 | `.git` sin compactar (691 MB sueltos) | Baja | — |
| B14 | Stylus impreso nuevo (IDs 181–191) | Baja | — |
| B15 | Reintegrar el depth al BA | Baja | — |
| B16 | Rama de registro por superficie (en pausa) | Baja | — |

## Abiertos

### B01 · Scripts legacy y de diagnóstico sueltos en `iter4\`
- **Qué:** sin referencias en la GUI ni en docs: `hello_femtobolt`, `leer_calibracion_femtobolt`, `medir_sigma_depth`, `test_backends`, `test_distancia_conocida`, `test_distancia_regla`, `test_jitter_tracking`. Con pocas: `test_pivote` (legacy, ADR-010), `test_alineacion_d2c`, `calibrar_topologia`, `limpiar_captura_fantasmas`, `test_deteccion_marker`. Los `test_*.py` de `iter4\` no son de pytest, y confunden.
- **Por qué queda:** ordenar exige comprobar antes que nada los importe; va con su plan.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** moverlos (no borrarlos) a `codigo\historico\iter4_diagnosticos\`, comprobando con grep que nadie los importa ni los nombra.
- **Prioridad:** media.

### B02 · La suite está rota y no hay comprobación de «no cambió»
- **Qué:** los 3 archivos de `codigo\tests\` fallan al importar (`No module named 'calibrar_rigid_body'`): buscan en `codigo\` y el código vive en `codigo\iter4\`. Hoy no corre ninguna prueba. Tampoco hay replay sin cámara.
- **Por qué queda:** sin suite no se puede verificar ningún cambio (principio 3).
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** repuntar los tests a `iter4\`; sumar `py_compile` de `iter4\` y `gui\`; un replay que corra la pose sobre un dataset grabado (p.ej. `captura_ba.npz`) y compare con una referencia guardada.
- **Prioridad:** alta.

### B03 · La calibración de punta vigente no tiene respaldo
- **Qué:** `StylusTipToDodecaedro_femto_dock.npy/.txt` está fuera de git (`.gitignore`: las puntas son por equipo). Si se pierde el disco, se pierde la punta vigente.
- **Por qué queda:** decidir si se versiona como excepción (igual que la geometría v2) o se respalda fuera.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** la decisión del autor; si se versiona, una excepción `!` en `.gitignore` y una nota en un ADR.
- **Prioridad:** alta.

### B04 · Docs viejas o duplicadas en la raíz
- **Qué:** `PROJECT_BRIEF.md` (2026-06-15, describe iter 4 temprana y el stylus 170–180; lo cubren los MVD) y `briefs/` (lo reemplazan los `specs/`, ADR-020).
- **Por qué queda:** van a `docs/history/` como copia literal, en el spec de limpieza.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** `git mv` a `docs/history/`, y quitar las referencias que queden.
- **Prioridad:** media.

### B05 · Ruido local y archivos muertos en `iter4\data\`
- **Qué:** `codigo\pytest-cache-files-xrzp8j4c\`, `reference_dodecaedro_nuevo_calibrado.txt` (0 bytes, del BA que no convergió el 2026-08-13), y geometrías o configs sin referencias: `reference_dodecaedro_doctor/_v2_fix/_v2_real.txt`, `reference_stylus_impreso_calibrado.txt`, `tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml` (1 referencia cada una).
- **Por qué queda:** un archivo de 0 bytes con nombre de calibrado puede tomarse como geometría válida.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** borrar el ruido local; mover lo muerto a `iter4\data\historico\`.
- **Prioridad:** baja.

### B06 · Rutas viejas fuera de `docs\`
- **Qué:** `documentos/MANUAL_simplificado.md` (`C:\dev\PoyectoNavegacion\codigo`), `PROJECT_BRIEF.md` y otros manuales nombran rutas que ya no existen.
- **Por qué queda:** se corrige junto con la limpieza.
- **De dónde:** `docs/CONTEXT.md` §6; paso 0 del método, 2026-10-19.
- **Qué haría falta:** grep de `Dr.Milton` y `C:\dev\PoyectoNavegacion` y corregir a `C:\Dev\OrtoMeta\PoyectoNavegacion`.
- **Prioridad:** media.

### B07 · Marker0 rígido y corto
- **Qué:** el Marker0 en una varilla de ~21 cm convierte un giro de 12° en 45 mm de desfase del hueso.
- **Por qué queda:** es montaje físico, no código.
- **De dónde:** ADR-013; `docs/CONTEXT.md` §6.
- **Qué haría falta:** un soporte rígido pegado al objeto (`stl/BaseMarcador/`) y medir el RMS antes y después.
- **Prioridad:** alta (da resultados equivocados también en paired-point).

### B08 · Runbook para el contexto Femto
- **Qué:** `MANUAL_simplificado.md` opera el contexto doctor; no hay uno para `tracker_config.yaml`.
- **Por qué queda:** no bloquea, porque el panel cubre buena parte.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** un runbook equivalente con Marker0 de 80 mm.
- **Prioridad:** media.

### B09 · FPS ~16–17 con la Femto en modo RGB
- **Qué:** el backend habilita depth + align aunque solo se use el RGB.
- **Por qué queda:** toca `camera_backend.py`, cerca de la cadena (principio 6).
- **De dónde:** `docs/CONTEXT.md` §6, observado en vivo el 2026-08-13.
- **Qué haría falta:** no abrir el stream de depth en modo solo RGB; medir FPS antes y después.
- **Prioridad:** media.

### B10 · Verificaciones en vivo pendientes del brief-02
- **Qué:** la captura del asistente con IDs nuevos, `calibrar_camara.py` interactivo y la calibración de punta por dock desde el panel.
- **Por qué queda:** necesita hardware (y la placa dock física).
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** una sesión con cámara; reportar números.
- **Prioridad:** media.

### B11 · Binarios pesados versionados
- **Qué:** `femto_pruebas/nubes/*.ply` (~250 MB), `documentos/referencias/*.pdf` y `documentos/slicerigt_curso/*.pptx` (~25 MB), `herramientas/*.h5` (pivotes legacy).
- **Por qué queda:** son evidencia de la rama en pausa; el autor decide.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** decidir si salen de git (`git rm --cached` + `.gitignore`) o se quedan.
- **Prioridad:** media.

### B12 · Detección de 3–4 markers por vista
- **Qué:** la referencia histórica es 5–6.
- **Por qué queda:** espera una sesión que mida distancia, ángulo y luz antes de tocar el detector.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** medir markers por vista a 50–70 cm con luz controlada.
- **Prioridad:** baja.

### B13 · `.git` sin compactar
- **Qué:** 691 MB en 1214 objetos sueltos, 0 packs y un temporal basura.
- **Por qué queda:** no da resultados equivocados; solo pesa.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** que el autor corra `git gc` desde PowerShell.
- **Prioridad:** baja.

### B14 · Stylus impreso nuevo (IDs 181–191)
- **Qué:** su geometría CAD es buena, pero falta pose robusta con rechazo de outliers y `marker_mm 15.7`; su BA se atora.
- **Por qué queda:** no urgente.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** retomar si se cambia de stylus.
- **Prioridad:** baja.

### B15 · Reintegrar el depth al BA
- **Qué:** el BA corre solo 2D por el bias residual del depth fuera de la caja.
- **Por qué queda:** espera resolver el bias (ADR-007, ADR-008).
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** medir y corregir el bias de −10 mm.
- **Prioridad:** baja.

### B16 · Rama de registro por superficie
- **Qué:** `femto_pruebas/` validado a 1.76 mm, con dos problemas abiertos: el brazo de palanca (B07) y la ambigüedad de deslizamiento en la columna.
- **Por qué queda:** en pausa por ADR-014.
- **De dónde:** ADR-012, ADR-014.
- **Qué haría falta:** el banco rígido con cubo distintivo (`stl/BaseMarcador/`).
- **Prioridad:** baja.

## Cerrados

_Ninguno todavía._
