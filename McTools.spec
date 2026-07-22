# -*- mode: python ; coding: utf-8 -*-
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
    upx=True,
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
