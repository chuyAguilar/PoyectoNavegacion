#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Plantilla de Marcadores ArUco para Cubo 50x50 mm
=============================================================

Genera una plantilla A4 con 6 marcadores ArUco (IDs 1-6) optimizados
para un cubo de 50x50 mm, listos para imprimir, recortar y pegar.

Cada marcador tiene:
- Tamaño: 40 mm x 40 mm (marcador ArUco)
- Borde blanco: 5 mm alrededor
- Total: 50 mm x 50 mm (encaja perfecto en cada cara del cubo)

Autor: Sistema de Navegación Quirúrgica
Fecha: 2025-11-25
"""

import cv2
import cv2.aruco as aruco
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Tamaño del cubo
CUBO_LADO = 50  # mm

# Tamaño del marcador ArUco (sin borde)
MARKER_SIZE_MM = 40  # mm

# Borde blanco alrededor del marcador
BORDER_MM = 5  # mm

# Total por marcador (debe ser igual al lado del cubo)
TOTAL_SIZE_MM = MARKER_SIZE_MM + 2 * BORDER_MM  # 50 mm

# IDs de marcadores para el cubo (6 caras)
MARKER_IDS = [1, 2, 3, 4, 5, 6]

# Diccionario ArUco
ARUCO_DICT = aruco.DICT_4X4_50

# DPI para impresión (300 DPI = alta calidad)
DPI = 300

# Directorio de salida
OUTPUT_DIR = "dodecaedro_aruco"

# ============================================================================
# FUNCIONES
# ============================================================================

def mm_to_pixels(mm, dpi=300):
    """Convierte milímetros a píxeles a una resolución dada"""
    inches = mm / 25.4
    return int(inches * dpi)


def generar_plantilla_cubo_50mm():
    """
    Genera una plantilla A4 con 6 marcadores ArUco de 50x50 mm
    listos para recortar y pegar en un cubo
    """
    print("\n📐 Generando plantilla de marcadores para cubo 50x50 mm...")
    
    # Tamaño A4 en píxeles a 300 DPI
    a4_width = mm_to_pixels(210, DPI)   # 210 mm
    a4_height = mm_to_pixels(297, DPI)  # 297 mm
    
    # Crear imagen blanca
    plantilla = Image.new('RGB', (a4_width, a4_height), 'white')
    draw = ImageDraw.Draw(plantilla)
    
    # Tamaños en píxeles
    total_size_px = mm_to_pixels(TOTAL_SIZE_MM, DPI)
    marker_size_px = mm_to_pixels(MARKER_SIZE_MM, DPI)
    border_px = mm_to_pixels(BORDER_MM, DPI)
    
    # Configurar detector ArUco
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    
    # Disposición: 2 columnas x 3 filas
    cols = 2
    rows = 3
    margin = mm_to_pixels(20, DPI)  # 20 mm de margen
    spacing = mm_to_pixels(10, DPI)  # 10 mm entre marcadores
    
    # Fuentes
    try:
        font_title = ImageFont.truetype("arial.ttf", 40)
        font_label = ImageFont.truetype("arial.ttf", 30)
        font_text = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    # Título
    draw.text(
        (a4_width // 2, margin // 2),
        "MARCADORES ARUCO - CUBO 50x50 mm",
        fill='black',
        font=font_title,
        anchor='mm'
    )
    
    # Generar y colocar los 6 marcadores
    marker_idx = 0
    for row in range(rows):
        for col in range(cols):
            if marker_idx >= len(MARKER_IDS):
                break
            
            marker_id = MARKER_IDS[marker_idx]
            
            # Generar marcador ArUco
            marker_img = aruco.generateImageMarker(aruco_dict, marker_id, marker_size_px)
            marker_pil = Image.fromarray(marker_img)
            
            # Calcular posición
            x = margin + col * (total_size_px + spacing)
            y = margin + 100 + row * (total_size_px + spacing)
            
            # Dibujar borde del cuadrado (50x50 mm)
            draw.rectangle(
                [x, y, x + total_size_px, y + total_size_px],
                outline='black',
                width=3
            )
            
            # Dibujar líneas de corte (punteadas)
            # Líneas horizontales
            for i in range(0, total_size_px, 20):
                if i % 40 < 20:
                    draw.line([x + i, y, x + i + 10, y], fill='gray', width=1)
                    draw.line([x + i, y + total_size_px, x + i + 10, y + total_size_px], fill='gray', width=1)
            
            # Líneas verticales
            for i in range(0, total_size_px, 20):
                if i % 40 < 20:
                    draw.line([x, y + i, x, y + i + 10], fill='gray', width=1)
                    draw.line([x + total_size_px, y + i, x + total_size_px, y + i + 10], fill='gray', width=1)
            
            # Pegar marcador ArUco (centrado con borde de 5 mm)
            plantilla.paste(marker_pil, (x + border_px, y + border_px))
            
            # Etiqueta con ID
            draw.text(
                (x + total_size_px // 2, y + total_size_px + 20),
                f"ID {marker_id}",
                fill='red',
                font=font_label,
                anchor='mm'
            )
            
            # Dimensiones
            draw.text(
                (x + total_size_px // 2, y + total_size_px + 50),
                f"50 x 50 mm",
                fill='blue',
                font=font_text,
                anchor='mm'
            )
            
            marker_idx += 1
    
    # Instrucciones
    instrucciones_y = a4_height - mm_to_pixels(40, DPI)
    instrucciones = [
        "INSTRUCCIONES:",
        "1. Imprimir en papel adhesivo mate o papel normal",
        "2. Recortar cada cuadrado por las líneas negras (50x50 mm)",
        "3. Pegar un marcador en cada cara del cubo impreso en 3D",
        "4. Asegurarse de que queden bien planos y sin burbujas",
        "5. El borde blanco de 5 mm ayuda a la detección"
    ]
    
    for i, linea in enumerate(instrucciones):
        draw.text(
            (margin, instrucciones_y + i * 25),
            linea,
            fill='black',
            font=font_text
        )
    
    # Guardar plantilla
    plantilla_path = os.path.join(OUTPUT_DIR, "plantilla_cubo_50mm.png")
    plantilla.save(plantilla_path, dpi=(DPI, DPI))
    print(f"  ✅ Plantilla guardada: {plantilla_path}")
    
    return plantilla_path


def generar_marcadores_individuales_50mm():
    """Genera marcadores individuales de 50x50 mm para referencia"""
    print("\n📐 Generando marcadores individuales 50x50 mm...")
    
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    
    total_size_px = mm_to_pixels(TOTAL_SIZE_MM, DPI)
    marker_size_px = mm_to_pixels(MARKER_SIZE_MM, DPI)
    border_px = mm_to_pixels(BORDER_MM, DPI)
    
    for marker_id in MARKER_IDS:
        # Generar marcador ArUco
        marker_img = aruco.generateImageMarker(aruco_dict, marker_id, marker_size_px)
        
        # Crear imagen con borde blanco
        img_con_borde = Image.new('RGB', (total_size_px, total_size_px), 'white')
        marker_pil = Image.fromarray(marker_img)
        img_con_borde.paste(marker_pil, (border_px, border_px))
        
        # Guardar
        marker_path = os.path.join(OUTPUT_DIR, f"marcador_cubo_50mm_ID{marker_id:02d}.png")
        img_con_borde.save(marker_path, dpi=(DPI, DPI))
        print(f"  ✅ Guardado: marcador_cubo_50mm_ID{marker_id:02d}.png")


def crear_guia_ensamblaje_cubo():
    """Crea guía de ensamblaje para el cubo"""
    guia = """
