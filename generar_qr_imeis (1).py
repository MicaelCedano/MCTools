# -*- coding: utf-8 -*-
"""
Generador de Etiquetas con QR para IMEIs
Versión: 1.0.0
Basado en: etiqueta_iphone_2025.py
"""
from PIL import Image, ImageDraw, ImageFont, ImageTk
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
CONFIG_FILE_NAME = "qr_imeis_config.json"
LABEL_WIDTH_INCHES = 4
LABEL_HEIGHT_INCHES = 3
PREVIEW_MAX_WIDTH = 380
PREVIEW_MAX_HEIGHT = int(PREVIEW_MAX_WIDTH * (LABEL_HEIGHT_INCHES / LABEL_WIDTH_INCHES))

# --- Rutas de Fuentes (Asegúrate de que estos archivos .ttf estén en la misma carpeta) ---
FONT_BOLD_PATH_TTF = "arialbd.ttf"
FONT_REGULAR_PATH_TTF = "arial.ttf"

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

def generar_texto_qr(imeis):
    """Genera el texto que se incluirá en el código QR con los IMEIs."""
    # Solo devolver los IMEIs, uno por línea, sin prefijos
    return "\n".join([imei.strip() for imei in imeis if imei.strip()])

# --- FUNCIÓN DE PREVISUALIZACIÓN ---
def _generar_etiqueta_pil_image(modelo, imeis, path_logo_pil):
    """Genera la etiqueta como una imagen PIL, replicando la lógica del PDF."""
    DPI = 300
    LABEL_WIDTH_PX, LABEL_HEIGHT_PX = int(LABEL_WIDTH_INCHES * DPI), int(LABEL_HEIGHT_INCHES * DPI)
    
    TOP_MARGIN_PX = int(0.20 * DPI)
    SIDE_MARGIN_PX = int(0.15 * DPI)
    BOTTOM_MARGIN_PX = int(0.25 * DPI)  # Aumentado para evitar que se corte el QR
    
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
                current_y += logo_img.height + int(0.15 * DPI)  # Aumentado de 0.1 a 0.15
        except Exception as e:
            print(f"Error procesando logo: {e}")

    # 2. Texto - Modelo con cantidad de equipos
    imeis_validos = [imei.strip() for imei in imeis if imei.strip()]
    cantidad_equipos = len(imeis_validos)
    
    if modelo.strip():
        texto_modelo = f"Modelo: {modelo} - QTY {cantidad_equipos}"
        
        # Calcular ancho disponible
        ancho_disponible = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
        
        # Verificar si el texto es demasiado largo y ajustar tamaño de fuente si es necesario
        texto_font = font_bold
        texto_largo = draw.textlength(texto_modelo, font=texto_font)
        
        # Si el texto es más largo que el ancho disponible, reducir tamaño de fuente
        if texto_largo > ancho_disponible:
            # Probar con tamaños menores hasta que quepa
            for size in [11, 10, 9, 8]:
                try:
                    font_ajustado = ImageFont.truetype(FONT_BOLD_PATH_TTF, size=int(size * DPI / 72))
                except IOError:
                    font_ajustado = ImageFont.load_default()
                
                texto_largo = draw.textlength(texto_modelo, font=font_ajustado)
                if texto_largo <= ancho_disponible:
                    texto_font = font_ajustado
                    break
        
        # Ajustar posición Y considerando la altura de las letras (ascendente)
        # Obtener el bbox del texto para calcular la altura real
        try:
            bbox = draw.textbbox((0, 0), texto_modelo, font=texto_font)
            altura_texto = bbox[3] - bbox[1]  # altura real del texto
            # Ajustar current_y para que el texto tenga espacio arriba
            current_y += int(0.1 * DPI)  # Espacio adicional antes del texto
        except:
            altura_texto = texto_font.size
            current_y += int(0.1 * DPI)
        
        # Centrar y dibujar el texto
        x_pos = (LABEL_WIDTH_PX - draw.textlength(texto_modelo, font=texto_font)) // 2
        draw.text((x_pos, current_y), texto_modelo, fill="black", font=texto_font)
        current_y += altura_texto + int(0.05 * DPI)  # Usar altura real + pequeño espacio

    # 3. Código QR
    if imeis_validos:
        try:
            padding_before_qr = int(0.05 * DPI)
            current_y += padding_before_qr
            
            # Calcular espacio disponible verticalmente (asegurando margen inferior)
            espacio_disponible_y = LABEL_HEIGHT_PX - current_y - BOTTOM_MARGIN_PX
            
            # Generar texto para el QR
            texto_qr = generar_texto_qr(imeis_validos)
            
            # Crear el código QR con ajuste automático de versión
            qr = qrcode.QRCode(
                version=None,  # Auto-detect version
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,  # Tamaño base razonable
                border=4,
            )
            
            qr.add_data(texto_qr)
            qr.make(fit=True)
            
            # Crear la imagen del QR
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert('RGB')
            
            # Calcular dimensiones máximas disponibles
            max_qr_w = LABEL_WIDTH_PX - 2 * SIDE_MARGIN_PX
            # Asegurar que el QR quepa completamente con margen de seguridad
            max_qr_h = espacio_disponible_y - int(0.05 * DPI)  # Margen de seguridad adicional
            
            # Calcular ratio para ajustar tanto ancho como alto
            ratio_w = max_qr_w / qr_img.width if qr_img.width > max_qr_w else 1.0
            ratio_h = max_qr_h / qr_img.height if qr_img.height > max_qr_h else 1.0
            ratio = min(ratio_w, ratio_h)  # Usar el ratio más pequeño para mantener proporción
            
            # Redimensionar el QR
            new_width = int(qr_img.width * ratio)
            new_height = int(qr_img.height * ratio)
            qr_img = qr_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Verificar que el QR no se salga de los límites
            if current_y + qr_img.height > LABEL_HEIGHT_PX - BOTTOM_MARGIN_PX:
                # Si se sale, reducir más el tamaño
                espacio_real = LABEL_HEIGHT_PX - current_y - BOTTOM_MARGIN_PX
                ratio_ajuste = espacio_real / qr_img.height
                new_width = int(new_width * ratio_ajuste)
                new_height = int(new_height * ratio_ajuste)
                qr_img = qr_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Centrar el QR
            qr_x = (LABEL_WIDTH_PX - qr_img.width) // 2
            image.paste(qr_img, (qr_x, current_y))
            
        except Exception as e:
            print(f"Error generando código QR en previsualización: {e}")
            
    return image

