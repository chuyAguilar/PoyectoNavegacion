"""El envio del tracker: transforms por OpenIGTLink (`igtl`).

Meta 003, fase 4 · El tracker en piezas (ADR-027). Lo unico que publica la
cadena es `Marker0ToTracker` en el puerto 18944 (principio 6, ADR-026); el
video por OpenIGTLink se quito (clarify.md P7: `send_video: true` aborta).
"""
