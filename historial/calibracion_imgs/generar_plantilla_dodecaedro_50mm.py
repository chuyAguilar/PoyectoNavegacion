#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Plantilla de Marcadores ArUco para Dodecaedro 50mm
===============================================================

Genera una plantilla con 12 marcadores ArUco pentagonales optimizados
para un dodecaedro de 50 mm de lado, listos para imprimir, recortar y pegar.

Especificaciones:
- Dodecaedro: 50 mm de lado por arista
- Cada cara: Pentágono regular
- Marcador ArUco: Inscrito en círculo de ~35 mm de diámetro
- 12 caras = IDs 1-12

Autor: Sistema de Navegación Quirúrgica
Fecha: 2025-11-25
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

# Lado del dodecaedro
DODECAEDRO_LADO = 50  # mm

# Para un dodecaedro regular, el radio del círculo inscrito en cada pentágono es:
# r = lado / (2 * tan(36°))
ANGULO_PENTAGONO = 36  # grados
RADIO_INSCRITO = DODECAEDRO_LADO / (2 * math.tan(math.radians(ANGULO_PENTAGONO)))

# Tamaño del marcador ArUco (debe caber en el pentágono)
# Usamos ~70% del radio inscrito para dejar margen
MARKER_SIZE_MM = int(RADIO_INSCRITO * 1.4)  # ~35 mm

# Tamaño total del pentágono (circunferencia circunscrita)
PENTAGONO_RADIO = DODECAEDRO_LADO / (2 * math.sin(math.radians(36)))  # ~29 mm

# IDs de marcadores para el dodecaedro (12 caras)
MARKER_IDS = list(range(1, 13))

# Diccionario ArUco
ARUCO_DICT = aruco.DICT_4X4_50

# DPI para impresión
DPI = 300

# Directorio de salida
OUTPUT_DIR = "dodecaedro_aruco"

# ============================================================================
# FUNCIONES
# ============================================================================

def mm_to_pixels(mm, dpi=300):
    """Convierte milímetros a píxeles"""
    inches = mm / 25.4
    return int(inches * dpi)


def generar_pentagono_vertices(center_x, center_y, radius):
    """Genera los vértices de un pentágono regular"""
    vertices = []
    for i in range(5):
        angle = (i * 72 - 90) * math.pi / 180  # -90 para que apunte arriba
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        vertices.append((x, y))
    return vertices


