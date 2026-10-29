# Meta 006 — Grafo de factores óptico-inercial (primero, las dos cámaras)

## Por qué

Hoy cada cámara SVPRO (gs1, gs2) corre en su propio proceso y da su propia pose de Marker0, en su propio sistema de coordenadas: nada las junta. Con una sola cámara, la profundidad sale del tamaño aparente del marker (80 mm), que es el eje más débil del PnP, y si algo tapa esa cámara la pose se pierde. El autor propuso el 2026-10-26 un grafo de factores (GTSAM) que fusione las poses de gs1 y gs2, y más adelante un IMU en el instrumento, de forma modular para poder pasar a puntos IR por PnP sin rehacerlo. Decidió el 2026-10-29 que esta meta sea **solo las dos cámaras**; el IMU va a una meta posterior. Viene después de las metas 003 y 004, que dejaron la cadena ordenada, medida y explicada (`docs/ARCHITECTURE.md` §9), y de la 005, en pausa.

Fuentes que el autor pidió usar: Context7 (GTSAM, OpenCV), el GitHub MCP (implementaciones de referencia) y la monografía `documentos/tecnicos/Factor Graphs for robot perception.pdf`.

## Qué se construye

1. **Las dos cámaras en un mismo sistema de coordenadas:** la calibración extrínseca de gs2 respecto a gs1, guardada como dato versionado junto a los intrínsecos, con su error medido. El autor diseña aparte una estructura rígida para las dos cámaras (barra con separación elegible y ángulo fijo); hasta que exista, se trabaja con el montaje actual (dos pinzas en la caja de luz) y la calibración se repite sobre la estructura cuando llegue.
2. **Las dos cámaras a la vez, con hora:** capturar gs1 y gs2 juntas y emparejar sus medidas por tiempo, sabiendo que las SVPRO no dan hora de hardware (hoy, `perf_counter` tras decodificar). Una grabación simultánea de las dos, como dataset para el replay.
3. **La fusión en un grafo de factores:** un paquete nuevo junto a `vision/` que recibe las poses de Marker0 de cada cámara (con su ruido) y estima una sola pose con iSAM2, de forma incremental y con tope de tiempo por frame. Modular: la fuente de cada medida (ArUco de una cámara hoy; IMU o puntos IR mañana) entra como un factor más, sin tocar el resto.
4. **La fusión en el tracker, apagada por defecto:** con la fusión apagada, el tracker hace exactamente lo de hoy; encendida, publica la pose fusionada por el mismo `Marker0ToTracker`.
5. **La dependencia nueva:** `gtsam` en `codigo/requirements.txt`, con su porqué y su versión.

## Criterio de cierre

Números del autor (2026-10-29), medidos con Marker0 de 80 mm a la distancia de trabajo (~35–40 cm) y la caja de luz al máximo:

- **Las cámaras coinciden:** con Marker0 quieto y visto por las dos, la pose de gs2 llevada a gs1 con los extrínsecos difiere de la de gs1 en **< 0.5 mm y < 0.2°** (media sobre una grabación; el plan fija cuántos frames y cuántas posiciones del marker).
- **La fusión mejora a cada cámara:** en reposo, la sd de la posición fusionada es **al menos un 30 % menor** que la de la mejor cámara sola, en la misma grabación.
- **Aguanta que se tape una cámara:** al tapar una cámara **5 s**, la pose fusionada no se pierde y no salta **más de 0.5 mm** ni al taparla ni al destaparla.
- **La cadena no cambia con la fusión apagada:** suite en verde con su tiempo, replay de Marker0 de gs1 y gs2 en 0.0 mm / 0.0° y el selftest del panel, como en la meta 003.
- **Tiempo real:** con la fusión encendida, el bucle sigue a la cámara; el plan fija el tope (ms por frame de la fusión y fps con y sin ventana) frente a los de la meta 003.
- Lo que necesita cámara y Slicer se mide en sesiones en vivo con el autor, con los comandos de Slicer y de PowerShell juntos (regla del autor, 2026-10-25).

## Lo que no se toca

- **La cadena (principio 6):** el nombre `Marker0ToTracker`, el puerto 18944 y la jerarquía en Slicer. Si la fusión cambia qué significa «Tracker» (gs1 u otro frame común), es un ADR y una verificación en vivo con Slicer. Con la fusión apagada, el replay de Marker0 tiene que salir igual.
- La detección ArUco, el PnP IPPE_SQUARE, los intrínsecos y los perfiles gs1 y gs2: se reusan tal cual. Si hace falta tocarlos, el plan dice por qué.
- El IMU, el instrumento y la punta (B40), el registro con el hueso y los puntos IR: fuera de esta meta. El diseño solo deja el hueco.
- La estructura de las cámaras la diseña y construye el autor aparte; la meta no la diseña.
- Los datos de paciente (principio 5): ni el PDF ni las grabaciones los tocan.

## Preguntas que el plan tiene que contestar

- **Un proceso o tres:** un tracker que abre las dos cámaras, o dos trackers que mandan sus poses a un fusionador. Qué cuesta cada uno en fps (dos SVPRO a 90 fps en el mismo PC, USB y CPU) y en cambios a `tracker.py`.
- **La sincronía:** cómo se emparejan medidas de dos cámaras sin hora de hardware, cuánto desfase hay y cómo se mide; si hace falta interpolar o un factor que lo modele.
- **Los extrínsecos:** con qué patrón y método (tablero visto por las dos, `stereoCalibrate` de OpenCV, o Marker0 en varias posiciones), cómo se valida aparte del error que da el propio ajuste, y qué formato y nombre de archivo.
- **El modelo del grafo:** qué nodos y factores (pose por instante, prior por cámara, movimiento entre instantes), cómo se estima el ruido de cada cámara (la sd de la meta 003, la distancia, el ángulo), qué hace con un outlier o con la ambigüedad de IPPE, y qué pasa con el 1-Euro con la fusión encendida.
- **El frame común y el nombre que se publica:** si «Tracker» pasa a ser gs1; qué ADR hace falta.
- **El desarrollo fuera de línea:** cómo se prueba la fusión sobre grabaciones antes de tocar el tracker (scripts con prueba o notebooks, según haga falta, decisión del autor del 2026-10-26), y qué dataset simultáneo hay que grabar.
- **La dependencia:** qué versión de `gtsam` tiene rueda para Python 3.11 en Windows, comprobado por Context7 y en la instalación real.
- **Las fases y su peso (ADR-022),** y en qué fase entra la estructura del autor cuando la tenga.
