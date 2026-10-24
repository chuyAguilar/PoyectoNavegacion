# CONTEXT.md — Reglas, Límites y Estado

> **Qué es este documento (MVD 3 de 3):** las **reglas y el estado**. Reglas de
> negocio, límites de seguridad/privacidad, entorno y máquinas, qué está hecho vs
> WIP, y las **restricciones no negociables** que cualquiera —humano o IA— debe
> respetar al tocar este proyecto. Documento **vivo**: se lee ANTES de trabajar y
> se actualiza al cerrar cada iteración.
>
> El *qué* está en `ARCHITECTURE.md`; el *porqué* en `DECISIONS.md`.
> _Última actualización: 2026-10-23 (§6: meta 003, fase 2 · la cadena solo con Marker0; manual del dodecaedro archivado). Antes, 2026-10-23 (§6: meta 002, fase 5, cámara 2 calibrada desde el panel). Antes, 2026-10-22 (§6: meta 002, fase 4, cámara 1 calibrada y escala comprobada). Antes, 2026-10-22 (§6: meta 002, fase 3, resolución y exposición elegidas). Antes, 2026-10-22 (§4: trampas 18 y 19, la aceleración HW de MSMF y la marca `focus` sin escribir; §6: meta 002, cámaras SVPRO). Antes, 2026-10-19 (§6: suite y respaldo de la punta; §3 y §6: rutas viejas corregidas)._

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
- **Código activo:** `codigo\iter4\`. Entorno virtual: `codigo\.venv\`
  (**Python 3.11.9**, fijado en `.python-version`).
- **Stack de software:**
  - Python 3.11.9 + **OpenCV 4.11/4.13** (`opencv-contrib-python`) + scipy +
    numpy + PyYAML + **pyigtl** + **pyorbbecsdk2** (NO el viejo `pyorbbecsdk`
    1.3.2, roto en Windows).
  - **3D Slicer 5.x** + extensión **SlicerIGT** (visualización, Fiducial
    Registration Wizard, Volume Reslice Driver). Corre aparte; no se controla
    directo, se le pasan scripts para su consola Python.
  - `open3d` 0.18 en el venv (usado por `femto_pruebas/`, hoy en pausa).
  - **PySide6 6.11.1** instalado en el venv (GUI del panel, brief-01; en
    `requirements.txt` como `pyside6>=6.7,<7`).
- **Dos cámaras, dos contextos (ambas activas):** Femto Bolt (RGB) = contexto
  principal (`tracker_config.yaml`, Marker0 80 mm); webcam **global shutter** =
  contexto "doctor" (`data/historico/tracker_config_doctor.yaml` + `data/historico/globalshutter.yml`,
  `source: 1`, Marker0 60 mm). La geometría del dodecaedro v2 es
  cámara-independiente → se comparte entre ambos contextos.
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
    `import camaras_uvc` antes de `import cv2` (los scripts que abren MSMF) y
    el panel se la pasa a sus procesos (`procesos.entorno_hijo`). **`tracker.py`
    a mano desde PowerShell no la apaga** (B28): `$env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS='0'`
    antes de lanzarlo.
19. **La marca `focus` de una cámara solo es fiable si se escribió.** La cámara 2
    nunca la tenía escrita y por DSHOW leía 332, 268, 362, 254, 337…, así que el
    backend paraba («no es la del perfil») sin motivo. Al dar de alta un perfil:
    `sondear_camara.py --fijar "focus=N" --forzar --puerto <ruta>` (`--forzar`
    escribe aunque la lectura ya diga N; sin él `aplicar` no escribe lo que ya
    coincide). Después la marca persiste tras desenchufar.

## 5. Metodología de trabajo (cómo colaboramos humano + IA)

Adoptada 2026-08-13. Cualquier IA que toque el repo la respeta.

> **2026-10-19:** se monta el método por specs (`docs/constitution.md`,
> `CLAUDE.md`, `memory.md`, `specs/`). Donde choque con lo de abajo, mandan la
> constitución y `CLAUDE.md`; en particular, ningún agente hace commit ni push:
> los hace el autor.

- **Leer los 3 MVD (`ARCHITECTURE.md`, `DECISIONS.md`, `CONTEXT.md`) ANTES de
  tocar código.** Son la fuente de verdad.
- **Roles:** el doctor + orquestador (Cowork) planean y escriben un `brief.md`
  acotado → el implementador (Claude Code, con acceso al repo) lee el brief + los
  3 MVD y devuelve un **PLAN sin ejecutar** → se aprueba → implementa → el
  orquestador valida (lee el código, corre tests/build) → Claude Code hace commit,
  **actualiza los MVD** y hace push. El doctor es el puente.
- **Principios:** sondear el terreno real antes de codificar (probar
  API/dispositivo/entorno, no suponer); fallar fuerte, no en silencio; revisión
  adversarial del código nuevo; **verificar empíricamente antes de declarar
  "hecho"**; cambios pequeños en iteraciones numeradas con criterio de aceptación;
  memoria para no perder el hilo entre sesiones.
- **Al terminar una iteración, actualizar los MVD** (y `CLAUDE.md` si cambian
  rutas/estado). Un MVD desactualizado es peor que no tenerlo.

## 6. Estado del proyecto (hecho / en pausa / WIP)

### Hecho y validado

- Pipeline de tracking (`tracker.py`) con backend `webcam | femtobolt`, detector
  ArUco tuneado, filtro `z<0`, filtro 1-Euro.
- Geometría del dodecaedro **v2 compartido** (IDs 3–13) calibrada por BA, validada
  a 1.26 px.
- Calibración de la punta por **dock** (`StylusTipToDodecaedro_femto_dock`,
  dodecaedro v2, spread ~1.8 mm); copia versionada en
  `iter4/data/respaldo_puntas/` desde 2026-10-19 (ADR-021, `ARCHITECTURE.md` §3.4).
- Jerarquía de transforms en Slicer + registro **paired-point** (RMS 2.80–3.46 mm
  histórico) y navegación tomográfica (iter 3, los cortes del CT siguen al stylus).
- Suite pytest sin cámara (2026-10-19, meta 001): `py_compile`, selftest del panel
  y replay de la pose contra una referencia guardada (`docs/ARCHITECTURE.md` §6).

### Vía activa

- **Rumbo (2026-10-20):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen. Solo valen los perfiles nuevos `tracker_config_gs1.yaml` y `tracker_config_gs2.yaml` (dos SVPRO AR0234 global shutter). Los contextos viejos (Femto `tracker_config.yaml`, «doctor» `tracker_config_doctor.yaml` + `globalshutter.yml`, archivados en `iter4/data/historico/` el 2026-10-23; ADR-014/015/016) quedan como referencia.

### En curso: meta 002 · calibración de las cámaras global shutter SVPRO

- **Hecho (fases 1–6, 2026-10-21/23; números en `specs/002-calibracion-camaras/resultados.md`):** identidad de cada cámara por la ruta de su puerto USB y marca `focus` (`camaras_uvc.py`); ajustes por DSHOW (`ajustes_camara.py`); el código apaga la aceleración HW de MSMF; 1280×960 MJPG 90 fps y 0.977 ms en las dos; las dos calibradas con el tablero impreso (24.86 mm, detector `sb`): cámara 1 RMS 0.167 / control 0.146 px, cámara 2 0.154 / 0.150 px, cobertura 1.00; escala por medias +0.27 y −0.37 mm en 80 mm. Pose del dodecaedro quieto 99.8 % con la K real. Calibración del panel: ventana de tres pasos (enfocar, tablero, escala). **No girar ni sacar el lente de la cámara 2 sin recalibrar** (cy 389.8, B36). Con ventana el tracking da 19–25 fps (B32).
- **Fase 6 (2026-10-23):** cadena bien con las dos cámaras; sd z cámara 2 1.08–1.15 mm (cumple, < 1.38), cámara 1 3.75–4.88 mm (no): la pose salta 11–25 mm al entrar o salir un marker de lado (B37, alta). Perfiles viejos archivados.
- **Falta:** cerrar la meta (pruebas, ADR-023, ADR-024, el del rumbo); luego optimizar el tracker (B37 primero).

### En pausa (se conserva, se puede retomar)

- **Femto *depth* / nube de puntos / registro por superficie** (`femto_pruebas/`): 1.76 mm, con brazo de palanca del Marker0 (ADR-013) y ambigüedad en la columna repetitiva; plan: banco rígido con cubo distintivo (`stl/BaseMarcador/`).

### WIP / deuda técnica pendiente

- **Meta 003 · Arquitectura y optimización del tracker** (en curso; `specs/003-arquitectura-tracker/`): fase 1 hecha (2026-10-23), línea base de Marker0 quieto con gs1 y gs2: 100 % con pose, sd z 0.04 mm, fps bimodales 20–35 (`resultados.md`); el tracker acepta `--record`, `--no-window`, `--save-frames`, `--frames-every` y `--duration` (apagadas). **Fase 2 hecha (2026-10-23):** los perfiles gs1 y gs2 ya no definen `rigid_bodies`, así que la cadena publica solo `Marker0ToTracker` (ADR-026, principio 6); en vivo, 19.1 Hz (gs1) y 31.4 Hz (gs2) en Slicer, `DodecaedroToTracker` ausente, salida limpia. `codigo/slicer/receive_marker0.py` mide la cadena desde Slicer. Faltan: archivar el dodecaedro (fase 3) y pasar `medir_modos.py --modos` a Marker0 (fase 4).
- **Runbooks:** `documentos/historico/MANUAL_simplificado.md` (archivado el 2026-10-23) es del contexto doctor y del dodecaedro; se rehacen con el rumbo nuevo (su §4.2 espera la prueba en Slicer, B10).
- **Panel** (brief-01/02, verificado 2026-08-13 con la Femto; detalle en el historial de git de este archivo, antes de `cd77185`): queda en vivo la captura del asistente con IDs nuevos y el dock (B10).
- **Detección ~3–4 markers/vista** (histórico 5–6): revisar distancia, ángulo y luz antes que el detector.
- **Marker0 rígido y corto** (ADR-013); **stylus impreso nuevo** (IDs 181–191, sin pose robusta, no urgente); **depth en el BA** cuando se resuelva el bias (ADR-008).

## 7. Preferencias de comunicación

- **Español.** Directo y honesto, incluido sobre incertidumbre. Sin exceso de
  disculpas: foco en diagnóstico y fix. Cuestionar supuestos si los datos lo piden.
- El doctor a veces retoma a mitad de tarea → leer los archivos recientes y los
  MVD para reconstruir el estado antes de asumir.
