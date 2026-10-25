"""Cuanto cuesta la ventana del tracker, sin camara (meta 003, fase 6).

Cronometra `cv2.imshow` + `cv2.waitKey(1)` (lo que hace hoy el tracker) frente
a `cv2.imshow` + `cv2.pollKey()` sobre un frame guardado, N vueltas por modo
y con un tope de tiempo para toda la corrida (principio 9). Por OpenCV 4.13:
`waitKey(delay)` espera *al menos* `delay` ms, segun el planificador del
sistema; `pollKey()` atiende los eventos de la ventana sin esperar. Uno de los
dos tiene que llamarse para que la ventana viva.

No abre ninguna camara ni puerto: solo una ventana de HighGUI, que se cierra
al acabar cada modo. Desde codigo\\, con el venv y los argumentos explicitos:

    python -m diagnostics.measure_window ^
        --frame tests\\data\\marker0_gs1_frames\\frame_00240.png ^
        --iterations 300 --timeout 60 --output "<salida>.json"

Sale con 0 si los dos modos completaron sus vueltas; con 3 si el tope de
tiempo corto la corrida (el JSON se escribe igual, con `truncated`).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from diagnostics.pose_log import timing_stats

WINDOW_TITLE = "measure_window - no es el tracker"
WARMUP = 10
MODES: dict[str, Callable[[], int]] = {
    "waitKey(1)": lambda: cv2.waitKey(1),
    "pollKey()": lambda: cv2.pollKey(),
}


def load_frame(path: Path) -> np.ndarray:
    """El frame en BGR (un PNG en gris se pasa a 3 canales, como el display del tracker)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe el frame: {path}")
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"OpenCV no pudo leer el frame: {path}")
    return img


def measure_mode(name: str, frame: np.ndarray, iterations: int, deadline: float,
                 clock: Callable[[], float] = time.perf_counter) -> dict:
    """`WARMUP` vueltas sin contar y despues hasta `iterations` de imshow + la tecla del modo.

    Para en cuanto el reloj pasa de `deadline` (segundos de `clock`)."""
    key_fn = MODES[name]
    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_AUTOSIZE)
    imshow_ms: list[float] = []
    key_ms: list[float] = []
    total_ms: list[float] = []
    truncated = False
    try:
        for _ in range(WARMUP):
            cv2.imshow(WINDOW_TITLE, frame)
            key_fn()
        for _ in range(int(iterations)):
            if clock() >= deadline:
                truncated = True
                break
            t0 = clock()
            cv2.imshow(WINDOW_TITLE, frame)
            t1 = clock()
            key_fn()
            t2 = clock()
            imshow_ms.append((t1 - t0) * 1000.0)
            key_ms.append((t2 - t1) * 1000.0)
            total_ms.append((t2 - t0) * 1000.0)
    finally:
        cv2.destroyWindow(WINDOW_TITLE)
        cv2.pollKey()       # deja que HighGUI procese el cierre
    total = timing_stats(total_ms)
    return {
        "mode": name, "iterations": len(total_ms), "requested": int(iterations),
        "truncated": truncated,
        "imshow": timing_stats(imshow_ms), "key": timing_stats(key_ms), "total": total,
        "fps_equivalent": (1000.0 / total["mean_ms"]) if total["mean_ms"] else None,
        "total_ms_per_iteration": [round(x, 4) for x in total_ms],
    }


def run(frame_path: Path, iterations: int, timeout_s: float,
        clock: Callable[[], float] = time.perf_counter) -> dict:
    """Los dos modos, uno tras otro, con un solo tope de `timeout_s` segundos."""
    frame = load_frame(frame_path)
    deadline = clock() + float(timeout_s)
    modes = [measure_mode(name, frame, iterations, deadline, clock) for name in MODES]
    return {
        "frame": str(Path(frame_path).resolve()), "shape": list(frame.shape),
        "iterations": int(iterations), "timeout_s": float(timeout_s), "warmup": WARMUP,
        "truncated": any(m["truncated"] for m in modes),
        "modes": modes, "opencv": cv2.__version__, "clock": "time.perf_counter",
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_result(res: dict) -> str:
    lineas = [f"{'modo':<12} {'vueltas':>7} {'imshow':>8} {'tecla':>8} {'total':>8} "
              f"{'p50':>8} {'p95':>8} {'fps eq.':>8}   (ms, media salvo p50/p95 del total)"]
    for m in res["modes"]:
        if m["total"]["mean_ms"] is None:
            lineas.append(f"{m['mode']:<12} {0:>7}  (sin vueltas)")
            continue
        lineas.append(f"{m['mode']:<12} {m['iterations']:>7} {m['imshow']['mean_ms']:8.3f} "
                      f"{m['key']['mean_ms']:8.3f} {m['total']['mean_ms']:8.3f} "
                      f"{m['total']['p50_ms']:8.3f} {m['total']['p95_ms']:8.3f} "
                      f"{m['fps_equivalent']:8.1f}")
    if res["truncated"]:
        lineas.append("[AVISO] El tope de tiempo corto la corrida: hay menos vueltas que las pedidas.")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Cronometra imshow + waitKey(1) frente a imshow + pollKey() sin camara (meta 003).")
    ap.add_argument("--frame", required=True, type=Path,
                    help="Frame guardado (PNG), p. ej. tests\\data\\marker0_gs1_frames\\frame_00240.png.")
    ap.add_argument("--iterations", required=True, type=int, help="Vueltas por modo (300 en la fase 6).")
    ap.add_argument("--timeout", required=True, type=float,
                    help="Tope de toda la corrida, en segundos.")
    ap.add_argument("--output", type=Path, default=None, help="JSON de salida (no se pisa).")
    args = ap.parse_args(argv)
    if args.iterations < 1:
        ap.error("--iterations tiene que ser >= 1")
    if args.timeout <= 0:
        ap.error("--timeout tiene que ser > 0")
    if args.output is not None and args.output.exists():
        ap.error(f"la salida ya existe, no se pisa: {args.output}")

    res = run(args.frame, args.iterations, args.timeout)
    print(format_result(res))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[measure_window] Guardado {args.output}")
    return 3 if res["truncated"] else 0


if __name__ == "__main__":
    sys.exit(main())
