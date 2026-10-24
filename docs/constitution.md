# Constitución de PoyectoNavegacion

Lo que no se negocia. No crea reglas: junta las que ya existen, cada una con su fuente. Cambiar un principio exige un ADR. Si un spec, un prompt o un comando choca con este archivo, gana este archivo y se avisa al autor.

Aprobada por el autor el 2026-10-19 (ADR-020).

1. **Cada quien su papel.**
   - **El autor** decide, autoriza cada plan y hace todos los commits y los push: títulos cortos, en español, sin coautor.
   - **Los agentes** hacen solo lo de su papel y dejan los cambios en el árbol de trabajo. Ninguno ejecuta `git commit` ni `git push`.

   *Fuente: ADR-020; `.claude/settings.json`.*

2. **Plan antes de código, fase por fase.**
   - Sin un plan autorizado por el autor no se implementa nada.
   - Lo que se deja para después va a `docs/BACKLOG.md` en el momento, no en una revisión posterior.

   *Fuente: ADR-020; `docs/CONTEXT.md` §5.*

3. **Medir antes de decidir.**
   - «Se ve bien» no cierra nada: un número que coincide con lo esperado, sí.
   - Registro paired-point: RMS < 1.5 mm deseable, < 3 mm aceptable, > 5 mm algo está mal y se investiga.
   - Punta: spread entre posturas < 1.0 mm excelente, < 1.5 mm bueno. BA: reproyección en px, validada aparte (el RMSE que reporta el propio BA no es confiable).
   - Diagnóstico antes que fix, una variable a la vez.

   *Fuente: `docs/CONTEXT.md` §1; ADR-003; ADR-010.*

4. **Es un prototipo de investigación, no un dispositivo clínico.** Se prueba sobre phantom impreso. Ningún texto lo llama «listo para cirugía».

   *Fuente: `docs/CONTEXT.md` §1.*

5. **Los datos de paciente no los toca ningún agente.**
   - El DICOM (`herramientas/A/`), el volumen CT (`*.nrrd`) y `documentos/VERONICA/` siguen en el repo por decisión del autor, pero ningún agente los lee, los edita ni los envía a un servicio externo.
   - Por un servidor MCP o una búsqueda solo salen nombres de librería y preguntas de API, nunca rutas ni datos clínicos.

   *Fuente: `docs/CONTEXT.md` §2; ADR-019.*

6. **La cadena tracker → OpenIGTLink → Slicer y su jerarquía no se rompen nunca.**
   - El tracker publica solo `Marker0ToTracker` por OpenIGTLink (TCP 18944, solo transforms). Desde la meta 003 ya no publica `DodecaedroToTracker` (ADR-026).
   - En Slicer, `Marker0ToTracker` llega a la raíz de la escena; lo reciben los scripts versionados en `codigo/slicer/`. El instrumento y su punta, y el registro con el hueso, se rehacen en sus metas (ADR-025), con nombres nuevos y su ADR. Hasta entonces, la jerarquía anterior (`DodecaedroToMarker0`, `StylusTipToDodecaedro`, `BoneToMarker0`) queda como referencia en `documentos/historico/MANUAL_simplificado.md`.
   - Cambiar nombres, puerto o jerarquía exige un ADR y una verificación en vivo con Slicer. Todo lo demás (cámaras, geometrías, calibraciones, GUI, scripts) puede cambiar con su plan.

   *Fuente: `docs/ARCHITECTURE.md` §3.5 y §4; ADR-004; ADR-005; ADR-025; ADR-026; decisiones del autor del 2026-10-19 y del 2026-10-23.*

7. **Fallar fuerte, no en silencio.**
   - Un script valida sus entradas (config, geometría, calibración presente y coherente) y aborta con un mensaje claro antes que dar un resultado plausible pero falso.
   - Los argumentos van siempre explícitos: varios defaults apuntan al stylus viejo.

   *Fuente: `docs/CONTEXT.md` §2 y §4.13–17; ADR-017.*

8. **Una sola fuente por cosa.**
   - `docs/constitution.md`: lo que no se negocia. `CLAUDE.md`: cómo se trabaja. `memory.md`: el estado y el spec activo.
   - `docs/ARCHITECTURE.md`: el qué. `docs/DECISIONS.md`: el porqué (aditivo; un ADR nunca se reescribe). `docs/CONTEXT.md`: las reglas del dominio y el entorno.
   - `docs/BACKLOG.md`: lo que falta. `docs/PRUEBAS.md`: lo que se probó. `docs/history/`: lo hecho, copia literal. `specs/NNN-nombre/`: una meta.

   *Fuente: ADR-020.*

9. **Nada sin tiempo límite, y nada que deje el equipo o el árbol en mal estado.**
   - Toda corrida lleva tope de tiempo; ninguna espera es sin fin.
   - Ni la cámara ni el puerto 18944 quedan tomados (Detener por `'q'`, luego `terminate()`); ni un `.git\index.lock` huérfano (git solo desde PowerShell); ni un archivo truncado (tras editar, `py_compile` y conteo de líneas).

   *Fuente: `docs/CONTEXT.md` §4.1–2; ADR-017.*

10. **Cambiar un principio exige un ADR.** Si algo choca con esta constitución, gana la constitución y se avisa al autor.

    *Fuente: ADR-020.*
