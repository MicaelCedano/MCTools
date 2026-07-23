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
from PIL import Image, ImageDraw, ImageFont
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None
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
import urllib.parse
import re
import threading
import sys
import time
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

def pil_to_tk_image_safe(pil_img, size=None):
    """
    Convierte una imagen PIL a un objeto de imagen compatible con CustomTkinter/Tkinter.
    Prueba activamente la disponibilidad de PIL._imagingtk. Si no está disponible o falla
    en el ejecutable congelado, realiza un fallback transparente e infalible a tk.PhotoImage
    usando bytes PNG o PPM en memoria (Tcl/Tk nativo sin necesidad de _imagingtk).
    """
    if pil_img is None:
        return None
    if size:
        img_resized = pil_img.resize(size, Image.Resampling.LANCZOS)
    else:
        img_resized = pil_img

    # 1. Probar si PIL._imagingtk / PIL.ImageTk funciona en este ejecutable
    has_imagingtk = False
    try:
        from PIL import _imagingtk, ImageTk
        test_img = Image.new("RGB", (1, 1))
        _ = ImageTk.PhotoImage(test_img)
        has_imagingtk = True
    except Exception as e:
        print(f"Aviso: PIL._imagingtk no funcional ({e}), usando fallback PNG nativo...")
        has_imagingtk = False

    if has_imagingtk:
        try:
            return customtkinter.CTkImage(light_image=img_resized, dark_image=img_resized, size=img_resized.size)
        except Exception as e:
            print(f"Aviso: CTkImage falló ({e}), usando fallback nativo PNG/PPM...")

    # 2. Fallback PNG con tk.PhotoImage (Tcl/Tk 8.6+ nativo sin necesidad de _imagingtk)
    try:
        buf = io.BytesIO()
        img_resized.save(buf, format="PNG")
        buf.seek(0)
        return tk.PhotoImage(data=buf.getvalue())
    except Exception as e2:
        print(f"Aviso: Fallback PNG falló ({e2}), usando fallback PPM...")

    # 3. Fallback PPM (Soporte universal Tcl/Tk)
    try:
        buf = io.BytesIO()
        img_resized.convert("RGB").save(buf, format="PPM")
        buf.seek(0)
        return tk.PhotoImage(data=buf.getvalue())
    except Exception as e3:
        raise e3

