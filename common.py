# -*- coding: utf-8 -*-
"""
common.py — Módulo compartido para McTools
Consolida funciones duplicadas entre main.py, qr.py y destinatario.py
"""
import os
import sys
import json
import platform
import subprocess
import tempfile
import io
import atexit
import webbrowser
import urllib.parse
from typing import Optional, List

# --- Constantes Compartidas ---
CONFIG_FILE_NAME = "etiqueta_config.json"

# --- Variables Globales Compartidas ---
SUMATRA_PDF_PATH = None
temporary_files_to_delete = []

# --- Paths de Fuentes ---
FONT_BOLD_PATH = None
FONT_REGULAR_PATH = None

# --- Cache de fuentes PIL ---
_fuentes_pil_cache = {}


def _obtener_ruta_fuente(nombre_fuente):
    """Busca una fuente TTF primero local, luego en Windows/Fonts."""
    if os.path.exists(nombre_fuente):
        return nombre_fuente
    if platform.system() == "Windows":
        ruta_sistema = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", nombre_fuente)
        if os.path.exists(ruta_sistema):
            return ruta_sistema
    return nombre_fuente


def init_font_paths(font_bold="arialbd.ttf", font_regular="arial.ttf"):
    """Inicializa las rutas de fuentes globales."""
    global FONT_BOLD_PATH, FONT_REGULAR_PATH
    FONT_BOLD_PATH = _obtener_ruta_fuente(font_bold)
    FONT_REGULAR_PATH = _obtener_ruta_fuente(font_regular)


def obtener_fuente_pil(ruta_fuente, tamano):
    """Cache de fuentes PIL para evitar recargar TTF."""
    from PIL import ImageFont
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


def obtener_ruta_recurso(rel_path):
    """Obtiene ruta absoluta a un recurso, compatible con PyInstaller."""
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


def corregir_directorio_trabajo():
    """Corrige el directorio de trabajo al lado del .exe o script."""
    if getattr(sys, 'frozen', False):
        dir_path = os.path.dirname(sys.executable)
    else:
        dir_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(dir_path)


