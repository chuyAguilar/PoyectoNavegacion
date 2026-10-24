"""Replay sin camara de la estimacion de pose del tracker (meta 001, fase 1).

Corre `tracker.estimar_pose_rigid_body` sobre un dataset grabado (las tablas de
`captura_calibracion.py`) con la misma regla de `tracker.main()` (menos de
`rigid_bodies_quality.min_markers` markers del rigid body -> sin pose) y compara
la pose por frame contra una referencia guardada. No cubre el filtro 1-Euro ni
el cuaternion de `main()`: estan dentro del lazo (BACKLOG).

pytest no recoge este archivo (no empieza por `test_`). Como CLI, desde
`codigo\\` con el venv y todos los argumentos explicitos:

    python tests\\replay_util.py recortar --input iter4\\data\\captura_ba.npz \\
        --paso 6 --output tests\\data\\replay_v2_femto.npz
    python tests\\replay_util.py referencia --dataset tests\\data\\replay_v2_femto.npz \\
        --config iter4\\tracker_config.yaml \\
        --output tests\\data\\replay_v2_femto_referencia.npz

La referencia no se regenera sola: si existe, `referencia` aborta salvo con
`--sobrescribir`, y el cambio queda visible en `git diff`.

Marker0 (meta 003, fase 1): las grabaciones de `tracker.py --record`
(`iter4/pose_log.py`). `run_marker0_replay` repite la pose de los markers
sueltos y el 1-Euro con los tiempos grabados; `compare_marker0` la compara
envio a envio; `compare_detection` detecta otra vez sobre los PNG guardados.

    python tests\\replay_util.py copy-frames --dataset tests\\data\\marker0_gs1.npz ^
        --frames-dir "..\\Claude outputs\\grabaciones\\003\\gs1_frames" --count 3 ^
        --output-dir tests\\data\\marker0_gs1_frames
    python tests\\replay_util.py reference-marker0 --dataset tests\\data\\marker0_gs1.npz ^
        --config iter4\\tracker_config_gs1.yaml ^
        --output tests\\data\\marker0_gs1_reference.npz

`reference-marker0` imprime tambien el replay frente a lo enviado en vivo y lo
guarda en el `.json`; aborta si la referencia existe salvo con `--overwrite`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

CODIGO_DIR = Path(__file__).resolve().parents[1]
ITER4_DIR = CODIGO_DIR / "iter4"
if str(ITER4_DIR) not in sys.path:
    sys.path.insert(0, str(ITER4_DIR))

import cv2  # noqa: E402
import tracker  # noqa: E402

TABLAS = ("timestamps", "frame_offsets", "marker_ids", "corners_2d", "K", "dist")


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _rel(ruta: Path) -> str:
    """Ruta relativa a codigo/ (con /) si cae dentro; si no, el nombre."""
    p = Path(ruta).resolve()
    try:
        return p.relative_to(CODIGO_DIR).as_posix()
    except ValueError:
        return p.name


def cargar_dataset(ruta: Path) -> tuple[list[dict[int, np.ndarray]], np.ndarray,
                                        np.ndarray, np.ndarray]:
    """Lee solo las tablas, sin pickle. Devuelve (detecciones por frame,
    timestamps, K, dist); cada frame es {tag_id: corners (4, 2) float32}."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el dataset: {ruta}")
    with np.load(ruta, allow_pickle=False) as d:
        faltan = [k for k in TABLAS if k not in d.files]
        if faltan:
            raise ValueError(f"{ruta.name}: faltan las tablas {faltan}")
        ts = d["timestamps"]
        off = d["frame_offsets"]
        ids = d["marker_ids"]
        corners = d["corners_2d"]
        K = d["K"]
        dist = d["dist"]
    if (len(off) != len(ts) + 1 or int(off[0]) != 0
            or int(off[-1]) != len(ids) or len(ids) != len(corners)
            or np.any(np.diff(off) < 0)):
        raise ValueError(f"{ruta.name}: frame_offsets incoherente con las tablas")
    if corners.shape[1:] != (4, 2):
        raise ValueError(f"{ruta.name}: corners_2d con forma {corners.shape}")
    frames = []
    for i in range(len(ts)):
        a, b = int(off[i]), int(off[i + 1])
        frames.append({int(ids[j]): corners[j] for j in range(a, b)})
    return frames, ts, K, dist


