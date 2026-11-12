# `codigo/slicer/` — scripts para la consola Python de 3D Slicer

Lo que Slicer necesita para recibir lo que publica el tracker, versionado aquí en vez de pegado desde un manual (ADR-026). Se corren **dentro de Slicer** (5.x con la extensión SlicerOpenIGTLink), no con el venv del proyecto.

La cadena (principio 6): el tracker publica solo `ReferenceToTracker` por OpenIGTLink, TCP 18944, solo transforms. Slicer se conecta como **cliente** a `localhost:18944` **antes** de arrancar el tracker: el tracker lo espera hasta `--slicer-timeout` (30 s) y, si no llega, aborta sin abrir la cámara (ADR-028; `docs/CONTEXT.md` §4.5).

Hasta la fase 7c2 de la meta 006 (2026-11, P57 y P65) el transform se llamaba `Marker0ToTracker` y el script, `receive_marker0.py`. La referencia es el mismo marker con otro nombre (`Reference` en `markers.list` del perfil); el puerto y la jerarquía no cambian.

## `receive_reference.py`

Deja el conector listo, espera `ReferenceToTracker` y mide su frecuencia.

1. En Slicer: *View → Python Console* (Ctrl+3).
2. Cargar el script (ruta explícita):

   ```python
   exec(open(r"C:\Dev\OrtoMeta\PoyectoNavegacion\codigo\slicer\receive_reference.py", encoding="utf-8").read())
   ```

   Imprime `[receive_reference] cargado`.
3. `run()` (10 s de medición), `run(seconds=30)` o, para otro transform, `run(seconds=20, name="RateProbeToTracker")` (el nodo del banco `diagnostics.igtl_rate bench --external`, meta 003, fase 8b). Hace, sin bloquear la consola:
   - busca un conector OpenIGTLink **cliente** a `localhost:18944`; si no hay, lo crea (`TrackerClient`) y lo activa. Equivale a OpenIGTLinkIF → «+» → Client, `localhost`, `18944`, Active;
   - espera a que exista el nodo `ReferenceToTracker` (o el `name` pedido; tope 120 s): aparece cuando el tracker corre y la cámara ve la referencia;
   - cuenta sus `TransformModifiedEvent` durante los segundos pedidos, guarda el instante de cada uno y escribe líneas como

     ```
     [receive_reference] ReferenceToTracker: 312 actualizaciones en 10.0 s = 31.2 Hz; ultima posicion (mm) [12.3, -4.5, 374.4]; conector CONNECTED
     [receive_reference] intervalos entre actualizaciones (ms): p50 31.2 p95 33.0 max 48.1 (tic de Windows 15.625; un frame a 90 fps 11.1)
     [receive_reference] ReferenceToTracker en la raiz de la escena (correcto, principio 6)
     [receive_reference] DodecaedroToTracker: no existe en la escena (correcto)
     [receive_reference] Marker0ToTracker: no existe en la escena (correcto)
     ```

   El mismo resultado queda en el dict `LAST_REPORT`: `node`, `seconds`, `updates`, `hz`, `last_position_mm`, `connector_state`, `en_raiz` (el nodo no cuelga de ningún otro transform), `legacy_present` (un `{nombre: bool}` con los nombres de antes, `DodecaedroToTracker` y `Marker0ToTracker`) y, desde la fase 8b, `interval_ms_p50`, `interval_ms_p95`, `interval_ms_max`.
4. Arrancar el tracker **después** de `run()` (o con el conector ya activo); `run()` se puede repetir en cada corrida.

Qué se mira:

- **Hz**: la frecuencia con que llega `ReferenceToTracker`. Se compara con la última línea `[FPS] Promedio` del tracker de la misma corrida: tiene que quedar a ≤ 10 % de ella (el tracker envía una vez por frame con pose). Eso vale por debajo de ~65 Hz: con este Slicer no se reciben más, aunque el tracker sin ventana envíe ~90 por segundo. La fase 8b (meta 003, 2026-10-25) lo midió con `codigo/diagnostics/igtl_rate.py`: no se pierde ningún envío y el techo es de Slicer (`docs/ARCHITECTURE.md` §3.5; B54).
- **intervalos**: el tiempo entre dos modificaciones seguidas del nodo. Si el p50 ronda los 15–16 ms, Slicer recibe al ritmo de las ráfagas del hilo de envío de `pyigtl` (que despierta en el tic de Windows, 15.625 ms), no al de los frames (11.1 ms a 90 fps).
- **`ReferenceToTracker en la raiz`** (`en_raiz == True`): el nodo llega a la raíz de la escena y nadie lo cuelga de otro transform.
- **`DodecaedroToTracker: no existe`** y **`Marker0ToTracker: no existe`** (`legacy_present` todo en `False`): en una escena nueva (*File → Close Scene* antes de la corrida) no debe aparecer ninguno de los nombres de antes, ni aun con el dodecaedro o un Marker0 viejo (ID 0) a la vista. En una escena guardada de antes pueden estar como nodos viejos: por eso se mide en una escena nueva.
- **conector**: `CONNECTED` mientras el tracker corre; `WAIT` cuando no hay tracker.

Si el nodo no aparece en 120 s, el script lo dice y para: comprobar que el tracker corre, que la referencia está a la vista y que el conector está en `CONNECTED`.

## Lo que ya no está aquí

La jerarquía anterior (`DodecaedroToMarker0` por Observer, `StylusTipToDodecaedro`, `BoneToMarker0`) queda como referencia en `documentos/historico/MANUAL_simplificado.md`; el instrumento, la punta y el registro se rehacen en sus metas con nombres nuevos (ADR-025, ADR-026).
