#!/usr/bin/env python3
"""
Vibe Coding Assistant
Main entry point for the application.
"""
import sys
import os
import gc
import traceback
from pathlib import Path

# Add src directory to path (zanim zaimportujemy cokolwiek z projektu).
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

# Windows: gdy stdout/stderr są PRZEKIEROWANE (do pliku/potoku), Python daje im
# kodowanie cp1252 — wtedy print() z polskim znakiem rzuca UnicodeEncodeError
# i potrafi wywalić CAŁĄ aplikację (zdarzyło się w handlerze błędu TTS).
# errors="replace" = znak spoza kodowania staje się '?', nigdy wyjątek.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass

# Tweaki środowiska Qt zależne od systemu MUSZĄ pójść przed importem PyQt5
# i utworzeniem QApplication. Cała logika per-OS żyje w platform_utils:
# - Linux: backend X11 (XWayland) + wyłączony iBus (zjada Enter w terminalu;
#   patrz DIAGNOSE-ENTER-FIX.md). Test natywnego Wayland: VOICE_USE_WAYLAND=1.
# - macOS/Windows: backendy natywne, nic nie wymuszamy.
from core.platform_utils import (
    configure_qt_environment, use_native_menu_bar, prefer_webengine_terminal,
)
configure_qt_environment()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from gui.main_window import MainWindow
from config import APP_NAME, ASSETS_DIR, IS_DEV, APP_WM_CLASS


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

    # QtWebEngine (WebTerminal na macOS/Windows, a na Linuksie pod
    # CVA_WEBTERMINAL=1) ma dwa twarde wymogi, oba PRZED QApplication:
    #  1) atrybut AA_ShareOpenGLContexts,
    #  2) zaimportowanie QtWebEngineWidgets zanim powstanie QApplication
    #     (inaczej PyQt5 rzuca "must be imported before a QApplication").
    # Na Linuksie domyślnie (QTermWidget) ten blok się NIE wykonuje → bez zmian.
    if prefer_webengine_terminal():
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
        import PyQt5.QtWebEngineWidgets  # noqa: F401  (import dla efektu ubocznego)

    # Create application
    app = QApplication(sys.argv)
    # W trybie deweloperskim doklej „ (beta)" do nazwy i użyj osobnego WM_CLASS,
    # by pasek zadań Linuksa NIE sklejał okna z kodu z wersją wydaną (AppImage).
    # Imię aplikacji = slug (APP_WM_CLASS). Na Linuksie (XWayland) to ONO trafia
    # do WM_CLASS okna, po którym pasek zadań GNOME dobiera ikonę z pliku .desktop
    # (StartupWMClass=<slug>). Ładną nazwę pokazujemy osobno przez displayName —
    # dzięki temu na dolnym pasku widać właściwą ikonę (a nie domyślną zębatkę).
    app.setApplicationName(APP_WM_CLASS)
    app.setApplicationDisplayName(APP_NAME + (" (beta)" if IS_DEV else ""))
    app.setDesktopFileName(APP_WM_CLASS)
    app.setOrganizationName("Fulfillment Polska")

    # Czcionki dołączone do aplikacji — wygląd ma być IDENTYCZNY na każdym
    # systemie, a nie zdany na to, co akurat ma użytkownik. Motyw używa
    # IBM Plex Sans (interfejs) i JetBrains Mono (terminal, dane techniczne);
    # Ubuntu zostaje jako zapas dla starszych skórek i systemów bez assets.
    from PyQt5.QtGui import QFontDatabase, QFont
    from config import ASSETS_DIR
    from gui import theme
    _fonts_dir = ASSETS_DIR / "fonts"
    for _name in ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Medium.ttf",
                  "IBMPlexSans-SemiBold.ttf", "IBMPlexSans-Bold.ttf",
                  "JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf",
                  "UbuntuMono.ttf", "Ubuntu.ttf"):
        _fp = _fonts_dir / _name
        if _fp.exists():
            QFontDatabase.addApplicationFont(str(_fp))

    # Domyślna czcionka interfejsu na WSZYSTKICH systemach (wcześniej tylko poza
    # Linuksem). Gdy plik .ttf nie wszedł do paczki, Qt cicho podstawia zamiennik
    # — dlatego sprawdzamy, czy rodzina faktycznie się zarejestrowała.
    _families = set(QFontDatabase().families())
    _ui_family = theme.FONT_UI if theme.FONT_UI in _families else theme.FONT_UI_FALLBACK
    _ui_font = QFont(_ui_family, 10)
    _ui_font.setWeight(QFont.Normal)
    app.setFont(_ui_font)

    # Set application icon
    icon_path = ASSETS_DIR / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    #
    # ⛔ NIE pisz tu `sys.exit(app.exec_())` — to była przyczyna crashu przy ZAMYKANIU
    # (Mac 1.0.25/1.0.26/1.0.28, `EXC_BAD_ACCESS`; pełny stos w pamięci projektu).
    # Mechanizm: `SystemExit` trzyma swój traceback → traceback trzyma RAMKĘ tej funkcji
    # → ramka trzyma JEDNOCZEŚNIE `app` i `window`. Oba giną więc dopiero przy sprzątaniu
    # wyjątku i w kolejności, na którą nie mamy wpływu — zmierzone: `QApplication` ginął
    # PIERWSZY, a `MainWindow` dopiero w środku jego destruktora. Ukrywanie okna woła
    # wtedy `QApplication::setActiveWindow()`, które ROZSYŁA zdarzenia po widżetach —
    # a te mają już zwolnioną stronę C++ (segfault w `QWidget::palette()`).
    #
    # Dlatego niszczymy okno JAWNIE, póki `QApplication` jeszcze żyje.
    # ⚠️ Kolejność jest tu istotą poprawki — nie „upraszczaj" tego z powrotem do jednej linii.
    rc = app.exec_()
    del window
    gc.collect()
    sys.exit(rc)


if __name__ == "__main__":
    main()
