# brief-01 — Panel de control gráfico (GUI), iteración 1

> **Para Claude Code.** Leé este brief + los 3 MVD (`ARCHITECTURE.md`,
> `DECISIONS.md`, `CONTEXT.md`) y devolvé un **PLAN numerado, SIN ejecutar nada
> todavía**. Sondeá primero el terreno real (interfaces de los scripts) antes de
> diseñar. Cuando aprobemos el plan, implementás por pasos verificables.

---

## 1. Contexto / porqué

Hoy el pipeline son pasos sueltos por consola (`identificar_ids.py`,
`captura_calibracion.py`, `calibrar_rigid_body.py`, `calibrar_tip_divot.py`,
`tracker.py`), repetitivos y difíciles de usar en orden correcto. Es fácil, por
ejemplo, arrancar el tracker sin geometría calibrada o con la calibración de punta
equivocada. Queremos un **panel gráfico** que orqueste todo desde un solo lugar y
que haga visible el principio *fail-loud*: **semáforos verde/rojo** por
prerrequisito (si no existe una calibración → rojo; si existe → verde).

## 2. Objetivo (iteración 1)

Una app de escritorio en **PySide6/Qt** que corre en Windows desde el `.venv` del
proyecto y que:

1. **Semáforos de prerrequisitos** que leen el **estado real** del repo (archivos
   en disco), no un estado inventado: config activa válida, geometría calibrada
   del rigid body presente, calibración de punta presente y coherente con la
   geometría, (si es factible sin bloquear) cámara disponible.
2. **Botones que lanzan los scripts EXISTENTES tal cual** (como subproceso), sin
   reescribir su lógica: verificar IDs, capturar dataset para BA, correr BA,
   calibrar la punta (dock), arrancar el tracker.
3. **Selección del perfil/config activo** (p.ej. `tracker_config.yaml`,
   `tracker_config_doctor.yaml`, `tracker_config_stylus_impreso.yaml`) para saber
   qué geometría/IDs se van a usar; los semáforos se recalculan según el perfil.
4. **Flujo "dar de alta un dodecaedro nuevo"** (esto es lo que el doctor llama
   "elegir qué IDs voy a usar"): elegir el rango de IDs / config semilla →
   capturar dataset → correr BA → guardar la geometría `*_calibrado.txt`,
   **encadenando los scripts existentes**. La app guía el orden correcto.
5. **Panel de log** que muestra la salida (stdout/stderr) de cada script en vivo,
   verbose, para que nada falle en silencio.

## 3. Reglas y restricciones heredadas (NO negociables)

De `CONTEXT.md` (y deben respetarse):

- **La GUI SOLO orquesta.** No reescribe ni altera la lógica de tracking ni de
  calibración. Si un script necesita un cambio (p.ej. un flag nuevo), es una
  **decisión aparte** que se marca, no se hace de pasada.
- **No romper las interfaces ni el comportamiento de los scripts existentes.**
- **Fail-loud:** si falta un prerrequisito, semáforo **rojo** + mensaje claro, y
  la acción dependiente queda **deshabilitada** (no se puede arrancar el tracker
  sin config + geometría válidas).
- **Geometría del rigid body y calibración de la punta = mismo ensamble.** Los
  semáforos deben detectar y avisar si la punta cargada NO corresponde a la
  geometría del perfil activo.
- **Entorno:** Windows, Python 3.11.9, `codigo\.venv`. PySide6 se instala en ese
  venv (agregar a `requirements.txt`). **Git siempre desde PowerShell.**
- **Verbose visible** (los scripts ya imprimen progreso; la GUI lo muestra).
- Al cerrar la iteración, **actualizar los MVD** (nuevo componente en
  `ARCHITECTURE.md`, ADR de la GUI en `DECISIONS.md`, estado en `CONTEXT.md`).

## 4. Alcance sugerido (a confirmar/afinar en tu PLAN)

- Nuevo componente, probablemente en una carpeta propia (p.ej. `codigo\iter4\gui\`
  o `codigo\gui\` — proponé tú la ubicación en el plan).
- Capa fina de "orquestador de procesos" que lanza los scripts como subproceso,
  captura su salida y conoce sus prerrequisitos.
- Una sola ventana: selector de perfil, fila de semáforos, botones de acción
  (agrupados: *Verificar/Preparar* · *Calibrar* · *Operar*), y panel de log.

## 5. Dudas a marcar (sondear y responder en el PLAN, no asumir)

1. **Interfaz CLI real de cada script:** args exactos y cómo terminan
   (`identificar_ids`, `captura_calibracion`, `calibrar_rigid_body`,
   `calibrar_tip_divot`, `tracker`). Verificar contra el código, no contra el
   manual.
2. **Cómo se seleccionan hoy los IDs / el rigid body:** vía `geometry_file` +
   `marker_mm` en el YAML. ¿Alcanza con cambiar de config, o hace falta algo más?
3. **Dónde viven** geometrías (`data\reference_*`), calibraciones de punta
   (`data\StylusTipToDodecaedro_*`) e intrínsecos, para que los semáforos los
   detecten.
4. **Detección de "cámara disponible"** sin bloquear ni robarle la cámara al
   tracker (¿un chequeo rápido de apertura y liberación? ¿o se omite en iter 1?).
5. **Coherencia punta↔geometría:** cómo determinarla de forma robusta (¿por el
   header de metadata del `.txt` de la punta, que referencia la geometría?).
6. **Ubicación del componente** y si conviene un módulo compartido de "estado del
   proyecto" reutilizable.

## 6. Prueba de aceptación (qué define "hecho" en iter 1)

- La app **abre en Windows** desde el venv sin error.
- Los **semáforos reflejan el estado real**: al renombrar/mover la geometría
  calibrada, el semáforo correspondiente pasa a **rojo**; al restaurarla, **verde**
  (demostrable en vivo).
- **Cada botón lanza el script correcto** con los args correctos y muestra su
  salida en el panel de log.
- El **flujo "dodecaedro nuevo"** se puede completar de punta a punta desde la app
  (capturar → BA → geometría guardada), encadenando los scripts existentes.
- **Arrancar el tracker está bloqueado** (o en rojo) si falta config o geometría
  válida.
- **Ningún script existente** de tracking/calibración fue modificado (verificable
  por `git diff`).

## 7. Fuera de alcance (iteración 1 — para futuras)

- Video/preview de la cámara embebido dentro de la app (los scripts siguen
  abriendo sus ventanas de OpenCV).
- Edición gráfica de IDs / picking de marcadores en vivo.
- Control de 3D Slicer desde la app (conexión OpenIGTLink, cadena de transforms).
- Empaquetado a `.exe` / instalador.
- Rediseño o refactor de los scripts subyacentes.

---

**Entregable de este paso:** un PLAN numerado con criterio de aceptación por paso,
las respuestas a las dudas de §5, y la ubicación propuesta del componente. **Sin
ejecutar todavía.**
