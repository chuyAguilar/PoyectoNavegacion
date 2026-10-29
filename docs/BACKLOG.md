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
| B19 | `validar_prerrequisitos` deja un calibrado vacío | Alta | — |
| B20 | Slicer carga la punta por fecha | Alta | — |
| B23 | Explorar el tracker en una Jetson Orin Nano, con Slicer en BigDaddy | Baja | — |
| B24 | Frecuencia de la red (50/60 Hz) de las SVPRO, que OpenCV no fija | Baja | — |
| B25 | La sonda pierde los modos medidos si salta el tope | Media | — |
| B26 | Modos de las SVPRO que no sirven o no son estables | Baja | — |
| B30 | Leer la marca y aplicar los controles en una sola apertura DSHOW | Baja | — |
| B31 | El criterio de exposición de `medir_modos.py` favorece imágenes casi saturadas | Media | — |
| B35 | El criterio de escala por medias no mira la repetibilidad | Media | — |
| B36 | Cámara 2 con el punto principal 90 px sobre el centro | Baja | — |
| B39 | Con el detector de los perfiles gs1/gs2, un Marker0 sintético inclinado se lee como ID 87 o 115 | Baja | — |
| B40 | Instrumento y punta con un transform de nombre nuevo | Media | — |
| B41 | Runbook de Slicer con Marker0 y el registro nuevo | Media | — |
| B42 | Documentos del dodecaedro y la Femto que siguen en `documentos/` | Baja | — |
| B43 | Identificadores y mensajes en español en los módulos que solo se movieron | Baja | — |
| B44 | Las pruebas archivadas en `historico/iter4/dodecahedron/tests/` no corren | Baja | — |
| B45 | `femto_pruebas/`, `open3d` y `pyorbbecsdk2` siguen aunque la Femto esté archivada | Baja | — |
| B46 | `calibration/` importa `_vigilante` de `diagnostics/probe_camera.py` | Baja | — |
| B47 | `python -m camera.uvc` avisa de que el módulo ya estaba importado | Baja | — |
| B48 | Tras una desconexión de Slicer, la cola de `pyigtl` puede entregar poses viejas al reconectar | Baja | — |
| B49 | `python -m gui.panel --selftest` se cuelga si la salida no es UTF-8 | Baja | — |
| B50 | Las SVPRO bajan solas los fps con poca luz: un control UVC automático que el perfil no fija | Media | — |
| B51 | Con `--sync-capture` a 52 fps, Slicer recibió solo 5.8 Hz | Baja | — |
| B52 | «Detener tracker» con el tracker con ventana sigue dependiendo de encontrar la ventana por su título | Baja | — |
| B53 | Con `--stop-stdin`, la parada no se atiende mientras el tracker espera a Slicer | Baja | — |
| B54 | Slicer recibe como mucho ~65 Hz de Marker0, aunque el tracker envíe ~90 | Baja | — |
| B55 | Con el Marker0 de 100 mm y el perfil en 80, todas las distancias salen a escala 0.81 sin aviso | Media | — |
| B56 | `slicer/receive_marker0.py` dice que `pyigtl` bloquea si Slicer no está conectado | Baja | — |
| B57 | El `.json` de procedencia de las referencias del replay nombra rutas de `iter4/` | Baja | — |
| B58 | La ventana de «Calibrar con tablero» detecta la vista previa a resolución completa y va lenta sin tablero | Media | — |
| B59 | Los comentarios de los perfiles gs1 y gs2 dicen cosas que ya no valen | Baja | — |
| B60 | El repo es público, versiona el DICOM y ahora más personas tienen escritura y el clon completo | Alta | — |
| B61 | Los hooks de `peticiones/` se pueden saltar y GitHub no filtra por ruta | Media | — |
| B62 | Enviar una petición son cinco comandos a mano | Baja | — |
| B63 | Resumen periódico del estado para el jefe (`docs/ESTADO.md`) | Baja | — |
| B64 | Las pruebas de `equipo/` corren fuera de la suite | Baja | — |
| B65 | El guion de `consulta` cuesta dinero en cada corrida | Baja | — |

## Abiertos

### B07 · Marker0 rígido y corto
- **Qué:** el Marker0 en una varilla de ~21 cm convierte un giro de 12° en 45 mm de desfase del hueso.
- **Por qué queda:** es montaje físico, no código.
- **De dónde:** ADR-013; `docs/CONTEXT.md` §6.
- **Qué haría falta:** un soporte rígido pegado al objeto (`stl/BaseMarcador/`) y medir el RMS antes y después.
- **Prioridad:** alta (da resultados equivocados también en paired-point).

### B08 · Runbook para el contexto Femto
- **Qué:** `documentos/historico/MANUAL_simplificado.md` opera el contexto doctor; no hay uno para `tracker_config.yaml`. Desde la meta 003 la Femto y su perfil están archivados (`codigo/historico/iter4/femto/`, ADR-025): el runbook vigente que falta es B41.
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
- **Qué:** la captura del asistente con IDs nuevos y la calibración de punta por dock desde el panel. (La calibración de cámara quedó verificada en vivo: `calibrar_camara.py` por línea de comandos en la fase 4 · Calibración de la cámara 1 y comprobación de escala, 2026-10-22, y desde el panel, con la ventana de tres pasos, en la fase 5 · Calibración de la cámara 2, 2026-10-23: cámara 2 RMS 0.154 px, control 0.150 px; meta 002.) (La fase 6 · Comparación contra P02 y archivo de los perfiles viejos, 2026-10-23, verificó el tracker desde el panel con el perfil gs1 —arranque, ventana, «Detener» por 'q', salida limpia— pero no cierra lo de arriba.) (El snippet de `MANUAL_simplificado.md` §4.2 —hoy en `documentos/historico/`— con la ruta nueva, que se sumó en la fase 4 de la meta 001, quedó verificado en vivo por el autor el 2026-10-19: traslación [0.904, 5.471, −201.808] mm, la esperada; `docs/PRUEBAS.md` P01.)
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
- **Qué haría falta:** retomar si se cambia de stylus. Su config (`tracker_config_stylus_impreso.yaml`) y su geometría calibrada (local, fuera de git) están en `codigo/historico/iter4/old_profiles/` desde la fase 3 de la meta 003 (antes, desde la meta 001, en la carpeta de perfiles viejos de entonces). Para usarlo hace falta el código multi-marker archivado (B40): devolver el config a `codigo/profiles/` (el panel solo ve `profiles/tracker_config*.yaml`) y poner sus rutas relativas a `codigo/`.
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

