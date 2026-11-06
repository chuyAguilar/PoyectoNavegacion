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
- **Respuesta del autor:** sin objeto (P28 a): con P22 ya no hay dos arquitecturas que comparar.
- **Fecha:** 2026-11-05

## P20 · Con un nodo por medida, cómo cuenta el 30 % del criterio 2

- **Opciones:** (a) recomendada: el 30 % se mide siempre como dice P14, por instante emparejado y sin factor de movimiento, frente a la mejor cámara cruda, gane el método de sincronía que gane; con un nodo por medida cada variable tiene un solo factor y sin factor de movimiento no hay fusión que medir, así que su sd publicada se reporta aparte, sin aprobado o suspenso. (b) Si gana el nodo por medida, el 30 % se mide sobre lo publicado, con su factor de movimiento: más cerca de lo que ve Slicer, pero mide también suavizado, que es lo que P14 quiso dejar fuera.
- **Respuesta del autor:** (a), por P28.
- **Fecha:** 2026-11-05

## P21 · El orden frente a la Jetson (pregunta de la dirección)

- **Opciones:** (a) la Jetson primero (meta 007) y la 006 después, sobre la Jetson; (b) la 006 primero, en el PC, y mudar después; (c) las dos juntas en una meta.
- **Respuesta del autor:** (a). La 006 queda en espera con este plan sin autorizar; al retomarla, `/planear 006-grafo-factores` lo rehace para la Jetson (P8 cambia: allí GTSAM se instala por pip).
- **Fecha:** 2026-10-29

## P22 · Dónde corre cada parte, al retomar la meta (pregunta de la dirección)

- **Contexto:** en Windows las dos cámaras no caben en el mismo concentrador USB 2.0 del frente: la segunda no recibe vídeo, `0x800718CF`, «sin ancho de banda» (meta 007, fase 7b, P-7b-B, B5; `Claude outputs/fases/007/por-que-atorados-7b.md`). En la Jetson corren las dos a la vez, a 63.2 fps de bucle cada una, pero con la CPU al 95.5 % (meta 007, P-7; B91).
- **Opciones:** (a) todo en el PC, con las dos cámaras en enlaces USB separados; (b) la Jetson detecta (las dos cámaras, ArUco y PnP) y el PC fusiona y habla con Slicer; (c) todo en la Jetson.
- **Respuesta del autor:** (b): la Jetson detecta y el PC fusiona. La meta 007 se pausa y la 006 pasa a ser la activa. El plan se rehace para (b), y su primera fase es una grabación con las dos cámaras en la Jetson más un experimento fuera de línea en el PC, que muestre si la fusión con dos cámaras y un grafo reduce el jitter frente a cada cámara sola. Lo quiere ver ya.
- **Fecha:** 2026-11-05

## P23 · Grabar ya, antes del plan (pregunta de la dirección)

- **Opciones:** grabar ya el dataset con lo que existe (los dos trackers en la Jetson con `--record`, sin código nuevo, con el `correr.ps1` de la regla de `CLAUDE.md` §4); o grabar cuando el plan esté autorizado, con el protocolo que fije.
- **Respuesta del autor:** grabar ya, con lo que existe. El plan reutiliza esas grabaciones si cumplen lo que fije; si no, se graba otra vez.
- **Fecha:** 2026-11-05

## P24 · Qué viaja de la Jetson al PC, y por qué canal (replan del 2026-11-05)

- **Opciones:** (a) recomendada: por UDP (biblioteca estándar, como `clock_offset.py`), un datagrama por cámara y por frame con las esquinas de Marker0, la pose cruda de IPPE con su error, la otra solución si la hay, la hora de captura y una secuencia; ~200 bytes, ~25 KB/s con las dos; deja usar factores de reproyección y ver cada pérdida; coste: una opción `--feed` en `tracker.py` (principio 6, ADR G3), un formato versionado y una regla de entrada en el cortafuegos del PC que pone el autor; su latencia se mide en la fase 3 frente a los 7.6 ms añadidos p95 de OpenIGTLink (meta 007, fase 6). (b) Solo la pose por OpenIGTLink, con lo que ya existe (`--igtl-iface`; el PC como cliente de los dos puertos): nada nuevo en la Jetson, pero sin esquinas ni la otra solución de IPPE, la matriz en float32, y el cliente de `pyigtl` guarda solo el último mensaje de cada nombre, así que pierde medidas en ráfaga. (c) MQTT: un broker (mosquitto) que instalar y mantener en una de las dos máquinas, `paho-mqtt` como dependencia en las dos, TCP y un salto más; da varios suscriptores, que hoy no hacen falta; latencia sin medir. La fase 1 dice si las esquinas cambian el número (factores de reproyección frente a los de pose) y cuántas medidas salva la otra solución de IPPE.
- **Respuesta del autor:** (a): por UDP, un datagrama por cámara y por frame con las esquinas, la pose cruda, la otra solución de IPPE, la hora de captura y una secuencia.
- **Fecha:** 2026-11-05

## P25 · Dónde corre GTSAM para la fase 1 y para el fusionador (replan del 2026-11-05)

