# 📱 McTools - Generador de Etiquetas & Procesador de IMEIs

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)
![Build](https://img.shields.io/badge/Build-PyInstaller-orange)

**McTools** (EtiquetaPro) es una aplicación de escritorio diseñada para negocios de tecnología, servicio técnico y distribuidores de telefonía móvil. Permite diseñar, generar e imprimir etiquetas profesionales con código de barras e IMEIs en formato QR para iPhones y dispositivos inteligentes.

---

## ✨ Características Principales

- 🏷️ **Generación de Etiquetas Doble Modo:**
  - **Modo Código de Barras:** Genera etiquetas con códigos de barras Code128 para IMEIs individuales o números de serie.
  - **Modo Código QR Multi-IMEI:** Empaqueta múltiples IMEIs dentro de un código QR estructurado para lectura rápida en inventario.
- 🎨 **Personalización y Previsualización:**
  - Renderizado dinámico en tiempo real de la etiqueta.
  - Inserción y ajuste de logotipo corporativo en la etiqueta.
  - Dimensiones optimizadas estándar (4" x 3" pulgadas o personalizadas).
- 🖨️ **Impresión Directa y Exportación a PDF:**
  - Creación de PDFs vectoriales de alta precisión con [ReportLab](https://www.reportlab.com/).
  - Impresión térmica/directa en impresoras de etiquetas configuradas en Windows (mediante SumatraPDF o la API de impresión `win32print`).
- 📜 **Historial de IMEIs & Procesador Inteligente:**
  - Historial persistente en JSON (`etiqueta_config.json`) con marcas de tiempo para consultar impresiones pasadas.
  - Extractor/limpiador de IMEIs desde textos sin formato o desde el portapapeles.
- 🔄 **Actualizador Automático Integrado:**
  - Verificación automática de lanzamientos en GitHub (`MicaelCedano/McTools`).
  - Descarga e instalación automatizada de nuevas versiones ejecutables sin intervención manual.
- 🌙 **Interfaz Moderna:**
  - Desarrollada con `CustomTkinter` ofreciendo un diseño limpio, fluido y adaptable.

---

## 📁 Estructura del Proyecto

```text
MCTools Dev/
├── etiqueta_iphone_2025.py        # Código fuente principal de la aplicación GUI (v3.4.2)
├── generar_qr_imeis (1).py        # Módulo/script alternativo para generación de etiquetas QR
├── procesador imeis yacelltech.py # Herramienta auxiliar de procesamiento e historial de IMEIs
├── etiqueta_config.json           # Archivo de configuración local y almacenamiento de historial
├── McTools.spec                   # Archivo de especificación de PyInstaller para compilar .exe
├── logo.ico                       # Icono oficial de la aplicación
└── logo.png                       # Imagen de logotipo corporativo por defecto
```

---

## 🚀 Requisitos e Instalación

### 1. Prerrequisitos
Asegúrate de contar con **Python 3.9** o superior instalado en Windows.

### 2. Instalación de Dependencias
Instala los paquetes necesarios ejecutando el siguiente comando en la terminal:

```bash
pip install customtkinter pillow python-barcode qrcode reportlab pywin32 pyperclip
```

---

## 💻 Uso

### Ejecutar desde el código fuente
Para iniciar la aplicación en modo desarrollo:

```bash
python etiqueta_iphone_2025.py
```

### Compilar a Ejecutable (.exe)
Para generar el ejecutable standalone listo para distribución en Windows:

```bash
pyinstaller McTools.spec
```

El ejecutable resultante estará en la carpeta `dist/McTools.exe`.

---

## 🛠️ Tecnologías Utilizadas

- **[Python](https://www.python.org/):** Lenguaje base de desarrollo.
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter):** Framework moderno para la interfaz gráfica.
- **[Pillow (PIL)](https://python-pillow.org/):** Procesamiento de imágenes y renderizado de etiquetas.
- **[ReportLab](https://www.reportlab.com/):** Generación de documentos PDF de alta resolución para impresión.
- **[python-barcode](https://github.com/python-barcode/python-barcode) & [qrcode](https://github.com/lincolnloop/python-qrcode):** Algoritmos de generación de códigos de barras (Code128) y códigos QR.
- **[PyInstaller](https://pyinstaller.org/):** Empaquetado a ejecutable Windows sin dependencias externas.

---

## 👤 Autor

Desarrollado por **[Micael Cedano](https://github.com/MicaelCedano)**  
*EtiquetaPro / McTools - Soluciones informáticas para gestión de dispositivos móviles.*
