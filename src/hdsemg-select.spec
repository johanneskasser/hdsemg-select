# -*- mode: python ; coding: utf-8 -*-
import sys, os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

# ── robust project root detection ────────────────────────────────────────────
if "__file__" in globals():
    ROOT = Path(__file__).parent.resolve()
else:
    ROOT = Path.cwd().resolve()

VERSION_TXT = ROOT / "version.txt"

is_macos   = sys.platform == "darwin"
is_windows = sys.platform.startswith("win")

# ── Analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[("_log", "_log"), ("resources", "resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# ── EXE ──────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="hdsemg-select",
    version=str(VERSION_TXT),
    icon="resources/icon.png" if is_windows else None,
    debug=False, strip=False, upx=True,
    console=False,
)

# optional macOS .app wrapper
targets = [exe]
if is_macos:
    app = BUNDLE(
        exe,
        name="hdsemg-select.app",
        icon="resources/icon.icns",
        bundle_identifier="at.fhcampuswien.hdsemg-select",
    )
    targets.append(app)

# --------------------------------------------------------------------
coll = COLLECT(
    *targets,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="hdsemg-select",
)

