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

## P34 · Dos procesos o uno con las dos cámaras en el PC (replan del 2026-11-05, tarde, P33)

- **Opciones:** (a) recomendada: dos trackers (los de hoy, cada uno con su cámara, su GIL y su bucle; ~90 fps cada uno a la vez en el P-7b5) que mandan sus esquinas por UDP local a un fusionador, lanzado todo con un comando, `python -m tracker --fusion profiles\fusion_gs1_gs2.yaml` (P10); si una cámara falla, la otra sigue; sirve igual si la Jetson vuelve; coste: `--feed` en `tracker.py` (principio 6, fase 3) y coordinar tres procesos por PID. (b) Un proceso con las dos cámaras: sin red ni apretón de manos, pero la detección cuesta 5.6–5.8 ms por frame (meta 003, fase 6) y las dos en serie no llegan a 85 parejas/s; en paralelo depende de que `detectMarkers` suelte el GIL (sin documentar); y es un segundo bucle de cámara que mantener; habría que medirlo antes. (c) Dos trackers sin cambios y el fusionador como cliente de OpenIGTLink: `tracker.py` intacto, pero llega solo la pose con el 1-Euro, en float32, sin esquinas (solo `numpy_pose`, −31.9 %, en el límite del 30 %) y con la hora de llegada.
- **Respuesta del autor:** (a), la recomendada: dos trackers con `--feed` y un fusionador, lanzados con un solo comando.
- **Fecha:** 2026-11-05

## P35 · Las ventanas durante la grabación de S2 en Windows (replan del 2026-11-05, tarde)

- **Opciones:** (a) recomendada: las dos ventanas abiertas toda la sesión (la vista y la grabación) y tramos de 60 s: con dos ventanas cada bucle puede bajar a ~45–60 fps (con una, 61.7 y 55.2 en la meta 003; con dos, sin medir), y 60 s a ≥ 45 fps dan ≥ 2700 parejas, sobre las 2000 de P16; la sesión dura ~18 min. (b) Las ventanas solo en la vista de antes de cada tramo y la grabación sin ventana, 40 s a ~90 fps, como en la Jetson: ~15 min, pero durante la grabación no se ve si algo se mueve.
- **Respuesta del autor:** (a), la recomendada: las dos ventanas abiertas toda la sesión y tramos de 60 s.
- **Fecha:** 2026-11-05
- **Revisada el 2026-11-05 (noche), tras la corrida `grabacion-pc/correr_20261105-223853`:**
  - **Qué se vio:** con las dos ventanas abiertas, cada cámara bajó a ~31 fps (bucle 30–34) al cabo de unos minutos, por debajo de los 45 del criterio. La mirilla no se cerraba con Enter (tres veces por el tope de 300 s) y la corrida se paró con Ctrl+C antes del primer tramo.
  - **Respuesta del autor:** «hagamos directamente las mediciones ahora»: ya alineó las dos cámaras con AMCap y las dos ven Marker0. Sin mirilla; los seis tramos se graban sin ventana (como (b): 40 s a ~90 fps).

## P36 · Si la fase 2 da «sesgo por vista» (o «se movió» dos veces) (replan del 2026-11-05, tarde)

- **Opciones:** (a) recomendada: adelantar la fase 7 (el tablero) justo después de la 2: da extrínsecos que no dependen de Marker0 y separa «los extrínsecos están mal» de «la pose de una cámara sola está sesgada»; la fusión en vivo espera. (b) Seguir a la fusión en vivo con los extrínsecos del ajuste conjunto y B94 abierta: el criterio 2 (jitter) se puede medir, pero los criterios 1 y 3 no van a cumplir y la pose publicada mezclaría dos vistas que no casan. (c) Una fase nueva antes de todo: la exactitud en profundidad de una cámara sola (B94, punto 3: Marker0 a distancias y ángulos conocidos frente a lo que da IPPE), que es lo que diría si el tracker de hoy publica mm de error según la vista.
- **Respuesta del autor:** (a), la recomendada: se adelanta la fase 7 (el tablero) justo después de la 2, y la fusión en vivo espera.
- **Fecha:** 2026-11-05
- **Aplicada el 2026-11-09 con un solo «se movió», sin repetir S2:**
  - **Lo que salió en la fase 2** (`ccfe803`): «se movió», con pos1 frente a pos1_fin 0.703 mm / 0.151°, al borde del umbral de 0.5 mm, que ya está en duda por el ruido (B100). Pero los extrínsecos por pose cambian 15.4 mm entre posiciones y el criterio 1 da 4.20 mm / 6.09°, mientras el ajuste conjunto cabe en 0.298 px. Lo que domina es el sesgo por vista, no el movimiento.
  - **Respuesta del autor:** adelantar ya la fase 7 (el tablero), sin repetir S2 como pide la regla del plan para «se movió». Las cámaras no se mueven hasta el tablero.

## P37 · Los topes de tiempo real del fusionador sin GTSAM en el PC (replan del 2026-11-05, tarde; revisa P15)

