r"""El ejemplo resuelto de deteccion -> pose sobre un frame grabado (meta 004, fase 2).

Sigue un frame de una grabacion de `python -m tracker --record` (el `.npz` de
`diagnostics/pose_log.py` y uno de sus PNG en gris) de principio a fin, con el
mismo codigo que corre el tracker, y deja cada numero a la vista:

1. detecta en el PNG con el detector del perfil (`vision.detection`) y compara
   las esquinas con las que el tracker grabo en vivo (px);
2. toma K y dist de la grabacion y dice si son los del `.yml` del perfil
   (sha256 del archivo y valores);
3. la pose cruda con IPPE_SQUARE (`vision.pose.estimate_single_pose`), su
   rotacion 3x3, la reproyeccion de las 4 esquinas (`cv2.projectPoints`, px por
   esquina) y la proyeccion pinhole del centro, con y sin distorsion;
4. la comprobacion a mano de Z (fx * lado_mm / lado_px) y la inclinacion del marker;
5. la pose filtrada como la hace el tracker: `vision.tracking.MarkerTracker
   .process_corners` sobre las esquinas grabadas de los frames 0..frame-1 con
   sus tiempos, y la de este frame con las detectadas;
6. la 4x4 (`vision.pose.rvec_tvec_to_matrix`) frente a la que se envio en vivo
   (mm y grados), y en float32, que es como la guarda pyigtl;
7. con `--alt-size-mm`, la pose con otro tamano de marker y el cociente de
   escala (B55: las mismas esquinas con un lado mayor dan una t proporcional y
   la misma rotacion).

`format_markdown` escribe el bloque de `docs/ARCHITECTURE.md` §9.3 (texto
determinista, decimales fijos); `tests/test_como_funciona.py` comprueba que el
bloque del documento es esa salida. `draw_example` dibuja la figura: esquinas
numeradas c0..c3, las reproyectadas y los ejes (lado/2, como
`tracker.draw_poses`), recortada alrededor del marker.

Sin camara ni red: solo lee `tests/data/`. Desde codigo\, con el venv y los
argumentos explicitos (principio 7); no pisa una salida que ya existe:

    python -m diagnostics.explain_pose --dataset tests\data\marker0_gs1.npz ^
        --frames-dir tests\data\marker0_gs1_frames --frame 480 ^
        --config profiles\tracker_config_gs1.yaml --alt-size-mm 98.6 ^
        --output-markdown "..\Claude outputs\fases\004\ejemplo_gs1_480.md" ^
        --output-image ..\docs\img\004\marker0_gs1_frame_00480.png --crop-px 320

Context7 (2026-10-26, OpenCV 4.13; instalado 4.11): `projectPoints(obj, rvec,
tvec, K, dist)` -> `(imagePoints, jacobian)`; `drawFrameAxes(img, K, dist, rvec,
tvec, length)`; `Rodrigues(rvec)` -> `(R, jacobian)`. pyigtl 0.3.1:
`TransformMessage(matrix, ...)` guarda la 4x4 como `np.float32`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

import profiles
from diagnostics.pose_log import load_recording
from vision.detection import create_detector, detect
from vision.pose import build_object_points, estimate_single_pose, rvec_tvec_to_matrix
from vision.tracking import MarkerTracker

DEFAULT_CROP_PX = 320
MARKER_NAME = "Marker0"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _angle_deg(Ra: np.ndarray, Rb: np.ndarray) -> float:
    """Angulo de Ra.T @ Rb por atan2 (estable cerca de 0), en grados."""
    D = Ra.T @ Rb
    s = 0.5 * np.linalg.norm([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]])
    c = 0.5 * (np.trace(D) - 1.0)
    return float(np.degrees(np.arctan2(s, c)))


def _read_yml_intrinsics(path: Path) -> tuple[np.ndarray, np.ndarray]:
    fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"No se pudo abrir el .yml de intrinsecos: {path}")
    try:
        K = np.asarray(fs.getNode("camera_matrix").mat(), dtype=np.float64)
        dist = np.asarray(fs.getNode("distortion_coefficients").mat(), dtype=np.float64).flatten()
    finally:
        fs.release()
    return K, dist


def _pinhole(K: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """u = fx*X/Z + cx, v = fy*Y/Z + cy, sin distorsion."""
    X, Y, Z = (float(v) for v in np.asarray(p).flatten())
    return float(K[0, 0] * X / Z + K[0, 2]), float(K[1, 1] * Y / Z + K[1, 2])


def explain_frame(dataset: Path, frames_dir: Path, frame: int, profile: Path,
                  alt_size_mm: float | None = None, name: str = MARKER_NAME) -> dict:
    """El ejemplo de un frame, de principio a fin (ver el docstring del modulo).

    Aborta con un mensaje claro si falta el PNG, si el frame no tiene una
    deteccion y un envio de `name` en la grabacion, o si el perfil no define el
    marker (principio 7). Devuelve un dict de numeros de Python (vale para JSON).
    """
    dataset, frames_dir, profile = Path(dataset), Path(frames_dir), Path(profile)
    png = frames_dir / f"frame_{int(frame):05d}.png"
    if not png.is_file():
        raise FileNotFoundError(f"No existe el frame guardado: {png}")
    rec = load_recording(dataset)
    n_frames = len(rec["timestamps"])
    if not 0 <= int(frame) < n_frames:
        raise ValueError(f"frame {frame} fuera de la grabacion ({n_frames} frames)")
    cfg = profiles.load(str(profile))
    markers = [m for m in cfg["markers"].get("list", []) or [] if str(m["name"]) == name]
    if len(markers) != 1:
        raise ValueError(f"{profile.name}: tiene que haber un solo marker '{name}' en markers.list")
    marker = markers[0]
    mid, size_mm = int(marker["id"]), float(marker["size_mm"])

    # 1. Deteccion sobre el PNG, con el detector y la lista blanca del perfil.
    gray = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
    if gray is None or gray.ndim != 2:
        raise ValueError(f"{png.name}: no es una imagen en gris")
    detector = create_detector(cfg["markers"])
    corners, ids = detect(detector, gray, {mid})
    found = [] if ids is None else ids.flatten().tolist()
    if found.count(mid) != 1:
        raise ValueError(f"{png.name}: el detector vio {found} y hacia falta exactamente un ID {mid}")
    c_det = np.asarray(corners[found.index(mid)], dtype=np.float32).reshape(4, 2)
    off = rec["frame_offsets"]
    a, b = int(off[frame]), int(off[frame + 1])
    rec_ids = rec["marker_ids"][a:b].tolist()
    if rec_ids.count(mid) != 1:
        raise ValueError(f"frame {frame}: la grabacion tiene {rec_ids}, hacia falta un ID {mid}")
    c_rec = rec["corners_2d"][a + rec_ids.index(mid)].astype(np.float32)
    sides_px = [float(np.linalg.norm(c_det[k].astype(np.float64) - c_det[(k + 1) % 4])) for k in range(4)]

    # 2. K y dist: los de la grabacion, contrastados con el .yml del perfil.
    K, dist = np.asarray(rec["K"], dtype=np.float64), np.asarray(rec["dist"], dtype=np.float64).flatten()
    yml = Path(cfg["camera"]["calibration_file"])
    K_yml, dist_yml = _read_yml_intrinsics(yml)
    yml_sha = _sha256(yml)

    # 3. Pose cruda y su reproyeccion.
    pose = estimate_single_pose(c_det, size_mm, K, dist)
    if pose is None:
        raise ValueError(f"frame {frame}: IPPE_SQUARE no dio una pose con z > 0")
    rvec, tvec = pose
    R, _ = cv2.Rodrigues(rvec)
    obj = build_object_points(size_mm)
    proj, _ = cv2.projectPoints(obj, rvec, tvec, K, dist)
    proj = proj.reshape(4, 2).astype(np.float64)
    err_px = np.linalg.norm(proj - c_det.astype(np.float64), axis=1)
    center_dist, _ = cv2.projectPoints(np.zeros((1, 3), np.float32), rvec, tvec, K, dist)
    center_dist = center_dist.reshape(2).astype(np.float64)
    center_pinhole = _pinhole(K, tvec)
    centroid = c_det.astype(np.float64).mean(axis=0)

    # 4. A mano: Z por el tamano en px, y la inclinacion del marker.
    side_mean = float(np.mean(sides_px))
    z_hand = float(K[0, 0] * size_mm / side_mean)
    tilt_deg = float(np.degrees(np.arccos(min(1.0, abs(float(R[2, 2]))))))

    # 5. La pose filtrada, como el tracker: los frames anteriores con lo grabado.
    tracker = MarkerTracker(cfg["markers"], cfg.get("filtering"))
    ids_r, cr, ts = rec["marker_ids"], rec["corners_2d"], rec["timestamps"]
    for i in range(int(frame)):
        dets = [(int(ids_r[j]), cr[j].reshape(1, 4, 2)) for j in range(int(off[i]), int(off[i + 1]))]
        tracker.process_corners(dets, float(ts[i]), K, dist)
    poses = [p for p in tracker.process_corners([(mid, c_det.reshape(1, 4, 2))], float(ts[frame]), K, dist)
             if p.name == name]
    if len(poses) != 1:
        raise ValueError(f"frame {frame}: el paso del tracker no dio la pose de {name}")
    M = poses[0].matrix
    t_filt = poses[0].tvec.flatten()

    # 6. Frente a lo enviado en vivo, y en float32.
    sent = [j for j in np.flatnonzero(rec["sent_frame"] == frame) if str(rec["sent_name"][j]) == name]
    if len(sent) != 1:
        raise ValueError(f"frame {frame}: la grabacion tiene {len(sent)} envios de {name}, hacia falta 1")
    M_live = np.asarray(rec["sent_M"][sent[0]], dtype=np.float64)
    M32 = M.astype(np.float32)
    dt = float(ts[frame] - ts[frame - 1]) if frame > 0 else float("nan")

    out = {
        "dataset": dataset.name, "png": png.name, "profile": profile.name,
        "frame": int(frame), "frames_in_recording": int(n_frames),
        "image_size": [int(gray.shape[1]), int(gray.shape[0])],
        "marker": {"id": mid, "name": name, "size_mm": size_mm,
                   "dictionary": str(cfg["markers"]["dictionary"])},
        "detection": {"ids_detected": found, "corners_px": c_det.astype(np.float64).tolist(),
                      "corners_recorded_px": c_rec.astype(np.float64).tolist(),
                      "max_diff_px": float(np.max(np.abs(c_det.astype(np.float64) - c_rec))),
                      "sides_px": sides_px, "side_mean_px": side_mean,
                      "centroid_px": centroid.tolist()},
        "intrinsics": {"K": K.tolist(), "dist": dist.tolist(),
                       "fx": float(K[0, 0]), "fy": float(K[1, 1]), "cx": float(K[0, 2]), "cy": float(K[1, 2]),
                       "calibration_file": yml.name, "yml_sha256": yml_sha,
                       "recording_sha256": str(rec["metadata"].get("calibration_sha256")),
                       "sha_matches": yml_sha == str(rec["metadata"].get("calibration_sha256")),
                       "max_diff_K_vs_yml": float(np.max(np.abs(K - K_yml))),
                       "max_diff_dist_vs_yml": float(np.max(np.abs(dist - dist_yml)))},
        "raw_pose": {"object_points_mm": obj.astype(np.float64).tolist(),
                     "rvec_rad": rvec.flatten().tolist(), "rvec_deg": float(np.degrees(np.linalg.norm(rvec))),
                     "tvec_mm": tvec.flatten().tolist(), "R": R.tolist(),
                     "reprojected_px": proj.tolist(), "reproj_err_px": err_px.tolist(),
                     "reproj_rms_px": float(np.sqrt(np.mean(err_px ** 2))), "reproj_max_px": float(err_px.max()),
                     "center_pinhole_px": list(center_pinhole), "center_projected_px": center_dist.tolist(),
                     "tilt_deg": tilt_deg},
        "hand_check": {"z_from_side_mm": z_hand, "z_pose_mm": float(tvec[2, 0]),
                       "diff_mm": z_hand - float(tvec[2, 0])},
        "filter": {"enabled": bool(tracker.filters), "min_cutoff": cfg["filtering"].get("min_cutoff"),
                   "beta": cfg["filtering"].get("beta"), "frames_before": int(frame),
                   "t_s": float(ts[frame]), "dt_ms": dt * 1000.0,
                   "tvec_filtered_mm": t_filt.tolist(),
                   "raw_minus_filtered_mm": (tvec.flatten() - t_filt).tolist(),
                   "shift_mm": float(np.linalg.norm(tvec.flatten() - t_filt))},
        "matrix": {"M": M.tolist(), "M_float32": M32.astype(np.float64).tolist(),
                   "float32_max_diff_mm": float(np.max(np.abs(M32.astype(np.float64) - M))),
                   "device_name": f"{name}ToTracker",
                   "live_diff_translation_mm": float(np.linalg.norm(M[:3, 3] - M_live[:3, 3])),
                   "live_diff_rotation_deg": _angle_deg(M_live[:3, :3], M[:3, :3])},
    }
    if alt_size_mm is not None:
        alt = estimate_single_pose(c_det, float(alt_size_mm), K, dist)
        if alt is None:
            raise ValueError(f"con {alt_size_mm} mm IPPE_SQUARE no dio una pose con z > 0")
        rvec_a, tvec_a = alt
        R_a, _ = cv2.Rodrigues(rvec_a)
        ratio = tvec_a.flatten() / tvec.flatten()
        expected = float(alt_size_mm) / size_mm
        out["alt_size"] = {"size_mm": float(alt_size_mm), "tvec_mm": tvec_a.flatten().tolist(),
                           "ratio": ratio.tolist(), "expected_ratio": expected,
                           "max_rel_err": float(np.max(np.abs(ratio / expected - 1.0))),
                           "rotation_diff_deg": _angle_deg(R, R_a)}
    return out


def _row(label: str, xy, dec: int = 3) -> str:
    return f"| {label} | {xy[0]:.{dec}f} | {xy[1]:.{dec}f} |"


def _mat(M, dec: int) -> list[str]:
    return ["    " + "  ".join(f"{v:{dec + 6}.{dec}f}" for v in row) for row in M]


def format_markdown(r: dict) -> str:
    """El bloque de §9.3: texto determinista con decimales fijos, a partir de `explain_frame`."""
    m, d, k, p, h, f, x = (r["marker"], r["detection"], r["intrinsics"], r["raw_pose"],
                           r["hand_check"], r["filter"], r["matrix"])
    w, hh = r["image_size"]
    L: list[str] = []
    L.append(f"_Generado por `diagnostics/explain_pose.py:format_markdown` sobre `{r['png']}` (el frame "
             f"{r['frame']} de {r['frames_in_recording']} de `{r['dataset']}`, grabado en vivo con "
             f"`profiles/{r['profile']}`). No se edita a mano: `tests/test_como_funciona.py` comprueba que es "
             f"la salida del script, y `tests/test_explain_pose.py` repite lo mismo sobre los 3 frames de cada cámara._")
    L.append("")
    L.append(f"**1 · El frame.** `{r['png']}`: {w}×{hh} en gris, tal como lo ve `vision/detection.py:detect` "
             f"(el tracker pasa a gris el frame BGR de la cámara en `tracker.py:main`). El marker es "
             f"`{m['name']}`, ID {m['id']} del diccionario `{m['dictionary']}`, de {m['size_mm']:.1f} mm de lado "
             f"(`profiles/{r['profile']}`, `markers.list`).")
    L.append("")
    c0 = d["corners_px"][0]
    where = (("abajo" if c0[1] > d["centroid_px"][1] else "arriba") + " a la "
             + ("derecha" if c0[0] > d["centroid_px"][0] else "izquierda"))
    L.append(f"**2 · Las esquinas.** El detector del perfil (`vision/detection.py:create_detector`, con refinado "
             f"subpíxel) ve el ID {m['id']} y da 4 esquinas en píxeles, en el orden de §7 (`c0=TL c1=TR c2=BR "
             f"c3=BL`: la esquina arriba-izquierda del dibujo del marker y después en el sentido de las agujas del "
             f"reloj). Ese orden es el del marker, no el de la imagen: aquí c0 cae {where} del centro porque el "
             f"marker está girado en la imagen. Comparadas con las que el tracker grabó en vivo para este frame, "
             f"la diferencia máxima es **{d['max_diff_px']:.6f} px**.")
    L.append("")
    L.append("| Esquina | u (px) | v (px) |")
    L.append("|---|---|---|")
    for i, c in enumerate(d["corners_px"]):
        L.append(_row(f"c{i}", c))
    L.append("")
    sides = ", ".join(f"{s:.2f}" for s in d["sides_px"])
    L.append(f"Lados en la imagen (c0c1, c1c2, c2c3, c3c0): {sides} px; media {d['side_mean_px']:.2f} px. "
             f"Centro de las cuatro esquinas: ({d['centroid_px'][0]:.2f}, {d['centroid_px'][1]:.2f}) px.")
    L.append("")
    L.append(f"**3 · K y dist.** Los intrínsecos de la cámara son los de `data/{k['calibration_file']}` "
             f"(sha256 `{k['yml_sha256'][:12]}…`; la grabación guardó el mismo sha: "
             f"{'sí' if k['sha_matches'] else 'NO'}; diferencia máxima de K {k['max_diff_K_vs_yml']:.1e} y de dist "
             f"{k['max_diff_dist_vs_yml']:.1e}). fx = {k['fx']:.3f}, fy = {k['fy']:.3f} px; "
             f"cx = {k['cx']:.3f}, cy = {k['cy']:.3f} px; dist (k1, k2, p1, p2, k3) = "
             + ", ".join(f"{v:.6f}" for v in k["dist"]) + ".")
    L.append("")
    L.append(f"**4 · La pose cruda.** `vision/pose.py:estimate_single_pose` llama a `solvePnP` con "
             f"`SOLVEPNP_IPPE_SQUARE`: las 4 esquinas en px, las 4 esquinas del modelo en mm "
             f"(`vision/pose.py:build_object_points`: (±{m['size_mm'] / 2:.0f}, ±{m['size_mm'] / 2:.0f}, 0)), K y dist. "
             f"Sale rvec = ({', '.join(f'{v:.6f}' for v in p['rvec_rad'])}) rad "
             f"(un giro de {p['rvec_deg']:.2f}° alrededor de ese eje) y "
             f"**tvec = ({', '.join(f'{v:.3f}' for v in p['tvec_mm'])}) mm**: el centro del marker está a "
             f"{p['tvec_mm'][2]:.1f} mm de la cámara, {p['tvec_mm'][0]:.1f} mm a la derecha y "
             f"{p['tvec_mm'][1]:.1f} mm hacia abajo del eje óptico (§7). `Rodrigues` pasa rvec a la rotación R:")
    L.append("")
    L.append("```")
    L.extend(_mat(p["R"], 6))
    L.append("```")
    L.append("")
    L.append(f"R[2,2] = {p['R'][2][2]:.4f} < 0: el marker mira hacia la cámara, inclinado {p['tilt_deg']:.1f}° "
             f"respecto al eje óptico. z = {p['tvec_mm'][2]:.1f} > 0: la solución es la de delante de la cámara "
             f"(la otra de las dos de IPPE se descarta).")
    L.append("")
    L.append(f"**Comprobación: la pose devuelve las esquinas.** Proyectando las 4 esquinas del modelo con esa "
             f"pose, K y dist (`projectPoints`) se vuelve a los píxeles del detector con un error de "
             f"**{p['reproj_rms_px']:.3f} px RMS** (máximo {p['reproj_max_px']:.3f} px), del orden del RMS de la "
             f"calibración de la cámara:")
    L.append("")
    L.append("| Esquina | u reproyectada | v reproyectada | error (px) |")
    L.append("|---|---|---|---|")
    for i, (c, e) in enumerate(zip(p["reprojected_px"], p["reproj_err_px"])):
        L.append(f"| c{i} | {c[0]:.3f} | {c[1]:.3f} | {e:.3f} |")
    L.append("")
    L.append(f"**La fórmula de la cámara, con estos números.** Sin distorsión, un punto (X, Y, Z) en mm cae en "
             f"u = fx·X/Z + cx, v = fy·Y/Z + cy. Para el centro del marker, (X, Y, Z) = tvec: "
             f"u = {k['fx']:.3f}·{p['tvec_mm'][0]:.3f}/{p['tvec_mm'][2]:.3f} + {k['cx']:.3f} = "
             f"**{p['center_pinhole_px'][0]:.2f}**, v = **{p['center_pinhole_px'][1]:.2f}** px. Con la distorsión, "
             f"({p['center_projected_px'][0]:.2f}, {p['center_projected_px'][1]:.2f}) px; el centro de las cuatro "
             f"esquinas está en ({d['centroid_px'][0]:.2f}, {d['centroid_px'][1]:.2f}) px (no coincide exactamente: "
             f"con el marker inclinado, el centro de un cuadrado no se proyecta en el centro de sus esquinas).")
    L.append("")
    L.append(f"**5 · A mano: la distancia por el tamaño.** Z ≈ fx · lado_mm / lado_px = {k['fx']:.3f} · "
             f"{m['size_mm']:.1f} / {d['side_mean_px']:.2f} = **{h['z_from_side_mm']:.1f} mm**, frente a los "
             f"{h['z_pose_mm']:.1f} mm de la pose ({h['diff_mm']:+.1f} mm): la cuenta a mano supone el marker de "
             f"frente, y este está inclinado {p['tilt_deg']:.1f}°, así que sus lados se ven algo más cortos y la "
             f"distancia sale algo mayor. Es la misma cuenta que hace invisible B55: si el perfil dijera un lado "
             f"mayor, la misma imagen daría una Z mayor en la misma proporción (punto 8).")
    L.append("")
    L.append(f"**6 · El filtro.** El 1-Euro de `vision/filtering.py:PositionFilter` (min_cutoff {f['min_cutoff']}, "
             f"beta {f['beta']}, de `filtering` del perfil) ya lleva {f['frames_before']} frames de esta grabación "
             f"(las esquinas y los tiempos grabados, en orden); este frame llega en t = {f['t_s']:.4f} s, "
             f"{f['dt_ms']:.1f} ms después del anterior. Solo se filtra la posición: "
             f"tvec pasa de ({', '.join(f'{v:.3f}' for v in p['tvec_mm'])}) a "
             f"**({', '.join(f'{v:.3f}' for v in f['tvec_filtered_mm'])}) mm**, un desplazamiento de "
             f"{f['shift_mm']:.3f} mm; la rotación no se toca.")
    L.append("")
    L.append(f"**7 · La 4×4 que recibe Slicer.** `vision/pose.py:rvec_tvec_to_matrix` junta R y la tvec filtrada "
             f"(mm). `transport/igtl.py:IgtlSender.send` la manda como `{x['device_name']}` por OpenIGTLink, y pyigtl "
             f"la guarda en float32 (diferencia máxima por el redondeo: {x['float32_max_diff_mm']:.1e} mm). Frente a "
             f"la matriz que el tracker envió en vivo en este frame: **{x['live_diff_translation_mm']:.1f} mm y "
             f"{x['live_diff_rotation_deg']:.1f}°** de diferencia.")
    L.append("")
    L.append("```")
    L.extend(_mat(x["M"], 6))
    L.append("```")
    if "alt_size" in r:
        s = r["alt_size"]
        L.append("")
        L.append(f"**8 · La escala la fija el tamaño del marker (B55).** Las mismas 4 esquinas con un lado de "
                 f"{s['size_mm']:.1f} mm en vez de {m['size_mm']:.1f} dan tvec = "
                 f"({', '.join(f'{v:.3f}' for v in s['tvec_mm'])}) mm: cada coordenada multiplicada por "
                 f"**{s['ratio'][2]:.4f}** ({s['size_mm']:.1f}/{m['size_mm']:.1f} = {s['expected_ratio']:.4f}; error "
                 f"relativo {s['max_rel_err']:.1e}) y la misma rotación ({s['rotation_diff_deg']:.1e}°). La imagen no "
                 f"puede distinguir un marker grande y lejos de uno chico y cerca: solo el `size_mm` del perfil lo "
                 f"decide, y por eso un Marker0 de otro tamaño con el mismo ID sale a escala sin aviso.")
    return "\n".join(L) + "\n"


def draw_example(gray: np.ndarray, result: dict, K, dist, crop_px: int = DEFAULT_CROP_PX) -> np.ndarray:
    """La figura del ejemplo: esquinas detectadas (c0..c3), las reproyectadas (cruces) y los
    ejes de la pose (lado/2, como `tracker.draw_poses`: rvec crudo y tvec filtrada), recortada
    en un cuadrado de `crop_px` alrededor del centro del marker (BGR)."""
    if crop_px < 32:
        raise ValueError(f"crop_px tiene que ser >= 32 (llego {crop_px})")
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    p, d, f = result["raw_pose"], result["detection"], result["filter"]
    rvec = np.asarray(p["rvec_rad"], dtype=np.float64).reshape(3, 1)
    tvec = np.asarray(f["tvec_filtered_mm"], dtype=np.float64).reshape(3, 1)
    K = np.asarray(K, dtype=np.float64)
    dist = np.asarray(dist, dtype=np.float64)
    cv2.drawFrameAxes(img, K, dist, rvec, tvec, result["marker"]["size_mm"] * 0.5, 2)
    corners = np.asarray(d["corners_px"], dtype=np.float64)
    cv2.polylines(img, [np.round(corners).astype(np.int32).reshape(-1, 1, 2)], True, (0, 255, 0), 1)
    for i, (c, q) in enumerate(zip(corners, p["reprojected_px"])):
        u, v = int(round(c[0])), int(round(c[1]))
        cv2.circle(img, (u, v), 4, (0, 255, 0), 1)
        cv2.drawMarker(img, (int(round(q[0])), int(round(q[1]))), (0, 200, 255), cv2.MARKER_CROSS, 7, 1)
        cv2.putText(img, f"c{i}", (u + 6, v - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
    cx, cy = (int(round(v)) for v in d["centroid_px"])
    half = int(crop_px) // 2
    h, w = gray.shape[:2]
    x0 = min(max(cx - half, 0), max(w - int(crop_px), 0))
    y0 = min(max(cy - half, 0), max(h - int(crop_px), 0))
    return img[y0:y0 + int(crop_px), x0:x0 + int(crop_px)]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="El ejemplo resuelto de deteccion -> pose sobre un frame grabado (meta 004).")
    ap.add_argument("--dataset", required=True, type=Path, help="Grabacion .npz de tracker --record.")
    ap.add_argument("--frames-dir", required=True, type=Path, help="Carpeta con frame_NNNNN.png de esa grabacion.")
    ap.add_argument("--frame", required=True, type=int, help="Numero del frame (tiene que tener su PNG).")
    ap.add_argument("--config", required=True, type=Path, help="El perfil con que se grabo.")
    ap.add_argument("--alt-size-mm", type=float, default=None, help="Otro lado del marker, para la escala (B55).")
    ap.add_argument("--output-json", type=Path, default=None, help="Todos los numeros (no se pisa).")
    ap.add_argument("--output-markdown", type=Path, default=None, help="El bloque de ARCHITECTURE.md 9.3 (no se pisa).")
    ap.add_argument("--output-image", type=Path, default=None, help="La figura PNG recortada (no se pisa).")
    ap.add_argument("--crop-px", type=int, default=DEFAULT_CROP_PX, help=f"Lado del recorte (defecto {DEFAULT_CROP_PX}).")
    args = ap.parse_args(argv)
    if args.alt_size_mm is not None and args.alt_size_mm <= 0:
        ap.error("--alt-size-mm tiene que ser > 0")
    if args.crop_px < 32:
        ap.error("--crop-px tiene que ser >= 32")
    for out in (args.output_json, args.output_markdown, args.output_image):
        if out is not None and out.exists():
            ap.error(f"la salida ya existe, no se pisa: {out}")
    if args.output_image is not None and args.output_image.suffix.lower() != ".png":
        ap.error("--output-image tiene que terminar en .png")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    r = explain_frame(args.dataset, args.frames_dir, args.frame, args.config, args.alt_size_mm)
    d, p, f, x = r["detection"], r["raw_pose"], r["filter"], r["matrix"]
    print(f"[Ejemplo] {r['png']}: esquinas frente a lo grabado {d['max_diff_px']:.6f} px; "
          f"reproyeccion {p['reproj_rms_px']:.3f} px RMS (max {p['reproj_max_px']:.3f}); "
          f"filtro {f['shift_mm']:.3f} mm; frente a lo enviado en vivo "
          f"{x['live_diff_translation_mm']:.3e} mm / {x['live_diff_rotation_deg']:.3e} deg")
    if "alt_size" in r:
        s = r["alt_size"]
        print(f"[Ejemplo] con {s['size_mm']} mm: cociente {s['ratio'][2]:.6f} (esperado {s['expected_ratio']:.6f}), "
              f"rotacion {s['rotation_diff_deg']:.3e} deg")
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                                    newline="\n")
        print(f"[Ejemplo] JSON: {args.output_json}")
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(format_markdown(r), encoding="utf-8", newline="\n")
        print(f"[Ejemplo] Markdown: {args.output_markdown}")
    if args.output_image is not None:
        gray = cv2.imread(str(Path(args.frames_dir) / r["png"]), cv2.IMREAD_UNCHANGED)
        img = draw_example(gray, r, r["intrinsics"]["K"], r["intrinsics"]["dist"], args.crop_px)
        args.output_image.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.output_image), img, [cv2.IMWRITE_PNG_COMPRESSION, 9]):
            raise SystemExit(f"[Ejemplo] No se pudo escribir {args.output_image}")
        print(f"[Ejemplo] Figura: {args.output_image} ({img.shape[1]}x{img.shape[0]}, "
              f"{args.output_image.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
