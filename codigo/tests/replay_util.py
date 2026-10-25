"""Replay sin camara de la pose de Marker0 (meta 003, fase 1; en piezas desde la fase 4).

Las grabaciones de `python -m tracker --record` (`diagnostics/pose_log.py`)
traen, por frame, los ids y las esquinas que vio el detector tras la lista
blanca, el tiempo con que se filtro y las matrices que se enviaron.
`run_marker0_replay` pasa esas esquinas por `vision.tracking.MarkerTracker
.process_corners` (IPPE_SQUARE con z > 0, el 1-Euro de la posicion con el
tiempo grabado y la matriz 4x4: el mismo paso por frame que corre el tracker)
y devuelve los envios de Marker0; `compare_marker0` los compara envio a envio
con lo enviado en vivo o con la referencia guardada; `compare_detection`
detecta otra vez (`vision.detection`) sobre los PNG guardados.

El replay del dodecaedro (meta 001: `correr_replay`, `recortar_dataset`,
`test_replay.py` y sus datos) se archivo con su codigo en
codigo/historico/iter4/dodecahedron/ (fase 3); sus funciones salieron de aqui
en la fase 4 con `estimar_pose_rigid_body`.

pytest no recoge este archivo (no empieza por `test_`). Como CLI, desde
`codigo\\` con el venv, como modulo y con todos los argumentos explicitos:

    python -m tests.replay_util copy-frames --dataset tests\\data\\marker0_gs1.npz ^
        --frames-dir "..\\Claude outputs\\grabaciones\\003\\gs1_frames" --count 3 ^
        --output-dir tests\\data\\marker0_gs1_frames
    python -m tests.replay_util reference-marker0 --dataset tests\\data\\marker0_gs1.npz ^
        --config profiles\\tracker_config_gs1.yaml ^
        --output tests\\data\\marker0_gs1_reference.npz

`reference-marker0` imprime tambien el replay frente a lo enviado en vivo y lo
guarda en el `.json`; aborta si la referencia existe salvo con `--overwrite`.
La referencia no se regenera sola, y el cambio queda visible en `git diff`.
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

import cv2

import profiles
from vision.detection import create_detector
from vision.tracking import MarkerTracker

# codigo/ va en sys.path por pytest.ini (pythonpath = .) o por `python -m tests.replay_util`.
CODIGO_DIR = Path(__file__).resolve().parents[1]

MARKER0_KEYS = ("sent_frame", "M")


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


def _angle_deg(R_ref: np.ndarray, R: np.ndarray) -> float:
    """Angulo de R_ref.T @ R por atan2 (estable cerca de 0, a diferencia de arccos)."""
    D = R_ref.T @ R
    s = 0.5 * np.linalg.norm([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]])
    c = 0.5 * (np.trace(D) - 1.0)
    return float(np.degrees(np.arctan2(s, c)))


def marker0_params(profile: Path) -> dict:
    """Lo del perfil que decide la pose de los markers sueltos: tamanos,
    nombres, diccionario, detector y filtro. Se guarda con la referencia y la
    prueba lo compara (el perfil cambia de sitio en esta meta; esto no)."""
    cfg = profiles.load(str(profile))
    return {
        "markers": [{"id": int(m["id"]), "name": str(m["name"]), "size_mm": float(m["size_mm"])}
                    for m in cfg["markers"].get("list", []) or []],
        "dictionary": str(cfg["markers"]["dictionary"]),
        "detector": dict(cfg["markers"].get("detector", {}) or {}),
        "filtering": {"enabled": bool(cfg["filtering"]["enabled"]),
                      "min_cutoff": float(cfg["filtering"]["min_cutoff"]),
                      "beta": float(cfg["filtering"]["beta"])},
    }


def run_marker0_replay(dataset: Path, profile: Path, name: str = "Marker0") -> dict:
    """Repite sobre una grabacion lo que el tracker hace por frame con las
    esquinas ya detectadas: `MarkerTracker.process_corners` con el tiempo
    grabado (pose IPPE_SQUARE con z > 0, 1-Euro de la posicion, matriz 4x4).
    Devuelve los envios de `name` en orden: `sent_frame` (S,) y `M` (S, 4, 4)."""
    from diagnostics.pose_log import load_recording
    rec = load_recording(dataset)
    cfg = profiles.load(str(profile))
    if not any(str(m["name"]) == name for m in cfg["markers"].get("list", []) or []):
        raise ValueError(f"{Path(profile).name}: no hay un marker '{name}' en markers.list")
    tracker = MarkerTracker(cfg["markers"], cfg.get("filtering"))
    K, dist = rec["K"], rec["dist"]
    off, ids, corners, ts = (rec["frame_offsets"], rec["marker_ids"],
                             rec["corners_2d"], rec["timestamps"])
    sent_frame: list[int] = []
    sent_M: list[np.ndarray] = []
    for i in range(len(ts)):
        detections = [(int(ids[j]), corners[j].reshape(1, 4, 2))
                      for j in range(int(off[i]), int(off[i + 1]))]
        for p in tracker.process_corners(detections, float(ts[i]), K, dist):
            if p.name == name:
                sent_frame.append(i)
                sent_M.append(p.matrix)
    return {"sent_frame": np.asarray(sent_frame, dtype=np.int32),
            "M": (np.asarray(sent_M, dtype=np.float64).reshape(-1, 4, 4)
                  if sent_M else np.zeros((0, 4, 4)))}


def recorded_marker0(dataset: Path, name: str = "Marker0") -> dict:
    """Los envios de `name` que hizo el tracker en vivo, con la forma de
    `run_marker0_replay`."""
    from diagnostics.pose_log import load_recording
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
        dif_r = max(dif_r, _angle_deg(Mb[:3, :3], Ma[:3, :3]))
    out["max_diff_translation_mm"] = dif_t
    out["max_diff_rotation_deg"] = dif_r
    return out


def build_detector(profile: Path):
    """El detector del tracker con el diccionario y los parametros del perfil."""
    cfg = profiles.load(str(profile))
    return create_detector(cfg["markers"])


def compare_detection(dataset: Path, frames_dir: Path, profile: Path) -> dict:
    """Detecta de nuevo sobre los PNG guardados (`frame_NNNNN.png`), aplica la
    lista blanca grabada y compara ids y esquinas con las del frame grabado."""
    from diagnostics.pose_log import load_recording
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
    from diagnostics.pose_log import load_recording
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
    from diagnostics.pose_log import load_recording
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
    ap = argparse.ArgumentParser(description="Replay sin camara de Marker0 (meta 003).")
    sub = ap.add_subparsers(dest="orden", required=True)
    m = sub.add_parser("reference-marker0",
                       help="Referencia del replay de Marker0 sobre una grabacion de tracker --record.")
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

    if args.orden == "copy-frames":
        print(json.dumps(copy_frames(args.dataset, args.frames_dir, args.count,
                                     args.output_dir), indent=2))
        return 0
    obtenido = run_marker0_replay(args.dataset, args.config)
    en_vivo = compare_marker0(obtenido, recorded_marker0(args.dataset))
    print("[replay] Replay frente a lo enviado en vivo:", json.dumps(en_vivo))
    proc = _marker0_provenance(args.dataset, args.config, obtenido)
    proc["replay_vs_live"] = en_vivo
    save_marker0_reference(obtenido, args.output, proc, args.overwrite)
    print(json.dumps(proc, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
