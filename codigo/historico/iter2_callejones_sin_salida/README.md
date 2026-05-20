# Iter 2 - Callejones sin salida (2026-05-19)

Archivos generados durante el debugging de Etapa D que NO formaron parte
de la solución final.

## Contexto

Durante iter 2, el BA (Etapa D) no convergía sobre el dataset capturado
(RMSE inicial ~15 px vs ~0.7 px que daba iter 1 con el mismo dodecaedro).

Hipótesis explorada (y descartada): **el dodecaedro físico tenía markers
pegados en posiciones distintas a la convención teórica**.

Evidencia que la descartó:
- Tanto `reference_dodecaedro.txt` (teórico original) como
  `reference_dodecaedro_real.txt` (calibración topológica) daban el mismo
  RMSE final (~11 px). Si la geometría fuera la causa, los dos darían
  resultados distintos.
- El usuario confirmó que el dodecaedro físico es el MISMO de iter 1
  (que convergía a 0.61 px).

Conclusión real: el problema está en el **dataset capturado** (técnica
de captura, motion blur, distancia, foco, o configuración de la cámara
entre iter 1 e iter 2 cambió algo sutil que no detectamos).

## Archivos

- `diagnostico_etapa_d.py`: diagnóstico de poses iniciales y RMSE por frame.
  Útil si en el futuro hay sospecha de problema con poses.

- `diagnostico_topologia.py`: comparación de distancias medidas vs teóricas
  entre pares de markers. Útil si hay sospecha de error de pegado.

- `reference_dodecaedro_real.txt`: archivo generado por calibrar_topologia.py
  con el orden detectado del cinturón inferior `[158, 159, 160, 161, 157]`
  en vez del teórico `[157, 158, 159, 160, 161]`. NO resolvió el problema,
  pero confirmó que la topología del cubo físico está bien (un dodecaedro
  válido).

## Cuándo desarchivar

- Si en el futuro alguien arma un dodecaedro NUEVO y tiene dudas sobre
  el orden de pegado: usar `calibrar_topologia.py` (NO archivado, en
  `codigo/`).

- Si vuelve a aparecer un caso de "BA no converge con RMSE alto":
  considerar correr `diagnostico_etapa_d.py` para identificar el frame
  o marker problemático.

## NO usar en flujo normal

Para captura → BA → tracker, el pipeline simple A→B→C→D→E→F es
suficiente. La calibración topológica es una herramienta de verificación
opcional, no un paso obligatorio.
