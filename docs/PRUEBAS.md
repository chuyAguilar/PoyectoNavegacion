# PRUEBAS — lo que se probó

Lo escribe solo el agente de pruebas (principio 1; ADR-020), sobre HEAD commiteado y con el árbol limpio. Cada ronda añade una entrada al final; lo anterior no se reescribe. El detalle de cada ronda está en `Claude outputs/pruebas/<fase>/ronda.md`, fuera de git. Quien añade una entrada pone su línea en el índice.

## Índice

| # | Meta y fase | Commit probado | Fecha | Veredicto |
|---|---|---|---|---|
| P01 | Meta 001, fases 1–4 · limpieza y orden | e52f58c | 2026-10-19 | pasa |

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

