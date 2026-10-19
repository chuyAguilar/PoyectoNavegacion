# memory.md — estado de hoy

_Actualizado: 2026-10-19._

Spec activo: ningún spec activo

## Dónde estamos

- Se está montando el método de trabajo (ADR-020) por etapas. **Etapa 1** (constitución, `CLAUDE.md`, este archivo, BACKLOG, plantilla de spec, `settings.json`) escrita el 2026-10-19, pendiente del commit del autor.
- Lo siguiente: **etapa 2** (agentes `direccion`, `planificacion`, `desarrollo`, `pruebas`; skills `planear`, `fase`, `cerrar-fase`; `docs/PRUEBAS.md`). Después, el **spec 001 · limpieza y orden del repo** (BACKLOG B01–B06).
- El autor tiene en mente una meta concreta para el repo que todavía no ha contado: va después del orden.
- Último commit de código: `7ac5a43` (brief-02, GUI M1–M5, 2026-08-13). Sin cambios de código desde entonces.

## Estado técnico (resumen; el detalle está en `docs/CONTEXT.md` §6)

- Vía activa: registro paired-point. Contexto principal = Femto Bolt RGB (`tracker_config.yaml`, Marker0 80 mm); contexto doctor = webcam global shutter (`tracker_config_doctor.yaml`, Marker0 60 mm).
- Geometría vigente: `codigo/iter4/data/reference_dodecaedro_v2_calibrado.txt` (IDs 3–13, 14.6 mm, 1.26 px). Punta vigente: `StylusTipToDodecaedro_femto_dock.npy` (~1.8 mm de spread), **no versionada** (B03).
- Métricas de referencia: RMS de registro 2.80 mm (iter 3), 3.46 mm (iter 1).

## La suite

- `codigo/tests/`: 3 archivos. **Rota**: los 3 fallan al importar (`No module named 'calibrar_rigid_body'`); buscan los scripts en `codigo/` y el código vive en `codigo/iter4/`. 0 pruebas corren; la colección tarda ~3.4 s (8 s en total). B02.
- Todavía no hay comprobación de «no cambió». La acordada: suite + replay sobre un dataset grabado (p.ej. `captura_ba.npz`), sin cámara. B02.

## Decisiones del autor de este arranque (2026-10-19)

- Los datos de paciente (DICOM en `herramientas/A/`, `202 AXIAL.nrrd`) siguen en el árbol y en el historial: el repo lo usan médicos (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6). Lo demás puede cambiar.
- No hay más carpetas privadas.
- Modelos por papel: dirección y planificación con opus y esfuerzo medio; desarrollo con opus y esfuerzo alto; pruebas con sonnet.

## Pendientes del autor

- Commit de la etapa 1.

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
