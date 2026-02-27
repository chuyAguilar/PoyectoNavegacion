#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Navegación Quirúrgica - Versión Final Adaptada
=========================================================

Script adaptado 100% al proyecto existente del usuario.

Combina lo mejor de:
- aruco_dos_camaras.py → Uso de 2 cámaras (índices 1 y 3)
- aruco_pose_cubo.py → Calibración real y corrección de distorsión
- aruco_pose_distancia.py → Cálculo de distancia entre marcadores
- aruco_pose_guardar.py → Guardado de datos en CSV

Mejoras agregadas:
- Triangulación estéreo REAL (no cámaras independientes)
- Navegación relativa (ID 0 = Columna, ID 4 = Lezna)
- Filtro de suavizado EMA
- Envío a 3D Slicer vía OpenIGTLink

Uso:
    python navegacion_quirurgica_final.py
    
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
    print("   Instalar con: pip install pyigtl")
    pyigtl = None

# ============================================================================
# CONFIGURACIÓN (ADAPTADA A TU PROYECTO)
# ============================================================================

# IDs de cámaras (TUS ÍNDICES)
CAMERA_LEFT_ID = 1   # Tu cámara física
CAMERA_RIGHT_ID = 3  # Tu OBS Virtual

# IDs de marcadores ArUco (BASADO EN TU CUBO)
ARUCO_ID_COLUMNA = 0  # Cubo pegado en la columna (referencia fija)
ARUCO_ID_LEZNA = 4    # Cubo pegado en la lezna (instrumento móvil)

# Diccionario ArUco
ARUCO_DICT = aruco.DICT_4X4_50

# Tamaño del marcador en metros
MARKER_SIZE = 0.05  # 5 cm (ajustar si tu cubo es diferente)

# Archivo de calibración estéreo
PARAMS_FILE = "parametros_calibracion_stereo.npz"

# Configuración OpenIGTLink
IGTL_HOST = "127.0.0.1"
IGTL_PORT = 18944
TRANSFORM_NAME = "LeznaToColumna"

# Filtro de suavizado
ALPHA_FILTER = 0.3  # 0 = máximo suavizado, 1 = sin suavizado

# Archivos CSV de salida
CSV_FILE = "navegacion_quirurgica.csv"

# Resolución de cámaras
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


def detectar_aruco(frame, aruco_dict, aruco_params, mtx, dist):
    """Detecta marcadores ArUco y estima poses"""
    # Corregir distorsión (como en tu aruco_pose_cubo.py)
    frame_undistorted = cv2.undistort(frame, mtx, dist, None, mtx)
    
    gray = cv2.cvtColor(frame_undistorted, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)
    
    rvecs, tvecs = None, None
    
    if ids is not None and len(ids) > 0:
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, MARKER_SIZE, mtx, dist
        )
    
    return frame_undistorted, corners, ids, rvecs, tvecs


def triangular_punto_3d(pt_left, pt_right, params):
    """Triangula un punto 3D desde dos vistas"""
    # Matrices de proyección
    P_left = params['mtx_left'] @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P_right = params['mtx_right'] @ np.hstack([params['R'], params['T'].reshape(3, 1)])
    
    # Triangular
    pt_4d = cv2.triangulatePoints(P_left, P_right, pt_left, pt_right)
    pt_3d = pt_4d[:3] / pt_4d[3]
    
    return pt_3d.flatten()


