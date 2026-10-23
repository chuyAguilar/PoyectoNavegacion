# DECISIONS.md — Registro de Decisiones (ADRs)

> **Qué es este documento (MVD 2 de 3):** el **porqué** del sistema. Cada entrada
> es un ADR (Architecture Decision Record): **contexto → decisión → consecuencias**.
> Es un documento **vivo** y **acumulativo**: la historia NO se borra. Cuando una
> decisión reemplaza a otra, la vieja se marca `Reemplazada por ADR-NNN` y se
> conserva, para no repetir errores ya pagados.
>
> Estados: `Aceptada` · `Reemplazada` · `En pausa` · `Propuesta`.
> _Última actualización: 2026-10-23._

Índice rápido:

| ADR | Título | Estado |
|---|---|---|
| 001 | Pipeline propio en OpenCV con IPPE_SQUARE (dejar Plus 2.8) | Aceptada |
| 002 | Stylus = dodecaedro multi-marcador (reducir brazo de palanca) | Aceptada |
| 003 | Bundle adjustment para la geometría del rigid body | Aceptada |
| 004 | `DodecaedroToMarker0` por Observer Python, no Transform Processor | Aceptada |
| 005 | `BoneSTL_Points` anidado bajo `BoneToMarker0` | Aceptada |
| 006 | Migrar la cámara a Orbbec Femto Bolt | Aceptada |
| 007 | Capturas de *depth* siempre fuera de la caja de luz | Aceptada |
| 008 | Bundle adjustment solo-2D (por ahora) + `jac_sparsity` conectado | Aceptada |
| 009 | Dodecaedro v2 compartido (IDs 3–13), geometría como propiedad física | Aceptada |
| 010 | Calibración de la punta por dock/divot (dejar el pivote clásico) | Aceptada |
| 011 | Ancla rotacional en el BA (fija centro, no orientación) | Aceptada |
| 012 | Registro por superficie (nube de puntos con la Femto) | En pausa |
| 013 | El desfase live es físico (brazo de palanca), no de software | Aceptada |
| 014 | Femto/nube de puntos en stand by; continuar con paired-point | Aceptada |
| 015 | Config canónica = `tracker_config.yaml` (Femto RGB, Marker0 80 mm, tip existente) | Reemplazada por ADR-025 |
| 016 | Cámara global shutter para el contexto "doctor" (webcam) | Reemplazada por ADR-023 y ADR-024 |
| 017 | Panel de control PySide6 que solo orquesta (brief-01) | Aceptada |
| 018 | La GUI puede mutar solo `camera.calibration_file` (quirúrgico) | Aceptada |
| 019 | Los datos de paciente siguen versionados; los agentes no los leen | Aceptada |
| 020 | Método de trabajo por specs, con constitución y el autor como único que commitea | Aceptada |
| 021 | La punta vigente se respalda como copia versionada fuera del glob de Slicer | Aceptada |
| 022 | Fable solo para implementar: las fases pesadas en dos tiempos | Aceptada |
| 023 | La SVPRO AR0234 es de obturador global (corrige ADR-016) | Aceptada |
| 024 | Un perfil por cámara física, identificada por su puerto USB | Aceptada |
| 025 | Se rescata solo el tracking; lo demás se rehace sobre las cámaras nuevas | Aceptada |

---

## ADR-001 — Pipeline propio en OpenCV con IPPE_SQUARE (dejar Plus 2.8)
**Fecha:** iter 1 (prototipo) · **Estado:** Aceptada

