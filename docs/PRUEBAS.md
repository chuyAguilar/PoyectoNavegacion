# PRUEBAS — lo que se probó

Lo escribe solo el agente de pruebas (principio 1; ADR-020), sobre HEAD commiteado y con el árbol limpio. Cada ronda añade una entrada al final; lo anterior no se reescribe. El detalle de cada ronda está en `Claude outputs/pruebas/<fase>/ronda.md`, fuera de git. Quien añade una entrada pone su línea en el índice.

## Índice

| # | Meta y fase | Commit probado | Fecha | Veredicto |
|---|---|---|---|---|
| P01 | Meta 001, fases 1–4 · limpieza y orden | e52f58c | 2026-10-19 | pasa |
| P02 | Cámara global shutter 1 · flujo actual con el perfil doctor | 6431bc6 | 2026-10-19/20 | cadena pasa; calibración intrínseca no concluyente |

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
