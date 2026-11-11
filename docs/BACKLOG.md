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
| B71 | Lo que escucha en la red de la Jetson, sin cortafuegos | Media | — |
| B69 | La barrera del PC para los agentes es blanda | Media | — |
| B70 | Cuota de disco real para la cuenta `navagente` | Baja | — |
| B72 | `test_probar_barrera.py` añade ~35 s a la suite | Baja | — |
| B73 | La cita de argumentos para `Start-Process` vive solo en `probar_barrera.ps1` | Baja | — |
| B75 | `probar_barrera.ps1` no prueba ninguna orden pesada ni `info temperatura` | Media | — |
| B76 | `suite` del guardián: con dos rutas corre solo la última, sin aviso, y no deja ver por qué se salta cada prueba | Baja | — |
| B67 | Las herramientas de cámara (sonda, modos, calibración, «Verificar IDs») solo abren por Windows | Baja | — |
| B77 | La sd z de gs1 por V4L2 es casi el doble que por MSMF (deriva lenta, no ruido) | Baja | — |
| B78 | Un `ssh` cortado mata el tracker antes de guardar el `.npz` y el `--timing` | Media | — |
| B80 | El guardián no pasa `DISPLAY`: no hay corrida con ventana por `ssh nav-jetson` | Baja | — |
| B82 | No hay verbo para el tamaño o el sha256 de un archivo de `~/nav-salidas/` | Baja | — |
| B83 | `--timing=~/…` con `=` no expande `~` | Baja | — |
| B84 | El tracker escribe «[Salida limpia]» antes de la traza de un error | Baja | — |
| B68 | El 18944 abierto en la red sin autenticación (con `--igtl-iface`) | Media | — |
| B85 | El cable directo Jetson ↔ PC quedó sin probar (P27) | Media | — |
| B86 | El ahorro de energía de la Wi-Fi de la Jetson no persiste y hunde la LAN | Media | — |
| B87 | El reloj de la Jetson deriva ~1.4 ms/min respecto al del PC | Baja | — |
| B88 | `pyigtl` gira en vacío si el cliente se va y no hay nada que enviar | Baja | — |
| B89 | Una calibración a medias pisa los intrínsecos que usa el tracker | Alta | — |
| B90 | `info energia` del guardián no encuentra `nvpmodel` (fuera del PATH de `navagente`) | Baja | — |
| B91 | Con dos cámaras la CPU de la Jetson va al 95.5 % y no deja margen para la meta 006 | Media | — |
| B92 | Los fps de una cámara sola en el PC varían de una corrida a otra (caída tardía en A1, arranque lento en A4) | Media | — |
| B93 | `CapaWindowsDShow` queda solo para la sonda; se archiva cuando nada la use | Baja | — |
| B94 | La pose de Marker0 desde una cámara sola no coincide entre gs1 y gs2 (19.5 mm / 5.8° en la peor posición) y las 5 posiciones no caben en dos cámaras rígidas | Alta | — |
| B95 | La pose cruda de IPPE_SQUARE es 1.2–1.5× más ruidosa que la de mínimos cuadrados sobre las mismas esquinas | Media | — |
| B96 | El desfase δ entre cámaras (P13) no se distingue en S4: la curva es plana | Baja | — |
| B97 | Cuánto ancho de banda isócrono reserva cada SVPRO en MJPG 1280x960 90 fps, sin leer su descriptor | Baja | — |
| B98 | La Jetson como fuente del fusionador de la meta 006 | Baja | — |
| B99 | El ancla de reloj de los `.npz` usa `time.time`, que en Windows con Python 3.11 va a pasos de hasta 15.6 ms | Baja | — |
| B100 | El suelo de ruido de `half_split` frente al umbral de 0.5 mm del veredicto de B94 | Media | — |
| B101 | Las dos ventanas del tracker llevan el mismo título y se abren en el mismo sitio | Baja | — |
| B102 | Las parejas reales de la grabación del PC quedan bajo las 2000 de P16 aunque el script estime más | Media | — |
| B103 | El filtro z ≤ 0 de `estimate_single_pose` no atrapa el salto de IPPE_SQUARE entre sus dos soluciones, y el tracker lo publica a Slicer | Alta | — |
| B104 | Un tramo repetido por los `correr.ps1` de grabación (`<tramo>_r2_<cámara>.npz`) no lo encuentra `fusion.dataset.segment_file` (`<tramo>_<cámara>_r2.npz`) | Media | — |
| B105 | `diagnostics.probe_camera._vigilante` no para el proceso si `estado` no se puede escribir como JSON | Baja | — |
| B106 | El 1-Euro de hoy deja la posición hasta ~3 mm detrás del marker cuando se mueve | Baja | — |
| B107 | La hora del mensaje TRANSFORM es la del envío (`time.time` de pyigtl), no la de captura | Baja | — |
| B108 | En la fusión, los frames que ve una sola cámara pasan tal cual y pueden dar un escalón en Slicer | Media | Meta 006, Fase 4 |
| B109 | El emparejado por hora admite medio periodo: con el marker en movimiento, el PnP conjunto mezcla dos instantes | Media | Meta 006, Fase 4 |
| B110 | El RMS de reproyección del PnP conjunto podría avisar en vivo de una cámara movida | Media | — |
| B111 | gs2 grabó a 41.4 fps en un tramo de la sesión del tablero cortada | Baja | — |
| B112 | El asistente del tablero podría servir para los intrínsecos | Baja | — |
| B113 | El asistente no comprueba en vivo el orden de las esquinas ni la coherencia de la vista | Baja | — |

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
- **De dónde:** primera parte en vivo de la fase 7, 2026-10-25 (`Claude outputs/fases/003/fase-7-en-vivo.md`, «C0, la captura sola»). **Al día (2026-10-25, segunda parte):** pedir 60 fps dio 29 en gs1 con la caja al máximo (28.9 de cámara): la SVPRO no tiene modo de 60 a 1280×960 MJPG y MSMF baja al de 30; los perfiles siguen a 90 (`clarify.md` P11). **Al día (2026-10-25, fase 8a · Un botón por modo en el panel, en vivo):** con la caja al máximo y el tracker con ventana, la cámara bajó al final de la corrida a 75.7 (gs1) y 77.0 fps (gs2), tras empezar a ~90; no se miró por qué (puede ser este mismo control o la carga del bucle con ventana). Lo anotó el cierre de la meta 003 (fase 8c). **Al día (2026-10-26, fase 2b · «Verificar IDs y colocar la cámara» marca la cámara en verde y se quita «Probar cámara», meta 004 · Cómo funciona el tracker, en vivo):** con la caja al máximo, la primera corrida de «Verificar IDs» marcó 30 fps y la segunda 89.8 (`[IDs] camara 89.8 fps`, exit 0); el autor decidió dejarlo aquí sin investigar. **Al día (2026-10-29, fase 1 · El escaneo de la Jetson, solo lectura, meta 007):** en la Jetson, `v4l2-ctl --list-ctrls-menus` de las dos SVPRO no trae `exposure_dynamic_framerate` (ni otra prioridad de exposición): la exposición solo tiene `auto_exposure` (manual o prioridad de apertura) y `exposure_time_absolute`. Además, `--list-formats-ext` sí anuncia 60 fps a 1280×960 MJPG (y 90, 30, 25, 20, 15, 10, 5), aunque por MSMF pedir 60 dio 29; y `power_line_frequency` se lee en 2 (60 Hz) en las dos (B24). No se tocó nada.
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
- **Al día (2026-11-04, P-6 de la meta 007):** con el tracker en la Jetson, Slicer en el PC contó 84.0 Hz por LAN y 82.0 por Tailscale (intervalo p50 15 ms), y 65.7 con el tracker en el PC. Hipótesis, sin demostrar: Slicer cuenta dos actualizaciones dentro de un mismo tic de 15.6 ms de Windows. Para decidir si «el techo es de Slicer» (R2) sigue valiendo, habría que repetir el banco con el emisor en otra máquina.
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
- **Al día (2026-11-05, fase 7b · Las dos cámaras a la vez en Windows, meta 007):** gs2 pasó a `…#USB(5)`, fuera del hub Genesys, y su comentario de identidad se puso al día; el de gs1 sigue diciendo «Las dos cuelgan de un hub», que ya no vale (el encargo no tocaba ese perfil).
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

### B71 · Lo que escucha en la red de la Jetson, sin cortafuegos
- **Qué:** el escaneo de la fase 1 (2026-10-29) ve varios servicios escuchando en todas las interfaces (0.0.0.0 o `*`): entre ellos un JupyterLab que corre como root, un gateway de openclaw, el escritorio remoto (VNC y RDP), CUPS y rpcbind; `ufw` está inactivo y sin su archivo de configuración. Ollama y n8n escuchan solo en 127.0.0.1. El detalle (puertos y procesos) está en el escaneo, fuera de git; aquí no va porque el repo es público (B60).
- **Por qué queda:** no es de la meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC, y tocarlo pide sudo y al autor. El escaneo no dice si cada servicio pide autenticación.
- **De dónde:** plan de la meta 007 (`specs/007-jetson/plan.md`, «Lo que va al BACKLOG»), con lo que vio el escaneo de la fase 1 · El escaneo de la Jetson, solo lectura.
- **Qué haría falta:** que el autor revise qué necesita cada servicio en la red (en particular si JupyterLab y el gateway piden clave o token) y decida un cortafuegos o ligarlos a 127.0.0.1 o a Tailscale. Se cruza con B68 (el 18944 abierto en la red), escrita en la fase 6.
- **Prioridad:** media (puede haber algo sin autenticación; sin confirmar).

