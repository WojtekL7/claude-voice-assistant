# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Vibe Coding Assistant dla Linuksa (onedir → AppImage).

Buduj NA Linuksie:  pyinstaller --noconfirm --clean packaging/linux/ClaudeVoiceAssistant.spec
(zwykle przez packaging/linux/build.sh, który dodatkowo składa AppImage).

Uwaga: w AppImage terminalem jest WebTerminal (xterm.js + QtWebEngine) — DOKŁADNIE
ten sam silnik co na macOS/Windows. QTermWidget jest celowo WYKLUCZONY: to natywna
biblioteka systemowa (libqtermwidget5.so + dane), której nie chcemy wnosić do paczki.
Po wykluczeniu `from QTermWidget import …` w paczce zawiedzie → terminal_backend
sam przełączy się na WebTerminal (selected_backend_kind() ma ten fallback). Uruchomienie
„z kodu" (python src/main.py) na Linuksie dalej używa QTermWidgetu — bez zmian.
"""
import os
import re
import glob

# SPECPATH = katalog tego pliku (packaging/linux). Korzeń repo = dwa poziomy wyżej.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
SRC = os.path.join(PROJECT_ROOT, "src")


def _read_app_version():
    """Wersja z JEDYNEGO źródła prawdy (config.APP_VERSION) — lekko, bez importu."""
    with open(os.path.join(SRC, "config.py"), encoding="utf-8") as f:
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
    return m.group(1) if m else "0.0.0"


APP_VERSION = _read_app_version()
ICON = os.path.join(SRC, "assets", "icon.png")

# Zasoby dołączane do paczki. Układ 'src/...' odpowiada config.BASE_DIR
# (sys._MEIPASS) w trybie spakowanym → ASSETS_DIR = <paczka>/src/assets.
datas = [
    (os.path.join(SRC, "assets"), "src/assets"),
    (os.path.join(SRC, "config.py"), "src"),
]
if os.path.isdir(os.path.join(SRC, "i18n")):
    datas.append((os.path.join(SRC, "i18n"), "src/i18n"))

# Ikony SVG leżące OBOK modułów gui/ (close_x, checkmark, refresh) — kod ładuje
# je przez `Path(__file__).parent / "X.svg"`, więc w paczce muszą trafić do
# `gui/` (tam PyInstaller umieszcza moduł gui.*), a NIE do src/assets.
for _svg in glob.glob(os.path.join(SRC, "gui", "*.svg")):
    datas.append((_svg, "gui"))

hiddenimports = [
    "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "PyQt5.QtSvg",
    "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebChannel",
    "edge_tts", "pygame", "sounddevice", "numpy", "scipy", "requests",
    "ptyprocess", "pexpect", "psutil",
]

# --- Wtyczki platformowe Qt (KRYTYCZNE na Linuksie) ---
# W buildach do 1.0.19 PyInstaller NIE dociągał automatycznie wtyczek Qt z PyQt5,
# przez co w paczce brakowało `platforms/libqxcb.so` → aplikacja nie startowała
# ("Could not find the Qt platform plugin xcb", crash w 1. sekundzie). Dołączamy
# je JAWNIE jako BINARIA (nie datas!), żeby PyInstaller przeanalizował też ich
# zależności (np. libQt5XcbQpa, libxcb-*) i wciągnął je do paczki. qt.conf w
# paczce ma `Prefix=..` względem PyQt5/Qt5/libexec → wtyczki MUSZĄ trafić do
# PyQt5/Qt5/plugins/<grupa>, inaczej Qt ich nie znajdzie.
import PyQt5  # dostępne w venv buildu (pyinstaller działa w tym venv)

_QT_PLUGINS_SRC = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
# Grupy niezbędne dla okna/GUI na Linuksie (X11 + Wayland + obrazy/ikony).
_QT_PLUGIN_GROUPS = [
    "platforms",                            # libqxcb.so itd. — BEZ tego brak okna
    "xcbglintegrations",                    # integracja OpenGL z xcb (WebEngine)
    "platformthemes",
    "platforminputcontexts",
    "iconengines",
    "imageformats",
    "wayland-shell-integration",            # dla pełnego Wayland (poza XWayland)
    "wayland-decoration-client",
    "wayland-graphics-integration-client",
]
binaries = []
for _grp in _QT_PLUGIN_GROUPS:
    _grp_dir = os.path.join(_QT_PLUGINS_SRC, _grp)
    if not os.path.isdir(_grp_dir):
        continue
    for _so in glob.glob(os.path.join(_grp_dir, "*.so")):
        binaries.append((_so, os.path.join("PyQt5", "Qt5", "plugins", _grp)))
if not any(d.endswith(os.path.join("plugins", "platforms")) for _, d in binaries):
    raise SystemExit(
        "BŁĄD spec: nie znaleziono wtyczek platforms w %s — paczka byłaby "
        "niestartowalalna (brak libqxcb.so)." % _QT_PLUGINS_SRC
    )

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["QTermWidget"],  # natywny, tylko-Linux; w AppImage używamy WebTerminala
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
