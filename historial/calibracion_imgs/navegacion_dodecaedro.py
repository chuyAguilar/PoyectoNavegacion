#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Navegación Quirúrgica - Versión con Dodecaedro ArUco
===============================================================

Versión optimizada que soporta:
- Columna: Marcador único (ID 0)
- Lezna: Dodecaedro con múltiples IDs (1-12)
  → Detecta automáticamente la cara más visible
  → Tracking continuo en cualquier orientación

Combina lo mejor de tu código existente con navegación relativa avanzada.

Uso:
    python navegacion_dodecaedro.py
    
    Opciones:
    --test-mode : Sin enviar a Slicer
    --no-filter : Sin filtro de suavizado
    --no-csv : Sin guardar CSV

Autor: Adaptado al proyecto de navegación quirúrgica
Fecha: 2025-11-24
"""

import cv2
import cv2.aruco as aruco
import numpy as np
import csv
import time
import json
import os
import argparse
from datetime import datetime

# Intentar importar pyigtl
try:
    import pyigtl
except ImportError:
    print("⚠️  pyigtl no instalado. Modo Slicer desactivado.")
    pyigtl = None

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# IDs de cámaras
CAMERA_LEFT_ID = 1
CAMERA_RIGHT_ID = 2

# IDs de marcadores ArUco
# Referencia: Se carga desde ref_rigidbody.json o usa ID 0 por defecto
ARUCO_ID_COLUMNA = 0
# Lezna: Dodecaedro (IDs 1-12)
ARUCO_IDS_LEZNA = range(1, 13)

# Diccionario ArUco
ARUCO_DICT = aruco.DICT_4X4_50

# Tamaño del marcador en metros
MARKER_SIZE = 0.05  # 5 cm

# Archivo de calibración estéreo
PARAMS_FILE = "parametros_calibracion_stereo.npz"

# Archivo de calibración de escala
SCALE_CONFIG_FILE = "config_calibracion.json"

# Configuración OpenIGTLink
IGTL_HOST = "127.0.0.1"
IGTL_PORT = 18944
TRANSFORM_NAME = "LeznaToColumna"

# Filtro de suavizado
ALPHA_FILTER = 0.1

# Archivos CSV
CSV_FILE = "navegacion_dodecaedro.csv"

# Resolución
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# ============================================================================
# CLASE PARA FILTRO DE SUAVIZADO
# ============================================================================

class ExponentialFilter:
    """Filtro EMA para suavizar transformaciones"""
    
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.prev_transform = None
    
    def filter(self, transform):
        if self.prev_transform is None:
            self.prev_transform = transform.copy()
            return transform
        
        filtered = self.alpha * transform + (1 - self.alpha) * self.prev_transform
        self.prev_transform = filtered.copy()
        return filtered
    
    def reset(self):
        self.prev_transform = None

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def cargar_parametros_calibracion():
    """Carga parámetros de calibración estéreo"""
    if not os.path.exists(PARAMS_FILE):
        print(f"❌ ERROR: No se encontró '{PARAMS_FILE}'")
        print("   Ejecuta primero: python calibracion_stereo_adaptada.py")
        return None
    
    data = np.load(PARAMS_FILE)
    
    params = {
        'mtx_left': data['mtx_left'],
        'dist_left': data['dist_left'],
        'mtx_right': data['mtx_right'],
        'dist_right': data['dist_right'],
        'R': data['R'],
        'T': data['T']
    }
    
    print("✅ Parámetros de calibración estéreo cargados")
    return params


def cargar_factor_escala():
    """Carga el factor de escala desde config_calibracion.json"""
    if not os.path.exists(SCALE_CONFIG_FILE):
        print(f"⚠️  No se encontró '{SCALE_CONFIG_FILE}'. Usando factor=1000")
        return 1000.0  # Default: asumir metros a mm
    
    try:
        with open(SCALE_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        factor = config.get('factor_escala', 1000.0)
        print(f"✅ Factor de escala cargado: {factor:.4f}")
        return factor
    except Exception as e:
        print(f"⚠️  Error cargando factor de escala: {e}")
        return 1000.0


def detectar_aruco(frame, aruco_detector, mtx, dist):
    """Detecta marcadores ArUco y estima poses"""
    frame_undistorted = cv2.undistort(frame, mtx, dist, None, mtx)
    
    gray = cv2.cvtColor(frame_undistorted, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = aruco_detector.detectMarkers(gray)
    
    rvecs, tvecs = None, None
    
    if ids is not None and len(ids) > 0:
        rvecs = []
        tvecs = []
        for i in range(len(ids)):
            obj_points = np.array([[-MARKER_SIZE/2, MARKER_SIZE/2, 0],
                                   [MARKER_SIZE/2, MARKER_SIZE/2, 0],
                                   [MARKER_SIZE/2, -MARKER_SIZE/2, 0],
                                   [-MARKER_SIZE/2, -MARKER_SIZE/2, 0]], dtype=np.float32)
            _, rvec, tvec = cv2.solvePnP(obj_points, corners[i], mtx, dist)
            rvecs.append(rvec)
            tvecs.append(tvec)
        rvecs = np.array(rvecs)
        tvecs = np.array(tvecs)
    
    return frame_undistorted, corners, ids, rvecs, tvecs


def encontrar_mejor_marcador_lezna(ids, rvecs, tvecs):
    """
    Encuentra el marcador del dodecaedro más visible (más frontal a la cámara)
    
    Criterio: El marcador cuyo eje Z apunta más hacia la cámara
    """
    if ids is None or len(ids) == 0:
        return None, None, None, None
    
    mejor_id = None
    mejor_rvec = None
    mejor_tvec = None
    mejor_score = -1
    
    for i, marker_id in enumerate(ids.flatten()):
        if marker_id in ARUCO_IDS_LEZNA:
            # Convertir rvec a matriz de rotación
            R, _ = cv2.Rodrigues(rvecs[i])
            
            # El eje Z del marcador en coordenadas de cámara
            z_axis = R[:, 2]
            
            # Score: producto punto con eje Z de la cámara (0, 0, 1)
            # Cuanto más cercano a -1, más frontal está el marcador
            score = -z_axis[2]
            
            if score > mejor_score:
                mejor_score = score
                mejor_id = marker_id
                mejor_rvec = rvecs[i]
                mejor_tvec = tvecs[i]
    
    return mejor_id, mejor_rvec, mejor_tvec, mejor_score


def triangular_punto_3d(pt_left, pt_right, params):
    """Triangula un punto 3D desde dos vistas"""
    P_left = params['mtx_left'] @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P_right = params['mtx_right'] @ np.hstack([params['R'], params['T'].reshape(3, 1)])
    
    pt_4d = cv2.triangulatePoints(P_left, P_right, pt_left, pt_right)
    pt_3d = pt_4d[:3] / pt_4d[3]
    
    return pt_3d.flatten()


def calcular_posicion_3d_aruco(rvec_left, tvec_left, rvec_right, tvec_right, params):
    """Calcula posición 3D del marcador mediante triangulación estéreo"""
    centro_marcador = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    
    pts_2d_left, _ = cv2.projectPoints(
        centro_marcador, rvec_left, tvec_left,
        params['mtx_left'], params['dist_left']
    )
    
    pts_2d_right, _ = cv2.projectPoints(
        centro_marcador, rvec_right, tvec_right,
        params['mtx_right'], params['dist_right']
    )
    
    pt_left = pts_2d_left[0][0].reshape(2, 1)
    pt_right = pts_2d_right[0][0].reshape(2, 1)
    
    posicion_3d = triangular_punto_3d(pt_left, pt_right, params)
    
    return posicion_3d


def crear_matriz_transformacion(rvec, tvec):
    """Crea matriz de transformación 4x4"""
    R, _ = cv2.Rodrigues(rvec)
    
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = tvec.flatten()
    
    return T


def calcular_transformacion_relativa(T_columna, T_lezna):
    """Calcula transformación relativa: Lezna respecto a Columna"""
    T_columna_inv = np.linalg.inv(T_columna)
    T_relativa = T_columna_inv @ T_lezna
    
    return T_relativa


def enviar_transformacion_slicer(client, transform, nombre):
    """Envía transformación a Slicer vía OpenIGTLink"""
    if client is None or pyigtl is None:
        return False
    
    try:
        transform_msg = pyigtl.TransformMessage(transform, device_name=nombre)
        client.send_message(transform_msg)
        return True
    except Exception as e:
        print(f"❌ Error al enviar a Slicer: {e}")
        return False


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Navegación con dodecaedro ArUco')
    parser.add_argument('--test-mode', action='store_true')
    parser.add_argument('--no-filter', action='store_true')
    parser.add_argument('--no-csv', action='store_true')
    args = parser.parse_args()
    
    print("=" * 70)
    print("NAVEGACIÓN QUIRÚRGICA - DODECAEDRO ARUCO")
    print("=" * 70)
    print(f"Cámara izquierda:  Índice {CAMERA_LEFT_ID}")
    print(f"Cámara derecha:    Índice {CAMERA_RIGHT_ID}")
    print(f"ArUco Columna:     ID {ARUCO_ID_COLUMNA}")
    print(f"ArUco Lezna:       IDs {min(ARUCO_IDS_LEZNA)}-{max(ARUCO_IDS_LEZNA)} (dodecaedro)")
    print("=" * 70)
    
    params = cargar_parametros_calibracion()
    if params is None:
        return
    
    # Cargar factor de escala
    factor_escala = cargar_factor_escala()
    
    print("\n📹 Inicializando cámaras...")
    cap_left = cv2.VideoCapture(CAMERA_LEFT_ID)
    cap_right = cv2.VideoCapture(CAMERA_RIGHT_ID)
    
    if not cap_left.isOpened() or not cap_right.isOpened():
        print("❌ ERROR: No se pudieron abrir las cámaras")
        return
    
    cap_left.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap_left.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap_right.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap_right.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    print("✅ Cámaras inicializadas")
    
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    aruco_params = aruco.DetectorParameters()
    aruco_detector = aruco.ArucoDetector(aruco_dict, aruco_params)
    
    filtro = None if args.no_filter else ExponentialFilter(alpha=ALPHA_FILTER)
    
    igtl_client = None
    if not args.test_mode and pyigtl is not None:
        print(f"\n🔌 Conectando con Slicer ({IGTL_HOST}:{IGTL_PORT})...")
        try:
            igtl_client = pyigtl.OpenIGTLinkClient(host=IGTL_HOST, port=IGTL_PORT)
            print("✅ Conectado con Slicer")
        except Exception as e:
            print(f"⚠️  No se pudo conectar: {e}")
    
    csv_file = None
    csv_writer = None
    if not args.no_csv:
        csv_file = open(CSV_FILE, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            'timestamp', 'lezna_id_visible', 'columna_x', 'columna_y', 'columna_z',
            'lezna_x', 'lezna_y', 'lezna_z', 'distancia_mm',
            'rel_x', 'rel_y', 'rel_z'
        ])
        print(f"✅ Guardando datos en '{CSV_FILE}'")
    
    cv2.namedWindow('Navegacion Dodecaedro', cv2.WINDOW_NORMAL)
    
    print("\n" + "=" * 70)
    print("INSTRUCCIONES:")
    print("=" * 70)
    print(f"- Marcador ID {ARUCO_ID_COLUMNA}: Pegar en la COLUMNA")
    print(f"- Dodecaedro IDs {min(ARUCO_IDS_LEZNA)}-{max(ARUCO_IDS_LEZNA)}: Pegar en la LEZNA")
    print("- El sistema detectará automáticamente la cara más visible del dodecaedro")
    print("- Presiona 'q' para salir, 'r' para reiniciar filtro")
    print("=" * 70)
    
    fps_counter = 0
    fps_start = time.time()
    current_fps = 0
    
    frame_count = 0
    
    while True:
        ret_left, frame_left = cap_left.read()
        ret_right, frame_right = cap_right.read()
        
        frame_count += 1
        if frame_count == 1:
            print(f"📷 Frame 1: Izq={ret_left}, Der={ret_right}")
        
        if not ret_left or not ret_right:
            print(f"❌ ERROR en frame {frame_count}: Izq={ret_left}, Der={ret_right}")
            if not ret_left:
                print("   → Cámara IZQUIERDA (1) no captura")
            if not ret_right:
                print("   → Cámara DERECHA (2) no captura")
            break
        
        # Detectar ArUcos
        frame_left_undist, corners_left, ids_left, rvecs_left, tvecs_left = detectar_aruco(
            frame_left, aruco_detector,
            params['mtx_left'], params['dist_left']
        )
        
        frame_right_undist, corners_right, ids_right, rvecs_right, tvecs_right = detectar_aruco(
            frame_right, aruco_detector,
            params['mtx_right'], params['dist_right']
        )
        
        frame_vis = frame_left_undist.copy()
        
        # Dibujar marcadores detectados
        if ids_left is not None:
            frame_vis = aruco.drawDetectedMarkers(frame_vis, corners_left, ids_left)
            for i in range(len(ids_left)):
                c = corners_left[i][0]
                x, y = int(c[0][0]), int(c[0][1]) - 10
                cv2.putText(
                    frame_vis, f'ID: {ids_left[i][0]}', (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2
                )
        
        columna_detectada = False
        lezna_detectada = False
        lezna_id_visible = None
        
        info_text = []
        info_color = (0, 165, 255)
        
        if ids_left is not None and ids_right is not None:
            # Buscar columna
            idx_col_left = np.where(ids_left == ARUCO_ID_COLUMNA)[0]
            idx_col_right = np.where(ids_right == ARUCO_ID_COLUMNA)[0]
            
            # Debug: mostrar detección por cámara
            col_L = "L:✓" if len(idx_col_left) > 0 else "L:✗"
            col_R = "R:✓" if len(idx_col_right) > 0 else "R:✗"
            cv2.putText(frame_vis, f"Col0: {col_L} {col_R}", (10, frame_vis.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            columna_detectada = len(idx_col_left) > 0 and len(idx_col_right) > 0
            
            # Buscar mejor marcador del dodecaedro
            lezna_id_left, rvec_lez_l, tvec_lez_l, score_left = encontrar_mejor_marcador_lezna(
                ids_left, rvecs_left, tvecs_left
            )
            lezna_id_right, rvec_lez_r, tvec_lez_r, score_right = encontrar_mejor_marcador_lezna(
                ids_right, rvecs_right, tvecs_right
            )
            
            lezna_detectada = lezna_id_left is not None and lezna_id_right is not None
            
            if columna_detectada and lezna_detectada:
                # Triangular posiciones
                rvec_col_l = rvecs_left[idx_col_left[0]]
                tvec_col_l = tvecs_left[idx_col_left[0]]
                rvec_col_r = rvecs_right[idx_col_right[0]]
                tvec_col_r = tvecs_right[idx_col_right[0]]
                
                pos_columna = calcular_posicion_3d_aruco(
                    rvec_col_l, tvec_col_l, rvec_col_r, tvec_col_r, params
                )
                
                pos_lezna = calcular_posicion_3d_aruco(
                    rvec_lez_l, tvec_lez_l, rvec_lez_r, tvec_lez_r, params
                )
                
                # Transformaciones
                T_columna = crear_matriz_transformacion(rvec_col_l, pos_columna)
                T_lezna = crear_matriz_transformacion(rvec_lez_l, pos_lezna)
                
                T_relativa = calcular_transformacion_relativa(T_columna, T_lezna)
                
                if filtro is not None:
                    T_relativa = filtro.filter(T_relativa)
                
                T_relativa_mm = T_relativa.copy()
                T_relativa_mm[:3, 3] *= factor_escala  # Aplicar factor de escala calibrado
                
                if igtl_client is not None:
                    if enviar_transformacion_slicer(igtl_client, T_relativa_mm, TRANSFORM_NAME):
                        # Debug: mostrar que se envió
                        print(f"📡 Enviado: X={T_relativa_mm[0,3]:.1f} Y={T_relativa_mm[1,3]:.1f} Z={T_relativa_mm[2,3]:.1f}")
                
                distancia_mm = np.linalg.norm(T_relativa_mm[:3, 3])
                lezna_id_visible = lezna_id_left
                
                if csv_writer is not None:
                    timestamp = time.time()
                    csv_writer.writerow([
                        timestamp, lezna_id_visible,
                        pos_columna[0]*factor_escala, pos_columna[1]*factor_escala, pos_columna[2]*factor_escala,
                        pos_lezna[0]*factor_escala, pos_lezna[1]*factor_escala, pos_lezna[2]*factor_escala,
                        distancia_mm,
                        T_relativa_mm[0,3], T_relativa_mm[1,3], T_relativa_mm[2,3]
                    ])
                
                info_text = [
                    f"Estado: NAVEGANDO",
                    f"Cara visible: ID {lezna_id_visible} (Score: {score_left:.2f})",
                    f"Distancia: {distancia_mm:.1f} mm",
                    f"Pos Relativa: X={T_relativa_mm[0,3]:.1f} Y={T_relativa_mm[1,3]:.1f} Z={T_relativa_mm[2,3]:.1f}",
                    f"FPS: {current_fps:.1f}"
                ]
                info_color = (0, 255, 0)
                
                cv2.drawFrameAxes(frame_vis, params['mtx_left'], params['dist_left'],
                                 rvec_col_l, tvec_col_l, MARKER_SIZE/2)
                cv2.drawFrameAxes(frame_vis, params['mtx_left'], params['dist_left'],
                                 rvec_lez_l, tvec_lez_l, MARKER_SIZE/2)
        
        if not columna_detectada or not lezna_detectada:
            info_text = [
                f"Columna (ID {ARUCO_ID_COLUMNA}): {'OK' if columna_detectada else 'NO DETECTADA'}",
                f"Lezna (IDs {min(ARUCO_IDS_LEZNA)}-{max(ARUCO_IDS_LEZNA)}): {'OK' if lezna_detectada else 'NO DETECTADA'}",
                f"FPS: {current_fps:.1f}"
            ]
            info_color = (0, 165, 255)
        
        y_offset = 30
        for i, line in enumerate(info_text):
            cv2.putText(frame_vis, line, (10, y_offset + i * 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
        
        cv2.imshow('Navegacion Dodecaedro', frame_vis)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print(f"\n✅ Navegación finalizada (tecla 'q' detectada en frame {frame_count})")
            break
        elif key != 255:  # 255 significa que no se presionó nada
            print(f"Tecla detectada: {key} (frame {frame_count})")
        elif key == ord('r'):
            if filtro is not None:
                filtro.reset()
                print("\n🔄 Filtro reiniciado")
        
        fps_counter += 1
        if time.time() - fps_start >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_start = time.time()
    
    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()
    
    if csv_file is not None:
        csv_file.close()
        print(f"✅ Datos guardados en '{CSV_FILE}'")
    
    # if igtl_client is not None:
    #     igtl_client.stop()  # pyigtl no tiene close(), a veces tiene stop() o nada
    
    print("\n✅ Sistema finalizado")


if __name__ == "__main__":
    main()
