import cv2
import numpy as np
import os
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# =========================
# CONFIGURACION
# =========================
DPI = 300
ARUCO_DICT_ID = cv2.aruco.DICT_6X6_250

# Tamaños
BONE_MARKER_SIZE_MM = 45.5
INST_MARKER_PATTERN_MM = 16.0
INST_MARKER_CANVAS_MM = 22.0
CHESSBOARD_SQUARE_MM = 25.0

# Configuracion Chessboard (intersecciones internas)
CHESSBOARD_INNER_X = 8
CHESSBOARD_INNER_Y = 6

# =========================
# FUNCIONES
# =========================

def mm_to_pixels(mm_val, dpi=DPI):
    """
    Convierte milímetros a píxeles basándose en los DPI.
    1 pulgada = 25.4 mm
    """
    return int((mm_val / 25.4) * dpi)

def generate_aruco_marker(dictionary_id, marker_id, size_mm, canvas_mm=None, dpi=DPI):
    """
    Genera la imagen de un marcador ArUco.
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
    marker_px = mm_to_pixels(size_mm, dpi)
    # create standard marker image with 1-bit module border as required by OpenCV
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_px)
    
    if canvas_mm is not None:
        canvas_px = mm_to_pixels(canvas_mm, dpi)
        canvas = np.full((canvas_px, canvas_px), 255, dtype=np.uint8)
        offset = (canvas_px - marker_px) // 2
        canvas[offset:offset+marker_px, offset:offset+marker_px] = marker_img
        return canvas
        
    return marker_img

def generate_chessboard(inner_x=CHESSBOARD_INNER_X, inner_y=CHESSBOARD_INNER_Y, square_mms=CHESSBOARD_SQUARE_MM, dpi=DPI):
    """
    Genera un patrón de calibración (chessboard).
    Note: Si las esquinas internas son 8x6, la cuadrícula debe tener 9x7 cuadrados.
    """
    squares_x = inner_x + 1
    squares_y = inner_y + 1
    
    square_px = mm_to_pixels(square_mms, dpi)
    
    width_px = squares_x * square_px
    height_px = squares_y * square_px
    
    # Fondo blanco
    board = np.full((height_px, width_px), 255, dtype=np.uint8)
    
    # Dibujar cuadrados negros
    for y in range(squares_y):
        for x in range(squares_x):
            # Alternar colores, típico para chessboard OpenCV
            if (x + y) % 2 == 1:
                top_left = (x * square_px, y * square_px)
                bottom_right = ((x + 1) * square_px, (y + 1) * square_px)
                cv2.rectangle(board, top_left, bottom_right, 0, -1)
                
    return board

# =========================
# FUNCION PRINCIPAL
# =========================

def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
    os.makedirs(out_dir, exist_ok=True)
    pdf_filename = os.path.join(out_dir, "printables_6x6.pdf")
    
    # Crear un PDF A4 (210 x 297 mm)
    c = canvas.Canvas(pdf_filename, pagesize=A4)
    page_w_mm, page_h_mm = 210, 297
    
    # Directorio temporal para las imagenes de opencv a inyectar en reportlab
    temp_dir = tempfile.mkdtemp()
    
    def add_image_to_pdf(img, x_mm, y_mm, size_x_mm, size_y_mm):
        # Guardar como PNG
        tmp_path = os.path.join(temp_dir, f"temp_{np.random.randint(100000)}.png")
        cv2.imwrite(tmp_path, img)
        # reportlab dibuja desde abajo-izquierda (x, y, width, height)
        # Asegura de poner el tamaño EXACTO físico en mm
        c.drawImage(tmp_path, x_mm * mm, y_mm * mm, width=size_x_mm * mm, height=size_y_mm * mm)

    print("Generando marcadores para PDF...")
    
    # --- PÁGINA 1: Marcadores del Hueso (IDs 0, 1) ---
    print(f"Página 1: Marcadores {0},{1}. Tamaño: {BONE_MARKER_SIZE_MM}mm.")
    img_m0 = generate_aruco_marker(ARUCO_DICT_ID, 0, BONE_MARKER_SIZE_MM)
    img_m1 = generate_aruco_marker(ARUCO_DICT_ID, 1, BONE_MARKER_SIZE_MM)
    
    # Centrados horizontalmente
    x_pos = (page_w_mm - BONE_MARKER_SIZE_MM) / 2
    
    # --- 1) Instrucciones de impresion ---
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w_mm / 2 * mm, 280 * mm, "IMPRIMIR A ESCALA 100%")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(page_w_mm / 2 * mm, 273 * mm, "NO AJUSTAR AL PAPEL")
    c.drawCentredString(page_w_mm / 2 * mm, 266 * mm, 'NO "FIT TO PAGE"')
    
    # Arriba (marcador 0) - Reportlab Y mide desde abajo
    y_pos_0 = 297 - 60 - BONE_MARKER_SIZE_MM
    add_image_to_pdf(img_m0, x_pos, y_pos_0, BONE_MARKER_SIZE_MM, BONE_MARKER_SIZE_MM)
    c.setFont("Helvetica", 12)
    c.drawString(x_pos * mm, (y_pos_0 + BONE_MARKER_SIZE_MM + 5) * mm, f"ID: 0  |  Size: {BONE_MARKER_SIZE_MM} mm")
    
    # --- 2) Regla de verificacion (100 mm) ---
    ruler_y = 175
    c.setLineWidth(1)
    c.line(55 * mm, ruler_y * mm, 155 * mm, ruler_y * mm)
    c.line(55 * mm, (ruler_y - 2) * mm, 55 * mm, (ruler_y + 2) * mm)
    c.line(105 * mm, (ruler_y - 2) * mm, 105 * mm, (ruler_y + 2) * mm)
    c.line(155 * mm, (ruler_y - 2) * mm, 155 * mm, (ruler_y + 2) * mm)
    c.setFont("Helvetica", 10)
    c.drawCentredString(55 * mm, (ruler_y + 3) * mm, "0 mm")
    c.drawCentredString(105 * mm, (ruler_y + 3) * mm, "50 mm")
    c.drawCentredString(155 * mm, (ruler_y + 3) * mm, "100 mm")
    c.drawCentredString(105 * mm, (ruler_y - 6) * mm, "Verificar con regla: esta línea debe medir exactamente 100 mm")
    
    # --- 3) Cuadro de calibracion (50x50 mm) ---
    box_size = 50
    box_x = (page_w_mm - box_size) / 2
    box_y = 115
    c.rect(box_x * mm, box_y * mm, box_size * mm, box_size * mm)
    c.drawCentredString(105 * mm, (box_y - 6) * mm, "Cuadro de verificación: 50 mm × 50 mm")
    
    # Abajo (marcador 1)
    y_pos_1 = 60
    add_image_to_pdf(img_m1, x_pos, y_pos_1, BONE_MARKER_SIZE_MM, BONE_MARKER_SIZE_MM)
    c.setFont("Helvetica", 12)
    c.drawString(x_pos * mm, (y_pos_1 + BONE_MARKER_SIZE_MM + 5) * mm, f"ID: 1  |  Size: {BONE_MARKER_SIZE_MM} mm")
    
    c.showPage()
    
    # --- PÁGINA 2: Marcadores de Instrumento (IDs 10–21) ---
    print(f"Página 2: Marcadores del 10 al 21. Tamaño canvas: {INST_MARKER_CANVAS_MM}mm (Patron: {INST_MARKER_PATTERN_MM}mm).")
    # 12 marcadores -> rejilla de 3 columnas x 4 filas
    col_spacing = 210 / 3
    row_spacing = 297 / 4
    
    for idx_in_page, m_id in enumerate(range(10, 22)):
        row = idx_in_page // 3
        col = idx_in_page % 3
        
        # Celda: col * col_spacing ... (col+1)*col_spacing
        cell_x = col * col_spacing
        cell_y = 297 - (row + 1) * row_spacing  # y desde abajo
        
        # Centrar marcador en su celda
        pos_x = cell_x + (col_spacing - INST_MARKER_CANVAS_MM) / 2
        pos_y = cell_y + (row_spacing - INST_MARKER_CANVAS_MM) / 2
        
        img_inst = generate_aruco_marker(ARUCO_DICT_ID, m_id, INST_MARKER_PATTERN_MM, INST_MARKER_CANVAS_MM)
        add_image_to_pdf(img_inst, pos_x, pos_y, INST_MARKER_CANVAS_MM, INST_MARKER_CANVAS_MM)
        
        c.setFont("Helvetica", 10)
        c.drawString(pos_x * mm, (pos_y + INST_MARKER_CANVAS_MM + 2) * mm, f"ID: {m_id}")
    
    c.showPage()
    
    # --- PÁGINA 3: Chessboard ---
    # Tamaño total fisico: 9 (columnas) * 25mm = 225mm. 7 (filas) * 25mm = 175mm.
    # Como 225mm > ancho A4 (210mm), necesitamos poner la pagina en orientacion apaisada (Landscape)
    c.setPageSize((297 * mm, 210 * mm)) 
    
    cb_w_mm = (CHESSBOARD_INNER_X + 1) * CHESSBOARD_SQUARE_MM # 225 mm
    cb_h_mm = (CHESSBOARD_INNER_Y + 1) * CHESSBOARD_SQUARE_MM # 175 mm
    
    print(f"Página 3: Chessboard. Tamaño Físico: {cb_w_mm}x{cb_h_mm} mm.")
    cb_x = (297 - cb_w_mm) / 2
    cb_y = (210 - cb_h_mm) / 2
    
    cb_img = generate_chessboard(CHESSBOARD_INNER_X, CHESSBOARD_INNER_Y, CHESSBOARD_SQUARE_MM)
    add_image_to_pdf(cb_img, cb_x, cb_y, cb_w_mm, cb_h_mm)
    
    c.setFont("Helvetica", 12)
    c.drawString(cb_x * mm, (cb_y + cb_h_mm + 5) * mm, 
                 f"Chessboard | Esquinas internas: {CHESSBOARD_INNER_X}x{CHESSBOARD_INNER_Y} | Cuadrado: {CHESSBOARD_SQUARE_MM} mm")
    
    c.save()
    
    # Cleanup temp
    for file in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, file))
    os.rmdir(temp_dir)
    
    print(f"\n¡Éxito! Archivo generado: {pdf_filename}")
    print("El PDF contiene dimensiones físicas EXACTAS para impresión sin escalado automático.")

if __name__ == '__main__':
    main()