### B68 · El 18944 abierto en la red sin autenticación (con `--igtl-iface`)
- **Qué:** OpenIGTLink no autentica. Con `tracker --igtl-iface <interfaz>` (meta 007, fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes; ADR J2) el servidor de `pyigtl` escucha en la IPv4 de esa interfaz de la Jetson, así que cualquier equipo de esa red puede conectarse al 18944 antes que Slicer y dejarlo fuera (el servidor atiende a un solo cliente), o leer las transforms. Sin la opción, el servidor sigue en 127.0.0.1.
- **Por qué queda:** es la consecuencia aceptada de J2 (P10: la opción, y sin ella loopback). Cerrarlo pide una regla de cortafuegos en la Jetson (sudo y el autor) o quedarse solo con Tailscale, que ya cifra y autentica a los dos extremos: la fase 6 mide las tres redes y el autor decide con los números.
- **De dónde:** plan de la meta 007 (`specs/007-jetson/plan.md`, «Lo que va al BACKLOG» y ADR J2), escrito al implementar la fase 6 (2026-11-03).
- **Qué haría falta:** si el tracker se queda en la Jetson por LAN o cable, una regla que admita en el 18944/tcp solo la IP del PC (`ufw` está inactivo y sin configurar en la Jetson, B71), o usar solo `--igtl-iface tailscale0`. Se cruza con B71.
- **Al día (2026-11-04, P-6):** por Tailscale (`direct`, por la misma Wi-Fi) Slicer recibió 82.0 Hz y la latencia añadida p95 fue 2.06 ms; por la LAN, 84.0 Hz y 7.62 ms. Tailscale no pierde nada frente a la LAN, así que quedarse solo con él no cuesta rendimiento; la decisión sigue siendo del autor.
- **Prioridad:** media.

### B69 · La barrera del PC para los agentes es blanda
- **Qué:** los agentes corren como el usuario de Windows del autor. Lo que ese usuario alcanza (su clave personal de `~/.ssh/`, un `subprocess` desde un Python permitido), un agente lo alcanza rodeando las reglas de `.claude/settings.json`. La barrera dura es la cuenta `navagente` y su guardián en la Jetson (`codigo/linux/guardian.py`): acota el daño solo si el acceso va por ella.
- **Por qué queda:** el rodeo no se cierra desde el repo; lo mitiga el autor (clave personal con frase de paso y `sudo` de la Jetson con contraseña: P20, contestada en «a»).
- **De dónde:** hallazgo 7 del plan de la meta 007 · El tracker en la Jetson Orin Nano, con Slicer en el PC (`specs/007-jetson/plan.md`), fase 2 · La barrera de seguridad para los agentes.
- **Qué haría falta:** un usuario de Windows aparte para los agentes, sin acceso al `~/.ssh/` del autor. Si la clave personal dejara de llevar frase de paso, la prioridad sube a alta.
- **Prioridad:** media.

### B70 · Cuota de disco real para la cuenta `navagente`
- **Qué:** el guardián se niega a lanzar lo pesado con menos de 5 GB libres en `/`, pero una sola orden puede llenar el disco por dentro (el límite por archivo es de 2 GiB, el total no tiene).
- **Por qué queda:** el chequeo previo cubre el uso normal; la cuota de ext4 pide sudo y cambios de montaje.
- **De dónde:** plan de la meta 007 (`specs/007-jetson/plan.md`, «Lo que va al BACKLOG»), fase 2.
- **Qué haría falta:** cuotas de ext4 para `navagente`, que aplica el autor con sudo.
- **Prioridad:** baja.

### B72 · `test_probar_barrera.py` añade ~35 s a la suite
- **Qué:** las corridas completas de `probar_barrera.ps1` con el guardián falso (los casos `prueba-tope` duermen 3 s) suben la suite de ~46 s a ~70 s (805 pruebas, 2026-10-29). Desde el 2026-11-02 son tres (la nueva, con una `-Salida` que lleva un espacio), de ~11.5 s cada una: ~35 s.
- **Por qué queda:** vale la pena mientras la barrera sea nueva; no estorba hoy.
- **De dónde:** fase 2 · La barrera de seguridad para los agentes, de la meta 007 (medido en «verifica», 2026-10-29, y en los arreglos tras el P-2, 2026-11-02).
- **Qué haría falta:** acortar el tope falso de las pruebas, o marcar esas tres pruebas como lentas y correrlas solo al tocar `codigo/linux/`.
- **Prioridad:** baja.

### B73 · La cita de argumentos para `Start-Process` vive solo en `probar_barrera.ps1`
- **Qué:** `Start-Process` de PowerShell 5.1 junta `-ArgumentList` con espacios sin citar nada; en el P-2 (2026-11-02) eso partió la ruta de `-Salida` y paró la fabricación de los tar. `probar_barrera.ps1` tiene ahora `ConvertTo-LineaArgumentos` (las reglas de `CommandLineToArgvW`). `escanear.ps1` no la usa y hoy no la necesita: sus rutas van por `-RedirectStandardInput`/`-RedirectStandardOutput` y su único argumento con espacios es la orden remota, que `ssh` vuelve a juntar con espacios igual.
- **Por qué queda:** no hay un segundo script que la necesite: `enviar_wip.ps1` aún no existe (es de la fase 3 · El entorno en la Jetson o posterior). Al día (2026-11-02, fase 3 · El entorno en la Jetson): `enviar_wip.ps1` ya existe y lleva una copia de la función (su prueba pasa la carpeta `codigo` por una ruta con espacio); hay dos copias iguales. No se sacó a un archivo común en esa fase para no tocar `probar_barrera.ps1`, probado en vivo.
- **De dónde:** fase 2 · La barrera de seguridad para los agentes, de la meta 007 (arreglos tras el P-2, 2026-11-02).
- **Qué haría falta:** cuando se escriba `enviar_wip.ps1` (o cualquier `.ps1` que lance un programa con una ruta), sacar la función a un archivo común de `codigo/linux/` y usarla en los dos, con una prueba de ruta con espacio.
- **Prioridad:** baja.

### B75 · `probar_barrera.ps1` no prueba ninguna orden pesada ni `info temperatura`
- **Qué:** los 30 casos de la barrera son negados, ligeros, de `sshd`, de tope y de corte. Ninguno pasa por `precondiciones` de una orden pesada ni lee las zonas térmicas. Por eso el guardián 2 dio 30 de 30 en la Jetson y, aun así, `info temperatura` y todas las pesadas (`entorno`, `suite`, `py`, `camara`, `medir`) salían con 125 y `TypeError: can't concat NoneType to bytes`: las zonas cv0, cv1 y cv2 dan EAGAIN al leer `temp` y `read_text` no lo soportaba. El guardián 3 (fase 3 · El entorno en la Jetson, 2026-11-02) lo arregla con `_leer_sysfs` y una prueba en `test_guardian.py`.
- **Por qué queda:** añadir casos cambia `probar_barrera.ps1` y su prueba, de la fase 2, y el arreglo ya está; no hace falta para la fase 3. Al día (2026-11-02, segunda vuelta de la fase 3): con el guardián 3 instalado, a mano, `info temperatura` sale con 0 y 6 zonas (sin cv0–cv2), `medir tegrastats 1` con 0, y `entorno instalar` y `suite` pasan `precondiciones`; `probar_barrera.ps1` sigue en 30 de 30 sin esos casos.
- **De dónde:** fase 3 · El entorno en la Jetson, de la meta 007 (2026-11-02, al lanzar `entorno instalar`).
- **Qué haría falta:** dos casos permitidos más en `probar_barrera.ps1` y en `test_probar_barrera.py`: `info temperatura` con 0 y al menos una zona, y `medir tegrastats 1` con 0 (pasa por `precondiciones` de una pesada sin abrir la cámara).
- **Prioridad:** media.

### B76 · `suite` del guardián: con dos rutas corre solo la última, sin aviso, y no deja ver por qué se salta cada prueba
- **Qué:** `ssh nav-jetson suite wip -q tests/a.py tests/b.py` corre solo `tests/b.py` (en `decidir`, cada ruta pisa a la anterior) y sale con el código de esa sola. Además el verbo no acepta `-rs`, así que el motivo de cada prueba saltada no se ve en la Jetson. Un `-k` con espacios sí llega si va citado dentro de la orden remota (`ssh nav-jetson "suite wip -k 'a or b'"`), no como argumentos sueltos.
- **Por qué queda:** con una ruta por orden basta; los saltos de la fase 4 se cuentan (45 + 13 = 58) y su motivo está en cada prueba. Cambiar el guardián pide que el autor lo reinstale con sudo.
- **De dónde:** fase 4 · La suite corre en Linux, de la meta 007 (2026-11-02, al medir el replay en la Jetson); la sugerencia de `-rs` venía de la fase 3.
- **Qué haría falta:** en `decidir`, negar una segunda ruta (o aceptar varias) y admitir `-rs`, con sus casos en `test_guardian.py`; el autor instala el guardián 4.
- **Prioridad:** baja.

