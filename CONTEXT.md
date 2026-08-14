# CONTEXT.md — Reglas, Límites y Estado

> **Qué es este documento (MVD 3 de 3):** las **reglas y el estado**. Reglas de
> negocio, límites de seguridad/privacidad, entorno y máquinas, qué está hecho vs
> WIP, y las **restricciones no negociables** que cualquiera —humano o IA— debe
> respetar al tocar este proyecto. Documento **vivo**: se lee ANTES de trabajar y
> se actualiza al cerrar cada iteración.
>
> El *qué* está en `ARCHITECTURE.md`; el *porqué* en `DECISIONS.md`.
> _Última actualización: 2026-08-13._

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
  paciente. El DICOM y datos identificables **no se suben a repos** ni salen del
  entorno local sin necesidad. `.gitignore` debe excluir DICOM/volúmenes. Tratar
  cualquier dato clínico con cuidado; ante duda, no exponerlo.
- **Fallar fuerte, no en silencio.** Un sistema que se niega a arrancar y dice por
  qué es mejor que uno que hace lo incorrecto callado. Los scripts deben validar
  sus entradas (geometría, config, calibración presente y coherente) y abortar con
  mensaje claro si algo falta o no cuadra, en vez de producir un resultado
  plausible pero falso.

## 3. Entorno y máquinas

- **Máquina principal:** `BigDaddy` (Windows 10/11). GPU **RTX 3060** (suficiente
  para inferencia si se retoma deep learning). Todos los comandos de shell se
  corren desde **PowerShell**.
- **Raíz del proyecto:** `C:\Dev\Dr.Milton\PoyectoNavegacion` (antes
  `C:\Dev\PoyectoNavegacion` — rutas viejas en docs por corregir).
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
  contexto "doctor" (`tracker_config_doctor.yaml` + `data/globalshutter.yml`,
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

## 5. Metodología de trabajo (cómo colaboramos humano + IA)

Adoptada 2026-08-13. Cualquier IA que toque el repo la respeta.

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
  dodecaedro v2, spread ~1.8 mm).
- Jerarquía de transforms en Slicer + registro **paired-point** (RMS 2.80–3.46 mm
  histórico) y navegación tomográfica (iter 3, los cortes del CT siguen al stylus).

### Vía activa

- **Registro paired-point.** Contexto principal: **Femto Bolt (RGB)**,
  `tracker_config.yaml`, Marker0 80 mm (ADR-014/015). Contexto "doctor": **webcam
  global shutter**, `tracker_config_doctor.yaml` + `data/globalshutter.yml`,
  Marker0 60 mm (ADR-016). Ambos comparten la geometría del dodecaedro v2.

### En pausa (se conserva, se puede retomar)

- **Femto *depth* / nube de puntos / registro por superficie** (`femto_pruebas/`).
  Validado a 1.76 mm pero con dos problemas abiertos: brazo de palanca del Marker0
  (ADR-013) y ambigüedad de deslizamiento en la columna repetitiva. Plan guardado:
  banco rígido con cubo de puntos distintivo (`stl/BaseMarcador/`).

### WIP / deuda técnica pendiente

- **`MANUAL_simplificado.md`** es el runbook del **contexto doctor** (webcam
  global shutter) — correcto para ese contexto. Pendientes menores: su encabezado
  tiene la ruta vieja `C:\dev\PoyectoNavegacion\codigo` (corregir a
  `C:\Dev\Dr.Milton\PoyectoNavegacion\codigo`), y falta un runbook equivalente
  para el contexto Femto (`tracker_config.yaml`) si se quiere.
- **`CLAUDE.md`** actualizado 2026-08-13 (rutas nuevas, estado al día, apunta a
  los 3 MVD).
- **Smoke test del entorno:** Parte 1 (sanidad del `.venv` + imports, incl.
  `pyorbbecsdk`) **verificada OK 2026-08-13**. Parte 2 (tracker en vivo +
  detección de IDs 3–13) pendiente, se hará al conectar la cámara para operar.
- **GUI / panel de control** (brief-01, iter 1): **VERIFICADO EN VIVO
  2026-08-13** con la Femto real (`codigo/iter4/gui/`): panel y 7 semáforos,
  probar cámara, verificar IDs (3–13), tracker → OpenIGTLink → Slicer con
  cierre limpio, **Detener del panel** (con ventana → 'q'; sin ventana →
  terminate), y el **asistente "dodecaedro nuevo"** encadenando captura → BA
  con fail-loud. **Único residual:** calibración de punta por dock en vivo
  (falta la placa física). Nota: el BA no convergió sobre una captura corta de
  60 s (cobertura floja) — tema de DATOS, no del panel.
- **GUI / panel de control (brief-02, iter 2): 5 mejoras implementadas y
  verificadas headless 2026-08-13.** M1 semilla default v2 + IDs visibles; M2
  alta de dodecaedro con IDs NUEVOS (generar teórica desde inputs → captura →
  BA, `corregir_giro_esquinas.py` documentado como escape); M3 intrínsecos
  desde el panel (`iter4/calibrar_camara.py` nuevo + apuntar el perfil con
  edición quirúrgica y backup, ADR-018); M4 grupo Calibrar limpio (los botones
  sueltos de captura/BA fuera — un BA sobre un dataset viejo queda SOLO por
  CLI); M5 cobertura pre-BA + monitor de estancamiento con auto-corte
  (umbrales calibrados con datos reales: antípodas in-co-visibles, pares
  débiles). **Pendiente de verificación con cámara en vivo:** captura del
  asistente con IDs nuevos y `calibrar_camara.py` interactivo (+ el residual
  del dock de brief-01).
- **FPS ~16–17 con Femto RGB en el tracker** (observado en vivo 2026-08-13):
  esperado — el backend habilita depth+align del SDK aunque solo se use el RGB.
  Optimización pendiente (p.ej. no habilitar el stream de depth en este modo).
- **Detección ~3–4 markers/vista en la sesión 2026-08-13** (referencia
  histórica: 5–6): revisar distancia (50–70 cm), ángulo y luz antes de tocar
  parámetros del detector.
- **Marker0 rígido y corto**: montaje pendiente para eliminar el brazo de palanca
  (ADR-013), relevante también para el paired-point.
- **Stylus impreso nuevo** (IDs 181–191): geometría CAD buena, pero falta pose
  robusta con rechazo de outliers y `marker_mm 15.7`; su BA se atora. No urgente.
- **Reintegrar el *depth* al BA** cuando se resuelva el bias residual fuera de la
  caja (ADR-008).

## 7. Preferencias de comunicación

- **Español.** Directo y honesto, incluido sobre incertidumbre. Sin exceso de
  disculpas: foco en diagnóstico y fix. Cuestionar supuestos si los datos lo piden.
- El doctor a veces retoma a mitad de tarea → leer los archivos recientes y los
  MVD para reconstruir el estado antes de asumir.
