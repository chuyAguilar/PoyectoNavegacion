# PRUEBAS — lo que se probó

Lo escribe solo el agente de pruebas (principio 1; ADR-020), sobre HEAD commiteado y con el árbol limpio. Cada ronda añade una entrada al final; lo anterior no se reescribe. El detalle de cada ronda está en `Claude outputs/pruebas/<fase>/ronda.md`, fuera de git. Quien añade una entrada pone su línea en el índice.

## Índice

| # | Meta y fase | Commit probado | Fecha | Veredicto |
|---|---|---|---|---|
| — | _Ninguna ronda todavía_ | — | — | — |

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

_Ninguna todavía._