### B67 · Las herramientas de cámara (sonda, modos, calibración, «Verificar IDs») solo abren por Windows
- **Qué:** la fase 5 · La capa V4L2 y cada cámara en la Jetson (meta 007, 2026-11-02) lleva a Linux solo lo que usa el tracker: `camera.backend.WebcamBackend` (por `plataforma`), `camera.controls.capa_para_plataforma` y el nuevo `camera/v4l2.py`. Siguen leyendo `usb_port_windows` a secas, o construyendo `CapaWindowsDShow` o enumerando por MSMF/DSHOW: `diagnostics/probe_camera.py` (`--puertos`, `--leer`, `--fijar`), `diagnostics/measure_modes.py`, `diagnostics/identify_ids.py`, `calibration/calibrate_camera.py`, `calibration/check_scale.py`, `gui/camera_probe.py`, `gui/calibration_window.py` y `gui/panel.py`. En la Jetson, dar de alta la marca de una cámara nueva (`--fijar focus=N --forzar`) o medir modos no se puede desde el código; `python -m camera.v4l2 --listar|--leer|--aplicar` cubre solo listar, leer y aplicar el perfil.
- **Por qué queda:** la meta 007 lleva el tracker a la Jetson, no las herramientas (plan, «Lo que va al BACKLOG»); se calibra en el PC y el panel corre en el PC (P16).
- **De dónde:** plan de la meta 007 (`specs/007-jetson/plan.md`), concretado al escribir la fase 5.
- **Qué haría falta:** que esos módulos pidan la identidad de la plataforma (`usb_port_linux` fuera de Windows) y la capa por `capa_para_plataforma`, con `--fijar` sobre `CapaLinuxV4L2` (que ya admite `forzar`), y «Verificar IDs» por SSH si algún día hace falta desde el panel.
- **Prioridad:** baja mientras se calibre y se den de alta las cámaras en el PC.

### B77 · La sd z de gs1 por V4L2 es casi el doble que por MSMF
- **Qué:** en el P-5 (2026-11-03), gs1 en reposo con Marker0 a 361 mm dio por V4L2 en la Jetson una sd z de 0.0737 mm (MAD×1.4826 0.0847, 0 saltos > 1 mm); la misma gs1, en la misma posición, por MSMF en el PC dio 0.032–0.043 mm (0.0425 sin los saltos de una corrida perturbada; MAD×1.4826 0.0323). gs2 por V4L2 dio 0.0399 mm a 326 mm, dentro de la banda de la meta 003 (0.030–0.043). Que la MAD sea mayor que la sd sugiere una distribución con dos valores.
- **Por qué queda:** el criterio del plan (fps, % con pose, marca, código 3) se cumple; la precisión de gs1 sigue siendo de décimas de milímetro. Hay dos corridas por cámara y una sola posición, y no hay causa medida.
- **De dónde:** P-5 de la fase 5 · La capa V4L2 y cada cámara en la Jetson, de la meta 007 (`Claude outputs/fases/007/fase-5.md`, «P-5 en vivo»).
- **Qué haría falta:** repetir gs1 y gs2 por V4L2 en la misma posición, mirar el histograma de z, y comparar una variable por vez: la exposición real (1.0 ms en Linux frente a 0.9766 en Windows), el formato o la decodificación MJPEG de V4L2, el hub USB 2.0. Antes de fijar los mínimos de P13 y de la fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes.
- **Prioridad:** baja (2026-11-03, decisión del autor, P26: espera datos, se trata solo si afecta de verdad; era media).
- **Parte A de la fase 5b (2026-11-03, sin cámara; `diagnostics/ruido_pose.py` sobre las tres grabaciones del P-5):** la sd z de gs1 (0.0737) es casi toda lenta: sd de las medias por segundo 0.0707, pendiente −3.9 µm/s (0.23 mm en 60 s, monótona; en lado aparente, +2.3 mpx/s, del orden de 0.1 px). Sin la recta queda 0.029 mm, igual que gs2 (0.032) y gs1 por MSMF; es una deriva, no ruido. gs2: pendiente −1.0 µm/s. Descartado: el filtro (0 % de dt < 2 ms; refiltrada con tiempos uniformes 0.0733) y la bimodalidad (Sarle 0.38 y 0.34; la «MAD > sd» es una media que se desliza). Apunta a calor, mecánica o luz, no a un control.
- **Estado (cierre de la fase 5b, 2026-11-03):** el autor decidió no correr el P-5b (P26); la fase cerró con la parte A. Lo que separaría las causas es el P-5b (`Claude outputs/fases/007/p5b.md`): J1 y J2 seguidas (calentamiento) frente a la continua, J4 con los cables intercambiados (puerto), W1 y W2 en el PC. La herramienta ya está: `diagnostics/ruido_pose.py` y `linux/perfil_temporal.py`. Se retoma si la deriva afecta de verdad al uso (la espera de calentamiento o la pendiente en `pose_log.summarize` serían lo primero).

### B78 · Un `ssh` cortado mata el tracker antes de guardar el `.npz` y el `--timing`
- **Qué:** en el P-5, el `ssh` de la consola 2 se cortó a los 54 s; el guardián registró `124 · se corto la salida (BrokenPipe)` y cortó el grupo de procesos. El tracker no guardó el `.npz` de `--record` ni el `.json` de `--timing`, y la corrida se perdió.
- **Por qué queda:** el corte fue un accidente de la sesión y el guardián hizo lo que debe (no deja procesos huérfanos).
- **De dónde:** incidente del P-5 de la fase 5 (meta 007), 2026-11-03.
- **Qué haría falta:** que el tracker guarde al recibir SIGTERM o SIGPIPE (en Linux), o que el guardián le dé unos segundos tras el corte antes de matar el grupo; con su prueba.
- **Prioridad:** media.

### B80 · El guardián no pasa `DISPLAY`: no hay corrida con ventana por `ssh nav-jetson`
- **Qué:** la corrida b) del P-5 (con ventana) no se pudo medir: la Jetson no tiene escritorio abierto y el guardián no pasa `DISPLAY` a lo que lanza.
- **Por qué queda:** el tracker en la Jetson se usa sin ventana (el panel del PC lo lanza así, fase 8).
- **De dónde:** P-5 de la fase 5 (meta 007), 2026-11-03.
- **Qué haría falta:** si algún día se quiere la ventana en la Jetson, un `DISPLAY` fijo en el entorno del guardián (lo instala el autor con sudo) o reenvío X11.
- **Prioridad:** baja.

### B82 · No hay verbo para el tamaño o el sha256 de un archivo de `~/nav-salidas/`
- **Qué:** para traer un `.npz` de la Jetson al PC y comprobarlo no hay forma de preguntar su tamaño ni su sha256 por `ssh nav-jetson`; en el P-5 se comprobó con `zipfile.testzip()` en el PC.
- **Por qué queda:** `testzip()` basta para saber que no llegó roto.
- **De dónde:** P-5 de la fase 5 (meta 007), 2026-11-03.
- **Qué haría falta:** un verbo de solo lectura en el guardián (por ejemplo `info archivo <nombre>`), con sus casos en `test_guardian.py`.
- **Prioridad:** baja.

### B83 · `--timing=~/…` con `=` no expande `~`
- **Qué:** `--timing=~/nav-salidas/x.json` (con `=`) llega al tracker con la tilde sin expandir; con un espacio, sí. No se sabe si lo hace el guardián o el tracker.
- **Por qué queda:** se sortea escribiendo la opción con espacio.
- **De dónde:** P-5 de la fase 5 (meta 007), 2026-11-03.
- **Qué haría falta:** mirar dónde se expande `~` en `_args_py` del guardián y en el tracker, y hacer que `--opcion=~/…` valga igual; con su prueba.
- **Prioridad:** baja.

### B84 · El tracker escribe «[Salida limpia]» antes de la traza de un error
- **Qué:** en la corrida c) del P-5 (marca cruzada) el tracker imprimió «[Salida limpia]» y después la traza del error; el mensaje engaña sobre cómo terminó (código 1).
- **Por qué queda:** el código de salida es el correcto, y `gui/status.py` (`_motivo_del_fallo`) ya ignora esa línea al buscar el motivo de un fallo.
- **De dónde:** P-5 de la fase 5 (meta 007), 2026-11-03.
- **Qué haría falta:** que `tracker.py` (línea 390) escriba «[Salida limpia]» solo si no hay una excepción en curso; toca `tracker.py` (principio 6: replay y suite) y las pruebas que esperan esa línea.
- **Prioridad:** baja.

### B85 · El cable directo Jetson ↔ PC quedó sin probar (P27)
- **Qué:** el P-6 midió Slicer en el PC contra el tracker de la Jetson por la LAN y por Tailscale; la tercera red del plan, el cable Ethernet directo entre la Jetson y el PC, no se probó. No hay número de Hz ni de latencia para ella.
- **Por qué queda:** el PC tiene un solo adaptador Ethernet físico y probar el cable lo deja sin LAN, Internet ni Tailscale mientras dura. Decisión del autor (P27, 2026-11-03, `specs/007-jetson/clarify.md`): LAN y Tailscale ahora, el cable más adelante.
- **De dónde:** fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes, de la meta 007 (P-6, paso C, `Claude outputs/fases/007/p6.md`).
- **Qué haría falta:** correr el paso C del P-6 con un módem usado como switch (así el PC conserva su red) o con un adaptador USB-Ethernet para el cable directo; el tracker con `--igtl-iface` de la interfaz del cable. Antes de llevar la Jetson a otro sitio o de compartirla (si no hay LAN conocida allí, el cable es la única red segura que queda).
- **Prioridad:** media.

### B86 · El ahorro de energía de la Wi-Fi de la Jetson no persiste y hunde la LAN
- **Qué:** con el ahorro de energía de la Wi-Fi de la Jetson encendido (lo normal tras cada arranque), la radio hace pausas de hasta 400 ms y Slicer en el PC recibe ~20 Hz por la LAN aunque el tracker envíe 88. El P-6 se midió con `iw dev <interfaz> set power_save off` puesto a mano, que se pierde al reiniciar la Jetson. (Nagle era la otra causa del 20 Hz y está arreglada: `TCP_NODELAY`, `f34ed71`.)
- **Por qué queda:** hacerlo persistente es una acción con `sudo` en la Jetson (del autor, no de los agentes). Tailscale `direct` va por la misma Wi-Fi y no lo evita; el cable sí (B85).
- **De dónde:** P-6 de la fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes, de la meta 007 (2026-11-03 y 2026-11-04).
- **Qué haría falta:** que el autor lo haga persistente (NetworkManager, `wifi.powersave = 2` en un archivo de `conf.d`), o que el tracker o el arranque de la Jetson avisen si la Wi-Fi tiene el ahorro encendido (un verbo de solo lectura en el guardián que lea `iw dev <interfaz> get power_save`).
- **Prioridad:** media (sin esto la LAN pasa de 84 a 20 Hz tras cada reinicio, sin ningún aviso).

