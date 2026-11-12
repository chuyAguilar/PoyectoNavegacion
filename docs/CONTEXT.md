# CONTEXT.md — Reglas, Límites y Estado

> **Qué es este documento (MVD 3 de 3):** las **reglas y el estado**. Reglas de
> negocio, límites de seguridad/privacidad, entorno y máquinas, qué está hecho vs
> WIP, y las **restricciones no negociables** que cualquiera —humano o IA— debe
> respetar al tocar este proyecto. Documento **vivo**: se lee ANTES de trabajar y
> se actualiza al cerrar cada iteración.
>
> El *qué* está en `ARCHITECTURE.md`; el *porqué* en `DECISIONS.md`.
> _Última actualización: 2026-11-11 (§3 y §6: meta 006, fase 7c2 · `Reference` y `ReferenceToTracker`: la referencia se llama `Reference` y la cadena publica `ReferenceToTracker`; lo hecho antes conserva «Marker0»). Antes, 2026-11-10 (§6: meta 006, fase 7a · El asistente de captura del tablero, hecha sin cámara). Antes, 2026-11-09 (§6: meta 006, fase 2 · S2 otra vez en Windows, y B94, hecha con el veredicto «se movió»). Antes, 2026-11-05 (§4.21 y §6: meta 007, fase 7b · Las dos cámaras a la vez en Windows: la causa de B5 medida, el concentrador USB 2.0 compartido; gs2 pasa al frontal USB 3.0, P-7b5). Antes, 2026-11-04 (§6: meta 007, fase 7b, parte B: la marca y los ajustes por COM en el tracker de Windows, hecha sin cámara). Antes, 2026-11-02 (§6: meta 007, fase 4 · La suite corre en Linux, hecha: 0 fallos en la Jetson). Antes, 2026-11-02 (§6: meta 007, fase 3 · El entorno en la Jetson, parcial, con el venv y la suite en la Jetson; faltan las ráfagas). Antes, 2026-11-02 (§6: meta 007, fase 3, parcial, esperando el guardián 3). Antes, 2026-11-02 (§6: meta 007 · El tracker en la Jetson Orin Nano, fase 2 · La barrera de seguridad para los agentes, hecha con los números en vivo). Antes, 2026-10-29 (§6: la meta 007 entra en la vía activa, fase 1). Las actualizaciones anteriores, en el historial de git._

---

## 1. Reglas de negocio y de dominio

- **Es un prototipo de investigación, NO un dispositivo clínico.** No está
  certificado ni validado para uso en pacientes reales. Toda prueba se hace sobre
  un **phantom impreso 3D** (columna L1–L5 + sacro segmentada de un CT). Cualquier
  lenguaje de "listo para cirugía" es incorrecto hasta que exista validación
  formal.
- **La verdad es cuantitativa, no visual.** Nada se declara "hecho" con "se ve
  bien": se mide (RMS de registro, spread de la punta, reproyección del BA, TRE).
  Objetivo de precisión: RMS de registro **< 1.5 mm** deseable, **< 3 mm**
  aceptable; **> 5 mm** = algo está mal, se investiga.
- **Diagnóstico antes que fix, una variable a la vez.** No cambiar varias cosas a
  la vez "a ver si funciona".

## 2. Seguridad y privacidad

- **Datos de paciente (CT/DICOM).** El STL del hueso proviene del CT de un
  paciente. El DICOM (`herramientas/A/`) y el volumen CT
  (`codigo/historico/iter2/202 AXIAL.nrrd`) **sí están versionados**: el repo es
  de uso del equipo médico y el autor decidió dejarlos en el árbol (ADR-019).
  Ningún agente los lee ni los envía a servicios externos (`docs/constitution.md`
  principio 5; `.claude/settings.json`). Tratar cualquier dato clínico con
  cuidado; ante duda, no exponerlo.
- **Fallar fuerte, no en silencio.** Un sistema que se niega a arrancar y dice por
  qué es mejor que uno que hace lo incorrecto callado. Los scripts deben validar
  sus entradas (geometría, config, calibración presente y coherente) y abortar con
  mensaje claro si algo falta o no cuadra, en vez de producir un resultado
  plausible pero falso.

## 3. Entorno y máquinas

- **Máquina principal:** `BigDaddy` (Windows 10/11). GPU **RTX 3060** (suficiente
  para inferencia si se retoma deep learning). Todos los comandos de shell se
  corren desde **PowerShell**.
- **Raíz del proyecto:** `C:\Dev\OrtoMeta\PoyectoNavegacion` (antes
  `C:\Dev\Dr.Milton\PoyectoNavegacion` y `C:\Dev\PoyectoNavegacion`; los archivos
  vivos se corrigieron el 2026-10-19, meta 001; los históricos las conservan).
