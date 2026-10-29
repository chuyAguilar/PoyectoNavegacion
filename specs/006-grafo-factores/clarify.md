# Aclaraciones — Meta 006 · Grafo de factores óptico-inercial (primero, las dos cámaras)

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

P1 a P7 son las que el autor ya contestó antes de que existiera este archivo; se copiaron de `memory.md` («Meta 006») el 2026-10-29. Contexto: la propuesta del autor (2026-10-26) es un grafo de factores con GTSAM, porque Ceres no tiene bindings oficiales de Python, que fusione las poses ArUco de gs1 y gs2 con un IMU, modular para pasar más adelante a puntos IR por PnP.

## P1 · Dónde va el IMU

- **Opciones:** en el instrumento (las cámaras fijas: tracking óptico-inercial); en las cámaras (VIO de la cámara).
- **Respuesta del autor:** en el instrumento; las cámaras son fijas, así que es tracking óptico-inercial, no VIO de la cámara.
- **Fecha:** 2026-10-26.

## P2 · Cuándo empieza la meta

- **Opciones:** ya; después de cerrar la meta 004.
- **Respuesta del autor:** después de cerrar la meta 004.
- **Fecha:** 2026-10-26.

## P3 · Qué fuentes se usan

- **Opciones:** Context7; el GitHub MCP; artículos.
- **Respuesta del autor:** GitHub MCP + Context7 + artículos (2026-10-26). El 2026-10-29 añadió la monografía `documentos/tecnicos/Factor Graphs for robot perception.pdf` (Dellaert y Kaess). El GitHub MCP no estaba instalado el 2026-10-29 (`mcpServers` vacío, sin `.mcp.json`); la dirección le dio al autor los pasos (token de solo lectura, ámbito local o de usuario, nunca `--scope project`). En la sesión que escribió el plan no estaba disponible.
- **Fecha:** 2026-10-26 y 2026-10-29.

## P4 · Dónde se prueba antes de tocar el tracker

- **Opciones:** scripts con prueba; notebooks; según haga falta.
- **Respuesta del autor:** scripts con prueba o notebooks, según haga falta.
- **Fecha:** 2026-10-26.

## P5 · El alcance de esta meta

- **Opciones:** cámaras e IMU; solo las dos cámaras.
- **Respuesta del autor:** solo cámaras (gs1 + gs2); el IMU va a una meta posterior.
- **Fecha:** 2026-10-29.

## P6 · La estructura rígida de las dos cámaras

- **Opciones:** la diseña la meta; la diseña el autor aparte.
- **Respuesta del autor:** la estructura (barra con agujeros cada X mm) la diseña el autor por su cuenta y después pasa sus características; la dirección le dio lo que tiene que cumplir. La meta no depende de ella para avanzar.
- **Fecha:** 2026-10-29.

## P7 · Los números de cierre

- **Opciones:** los del autor.
- **Respuesta del autor:** gs1 y gs2 coinciden con el marcador quieto (pose de gs2 llevada a gs1 con los extrínsecos) a < 0.5 mm y < 0.2°; la fusión baja la sd en reposo al menos un 30 % frente a la mejor cámara sola; al tapar una cámara 5 s, la pose no se pierde ni salta más de 0.5 mm.
- **Fecha:** 2026-10-29.

## P8 · Cómo se instala gtsam en Windows, si PyPI no tiene rueda para Windows en ninguna versión

- **Opciones:** (a) recomendada: un entorno de conda-forge (miniforge) con Python 3.11 y `gtsam 4.3.0` (hay construcción win-64 py311, con numpy 2), y el resto de `requirements.txt` por pip; se mide primero en una carpeta aparte, sin tocar `.venv` (fase 1), y si la suite y el replay pasan, el proyecto se muda con un ADR (cambia `CLAUDE.md` §5 y `docs/EQUIPO.md`); coste: numpy 2 en vez de 1.26, y open3d o pyorbbecsdk2 pueden no instalar (B45). (b) Compilar gtsam 4.3.0 desde fuente con Visual Studio dentro de `.venv`: el entorno no cambia, pero la compilación es larga y cada compañero tendría que repetirla o recibir la rueda. (c) Sin gtsam: el mismo grafo (factores de pose y de movimiento, ventana fija) sobre `scipy.optimize.least_squares`, ya en `requirements.txt`, con la misma interfaz `FactorSource`; sin dependencia nueva, pero se aparta de lo que propuso el autor y la meta del IMU tendría que escribir la preintegración que GTSAM ya trae. (d) `pyceres 2.6` (rueda cp311 win_amd64, de COLMAP): Ceres sin ser oficial, con factores en Python más lentos.
- **Respuesta del autor:** (a) un entorno de conda-forge (miniforge) con Python 3.11 y gtsam 4.3.0, medido primero en una carpeta aparte sin tocar `.venv`. La dirección comprobó por Context7 (documentación de GTSAM) que sus ruedas de Python solo se construyen para Linux y macOS.
- **Fecha:** 2026-10-29

## P9 · Un proceso o tres