### B87 · El reloj de la Jetson deriva ~1.4 ms/min respecto al del PC
- **Qué:** la Jetson no está sincronizada: su reloj y el del PC derivan ~1.4 ms por minuto (20–30 ppm). Por Tailscale el desfase pasó de −143.282 a −129.548 ms en 606 s. La latencia del P-6 se corrigió interpolando el desfase medido antes y después de cada corrida (`diagnostics/clock_offset.py`), con ± 0.8 ms.
- **Por qué queda:** con `clock_offset` antes y después basta para medir la latencia; sincronizar pide `sudo` en la Jetson.
- **De dónde:** P-6 de la fase 6 · Slicer en el PC recibe de la Jetson, por las tres redes, de la meta 007 (2026-11-04).
- **Zona horaria (2026-11-04, P-7):** la Jetson está en UTC+8 (su log dijo 2026-11-05 10:02 cuando el PC decía 2026-11-04 20:02); las fechas tomadas de ella salen un día adelantadas. No cambia ninguna medida, que son relativas; la fecha de una fase es la del PC.
- **Qué haría falta:** NTP o chrony en la Jetson (la latencia entonces se mediría sin el desfase antes y después), si la latencia tiene que medirse a menudo o si los sellos de tiempo de la Jetson se usan junto a los del PC (meta 006 · Grafo de factores óptico-inercial).
- **Prioridad:** baja.

### B88 · `pyigtl` gira en vacío si el cliente se va y no hay nada que enviar
- **Qué:** en `pyigtl` 0.3.1, el hilo del servidor (`TCPRequestHandler.handle`) solo nota que el cliente se fue cuando falla un envío: si el cliente cierra, `recv` devuelve `b''` al instante, `_receive_message_from_socket` lo toma como «no hay mensaje» y el bucle vuelve a llamar sin esperar. Mientras el tracker no envíe nada (la cámara aún abriéndose, B79, o Marker0 fuera de la vista), ese hilo ocupa un núcleo entero y el servidor no acepta otro cliente. Leído en el código de `pyigtl` del venv, sin medir.
- **Por qué queda:** dura lo que tarda el siguiente envío (con Marker0 a la vista, milisegundos) y no cambia lo que se envía; arreglarlo toca `transport/igtl.py` (la cadena, principio 6) o `pyigtl`.
- **De dónde:** fase 7 · Las dos cámaras a la vez en la Jetson, de la meta 007 (2026-11-04), al preparar el bucle de listeners del P-7 para B79.
- **Qué haría falta:** medirlo (CPU del tracker con un cliente que se conecta y se va con Marker0 tapado); si se confirma y estorba, que `IgtlSender` detecte el cierre (p. ej. un `verify_request` que deje el socket con `SO_KEEPALIVE`, o un envío de prueba) o un parche a `pyigtl`, con su ADR y la verificación de la cadena.
- **Prioridad:** baja.
- **Al día (2026-11-04, fase 7b · Las dos cámaras a la vez en Windows, parte A):** con `igtl_rate listen --idle-s 60` (B79, cerrada) el listener ya no se rinde mientras el tracker abre la cámara y no hace falta reconectarlo, así que el P-7w no tropieza con esto; el hilo que gira en vacío solo aparecía al reconectar. Sigue sin medirse.

### B89 · Una calibración a medias pisa los intrínsecos que usa el tracker
- **Qué:** la ventana de calibración del panel (`gui/calibration_window.py`, `salidas_del_perfil`) le pasa a `calibration/calibrate_camera.py` como `--output` el mismo `data/intrinsecos_<cámara>_<modo>.yml` que lee el perfil, y el script lo escribe siempre, incluso si el criterio no se cumple (sale con código 1 y deja el `.yml` «con el veredicto dentro»). Una calibración de prueba, una demostración o una que alguien abre y abandona cambia la K y la distorsión con las que trabaja el tracker, sin que nadie la acepte.
- **Por qué queda:** se vio el 2026-11-04, cuando dos pruebas de la suite fallaron por un `intrinsecos_gs1_1280x960.yml` cambiado así (fx 845.1 en vez de 849.9); el autor lo descartó y pidió que el cambio solo valga cuando la calibración se termina. No se arregla dentro de la meta 007 (la Jetson) sin replanearla.
- **De dónde:** el autor, al cerrar la fase 7 · Las dos cámaras a la vez en la Jetson (meta 007), 2026-11-04.
- **Qué haría falta:** que la calibración escriba siempre a un archivo provisional (por ejemplo, en `Claude outputs/camaras/`), y que el `.yml` de `data/` solo se sustituya con un paso explícito de «aceptar», con el criterio cumplido, una copia de seguridad del anterior (como el ADR-018 con el perfil) y un aviso si la K cambia; con sus pruebas, y comprobando que el replay sigue igual.
- **Prioridad:** alta (puede dar un resultado equivocado: el tracker trabajaría con una calibración no aceptada sin avisar).

### B90 · `info energia` del guardián no encuentra `nvpmodel`
- **Qué:** `ssh nav-jetson info energia` falló en el paso 0 del P-7 con «no se pudo lanzar nvpmodel: [Errno 2]» (código 125): `nvpmodel` vive en `/usr/sbin`, que no está en el PATH de la cuenta `navagente`. El modo de energía (`MAXN_SUPER`) lo leyó el autor a mano en su sesión.
- **Por qué queda:** no cambia ninguna medida; el modo se puede leer por otro camino. Tocar el guardián pide reinstalarlo en la Jetson.
- **De dónde:** P-7 de la fase 7 · Las dos cámaras a la vez en la Jetson, de la meta 007 (2026-11-04).
- **Qué haría falta:** que `linux/guardian.py` lance `nvpmodel` por su ruta absoluta (`/usr/sbin/nvpmodel -q`), con su prueba en `probar_barrera.ps1`, y que el autor reinstale el guardián (`sudo`).
- **Prioridad:** baja.

### B91 · Con dos cámaras la CPU de la Jetson va al 95.5 % y no deja margen para la meta 006
- **Qué:** en el P-7 (condición A, 450 s), con gs1 y gs2 a la vez cada una en su tracker, la CPU de la Jetson quedó al 95.5 % de media (núcleos 93–97 %, a 1728 MHz) con la GPU al 0 %. La cámara entrega 86.2 fps cada una, pero el bucle da 63.2 y cada tracker salta ~27 % de los frames. Cumple P13 (≥ 45 fps por cámara) y no deja CPU para el grafo de factores de la meta 006 · Grafo de factores óptico-inercial.
- **Por qué queda:** cumple lo pedido hoy y no se ha decidido qué aliviar; las opciones piden medir antes y alguna toca la cadena (principio 6) o una dependencia nueva.
- **De dónde:** P-7 de la fase 7 · Las dos cámaras a la vez en la Jetson, de la meta 007 (2026-11-04).
- **Qué haría falta:** medir dónde se va la CPU (decodificar MJPEG, `ArucoDetector`, el hilo de captura) y probar, sin decidir: un solo proceso para las dos cámaras; decodificar el MJPEG por hardware (NVJPG, `nvjpegdec` de GStreamer) o directo a gris; detectar en una región alrededor de la última pose; el umbral adaptativo en la GPU (OpenCV con CUDA es una dependencia nueva, con su ADR); o dejar el grafo en el PC. Comparar con el P-7w del PC (fase 7b).
- **Prioridad:** media (sin esto la meta 006 no cabe en la Jetson junto a los dos trackers).

### B92 · Los fps de una cámara sola en el PC varían de una corrida a otra (caída tardía en A1, arranque lento en A4)
- **Qué:** en el P-7b-A (2026-11-04; una cámara transmitiendo sola por el tracker sin ventana, con su listener local, caja de luz al máximo), en A1 gs2 fue a 88.5–89.3 fps de cámara durante y justo después de la lectura de gs1 por cv2, y a partir de ~35 s después de esa lectura su promedio acumulado cayó a 60.4 (al final: cámara 58.5 fps, bucle 55.4); en A4 gs1 arrancó bajo (`[FPS]` 44.7 en los primeros 5 s) y subió hasta 87.4 de media (bucle 86.4); en A2 gs2 estuvo estable a ~90 los 75 s (bucle 88.6). La caída no coincide en el tiempo con la lectura de la otra cámara: el hallazgo 17 del plan (la que transmite baja cuando la otra intenta abrir) no se confirmó, ni por cv2 ni por COM.
- **Por qué queda:** no se midió la causa y no cambia lo que se envía. Hipótesis sin medir: la luz (B50: alguna sombra o reflejo con la caja al máximo), un control automático de la cámara al arrancar, u otro programa del PC.
- **De dónde:** el P-7b-A del autor, fase 7b · Las dos cámaras a la vez en Windows (meta 007 · El tracker en la Jetson Orin Nano), 2026-11-04 (salidas en `Claude outputs/fases/007/p7b/A1_*`, `A4_*`).
- **Qué haría falta:** repetir una cámara sola 120 s, tres veces, anotando las `[FPS]` de cada 5 s y la luz; si se repite, grabar con `--record` y mirar el brillo de los frames en la caída (B50); y comparar con la parte C (el P-7w largo), que da 450 s por cámara.
- **Prioridad:** media (es una caída de fps en uso; sube a alta si en la parte C alguna cámara baja de 45 fps, P13).

