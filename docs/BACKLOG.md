# BACKLOG — lo que falta

Lo que se decidió no hacer ahora, con su porqué. Prioridades: **alta**, puede dar un resultado equivocado o impide usar el sistema; **media**, mejora clara sin riesgo; **baja**, espera datos o solo si estorba. Lo cerrado pasa a «Cerrados» con la fecha y qué lo cerró. Quien toca una entrada actualiza el índice en el mismo cambio.

## Índice

| # | Qué | Prioridad | Destino |
|---|---|---|---|
| B04 | Docs viejas o duplicadas en la raíz (`PROJECT_BRIEF.md`, `briefs/`) | Media | spec 001 |
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
| B17 | 22 pruebas desfasadas en `xfail(strict=True)` | Media | — |
| B18 | El filtro 1-Euro no tiene replay | Media | — |
| B19 | `validar_prerrequisitos` deja un calibrado vacío | Alta | — |
| B20 | Slicer carga la punta por fecha | Alta | — |
| B21 | `opencv-python` frente a `opencv-contrib-python` | Baja | — |
| B22 | Secuencias de escape inválidas en docstrings de `iter4\` | Baja | — |

## Abiertos

### B04 · Docs viejas o duplicadas en la raíz
- **Qué:** `PROJECT_BRIEF.md` (2026-06-15, describe iter 4 temprana y el stylus 170–180; lo cubren los MVD) y `briefs/` (lo reemplazan los `specs/`, ADR-020).
- **Por qué queda:** van a `docs/history/` como copia literal, en el spec de limpieza.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** `git mv` a `docs/history/`, y quitar las referencias que queden.
- **Prioridad:** media.

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
- **Qué haría falta:** retomar si se cambia de stylus. Su config (`tracker_config_stylus_impreso.yaml`) y su geometría calibrada están en `iter4\data\historico\` desde la fase 3 · movimientos de la meta 001 (2026-10-19): para usarlo, devolver el config a `iter4\` (el panel solo ve `iter4\tracker_config*.yaml`) y revisar sus rutas relativas.
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

### B17 · 22 pruebas desfasadas en `xfail(strict=True)`
- **Qué:** al repuntar la suite a `iter4\`, 22 de las 70 pruebas de los 3 archivos de mayo fallan porque el código cambió después (el plan estimó 11). Por familia: 7 esperan los IDs 151–161 y hoy son 170–180 (`reference_dodecaedro.txt` y los defaults de `generar_reference_dodecaedro.py`: `test_cargar_referencia_archivo_real`, `test_cargar_rb_ids_archivo_real`, `test_ids_default_son_iter1`, `test_distancia_top_cinturones_uniforme`, `test_adyacencia_antiprismatica`, `test_frame_right_handed_top`, `test_iter2_ids_1_11`); 1 compara con el histórico de iter 1 (`test_matches_historico_iter1`); 8 del BA de `calibrar_rigid_body.py`, que pasó a parametrización rígida y a pedir `use_depth`, `sigma_2d` y `sigma_3d` (`test_parametrizar_reconstruir_round_trip`, las 3 de `construir_jac_sparsity`, las 2 de `calcular_residuos`, `test_rmse_por_marker_agrupa_correctamente`, `test_ba_recupera_geometria_perturbada`); y 6 de `captura_calibracion.py`: `cargar_calibracion` (2, vive en `tracker.py`), `fourcc_int_a_str` (1, ya no existe), la firma nueva de `construir_metadata` (1), `resolver_geometry_path` relativo al CWD (1, `CONTEXT.md` §4.14) y `validar_prerrequisitos`, que ya no comprueba el archivo de intrínsecos (1).
- **Por qué queda:** por decisión del autor (`clarify.md` P1 = b), la fase 1 las marca sin reescribirlas. Lo que vigilaban hoy no se vigila; en particular, el núcleo del BA queda casi sin pruebas.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo, P1; fase 1 · suite y replay, 2026-10-19.
- **Qué haría falta:** por cada una, caracterizarla (que espere lo que el código hace hoy) o borrarla. La de los intrínsecos exige antes decidir si es a propósito (la Femto usa los de fábrica) o hay que restaurar el fallo fuerte (principio 7).
- **Prioridad:** media (por la de los intrínsecos y las 8 del BA no es baja).

### B18 · El filtro 1-Euro no tiene replay
- **Qué:** el filtrado de posición y de cuaternión está dentro del lazo de `tracker.main()`; el replay de la suite cubre solo `estimar_pose_rigid_body` y la regla de `min_markers`.
- **Por qué queda:** cubrirlo exige sacar el filtrado a una función de `tracker.py`, que es la cadena (principio 6).
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** extraer el filtrado a una función sin cambiar su resultado, con replay antes y después, y sumarlo al replay.
- **Prioridad:** media.

### B19 · `validar_prerrequisitos` deja un calibrado vacío
- **Qué:** en `calibrar_rigid_body.py` y `captura_calibracion.py` abre la salida en modo `"ab"` antes de correr para comprobar que se puede escribir; si el proceso falla después, queda un archivo de 0 bytes con nombre válido (el origen del `reference_dodecaedro_nuevo_calibrado.txt` de B05).
- **Por qué queda:** la meta 001 no toca la lógica de los scripts activos.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** comprobar la carpeta sin crear el archivo y escribir solo al final.
- **Prioridad:** alta (un calibrado vacío con nombre válido puede tomarse por bueno).

### B20 · Slicer carga la punta por fecha
- **Qué:** el snippet de `documentos/MANUAL_simplificado.md` §4.2 carga el `StylusTipToDodecaedro*.npy` más reciente por fecha de `iter4\data\`; un `git pull`, una copia o un movimiento cambian cuál, sin aviso en Slicer (`estado.py` sí avisa).
- **Por qué queda:** toca lo que se carga en Slicer: necesita verificación en vivo.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** nombrar la punta explícita en el snippet y mover las puntas viejas (`StylusTipToDodecaedro.npy`, `_2`, `_divot`, `_viejo_dock`, del dodecaedro viejo) a `data\historico\`.
- **Prioridad:** alta.

### B21 · `opencv-python` frente a `opencv-contrib-python`
- **Qué:** el venv y `requirements.txt` tienen `opencv-python` 4.11; `CONTEXT.md` §3 dice contrib.
- **Por qué queda:** no afecta a nada de hoy.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** alinear el texto, o el paquete si algo de contrib hiciera falta.
- **Prioridad:** baja.

### B22 · Secuencias de escape inválidas en docstrings de `iter4\`
- **Qué:** 14 scripts de `iter4\` y `gui\` (rutas Windows en el docstring, p.ej. `\)`) dan `DeprecationWarning: invalid escape sequence` al compilar; eran los 14 avisos de la suite. Desde la fase 3 · movimientos de la meta 001 (2026-10-19), 6 de ellos están en `codigo\historico\iter4_diagnosticos\` y quedan 8 avisos (`calibrar_camara`, `calibrar_tip_divot`, `captura_calibracion`, `identificar_ids`, `limpiar_captura_fantasmas`, `gui\ba_monitor`, `gui\estado`, `gui\panel`). En Python 3.12+ pasa a `SyntaxWarning`.
- **Por qué queda:** con Python 3.11.9 no cambia nada; corregirlo toca scripts activos.
- **De dónde:** fase 1 · suite y replay de la meta 001, 2026-10-19.
- **Qué haría falta:** docstrings crudos (`r"""`) o barras dobles, al tocar cada script por otra razón o antes de subir de Python.
- **Prioridad:** baja.

## Cerrados

### B01 · Scripts legacy y de diagnóstico sueltos en `iter4\`
- **Qué era:** 10 scripts de diagnóstico y legacy en `iter4\` que nadie importaba ni nombraba; los `test_*.py` no eran de pytest y confundían.
- **Cerrado:** 2026-10-19, por la fase 3 · movimientos de la meta 001 · limpieza y orden del repo: `git mv` (renombres, sin tocar contenido) de `hello_femtobolt`, `leer_calibracion_femtobolt`, `medir_sigma_depth`, `test_backends`, `test_distancia_conocida`, `test_distancia_regla`, `test_jitter_tracking`, `test_pivote`, `test_alineacion_d2c` y `test_deteccion_marker` a `codigo\historico\iter4_diagnosticos\`, con su `README.md`. Se quedan en `iter4\` `calibrar_topologia` y `limpiar_captura_fantasmas` (pasos de la GUIA y de los manuales). El docstring de `calibrar_rigid_body.py` y `codigo/readme.md` nombran la ruta nueva; `PROJECT_BRIEF.md` (va a `docs/history/` en la fase 4) y el ADR-010 conservan la vieja.

### B05 · Ruido local y archivos muertos en `iter4\data\`
- **Qué era:** ruido local, un calibrado de 0 bytes con nombre válido y geometrías o configs sin uso.
- **Cerrado:** 2026-10-19, por la fase 3 · movimientos de la meta 001 · limpieza y orden del repo: borrados `codigo\pytest-cache-files-xrzp8j4c\` (estaba versionado: 2 archivos de caché de pytest, `git rm --cached`) y `reference_dodecaedro_nuevo_calibrado.txt` (0 bytes); a `iter4\data\historico\` `reference_stylus_impreso_calibrado.txt` (movimiento de disco, ignorado) y, por P4 = a, `tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml` (`git mv`; el panel pasa de 4 a 2 perfiles). Se quedan `reference_dodecaedro_doctor.txt` (GUIA y `MANUAL_webcam.md`) y `_v2_fix`/`_v2_real` (procedencia de la geometría vigente). 0 archivos de 0 bytes en `iter4\data\`. La causa del calibrado vacío sigue abierta en B19.

### B02 · La suite está rota y no hay comprobación de «no cambió»
- **Qué era:** los 3 archivos de `codigo\tests\` no importaban (buscaban en `codigo\`) y no había replay sin cámara.
- **Cerrado:** 2026-10-19, por la fase 1 · suite y replay de la meta 001 · limpieza y orden del repo: `pytest.ini` y `conftest.py`, los 3 tests repuntados (22 desfasadas en `xfail`, B17), `py_compile` de `iter4\` y `gui\`, el selftest del panel y el replay sobre un recorte de `captura_ba.npz` con referencia guardada. 110 pruebas: 88 pasan, 22 `xfail`, en ~6 s.

### B03 · La calibración de punta vigente no tiene respaldo
- **Qué era:** `StylusTipToDodecaedro_femto_dock.npy/.txt` solo existía en este disco (`.gitignore`: las puntas son por equipo).
- **Cerrado:** 2026-10-19, por la fase 2 · respaldo de la punta de la meta 001 · limpieza y orden del repo (P3 = A', ADR-021): copia byte a byte en `codigo\iter4\data\respaldo_puntas\` con dos excepciones en `.gitignore`, fuera del glob del snippet de Slicer y de `estado.py`; sha256 del `.npy` igual al original (`a3c83203…5ebf`). Queda versionada con el commit del autor.
