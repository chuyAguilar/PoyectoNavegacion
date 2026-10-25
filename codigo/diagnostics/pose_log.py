"""Grabacion y resumen de la pose que envia el tracker (meta 003, fase 1).

`PoseLog` guarda, frame a frame, lo que el tracker detecto (ids y esquinas, ya
filtrados por la lista blanca), el tiempo con que filtro la pose y las
matrices que envio por OpenIGTLink, en un `.npz` de tablas sin pickle:

    timestamps (N,) float64        t_now de cada frame (el del 1-Euro)
    frame_offsets (N+1,) int32     detecciones del frame i: [off[i], off[i+1])
    marker_ids (D,) int32          id de cada deteccion, en el orden del detector
    corners_2d (D, 4, 2) float32   esquinas de cada deteccion
    K, dist                        los intrinsecos que uso el tracker
    sent_frame (S,) int32          frame de cada envio, en orden
    sent_name (S,) str             nombre del envio sin "ToTracker" (Marker0, ...)
    sent_M (S, 4, 4) float64       la matriz enviada
    frames_saved (F,) int32        frames guardados como PNG (frame_NNNNN.png)
    frames_every () int32
    metadata_json () str           perfil, argumentos, versiones, tiempos

Las cuatro primeras tablas y K/dist son las del replay de la meta 001, asi
que `tests/replay_util.cargar_dataset` las lee igual.

`summarize` resume una grabacion para la linea base. Como CLI, desde
`codigo\\` con el venv y los argumentos explicitos:

    python -m diagnostics.pose_log --input "<grabacion>.npz" --name Marker0 ^
        --output "<resumen>.json"

`Stopwatch` (meta 003, fase 6 · Donde se va el tiempo por frame) cronometra
el bucle del tracker por etapa (`tracker --timing <json>`): `mark(etapa)`
suma a esa etapa el tiempo desde la marca anterior y `end_frame()` cierra el
frame, con lo no marcado en la etapa `other`. Asi la suma de las etapas de un
frame es exactamente el tiempo entre dos `end_frame` seguidos.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

JUMP_DEG = 5.0
TABLES = ("timestamps", "frame_offsets", "marker_ids", "corners_2d", "K", "dist",
          "sent_frame", "sent_name", "sent_M", "frames_saved", "frames_every",
          "metadata_json")


class PoseLog:
    """Acumula en memoria lo de cada frame y lo escribe al final con `save`.

    Falla al crearse (antes de abrir la camara) si la salida ya existe o la
    carpeta de frames ya tiene PNG: una grabacion no pisa a otra.
    """

    def __init__(self, path: Path, frames_dir: Path | None = None,
                 frames_every: int = 30) -> None:
        self.path = Path(path)
        if self.path.suffix != ".npz":
            raise ValueError(f"La grabacion tiene que terminar en .npz: {self.path}")
        if self.path.exists():
            raise FileExistsError(f"La grabacion ya existe, no se pisa: {self.path}")
        if int(frames_every) < 1:
            raise ValueError(f"frames_every tiene que ser >= 1 (llego {frames_every})")
        self.frames_every = int(frames_every)
        self.frames_dir = Path(frames_dir) if frames_dir is not None else None
        if self.frames_dir is not None:
            self.frames_dir.mkdir(parents=True, exist_ok=True)
            previos = sorted(self.frames_dir.glob("frame_*.png"))
            if previos:
                raise FileExistsError(
                    f"La carpeta de frames ya tiene {len(previos)} PNG, no se mezclan "
                    f"grabaciones: {self.frames_dir}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._t: list[float] = []
        self._offsets: list[int] = [0]
        self._ids: list[int] = []
        self._corners: list[np.ndarray] = []
        self._sent_frame: list[int] = []
        self._sent_name: list[str] = []
        self._sent_M: list[np.ndarray] = []
        self._frames_saved: list[int] = []

    @property
    def n_frames(self) -> int:
        return len(self._t)

    def add(self, t: float, ids: np.ndarray | None, corners: tuple,
            poses: list[tuple[str, np.ndarray]],
            gray: np.ndarray | None) -> None:
        """Un frame: `ids`/`corners` como salen del detector tras la lista
        blanca; `poses`, los envios del frame en orden, (nombre, matriz 4x4);
        `gray`, la imagen en gris que se detecto (se guarda 1 de cada N)."""
        i = len(self._t)
        self._t.append(float(t))
        if ids is not None:
            for k, mid in enumerate(np.asarray(ids).flatten().tolist()):
                self._ids.append(int(mid))
                self._corners.append(np.asarray(corners[k], dtype=np.float32).reshape(4, 2))
        self._offsets.append(len(self._ids))
        for name, M in poses:
            self._sent_frame.append(i)
            self._sent_name.append(str(name))
            self._sent_M.append(np.array(M, dtype=np.float64).reshape(4, 4))
        if self.frames_dir is not None and gray is not None and i % self.frames_every == 0:
            ruta = self.frames_dir / f"frame_{i:05d}.png"
            if not cv2.imwrite(str(ruta), gray):
                raise RuntimeError(f"No se pudo escribir el frame {ruta}")
            self._frames_saved.append(i)

    def save(self, K: np.ndarray, dist: np.ndarray, metadata: dict) -> Path:
        corners = (np.asarray(self._corners, dtype=np.float32).reshape(-1, 4, 2)
                   if self._corners else np.zeros((0, 4, 2), dtype=np.float32))
        sent_M = (np.asarray(self._sent_M, dtype=np.float64).reshape(-1, 4, 4)
                  if self._sent_M else np.zeros((0, 4, 4), dtype=np.float64))
        np.savez(
            self.path,
            timestamps=np.asarray(self._t, dtype=np.float64),
            frame_offsets=np.asarray(self._offsets, dtype=np.int32),
            marker_ids=np.asarray(self._ids, dtype=np.int32),
            corners_2d=corners,
            K=np.asarray(K), dist=np.asarray(dist),
            sent_frame=np.asarray(self._sent_frame, dtype=np.int32),
            sent_name=np.asarray(self._sent_name, dtype="U64"),
            sent_M=sent_M,
            frames_saved=np.asarray(self._frames_saved, dtype=np.int32),
            frames_every=np.asarray(self.frames_every, dtype=np.int32),
            metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False,
                                                sort_keys=True, default=str)),
        )
        return self.path


def load_recording(path: Path) -> dict:
    """Lee una grabacion de `PoseLog` sin pickle y comprueba sus tablas."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe la grabacion: {path}")
    with np.load(path, allow_pickle=False) as d:
        faltan = [k for k in TABLES if k not in d.files]
        if faltan:
            raise ValueError(f"{path.name}: faltan las tablas {faltan}")
        rec = {k: d[k] for k in TABLES}
    off = rec["frame_offsets"]
    n = len(rec["timestamps"])
    if (len(off) != n + 1 or int(off[0]) != 0 or int(off[-1]) != len(rec["marker_ids"])
            or len(rec["marker_ids"]) != len(rec["corners_2d"]) or np.any(np.diff(off) < 0)):
        raise ValueError(f"{path.name}: frame_offsets incoherente con las tablas")
    s = len(rec["sent_frame"])
    if len(rec["sent_name"]) != s or len(rec["sent_M"]) != s:
        raise ValueError(f"{path.name}: las tablas de envios no tienen el mismo largo")
    if s and (np.any(rec["sent_frame"] < 0) or np.any(rec["sent_frame"] >= n)
              or np.any(np.diff(rec["sent_frame"]) < 0)):
        raise ValueError(f"{path.name}: sent_frame fuera de rango o desordenado")
    rec["metadata"] = json.loads(str(rec["metadata_json"]))
    return rec


