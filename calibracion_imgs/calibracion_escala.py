#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Calibración de Escala para Navegación Quirúrgica
===========================================================

Este script determina el factor de conversión correcto entre las unidades
de OpenCV (resultado de triangulación) y milímetros de 3D Slicer.

Uso:
    1. Ejecutar el script
    2. Colocar el marcador ArUco en posición inicial
    3. Presionar ESPACIO para capturar posición inicial
    4. Mover el marcador exactamente 100mm (usar regla/calibrador)
    5. Presionar ESPACIO para capturar posición final
    6. El script calculará y guardará el factor de escala

Autor: Sistema de Navegación Quirúrgica
Fecha: 2025-11-24
"""

import cv2
import numpy as np
import json
from datetime import datetime
import os

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# IDs de cámaras (ajustar según tu sistema)
CAMERA_LEFT_ID = 1
CAMERA_RIGHT_ID = 2

# Diccionario ArUco
ARUCO_DICT = cv2.aruco.DICT_4X4_50
ARUCO_ID_CALIBRACION = 0  # ID del marcador para calibración

# Tamaño del marcador ArUco en metros (ajustar al tamaño real de tu marcador)
MARKER_SIZE = 0.05  # 5 cm = 0.05 m

# Distancia de prueba en milímetros
DISTANCIA_PRUEBA_MM = 100.0

# Archivo de salida
CONFIG_FILE = "config_calibracion.json"

# Archivo de parámetros de calibración estéreo
PARAMS_FILE = "parametros_calibracion_stereo.npz"

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def cargar_parametros_calibracion():
    """Carga los parámetros de calibración estéreo desde archivo .npz"""
    if not os.path.exists(PARAMS_FILE):
        print(f"❌ ERROR: No se encontró el archivo {PARAMS_FILE}")
        print("   Ejecuta primero el script de calibración estéreo.")
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
    
    print("✅ Parámetros de calibración cargados correctamente")
    return params


def detectar_aruco(frame, aruco_detector, mtx, dist):
    """
    Detecta marcadores ArUco en un frame
    
    Returns:
        corners: Esquinas detectadas
        ids: IDs de los marcadores
        rvecs: Vectores de rotación
        tvecs: Vectores de traslación
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = aruco_detector.detectMarkers(gray)
    
    rvecs, tvecs = None, None
    
    if ids is not None and len(ids) > 0:
        # Estimar pose de los marcadores
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
    
    return corners, ids, rvecs, tvecs


def triangular_punto(pt_left, pt_right, params):
    """
    Triangula un punto 3D a partir de sus proyecciones en ambas cámaras
    
    Args:
        pt_left: Punto 2D en cámara izquierda [x, y]
        pt_right: Punto 2D en cámara derecha [x, y]
        params: Parámetros de calibración estéreo
    
    Returns:
        punto_3d: Coordenadas 3D [x, y, z]
    """
    # Crear matrices de proyección
    P_left = params['mtx_left'] @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P_right = params['mtx_right'] @ np.hstack([params['R'], params['T'].reshape(3, 1)])
    
    # Triangular
    pt_4d = cv2.triangulatePoints(P_left, P_right, pt_left, pt_right)
    pt_3d = pt_4d[:3] / pt_4d[3]
    
    return pt_3d.flatten()


def calcular_posicion_3d_aruco(rvec_left, tvec_left, rvec_right, tvec_right, params):
    """
    Calcula la posición 3D del marcador ArUco mediante triangulación
    
    Args:
        rvec_left, tvec_left: Pose del marcador en cámara izquierda
        rvec_right, tvec_right: Pose del marcador en cámara derecha
        params: Parámetros de calibración estéreo
    
    Returns:
        posicion_3d: Coordenadas 3D del centro del marcador
    """
    # Proyectar el centro del marcador (0,0,0 en coordenadas del marcador) a 2D
    centro_marcador = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    
    # Proyectar en cámara izquierda
    pts_2d_left, _ = cv2.projectPoints(
        centro_marcador, rvec_left, tvec_left,
        params['mtx_left'], params['dist_left']
    )
    
    # Proyectar en cámara derecha
    pts_2d_right, _ = cv2.projectPoints(
        centro_marcador, rvec_right, tvec_right,
        params['mtx_right'], params['dist_right']
    )
    
    # Triangular
    pt_left = pts_2d_left[0][0].reshape(2, 1)
    pt_right = pts_2d_right[0][0].reshape(2, 1)
    
    posicion_3d = triangular_punto(pt_left, pt_right, params)
    
    return posicion_3d