- **Código activo:** `codigo\`, en paquetes por responsabilidad (`camera`, `vision`,
  `transport`, `profiles`, `calibration`, `diagnostics`, `gui`, `slicer`;
  `tracker.py`); se lanza con `python -m <paquete>.<modulo>` **desde `codigo\`** y las
  rutas de un perfil son relativas a `codigo\` (desde 2026-10-23, meta 003, ADR-027).
  `codigo\historico\` es archivo, no se mantiene. Entorno virtual: `codigo\.venv\`
  (**Python 3.11.9**, fijado en `.python-version`).
- **Stack de software:**
  - Python 3.11.9 + **OpenCV 4.11** (`opencv-python` 4.11.0.86: ArUco está en el
    módulo principal, `objdetect`, desde 4.7; no hace falta el paquete contrib) + scipy
    + numpy + PyYAML + **pyigtl** 0.3.1 + **pyorbbecsdk2** (solo para la Femto
    archivada y `femto_pruebas/`; NO el viejo `pyorbbecsdk` 1.3.2, roto en Windows).
  - **3D Slicer 5.x** + extensión **SlicerIGT** (visualización, Fiducial
    Registration Wizard, Volume Reslice Driver). Corre aparte; no se controla
    directo, se le pasan scripts para su consola Python.
  - `open3d` 0.18 en el venv (usado por `femto_pruebas/`, hoy en pausa).
  - **PySide6 6.11.1** instalado en el venv (GUI del panel, brief-01; en
    `requirements.txt` como `pyside6>=6.7,<7`).
- **Cámaras:** dos **SVPRO AR0234 global shutter**, un perfil cada una:
  `codigo\profiles\tracker_config_gs1.yaml` y `_gs2.yaml` (identidad por la ruta del
  puerto USB y la marca `focus`; 1280×960 MJPG 90 fps, sin modo de 60 (pedir 60 da ~29,
  fase 7 de la meta 003); intrínsecos en
  `codigo\data\intrinsecos_gs{1,2}_1280x960.yml`). Solo la referencia (`name: Reference`
  en el perfil; hasta la fase 7c2 de la meta 006, Marker0), hoy el ID 0 de 80 mm. La Femto
  Bolt y el contexto «doctor» están archivados en `codigo\historico\iter4\femto\` y
  `old_profiles\` (ADR-025).
- **Segunda máquina (a confirmar):** memoria registra un "equipo del doctor"
  aparte (marker 16.58 mm). Si sigue vivo, se documenta por separado; no es la
  máquina de referencia de estos MVD.

## 4. Restricciones NO negociables (trampas ya pagadas — no repetir)

1. **Git SIEMPRE desde PowerShell, nunca desde el sandbox Linux** sobre el repo
   NTFS: deja `.git\index.lock` huérfano. Si aparece, limpiarlo desde PowerShell.
   El `.gitattributes` fija el EOL (había cambios fantasma por ciclo CRLF).
2. **`Edit`/`Write` truncan archivos** silenciosamente a veces. Tras editar,
   validar con `wc -l` y `py_compile`; reconstruir si truncó.
3. **Cámara webcam: backend `MSMF` + códec `MJPG`**, o el FPS cae a ~5.
4. **No enviar video por OpenIGTLink** (`send_video: false`): satura el pipeline.
5. **Slicer se conecta ANTES de arrancar el tracker** (OpenIGTLink IF activo). El tracker
   lo espera con tope, `--slicer-timeout` (30 s), y si no llega aborta: lo dice
   («Slicer no se conecto al puerto 18944 en 30 s»), no abre la cámara, cierra el servidor
   y sale con código 3 (fase 7 de la meta 003, ADR-028; en vivo se vio el mensaje, la
   cámara sin abrir y la salida limpia; el código lo fija la suite). Antes de la fase 7,
   `pyigtl` bloqueaba el bucle. Desde la fase 7b (2026-10-25) el panel lo pregunta en los
   dos botones del tracker (con y sin ventana) con ese texto, ya sin «SE BLOQUEA».
6. **Marcadores impresos en NEGRO mate**, no colores (contraste en escala de
   grises para la detección).
7. **Capturas con *depth*: SIEMPRE fuera de la caja de luz** (multipath ToF:
   +57 mm de bias dentro). RGB sí puede ir dentro.
8. **Usar geometría `reference_*_calibrado.txt`** (BA), nunca la teórica, una vez
   hecho el bundle adjustment.
9. **Geometría del rigid body y calibración de la punta = mismo ensamble físico.**
   NO mezclar geometrías (p.ej. la punta `viejo_dock` es del dodecaedro viejo y
   NO sirve con la config v2).
10. **La calibración es por-setup.** Cámara movida/reenfocada → recalibrar
    intrínsecos. Stylus desarmado/rearmado → recalibrar la punta.
11. **Scripts no triviales: verbose paso a paso** (p.ej. `verbose=2` en scipy).
    Nada de quedarse mudo hasta el final.
12. **Guardar la escena de Slicer como `.mrml`** antes de cerrar (preserva
    jerarquía y transforms).
> **13–17, del dodecaedro archivado (nota del 2026-10-24, meta 003):** los scripts que
> nombran están en `codigo\historico\iter4\dodecahedron\` y ya no los lanza nada vivo;
> las rutas `iter4/data/...` son las de entonces. Quedan como registro y valen si el
> instrumento nuevo (B40) reusa ese código.

13. **`calibrar_rigid_body.py` trae defaults del stylus VIEJO** (`--ancla 170`,
    `--marker-mm 13.4`). Para el dodecaedro v2 hay que pasar **`--ancla 3
    --marker-mm 14.6`** explícitos, o el BA calibra contra el rigid body
    equivocado. (Trampa detectada al sondear el código, 2026-08-13.)
14. **`captura_calibracion.py --geometry-file` sin valor cae en
    `iter4/data/reference_dodecaedro.txt`** (teórica VIEJA, IDs 170–180) porque
    ese archivo existe — antes de mirar el config. Con el dodecaedro v2 captura
    **0 frames útiles en silencio**. Pasar `--geometry-file` explícito SIEMPRE
    (la GUI ya lo hace).
15. **El BA contradice a ADR-008 si se corre con defaults sobre un dataset
    Femto:** `use_depth` default ON activa residuos 3D. Pasar **`--no-depth`**
    explícito (y `--no-sparse` para el dataset v2, ADR-009). Además el
    `--output` default pisaría `reference_dodecaedro_calibrado.txt` (del stylus
    viejo): salida siempre explícita.
16. **`calibrar_tip_divot.py` se AUTOCIERRA a los `--timeout` segundos
    (default 600)**: si la sesión de posturas se alarga, termina solo y
    resuelve con lo capturado (o falla con <4 posturas).
17. **`generar_reference_dodecaedro.py --output` default cae en `codigo\data\`**
    (ruta relativa al CWD — carpeta equivocada que además crea en silencio) y
    sus IDs/tamaño default son del stylus viejo (170–180, 13.4 mm). Pasar
    `--output iter4/data/...` y el layout completo explícitos (la GUI ya lo
    hace, brief-02 M2).
18. **La aceleración HW de MSMF alarga la apertura de las SVPRO de ~4 s a
    43–51 s sin dar fps** (`OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS`, por
    defecto activa; medido 2026-10-22: 90.0 fps con y sin ella). Tiene que estar
    en `0` **antes del primer `import cv2` del proceso**: `cv2.pyd` copia el
    entorno al cargarse y ponerla después no hace nada. El código lo hace con
    `import camera` antes de `import cv2` (los scripts que abren MSMF, y desde
    la fase 4 de la meta 003 también `tracker.py`: a mano la apaga y lo dice
    en su log; B28, en vivo 2026-10-24: abre en 0.4 s) y el panel se la pasa a
    sus procesos (`gui.processes.entorno_hijo`).
19. **La marca `focus` de una cámara solo es fiable si se escribió.** La cámara 2
    nunca la tenía escrita y por DSHOW leía 332, 268, 362, 254, 337…, así que el
    backend paraba («no es la del perfil») sin motivo. Al dar de alta un perfil
    (desde `codigo\`): `python -m diagnostics.probe_camera --fijar "focus=N" --forzar
    --puerto <ruta> --salida <json> --timeout <s>` (era `sondear_camara.py`; `--forzar`
    escribe aunque la lectura ya diga N; sin él `aplicar` no escribe lo que ya
    coincide). Después la marca persiste tras desenchufar.
20. **El tracking va con la caja de luz al máximo.** Por debajo del máximo, las SVPRO
    bajan solas de 90 a 22–31 fps (medido con el hilo de captura, fase 7 de la meta 003,
    2026-10-25): algún control automático que el perfil no fija (B50). Pedir 60 fps no
    sirve: la cámara no tiene ese modo a 1280×960 MJPG y entrega ~29.
21. **En Windows, cada cámara en su propio enlace USB 2.0: gs1 en el concentrador Genesys
    (`05E3:0608`, `…#USB(11)#USB(3)`) y gs2 en el frontal USB 3.0 (`…#USB(5)`, directo
    al concentrador raíz).** Con las dos MJPG 1280x960 90 fps en el mismo concentrador
    USB 2.0 (el Genesys, `HS11`), la segunda abre por MSMF y pasa la marca y los ajustes
    por COM, pero `grabFrame` falla con `0x800718CF` («una interfaz de cámara no tiene el
    ancho de banda deseado para la transferencia de datos») y no da ningún frame, en los
    dos órdenes (P-7b-B, 2026-11-04): no caben las dos reservas isócronas en un enlace.
    Con gs2 en `USB(5)`, la única variable cambiada (P-7b5, 2026-11-05), las dos a la vez
    cumplen en los dos órdenes: gs1 → gs2 89.9 / 90.0 fps de cámara y listeners a
    88.6 / 88.6 mensajes/s; gs2 → gs1 90.0 / 89.5 fps y 89.4 / 89.1; códigos 0, sin
    `0x800718CF`. Cuánto reserva cada cámara (¿~197 Mbit/s?) es hipótesis, sin leer su
    descriptor (B97). Si una cámara cambia de puerto, cambia su ruta: medirla otra vez con
    `python -m diagnostics.probe_camera --puertos` y poner al día `usb_port_windows` del
    perfil (con la ruta vieja el backend no la encuentra; si se cruzan, la marca `focus`
    lo detecta y para). Aparte, con las dos en el Genesys y una transmitiendo por MSMF, la
    apertura corta por `cv2`/DSHOW de la otra daba `isOpened=0` a ~2 s, también a 640x480
    (P-7b-A, 2026-11-04; probablemente la misma causa, sin medir). Por eso en Windows la
    marca y los ajustes se leen y se escriben por COM sobre el filtro de captura, sin
    abrir vídeo (`camera/dshow_props.py`; el tracker, desde la parte B de la fase 7b).
    No volver a la apertura corta para leer una cámara mientras la otra corre.

