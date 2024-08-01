# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

# Needed for pypdfium2
import os
import sysconfig
site_packages_dir = sysconfig.get_paths()["purelib"]
pdfium_dll_path = os.path.join(site_packages_dir, 'pypdfium2_raw', 'pdfium.dll')

datas = [(os.path.join(site_packages_dir, 'pypdfium2_raw', 'pdfium.dll'), 'pypdfium2_raw'),
         (os.path.join(site_packages_dir, 'pypdfium2_raw', 'version.json'), 'pypdfium2_raw'),
         (os.path.join(site_packages_dir, 'pypdfium2', 'version.json'), 'pypdfium2')]
datas += collect_data_files('gradio_client')
datas += collect_data_files('gradio')


a = Analysis(
    ['demo_gradio.py'],
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
    name='PDF-to-AAS Demo',
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
