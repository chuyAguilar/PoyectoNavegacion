# BACKLOG — lo que falta

Lo que se decidió no hacer ahora, con su porqué. Prioridades: **alta**, puede dar un resultado equivocado o impide usar el sistema; **media**, mejora clara sin riesgo; **baja**, espera datos o solo si estorba. Lo cerrado pasa a «Cerrados» con la fecha y qué lo cerró. Quien toca una entrada actualiza el índice en el mismo cambio.

## Índice

| # | Qué | Prioridad | Destino |
|---|---|---|---|
| B07 | Marker0 rígido y corto (brazo de palanca) | Alta | — |
| B08 | Runbook para el contexto Femto | Media | — |
| B09 | FPS ~16–17 con la Femto en modo RGB | Media | — |
| B10 | Verificaciones en vivo pendientes del brief-02 | Media | — |
| B11 | Binarios pesados versionados (`.ply`, PDF, PPTX, `.h5`) | Media | — |
| B12 | Detección de 3–4 markers por vista | Baja | — |
| B13 | `.git` sin compactar (691 MB sueltos) | Baja | — |
| B14 | Stylus impreso nuevo (IDs 181–191) | Baja | — |
| B15 | Reintegrar el depth al BA | Baja | — |
| B16 | Rama de registro por superficie (en pausa) | Baja | — |
| B17 | 22 pruebas desfasadas en `xfail(strict=True)` | Media | — |
| B18 | El filtro 1-Euro no tiene replay | Media | — |
| B19 | `validar_prerrequisitos` deja un calibrado vacío | Alta | — |
| B20 | Slicer carga la punta por fecha | Alta | — |
| B21 | `opencv-python` frente a `opencv-contrib-python` | Baja | — |
| B22 | Secuencias de escape inválidas en docstrings de `iter4\` | Baja | — |
| B23 | Explorar el tracker en una Jetson Orin Nano, con Slicer en BigDaddy | Baja | — |
| B24 | Frecuencia de la red (50/60 Hz) de las SVPRO, que OpenCV no fija | Baja | — |
| B25 | La sonda pierde los modos medidos si salta el tope | Media | — |
| B26 | Modos de las SVPRO que no sirven o no son estables | Baja | — |
| B27 | `tracker.abrir_camara`, función que nadie llama | Baja | — |
| B28 | `tracker.py` lanzado a mano abre MSMF con la aceleración HW encendida | Media | — |
| B29 | «Probar cámara» del panel no comprueba la marca ni aplica los ajustes | Media | — |
| B30 | Leer la marca y aplicar los controles en una sola apertura DSHOW | Baja | — |
| B31 | El criterio de exposición de `medir_modos.py` favorece imágenes casi saturadas | Media | — |
| B32 | Optimizar el tracker: la ventana limita a 19–25 fps en cualquier resolución | Media | — |
| B34 | Las pruebas no deben poder abrir una cámara real aunque cambie un perfil | Media | — |
| B35 | El criterio de escala por medias no mira la repetibilidad | Media | — |
| B36 | Cámara 2 con el punto principal 90 px sobre el centro | Baja | — |

## Abiertos

### B07 · Marker0 rígido y corto
- **Qué:** el Marker0 en una varilla de ~21 cm convierte un giro de 12° en 45 mm de desfase del hueso.
- **Por qué queda:** es montaje físico, no código.
- **De dónde:** ADR-013; `docs/CONTEXT.md` §6.
- **Qué haría falta:** un soporte rígido pegado al objeto (`stl/BaseMarcador/`) y medir el RMS antes y después.
- **Prioridad:** alta (da resultados equivocados también en paired-point).

### B08 · Runbook para el contexto Femto
- **Qué:** `MANUAL_simplificado.md` opera el contexto doctor; no hay uno para `tracker_config.yaml`.
- **Por qué queda:** no bloquea, porque el panel cubre buena parte.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** un runbook equivalente con Marker0 de 80 mm.
- **Prioridad:** media.

### B09 · FPS ~16–17 con la Femto en modo RGB
- **Qué:** el backend habilita depth + align aunque solo se use el RGB.
- **Por qué queda:** toca `camera_backend.py`, cerca de la cadena (principio 6).
- **De dónde:** `docs/CONTEXT.md` §6, observado en vivo el 2026-08-13.
- **Qué haría falta:** no abrir el stream de depth en modo solo RGB; medir FPS antes y después.
- **Prioridad:** media.

### B10 · Verificaciones en vivo pendientes del brief-02
- **Qué:** la captura del asistente con IDs nuevos y la calibración de punta por dock desde el panel. (La calibración de cámara quedó verificada en vivo: `calibrar_camara.py` por línea de comandos en la fase 4 · Calibración de la cámara 1 y comprobación de escala, 2026-10-22, y desde el panel, con la ventana de tres pasos, en la fase 5 · Calibración de la cámara 2, 2026-10-23: cámara 2 RMS 0.154 px, control 0.150 px; meta 002.) (El snippet de `documentos/MANUAL_simplificado.md` §4.2 con la ruta nueva, que se sumó en la fase 4 de la meta 001, quedó verificado en vivo por el autor el 2026-10-19: traslación [0.904, 5.471, −201.808] mm, la esperada; `docs/PRUEBAS.md` P01.)
- **Por qué queda:** necesita hardware y la placa dock física.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** una sesión con cámara; reportar números.
- **Prioridad:** media.

### B11 · Binarios pesados versionados
- **Qué:** `femto_pruebas/nubes/*.ply` (~250 MB), `documentos/referencias/*.pdf` y `documentos/slicerigt_curso/*.pptx` (~25 MB), `herramientas/*.h5` (pivotes legacy).
- **Por qué queda:** son evidencia de la rama en pausa; el autor decide.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** decidir si salen de git (`git rm --cached` + `.gitignore`) o se quedan.
- **Prioridad:** media.

### B12 · Detección de 3–4 markers por vista
- **Qué:** la referencia histórica es 5–6.
- **Por qué queda:** espera una sesión que mida distancia, ángulo y luz antes de tocar el detector.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** medir markers por vista a 50–70 cm con luz controlada.
- **Prioridad:** baja.

### B13 · `.git` sin compactar
- **Qué:** 691 MB en 1214 objetos sueltos, 0 packs y un temporal basura.
- **Por qué queda:** no da resultados equivocados; solo pesa.
- **De dónde:** paso 0 del método, 2026-10-19.
- **Qué haría falta:** que el autor corra `git gc` desde PowerShell.
- **Prioridad:** baja.

### B14 · Stylus impreso nuevo (IDs 181–191)
- **Qué:** su geometría CAD es buena, pero falta pose robusta con rechazo de outliers y `marker_mm 15.7`; su BA se atora.
- **Por qué queda:** no urgente.
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** retomar si se cambia de stylus. Su config (`tracker_config_stylus_impreso.yaml`) y su geometría calibrada están en `iter4\data\historico\` desde la fase 3 · movimientos de la meta 001 (2026-10-19): para usarlo, devolver el config a `iter4\` (el panel solo ve `iter4\tracker_config*.yaml`) y revisar sus rutas relativas.
- **Prioridad:** baja.

### B15 · Reintegrar el depth al BA
- **Qué:** el BA corre solo 2D por el bias residual del depth fuera de la caja.
- **Por qué queda:** espera resolver el bias (ADR-007, ADR-008).
- **De dónde:** `docs/CONTEXT.md` §6.
- **Qué haría falta:** medir y corregir el bias de −10 mm.
- **Prioridad:** baja.

### B16 · Rama de registro por superficie
- **Qué:** `femto_pruebas/` validado a 1.76 mm, con dos problemas abiertos: el brazo de palanca (B07) y la ambigüedad de deslizamiento en la columna.
- **Por qué queda:** en pausa por ADR-014.
- **De dónde:** ADR-012, ADR-014.
- **Qué haría falta:** el banco rígido con cubo distintivo (`stl/BaseMarcador/`).
- **Prioridad:** baja.

### B17 · 22 pruebas desfasadas en `xfail(strict=True)`
- **Qué:** al repuntar la suite a `iter4\`, 22 de las 70 pruebas de los 3 archivos de mayo fallan porque el código cambió después (el plan estimó 11). Por familia: 7 esperan los IDs 151–161 y hoy son 170–180 (`reference_dodecaedro.txt` y los defaults de `generar_reference_dodecaedro.py`: `test_cargar_referencia_archivo_real`, `test_cargar_rb_ids_archivo_real`, `test_ids_default_son_iter1`, `test_distancia_top_cinturones_uniforme`, `test_adyacencia_antiprismatica`, `test_frame_right_handed_top`, `test_iter2_ids_1_11`); 1 compara con el histórico de iter 1 (`test_matches_historico_iter1`); 8 del BA de `calibrar_rigid_body.py`, que pasó a parametrización rígida y a pedir `use_depth`, `sigma_2d` y `sigma_3d` (`test_parametrizar_reconstruir_round_trip`, las 3 de `construir_jac_sparsity`, las 2 de `calcular_residuos`, `test_rmse_por_marker_agrupa_correctamente`, `test_ba_recupera_geometria_perturbada`); y 6 de `captura_calibracion.py`: `cargar_calibracion` (2, vive en `tracker.py`), `fourcc_int_a_str` (1, ya no existe), la firma nueva de `construir_metadata` (1), `resolver_geometry_path` relativo al CWD (1, `CONTEXT.md` §4.14) y `validar_prerrequisitos`, que ya no comprueba el archivo de intrínsecos (1).
- **Por qué queda:** por decisión del autor (`clarify.md` P1 = b), la fase 1 las marca sin reescribirlas. Lo que vigilaban hoy no se vigila; en particular, el núcleo del BA queda casi sin pruebas.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo, P1; fase 1 · suite y replay, 2026-10-19.
- **Qué haría falta:** por cada una, caracterizarla (que espere lo que el código hace hoy) o borrarla. La de los intrínsecos exige antes decidir si es a propósito (la Femto usa los de fábrica) o hay que restaurar el fallo fuerte (principio 7).
- **Prioridad:** media (por la de los intrínsecos y las 8 del BA no es baja).

### B18 · El filtro 1-Euro no tiene replay
- **Qué:** el filtrado de posición y de cuaternión está dentro del lazo de `tracker.main()`; el replay de la suite cubre solo `estimar_pose_rigid_body` y la regla de `min_markers`.
- **Por qué queda:** cubrirlo exige sacar el filtrado a una función de `tracker.py`, que es la cadena (principio 6).
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** extraer el filtrado a una función sin cambiar su resultado, con replay antes y después, y sumarlo al replay.
- **Prioridad:** media.

### B19 · `validar_prerrequisitos` deja un calibrado vacío
- **Qué:** en `calibrar_rigid_body.py` y `captura_calibracion.py` abre la salida en modo `"ab"` antes de correr para comprobar que se puede escribir; si el proceso falla después, queda un archivo de 0 bytes con nombre válido (el origen del `reference_dodecaedro_nuevo_calibrado.txt` de B05).
- **Por qué queda:** la meta 001 no toca la lógica de los scripts activos.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** comprobar la carpeta sin crear el archivo y escribir solo al final.
- **Prioridad:** alta (un calibrado vacío con nombre válido puede tomarse por bueno).

### B20 · Slicer carga la punta por fecha
- **Qué:** el snippet de `documentos/MANUAL_simplificado.md` §4.2 carga el `StylusTipToDodecaedro*.npy` más reciente por fecha de `iter4\data\`; un `git pull`, una copia o un movimiento cambian cuál, sin aviso en Slicer (`estado.py` sí avisa).
- **Por qué queda:** toca lo que se carga en Slicer: necesita verificación en vivo.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** nombrar la punta explícita en el snippet y mover las puntas viejas (`StylusTipToDodecaedro.npy`, `_2`, `_divot`, `_viejo_dock`, del dodecaedro viejo) a `data\historico\`.
- **Prioridad:** alta.

### B21 · `opencv-python` frente a `opencv-contrib-python`
- **Qué:** el venv y `requirements.txt` tienen `opencv-python` 4.11; `CONTEXT.md` §3 dice contrib.
- **Por qué queda:** no afecta a nada de hoy.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** alinear el texto, o el paquete si algo de contrib hiciera falta.
- **Prioridad:** baja.

### B22 · Secuencias de escape inválidas en docstrings de `iter4\`
- **Qué:** 14 scripts de `iter4\` y `gui\` (rutas Windows en el docstring, p.ej. `\)`) dan `DeprecationWarning: invalid escape sequence` al compilar; eran los 14 avisos de la suite. Desde la fase 3 · movimientos de la meta 001 (2026-10-19), 6 de ellos están en `codigo\historico\iter4_diagnosticos\` y quedan 8 avisos (`calibrar_camara`, `calibrar_tip_divot`, `captura_calibracion`, `identificar_ids`, `limpiar_captura_fantasmas`, `gui\ba_monitor`, `gui\estado`, `gui\panel`). En Python 3.12+ pasa a `SyntaxWarning`.
- **Por qué queda:** con Python 3.11.9 no cambia nada; corregirlo toca scripts activos.
- **De dónde:** fase 1 · suite y replay de la meta 001, 2026-10-19.
- **Qué haría falta:** docstrings crudos (`r"""`) o barras dobles, al tocar cada script por otra razón o antes de subir de Python.
- **Prioridad:** baja.

### B23 · Explorar el tracker en una Jetson Orin Nano, con Slicer en BigDaddy
- **Qué:** conectar las cámaras global shutter a una Jetson y correr ahí el tracker, viendo la navegación en Slicer en BigDaddy por la red. La cadena no cambiaría (principio 6): `pyigtl` ya publica por TCP (18944) y Slicer se conectaría a la IP de la Jetson en lugar de a `localhost`.
- **El equipo (escaneo del autor, 2026-10-19):** Jetson Orin Nano Developer Kit Super (Yahboom, hostname `yahboom`); Ubuntu 22.04.5, aarch64, JetPack 6.2 (L4T R36.4.3), CUDA 12.6; modo MAXN_SUPER; 7.4 GB de RAM unificada (~5.2 GB libres) y ~11 GB de swap; NVMe con ~21 GB libres (88 % usado); escritorio gráfico con escritorio remoto (3389, 5900); Docker 27.5 con runtime de GPU; Tailscale. Comparte la máquina con Ollama (13 modelos, 37 GB en disco), JupyterLab, openclaw-gateway y CUPS.
- **Por qué queda:** es exploración, no prioridad: el autor puede dejar el cable de las cámaras en BigDaddy (2026-10-19). Dudas sin medir: Ubuntu 22.04 trae Python 3.10, no el 3.11.9 del venv (instalar 3.11 o probar el código con 3.10); que `opencv-contrib-python` ≥ 4.7 instale por pip en aarch64 (o un contenedor); el backend `MSMF` es solo Windows y en Linux sería V4L2, que `camera_backend.py` no tiene probado; los FPS de decodificar MJPEG y detectar ArUco a 1920×1200 en su CPU, con 2 cámaras; la latencia por la red (LAN directa frente a Tailscale); y la memoria si Ollama tiene un modelo cargado a la vez. El panel (PySide6) podría correr por el escritorio remoto o quedarse en BigDaddy.
- **De dónde:** el autor, 2026-10-19, al hablar de la meta siguiente (cables cortos de las cámaras).
- **Qué haría falta:** una prueba corta antes de cualquier plan: en la Jetson, Python 3.10/3.11 con OpenCV ≥ 4.7, abrir una cámara con V4L2 + MJPG, detectar ArUco y medir FPS y latencia hacia Slicer en BigDaddy por la red; comparar con la alternativa barata (un cable USB 3 activo o extensor). Con números, decidir.
- **Lo que deja la meta 002 (2026-10-21, conversación con el autor):** lo que es de la cámara se conserva (modos: MJPG ~90 fps hasta 1280×960; serie `01.00.00` idéntica; ajustes guardados en la cámara; saturación según exposición) y la calibración intrínseca (`.yml`) vale en la Jetson tal cual si se usa la misma resolución y no se toca el foco. Se rehace lo que es de Windows: la sonda (`camaras_uvc.py`, la parte MSMF/DSHOW de `sondear_camara.py`), la escritura de controles (en Linux por V4L2; `v4l2-ctl` lista controles y modos con sus intervalos) y la identidad de cada cámara (en Linux probablemente por la ruta del puerto en `/dev/v4l/by-path/`, sin contrastar). Se mide de nuevo: los FPS de tracking en la CPU ARM. Para no repetir de más, la Fase 2 · Ajustes fijos, identidad y comprobación del tamaño al abrir debería declarar los ajustes en el perfil de forma independiente del sistema operativo, con una capa por sistema.
- **Al día (2026-10-21, fase 2a):** el formato de `controls` ya es independiente del sistema (`ajustes_camara.py`: nombres propios, exposición en ms) y la capa de Windows es `CapaWindowsDShow`; queda por escribir la capa de Linux (V4L2, `capa_para_plataforma("linux")`) y la identidad por `/dev/v4l/by-path` (`usb_port_linux`). La identidad en Windows es la ruta del puerto USB (`camaras_uvc.py`, CfgMgr32).
- **Prioridad:** baja.

### B24 · Frecuencia de la red (50/60 Hz) de las SVPRO, que OpenCV no fija
- **Qué:** AMCap muestra «Frecuencia de PowerLine» en 50 Hz en la cámara 1; la red en México es de 60 Hz. Con luz de red, eso puede dar parpadeo (posible causa del de P02 con la caja al mínimo). Es un control UVC de la unidad de proceso que OpenCV no expone como `CAP_PROP_*`; hoy solo se cambia a mano en AMCap.
- **Por qué queda:** el plan de la meta 002 · Calibración de las cámaras global shutter lo deja fuera (se pone a mano a 60 Hz en AMCap antes de cada sesión) y no se sabe si persiste tras desenchufar.
- **De dónde:** sesión en vivo de la fase 1 · Sonda de controles, modos e identidad, 2026-10-20; el plan de la meta 002 la manda aquí si se ve.
- **Qué haría falta:** medir si los 60 Hz puestos en AMCap persisten tras desenchufar; si no, fijarlo por código (`IKsControl` con la propiedad de PowerLine de la unidad de proceso, por `ctypes`, o una dependencia que lo exponga), con su plan. Sube a media si el parpadeo afecta a la detección.
- **Medido (2026-10-21, cierre de la fase 1):** en la cámara 1, los 60 Hz puestos en AMCap siguieron tras desenchufar y enchufar (los ajustes viven en la cámara). Falta verlo en la cámara 2 y comprobarlo al empezar cada sesión; fijarlo por código solo si se pierde.
- **Medido (2026-10-21, fase 2a):** en la cámara 2 persisten exposición, ganancia y `focus` tras desenchufar (`--leer`); el PowerLine no se leyó (OpenCV no lo expone) ni se midió su persistencia en la 2. Sigue abierta solo esa parte.
- **Prioridad:** baja.

### B25 · La sonda pierde los modos medidos si salta el tope, y su presupuesto por modo se queda corto
- **Qué:** en `sondear_camara.py`, `estado["modos"]` se asigna cuando `sondear_modos` termina; si el vigilante (`_vigilante`) salta antes, el JSON queda con `"timeout": true` y sin ninguna fila. Pasó en `modos_gs1_msmf_mjpg.json` y `modos_gs1_msmf_yuy2.json` (sesión del 2026-10-20): sus cifras solo quedaron en la consola y en `Claude outputs/fases/002/fase-1-en-vivo.md`. Además el presupuesto (`ABRIR_S + segundos + MARGEN_MODO_S` = 21 s con 5 s de captura) se queda corto: por MSMF a 90 fps cada modo tardó ~44–49 s (`total_s`; abrir ~10–11 s), y la comprobación por modo (`ABRIR_S + segundos`) no cuenta el resto.
- **Por qué queda:** la fase 1 ya tiene sus números y la dirección cerró la fase sin abrir cámaras. No da un resultado equivocado: el JSON dice `timeout` y no trae filas.
- **De dónde:** cierre de la fase 1 · Sonda de controles, modos e identidad (meta 002), 2026-10-21, al leer los JSON.
- **Qué haría falta:** guardar cada fila al medirla (en el `estado` compartido con el vigilante) y subir el presupuesto por modo a lo medido (~50 s por MSMF). Lo mismo vale para `medir_modos.py` de la fase 3 · Enfoque y medición de resolución × formato, que aún no existe: conviene que su plan lo traiga desde el principio.
- **Al día (2026-10-21, fase 2a):** lo nuevo de la 2a (`--puertos`, `--leer`, `--fijar`, `--tras-msmf`, `--verificar-orden`) guarda cada medición en el `estado` del vigilante al tenerla; `sondear_modos` (el barrido de modos de la fase 1) sigue como estaba, y por eso la entrada sigue abierta.
- **Al día (2026-10-22, fase 3):** `medir_modos.py` (el de la fase 3) escribe cada fila al medirla y el vigilante guarda lo que haya si salta el tope; el tope se comprueba antes de empezar y antes de cada fila. No saltó en la sesión en vivo. Queda abierta solo para `sondear_modos` de `sondear_camara.py`, que ya no se usa para elegir modos.
- **Prioridad:** media.

### B26 · Modos de las SVPRO que no sirven o no son estables
- **Qué:** por MSMF con MJPG, 800×600 abre y no da frames (y gasta el tiempo de apertura); 1024×768 dio ~90 fps en la cámara 1 y ningún frame en la cámara 2; 1600×1200 entrega 1280×960; en YUY2, 960×720 no da frames y el resto va a ≤ 59 fps. Por MSMF, `get(CAP_PROP_FOURCC)` devuelve `0x00000016`, no `MJPG`: el formato obtenido no se puede leer de vuelta así.
- **Por qué queda:** es informativo; la fase 3 · Enfoque y medición de resolución × formato elige entre los modos que sí funcionan.
- **De dónde:** sesión en vivo de la fase 1 · Sonda de controles, modos e identidad (meta 002), 2026-10-20/21 (`Claude outputs/camaras/modos_*.json`).
- **Qué haría falta:** nada, salvo que la resolución elegida sea una de estas; si la comprobación del tamaño de la fase 2 quiere verificar también el formato, que no use `get(CAP_PROP_FOURCC)` por MSMF.
- **Al día (2026-10-22, fase 2b):** la comprobación de tamaño del backend compara el frame, no el FOURCC, y detecta el caso de 1600×1200 que entrega 1280×960 (prueba sin cámara).
- **Al día (2026-10-22, fase 3):** medido con la aceleración HW de MSMF apagada (`medir_modos.py`, las dos cámaras): 1920×1080 y 1920×1200 en MJPG y 640×480 y 1280×720 en YUY2 dan ~90 fps de captura (89.5–90), no los ~30 y ≤ 59 de la fase 1, que se midieron con la aceleración encendida. Esos modos sí sirven para captura; la resolución elegida (1280×960 MJPG, P16) no depende de ello. Los que no abren o no entregan (800×600, 1024×768 en la cámara 2, 960×720 YUY2) no se volvieron a medir.
- **Prioridad:** baja.

### B27 · `tracker.abrir_camara`, función que nadie llama
- **Qué:** `abrir_camara(cfg_cam)` en `codigo/iter4/tracker.py` (línea 181) no la llama nadie (grep); el tracker abre la cámara por `camera_backend.create_backend`.
- **Por qué queda:** no estorba y `tracker.py` es la cadena (principio 6): la meta 002 no lo toca.
- **De dónde:** plan de la meta 002 · Calibración de las cámaras global shutter, al buscar quién abre la cámara; confirmado por grep en la fase 2a, 2026-10-21.
- **Qué haría falta:** quitarla (o usarla) en una fase que ya toque `tracker.py`, con la suite y el replay.
- **Prioridad:** baja.

### B28 · `tracker.py` lanzado a mano abre MSMF con la aceleración HW encendida
- **Qué:** `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` baja la apertura de una SVPRO de 43–51 s a 3.6–4.0 s sin cambiar los fps (sesión en vivo de la fase 2b, 2026-10-21/22). El código la pone en `camaras_uvc` al importarse, pero cv2 solo la ve si se puso antes de cargarse: `cv2.pyd` del venv (4.11) lleva el CRT estático y copia el entorno al cargarse (comprobado sin cámara con `OPENCV_IO_ENABLE_OPENEXR`). `tracker.py` importa `cv2` (línea 23) antes que `camera_backend` (línea 30), así que lanzado a mano desde PowerShell sigue con la aceleración encendida; el backend lo dice en su log («Aceleracion HW de MSMF ENCENDIDA: cv2 se cargo antes…») y `tests/test_aceleracion_msmf.py` lo fija. Desde el panel no pasa: `procesos.entorno_hijo` se la pasa apagada a sus procesos.
- **Por qué queda:** el encargo de la corrección de la fase 2b dice que `tracker.py` no cambia (principio 6).
- **De dónde:** corrección de la fase 2b · Perfiles por cámara: identidad, ajustes y tamaño al abrir (meta 002), 2026-10-22.
- **Qué haría falta:** una línea en `tracker.py`, `import camaras_uvc` antes de `import cv2`, en una fase que ya toque el tracker (con la suite, el replay y la comprobación de la cadena); mientras tanto, lanzar a mano con `$env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS='0'`. Cambiar entonces la prueba `test_tracker_importa_cv2_antes_y_no_la_ve`.
- **Prioridad:** media.

### B29 · «Probar cámara» del panel no comprueba la marca ni aplica los ajustes
- **Qué:** `gui/sonda_camara.py` resuelve el índice por el puerto, abre por MSMF y lee un frame, pero no lee la marca ni aplica `controls`: con las cámaras intercambiadas de puerto da «OK» (el tracker y el backend sí paran).
- **Por qué queda:** en la fase 2b la sonda se dejó corta para caber en los 20 s del vigilante del panel; con la aceleración apagada (corrección de la 2b) ya cabría (~1 s de abrir + leer, ~1.2 s de marca).
- **De dónde:** sesión en vivo de la fase 2b · Perfiles por cámara: identidad, ajustes y tamaño al abrir (meta 002), punto 3, 2026-10-22.
- **Qué haría falta:** que la sonda lea la marca (sin escribir) antes de abrir, o que use `camera_backend` entero; medir que sigue dentro del vigilante de `recetas.py`.
- **Prioridad:** media.

### B30 · Leer la marca y aplicar los controles en una sola apertura DSHOW
- **Qué:** `WebcamBackend.open()` abre la cámara por DSHOW dos veces antes del video: una para leer la marca (`capa.leer`, 1.11–1.48 s) y otra para aplicar los ajustes (`capa.aplicar`, 1.26–1.57 s).
- **Por qué queda:** es solo tiempo (~1.2 s por arranque) y la fase 2b ya cumple su criterio.
- **De dónde:** sugerencia del «implementa» de la fase 2b · Perfiles por cámara: identidad, ajustes y tamaño al abrir (meta 002), medida en su sesión en vivo, 2026-10-22.
- **Qué haría falta:** un método de la capa que lea la marca, pare si no coincide y, sin cerrar, aplique los controles; con su prueba sin cámara del orden (leer marca → parar o escribir) y la misma garantía de que con marca distinta no se escribe nada.
- **Prioridad:** baja.

### B31 · El criterio de exposición de `medir_modos.py` favorece imágenes casi saturadas
- **Qué:** `elegir_exposicion` descarta lo que satura más de 1 % de los píxeles a 255 sobre el dodecaedro y, entre empates de markers, elige la exposición más larga. Con MJPG la imagen se queda en 250–254 sin llegar a 255, y la fracción a 255 no lo ve. En la sesión en vivo (1280×960, caja en nivel 2) eligió 3.906 ms (brillo medio 244–245, casi quemada) y la cámara 2 sola 0.488; el autor eligió 0.977 ms (brillo ~170, los mismos markers, ~4 veces menos estela de movimiento; P15).
- **Por qué queda:** el autor ya eligió a mano y la meta 002 no vuelve a elegir exposición; no da un resultado equivocado mientras la elija una persona con la tabla delante.
- **De dónde:** sesión en vivo de la fase 3 · Enfoque, exposición y medición de resolución × formato (meta 002), 2026-10-22 (`Claude outputs/fases/002/fase-3-en-vivo.md`).
- **Qué haría falta:** si el script se vuelve a usar para elegir, cambiar la regla: contar los píxeles por encima de un umbral más bajo (p. ej. ≥ 250) o fijar un techo de brillo medio (~200), y desempatar por la exposición más corta, no la más larga (menos estela). Con su prueba sin cámara.
- **Prioridad:** media.

### B32 · Optimizar el tracker: la ventana limita a 19–25 fps en cualquier resolución
- **Qué:** en la fase 3 el tracking con ventana (`debug.show_window`) dio 19–25 fps en todos los modos, incluso 320×240 (18.9–19.2); sin ventana, 90 hasta 640×480 y 62–68 fps por encima (960×720 a 1280×960; 1280×960: 61.9 y 61.6). La captura da ~90 en todos los modos, incluidos 1920×1200. Explica los ~20–26 fps de P02. Ningún modo llegó a 88.2 fps con ventana en ninguna de las dos cámaras.
- **Por qué queda:** el plan lo manda a la meta de optimizar el tracker (decisión del autor, 2026-10-20); la fase 3 no toca `tracker.py` (principio 6). El autor eligió 1280×960 MJPG (P16) sabiendo que el tracking con ventana no llega a 90.
- **De dónde:** sesión en vivo de la fase 3 (meta 002), 2026-10-22; tablas en `Claude outputs/fases/002/fase-3-en-vivo.md`.
- **Qué haría falta:** en la meta de optimizar el tracker: medir qué cuesta más (dibujo, `imshow`, `waitKey(1)`, detección a 1280×960, 1-Euro) y sacarlo del bucle (ventana en otro hilo o a menor frecuencia, detección en una región de interés tras la primera, hilo propio de captura); extraer el paso por frame de `tracker.main()` a una función que usen el tracker y `medir_modos.medir_tracking` (hoy este repite el bucle); la línea base es la tabla de la fase 3 y se repite con intrínsecos reales (fases 4–5). Con la K real de la cámara 1 (fase 4, 1280×960, dodecaedro quieto): sin ventana 56 fps con pose casi siempre (99.8 %); la fase 3 daba 62 sin pose (la K nominal no resolvía la pose): más trabajo por frame. Con ventana, 21.4 fps.
- **Prioridad:** media.

### B34 · Las pruebas no deben poder abrir una cámara real aunque cambie un perfil
- **Qué:** nada impide hoy que una prueba llegue a `camera_backend.create_backend` o a `cv2.VideoCapture` con un perfil real y abra la cámara física. En la fase 4, al apuntar `tracker_config_gs1.yaml` a su `.yml`, `test_comprobar_escala.py::test_main_exige_argumentos_explicitos` (que suponía gs1 sin calibrar) pasó a abrir la cámara 1 real; el vigilante la cortó a los 60 s, sin procesos vivos después.
- **Por qué queda:** la fase 4 lo cerró solo en sus dos módulos (`test_calibrar_camara.py` y `test_comprobar_escala.py`: un fixture autouse cambia `create_backend` por uno que falla) y arregló las dos pruebas que suponían gs1 sin calibrar; el resto de la suite sigue expuesta a un cambio de perfil.
- **De dónde:** sesión en vivo de la fase 4 · Calibración de la cámara 1 y comprobación de escala (meta 002), paso 3, 2026-10-22 (`Claude outputs/fases/002/fase-4-en-vivo.md`).
- **Qué haría falta:** un fixture autouse en `codigo/tests/conftest.py` que niegue `camera_backend.create_backend` y `cv2.VideoCapture` a toda la suite, salvo las pruebas marcadas a propósito (y las que usan una cámara falsa); con su prueba de que un perfil real no abre nada.
- **Prioridad:** media.

### B35 · El criterio de escala por medias no mira la repetibilidad
- **Qué:** desde P20, `comprobar_escala.py` juzga la escala por la distancia entre las medias de las posiciones repetidas; la repetibilidad de cada grupo se calcula, se guarda y se imprime, pero no juzga. Así, `escala_gs1_sin_topes.json` (primera sesión de la cámara 1, sin topes) cumple por medias con +0.645 mm aunque cada marca se repitió solo a 1.7–2.0 mm: una sesión con el montaje moviéndose puede pasar.
- **Por qué queda:** P20 fijó el criterio por medias y la fase 5 · Calibración de la cámara 2 no lo cambia; las dos sesiones buenas (gs1 con topes 0.39 / 0.30 mm; gs2 0.70 / 0.33 mm) tienen buena repetibilidad.
- **De dónde:** recálculo `--desde-json` de la fase 5 · Calibración de la cámara 2 (meta 002), 2026-10-23 (`Claude outputs/fases/002/fase-5-panel.md`, «Pendiente o dudoso»).
- **Qué haría falta:** un tope a la repetibilidad (p. ej. ≤ 1 mm por grupo) que entre en `cumple`, o al menos mostrarla en «Última» de la ventana de calibración; con su prueba sobre el JSON sin topes.
- **Prioridad:** media.

### B36 · Cámara 2 con el punto principal 90 px sobre el centro
- **Qué:** la calibración de la cámara 2 (`intrinsecos_gs2_1280x960.yml`) da cy 389.81 px en una imagen de 960 (centro 480): 90 px arriba. Los dos detectores coinciden a ±0.66 px, así que no es ruido del ajuste; lo probable es que el lente quedó descentrado al remontarlo para enfocar. La cámara 1 da cy 488.87.
- **Por qué queda:** la calibración cumple (RMS 0.154 px, control 0.150 px, escala −0.37 mm) y vale mientras el lente no se mueva.
- **De dónde:** sesión en vivo de la fase 5 · Calibración de la cámara 2 (meta 002), 2026-10-23.
- **Qué haría falta:** vigilarlo: si el lente de la cámara 2 se gira o se saca, recalibrar; si la fase 6 · Comparación contra P02 da peor sd con la cámara 2 que con la 1, mirar aquí primero (remontar el lente centrado y recalibrar).
- **Prioridad:** baja.

## Cerrados

### B04 · Docs viejas o duplicadas en la raíz
- **Qué era:** `PROJECT_BRIEF.md` (2026-06-15, iter 4 temprana y el stylus 170–180) y `briefs/` (los reemplazan los `specs/`, ADR-020) en la raíz.
- **Cerrado:** 2026-10-19, por la fase 4 · textos de la meta 001 · limpieza y orden del repo: `git mv` a `docs/history/PROJECT_BRIEF.md` y `docs/history/briefs/` (con `historico/`), copia literal. Fuera de `docs/history/` y `specs/` solo los nombran `docs/ARCHITECTURE.md` §6 (dice que están en `docs/history/`), este BACKLOG, el ADR-020 (no se reescribe) y `documentos/auditoria_iter2/_archivo/` (histórico, P5).

### B06 · Rutas viejas fuera de `docs\`
- **Qué era:** `Dr.Milton` y `C:\dev\PoyectoNavegacion` en manuales, `codigo/readme.md`, scripts de `femto_pruebas/` y la cabecera de la punta vigente.
- **Cerrado:** 2026-10-19, por la fase 4 · textos de la meta 001 · limpieza y orden del repo: solo el prefijo pasa a `C:\Dev\OrtoMeta\PoyectoNavegacion` en 13 líneas de 7 archivos vivos (`codigo/readme.md`, `MANUAL_simplificado.md` con el snippet de §4.2, `MANUAL_webcam.md`, `MANUAL_femtobolt.md` y 3 scripts de `femto_pruebas/`) y en la cabecera de `StylusTipToDodecaedro_femto_dock.txt` (la de `respaldo_puntas/` y la original, fuera de git; sha y matriz intactos, `.npy` sin tocar). El grep del plan da 0 líneas. Por P5 = b quedan literales los históricos (15 apariciones en 9 archivos de `codigo/historico/`, `documentos/auditoria_iter2/` y `documentos/tecnicos/`). La prueba del snippet en Slicer quedó en B10.

### B01 · Scripts legacy y de diagnóstico sueltos en `iter4\`
- **Qué era:** 10 scripts de diagnóstico y legacy en `iter4\` que nadie importaba ni nombraba; los `test_*.py` no eran de pytest y confundían.
- **Cerrado:** 2026-10-19, por la fase 3 · movimientos de la meta 001 · limpieza y orden del repo: `git mv` (renombres, sin tocar contenido) de `hello_femtobolt`, `leer_calibracion_femtobolt`, `medir_sigma_depth`, `test_backends`, `test_distancia_conocida`, `test_distancia_regla`, `test_jitter_tracking`, `test_pivote`, `test_alineacion_d2c` y `test_deteccion_marker` a `codigo\historico\iter4_diagnosticos\`, con su `README.md`. Se quedan en `iter4\` `calibrar_topologia` y `limpiar_captura_fantasmas` (pasos de la GUIA y de los manuales). El docstring de `calibrar_rigid_body.py` y `codigo/readme.md` nombran la ruta nueva; `PROJECT_BRIEF.md` (va a `docs/history/` en la fase 4) y el ADR-010 conservan la vieja.

### B05 · Ruido local y archivos muertos en `iter4\data\`
- **Qué era:** ruido local, un calibrado de 0 bytes con nombre válido y geometrías o configs sin uso.
- **Cerrado:** 2026-10-19, por la fase 3 · movimientos de la meta 001 · limpieza y orden del repo: borrados `codigo\pytest-cache-files-xrzp8j4c\` (estaba versionado: 2 archivos de caché de pytest, `git rm --cached`) y `reference_dodecaedro_nuevo_calibrado.txt` (0 bytes); a `iter4\data\historico\` `reference_stylus_impreso_calibrado.txt` (movimiento de disco, ignorado) y, por P4 = a, `tracker_config_webcam.yaml` y `tracker_config_stylus_impreso.yaml` (`git mv`; el panel pasa de 4 a 2 perfiles). Se quedan `reference_dodecaedro_doctor.txt` (GUIA y `MANUAL_webcam.md`) y `_v2_fix`/`_v2_real` (procedencia de la geometría vigente). 0 archivos de 0 bytes en `iter4\data\`. La causa del calibrado vacío sigue abierta en B19.

### B02 · La suite está rota y no hay comprobación de «no cambió»
- **Qué era:** los 3 archivos de `codigo\tests\` no importaban (buscaban en `codigo\`) y no había replay sin cámara.
- **Cerrado:** 2026-10-19, por la fase 1 · suite y replay de la meta 001 · limpieza y orden del repo: `pytest.ini` y `conftest.py`, los 3 tests repuntados (22 desfasadas en `xfail`, B17), `py_compile` de `iter4\` y `gui\`, el selftest del panel y el replay sobre un recorte de `captura_ba.npz` con referencia guardada. 110 pruebas: 88 pasan, 22 `xfail`, en ~6 s.

### B03 · La calibración de punta vigente no tiene respaldo
- **Qué era:** `StylusTipToDodecaedro_femto_dock.npy/.txt` solo existía en este disco (`.gitignore`: las puntas son por equipo).
- **Cerrado:** 2026-10-19, por la fase 2 · respaldo de la punta de la meta 001 · limpieza y orden del repo (P3 = A', ADR-021): copia byte a byte en `codigo\iter4\data\respaldo_puntas\` con dos excepciones en `.gitignore`, fuera del glob del snippet de Slicer y de `estado.py`; sha256 del `.npy` igual al original (`a3c83203…5ebf`). Queda versionada con el commit del autor.

### B33 · Fracción con pose baja por encima de 640×480 con la K nominal
- **Qué era:** en la fase 3, a 960×720, 1280×720 y 1280×960 la fracción de frames con pose fue 0–7 % (cám. 1 a 1280×960: 6.9 %) con 4–5 markers, frente a 46.9 % y 68.0 % a 640×480. La pose se calculó con una K nominal (FOV 84°).
- **Cerrado:** 2026-10-22, por la fase 4 · Calibración de la cámara 1 y comprobación de escala (meta 002): lo explicaba la K nominal. Con `intrinsecos_gs1_1280x960.yml` (K real, campo horizontal ~74°), `medir_modos.py --intrinsecos` a 1280×960 da **99.8 %** con pose (99.84 % con ventana), con 4 markers y sin tocar el tracker. Los umbrales en píxeles de `estimar_pose_rigid_body` no hacen falta cambiarlos.