- **Opciones:** (a) recomendada: cámara ≥ 85 fps cada una; bucle de cada tracker con `--feed` ≥ 85 fps sin ventana y ≥ 45 con dos ventanas; fusión por pareja p95 ≤ 5 ms y máx. ≤ 15 ms (la parte A midió en el PC p50 2.9–3.3 ms y p95 20.5 ms con el BLAS en hilos; si no llega, se prueba `OPENBLAS_NUM_THREADS=1`); poses fusionadas ≥ 85/s sin ventana y ≥ 45/s con ventana; latencia añadida (captura del frame más nuevo de la pareja → envío a Slicer) p95 ≤ 12 ms; pérdida UDP ≤ 0.1 %; Slicer ≥ 50 Hz (techo ~65, B54). Los de P15 para GTSAM siguen en la fase 6. (b) Los de P15 tal cual (fusión p95 ≤ 3 ms, ≥ 50/s con ventana): con la parte A medida, la fusión numpy probablemente no llega sin optimizarla. (c) Otros números del autor.
- **Respuesta del autor:** (a), la recomendada: los topes revisados para el PC.
- **Fecha:** 2026-11-05

## P38 · Qué viaja de cada tracker al fusionador en el PC (replan del 2026-11-05, tarde; revisa P24)

- **Opciones:** (a) recomendada: por frame, aunque no vea nada, la cámara, una secuencia, la hora de captura en ns y las esquinas de Marker0 (~50 bytes), por `127.0.0.1:18961`; el fusionador rehace las dos soluciones de IPPE con `fusion.dataset.ippe_solutions`, igual que el experimento, así que en vivo se fusiona lo mismo que fuera de línea; el tracker solo añade un envío; la pose cruda y la otra solución de P24 sobran (las calculaba la Jetson; la parte A midió 0 medidas salvadas por la otra solución); sin regla de cortafuegos. (b) Lo de P24 tal cual (además la pose cruda y la otra solución): el tracker tendría que calcular la pose sin el 1-Euro aparte (hoy `tvec` sale filtrada), más cambio en la cadena para nada que el fusionador no pueda rehacer.
- **Respuesta del autor:** (a), la recomendada: por frame, la cámara, la secuencia, la hora de captura y las esquinas de Marker0; el fusionador rehace IPPE.
- **Fecha:** 2026-11-05

## P39 · Qué motor publica el fusionador en vivo (replan del 2026-11-05, tarde)

- **Opciones:** (a) recomendada: `numpy_reproj`, el PnP conjunto sobre las 8 esquinas (−63.1 % en la parte A, aunque con B94 abierta; la pose sola de IPPE es 1.2–1.5× más ruidosa, B95), y con una sola cámara, su pose por mínimos cuadrados; `numpy_pose` queda elegible en el perfil; se confirma con los números de la fase 2. (b) `numpy_pose`, la media ponderada de las dos poses de IPPE (−31.9 %, justo en el 30 %): más simple, y con una sola cámara pasa su pose de IPPE tal cual. (c) Decidirlo con la fase 2, sin valor por defecto en el perfil.
- **Respuesta del autor:** (a), la recomendada: `numpy_reproj`; `numpy_pose` queda elegible en el perfil y se confirma con los números de la fase 2.
- **Fecha:** 2026-11-05

## P40 · Cómo se graba el tablero de la Fase 7 · Los extrínsecos por tablero (tras la sesión cortada del 2026-11-10)

- **Contexto:** la primera sesión con `Claude outputs/fases/006/fase-7/correr.ps1` (`correr_20261110-180748`) se detuvo en T04 por el tope de 15 min de la mano, con 3 vistas usables y casi iguales (tablero plano; gs1 z 364–373 mm e inclinación 21–24°, gs2 z 425–437 mm y 19–26°). Las cámaras miran de arriba hacia abajo y el tablero se pone sobre la mesa, con cuñas. El script abre cada cámara por turnos en cada posición (~25 s de máquina), no muestra nada en vivo y va por teclado.
- **Opciones:** (a) recomendada: un asistente en vivo, `calibration.capture_stereo_board`: las dos cámaras abiertas a la vez en un proceso, una ventana con las dos vistas, el tablero marcado, `z` e inclinación en vivo, la postura siguiente y su estado; captura sola cuando el tablero lleva ~1 s quieto y la vista es distinta de las ya tomadas; escribe las vistas en el formato que ya lee `calibrate_extrinsics --desde-vistas`; no usa el tracker ni la cadena. (b) Arreglar `correr.ps1`: la mano sin tope corto, `-Continuar`, posturas en horizontal y aviso de vista repetida. (c) Repetir `correr.ps1` tal cual.
- **Respuesta del autor:** (a), el asistente en vivo. Se replanifica la Fase 7 para incluirlo; las vistas de `correr_20261110-180748` no se reutilizan.
- **Fecha:** 2026-11-10

## P41 · El umbral de variedad del asistente del tablero (Fase 7a, replan del 2026-11-10)

