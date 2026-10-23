# memory.md — estado de hoy

_Actualizado: 2026-10-23 (meta 002, fase 5 · Calibración de la cámara 2 hecha; falta el commit del autor)._

Spec activo: `specs/002-calibracion-camaras/`

## Dónde estamos

- Método de trabajo (ADR-020): etapas 1 (`8f398da`) y 2 (`edb9aa0`: agentes `direccion`, `planificacion`, `desarrollo`, `pruebas`; skills `planear`, `fase`, `cerrar-fase`; `docs/PRUEBAS.md`) commiteadas. La etapa 3 (hooks) queda para cuando haga falta; hasta entonces cada papel lo limitan sus `tools` y su texto, y `settings.json` niega commit, push y los datos de paciente.
- **Meta 001 · limpieza y orden del repo** (B01–B06): cerrada el 2026-10-19 (`2ce4b5d`, `8f33b3a`, `30437e4`, `e52f58c`; ADR-021); P01 «pasa». Detalle en `specs/001-*/` y `docs/PRUEBAS.md`.
- **Meta 002 · Calibración de las cámaras global shutter:** en curso (abajo).

## Estado técnico (el detalle está en `docs/CONTEXT.md` §6)

- Cámaras: dos SVPRO AR0234 global shutter, perfiles `tracker_config_gs1.yaml` (puerto 1, marca `focus` 500) y `tracker_config_gs2.yaml` (puerto 2, marca 332), 1280×960 MJPG 90 fps, `exposure_ms` 0.977, **las dos calibradas** (detector `sb`): gs1 `data/intrinsecos_gs1_1280x960.yml` (fase 4), gs2 `data/intrinsecos_gs2_1280x960.yml` (fase 5). **No girar ni sacar el lente de la cámara 2 sin recalibrar:** su punto principal queda 90 px sobre el centro (cy 390; B36). Los perfiles viejos (Femto `tracker_config.yaml`, `tracker_config_doctor.yaml`, `globalshutter.yml`) ya no se usan; la fase 6 archiva el doctor.
- Geometría vigente: `codigo/iter4/data/reference_dodecaedro_v2_calibrado.txt` (IDs 3–13, 14.6 mm, 1.26 px). Punta vigente: `StylusTipToDodecaedro_femto_dock.npy`, fuera de git; copia versionada (sha256 `a3c83203…5ebf`) en `iter4/data/respaldo_puntas/`.
- Métricas de referencia: RMS de registro 2.80 mm (iter 3), 3.46 mm (iter 1). P02 (cámara 1 a 640×480): 25.7 fps con ventana, sd z 1.38 mm a ~45 cm.

## La suite

- `codigo/tests/`: en verde. Desde la fase 5 de la meta 002: **444 pruebas, 422 pasan, 22 `xfail(strict=True)`** (B17), 7 avisos (B22); 19.5 s de pytest, 22–23 s de pared. Con `timeout 600 codigo/.venv/Scripts/python.exe -m pytest codigo/tests -q`. `pytest.ini` ya pone `-q` y con el doble `-q` no sale la línea de totales: para verla, `-o addopts="-p no:cacheprovider" -q`.
- «No cambió»: la suite + el replay (`tests/test_replay.py`, 0.0 mm/0.0°) + `panel.py --selftest` (`tests/test_gui_headless.py`). Detalle en `docs/ARCHITECTURE.md` §6. La referencia del replay depende del sha256 de la geometría y de `min_markers` de `tracker_config.yaml`; se regenera solo a propósito.

## Decisiones del autor

- Los datos de paciente siguen en el árbol y en el historial (ADR-019). Los agentes no los leen.
- Lo único que no se rompe nunca: la cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6).
- Modelos por papel: dirección y planificación con opus; desarrollo con opus, y Fable solo para «implementa» de las fases pesadas (ADR-022); pruebas con sonnet.
- **Rumbo (2026-10-20):** se rescata solo el tracking; punta, registro, navegación en Slicer y runbooks se rehacen mejorados. Solo valen los perfiles nuevos. Pendiente: el ADR que lo registre y qué significa para el principio 6.
- **Optimizar el tracker** se hará en la meta siguiente (B32: la ventana es el cuello).
- **Context7 obligatorio** para dirección, planificación y desarrollo sobre cualquier librería o tecnología.
- Cada meta, fase y entrada del BACKLOG va siempre con su nombre descriptivo junto al número; cada fase se presenta al autor antes de lanzarla.

## Meta 002 · Calibración de las cámaras global shutter

