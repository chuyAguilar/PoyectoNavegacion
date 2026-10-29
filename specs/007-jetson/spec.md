# Meta 007 — El tracker en la Jetson Orin Nano, con Slicer en el PC

## Por qué

El autor decidió el 2026-10-29 llevar el tracker a la Jetson Orin Nano y dejar su PC (BigDaddy) solo como monitor de 3D Slicer, y hacerlo **antes** de la meta 006 · Grafo de factores óptico-inercial, para que la fusión se construya y se mida directamente donde va a correr. Si la fusión se hiciera en Windows y se mudara después, se harían dos veces el entorno de GTSAM (en Windows no tiene rueda de pip; en Linux aarch64 sí, según su documentación por Context7), la elección entre un proceso y dos trackers (depende de la CPU) y los números de tiempo real. La idea venía de «B23 · Explorar el tracker en una Jetson Orin Nano, con Slicer en BigDaddy» (2026-10-19), que trae el escaneo del equipo y las dudas sin medir.

El equipo (B23): Jetson Orin Nano Developer Kit Super (Yahboom, hostname `yahboom`), Ubuntu 22.04.5 aarch64, JetPack 6.2, CUDA 12.6, 7.4 GB de RAM compartida con Ollama, JupyterLab y otros servicios, NVMe con ~21 GB libres, Docker y Tailscale.

## Qué se construye

1. **El entorno en la Jetson:** Python 3.11 (Ubuntu 22.04 trae 3.10), OpenCV ≥ 4.7 con ArUco y lo demás de `codigo/requirements.txt` que el tracker necesita, reproducible y anotado. De paso, comprobar que `gtsam` instala en ese entorno (la meta 006 lo necesita).
2. **La cámara en Linux:** la capa V4L2 que hoy falta. Abrir las SVPRO con MJPG a 1280×960 y 90 fps, escribir sus ajustes (la meta 002 ya dejó el formato de `controls` independiente del sistema) e identificar cada cámara por su puerto (probablemente `/dev/v4l/by-path/`), con su comprobación al abrir, como hoy en Windows. Los perfiles gs1 y gs2 ganan lo de Linux sin perder lo de Windows.
3. **El tracker de cada cámara en la Jetson,** una por proceso, como hoy, publicando `Marker0ToTracker` por el 18944; Slicer, en el PC, se conecta a la IP de la Jetson.
4. **Las dos cámaras a la vez en la Jetson:** medir si gs1 y gs2 juntas llegan a la cámara (fps, CPU, memoria, temperatura), que es la base de la meta 006.
5. **El panel:** dónde corre y cómo arranca y para el tracker de la Jetson (lo propone el plan con datos: en la Jetson por escritorio remoto, o en el PC lanzando por SSH).
6. **Cómo se trabaja con la Jetson:** cómo llega el código (git en la Jetson), cómo se corre la suite allí, cómo se para sin dejar la cámara ni el puerto tomados (principio 9), y lo que cambia en `docs/CONTEXT.md` §3–§4 y en `CLAUDE.md` §5.

## Criterio de cierre

El autor (2026-10-29) deja que el plan proponga los números de fps y de red con una primera medida, y que la meta cierre con ellos aunque no lleguen: él decide entonces si el tracker se queda en el PC o se optimiza.

- **La cadena igual, en la Jetson:** la suite en verde allí con su tiempo, y el replay de Marker0 de gs1 y gs2 en 0.0 mm / 0.0° (si la aritmética de ARM da una diferencia, se mide y se dice; el plan fija la tolerancia antes de medir). En el PC, la suite y el replay siguen igual.
- **Cada cámara en la Jetson:** abre por su puerto con su marca y sus ajustes, a 1280×960 MJPG; se reportan los fps de la cámara y del bucle, sin y con ventana, la sd z con Marker0 quieto frente a la de la meta 003 (0.030–0.043 mm) y el % de frames con pose. El plan fija el mínimo de fps tras la primera medida.
- **Las dos a la vez:** fps de cada una, CPU, memoria y temperatura, durante un tope de tiempo que fija el plan, con Ollama parado y con Ollama cargado.
- **La llegada a Slicer en el PC:** Hz que recibe Slicer y latencia frente al tracker en el PC, por cable de red o LAN y por Tailscale. El plan fija el mínimo tras la primera medida.
- **Salida limpia:** al parar, la cámara y el puerto 18944 de la Jetson quedan libres, y el tracker aborta con su mensaje si Slicer no llega (ADR-028).
- Todo lo que necesita cámara y Slicer se mide en vivo con el autor, con los comandos de Slicer y de la Jetson juntos (regla del autor, 2026-10-25).

## Lo que no se toca

- **La cadena (principio 6):** `Marker0ToTracker`, el puerto 18944, los mensajes y la jerarquía en Slicer. Lo único que cambia es la máquina del tracker y la dirección a la que se conecta Slicer; si eso pide cambiar algo de la cadena, es un ADR y una verificación en vivo.
- El tracker en el PC sigue funcionando igual: Windows no pierde nada (capa MSMF/DSHOW, perfiles, panel).
- La detección, el PnP, el filtro y los intrínsecos: el mismo código y los mismos `.yml` (valen si no se toca el foco ni la resolución). Las cámaras no se recalibran salvo que la medida lo pida.
- La fusión de las dos cámaras (meta 006), el IMU y el instrumento (B40): fuera.
- Los datos de paciente (principio 5): no viajan a la Jetson si el plan propone un clon sin ellos; si va el clon completo, nadie los abre.
- Lo que ya corre en la Jetson (Ollama, JupyterLab, Docker): no se desinstala ni se reconfigura sin preguntar al autor.

## Preguntas que el plan tiene que contestar

- **El entorno:** Python 3.11 por deadsnakes, conda o un contenedor de Docker; cómo se instala OpenCV con ArUco en aarch64 (rueda de pip o compilado) y si `gtsam` tiene rueda para ese Python; cuánto disco ocupa (quedan ~21 GB).
- **La identidad de cada cámara en Linux** (`/dev/v4l/by-path/` u otra) y cómo se escriben los ajustes por V4L2; qué dice `v4l2-ctl` de los modos y de los controles; si la marca `focus` se lee igual.
- **El código:** la capa de Linux de `camera/` y cómo se prueba sin cámara en la suite, sin tocar lo de Windows. Lo que hoy da por hecho Windows (`OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS`, rutas con `\`, `--stop-stdin`, el panel).
- **La red:** cable directo, LAN o Tailscale; cómo se mide la latencia tracker → Slicer entre dos máquinas con relojes distintos.
- **El panel:** dónde corre y cómo controla el tracker de la Jetson.
- **El clon en la Jetson:** completo o sin los datos de paciente; cómo se pone al día y quién hace el commit si algo cambia allí (el autor; ningún agente ejecuta commit ni push, principio 1).
- **Cómo trabaja `desarrollo` con la Jetson:** si se conecta por SSH desde el PC o el autor corre los comandos allí; qué permisos de `settings.json` haría falta proponer.
- **Ollama:** cuánta memoria y CPU le quita al tracker, y si hay que pararlo durante el tracking.
- **Las fases y su peso (ADR-022).**
