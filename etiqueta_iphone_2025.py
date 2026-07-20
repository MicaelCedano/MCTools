# -*- coding: utf-8 -*-
"""
Generador de Etiquetas para iPhone
Versión: 3.2.5 (Personalizado)
Autor: Micael (Modificado por Asistente de IA)
Fecha: 2025-08-15

Cambios en v3.2.5:
- Adaptado para iPhones: S/N cambiado a IMEI
- Eliminadas las plantillas
- Eliminadas las especificaciones
- Eliminada la condición final que impedía el dibujado del código de barras en el PDF.
- Reajustados los márgenes y espaciados para garantizar que todos los elementos quepan.
- Se fuerza el dibujado secuencial y completo de todos los elementos.
"""
from PIL import Image, ImageDraw, ImageFont, ImageTk
import barcode
from barcode.writer import ImageWriter
import qrcode
import io
import customtkinter
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import platform
import subprocess
import tempfile
import atexit
import json
import urllib.request
import threading
import sys
import webbrowser

# --- Dependencias para Guardado/Impresión en PDF ---
PDF_SAVE_ENABLED = False
try:
    from reportlab.pdfgen import canvas as reportlab_canvas
    from reportlab.lib.pagesizes import inch
    from reportlab.lib.utils import ImageReader as ReportLabImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_SAVE_ENABLED = True
except ImportError:
    print("ADVERTENCIA: La librería 'ReportLab' no está instalada. El guardado en PDF y la impresión estarán deshabilitados.")
    PDF_SAVE_ENABLED = False

# --- Corregir Directorio de Trabajo ---
def corregir_directorio_trabajo():
    if getattr(sys, 'frozen', False):
        dir_path = os.path.dirname(sys.executable)
    else:
        dir_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(dir_path)

corregir_directorio_trabajo()

# --- Constantes ---
VERSION = "3.0"
REPO_OWNER = "MicaelCedano"
REPO_NAME = "McTools"
CONFIG_FILE_NAME = "etiqueta_config.json"
LABEL_WIDTH_INCHES = 4
LABEL_HEIGHT_INCHES = 3
PREVIEW_MAX_WIDTH = 380
PREVIEW_MAX_HEIGHT = int(PREVIEW_MAX_WIDTH * (LABEL_HEIGHT_INCHES / LABEL_WIDTH_INCHES))

# --- Rutas de Fuentes (Asegúrate de que estos archivos .ttf estén en la misma carpeta o en Windows/Fonts) ---
def _obtener_ruta_fuente(nombre_fuente):
    if os.path.exists(nombre_fuente):
        return nombre_fuente
    if platform.system() == "Windows":
        ruta_sistema = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", nombre_fuente)
        if os.path.exists(ruta_sistema):
            return ruta_sistema
    return nombre_fuente

FONT_BOLD_PATH_TTF = _obtener_ruta_fuente("arialbd.ttf")
FONT_REGULAR_PATH_TTF = _obtener_ruta_fuente("arial.ttf")

# --- Cache de Fuentes PIL ---
_fuentes_pil_cache = {}

def obtener_fuente_pil(ruta_fuente, tamano):
    clave = (ruta_fuente, tamano)
    if clave not in _fuentes_pil_cache:
        try:
            if os.path.exists(ruta_fuente):
                _fuentes_pil_cache[clave] = ImageFont.truetype(ruta_fuente, size=tamano)
            else:
                _fuentes_pil_cache[clave] = ImageFont.load_default()
        except Exception:
            _fuentes_pil_cache[clave] = ImageFont.load_default()
    return _fuentes_pil_cache[clave]

# --- Nombres de Fuentes para ReportLab (PDF) ---
RL_FONT_BOLD_NAME = "ArialBoldRegistered"
RL_FONT_REGULAR_NAME = "ArialRegularRegistered"


# --- Variables Globales ---
SUMATRA_PDF_PATH = None
temporary_files_to_delete = []

# --- Funciones de Configuración y Limpieza ---

def _read_config():
    """Lee el archivo de configuración JSON de forma segura."""
    if os.path.exists(CONFIG_FILE_NAME):
        with open(CONFIG_FILE_NAME, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def _write_config(config_data):
    """Escribe en el archivo de configuración JSON."""
    try:
        with open(CONFIG_FILE_NAME, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error al guardar configuración: {e}")

def cargar_config_inicial():
    """Carga la configuración de SumatraPDF al inicio."""
    global SUMATRA_PDF_PATH
    config = _read_config()
    path_guardado = config.get("sumatra_pdf_path")
    if path_guardado and os.path.exists(path_guardado) and os.path.isfile(path_guardado):
        SUMATRA_PDF_PATH = path_guardado
        print(f"SumatraPDF cargado desde config: {SUMATRA_PDF_PATH}")
    else:
        detectar_sumatra_si_no_configurado()

def cargar_logo_config():
    """Carga la ruta del logo guardada en la configuración."""
    config = _read_config()
    logo_path = config.get("logo_path")
    if logo_path and os.path.exists(logo_path) and os.path.isfile(logo_path):
        return logo_path
    return "logo.png"  # Valor por defecto

def guardar_logo_config(logo_path):
    """Guarda la ruta del logo en el archivo de configuración."""
    if logo_path:
        config = _read_config()
        config["logo_path"] = logo_path
        _write_config(config)

def guardar_config_sumatra():
    """Guarda solo la ruta de SumatraPDF en el archivo de configuración."""
    if SUMATRA_PDF_PATH and platform.system() == "Windows":
        config = _read_config()
        config["sumatra_pdf_path"] = SUMATRA_PDF_PATH
        _write_config(config)

def detectar_sumatra_si_no_configurado():
    """Intenta encontrar SumatraPDF en rutas comunes si no está configurado."""
    global SUMATRA_PDF_PATH
    if SUMATRA_PDF_PATH or platform.system() != "Windows": return
    SUMATRA_PDF_DEFAULT_PATHS = [
        "SumatraPDF.exe",
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "SumatraPDF", "SumatraPDF.exe"),
    ]
    for path_candidate in SUMATRA_PDF_DEFAULT_PATHS:
        try:
            result = subprocess.run(["where", os.path.basename(path_candidate)], capture_output=True, text=True, check=False, shell=True)
            if result.returncode == 0 and result.stdout.strip():
                SUMATRA_PDF_PATH = result.stdout.strip().splitlines()[0]
                print(f"SumatraPDF detectado en el PATH: {SUMATRA_PDF_PATH}")
                return
            elif os.path.exists(path_candidate) and os.path.isfile(path_candidate):
                SUMATRA_PDF_PATH = path_candidate
                print(f"SumatraPDF detectado en: {SUMATRA_PDF_PATH}")
                return
        except Exception: pass
    print("ADVERTENCIA: SumatraPDF no se detectó automáticamente.")

def cleanup_temp_files():
    """Elimina los archivos temporales creados durante la sesión."""
    for temp_file_path in list(temporary_files_to_delete):
        try:
            if os.path.exists(temp_file_path): os.remove(temp_file_path)
            if temp_file_path in temporary_files_to_delete:
                temporary_files_to_delete.remove(temp_file_path)
        except Exception as e:
            print(f"Error al limpiar archivo temporal {temp_file_path}: {e}")

atexit.register(cleanup_temp_files)
atexit.register(guardar_config_sumatra)

def cargar_fuentes_pdf():
    """Registra las fuentes TTF en ReportLab, usando Helvetica como fallback seguro."""
    global RL_FONT_BOLD_NAME, RL_FONT_REGULAR_NAME
    if not PDF_SAVE_ENABLED: return
    try:
        if os.path.exists(FONT_BOLD_PATH_TTF):
            pdfmetrics.registerFont(TTFont(RL_FONT_BOLD_NAME, FONT_BOLD_PATH_TTF))
        else: raise IOError(f"No se encontró '{FONT_BOLD_PATH_TTF}'.")
    except Exception:
        RL_FONT_BOLD_NAME = 'Helvetica-Bold'
    try:
        if os.path.exists(FONT_REGULAR_PATH_TTF):
            pdfmetrics.registerFont(TTFont(RL_FONT_REGULAR_NAME, FONT_REGULAR_PATH_TTF))
        else: raise IOError(f"No se encontró '{FONT_REGULAR_PATH_TTF}'.")
    except Exception:
        RL_FONT_REGULAR_NAME = 'Helvetica'

# --- FUNCIÓN DE PREVISUALIZACIÓN ---
# --- FUNCIÓN DE PREVISUALIZACIÓN (CÓDIGO DE BARRAS) ---
def _generar_etiqueta_barcode_pil_image(modelo, numero_serie, especificacion, logo_pil_image):
    """Genera la etiqueta como una imagen PIL, replicando la lógica del PDF."""
    DPI = 300
    LABEL_WIDTH_PX, LABEL_HEIGHT_PX = int(LABEL_WIDTH_INCHES * DPI), int(LABEL_HEIGHT_INCHES * DPI)
    
    TOP_MARGIN_PX = int(0.20 * DPI)
    SIDE_MARGIN_PX = int(0.15 * DPI)
    BOTTOM_MARGIN_PX = int(0.20 * DPI)
    
    image = Image.new("RGB", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), "white")
    draw = ImageDraw.Draw(image)
    
    font_bold = obtener_fuente_pil(FONT_BOLD_PATH_TTF, int(12 * DPI / 72))
    font_regular = obtener_fuente_pil(FONT_REGULAR_PATH_TTF, int(10 * DPI / 72))
    
    current_y = TOP_MARGIN_PX
    
    # 1. Logo
    if logo_pil_image:
        try:
            logo_img = logo_pil_image.copy()
            logo_max_width = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
            logo_max_height = int(0.28 * LABEL_HEIGHT_PX)
            logo_img.thumbnail((logo_max_width, logo_max_height), Image.Resampling.LANCZOS)
            
            logo_x = (LABEL_WIDTH_PX - logo_img.width) // 2
            image.paste(logo_img, (logo_x, current_y), logo_img)
            current_y += logo_img.height + int(0.1 * DPI)
        except Exception as e:
            print(f"Error procesando logo: {e}")

    # 2. Texto
    info_items = [
        (f"Modelo: {modelo}", font_bold, modelo),
        (f"IMEI: {numero_serie}", font_bold, numero_serie),
    ]
    
    for texto, font, valor in info_items:
        if not valor.strip(): continue
        x_pos = (LABEL_WIDTH_PX - draw.textlength(texto, font=font)) // 2
        draw.text((x_pos, current_y), texto, fill="black", font=font)
        current_y += font.size + 4

    # 3. Código de Barras
    if numero_serie:
        try:
            padding_before_bc = int(0.1 * DPI)
            current_y += padding_before_bc
            
            # Configurar parámetros optimizados para lectura
            # quiet_zone mínimo recomendado: 6.5 módulos para Code128
            # module_height: altura suficiente para escaneo confiable
            barcode_options = {
                'module_height': 15.0,  # Altura adecuada para lectura
                'module_width': 0.3,    # Ancho de módulo optimizado  
                'quiet_zone': 6.5,       # Zona silenciosa amplia (mínimo recomendado: 6.5)
                'write_text': False,    # El texto se dibuja por separado
                'text_distance': 5.0,
                'font_size': 10
            }
            
            code128 = barcode.get_barcode_class('code128')
            writer = ImageWriter()
            barcode_obj = code128(numero_serie, writer=writer)
            
            # Usar render() que devuelve directamente una imagen PIL
            barcode_pil = barcode_obj.render(barcode_options)
            barcode_pil = barcode_pil.convert('RGB')
            
            # Ajustar tamaño manteniendo proporción, pero sin degradar demasiado
            max_bc_w = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
            if barcode_pil.width > max_bc_w:
                ratio = max_bc_w / barcode_pil.width
                new_width = int(barcode_pil.width * ratio)
                new_height = int(barcode_pil.height * ratio)
                # Usar LANCZOS para mejor calidad en redimensionamiento
                barcode_pil = barcode_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

            sn_font = obtener_fuente_pil(FONT_REGULAR_PATH_TTF, int(9 * DPI / 72))
            sn_text_w = draw.textlength(numero_serie, font=sn_font)
            
            bc_x = (LABEL_WIDTH_PX - barcode_pil.width) // 2
            image.paste(barcode_pil, (bc_x, current_y))
            current_y += barcode_pil.height + int(0.03 * DPI)

            sn_x = (LABEL_WIDTH_PX - sn_text_w) // 2
            draw.text((sn_x, current_y), numero_serie, fill="black", font=sn_font)
        except Exception as e:
            print(f"Error generando código de barras en previsualización: {e}")
            
    return image

