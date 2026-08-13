# Prompt para Claude Code — Primer encargo (onboarding + brief-01)

> Pegá este mensaje a Claude Code en el repo `C:\Dev\Dr.Milton\PoyectoNavegacion`,
> junto con el archivo `brief-01-gui-panel.md`.

---

Vas a trabajar como el **implementador** de este proyecto. Antes de tocar nada,
leé esto completo: es tu primer encargo y necesito que entiendas el terreno, no
solo la tarea.

## Quién sos aquí y cómo trabajamos

Este NO es un proyecto nuevo. Es un sistema de navegación quirúrgica óptica con
**meses de trabajo, código que ya funciona y decisiones ya tomadas**. Tu trabajo
no es reinventarlo: es **leerlo, reconocerlo, analizarlo** y, sobre esa base,
planear e implementar cambios acotados.

Trabajamos con una metodología de **documentos vivos + orquestación**:
- El doctor + un orquestador (Cowork) planean y te entregan un `brief.md` acotado.
- Vos leés el brief y los documentos maestros, y devolvés un **PLAN sin ejecutar**.
- Se aprueba el plan, y recién ahí implementás, en pasos chicos y verificables.
- Al final: commit, actualizás los documentos maestros y push.
- El doctor es el puente entre vos y el orquestador.

Respondé en **español**, directo y honesto (incluida la incertidumbre).

## Paso 0 — Leé PRIMERO los 3 documentos maestros (MVD), completos y en orden

Están en la raíz del repo. Son la **fuente de verdad**; todo lo que propongas debe
ser coherente con ellos:

1. **`ARCHITECTURE.md`** — el *qué*: topología, componentes, flujo de datos, cadena
   de transforms, estructura del repo.
2. **`DECISIONS.md`** — el *porqué*: registro de decisiones (ADRs). La historia no
   se borra; entendé por qué las cosas son como son antes de cambiarlas.
3. **`CONTEXT.md`** — las *reglas y el estado*: restricciones NO negociables,
   entorno/máquinas, y qué está hecho / en pausa / WIP.

Si encontrás algo en el código que **contradice** a los MVD, marcálo explícitamente
(no lo silencies ni lo "arregles" de pasada).

## Paso 1 — Reconocé y analizá lo que YA existe

Antes de diseñar nada, explorá y entendé el pipeline actual. Como mínimo:
- `codigo\iter4\`: `tracker.py`, `identificar_ids.py`, `captura_calibracion.py`,
  `calibrar_rigid_body.py`, `calibrar_tip_divot.py`, `camera_backend.py`.
- Los configs `tracker_config*.yaml` y la carpeta `data\` (geometrías
  `reference_*`, calibraciones de punta `StylusTipToDodecaedro_*`, intrínsecos).

Los scripts **funcionan y se respetan**: el encargo de esta iteración los
**orquesta**, no los reescribe.

## Paso 2 — Leé el encargo actual

`brief-01-gui-panel.md` (te lo adjunto / está en la carpeta de briefs). Es el
alcance concreto de esta iteración: un panel gráfico en PySide6 que orquesta los
scripts existentes y muestra semáforos de prerrequisitos.

## Paso 3 — Sondeá el terreno real (no supongas)

Verificá las **interfaces reales** de cada script (args de CLI, cómo terminan, qué
prerrequisitos tienen) **leyendo el código**, no el manual — el manual puede estar
desactualizado. Confirmá dónde viven las geometrías, calibraciones e intrínsecos.

## Paso 4 — Devolvé un PLAN, y DETENTE (no ejecutes todavía)

Entregá un **plan numerado** que incluya:
- Las **respuestas a las dudas** del §5 del brief (con lo que encontraste al
  sondear).
- La **ubicación propuesta** del componente nuevo.
- **Pasos numerados**, cada uno con su **criterio de aceptación**.
- Riesgos y decisiones abiertas.

Después del plan, **esperá aprobación**. No escribas código de la app hasta que lo
aprobemos.

## Paso 5 — (Tras aprobación) Implementá por pasos verificables

Principios que aplicás siempre:
- **Sonda antes de codificar**; **fallar fuerte, no en silencio**.
- **Revisión adversarial de tu propio código** antes de darlo por bueno.
- **Verificar empíricamente antes de declarar "hecho"** (que la app abra en el
  venv, que los semáforos reflejen el estado real, que los botones lancen lo
  correcto).
- Cambios chicos; **verbose** visible.
- Tras editar archivos, validá que no se truncaron (`py_compile`, conteo de
  líneas): `Edit`/`Write` a veces truncan en silencio en este repo.

## Paso 6 — Cierre

- **Commit desde PowerShell** (nunca desde otro shell — sobre este repo NTFS deja
  locks huérfanos).
- **Actualizá los MVD** afectados (nuevo componente en `ARCHITECTURE.md`, un ADR de
  la GUI en `DECISIONS.md`, estado en `CONTEXT.md`) y push.

## Lo que NO te ocupa

El archivado/renombrado de los briefs cuando pasemos al siguiente lo maneja el
orquestador. Vos concentrate en el brief activo.

---

**Ahora:** hacé el Paso 0 al Paso 3 y devolveme el PLAN del Paso 4. Sin ejecutar.
