# PRUEBAS — lo que se probó

Lo escribe solo el agente de pruebas (principio 1; ADR-020), sobre HEAD commiteado y con el árbol limpio. Cada ronda añade una entrada al final; lo anterior no se reescribe. El detalle de cada ronda está en `Claude outputs/pruebas/<fase>/ronda.md`, fuera de git. Quien añade una entrada pone su línea en el índice.

## Índice

| # | Meta y fase | Commit probado | Fecha | Veredicto |
|---|---|---|---|---|
| P01 | Meta 001, fases 1–4 · limpieza y orden | e52f58c | 2026-10-19 | pasa |
| P02 | Cámara global shutter 1 · flujo actual con el perfil doctor | 6431bc6 | 2026-10-19/20 | cadena pasa; calibración intrínseca no concluyente |
| P03 | Meta 002 · calibración de las cámaras global shutter (sin cámara) | 2322553 | 2026-10-23 | pasa; 3 hallazgos menores |
| P04 | Meta 003 · Arquitectura y optimización del tracker (sin hardware) | 26e724e | 2026-10-26 | pasa |
| P05 | Meta 004 · Cómo funciona el tracker (sin hardware) | eceef59 | 2026-10-26 | pasa; 2 hallazgos bajos |

## Formato de una entrada

```
## P<NN> · Meta NNN, fase n · nombre de la fase
- Commit probado: <hash> · Fecha: AAAA-MM-DD
- Comprobaciones: | qué | cómo (suite, replay, en vivo) | resultado | número o evidencia |
- Fallos: pasos, lo esperado, lo obtenido, gravedad (alta, media, baja).
- Lo dudoso: lo que no se pudo comprobar y por qué.
- En vivo: los números del autor, si los hubo, y su fecha.
- Veredicto: pasa / pasa con reservas / falla.
```

## Antes del método

Las validaciones de las iteraciones 1–4 (RMS de registro 3.46 → 2.80 mm, BA 0.78 y 1.26 px, spread de la punta 1.04 y ~1.8 mm) están en `docs/CONTEXT.md` §6 y en los ADR de `docs/DECISIONS.md`; aquí no se copian.

## Rondas

## P01 · Meta 001, fases 1–4 · limpieza y orden del repo
- Commit probado: e52f58c · Fecha: 2026-10-19
- Comprobaciones:

| qué | cómo | resultado | número o evidencia |
|---|---|---|---|
| Suite | pytest | pasa | 100 recogidas, 78 pasan, 22 xfail, 0 fallos, 3.44 s |
| Replay | suite y aparte | pasa | 302 frames, 275 con pose, 0.0 mm, 0.0°; sin dataset, referencia o json, `pytest.fail` (no regenera; por lectura) |
| Respaldo de punta | git, sha256, mtime, estado.py | pasa | 2 archivos versionados; sha a3c83203…5ebf igual; el más reciente es `_femto_dock`; VERDE, sha 11b0846fc5b5d43f |
| Greps | git grep | pasa | rutas viejas vivas 0; 0 bytes en `iter4/data/` 0; nombres de los 10 scripts 1 (fallo 1) |
| Históricos literales | git grep, diff | pasa | 15 apariciones en 9 archivos; el diff solo añade `iter4_diagnosticos/` |
| Historia de movimientos | git log --follow | pasa | brief y config llegan a commits previos a la meta |
| GUI sin cámara | panel --selftest | pasa | rc 0, 6 VERDE y cámara GRIS, apto_tracker=SI; 2 perfiles |
| Cadena | git diff | pasa | `tracker.py` y `camera_backend.py` sin cambios; sin cambios en transforms ni puerto 18944 |
| BACKLOG y líneas | lectura, awk | pasa | B01–B06 cerrados, B17–B22 en índice, 0 líneas >2000 (fallo 2) |

- Fallos:
  1. Baja. `codigo/iter4/calibrar_rigid_body.py:17` nombra `medir_sigma_depth.py` (con la ruta nueva) en un comentario; no es una invocación, pero el grep da 1, no 0. Lectura de la dirección: es la mención permitida por el spec («salvo la que diga que se movió y adónde»); no es fallo.
  2. Baja. `docs/BACKLOG.md:160` (B02 cerrado) dice «110 pruebas: 88 pasan, ~6 s»; la suite real y `memory.md` dicen 100, 78 y ~3.4 s. Lectura de la dirección: era la cifra correcta al cerrar B02 en la fase 1; la suite cambió después.
