# Aclaraciones — Meta 002 · Calibración de las cámaras global shutter

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

## P1 · Cómo se identifica cada cámara si las dos son del mismo modelo

- **Opciones:** (a) Recomendada: el perfil declara `device_id` (un trozo de la instancia USB que da Windows, p. ej. `6&325DB0BA&1`) y el backend lo traduce a índice enumerando Media Foundation por `ctypes`, sin dependencia nueva. Si las cámaras no traen número de serie, la instancia depende del puerto: cada cámara va siempre al mismo puerto, etiquetado. Cuesta un módulo de ~150 líneas y la fase 1 confirma que el orden coincide con el índice de OpenCV. (b) Dependencia nueva para enumerar (p. ej. `pygrabber` o `comtypes`, por DirectShow): menos código propio, pero una dependencia más en `requirements.txt` y el orden de DSHOW puede no ser el de MSMF. (c) Sin enumeración: `source` explícito en cada perfil, puertos etiquetados y una comprobación a ojo al abrir. No cuesta código, pero un índice cambiado abre la cámara equivocada con la calibración de la otra sin aviso.
- **Respuesta del autor:** Puerto USB fijo (a): `device_id` en el perfil, enumeración por `ctypes`, cada cámara en su puerto etiquetado.
- **Fecha:** 2026-10-20

## Enmienda del umbral de FPS (autor, 2026-10-20)

- En la sesión en vivo de la Fase 1 · Sonda de controles, modos e identidad, la cámara 1 dio ~90 fps de captura en MJPG por MSMF de 320×240 a 1280×960 (29–30 fps a 1920×1080 y 1920×1200). El autor: «si el máximo es 90, usemos esa sobre los 60». El umbral de la elección de resolución pasa de ≥ 60 a **≥ 90 fps** (de tracking con ventana, P2). Si ninguna resolución lo sostiene en tracking, se aplica lo mismo que el spec decía para 60: se reporta como hallazgo para la meta de optimizar el tracker y el autor elige con la tabla.
- **Fecha:** 2026-10-20

## P2 · Qué cuenta como «FPS de tracking» para el umbral de 60

- **Opciones:** (a) Recomendada: con la ventana del tracker (`imshow` + `waitKey(1)`), como se opera, y sin la impresión por frame de `verbose`; la tabla da también la cifra sin ventana. (b) Sin ventana: mide solo captura + detección + pose; da una resolución mayor, pero puede no sostenerse con la ventana abierta.
- **Respuesta del autor:** Con ventana (a); la tabla da también la cifra sin ventana.
- **Fecha:** 2026-10-20

## P3 · El Marker0 de los perfiles gs1 y gs2

- **Opciones:** (a) Recomendada: 80 mm, el que se usó en P02 con la cámara 1, medido con calibrador al crear el perfil. (b) 60 mm, como `tracker_config_doctor.yaml`.
- **Respuesta del autor:** 80 mm (a), medido con calibrador al crear el perfil.
- **Fecha:** 2026-10-20

## P4 · Si se versionan los `.yml` de intrínsecos y los perfiles nuevos

- **Opciones:** (a) Recomendada: se versionan los dos (`.gitignore` ya no ignora `.yml` ni `.yaml`; `globalshutter.yml` está versionado): quien hace `git pull` recibe la calibración de cada cámara física con su `device_id`. (b) Solo los perfiles; los `.yml` quedan por equipo, fuera de git, como la punta: hay que añadir una regla a `.gitignore` y el perfil apunta a un archivo que otro equipo no tiene.
- **Respuesta del autor:** Se versionan los dos (a).
- **Fecha:** 2026-10-20

## P5 · Qué pasa con `globalshutter.yml` y `tracker_config_doctor.yaml`