# --- FUNCIÓN DE GENERACIÓN DE PDF (CÓDIGO DE BARRAS) ---
def _generar_etiqueta_barcode_pdf_temporal(modelo, numero_serie, especificacion, path_logo_pil):
    if not PDF_SAVE_ENABLED: return None
    fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="etiqueta_")
    os.close(fd)
    temporary_files_to_delete.append(temp_pdf_path)
    
    c = reportlab_canvas.Canvas(temp_pdf_path, pagesize=(LABEL_WIDTH_INCHES * inch, LABEL_HEIGHT_INCHES * inch))
    width, height = LABEL_WIDTH_INCHES * inch, LABEL_HEIGHT_INCHES * inch
    
    # Márgenes
    margin_top = 0.20 * inch
    margin_sides = 0.15 * inch
    
    # Coordenada Y, se mueve de arriba hacia abajo
    current_y = height - margin_top

    # 1. Dibujar Logo
    try:
        if path_logo_pil and os.path.exists(path_logo_pil):
            logo_pil = Image.open(path_logo_pil)
            logo_max_width_pt = width - 2 * margin_sides
            logo_max_height_pt = 0.28 * height
            w_px, h_px = logo_pil.size
            aspect = h_px / float(w_px) if w_px > 0 else 0
            logo_w_pt = logo_max_width_pt
            logo_h_pt = logo_w_pt * aspect
            if logo_h_pt > logo_max_height_pt:
                logo_h_pt = logo_max_height_pt
                logo_w_pt = logo_h_pt / aspect if aspect > 0 else 0

            img_reader = ReportLabImageReader(logo_pil)
            
            current_y -= logo_h_pt
            c.drawImage(img_reader, (width - logo_w_pt) / 2, current_y, width=logo_w_pt, height=logo_h_pt, mask='auto')
            current_y -= 0.1 * inch
    except Exception as e:
        print(f"Error al procesar logo para PDF: {e}")

    # 2. Dibujar Texto
    info_items = [
        (f"Modelo: {modelo}", RL_FONT_BOLD_NAME, 12, modelo),
        (f"IMEI: {numero_serie}", RL_FONT_BOLD_NAME, 12, numero_serie),
    ]
    
    for texto, font, size, valor in info_items:
        if not valor.strip(): continue
        current_y -= size
        c.setFont(font, size)
        c.drawCentredString(width / 2, current_y, texto)
        current_y -= 4

    # 3. Dibujar Código de Barras
    if numero_serie:
        try:
            current_y -= 0.1 * inch
            
            # Configurar parámetros optimizados para lectura
            # quiet_zone mínimo recomendado: 6.5 módulos para Code128
            barcode_options = {
                'module_height': 15.0,  # Altura adecuada para lectura
                'module_width': 0.3,    # Ancho de módulo optimizado
                'quiet_zone': 6.5,      # Zona silenciosa amplia (mínimo recomendado: 6.5)
                'write_text': False,    # El texto se dibuja por separado
                'text_distance': 5.0,
                'font_size': 10
            }
            
            code128 = barcode.get_barcode_class('code128')
            writer = ImageWriter()
            barcode_obj = code128(numero_serie, writer=writer)
            
            # Generar imagen PIL y guardar en buffer para PDF
            barcode_pil_pdf = barcode_obj.render(barcode_options)
            barcode_pil_pdf = barcode_pil_pdf.convert('RGB')
            
            barcode_io = io.BytesIO()
            barcode_pil_pdf.save(barcode_io, format='PNG')
            barcode_io.seek(0)
            
            img_reader = ReportLabImageReader(barcode_io)
            bc_w, bc_h = img_reader.getSize()
            
            max_bc_w = width - (2 * margin_sides)
            if bc_w > max_bc_w:
                ratio = max_bc_w / bc_w
                bc_w, bc_h = bc_w * ratio, bc_h * ratio
            
            # Dibujar barcode
            current_y -= bc_h
            c.drawImage(img_reader, (width - bc_w) / 2, current_y, width=bc_w, height=bc_h, mask='auto')
            
            # Dibujar texto IMEI
            sn_font_size = 9
            current_y -= 3
            current_y -= sn_font_size
            c.setFont(RL_FONT_REGULAR_NAME, sn_font_size)
            c.drawCentredString(width / 2, current_y, numero_serie)

        except Exception as e:
            print(f"Error generando código de barras para PDF: {e}")
            
    c.save()
    return temp_pdf_path

# --- FUNCIONES DE DIBUJO (CÓDIGO QR) ---
def generar_texto_qr(imeis):
    """Genera el texto que se incluirá en el código QR con los IMEIs."""
    return "\n".join([imei.strip() for imei in imeis if imei.strip()])

