#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Navegación Quirúrgica con Detección Dual de ArUcos
==============================================================

Este script implementa navegación relativa usando dos marcadores ArUco:
- ArUco ID 0: Columna vertebral (referencia fija)
- ArUco ID 1: Lezna (instrumento quirúrgico móvil)

La transformación relativa (Lezna respecto a Columna) se envía a 3D Slicer
mediante OpenIGTLink, lo que proporciona estabilidad ante movimientos de cámara.

Características:
- Detección simultánea de dos ArUcos
- Triangulación estéreo para ambos marcadores
- Cálculo de transformación relativa
- Filtro de suavizado exponencial (EMA)
- Comunicación OpenIGTLink con Slicer
- Visualización en tiempo real

Uso:
    python aruco_navegacion_relativa.py
    
    Opciones:
    --test-mode : Modo de prueba sin enviar a Slicer
    --no-filter : Desactivar filtro de suavizado

Autor: Sistema de Navegación Quirúrgica
Fecha: 2025-11-24
"""

import cv2
import numpy as np
import json
import os
import sys
import argparse
from datetime import datetime
import time

# Importar pyigtl para comunicación con Slicer
try:
    import pyigtl
except ImportError:
    print("⚠️  ADVERTENCIA: pyigtl no está instalado.")
    print("   Instalar con: pip install pyigtl")
    print("   El script funcionará en modo de prueba sin enviar datos a Slicer.")
    pyigtl = None

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# IDs de cámaras
CAMERA_LEFT_ID = 0
CAMERA_RIGHT_ID = 1

# Diccionario ArUco
ARUCO_DICT = cv2.aruco.DICT_4X4_50

# IDs de marcadores
ARUCO_ID_COLUMNA = 0  # Marcador fijo en la columna (referencia)
ARUCO_ID_LEZNA = 1    # Marcador móvil en la lezna (instrumento)

# Tamaño de los marcadores ArUco en metros
MARKER_SIZE = 0.05  # 5 cm

# Archivo de configuración de escala
CONFIG_FILE = "config_calibracion.json"

# Archivo de parámetros de calibración estéreo
PARAMS_FILE = "../parametros_calibracion.npz"

# Configuración OpenIGTLink
IGTL_HOST = "127.0.0.1"  # localhost
IGTL_PORT = 18944        # Puerto por defecto de Slicer

# Nombre del nodo de transformación en Slicer
TRANSFORM_NAME = "LeznaToColumna"

# Filtro de suavizado (EMA - Exponential Moving Average)
ALPHA_FILTER = 0.3  # 0 = sin filtro, 1 = sin suavizado

# FPS objetivo
TARGET_FPS = 30

# ============================================================================
# CLASE PARA FILTRO DE SUAVIZADO
# ============================================================================

class ExponentialFilter:
    """Filtro de media móvil exponencial para suavizar transformaciones"""
    
    def __init__(self, alpha=0.3):
        """
        Args:
            alpha: Factor de suavizado (0-1)
                   0 = máximo suavizado (lento)
                   1 = sin suavizado (rápido)
        """
        self.alpha = alpha
        self.prev_transform = None
    
    def filter(self, transform):
        """
        Aplica filtro EMA a una matriz de transformación 4x4
        
        Args:
            transform: Matriz de transformación 4x4
        
        Returns:
            Transformación filtrada
        """
        if self.prev_transform is None:
            self.prev_transform = transform.copy()
            return transform
        
        # Filtrar cada componente
        filtered = self.alpha * transform + (1 - self.alpha) * self.prev_transform
        self.prev_transform = filtered.copy()
        
        return filtered
    
    def reset(self):
        """Reinicia el filtro"""
        self.prev_transform = None


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def cargar_configuracion():
    """Carga la configuración de calibración de escala"""
    if not os.path.exists(CONFIG_FILE):
        print(f"⚠️  ADVERTENCIA: No se encontró {CONFIG_FILE}")
        print("   Usando factor de escala por defecto: 1000.0")
        print("   Ejecuta 'calibracion_escala.py' para calibrar correctamente.")
        return {"factor_escala": 1000.0}
    
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    print(f"✅ Factor de escala cargado: {config['factor_escala']:.2f}")
    return config


def cargar_parametros_calibracion():
    """Carga los parámetros de calibración estéreo"""
    if not os.path.exists(PARAMS_FILE):
        print(f"❌ ERROR: No se encontró {PARAMS_FILE}")
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
    """Detecta marcadores ArUco y estima sus poses"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)
    
    rvecs, tvecs = None, None
    
    if ids is not None and len(ids) > 0:
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, MARKER_SIZE, mtx, dist
        )
    
    return corners, ids, rvecs, tvecs


