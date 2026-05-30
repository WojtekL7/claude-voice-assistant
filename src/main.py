#!/usr/bin/env python3
"""
Claude Voice Assistant
Main entry point for the application.
"""
import sys
import os
import traceback
from pathlib import Path

# Add src directory to path (zanim zaimportujemy cokolwiek z projektu).
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

# Tweaki środowiska Qt zależne od systemu MUSZĄ pójść przed importem PyQt5
# i utworzeniem QApplication. Cała logika per-OS żyje w platform_utils:
# - Linux: backend X11 (XWayland) + wyłączony iBus (zjada Enter w terminalu;
#   patrz DIAGNOSE-ENTER-FIX.md). Test natywnego Wayland: VOICE_USE_WAYLAND=1.
# - macOS/Windows: backendy natywne, nic nie wymuszamy.
from core.platform_utils import configure_qt_environment, use_native_menu_bar
configure_qt_environment()

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

    # Pasek menu: natywny na macOS/Windows, w oknie na Linuksie (pozycjonowanie
    # pod XWayland bywa błędne). Atrybut "DontUseNative" = odwrotność.
    QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar, not use_native_menu_bar())

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
