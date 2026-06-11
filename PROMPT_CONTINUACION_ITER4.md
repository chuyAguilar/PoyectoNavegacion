# Prompt de continuación — Iter 4 surgical navigation (MIRAI / PoyectoNavegacion)

> Pegá este mensaje completo como primer turno del nuevo chat. Está pensado para que el nuevo agente arranque sin necesidad de preguntas adicionales.

---

## 0. Idioma y estilo de trabajo

- Respondeme en **español**.
- Sé **directo y honesto**, incluso con la incertidumbre.
- Cuando algo no funcione, no te disculpes excesivamente — andá al diagnóstico y a la solución.
- **Validá cuantitativamente** cada paso. "Se ve bien" no es criterio de éxito.
- **Una cosa a la vez** cuando debuguemos. Nada de cambiar tres variables y rezar.
- Si un escript es no-trivial, **mostrame progreso paso a paso** (verbose=2 en scipy, prints intermedios). No te quedes mudo.

## 1. Qué es este proyecto

Sistema de **navegación quirúrgica óptica** para cirugía ortopédica de columna. Trackea instrumentos y la anatomía del paciente con marcadores ArUco y visualiza coherencia espacial en 3D Slicer (similar a Perk Lab / IGSTK).

Soy **Dr. Milton (Aguilar)**, médico, no developer pro. Manejo Python a nivel intermedio. Necesito que me expliques las decisiones técnicas, no que las asumas.

### Hardware actual (iter 4)

- Cámara **Orbbec Femto Bolt** (ToF + RGB 4K). Reemplazó la webcam SVPro de iter 1-3.
- Dodecaedro impreso 3D con 11 marcadores ArUco:
  - TOP: ID **170**, marcadores 13.4 mm, arista del dodecaedro 17.5 mm.
  - Anillo superior: IDs [171, 172, 173, 174, 175].
  - Anillo inferior: IDs [176, 177, 178, 179, 180].
- Marker individual del paciente: ID **0**, tamaño **80 mm**.
- Phantom impreso del L1-L5 + sacro segmentado del CT del paciente.

### Iteraciones

- Iter 1: prototipo inicial con webcam. Cerrada. Métricas: 28 FPS, registro RMS 3.46 mm.
- Iter 2: auditoría de código + bundle adjustment + pivote calibrado. Cerrada.
- Iter 3: navegación tomográfica completa — cortes de CT siguen al stylus en tiempo real. Cerrada. RMS 2.80 mm.
- **Iter 4 (ACTUAL)**: integrar Femto Bolt para usar depth + RGB y bajar RMS a <1.5 mm. **EN CURSO.**

## 2. Estructura del proyecto

```
C:\Dev\Dr.Milton\PoyectoNavegacion\
├── CLAUDE.md                      # instrucciones para Claude (ya leídas)
├── codigo\
│   ├── .venv\                     # virtualenv (Python 3.x, pyorbbecsdk2 instalado)
│   ├── requirements.txt           # dependencias
│   ├── iter4\                     # ← TRABAJO ACTUAL
│   │   ├── camera_backend.py
│   │   ├── tracker.py
│   │   ├── tracker_config.yaml
│   │   ├── captura_calibracion.py
│   │   ├── calibrar_rigid_body.py
│   │   ├── medir_sigma_depth.py
│   │   ├── leer_calibracion_femtobolt.py
│   │   ├── generar_reference_dodecaedro.py
│   │   ├── hello_femtobolt.py
│   │   ├── test_backends.py
│   │   └── data\
│   │       ├── reference_dodecaedro.txt           # teórico (semilla del BA)
│   │       ├── reference_dodecaedro_calibrado.txt # post-BA (todavía bootstrap)
│   │       ├── smoke_captura.npz                  # dataset 30s smoke test
│   │       └── femtobolt_calibration.yml          # K1+K2 de fábrica
│   ├── historico\
│   │   └── iter3\                 # snapshot intacto de iter 3
│   └── Log\
├── documentos\auditoria_iter2\    # auditorías técnicas
└── stl\                           # archivos de impresión 3D
```

**Workspace folder en Cowork**: `C:\Dev\Dr.Milton\PoyectoNavegacion`.

## 3. Skills que tenés disponibles y debés leer ANTES de tocar nada

Si estás en Cowork (Claude Code), tenés 3 skills críticas:

1. **`surgical-nav-project-context`** — contiene mi setup específico, archivos, decisiones históricas. LEÉ ESTA PRIMERO.
2. **`surgical-navigation-aruco`** — conocimiento técnico ArUco, IPPE_SQUARE, BA, ambigüedad planar.
3. **`slicer-igt-workflow`** — 3D Slicer + SlicerIGT, paired-point registration, transform hierarchies.

