"""
Genera reference_dodecaedro.txt para el rigid body multi-marker tipo dodecaedro.

Por defecto, reproduce la geometria de iteracion 1 (IDs 151-161, arista 20 mm,
marker 16 mm), bit-a-bit identica al historico (RMSE BA 0.61 px).

Para migrar a iteracion 2 (IDs 1-11):
  python generar_reference_dodecaedro.py \
      --id-top 1 --ids-superior 2,3,4,5,6 --ids-inferior 7,8,9,10,11 \
      --output data/reference_dodecaedro_iter2.txt

Auditoria: documentos/auditoria_iter2/03a_auditoria_generar_reference_dodecaedro.md

Convencion de esquinas (OpenCV ArUco):
  c0=TL  c1=TR  c2=BR  c3=BL  (clockwise empezando por top-left)

Convencion fisica del label:
  El label del marker apunta hacia +Z (regla 'ID label apuntando hacia la
  punta'). El frame local de cada cara es right-handed con la normal saliente.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


PHI = (1.0 + np.sqrt(5.0)) / 2.0
THETA = np.arccos(1.0 / np.sqrt(5.0))
DIHEDRAL_DEG = float(np.degrees(np.arccos(-1.0 / np.sqrt(5.0))))

DEFAULT_EDGE_MM = 20.0
DEFAULT_MARKER_MM = 16.0
DEFAULT_ID_TOP = 151
DEFAULT_IDS_SUPERIOR = [152, 153, 154, 155, 156]
DEFAULT_IDS_INFERIOR = [157, 158, 159, 160, 161]


def inradius(edge_mm):
    """Distancia del centro del dodecaedro a una cara."""
    return edge_mm * PHI**2 / (2.0 * np.sqrt(3.0 - PHI))


def diametro_cara_pentagonal(edge_mm):
    """Diametro circunscrito al pentagono regular de lado edge_mm."""
    return edge_mm / np.sin(np.radians(36.0))


def construir_cara(centro, normal, marker_mm, rotacion_propia=0.0):
    """4 esquinas de un marker en una cara del dodecaedro.

    Frame local right-handed (z=normal saliente):
      y_marker = proyeccion de +Z sobre la cara (label apunta hacia +Z).
                 Caso especial TOP/BASE: y_marker = +Y global.
      x_marker = cross(y_marker, normal).

    Esquinas OpenCV ArUco: c0=TL, c1=TR, c2=BR, c3=BL.
    """
    z_global = np.array([0.0, 0.0, 1.0])

    if abs(np.dot(normal, z_global)) > 0.99:
        y_marker = np.array([0.0, 1.0, 0.0])
    else:
        y_marker = z_global - np.dot(z_global, normal) * normal
        y_marker = y_marker / np.linalg.norm(y_marker)

    x_marker = np.cross(y_marker, normal)
    x_marker = x_marker / np.linalg.norm(x_marker)

    if rotacion_propia != 0.0:
        from scipy.spatial.transform import Rotation
        R = Rotation.from_rotvec(normal * rotacion_propia).as_matrix()
        x_marker = R @ x_marker
        y_marker = R @ y_marker

    half = marker_mm / 2.0
    esquinas_locales = np.array([
        [-half,  half, 0.0],
        [ half,  half, 0.0],
        [ half, -half, 0.0],
        [-half, -half, 0.0],
    ])
    R_local_to_global = np.column_stack([x_marker, y_marker, normal])
    return centro + esquinas_locales @ R_local_to_global.T


def _validar_inputs(edge_mm, marker_mm, id_top, ids_superior, ids_inferior):
    if edge_mm <= 0.0:
        raise ValueError(f"edge_mm debe ser positivo (recibido: {edge_mm})")
    if marker_mm <= 0.0:
        raise ValueError(f"marker_mm debe ser positivo (recibido: {marker_mm})")
    diam = diametro_cara_pentagonal(edge_mm)
    if marker_mm >= diam:
        raise ValueError(
            f"marker_mm={marker_mm} no cabe en cara pentagonal "
            f"(diam={diam:.3f} mm con edge={edge_mm} mm)"
        )
    if len(ids_superior) != 5:
        raise ValueError(f"ids_superior debe tener 5 IDs (recibidos {len(ids_superior)})")
    if len(ids_inferior) != 5:
        raise ValueError(f"ids_inferior debe tener 5 IDs (recibidos {len(ids_inferior)})")
    todos = [id_top] + list(ids_superior) + list(ids_inferior)
    if len(set(todos)) != 11:
        raise ValueError(f"Los 11 IDs deben ser unicos; recibidos: {todos}")


def construir_dodecaedro(edge_mm=DEFAULT_EDGE_MM, marker_mm=DEFAULT_MARKER_MM,
                         id_top=DEFAULT_ID_TOP, ids_superior=None, ids_inferior=None):
    """Geometria 3D de los 11 markers del dodecaedro."""
    if ids_superior is None:
        ids_superior = list(DEFAULT_IDS_SUPERIOR)
    if ids_inferior is None:
        ids_inferior = list(DEFAULT_IDS_INFERIOR)

    _validar_inputs(edge_mm, marker_mm, id_top, ids_superior, ids_inferior)

    r_in = inradius(edge_mm)
    geometria = {}

    centro_top = np.array([0.0, 0.0, r_in])
    normal_top = np.array([0.0, 0.0, 1.0])
    geometria[id_top] = construir_cara(centro_top, normal_top, marker_mm)

    for i, tag_id in enumerate(ids_superior):
        az = i * (2.0 * np.pi / 5.0)
        centro = np.array([
            np.sin(THETA) * np.cos(az),
            np.sin(THETA) * np.sin(az),
            np.cos(THETA),
        ]) * r_in
        normal = centro / np.linalg.norm(centro)
        geometria[tag_id] = construir_cara(centro, normal, marker_mm)

    for i, tag_id in enumerate(ids_inferior):
        az = i * (2.0 * np.pi / 5.0) + np.pi / 5.0
        centro = np.array([
            np.sin(THETA) * np.cos(az),
            np.sin(THETA) * np.sin(az),
            -np.cos(THETA),
        ]) * r_in
        normal = centro / np.linalg.norm(centro)
        geometria[tag_id] = construir_cara(centro, normal, marker_mm)

    return geometria


def validar_geometria(geometria, edge_mm=DEFAULT_EDGE_MM, marker_mm=DEFAULT_MARKER_MM,
                      id_top=DEFAULT_ID_TOP, ids_superior=None, ids_inferior=None,
                      tol_mm=1e-3, verbose=True):
    """Valida la geometria contra invariantes del dodecaedro regular."""
    if ids_superior is None:
        ids_superior = list(DEFAULT_IDS_SUPERIOR)
    if ids_inferior is None:
        ids_inferior = list(DEFAULT_IDS_INFERIOR)

    r_in_esp = inradius(edge_mm)
    d_adj_esp = 2.0 * r_in_esp * np.sin(THETA / 2.0)
    diam = diametro_cara_pentagonal(edge_mm)

    chequeos = []

    def add(nombre, ok, valor="", esperado="", unidad=""):
        chequeos.append((nombre, ok, str(valor), str(esperado), unidad))

    add("PHI identidad (phi^2 = phi+1)", abs(PHI**2 - PHI - 1) < 1e-12)

    theta_alt = np.pi - np.arccos(-1.0 / np.sqrt(5.0))
    add("THETA = pi - dihedral", abs(THETA - theta_alt) < 1e-12,
        f"{np.degrees(THETA):.6f}", f"{np.degrees(theta_alt):.6f}", "deg")

    r_in_alt = (edge_mm / 2.0) * np.sqrt(2.5 + 1.1 * np.sqrt(5.0))
    add("inradius formulas alternativas coinciden",
        abs(r_in_esp - r_in_alt) < 1e-9,
        f"{r_in_esp:.6f}", f"{r_in_alt:.6f}", "mm")

    add("11 markers presentes", len(geometria) == 11, len(geometria), 11)

    ids_esp = set([id_top] + list(ids_superior) + list(ids_inferior))
    add("IDs esperados presentes", ids_esp == set(geometria.keys()),
        sorted(geometria.keys()), sorted(ids_esp))

    max_err_eq = 0.0
    for esq in geometria.values():
        err = abs(np.linalg.norm(esq.mean(axis=0)) - r_in_esp)
        if err > max_err_eq:
            max_err_eq = err
    add("Caras equidistantes del origen", max_err_eq < tol_mm,
        f"{max_err_eq:.6f}", f"< {tol_mm}", "mm")

    margen = (diam - marker_mm) / 2.0
    add("Marker cabe en cara (margen > 1 mm)", margen > 1.0,
        f"{margen:.3f}", "> 1.0", "mm")

    c_top = geometria[id_top].mean(axis=0)
    max_err_ts = 0.0
    for tid in ids_superior:
        err = abs(np.linalg.norm(c_top - geometria[tid].mean(axis=0)) - d_adj_esp)
        if err > max_err_ts:
            max_err_ts = err
    add("Distancia TOP <-> cinturon superior uniforme", max_err_ts < tol_mm,
        f"{max_err_ts:.6f}", f"d_adj={d_adj_esp:.4f}", "mm")

    max_err_si = 0.0
    for i in range(5):
        err = abs(np.linalg.norm(
            geometria[ids_superior[i]].mean(axis=0)
            - geometria[ids_inferior[i]].mean(axis=0)
        ) - d_adj_esp)
        if err > max_err_si:
            max_err_si = err
    add("Adyacencia antiprismatica (sup_i, inf_i)", max_err_si < tol_mm,
        f"{max_err_si:.6f}", f"d_adj={d_adj_esp:.4f}", "mm")

    normales = []
    for esq in geometria.values():
        n = esq.mean(axis=0)
        normales.append(n / np.linalg.norm(n))
    normales.append(np.array([0.0, 0.0, -1.0]))
    suma_norm = np.linalg.norm(np.sum(normales, axis=0))
    add("Simetria: suma de 12 normales ~ 0", suma_norm < 1e-10,
        f"{suma_norm:.2e}", "< 1e-10")

    max_err_lado = 0.0
    for esq in geometria.values():
        for i in range(4):
            err = abs(np.linalg.norm(esq[i] - esq[(i + 1) % 4]) - marker_mm)
            if err > max_err_lado:
                max_err_lado = err
    add("Esquinas forman cuadrado de lado marker_mm",
        max_err_lado < tol_mm, f"{max_err_lado:.6f}", f"{marker_mm}", "mm")

    if verbose:
        print(f"\n{'='*78}\nVALIDACION GEOMETRICA EXHAUSTIVA\n{'='*78}")
        print(f"Parametros: edge={edge_mm} mm, marker={marker_mm} mm")
        print(f"             id_top={id_top}, ids_sup={ids_superior}, ids_inf={ids_inferior}")
        print(f"Esperados: r_in={r_in_esp:.4f} mm, d_adj={d_adj_esp:.4f} mm, "
              f"dihedral={DIHEDRAL_DEG:.3f} deg, diam_cara={diam:.3f} mm")
        print(f"Tolerancia: {tol_mm} mm")
        print("-" * 78)
        for nombre, ok, v, e, u in chequeos:
            estado = "PASS" if ok else "FAIL"
            extra = f"  [{v} vs {e} {u}]" if v or e else ""
            print(f"  [{estado}] {nombre}{extra}")
        print("-" * 78)

    ok_todos = all(c[1] for c in chequeos)
    if verbose:
        print(f"RESULTADO: {'TODOS PASS' if ok_todos else 'HAY FAILS'}\n")
    return ok_todos


def guardar_archivo(geometria, output_path, edge_mm=DEFAULT_EDGE_MM,
                    marker_mm=DEFAULT_MARKER_MM):
    """Guarda en formato reference.txt compatible con tracker.py."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    r_in = inradius(edge_mm)
    ids_sorted = sorted(geometria.keys())

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Geometria TEORICA del dodecaedro multi-marker\n")
        f.write(f"# IDs: {ids_sorted}\n")
        f.write(f"# Arista del dodecaedro: {edge_mm} mm\n")
        f.write(f"# Tamano del marker: {marker_mm} mm\n")
        f.write(f"# Radio inscrito: {r_in:.4f} mm\n")
        f.write("# Convencion esquinas (OpenCV ArUco): c0=TL c1=TR c2=BR c3=BL\n")
        f.write("# Convencion fisica: label apunta hacia +Z (hacia la punta)\n")
        f.write("# Formato: tag_id  cx cy cz  c0x c0y c0z  c1x c1y c1z  c2x c2y c2z  c3x c3y c3z\n")
        f.write("#\n")
        for tag_id in ids_sorted:
            esquinas = geometria[tag_id]
            centro = esquinas.mean(axis=0)
            valores = list(centro) + list(esquinas.flatten())
            linea = f"{tag_id:3d}   " + "  ".join(f"{v:+8.3f}" for v in valores)
            f.write(linea + "\n")