### B19 · `validar_prerrequisitos` deja un calibrado vacío
- **Qué:** en `calibrar_rigid_body.py` y `captura_calibracion.py` abre la salida en modo `"ab"` antes de correr para comprobar que se puede escribir; si el proceso falla después, queda un archivo de 0 bytes con nombre válido (el origen del `reference_dodecaedro_nuevo_calibrado.txt` de B05).
- **Por qué queda:** la meta 001 no toca la lógica de los scripts activos.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** comprobar la carpeta sin crear el archivo y escribir solo al final.
- **Meta 003, fase 3 (2026-10-23):** `calibrar_rigid_body.py` y `captura_calibracion.py` se archivaron con el dodecaedro en `codigo/historico/iter4/dodecahedron/`: ya no los lanza nada vivo. Queda para cuando el instrumento nuevo (B40) vuelva a tener un BA; el autor decide si se cierra.
- **Prioridad:** alta (un calibrado vacío con nombre válido puede tomarse por bueno).

### B20 · Slicer carga la punta por fecha
- **Qué:** el snippet de `documentos/historico/MANUAL_simplificado.md` §4.2 cargaba el `StylusTipToDodecaedro*.npy` más reciente por fecha de la carpeta de datos de entonces (`iter4\data\`, hoy archivada); un `git pull`, una copia o un movimiento cambian cuál, sin aviso en Slicer (`estado.py` sí avisa).
- **Por qué queda:** toca lo que se carga en Slicer: necesita verificación en vivo.
- **De dónde:** plan de la meta 001 · limpieza y orden del repo.
- **Qué haría falta:** nombrar la punta explícita en el snippet y mover las puntas viejas (`StylusTipToDodecaedro.npy`, `_2`, `_divot`, `_viejo_dock`, del dodecaedro viejo) a `data\historico\`.
- **Meta 003, fase 3 (2026-10-23):** el manual está en `documentos/historico/` (fase 2) y todas las puntas en `codigo/historico/iter4/dodecahedron/data/`; la cadena ya no publica el dodecaedro. Vale para la punta del instrumento nuevo (B40); el autor decide si se cierra.
- **Prioridad:** alta.

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
- **Qué:** en `sondear_camara.py` (desde la meta 003, `codigo/diagnostics/probe_camera.py`), `estado["modos"]` se asigna cuando `sondear_modos` termina; si el vigilante (`_vigilante`) salta antes, el JSON queda con `"timeout": true` y sin ninguna fila. Pasó en `modos_gs1_msmf_mjpg.json` y `modos_gs1_msmf_yuy2.json` (sesión del 2026-10-20): sus cifras solo quedaron en la consola y en `Claude outputs/fases/002/fase-1-en-vivo.md`. Además el presupuesto (`ABRIR_S + segundos + MARGEN_MODO_S` = 21 s con 5 s de captura) se queda corto: por MSMF a 90 fps cada modo tardó ~44–49 s (`total_s`; abrir ~10–11 s), y la comprobación por modo (`ABRIR_S + segundos`) no cuenta el resto.
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

### B30 · Leer la marca y aplicar los controles en una sola apertura DSHOW
- **Qué:** `WebcamBackend.open()` abre la cámara por DSHOW dos veces antes del video: una para leer la marca (`capa.leer`, 1.11–1.48 s) y otra para aplicar los ajustes (`capa.aplicar`, 1.26–1.57 s).
- **Por qué queda:** es solo tiempo (~1.2 s por arranque) y la fase 2b ya cumple su criterio.
- **De dónde:** sugerencia del «implementa» de la fase 2b · Perfiles por cámara: identidad, ajustes y tamaño al abrir (meta 002), medida en su sesión en vivo, 2026-10-22.
- **Qué haría falta:** un método de la capa que lea la marca, pare si no coincide y, sin cerrar, aplique los controles; con su prueba sin cámara del orden (leer marca → parar o escribir) y la misma garantía de que con marca distinta no se escribe nada.
- **Prioridad:** baja.

### B31 · El criterio de exposición de `medir_modos.py` favorece imágenes casi saturadas
- **Qué:** `elegir_exposicion` (en `medir_modos.py`; desde la meta 003, `codigo/diagnostics/measure_modes.py`) descarta lo que satura más de 1 % de los píxeles a 255 sobre el dodecaedro y, entre empates de markers, elige la exposición más larga. Con MJPG la imagen se queda en 250–254 sin llegar a 255, y la fracción a 255 no lo ve. En la sesión en vivo (1280×960, caja en nivel 2) eligió 3.906 ms (brillo medio 244–245, casi quemada) y la cámara 2 sola 0.488; el autor eligió 0.977 ms (brillo ~170, los mismos markers, ~4 veces menos estela de movimiento; P15).
- **Por qué queda:** el autor ya eligió a mano y la meta 002 no vuelve a elegir exposición; no da un resultado equivocado mientras la elija una persona con la tabla delante.
- **De dónde:** sesión en vivo de la fase 3 · Enfoque, exposición y medición de resolución × formato (meta 002), 2026-10-22 (`Claude outputs/fases/002/fase-3-en-vivo.md`).
- **Qué haría falta:** si el script se vuelve a usar para elegir, cambiar la regla: contar los píxeles por encima de un umbral más bajo (p. ej. ≥ 250) o fijar un techo de brillo medio (~200), y desempatar por la exposición más corta, no la más larga (menos estela). Con su prueba sin cámara.
- **Prioridad:** media.

### B35 · El criterio de escala por medias no mira la repetibilidad
- **Qué:** desde P20, `comprobar_escala.py` (desde la meta 003, `codigo/calibration/check_scale.py`) juzga la escala por la distancia entre las medias de las posiciones repetidas; la repetibilidad de cada grupo se calcula, se guarda y se imprime, pero no juzga. Así, `escala_gs1_sin_topes.json` (primera sesión de la cámara 1, sin topes) cumple por medias con +0.645 mm aunque cada marca se repitió solo a 1.7–2.0 mm: una sesión con el montaje moviéndose puede pasar.
- **Por qué queda:** P20 fijó el criterio por medias y la fase 5 · Calibración de la cámara 2 no lo cambia; las dos sesiones buenas (gs1 con topes 0.39 / 0.30 mm; gs2 0.70 / 0.33 mm) tienen buena repetibilidad.
- **De dónde:** recálculo `--desde-json` de la fase 5 · Calibración de la cámara 2 (meta 002), 2026-10-23 (`Claude outputs/fases/002/fase-5-panel.md`, «Pendiente o dudoso»).
- **Qué haría falta:** un tope a la repetibilidad (p. ej. ≤ 1 mm por grupo) que entre en `cumple`, o al menos mostrarla en «Última» de la ventana de calibración; con su prueba sobre el JSON sin topes.
- **Prioridad:** media.

### B36 · Cámara 2 con el punto principal 90 px sobre el centro
- **Qué:** la calibración de la cámara 2 (`intrinsecos_gs2_1280x960.yml`) da cy 389.81 px en una imagen de 960 (centro 480): 90 px arriba. Los dos detectores coinciden a ±0.66 px, así que no es ruido del ajuste; lo probable es que el lente quedó descentrado al remontarlo para enfocar. La cámara 1 da cy 488.87.
- **Por qué queda:** la calibración cumple (RMS 0.154 px, control 0.150 px, escala −0.37 mm) y vale mientras el lente no se mueva.
- **De dónde:** sesión en vivo de la fase 5 · Calibración de la cámara 2 (meta 002), 2026-10-23.
- **Qué haría falta:** vigilarlo: si el lente de la cámara 2 se gira o se saca, recalibrar; si la fase 6 · Comparación contra P02 da peor sd con la cámara 2 que con la 1, mirar aquí primero (remontar el lente centrado y recalibrar). **Fase 6 (2026-10-23):** no se nota en el temblor; la cámara 2 dio la mejor sd z (1.08–1.15 mm) y la peor fue la 1 (B37). Sigue solo como vigilancia.
- **Prioridad:** baja.

### B39 · Con el detector de los perfiles gs1/gs2, un Marker0 sintético inclinado se lee como ID 87 o 115
- **Qué:** en la prueba sin cámara de la fase 1 de la meta 003, un Marker0 (ID 0, `DICT_ARUCO_MIP_36h12`) renderizado limpio a 450 mm con K sintética (fx 800, 640×480) e inclinado 15–20° se decodifica como 87 o 115 en 5–6 de 12 frames con los parámetros del detector de `tracker_config_gs1.yaml`; con `DetectorParameters()` por defecto, 12 de 12 como 0. Inclinado 5°, 12 de 12 como 0 también con los del perfil. La lista blanca descarta 87 y 115, así que el efecto sería perder el frame, no una pose falsa; no se ha visto lo contrario (otro marker leído como 0).
- **Por qué queda:** es sobre imágenes sintéticas, no reales; la fase 1 no cambia el detector (principio 6, P6 = a).
- **De dónde:** `tests/test_pose_log.py`, fase 1 · Línea base de Marker0 en vivo, antes de mover nada (meta 003), 2026-10-23.
- **Acotado (2026-10-23, línea base en vivo):** con Marker0 real de frente (≤ 10°) a ~37–38 cm, 100 % de los frames con pose y ID 0 en las dos cámaras (gs1 977 y 628 frames; gs2 973 y 1057); no apareció ni un 87 o 115. No se ha probado inclinado 15–20° con imágenes reales, así que no se cierra: solo se sabe que de frente no pasa.
- **Qué haría falta:** una corrida en vivo con Marker0 inclinado 15–20° (se graba con `--record`; el resumen de `pose_log.py` da la fracción con pose) y, si queda por debajo de 95 %, buscar qué parámetro lo causa (`polygonal_approx_accuracy_rate` 0.05, `max_erroneous_bits_in_border_rate` 0.40, ventanas del umbral), una variable a la vez, con el replay de detección de la fase 1. Se puede hacer en la sesión en vivo de otra fase de la meta 003 sin costo extra.
- **Prioridad:** baja (sube si la corrida inclinada da menos del 95 % con pose o si aparece otro ID leído como 0).

### B40 · Instrumento y punta con un transform de nombre nuevo
- **Qué:** volver a seguir un instrumento con punta, publicado con un transform de nombre nuevo y su ADR (principio 6).
- **Por qué queda:** el spec de la meta 003 descarta el dodecaedro y deja el tracker solo con Marker0; el instrumento es otra meta (ADR-025).
- **De dónde:** spec y plan de la meta 003; archivado en la fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker), 2026-10-23.
- **Qué haría falta:** su spec; el punto de partida es `codigo/historico/iter4/dodecahedron/` (geometrías, BA, punta por dock) y, desde la fase 4, `pose_rigid_body.py`. Al hacerlo, mirar B19, B20 y B37.
- **Prioridad:** media.

### B41 · Runbook de Slicer con Marker0 y el registro nuevo
- **Qué:** un runbook vigente para Slicer: hoy `codigo/slicer/README.md` solo cubre recibir Marker0, y `MANUAL_simplificado.md` está archivado en `documentos/historico/` (meta 003, fase 2).
- **Por qué queda:** la punta, el registro y la navegación se rehacen en sus metas (ADR-025).
- **De dónde:** plan de la meta 003 (P5 = b).
- **Qué haría falta:** escribirlo con el instrumento nuevo (B40) y el registro, en `codigo/slicer/`.
- **Prioridad:** media.

### B42 · Documentos del dodecaedro y la Femto que siguen en `documentos/`
- **Qué:** `GUIA_calibrar_dodecaedro_propio.md`, `convencion_dodecaedro_compartido.md` y `MANUAL_femtobolt.md` siguen en `documentos/` aunque su código esté archivado.
- **Por qué queda:** no estorban; el plan de la meta 003 solo movía el manual del doctor.
- **De dónde:** plan de la meta 003.
- **Qué haría falta:** `git mv` a `documentos/historico/` si estorban.
- **Prioridad:** baja.

### B43 · Identificadores y mensajes en español en los módulos que solo se movieron
- **Qué:** las funciones, variables y mensajes de `camera/`, `calibration/`, `diagnostics/` y `gui/` siguen en español (y algunos mensajes nombran el script viejo, p. ej. «calibra primero (calibrar_camara.py)»); también los nombres de las pruebas que ya existían. `CLAUDE.md` pide identificadores en inglés.
- **Por qué queda:** la fase 3 cambia el sitio, no el cuerpo (plan de la meta 003, P8).
- **De dónde:** fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker), 2026-10-23.
- **Qué haría falta:** renombrar en un cambio aparte, con la suite como red.
- **Prioridad:** baja.

### B44 · Las pruebas archivadas en `historico/iter4/dodecahedron/tests/` no corren
- **Qué:** las cuatro pruebas archivadas (y `test_replay.py`, que usa `tests/replay_util.py`) conservan los imports de `iter4/`: son registro.
- **Por qué queda:** el plan las archiva sin reescribirlas.
- **De dónde:** fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker), 2026-10-23.
- **Qué haría falta:** si el instrumento nuevo (B40) reusa el BA, reescribirlas contra su código.
- **Prioridad:** baja.

### B45 · `femto_pruebas/`, `open3d` y `pyorbbecsdk2` siguen aunque la Femto esté archivada
- **Qué:** el backend y el perfil de la Femto están en `codigo/historico/iter4/femto/`, pero `femto_pruebas/` y sus dependencias siguen en el repo y en `requirements.txt`.
- **Por qué queda:** P4 de la meta 003 = a: no se tocan en esta meta (ADR-014, en pausa).
- **De dónde:** plan de la meta 003.
- **Qué haría falta:** decidir si la rama de depth se retoma; si no, archivarla y quitar las dependencias.
- **Prioridad:** baja.

### B46 · `calibration/` importa `_vigilante` de `diagnostics/probe_camera.py`
- **Qué:** `calibrate_camera.py` y `check_scale.py` importan el vigilante de tiempo de la sonda: una dependencia cruzada heredada de `iter4/`.
- **Por qué queda:** la fase 3 solo mueve.
- **De dónde:** plan de la meta 003.
- **Qué haría falta:** moverlo a un módulo común si estorba.
- **Prioridad:** baja.

### B47 · `python -m camera.uvc` avisa de que el módulo ya estaba importado
- **Qué:** `camera/__init__.py` importa `camera.uvc` (para apagar la aceleración de MSMF antes que cv2), así que `python -m camera.uvc` (listar las cámaras) da `RuntimeWarning: 'camera.uvc' found in sys.modules ...` y ejecuta el módulo dos veces. Lista bien; el aviso es ruido.
- **Por qué queda:** no cambia lo que hace; lo vio la fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker), 2026-10-23.
- **De dónde:** fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker).
- **Qué haría falta:** lanzar la lista desde `diagnostics.probe_camera --puertos`, o un `__main__` aparte.
- **Prioridad:** baja.

### B48 · Tras una desconexión de Slicer, la cola de `pyigtl` puede entregar poses viejas al reconectar
- **Qué:** desde la fase 7 · Subir los fps con ventana (meta 003 · Arquitectura y optimización del tracker) `IgtlSender.send` encola con `send_message(wait=False)` y no encola si `is_connected()` es falso. `pyigtl` 0.3.1 solo marca la desconexión cuando falla un `sendall` (o al parar), así que entre que Slicer cierra y el primer envío falla pueden quedar en la cola (`deque(maxlen=100)`) unas pocas poses, y al reconectar Slicer las recibiría antes que las nuevas. Con Slicer conectado todo el rato no pasa nada; el tracker está pensado para arrancar con Slicer ya conectado (espera con tope y aborta si no llega).
- **Por qué queda:** el autor eligió E1 (encolar sin esperar, con guarda) frente a un envío propio (E3); vaciar la cola al reconectar exige tocar el objeto interno de `pyigtl` (`outgoing_messages`) o reemplazar el transporte (ADR-028 lo preveía para E3).
- **De dónde:** fase 7 · Subir los fps con ventana (meta 003), 2026-10-24, al escribir la guarda de `transport/igtl.py`.
- **Qué haría falta:** medirlo en vivo (desconectar y reconectar el conector en Slicer con el tracker corriendo) y, si estorba, vaciar `outgoing_messages` bajo su candado al detectar `is_connected()` falso, o pasar a E3.
- **Al día (2026-10-25, primera parte en vivo de la fase 7):** sin desconexiones, gs2 con `--sync-capture` a 52 fps dio 5.8 Hz en Slicer; puede venir de las ráfagas de `wait=False`, pero es otra cosa: va aparte en B51.
- **Prioridad:** baja.

### B49 · `python -m gui.panel --selftest` se cuelga si la salida no es UTF-8
- **Qué:** con la salida redirigida (Bash, `> archivo`), `print` usa cp1252; la etiqueta «Última: ✔ …» de la calibración trae `✔`, el `print` del temporizador del selftest lanza `UnicodeEncodeError`, nunca llega a `app.quit()` y el proceso queda vivo para siempre (dos procesos huérfanos). Con `PYTHONIOENCODING=utf-8` termina en 1.2 s con exit 0 y los 3 argv `-m`.
- **Por qué queda:** no cambia la fase 7; en consola interactiva no pasa. Lo vio «verifica» de la fase 7 · Subir los fps con ventana (meta 003).
- **De dónde:** fase 7 · Subir los fps con ventana, 2026-10-25.
- **Qué haría falta:** en `dump_y_cerrar`, `try/finally` que cierre siempre, o `sys.stdout.reconfigure(encoding="utf-8")` en el selftest; y un tope en el arranque de quien lo corra.
- **Prioridad:** baja.

### B50 · Las SVPRO bajan solas los fps con poca luz: un control UVC automático que el perfil no fija
- **Qué:** con la caja de luz por debajo del máximo (nivel 2–3), las dos SVPRO entregan 22–31 fps aunque el perfil pida 90 y la exposición manual sea de 0.977 ms; con la caja al máximo, 90 (gs1 estable; gs2 una vez estable y otra cayendo a ~30 a mitad de la corrida). Lo mide el hilo de captura (`camara X fps`), así que es la cámara, no el bucle. El perfil no escribe ningún ajuste al abrir (`escritos: ninguno`): lo que baja los fps es algún control automático que el perfil no lista, probablemente la prioridad de exposición (UVC *auto exposure priority*) o una prioridad de fps del firmware.
- **Por qué queda:** la fase 7 · Subir los fps con ventana (meta 003 · Arquitectura y optimización del tracker) no lo arregla con código: la regla es trabajar con la caja al máximo (`docs/CONTEXT.md` §4.20). Decisión del autor, 2026-10-25.
- **De dónde:** primera parte en vivo de la fase 7, 2026-10-25 (`Claude outputs/fases/003/fase-7-en-vivo.md`, «C0, la captura sola»). **Al día (2026-10-25, segunda parte):** pedir 60 fps dio 29 en gs1 con la caja al máximo (28.9 de cámara): la SVPRO no tiene modo de 60 a 1280×960 MJPG y MSMF baja al de 30; los perfiles siguen a 90 (`clarify.md` P11). **Al día (2026-10-25, fase 8a · Un botón por modo en el panel, en vivo):** con la caja al máximo y el tracker con ventana, la cámara bajó al final de la corrida a 75.7 (gs1) y 77.0 fps (gs2), tras empezar a ~90; no se miró por qué (puede ser este mismo control o la carga del bucle con ventana). Lo anotó el cierre de la meta 003 (fase 8c). **Al día (2026-10-26, fase 2b · «Verificar IDs y colocar la cámara» marca la cámara en verde y se quita «Probar cámara», meta 004 · Cómo funciona el tracker, en vivo):** con la caja al máximo, la primera corrida de «Verificar IDs» marcó 30 fps y la segunda 89.8 (`[IDs] camara 89.8 fps`, exit 0); el autor decidió dejarlo aquí sin investigar.
- **Qué haría falta:** buscar el control: leer por DSHOW y en AMCap lo que expone la cámara (la exposición automática y su prioridad, PowerLine, B24), con la caja en nivel 2 y al máximo, y ver cuál cambia los fps de captura (`diagnostics.measure_modes --modos` lee `fps_captura`), una variable a la vez. Si se puede fijar, añadirlo a `controls` de los dos perfiles con su prueba sin cámara; si solo se fija a mano, anotarlo en `CONTEXT.md` §4 como el PowerLine.
- **Prioridad:** media.

### B51 · Con `--sync-capture` a 52 fps, Slicer recibió solo 5.8 Hz
- **Qué:** en la corrida gs2 E1b de la fase 7 · Subir los fps con ventana (captura en el bucle, `--sync-capture`, envío con `wait=False`), el tracker envió 1 559 poses en 30 s (51.9 fps, 100 % con pose, «sin cliente 0») y `receive_marker0.py` contó 5.8 Hz. En las corridas con el hilo de captura, los Hz en Slicer siguen a los fps (46.0, 56.9, 50.4, 30.9). Sin explicar: pueden ser las ráfagas de `wait=False` (B48), Slicer con el bucle de eventos ocupado o un arranque tardío de `run()`.
- **Por qué queda:** `--sync-capture` es solo para comparar; el modo por defecto entrega. La segunda parte en vivo de la fase 7 no lo repitió (se cerró con lo medido, `clarify.md` P11).
- **De dónde:** primera parte en vivo de la fase 7 (meta 003 · Arquitectura y optimización del tracker), 2026-10-25 (`Claude outputs/fases/003/fase-7-en-vivo.md`).
- **Al día (2026-10-25, fase 8b):** el techo de ~65 Hz en Slicer (B54) no lo explica: a 52 fps los 5.8 Hz quedan muy por debajo de ese techo. Sigue sin explicar.
- **Qué haría falta:** repetir gs2 con `--sync-capture` y luz máxima, con `run(seconds=20)` arrancado antes del tracker, y comparar los Hz con los envíos; si se repite, contar en Slicer los mensajes por segundo (no solo los `TransformModifiedEvent`) para saber si se pierden o se agrupan.
- **Prioridad:** baja (sube a alta si se ve sin `--sync-capture`: Slicer no seguiría a Marker0).

### B52 · «Detener tracker» con el tracker con ventana sigue dependiendo de encontrar la ventana por su título
- **Qué:** con la receta del tracker con ventana, «Detener tracker» (y «Detener proceso») manda `q` a la ventana por su título (`FindWindowW`); si no la encuentra en 4 s (`ESPERA_Q_S`), cae en `terminate()`, que no corre el `finally` (la cámara y el 18944 los libera el sistema al morir el proceso, no el tracker; principio 9). El tracker sin ventana ya tiene un camino limpio siempre: `--stop-stdin`.
- **Por qué queda:** la fase 7b · Botones de tracker sin ventana y de vista previa para posicionar las cámaras (meta 003 · Arquitectura y optimización del tracker) cambia una variable a la vez: `--stop-stdin` solo en la receta sin ventana. Decidido en su plan (`plan.md`, «Lo que va al BACKLOG», 2026-10-25).
- **De dónde:** fase 7b, 2026-10-25.
- **Qué haría falta:** añadir `--stop-stdin` y `stop_stdin=True` también a `receta_tracker` (la entrada estándar primero y, si no responde, `q` a la ventana), con su prueba del `Lanzador` y una corrida en vivo con ventana.
- **Prioridad:** baja.

### B53 · Con `--stop-stdin`, la parada no se atiende mientras el tracker espera a Slicer
- **Qué:** el hilo de `--stop-stdin` arranca antes de la espera a Slicer, pero el bucle solo mira el evento una vez abierto: si el panel pide «Detener tracker» mientras el tracker espera a Slicer (hasta `--slicer-timeout`, 30 s), el `q` queda leído y el tracker no sale hasta que Slicer llega (entonces abre la cámara y sale en la primera vuelta) o hasta el tope (código 3). El panel espera 8 s (`ESPERA_STDIN_S`) y cae en `terminate()`; la cámara todavía no estaba abierta, así que lo único que se corta en duro es el servidor del 18944, que el sistema libera al morir el proceso.
- **Por qué queda:** atenderlo pide que `IgtlSender.wait_for_client` (la cadena, principio 6) acepte un evento de parada; la fase 7b no toca `transport/`. Visto al implementar la fase 7b (meta 003 · Arquitectura y optimización del tracker), 2026-10-25.
- **De dónde:** fase 7b, 2026-10-25.
- **Qué haría falta:** pasar el evento a `wait_for_client(timeout_s, stop=None)` y salir con un código propio si se pide parar; su prueba sin cámara con el emisor falso.
- **Prioridad:** baja.

### B54 · Slicer recibe como mucho ~65 Hz de Marker0, aunque el tracker envíe ~90
- **Qué:** con el tracker a ~82–90 fps, `receive_marker0.py` cuenta 64.3–67.4 Hz en Slicer (intervalo p50 16.0 ms, el tic de Windows de 15.6). La fase 8b · De dónde sale el techo de ~66 Hz en Slicer (meta 003 · Arquitectura y optimización del tracker) lo midió: el emisor (pyigtl) agrupa los mensajes en 64.1 ráfagas/s y con `timeBeginPeriod(1)` saca ~88, pero Slicer sigue en 64.3 Hz sin cámara y 52.0 con esa opción (una corrida). No se pierde nada en el tracker (974 envíos = 974 recibidos en gs1). Conclusión R2: el techo es de Slicer.
- **Por qué queda:** con ~65 Hz la cadena llega y se mueve (criterio del spec), y los 65 Hz superan los fps con ventana (55–62). Subirlo no está en la meta; por P18 no hay fase 8b2.
- **De dónde:** fase 8b, 2026-10-25 (`specs/003-*/resultados.md`; `Claude outputs/fases/003/fase-8b-en-vivo.md`).
- **Qué haría falta:** si alguna vez hacen falta más de 65 Hz en Slicer: mirar en SlicerOpenIGTLink cómo y a qué ritmo importa los mensajes a la escena (hilo de importación, refresco del conector) y si hay un ajuste; repetir el banco (`python -m diagnostics.igtl_rate bench … --external`) tras cada cambio; explicar los 52.0 Hz con `--timer-1ms`. El remedio en el tracker (timer de 1 ms o hilo de envío propio) no sube nada mientras Slicer no cambie.
- **Prioridad:** baja.

### B55 · Con el Marker0 de 100 mm y el perfil en 80, todas las distancias salen a escala 0.81 sin aviso
- **Qué:** el autor tiene dos Marker0, de 80 mm y de 100 mm (98.6 con calibrador), con el mismo ID. Los perfiles dicen `size_mm: 80.0`. Con el de 100 delante, la pose sale a escala 80 / 98.6 = 0.811: posiciones, distancias y sd. Nada lo detecta: el tamaño del marker y la distancia a la cámara no se distinguen en una sola imagen. En la comprobación «se mueve» de la fase 8c (meta 003 · Arquitectura y optimización del tracker), 50 mm reales salieron como 40.28.
- **Por qué queda:** se vio al cerrar la meta; arreglarlo es una decisión (cuál se usa) y quizá código. Mientras tanto, la regla es usar el Marker0 de 80 mm.
- **De dónde:** fase 8c, 2026-10-26 (`specs/003-*/resultados.md`).
- **Qué haría falta:** decidir con cuál se trabaja y guardar o marcar el otro; o darle otro ID al de 100 (ArUco permite IDs distintos) y su `size_mm` en el perfil, para que el tracker no pueda confundirlos; o una comprobación de escala en «Verificar IDs y colocar la cámara» con una distancia conocida.
- **Decisión del autor (2026-10-26):** se trabaja con el Marker0 de 80 mm (el de los perfiles) y el de 100 se guarda y se marca. Con eso el riesgo queda en el procedimiento, no en el código.
- **Prioridad:** media (era alta; baja a media con la decisión del autor). Vuelve a alta si hace falta usar otro tamaño: entonces, otro ID y su `size_mm`.

### B56 · `slicer/receive_marker0.py` dice que `pyigtl` bloquea si Slicer no está conectado
- **Qué:** el docstring de `codigo/slicer/receive_marker0.py` cita `CONTEXT.md` §4.5 de antes de ADR-028 («pyigtl bloquea el bucle»). Desde la fase 7 de la meta 003 · Arquitectura y optimización del tracker, el tracker espera a Slicer con tope (`--slicer-timeout`, 30 s) y, si no llega, aborta con código 3 sin abrir la cámara.
- **Por qué queda:** es un archivo de la cadena (principio 6) y la meta 004 · Cómo funciona el tracker no la toca; solo despista al leerlo, no cambia nada en vivo.
- **De dónde:** visto al planear la meta 004 (2026-10-26, `specs/004-como-funciona/plan.md`); anotado en su fase 1 · El mapa del proyecto.
- **Qué haría falta:** corregir el docstring en una fase que ya toque `codigo/slicer/` (p. ej. la del instrumento, B40), con su verificación de la cadena.
- **Prioridad:** baja.

### B57 · El `.json` de procedencia de las referencias del replay nombra rutas de `iter4/`
- **Qué:** `codigo/tests/data/marker0_gs{1,2}_reference.json` dicen `profile: iter4/…` y `calibration_file: …\codigo\iter4\data\…`, rutas de antes de ADR-027. Los sha256 que guardan siguen valiendo (son los de `data/intrinsecos_gs{1,2}_1280x960.yml`).
- **Por qué queda:** regenerar la referencia es un cambio visible y a propósito (`python -m tests.replay_util reference-marker0 … --overwrite`); la meta 004 · Cómo funciona el tracker no toca `tests/data/`. Solo despista.
- **De dónde:** visto al planear la meta 004 (2026-10-26, `specs/004-como-funciona/plan.md`); anotado en su fase 1 · El mapa del proyecto.
- **Qué haría falta:** al regenerar la referencia por otro motivo, comprobar que el `.json` nuevo nombra las rutas de hoy; o una nota en `tests/data/` que diga que las rutas son de entonces.
- **Prioridad:** baja.

### B58 · La ventana de «Calibrar con tablero» detecta la vista previa a resolución completa y va lenta sin tablero
- **Qué:** `calibration/calibrate_camera.py` (la captura de vistas, paso 2 de «Calibrar cámara») corre en cada frame `detectar_esquinas(gray, …, "clasico", rapido=True)` sobre el frame entero de 1280×960, como hacía `check_scale.py` antes de la fase 2c. Medido sin cámara con ese mismo detector: 245–257 ms por frame con Marker0 delante y sin tablero (~4 fps de ventana), 73 ms con un gris liso, 5 ms con el tablero. Con el tablero delante va fluida; entre una vista y otra, si el tablero sale del cuadro, se arrastra.
- **Por qué queda:** la fase 2c · «Comprobar escala con regla» sin congelarse y con vista previa fluida (meta 004 · Cómo funciona el tracker) solo toca `check_scale.py` (P11); la ventana de calibración no se pidió.
- **De dónde:** visto al implementar la fase 2c, 2026-10-26 (`Claude outputs/fases/004/fase-2c.md`).
- **Qué haría falta:** usar en esa ventana `check_scale.PreviaEnHilo` (o moverla a un módulo común de `calibration/`): la detección de la vista previa a la mitad y en otro hilo; la captura con ESPACIO sigue con el detector de la calibración sobre el frame completo. Su prueba con una cámara falsa, como las de la fase 2c, y un minuto en vivo.
- **Prioridad:** media.

### B59 · Los comentarios de los perfiles gs1 y gs2 dicen cosas que ya no valen
- **Qué:** los comentarios de `codigo/profiles/tracker_config_gs1.yaml` y `_gs2.yaml` dicen que «la ventana del tracker es el cuello, 19-25 fps» (la fase 6 de la meta 003 · Arquitectura y optimización del tracker vio que eran el envío y la captura, y hoy con ventana van a 55–62 fps), que la caja de luz va «en nivel 2» (hoy el tracking va con la caja al máximo, `docs/CONTEXT.md` §4.20) y que `tracker.py` lanzado a mano necesita `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` en el entorno (desde B28, `tracker.py` importa `camera` antes que `cv2` y la apaga solo). Los valores de los perfiles están bien; solo los comentarios despistan.
- **Por qué queda:** los perfiles son de la cadena (principio 6) y la meta 004 · Cómo funciona el tracker no los toca.
- **De dónde:** visto al escribir la fase 3 · La explicación y el glosario (meta 004), 2026-10-26.
- **Qué haría falta:** poner al día esos comentarios en una fase que ya toque `profiles/`, comprobando con la suite que el perfil leído no cambia.
- **Prioridad:** baja.

### B60 · El repo es público, versiona el DICOM y ahora más personas tienen escritura y el clon completo
- **Qué:** el repo `chuyAguilar/PoyectoNavegacion` es público y versiona el DICOM y el volumen CT (ADR-019). Desde la meta 005, Kike, Armando y el doctor Milton tienen escritura y un clon completo en sus máquinas (P6), con los datos de paciente dentro.
- **Por qué queda:** decisión del autor de mantenerlo así (2026-10-27); los tres son del equipo médico (P1), así que encaja con ADR-019. Mover el DICOM o hacer el repo privado no entra en la meta 005.
- **De dónde:** plan de la meta 005 · Agente de consulta para el equipo y buzón de peticiones (`specs/005-equipo-consulta/`, «Lo que va al BACKLOG»), 2026-10-28.
- **Qué haría falta:** sacar los datos de paciente del árbol y del historial (reescritura acordada con el autor), o hacer el repo privado, con su ADR.
- **Prioridad:** alta (P4).

### B61 · Los hooks de `peticiones/` se pueden saltar y GitHub no filtra por ruta
- **Qué:** el único seguro de ADR-034 son los hooks `pre-commit` y `pre-push` de `equipo/hooks/`. Se saltan con `--no-verify`, quitando `core.hooksPath`, editando el hook o empujando con otra herramienta, y en un repo personal y público GitHub no tiene reglas de push por ruta. Con libertad total (P9), un agente en la máquina de un compañero puede cambiar su copia si él lo aprueba; el hook impide enviarlo, no hacerlo. `consulta` comprueba que el hook esté activo antes de cada envío, pero un envío sin `consulta` no pasa por esa comprobación.
- **Por qué queda:** el autor quiere libertad para los compañeros y solo los hooks como seguro (P9, P12).
- **De dónde:** plan de la meta 005 · Agente de consulta para el equipo y buzón de peticiones (`specs/005-equipo-consulta/`, «Lo que va al BACKLOG»), 2026-10-28.
- **Qué haría falta:** ramas por compañero con `main` restringido al autor, una GitHub Action que avise, o un repo privado de organización con reglas por ruta.
- **Prioridad:** media.

### B62 · Enviar una petición son cinco comandos a mano
- **Qué:** el envío son los cinco comandos de `peticiones/README.md` («Cómo se envía»), que el compañero ejecuta uno por uno (P14).
- **Por qué queda:** el autor no quiere script de envío; falta ver si cinco comandos son demasiados.
- **De dónde:** plan de la meta 005 · Agente de consulta para el equipo y buzón de peticiones (`specs/005-equipo-consulta/`, «Lo que va al BACKLOG»), 2026-10-28.
- **Qué haría falta:** si en las fases 2 y 5 el compañero necesitó ayuda o se equivocó, un alias de git versionado o un script lanzado por él.
- **Prioridad:** baja: espera los números de la fase 5.

### B63 · Resumen periódico del estado para el jefe (`docs/ESTADO.md`)
- **Qué:** un `docs/ESTADO.md` que `direccion` pondría al día al cerrar cada meta, para quien no quiere preguntarle a un agente.
- **Por qué queda:** el jefe usa `consulta` como los demás (P3).
- **De dónde:** plan de la meta 005 · Agente de consulta para el equipo y buzón de peticiones (`specs/005-equipo-consulta/`, «Lo que va al BACKLOG»), 2026-10-28.
- **Qué haría falta:** el archivo y una línea en `/cerrar-fase` o en el cierre de meta de `direccion`.
- **Prioridad:** baja.

### B64 · Las pruebas de `equipo/` corren fuera de la suite
- **Qué:** `equipo/pruebas/probar_*.ps1` no están en pytest: la suite no las corre.
- **Por qué queda:** meterlas pediría tocar `codigo/tests`, y la meta 005 no toca `codigo/`.
- **De dónde:** plan de la meta 005 · Agente de consulta para el equipo y buzón de peticiones (`specs/005-equipo-consulta/`, «Lo que va al BACKLOG»), 2026-10-28.
- **Qué haría falta:** una prueba de pytest que lance los scripts de `equipo/pruebas/` con tope de tiempo, o correrlos en cada ronda de `pruebas`.
- **Prioridad:** baja.

### B65 · El guion de `consulta` cuesta dinero en cada corrida
- **Qué:** la prueba de `consulta` (`claude -p` con el guion de 5 preguntas) gasta cuota de Claude Code cada vez.
- **Por qué queda:** es informativa; por eso no se corre en cada fase.
- **De dónde:** plan de la meta 005 · Agente de consulta para el equipo y buzón de peticiones (`specs/005-equipo-consulta/`, «Lo que va al BACKLOG»), 2026-10-28.
- **Medido (fase 2 · El agente `consulta` y su skill de peticiones, 2026-10-28):** `equipo/pruebas/probar_consulta.ps1` hace 7 llamadas a `claude -p` con sonnet (5 preguntas y 2 órdenes): USD 0.96 en total (0.09 a 0.17 por llamada) y 605 s, casi todo espera de la API (de 15 a 222 s por llamada).
- **Qué haría falta:** nada mientras el coste medido en la fase 2 sea bajo; si sube, correrla solo al cerrar metas que toquen `docs/` o `consulta`.
- **Prioridad:** baja.

## Cerrados

### B29 · «Probar cámara» del panel no comprueba la marca ni aplica los ajustes
- **Qué era:** `gui/camera_probe.py` (era `gui/sonda_camara.py`), detrás de «Probar cámara», resolvía el índice por el puerto, abría por MSMF y leía un frame, pero no leía la marca ni aplicaba `controls`: con las cámaras intercambiadas de puerto daba «OK» y ponía el semáforo «Cámara» en verde (sesión en vivo de la fase 2b de la meta 002, punto 3, 2026-10-22).
- **Cerrado:** 2026-10-26, por la fase 2b · «Verificar IDs y colocar la cámara» marca la cámara en verde y se quita «Probar cámara» (meta 004 · Cómo funciona el tracker; P10): el panel ya no tiene el botón y el semáforo lo pone «Verificar IDs», que abre con `camera.backend` entero (marca y ajustes del perfil, como el tracker). `camera_probe.py` y su receta quedan para la CLI, sin la marca: quien los lance a mano no tiene esa comprobación.

### B32 · Optimizar el tracker: la ventana limita a 19–25 fps en cualquier resolución
- **Qué era:** en la fase 3 de la meta 002 el tracking con ventana dio 19–25 fps en todos los modos (sin ventana, 62–68 a 1280×960), y en la meta 003 los fps eran bimodales (~20 o ~32–37). La fase 6 · Dónde se va el tiempo por frame lo midió: el envío costaba 9–12.5 ms por frame (`pyigtl` con `wait=True` espera el tic de 15.6 ms de Windows) y el modo lento era la captura (32 ms); la ventana sola, ~2 ms.
- **Cerrado:** 2026-10-25, por la fase 7 · Subir los fps con ventana (meta 003 · Arquitectura y optimización del tracker; `clarify.md` P9 y P11): envío sin esperar (`wait=False`, 0.02 ms en vivo), el tracker espera a Slicer con tope (`--slicer-timeout` 30 s) y aborta si no llega, hilo de captura con el último frame (`camera/grabber.py`) y `t_now` por `perf_counter`. En vivo, caja de luz al máximo, cámara a 90: gs1 61.7 fps con ventana, sd z 0.033 mm, 56.9 Hz en Slicer (cumple ≥ 60); **gs2 queda en 55.2 fps** (cámara 88.8; el límite es el bucle, detección 9.7 ms), sd z 0.034 mm, 50.4 Hz; el autor lo acepta (P11). El modo lento resultó de la cámara con poca luz (B50). Lo que falta (tracking sin ventana para subir gs2) va a la fase 7b · Botones de tracker sin ventana y de vista previa. Números en `specs/003-arquitectura-tracker/resultados.md`.

### B21 · `opencv-python` frente a `opencv-contrib-python`
- **Qué era:** el venv y `requirements.txt` tenían `opencv-python` 4.11, pero `CONTEXT.md` §3 decía contrib.
- **Cerrado:** 2026-10-24, por la fase 5 · Documentación del paso 1 (meta 003 · Arquitectura y optimización del tracker): se alineó el texto, no el paquete. `CONTEXT.md` §3 dice `opencv-python` 4.11.0.86 (ArUco está en el módulo principal, `objdetect`, desde 4.7; Context7, OpenCV 4.13) y el comando de respaldo de `codigo/readme.md` §4 instala `opencv-python`. Nada del código vivo usa contrib.

### B34 · Las pruebas no deben poder abrir una cámara real aunque cambie un perfil
- **Qué era:** nada impedía que una prueba llegara a `cv2.VideoCapture` o a `create_backend(...).open()` con un perfil real y abriera la cámara física (en la meta 002 una prueba abrió la cámara 1 real y el vigilante la cortó a los 60 s).
- **Cerrado:** 2026-10-24, por la fase 4 · El tracker en piezas (meta 003 · Arquitectura y optimización del tracker): el fixture autouse `no_real_camera` de `codigo/tests/conftest.py` niega a toda la suite `cv2.VideoCapture`, `camera.uvc.listar_camaras_msmf/dshow`, `WebcamBackend.open` sin un `abrir` falso inyectado y `pyigtl.OpenIGTLinkServer` (`RealHardwareForbidden`). `tests/test_no_real_camera.py` lo prueba con los perfiles gs1 y gs2 reales y con `tracker.main`. No niega `create_backend` (construir el backend no toca hardware).

### B28 · `tracker.py` lanzado a mano abre MSMF con la aceleración HW encendida
- **Qué era:** `tracker.py` importaba `cv2` antes que el código que apaga la aceleración HW de MSMF, así que lanzado a mano desde PowerShell la apertura tardaba 43–51 s en vez de ~4 s.
- **Cerrado:** 2026-10-24, por la fase 4 · El tracker en piezas (meta 003): `tracker.py` hace `import camera` antes que `import cv2` y escribe «[Tracker] Aceleracion HW de MSMF apagada (…, puesta por el codigo)»; `test_aceleracion_msmf.py` lo fija (`test_tracker_a_mano_la_apaga_y_respeta_el_entorno`, `test_tracker_importa_camera_antes_que_cv2`). **Falta verlo en vivo a mano** (apertura ~4 s; protocolo en `Claude outputs/fases/003/fase-4-en-vivo-protocolo.md`): si no baja, se reabre. **Visto en vivo (2026-10-24, parte en vivo de la fase 4):** a mano, sin la variable de entorno, «puesta por el codigo» y la cámara abierta en 0.4 s (gs1 y gs2); desde el panel, «del entorno», 0.4–0.5 s. Desde entonces la suite lo fija (`test_aceleracion_msmf.py`); lo confirmó el cierre de la meta 003 (fase 8c, 2026-10-25).

### B27 · `tracker.abrir_camara`, función que nadie llama
- **Qué era:** `abrir_camara(cfg_cam)` en el tracker, sin ningún llamador.
- **Cerrado:** 2026-10-24, por la fase 4 · El tracker en piezas (meta 003): el bucle nuevo de `tracker.py` no la trae (`grep` 0).

### B22 · Secuencias de escape inválidas en docstrings
- **Qué era:** docstrings con rutas Windows (`\)`) daban `DeprecationWarning: invalid escape sequence` al compilar; en Python 3.12+ serían `SyntaxWarning`.
- **Cerrado:** 2026-10-24, por la fase 4 · El tracker en piezas (meta 003): `tests/test_compilan.py` compila los 55 archivos de `codigo/` (sin `historico/`) y los `tests/*.py` con los avisos como errores; 0 avisos.

### B17 · 22 pruebas desfasadas en `xfail(strict=True)`
- **Qué era:** 22 pruebas de los 3 archivos de mayo (`test_calibrar_rigid_body.py`, `test_captura_calibracion.py`, `test_generar_reference_dodecaedro.py`) marcadas `xfail(strict=True)` en la meta 001 porque el código del dodecaedro y del BA había cambiado después.
- **Cerrado:** 2026-10-23, por la fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker): las tres pruebas se archivaron con su código en `codigo/historico/iter4/dodecahedron/tests/` (registro, pytest no las recoge; B44). La suite queda con 0 `xfail`.

### B37 · La pose del dodecaedro salta 11–25 mm cuando entra o sale un marker visto de lado (11, 12)
- **Qué era:** con el dodecaedro quieto, la pose cambiaba 11–25 mm en z al entrar o salir un marker visto de lado (cámara 1, sd z 3.75–4.88 mm; meta 002, fase 6).
- **Cerrado:** 2026-10-23, por decisión del spec de la meta 003 (el dodecaedro se descarta): la fase 2 dejó de publicarlo (ADR-026) y la fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker) lo archivó en `codigo/historico/iter4/dodecahedron/`. Los números quedan en `Claude outputs/fases/002/fase-6-en-vivo.md`; sirven si el instrumento nuevo (B40) vuelve a ser multi-marker.

### B38 · `iter4/data/historico/` sin índice de qué es cada archivo
- **Qué era:** la carpeta de los perfiles viejos no tenía un `README` que dijera qué es cada archivo.
- **Cerrado:** 2026-10-23, por la fase 3 · La estructura nueva y el archivo (meta 003 · Arquitectura y optimización del tracker): la carpeta pasó a `codigo/historico/iter4/old_profiles/` y `codigo/historico/iter4/README.md` dice qué es cada cosa de `dodecahedron/`, `femto/` y `old_profiles/`.

### B18 · El filtro 1-Euro no tiene replay
- **Qué era:** el filtrado de posición dentro del lazo de `tracker.main()` no tenía replay; el de la suite cubría solo la pose del dodecaedro y `min_markers`.
- **Cerrado:** 2026-10-23, por la fase 1 · Línea base de Marker0 en vivo, antes de mover nada (meta 003): `tests/test_replay_marker0.py` pasa las esquinas grabadas en vivo por `estimar_pose_individual`, el `OneEuroFilter` de la posición y `rvec_tvec_a_matriz`, y compara con las matrices que `tracker.main()` envió: 0.0 mm / 0.0° en gs1 (977 envíos) y gs2 (973). No cubre el filtro del cuaternión del dodecaedro, que se archiva en la fase 3.

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