Si no tenés acceso a skills, lee directamente:
- `CLAUDE.md` en la raíz del proyecto.
- `documentos\auditoria_iter2\` (especialmente `01_mapa_del_flujo.md`, `03c_auditoria_calibrar_rigid_body.md`, `06_workflow_slicer.md`).

## 4. Memorias críticas

El sistema de memoria persiste lecciones aprendidas. Las relevantes para iter 4 son:

| Memoria | Tema |
|---|---|
| `iter3-navegacion-tomografica-completada` | RMS 2.80, jerarquía Slicer, Observer Python (no Transform Processor) |
| `pyorbbecsdk2-paquete-renombrado-pypi` | Usar `pyorbbecsdk2`, NO `pyorbbecsdk` (v1.3.2 está rota en Windows) |
| `aruco-tuning-iter4-y-filtro-z-negativo` | DetectorParameters tuneados + filtro tvec[2]<=0 (subió detección 3→6 markers/pose) |
| `sigma-depth-femtobolt-empirico` | **σ_3d empírico = 4.5 mm a 67 cm** (99% espacial, 1% temporal). Usar 5.0 como default en el BA. |
| `ancla-rotacional-ba` | El ancla del BA tiene centro fijo pero rvec libre. Sin esto el pivote se rompe. |
| `pyigtl-bloquea-sin-cliente` | tracker.py se cuelga si Slicer no está conectado. Conectar Slicer ANTES. |
| `topologia-real-dodecaedro` | Para iter 2 el anillo inferior estaba rotado 1 pos. **Para iter 4 hay que verificar la topología REAL.** |
| `bug-critico-np-save-trunca-windows` | Usar `np.savez_compressed` y verificar post-escritura |

## 5. Estado al cierre de la sesión anterior

### Hecho (NO hay que rehacer)

- **K3 completo**: tracker.py refactorizado para Femto Bolt con `camera_backend` (webcam | femtobolt), detector tuning, filtro Z<0, solvePnPGeneric.
  - Mejora medida: 3-4 → **5-6 markers/pose**, poses espejadas eliminadas, FPS estable 17.
- **K4.1**: `iter4/captura_calibracion.py` refactorizado, muestrea depth en cada corner detectado.
- **K4.2 smoke test**: 1287 frames útiles, 100% con depth, **50/55 pares únicos**, todos los markers cubiertos.
- **K4.2.5**: σ_3d empírico medido = 4.5 mm. Default en el BA: **5.0 mm**.
- **K4.3**: `iter4/calibrar_rigid_body.py` refactorizado con residuos 2D + 3D mixtos. 731 líneas, SYNTAX OK, CLI funcionando.

### Pendiente (PRÓXIMOS PASOS)

| ID | Tarea | Comando |
|---|---|---|
| **K4.0** | Commit cierre de K3. Hay un `.git\index.lock` huérfano que limpiar primero. | Ver §6 abajo |
| **K4.4** | Correr captura larga (90 s) + BA real. Producir `reference_dodecaedro_calibrado.txt` REAL. | `python iter4\captura_calibracion.py --duracion 90` y después `python iter4\calibrar_rigid_body.py` |
| **K4.5** | Análisis Procrustes vs teórico. Confirmar rotación rígida sin deformaciones. | Por escribir |
| **K5** | Refactor `test_pivote.py` → `iter4/test_pivote.py` con depth directo (3D sphere fit). | Por escribir |
| **K6** | Validación cuantitativa iter 4 vs iter 3: RMS paired-point objetivo <1.5 mm. | Slicer |

## 6. Commit pendiente — limpiar git lock antes

En la sesión anterior intenté `git pull` desde el sandbox Linux y dejó un lock huérfano que el usuario en Windows no pudo limpiar. Pasos exactos:

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion

# 1) Borrar locks
Remove-Item .git\index.lock -ErrorAction SilentlyContinue
Remove-Item .git\objects\maintenance.lock -ErrorAction SilentlyContinue
Get-ChildItem .git -Recurse -Filter "*.lock" | Select-Object FullName  # debe estar vacío

# 2) Flujo normal
git pull --ff-only
git add -A
git commit -m "iter4: integracion Femto Bolt + reorganizacion historico" -m "
- Iter 3 archivado: codigo/* -> codigo/historico/iter3/
- requirements.txt: nuevas dependencias (pyorbbecsdk2 entre otras)
- iter4/camera_backend.py: abstraccion webcam | femtobolt
- iter4/hello_femtobolt.py + test_backends.py: smoke tests
- iter4/leer_calibracion_femtobolt.py: K1+K2 de fabrica via SDK
- iter4/generar_reference_dodecaedro.py: nuevos defaults (IDs 170-180, edge 17.5mm, marker 13.4mm)
- iter4/captura_calibracion.py: refactor con depth en corners
- iter4/medir_sigma_depth.py: sigma_3d empirico = 4.5 mm
- iter4/calibrar_rigid_body.py: BA con residuos 2D+3D mixtos
- iter4/tracker.py: backend abstraction + detector tuning + filtro Z<0 + solvePnPGeneric
- iter4/tracker_config.yaml: seccion markers.detector + camera_type: femtobolt
- data/femtobolt_calibration.yml: calibracion de fabrica leida del SDK
- stl/: nuevo dodecaedro 15mm + pentaedro

Mejoras medidas iter 3 -> iter 4 (mismo setup):
  promedio markers/pose: 3-4 -> 5-6
  poses con z<0 (espejadas): ~3%/frame -> 0
  sigma_3d empirico: 4.5 mm @ 67 cm
  FPS estable: 17"
git push
```