- **Opciones:** (a) recomendada: una vista es distinta si, frente a cada una de las ya tomadas, el tablero giró ≥ 10° o su centro se movió ≥ 40 mm (medido en gs1; las dos medidas no dependen de la cámara ni del orden de las esquinas). Con la guía, las cuñas dan 20–30° y la pila 80 mm, así que cada postura pasa; las 3 planas de la sesión cortada (21–26°, 9 mm de `z`) habrían contado como una. (b) 5° o 25 mm: acepta más vistas parecidas y la sesión termina antes, pero el ajuste gana menos con cada una. (c) 15° o 60 mm: más variedad garantizada, pero los desplazamientos de 5–6 cm de la guía (T13, T14, T19, T20) solo pasarían por su cuña.
- **Respuesta del autor:** (a), la recomendada: ≥ 10° o ≥ 40 mm frente a cada vista tomada, medido en gs1.
- **Fecha:** 2026-11-10

## P42 · Cuántas vistas toma el asistente (Fase 7a, replan del 2026-11-10)

- **Opciones:** (a) recomendada: objetivo 20 (termina solo al llegar) y mínimo 18 (con `q` termina si ya hay 18); el cálculo pide 18 usables (15 de ajuste y 3 de control) y aparta las vistas incoherentes, así que 2 de margen evitan repetir la sesión por una. (b) Objetivo 18 y mínimo 18: la sesión más corta, sin margen. (c) Objetivo 24 y mínimo 18: más margen y más vistas en el ajuste, ~6 posturas más (las «extra» de la guía).
- **Respuesta del autor:** (a), la recomendada: objetivo 20 (termina solo) y mínimo 18 (con `q`).
- **Fecha:** 2026-11-10

## P43 · Los topes del asistente (Fase 7a, replan del 2026-11-10; principio 9)

- **Opciones:** (a) recomendada: tope de la sesión 45 min (`--timeout 2700`; el vigilante, 60 s después, y `correr.ps1` para el proceso por su PID a los 2700 + 120 s); sin tope por postura, para que no se corte como a los 15 min de T04; la ventana dice los minutos desde la última captura; una cámara sin frames 5 s para la sesión (código 4); la comprobación de una ráfaga, 30 s. Al tope, lo tomado queda escrito y vale para el cálculo si llega a 18. (b) 30 min de sesión: el ritmo de la guía (~1 min por postura) da para 20, pero con cuñas a mano puede no bastar. (c) 60 min de sesión.
- **Respuesta del autor:** (a), la recomendada: 45 min de sesión, sin tope por postura; una cámara sin frames 5 s para la sesión (código 4); la comprobación de una ráfaga, 30 s.
- **Fecha:** 2026-11-10

## P44 · Si la postura tomada tiene que coincidir con la de la guía (Fase 7a, replan del 2026-11-10)

- **Opciones:** (a) recomendada: no; vale cualquier vista que las dos cámaras vean entera, quieta y distinta de las tomadas; la ventana muestra la postura siguiente de la guía como orientación, `n` la salta, y el informe da la variedad lograda (en gs1, inclinación de ≤ 10° a ≥ 30° y `z` con ≥ 60 mm de recorrido) para juzgarla con un número. (b) Sí: el asistente comprueba la postura pedida (p. ej. «inclinación ≥ 15° más que T01» con cuña, «`z` 60 mm menos» sobre la pila) y no captura otra cosa; más guía, pero más lógica que probar y más esperas si la cuña no da justo lo previsto.
- **Respuesta del autor:** (a), la recomendada: no; vale cualquier vista distinta, la guía orienta, `n` la salta y el informe da la variedad lograda.
- **Fecha:** 2026-11-10

## P45 · Cómo seguir tras la primera sesión del asistente, con la investigación del autor (2026-11-11)

- **Contexto:** sesión `fase-7/asistente/correr_20261111-124742`: el asistente cumple (20 vistas en 8.6 min, 90 fps), el cálculo no (RMS 0.548 px, control 1.611, distancia triangulada 0.908 mm; sin las 5 vistas de ≥ 50°, 0.482 / 1.076 / 0.500). Base del tablero 236.6 mm frente a ~188.8 de Marker0 (S2 del 2026-11-09); el autor mide ~25 cm con regla y cree que las cámaras se movieron; S2 repetida sin tocar nada: `grabacion-pc/datos/20261111-131000`. El autor dejó una investigación (`Claude outputs/especificaci_n_de_calibraci_n_est_reo_para_navegaci_n_por_grafo_de_factores.md`: Kalibr, Basalt, mrcal, ChArUco, flujo desacoplado, criterios). Lectura de la dirección: el método ya es el del documento (§3.3, pasos 1 y 2); faltan el refinado conjunto acotado, más vistas, ChArUco para cubrir los bordes, y residuos y error epipolar; Kalibr y Basalt no ahora (VIO, ROS/Linux), Kalibr `imu_camera` cuando llegue el IMU, mrcal opcional como validador externo.
- **Opciones:** (a) recomendada: diagnóstico primero, sin cámara y sin escribir en el repo (Marker0 con la S2 nueva, criterio 1 con el tablero de hoy contra ella, intrínsecos recalibrados con las vistas de hoy, refinado conjunto con `CALIB_USE_INTRINSIC_GUESS` como medida, residuos y epipolar); después se decide el método con los números. (b) Replan directo a ChArUco y 40 vistas. (c) Solo el criterio 1 con la S2 nueva.
- **Respuesta del autor:** (a), diagnóstico primero.
- **Fecha:** 2026-11-11

## P46 · B55: el Marker0 de 100 mm con el perfil en 80 (tras el diagnóstico del 2026-11-11)

