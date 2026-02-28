#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calibración Estéreo para Navegación Quirúrgica
==============================================

Script adaptado al proyecto existente para calibrar dos cámaras en configuración estéreo.

Configuración:
- Cámara Izquierda: Índice 1
- Cámara Derecha: Índice 3
- Tablero de ajedrez: 9x6 esquinas internas
- Tamaño de cuadro: 25 mm (ajustar según tu tablero)

Genera: parametros_calibracion_stereo.npz

Autor: Adaptado al proyecto de navegación quirúrgica
Fecha: 2025-11-24
"""

import cv2
import numpy as np
import os
import glob

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Índices de las cámaras (ADAPTADO A TU PROYECTO)
CAMERA_LEFT_ID = 1   # Tu cámara izquierda
CAMERA_RIGHT_ID = 2  # Tu cámara derecha

# Parámetros del tablero de ajedrez
CHESSBOARD_SIZE = (9, 6)  # Esquinas internas (ancho x alto)
SQUARE_SIZE = 25.0        # Tamaño del cuadro en mm

# Directorio para guardar imágenes de calibración
CAPTURE_DIR = "calibracion_stereo_imgs"

# Archivo de salida
OUTPUT_FILE = "parametros_calibracion_stereo.npz"

# Resolución de las cámaras
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Número mínimo de imágenes para calibración
MIN_IMAGES = 15

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def crear_directorio():
    """Crea el directorio para guardar imágenes si no existe"""
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    print(f"✅ Directorio '{CAPTURE_DIR}' listo")


def inicializar_camaras():
    """Inicializa ambas cámaras"""
    print("\n📹 Inicializando cámaras...")
    
    cap_left = cv2.VideoCapture(CAMERA_LEFT_ID)
    cap_right = cv2.VideoCapture(CAMERA_RIGHT_ID)
    
    if not cap_left.isOpened() or not cap_right.isOpened():
        print("❌ ERROR: No se pudieron abrir las cámaras")
        print(f"   Verifica que las cámaras {CAMERA_LEFT_ID} y {CAMERA_RIGHT_ID} estén conectadas")
        return None, None
    
    # Configurar resolución
    cap_left.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap_left.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap_right.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap_right.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    print(f"✅ Cámara izquierda (índice {CAMERA_LEFT_ID}): OK")
    print(f"✅ Cámara derecha (índice {CAMERA_RIGHT_ID}): OK")
    
    return cap_left, cap_right


def capturar_imagenes_calibracion(cap_left, cap_right):
    """
    Captura pares de imágenes del tablero de ajedrez desde ambas cámaras
    """
    print("\n" + "=" * 70)
    print("CAPTURA DE IMÁGENES PARA CALIBRACIÓN ESTÉREO")
    print("=" * 70)
    print(f"Objetivo: Capturar al menos {MIN_IMAGES} pares de imágenes")
    print("\nInstrucciones:")
    print("1. Coloca el tablero de ajedrez frente a AMBAS cámaras")
    print("2. Mueve el tablero a diferentes posiciones y ángulos")
    print("3. Presiona 'c' para capturar cuando ambas cámaras detecten el tablero")
    print("4. Presiona 'q' cuando tengas suficientes imágenes")
    print("=" * 70)
    
    img_count = 0
    
    # Crear ventanas
    cv2.namedWindow('Camara Izquierda (1)', cv2.WINDOW_NORMAL)
    cv2.namedWindow('Camara Derecha (3)', cv2.WINDOW_NORMAL)
    
    while True:
        ret_left, frame_left = cap_left.read()
        ret_right, frame_right = cap_right.read()
        
        if not ret_left or not ret_right:
            print("❌ ERROR: No se pudo capturar frame")
            break
        
        # Convertir a escala de grises
        gray_left = cv2.cvtColor(frame_left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(frame_right, cv2.COLOR_BGR2GRAY)
        
        # Buscar esquinas del tablero
        ret_left_chess, corners_left = cv2.findChessboardCorners(
            gray_left, CHESSBOARD_SIZE, None
        )
        ret_right_chess, corners_right = cv2.findChessboardCorners(
            gray_right, CHESSBOARD_SIZE, None
        )
        
        # Copias para visualización
        display_left = frame_left.copy()
        display_right = frame_right.copy()
        
        # Dibujar esquinas si se detectan
        if ret_left_chess:
            cv2.drawChessboardCorners(display_left, CHESSBOARD_SIZE, corners_left, ret_left_chess)
            cv2.putText(display_left, "TABLERO DETECTADO", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_left, "Buscando tablero...", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        if ret_right_chess:
            cv2.drawChessboardCorners(display_right, CHESSBOARD_SIZE, corners_right, ret_right_chess)
            cv2.putText(display_right, "TABLERO DETECTADO", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_right, "Buscando tablero...", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Mostrar contador de imágenes
        cv2.putText(display_left, f"Imagenes: {img_count}/{MIN_IMAGES}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(display_right, f"Imagenes: {img_count}/{MIN_IMAGES}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # Mostrar frames
        cv2.imshow('Camara Izquierda (1)', display_left)
        cv2.imshow('Camara Derecha (3)', display_right)
        
        # Procesar teclas
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('c'):
            if ret_left_chess and ret_right_chess:
                # Guardar ambas imágenes
                left_path = os.path.join(CAPTURE_DIR, f"left_{img_count:02d}.jpg")
                right_path = os.path.join(CAPTURE_DIR, f"right_{img_count:02d}.jpg")
                
                cv2.imwrite(left_path, frame_left)
                cv2.imwrite(right_path, frame_right)
                
                print(f"✅ Par {img_count} capturado: {left_path}, {right_path}")
                img_count += 1
            else:
                print("⚠️  El tablero debe ser visible en AMBAS cámaras")
        
        elif key == ord('q'):
            if img_count >= MIN_IMAGES:
                print(f"\n✅ Captura completada: {img_count} pares de imágenes")
                break
            else:
                print(f"\n⚠️  Necesitas al menos {MIN_IMAGES} imágenes (tienes {img_count})")
                respuesta = input("¿Salir de todas formas? (s/n): ")
                if respuesta.lower() == 's':
                    break
    
    cv2.destroyAllWindows()
    return img_count


def calibrar_camaras_stereo():
    """
    Realiza la calibración estéreo usando las imágenes capturadas
    """
    print("\n" + "=" * 70)
    print("CALIBRACIÓN ESTÉREO")
    print("=" * 70)
    
    # Preparar puntos 3D del tablero
    objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
    objp *= SQUARE_SIZE
    
    # Listas para almacenar puntos
    objpoints = []  # Puntos 3D en el mundo real
    imgpoints_left = []  # Puntos 2D en imagen izquierda
    imgpoints_right = []  # Puntos 2D en imagen derecha
    
    # Cargar imágenes
    left_images = sorted(glob.glob(os.path.join(CAPTURE_DIR, 'left_*.jpg')))
    right_images = sorted(glob.glob(os.path.join(CAPTURE_DIR, 'right_*.jpg')))
    
    if len(left_images) == 0 or len(right_images) == 0:
        print("❌ ERROR: No se encontraron imágenes de calibración")
        return False
    
    print(f"\n📁 Procesando {len(left_images)} pares de imágenes...")
    
    img_shape = None
    valid_pairs = 0
    
    for left_path, right_path in zip(left_images, right_images):
        img_left = cv2.imread(left_path)
        img_right = cv2.imread(right_path)
        
        gray_left = cv2.cvtColor(img_left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(img_right, cv2.COLOR_BGR2GRAY)
        
        if img_shape is None:
            img_shape = gray_left.shape[::-1]
        
        # Buscar esquinas
        ret_left, corners_left = cv2.findChessboardCorners(gray_left, CHESSBOARD_SIZE, None)
        ret_right, corners_right = cv2.findChessboardCorners(gray_right, CHESSBOARD_SIZE, None)
        
        if ret_left and ret_right:
            objpoints.append(objp)
            
            # Refinar esquinas
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_left = cv2.cornerSubPix(gray_left, corners_left, (11, 11), (-1, -1), criteria)
            corners_right = cv2.cornerSubPix(gray_right, corners_right, (11, 11), (-1, -1), criteria)
            
            imgpoints_left.append(corners_left)
            imgpoints_right.append(corners_right)
            
            valid_pairs += 1
            print(f"  ✅ Par {valid_pairs}: {os.path.basename(left_path)}")
        else:
            print(f"  ⚠️  Esquinas no detectadas en: {os.path.basename(left_path)}")
    
    if valid_pairs < 10:
        print(f"\n❌ ERROR: Solo {valid_pairs} pares válidos (mínimo 10)")
        return False
    
    print(f"\n✅ {valid_pairs} pares válidos para calibración")
    
    # Calibrar cámara izquierda
    print("\n🔧 Calibrando cámara izquierda...")
    ret_left, mtx_left, dist_left, rvecs_left, tvecs_left = cv2.calibrateCamera(
        objpoints, imgpoints_left, img_shape, None, None
    )
    print(f"   Error de reproyección: {ret_left:.4f}")
    
    # Calibrar cámara derecha
    print("🔧 Calibrando cámara derecha...")
    ret_right, mtx_right, dist_right, rvecs_right, tvecs_right = cv2.calibrateCamera(
        objpoints, imgpoints_right, img_shape, None, None
    )
    print(f"   Error de reproyección: {ret_right:.4f}")
    
    # Calibración estéreo
    print("🔧 Calibrando sistema estéreo...")
    criteria_stereo = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)
    
    ret_stereo, mtx_left, dist_left, mtx_right, dist_right, R, T, E, F = cv2.stereoCalibrate(
        objpoints, imgpoints_left, imgpoints_right,
        mtx_left, dist_left,
        mtx_right, dist_right,
        img_shape,
        criteria=criteria_stereo,
        flags=cv2.CALIB_FIX_INTRINSIC
    )
    
    print(f"   Error de reproyección estéreo: {ret_stereo:.4f}")
    
    # Guardar parámetros
    print(f"\n💾 Guardando parámetros en '{OUTPUT_FILE}'...")
    np.savez(
        OUTPUT_FILE,
        mtx_left=mtx_left,
        dist_left=dist_left,
        mtx_right=mtx_right,
        dist_right=dist_right,
        R=R,
        T=T,
        E=E,
        F=F
    )
    
    print("\n" + "=" * 70)
    print("RESULTADOS DE CALIBRACIÓN")
    print("=" * 70)
    print(f"Error cámara izquierda:  {ret_left:.4f}")
    print(f"Error cámara derecha:    {ret_right:.4f}")
    print(f"Error estéreo:           {ret_stereo:.4f}")
    print(f"\nDistancia entre cámaras: {np.linalg.norm(T):.2f} mm")
    print(f"Archivo generado:        {OUTPUT_FILE}")
    print("=" * 70)
    
    return True


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("CALIBRACIÓN ESTÉREO - NAVEGACIÓN QUIRÚRGICA")
    print("=" * 70)
    print(f"Cámara izquierda: Índice {CAMERA_LEFT_ID}")
    print(f"Cámara derecha:   Índice {CAMERA_RIGHT_ID}")
    print(f"Tablero:          {CHESSBOARD_SIZE[0]}x{CHESSBOARD_SIZE[1]} esquinas")
    print(f"Tamaño cuadro:    {SQUARE_SIZE} mm")
    print("=" * 70)
    
    # Crear directorio
    crear_directorio()
    
    # Preguntar si usar imágenes existentes
    if os.path.exists(CAPTURE_DIR) and len(glob.glob(os.path.join(CAPTURE_DIR, 'left_*.jpg'))) > 0:
        print(f"\n⚠️  Se encontraron imágenes existentes en '{CAPTURE_DIR}'")
        respuesta = input("¿Usar imágenes existentes? (s/n): ")
        if respuesta.lower() == 's':
            print("✅ Usando imágenes existentes")
            if calibrar_camaras_stereo():
                print("\n✅ Calibración completada exitosamente")
            return
    
    # Inicializar cámaras
    cap_left, cap_right = inicializar_camaras()
    if cap_left is None or cap_right is None:
        return
    
    # Capturar imágenes
    img_count = capturar_imagenes_calibracion(cap_left, cap_right)
    
    # Liberar cámaras
    cap_left.release()
    cap_right.release()
    
    if img_count < MIN_IMAGES:
        print(f"\n❌ Calibración cancelada: Solo se capturaron {img_count} imágenes")
        return
    
    # Calibrar
    if calibrar_camaras_stereo():
        print("\n✅ Calibración completada exitosamente")
        print(f"\n📝 Próximo paso: Ejecuta 'navegacion_quirurgica_final.py'")
    else:
        print("\n❌ La calibración falló")


if __name__ == "__main__":
    main()