def _generar_etiqueta_qr_pil_image(modelo, imeis, logo_pil_image):
    """Genera la etiqueta como una imagen PIL, replicando la lógica del PDF."""
    DPI = 300
    LABEL_WIDTH_PX, LABEL_HEIGHT_PX = int(LABEL_WIDTH_INCHES * DPI), int(LABEL_HEIGHT_INCHES * DPI)
    
    TOP_MARGIN_PX = int(0.20 * DPI)
    SIDE_MARGIN_PX = int(0.15 * DPI)
    BOTTOM_MARGIN_PX = int(0.25 * DPI)  # Aumentado para evitar que se corte el QR
    
    image = Image.new("RGB", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), "white")
    draw = ImageDraw.Draw(image)
    
    font_bold = obtener_fuente_pil(FONT_BOLD_PATH_TTF, int(12 * DPI / 72))
    font_regular = obtener_fuente_pil(FONT_REGULAR_PATH_TTF, int(10 * DPI / 72))
    
    current_y = TOP_MARGIN_PX
    
    # 1. Logo
    if logo_pil_image:
        try:
            logo_img = logo_pil_image.copy()
            logo_max_width = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
            logo_max_height = int(0.28 * LABEL_HEIGHT_PX)
            logo_img.thumbnail((logo_max_width, logo_max_height), Image.Resampling.LANCZOS)
            
            logo_x = (LABEL_WIDTH_PX - logo_img.width) // 2
            image.paste(logo_img, (logo_x, current_y), logo_img)
            current_y += logo_img.height + int(0.15 * DPI)
        except Exception as e:
            print(f"Error procesando logo: {e}")

    # 2. Texto - Modelo con cantidad de equipos
    imeis_validos = [imei.strip() for imei in imeis if imei.strip()]
    cantidad_equipos = len(imeis_validos)
    
    if modelo.strip():
        texto_modelo = f"Modelo: {modelo} - QTY {cantidad_equipos}"
        
        # Calcular ancho disponible
        ancho_disponible = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
        
        # Verificar si el texto es demasiado largo y ajustar tamaño de fuente
        texto_font = font_bold
        texto_largo = draw.textlength(texto_modelo, font=texto_font)
        
        if texto_largo > ancho_disponible:
            for size in [11, 10, 9, 8]:
                font_ajustado = obtener_fuente_pil(FONT_BOLD_PATH_TTF, int(size * DPI / 72))
                texto_largo = draw.textlength(texto_modelo, font=font_ajustado)
                if texto_largo <= ancho_disponible:
                    texto_font = font_ajustado
                    break
        
        try:
            bbox = draw.textbbox((0, 0), texto_modelo, font=texto_font)
            altura_texto = bbox[3] - bbox[1]
            current_y += int(0.1 * DPI)
        except:
            altura_texto = texto_font.size
            current_y += int(0.1 * DPI)
        
        x_pos = (LABEL_WIDTH_PX - draw.textlength(texto_modelo, font=texto_font)) // 2
        draw.text((x_pos, current_y), texto_modelo, fill="black", font=texto_font)
        current_y += altura_texto + int(0.05 * DPI)

    # 3. Código QR
    if imeis_validos:
        try:
            padding_before_qr = int(0.05 * DPI)
            current_y += padding_before_qr
            
            espacio_disponible_y = LABEL_HEIGHT_PX - current_y - BOTTOM_MARGIN_PX
            
            texto_qr = generar_texto_qr(imeis_validos)
            
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=4,
            )
            
            qr.add_data(texto_qr)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert('RGB')
            
            max_qr_w = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
            max_qr_h = espacio_disponible_y - int(0.05 * DPI)
            
            ratio_w = max_qr_w / qr_img.width if qr_img.width > max_qr_w else 1.0
            ratio_h = max_qr_h / qr_img.height if qr_img.height > max_qr_h else 1.0
            ratio = min(ratio_w, ratio_h)
            
            new_width = int(qr_img.width * ratio)
            new_height = int(qr_img.height * ratio)
            qr_img = qr_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            if current_y + qr_img.height > LABEL_HEIGHT_PX - BOTTOM_MARGIN_PX:
                espacio_real = LABEL_HEIGHT_PX - current_y - BOTTOM_MARGIN_PX
                ratio_ajuste = espacio_real / qr_img.height
                new_width = int(new_width * ratio_ajuste)
                new_height = int(new_height * ratio_ajuste)
                qr_img = qr_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            qr_x = (LABEL_WIDTH_PX - qr_img.width) // 2
            image.paste(qr_img, (qr_x, current_y))
            
        except Exception as e:
            print(f"Error generando código QR en previsualización: {e}")
            
    return image

# --- FUNCIÓN DE GENERACIÓN DE PDF (CÓDIGO QR) ---
def _generar_etiqueta_qr_pdf_temporal(modelo, imeis, path_logo_pil):
    if not PDF_SAVE_ENABLED: return None
    fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="etiqueta_qr_")
    os.close(fd)
    temporary_files_to_delete.append(temp_pdf_path)
    
    c = reportlab_canvas.Canvas(temp_pdf_path, pagesize=(LABEL_WIDTH_INCHES * inch, LABEL_HEIGHT_INCHES * inch))
    width, height = LABEL_WIDTH_INCHES * inch, LABEL_HEIGHT_INCHES * inch
    
    margin_top = 0.20 * inch
    margin_sides = 0.15 * inch
    margin_bottom = 0.25 * inch
    
    current_y = height - margin_top

    # 1. Dibujar Logo
    try:
        if path_logo_pil and os.path.exists(path_logo_pil):
            logo_pil = Image.open(path_logo_pil)
            logo_max_width_pt = width - 2 * margin_sides
            logo_max_height_pt = 0.28 * height
            w_px, h_px = logo_pil.size
            aspect = h_px / float(w_px) if w_px > 0 else 0
            logo_w_pt = logo_max_width_pt
            logo_h_pt = logo_w_pt * aspect
            if logo_h_pt > logo_max_height_pt:
                logo_h_pt = logo_max_height_pt
                logo_w_pt = logo_h_pt / aspect if aspect > 0 else 0

            img_reader = ReportLabImageReader(logo_pil)
            
            current_y -= logo_h_pt
            c.drawImage(img_reader, (width - logo_w_pt) / 2, current_y, width=logo_w_pt, height=logo_h_pt, mask='auto')
            current_y -= 0.15 * inch
    except Exception as e:
        print(f"Error al procesar logo para PDF: {e}")

    # 2. Dibujar Texto - Modelo con cantidad de equipos
    imeis_validos = [imei.strip() for imei in imeis if imei.strip()]
    cantidad_equipos = len(imeis_validos)
    
    if modelo.strip():
        texto_modelo = f"Modelo: {modelo} - QTY {cantidad_equipos}"
        
        ancho_disponible = width - (2 * margin_sides)
        
        font_size = 12
        c.setFont(RL_FONT_BOLD_NAME, font_size)
        texto_largo = c.stringWidth(texto_modelo, RL_FONT_BOLD_NAME, font_size)
        
        if texto_largo > ancho_disponible:
            for size in [11, 10, 9, 8]:
                texto_largo = c.stringWidth(texto_modelo, RL_FONT_BOLD_NAME, size)
                if texto_largo <= ancho_disponible:
                    font_size = size
                    break
        
        current_y -= 0.1 * inch
        current_y -= font_size
        
        c.setFont(RL_FONT_BOLD_NAME, font_size)
        c.drawCentredString(width / 2, current_y, texto_modelo)
        current_y -= 0.05 * inch

    # 3. Dibujar Código QR
    if imeis_validos:
        try:
            current_y -= 0.05 * inch
            
            espacio_disponible_y = current_y - margin_bottom
            
            texto_qr = generar_texto_qr(imeis_validos)
            
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=4,
            )
            
            qr.add_data(texto_qr)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert('RGB')
            
            qr_io = io.BytesIO()
            qr_img.save(qr_io, format='PNG')
            qr_io.seek(0)
            
            img_reader = ReportLabImageReader(qr_io)
            qr_w, qr_h = img_reader.getSize()
            
            max_qr_w = width - (2 * margin_sides)
            max_qr_h_pt = espacio_disponible_y - (0.05 * inch)
            
            ratio_w = max_qr_w / qr_w if qr_w > max_qr_w else 1.0
            ratio_h = max_qr_h_pt / qr_h if qr_h > max_qr_h_pt else 1.0
            ratio = min(ratio_w, ratio_h)
            
            qr_w, qr_h = qr_w * ratio, qr_h * ratio
            
            if current_y - qr_h < margin_bottom:
                espacio_real = current_y - margin_bottom
                ratio_ajuste = espacio_real / qr_h
                qr_w, qr_h = qr_w * ratio_ajuste, qr_h * ratio_ajuste
            
            current_y -= qr_h
            c.drawImage(img_reader, (width - qr_w) / 2, current_y, width=qr_w, height=qr_h, mask='auto')

        except Exception as e:
            print(f"Error generando código QR para PDF: {e}")
            
    c.save()
    return temp_pdf_path

# --- Funciones Auxiliares para Actualización ---
def limpiar_archivos_antiguos():
    """Elimina el archivo ejecutable antiguo (.old) si existe."""
    if getattr(sys, 'frozen', False):
        try:
            current_exe = sys.executable
            old_exe = current_exe + ".old"
            if os.path.exists(old_exe):
                os.remove(old_exe)
                print("Archivo ejecutable antiguo (.old) eliminado con éxito.")
        except Exception as e:
            print(f"Error al eliminar archivo antiguo: {e}")

def parse_version(v_str):
    cleaned = "".join(c for c in v_str if c.isdigit() or c == '.')
    parts = cleaned.split('.')
    res = []
    for p in parts:
        try:
            res.append(int(p))
        except ValueError:
            res.append(0)
    while len(res) < 3:
        res.append(0)
    return tuple(res[:3])