- **Contexto:** el diagnóstico (`Claude outputs/fases/006/fase-7/diagnostico-20261111/reporte.md`) triangula con el tablero el lado del Marker0 de la S2 de hoy en 98.26–98.56 mm: era el de 100 mm (98.6 con calibrador) con el perfil en 80, así que todas las distancias por Marker0 salieron a escala 0.81. Corregida la escala, el criterio 1 baja de 44.6 a 0.87–1.12 mm (los grados siguen en 5.4–6.6°, B95). El autor midió el marker del montaje: ~98 mm. Dice que en las sesiones anteriores usó el de 80 y hoy los confundió.
- **Opciones:** (a) recomendada: B55 a alta y otro ID para el de 100 mm, con su `size_mm` en el perfil, para que el tracker no pueda confundirlos (toca la cadena: ADR y verificación en vivo con Slicer). (b) Alta y usar solo el de 80. (c) Alta y una comprobación de escala en «Verificar IDs».
- **Respuesta del autor:** (a). Además: «podemos usar el de 98 mm de ahora en adelante».
- **Nota de la dirección:** la base por Marker0 salió 188.76 mm el 11-09 y 188.81 hoy, a escala 80. Si el 11-09 hubiera sido el de 80 y hoy el de 100, la coincidencia a 0.05 mm sería casual entre dos montajes distintos (las cámaras giraron 12°). Que el 11-09 fuera también el de 100 queda abierto: sin comprobar.
- **Fecha:** 2026-11-11

## P47 · Los intrínsecos y la rigidez del montaje (tras el diagnóstico del 2026-11-11)

- **Contexto:** los intrínsecos de gs2 se apartan de los de la meta 002 (fx +11, cx −9.5, cy −7.3 px, 4–7 σ); el ~0.5 px que queda en el tablero es un desplazamiento por vista agrupado por orden de toma (hipótesis: el montaje de pinzas cede).
- **Opciones:** (a) recomendada: probar la rigidez primero; (b) recalibrar los intrínsecos de gs2 ya; (c) pasar a la estructura rígida directamente.
- **Respuesta del autor (texto libre):** «es verdad que el montaje actual no es rígido; no entiendo por qué los intrínsecos se descalibrarían, pero podemos volver a calibrarlos por seguridad; es un paso que deberíamos automatizar, sacar rápido la calibración de intrínsecos».
- **Fecha:** 2026-11-11

## P48 · El ID del Marker0 nuevo de ~100 mm (Fase 7c · El Marker0 con su propio ID, replan del 2026-11-11)

- **Contexto:** el diccionario es `DICT_ARUCO_MIP_36h12` (IDs 0–249). En uso o vistos: 0 (los dos Marker0 de hoy, el de 80 y el de 100), 170–180 (el dodecaedro archivado), 181–191 (el stylus, B14), 87 y 115 (lecturas fantasma de un Marker0 sintético inclinado, B39).
- **Opciones:** (a) recomendada: ID 100: libre, lejos de todos los de arriba, y recuerda los 100 mm al leerlo en «Verificar IDs» (el problema de B55 fue de procedimiento). (b) ID 1: el siguiente al 0, sin significado. (c) Otro que el autor elija.
- **Respuesta del autor:** (a), la recomendada: ID 100. (Y el nombre cambia: P57.)
- **Fecha:** 2026-11-11

## P49 · Cómo conviven el Marker0 nuevo y los de ID 0 en el perfil (Fase 7c, replan del 2026-11-11)

- **Opciones:** (a) recomendada: `markers.list` lleva solo el nuevo, con `name: Marker0` y su `size_mm`; el ID 0 sale de la lista blanca, así que ni el de 80 ni el de 100 viejo (los dos son ID 0) pueden dar una pose; si se ven los dos, se publica solo el nuevo, un `Marker0ToTracker` por frame como hoy; `profiles.load` impide dos entradas con el mismo nombre. Para volver al de 80 bastaría cambiar el perfil (con su replay y su verificación). (b) Los dos en la lista con nombres distintos (`Marker0` el nuevo y `Marker0_80` el viejo): el tracker publicaría también `Marker0_80ToTracker`, un nodo nuevo en Slicer: contradice ADR-026 (solo `Marker0ToTracker`) y pide otro ADR y verificación. (c) Los dos con el nombre `Marker0`: dos envíos por frame con poses distintas; no se recomienda y `check_markers` lo prohibiría.
- **Respuesta del autor:** (a), la recomendada: solo el nuevo en el perfil; el ID 0 sale de la lista blanca y un marker viejo a la vista no envía nada. (El nombre ya no es «Marker0»: P57.)
- **Fecha:** 2026-11-11

## P50 · Cómo se hace el marker nuevo (Fase 7c, replan del 2026-11-11)

