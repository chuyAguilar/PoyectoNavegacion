# `codigo/slicer/` — scripts para la consola Python de 3D Slicer

Lo que Slicer necesita para recibir lo que publica el tracker, versionado aquí en vez de pegado desde un manual (ADR-026). Se corren **dentro de Slicer** (5.x con la extensión SlicerOpenIGTLink), no con el venv del proyecto.

La cadena (principio 6): el tracker publica solo `Marker0ToTracker` por OpenIGTLink, TCP 18944, solo transforms. Slicer se conecta como **cliente** a `localhost:18944` **antes** de arrancar el tracker (`pyigtl` bloquea si nadie está conectado; `docs/CONTEXT.md` §4.5).

## `receive_marker0.py`

Deja el conector listo, espera `Marker0ToTracker` y mide su frecuencia.

1. En Slicer: *View → Python Console* (Ctrl+3).
2. Cargar el script (ruta explícita):

   ```python
   exec(open(r"C:\Dev\OrtoMeta\PoyectoNavegacion\codigo\slicer\receive_marker0.py", encoding="utf-8").read())
   ```

   Imprime `[receive_marker0] cargado`.
3. `run()` (10 s de medición), `run(seconds=30)` o, para otro transform, `run(seconds=20, name="RateProbeToTracker")` (el nodo del banco `diagnostics.igtl_rate bench --external`, meta 003, fase 8b). Hace, sin bloquear la consola:
   - busca un conector OpenIGTLink **cliente** a `localhost:18944`; si no hay, lo crea (`TrackerClient`) y lo activa. Equivale a OpenIGTLinkIF → «+» → Client, `localhost`, `18944`, Active;
   - espera a que exista el nodo `Marker0ToTracker` (o el `name` pedido; tope 120 s): aparece cuando el tracker corre y la cámara ve Marker0;
   - cuenta sus `TransformModifiedEvent` durante los segundos pedidos, guarda el instante de cada uno y escribe dos líneas como

     ```
     [receive_marker0] Marker0ToTracker: 312 actualizaciones en 10.0 s = 31.2 Hz; ultima posicion (mm) [12.3, -4.5, 374.4]; conector CONNECTED
     [receive_marker0] intervalos entre actualizaciones (ms): p50 31.2 p95 33.0 max 48.1 (tic de Windows 15.625; un frame a 90 fps 11.1)
     [receive_marker0] DodecaedroToTracker: no existe en la escena (correcto, ADR-026)
     ```

   El mismo resultado queda en el dict `LAST_REPORT` (`node`, `seconds`, `updates`, `hz`, `last_position_mm`, `connector_state`, `legacy_present` y, desde la fase 8b, `interval_ms_p50`, `interval_ms_p95`, `interval_ms_max`).
4. Arrancar el tracker **después** de `run()` (o con el conector ya activo); `run()` se puede repetir en cada corrida.

Qué se mira:

- **Hz**: la frecuencia con que llega `Marker0ToTracker`. Se compara con la última línea `[FPS] Promedio` del tracker de la misma corrida: tiene que quedar a ≤ 10 % de ella (el tracker envía una vez por frame con pose). Desde la fase 7b el tracker sin ventana va a ~90 fps y Slicer cuenta ~66 Hz; la fase 8b mide de dónde sale ese techo (`codigo/diagnostics/igtl_rate.py`).
- **intervalos**: el tiempo entre dos modificaciones seguidas del nodo. Si el p50 ronda los 15–16 ms, Slicer recibe al ritmo de las ráfagas del hilo de envío de `pyigtl` (que despierta en el tic de Windows, 15.625 ms), no al de los frames (11.1 ms a 90 fps).
- **`DodecaedroToTracker: no existe`**: en una escena nueva (*File → Close Scene* antes de la corrida) no debe aparecer, ni aun con el dodecaedro a la vista.
- **conector**: `CONNECTED` mientras el tracker corre; `WAIT` cuando no hay tracker.

Si el nodo no aparece en 120 s, el script lo dice y para: comprobar que el tracker corre, que Marker0 está a la vista y que el conector está en `CONNECTED`.

## Lo que ya no está aquí

La jerarquía anterior (`DodecaedroToMarker0` por Observer, `StylusTipToDodecaedro`, `BoneToMarker0`) queda como referencia en `documentos/historico/MANUAL_simplificado.md`; el instrumento, la punta y el registro se rehacen en sus metas con nombres nuevos (ADR-025, ADR-026).
