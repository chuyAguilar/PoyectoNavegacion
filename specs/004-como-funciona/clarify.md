# Aclaraciones — Meta 004 · Cómo funciona el tracker

Las preguntas del plan y las respuestas del autor, en orden. Una pregunta por bloque; lo respondido no se borra. `/planear` añade las preguntas; el autor, o el agente por encargo suyo, escribe la respuesta y la fecha.

## P1 · ¿En qué formato va el gráfico?

- **Opciones:** (a) Mermaid dentro del Markdown: sin dependencia, GitHub y VS Code lo dibujan, se diffea y la prueba lo lee como texto (recomendada). (b) SVG o PNG generado por un script: una dependencia de dibujo nueva y un binario más en git; se lee mejor si el gráfico crece mucho. (c) Los dos: el doble de mantenimiento.
- **Respuesta del autor:** (c) los dos: el Mermaid como fuente y una imagen exportada.
- **Fecha:** 2026-10-26

## P2 · ¿Dónde vive la explicación?

- **Opciones:** (a) `docs/COMO_FUNCIONA.md` nuevo con el gráfico, la explicación, el ejemplo y el glosario, y una línea en `ARCHITECTURE.md` §2 que remite; no copia contratos ni opciones, los cita por sección (recomendada). (b) El gráfico en `ARCHITECTURE.md` y la explicación aparte: dos sitios que mirar. (c) Todo como sección nueva de `ARCHITECTURE.md`, que ya mide 39 KB y se lee por secciones.
- **Respuesta del autor:** (c) todo como sección nueva de `ARCHITECTURE.md`.
- **Fecha:** 2026-10-26

## P3 · ¿`COMO_FUNCIONA.md` entra en la lista de fuentes del método?

- **Opciones:** (a) Se añade a `CLAUDE.md` §1 paso 3 (se consulta por su índice) y se registra con ADR-032, sin tocar la constitución (recomendada). (b) Además se añade al principio 8 de la constitución: cambiar un principio exige el ADR (principio 10). (c) No se nombra en ninguno: queda como documento para el autor.
- **Respuesta del autor:** no aplica: con P2 = c no hay documento nuevo; `ARCHITECTURE.md` ya es fuente del método (`CLAUDE.md` §1). La dirección lo decide así; sin ADR-032 por esto.
- **Fecha:** 2026-10-26

## P4 · ¿Cuánta matemática lleva la explicación?

- **Opciones:** (a) Intuición primero, una fórmula por paso como mucho (la proyección pinhole), cada paso con los números del ejemplo y dos comprobaciones a mano: la distancia por el tamaño en px y la escala de B55 (recomendada). (b) Solo intuición, sin fórmulas. (c) Con las derivaciones: proyección completa con distorsión, PnP e IPPE, Rodrigues.
- **Respuesta del autor:** (a) intuición primero, una fórmula por paso y las dos comprobaciones a mano.
- **Fecha:** 2026-10-26

## P5 · ¿Qué frame se usa en el ejemplo?

- **Opciones:** (a) `marker0_gs1_frames/frame_00480.png` en el documento, y los 3 frames de gs1 y los 3 de gs2 en la prueba (recomendada; sin cámara). (b) Uno de cada cámara en el documento: más largo, mismas lecciones. (c) Una captura nueva, p. ej. con Marker0 inclinado: exige una sesión en vivo con cámara y una grabación nueva en `tests/data/`.
- **Respuesta del autor:** (a) `frame_00480` de gs1 en el documento y los 6 frames en la prueba.
- **Fecha:** 2026-10-26

## P6 · ¿Se versiona la figura del ejemplo (el frame con esquinas y ejes)?