def _angle_deg(Ra: np.ndarray, Rb: np.ndarray) -> float:
    """Angulo de Ra.T @ Rb por atan2 (estable cerca de 0)."""
    D = Ra.T @ Rb
    s = 0.5 * np.linalg.norm([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]])
    c = 0.5 * (np.trace(D) - 1.0)
    return float(np.degrees(np.arctan2(s, c)))


def summarize(npz_path: Path, name: str = "Marker0") -> dict:
    """Resumen de una grabacion para la linea base: frames, fps, fraccion con
    pose, sd x/y/z (mm, muestral), rango z, sd de la orientacion (RMS del
    angulo a la rotacion media, grados) y saltos > 5 grados entre frames
    seguidos con pose. La pose de un frame es el ultimo envio de `name` en
    ese frame (lo ultimo que recibio Slicer)."""
    rec = load_recording(npz_path)
    t = rec["timestamps"]
    n = len(t)
    if n < 2:
        raise ValueError(f"{Path(npz_path).name}: {n} frames, no hay que resumir")
    meta = rec["metadata"]
    sel = np.flatnonzero(rec["sent_name"] == name)
    M = np.full((n, 4, 4), np.nan)
    envios_por_frame = np.zeros(n, dtype=np.int32)
    for j in sel:
        f = int(rec["sent_frame"][j])
        M[f] = rec["sent_M"][j]
        envios_por_frame[f] += 1
    valid = envios_por_frame > 0
    span = float(t[-1] - t[0])
    out: dict = {
        "file": Path(npz_path).name, "name": name, "frames": int(n),
        "duration_s": span, "fps": (n - 1) / span if span > 0 else float("nan"),
        "fps_tracker": meta.get("fps_average"),
        "show_window": meta.get("show_window"),
        "frames_with_pose": int(valid.sum()),
        "fraction_with_pose": float(valid.mean()),
        "frames_with_two_sends": int(np.sum(envios_por_frame > 1)),
    }
    if valid.sum() < 2:
        out["error"] = f"menos de 2 frames con pose de {name}"
        return out
    T = M[valid][:, :3, 3]
    R = M[valid][:, :3, :3]
    rots = Rotation.from_matrix(R)
    mean_rot = rots.mean()
    dev = np.degrees((mean_rot.inv() * rots).magnitude())
    idx = np.flatnonzero(valid)
    seguidos = np.flatnonzero(np.diff(idx) == 1)
    paso_ang = np.array([_angle_deg(R[k], R[k + 1]) for k in seguidos])
    paso_t = np.array([float(np.linalg.norm(T[k + 1] - T[k])) for k in seguidos])
    out.update({
        "mean_x_mm": float(T[:, 0].mean()), "mean_y_mm": float(T[:, 1].mean()),
        "mean_z_mm": float(T[:, 2].mean()),
        "sd_x_mm": float(T[:, 0].std(ddof=1)), "sd_y_mm": float(T[:, 1].std(ddof=1)),
        "sd_z_mm": float(T[:, 2].std(ddof=1)),
        "range_z_mm": float(T[:, 2].max() - T[:, 2].min()),
        "sd_orientation_deg": float(np.sqrt(np.mean(dev ** 2))),
        "max_orientation_dev_deg": float(dev.max()),
        "consecutive_pairs": int(len(seguidos)),
        "jumps_over_5deg": int(np.sum(paso_ang > JUMP_DEG)) if len(paso_ang) else 0,
        "max_step_deg": float(paso_ang.max()) if len(paso_ang) else 0.0,
        "max_step_mm": float(paso_t.max()) if len(paso_t) else 0.0,
    })
    return out