**Contexto.** El primer intento usó Plus Toolkit 2.8 y luego SciKit-SurgeryBARD
(`C:\Dev\mirai_sks\`, hoy deprecado). Plus 2.8 trae un detector ArUco viejo sin
IPPE_SQUARE → ambigüedad planar (la pose "salta" entre dos soluciones), que
corrompe la calibración del pivote. Diagnóstico: std de 11 mm entre capturas,
reproducibilidad ±15 mm.

**Decisión.** Construir el pipeline de tracking propio en **OpenCV 4.x** usando
explícitamente **IPPE_SQUARE** para la pose de marcadores planos.

**Consecuencias.** Control total del detector y la estimación de pose; se elimina
la fuente principal de ambigüedad. A cambio, se mantiene código propio en vez de
un toolkit. Base de todo lo que vino después.

---

## ADR-002 — Stylus = dodecaedro multi-marcador (reducir brazo de palanca)
**Fecha:** iter 1 · **Estado:** Aceptada

**Contexto.** El stylus original (lezna) tenía **1 marcador a ~22 cm** de la
punta. El brazo de palanca amplifica el error angular: `sin(2–3°) × 220 mm ≈
7–12 mm` de error en la punta.

**Decisión.** Rigid body **dodecaedro multi-marcador** (varias caras con ArUco),
punta-a-marcador reducida a ~9.6 cm, resolviendo la pose con los ≥3 marcadores
visibles.

**Consecuencias.** Menor sensibilidad al error angular y robustez ante oclusión
(si se pierde una cara, quedan otras). Introduce la necesidad de conocer la
geometría 3D precisa del cúmulo → motiva ADR-003. Este principio (acortar el
brazo de palanca) reaparece como diagnóstico central en ADR-013.

---

## ADR-003 — Bundle adjustment para la geometría del rigid body
**Fecha:** iter 1 (Day 3); BA de iter 4 cerrado 2026-05-19 · **Estado:** Aceptada

**Contexto.** La geometría teórica del dodecaedro asume impresión 3D y pegado
perfectos. La realidad tiene 1–3 mm de error por marcador. Con geometría teórica,
el dodecaedro estático mostraba oscilación bimodal de ~10 mm en Z.

**Decisión.** Capturar un dataset (`captura_calibracion.py`), correr **bundle
adjustment** (`calibrar_rigid_body.py`, `scipy.least_squares`) y usar SIEMPRE la
geometría **calibrada** (`reference_dodecaedro_*_calibrado.txt`), no la teórica.

**Consecuencias.** Reproyección sub-pixel (0.61 px iter 1; 0.78 px iter 4). Notas
duras aprendidas: (a) el `jac_sparsity` debe conectarse a `least_squares` o el
Jacobiano denso (~13 GB) congela la máquina; (b) el RMSE que reporta el propio BA
**no es confiable** — validar por reproyección independiente; (c) desplazamientos
de 20–30 mm en el anillo inferior pueden ser una solución válida, no un bug.

---

## ADR-004 — `DodecaedroToMarker0` por Observer Python, no Transform Processor
**Fecha:** iter 1 (Day 4) · **Estado:** Aceptada

**Contexto.** El stylus llega en frame del tracker y la anatomía en frame de
Marker0. El Fiducial Registration Wizard ignora los transforms padre al leer
coordenadas, así que hay que llevar el stylus al frame del paciente
explícitamente. El **Transform Processor** de Slicer a veces deja de actualizarse.

**Decisión.** Calcular `DodecaedroToMarker0 = Marker0ToTracker⁻¹ ·
DodecaedroToTracker` con un **Observer Python** que recomputa en cada
`TransformModifiedEvent`.

**Consecuencias.** Cadena de transforms estable y siempre fresca. El costo es
un bloque de script que debe instalarse en la consola Python de Slicer (está en
`MANUAL_simplificado.md` §4.4).

---

## ADR-005 — `BoneSTL_Points` anidado bajo `BoneToMarker0`
**Fecha:** iter 1 (Day 4) · **Estado:** Aceptada

**Contexto.** Al aplicar el registro, si solo se anida el modelo `Bone` bajo
`BoneToMarker0`, el modelo se mueve al frame del paciente pero `BoneSTL_Points`
se queda en el frame nativo del STL → desajuste visual.

**Decisión.** Tanto **`Bone`** como **`BoneSTL_Points`** heredan `BoneToMarker0`.
`BoneToMarker0` va en la raíz (mismo nivel que `Marker0ToTracker` y
`DodecaedroToTracker`); `Physical_Points` queda en la raíz sin padre.

**Consecuencias.** Coherencia visual modelo↔puntos↔paciente. Es la "jerarquía
final validada" que hizo coincidir el STL con los puntos físicos.

---

## ADR-006 — Migrar la cámara a Orbbec Femto Bolt
**Fecha:** iter 4 (2026-06) · **Estado:** Aceptada

**Contexto.** La webcam SVPRO (RGB) no da profundidad. Se quería explorar
registro por superficie (nube de puntos) para bajar el RMS y evitar el
paired-point manual.

**Decisión.** Introducir la **Femto Bolt** (ToF depth + RGB) vía `pyorbbecsdk2`
(el `pyorbbecsdk` 1.3.2 está roto en Windows). Refactor de `tracker.py` con
abstracción de backend `webcam | femtobolt`.

**Consecuencias.** Detección subió de 3–4 a 5–6 markers/pose con el detector
tuneado. La Femto no tiene D2C por hardware (alineación depth-color por software,
verificada correcta). Enfoque fijo 0.5–5 m → distancia de trabajo 50–70 cm, sin
vista cenital (esto rompe el pivote clásico → ADR-010). La rama de *depth* se
pausa en ADR-014, pero la Femto queda como cámara RGB principal (ADR-015).

---

## ADR-007 — Capturas de *depth* siempre fuera de la caja de luz
**Fecha:** iter 4 (2026-06) · **Estado:** Aceptada

**Contexto.** Dentro de la caja de luz Puluz (blanca, cerrada) el ToF lee **+57 mm**
de bias por multipath (rebotes IR); fuera lee **−10 mm**. La caja es buena para
RGB pero contamina el depth.

**Decisión.** **Todas** las capturas con profundidad se hacen **fuera** de la caja,
con cámara cenital y mesa blanca mate. El RGB puede seguir en la caja.

**Consecuencias.** Depth utilizable pero con bias residual (−10 mm) aún no
corregido → contribuye a ADR-008. Regla operativa registrada en `CONTEXT.md`.

---

## ADR-008 — Bundle adjustment solo-2D (por ahora) + `jac_sparsity` conectado
**Fecha:** iter 4 (2026-05/06) · **Estado:** Aceptada

**Contexto.** Integrar el depth al BA (residuos 3D) prometía mejor geometría, pero
el depth arrastra bias residual (ADR-007) y el `jac_sparsity` estaba desconectado
(Jacobiano denso ~13 GB → cuelgue).

**Decisión.** Conectar `jac_sparsity` a `least_squares` (`tr_solver=lsmr`) y correr
el BA con **residuos solo-2D** por ahora. Reintegrar el depth cuando el bias
residual fuera de la caja esté resuelto.

**Consecuencias.** BA converge y da geometría válida (0.78 px). El depth queda
como línea de trabajo aparte. Comando de referencia:
`calibrar_rigid_body.py --max-frames 500 --max-nfev 3000`.

---

## ADR-009 — Dodecaedro v2 compartido (IDs 3–13), geometría como propiedad física
**Fecha:** 2026-06-25/26 · **Estado:** Aceptada

**Contexto.** Se necesitaba un dodecaedro reproducible entre equipos/personas, sin
que cada quien recalibre la geometría. La geometría del cúmulo es propiedad física
del objeto, independiente de la cámara.

**Decisión.** Adoptar el **dodecaedro v2 compartido**: IDs **3–13**, lado de
marcador **14.6 mm**, geometría calibrada por BA **una vez** (por Milton, con la
Femto) y **compartida por git** (`reference_dodecaedro_v2_calibrado.txt`, validada
a 1.26 px). Quien lo use solo verifica IDs/orientación con `identificar_ids.py`.

**Consecuencias.** Reproducibilidad entre setups. Trampas registradas: el giro de
esquinas es **por-marcador** (cara TOP roll 0, laterales roll 180°); el BA exige
`--no-sparse` para este dataset; el RMSE del BA no es confiable (validar por
reproyección). Reemplaza la convención vieja de IDs 151–161 (iter 1) y la
intermedia 170–180 (iter 4 temprana), que se conservan como legacy.

---

## ADR-010 — Calibración de la punta por dock/divot (dejar el pivote clásico)
**Fecha:** 2026-06-12 (decisión) → dock v3 validado 2026-06-15 · **Estado:** Aceptada

**Contexto.** Con la cámara **lateral** de la Femto (sin vista cenital) el pivote
clásico no reproduce: el "cono" sale como péndulo plano, la esfera queda mal
condicionada (radio vagando 70–97 mm), y la punta roscada no asienta en un punto
repetible (sesiones difieren 5 mm, spread 3–6 mm). Causa de fondo: marcadores de
un solo lado → bias de profundidad dependiente de orientación que no promedia.

**Decisión.** Migrar a calibración **template/divot** estilo Brainlab/Navident:
placa con marcador de posición conocida + divots cónicos, o placa **dock** donde el
stylus se **encaja** (pose definida por geometría) y se rota el conjunto ante la
cámara (`calibrar_tip_divot.py --divot DOCK`).

**Consecuencias.** El dock neutraliza el factor humano: spread bajó a **1.04 mm**
(stylus viejo), muy por debajo de los 3–6 mm a mano. La métrica pasa a ser el
*spread* entre posturas (< 1.0 EXCELENTE, < 1.5 BUENO). El pivote clásico
(`test_pivote.py`) queda como **legacy**. Acople crítico: la calibración es del
ensamble físico exacto; no se mezcla con otra geometría de dodecaedro.

---

## ADR-011 — Ancla rotacional en el BA (fija centro, no orientación)
**Fecha:** iter 4 · **Estado:** Aceptada

**Contexto.** Anclar un marcador fijando su pose completa (centro + orientación)
metía un sesgo de inclinación que rompía el pivote.

**Decisión.** El ancla del BA fija **solo el centro** del marcador de referencia,
dejando los **3 DOF de rotación libres**.

**Consecuencias.** Se elimina el sesgo de inclinación; el std del pivote bajó de
4.5 a **1.35 mm**.

---

## ADR-012 — Registro por superficie (nube de puntos con la Femto)
**Fecha:** 2026-06-16/17 · **Estado:** En pausa (ver ADR-014)

**Contexto.** El paired-point manual daba RMS ~2.8 mm y depende de tocar bien los
puntos. Se probó reemplazarlo por **registro por superficie**: fusionar una nube
de la Femto (TSDF) y registrarla contra el STL del CT (semilla manual + ICP).

**Decisión.** Construir el pipeline en `femto_pruebas/` (captura TSDF `08` →
registro semilla `06` → inyección en Slicer). Validado a **1.76 mm** en zona
visible.

**Consecuencias / por qué se pausó.** Dos problemas de fondo aparecieron
(ADR-013): el desfase live es físico (brazo de palanca del marcador en varilla),
y la columna es **repetitiva** → ambigüedad de deslizamiento (encaja a 1.8 mm pero
puede correrse una vértebra; los métodos clásicos fallan, los papers usan deep
learning). Se propuso un banco rígido con cubo de puntos distintivo
(`stl/BaseMarcador/`) como siguiente paso. Todo esto queda **en pausa** por
ADR-014. El pipeline y su validación se conservan intactos en `femto_pruebas/`.

---

## ADR-013 — El desfase live es físico (brazo de palanca), no de software
**Fecha:** 2026-06-17 · **Estado:** Aceptada

**Contexto.** El registro daba ~1.8 mm en software (validado, inyección
verificada) pero el live se desfasaba ~45 mm. Se sospechaba del software.

**Decisión / hallazgo.** El software es correcto. El desfase es **físico**: el
Marker0 está en una varilla de ~21 cm del hueso (`BoneToMarker0` traslación
~228 mm). Con ese brazo de palanca, un giro de 12° del marcador = 45 mm de
desplazamiento del hueso. Manipular el conjunto entre pasos mueve el marcador.
**Esto rompe igual al paired-point.**

**Consecuencias.** El fix no es de código sino de montaje: **Marker0 rígido y
corto**, pegado al objeto. Es el mismo principio de ADR-002 (acortar brazos de
palanca), ahora aplicado a la referencia del paciente. Insumo directo para el
banco rígido propuesto en ADR-012.

---

## ADR-014 — Femto/nube de puntos en stand by; continuar con paired-point
**Fecha:** 2026-08-13 · **Estado:** Aceptada

**Contexto.** Tras ~2 meses de pausa, se retoma el proyecto. La rama de registro
por superficie (ADR-012) tiene problemas abiertos no triviales (ADR-013) y el
doctor no está seguro de continuar por esa vía ahora.

**Decisión.** Poner la **Femto depth / nube de puntos en stand by** y **continuar
con el registro paired-point**, que es independiente de la profundidad y está
validado (RMS 2.80–3.46 mm). El pipeline de superficie se conserva para retomarlo
después.

**Consecuencias.** Ruta clara y de menor riesgo para volver a operar. La deuda del
banco rígido (ADR-012/013) queda anotada como trabajo futuro. Se adopta la
metodología de trabajo con MVD + orquestación (ver `CONTEXT.md`).

---

## ADR-015 — Config canónica = `tracker_config.yaml` (Femto RGB, Marker0 80 mm, tip existente)
**Fecha:** 2026-08-13 · **Estado:** Reemplazada por ADR-025

**Contexto.** Con la nube de puntos en pausa (ADR-014) había que fijar la
configuración de operación para el paired-point.

**Decisión.** (a) **Femto Bolt como cámara principal**, usando **solo RGB**;
config canónica **`tracker_config.yaml`** (`camera_type: femtobolt`). (b)
**Marker0 = 80 mm**. (c) Calibración de punta = usar la **existente**
`StylusTipToDodecaedro_femto_dock` (dodecaedro v2, ~1.8 mm de spread), sin
recalibrar por ahora. El contexto "doctor" usa una cámara y config aparte
(`tracker_config_doctor.yaml`, global shutter — ver ADR-016), en paralelo.

**Consecuencias.** Config coherente para el contexto principal (femtobolt + 80 mm
+ geometría v2 + tip v2). El contexto "doctor" (webcam global shutter) convive con
éste; el `MANUAL_simplificado.md` opera ese contexto y es correcto como está. Si
más adelante se quiere sub-mm en la punta, correr un dock nuevo reabre esta
decisión.

---

## ADR-016 — Cámara global shutter para el contexto "doctor" (webcam)
**Fecha:** commit reciente en `origin/main` (fecha exacta en git log) · **Estado:** Reemplazada por ADR-023 y ADR-024

**Contexto.** El path webcam del contexto "doctor" usaba la SVPRO (AR0234), de
**rolling shutter**: cada fila se expone en un instante distinto, así que el
marcador se deforma cuando el objeto se mueve → error de pose durante el
movimiento del stylus.

**Decisión.** Adoptar una **cámara USB de global shutter** para ese contexto,
calibrada (`data/globalshutter.yml`, 640×480). `tracker_config_doctor.yaml` apunta
a ella (`source: 1`, `calibration_file: data/globalshutter.yml`, Marker0 60 mm). El
`MANUAL_simplificado.md` opera con esta config.

**Consecuencias.** Sin skew de rolling shutter en movimiento → poses más estables
con el objeto en mano. **Convive** con la Femto (ADR-015), que sigue siendo la
cámara principal del contexto BigDaddy; se usan en **contextos distintos**. La
geometría del dodecaedro v2 es cámara-independiente (propiedad física), así que se
comparte entre ambos contextos sin recalibrar.

---

## ADR-017 — Panel de control PySide6 que solo orquesta (brief-01)
**Fecha:** 2026-08-13 · **Estado:** Aceptada

**Contexto.** El pipeline eran pasos sueltos por consola, fáciles de correr en
el orden equivocado o con prerrequisitos rotos (tracker sin geometría calibrada,
punta de otro ensamble). Varios defaults de los scripts apuntan al stylus viejo
y fallan en silencio con el v2 (CONTEXT §4.13–15).

**Decisión.** Panel **PySide6** en `codigo/iter4/gui/` que **solo orquesta**:
semáforos que leen el disco, subprocesos con args siempre explícitos, candado
de un proceso a la vez, log verbose en vivo, gating duro del tracker (entorno +
config + geometría calibrada + intrínsecos + puerto), y coherencia
punta↔geometría por el sha16 del header del `.txt` de la punta. **Detener** usa
el camino nativo (`'q'` por PostMessage a la ventana OpenCV del script): la
sonda empírica demostró que `CTRL_BREAK` mata duro SIN correr el `finally`
(cámara/servidor quedarían tomados), así que la escalada es `'q'` →
`terminate()`.

**Consecuencias.** Fail-loud operativo (rojo + acción deshabilitada + motivo
visible). La GUI **no muta configs**: al dar de alta una geometría nueva
muestra la instrucción para editar el YAML a mano (candidato a iter 2).
Dependencia nueva: PySide6 (LGPL) en el venv. Verificado headless (BA real,
fail-loud, Detener) **+ EN VIVO (núcleo) 2026-08-13** con la Femto real
(panel y semáforos, probar cámara, verificar IDs, tracker → OpenIGTLink →
Slicer con cierre limpio); pendientes las verificaciones opcionales con
hardware (dock, BA live, asistente "dodecaedro nuevo").

---

## ADR-018 — La GUI puede mutar SOLO `camera.calibration_file` (edición quirúrgica)
**Fecha:** 2026-08-13 · **Estado:** Aceptada

**Contexto.** brief-02 M3: gestionar la calibración de cámara desde el panel
requiere apuntar el perfil a un `.yml` nuevo. La regla de brief-01 era "la GUI
no muta configs" (ADR-017); un round-trip de PyYAML destruiría los comentarios
de los configs (documentan el tuning del detector).

**Decisión.** Excepción ÚNICA y acotada: el panel puede editar la línea
`calibration_file:` de un `tracker_config*.yaml`, con estas guardas
(`gui/perfil_editor.py`): (a) reemplazo TEXTUAL de esa única línea —
comentarios y EOLs del resto intactos byte a byte; (b) backup timestampeado
ANTES de escribir; (c) confirmación mostrando el antes/después exacto; (d)
aborta sin tocar nada si el patrón no aparece EXACTAMENTE una vez; (e) el
`.yml` destino se valida antes (camera_matrix/distortion_coefficients); (f)
verificación post-escritura. Todo lo demás del YAML sigue inmutable para la GUI.

---

## ADR-019 — Los datos de paciente siguen versionados; los agentes no los leen
**Fecha:** 2026-10-19 · **Estado:** Aceptada

**Contexto.** Al montar el método (paso 0) apareció que git versiona 449
archivos DICOM (`herramientas/A/`, ~228 MB, desde 2026-05-26) y un volumen CT
(`codigo/historico/iter2/202 AXIAL.nrrd`, 87 MB, desde 2026-06-15).
`CONTEXT.md` §2 decía que el DICOM no se sube a repos.

**Decisión.** El autor decide **dejarlos en el árbol y en el historial**: el
repo lo usan solo médicos del equipo. A cambio, ningún agente los lee, los edita
ni los envía a servicios externos: `.claude/settings.json` niega `Read`/`Edit`
de `herramientas/A/**`, `**/*.nrrd`, `**/*.dcm` y `documentos/VERONICA/**`.
`CONTEXT.md` §2 se corrige en el mismo cambio.

**Consecuencias.** No se reescribe el historial. Si el repo se abre a gente
fuera del equipo médico, esta decisión se reabre. El `.git` sigue pesando por
estos binarios (BACKLOG).

---

## ADR-020 — Método de trabajo por specs, con constitución y el autor como único que commitea
**Fecha:** 2026-10-19 · **Estado:** Aceptada

**Contexto.** La metodología MVD + briefs (CONTEXT §5) dejaba que el
implementador hiciera commit y push, y repartía el estado entre briefs, MVD y
la memoria privada de cada sesión.

**Decisión.** Se adopta el método de segmentadorDicom, por etapas:
`docs/constitution.md` (lo que no se negocia; cambiarlo exige un ADR),
`CLAUDE.md` como instrucción de herramienta, `memory.md` como estado,
`docs/BACKLOG.md` como lo pendiente y `specs/NNN-nombre/` (spec → plan
autorizado → fases) en lugar de `briefs/`. **Ningún agente hace commit ni push**:
los hace el autor (negado en `.claude/settings.json`). Los 3 MVD pasan a `docs/`.
Lo único que no se puede romper nunca es la cadena tracker → OpenIGTLink →
Slicer y su jerarquía (principio 6); lo demás puede cambiar con su plan.

**Consecuencias.** Hay dos paradas del autor: la autorización de cada plan y
cada commit. La etapa 2 (agentes por papel y skills) y la 3 (hooks) vienen
después. Los `briefs/` existentes quedan como historia.

**Consecuencias.** Recalibrar y apuntar la cámara sin editar YAML a mano. El
comentario inline de la línea editada (si lo había) se reemplaza con el valor
viejo que describía. Verificado headless sobre copia real del perfil (diff de
1 línea, backup idéntico, YAML re-parsea). Editar `geometry_file` u otras
claves queda explícitamente FUERA (el asistente sigue mostrando la instrucción).

---

## ADR-021 — La punta vigente se respalda como copia versionada fuera del glob de Slicer
**Fecha:** 2026-10-19 · **Estado:** Aceptada

**Contexto.** La calibración de punta vigente
(`StylusTipToDodecaedro_femto_dock.npy/.txt`, contexto canónico, ADR-015) estaba
fuera de git porque `.gitignore` excluye las puntas, que son por equipo
(B03). Si se perdía el disco, se perdía la punta. Versionarla en su sitio
tiene un riesgo: el snippet de Slicer (`MANUAL_simplificado.md` §4.2) y
`estado.py` toman la `StylusTipToDodecaedro*.npy` más reciente de
`iter4/data/`, y en la máquina del doctor un `git pull` la volvería la más
reciente y Slicer cargaría una punta de otro ensamble (B20). Fuera de git
(USB, nube) dependía de copiarla a mano y no tenía historia.

**Decisión.** El autor elige (meta 001, `clarify.md` P3 = A', 2026-10-19) una
**copia byte a byte** en `codigo/iter4/data/respaldo_puntas/`, versionada con
dos excepciones `!` en `.gitignore`. El original sigue en `iter4/data/` y
fuera de git; la copia, en una subcarpeta, no la ve ni el glob no recursivo de
Slicer ni `estado.py`. El sha256 de referencia está en `ARCHITECTURE.md` §3.4.

**Consecuencias.** La copia no sigue sola a la punta: quien recalibre la punta
del contexto canónico copia de nuevo los dos archivos a `respaldo_puntas/`,
actualiza el sha256 de `ARCHITECTURE.md` §3.4 y lo hace en el mismo commit.
Restaurar es copiarla de vuelta a `iter4/data/`. El `.txt` se guarda con LF
(`.gitattributes`), así que su sha256 tras un checkout es el del texto
normalizado; el `.npy` es binario e idéntico. Las puntas de otros equipos
siguen fuera de git. Cuando B20 haga que Slicer nombre la punta explícita, esta
decisión se puede revisar.

## ADR-022 — Fable solo para implementar: las fases pesadas en dos tiempos
**Fecha:** 2026-10-21 · **Estado:** Aceptada

**Contexto.** Fable tiene una cuota semanal. Una fase lanzada entera con un
solo modelo gasta buena parte en trabajo mecánico que no lo necesita: correr la
suite dos veces y leer su salida, la equivalencia (replay), escribir el reporte,
`memory.md` y el BACKLOG, y proponer el commit. En Claude Code un subagente no
puede lanzar otros subagentes (la herramienta `Agent` es de la sesión
principal), así que `desarrollo` no puede repartir su trabajo entre modelos: el
reparto lo hace la dirección, con el parámetro `model` de cada llamada a
`Agent`, que manda sobre el `model:` del frontmatter. Es la misma decisión que
el ADR-043 de SegmentadorDicom, traída por el autor (2026-10-21).

**Decisión.**
1. **El peso.** Cada fase del plan declara su peso: «pesada» (lógica nueva, un
   fallo difícil, la cadena del principio 6) o «ligera» (textos, mover código,
   ajustes, un caso más). Una fase sin peso cuenta como pesada.
2. **Dos tiempos para las pesadas.** La dirección lanza primero
   «/fase n implementa» con Fable: comprueba la marca, la casilla y el commit
   anterior, lee el plan y el código, implementa, corre solo las pruebas de la
   fase, mide el criterio y deja una nota en
   `Claude outputs/fases/<NNN>/<fase>-implementa.md`; devuelve «Implementada:
   criterio y número» o «Parado: por qué». Al volver, «/fase n verifica» con
   sonnet: parte del árbol que dejó «implementa» (su nota y el `git diff`),
   corre la suite completa dos veces y la equivalencia, marca la casilla, hace
   el cierre (`memory.md`, BACKLOG, índices), escribe el reporte y propone el
   commit; un arreglo pequeño lo hace él; si un fallo pide diseño, devuelve
   «Parado: falla X» y la dirección relanza «implementa» con Fable.
3. **Lo demás, sin Fable.** Fase ligera: «/fase n» de una vez, con opus.
   «/cerrar-fase» y los encargos cortos («falta X; corrige»): sonnet u opus.
   Planificación y pruebas: su modelo de siempre.
4. **El respaldo.** Si Fable se queda sin cuota a media fase, la dirección
   relanza «implementa» con opus y el mensaje «continúa la fase n implementa:
   mira tasks.md y git status»; el trabajo ya está en el disco.

**Consecuencias.** Fable trabaja solo en el código; la verificación, que es
una parte grande de lo que gasta una fase, la hace sonnet. Una fase pesada son
dos lanzamientos y dos resúmenes para la dirección, con el árbol sin commitear
entre ellos (la dirección no escribe `memory.md`, `docs/` ni `.claude/`
mientras tanto, como con cualquier fase). La skill `planear` pide el peso; la
skill `fase` acepta «n», «n implementa» y «n verifica»; `desarrollo.md` y
`direccion.md` lo recogen. El `model:` del frontmatter de `desarrollo` queda
como valor por defecto: la dirección lo fija en cada lanzamiento.

---

## ADR-023 — La SVPRO AR0234 es de obturador global (corrige ADR-016)
**Fecha:** 2026-10-23 · **Estado:** Aceptada

**Contexto.** El ADR-016 dice que la SVPRO (sensor AR0234) era de *rolling shutter* y que por eso se adoptó otra cámara «global shutter» para el contexto doctor. Es al revés: el AR0234 de onsemi es un sensor CMOS de 2.3 MP con **obturador global** (hoja de datos del fabricante). La meta 002 (`specs/002-calibracion-camaras/`) trabajó con dos SVPRO AR0234 como cámaras del tracker; la sonda de la fase 1 no puede medir el tipo de obturador, así que el dato viene del fabricante, no de una medición.

**Decisión.** Las dos SVPRO AR0234 son las cámaras global shutter del proyecto. El ADR-016 no se reescribe: queda marcado «Reemplazado por ADR-023 y ADR-024» y su perfil (`tracker_config_doctor.yaml`, `data/globalshutter.yml`) está archivado en `iter4/data/historico/` desde la fase 6 (`2322553`).

**Consecuencias.** Lo que el ADR-016 atribuía al obturador no se apoya en él. Con el objeto quieto, la cámara 2 dio sd z 1.08–1.15 mm a ~45 cm (fase 6); el salto de pose de la cámara 1 vino del juego de markers (B37), no del obturador. Si algún día se quiere medir el obturador (barrido rápido de una línea recta), va al BACKLOG.

---

## ADR-024 — Un perfil por cámara física, identificada por su puerto USB
**Fecha:** 2026-10-23 · **Estado:** Aceptada

**Contexto.** Las dos SVPRO declaran la misma serie (`01.00.00`) y Windows da la instancia de esa serie a la primera que se conecta, en cualquier puerto; el índice de OpenCV cambia con el orden de conexión. Por MSMF, OpenCV no lee ni escribe los controles de la cámara; por DSHOW sí. Con la aceleración por hardware de MSMF encendida (el valor por defecto de OpenCV), abrir la cámara tardaba 43–51 s (meta 002, fases 1, 2a y 2b).

**Decisión.**
1. **Un perfil por cámara física** (`tracker_config_gs1.yaml`, `tracker_config_gs2.yaml`), no por contexto. La cámara se identifica por la **ruta física de su puerto USB** (`usb_port_windows`, `DEVPKEY_Device_LocationPaths` por CfgMgr32, `camaras_uvc.py`): la identidad es la del puerto, y las cámaras y los puertos van etiquetados.
2. **La marca.** Cada perfil declara una marca (`focus`, cámara 1 = 500, cámara 2 = 332) que se **escribe a propósito** al dar de alta la cámara (`sondear_camara.py --fijar … --forzar`): sin escribir, la cámara la mueve sola. El backend la lee antes de escribir nada y para si no coincide (cámaras intercambiadas).
3. **Los ajustes** se declaran en el perfil con nombres y unidades propios (exposición en ms) y una capa por sistema los aplica: en Windows, DSHOW en una apertura corta antes del vídeo, escribiendo solo lo que difiere; Linux (V4L2) tiene sitio.
4. **El vídeo, por MSMF** con la aceleración HW apagada por el código (`OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` con `setdefault`, antes de importar `cv2`; el panel la pone a sus hijos): apertura de 43–51 s a 0.4–0.6 s, sin perder fps (90 en todos los modos).
5. **El tamaño.** El backend para si el frame no tiene el tamaño del perfil o el del `.yml` de intrínsecos.
6. **El modo común:** 1280×960 MJPG 90 fps, exposición 0.977 ms (P15, P16); cada perfil apunta a su `.yml` (`intrinsecos_gs1/gs2_1280x960.yml`, tablero medido 24.86 mm, detector `sb`).

**Consecuencias.** Cambiar de hub o de puerto cambia la ruta: hay que reapuntar el perfil. Una cámara nueva se da de alta escribiendo su marca. `tracker.py` lanzado a mano no apaga la aceleración (B28); desde el panel sí. No reescribe el ADR-018: el panel sigue mutando solo `camera.calibration_file`, con backup.

---

## ADR-025 — Se rescata solo el tracking; lo demás se rehace sobre las cámaras nuevas
**Fecha:** 2026-10-23 (decisión del autor del 2026-10-20) · **Estado:** Aceptada

**Contexto.** El sistema se construyó sobre la Femto Bolt (ADR-006, ADR-015) y la webcam del contexto doctor (ADR-016). La punta, el registro paired-point, la navegación en Slicer y los runbooks se validaron con esas cámaras y esos perfiles. Con las dos SVPRO calibradas (meta 002), el autor decidió el 2026-10-20 no arrastrar lo viejo.

**Decisión.**
1. **Se rescata el tracking:** `tracker.py`, el detector, la geometría del dodecaedro v2 (ADR-009, cámara-independiente), el filtro 1-Euro y el envío por OpenIGTLink.
2. **Se rehacen, mejorados y sobre los perfiles gs1/gs2:** la calibración de la punta, el registro, la navegación en Slicer y los runbooks. Lo viejo queda como referencia, no como camino.
3. **Perfiles:** solo valen `tracker_config_gs1.yaml` y `tracker_config_gs2.yaml`. `tracker_config.yaml` (Femto) se conserva porque de él dependen el replay y el selftest; el doctor está archivado (ADR-023).
4. **El principio 6 no cambia:** los nombres (`Marker0ToTracker`, `DodecaedroToTracker`), el puerto 18944 y la jerarquía de Slicer siguen siendo los mismos. Lo que se rehaga en Slicer los respeta; cambiarlos exige su ADR y una verificación en vivo, como dice la constitución.

**Consecuencias.** El ADR-015 (config canónica = Femto) queda «Reemplazado por ADR-025»; el ADR-014 y el ADR-012 no cambian (la Femto *depth* sigue en pausa). La meta siguiente es optimizar el tracker (B32), empezando por el salto de pose al cambiar el juego de markers (B37, alta); después, la punta y el registro con las cámaras nuevas.
