# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('venv\\Lib\\site-packages\\pypdfium2_raw\\pdfium.dll', 'pypdfium2_raw'),
        ('venv\\Lib\\site-packages\\pypdfium2_raw\\version.json', 'pypdfium2_raw'),
        ('venv\\Lib\\site-packages\\pypdfium2\\version.json', 'pypdfium2')]
datas += collect_data_files('gradio_client')
datas += collect_data_files('gradio')


a = Analysis(
    ['examples\\demo_gradio.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    module_collection_mode={
        'gradio': 'py',  # Collect gradio package as source .py files
    },
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='demo_gradio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
