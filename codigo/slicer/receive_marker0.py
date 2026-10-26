# -*- coding: utf-8 -*-
"""receive_marker0.py — recibe `Marker0ToTracker` en 3D Slicer y mide su frecuencia.

Se corre DENTRO de la consola Python de 3D Slicer (5.x + SlicerOpenIGTLink),
no con el venv del proyecto. Lo que hace (ADR-026, meta 003):

1. Busca un conector OpenIGTLink cliente a HOST:PORT; si no hay, lo crea y lo
   activa. Slicer tiene que estar conectado ANTES de arrancar el tracker
   (`pyigtl` bloquea; CONTEXT.md §4.5), asi que esto se corre primero.
2. Espera a que aparezca el nodo `Marker0ToTracker` (llega cuando la camara ve
   Marker0).
3. Cuenta sus `TransformModifiedEvent` durante SECONDS segundos y escribe la
   frecuencia (Hz), la ultima posicion y si existe un nodo `DodecaedroToTracker`
   en la escena (no deberia: la cadena publica solo Marker0). Desde la fase 8b
   (meta 003) guarda tambien el `time.monotonic()` de cada evento y escribe una
   segunda linea con los intervalos entre modificaciones (p50, p95 y max en ms):
   si el p50 ronda los 15-16 ms, Slicer recibe al ritmo de las rafagas del
   hilo de envio de pyigtl (tic de Windows), no al de los frames.

Nada bloquea el hilo de Slicer: las esperas van por `qt.QTimer`, porque los
mensajes OpenIGTLink solo llegan mientras el bucle de eventos corre.

Uso, en la consola Python de Slicer (ruta explicita, principio 7):

    exec(open(r"C:\\Dev\\OrtoMeta\\PoyectoNavegacion\\codigo\\slicer\\receive_marker0.py", encoding="utf-8").read())
    run()            # 10 s por defecto
    run(seconds=30)  # otra duracion
    run(seconds=20, name="RateProbeToTracker")   # otro nodo: el del banco diagnostics.igtl_rate (fase 8b)

El resultado tambien queda en `LAST_REPORT` (dict) para copiarlo al reporte.
"""

import time

import qt
import slicer
import vtk

HOST = "localhost"
PORT = 18944
SECONDS = 10.0
NAME = "Marker0ToTracker"
LEGACY_NAME = "DodecaedroToTracker"       # no debe aparecer (ADR-026)
WAIT_NODE_TIMEOUT_S = 120.0               # tope de la espera del nodo (principio 9)
POLL_MS = 200

TAG = "[receive_marker0]"
LAST_REPORT = {}


def _log(msg):
    print(f"{TAG} {msg}")


def _connector_class():
    cls = getattr(slicer, "vtkMRMLIGTLConnectorNode", None)
    if cls is None:
        raise RuntimeError("SlicerOpenIGTLink no esta instalado: falta vtkMRMLIGTLConnectorNode "
                           "(Extensions Manager -> SlicerOpenIGTLink).")
    return cls


def state_name(connector):
    cls = _connector_class()
    names = {getattr(cls, "StateOff", 0): "OFF",
             getattr(cls, "StateWaitConnection", 1): "WAIT",
             getattr(cls, "StateConnected", 2): "CONNECTED"}
    return names.get(connector.GetState(), f"state={connector.GetState()}")


def find_connector(host=HOST, port=PORT):
    """El conector cliente a host:port que ya exista en la escena, o None."""
    cls = _connector_class()
    type_client = getattr(cls, "TypeClient", 2)
    for node in slicer.util.getNodesByClass("vtkMRMLIGTLConnectorNode"):
        if (node.GetType() == type_client and node.GetServerHostname() == host
                and int(node.GetServerPort()) == int(port)):
            return node
    return None


def ensure_connector(host=HOST, port=PORT):
    """Reutiliza el conector cliente a host:port o lo crea; lo deja activo."""
    cls = _connector_class()
    node = find_connector(host, port)
    if node is None:
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLIGTLConnectorNode", "TrackerClient")
        node.SetTypeClient(host, int(port))
        _log(f"conector creado: {node.GetName()} -> {host}:{port}")
    else:
        _log(f"conector existente: {node.GetName()} -> {host}:{port} ({state_name(node)})")
    if node.GetState() == getattr(cls, "StateOff", 0):
        node.Start()
        _log(f"conector activado ({state_name(node)}); arranca el tracker cuando quieras")
    return node


def legacy_present():
    """True si hay un nodo `DodecaedroToTracker` en la escena (no deberia)."""
    return slicer.mrmlScene.GetFirstNodeByName(LEGACY_NAME) is not None