- **Opciones:** (a) Recomendada: se quedan como están en esta meta; al cerrar, con los números de las fases 4–6, el autor decide si el doctor pasa a gs1 o gs2 (cambio de una línea, con su fase o su meta). (b) En la fase 5, el perfil doctor apunta al `.yml` de la cámara que use el doctor (toca el runbook y el contexto doctor dentro de esta meta). (c) `globalshutter.yml` pasa a `data/historico/` al cerrar.
- **Respuesta del autor:** Archivar el viejo (c), y precisado en el chat el mismo día: no hay que preocuparse por los perfiles anteriores (`tracker_config_doctor.yaml`, `tracker_config.yaml` de la Femto, `globalshutter.yml`): ya no se usarán; solo valen los perfiles nuevos que genere esta meta. Se deja de distinguir entre perfil del doctor y perfil del autor. El proyecto se está relevantando: de lo que hay se rescata el tracking; lo que va después (punta, registro, navegación en Slicer) se rehará mejorado en metas siguientes. Esta meta no gasta trabajo en adaptar ni mantener los perfiles viejos; qué se hace con ellos (archivarlos) va al cierre o a otra meta.
- **Fecha:** 2026-10-20

## P6 · El umbral de la comprobación de escala

- **Opciones:** (a) Recomendada: |error| ≤ 1.0 mm por cada 100 mm de desplazamiento del tablero contra una regla (1 %; la regla y la base deslizante aportan ~0.5 mm). (b) ≤ 0.5 mm por 100 mm: más exigente; necesita un tope o un riel en vez de una regla.
- **Respuesta del autor:** 1.0 mm por cada 100 mm (a).
- **Fecha:** 2026-10-20

## P7 · La luz de las sesiones con cámara

- **Opciones:** (a) Recomendada: la caja de luz en un nivel fijo sin parpadeo (P02: nivel ≥ 2), el mismo en todas las sesiones, con la luz de la sala en el estado que el autor diga; cada medición lo anota en `--luz`. (b) Medir en dos niveles (el de trabajo y uno alto) para ver si la exposición fija aguanta los dos: duplica el tiempo de la fase 3.
- **Respuesta del autor:** Nivel fijo sin parpadeo (a): la caja de luz en **nivel 2** en todas las sesiones de esta meta. El nivel óptimo se buscará después, con las cámaras ya calibradas (fuera de esta meta).
- **Fecha:** 2026-10-20

## P8 · Si las dos cámaras usan la misma resolución

- **Opciones:** (a) Recomendada: la misma para las dos, la mayor que las dos sostienen a ≥ 60 fps de tracking: son el mismo modelo y así los números se comparan. (b) Cada una la suya, aunque difieran.
- **Respuesta del autor:** La misma para las dos (a).
- **Fecha:** 2026-10-20

## P9 · Si la Fase 2 se parte en 2a (medir) y 2b (backend)

- **Opciones:** (a) Recomendada: dos fases con su commit cada una. La 2a añade la ruta del puerto, la enumeración DSHOW y la capa de ajustes, y mide con las dos cámaras (identidad en 6 enumeraciones, orden DSHOW, MSMF frente a DSHOW, Auto de AMCap, coste, marca opcional) sin tocar el backend; la 2b toca `camera_backend.py` solo con eso medido. Si la medición falla, no se ha tocado el backend. Las fases 3–6 conservan su número. (b) Una sola Fase 2 con una parada interna entre medir y tocar el backend: un commit menos, pero si la medición obliga a cambiar el diseño, el commit mezcla código que se tira.
- **Respuesta del autor:** Sí (a): Fase 2a (medir identidad y controles con las dos cámaras) y Fase 2b (perfiles y backend), un commit cada una.
- **Fecha:** 2026-10-21

## P10 · En qué unidad se declara la exposición en el perfil

- **Opciones:** (a) Recomendada: en milisegundos (`exposure_ms`), una unidad física que no depende del sistema; la capa de Windows la convierte a log2 de segundos de DSHOW (3.906 ms → −8) y para si no es un valor representable, con los válidos cercanos; la de Linux la convertiría a las unidades de 100 µs de V4L2. Cuesta una conversión con prueba. (b) El valor nativo de cada sistema, en una sección por sistema (`windows: {exposure: -8}`): sin conversión, pero el perfil deja de ser independiente del sistema y cada valor hay que medirlo dos veces.
- **Respuesta del autor:** Milisegundos (a): `exposure_ms` en el perfil; la capa de Windows convierte y para si no es representable.
- **Fecha:** 2026-10-21

## P11 · La tolerancia del umbral de 90 fps

