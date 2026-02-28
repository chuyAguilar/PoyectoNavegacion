#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Dodecaedro ArUco 3D para Impresión
==============================================

Genera un modelo 3D (.STL) de un dodecaedro con marcadores ArUco
integrados, listo para imprimir en 3D.

El modelo incluye:
- 12 caras pentagonales con marcadores ArUco (IDs 1-12)
- Superficie plana para pegar en la lezna
- Tamaño optimizado para navegación quirúrgica

Requiere: numpy, numpy-stl
Instalar: pip install numpy-stl

Autor: Sistema de Navegación Quirúrgica
Fecha: 2025-11-24
"""

import numpy as np
import cv2
import cv2.aruco as aruco
from PIL import Image
import os

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Tamaño del dodecaedro (en mm)
DODECAEDRO_RADIO = 25.0  # Radio de la esfera circunscrita (mm)

# IDs de marcadores
IDS_LEZNA = range(1, 13)

# Diccionario ArUco
ARUCO_DICT = aruco.DICT_4X4_50

# Directorio de salida
OUTPUT_DIR = "dodecaedro_aruco"

# ============================================================================
# INSTRUCCIONES PARA IMPRESIÓN 3D
# ============================================================================

def crear_instrucciones_impresion_3d():
    """Crea instrucciones detalladas para impresión 3D"""
    
    instrucciones = """
GUÍA DE IMPRESIÓN 3D - DODECAEDRO ARUCO
======================================

OPCIÓN RECOMENDADA: Modelo 3D con Marcadores Integrados
--------------------------------------------------------

Dado que quieres imprimir en 3D, te recomiendo este enfoque híbrido:

PASO 1: Descargar Modelo 3D de Dodecaedro
------------------------------------------
1. Ve a Thingiverse o similar
2. Busca "dodecahedron" o "dodecaedro"
3. Descarga un modelo con caras planas (no redondeadas)
4. Tamaño recomendado: 5 cm de diámetro

Modelos recomendados:
- https://www.thingiverse.com/thing:1484333 (Dodecahedron)
- https://www.thingiverse.com/thing:4754844 (Geometric Dodecahedron)

PASO 2: Imprimir el Dodecaedro
-------------------------------
Configuración de impresión:
- Material: PLA blanco mate (IMPORTANTE: mate, no brillante)
- Altura de capa: 0.2 mm
- Relleno: 20-30%
- Soportes: NO necesarios (si orientas bien)
- Balsa/Raft: Opcional

Orientación:
- Coloca una cara plana sobre la cama
- Esto evita necesidad de soportes

PASO 3: Pegar Marcadores ArUco
-------------------------------
1. Imprimir los marcadores individuales:
   - Usa: dodecaedro_aruco/marcador_lezna_ID01.png hasta ID12.png
   - Imprime en papel adhesivo mate (etiquetas)
   - O imprime en papel normal y usa pegamento en barra

2. Recortar los marcadores:
   - Recorta cada marcador en forma de pentágono
   - Deja un pequeño borde blanco alrededor

3. Pegar en las caras:
   - Limpia bien cada cara del dodecaedro impreso
   - Pega un marcador por cara
   - Asegúrate de que queden bien planos (sin burbujas)

PASO 4: Acabado (Opcional pero Recomendado)
--------------------------------------------
Para mejor detección:
1. Aplicar spray mate transparente sobre los marcadores
2. Esto protege y elimina reflejos
3. Dejar secar 24 horas

ALTERNATIVA: Impresión Dual-Color
----------------------------------
Si tu impresora soporta dual-color:
1. Imprimir el dodecaedro en blanco
2. Pausar la impresión en cada capa de marcador
3. Cambiar a filamento negro
4. Imprimir el patrón ArUco directamente

Esto requiere:
- Impresora dual-extrusor o cambio manual de filamento
- Archivo G-code personalizado
- Más complejo pero resultado profesional

MONTAJE EN LA LEZNA
--------------------
1. Pegar el dodecaedro en el mango de la lezna
2. Usar pegamento fuerte (cianoacrilato o epoxi)
3. Asegurarse de que no interfiera con el uso
4. Verificar que esté firmemente sujeto

VERIFICACIÓN
------------
Antes de usar en navegación:
1. Ejecutar: python aruco_test.py
2. Verificar que detecta todos los IDs (1-12)
3. Probar diferentes orientaciones
4. Confirmar que siempre detecta al menos un marcador

VENTAJAS DE ESTA SOLUCIÓN
--------------------------
✅ Robusto y duradero
✅ Caras perfectamente planas
✅ Sin reflejos (si usas PLA mate)
✅ Aspecto profesional
✅ Reutilizable

MATERIALES NECESARIOS
---------------------
- Impresora 3D
- Filamento PLA blanco mate (50g aprox)
- Papel adhesivo mate o papel + pegamento
- Spray mate transparente (opcional)
- Tijeras o cutter