def _position(node):
    m = vtk.vtkMatrix4x4()
    node.GetMatrixTransformToWorld(m)
    return [round(m.GetElement(i, 3), 2) for i in range(3)]


def _percentile(sorted_values, q):
    """Percentil q (0-100) de una lista ya ordenada, por interpolacion lineal (sin numpy)."""
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def interval_stats(times):
    """p50, p95 y max (ms) de los intervalos entre marcas `times` (s, monotonic); None si hay < 2."""
    if len(times) < 2:
        return {"interval_ms_p50": None, "interval_ms_p95": None, "interval_ms_max": None}
    iv = sorted((b - a) * 1000.0 for a, b in zip(times, times[1:]))
    return {"interval_ms_p50": round(_percentile(iv, 50), 2),
            "interval_ms_p95": round(_percentile(iv, 95), 2),
            "interval_ms_max": round(iv[-1], 2)}


def measure(node, seconds=SECONDS, done=None):
    """Cuenta los TransformModifiedEvent de `node` durante `seconds` y reporta.

    Guarda el instante (`time.monotonic()`) de cada evento para dar los intervalos
    entre modificaciones (fase 8b): la primera linea del reporte no cambia; la
    segunda trae p50, p95 y max en ms."""
    count = [0]
    stamps = []
    t0 = time.monotonic()

    def on_modified(_caller=None, _event=None):
        count[0] += 1
        stamps.append(time.monotonic())

    tag = node.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, on_modified)
    _log(f"midiendo {node.GetName()} durante {seconds:g} s...")

    def finish():
        node.RemoveObserver(tag)
        dt = time.monotonic() - t0
        hz = count[0] / dt if dt > 0 else 0.0
        connector = find_connector()
        report = {
            "node": node.GetName(),
            "seconds": round(dt, 2),
            "updates": count[0],
            "hz": round(hz, 1),
            "last_position_mm": _position(node),
            "connector_state": state_name(connector) if connector else "sin conector",
            "legacy_present": legacy_present(),
        }
        report.update(interval_stats(stamps))
        LAST_REPORT.clear()
        LAST_REPORT.update(report)
        _log(f"{report['node']}: {report['updates']} actualizaciones en {report['seconds']} s = "
             f"{report['hz']} Hz; ultima posicion (mm) {report['last_position_mm']}; "
             f"conector {report['connector_state']}")
        _log(f"intervalos entre actualizaciones (ms): p50 {report['interval_ms_p50']} "
             f"p95 {report['interval_ms_p95']} max {report['interval_ms_max']} "
             f"(tic de Windows 15.625; un frame a 90 fps 11.1)")
        if report["legacy_present"]:
            _log(f"ATENCION: existe un nodo {LEGACY_NAME} en la escena (ADR-026: no deberia enviarse). "
                 "Si la escena es nueva, el tracker lo sigue publicando.")
        else:
            _log(f"{LEGACY_NAME}: no existe en la escena (correcto, ADR-026)")
        if done:
            done(report)

    qt.QTimer.singleShot(int(seconds * 1000), finish)


def wait_for_node(name=NAME, timeout_s=WAIT_NODE_TIMEOUT_S, then=None):
    """Espera (sin bloquear) a que exista el transform `name`; luego llama `then(node)`."""
    deadline = time.monotonic() + timeout_s

    def poll():
        node = slicer.mrmlScene.GetFirstNodeByName(name)
        if node is not None and node.IsA("vtkMRMLTransformNode"):
            _log(f"nodo {name} presente")
            if then:
                then(node)
            return
        if time.monotonic() > deadline:
            connector = find_connector()
            _log(f"TOPE: {name} no aparecio en {timeout_s:g} s (conector "
                 f"{state_name(connector) if connector else 'sin conector'}). "
                 "¿Esta corriendo el tracker y ve Marker0?")
            LAST_REPORT.clear()
            LAST_REPORT.update({"node": name, "error": "timeout"})
            return
        qt.QTimer.singleShot(POLL_MS, poll)

    _log(f"esperando el nodo {name} (tope {timeout_s:g} s)...")
    poll()


def run(seconds=SECONDS, host=HOST, port=PORT, name=NAME):
    """Conector listo -> espera el nodo `name` (Marker0ToTracker) -> mide `seconds` s -> reporte.

    `name` (fase 8b) sirve para medir otro transform, p. ej. `RateProbeToTracker`,
    el del banco `diagnostics.igtl_rate bench --external`."""
    ensure_connector(host, port)
    wait_for_node(name, WAIT_NODE_TIMEOUT_S, lambda node: measure(node, seconds))


_log("cargado. Llama run() (10 s), run(seconds=30) o run(seconds=20, name=\"RateProbeToTracker\").")
