"""Los dos `.npz` de un segmento de la grabacion, como pistas por camara (meta 006, fase 1).

Cada tracker de la Jetson grabo con `--record` un `.npz` de `diagnostics.pose_log.PoseLog`
(`<segmento>_<camara>.npz`; un intento repetido lleva `_r2`, `_r3`). `load_segment` lee
los de un segmento y rehace, frame a frame, la pose cruda de Marker0 desde las esquinas
grabadas con IPPE_SQUARE (las dos soluciones, `ippe_solutions`), sin el 1-Euro; la pose
enviada (`sent_M`, con el filtro) queda aparte en `T_sent`. `check_segment` comprueba lo
que fija el plan antes de usar un segmento: el ancla de reloj de los dos procesos, el
solape, la fraccion con pose, el sha256 de la calibracion frente a `data/` y que la
rotacion rehecha coincida con la enviada (la orientacion no la filtra el 1-Euro).

`cut_segment` recorta un segmento (sin frames) para la suite: `tests/data/fusion_gs1_gs2/`.
Como CLI, desde `codigo\\` con el venv y los argumentos explicitos:

    python -m fusion.dataset recortar --datos <carpeta> --segmento S1_reposo ^
        --desde-s 20 --hasta-s 28 --salida tests\\data\\fusion_gs1_gs2

Context7 (2026-11-05): OpenCV `/opencv/opencv`, `solvePnPGeneric(obj, img, K, dist,
flags=SOLVEPNP_IPPE_SQUARE)` devuelve `(n, rvecs, tvecs, errores)` con todas las
soluciones (IPPE_SQUARE da dos); la primera es la que elige `solvePnP` (comprobado sobre
S1: diferencia 0.0). Instalado: OpenCV 4.11.0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from diagnostics.pose_log import TABLES, load_recording
from fusion.geometry import angle_deg
from vision.pose import build_object_points, rvec_tvec_to_matrix

CAMERAS = ("gs1", "gs2")
MARKER_NAME = "Marker0"
ANCHOR_TOL_MS = 1.0
OVERLAP_MARGIN_S = 10.0
POSE_MIN_FRACTION = 0.90
OCCLUDED_FRACTION = (0.60, 0.95)
ROTATION_TOL_DEG = 1e-3     # el plan decia 1e-6; la grabacion es de ARM (Jetson) y el PC x86: 3e-6 medido (P22)
_ATTEMPT = re.compile(r"_r(\d+)$")


@dataclass
class CameraTrack:
    """Lo de una camara en un segmento, frame a frame (N frames del bucle)."""
    name: str
    t: np.ndarray                   # (N,) s, perf_counter de la Jetson
    T_raw: np.ndarray               # (N, 4, 4) T_cam<-marker de IPPE (1a solucion, z > 0); NaN sin pose
    T_alt: np.ndarray               # (N, 4, 4) la otra solucion de IPPE con z > 0; NaN si no la hay
    corners: np.ndarray             # (N, 4, 2) px; NaN sin deteccion (o con mas de una del id)
    reproj_px: np.ndarray           # (N,) error RMS de reproyeccion de la 1a solucion; NaN sin pose
    reproj_alt_px: np.ndarray       # (N,) el de la otra solucion
    T_sent: np.ndarray              # (N, 4, 4) lo enviado (con 1-Euro); NaN si ese frame no envio
    K: np.ndarray
    dist: np.ndarray
    size_mm: float
    meta: dict = field(default_factory=dict)
    file: str = ""
    excluded: dict = field(default_factory=dict)

    @property
    def valid(self) -> np.ndarray:
        """(N,) bool: frames con pose cruda."""
        return np.isfinite(self.T_raw[:, 3, 3]) if len(self.T_raw) else np.zeros(0, bool)

    @property
    def detected(self) -> np.ndarray:
        return np.isfinite(self.corners[:, 0, 0]) if len(self.corners) else np.zeros(0, bool)

    @property
    def positions(self) -> np.ndarray:
        """(N, 3) mm, NaN sin pose."""
        return self.T_raw[:, :3, 3]

    @property
    def span_s(self) -> float:
        return float(self.t[-1] - self.t[0]) if len(self.t) > 1 else 0.0

    @property
    def period_s(self) -> float:
        """La mediana del intervalo entre frames."""
        return float(np.median(np.diff(self.t))) if len(self.t) > 1 else float("nan")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def ippe_solutions(corners, size_mm: float, K, dist) -> list[tuple[np.ndarray, float]]:
    """Las soluciones de IPPE_SQUARE para las 4 esquinas, en el orden de OpenCV (la primera
    es la de `solvePnP`, la del tracker), cada una como `(T_cam<-marker 4x4, error px)`.
    No filtra z <= 0: eso lo hace quien llama."""
    img = np.asarray(corners, dtype=np.float32).reshape(4, 2)
    n, rvecs, tvecs, errs = cv2.solvePnPGeneric(build_object_points(size_mm), img,
                                                np.asarray(K), np.asarray(dist),
                                                flags=cv2.SOLVEPNP_IPPE_SQUARE)
    out = []
    for k in range(int(n)):
        out.append((rvec_tvec_to_matrix(rvecs[k], tvecs[k]), float(np.asarray(errs).reshape(-1)[k])))
    return out


def _marker(meta: dict, name: str) -> tuple[int, float]:
    for m in meta.get("markers", []) or []:
        if str(m.get("name")) == name:
            return int(m["id"]), float(m["size_mm"])
    raise ValueError(f"la grabacion no tiene un marker llamado {name!r} en metadata.markers")


def build_track(rec: dict, camera: str, name: str = MARKER_NAME, file: str = "") -> CameraTrack:
    """Una `CameraTrack` desde una grabacion ya cargada (`load_recording`)."""
    meta = rec["metadata"]
    mid, size_mm = _marker(meta, name)
    K, dist = np.asarray(rec["K"], dtype=np.float64), np.asarray(rec["dist"], dtype=np.float64)
    t = np.asarray(rec["timestamps"], dtype=np.float64)
    n = len(t)
    off, ids, C = rec["frame_offsets"], rec["marker_ids"], rec["corners_2d"]
    T_raw = np.full((n, 4, 4), np.nan)
    T_alt = np.full((n, 4, 4), np.nan)
    corners = np.full((n, 4, 2), np.nan)
    reproj = np.full(n, np.nan)
    reproj_alt = np.full(n, np.nan)
    T_sent = np.full((n, 4, 4), np.nan)
    for j in np.flatnonzero(rec["sent_name"] == name):
        T_sent[int(rec["sent_frame"][j])] = rec["sent_M"][j]
    excluded = {"sin_deteccion": 0, "varias_detecciones": 0, "pose_invalida": 0,
                "rescatables_por_la_otra_solucion": 0}
    for i in range(n):
        js = [j for j in range(int(off[i]), int(off[i + 1])) if int(ids[j]) == mid]
        if not js:
            excluded["sin_deteccion"] += 1
            continue
        if len(js) > 1:
            excluded["varias_detecciones"] += 1
            continue
        corners[i] = np.asarray(C[js[0]], dtype=np.float64).reshape(4, 2)
        sols = ippe_solutions(corners[i], size_mm, K, dist)
        if not sols or sols[0][0][2, 3] <= 0:
            excluded["pose_invalida"] += 1
            if len(sols) > 1 and sols[1][0][2, 3] > 0:
                excluded["rescatables_por_la_otra_solucion"] += 1
                T_alt[i], reproj_alt[i] = sols[1]
            continue
        T_raw[i], reproj[i] = sols[0]
        if len(sols) > 1 and sols[1][0][2, 3] > 0:
            T_alt[i], reproj_alt[i] = sols[1]
    return CameraTrack(name=camera, t=t, T_raw=T_raw, T_alt=T_alt, corners=corners,
                       reproj_px=reproj, reproj_alt_px=reproj_alt, T_sent=T_sent, K=K, dist=dist,
                       size_mm=size_mm, meta=meta, file=file, excluded=excluded)


def segment_file(folder: Path, segment: str, camera: str, attempt: str | None = None) -> Path:
    """`<segmento>_<camara>.npz`, o el ultimo intento (`_r2`, `_r3`...) si lo hay; con
    `attempt` ("r2"), ese y solo ese."""
    folder = Path(folder)
    if attempt is not None:
        p = folder / f"{segment}_{camera}_{attempt}.npz"
        if not p.is_file():
            raise FileNotFoundError(f"no existe el intento {attempt} de {segment}/{camera}: {p}")
        return p
    base = folder / f"{segment}_{camera}.npz"
    repes = []
    for p in folder.glob(f"{segment}_{camera}_r*.npz"):
        m = _ATTEMPT.search(p.stem)
        if m:
            repes.append((int(m.group(1)), p))
    if repes:
        return max(repes)[1]
    if not base.is_file():
        raise FileNotFoundError(f"no existe la grabacion de {segment}/{camera}: {base}")
    return base


def load_segment(folder: Path, segment: str, cameras: tuple[str, ...] = CAMERAS,
                 attempt: str | None = None, name: str = MARKER_NAME) -> dict[str, CameraTrack]:
    """Las pistas de las camaras de un segmento. Aborta si falta un `.npz`."""
    out = {}
    for cam in cameras:
        p = segment_file(folder, segment, cam, attempt)
        rec = load_recording(p)
        out[cam] = build_track(rec, cam, name, file=p.name)
    return out


def expected_duration(meta: dict) -> float | None:
    """Lo que se pidio grabar: `metadata.recorte.duration_s` si es un recorte; si no, el
    `--duration` de `argv`; None si no esta."""
    rec = meta.get("recorte")
    if isinstance(rec, dict) and rec.get("duration_s") is not None:
        return float(rec["duration_s"])
    argv = list(meta.get("argv") or [])
    for k, a in enumerate(argv):
        if a == "--duration" and k + 1 < len(argv):
            try:
                return float(argv[k + 1])
            except ValueError:
                return None
        if a.startswith("--duration="):
            try:
                return float(a.split("=", 1)[1])
            except ValueError:
                return None
    return None


def check_segment(tracks: dict[str, CameraTrack], intrinsics: dict[str, Path],
                  expected_s: float | None, occluded: str | None = None,
                  rotation_tol_deg: float = ROTATION_TOL_DEG,
                  anchor_tol_ms: float = ANCHOR_TOL_MS) -> dict:
    """La comprobacion del plan. Devuelve los numeros y `ok` con sus `reasons`:
    |ancla gs1 - ancla gs2| <= `anchor_tol_ms` (1 ms por defecto; ancla = t_start - t_loop_start
    de cada `.npz`; en Windows `t_start` es `time.time()`, con pasos de 15.6 ms, y las grabaciones
    del PC piden 20, fase 2); solape >= esperado - 10 s; pose en >= 90 % de los frames (la tapada,
    entre 60 y 95 %); el sha256 de la calibracion de cada `.npz` igual al del `.yml` de `data/`; la
    rotacion rehecha desde las esquinas igual a la enviada (<= `rotation_tol_deg`) y en los mismos
    frames."""
    if not anchor_tol_ms > 0:
        raise ValueError(f"anchor_tol_ms tiene que ser > 0, no {anchor_tol_ms!r}")
    cams = list(tracks)
    reasons: list[str] = []
    out: dict = {"cameras": cams, "expected_s": expected_s}
    anchors = {}
    for c in cams:
        m = tracks[c].meta
        if "t_start" in m and "t_loop_start" in m:
            anchors[c] = float(m["t_start"]) - float(m["t_loop_start"])
    if len(anchors) == len(cams) and len(cams) >= 2:
        vals = list(anchors.values())
        out["anchor_diff_ms"] = float((max(vals) - min(vals)) * 1000.0)
        if out["anchor_diff_ms"] > anchor_tol_ms:
            reasons.append(f"ancla de reloj: {out['anchor_diff_ms']:.3f} ms > {float(anchor_tol_ms)} ms")
    else:
        out["anchor_diff_ms"] = float("nan")
        reasons.append("falta t_start o t_loop_start en metadata")
    t0 = max(tracks[c].t[0] for c in cams)
    t1 = min(tracks[c].t[-1] for c in cams)
    out["overlap_s"] = float(t1 - t0)
    out["span_s"] = {c: tracks[c].span_s for c in cams}
    if expected_s is not None and out["overlap_s"] < expected_s - OVERLAP_MARGIN_S:
        reasons.append(f"solape {out['overlap_s']:.1f} s < {expected_s - OVERLAP_MARGIN_S:.1f} s")
    out["fraction_with_pose"] = {}
    for c in cams:
        fr = float(tracks[c].valid.mean()) if len(tracks[c].t) else 0.0
        out["fraction_with_pose"][c] = fr
        if c == occluded:
            lo, hi = OCCLUDED_FRACTION
            if not (lo <= fr <= hi):
                reasons.append(f"{c} (tapada) con pose en {fr:.1%}, fuera de {lo:.0%}-{hi:.0%}")
        elif fr < POSE_MIN_FRACTION:
            reasons.append(f"{c} con pose en {fr:.1%} < {POSE_MIN_FRACTION:.0%}")
    out["calibration_ok"] = {}
    out["calibration_sha256"] = {}
    for c in cams:
        grabado = str(tracks[c].meta.get("calibration_sha256") or "")
        p = intrinsics.get(c)
        local = sha256_file(Path(p)) if p is not None and Path(p).is_file() else None
        out["calibration_sha256"][c] = {"recorded": grabado, "local": local}
        ok = local is not None and grabado == local
        out["calibration_ok"][c] = bool(ok)
        if not ok:
            reasons.append(f"{c}: la calibracion grabada no es la de data/ ({grabado[:12]} vs {str(local)[:12]})")
    out["rotation_max_diff_deg"] = {}
    out["frames_differ"] = {}
    for c in cams:
        tr = tracks[c]
        sent = np.isfinite(tr.T_sent[:, 3, 3])
        both = sent & tr.valid
        maxang = 0.0
        for i in np.flatnonzero(both):
            maxang = max(maxang, angle_deg(tr.T_sent[i, :3, :3], tr.T_raw[i, :3, :3]))
        out["rotation_max_diff_deg"][c] = maxang
        out["frames_differ"][c] = int(np.sum(sent != tr.valid))
        if maxang > rotation_tol_deg:
            reasons.append(f"{c}: la rotacion rehecha difiere de la enviada {maxang:.2e} grados > {rotation_tol_deg:.0e}")
        if out["frames_differ"][c]:
            reasons.append(f"{c}: {out['frames_differ'][c]} frames con pose en un lado y no en el otro")
    out["excluded"] = {c: dict(tracks[c].excluded) for c in cams}
    out["frames"] = {c: int(len(tracks[c].t)) for c in cams}
    out["fps_loop"] = {c: (float((len(tracks[c].t) - 1) / tracks[c].span_s) if tracks[c].span_s > 0 else float("nan"))
                       for c in cams}
    out["ok"] = not reasons
    out["reasons"] = reasons
    return out


# ---------------------------------------------------------------------------
# Recorte para la suite
# ---------------------------------------------------------------------------

def cut_segment(src_folder: Path, segment: str, dst_folder: Path, from_s: float, to_s: float,
                cameras: tuple[str, ...] = CAMERAS, attempt: str | None = None) -> list[Path]:
    """Recorta `[from_s, to_s)` (desde el primer frame de la camara que arranco mas tarde) de
    cada `.npz` del segmento a `dst_folder/<segmento>_<camara>.npz`, comprimido y sin frames
    guardados; `metadata.recorte` dice de donde sale y cuanto dura. No pisa."""
    if not (to_s > from_s >= 0):
        raise ValueError(f"recorte vacio: desde {from_s} hasta {to_s}")
    dst_folder = Path(dst_folder)
    recs = {c: load_recording(segment_file(src_folder, segment, c, attempt)) for c in cameras}
    t_ref = max(float(recs[c]["timestamps"][0]) for c in cameras)
    salidas = []
    for c in cameras:
        dst = dst_folder / f"{segment}_{c}.npz"
        if dst.exists():
            raise FileExistsError(f"el recorte ya existe, no se pisa: {dst}")
    for c in cameras:
        rec = recs[c]
        t = rec["timestamps"]
        sel = np.flatnonzero((t >= t_ref + from_s) & (t < t_ref + to_s))
        if len(sel) < 2:
            raise ValueError(f"{segment}/{c}: el recorte deja {len(sel)} frames")
        a, b = int(sel[0]), int(sel[-1]) + 1
        off = rec["frame_offsets"]
        da, db = int(off[a]), int(off[b])
        new_off = (off[a:b + 1] - da).astype(np.int32)
        sent_sel = (rec["sent_frame"] >= a) & (rec["sent_frame"] < b)
        meta = dict(rec["metadata"])
        meta["recorte"] = {"source": segment_file(src_folder, segment, c, attempt).name,
                           "frames": [a, b], "from_s": float(from_s), "to_s": float(to_s),
                           "duration_s": float(to_s - from_s)}
        for k in ("frames", "sent", "fps_average"):
            meta.pop(k, None)
        dst = dst_folder / f"{segment}_{c}.npz"
        dst.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            dst,
            timestamps=t[a:b].astype(np.float64),
            frame_offsets=new_off,
            marker_ids=rec["marker_ids"][da:db].astype(np.int32),
            corners_2d=rec["corners_2d"][da:db].astype(np.float32),
            K=rec["K"], dist=rec["dist"],
            sent_frame=(rec["sent_frame"][sent_sel] - a).astype(np.int32),
            sent_name=rec["sent_name"][sent_sel].astype("U64"),
            sent_M=rec["sent_M"][sent_sel].astype(np.float64),
            frames_saved=np.zeros(0, dtype=np.int32),
            frames_every=np.asarray(int(rec["frames_every"]), dtype=np.int32),
            metadata_json=np.asarray(json.dumps(meta, ensure_ascii=False, sort_keys=True, default=str)),
        )
        load_recording(dst)          # comprueba las tablas del recorte
        salidas.append(dst)
    return salidas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recorte de un segmento de la grabacion de las dos camaras (meta 006).")
    sub = ap.add_subparsers(dest="orden", required=True)
    r = sub.add_parser("recortar", help="Recorta [desde, hasta) de los .npz de un segmento, sin frames.")
    r.add_argument("--datos", required=True, type=Path)
    r.add_argument("--segmento", required=True)
    r.add_argument("--desde-s", required=True, type=float)
    r.add_argument("--hasta-s", required=True, type=float)
    r.add_argument("--salida", required=True, type=Path)
    r.add_argument("--intento", default=None, help="r2, r3... (por defecto, el ultimo).")
    args = ap.parse_args(argv)
    try:
        salidas = cut_segment(args.datos, args.segmento, args.salida, args.desde_s, args.hasta_s,
                              attempt=args.intento)
    except (OSError, ValueError) as e:
        print(f"[fusion.dataset] ERROR: {e}", file=sys.stderr)
        return 1
    for p in salidas:
        print(f"[fusion.dataset] {p} ({p.stat().st_size} bytes)")
    return 0


__all__ = ["CameraTrack", "TABLES", "load_segment", "build_track", "check_segment",
           "ippe_solutions", "segment_file", "expected_duration", "cut_segment", "sha256_file"]

if __name__ == "__main__":
    sys.exit(main())