def recortar_dataset(entrada: Path, salida: Path, paso: int) -> dict:
    """Toma uno de cada `paso` frames y guarda solo las tablas (sin depth, sin
    `frames_data` pickle, sin `metadata_json`), mas la procedencia del recorte."""
    entrada, salida = Path(entrada), Path(salida)
    if paso < 1:
        raise ValueError(f"paso tiene que ser >= 1 (llego {paso})")
    if salida.suffix != ".npz":
        raise ValueError(f"La salida tiene que terminar en .npz: {salida}")
    if salida.exists():
        raise FileExistsError(f"La salida ya existe, no se pisa: {salida}")
    frames, ts, K, dist = cargar_dataset(entrada)
    sel = list(range(0, len(frames), paso))
    offsets = [0]
    ids, corners = [], []
    for i in sel:
        for mid, c in frames[i].items():
            ids.append(mid)
            corners.append(c)
        offsets.append(len(ids))
    salida.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        salida,
        timestamps=ts[sel].astype(np.float64),
        frame_offsets=np.asarray(offsets, dtype=np.int32),
        marker_ids=np.asarray(ids, dtype=np.int32),
        corners_2d=np.asarray(corners, dtype=np.float32).reshape(-1, 4, 2),
        K=K, dist=dist,
        recorte_origen=np.asarray(_rel(entrada)),
        recorte_origen_sha256=np.asarray(sha256(entrada)),
        recorte_paso=np.asarray(paso, dtype=np.int32),
    )
    return {
        "frames_entrada": len(frames), "frames_salida": len(sel),
        "detecciones_salida": len(ids), "paso": paso,
        "bytes_entrada": entrada.stat().st_size, "bytes_salida": salida.stat().st_size,
        "sha256_entrada": sha256(entrada), "sha256_salida": sha256(salida),
    }


def ruta_geometria(config: Path) -> Path:
    """La geometria del unico rigid body del config, resuelta como el tracker."""
    cfg = tracker.cargar_config(str(config))
    rbs = cfg.get("rigid_bodies") or []
    if len(rbs) != 1:
        raise ValueError(f"{Path(config).name}: el replay espera 1 rigid body, hay {len(rbs)}")
    ruta = Path(rbs[0].get("geometry_file") or "")
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la geometria del config: {ruta}")
    return ruta.resolve()


def min_markers(config: Path) -> int:
    cfg = tracker.cargar_config(str(config))
    return int(cfg.get("rigid_bodies_quality", {}).get("min_markers", 1))


def correr_replay(dataset: Path, config: Path) -> dict[str, np.ndarray]:
    """Pose por frame con la regla de `tracker.main()`. Devuelve `valida` (N,),
    `M` (N, 4, 4; NaN donde no hay pose) y `n_usados` (N,)."""
    geom = tracker.cargar_rigid_body(str(ruta_geometria(config)))
    if not geom:
        raise ValueError(f"La geometria de {Path(config).name} no tiene marcadores")
    minimo = min_markers(config)
    frames, _, K, dist = cargar_dataset(dataset)
    n = len(frames)
    valida = np.zeros(n, dtype=bool)
    M = np.full((n, 4, 4), np.nan, dtype=np.float64)
    n_usados = np.zeros(n, dtype=np.int32)
    for i, det in enumerate(frames):
        det_rb = {mid: c for mid, c in det.items() if mid in geom}
        if not det_rb or len(det_rb) < minimo:
            continue
        resultado = tracker.estimar_pose_rigid_body(det_rb, geom, K, dist)
        if resultado is None:
            continue
        rvec, tvec, usados = resultado
        valida[i] = True
        M[i] = tracker.rvec_tvec_a_matriz(rvec, tvec)
        n_usados[i] = usados
    return {"valida": valida, "M": M, "n_usados": n_usados}


def _angulo_grados(R_ref: np.ndarray, R: np.ndarray) -> float:
    """Angulo de R_ref.T @ R por atan2 (estable cerca de 0, a diferencia de arccos)."""
    D = R_ref.T @ R
    s = 0.5 * np.linalg.norm([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]])
    c = 0.5 * (np.trace(D) - 1.0)
    return float(np.degrees(np.arctan2(s, c)))


