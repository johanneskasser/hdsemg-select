# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

# -------- Windows-only bits -------------------------------------------------
version_txt = os.path.abspath("version.txt")      # created by make_version.py
ICON_FILE   = "resources/icon.ico"               # .ico is required on Windows
# ----------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("_log",      "_log"),
        ("resources", "resources"),
    ],
    hiddenimports=[],
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
    name              = "hdsemg-select",
    version           = version_txt,   # ✅ keep the version resource
    icon              = ICON_FILE,     # ✅ .ico file
    debug             = False,
    bootloader_ignore_signals=False,
    strip             = False,
    upx               = True,
    upx_exclude       = [],
    runtime_tmpdir    = None,
    console           = False,
    disable_windowed_traceback=False,
    argv_emulation    = False,
    target_arch       = None,          # 32/64 handled by the PyInstaller wheel
    codesign_identity = None,
    entitlements_file = None,
)
