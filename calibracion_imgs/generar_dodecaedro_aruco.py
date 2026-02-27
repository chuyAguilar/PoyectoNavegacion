#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Dodecaedro ArUco para Navegación Quirúrgica
========================================================

Genera:
1. 12 marcadores ArUco individuales (IDs 1-12) para la lezna
2. 1 marcador ArUco grande (ID 0) para la columna
3. Plantilla PDF del dodecaedro lista para imprimir y armar

Optimizado para:
- Tracking de lezna quirúrgica con rotación libre
- Máxima visibilidad desde cualquier ángulo
- Fácil ensamblaje

Autor: Sistema de Navegación Quirúrgica
Fecha: 2025-11-24
"""

import cv2
import cv2.aruco as aruco
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import math

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Diccionario ArUco
ARUCO_DICT = aruco.DICT_4X4_50

# IDs de marcadores
ID_COLUMNA = 0          # Marcador para la columna (referencia fija)
IDS_LEZNA = range(1, 13)  # IDs 1-12 para las 12 caras del dodecaedro

# Tamaños de marcadores (en píxeles)
MARKER_SIZE_DODECAEDRO = 200  # Tamaño de cada marcador del dodecaedro
MARKER_SIZE_COLUMNA = 400     # Marcador grande para la columna

# Directorio de salida
OUTPUT_DIR = "dodecaedro_aruco"

# Tamaño del dodecaedro (en cm)
DODECAEDRO_LADO = 5.0  # 5 cm por lado (ajustar según el tamaño de tu lezna)

# ============================================================================
# FUNCIONES PARA GENERAR MARCADORES
# ============================================================================

def generar_marcador_aruco(marker_id, marker_size, aruco_dict):
    """Genera un marcador ArUco"""
    marker_image = aruco.generateImageMarker(aruco_dict, marker_id, marker_size)
    return marker_image


def crear_directorio():
    """Crea el directorio de salida"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✅ Directorio '{OUTPUT_DIR}' creado")


def generar_marcadores_individuales():
    """Genera todos los marcadores ArUco como imágenes PNG"""
    print("\n📐 Generando marcadores ArUco...")
    
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    
    # Generar marcador de la columna (ID 0)
    print(f"  Generando marcador ID {ID_COLUMNA} (Columna) - {MARKER_SIZE_COLUMNA}x{MARKER_SIZE_COLUMNA} px")
    marker_columna = generar_marcador_aruco(ID_COLUMNA, MARKER_SIZE_COLUMNA, aruco_dict)
    
    # Agregar borde blanco
    border = 20
    marker_columna_bordered = cv2.copyMakeBorder(
        marker_columna, border, border, border, border,
        cv2.BORDER_CONSTANT, value=255
    )
    
    # Guardar
    columna_path = os.path.join(OUTPUT_DIR, f"marcador_columna_ID{ID_COLUMNA}.png")
    cv2.imwrite(columna_path, marker_columna_bordered)
    print(f"    ✅ Guardado: {columna_path}")
    
    # Generar marcadores del dodecaedro (IDs 1-12)
    for marker_id in IDS_LEZNA:
        print(f"  Generando marcador ID {marker_id} (Lezna) - {MARKER_SIZE_DODECAEDRO}x{MARKER_SIZE_DODECAEDRO} px")
        marker = generar_marcador_aruco(marker_id, MARKER_SIZE_DODECAEDRO, aruco_dict)
        
        # Agregar borde blanco
        border = 10
        marker_bordered = cv2.copyMakeBorder(
            marker, border, border, border, border,
            cv2.BORDER_CONSTANT, value=255
        )
        
        # Guardar
        marker_path = os.path.join(OUTPUT_DIR, f"marcador_lezna_ID{marker_id:02d}.png")
        cv2.imwrite(marker_path, marker_bordered)
        print(f"    ✅ Guardado: {marker_path}")
    
    print(f"\n✅ {len(IDS_LEZNA) + 1} marcadores generados")


# ============================================================================
# FUNCIONES PARA GENERAR PLANTILLA DE DODECAEDRO
# ============================================================================

