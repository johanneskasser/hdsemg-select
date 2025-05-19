# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

ICON_FILE = "resources/icon.icns"

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
    [],
    exclude_binaries=True,
    name               = "hdsemg-select",
    icon               = ICON_FILE,
    console            = False,
    debug              = False,
    strip              = False,
    upx                = True,
    target_arch        = "arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip       = False,
    upx         = True,
    name        = "hdsemg-select",
)

app = BUNDLE(
    coll,
    name               = "hdsemg-select.app",
    icon               = ICON_FILE,
    bundle_identifier  = "at.fhcampuswien.hdsemgselect",
)