- **Opciones:** (a) recomendada: con un generador del repo (`python -m diagnostics.marker_image`): un SVG en mm exactos (100 mm de lado, margen blanco, una regla de 50 mm para comprobar la escala de la impresión, el ID y el diccionario escritos fuera del marker) y una PNG; el autor lo hace como hizo los de ahora (negro mate, sobre un soporte plano) y lo mide con calibrador, 5 medidas del lado negro; la media va a `size_mm`. (b) Sin generador: el autor genera la imagen con otra herramienta y da el lado medido; una pieza menos que mantener, pero el ID y el diccionario no los comprueba ninguna prueba hasta la sesión.
- **Respuesta del autor:** (a), la recomendada: un generador del repo da SVG y PNG a escala; el autor lo imprime, lo mide con calibrador y ese número va al perfil.
- **Fecha:** 2026-11-11

## P51 · ChArUco para los intrínsecos, ahora o después (Fase 7d, replan del 2026-11-11)

- **Contexto:** el diagnóstico dio cobertura 0.83, sin esquinas en los ~150 px laterales. Un ChArUco (`CharucoBoard`, `CharucoDetector.detectBoard`, `matchImagePoints`, OpenCV por Context7) se detecta con el tablero en parte fuera de la imagen, porque cada esquina lleva su ID: es lo que cubre los bordes.
- **Opciones:** (a) recomendada: después, solo si el asistente de una cámara no llega a 0.85 de cobertura fina con el tablero de ajedrez de hoy (la sesión de la 7e lo dice con un número); el asistente guía hacia las celdas sin cubrir, que es lo que faltó el 11-11. (b) Ahora: un tablero ChArUco nuevo (imprimirlo plano y medirlo) y su detector en el asistente y en `calibrate_camera`; cubre mejor los bordes, pero es una pieza física más y un segundo camino de detección que probar antes de recalibrar. (c) No: solo el tablero de ajedrez.
- **Respuesta del autor:** **Ahora, en la Fase 7d** (no la recomendada): el asistente de intrínsecos nace con ChArUco y hay que imprimir un tablero ChArUco nuevo.
- **Fecha:** 2026-11-11

## P52 · Las vistas y el criterio de los intrínsecos (Fases 7d y 7e, replan del 2026-11-11)

- **Contexto:** la meta 002 calibró con 23 vistas (RMS 0.15–0.17, control 0.15, cobertura 4×3 = 1.00, sd de fx 0.67–1.09 px). El 11-11, con 20 vistas del tablero estéreo, el jackknife dio ±1.5–2.2 px; la investigación del autor (P45) habla de 40–80 vistas. El asistente estéreo tomó 20 en 8.6 min.
- **Opciones:** (a) recomendada: objetivo 40 y mínimo 30, ≤ 20 min de asistente por cámara (~40 min las dos); criterio: RMS ≤ 0.5 px, control (5 vistas) ≤ 0.75 px, cobertura 4×3 = 1.00 y 8×6 ≥ 0.85, sd de fx, fy, cx, cy ≤ 1.0 px. (b) Objetivo 25 y mínimo 20, el criterio de la meta 002 sin la sd: ~10 min por cámara, pero la sd probablemente se queda en 1.5–2 px, como el jackknife. (c) Objetivo 60 y mínimo 50: más cerca de lo que pide la investigación, ~30 min por cámara.
- **Respuesta del autor:** (a), la recomendada: objetivo 40 vistas, mínimo 30; ≤ 20 min por cámara; sd de fx, fy, cx, cy ≤ 1.0 px; cobertura 8×6 ≥ 0.85.
- **Fecha:** 2026-11-11

## P53 · El montaje de las cámaras: la estructura rígida y las pinzas mientras tanto (replan del 2026-11-11)

- **Contexto:** el autor dice que las pinzas no son rígidas; el diagnóstico ve ~0.1° por vista agrupado en el tiempo y un giro de 12° entre el 11-09 y el 11-11. Los intrínsecos (7e) y el marker (7c) no dependen del montaje; los extrínsecos (Fase 7, sesión 2) y la fusión en vivo (3–5), sí.
- **Opciones:** (a) recomendada: 7c, 7d y 7e ya; la sesión 2 de la Fase 7 sobre las pinzas, sujetas con cinta o peso, con la rigidez medida, y sus extrínsecos como provisionales para desarrollar las fases 3–5; los definitivos, en la 7b sobre la estructura. El autor dice además cuándo espera tener la estructura. (b) 7c, 7d y 7e ya, y ninguna sesión de extrínsecos ni fusión en vivo hasta la estructura: no se gasta una sesión en un montaje que ya se sabe que cede, pero 3–5 esperan. (c) La estructura ya existe (o llega en días): la sesión 2 se hace directamente sobre ella y sustituye a la 7b.
- **Respuesta del autor:** **Texto libre del autor:** «ningún montaje es perfecto; para mayor seguridad conviene hacer recalibraciones cada cierto tiempo, por ejemplo cada que termine una sesión, cada que cambie de día, cada que algo no cuadre y apunte a la calibración; por eso debemos automatizar el proceso de recalibración, que no sea algo cansado y pesado para el usuario, que sea recalibrar y continuar». Lectura de la dirección: se sigue con el montaje actual; los extrínsecos se dan por válidos solo para la sesión en que se midieron, y la recalibración (extrínsecos, y los intrínsecos cuando toque) tiene que ser rápida y guiada, con sus disparadores (inicio de sesión o de día, o un aviso de que algo no cuadra, p. ej. el RMS del PnP conjunto, B110).
- **Fecha:** 2026-11-11