# ---------------------------------------------------------------------------
# Tiempo por etapa del bucle (meta 003, fase 6)
# ---------------------------------------------------------------------------

OTHER_STAGE = "other"


def timing_stats(ms: Sequence[float]) -> dict:
    """Media, p50 y p95 (ms) de una serie de tiempos en ms; None si esta vacia."""
    a = np.asarray(ms, dtype=np.float64)
    if a.size == 0:
        return {"mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {"mean_ms": float(a.mean()), "p50_ms": float(np.percentile(a, 50)),
            "p95_ms": float(np.percentile(a, 95)), "max_ms": float(a.max())}


class Stopwatch:
    """Cronometro por etapa, frame a frame, con un reloj monotono (perf_counter).

    El tiempo cuenta desde que se crea (o desde el ultimo `end_frame`). Una
    etapa que no se marco en un frame cuenta 0 ms en ese frame. El reloj no es
    el del tracker (`time.time`), asi que activarlo no cambia los tiempos con
    que se filtra la pose.
    """

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._order: list[str] = []
        self._frames: list[dict[str, float]] = []
        self._frame_ms: list[float] = []
        self._current: dict[str, float] = {}
        self._t_last = self._t_frame = clock()

    @property
    def n_frames(self) -> int:
        return len(self._frame_ms)

    def mark(self, stage: str) -> None:
        """Suma a `stage` el tiempo desde la marca anterior (o desde el inicio del frame)."""
        now = self._clock()
        if stage not in self._order:
            self._order.append(stage)
        self._current[stage] = self._current.get(stage, 0.0) + (now - self._t_last) * 1000.0
        self._t_last = now

    def end_frame(self) -> None:
        """Cierra el frame: lo no marcado va a `other`; el frame dura desde el `end_frame` anterior."""
        self.mark(OTHER_STAGE)
        now = self._t_last
        self._frame_ms.append((now - self._t_frame) * 1000.0)
        self._frames.append(self._current)
        self._current = {}
        self._t_frame = now

    def stages(self) -> list[str]:
        """Las etapas en el orden en que aparecieron, con `other` al final."""
        return [s for s in self._order if s != OTHER_STAGE] + (
            [OTHER_STAGE] if OTHER_STAGE in self._order else [])

    def per_frame(self) -> dict[str, list[float]]:
        """Los ms de cada etapa y del frame, frame a frame (0.0 si no se marco)."""
        out = {s: [f.get(s, 0.0) for f in self._frames] for s in self.stages()}
        out["frame"] = list(self._frame_ms)
        return out

    def summary(self) -> dict:
        """Media, p50 y p95 por etapa y del frame; la suma de las medias y su cociente con el frame."""
        pf = self.per_frame()
        stages = {s: timing_stats(pf[s]) for s in self.stages()}
        frame = timing_stats(self._frame_ms)
        sum_means = float(sum(v["mean_ms"] for v in stages.values())) if self._frame_ms else None
        return {
            "frames": self.n_frames,
            "stages": stages,
            "frame": frame,
            "sum_of_stage_means_ms": sum_means,
            "sum_over_frame_mean": (sum_means / frame["mean_ms"]
                                    if sum_means is not None and frame["mean_ms"] else None),
            "fps_from_frame_mean": (1000.0 / frame["mean_ms"] if frame["mean_ms"] else None),
        }

    def save(self, path: Path, metadata: dict) -> Path:
        """Escribe el resumen, los ms frame a frame y `metadata` en un JSON (no pisa uno que exista)."""
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"La salida de tiempos ya existe, no se pisa: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"summary": self.summary(), "metadata": metadata,
                "per_frame_ms": {k: [round(x, 4) for x in v] for k, v in self.per_frame().items()}}
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str) + "\n",
                        encoding="utf-8")
        return path