# --- FUNCIÓN DE GENERACIÓN DE PDF ---
def _generar_etiqueta_pdf_temporal(modelo, imeis, path_logo_pil):
    if not PDF_SAVE_ENABLED: return None
    fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="etiqueta_qr_")
    os.close(fd)
    temporary_files_to_delete.append(temp_pdf_path)
    
    c = reportlab_canvas.Canvas(temp_pdf_path, pagesize=(LABEL_WIDTH_INCHES * inch, LABEL_HEIGHT_INCHES * inch))
    width, height = LABEL_WIDTH_INCHES * inch, LABEL_HEIGHT_INCHES * inch
    
    # Márgenes
    margin_top = 0.20 * inch
    margin_sides = 0.15 * inch
    margin_bottom = 0.25 * inch  # Aumentado para evitar que se corte el QR
    
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
            current_y -= 0.15 * inch  # Aumentado de 0.1 a 0.15
    except Exception as e:
        print(f"Error al procesar logo para PDF: {e}")

    # 2. Dibujar Texto - Modelo con cantidad de equipos
    imeis_validos = [imei.strip() for imei in imeis if imei.strip()]
    cantidad_equipos = len(imeis_validos)
    
    if modelo.strip():
        texto_modelo = f"Modelo: {modelo} - QTY {cantidad_equipos}"
        
        # Calcular ancho disponible
        ancho_disponible = width - (2 * margin_sides)
        
        # Determinar tamaño de fuente apropiado
        font_size = 12
        c.setFont(RL_FONT_BOLD_NAME, font_size)
        texto_largo = c.stringWidth(texto_modelo, RL_FONT_BOLD_NAME, font_size)
        
        # Si el texto es demasiado largo, reducir tamaño de fuente
        if texto_largo > ancho_disponible:
            for size in [11, 10, 9, 8]:
                texto_largo = c.stringWidth(texto_modelo, RL_FONT_BOLD_NAME, size)
                if texto_largo <= ancho_disponible:
                    font_size = size
                    break
        
        # Ajustar posición Y para dar espacio arriba al texto
        # En ReportLab, la coordenada Y es desde abajo, y el texto se dibuja desde la línea base
        current_y -= 0.1 * inch  # Espacio adicional antes del texto
        current_y -= font_size  # Espacio para la altura de la fuente
        
        c.setFont(RL_FONT_BOLD_NAME, font_size)
        c.drawCentredString(width / 2, current_y, texto_modelo)
        current_y -= 0.05 * inch  # Pequeño espacio después del texto

    # 3. Dibujar Código QR
    if imeis_validos:
        try:
            current_y -= 0.05 * inch
            
            # Calcular espacio disponible verticalmente (asegurando margen inferior)
            espacio_disponible_y = current_y - margin_bottom
            
            # Generar texto para el QR
            texto_qr = generar_texto_qr(imeis_validos)
            
            # Crear el código QR con ajuste automático de versión
            qr = qrcode.QRCode(
                version=None,  # Auto-detect version
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,  # Tamaño base razonable
                border=4,
            )
            
            qr.add_data(texto_qr)
            qr.make(fit=True)
            
            # Crear la imagen del QR
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert('RGB')
            
            # Guardar QR en buffer para PDF
            qr_io = io.BytesIO()
            qr_img.save(qr_io, format='PNG')
            qr_io.seek(0)
            
            img_reader = ReportLabImageReader(qr_io)
            qr_w, qr_h = img_reader.getSize()
            
            # Calcular dimensiones máximas disponibles
            max_qr_w = width - (2 * margin_sides)
            # Asegurar que el QR quepa completamente con margen de seguridad
            max_qr_h_pt = espacio_disponible_y - (0.05 * inch)  # Margen de seguridad adicional
            
            # Calcular ratio para ajustar tanto ancho como alto
            ratio_w = max_qr_w / qr_w if qr_w > max_qr_w else 1.0
            ratio_h = max_qr_h_pt / qr_h if qr_h > max_qr_h_pt else 1.0
            ratio = min(ratio_w, ratio_h)  # Usar el ratio más pequeño para mantener proporción
            
            # Ajustar dimensiones
            qr_w, qr_h = qr_w * ratio, qr_h * ratio
            
            # Verificar que el QR no se salga de los límites
            if current_y - qr_h < margin_bottom:
                # Si se sale, reducir más el tamaño
                espacio_real = current_y - margin_bottom
                ratio_ajuste = espacio_real / qr_h
                qr_w, qr_h = qr_w * ratio_ajuste, qr_h * ratio_ajuste
            
            # Dibujar QR
            current_y -= qr_h
            c.drawImage(img_reader, (width - qr_w) / 2, current_y, width=qr_w, height=qr_h, mask='auto')

        except Exception as e:
            print(f"Error generando código QR para PDF: {e}")
            
    c.save()
    return temp_pdf_path

