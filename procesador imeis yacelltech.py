import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, font as tkfont
import os
import re
import pyperclip
import json
import datetime
from typing import List, Dict, Any, Callable # Agregado Callable

class IMEIHistoryWindow(tk.Toplevel):
    def __init__(self, parent, theme, on_select_callback):
        super().__init__(parent)
        self.title("Historial de IMEIs Procesados")
        self.geometry("550x450")
        self.resizable(False, False)
        self.theme = theme
        self.on_select_callback = on_select_callback
        
        self.transient(parent)
        self.grab_set()
        self.focus()
        
        self.configure(bg=theme["bg"])
        
        # Header
        header_frame = tk.Frame(self, bg=theme.get("status_bar_bg", "grey"), height=60)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        
        title_label = tk.Label(
            header_frame, 
            text="Historial de Procesos", 
            font=("Arial", 12, "bold"),
            bg=theme.get("status_bar_bg", "grey"),
            fg=theme.get("info_fg", "blue")
        )
        title_label.pack(pady=15, padx=20, side=tk.LEFT)
        
        # Scrollable Canvas frame
        self.canvas = tk.Canvas(self, bg=theme["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=theme["bg"])
        
        self.scrollable_frame_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.scrollable_frame_window, width=e.width))
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        self.scrollbar.pack(side="right", fill="y", pady=15)
        
        self.cargar_historial()

    def cargar_historial(self):
        # Limpiar frame
        for child in self.scrollable_frame.winfo_children():
            child.destroy()
            
        config = self.read_config()
        historial = config.get("imei_history", [])
        
        if not historial:
            no_history_label = tk.Label(
                self.scrollable_frame,
                text="No hay registros en el historial.",
                font=("Arial", 10, "italic"),
                bg=self.theme["bg"],
                fg=self.theme["label_fg"]
            )
            no_history_label.pack(pady=40)
            return
            
        for index, reg in enumerate(historial):
            # Tarjeta de registro
            card = tk.Frame(
                self.scrollable_frame,
                bg=self.theme["text_bg"],
                bd=1,
                relief=tk.SOLID
            )
            card.pack(fill=tk.X, pady=6, padx=5, ipady=5)
            
            # Textos de la tarjeta
            info_frame = tk.Frame(card, bg=self.theme["text_bg"])
            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=5)
            
            time_label = tk.Label(
                info_frame,
                text=reg.get("timestamp", "Fecha desconocida"),
                font=("Arial", 9, "bold"),
                bg=self.theme["text_bg"],
                fg=self.theme["label_fg"]
            )
            time_label.pack(anchor="w")
            
            detalles = f"IMEIs extraídos: {reg.get('count', 0)}"
            if reg.get("preview"):
                detalles += f" ({reg.get('preview')})"
                
            details_label = tk.Label(
                info_frame,
                text=detalles,
                font=("Arial", 9),
                bg=self.theme["text_bg"],
                fg=self.theme["text_fg"]
            )
            details_label.pack(anchor="w", pady=(2, 0))
            
            # Botones
            btn_frame = tk.Frame(card, bg=self.theme["text_bg"])
            btn_frame.pack(side=tk.RIGHT, padx=12, pady=5)
            
            importar_btn = tk.Button(
                btn_frame,
                text="Importar",
                font=("Arial", 9, "bold"),
                bg=self.theme.get("button_secondary_bg", "blue"),
                fg=self.theme.get("button_secondary_fg", "white"),
                activebackground=self.theme.get("button_active_bg", "darkgrey"),
                command=lambda r=reg: self.seleccionar_registro(r)
            )
            importar_btn.pack(side=tk.LEFT, padx=3)
            
            eliminar_btn = tk.Button(
                btn_frame,
                text="Borrar",
                font=("Arial", 9, "bold"),
                bg="red",
                fg="white",
                activebackground="darkred",
                command=lambda idx=index: self.eliminar_registro(idx)
            )
            eliminar_btn.pack(side=tk.LEFT, padx=3)

    def seleccionar_registro(self, registro):
        self.on_select_callback(registro.get("input_text", ""))
        self.grab_release()
        self.destroy()
        
    def eliminar_registro(self, index):
        config = self.read_config()
        historial = config.get("imei_history", [])
        if 0 <= index < len(historial):
            historial.pop(index)
            config["imei_history"] = historial
            self.write_config(config)
            self.cargar_historial()

    def read_config(self):
        if os.path.exists("etiqueta_config.json"):
            with open("etiqueta_config.json", 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except Exception:
                    return {}
        return {}

    def write_config(self, config_data):
        try:
            with open("etiqueta_config.json", 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Error al guardar configuración: {e}")

class IMEIProcessorApp:
    def __init__(self, parent_frame: ttk.Frame, main_app_instance: Any, update_save_menu_callback: Callable[[str], None]): # Añadido callback
        self.parent_frame = parent_frame
        self.main_app = main_app_instance
        self.root_toplevel = parent_frame.winfo_toplevel()
        self.update_save_menu_callback = update_save_menu_callback # Guardar el callback

        self.theme = self.main_app.current_theme_colors

        self.app_icon_photoimg = None
        self.omit_alternate_imeis_var = tk.BooleanVar(value=False)

        self._setup_ui()
        self.apply_theme_colors(self.theme)

    def _setup_ui(self):
        self.default_font = tkfont.nametofont("TkDefaultFont")
        self.default_font.configure(size=10)
        self.bold_font = tkfont.Font(family=self.default_font.cget("family"), size=10, weight="bold")

        self.input_frame = tk.Frame(self.parent_frame, pady=10)
        self.input_frame.pack(fill=tk.X, padx=10)
        self.input_label = tk.Label(self.input_frame, text="Pega aquí el texto del lector QR (o cualquier texto con IMEIs):")
        self.input_label.pack(side=tk.LEFT, padx=5)
        self.input_text_area = scrolledtext.ScrolledText(self.parent_frame, wrap=tk.WORD, height=10, width=70, font=self.default_font)
        self.input_text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.input_text_area.focus()

        self.options_actions_frame = tk.Frame(self.parent_frame)
        self.options_actions_frame.pack(pady=10)

        self.omit_imeis_checkbutton = tk.Checkbutton(
            self.options_actions_frame,
            text="Omitir IMEIs en posiciones pares (procesar 1°, 3°, 5°...)",
            variable=self.omit_alternate_imeis_var,
            command=self.process_and_display_imeis
        )
        self.omit_imeis_checkbutton.pack(side=tk.TOP, pady=(0,5), anchor="w")


        self.action_buttons_frame = tk.Frame(self.options_actions_frame)
        self.action_buttons_frame.pack(pady=5)

        self.process_button = tk.Button(self.action_buttons_frame, text="Extraer IMEIs Únicos",
                                         command=self.process_and_display_imeis, font=self.bold_font,
                                         relief=tk.RAISED, borderwidth=2)
        self.process_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = tk.Button(self.action_buttons_frame, text="Limpiar Todo",
                                       command=self.clear_all_fields, font=self.bold_font,
                                       relief=tk.RAISED, borderwidth=2)
        self.clear_button.pack(side=tk.LEFT, padx=5)

        self.history_button = tk.Button(self.action_buttons_frame, text="Ver Historial",
                                         command=self.show_history, font=self.bold_font,
                                         relief=tk.RAISED, borderwidth=2)
        self.history_button.pack(side=tk.LEFT, padx=5)

        self.output_frame = tk.Frame(self.parent_frame, pady=5)
        self.output_frame.pack(fill=tk.X, padx=10)
        self.output_label = tk.Label(self.output_frame, text="IMEIs únicos encontrados:")
        self.output_label.pack(side=tk.LEFT, padx=5)
        self.output_text_area = scrolledtext.ScrolledText(self.parent_frame, wrap=tk.WORD, height=10, width=70,
                                                           state=tk.DISABLED, font=self.default_font)
        self.output_text_area.pack(padx=10, pady=(0,5), fill=tk.BOTH, expand=True)

        self.imei_count_label = tk.Label(self.parent_frame, text="IMEIs únicos encontrados: 0", font=("Arial", 10, "italic"))
        self.imei_count_label.pack(pady=(5, 5))

        self.copy_button = tk.Button(self.parent_frame, text="Copiar IMEIs Únicos",
                                      command=self.copy_imeis_to_clipboard, state=tk.DISABLED,
                                      font=self.bold_font, relief=tk.RAISED, borderwidth=2)
        self.copy_button.pack(pady=(5, 10))

        self.status_label = tk.Label(self.parent_frame, text="Esperando entrada...", bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=5)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.themed_widgets = [
            self.input_frame, self.input_label, self.input_text_area,
            self.options_actions_frame, self.omit_imeis_checkbutton,
            self.action_buttons_frame, self.process_button, self.clear_button,
            self.history_button,
            self.output_frame, self.output_label, self.output_text_area,
            self.imei_count_label, self.copy_button, self.status_label
        ]

    def apply_theme_colors(self, theme: Dict[str, str]):
        self.theme = theme

        self.input_frame.config(bg=theme["bg"])
        self.input_label.config(bg=theme["bg"], fg=theme["label_fg"])
        self.input_text_area.config(bg=theme["text_bg"], fg=theme["text_fg"], insertbackground=theme["fg"])

        self.options_actions_frame.config(bg=theme["bg"])
        self.omit_imeis_checkbutton.config(
            bg=theme.get("checkbutton_bg", theme["bg"]),
            fg=theme.get("checkbutton_fg", theme["label_fg"]),
            selectcolor=theme.get("checkbutton_selectcolor", theme["text_bg"]),
            activebackground=theme.get("checkbutton_bg", theme["bg"]),
            activeforeground=theme.get("checkbutton_fg", theme["label_fg"])
        )

        self.action_buttons_frame.config(bg=theme["bg"])
        self.process_button.config(bg=theme["button_bg"], fg=theme["button_fg"], activebackground=theme["button_active_bg"])
        self.clear_button.config(bg=theme["button_clear_bg"], fg=theme["button_clear_fg"], activebackground=theme.get("button_clear_active_bg", theme["button_active_bg"]))
        self.history_button.config(bg=theme.get("button_secondary_bg", "blue"), fg=theme.get("button_secondary_fg", "white"), activebackground=theme.get("button_active_bg", "darkgrey"))

        self.output_frame.config(bg=theme["bg"])
        self.output_label.config(bg=theme["bg"], fg=theme["label_fg"])
        self.output_text_area.config(bg=theme["text_bg"], fg=theme["text_fg"])

        self.imei_count_label.config(bg=theme["bg"], fg=theme["label_fg"])
        self.copy_button.config(bg=theme["button_secondary_bg"], fg=theme["button_secondary_fg"], activebackground=theme.get("button_secondary_active_bg", theme["button_active_bg"]))

        self.status_label.config(bg=theme["status_bar_bg"])
        self.update_status_styling()


    def update_status_styling(self):
        theme = self.theme
        current_status_text = self.status_label.cget("text")
        if "listos para copiar" in current_status_text.lower() or "se encontraron" in current_status_text.lower() or "archivo cargado" in current_status_text.lower():
            self.status_label.config(fg=theme["success_fg"])
        elif "no se encontraron" in current_status_text.lower():
            self.status_label.config(fg=theme["error_fg"])
        elif "nada que copiar" in current_status_text.lower() or \
             "entrada vacía" in current_status_text.lower() or \
             "guardado cancelado" in current_status_text.lower() or \
             "importación cancelada" in current_status_text.lower() or \
             "error al leer archivo" in current_status_text.lower() or \
             "nada que guardar" in current_status_text.lower():
            self.status_label.config(fg=theme["warning_fg"])
        elif "copiados al portapapeles" in current_status_text.lower() or \
             "guardado" in current_status_text.lower() or \
             "campos limpiados" in current_status_text.lower():
            self.status_label.config(fg=theme["info_fg"])
        else:
            self.status_label.config(fg=theme["status_bar_fg"])


    def extract_imeis(self, text_data: str, omit_alternates: bool) -> List[str]:
        imei_pattern = r'\b\d{15}\b'
        all_imeis_found = re.findall(imei_pattern, text_data)

        processed_imeis = []
        if omit_alternates:
            for i, imei in enumerate(all_imeis_found):
                if i % 2 == 0:
                    processed_imeis.append(imei)
        else:
            processed_imeis = all_imeis_found

        unique_imeis_ordered = []
        seen_imeis = set()
        for imei in processed_imeis:
            if imei not in seen_imeis:
                unique_imeis_ordered.append(imei)
                seen_imeis.add(imei)
        return unique_imeis_ordered

    def process_and_display_imeis(self):
        input_text_content = self.input_text_area.get("1.0", tk.END)
        omit_option_active = self.omit_alternate_imeis_var.get()

        if not input_text_content.strip():
            self.imei_count_label.config(text="IMEIs únicos encontrados: 0")
            self.output_text_area.config(state=tk.NORMAL)
            self.output_text_area.delete("1.0", tk.END)
            self.output_text_area.config(state=tk.DISABLED)
            self.copy_button.config(state=tk.DISABLED)
            self.update_save_menu_callback(tk.DISABLED) # Usar callback
            self.status_label.config(text="Entrada vacía. Por favor, pega algún texto.")
            self.update_status_styling()
            return

        unique_extracted_imeis = self.extract_imeis(input_text_content, omit_option_active)

        self.output_text_area.config(state=tk.NORMAL)
        self.output_text_area.delete("1.0", tk.END)

        if unique_extracted_imeis:
            imeis_string = "\n".join(unique_extracted_imeis)
            self.output_text_area.insert(tk.END, imeis_string)
            self.copy_button.config(state=tk.NORMAL)
            self.update_save_menu_callback(tk.NORMAL) # Usar callback
            self.imei_count_label.config(text=f"IMEIs únicos encontrados: {len(unique_extracted_imeis)}")
            status_message = f"Se encontraron {len(unique_extracted_imeis)} IMEI(s) únicos."
            if omit_option_active:
                status_message += " (Omitiendo posiciones pares)"
            self.status_label.config(text=status_message + " Listos para copiar.")
            # Guardar en historial
            self.save_to_history(input_text_content, len(unique_extracted_imeis), unique_extracted_imeis)
        else:
            self.output_text_area.insert(tk.END, "No se encontraron IMEIs válidos.")
            self.copy_button.config(state=tk.DISABLED)
            self.update_save_menu_callback(tk.DISABLED) # Usar callback
            self.imei_count_label.config(text="IMEIs únicos encontrados: 0")
            status_message = "No se encontraron IMEIs válidos."
            if omit_option_active:
                status_message += " (Omitiendo posiciones pares)"
            self.status_label.config(text=status_message)

        self.update_status_styling()
        self.output_text_area.config(state=tk.DISABLED)

    def save_to_history(self, raw_text, count, unique_imeis):
        if not raw_text or raw_text.strip() == "":
            return
        
        # Generar un preview corto (primeros 3 IMEIs)
        preview = ", ".join(unique_imeis[:3])
        if len(unique_imeis) > 3:
            preview += "..."
            
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        nuevo_registro = {
            "timestamp": now_str,
            "input_text": raw_text,
            "count": count,
            "preview": preview
        }
        
        config = self.read_config_history()
        historial = config.get("imei_history", [])
        
        if historial and historial[0].get("input_text") == raw_text:
            return
            
        historial.insert(0, nuevo_registro)
        historial = historial[:10]
        
        config["imei_history"] = historial
        self.write_config_history(config)

    def read_config_history(self):
        if os.path.exists("etiqueta_config.json"):
            with open("etiqueta_config.json", 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except Exception:
                    return {}
        return {}

    def write_config_history(self, config_data):
        try:
            with open("etiqueta_config.json", 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Error al guardar configuración: {e}")

    def restore_from_history(self, raw_text):
        self.input_text_area.delete("1.0", tk.END)
        self.input_text_area.insert("1.0", raw_text)
        self.process_and_display_imeis()

    def show_history(self):
        if hasattr(self, 'history_window') and self.history_window.winfo_exists():
            self.history_window.focus()
            return
        self.history_window = IMEIHistoryWindow(self.root_toplevel, self.theme, self.restore_from_history)


    def copy_imeis_to_clipboard(self):
        imeis_to_copy = self.output_text_area.get("1.0", tk.END).strip()
        if imeis_to_copy and "No se encontraron IMEIs válidos." not in imeis_to_copy:
            try:
                pyperclip.copy(imeis_to_copy)
                self.status_label.config(text="¡IMEIs copiados al portapapeles!")
                
                # Feedback moderno temporizado sin popup
                original_text = self.copy_button.cget("text")
                original_bg = self.copy_button.cget("bg")
                self.copy_button.config(text="¡Copiado!", bg="#10B981")
                self.parent_frame.after(1500, lambda: self.copy_button.config(text=original_text, bg=original_bg))
            except pyperclip.PyperclipException:
                messagebox.showerror("Error al Copiar",
                                     "No se pudo acceder al portapapeles. Revisa la instalación de 'pyperclip' y sus dependencias (xclip/xsel en Linux).",
                                     parent=self.root_toplevel)
                self.status_label.config(text="Error al copiar al portapapeles.")
        elif not imeis_to_copy or "No se encontraron IMEIs válidos." in imeis_to_copy :
             if "No se encontraron IMEIs válidos." in imeis_to_copy:
                self.status_label.config(text="No hay IMEIs válidos para copiar.")
             else:
                self.status_label.config(text="Nada que copiar.")
        self.update_status_styling()

    def save_imeis_to_txt(self):
        imeis_to_save = self.output_text_area.get("1.0", tk.END).strip()

        if not imeis_to_save or "No se encontraron IMEIs válidos." in imeis_to_save:
            self.status_label.config(text="Nada que guardar.")
            self.update_status_styling()
            return

        try:
            default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(default_dir): default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.isdir(default_dir): default_dir = os.getcwd()

            filepath = filedialog.asksaveasfilename(
                initialdir=default_dir,
                title="Guardar IMEIs como archivo TXT",
                defaultextension=".txt",
                filetypes=(("Archivos de Texto", "*.txt"), ("Todos los archivos", "*.*")),
                initialfile="imeis_unicos_extraidos.txt",
                parent=self.root_toplevel
            )
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(imeis_to_save)
                self.status_label.config(text=f"IMEIs guardados en {os.path.basename(filepath)}")
            else:
                self.status_label.config(text="Guardado cancelado.")
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo.\nError: {e}", parent=self.root_toplevel)
            self.status_label.config(text="Error al guardar archivo.")
        self.update_status_styling()

    def clear_all_fields(self):
        self.input_text_area.delete("1.0", tk.END)
        self.output_text_area.config(state=tk.NORMAL)
        self.output_text_area.delete("1.0", tk.END)
        self.output_text_area.config(state=tk.DISABLED)
        self.imei_count_label.config(text="IMEIs únicos encontrados: 0")
        self.copy_button.config(state=tk.DISABLED)
        self.update_save_menu_callback(tk.DISABLED) # Usar callback
        self.status_label.config(text="Campos limpiados. Esperando nueva entrada.")
        self.update_status_styling()
        self.input_text_area.focus_set()

    def _internal_on_closing(self):
        pass

# --- START OF FILE procesador imeis yacelltech.py ---
# This comment was present in your original input, so I've kept it.
# Usually, the "START OF FILE" and "END OF FILE" markers are for delimiting
# the code when you provide it, and not part of the code itself.
# If this file were to be run, a main part would be needed, e.g.:
#
# if __name__ == '__main__':
#     # This is a mock main_app for demonstration purposes
#     class MockMainApp:
#         def __init__(self):
#             self.current_theme_colors = {
#                 "bg": "lightgrey", "fg": "black", "label_fg": "black",
#                 "text_bg": "white", "text_fg": "black",
#                 "button_bg": "grey", "button_fg": "black", "button_active_bg": "darkgrey",
#                 "button_clear_bg": "lightcoral", "button_clear_fg": "black",
#                 "button_secondary_bg": "lightblue", "button_secondary_fg": "black",
#                 "status_bar_bg": "grey", "status_bar_fg": "black",
#                 "success_fg": "green", "error_fg": "red", "warning_fg": "orange", "info_fg": "blue",
#                 "checkbutton_bg": "lightgrey", "checkbutton_fg": "black", "checkbutton_selectcolor": "white"
#             }
#
#     def mock_update_save_menu(state):
#         print(f"Save menu state updated to: {state}")
#
#     root = tk.Tk()
#     root.title("IMEI Processor Test")
#     main_frame = ttk.Frame(root, padding="10")
#     main_frame.pack(fill=tk.BOTH, expand=True)
#
#     mock_app = MockMainApp()
#     app_instance = IMEIProcessorApp(main_frame, mock_app, mock_update_save_menu)
#
#     # Add some example menu items for testing import/save
#     menubar = tk.Menu(root)
#     filemenu = tk.Menu(menubar, tearoff=0)
#     filemenu.add_command(label="Ver Historial...", command=app_instance.show_history)
#     filemenu.add_command(label="Guardar TXT...", command=app_instance.save_imeis_to_txt)
#     menubar.add_cascade(label="Archivo", menu=filemenu)
#     root.config(menu=menubar)
#
#     root.mainloop()