def calcular_posicion_3d_aruco(rvec_left, tvec_left, rvec_right, tvec_right, params):
    """Calcula posición 3D del marcador mediante triangulación estéreo"""
    centro_marcador = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    
    # Proyectar centro del marcador en ambas cámaras
    pts_2d_left, _ = cv2.projectPoints(
        centro_marcador, rvec_left, tvec_left,
        params['mtx_left'], params['dist_left']
    )
    
    pts_2d_right, _ = cv2.projectPoints(
        centro_marcador, rvec_right, tvec_right,
        params['mtx_right'], params['dist_right']
    )
    
    # Triangular
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
    # Parsear argumentos
    parser = argparse.ArgumentParser(description='Navegación quirúrgica adaptada')
    parser.add_argument('--test-mode', action='store_true',
                        help='Modo de prueba sin Slicer')
    parser.add_argument('--no-filter', action='store_true',
                        help='Desactivar filtro de suavizado')
    parser.add_argument('--no-csv', action='store_true',
                        help='No guardar CSV')
    args = parser.parse_args()
    
    print("=" * 70)
    print("NAVEGACIÓN QUIRÚRGICA - VERSIÓN FINAL ADAPTADA")
    print("=" * 70)
    print(f"Cámara izquierda:  Índice {CAMERA_LEFT_ID}")
    print(f"Cámara derecha:    Índice {CAMERA_RIGHT_ID}")
    print(f"ArUco Columna:     ID {ARUCO_ID_COLUMNA}")
    print(f"ArUco Lezna:       ID {ARUCO_ID_LEZNA}")
    print("=" * 70)
    
    # Cargar parámetros de calibración
    params = cargar_parametros_calibracion()
    if params is None:
        return
    
    # Inicializar cámaras (COMO EN TU CÓDIGO)
    print("\n📹 Inicializando cámaras...")
    cap_left = cv2.VideoCapture(CAMERA_LEFT_ID)
    cap_right = cv2.VideoCapture(CAMERA_RIGHT_ID, cv2.CAP_DSHOW)
    
    if not cap_left.isOpened() or not cap_right.isOpened():
        print("❌ ERROR: No se pudieron abrir las cámaras")
        return
    
    cap_left.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap_left.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap_right.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap_right.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    print("✅ Cámaras inicializadas")
    
    # Configurar detector ArUco
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    aruco_params = aruco.DetectorParameters()
    
    # Inicializar filtro
    filtro = None if args.no_filter else ExponentialFilter(alpha=ALPHA_FILTER)
    
    # Conectar con Slicer
    igtl_client = None
    if not args.test_mode and pyigtl is not None:
        print(f"\n🔌 Conectando con Slicer ({IGTL_HOST}:{IGTL_PORT})...")
        try:
            igtl_client = pyigtl.OpenIGTLinkClient(host=IGTL_HOST, port=IGTL_PORT)
            print("✅ Conectado con Slicer")
        except Exception as e:
            print(f"⚠️  No se pudo conectar: {e}")
    
    # Preparar CSV (COMO EN TU CÓDIGO)
    csv_file = None
    csv_writer = None
    if not args.no_csv:
        csv_file = open(CSV_FILE, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            'timestamp', 'columna_x', 'columna_y', 'columna_z',
            'lezna_x', 'lezna_y', 'lezna_z', 'distancia_mm',
            'rel_x', 'rel_y', 'rel_z'
        ])
        print(f"✅ Guardando datos en '{CSV_FILE}'")
    
    # Crear ventanas (COMO EN TU CÓDIGO)
    cv2.namedWindow('Navegacion Quirurgica', cv2.WINDOW_NORMAL)
    
    print("\n" + "=" * 70)
    print("INSTRUCCIONES:")
    print("=" * 70)
    print(f"- Cubo ArUco ID {ARUCO_ID_COLUMNA}: Pegar en la COLUMNA (referencia fija)")
    print(f"- Cubo ArUco ID {ARUCO_ID_LEZNA}: Pegar en la LEZNA (instrumento)")
    print("- Ambos cubos deben ser visibles en AMBAS cámaras")
    print("- Presiona 'q' para salir")
    print("- Presiona 'r' para reiniciar filtro")
    print("=" * 70)
    
    fps_counter = 0
    fps_start = time.time()
    current_fps = 0
    
    while True:
        # Capturar frames
        ret_left, frame_left = cap_left.read()
        ret_right, frame_right = cap_right.read()
        
        if not ret_left or not ret_right:
            print("❌ ERROR: No se pudo capturar frame")
            break
        
        # Detectar ArUcos en ambas cámaras
        frame_left_undist, corners_left, ids_left, rvecs_left, tvecs_left = detectar_aruco(
            frame_left, aruco_dict, aruco_params,
            params['mtx_left'], params['dist_left']
        )
        
        frame_right_undist, corners_right, ids_right, rvecs_right, tvecs_right = detectar_aruco(
            frame_right, aruco_dict, aruco_params,
            params['mtx_right'], params['dist_right']
        )
        
        # Frame para visualización
        frame_vis = frame_left_undist.copy()
        
        # Dibujar marcadores detectados (COMO EN TU CÓDIGO)
        if ids_left is not None:
            frame_vis = aruco.drawDetectedMarkers(frame_vis, corners_left, ids_left)
            for i in range(len(ids_left)):
                c = corners_left[i][0]
                x, y = int(c[0][0]), int(c[0][1]) - 10
                cv2.putText(
                    frame_vis,
                    f'ID: {ids_left[i][0]}',
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.5,
                    (0, 255, 0),
                    3,
                    cv2.LINE_AA
                )
        
        # Buscar ambos marcadores
        columna_detectada = False
        lezna_detectada = False
        
        info_text = []
        info_color = (0, 165, 255)  # Naranja
        
        if ids_left is not None and ids_right is not None:
            # Buscar marcador de columna
            idx_col_left = np.where(ids_left == ARUCO_ID_COLUMNA)[0]
            idx_col_right = np.where(ids_right == ARUCO_ID_COLUMNA)[0]
            
            # Buscar marcador de lezna
            idx_lez_left = np.where(ids_left == ARUCO_ID_LEZNA)[0]
            idx_lez_right = np.where(ids_right == ARUCO_ID_LEZNA)[0]
            
            columna_detectada = len(idx_col_left) > 0 and len(idx_col_right) > 0
            lezna_detectada = len(idx_lez_left) > 0 and len(idx_lez_right) > 0
            
            if columna_detectada and lezna_detectada:
                # Calcular posiciones 3D mediante triangulación
                rvec_col_l = rvecs_left[idx_col_left[0]]
                tvec_col_l = tvecs_left[idx_col_left[0]]
                rvec_col_r = rvecs_right[idx_col_right[0]]
                tvec_col_r = tvecs_right[idx_col_right[0]]
                
                rvec_lez_l = rvecs_left[idx_lez_left[0]]
                tvec_lez_l = tvecs_left[idx_lez_left[0]]
                rvec_lez_r = rvecs_right[idx_lez_right[0]]
                tvec_lez_r = tvecs_right[idx_lez_right[0]]
                
                # Triangular posiciones 3D
                pos_columna = calcular_posicion_3d_aruco(
                    rvec_col_l, tvec_col_l, rvec_col_r, tvec_col_r, params
                )
                
                pos_lezna = calcular_posicion_3d_aruco(
                    rvec_lez_l, tvec_lez_l, rvec_lez_r, tvec_lez_r, params
                )
                
                # Crear matrices de transformación
                T_columna = crear_matriz_transformacion(rvec_col_l, pos_columna)
                T_lezna = crear_matriz_transformacion(rvec_lez_l, pos_lezna)
                
                # Calcular transformación relativa
                T_relativa = calcular_transformacion_relativa(T_columna, T_lezna)
                
                # Aplicar filtro
                if filtro is not None:
                    T_relativa = filtro.filter(T_relativa)
                
                # Convertir a milímetros (como en tu código)
                T_relativa_mm = T_relativa.copy()
                T_relativa_mm[:3, 3] *= 1000  # metros a mm
                
                # Enviar a Slicer
                if igtl_client is not None:
                    enviar_transformacion_slicer(igtl_client, T_relativa_mm, TRANSFORM_NAME)
                
                # Calcular distancia (COMO EN TU CÓDIGO)
                distancia_mm = np.linalg.norm(T_relativa_mm[:3, 3])
                
                # Guardar en CSV
                if csv_writer is not None:
                    timestamp = time.time()
                    csv_writer.writerow([
                        timestamp,
                        pos_columna[0]*1000, pos_columna[1]*1000, pos_columna[2]*1000,
                        pos_lezna[0]*1000, pos_lezna[1]*1000, pos_lezna[2]*1000,
                        distancia_mm,
                        T_relativa_mm[0,3], T_relativa_mm[1,3], T_relativa_mm[2,3]
                    ])
                
                # Información para visualización
                info_text = [
                    f"Estado: NAVEGANDO",
                    f"Distancia {ARUCO_ID_COLUMNA}-{ARUCO_ID_LEZNA}: {distancia_mm:.1f} mm",
                    f"Posicion Relativa: X={T_relativa_mm[0,3]:.1f} Y={T_relativa_mm[1,3]:.1f} Z={T_relativa_mm[2,3]:.1f}",
                    f"FPS: {current_fps:.1f}"
                ]
                info_color = (0, 255, 0)  # Verde
                
                # Dibujar ejes (COMO EN TU CÓDIGO)
                cv2.drawFrameAxes(frame_vis, params['mtx_left'], params['dist_left'],
                                 rvec_col_l, tvec_col_l, MARKER_SIZE/2)
                cv2.drawFrameAxes(frame_vis, params['mtx_left'], params['dist_left'],
                                 rvec_lez_l, tvec_lez_l, MARKER_SIZE/2)
        
        # Mostrar estado de detección
        if not columna_detectada or not lezna_detectada:
            info_text = [
                f"Columna (ID {ARUCO_ID_COLUMNA}): {'OK' if columna_detectada else 'NO DETECTADA'}",
                f"Lezna (ID {ARUCO_ID_LEZNA}): {'OK' if lezna_detectada else 'NO DETECTADA'}",
                f"FPS: {current_fps:.1f}"
            ]
            info_color = (0, 165, 255)  # Naranja
        
        # Dibujar información
        y_offset = 30
        for i, line in enumerate(info_text):
            cv2.putText(frame_vis, line, (10, y_offset + i * 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, info_color, 2)
        
        # Mostrar frame
        cv2.imshow('Navegacion Quirurgica', frame_vis)
        
        # Procesar teclas
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n✅ Navegación finalizada")
            break
        
        elif key == ord('r'):
            if filtro is not None:
                filtro.reset()
                print("\n🔄 Filtro reiniciado")
        
        # Calcular FPS
        fps_counter += 1
        if time.time() - fps_start >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_start = time.time()
    
    # Liberar recursos
    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()
    
    if csv_file is not None:
        csv_file.close()
        print(f"✅ Datos guardados en '{CSV_FILE}'")
    
    if igtl_client is not None:
        igtl_client.close()
    
    print("\n✅ Sistema finalizado")


if __name__ == "__main__":
    main()
