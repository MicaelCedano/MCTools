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

# --- Constantes ---
VERSION = "2.0"
REPO_OWNER = "MicaelCedano"
REPO_NAME = "EtiquetaPro"
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
def _generar_etiqueta_pil_image(modelo, numero_serie, especificacion, path_logo_pil):
    """Genera la etiqueta como una imagen PIL, replicando la lógica del PDF."""
    DPI = 300
    LABEL_WIDTH_PX, LABEL_HEIGHT_PX = int(LABEL_WIDTH_INCHES * DPI), int(LABEL_HEIGHT_INCHES * DPI)
    
    TOP_MARGIN_PX = int(0.20 * DPI)
    SIDE_MARGIN_PX = int(0.15 * DPI)
    BOTTOM_MARGIN_PX = int(0.20 * DPI)
    
    image = Image.new("RGB", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), "white")
    draw = ImageDraw.Draw(image)
    try:
        font_bold = ImageFont.truetype(FONT_BOLD_PATH_TTF, size=int(12 * DPI / 72))
        font_regular = ImageFont.truetype(FONT_REGULAR_PATH_TTF, size=int(10 * DPI / 72))
    except IOError:
        font_bold, font_regular = ImageFont.load_default(), ImageFont.load_default()
    
    current_y = TOP_MARGIN_PX
    
    # 1. Logo
    if path_logo_pil and os.path.exists(path_logo_pil):
        try:
            with Image.open(path_logo_pil) as logo_img:
                logo_img = logo_img.convert("RGBA")
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

            sn_font = ImageFont.truetype(FONT_REGULAR_PATH_TTF, size=int(9 * DPI / 72))
            sn_text_w = draw.textlength(numero_serie, font=sn_font)
            
            bc_x = (LABEL_WIDTH_PX - barcode_pil.width) // 2
            image.paste(barcode_pil, (bc_x, current_y))
            current_y += barcode_pil.height + int(0.03 * DPI)

            sn_x = (LABEL_WIDTH_PX - sn_text_w) // 2
            draw.text((sn_x, current_y), numero_serie, fill="black", font=sn_font)
        except Exception as e:
            print(f"Error generando código de barras en previsualización: {e}")
            
    return image

# --- FUNCIÓN DE GENERACIÓN DE PDF (REVISADA Y SECUENCIAL) ---
def _generar_etiqueta_pdf_temporal(modelo, numero_serie, especificacion, path_logo_pil):
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

    # 3. Dibujar Código de Barras (Sin 'if' de espacio)
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

