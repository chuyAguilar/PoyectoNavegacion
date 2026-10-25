"""
Pose multi-marker de un rigid body (el dodecaedro), sacada tal cual de
codigo/tracker.py en la meta 003, fase 4 · El tracker en piezas (2026-10-24).

Es registro (ADR-025, ADR-026): el tracker sigue solo Marker0 y no la importa
nada vivo de codigo/. El instrumento nuevo de otra meta (B40) puede partir de
aqui. Las dos funciones son las que tenia tracker.py desde la iteracion 4 y la
iter 5 (rechazo de outliers), sin cambios.

  cargar_rigid_body(ruta)                            -> {tag_id: esquinas 3D (4x3)}
  estimar_pose_rigid_body(detecciones, geom, K, dist) -> (rvec, tvec, n_usados) | None
"""

import cv2
import numpy as np


def cargar_rigid_body(ruta):
    """Carga el archivo de geometria del rigid body.

    Formato: cada linea con tag_id, centro (3), 4 esquinas (12 valores)
    Devuelve dict {tag_id: array(4, 3) con las 4 esquinas en 3D}
    """
    rigid_body = {}
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            valores = linea.split()
            if len(valores) < 16:
                continue
            tag_id = int(valores[0])
            # valores[1:4] = centro (no lo usamos directamente, lo derivamos)
            # valores[4:7]   = c0 (top-left)
            # valores[7:10]  = c1 (top-right)
            # valores[10:13] = c2 (bottom-right)
            # valores[13:16] = c3 (bottom-left)
            esquinas = np.array([
                [float(valores[4]),  float(valores[5]),  float(valores[6])],
                [float(valores[7]),  float(valores[8]),  float(valores[9])],
                [float(valores[10]), float(valores[11]), float(valores[12])],
                [float(valores[13]), float(valores[14]), float(valores[15])],
            ], dtype=np.float32)
            rigid_body[tag_id] = esquinas

    print(f"[Rigid body] Cargados {len(rigid_body)} marcadores de {ruta}")
    return rigid_body


def estimar_pose_rigid_body(detecciones, rigid_body_geom, K, dist):
    """Pose conjunta de un rigid body usando todos los marcadores visibles.

    detecciones: dict {tag_id: corners_2d (shape 1x4x2)}
    rigid_body_geom: dict {tag_id: esquinas_3d (shape 4x3)}

    Combina los puntos 3D-2D de todos los marcadores visibles del rigid body
    y resuelve cv2.solvePnP con todos ellos. Esto es matematicamente optimo:
    aprovecha toda la informacion disponible para una sola estimacion robusta.

    Devuelve (rvec, tvec, n_marcadores_usados) o None si no se pudo resolver.
    """
    object_pts_list = []
    image_pts_list = []
    n_usados = 0

    for tag_id, corners_2d in detecciones.items():
        if tag_id not in rigid_body_geom:
            continue
        # Esquinas 3D en sistema del dodecaedro (4x3)
        obj_3d = rigid_body_geom[tag_id]
        # Esquinas 2D en imagen (4x2)
        img_2d = corners_2d.reshape(4, 2).astype(np.float32)
        object_pts_list.append(obj_3d)
        image_pts_list.append(img_2d)
        n_usados += 1

    if n_usados == 0:
        return None

    # Concatenar todos los puntos: shape (4*N, 3) y (4*N, 2)
    all_object_pts = np.concatenate(object_pts_list, axis=0).astype(np.float32)
    all_image_pts = np.concatenate(image_pts_list, axis=0).astype(np.float32)

    if n_usados == 1:
        # Con un solo marcador, IPPE_SQUARE devuelve las 2 soluciones espejadas.
        # solvePnPGeneric nos da ambas y elegimos la de menor reprojection error
        # CON tvec[2] > 0 (la otra suele tener el marker detras de la camara).
        n_sol, rvecs, tvecs, errors = cv2.solvePnPGeneric(
            all_object_pts, all_image_pts, K, dist,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if n_sol == 0:
            return None
        # Filtrar soluciones invalidas (z<=0)
        candidatos = [(i, errors[i][0] if errors is not None else 0.0)
                      for i in range(n_sol)
                      if float(tvecs[i][2, 0]) > 0]
        if not candidatos:
            return None
        # Tomar la de menor error de reproyeccion
        i_best = min(candidatos, key=lambda c: c[1])[0]
        rvec = rvecs[i_best]
        tvec = tvecs[i_best]
        ok = True
    else:
        # Con multiples marcadores no coplanares, ITERATIVE da mejor resultado
        # (IPPE_SQUARE es solo para puntos planares)
        ok, rvec, tvec = cv2.solvePnP(
            all_object_pts, all_image_pts, K, dist,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        if ok:
            # Refinamiento iterativo Levenberg-Marquardt
            rvec, tvec = cv2.solvePnPRefineLM(
                all_object_pts, all_image_pts, K, dist, rvec, tvec
            )

            # --- RECHAZO DE OUTLIERS (iter 5) ---
            # Un marcador mal detectado (esquina equivocada, casi coplanar,
            # intermitente) corrompe el PnP conjunto. Calculamos el error de
            # reproyeccion POR MARCADOR, descartamos los que se salen y
            # re-resolvemos solo con los buenos. Quita los picos de orientacion
            # que metia un marcador con reproyeccion alta (diagnostico estatico).
            errs = np.array([
                float(np.mean(np.linalg.norm(
                    cv2.projectPoints(obj_m, rvec, tvec, K, dist)[0].reshape(4, 2)
                    - img_m, axis=1)))
                for obj_m, img_m in zip(object_pts_list, image_pts_list)
            ])
            umbral = max(2.0, 2.5 * float(np.median(errs)))
            inliers = errs <= umbral
            # Requiere >=3 inliers (2 casi coplanares dan pose degenerada).
            if 3 <= int(inliers.sum()) < n_usados:
                obj_in = np.concatenate(
                    [object_pts_list[i] for i in range(n_usados) if inliers[i]],
                    axis=0).astype(np.float32)
                img_in = np.concatenate(
                    [image_pts_list[i] for i in range(n_usados) if inliers[i]],
                    axis=0).astype(np.float32)
                ok2, rvec2, tvec2 = cv2.solvePnP(
                    obj_in, img_in, K, dist, rvec.copy(), tvec.copy(),
                    useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
                if ok2:
                    rvec2, tvec2 = cv2.solvePnPRefineLM(obj_in, img_in, K, dist, rvec2, tvec2)
                    # ACEPTAR SOLO si la pose refinada esta CERCA de la original.
                    # Quitar un marcador malo refina (mm/grados), NO salta. Un salto
                    # grande = re-solve degenerado -> revertir a la pose con todos.
                    R1, _ = cv2.Rodrigues(rvec)
                    R2, _ = cv2.Rodrigues(rvec2)
                    d_ang = np.degrees(np.arccos(np.clip(
                        (np.trace(R1.T @ R2) - 1.0) / 2.0, -1.0, 1.0)))
                    d_t = float(np.linalg.norm(tvec2.flatten() - tvec.flatten()))
                    if d_ang < 15.0 and d_t < 20.0:
                        rvec, tvec = rvec2, tvec2
                        n_usados = int(inliers.sum())

    if not ok:
        return None

    # Filtro final: descartar poses con z<=0 (marker detras de la camara).
    # Aparece cuando los markers usados son casi coplanares y la solucion
    # se invierte (visto en log iter 4: t=[..., ..., -589.8] con 4 markers
    # del anillo inferior).
    if float(tvec[2, 0]) <= 0:
        return None

    return rvec, tvec, n_usados