- **Opciones:** (a) Recomendada: ≥ 90 fps con un 2 % de tolerancia (≥ 88.2 fps sostenidos 30 s). En la Fase 1 la captura sola dio 89.6–90.2 fps a 90 pedidos: con ≥ 90.0 estricto, el ruido de la medida descartaría modos que sí van a 90. (b) ≥ 90.0 estricto. (c) Otra tolerancia que diga el autor.
- **Respuesta del autor:** ≥ 88.2 fps (a), un 2 % bajo 90.
- **Fecha:** 2026-10-21

## P12 · El criterio de saturación para elegir la exposición

- **Opciones:** (a) Recomendada: fracción de píxeles a 255 dentro de la envolvente de los markers del dodecaedro (con 10 px de margen) ≤ 1 %, y FPS de captura ≥ 88.2; entre las que cumplen, la de más markers por vista, y a igualdad la mayor exposición (menos ruido). Candidatas: 7.8, 3.9, 1.95, 0.98 y 0.49 ms, a 1280×960 MJPG. (b) Brillo medio de la imagen bajo un umbral (p. ej. ≤ 180): más simple, pero el brillo medio no ve la saturación local sobre los markers. (c) Otro umbral de fracción saturada.
- **Respuesta del autor:** ≤ 1 % de píxeles a 255 sobre el dodecaedro (a).
- **Fecha:** 2026-10-21

## P13 · Si la marca en `focus` se usa al abrir, cuando la 2a la valide

- **Opciones:** (a) Recomendada: sí. Si la 2a mide que escribir `focus` no cambia la imagen (brillo y nitidez dentro del 2 %) y que persiste tras desenchufar, cada perfil declara `marca: {focus: N}` con un valor distinto por cámara, y el backend para si el `focus` leído no es el suyo: detecta el intercambio de cámaras entre puertos. Cuesta una lectura en la apertura DSHOW que ya se hace. (b) No: solo etiquetas en cámara, cable y puerto; el intercambio no se detecta y va al BACKLOG con prioridad alta.
- **Respuesta del autor:** Sí, si la Fase 2a lo valida (a): la marca en `focus` se comprueba al abrir.
- **Fecha:** 2026-10-21

## P14 · Qué se hace si la 2a muestra que MSMF pisa los controles de DSHOW o que el Auto de exposición no se desmarca

- **Opciones:** (a) Recomendada: la 2b no empieza y planificación replantea la capa de Windows con `IAMCameraControl`/`IAMVideoProcAmp` directos por `ctypes` COM (sin dependencia nueva; el moniker ya lo da la enumeración DSHOW de la 2a): permite escribir con la bandera manual y leerla, y no abre el vídeo. Cuesta ~150 líneas de COM sin contraste en Context7 y su verificación en vivo. (b) Aceptarlo y documentarlo: el autor deja la exposición en manual con AMCap y el backend solo comprueba los valores. (c) Otra que diga el autor.
- **Respuesta del autor:** Parar y decidir (b): si MSMF cambia los controles o la exposición no sale de Auto, la meta se para y el autor decide con los datos. No se replanea por adelantado la capa con `IAMCameraControl` directo.
- **Fecha:** 2026-10-21

## P15 · Qué exposición común se deja en las dos cámaras (Fase 3, Medición 1)

- **Contexto:** Medición 1 a 1280×960 MJPG, caja en nivel 2, dodecaedro a ~60 cm (`Claude outputs/camaras/exposicion_gs1.json`, `exposicion_gs2.json`). La exposición por DSHOW gobierna (leída = pedida; brillo monótono: cám. 1 250 → 244 → 216 → 173 → 124; cám. 2 250 → 245 → 215 → 169 → 120) y la captura queda en 89.4–90 fps en todas. `--elegir` propone 3.906 ms (empate de markers → la más larga), con brillo medio 244–245: la fracción a 255 (0.0–0.3 %) no ve lo que la compresión MJPG deja en 250–254.
- **Opciones:** (a) Recomendada: 0.977 ms (−10 por DSHOW): brillo ~170, mismos markers (5 y 4), 90 fps, ~4 veces menos estela de movimiento que 3.906. (b) 1.953 ms. (c) 3.906 ms, la del script. (d) 0.488 ms.
- **Respuesta del autor:** 0.977 ms (a), la misma en las dos cámaras.
- **Fecha:** 2026-10-22

## P16 · A qué resolución quedan los perfiles y se calibran las cámaras (Fase 3, Medición 2)

