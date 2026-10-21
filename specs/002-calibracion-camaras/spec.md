# Meta 002 — Calibración de las cámaras global shutter

## Por qué

El autor va a trabajar con cámaras global shutter SVPRO (sensor AR0234, hasta 1920×1200, MJPEG hasta 90 fps, lente M12 de ~83–85°, UVC); hoy son 2. La prueba P02 (`docs/PRUEBAS.md`, cámara 1, commit `6431bc6`, 2026-10-19/20) mostró que el flujo actual funciona con la cámara 1 hasta Slicer, pero:

- la calibración intrínseca quedó «no concluyente»: no se sabe si `codigo/iter4/data/globalshutter.yml` (640×480, 2026-06-29) es de esta unidad, y la imagen se ve pixelada (el autor cree que el lente está desenfocado);
- el tracker da 25.7 fps de media (19.7–30) a 640×480 MJPG, por debajo de los 28–30 esperados, sin causa aislada;
- con el dodecaedro quieto a ~45 cm, el temblor en profundidad es sd 1.38 mm (rango 6.3 mm), frente a 0.14–0.25 mm en x/y;
- los ajustes de la cámara (exposición y demás) los ha movido el autor a mano en las dos cámaras y no están registrados; el código no fija ninguno (`camera_backend.py` no toca exposición, ganancia ni balance);
- nada comprueba que el tamaño real del frame coincide con el del `.yml`.

El autor quiere (2026-10-20): fijar y automatizar los ajustes de cada cámara; elegir la resolución midiendo, no a ojo; y calibrar las dos cámaras, una por una, a esa resolución. Va antes que cualquier otra cosa con estas cámaras: es la base que se mantiene y se mejora.

Material: tablero de ajedrez impreso en 3D por el autor (Bambu A1, multicolor al ras): 9×6 casillas de 25 mm nominales (8×5 esquinas interiores), con borde blanco de 10 mm; antes, una pieza de prueba 2×2 para medir con calibrador. Los STL están fuera de git en `Claude outputs/tablero/`. El script de calibración existe: `codigo/iter4/calibrar_camara.py` (su prueba con cámara está pendiente en B10 · Verificaciones en vivo pendientes del brief-02).

## Qué se construye

1. **Ajustes fijos por cámara.** Lo que la cámara acepte de verdad por el backend que se use (exposición, ganancia, balance de blancos, autoexposición y lo que haya): se declaran en el perfil, se aplican al abrir la cámara, se leen de vuelta y se registran. Primero se mide qué controles acepta cada cámara.
2. **La identificación de cada cámara.** Cómo se sabe cuál de las dos SVPRO es cuál, para que cada una use su perfil y su calibración, sin depender de que el índice no cambie.
3. **Medir resolución × formato.** Por cada cámara: cada resolución y formato que anuncie (al menos MJPG y YUY2), con el tamaño real del frame, los FPS de captura sola y los FPS de tracking (con la detección ArUco del tracker) y los markers del dodecaedro por vista a ~60 cm. Sale una tabla por cámara y una resolución elegida.
4. **Enfocar, fijar y calibrar.** El autor enfoca cada lente a la distancia de trabajo (50–70 cm) y lo fija. Se calibra cada cámara con el tablero impreso, medido con calibrador (el `--square-mm` es el medido, no el nominal), a la resolución elegida. Un `.yml` de intrínsecos por cámara y un perfil por cámara.
5. **La comprobación del tamaño.** Al abrir la cámara, si el frame real no coincide con el `image_width`/`image_height` del `.yml`, se avisa o se para (lo propone el plan).
6. **Comparar contra P02.** Con cada cámara calibrada: temblor del dodecaedro quieto y la cadena hasta Slicer.

## Criterio de cierre