- Plan autorizado el 2026-10-20/21 (revisiones 1–3); respuestas P1–P21 en `clarify.md`. Casillas en `tasks.md`; su texto completo, en `resultados.md`.
- **Fase 1** (`e27049e`, `f1536cf`, `06619cf`), **Fase 2a** (`4b548cb`), **Fase 2b** (`0e14bc8`), **Fase 3 · Enfoque, exposición y medición de resolución × formato** (`e42061f`) y **Fase 4 · Calibración de la cámara 1 y comprobación de escala** (`1c19d0a`): hechas y commiteadas. **Fase 5 · Calibración de la cámara 2:** hecha el 2026-10-23, falta el commit del autor.
- Lo que dejaron: identidad por la ruta del puerto USB (las dos cuelgan de un hub; si cambia el hub, cambian las rutas); controles por DSHOW antes de abrir por MSMF; la marca `focus` solo es fiable escrita (`sondear_camara.py --fijar … --forzar`; `CONTEXT.md` §4.19); el código apaga la aceleración HW de MSMF (apertura 43–51 s → 0.4–0.5 s; §4.18; `tracker.py` a mano no, B28); `medir_modos.py`. Con la aceleración apagada la captura da ~90 fps en todos los modos, hasta 1920×1200. Con ventana el tracking da 19–25 fps en cualquier modo (el criterio de ≥ 88.2 no se cumplió; el autor eligió 1280×960, P16, y 0.977 ms, P15).
- **Fase 4, lo que dejó:** casilla del tablero 24.86 mm (P17); cámara 1 a 1280×960: RMS 0.167 px, control 0.146 px, cobertura 1.00, detector `sb` (gana al clásico: 0.146 frente a 0.181 de control), `data/intrinsecos_gs1_1280x960.yml` y el perfil gs1 apuntado a él; escala contra regla 5 de 5 pasos (media +0.18 mm en 80 mm, peor 0.47; la caja de luz no deja 200 mm); B33 cerrado (pose 99.8 % con la K real). Código: `calibrar_camara.py` (`--detector clasico|sb|ambos`, `--desde-vistas`), `comprobar_escala.py`, `medir_modos.py --intrinsecos`, y el panel con las medidas del calibrador, los dos detectores, «Comprobar escala con regla…» y oferta de apuntar el perfil (P18). Con la K real el campo es ~74°, no 84°.
- **Fase 5, lo que dejó:** cámara 2 calibrada desde el panel: RMS 0.154 px (23 vistas), control 0.150 px, cobertura 1.00, gana `sb` (clásico 0.204 / 0.202); fx 836.7, cy 389.8. Escala juzgada **por las medias** de las posiciones repetidas (P20): gs2 −0.37 mm, gs1 con topes +0.27 mm en 80 mm; la repetibilidad se guarda pero no juzga (B35). La calibración del panel es una **ventana de tres pasos sin campos** (P19, P21): 1 Enfocar lente, 2 Calibrar con tablero, 3 Comprobar escala con regla; tablero guardado en `data/tablero_calibracion.yaml` (24.86 mm), «Última» de cada paso y «Volver a medir el tablero…» con el texto del autor. Código en `gui/calibracion.py` (nuevo), `panel.py`, `comprobar_escala.py` (`--desde-json`). El autor la probó en vivo: «mucho mucho mejor».
- **Siguiente · Fase 6 · Comparación contra P02 y archivo de los perfiles viejos** (pesada): una sesión en vivo por cámara con Slicer conectado antes; sd z < 1.38 mm a ~45 cm; los dos transforms en Slicer; luego `git mv` de `tracker_config_doctor.yaml` y `data/globalshutter.yml` a `iter4/data/historico/`.
- ADR-016 decía que la SVPRO AR0234 era rolling shutter; es global shutter: ADR-023 al cerrar la meta (ADR-016 no se reescribe). ADR-024: un perfil por cámara física, identificada por su puerto USB.

## Pendientes del autor

- Meta 002: el commit de la Fase 5 · Calibración de la cámara 2; luego la Fase 6 · Comparación contra P02 y archivo de los perfiles viejos, en vivo con Slicer. Decidir si B35 (tope a la repetibilidad de la escala) entra antes de la fase 6. Los ADR-023, ADR-024 y el del rumbo los escribe la dirección al cerrar la meta. En la fase 6 (o antes si se toca el tracker): medir en vivo «Probar cámara» con la aceleración apagada por el código y el tracker desde el panel; B28.
- Decidir si B17 (22 pruebas en `xfail`) sube de prioridad; y B19/B20 (alta). B20 (Slicer carga la punta por fecha) sigue igual. B34 (las pruebas no deben poder abrir una cámara real aunque cambie un perfil; media) quedó abierto tras el incidente de la fase 4.
- Los commits se proponen con `git -C C:/Dev/OrtoMeta/PoyectoNavegacion …`, con barras `/` (el autor usa también Git Bash).

## Trampas de la sesión

- `.git` tiene 691 MB en objetos sueltos (0 packs) y un temporal basura (`.git/objects/ad/tmp_obj_*`): B13.
- `gh` no está instalado en esta máquina.