GUÍA DE ENSAMBLAJE - CUBO ARUCO 50x50 mm
========================================

MATERIALES:
-----------
✅ Cubo impreso en 3D (50x50x50 mm) en PLA blanco mate
✅ Plantilla impresa (plantilla_cubo_50mm.png)
✅ Tijeras o cutter
✅ Pegamento en barra o papel adhesivo
✅ Regla

PASOS:
------

1. IMPRIMIR PLANTILLA
   - Imprimir plantilla_cubo_50mm.png en papel mate
   - Configurar impresora a escala 100% (sin ajustar)
   - Verificar que cada cuadrado mida exactamente 50x50 mm con regla

2. RECORTAR MARCADORES
   - Recortar cada cuadrado por las líneas negras
   - Usar tijeras afiladas o cutter con regla
   - Mantener los bordes rectos y limpios
   - Verificar que cada marcador mida 50x50 mm

3. PREPARAR CUBO
   - Limpiar cada cara del cubo con alcohol
   - Asegurarse de que estén completamente secas
   - Identificar qué cara será cada ID (opcional)

4. PEGAR MARCADORES
   - Aplicar pegamento uniformemente (si no es adhesivo)
   - Centrar el marcador en cada cara del cubo
   - Presionar firmemente desde el centro hacia afuera
   - Eliminar burbujas de aire
   - Dejar secar 10-15 minutos

