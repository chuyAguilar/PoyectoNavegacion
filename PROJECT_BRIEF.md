# Project Brief — Dr. Milton's Surgical Navigation System

**Copy this as the "Project Instructions" when creating the new Project in Cowork.**

_Última actualización: 2026-06-15 (iteración 4 en curso)._

---

## Project Overview

Sistema de navegación quirúrgica óptica para cirugía ortopédica de columna. El
sistema trackea instrumentos e anatomía del paciente con marcadores ArUco y una
cámara, y visualiza la coherencia espacial en 3D Slicer (similar a Perk Lab /
Navident / Brainlab).

El objetivo: que un modelo 3D del hueso del paciente (segmentado de su CT)
aparezca alineado con el hueso físico, de modo que al mover un stylus trackeado
se vea en tiempo real dónde está su punta respecto al modelo y a los cortes
tomográficos.

## Hardware (iteración 4)

- **Cámara Orbbec Femto Bolt** (ToF depth 640×576 + RGB 1920×1080 @ 30 FPS).
  Reemplazó a la webcam SVPRO de iter 1-3. Enfoque fijo 0.5-5 m → distancia de
  trabajo 50-70 cm. NO tiene D2C por hardware: alineación depth-color por
  software (AlignFilter del SDK, verificada correcta).
- **Stylus dodecaedro**: dos versiones.
  - Actual en uso (iter 4): impreso, 11 markers ArUco pegados, IDs 170-180,
    arista 17.5 mm, marker 13.4 mm. Punta roscada (problemática, ver abajo).
  - **NUEVO stylus 100% impreso** (`stl/stylus_impreso/`): markers MODELADOS en
    el CAD (geometría exacta, sin pegado), IDs 181-191, arista 20 mm, marker
    16 mm en relieve multicolor, punta cónica + esfera r=1 mm autocentrante,
    mango de 150 mm. Recién impreso (2026-06-15).
- **Phantom L1-L5 + sacro** impreso 3D, segmentado del CT del paciente.
- **Marker individual del paciente**: ID 0, 80 mm.
- **Placas de calibración impresas** (`stl/placa_calibracion/`, `stl/placa_dock_v3/`).
- Caja de luz Puluz (OJO: solo para RGB; el depth NO se captura dentro, ver abajo).

## Software Stack

- Python 3.11 + OpenCV 4.13 + scipy + pyigtl + **pyorbbecsdk2** (NO el viejo
  pyorbbecsdk 1.3.2, roto en Windows).
- 3D Slicer 5.4 + SlicerIGT (visualización, registro paired-point).
- OpenIGTLink (puerto 18944). NO enviar video (mata el FPS).

## Iteraciones

- **Iter 1** (webcam, cerrada): prototipo. 28 FPS, pivote std 1.7 mm,
  registro RMS 3.46 mm.
- **Iter 2** (cerrada): auditoría de código + bundle adjustment + pivote
  calibrado.
- **Iter 3** (cerrada): navegación tomográfica completa — los cortes de CT
  siguen al stylus en tiempo real. RMS 2.80 mm.
- **Iter 4 (ACTUAL)**: integrar Femto Bolt (depth + RGB) y bajar el RMS a
  <1.5 mm. EN CURSO.

## Estado actual de iteración 4 (2026-06-15)

**Hecho y validado:**
- `tracker.py` refactorizado para Femto Bolt (abstracción de backend
  webcam|femtobolt, detector tuneado, filtro z<0, solvePnPGeneric). Detección
  subió de 3-4 a 5-6 markers/pose.
- **Bundle adjustment iter 4 cerrado**: RMSE 2D 0.78 px, geometría intacta. El
  `jac_sparsity` se conectó a least_squares (tr_solver lsmr) — sin esto el
  Jacobiano denso (~13 GB) congelaba la máquina. Producto:
  `data/reference_dodecaedro_calibrado.txt` real.
- **Topología real del dodecaedro** detectada por reproyección (ambos anillos
  rotados sup+2/inf+3 vs teórico).

**Diagnóstico depth (decisión: usar BA solo-2D por ahora):**
- **Multipath ToF en la caja de luz**: el depth lee +57 mm de bias DENTRO de la
  caja blanca cerrada (rebotes IR), −10 mm fuera. **Las capturas con depth se
  hacen SIEMPRE fuera de la caja.**
- La alineación SW depth→color del SDK es correcta (verificada contra alineación
  manual con calibración de fábrica). El depth queda como línea de trabajo
  aparte; el pipeline avanza con residuos 2D.

