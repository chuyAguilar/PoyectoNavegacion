"""El ruido en reposo de una o varias grabaciones de `tracker --record`, sin camara
(meta 007 · El tracker en la Jetson Orin Nano, fase 5b · El ruido de gs1 por V4L2, B77).

Separa, sobre el `.npz` de `diagnostics.pose_log`, las tres cosas que se mezclan en la
sd z que envia el tracker:
  - el detector (la pose cruda de IPPE_SQUARE sobre las esquinas grabadas, sin filtro);
  - el filtro 1-Euro (la misma pose refiltrada con los tiempos grabados, que tiene que
    reproducir `sent_M`, y con tiempos uniformes a la fps media);
  - la imagen (si la grabacion llevo `--save-frames`: ruido por pixel, contraste, ancho
    de borde y bloqueo JPEG en los PNG).
Ademas: los intervalos entre frames, la sd de cada esquina y del lado aparente (la z de un
marker sale de su tamano aparente), la bimodalidad de la z cruda y del lado, las
frecuencias de mas potencia de la z cruda y, con `deriva`, lo lento (la pendiente y las
medias por segundo, que el 1-Euro deja pasar) frente a lo rapido (el ruido frame a frame). `comparar` pone cada numero frente al de una
grabacion de referencia, en cociente, y `formato_markdown` lo escribe como tabla.

No abre camara ni red: solo numpy, scipy, cv2 y `vision/`. No importa `tracker.py` ni lo
importa nada de la cadena (principio 6). Uso (desde codigo/, con el venv):

    python -m diagnostics.ruido_pose --input W1=<ruta>.npz --input J1=<ruta>.npz \\
        --frames J1=<carpeta con frame_NNNNN.png> --referencia W1 \\
        --output <ruta>.json --output-markdown <ruta>.md

Los dos archivos de salida no se pisan. Context7 (2026-11-03): SciPy `/scipy/scipy`
(`signal.welch(x, fs, nperseg)`: densidad espectral por segmentos; `nperseg` mayor que la
serie se recorta con aviso; `detrend` quita la media por defecto); OpenCV `/websites/opencv`
(`fillPoly` para las mascaras, `imread` en gris, `Sobel` no hace falta: el bloqueo se mide
con diferencias entre pixeles vecinos).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy import signal
from scipy.ndimage import map_coordinates

from diagnostics.pose_log import load_recording
from vision.filtering import PositionFilter
from vision.pose import estimate_single_pose

SARLE_UNIFORME = 5.0 / 9.0          # por encima, la distribucion apunta a dos valores
SEPARACION_NORMAL = 2.66            # lo que da k-medias en 1D sobre una normal (dos medias normales)
SALTO_MM = 1.0                      # un salto de z entre frames seguidos, como en el P-5
PASO_Z_MM = 0.02
PASO_LADO_PX = 0.01
ESCALA_NEGRO = (0.80, 0.95)         # el borde negro del marker, en fraccion del semilado
ESCALA_BLANCO = (1.08, 1.30)        # la zona blanca alrededor del marker
BLOQUE_JPEG = 8


# ---------------------------------------------------------------------------
# La serie de una grabacion
# ---------------------------------------------------------------------------

def _marker(rec: dict, nombre: str) -> tuple[int, float]:
    for m in rec["metadata"].get("markers", []) or []:
        if str(m.get("name")) == nombre:
            return int(m["id"]), float(m["size_mm"])
    raise ValueError(f"la grabacion no tiene un marker llamado {nombre!r} en metadata.markers")


def serie_pose(rec: dict, nombre: str = "Marker0") -> dict:
    """Los frames con exactamente una deteccion del marker y pose valida: `frames` (N,),
    `t` (N,), `esquinas` (N, 4, 2), `xyz_crudo` (N, 3) de IPPE_SQUARE sin filtro con el K,
    el dist y el tamano grabados, y `xyz_enviado` (N, 3) del ultimo `sent_M` de `nombre`
    en ese frame (NaN si ese frame no envio). `excluidos` cuenta los frames con 0, con
    mas de una deteccion del id o con pose invalida."""
    mid, size_mm = _marker(rec, nombre)
    K, dist = rec["K"], rec["dist"]
    off, ids, corners = rec["frame_offsets"], rec["marker_ids"], rec["corners_2d"]
    n = len(rec["timestamps"])
    enviado = np.full((n, 3), np.nan)
    for j in np.flatnonzero(rec["sent_name"] == nombre):
        enviado[int(rec["sent_frame"][j])] = rec["sent_M"][j][:3, 3]
    frames, esquinas, crudo = [], [], []
    excluidos = {"sin_deteccion": 0, "varias_detecciones": 0, "pose_invalida": 0}
    for i in range(n):
        js = [j for j in range(int(off[i]), int(off[i + 1])) if int(ids[j]) == mid]
        if not js:
            excluidos["sin_deteccion"] += 1
            continue
        if len(js) > 1:
            excluidos["varias_detecciones"] += 1
            continue
        pose = estimate_single_pose(corners[js[0]], size_mm, K, dist)
        if pose is None:
            excluidos["pose_invalida"] += 1
            continue
        frames.append(i)
        esquinas.append(np.asarray(corners[js[0]], dtype=np.float64).reshape(4, 2))
        crudo.append(np.asarray(pose[1], dtype=np.float64).reshape(3))
    idx = np.asarray(frames, dtype=np.int64)
    return {
        "frames": idx, "t": rec["timestamps"][idx] if len(idx) else np.zeros(0),
        "esquinas": (np.asarray(esquinas).reshape(-1, 4, 2) if esquinas
                     else np.zeros((0, 4, 2))),
        "xyz_crudo": np.asarray(crudo).reshape(-1, 3) if crudo else np.zeros((0, 3)),
        "xyz_enviado": enviado[idx] if len(idx) else np.zeros((0, 3)),
        "excluidos": excluidos, "n_frames": n, "size_mm": size_mm, "id": mid,
    }


def refiltrar(t: np.ndarray, xyz: np.ndarray, min_cutoff: float, beta: float) -> np.ndarray:
    """El `PositionFilter` de `vision/filtering.py` sobre la serie, con los tiempos `t`."""
    f = PositionFilter(float(min_cutoff), float(beta))
    out = np.empty_like(np.asarray(xyz, dtype=np.float64))
    for k in range(len(out)):
        out[k] = f.filter(np.asarray(xyz[k]).reshape(3, 1), float(t[k])).reshape(3)
    return out


# ---------------------------------------------------------------------------
# Los bloques
# ---------------------------------------------------------------------------

def _sd(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    return float(np.std(x, ddof=1)) if x.size > 1 else float("nan")


def _mad_sd(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if x.size else float("nan")


def intervalos(t: np.ndarray) -> dict:
    """Los `dt` entre muestras seguidas, en ms: p1, p50, p99, max, la fraccion con dt < 2 ms
    (frames en rafaga) y la fraccion con dt > 1.5 veces la mediana (huecos)."""
    t = np.asarray(t, dtype=np.float64)
    if t.size < 2:
        return {"n": int(t.size), "p1_ms": float("nan"), "p50_ms": float("nan"),
                "p99_ms": float("nan"), "max_ms": float("nan"), "fraccion_menor_2ms": float("nan"),
                "fraccion_mayor_1p5_mediana": float("nan"), "fps_media": float("nan")}
    dt = np.diff(t) * 1000.0
    p1, p50, p99 = np.percentile(dt, [1, 50, 99])
    return {"n": int(dt.size), "p1_ms": float(p1), "p50_ms": float(p50), "p99_ms": float(p99),
            "max_ms": float(dt.max()), "fraccion_menor_2ms": float(np.mean(dt < 2.0)),
            "fraccion_mayor_1p5_mediana": float(np.mean(dt > 1.5 * p50)),
            "fps_media": float((t.size - 1) / (t[-1] - t[0])) if t[-1] > t[0] else float("nan")}


def lado_aparente(esquinas: np.ndarray) -> np.ndarray:
    """La media de los cuatro lados del cuadrilatero, en px, por frame (N,)."""
    e = np.asarray(esquinas, dtype=np.float64).reshape(-1, 4, 2)
    lados = np.linalg.norm(e - np.roll(e, -1, axis=1), axis=2)
    return lados.mean(axis=1)


def _correlacion(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def ruido_esquinas(esquinas: np.ndarray, z: np.ndarray | None = None) -> dict:
    """La sd en px de cada esquina (x e y), la del centroide, la del lado aparente medio y,
    si llega `z`, la correlacion entre el lado aparente y esa z."""
    e = np.asarray(esquinas, dtype=np.float64).reshape(-1, 4, 2)
    if len(e) < 2:
        return {"n": int(len(e))}
    lado = lado_aparente(e)
    centroide = e.mean(axis=1)
    out = {
        "n": int(len(e)),
        "sd_esquinas_px": [[_sd(e[:, k, 0]), _sd(e[:, k, 1])] for k in range(4)],
        "sd_esquinas_media_px": float(np.mean([_sd(e[:, k, c]) for k in range(4) for c in range(2)])),
        "sd_centroide_px": [_sd(centroide[:, 0]), _sd(centroide[:, 1])],
        "lado_medio_px": float(lado.mean()),
        "sd_lado_px": _sd(lado),
        "sd_lado_relativa": float(_sd(lado) / lado.mean()) if lado.mean() else float("nan"),
    }
    if z is not None:
        out["correlacion_lado_z"] = _correlacion(lado, np.asarray(z, dtype=np.float64))
    return out


def _sarle(x: np.ndarray) -> float:
    n = x.size
    if n < 4:
        return float("nan")
    d = x - x.mean()
    m2 = np.mean(d ** 2)
    if m2 == 0:
        return float("nan")
    g = np.mean(d ** 3) / m2 ** 1.5
    k = np.mean(d ** 4) / m2 ** 2 - 3.0
    return float((g ** 2 + 1.0) / (k + 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3))))


def _rachas(etiquetas: np.ndarray) -> dict[int, float]:
    """La longitud media de las rachas (muestras seguidas con la misma etiqueta), por etiqueta."""
    cortes = np.flatnonzero(np.diff(etiquetas) != 0) + 1
    inicios = np.concatenate(([0], cortes))
    fines = np.concatenate((cortes, [etiquetas.size]))
    largos = fines - inicios
    out: dict[int, float] = {}
    for g in (0, 1):
        sel = etiquetas[inicios] == g
        out[g] = float(largos[sel].mean()) if sel.any() else float("nan")
    return out


def bimodalidad(x: np.ndarray, paso: float) -> dict:
    """El coeficiente de Sarle (uniforme 0.556; mas alto, dos valores), el histograma con
    ese `paso`, la particion en dos grupos (k-medias en 1D: centros, fraccion, separacion
    entre centros dividida por la sd dentro de los grupos; una normal da ~2.66, dos valores
    bien separados mucho mas) y la longitud media de las rachas en cada grupo (si alterna
    frame a frame o va por bloques)."""
    x = np.asarray(x, dtype=np.float64)
    out: dict = {"n": int(x.size), "sarle": _sarle(x), "sarle_uniforme": SARLE_UNIFORME,
                 "separacion_normal": SEPARACION_NORMAL}
    if x.size < 4 or paso <= 0:
        return out
    lo = np.floor(x.min() / paso) * paso
    bordes = np.arange(lo, x.max() + paso, paso)
    if len(bordes) < 2:
        bordes = np.array([lo, lo + paso])
    cuentas, bordes = np.histogram(x, bins=bordes)
    out["histograma"] = {"paso": float(paso), "centros": [float(c) for c in (bordes[:-1] + paso / 2)],
                         "cuentas": [int(c) for c in cuentas]}
    c = np.percentile(x, [25, 75]).astype(np.float64)
    if c[0] == c[1]:
        c = np.array([x.min(), x.max()])
    etiquetas = np.zeros(x.size, dtype=np.int64)
    for _ in range(100):
        nuevas = (np.abs(x - c[1]) < np.abs(x - c[0])).astype(np.int64)
        if not nuevas.any() or nuevas.all():
            break
        nc = np.array([x[nuevas == 0].mean(), x[nuevas == 1].mean()])
        if np.array_equal(nuevas, etiquetas) and np.allclose(nc, c):
            break
        etiquetas, c = nuevas, nc
    if not etiquetas.any() or etiquetas.all():
        out["dos_grupos"] = {"centros": [float(c[0]), float(c[1])], "fraccion": [1.0, 0.0],
                             "separacion": float("nan"), "racha_media": [float("nan"), float("nan")]}
        return out
    var_dentro = np.mean([np.var(x[etiquetas == g]) for g in (0, 1) if np.sum(etiquetas == g) > 1])
    sd_dentro = float(np.sqrt(var_dentro)) if var_dentro > 0 else float("nan")
    rachas = _rachas(etiquetas)
    out["dos_grupos"] = {
        "centros": [float(c[0]), float(c[1])],
        "fraccion": [float(np.mean(etiquetas == 0)), float(np.mean(etiquetas == 1))],
        "separacion": float(abs(c[1] - c[0]) / sd_dentro) if sd_dentro else float("nan"),
        "racha_media": [rachas[0], rachas[1]],
    }
    return out


def espectro(x: np.ndarray, fs: float, n: int = 3, corte_hz: float = 2.0) -> dict:
    """`scipy.signal.welch` de `x` a `fs` Hz: las `n` frecuencias de mas potencia (sin la
    continua), la fraccion de la potencia total de cada una y la fraccion por debajo de
    `corte_hz` (el `min_cutoff` del 1-Euro: lo que esta por debajo pasa el filtro casi
    entero)."""
    x = np.asarray(x, dtype=np.float64)
    if x.size < 16 or not np.isfinite(fs) or fs <= 0:
        return {"n": int(x.size), "frecuencias_hz": [], "fraccion_potencia": [],
                "fraccion_bajo_corte": float("nan"), "corte_hz": float(corte_hz)}
    nperseg = int(min(1024, x.size))
    f, p = signal.welch(x - x.mean(), fs=float(fs), nperseg=nperseg)
    sel = f > 0
    f, p = f[sel], p[sel]
    total = float(p.sum())
    orden = np.argsort(p)[::-1][:n]
    return {"n": int(x.size), "nperseg": nperseg, "resolucion_hz": float(f[1] - f[0]) if len(f) > 1 else float("nan"),
            "frecuencias_hz": [float(f[i]) for i in orden],
            "fraccion_potencia": [float(p[i] / total) if total > 0 else float("nan") for i in orden],
            "corte_hz": float(corte_hz),
            "fraccion_bajo_corte": float(p[f < corte_hz].sum() / total) if total > 0 else float("nan")}


def deriva(t: np.ndarray, x: np.ndarray, ventana_s: float = 1.0) -> dict:
    """Lo lento frente a lo rapido de una serie: la pendiente de una recta (unidades/s), la
    sd que queda al quitar esa recta, la sd de las medias por ventana de `ventana_s`
    (lo lento), la sd del residuo frente a la media movil de esa ventana (lo rapido, lo que
    de verdad es ruido frame a frame) y el pico a pico de las medias."""
    t = np.asarray(t, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    ok = np.isfinite(x)
    t, x = t[ok], x[ok]
    if x.size < 8 or t[-1] <= t[0]:
        return {"n": int(x.size), "pendiente_por_s": float("nan"), "sd_sin_recta": float("nan"),
                "sd_lenta": float("nan"), "sd_rapida": float("nan"), "pico_a_pico_lenta": float("nan"),
                "ventana_s": float(ventana_s)}
    tt = t - t[0]
    a, b = np.polyfit(tt, x, 1)
    sin_recta = x - (a * tt + b)
    fs = (x.size - 1) / tt[-1]
    w = max(2, int(round(fs * ventana_s)))
    w = min(w, x.size)
    movil = np.convolve(x, np.ones(w) / w, mode="valid")
    ini = (w - 1) // 2
    rapida = x[ini:ini + movil.size] - movil
    bloques = np.floor(tt / ventana_s).astype(np.int64)
    medias = np.array([x[bloques == k].mean() for k in np.unique(bloques)])
    return {"n": int(x.size), "pendiente_por_s": float(a), "sd_sin_recta": _sd(sin_recta),
            "sd_lenta": _sd(medias), "sd_rapida": _sd(rapida),
            "pico_a_pico_lenta": float(medias.max() - medias.min()), "ventana_s": float(ventana_s),
            "medias_por_ventana": [float(m) for m in medias]}


# ---------------------------------------------------------------------------
# La imagen (solo si la grabacion guardo PNG)
# ---------------------------------------------------------------------------

def _poligono(esquinas: np.ndarray, escala: float) -> np.ndarray:
    c = esquinas.mean(axis=0)
    return (c + (esquinas - c) * escala)


def _mascara_anillo(forma: tuple[int, int], esquinas: np.ndarray, escalas: tuple[float, float]) -> np.ndarray:
    """Pixeles entre el poligono a `escalas[0]` y el poligono a `escalas[1]` (bool)."""
    m = np.zeros(forma, dtype=np.uint8)
    cv2.fillPoly(m, [np.round(_poligono(esquinas, escalas[1])).astype(np.int32).reshape(-1, 1, 2)], 1)
    cv2.fillPoly(m, [np.round(_poligono(esquinas, escalas[0])).astype(np.int32).reshape(-1, 1, 2)], 0)
    return m.astype(bool)


def _ancho_borde(img: np.ndarray, esquinas: np.ndarray) -> float:
    """La distancia, en px, entre el 10 y el 90 % del escalon negro -> blanco a traves del
    punto medio de cada lado, promediada en los cuatro lados (NaN si no hay escalon)."""
    c = esquinas.mean(axis=0)
    s = np.arange(-6.0, 6.01, 0.25)
    anchos = []
    for k in range(4):
        a, b = esquinas[k], esquinas[(k + 1) % 4]
        medio = (a + b) / 2.0
        normal = medio - c
        normal /= np.linalg.norm(normal) or 1.0
        puntos = medio[None, :] + s[:, None] * normal[None, :]
        perfil = map_coordinates(img.astype(np.float64), [puntos[:, 1], puntos[:, 0]], order=1, mode="nearest")
        lo, hi = np.median(perfil[s <= -4]), np.median(perfil[s >= 4])
        if hi - lo < 20:
            continue
        n10, n90 = lo + 0.1 * (hi - lo), lo + 0.9 * (hi - lo)
        i10 = int(np.argmax(perfil >= n10))
        i90 = int(np.argmax(perfil >= n90))
        anchos.append(abs(s[i90] - s[i10]))
    return float(np.mean(anchos)) if anchos else float("nan")


def _bloqueo_jpeg(img: np.ndarray, mascara: np.ndarray) -> float:
    """Cociente entre la diferencia media entre pixeles vecinos en las fronteras de bloques
    de 8 px y la de dentro de los bloques, en la zona de la mascara (1.0 = sin bloqueo)."""
    im = img.astype(np.float64)
    dx = np.abs(np.diff(im, axis=1))
    dy = np.abs(np.diff(im, axis=0))
    mx = mascara[:, 1:] & mascara[:, :-1]
    my = mascara[1:, :] & mascara[:-1, :]
    cols = (np.arange(1, im.shape[1]) % BLOQUE_JPEG) == 0
    filas = (np.arange(1, im.shape[0]) % BLOQUE_JPEG) == 0
    front = np.concatenate((dx[:, cols][mx[:, cols]], dy[filas, :][my[filas, :]]))
    dentro = np.concatenate((dx[:, ~cols][mx[:, ~cols]], dy[~filas, :][my[~filas, :]]))
    if front.size < 10 or dentro.size < 10 or dentro.mean() == 0:
        return float("nan")
    return float(front.mean() / dentro.mean())


def ruido_imagen(pngs: list[Path], esquinas: list[np.ndarray]) -> dict:
    """Con el marker quieto: la sd temporal por pixel en la zona blanca de alrededor y en el
    borde negro (mascaras desde las esquinas medias), el contraste blanco - negro, el ancho
    del borde (10-90 %) y el cociente de bloqueo JPEG en la zona blanca."""
    if not pngs:
        return {"n_png": 0}
    imgs = []
    for p in pngs:
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"no se pudo leer {p}")
        imgs.append(img)
    forma = imgs[0].shape
    if any(i.shape != forma for i in imgs):
        raise ValueError("los PNG no tienen todos el mismo tamano")
    esq = np.asarray(esquinas, dtype=np.float64).reshape(-1, 4, 2)
    media = esq.mean(axis=0)
    negro = _mascara_anillo(forma, media, ESCALA_NEGRO)
    blanco = _mascara_anillo(forma, media, ESCALA_BLANCO)
    pila = np.stack(imgs).astype(np.float64)
    out = {
        "n_png": len(imgs),
        "nivel_blanco": float(pila[:, blanco].mean()) if blanco.any() else float("nan"),
        "nivel_negro": float(pila[:, negro].mean()) if negro.any() else float("nan"),
        # Por PNG, en orden: si la luz o la exposicion cambian a lo largo de la corrida, se ve aqui.
        "nivel_blanco_por_png": [float(im[blanco].mean()) if blanco.any() else float("nan") for im in imgs],
        "nivel_negro_por_png": [float(im[negro].mean()) if negro.any() else float("nan") for im in imgs],
        "ancho_borde_px": float(np.mean([_ancho_borde(im, e) for im, e in zip(imgs, esq)])),
        "bloqueo_jpeg": float(np.nanmean([_bloqueo_jpeg(im, blanco) for im in imgs])),
        "movimiento_esquinas_px": float(np.abs(esq - media).max()) if len(esq) > 1 else 0.0,
    }
    out["contraste"] = out["nivel_blanco"] - out["nivel_negro"]
    if len(imgs) >= 2:
        sd = pila.std(axis=0, ddof=1)
        out["sd_pixel_blanco"] = float(sd[blanco].mean()) if blanco.any() else float("nan")
        out["sd_pixel_negro"] = float(sd[negro].mean()) if negro.any() else float("nan")
    else:
        out["sd_pixel_blanco"] = out["sd_pixel_negro"] = float("nan")
    return out


# ---------------------------------------------------------------------------
# Todo junto
# ---------------------------------------------------------------------------

def _pngs_de(frames_dir: Path, serie: dict, rec: dict) -> tuple[list[Path], list[np.ndarray]]:
    pos = {int(f): k for k, f in enumerate(serie["frames"])}
    pngs, esq = [], []
    for f in rec["frames_saved"]:
        p = Path(frames_dir) / f"frame_{int(f):05d}.png"
        if int(f) in pos and p.is_file():
            pngs.append(p)
            esq.append(serie["esquinas"][pos[int(f)]])
    return pngs, esq


def analizar(npz: Path, frames_dir: Path | None = None, nombre: str = "Marker0",
             paso_z_mm: float = PASO_Z_MM, paso_lado_px: float = PASO_LADO_PX) -> dict:
    """Todo lo anterior para una grabacion. `refiltrado_grabado` tiene que reproducir lo
    enviado (`max_diff_refiltrado_mm`); `refiltrado_uniforme` usa tiempos a la fps media."""
    rec = load_recording(npz)
    s = serie_pose(rec, nombre)
    meta = rec["metadata"]
    filt = meta.get("filtering") or {}
    n = len(s["t"])
    out: dict = {
        "archivo": Path(npz).name, "config": meta.get("config"), "frames": int(s["n_frames"]),
        "frames_con_pose": n, "fraccion_con_pose": float(n / s["n_frames"]) if s["n_frames"] else float("nan"),
        "excluidos": s["excluidos"], "fps_tracker": meta.get("fps_average"),
        "fps_camara": (meta.get("capture") or {}).get("fps_camera"),
        "captura": (meta.get("capture") or {}).get("mode"), "opencv": meta.get("opencv"),
    }
    if n < 4:
        out["error"] = f"solo {n} frames con pose de {nombre}"
        return out
    z_env, z_cru = s["xyz_enviado"][:, 2], s["xyz_crudo"][:, 2]
    con_envio = np.isfinite(z_env)
    inter = intervalos(s["t"])
    fps = inter["fps_media"]
    t_unif = s["t"][0] + np.arange(n) / fps if np.isfinite(fps) and fps > 0 else s["t"]
    ref_grab = refiltrar(s["t"], s["xyz_crudo"], filt.get("min_cutoff", 1.0), filt.get("beta", 0.0))
    ref_unif = refiltrar(t_unif, s["xyz_crudo"], filt.get("min_cutoff", 1.0), filt.get("beta", 0.0))
    dz = np.abs(np.diff(z_env[con_envio]))
    saltos = int(np.sum(dz > SALTO_MM))
    quietos = np.concatenate(([True], dz <= SALTO_MM)) & np.concatenate((dz <= SALTO_MM, [True]))
    out.update({
        "filtro": {"enabled": bool(filt.get("enabled")), "min_cutoff": filt.get("min_cutoff"),
                   "beta": filt.get("beta")},
        "z_media_mm": float(np.nanmean(z_env)),
        "sd_z_enviada_mm": _sd(z_env[con_envio]),
        "mad_z_enviada_mm": _mad_sd(z_env[con_envio]),
        "saltos_z_mayores_1mm": saltos,
        "sd_z_enviada_sin_saltos_mm": _sd(z_env[con_envio][quietos]),
        "sd_x_enviada_mm": _sd(s["xyz_enviado"][con_envio, 0]),
        "sd_y_enviada_mm": _sd(s["xyz_enviado"][con_envio, 1]),
        "sd_z_cruda_mm": _sd(z_cru), "mad_z_cruda_mm": _mad_sd(z_cru),
        "sd_x_cruda_mm": _sd(s["xyz_crudo"][:, 0]), "sd_y_cruda_mm": _sd(s["xyz_crudo"][:, 1]),
        "sd_z_refiltrada_grabada_mm": _sd(ref_grab[:, 2]),
        "sd_z_refiltrada_uniforme_mm": _sd(ref_unif[:, 2]),
        "max_diff_refiltrado_mm": (float(np.max(np.abs(ref_grab[con_envio] - s["xyz_enviado"][con_envio])))
                                   if con_envio.any() else float("nan")),
        "cociente_enviada_cruda": float(_sd(z_env[con_envio]) / _sd(z_cru)) if _sd(z_cru) else float("nan"),
        "deriva_z_enviada": deriva(s["t"][con_envio], z_env[con_envio]),
        "deriva_z_cruda": deriva(s["t"], z_cru),
        "deriva_lado": deriva(s["t"], lado_aparente(s["esquinas"])),
        "intervalos": inter,
        "esquinas": ruido_esquinas(s["esquinas"], z_cru),
        "bimodalidad_z_cruda": bimodalidad(z_cru, paso_z_mm),
        "bimodalidad_lado": bimodalidad(lado_aparente(s["esquinas"]), paso_lado_px),
        "espectro_z_cruda": espectro(z_cru, fps),
    })
    if frames_dir is not None:
        pngs, esq = _pngs_de(Path(frames_dir), s, rec)
        out["imagen"] = ruido_imagen(pngs, esq) if pngs else {"n_png": 0}
    return out


def _aplanar(d: dict, prefijo: str = "") -> dict[str, float]:
    plano: dict[str, float] = {}
    for k, v in d.items():
        clave = f"{prefijo}{k}"
        if isinstance(v, dict):
            plano.update(_aplanar(v, clave + "."))
        elif isinstance(v, bool) or v is None:
            continue
        elif isinstance(v, (int, float)):
            plano[clave] = float(v)
        elif isinstance(v, list) and 0 < len(v) <= 4 \
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            for i, x in enumerate(v):
                plano[f"{clave}[{i}]"] = float(x)
    return plano


def comparar(resultados: dict[str, dict], referencia: str) -> dict:
    """Cada numero de cada grabacion frente al de `referencia`, en cociente (NaN si la
    referencia es 0 o falta). `filas` va en el orden de la referencia."""
    if referencia not in resultados:
        raise ValueError(f"la referencia {referencia!r} no esta entre {sorted(resultados)}")
    planos = {e: _aplanar(r) for e, r in resultados.items()}
    claves = list(planos[referencia])
    for e in resultados:
        claves += [k for k in planos[e] if k not in claves]
    filas = {}
    for k in claves:
        ref = planos[referencia].get(k)
        fila = {"valores": {e: planos[e].get(k) for e in resultados}, "cociente": {}}
        for e in resultados:
            v = planos[e].get(k)
            fila["cociente"][e] = (v / ref if v is not None and ref not in (None, 0.0)
                                   and np.isfinite(ref) and np.isfinite(v) else None)
        filas[k] = fila
    return {"referencia": referencia, "etiquetas": list(resultados), "filas": filas}


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    if abs(v) >= 1000 or v == int(v):
        return f"{v:.0f}" if abs(v) < 1e7 else f"{v:.3g}"
    return f"{v:.4g}"


def formato_markdown(comparacion: dict) -> str:
    """Una tabla: una fila por numero, una columna por grabacion; fuera de la referencia,
    el valor y su cociente entre parentesis."""
    ref = comparacion["referencia"]
    etiquetas = comparacion["etiquetas"]
    lineas = ["| metrica | " + " | ".join(f"{e} (ref)" if e == ref else e for e in etiquetas) + " |",
              "|---|" + "---|" * len(etiquetas)]
    for k, fila in comparacion["filas"].items():
        celdas = []
        for e in etiquetas:
            v = fila["valores"].get(e)
            c = fila["cociente"].get(e)
            celdas.append(_fmt(v) if e == ref or c is None else f"{_fmt(v)} (x{c:.2f})")
        lineas.append(f"| `{k}` | " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _etiqueta_ruta(texto: str) -> tuple[str, Path]:
    if "=" not in texto:
        raise argparse.ArgumentTypeError(f"se espera ETIQUETA=RUTA, no {texto!r}")
    e, r = texto.split("=", 1)
    if not e.strip():
        raise argparse.ArgumentTypeError(f"etiqueta vacia en {texto!r}")
    return e.strip(), Path(r.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="El ruido en reposo de grabaciones de tracker --record (meta 007, B77).")
    ap.add_argument("--input", action="append", required=True, type=_etiqueta_ruta, metavar="ETIQUETA=RUTA.npz")
    ap.add_argument("--frames", action="append", default=[], type=_etiqueta_ruta, metavar="ETIQUETA=CARPETA",
                    help="PNG de --save-frames de esa grabacion (opcional).")
    ap.add_argument("--referencia", required=True, help="La etiqueta frente a la que se comparan las demas.")
    ap.add_argument("--name", default="Marker0", help="Nombre del marker (Marker0).")
    ap.add_argument("--output", required=True, type=Path, help="JSON (no se pisa).")
    ap.add_argument("--output-markdown", required=True, type=Path, help="Markdown con la tabla (no se pisa).")
    args = ap.parse_args(argv)
    for p in (args.output, args.output_markdown):
        if p.exists():
            print(f"[ruido_pose] la salida ya existe, no se pisa: {p}", file=sys.stderr)
            return 2
    etiquetas = [e for e, _ in args.input]
    if len(set(etiquetas)) != len(etiquetas):
        print(f"[ruido_pose] etiquetas repetidas: {etiquetas}", file=sys.stderr)
        return 2
    frames = dict(args.frames)
    sobran = [e for e in frames if e not in etiquetas]
    if sobran or args.referencia not in etiquetas:
        print(f"[ruido_pose] --frames de etiquetas sin --input {sobran} o --referencia "
              f"{args.referencia!r} fuera de {etiquetas}", file=sys.stderr)
        return 2
    try:
        resultados = {e: analizar(r, frames.get(e), args.name) for e, r in args.input}
    except (OSError, ValueError) as e:
        print(f"[ruido_pose] ERROR: {e}", file=sys.stderr)
        return 1
    comp = comparar(resultados, args.referencia)
    for p in (args.output, args.output_markdown):
        p.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"resultados": resultados, "comparacion": comp}, indent=1,
                                      ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    md = formato_markdown(comp)
    args.output_markdown.write_text(md, encoding="utf-8")
    print(md)
    for e, r in resultados.items():
        d = r.get("deriva_z_enviada") or {}
        print(f"[ruido_pose] {e}: sd z enviada {_fmt(r.get('sd_z_enviada_mm'))} mm (lenta "
              f"{_fmt(d.get('sd_lenta'))}, rapida {_fmt(d.get('sd_rapida'))}, pendiente "
              f"{_fmt((d.get('pendiente_por_s') or float('nan')) * 1000)} um/s), cruda "
              f"{_fmt(r.get('sd_z_cruda_mm'))}, refiltrada uniforme {_fmt(r.get('sd_z_refiltrada_uniforme_mm'))}; "
              f"max diff refiltrado {r.get('max_diff_refiltrado_mm')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