## P54 · Los grados del criterio 1 (0.2°), con un marker por cámara (replan del 2026-11-11)

- **Contexto:** el criterio 1 del spec pide que la pose de gs2 llevada a gs1 difiera de la de gs1 en < 0.5 mm y < 0.2°. Con la escala corregida, el diagnóstico da 0.87–1.12 mm y 5.4–6.6° con cualquier juego de extrínsecos: los grados son la orientación de IPPE de cada cámara sola (B95; en la Fase 2, gs2 saltaba entre dos soluciones de IPPE separadas ~5°, B103). La fusión no publica esa orientación: publica la del PnP conjunto de las 8 esquinas (P39). Cambiar un número del spec es decisión del autor.
- **Opciones:** (a) recomendada: los mm se quedan (< 0.5 mm); los grados de cada cámara sola pasan a número informativo, y en su lugar cuenta la coherencia de lo que publicará la fusión: el RMS del PnP conjunto de cada pareja con los extrínsecos del tablero, mediana ≤ 0.5 px y p95 ≤ 1.0 px en cada posición de S2 (`consistencia_conjunta`). (b) Los grados con la pose de cada cámara refinada por mínimos cuadrados desde las dos soluciones de IPPE (la de menor reproyección), < 0.2°: mide la misma cosa que pide el spec con menos sesgo, pero puede seguir sin cumplir y no está medido. (c) Se queda como está (< 0.2° con IPPE): según el diagnóstico, no va a cumplir con ningún extrínseco.
- **Respuesta del autor:** (a), la recomendada: los mm siguen en < 0.5; los grados de una cámara sola pasan a informativos y cuenta la coherencia del PnP conjunto (mediana ≤ 0.5 px, p95 ≤ 1.0 px).
- **Fecha:** 2026-11-11

## P55 · Residuos, error epipolar y rigidez en el criterio del tablero (Fase 7, replan del 2026-11-11; P45)

- **Contexto:** el 11-11, el error epipolar de gs2 dio mediana 0.58 y p95 1.87 px; el residuo medio por vista, +1.1 a +2.0 px en T03–T06 y −0.2 a −1.1 en el resto; ~0.1° por vista agrupado por orden de toma. Los umbrales de abajo son propuestas sin más datos que esos; la parte sin cámara mide el suelo de ruido y para si no queda por debajo de la mitad de cada uno.
- **Opciones:** (a) recomendada: que cuenten para escribir el `.yml`: epipolar (vistas de control) mediana ≤ 0.3 px y p95 ≤ 0.75 px; residuo medio por vista ≤ 0.25 px en cada cámara; rigidez: el giro de los extrínsecos por vista a ≤ 0.05° de su mediana y |ρ| con el orden de toma < 0.5; si la rigidez no cumple, el veredicto es «el montaje se mueve». (b) Solo como números en el reporte, sin veredicto: el criterio sigue siendo RMS, control y distancia. (c) Solo el epipolar.
- **Respuesta del autor:** (a), la recomendada: cuentan; epipolar mediana ≤ 0.3 y p95 ≤ 0.75 px, residuo medio por vista ≤ 0.25 px, rigidez ≤ 0.05°; los umbrales se ajustan si el ruido medido no queda por debajo de la mitad.
- **Fecha:** 2026-11-11

## P56 · Dónde van los intrínsecos nuevos (Fase 7e, replan del 2026-11-11; B89)

- **Opciones:** (a) recomendada: archivos nuevos, `data/intrinsecos_gs{1,2}_1280x960_<AAAAMMDD>.yml`, y `calibration_file` de los perfiles apuntando a ellos; los de la meta 002 se quedan (las grabaciones guardan su sha256, la copia congelada del perfil y `explain_pose` los citan, y así se puede volver atrás cambiando una línea). (b) Pisar los de ahora con una copia `.bak`: un archivo por cámara, pero rompe las pruebas que comparan el sha256 de las grabaciones y repite el riesgo de B89.
- **Respuesta del autor:** (a), la recomendada: archivos nuevos con su fecha; los perfiles los apuntan; los de la meta 002 se quedan (B89).
- **Fecha:** 2026-11-11

## P57 · El nombre del marker de referencia y de su transform (2026-11-11, a raíz de P48)

- **Contexto:** con ID 100 (P48), «Marker0» deja de tener sentido; el autor pide no llamarlo así. El transform que recibe Slicer, `Marker0ToTracker`, es parte de la cadena (principio 6): cambiarlo exige ADR, poner al día los scripts de `codigo/slicer/` y verificación en vivo con Slicer.
- **Opciones:** (a) recomendada: por su papel, `Reference` y `ReferenceToTracker` (si cambia el ID, el nombre sigue valiendo); (b) por su ID, `Marker100` y `Marker100ToTracker`; (c) renombrar el marker en perfiles y docs pero mantener `Marker0ToTracker` por ahora.
- **Respuesta del autor:** (a): `Reference` y `ReferenceToTracker`, en la Fase 7c, con su ADR y en vivo.
- **Fecha:** 2026-11-11

## P58 · ChArUco también en los extrínsecos, y cuándo (Fase 7f, replan del 2026-11-11, tarde; tras P51)

