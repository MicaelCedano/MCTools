# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas = [('logo.ico', '.'), ('logo.png', '.'), ('destinatarios_etiquetas.json', '.')]
if os.path.exists(os.path.join('dist', 'updater.exe')):
    datas.append((os.path.join('dist', 'updater.exe'), '.'))
elif os.path.exists('updater.exe'):
    datas.append(('updater.exe', '.'))
binaries = []

# Incluir explícitamente las DLLs del runtime de Python (python311.dll, vcruntime140.dll)
py_dir = os.path.dirname(sys.executable)
for dll_file in ['python3.dll', 'python311.dll', 'python313.dll', 'python314.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll']:
    full_dll_path = os.path.join(py_dir, dll_file)
    if os.path.exists(full_dll_path):
        binaries.append((full_dll_path, '.'))
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

# Excluir módulos que inflan el .exe sin ser necesarios
# numpy: arrastra ~15MB, PIL no lo necesita para formatos comunes
# lxml: reportlab lo llama solo si está instalado, pero no se usa en runtime
# pygments: reportlab lo referencia para syntax highlight, no usado
# setuptools/pkg_resources: solo para detección de paquetes en desarrollo
# tests/docs de qrcode y reportlab: metadata instalada, no ejecutable
EXCLUDES = [
    'numpy',
    'lxml',
    'pygments',
    'setuptools',
    'pkg_resources',
    'pip',
    'tkinter.test',
    'tkinter.tix',
    'unittest',
    'distutils',
    'qrcode.tests',
    'PIL.GifImagePlugin',      # formatos de imagen no usados
    'PIL.FpxImagePlugin',
    'PIL.MpegImagePlugin',
    'PIL.PcdImagePlugin',
    'PIL.PixarImagePlugin',
    'PIL.PsdImagePlugin',
    'PIL.SgiImagePlugin',
    'PIL.SunImagePlugin',
    'PIL.WalImageFile',
    'PIL.XbmImagePlugin',
    'PIL.XpmImagePlugin',
    'PIL.BufrStubImagePlugin',
    'PIL.FitsStubImagePlugin',
    'PIL.GribStubImagePlugin',
    'PIL.Hdf5StubImagePlugin',
    'PIL.McIdasImagePlugin',
    'PIL.MicImagePlugin',
    'PIL.FtexImagePlugin',
    'PIL.BlpImagePlugin',
    'PIL.ImImagePlugin',
    'PIL.ImtImagePlugin',
    'PIL.IptcImagePlugin',
    'PIL.MspImagePlugin',
    'PIL.PalmImagePlugin',
    'PIL.PcdImagePlugin',
    'PIL.QoiImagePlugin',
    'PIL.TgaImagePlugin',
    'PIL.WmfImagePlugin',
    'PIL.XVThumbImagePlugin',
    'PIL.CurImagePlugin',
    'PIL.DcxImagePlugin',
    'PIL.DdsImagePlugin',
    'PIL.FliImagePlugin',
    'PIL.GbrImagePlugin',
    'PIL.GdImageFile',
    'PIL.IcnsImagePlugin',
    'PIL.IcoImagePlugin',
]

# Incluir carpeta completa de customtkinter (assets, themes, fonts, json, etc)
ctk_path = os.path.dirname(customtkinter.__file__)
datas.append((ctk_path, 'customtkinter'))

# Recolectar binarios DLL/PYD dinámicos de PIL
try:
    binaries.extend(collect_dynamic_libs('PIL'))
except Exception as e:
    print(f"Advertencia al recolectar librerías dinámicas de PIL: {e}")

for pkg in ['PIL', 'customtkinter', 'reportlab', 'barcode', 'qrcode']:
    try:
        d, b, h = collect_all(pkg)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports.extend(h)
    except Exception as e:
        print(f"Advertencia al recolectar hooks de {pkg}: {e}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
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