class VentanaProgresoActualizacion(customtkinter.CTkToplevel):
    def __init__(self, parent, version_nueva):
        super().__init__(parent)
        self.title("Actualizando EtiquetaPro")
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
        
        # Configuración Inicial
        self.title(f"Generador de Etiquetas iPhone v{VERSION}")
        self.geometry("860x520")
        self.minsize(860, 520)
        
        limpiar_archivos_antiguos()
        cargar_config_inicial()
        cargar_fuentes_pdf()
        
        # Configurar Grid Layout (2x1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Crear Frames
        self.controls_frame = customtkinter.CTkFrame(self, width=300, corner_radius=0)
        self.controls_frame.grid(row=0, column=0, sticky="nsw")
        self.controls_frame.grid_rowconfigure(2, weight=1)

        self.preview_frame = customtkinter.CTkFrame(self)
        self.preview_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self._setup_ui()
        self._bind_events()
        self.after(100, self.force_preview_update)
        self.after(2000, self.chequear_actualizaciones_async)

    def _setup_ui(self):
        # Frame de Controles (Izquierda)
        self.controls_frame.grid_columnconfigure(0, weight=1)
        
        # Variables
        self.modelo_var = tk.StringVar()
        self.imei_var = tk.StringVar()
        logo_path_inicial = cargar_logo_config()
        self.logo_path_var = tk.StringVar(value=logo_path_inicial)
        
        # Widgets de Entrada
        main_controls_frame = customtkinter.CTkFrame(self.controls_frame, fg_color="transparent")
        main_controls_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        main_controls_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(main_controls_frame, text="Modelo:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,2), sticky="w")
        modelo_entry_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        modelo_entry_frame.grid(row=1, column=0, padx=0, pady=(0,10), sticky="ew")
        modelo_entry_frame.grid_columnconfigure(0, weight=1)
        self.modelo_entry = customtkinter.CTkEntry(modelo_entry_frame, textvariable=self.modelo_var)
        self.modelo_entry.grid(row=0, column=0, padx=(0,5), sticky="ew")
        customtkinter.CTkButton(modelo_entry_frame, text="Pegar", width=60, command=self.pegar_modelo).grid(row=0, column=1, padx=0)

        customtkinter.CTkLabel(main_controls_frame, text="IMEI:", font=customtkinter.CTkFont(weight="bold")).grid(row=2, column=0, padx=0, pady=(0,2), sticky="w")
        imei_entry_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        imei_entry_frame.grid(row=3, column=0, padx=0, pady=(0,20), sticky="ew")
        imei_entry_frame.grid_columnconfigure(0, weight=1)
        self.imei_entry = customtkinter.CTkEntry(imei_entry_frame, textvariable=self.imei_var)
        self.imei_entry.grid(row=0, column=0, padx=(0,5), sticky="ew")
        customtkinter.CTkButton(imei_entry_frame, text="Pegar", width=60, command=self.pegar_imei).grid(row=0, column=1, padx=0)

        # Selección de Logo
        logo_frame = customtkinter.CTkFrame(main_controls_frame)
        logo_frame.grid(row=4, column=0, sticky='ew', pady=(0,20))
        logo_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(logo_frame, text="Ruta del Logo:").grid(row=0, column=0, columnspan=2, padx=10, pady=(5,2), sticky="w")
        customtkinter.CTkEntry(logo_frame, textvariable=self.logo_path_var).grid(row=1, column=0, padx=(10,5), pady=(0,10), sticky='ew')
        customtkinter.CTkButton(logo_frame, text="Buscar...", width=80, command=self.buscar_logo).grid(row=1, column=1, padx=(0,10), pady=(0,10))

        # Botones de Acción (PDF)
        pdf_buttons_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        pdf_buttons_frame.grid(row=5, column=0, sticky='ew')
        pdf_buttons_frame.grid_columnconfigure((0,1), weight=1)
        customtkinter.CTkButton(pdf_buttons_frame, text="Guardar PDF", command=self.generar_y_guardar_pdf).grid(row=0, column=0, padx=(0,5), sticky='ew')
        customtkinter.CTkButton(pdf_buttons_frame, text="Imprimir", command=self.imprimir).grid(row=0, column=1, padx=(5,0), sticky='ew')
        
        # Botón de Configuración
        customtkinter.CTkButton(self.controls_frame, text="Configurar SumatraPDF", command=self.configurar_ruta_sumatra_manualmente).grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        # Etiqueta de autor
        customtkinter.CTkLabel(self.controls_frame, text="Hecho por Micael  ", font=customtkinter.CTkFont(size=10, slant="italic"), text_color="gray50").grid(row=2, column=0, padx=20, pady=(10,10), sticky="sw")

        # Frame de Previsualización (Derecha)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_image_label = customtkinter.CTkLabel(self.preview_frame, text="La previsualización aparecerá aquí.", text_color="gray60")
        self.preview_image_label.grid(row=0, column=0, sticky="nsew")

    def _bind_events(self):
        for var in [self.modelo_var, self.imei_var, self.logo_path_var]:
            var.trace_add("write", self.schedule_preview_update)

    def schedule_preview_update(self, *args):
        if self._preview_update_job: self.after_cancel(self._preview_update_job)
        self._preview_update_job = self.after(50, self.force_preview_update)

    def force_preview_update(self):
        try:
            pil_image = _generar_etiqueta_pil_image(
                self.modelo_var.get().strip().upper(),
                self.imei_var.get().strip().upper(),
                "",
                self.logo_path_var.get().strip()
            )
            
            self.preview_ctk_image = customtkinter.CTkImage(
                light_image=pil_image,
                dark_image=pil_image,
                size=(PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT)
            )
            
            self.preview_image_label.configure(image=self.preview_ctk_image, text="")
        except Exception as e:
            self.preview_image_label.configure(image=None, text=f"Error en preview:\n{e}")

    def generar_y_guardar_pdf(self): self._procesar_generacion(guardar_permanente=True)
    def imprimir(self): self._procesar_generacion(imprimir_despues=True)

    def _procesar_generacion(self, guardar_permanente=False, imprimir_despues=False):
        if not PDF_SAVE_ENABLED:
            messagebox.showerror("Función Deshabilitada", "La librería 'ReportLab' es necesaria para esta función.")
            return
        modelo = self.modelo_var.get().strip().upper()
        imei = self.imei_var.get().strip().upper()
        if not modelo or not imei:
            messagebox.showerror("Campos Obligatorios", "'Modelo' e 'IMEI' son campos obligatorios.")
            return
        temp_pdf_path = _generar_etiqueta_pdf_temporal(
            modelo, imei,
            "",
            self.logo_path_var.get().strip()
        )
        if not temp_pdf_path or not os.path.exists(temp_pdf_path):
            messagebox.showerror("Error de Generación", "No se pudo crear el archivo PDF temporal.")
            return
        if guardar_permanente:
            path_salida = filedialog.asksaveasfilename(
                title="Guardar Etiqueta PDF",
                defaultextension=".pdf",
                initialfile=f"etiqueta_{modelo}_{imei}.pdf".replace(" ", "_"),
                filetypes=[("Archivos PDF", "*.pdf"), ("Todos", "*.*")]
            )
            if path_salida:
                try:
                    import shutil
                    shutil.move(temp_pdf_path, path_salida)
                    if temp_pdf_path in temporary_files_to_delete: temporary_files_to_delete.remove(temp_pdf_path)
                    messagebox.showinfo("Éxito", f"Etiqueta PDF guardada en:\n'{path_salida}'")
                except Exception as e: messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo:\n{e}")
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
                
                self.modelo_entry.delete(0, tk.END)  # Limpiar todo el contenido anterior
                self.modelo_entry.insert(0, texto_limpio)  # Insertar el contenido sin color
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")

    def pegar_imei(self):
        """Pega el contenido del portapapeles en el campo de IMEI, limpiando el contenido anterior."""
        try:
            contenido = self.clipboard_get()
            if contenido:
                self.imei_entry.delete(0, tk.END)  # Limpiar todo el contenido anterior
                self.imei_entry.insert(0, contenido.strip())  # Insertar el nuevo contenido
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")

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
                
                # Programar en el hilo principal de Tkinter
                self.after(100, lambda: self.mostrar_dialogo_actualizacion(latest_version_tag, exe_url, exe_name, html_url))
        except Exception as e:
            print(f"Error al buscar actualizaciones en GitHub: {e}")

    def mostrar_dialogo_actualizacion(self, nueva_version, exe_url, exe_name, html_url):
        """Muestra el diálogo informando de la nueva versión."""
        if getattr(sys, 'frozen', False) and exe_url:
            respuesta = messagebox.askyesno(
                "Actualización Disponible",
                f"¡Hay una nueva versión disponible ({nueva_version})!\n\n"
                "¿Deseas descargarla e instalarla automáticamente ahora mismo?"
            )
            if respuesta:
                self.iniciar_descarga_actualizacion(exe_url, exe_name, nueva_version)
        else:
            # Si no es un binario congelado, o no hay .exe asset, abrimos la página
            respuesta = messagebox.askyesno(
                "Actualización Disponible",
                f"¡Hay una nueva versión disponible ({nueva_version})!\n\n"
                "¿Deseas abrir la página de descargas en tu navegador?"
            )
            if respuesta:
                webbrowser.open(html_url)

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