- **Contexto:** con P51 el tablero ChArUco llega en la 7d para los intrínsecos. Hoy los extrínsecos piden el 8 × 5 entero en las dos cámaras a la vez: eso dejó fuera las inclinaciones fuertes y los bordes el 11-11, y obliga a adivinar el orden de las esquinas (B113, B114). Con ChArUco vale la parte que ven las dos (comprobado en `.venv`: `stereoCalibrate` acepta vistas con distinto número de puntos).
- **Opciones:** (a) recomendada: sí, en esta ronda, en una fase propia (7f) después de la 7e y antes de la recalibración rápida (7g): un solo tablero para todo, la recalibración frecuente más fácil de colocar, y sin orden de esquinas que adivinar; el 8 × 5 queda como camino alterno con sus pruebas; coste: una fase pesada más antes de la sesión 2. (b) Después, al BACKLOG: la sesión 2 y la recalibración con el 8 × 5; menos código ahora, pero cada recalibración pide que las dos vean el tablero entero y el autor maneja dos tableros. (c) Solo ChArUco, retirando el 8 × 5 de los extrínsecos: menos código que mantener, pero se pierde el camino probado (32 pruebas del asistente, la comparación con la meta 002).
- **Respuesta del autor:** (a), la recomendada: sí, en esta ronda, en su propia Fase 7f.
- **Fecha:** 2026-11-11

## P59 · Las medidas y el diccionario del tablero ChArUco (Fase 7d, replan del 2026-11-11, tarde)

- **Contexto:** imagen 1280 × 960, fx ≈ 850 px, distancia de trabajo 30–50 cm, impresión en 3D bicolor en la cama de 256 × 256 de la A1 con el negro agrandado 0.40 mm por lado (como el 9 × 6 de la meta 002). Comprobado en `.venv` (OpenCV 4.11): el 9 × 7 de (a) da 31 marcadores y 48 esquinas y se detecta entero en su propia imagen.
- **Opciones:** (a) recomendada: 9 × 7 casillas de 26 mm, marcadores de 19.5 mm, `DICT_4X4_50`, 8 mm de margen (250 × 198 mm), patrón nuevo; a 50 cm, ~44 px por casilla y ~5.5 px por módulo del marcador (módulo impreso de 3.25 mm); 48 esquinas por vista; con una muestra de 3 × 3 casillas impresa antes. (b) 7 × 5 casillas de 34 mm, marcadores de 25.5 mm, `DICT_4X4_50` (256 × 188 mm: sin margen en la cama): módulos de 4.25 mm, más fáciles de imprimir y de leer lejos, pero 24 esquinas por vista y menos cobertura fina por vista. (c) 11 × 8 casillas de 21 mm, marcadores de 15.75 mm, `DICT_5X5_100`: 70 esquinas por vista, pero módulos de 2.25 mm (~3.8 px a 50 cm), al límite de la impresión y de la lectura.
- **Respuesta del autor:** (a), la recomendada: 9×7 casillas de 26 mm, marcadores de 19.5 mm, `DICT_4X4_50`, 250 × 198 mm con margen; antes, la muestra de 3×3.
- **Fecha:** 2026-11-11

## P60 · Cuántas vistas y cuánto tiempo la recalibración rápida de extrínsecos (Fase 7g, replan del 2026-11-11, tarde; P53)

- **Contexto:** el 11-11 el asistente tomó 20 vistas en 8.6 min (~26 s por vista). Con los intrínsecos fijos los extrínsecos son 6 números; la fase prueba con 0.1 px de ruido que el mínimo los deja a ≤ 0.1 mm a 37 cm y, si no, para con el número.
- **Opciones:** (a) recomendada: objetivo 12 vistas y mínimo 10 (8 de ajuste y 2 de control), 3 frames por ráfaga, más 10 s de la referencia a la vista; ≤ 5 min de asistente y ≤ 6 min de punta a punta; tope 10 min. (b) Objetivo 10 y mínimo 8: ~4 min, pero la rigidez se juzga con menos vistas. (c) Objetivo 20 y mínimo 18, como la sesión del 11-11: más robusto, ~10 min cada vez.
- **Respuesta del autor:** **(c), no la recomendada:** objetivo 20 vistas y mínimo 18, como la sesión del 11-11; ~10 min cada vez. Donde el plan dice 12 / 10 vistas y ≤ 5–6 min, vale esto; el tope pasa a 15 min (1.5 × 10, nota de la dirección).
- **Fecha:** 2026-11-11

## P61 · Qué hace el sistema con cada disparador de recalibración (Fases 7g y 4, replan del 2026-11-11, tarde; P53, B110)

