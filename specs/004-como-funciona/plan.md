# Plan — Meta 004 · Cómo funciona el tracker: gráfico y explicación de detección → pose

Lo escribió el agente de planificación con `/planear 004-como-funciona` el 2026-10-26, sin código. Lo que el autor autoriza es este archivo.

**Versión 2 (2026-10-26), tras las respuestas P1–P7 de `clarify.md`.** Lo que cambia respecto a la versión 1: el gráfico es Mermaid como fuente **y** una imagen PNG exportada (P1 = c), que se genera con `mermaid-cli` y una prueba ata al Mermaid por su sha256; todo vive en una sección nueva, §9, de `docs/ARCHITECTURE.md` (P2 = c), no en `docs/COMO_FUNCIONA.md`; `ARCHITECTURE.md` gana un índice al principio; P3 queda sin efecto y el ADR-032 cambia de objeto (ahora es la herramienta de exportar, fuera de `requirements.txt`); las dos figuras van a `docs/img/004/`, < 200 KB en total (P6 = a). P4, P5 y P7 quedan como estaban. Una pregunta nueva: P8.

## Lo leído

- HEAD: `63bbdd8 Cierra el spec activo de la meta 003` (árbol con `docs/BACKLOG.md` y `memory.md` modificados y `specs/004-como-funciona/` sin seguimiento).
- El spec, `clarify.md` (P1–P7 contestadas el 2026-10-26) y `tasks.md` de `specs/004-como-funciona/`. `docs/constitution.md`, `memory.md`, `docs/CONTEXT.md` completo (trampas §4.1–20).
- `docs/ARCHITECTURE.md` completo por sus títulos (§1–§8; no tiene índice al principio; 39 279 bytes; ninguna línea pasa hoy de 1 800 caracteres): §2 (la topología en Mermaid, 6 cajas), §3.2 (el bucle), §3.4 (intrínsecos), §3.5 (transporte y el techo de ~65 Hz), §3.6 (Slicer), §4 (la cadena en Slicer), §6 (estructura y el «no cambió»), §7 (frames y convención de esquinas), §8 (decisiones viejas, «reemplazadas»). `docs/BACKLOG.md`: índice, B54 y B55. `docs/DECISIONS.md`: índice (último ADR-031). `docs/PRUEBAS.md`: índice y P04.
- `specs/003-arquitectura-tracker/diagrama.md` y el índice de su `resultados.md` (las fuentes de fps y Hz).
- Código de `codigo/`: `tracker.py` (`main`, `draw_poses`), `vision/detection.py`, `vision/pose.py`, `vision/filtering.py`, `vision/tracking.py`, `transport/igtl.py`, `camera/grabber.py`, `camera/backend.py` (firmas), `profiles/__init__.py`, `gui/panel.py`, `gui/recipes.py`, `gui/processes.py` (firmas), `slicer/receive_marker0.py`, `diagnostics/*.py` (firmas; `pose_log.load_recording`), `tests/replay_util.py`, `tests/test_replay_marker0.py`, `tests/test_compilan.py`, `tests/conftest.py`, `profiles/tracker_config_gs1.yaml`, `data/intrinsecos_gs1_1280x960.yml`, `tests/data/marker0_gs{1,2}_reference.json`, `requirements.txt`.
- Comprobado al leer: el sha256 de `data/intrinsecos_gs1_1280x960.yml` (`0b4250e5…`) y el de gs2 (`8a6a06f4…`) son los `calibration_sha256` con que se grabaron `marker0_gs1.npz` y `marker0_gs2.npz`. La grabación de gs1 tiene 977 frames y 977 envíos. Los tres PNG de `tests/data/marker0_gs1_frames/` pesan ~188 KB cada uno (1280×960): la figura del ejemplo tiene que ir recortada para que las dos imágenes quepan en 200 KB.
- En la máquina, sin instalar nada: Node.js v24.15.0 y npm 11.12.1 están; Microsoft Edge está en `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`; Chrome no. `docs/img/` no existe.
- **Context7 (2026-10-26), solo preguntas de API:**
  - Mermaid (`/websites/mermaid_js`): etiquetas de nodo entre comillas dobles para caracteres especiales, `subgraph … end`, etiquetas en las flechas (`A -- texto --> B` o `-->|texto|`). GitHub y VS Code lo dibujan sin instalar nada.
  - mermaid-cli (`/mermaid-js/mermaid-cli`): el comando es `mmdc -i entrada.mmd -o salida.png` (la extensión fija el formato: svg, png o pdf); `-b` el fondo (`white`, `transparent`), `-t` el tema; `--size`/ancho para el tamaño; se corre sin instalar global con `npx -p @mermaid-js/mermaid-cli mmdc …` (el `-p` hace falta porque el paquete no se llama como el comando); usa puppeteer y un Chromium: con `--puppeteerConfigFile cfg.json` y `{"executablePath": "…"}` usa un navegador ya instalado; también se instala local con `npm install @mermaid-js/mermaid-cli`. Los nombres exactos de las opciones de tamaño y escala se fijan en la fase 1 contra `mmdc -h` de la versión que se fije.
  - OpenCV 4.13 (`/websites/opencv_4_13_0`; instalado 4.11): `solvePnP` → `(ok, rvec, tvec)`; `projectPoints(obj, rvec, tvec, K, dist)` da los px reproyectados; `drawFrameAxes(img, K, dist, rvec, tvec, length)` dibuja los ejes. El orden de esquinas de `SOLVEPNP_IPPE_SQUARE` ya está contrastado en el docstring de `vision/pose.py` (2026-10-24).
  - pyigtl (`/lassoan/pyigtl`): `TransformMessage(matrix, timestamp, device_name)` guarda la 4×4 como `float32`; `send_message(msg, wait=False)` encola y vuelve.

