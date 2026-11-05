"""La fusion de las dos camaras (meta 006 · Grafo de factores optico-inercial).

Fase 1 · Verlo, parte A · Los numeros sin gtsam: un experimento fuera de linea sobre
la grabacion de los dos trackers de la Jetson (`tracker --record`, un `.npz` por camara
y segmento) que mide, en el PC y con `.venv`, lo que la fusion daria: los extrinsecos
de gs2 respecto a gs1 por Marker0 (`extrinsics`), si las dos camaras coinciden, cuanto
baja el jitter al fusionar por instante (`geometry.fuse_poses` y `geometry.joint_pnp`),
que pasa al tapar una camara (`metrics`) y el desfase entre las dos (`pairing`). El
informe HTML lo escribe `report`; la orden es `python -m fusion.experiment`.

Este paquete no importa gtsam al cargarse: solo `fusion.graph` (parte B) lo hara, y
vive en su propio entorno (P25). Nada de aqui lo importa la cadena del tracker
(principio 6): `tracker.py`, `camera/`, `vision/` y `transport/` no cambian.
"""
