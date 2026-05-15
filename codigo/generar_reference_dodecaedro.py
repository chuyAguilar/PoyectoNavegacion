"""
Genera reference_dodecaedro.txt para el dodecaedro V1 con IDs 151-161.

==========================================================================
ADVERTENCIA (recuperacion 2026-05-14, Fase 1 de auditoria iter 2):

Este script fue recuperado desde una conversacion previa porque el original
no estaba versionado en el repo. Al ejecutarlo y comparar con el
reference_dodecaedro.txt que SI existe en data/, los resultados son:

  - ID 151 (TOP): identico al 100%.
  - IDs 152-161: centros identicos, pero las 4 esquinas estan rotadas
                 ciclicamente 90 grados (c0 nuevo = c3 viejo, c1 = c0, etc.).

La fuente de verdad sigue siendo data/reference_dodecaedro.txt, porque
ese fue el que sirvio de semilla al bundle adjustment exitoso (RMSE 0.61 px)
y todo el pipeline downstream (tracker, pivote, registro) ya esta validado
contra el. Este script queda como referencia historica de la matematica
generadora, NO regenerar data/reference_dodecaedro.txt con el sin antes
auditar la convencion de orden de esquinas en Fase 3.
==========================================================================

Convencion (iteracion 1):
  ID 151: cara TOP (eje +Z)
  IDs 152-156: cinturon superior (azimuts 0, 72, 144, 216, 288 deg)
  IDs 157-161: cinturon inferior (azimuts 36, 108, 180, 252, 324 deg)

Geometria:
  Arista del dodecaedro: 20 mm (medida real del impreso)
  Tamanio de marcador: 16 mm
  Configuracion: antiprismatica (cinturon inferior offset 36 deg respecto al superior)

Formato del archivo:
  tag_id  cx cy cz  c0x c0y c0z  c1x c1y c1z  c2x c2y c2z  c3x c3y c3z
  donde c0, c1, c2, c3 son las 4 esquinas del marcador en orden:
    c0: top-left, c1: top-right, c2: bottom-right, c3: bottom-left
  El orden corresponde a la convencion de OpenCV ArUco.
"""
import numpy as np

# ============================================================================
# PARAMETROS GEOMETRICOS
# ============================================================================

# Constante geometrica del dodecaedro regular
PHI = (1 + np.sqrt(5)) / 2

# Arista del dodecaedro (medida real del impreso)
EDGE_MM = 20.0

# Tamanio del marcador (medido real del impreso)
MARKER_MM = 16.0

# Radio inscrito (distancia del centro del dodecaedro a una cara)
R_IN = EDGE_MM * PHI**2 / (2 * np.sqrt(3 - PHI))

# Angulo polar de las caras del cinturon (desde el eje +Z)
THETA = np.arccos(1 / np.sqrt(5))


# ============================================================================
# CONVENCION DE IDs (ITERACION 1)
# ============================================================================

# IDs por posicion en el dodecaedro
ID_TOP = 151
IDS_SUPERIOR = [152, 153, 154, 155, 156]   # azimuts 0, 72, 144, 216, 288
IDS_INFERIOR = [157, 158, 159, 160, 161]   # azimuts 36, 108, 180, 252, 324


# ============================================================================
# FUNCIONES GEOMETRICAS
# ============================================================================

def rotation_matrix(axis, angle):
    """Matriz de rotacion 3x3 alrededor de un eje (Rodrigues)."""
    axis = np.array(axis) / np.linalg.norm(axis)
    a = np.cos(angle / 2)
    b, c, d = -axis * np.sin(angle / 2)
    return np.array([
        [a*a + b*b - c*c - d*d, 2*(b*c - a*d), 2*(b*d + a*c)],
        [2*(b*c + a*d), a*a + c*c - b*b - d*d, 2*(c*d - a*b)],
        [2*(b*d - a*c), 2*(c*d + a*b), a*a + d*d - b*b - c*c]
    ])


def construir_cara(centro, normal, rotacion_propia=0):
    """Construye las 4 esquinas de un marcador en una cara del dodecaedro.

    Args:
        centro: posicion 3D del centro de la cara
        normal: vector normal a la cara (apunta hacia afuera)
        rotacion_propia: angulo (rad) de rotacion del marcador alrededor de su normal

    Returns:
        Array (4, 3) con las 4 esquinas en el orden top-left, top-right, bottom-right, bottom-left
    """
    # Sistema de coordenadas local de la cara:
    # - eje z local = normal (apunta hacia afuera)
    # - eje x local = perpendicular a la normal, en un plano elegido consistentemente
    # - eje y local = z x x
    # Para que el sistema sea consistente, elegimos x como la proyeccion
    # del eje Z global sobre el plano de la cara
    z_global = np.array([0, 0, 1])

    # Si la cara mira hacia arriba o abajo, usar eje X global como referencia
    if abs(np.dot(normal, z_global)) > 0.99:
        x_ref = np.array([1, 0, 0])
    else:
        x_ref = z_global

    # Proyectar x_ref sobre el plano de la cara
    x_local = x_ref - np.dot(x_ref, normal) * normal
    x_local = x_local / np.linalg.norm(x_local)

    # Aplicar rotacion propia del marcador
    if rotacion_propia != 0:
        R = rotation_matrix(normal, rotacion_propia)
        x_local = R @ x_local

    y_local = np.cross(normal, x_local)
    y_local = y_local / np.linalg.norm(y_local)

    # Las 4 esquinas del marcador (en sistema local, luego trasladar)
    half = MARKER_MM / 2
    esquinas_locales = [
        np.array([-half,  half, 0]),  # c0: top-left
        np.array([ half,  half, 0]),  # c1: top-right
        np.array([ half, -half, 0]),  # c2: bottom-right
        np.array([-half, -half, 0]),  # c3: bottom-left
    ]

    # Transformar a sistema global
    R_local_to_global = np.column_stack([x_local, y_local, normal])
    esquinas_globales = np.array([centro + R_local_to_global @ esq for esq in esquinas_locales])

    return esquinas_globales