# --- Clase Principal de la Aplicación ---
class AppGeneradorEtiquetas(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.preview_ctk_image = None
        self._preview_update_job = None
        
        # Configuración Inicial
        self.title("Generador de Etiquetas con QR para IMEIs")
        self.geometry("860x720")
        self.minsize(860, 720)
        
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

    def _setup_ui(self):
        # Frame de Controles (Izquierda)
        self.controls_frame.grid_columnconfigure(0, weight=1)
        
        # Variables
        self.modelo_var = tk.StringVar()
        logo_path_inicial = cargar_logo_config()
        self.logo_path_var = tk.StringVar(value=logo_path_inicial)
        
        # Widgets de Entrada
        main_controls_frame = customtkinter.CTkFrame(self.controls_frame, fg_color="transparent")
        main_controls_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        main_controls_frame.grid_columnconfigure(0, weight=1)

        # Campo Modelo
        customtkinter.CTkLabel(main_controls_frame, text="Modelo:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=0, pady=(0,2), sticky="w")
        modelo_entry_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        modelo_entry_frame.grid(row=1, column=0, padx=0, pady=(0,10), sticky="ew")
        modelo_entry_frame.grid_columnconfigure(0, weight=1)
        self.modelo_entry = customtkinter.CTkEntry(modelo_entry_frame, textvariable=self.modelo_var)
        self.modelo_entry.grid(row=0, column=0, padx=(0,5), sticky="ew")
        customtkinter.CTkButton(modelo_entry_frame, text="Pegar", width=60, command=self.pegar_modelo).grid(row=0, column=1, padx=0)

        # Cuadro de texto para IMEIs
        imeis_label_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        imeis_label_frame.grid(row=2, column=0, padx=0, pady=(0,2), sticky="ew")
        imeis_label_frame.grid_columnconfigure(0, weight=1)
        
        customtkinter.CTkLabel(imeis_label_frame, text="IMEIs (uno por línea):", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        self.imeis_count_label = customtkinter.CTkLabel(imeis_label_frame, text="0 IMEIs", font=customtkinter.CTkFont(size=10), text_color="gray")
        self.imeis_count_label.grid(row=0, column=1, sticky="e")
        
        # Cuadro de texto grande para pegar todos los IMEIs
        self.imeis_textbox = customtkinter.CTkTextbox(main_controls_frame, height=300, font=customtkinter.CTkFont(size=11))
        self.imeis_textbox.grid(row=3, column=0, padx=0, pady=(0,10), sticky="ew")
        self.placeholder_text = "Pegue aquí todos los IMEIs, uno por línea..."
        self.imeis_textbox.insert("1.0", self.placeholder_text)
        self.imeis_textbox.configure(text_color="gray")
        
        # Botón para limpiar
        limpiar_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        limpiar_frame.grid(row=4, column=0, padx=0, pady=(0,10), sticky="ew")
        customtkinter.CTkButton(limpiar_frame, text="Limpiar IMEIs", width=100, command=self.limpiar_imeis).grid(row=0, column=0, sticky="w")
        customtkinter.CTkButton(limpiar_frame, text="Pegar IMEIs", width=100, command=self.pegar_imeis).grid(row=0, column=1, sticky="e")

        # Selección de Logo
        logo_frame = customtkinter.CTkFrame(main_controls_frame)
        logo_frame.grid(row=5, column=0, sticky='ew', pady=(0,20))
        logo_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkLabel(logo_frame, text="Ruta del Logo:").grid(row=0, column=0, columnspan=2, padx=10, pady=(5,2), sticky="w")
        customtkinter.CTkEntry(logo_frame, textvariable=self.logo_path_var).grid(row=1, column=0, padx=(10,5), pady=(0,10), sticky='ew')
        customtkinter.CTkButton(logo_frame, text="Buscar...", width=80, command=self.buscar_logo).grid(row=1, column=1, padx=(0,10), pady=(0,10))

        # Botones de Acción (PDF)
        pdf_buttons_frame = customtkinter.CTkFrame(main_controls_frame, fg_color="transparent")
        pdf_buttons_frame.grid(row=6, column=0, sticky='ew')
        pdf_buttons_frame.grid_columnconfigure(0, weight=1)
        customtkinter.CTkButton(pdf_buttons_frame, text="Imprimir", command=self.imprimir).grid(row=0, column=0, padx=0, sticky='ew')
        
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
        self.modelo_var.trace_add("write", self.schedule_preview_update)
        self.logo_path_var.trace_add("write", self.schedule_preview_update)
        # Bind para el cuadro de texto de IMEIs
        self.imeis_textbox.bind("<KeyRelease>", self.on_imeis_text_change)
        self.imeis_textbox.bind("<Button-1>", self.on_imeis_click)
        self.imeis_textbox.bind("<FocusIn>", self.on_imeis_focus_in)
    
    def on_imeis_click(self, event):
        """Elimina el placeholder cuando se hace clic en el cuadro."""
        texto = self.imeis_textbox.get("1.0", "end-1c")
        if texto.strip() == self.placeholder_text:
            self.imeis_textbox.delete("1.0", "end")
            self.imeis_textbox.configure(text_color=("gray10", "gray90"))
        self.schedule_preview_update()
    
    def on_imeis_focus_in(self, event):
        """Elimina el placeholder cuando se enfoca el cuadro."""
        texto = self.imeis_textbox.get("1.0", "end-1c")
        if texto.strip() == self.placeholder_text:
            self.imeis_textbox.delete("1.0", "end")
            self.imeis_textbox.configure(text_color=("gray10", "gray90"))
    
    def on_imeis_text_change(self, event):
        """Actualiza cuando cambia el texto."""
        texto = self.imeis_textbox.get("1.0", "end-1c")
        if texto.strip() == self.placeholder_text:
            self.imeis_textbox.configure(text_color="gray")
        else:
            self.imeis_textbox.configure(text_color=("gray10", "gray90"))
        self.schedule_preview_update()

    def schedule_preview_update(self, *args):
        if self._preview_update_job: self.after_cancel(self._preview_update_job)
        self._preview_update_job = self.after(50, self.force_preview_update)

    def obtener_imeis_del_texto(self):
        """Extrae los IMEIs del cuadro de texto, uno por línea."""
        texto = self.imeis_textbox.get("1.0", "end-1c")
        # Dividir por líneas y limpiar
        lineas = texto.split('\n')
        imeis = []
        for linea in lineas:
            imei = linea.strip()
            # Ignorar líneas vacías y el placeholder
            if imei and imei != "Pegue aquí todos los IMEIs, uno por línea...":
                imeis.append(imei)
        return imeis
    
    def actualizar_contador_imeis(self):
        """Actualiza el contador de IMEIs en la interfaz."""
        imeis = self.obtener_imeis_del_texto()
        count = len(imeis)
        self.imeis_count_label.configure(text=f"{count} IMEIs")
    
    def force_preview_update(self):
        try:
            imeis = self.obtener_imeis_del_texto()
            self.actualizar_contador_imeis()
            
            pil_image = _generar_etiqueta_pil_image(
                self.modelo_var.get().strip().upper(),
                imeis,
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

    def imprimir(self): self._procesar_generacion(imprimir_despues=True)

    def _procesar_generacion(self, guardar_permanente=False, imprimir_despues=False):
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
        
        temp_pdf_path = _generar_etiqueta_pdf_temporal(
            modelo,
            imeis,
            self.logo_path_var.get().strip()
        )
        if not temp_pdf_path or not os.path.exists(temp_pdf_path):
            messagebox.showerror("Error de Generación", "No se pudo crear el archivo PDF temporal.")
            return
        if guardar_permanente:
            path_salida = filedialog.asksaveasfilename(
                title="Guardar Etiqueta PDF",
                defaultextension=".pdf",
                initialfile=f"etiqueta_qr_{modelo}.pdf".replace(" ", "_"),
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
                # Lista de colores comunes de iPhone a eliminar
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
                    texto_limpio = texto_limpio.replace(color, "").strip()
                    while "  " in texto_limpio:
                        texto_limpio = texto_limpio.replace("  ", " ")
                
                self.modelo_entry.delete(0, tk.END)
                self.modelo_entry.insert(0, texto_limpio)
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")

    def limpiar_imeis(self):
        """Limpia el cuadro de texto de IMEIs."""
        self.imeis_textbox.delete("1.0", "end")
        self.imeis_textbox.insert("1.0", self.placeholder_text)
        self.imeis_textbox.configure(text_color="gray")
        self.actualizar_contador_imeis()
        self.schedule_preview_update()
    
    def pegar_imeis(self):
        """Pega el contenido del portapapeles en el cuadro de IMEIs."""
        try:
            contenido = self.clipboard_get()
            if contenido:
                self.imeis_textbox.delete("1.0", "end")
                self.imeis_textbox.insert("1.0", contenido.strip())
                self.imeis_textbox.configure(text_color=("gray10", "gray90"))
                self.actualizar_contador_imeis()
                self.schedule_preview_update()
        except tk.TclError:
            messagebox.showwarning("Portapapeles Vacío", "No hay contenido en el portapapeles para pegar.")
    
    def buscar_logo(self):
        filepath = filedialog.askopenfilename(title="Seleccionar archivo de logo", filetypes=[("Archivos de Imagen", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*")])
        if filepath:
            self.logo_path_var.set(filepath)
            guardar_logo_config(filepath)

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


if __name__ == "__main__":
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("blue")
    
    app = AppGeneradorEtiquetas()
    app.mainloop()