class VentanaActualizacionDisponible(customtkinter.CTkToplevel):
    def __init__(self, parent, nueva_version, changelog, exe_url, exe_name, html_url):
        super().__init__(parent)
        self.parent = parent
        self.nueva_version = nueva_version
        self.exe_url = exe_url
        self.exe_name = exe_name
        self.html_url = html_url
        
        self.title("Actualización Disponible")
        self.geometry("520x450")
        self.resizable(False, False)
        self.configure(fg_color="#0F172A")
        
        # Make transient and grab focus
        self.transient(parent)
        self.grab_set()
        
        # Center window relative to parent
        self.update_idletasks()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        x = p_x + (p_w - 520) // 2
        y = p_y + (p_h - 450) // 2
        self.geometry(f"520x450+{x}+{y}")
        
        # Layout
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Icon/Header
        header_label = customtkinter.CTkLabel(
            self, 
            text="✨ ¡Nueva actualización disponible! ✨", 
            font=customtkinter.CTkFont(family="Inter", size=18, weight="bold"),
            text_color="#06B6D4"
        )
        header_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")
        
        version_label = customtkinter.CTkLabel(
            self, 
            text=f"Versión actual: v{VERSION}  ➡  Nueva versión: {nueva_version}", 
            font=customtkinter.CTkFont(family="Inter", size=12, weight="bold"),
            text_color="#94A3B8"
        )
        version_label.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        
        # Changelog frame & text
        changelog_frame = customtkinter.CTkFrame(self, fg_color="#1E293B", border_width=1, border_color="#334155", corner_radius=12)
        changelog_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        changelog_frame.grid_rowconfigure(1, weight=1)
        changelog_frame.grid_columnconfigure(0, weight=1)
        
        customtkinter.CTkLabel(
            changelog_frame, 
            text="¿Qué hay de nuevo?", 
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            text_color="#64748B"
        ).grid(row=0, column=0, padx=15, pady=(8, 2), sticky="w")
        
        self.textbox = customtkinter.CTkTextbox(
            changelog_frame, 
            font=customtkinter.CTkFont(size=11), 
            fg_color="#0F172A", 
            text_color="#F8FAFC", 
            border_width=0, 
            corner_radius=8
        )
        self.textbox.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        
        # Clean up changelog body formatting
        clean_changelog = changelog.strip() if changelog else "No se proporcionaron detalles sobre esta versión."
        self.textbox.insert("1.0", clean_changelog)
        self.textbox.configure(state="disabled")
        
        # Buttons
        buttons_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        buttons_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        buttons_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.cancel_btn = customtkinter.CTkButton(
            buttons_frame, 
            text="Cancelar", 
            fg_color="#334155", 
            hover_color="#475569", 
            text_color="#F8FAFC", 
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), 
            height=40, 
            corner_radius=10, 
            command=self.destroy
        )
        self.cancel_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        
        action_text = "Instalar ahora" if (getattr(sys, 'frozen', False) and exe_url) else "Ver en GitHub"
        self.update_btn = customtkinter.CTkButton(
            buttons_frame, 
            text=action_text, 
            fg_color="#6366F1", 
            hover_color="#4F46E5", 
            text_color="#FFFFFF", 
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), 
            height=40, 
            corner_radius=10, 
            command=self.proceder_actualizacion
        )
        self.update_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        
    def proceder_actualizacion(self):
        self.destroy()
        if getattr(sys, 'frozen', False) and self.exe_url:
            self.parent.iniciar_descarga_actualizacion(self.exe_url, self.exe_name, self.nueva_version)
        else:
            webbrowser.open(self.html_url)

class VentanaProgresoActualizacion(customtkinter.CTkToplevel):
    def __init__(self, parent, version_nueva):
        super().__init__(parent)
        self.title("Actualizando McTools")
        self.geometry("400x150")
        self.resizable(False, False)
        
        # Centrar la ventana de progreso respecto al padre
        self.transient(parent)
        
        # En Windows, grab_set asegura el comportamiento modal
        self.grab_set()
        self.focus_set()
        
        self.grid_columnconfigure(0, weight=1)
        
        self.label = customtkinter.CTkLabel(
            self, 
            text=f"Descargando versión {version_nueva}...", 
            font=customtkinter.CTkFont(size=14, weight="bold")
        )
        self.label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.progress_bar = customtkinter.CTkProgressBar(self, width=320)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=10)
        self.progress_bar.set(0)
        
        self.status_label = customtkinter.CTkLabel(self, text="Conectando con GitHub...", text_color="gray")
        self.status_label.grid(row=2, column=0, padx=20, pady=(0, 20))
        
    def actualizar_progreso(self, valor, texto_status):
        self.progress_bar.set(valor)
        self.status_label.configure(text=texto_status)

