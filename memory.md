# memory.md — estado de hoy

_Actualizado: 2026-10-19._

Spec activo: `specs/001-limpieza/`

## Dónde estamos

- Se está montando el método de trabajo (ADR-020) por etapas. **Etapa 1** commiteada (`8f398da`). **Etapa 2** (agentes `direccion`, `planificacion`, `desarrollo`, `pruebas`; skills `planear`, `fase`, `cerrar-fase`; `docs/PRUEBAS.md`) commiteada (`edb9aa0`).
- **Meta 001 · limpieza y orden del repo** (BACKLOG B01–B06): plan autorizado el 2026-10-19. **Fase 1 · suite y replay: hecha el 2026-10-19, pendiente del commit del autor.** Lo siguiente: fase 2 · respaldo de la punta (B03; la dirección escribe el ADR-021). La **etapa 3** (hooks) queda para cuando haga falta.
- Línea base de «no cambió» (fase 1): 110 pruebas, 88 pasan, 22 `xfail`; replay 302 frames, 275 con pose, mediana 4 markers, 0.0 mm/0.0°; selftest del panel rc 0 con perfil `tracker_config.yaml` (7 semáforos, `apto_tracker=SI`); punta más reciente de `iter4/data/`: `StylusTipToDodecaedro_femto_dock.npy`. Los números de la fase 3 del plan (102/91/11) parten de la estimación vieja: con los reales son 100 recogidas, 78 pasan, 22 `xfail`.
- Hasta la etapa 3, cada papel lo limitan su lista de `tools` y su texto; `settings.json` niega commit, push y los datos de paciente para todos.
- El autor tiene en mente una meta concreta para el repo que todavía no ha contado: va después del orden.
- Último commit de código: `7ac5a43` (brief-02, GUI M1–M5, 2026-08-13). Sin cambios en `codigo/iter4/` desde entonces; la fase 1 solo toca `codigo/tests/`, `codigo/pytest.ini` y `.gitignore`.

## Estado técnico (resumen; el detalle está en `docs/CONTEXT.md` §6)

- Vía activa: registro paired-point. Contexto principal = Femto Bolt RGB (`tracker_config.yaml`, Marker0 80 mm); contexto doctor = webcam global shutter (`tracker_config_doctor.yaml`, Marker0 60 mm).
- Geometría vigente: `codigo/iter4/data/reference_dodecaedro_v2_calibrado.txt` (IDs 3–13, 14.6 mm, 1.26 px). Punta vigente: `StylusTipToDodecaedro_femto_dock.npy` (~1.8 mm de spread), **no versionada** (B03).
- Métricas de referencia: RMS de registro 2.80 mm (iter 3), 3.46 mm (iter 1).

## La suite

- `codigo/tests/`: **en verde** desde la fase 1 (2026-10-19). 110 pruebas: 88 pasan, 22 `xfail(strict=True)` desfasadas (B17); ~6 s de pared (3.7 s de pytest). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`.
- Comprobación de «no cambió»: la suite + el replay (`tests/test_replay.py`, recorte `tests/data/replay_v2_femto.npz` contra `replay_v2_femto_referencia.npz`) + `panel.py --selftest` (`tests/test_gui_headless.py`). Detalle en `docs/ARCHITECTURE.md` §6.
- La referencia del replay depende del sha256 de `reference_dodecaedro_v2_calibrado.txt` y de `min_markers` de `tracker_config.yaml`: si cambian, el test lo dice; se regenera solo a propósito (`replay_util.py referencia ... --sobrescribir`).

## Decisiones del autor de este arranque (2026-10-19)

- Los datos de paciente (DICOM en `herramientas/A/`, `202 AXIAL.nrrd`) siguen en el árbol y en el historial: el repo lo usan médicos (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6). Lo demás puede cambiar.
- No hay más carpetas privadas.
- Modelos por papel: dirección y planificación con opus y esfuerzo medio; desarrollo con opus y esfuerzo alto; pruebas con sonnet.

## Pendientes del autor

- Commit de la fase 1 · suite y replay (título y `git add` en `Claude outputs/fases/001/fase-1.md`). Incluye `specs/001-limpieza/` y los cambios previos de `memory.md`; `.claude/settings.json` queda fuera.
- Decidir si B17 (22 pruebas en `xfail`, 8 del BA) sube de prioridad; y B19/B20 (alta), que vienen del plan.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`: el autor a veces trabaja desde otra carpeta y desde Git Bash, donde `\` se come la ruta (2026-10-19).

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
