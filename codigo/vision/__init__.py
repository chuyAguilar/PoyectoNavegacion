"""La vision del tracker: deteccion ArUco (`detection`), pose de un marker (`pose`),
filtro 1-Euro (`filtering`) y el paso por frame (`tracking`).

Meta 003, fase 4 · El tracker en piezas (ADR-027): lo que `tracker.py` hacia en
un solo archivo, separado en piezas con pruebas sin camara. Los cuerpos de las
funciones son los de antes (solo cambian de sitio y de nombre, en ingles); el
replay de Marker0 (`tests/test_replay_marker0.py`) comprueba que la pose que se
envia es la misma, 0.0 mm / 0.0 grados.

Este paquete no abre la camara ni toca pyigtl: solo numpy y cv2.
"""