- **Contexto:** el autor pidió recalibrar al terminar una sesión, al cambiar de día y cuando algo no cuadre. Los disparadores: la edad de los extrínsecos al arrancar la fusión; en vivo, el RMS del PnP conjunto (B110) y el lado de la referencia triangulado; en cada recalibración, sus comprobaciones.
- **Opciones:** (a) recomendada: al arrancar, la fusión no arranca con extrínsecos de otro día o de más de 12 h (código 2 y el comando de recalibrar; `--aceptar-extrinsecos-viejos` lo salta y queda escrito); en vivo, con la mediana de 2 s del RMS conjunto > 1.0 px o el lado a > 1.0 mm de su tamaño durante 5 s, un aviso en el log, el resumen y el panel, y se sigue publicando; la recalibración que no cumple no escribe nada. (b) Solo avisos, también al arrancar: la fusión arranca siempre y avisa de la edad; menos fricción, pero una sesión puede correr entera con extrínsecos de otro día. (c) Como (a), y además en vivo deja de publicar (o publica solo gs1) mientras dure el aviso: más seguro, pero Slicer pierde la pose o cambia de fuente sin que nadie lo decida en el momento; pide su ADR.
- **Respuesta del autor:** (a), la recomendada: la fusión no arranca con extrínsecos de otro día o de más de 12 h, salvo una opción explícita; en vivo, avisa y sigue publicando.
- **Fecha:** 2026-11-11

## P62 · Cuándo se recalibran los intrínsecos (Fase 7g, replan del 2026-11-11, tarde; P47, P53)

- **Contexto:** los intrínsecos son de cada cámara y no dependen del montaje; recalibrarlos son ~40 min (7e, las dos cámaras). La recalibración de extrínsecos puede reconocer su firma: el epipolar o el residuo por vista fuera con la rigidez dentro.
- **Opciones:** (a) recomendada: por eventos: dos recalibraciones de extrínsecos seguidas con la firma de intrínsecos, o un lente o el enfoque tocados (CONTEXT §4.10, B36); y un aviso (no un bloqueo) cuando pasen 30 días. (b) Cada semana, fija, aunque nada falle. (c) Solo cuando el autor lo decida, sin aviso.
- **Respuesta del autor:** (a), la recomendada: por eventos (lente o enfoque tocados, o dos recalibraciones seguidas con la firma de intrínsecos malos) y un aviso a los 30 días.
- **Fecha:** 2026-11-11

## P63 · Cómo lanza el autor la recalibración (Fases 7g y 7h, replan del 2026-11-11, tarde; P53)

- **Opciones:** (a) recomendada: un comando de un paso, `python -m calibration.recalibrar --montaje pinzas` con los perfiles del repo (lo demás lo fijan sus constantes), y un botón del panel, «Recalibrar extrínsecos (gs1 + gs2)», que lo lanza y enseña la edad de los vigentes; el botón en una fase ligera aparte (7h), después de probar el comando en vivo. (b) Solo el comando: menos código, pero el autor tiene que tenerlo a mano. (c) Solo el botón, en la misma fase que el comando: un paso menos, pero la primera prueba en vivo mezcla el panel y la recalibración.
- **Respuesta del autor:** (a), la recomendada: el comando de un paso y el botón del panel (Fase 7h), con la edad de la calibración.
- **Fecha:** 2026-11-11

## P64 · Dónde van los extrínsecos de cada recalibración y cuál vale (Fase 7g, replan del 2026-11-11, tarde; revisa P18)

- **Contexto:** con «recalibrar y continuar» habrá un archivo por sesión. P18 fijaba un nombre por montaje (`extrinsecos_gs1_gs2_pinzas.yml`) y nada se pisa (B89, P56).
- **Opciones:** (a) recomendada: `codigo/data/extrinsecos/<montaje>/<AAAAMMDD-HHMMSS>.yml` (formato 2, con su fecha y `criteria_passed`), versionados pero sin commit obligatorio por recalibración (el autor los sube cuando quiera); vale el más nuevo que cumplió con los intrínsecos de hoy; las grabaciones de la fusión copian el que usaron; los frames de cada recalibración, fuera de git en `Claude outputs/recalibraciones/`. (b) Lo mismo fuera de git (en `.gitignore`): `git status` limpio, pero un clon no tiene los extrínsecos (hoy solo el PC del autor abre las cámaras) y solo la copia de las grabaciones los guarda. (c) Un archivo por montaje que se pisa con copia `.bak`: el más simple, pero va contra P56 y B89.
- **Respuesta del autor:** (a), la recomendada: `data/extrinsecos/<montaje>/<fecha-hora>.yml`, versionados sin commit obligatorio; vale el más nuevo que cumplió.
- **Fecha:** 2026-11-11

## P65 · El script de Slicer con el nombre nuevo (Fase 7c2, replan del 2026-11-11, tarde; P57)

- **Contexto:** el script versionado es `codigo/slicer/receive_marker0.py`; el autor lo carga con `exec(open(r"…\receive_marker0.py"…))`, y `docs/ARCHITECTURE.md` §9.1 lo nombra en el mapa (el Mermaid tiene que reexportarse si cambia, ADR-032, con `mermaid-cli` por `npx`).
- **Opciones:** (a) recomendada: renombrarlo con `git mv` a `receive_reference.py`, con `NAME = "ReferenceToTracker"` y la comprobación de que `Marker0ToTracker` no está en la escena, y reexportar el mapa (el Mermaid cambia igual por el nombre del nodo). (b) Mantener `receive_marker0.py` y cambiar solo su `NAME`: el comando de Slicer del autor no cambia, pero el nombre del archivo cuenta otra cosa que lo que mide.
- **Respuesta del autor:** (a), la recomendada: `git mv` a `receive_reference.py` y reexportar el mapa de §9.1.
- **Fecha:** 2026-11-11
