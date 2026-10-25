# CONTEXT.md — Reglas, Límites y Estado

> **Qué es este documento (MVD 3 de 3):** las **reglas y el estado**. Reglas de
> negocio, límites de seguridad/privacidad, entorno y máquinas, qué está hecho vs
> WIP, y las **restricciones no negociables** que cualquiera —humano o IA— debe
> respetar al tocar este proyecto. Documento **vivo**: se lee ANTES de trabajar y
> se actualiza al cerrar cada iteración.
>
> El *qué* está en `ARCHITECTURE.md`; el *porqué* en `DECISIONS.md`.
> _Última actualización: 2026-10-24 (§6: meta 003, fase 6 · Dónde se va el tiempo por frame, con la tabla en vivo; la suite, 475). Antes, 2026-10-24 (§3, §4 y §6: meta 003, fase 5 · Documentación del paso 1). Las actualizaciones anteriores, en el historial de git._

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
  puerto USB y la marca `focus`; 1280×960 MJPG 90 fps; intrínsecos en
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
5. **`pyigtl` bloquea el tracker si Slicer no está conectado.** Conectar Slicer
   (OpenIGTLink IF activo) **ANTES** de arrancar el tracker.
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

## 5. Metodología de trabajo (cómo colaboramos humano + IA)

Desde el 2026-10-19, el método por specs: `docs/constitution.md` (lo que no se negocia), `CLAUDE.md` (cómo se trabaja), `memory.md` y `specs/` (ADR-020). Ningún agente hace commit ni push; los hace el autor. El método anterior de briefs (adoptado el 2026-08-13) queda en el historial de git de este archivo.

## 6. Estado del proyecto (hecho / en pausa / WIP)

### Hecho y validado

- **Tracking de Marker0** (`python -m tracker`, meta 003): `camera` (dos SVPRO global
  shutter por puerto USB y marca, aceleración HW de MSMF apagada) → `vision` (ArUco con
  lista blanca, IPPE_SQUARE con z > 0, 1-Euro de la posición) → `transport`
  (`Marker0ToTracker` por OpenIGTLink, 18944) → Slicer. Línea base (fase 1, Marker0
  quieto a ~37–38 cm): 100 % de frames con pose, sd z 0.043 mm (gs1) y 0.039 mm (gs2),
  orientación 0.10–0.13°. En vivo con Slicer (fase 4): 22.1 Hz (gs1) y 30.9 Hz (gs2) a
  mano; salida limpia y puerto libre.
- **Las dos cámaras calibradas** (meta 002, cerrada el 2026-10-23; números en
  `specs/002-calibracion-camaras/resultados.md`): 1280×960 MJPG 90 fps, 0.977 ms;
  cámara 1 RMS 0.167 / control 0.146 px, cámara 2 0.154 / 0.150 px (detector `sb`,
  tablero de 24.86 mm); escala por medias +0.27 y −0.37 mm en 80 mm. Calibración desde
  el panel en tres pasos (enfocar, tablero, escala). **No girar ni sacar el lente de la
  cámara 2 sin recalibrar** (cy 389.8, B36).
- **Suite pytest sin cámara** (`codigo\tests\`, 475 pruebas desde la fase 6 de la meta 003, ~18 s): niega la cámara
  real y el servidor pyigtl (B34); la comprobación de «no cambió» es la suite, el
  selftest del panel y el replay de Marker0 (`docs/ARCHITECTURE.md` §6).
- **Histórico (archivado, se puede retomar):** el dodecaedro v2 (IDs 3–13, BA a 1.26 px),
  su punta por dock (spread ~1.8 mm) y la jerarquía de Slicer con registro
  **paired-point** (RMS 2.80–3.46 mm) y navegación tomográfica (iter 3), en
  `codigo\historico\iter4\dodecahedron\` y `documentos\historico\MANUAL_simplificado.md`.

### Vía activa

- **Rumbo (2026-10-20; ADR-025):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen mejorados sobre gs1/gs2. Solo valen los perfiles `profiles\tracker_config_gs1.yaml` y `_gs2.yaml`. Los contextos viejos (Femto `tracker_config.yaml`, «doctor» `tracker_config_doctor.yaml` + `globalshutter.yml`; ADR-014/015/016) están archivados en `codigo\historico\iter4\femto\` y `old_profiles\` como referencia.

### En pausa (se conserva, se puede retomar)

- **Femto *depth* / nube de puntos / registro por superficie** (`femto_pruebas/`): 1.76 mm, con brazo de palanca del Marker0 (ADR-013) y ambigüedad en la columna repetitiva; plan: banco rígido con cubo distintivo (`stl/BaseMarcador/`).

### WIP / deuda técnica pendiente

- **Meta 003 · Arquitectura y optimización del tracker** (en curso; `specs/003-arquitectura-tracker/`, números en `resultados.md`). **Paso 1, la arquitectura (fases 1–5), hecho:** fase 1, línea base de Marker0 (sd z 0.04 mm, replay 0.0); fase 2, la cadena publica solo `Marker0ToTracker` (ADR-026; en Slicer 19.1 y 31.4 Hz); fase 3 (2026-10-23/24), el código pasa de `codigo\iter4\` a paquetes bajo `codigo\`, se lanza con `python -m` y el dodecaedro, la Femto y los perfiles viejos van a `codigo\historico\iter4\` (ADR-027); fase 4 (2026-10-24, sin cámara y en vivo), el tracker se parte en `vision\` y `transport\` y `tracker.py` queda solo con el bucle (replay 0.0 mm / 0.0°; B28 cumple a mano: la cámara abre en 0.4 s); fase 5 (2026-10-24), la documentación (§3, §4 y §6 de aquí y de `ARCHITECTURE.md`). **Paso 2, la optimización:** fase 6 · Dónde se va el tiempo por frame (2026-10-24, `tracker --timing`, en vivo): gris + detección + pose ~6.5 ms y ventana ~3.7 ms por frame; pesan el envío de `pyigtl` (9–12.5 ms: espera el tic de 15.6 ms de Windows) y, en el modo lento, la captura (32 ms); la fase 7 · Subir los fps con ventana aplica lo que elija el autor (B32).
- **Runbooks:** `documentos/historico/MANUAL_simplificado.md` (archivado el 2026-10-23) es del contexto doctor y del dodecaedro; se rehacen con el rumbo nuevo (su §4.2 espera la prueba en Slicer, B10).
- **Panel** (`python -m gui.panel`; brief-01/02, verificado 2026-08-13 con la Femto y desde la meta 003 con gs1 y gs2; detalle en el historial de git de este archivo, antes de `cd77185`): el asistente del dodecaedro y el dock se archivaron en la fase 3 de la meta 003, así que su verificación en vivo (B10) espera al instrumento nuevo (B40).
- **Detección ~3–4 markers/vista** (histórico 5–6): revisar distancia, ángulo y luz antes que el detector.
- **Marker0 rígido y corto** (ADR-013); **stylus impreso nuevo** (IDs 181–191, sin pose robusta, no urgente); **depth en el BA** cuando se resuelva el bias (ADR-008).

## 7. Preferencias de comunicación

- **Español.** Directo y honesto, incluido sobre incertidumbre. Sin exceso de
  disculpas: foco en diagnóstico y fix. Cuestionar supuestos si los datos lo piden.
- El doctor a veces retoma a mitad de tarea → leer los archivos recientes y los
  MVD para reconstruir el estado antes de asumir.