- **Contexto:** Medición 2 con 0.977 ms (`Claude outputs/camaras/modos_gs1.json`, `modos_gs2.json`). Captura ~90 fps en todos los modos de las dos cámaras, incluidos 1920×1080/1200 MJPG y YUY2 (con la aceleración HW de MSMF apagada; en la fase 1, encendida, daban ~30 y ≤ 59). Tracking sin ventana: 320×240 90, 640×480 90, 960×720 68/67, 1280×720 64, 1280×960 62 fps. Con ventana: 19–25 fps en todos los modos: la ventana es el cuello (explica los ~20 fps de P02). Ningún modo llega a 88.2 con ventana en ninguna cámara: por el plan, hallazgo para la meta de optimizar el tracker y el autor elige con la tabla. Fracción con pose con K nominal (84°): 640×480 47–68 %, mayores 0–7 % con 4 markers (por confirmar con los intrínsecos reales).
- **Opciones:** (a) Recomendada: 1280×960 MJPG (más píxeles por marker; la velocidad la sube la optimización). (b) 640×480. (c) 960×720. (d) 1920×1200 (tracking sin medir).
- **Respuesta del autor:** 1280×960 MJPG (a), en las dos cámaras.
- **Fecha:** 2026-10-22

## P17 · El lado medido de la casilla del tablero (Fase 4, paso 0)

- **Contexto:** tablero impreso en 3D (9×6 casillas, 25 mm nominal, negras engrosadas 0.4 mm por lado; fotos en `Claude outputs/tablero/`). Calibrador digital de 0.1 mm, puesto en cero. Se mide siempre de orilla de arriba de un negro a orilla de arriba de otro negro (misma orilla: el engrosamiento se cancela). Un primer juego con tramos mezclados (2, 4 y 6 casillas; 24.75–25.18 mm por casilla) se descartó; las medidas de orilla de arriba a orilla de abajo (149.8 mm en 6 casillas del eje corto) incluyen el engrosamiento y no se usan.
- **Medidas:** eje largo, 6 casillas: 149.1, 149.1, 149.1, 149.1, 149.4 mm → media 149.16 / 6 = **24.86 mm**. Eje corto, 4 casillas: tres medidas «cerca de 99.6» (valor aproximado, dicho por el autor) → ~24.90 mm. Diferencia entre ejes ~0.04 mm por casilla (~0.16 %), muy por debajo del criterio de escala (≤ 1.0 mm por 100 mm); la comprobación de escala del paso 4 lo mide en la imagen.
- **Respuesta del autor:** se calibra con `--square-mm 24.86 --medidas-mm 149.1,149.1,149.1,149.1,149.4 --casillas-por-medida 6` (decisión de la dirección con las medidas del autor).
- **Fecha:** 2026-10-22

## P18 · La calibración desde el panel, como la de la sesión en vivo (Fase 4, paso 6)

- **Contexto:** la calibración de la cámara 1 por línea de comandos (`Claude outputs/fases/002/fase-4-en-vivo.md`) le gustó al autor: la rejilla que se rellena, el número de vistas, el flujo. El diálogo del panel ya lanza el mismo `calibrar_camara.py`, pero solo pide el lado (no las medidas ni el tramo), usa un solo detector, no pasa reporte ni luz y no tiene la comprobación de escala.
- **Opciones (selección múltiple):** (a) medidas del calibrador + casillas por medida + reporte y luz; (b) los dos detectores sobre las mismas vistas, se queda el de menor RMS de control; (c) botón «Comprobar escala»; (d) apuntar el perfil al .yml al terminar.
- **Respuesta del autor:** las cuatro. Se hacen dentro de la Fase 4, antes de «verifica»; se prueban en vivo con la cámara 2 en la Fase 5 (calibrada desde el panel).
- **Fecha:** 2026-10-22

## P19 · Enfocar el lente desde el panel (Fase 5)

- **Contexto:** en la Fase 3 el lente se enfocó con `medir_modos.py --enfocar` (ventana con el número de nitidez) desde la línea de comandos. El autor quiere hacerlo desde el panel.
- **Opciones:** (a) Recomendada: un botón «Enfocar lente» con su receta, por encargo corto al cerrar la Fase 5, en su commit; (b) en la Fase 6; (c) al BACKLOG.
- **Respuesta del autor:** (a), al cerrar la Fase 5.
- **Fecha:** 2026-10-23

