# Aclaraciones — Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

## P1 · El orden frente a la meta 006

- **Opciones:** la Jetson antes de la meta 006 · Grafo de factores óptico-inercial / la 006 primero en Windows y mudarla después.
- **Respuesta del autor:** la Jetson va antes de la meta 006.
- **Fecha:** 2026-10-29.

## P2 · El alcance de cámaras

- **Opciones:** las dos cámaras, una por proceso / solo una.
- **Respuesta del autor:** las dos cámaras, una por proceso.
- **Fecha:** 2026-10-29.

## P3 · Los mínimos de fps sin ventana y de la red (Hz en Slicer, latencia)

- **Opciones:** fijarlos ahora / que los proponga el plan tras una primera medida.
- **Respuesta del autor:** los propone el plan tras una primera medida (en el plan, P13, provisionales hasta la fase 3).
- **Fecha:** 2026-10-29.

## P4 · Si no se llega a los mínimos

- **Opciones:** la meta sigue hasta llegar / la meta cierra con los números y el autor decide.
- **Respuesta del autor:** la meta cierra con los números y el autor decide entonces si el tracker se queda en el PC o se optimiza.
- **Fecha:** 2026-10-29.

## P5 · Dónde corre el panel

- **Opciones:** en la Jetson por escritorio remoto / en el PC lanzando por SSH.
- **Respuesta del autor:** lo propone el plan (en el plan, P16: en el PC por SSH, recomendado).
- **Fecha:** 2026-10-29.

## P6 · Python 3.11 en la Jetson

- **Opciones:** uv en `~/.venvs/navegacion` (descarga un CPython 3.11 gestionado; sin sudo ni tocar el Python del sistema; Linux aarch64 con soporte de nivel 2, Context7), recomendada / deadsnakes (PPA en apt y sudo) / miniforge / un contenedor Docker de L4T (aísla, pero complica cámaras y red) / el Python 3.10 del sistema (sin instalar nada, pero distinto del PC).
- **Respuesta del autor:** primero un escaneo del equipo y de sus capacidades técnicas (sistema, Python, CPU/GPU, memoria, disco, USB, V4L2, red, servicios); con ese escaneo se decide cómo se pone Python 3.11. La fase 1 pasa a ser el escaneo.
- **Fecha:** 2026-10-29

## P7 · Cómo llega el código a la Jetson

- **Opciones:** clon parcial y disperso de `origin` sin datos de paciente (`git clone --filter=blob:none --sparse` y patrones que dejan fuera `herramientas/`, `documentos/` y `*.nrrd`/`*.dcm`; no descarga esos blobs), más la copia WIP de `codigo/` con `enviar_wip.ps1` para verificar una fase antes de su commit, recomendada / el clon completo (nadie abre los datos; ~700 MB) / solo la copia WIP, sin git. En la Jetson nadie hace commit: el clon solo hace `git pull --ff-only`.
- **Respuesta del autor:** (a) clon parcial y disperso de `origin` sin datos de paciente (sin `herramientas/`, `documentos/`, `*.nrrd` ni `*.dcm`), más la copia del trabajo sin commit con `enviar_wip.ps1`; en la Jetson nadie hace commit.
- **Fecha:** 2026-10-29

## P8 · Quién corre los comandos en la Jetson

- **Opciones:** el autor, con los protocolos de cada fase, recomendada para esta meta / un `allow` de `ssh yahboom …` en `settings.json` para `desarrollo` y `pruebas` (más rápido, pero deja ejecutar cualquier cosa en la Jetson; necesita una clave aparte).
- **Respuesta del autor:** los agentes, por SSH, pero con protocolos de seguridad al interactuar con la Jetson para no dejarla inservible («brickearla») ni hacer nada peor. El plan define esos protocolos: qué puede ejecutar un agente y qué no (nada con sudo, apt, reinicio, `nvpmodel`, `jetson_clocks`, firmware, arranque, particiones, servicios del sistema, ni escribir fuera de la carpeta del proyecto), cómo se hace cumplir de verdad (no solo con patrones de `settings.json`; p. ej. una clave propia con orden forzada y lista blanca en la Jetson), con tope de tiempo y registro de lo ejecutado, y qué queda siempre para el autor. Los cambios de `settings.json` y de la Jetson los aplica el autor.
- **Fecha:** 2026-10-29