## Respuestas a las preguntas del spec (con P1–P7 del autor)

- **Formato del gráfico (P1 = c):** el bloque Mermaid de §9.1 es la fuente; la imagen `docs/img/004/mapa_proyecto.png` se exporta de ese bloque con `mermaid-cli` y nunca se edita a mano. PNG y no SVG: el SVG de `mmdc` pone los textos en `foreignObject`, que algunos visores no dibujan; el PNG se ve en todas partes. Cómo se genera y la dependencia: ver «La imagen del mapa» abajo y P8.
- **Dónde vive (P2 = c):** una sección nueva, **§9 · Cómo funciona: de la cámara a Slicer**, al final de `ARCHITECTURE.md`. Va al final y no después de §2 para no renumerar §3–§8, que se citan por número en `docs/`, `memory.md`, los specs y el código. Sus apartados: §9.1 el mapa, §9.2 detección → pose paso a paso, §9.3 el ejemplo resuelto, §9.4 el glosario, §9.5 las fuentes de cada número.
- **Cómo no se repite lo que ya dice `ARCHITECTURE.md`:** §1–§8 siguen siendo el «qué» (contratos, opciones de CLI, números de rendimiento, árbol); §9 es el «cómo y por qué» para el autor y no copia nada de eso: lo cita por sección («ver §3.5»). En concreto: el detalle de `WebcamBackend.open` se cita a §3.1; las opciones del tracker, a §3.2 y §6; el techo de ~65 Hz, a §3.5; la convención de esquinas se nombra y se cita a §7, y §9.2 solo añade por qué importa el orden. §2 conserva su dibujo de 6 cajas (la vista de un vistazo) y gana una línea que remite a §9.1 (el mapa con archivo por caja y lo que pasa por cada flecha). §4 no se toca.
- **El índice de `ARCHITECTURE.md`:** hoy no tiene; `CLAUDE.md` §1 pide consultarlo «primero su índice». Se añade un bloque «Índice» tras la cabecera, una línea por sección (§1–§9) y por apartado de §9 (§9.1–§9.5), con lo que contiene. Así el archivo, que pasará de ~39 KB a ~60–65 KB, se sigue leyendo por partes. La prueba comprueba que el índice nombra §9.1–§9.5.
- **Nivel (P4 = a):** intuición primero, una fórmula por paso como mucho, cada paso con los números del ejemplo. Matemática explícita: la proyección pinhole (u = fx·X/Z + cx), qué corrige la distorsión, qué busca el PnP, las dos soluciones de un cuadrado plano (por qué se descarta z ≤ 0) y rvec → matriz (Rodrigues) sin derivarlo. Dos comprobaciones a mano: Z ≈ fx·80 / lado en px, y la escala de B55 (las mismas esquinas con 98.6 mm dan una t 98.6/80 veces mayor y la misma rotación).
- **El ejemplo (P5 = a):** `tests/data/marker0_gs1_frames/frame_00480.png` en el documento; la prueba recorre los 3 frames de gs1 y los 3 de gs2. Script en `codigo/diagnostics/explain_pose.py`, con los argumentos explícitos (principio 7); la figura solo con `--output-image`.
- **La prueba de fidelidad (ajustada a P2 = c):** el alcance es solo §9, entre las marcas `<!-- como-funciona:inicio -->` y `<!-- como-funciona:fin -->` (el resto de `ARCHITECTURE.md` usa otras formas, como `vision.detection`, y nombra lo archivado; no se le exige la convención). Dentro de §9, toda referencia a código va entre comillas invertidas como `ruta.py` o `ruta.py:Símbolo` (ruta relativa a `codigo/`; `Símbolo` puede ser `Clase.método`). La prueba busca ese patrón, comprueba con `ast` (sin importar, así vale para `slicer/*.py`) que el archivo existe fuera de `historico/` y que el símbolo está definido; cada caja `ID["…"]` del Mermaid de §9.1 lleva al menos una referencia; una prueba negativa comprueba que el verificador falla con un nombre inventado. Además: el sha256 del bloque Mermaid de §9.1 es el que se guardó al exportar la imagen (si alguien cambia el Mermaid y no reexporta, falla); el bloque del ejemplo es la salida del script; el índice nombra §9.1–§9.5; ninguna línea de `ARCHITECTURE.md` pasa de 2 000 caracteres; `docs/img/004/` pesa < 200 KB.
- **Las fases (P7 = a):** cuatro, en el orden en que se le enseña al autor: el mapa (con su imagen), el ejemplo, la explicación, la lectura y el cierre.