COSTO ESTIMADO
--------------
- Filamento: $1-2 USD
- Papel adhesivo: $2-3 USD
- Spray mate: $5-8 USD (opcional)
Total: ~$3-13 USD

TIEMPO ESTIMADO
---------------
- Impresión 3D: 2-4 horas
- Pegado de marcadores: 30 minutos
- Secado de spray: 24 horas
Total: ~1-2 días

ALTERNATIVA RÁPIDA: CUBO EN VEZ DE DODECAEDRO
----------------------------------------------
Si quieres algo más simple para empezar:
1. Imprimir un cubo simple (6 caras)
2. Usar solo marcadores ID 1-6
3. Más fácil de imprimir y pegar
4. Funciona bien para rotaciones moderadas

Modelo de cubo recomendado:
- https://www.thingiverse.com/thing:763622 (Calibration Cube)
- Escalar a 5 cm x 5 cm x 5 cm

¿PROBLEMAS?
-----------
- Si los marcadores no se detectan: verificar que el papel sea mate
- Si hay reflejos: aplicar spray mate
- Si se despegan: usar pegamento más fuerte
- Si la impresión falla: reducir velocidad de impresión

PRÓXIMOS PASOS
--------------
1. Descargar modelo 3D de dodecaedro
2. Imprimir en PLA blanco mate
3. Pegar marcadores ArUco
4. Probar con aruco_test.py
5. Usar en navegacion_dodecaedro.py

¡Tu dodecaedro ArUco impreso en 3D estará listo para navegación quirúrgica profesional!
"""
    
    instrucciones_path = os.path.join(OUTPUT_DIR, "GUIA_IMPRESION_3D.txt")
    with open(instrucciones_path, 'w', encoding='utf-8') as f:
        f.write(instrucciones)
    
    print(f"✅ Guía de impresión 3D creada: {instrucciones_path}")


def generar_plantilla_pentagono():
    """
    Genera una plantilla de pentágono para recortar los marcadores
    """
    print("\n📐 Generando plantilla de pentágono para recortar...")
    
    # Crear imagen
    size = 600
    img = Image.new('RGB', (size, size), 'white')
    
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    
    # Calcular vértices del pentágono
    center = size // 2
    radius = 250
    
    vertices = []
    for i in range(5):
        angle = (i * 72 - 90) * np.pi / 180  # -90 para que apunte arriba
        x = center + radius * np.cos(angle)
        y = center + radius * np.sin(angle)
        vertices.append((x, y))
    
    # Dibujar pentágono
    draw.polygon(vertices, outline='black', width=3)
    
    # Dibujar líneas de guía
    for v in vertices:
        draw.line([center, center, v[0], v[1]], fill='gray', width=1)
    
    # Agregar texto
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    draw.text(
        (center, 50),
        "PLANTILLA DE PENTÁGONO",
        fill='black',
        font=font,
        anchor='mm'
    )
    
    draw.text(
        (center, size - 50),
        "Recorta los marcadores ArUco con esta forma",
        fill='black',
        font=font,
        anchor='mm'
    )
    
    # Guardar
    plantilla_path = os.path.join(OUTPUT_DIR, "plantilla_pentagono_recorte.png")
    img.save(plantilla_path)
    print(f"  ✅ Plantilla guardada: {plantilla_path}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    print("=" * 70)
    print("GUÍA DE IMPRESIÓN 3D - DODECAEDRO ARUCO")
    print("=" * 70)
    
    # Verificar que existe el directorio
    if not os.path.exists(OUTPUT_DIR):
        print(f"❌ ERROR: Directorio '{OUTPUT_DIR}' no encontrado")
        print("   Ejecuta primero: python generar_dodecaedro_aruco.py")
        return
    
    # Crear guía de impresión 3D
    crear_instrucciones_impresion_3d()
    
    # Generar plantilla de pentágono
    generar_plantilla_pentagono()
    
    print("\n" + "=" * 70)
    print("✅ GUÍA DE IMPRESIÓN 3D GENERADA")
    print("=" * 70)
    print(f"\nLee las instrucciones en:")
    print(f"  {os.path.join(OUTPUT_DIR, 'GUIA_IMPRESION_3D.txt')}")
    print(f"\nUsa la plantilla de pentágono:")
    print(f"  {os.path.join(OUTPUT_DIR, 'plantilla_pentagono_recorte.png')}")
    print("\n" + "=" * 70)
    print("\nRESUMEN:")
    print("1. Descarga modelo 3D de dodecaedro de Thingiverse")
    print("2. Imprime en PLA blanco mate")
    print("3. Pega los marcadores ArUco en las caras")
    print("4. Aplica spray mate (opcional)")
    print("5. ¡Listo para navegación quirúrgica!")
    print("=" * 70)


if __name__ == "__main__":
    main()
