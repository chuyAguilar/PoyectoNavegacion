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