## La imagen del mapa (P1 = c, P6 = a)

- **P9: SVG** (2026-10-26, `clarify.md`): la imagen es `docs/img/004/mapa_proyecto.svg` y no `.png` (el PNG de ~570 × 1400 px no se leía), el mapa va de izquierda a derecha y la prueba comprueba que es un SVG; donde abajo dice `.png` del mapa, léase `.svg`. El riesgo de `foreignObject` de arriba sigue: se ve al abrir el SVG exportado en GitHub y VS Code.
- **La herramienta:** `@mermaid-js/mermaid-cli` (`mmdc`), la oficial de Mermaid: dibuja el mismo Mermaid que GitHub y VS Code, sin reescribir el gráfico en otro formato. Es de Node.js, no de Python: no va al venv ni a `requirements.txt` como paquete, y por eso se propone ADR-032. Se fija una versión exacta (la que se use en la fase 1, anotada en el ADR y en la cabecera del script), y se llama con `npx -y -p @mermaid-js/mermaid-cli@<versión> mmdc …`: queda en la caché de npm del usuario, nada dentro del repo (ni `node_modules/` ni `package.json`).
- **El navegador:** `mmdc` necesita un Chromium. Se usa el Edge que ya está, con un `puppeteerConfigFile` temporal (`executablePath`) y `PUPPETEER_SKIP_DOWNLOAD=1` para que no baje otro navegador. Si con Edge falla, la alternativa es dejar que puppeteer baje su Chromium a la caché del usuario (cientos de MB, fuera del repo); se decide en P8 y se anota en el reporte.
- **Quién la corre:** solo hace falta al cambiar el Mermaid de §9.1. La suite no la necesita (no corre Node): comprueba el sha. Lo corre el agente de desarrollo en la fase 1 si los permisos le dejan correr `npx` con red; si no, la fase queda «parcial: falta la imagen» y el reporte le da al autor el comando de PowerShell exacto. Una negación no se rodea.
- **Lo que se versiona:** `docs/img/004/mapa_proyecto.png` y `docs/img/004/mapa_proyecto.sha256` (una línea: el sha256 del bloque Mermaid con finales LF y sin espacios al final de línea, y la versión de `mermaid-cli`). Es un archivo aparte para que el script no escriba en `ARCHITECTURE.md`.
- **Principio 5:** el Mermaid solo lleva nombres de archivos y funciones de `codigo/`; se dibuja en local, no sale a ningún servicio (no se usa mermaid.ink ni el editor web).
- **Principio 9:** el script llama a `mmdc` con tope de tiempo (`--timeout`, obligatorio) y no pisa una imagen existente sin `--overwrite`.

## Archivos