def format_timing(summary: dict) -> str:
    """La tabla de `Stopwatch.summary()` en texto: una linea por etapa, mas el frame y la suma."""
    lineas = [f"{'etapa':<12} {'media':>8} {'p50':>8} {'p95':>8}  (ms, {summary['frames']} frames)"]

    def fila(nombre: str, st: dict) -> str:
        if st["mean_ms"] is None:
            return f"{nombre:<12} {'-':>8} {'-':>8} {'-':>8}"
        return f"{nombre:<12} {st['mean_ms']:8.3f} {st['p50_ms']:8.3f} {st['p95_ms']:8.3f}"
    for nombre, st in summary["stages"].items():
        lineas.append(fila(nombre, st))
    lineas.append(fila("FRAME", summary["frame"]))
    if summary["sum_of_stage_means_ms"] is not None:
        lineas.append(f"suma de medias {summary['sum_of_stage_means_ms']:.3f} ms; "
                      f"{summary['fps_from_frame_mean']:.1f} fps por la media del frame")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resumen de una grabacion del tracker (meta 003).")
    ap.add_argument("--input", required=True, type=Path, help="Grabacion .npz de tracker.py --record.")
    ap.add_argument("--name", required=True, help="Nombre del envio, sin ToTracker (Marker0).")
    ap.add_argument("--output", type=Path, default=None, help="JSON de salida (no se pisa).")
    args = ap.parse_args(argv)
    res = summarize(args.input, args.name)
    texto = json.dumps(res, indent=2, ensure_ascii=False)
    print(texto)
    if args.output is not None:
        if args.output.exists():
            raise SystemExit(f"[pose_log] La salida ya existe, no se pisa: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(texto + "\n", encoding="utf-8")
    return 0 if "error" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