5. VERIFICACIÓN
   - Verificar que todos los marcadores estén planos
   - No debe haber arrugas ni burbujas
   - Los bordes deben estar bien pegados
   - Probar con: python aruco_test.py

DISTRIBUCIÓN DE IDs EN EL CUBO:
--------------------------------
Sugerencia de distribución:

    [Cara Superior: ID 1]
         |
[ID 2] - [ID 3] - [ID 4]
         |
    [Cara Inferior: ID 5]
    
[Cara Trasera: ID 6]

MONTAJE EN LA LEZNA:
--------------------
1. Limpiar el mango de la lezna
2. Aplicar pegamento fuerte (cianoacrilato o epoxi)
3. Pegar el cubo firmemente
4. Dejar secar 24 horas antes de usar
5. Verificar que no interfiera con el uso del instrumento

CONFIGURACIÓN DEL CUBO EN EL SLICER 3D:
---------------------------------------
Dimensiones: 50 x 50 x 50 mm
Material: PLA blanco mate
Relleno: 20%
Soportes: NO
Tiempo: ~2-3 horas
Filamento: ~25 g

VERIFICACIÓN FINAL:
-------------------
✅ Cada marcador mide 50x50 mm
✅ Marcadores bien pegados y planos
✅ Sin burbujas ni arrugas
✅ Cubo firmemente pegado a la lezna
✅ Todos los IDs (1-6) detectables con aruco_test.py

VENTAJAS DEL CUBO 50x50 mm:
---------------------------
✅ Compacto y manejable
✅ Marcadores de 40 mm (buen tamaño para detección)
✅ No estorba al usar la lezna
✅ Detección confiable a 30-60 cm
✅ Ligero (~25 g con marcadores)
✅ Rápido de imprimir y ensamblar

¡Tu cubo ArUco está listo para navegación quirúrgica!
"""
    
    guia_path = os.path.join(OUTPUT_DIR, "GUIA_ENSAMBLAJE_CUBO_50MM.txt")
    with open(guia_path, 'w', encoding='utf-8') as f:
        f.write(guia)
    
    print(f"\n✅ Guía de ensamblaje creada: {guia_path}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("GENERADOR DE PLANTILLA - CUBO ARUCO 50x50 mm")
    print("=" * 70)
    print(f"Tamaño del cubo: {CUBO_LADO} x {CUBO_LADO} x {CUBO_LADO} mm")
    print(f"Tamaño de marcador: {MARKER_SIZE_MM} x {MARKER_SIZE_MM} mm")
    print(f"Borde blanco: {BORDER_MM} mm")
    print(f"Total por marcador: {TOTAL_SIZE_MM} x {TOTAL_SIZE_MM} mm")
    print(f"IDs: {MARKER_IDS}")
    print("=" * 70)
    
    # Verificar directorio
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✅ Directorio '{OUTPUT_DIR}' creado")
    
    # Generar plantilla principal
    plantilla_path = generar_plantilla_cubo_50mm()
    
    # Generar marcadores individuales
    generar_marcadores_individuales_50mm()
    
    # Crear guía de ensamblaje
    crear_guia_ensamblaje_cubo()
    
    print("\n" + "=" * 70)
    print("✅ GENERACIÓN COMPLETADA")
    print("=" * 70)
    print(f"\nArchivo principal para imprimir:")
    print(f"  📄 {plantilla_path}")
    print(f"\nGuía de ensamblaje:")
    print(f"  📄 {os.path.join(OUTPUT_DIR, 'GUIA_ENSAMBLAJE_CUBO_50MM.txt')}")
    print("\n" + "=" * 70)
    print("PRÓXIMOS PASOS:")
    print("=" * 70)
    print("1. Imprimir plantilla_cubo_50mm.png en papel mate")
    print("2. Imprimir cubo de 50x50x50 mm en 3D (PLA blanco mate)")
    print("3. Recortar los 6 marcadores (50x50 mm cada uno)")
    print("4. Pegar un marcador en cada cara del cubo")
    print("5. Montar el cubo en la lezna")
    print("6. Probar con: python aruco_test.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