- Lo dudoso: no se mutó código ni se borró la referencia del replay (comprobado por lectura).
- En vivo: snippet de Slicer del 2026-10-19: «Usando el tip mas reciente: StylusTipToDodecaedro_femto_dock.npy» y «OK: nodo creado». Traslación del nodo `StylusTipToDodecaedro` leída por el autor (2026-10-19, e52f58c, 3 decimales): [0.904, 5.471, −201.808] mm; coincide con lo esperado (el autor dictó 0.99 por error de tecleo y lo corrigió).
- Veredicto: pasa.

## P02 · Cámara global shutter 1 · el flujo actual con el perfil doctor
- Commit probado: 6431bc6 · Fecha: 2026-10-19/20 (sin cámara el 19; en vivo con el autor el 19/20)
- Alcance real: el autor paró al ver los transforms en Slicer. No se hizo precisión quieto, punta, pivote ni escala. Marker0 de 80 mm en la prueba en vivo (el perfil de la parte sin cámara decía 60 mm).
- Comprobaciones:

| qué | cómo | resultado | número o evidencia |
|---|---|---|---|
| Suite | pytest | pasa | 100 recogidas, 78 pasan, 22 xfail, 0 fallos, 3.34 s |
| Panel con el perfil doctor | panel --selftest | pasa | entorno, config, geometría (11 markers, IDs 3-13), intrínsecos, puerto VERDE; punta AMARILLO (cae en `_femto_dock`, 201.884 mm); cámara GRIS; apto_tracker=SI |
| Calibración declarada | lectura | pasa | `globalshutter.yml` declara 640x480; el perfil la apunta con 640x480, MSMF, MJPG |
| Dispositivo | en vivo | pasa | con la cámara 1 sola, Windows lista `Global Shutter Camera` (VID_32E4 PID_0234); source 0, MSMF, entrega 640x480 |
| IDs | en vivo, `identificar_ids.py` | pasa | se vieron 0 y 3-13, todos; hasta 4 caras del dodecaedro a la vez |
| Tracker a Slicer | en vivo | pasa | `Marker0ToTracker` y `DodecaedroToTracker` en Slicer, visibles en 3D; 1619 poses del dodecaedro, todas con 3 markers |
| FPS | en vivo, log del tracker | reserva | 145 promedios: media 25.7, mín 19.7, máx 30 (esperado 28-30); el autor leyó ~20.5 en la ventana |
| Jitter quieto | en vivo, últimas 60 poses | reserva | a ~45 cm: sd x 0.25, y 0.14, z 1.38 mm; rango z 6.3 mm (domina la profundidad); el autor lo vio con «bastante jitter» |
| Calibración intrínseca | en vivo | no concluyente | no se midió reproyección ni escala; imagen pixelada y lente M12 posiblemente desenfocado según el autor; se recalibra en la meta 002 |
| Liberar al cerrar | en vivo | pasa | el autor cerró la ventana por accidente; después, puerto 18944 sin conexiones y ningún python vivo |
| Precisión quieto x3, punta, pivote, escala, check 4.6 | en vivo | no hecho | decisión del autor |

- Fallos y hallazgos (sin pasos de reproducción mayores: se ven al usar el flujo):
  1. Media. Nada compara el tamaño del frame con `image_width`/`image_height` del `.yml`: `WebcamBackend` aplica K de 640x480 a lo que entregue MSMF. Si el modo no se fija, la pose sale mal sin aviso. (En esta ronda la sonda mostró 640x480, así que no se manifestó.)
  2. Media. FPS del tracker 25.7 de media (19.7-30) frente a 28-30 esperados; puede deberse a la exposición, la luz o la carga; no se aisló la causa.
  3. Media. Jitter en profundidad: sd z 1.38 mm a ~45 cm, rango 6.3 mm, con markers de pocos píxeles (K de fx ~425). Afecta a cualquier medida de punta.
  4. Media. Los ajustes de la cámara (exposición, etc.) se movieron a mano en ambas cámaras y no quedan registrados: la ronda no es reproducible en esas condiciones.
  5. Baja. «Probar cámara» (`sonda_camara.py`) abre sin fijar 640x480 ni MJPG: su `WxH` no es lo que usa el tracker.
  6. Baja. El panel solo lista perfiles versionados `iter4/tracker_config*.yaml`: un índice distinto de 1 obliga a editar uno versionado o crear un archivo en `iter4/`.