def calcular_posicion_3d_aruco(rvec_left, tvec_left, rvec_right, tvec_right, params):
    """
    Calcula la posición 3D del marcador mediante triangulación estéreo
    
    Returns:
        posicion_3d: Vector de posición [x, y, z]
    """
    centro_marcador = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    
    # Proyectar en ambas cámaras
    pts_2d_left, _ = cv2.projectPoints(
        centro_marcador, rvec_left, tvec_left,
        params['mtx_left'], params['dist_left']
    )
    
    pts_2d_right, _ = cv2.projectPoints(
        centro_marcador, rvec_right, tvec_right,
        params['mtx_right'], params['dist_right']
    )
    
    # Matrices de proyección
    P_left = params['mtx_left'] @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P_right = params['mtx_right'] @ np.hstack([params['R'], params['T'].reshape(3, 1)])
    
    # Triangular
    pt_left = pts_2d_left[0][0].reshape(2, 1)
    pt_right = pts_2d_right[0][0].reshape(2, 1)
    
    pt_4d = cv2.triangulatePoints(P_left, P_right, pt_left, pt_right)
    pt_3d = pt_4d[:3] / pt_4d[3]
    
    return pt_3d.flatten()


def rvec_to_rotation_matrix(rvec):
    """Convierte un vector de rotación (Rodrigues) a matriz de rotación 3x3"""
    R, _ = cv2.Rodrigues(rvec)
    return R


def crear_matriz_transformacion(rvec, tvec):
    """
    Crea una matriz de transformación homogénea 4x4 a partir de rvec y tvec
    
    Args:
        rvec: Vector de rotación (3x1)
        tvec: Vector de traslación (3x1)
    
    Returns:
        Matriz de transformación 4x4
    """
    R = rvec_to_rotation_matrix(rvec)
    
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = tvec.flatten()
    
    return T


def calcular_transformacion_relativa(T_columna, T_lezna):
    """
    Calcula la transformación de la lezna respecto a la columna
    
    T_relativa = T_columna^-1 × T_lezna
    
    Esto nos da la pose de la lezna en el sistema de coordenadas de la columna.
    
    Args:
        T_columna: Transformación 4x4 de la columna
        T_lezna: Transformación 4x4 de la lezna
    
    Returns:
        T_relativa: Transformación relativa 4x4
    """
    T_columna_inv = np.linalg.inv(T_columna)
    T_relativa = T_columna_inv @ T_lezna
    
    return T_relativa


def aplicar_factor_escala(transform, factor_escala):
    """
    Aplica el factor de escala a la componente de traslación
    
    Args:
        transform: Matriz de transformación 4x4
        factor_escala: Factor de conversión (unidades OpenCV → mm)
    
    Returns:
        Transformación con escala aplicada
    """
    transform_scaled = transform.copy()
    transform_scaled[:3, 3] *= factor_escala
    
    return transform_scaled


def enviar_transformacion_slicer(client, transform, nombre="LeznaToColumna"):
    """
    Envía una transformación a 3D Slicer mediante OpenIGTLink
    
    Args:
        client: Cliente pyigtl
        transform: Matriz de transformación 4x4
        nombre: Nombre del nodo de transformación en Slicer
    """
    if client is None or pyigtl is None:
        return False
    
    try:
        # Crear mensaje de transformación
        # pyigtl espera la matriz en formato row-major (C-style)
        transform_msg = pyigtl.TransformMessage(transform, device_name=nombre)
        
        # Enviar
        client.send_message(transform_msg)
        return True
    
    except Exception as e:
        print(f"❌ Error al enviar transformación: {e}")
        return False


