# memory.md — estado de hoy

_Actualizado: 2026-10-22 (meta 002, fase 2b hecha con la sesión en vivo; pendiente de su commit)._

Spec activo: `specs/002-calibracion-camaras/`

## Dónde estamos

- Se está montando el método de trabajo (ADR-020) por etapas. **Etapa 1** commiteada (`8f398da`). **Etapa 2** (agentes `direccion`, `planificacion`, `desarrollo`, `pruebas`; skills `planear`, `fase`, `cerrar-fase`; `docs/PRUEBAS.md`) commiteada (`edb9aa0`).
- **Meta 001 · limpieza y orden del repo** (BACKLOG B01–B06): plan autorizado el 2026-10-19. Fase 1 · suite y replay: `2ce4b5d`. Fase 2 · respaldo de la punta (B03): `8f33b3a` (ADR-021). Fase 3 · movimientos (B01, B05): `30437e4`. Fase 4 · textos (B04, B06): `e52f58c`. **Cerrada el 2026-10-19:** B01–B06 en «Cerrados»; pruebas P01 sobre `e52f58c`, veredicto «pasa», con el snippet de Slicer verificado en vivo por el autor ([0.904, 5.471, −201.808] mm). Lo siguiente: la meta que el autor tiene en mente (spec 002). La **etapa 3** (hooks) queda para cuando haga falta.
- Línea base de «no cambió» desde la fase 3 (la fase 4 la mantiene): 100 pruebas, 78 pasan, 22 `xfail`; replay 302 frames, 275 con pose, mediana 4 markers, 0.0 mm/0.0°; selftest del panel rc 0 con perfil `tracker_config.yaml` (7 semáforos, `apto_tracker=SI`); el panel ve 2 perfiles (`tracker_config.yaml`, `tracker_config_doctor.yaml`; desde la fase 2b de la meta 002, 4 con `_gs1` y `_gs2`, y la fase 6 archiva el doctor); punta más reciente de `iter4/data/`: `StylusTipToDodecaedro_femto_dock.npy`.
- Fase 4: `PROJECT_BRIEF.md` y `briefs/` están en `docs/history/` (`git mv`, literales). Las rutas vivas dicen `C:\Dev\OrtoMeta\PoyectoNavegacion` (manuales, `codigo/readme.md`, 3 scripts de `femto_pruebas/`, cabecera de la punta vigente y de su respaldo); los históricos (`codigo/historico/`, `documentos/auditoria_iter2/`, `documentos/tecnicos/`, `docs/history/`) conservan las viejas (P5 = b).
- Hasta la etapa 3, cada papel lo limitan su lista de `tools` y su texto; `settings.json` niega commit, push y los datos de paciente para todos.
- Último commit de código: `7ac5a43` (brief-02, GUI M1–M5, 2026-08-13). La lógica de `codigo/iter4/` no ha cambiado desde entonces: la fase 3 solo mueve archivos y cambia una línea de docstring de `calibrar_rigid_body.py`; la fase 4 en `iter4/` solo cambia la ruta (texto) de la cabecera de la punta.

## Estado técnico (resumen; el detalle está en `docs/CONTEXT.md` §6)

- Vía activa: registro paired-point. Contexto principal = Femto Bolt RGB (`tracker_config.yaml`, Marker0 80 mm); contexto doctor = webcam global shutter (`tracker_config_doctor.yaml`, Marker0 60 mm).
- Geometría vigente: `codigo/iter4/data/reference_dodecaedro_v2_calibrado.txt` (IDs 3–13, 14.6 mm, 1.26 px). Punta vigente: `StylusTipToDodecaedro_femto_dock.npy` (~1.8 mm de spread), fuera de git en `iter4/data/`; su copia versionada (sha256 `a3c83203…5ebf`) está en `iter4/data/respaldo_puntas/`, fuera del glob de Slicer y de `estado.py` (fase 2). Si se recalibra la punta, el respaldo no se actualiza solo.
- Métricas de referencia: RMS de registro 2.80 mm (iter 3), 3.46 mm (iter 1).

## La suite

