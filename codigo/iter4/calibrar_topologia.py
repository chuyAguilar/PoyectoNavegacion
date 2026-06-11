"""
Herramienta OPCIONAL: Calibracion topologica del dodecaedro.

Esta NO es parte del pipeline obligatorio (A->B->C->D->E->F). Es una herramienta
de verificacion para usar cuando:

  (a) Se arma un dodecaedro NUEVO y hay dudas sobre el orden de pegado.
  (b) Se sospecha que la topologia del dodecaedro fisico no coincide con
      la convencion teorica de generar_reference_dodecaedro.py.
  (c) Se quiere documentar el orden REAL de los IDs en un cubo dado.

Pipeline:
  1. Estimar pose individual de cada marker (IPPE_SQUARE) desde el dataset.
  2. Medir distancia 3D entre cada par de markers.
  3. Clasificar adyacencias (distancia ~ 23.4 mm con edge=20 mm).
  4. Verificar estructura de dodecaedro (1 TOP, 5 sup, 5 inf).
  5. Ordenar anillos siguiendo adyacencias ciclicas.
  6. Generar geometria canonica con IDs mapeados a sus posiciones reales.

Salida: data/reference_dodecaedro_real.txt (drop-in para BA si se quiere usar).

Uso tipico:
    python calibrar_topologia.py
    # Mira el output: si todos los pares matchean dentro de 3 mm, la
    # topologia del cubo es consistente con un dodecaedro regular.

ADVERTENCIA (lecciones aprendidas 2026-05-19):
  - Generar este archivo y usarlo en el BA en lugar del teorico NO mejora la
    convergencia si el problema esta en el dataset (motion blur, mala
    iluminacion, cobertura desbalanceada). Antes de usar este script para
    "arreglar" un BA que no converge, verificar primero la calidad de la
    captura (etapa C).
  - El "orden detectado" del anillo inferior puede ser arbitrario por una
    eleccion ciclica (e.g., [158,159,160,161,157] o equivalentes son la misma
    topologia geometrica). No tomar la diferencia con el teorico como error
    de pegado a menos que las distancias entre pares confirmen desfases.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


# Constantes geometricas
PHI = (1.0 + np.sqrt(5.0)) / 2.0
THETA = np.arccos(1.0 / np.sqrt(5.0))

DEFAULT_EDGE_MM = 20.0
DEFAULT_MARKER_MM = 16.0
DEFAULT_ID_TOP = 151
DEFAULT_TOL_ADJ_MM = 5.0  # tolerancia para clasificar adyacencia
DEFAULT_MIN_PAR_OBS = 5    # minimo de observaciones por par para confiar


def log_info(m): print(f"[INFO] {m}")
def log_warn(m): print(f"[WARN] {m}")
def log_error(m): print(f"[ERROR] {m}", file=sys.stderr)
def log_stats(m): print(f"[STATS] {m}")


def inradius(edge_mm):
    return edge_mm * PHI**2 / (2.0 * np.sqrt(3.0 - PHI))


def cargar_dataset(npz_path):
    d = np.load(npz_path, allow_pickle=True)
    return list(d["frames_data"]), d["K"], d["dist"], set(int(x) for x in d["rb_ids"])


def marker_object_points(marker_mm):
    """4 esquinas locales de un marker (convencion OpenCV TL, TR, BR, BL)."""
    h = marker_mm / 2.0
    return np.array([
        [-h,  h, 0.0],
        [ h,  h, 0.0],
        [ h, -h, 0.0],
        [-h, -h, 0.0],
    ], dtype=np.float64)


def estimar_centros_3d_por_frame(frames, K, dist, marker_mm):
    """Para cada frame, estima la pose individual de cada marker con IPPE_SQUARE.

    Devuelve lista de dicts {mid: tvec (3,)} - el centro 3D de cada marker en frame de camara.
    """
    obj_pts = marker_object_points(marker_mm)
    centros_por_frame = []
    for fd in frames:
        centros = {}
        for mid, corners_2d in fd["detecciones"].items():
            img = corners_2d.reshape(4, 2).astype(np.float64)
            retval, rvecs, tvecs, errores = cv2.solvePnPGeneric(
                obj_pts, img, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            if retval < 1:
                continue
            mejor = None
            for rv, tv, er in zip(rvecs, tvecs, errores):
                if tv[2, 0] > 0:
                    err_v = float(er[0]) if hasattr(er, "__len__") else float(er)
                    if mejor is None or err_v < mejor[1]:
                        mejor = (tv.flatten(), err_v)
            if mejor is not None:
                centros[int(mid)] = mejor[0]
        centros_por_frame.append(centros)
    return centros_por_frame


def computar_distancias_pares(centros_por_frame):
    """Mediana de distancias 3D entre cada par de markers a traves de todos los frames."""
    dist_pares = defaultdict(list)
    for centros in centros_por_frame:
        ids_vis = sorted(centros.keys())
        for i in range(len(ids_vis)):
            for j in range(i + 1, len(ids_vis)):
                a, b = ids_vis[i], ids_vis[j]
                d = float(np.linalg.norm(centros[a] - centros[b]))
                dist_pares[(a, b)].append(d)
    return {par: float(np.median(ds)) for par, ds in dist_pares.items()
            if len(ds) >= DEFAULT_MIN_PAR_OBS}, dist_pares


def construir_grafo_adyacencias(dist_pares, d_adj_esperada, tol_mm):
    """Construye dict {mid: set[mids_adyacentes]} segun umbral."""
    g = defaultdict(set)
    for (a, b), d in dist_pares.items():
        if abs(d - d_adj_esperada) <= tol_mm:
            g[a].add(b)
            g[b].add(a)
    return dict(g)


def identificar_anillos(grafo, id_top):
    """Dado el TOP, identifica anillo superior (5 vecinos del TOP) y anillo inferior.

    Devuelve (sup_ordenado, inf_ordenado), cada uno con 5 IDs.
    """
    if id_top not in grafo:
        raise ValueError(f"ID TOP {id_top} no esta en el grafo de adyacencias")
    sup_set = grafo[id_top]
    if len(sup_set) != 5:
        raise ValueError(
            f"ID TOP {id_top} tiene {len(sup_set)} vecinos, deberia tener 5. "
            f"Adyacentes detectados: {sorted(sup_set)}"
        )

    # Ordenar anillo superior ciclicamente
    sup_list = list(sup_set)
    orden_sup = [sup_list[0]]
    while len(orden_sup) < 5:
        actual = orden_sup[-1]
        anterior = orden_sup[-2] if len(orden_sup) >= 2 else None
        # Vecino de 'actual' que esta en sup_set y NO es el anterior
        candidatos = [v for v in grafo[actual]
                      if v in sup_set and v != anterior and v not in orden_sup]
        if not candidatos:
            raise ValueError(f"No se puede continuar el anillo superior en {actual}")
        orden_sup.append(candidatos[0])

    # Anillo inferior: el resto de markers
    todos = set(grafo.keys()) | {id_top}
    inf_set = todos - {id_top} - set(orden_sup)
    if len(inf_set) != 5:
        raise ValueError(
            f"Anillo inferior tiene {len(inf_set)} markers, deberia tener 5. "
            f"Resto: {sorted(inf_set)}"
        )

    # inf_i debe estar adyacente a sup_i Y sup_{i+1} (compartiendo arista en el zigzag)
    orden_inf = []
    for i in range(5):
        sup_a = orden_sup[i]
        sup_b = orden_sup[(i + 1) % 5]
        candidatos = inf_set & grafo.get(sup_a, set()) & grafo.get(sup_b, set())
        candidatos -= set(orden_inf)
        if not candidatos:
            raise ValueError(
                f"No hay marker inferior compartido entre sup_{i}={sup_a} y sup_{(i+1)%5}={sup_b}"
            )
        orden_inf.append(next(iter(candidatos)))

    return orden_sup, orden_inf


def construir_cara_canonica(centro, normal, marker_mm):
    """4 esquinas en el frame del dodecaedro. Convencion: label hacia +Z."""
    z_global = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(normal, z_global)) > 0.99:
        y_marker = np.array([0.0, 1.0, 0.0])
    else:
        y_marker = z_global - np.dot(z_global, normal) * normal
        y_marker = y_marker / np.linalg.norm(y_marker)
    x_marker = np.cross(y_marker, normal)
    x_marker = x_marker / np.linalg.norm(x_marker)
    h = marker_mm / 2.0
    esq_local = np.array([[-h, h, 0.0], [h, h, 0.0], [h, -h, 0.0], [-h, -h, 0.0]])
    R = np.column_stack([x_marker, y_marker, normal])
    return centro + esq_local @ R.T


def generar_geometria_real(id_top, sup_orden, inf_orden, edge_mm, marker_mm):
    """Genera dict {tag_id: (4, 3)} asignando cada ID a su posicion canonica real."""
    r_in = inradius(edge_mm)
    geom = {}

    # TOP
    geom[id_top] = construir_cara_canonica(
        np.array([0.0, 0.0, r_in]), np.array([0.0, 0.0, 1.0]), marker_mm
    )

    # Anillo superior (azimuts 0, 72, 144, 216, 288)
    for i, mid in enumerate(sup_orden):
        az = i * (2.0 * np.pi / 5.0)
        centro = np.array([np.sin(THETA) * np.cos(az),
                           np.sin(THETA) * np.sin(az),
                           np.cos(THETA)]) * r_in
        normal = centro / np.linalg.norm(centro)
        geom[mid] = construir_cara_canonica(centro, normal, marker_mm)

    # Anillo inferior (azimuts 36, 108, 180, 252, 324)
    for i, mid in enumerate(inf_orden):
        az = i * (2.0 * np.pi / 5.0) + np.pi / 5.0
        centro = np.array([np.sin(THETA) * np.cos(az),
                           np.sin(THETA) * np.sin(az),
                           -np.cos(THETA)]) * r_in
        normal = centro / np.linalg.norm(centro)
        geom[mid] = construir_cara_canonica(centro, normal, marker_mm)

    return geom


def validar_geometria_vs_medidas(geom, dist_pares, tol_mm=2.0):
    """Compara distancias en geom calibrada vs distancias medidas. Devuelve dict de errores."""
    errores = {}
    for (a, b), d_medida in dist_pares.items():
        if a in geom and b in geom:
            d_geom = float(np.linalg.norm(geom[a].mean(axis=0) - geom[b].mean(axis=0)))
            diff = abs(d_geom - d_medida)
            if diff > tol_mm:
                errores[(a, b)] = (d_geom, d_medida, diff)
    return errores


def guardar_archivo(geom, output_path, id_top, sup_orden, inf_orden,
                    edge_mm, marker_mm, dist_pares):
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Geometria REAL del dodecaedro (calibracion topologica - Etapa C.5)\n")
        f.write(f"# Mapeo de IDs fisicos a posiciones canonicas:\n")
        f.write(f"#   TOP: {id_top}\n")
        f.write(f"#   Anillo superior (az 0,72,144,216,288): {sup_orden}\n")
        f.write(f"#   Anillo inferior (az 36,108,180,252,324): {inf_orden}\n")
        f.write(f"# Arista: {edge_mm} mm, Marker: {marker_mm} mm\n")
        f.write(f"# Pares medidos: {len(dist_pares)}\n")
        f.write(f"# Convencion esquinas (OpenCV ArUco): c0=TL c1=TR c2=BR c3=BL\n")
        f.write("# Formato: tag_id  cx cy cz  c0..c3\n#\n")
        for tag_id in sorted(geom.keys()):
            esq = geom[tag_id]
            centro = esq.mean(axis=0)
            vals = list(centro) + list(esq.flatten())
            f.write(f"{tag_id:3d}   " + "  ".join(f"{v:+8.3f}" for v in vals) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Etapa C.5: calibracion topologica del dodecaedro.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default="capturas_calibracion.npz")
    parser.add_argument("--output", default="data/reference_dodecaedro_real.txt")
    parser.add_argument("--id-top", type=int, default=DEFAULT_ID_TOP)
    parser.add_argument("--edge-mm", type=float, default=DEFAULT_EDGE_MM)
    parser.add_argument("--marker-mm", type=float, default=DEFAULT_MARKER_MM)
    parser.add_argument("--tol-adj-mm", type=float, default=DEFAULT_TOL_ADJ_MM)
    args = parser.parse_args()

    if not Path(args.input).exists():
        log_error(f"Dataset no existe: {args.input}")
        sys.exit(1)

    log_info(f"Cargando dataset {args.input}...")
    frames, K, dist, rb_ids = cargar_dataset(args.input)
    log_info(f"  Frames: {len(frames)}, rb_ids: {sorted(rb_ids)}")

    log_info("Estimando poses individuales (IPPE_SQUARE)...")
    centros_pf = estimar_centros_3d_por_frame(frames, K, dist, args.marker_mm)

    log_info("Calculando distancias entre pares...")
    dist_pares, _ = computar_distancias_pares(centros_pf)
    log_info(f"  Pares con >= {DEFAULT_MIN_PAR_OBS} observaciones: {len(dist_pares)}")

    r_in = inradius(args.edge_mm)
    d_adj = 2.0 * r_in * np.sin(THETA / 2.0)
    log_info(f"  Distancia adyacente esperada (edge={args.edge_mm}): {d_adj:.3f} mm")
    log_info(f"  Tolerancia: +/- {args.tol_adj_mm} mm")

    grafo = construir_grafo_adyacencias(dist_pares, d_adj, args.tol_adj_mm)
    log_stats(f"Grafo de adyacencias detectado:")
    for mid in sorted(grafo.keys()):
        log_stats(f"  ID {mid}: vecinos = {sorted(grafo[mid])} (n={len(grafo[mid])})")

    try:
        sup_orden, inf_orden = identificar_anillos(grafo, args.id_top)
    except ValueError as e:
        log_error(f"No se puede identificar anillos: {e}")
        log_error("Posibles causas: dataset insuficiente, marker faltante, "
                  "o topologia inconsistente. Revisar la cobertura por marker.")
        sys.exit(1)

    log_stats(f"Mapeo de IDs detectado:")
    log_stats(f"  TOP: {args.id_top}")
    log_stats(f"  Anillo superior (az 0,72,144,216,288): {sup_orden}")
    log_stats(f"  Anillo inferior (az 36,108,180,252,324): {inf_orden}")

    geom = generar_geometria_real(args.id_top, sup_orden, inf_orden,
                                    args.edge_mm, args.marker_mm)

    log_info("Validando geometria contra distancias medidas...")
    errores = validar_geometria_vs_medidas(geom, dist_pares, tol_mm=3.0)
    if errores:
        log_warn(f"{len(errores)} pares con diff > 3 mm (probable orientacion de label):")
        for (a, b), (d_g, d_m, df) in sorted(errores.items(), key=lambda x: -x[1][2])[:5]:
            log_warn(f"  {a}-{b}: geom={d_g:.2f}, medida={d_m:.2f}, diff={df:.2f}")
    else:
        log_info("  Todas las distancias matchean dentro de 3 mm.")

    guardar_archivo(geom, args.output, args.id_top, sup_orden, inf_orden,
                    args.edge_mm, args.marker_mm, dist_pares)
    log_info(f"Guardado: {args.output}")
    log_info("Proximo paso: python calibrar_rigid_body.py --teorico " + str(args.output))


if __name__ == "__main__":
    main()