**Calibración del tip (problema activo → solución en marcha):**
- El pivote clásico NO reproduce con la cámara lateral del Femto Bolt (no se
  puede ver el dodecaedro desde arriba como en iter 1-3): el "cono" sale plano,
  la esfera queda mal condicionada, y la punta ROSCADA del stylus actual no
  asienta en un punto repetible (sesiones difieren 5 mm, spread 3-6 mm).
- Migramos a **calibración template/divot** (el método de Brainlab/Navident):
  - `stl/placa_calibracion/` (v2): placa con marker ID 1 en relieve + 3 divots
    cónicos de posición conocida. Toca un divot quieto, sin técnica.
  - `stl/placa_dock_v3/`: placa **dock** con marker ID 2 + encaje cónico/V para
    el stylus NUEVO. El stylus se ENCAJA (pose totalmente definida por
    geometría); se rota el conjunto frente a la cámara. Objetivo: calibración
    de pivote más fácil, rápida y precisa, sin factor humano.
  - Script: `iter4/calibrar_tip_divot.py` (modos `--divot A/B/C` y `--divot DOCK`).
- El cupón de prueba del stylus nuevo detectó 77% en verde (patrón OK); se
  imprime en NEGRO mate para >95% de detección.

## Estructura del proyecto

```
C:\Dev\Dr.Milton\PoyectoNavegacion\
├── CLAUDE.md, PROJECT_BRIEF.md
├── codigo\
│   ├── .venv\
│   ├── iter4\                    # ← TRABAJO ACTUAL
│   │   ├── camera_backend.py     # webcam | femtobolt
│   │   ├── tracker.py
│   │   ├── calibrar_rigid_body.py        # BA 2D(+3D) con sparsity
│   │   ├── captura_calibracion.py
│   │   ├── calibrar_tip_divot.py         # calibración divot/dock
│   │   ├── test_pivote.py                # pivote clásico (legacy)
│   │   ├── test_alineacion_d2c.py        # diagnóstico depth
│   │   ├── test_deteccion_marker.py      # validar markers impresos
│   │   └── data\                         # reference_*, capturas, calibraciones
│   └── historico\iter3\          # snapshot intacto de iter 3
├── stl\
│   ├── stylus_impreso\           # dodecaedro CAD + mango 150 + reference
│   ├── placa_calibracion\        # placa divot v2 (marker ID 1)
│   └── placa_dock_v3\            # placa dock template (marker ID 2)
└── documentos\auditoria_iter2\
```

## Available Skills

1. **surgical-navigation-aruco**: ArUco, IPPE_SQUARE, rigid bodies, bundle
   adjustment, pivote, ambigüedad planar.
2. **slicer-igt-workflow**: 3D Slicer + SlicerIGT, jerarquías de transforms,
   paired-point registration.
3. **surgical-nav-project-context**: estructura de archivos, convenciones,
   estado actual, decisiones históricas de este proyecto.

## How I Work

- Comunicación **directa y honesta**, incluso sobre incertidumbre.
- Prefiero **español**.
- **Validación cuantitativa** en cada paso, no "se ve bien".
- Una variable a la vez al debuggear. Diagnóstico antes que fix.
- Scripts no triviales: mostrar progreso paso a paso (verbose), no quedarse mudo.
- A veces retomo a mitad de tarea — leé los archivos recientes para entender el
  estado.
- 3D Slicer corre aparte: no lo controlás directo, pero podés generar scripts
  para su consola Python, leer .mrml, o sugerir pasos de UI.

## Trampas conocidas (NO repetir)

- **Edit/Write truncan archivos** silenciosamente a veces. Validar con `wc -l`
  y `py_compile` después de editar; reconstruir si truncó.
- **Git lock huérfano** si se corre git desde el sandbox Linux sobre el repo
  NTFS. Limpiar `.git\index.lock` desde PowerShell.
- **Capturas con depth: SIEMPRE fuera de la caja de luz** (multipath).
- **pyigtl bloquea** si Slicer no está conectado: conectar Slicer ANTES.
- **Marcadores impresos: NEGRO mate**, no colores (contraste en escala de grises).

## Próximos pasos

1. Calibrar el tip del stylus nuevo con la placa dock v3 (`--divot DOCK
   --plate-id 2`). Objetivo: spread <1 mm, magnitud reproducible.
2. Validación cuantitativa iter 4 vs iter 3 en Slicer: RMS paired-point <1.5 mm.
3. (Aparte) Reintegrar el depth al BA una vez resuelto el bias residual fuera
   de la caja.
