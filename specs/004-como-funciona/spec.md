# Meta 004 — Cómo funciona el tracker: gráfico y explicación de detección → pose

## Por qué

El autor lo pidió al empezar la meta 003 (2026-10-23): quiere un gráfico del proyecto, desde el panel, la cámara y los cálculos hasta la pose en Slicer, y entender la lógica de detección → pose. Lo dejó para después de la arquitectura y la optimización, y lo eligió como meta siguiente al cerrar la 003 (2026-10-26). Hoy el código está ordenado por responsabilidad (ADR-027) y la cadena publica solo `Marker0ToTracker` (ADR-026), así que el dibujo ya no va a cambiar de forma en cuanto se haga. La siguiente meta grande, instrumento y punta (ADR-025), se apoya en entender bien esta cadena.

## Qué se construye

1. **El gráfico del proyecto:** de dónde sale cada cosa y adónde va. El panel y lo que lanza; la cámara (perfil, intrínsecos, hilo de captura); la visión (gris, detección ArUco, esquinas, pose, filtro); el envío por OpenIGTLink; Slicer y su escena. Cada caja con el archivo o el módulo de `codigo/` que la hace, y cada flecha con lo que pasa por ella (un frame, cuatro esquinas en px, una matriz 4×4 en mm).
2. **La explicación de detección → pose, para el autor:** en español llano, paso a paso, con el porqué de cada paso. Qué es una esquina y por qué importa su orden; qué hacen la matriz de la cámara (K) y la distorsión; cómo de cuatro esquinas y el tamaño del marker sale una posición y una orientación; por qué el tamaño del marker fija la escala (lo de B55); qué hace el filtro 1-Euro; qué es `Marker0ToTracker` en Slicer y en qué unidades llega.
3. **Un ejemplo resuelto con datos reales:** un frame grabado de Marker0 (`codigo/tests/data/marker0_*`, ya en git), seguido de principio a fin con sus números: las esquinas detectadas, la pose calculada y la matriz que se enviaría. Lo reproduce un script corto que cualquiera puede correr.
4. **Un glosario corto** con los términos que el autor encuentra en logs y docs (fps de cámara y de bucle, ráfagas, tic de Windows, sd z, replay, R2…).

## Criterio de cierre

- **El gráfico es fiel al código:** cada caja nombra un archivo o una función que existe en HEAD, y una prueba de la suite lo comprueba (si se renombra algo, la prueba falla). 0 nombres inexistentes.
- **El ejemplo resuelto reproduce la cadena:** el script, sobre el frame grabado, da la misma pose que el replay de Marker0 de la suite, a 0.0 mm / 0.0° (la tolerancia del replay). Lo comprueba una prueba.
- **La explicación se entiende:** el autor la lee entera y marca lo que no entendió; la meta cierra con 0 dudas abiertas (cada duda, contestada en el texto, no en el chat). Se hace en una sesión con el autor; las dudas y su respuesta se anotan en `resultados.md`.
- **Cada número de la explicación tiene su fuente:** el tamaño del marker, K, la distorsión, el puerto, los fps y los Hz citan el archivo o la medida de donde salen (perfil, `.yml`, `resultados.md` de la 003).
- La suite en verde con su tiempo, el replay de Marker0 en 0.0 mm / 0.0° y el selftest del panel, como en la meta 003.
- Sin cámara ni Slicer: la meta no necesita sesión en vivo, salvo que el plan proponga una captura nueva para el ejemplo (y entonces lo dice).

## Lo que no se toca

- El código de la cadena: `tracker.py`, `camera/`, `vision/`, `transport/`, `profiles/`, `data/` y los scripts de `codigo/slicer/`. Su `git diff` tiene que salir vacío. Si al explicar se encuentra algo mal, va al BACKLOG; no se arregla en esta meta (principio 6).
- Lo que se explica es lo que hay hoy (HEAD al empezar la meta), no lo que habrá: instrumento, punta, registro y navegación quedan para la meta siguiente.
- Ninguna dependencia nueva salvo que el plan la proponga con su porqué (p. ej., para dibujar el gráfico).
- Los datos de paciente (principio 5): el ejemplo usa solo los frames de Marker0 de `codigo/tests/data/`.

## Preguntas que el plan tiene que contestar

- **El formato del gráfico:** Mermaid dentro del Markdown (se ve en GitHub y VS Code, y se diffea), un SVG o PNG generado por un script, o los dos. Cuál se mantiene mejor y cuál se lee mejor. Si hace falta una dependencia, cuál y por qué.
- **Dónde vive:** un `docs/COMO_FUNCIONA.md` nuevo, una sección de `docs/ARCHITECTURE.md`, o los dos (el gráfico en ARCHITECTURE y la explicación aparte). Cómo se evita repetir lo que ya dice `ARCHITECTURE.md`.
- **El nivel de la explicación:** cuánta matemática (proyección pinhole, PnP, rotaciones) y cuánta intuición; con qué figuras (p. ej., el frame con las esquinas y los ejes dibujados).
- **El ejemplo:** qué frame (gs1, gs2 o uno de cada uno), dónde vive el script (`diagnostics/`?) y si dibuja una imagen con las esquinas y los ejes.
- **La prueba de fidelidad del gráfico:** cómo se comprueba que los nombres del gráfico existen sin atar la prueba al formato.
- **Las fases:** cuántas y su peso (ADR-022), y en qué orden se le enseña al autor lo que se va haciendo.
