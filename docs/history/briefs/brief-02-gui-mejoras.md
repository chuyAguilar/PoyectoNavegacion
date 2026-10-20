# brief-02 — Refinamiento de la GUI (panel de control), iteración 2

> **Para Claude Code.** Releé los 3 MVD (`ARCHITECTURE.md`, `DECISIONS.md`,
> `CONTEXT.md` — ya actualizados) y este brief, y devolvé un **PLAN numerado, SIN
> ejecutar**. Sondeá las interfaces reales antes de diseñar. Esperá aprobación.

---

## 1. Contexto / porqué

`brief-01` entregó el panel de control (`codigo/iter4/gui/`), verificado en vivo
2026-08-13. Al exprimirlo con hardware real salieron **5 mejoras concretas** de UX
y robustez. Este brief las agrupa. El panel sigue siendo **solo-orquestador** salvo
donde este brief indique lo contrario.

## 2. Objetivo (iteración 2)

Refinar el panel existente con las 5 mejoras de abajo, **sin romper** lo validado
en brief-01 (semáforos, gating, Detener, asistente, tracker→Slicer).

### Mejora 1 — Default de semilla en el asistente (fix rápido)
Hoy el asistente "dodecaedro nuevo" arranca con `reference_dodecaedro.txt` (IDs
viejos 170–180) como semilla por default → **footgun**: capturar con esa semilla
y el dodecaedro v2 junta **0 frames útiles en silencio** (CONTEXT §4.14). Cambiar
el default a algo sensato: la geometría del perfil activo si aplica, o la teórica
v2, o forzar selección explícita. El ancla ya sincroniza a la semilla elegida
(mantener ese comportamiento, funciona bien).

### Mejora 2 — Alta de un dodecaedro REALMENTE nuevo (generar teórica)
Hoy el asistente solo **recalibra un layout existente** (eliges un archivo semilla
que ya existe). Para dar de alta un dodecaedro con **IDs nuevos** desde cero, el
asistente debería permitir especificar el layout por **inputs** — cara superior
(ID), anillo superior (IDs), anillo inferior (IDs), arista, lado del marker — y
**generar la teórica semilla** con `generar_reference_dodecaedro.py`, y de ahí
seguir con capturar → BA. Es el paso "generar teórica" que se difirió a propósito
de iter 1 (decisión §E.2 de brief-01). Motivación del doctor: los IDs de los
anillos deberían ser inputs, no la obligación de tener un archivo previo.

### Mejora 3 — Gestión de calibración de cámara desde el panel
Hoy el panel solo consume la calibración existente (fábrica del SDK para la Femto;
el `.yml` que apunta el perfil para webcam). No deja, desde la UI, **cargar/apuntar
a un `.yml` existente** ni **correr una calibración de cámara**. Relevante sobre
todo para el contexto webcam/global shutter (la Femto de fábrica está bien).

### Mejora 4 — Limpiar y reordenar el grupo "Calibrar" (fix rápido)
Los botones sueltos **"Capturar dataset BA"** y **"Correr BA"** son **redundantes**
con el asistente (que ya encadena captura→BA) y peligrosos sueltos (invitan a
correrlos con defaults del stylus viejo). Quitarlos del menú (viven dentro del
asistente). Reordenar el grupo: **Asistente (dodecaedro nuevo) primero, Calibrar
punta (dock) después**.

### Mejora 5 — BA: convergencia visible y cortes sanos
En la prueba en vivo, un BA sobre una captura corta (cobertura floja del anillo
inferior; par (3,9) visto 1 vez) quedó **grindeando 2 horas** (step norm clavado
en 0.35, cost casi sin bajar) sin señal de que no iba a converger. Mejorar: (a)
`--max-nfev` default más sensato; (b) **detección/aviso de no-convergencia** (step
norm estancado / cost sin reducir) con sugerencia de recapturar; (c) idealmente,
un **chequeo de cobertura mínima post-captura** (pares únicos, % por marker) que
avise "cobertura floja → el BA puede no converger" **antes** de ofrecer correr el
BA. Evita las 2 horas ciegas.

## 3. Reglas y restricciones heredadas (NO negociables)

De `CONTEXT.md`. En particular:
- El panel sigue **solo-orquestando** los scripts existentes, **salvo**: la Mejora
  2 (invoca `generar_reference_dodecaedro.py` para generar la teórica) y la posible
  edición de YAML de la Mejora 3 (a decidir en el plan — ver dudas).
- **No romper** nada de lo validado en brief-01 (`git diff` de los scripts de
  tracking/calibración debe seguir vacío; los cambios son en `iter4/gui/`).
- Fail-loud; verbose; validar truncados tras editar (`py_compile` + conteo).
- **Git siempre desde PowerShell.** Actualizar los MVD al cierre.

## 4. Alcance sugerido (a confirmar/priorizar en el PLAN)

Propuesta de orden por costo/riesgo: **Mejoras 1 y 4** (fixes rápidos de UX) →
**Mejora 5** (robustez del BA) → **Mejoras 2 y 3** (features más grandes, que
tocan interfaces nuevas). Podrían ser sub-iteraciones numeradas dentro de este
brief.

## 5. Dudas a marcar (sondear en el PLAN, no asumir)

1. **Mejora 2:** interfaz real de `generar_reference_dodecaedro.py` (args, cómo se
   especifica el layout de anillos, qué produce). ¿Genera un `.txt` compatible con
   el `--geometry-file` de captura y el `--teorico` del BA?
2. **Mejora 3:** ¿la GUI **edita** el YAML (con backup) para apuntar a un `.yml`
   nuevo, o solo **muestra la instrucción** (coherente con "no muta config")? ¿Qué
   herramienta de calibración de cámara — MRPT externo (readme §8) o un script
   OpenCV chessboard propio?
3. **Mejora 5:** ¿umbral de cobertura mínima razonable (pares únicos, % por
   marker)? ¿Cómo detectar no-convergencia de forma robusta (step norm estancado N
   iteraciones)?
4. ¿Conviene un módulo compartido para el layout de dodecaedro (usado por la
   generación de teórica y por los semáforos)?

## 6. Prueba de aceptación (qué define "hecho")

- **M1:** al abrir el asistente con el perfil v2, la semilla por default **no** es
  la vieja (170–180); no es posible capturar 0 frames por el default.
- **M2:** se puede dar de alta un dodecaedro con **IDs nuevos** especificando el
  layout, generando la teórica y corriendo captura→BA, **sin archivo previo**.
- **M3:** desde el panel se puede apuntar el perfil a un `.yml` de calibración (o
  queda documentado/claro cómo); el semáforo de intrínsecos lo refleja.
- **M4:** el grupo "Calibrar" ya **no** tiene los botones sueltos de captura/BA;
  orden = asistente → dock.
- **M5:** un BA que no converge se **corta o avisa** en tiempo razonable (no 2
  horas ciegas); una captura con cobertura floja **avisa antes** de correr el BA.
- `git diff` no toca los scripts existentes salvo lo intencional (Mejora 2 usa
  `generar_reference_dodecaedro.py` tal cual); MVD actualizados al cierre.

## 7. Fuera de alcance (iteración 2)

- Nada del tracking / registro / paired-point en sí.
- Nada de control de 3D Slicer desde la app.
- Video embebido en la app; empaquetado a `.exe`.
- Rediseño de los scripts subyacentes (más allá de invocar
  `generar_reference_dodecaedro.py`).

---

**Entregable:** PLAN numerado con criterio de aceptación por paso, respuestas a las
dudas de §5, priorización de las 5 mejoras y ubicación. **Sin ejecutar.**