- `docs/ARCHITECTURE.md`: el índice nuevo tras la cabecera; §2, una línea que remite a §9.1; §6, el árbol con `docs\img\004\`, `diagnostics\explain_pose.py`, `diagnostics\export_map.py` y los dos tests nuevos; **§9 nueva** (§9.1 el Mermaid entre `<!-- mapa:inicio -->` y `<!-- mapa:fin -->`, la imagen exportada debajo con una línea «la misma figura, exportada para visores sin Mermaid», y una tabla caja → archivo/función → lo que entra y sale; §9.2; §9.3 con el bloque generado entre `<!-- ejemplo:inicio -->` y `<!-- ejemplo:fin -->` y la figura; §9.4; §9.5); la fecha de actualización. Ninguna línea de más de 2 000 caracteres.
- `docs/img/004/mapa_proyecto.png` y `docs/img/004/mapa_proyecto.sha256` (nuevos, fase 1).
- `docs/img/004/marker0_gs1_frame_00480.png` (nuevo, fase 2): la figura del ejemplo, recortada alrededor del marker. Las tres imágenes de la carpeta suman < 200 KB.
- `codigo/diagnostics/export_map.py` (nuevo, fase 1): extrae el Mermaid de §9.1, llama a `mmdc` y escribe la imagen y el `.sha256`.
- `codigo/diagnostics/explain_pose.py` (nuevo, fase 2): el ejemplo resuelto, como módulo con CLI.
- `codigo/tests/test_como_funciona.py` (nuevo, fase 1; la prueba del bloque del ejemplo, en la fase 2).
- `codigo/tests/test_explain_pose.py` (nuevo, fase 2).
- `codigo/requirements.txt`: en «Notas», una línea de comentario: el mapa de `ARCHITECTURE.md` §9.1 se exporta con `@mermaid-js/mermaid-cli@<versión>` (Node.js, fuera del venv; ADR-032), como ya se anota Slicer. Ningún paquete nuevo de Python.
- `docs/CONTEXT.md` §6: la meta 004 al cerrar. `memory.md` y `docs/BACKLOG.md` al cerrar cada fase (`cerrar-fase`). `docs/DECISIONS.md`: ADR-032 si se aprueba (lo escribe la dirección).
- `specs/004-como-funciona/resultados.md` (nuevo, fase 4): las dudas del autor y dónde se contestaron.
- **No se tocan** (principio 6, «Lo que no se toca» del spec): `codigo/tracker.py`, `codigo/camera/`, `codigo/vision/`, `codigo/transport/`, `codigo/profiles/`, `codigo/data/`, `codigo/slicer/`. Tampoco `codigo/tests/replay_util.py` ni `codigo/tests/data/`. Ya no se crea `docs/COMO_FUNCIONA.md`.

## Funciones y clases

En `codigo/diagnostics/export_map.py` (no importa nada del tracker; solo `hashlib`, `subprocess`, `tempfile`, `json`, `argparse`):

- `extract_mermaid(doc_text: str, start: str = "<!-- mapa:inicio -->", end: str = "<!-- mapa:fin -->") -> str`: el único bloque ```` ```mermaid ```` entre las dos marcas; aborta con un mensaje claro si faltan las marcas o hay cero o más de un bloque (principio 7).
- `mermaid_sha256(source: str) -> str`: el sha256 del bloque normalizado (finales LF, sin espacios al final de línea), para que un cambio de CRLF no lo invalide.
- `build_mmdc_command(mmdc: list[str], src: Path, out: Path, puppeteer_config: Path | None, background: str, width: int) -> list[str]`: el argv de `mmdc` (sin shell).
- `main(argv: list[str] | None = None) -> int`: CLI. Obligatorios `--doc`, `--output`, `--mmdc` (el comando, p. ej. la línea de `npx` con la versión fija), `--mmdc-version`, `--timeout`; opcionales `--browser` (ruta del navegador; genera el `puppeteerConfigFile` en un temporal), `--width`, `--overwrite`. Escribe la imagen y, junto a ella, el `.sha256` con el sha y la versión de `--mmdc-version`. Código distinto de 0 y mensaje si `mmdc` falla o pasa el tope.

En `codigo/diagnostics/explain_pose.py` (importa `profiles`, `vision.detection`, `vision.pose`, `vision.tracking.MarkerTracker` y `diagnostics.pose_log.load_recording`; no importa `tests/`):

