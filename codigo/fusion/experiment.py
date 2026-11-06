"""El experimento fuera de linea de las dos camaras (meta 006 · Grafo de factores
optico-inercial, fase 1 · Verlo, parte A · Los numeros sin gtsam).

Sobre la grabacion de los dos trackers de la Jetson (`Claude outputs/fases/006/grabacion/
datos/<fecha>/`, un `.npz` por camara y segmento) mide lo que la fusion daria y escribe
`resultados.json` (sin tiempos ni fechas: dos corridas seguidas dan el mismo archivo),
`tiempos.json` e `informe.html`. Los segmentos: S1_reposo (el jitter), S2_pos1..5 (los
extrinsecos y la coincidencia, P16), S3_tapa_gs1 / S3_tapa_gs2 (tapar una camara) y
S4_movimiento (el desfase). Los numeros de los criterios del spec son el resultado, no
el criterio de la fase.

Desde `codigo\\` con el venv, con todos los argumentos explicitos (principio 7):

    python -m fusion.experiment --datos "..\\Claude outputs\\fases\\006\\grabacion\\datos\\20261105-120826" ^
        --intrinsecos gs1=data\\intrinsecos_gs1_1280x960.yml gs2=data\\intrinsecos_gs2_1280x960.yml ^
        --salida "..\\Claude outputs\\fases\\006\\fase-1\\corrida-01" --motores numpy_pose numpy_reproj ^
        --timeout 600

Codigo 0 si corrio entero y todos los segmentos pasaron la comprobacion; 1 si algun
segmento no la paso (lo dice, lo deja fuera y sigue con los demas); 2 si no pudo empezar o
se paso del tope. No importa gtsam: los motores `gtsam_*` son de la parte B.

Fase 2 · S2 otra vez en Windows, y B94: el segmento `S2_pos1_fin` (la posicion 1 repetida al
final; entra en sigma_px y en el criterio 2 como un reposo mas, pero no en los extrinsecos
ni en la validacion cruzada, que dejarian dentro a su gemelo), el veredicto de B94
(`b94_verdict`: sin_decidir | se_movio | cumple | sesgo_por_vista) y `--tolerancia-ancla-ms`
(1 por defecto; 20 para las grabaciones del PC, donde `t_start` es `time.time()` con pasos de
15.6 ms). Con la tolerancia por defecto y sin `S2_pos1_fin`, `resultados.json` es el de la
fase 1 mas las claves `b94` y `tolerancia_ancla_ms`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from diagnostics.pose_log import timing_stats
from fusion import dataset as ds
from fusion import extrinsics as ex
from fusion import geometry as g
from fusion import metrics as mt
from fusion import pairing as pr
from fusion import report as rp

ENGINES_A = ("numpy_pose", "numpy_reproj")
ENGINES_B = ("gtsam_pose", "gtsam_reproj", "gtsam_smoother")
SEGMENTS: dict[str, dict] = {
    "S1_reposo": {"kind": "rest", "role": "S1"},
    "S2_pos1": {"kind": "rest", "role": "S2"}, "S2_pos2": {"kind": "rest", "role": "S2"},
    "S2_pos3": {"kind": "rest", "role": "S2"}, "S2_pos4": {"kind": "rest", "role": "S2"},
    "S2_pos5": {"kind": "rest", "role": "S2"},
    "S2_pos1_fin": {"kind": "rest", "role": "S2_rep"},      # fase 2: la posicion 1 otra vez, al final
    "S3_tapa_gs1": {"kind": "occlusion", "covered": "gs1"},
    "S3_tapa_gs2": {"kind": "occlusion", "covered": "gs2"},
    "S4_movimiento": {"kind": "motion"},
}
THRESH = {"agreement_mm": 0.5, "agreement_deg": 0.2, "reduction": 0.30, "jump_mm": 0.5}
ANGLE_WARN_DEG = 10.0
REF, OTHER = "gs1", "gs2"
B94_REPEAT = ("S2_pos1", "S2_pos1_fin")
B94_RETURN_TOL = {"mm": 5.0, "deg": 2.0}      # el marker no volvio a su sitio (umbral propuesto en el plan, sin medir)
B94_VERDICTS = ("sin_decidir", "se_movio", "cumple", "sesgo_por_vista")


class Deadline:
    """El tope del experimento (principio 9): `check` lanza TimeoutError si se paso."""

    def __init__(self, seconds: float | None) -> None:
        self.t0 = time.perf_counter()
        self.seconds = float(seconds) if seconds is not None else None

    def elapsed(self) -> float:
        return time.perf_counter() - self.t0

    def check(self, where: str) -> None:
        if self.seconds is not None and self.elapsed() > self.seconds:
            raise TimeoutError(f"tope de {self.seconds:.0f} s superado en {where} ({self.elapsed():.0f} s)")


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else None
    return x


# ---------------------------------------------------------------------------
# Los bloques
# ---------------------------------------------------------------------------

def pairs_of(tracks: dict[str, ds.CameraTrack], tolerance_s: float | None = None,
             offset_s: float = 0.0) -> tuple[np.ndarray, float]:
    """Las parejas `(i_gs1, j_gs2)` entre frames con pose cruda, dentro de medio periodo de
    gs1 (P13 a) salvo que llegue `tolerance_s`. Devuelve `(parejas, tolerancia)`."""
    a, b = tracks[REF], tracks[OTHER]
    tol = 0.5 * a.period_s if tolerance_s is None else float(tolerance_s)
    ia, ib = np.flatnonzero(a.valid), np.flatnonzero(b.valid)
    p = pr.pair_by_time(a.t[ia], b.t[ib], tol, offset_s)
    if len(p) == 0:
        return np.zeros((0, 2), dtype=np.int64), tol
    return np.column_stack([ia[p[:, 0]], ib[p[:, 1]]]), tol


def fit_sigma_px(rest: dict[str, dict], camera: str) -> dict:
    """El sigma_px que hace que la sd 3D predicha por la jacobiana (en la pose media de cada
    segmento de reposo) iguale la medida: `sigma^2 = sum(var medida) / sum(var predicha con
    sigma = 1)`, sobre los segmentos `rest` (cruda y sin deriva)."""
    num = num_d = den = 0.0
    segs = []
    for seg, r in rest.items():
        tr = r["tracks"][camera]
        p = tr.positions[tr.valid]
        if len(p) < 10:
            continue
        sd = mt.rest_sd(p, tr.t[tr.valid])
        Tm = g.mean_pose(tr.T_raw[tr.valid])
        unit = g.position_covariance(Tm, g.pose_covariance(Tm, tr.size_mm, tr.K, tr.dist, 1.0))
        den += float(np.trace(unit))
        num += sd["sd_3d_mm"] ** 2
        num_d += sd["sd_3d_detrended_mm"] ** 2
        segs.append(seg)
    if den <= 0:
        return {"sigma_px": None, "sigma_px_detrended": None, "segmentos": segs, "origen": "sin datos"}
    return {"sigma_px": float(np.sqrt(num / den)), "sigma_px_detrended": float(np.sqrt(num_d / den)),
            "segmentos": segs, "origen": "ajustado (sd cruda)"}


def fuse_pair(tracks: dict[str, ds.CameraTrack], i: int, j: int, T_ref_other: np.ndarray,
              sigma: dict[str, float], engine: str) -> tuple[np.ndarray, np.ndarray]:
    """La pose fusionada de la pareja `(i, j)` con el motor dado: `(T_gs1<-M, Sigma)`."""
    a, b = tracks[REF], tracks[OTHER]
    Z1 = a.T_raw[i]
    Z2 = T_ref_other @ b.T_raw[j]
    if engine == "numpy_pose":
        c1 = g.pose_covariance(Z1, a.size_mm, a.K, a.dist, sigma[REF])
        c2 = g.transport_covariance(T_ref_other, g.pose_covariance(b.T_raw[j], b.size_mm, b.K, b.dist, sigma[OTHER]))
        return g.fuse_poses([Z1, Z2], [c1, c2])
    if engine == "numpy_reproj":
        T, cov, _rms = g.joint_pnp([(REF, a.corners[i], a.K, a.dist, np.eye(4)),
                                    (OTHER, b.corners[j], b.K, b.dist, T_ref_other)],
                                   a.size_mm, Z1, sigma)
        return T, cov
    raise ValueError(f"motor desconocido o de la parte B: {engine!r}")


def fused_rest(tracks, pairs, T_ref_other, sigma, engines, timings) -> tuple[dict, dict]:
    """Las posiciones fusionadas de las parejas, por motor, y el RMS en px de cada fusion por
    reproyeccion (cuanto discrepan las dos vistas con esos extrinsecos); los tiempos van a `timings`."""
    out, rms = {}, {}
    a, b = tracks[REF], tracks[OTHER]
    for e in engines:
        P = np.full((len(pairs), 3), np.nan)
        R = np.full(len(pairs), np.nan)
        ms = timings.setdefault(e, [])
        for k, (i, j) in enumerate(pairs):
            t0 = time.perf_counter()
            T, _cov = fuse_pair(tracks, int(i), int(j), T_ref_other, sigma, e)
            ms.append((time.perf_counter() - t0) * 1000.0)
            P[k] = T[:3, 3]
            if e == "numpy_reproj":
                r1 = g.project_corners(T, a.size_mm, a.K, a.dist) - a.corners[int(i)]
                r2 = g.project_corners(g.inv(T_ref_other) @ T, b.size_mm, b.K, b.dist) - b.corners[int(j)]
                R[k] = float(np.sqrt(np.mean(np.concatenate([r1.ravel(), r2.ravel()]) ** 2)))
        out[e] = P
        rms[e] = float(np.nanmedian(R)) if np.isfinite(R).any() else None
    return out, rms


def fused_timeline(tracks, T_ref_other, sigma, engine, timings) -> tuple[np.ndarray, np.ndarray]:
    """La linea fusionada por instante para S3: las parejas se fusionan; los frames con pose de
    una sola camara pasan tal cual (gs2 llevada a gs1). Devuelve `(t, posiciones)` ordenadas."""
    a, b = tracks[REF], tracks[OTHER]
    pairs, _tol = pairs_of(tracks)
    used_a = np.zeros(len(a.t), bool)
    used_b = np.zeros(len(b.t), bool)
    ts, ps = [], []
    ms = timings.setdefault(engine, [])
    for i, j in pairs:
        t0 = time.perf_counter()
        T, _ = fuse_pair(tracks, int(i), int(j), T_ref_other, sigma, engine)
        ms.append((time.perf_counter() - t0) * 1000.0)
        ts.append(0.5 * (a.t[i] + b.t[j]))
        ps.append(T[:3, 3])
        used_a[i] = used_b[j] = True
    for i in np.flatnonzero(a.valid & ~used_a):
        ts.append(a.t[i])
        ps.append(a.T_raw[i][:3, 3])
    for j in np.flatnonzero(b.valid & ~used_b):
        ts.append(b.t[j])
        ps.append((T_ref_other @ b.T_raw[j])[:3, 3])
    if not ts:
        return np.zeros(0), np.zeros((0, 3))
    order = np.argsort(ts)
    return np.asarray(ts)[order], np.asarray(ps)[order]


def _criterion(cid: str, nombre: str, valor, umbral: str, estado: str, nota: str = "") -> dict:
    return {"id": cid, "nombre": nombre, "valor": valor, "umbral": umbral, "estado": estado, "nota": nota}


def consistency_diagnostics(rest: dict, ext_segs: list[str], T12_init: np.ndarray,
                            sigma_px: dict[str, float] | None, log=print) -> dict:
    """Si las N posiciones de Marker0 son compatibles con dos camaras rigidas y sus intrinsecos:
    - `bundle`: `T_gs1<-gs2` y la pose de cada posicion ajustadas a la vez sobre las esquinas
      medias (`fusion.bundle`, con todas las combinaciones de la ambiguedad de IPPE): su RMS
      en px frente al de cada vista sola dice cuanto sobra;
    - `loo`: el mismo ajuste dejando una posicion fuera y la coincidencia en ella;
    - `distancias`: la distancia entre los centros del marker de cada par de posiciones, medida
      por gs1 y por gs2 (invariante a los extrinsecos: si difieren, una camara mide mal o se movio);
    - `vista_unica`: el RMS en px de la pose por minimos cuadrados de cada camara sola."""
    from fusion import bundle as bd
    out: dict = {"segmentos": ext_segs, "distancias": [], "vista_unica": {}, "bundle": None, "loo": []}
    if not ext_segs:
        return out
    tr0 = rest[ext_segs[0]]["tracks"]
    Kd = {c: tr0[c].K for c in (REF, OTHER)}
    Dd = {c: tr0[c].dist for c in (REF, OTHER)}
    size_mm = tr0[REF].size_mm
    sig = {REF: 0.1, OTHER: 0.1} if not sigma_px else {c: float(sigma_px.get(c, 0.1)) for c in (REF, OTHER)}
    obs, Xi, centers, ppp = [], [], {}, []
    for s in ext_segs:
        tr, pairs = rest[s]["tracks"], rest[s]["pairs"]
        c1 = bd.mean_corners(tr[REF].corners[pairs[:, 0]])
        c2 = bd.mean_corners(tr[OTHER].corners[pairs[:, 1]])
        obs.append({REF: c1, OTHER: c2})
        Xi.append([T for T, _e in ds.ippe_solutions(c1, size_mm, Kd[REF], Dd[REF]) if T[2, 3] > 0] or [g.mean_pose(tr[REF].T_raw[pairs[:, 0]])])
        centers[s] = {c: tr[c].positions[pairs[:, k]].mean(axis=0) for k, c in enumerate((REF, OTHER))}
        ppp.append((tr[REF].T_raw[pairs[:, 0]], tr[OTHER].T_raw[pairs[:, 1]]))
        out["vista_unica"][s] = {}
        for k, c in enumerate((REF, OTHER)):
            corners = obs[-1][c]
            T0 = g.mean_pose(tr[c].T_raw[pairs[:, k]])
            _T, _cov, rms = g.joint_pnp([(c, corners, Kd[c], Dd[c], np.eye(4))], size_mm, T0, {c: sig[c]})
            out["vista_unica"][s][c] = {"rms_px": rms, "ippe_median_px": float(np.nanmedian(tr[c].reproj_px[pairs[:, k]]))}
    for i in range(len(ext_segs)):
        for j in range(i + 1, len(ext_segs)):
            a, b = ext_segs[i], ext_segs[j]
            d1 = float(np.linalg.norm(centers[a][REF] - centers[b][REF]))
            d2 = float(np.linalg.norm(centers[a][OTHER] - centers[b][OTHER]))
            out["distancias"].append({"a": a, "b": b, REF: d1, OTHER: d2, "diff_mm": d1 - d2})
    out["distancias_max_diff_mm"] = float(max((abs(d["diff_mm"]) for d in out["distancias"]), default=float("nan")))
    out["vista_unica_max_rms_px"] = float(max(v["rms_px"] for s in out["vista_unica"].values() for v in s.values()))
    if len(ext_segs) >= 2:
        f = bd.fit_extrinsics_bundle_multistart(obs, size_mm, Kd, Dd, sig, T12_init, Xi)
        out["bundle"] = {"T_ref_other": f["T_ref_other"], "rms_px": f["rms_px"], "rms_por_posicion": f["rms_por_posicion"],
                         "iteraciones": f["iteraciones"], "combinaciones": f["combinaciones"], "angle_deg": f["angle_deg"],
                         "sd_T12": [float(x) for x in np.sqrt(np.maximum(np.diag(f["cov_T12"]), 0))]}
        for k, s in enumerate(ext_segs):
            o = [obs[i] for i in range(len(obs)) if i != k]
            x = [[Xi[i][f["combinacion"][i]]] for i in range(len(obs)) if i != k]
            fk = bd.fit_extrinsics_bundle_multistart(o, size_mm, Kd, Dd, sig, f["T_ref_other"], x)
            agr = ex.agreement_stats(ppp[k][0], ex.apply_extrinsics(fk["T_ref_other"], ppp[k][1]))
            out["loo"].append({"segmento": s, "rms_px": fk["rms_px"], "angle_deg": fk["angle_deg"], **agr})
        out["loo_peor_mm"] = float(max(r["mean_mm"] for r in out["loo"]))
        out["loo_peor_deg"] = float(max(r["mean_deg"] for r in out["loo"]))
        log(f"[experimento] consistencia: bundle {f['rms_px']:.3f} px (vista sola <= {out['vista_unica_max_rms_px']:.3f} px); "
            f"distancias gs1-gs2 hasta {out['distancias_max_diff_mm']:.2f} mm; LOO peor {out['loo_peor_mm']:.2f} mm / {out['loo_peor_deg']:.2f} grados")
    return out


def b94_rule(repeat: dict | None, halves: dict[str, dict], criterio_1: dict,
             tol_mm: float = THRESH["agreement_mm"], tol_deg: float = THRESH["agreement_deg"],
             return_tol: dict = B94_RETURN_TOL) -> tuple[str, str]:
    """La regla del veredicto de B94 (plan, fase 2), en este orden; devuelve `(veredicto, motivo)`:
    - `sin_decidir` si falta la posicion repetida o el marker no volvio a su sitio (visto por gs1,
      pos1_fin esta a > 5 mm o > 2 grados de pos1): con la vista cambiada, un sesgo por vista
      tambien cambiaria;
    - `se_movio` si los extrinsecos de pos1 y pos1_fin difieren >= 0.5 mm o >= 0.2 grados, o si
      las dos mitades de algun tramo difieren eso;
    - `cumple` si no se movio y el criterio 1 (validacion cruzada) cumple;
    - `sesgo_por_vista` si no se movio y el criterio 1 no cumple (la hipotesis b de B94)."""
    if repeat is None:
        return "sin_decidir", (f"falta {B94_REPEAT[0]} o {B94_REPEAT[1]} con parejas: sin la posicion 1 repetida al final "
                               "no se separan las dos hipotesis de B94")
    if repeat["marker_shift_ref_mm"] > return_tol["mm"] or repeat["marker_shift_ref_deg"] > return_tol["deg"]:
        return "sin_decidir", (f"el marker no volvio a su sitio: visto por {REF}, {B94_REPEAT[1]} esta a "
                               f"{repeat['marker_shift_ref_mm']:.2f} mm / {repeat['marker_shift_ref_deg']:.2f} grados de {B94_REPEAT[0]} "
                               f"(umbral {return_tol['mm']:g} mm / {return_tol['deg']:g} grados); repetir la sesion con mas cuidado en las marcas")
    moved = []
    if not (repeat["diff_mm"] < tol_mm and repeat["diff_deg"] < tol_deg):
        moved.append(f"los extrinsecos de {B94_REPEAT[0]} y {B94_REPEAT[1]} difieren {repeat['diff_mm']:.3f} mm / {repeat['diff_deg']:.3f} grados")
    for seg, h in halves.items():
        if not (h["diff_mm"] < tol_mm and h["diff_deg"] < tol_deg):
            moved.append(f"las dos mitades de {seg} difieren {h['diff_mm']:.3f} mm / {h['diff_deg']:.3f} grados")
    if moved:
        return "se_movio", "; ".join(moved) + f" (umbral {tol_mm:g} mm / {tol_deg:g} grados): fijar el montaje y repetir la sesion"
    if criterio_1.get("cumple") is None:
        return "sin_decidir", "nada se movio, pero el criterio 1 no se evaluo (una sola posicion usable)"
    if criterio_1["cumple"]:
        return "cumple", (f"nada se movio y el criterio 1 cumple ({criterio_1['peor_mm']:.3f} mm / {criterio_1['peor_deg']:.3f} grados "
                          f"en la peor posicion): B94 se cierra; la causa fue el montaje de la grabacion anterior")
    return "sesgo_por_vista", (f"nada se movio y el criterio 1 no cumple ({criterio_1['peor_mm']:.3f} mm / {criterio_1['peor_deg']:.3f} grados "
                               f"en la peor posicion): la pose de una camara sola tiene un error que cambia con la vista (hipotesis b de B94); P36")


def b94_verdict(rest: dict, ext_segs: list[str], criterio_1: dict, consistencia: dict | None = None) -> dict:
    """El veredicto de B94 sobre los segmentos de reposo ya emparejados (`rest[seg]["tracks"]`,
    `rest[seg]["pairs"]`): `repeat_check` de S2_pos1 frente a S2_pos1_fin, `half_split` de cada
    tramo (los de los extrinsecos y la repetida), las distancias invariantes del diagnostico de
    consistencia si llega, y la regla (`b94_rule`)."""
    def ppp(seg):
        tr, pairs = rest[seg]["tracks"], rest[seg]["pairs"]
        return tr[REF].T_raw[pairs[:, 0]], tr[OTHER].T_raw[pairs[:, 1]]

    out: dict = {"posiciones_repetidas": list(B94_REPEAT), "repeticion": None, "mitades": {},
                 "umbrales": {"mm": THRESH["agreement_mm"], "deg": THRESH["agreement_deg"],
                              "volvio_mm": B94_RETURN_TOL["mm"], "volvio_deg": B94_RETURN_TOL["deg"]}}
    a, b = B94_REPEAT
    if a in rest and b in rest and len(rest[a]["pairs"]) >= 2 and len(rest[b]["pairs"]) >= 2:
        out["repeticion"] = ex.repeat_check(ppp(a), ppp(b), THRESH["agreement_mm"], THRESH["agreement_deg"])
    for seg in list(ext_segs) + ([b] if b in rest and b not in ext_segs else []):
        if seg in rest and len(rest[seg]["pairs"]) >= 4:
            h = ex.half_split(*ppp(seg))
            out["mitades"][seg] = {k: h[k] for k in ("n", "n_first", "n_second", "diff_mm", "diff_deg")}
    if out["mitades"]:
        out["mitades_peor_mm"] = float(max(h["diff_mm"] for h in out["mitades"].values()))
        out["mitades_peor_deg"] = float(max(h["diff_deg"] for h in out["mitades"].values()))
    if consistencia:
        out["distancias_max_diff_mm"] = consistencia.get("distancias_max_diff_mm")
    out["criterio_1_cumple"] = criterio_1.get("cumple")
    out["veredicto"], out["motivo"] = b94_rule(out["repeticion"], out["mitades"], criterio_1)
    return out


# ---------------------------------------------------------------------------
# El experimento
# ---------------------------------------------------------------------------

def run_experiment(data_dir: Path, intrinsics: dict[str, Path], sigma_px: dict[str, float] | None,
                   engines: tuple[str, ...], attempts: dict[str, str] | None = None,
                   timeout_s: float | None = None, log=print, anchor_tol_ms: float = ds.ANCHOR_TOL_MS) -> dict:
    """Todo el experimento. Devuelve `results` (lo que va a `resultados.json`, mas `series`
    para las graficas y `tiempos` para `tiempos.json`, que `main` separa)."""
    deadline = Deadline(timeout_s)
    data_dir = Path(data_dir)
    for e in engines:
        if e not in ENGINES_A:
            raise ValueError(f"motor {e!r}: en la parte A solo {ENGINES_A}; los gtsam_* son de la parte B")
    if not anchor_tol_ms > 0:
        raise ValueError(f"la tolerancia del ancla tiene que ser > 0 ms, no {anchor_tol_ms!r}")
    attempts = dict(attempts or {})
    results: dict = {"datos": data_dir.name, "motores": list(engines), "criterios": [], "avisos": [], "notas": [],
                     "comprobacion": {}, "segmentos_fuera": []}
    series: dict = {}
    timings: dict[str, list[float]] = {}
    tracks_by_seg: dict[str, dict[str, ds.CameraTrack]] = {}

    # 1. Cargar y comprobar.
    for seg, info in SEGMENTS.items():
        try:
            ds.segment_file(data_dir, seg, REF, attempts.get(seg))
        except FileNotFoundError:
            continue
        t0 = time.perf_counter()
        tracks = ds.load_segment(data_dir, seg, (REF, OTHER), attempts.get(seg))
        exp_s = ds.expected_duration(tracks[REF].meta)
        check = ds.check_segment(tracks, intrinsics, exp_s, occluded=info.get("covered"), anchor_tol_ms=anchor_tol_ms)
        check["files"] = {c: tracks[c].file for c in tracks}
        check["load_s"] = time.perf_counter() - t0
        results["comprobacion"][seg] = check
        tracks_by_seg[seg] = tracks
        log(f"[experimento] {seg}: {'ok' if check['ok'] else 'NO cumple'}; ancla {check['anchor_diff_ms']:.3f} ms, "
            f"solape {check['overlap_s']:.1f} s, pose " +
            " / ".join(f"{c} {100 * v:.1f} %" for c, v in check["fraction_with_pose"].items()) +
            (f"; motivos: {'; '.join(check['reasons'])}" if check["reasons"] else "") + f" ({check['load_s']:.1f} s)")
        if not check["ok"]:
            results["segmentos_fuera"].append(seg)
        deadline.check(f"la carga de {seg}")
    if not tracks_by_seg:
        raise FileNotFoundError(f"no hay ningun segmento conocido en {data_dir}")
    usable = {s: t for s, t in tracks_by_seg.items() if results["comprobacion"][s]["ok"]}
    rest_S2 = {s: {"tracks": t} for s, t in usable.items() if SEGMENTS[s].get("role") == "S2"}
    rest_S1 = {s: {"tracks": t} for s, t in usable.items() if SEGMENTS[s].get("role") == "S1"}
    rest_rep = {s: {"tracks": t} for s, t in usable.items() if SEGMENTS[s].get("role") == "S2_rep"}   # fase 2
    if "S1_reposo" in tracks_by_seg and "S1_reposo" not in usable:
        results["avisos"].append("S1_reposo no cumple la comprobacion: hay que grabar otra vez.")
    if sum(1 for s in SEGMENTS if SEGMENTS[s].get("role") == "S2" and s in tracks_by_seg and s not in usable) > 1:
        results["avisos"].append("Mas de una posicion de S2 no cumple la comprobacion: hay que grabar otra vez.")

    # 2. Parejas de cada segmento de reposo (la posicion repetida tambien: sigma_px y criterio 2).
    rest = {**rest_S1, **rest_S2, **rest_rep}
    for seg, r in rest.items():
        r["pairs"], r["tolerance_s"] = pairs_of(r["tracks"])

    # 3. Extrinsecos por Marker0 (P12 b) sobre las posiciones de S2; sin S2, sobre S1. La
    # posicion repetida (S2_pos1_fin) queda fuera: dentro, dejar pos1 fuera en la validacion
    # cruzada dejaria a su gemelo y el numero saldria optimista.
    ext_segs = [s for s in rest_S2 if len(rest_S2[s]["pairs"]) > 0] or [s for s in rest_S1 if len(rest_S1[s]["pairs"]) > 0]
    if not ext_segs:
        raise ValueError("ningun segmento de reposo usable con parejas: no hay extrinsecos")
    ppp = [(rest[s]["tracks"][REF].T_raw[rest[s]["pairs"][:, 0]],
            rest[s]["tracks"][OTHER].T_raw[rest[s]["pairs"][:, 1]]) for s in ext_segs]
    E = ex.from_marker_positions(ppp)
    T_ref_other = E["T_ref_other"]
    results["extrinsecos"] = {"T_ref_other": T_ref_other, "segmentos": ext_segs, "n_positions": E["n_positions"],
                              "spread_mm": E["spread_mm"], "spread_deg": E["spread_deg"], "angle_deg": E["angle_deg"],
                              "baseline_mm": float(np.linalg.norm(T_ref_other[:3, 3])),
                              "per_position": E["per_position"], "pairs_per_position": E["pairs_per_position"],
                              "origen": "S2" if ext_segs[0] in rest_S2 else "S1 (sin posiciones de S2 usables)"}
    if E["angle_deg"] < ANGLE_WARN_DEG:
        results["extrinsecos"]["aviso_angulo"] = (
            f"Las camaras estan casi paralelas (theta = {E['angle_deg']:.1f} grados < {ANGLE_WARN_DEG:.0f}): con este montaje el "
            "criterio 2 (30 %) no se puede cumplir por geometria (techo 29 % con ruido igual e independiente); dato para la estructura (P6).")
        results["avisos"].append(results["extrinsecos"]["aviso_angulo"])
    log(f"[experimento] extrinsecos de {len(ext_segs)} posiciones: theta {E['angle_deg']:.2f} grados, base "
        f"{results['extrinsecos']['baseline_mm']:.1f} mm, dispersion {E['spread_mm']:.3f} mm / {E['spread_deg']:.4f} grados")
    deadline.check("los extrinsecos")

    # 3b. Diagnostico de consistencia: ajuste conjunto (bundle), distancias invariantes y
    # residuo de cada vista sola.
    results["consistencia"] = consistency_diagnostics(rest, ext_segs, E["T_ref_other"], sigma_px, log)
    deadline.check("el diagnostico de consistencia")

    # 4. Criterio 1: validacion cruzada (P27).
    c1: dict = {"por_posicion": [], "nota": ""}
    if len(ppp) >= 2:
        for k, row in enumerate(ex.leave_one_out(ppp)):
            agr = row["agreement"]
            c1["por_posicion"].append({"segmento": ext_segs[k], **agr, "T_ref_other_others": row["T_ref_other"],
                                       "cumple": bool(agr["mean_mm"] < THRESH["agreement_mm"] and agr["mean_deg"] < THRESH["agreement_deg"])})
        worst_mm = max(r["mean_mm"] for r in c1["por_posicion"])
        worst_deg = max(r["mean_deg"] for r in c1["por_posicion"])
        c1.update({"peor_mm": worst_mm, "peor_deg": worst_deg,
                   "cumple": bool(worst_mm < THRESH["agreement_mm"] and worst_deg < THRESH["agreement_deg"]),
                   "min_parejas": int(min(r["n"] for r in c1["por_posicion"]))})
        results["criterios"].append(_criterion(
            "1", "Las camaras coinciden (peor posicion, gs2 llevada a gs1; validacion cruzada)",
            f"{worst_mm:.3f} mm / {worst_deg:.3f} grados", "< 0.5 mm y < 0.2 grados",
            "cumple" if c1["cumple"] else "no cumple",
            f"{len(ppp)} posiciones, >= {c1['min_parejas']} parejas cada una" + ("" if c1["min_parejas"] >= 2000 else " (P16 pedia >= 2000)")))
    else:
        c1["nota"] = "una sola posicion usable: sin validacion cruzada (el criterio 1 queda sin evaluar)"
        results["criterios"].append(_criterion("1", "Las camaras coinciden", None, "< 0.5 mm y < 0.2 grados", "sin evaluar", c1["nota"]))
    results["criterio_1"] = c1
    cons = results["consistencia"]
    if cons.get("bundle"):
        b = cons["bundle"]
        results["criterios"].append(_criterion(
            "1b", "Las camaras coinciden con los extrinsecos del ajuste conjunto (peor posicion, dejando una fuera)",
            f"{cons['loo_peor_mm']:.3f} mm / {cons['loo_peor_deg']:.3f} grados", "< 0.5 mm y < 0.2 grados",
            "cumple" if (cons["loo_peor_mm"] < THRESH["agreement_mm"] and cons["loo_peor_deg"] < THRESH["agreement_deg"]) else "no cumple",
            "T_gs1<-gs2 y la pose de cada posicion ajustadas a la vez sobre las esquinas medias"))
        results["criterios"].append(_criterion(
            "rigidez", "Las posiciones de Marker0 caben en dos camaras rigidas: RMS del ajuste conjunto frente al de cada vista sola",
            f"{b['rms_px']:.3f} px (vista sola <= {cons['vista_unica_max_rms_px']:.3f} px); distancias entre posiciones gs1 - gs2 hasta {cons['distancias_max_diff_mm']:.2f} mm",
            "del orden de la vista sola", "informativo",
            "si el conjunto no cabe y cada vista si, o una camara se movio entre posiciones o la pose de un marker solo tiene un error que cambia con la vista (inclinacion-profundidad)"))

    # 4b. El veredicto de B94 (fase 2): la posicion repetida, las mitades y la regla.
    results["b94"] = b94_verdict(rest, ext_segs, c1, results["consistencia"])
    log(f"[experimento] B94: {results['b94']['veredicto']} ({results['b94']['motivo']})")
    deadline.check("el veredicto de B94")

    # 5. sigma_px por camara, ajustado en S2 (y en la posicion repetida; no en S1); si no hay S2, en S1 y se dice.
    fit_on = {**rest_S2, **rest_rep} if rest_S2 else rest_S1
    sig: dict = {}
    for cam in (REF, OTHER):
        if sigma_px and cam in sigma_px:
            sig[cam] = {"sigma_px": float(sigma_px[cam]), "sigma_px_detrended": None, "segmentos": [], "origen": "dado por --sigma-px"}
        else:
            sig[cam] = fit_sigma_px(fit_on, cam)
            if not rest_S2:
                sig[cam]["origen"] += " en S1 (sin S2: el criterio 2 en S1 se pesa con el mismo dato)"
        if sig[cam]["sigma_px"] is None:
            raise ValueError(f"no se pudo ajustar sigma_px de {cam}")
    results["sigma_px"] = sig
    sigma = {c: sig[c]["sigma_px"] for c in sig}
    log(f"[experimento] sigma_px: " + ", ".join(f"{c} {v:.4f}" for c, v in sigma.items()))
    deadline.check("sigma_px")

    # 6. Criterio 2: la fusion por instante en cada segmento de reposo.
    c2: dict = {"por_segmento": []}
    for seg, r in rest.items():
        tr, pairs = r["tracks"], r["pairs"]
        if len(pairs) < 10:
            results["notas"].append(f"{seg}: solo {len(pairs)} parejas; fuera del criterio 2")
            continue
        a, b = tr[REF], tr[OTHER]
        P1 = a.positions[pairs[:, 0]]
        T2 = ex.apply_extrinsics(T_ref_other, b.T_raw[pairs[:, 1]])
        P2 = T2[:, :3, 3]
        tpair = 0.5 * (a.t[pairs[:, 0]] + b.t[pairs[:, 1]])
        cams = {REF: mt.rest_sd(P1, tpair), OTHER: mt.rest_sd(P2, tpair)}
        Tm1 = g.mean_pose(a.T_raw[pairs[:, 0]])
        Tm2 = g.mean_pose(b.T_raw[pairs[:, 1]])
        cov1 = g.position_covariance(Tm1, g.pose_covariance(Tm1, a.size_mm, a.K, a.dist, sigma[REF]))
        cov2 = g.position_covariance(T_ref_other @ Tm2, g.pose_covariance(Tm2, b.size_mm, b.K, b.dist, sigma[OTHER]))
        pred = mt.predicted_reduction(cov1, cov2)
        pred.pop("cov_fused", None)
        fused, rms_fused = fused_rest(tr, pairs, T_ref_other, sigma, engines, timings)
        agr_seg = ex.agreement_stats(a.T_raw[pairs[:, 0]], T2)
        row = {"segmento": seg, "parejas": int(len(pairs)), "tolerancia_ms": r["tolerance_s"] * 1000.0,
               "camaras": cams, "mejor": min(cams, key=lambda c: cams[c]["sd_3d_mm"]), "predicha": pred, "motores": {},
               "discrepancia_gs1_gs2_mm": agr_seg["mean_mm"], "discrepancia_gs1_gs2_deg": agr_seg["mean_deg"]}
        series[seg] = {"t": tpair, "positions": {REF: P1, OTHER: P2, **fused}}
        for e, P in fused.items():
            sd = mt.rest_sd(P, tpair)
            m = mt.measured_reduction({c: cams[c]["sd_3d_mm"] for c in cams}, sd["sd_3d_mm"])
            md = mt.measured_reduction({c: cams[c]["sd_3d_detrended_mm"] for c in cams}, sd["sd_3d_detrended_mm"])
            row["motores"][e] = {**sd, "reduction": m["reduction"], "reduction_detrended": md["reduction"],
                                 "parte_comun_pt": float(pred["reduction_3d"] - m["reduction"]),
                                 "rms_px_median": rms_fused.get(e),
                                 "cumple": bool(m["reduction"] >= THRESH["reduction"])}
        c2["por_segmento"].append(row)
        log(f"[experimento] {seg}: sd 3D cruda " + " / ".join(f"{c} {cams[c]['sd_3d_mm']:.4f}" for c in cams) +
            f" mm; predicha {100 * pred['reduction_3d']:.1f} %; " +
            "; ".join(f"{e} {100 * row['motores'][e]['reduction']:.1f} %" for e in row["motores"]))
        deadline.check(f"el criterio 2 en {seg}")
    results["criterio_2"] = c2
    s1 = next((r for r in c2["por_segmento"] if r["segmento"] == "S1_reposo"), None)
    results["segmento_reposo"] = "S1_reposo" if s1 else (c2["por_segmento"][0]["segmento"] if c2["por_segmento"] else None)
    verdict_row = s1 or (c2["por_segmento"][0] if c2["por_segmento"] else None)
    for e in engines:
        if verdict_row is None or e not in verdict_row["motores"]:
            results["criterios"].append(_criterion("2", f"La fusion baja el jitter ({e})", None, ">= 30 %", "sin evaluar", "sin segmento de reposo usable"))
            continue
        m = verdict_row["motores"][e]
        results["criterios"].append(_criterion(
            "2", f"La fusion baja la sd 3D en reposo ({e}, {verdict_row['segmento']})",
            f"{100 * m['reduction']:.1f} % (predicha {100 * verdict_row['predicha']['reduction_3d']:.1f} %)",
            ">= 30 %", "cumple" if m["cumple"] else "no cumple",
            f"mejor camara {verdict_row['mejor']} {verdict_row['camaras'][verdict_row['mejor']]['sd_3d_mm']:.4f} mm; fusionada {m['sd_3d_mm']:.4f} mm; sin deriva {100 * m['reduction_detrended']:.1f} %"))

    # 7. Criterio 3 por instante en S3.
    c3: dict = {"por_segmento": []}
    for seg, tr in usable.items():
        if SEGMENTS[seg]["kind"] != "occlusion":
            continue
        covered = SEGMENTS[seg]["covered"]
        events = mt.occlusion_events(tr[covered])
        row = {"segmento": seg, "tapada": covered, "eventos": [[float(a), float(b)] for a, b in events], "motores": {}}
        t_ref0 = min(tr[REF].t[0], tr[OTHER].t[0])
        for e in engines:
            t, P = fused_timeline(tr, T_ref_other, sigma, e, timings)
            j = mt.jumps(t, P, events)
            for trn in j["transitions"]:
                trn["t_rel_s"] = trn["t"] - t_ref0
            j["cumple"] = bool(math.isfinite(j["max_jump_mm"]) and j["max_jump_mm"] <= THRESH["jump_mm"])
            row["motores"][e] = j
            series.setdefault(seg, {"t": t, "positions": {}, "events": events})
            if e == engines[0]:
                series[seg]["positions"] = {e: P}
                # las camaras solas, en la misma linea de tiempo (NaN donde no ven)
                for cam in (REF, OTHER):
                    Pc = np.full((len(t), 3), np.nan)
                    tc = tr[cam].t[tr[cam].valid]
                    pc = (ex.apply_extrinsics(T_ref_other, tr[cam].T_raw[tr[cam].valid])[:, :3, 3] if cam == OTHER
                          else tr[cam].positions[tr[cam].valid])
                    idx = np.searchsorted(tc, t)
                    idx = np.clip(idx, 0, len(tc) - 1)
                    near = np.abs(tc[idx] - t) <= 0.5 * tr[cam].period_s
                    Pc[near] = pc[idx[near]]
                    series[seg]["positions"][cam] = Pc
            else:
                series[seg]["positions"][e] = P
        c3["por_segmento"].append(row)
        log(f"[experimento] {seg}: {len(events)} tramo(s) tapado(s); " +
            "; ".join(f"{e} salto max {row['motores'][e]['max_jump_mm']:.3f} mm, paso max {row['motores'][e]['max_step_mm']:.3f} mm"
                      for e in row["motores"]))
        deadline.check(f"el criterio 3 en {seg}")
    results["criterio_3"] = c3
    for e in engines:
        vals = [r["motores"][e]["max_jump_mm"] for r in c3["por_segmento"] if e in r["motores"] and math.isfinite(r["motores"][e]["max_jump_mm"])]
        n_ev = sum(len(r["eventos"]) for r in c3["por_segmento"])
        if not vals:
            results["criterios"].append(_criterion("3", f"Aguanta que se tape una camara ({e})", None, "<= 0.5 mm", "sin evaluar", "sin S3 usable o sin tramos tapados"))
        else:
            results["criterios"].append(_criterion(
                "3", f"Salto al tapar y destapar, por instante ({e})", f"{max(vals):.3f} mm", "<= 0.5 mm",
                "cumple" if max(vals) <= THRESH["jump_mm"] else "no cumple",
                f"{n_ev} tramo(s) tapado(s) en {len(c3['por_segmento'])} segmento(s); por instante el salto es la diferencia entre la fusion y la camara que queda: el numero que cuenta es el de la parte B (factor de movimiento)"))

    # 8. El desfase (S4).
    d: dict = {}
    s4 = next((s for s in tracks_by_seg if SEGMENTS[s]["kind"] == "motion"), None)
    if s4 is not None:
        d = pr.estimate_offset(tracks_by_seg[s4][REF], tracks_by_seg[s4][OTHER], T_ref_other, align="rigid")
        d["sin_alinear"] = pr.estimate_offset(tracks_by_seg[s4][REF], tracks_by_seg[s4][OTHER], T_ref_other, align="none")
        d["sin_alinear"].pop("curve", None)
        d["segmento"] = s4
        d["informativo"] = s4 not in usable
        estado = "informativo" if d["informativo"] else ("cumple" if d["ok"] else "sin evaluar")
        if not d["ok"]:
            estado = "sin evaluar"
        results["criterios"].append(_criterion(
            "delta", "Desfase entre camaras (P13), hora de gs2 + delta", f"{d['offset_ms']:.2f} ms" if d.get("offset_ms") is not None else None,
            "|delta| <= 2 ms sin corregir (P13)", estado,
            (f"{s4} no cumple la comprobacion (pose {100 * results['comprobacion'][s4]['fraction_with_pose'][OTHER]:.1f} % en gs2): el numero es informativo. " if d["informativo"] else "") + (d.get("note") or "")))
        log(f"[experimento] desfase: {d.get('offset_ms')} ms ({d.get('note') or 'ok'})")
    else:
        results["criterios"].append(_criterion("delta", "Desfase entre camaras (P13)", None, "—", "sin evaluar", "S4 no se grabo"))
    results["desfase"] = d

    # 9. La otra solucion de IPPE (dato para P24).
    results["ippe_otra_solucion"] = {s: {c: dict(tr[c].excluded) for c in tr} for s, tr in tracks_by_seg.items()}
    resc = sum(v["rescatables_por_la_otra_solucion"] for cams in results["ippe_otra_solucion"].values() for v in cams.values())
    inval = sum(v["pose_invalida"] for cams in results["ippe_otra_solucion"].values() for v in cams.values())
    results["criterios"].append(_criterion("IPPE", "Medidas que solo se salvan con la otra solucion de IPPE", f"{resc} de {inval} con z <= 0",
                                           "—", "informativo", "dato para P24 (si viajan las dos soluciones)"))

    # 10. Lo que se uso (fase 2) y los tiempos (aparte del JSON reproducible).
    results["tolerancia_ancla_ms"] = float(anchor_tol_ms)
    results["tiempos"] = {"por_motor": {e: {"n": len(ms), **timing_stats(ms)} for e, ms in timings.items()},
                          "total_s": deadline.elapsed(), "carga_s": {s: results["comprobacion"][s]["load_s"] for s in results["comprobacion"]}}
    results["series"] = series
    return results


def _split_results(results: dict) -> tuple[dict, dict, dict]:
    """`(reproducible, tiempos, series)`: lo que va a cada archivo."""
    series = results.pop("series", {})
    tiempos = results.pop("tiempos", {})
    rep = dict(results)
    for seg in rep.get("comprobacion", {}).values():
        seg.pop("load_s", None)
    return rep, tiempos, series


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cam_path(texto: str) -> tuple[str, Path]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera CAMARA=RUTA, no {texto!r}")
    c, r = texto.split("=", 1)
    return c.strip(), Path(r.strip())


def _cam_float(texto: str) -> tuple[str, float]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera CAMARA=VALOR, no {texto!r}")
    c, v = texto.split("=", 1)
    return c.strip(), float(v)


def _seg_attempt(texto: str) -> tuple[str, str]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera SEGMENTO=rN, no {texto!r}")
    s, a = texto.split("=", 1)
    return s.strip(), a.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="El experimento fuera de linea de las dos camaras (meta 006, fase 1, parte A).")
    ap.add_argument("--datos", required=True, type=Path, help="Carpeta con <segmento>_<camara>.npz.")
    ap.add_argument("--intrinsecos", required=True, nargs="+", type=_cam_path, metavar="CAM=YML",
                    help="gs1=<yml> gs2=<yml>: los .yml de data/ con que se grabo (se comprueba el sha256).")
    ap.add_argument("--salida", required=True, type=Path, help="Carpeta nueva (no se pisa).")
    ap.add_argument("--motores", nargs="+", default=list(ENGINES_A), choices=list(ENGINES_A) + list(ENGINES_B))
    ap.add_argument("--sigma-px", nargs="*", type=_cam_float, default=[], metavar="CAM=PX",
                    help="Fija sigma_px en vez de ajustarlo (opcional).")
    ap.add_argument("--intento", nargs="*", type=_seg_attempt, default=[], metavar="SEG=rN",
                    help="Que intento usar de un segmento (por defecto, el ultimo).")
    ap.add_argument("--timeout", required=True, type=float, help="Tope en segundos (principio 9).")
    ap.add_argument("--tolerancia-ancla-ms", type=float, default=ds.ANCHOR_TOL_MS,
                    help=f"Tolerancia del ancla de reloj entre los dos .npz (defecto {ds.ANCHOR_TOL_MS:g}; "
                         f"20 para las grabaciones del PC, donde t_start va a pasos de 15.6 ms).")
    args = ap.parse_args(argv)
    if not args.tolerancia_ancla_ms > 0:
        print(f"[experimento] --tolerancia-ancla-ms tiene que ser > 0, no {args.tolerancia_ancla_ms}", file=sys.stderr)
        return 2

    intr = dict(args.intrinsecos)
    for cam in (REF, OTHER):
        if cam not in intr or not intr[cam].is_file():
            print(f"[experimento] faltan los intrinsecos de {cam} (--intrinsecos {cam}=<yml>)", file=sys.stderr)
            return 2
    if args.salida.exists():
        print(f"[experimento] la salida ya existe, no se pisa: {args.salida}", file=sys.stderr)
        return 2
    if not args.datos.is_dir():
        print(f"[experimento] no existe la carpeta de datos: {args.datos}", file=sys.stderr)
        return 2
    try:
        results = run_experiment(args.datos, intr, dict(args.sigma_px) or None, tuple(args.motores),
                                 attempts=dict(args.intento), timeout_s=args.timeout,
                                 anchor_tol_ms=args.tolerancia_ancla_ms)
    except TimeoutError as e:
        print(f"[experimento] {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"[experimento] ERROR: {e}", file=sys.stderr)
        return 2
    rep, tiempos, series = _split_results(results)
    rep["titulo"] = "Meta 006 · Fase 1 · El experimento fuera de linea de las dos camaras (parte A, sin gtsam)"
    rep["subtitulo"] = (f"Datos: {args.datos}; motores: {', '.join(args.motores)}; "
                        f"segmentos fuera: {', '.join(rep['segmentos_fuera']) or 'ninguno'}.")
    args.salida.mkdir(parents=True, exist_ok=False)
    (args.salida / "resultados.json").write_text(json.dumps(_jsonable(rep), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.salida / "tiempos.json").write_text(json.dumps(_jsonable({"tiempos": tiempos, "fecha_local": time.strftime("%Y-%m-%d %H:%M:%S")}),
                                                         indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rep["tiempos"] = tiempos
    figs = rp.figures_for(rep, series)
    rp.write_report(rep, figs, rp.mermaid_diagrams(tuple(args.motores)), args.salida / "informe.html")
    print("[experimento] criterios:")
    for c in rep["criterios"]:
        print(f"  {c['id']:>4}  {c['estado']:<12} {c['valor'] if c['valor'] is not None else '—':<36} {c['nombre']}")
    print(f"[experimento] B94: {rep['b94']['veredicto']}: {rep['b94']['motivo']}")
    print(f"[experimento] informe: {args.salida / 'informe.html'} ({tiempos.get('total_s', 0):.1f} s)")
    return 1 if rep["segmentos_fuera"] else 0


if __name__ == "__main__":
    sys.exit(main())