# --- Config JSON ---
def read_config() -> dict:
    """Lee el archivo de configuración JSON de forma segura."""
    if os.path.exists(CONFIG_FILE_NAME):
        with open(CONFIG_FILE_NAME, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def write_config(config_data: dict):
    """Escribe en el archivo de configuración JSON."""
    try:
        with open(CONFIG_FILE_NAME, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error al guardar configuración: {e}")


# --- SumatraPDF ---
def detectar_sumatra() -> Optional[str]:
    """Busca SumatraPDF en rutas comunes del sistema y registro."""
    global SUMATRA_PDF_PATH
    if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH):
        return SUMATRA_PDF_PATH
    if platform.system() != "Windows":
        return None

    user_profile = os.environ.get("USERPROFILE", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")
    current_exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()

    CANDIDATE_PATHS = [
        os.path.join(current_exe_dir, "SumatraPDF.exe"),
        os.path.join(local_app_data, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(program_files, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(program_files_x86, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(app_data, "SumatraPDF", "SumatraPDF.exe"),
        os.path.join(user_profile, "Downloads", "SumatraPDF.exe"),
        os.path.join(user_profile, "Desktop", "SumatraPDF.exe"),
        "C:\\SumatraPDF\\SumatraPDF.exe",
        "SumatraPDF.exe",
    ]

    for path_candidate in CANDIDATE_PATHS:
        if path_candidate and os.path.exists(path_candidate):
            SUMATRA_PDF_PATH = path_candidate
            print(f"SumatraPDF detectado en: {SUMATRA_PDF_PATH}")
            guardar_config_sumatra()
            return SUMATRA_PDF_PATH

    # Buscar en PATH
    try:
        result = subprocess.run(["where", "SumatraPDF.exe"], capture_output=True, text=True, check=False, shell=True)
        if result.returncode == 0 and result.stdout.strip():
            found_path = result.stdout.strip().splitlines()[0]
            if os.path.exists(found_path):
                SUMATRA_PDF_PATH = found_path
                print(f"SumatraPDF detectado en PATH: {SUMATRA_PDF_PATH}")
                guardar_config_sumatra()
                return SUMATRA_PDF_PATH
    except Exception:
        pass

    # Buscar en Registro de Windows
    try:
        import winreg
        keys_to_check = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\SumatraPDF.exe"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\SumatraPDF.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SumatraPDF"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\SumatraPDF"),
        ]
        for root_key, subkey in keys_to_check:
            try:
                with winreg.OpenKey(root_key, subkey) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.exists(val):
                        SUMATRA_PDF_PATH = val
                        print(f"SumatraPDF detectado en Registro: {SUMATRA_PDF_PATH}")
                        guardar_config_sumatra()
                        return SUMATRA_PDF_PATH
            except Exception:
                continue
    except Exception:
        pass

    return None


def es_sumatra_configurado() -> bool:
    """Retorna True si SumatraPDF está configurado y existe en disco."""
    global SUMATRA_PDF_PATH
    if SUMATRA_PDF_PATH and os.path.exists(SUMATRA_PDF_PATH):
        return True
    path = detectar_sumatra()
    return bool(path and os.path.exists(path))


def guardar_config_sumatra():
    """Guarda la ruta de SumatraPDF en la configuración."""
    global SUMATRA_PDF_PATH
    if SUMATRA_PDF_PATH and platform.system() == "Windows":
        config = read_config()
        config["sumatra_pdf_path"] = SUMATRA_PDF_PATH
        write_config(config)


def cargar_config_inicial():
    """Carga SumatraPDF desde config al inicio."""
    global SUMATRA_PDF_PATH
    config = read_config()
    path_guardado = config.get("sumatra_pdf_path")
    if path_guardado and os.path.exists(path_guardado):
        SUMATRA_PDF_PATH = path_guardado
        print(f"SumatraPDF cargado desde config: {SUMATRA_PDF_PATH}")
    else:
        detectar_sumatra()


# --- Logo Config ---
def cargar_logo_config(default_logo="logo.png") -> str:
    """Carga la ruta del logo guardada en configuración."""
    config = read_config()
    logo_path = config.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        return logo_path
    return default_logo


def guardar_logo_config(logo_path: str):
    """Guarda la ruta del logo en configuración."""
    if logo_path:
        config = read_config()
        config["logo_path"] = logo_path
        write_config(config)


def cargar_logo_enabled_config() -> bool:
    """Carga preferencia de logo activado/desactivado."""
    config = read_config()
    return config.get("logo_enabled", True)


def guardar_logo_enabled_config(enabled: bool):
    """Guarda preferencia de activación del logo."""
    config = read_config()
    config["logo_enabled"] = bool(enabled)
    write_config(config)


# --- Printer Config ---
def cargar_impresora_config() -> str:
    """Carga el nombre de la impresora guardada."""
    config = read_config()
    return config.get("printer_name", "")


def guardar_impresora_config(printer_name: str):
    """Guarda el nombre de la impresora."""
    config = read_config()
    config["printer_name"] = printer_name
    write_config(config)


# --- PIL -> Tk Image Converter ---
def pil_to_tk_image(pil_img, size=None):
    """
    Convierte PIL Image a objeto compatible con CustomTkinter/Tkinter.
    Fallback automático si PIL._imagingtk no está disponible.
    """
    if pil_img is None:
        return None
    try:
        from PIL import ImageTk
    except ImportError:
        ImageTk = None

    if size:
        img_resized = pil_img.resize(size, Image.Resampling.LANCZOS)
    else:
        img_resized = pil_img

    # Intentar CTkImage (CustomTkinter)
    try:
        import customtkinter
        return customtkinter.CTkImage(light_image=img_resized, dark_image=img_resized, size=img_resized.size)
    except Exception:
        pass

    # Intentar ImageTk.PhotoImage
    if ImageTk:
        try:
            return ImageTk.PhotoImage(img_resized)
        except Exception:
            pass

    # Fallback: tk.PhotoImage vía PNG en memoria
    try:
        buf = io.BytesIO()
        img_resized.save(buf, format="PNG")
        buf.seek(0)
        import tkinter as tk
        return tk.PhotoImage(data=buf.getvalue())
    except Exception:
        pass

    # Fallback final: PPM
    buf = io.BytesIO()
    img_resized.convert("RGB").save(buf, format="PPM")
    buf.seek(0)
    import tkinter as tk
    return tk.PhotoImage(data=buf.getvalue())


# --- Google Maps ---
def generar_google_maps_link(ubicacion_str: str) -> Optional[str]:
    """Genera un enlace de búsqueda de Google Maps."""
    if not ubicacion_str or not ubicacion_str.strip():
        return None
    query_encoded = urllib.parse.quote_plus(ubicacion_str.strip())
    return f"https://www.google.com/maps/search/?api=1&query={query_encoded}"


def abrir_google_maps(ubicacion_str: str) -> bool:
    """Abre Google Maps en el navegador para una ubicación."""
    link = generar_google_maps_link(ubicacion_str)
    if link:
        try:
            webbrowser.open(link)
            return True
        except Exception:
            pass
    return False


# --- Temp files cleanup ---
def cleanup_temp_files():
    """Elimina archivos temporales creados durante la sesión."""
    for temp_file_path in list(temporary_files_to_delete):
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if temp_file_path in temporary_files_to_delete:
                temporary_files_to_delete.remove(temp_file_path)
        except Exception as e:
            print(f"Error al limpiar archivo temporal {temp_file_path}: {e}")


atexit.register(cleanup_temp_files)
atexit.register(guardar_config_sumatra)


# --- Printing (direct via win32print) ---
def imprimir_pdf_directo(pdf_path: str, printer_name: str = "") -> bool:
    """
    Imprime un PDF directamente vía win32print sin SumatraPDF.
    Envía el raw PDF a la cola de impresión.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: archivo PDF no encontrado: {pdf_path}")
        return False
    try:
        import win32print
        import win32api
        printer_name = printer_name or win32print.GetDefaultPrinter()
        win32api.ShellExecute(
            0, "print", pdf_path,
            f'/d:"{printer_name}"',
            ".", 0
        )
        print(f"Enviado a imprimir en: {printer_name}")
        return True
    except Exception as e:
        print(f"Error al imprimir directamente: {e}")
        return False


def obtener_lista_impresoras() -> List[str]:
    """Enumera las impresoras instaladas en Windows."""
    if platform.system() == "Windows":
        try:
            import win32print
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            return [p[2] for p in printers]
        except Exception:
            return []
    return []


def obtener_impresora_predeterminada() -> str:
    """Obtiene el nombre de la impresora predeterminada."""
    if platform.system() == "Windows":
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return ""
    return ""
