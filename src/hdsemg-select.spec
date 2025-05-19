# -*- mode: python ; coding: utf-8 -*-
# A single spec that works on Windows and macOS without edits
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(__file__).parent.resolve()
VERSION_TXT = ROOT / "version.txt"

is_macos   = sys.platform == "darwin"
is_windows = sys.platform.startswith("win")

# ─────────────────── Analysis ────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
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

# ─────────────────── EXE ─────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="hdsemg-select",
    version=str(VERSION_TXT),
    icon="resources/icon.png" if is_windows else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI app
)

# ─────────────────── macOS: wrap inside .app bundle ─────────────────────────
if is_macos:
    app = BUNDLE(
        exe,
        name="hdsemg-select.app",
        icon="resources/icon.icns",
        bundle_identifier="at.fhcampuswien.hdsemg-select",
    )
    # This is what we will hand to COLLECT
    main_target = app
else:
    # Windows (and Linux, if ever needed) → just the exe
    main_target = exe

# ─────────────────── COLLECT (creates dist/ folder) ─────────────────────────
coll = COLLECT(
    main_target,          # *** pass the object, not a string path! ***
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="hdsemg-select",
)

