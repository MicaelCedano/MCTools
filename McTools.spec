# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter
import PIL
from PyInstaller.utils.hooks import collect_all

datas = [('logo.ico', '.'), ('logo.png', '.')]
binaries = []
hiddenimports = [
    'PIL',
    'PIL._imagingtk',
    'PIL.ImageTk',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'customtkinter',
    'reportlab',
    'barcode',
    'qrcode',
    'pyperclip',
    'win32print',
    'win32api',
    'win32con',
]

# Incluir carpeta completa de customtkinter (assets, themes, fonts, json, etc)
ctk_path = os.path.dirname(customtkinter.__file__)
datas.append((ctk_path, 'customtkinter'))

# Incluir carpeta completa de PIL
pil_path = os.path.dirname(PIL.__file__)
datas.append((pil_path, 'PIL'))

for pkg in ['PIL', 'customtkinter', 'reportlab', 'barcode', 'qrcode']:
    try:
        d, b, h = collect_all(pkg)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports.extend(h)
    except Exception as e:
        print(f"Advertencia al recolectar hooks de {pkg}: {e}")

a = Analysis(
    ['etiqueta_iphone_2025.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Excluir Tcl/Tk (no se necesita para customtkinter que incluye su propio runtime)
# a.binaries = [x for x in a.binaries if not x[0].startswith('tcl') and not x[0].startswith('tk')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='McTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
