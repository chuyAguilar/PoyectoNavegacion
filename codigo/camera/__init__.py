"""La camara: backend de captura (`backend`), identidad por puerto USB (`uvc`) y ajustes por DSHOW (`controls`).

Meta 003, fase 3 (ADR-027): eran `iter4/camera_backend.py`, `iter4/camaras_uvc.py`
e `iter4/ajustes_camara.py`; solo cambian de sitio y de imports.

Importar el paquete importa antes que nada `camera.uvc`, que apaga la
aceleracion por hardware de MSMF (`docs/CONTEXT.md` §4.18): un punto de entrada
que importe `camera` antes que cv2 abre la camara sin ella.
"""
from camera import uvc  # noqa: F401  (primero: apaga la aceleracion HW de MSMF antes de cargar cv2)
