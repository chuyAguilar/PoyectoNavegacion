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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay sin camara (meta 001).")
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
    args = ap.parse_args(argv)

    if args.orden == "recortar":
        info = recortar_dataset(args.input, args.output, args.paso)
        print(json.dumps(info, indent=2))
        return 0
    obtenido = correr_replay(args.dataset, args.config)
    proc = _procedencia(args.dataset, args.config, obtenido)
    guardar_referencia(obtenido, args.output, proc, args.sobrescribir)
    print(json.dumps(proc, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
