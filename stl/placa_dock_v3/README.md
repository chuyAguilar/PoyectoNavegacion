# Placa dock v3 — calibracion por template completo (2026-06-13)

Calibracion estilo CAScination/Navident: el stylus IMPRESO (stl/stylus_impreso,
mango de 150 mm) se ENCAJA en la cuna y queda con la pose completamente
definida por geometria. Cero manos, cero tecnica.

## Piezas
- `placa_dock_v3_blanco.stl` + `placa_dock_v3_celdas_negras.stl`: imprimir
  juntas (multiparte AMS, blanco/negro mate), PLANA, sin soporte, relleno >=30%.
- Marker: **ID 2** @ 60 mm (en relieve, como la v2). Muesca TL arriba-izq.

## Geometria del dock (frame del marker ID 2, CAD nominal)
- Apice del cono de la punta: (-50.0, -60.0, +20.0)
- **CENTRO DE LA ESFERA r1 (p_dock): (-48.718, -60.0, +20.598)**
- Eje del stylus: (0.9063, 0, 0.4226) — elevado 25 grados de la placa.
- El dodecaedro queda flotando en (87, -60, 84), mas alla del borde derecho,
  sin ocluir el marker.
- Al imprimir: medir ancho de placa (nominal 150.0) y lado del marker
  (nominal 60.0) con caliper; actualizar escala y --plate-mm como con la v2.

## Protocolo
1. Encajar el stylus: esfera en el cono (punta cuesta abajo) + eje en la V.
   Asienta por gravedad. NO se toca mas.
2. `python iter4\calibrar_tip_divot.py --divot DOCK --plate-id 2`
3. Apoyar el conjunto en una orientacion frente a la camara -> ESPACIO.
4. Reorientar EL CONJUNTO ENTERO (otra inclinacion/azimut) -> ESPACIO.
   Repetir 4-6 orientaciones. q para resolver.
   (La pose relativa stylus-placa no cambia: cada orientacion da una
   estimacion independiente y el spread sigue siendo el control de calidad.)

## Por que
La punta roscada del stylus viejo no define un punto (sesiones divot:
92.0 vs 96.8 mm, spread 3-6 mm). El dock + esfera r1 hace el contacto
deterministico y elimina el factor humano por completo.
