# Guía — Calibrá tu propio dodecaedro (geometría por-impresión)

**Por qué:** la geometría calibrada por BA es de **una impresión física**. Cada
impresión 3D tiene los marcadores en posiciones ligeramente distintas, así que la
geometría **NO se comparte entre impresiones** — cada equipo calibra la suya. (Lo
compartido es el diseño: IDs 3–13, anillos, orientación y el software.) Si usás la
geometría de otra impresión, el tracking y la calibración del tip salen con error
enorme (spread de varios mm).

**Cuándo:** una sola vez por dodecaedro impreso (o si lo reimprimís/rearmás).

---

## Prerrequisitos

- Tu dodecaedro impreso con IDs **3–13**, orientación según
  `convencion_dodecaedro_compartido.md` (punto rojo abajo-derecha en los
  laterales). Verificá con `python iter4\identificar_ids.py --config iter4\tracker_config_doctor.yaml`.
- Tu cámara calibrada (tu `config` apunta a tu `calibration_file`).
- Medí con calibrador: `marker_mm` (lado del cuadrado negro) y `edge_mm` (arista).
- PowerShell en `codigo\` con el venv activado. **Los comandos de abajo ya están
  rellenados con las medidas de ESTA impresión del doctor** (marcador 14.5 mm, arista
  19.5 mm, config `tracker_config_doctor.yaml`). Si reimprimís/rearmás, re-medí y
  ajustá `--marker-mm`, `--edge-mm` y los nombres de archivo.

---

## Pasos

**1. Geometría teórica (semilla):**
```powershell
python iter4\generar_reference_dodecaedro.py --id-top 3 --ids-superior 4,5,6,7,8 --ids-inferior 9,10,11,12,13 --edge-mm 19.5 --marker-mm 14.5 --output iter4\data\reference_dodecaedro_doctor.txt
```

**2. Capturar dataset (90 s):** rotá el dodecaedro lento mostrando TODAS las caras,
dale tiempo extra al **anillo inferior (9–13)**, que es el que rompe el BA si queda
poco visto.
```powershell
python iter4\captura_calibracion.py --config iter4\tracker_config_doctor.yaml --geometry-file iter4\data\reference_dodecaedro_doctor.txt --duracion 90 --output iter4\data\captura_ba.npz
```

**3. Confirmar el orden real de los anillos** (sobre el CRUDO):
```powershell
python iter4\calibrar_topologia.py --input iter4\data\captura_ba.npz --id-top 3 --edge-mm 19.5 --marker-mm 14.5 --output iter4\data\reference_dodecaedro_doctor_real.txt
```
El TOP (3) debe salir con 5 vecinos y deben identificarse los dos anillos. Usá el
`_real.txt` como teórico en los pasos siguientes.

**4. Corregir el giro de esquinas (PASO CLAVE):** ajusta la geometría a cómo están
pegados TUS marcadores. Sin esto, la limpieza descarta ~90% y el BA no converge.
```powershell
python iter4\corregir_giro_esquinas.py --input iter4\data\captura_ba.npz --teorico iter4\data\reference_dodecaedro_doctor_real.txt --marker-mm 14.5 --output iter4\data\reference_dodecaedro_doctor_fix.txt
```
Debe terminar en **`[OK]`** (mediana < ~3 px). Reporta el giro por marker (es normal
que la cara TOP vaya distinto a los laterales). Si queda en `[WARN]`, revisá
`marker_mm`, la topología (paso 3) o la cobertura de la captura.

**5. Limpiar misdetecciones:**
```powershell
python iter4\limpiar_captura_fantasmas.py --input iter4\data\captura_ba.npz --teorico iter4\data\reference_dodecaedro_doctor_fix.txt --marker-mm 14.5 --umbral-px 12 --output iter4\data\captura_ba_limpia.npz
```
Debe conservar la mayoría (>80%). Si descarta casi todo, el paso 4 no quedó bien.

**6. Bundle adjustment — OJO: `--no-sparse` OBLIGATORIO** (el modo sparse está roto
y no converge):
```powershell
python iter4\calibrar_rigid_body.py --input iter4\data\captura_ba_limpia.npz --teorico iter4\data\reference_dodecaedro_doctor_fix.txt --output iter4\data\reference_dodecaedro_doctor_calibrado.txt --ancla 3 --marker-mm 14.5 --no-depth --no-sparse --max-frames 150 --max-nfev 150
```
Convergencia esperada: costo baja fuerte en ~20–30 iteraciones, RMSE final bajo.
> El reporte RMSE por-marker del BA NO es 100% confiable (puede marcar 1–2 markers
> alto por mínimo local de pose). Lo que vale es la reproyección independiente del
> paso 4 (que ya viste en `[OK]`).

**7. Apuntá tu config a tu geometría calibrada.** En `iter4\tracker_config_doctor.yaml`:
```yaml
rigid_bodies:
  - name: Dodecaedro
    geometry_file: data/reference_dodecaedro_doctor_calibrado.txt
    marker_mm: 14.5
```

**8. Recién ahora, la calibración del tip (dock).** Con la geometría correcta, el
`spread` del tip debe bajar a < 1.5 mm. Si seguía alto, era por la geometría.

---

## Resumen del flujo

```
generar_reference -> captura_calibracion -> calibrar_topologia ->
corregir_giro_esquinas -> limpiar_captura_fantasmas (umbral 12) ->
calibrar_rigid_body (--no-depth --no-sparse) -> apuntar config -> calibrar tip
```

Las dos cosas que el flujo "de manual" viejo NO tenía y que son imprescindibles:
**`corregir_giro_esquinas.py`** (paso 4) y **`--no-sparse`** en el BA (paso 6).