- **Opciones:** (a) recomendada: un proceso con las dos cámaras, un hilo de captura y uno de detección por cámara; la hora es del mismo reloj y la fusión no espera a la red; coste: código nuevo en `fusion/` y medir si el USB y la CPU dan para dos cámaras a 90 fps (fase 2). (b) Dos trackers (uno por cámara, cada uno en su puerto) y un fusionador que los recibe por OpenIGTLink y publica `Marker0ToTracker`: reusa `tracker.py`, pero la hora viaja en ráfagas de 15.6 ms (B54), hacen falta dos puertos más y el panel tiene que coordinar tres procesos.
- **Respuesta del autor:** probar las dos arquitecturas (un proceso con las dos cámaras, y dos trackers con un fusionador) y decidir con números. El autor se inclina por dos trackers, pero quiere validar o justificar la decisión con medidas: el plan define qué se mide en las dos (fps, desfase entre cámaras, latencia, carga de CPU, complejidad del arranque) y con qué umbral se elige.
- **Fecha:** 2026-10-29

## P10 · Cómo se lanza la fusión

- **Opciones:** (a) recomendada: `python -m tracker --fusion profiles\fusion_gs1_gs2.yaml`, con `--fusion` excluyente con `--config`; `main` delega en `fusion.runner` antes de leer ningún perfil, así que sin `--fusion` el bucle no cambia; es lo que dice el spec («la fusión en el tracker»). (b) Una entrada aparte, `python -m fusion.run --fusion …`, y `tracker.py` sin tocar: el «no cambió» es trivial, pero hay dos comandos de tracker.
- **Respuesta del autor:** (a) `python -m tracker --fusion profiles\fusion_gs1_gs2.yaml`, excluyente con `--config`; sin `--fusion` el bucle no cambia. Si gana la arquitectura de dos trackers, el plan adapta el lanzamiento manteniendo esa idea (un comando, el tracker de hoy intacto sin la opción).
- **Fecha:** 2026-10-29

## P11 · Qué es «Tracker» con la fusión encendida

- **Opciones:** (a) recomendada: el frame de la cámara gs1, que ya lo era con gs1 sola; `Marker0ToTracker`, el 18944 y la jerarquía no cambian; ADR y verificación en vivo con Slicer en la fase 7. (b) Un frame propio del montaje (por ejemplo, el de la estructura cuando exista): cambia lo que significa «Tracker» para todo lo que ya se midió y necesita otro ADR.
- **Respuesta del autor:** (a) el frame de gs1; `Marker0ToTracker`, el 18944 y la jerarquía no cambian; ADR y verificación en vivo con Slicer.
- **Fecha:** 2026-10-29

## P12 · Cómo se calibran los extrínsecos

- **Opciones:** (a) recomendada: `stereoCalibrate` con `CALIB_FIX_INTRINSIC` y el tablero de la meta 002 (9×6, 24.86 mm) visto por las dos a la vez, ≥ 15 parejas y 3 de control, validado aparte por la reproyección de control, la distancia triangulada del tablero y Marker0 en posiciones que no entraron (fase 4). (b) Marker0 en N posiciones (T_gs1←gs2 = media de T_gs1←M · T_gs2←M⁻¹): sin tablero, pero hereda el sesgo de profundidad de cada cámara y la validación con Marker0 deja de ser independiente. (c) Las dos, y comparar: más tiempo en vivo.
- **Respuesta del autor:** (c) las dos: tablero con `stereoCalibrate` y Marker0 en varias posiciones, y comparar.
- **Fecha:** 2026-10-29

## P13 · Cómo se emparejan las medidas sin hora de hardware

- **Opciones:** (a) recomendada: por hora (`perf_counter` del hilo de captura, como hoy), la más cercana dentro de medio periodo (5.5 ms a 90 fps); se mide el desfase δ con el marker en movimiento y, si |δ| > 2 ms, el perfil lleva una corrección fija por cámara. (b) Un nodo por medida, sin emparejar, con el factor de movimiento entre medidas de cámaras distintas: más fino moviéndose, más nodos (~180/s) y más coste; al BACKLOG si (a) se queda corto.
- **Respuesta del autor:** probar los dos métodos (emparejar por hora dentro de medio periodo, y un nodo por medida) y comparar con números.
- **Fecha:** 2026-10-29

## P14 · El 1-Euro con la fusión y cómo se mide el 30 %

- **Opciones:** (a) recomendada: las cámaras entregan la pose cruda; la fusión suaviza con su factor de movimiento; el 1-Euro, después de la fusión y apagado por defecto; el 30 % se mide sin ningún suavizado temporal en ningún lado (fusión por instante frente a la mejor cámara cruda), para que la mejora sea de geometría y no de filtro; aparte se reporta lo publicado de cada lado. (b) Comparar lo publicado: cada cámara con su 1-Euro frente a la fusión con su factor de movimiento; más cerca de lo que ve Slicer, pero un suavizado fuerte cumpliría el 30 % a costa de retraso.
- **Respuesta del autor:** (a) el 30 % se mide sin ningún suavizado temporal (fusión por instante frente a la mejor cámara cruda); el 1-Euro va después de la fusión y apagado por defecto.
- **Fecha:** 2026-10-29

