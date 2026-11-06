"""Los extrinsecos de gs2 respecto a gs1 por Marker0 en N posiciones (meta 006, fase 1; P12 b, P27).

Con Marker0 quieto y visto por las dos camaras, `T_gs1<-gs2 = T_gs1<-M . T_gs2<-M^-1`. Por
posicion se toma la media de las poses de cada camara (`geometry.mean_pose`) y luego la
media entre posiciones (`from_marker_positions`); la dispersion entre posiciones (mm y
grados) dice cuanto se mueve el resultado de una posicion a otra. `leave_one_out` deja
una posicion fuera, saca los extrinsecos de las demas y mide la coincidencia en la que
quedo fuera: es el criterio 1 del spec sin circularidad (P27). El `.yml` (P18) lleva el
sha256 de los dos intrinsecos y `load_extrinsics` aborta si no coinciden con los de `data/`.

Fase 2 (B94): `half_split` saca los extrinsecos de las dos mitades de un tramo (el suelo de
ruido y si algo se movio dentro de el) y `repeat_check` compara los de la posicion 1 del
principio con los de la posicion 1 del final (si difieren, una camara se movio entre medias).
La orden `guardar` escribe el `.yml` solo si el criterio 1 de un `resultados.json` cumple:

    python -m fusion.extrinsics guardar --resultados <corrida>\\resultados.json --metodo marker0 ^
        --montaje pinzas --intrinsecos gs1=data\\intrinsecos_gs1_1280x960.yml ^
        gs2=data\\intrinsecos_gs2_1280x960.yml --salida data\\extrinsecos_gs1_gs2_pinzas.yml

Context7 (2026-11-05): PyYAML `/yaml/pyyaml` (`safe_dump(data, stream, sort_keys=False,
default_flow_style=False)`, `safe_load(stream)`); SciPy `/scipy/scipy` (`Rotation.mean`);
CPython `/python/cpython/v3.11.14` (`argparse.add_subparsers(dest=..., required=True)`).
Instalados: PyYAML 6.0.3, SciPy 1.17.1, Python 3.11.9.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import yaml

from fusion.dataset import sha256_file
from fusion.geometry import angle_deg, inv, mean_pose, pose_difference

FORMAT = 1
REPEAT_TOL_MM = 0.5         # los umbrales del criterio 1 del spec (P7)
REPEAT_TOL_DEG = 0.2


@dataclass(frozen=True)
class Extrinsics:
    """`T_ref<-other` (4x4, mm) con su procedencia."""
    T_ref_other: np.ndarray
    reference: str
    other: str
    method: str                     # "marker0" | "tablero"
    mount: str                      # "pinzas" | "estructura"
    intrinsics_sha256: dict[str, str]
    angle_deg: float                # entre los ejes opticos
    validation: dict = field(default_factory=dict)
    alternative: dict | None = None


def optical_axis_angle_deg(T_ref_other: np.ndarray) -> float:
    """El angulo entre los ejes opticos (z) de las dos camaras."""
    R = np.asarray(T_ref_other, dtype=np.float64)[:3, :3]
    return float(np.degrees(np.arccos(np.clip(R[2, 2], -1.0, 1.0))))


def _extrinsics_of_position(Ta: np.ndarray, Tb: np.ndarray) -> np.ndarray:
    """`T_a<-b = mean(T_a<-M) . mean(T_b<-M)^-1` de las parejas de una posicion."""
    Ta = np.asarray(Ta, dtype=np.float64).reshape(-1, 4, 4)
    Tb = np.asarray(Tb, dtype=np.float64).reshape(-1, 4, 4)
    if len(Ta) != len(Tb) or len(Ta) == 0:
        raise ValueError("cada posicion necesita N >= 1 parejas (T_a<-M, T_b<-M)")
    return mean_pose(Ta) @ inv(mean_pose(Tb))


def _mean_and_spread(Ts: list[np.ndarray]) -> tuple[np.ndarray, float, float]:
    T = mean_pose(np.asarray(Ts))
    if len(Ts) < 2:
        return T, 0.0, 0.0
    dmm = [float(np.linalg.norm(x[:3, 3] - T[:3, 3])) for x in Ts]
    ddeg = [angle_deg(T[:3, :3], x[:3, :3]) for x in Ts]
    return T, float(np.sqrt(np.mean(np.square(dmm)))), float(np.sqrt(np.mean(np.square(ddeg))))


def from_marker_positions(pairs_per_position: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    """`pairs_per_position[k] = (T_a<-M (N_k,4,4), T_b<-M (N_k,4,4))`, emparejadas por hora.
    Devuelve `T_ref_other` (la media entre posiciones), `per_position` (la de cada una),
    `spread_mm` y `spread_deg` (RMS de la distancia de cada posicion a la media),
    `angle_deg` y `pairs_per_position`."""
    if not pairs_per_position:
        raise ValueError("from_marker_positions: no hay posiciones")
    per = [_extrinsics_of_position(Ta, Tb) for Ta, Tb in pairs_per_position]
    T, smm, sdeg = _mean_and_spread(per)
    return {"T_ref_other": T, "per_position": per, "spread_mm": smm, "spread_deg": sdeg,
            "angle_deg": optical_axis_angle_deg(T), "n_positions": len(per),
            "pairs_per_position": [int(len(Ta)) for Ta, _ in pairs_per_position]}


def agreement_stats(Ta: np.ndarray, Tb_in_a: np.ndarray) -> dict:
    """Pareja a pareja, `|t_a - t_b|` (mm) y el angulo (grados): media, sd, maximo y la
    diferencia media por eje (mm, a - b) en el frame de `a`."""
    Ta = np.asarray(Ta, dtype=np.float64).reshape(-1, 4, 4)
    Tb = np.asarray(Tb_in_a, dtype=np.float64).reshape(-1, 4, 4)
    if len(Ta) != len(Tb) or len(Ta) == 0:
        raise ValueError("agreement_stats: hacen falta N >= 1 parejas")
    dmm = np.array([pose_difference(a, b)[0] for a, b in zip(Ta, Tb)])
    ddeg = np.array([pose_difference(a, b)[1] for a, b in zip(Ta, Tb)])
    dxyz = Ta[:, :3, 3] - Tb[:, :3, 3]
    return {"n": int(len(Ta)),
            "mean_mm": float(dmm.mean()), "sd_mm": float(dmm.std(ddof=1)) if len(dmm) > 1 else 0.0,
            "max_mm": float(dmm.max()),
            "mean_deg": float(ddeg.mean()), "sd_deg": float(ddeg.std(ddof=1)) if len(ddeg) > 1 else 0.0,
            "max_deg": float(ddeg.max()),
            "mean_dxyz_mm": [float(x) for x in dxyz.mean(axis=0)],
            "bias_mm": float(np.linalg.norm(dxyz.mean(axis=0)))}


def apply_extrinsics(T_a_b: np.ndarray, Tb: np.ndarray) -> np.ndarray:
    """`T_a<-b . T_b<-M` para N poses (N,4,4)."""
    return np.einsum("ij,njk->nik", np.asarray(T_a_b, dtype=np.float64),
                     np.asarray(Tb, dtype=np.float64).reshape(-1, 4, 4))


def leave_one_out(pairs_per_position: list[tuple[np.ndarray, np.ndarray]]) -> list[dict]:
    """Para cada posicion k: los extrinsecos de las otras y la coincidencia en k
    (`agreement_stats` de `T_a<-M` frente a `T_a<-b . T_b<-M`). Con una sola posicion no
    hay validacion cruzada: lo dice en `note`."""
    n = len(pairs_per_position)
    out = []
    for k in range(n):
        others = [p for i, p in enumerate(pairs_per_position) if i != k]
        Ta, Tb = pairs_per_position[k]
        if not others:
            out.append({"position": k, "note": "una sola posicion: sin validacion cruzada",
                        "T_ref_other": None, "agreement": None})
            continue
        ext = from_marker_positions(others)
        agr = agreement_stats(Ta, apply_extrinsics(ext["T_ref_other"], Tb))
        out.append({"position": k, "n_others": len(others), "T_ref_other": ext["T_ref_other"],
                    "spread_others_mm": ext["spread_mm"], "spread_others_deg": ext["spread_deg"],
                    "agreement": agr})
    return out


# ---------------------------------------------------------------------------
# B94 (fase 2): las dos mitades de un tramo y la posicion repetida
# ---------------------------------------------------------------------------

def half_split(Ta: np.ndarray, Tb: np.ndarray) -> dict:
    """Los extrinsecos de la primera y la segunda mitad de las parejas de un tramo (en su
    orden, el del tiempo) y su diferencia (mm, grados): el suelo de ruido del tramo y si algo
    se movio dentro de el. Hacen falta >= 4 parejas."""
    Ta = np.asarray(Ta, dtype=np.float64).reshape(-1, 4, 4)
    Tb = np.asarray(Tb, dtype=np.float64).reshape(-1, 4, 4)
    n = len(Ta)
    if n != len(Tb) or n < 4:
        raise ValueError(f"half_split: hacen falta >= 4 parejas (T_a<-M, T_b<-M), no {n} y {len(Tb)}")
    h = n // 2
    T1 = _extrinsics_of_position(Ta[:h], Tb[:h])
    T2 = _extrinsics_of_position(Ta[h:], Tb[h:])
    dmm, ddeg = pose_difference(T1, T2)
    return {"n": int(n), "n_first": int(h), "n_second": int(n - h), "T_first": T1, "T_second": T2,
            "diff_mm": dmm, "diff_deg": ddeg}


def repeat_check(first: tuple[np.ndarray, np.ndarray], last: tuple[np.ndarray, np.ndarray],
                 tol_mm: float = REPEAT_TOL_MM, tol_deg: float = REPEAT_TOL_DEG) -> dict:
    """La posicion 1 del principio (`first = (T_a<-M, T_b<-M)`) frente a la del final (`last`):
    los extrinsecos de cada una, su diferencia en traslacion (mm) y giro (grados) y `coinciden`
    (< `tol_mm` y < `tol_deg`). Ademas, cuanto se movio el marker entre las dos visto por cada
    camara sola (la media de sus poses): si por `a` se movio mucho, el marker no volvio a su
    sitio y la comparacion no separa nada."""
    Ta1, Tb1 = (np.asarray(x, dtype=np.float64).reshape(-1, 4, 4) for x in first)
    Ta2, Tb2 = (np.asarray(x, dtype=np.float64).reshape(-1, 4, 4) for x in last)
    E1 = _extrinsics_of_position(Ta1, Tb1)
    E2 = _extrinsics_of_position(Ta2, Tb2)
    dmm, ddeg = pose_difference(E1, E2)
    sa = pose_difference(mean_pose(Ta1), mean_pose(Ta2))
    sb = pose_difference(mean_pose(Tb1), mean_pose(Tb2))
    return {"n_first": int(len(Ta1)), "n_last": int(len(Ta2)), "T_first": E1, "T_last": E2,
            "diff_mm": dmm, "diff_deg": ddeg, "tol_mm": float(tol_mm), "tol_deg": float(tol_deg),
            "coinciden": bool(dmm < tol_mm and ddeg < tol_deg),
            "marker_shift_ref_mm": sa[0], "marker_shift_ref_deg": sa[1],
            "marker_shift_other_mm": sb[0], "marker_shift_other_deg": sb[1]}


# ---------------------------------------------------------------------------
# El archivo (P18)
# ---------------------------------------------------------------------------

def _to_plain(x):
    if isinstance(x, np.ndarray):
        return [_to_plain(v) for v in x.tolist()]
    if isinstance(x, dict):
        return {str(k): _to_plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_plain(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    return x


def save_extrinsics(path: Path, ext: Extrinsics) -> Path:
    """Escribe el `.yml` (no pisa uno que exista)."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"los extrinsecos ya existen, no se pisan: {path}")
    d = _to_plain(asdict(ext))
    d["T_ref_other"] = [[float(v) for v in fila] for fila in np.asarray(ext.T_ref_other).reshape(4, 4).tolist()]
    doc = {"format": FORMAT, "units": "mm", "convention": "T_ref_other lleva puntos del frame de `other` al de `reference`"}
    doc.update(d)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return path