def crear_plantilla_dodecaedro():
    """
    Crea una plantilla desplegada del dodecaedro para imprimir y armar
    """
    print("\n📄 Generando plantilla de dodecaedro...")
    
    # Dimensiones de la plantilla (A4 en píxeles a 300 DPI)
    dpi = 300
    a4_width = int(8.27 * dpi)   # 210 mm
    a4_height = int(11.69 * dpi)  # 297 mm
    
    # Crear imagen blanca
    plantilla = Image.new('RGB', (a4_width, a4_height), 'white')
    draw = ImageDraw.Draw(plantilla)
    
    # Calcular tamaño de cada pentágono en píxeles
    # Dodecaedro desplegado: aproximadamente 4x3 pentágonos
    lado_px = int((DODECAEDRO_LADO / 2.54) * dpi)  # cm a píxeles
    
    # Cargar marcadores ArUco
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    
    # Posiciones aproximadas de los pentágonos en la plantilla desplegada
    # (Simplificado: usaremos una disposición en cuadrícula para facilitar)
    
    print("  Creando disposición de marcadores...")
    
    # Disposición simplificada: 4 columnas x 3 filas
    cols = 4
    rows = 3
    margin = 50
    spacing = 20
    
    marker_size = min(
        (a4_width - 2*margin - (cols-1)*spacing) // cols,
        (a4_height - 2*margin - (rows-1)*spacing) // rows
    )
    
    # Colocar los 12 marcadores
    marker_idx = 0
    for row in range(rows):
        for col in range(cols):
            if marker_idx >= 12:
                break
            
            marker_id = marker_idx + 1  # IDs 1-12
            
            # Generar marcador
            marker = generar_marcador_aruco(marker_id, marker_size - 40, aruco_dict)
            
            # Convertir a PIL Image
            marker_pil = Image.fromarray(marker)
            
            # Calcular posición
            x = margin + col * (marker_size + spacing)
            y = margin + row * (marker_size + spacing)
            
            # Dibujar borde del pentágono (simplificado como cuadrado)
            draw.rectangle(
                [x, y, x + marker_size, y + marker_size],
                outline='black',
                width=2
            )
            
            # Pegar marcador ArUco
            marker_offset = 20
            plantilla.paste(
                marker_pil,
                (x + marker_offset, y + marker_offset)
            )
            
            # Agregar etiqueta con ID
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            draw.text(
                (x + marker_size//2, y + marker_size - 15),
                f"ID {marker_id}",
                fill='red',
                font=font,
                anchor='mm'
            )
            
            # Agregar líneas de corte (punteadas)
            draw.line([x, y, x + marker_size, y], fill='gray', width=1)
            draw.line([x, y, x, y + marker_size], fill='gray', width=1)
            
            marker_idx += 1
    
    # Agregar instrucciones
    try:
        font_title = ImageFont.truetype("arial.ttf", 24)
        font_text = ImageFont.truetype("arial.ttf", 14)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    # Título
    draw.text(
        (a4_width // 2, 20),
        "DODECAEDRO ARUCO - LEZNA QUIRÚRGICA",
        fill='black',
        font=font_title,
        anchor='mm'
    )
    
    # Instrucciones
    instrucciones = [
        "INSTRUCCIONES:",
        "1. Imprimir en papel grueso o cartulina",
        "2. Recortar cada cuadrado por las líneas grises",
        "3. Doblar y pegar formando un dodecaedro",
        f"4. Tamaño objetivo: {DODECAEDRO_LADO} cm por lado",
        "5. Pegar en el mango de la lezna quirúrgica"
    ]
    
    y_instrucciones = a4_height - 150
    for i, linea in enumerate(instrucciones):
        draw.text(
            (margin, y_instrucciones + i * 20),
            linea,
            fill='black',
            font=font_text
        )
    
    # Guardar plantilla
    plantilla_path = os.path.join(OUTPUT_DIR, "plantilla_dodecaedro_lezna.png")
    plantilla.save(plantilla_path, dpi=(dpi, dpi))
    print(f"  ✅ Plantilla guardada: {plantilla_path}")
    
    return plantilla_path


def crear_plantilla_columna():
    """Crea una plantilla simple para el marcador de la columna"""
    print("\n📄 Generando plantilla de marcador de columna...")
    
    dpi = 300
    
    # Tamaño del marcador en cm (10 cm x 10 cm)
    marker_cm = 10
    marker_px = int((marker_cm / 2.54) * dpi)
    
    # Tamaño de la imagen con margen
    margin = int(1 * dpi)  # 1 inch de margen
    img_size = marker_px + 2 * margin
    
    # Crear imagen
    plantilla = Image.new('RGB', (img_size, img_size), 'white')
    draw = ImageDraw.Draw(plantilla)
    
    # Generar marcador ArUco
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    marker = generar_marcador_aruco(ID_COLUMNA, marker_px - 40, aruco_dict)
    marker_pil = Image.fromarray(marker)
    
    # Dibujar borde
    draw.rectangle(
        [margin, margin, margin + marker_px, margin + marker_px],
        outline='black',
        width=3
    )
    
    # Pegar marcador
    plantilla.paste(marker_pil, (margin + 20, margin + 20))
    
    # Agregar etiquetas
    try:
        font_title = ImageFont.truetype("arial.ttf", 30)
        font_text = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    draw.text(
        (img_size // 2, margin // 2),
        "MARCADOR COLUMNA - ID 0",
        fill='black',
        font=font_title,
        anchor='mm'
    )
    
    draw.text(
        (img_size // 2, img_size - margin // 2),
        f"Tamaño: {marker_cm} cm x {marker_cm} cm",
        fill='black',
        font=font_text,
        anchor='mm'
    )
    
    # Guardar
    columna_plantilla_path = os.path.join(OUTPUT_DIR, "plantilla_marcador_columna.png")
    plantilla.save(columna_plantilla_path, dpi=(dpi, dpi))
    print(f"  ✅ Plantilla guardada: {columna_plantilla_path}")
    
    return columna_plantilla_path


def crear_instrucciones_ensamblaje():
    """Crea un archivo de texto con instrucciones de ensamblaje"""
    instrucciones = """
INSTRUCCIONES DE ENSAMBLAJE - DODECAEDRO ARUCO
==============================================

MATERIALES NECESARIOS:
- Plantilla impresa (plantilla_dodecaedro_lezna.png)
- Cartulina o papel grueso (180-250 g/m²)
- Tijeras o cutter
- Pegamento o cinta adhesiva
- Regla

PASOS:

1. IMPRESIÓN
   - Imprimir plantilla_dodecaedro_lezna.png en cartulina
   - Asegurarse de que la escala sea 100% (sin ajustar al tamaño de página)
   - Verificar que los marcadores se vean nítidos

2. RECORTE
   - Recortar cada cuadrado por las líneas grises
   - Usar tijeras afiladas o cutter para bordes limpios
   - Mantener los marcadores ArUco centrados

3. ENSAMBLAJE (VERSIÓN SIMPLIFICADA)
   Opción A - Cubo (más fácil):
   - Usar 6 de los 12 marcadores
   - Formar un cubo pegando las caras
   - IDs recomendados: 1, 2, 3, 4, 5, 6
   
   Opción B - Dodecaedro completo (óptimo):
   - Buscar plantilla de dodecaedro en internet
   - Pegar los 12 marcadores en las 12 caras
   - Requiere más tiempo pero mejor cobertura

4. MONTAJE EN LA LEZNA
   - Pegar el cubo/dodecaedro en el mango de la lezna
   - Asegurarse de que esté firmemente sujeto
   - Verificar que no interfiera con el uso del instrumento

5. MARCADOR DE LA COLUMNA
   - Imprimir plantilla_marcador_columna.png
   - Recortar y pegar en cartón rígido
   - Fijar en la columna vertebral (modelo físico)
   - Orientar hacia las cámaras

VERIFICACIÓN:
- Ejecutar: python aruco_test.py
- Verificar que detecta los IDs correctamente
- Probar diferentes orientaciones

NOTAS:
- Para navegación quirúrgica, usar cartulina mate (sin brillo)
- Evitar arrugas o dobleces en los marcadores
- Mantener los marcadores limpios y sin reflejos

¿PROBLEMAS?
- Si los marcadores no se detectan: verificar iluminación
- Si la detección es inestable: aumentar el tamaño del dodecaedro
- Si hay reflejos: usar papel mate o aplicar spray anti-reflejo
"""
    
    instrucciones_path = os.path.join(OUTPUT_DIR, "INSTRUCCIONES_ENSAMBLAJE.txt")
    with open(instrucciones_path, 'w', encoding='utf-8') as f:
        f.write(instrucciones)
    
    print(f"\n✅ Instrucciones guardadas: {instrucciones_path}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("GENERADOR DE DODECAEDRO ARUCO - NAVEGACIÓN QUIRÚRGICA")
    print("=" * 70)
    print(f"Marcador Columna:  ID {ID_COLUMNA} ({MARKER_SIZE_COLUMNA}x{MARKER_SIZE_COLUMNA} px)")
    print(f"Marcadores Lezna:  IDs {min(IDS_LEZNA)}-{max(IDS_LEZNA)} ({MARKER_SIZE_DODECAEDRO}x{MARKER_SIZE_DODECAEDRO} px)")
    print(f"Tamaño dodecaedro: {DODECAEDRO_LADO} cm por lado")
    print("=" * 70)
    
    # Crear directorio
    crear_directorio()
    
    # Generar marcadores individuales
    generar_marcadores_individuales()
    
    # Generar plantillas
    plantilla_dodecaedro = crear_plantilla_dodecaedro()
    plantilla_columna = crear_plantilla_columna()
    
    # Crear instrucciones
    crear_instrucciones_ensamblaje()
    
    print("\n" + "=" * 70)
    print("✅ GENERACIÓN COMPLETADA")
    print("=" * 70)
    print(f"\nArchivos generados en: {OUTPUT_DIR}/")
    print("\nPara imprimir:")
    print(f"  1. {plantilla_columna}")
    print(f"  2. {plantilla_dodecaedro}")
    print("\nSigue las instrucciones en:")
    print(f"  {os.path.join(OUTPUT_DIR, 'INSTRUCCIONES_ENSAMBLAJE.txt')}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
