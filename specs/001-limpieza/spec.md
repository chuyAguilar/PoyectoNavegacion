# Meta 001 — limpieza y orden del repo

## Por qué

El paso 0 del método (ADR-020, 2026-10-19) dejó en el BACKLOG seis entradas de orden con destino «spec 001»: B01 · Scripts legacy y de diagnóstico sueltos en `iter4\`, B02 · La suite está rota y no hay comprobación de «no cambió», B03 · La calibración de punta vigente no tiene respaldo, B04 · Docs viejas o duplicadas en la raíz, B05 · Ruido local y archivos muertos en `iter4\data\` y B06 · Rutas viejas fuera de `docs\`.

Van ahora y antes que cualquier meta de producto porque, sin suite, ningún cambio se puede verificar (principio 3), y porque hay archivos que pueden dar un resultado equivocado: un calibrado de 0 bytes con nombre de geometría válida (B05) y una punta vigente que solo existe en un disco (B03). El autor tiene una meta concreta para después del orden.

## Qué se construye

1. **Una suite que corre y una comprobación de «no cambió» (B02).** Los tests de `codigo\tests\` repuntados a `codigo\iter4\`; un `py_compile` de todo `iter4\` y `iter4\gui\`; y un replay sin cámara que corre la estimación de pose sobre un dataset grabado y compara contra una referencia guardada. Esta pieza va primero: las demás se verifican con ella.
2. **El respaldo de la punta vigente (B03),** según lo que decida el autor (versionarla como excepción o respaldarla fuera de git).
3. **Scripts legacy y de diagnóstico fuera de `iter4\` (B01),** movidos (no borrados) a `codigo\historico\iter4_diagnosticos\`, solo los que nadie importa ni nombra.
4. **Ruido local y archivos muertos fuera de `iter4\data\` (B05):** el ruido local borrado; lo muerto movido a `iter4\data\historico\`.
5. **Docs viejas a `docs/history/` (B04):** `PROJECT_BRIEF.md` y `briefs/` como copia literal, con las referencias que queden corregidas.
6. **Rutas viejas corregidas (B06)** fuera de `docs\` a `C:\Dev\OrtoMeta\PoyectoNavegacion`.

## Criterio de cierre

- **La suite:** `codigo\.venv\Scripts\python.exe -m pytest codigo\tests -q` termina en verde, con 0 errores de colección y al menos las pruebas de los 3 archivos actuales corriendo, más el `py_compile` y el replay. Se reporta cuántas y cuánto tardan; tope de tiempo de la suite completa propuesto por el plan (orden: segundos, no minutos).
- **El replay:** sobre el dataset grabado elegido, la pose por frame coincide con la referencia guardada dentro de una tolerancia que fija el plan (orden propuesto: ≤ 1e-6 mm en traslación y ≤ 1e-6° en rotación, es decir, igualdad numérica salvo redondeo). Se corre antes y después de cada fase de movimientos.
- **Lo que no debe cambiar:** después de cada fase, la suite y el replay dan lo mismo que al cerrar la fase 1.
- **Los greps, en cero** (excluyendo `docs/history/` y las carpetas de datos de paciente):
  - ninguna aparición de `Dr.Milton` ni de `C:\dev\PoyectoNavegacion` (sin `OrtoMeta`) en los archivos vivos fuera de `docs\`; los históricos (`codigo/historico/`, `documentos/auditoria_iter2/`, `documentos/tecnicos/`) quedan literales y fuera del grep (`clarify.md` P5, 2026-10-19);
  - ningún `import` ni mención, en `codigo\iter4\`, `codigo\iter4\gui\`, `codigo\tests\` ni en los docs vivos, de un script movido por B01, salvo la que diga que se movió y adónde;
  - ningún archivo de 0 bytes en `codigo\iter4\data\`.
- **B03:** la decisión del autor escrita en `clarify.md`, y la punta vigente con respaldo comprobable (si se versiona: `git ls-files` la lista; si no: dónde está la copia y que su hash coincide).
- **La GUI y la cadena:** el panel (`iter4\gui\panel.py`) importa y arranca sin cámara hasta mostrar su ventana o, si el plan lo prefiere, una prueba headless que importe sus módulos. No hace falta sesión en vivo con cámara ni Slicer, porque esta meta no toca `tracker.py`, `camera_backend.py`, el envío por `pyigtl` ni los scripts de Slicer; si el plan descubre que alguno se toca, propone su verificación en vivo.
- **B01–B06** pasan a «Cerrados» en el BACKLOG con la fecha y la fase que los cerró.

## Lo que no se toca

- La cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6): `tracker.py`, `camera_backend.py`, el envío por `pyigtl`, los nombres de transform y el puerto 18944. Se comprueba con la suite y el replay.
- La lógica de ningún script activo: esta meta mueve, borra ruido, repunta tests y corrige textos. Si un script activo necesita un cambio para que un test corra, se anota en el BACKLOG y no se hace aquí, salvo que sea solo una ruta de importación.
- Los defaults peligrosos de los scripts (`CONTEXT.md` §4.13–17): son de otra meta; si el plan cree que alguno entra aquí, lo propone como pregunta.
- Los datos de paciente (principio 5): `herramientas/A/`, `*.nrrd`, `*.dcm` y `documentos/VERONICA/` no se leen, no se mueven y quedan fuera de todo grep.
- Los binarios pesados (B11 · Binarios pesados versionados) y la compactación de `.git` (B13 · `.git` sin compactar): no entran.
- `docs/history/` no se edita; solo recibe copias nuevas.
- Nada se borra de git que no sea ruido local: lo que tenga historia se mueve con `git mv`.

## Preguntas que el plan tiene que contestar

1. **El dataset del replay:** ¿cuál (p.ej. `captura_ba.npz`), está versionado, cuánto pesa, qué geometría e intrínsecos usa, y qué función de pose se llama? Si el dataset idóneo no está en git, ¿se versiona uno pequeño o se recorta?
2. **La referencia del replay:** ¿cómo se genera la primera vez, dónde se guarda y cómo se regenera a propósito sin que se regenere sola?
3. **B03:** las opciones para la punta vigente (excepción en `.gitignore` como la geometría v2, o respaldo fuera de git), con sus pros y contras, para que decida el autor. Si se versiona, ¿hace falta ADR?
4. **B01:** la lista final de scripts que se mueven, con la evidencia de grep de cada uno; y los que se quedan, con por qué (en especial `test_pivote`, `test_alineacion_d2c`, `calibrar_topologia`, `limpiar_captura_fantasmas`, `test_deteccion_marker`).
5. **B05:** la lista final de archivos de `iter4\data\` que se mueven o borran, con sus referencias; y si `tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml` siguen en uso (contexto doctor, B14 · Stylus impreso nuevo).
6. **B04:** qué referencias a `PROJECT_BRIEF.md` y a `briefs/` quedan y dónde.
7. **B06:** la lista de archivos con rutas viejas; cuáles están en `docs/history/` (no se tocan) y cuáles en código (scripts, configs) que cambiarían comportamiento.
8. **El orden y el número de fases,** con un commit por fase; propuesta: suite y replay primero, luego B03, luego los movimientos (B01, B05), luego los textos (B04, B06).
9. **`pytest`:** si hace falta un `conftest.py` o un `pytest.ini` para la ruta de importación, y si `pytest` está ya en `codigo\requirements.txt`.
