# hdsemg-select.spec
# ---------------------------------------------------------------
import platform, os
from PyInstaller.utils.hooks import collect_data_files

APP = "hdsemg-select"
MAIN_SCRIPT = "main.py"

# ─── data that must be shipped on every platform ────────────────
datas = [("_log", "_log"), ("resources", "resources")]

a   = Analysis([MAIN_SCRIPT], pathex=["."], datas=datas, binaries=[])
pyz = PYZ(a.pure)

# ---------------- common EXE ----------------
exe = EXE(
    pyz,
    a.scripts, a.binaries, a.datas,
    name              = APP,
    console           = False,          # GUI
    strip             = False,
    upx               = True,
    # platform-specific below
)

system = platform.system()

if system == "Windows":
    exe.version = os.path.abspath("version.txt")
    exe.icon    = "resources/icon.ico"

elif system == "Darwin":                 # macOS
    exe.icon         = "resources/icon.icns"
    exe.target_arch  = "arm64"           # or "x86_64" on Intel

# -------------- onedir build everywhere --------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name=APP,
)

# -------------- wrap in .app bundle *only* on macOS --------------
if system == "Darwin":
    app = BUNDLE(
        coll,
        name              = f"{APP}.app",
        icon              = exe.icon,
        bundle_identifier = "com.yourorg.hdsemgselect",
    )
