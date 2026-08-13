# DECISIONS.md — Registro de Decisiones (ADRs)

> **Qué es este documento (MVD 2 de 3):** el **porqué** del sistema. Cada entrada
> es un ADR (Architecture Decision Record): **contexto → decisión → consecuencias**.
> Es un documento **vivo** y **acumulativo**: la historia NO se borra. Cuando una
> decisión reemplaza a otra, la vieja se marca `Reemplazada por ADR-NNN` y se
> conserva, para no repetir errores ya pagados.
>
> Estados: `Aceptada` · `Reemplazada` · `En pausa` · `Propuesta`.
> _Última actualización: 2026-08-13._

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
| 015 | Config canónica = `tracker_config.yaml` (Femto RGB, Marker0 80 mm, tip existente) | Aceptada |
| 016 | Cámara global shutter para el contexto "doctor" (webcam) | Aceptada |

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
**Fecha:** 2026-08-13 · **Estado:** Aceptada

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
**Fecha:** commit reciente en `origin/main` (fecha exacta en git log) · **Estado:** Aceptada

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