- Lo dudoso: no se sabe si `globalshutter.yml` es de esta unidad. Sin reproyección ni escala no se puede decir si K es buena. No se aisló la causa del FPS ni del jitter. El FPS medido es el del tracker, no el de la cámara sola.
- En vivo: números del autor en `Claude outputs/pruebas/camara-1/numeros_autor.md` y datos crudos en `en_vivo_datos/` (2026-10-19/20).
- Veredicto: cadena hasta Slicer con la cámara 1: pasa. Calibración intrínseca: no concluyente, se recalibra en la meta 002.

## P03 · Meta 002 · calibración de las cámaras global shutter (sin cámara)
- Commit probado: 2322553 · Fecha: 2026-10-23
- Comprobaciones:

| qué | cómo | resultado | número o evidencia |
|---|---|---|---|
| Suite | pytest | pasa | 444 recogidas, 422 pasan, 22 xfail, 0 fallos, 19.4 s (25.8 s de pared) |
| Selftest del panel | panel --selftest | pasa | rc 0; textos de la ventana de calibración y «Última:» leen los JSON |
| Cámara real en pruebas (B34) | búsqueda | pasa con reserva | create_backend/VideoCapture solo con doble o prohibido (comprobar_escala, calibrar_camara, sondear_camara); test_camera_backend construye backends con los perfiles reales pero sin abrir |
| Intrínsecos .yml | cv2.FileStorage | pasa | 1280x960; gs1 fx 849.94 fy 848.88 cx 603.56 cy 488.87; gs2 fx 836.72 fy 836.50 cx 628.56 cy 389.81; dist de 5 |
| Perfiles gs1/gs2 | lectura | pasa | puerto USB(3)/USB(4), focus 500/332, 1280x960 MSMF MJPG 90, 0.977 ms, calibration_file a su .yml |
| Escala --desde-json | script | pasa | gs1 +0.271 mm, gs2 -0.368 mm (cumple); --config junto a --desde-json se rechaza |
| Recalibrar gs2 --desde-vistas | script a temporal | pasa | sb 0.1540 / control 0.1500, clásico 0.2037 / 0.2021, gana sb; el .yml de data/ no cambió (hash) |
| Bordes | script | pasa | carpeta de vistas vacía o ausente, JSON de 0 bytes o ausente: rc 1 con mensaje, sin salida escrita |
| listar_perfiles | llamada | pasa | tracker_config, _gs1, _gs2 |
| Cadena | git diff 709a535..HEAD | pasa | tracker.py sin cambios; pyigtl con las mismas 8 menciones en tracker/estado/procesos (+1 en medir_modos); camera_backend: FemtoBolt, read() y get_intrinsics() sin tocar |
| Documentos | lectura | pasa con reserva | arranque 45 859 B (< 49 152); ninguna línea > 2 000; BACKLOG B34–B38 en el índice; B33 en Cerrados; memory.md 8 717 B |

- Fallos:
  1. Baja. Quedan nombres del perfil archivado sin ruta histórica: `estado.py:13`, `panel.py:23` e `identificar_ids.py:17` (docstrings/uso) y los diccionarios `estado.py:42`, `recetas.py:48` por nombre de archivo. Quien siga el ejemplo con `iter4/tracker_config_doctor.yaml` no lo encuentra. Los diccionarios son inertes (el panel ya no lista el perfil).
  2. Baja. `tracker_config_gs2.yaml` aún dice en un comentario «calibration_file vacio hasta la fase 5» y «Vacio hasta la fase 5…» mientras el campo ya apunta al .yml.
  3. Baja. En `tasks.md` la casilla de la fase 6 trae «Commit: —» aunque HEAD ya es su commit; el encargo esperaba seis casillas con commit (cinco lo tienen). Es el flujo normal (lo añade el cierre o la fase siguiente).