## P15 · Los topes de tiempo real con la fusión encendida

- **Opciones:** (a) recomendada: la actualización del grafo con p95 ≤ 2 ms fuera de línea y ≤ 3 ms en vivo (máx. 5 ms); sin ventana ≥ 85 poses fusionadas/s con las dos cámaras ≥ 85 fps; con ventana (una sola, con las dos vistas a media resolución) ≥ 50/s; Slicer ≥ 50 Hz (su techo es ~65, B54). La meta 003 dio, con una cámara, 89.9 y 88.8 fps sin ventana y 61.7 y 55.2 con ventana. (b) Otros números del autor.
- **Respuesta del autor:** (a) los propuestos: actualización del grafo con p95 ≤ 2 ms fuera de línea y ≤ 3 ms en vivo (máx. 5 ms); sin ventana ≥ 85 poses fusionadas/s; con ventana ≥ 50/s; Slicer ≥ 50 Hz.
- **Fecha:** 2026-10-29

## P16 · Dónde y cuánto se mide la coincidencia de las cámaras

- **Opciones:** (a) recomendada: 5 posiciones fijas de Marker0 a ~35–40 cm (centro y cuatro desplazadas ~8 cm, dos de ellas inclinadas ~30°), 30 s cada una (≥ 2000 parejas), y cuenta la peor posición. (b) 3 posiciones y la media de las tres: menos tiempo en vivo, pero una posición mala queda escondida.
- **Respuesta del autor:** (a) 5 posiciones fijas de Marker0 a ~35–40 cm, 30 s cada una, y cuenta la peor.
- **Fecha:** 2026-10-29

## P17 · Si las dos cámaras no caben en el mismo hub USB

- **Opciones:** (a) recomendada: si en la fase 2 las dos juntas bajan de 85 fps y la causa es el USB, se permite pasar gs2 a otro puerto raíz y medir de nuevo su `usb_port_windows` en su perfil (ADR-024 lo admite con su medición). (b) No mover nada: la fase para con el número y se decide entonces.
- **Respuesta del autor:** no se mueve nada: las cámaras van como se calibraron, la cámara 1 en el puerto 1 y la cámara 2 en el puerto 2 (los `usb_port_windows` de sus perfiles). Si con las dos a la vez no llegan a 85 fps, la fase para con el número y el autor decide.
- **Fecha:** 2026-10-29

## P18 · El nombre del archivo de extrínsecos

- **Opciones:** (a) recomendada: `data/extrinsecos_gs1_gs2_pinzas.yml`, con el montaje en el nombre; la estructura tendrá el suyo (`_estructura.yml`) y el perfil de fusión nombra el vigente. (b) `data/extrinsecos_gs1_gs2.yml`, con el montaje solo dentro del archivo: un solo nombre, pero el de las pinzas se pisa o se archiva al llegar la estructura.
- **Respuesta del autor:** (a) `data/extrinsecos_gs1_gs2_pinzas.yml`, con el montaje en el nombre; la estructura tendrá `_estructura.yml`.
- **Fecha:** 2026-10-29

## P19 · Si pierde la arquitectura de dos trackers, qué pasa con `--feed`

- **Opciones:** (a) recomendada: se retira en la fase 4b (`--feed`, el `timestamp` de `IgtlSender.send`, `fusion/feeds.py`, `collector.py` y `clockcheck.py`, con sus pruebas), y `tracker.py` y `transport/igtl.py` vuelven al texto de antes de la fase 3; sus números quedan en `resultados.md` y una entrada en el BACKLOG; coste: si algún día se vuelve a B (más cámaras, otra máquina), se rehace desde el commit de la fase 3. (b) Se deja como diagnóstico, apagado: no se pierde nada, pero el tracker carga una opción que nada usa y la suite la sigue probando.
- **Respuesta del autor:** pendiente.
- **Fecha:** —

## P20 · Con un nodo por medida, cómo cuenta el 30 % del criterio 2

- **Opciones:** (a) recomendada: el 30 % se mide siempre como dice P14, por instante emparejado y sin factor de movimiento, frente a la mejor cámara cruda, gane el método de sincronía que gane; con un nodo por medida cada variable tiene un solo factor y sin factor de movimiento no hay fusión que medir, así que su sd publicada se reporta aparte, sin aprobado o suspenso. (b) Si gana el nodo por medida, el 30 % se mide sobre lo publicado, con su factor de movimiento: más cerca de lo que ve Slicer, pero mide también suavizado, que es lo que P14 quiso dejar fuera.
- **Respuesta del autor:** pendiente.
- **Fecha:** —

## P21 · El orden frente a la Jetson (pregunta de la dirección)

- **Opciones:** (a) la Jetson primero (meta 007) y la 006 después, sobre la Jetson; (b) la 006 primero, en el PC, y mudar después; (c) las dos juntas en una meta.
- **Respuesta del autor:** (a). La 006 queda en espera con este plan sin autorizar; al retomarla, `/planear 006-grafo-factores` lo rehace para la Jetson (P8 cambia: allí GTSAM se instala por pip).
- **Fecha:** 2026-10-29