## P9 · Qué redes se miden, y con qué interfaces

- **Opciones:** LAN por router y Tailscale, recomendada / cable directo PC–Jetson y Tailscale / las tres. Además: los nombres de interfaz de la Jetson (`ip -br addr`), que hacen falta para `--igtl-iface`.
- **Respuesta del autor:** (c) las tres: LAN por router, cable directo PC–Jetson y Tailscale. Los nombres de interfaz salen del escaneo.
- **Fecha:** 2026-10-29

## P10 · Dónde se elige la interfaz de escucha del servidor OpenIGTLink

- **Opciones:** la opción `--igtl-iface` del tracker (solo Linux; sin ella, 127.0.0.1 como hoy), recomendada / una clave del perfil (pero es de la máquina, no de la cámara) / escuchar en todas (0.0.0.0), rodeando a `pyigtl`, que no lo permite.
- **Respuesta del autor:** (a) la opción `--igtl-iface` del tracker, solo Linux; sin ella, 127.0.0.1 como hoy; ADR y verificación en vivo con Slicer.
- **Fecha:** 2026-10-29

## P11 · Los perfiles de cámara en Linux

- **Opciones:** `usb_port_linux` en los mismos `tracker_config_gs1.yaml` y `_gs2.yaml` (en Linux el backend es siempre V4L2), recomendada / perfiles aparte `tracker_config_gs{1,2}_jetson.yaml` (duplican detector, marca, intrínsecos y filtro).
- **Respuesta del autor:** (a) `usb_port_linux` en los mismos `tracker_config_gs1.yaml` y `_gs2.yaml`.
- **Fecha:** 2026-10-29

## P12 · Cómo se escriben y leen los controles en Linux

- **Opciones:** `v4l2-ctl` por subproceso con tope (si no está, instalar `v4l-utils` con apt: sudo y permiso del autor), recomendada / cv2 `set/get` con `CAP_V4L2` (sin dependencia, pero `set` True no asegura nada y algunos controles no tienen propiedad) / ioctl por ctypes (sin dependencia, más código).
- **Respuesta del autor:** (a) `v4l2-ctl` por subproceso con tope; si hace falta instalar `v4l-utils`, con permiso del autor.
- **Fecha:** 2026-10-29

## P13 · Los mínimos provisionales (se confirman tras la fase 3, antes de la fase 4)

- **Opciones:**
  - Lo propuesto: una cámara sin ventana ≥ 60 fps de bucle (el techo de Slicer es ~65 Hz, B54); dos a la vez ≥ 45 fps cada una; Slicer por LAN ≥ 55 Hz; latencia de red añadida p95 ≤ 10 ms por LAN y ≤ 30 ms por Tailscale; con ventana, solo se reporta.
  - Otros números del autor.
- **Respuesta del autor:** (a) los propuestos, provisionales hasta medir la primera cámara: una cámara sin ventana ≥ 60 fps; dos a la vez ≥ 45 fps cada una; Slicer por LAN ≥ 55 Hz; latencia añadida p95 ≤ 10 ms por LAN y ≤ 30 ms por Tailscale.
- **Fecha:** 2026-10-29

## P14 · La tolerancia del replay de Marker0 en ARM

- **Opciones:** la misma que hoy (1e-9 mm, 1e-9°, 1e-6 px) y, si falla, se mide la diferencia y decide el autor, recomendada / aceptar de antemano, solo en Linux, hasta 0.001 mm, 0.001° y 0.01 px (el 3 % de la sd z en reposo).
- **Respuesta del autor:** (a) la de hoy (1e-9 mm, 1e-9°, 1e-6 px); si falla en ARM, se mide la diferencia y decide el autor.
- **Fecha:** 2026-10-29

## P15 · Ollama durante las medidas