- Lo dudoso: B34 sigue abierto (nada impide que una prueba nueva abra una cámara real si se cambia un perfil); no se probó ninguna cifra en vivo (sd z, fps, enfoque), solo que lo commiteado coincide con lo registrado. B37 (alta) y el criterio de la cámara 1 no cumplido quedan como los dejó la fase 6.
- Veredicto: lo commiteado dice y hace lo que registran las fases 1–6; sin fallos de gravedad media o alta. Detalle: `Claude outputs/pruebas/002-meta/ronda.md`.

## P04 · Meta 003 · Arquitectura y optimización del tracker (sin hardware)
- Commit probado: 26e724e · Fecha: 2026-10-26
- Comprobaciones:

| qué | cómo | resultado | número o evidencia |
|---|---|---|---|
| Suite x2 | pytest | pasa | 555 passed, 0 avisos; 37.2 s y 32.9 s de pared (29.7 s la tercera) |
| Replay Marker0 | test_replay_marker0 | pasa | 8 passed, 1.84 s |
| Selftest del panel | panel --selftest (offscreen, utf-8) | pasa | rc 0; sin boton_vista_previa_*; tracker_argv = `-m tracker --config profiles\tracker_config_gs1.yaml --no-window --stop-stdin` |
| --help | 7 módulos `python -m` de CLAUDE.md §5 y readme | pasa | todos exit 0; identify_ids sin --timeout: exit 2 |
| Tracker sin Slicer | tracker --no-window --slicer-timeout 3 | pasa | hecho por el autor el 2026-10-26 sobre 26e724e, Slicer sin conector: «[ERROR] Slicer no se conecto al puerto 18944 en 3 s», «Servidor del puerto 18944 cerrado (0 envios)», exit=3, sin líneas [Webcam]; la dirección vio 18944 sin Listen y ningún tracker vivo |
| Banco igtl_rate (18950) | bench 90 Hz 10 s | pasa | sin timer 64.6 ráfagas/s (E1: 64.1), 1.39 msg/ráfaga; con --timer-1ms 86.7 ráfagas/s (E1: 87.7–88.6), 902/902 enviados |
| Docs | lectura | pasa | índices ADR hasta 031 y B54/B55 coinciden; memory.md 9 317 B; ninguna línea > 2 000; arranque 40 355 B |
| B55 | cálculo | pasa | 0.033/0.811=0.041, 0.034→0.042, 0.037→0.046, 0.030→0.037: coinciden con resultados.md; 40.28/0.811=49.7 mm; ADR-031 y BACKLOG coherentes |
| iter4 | git grep | pasa | no existe codigo/iter4/; lo que queda son docstrings de procedencia, rutas a historico/iter4 y `generated_by` de los .yml |

- Fallos:
  1. Resuelto (error mío de procedimiento, no del código). Lancé el punto 5 sin comprobar que Slicer estuviera cerrado: conectó, el tracker abrió la cámara y quedó en bucle (PIDs 14604 y 32120). Terminó después y la dirección confirmó que ya no existe.
  2. Baja. `docs/DECISIONS.md` dice «Última actualización: 2026-10-23» con ADR-026 a 031 de 2026-10-25/26.
- Lo dudoso: sin hardware no se comprobó nada en vivo. Cobertura en vivo de fases 7 a 8c según resultados.md; no vi hueco que exija en_vivo.md.
- Veredicto: lo commiteado coincide con lo registrado, sin fallos de gravedad media o alta. Veredicto final de la meta 003: pasa. Detalle: `Claude outputs/pruebas/003-meta/ronda.md`.

## P05 · Meta 004 · Cómo funciona el tracker (sin hardware)
- Commit probado: eceef59 · Fecha: 2026-10-26
- Comprobaciones:

| qué | cómo | resultado | número o evidencia |
|---|---|---|---|
| Suite x2 | pytest | pasa | 618 passed, 0 avisos; 40.1 s y 39.9 s (35.2 s con -rA) |
| Replay Marker0 | test_replay_marker0 | pasa | verde; además `explain_pose` repite 0.0 mm / 0.0° y esquinas a 0.000000 px |
| Selftest del panel | panel --selftest (offscreen, utf-8) | pasa | rc 0; sin botón «Probar cámara»; camara_antes=GRIS, tras rc0 VERDE (89.9 fps), tras rc1 ROJO |
| Cadena sin cambios | git diff --stat 63bbdd8 HEAD (tracker, camera, vision, transport, profiles, data, slicer) | pasa | vacío |
| §9 fiel al código | 14 referencias a mano; números de §9.2/§9.4 contra perfil, .yml y resultados.md de la 003 | pasa | fx/fy/cx/cy, dist, RMS 0.167/0.154 y criterio 0.5, modo 1280x960 MJPG 90, ventanas 5–35/10, ±40 mm, 61.7/55.2, 89.9/88.8, 40.28, a≈0.12/0.33: coinciden; ver fallo 1 |
| Ejemplo §9.3 | explain_pose con el comando de §9.3, salida en Claude outputs | pasa | bloque Markdown idéntico al de ARCHITECTURE.md; PNG idéntico byte a byte (sha 19FB38E7…) |
| --help | export_map y explain_pose | pasa | exit 0 los dos (npx no se corrió) |
| Imágenes | tamaño y sha | pasa | docs/img/004 = 134.4 KB (< 200); .sha256 = sha del Mermaid actual (e82f2d42…) |
| Docs | lectura y script | pasa | índices ADR (33) y BACKLOG (41 abiertos) = sus entradas, hasta ADR-033, B58/B59, sin B60, B29 en Cerrados; memory.md 8 010 B; ninguna línea > 2 000; arranque 37 523 B; «ningún spec activo»; P12, resultados.md y ADR-033 dicen lo mismo (0 dudas en §9.2 y §9.4; §9.3 y §9.5 sin lectura) |
| check_scale sin cámara | test_comprobar_escala + PreviaEnHilo | pasa | 31 pruebas verdes; sin hilos vivos tras cerrar (normal, error, doble cerrar, enviar tras cerrar); con detector lento y tope 0.3 s, `cerrar` vuelve a tiempo y el hilo muere solo al acabar |
| Mutaciones (copia) | 6 cambios en una copia | pasa | símbolo inexistente, número del bloque, Mermaid sin SVG, quitar el filtro z ≤ 0, corte de velocidad 1→2 Hz y orden del modelo: todos hacen caer alguna prueba |

- Fallos:
  1. Baja. §9.5 da «banco sin cámara: 0.47–0.53, 5.6–5.8 y 0.17 ms» (gris, detección, pose+filtro); la tabla de la fase 6 de `resultados.md` de la 003 trae medias 0.46–0.50 (gris) y 5.58–5.98 (detect). Las cifras de §9.2 (~0.5 y ~6 ms) valen.
  2. Baja. `PRUEBAS.md` no tenía la fila de P04 en el índice (anterior a esta ronda); solo añadí la de P05.
- Dudas técnicas de §9.2 (sin fallo): paso 6, los dos candidatos de IPPE salen de la misma homografía y normalmente quedan los dos delante de la cámara; el descarte con z ≤ 0 (`vision/pose.py`) es una red de seguridad rara, y el texto lo dice («a veces»). El riesgo real es el caso en que gana la solución equivocada y queda delante: el texto lo reconoce, pero no hay medida de cuán frecuente es. Paso 9, «100 mm/s» es por eje; el corte de 7 Hz vale para esa velocidad en un eje.
- Lo dudoso: no verificado en vivo, por decisión del autor, la prueba con la regla de la 2c (rendimiento de la vista previa de `check_scale`). Los hilos de `PreviaEnHilo` se probaron con detectores simulados, no con tablero real. El proceso `python -m gui.panel --perfil …` vivo (PID 13368, desde las 20:19) no es mío.
- En vivo: ninguno nuevo.
- Veredicto: pasa. Detalle: `Claude outputs/pruebas/004-meta/ronda.md`.