### B93 · `CapaWindowsDShow` queda solo para la sonda; se archiva cuando nada la use
- **Qué:** desde la parte B de la fase 7b el tracker en Windows usa `camera.dshow_props.CapaWindowsCOM` (ADR J7); `CapaWindowsDShow` (`camera/controls.py`, la apertura corta por `cv2` DSHOW) la usan solo `probe_camera --capa cv2`, `--comparar-capas` y sus pruebas (`tests/test_ajustes_camara.py`).
- **Por qué queda:** hoy sirve para comparar las dos capas (B1 del P-7b-B) y como rescate si COM dejara una cámara en otro valor (`--fijar … --capa cv2`); archivarla ahora quitaría esa comparación.
- **De dónde:** el plan de la fase 7b (meta 007), «Lo que va al BACKLOG»; anotada el 2026-11-04 al implementar la parte B.
- **Qué haría falta:** cuando una meta posterior deje de usarla también en la sonda, moverla a `codigo/historico/` con sus pruebas y dejar `--capa com` como única capa (la opción `--capa` podría irse con ella).
- **Prioridad:** baja.

### B94 · La pose de Marker0 desde una cámara sola no coincide entre gs1 y gs2 (19.5 mm / 5.8° en la peor posición) y las 5 posiciones no caben en dos cámaras rígidas
- **Qué:** en el experimento fuera de línea de la fase 1 · Verlo (meta 006 · Grafo de factores óptico-inercial, parte A, `python -m fusion.experiment` sobre la grabación del 2026-11-05 en la Jetson), los extrínsecos T_gs1←gs2 por Marker0 (P12 b, media de `T_gs1←M · T_gs2←M⁻¹` por posición) cambian 17.7 mm / 2.7° (RMS) de una posición de S2 a otra, y el criterio 1 del spec (gs2 llevada a gs1 frente a gs1, validación cruzada, P27) da 19.5 mm / 5.8° en la peor posición frente a < 0.5 mm / < 0.2°. No es ruido (la sd dentro de cada posición es 0.05–0.25 mm, 0.1–0.6°): ajustando a la vez los extrínsecos y la pose del marker en las 5 posiciones (`fusion/bundle.py`, con las 32 combinaciones de la ambigüedad de IPPE) quedan 5.8 px RMS, cuando cada vista sola ajusta a 0.02–0.25 px (gs2 en S2_pos4, 1.25 px); y la distancia entre los centros del marker de dos posiciones, que no depende de los extrínsecos, difiere entre gs1 y gs2 hasta 6.8 mm (S2_pos1–S2_pos2: 62.5 frente a 55.7 mm). S1_reposo y S2_pos1 (el marker en el mismo sitio, grabados seguidos) sí coinciden a 0.4–0.5 mm; en S4 (movimiento), tras alinear rígidamente las dos trayectorias quedan 3.8 mm RMS de diferencia de forma.
- **Por qué queda:** la fase 1 cierra con el número (el plan lo fija: los criterios del spec son el resultado, no el criterio de la fase) y la causa no se separa con esta grabación. Dos hipótesis: (a) una cámara (o las dos, en sus pinzas) se movió entre posiciones al recolocar el soporte del marker; (b) la pose de un marker planar desde una cámara sola tiene un error sistemático de grados en la inclinación que arrastra la profundidad (z·tan θ·δθ: a 30° y 3°, ~10 mm), por los intrínsecos en esa zona de la imagen (gs2, B36), por un marker no plano o no cuadrado, o por el sesgo de las esquinas. Si es (b), el tracker de hoy publica Marker0 con un error de posición de mm que cambia con la vista, y nadie lo ha medido: la meta 002 midió la escala en el plano y la 003 el jitter, no la exactitud en profundidad.
- **De dónde:** fase 1 · Verlo, parte A, de la meta 006 (2026-11-05; informe en `Claude outputs/fases/006/fase-1/corrida-02/informe.html`).
- **Qué haría falta:** (1) repetir S2 sin tocar las cámaras y grabando la posición 1 otra vez al final (desde el 2026-11-05, la Fase 2 · S2 otra vez en Windows, y B94, de la meta 006, con su veredicto) (si pos1-inicio y pos1-final coinciden a < 0.5 mm y las demás no, es (b); si no coinciden, es (a)); (2) los extrínsecos por tablero (independientes de Marker0; desde el replan por P33, la Fase 7 · Los extrínsecos por tablero, que se adelanta si la Fase 2 da «sesgo por vista», P36) y repetir el criterio 1 con ellos; (3) medir la exactitud en profundidad de una cámara sola: Marker0 a distancias y ángulos conocidos (un calibre o la regla de la meta 002) frente a lo que da IPPE; (4) mirar por qué gs2 ajusta a 1.25 px en S2_pos4 (recalibrar gs2 o comprobar la planitud del marker).
- **Veredicto de la Fase 2 · S2 otra vez en Windows, y B94 (2026-11-09, grabación del PC `20261109-163350`, `Claude outputs/fases/006/fase-2/corrida-pc-01/`): «se movió», y B94 sigue abierta.** El veredicto lo dan dos cosas: `repeat_check` (pos1 frente a pos1_fin) 0.703 mm / 0.151°, con el marker devuelto a 2.56 mm / 1.41° de su sitio según gs1 (2.54 mm / 1.50° según gs2), y las mitades de S2_pos2, 0.952 mm / 0.159°. Lo que pesa hacia (b): el ajuste conjunto de las 5 posiciones cabe ahora en dos cámaras rígidas (0.298 px, vista sola ≤ 0.332 px; en la Jetson 5.58 px) y las distancias entre posiciones difieren entre gs1 y gs2 como mucho 0.55 mm (Jetson 6.84), pero los extrínsecos por pose siguen cambiando 15.4 mm / 2.64° de una posición a otra y el criterio 1 da 4.198 mm / 6.087° (Jetson 19.5 mm / 5.82°). Las mitades de S2_pos2 salen de gs2: su orientación salta entre dos soluciones separadas ~5° (la ambigüedad de IPPE; 21 % de los frames en una en la primera mitad, 29 % en la segunda). Que los 0.703 mm de la pos1 repetida vengan del sesgo por vista con el marker mal devuelto, y no de una cámara movida, es hipótesis: la regla no lo separa. Con P36 (a), la Fase 7 · Los extrínsecos por tablero lo separa.
- **Prioridad:** alta (si es (b), el resultado que publica el tracker está mal por mm según la vista; hasta separarlo, ningún número de fusión entre cámaras vale).

### B95 · La pose cruda de IPPE_SQUARE es 1.2–1.5× más ruidosa que la de mínimos cuadrados sobre las mismas esquinas
- **Qué:** con 2000 muestras sintéticas (ruido 0.1 px, `tests/test_fusion_geometry.py`), la sd de la pose de `cv2.solvePnP(IPPE_SQUARE)` es 1.47× la predicha por la jacobiana en la inclinación y 1.18× en la profundidad; la pose por mínimos cuadrados sobre las mismas 4 esquinas (`fusion.geometry.joint_pnp` con una cámara, Gauss-Newton desde la de IPPE) da 1.00 ± 0.02. En la grabación real, la fusión por reproyección (`numpy_reproj`, un PnP conjunto de las dos cámaras) baja la sd 3D en reposo un 63 % frente al 32 % de la media ponderada de las dos poses de IPPE (`numpy_pose`): buena parte de la diferencia es ese refinado, no la segunda cámara.
- **Por qué queda:** toca `vision/pose.py` (la cadena, principio 6) y cambia la pose que publica el tracker con una cámara: pide su plan, su replay y una verificación en vivo; la meta 006 solo lo midió.
- **De dónde:** fase 1 · Verlo, parte A, de la meta 006 (2026-11-05).
- **Qué haría falta:** en el tracker, refinar la pose de IPPE con unas iteraciones de Gauss-Newton sobre la reproyección (o `SOLVEPNP_ITERATIVE` con `useExtrinsicGuess`), medir su coste por frame (~0.1 ms en el PC) y la sd z en reposo frente a la de hoy; con ADR, porque cambia lo que llega a Slicer.
- **Prioridad:** media (bajaría el jitter de una cámara sola sin hardware nuevo; no da un resultado equivocado).

### B96 · El desfase δ entre cámaras (P13) no se distingue en S4: la curva es plana
- **Qué:** sobre S4_movimiento (el marker en la mano a 32 mm/s de media, gs2 con pose en el 71.6 % de los frames), el RMS entre la trayectoria de gs1 y la de gs2 llevada a gs1 (alineada rígidamente a cada δ, con los huecos sin pose fuera) baja solo 0.04 mm (de 3.83 a 3.79 mm) en toda la búsqueda de ±20 ms: el desfase no se separa de la diferencia de forma entre las dos trayectorias (B94). A 32 mm/s, 20 ms de desfase son 0.6 mm.
- **Por qué queda:** el plan daba δ por S4 y S4 no cumplió la comprobación (pose < 90 % en gs2); con B94 abierta el número no se podría interpretar.
- **De dónde:** fase 1 · Verlo, parte A, de la meta 006 (2026-11-05).
- **Qué haría falta:** otro S4 con las dos cámaras viendo el marker todo el rato y movimiento más rápido (≥ 100 mm/s, un vaivén de ~10 cm a 1 Hz), después de resolver B94; o medir δ con la hora del buffer de V4L2 (fase 3 del plan).
- **Prioridad:** baja.

