# -*- coding: utf-8 -*-

"""
Generador de Etiquetas Yacelltech v3.3 (Modo Oscuro)
Aplicación de escritorio con interfaz moderna para crear e imprimir etiquetas.
Refactorizado con CustomTkinter para una apariencia oscura y mejorada.
Modificado por Micael.
Ajuste de altura de texto realizado.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader as ReportLabImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
import os
import qrcode
import subprocess
import tempfile
import json
from typing import Optional, Tuple, List, Dict
import webbrowser
import urllib.parse

# --- Dependencias opcionales para la previsualización ---
PDF_PREVIEW_ENABLED = False
try:
    import fitz  # PyMuPDF
    from PIL import Image
    PDF_PREVIEW_ENABLED = True
except ImportError:
    print("ADVERTENCIA: PyMuPDF o Pillow no están instalados. La vista previa integrada ha sido DESHABILITADA.")

# --- Constantes de Configuración ---
CONFIG_FILE = "etiqueta_config.json"
DEFAULT_ICON_PATH = "yacelltech_icon.ico"
DESTINATARIOS_FILE = "destinatarios_etiquetas.json"


class LabelApp(ctk.CTk):
    """
    Clase principal para la aplicación de generación de etiquetas, ahora usando CustomTkinter.
    """
    # --- Constantes de Diseño de Etiqueta (con ajuste de altura) ---
    LABEL_WIDTH_PT = 4 * inch
    LABEL_HEIGHT_PT = 3 * inch
    ETIQUETA_MARGEN_GENERAL_PT = 15
    # --- CAMBIO REALIZADO: Aumentado de 40 a 50 para bajar más el texto ---
    ETIQUETA_MARGEN_SUPERIOR_TEXTO_PT = 50 
    ETIQUETA_ESPACIO_NOMBRE_A_QR_SUPERIOR = 15
    ETIQUETA_FONT_TITULO_SIZE = 14
    ETIQUETA_FONT_DESTINATARIO_MAX_SIZE = 30
    ETIQUETA_FONT_DESTINATARIO_MIN_SIZE = 10
    ETIQUETA_FONT_QR_HELP_SIZE = 7
    ETIQUETA_FONT_QR_ERROR_SIZE = 8
    ETIQUETA_FONT_PRINCIPAL_BOLD = "Times-Bold"
    ETIQUETA_FONT_QR_HELPER = "Helvetica"
    ETIQUETA_FONT_QR_ERROR_FALLBACK = "Helvetica-Oblique"
    ETIQUETA_QR_SIZE_PT = 60
    ETIQUETA_ESPACIO_QR_A_TEXTO_AYUDA = 3
    ETIQUETA_MARGEN_INFERIOR_MINIMO = 10
    
    # --- Colores para el tema oscuro ---
    PREVIEW_BG_COLOR = "#FFFFFF" # El fondo de la preview simula papel blanco
    BUTTON_PRINT_COLOR = "#28A745"
    BUTTON_PRINT_HOVER_COLOR = "#218838"
    BUTTON_MANAGE_COLOR = "#1F6AA5"
    BUTTON_MANAGE_HOVER_COLOR = "#1A5A8E"
    BUTTON_DELETE_COLOR = "#DC3545"
    BUTTON_DELETE_HOVER_COLOR = "#C82333"


    def __init__(self):
        super().__init__()
        
        # --- Configuración de CustomTkinter ---
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Generador de Etiquetas Yacelltech v3.3")
        self.geometry("950x650")
        self.minsize(900, 600)

        self.sumatra_path: Optional[str] = "C:\\Program Files\\SumatraPDF\\SumatraPDF.exe"
        self._load_app_config()
        
        self.destinatarios_guardados: Dict[str, Dict[str, str]] = {}
        self._load_destinatarios()

        self.temp_files_to_delete_on_exit: List[str] = []
        self._preview_update_job: Optional[str] = None
        self.current_live_preview_photo: Optional[ctk.CTkImage] = None

        self._setup_icon()
        self._setup_ui()
        self._update_destinatarios_combobox()
        self._bind_events()
        
        self.entry_destinatario.focus_set()

        self._check_sumatra_initial()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        if PDF_PREVIEW_ENABLED:
            self.after(100, self.schedule_preview_update)

    def _setup_icon(self) -> None:
        if os.path.exists(DEFAULT_ICON_PATH):
            try:
                self.iconbitmap(DEFAULT_ICON_PATH)
            except tk.TclError as e:
                print(f"Advertencia al cargar el icono: {e}")

    # --- Métodos de carga y guardado (sin cambios lógicos) ---
    def _load_app_config(self) -> None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.sumatra_path = config.get("sumatra_path", self.sumatra_path)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error al leer el archivo de configuración '{CONFIG_FILE}': {e}")

    def _save_app_config(self) -> None:
        config_data = {"sumatra_path": self.sumatra_path}
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except IOError as e:
            messagebox.showerror("Error de Configuración", f"No se pudo guardar la configuración:\n{e}", parent=self)

    def _load_destinatarios(self) -> None:
        if os.path.exists(DESTINATARIOS_FILE):
            try:
                with open(DESTINATARIOS_FILE, 'r', encoding='utf-8') as f:
                    self.destinatarios_guardados = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: El archivo {DESTINATARIOS_FILE} está corrupto. Se creará uno nuevo.")
                self.destinatarios_guardados = {}

    def _save_destinatarios(self) -> None:
        try:
            with open(DESTINATARIOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.destinatarios_guardados, f, indent=4, ensure_ascii=False)
            self.status_bar.configure(text="Lista de destinatarios guardada.")
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo guardar la lista:\n{e}", parent=self)
            self.status_bar.configure(text="Error al guardar lista.")

    def _update_destinatarios_combobox(self):
        nombres = sorted(list(self.destinatarios_guardados.keys()))
        self.combobox_destinatarios.configure(values=nombres)
        if not nombres:
            self.combobox_destinatarios.set("")

    def _on_destinatario_selected(self, nombre_seleccionado: str):
        if nombre_seleccionado in self.destinatarios_guardados:
            datos = self.destinatarios_guardados[nombre_seleccionado]
            self.entry_destinatario.delete(0, tk.END)
            self.entry_destinatario.insert(0, datos.get("nombre_destinatario", nombre_seleccionado))
            self.entry_origen.delete(0, tk.END)
            self.entry_origen.insert(0, datos.get("origen", ""))
            self.entry_destino.delete(0, tk.END)
            self.entry_destino.insert(0, datos.get("destino", ""))
            self.status_bar.configure(text=f"Datos de '{nombre_seleccionado}' cargados.")
            # La actualización de la preview se hará al escribir o al seleccionar
            self.schedule_preview_update()

    def guardar_destinatario_actual(self):
        nombre_destinatario = self.entry_destinatario.get().strip()
        if not nombre_destinatario:
            messagebox.showwarning("Campo Vacío", "El campo 'Nombre del DESTINATARIO' no puede estar vacío.", parent=self)
            return

        dialog = ctk.CTkInputDialog(
            text="Ingresa un nombre clave para este destinatario:",
            title="Guardar Destinatario",
            entry_fg_color="#333",
            entry_text_color="#DDD",
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
            "origen": self.entry_origen.get().strip(),
            "destino": self.entry_destino.get().strip()
        }
        self._save_destinatarios()
        self._update_destinatarios_combobox()
        self.combobox_destinatarios.set(nombre_clave)
        self.status_bar.configure(text=f"Destinatario '{nombre_clave}' guardado.")

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
                self.clear_fields()
                self.status_bar.configure(text=f"Destinatario '{nombre_clave}' eliminado.")

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Frame de Controles (Izquierda) ---
        controls_frame = ctk.CTkFrame(self, width=320, corner_radius=10)
        controls_frame.grid(row=0, column=0, sticky="nswe", padx=10, pady=10)
        controls_frame.grid_propagate(False)

        # -- Gestión de Destinatarios --
        dest_management_frame = ctk.CTkFrame(controls_frame)
        dest_management_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkLabel(dest_management_frame, text="Gestión de Destinatarios", font=ctk.CTkFont(weight="bold")).pack(pady=(0,10))

        ctk.CTkLabel(dest_management_frame, text="Cargar Destinatario:").pack(anchor="w")
        self.combobox_destinatarios = ctk.CTkComboBox(dest_management_frame, state="readonly", command=self._on_destinatario_selected)
        self.combobox_destinatarios.pack(fill="x", pady=(0, 10))

        dest_buttons_frame = ctk.CTkFrame(dest_management_frame, fg_color="transparent")
        dest_buttons_frame.pack(fill="x")
        dest_buttons_frame.grid_columnconfigure((0,1), weight=1)

        self.btn_guardar_dest = ctk.CTkButton(dest_buttons_frame, text="Guardar Actual", command=self.guardar_destinatario_actual, fg_color=self.BUTTON_MANAGE_COLOR, hover_color=self.BUTTON_MANAGE_HOVER_COLOR)
        self.btn_guardar_dest.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_eliminar_dest = ctk.CTkButton(dest_buttons_frame, text="Eliminar", command=self.eliminar_destinatario_seleccionado, fg_color=self.BUTTON_DELETE_COLOR, hover_color=self.BUTTON_DELETE_HOVER_COLOR)
        self.btn_eliminar_dest.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # -- Campos de Entrada --
        fields_frame = ctk.CTkFrame(controls_frame)
        fields_frame.pack(pady=10, padx=10, fill="x", expand=True)
        
        ctk.CTkLabel(fields_frame, text="Nombre del DESTINATARIO:").pack(pady=(5, 2), anchor="w")
        self.entry_destinatario = ctk.CTkEntry(fields_frame)
        self.entry_destinatario.pack(pady=(0, 10), fill="x")
        
        ctk.CTkLabel(fields_frame, text="Ciudad/Dirección ORIGEN:").pack(pady=(5, 2), anchor="w")
        self.entry_origen = ctk.CTkEntry(fields_frame)
        self.entry_origen.pack(pady=(0, 5), fill="x")
        self.btn_open_gmaps_origen = ctk.CTkButton(fields_frame, text="Ver en Google Maps", command=lambda: self._open_gmaps("origen"), height=25, text_color="white")
        self.btn_open_gmaps_origen.pack(pady=(0, 10), anchor="e")

        ctk.CTkLabel(fields_frame, text="Ciudad/Dirección DESTINO:").pack(pady=(5, 2), anchor="w")
        self.entry_destino = ctk.CTkEntry(fields_frame)
        self.entry_destino.pack(pady=(0, 5), fill="x")
        self.btn_open_gmaps_destino = ctk.CTkButton(fields_frame, text="Ver en Google Maps", command=lambda: self._open_gmaps("destino"), height=25, text_color="white")
        self.btn_open_gmaps_destino.pack(pady=(0, 10), anchor="e")

        # -- Cantidad y Botones Principales --
        bottom_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        amount_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        amount_frame.pack(fill="x", pady=(5, 15))
        ctk.CTkLabel(amount_frame, text="Cantidad a imprimir:").pack(side="left", padx=(0, 5))
        self.entry_cantidad = ctk.CTkEntry(amount_frame, width=120)
        self.entry_cantidad.insert(0, "1")
        self.entry_cantidad.pack(side="left")

        buttons_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=5)
        buttons_frame.columnconfigure(0, weight=1)
        
        self.btn_print = ctk.CTkButton(buttons_frame, text="Imprimir Etiquetas", command=self.imprimir, fg_color=self.BUTTON_PRINT_COLOR, hover_color=self.BUTTON_PRINT_HOVER_COLOR, state="disabled")
        self.btn_print.grid(row=0, column=0, sticky="ew", padx=0)
        
        # --- Frame de Previsualización (Derecha) ---
        preview_container = ctk.CTkFrame(self, corner_radius=10)
        preview_container.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        preview_container.grid_columnconfigure(0, weight=1)
        preview_container.grid_rowconfigure(0, weight=1)

        preview_text = "Previsualización en vivo..." if PDF_PREVIEW_ENABLED else "Previsualización deshabilitada.\nInstala PyMuPDF y Pillow."
        self.live_preview_label = ctk.CTkLabel(preview_container, text=preview_text, fg_color=self.PREVIEW_BG_COLOR, text_color="black", corner_radius=8)
        self.live_preview_label.grid(sticky="nsew", padx=10, pady=10)

        # --- Barra de Estado y Créditos ---
        self.status_bar = ctk.CTkLabel(self, text="Listo.", anchor="w")
        self.status_bar.grid(row=1, column=0, sticky="w", padx=10, pady=(0,5))
        
        self.credits_label = ctk.CTkLabel(self, text="Hecho Por Micael  ", anchor="e", font=ctk.CTkFont(size=10, slant="italic"))
        self.credits_label.grid(row=1, column=1, sticky="e", padx=(0, 20), pady=(0,5))
        
        # --- Menú Superior (tk estándar) ---
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Configurar SumatraPDF...", command=self.prompt_for_sumatra_path)
        filemenu.add_separator()
        filemenu.add_command(label="Salir", command=self._on_closing)
        menubar.add_cascade(label="Archivo", menu=filemenu)
        self.configure(menu=menubar)

    def _bind_events(self) -> None:
        self.entry_destinatario.bind("<Return>", lambda e: self.entry_origen.focus_set())
        self.entry_origen.bind("<Return>", lambda e: self.entry_destino.focus_set())
        self.entry_destino.bind("<Return>", lambda e: self.entry_cantidad.focus_set())
        self.entry_cantidad.bind("<Return>", lambda e: self.imprimir() if self._validate_inputs() else None)
        
        # Vincular escritura en los campos a la actualización de la preview
        for entry in [self.entry_destinatario, self.entry_origen, self.entry_destino]:
            entry.bind("<KeyRelease>", self.schedule_preview_update)

    def _check_sumatra_initial(self) -> None:
        is_valid = self.sumatra_path and os.path.exists(self.sumatra_path)
        if is_valid:
            self.btn_print.configure(state="normal")
            self.status_bar.configure(text=f"SumatraPDF encontrado: {os.path.basename(self.sumatra_path or '')}")
        else:
            self.btn_print.configure(state="disabled")
            self.status_bar.configure(text="SumatraPDF no configurado. Vaya a Archivo > Configurar.")
            self.prompt_for_sumatra_path(initial_prompt=True)

    def prompt_for_sumatra_path(self, initial_prompt: bool = False) -> None:
        msg = ("SumatraPDF.exe no se encontró o la ruta no es válida.\n\n"
               "Por favor, localiza el archivo para poder imprimir.")
        if not initial_prompt:
            msg = f"Ruta actual de SumatraPDF:\n{self.sumatra_path or 'No configurada'}\n\nSeleccione una nueva ruta."
        
        if initial_prompt or messagebox.askokcancel("Configurar Impresora", msg, parent=self):
            initial_dir = os.path.dirname(self.sumatra_path) if self.sumatra_path and os.path.isdir(os.path.dirname(self.sumatra_path)) else "C:\\Program Files\\"
            new_path = filedialog.askopenfilename(
                title="Localizar SumatraPDF.exe",
                filetypes=[("Ejecutable", "SumatraPDF.exe"), ("Todos", "*.*")],
                initialdir=initial_dir,
                parent=self
            )
            if new_path and os.path.isfile(new_path):
                self.sumatra_path = new_path
                self._save_app_config()
                self.status_bar.configure(text=f"SumatraPDF configurado: {os.path.basename(new_path)}")
                self.btn_print.configure(state="normal")

    def schedule_preview_update(self, *args) -> None:
        if not PDF_PREVIEW_ENABLED: return
        if self._preview_update_job:
            self.after_cancel(self._preview_update_job)
        self._preview_update_job = self.after(400, self._update_live_preview)

    def _update_live_preview(self) -> None:
        if not PDF_PREVIEW_ENABLED: return
        if not self.live_preview_label.winfo_exists(): return
        self._preview_update_job = None
        
        destinatario_val = self.entry_destinatario.get().strip() or " "
        origen_val = self.entry_origen.get().strip() or " "
        destino_val = self.entry_destino.get().strip() or " "
        
        temp_pdf_path = None
        current_preview_qr_files = []

        try:
            fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="live_prev_")
            os.close(fd)
            
            qr_origen_path = self._create_temp_file_for_qr(origen_val, "qr_prev_orig_")
            if qr_origen_path: current_preview_qr_files.append(qr_origen_path)
            
            qr_destino_path = self._create_temp_file_for_qr(destino_val, "qr_prev_dest_")
            if qr_destino_path: current_preview_qr_files.append(qr_destino_path)

            c = canvas.Canvas(temp_pdf_path, pagesize=(self.LABEL_WIDTH_PT, self.LABEL_HEIGHT_PT))
            self._dibujar_etiqueta_en_canvas(
                c,
                destinatario_val, origen_val, destino_val,
                qr_origen_path, qr_destino_path,
                is_final_pdf=True # Lo cerramos dentro del método de dibujo
            )
            
            doc = fitz.open(temp_pdf_path)
            page = doc.load_page(0)
            
            self.update_idletasks()
            preview_w = self.live_preview_label.winfo_width() - 20
            preview_h = self.live_preview_label.winfo_height() - 20

            if preview_w <= 1 or preview_h <= 1:
                self.live_preview_label.configure(image=None, text="Área de preview muy pequeña.")
                return

            zoom_factor = min(preview_w / page.rect.width, preview_h / page.rect.height, 2.5) if page.rect.width > 0 else 1
            
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom_factor, zoom_factor), alpha=False)
            doc.close()
            
            img_pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            
            self.current_live_preview_photo = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(img_pil.width, img_pil.height))
            self.live_preview_label.configure(image=self.current_live_preview_photo, text="")
        
        except Exception as e:
            self.live_preview_label.configure(image=None, text=f"Error al generar preview:\n{str(e)[:100]}")
        finally:
            if temp_pdf_path and os.path.exists(temp_pdf_path): self._cleanup_temp_file(temp_pdf_path)
            for qr_file in current_preview_qr_files: self._cleanup_temp_file(qr_file)

    def _generar_google_maps_link(self, ubicacion_str: str) -> Optional[str]:
        if not ubicacion_str.strip(): return None
        # Simplificado para generar siempre un enlace de búsqueda
        query_encoded = urllib.parse.quote_plus(ubicacion_str)
        return f"https://www.google.com/maps/search/?api=1&query={query_encoded}"

    def _open_gmaps(self, tipo_ubicacion: str) -> None:
        ubicacion_str = (self.entry_origen.get() if tipo_ubicacion == "origen" else self.entry_destino.get()).strip()
        if not ubicacion_str:
            messagebox.showwarning("Entrada Vacía", f"El campo de {tipo_ubicacion} está vacío.", parent=self)
            return
        gmaps_link = self._generar_google_maps_link(ubicacion_str)
        if gmaps_link:
            try:
                webbrowser.open(gmaps_link)
                self.status_bar.configure(text=f"Abriendo Google Maps para {tipo_ubicacion}...")
            except Exception as e:
                messagebox.showerror("Error al Abrir Enlace", f"No se pudo abrir el enlace:\n{e}", parent=self)

    def _validate_inputs(self) -> Optional[Tuple[str, str, str, int]]:
        destinatario = self.entry_destinatario.get().strip()
        origen = self.entry_origen.get().strip()
        destino = self.entry_destino.get().strip()
        cantidad_str = self.entry_cantidad.get().strip()

        if not destinatario:
             messagebox.showerror("Campo Obligatorio", "El campo 'DESTINATARIO' es obligatorio.", parent=self)
             return None
        
        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0: raise ValueError("La cantidad debe ser positiva")
        except ValueError:
            messagebox.showerror("Error en Cantidad", "La cantidad debe ser un número entero mayor que cero.", parent=self)
            return None
            
        return destinatario, origen, destino, cantidad

    def clear_fields(self) -> None:
        self.entry_destinatario.delete(0, tk.END)
        self.entry_origen.delete(0, tk.END)
        self.entry_destino.delete(0, tk.END)
        self.entry_cantidad.delete(0, tk.END)
        self.entry_cantidad.insert(0, "1")
        self.combobox_destinatarios.set("")
        self.entry_destinatario.focus_set()
        self.status_bar.configure(text="Campos limpiados.")
        self.schedule_preview_update()

    def _generar_qr(self, ubicacion: str, output_path: str) -> bool:
        if not ubicacion.strip(): return False
        gmaps_link = self._generar_google_maps_link(ubicacion)
        if not gmaps_link: return False
        
        qr = qrcode.QRCode(version=1, box_size=3, border=1, error_correction=qrcode.ERROR_CORRECT_L)
        qr.add_data(gmaps_link)
        img = qr.make_image(fill_color="black", back_color="white")
        try:
            with open(output_path, 'wb') as f:
                img.save(f)
            return True
        except Exception as e:
            print(f"Error al guardar QR ({ubicacion}): {e}")
            return False

    def _ajustar_tamano_texto(self, texto: str, font_name: str, max_width: float, max_size: int, min_size: int) -> int:
        current_size = max_size
        while current_size >= min_size:
            if stringWidth(texto, font_name, current_size) <= max_width:
                return current_size
            current_size -= 1
        return min_size

    # --- Métodos de dibujo y generación de PDF (sin cambios lógicos) ---
    def _dibujar_etiqueta_en_canvas(self, c: canvas.Canvas, 
                                 nombre_destinatario_data: str, origen_data: str, destino_data: str,
                                 qr_origen_path: Optional[str], qr_destino_path: Optional[str],
                                 is_final_pdf: bool = False):
        try:
            y_actual = self.LABEL_HEIGHT_PT - self.ETIQUETA_MARGEN_SUPERIOR_TEXTO_PT
            c.setFont(self.ETIQUETA_FONT_PRINCIPAL_BOLD, self.ETIQUETA_FONT_TITULO_SIZE)
            c.drawCentredString(self.LABEL_WIDTH_PT / 2, y_actual, "DESTINATARIO:")
            
            y_actual -= (10 + self.ETIQUETA_FONT_TITULO_SIZE * 0.9)
            nombre_destinatario_upper = nombre_destinatario_data.upper()
            max_ancho_nombre = self.LABEL_WIDTH_PT - (2 * self.ETIQUETA_MARGEN_GENERAL_PT)
            tam_fuente_destinatario = self._ajustar_tamano_texto(
                nombre_destinatario_upper, self.ETIQUETA_FONT_PRINCIPAL_BOLD, max_ancho_nombre,
                self.ETIQUETA_FONT_DESTINATARIO_MAX_SIZE, self.ETIQUETA_FONT_DESTINATARIO_MIN_SIZE
            )
            c.setFont(self.ETIQUETA_FONT_PRINCIPAL_BOLD, tam_fuente_destinatario)
            y_actual -= (tam_fuente_destinatario * 0.9)
            c.drawCentredString(self.LABEL_WIDTH_PT / 2, y_actual, nombre_destinatario_upper)
            
            y_superior_qrs = y_actual - (tam_fuente_destinatario * 0.3) - self.ETIQUETA_ESPACIO_NOMBRE_A_QR_SUPERIOR
            y_base_qrs = y_superior_qrs - self.ETIQUETA_QR_SIZE_PT
            y_texto_ayuda = y_base_qrs - self.ETIQUETA_ESPACIO_QR_A_TEXTO_AYUDA
            
            qr_origen_x = self.ETIQUETA_MARGEN_GENERAL_PT
            qr_destino_x = self.LABEL_WIDTH_PT - self.ETIQUETA_MARGEN_GENERAL_PT - self.ETIQUETA_QR_SIZE_PT

            if qr_origen_path and os.path.exists(qr_origen_path): 
                c.drawImage(ReportLabImageReader(qr_origen_path), qr_origen_x, y_base_qrs, width=self.ETIQUETA_QR_SIZE_PT, height=self.ETIQUETA_QR_SIZE_PT, mask='auto')
                c.setFont(self.ETIQUETA_FONT_QR_HELPER, self.ETIQUETA_FONT_QR_HELP_SIZE)
                c.drawCentredString(qr_origen_x + self.ETIQUETA_QR_SIZE_PT / 2, y_texto_ayuda, "Escanear para ver origen")
            
            if qr_destino_path and os.path.exists(qr_destino_path): 
                c.drawImage(ReportLabImageReader(qr_destino_path), qr_destino_x, y_base_qrs, width=self.ETIQUETA_QR_SIZE_PT, height=self.ETIQUETA_QR_SIZE_PT, mask='auto')
                c.setFont(self.ETIQUETA_FONT_QR_HELPER, self.ETIQUETA_FONT_QR_HELP_SIZE)
                c.drawCentredString(qr_destino_x + self.ETIQUETA_QR_SIZE_PT / 2, y_texto_ayuda, "Escanear para ver destino")

            if is_final_pdf:
                c.showPage()
                c.save()
        except Exception as e:
            print(f"Error dibujando etiqueta: {e}") 
            if is_final_pdf:
                try: c.save() 
                except: pass
            raise

    def _create_temp_file_for_qr(self, data: str, prefix: str) -> Optional[str]:
        if not data.strip(): return None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".png", prefix=prefix)
            os.close(fd)
            if self._generar_qr(data, temp_path):
                return temp_path
            else:
                self._cleanup_temp_file(temp_path)
                return None
        except Exception as e:
            print(f"Error creando archivo temporal para QR: {e}")
            return None

    def imprimir(self) -> None:
        validated_data = self._validate_inputs()
        if not validated_data: return
        
        destinatario, origen, destino, cantidad = validated_data
        
        if not self.sumatra_path or not os.path.exists(self.sumatra_path):
            self.prompt_for_sumatra_path()
            if not self.sumatra_path or not os.path.exists(self.sumatra_path): return

        fd, pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="lbl_print_")
        os.close(fd)
        self.temp_files_to_delete_on_exit.append(pdf_path)
        
        qr_origen_path = self._create_temp_file_for_qr(origen, "qr_p_o_")
        if qr_origen_path: self.temp_files_to_delete_on_exit.append(qr_origen_path)
        
        qr_destino_path = self._create_temp_file_for_qr(destino, "qr_p_d_")
        if qr_destino_path: self.temp_files_to_delete_on_exit.append(qr_destino_path)
        
        try:
            self.status_bar.configure(text=f"Generando PDF con {cantidad} etiqueta(s)...")
            self.update_idletasks()
            c = canvas.Canvas(pdf_path, pagesize=(self.LABEL_WIDTH_PT, self.LABEL_HEIGHT_PT))
            
            for _ in range(cantidad):
                self._dibujar_etiqueta_en_canvas(c, destinatario, origen, destino, qr_origen_path, qr_destino_path)
                c.showPage()
            
            c.save()
            
            if os.path.getsize(pdf_path) > 0:
                self._imprimir_con_sumatra(pdf_path, cantidad)
            else:
                messagebox.showerror("Error", "El PDF para imprimir está vacío.", parent=self)

        except Exception as e:
            messagebox.showerror("Error de Impresión", f"Ocurrió un error general:\n{e}", parent=self)

    def _imprimir_con_sumatra(self, pdf_path: str, cantidad: int) -> None:
        self.status_bar.configure(text=f"Enviando {cantidad} etiqueta(s) a la impresora...")
        self.update_idletasks()
        try:
            command = [self.sumatra_path, "-print-to-default", "-silent", "-exit-when-done", pdf_path]
            subprocess.Popen(command)
            self.status_bar.configure(text=f"Documento enviado. Verifique la impresora.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al intentar imprimir:\n{e}", parent=self)

    def _cleanup_temp_file(self, file_path: Optional[str]) -> None:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except (OSError, PermissionError) as e:
                print(f"ADVERTENCIA: No se pudo eliminar '{file_path}'. Error: {e}")

    def _on_closing(self) -> None:
        self._save_app_config()
        self._save_destinatarios()
        
        for temp_file in self.temp_files_to_delete_on_exit:
            self._cleanup_temp_file(temp_file)

        self.destroy()

if __name__ == "__main__":
    app = LabelApp()
    app.mainloop()
