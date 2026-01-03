# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Add current directory to path for importing version
current_dir = os.getcwd()
sys.path.insert(0, current_dir)

import version

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[('app.ico', '.')] if os.path.exists('app.ico') else [],
    hiddenimports=['version'],
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
    name=f'ChatList-{version.__version__}',
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
    icon='app.ico' if os.path.exists('app.ico') else None,
)