- **Resolución:** la tabla de cada cámara existe con sus números, y la resolución elegida es la mayor que sostiene **≥ 60 fps de tracking** (decisión del autor, 2026-10-20), medidos sobre al menos 30 s con el dodecaedro a ~60 cm. Si ninguna llega a 60 fps de tracking pero la captura sí, la meta no lo fuerza: lo reporta como hallazgo («hay que optimizar el tracker»), y el autor decide la resolución con la tabla.
- **Ajustes:** cada perfil declara sus ajustes; al abrir, se leen de la cámara y coinciden con los declarados (o se reporta cuáles no acepta). Dos aperturas seguidas dan los mismos valores.
- **Tablero:** el tamaño de casilla medido con calibrador (media de al menos 5 medidas sobre varias casillas, en mm con dos decimales) queda escrito en `clarify.md` o en el `.yml`.
- **Calibración:** por cada cámara, error de reproyección RMS ≤ 0.5 px con ≥ 15 vistas variadas (umbral propuesto; el plan lo puede ajustar con razón), a la resolución elegida, y el `.yml` declara esa resolución.
- **Contra P02:** con el dodecaedro quieto a ~45 cm, el temblor en profundidad (sd) baja de 1.38 mm; se reporta el número de cada cámara. La cadena llega a Slicer con los dos transforms. Necesita sesión en vivo con el autor, una por cámara.
- **Escala:** al menos una comprobación de escala independiente de la reproyección (que no la detecta), propuesta por el plan con lo que hay (p.ej. distancia conocida entre dos marcadores o el propio tablero a otra distancia), con su error en mm.
- **No cambió:** la suite y el replay dan lo mismo que la línea base (100 recogidas, 78 pasan, 22 `xfail`; replay 0.0 mm / 0.0°) y `panel.py --selftest` en verde. El perfil Femto (`tracker_config.yaml`) se comporta igual.
- B10 · Verificaciones en vivo pendientes del brief-02: la parte de `calibrar_camara.py` se cierra o se acota.

## Lo que no se toca

- La cadena tracker → OpenIGTLink → Slicer y su jerarquía (principio 6): nombres de transform, puerto 18944, `pyigtl`. Esta meta sí toca `camera_backend.py` y quizá `tracker.py` (ajustes, comprobación de tamaño): el plan dice cómo verifica que la cadena sigue igual (suite, replay y en vivo).
- El contexto Femto (`tracker_config.yaml`): no cambia su comportamiento.
- `globalshutter.yml` no se sobrescribe: los nuevos `.yml` van con su propio nombre; qué pasa con el viejo lo decide el autor.
- La punta, el registro paired-point y la optimización del tracker (si hace falta para llegar a 60 fps, es otra meta).
- Las dos cámaras a la vez en el tracker (estéreo o multicámara): no entra; esta meta deja cada cámara calibrada por separado.
- La Jetson (B23): no entra.
- Datos de paciente (principio 5).

## Preguntas que el plan tiene que contestar

1. **Controles de la cámara:** qué controles expone la SVPRO por MSMF (y por DirectShow, si sirve para fijarlos), cuáles se aplican y se leen de vuelta, y si los que el autor movió a mano (con AMCap) persisten en la cámara o en el driver. Si OpenCV no basta, qué alternativa sin dependencia nueva, o cuál dependencia y por qué.
2. **Identificar cada cámara:** las dos son del mismo modelo; ¿tienen número de serie o ruta de dispositivo distinta que Windows y OpenCV puedan usar? Si no, qué se propone.
3. **La medición:** qué script (nuevo o existente) recorre resolución × formato, con qué tope de tiempo, y cómo separa FPS de captura y de tracking (y la ventana de OpenCV, si cuenta).
4. **El umbral de reproyección** y el número de vistas, con su razón; y la comprobación de escala.
5. **Los archivos:** nombre y lugar de los `.yml` y de los perfiles por cámara; si se versionan.
6. **ADR:** ADR-016 dice que la SVPRO AR0234 era rolling shutter; la ficha y Windows («Global Shutter Camera», PID 0234) dicen global shutter. ¿Hace falta ADR nuevo (ADR-016 no se reescribe)? ¿Y uno para la resolución y los ajustes elegidos?
7. **Las fases:** orden y número, con un commit por fase; propuesta: controles e identificación → medición → calibración por cámara → comparación; qué fases necesitan sesión en vivo y qué hace el autor en cada una.
8. **La luz:** el parpadeo con la caja de luz al mínimo (P02); si la medición fija un nivel y cómo se anota.
