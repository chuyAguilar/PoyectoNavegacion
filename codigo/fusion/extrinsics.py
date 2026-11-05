"""Los extrinsecos de gs2 respecto a gs1 por Marker0 en N posiciones (meta 006, fase 1; P12 b, P27).

Con Marker0 quieto y visto por las dos camaras, `T_gs1<-gs2 = T_gs1<-M . T_gs2<-M^-1`. Por
posicion se toma la media de las poses de cada camara (`geometry.mean_pose`) y luego la
media entre posiciones (`from_marker_positions`); la dispersion entre posiciones (mm y
grados) dice cuanto se mueve el resultado de una posicion a otra. `leave_one_out` deja
una posicion fuera, saca los extrinsecos de las demas y mide la coincidencia en la que
quedo fuera: es el criterio 1 del spec sin circularidad (P27). El `.yml` (P18) lleva el
sha256 de los dos intrinsecos y `load_extrinsics` aborta si no coinciden con los de `data/`.

Context7 (2026-11-05): PyYAML `/yaml/pyyaml` (`safe_dump(data, stream, sort_keys=False,
default_flow_style=False)`, `safe_load(stream)`); SciPy `/scipy/scipy` (`Rotation.mean`).
Instalados: PyYAML 6.0.3, SciPy 1.17.1.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import yaml

from fusion.dataset import sha256_file
from fusion.geometry import angle_deg, inv, mean_pose, pose_difference

FORMAT = 1


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


__all__ = ["Extrinsics", "from_marker_positions", "leave_one_out", "agreement_stats",
           "apply_extrinsics", "optical_axis_angle_deg", "save_extrinsics", "load_extrinsics"]