## 5. Metodología de trabajo (cómo colaboramos humano + IA)

Desde el 2026-10-19, el método por specs: `docs/constitution.md` (lo que no se negocia), `CLAUDE.md` (cómo se trabaja), `memory.md` y `specs/` (ADR-020). Ningún agente hace commit ni push; los hace el autor. El método anterior de briefs (adoptado el 2026-08-13) queda en el historial de git de este archivo.

Desde el 2026-10-28 (ADR-034, meta 005 · Agente de consulta para el equipo y buzón de peticiones), los compañeros del equipo también hacen commit y push, pero solo de archivos nuevos en `peticiones/`: una petición por archivo, escrita por el agente `consulta` y enviada por el compañero con los cinco comandos de `peticiones/README.md` («Cómo se envía»). En sus máquinas la filtran los hooks `pre-commit` y `pre-push` de `equipo/hooks/` (`git config core.hooksPath equipo/hooks`); el autor decide cada petición desde `direccion`. Siguen sin hacer commit ni push los agentes, `consulta` incluido.

## 6. Estado del proyecto (hecho / en pausa / WIP)

### Hecho y validado

- **Tracking de la referencia** (`python -m tracker`, meta 003; la referencia se llamó Marker0 hasta la fase 7c2 de la meta 006): `camera` (dos SVPRO global
  shutter por puerto USB y marca, aceleración HW de MSMF apagada) → `vision` (ArUco con
  lista blanca, IPPE_SQUARE con z > 0, 1-Euro de la posición) → `transport`
  (`ReferenceToTracker` por OpenIGTLink, 18944; antes `Marker0ToTracker`) → Slicer. Línea base (fase 1, Marker0
  quieto a ~37–38 cm): 100 % de frames con pose, sd z 0.043 mm (gs1) y 0.039 mm (gs2),
  orientación 0.10–0.13°. Desde la fase 7 (ADR-028) la captura va en un hilo con el último
  frame y el envío no espera; en vivo (2026-10-25, caja de luz al máximo, cámara a 90):
  con ventana, gs1 61.7 fps (sd z 0.033 mm) y gs2 55.2 (sd z 0.034, aceptado por el autor,
  P11), Slicer 50.4–56.9 Hz; sin ventana, el bucle va al ritmo de la cámara, 89.9 y 88.8
  fps (sd z 0.037 y 0.030 mm, 99.96 % con pose), y Slicer recibe como mucho ~65 Hz: el
  techo es de Slicer, no del tracker (fase 8b, R2; B54). Salida limpia con los dos botones
  del tracker del panel y el 18944 libre (fase 8a).