- `explain_frame(dataset: Path, frames_dir: Path, frame: int, profile: Path, alt_size_mm: float | None = None) -> dict`: el ejemplo de un frame, de principio a fin. Lee el PNG en gris; detecta con `create_detector` + `detect` (lista blanca del perfil) y compara las esquinas con las grabadas (px); toma K y dist de la grabación y dice si su sha coincide con el `.yml` del perfil; pose cruda (`estimate_single_pose`) y su reproyección (`cv2.projectPoints`, px por esquina); pose filtrada como la hace el tracker (`MarkerTracker.process_corners` sobre las esquinas grabadas de los frames 0…frame−1 con sus tiempos, y la de este frame con las detectadas); su 4×4 contra la enviada en vivo (mm, °); la 4×4 en float32; la estimación a mano de Z; con `alt_size_mm`, la pose con ese tamaño y el cociente de escala (B55).
- `format_markdown(result: dict) -> str`: el bloque de números de §9.3, con decimales fijos (texto determinista).
- `draw_example(gray: np.ndarray, result: dict, K, dist, crop_px: int) -> np.ndarray`: la figura: esquinas numeradas c0–c3, ejes con `cv2.drawFrameAxes` (lado/2, como `tracker.draw_poses`), esquinas reproyectadas, recorte alrededor del marker.
- `main(argv: list[str] | None = None) -> int`: CLI. Obligatorios `--dataset`, `--frames-dir`, `--frame`, `--config`; opcionales `--alt-size-mm`, `--output-json`, `--output-markdown`, `--output-image`, `--crop-px`. No pisa una salida que ya existe. Sin cámara ni red.

En `codigo/tests/test_como_funciona.py`:

- `section_text(doc_text: str) -> str`: §9, entre `<!-- como-funciona:inicio -->` y `<!-- como-funciona:fin -->`.
- `find_code_refs(text: str) -> list[tuple[str, str | None]]`: las referencias `ruta.py` / `ruta.py:Símbolo` entre comillas invertidas.
- `symbol_defined(path: Path, symbol: str) -> bool`: por `ast`: función o clase de primer nivel, `Clase.método`, o nombre asignado en el módulo.
- `mermaid_nodes(text: str) -> list[str]`: las etiquetas de los nodos `ID["…"]` del bloque Mermaid de §9.1 (usa `export_map.extract_mermaid`).
- Pruebas: todas las referencias de §9 existen (0 inexistentes) y hay al menos 15; cada nodo del Mermaid tiene al menos una; la prueba negativa (`vision/pose.py:no_existe` y `vision/no_existe.py` dan falso); el sha del Mermaid actual = el de `docs/img/004/mapa_proyecto.sha256` y la imagen existe y se lee (`cv2.imread` no da `None`); `mermaid_sha256` cambia si cambia una etiqueta y no si cambia CRLF por LF; `docs/img/004/` < 200 KB; el índice nombra §9.1–§9.5; ninguna línea de `ARCHITECTURE.md` pasa de 2 000 caracteres; (fase 2) el bloque `ejemplo:inicio…fin` = `format_markdown(explain_frame(… gs1, 480 …))`.

En `codigo/tests/test_explain_pose.py`, parametrizado por cámara (gs1, gs2) y por los 3 frames de cada una:

- las esquinas detectadas en el PNG = las grabadas (≤ 1e-6 px, la tolerancia del replay);
- la 4×4 filtrada = la enviada en vivo en ese frame y = la de `marker0_<cam>_reference.npz` (`TOL_MM` y `TOL_DEG` del replay);
- la reproyección de la pose cruda por esquina, por debajo del tope que se fije con el número medido en la fase 2;
- con `alt_size_mm` = 98.6, la misma rotación (≤ 1e-6°) y una t 98.6/80 la de 80 (error relativo ≤ 1e-6): la propiedad que hace invisible B55;
- el sha de la K de la grabación = el del `.yml` del perfil.

## Fases

### Fase 1 · El mapa del proyecto, su imagen y su prueba — ligera

- **P9: SVG** (2026-10-26): `mapa_proyecto.svg` en vez de `.png`, `flowchart LR` con cada grupo de arriba abajo, «se lee» = empieza por `<svg` o `<?xml` y contiene `<svg`; una línea al pie de §9.1 nombra lo que queda fuera del mapa.