def guardar_configuracion(factor_escala, distancia_medida, distancia_calculada):
    """Guarda el factor de escala en archivo JSON"""
    config = {
        "factor_escala": float(factor_escala),
        "fecha_calibracion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "distancia_prueba_mm": float(DISTANCIA_PRUEBA_MM),
        "distancia_medida_unidades": float(distancia_medida),
        "distancia_calculada_mm": float(distancia_calculada),
        "aruco_id_usado": int(ARUCO_ID_CALIBRACION),
        "notas": "Calibración de escala para navegación quirúrgica"
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    
    print(f"\n✅ Configuración guardada en: {CONFIG_FILE}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("CALIBRACIÓN DE ESCALA - NAVEGACIÓN QUIRÚRGICA")
    print("=" * 70)
    
    # Cargar parámetros de calibración
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
    
    # Configurar resolución (ajustar según tus cámaras)
    cap_left.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap_left.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap_right.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap_right.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("✅ Cámaras inicializadas")
    
    # Configurar detector ArUco (nueva API OpenCV 4.7+)
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    aruco_params = cv2.aruco.DetectorParameters()
    aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
    
    # Variables de estado
    posicion_inicial = None
    posicion_final = None
    estado = "ESPERANDO_INICIAL"  # Estados: ESPERANDO_INICIAL, ESPERANDO_FINAL, COMPLETADO
    
    print("\n" + "=" * 70)
    print("INSTRUCCIONES:")
    print("=" * 70)
    print(f"1. Coloca el marcador ArUco ID {ARUCO_ID_CALIBRACION} en una posición inicial")
    print("2. Presiona ESPACIO para capturar la posición inicial")
    print(f"3. Mueve el marcador EXACTAMENTE {DISTANCIA_PRUEBA_MM} mm (usa regla/calibrador)")
    print("4. Presiona ESPACIO para capturar la posición final")
    print("5. El script calculará automáticamente el factor de escala")
    print("\nPresiona 'q' para salir")
    print("=" * 70)
    
    while True:
        # Capturar frames
        ret_left, frame_left = cap_left.read()
        ret_right, frame_right = cap_right.read()
        
        if not ret_left or not ret_right:
            print("❌ ERROR: No se pudo capturar frame")
            break
        
        # Detectar ArUcos en ambas cámaras
        corners_left, ids_left, rvecs_left, tvecs_left = detectar_aruco(
            frame_left, aruco_detector,
            params['mtx_left'], params['dist_left']
        )
        
        corners_right, ids_right, rvecs_right, tvecs_right = detectar_aruco(
            frame_right, aruco_detector,
            params['mtx_right'], params['dist_right']
        )
        
        # Visualizar detección
        frame_left_vis = frame_left.copy()
        frame_right_vis = frame_right.copy()
        
        if ids_left is not None:
            cv2.aruco.drawDetectedMarkers(frame_left_vis, corners_left, ids_left)
        if ids_right is not None:
            cv2.aruco.drawDetectedMarkers(frame_right_vis, corners_right, ids_right)
        
        # Verificar si se detectó el marcador de calibración en ambas cámaras
        marcador_detectado = False
        posicion_actual = None
        
        if ids_left is not None and ids_right is not None:
            # Buscar el marcador de calibración
            idx_left = np.where(ids_left == ARUCO_ID_CALIBRACION)[0]
            idx_right = np.where(ids_right == ARUCO_ID_CALIBRACION)[0]
            
            if len(idx_left) > 0 and len(idx_right) > 0:
                marcador_detectado = True
                
                # Calcular posición 3D
                rvec_l = rvecs_left[idx_left[0]]
                tvec_l = tvecs_left[idx_left[0]]
                rvec_r = rvecs_right[idx_right[0]]
                tvec_r = tvecs_right[idx_right[0]]
                
                posicion_actual = calcular_posicion_3d_aruco(
                    rvec_l, tvec_l, rvec_r, tvec_r, params
                )
        
        # Mostrar estado
        if estado == "ESPERANDO_INICIAL":
            texto = f"Estado: Esperando posicion inicial | ArUco ID {ARUCO_ID_CALIBRACION}"
            color = (0, 165, 255)  # Naranja
        elif estado == "ESPERANDO_FINAL":
            texto = f"Estado: Mueve {DISTANCIA_PRUEBA_MM}mm y presiona ESPACIO"
            color = (0, 255, 255)  # Amarillo
        else:
            texto = "Estado: COMPLETADO"
            color = (0, 255, 0)  # Verde
        
        cv2.putText(frame_left_vis, texto, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        if marcador_detectado:
            cv2.putText(frame_left_vis, "ArUco DETECTADO", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(frame_left_vis, "ArUco NO detectado", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Mostrar frames
        cv2.imshow('Camara Izquierda - Calibracion', frame_left_vis)
        cv2.imshow('Camara Derecha - Calibracion', frame_right_vis)
        
        # Procesar teclas
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n❌ Calibración cancelada por el usuario")
            break
        
        elif key == ord(' '):  # ESPACIO
            if not marcador_detectado:
                print("\n⚠️  No se detectó el marcador ArUco. Intenta de nuevo.")
                continue
            
            if estado == "ESPERANDO_INICIAL":
                posicion_inicial = posicion_actual.copy()
                estado = "ESPERANDO_FINAL"
                print(f"\n✅ Posición inicial capturada: {posicion_inicial}")
                print(f"   Ahora mueve el marcador EXACTAMENTE {DISTANCIA_PRUEBA_MM} mm")
            
            elif estado == "ESPERANDO_FINAL":
                posicion_final = posicion_actual.copy()
                estado = "COMPLETADO"
                
                # Calcular distancia
                distancia_medida = np.linalg.norm(posicion_final - posicion_inicial)
                
                # Calcular factor de escala
                # distancia_medida (unidades OpenCV) -> DISTANCIA_PRUEBA_MM (mm)
                factor_escala = DISTANCIA_PRUEBA_MM / distancia_medida
                
                print(f"\n✅ Posición final capturada: {posicion_final}")
                print("\n" + "=" * 70)
                print("RESULTADOS DE CALIBRACIÓN")
                print("=" * 70)
                print(f"Distancia medida (unidades OpenCV): {distancia_medida:.6f}")
                print(f"Distancia real (mm):                 {DISTANCIA_PRUEBA_MM:.2f}")
                print(f"Factor de escala calculado:          {factor_escala:.2f}")
                print("=" * 70)
                
                # Verificación
                distancia_calculada = distancia_medida * factor_escala
                error = abs(distancia_calculada - DISTANCIA_PRUEBA_MM)
                error_porcentaje = (error / DISTANCIA_PRUEBA_MM) * 100
                
                print(f"\nVerificación:")
                print(f"  Distancia calculada: {distancia_calculada:.2f} mm")
                print(f"  Error: {error:.2f} mm ({error_porcentaje:.2f}%)")
                
                if error_porcentaje < 5:
                    print("  ✅ Calibración EXITOSA (error < 5%)")
                    guardar_configuracion(factor_escala, distancia_medida, distancia_calculada)
                else:
                    print("  ⚠️  ADVERTENCIA: Error alto (>5%). Considera repetir la calibración.")
                    respuesta = input("\n¿Guardar de todas formas? (s/n): ")
                    if respuesta.lower() == 's':
                        guardar_configuracion(factor_escala, distancia_medida, distancia_calculada)
                
                print("\nPresiona 'q' para salir o ESPACIO para recalibrar")
        
        # Si está completado, permitir recalibrar
        if estado == "COMPLETADO" and key == ord(' '):
            estado = "ESPERANDO_INICIAL"
            posicion_inicial = None
            posicion_final = None
            print("\n🔄 Reiniciando calibración...")
    
    # Liberar recursos
    cap_left.release()
    cap_right.release()
    cv2.destroyAllWindows()
    
    print("\n✅ Calibración finalizada")


if __name__ == "__main__":
    main()