## 7. K4.4 — comandos para correr cuando esté lista la cámara

```powershell
cd C:\Dev\Dr.Milton\PoyectoNavegacion\codigo
.\.venv\Scripts\activate

# Captura larga para BA (90s)
python iter4\captura_calibracion.py --duracion 90 --output iter4\data\captura_ba_femtobolt.npz

# BA con defaults (sigma_2d=1.0 px, sigma_3d=5.0 mm, ancla=170, marker_mm=13.4)
python iter4\calibrar_rigid_body.py
```

### Qué buscar en el output del BA

```
[INFO]   has_depth (del .npz): True, use_depth (CLI): True
[INFO]   Residuos: ~50000 2D + ~25000 3D = ~75000 total
[INFO]   RMSE inicial 2D: ~3-5 px
[INFO]   RMSE inicial 3D: ~10-30 mm
[STATS]  RMSE 2D: 3-5 -> <1.0 px      ← objetivo principal
[STATS]  RMSE 3D: 20 -> <5 mm          ← objetivo secundario
[STATS]  Desplazamientos: max <5 mm    ← geometría sin deformaciones
```

### Banderas de problema (qué hacer en cada caso)

- **RMSE 2D final > 2 px**: pose inicial mala o problema en datos. Revisar % de frames válidos.
- **RMSE 3D final > 10 mm**: sigma_3d muy optimista. Subir a 7 mm con `--sigma-3d 7.0` y re-correr.
- **Desplazamiento centro > 10 mm**: BA destruyó la geometría (problema observado en iter 1). Revisar topología con `calibrar_topologia.py` (está en historico/iter3/).
- **BA no converge** (status < 1): bajar `--max-frames 500` y subir `--max-nfev 500`.

## 8. Trampas conocidas — léelas ANTES de modificar archivos

1. **File truncation con Edit/Write**: el archivo se trunca silenciosamente a veces. SIEMPRE validá con `wc -l` y `python -m py_compile <archivo>` después de editar. Si truncó, reconstruir con `cat >> archivo << 'EOF' ... EOF`.
2. **Null bytes con heredoc**: si el archivo tiene padding nulo del Write previo, el append por bash genera bytes nulos en el medio. Detectarlos con `grep -c $'\x00' <archivo>` o `hexdump`. Limpiar con `raw.replace(b'\x00', b'')`.
3. **Git lock huérfano**: si corres `git pull` desde Linux/WSL sobre un repo en NTFS, puede dejar `.git/index.lock`. Limpiar como en §6.
4. **Femto Bolt enfoque fijo**: 0.5-5 m. Si ponés el dodecaedro a <30 cm, va a estar borroso. Distancia óptima: **50-70 cm**.
5. **pyigtl bloquea sin Slicer**: tracker.py se cuelga en frame 1 si Slicer no está conectado al puerto 18944. Conectar Slicer ANTES.
6. **DodecaedroToMarker0 con Transform Processor**: NO usar Transform Processor de SlicerIGT, no auto-actualiza. Usar Observer Python (script en memoria `iter3-navegacion-tomografica-completada` §J3).
7. **Marker individual size_mm en config**: el `marker_mm: 13.4` del rigid body es DISTINTO del `size_mm: 80.0` del marker 0 individual.

## 9. Convenciones de código

- Scripts Python en `C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\iter4\`.
- venv activable con `.\.venv\Scripts\activate`.
- Comentarios en español cuando explican decisiones, inglés en código.
- Outputs con nombres descriptivos + metadata (sha256, versiones, fecha UTC).
- Verbose=2 en scipy least_squares para que muestre iter por iter.

## 10. Lo que quiero que hagas ahora

1. **Confirmá que entendiste leyendo**:
   - `CLAUDE.md` en `C:\Dev\Dr.Milton\PoyectoNavegacion\`.
   - Las memorias listadas en §4 (si tenés acceso al sistema de memoria persistente).
   - El skill `surgical-nav-project-context` si está disponible.
   - Los archivos en `C:\Dev\Dr.Milton\PoyectoNavegacion\codigo\iter4\` para entender el estado.
2. **Reportame un resumen breve** (no más de 10 líneas) de:
   - El estado actual del proyecto según vos lo entendiste.
   - Cuál es el próximo paso concreto.
   - Si hay alguna duda crítica sobre la matemática del BA mixto 2D+3D, preguntámela ANTES de seguir.
3. **Esperá mi confirmación** antes de modificar archivos o correr scripts en mi máquina.

Una vez confirmado, seguimos con el commit (K4.0) y después K4.4 (correr el BA real con captura de 90 s).

Gracias.