- **Entrega:** en `ARCHITECTURE.md`, el índice, la línea de §2 y §9 con §9.1 completo (Mermaid, imagen, tabla de cajas) y los títulos vacíos de §9.2–§9.5 entre las marcas; `codigo/diagnostics/export_map.py`; `docs/img/004/mapa_proyecto.png` y `.sha256`; `codigo/tests/test_como_funciona.py` sin la prueba del ejemplo; la nota en `requirements.txt`; §6 con lo nuevo.
- **El gráfico:** cuatro grupos. Panel: `gui/panel.py:Panel` → `gui/recipes.py:receta_tracker_sin_ventana` / `receta_tracker` → `gui/processes.py:Lanzador` (con `entorno_hijo`) → proceso `tracker.py:main`. Arranque: `profiles/__init__.py:load` → `transport/igtl.py:IgtlSender.wait_for_client` (Slicer antes que la cámara) → `camera/backend.py:create_backend` / `WebcamBackend.open` (K y dist del `.yml`) → `camera/grabber.py:FrameGrabber`. Por frame: frame BGR 1280×960 → gris → `vision/detection.py:detect` (4 esquinas en px, ID 0) → `vision/pose.py:estimate_single_pose` (rvec, tvec en mm) → `vision/filtering.py:PositionFilter` → `vision/pose.py:rvec_tvec_to_matrix` (4×4 en mm) → `transport/igtl.py:IgtlSender.send` (`Marker0ToTracker`, TCP 18944) → Slicer (`slicer/receive_marker0.py:ensure_connector`, nodo en la raíz). Aparte, la calibración que alimenta la cadena (`calibration/calibrate_camera.py` → `data/intrinsecos_gs1_1280x960.yml`) y los diagnósticos que la miran (`diagnostics/identify_ids.py`, `diagnostics/pose_log.py:PoseLog`, `slicer/receive_marker0.py:run`). Cada flecha dice lo que pasa por ella. Los nombres exactos se fijan al escribirlo, contra HEAD; si el Mermaid queda demasiado ancho para leerse en la imagen, se parte en `subgraph` de arriba abajo, sin quitar cajas.
- **Criterio:** la prueba de fidelidad con 0 referencias inexistentes y ≥ 15 referencias; cada caja del Mermaid con su referencia; la prueba negativa pasa; el sha del Mermaid = el del `.sha256`; la imagen existe, se lee y `docs/img/004/` < 200 KB (se anota su tamaño); el índice nombra §9.1–§9.5; ninguna línea de `ARCHITECTURE.md` > 2 000 caracteres. `py_compile` y conteo de líneas de `export_map.py`. La suite en verde con su tiempo, el replay de Marker0 en 0.0 mm / 0.0° y el selftest del panel. `git diff --stat 63bbdd8 -- codigo/tracker.py codigo/camera codigo/vision codigo/transport codigo/profiles codigo/data codigo/slicer` vacío.
- **Cómo se mide:** suite, y la exportación una vez (por el agente si puede, si no por el autor con el comando del reporte). Se le enseña al autor el gráfico (Mermaid en VS Code o GitHub y la imagen) antes de la fase 2: si algo no se entiende, se corrige aquí y se reexporta.
- **Peso:** ligera: un texto, un script corto de extraer y llamar a un comando, y pruebas de texto; nada de la cadena. El riesgo es de entorno (Edge con puppeteer), no de lógica: está en P8.

### Fase 2 · El ejemplo resuelto con un frame real — pesada

- **Entrega:** `codigo/diagnostics/explain_pose.py`, `codigo/tests/test_explain_pose.py`, la prueba del bloque del ejemplo en `test_como_funciona.py`, §9.3 con el bloque generado y `docs/img/004/marker0_gs1_frame_00480.png`.
- **Criterio:** sobre los 3 frames de gs1 y los 3 de gs2: esquinas detectadas = grabadas a 0.0 px (≤ 1e-6); pose filtrada = la enviada en vivo y = la referencia del replay a 0.0 mm / 0.0°; escala de B55 con cociente 98.6/80 = 1.2325 y rotación igual; la reproyección de la pose cruda, anotada en px (se espera ≲ 0.2 px, del orden del RMS de la calibración, 0.167 px). El bloque de §9.3 = la salida de `format_markdown`. `docs/img/004/` sigue < 200 KB con las dos imágenes (se anotan los dos tamaños). Suite, replay, selftest y el `git diff` de la cadena vacío. `py_compile` y conteo de líneas.
- **Riesgo conocido:** si las esquinas detectadas en el PNG no son idénticas bit a bit a las grabadas, la 4×4 podría diferir en más de 1e-9 mm. Si pasa, el script calcula la pose enviada con las grabadas (lo que hace el replay) y da aparte la diferencia que producen las detectadas; se anota y no cambia el criterio.
- **Cómo se mide:** suite. Sin cámara ni Slicer: solo datos de `codigo/tests/data/` (principio 5). Se le enseña al autor el ejemplo con sus números y la figura antes de escribir la explicación.