def comparar(obtenido: dict, referencia: dict) -> dict[str, float]:
    va = np.asarray(obtenido["valida"], dtype=bool)
    vb = np.asarray(referencia["valida"], dtype=bool)
    if va.shape != vb.shape:
        raise ValueError(f"Distinto numero de frames: {va.shape} frente a {vb.shape}")
    ambos = va & vb
    dif_n, dif_t, dif_r = 0.0, 0.0, 0.0
    for i in np.flatnonzero(ambos):
        Ma, Mb = obtenido["M"][i], referencia["M"][i]
        dif_n = max(dif_n, abs(float(obtenido["n_usados"][i]) - float(referencia["n_usados"][i])))
        dif_t = max(dif_t, float(np.linalg.norm(Ma[:3, 3] - Mb[:3, 3])))
        dif_r = max(dif_r, _angulo_grados(Mb[:3, :3], Ma[:3, :3]))
    return {
        "frames": float(va.size),
        "frames_comparados": float(ambos.sum()),
        "frames_validez_distinta": float(np.sum(va != vb)),
        "max_dif_n_usados": dif_n,
        "max_dif_traslacion_mm": dif_t,
        "max_dif_rotacion_grados": dif_r,
    }


def cargar_referencia(ruta: Path) -> dict[str, np.ndarray]:
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la referencia del replay: {ruta}")
    with np.load(ruta, allow_pickle=False) as d:
        return {k: d[k] for k in ("valida", "M", "n_usados")}


