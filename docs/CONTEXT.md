# CONTEXT.md — Reglas, Límites y Estado

> **Qué es este documento (MVD 3 de 3):** las **reglas y el estado**. Reglas de
> negocio, límites de seguridad/privacidad, entorno y máquinas, qué está hecho vs
> WIP, y las **restricciones no negociables** que cualquiera —humano o IA— debe
> respetar al tocar este proyecto. Documento **vivo**: se lee ANTES de trabajar y
> se actualiza al cerrar cada iteración.
>
> El *qué* está en `ARCHITECTURE.md`; el *porqué* en `DECISIONS.md`.
> _Última actualización: 2026-10-29 (§6: la meta 007 · El tracker en la Jetson Orin Nano entra en la vía activa, fase 1). Antes, 2026-10-28 (§5: meta 005 · Agente de consulta para el equipo y buzón de peticiones, fase 1 · El buzón `peticiones/` y los hooks: los compañeros envían peticiones nuevas, ADR-034). Antes, 2026-10-26 (§6: meta 004 · Cómo funciona el tracker, fase 4 · Lectura con el autor y cierre de la meta: la meta pasa a «Hecho»; la suite, 618 pruebas). Antes, 2026-10-25 (§6: meta 003 · Arquitectura y optimización del tracker, fase 8c · Cierre de la meta: la meta pasa a «Hecho», con los números en vivo de las fases 7, 7b, 8a y 8b). Antes, 2026-10-25 (§6: meta 003, fase 8a · Un botón por modo en el panel, hecha sin cámara). Antes, 2026-10-25 (§3, §4.5, §4.20 y §6: meta 003, fase 7 · Subir los fps con ventana, cerrada; el tracker espera a Slicer con tope y aborta, los perfiles siguen a 90 fps y el tracking va con la caja al máximo). Las actualizaciones anteriores, en el historial de git._

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
  `codigo\data\intrinsecos_gs{1,2}_1280x960.yml`). Solo Marker0, de 80 mm. La Femto
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

## 5. Metodología de trabajo (cómo colaboramos humano + IA)

Desde el 2026-10-19, el método por specs: `docs/constitution.md` (lo que no se negocia), `CLAUDE.md` (cómo se trabaja), `memory.md` y `specs/` (ADR-020). Ningún agente hace commit ni push; los hace el autor. El método anterior de briefs (adoptado el 2026-08-13) queda en el historial de git de este archivo.

Desde el 2026-10-28 (ADR-034, meta 005 · Agente de consulta para el equipo y buzón de peticiones), los compañeros del equipo también hacen commit y push, pero solo de archivos nuevos en `peticiones/`: una petición por archivo, escrita por el agente `consulta` y enviada por el compañero con los cinco comandos de `peticiones/README.md` («Cómo se envía»). En sus máquinas la filtran los hooks `pre-commit` y `pre-push` de `equipo/hooks/` (`git config core.hooksPath equipo/hooks`); el autor decide cada petición desde `direccion`. Siguen sin hacer commit ni push los agentes, `consulta` incluido.

## 6. Estado del proyecto (hecho / en pausa / WIP)

### Hecho y validado

- **Tracking de Marker0** (`python -m tracker`, meta 003): `camera` (dos SVPRO global
  shutter por puerto USB y marca, aceleración HW de MSMF apagada) → `vision` (ArUco con
  lista blanca, IPPE_SQUARE con z > 0, 1-Euro de la posición) → `transport`
  (`Marker0ToTracker` por OpenIGTLink, 18944) → Slicer. Línea base (fase 1, Marker0
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

- **Meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC** (`specs/007-jetson/`, desde el 2026-10-29): la fase 1 · El escaneo de la Jetson, solo lectura (`codigo\linux\`), hecha el 2026-10-29 con el escaneo del autor; sigue la fase 2. Ningún agente se conecta a la Jetson hasta la fase 2 · La barrera de seguridad para los agentes.

### En pausa (se conserva, se puede retomar)

- **Femto *depth* / nube de puntos / registro por superficie** (`femto_pruebas/`): 1.76 mm, con brazo de palanca del Marker0 (ADR-013) y ambigüedad en la columna repetitiva; plan: banco rígido con cubo distintivo (`stl/BaseMarcador/`).

### WIP / deuda técnica pendiente

- **Runbooks:** `documentos/historico/MANUAL_simplificado.md` (archivado el 2026-10-23) es del contexto doctor y del dodecaedro; se rehacen con el rumbo nuevo (su §4.2 espera la prueba en Slicer, B10).
- **Panel** (`python -m gui.panel`; brief-01/02, verificado 2026-08-13 con la Femto y desde la meta 003 con gs1 y gs2; detalle en el historial de git de este archivo, antes de `cd77185`): el asistente del dodecaedro y el dock se archivaron en la fase 3 de la meta 003, así que su verificación en vivo (B10) espera al instrumento nuevo (B40).
- **Detección ~3–4 markers/vista** (histórico 5–6): revisar distancia, ángulo y luz antes que el detector.
- **Marker0 rígido y corto** (ADR-013); **stylus impreso nuevo** (IDs 181–191, sin pose robusta, no urgente); **depth en el BA** cuando se resuelva el bias (ADR-008).

## 7. Preferencias de comunicación

- **Español.** Directo y honesto, incluido sobre incertidumbre. Sin exceso de
  disculpas: foco en diagnóstico y fix. Cuestionar supuestos si los datos lo piden.
- El doctor a veces retoma a mitad de tarea → leer los archivos recientes y los
  MVD para reconstruir el estado antes de asumir.