- **Opciones:** (a) Sí, en `docs/img/004/`, recortada alrededor del marker y de menos de 200 KB: se ve en GitHub sin correr nada (recomendada). (b) No: el script la genera en `Claude outputs/` y el documento da el comando; va al BACKLOG como baja. (c) Sin figura.
- **Respuesta del autor:** (a) versionadas en `docs/img/004/`, menos de 200 KB en total; también la imagen exportada del gráfico (P1 = c).
- **Fecha:** 2026-10-26

## P7 · ¿Cuatro fases, con esos pesos y en ese orden?

- **Opciones:** (a) 1 el mapa (ligera), 2 el ejemplo (pesada), 3 la explicación y el glosario (ligera), 4 la lectura con el autor y el cierre (ligera), en ese orden, enseñando cada una antes de la siguiente (recomendada). (b) Juntar la 1 y la 2: menos commits, más que revisar de golpe. (c) La explicación antes que el ejemplo: el texto se escribiría sin los números reales.
- **Respuesta del autor:** (a) cuatro fases, en ese orden.
- **Fecha:** 2026-10-26

## P8 · ¿Con qué se exporta la imagen del mapa?

- **Opciones:** (a) `@mermaid-js/mermaid-cli` (`mmdc`) a versión fija por `npx`, con el Edge ya instalado y `PUPPETEER_SKIP_DOWNLOAD=1` (no baja navegador); nada queda dentro del repo; si Edge no le sirve, la fase 1 se para y se pregunta (recomendada). (b) Como (a), pero si Edge falla se deja que puppeteer baje su Chromium a la caché del usuario (cientos de MB, fuera del repo) sin volver a preguntar; va al BACKLOG como baja. (c) Sin Node: el autor exporta a mano desde un visor de Mermaid y la prueba solo vigila el sha; sin dependencia, pero no se repite igual y depende de una persona. En (a) y (b) se propone ADR-032 (herramienta de documentación fuera de `requirements.txt`).
- **Respuesta del autor:** (a) con Edge (`mermaid-cli@12.0.0` por `npx`). Se registra en ADR-032.
- **Fecha:** 2026-10-26. Ese mismo día el autor autorizó el plan (versión 2) en el chat.

## P9 · La imagen del mapa no se lee (fase 1, tras la primera exportación)

- **Datos:** con `--size 1400` el PNG salió de ~570 × 1400 px (83 KB): el mapa es alto y estrecho y el texto queda ilegible.
- **Respuesta del autor:** la imagen pasa a **SVG** (vectorial, nítida a cualquier zoom) en vez de PNG, con el mismo tope de 200 KB en `docs/img/004/` (cambia P6 de `.png` a `.svg`); el mapa se dibuja **más ancho que alto** (los cuatro grupos de izquierda a derecha, cada uno de arriba abajo); el alcance sigue siendo **solo la cadena del tracking**, con una línea al pie que nombra lo que queda fuera (los demás botones del panel, otros diagnósticos, `historico/`).
- **Fecha:** 2026-10-26

## P10 · «Probar cámara» repite lo que ya hace «Verificar IDs y colocar la cámara»

- **Datos:** el autor (2026-10-26): «probar cámara también es un paso extra… si uso primero ese y luego el otro, el segundo parece que no hace nada». «Probar cámara» no abre ventana: solo pone en verde el semáforo «Cámara»; «Verificar IDs» abre la cámara pero no lo pone.
- **Opciones:** (a) BACKLOG media, tras la meta 004; (b) fase extra dentro de la meta 004; (c) BACKLOG baja.
- **Respuesta del autor:** (b) fase extra: la 2b.
- **Fecha:** 2026-10-26

## P11 · «Comprobar escala con regla» va lento y se congela al pulsar ESPACIO

- **Datos:** el autor lo vio en vivo el 2026-10-26; la causa leída en el código está en `plan.md`, fase 2c.
- **Opciones:** (a) fase extra en la meta 004, tras la 2b; (b) BACKLOG media; (c) junto con la 2b.
- **Respuesta del autor:** (a) fase extra: la 2c.
- **Fecha:** 2026-10-26