- **Opciones:** el autor lo para (`systemctl stop ollama`) para la condición «parado», lo vuelve a arrancar y dice qué modelo cargar para la condición «cargado», recomendada / no se para y se mide con lo que haya. Además: si durante el tracking normal se para.
- **Respuesta del autor:** (a) medir con Ollama parado y con un modelo cargado; con los números el autor decide si se para durante el tracking.
- **Fecha:** 2026-10-29

## P16 · El panel y el acceso por SSH

- **Opciones:** el panel en el PC, por SSH con clave (el autor crea la clave, la copia a la Jetson y define el alias `yahboom` en su `~/.ssh/config`, fuera del repo), recomendada / el panel en la Jetson por escritorio remoto (PySide6 no tiene rueda para la glibc 2.35 de Ubuntu 22.04: habría que compilarlo; y el escritorio remoto le quita CPU al tracker).
- **Respuesta del autor:** lo que sea mejor para el sistema, estable y reproducible en otras máquinas. La dirección lo lee como (a), el panel en el PC por SSH con clave: PySide6 instala por pip en el PC, y compilarlo en la Jetson no es reproducible; el plan lo confirma o dice por qué no.
- **Fecha:** 2026-10-29

## P17 · El modo de energía de la Jetson

- **Opciones:** medir en MAXN_SUPER tal como está y anotar `nvpmodel -q`, sin `jetson_clocks`, recomendada / fijar los relojes con `jetson_clocks` (cambia la máquina; con permiso del autor).
- **Respuesta del autor:** (a) MAXN_SUPER tal cual, anotando `nvpmodel -q`, sin `jetson_clocks`.
- **Fecha:** 2026-10-29

## P18 · El puerto del segundo tracker en la fase 5

- **Opciones:** un perfil temporal fuera del repo con `transforms_port: 18946`, recomendada / una opción `--igtl-port` del tracker (toca la cadena: otro ADR y su verificación). Que Slicer reciba de las dos a la vez queda para la meta 006.
- **Respuesta del autor:** (a) un perfil temporal fuera del repo con `transforms_port: 18946`.
- **Fecha:** 2026-10-29

## P19 · Quién teclea lo que abre la cámara en la Jetson

- **Opciones:** (a) el autor, en la sesión en vivo, con los comandos del protocolo, por el mismo alias `nav-jetson` y el mismo guardián (`camara rafaga` y `py … tracker`); mantiene la regla de `desarrollo` y `pruebas` («No abres la cámara, el tracker ni Slicer»), recomendada / (b) los agentes, por el guardián, en una sesión en vivo con el autor presente que lo confirma antes; cambia esa regla de los dos agentes.
- **Respuesta del autor:** (a) el autor, en la sesión en vivo, por el mismo guardián; `desarrollo` y `pruebas` no abren la cámara.
- **Fecha:** 2026-10-29

## P20 · La clave personal del autor hacia la Jetson y su sudo allí

- **Opciones:** (a) la clave personal (alias `yahboom`) con frase de paso, sin dejarla cargada en el agente de claves de Windows, y el `sudo` de la cuenta del autor con contraseña; cierra el rodeo por el que un agente, que corre como el usuario de Windows del autor, podría usarla (plan, hallazgo 7; B69), recomendada / (b) como esté hoy; B69 sube a alta.
- **Respuesta del autor:** (a) su clave personal hacia la Jetson lleva frase de paso y no se deja cargada en Windows; su `sudo` allí pide contraseña.
- **Fecha:** 2026-10-29

(La pregunta del método de Python 3.11 no se abre ahora: se abre al cerrar la fase 1, con los datos del escaneo, por P6.)

## P21 · Cómo se pone Python 3.11 en la Jetson (abierta tras el escaneo de la fase 1)

- **Opciones:** (a) uv, un CPython 3.11 propio de la cuenta del proyecto, sin sudo ni tocar el del sistema; (b) miniforge (ya en la cuenta `jetson`; más pesado, con ~21 GB libres); (c) deadsnakes por apt, con sudo; (d) el 3.10.12 del sistema. El escaneo: Python 3.10.12, glibc 2.35, sin ningún 3.11; uv y miniforge3 solo en la cuenta `jetson`.
- **Respuesta del autor:** (a) uv.
- **Fecha:** 2026-10-29