def guardar_referencia(obtenido: dict, ruta: Path, procedencia: dict,
                       sobrescribir: bool) -> None:
    ruta = Path(ruta)
    if ruta.suffix != ".npz":
        raise ValueError(f"La referencia tiene que terminar en .npz: {ruta}")
    ruta_json = ruta.with_suffix(".json")
    existentes = [p for p in (ruta, ruta_json) if p.exists()]
    if existentes and not sobrescribir:
        raise SystemExit(
            "[replay] La referencia ya existe y no se regenera sola: "
            f"{[p.name for p in existentes]}. Para regenerarla a proposito, "
            "--sobrescribir (y el cambio queda en git diff).")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    np.savez(ruta, valida=obtenido["valida"], M=obtenido["M"],
             n_usados=obtenido["n_usados"])
    with open(ruta_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(procedencia, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _procedencia(dataset: Path, config: Path, obtenido: dict) -> dict:
    geom = ruta_geometria(config)
    valida = obtenido["valida"]
    proc = {
        "dataset": _rel(dataset), "dataset_sha256": sha256(dataset),
        "config": _rel(config), "geometria": _rel(geom),
        "geometria_sha256": sha256(geom), "min_markers": min_markers(config),
        "frames": int(valida.size), "frames_con_pose": int(valida.sum()),
        "mediana_n_usados": (float(np.median(obtenido["n_usados"][valida]))
                             if valida.any() else None),
        "opencv": cv2.__version__, "numpy": np.__version__,
        "python": platform.python_version(),
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with np.load(dataset, allow_pickle=False) as d:
        if "recorte_origen" in d.files:
            proc["recorte"] = {"origen": str(d["recorte_origen"]),
                               "origen_sha256": str(d["recorte_origen_sha256"]),
                               "paso": int(d["recorte_paso"])}
    return proc


# ============================================================================
# Replay de Marker0 (meta 003, fase 1): las grabaciones de `tracker.py --record`
# ============================================================================

MARKER0_KEYS = ("sent_frame", "M")


def _marker_list(cfg: dict) -> dict[int, dict]:
    return {int(m["id"]): m for m in cfg["markers"].get("list", []) or []}


def marker0_params(profile: Path) -> dict:
    """Lo del perfil que decide la pose de los markers sueltos: tamanos,
    nombres, diccionario, detector y filtro. Se guarda con la referencia y la
    prueba lo compara (el perfil cambia de sitio y pierde el dodecaedro en
    esta meta; estos parametros no)."""
    cfg = tracker.cargar_config(str(profile))
    return {
        "markers": [{"id": int(m["id"]), "name": str(m["name"]), "size_mm": float(m["size_mm"])}
                    for m in cfg["markers"].get("list", []) or []],
        "dictionary": str(cfg["markers"]["dictionary"]),
        "detector": dict(cfg["markers"].get("detector", {}) or {}),
        "filtering": {"enabled": bool(cfg["filtering"]["enabled"]),
                      "min_cutoff": float(cfg["filtering"]["min_cutoff"]),
                      "beta": float(cfg["filtering"]["beta"])},
    }


def _rigid_body_ids(cfg: dict) -> set[int]:
    ids: set[int] = set()
    for rb in cfg.get("rigid_bodies", []) or []:
        ruta = Path(rb.get("geometry_file") or "")
        if not ruta.is_file():
            raise FileNotFoundError(f"No existe la geometria del perfil: {ruta}")
        ids.update(tracker.cargar_rigid_body(str(ruta)).keys())
    return ids


def run_marker0_replay(dataset: Path, profile: Path, name: str = "Marker0") -> dict:
    """Repite sobre una grabacion lo que `tracker.main()` hace con los markers
    sueltos: por cada deteccion, en el orden del detector, IPPE_SQUARE con
    z > 0 (`estimar_pose_individual`), el 1-Euro de la posicion con el tiempo
    grabado y `rvec_tvec_a_matriz`. Devuelve los envios de `name` en orden:
    `sent_frame` (S,) y `M` (S, 4, 4)."""
    from pose_log import load_recording
    rec = load_recording(dataset)
    cfg = tracker.cargar_config(str(profile))
    markers = _marker_list(cfg)
    rb_ids = _rigid_body_ids(cfg)
    if not any(m["name"] == name for m in markers.values()):
        raise ValueError(f"{Path(profile).name}: no hay un marker '{name}' en markers.list")
    filtros: dict[int, list] = {}
    if cfg["filtering"]["enabled"]:
        for mid in markers:
            filtros[mid] = [tracker.OneEuroFilter(cfg["filtering"]["min_cutoff"],
                                                  cfg["filtering"]["beta"]) for _ in range(3)]
    K, dist = rec["K"], rec["dist"]
    off, ids, corners, ts = (rec["frame_offsets"], rec["marker_ids"],
                             rec["corners_2d"], rec["timestamps"])
    sent_frame: list[int] = []
    sent_M: list[np.ndarray] = []
    for i in range(len(ts)):
        t_now = float(ts[i])
        for j in range(int(off[i]), int(off[i + 1])):
            mid = int(ids[j])
            if mid in rb_ids or mid not in markers:
                continue
            info = markers[mid]
            pose = tracker.estimar_pose_individual(corners[j].reshape(1, 4, 2),
                                                   info["size_mm"], K, dist)
            if pose is None:
                continue
            rvec, tvec = pose
            if mid in filtros:
                f = filtros[mid]
                tvec_flat = tvec.flatten()
                tvec = np.array([f[k].filtrar(tvec_flat[k], t_now) for k in range(3)]).reshape(3, 1)
            if info["name"] == name:
                sent_frame.append(i)
                sent_M.append(tracker.rvec_tvec_a_matriz(rvec, tvec))
    return {"sent_frame": np.asarray(sent_frame, dtype=np.int32),
            "M": (np.asarray(sent_M, dtype=np.float64).reshape(-1, 4, 4)
                  if sent_M else np.zeros((0, 4, 4)))}


def recorded_marker0(dataset: Path, name: str = "Marker0") -> dict:
    """Los envios de `name` que hizo el tracker en vivo, con la forma de
    `run_marker0_replay`."""
    from pose_log import load_recording
    rec = load_recording(dataset)
    sel = rec["sent_name"] == name
    return {"sent_frame": rec["sent_frame"][sel].astype(np.int32),
            "M": rec["sent_M"][sel].astype(np.float64)}


def compare_marker0(result: dict, reference: dict) -> dict:
    """Envio a envio: mismo numero, mismos frames, y la diferencia maxima de
    traslacion (mm) y de rotacion (grados)."""
    fa, fb = np.asarray(result["sent_frame"]), np.asarray(reference["sent_frame"])
    out = {"sends": float(len(fa)), "sends_reference": float(len(fb)),
           "frames_differ": float("nan"), "max_diff_translation_mm": float("nan"),
           "max_diff_rotation_deg": float("nan")}
    if len(fa) != len(fb):
        return out
    out["frames_differ"] = float(np.sum(fa != fb))
    dif_t, dif_r = 0.0, 0.0
    for Ma, Mb in zip(result["M"], reference["M"]):
        dif_t = max(dif_t, float(np.linalg.norm(Ma[:3, 3] - Mb[:3, 3])))
        dif_r = max(dif_r, _angulo_grados(Mb[:3, :3], Ma[:3, :3]))
    out["max_diff_translation_mm"] = dif_t
    out["max_diff_rotation_deg"] = dif_r
    return out


def build_detector(profile: Path):
    """El detector de `tracker.main()` con el diccionario y los parametros del perfil."""
    cfg = tracker.cargar_config(str(profile))
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    tracker.aplicar_detector_params(params, cfg["markers"].get("detector", {}) or {})
    return cv2.aruco.ArucoDetector(tracker.obtener_diccionario(cfg["markers"]["dictionary"]),
                                   params)


def compare_detection(dataset: Path, frames_dir: Path, profile: Path) -> dict:
    """Detecta de nuevo sobre los PNG guardados (`frame_NNNNN.png`), aplica la
    lista blanca grabada y compara ids y esquinas con las del frame grabado."""
    from pose_log import load_recording
    rec = load_recording(dataset)
    whitelist = set(int(x) for x in rec["metadata"]["whitelist"])
    detector = build_detector(profile)
    off = rec["frame_offsets"]
    pngs = sorted(Path(frames_dir).glob("frame_*.png"))
    if not pngs:
        raise FileNotFoundError(f"No hay frame_*.png en {frames_dir}")
    out = {"frames": float(len(pngs)), "frames_ids_differ": 0.0, "detections": 0.0,
           "max_diff_px": 0.0}
    for png in pngs:
        i = int(png.stem.split("_")[1])
        gray = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
        if gray is None or gray.ndim != 2:
            raise ValueError(f"{png.name}: no es una imagen en gris")
        corners, ids, _ = detector.detectMarkers(gray)
        got = []
        if ids is not None:
            got = [(int(m), np.asarray(corners[k], np.float32).reshape(4, 2))
                   for k, m in enumerate(ids.flatten().tolist()) if int(m) in whitelist]
        a, b = int(off[i]), int(off[i + 1])
        want = [(int(rec["marker_ids"][j]), rec["corners_2d"][j]) for j in range(a, b)]
        if [g[0] for g in got] != [w[0] for w in want]:
            out["frames_ids_differ"] += 1
            continue
        out["detections"] += len(got)
        for (_, cg), (_, cw) in zip(got, want):
            out["max_diff_px"] = max(out["max_diff_px"],
                                     float(np.max(np.abs(cg.astype(np.float64) - cw))))
    return out


def save_marker0_reference(result: dict, path: Path, provenance: dict,
                           overwrite: bool) -> None:
    path = Path(path)
    if path.suffix != ".npz":
        raise ValueError(f"La referencia tiene que terminar en .npz: {path}")
    path_json = path.with_suffix(".json")
    existentes = [p for p in (path, path_json) if p.exists()]
    if existentes and not overwrite:
        raise SystemExit(
            "[replay] La referencia ya existe y no se regenera sola: "
            f"{[p.name for p in existentes]}. Para regenerarla a proposito, "
            "--overwrite (y el cambio queda en git diff).")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, sent_frame=result["sent_frame"], M=result["M"])
    with open(path_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(provenance, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def load_marker0_reference(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe la referencia del replay de Marker0: {path}")
    with np.load(path, allow_pickle=False) as d:
        return {k: d[k] for k in MARKER0_KEYS}


def copy_frames(dataset: Path, frames_dir: Path, count: int, output_dir: Path,
                name: str = "Marker0") -> list[str]:
    """Copia `count` PNG guardados, repartidos a lo largo de la grabacion y
    solo de frames con pose de `name`, recomprimidos sin perdida (PNG nivel 9)
    y comprobados pixel a pixel."""
    from pose_log import load_recording
    rec = load_recording(dataset)
    con_pose = set(int(f) for f in rec["sent_frame"][rec["sent_name"] == name])
    candidatos = [int(f) for f in rec["frames_saved"] if int(f) in con_pose
                  and (Path(frames_dir) / f"frame_{int(f):05d}.png").is_file()]
    if len(candidatos) < count:
        raise ValueError(f"Solo hay {len(candidatos)} frames guardados con {name}; se piden {count}")
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"La carpeta de salida no esta vacia, no se pisa: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    pos = np.linspace(0, len(candidatos) - 1, count + 2)[1:-1].round().astype(int)
    copiados = []
    for p in pos:
        f = candidatos[int(p)]
        src = Path(frames_dir) / f"frame_{f:05d}.png"
        dst = output_dir / src.name
        img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
        if not cv2.imwrite(str(dst), img, [cv2.IMWRITE_PNG_COMPRESSION, 9]):
            raise RuntimeError(f"No se pudo escribir {dst}")
        if not np.array_equal(cv2.imread(str(dst), cv2.IMREAD_UNCHANGED), img):
            raise RuntimeError(f"{dst.name}: la copia no es igual pixel a pixel")
        copiados.append(dst.name)
    return copiados


def _marker0_provenance(dataset: Path, profile: Path, result: dict) -> dict:
    from pose_log import load_recording
    rec = load_recording(dataset)
    return {
        "dataset": _rel(dataset), "dataset_sha256": sha256(dataset),
        "profile": _rel(profile), "params": marker0_params(profile),
        "frames": int(len(rec["timestamps"])), "sends": int(len(result["sent_frame"])),
        "recorded_with": {k: rec["metadata"].get(k) for k in
                          ("config_sha256", "calibration_file", "calibration_sha256",
                           "show_window", "frames", "fps_average", "opencv")},
        "opencv": cv2.__version__, "numpy": np.__version__,
        "python": platform.python_version(),
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay sin camara (meta 001; Marker0, meta 003).")
    sub = ap.add_subparsers(dest="orden", required=True)
    r = sub.add_parser("recortar", help="Recorta un dataset grabado.")
    r.add_argument("--input", required=True, type=Path)
    r.add_argument("--paso", required=True, type=int)
    r.add_argument("--output", required=True, type=Path)
    g = sub.add_parser("referencia", help="Genera la referencia del replay.")
    g.add_argument("--dataset", required=True, type=Path)
    g.add_argument("--config", required=True, type=Path)
    g.add_argument("--output", required=True, type=Path)
    g.add_argument("--sobrescribir", action="store_true")
    m = sub.add_parser("reference-marker0",
                       help="Referencia del replay de Marker0 sobre una grabacion de tracker.py --record.")
    m.add_argument("--dataset", required=True, type=Path)
    m.add_argument("--config", required=True, type=Path)
    m.add_argument("--output", required=True, type=Path)
    m.add_argument("--overwrite", action="store_true")
    c = sub.add_parser("copy-frames",
                       help="Copia N frames guardados con Marker0 a tests/data (PNG sin perdida).")
    c.add_argument("--dataset", required=True, type=Path)
    c.add_argument("--frames-dir", required=True, type=Path)
    c.add_argument("--count", required=True, type=int)
    c.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args(argv)

    if args.orden == "recortar":
        info = recortar_dataset(args.input, args.output, args.paso)
        print(json.dumps(info, indent=2))
        return 0
    if args.orden == "copy-frames":
        print(json.dumps(copy_frames(args.dataset, args.frames_dir, args.count,
                                     args.output_dir), indent=2))
        return 0
    if args.orden == "reference-marker0":
        obtenido = run_marker0_replay(args.dataset, args.config)
        en_vivo = compare_marker0(obtenido, recorded_marker0(args.dataset))
        print("[replay] Replay frente a lo enviado en vivo:", json.dumps(en_vivo))
        proc = _marker0_provenance(args.dataset, args.config, obtenido)
        proc["replay_vs_live"] = en_vivo
        save_marker0_reference(obtenido, args.output, proc, args.overwrite)
        print(json.dumps(proc, indent=2, ensure_ascii=False))
        return 0
    obtenido = correr_replay(args.dataset, args.config)
    proc = _procedencia(args.dataset, args.config, obtenido)
    guardar_referencia(obtenido, args.output, proc, args.sobrescribir)
    print(json.dumps(proc, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
