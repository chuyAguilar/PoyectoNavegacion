# Plan — Meta 001 · limpieza y orden del repo

Lo escribe el agente de planificación con `/planear`, sin código. Lo que el autor autoriza es este archivo.

Revisión del 2026-10-19: ajustado a las respuestas del autor en `clarify.md` (P1 = b, P2 = a, P3 = A', P4 = a, P5 = b, P6 = a).

## Lo leído

- HEAD: `edb9aa0 Monta la etapa 2 del método: papeles y rutinas`. Árbol: `memory.md` modificado y `specs/001-limpieza/` sin seguimiento.
- `specs/001-limpieza/spec.md`; `docs/constitution.md`; `memory.md`; `docs/CONTEXT.md` completo (trampas §4.1–17); `docs/BACKLOG.md` B01–B16; `docs/ARCHITECTURE.md` §3.2–3.7 y §6; `docs/PRUEBAS.md` (sin rondas); el índice de `docs/DECISIONS.md` y ADR-010/ADR-020 por grep.
- Código: `codigo/tests/` (3 archivos), `iter4/tracker.py` (`cargar_config`, `cargar_calibracion`, `cargar_rigid_body`, `estimar_pose_rigid_body`, `rvec_tvec_a_matriz`, `OneEuroFilter`, el lazo de `main()`), `iter4/captura_calibracion.py`, `iter4/calibrar_rigid_body.py`, `iter4/generar_reference_dodecaedro.py`, `iter4/gui/estado.py` (puntas y sha16), `iter4/gui/recetas.py` (`SLUGS`), `iter4/gui/panel.py` (`--selftest`), `iter4/tracker_config.yaml`.
- Datos inspeccionados (solo forma, sin abrir nada clínico): `iter4/data/captura_ba.npz`, `captura_ba_limpia.npz`, `smoke_captura.npz`; cabeceras de `reference_dodecaedro_v2_calibrado.txt` y `StylusTipToDodecaedro_femto_dock.txt`; `.gitignore`, `.gitattributes`, `codigo/requirements.txt`, `.claude/settings.json`.
- Greps (excluidos `.git`, `.venv`, `herramientas/A/`, `documentos/VERONICA/`, `*.nrrd`, `*.dcm`) de cada script de B01, cada archivo de B05, `PROJECT_BRIEF`, `briefs/`, `Dr.Milton` y `C:\dev\PoyectoNavegacion`.

### Lo que se encontró y cambia el plan

1. **La suite no solo está mal apuntada: está desfasada.** Escrita en mayo contra el código de la iteración 1–2. Los 3 archivos dan 72 pruebas (71 funciones; `test_inradius_alternate_formula` está parametrizada ×4). Comprobación estática (lectura de los tests y de las firmas de hoy, sin correr nada): tras repuntar a `iter4/`, 11 están desfasadas, 10 en rojo y 1 que hoy se salta y fallará al repuntarla:
   - Datos viejos: esperan IDs 151–161, y `iter4/data/reference_dodecaedro.txt` (versionado) y los defaults de `generar_reference_dodecaedro.py` son hoy 170–180: `test_calibrar_rigid_body::test_cargar_referencia_archivo_real`, `test_captura_calibracion::test_cargar_rb_ids_archivo_real`, `test_generar_reference_dodecaedro::test_ids_default_son_iter1`, `::test_iter2_ids_1_11` (KeyError en 151).
   - Funciones que ya no están en `captura_calibracion.py`: `cargar_calibracion` (vive en `tracker.py`; `test_cargar_calibracion_ok`, `test_cargar_calibracion_archivo_inexistente`) y `fourcc_int_a_str` (no existe; `test_fourcc_int_a_str_mjpg`); `construir_metadata` cambió de firma (`backend_info`, `has_depth` en vez de `calib_path`, `cam_info`; `test_construir_metadata_keys`).
   - Comportamiento que cambió: `captura_calibracion.validar_prerrequisitos` ya no valida el archivo de calibración (`test_validar_prereqs_falla_calibracion`); `resolver_geometry_path` busca `iter4/data/reference_dodecaedro.txt` relativo al CWD (la trampa de `CONTEXT.md` §4.14; `test_resolver_prefiere_teorico`).
   - `test_matches_historico_iter1` hoy se salta: apunta a `historico/iter1_2026-05-16/` y la carpeta es `historico/iter1/iter1_2026-05-16/`. Repuntada, falla: el histórico tiene IDs 151–161 y la geometría por defecto, 170–180.
   Por P1 = (b), las 11 quedan como `xfail(strict=True)` y ninguna se borra ni se reescribe.
2. **Ningún dataset grabado está en git:** `.gitignore` ignora `*.npz` y `*.npy`. `captura_ba.npz` (803 KB, 1809 frames, Femto 1920×1080 con K y dist dentro, IDs 3–13, 8046 detecciones) solo existe en este disco.
3. **La causa del archivo de 0 bytes (B05):** `validar_prerrequisitos` de `calibrar_rigid_body.py` (y la de `captura_calibracion.py`) abre la salida en modo `"ab"` para comprobar que se puede escribir. Un BA que falla después deja un `*_calibrado.txt` vacío con nombre válido. Borrarlo no basta: volverá. Va al BACKLOG (no se toca la lógica aquí).
4. **La punta se elige por fecha.** El snippet de Slicer de `documentos/MANUAL_simplificado.md` §4.2 carga el `StylusTipToDodecaedro*.npy` **más reciente por mtime** de `iter4/data/`; `estado.py` hace el mismo glob y avisa si no coincide con la preferida. Cualquier copia, `git pull` o movimiento que renueve el mtime de otra punta cambia lo que Slicer carga, sin aviso en Slicer. Esto condiciona B03 y B05, y obliga a una comprobación en cada fase: la punta más reciente de `iter4/data/` sigue siendo `StylusTipToDodecaedro_femto_dock.npy`.
5. **La punta vigente es coherente:** el sha16 de su cabecera (`11b0846fc5b5d43f`) coincide con el de `reference_dodecaedro_v2_calibrado.txt` hoy (crudo y con EOL normalizado). La cabecera nombra la ruta vieja `C:\Dev\Dr.Milton\...`; `estado.py` solo compara el sha, no la ruta.
6. **La GUI descubre perfiles por glob** (`estado.py`: `iter4/tracker_config*.yaml`). Mover `tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml` los quita del combo del panel. `recetas.SLUGS` los sigue nombrando (entrada de diccionario inerte; no se toca).
7. **`panel.py --selftest`** ya existe: abre el panel, refresca, imprime semáforos, botones y la semilla del asistente, y se cierra solo a los 1.2 s. Sirve de prueba headless (con `QT_QPA_PLATFORM=offscreen`) y de línea base de «no cambió» de la GUI.
8. **Referencias que el BACKLOG no tenía:** `reference_dodecaedro_doctor.txt` la usan `documentos/GUIA_calibrar_dodecaedro_propio.md` y `MANUAL_webcam.md` (se queda); `reference_dodecaedro_v2_fix.txt` es la semilla nombrada en la cabecera de la geometría vigente y `_v2_real.txt` es su origen (se quedan: son la procedencia de lo vigente, y editar la cabecera de la geometría cambiaría su sha y rompería la coherencia con la punta); `calibrar_topologia.py` y `limpiar_captura_fantasmas.py` son pasos de la GUIA y de los manuales, y `corregir_giro_esquinas.py` (escape del asistente) nombra a `limpiar_captura_fantasmas.py` (se quedan).
9. **Rutas viejas en scripts de Slicer:** además del snippet de `MANUAL_simplificado.md` §4.2, tres scripts de `femto_pruebas/` (rama en pausa, ADR-014) llevan constantes con `C:\Dev\Dr.Milton\...`. Corregirlos toca «lo que se carga en Slicer»: la verificación está en la fase 4.
10. **Entorno:** el venv tiene `pytest 9.0.3` (y `pytest>=7.4` está en `requirements.txt`): no hace falta dependencia nueva. Tiene `opencv_python 4.11.0.86` y `CONTEXT.md` §3 dice `opencv-contrib-python`; no afecta a esta meta, se anota como sugerencia.

## Archivos

### Fase 1 · suite y replay (B02)
- `codigo/pytest.ini` (nuevo): `testpaths = tests`; `addopts = -q -p no:cacheprovider` (evita las carpetas `pytest-cache-files-*` que dejó la caché en Windows).
- `codigo/tests/conftest.py` (nuevo): pone `codigo/iter4/` y `codigo/iter4/gui/` en `sys.path`; expone `ITER4_DIR` y `DATA_DIR`.
- `codigo/tests/test_calibrar_rigid_body.py`, `test_captura_calibracion.py`, `test_generar_reference_dodecaedro.py` (modificados): sin su `sys.path.insert` propio; rutas de datos a `iter4/data/` y a `historico/iter1/iter1_2026-05-16/`; las 11 pruebas desfasadas (lista en «Lo que se encontró», punto 1) con `@pytest.mark.xfail(strict=True, reason=...)`, sin tocar su cuerpo; el `reason` dice qué cambió en una frase y nombra la entrada del BACKLOG. Ninguna prueba se borra.
- `codigo/tests/test_compilan.py` (nuevo): `py_compile` de cada `.py` de `iter4/` y `iter4/gui/`, parametrizado, con el `.pyc` a `tmp_path` (no ensucia `__pycache__`).
- `codigo/tests/test_gui_headless.py` (nuevo): importa los 8 módulos de `gui/`; corre `panel.py --selftest` como subproceso con `QT_QPA_PLATFORM=offscreen`, CWD `codigo/` y tope de 60 s.
- `codigo/tests/replay_util.py` (nuevo; pytest no lo recoge): funciones del replay y una CLI con dos órdenes, `recortar` y `referencia`.
- `codigo/tests/test_replay.py` (nuevo): el replay contra la referencia.
- `codigo/tests/data/replay_v2_femto.npz` (nuevo, versionado): recorte de `captura_ba.npz` con paso 6 (P2 = a).
- `codigo/tests/data/replay_v2_femto_referencia.npz` (nuevo, versionado) y `replay_v2_femto_referencia.json` (nuevo): poses de referencia, y de dónde salieron (sha256 del dataset y de la geometría, versiones de OpenCV, numpy y Python, fecha, `min_markers`).
- `.gitignore` (modificado): excepción `!codigo/tests/data/*.npz`.

### Fase 2 · respaldo de la punta (B03)
- Por P3 = A': `codigo/iter4/data/respaldo_puntas/StylusTipToDodecaedro_femto_dock.npy` y `.txt` (nuevos, copia byte a byte, versionados) y dos excepciones en `.gitignore`. La subcarpeta queda fuera del glob no recursivo del snippet de Slicer y de `estado.listar_puntas()`.
- `docs/ARCHITECTURE.md` §3.4: dónde está el respaldo y su sha256.

### Fase 3 · movimientos (B01, B05)
- `git mv` de 10 scripts de `codigo/iter4/` a `codigo/historico/iter4_diagnosticos/`: `hello_femtobolt.py`, `leer_calibracion_femtobolt.py`, `medir_sigma_depth.py`, `test_backends.py`, `test_distancia_conocida.py`, `test_distancia_regla.py`, `test_jitter_tracking.py`, `test_pivote.py`, `test_alineacion_d2c.py`, `test_deteccion_marker.py` (evidencia en la tabla de abajo).
- `codigo/historico/iter4_diagnosticos/README.md` (nuevo): de dónde vienen, la fecha, que no se mantienen y que importan `camera_backend` de `iter4/` (para correrlos hace falta `PYTHONPATH`).
- `codigo/iter4/calibrar_rigid_body.py`: solo el docstring de la línea 17 («medido con `medir_sigma_depth.py`») pasa a nombrar la ruta nueva. Sin cambio de código.
- `codigo/readme.md`: la línea de `python test_pivote.py` dice que se movió y adónde.
- Borrados (ruido local, fuera de git): `codigo/pytest-cache-files-xrzp8j4c/` y `codigo/iter4/data/reference_dodecaedro_nuevo_calibrado.txt` (0 bytes).
- A `codigo/iter4/data/historico/` (movimiento de disco; están ignorados por `*_calibrado.txt`): `reference_stylus_impreso_calibrado.txt`.
- Por P4 = (a): `git mv` de `codigo/iter4/tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml` a `codigo/iter4/data/historico/`.
- `docs/ARCHITECTURE.md` §6: el árbol de `iter4/` sin los `test_*.py` ni los configs movidos.

### Fase 4 · textos (B04, B06)
- `git mv PROJECT_BRIEF.md docs/history/PROJECT_BRIEF.md` y `git mv briefs docs/history/briefs` (se conserva la estructura `briefs/historico/`).
- `docs/ARCHITECTURE.md` §6: quitar `PROJECT_BRIEF.md` de la raíz.
- Rutas viejas a `C:\Dev\OrtoMeta\PoyectoNavegacion` (solo el prefijo; el resto de cada línea igual), en los archivos versionados fuera de `docs/` y `specs/`: `codigo/readme.md` (3), `documentos/MANUAL_simplificado.md` (2: encabezado y snippet de Slicer §4.2), `MANUAL_webcam.md` (2), `MANUAL_femtobolt.md` (2), `femto_pruebas/cargar_stylus_en_slicer.py`, `diag_overlay_slicer.py`, `inyectar_en_slicer.py` (1, 1, 2: constantes de ruta). `PROJECT_BRIEF.md` (1) y `briefs/historico/prompt-brief-01.md` (1) no se corrigen: van literales a `docs/history/`.
- Por P5 = (b), quedan literales y fuera del grep los históricos versionados con la ruta vieja: `documentos/auditoria_iter2/` (7 archivos, 11 apariciones, 3 de ellos en `_archivo/`), `documentos/tecnicos/Documento_Tecnico_Navegacion_Quirurgica.md` (3) y `codigo/historico/iter1/Displacement to color.txt` (1). Conteo de `git grep -c` sobre HEAD `edb9aa0`.
- Cabecera de `iter4/data/StylusTipToDodecaedro_femto_dock.txt` y de su copia en `respaldo_puntas/` (versionada, así que `git grep` la ve): solo la ruta de la línea «Geometria dodecaedro»; el sha y la matriz no se tocan, el `.npy` tampoco.
- `docs/CONTEXT.md` §3 y §6: quitar el pendiente de la ruta vieja del `MANUAL_simplificado.md`.

### Evidencia de B01 (grep del 2026-10-19)

| Script | Referencias fuera de sí mismo | Decisión |
|---|---|---|
| `hello_femtobolt`, `leer_calibracion_femtobolt`, `test_backends`, `test_jitter_tracking` | solo `docs/BACKLOG.md` | se mueve |
| `medir_sigma_depth` | docstring de `calibrar_rigid_body.py` (cita de dónde salió `sigma_3d`) | se mueve; el docstring nombra la ruta nueva |
| `test_distancia_conocida`, `test_distancia_regla` | `test_distancia_regla` cita a `test_distancia_conocida` | se mueven juntos |
| `test_alineacion_d2c`, `test_deteccion_marker` | solo `PROJECT_BRIEF.md` (va a `docs/history/` en la fase 4) | se mueven |
| `test_pivote` | legacy por ADR-010; `codigo/readme.md`; `documentos/auditoria_iter2/`, `documentos/tecnicos/` e `historico/` (históricos); el ADR | se mueve; el readme dice adónde; el ADR no se reescribe |
| `calibrar_topologia` | paso de `GUIA_calibrar_dodecaedro_propio.md` y `MANUAL_webcam.md` | se queda |
| `limpiar_captura_fantasmas` | GUIA, `MANUAL_webcam.md`, `MANUAL_femtobolt.md`, mensaje final de `corregir_giro_esquinas.py` | se queda |

### Evidencia de B05 (grep del 2026-10-19)

| Archivo | Estado en git | Referencias | Decisión |
|---|---|---|---|
| `pytest-cache-files-xrzp8j4c/` | no aparece (carpetas vacías) | — | se borra |
| `reference_dodecaedro_nuevo_calibrado.txt` | ignorado, 0 bytes | el nombre lo propone el asistente (`asistente.py:149`) | se borra |
| `reference_stylus_impreso_calibrado.txt` | ignorado | ninguna | a `data/historico/` |
| `reference_dodecaedro_doctor.txt` | versionado | GUIA y `MANUAL_webcam.md` | se queda |
| `reference_dodecaedro_v2_fix.txt`, `_v2_real.txt` | versionados | procedencia de la geometría vigente | se quedan |
| `tracker_config_webcam.yaml` | versionado | `recetas.SLUGS`; usa la geometría del stylus viejo (170–180) y `camera_calibration_webcam.yml` | P4 |
| `tracker_config_stylus_impreso.yaml` | versionado | `recetas.SLUGS`; stylus impreso (B14) | P4 |

## Funciones y clases

Todas nuevas y en `codigo/tests/`. Ningún script de `iter4/` cambia de lógica.

- `replay_util.cargar_dataset(ruta: Path) -> tuple[list[dict[int, np.ndarray]], np.ndarray, np.ndarray, np.ndarray]`: lee solo las tablas (`timestamps`, `frame_offsets`, `marker_ids`, `corners_2d`, `K`, `dist`) con `allow_pickle=False`; devuelve las detecciones por frame, los timestamps, K y dist.
- `replay_util.recortar_dataset(entrada: Path, salida: Path, paso: int) -> dict`: toma uno de cada `paso` frames y guarda solo esas tablas (sin depth, sin `frames_data` pickle, sin `metadata_json`); devuelve frames, detecciones, bytes y sha256 de la entrada y la salida.
- `replay_util.correr_replay(dataset: Path, config: Path) -> dict[str, np.ndarray]`: lee la geometría y `rigid_bodies_quality.min_markers` del config con `tracker.cargar_config` y `tracker.cargar_rigid_body`; por frame aplica la regla de `main()` (menos de `min_markers` → sin pose) y llama a `tracker.estimar_pose_rigid_body` y `tracker.rvec_tvec_a_matriz`. Devuelve `valida` (N,), `M` (N,4,4) y `n_usados` (N,).
- `replay_util.comparar(obtenido: dict, referencia: dict) -> dict[str, float]`: frames cuya validez difiere, diferencia máxima de `n_usados`, de traslación (mm) y de rotación (grados, por el ángulo de `R_ref.T @ R`).
- `replay_util.guardar_referencia(obtenido: dict, ruta: Path, procedencia: dict, sobrescribir: bool) -> None`: escribe el `.npz` y el `.json`; si existen y no se pasa `sobrescribir`, aborta con mensaje.
- `replay_util.main(argv: list[str] | None = None) -> int`: `recortar --input --paso --output` y `referencia --dataset --config --output [--sobrescribir]`, todos explícitos.
- `test_replay.py`: `test_dataset_es_el_registrado()` (sha256 del dataset y de la geometría = los del `.json`), `test_replay_coincide_con_referencia()`. Si falta la referencia, falla; nunca la genera.
- `test_gui_headless.py`: `test_importan_modulos_gui(modulo: str)` (parametrizado) y `test_panel_selftest()` (rc 0, «cerrando OK» en la salida, menos de 60 s).
- `test_compilan.py`: `test_compila(ruta: Path)` (parametrizado).

La referencia se genera una vez, a mano, con `replay_util.py referencia`; regenerarla exige `--sobrescribir` y es un cambio visible en `git diff` que el autor commitea a propósito (p.ej. al cambiar de OpenCV). El filtro 1-Euro y el cuaternión de `main()` quedan fuera: están dentro del lazo y sacarlos a una función toca `tracker.py` (BACKLOG).

## Fases

Todas: la suite con `codigo\.venv\Scripts\python.exe -m pytest codigo\tests -q`, con tope de 120 s en la orden; tras editar un `.py`, `py_compile` y conteo de líneas. La línea base de «no cambió» la fija la fase 1 y queda en su reporte: el número de pruebas, el resultado del replay, la salida de `panel.py --selftest` y el nombre de la punta más reciente de `iter4/data/`.

### Fase 1 · suite y replay (B02)
- **Entrega:** `pytest.ini`, `conftest.py`, los 3 tests repuntados (con P1), `test_compilan.py`, `test_gui_headless.py`, `replay_util.py`, `test_replay.py`, el recorte, la referencia y la excepción de `.gitignore`.
- **Criterio:**
  - la suite en verde, 0 errores de colección, 0 fallos y 0 `XPASS` (con `strict=True` un xfail que pasa es un fallo); tiempo de la suite completa ≤ 30 s;
  - de los 3 archivos originales, 72 pruebas: 61 pasan, 11 `xfail` (las de «Lo que se encontró», punto 1) y 0 saltadas; por archivo: `test_calibrar_rigid_body` 15 + 1 xfail, `test_captura_calibracion` 19 + 7 xfail, `test_generar_reference_dodecaedro` 27 + 3 xfail;
  - las nuevas, todas pasan: `test_compilan` 29 (21 `.py` de `iter4/` y 8 de `gui/`), `test_gui_headless` 9 (8 imports y el selftest), `test_replay` 2. Total esperado: 112 recogidas, 101 pasan, 11 `xfail`, 0 saltadas. Si un número difiere, la fase lo reporta con la prueba que lo explica y no lo ajusta en silencio;
  - replay: generar la referencia y correr el replay dos veces seguidas da 0 frames con distinta validez, diferencia máxima 0.0 mm y 0.0° (tolerancia del test: ≤ 1e-6 mm y ≤ 1e-6°); se reporta cuántos frames dan pose y la mediana de `n_usados`;
  - el recorte pesa ≤ 150 KB y tiene ≥ 250 frames;
  - `panel.py --selftest` termina con rc 0 en ≤ 60 s;
  - `git status --short` no muestra ningún `.npz` fuera de `codigo/tests/data/`.
- **Cómo se mide:** suite; replay; la salida guardada del selftest. Sin cámara ni Slicer.
- **Cierra:** B02. La dirección añade al BACKLOG la entrada de las 11 pruebas en `xfail` (abajo).

### Fase 2 · respaldo de la punta (B03)
- **Entrega:** la copia en `iter4/data/respaldo_puntas/`, las dos excepciones de `.gitignore` y `ARCHITECTURE.md` §3.4.
- **Criterio:** `git ls-files codigo/iter4/data/respaldo_puntas` lista el `.npy` y el `.txt`; el sha256 del `.npy` copiado es igual al del original (`a3c83203…`); la punta más reciente de `iter4/data/` sigue siendo `StylusTipToDodecaedro_femto_dock.npy`; suite, replay y selftest iguales a la línea base.
- **Cómo se mide:** suite, replay, `Get-FileHash`, `git ls-files`.
- **Cierra:** B03. La dirección escribe el ADR-021 (P3 = A').

### Fase 3 · movimientos (B01, B05)
- **Entrega:** los `git mv` y borrados de la sección «Archivos», el README de `iter4_diagnosticos/`, el docstring y la línea del readme, `ARCHITECTURE.md` §6.
- **Criterio:**
  - suite igual a la línea base salvo `test_compilan`, que baja de 29 a 19 por los 10 scripts movidos: 102 recogidas, 91 pasan, 11 `xfail`, 0 saltadas; replay y selftest iguales a la línea base (el selftest no lista perfiles; el combo del panel sí pasa de 4 a 2 perfiles por P4, y se reporta);
  - grep, en 0: los 10 nombres en `codigo/iter4/`, `codigo/iter4/gui/`, `codigo/tests/` y los docs vivos (clasificación de P5), salvo la mención que diga adónde se movieron; los históricos de P5 no cuentan;
  - `Get-ChildItem codigo\iter4\data -Recurse -File | Where-Object Length -eq 0` devuelve 0 archivos;
  - la punta más reciente sigue siendo `StylusTipToDodecaedro_femto_dock.npy`;
  - `git status` muestra los movimientos como renombres (`R`), no como borrado más alta.
- **Cómo se mide:** suite, replay, selftest, grep.
- **Cierra:** B01 y B05.

### Fase 4 · textos (B04, B06)
- **Entrega:** los dos `git mv` a `docs/history/`, las rutas corregidas, las cabeceras de la punta y `CONTEXT.md`/`ARCHITECTURE.md`.
- **Criterio:**
  - `git grep -nE "Dr\.Milton|[Cc]:[\\/]+[Dd]ev[\\/]+PoyectoNavegacion" -- . ":!docs/" ":!specs/" ":!codigo/historico/" ":!documentos/auditoria_iter2/" ":!documentos/tecnicos/" ":!herramientas/A/" ":!documentos/VERONICA/" ":!*.nrrd" ":!*.dcm"` devuelve 0 líneas (en HEAD `edb9aa0` da 13 líneas en 7 archivos vivos y 2 en los que van a `docs/history/`; tras la fase 2 se suma la cabecera de la copia en `respaldo_puntas/`);
  - los históricos de P5 siguen literales: el mismo grep sobre `codigo/historico/`, `documentos/auditoria_iter2/` y `documentos/tecnicos/` da las mismas 15 apariciones en 9 archivos que en HEAD `edb9aa0`, y `git diff --stat` no los lista;
  - grep de `PROJECT_BRIEF` y `briefs/` fuera de `docs/history/` y `specs/`: solo menciones que dicen que están en `docs/history/` y la del ADR-020 (no se reescribe);
  - `git diff --word-diff` de cada archivo tocado solo cambia el prefijo de la ruta;
  - cadena (principio 6): el directorio que nombra el snippet de §4.2 existe y su glob `StylusTipToDodecaedro*.npy` da como más reciente `StylusTipToDodecaedro_femto_dock.npy`; los tres scripts de `femto_pruebas/` compilan y su diff es solo la constante;
  - `estado.py --perfil iter4/tracker_config.yaml --puntas` da para la punta el mismo semáforo que antes de editar la cabecera (VERDE, sha `11b0846fc5b5d43f`);
  - suite, replay y selftest iguales a la línea base.
- **En vivo con el autor (P6 = a):** no bloquea el cierre. La prueba (pegar el snippet de §4.2 en la consola de Slicer y leer la traslación del nodo `StylusTipToDodecaedro`; esperado [+0.904, +5.471, −201.808] mm, magnitud 201.884 mm) se anota en B10 para la próxima sesión con Slicer.
- **Cierra:** B04 y B06.

## Lo que va al BACKLOG

- **Alta · `validar_prerrequisitos` deja un calibrado vacío.** En `calibrar_rigid_body.py` y `captura_calibracion.py` abre la salida en `"ab"` antes de correr: si el proceso falla, queda un archivo de 0 bytes con nombre válido (origen de B05). Haría falta comprobar la carpeta sin crear el archivo y escribir solo al final. De: plan de la meta 001.
- **Alta · Slicer carga la punta por fecha.** El snippet de `MANUAL_simplificado.md` §4.2 toma el `StylusTipToDodecaedro*.npy` más reciente; un `git pull`, una copia o un movimiento cambian cuál, sin aviso en Slicer (`estado.py` sí avisa). Haría falta nombrar la punta explícita en el snippet y mover las puntas viejas (`StylusTipToDodecaedro.npy`, `_2`, `_divot`, `_viejo_dock`, del dodecaedro viejo) a `data/historico/`. Toca lo que se carga en Slicer: verificación en vivo. De: plan de la meta 001.
- **Media · 11 pruebas desfasadas en `xfail(strict=True)`.** Por P1 = (b), la fase 1 las marca sin reescribirlas: 4 por los IDs 151–161 frente a 170–180, 1 por el histórico de iter1 con IDs viejos, 3 por funciones que ya no están en `captura_calibracion.py` (`cargar_calibracion`, `fourcc_int_a_str`), 1 por la firma nueva de `construir_metadata`, 1 por `resolver_geometry_path` relativo al CWD (`CONTEXT.md` §4.14) y 1 porque `captura_calibracion.validar_prerrequisitos` ya no comprueba el archivo de intrínsecos. Lo que vigilaban hoy no se vigila. Haría falta, por cada una, caracterizarla (que espere lo que el código hace hoy) o borrarla; la de los intrínsecos exige antes decidir si es a propósito (la Femto usa los de fábrica) o hay que restaurar el fallo fuerte (principio 7), y por ella la entrada no es baja. De: plan de la meta 001, P1.
- **Media · el filtro 1-Euro no tiene replay.** El filtrado de posición y cuaternión está dentro de `tracker.main()`; cubrirlo exige sacarlo a una función de `tracker.py` (principio 6: replay antes y después). De: plan de la meta 001.
- **B10 (se amplía, no es entrada nueva) · la prueba del snippet de Slicer con la ruta nueva.** Por P6 = (a): pegar el snippet de `MANUAL_simplificado.md` §4.2 y leer la traslación de `StylusTipToDodecaedro`; esperado [+0.904, +5.471, −201.808] mm, magnitud 201.884 mm. De: fase 4 de la meta 001.
- **Baja · `opencv-python` frente a `opencv-contrib-python`.** El venv y `requirements.txt` tienen `opencv-python 4.11`; `CONTEXT.md` §3 dice contrib. Solo alinear el texto, o el paquete si algo de contrib hiciera falta.

## ADR que se proponen

- **ADR-021 · La punta vigente se respalda en git como copia fuera del glob** (P3 = A', aceptado por el autor el 2026-10-19; lo escribe la dirección en la fase 2): amplía la excepción de ADR-009 a la calibración de punta del contexto canónico; la copia vive en `iter4/data/respaldo_puntas/` para que ni el snippet de Slicer ni `estado.py` la vean; el original sigue siendo por equipo y fuera de git.
- No se propone ADR para `pytest.ini` ni para el replay: son herramienta de prueba y no cambian el sistema.

## Preguntas abiertas

Ninguna. P1–P6 están respondidas por el autor en `clarify.md` (2026-10-19): P1 = (b) las 11 desfasadas en `xfail(strict=True)` con entrada de BACKLOG; P2 = (a) recorte de `captura_ba.npz` con paso 6; P3 = A' con ADR-021; P4 = (a) los dos configs a `data/historico/`; P5 = (b) clasificación vivo/histórico propuesta, históricos literales y fuera del grep de B06; P6 = (a) la prueba en Slicer va a B10.

## Títulos de commit

- Fase 1: `Repara la suite y añade el replay sin cámara`
- Fase 2: `Respalda la punta vigente`
- Fase 3: `Mueve los diagnósticos y los datos muertos de iter4`
- Fase 4: `Archiva briefs y corrige las rutas viejas`