### Fase 3 · La explicación y el glosario — ligera

- **Entrega:** §9.2 (detección → pose, paso a paso, en español llano), §9.4 (glosario) y §9.5 (fuentes).
- **Contenido de §9.2, en este orden:** qué ve la cámara (el frame, MJPG, 1280×960, el hilo que se queda con el último; el cómo se abre, citado a §3.1); el gris y por qué; qué es un ArUco y qué hace el detector (umbral, contornos, cuadrados, los bits, la lista blanca); qué es una esquina y por qué importa el orden (la convención, citada a §7; con el orden cambiado el marker sale girado 90°, con el sentido invertido no hay pose coherente); K (de mm a px) y la distorsión (se corrige al calcular, no en la imagen); el PnP con IPPE_SQUARE (las dos soluciones; por qué se descarta z ≤ 0); por qué el tamaño del marker fija la escala (B55, con la comprobación del ejemplo); rvec, tvec y la 4×4; el 1-Euro (`min_cutoff` 2.0 y `beta` 0.05 del perfil; la orientación no se filtra); qué es `Marker0ToTracker` (la pose de Marker0 en el frame de la cámara, en mm, float32 por OpenIGTLink, en la raíz de Slicer, sin convertir; la cadena, citada a §4); y por qué Slicer ve ~65 Hz y no 90 (citado a §3.5 y B54, sin copiar sus números).
- **Glosario:** al menos fps de cámara, fps del bucle, saltados, ráfaga, tic de Windows (15.6 ms), sd z, replay, «no cambió», R2, IPPE_SQUARE, PnP, K, dist, rvec/tvec, 1-Euro, lista blanca, MSMF, MJPG, OpenIGTLink, conector, `Marker0ToTracker`, código de salida 3, `[Salida limpia]`, perfil, `.yml` de intrínsecos, RMS de reproyección. Si un término ya está definido en §3, el glosario da una línea y cita la sección.
- **Fuentes:** cada número cita el archivo o la medida: 80 mm (`profiles/tracker_config_gs1.yaml`, `markers.list`), K y dist (`data/intrinsecos_gs1_1280x960.yml`), 18944 (`igtlink.transforms_port` del perfil), los fps y los Hz (`specs/003-arquitectura-tracker/resultados.md`, fases 7, 7b y 8b), 0.167 px (el `.yml`), 98.6 mm (B55).
- **Criterio:** la prueba de fidelidad sigue en 0 inexistentes con las referencias nuevas; cada número de §9.2 y §9.4 tiene su fuente en §9.5 o al lado (la dirección lo revisa con una lista: 0 números sin fuente); 0 párrafos que copien un contrato u opción de §1–§8 en vez de citarlo (misma revisión); ninguna línea > 2 000 caracteres. Suite, replay, selftest y el `git diff` de la cadena vacío. Si el texto no toca el Mermaid, la imagen no se reexporta (la prueba del sha lo confirma).
- **Cómo se mide:** suite y lectura de la dirección con la lista de números y de citas.

### Fase 4 · Lectura con el autor y cierre de la meta — ligera

- **Entrega:** una sesión con el autor (sin cámara ni Slicer): lee §9 entera y marca lo que no entiende; cada duda se contesta en el texto de §9 (no en el chat) y se anota en `specs/004-como-funciona/resultados.md` (la duda, dónde se contestó, la fecha). Si una duda cambia el Mermaid, se reexporta la imagen. Si descubre algo mal en la cadena, va al BACKLOG y no se arregla (principio 6). Después, el cierre: `memory.md`, `docs/CONTEXT.md` §6, `docs/ARCHITECTURE.md` §6 y la fecha, `docs/BACKLOG.md` e índices.
- **Criterio:** 0 dudas abiertas en `resultados.md` (el autor lo confirma); la prueba de fidelidad, la del sha de la imagen y la del ejemplo en verde tras los cambios; suite con su tiempo, replay en 0.0 mm / 0.0°, selftest; `git diff` de la cadena vacío desde `63bbdd8`.
- **Cómo se mide:** sesión con el autor y suite. Puede necesitar más de una vuelta: la casilla se marca cuando el autor dice que no le queda ninguna duda.