# --- Clase Principal de la Aplicación ---
class AppGeneradorEtiquetas(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.preview_ctk_image = None
        self._preview_update_job = None
        self.cached_logo_pil = None
        
        # Configuración Inicial
        self.title(f"McTools v{VERSION}")
        if os.path.exists("logo.ico"):
            try:
                self.iconbitmap("logo.ico")
            except Exception:
                pass
        self.geometry("920x720")  # Aumentado para acomodar el cuadro de texto
        self.minsize(920, 720)
        self.configure(fg_color="#0F172A")  # Slate-900 Main Window
        
        limpiar_archivos_antiguos()
        cargar_config_inicial()
        cargar_fuentes_pdf()
        
        # Configurar Grid Layout (2x1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Crear Frames
        self.controls_frame = customtkinter.CTkFrame(self, width=340, corner_radius=0, fg_color="#1E293B", border_width=1, border_color="#334155")
        self.controls_frame.grid(row=0, column=0, sticky="nsw")
        self.controls_frame.grid_rowconfigure(2, weight=1)  # Expand tabview area

        self.preview_frame = customtkinter.CTkFrame(self, fg_color="#1E293B", corner_radius=16, border_width=1, border_color="#334155")
        self.preview_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")

        self._setup_ui()
        self.cargar_y_cachear_logo()
        self._bind_events()
        self.after(100, self.force_preview_update)
        self.after(2000, self.chequear_actualizaciones_async)

    def _setup_ui(self):
        # Frame de Controles (Izquierda)
        self.controls_frame.grid_columnconfigure(0, weight=1)
        
        # Variables Compartidas
        self.modelo_var = tk.StringVar()
        logo_path_inicial = cargar_logo_config()
        self.logo_path_var = tk.StringVar(value=logo_path_inicial)
        
        # Variables específicas de Pestaña Barcode
        self.imei_var = tk.StringVar()

        # 1. Banner de Encabezado (Logo & Versión)
        header_frame = customtkinter.CTkFrame(self.controls_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        
        title_container = customtkinter.CTkFrame(header_frame, fg_color="transparent")
        title_container.grid(row=0, column=0, sticky="w")
        
        title_label = customtkinter.CTkLabel(
            title_container, 
            text="McTools", 
            font=customtkinter.CTkFont(family="Inter", size=24, weight="bold"),
            text_color="#06B6D4"  # Cyan Accent
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        version_badge = customtkinter.CTkLabel(
            title_container, 
            text=f"v{VERSION}", 
            font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
            text_color="#94A3B8",
            fg_color="#334155",
            corner_radius=6,
            height=18,
            width=40
        )
        version_badge.grid(row=0, column=1, padx=(8, 0), sticky="w")
        
        subtitle_label = customtkinter.CTkLabel(
            header_frame, 
            text="Herramientas de IMEI y Etiquetas", 
            font=customtkinter.CTkFont(family="Inter", size=12),
            text_color="#94A3B8"
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # 2. Pestañas (Tabview)
        self.tabview = customtkinter.CTkTabview(
            self.controls_frame, 
            fg_color="transparent",
            segmented_button_fg_color="#0F172A",
            segmented_button_selected_color="#06B6D4",
            segmented_button_selected_hover_color="#0891B2",
            segmented_button_unselected_color="#1E293B",
            segmented_button_unselected_hover_color="#334155",
            text_color="#F8FAFC",
            corner_radius=12
        )
        self.tabview.grid(row=1, column=0, padx=15, pady=(5, 5), sticky="nsew")
        self.tabview.grid_rowconfigure(0, weight=1)
        self.tabview.grid_columnconfigure(0, weight=1)
        
        self.tab_barcode = self.tabview.add("Código de Barras")
        self.tab_qr = self.tabview.add("Código QR")
        self.tab_procesador = self.tabview.add("Procesador")
        
        # Configure columns inside tabs
        self.tab_barcode.grid_columnconfigure(0, weight=1)
        self.tab_qr.grid_columnconfigure(0, weight=1)
        self.tab_procesador.grid_columnconfigure(0, weight=1)

        # ---------------- PESTAÑA CÓDIGO DE BARRAS ----------------
        inputs_barcode = customtkinter.CTkFrame(self.tab_barcode, fg_color="transparent")
        inputs_barcode.grid(row=0, column=0, sticky="ew")
        inputs_barcode.grid_columnconfigure(0, weight=1)

        # Tarjeta Modelo (Compartida)
        modelo_card_bc = customtkinter.CTkFrame(inputs_barcode, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        modelo_card_bc.grid(row=0, column=0, padx=5, pady=(5, 12), sticky="ew")
        modelo_card_bc.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(modelo_card_bc, text="Modelo", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        modelo_entry_frame_bc = customtkinter.CTkFrame(modelo_card_bc, fg_color="transparent")
        modelo_entry_frame_bc.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        modelo_entry_frame_bc.grid_columnconfigure(0, weight=1)
        self.modelo_entry_bc = customtkinter.CTkEntry(modelo_entry_frame_bc, textvariable=self.modelo_var, placeholder_text="Ej. iPhone 15 Pro Max", fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", placeholder_text_color="#64748B", height=32, corner_radius=8)
        self.modelo_entry_bc.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(modelo_entry_frame_bc, text="Pegar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.pegar_modelo).grid(row=0, column=1, padx=0)

        # Tarjeta IMEI (Específica Barcode)
        imei_card = customtkinter.CTkFrame(inputs_barcode, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        imei_card.grid(row=1, column=0, padx=5, pady=(0, 12), sticky="ew")
        imei_card.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(imei_card, text="IMEI", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        imei_entry_frame = customtkinter.CTkFrame(imei_card, fg_color="transparent")
        imei_entry_frame.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        imei_entry_frame.grid_columnconfigure(0, weight=1)
        self.imei_entry = customtkinter.CTkEntry(imei_entry_frame, textvariable=self.imei_var, placeholder_text="Ej. 350123456789012", fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", placeholder_text_color="#64748B", height=32, corner_radius=8)
        self.imei_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(imei_entry_frame, text="Pegar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.pegar_imei).grid(row=0, column=1, padx=0)

        # Tarjeta Logo (Compartida)
        logo_card_bc = customtkinter.CTkFrame(inputs_barcode, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        logo_card_bc.grid(row=2, column=0, padx=5, pady=(0, 15), sticky="ew")
        logo_card_bc.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(logo_card_bc, text="Ruta del Logo", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        logo_entry_frame_bc = customtkinter.CTkFrame(logo_card_bc, fg_color="transparent")
        logo_entry_frame_bc.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        logo_entry_frame_bc.grid_columnconfigure(0, weight=1)
        self.logo_entry_bc = customtkinter.CTkEntry(logo_entry_frame_bc, textvariable=self.logo_path_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.logo_entry_bc.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(logo_entry_frame_bc, text="Buscar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.buscar_logo).grid(row=0, column=1, padx=0)

        # Acciones Barcode
        actions_bc = customtkinter.CTkFrame(self.tab_barcode, fg_color="transparent")
        actions_bc.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        actions_bc.grid_columnconfigure((0, 1), weight=1)
        customtkinter.CTkButton(actions_bc, text="Guardar PDF", fg_color="#6366F1", hover_color="#4F46E5", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.generar_y_guardar_pdf).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        customtkinter.CTkButton(actions_bc, text="Imprimir", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.imprimir).grid(row=0, column=1, padx=(6, 0), sticky="ew")


        # ---------------- PESTAÑA CÓDIGO QR ----------------
        inputs_qr = customtkinter.CTkFrame(self.tab_qr, fg_color="transparent")
        inputs_qr.grid(row=0, column=0, sticky="ew")
        inputs_qr.grid_columnconfigure(0, weight=1)

        # Tarjeta Modelo (Compartida)
        modelo_card_qr = customtkinter.CTkFrame(inputs_qr, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        modelo_card_qr.grid(row=0, column=0, padx=5, pady=(5, 12), sticky="ew")
        modelo_card_qr.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(modelo_card_qr, text="Modelo", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        modelo_entry_frame_qr = customtkinter.CTkFrame(modelo_card_qr, fg_color="transparent")
        modelo_entry_frame_qr.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        modelo_entry_frame_qr.grid_columnconfigure(0, weight=1)
        self.modelo_entry_qr = customtkinter.CTkEntry(modelo_entry_frame_qr, textvariable=self.modelo_var, placeholder_text="Ej. iPhone 15 Pro Max", fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", placeholder_text_color="#64748B", height=32, corner_radius=8)
        self.modelo_entry_qr.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(modelo_entry_frame_qr, text="Pegar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.pegar_modelo).grid(row=0, column=1, padx=0)

        # Tarjeta IMEIs (Específica QR - Caja de texto grande)
        imeis_card = customtkinter.CTkFrame(inputs_qr, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        imeis_card.grid(row=1, column=0, padx=5, pady=(0, 12), sticky="ew")
        imeis_card.grid_columnconfigure(0, weight=1)
        
        imeis_label_frame = customtkinter.CTkFrame(imeis_card, fg_color="transparent")
        imeis_label_frame.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="ew")
        imeis_label_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(imeis_label_frame, text="IMEIs (uno por línea)", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, sticky="w")
        self.imeis_count_label = customtkinter.CTkLabel(imeis_label_frame, text="0 IMEIs", font=customtkinter.CTkFont(family="Inter", size=10), text_color="#64748B")
        self.imeis_count_label.grid(row=0, column=1, sticky="e")
        
        self.imeis_textbox = customtkinter.CTkTextbox(imeis_card, height=140, font=customtkinter.CTkFont(size=11), fg_color="#1E293B", border_color="#475569", border_width=1, text_color="gray", corner_radius=8)
        self.imeis_textbox.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        self.placeholder_text = "Pegue aquí todos los IMEIs, uno por línea..."
        self.imeis_textbox.insert("1.0", self.placeholder_text)
        
        limpiar_frame = customtkinter.CTkFrame(imeis_card, fg_color="transparent")
        limpiar_frame.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
        limpiar_frame.grid_columnconfigure((0, 1), weight=1)
        customtkinter.CTkButton(limpiar_frame, text="Limpiar IMEIs", height=28, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), command=self.limpiar_imeis).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        customtkinter.CTkButton(limpiar_frame, text="Pegar IMEIs", height=28, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), command=self.pegar_imeis).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Tarjeta Logo (Compartida)
        logo_card_qr = customtkinter.CTkFrame(inputs_qr, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        logo_card_qr.grid(row=2, column=0, padx=5, pady=(0, 15), sticky="ew")
        logo_card_qr.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(logo_card_qr, text="Ruta del Logo", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        logo_entry_frame_qr = customtkinter.CTkFrame(logo_card_qr, fg_color="transparent")
        logo_entry_frame_qr.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        logo_entry_frame_qr.grid_columnconfigure(0, weight=1)
        self.logo_entry_qr = customtkinter.CTkEntry(logo_entry_frame_qr, textvariable=self.logo_path_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.logo_entry_qr.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(logo_entry_frame_qr, text="Buscar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.buscar_logo).grid(row=0, column=1, padx=0)

        # Acciones QR
        actions_qr = customtkinter.CTkFrame(self.tab_qr, fg_color="transparent")
        actions_qr.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        actions_qr.grid_columnconfigure((0, 1), weight=1)
        customtkinter.CTkButton(actions_qr, text="Guardar PDF", fg_color="#6366F1", hover_color="#4F46E5", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.generar_y_guardar_pdf).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        customtkinter.CTkButton(actions_qr, text="Imprimir", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.imprimir).grid(row=0, column=1, padx=(6, 0), sticky="ew")


        # ---------------- PESTAÑA PROCESADOR ----------------
        inputs_proc = customtkinter.CTkFrame(self.tab_procesador, fg_color="transparent")
        inputs_proc.grid(row=0, column=0, sticky="ew")
        inputs_proc.grid_columnconfigure(0, weight=1)

        # Tarjeta Caja de Texto (Entrada RAW)
        raw_card = customtkinter.CTkFrame(inputs_proc, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        raw_card.grid(row=0, column=0, padx=5, pady=(5, 12), sticky="ew")
        raw_card.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(raw_card, text="Pega aquí el texto con IMEIs:", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        
        self.proc_input_textbox = customtkinter.CTkTextbox(raw_card, height=180, font=customtkinter.CTkFont(size=11), fg_color="#1E293B", border_color="#475569", border_width=1, text_color="gray", corner_radius=8)
        self.proc_input_textbox.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        self.proc_placeholder_text = "Pega aquí el texto con IMEIs a extraer..."
        self.proc_input_textbox.insert("1.0", self.proc_placeholder_text)

        # Checkbox de Omitir Posiciones Pares
        self.proc_omit_alternate_var = tk.BooleanVar(value=False)
        self.proc_omit_checkbox = customtkinter.CTkCheckBox(
            inputs_proc,
            text="Omitir IMEIs en posiciones pares\n(procesar 1°, 3°, 5°...)",
            variable=self.proc_omit_alternate_var,
            font=customtkinter.CTkFont(family="Inter", size=11),
            text_color="#94A3B8",
            fg_color="#06B6D4",
            hover_color="#0891B2",
            border_color="#475569",
            command=self.proc_extraer_imeis
        )
        self.proc_omit_checkbox.grid(row=1, column=0, padx=10, pady=(0, 15), sticky="w")

        # Acciones Procesador (Izquierda)
        actions_proc = customtkinter.CTkFrame(self.tab_procesador, fg_color="transparent")
        actions_proc.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        actions_proc.grid_columnconfigure(0, weight=1)
        
        customtkinter.CTkButton(
            actions_proc,
            text="Extraer IMEIs Únicos",
            fg_color="#6366F1",
            hover_color="#4F46E5",
            text_color="#FFFFFF",
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"),
            height=40,
            corner_radius=10,
            command=self.proc_extraer_imeis
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        
        limpiar_importar_frame = customtkinter.CTkFrame(actions_proc, fg_color="transparent")
        limpiar_importar_frame.grid(row=1, column=0, sticky="ew")
        limpiar_importar_frame.grid_columnconfigure((0, 1), weight=1)
        
        customtkinter.CTkButton(
            limpiar_importar_frame,
            text="Limpiar Todo",
            fg_color="#334155",
            hover_color="#475569",
            text_color="#F8FAFC",
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            height=32,
            corner_radius=8,
            command=self.proc_limpiar_campos
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        
        customtkinter.CTkButton(
            limpiar_importar_frame,
            text="Importar TXT",
            fg_color="#334155",
            hover_color="#475569",
            text_color="#F8FAFC",
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            height=32,
            corner_radius=8,
            command=self.proc_importar_txt
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")


        # 3. Contenedor Inferior (Configuración & Autor)
        footer_container = customtkinter.CTkFrame(self.controls_frame, fg_color="transparent")
        footer_container.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="sew")
        footer_container.grid_columnconfigure(0, weight=1)
        
        # Botón Outline de SumatraPDF
        self.config_sumatra_btn = customtkinter.CTkButton(
            footer_container, 
            text="Configurar SumatraPDF", 
            fg_color="transparent",
            border_width=1,
            border_color="#475569",
            hover_color="#334155",
            text_color="#94A3B8",
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            height=32,
            corner_radius=8,
            command=self.configurar_ruta_sumatra_manualmente
        )
        self.config_sumatra_btn.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Créditos
        customtkinter.CTkLabel(
            footer_container, 
            text="Hecho por Micael", 
            font=customtkinter.CTkFont(family="Inter", size=10, slant="italic"), 
            text_color="#64748B"
        ).grid(row=1, column=0, sticky="w")

        # Frame de Vista Previa (Derecha)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        
        self.preview_image_label = customtkinter.CTkLabel(
            self.preview_frame, 
            text="Vista Previa de la Etiqueta\n\nIngresa el Modelo y datos para generar la previsualización.", 
            text_color="#94A3B8",
            font=customtkinter.CTkFont(family="Inter", size=13, weight="bold")
        )
        self.preview_image_label.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Frame de Salida del Procesador (Derecha) - Oculto al inicio
        self.procesador_output_frame = customtkinter.CTkFrame(self.preview_frame, fg_color="transparent")
        self.procesador_output_frame.grid_rowconfigure(1, weight=1)
        self.procesador_output_frame.grid_columnconfigure(0, weight=1)
        
        proc_header = customtkinter.CTkFrame(self.procesador_output_frame, fg_color="transparent")
        proc_header.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        proc_header.grid_columnconfigure(0, weight=1)
        
        customtkinter.CTkLabel(proc_header, text="IMEIs Únicos Extraídos", font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"), text_color="#06B6D4").grid(row=0, column=0, sticky="w")
        self.proc_count_label = customtkinter.CTkLabel(proc_header, text="0 IMEIs", font=customtkinter.CTkFont(family="Inter", size=12), text_color="#94A3B8")
        self.proc_count_label.grid(row=0, column=1, sticky="e")
        
        self.proc_output_textbox = customtkinter.CTkTextbox(self.procesador_output_frame, font=customtkinter.CTkFont(size=12), fg_color="#0F172A", border_color="#334155", border_width=1, text_color="#F8FAFC", corner_radius=12)
        self.proc_output_textbox.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")
        self.proc_output_textbox.configure(state="disabled")
        
        proc_actions = customtkinter.CTkFrame(self.procesador_output_frame, fg_color="transparent")
        proc_actions.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")
        proc_actions.grid_columnconfigure((0, 1), weight=1)
        
        self.proc_copy_btn = customtkinter.CTkButton(proc_actions, text="Copiar al Portapapeles", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.proc_copiar_portapapeles, state="disabled")
        self.proc_copy_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        
        self.proc_save_btn = customtkinter.CTkButton(proc_actions, text="Guardar como TXT", fg_color="#6366F1", hover_color="#4F46E5", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.proc_guardar_txt, state="disabled")
        self.proc_save_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        
        # Grid inicial para el procesador (oculto)
        self.procesador_output_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.procesador_output_frame.grid_remove()

    def _bind_events(self):
        # Eventos para actualizar la vista previa al escribir
        for var in [self.modelo_var, self.imei_var]:
            var.trace_add("write", self.schedule_preview_update)
            
        # Evento específico para recargar logo si cambia la ruta
        self.logo_path_var.trace_add("write", self.on_logo_path_change)
            
        # Binds para el cuadro de texto de IMEIs
        self.imeis_textbox.bind("<KeyRelease>", self.on_imeis_text_change)
        self.imeis_textbox.bind("<Button-1>", self.on_imeis_click)
        self.imeis_textbox.bind("<FocusIn>", self.on_imeis_focus_in)
        
        # Binds para el cuadro de texto del Procesador
        self.proc_input_textbox.bind("<KeyRelease>", self.on_proc_text_change)
        self.proc_input_textbox.bind("<Button-1>", self.on_proc_click)
        self.proc_input_textbox.bind("<FocusIn>", self.on_proc_focus_in)
        
        # Actualizar cuando cambie la pestaña activa
        self.tabview.configure(command=self.schedule_preview_update)

    def schedule_preview_update(self, *args):
        if self._preview_update_job: self.after_cancel(self._preview_update_job)
        self._preview_update_job = self.after(50, self.force_preview_update)

    def force_preview_update(self):
        try:
            tab_activa = self.tabview.get()
            
            if tab_activa == "Procesador":
                # Conmutar paneles: Ocultar previsualización y mostrar el procesador
                self.preview_image_label.grid_remove()
                self.procesador_output_frame.grid()
                return
            else:
                # Conmutar paneles: Ocultar procesador y mostrar previsualización
                self.procesador_output_frame.grid_remove()
                self.preview_image_label.grid()
            
            # Asegurarnos de que el logo esté cargado en caché
            if self.cached_logo_pil is None and self.logo_path_var.get().strip():
                self.cargar_y_cachear_logo()
            
            if tab_activa == "Código de Barras":
                pil_image = _generar_etiqueta_barcode_pil_image(
                    self.modelo_var.get().strip().upper(),
                    self.imei_var.get().strip().upper(),
                    "",
                    self.cached_logo_pil
                )
            else:  # Código QR
                imeis = self.obtener_imeis_del_texto()
                self.actualizar_contador_imeis()
                pil_image = _generar_etiqueta_qr_pil_image(
                    self.modelo_var.get().strip().upper(),
                    imeis,
                    self.cached_logo_pil
                )
                
            self.preview_ctk_image = customtkinter.CTkImage(
                light_image=pil_image,
                dark_image=pil_image,
                size=(PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT)
            )
            
            self.preview_image_label.configure(image=self.preview_ctk_image, text="")
        except Exception as e:
            self.preview_image_label.configure(image=None, text=f"Error en preview:\n{e}")

    def generar_y_guardar_pdf(self):
        tab_activa = self.tabview.get()
        if tab_activa == "Código de Barras":
            self._procesar_generacion_barcode(guardar_permanente=True)
        else:
            self._procesar_generacion_qr(guardar_permanente=True)

    def imprimir(self):
        tab_activa = self.tabview.get()
        if tab_activa == "Código de Barras":
            self._procesar_generacion_barcode(imprimir_despues=True)
        else:
            self._procesar_generacion_qr(imprimir_despues=True)

    def _procesar_generacion_barcode(self, guardar_permanente=False, imprimir_despues=False):
        if not PDF_SAVE_ENABLED:
            messagebox.showerror("Función Deshabilitada", "La librería 'ReportLab' es necesaria para esta función.")
            return
        modelo = self.modelo_var.get().strip().upper()
        imei = self.imei_var.get().strip().upper()
        if not modelo or not imei:
            messagebox.showerror("Campos Obligatorios", "'Modelo' e 'IMEI' son campos obligatorios.")
            return
        temp_pdf_path = _generar_etiqueta_barcode_pdf_temporal(
            modelo, imei,
            "",
            self.logo_path_var.get().strip()
        )
        if not temp_pdf_path or not os.path.exists(temp_pdf_path):
            messagebox.showerror("Error de Generación", "No se pudo crear el archivo PDF temporal.")
            return
        self._finalizar_generacion(temp_pdf_path, modelo, imei, guardar_permanente, imprimir_despues)

    def _procesar_generacion_qr(self, guardar_permanente=False, imprimir_despues=False):
        if not PDF_SAVE_ENABLED:
            messagebox.showerror("Función Deshabilitada", "La librería 'ReportLab' es necesaria para esta función.")
            return
        modelo = self.modelo_var.get().strip().upper()
        imeis = self.obtener_imeis_del_texto()
        imeis_validos = [imei for imei in imeis if imei.strip()]
        
        if not modelo:
            messagebox.showerror("Campo Obligatorio", "'Modelo' es un campo obligatorio.")
            return
        if not imeis_validos:
            messagebox.showerror("Campo Obligatorio", "Debe ingresar al menos un IMEI.")
            return
            
        temp_pdf_path = _generar_etiqueta_qr_pdf_temporal(
            modelo,
            imeis,
            self.logo_path_var.get().strip()
        )
        if not temp_pdf_path or not os.path.exists(temp_pdf_path):
            messagebox.showerror("Error de Generación", "No se pudo crear el archivo PDF temporal.")
            return
        self._finalizar_generacion(temp_pdf_path, modelo, "qr", guardar_permanente, imprimir_despues)

    def _finalizar_generacion(self, temp_pdf_path, modelo, identificador, guardar_permanente=False, imprimir_despues=False):
        if guardar_permanente:
            path_salida = filedialog.asksaveasfilename(
                title="Guardar Etiqueta PDF",
                defaultextension=".pdf",
                initialfile=f"etiqueta_{modelo}_{identificador}.pdf".replace(" ", "_"),
                filetypes=[("Archivos PDF", "*.pdf"), ("Todos", "*.*")]
            )
            if path_salida:
                try:
                    import shutil
                    shutil.move(temp_pdf_path, path_salida)
                    if temp_pdf_path in temporary_files_to_delete: 
                        temporary_files_to_delete.remove(temp_pdf_path)
                    messagebox.showinfo("Éxito", f"Etiqueta PDF guardada en:\n'{path_salida}'")
                except Exception as e: 
                    messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo:\n{e}")
        if imprimir_despues: self.imprimir_pdf_directo(temp_pdf_path)

    def imprimir_pdf_directo(self, filepath):
        if not os.path.exists(filepath):
            messagebox.showerror("Error de Impresión", f"El archivo a imprimir no fue encontrado: {filepath}")
            return
        current_os = platform.system()
        try:
            if current_os == "Windows":
                if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH):
                    subprocess.Popen([SUMATRA_PDF_PATH, "-print-to-default", "-silent", filepath])
                else: os.startfile(filepath, "print")
            elif current_os in ["Darwin", "Linux"]:
                cmd = "lpr" if current_os == "Darwin" else "lp"
                subprocess.run([cmd, filepath], check=True)
            else: messagebox.showwarning("Sistema No Soportado", f"La impresión directa no está configurada para {current_os}.")
        except FileNotFoundError: messagebox.showerror("Error de Comando", "Comando de impresión no encontrado (lpr o lp). Asegúrate de que esté instalado.")
        except Exception as e: messagebox.showerror("Error de Impresión", f"Ocurrió un error inesperado al imprimir:\n\n{e}")

    def pegar_modelo(self):
        """Pega el contenido del portapapeles en el campo de Modelo, limpiando el contenido anterior y eliminando colores."""
        try:
            contenido = self.clipboard_get()
            if contenido:
                # Lista de colores comunes de iPhone a eliminar (ordenados de más largo a más corto para evitar conflictos)
                colores_iphone = [
                    "Pro Blue Titanium", "pro blue titanium",
                    "Natural Titanium", "natural titanium",
                    "White Titanium", "white titanium",
                    "Black Titanium", "black titanium",
                    "Space Gray", "Space Grey", "space gray", "space grey",
                    "Space Black", "space black",
                    "Sierra Blue", "sierra blue",
                    "Deep Purple", "deep purple",
                    "Rose Gold", "rose gold",
                    "Product Red", "product red",
                    "Titanium", "titanium",
                    "Midnight", "midnight",
                    "Starlight", "starlight",
                    "Silver", "silver",
                    "White", "white",
                    "Gold", "gold",
                    "Graphite", "graphite",
                    "Blue", "blue",
                    "Purple", "purple",
                    "Red", "red",
                    "Yellow", "yellow",
                    "Green", "green",
                    "Pink", "pink"
                ]
                
                # Eliminar colores del contenido
                texto_limpio = contenido.strip()
                for color in colores_iphone:
                    # Eliminar el color y espacios extra alrededor
                    texto_limpio = texto_limpio.replace(color, "").strip()
                    # Eliminar espacios múltiples
                    while "  " in texto_limpio:
                        texto_limpio = texto_limpio.replace("  ", " ")
                
                self.modelo_var.set(texto_limpio)
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")

    def pegar_imei(self):
        """Pega el contenido del portapapeles en el campo de IMEI, limpiando el contenido anterior."""
        try:
            contenido = self.clipboard_get()
            if contenido:
                self.imei_var.set(contenido.strip())
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")

    def obtener_imeis_del_texto(self):
        """Extrae la lista de IMEIs del cuadro de texto, eliminando líneas vacías y el placeholder."""
        texto = self.imeis_textbox.get("1.0", tk.END).strip()
        if texto == self.placeholder_text:
            return []
        return [line.strip() for line in texto.split("\n") if line.strip()]

    def actualizar_contador_imeis(self):
        """Actualiza la etiqueta con la cantidad de IMEIs ingresados."""
        cantidad = len(self.obtener_imeis_del_texto())
        self.imeis_count_label.configure(text=f"{cantidad} IMEIs")

    def pegar_imeis(self):
        """Pega el contenido del portapapeles en el cuadro de texto de IMEIs."""
        try:
            contenido = self.clipboard_get().strip()
            if contenido:
                # Si está el placeholder, limpiarlo
                texto_actual = self.imeis_textbox.get("1.0", tk.END).strip()
                if texto_actual == self.placeholder_text:
                    self.imeis_textbox.delete("1.0", tk.END)
                    self.imeis_textbox.configure(text_color="#F8FAFC")
                
                # Insertar contenido
                self.imeis_textbox.insert(tk.END, contenido + "\n")
                self.actualizar_contador_imeis()
                self.schedule_preview_update()
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")

    def limpiar_imeis(self):
        """Limpia el cuadro de texto y restablece el placeholder."""
        self.imeis_textbox.delete("1.0", tk.END)
        self.imeis_textbox.insert("1.0", self.placeholder_text)
        self.imeis_textbox.configure(text_color="gray")
        self.actualizar_contador_imeis()
        self.schedule_preview_update()

    def on_imeis_click(self, event):
        """Limpia el placeholder si el usuario hace clic en el cuadro de texto."""
        texto_actual = self.imeis_textbox.get("1.0", tk.END).strip()
        if texto_actual == self.placeholder_text:
            self.imeis_textbox.delete("1.0", tk.END)
            self.imeis_textbox.configure(text_color="#F8FAFC")

    def on_imeis_focus_in(self, event):
        """Limpia el placeholder si el cuadro de texto recibe el foco."""
        texto_actual = self.imeis_textbox.get("1.0", tk.END).strip()
        if texto_actual == self.placeholder_text:
            self.imeis_textbox.delete("1.0", tk.END)
            self.imeis_textbox.configure(text_color="#F8FAFC")

    def on_imeis_text_change(self, event):
        """Se activa al cambiar el texto de los IMEIs."""
        self.actualizar_contador_imeis()
        self.schedule_preview_update()

    # ---------------- MÉTODOS DEL PROCESADOR DE IMEIS ----------------
    def proc_extraer_imeis(self):
        """Extrae IMEIs de 15 dígitos únicos, aplicando filtro de posiciones pares si es requerido."""
        texto_crudo = self.proc_input_textbox.get("1.0", tk.END).strip()
        if not texto_crudo or texto_crudo == self.proc_placeholder_text:
            self.proc_output_textbox.configure(state="normal")
            self.proc_output_textbox.delete("1.0", tk.END)
            self.proc_output_textbox.configure(state="disabled")
            self.proc_count_label.configure(text="0 IMEIs")
            self.proc_copy_btn.configure(state="disabled")
            self.proc_save_btn.configure(state="disabled")
            return

        # Encontrar todos los IMEIs de 15 dígitos con expresión regular
        imei_pattern = r'\b\d{15}\b'
        todos_los_imeis = re.findall(imei_pattern, texto_crudo)

        # Aplicar filtro de posiciones pares (omitir impares en base 1-indexada, es decir indices 1, 3, 5 en 0-indexada)
        imeis_filtrados = []
        if self.proc_omit_alternate_var.get():
            for i, imei in enumerate(todos_los_imeis):
                if i % 2 == 0:  # Posiciones impares base 1-indexada (1, 3, 5...)
                    imeis_filtrados.append(imei)
        else:
            imeis_filtrados = todos_los_imeis

        # Eliminar duplicados manteniendo el orden
        imeis_unicos = []
        vistos = set()
        for imei in imeis_filtrados:
            if imei not in vistos:
                imeis_unicos.append(imei)
                vistos.add(imei)

        # Escribir el resultado en la caja de salida
        self.proc_output_textbox.configure(state="normal")
        self.proc_output_textbox.delete("1.0", tk.END)
        
        if imeis_unicos:
            self.proc_output_textbox.insert("1.0", "\n".join(imeis_unicos))
            self.proc_count_label.configure(text=f"{len(imeis_unicos)} IMEIs")
            self.proc_copy_btn.configure(state="normal")
            self.proc_save_btn.configure(state="normal")
        else:
            self.proc_output_textbox.insert("1.0", "No se encontraron IMEIs válidos.")
            self.proc_count_label.configure(text="0 IMEIs")
            self.proc_copy_btn.configure(state="disabled")
            self.proc_save_btn.configure(state="disabled")

        self.proc_output_textbox.configure(state="disabled")

    def proc_limpiar_campos(self):
        """Limpia la entrada, salida y el contador del procesador."""
        self.proc_input_textbox.delete("1.0", tk.END)
        self.proc_input_textbox.insert("1.0", self.proc_placeholder_text)
        self.proc_input_textbox.configure(text_color="gray")
        
        self.proc_output_textbox.configure(state="normal")
        self.proc_output_textbox.delete("1.0", tk.END)
        self.proc_output_textbox.configure(state="disabled")
        
        self.proc_count_label.configure(text="0 IMEIs")
        self.proc_copy_btn.configure(state="disabled")
        self.proc_save_btn.configure(state="disabled")
        self.proc_input_textbox.focus_set()

    def proc_importar_txt(self):
        """Abre un archivo de texto e importa su contenido en el procesador."""
        try:
            default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(default_dir): 
                default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(default_dir): 
                default_dir = os.getcwd()

            filepath = filedialog.askopenfilename(
                initialdir=default_dir,
                title="Importar IMEIs desde archivo TXT",
                filetypes=(("Archivos de Texto", "*.txt"), ("Todos los archivos", "*.*")),
                parent=self
            )
            if filepath:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                self.proc_input_textbox.delete("1.0", tk.END)
                self.proc_input_textbox.insert("1.0", content)
                self.proc_input_textbox.configure(text_color="#F8FAFC")
                
                # Procesar automáticamente al importar
                self.proc_extraer_imeis()
        except Exception as e:
            messagebox.showerror("Error al Importar", f"No se pudo leer el archivo.\nError: {e}", parent=self)

    def proc_copiar_portapapeles(self):
        """Copia la salida del procesador de IMEIs al portapapeles."""
        texto_salida = self.proc_output_textbox.get("1.0", tk.END).strip()
        if texto_salida and "No se encontraron IMEIs válidos." not in texto_salida:
            try:
                self.clipboard_clear()
                self.clipboard_append(texto_salida)
                messagebox.showinfo("Copiado", "¡IMEIs únicos copiados al portapapeles con éxito!", parent=self)
            except Exception as e:
                messagebox.showerror("Error al Copiar", f"No se pudo copiar al portapapeles:\n{e}", parent=self)

    def proc_guardar_txt(self):
        """Exporta los IMEIs limpios a un archivo de texto .txt."""
        texto_salida = self.proc_output_textbox.get("1.0", tk.END).strip()
        if not texto_salida or "No se encontraron IMEIs válidos." in texto_salida:
            return

        try:
            default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(default_dir): 
                default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(default_dir): 
                default_dir = os.getcwd()

            filepath = filedialog.asksaveasfilename(
                initialdir=default_dir,
                title="Guardar IMEIs como archivo TXT",
                defaultextension=".txt",
                filetypes=(("Archivos de Texto", "*.txt"), ("Todos los archivos", "*.*")),
                initialfile="imeis_unicos_extraidos.txt",
                parent=self
            )
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(texto_salida)
                messagebox.showinfo("Guardado", f"Archivo de texto guardado con éxito en:\n'{filepath}'", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo.\nError: {e}", parent=self)

    def on_proc_text_change(self, event):
        """Se ejecuta cuando cambia el texto de entrada en el procesador."""
        # Si tiene texto válido, cambiar color del texto
        texto_actual = self.proc_input_textbox.get("1.0", tk.END).strip()
        if texto_actual and texto_actual != self.proc_placeholder_text:
            self.proc_input_textbox.configure(text_color="#F8FAFC")
        
        # Procesamiento dinámico desactivado por defecto (se activa con botón o cambio de checkbox),
        # pero podemos actualizar el estado de los botones si el usuario borra todo.
        if not texto_actual:
            self.proc_copy_btn.configure(state="disabled")
            self.proc_save_btn.configure(state="disabled")

    def on_proc_click(self, event):
        """Limpia el placeholder si el usuario hace clic."""
        texto_actual = self.proc_input_textbox.get("1.0", tk.END).strip()
        if texto_actual == self.proc_placeholder_text:
            self.proc_input_textbox.delete("1.0", tk.END)
            self.proc_input_textbox.configure(text_color="#F8FAFC")

    def on_proc_focus_in(self, event):
        """Limpia el placeholder al recibir el foco."""
        texto_actual = self.proc_input_textbox.get("1.0", tk.END).strip()
        if texto_actual == self.proc_placeholder_text:
            self.proc_input_textbox.delete("1.0", tk.END)
            self.proc_input_textbox.configure(text_color="#F8FAFC")

    def cargar_y_cachear_logo(self):
        """Carga y procesa el logo de forma que esté listo para el renderizado instantáneo en memoria."""
        path = self.logo_path_var.get().strip()
        if path and os.path.exists(path):
            try:
                # Abrir y convertir a RGBA en memoria
                with Image.open(path) as img:
                    self.cached_logo_pil = img.convert("RGBA")
            except Exception as e:
                print(f"Error al cachear logo: {e}")
                self.cached_logo_pil = None
        else:
            self.cached_logo_pil = None

    def on_logo_path_change(self, *args):
        """Recarga el logo en caché y actualiza la previsualización."""
        self.cargar_y_cachear_logo()
        self.schedule_preview_update()

    def buscar_logo(self):
        filepath = filedialog.askopenfilename(title="Seleccionar archivo de logo", filetypes=[("Archivos de Imagen", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*")])
        if filepath:
            self.logo_path_var.set(filepath)
            guardar_logo_config(filepath)  # Guardar la ruta del logo seleccionado

    def configurar_ruta_sumatra_manualmente(self):
        global SUMATRA_PDF_PATH
        if platform.system() != "Windows":
            messagebox.showinfo("Información", "Esta opción de configuración es solo para el sistema operativo Windows.")
            return
        filepath = filedialog.askopenfilename(title="Localizar el ejecutable SumatraPDF.exe", filetypes=[("Ejecutable", "SumatraPDF.exe")])
        if filepath and os.path.basename(filepath).lower() == 'sumatrapdf.exe':
            SUMATRA_PDF_PATH = filepath
            guardar_config_sumatra()
            messagebox.showinfo("Éxito", f"La ruta de SumatraPDF ha sido establecida a:\n{filepath}")
        elif filepath: messagebox.showerror("Archivo Incorrecto", "Por favor, selecciona el archivo 'SumatraPDF.exe'.")

    def chequear_actualizaciones_async(self):
        """Inicia el hilo para buscar actualizaciones."""
        thread = threading.Thread(target=self._hilo_chequeo_actualizaciones)
        thread.daemon = True
        thread.start()

    def _hilo_chequeo_actualizaciones(self):
        try:
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            latest_version_tag = data.get("tag_name", "")
            latest_version = latest_version_tag.lstrip('v')
            # Si el tag no tiene digitos (ej. "EtiquetaPro"), intentar usar el titulo del release
            if not any(c.isdigit() for c in latest_version):
                release_title = data.get("name", "")
                if release_title:
                    latest_version_tag = release_title
                    latest_version = release_title.lstrip('v')
            current_ver = VERSION.lstrip('v')
            
            if parse_version(latest_version) > parse_version(current_ver):
                assets = data.get("assets", [])
                exe_url = None
                exe_name = None
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".exe"):
                        exe_url = asset.get("browser_download_url")
                        exe_name = name
                        break
                
                html_url = data.get("html_url", f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases")
                changelog_text = data.get("body", "")
                
                # Programar en el hilo principal de Tkinter
                self.after(100, lambda: self.mostrar_dialogo_actualizacion(latest_version_tag, changelog_text, exe_url, exe_name, html_url))
        except Exception as e:
            print(f"Error al buscar actualizaciones en GitHub: {e}")

    def mostrar_dialogo_actualizacion(self, nueva_version, changelog, exe_url, exe_name, html_url):
        """Muestra el diálogo informando de la nueva versión con notas del release."""
        VentanaActualizacionDisponible(self, nueva_version, changelog, exe_url, exe_name, html_url)

    def iniciar_descarga_actualizacion(self, exe_url, exe_name, nueva_version):
        """Crea la ventana de progreso e inicia la descarga."""
        ventana_progreso = VentanaProgresoActualizacion(self, nueva_version)
        
        thread = threading.Thread(
            target=self._hilo_descarga_reemplazo,
            args=(exe_url, exe_name, ventana_progreso)
        )
        thread.daemon = True
        thread.start()

    def _hilo_descarga_reemplazo(self, exe_url, exe_name, ventana_progreso):
        try:
            current_exe = sys.executable
            exe_dir = os.path.dirname(current_exe)
            new_exe = os.path.join(exe_dir, f"{exe_name}.new")
            
            req = urllib.request.Request(
                exe_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_downloaded = 0
                
                with open(new_exe, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        if total_size > 0:
                            progreso = bytes_downloaded / total_size
                            porcentaje = int(progreso * 100)
                            descargado_mb = bytes_downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            texto_status = f"Descargado {descargado_mb:.2f} MB de {total_mb:.2f} MB ({porcentaje}%)"
                            
                            # Actualizar UI
                            self.after(0, lambda val=progreso, txt=texto_status: ventana_progreso.actualizar_progreso(val, txt))
            
            # Completado, proceder a reemplazo
            self.after(0, lambda: ventana_progreso.actualizar_progreso(1.0, "Instalando actualización..."))
            
            # 1. Renombrar actual a .old
            old_exe = current_exe + ".old"
            if os.path.exists(old_exe):
                try:
                    os.remove(old_exe)
                except Exception:
                    pass
            
            os.rename(current_exe, old_exe)
            # 2. Renombrar new a actual
            os.rename(new_exe, current_exe)
            
            # 3. Lanzar nueva versión
            subprocess.Popen([current_exe])
            
            # 4. Cerrar la app actual
            os._exit(0)
            
        except Exception as e:
            # En caso de error, intentar borrar .new y mostrar error
            try:
                if 'new_exe' in locals() and os.path.exists(new_exe):
                    os.remove(new_exe)
            except Exception:
                pass
                
            self.after(0, lambda err=e: self._mostrar_error_actualizacion(err, ventana_progreso))

    def _mostrar_error_actualizacion(self, error, ventana_progreso):
        try:
            ventana_progreso.destroy()
        except Exception:
            pass
        messagebox.showerror(
            "Error de Actualización",
            f"Ocurrió un error al descargar o instalar la actualización:\n\n{error}"
        )


if __name__ == "__main__":
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("blue")
    
    app = AppGeneradorEtiquetas()
    app.mainloop()
