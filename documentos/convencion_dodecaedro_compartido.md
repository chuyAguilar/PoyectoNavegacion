# Convención del dodecaedro compartido (stylus) — reproducibilidad

**Fecha:** 2026-06-22
**Aplica a:** el DISEÑO de dodecaedro (IDs 3–13) que usan Dr. Milton (Femto Bolt) y el doctor colaborador (webcam global shutter). OJO: cada uno tiene su PROPIA impresión y su propio stylus → cada uno calibra su geometría y su tip por separado (ver 'Qué se comparte y qué NO').

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

## Qué se comparte y qué NO (CORREGIDO 2026-06-26)

**La geometría calibrada por BA es de UNA impresión física — NO es compartible.** Cada impresión 3D tiene las posiciones de los marcadores ligeramente distintas (tolerancias), y el BA fija la pose de cada marcador a ESE objeto. Usar la geometría de otra impresión da spread enorme (lo vimos: 15 mm en el dodecaedro del doctor usando mi geometría calibrada). Lo mismo el tip: depende del stylus físico.

Por lo tanto **cada equipo calibra lo suyo**:
- **Geometría BA** (`reference_dodecaedro_<equipo>_calibrado.txt`): POR-IMPRESIÓN. Ver `GUIA_calibrar_dodecaedro_propio.md`.
- **Tip/pivote** (`StylusTipToDodecaedro_<equipo>_dock.*`): POR-STYLUS.
- **Calibración intrínseca de cámara** (`.yml`): POR-CÁMARA.
- **Marcador 0 del paciente**: por-equipo.

**Lo único compartido es el DISEÑO**: IDs 3–13, la asignación de anillos, la convención de orientación y el software/flujo. Dos personas con impresiones distintas siguen el mismo diseño pero calibran cada una por separado.

## Parámetros de calibración (rellenar al medir)

- `marker_mm` (lado del cuadrado negro del ArUco): **14.6 mm**
- `edge_mm` (arista del dodecaedro): **20 mm**
- Comando geometría: `--id-top 3 --ids-superior 4,5,6,7,8 --ids-inferior 9,10,11,12,13`
- OJO: el ORDEN del anillo inferior puede no ser el nominal; confirmar con el diagnóstico de topología tras la captura BA y reordenar si hace falta.

Ver también: [[project_registro_superficie_iter5]].
