# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Claude Voice Assistant dla Windows (.exe, onedir) — Etap W2.

Buduj NA Windows:  pyinstaller --noconfirm --clean packaging/windows/ClaudeVoiceAssistant.spec
(zwykle przez packaging/windows/build-windows.ps1, który dodatkowo robi .ico i instalator Inno Setup).

Uwaga:
  • QTermWidget jest tylko-Linux — celowo wykluczony; na Windows terminalem jest
    WebTerminal (xterm.js + QtWebEngine), dlatego dołączamy QtWebEngineWidgets.
  • Terminal na Windows używa ConPTY przez pywinpty (moduł `winpty`) — w hiddenimports.
  • onedir (folder z .exe) — pewniejsze dla QtWebEngine niż onefile
    (QtWebEngineProcess.exe + zasoby rozpakowują się obok, bez kosztu/ryzyka onefile).
"""
import os
import re

# SPECPATH = katalog tego pliku (packaging/windows). Korzeń repo = dwa poziomy wyżej.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
SRC = os.path.join(PROJECT_ROOT, "src")


def _read_app_version():
    """Wersja z JEDYNEGO źródła prawdy (config.APP_VERSION) — lekko, bez importu."""
    with open(os.path.join(SRC, "config.py"), encoding="utf-8") as f:
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
    return m.group(1) if m else "0.0.0"


APP_NAME = "Claude Voice Assistant"
APP_VERSION = _read_app_version()
ICON = os.path.join(SRC, "assets", "icon.ico")  # build-windows.ps1 zrobi .ico z .png

# Zasoby dołączane do paczki. Układ 'src/...' odpowiada config.BASE_DIR
# (sys._MEIPASS) w trybie spakowanym → ASSETS_DIR = <paczka>/src/assets.
datas = [
    (os.path.join(SRC, "assets"), "src/assets"),
    (os.path.join(SRC, "config.py"), "src"),
]
if os.path.isdir(os.path.join(SRC, "i18n")):
    datas.append((os.path.join(SRC, "i18n"), "src/i18n"))

hiddenimports = [
    "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
    "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebChannel",
    "edge_tts", "pygame", "sounddevice", "numpy", "scipy", "requests",
    "winpty",  # pywinpty — ConPTY (terminal na Windows)
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
    excludes=["QTermWidget"],  # tylko-Linux; na Windows nieobecny i niepotrzebny
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,            # nazwa pliku .exe: "Claude Voice Assistant.exe"
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # aplikacja okienkowa (GUI) — bez czarnego okna konsoli
    disable_windowed_traceback=False,
    icon=(ICON if os.path.exists(ICON) else None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,           # nazwa folderu onedir w dist/
)