### B97 · Cuánto ancho de banda isócrono reserva cada SVPRO en MJPG 1280x960 90 fps, sin leer su descriptor
- **Qué:** en el PC, con gs1 y gs2 en el mismo concentrador USB 2.0 (Genesys `05E3:0608`, `HS11`) la segunda cámara no daba frames (`0x800718CF`, «sin ancho de banda»; P-7b-B, 2026-11-04) y con gs2 en el frontal USB 3.0 (`…#USB(5)`, fuera del Genesys) las dos van a ~90 fps (P-7b5, 2026-11-05; `docs/CONTEXT.md` §4.21). La causa medida es el enlace compartido; que cada cámara reserve el máximo de un enlace de alta velocidad (~197 Mbit/s, la alternativa de mayor `wMaxPacketSize`) sigue siendo hipótesis.
- **Por qué queda:** la regla de §4.21 (un enlace USB 2.0 por cámara) ya resuelve el uso; el número solo diría si caben dos en un enlace con otro modo o en otro concentrador, y en la Jetson las dos comparten un hub USB 2.0 y sí funcionan (fase 7, 86.2 fps cada una), lo que el número ayudaría a explicar.
- **De dónde:** el P-7b5 de la fase 7b · Las dos cámaras a la vez en Windows (meta 007 · El tracker en la Jetson Orin Nano), 2026-11-05; análisis en `Claude outputs/fases/007/por-que-atorados-7b.md`.
- **Qué haría falta:** leer el descriptor de configuración de cada cámara (las alternativas de la interfaz de vídeo y su `wMaxPacketSize`) con USBView en el PC o `lsusb -v` en la Jetson (por el autor, si necesita `sudo`), y anotar qué alternativa elige cada una en MJPG 1280x960 90 fps.
- **Prioridad:** baja (espera datos; no cambia lo que se envía).

### B98 · La Jetson como fuente del fusionador de la meta 006
- **Qué:** que los dos trackers de la Jetson manden sus esquinas por `--feed` a la IP del PC y el fusionador del PC las use igual que las de los trackers locales.
- **Por qué queda:** P33 (2026-11-05): el PC ya puede con las dos cámaras (P-7b5) y el autor dio prioridad a Windows; la Jetson sale de la meta 006 por ahora. Su CPU va al 95.5 % con los dos trackers (B91).
- **De dónde:** el replan de la meta 006 · Grafo de factores óptico-inercial por P33 (`specs/006-grafo-factores/plan.md`, «Lo que va al BACKLOG»).
- **Qué haría falta:** el mismo `--feed` de la Fase 3 hacia la IP del PC, la regla del cortafuegos, el desfase entre los relojes de las dos máquinas (`clock_offset`, B87; los relojes de la Jetson y del PC son distintos, aunque las dos cámaras de la Jetson comparten el suyo) y la hora del buffer de V4L2. Sustituye a «la hora del buffer de V4L2» y a «MQTT u otro bus» del plan anterior.
- **Prioridad:** baja (no impide usar el sistema: el PC lo hace solo).

### B99 · El ancla de reloj de los `.npz` usa `time.time`, que en Windows con Python 3.11 va a pasos de hasta 15.6 ms
- **Qué:** en el venv (CPython 3.11.9), `time.get_clock_info("time")` da `GetSystemTimeAsFileTime()` con resolución 0.015625 s; medido el 2026-11-05, los pasos reales fueron de 0.35 a 2.0 ms en ese momento: dependen de la resolución del temporizador que pida algún proceso, así que pueden volver a 15.6 ms. `perf_counter` (`QueryPerformanceCounter`, 1e-07 s, común a todos los procesos) no tiene el problema, y el emparejado de las dos cámaras usa solo `perf_counter`.
- **Por qué queda:** solo afecta a la comprobación del ancla de `check_segment`, que exige ≤ 1 ms; la Fase 2 de la meta 006 la abre con `--tolerancia-ancla-ms 20` en el PC, sin tocar `tracker.py`. Así, en Windows esa comprobación solo detecta errores gruesos.
- **De dónde:** el replan de la meta 006 por P33 (2026-11-05).
- **Qué haría falta:** en `tracker.py` (la cadena, principio 6), tomar el ancla con `GetSystemTimePreciseAsFileTime` por `ctypes` (resolución de ~1 µs) o, si se pasa a Python 3.13, con `time.time()`, que allí usa ese reloj (hipótesis: no confirmado en Context7); y volver a 1 ms.
- **Prioridad:** baja (no cambia ningún resultado: el emparejado no la usa).

### B100 · El suelo de ruido de `half_split` frente al umbral de 0.5 mm del veredicto de B94
- **Qué:** `fusion.extrinsics.half_split` calcula los extrínsecos de las dos mitades de un tramo y su diferencia; el veredicto «se movió» (`b94_rule`) lo da si la diferencia de algún tramo llega a 0.5 mm o 0.2°. Sobre la grabación de la Jetson `20261105-120826` (informativo, sin la pos1 repetida) las mitades dan: S2_pos1 0.566 mm / 0.091° (1961 parejas), pos2 0.334 / 0.047, pos3 0.437 / 0.063, pos4 0.280 / 0.043, pos5 0.119 / 0.018. La pos1 supera el umbral dentro de un mismo tramo, con el marker supuestamente quieto: o algo se movía despacio, o el ruido de los extrínsecos por mitades ya es del orden de 0.5 mm y el umbral no lo separa del movimiento.
- **Por qué queda:** el umbral es el del criterio 1 del spec, no está medido como suelo de ruido de este método; la grabación de Windows (Fase 2, en vivo pendiente) da los seis tramos y dirá si el umbral vale (todas las mitades < 0.2 mm) o no (todas rondan 0.5 mm).
- **En el PC (2026-11-09, grabación `20261109-163350`, 1284–2343 parejas por tramo):** S2_pos1 0.099 mm / 0.018°, pos2 0.952 / 0.159, pos3 0.315 / 0.054, pos4 0.084 / 0.016, pos5 0.057 / 0.013, pos1_fin 0.175 / 0.029. Cinco de seis quedan bajo el umbral, cuatro bajo 0.2 mm: en el PC el suelo es ~0.06–0.3 mm, por debajo de los 0.566 de la Jetson. La pos2 (0.952 mm, 1.7 veces los 0.566 de la Jetson) no es ruido de este suelo: gs2 salta entre dos soluciones de IPPE (B94) y la mezcla cambia entre mitades. El «se movió» de esta corrida no viene solo de las mitades (también `repeat_check`, 0.703 mm). Los umbrales no se cambiaron.
- **De dónde:** la fase 2 · S2 otra vez en Windows, y B94 (meta 006 · Grafo de factores óptico-inercial), 2026-11-05; nota en `Claude outputs/fases/006/fase-2-implementa.md`.
- **Qué haría falta:** con la grabación de Windows, medir la sd de los extrínsecos por bloques de un mismo tramo (p. ej. 4 u 8 bloques) y fijar el umbral de las mitades como un múltiplo de esa sd; o cerrar el veredicto «se movió» solo con `repeat_check` (pos1 frente a pos1_fin) y dejar las mitades como aviso. Antes de leer un «se movió» que venga solo de las mitades, la dirección mira este número.
- **Prioridad:** media (puede dar un «se movió» falso y repetir la sesión sin necesidad, o un «cumple» con la cámara en movimiento lento).

### B101 · Las dos ventanas del tracker llevan el mismo título y se abren en el mismo sitio
- **Qué:** con dos trackers con ventana a la vez (M1 de `grabacion-pc/correr.ps1`, Fase 2 de la meta 006), el título de la ventana es el mismo en los dos y la posición también; una puede salir encima de la otra y el autor no distingue cuál es gs1 y cuál gs2.
- **Por qué queda:** darle un título o una posición por perfil (`WINDOW_TITLE` o un campo del perfil) toca `tracker.py` (la cadena, principio 6) y pide su plan, el replay y su verificación en vivo; la Fase 2 solo toca `fusion/`.
- **De dónde:** la fase 2 · S2 otra vez en Windows, y B94 (meta 006), 2026-11-05.
- **Qué haría falta:** que el título lleve el nombre del perfil (`Tracker gs1`, `Tracker gs2`) y, si hace falta, un desplazamiento en x; la prueba en `test_tracker_loop.py` de que sin ese campo el título no cambia. Mientras tanto, el autor arrastra una ventana a un lado al abrirlas.
- **Prioridad:** baja (estorba solo en la mirilla y en los tramos con ventanas; no cambia ningún resultado).

### B102 · Las parejas reales de la grabación del PC quedan bajo las 2000 de P16 aunque el script estime más
- **Qué:** en la grabación de S2 del PC (`grabacion-pc/correr_20261109-163350`, tramos de 40 s), `correr.ps1` estima las parejas como el mínimo de frames con pose de las dos cámaras (2596–3519 por tramo, todas «cumple»), pero `fusion.experiment` empareja 2338, 1284, 1698, 1852 y 2343 en las cinco posiciones (1842 en pos1_fin): tres de cinco quedan bajo las 2000 de P16 (el informe lo avisa en la nota del criterio 1). Dos causas medidas: gs2 arranca ~8 s después que gs1 (8.06–8.9 s), así que el solape es ~31–32 s de 40; y el emparejado admite medio periodo (5–6 ms), así que con el bucle a 65–75 fps (pos2, pos3) se queda sin pareja el ~25–40 % de los frames del solape (a ~85–88 fps, el ~15 %).
- **Por qué queda:** la Fase 2 cierra con el veredicto de B94 y el siguiente paso, por P36, es la Fase 7 (el tablero); el script está fuera de git y no se toca en un cierre.
- **De dónde:** la fase 2 · S2 otra vez en Windows, y B94 (meta 006 · Grafo de factores óptico-inercial), 2026-11-09; reporte en `Claude outputs/fases/006/fase-2.md`, «En vivo (2026-11-09)».
- **Qué haría falta:** si se repite S2 (o en la grabación de la Fase 7), contar las parejas con el solape real (desde que arrancan las dos) o con `fusion.dataset`, y alargar los tramos a ~60 s o esperar a que las dos cámaras den frames antes de empezar a contar los 40 s.
- **Prioridad:** media (con menos parejas que P16 el criterio 1 se lee con menos datos de los pedidos; no cambia lo que publica el tracker).