- `codigo/tests/`: **en verde** desde la fase 1 (2026-10-19). Desde la fase 3 de la meta 001, 100 pruebas: 78 pasan, 22 `xfail(strict=True)` desfasadas (B17), 8 avisos (B22). Desde la corrección de la fase 1 de la meta 002, 147: 125 pasan, 22 `xfail`. Desde la fase 2a, 212: 190 pasan, 22 `xfail`. Desde la fase 2b, 267: 245 pasan (55 nuevas, sin cámara), 22 `xfail`, 8 avisos; 5.7–5.8 s de pytest, ~9 s de pared (las pruebas de importación lanzan 11 procesos). `pytest.ini` ya pone `-q`: con el `-q` del comando no sale la línea de totales (`-rN` la da). Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`.
- Comprobación de «no cambió»: la suite + el replay (`tests/test_replay.py`, recorte `tests/data/replay_v2_femto.npz` contra `replay_v2_femto_referencia.npz`) + `panel.py --selftest` (`tests/test_gui_headless.py`). Detalle en `docs/ARCHITECTURE.md` §6.
- La referencia del replay depende del sha256 de `reference_dodecaedro_v2_calibrado.txt` y de `min_markers` de `tracker_config.yaml`: si cambian, el test lo dice; se regenera solo a propósito (`replay_util.py referencia ... --sobrescribir`).

## Decisiones del autor de este arranque (2026-10-19)

- Los datos de paciente (DICOM en `herramientas/A/`, `202 AXIAL.nrrd`) siguen en el árbol y en el historial: el repo lo usan médicos (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6). Lo demás puede cambiar.
- No hay más carpetas privadas.
- Modelos por papel: dirección y planificación con opus y esfuerzo medio; desarrollo con opus y esfuerzo alto; pruebas con sonnet.

## Meta 002 · Calibración de las cámaras global shutter

- Spec escrito el 2026-10-20 a pedido del autor, tras P02 (cámara 1: cadena pasa, calibración no concluyente; 25.7 fps; sd z 1.38 mm a ~45 cm). Decisiones del autor: ajustes de cámara fijos y automatizados; resolución elegida midiendo, la mayor con ≥ 60 fps de tracking; calibrar las dos, una por una; tablero impreso en 3D (STL en `Claude outputs/tablero/`, prueba 2×2 primero). La cámara 2 se prueba dentro de esta meta.
- Plan (6 fases, revisión 1) autorizado el 2026-10-20; respuestas P1–P8 en `clarify.md`.
- **Fase 1 · Sonda de controles, modos e identidad: hecha y commiteada** (`e27049e`, `f1536cf`, cierre `06619cf`). Modos MSMF MJPG: ~90 fps de 320×240 a 1280×960 en las dos, ~30 a 1920×1080/1200. Controles por DSHOW: 10 de 12 verificados, `auto_exposure` no verificable, `wb_temperature` rechazado; los ajustes persisten en la cámara. La serie `01.00.00` es igual en las dos. Enmienda del autor (`clarify.md`): umbral de la elección ≥ 90 fps de tracking con ventana.
- **Fase 2a · Identidad por puerto y controles por DSHOW, medidos con las dos cámaras: hecha y commiteada (`4b548cb`, 2026-10-21).** Sesión en vivo con el autor (`Claude outputs/fases/002/fase-2a-en-vivo.md`; reporte `fase-2a.md`). Identidad por la ruta del puerto 6 de 6: puerto 1 = `PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(11)#USB(3)`, puerto 2 = `…#USB(11)#USB(4)` (las dos cuelgan de un hub; si cambia el hub, cambian las rutas). Orden DSHOW = índice, 4 de 4. MSMF no pisa lo escrito por DSHOW (0 diferencias); escribir `exposure` desmarca el Auto de AMCap y muestra −8; la capa cuesta ~1.2 s. La marca en `focus` sirve (imagen igual; persiste; cám. 1 500, cám. 2 332): P13 = se usa. P14 no saltó. La cámara 2 está más desenfocada (nitidez 64.7 frente a 227): dato para la fase 3. Código nuevo: `ajustes_camara.py`; cambios en `camaras_uvc.py` y `sondear_camara.py`; el backend no se tocó.
- **Fase 2b · Perfiles por cámara: hecha (2026-10-22), pendiente del commit.** `camera_backend.py` abre la webcam por el puerto, lee la marca `focus` antes de escribir (si no coincide, para sin escribir), aplica los controles y comprueba el tamaño (pedido y `.yml`); perfiles `tracker_config_gs1.yaml`/`gs2` (640×480 MJPG 90 fps y exposición 3.906 ms, provisionales hasta la fase 3). Sesión en vivo (`Claude outputs/fases/002/fase-2b-en-vivo.md`): los seis puntos pasan, 4 de 4 y 2 de 2; la capa añade 2.6–3.0 s. **Hallazgos:** la aceleración HW de MSMF alarga la apertura de ~4 s a 43–51 s sin dar fps, y el código la apaga (`camaras_uvc`; `CONTEXT.md` §4.18; el tracker a mano no, B28); la marca `focus` de la cámara 2 saltaba mientras no se escribió: se escribió con `--fijar focus=332 --forzar` (§4.19). Al BACKLOG: B28, B29, B30. Sin medir en vivo: «Probar cámara» con la línea de la aceleración y el tracker desde el panel.
- **Siguiente · Fase 3 · Enfoque, exposición y medición de resolución × formato** (pesada). Los valores de los perfiles gs1/gs2 son provisionales; B25 pide que su sonda guarde cada modo al medirlo. La cámara 2 está más desenfocada (nitidez 64.7 frente a 227).
- **Rumbo del proyecto (autor, 2026-10-20):** se relevanta el proyecto y se mejora. De lo que hay se **rescata solo el tracking**; lo que va después (punta, registro paired-point, navegación en Slicer, runbooks) se rehará mejorado. Los perfiles anteriores (doctor, Femto) y `globalshutter.yml` ya no se usarán: solo los nuevos. No se distingue perfil del doctor y del autor. Pendiente: ADR que lo registre y qué significa para el principio 6.
- **Optimizar el tracker** se hará aunque se llegue a 60 fps (autor, 2026-10-20): candidata a la meta siguiente.
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología, actual o nueva (autor, 2026-10-20; en `.claude/agents/`). Context7 de la dirección: herramientas añadidas a `direccion.md`, efectivas al abrir una sesión nueva.
- Lo dicho: el primer paso no usa la Femto, sino cámaras global shutter SVPRO (sensor AR0234, 1920×1200, MJPEG hasta 90 fps, lente M12 de ~83–85°, UVC). Por ahora son 2. Probablemente sin calibrar. No se sabe si alguna es la de `data/globalshutter.yml` (640×480, contexto doctor). La resolución, que la decida el plan con medidas.
- A aclarar en el spec: ADR-016 dice que la SVPRO AR0234 era rolling shutter; la ficha (y el AR0234 de onsemi) dice global shutter. Si se confirma, ADR nuevo (ADR-016 no se reescribe). `calibrar_camara.py` existe pero su prueba con cámara sigue en B10.

## Pendientes del autor

- Meta 002, fase 2b: el commit (título y `git add` en `Claude outputs/fases/002/fase-2b.md`). Los ADR-023 y ADR-024 los escribe la dirección. En la fase 6 (o antes si se toca el tracker): medir en vivo «Probar cámara» con la aceleración apagada por el código y el tracker desde el panel; B28 (una línea en `tracker.py`).
- Decidir si B17 (22 pruebas en `xfail`, 8 del BA) sube de prioridad; y B19/B20 (alta), que vienen del plan. B20 (Slicer carga la punta por fecha) sigue igual tras la fase 4: el snippet aún elige por mtime.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/`: el autor a veces trabaja desde otra carpeta y desde Git Bash, donde `\` se come la ruta (2026-10-19).

## Para la etapa 3 (hooks)

- Regla del autor (2026-10-19): cada fase se le presenta con un título descriptivo y lo que hará, antes de lanzarla. Hoy está en `.claude/agents/direccion.md`; cuando haya hooks, ver si alguno la refuerza (un hook no puede revisar lo que se escribe en el chat; como mucho, recordarla).

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