def obtener_ruta_recurso(rel_path):
    """Obtiene la ruta absoluta a un recurso, compatible con entorno dev y PyInstaller."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        mei_path = os.path.join(sys._MEIPASS, rel_path)
        if os.path.exists(mei_path):
            return mei_path
    if os.path.exists(rel_path):
        return os.path.abspath(rel_path)
    base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_dir, rel_path)
    if os.path.exists(app_path):
        return app_path
    return rel_path

# --- Constantes ---
VERSION = "3.5.2"
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

def obtener_lista_impresoras():
    """Enumera las impresoras instaladas en el sistema operativo Windows."""
    if platform.system() == "Windows":
        try:
            import win32print
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            return [p[2] for p in printers]
        except Exception:
            return []
    return []

def obtener_impresora_predeterminada():
    """Obtiene el nombre de la impresora predeterminada de Windows."""
    if platform.system() == "Windows":
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return ""
    return ""

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

# --- Funciones de Configuración y Limpieza ---

DEFAULT_MODELOS = []

# Conjunto de modelos de ejemplo antiguos para limpiar de la configuración local si existieran
PREPOPULATED_DEFAULTS = {
    "iphone 16 pro max", "iphone 16 pro", "iphone 16 plus", "iphone 16",
    "iphone 15 pro max", "iphone 15 pro", "iphone 15 plus", "iphone 15",
    "iphone 14 pro max", "iphone 14 pro", "iphone 14 plus", "iphone 14",
    "iphone 13 pro max", "iphone 13 pro", "iphone 13 mini", "iphone 13",
    "iphone 12 pro max", "iphone 12 pro", "iphone 12 mini", "iphone 12",
    "iphone 11 pro max", "iphone 11 pro", "iphone 11",
    "ipad pro", "ipad air",
    "samsung galaxy s24 ultra", "samsung galaxy s23 ultra", "xiaomi redmi note"
}

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

def obtener_lista_modelos():
    """Obtiene la lista de modelos aprendidos únicamente por el usuario."""
    config = _read_config()
    modelos = config.get("custom_modelos", [])
    
    # Filtrar modelos por defecto antiguos si existían en el json
    modelos_limpios = [m for m in modelos if isinstance(m, str) and m.strip().lower() not in PREPOPULATED_DEFAULTS]
    
    if len(modelos_limpios) != len(modelos):
        config["custom_modelos"] = modelos_limpios
        _write_config(config)
        
    return modelos_limpios

def guardar_nuevo_modelo(modelo_texto):
    """Agrega un nuevo modelo a la lista si no existe previamente y la guarda en la configuración."""
    if not modelo_texto or not isinstance(modelo_texto, str):
        return False
    modelo_clean = modelo_texto.strip()
    if not modelo_clean or len(modelo_clean) < 2:
        return False
        
    config = _read_config()
    modelos = config.get("custom_modelos", [])
    modelos = [m for m in modelos if isinstance(m, str) and m.strip().lower() not in PREPOPULATED_DEFAULTS]
    
    # Verificar insensible a mayúsculas/minúsculas
    if not any(m.lower() == modelo_clean.lower() for m in modelos):
        modelos.insert(0, modelo_clean)  # Agregar al inicio para rápida selección
        config["custom_modelos"] = modelos
        _write_config(config)
        return True
    return False

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

def cargar_logo_enabled_config():
    """Carga la preferencia de si el logo está activado o no."""
    config = _read_config()
    return config.get("logo_enabled", True)

def guardar_logo_enabled_config(enabled):
    """Guarda la preferencia de activación del logo en la configuración."""
    config = _read_config()
    config["logo_enabled"] = bool(enabled)
    _write_config(config)

def cargar_impresora_config():
    """Carga el nombre de la impresora guardada en la configuración."""
    config = _read_config()
    return config.get("printer_name", "")

def guardar_impresora_config(printer_name):
    """Guarda el nombre de la impresora en la configuración."""
    config = _read_config()
    config["printer_name"] = printer_name
    _write_config(config)

def guardar_config_sumatra():
    """Guarda solo la ruta de SumatraPDF en el archivo de configuración."""
    if SUMATRA_PDF_PATH and platform.system() == "Windows":
        config = _read_config()
        config["sumatra_pdf_path"] = SUMATRA_PDF_PATH
        _write_config(config)

def detectar_sumatra_si_no_configurado():
    """Intenta encontrar SumatraPDF en todas las rutas comunes de Windows, registros y carpetas del usuario."""
    global SUMATRA_PDF_PATH
    if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH) and os.path.isfile(SUMATRA_PDF_PATH):
        return SUMATRA_PDF_PATH

    if platform.system() != "Windows":
        return None

    user_profile = os.environ.get("USERPROFILE", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")
    current_exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()

    SUMATRA_PDF_CANDIDATE_PATHS = [
        os.path.join(current_exe_dir, "SumatraPDF.exe"),
        os.path.join(local_app_data, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(program_files, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(program_files_x86, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(app_data, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(user_profile, "Downloads", "SumatraPDF.exe"),
        os.path.join(user_profile, "Desktop", "SumatraPDF.exe"),
        "C:\\SumatraPDF\\SumatraPDF.exe",
        "SumatraPDF.exe"
    ]

    # 1. Probar candidato por candidato
    for path_candidate in SUMATRA_PDF_CANDIDATE_PATHS:
        if path_candidate and os.path.exists(path_candidate) and os.path.isfile(path_candidate):
            SUMATRA_PDF_PATH = path_candidate
            print(f"SumatraPDF detectado automáticamente en: {SUMATRA_PDF_PATH}")
            guardar_config_sumatra()
            return SUMATRA_PDF_PATH

    # 2. Buscar en el PATH del sistema usando 'where'
    try:
        result = subprocess.run(["where", "SumatraPDF.exe"], capture_output=True, text=True, check=False, shell=True)
        if result.returncode == 0 and result.stdout.strip():
            found_path = result.stdout.strip().splitlines()[0]
            if os.path.exists(found_path) and os.path.isfile(found_path):
                SUMATRA_PDF_PATH = found_path
                print(f"SumatraPDF detectado en el PATH: {SUMATRA_PDF_PATH}")
                guardar_config_sumatra()
                return SUMATRA_PDF_PATH
    except Exception:
        pass

    # 3. Buscar en el Registro de Windows (App Paths / Uninstall)
    try:
        import winreg
        keys_to_check = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\SumatraPDF.exe"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\SumatraPDF.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SumatraPDF"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\SumatraPDF")
        ]
        for root_key, subkey in keys_to_check:
            try:
                with winreg.OpenKey(root_key, subkey) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.exists(val) and os.path.isfile(val):
                        SUMATRA_PDF_PATH = val
                        print(f"SumatraPDF detectado en Registro: {SUMATRA_PDF_PATH}")
                        guardar_config_sumatra()
                        return SUMATRA_PDF_PATH
            except Exception:
                continue
    except Exception:
        pass

    return None

def es_sumatra_configurado():
    """Retorna True si SumatraPDF está configurado/detectado y existe en disco."""
    global SUMATRA_PDF_PATH
    if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH) and os.path.isfile(SUMATRA_PDF_PATH):
        return True
    path = detectar_sumatra_si_no_configurado()
    return bool(path and os.path.exists(path) and os.path.isfile(path))


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

# --- FUNCIONES ETIQUETA 2X4 / ENVÍO ---
def _generar_google_maps_link(ubicacion_str):
    if not ubicacion_str or not ubicacion_str.strip():
        return None
    query_encoded = urllib.parse.quote_plus(ubicacion_str.strip())
    return f"https://www.google.com/maps/search/?api=1&query={query_encoded}"

def _generar_qr_gmaps_temp(ubicacion_str):
    if not ubicacion_str or not ubicacion_str.strip():
        return None
    gmaps_link = _generar_google_maps_link(ubicacion_str)
    if not gmaps_link:
        return None
    try:
        qr = qrcode.QRCode(version=1, box_size=3, border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(gmaps_link)
        img = qr.make_image(fill_color="black", back_color="white")
        fd, temp_path = tempfile.mkstemp(suffix=".png", prefix="qr_gmaps_")
        os.close(fd)
        with open(temp_path, 'wb') as f:
            img.save(f)
        return temp_path
    except Exception as e:
        print(f"Error guardando QR temp: {e}")
        return None

def _generar_etiqueta_2x4_pil_image(destinatario, origen, destino):
    DPI = 300
    LABEL_WIDTH_PX = int(4.0 * DPI)  # 1200 px
    LABEL_HEIGHT_PX = int(3.0 * DPI) # 900 px
    
    image = Image.new("RGB", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), "white")
    draw = ImageDraw.Draw(image)
    
    font_titulo = obtener_fuente_pil(FONT_BOLD_PATH_TTF, int(14 * DPI / 72))
    titulo_text = "DESTINATARIO:"
    titulo_w = draw.textlength(titulo_text, font=font_titulo)
    y_actual = int(0.55 * DPI)
    draw.text(((LABEL_WIDTH_PX - titulo_w) // 2, y_actual), titulo_text, fill="black", font=font_titulo)
    
    destinatario_upper = destinatario.strip().upper() if destinatario.strip() else "NOMBRE DESTINATARIO"
    max_w = LABEL_WIDTH_PX - int(0.4 * DPI)
    
    font_size_pt = 30
    min_size_pt = 10
    font_dest = obtener_fuente_pil(FONT_BOLD_PATH_TTF, int(font_size_pt * DPI / 72))
    while font_size_pt > min_size_pt and draw.textlength(destinatario_upper, font=font_dest) > max_w:
        font_size_pt -= 1
        font_dest = obtener_fuente_pil(FONT_BOLD_PATH_TTF, int(font_size_pt * DPI / 72))
        
    dest_w = draw.textlength(destinatario_upper, font=font_dest)
    y_actual += int(0.35 * DPI)
    draw.text(((LABEL_WIDTH_PX - dest_w) // 2, y_actual), destinatario_upper, fill="black", font=font_dest)
    
    # QR grande en el centro para el envío
    qr_size_px = int(1.65 * DPI) # ~495px (QR grande centrado)
    y_qr = y_actual + int(0.40 * DPI)
    x_qr = (LABEL_WIDTH_PX - qr_size_px) // 2
    
    ubicacion_qr = destino.strip() if destino.strip() else origen.strip()
    if ubicacion_qr:
        link_qr = _generar_google_maps_link(ubicacion_qr)
        qr_img = _crear_qr_pil(link_qr, qr_size_px)
        if qr_img:
            image.paste(qr_img, (x_qr, y_qr))
            font_help = obtener_fuente_pil(FONT_REGULAR_PATH_TTF, int(9 * DPI / 72))
            help_txt = "Escanear para ver envío"
            help_w = draw.textlength(help_txt, font=font_help)
            draw.text(((LABEL_WIDTH_PX - help_w) // 2, y_qr + qr_size_px + 10), help_txt, fill="black", font=font_help)

    return image

def _crear_qr_pil(data, target_size_px):
    if not data: return None
    try:
        qr = qrcode.QRCode(version=1, box_size=3, border=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(data)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        return img.resize((target_size_px, target_size_px), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"Error generando QR PIL: {e}")
        return None

def _dibujar_etiqueta_2x4_canvas(c, nombre_destinatario_data, origen_data, destino_data):
    if not PDF_SAVE_ENABLED: return
    LABEL_WIDTH_PT = 4 * inch
    LABEL_HEIGHT_PT = 3 * inch
    ETIQUETA_MARGEN_GENERAL_PT = 15
    ETIQUETA_MARGEN_SUPERIOR_TEXTO_PT = 45 
    ETIQUETA_FONT_TITULO_SIZE = 14
    ETIQUETA_FONT_DESTINATARIO_MAX_SIZE = 30
    ETIQUETA_FONT_DESTINATARIO_MIN_SIZE = 10
    ETIQUETA_FONT_QR_HELP_SIZE = 8
    ETIQUETA_FONT_PRINCIPAL_BOLD = "Times-Bold"
    ETIQUETA_FONT_QR_HELPER = "Helvetica"
    ETIQUETA_QR_SIZE_PT = 95  # QR grande centrado

    y_actual = LABEL_HEIGHT_PT - ETIQUETA_MARGEN_SUPERIOR_TEXTO_PT
    c.setFont(ETIQUETA_FONT_PRINCIPAL_BOLD, ETIQUETA_FONT_TITULO_SIZE)
    c.drawCentredString(LABEL_WIDTH_PT / 2, y_actual, "DESTINATARIO:")
    
    y_actual -= (10 + ETIQUETA_FONT_TITULO_SIZE * 0.9)
    nombre_destinatario_upper = nombre_destinatario_data.upper()
    max_ancho_nombre = LABEL_WIDTH_PT - (2 * ETIQUETA_MARGEN_GENERAL_PT)
    
    tam_fuente = ETIQUETA_FONT_DESTINATARIO_MAX_SIZE
    while tam_fuente >= ETIQUETA_FONT_DESTINATARIO_MIN_SIZE:
        if c.stringWidth(nombre_destinatario_upper, ETIQUETA_FONT_PRINCIPAL_BOLD, tam_fuente) <= max_ancho_nombre:
            break
        tam_fuente -= 1
        
    c.setFont(ETIQUETA_FONT_PRINCIPAL_BOLD, tam_fuente)
    y_actual -= (tam_fuente * 0.9)
    c.drawCentredString(LABEL_WIDTH_PT / 2, y_actual, nombre_destinatario_upper)
    
    # QR Único Grande Centrado
    ubicacion_qr = destino_data.strip() if destino_data.strip() else origen_data.strip()
    if ubicacion_qr:
        qr_path = _generar_qr_gmaps_temp(ubicacion_qr)
        if qr_path and os.path.exists(qr_path):
            qr_x = (LABEL_WIDTH_PT - ETIQUETA_QR_SIZE_PT) / 2
            y_qr = y_actual - (tam_fuente * 0.3) - 15 - ETIQUETA_QR_SIZE_PT
            c.drawImage(ReportLabImageReader(qr_path), qr_x, y_qr, width=ETIQUETA_QR_SIZE_PT, height=ETIQUETA_QR_SIZE_PT, mask='auto')
            c.setFont(ETIQUETA_FONT_QR_HELPER, ETIQUETA_FONT_QR_HELP_SIZE)
            c.drawCentredString(LABEL_WIDTH_PT / 2, y_qr - 10, "Escanear para ver envío")
            try: os.remove(qr_path)
            except: pass

def _generar_etiqueta_2x4_pdf_temporal(destinatario, origen, destino, cantidad=1):
    if not PDF_SAVE_ENABLED: return None
    fd, pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="etiqueta_2x4_")
    os.close(fd)
    if pdf_path not in temporary_files_to_delete:
        temporary_files_to_delete.append(pdf_path)
        
    LABEL_WIDTH_PT = 4 * inch
    LABEL_HEIGHT_PT = 3 * inch
    
    c = reportlab_canvas.Canvas(pdf_path, pagesize=(LABEL_WIDTH_PT, LABEL_HEIGHT_PT))
    for _ in range(cantidad):
        _dibujar_etiqueta_2x4_canvas(c, destinatario, origen, destino)
        c.showPage()
    c.save()
    return pdf_path

# --- FUNCIÓN DE LECTURA E IMPORTACIÓN DE ARCHIVOS (EXCEL / CSV / TXT) ---
def extraer_imeis_y_modelo_de_archivo(filepath):
    """
    Lee un archivo .xlsx, .csv, .tsv o .txt y extrae todos los IMEIs (15 dígitos)
    y opcionalmente el modelo de dispositivo si se encuentra en la hoja o texto.
    """
    ext = os.path.splitext(filepath)[1].lower()
    imeis = []
    modelo_encontrado = None
    imei_regex = re.compile(r'\b\d{15}\b')
    lines_raw = []

    if ext == '.xlsx':
        try:
            import zipfile, xml.etree.ElementTree as ET
            with zipfile.ZipFile(filepath, 'r') as z:
                shared_strings = []
                if 'xl/sharedStrings.xml' in z.namelist():
                    xml_content = z.read('xl/sharedStrings.xml')
                    tree = ET.fromstring(xml_content)
                    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for si in tree.findall('.//ns:si', ns):
                        t_nodes = si.findall('.//ns:t', ns)
                        text = "".join([t.text for t in t_nodes if t.text])
                        shared_strings.append(text)
                
                sheet_files = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet')]
                if sheet_files:
                    xml_content = z.read(sheet_files[0])
                    tree = ET.fromstring(xml_content)
                    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for row in tree.findall('.//ns:row', ns):
                        fila = []
                        for c in row.findall('.//ns:c', ns):
                            t_attr = c.get('t', '')
                            v_node = c.find('ns:v', ns)
                            val = ""
                            if v_node is not None and v_node.text is not None:
                                val = v_node.text
                                if t_attr == 's' and val.isdigit():
                                    idx = int(val)
                                    val = shared_strings[idx] if idx < len(shared_strings) else val
                            else:
                                is_node = c.find('ns:is', ns)
                                if is_node is not None:
                                    t_nodes = is_node.findall('.//ns:t', ns)
                                    val = "".join([t.text for t in t_nodes if t.text])
                            if val:
                                fila.append(val)
                        if fila:
                            lines_raw.append(" ".join(fila))
                            for cell in fila:
                                cell_clean = cell.strip()
                                if any(kw in cell_clean.lower() for kw in ["iphone", "ipad", "samsung", "xiaomi", "redmi", "pixel"]):
                                    if not modelo_encontrado:
                                        modelo_encontrado = cell_clean
        except Exception as e:
            print(f"Error al leer archivo Excel: {e}")

    elif ext in ['.csv', '.tsv']:
        try:
            import csv
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                sample = f.read(2048)
                f.seek(0)
                delimiter = '\t' if ext == '.tsv' or '\t' in sample else (',' if ',' in sample else ';')
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    lines_raw.append(" ".join(row))
                    for cell in row:
                        cell_clean = cell.strip()
                        if any(kw in cell_clean.lower() for kw in ["iphone", "ipad", "samsung", "xiaomi", "redmi", "pixel"]):
                            if not modelo_encontrado:
                                modelo_encontrado = cell_clean
        except Exception as e:
            print(f"Error al leer archivo CSV/TSV: {e}")
    else:  # .txt o similar
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    lines_raw.append(line.strip())
        except Exception as e:
            print(f"Error al leer archivo de texto: {e}")

    # Extraer IMEIs usando regex estricto de 15 dígitos
    texto_completo = "\n".join(lines_raw)
    encontrados = imei_regex.findall(texto_completo)

    if not encontrados:
        for line in lines_raw:
            cleaned = "".join(c for c in line if c.isdigit())
            if len(cleaned) == 15:
                encontrados.append(cleaned)

    # Eliminar duplicados preservando el orden
    seen = set()
    for imei in encontrados:
        if imei not in seen:
            seen.add(imei)
            imeis.append(imei)

    return imeis, modelo_encontrado

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
        self.geometry("450x190")
        self.resizable(False, False)
        self.configure(fg_color="#0F172A")
        
        # Centrar la ventana de progreso respecto al padre
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        
        self.grid_columnconfigure(0, weight=1)
        
        # 1. Porcentaje y Título en la Parte Superior
        self.percent_label = customtkinter.CTkLabel(
            self, 
            text=f"⚡ Descargando v{version_nueva} (0%)", 
            font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"),
            text_color="#06B6D4"
        )
        self.percent_label.grid(row=0, column=0, padx=20, pady=(20, 5))
        
        # 2. Barra de Progreso
        self.progress_bar = customtkinter.CTkProgressBar(self, width=380, height=14, corner_radius=7, fg_color="#1E293B", progress_color="#06B6D4")
        self.progress_bar.grid(row=1, column=0, padx=20, pady=10)
        self.progress_bar.set(0)
        
        # 3. Detalle de estado (MBs transferidos)
        self.status_label = customtkinter.CTkLabel(self, text="Conectando con servidor de descarga...", font=customtkinter.CTkFont(family="Inter", size=11), text_color="#94A3B8")
        self.status_label.grid(row=2, column=0, padx=20, pady=(0, 20))
        
    def actualizar_progreso(self, valor, porcentaje, texto_status):
        self.progress_bar.set(valor)
        self.percent_label.configure(text=f"⚡ Descargando v3.3.12 ({porcentaje}%)")
        self.status_label.configure(text=texto_status)

class IMEIHistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, parent, on_select_callback):
        super().__init__(parent)
        self.title("Historial de IMEIs Procesados")
        self.geometry("550x450")
        self.resizable(False, False)
        self.on_select_callback = on_select_callback
        
        # Asegurarnos de que aparezca al frente
        self.transient(parent)
        self.grab_set()
        self.lift()
        self.focus_force()
        
        # Configurar colores
        self.configure(fg_color="#0F172A")
        
        # Header
        header_frame = customtkinter.CTkFrame(self, fg_color="#1E293B", height=60, corner_radius=0)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        
        title_label = customtkinter.CTkLabel(
            header_frame, 
            text="Historial de Procesos", 
            font=customtkinter.CTkFont(family="Inter", size=16, weight="bold"),
            text_color="#06B6D4"
        )
        title_label.pack(pady=15, padx=20, side=tk.LEFT)
        
        # Scrollable Frame para la lista de historial
        self.scrollable_frame = customtkinter.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569"
        )
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.cargar_historial()

    def cargar_historial(self):
        # Limpiar frame
        for child in self.scrollable_frame.winfo_children():
            child.destroy()
            
        config = _read_config()
        historial = config.get("imei_history", [])
        
        if not historial:
            no_history_label = customtkinter.CTkLabel(
                self.scrollable_frame,
                text="No hay registros en el historial.",
                font=customtkinter.CTkFont(family="Inter", size=13, slant="italic"),
                text_color="#64748B"
            )
            no_history_label.pack(pady=40)
            return
            
        for index, reg in enumerate(historial):
            # Tarjeta de registro
            card = customtkinter.CTkFrame(
                self.scrollable_frame,
                fg_color="#1E293B",
                border_width=1,
                border_color="#334155",
                corner_radius=10
            )
            card.pack(fill=tk.X, pady=6, padx=5)
            card.grid_columnconfigure(0, weight=1)
            
            # Textos de la tarjeta
            info_frame = customtkinter.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=0, column=0, padx=12, pady=10, sticky="w")
            
            time_label = customtkinter.CTkLabel(
                info_frame,
                text=reg.get("timestamp", "Fecha desconocida"),
                font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
                text_color="#94A3B8"
            )
            time_label.pack(anchor="w")
            
            detalles = f"IMEIs extraídos: {reg.get('count', 0)}"
            if reg.get("preview"):
                detalles += f" ({reg.get('preview')})"
                
            details_label = customtkinter.CTkLabel(
                info_frame,
                text=detalles,
                font=customtkinter.CTkFont(family="Inter", size=11),
                text_color="#F8FAFC"
            )
            details_label.pack(anchor="w", pady=(2, 0))
            
            # Botones
            btn_frame = customtkinter.CTkFrame(card, fg_color="transparent")
            btn_frame.grid(row=0, column=1, padx=12, pady=10, sticky="e")
            
            importar_btn = customtkinter.CTkButton(
                btn_frame,
                text="Importar",
                width=80,
                height=28,
                corner_radius=6,
                fg_color="#06B6D4",
                hover_color="#0891B2",
                text_color="#FFFFFF",
                font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
                command=lambda r=reg: self.seleccionar_registro(r)
            )
            importar_btn.pack(side=tk.LEFT, padx=3)
            
            eliminar_btn = customtkinter.CTkButton(
                btn_frame,
                text="Borrar",
                width=60,
                height=28,
                corner_radius=6,
                fg_color="#EF4444",
                hover_color="#DC2626",
                text_color="#FFFFFF",
                font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
                command=lambda idx=index: self.eliminar_registro(idx)
            )
            eliminar_btn.pack(side=tk.LEFT, padx=3)

    def seleccionar_registro(self, registro):
        self.on_select_callback(registro.get("input_text", ""))
        self.grab_release()
        self.destroy()
        
    def eliminar_registro(self, index):
        config = _read_config()
        historial = config.get("imei_history", [])
        if 0 <= index < len(historial):
            historial.pop(index)
            config["imei_history"] = historial
            _write_config(config)
            self.cargar_historial()

# --- Clase Principal de la Aplicación ---
class AppGeneradorEtiquetas(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.preview_ctk_image = None
        self._preview_update_job = None
        self.cached_logo_pil = None
        
        # Configuración Inicial y de Icono (Ventana y Barra de Tareas)
        self.title(f"McTools v{VERSION}")
        icon_ico = obtener_ruta_recurso("logo.ico")
        icon_png = obtener_ruta_recurso("logo.png")
        if os.path.exists(icon_ico):
            try:
                self.iconbitmap(icon_ico)
            except Exception:
                pass
        if os.path.exists(icon_png):
            try:
                img = Image.open(icon_png)
                self._app_icon_photo = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._app_icon_photo)
            except Exception:
                pass
        elif os.path.exists(icon_ico):
            try:
                img = Image.open(icon_ico)
                self._app_icon_photo = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._app_icon_photo)
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
        self.actualizar_estado_sumatra_ui()
        self.cargar_y_cachear_logo()
        self._bind_events()
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_aplicacion)
        self.after(100, self.force_preview_update)
        self.after(2000, self.chequear_actualizaciones_async)

    def _setup_ui(self):
        # Frame de Controles (Izquierda)
        self.controls_frame.grid_columnconfigure(0, weight=1)
        
        # Variables Compartidas
        self.modelo_var = tk.StringVar()
        logo_path_inicial = cargar_logo_config()
        self.logo_path_var = tk.StringVar(value=logo_path_inicial)
        self.logo_enabled_var = tk.BooleanVar(value=cargar_logo_enabled_config())
        
        # Variables específicas de Pestaña Barcode
        self.imei_var = tk.StringVar()

        # Variables para Pestaña Etiqueta 2x4 (Envío) y Gestión de Destinatarios
        self.destinatarios_guardados = {}
        self.envio_destinatario_var = tk.StringVar()
        self.envio_origen_var = tk.StringVar()
        self.envio_destino_var = tk.StringVar()
        self.envio_cantidad_var = tk.StringVar(value="1")
        self._load_destinatarios()

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
        
        self.update_ready = False
        self.downloaded_new_exe = None

        self.btn_update = customtkinter.CTkButton(
            title_container, 
            text="Buscar act.", 
            font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
            text_color="#F8FAFC",
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=6,
            height=22,
            width=110,
            command=self.accion_boton_actualizacion
        )
        self.btn_update.grid(row=0, column=2, padx=(8, 0), sticky="w")
        
        subtitle_label = customtkinter.CTkLabel(
            header_frame, 
            text="Herramientas de IMEI y Etiquetas", 
            font=customtkinter.CTkFont(family="Inter", size=12),
            text_color="#94A3B8"
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Barra de progreso integrada para descargas de actualización (inline, sin popups)
        self.update_progress = customtkinter.CTkProgressBar(header_frame, height=5, corner_radius=3, fg_color="#0F172A", progress_color="#06B6D4")
        self.update_progress.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.update_progress.set(0)
        self.update_progress.grid_remove()  # Oculta hasta que se inicie una descarga

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
        self.tab_envio = self.tabview.add("Gestión de Destinatario")
        
        # Configure columns inside tabs
        self.tab_barcode.grid_columnconfigure(0, weight=1)
        self.tab_qr.grid_columnconfigure(0, weight=1)
        self.tab_procesador.grid_columnconfigure(0, weight=1)
        self.tab_envio.grid_columnconfigure(0, weight=1)

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
        self.modelo_entry_bc = customtkinter.CTkComboBox(
            modelo_entry_frame_bc,
            variable=self.modelo_var,
            values=obtener_lista_modelos(),
            fg_color="#1E293B",
            border_color="#475569",
            text_color="#F8FAFC",
            button_color="#334155",
            button_hover_color="#475569",
            dropdown_fg_color="#0F172A",
            dropdown_text_color="#F8FAFC",
            dropdown_hover_color="#334155",
            font=customtkinter.CTkFont(family="Inter", size=11),
            dropdown_font=customtkinter.CTkFont(family="Inter", size=11),
            height=32,
            corner_radius=8
        )
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
        
        logo_header_bc = customtkinter.CTkFrame(logo_card_bc, fg_color="transparent")
        logo_header_bc.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="ew")
        logo_header_bc.grid_columnconfigure(0, weight=1)
        
        customtkinter.CTkLabel(logo_header_bc, text="Logo en Etiqueta", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, sticky="w")
        
        self.logo_switch_bc = customtkinter.CTkSwitch(
            logo_header_bc,
            text="Activado" if self.logo_enabled_var.get() else "Desactivado",
            variable=self.logo_enabled_var,
            onvalue=True,
            offvalue=False,
            font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
            text_color="#10B981" if self.logo_enabled_var.get() else "#64748B",
            progress_color="#10B981",
            command=self.al_cambiar_switch_logo
        )
        self.logo_switch_bc.grid(row=0, column=1, sticky="e")

        logo_entry_frame_bc = customtkinter.CTkFrame(logo_card_bc, fg_color="transparent")
        logo_entry_frame_bc.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        logo_entry_frame_bc.grid_columnconfigure(0, weight=1)
        self.logo_entry_bc = customtkinter.CTkEntry(logo_entry_frame_bc, textvariable=self.logo_path_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.logo_entry_bc.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(logo_entry_frame_bc, text="Buscar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.buscar_logo).grid(row=0, column=1, padx=0)

        # Acciones Barcode
        actions_bc = customtkinter.CTkFrame(self.tab_barcode, fg_color="transparent")
        actions_bc.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        actions_bc.grid_columnconfigure(0, weight=1)
        customtkinter.CTkButton(actions_bc, text="Imprimir", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.imprimir).grid(row=0, column=0, padx=0, sticky="ew")


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
        self.modelo_entry_qr = customtkinter.CTkComboBox(
            modelo_entry_frame_qr,
            variable=self.modelo_var,
            values=obtener_lista_modelos(),
            fg_color="#1E293B",
            border_color="#475569",
            text_color="#F8FAFC",
            button_color="#334155",
            button_hover_color="#475569",
            dropdown_fg_color="#0F172A",
            dropdown_text_color="#F8FAFC",
            dropdown_hover_color="#334155",
            font=customtkinter.CTkFont(family="Inter", size=11),
            dropdown_font=customtkinter.CTkFont(family="Inter", size=11),
            height=32,
            corner_radius=8
        )
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
        limpiar_frame.grid_columnconfigure((0, 1, 2), weight=1)
        customtkinter.CTkButton(limpiar_frame, text="Limpiar IMEIs", height=28, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), command=self.limpiar_imeis).grid(row=0, column=0, padx=(0, 2), sticky="ew")
        customtkinter.CTkButton(limpiar_frame, text="Pegar IMEIs", height=28, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), command=self.pegar_imeis).grid(row=0, column=1, padx=2, sticky="ew")
        customtkinter.CTkButton(limpiar_frame, text="📥 Cargar Excel/CSV", height=28, fg_color="#10B981", hover_color="#059669", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), command=self.importar_archivo_imeis).grid(row=0, column=2, padx=(2, 0), sticky="ew")

        # Tarjeta Logo (Compartida)
        logo_card_qr = customtkinter.CTkFrame(inputs_qr, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        logo_card_qr.grid(row=2, column=0, padx=5, pady=(0, 15), sticky="ew")
        logo_card_qr.grid_columnconfigure(0, weight=1)

        logo_header_qr = customtkinter.CTkFrame(logo_card_qr, fg_color="transparent")
        logo_header_qr.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="ew")
        logo_header_qr.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(logo_header_qr, text="Logo en Etiqueta", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, sticky="w")

        self.logo_switch_qr = customtkinter.CTkSwitch(
            logo_header_qr,
            text="Activado" if self.logo_enabled_var.get() else "Desactivado",
            variable=self.logo_enabled_var,
            onvalue=True,
            offvalue=False,
            font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
            text_color="#10B981" if self.logo_enabled_var.get() else "#64748B",
            progress_color="#10B981",
            command=self.al_cambiar_switch_logo
        )
        self.logo_switch_qr.grid(row=0, column=1, sticky="e")

        logo_entry_frame_qr = customtkinter.CTkFrame(logo_card_qr, fg_color="transparent")
        logo_entry_frame_qr.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        logo_entry_frame_qr.grid_columnconfigure(0, weight=1)
        self.logo_entry_qr = customtkinter.CTkEntry(logo_entry_frame_qr, textvariable=self.logo_path_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.logo_entry_qr.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        customtkinter.CTkButton(logo_entry_frame_qr, text="Buscar", width=60, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), command=self.buscar_logo).grid(row=0, column=1, padx=0)

        # Acciones QR
        actions_qr = customtkinter.CTkFrame(self.tab_qr, fg_color="transparent")
        actions_qr.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        actions_qr.grid_columnconfigure(0, weight=1)
        customtkinter.CTkButton(actions_qr, text="Imprimir", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.imprimir).grid(row=0, column=0, padx=0, sticky="ew")


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
        limpiar_importar_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
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
        ).grid(row=0, column=0, padx=(0, 2), sticky="ew")
        
        customtkinter.CTkButton(
            limpiar_importar_frame,
            text="📥 Cargar Excel",
            fg_color="#10B981",
            hover_color="#059669",
            text_color="#FFFFFF",
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            height=32,
            corner_radius=8,
            command=self.proc_importar_archivo
        ).grid(row=0, column=1, padx=2, sticky="ew")

        customtkinter.CTkButton(
            limpiar_importar_frame,
            text="Ver Historial",
            fg_color="#334155",
            hover_color="#475569",
            text_color="#F8FAFC",
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"),
            height=32,
            corner_radius=8,
            command=self.proc_mostrar_historial
        ).grid(row=0, column=2, padx=(2, 0), sticky="ew")


        # 3. Contenedor Inferior (Configuración & Autor)
        footer_container = customtkinter.CTkFrame(self.controls_frame, fg_color="transparent")
        footer_container.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="sew")
        footer_container.grid_columnconfigure(0, weight=1)
        
        # Selector de Impresora
        customtkinter.CTkLabel(
            footer_container, 
            text="Seleccionar Impresora", 
            font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), 
            text_color="#94A3B8"
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        impresoras = obtener_lista_impresoras()
        default_sys_printer = obtener_impresora_predeterminada()
        saved_printer = cargar_impresora_config()
        
        # Validar si la impresora guardada sigue disponible, de lo contrario usar predeterminada
        if saved_printer and saved_printer in impresoras:
            active_printer = saved_printer
        elif default_sys_printer:
            active_printer = default_sys_printer
        else:
            active_printer = impresoras[0] if impresoras else "Impresora Predeterminada"
            
        self.printer_var = tk.StringVar(value=active_printer)
        self.printer_combo = customtkinter.CTkComboBox(
            footer_container,
            values=impresoras if impresoras else ["Impresora Predeterminada"],
            variable=self.printer_var,
            fg_color="#1E293B",
            border_color="#475569",
            text_color="#F8FAFC",
            button_color="#334155",
            button_hover_color="#475569",
            height=32,
            corner_radius=8,
            command=self.al_seleccionar_impresora
        )
        self.printer_combo.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
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
        self.config_sumatra_btn.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        # Créditos
        customtkinter.CTkLabel(
            footer_container, 
            text="Hecho por Micael", 
            font=customtkinter.CTkFont(family="Inter", size=10, slant="italic"), 
            text_color="#64748B"
        ).grid(row=3, column=0, sticky="w")

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
        proc_actions.grid_columnconfigure(0, weight=1)
        
        self.proc_copy_btn = customtkinter.CTkButton(proc_actions, text="Copiar al Portapapeles", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.proc_copiar_portapapeles, state="disabled")
        self.proc_copy_btn.grid(row=0, column=0, padx=0, sticky="ew")
        
        # Grid inicial para el procesador (oculto)
        self.procesador_output_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.procesador_output_frame.grid_remove()

        # ---------------- PESTAÑA ETIQUETA 2X4 (ENVÍO) ----------------
        inputs_envio = customtkinter.CTkFrame(self.tab_envio, fg_color="transparent")
        inputs_envio.grid(row=0, column=0, sticky="ew")
        inputs_envio.grid_columnconfigure(0, weight=1)

        # 1. Tarjeta Gestión de Destinatarios
        dest_card = customtkinter.CTkFrame(inputs_envio, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        dest_card.grid(row=0, column=0, padx=5, pady=(5, 12), sticky="ew")
        dest_card.grid_columnconfigure(0, weight=1)
        
        dest_header = customtkinter.CTkFrame(dest_card, fg_color="transparent")
        dest_header.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="ew")
        dest_header.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(dest_header, text="Gestión de Destinatarios", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, sticky="w")
        
        dest_combo_frame = customtkinter.CTkFrame(dest_card, fg_color="transparent")
        dest_combo_frame.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")
        dest_combo_frame.grid_columnconfigure(0, weight=1)
        
        nombres_dest = sorted(list(self.destinatarios_guardados.keys()))
        self.combobox_destinatarios = customtkinter.CTkComboBox(
            dest_combo_frame,
            values=nombres_dest,
            state="readonly",
            command=self._on_destinatario_selected,
            fg_color="#1E293B",
            border_color="#475569",
            text_color="#F8FAFC",
            button_color="#334155",
            button_hover_color="#475569",
            dropdown_fg_color="#0F172A",
            dropdown_text_color="#F8FAFC",
            dropdown_hover_color="#334155",
            font=customtkinter.CTkFont(family="Inter", size=11),
            dropdown_font=customtkinter.CTkFont(family="Inter", size=11),
            height=32,
            corner_radius=8
        )
        self.combobox_destinatarios.grid(row=0, column=0, sticky="ew")
        if not nombres_dest:
            self.combobox_destinatarios.set("")

        dest_buttons_frame = customtkinter.CTkFrame(dest_card, fg_color="transparent")
        dest_buttons_frame.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
        dest_buttons_frame.grid_columnconfigure((0, 1), weight=1)
        
        customtkinter.CTkButton(
            dest_buttons_frame,
            text="Guardar Actual",
            height=28,
            fg_color="#06B6D4",
            hover_color="#0891B2",
            text_color="#FFFFFF",
            font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
            command=self.guardar_destinatario_actual
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        customtkinter.CTkButton(
            dest_buttons_frame,
            text="Eliminar",
            height=28,
            fg_color="#EF4444",
            hover_color="#DC2626",
            text_color="#FFFFFF",
            font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"),
            command=self.eliminar_destinatario_seleccionado
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # 2. Tarjeta Datos de Envío
        datos_card = customtkinter.CTkFrame(inputs_envio, fg_color="#0F172A", border_width=1, border_color="#334155", corner_radius=12)
        datos_card.grid(row=1, column=0, padx=5, pady=(0, 15), sticky="ew")
        datos_card.grid_columnconfigure(0, weight=1)

        # Destinatario
        customtkinter.CTkLabel(datos_card, text="Nombre del DESTINATARIO", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")
        dest_entry_frame = customtkinter.CTkFrame(datos_card, fg_color="transparent")
        dest_entry_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        dest_entry_frame.grid_columnconfigure(0, weight=1)
        self.destinatario_entry_envio = customtkinter.CTkEntry(dest_entry_frame, textvariable=self.envio_destinatario_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.destinatario_entry_envio.grid(row=0, column=0, sticky="ew")

        # Destino / Envío
        customtkinter.CTkLabel(datos_card, text="Ciudad/Dirección de ENVÍO", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=2, column=0, padx=12, pady=(4, 2), sticky="w")
        destino_entry_frame = customtkinter.CTkFrame(datos_card, fg_color="transparent")
        destino_entry_frame.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="ew")
        destino_entry_frame.grid_columnconfigure(0, weight=1)
        self.destino_entry_envio = customtkinter.CTkEntry(destino_entry_frame, textvariable=self.envio_destino_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.destino_entry_envio.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        customtkinter.CTkButton(destino_entry_frame, text="📍 Maps", width=65, height=32, corner_radius=8, fg_color="#334155", hover_color="#475569", text_color="#F8FAFC", font=customtkinter.CTkFont(family="Inter", size=10, weight="bold"), command=lambda: self._open_gmaps("destino")).grid(row=0, column=1)

        # Cantidad de Etiquetas a Imprimir
        customtkinter.CTkLabel(datos_card, text="Cantidad de Etiquetas a Imprimir", font=customtkinter.CTkFont(family="Inter", size=11, weight="bold"), text_color="#94A3B8").grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
        cantidad_entry_frame = customtkinter.CTkFrame(datos_card, fg_color="transparent")
        cantidad_entry_frame.grid(row=5, column=0, padx=12, pady=(0, 10), sticky="ew")
        cantidad_entry_frame.grid_columnconfigure(0, weight=1)
        self.cantidad_entry_envio = customtkinter.CTkEntry(cantidad_entry_frame, textvariable=self.envio_cantidad_var, fg_color="#1E293B", border_color="#475569", text_color="#F8FAFC", height=32, corner_radius=8)
        self.cantidad_entry_envio.grid(row=0, column=0, sticky="ew")

        # Acciones Etiqueta 2x4
        actions_envio = customtkinter.CTkFrame(self.tab_envio, fg_color="transparent")
        actions_envio.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        actions_envio.grid_columnconfigure(0, weight=1)
        customtkinter.CTkButton(actions_envio, text="Imprimir", fg_color="#06B6D4", hover_color="#0891B2", text_color="#FFFFFF", font=customtkinter.CTkFont(family="Inter", size=13, weight="bold"), height=40, corner_radius=10, command=self.imprimir).grid(row=0, column=0, padx=0, sticky="ew")

    def _bind_events(self):
        # Eventos para actualizar la vista previa al escribir
        for var in [self.modelo_var, self.imei_var, self.envio_destinatario_var, self.envio_origen_var, self.envio_destino_var, self.envio_cantidad_var]:
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
            elif tab_activa == "Gestión de Destinatario":
                pil_image = _generar_etiqueta_2x4_pil_image(
                    self.envio_destinatario_var.get(),
                    self.envio_origen_var.get(),
                    self.envio_destino_var.get()
                )
            else:  # Código QR
                imeis = self.obtener_imeis_del_texto()
                self.actualizar_contador_imeis()
                pil_image = _generar_etiqueta_qr_pil_image(
                    self.modelo_var.get().strip().upper(),
                    imeis,
                    self.cached_logo_pil
                )
                
            self.preview_ctk_image = pil_to_tk_image_safe(
                pil_image,
                size=(PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT)
            )
            
            self.preview_image_label.configure(image=self.preview_ctk_image, text="")
        except Exception as e:
            self.preview_image_label.configure(image=None, text=f"Error en preview:\n{e}")

    def imprimir(self):
        tab_activa = self.tabview.get()
        if tab_activa == "Código de Barras":
            self._procesar_generacion_barcode(imprimir_despues=True)
        elif tab_activa == "Gestión de Destinatario":
            self._procesar_generacion_2x4(imprimir_despues=True)
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
        path_logo_pdf = self.logo_path_var.get().strip() if (hasattr(self, 'logo_enabled_var') and self.logo_enabled_var.get()) else ""
        temp_pdf_path = _generar_etiqueta_barcode_pdf_temporal(
            modelo, imei,
            "",
            path_logo_pdf
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
            
        path_logo_pdf = self.logo_path_var.get().strip() if (hasattr(self, 'logo_enabled_var') and self.logo_enabled_var.get()) else ""
        temp_pdf_path = _generar_etiqueta_qr_pdf_temporal(
            modelo,
            imeis,
            path_logo_pdf
        )
        if not temp_pdf_path or not os.path.exists(temp_pdf_path):
            messagebox.showerror("Error de Generación", "No se pudo crear el archivo PDF temporal.")
            return
        self._finalizar_generacion(temp_pdf_path, modelo, "qr", guardar_permanente, imprimir_despues)

    def _load_destinatarios(self):
        DESTINATARIOS_FILE = "destinatarios_etiquetas.json"
        target_path = DESTINATARIOS_FILE if os.path.exists(DESTINATARIOS_FILE) else obtener_ruta_recurso(DESTINATARIOS_FILE)
        if os.path.exists(target_path):
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    self.destinatarios_guardados = json.load(f)
            except Exception as e:
                print(f"Error al leer {target_path}: {e}")
                self.destinatarios_guardados = {}
        else:
            self.destinatarios_guardados = {}

    def _save_destinatarios(self):
        DESTINATARIOS_FILE = "destinatarios_etiquetas.json"
        try:
            with open(DESTINATARIOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.destinatarios_guardados, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo guardar la lista de destinatarios:\n{e}", parent=self)

    def _update_destinatarios_combobox(self):
        nombres = sorted(list(self.destinatarios_guardados.keys()))
        if hasattr(self, 'combobox_destinatarios'):
            self.combobox_destinatarios.configure(values=nombres)
            if not nombres:
                self.combobox_destinatarios.set("")

    def _on_destinatario_selected(self, nombre_seleccionado: str):
        if nombre_seleccionado in self.destinatarios_guardados:
            datos = self.destinatarios_guardados[nombre_seleccionado]
            self.envio_destinatario_var.set(datos.get("nombre_destinatario", nombre_seleccionado))
            self.envio_origen_var.set(datos.get("origen", ""))
            self.envio_destino_var.set(datos.get("destino", ""))
            self.schedule_preview_update()

    def guardar_destinatario_actual(self):
        nombre_destinatario = self.envio_destinatario_var.get().strip()
        if not nombre_destinatario:
            messagebox.showwarning("Campo Vacío", "El campo 'Nombre del DESTINATARIO' no puede estar vacío.", parent=self)
            return

        dialog = customtkinter.CTkInputDialog(
            text="Ingresa un nombre clave para este destinatario:",
            title="Guardar Destinatario",
            fg_color="#0F172A",
            button_fg_color="#06B6D4",
            button_hover_color="#0891B2",
            entry_fg_color="#1E293B",
            entry_text_color="#F8FAFC",
        )
        nombre_clave = dialog.get_input()

        if not nombre_clave or not nombre_clave.strip():
            return
        
        nombre_clave = nombre_clave.strip()

        if nombre_clave in self.destinatarios_guardados:
            if not messagebox.askyesno("Sobrescribir", f"El destinatario '{nombre_clave}' ya existe.\n¿Deseas sobrescribir?", parent=self):
                return

        self.destinatarios_guardados[nombre_clave] = {
            "nombre_destinatario": nombre_destinatario,
            "origen": self.envio_origen_var.get().strip(),
            "destino": self.envio_destino_var.get().strip()
        }
        self._save_destinatarios()
        self._update_destinatarios_combobox()
        self.combobox_destinatarios.set(nombre_clave)

    def eliminar_destinatario_seleccionado(self):
        nombre_clave = self.combobox_destinatarios.get()
        if not nombre_clave:
            messagebox.showwarning("Nada seleccionado", "Selecciona un destinatario de la lista para eliminar.", parent=self)
            return

        if nombre_clave in self.destinatarios_guardados:
            if messagebox.askyesno("Confirmar", f"¿Seguro que quieres eliminar a '{nombre_clave}'?", parent=self):
                del self.destinatarios_guardados[nombre_clave]
                self._save_destinatarios()
                self._update_destinatarios_combobox()
                self.envio_destinatario_var.set("")
                self.envio_origen_var.set("")
                self.envio_destino_var.set("")
                self.combobox_destinatarios.set("")
                self.schedule_preview_update()

    def _open_gmaps(self, tipo_ubicacion: str):
        ubicacion_str = (self.envio_origen_var.get() if tipo_ubicacion == "origen" else self.envio_destino_var.get()).strip()
        if not ubicacion_str:
            messagebox.showwarning("Entrada Vacía", f"El campo de {tipo_ubicacion} está vacío.", parent=self)
            return
        gmaps_link = _generar_google_maps_link(ubicacion_str)
        if gmaps_link:
            try:
                webbrowser.open(gmaps_link)
            except Exception as e:
                messagebox.showerror("Error al Abrir Enlace", f"No se pudo abrir el enlace:\n{e}", parent=self)

    def _procesar_generacion_2x4(self, guardar_permanente=False, imprimir_despues=False):
        if not PDF_SAVE_ENABLED:
            messagebox.showerror("Función Deshabilitada", "La librería 'ReportLab' es necesaria para esta función.")
            return
        destinatario = self.envio_destinatario_var.get().strip()
        origen = self.envio_origen_var.get().strip()
        destino = self.envio_destino_var.get().strip()
        if not destinatario:
            messagebox.showerror("Campo Obligatorio", "El campo 'Nombre del DESTINATARIO' es obligatorio.")
            return

        cantidad_str = self.envio_cantidad_var.get().strip() if hasattr(self, 'envio_cantidad_var') else "1"
        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0: raise ValueError("Debe ser mayor a 0")
        except ValueError:
            messagebox.showerror("Error en Cantidad", "La cantidad de etiquetas debe ser un número entero mayor que cero.", parent=self)
            return

        temp_pdf_path = _generar_etiqueta_2x4_pdf_temporal(
            destinatario, origen, destino, cantidad
        )
        if not temp_pdf_path or not os.path.exists(temp_pdf_path):
            messagebox.showerror("Error de Generación", "No se pudo crear el archivo PDF temporal.")
            return
        self._finalizar_generacion(temp_pdf_path, destinatario, "ENVIO_2X4", guardar_permanente, imprimir_despues)

    def aprender_modelo_actual(self):
        """Aprende y guarda en la configuración el modelo que el usuario está utilizando actualmente."""
        modelo = self.modelo_var.get().strip()
        if guardar_nuevo_modelo(modelo):
            # Actualizar opciones de los comboboxes de modelo en la interfaz
            nuevos_modelos = obtener_lista_modelos()
            if hasattr(self, 'modelo_entry_bc') and self.modelo_entry_bc:
                self.modelo_entry_bc.configure(values=nuevos_modelos)
            if hasattr(self, 'modelo_entry_qr') and self.modelo_entry_qr:
                self.modelo_entry_qr.configure(values=nuevos_modelos)

    def _finalizar_generacion(self, temp_pdf_path, modelo, identificador, guardar_permanente=False, imprimir_despues=False):
        self.aprender_modelo_actual()
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
                global SUMATRA_PDF_PATH
                if not es_sumatra_configurado():
                    detectar_sumatra_si_no_configurado()
                self.actualizar_estado_sumatra_ui()

                printer_name = self.printer_var.get().strip()
                
                # Si está seleccionada la "Impresora Predeterminada", usar la lógica predeterminada
                if printer_name == "Impresora Predeterminada":
                    if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH):
                        subprocess.Popen([SUMATRA_PDF_PATH, "-print-to-default", "-silent", filepath])
                    else:
                        os.startfile(filepath, "print")
                else:
                    if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH):
                        # SumatraPDF -print-to "<printer-name>" -silent filepath
                        subprocess.Popen([SUMATRA_PDF_PATH, "-print-to", printer_name, "-silent", filepath])
                    else:
                        # Si no hay SumatraPDF, usar win32api "printto" verb
                        try:
                            import win32api
                            win32api.ShellExecute(0, "printto", filepath, f'"{printer_name}"', ".", 0)
                        except Exception:
                            # Fallback si falla
                            os.startfile(filepath, "print")
            elif current_os in ["Darwin", "Linux"]:
                printer_name = self.printer_var.get().strip()
                if printer_name == "Impresora Predeterminada":
                    cmd = ["lpr", filepath] if current_os == "Darwin" else ["lp", filepath]
                else:
                    cmd = ["lpr", "-P", printer_name, filepath] if current_os == "Darwin" else ["lp", "-d", printer_name, filepath]
                subprocess.run(cmd, check=True)
            else:
                messagebox.showwarning("Sistema No Soportado", f"La impresión directa no está configurada para {current_os}.")
        except FileNotFoundError:
            messagebox.showerror("Error de Comando", "Comando de impresión no encontrado. Asegúrate de tener SumatraPDF configurado en Windows o lpr/lp en Unix.")
        except Exception as e:
            messagebox.showerror("Error de Impresión", f"Ocurrió un error inesperado al imprimir:\n\n{e}")

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
            # Guardar en el historial
            self.proc_guardar_en_historial(texto_crudo, len(imeis_unicos), imeis_unicos)
        else:
            self.proc_output_textbox.insert("1.0", "No se encontraron IMEIs válidos.")
            self.proc_count_label.configure(text="0 IMEIs")
            self.proc_copy_btn.configure(state="disabled")

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
        self.proc_input_textbox.focus_set()

    def proc_guardar_en_historial(self, texto_crudo, count, imeis_unicos):
        """Guarda un proceso de IMEIs en el historial de la configuración."""
        if not texto_crudo or texto_crudo == self.proc_placeholder_text:
            return
        
        # Generar un preview corto (primeros 3 IMEIs)
        preview = ", ".join(imeis_unicos[:3])
        if len(imeis_unicos) > 3:
            preview += "..."
            
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        nuevo_registro = {
            "timestamp": now_str,
            "input_text": texto_crudo,
            "count": count,
            "preview": preview
        }
        
        config = _read_config()
        historial = config.get("imei_history", [])
        
        # Evitar duplicar el mismo texto crudo si es el último procesado
        if historial and historial[0].get("input_text") == texto_crudo:
            return
            
        historial.insert(0, nuevo_registro)
        # Mantener al menos los últimos 10 procesos
        historial = historial[:10]
        
        config["imei_history"] = historial
        _write_config(config)

    def proc_restaurar_desde_historial(self, texto_crudo):
        """Restaura el texto crudo del historial y lo procesa."""
        self.proc_input_textbox.delete("1.0", tk.END)
        self.proc_input_textbox.insert("1.0", texto_crudo)
        self.proc_input_textbox.configure(text_color="#F8FAFC")
        self.proc_extraer_imeis()

    def proc_mostrar_historial(self):
        """Abre la ventana emergente con el historial de procesos de IMEIs."""
        try:
            if hasattr(self, 'historial_window') and self.historial_window and self.historial_window.winfo_exists():
                self.historial_window.lift()
                self.historial_window.focus_force()
                return
        except Exception:
            pass
            
        self.historial_window = IMEIHistoryWindow(self, self.proc_restaurar_desde_historial)

    def proc_copiar_portapapeles(self):
        """Copia la salida del procesador de IMEIs al portapapeles."""
        texto_salida = self.proc_output_textbox.get("1.0", tk.END).strip()
        if texto_salida and "No se encontraron IMEIs válidos." not in texto_salida:
            try:
                self.clipboard_clear()
                self.clipboard_append(texto_salida)
                
                # Feedback moderno temporizado sin popup
                self.proc_copy_btn.configure(text="¡Copiado!", fg_color="#10B981", hover_color="#059669")
                self.after(1500, lambda: self.proc_copy_btn.configure(text="Copiar al Portapapeles", fg_color="#06B6D4", hover_color="#0891B2"))
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

    def importar_archivo_imeis(self):
        """Permite al usuario seleccionar un archivo Excel/CSV/TXT e importa los IMEIs al cuadro de texto."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo de IMEIs (Excel / CSV / TXT)",
            filetypes=[
                ("Archivos de Datos", "*.xlsx;*.csv;*.tsv;*.txt"),
                ("Excel (*.xlsx)", "*.xlsx"),
                ("CSV / TSV (*.csv, *.tsv)", "*.csv;*.tsv"),
                ("Texto (*.txt)", "*.txt"),
                ("Todos los archivos", "*.*")
            ],
            parent=self
        )
        if not filepath:
            return

        imeis, modelo_detectado = extraer_imeis_y_modelo_de_archivo(filepath)
        if not imeis:
            messagebox.showwarning("Sin IMEIs", "No se encontraron números de IMEI válidos (15 dígitos) en el archivo seleccionado.", parent=self)
            return

        # Si el cuadro de texto tiene el placeholder, limpiarlo
        texto_actual = self.imeis_textbox.get("1.0", tk.END).strip()
        if texto_actual == self.placeholder_text:
            self.imeis_textbox.delete("1.0", tk.END)
            self.imeis_textbox.configure(text_color="#F8FAFC")

        # Insertar IMEIs importados
        self.imeis_textbox.insert(tk.END, "\n".join(imeis) + "\n")
        
        # Si se detectó un modelo y el campo Modelo está vacío, autocompletar
        if modelo_detectado and not self.modelo_var.get().strip():
            self.modelo_var.set(modelo_detectado)
            self.aprender_modelo_actual()

        self.actualizar_contador_imeis()
        self.schedule_preview_update()

        messagebox.showinfo("Importación Exitosa", f"Se importaron {len(imeis)} IMEIs correctamente desde:\n{os.path.basename(filepath)}", parent=self)

    def proc_importar_archivo(self):
        """Importa un archivo Excel/CSV/TXT directamente en la entrada del Procesador."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo para Procesador (Excel / CSV / TXT)",
            filetypes=[
                ("Archivos de Datos", "*.xlsx;*.csv;*.tsv;*.txt"),
                ("Excel (*.xlsx)", "*.xlsx"),
                ("CSV / TSV (*.csv, *.tsv)", "*.csv;*.tsv"),
                ("Texto (*.txt)", "*.txt"),
                ("Todos los archivos", "*.*")
            ],
            parent=self
        )
        if not filepath:
            return

        imeis, _ = extraer_imeis_y_modelo_de_archivo(filepath)
        if not imeis:
            messagebox.showwarning("Sin IMEIs", "No se encontraron IMEIs válidos en el archivo seleccionado.", parent=self)
            return

        self.proc_input_textbox.delete("1.0", tk.END)
        self.proc_input_textbox.insert("1.0", "\n".join(imeis))
        self.proc_input_textbox.configure(text_color="#F8FAFC")
        self.proc_extraer_imeis()
        messagebox.showinfo("Importación Exitosa", f"Se cargaron {len(imeis)} IMEIs en el Procesador.", parent=self)

    def proc_exportar_excel_csv(self):
        """Exporta la lista de IMEIs procesados a un archivo .csv o .txt delimitado por comas."""
        texto_salida = self.proc_output_textbox.get("1.0", tk.END).strip()
        if not texto_salida or "No se encontraron IMEIs válidos." in texto_salida:
            return

        imeis = [line.strip() for line in texto_salida.split("\n") if line.strip()]
        if not imeis:
            return

        filepath = filedialog.asksaveasfilename(
            title="Exportar IMEIs Procesados a Excel / CSV",
            defaultextension=".csv",
            filetypes=[("Archivo CSV (*.csv)", "*.csv"), ("Documento de Texto (*.txt)", "*.txt")],
            initialfile="imeis_procesados.csv",
            parent=self
        )
        if not filepath:
            return

        try:
            import csv, datetime
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            modelo = self.modelo_var.get().strip() or "General"

            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["No", "IMEI", "Modelo", "Fecha Registro"])
                for idx, imei in enumerate(imeis, 1):
                    writer.writerow([idx, f"'{imei}", modelo, now_str])

            messagebox.showinfo("Exportación Exitosa", f"Se exportaron {len(imeis)} IMEIs a:\n{os.path.basename(filepath)}", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Exportar", f"No se pudo exportar el archivo:\n{e}", parent=self)

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
        if hasattr(self, 'logo_enabled_var') and not self.logo_enabled_var.get():
            self.cached_logo_pil = None
            return

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

    def al_cambiar_switch_logo(self):
        """Maneja el evento de cambio en el switch para activar o desactivar el logo."""
        estado = self.logo_enabled_var.get()
        guardar_logo_enabled_config(estado)
        texto_estado = "Activado" if estado else "Desactivado"
        color_texto = "#10B981" if estado else "#64748B"

        if hasattr(self, 'logo_switch_bc'):
            self.logo_switch_bc.configure(text=texto_estado, text_color=color_texto)
        if hasattr(self, 'logo_switch_qr'):
            self.logo_switch_qr.configure(text=texto_estado, text_color=color_texto)

        self.cargar_y_cachear_logo()
        self.schedule_preview_update()

    def on_logo_path_change(self, *args):
        """Recarga el logo en caché y actualiza la previsualización."""
        self.cargar_y_cachear_logo()
        self.schedule_preview_update()

    def al_seleccionar_impresora(self, valor):
        """Callback al seleccionar una impresora de la lista."""
        guardar_impresora_config(valor)

    def buscar_logo(self):
        filepath = filedialog.askopenfilename(title="Seleccionar archivo de logo", filetypes=[("Archivos de Imagen", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*")])
        if filepath:
            self.logo_path_var.set(filepath)
            guardar_logo_config(filepath)  # Guardar la ruta del logo seleccionado

    def actualizar_estado_sumatra_ui(self):
        """Actualiza el texto y apariencia del botón de SumatraPDF según su disponibilidad."""
        if es_sumatra_configurado():
            self.config_sumatra_btn.configure(
                text="SumatraPDF: Detectado ✓",
                border_color="#10B981",
                text_color="#34D399",
                hover_color="#064E3B"
            )
        else:
            self.config_sumatra_btn.configure(
                text="SumatraPDF: No Detectado ⚠️",
                border_color="#F59E0B",
                text_color="#FBBF24",
                hover_color="#78350F"
            )

    def configurar_ruta_sumatra_manualmente(self):
        global SUMATRA_PDF_PATH
        if platform.system() != "Windows":
            messagebox.showinfo("Información", "La detección de SumatraPDF es solo para sistemas Windows.")
            return

        if es_sumatra_configurado():
            msg = (
                f"SumatraPDF está DETECTADO Y CONFIGURADO:\n\nRuta actual:\n{SUMATRA_PDF_PATH}\n\n"
                "• [Sí]: Seleccionar otra ruta de SumatraPDF ejecutable.\n"
                "• [No]: Re-buscar automáticamente en el sistema.\n"
                "• [Cancelar]: Mantener la ruta actual."
            )
            respuesta = messagebox.askyesnocancel("Estado de SumatraPDF", msg)
            if respuesta is None:
                return
            elif respuesta is False:
                SUMATRA_PDF_PATH = None
                detectado = detectar_sumatra_si_no_configurado()
                self.actualizar_estado_sumatra_ui()
                if detectado:
                    messagebox.showinfo("SumatraPDF Detectado", f"SumatraPDF ha sido detectado exitosamente en:\n{detectado}")
                else:
                    messagebox.showwarning("No Encontrado", "No se encontró SumatraPDF automáticamente. Selecciona el ejecutable manualmente.")
                return

        filepath = filedialog.askopenfilename(
            title="Localizar SumatraPDF.exe",
            filetypes=[("Ejecutable", "SumatraPDF.exe"), ("Ejecutables (*.exe)", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
            if os.path.basename(filepath).lower() == 'sumatrapdf.exe' or filepath.lower().endswith('.exe'):
                SUMATRA_PDF_PATH = filepath
                guardar_config_sumatra()
                self.actualizar_estado_sumatra_ui()
                messagebox.showinfo("Éxito", f"SumatraPDF configurado correctamente en:\n{filepath}")
            else:
                messagebox.showerror("Archivo Incorrecto", "Por favor selecciona el ejecutable SumatraPDF.exe.")
        self.actualizar_estado_sumatra_ui()

    def chequear_actualizaciones_async(self, manual=False):
        """Inicia el hilo para buscar actualizaciones."""
        if manual:
            self.btn_update.configure(text="Buscando...", fg_color="#334155", state="disabled")
        thread = threading.Thread(target=self._hilo_chequeo_actualizaciones, args=(manual,))
        thread.daemon = True
        thread.start()

    def _hilo_chequeo_actualizaciones(self, manual=False):
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
                self.after(100, lambda: self.btn_update.configure(text="¡Nueva act.!", fg_color="#EF4444", state="normal"))
                self.after(100, lambda: self.mostrar_dialogo_actualizacion(latest_version_tag, changelog_text, exe_url, exe_name, html_url))
            else:
                self.after(100, lambda: self.btn_update.configure(text="Al día", fg_color="#10B981", state="normal"))
                if manual:
                    self.after(200, lambda: messagebox.showinfo("Actualizado", f"Ya tienes la versión más reciente (v{VERSION})."))
        except Exception as e:
            print(f"Error al buscar actualizaciones en GitHub: {e}")
            self.after(100, lambda: self.btn_update.configure(text="Error", fg_color="#EF4444", state="normal"))
            if manual:
                self.after(200, lambda: messagebox.showerror("Error", f"No se pudo buscar actualizaciones:\n{e}"))
        finally:
            # Volver a programar el chequeo periódico cada 15 minutos (900,000 ms) mientras la app esté abierta
            self.after(900000, lambda: self.chequear_actualizaciones_async(manual=False))

    def accion_boton_actualizacion(self):
        """Maneja el clic en el botón de actualización según su estado actual."""
        if getattr(self, 'update_ready', False) and getattr(self, 'downloaded_new_exe', None):
            self.ejecutar_instalacion_inmediata()
        else:
            self.chequear_actualizaciones_async(manual=True)

    def chequear_actualizaciones_async(self, manual=False):
        """Inicia el chequeo de actualizaciones en un hilo secundario."""
        if getattr(self, 'update_ready', False):
            return  # Ya hay una versión descargada lista para instalar
        if manual:
            self.btn_update.configure(text="Buscando...", fg_color="#334155", state="disabled")
        
        thread = threading.Thread(target=self._buscar_actualizaciones_hilo, args=(manual,))
        thread.daemon = True
        thread.start()

    def _buscar_actualizaciones_hilo(self, manual):
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
            if not any(c.isdigit() for c in latest_version):
                release_title = data.get("name", "")
                if release_title:
                    latest_version_tag = release_title
                    latest_version = release_title.lstrip('v')
            current_ver = VERSION.lstrip('v')
            
            if parse_version(latest_version) > parse_version(current_ver):
                assets = data.get("assets", [])
                exe_url = None
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".exe"):
                        exe_url = asset.get("browser_download_url")
                        break
                
                if exe_url and getattr(sys, 'frozen', False):
                    # Iniciar descarga inline directamente (sin popup)
                    self.after(100, lambda: self.iniciar_descarga_inline(exe_url, latest_version_tag))
                else:
                    self.after(100, lambda: self.btn_update.configure(text="¡Nueva v" + latest_version + "!", fg_color="#EF4444", state="normal"))
            else:
                self.after(100, lambda: self.btn_update.configure(text="Al día", fg_color="#10B981", state="normal"))
                if manual:
                    self.after(200, lambda: messagebox.showinfo("Actualizado", f"Ya tienes la versión más reciente (v{VERSION})."))
        except Exception as e:
            print(f"Error al buscar actualizaciones en GitHub: {e}")
            self.after(100, lambda: self.btn_update.configure(text="Buscar act.", fg_color="#334155", state="normal"))
            if manual:
                self.after(200, lambda: messagebox.showerror("Error", f"No se pudo buscar actualizaciones:\n{e}"))
        finally:
            self.after(900000, lambda: self.chequear_actualizaciones_async(manual=False))

    def iniciar_descarga_inline(self, exe_url, nueva_version_tag):
        """Inicia la descarga de la nueva versión mostrando la barra de progreso inline."""
        self.btn_update.configure(text="Descargando 0%", fg_color="#0284C7", state="disabled")
        self.update_progress.grid()  # Mostrar la barra de progreso inline
        self.update_progress.set(0)
        
        thread = threading.Thread(
            target=self._hilo_descarga_inline,
            args=(exe_url, nueva_version_tag)
        )
        thread.daemon = True
        thread.start()

    def _hilo_descarga_inline(self, exe_url, nueva_version_tag):
        try:
            temp_dir = tempfile.gettempdir()
            new_exe = os.path.join(temp_dir, f"mctools_update_{int(time.time())}.exe")
            
            req = urllib.request.Request(
                exe_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            
            with urllib.request.urlopen(req, timeout=45) as response:
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
                            self.after(0, lambda p=progreso, pct=porcentaje: self._actualizar_progreso_inline(p, pct))
            
            # Descarga completada 100%
            self.after(0, lambda: self._finalizar_descarga_inline(nueva_version_tag, new_exe))
            
        except Exception as e:
            print(f"Error en descarga inline: {e}")
            self.after(0, self._error_descarga_inline)

    def _actualizar_progreso_inline(self, progreso, porcentaje):
        self.update_progress.set(progreso)
        self.btn_update.configure(text=f"Descargando {porcentaje}%")

    def _finalizar_descarga_inline(self, nueva_version_tag, new_exe):
        self.update_progress.grid_remove()  # Ocultar barra de progreso
        self.update_ready = True
        self.downloaded_new_exe = new_exe
        self.btn_update.configure(
            text="✨ Instalar ahora", 
            fg_color="#10B981", 
            hover_color="#059669", 
            text_color="#FFFFFF",
            state="normal"
        )

    def _error_descarga_inline(self):
        self.update_progress.grid_remove()
        self.btn_update.configure(text="Buscar act.", fg_color="#334155", state="normal")

    def al_cerrar_aplicacion(self):
        """Intercepta el cierre de la aplicación. Si hay una actualización lista, la aplica automáticamente al salir."""
        if getattr(self, 'update_ready', False) and getattr(self, 'downloaded_new_exe', None) and os.path.exists(self.downloaded_new_exe):
            self.ejecutar_instalacion_inmediata()
        else:
            try:
                self.destroy()
            except Exception:
                pass
            os._exit(0)

    def ejecutar_instalacion_inmediata(self):
        """Ejecuta la sustitución del ejecutable utilizando el actualizador independiente (updater.exe)."""
        if not hasattr(self, 'downloaded_new_exe') or not self.downloaded_new_exe or not os.path.exists(self.downloaded_new_exe):
            messagebox.showerror("Error", "No se encontró el archivo de actualización listo para instalar.")
            return
            
        try:
            current_exe = sys.executable
            temp_dir = tempfile.gettempdir()
            new_exe = self.downloaded_new_exe
            current_pid = os.getpid()
            
            updater_exe_name = "updater.exe"
            updater_found = None
            
            # 1. Buscar updater.exe en bundle PyInstaller o directorio de instalación
            if getattr(sys, 'frozen', False):
                base_dir = getattr(sys, '_MEIPASS', os.path.dirname(current_exe))
                candidates = [
                    os.path.join(base_dir, updater_exe_name),
                    os.path.join(os.path.dirname(current_exe), updater_exe_name),
                    os.path.join(os.getcwd(), updater_exe_name)
                ]
                for cand in candidates:
                    if os.path.exists(cand):
                        updater_found = cand
                        break
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                cand_exe = os.path.join(script_dir, updater_exe_name)
                if os.path.exists(cand_exe):
                    updater_found = cand_exe

            if updater_found:
                # Copiar updater.exe a temp_dir para evitar bloqueos en el directorio original
                temp_updater = os.path.join(temp_dir, "mctools_updater.exe")
                try:
                    import shutil
                    shutil.copy2(updater_found, temp_updater)
                    updater_cmd_path = temp_updater
                except Exception:
                    updater_cmd_path = updater_found

                cmd = [
                    updater_cmd_path,
                    "--target", current_exe,
                    "--source", new_exe,
                    "--pid", str(current_pid)
                ]
                subprocess.Popen(cmd)
            else:
                # Si estamos en modo desarrollo o updater.exe no está compilado, intentar ejecutar updater.py
                script_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(current_exe)
                updater_py = os.path.join(script_dir, "updater.py")
                if os.path.exists(updater_py):
                    cmd = [
                        sys.executable,
                        updater_py,
                        "--target", current_exe if getattr(sys, 'frozen', False) else new_exe,
                        "--source", new_exe,
                        "--pid", str(current_pid)
                    ]
                    subprocess.Popen(cmd)
                else:
                    # Respaldo de emergencia mediante script batch
                    self._ejecutar_instalacion_bat_fallback(current_exe, new_exe, temp_dir)
                    return

            time.sleep(0.3)
            os._exit(0)
        except Exception as e:
            messagebox.showerror("Error de Instalación", f"No se pudo iniciar el actualizador (updater.exe):\n{e}")

    def _ejecutar_instalacion_bat_fallback(self, current_exe, new_exe, temp_dir):
        """Respaldo secundario mediante batch script en caso extremo de no contar con updater.exe."""
        try:
            bat_path = os.path.join(temp_dir, "mctools_updater.bat")
            vbs_path = os.path.join(temp_dir, "mctools_launcher.vbs")
            exe_basename = os.path.basename(current_exe)
            bat_lines = [
                "@echo off",
                ":wait_exit",
                "ping 127.0.0.1 -n 2 >nul",
                f'tasklist /FI "IMAGENAME eq {exe_basename}" 2>nul | find /I "{exe_basename}" >nul',
                "if not errorlevel 1 goto wait_exit",
                "ping 127.0.0.1 -n 3 >nul",
                ":retry_copy",
                f'copy /Y "{new_exe}" "{current_exe}" >nul 2>&1 || goto retry_copy',
                "ping 127.0.0.1 -n 2 >nul",
                f'start "" "{current_exe}"',
                "ping 127.0.0.1 -n 2 >nul",
                f'if exist "{vbs_path}" del /F /Q "{vbs_path}" >nul 2>&1',
                f'if exist "{new_exe}" del /F /Q "{new_exe}" >nul 2>&1',
                '(goto) 2>nul & del "%~f0" >nul 2>&1'
            ]
            with open(bat_path, 'w', encoding='cp1252') as f:
                f.write("\r\n".join(bat_lines))
            vbs_code = f'CreateObject("WScript.Shell").Run Chr(34) & "{bat_path}" & Chr(34), 0, False'
            with open(vbs_path, 'w', encoding='cp1252') as f:
                f.write(vbs_code)
            subprocess.Popen(['wscript.exe', vbs_path])
            time.sleep(0.3)
            os._exit(0)
        except Exception as e:
            messagebox.showerror("Error de Instalación", f"No se pudo iniciar la actualización:\n{e}")


if __name__ == "__main__":
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("blue")
    
    app = AppGeneradorEtiquetas()
    app.mainloop()