def dibujar_informacion(frame, info_text, color=(0, 255, 0)):
    """Dibuja información de estado en el frame"""
    y_offset = 30
    for i, line in enumerate(info_text):
        cv2.putText(frame, line, (10, y_offset + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    # Parsear argumentos
    parser = argparse.ArgumentParser(description='Navegación quirúrgica con ArUcos')
    parser.add_argument('--test-mode', action='store_true',
                        help='Modo de prueba sin enviar a Slicer')
    parser.add_argument('--no-filter', action='store_true',
                        help='Desactivar filtro de suavizado')
    args = parser.parse_args()
    
    print("=" * 70)
    print("SISTEMA DE NAVEGACIÓN QUIRÚRGICA - NAVEGACIÓN RELATIVA")
    print("=" * 70)
    
    # Cargar configuración
    config = cargar_configuracion()
    factor_escala = config['factor_escala']
    
    params = cargar_parametros_calibracion()
    if params is None:
        return
    
    # Inicializar cámaras
    print("\n📹 Inicializando cámaras...")
    cap_left = cv2.VideoCapture(CAMERA_LEFT_ID)
    cap_right = cv2.VideoCapture(CAMERA_RIGHT_ID)
    
    if not cap_left.isOpened() or not cap_right.isOpened():
        print("❌ ERROR: No se pudieron abrir las cámaras")
        return
    
    cap_left.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap_left.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap_right.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap_right.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("✅ Cámaras inicializadas")
    
    # Configurar detector ArUco
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    aruco_params = cv2.aruco.DetectorParameters()
    
    # Inicializar filtro de suavizado
    filtro = None if args.no_filter else ExponentialFilter(alpha=ALPHA_FILTER)
    
    # Conectar con Slicer (si no está en modo de prueba)
    igtl_client = None
    if not args.test_mode and pyigtl is not None:
        print(f"\n🔌 Conectando con 3D Slicer ({IGTL_HOST}:{IGTL_PORT})...")
        try:
            igtl_client = pyigtl.OpenIGTLinkClient(host=IGTL_HOST, port=IGTL_PORT)
            print("✅ Conectado con 3D Slicer")
        except Exception as e:
            print(f"⚠️  No se pudo conectar con Slicer: {e}")
            print("   Continuando en modo de prueba...")
    
    if args.test_mode:
        print("\n🧪 Modo de prueba activado (sin enviar a Slicer)")
    
    print("\n" + "=" * 70)
    print("INSTRUCCIONES:")
    print("=" * 70)
    print(f"- ArUco ID {ARUCO_ID_COLUMNA}: Columna (referencia fija)")
    print(f"- ArUco ID {ARUCO_ID_LEZNA}: Lezna (instrumento móvil)")
    print("- Ambos marcadores deben ser visibles simultáneamente")
    print("- Presiona 'q' para salir")
    print("- Presiona 'r' para reiniciar el filtro")
    print("=" * 70)
    
    # Variables de estadísticas
    fps_counter = 0
    fps_start_time = time.time()
    current_fps = 0
    
    while True:
        loop_start = time.time()
        
        # Capturar frames
        ret_left, frame_left = cap_left.read()
        ret_right, frame_right = cap_right.read()
        
        if not ret_left or not ret_right:
            print("❌ ERROR: No se pudo capturar frame")
            break
        
        # Detectar ArUcos en ambas cámaras
        corners_left, ids_left, rvecs_left, tvecs_left = detectar_aruco(
            frame_left, aruco_dict, aruco_params,
            params['mtx_left'], params['dist_left']
        )
        
        corners_right, ids_right, rvecs_right, tvecs_right = detectar_aruco(
            frame_right, aruco_dict, aruco_params,
            params['mtx_right'], params['dist_right']
        )
        
        # Visualizar detección
        frame_vis = frame_left.copy()
        
        if ids_left is not None:
            cv2.aruco.drawDetectedMarkers(frame_vis, corners_left, ids_left)
        
        # Buscar ambos marcadores
        columna_detectada = False
        lezna_detectada = False
        
        info_lines = []
        info_color = (0, 165, 255)  # Naranja por defecto
        
        if ids_left is not None and ids_right is not None:
            # Buscar marcador de columna
            idx_columna_left = np.where(ids_left == ARUCO_ID_COLUMNA)[0]
            idx_columna_right = np.where(ids_right == ARUCO_ID_COLUMNA)[0]
            
            # Buscar marcador de lezna
            idx_lezna_left = np.where(ids_left == ARUCO_ID_LEZNA)[0]
            idx_lezna_right = np.where(ids_right == ARUCO_ID_LEZNA)[0]
            
            columna_detectada = len(idx_columna_left) > 0 and len(idx_columna_right) > 0
            lezna_detectada = len(idx_lezna_left) > 0 and len(idx_lezna_right) > 0
            
            if columna_detectada and lezna_detectada:
                # Calcular poses 3D de ambos marcadores
                rvec_col_l = rvecs_left[idx_columna_left[0]]
                tvec_col_l = tvecs_left[idx_columna_left[0]]
                rvec_col_r = rvecs_right[idx_columna_right[0]]
                tvec_col_r = tvecs_right[idx_columna_right[0]]
                
                rvec_lez_l = rvecs_left[idx_lezna_left[0]]
                tvec_lez_l = tvecs_left[idx_lezna_left[0]]
                rvec_lez_r = rvecs_right[idx_lezna_right[0]]
                tvec_lez_r = tvecs_right[idx_lezna_right[0]]
                
                # Calcular posiciones 3D
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
                
                # Aplicar filtro de suavizado
                if filtro is not None:
                    T_relativa = filtro.filter(T_relativa)
                
                # Aplicar factor de escala
                T_relativa_scaled = aplicar_factor_escala(T_relativa, factor_escala)
                
                # Enviar a Slicer
                if igtl_client is not None:
                    enviar_transformacion_slicer(igtl_client, T_relativa_scaled, TRANSFORM_NAME)
                
                # Información para visualización
                distancia = np.linalg.norm(T_relativa_scaled[:3, 3])
                
                info_lines = [
                    f"Estado: NAVEGANDO",
                    f"Distancia: {distancia:.1f} mm",
                    f"Posicion: X={T_relativa_scaled[0,3]:.1f} Y={T_relativa_scaled[1,3]:.1f} Z={T_relativa_scaled[2,3]:.1f}",
                    f"FPS: {current_fps:.1f}"
                ]
                info_color = (0, 255, 0)  # Verde
        
        # Mostrar estado de detección
        if not columna_detectada or not lezna_detectada:
            info_lines = [
                f"Columna (ID {ARUCO_ID_COLUMNA}): {'OK' if columna_detectada else 'NO DETECTADA'}",
                f"Lezna (ID {ARUCO_ID_LEZNA}): {'OK' if lezna_detectada else 'NO DETECTADA'}",
                f"FPS: {current_fps:.1f}"
            ]
            info_color = (0, 165, 255)  # Naranja
        
        dibujar_informacion(frame_vis, info_lines, info_color)
        
        # Mostrar frame
        cv2.imshow('Navegacion Quirurgica - Camara Izquierda', frame_vis)
        
        # Procesar teclas
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n✅ Navegación finalizada por el usuario")
            break
        
        elif key == ord('r'):
            if filtro is not None:
                filtro.reset()
                print("\n🔄 Filtro reiniciado")
        
        # Calcular FPS
        fps_counter += 1
        if time.time() - fps_start_time >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_start_time = time.time()
        
        # Control de FPS
        elapsed = time.time() - loop_start
        sleep_time = (1.0 / TARGET_FPS) - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    # Liberar recursos
    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()
    
    if igtl_client is not None:
        igtl_client.close()
    
    print("\n✅ Sistema finalizado")


if __name__ == "__main__":
    main()
