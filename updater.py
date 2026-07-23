# -*- coding: utf-8 -*-
"""
McTools Updater - Asistente de Actualización Independiente
Permite reemplazar McTools.exe por una nueva versión descargada sin conflictos de archivo bloqueado.
"""
import sys
import os
import time
import argparse
import subprocess
import shutil
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox

def is_pid_running(pid):
    """Comprueba si un proceso con el PID dado sigue activo en Windows."""
    if pid <= 0:
        return False
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        SYNCHRONIZE = 0x0010
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            DWORD = ctypes.c_ulong
            exit_code = DWORD()
            STILL_ACTIVE = 259
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return False

class UpdaterApp:
    def __init__(self, root, target, source, pid, launch):
        self.root = root
        self.target = target
        self.source = source
        self.pid = pid
        self.launch = launch

        self.root.title("Actualizador McTools")
        self.root.geometry("420x200")
        self.root.resizable(False, False)
        self.root.configure(bg="#0F172A")

        # Centrar ventana
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # Icono si existe en el directorio de trabajo o bundle
        icon_path = "logo.ico"
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            icon_path = os.path.join(base_dir, "logo.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # Frame contenedor
        container = tk.Frame(root, bg="#0F172A", padx=20, pady=20)
        container.pack(fill="both", expand=True)

        # Título
        title_label = tk.Label(
            container, 
            text="Actualizando McTools", 
            font=("Segoe UI", 14, "bold"), 
            fg="#F8FAFC", 
            bg="#0F172A"
        )
        title_label.pack(anchor="w", pady=(0, 10))

        # Mensaje de estado
        self.status_label = tk.Label(
            container, 
            text="Iniciando proceso de actualización...", 
            font=("Segoe UI", 10), 
            fg="#94A3B8", 
            bg="#0F172A",
            anchor="w"
        )
        self.status_label.pack(fill="x", pady=(0, 15))

        # Estilo para ProgressBar
        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "Custom.Horizontal.TProgressbar", 
            thickness=10, 
            troughcolor="#1E293B", 
            background="#06B6D4", 
            bordercolor="#0F172A", 
            lightcolor="#06B6D4", 
            darkcolor="#06B6D4"
        )

        # Barra de progreso
        self.progress = ttk.Progressbar(
            container, 
            style="Custom.Horizontal.TProgressbar", 
            orient="horizontal", 
            mode="determinate"
        )
        self.progress.pack(fill="x", pady=(0, 15))
        self.progress["value"] = 0

        # Subtexto de información
        self.sub_label = tk.Label(
            container, 
            text="Por favor espere mientras se reemplaza la versión anterior.", 
            font=("Segoe UI", 8), 
            fg="#64748B", 
            bg="#0F172A",
            anchor="w"
        )
        self.sub_label.pack(fill="x")

        # Iniciar proceso tras renderizar ventana
        self.root.after(300, self.run_update)

    def set_status(self, text, progress_val):
        self.status_label.configure(text=text)
        self.progress["value"] = progress_val
        self.root.update_idletasks()

    def run_update(self):
        try:
            # Paso 1: Esperar a que el proceso anterior finalice
            if self.pid > 0:
                self.set_status("Esperando que McTools se cierre...", 15)
                max_wait = 15.0  # segundos maximos
                start_time = time.time()
                while is_pid_running(self.pid):
                    time.sleep(0.3)
                    if time.time() - start_time > max_wait:
                        try:
                            subprocess.run(["taskkill", "/F", "/PID", str(self.pid)], capture_output=True)
                        except Exception:
                            pass
                        break

            # Breve pausa para asegurar liberación de handles por el SO
            self.set_status("Preparando reemplazo de archivos...", 35)
            time.sleep(0.5)

            # Paso 2: Reemplazar el ejecutable destino
            if not os.path.exists(self.source):
                raise FileNotFoundError(f"No se encontró el archivo fuente descargado:\n{self.source}")

            self.set_status("Instalando nueva versión...", 60)
            
            copied = False
            last_error = None
            for attempt in range(12):
                try:
                    shutil.copy2(self.source, self.target)
                    copied = True
                    break
                except Exception as e:
                    last_error = e
                    time.sleep(0.5)

            if not copied:
                raise RuntimeError(f"No se pudo reemplazar {self.target}:\n{last_error}")

            self.set_status("Limpiando archivos temporales...", 85)
            try:
                if os.path.exists(self.source):
                    os.remove(self.source)
            except Exception:
                pass

            self.set_status("¡Actualización completada! Iniciando McTools...", 100)
            time.sleep(0.5)

            # Paso 3: Ejecutar la aplicación actualizada si se especificó launch
            if self.launch and os.path.exists(self.target):
                subprocess.Popen([self.target])

            self.root.after(300, self.root.destroy)

        except Exception as e:
            messagebox.showerror("Error de Actualización", f"Ocurrió un error al instalar la actualización:\n{e}")
            self.root.destroy()

def main():
    parser = argparse.ArgumentParser(description="McTools Standalone Updater")
    parser.add_argument("--target", required=True, help="Ruta al ejecutable objetivo McTools.exe")
    parser.add_argument("--source", required=True, help="Ruta al archivo ejecutable descargado")
    parser.add_argument("--pid", type=int, default=0, help="PID del proceso McTools a esperar")
    parser.add_argument("--launch", action="store_true", default=True, help="Iniciar app después de actualizar")

    args = parser.parse_args()

    root = tk.Tk()
    app = UpdaterApp(root, target=args.target, source=args.source, pid=args.pid, launch=args.launch)
    root.mainloop()

if __name__ == "__main__":
    main()
