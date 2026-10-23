# Cómo funciona el proyecto hoy (2026-10-23, antes de la meta 003)

El diagrama que la dirección le dio al autor al abrir la meta 003. Es la foto de partida: la meta 003 lo cambia, y la meta posterior («entender detección → pose» con un gráfico) parte del resultado.

## 1. El recorrido de un frame (en vivo)

```
PANEL (gui/panel.py) — solo lanza scripts como procesos aparte
  "Arrancar tracker" → python tracker.py --config tracker_config_gs1.yaml
        │
        ▼
tracker.py (703 líneas: hace casi todo en un solo archivo)
  ① PERFIL     tracker_config_gs1.yaml → puerto, ajustes, .yml, K
  ② CÁMARA     camera_backend.py ─┬─ camaras_uvc.py   (qué cámara es: puerto USB)
                                  └─ ajustes_camara.py (exposición, foco… por DSHOW)
               frame 1280×960 + K + dist (intrinsecos_gs1_….yml)
  ③ DETECCIÓN  ArUco detectMarkers → esquinas 2D de cada marker (0 = Marker0; 3–13 = dodecaedro)
  ④ POSE       Marker0: solvePnP con 1 marker (4 esquinas)
               Dodecaedro: esquinas de todos los markers visibles + su posición 3D
               (reference_dodecaedro_v2_calibrado.txt) → un solvePnP (B37 nace aquí)
  ⑤ FILTRO     OneEuroFilter (clase dentro de tracker.py)
  ⑥ ENVÍO      pyigtl → OpenIGTLink 18944: Marker0ToTracker, DodecaedroToTracker (4×4)
  ⑦ VENTANA    cv2.imshow con los ejes (el cuello: ~20 fps, B32)
        │ TCP 18944
        ▼
3D SLICER (sus scripts no están en codigo/: se pegan desde MANUAL_simplificado.md)
  DodecaedroToMarker0 = Marker0ToTracker⁻¹ · DodecaedroToTracker
  → StylusTipToDodecaedro (.npy) → StylusTip → CT
```

## 2. Calibraciones (una vez, antes de operar)

| Qué | Script | Deja en `iter4/data/` |
|---|---|---|
| La lente (K, dist) y la escala | `calibrar_camara.py`, `comprobar_escala.py` | `intrinsecos_gs1/gs2_….yml` |
| La geometría del dodecaedro (BA) | `captura_calibracion.py` → `calibrar_rigid_body.py` (+ `calibrar_topologia`, `generar_reference_dodecaedro`, `corregir_giro_esquinas`, `limpiar_captura_fantasmas`) | `reference_dodecaedro_v2_calibrado.txt` |
| La punta (dock) | `calibrar_tip_divot.py` | `StylusTipToDodecaedro_….npy` |

## 3. Diagnóstico (no va en vivo)

`sondear_camara.py` (modos y controles), `medir_modos.py` (fps, exposición, enfoque), `identificar_ids.py` (qué markers ve).

## 4. El panel por dentro (`gui/`)

```
panel.py ── ventana y botones
  ├─ recetas.py        arma la línea de comando de cada botón
  ├─ procesos.py       lanza y detiene los scripts (apaga la aceleración MSMF)
  ├─ estado.py         semáforos: perfil, .yml, punta, geometría
  ├─ calibracion.py    ventana de 3 pasos (enfocar, tablero, escala)
  ├─ asistente.py + ba_monitor.py   asistente «dodecaedro nuevo»
  ├─ perfil_editor.py  única edición del perfil (calibration_file)
  └─ sonda_camara.py   «Probar cámara»
```

## Lo que falla

1. `tracker.py` lo hace todo (perfil, detección, pose, filtro, envío, ventana).
2. La matemática no tiene casa: `solvePnP`, geometría y filtro viven en el tracker; la calibración y el BA repiten parte.
3. Todo es plano: 17 scripts mezclan cámara, pose, calibraciones y diagnóstico; `data/` mezcla lo vigente con lo viejo.
4. Lo de Slicer vive fuera del código, en un manual.

## La propuesta que se discutió (no decidida; la decide el plan)

```
codigo/
  camara/       backend, puerto USB, ajustes
  vision/       detección ArUco, pose, filtro
  envio/        OpenIGTLink
  tracker.py    solo el bucle: cámara → vision → envío → ventana
  calibracion/  lente y escala
  diagnostico/  sonda, medir_modos, identificar_ids
  gui/          el panel
  slicer/       scripts de la consola de Slicer, versionados
  perfiles/ y data/ (solo lo vigente)
```