### B103 · El filtro z ≤ 0 de `estimate_single_pose` no atrapa el salto de IPPE_SQUARE entre sus dos soluciones, y el tracker lo publica a Slicer
- **Qué:** con 4 puntos coplanares, `SOLVEPNP_IPPE_SQUARE` tiene casi siempre dos soluciones de reproyección parecida, que se diferencian en la inclinación del marker (la doc de OpenCV, por Context7: «the estimation of the pose using only 4 coplanar points is subject to ambiguity»; `solvePnPGeneric` devuelve las dos). `vision/pose.py:estimate_single_pose` usa `cv2.solvePnP`, que devuelve solo una, y descarta la pose si `tvec z ≤ 0`; su docstring dice que la solución equivocada es la que queda detrás de la cámara. En el caso típico las dos quedan delante (z > 0), así que el filtro no atrapa el salto: el tracker manda a Slicer un `Marker0ToTracker` cuya orientación salta varios grados entre frames, con la posición casi igual. Ya se vio en la grabación del PC de la Fase 2 de la meta 006 (`20261109-163350`, S2_pos2): la orientación de gs2 salta entre dos soluciones separadas ~5° en el 21–29 % de los frames (B94, B100).
- **Por qué queda:** salió en la sesión de entendimiento del paso 9 · La pose (PnP) del HTML `Claude outputs/fases/007/como-funciona-tracking.html` (2026-11-09); arreglarlo toca `vision/pose.py` (la cadena, principio 6) y cambia lo que llega a Slicer: pide su plan, su replay y una verificación en vivo. Cuánto pasa con una cámara sola, en las vistas de uso, no está medido: lo de gs2 en S2_pos2 es una vista.
- **De dónde:** la dirección, explicando el paso 9 al autor (2026-11-09).
- **Qué haría falta:** (1) medirlo fuera de línea sobre las grabaciones con esquinas (Jetson `20261105-120826`, PC `20261109-163350`): con `solvePnPGeneric(IPPE_SQUARE)`, por frame, el cociente de los errores de reproyección de las dos soluciones y cuántos frames cambian de solución respecto al anterior; (2) elegir la regla: descartar la pose si el cociente es cercano a 1, elegir la más cercana a la del frame anterior, o refinar (B95); (3) corregir el docstring de `estimate_single_pose`; (4) con dos cámaras, el fusionador por reproyección de la meta 006 (P39) lo resuelve en las vistas que ven las dos, pero solo si arranca bien: `fusion.geometry.joint_pnp` es local (Gauss-Newton) y `experiment.fuse_pair` lo arranca desde `T0 = Z1`, la solución de IPPE que eligió gs1; si gs1 eligió la inclinación equivocada, puede quedarse en un mínimo local (hipótesis alta, sin medir). Para la Fase 4 · El fusionador del PC, sin GTSAM: arrancar desde las 2×2 soluciones de `fusion.dataset.ippe_solutions` (las dos de cada cámara, gs2 llevada a gs1) y quedarse con la de menor RMS, como hacía `fusion/bundle.py` con sus 32 combinaciones; medirlo antes sobre S2_pos2 del PC. Con ADR si cambia la pose publicada.
- **Prioridad:** alta (da un resultado equivocado en la orientación que recibe Slicer, ya observado en gs2; no sabemos aún cuánto con una cámara en uso normal).

### B104 · Un tramo repetido por los `correr.ps1` de grabación (`<tramo>_r2_<cámara>.npz`) no lo encuentra `fusion.dataset.segment_file` (`<tramo>_<cámara>_r2.npz`)
- **Qué:** los tres scripts de grabación de la meta 006, fuera de git (`Claude outputs/fases/006/grabacion/correr.ps1`, `grabacion-b94/correr.ps1` y `grabacion-pc/correr.ps1`), nombran un tramo repetido con el intento antes de la cámara (`"$($seg.id)_r$k"` y luego `_<cámara>.npz`: `S2_pos3_r2_gs1.npz`). `fusion.dataset.segment_file` busca el intento después de la cámara (`<segmento>_<cámara>_r*.npz`: `S2_pos3_gs1_r2.npz`), y `--intento S2_pos3=r2` también. Si el autor repite un tramo con `r`, el experimento no ve la repetición: usa el primer intento (el que no cumplió) sin decirlo, salvo por el nombre de archivo en `comprobacion.<segmento>.files`. Leído en el código de los dos lados; no ha pasado todavía: en la grabación del PC (`20261109-163350`) no se repitió ningún tramo y en la de la Jetson solo la mirilla (`M1_r2`, `M1_r3`), que el experimento no lee.
- **Por qué queda:** salió al escribir el script del tablero (Fase 7 · Los extrínsecos por tablero), que ya nombra sus repeticiones como espera el código (`T05_gs1_r2_frames`); arreglar los scripts de las fases 1 y 2 o `segment_file` no es de esta fase, y `fusion/dataset.py` no está entre sus archivos.
- **De dónde:** la fase 7 · Los extrínsecos por tablero, independientes de Marker0 (meta 006 · Grafo de factores óptico-inercial), 2026-11-09; nota en `Claude outputs/fases/006/fase-7-implementa.md`.
- **Qué haría falta:** una de dos, con su prueba: que `segment_file` admita también `<segmento>_rN_<cámara>.npz` (y falle si encuentra las dos formas), o cambiar el nombre en `grabacion-pc/correr.ps1` antes de volver a usarlo. Mientras tanto, si se repite S2 con ese script y se usa `r`, renombrar a mano los `.npz` del intento bueno antes de correr `fusion.experiment` y comprobar `files` en `resultados.json`.
- **Prioridad:** media (el experimento usaría un intento que el script marcó como «no cumple», con el marker en el mismo sitio: menos datos o un tramo fuera, no una pose equivocada; no toca lo que publica el tracker).

### B105 · `diagnostics.probe_camera._vigilante` no para el proceso si `estado` no se puede escribir como JSON
- **Qué:** el vigilante del tope (`_vigilante(timeout, estado, salida)`, que usan `probe_camera`, `calibration.calibrate_camera` y desde la Fase 7 `calibration.calibrate_extrinsics`) escribe `estado` con `json.dumps` a secas dentro de un `try` que solo atrapa `OSError`, y después llama a `os._exit(2)`. Si `estado` lleva algo que JSON no admite (un `ndarray`, un `Path`), `json.dumps` lanza `TypeError` en el hilo del temporizador, el hilo muere y `os._exit` no llega a ejecutarse: el tope no para nada y nadie lo dice. Leído en el código; no se ha visto fallar.
- **Por qué queda:** `diagnostics/probe_camera.py` no es de la Fase 7. `calibrate_extrinsics` lo esquiva guardando en `estado` solo tipos de JSON (una prueba lo fija: `test_el_estado_que_escribiria_el_vigilante_es_json`).
- **De dónde:** la fase 7 · Los extrínsecos por tablero, independientes de Marker0 (meta 006 · Grafo de factores óptico-inercial), 2026-11-09.
- **Qué haría falta:** que `disparar` atrape cualquier excepción al escribir (o use `default=str`) y llame siempre a `os._exit(2)` en un `finally`; una prueba con un `estado` no serializable y un `os._exit` falso.
- **Prioridad:** baja (`calibrate_extrinsics` guarda solo tipos de JSON, con su prueba; en `probe_camera` y `calibrate_camera` no se ha comprobado qué llevan en `estado` en cada momento; es una trampa para el siguiente).

### B106 · El 1-Euro de hoy deja la posición hasta ~3 mm detrás del marker cuando se mueve
- **Qué:** con los parámetros de los perfiles (`min_cutoff` 2.0 Hz, `beta` 0.05), simulando `vision.filtering.OneEuroFilter` a 90 fps con rampas de velocidad constante (2026-11-09, la dirección, sin cámara), el retraso de la posición filtrada es 0.24 mm a 5 mm/s, 0.57 a 20, 1.26 a 100, 2.17 a 500 y 2.78 a 2000 mm/s; el tope teórico es `1/(2π·beta)` ≈ 3.2 mm. En reposo baja la sd de un ruido blanco de 0.050 a 0.013 mm (el ruido real tiene deriva lenta y bajará menos, hipótesis alta).
- **Por qué queda:** para Marker0 (la referencia ósea, casi quieta) importa poco; importará cuando haya un instrumento que se mueva (la punta se rehace, ADR-025).
- **De dónde:** la dirección, explicando al autor el paso 10 de `Claude outputs/fases/007/como-funciona-tracking.html` (2026-11-09).
- **Qué haría falta:** cuando exista el instrumento, medir el retraso real con un movimiento conocido y elegir `beta` por perfil (subirlo baja el retraso y deja pasar más ruido); los perfiles ya lo admiten sin tocar código.
- **Prioridad:** baja (solo si estorba; no cambia nada de Marker0 quieto).

