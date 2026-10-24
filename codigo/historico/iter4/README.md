# historico/iter4 — el dodecaedro, la Femto Bolt y los perfiles viejos

Archivados el 2026-10-23 (meta 003 · Arquitectura y optimización del tracker, fase 3 · La estructura nueva y el archivo; ADR-025, ADR-026, ADR-027). Lo versionado se movió con `git mv`, sin tocar su contenido (la historia sigue con `git log --follow`); lo local, que sigue fuera de git (`*.npz`, `*.npy`, `*_calibrado.txt`, puntas), con `Move-Item`. Cierra B38 (índice de lo archivado) y B37 (la pose del dodecaedro saltaba 11–25 mm con un marker de lado: cerrado por decisión, el dodecaedro se descarta).

Es registro. **No se mantiene:** nada vivo de `codigo/` lo importa, la suite no lo recoge (`testpaths = tests`) y sus imports y rutas son los de `codigo/iter4/` antes de la meta 003, así que no corre tal cual. El tracker sigue solo Marker0 (`Marker0ToTracker`, principio 6). El instrumento y su punta vuelven en otra meta, con un transform de nombre nuevo; esta carpeta es su punto de partida.

Los archivos conservan su nombre de entonces.

## `dodecahedron/` — el dodecaedro v2, el stylus y la punta

| Archivo | Qué es |
|---|---|
| `captura_calibracion.py` | Captura del dataset para el bundle adjustment (tablas de ids, esquinas y tiempos). |
| `calibrar_rigid_body.py` | Bundle adjustment de la geometría del rigid body (ADR-008, ADR-009). |
| `calibrar_topologia.py` | Verificación opcional del orden real de pegado de los IDs frente a la convención teórica. |
| `generar_reference_dodecaedro.py` | Geometría teórica del dodecaedro (11 markers) para sembrar el BA. |
| `corregir_giro_esquinas.py` | Corrige, cara por cara, el giro de las esquinas de una geometría teórica según cómo se pegaron los markers. |
| `limpiar_captura_fantasmas.py` | Quita de una captura del BA las detecciones fantasma (por su error de reproyección). |
| `calibrar_tip_divot.py` | Calibración de la punta por dock/divot (ADR-010). |
| `gui/asistente.py` | El asistente «dodecaedro nuevo» del panel (captura → cobertura → BA). |
| `gui/ba_monitor.py` | El monitor del BA que usaba el asistente. |
| `data/reference_*.txt` | Las 8 geometrías versionadas: teórica vieja (`reference_dodecaedro.txt`, IDs 170–180), doctor, real, v2, **v2 calibrada** (la vigente hasta la meta 003, 1.26 px), v2_fix, v2_real y stylus impreso. |
| `data/respaldo_puntas/` | La copia versionada de la punta vigente, `StylusTipToDodecaedro_femto_dock` (ADR-021). |
| `data/` (locales) | Capturas del BA (`captura_ba*.npz`, `smoke_captura.npz`), muestras del divot y poses de pivote, las puntas `StylusTipToDodecaedro*` y `reference_dodecaedro_calibrado.txt` (del stylus viejo). |
| `tests/` | Las pruebas que se fueron con su código: `test_calibrar_rigid_body.py`, `test_captura_calibracion.py`, `test_generar_reference_dodecaedro.py` (las 22 `xfail` de B17 estaban aquí) y `test_replay.py` con `tests/data/replay_v2_femto*` (el replay del dodecaedro con el perfil Femto). |

La pose multi-marker (`estimar_pose_rigid_body`, `cargar_rigid_body`) sigue por ahora en `codigo/tracker.py`; la fase 4 de la meta 003 la saca a `dodecahedron/pose_rigid_body.py`.

## `femto/` — la Femto Bolt (ADR-025: solo valen las SVPRO gs1 y gs2)

| Archivo | Qué es |
|---|---|
| `femto_backend.py` | `FemtoBoltBackend`, sacado tal cual de `camera_backend.py`. `create_backend` con `camera_type: femtobolt` aborta y dice que está aquí. |
| `tracker_config.yaml` | El perfil Femto (contexto «canónico» hasta la meta 002), con el dodecaedro. |
| `data/femtobolt_calibration.yml` | Override de los intrínsecos de fábrica. |
| `data/diag_d2c/`, `data/diag_d2c_fuera/` | Diagnóstico de la alineación depth-to-color, dentro y fuera de la caja de luz (PNG versionados; los `.npz` son locales). |

`femto_pruebas/`, `open3d` y `pyorbbecsdk2` siguen en el repo y en `requirements.txt` (P4 de la meta 003; BACKLOG).

## `old_profiles/` — perfiles viejos

| Archivo | Qué es |
|---|---|
| `tracker_config_doctor.yaml`, `globalshutter.yml` | El contexto «doctor» (webcam global shutter a 640×480, Marker0 de 60 mm) y sus intrínsecos; archivados en la meta 002, fase 6. |
| `tracker_config_webcam.yaml`, `camera_calibration_webcam.yml` | El perfil webcam de la iteración 4 (SVPRO a 640×480, con el dodecaedro del stylus viejo) y sus intrínsecos. |
| `tracker_config_stylus_impreso.yaml`, `reference_stylus_impreso_calibrado.txt` (local) | El stylus impreso (IDs 181–191) con la Femto. |
