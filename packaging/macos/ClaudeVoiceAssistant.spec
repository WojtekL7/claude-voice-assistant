# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Vibe Coding Assistant dla macOS (.app) — Etap M4.

Buduj NA macOS:  pyinstaller --noconfirm --clean packaging/macos/ClaudeVoiceAssistant.spec
(zwykle przez packaging/macos/build-macos.sh, który dodatkowo robi .dmg i podpis).

Uwaga: QTermWidget jest tylko-Linux — celowo wykluczony; na macOS terminalem
jest WebTerminal (xterm.js + QtWebEngine), dlatego dołączamy QtWebEngineWidgets.
"""
import os
import re

# SPECPATH = katalog tego pliku (packaging/macos). Korzeń repo = dwa poziomy wyżej.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
SRC = os.path.join(PROJECT_ROOT, "src")


def _read_app_version():
    """Wersja z JEDYNEGO źródła prawdy (config.APP_VERSION) — lekko, bez importu."""
    with open(os.path.join(SRC, "config.py"), encoding="utf-8") as f:
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
    return m.group(1) if m else "0.0.0"


APP_NAME = "Vibe Coding Assistant"
APP_VERSION = _read_app_version()
BUNDLE_ID = "pl.fulfillment.claude-voice-assistant"
ICON = os.path.join(SRC, "assets", "icon.icns")  # build-macos.sh zrobi .icns z .png

# Zasoby dołączane do bundla. Układ 'src/...' odpowiada config.BASE_DIR
# (sys._MEIPASS) w trybie spakowanym → ASSETS_DIR = <bundle>/src/assets.
datas = [
    (os.path.join(SRC, "assets"), "src/assets"),
    (os.path.join(SRC, "config.py"), "src"),
]
if os.path.isdir(os.path.join(SRC, "i18n")):
    datas.append((os.path.join(SRC, "i18n"), "src/i18n"))

hiddenimports = [
    "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "PyQt5.QtSvg",
    "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebChannel",
    "edge_tts", "pygame", "sounddevice", "numpy", "scipy", "requests",
    "ptyprocess", "pexpect", "psutil",
]

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["QTermWidget"],  # tylko-Linux; na macOS nieobecny i niepotrzebny
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="claude-voice-assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # aplikacja okienkowa (GUI)
    disable_windowed_traceback=False,
    target_arch=None,  # natywna architektura maszyny budującej (arm64/x86_64)
    codesign_identity=None,  # podpis robi build-macos.sh wg signing.conf
    entitlements_file=None,
    icon=(ICON if os.path.exists(ICON) else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="claude-voice-assistant",
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=(ICON if os.path.exists(ICON) else None),
    bundle_identifier=BUNDLE_ID,
    version=APP_VERSION,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        # Uprawnienie do mikrofonu — dyktowanie głosem (STT). Bez tego macOS
        # ubije aplikację przy próbie nagrywania.
        "NSMicrophoneUsageDescription":
            "Aplikacja używa mikrofonu do dyktowania poleceń głosem "
            "(zamiana mowy na tekst).",
        "LSApplicationCategoryType": "public.app-category.developer-tools",
    },
)