- **Las dos cámaras calibradas** (meta 002, cerrada el 2026-10-23; números en
  `specs/002-calibracion-camaras/resultados.md`): 1280×960 MJPG 90 fps, 0.977 ms;
  cámara 1 RMS 0.167 / control 0.146 px, cámara 2 0.154 / 0.150 px (detector `sb`,
  tablero de 24.86 mm); escala por medias +0.27 y −0.37 mm en 80 mm. Calibración desde
  el panel en tres pasos (enfocar, tablero, escala). **No girar ni sacar el lente de la
  cámara 2 sin recalibrar** (cy 389.8, B36).
- **Suite pytest sin cámara** (`codigo\tests\`, 618 pruebas al cerrar la meta 004, 34.3 s, 2026-10-26; 555 desde la fase 8b de la meta 003; ~33 s en la 8b, 41 y 56 s en la 8c, 42–47 s en la 8a con la CPU al 79 % por otros programas, ~24–26 s en la 7b): niega la cámara
  real y el servidor pyigtl (B34); la comprobación de «no cambió» es la suite, el
  selftest del panel y el replay de Marker0 (`docs/ARCHITECTURE.md` §6).
- **Meta 003 · Arquitectura y optimización del tracker** (`specs/003-arquitectura-tracker/`, números en `resultados.md`): fase 8c · Cierre de la meta hecha el 2026-10-25 y commiteada (`26e724e`). Paso 1, la arquitectura (fases 1–5; ADR-026 y ADR-027): el código por responsabilidad bajo `codigo\`, `codigo\iter4\` vacío, el dodecaedro y la Femto archivados, la cadena solo con `Marker0ToTracker` y el replay de Marker0 en 0.0 mm / 0.0°. Paso 2, la optimización (fases 6–8b; ADR-028 a ADR-030): el envío ya no espera el tic, la captura va en un hilo, el panel arranca el tracker sin ventana (~89–90 fps) y con ventana (gs1 61.7, gs2 55.2 aceptado, P11), la sd z no empeora (0.030–0.037 mm frente a 0.039–0.043) y el techo de ~65 Hz en Slicer está explicado (R2, B54).
- **Meta 004 · Cómo funciona el tracker** (`specs/004-como-funciona/`, números en `resultados.md`): cerrada el 2026-10-26, a falta del commit del autor. `docs/ARCHITECTURE.md` §9: el mapa del proyecto en Mermaid y SVG (ADR-032), la detección → pose en 11 pasos, un ejemplo resuelto con el frame 480 de gs1 (`diagnostics/explain_pose.py`, 0.0 mm / 0.0° frente al replay), el glosario y la fuente de cada número; una prueba ata §9 al código (0 referencias inexistentes). El autor leyó §9.2 y §9.4 y no le quedó ninguna duda (P12). De paso, «Verificar IDs» pone la cámara en verde (fase 2b) y «Comprobar escala con regla» ya no se congela (fase 2c). La cadena no cambió.
- **Histórico (archivado, se puede retomar):** el dodecaedro v2 (IDs 3–13, BA a 1.26 px),
  su punta por dock (spread ~1.8 mm) y la jerarquía de Slicer con registro
  **paired-point** (RMS 2.80–3.46 mm) y navegación tomográfica (iter 3), en
  `codigo\historico\iter4\dodecahedron\` y `documentos\historico\MANUAL_simplificado.md`.

### Vía activa

- **Rumbo (2026-10-20; ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen mejorados sobre gs1/gs2. Solo valen los perfiles `profiles\tracker_config_gs1.yaml` y `_gs2.yaml`. Los contextos viejos (Femto `tracker_config.yaml`, «doctor» `tracker_config_doctor.yaml` + `globalshutter.yml`; ADR-014/015/016) están archivados en `codigo\historico\iter4\femto\` y `old_profiles\` como referencia.

- **Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC** (`specs/007-jetson/`, desde el 2026-10-29): la fase 1 · El escaneo de la Jetson, solo lectura (`codigo\linux\`), hecha el 2026-10-29 con el escaneo del autor. La fase 2 · La barrera de seguridad para los agentes (`guardian.py`, `sonda_privilegios.py`, `instalar_guardian.sh`, `probar_barrera.ps1`): hecha el 2026-11-02. El P-2 del autor sacó tres fallos (los grupos extra de `adduser`, la ruta con espacio de `probar_barrera.ps1` y el tope de 3 s que duraba 8), arreglados; con el guardián 2 en la Jetson: 30 de 30 casos (el 24 en 3.51 s), la sonda con 0 privilegios en 28 y el registro igual a `journalctl` (122 líneas). Desde entonces los agentes entran a la Jetson solo por `ssh nav-jetson <verbo>` (`settings.json`, `desarrollo.md` y `pruebas.md`). La fase 3 · El entorno en la Jetson, hecha el 2026-11-02 (las ráfagas del autor: gs1 y gs2 estables a 88.5 fps, criterio ≥ 85): con el guardián 3 en la Jetson (el 2 moría en toda orden pesada al leer las zonas térmicas, B75), el clon disperso sin datos de paciente, la copia WIP (`enviar_wip.ps1`) y el venv `~/.venvs/navegacion` (uv, P21: CPython 3.11.9 y las mismas versiones que en el PC; gtsam 4.3.0 instala aparte; 529 MB) ya están; la sonda por `py` da 0 privilegios y la suite allí, 760 de 840 (35 fallos, inventario para la fase 4). La fase 4 · La suite corre en Linux, hecha el 2026-11-02: en la Jetson, 841 con 0 fallos (783 pasan, 58 saltadas con su motivo, 39.8 s); en Linux el replay admite 1e-3 mm, 1e-3° y 1e-3 px (P22; en ARM la detección difiere en 6.1e-05 px), en Windows la de siempre; el PC sigue igual (836 pasan, 5 saltadas) y B74 se cerró.

- **Meta 007, fase 5 · La capa V4L2 y cada cámara en la Jetson** (hecha el 2026-11-03 con el P-5 del autor): `camera/v4l2.py` y la rama Linux de `WebcamBackend` abren cada cámara por su enlace by-path (`usb_port_linux` en los perfiles) con `cv2.VideoCapture("/dev/videoN", CAP_V4L2)`, tras comprobar la marca `focus` y aplicar los controles con `v4l2-ctl` (la exposición se compara en unidades nativas, 100 µs). En la Jetson, sin abrir la cámara, se leen los 11 controles del perfil y la marca (500 y 332); la suite allí, 885: 827 pasan, 0 fallan, 58 saltadas. En Windows las llamadas son las mismas. P-5 en vivo (sin ventana): bucle de 87.5 fps (gs1) y 87.8 (gs2), con la cámara a 88.5; sd z 0.074 mm (gs1) y 0.040 (gs2); pose en el 99.7 y el 99.5 % de los frames; marca cruzada y código 3 bien; en el PC, 67.6 Hz en Slicer. La sd z de gs1 por V4L2 duplica la de MSMF (B77).

- **Meta 007, fase 5b · El ruido de gs1 por V4L2 (B77)** (hecha el 2026-11-03 con la parte A; el autor decidió no correr el P-5b, P26): `diagnostics/ruido_pose.py` analiza sin cámara las grabaciones `--record` y `linux/perfil_temporal.py` hace perfiles temporales con una clave cambiada. Sobre las tres grabaciones del P-5, la sd z de gs1 (0.074 mm) es casi toda lenta (deriva monótona de −3.9 µm/s; sin ella, 0.029 mm), no del filtro ni de dos valores: apunta a calor, mecánica o luz. B77 queda abierta con prioridad baja; el P-5b (`Claude outputs/fases/007/p5b.md`) se corre solo si la deriva afecta de verdad.

- **Meta 007, fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes** (hecha el 2026-11-04 con el P-6 del autor): `tracker --igtl-iface <interfaz>` (Linux) liga el 18944 a la IPv4 de esa interfaz y aborta con código 2 si cae a loopback; sin la opción, 127.0.0.1 como siempre. El servidor pone `TCP_NODELAY` en cada socket aceptado (sin él, Nagle daba 20 Hz por la LAN). `diagnostics/clock_offset.py` mide el desfase de reloj Jetson − PC por un eco UDP (puerto 18960) y `igtl_rate listen --clock-offset-ms` lo usa. Con el tracker en la Jetson, Slicer en el PC recibe 84.0 Hz por la LAN (latencia añadida p95 7.62 ms) y 82.0 por Tailscale (2.06 ms), sobre el techo de ~65 Hz del tracker en el PC (65.7; B54). El cable directo no se probó (P27, B85); el ahorro de energía de la Wi-Fi de la Jetson hay que apagarlo a mano tras cada reinicio (B86). Suite del PC 977: 967 pasan, 10 saltadas. B68 (el 18944 sin autenticación en la red) anotada.

- **Meta 007, fase 7 · Las dos cámaras a la vez en la Jetson** (hecha el 2026-11-04 con el P-7 del autor, sin condición B, P28): `diagnostics/tegrastats_log.py` resume el log de `medir tegrastats` (CPU por núcleo, RAM, temperatura) en una ventana por la hora. gs2 corre con un perfil temporal en el 18946 (`linux.perfil_temporal --puerto 18946`, P18). Con las dos a la vez (450 s, Ollama parado): la cámara da 86.2 fps cada una (sola, 88.5) y el bucle 63.2 (cumple P13, ≥ 45), listeners 63.2 msg/s, latencia p95 10.3 ms; la CPU va al 95.5 % con la GPU al 0 %, RAM máx 3074 de 7620 MB, 69.9 °C: caben en el USB, pero sin margen de CPU para la meta 006 (B91). Ollama deshabilitado. La cadena no cambia. El P-7w del PC pasa a la fase 7b · Las dos cámaras a la vez en Windows.

- **Meta 007, fase 7b · Las dos cámaras a la vez en Windows** (en marcha; autorizada el 2026-11-04, tres partes con su commit cada una). **Parte A · El diagnóstico (`244d31e`):** `camera/dshow_props.py` lee los 10 controles por COM sobre el filtro de captura de DirectShow, sin abrir vídeo; `probe_camera` gana `--capa cv2|com` y `--comparar-capas`; `igtl_rate listen --idle-s` (cierra B79). P-7b-A en vivo: COM y cv2 leen lo mismo (0 diferencias de 10, por cámara) y COM lee en 0.2 s con la otra cámara transmitiendo; la apertura corta por cv2/DSHOW de una cámara no abre con la otra transmitiendo por MSMF, ni a 640x480 (entonces se leyó «no es el ancho de banda»; desde el P-7b5, probablemente la misma causa que B5, sin medir); decisión: J7 (COM). **Parte B · El arreglo (`ba3ed36`; P-7b-B del autor el 2026-11-04 y P-7b5 el 2026-11-05):** B1–B3 cumplen; B4, gs1 sola con Slicer, 82.2 fps de cámara y 81.7 de bucle, faltan los Hz de Slicer; B5 no cumplía con las dos en el Genesys (`0x800718CF`) y cumple con gs2 en `USB(5)`, ~89–90 fps cada una (§4.21; el perfil de gs2 cambió de ruta). Lo hecho sin cámara: `CapaWindowsCOM.aplicar` escribe por COM y relee; `capa_para_plataforma("win32")` da `CapaWindowsCOM`, así que el tracker lee la marca y aplica los ajustes sin abrir vídeo y sin la apertura corta que fallaba; `linux.perfil_temporal` gana `camera.usb_port_windows` (y se arregló su regex para valores con `#`); `probe_camera --fijar --capa com`. La cadena (índice MSMF, modo, calibración, detección, filtro, envío) no cambia: replay 0.0 mm / 0.0° / 0.0 px. Suite del PC 1071: 1061 pasan, 10 saltadas, 0 fallan. Falta la parte C (el P-7w largo). B92 (fps que varían) y B93 (`CapaWindowsDShow` solo para la sonda) anotadas.

- **Meta 006, fase 7 · Los extrínsecos por tablero, independientes de Marker0** (parcial, 2026-11-09; adelantada por P36): `python -m calibration.calibrate_extrinsics --desde-vistas …` (sin cámara, fuera de la cadena) calcula `T_gs1←gs2` con el tablero 8×5 de 24.86 mm, mide el control cruzado y la distancia triangulada (200.43 mm, no los 198.88 del plan) y repite el criterio 1 de Marker0 con ellos. Sintético: ΔT 9.5e-06 mm, ΔR 1.4e-06°. Falta lo en vivo: ya no con `fase-7/correr.ps1` (los dos trackers por turnos, cortado en T04 el 2026-11-10) sino con `fase-7/asistente/correr.ps1` y el asistente de la fase 7a; sin él no hay `data/extrinsecos_gs1_gs2_pinzas.yml` ni veredicto de B94. B104 y B105 anotadas.
- **Meta 006, fase 7c2 · `Reference` y `ReferenceToTracker`** (hecha sin cámara el 2026-11-11; pendiente del commit; falta la sesión en vivo con Slicer, que verifica también la 7c): el marker se llama `Reference` en `markers.list` y la cadena publica `ReferenceToTracker` (P57); `profiles.reference_marker` exige una sola referencia (`Reference` o, en las copias congeladas, `Marker0`); el script de Slicer es `codigo/slicer/receive_reference.py` (`en_raiz`, `legacy_present`); `tests/test_nombre_referencia.py` impide que un archivo vivo vuelva a nombrar `Marker0ToTracker`. Las grabaciones viejas se leen con el alias `Marker0`. `pose_log.summarize` ya no tiene nombre por defecto. **Los perfiles siguen con ID 0 y 80 mm** hasta las 5 medidas del autor. Suite 1333 pasan, 10 saltadas, 0 fallan (335.6 y 268.8 s); replay 8/8 en 0.0; `fusion.experiment` y las matrices del bucle, iguales byte a byte; `git diff` de la cadena, 6 líneas de texto. B124, B125 y B128 anotadas.
- **Meta 006, fase 7c · La referencia con su propio ID** (hecha sin cámara el 2026-11-11; commit `80e21a9`; lo en vivo es la sesión de la 7c2): `python -m diagnostics.marker_image` genera el marker de ID 100 de ~100 mm (SVG, PNG y STL bicolor para la Bambu Lab A1; el autor lo imprime y lo mide con calibrador); `profiles.load` valida `markers.list` con `check_markers` (nombre e ID únicos, `size_mm` > 0); las pruebas de las grabaciones leen copias congeladas de los perfiles (`tests/data/marker0_gs1_perfil.yaml`, `_gs2_`: ID 0, 80 mm) y los sintéticos siguen al perfil del repo. **Los perfiles gs1/gs2 siguen con ID 0 y 80 mm hasta que el autor dé las 5 medidas del marker impreso;** hasta cerrar la 7c2 ninguna sesión con Marker0 vale (B55). Suite 1303 pasan, 10 saltadas, 0 fallan (286.9 y 346.3 s); replay 8/8 en 0.0; la cadena sin tocar. B39 ampliada y B127 anotadas.
- **Meta 006, fase 7a · El asistente de captura del tablero** (hecha sin cámara el 2026-11-10; commit `238117e`): `python -m calibration.capture_stereo_board` abre gs1 y gs2 en un proceso, enseña una ventana con las dos vistas y captura sola cada vista quieta (1 s, `QUIETO_PX` 0.5) y distinta (≥ 10° o ≥ 40 mm), en el formato de `calibrate_extrinsics --desde-vistas`. Sin cámara: vista previa de las dos cámaras p95 ~30 ms, `comprobar_rafaga` p95 1.2 s, 32 pruebas; suite 1189 pasan (182.8 y 201.6 s). La prueba de 20 poses da ΔT 0.294 mm / ΔR 0.0213° (con esquinas exactas, 0.0) y el asistente da lo mismo que escribir las vistas a mano. Sin cámara no se ha probado: las dos cámaras en un proceso, sus fps y los Hz de la ventana. B114 y B115 anotadas. La cadena no se toca.
- **Meta 006, fase 2 · S2 otra vez en Windows, y B94** (hecha el 2026-11-09): la parte sin cámara en `codigo/fusion/` (el segmento `S2_pos1_fin`, `half_split`, `repeat_check`, el veredicto de B94, `--tolerancia-ancla-ms` y `python -m fusion.extrinsics guardar`, `be78d55`), sin tocar la cadena; y la grabación de S2 en el PC con las dos cámaras (6 tramos de 40 s, pose 99.9–100 %). Veredicto de B94: «se movió» (pos1 frente a pos1_fin 0.703 mm / 0.151°; mitades de S2_pos2 0.952 mm, de la ambigüedad de IPPE en gs2). El ajuste conjunto de las 5 posiciones ya cabe en dos cámaras rígidas (0.298 px; Jetson 5.58), pero el criterio 1 da 4.198 mm / 6.087° (Jetson 19.5 / 5.82): B94 sigue abierta, alta. Por P36 se adelanta la Fase 7 (el tablero). B100, B101 y B102 anotadas.
- **Meta 006, fase 1 parte A · Los números sin gtsam** (hecha el 2026-11-05, `a1a714b`): `codigo/fusion/` (`python -m fusion.experiment`) corre fuera de línea, sin cámara ni gtsam y sin tocar la cadena, sobre la grabación de las dos cámaras en la Jetson. Fusionar baja el jitter 31.9 % (pose) y 63.1 % (PnP conjunto), pero los extrínsecos por Marker0 no coinciden entre gs1 y gs2 (19.5 mm / 5.82°; B94, alta). Falta la parte B (GTSAM).

### En pausa (se conserva, se puede retomar)

- **Femto *depth* / nube de puntos / registro por superficie** (`femto_pruebas/`): 1.76 mm, con brazo de palanca del Marker0 (ADR-013) y ambigüedad en la columna repetitiva; plan: banco rígido con cubo distintivo (`stl/BaseMarcador/`).

### WIP / deuda técnica pendiente

- **Runbooks:** `documentos/historico/MANUAL_simplificado.md` (archivado el 2026-10-23) es del contexto doctor y del dodecaedro; se rehacen con el rumbo nuevo (su §4.2 espera la prueba en Slicer, B10).
- **Panel** (`python -m gui.panel`; brief-01/02, verificado 2026-08-13 con la Femto y desde la meta 003 con gs1 y gs2; detalle en el historial de git de este archivo, antes de `cd77185`): el asistente del dodecaedro y el dock se archivaron en la fase 3 de la meta 003, así que su verificación en vivo (B10) espera al instrumento nuevo (B40).
- **Detección ~3–4 markers/vista** (histórico 5–6): revisar distancia, ángulo y luz antes que el detector.
- **La referencia (Marker0 en ADR-013) rígida y corta**; **stylus impreso nuevo** (IDs 181–191, sin pose robusta, no urgente); **depth en el BA** cuando se resuelva el bias (ADR-008).

## 7. Preferencias de comunicación

- **Español.** Directo y honesto, incluido sobre incertidumbre. Sin exceso de
  disculpas: foco en diagnóstico y fix. Cuestionar supuestos si los datos lo piden.
- El doctor a veces retoma a mitad de tarea → leer los archivos recientes y los
  MVD para reconstruir el estado antes de asumir.
