# Convención del dodecaedro compartido (stylus) — reproducibilidad

**Fecha:** 2026-06-22
**Aplica a:** el dodecaedro impreso NUEVO que comparten Dr. Milton (Femto Bolt) y el doctor colaborador (webcam global shutter). Mismo stylus físico para ambos.

## Asignación de IDs (ArUco DICT_ARUCO_MIP_36h12)

- **ID 0**: marcador del PACIENTE (referencia ósea). Reservado, NO va en el dodecaedro.
- **ID 2**: placa de calibración del DIVOT/dock. Reservado, NO va en el dodecaedro.
- **IDs 3–13**: el dodecaedro (11 marcadores). Papel, alta calidad, negro mate, bordes nítidos.
  - **ID 3**: cara superior (opuesta a la base donde entra el mango).
  - **IDs 4–8**: anillo superior.
  - **IDs 9–13**: anillo inferior.

## Convención de ORIENTACIÓN (clave para reproducibilidad)

Regla fija para las 11 caras: **vista cada cara con el marcador "derecho" (ID legible), la esquina 0 queda ABAJO-DERECHA.**

- La "esquina 0" es la esquina top-left interna que decodifica ArUco; en `codigo/iter4/identificar_ids.py` se dibuja como un **punto ROJO**. Regla operativa: **el punto rojo abajo-derecha en TODAS las caras.**
- Verificación: `python iter4\identificar_ids.py` (detección estricta) → cada cara muestra su ID correcto y el punto rojo abajo-derecha.

### ¿Por qué consistencia si el BA igual calibra?

El bundle adjustment resuelve la pose completa (posición Y orientación) de cada marcador, así que **matemáticamente la orientación consistente NO es obligatoria** para que el tracking funcione. Se mantiene por **reproducibilidad**: build documentable, geometría teórica de partida más cercana a la real (BA converge mejor) y verificable de un vistazo. Si se rearma o reimprime el dodecaedro, seguir esta misma regla.

## Calibraciones compartidas vs por-equipo

Como es el **mismo stylus físico**, estas calibraciones se generan una vez (Milton, con la Femto) y se versionan para que el doctor haga `pull` y entre directo:

- **Geometría BA**: `reference_dodecaedro_v2_calibrado.txt` — física, compartible.
- **Pivote/tip**: `StylusTipToDodecaedro_v2.*` — físico, compartible.

Por-equipo (NO se comparte): **calibración intrínseca de cámara** (Femto de fábrica vs `.yml` de la global shutter) y el **marcador 0 del paciente**.

## Parámetros de calibración (rellenar al medir)

- `marker_mm` (lado del cuadrado negro del ArUco): **14.6 mm**
- `edge_mm` (arista del dodecaedro): **20 mm**
- Comando geometría: `--id-top 3 --ids-superior 4,5,6,7,8 --ids-inferior 9,10,11,12,13`
- OJO: el ORDEN del anillo inferior puede no ser el nominal; confirmar con el diagnóstico de topología tras la captura BA y reordenar si hace falta.

Ver también: [[project_registro_superficie_iter5]].