def _parse_int_list(s):
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Genera reference_dodecaedro.txt (geometria teorica).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--output", default="data/reference_dodecaedro.txt")
    parser.add_argument("--edge-mm", type=float, default=DEFAULT_EDGE_MM)
    parser.add_argument("--marker-mm", type=float, default=DEFAULT_MARKER_MM)
    parser.add_argument("--id-top", type=int, default=DEFAULT_ID_TOP)
    parser.add_argument("--ids-superior", type=_parse_int_list,
                        default=DEFAULT_IDS_SUPERIOR)
    parser.add_argument("--ids-inferior", type=_parse_int_list,
                        default=DEFAULT_IDS_INFERIOR)
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    print("Generando geometria teorica del dodecaedro...")
    print(f"  edge={args.edge_mm} mm, marker={args.marker_mm} mm")
    print(f"  id_top={args.id_top}, ids_sup={args.ids_superior}, ids_inf={args.ids_inferior}")

    geometria = construir_dodecaedro(
        edge_mm=args.edge_mm, marker_mm=args.marker_mm,
        id_top=args.id_top,
        ids_superior=args.ids_superior, ids_inferior=args.ids_inferior,
    )

    if not args.no_validate:
        ok = validar_geometria(
            geometria, edge_mm=args.edge_mm, marker_mm=args.marker_mm,
            id_top=args.id_top,
            ids_superior=args.ids_superior, ids_inferior=args.ids_inferior,
        )
        if not ok:
            raise SystemExit("ERROR: la validacion fallo. No se guarda el archivo.")

    guardar_archivo(geometria, args.output,
                    edge_mm=args.edge_mm, marker_mm=args.marker_mm)
    print(f"\nArchivo generado: {args.output}")
    print(f"Total marcadores: {len(geometria)}")


if __name__ == "__main__":
    main()