# ============================================================================
# CONSTRUCCION DEL DODECAEDRO
# ============================================================================

def construir_dodecaedro():
    """Devuelve dict {tag_id: 4x3 esquinas} para los 11 marcadores."""
    geometria = {}

    # === Cara TOP (ID 151) ===
    centro_top = np.array([0, 0, R_IN])
    normal_top = np.array([0, 0, 1])
    geometria[ID_TOP] = construir_cara(centro_top, normal_top)

    # === Cinturon superior (IDs 152-156) ===
    for i, tag_id in enumerate(IDS_SUPERIOR):
        azimut = i * (2 * np.pi / 5)  # 0, 72, 144, 216, 288 deg
        centro = np.array([
            np.sin(THETA) * np.cos(azimut),
            np.sin(THETA) * np.sin(azimut),
            np.cos(THETA)
        ]) * R_IN
        normal = centro / np.linalg.norm(centro)
        geometria[tag_id] = construir_cara(centro, normal)

    # === Cinturon inferior (IDs 157-161) ===
    for i, tag_id in enumerate(IDS_INFERIOR):
        azimut = i * (2 * np.pi / 5) + np.pi / 5  # offset 36 deg
        centro = np.array([
            np.sin(THETA) * np.cos(azimut),
            np.sin(THETA) * np.sin(azimut),
            -np.cos(THETA)
        ]) * R_IN
        normal = centro / np.linalg.norm(centro)
        geometria[tag_id] = construir_cara(centro, normal)

    return geometria


# ============================================================================
# GUARDAR ARCHIVO
# ============================================================================

def guardar_archivo(geometria, output_path):
    """Guarda en formato reference.txt compatible con tracker.py."""
    with open(output_path, "w") as f:
        f.write(f"# Geometria TEORICA del dodecaedro V1\n")
        f.write(f"# IDs: 151-161 (TOP, cinturon superior, cinturon inferior)\n")
        f.write(f"# Arista: {EDGE_MM} mm\n")
        f.write(f"# Marcador: {MARKER_MM} mm\n")
        f.write(f"# Radio inscrito: {R_IN:.4f} mm\n")
        f.write(f"# Formato: tag_id  cx cy cz  c0x c0y c0z  c1x c1y c1z  c2x c2y c2z  c3x c3y c3z\n")
        f.write(f"#\n")

        # Ordenar por ID
        for tag_id in sorted(geometria.keys()):
            esquinas = geometria[tag_id]
            centro = esquinas.mean(axis=0)
            valores = list(centro) + list(esquinas.flatten())
            linea = f"{tag_id:3d}   " + "  ".join(f"{v:+8.3f}" for v in valores)
            f.write(linea + "\n")


# ============================================================================
# VALIDACION DE ADYACENCIAS
# ============================================================================

def validar_geometria(geometria):
    """Imprime distancias entre caras para validar la geometria."""
    print("\n=== VALIDACION GEOMETRICA ===")
    print(f"Radio inscrito teorico: {R_IN:.3f} mm")
    print(f"Arista: {EDGE_MM} mm")
    print(f"Marcador: {MARKER_MM} mm")

    # Distancia entre caras adyacentes en dodecaedro regular
    centro_top = geometria[ID_TOP].mean(axis=0)
    centro_sup0 = geometria[IDS_SUPERIOR[0]].mean(axis=0)
    d_adj = np.linalg.norm(centro_top - centro_sup0)
    print(f"\nDistancia TOP-Sup_0 (caras adyacentes): {d_adj:.3f} mm")

    print(f"\nValidacion clave: ID 152 (Sup_0) e ID 157 (Inf_0) deben compartir arista")
    centro_152 = geometria[152].mean(axis=0)
    centro_157 = geometria[157].mean(axis=0)
    d_152_157 = np.linalg.norm(centro_152 - centro_157)
    print(f"Distancia ID152-ID157: {d_152_157:.3f} mm")

    if abs(d_152_157 - d_adj) < 0.5:
        print(f"  OK: comparten arista (distancia {d_152_157:.2f} ~ {d_adj:.2f} mm)")
    else:
        print(f"  ERROR: NO comparten arista")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("Generando geometria teorica del dodecaedro V1 (IDs 151-161)...")
    geometria = construir_dodecaedro()
    validar_geometria(geometria)

    output_path = "reference_dodecaedro.txt"
    guardar_archivo(geometria, output_path)
    print(f"\nArchivo generado: {output_path}")
    print(f"Total marcadores: {len(geometria)}")

    print("\n=== POSICIONES DE CENTROS ===")
    for tag_id in sorted(geometria.keys()):
        centro = geometria[tag_id].mean(axis=0)
        print(f"  ID {tag_id:3d}: ({centro[0]:+7.2f}, {centro[1]:+7.2f}, {centro[2]:+7.2f}) mm")
