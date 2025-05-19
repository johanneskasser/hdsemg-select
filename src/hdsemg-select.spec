# -*- mode: python ; coding: utf-8 -*-

import os, platform
from PyInstaller.utils.hooks import collect_data_files

# --------------------------------------------------------------------------
#  Detect the platform we are running on
# --------------------------------------------------------------------------
SYSTEM      = platform.system()
IS_WINDOWS  = SYSTEM == "Windows"
IS_MACOS    = SYSTEM == "Darwin"

# --------------------------------------------------------------------------
#  Common inputs
# --------------------------------------------------------------------------
MAIN_SCRIPT = "main.py"
APP_NAME    = "hdsemg-select"

datas = [
    ("_log",      "_log"),
    ("resources", "resources"),
]

# --------------------------------------------------------------------------
#  Platform-specific
# --------------------------------------------------------------------------
exe_kwargs = dict(                # kwargs fed into EXE(...)
    name                 = APP_NAME,
    debug                = False,
    bootloader_ignore_signals = False,
    strip                = False,
    upx                  = True,
    upx_exclude          = [],
    runtime_tmpdir       = None,
    console              = False,
    disable_windowed_traceback = False,
    argv_emulation       = False,
    codesign_identity    = None,
    entitlements_file    = None,
)

if IS_WINDOWS:
    # ① embed a VERSION resource
    exe_kwargs["version"] = os.path.abspath("version.txt")
    # ② Windows wants an .ico file
    exe_kwargs["icon"]    = "resources/icon.ico"
    # target_arch left to PyInstaller (it follows the Python bitness)

elif IS_MACOS:
    exe_kwargs["target_arch"] = "arm64"
    exe_kwargs["icon"]        = "resources/icon.icns"

else:
    exe_kwargs["icon"] = "resources/icon.png"  # PNG is accepted on Linux

a = Analysis(
    [MAIN_SCRIPT],
    pathex=["."],
    binaries=[],
    datas=datas,
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
    **exe_kwargs,
)

if IS_MACOS:
    app = BUNDLE(
        exe,
        name               = f"{APP_NAME}.app",
        icon               = exe_kwargs["icon"],
        bundle_identifier  = "at.fhcampuswien.hdsemgselect",
    )