### B107 · La hora del mensaje TRANSFORM es la del envío (`time.time` de pyigtl), no la de captura
- **Qué:** `transport.igtl.IgtlSender.send` crea `pyigtl.TransformMessage(M, device_name=...)` sin `timestamp`, y pyigtl 0.3.1 pone `time.time()` al crear el mensaje (`pyigtl/messages.py:35`): es la hora del envío, no la del frame (`perf_counter` del `FrameGrabber`). En Windows con Python 3.11, `time.time` puede avanzar a pasos de hasta 15.6 ms (B99). La diferencia con la captura es la latencia del bucle más ese paso.
- **Por qué queda:** hoy Slicer no usa esa hora para nada que veamos (hipótesis alta); estorbará si algo la usa (sincronizar con el IMU, grabar en Slicer y compararlo con la cámara). Pasarle la hora de captura toca `transport/` (la cadena, principio 6) y cambia los bytes del mensaje.
- **De dónde:** la dirección, explicando al autor el paso 11 del mismo HTML (2026-11-09).
- **Qué haría falta:** decidir qué reloj de pared se manda (la hora de captura convertida a época con un ancla `time.time_ns`/`perf_counter` al arrancar) y pasarla como `timestamp=`; comprobar en Slicer que el nodo no cambia.
- **Prioridad:** baja (espera a que algo use la hora).

### B108 · En la fusión, los frames que ve una sola cámara pasan tal cual y pueden dar un escalón en Slicer
- **Qué:** `fusion.experiment.fused_timeline` fusiona las parejas y deja pasar tal cual los frames con pose de una sola cámara (gs2 llevada a gs1 con los extrínsecos). En esos frames vuelve todo lo de una cámara sola (B103, B95), y al pasar de «fusionado» a «solo gs1» o «solo gs2» la pose publicada puede saltar varios mm si los extrínsecos o la pose de una cámara tienen sesgo (B94: el criterio 1 dio 4.2 mm / 6.1° en el PC).
- **Por qué queda:** el fusionador en vivo es la Fase 4 · El fusionador del PC, sin GTSAM, de la meta 006; hoy solo existe fuera de línea.
- **De dónde:** la dirección, explicando el fusionador al autor (2026-11-09).
- **Qué haría falta:** en la Fase 4, decidir y medir qué se publica con una sola cámara (tal cual, nada, o un PnP de una cámara arrancado en la última pose fusionada) y medir el escalón en una grabación con oclusiones; que el criterio de la Fase 5 lo incluya.
- **Prioridad:** media (con extrínsecos buenos el escalón debería ser pequeño; sin medir).

### B109 · El emparejado por hora admite medio periodo: con el marker en movimiento, el PnP conjunto mezcla dos instantes
- **Qué:** el fusionador empareja un frame de gs1 con uno de gs2 si sus horas de captura difieren hasta medio periodo (~5–6 ms a 90 fps). Con el marker quieto no importa; en movimiento, las dos cámaras lo vieron en sitios distintos y `joint_pnp` busca una pose que explique a la vez dos posiciones: a 100 mm/s, 5 ms son 0.5 mm; a 500 mm/s, 2.5 mm. El residuo sube y la pose queda entre las dos. El desfase δ entre relojes (P13) no se pudo medir (B96).
- **Por qué queda:** la meta 006 mide el criterio con el marker en reposo; el movimiento rápido llega con el instrumento.
- **De dónde:** la dirección, explicando el fusionador al autor (2026-11-09).
- **Qué haría falta:** medir en una grabación en movimiento el residuo del PnP conjunto frente a la diferencia de horas de cada pareja; si crece, interpolar la pose de una cámara a la hora de la otra, o el modelo de velocidad del grafo de GTSAM (Fase 6).
- **Prioridad:** media (puede dar mm de error en movimiento rápido; no afecta al reposo).

### B110 · El RMS de reproyección del PnP conjunto podría avisar en vivo de una cámara movida
- **Qué:** `fusion.geometry.joint_pnp` devuelve el RMS de reproyección de las 8 esquinas. Con extrínsecos buenos queda cerca del de una vista sola (~0.2–0.3 px en el PC); con extrínsecos que no casan sube mucho (12.9 px en la Jetson, B94). Si alguien golpea una cámara durante el uso, los extrínsecos dejan de valer y ese RMS lo delataría sin hardware nuevo.
- **Por qué queda:** el fusionador en vivo aún no existe (Fase 4) y el umbral no está medido. Es una propuesta, no un fallo.
- **De dónde:** la dirección, explicando el fusionador al autor (2026-11-09).
- **Qué haría falta:** en la Fase 4 o 5, publicar el RMS (en el log o en el panel) y fijar el umbral con la sd del RMS en reposo; con un valor sostenido por encima, avisar y, si el autor lo decide, dejar de publicar la pose fusionada.
- **Prioridad:** media (mejora clara de seguridad sin riesgo; no cambia la pose).

### B111 · gs2 grabó a 41.4 fps en un tramo de la sesión del tablero cortada
- **Qué:** en T03 de `Claude outputs/fases/006/fase-7/correr_20261110-180748`, el bucle de gs2 grabó 4 frames a 41.4 fps; en el resto de tramos, 84–88. Causa desconocida (¿la luz, B50?).
- **Por qué queda:** un solo tramo; la vista salió usable. El asistente de la Fase 7a da los fps por tramo y dirá si se repite.
- **De dónde:** el plan de la Fase 7a · El asistente de captura del tablero (meta 006, replan del 2026-11-10).
- **Qué haría falta:** mirar los fps por tramo de la sesión del asistente; si se repite, medirlo con la caja al máximo y una sola variable. Si algún tramo da < 85 fps, la entrada sube a media con ese número.
- **Prioridad:** baja (un tramo, sin efecto en la vista).

### B112 · El asistente del tablero podría servir para los intrínsecos
- **Qué:** `calibration.capture_stereo_board` (Fase 7a) con una sola cámara sustituiría la captura por ESPACIO de `calibration.calibrate_camera.capturar_vistas`: captura sola al quedar quieto y con variedad medida.
- **Por qué queda:** los intrínsecos de gs1 y gs2 valen (meta 002); solo hace falta si hay que recalibrarlos.
- **De dónde:** el plan de la Fase 7a (meta 006, replan del 2026-11-10).
- **Qué haría falta:** un modo de una cámara en el asistente y que `calibrate_camera` lea sus vistas; con su plan.
- **Prioridad:** baja (solo si hay que recalibrar intrínsecos: B36, o la estructura del autor).

### B113 · El asistente no comprueba en vivo el orden de las esquinas ni la coherencia de la vista
- **Qué:** el asistente de la Fase 7a no corre `emparejar_orden` durante la sesión; una vista incoherente (el tablero movido entre cámaras, imposible con la ráfaga simultánea salvo un golpe) la aparta el cálculo de `calibrate_extrinsics`.
- **Por qué queda:** con la captura simultánea es improbable; comprobarlo en vivo añade tiempo a cada ráfaga.
- **De dónde:** el plan de la Fase 7a (meta 006, replan del 2026-11-10).
- **Qué haría falta:** solo si el cálculo aparta más de 2 vistas de una sesión del asistente: correr la coherencia en el hilo de la comprobación.
- **Prioridad:** baja (espera datos).

## Cerrados

### B79 · `igtl_rate listen` se para a los 5 s sin datos
- **Qué era:** si Marker0 no se veía al arrancar el tracker, `diagnostics.igtl_rate listen` se rendía a los 5 s sin mensajes y la corrida no medía nada aunque el tracker siguiera vivo (P-5, fase 5; y en el P-6, fase 6, impidió la corrida d): abrir la cámara en el PC tardó ~8 s).
- **Cerrado:** 2026-11-04, por la fase 7b · Las dos cámaras a la vez en Windows, parte A (meta 007): `igtl_rate listen --idle-s <segundos>` (y `listen(..., idle_s=)`) fija cuánto espera conectado sin recibir nada; sin la opción siguen los 5 s de `NO_DATA_S`, y 0 o negativo se rechaza (código 2). El P-7b y el P-7w lo usan con 60. Con `tests/test_igtl_rate.py`. Queda sin explicar por qué la misma marca tardó 6.11 s en el P-6 y 1.26 s en otra corrida; la opción lo cubre, no lo explica.

### B81 · `linux.perfil_temporal` está en la lista blanca del guardián y no existe
- **Qué era:** la lista blanca de módulos de `py` en `codigo/linux/guardian.py` nombra `linux.perfil_temporal`, y ese módulo no estaba en `codigo/linux/`.
- **Cerrado:** 2026-11-03, por la fase 5b · El ruido de gs1 por V4L2 (meta 007; P25 = (a)): `codigo/linux/perfil_temporal.py` (`--base`, `--salida`, `--puerto`, `--poner`) con `tests/test_perfil_temporal.py`. El guardián no cambió.

### B74 · Las pruebas del sha de la calibración dependen del fin de línea del `.yml`
- **Qué era:** `test_como_funciona` y `test_explain_pose[gs1]` comparaban el sha256 de los bytes de `codigo/data/intrinsecos_gs1_1280x960.yml` con el que guardó la grabación, que es el del archivo con CRLF (`0b4250e5…`); git y la Jetson lo tienen en LF (`0da9280e…`), y las dos fallaban sin que cambiara ningún valor.
- **Cerrado:** 2026-11-02, por la fase 4 · La suite corre en Linux (meta 007 · El tracker en la Jetson Orin Nano): `diagnostics/explain_pose.py:comparar_sha_grabado` compara el sha grabado con el del `.yml` tal cual, con LF y con CRLF, y dice cuál coincidió (`sha_eol`); la prueba exige además que K y dist sean iguales. No se regeneraron las grabaciones ni sus referencias. Pasa en el PC (gs1 en LF) y en la Jetson.

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