- **Opciones:** (a) recomendada: un entorno de miniforge solo para la fusión, fuera del repo, con Python 3.11 y `gtsam 4.3.0` de conda-forge (comprobado el 2026-11-05: `win-64`, py311, numpy 2; PyPI sigue sin rueda para Windows), más numpy, scipy, opencv-python, pyyaml, pyigtl, matplotlib y pytest; `.venv` no cambia y sigue siendo el del tracker, el panel y la suite; el autor instala miniforge (por usuario; sin administrador, hipótesis) y `desarrollo` crea el entorno desde `codigo/fusion/environment.yml`; la parte A de la fase 1 no lo necesita. Es P8 (a) acotado a la fusión, sin mudar el proyecto. (b) En la Jetson, donde gtsam 4.3.0 ya está en `~/.venvs/prueba-gtsam`: el guardián solo lanza su lista blanca en el venv del tracker, así que hay que cambiarlo y reinstalarlo con sudo, y la CPU ya va al 95.5 % con los dos trackers (B91); sirve para lo fuera de línea, no para el fusionador en vivo, que va en el PC (P22). (c) La parte B sin gtsam, con una ventana deslizante sobre `scipy.optimize.least_squares`: sin entorno nuevo, pero se aparta de lo que propuso el autor y la meta del IMU tendría que escribir lo que GTSAM ya trae.
- **Respuesta del autor:** (a): un entorno de miniforge solo para la fusión, fuera del repo, con gtsam 4.3.0 de conda-forge; `.venv` no cambia. Miniforge lo instala el autor.
- **Fecha:** 2026-11-05

## P26 · Con qué número se cuenta el 30 % del criterio 2 (replan del 2026-11-05)

- **Opciones:** (a) recomendada: la sd 3D de la posición, √ (traza de su covarianza), en el frame de gs1, cruda (sin quitar la deriva), en el reposo (S1), fusionada por instante (P14) frente a la mejor cámara sola llevada al mismo frame; la √ traza no depende de cómo se giren los ejes, así que compara bien una cámara girada con la otra; aparte y sin veredicto, por eje y sin la media móvil de 1 s (lo que deja fuera la deriva de gs1 por V4L2, B77). (b) Solo la sd z de gs1, el eje débil: da el número más alto, pero depende del frame y castiga menos lo que la fusión empeore en x o y. (c) La sd sin deriva como criterio: mide el temblor puro, pero la deriva es error real de una cámara y la fusión también tendría que bajarla.
- **Respuesta del autor:** (a): la sd 3D de la posición (√ traza), en el frame de gs1, cruda, en el reposo; la fusionada por instante frente a la mejor cámara sola. Por eje y sin deriva, aparte y sin veredicto.
- **Fecha:** 2026-11-05

## P27 · Los extrínsecos de la fase 1 y el criterio 1, sin tablero (replan del 2026-11-05)

- **Opciones:** (a) recomendada: validación cruzada sobre las 5 posiciones de S2: en cada posición, los extrínsecos de las otras cuatro y la coincidencia en ella; cuenta la peor (P16); el tablero de la fase 2 da después unos extrínsecos que no dependen de Marker0 y el criterio 1 se repite con ellos. (b) Los extrínsecos de las 5 posiciones y la coincidencia en esas mismas 5: es circular (la media coincide casi por construcción) y da un número optimista. (c) Esperar al tablero antes de la fase 1: el número es independiente, pero retrasa «verlo» una sesión en vivo.
- **Respuesta del autor:** (a): validación cruzada sobre las 5 posiciones (los extrínsecos de las otras cuatro, la coincidencia en la que queda fuera); cuenta la peor. El tablero de la fase 2 lo repite.
- **Fecha:** 2026-11-05

## P28 · Qué se hace con P17, P19 y P20 (replan del 2026-11-05)

- **Opciones:** (a) recomendada: P17 (el hub USB de Windows) queda sin objeto, porque con P22 el PC no abre cámaras; si algún día vuelve, es B5 de la meta 007. P19 (retirar `--feed` si perdía la arquitectura de dos trackers) queda sin objeto: ya no hay dos arquitecturas que comparar, y el envío por UDP de la fase 3 es la vía. P20: (a), el 30 % se mide siempre por instante (P14), gane el método de sincronía que gane; la sd publicada con el factor de movimiento se da aparte, sin veredicto. (b) Dejarlas abiertas hasta el replan de la fase 3.
- **Respuesta del autor:** (a), la recomendada: P17 y P19 quedan sin objeto; P20 se contesta con (a).
- **Fecha:** 2026-11-05

## P33 · Windows primero, tras P-7b5 (pregunta de la dirección, 2026-11-05)

- **Contexto:** en P-7b5 (meta 007, `Claude outputs/fases/007/p7b5/correr_20261105-193558`), con gs2 fuera del concentrador Genesys (`…USB(5)`), las dos cámaras van a la vez en Windows a 89.5–90 fps cada una, en los dos órdenes, sin `0x800718CF`. El autor pide prioridad a Windows para usar ya las dos cámaras a la vez.
- **Pregunta 1, el papel de la Jetson.** Opciones:
  - (a) recomendada: fuera por ahora. El PC detecta y fusiona, la fase 3 «La Jetson envía al PC» desaparece y la meta 007 sigue en pausa.
  - (b) La Jetson como alternativa: el fusionador acepta las detecciones de las dos plataformas.
- **Respuesta del autor (1):** (a). P22 cambia: el PC detecta con las dos cámaras y fusiona; la Jetson sale de la meta 006 por ahora.
- **Pregunta 2, el orden.** Opciones:
  - (a) recomendada: primero se regraba S2 en Windows, con las ventanas de las dos cámaras a la vista, y se resuelve B94 · Las dos cámaras no ven el Marker0 en el mismo sitio; después, la fusión en vivo en el PC con lo de la parte A, sin GTSAM; GTSAM y el tablero, al final.
  - (b) La fusión en vivo ya, con los extrínsecos de hoy y el sesgo de B94.
  - (c) El orden del plan actual: la parte B (GTSAM) y el tablero primero.
- **Respuesta del autor (2):** (a).
- **Consecuencia:** se replanea la meta desde la Fase 1, parte B, y el autor autoriza el plan nuevo.
- **Fecha:** 2026-11-05