## P20 · Con qué se juzga la escala (Fase 5)

- **Contexto:** escala de la cámara 2 desde el panel (`escala_gs2.json`, 0,80,0,80,0,80): pasos −0.003, −1.224, −1.121, −0.378, +0.020 mm; fallan dos de cinco. El segundo «0» quedó 1.24 mm del primero (los otros «0» a 0.55 mm entre sí y los «80» a < 0.6 mm): los dos pasos que fallan son los que tocan esa posición. Con la media de las posiciones repetidas (los tres «0» contra los tres «80»): 79.63 mm, error −0.37 mm (−0.46 %); en la cámara 1 (`escala_gs1_topes.json`), +0.27 mm. El criterio por paso mide sobre todo la colocación a mano (±0.6 mm), no la escala de la cámara.
- **Opciones:** (a) Recomendada: el criterio pasa a la distancia entre las medias de las posiciones repetidas (|error| ≤ 1.0 mm por 100 mm); los pasos sueltos quedan como información y para ver la repetibilidad; (b) repetir con el criterio por paso; (c) las dos.
- **Respuesta del autor:** (a). Se recalcula sin cámara con los JSON de las dos cámaras.
- **Fecha:** 2026-10-23

## P21 · La ventana «Calibración de cámara» del panel, simplificada (Fase 5)

- **Contexto:** los diálogos de calibración y escala de P18 tienen 11–12 campos y al autor le resultan confusos; casi todos son fijos (tablero, esquinas, rutas, detector, vistas, luz, autocierre).
- **Opciones:** (a) Recomendada: tres pasos sin campos (1 Enfocar lente, 2 Calibrar con tablero, 3 Comprobar escala con regla), con el tablero y su lado guardados y «Cambiar medidas…», el último resultado de cada paso a la vista, y en la escala solo recorrido e idas y vueltas; (b) lo mismo con un «Avanzado…» que despliega los campos de hoy.
- **Respuesta del autor:** (a), sin «Avanzado».
- **Fecha:** 2026-10-23

## P22 · El temblor de la Fase 6 no cumple: qué se hace (Fase 6)

- **Contexto:** cámara 1 con Slicer (cadena bien: los dos transforms aparecen y se mueven, salida limpia, 18944 libre). Dodecaedro quieto a ~40 cm: sd z 4.88 mm (todo el tramo quieto) y 3.75 (últimas 60) frente a 1.38 de P02; girado para ver 4–6 markers, 9.7–10.2 mm. La pose salta según el juego de markers: con 3,4,7,8 z 411.7 mm; +12, 422.6; +11+12, 435.5 (quieto). Con juego fijo de 4 markers sd z 1.5–4 mm. Causa probable en el tracker o la geometría (cómo combina markers de lado, caras 11 y 12), no en la calibración de la cámara. FPS 13.8–15.2 con `verbose` y `Tee-Object`.
- **Opciones:** (a) Recomendada: correr la cámara 2 y la prueba del panel, cerrar la Fase 6 con el criterio NO cumplido y el hallazgo como entrada de prioridad alta, la primera de la meta siguiente (optimizar el tracker); (b) investigar ahora; (c) cámara 2 primero y decidir.
- **Respuesta del autor:** (a).
- **Fecha:** 2026-10-23
- **Texto de «Volver a medir el tablero» (elegido por el autor, 2026-10-23, tras probar la ventana en vivo):** «Solo hace falta si imprimes un tablero nuevo. El programa necesita saber cuánto mide cada cuadro de verdad (la impresora nunca es exacta). 1. Abre el calibrador sobre una columna del tablero. 2. Una punta en el borde de ARRIBA de un cuadro negro. 3. La otra punta en el borde de ARRIBA de otro cuadro negro, más abajo. Cuenta cuántos cuadros avanzaste. 4. Anota lo que marca. Repítelo 5 veces en otras columnas. Ejemplo: 6 cuadros → 149.1 mm»; campos «Cuadros que avanzaste:» y «Lo que marcó (5 veces):»; debajo, en negrita, «Cada cuadro mide: 24.86 mm»; botones Guardar y Cancelar.