def load_extrinsics(path: Path, intrinsics_files: dict[str, Path]) -> Extrinsics:
    """Lee el `.yml` y aborta si el sha256 de algun intrinseco no es el de `intrinsics_files`."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no existen los extrinsecos: {path}")
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict) or int(doc.get("format", -1)) != FORMAT:
        raise ValueError(f"{path.name}: formato desconocido (se espera format {FORMAT})")
    T = np.asarray(doc["T_ref_other"], dtype=np.float64).reshape(4, 4)
    R = T[:3, :3]
    if not np.allclose(R @ R.T, np.eye(3), atol=1e-6) or not np.allclose(T[3], [0, 0, 0, 1]):
        raise ValueError(f"{path.name}: T_ref_other no es una pose rigida")
    shas = {str(k): str(v) for k, v in (doc.get("intrinsics_sha256") or {}).items()}
    for cam, p in intrinsics_files.items():
        local = sha256_file(Path(p))
        if shas.get(cam) != local:
            raise ValueError(f"{path.name}: el sha256 de los intrinsecos de {cam} no coincide "
                             f"({str(shas.get(cam))[:12]} vs {local[:12]}): recalibrar o rehacer los extrinsecos")
    return Extrinsics(T_ref_other=T, reference=str(doc["reference"]), other=str(doc["other"]),
                      method=str(doc["method"]), mount=str(doc["mount"]), intrinsics_sha256=shas,
                      angle_deg=float(doc.get("angle_deg", optical_axis_angle_deg(T))),
                      validation=dict(doc.get("validation") or {}),
                      alternative=doc.get("alternative"))


# ---------------------------------------------------------------------------
# CLI: guardar (fase 2)
# ---------------------------------------------------------------------------

def _cam_path(texto: str) -> tuple[str, Path]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera CAMARA=RUTA, no {texto!r}")
    c, r = texto.split("=", 1)
    return c.strip(), Path(r.strip())


def extrinsics_from_results(rep: dict, method: str, mount: str, intrinsics: dict[str, Path]) -> Extrinsics:
    """Los `Extrinsics` que `guardar` escribe desde un `resultados.json` del experimento.
    Exige que el criterio 1 cumpla y, si hay veredicto de B94, que sea «cumple»; que los
    intrinsecos dados sean los que la grabacion llevaba (sha256); y que exista el metodo pedido.
    Lanza ValueError con el motivo si no."""
    c1 = rep.get("criterio_1") or {}
    if c1.get("cumple") is None:
        raise ValueError("el criterio 1 no se evaluo en ese resultados.json: no se guardan extrinsecos")
    if not c1["cumple"]:
        raise ValueError(f"el criterio 1 no cumple ({c1.get('peor_mm', float('nan')):.3f} mm / "
                         f"{c1.get('peor_deg', float('nan')):.3f} grados frente a < {REPEAT_TOL_MM} mm y < {REPEAT_TOL_DEG} grados): no se guardan extrinsecos")
    b94 = rep.get("b94") or {}
    if b94 and b94.get("veredicto") != "cumple":
        raise ValueError(f"el veredicto de B94 es {b94.get('veredicto')!r}, no 'cumple': no se guardan extrinsecos ({b94.get('motivo', '')})")
    ext = rep.get("extrinsecos") or {}
    bundle = (rep.get("consistencia") or {}).get("bundle")
    if not ext:
        raise ValueError("resultados.json sin extrinsecos")
    marker0 = {"method": "marker0", "T_ref_other": ext["T_ref_other"], "spread_mm": ext.get("spread_mm"),
               "spread_deg": ext.get("spread_deg"), "angle_deg": ext.get("angle_deg")}
    conjunto = ({"method": "bundle", "T_ref_other": bundle["T_ref_other"], "rms_px": bundle.get("rms_px"),
                 "angle_deg": bundle.get("angle_deg")} if bundle else None)
    if method == "marker0":
        chosen, alt = marker0, conjunto
    elif method == "bundle":
        if conjunto is None:
            raise ValueError("resultados.json sin ajuste conjunto (consistencia.bundle): no hay extrinsecos de metodo bundle")
        chosen, alt = conjunto, marker0
    else:
        raise ValueError(f"metodo desconocido: {method!r} (marker0 | bundle)")
    shas = {}
    grabados = {}
    for seg in (rep.get("comprobacion") or {}).values():
        for cam, d in (seg.get("calibration_sha256") or {}).items():
            grabados.setdefault(cam, set()).add(str(d.get("recorded")))
    for cam, p in intrinsics.items():
        p = Path(p)
        if not p.is_file():
            raise ValueError(f"no existe el intrinseco de {cam}: {p}")
        shas[cam] = sha256_file(p)
        if cam in grabados and shas[cam] not in grabados[cam]:
            raise ValueError(f"el sha256 de {p.name} ({shas[cam][:12]}) no es el que llevaba la grabacion de {cam} "
                             f"({', '.join(s[:12] for s in sorted(grabados[cam]))})")
    T = np.asarray(chosen["T_ref_other"], dtype=np.float64).reshape(4, 4)
    validation = {"datos": rep.get("datos"), "criterio_1_peor_mm": c1.get("peor_mm"), "criterio_1_peor_deg": c1.get("peor_deg"),
                  "posiciones": ext.get("n_positions"), "segmentos": list(ext.get("segmentos") or []),
                  "min_parejas": c1.get("min_parejas"), "spread_mm": ext.get("spread_mm"), "spread_deg": ext.get("spread_deg"),
                  "b94": b94.get("veredicto")}
    return Extrinsics(T_ref_other=T, reference="gs1", other="gs2", method=chosen["method"], mount=mount,
                      intrinsics_sha256=shas, angle_deg=optical_axis_angle_deg(T), validation=validation,
                      alternative=_to_plain(alt) if alt else None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Los extrinsecos de gs2 respecto a gs1 (meta 006).")
    sub = ap.add_subparsers(dest="orden", required=True)
    g = sub.add_parser("guardar", help="Escribe el .yml de extrinsecos desde un resultados.json, solo si el criterio 1 cumple.")
    g.add_argument("--resultados", required=True, type=Path, help="resultados.json de python -m fusion.experiment.")
    g.add_argument("--metodo", required=True, choices=["marker0", "bundle"], help="El vigente; el otro va en `alternativa`.")
    g.add_argument("--montaje", required=True, choices=["pinzas", "estructura"])
    g.add_argument("--intrinsecos", required=True, nargs="+", type=_cam_path, metavar="CAM=YML",
                   help="gs1=<yml> gs2=<yml>: los de data/ con que se grabo (se comprueba el sha256).")
    g.add_argument("--salida", required=True, type=Path, help="El .yml (no se pisa).")
    args = ap.parse_args(argv)
    try:
        rep = json.loads(Path(args.resultados).read_text(encoding="utf-8"))
        intr = dict(args.intrinsecos)
        for cam in ("gs1", "gs2"):
            if cam not in intr:
                raise ValueError(f"faltan los intrinsecos de {cam} (--intrinsecos {cam}=<yml>)")
        ext = extrinsics_from_results(rep, args.metodo, args.montaje, intr)
        p = save_extrinsics(args.salida, ext)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"[extrinsecos] no se guarda: {e}", file=sys.stderr)
        return 1 if isinstance(e, ValueError) and "no se guardan" in str(e) else 2
    print(f"[extrinsecos] escrito {p}: metodo {ext.method}, montaje {ext.mount}, theta {ext.angle_deg:.2f} grados, "
          f"criterio 1 {ext.validation.get('criterio_1_peor_mm'):.3f} mm / {ext.validation.get('criterio_1_peor_deg'):.3f} grados")
    return 0


__all__ = ["Extrinsics", "from_marker_positions", "leave_one_out", "agreement_stats", "apply_extrinsics",
           "optical_axis_angle_deg", "save_extrinsics", "load_extrinsics", "half_split", "repeat_check",
           "extrinsics_from_results", "main"]

if __name__ == "__main__":
    sys.exit(main())
