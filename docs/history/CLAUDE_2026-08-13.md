# CLAUDE.md — Proyecto de Navegación Quirúrgica de Dr. Milton

Instrucciones para Claude al trabajar en este proyecto. Breve y enfocado.

## LEER PRIMERO: los 3 documentos vivos (MVD)

Antes de tocar código, leer los tres documentos maestros en la raíz del repo. Son
la fuente de verdad y se mantienen actualizados:

- **`ARCHITECTURE.md`** — el *qué*: topología, componentes, flujo de datos, cadena
  de transforms, estructura del repo.
- **`DECISIONS.md`** — el *porqué*: registro de decisiones (ADRs), con historia.
- **`CONTEXT.md`** — las *reglas y el estado*: restricciones no negociables,
  entorno/máquinas, y qué está hecho / en pausa / WIP.

Conocimiento técnico detallado en las skills: `surgical-navigation-aruco`
(ArUco, pose, bundle adjustment), `slicer-igt-workflow` (3D Slicer + SlicerIGT),
`surgical-nav-project-context` (setup e historia del proyecto).

## Descripción

Sistema de navegación quirúrgica óptica para cirugía ortopédica de columna.
Trackea instrumentos y anatomía con marcadores ArUco + cámara y visualiza la
coherencia espacial en 3D Slicer. **Vía activa:** registro **paired-point** con la
Femto Bolt como cámara RGB. La rama de nube de puntos (depth) está en pausa
(ver `DECISIONS.md` ADR-014).

## Estilo de trabajo

- Responder en **español**. Directo y honesto, incluida la incertidumbre.
- **Validar cuantitativamente en cada paso.** No aceptar "se ve bien".
- **Un cambio a la vez** al debuggear. Diagnóstico antes que fix.
- Scripts no triviales: **verbose paso a paso**, no quedarse mudo.
- Metodología MVD + orquestación (ver `CONTEXT.md` §5): leer los 3 MVD, plan antes
  de ejecutar, verificar empíricamente antes de declarar "hecho", y **actualizar
  los MVD al cerrar cada iteración**.

## Entorno y comandos

- Raíz: `C:\Dev\Dr.Milton\PoyectoNavegacion`. Código activo: `codigo\iter4\`.
- Todo git y shell desde **PowerShell** (nunca desde el sandbox Linux; deja lock
  huérfano sobre NTFS).

```powershell
# Activar entorno
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate

# Verificar IDs/orientación del dodecaedro (v2 compartido, IDs 3-13)
python iter4\identificar_ids.py --config iter4\tracker_config.yaml

# Tracker principal (Slicer conectado ANTES) — config canónica = Femto RGB
python iter4\tracker.py --config iter4\tracker_config.yaml

# Capturar dataset para bundle adjustment
python iter4\captura_calibracion.py --duracion 60

# Bundle adjustment
python iter4\calibrar_rigid_body.py --max-frames 500 --max-nfev 3000

# Calibración de la punta por dock
python iter4\calibrar_tip_divot.py --config iter4\tracker_config.yaml --divot DOCK --plate-id 2 --plate-mm 59.6
```

## Cosas críticas (detalle completo en `CONTEXT.md` §4)

1. **Geometría `reference_*_calibrado.txt`** (BA), nunca la teórica.
2. **Dos cámaras, dos contextos (ambas activas):** contexto principal = Femto Bolt
   (RGB), `tracker_config.yaml`, Marker0 80 mm; contexto "doctor" = webcam **global
   shutter**, `tracker_config_doctor.yaml` + `data/globalshutter.yml`, Marker0
   60 mm. Dodecaedro v2 (IDs 3-13, marker 14.6 mm) y tip
   `StylusTipToDodecaedro_femto_dock` se comparten.
3. **`calibrar_rigid_body.py`**: defaults son del stylus viejo (`--ancla 170
   --marker-mm 13.4`). Para v2 pasar **`--ancla 3 --marker-mm 14.6`**. Webcam:
   backend MSMF + códec MJPG o el FPS cae a 5.
4. **No enviar video** por pyigtl (`send_video: false`).
5. **pyigtl bloquea si Slicer no está conectado** → conectar Slicer ANTES.
6. **Jerarquía de Slicer** para paired-point: seguir `MANUAL_simplificado.md` y la
   skill `slicer-igt-workflow` al pie de la letra.
7. **Geometría y calibración de punta = mismo ensamble.** No mezclar.

## Al retomar ("continúa")

1. Leer los **3 MVD** y los archivos recientes de `codigo\iter4\`.
2. Revisar `CONTEXT.md` §6 (estado hecho/pausa/WIP).
3. Una sola pregunta de aclaración si el estado es ambiguo, y proceder.

## Archivos clave

- `codigo\iter4\tracker.py` — pipeline de tracking (rigid body multi-marcador).
- `codigo\iter4\tracker_config.yaml` — config canónica (contexto Femto).
  `tracker_config_doctor.yaml` — contexto doctor (webcam global shutter +
  `data/globalshutter.yml`).
- `codigo\iter4\data\reference_dodecaedro_v2_calibrado.txt` — geometría del rigid body.
- `codigo\iter4\data\StylusTipToDodecaedro_femto_dock.npy` — calibración de punta vigente.
- `documentos\MANUAL_simplificado.md` — runbook operativo paso a paso
  (⚠ pendiente reapuntar de la config webcam a `tracker_config.yaml`).