def generar_plantilla_dodecaedro_50mm():
    """
    Genera una plantilla A4 con 12 marcadores ArUco pentagonales
    para dodecaedro de 50 mm
    """
    print("\n📐 Generando plantilla de marcadores para dodecaedro 50mm...")
    print(f"   Lado del dodecaedro: {DODECAEDRO_LADO} mm")
    print(f"   Radio inscrito: {RADIO_INSCRITO:.1f} mm")
    print(f"   Tamaño marcador ArUco: {MARKER_SIZE_MM} mm")
    
    # Tamaño A4 en píxeles a 300 DPI
    a4_width = mm_to_pixels(210, DPI)
    a4_height = mm_to_pixels(297, DPI)
    
    # Crear imagen blanca
    plantilla = Image.new('RGB', (a4_width, a4_height), 'white')
    draw = ImageDraw.Draw(plantilla)
    
    # Tamaños en píxeles
    marker_size_px = mm_to_pixels(MARKER_SIZE_MM, DPI)
    pentagono_radius_px = mm_to_pixels(PENTAGONO_RADIO, DPI)
    
    # Configurar detector ArUco
    aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICT)
    
    # Disposición: 3 columnas x 4 filas
    cols = 3
    rows = 4
    margin = mm_to_pixels(10, DPI)  # Reducir margen
    spacing_x = mm_to_pixels(5, DPI)  # Reducir espaciado horizontal
    spacing_y = mm_to_pixels(5, DPI)  # Reducir espaciado vertical
    
    # Calcular tamaño de celda para que quepan todos
    available_width = a4_width - 2 * margin - (cols - 1) * spacing_x
    available_height = a4_height - 2 * margin - 100 - (rows - 1) * spacing_y - mm_to_pixels(60, DPI)
    cell_size = min(available_width // cols, available_height // rows)
    
    # Ajustar tamaño del pentágono y marcador proporcionalmente
    pentagono_radius_px = int(cell_size * 0.35)
    marker_size_px = int(pentagono_radius_px * 1.2)
    
    # Fuentes
    try:
        font_title = ImageFont.truetype("arial.ttf", 35)
        font_label = ImageFont.truetype("arial.ttf", 25)
        font_text = ImageFont.truetype("arial.ttf", 18)
    except:
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_text = ImageFont.load_default()
    
    # Título
    draw.text(
        (a4_width // 2, margin // 2),
        "MARCADORES ARUCO - DODECAEDRO 50mm",
        fill='black',
        font=font_title,
        anchor='mm'
    )
    
    # Generar y colocar los 12 marcadores
    marker_idx = 0
    for row in range(rows):
        for col in range(cols):
            if marker_idx >= len(MARKER_IDS):
                break
            
            marker_id = MARKER_IDS[marker_idx]
            
            # Generar marcador ArUco cuadrado
            marker_img = aruco.generateImageMarker(aruco_dict, marker_id, marker_size_px)
            marker_pil = Image.fromarray(marker_img)
            
            # Calcular posición del centro
            center_x = margin + col * (cell_size + spacing_x) + cell_size // 2
            center_y = margin + 80 + row * (cell_size + spacing_y) + cell_size // 2
            
            # Generar vértices del pentágono
            vertices = generar_pentagono_vertices(center_x, center_y, pentagono_radius_px)
            
            # Dibujar pentágono (borde)
            draw.polygon(vertices, outline='black', width=3)
            
            # Dibujar líneas de corte punteadas
            for i in range(5):
                v1 = vertices[i]
                v2 = vertices[(i + 1) % 5]
                # Línea punteada
                steps = 20
                for j in range(0, steps, 2):
                    x1 = v1[0] + (v2[0] - v1[0]) * j / steps
                    y1 = v1[1] + (v2[1] - v1[1]) * j / steps
                    x2 = v1[0] + (v2[0] - v1[0]) * (j + 1) / steps
                    y2 = v1[1] + (v2[1] - v1[1]) * (j + 1) / steps
                    draw.line([x1, y1, x2, y2], fill='gray', width=1)
            
            # Pegar marcador ArUco (centrado)
            marker_x = center_x - marker_size_px // 2
            marker_y = center_y - marker_size_px // 2
            plantilla.paste(marker_pil, (int(marker_x), int(marker_y)))
            
            # Etiqueta con ID
            draw.text(
                (center_x, center_y + pentagono_radius_px + 25),
                f"ID {marker_id}",
                fill='red',
                font=font_label,
                anchor='mm'
            )
            
            marker_idx += 1
    
    # Instrucciones
    instrucciones_y = a4_height - mm_to_pixels(50, DPI)
    instrucciones = [
        "INSTRUCCIONES:",
        "1. Imprimir en papel adhesivo mate o papel normal (escala 100%)",
        "2. Recortar cada pentágono por las líneas negras",
        "3. Pegar un marcador en cada cara del dodecaedro impreso en 3D",
        f"4. Dodecaedro: {DODECAEDRO_LADO} mm de lado, marcadores: ~{MARKER_SIZE_MM} mm",
        "5. Asegurarse de que queden bien planos y centrados"
    ]
    
    for i, linea in enumerate(instrucciones):
        draw.text(
            (margin, instrucciones_y + i * 22),
            linea,
            fill='black',
            font=font_text
        )
    
    # Guardar plantilla
    plantilla_path = os.path.join(OUTPUT_DIR, "plantilla_dodecaedro_50mm.png")
    plantilla.save(plantilla_path, dpi=(DPI, DPI))
    print(f"  ✅ Plantilla guardada: {plantilla_path}")
    
    return plantilla_path


def crear_guia_dodecaedro_50mm():
    """Crea guía específica para dodecaedro de 50 mm"""
    guia = f"""
GUÍA DE ENSAMBLAJE - DODECAEDRO ARUCO 50mm
==========================================

ESPECIFICACIONES:
-----------------
Dodecaedro: {DODECAEDRO_LADO} mm de lado (por arista)
Diámetro total: ~{DODECAEDRO_LADO * 3.1:.0f} mm
Caras: 12 pentágonos regulares
Marcadores ArUco: ~{MARKER_SIZE_MM} mm (cuadrados)
IDs: 1-12

MATERIALES:
-----------
✅ Dodecaedro impreso en 3D ({DODECAEDRO_LADO}mm de lado) en PLA blanco mate
✅ Plantilla impresa (plantilla_dodecaedro_50mm.png)
✅ Tijeras afiladas o cutter
✅ Pegamento en barra o papel adhesivo
✅ Paciencia (recortar pentágonos requiere precisión)

PASOS:
------

1. IMPRIMIR PLANTILLA
   - Imprimir plantilla_dodecaedro_50mm.png en papel mate
   - Configurar impresora a escala 100% (sin ajustar)
   - Verificar que los pentágonos tengan el tamaño correcto

2. RECORTAR MARCADORES
   - Recortar cada pentágono por las líneas negras
   - Usar tijeras muy afiladas para bordes limpios
   - Los pentágonos deben quedar simétricos
   - Tomar tiempo, la precisión es importante

3. PREPARAR DODECAEDRO
   - Limpiar cada cara con alcohol
   - Identificar qué cara será cada ID (opcional)
   - Asegurarse de que estén secas

4. PEGAR MARCADORES
   - Aplicar pegamento uniformemente
   - Centrar el marcador en cada cara pentagonal
   - El marcador cuadrado debe quedar centrado en el pentágono
   - Presionar firmemente
   - Eliminar burbujas de aire

5. VERIFICACIÓN
   - Todos los marcadores deben estar planos
   - Sin arrugas ni burbujas
   - Probar con: python aruco_test.py

CONFIGURACIÓN DEL DODECAEDRO EN EL SLICER 3D:
---------------------------------------------
Lado de arista: {DODECAEDRO_LADO} mm
Material: PLA blanco mate
Relleno: 15-20%
Soportes: NO (orientar bien)
Tiempo: ~3-4 horas
Filamento: ~30-40 g

ORIENTACIÓN PARA IMPRESIÓN:
---------------------------
- Colocar una cara plana sobre la cama
- Usar "Lay flat" si está disponible
- Esto evita necesidad de soportes

MONTAJE EN LA LEZNA:
--------------------
1. Limpiar el mango de la lezna
2. Aplicar pegamento fuerte (cianoacrilato)
3. Pegar el dodecaedro firmemente
4. Dejar secar 24 horas
5. Verificar que no interfiera con el uso

VENTAJAS DEL DODECAEDRO 50mm:
-----------------------------
✅ Compacto ({DODECAEDRO_LADO}mm de lado)
✅ 12 caras = mejor cobertura angular que cubo
✅ Siempre hay una cara visible
✅ Ideal para rotaciones libres de la lezna
✅ Tracking continuo durante perforación

DESVENTAJAS:
------------
⚠️ Más complejo de ensamblar que un cubo
⚠️ Recortar pentágonos requiere más precisión
⚠️ Marcadores más pequeños (~{MARKER_SIZE_MM}mm vs 40mm en cubo)

COMPARACIÓN CON CUBO:
---------------------
Cubo 50mm:
- 6 caras cuadradas
- Marcadores de 40mm
- Más fácil de ensamblar
- Suficiente para rotaciones moderadas

Dodecaedro 50mm:
- 12 caras pentagonales
- Marcadores de ~{MARKER_SIZE_MM}mm
- Más complejo de ensamblar
- Mejor para rotaciones libres

RECOMENDACIÓN:
--------------
Si es tu primera vez, considera empezar con un CUBO de 50mm.
Si necesitas tracking perfecto en cualquier orientación, usa el DODECAEDRO.

¡Tu dodecaedro ArUco está listo para navegación quirúrgica profesional!
"""
    
    guia_path = os.path.join(OUTPUT_DIR, "GUIA_DODECAEDRO_50MM.txt")
    with open(guia_path, 'w', encoding='utf-8') as f:
        f.write(guia)
    
    print(f"\n✅ Guía de dodecaedro creada: {guia_path}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("GENERADOR DE PLANTILLA - DODECAEDRO ARUCO 50mm")
    print("=" * 70)
    print(f"Lado del dodecaedro: {DODECAEDRO_LADO} mm")
    print(f"Tamaño de marcador: ~{MARKER_SIZE_MM} mm")
    print(f"Número de caras: 12 (pentágonos)")
    print(f"IDs: {MARKER_IDS}")
    print("=" * 70)
    
    # Verificar directorio
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✅ Directorio '{OUTPUT_DIR}' creado")
    
    # Generar plantilla
    plantilla_path = generar_plantilla_dodecaedro_50mm()
    
    # Crear guía
    crear_guia_dodecaedro_50mm()
    
    print("\n" + "=" * 70)
    print("✅ GENERACIÓN COMPLETADA")
    print("=" * 70)
    print(f"\nArchivo principal para imprimir:")
    print(f"  📄 {plantilla_path}")
    print(f"\nGuía de ensamblaje:")
    print(f"  📄 {os.path.join(OUTPUT_DIR, 'GUIA_DODECAEDRO_50MM.txt')}")
    print("\n" + "=" * 70)
    print("PRÓXIMOS PASOS:")
    print("=" * 70)
    print("1. Imprimir plantilla_dodecaedro_50mm.png en papel mate")
    print(f"2. Imprimir dodecaedro de {DODECAEDRO_LADO}mm de lado en 3D (PLA blanco mate)")
    print("3. Recortar los 12 marcadores pentagonales con precisión")
    print("4. Pegar un marcador centrado en cada cara del dodecaedro")
    print("5. Montar el dodecaedro en la lezna")
    print("6. Probar con: python aruco_test.py")
    print("=" * 70)
    print("\n💡 NOTA: Si es tu primera vez, considera usar un CUBO en lugar")
    print("   del dodecaedro. Es más fácil de ensamblar y funciona bien.")
    print("=" * 70)


if __name__ == "__main__":
    main()
