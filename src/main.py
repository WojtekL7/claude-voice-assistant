#!/usr/bin/env python3
"""
Claude Voice Assistant
Main entry point for the application.
"""
import sys
import os
import traceback
from pathlib import Path

# Domyślnie wymuszamy backend X11 (XWayland pod sesją Wayland) — historycznie
# rozwiązywało to problem pozycjonowania menu pod Wayland. ALE: XWayland +
# Intel iGPU + ciężki UI = ryzyko zamarznięcia kompozytora (patrz diagnoza
# DIAGNOSE-ENTER-FIX.md i analiza zawieszeń z 2026-05-12).
# Test natywnego Wayland: VOICE_USE_WAYLAND=1 python3 src/main.py
# (jeśli menu pozycjonuje się poprawnie pod Wayland w Twoim Ubuntu, lepiej
# zostać przy Wayland natywnym — odciąża kompozytor i grafikę).
if os.environ.get("VOICE_USE_WAYLAND") != "1":
    os.environ["QT_QPA_PLATFORM"] = "xcb"

# Wyłącz iBus dla Voice Assistant — pod XWayland z aktywnym iBus klawisz Enter
# jest "zjadany" przez ibus-engine-simple, gdy w terminalu pojawiają się
# podpowiedzi/popupy (Claude Code). Skutek: Enter z klawiatury nie wywołuje
# returnPressed w AutoResizeTextEdit, klik w przycisk "↵ Enter" działa
# (pomija warstwę IM). Wymuszamy "none" — Qt bierze klawisze bezpośrednio
# bez pośrednictwa Input Method. Inne aplikacje (LibreOffice, Firefox)
# iBus nadal używają.
os.environ["QT_IM_MODULE"] = "none"

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from gui.main_window import MainWindow
from config import APP_NAME, ASSETS_DIR


def _excepthook(exc_type, exc_value, exc_tb):
    """Log unhandled exceptions instead of letting Qt silently kill the app.

    Without this, a Python exception from a PyQt slot takes down the process
    without a visible traceback, making crashes feel like "app closed itself".
    """
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
    sys.stderr.flush()


def main():
    """Main entry point."""
    sys.excepthook = _excepthook

    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Disable native menu bar - fixes menu positioning on XWayland
    QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar, True)

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Fulfillment Polska")

    # Set application icon
    icon_path = ASSETS_DIR / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