### La cadena (principio 6)

Ninguna fase toca `tracker.py`, `camera/`, `vision/`, `transport/`, `profiles/`, `data/` ni `slicer/`. Lo que se añade (`diagnostics/export_map.py`, `diagnostics/explain_pose.py`, dos tests, texto e imágenes en `docs/`, un comentario en `requirements.txt`) no lo importa la cadena. La verificación, en cada fase: el `git diff --stat` de esas rutas contra `63bbdd8` vacío, la suite (con el replay de Marker0 a 0.0 mm / 0.0° y la detección a 0.0 px) y el selftest del panel. No hace falta sesión en vivo: la cadena en vivo es la que cerró la meta 003 (P04).

## Lo que va al BACKLOG

- **B56 · `slicer/receive_marker0.py` dice que `pyigtl` bloquea si Slicer no está conectado** (baja): su docstring cita `CONTEXT.md` §4.5 de antes de ADR-028; hoy el tracker espera con tope y aborta. Es un archivo de la cadena que esta meta no toca. Visto al planear.
- **B57 · El `.json` de procedencia de las referencias del replay nombra rutas de `iter4/`** (baja): `marker0_gs{1,2}_reference.json` dicen `profile: iter4/…` y `calibration_file: …\codigo\iter4\data\…`, de antes de ADR-027. Los sha siguen valiendo; solo despista. Regenerar la referencia es un cambio visible y a propósito; no entra aquí.
- Si en la fase 1 Edge no sirve para `mmdc` y se usa el Chromium de puppeteer (P8 = b): «la exportación del mapa baja un navegador a la caché del usuario» (baja), con su tamaño.
- Lo que la lectura del autor descubra en la cadena (fase 4), con su prioridad.

## ADR que se proponen

- **ADR-032 · El mapa de `ARCHITECTURE.md` §9.1 se exporta con `mermaid-cli`, fuera de `requirements.txt`, y una prueba lo ata al código y al Mermaid.** Qué: el Mermaid de §9.1 es la fuente; la imagen se exporta con `@mermaid-js/mermaid-cli` a una versión fija, por `npx` y con el Edge instalado (o lo que diga P8); es una herramienta de documentación de Node.js, no una dependencia del sistema, y se anota en «Notas» de `requirements.txt` como Slicer; el sha256 del Mermaid se guarda junto a la imagen y la suite lo compara; las referencias de §9 van como `ruta.py:Símbolo` y la suite comprueba que existen. Por qué: P1 = c pide imagen y fuente, y la regla del método es que solo vale lo que declara `requirements.txt` (`CLAUDE.md` §2): una herramienta fuera de él, aunque sea de documentación, es una excepción que se decide por escrito. La prueba evita que el dibujo, la imagen y el código se separen al renombrar algo (principio 8). Sigue haciendo falta un ADR solo por esto: el de la lista de fuentes (el ADR-032 de la versión 1, P3) ya no aplica.

## Preguntas abiertas

- **P8 · ¿Con qué se exporta la imagen del mapa?** (a) `mermaid-cli` a versión fija por `npx`, con el Edge instalado y sin bajar navegador; si Edge no le sirve, se para y se pregunta (recomendada). (b) Como (a), pero si Edge falla se deja que puppeteer baje su Chromium a la caché del usuario (cientos de MB, fuera del repo) sin volver a preguntar. (c) Sin Node: el autor exporta a mano desde un visor de Mermaid y la prueba solo vigila el sha; sin dependencia, pero no se puede repetir igual y depende de una persona.

## Títulos de commit

- Fase 1: «Dibuja el mapa del proyecto con su imagen y su prueba de fidelidad (meta 004, fase 1)»
- Fase 2: «Añade el ejemplo resuelto de detección a pose (meta 004, fase 2)»
- Fase 3: «Explica la detección y la pose y añade el glosario (meta 004, fase 3)»
- Fase 4: «Cierra la meta 004 · Cómo funciona el tracker»
