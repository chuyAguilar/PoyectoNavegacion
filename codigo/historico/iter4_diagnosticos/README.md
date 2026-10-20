# iter4_diagnosticos — scripts de diagnóstico y legacy de la iteración 4

Movidos de `codigo/iter4/` el 2026-10-19 (meta 001 · limpieza y orden del repo, fase 3 · movimientos; BACKLOG B01) con `git mv`, sin tocar su contenido: la historia de cada uno sigue con `git log --follow`.

Son de junio de 2026 (iteración 4, Femto Bolt). Ningún script activo, la GUI ni la suite los importa o los nombra. **No se mantienen**: pueden no correr contra el código de hoy, y ninguno es parte de la cadena tracker → OpenIGTLink → Slicer.

| Script | Qué hacía |
|---|---|
| `hello_femtobolt.py` | Hello World del SDK de la Femto Bolt (importa el `pyorbbecsdk` viejo, no `pyorbbecsdk2`). |
| `leer_calibracion_femtobolt.py` | Lee los intrínsecos de fábrica de la Femto (RGB y depth). |
| `medir_sigma_depth.py` | Mide el ruido del depth sobre un plano; de aquí salió `sigma_3d = 5.0 mm` del BA (`iter4/calibrar_rigid_body.py`). |
| `test_backends.py` | Smoke test de `camera_backend.py` (webcam y femtobolt). |
| `test_alineacion_d2c.py` | Diagnóstico de la alineación depth-to-color (el bias de +58 mm). |
| `test_deteccion_marker.py` | Prueba rápida de detección de un marker impreso. |
| `test_distancia_conocida.py` | Exactitud de la punta con la placa de divots. |
| `test_distancia_regla.py` | Variante de la anterior con una regla. |
| `test_jitter_tracking.py` | Jitter de la pose con el dodecaedro quieto. |
| `test_pivote.py` | Calibración de la punta por pivote: legacy desde ADR-010 (la vía vigente es `iter4/calibrar_tip_divot.py`). |

Los `test_*.py` no son pruebas de pytest: son scripts con cámara.

## Si hace falta correr uno

Importan módulos de `iter4/` (`camera_backend`, `captura_calibracion`, `tracker`, `calibrar_tip_divot`) y sus rutas por defecto son relativas a `codigo/`. Desde `codigo/`, con el venv, `iter4/` en `PYTHONPATH` y los argumentos explícitos (principio 7):

```powershell
$env:PYTHONPATH = "iter4"
python historico\iter4_diagnosticos\test_jitter_tracking.py --config iter4\tracker_config.yaml
```

Las líneas de «Uso» de sus docstrings todavía dicen `python iter4\...`: son de antes del movimiento.
