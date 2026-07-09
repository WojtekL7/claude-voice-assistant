"""
Vibe Coding Assistant - Main Window
PyQt5-based GUI for the application.
"""
import sys
import os
import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox,
    QCheckBox, QMenuBar, QMenu, QAction, QStatusBar, QDialog,
    QDialogButtonBox, QFormLayout, QMessageBox, QFrame,
    QToolButton, QSizePolicy, QApplication, QInputDialog,
    QColorDialog, QGridLayout, QGroupBox, QScrollArea, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTabWidget, QTabBar, QProgressBar, QProxyStyle, QStyle, QStyleFactory
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QObject, QEvent, QPoint, QRect
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QKeySequence, QPalette, QColor, QTextCharFormat, QPainter, QPen, QPixmap, QLinearGradient

# QTermWidget for real terminal emulation
try:
    from QTermWidget import QTermWidget
    QTERMWIDGET_AVAILABLE = True
except ImportError:
    QTERMWIDGET_AVAILABLE = False
    print("Warning: QTermWidget not available, using fallback QTextEdit")


class _AccentFrame(QWidget):
    """Centralny widget rysujący kolorową ramkę akcentu (kolor aktywnego agenta,
    Funkcja #2) RĘCZNIE w paintEvent — BEZ arkusza stylu.

    Dlaczego nie QSS: arkusz stylu na centralnym widżecie (rodzicu terminala)
    kaskaduje QStyleSheetStyle na QTermWidget → wokół terminala pojawiają się
    białe ramki i zmieniają się suwaki. Ramka na QMainWindow z kolei gubi górę
    i dół (zasłaniają je pasek menu i pasek statusu). Ręczne malowanie rysuje
    pełną ramkę po 4 bokach i nie dotyka stylu dzieci."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = None

    def set_accent(self, color):
        if color != self._accent:
            self._accent = color
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._accent:
            return
        painter = QPainter(self)
        pen = QPen(QColor(self._accent))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.end()


class _LeftAlignedTabStyle(QProxyStyle):
    """Wyrównuje pasek zakładek do LEWEJ na każdej platformie (zwł. macOS).

    Tło problemu (potwierdzone na realnym Macu + research):
    macOS centruje zakładki NIE przez sam style-hint SH_TabBar_Alignment (ten
    QMacStyle ignoruje — dlatego ani CSS `tab-bar{alignment:left}`, ani sam
    QProxyStyle nadpisujący ten hint nie działały). Realne centrowanie liczy
    styl *QTabWidget* w `subElementRect(SE_TabWidgetTabBar)` — zwraca prostokąt
    paska wyśrodkowany w szerokości widżetu.

    Dlatego ta nakładka robi DWIE rzeczy i jest oparta o silnik **Fusion**
    (nie-macowy, który wyrównanie do lewej respektuje):
      1. `subElementRect(SE_TabWidgetTabBar)` — dosuwa prostokąt paska do lewej
         krawędzi, jeśli styl bazowy zwrócił go przesuniętego w prawo (centrowanie).
      2. `styleHint(SH_TabBar_Alignment)` -> Qt.AlignLeft — wyrównanie zakładek
         wewnątrz paska (dla porządku / innych stylów).

    Podpinana do *QTabWidget* (decyduje o położeniu paska) i do jego paska.
    Kolory/kształt/ikona X z QSS działają dalej. Na Linuksie i tak lewo → zero regresji.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.SH_TabBar_Alignment:
            return Qt.AlignLeft
        return super().styleHint(hint, option, widget, returnData)

    def subElementRect(self, element, option, widget=None):
        rect = super().subElementRect(element, option, widget)
        if element == QStyle.SE_TabWidgetTabBar and option is not None:
            # Dosuń pasek zakładek do lewej krawędzi (gdy styl bazowy wycentrował).
            if rect.left() > option.rect.left():
                rect.moveLeft(option.rect.left())
        return rect


class _AccentTabBar(QTabBar):
    """Pasek zakładek z gradientową kreską nad aktywną zakładką.

    QSS nie umie gradientu w `border-top` (tylko jednolity kolor), a przez
    `background` nie da się namalować samej kreski. Dlatego dokładamy ją ręcznie
    po tym, jak styl narysuje zakładki. Kreska jest wcięta po bokach — jak w
    makiecie — i nie zasłania ikony ani flagi „?" (rysowana w górnych 2 px).

    Kolor jest STAŁY (akcent aplikacji), niezależny od koloru agenta: kreska ma
    mówić „ta zakładka jest aktywna", a nie dublować informację, którą już niesie
    kolor tytułu.
    """

    _STRIPE_H = 2      # grubość kreski
    _STRIPE_INSET = 8  # wcięcie od lewej i prawej krawędzi zakładki

    def paintEvent(self, event):
        super().paintEvent(event)
        idx = self.currentIndex()
        if idx < 0:
            return
        rect = self.tabRect(idx)
        if rect.isNull() or rect.width() <= 2 * self._STRIPE_INSET:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        stripe = QRect(rect.left() + self._STRIPE_INSET, rect.top(),
                       rect.width() - 2 * self._STRIPE_INSET, self._STRIPE_H)
        grad = QLinearGradient(stripe.left(), 0, stripe.right(), 0)
        grad.setColorAt(0.0, QColor(theme.ACCENT))
        grad.setColorAt(1.0, QColor(theme.ACCENT_GLOW))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(stripe, 1, 1)
        painter.end()


class SignalBridge(QObject):
    """Thread-safe bridge for signals from background threads to GUI."""
    output_received = pyqtSignal(str)
    response_received = pyqtSignal(str)
    error_received = pyqtSignal(str)
    tts_state_changed = pyqtSignal(object)
    tts_finished = pyqtSignal()
    stt_state_changed = pyqtSignal(object)
    stt_transcription = pyqtSignal(str)
    stt_error = pyqtSignal(str)


class MenuPositionFixer(QObject):
    """
    Event filter that fixes menu positioning on rotated monitors.

    On XWayland with rotated monitors, Qt calculates wrong coordinates
    for popup menus. This filter intercepts menu Show events and
    corrects the position to appear directly below the menu bar item.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fixing = False  # Prevent recursion

    def eventFilter(self, obj, event):
        """Intercept QMenu show events and fix position."""
        if isinstance(obj, QMenu) and event.type() == QEvent.Show and not self._fixing:
            # Schedule position fix after menu is shown
            QTimer.singleShot(0, lambda: self._fix_menu_position(obj))
        return super().eventFilter(obj, event)

    def _fix_menu_position(self, menu):
        """Fix menu position if it's wrong."""
        if self._fixing:
            return

        # Check if menu has intended position set (for popup menus like "+" tab)
        if hasattr(menu, '_intended_pos') and menu._intended_pos is not None:
            intended_pos = menu._intended_pos
            current_pos = menu.pos()

            # Check if position is significantly wrong (more than 50px off)
            dx = abs(current_pos.x() - intended_pos.x())
            dy = abs(current_pos.y() - intended_pos.y())

            if dx > 50 or dy > 50:
                # Position is wrong - fix it
                self._fixing = True
                menu.move(intended_pos)
                self._fixing = False

            # Clear after use
            menu._intended_pos = None
            return

        # Find the parent menubar and active action
        parent = menu.parent()

        # Handle QMenuBar menus
        if isinstance(parent, QMenuBar):
            action = parent.activeAction()
            if action:
                # Calculate correct position: below the menu bar item
                action_rect = parent.actionGeometry(action)
                correct_pos = parent.mapToGlobal(action_rect.bottomLeft())

                current_pos = menu.pos()

                # Check if position is significantly wrong (more than 50px off)
                dx = abs(current_pos.x() - correct_pos.x())
                dy = abs(current_pos.y() - correct_pos.y())

                if dx > 50 or dy > 50:
                    # Position is wrong - fix it
                    self._fixing = True
                    menu.move(correct_pos)
                    self._fixing = False

        # Handle submenus (QMenu -> QMenu)
        elif isinstance(parent, QMenu):
            # For submenus, check if position is reasonable
            parent_pos = parent.pos()
            current_pos = menu.pos()

            # Submenu should appear near the parent menu
            # If it's too far away, try to fix it
            dx = abs(current_pos.x() - parent_pos.x())
            dy = abs(current_pos.y() - parent_pos.y())

            # Submenu should be within reasonable distance of parent
            parent_width = parent.width()
            if dx > parent_width + 100 or dy > parent.height() + 100:
                # Position is wrong - place submenu to the right of parent
                self._fixing = True
                new_pos = QPoint(parent_pos.x() + parent_width, parent_pos.y())
                menu.move(new_pos)
                self._fixing = False


class TerminalScrollManager:
    """
    Centralized manager for terminal scrolling.

    Solves the problem of inconsistent scrolling by:
    1. Using a single debounced timer (150ms delay for layout to settle)
    2. Using scrollbar.setValue(maximum) instead of scrollToEnd() - more reliable
    3. Coalescing multiple scroll requests into one
    4. Working correctly with rotated monitors
    """

    SCROLL_DELAY_MS = 300  # Delay to let layout fully settle (increased for rotated monitors)

    def __init__(self, terminal, parent):
        self._terminal = terminal
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_scroll)
        self._enabled = True

    def schedule_scroll(self):
        """
        Schedule a scroll to bottom.
        Multiple calls within SCROLL_DELAY_MS are coalesced into one.
        """
        if not self._enabled or not self._terminal:
            return
        # Restart timer - this cancels any pending scroll and schedules a new one
        self._timer.stop()
        self._timer.start(self.SCROLL_DELAY_MS)

    def scroll_now(self):
        """Force immediate scroll to bottom (use sparingly)."""
        self._timer.stop()
        self._do_scroll()

    def _do_scroll(self):
        """Actually perform the scroll using scrollbar for reliability."""
        if not self._terminal:
            return
        try:
            # Method 1: Use scrollbar directly (most reliable)
            scrollbar = self._terminal.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            else:
                # Fallback: use scrollToEnd
                self._terminal.scrollToEnd()
        except Exception:
            pass

    def disable(self):
        """Temporarily disable scrolling (e.g., when user is reading history)."""
        self._enabled = False
        self._timer.stop()

    def enable(self):
        """Re-enable scrolling."""
        self._enabled = True

    def stop(self):
        """Stop any pending scroll."""
        self._timer.stop()


class AutoResizeTextEdit(QTextEdit):
    """QTextEdit that auto-resizes based on content."""

    # Signal emitted when Enter is pressed (without Shift)
    returnPressed = pyqtSignal()
    # Signal emitted when height changes (for scroll manager to react)
    heightChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_height = 55
        self.max_height = 180  # ~5 lines
        self.document().contentsChanged.connect(self._adjust_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Set document margin for proper text rendering
        self.document().setDocumentMargin(12)
        # Set line height
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self._adjust_height()

    def _adjust_height(self):
        """Adjust height based on content."""
        doc_height = self.document().size().height()
        new_height = max(self.min_height, min(int(doc_height) + 16, self.max_height))

        if new_height != self.height():
            # Block signals to prevent QSplitter relayout from causing scroll
            old_block = self.signalsBlocked()
            self.blockSignals(True)
            self.setFixedHeight(new_height)
            self.blockSignals(old_block)
            # NOTE: Removed heightChanged.emit() - it was causing unwanted page scrolling

    def keyPressEvent(self, event):
        """Handle key press - Enter sends, Shift+Enter adds new line."""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if event.modifiers() & Qt.ShiftModifier:
                # Shift+Enter = new line
                super().keyPressEvent(event)
            else:
                # Enter = send
                self.returnPressed.emit()
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Paste as plain text — drop colors, fonts, underlines from the source.

        Covers Ctrl+V, Shift+Insert, context-menu Paste, and text drag&drop.
        """
        if source.hasText():
            self.textCursor().insertText(source.text())
        else:
            super().insertFromMimeData(source)

    def text(self):
        """Return plain text (compatibility with QLineEdit)."""
        return self.toPlainText()

    def setText(self, text):
        """Set plain text."""
        self.setPlainText(text)

    def clear(self):
        """Clear text and reset height."""
        # Block ALL signals to prevent scroll issues during clear
        old_block = self.signalsBlocked()
        self.blockSignals(True)
        self.document().blockSignals(True)
        super().clear()
        # Manually reset to minimum height (with signals blocked)
        self.setFixedHeight(self.min_height)
        self.document().blockSignals(False)
        self.blockSignals(old_block)
        # NOTE: Removed heightChanged.emit() - it was causing unwanted page scrolling

# Import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    SUPPORTED_LANGUAGES, UI_TRANSLATIONS, DEFAULT_QUICK_ACTIONS,
    CONFIG_FILE, QUICK_ACTIONS_FILE, CLAUDE_COMMAND, GROQ_API_KEY,
    AGENTS_FILE, MEMORY_PROJECTS_FILE, DEFAULT_AGENTS, DEFAULT_MEMORY_PROJECTS,
    CONFIG_DIR,
    ASSETS_DIR, CLAUDE_MODEL_CONTEXT_LIMITS, DEFAULT_AGENT_MODEL,
    APP_TITLE_SUFFIX,
    UPDATE_APPCAST_URL, UPDATE_PUBLIC_KEY, UPDATE_DOWNLOAD_DIR,
    MAX_ACTIVE_AGENTS, RAM_PER_AGENT_GB, RAM_SYSTEM_RESERVE_GB,
    t as tr, set_ui_language, detect_system_language,
)
from core.claude_bridge import ClaudeBridgeAsync
from core.tts_engine import TTSEngine, TTSState
from core.stt_engine import STTEngine, STTState
from core.license_manager import LicenseManager, LicenseStatus
from core.text_cleaner import TextCleanerForTTS, extract_last_claude_response, fix_polish_encoding, prose_from_markdown
from core.transcript_reader import TranscriptReader
from core.update_manager import UpdateManager
from core.platform_utils import update_platform_id, total_ram_gb, recommended_max_agents
from gui.agent_tab import AgentTab
from gui import icon_set
from gui import theme
from gui.dialogs import (
    MemoryProjectsDialog, AgentConfigDialog, AgentsManagerDialog,
    SkillsManagerDialog, McpManagerDialog, UpdateAvailableDialog,
    ClaudeSetupDialog,
    styled_get_open_file_names, styled_get_open_file_name, styled_get_save_file_name
)
from gui.mcp_status_widget import McpStatusWidget
from gui.resource_monitor import ResourceMonitorWidget

# Diagnostyka flagi „?" — PASYWNY czujnik, domyślnie WYŁĄCZONY (zero kosztu
# w wydanej apce). Włącz przez zmienną środowiskową CVA_FLAG_DEBUG=1. Zapisuje
# stan każdego ogniwa flagi do ~/.vibe-coding-assistant/flag-debug.log, żeby
# ustalić, dlaczego flaga „agent czeka" nie pokazuje się na zakładce w tle.
_FLAG_DEBUG = bool(os.environ.get("CVA_FLAG_DEBUG"))

# Domyślne kolory skórki (motyw „Vibe Purple") — interfejs + terminal.
# Wartości pochodzą z jednej palety (gui/theme.py), nie są tu wpisywane wprost.
DEFAULT_SKIN_COLORS = theme.skin_colors()

# Wersja schematu skórki. Podbicie = zapisana u użytkownika skórka jest
# PORZUCANA na rzecz nowych domyślnych (z kopią zapasową configu). Bez tego
# redesign byłby niewidoczny: `_load_settings` nadpisuje defaulty wartościami
# z config.json, więc kto raz uruchomił starą wersję, ten oglądałby ją dalej.
SKIN_VERSION = 2

# Nazwy kolorów do wyświetlenia w UI (po polsku)
SKIN_COLOR_NAMES = {
    # === Kolory interfejsu ===
    'main_window_bg': 'Tło głównego okna',
    'menu_bar_bg': 'Tło paska menu',
    'status_bar_bg': 'Tło paska statusu',
    'bottom_panel_bg': 'Tło panelu przycisków',
    'border_color': 'Kolor obramowań',
    'hover_color': 'Kolor podświetlenia (hover)',
    'splitter_color': 'Kolor rozdzielacza',
    'text_color': 'Kolor tekstu interfejsu',
    'button_bg': 'Tło przycisków',
    'button_hover': 'Przycisk przy najechaniu',
    'input_bg': 'Tło pola tekstowego',
    'inactive_panel_bg': 'Panel nieaktywny',
    # === Kolory terminala ===
    'terminal_bg': 'Tło terminala',
    'terminal_fg': 'Tekst terminala',
    'terminal_color_0': 'Czarny',
    'terminal_color_1': 'Czerwony',
    'terminal_color_2': 'Zielony',
    'terminal_color_3': 'Żółty',
    'terminal_color_4': 'Niebieski',
    'terminal_color_5': 'Magenta (fioletowy)',
    'terminal_color_6': 'Cyan (turkusowy)',
    'terminal_color_7': 'Biały',
    'terminal_color_0_bright': 'Jasny czarny (szary)',
    'terminal_color_1_bright': 'Jasny czerwony',
    'terminal_color_2_bright': 'Jasny zielony',
    'terminal_color_3_bright': 'Jasny żółty',
    'terminal_color_4_bright': 'Jasny niebieski',
    'terminal_color_5_bright': 'Jasna magenta',
    'terminal_color_6_bright': 'Jasny cyan',
    'terminal_color_7_bright': 'Jasny biały',
    # === Kolory ikon przycisków ===
    'icon_dictate_color': 'Kolor ikony mikrofonu',
    'icon_read_color': 'Kolor ikony głośnika',
    'icon_pause_color': 'Kolor ikony pauzy',
    'icon_stop_color': 'Kolor ikony stop',
    'icon_copy_color': 'Kolor ikony kopiuj',
    'icon_clear_input_color': 'Kolor ikony wyczyść',
    'icon_add_media_color': 'Kolor ikony dodaj media',
    'icon_send_color': 'Kolor ikony wyślij',
    'icon_quick_actions_color': 'Kolor ikony szybkich akcji',
}

# Domyślne ikony przycisków (emoji/tekst)
DEFAULT_SKIN_ICONS = {
    'dictate': {'normal': '🎤', 'active': '🎤', 'processing': '⏳'},
    'read': {'normal': '🔊', 'active': '🔉', 'processing': '⏳'},
    'pause': {'normal': '⏸', 'active': '▶'},
    'stop': {'normal': '⬜'},
    'copy': {'normal': '⧉', 'active': '✓'},
    'clear_input': {'normal': '✕'},
    'add_media': {'normal': '📎'},
    'send': {'normal': '↵'},
    'quick_actions': {'normal': '⚡▼'},
}

# Nazwy ikon do wyświetlenia w UI (po polsku)
SKIN_ICON_NAMES = {
    'dictate': 'Mikrofon (dyktowanie)',
    'read': 'Głośnik (czytanie)',
    'pause': 'Pauza',
    'stop': 'Stop',
    'copy': 'Kopiuj',
    'clear_input': 'Wyczyść pole',
    'add_media': 'Dodaj media',
    'send': 'Wyślij',
    'quick_actions': 'Szybkie akcje',
}


def _skin_color_name(color_key: str) -> str:
    """Przetłumaczona nazwa koloru skórki (fallback: SKIN_COLOR_NAMES / klucz)."""
    # UI_TRANSLATIONS jest importowane na górze modułu (absolutnie, `from config import`).
    tkey = 'skin_color_' + color_key
    if tkey in UI_TRANSLATIONS.get('pl-PL', {}):
        return tr(tkey)
    return SKIN_COLOR_NAMES.get(color_key, color_key)


def _skin_icon_name(icon_key: str) -> str:
    """Przetłumaczona nazwa ikony skórki (fallback: SKIN_ICON_NAMES / klucz)."""
    # UI_TRANSLATIONS jest importowane na górze modułu (absolutnie, `from config import`).
    tkey = 'skin_icon_' + icon_key
    if tkey in UI_TRANSLATIONS.get('pl-PL', {}):
        return tr(tkey)
    return SKIN_ICON_NAMES.get(icon_key, icon_key)


class MainWindow(QMainWindow):
    """Main application window."""

    # Flaga „?": ile sekund CISZY w terminalu uznajemy za „agent nie pracuje".
    # Pracujący Claude Code odświeża pasek (licznik sekund) co ~1 s — 3 s daje
    # trzykrotny margines, a flaga i tak ma sens dopiero po paru sekundach.
    QUESTION_TERMINAL_QUIET_SECS = 3.0

    # Wynik sprawdzania gotowości (3 punkty kreatora) policzonego w wątku tła —
    # emitowany z wątku, odbierany w wątku GUI (bezpieczne przez kolejkę Qt).
    _readiness_ready = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        # False przez cały __init__: pierwszy addTab()/setCurrentIndex emituje
        # currentChanged JESZCZE W TRAKCIE budowy okna, a aktywacja zakładki
        # w niezamontowanym kontekście tworzy NIEWIDOCZNY QTermWidget (terminal
        # działa w tle, ekran pusty). Aktywację primary robi odroczony QTimer
        # (patrz komentarz przy setCurrentIndex w _load_agents). Szczegóły:
        # guard na początku _on_tab_changed.
        self._ui_ready = False

        # Thread-safe signal bridge
        self.signals = SignalBridge()

        # Initialize managers
        self.claude = ClaudeBridgeAsync(CLAUDE_COMMAND)
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self.license_manager = LicenseManager()

        # Auto-aktualizacja (M3) — sprawdzanie/pobieranie idzie w wątku tła managera.
        self.update_manager = UpdateManager(
            UPDATE_APPCAST_URL, APP_VERSION, update_platform_id(),
            public_key=UPDATE_PUBLIC_KEY, download_dir=UPDATE_DOWNLOAD_DIR)
        # True = sprawdzanie wywołane ręcznie z menu (wtedy pokazujemy też wynik
        # „masz najnowszą"/błąd); False = ciche sprawdzanie przy starcie.
        # Aktualizacje sprawdzamy WYŁĄCZNIE przy starcie (i ręcznie z menu) —
        # nie przy zamykaniu, więc zamknięcie jest natychmiastowe.
        self._manual_update_check = False
        # Wersja, dla której pokazaliśmy już SAMO okno pobierania — żeby cykliczne
        # sprawdzanie (co 30 min) nie otwierało go w kółko; nowsza wersja = znów okno.
        self._prompted_update_version = None

        # Settings
        self.current_language = "pl-PL"
        self.auto_read_responses = False
        self.auto_check_updates = True  # nadpisywane przez _load_settings
        # Kreator dyktowania: user zaznaczył „nie przypominaj" → nie wymuszaj okna
        # z powodu braku klucza Groq (nadpisywane przez _load_settings).
        self.dictation_reminder_dismissed = False
        self._readiness_ready.connect(self._on_readiness_checked)
        self.quick_actions = self._load_quick_actions()
        self.attached_files = []  # List of attached file paths
        self.skin_colors = DEFAULT_SKIN_COLORS.copy()  # Custom skin colors (interfejs + terminal)
        self.skin_icons = {k: v.copy() for k, v in DEFAULT_SKIN_ICONS.items()}  # Custom icons
        self.claude_command = CLAUDE_COMMAND  # rozwiązywane wieloplatformowo (config.find_claude_command)
        self.auto_run_claude = True  # Auto-run Claude command on startup
        # Id ostatnio aktywnej zakładki — używane do wyboru "primary agent" przy
        # starcie (aktywuje się od razu; pozostałe zakładki czekają na klik).
        self.last_active_agent_id = None

        # Agents and memory projects
        self.agents = self._load_agents()
        self.memory_projects = self._load_memory_projects()
        self.agent_tabs = {}  # Dict of agent_id -> AgentTab

        # Historia używania zakładek (MRU — ostatnio używana na początku).
        # Po zamknięciu zakładki wracamy do ostatnio używanej, a nie do
        # sąsiada wybranego przez Qt (który bywa pustą atrapą "+").
        self._tab_mru = []  # lista agent_id

        # Load settings
        self._load_settings()

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._setup_shortcuts()

        # Install menu position fixer for rotated monitors
        self._menu_fixer = MenuPositionFixer(self)
        QApplication.instance().installEventFilter(self._menu_fixer)

        # Check license
        self._check_license()

        # Start Claude Code
        self._start_claude()

        # Apply terminal colors after a delay (terminal needs time to initialize)
        QTimer.singleShot(500, lambda: self._apply_terminal_colors(self.skin_colors))
        # Apply again after longer delay to ensure it takes effect
        QTimer.singleShot(1500, lambda: self._apply_terminal_colors(self.skin_colors))

        # Sprawdzenie aktualizacji ~3 s po starcie (po rozruchu terminala), w tle;
        # gdy jest nowsza wersja, _on_update_available SAM otworzy okno pobierania.
        QTimer.singleShot(3000, self._maybe_auto_check_updates)

        # Cykliczne sprawdzanie aktualizacji co ~30 min (nie tylko przy starcie),
        # żeby nowa wersja zgłosiła się sama bez restartu programu. Lampka „nowa
        # wersja" zapala się od razu; okno pobierania wyskakuje RAZ na daną wersję.
        self._update_poll_timer = QTimer(self)
        self._update_poll_timer.setInterval(30 * 60 * 1000)  # 30 minut
        self._update_poll_timer.timeout.connect(self._maybe_auto_check_updates)
        self._update_poll_timer.start()

        # Brak Claude Code CLI (świeży komputer) → kreator „dokończ instalację"
        # zamiast surowego „command not found" w terminalu. Po rozruchu okna,
        # żeby dialog stanął NAD głównym oknem, nie przed nim.
        QTimer.singleShot(1500, self._maybe_show_claude_setup)

        # NOTE: Claude jest teraz uruchamiany w _create_agent_tab() dla każdej zakładki
        # Stare globalne wywołanie usunięte, bo powodowało podwójne uruchomienie

        # Okno zbudowane — od teraz _on_tab_changed obsługuje zmiany zakładek
        # normalnie (emisje currentChanged z trakcie __init__ są ignorowane).
        self._ui_ready = True

        # Ramka akcentu + kolory zakładek dla PRIMARY zakładki na starcie.
        # Primary aktywuje się odroczonym QTimerem (nie przez _on_tab_changed),
        # więc _apply_tab_change nie odpala i bez tego ramka pojawiłaby się
        # dopiero po pierwszym przełączeniu zakładek (zgłoszenie usera).
        QTimer.singleShot(0, self._recolor_all_tabs)
        QTimer.singleShot(0, self._apply_active_tab_frame)

    def _setup_ui(self):
        """Setup user interface."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}{APP_TITLE_SUFFIX}")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)  # Domyślny rozmiar startowy

        # Central widget
        central_widget = _AccentFrame()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # Tab widget for agents
        self.tab_widget = QTabWidget()
        # Własny pasek — dokłada gradientową kreskę nad aktywną zakładką.
        # Musi trafić przed dodaniem zakładek (QTabWidget.setTabBar).
        self.tab_widget.setTabBar(_AccentTabBar())
        # Wyrównaj zakładki do lewej także na macOS. Centrowanie liczy styl
        # QTabWidget (SE_TabWidgetTabBar), a QMacStyle ignoruje hint wyrównania —
        # dlatego bazujemy na silniku Fusion (respektuje lewą) i dosuwamy pasek
        # jawnie. Nakładkę podpinamy do QTabWidget (położenie paska) ORAZ do paska.
        # Referencję TRZYMAMY na self — inaczej GC skasuje styl i wróci środek.
        _fusion = QStyleFactory.create("Fusion")
        self._tab_style = (
            _LeftAlignedTabStyle(_fusion) if _fusion is not None
            else _LeftAlignedTabStyle()
        )
        self.tab_widget.setStyle(self._tab_style)
        self.tab_widget.tabBar().setStyle(self._tab_style)
        # Ikona agenta na zakładce ~2× większa (życzenie usera) — domyślnie Qt daje
        # ~16 px; ustawiamy 30 px, żeby ikona (robot/własna) była wyraźnie widoczna.
        self.tab_widget.setIconSize(QSize(30, 30))
        # Czcionka zakładek przez API (nie QSS — font-size w QTabBar::tab jest
        # ignorowany przy własnym QStyle/Fusion). Rodzina interfejsu z palety;
        # rozmiar dobrany pod makietę. Uwaga: ikony-emoji to TEKST, więc rosną
        # razem z czcionką (obrazki skalują się przez setIconSize).
        _tab_font = QFont(theme.ui_family())
        _tab_font.setPointSize(11)
        _tab_font.setWeight(QFont.Medium)
        self.tab_widget.tabBar().setFont(_tab_font)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_agent_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.tab_widget.setStyleSheet(self._compose_tabbar_qss(self.skin_colors))

        # Create dropdown menu for "+" tab
        self._add_tab_menu = QMenu(self)
        self._add_tab_menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px;
            }
            QMenu::item:selected {
                background-color: #4a1a3a;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4a1a3a;
                margin: 5px 10px;
            }
        """)

        self._populate_add_tab_menu()

        # Connect tab bar click to handle "+" tab
        self.tab_widget.tabBarClicked.connect(self._on_tab_bar_clicked)

        # Create tabs for auto-start agents
        self._create_agent_tabs()

        # Add "+" tab at the end (must be after creating agent tabs)
        self._add_plus_tab()

        # Kolory tekstu zakładek (po dodaniu „+"); QSS nie ustawia już 'color'.
        self._recolor_all_tabs()

        main_layout.addWidget(self.tab_widget)

        # Keep references for compatibility with existing code
        # terminal_backend — wspólny interfejs aktywnej zakładki (M2.2/M2.3).
        # terminal — opakowany widget (na Linuksie QTermWidget). Operacje wołamy
        # przez terminal_backend, by działały też na WebTerminalu (macOS/Windows).
        self.terminal_backend = None
        self.terminal = None
        self.conversation_area = None
        self.bottom_panel = None
        self.input_field = None
        self._terminal_output_buffer = ""
        self._scroll_manager = None

        # Animation timers (shared across all tabs)
        self._mic_pulse_timer = QTimer()
        self._mic_pulse_timer.timeout.connect(self._animate_mic_pulse)
        self._mic_pulse_state = False

        self._speaker_anim_timer = QTimer()
        self._speaker_anim_timer.timeout.connect(self._animate_speaker)
        self._speaker_anim_state = 0
        # Poziomy głośnika do animacji czytania (nazwy ikon SVG; dawniej 🔈🔉🔊).
        self._speaker_icons = icon_set.SPEAKER_LEVELS

        self._pause_blink_timer = QTimer()
        self._pause_blink_timer.timeout.connect(self._animate_pause_blink)
        self._pause_blink_state = True

        # Etap 3 (Droga A): cykliczne czytanie nowej prozy z dziennika sesji.
        # Co ~0.8s zaglądamy do dziennika aktywnej zakładki i czytamy nowe
        # wypowiedzi; nieaktywne zakładki z auto-read zbierają zaległości.
        self._transcript_timer = QTimer()
        self._transcript_timer.timeout.connect(self._poll_transcripts)
        self._transcript_timer.start(800)

        # Update references to current tab
        self._update_current_tab_references()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status(tr('status_ready'))

        # Context usage counter (per-agent — pokazuje licznik aktywnej zakładki).
        # Każdy AgentTab przechowuje własny total_context_tokens; tu trzymamy
        # tylko współczynnik, globalny sumator i sam label.
        self._chars_per_token = 3.5  # Średnia dla polskiego (angielski ~4).
        self._total_app_tokens = 0   # Suma tokenów ze wszystkich zakładek (od startu).
        # Throttling odświeżania paska tokenów. Terminal emituje chunki kilkadziesiąt
        # razy na sekundę przy streamingu odpowiedzi Claude — bez tego setStyleSheet
        # leciał tysiącami i blokował UI.
        self._refresh_tokens_pending = False
        self._context_label = QLabel("0")
        self._context_label.setToolTip(tr('context_label_tooltip'))
        self._context_label.setStyleSheet("""
            QLabel {
                color: #4ade80;
                font-size: 11px;
                padding: 0 10px 0 4px;
                font-weight: bold;
            }
        """)
        # Stała zarezerwowana szerokość — bez tego rosnąca liczba cyfr zmienia
        # szerokość etykiety i cały prawy róg paska statusu „skacze" w lewo/prawo
        # przy każdej aktualizacji (co ~200 ms podczas streamingu). Rezerwujemy
        # miejsce pod największą realną wartość i wyrównujemy do prawej (przy
        # grupie przyklejonej do prawej krawędzi prawa krawędź liczby zostaje w
        # miejscu, a ewentualna luka chowa się na lewym końcu paska).
        _ctx_font = QFont(self._context_label.font())
        _ctx_font.setPixelSize(11)
        self._context_label.setFont(_ctx_font)
        # ZERO RUCHU: STAŁA szerokość + wyrównanie do PRAWEJ. Prawa krawędź liczby
        # (tuż przy ikonach) jest nieruchoma, a liczba „dorasta" w lewo jak na
        # wyświetlaczu kalkulatora — nic nie drga, niezależnie od liczby cyfr ani
        # długości procentu. Rezerwa z zapasem pod największą realną wartość
        # per-zakładka (7 cyfr tokenów + do 3 cyfr %).
        self._context_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._context_label.setFixedWidth(
            self._context_label.fontMetrics().horizontalAdvance("9,999,999  (999%)") + 18)

        # Pasek postępu zużycia okna kontekstu zakładki — graficzny odpowiednik
        # zielonej liczby. Wypełnienie = ten sam procent, kolor = ten sam próg
        # (zielony/żółty/pomarańczowy/czerwony); jedno i drugie ustawiane w
        # _refresh_context_label. Stała szerokość → nie wprowadza skakania.
        self._context_bar = QProgressBar()
        self._context_bar.setRange(0, 100)
        self._context_bar.setValue(0)
        self._context_bar.setTextVisible(False)
        self._context_bar.setFixedSize(70, 10)
        self._context_bar.setToolTip(
            "Graficzne zużycie okna kontekstu modelu w tej zakładce.\n"
            "Wypełnienie i kolor odpowiadają liczbie obok (zielony→żółty→\n"
            "pomarańczowy→czerwony). Auto-compact w Claude Code: ~80–90%."
        )
        # Pasek (lewo) + liczba (prawo) w jednym kontenerze — pewna kolejność,
        # niezależnie od porządku addPermanentWidget.
        self._context_box = QWidget()
        # Maximum: kontener [pasek+liczba] przylega do treści i ląduje przy prawej
        # krawędzi obszaru (tuż przy ikonach MCP), zamiast być rozciągany.
        self._context_box.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        _ctx_box_layout = QHBoxLayout(self._context_box)
        _ctx_box_layout.setContentsMargins(0, 0, 0, 0)
        _ctx_box_layout.setSpacing(4)
        _ctx_box_layout.addWidget(self._context_bar)
        _ctx_box_layout.addWidget(self._context_label)
        self.status_bar.addPermanentWidget(self._context_box)

        # Lampka „nowa wersja" — pojawia się TYLKO gdy update_available; klik
        # otwiera okno pobierania zapamiętanej aktualizacji. Siedzi tuż obok
        # graficznego wskaźnika kontekstu (dodana jako drugi permanentny widget
        # → ląduje na lewo od _context_box). Ukryta na starcie.
        self._pending_update_info = None
        self._update_indicator = QToolButton()
        self._update_indicator.setText(tr('update_indicator_text'))
        self._update_indicator.setToolTip(tr('update_indicator_tooltip'))
        self._update_indicator.setCursor(Qt.PointingHandCursor)
        self._update_indicator.setAutoRaise(True)
        self._update_indicator.setStyleSheet(
            "QToolButton { color: #4ade80; font-size: 11px; font-weight: bold;"
            " padding: 0 8px; border: none; }"
            "QToolButton:hover { color: #22c55e; }")
        self._update_indicator.clicked.connect(self._open_pending_update)
        self._update_indicator.setVisible(False)
        self.status_bar.addPermanentWidget(self._update_indicator)

        # Status widget agenta (po lewej od licznika tokenów):
        # 🔌 MCP, 🧩 skille, 📁 pliki, 🤖 model + 🔄 refresh.
        self.mcp_status_widget = McpStatusWidget()
        self.mcp_status_widget.request_open_manager.connect(self._open_mcp_manager_for_dir)
        self.mcp_status_widget.request_open_skills.connect(self._open_skills_manager_from_status)
        self.mcp_status_widget.request_edit_agent.connect(self._open_edit_agent_from_status)
        # Drugie addPermanentWidget — ląduje bardziej na lewo niż _context_label
        self.status_bar.addPermanentWidget(self.mcp_status_widget)

        # Wskaźnik zużycia RAM — ikona „kości RAM" zmieniająca kolor wg obciążenia
        # pamięci komputera (zielony→żółty→pomarańczowy→czerwony). Ostrzega przed
        # zawieszeniem przy zapchanej pamięci. Niezależny od aktywnej zakładki;
        # sam się odświeża. Ukrywa się, gdy brak biblioteki psutil.
        self.resource_monitor = ResourceMonitorWidget()
        self.status_bar.addPermanentWidget(self.resource_monitor)

        # Synchronizuj z aktywną zakładką (która już istnieje po _create_agent_tabs)
        self._update_mcp_status_widget()
        # Inicjalna wartość globalnego licznika (Σ 0)
        self._refresh_total_tokens_label()

        # Menu bar
        self._create_menu_bar()

        # Apply dark theme (includes terminal colors via apply_skin_colors)
        self._apply_dark_theme()

    # ==================== Agent Management ====================

    def _load_agents(self) -> list:
        """Load agents from file."""
        if AGENTS_FILE.exists():
            try:
                with open(AGENTS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return [a.copy() for a in DEFAULT_AGENTS]

    def _save_agents(self):
        """Save agents to file."""
        try:
            # Siatka bezpieczeństwa: RAZ na sesję zachowaj poprzednią wersję pliku
            # (agents.json.autobak). Apka nadpisuje agents.json przy każdym zapisie
            # (suwak/zmiana zakładki), więc ręczna edycja pliku przy działającej
            # apce bywa kasowana — backup pozwala odzyskać stan sprzed sesji.
            if not getattr(self, '_agents_session_backed_up', False) and AGENTS_FILE.exists():
                try:
                    import shutil
                    shutil.copy2(AGENTS_FILE, AGENTS_FILE.parent / (AGENTS_FILE.name + ".autobak"))
                except Exception:
                    pass
                self._agents_session_backed_up = True
            with open(AGENTS_FILE, 'w') as f:
                json.dump(self.agents, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving agents: {e}")

    def _on_splitter_changed(self, agent_tab, sizes: list):
        """Handle splitter position change - update agent config and save."""
        agent_id = agent_tab.agent_id

        # Update agent in self.agents list
        for agent in self.agents:
            if agent.get('id') == agent_id:
                agent['splitter_sizes'] = sizes
                self._save_agents()
                return

    def _inherit_splitter_sizes(self, config: dict):
        """Nowa zakładka dziedziczy proporcje suwaka z aktywnej zakładki.

        Działa tylko gdy config nie ma jeszcze własnych splitter_sizes
        (nowy agent / nowy terminal „+"). Bez aktywnej zakładki (start
        aplikacji) zostaje fallback config.DEFAULT_SPLITTER_SIZES w AgentTab.
        """
        if config.get('splitter_sizes'):
            return
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, AgentTab):
            sizes = widget.splitter_sizes
            if sizes and len(sizes) == 2 and all(s > 0 for s in sizes):
                config['splitter_sizes'] = list(sizes)

    def _load_memory_projects(self) -> list:
        """Load memory projects from file."""
        if MEMORY_PROJECTS_FILE.exists():
            try:
                with open(MEMORY_PROJECTS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return DEFAULT_MEMORY_PROJECTS.copy()

    def _add_plus_tab(self):
        """Add '+' tab at the end for creating new tabs."""
        # Add empty widget as placeholder
        plus_widget = QWidget()
        self._plus_tab_index = self.tab_widget.addTab(plus_widget, "+")

        # Style the "+" tab to look like a button
        self.tab_widget.tabBar().setTabToolTip(self._plus_tab_index, tr('dlg_new_tab_tooltip'))

        # Make "+" tab non-closable (hide close button)
        self.tab_widget.tabBar().setTabButton(self._plus_tab_index, QTabBar.RightSide, None)
        self.tab_widget.tabBar().setTabButton(self._plus_tab_index, QTabBar.LeftSide, None)

    def _on_tab_bar_clicked(self, index: int):
        """Handle click on tab bar - show menu for '+' tab."""
        # Check if clicked on "+" tab (always last)
        if index == self.tab_widget.count() - 1:
            # Get tab bar position for menu
            tab_bar = self.tab_widget.tabBar()
            tab_rect = tab_bar.tabRect(index)
            global_pos = tab_bar.mapToGlobal(tab_rect.bottomLeft())

            # Store intended position for MenuPositionFixer (fixes rotated monitors)
            self._add_tab_menu._intended_pos = global_pos

            # Show menu below the "+" tab
            self._add_tab_menu.exec_(global_pos)

            # Prevent switching to "+" tab - go back to previous
            if self.tab_widget.count() > 1:
                self.tab_widget.setCurrentIndex(max(0, index - 1))

    def _move_plus_tab_to_end(self):
        """Move '+' tab to the end after adding new tabs."""
        plus_index = self.tab_widget.count() - 1
        # The "+" tab should always be last, so we check if it's not
        # and move it if necessary
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "+":
                if i != self.tab_widget.count() - 1:
                    # Move to end
                    self.tab_widget.tabBar().moveTab(i, self.tab_widget.count() - 1)
                break

    def _create_agent_tabs(self):
        """Create tabs for all auto-start agents.

        Każda zakładka powstaje "leniwie" — _create_agent_tab tworzy tylko
        UI shell (input, przyciski, placeholder terminala). Ciężki QTermWidget
        + bash + claude CLI startują dopiero w AgentTab.activate(), gdy
        użytkownik kliknie w zakładkę (lub gdy zakładka stanie się aktywna
        przy starcie — primary agent poniżej).
        """
        for agent in self.agents:
            if agent.get('auto_start', True):
                self._create_agent_tab(agent)

        # If no tabs created, create default one
        if self.tab_widget.count() == 0:
            default_agent = DEFAULT_AGENTS[0].copy()
            self.agents = [default_agent]
            self._create_agent_tab(default_agent)

        # Wybierz "primary agent" do natychmiastowej aktywacji. Pozostałe
        # zakładki czekają na pierwsze kliknięcie. Priorytet:
        # last_active_agent_id z configu → pierwsza zakładka.
        primary_index = 0
        if getattr(self, 'last_active_agent_id', None):
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if isinstance(widget, AgentTab) and widget.agent_id == self.last_active_agent_id:
                    primary_index = i
                    break
        # NIE polegamy na currentChanged → activate(): pierwsza dodana
        # zakładka już JEST currentIndex=0, więc setCurrentIndex(0) nie
        # emituje sygnału i activate() nigdy by się nie wywołał (placeholder
        # zostaje na ekranie jako czarne tło).
        # Aktywację primary odraczamy QTimerem na "po pokazaniu okna" — bez
        # tego QTermWidget startuje w niezamontowanym kontekście (window jeszcze
        # nie show()-uje się; jesteśmy w __init__) i wyświetla się jako
        # niewidoczny, mimo że bash + claude działają w tle.
        self.tab_widget.setCurrentIndex(primary_index)
        primary_widget = self.tab_widget.widget(primary_index)
        if isinstance(primary_widget, AgentTab) and not primary_widget.is_activated():
            self.last_active_agent_id = primary_widget.agent_id
            QTimer.singleShot(0, primary_widget.activate)

    def _connect_agent_tab_signals(self, agent_tab: AgentTab):
        """Podłącz WSZYSTKIE sygnały zakładki do MainWindow — jedno źródło prawdy.

        Używane przez OBIE ścieżki tworzenia zakładek (_create_agent_tab oraz
        _add_new_terminal). Wcześniej lista połączeń była zdublowana w dwóch
        miejscach i w _add_new_terminal zabrakło `terminal_output` → na
        zakładkach otwartych przyciskiem „+" licznik tokenów nie rósł (wyjście
        terminala nie docierało do _on_terminal_output). Trzymanie listy w
        jednym miejscu eliminuje ten rodzaj „zgubionego kabelka" na przyszłość.
        """
        agent_tab.status_changed.connect(self._update_status)
        agent_tab.request_tts.connect(self._handle_tts_request)
        agent_tab.request_tts_stop.connect(self._stop_all)
        agent_tab.request_pause.connect(self._toggle_pause)
        agent_tab.request_read_last.connect(self._read_last_response)
        agent_tab.request_dictation.connect(self._handle_dictation_request)
        agent_tab.message_sent.connect(self._on_message_sent)
        agent_tab.add_quick_action_requested.connect(self._add_quick_action)
        agent_tab.splitter_changed.connect(
            lambda sizes, tab=agent_tab: self._on_splitter_changed(tab, sizes))
        # Wyjście terminala → liczenie tokenów (per-agent + globalna suma Σ).
        agent_tab.terminal_output.connect(self._on_terminal_output)
        # Sygnał z lazy activate() — terminal właśnie powstał, czas zaaplikować
        # kolory, odpalić claude i wysłać pliki pamięci.
        agent_tab.terminal_ready.connect(
            lambda tab=agent_tab: self._on_terminal_ready(tab))

    def _create_agent_tab(self, agent_config: dict) -> AgentTab:
        """Create a single agent tab (lazy — bez terminala+claude do aktywacji).

        Tworzy tylko UI shell (splitter, input, przyciski, placeholder zamiast
        terminala). Prawdziwy QTermWidget + bash + claude CLI startują dopiero
        gdy zakładka po raz pierwszy stanie się aktywna (currentChanged →
        _on_tab_changed → agent_tab.activate()), co emituje terminal_ready →
        _on_terminal_ready obsługuje kolory + uruchomienie claude + pliki pamięci.
        """
        agent_tab = AgentTab(agent_config, self)

        # Set shared state
        agent_tab.set_shared_state(
            self.skin_colors, self.skin_icons,
            self.auto_read_responses, self.current_language
        )

        # Connect signals — jedno źródło prawdy (patrz _connect_agent_tab_signals)
        self._connect_agent_tab_signals(agent_tab)

        # Add tab (insert before "+" tab which is always last)
        agent_id = agent_config.get('id', 'unknown')
        agent_name = agent_config.get('name', 'Agent')
        self.agent_tabs[agent_id] = agent_tab

        # Insert before "+" tab (if exists), otherwise add at end
        insert_index = max(0, self.tab_widget.count() - 1) if self.tab_widget.count() > 0 else 0
        # Etykieta + ikona zakładki wg pola 'icon' agenta (emoji w tekście / plik jako QIcon).
        tab_label, tab_icon = self._agent_label_icon(agent_config)
        # Check if last tab is "+" tab
        if self.tab_widget.count() > 0 and self.tab_widget.tabText(self.tab_widget.count() - 1) == "+":
            index = self.tab_widget.insertTab(insert_index, agent_tab, tab_label)
        else:
            index = self.tab_widget.addTab(agent_tab, tab_label)
        if not tab_icon.isNull():
            self.tab_widget.setTabIcon(index, tab_icon)
        # NIE wołamy setCurrentIndex tutaj — _create_agent_tabs zrobi to
        # świadomie raz, dla primary agent. Inaczej każda nowa zakładka
        # natychmiast się aktywuje i znowu mamy 4× claude przy starcie.

        # Apply styles (na shell UI — terminal jeszcze nie istnieje)
        agent_tab.apply_styles(self.skin_colors, self.skin_icons)

        # Apply button icon styles to new tab
        self._apply_button_icon_styles()
        # ...oraz same ikony w kolorach skórki (AgentTab tworzy je w kolorze
        # domyślnym, bo nie zna palety).
        self._apply_skin_icons()

        # Kolor tekstu zakładki wg pola 'tab_color' agenta (Funkcja #2).
        self._recolor_all_tabs()

        return agent_tab

    def _add_new_agent(self):
        """Add new agent via dialog."""
        dialog = AgentConfigDialog(self, memory_projects=self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            agent_config = dialog.get_data()
            self._inherit_splitter_sizes(agent_config)
            self.agents.append(agent_config)
            self._save_agents()

            # Only create tab if "Save and run" was clicked
            if dialog.get_run_immediately():
                agent_tab = self._create_agent_tab(agent_config)
                self.tab_widget.setCurrentWidget(agent_tab)
            else:
                # Just saved - will be available after restart
                QMessageBox.information(
                    self, tr('dlg_saved_title'),
                    tr('dlg_agent_saved_msg').format(name=agent_config.get('name'))
                )

    def _add_new_terminal(self):
        """Add a plain Ubuntu terminal tab (no agent features)."""
        # Generate unique terminal ID
        terminal_count = sum(1 for agent_id in self.agent_tabs if agent_id.startswith('terminal-'))
        terminal_id = f"terminal-{terminal_count + 1}"

        # Create plain terminal config (no memory, no auto-start Claude)
        terminal_config = {
            'id': terminal_id,
            'name': f"Terminal {terminal_count + 1}",
            'working_directory': str(Path.home()),
            'memory_project_id': None,
            'auto_start': False,  # Don't auto-run Claude command
            'send_memory_on_start': False,  # No memory files
            'is_plain_terminal': True  # Flag for plain terminal
        }
        self._inherit_splitter_sizes(terminal_config)

        # Create tab (don't save to agents list - it's temporary)
        agent_tab = AgentTab(terminal_config, self)

        # Set shared state
        agent_tab.set_shared_state(
            self.skin_colors, self.skin_icons,
            self.auto_read_responses, self.current_language
        )

        # Connect signals — jedno źródło prawdy (patrz _connect_agent_tab_signals).
        # To tu wcześniej brakowało terminal_output → licznik tokenów nie rósł
        # na zakładkach „+". Teraz obie ścieżki podłączają identyczny zestaw.
        self._connect_agent_tab_signals(agent_tab)

        # Add tab with terminal icon (🖥️ instead of 🤖) - insert before "+" tab
        self.agent_tabs[terminal_id] = agent_tab
        # Insert before "+" tab (if exists)
        if self.tab_widget.count() > 0 and self.tab_widget.tabText(self.tab_widget.count() - 1) == "+":
            insert_index = self.tab_widget.count() - 1
            index = self.tab_widget.insertTab(insert_index, agent_tab, f"🖥️ {terminal_config['name']}")
        else:
            index = self.tab_widget.addTab(agent_tab, f"🖥️ {terminal_config['name']}")

        # WAŻNE: apply_styles MUSI być przed setCurrentIndex.
        # setCurrentIndex → _on_tab_changed → activate() → tworzy QTermWidget.
        # Jeśli apply_styles przyjdzie PO activate, setStyleSheet na main_splitter
        # przelicza geometrię już zamontowanego terminala — efekt: szare pasy po
        # prawej stronie (terminal zostaje przy szerokości sprzed stylowania).
        # Ścieżka kliknięcia w istniejącą zakładkę nie ma tego problemu, bo
        # apply_styles było wywołane przy tworzeniu, dawno przed activate().
        agent_tab.apply_styles(self.skin_colors, self.skin_icons)
        self._apply_button_icon_styles()
        self._apply_skin_icons()

        # Dopiero teraz aktywuj — terminal powstanie w już ostylowanym splitterze.
        self.tab_widget.setCurrentIndex(index)

        self._update_status(tr('status_new_terminal').format(name=terminal_config['name']))

    def _close_agent_tab(self, index: int):
        """Close agent tab."""
        # Don't allow closing "+" tab
        if self.tab_widget.tabText(index) == "+":
            return

        # Must keep at least one real tab (+ doesn't count)
        if self.tab_widget.count() <= 2:
            QMessageBox.warning(self, tr('dlg_cannot_close_title'),
                tr('dlg_must_keep_one_tab'))
            return

        # Get agent tab and remove from dict
        widget = self.tab_widget.widget(index)
        if isinstance(widget, AgentTab):
            agent_id = widget.agent_id
            if agent_id in self.agent_tabs:
                del self.agent_tabs[agent_id]
            if agent_id in self._tab_mru:
                self._tab_mru.remove(agent_id)

        # Gdy zamykamy AKTYWNĄ zakładkę, NAJPIERW przełącz się na ostatnio
        # używaną z pozostałych, a dopiero potem usuń. Bez tego Qt po
        # removeTab samo wybiera sąsiada — przy ostatniej zakładce przed "+"
        # jest nim pusta atrapa "+" (czarna strona), a przy środkowej Qt
        # aktywowałoby (lazy activation → start claude) zakładkę, której
        # użytkownik nie wybrał.
        if index == self.tab_widget.currentIndex():
            target = self._most_recent_tab(exclude=widget)
            if target is not None:
                self.tab_widget.setCurrentWidget(target)

        self.tab_widget.removeTab(index)
        widget.deleteLater()

    def _most_recent_tab(self, exclude=None) -> Optional[AgentTab]:
        """Ostatnio używana z istniejących zakładek (wg historii MRU).

        `exclude` — zakładka pomijana (ta właśnie zamykana; wciąż wisi
        w pasku do czasu removeTab). Fallback (pusta/nieaktualna historia):
        ostatnia prawdziwa zakładka przed atrapą "+" — nigdy sama "+".
        """
        for agent_id in self._tab_mru:
            tab = self.agent_tabs.get(agent_id)
            if tab is not None and tab is not exclude \
                    and self.tab_widget.indexOf(tab) != -1:
                return tab
        for i in range(self.tab_widget.count() - 1, -1, -1):
            candidate = self.tab_widget.widget(i)
            if isinstance(candidate, AgentTab) and candidate is not exclude:
                return candidate
        return None

    def _active_agent_count(self) -> int:
        """Ile zakładek z uruchomionym `claude` jest aktywnych (żre RAM).

        Liczymy tylko aktywowane AgentTab-y będące prawdziwymi agentami —
        zwykłe terminale (is_plain_terminal) nie uruchamiają claude, więc
        nie obciążają pamięci w ten sam sposób i ich nie wliczamy.
        """
        return sum(
            1 for t in self.agent_tabs.values()
            if isinstance(t, AgentTab) and t.is_activated()
            and not getattr(t, 'is_plain_terminal', False)
        )

    def _max_active_agents(self) -> int:
        """Bezpieczny limit jednoczesnych agentów dla RAM tej maszyny.

        Liczony z wykrytego RAM (recommended_max_agents — każdy `claude` to
        3–5 GB). Gdy RAM nieznany → dotychczasowa stała MAX_ACTIVE_AGENTS
        (zachowanie sprzed RAM-aware, brak regresji)."""
        return recommended_max_agents(
            RAM_PER_AGENT_GB, RAM_SYSTEM_RESERVE_GB) or MAX_ACTIVE_AGENTS

    def _confirm_more_agents(self) -> bool:
        """Ostrzeż przed uruchomieniem kolejnego agenta. True = kontynuuj.

        Komunikat dopasowany do maszyny: gdy znamy RAM, podajemy ile GB ma
        komputer i ilu agentów bezpiecznie uniesie; gdy nie znamy — wariant
        bez liczb (klucz _noram)."""
        active = self._active_agent_count()
        total = total_ram_gb()
        if total is not None:
            msg = tr('dlg_many_agents_msg').format(
                active=active,
                recommended=self._max_active_agents(),
                total=int(round(total)),
            )
        else:
            msg = tr('dlg_many_agents_msg_noram').format(active=active)
        reply = QMessageBox.question(
            self,
            tr('dlg_many_agents_title'),
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _revert_tab_activation(self):
        """Wróć do poprzednio aktywnej zakładki bez uruchamiania nowej.

        Wołane gdy użytkownik odmówił uruchomienia kolejnego agenta.
        Poprzednia zakładka (last_active_agent_id) jest już aktywowana, więc
        przełączenie na nią NIE wyzwoli ponownie ostrzeżenia.
        """
        prev_id = getattr(self, 'last_active_agent_id', None)
        prev_tab = self.agent_tabs.get(prev_id) if prev_id else None
        if isinstance(prev_tab, AgentTab):
            idx = self.tab_widget.indexOf(prev_tab)
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)
                return
        # Brak sensownej poprzedniej zakładki — wróć do pierwszej aktywowanej.
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            if isinstance(w, AgentTab) and w.is_activated():
                self.tab_widget.setCurrentIndex(i)
                return

    def _on_tab_changed(self, index: int):
        """Handle tab change.

        Debounce: gdy użytkownik szybko klika między zakładkami (lub gdy
        currentChanged jest emitowane wielokrotnie podczas tworzenia tabów),
        odpalamy ciężkie odświeżanie (set_agent → setStyleSheet w widgecie
        MCP status, refresh context label) raz, dopiero 50ms po ostatniej
        zmianie. Bez tego Intel HD 5500 + XWayland dostawał lawinę
        repaintów, co przyczyniało się do zamarzania kompozytora.

        Lazy activation: jeśli zakładka jeszcze nigdy nie była aktywna,
        woła AgentTab.activate() — to tworzy QTermWidget+bash i (po sygnale
        terminal_ready) startuje claude. Bez tego 4 agenty startują równolegle
        przy uruchomieniu aplikacji i OOM-killer ubija proces.
        """
        # Start aplikacji: pierwszy addTab()/setCurrentIndex emituje currentChanged
        # JESZCZE W __init__ — aktywacja zakładki tutaj tworzy QTermWidget w
        # niezamontowanym kontekście → terminal NIEWIDOCZNY (bash/claude działają
        # w tle, ekran pusty). Primary aktywuje odroczony QTimer w _load_agents.
        # Uwaga historyczna: ten slot przerywał się tu PRZYPADKIEM (AttributeError
        # na status_bar, zanim powstał) — po naprawieniu tamtego crasha guardem
        # w _update_status objaw wrócił (2026-06-10), stąd jawna flaga.
        if not getattr(self, "_ui_ready", False):
            return

        # Zmieniła się aktywna zakładka → przelicz flagi WSZYSTKICH: nowa
        # aktywna gasi ikonę (zobaczyłeś pytanie), a zakładka, z której właśnie
        # zszedłeś, zapali ikonę, jeśli agent w niej wciąż czeka na odpowiedź.
        self._refresh_all_question_flags()

        current = self.tab_widget.currentWidget()
        if isinstance(current, AgentTab):
            if not current.is_activated():
                # Ochrona pamięci: każdy aktywny agent to osobny proces `claude`
                # (3–5 GB RAM). Limit dopasowany do RAM maszyny (_max_active_agents);
                # po przekroczeniu ostrzegamy, zanim uruchomimy kolejny — inaczej
                # kilku agentów zawiesza komputer.
                if self._active_agent_count() >= self._max_active_agents() \
                        and not current.is_plain_terminal:
                    if not self._confirm_more_agents():
                        # Użytkownik zrezygnuje — wracamy do poprzedniej
                        # zakładki BEZ uruchamiania claude w bieżącej.
                        self._revert_tab_activation()
                        return
                self._update_status(f"⏳ {tr('status_starting_agent').format(name=current.agent_name)}")
                current.activate()
            # Zapamiętaj ostatnio aktywnego — zostanie zapisane przez
            # _apply_tab_change → _save_settings (debounced 50ms).
            self.last_active_agent_id = current.agent_id
            # Aktualizuj historię MRU: bieżąca zakładka na początek listy.
            if current.agent_id in self._tab_mru:
                self._tab_mru.remove(current.agent_id)
            self._tab_mru.insert(0, current.agent_id)
        self._update_current_tab_references()
        if not hasattr(self, '_tab_change_debounce'):
            self._tab_change_debounce = QTimer(self)
            self._tab_change_debounce.setSingleShot(True)
            self._tab_change_debounce.timeout.connect(self._apply_tab_change)
        self._tab_change_debounce.start(50)

    def _apply_tab_change(self):
        """Odroczona aktualizacja stanu UI po zmianie zakładki (debounced)."""
        self._update_mcp_status_widget()
        self._refresh_context_label()
        self._handle_active_tab_switch()
        # Funkcja #2: kolor tekstu zakładek + ramka okna w kolorze aktywnego agenta.
        self._recolor_all_tabs()
        self._apply_active_tab_frame()
        # Persist last_active_agent_id (settings JSON jest mały, ~2 KB,
        # zapis przy każdej zmianie zakładki jest niezauważalny).
        self._save_settings()

    def _handle_active_tab_switch(self):
        """Etap 3: po przełączeniu zakładki — tylko aktywna czyta na głos.

        - Zatrzymujemy czytanie (kolejkę) poprzedniej zakładki.
        - Jeśli nowa zakładka ma włączone auto-czytanie i nazbierała zaległości
          (gdy była nieaktywna) — pokazujemy komunikat; doczytanie odpala
          przycisk 🔊 (patrz _read_last_response).
        """
        # Zatrzymaj głos poprzedniej zakładki (jest jeden lektor).
        try:
            self.tts.clear_queue()
        except Exception:
            pass

        tab = self._get_current_agent_tab()
        if not tab:
            return
        backlog = getattr(tab, 'pending_backlog', None) or []
        if getattr(tab, 'auto_read_responses', False) and backlog:
            n = len(backlog)
            self._update_status(tr('status_unread_backlog').format(n=n))

    def _poll_transcripts(self):
        """Etap 3: czytaj nową prozę Claude'a z dziennika sesji (Droga A).

        Co tick: dla aktywnej zakładki z auto-read — nową prozę wysyłamy do
        lektora na żywo. Dla nieaktywnych z auto-read — odkładamy do zaległości.
        Priming: przy pierwszym wykryciu pliku sesji przeskakujemy na jego
        koniec (pomijamy historię i startowe potwierdzenie pamięci).
        """
        tabs = getattr(self, 'agent_tabs', None)
        if not tabs:
            return
        # DIAG: baner startu w logu flagi — odróżnia świeży przebieg od
        # nieaktualnego (throttle _flag_dbg loguje tylko zmiany, więc bez tego
        # nie widać, kiedy zaczął się nowy przebieg). Raz na uruchomienie.
        if _FLAG_DEBUG and not getattr(self, '_flag_dbg_banner', False):
            self._flag_dbg_banner = True
            try:
                with open(CONFIG_DIR / "flag-debug.log", "a", encoding="utf-8") as f:
                    f.write(f"\n===== START {datetime.now():%Y-%m-%d %H:%M:%S} "
                            f"v{APP_VERSION} =====\n")
            except Exception:
                pass
        active = self.tab_widget.currentWidget()

        for tab in list(tabs.values()):
            if not isinstance(tab, AgentTab):
                continue
            reader = getattr(tab, '_transcript_reader', None)
            if reader is None:
                # DIAG: rozróżnij „zakładki nie kliknięto" (leniwa aktywacja —
                # aktyw=0) od zwykłego terminala/awarii tworzenia czytnika.
                self._flag_dbg(
                    tab,
                    "reader=None aktyw={} plain={} pin={}".format(
                        int(bool(getattr(tab, '_terminal_ready_handled', False))),
                        int(bool(getattr(tab, 'is_plain_terminal', False))),
                        getattr(tab, '_pinned_session_id', None) or '-',
                    ),
                )
                continue
            try:
                if not reader.has_session():
                    # DIAG: pokaż przypięty uuid, oczekiwany plik i czy istnieje —
                    # rozróżni „claude nie utworzył przypiętego pliku" od reszty.
                    if _FLAG_DEBUG:
                        st = reader.debug_state()
                        self._flag_dbg(
                            tab,
                            "has_session=N pin={} dir={} plik={} istnieje={}".format(
                                st['pinned'] or '-', st['project_dir'] or '-',
                                st['expected'] or '-', int(st['exists']),
                            ),
                        )
                    continue
                # Priming — pomiń to, co było przed startem czytania.
                if not getattr(tab, '_transcript_primed', False):
                    reader.seek_to_end()
                    tab._transcript_primed = True
                    self._flag_dbg(tab, "priming (pierwszy tick — pomijam)")
                    continue
                # Flaga "?": czy agent ZATRZYMAŁ się i czeka na odpowiedź?
                # Sprawdzane KAŻDY tick (nie zależy od nowej prozy) — stan
                # "czeka" zmienia się też bez nowego tekstu (tool_use, zgoda).
                # Liczone niezależnie od aktywności; ikona pokaże się dopiero,
                # gdy zakładka nie jest na wierzchu (patrz _refresh_question_flag).
                #
                # Wymagane są OBIE cisze naraz:
                #  • dziennika (reader.waiting_for_user) — ale dziennik dostaje
                #    tylko UKOŃCZONE wpisy, więc stoi też podczas myślenia/
                #    pisania/narzędzi (zmierzone: 20 s ciszy W TRAKCIE pisania
                #    odpowiedzi) — sama z siebie zapalała flagę przy każdej
                #    dłuższej pracy agenta;
                #  • TERMINALA (puls aktywności) — pracujący Claude Code animuje
                #    pasek (spinner + licznik sekund ~1×/s), więc dane płyną
                #    ciągle; czekający — ekran stoi. To czujnik ruchu, NIE
                #    czytanie treści (treści z terminala nie parsujemy — kruche).
                # reader.waiting_for_user() wołamy ZAWSZE (nie za '... and'),
                # żeby jego wewnętrzny licznik stabilności był świeży.
                journal_quiet = reader.waiting_for_user()
                _term_idle = time.monotonic() - getattr(tab, '_last_terminal_data_ts', 0.0)
                terminal_quiet = _term_idle >= self.QUESTION_TERMINAL_QUIET_SECS
                _armed = journal_quiet and terminal_quiet
                _active = tab is self.tab_widget.currentWidget()
                self._flag_dbg(
                    tab,
                    f"jq={int(journal_quiet)} term_idle={_term_idle:.1f}s "
                    f"tq={int(terminal_quiet)} ARMED={int(_armed)} "
                    f"active={int(_active)} SHOW={int(_armed and not _active)}",
                )
                self._arm_question(tab, _armed)

                new_blocks = reader.poll()
            except Exception:
                continue
            if not new_blocks:
                continue

            proses = []
            for raw in new_blocks:
                p = prose_from_markdown(raw)
                if p and len(p.strip()) >= 2:
                    proses.append(p)
            if not proses:
                continue

            if tab is active:
                if getattr(tab, 'auto_read_responses', False):
                    # Funkcja #3: czytaj głosem tej (aktywnej) zakładki.
                    v = self._agent_voice(tab)
                    if v:
                        self.tts.set_voice(v)
                    for p in proses:
                        self.tts.enqueue(p)
                # aktywna, ale auto-read wyłączone → nie czytamy, nie zbieramy
            else:
                if getattr(tab, 'auto_read_responses', False):
                    tab.pending_backlog.extend(proses)
                    # Ogranicz rozrost (trzymamy ostatnie 50 wypowiedzi).
                    if len(tab.pending_backlog) > 50:
                        tab.pending_backlog = tab.pending_backlog[-50:]

    def _on_terminal_ready(self, agent_tab):
        """Slot wywoływany po AgentTab.activate() — terminal właśnie powstał.

        Wykonuje to, co dawniej robił deferred lambda w _create_agent_tab:
        1. zaaplikuj kolory terminala (CustomSkin),
        2. uruchom komendę `claude` (jeśli auto_start lub _force_start),
        3. po 8s wyślij pliki pamięci (jeśli send_memory_on_start).

        Bash potrzebuje chwili na rozruch — komenda claude leci po 500ms,
        pliki pamięci po 8500ms (8 s od claude, jak w starej logice).
        """
        # Guard idempotencji: terminal_ready bywa emitowany >1× w pewnych
        # ścieżkach (reentrancy z QSplitter.replaceWidget + deleteLater wewnątrz
        # activate(), event-processing w trakcie zmiany drzewa widgetów). Bez
        # tego guardu każde wywołanie dodaje nowy QTimer(claude) + QTimer(memory),
        # czego efektem jest 2× banner Claude Code i 2× "Przeczytaj pliki
        # pamięci..." w jednym terminalu (zgłoszenie 2026-05-14, po wdrożeniu
        # lazy activation w commicie 3aa5e35). Wzorzec symetryczny do _activated
        # w AgentTab.activate() i _memory_sent w AgentTab.send_memory_files() —
        # uzupełniamy brakujący trzeci, środkowy guard.
        if getattr(agent_tab, '_terminal_ready_handled', False):
            return
        agent_tab._terminal_ready_handled = True

        if agent_tab.terminal_backend:
            self._apply_terminal_colors(self.skin_colors, agent_tab.terminal_backend)

        # _force_start jest flagą tymczasową ustawianą przez AgentsManagerDialog
        # gdy user kliknął "Uruchom" przy zapisanym agencie z auto_start=False.
        agent_config = agent_tab.agent_config
        force_start = agent_config.pop('_force_start', False)

        claude_started = False
        if (agent_tab.auto_start or force_start) and self.claude_command:
            QTimer.singleShot(
                500,
                lambda: self._run_claude_in_tab(agent_tab, force=force_start)
            )
            claude_started = True

        if claude_started and agent_config.get('send_memory_on_start', True):
            QTimer.singleShot(8500, agent_tab.send_memory_files)

        # Etap 3: utwórz czytnik dziennika dla tej zakładki (poza zwykłym
        # terminalem, który nie ma sesji claude). Priming (przeskok na koniec,
        # by pominąć historię/startowe potwierdzenie pamięci) robi pętla
        # _poll_transcripts przy pierwszym wykryciu pliku sesji.
        if not getattr(agent_tab, 'is_plain_terminal', False):
            try:
                agent_tab._transcript_reader = TranscriptReader(agent_tab.working_directory)
                agent_tab._transcript_primed = False
                # Gdyby komenda claude (z --session-id) zbudowała się wcześniej,
                # podepnij już znany identyfikator sesji do świeżego czytnika.
                _pinned = getattr(agent_tab, '_pinned_session_id', None)
                if _pinned:
                    agent_tab._transcript_reader.pin_session(_pinned)
            except Exception:
                agent_tab._transcript_reader = None

        # Po faktycznym powstaniu terminala: jeśli to AKTYWNA zakładka, odśwież
        # referencje MainWindow (self.terminal_backend itd.). Przy starcie primary
        # tab (index 0) activate() jest odroczone QTimerem i wykonuje się PO
        # _update_current_tab_references() z __init__, a setCurrentIndex(0) nie
        # emituje currentChanged (Qt deduplikuje) → bez tego self.terminal_backend
        # zostaje None aż do pierwszej zmiany zakładki, więc 🔊/⧉ nie widzą
        # zaznaczenia tuż po uruchomieniu. Guard chroni przed nadpisaniem
        # referencji, gdyby w tle aktywowała się nieaktywna zakładka.
        if agent_tab is self._get_current_agent_tab():
            self._update_current_tab_references()

    def _update_mcp_status_widget(self):
        """Synchronizuje widget statusu agenta z aktywną zakładką.

        Przekazuje 4 informacje: working_dir, agent_name, agent_id,
        memory_files, model — widget sam aktualizuje wszystkie 4 liczniki.
        """
        # Guard: _create_agent_tabs() w __init__ emituje currentChanged ZANIM
        # self.mcp_status_widget zostanie utworzony (kilka dziesiątek linii
        # poniżej). Bez tego guard'u Python wyrzuca AttributeError przy każdym
        # starcie aplikacji (czasem 4+ razy), excepthook tylko drukuje, ale
        # event loop Qt zostaje w niespójnym stanie — to był jeden z głównych
        # winowajców zamarzania całego systemu (XWayland + Mutter starvation).
        if not hasattr(self, 'mcp_status_widget'):
            return
        current = self.tab_widget.currentWidget()
        if isinstance(current, AgentTab):
            self.mcp_status_widget.set_agent(
                Path(current.working_directory) if current.working_directory else None,
                agent_name=current.agent_name,
                agent_id=current.agent_id,
                memory_files=current.memory_files,
                model_key=current.model,
            )
        else:
            self.mcp_status_widget.set_agent(None)

    def _open_mcp_manager_for_dir(self, working_dir):
        """Slot dla request_open_manager z McpStatusWidget."""
        if working_dir is None:
            return
        # Scoped manager dla bieżącego agenta
        current = self.tab_widget.currentWidget()
        agent_name = current.agent_name if isinstance(current, AgentTab) else None
        dialog = McpManagerDialog(self, working_dir=Path(working_dir), agent_name=agent_name)
        dialog.exec_()
        self.mcp_status_widget.force_refresh()

    def _open_skills_manager_from_status(self):
        """Slot dla request_open_skills z McpStatusWidget — kliknięcie 🧩."""
        self._show_skills_manager_dialog()
        # Po zamknięciu dialogu skille mogły się zmienić → odśwież widget
        self.mcp_status_widget.force_refresh()

    def _open_edit_agent_from_status(self, agent_id: str):
        """Slot dla request_edit_agent z McpStatusWidget — kliknięcie 📁 lub 🤖.

        Otwiera Menedżer agentów (dialog edycji konkretnego agenta nie istnieje
        jako osobny entrypoint — najbliższe miejsce edycji to ten menedżer).
        """
        if not agent_id:
            return
        self._show_agents_manager_dialog()
        # Po zamknięciu konfig mógł się zmienić → odśwież widget
        self._update_mcp_status_widget()

    def _update_current_tab_references(self):
        """Update references to current tab's widgets."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, AgentTab):
            self.terminal_backend = current_tab.terminal_backend
            self.terminal = current_tab.terminal
            self.conversation_area = current_tab.conversation_area
            self.bottom_panel = current_tab.bottom_panel
            self.input_field = current_tab.input_field
            self._terminal_output_buffer = current_tab._terminal_output_buffer

    def _get_current_agent_tab(self) -> Optional[AgentTab]:
        """Get current agent tab."""
        current = self.tab_widget.currentWidget()
        if isinstance(current, AgentTab):
            return current
        return None

    def _handle_tts_request(self, text: str):
        """Handle TTS request from agent tab."""
        if text.strip():
            # Clean text for TTS
            text_cleaner = TextCleanerForTTS(self.current_language)
            cleaned_text = text_cleaner.clean(text, use_dictionary=False)
            if cleaned_text:
                self.tts.speak(cleaned_text)
                self._update_status(tr('reading'))

    def _handle_dictation_request(self, start: bool):
        """Handle dictation request from agent tab."""
        if start:
            self._toggle_dictation()
        else:
            self._toggle_dictation()

    def _on_message_sent(self, message: str):
        """Handle message sent from agent tab."""
        # Odpowiedziałeś agentowi → rozbrój flagę "?" od razu (nie czekaj na
        # następny tick poll). Dziennik i tak potwierdzi to przy kolejnym
        # sprawdzeniu (plik rośnie → waiting_for_user()=False).
        src_tab = self.sender()
        if isinstance(src_tab, AgentTab):
            self._arm_question(src_tab, False)

        # Wykryj komendy Claude Code, które resetują kontekst rozmowy:
        # /clear (czyści historię) i /compact (kompaktuje, zaczyna od nowa).
        # Sprawdzamy pierwsze słowo, by nie reagować na np. "/clearance".
        first_word = message.strip().split(maxsplit=1)[0] if message.strip() else ""
        if first_word in ("/clear", "/compact"):
            self._reset_context_usage()
            return
        self._update_context_usage(len(message))

    def _show_memory_projects_dialog(self):
        """Show memory projects management dialog."""
        dialog = MemoryProjectsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.memory_projects = dialog.get_memory_projects()

    def _show_skills_manager_dialog(self):
        """Show skills manager dialog (Claude Code skills in ~/.claude/skills/)."""
        dialog = SkillsManagerDialog(self)
        dialog.exec_()

    def _show_mcp_manager_dialog(self):
        """Show MCP servers manager dialog (global scope)."""
        dialog = McpManagerDialog(self)
        dialog.exec_()
        # Globalne zmiany mogą wpłynąć na status bieżącego agenta — odśwież.
        self.mcp_status_widget.force_refresh()

    def _refresh_open_agent_tabs(self):
        """Po edycji w menedżerze: zaktualizuj NA ŻYWO otwarte zakładki istniejących
        agentów (nazwa, ikona, config) — bez restartu. Dopasowanie po agent_id.

        Ikonę pomijamy, gdy świeci flaga „?" (zostanie przywrócona z nowego
        configu po jej zniknięciu — patrz _refresh_question_flag)."""
        by_id = {a.get('id'): a for a in self.agents if isinstance(a, dict)}
        for agent_id, tab in list(self.agent_tabs.items()):
            if not isinstance(tab, AgentTab):
                continue
            cfg = by_id.get(agent_id)
            if not cfg:
                continue
            tab.update_config(cfg)
            index = self.tab_widget.indexOf(tab)
            if index < 0:
                continue
            # Nazwę, ikonę I flagę („?" żółta na ikonie) ustawia spójnie
            # _refresh_question_flag. Reset sygnatury wymusza ponowne nałożenie po
            # edycji (nowa nazwa/ikona), mimo strażnika no-op.
            tab._flag_sig = None
            self._refresh_question_flag(tab)
        # Funkcja #2: po edycji kolor zakładki/ramki mógł się zmienić.
        self._recolor_all_tabs()
        self._apply_active_tab_frame()

    def _show_agents_manager_dialog(self):
        """Show agents manager dialog."""
        dialog = AgentsManagerDialog(self, self.agents, self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            self.agents = dialog.get_agents()
            self._refresh_open_agent_tabs()  # edycje istniejących agentów na żywo
            agents_to_run = dialog.get_agents_to_run()

            # Create tabs for agents marked for immediate run
            last_tab = None
            for agent in agents_to_run:
                # Remove temporary flag
                agent.pop('_run_immediately', None)
                self._inherit_splitter_sizes(agent)
                # Create tab and switch to it
                last_tab = self._create_agent_tab(agent)

            self._save_agents()

            # Show appropriate message
            if agents_to_run:
                if last_tab:
                    self.tab_widget.setCurrentWidget(last_tab)
            else:
                # Edycje istniejących agentów zostały już nałożone NA ŻYWO na
                # otwarte zakładki (_refresh_open_agent_tabs wyżej) — nazwa,
                # ikona, kolor, głos. Dawny modal „po restarcie" był mylący;
                # zastępujemy go nieinwazyjnym komunikatem na pasku statusu.
                self._update_status(tr('status_agents_saved'))
        # MCP toggle / lokalne MCP w dialogu agenta zapisywane są na bieżąco —
        # odśwież status żeby panel pokazał aktualne dane.
        self.mcp_status_widget.force_refresh()

    def _populate_add_tab_menu(self):
        """(Re)buduje pozycje menu rozwijanego zakładki „+" w bieżącym języku.

        Usuwa stare akcje (i ich skróty) PRZED odbudową — patrz uwaga o kumulacji
        skrótów w _update_ui_language."""
        for a in self._add_tab_menu.actions():
            a.setShortcut(QKeySequence())
            a.deleteLater()
        self._add_tab_menu.clear()

        new_agent_action = QAction(f"🤖 {tr('menu_new_agent')}", self)
        new_agent_action.setShortcut(QKeySequence("Ctrl+T"))
        new_agent_action.triggered.connect(self._add_new_agent)
        self._add_tab_menu.addAction(new_agent_action)

        new_terminal_action = QAction(f"🖥️ {tr('menu_new_terminal')}", self)
        new_terminal_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        new_terminal_action.triggered.connect(self._add_new_terminal)
        self._add_tab_menu.addAction(new_terminal_action)

        self._add_tab_menu.addSeparator()

        manage_agents_action = QAction(tr('menu_manage_agents'), self)
        manage_agents_action.triggered.connect(self._show_agents_manager_dialog)
        self._add_tab_menu.addAction(manage_agents_action)

    def _create_menu_bar(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(tr('menu_file'))

        new_session = QAction(tr('menu_new_session'), self)
        new_session.setShortcut("Ctrl+N")
        new_session.triggered.connect(self._new_session)
        file_menu.addAction(new_session)

        file_menu.addSeparator()

        exit_action = QAction(tr('menu_exit'), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Agents menu
        agents_menu = menubar.addMenu(tr('menu_tabs'))

        new_agent_action = QAction(f"➕ {tr('menu_new_agent')}", self)
        new_agent_action.setShortcut("Ctrl+T")
        new_agent_action.triggered.connect(self._add_new_agent)
        agents_menu.addAction(new_agent_action)

        new_terminal_action = QAction(f"🖥️ {tr('menu_new_terminal')}", self)
        new_terminal_action.setShortcut("Ctrl+Shift+T")
        new_terminal_action.triggered.connect(self._add_new_terminal)
        agents_menu.addAction(new_terminal_action)

        agents_menu.addSeparator()

        manage_agents_action = QAction(tr('menu_manage_agents'), self)
        manage_agents_action.triggered.connect(self._show_agents_manager_dialog)
        agents_menu.addAction(manage_agents_action)

        # Memory projects menu hidden - files are now managed directly in agent config
        # memory_projects_action = QAction("📁 Pliki pamięci projektów...", self)
        # memory_projects_action.triggered.connect(self._show_memory_projects_dialog)
        # agents_menu.addAction(memory_projects_action)

        # Settings menu (Język, Skills, MCP, API keys, Claude command)
        settings_menu = menubar.addMenu(tr('settings'))

        # Submenu Język (przeniesione z top-level — używane przez _set_language
        # i pętlę aktualizującą checkmarki w l. ~1383).
        self.language_menu = settings_menu.addMenu(f"🌐 {tr('language')}")
        self.language_actions = {}
        for code, (native, english, voice) in SUPPORTED_LANGUAGES.items():
            action = QAction(f"{native} ({english})", self)
            action.setCheckable(True)
            action.setChecked(code == self.current_language)
            action.triggered.connect(lambda checked, c=code: self._set_language(c))
            self.language_menu.addAction(action)
            self.language_actions[code] = action

        settings_menu.addSeparator()

        skills_action = QAction(f"🧩 {tr('menu_skills')}", self)
        skills_action.triggered.connect(self._show_skills_manager_dialog)
        settings_menu.addAction(skills_action)

        mcp_action = QAction(f"🔌 {tr('menu_mcp')}", self)
        mcp_action.triggered.connect(self._show_mcp_manager_dialog)
        settings_menu.addAction(mcp_action)

        settings_menu.addSeparator()

        # UI / aplikacja (przeniesione z dawnego menu Edycja)
        skin_colors_action = QAction(f"🎨 {tr('menu_skin_colors')}", self)
        skin_colors_action.triggered.connect(self._show_skin_settings)
        settings_menu.addAction(skin_colors_action)

        settings_menu.addSeparator()

        groq_api_action = QAction(tr('menu_groq_api'), self)
        groq_api_action.triggered.connect(self._show_groq_api_dialog)
        settings_menu.addAction(groq_api_action)

        anthropic_api_action = QAction(tr('menu_anthropic_api'), self)
        anthropic_api_action.triggered.connect(self._show_anthropic_api_dialog)
        settings_menu.addAction(anthropic_api_action)

        settings_menu.addSeparator()

        claude_command_action = QAction(tr('menu_claude_command'), self)
        claude_command_action.triggered.connect(self._show_claude_command_dialog)
        settings_menu.addAction(claude_command_action)

        settings_menu.addSeparator()

        # Szybkie akcje na samym dole — to ergonomia użytkowania, oddzielona
        # od konfiguracji systemowej (klucze API, komenda Claude Code).
        manage_actions = QAction(tr('menu_manage_actions'), self)
        manage_actions.triggered.connect(self._manage_quick_actions)
        settings_menu.addAction(manage_actions)

        # Help menu
        help_menu = menubar.addMenu(tr('menu_help'))

        about_action = QAction(tr('menu_about'), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        claude_setup_action = QAction(tr('menu_claude_setup'), self)
        claude_setup_action.triggered.connect(self._show_claude_setup_dialog)
        help_menu.addAction(claude_setup_action)

        agents_guide_action = QAction(tr('menu_agents_guide'), self)
        agents_guide_action.triggered.connect(self._open_agents_guide)
        help_menu.addAction(agents_guide_action)

        license_action = QAction(tr('menu_license'), self)
        license_action.triggered.connect(self._show_license_dialog)
        help_menu.addAction(license_action)

        help_menu.addSeparator()

        check_updates_action = QAction(tr('menu_check_updates'), self)
        check_updates_action.triggered.connect(self._check_updates_manual)
        help_menu.addAction(check_updates_action)

        self.auto_update_action = QAction(tr('menu_auto_update'), self)
        self.auto_update_action.setCheckable(True)
        self.auto_update_action.setChecked(getattr(self, 'auto_check_updates', True))
        self.auto_update_action.toggled.connect(self._on_auto_check_updates_toggled)
        help_menu.addAction(self.auto_update_action)

    def _setup_connections(self):
        """Setup signal connections (thread-safe via SignalBridge)."""
        # Connect SignalBridge signals to GUI slots (thread-safe)
        self.signals.output_received.connect(self._on_claude_output)
        self.signals.response_received.connect(self._on_claude_response)
        self.signals.error_received.connect(self._on_claude_error)
        self.signals.tts_state_changed.connect(self._on_tts_state_changed)
        self.signals.tts_finished.connect(self._on_tts_finished)
        self.signals.stt_state_changed.connect(self._on_stt_state_changed)
        self.signals.stt_transcription.connect(self._on_transcription)
        self.signals.stt_error.connect(self._on_stt_error)

        # Claude bridge - emit signals instead of direct callbacks
        self.claude.connect_output(lambda t: self.signals.output_received.emit(t))
        self.claude.connect_response(lambda t: self.signals.response_received.emit(t))
        self.claude.connect_error(lambda t: self.signals.error_received.emit(t))

        # TTS - emit signals instead of direct callbacks
        self.tts.on_state_changed = lambda s: self.signals.tts_state_changed.emit(s)
        self.tts.on_finished = lambda: self.signals.tts_finished.emit()

        # STT - emit signals instead of direct callbacks
        self.stt.on_state_changed = lambda s: self.signals.stt_state_changed.emit(s)
        self.stt.on_transcription = lambda t: self.signals.stt_transcription.emit(t)
        self.stt.on_error = lambda e: self.signals.stt_error.emit(e)

        # Auto-aktualizacja (M3) — wynik sprawdzania wraca z wątku tła tu.
        self.update_manager.update_available.connect(self._on_update_available)
        self.update_manager.no_update.connect(self._on_no_update)
        self.update_manager.check_failed.connect(self._on_update_check_failed)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Ctrl+Enter to send
        # Ctrl+D to dictate
        # Ctrl+R to read
        # Escape to stop
        pass

    # ==================== Kreator instalacji Claude Code ====================

    def _claude_cli_available(self) -> bool:
        """Czy skonfigurowana komenda Claude Code realnie istnieje w systemie.

        `claude_command` bywa pełną ścieżką (także ze spacjami — Windows) albo
        gołą nazwą rozwiązywaną przez PATH; sprawdzamy oba warianty."""
        import shutil
        cmd = (self.claude_command or "").strip()
        if not cmd:
            return False
        try:
            if Path(cmd).exists():
                return True
        except Exception:
            pass
        first = cmd.split()[0]
        if shutil.which(first):
            return True
        try:
            return Path(first).exists()
        except Exception:
            return False

    def _compute_readiness(self) -> dict:
        """Policz gotowość programu w 3 punktach. Może chwilę potrwać (powłoka
        logowania przy wykrywaniu `claude`), dlatego przy starcie wołane w wątku
        tła; przez „Sprawdź ponownie" w kreatorze — synchronicznie."""
        from core.platform_utils import (
            claude_runnable, claude_logged_in, find_claude_command)
        installed = claude_runnable(self.claude_command)
        return {
            'claude_installed': installed,
            'claude_logged_in': claude_logged_in() if installed else False,
            'dictation': bool(self.stt.api_key),
            'claude_command_path': find_claude_command() if installed else None,
        }

    def _maybe_show_claude_setup(self):
        """Przy starcie policz gotowość w TLE (nie zamrażaj okna), a po wyniku
        ewentualnie pokaż kreator. Raz na uruchomienie."""
        if getattr(self, '_claude_setup_shown', False):
            return
        import threading
        threading.Thread(
            target=lambda: self._readiness_ready.emit(self._compute_readiness()),
            daemon=True).start()

    def _on_readiness_checked(self, readiness):
        """Wynik z wątku tła (wątek GUI). Pokaż kreator TYLKO gdy czegoś brakuje:
        Claude Code, logowanie albo dyktowanie (chyba że user zaznaczył
        „nie przypominaj o dyktowaniu")."""
        if getattr(self, '_claude_setup_shown', False):
            return
        r = readiness or {}
        # Komenda mogła rozwiązać się do konkretnej ścieżki — przejmij ją cicho.
        path = r.get('claude_command_path')
        if r.get('claude_installed') and path and path != self.claude_command:
            self.claude_command = path
            self._save_settings()
        need = (not r.get('claude_installed')
                or not r.get('claude_logged_in')
                or (not r.get('dictation') and not self.dictation_reminder_dismissed))
        if not need:
            return
        self._claude_setup_shown = True
        self._show_claude_setup_dialog(readiness=r)

    def _show_claude_setup_dialog(self, readiness=None):
        """Kreator konfiguracji = lista kontrolna (też ręcznie z menu Pomoc).
        Bez podanego stanu (otwarcie z menu) — policz teraz, synchronicznie."""
        # Sygnał `triggered` z menu przekazuje bool `checked` — odfiltruj go.
        if not isinstance(readiness, dict):
            readiness = self._compute_readiness()
        dlg = ClaudeSetupDialog(
            self, readiness=readiness,
            dictation_dismissed=self.dictation_reminder_dismissed,
            readiness_provider=self._compute_readiness)
        dlg.claude_found.connect(self._on_claude_cli_found)
        dlg.open_groq_settings.connect(self._show_groq_api_dialog)
        dlg.dictation_reminder_changed.connect(self._on_dictation_reminder_changed)
        dlg.exec_()

    def _on_dictation_reminder_changed(self, dismissed: bool):
        """Zapamiętaj wybór „nie przypominaj o dyktowaniu" (trwale w configu)."""
        self.dictation_reminder_dismissed = bool(dismissed)
        self._save_settings()

    def _open_agents_guide(self):
        """Instrukcja online „Zarządzaj agentami" (publiczna podstrona /cva)."""
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        from config import install_guide_url
        QDesktopServices.openUrl(QUrl(install_guide_url('agenci')))

    def _on_claude_cli_found(self, path: str):
        """Kreator znalazł CLI — przejmij ścieżkę bez restartu aplikacji."""
        self.claude_command = path
        self._save_settings()
        self._update_status(tr('status_claude_found').format(path=path))

    # ==================== Auto-aktualizacja (M3) ====================

    def _check_updates_manual(self):
        """Ręczne 'Sprawdź aktualizacje' z menu — pokazuje też wynik negatywny."""
        self._manual_update_check = True
        self._update_status(tr('status_checking_updates'))
        self.update_manager.check_async()

    def _maybe_auto_check_updates(self):
        """Ciche sprawdzenie przy starcie (jeśli włączone w ustawieniach)."""
        if getattr(self, 'auto_check_updates', True):
            self._manual_update_check = False
            self.update_manager.check_async()

    def _on_update_available(self, info):
        """Jest nowsza wersja. Zapalamy lampkę „nowa wersja" w pasku ORAZ
        automatycznie otwieramy okno pobierania:
          - ręczne sprawdzenie z menu → zawsze,
          - start / cykliczne sprawdzanie (co ~30 min) → RAZ na daną wersję
            (żeby okno nie wyskakiwało w kółko; lampka zostaje jako przypomnienie,
            klik w nią znów otwiera okno)."""
        was_manual = self._manual_update_check
        self._manual_update_check = False
        self._update_status("")
        # Lampka — niezależnie od trybu (zostaje jako przypomnienie).
        self._pending_update_info = info
        if hasattr(self, '_update_indicator'):
            self._update_indicator.setVisible(True)
        already_prompted = (self._prompted_update_version == info.version)
        if was_manual or not already_prompted:
            self._prompted_update_version = info.version
            self._show_update_dialog(info)

    def _show_update_dialog(self, info):
        """Otwórz okno pobierania/instalacji dla danej aktualizacji."""
        dlg = UpdateAvailableDialog(self.update_manager, info, APP_VERSION, self)
        dlg.exec_()

    def _open_pending_update(self):
        """Klik w lampkę „nowa wersja" — otwórz okno dla zapamiętanej wersji."""
        info = getattr(self, '_pending_update_info', None)
        if info is not None:
            self._show_update_dialog(info)

    def _on_no_update(self):
        """Brak nowszej — informuj tylko, gdy użytkownik sprawdzał ręcznie."""
        if self._manual_update_check:
            self._manual_update_check = False
            QMessageBox.information(
                self, "Aktualizacje", f"Masz najnowszą wersję ({APP_VERSION}).")
        self._update_status("")

    def _on_update_check_failed(self, msg):
        """Błąd sprawdzania — komunikat tylko przy ręcznym; przy cichym milczy."""
        if self._manual_update_check:
            self._manual_update_check = False
            QMessageBox.warning(
                self, "Aktualizacje",
                f"Nie udało się sprawdzić aktualizacji.\n\n{msg}")
        self._update_status("")

    def _on_auto_check_updates_toggled(self, checked):
        """Przełącznik 'Sprawdzaj przy starcie' z menu."""
        self.auto_check_updates = bool(checked)
        self._save_settings()

    def _apply_dark_theme(self):
        """Apply dark theme using custom skin colors and icons."""
        # Use the apply_skin_colors method with current skin colors
        self.apply_skin_colors(self.skin_colors)
        # Apply custom icons to buttons
        self._apply_skin_icons()

    def _load_settings(self):
        """Load settings from file."""
        self.anthropic_api_key = ""  # Initialize
        # Pierwszy start (brak zapisanego configu) → język wg systemu:
        # angielski system = interfejs EN, każdy inny = PL. Zapisany 'language'
        # (poniżej) ma pierwszeństwo, więc obecni użytkownicy zostają na swoim.
        self.current_language = detect_system_language()

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    settings = json.load(f)
                    self.current_language = settings.get('language', self.current_language)
                    self.auto_read_responses = settings.get('auto_read', False)

                    # Skórka: wczytaj zapisaną TYLKO gdy pochodzi z bieżącego
                    # schematu. Starsza (np. motyw Ubuntu sprzed redesignu)
                    # jest porzucana na rzecz nowych domyślnych — inaczej stare
                    # kolory z config.json przykryłyby nowy motyw i użytkownik
                    # nie zobaczyłby żadnej zmiany. Kopia zapasowa poniżej.
                    saved_version = settings.get('skin_version', 1)
                    if saved_version >= SKIN_VERSION:
                        saved_skin = settings.get('skin_colors', {})
                        for key in DEFAULT_SKIN_COLORS:
                            if key in saved_skin:
                                self.skin_colors[key] = saved_skin[key]
                    elif settings.get('skin_colors'):
                        self._backup_config_before_skin_migration(settings, saved_version)

                    # Ikony przycisków NIE podlegają migracji — to własne napisy
                    # i emoji użytkownika (np. „Poszło" na przycisku wysyłania),
                    # niezależne od palety. Zmiana motywu nie ma ich kasować.
                    saved_icons = settings.get('skin_icons', {})
                    for key in DEFAULT_SKIN_ICONS:
                        if key in saved_icons:
                            self.skin_icons[key] = saved_icons[key]

                    # Set STT language
                    lang_code = self.current_language.split('-')[0]
                    self.stt.set_language(lang_code)

                    # Set TTS voice
                    if self.current_language in SUPPORTED_LANGUAGES:
                        voice = SUPPORTED_LANGUAGES[self.current_language][2]
                        self.tts.set_voice(voice)

                    # Set Groq API key
                    api_key = settings.get('groq_api_key', GROQ_API_KEY)
                    self.stt.set_api_key(api_key)

                    # Set Anthropic API key
                    self.anthropic_api_key = settings.get('anthropic_api_key', '')

                    # Load Claude command settings (domyślnie wieloplatformowo)
                    self.claude_command = settings.get('claude_command', CLAUDE_COMMAND)
                    self.auto_run_claude = settings.get('auto_run_claude', True)
                    self.last_active_agent_id = settings.get('last_active_agent_id', None)
                    self.auto_check_updates = settings.get('auto_check_updates', True)
                    self.dictation_reminder_dismissed = settings.get(
                        'dictation_reminder_dismissed', False)

            except Exception as e:
                print(f"Error loading settings: {e}")

        # Zsynchronizuj globalny język tłumacza (config.t) z wynikiem powyżej —
        # zanim powstaną menu i zakładki (kolejność w __init__: load → setup_ui).
        set_ui_language(self.current_language)

    def _backup_config_before_skin_migration(self, settings: dict, old_version: int):
        """Zachowaj poprzednie KOLORY, zanim zastąpi je nowy motyw domyślny.

        Zapisuje tylko klucze skórki (nie cały config — tam siedzą klucze API).
        Plik jest jednorazowy per wersja, więc kolejne starty go nie nadpisują
        świeżo zmigrowanymi wartościami. Kto miał własną paletę, odtworzy ją
        stąd ręcznie w oknie „Skórka".
        """
        backup = CONFIG_FILE.with_suffix(f'.skin-v{old_version}.bak')
        if backup.exists():
            return
        try:
            with open(backup, 'w') as f:
                json.dump({
                    'skin_version': old_version,
                    'skin_colors': settings.get('skin_colors', {}),
                    'skin_icons': settings.get('skin_icons', {}),
                }, f, indent=2, ensure_ascii=False)
            print(f"Skórka zmigrowana do v{SKIN_VERSION}; poprzednia zapisana w {backup}")
        except Exception as e:
            print(f"Nie udało się zapisać kopii starej skórki: {e}")

    def _save_settings(self):
        """Save settings to file."""
        settings = {
            'language': self.current_language,
            'auto_read': self.auto_read_responses,
            'groq_api_key': self.stt.api_key,
            'anthropic_api_key': getattr(self, 'anthropic_api_key', ''),
            'skin_version': SKIN_VERSION,     # patrz _load_settings (migracja)
            'skin_colors': self.skin_colors,  # Zawiera kolory interfejsu + terminala
            'skin_icons': self.skin_icons,    # Zawiera ikony przycisków
            'claude_command': self.claude_command,
            'auto_run_claude': self.auto_run_claude,
            'last_active_agent_id': self.last_active_agent_id,
            'auto_check_updates': getattr(self, 'auto_check_updates', True),
            'dictation_reminder_dismissed': getattr(self, 'dictation_reminder_dismissed', False),
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _load_quick_actions(self) -> list:
        """Load quick actions from file."""
        if QUICK_ACTIONS_FILE.exists():
            try:
                with open(QUICK_ACTIONS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return DEFAULT_QUICK_ACTIONS.copy()

    def _save_quick_actions(self):
        """Save quick actions to file."""
        try:
            with open(QUICK_ACTIONS_FILE, 'w') as f:
                json.dump(self.quick_actions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving quick actions: {e}")

    def _update_quick_actions_menu(self):
        """Update quick actions dropdown menu in all tabs."""
        for agent_id, tab in self.agent_tabs.items():
            if hasattr(tab, 'quick_actions_btn'):
                menu = QMenu(tab.quick_actions_btn)

                for action in self.quick_actions:
                    item = QAction(action['label'], self)
                    item.triggered.connect(lambda checked, cmd=action['command']: self._insert_quick_action(cmd))
                    menu.addAction(item)

                menu.addSeparator()

                add_action = QAction(f"➕ {tr('add_action')}", self)
                add_action.triggered.connect(self._add_quick_action)
                menu.addAction(add_action)

                tab.quick_actions_btn.setMenu(menu)

    def _check_license(self):
        """Check license status (silent - no popups)."""
        status = self.license_manager.validate()
        # All license states handled silently - no popups
        pass

    def _start_claude(self):
        """Start Claude Code process (legacy - not used with QTermWidget)."""
        self._update_status(tr('status_starting_claude'))
        self._append_system_message("Uruchamianie Claude Code...")

        if self.claude.start():
            self._update_status(tr('status_claude_started'))
            self._append_system_message("Claude Code gotowy. Możesz pisać lub dyktować polecenia.")
        else:
            self._update_status(tr('status_claude_start_error'))
            self._append_system_message("Błąd: Nie można uruchomić Claude Code. Upewnij się, że jest zainstalowany.")

    def _build_claude_command(self, agent_tab) -> str:
        """Build the claude launch command for a given agent tab,
        appending --model when the agent has a non-default model selected.

        Przypina też KONKRETNĄ sesję: generujemy własny identyfikator i
        przekazujemy `claude --session-id <uuid>`, a czytnikowi dziennika
        wskazujemy DOKŁADNY plik tej sesji. Dzięki temu wykrywanie „agent
        czeka" (flaga „?") oraz auto-czytanie nie muszą ZGADYWAĆ pliku z
        katalogu (zgadywanie zawodziło dla sesji wznowionych/cichych i myliło
        sesje między oknami) — działają od razu i deterministycznie.
        """
        cmd = self.claude_command
        model = getattr(agent_tab, 'model', 'default')
        if model and model != 'default':
            cmd = f"{cmd} --model {model}"
        session_id = str(uuid.uuid4())
        cmd = f"{cmd} --session-id {session_id}"
        self._pin_tab_session(agent_tab, session_id)
        return cmd

    def _pin_tab_session(self, agent_tab, session_id: str):
        """Wskaż czytnikowi dziennika DOKŁADNY plik sesji (po --session-id).

        Resetuje priming, by przy RESTARCIE zakładki (Stop→Uruchom) czytnik
        zaczął od nowej sesji od zera. Bezpieczne, gdy czytnik jeszcze nie
        istnieje — id zostaje na zakładce i zostanie podpięte przy jego
        utworzeniu (patrz _on_terminal_ready).
        """
        try:
            agent_tab._pinned_session_id = session_id
            agent_tab._transcript_primed = False
            reader = getattr(agent_tab, '_transcript_reader', None)
            if reader is not None:
                reader.pin_session(session_id)
        except Exception:
            pass

    def _auto_run_claude_command(self):
        """Auto-run Claude command in all terminals with auto_start enabled.

        NOTE: Ta metoda jest używana tylko przy starcie aplikacji.
        Dla nowych zakładek tworzonych później używamy _run_claude_in_tab().
        """
        if not self.claude_command:
            return

        self._update_status(tr('status_starting_cmd').format(cmd=self.claude_command))

        # Send command to all auto-start agent terminals
        for agent_id, tab in self.agent_tabs.items():
            if tab.terminal_backend and tab.auto_start:
                cmd = self._build_claude_command(tab)
                tab.terminal_backend.send_text(cmd + "\r")
                self._update_status(tr('status_claude_started'))

    def _run_claude_in_tab(self, agent_tab, force=False):
        """Run Claude command in a specific agent tab.

        Używane przy tworzeniu nowych zakładek (po dialogu dodawania agenta).
        Args:
            agent_tab: Zakładka agenta
            force: Wymuś uruchomienie nawet jeśli auto_start=False
        """
        if not self.claude_command:
            return

        if agent_tab.terminal_backend and (agent_tab.auto_start or force):
            cmd = self._build_claude_command(agent_tab)
            agent_tab.terminal_backend.send_text(cmd + "\r")
            self._update_status(tr('status_claude_started_in').format(name=agent_tab.agent_name))

    # ==================== Event Handlers ====================

    def _ensure_terminal_at_bottom(self):
        """Scroll terminal to the bottom after layout changes.

        Uses the centralized scroll manager for consistent behavior.
        """
        if self._scroll_manager:
            self._scroll_manager.schedule_scroll()

    def _set_language(self, lang_code: str):
        """Handle language change from menu."""
        self.current_language = lang_code
        # Globalny tłumacz (config.t) — z niego korzystają też okna dialogowe.
        set_ui_language(lang_code)

        # Update checkmarks in menu
        for code, action in self.language_actions.items():
            action.setChecked(code == lang_code)

        # Update TTS voice
        if self.current_language in SUPPORTED_LANGUAGES:
            voice = SUPPORTED_LANGUAGES[self.current_language][2]
            self.tts.set_voice(voice)

        # Update STT language
        lang_prefix = self.current_language.split('-')[0]
        self.stt.set_language(lang_prefix)

        # Update UI language
        self._update_ui_language()

        self._save_settings()

    def _get_text(self, key: str) -> str:
        """Get translated text for current language (delegates to config.t)."""
        return tr(key)

    def _update_ui_language(self):
        """Update all UI elements to current language."""
        # Pasek menu odtwarzamy w nowym języku. PUŁAPKA Qt: QAction-y są
        # parentowane do okna (nie do menu), więc samo menuBar().clear() ich NIE
        # usuwa — zostają żywe i ich skróty (Ctrl+N, Ctrl+T…) KUMULUJĄ się przy
        # każdej zmianie języka („ambiguous shortcut"). Dlatego najpierw zbieramy
        # stare akcje, zdejmujemy skróty i kasujemy je, dopiero potem odbudowa.
        mb = self.menuBar()
        old_actions = []

        def _collect(menu):
            for a in menu.actions():
                old_actions.append(a)
                sub = a.menu()
                if sub is not None:
                    _collect(sub)

        for a in mb.actions():
            old_actions.append(a)
            sub = a.menu()
            if sub is not None:
                _collect(sub)
        mb.clear()
        for a in old_actions:
            a.setShortcut(QKeySequence())
            a.deleteLater()
        self._create_menu_bar()
        # Menu rozwijane zakładki „+" (budowane osobno w _setup_ui; samo czyści stare akcje).
        if hasattr(self, '_add_tab_menu'):
            self._populate_add_tab_menu()
        # Dolny panel KAŻDEJ zakładki (nie tylko aktywnej).
        for tab in self.agent_tabs.values():
            self._apply_tab_language(tab)
        # Etykieta „Dodaj własną…" w menu szybkich akcji wszystkich zakładek.
        self._update_quick_actions_menu()
        # Tytuł okna
        self.setWindowTitle(f"{tr('app_title')} v{APP_VERSION}{APP_TITLE_SUFFIX}")

    def _apply_tab_language(self, tab):
        """Ustaw napisy dolnego panelu zakładki wg bieżącego języka."""
        try:
            tab.input_field.setPlaceholderText(tr('input_placeholder'))
            tab.send_btn.setToolTip(tr('send_tooltip'))
            tab.dictate_btn.setToolTip(tr('dictate_tooltip'))
            tab.read_btn.setToolTip(tr('read_tooltip'))
            tab.pause_btn.setToolTip(tr('pause_tooltip'))
            tab.stop_btn.setToolTip(tr('stop_tooltip'))
            tab.copy_btn.setToolTip(tr('copy_tooltip'))
            tab.clear_input_btn.setToolTip(tr('clear_input_tooltip'))
            tab.add_media_btn.setToolTip(tr('add_media_tooltip'))
            tab.quick_actions_btn.setToolTip(tr('quick_actions'))
            tab.auto_read_checkbox.setText(tr('auto_read'))
        except Exception:
            pass

    def _on_auto_read_changed(self, state: int):
        """Handle auto-read checkbox change."""
        self.auto_read_responses = state == Qt.Checked
        self._save_settings()

    def _on_claude_output(self, text: str):
        """Handle real-time output from Claude."""
        if text and text.strip():
            cursor = self.conversation_area.textCursor()
            cursor.movePosition(QTextCursor.End)

            # Check if it's processing indicator
            if "Processing" in text or "⏳" in text:
                # Purple color for processing
                fmt = QTextCharFormat()
                fmt.setForeground(QColor("#a78bfa"))
                cursor.insertText("⏳ Processing...\n", fmt)
            else:
                # White color for AI response
                fmt = QTextCharFormat()
                fmt.setForeground(QColor("#e4e4e7"))
                cursor.insertText(text, fmt)

            self.conversation_area.setTextCursor(cursor)
            self.conversation_area.ensureCursorVisible()
            # USUNIĘTO: QApplication.processEvents() — to była klasyczna pułapka
            # rekurencji event loopa: callback przychodzi z wątku tła
            # (ClaudeBridge._execute_query w threading.Thread), ale modyfikuje
            # widget Qt z tego wątku (już samo to jest błędem — niewspierane
            # cross-thread GUI access w PyQt). Dodatkowo processEvents()
            # pozwalało na re-entrancy: w środku obsługi outputu pętla Qt mogła
            # obsłużyć inne sygnały, m.in. ponownie ten sam, lub kolejny output
            # → stos przepełniony, GUI starvation, Wayland compositor (Mutter)
            # blokowany w XWayland handshake → zamarzanie systemu.
            # Bez processEvents() Qt sam zaplanuje repaint w naturalnym cyklu.

    def _on_claude_response(self, text: str):
        """Handle complete response from Claude."""
        if self.auto_read_responses and text.strip():
            self.tts.speak(text)

    def _on_claude_error(self, error: str):
        """Handle Claude error."""
        self._append_system_message(f"Błąd: {error}")
        self._update_status(tr('status_error').format(error=error))

    # ==================== Terminal Handlers ====================

    def _on_terminal_output(self, data):
        """Handle data received from terminal (for TTS and token counting)."""
        # Decode bytes to string
        try:
            text = data.data().decode('utf-8', errors='ignore')
        except:
            text = str(data)

        # Filter out ANSI escape codes for TTS
        import re
        clean_text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
        clean_text = re.sub(r'\x1b\][^\x07]*\x07', '', clean_text)  # OSC sequences
        clean_text = clean_text.strip()

        if clean_text:
            # (Flaga "agent czeka" jest wykrywana z dziennika sesji w
            # _poll_transcripts — patrz reader.waiting_for_user(). Strumień
            # terminala jest do tego niepewny: zniekształcone kodowanie ramek/
            # ❯ i różny format popupów. Tu zostaje tylko liczenie tokenów.)

            # Add to buffer with newline separator
            self._terminal_output_buffer += clean_text + "\n"

            # Update context usage counter
            self._update_context_usage(len(clean_text))

            # LIMIT buffer size to last 5000 characters to prevent memory issues
            if len(self._terminal_output_buffer) > 5000:
                self._terminal_output_buffer = self._terminal_output_buffer[-5000:]

            # Auto-czytanie korzysta teraz z dziennika sesji (Droga A,
            # _poll_transcripts), nie z tego bufora. Bufor zostaje wyłącznie
            # do liczenia tokenów (_update_context_usage powyżej).

            # NOTE: Removed auto-scroll on terminal output - user controls scroll manually
            # Previously this caused annoying jumps when trying to read history

    def _on_terminal_finished(self):
        """Handle terminal session finished."""
        self._update_status(tr('status_terminal_ended'))
        # Optionally restart
        if self.terminal_backend:
            self.terminal_backend.start_shell_program()
            # Schedule scroll after terminal restarts
            if self._scroll_manager:
                QTimer.singleShot(500, self._scroll_manager.schedule_scroll)

    def _on_tts_state_changed(self, state: TTSState):
        """Handle TTS state change."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        if state == TTSState.PLAYING:
            # Show pause and stop buttons
            tab.pause_btn.setVisible(True)
            tab.stop_btn.setVisible(True)
            tab.pause_btn.setEnabled(True)
            tab.pause_btn.setIcon(self._icon('pause', 'normal'))
            # Start speaker animation
            self._speaker_anim_timer.start(300)
            # Stop pause blink if running
            self._pause_blink_timer.stop()
            self._update_status(tr('reading'))
        elif state == TTSState.PAUSED:
            # Keep buttons visible during pause
            tab.pause_btn.setVisible(True)
            tab.stop_btn.setVisible(True)
            tab.pause_btn.setIcon(self._icon('pause', 'active'))
            # Stop speaker animation
            self._speaker_anim_timer.stop()
            tab.read_btn.setIcon(self._icon('read', 'normal'))
            # Start pause blink animation
            self._pause_blink_timer.start(500)
            self._update_status(tr('paused'))
        elif state == TTSState.GENERATING:
            # Show stop button during generation (to allow cancel)
            tab.stop_btn.setVisible(True)
            self._update_status(tr('status_generating_speech'))
        else:
            # Hide pause and stop buttons when idle
            tab.pause_btn.setVisible(False)
            tab.stop_btn.setVisible(False)
            tab.pause_btn.setEnabled(False)
            tab.pause_btn.setIcon(self._icon('pause', 'normal'))
            # Stop all animations
            self._speaker_anim_timer.stop()
            self._pause_blink_timer.stop()
            tab.read_btn.setIcon(self._icon('read', 'normal'))
            self._update_status(tr('status_ready'))

    def _on_tts_finished(self):
        """Handle TTS finished."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        # Hide pause and stop buttons
        tab.pause_btn.setVisible(False)
        tab.stop_btn.setVisible(False)
        # Stop speaker animation
        self._speaker_anim_timer.stop()
        tab.read_btn.setIcon(self._icon('read', 'normal'))
        self._update_status(tr('status_ready'))

    def _on_stt_state_changed(self, state: STTState):
        """Handle STT state change."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        if state == STTState.RECORDING:
            tab.dictate_btn.setChecked(True)
            # Start microphone pulse animation
            self._mic_pulse_timer.start(400)
            self._update_status(tr('status_recording_click'))
        elif state == STTState.PROCESSING:
            tab.dictate_btn.setIcon(self._icon('dictate', 'processing'))
            # Stop pulse animation
            self._mic_pulse_timer.stop()
            self._update_status(tr('status_processing_speech'))
        else:
            tab.dictate_btn.setIcon(self._icon('dictate', 'normal'))
            tab.dictate_btn.setChecked(False)
            # Stop pulse animation and reset style
            self._mic_pulse_timer.stop()
            self._reset_mic_style()
            self._update_status(tr('status_ready'))

    # ==================== Animation Methods ====================

    def _animate_mic_pulse(self):
        """Animate microphone button pulsing when recording."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        self._mic_pulse_state = not self._mic_pulse_state
        # Nagrywanie = czerwone WYPEŁNIENIE przycisku (jak w makiecie), więc ikona
        # musi być biała — w kolorze skórki (fiolet) zlałaby się z czerwienią.
        tab.dictate_btn.setIcon(icon_set.button_icon('dictate', 'active', '#ffffff'))
        # Puls: jaśniejsza/ciemniejsza czerwień + rosnąca poświata.
        bg, glow = ((theme.DANGER, '3px') if self._mic_pulse_state
                    else (theme.DANGER_LIGHT, '1px'))
        tab.dictate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: {glow} solid {theme.DANGER_LIGHT};
                border-radius: {theme.RADIUS}px;
            }}
        """)

    def _reset_mic_style(self):
        """Reset microphone button to default style."""
        tab = self._get_current_agent_tab()
        if tab:
            self._apply_button_icon_style(tab.dictate_btn, 'icon_dictate_color')
            # ...i cofnij BIAŁĄ ikonę z trybu nagrywania na kolor skórki.
            tab.dictate_btn.setIcon(self._icon('dictate', 'normal'))

    def _animate_speaker(self):
        """Animate speaker icon showing sound waves."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        self._speaker_anim_state = (self._speaker_anim_state + 1) % 3
        tab.read_btn.setIcon(icon_set.icon_by_name(
            self._speaker_icons[self._speaker_anim_state],
            self.skin_colors.get('icon_read_color', theme.TEXT_DIM)))

    def _animate_pause_blink(self):
        """Animate pause button blinking - icon only, button stays in place."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        self._pause_blink_state = not self._pause_blink_state
        if self._pause_blink_state:
            # Ikona „play" widoczna (wznów)
            tab.pause_btn.setIcon(self._icon('pause', 'active'))
        else:
            # Mrugnięcie — chwilowo pusta ikona, by przyciągnąć wzrok
            tab.pause_btn.setIcon(QIcon())

    def _on_transcription(self, text: str):
        """Handle transcription result - inserts at cursor position."""
        if text.strip():
            cursor = self.input_field.textCursor()
            pos = cursor.position()
            current_text = self.input_field.toPlainText()

            # Sprawdź czy trzeba dodać spację PRZED (jeśli poprzedni znak nie jest spacją/enterem)
            needs_space_before = pos > 0 and current_text[pos-1] not in (' ', '\n', '\t')

            # Sprawdź czy trzeba dodać spację PO (jeśli następny znak to litera/cyfra)
            needs_space_after = pos < len(current_text) and current_text[pos] not in (' ', '\n', '\t', '.', ',', '!', '?', ':', ';')

            # Zbuduj tekst do wstawienia z odpowiednimi spacjami
            insert_text = ""
            if needs_space_before:
                insert_text += " "
            insert_text += text
            if needs_space_after:
                insert_text += " "

            # SCROLL FIX: Block signals during text insertion to prevent page scroll
            # The contentsChanged -> _adjust_height -> setFixedHeight chain was causing scroll
            self.input_field.blockSignals(True)
            self.input_field.document().blockSignals(True)

            # Wstaw tekst w pozycji kursora
            cursor.insertText(insert_text)
            self.input_field.setTextCursor(cursor)

            # Restore signals
            self.input_field.document().blockSignals(False)
            self.input_field.blockSignals(False)

            # Manually trigger height adjustment AFTER signals are restored
            # This ensures layout updates happen once, not multiple times
            self.input_field._adjust_height()

            self._append_system_message(f"Rozpoznano: {text}")

    def _on_stt_error(self, error: str):
        """Handle STT error."""
        self._append_system_message(f"Błąd rozpoznawania: {error}")
        self._update_status(tr('status_stt_error'))

    # ==================== Actions ====================

    def _send_message(self):
        """Send message to terminal or Claude."""
        text = self.input_field.text().strip()

        # Build full message with attachments
        full_message = self._build_message_with_attachments(text)

        if self.terminal_backend:
            if full_message:
                # Send text + Enter (with delay for Claude Code)
                self.terminal_backend.send_text(full_message)
                QTimer.singleShot(50, lambda: self.terminal_backend.send_text("\r"))
                self.input_field.clear()
                self._clear_attachments()
                # Update context usage with user input
                self._update_context_usage(len(full_message))
            else:
                # Empty field - just send Enter (accept Claude Code proposal)
                self.terminal_backend.send_text("\r")

            # Schedule scroll to bottom via centralized manager
            # The manager handles debouncing and proper timing
            if self._scroll_manager:
                self._scroll_manager.schedule_scroll()

            # NOTE: Removed 30-second auto-scroll timer - was causing unwanted jumps
            # User now has full control over scrolling after sending a message

            self._update_status(tr('status_sent_to_terminal'))
            return

        # Fallback for non-terminal mode - require text
        if not full_message:
            return

        self.input_field.clear()
        self._clear_attachments()
        # Fallback to Claude bridge
        self._append_user_message(full_message)
        self.claude.send(full_message)
        # Update context usage with user input
        self._update_context_usage(len(full_message))
        self._update_status(tr('status_sent'))

    def _build_message_with_attachments(self, text: str) -> str:
        """Build message with attached file paths."""
        if not self.attached_files:
            return text

        # Create message with file references
        parts = []

        # Add file paths as references for Claude Code
        if self.attached_files:
            files_list = " ".join(self.attached_files)
            if text:
                # Combine files with message
                parts.append(f"Przeanalizuj te pliki: {files_list}")
                parts.append("")
                parts.append(text)
            else:
                # Just files
                parts.append(f"Przeanalizuj te pliki: {files_list}")

        return "\n".join(parts) if parts else text

    def _clear_attachments(self):
        """Clear all attachments after sending."""
        self.attached_files = []
        self._update_attachments_display()

    def _toggle_dictation(self):
        """Toggle voice dictation."""
        if self.stt.is_recording():
            self.stt.stop_recording()
        else:
            if not self.stt.api_key:
                # Brak klucza Groq. Dyktowanie (STT) go WYMAGA; czytanie (TTS,
                # edge-tts) działa bez klucza. Wyjaśnij i zaproponuj dodanie.
                # (Wcześniej wołano nieistniejące _show_api_key_dialog →
                #  AttributeError, przez co klik mikrofonu nic nie robił na
                #  świeżej instalacji bez klucza.)
                answer = QMessageBox.question(
                    self,
                    tr('dlg_groq_required_title'),
                    tr('dlg_groq_required_msg'),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if answer == QMessageBox.Yes:
                    self._show_groq_api_dialog()
                return
            self.stt.start_recording()

    def _read_last_response(self):
        """Read the last Claude Code response aloud (cleaned for TTS)."""
        # Initialize text cleaner with current language
        text_cleaner = TextCleanerForTTS(self.current_language)

        # Funkcja #3: ręczny odczyt też głosem aktywnej zakładki (per-agent).
        _vtab = self._get_current_agent_tab()
        _voice = self._agent_voice(_vtab) if _vtab else None
        if _voice:
            self.tts.set_voice(_voice)

        if self.terminal_backend:
            # For terminal mode - read from buffer or selected text
            selected = self.terminal_backend.selected_text()

            # Diagnostyka „czyta przedostatnią/coś innego" (pasywna, CVA_FLAG_DEBUG=1).
            # Wołana TU (przed gałęzią zaznaczenia), by zarejestrować też przypadek
            # „czyta stare/przypadkowe zaznaczenie zamiast ostatniej odpowiedzi".
            self._read_last_dbg(selected)

            if selected:
                # Fix Polish encoding first
                selected = fix_polish_encoding(selected)
                # User selected text - clean and read it
                # use_dictionary=False because terminal encoding may corrupt Polish chars
                cleaned_text = text_cleaner.clean(selected, use_dictionary=False)
                if cleaned_text:
                    self.tts.speak(cleaned_text)
                    self._update_status(tr('status_reading_selected'))
                else:
                    self._update_status(tr('status_selection_no_content'))
                return

            # Bez zaznaczenia: przycisk „czytaj ostatnią" ma czytać NAJNOWSZĄ
            # wypowiedź Claude'a — NIE zaległości zebrane od początku (te kasujemy,
            # by nie odczytały się jako „od początku"; objaw zgłoszony przez usera).
            # Źródłem prawdy jest dziennik sesji (czysta proza zamiast śmieci z
            # bufora terminala).
            tab = self._get_current_agent_tab()
            if tab is not None and getattr(tab, 'pending_backlog', None):
                tab.pending_backlog = []  # odrzuć zaległości — chcemy tylko ostatnią

            reader = getattr(tab, '_transcript_reader', None) if tab else None

            def _speak_from_terminal_buffer(clear_after: bool) -> bool:
                """Odczytaj ostatnią odpowiedź z bufora EKRANU (terminala).

                Zwraca True gdy udało się coś odczytać. Używane dwutorowo:
                jako obejście pułapki „agent czeka" (poniżej) oraz jako końcowy
                fallback, gdy dziennik nic nie zwróci.
                """
                # Notes TEJ zakładki (zasilany wyłącznie przez jej własny
                # terminal), a NIE wspólny bufor MainWindow — tamten miesza
                # wyjście WSZYSTKICH zakładek naraz, więc „ostatnia odpowiedź"
                # bywała treścią agenta z tła (np. Strona F-P), a nie bieżącego.
                buf = getattr(tab, '_terminal_output_buffer', '') if tab else ''
                if not buf.strip():
                    return False
                resp = extract_last_claude_response(buf)
                if not resp:
                    return False
                resp = fix_polish_encoding(resp)
                cleaned = text_cleaner.clean(resp, use_dictionary=False)
                if not cleaned:
                    return False
                # Stop auto-read timer to prevent double reading
                if hasattr(self, '_tts_timer') and self._tts_timer is not None:
                    self._tts_timer.stop()
                self.tts.speak(cleaned)
                self._update_status(tr('status_reading_last'))
                if clear_after and tab is not None:
                    tab._terminal_output_buffer = ""
                return True

            # PUŁAPKA Claude Code (potwierdzona diagnostyką 2026-07-03): gdy agent
            # WŁAŚNIE czeka na Twoją odpowiedź (na ekranie wisi pytanie
            # AskUserQuestion / prośba o zgodę), Claude Code zapisuje swoją OSTATNIĄ
            # wypowiedź do dziennika sesji DOPIERO po Twojej odpowiedzi. W tym oknie
            # dziennik ma jeszcze PRZEDOSTATNIĄ wypowiedź → reader.last_response()
            # zwróciłby ją (objaw: „🔊 czyta przedostatnią"). Dlatego w stanie
            # „czeka" czytamy z EKRANU (bufor terminala), gdzie najnowsza odpowiedź
            # już JEST. Bufora NIE czyścimy (rozmowa trwa). Bezpiecznik: gdy z ekranu
            # nic sensownego nie wyjdzie → spadamy niżej na dziennik (jak dotąd).
            agent_waiting = False
            if reader is not None:
                try:
                    agent_waiting = reader.waiting_for_user()
                except Exception:
                    agent_waiting = False
            if agent_waiting and _speak_from_terminal_buffer(clear_after=False):
                return

            if reader is not None:
                try:
                    last = reader.last_response()
                except Exception:
                    last = None
                if last:
                    cleaned_text = prose_from_markdown(last)
                    if cleaned_text:
                        self.tts.speak(cleaned_text)
                        self._update_status(tr('status_reading_last'))
                        return

            # Fallback (stary tor) — ekstrakcja z bufora terminala TEJ zakładki
            # (nie ze wspólnego MainWindow, który miesza wyjście wszystkich
            # zakładek → czytał treść agenta z tła).
            tab_buf = getattr(tab, '_terminal_output_buffer', '') if tab else ''
            if tab_buf.strip():
                # Extract only the last response (strips UI frames, spinners, user prompts)
                last_response = extract_last_claude_response(tab_buf)

                if last_response:
                    last_response = fix_polish_encoding(last_response)
                    cleaned_text = text_cleaner.clean(last_response, use_dictionary=False)

                    if cleaned_text:
                        # Stop auto-read timer to prevent double reading
                        if hasattr(self, '_tts_timer') and self._tts_timer is not None:
                            self._tts_timer.stop()
                        self.tts.speak(cleaned_text)
                        self._update_status(tr('status_reading_last'))
                        # Clear buffer after reading
                        if tab is not None:
                            tab._terminal_output_buffer = ""
                    else:
                        self._update_status(tr('status_response_no_content'))
                else:
                    self._update_status(tr('status_no_response_found'))
                    # Clear buffer anyway to prevent accumulation
                    if tab is not None:
                        tab._terminal_output_buffer = ""
            else:
                self._update_status(tr('status_no_text'))
            return

        # Fallback for QTextEdit mode
        if not self.conversation_area:
            return

        text = self.conversation_area.toPlainText()
        if not text:
            return

        # Extract last response
        last_response = extract_last_claude_response(text)

        if last_response:
            # Clean for TTS
            cleaned_text = text_cleaner.clean(last_response)

            if cleaned_text:
                self.tts.speak(cleaned_text)
            else:
                self._update_status(tr('status_response_no_content'))
        else:
            self._update_status(tr('status_no_response_found'))

    def _copy_selection(self):
        """Copy selected text from terminal to system clipboard."""
        if self.terminal_backend:
            selected = self.terminal_backend.selected_text()

            if selected and selected.strip():
                # Copy to system clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(selected)
                self._update_status(tr('status_copied').format(n=len(selected)))
                # Flash green effect
                self._flash_copy_success()
            else:
                self._update_status(tr('status_select_text_first_terminal'))
        else:
            # Fallback for QTextEdit mode
            if self.conversation_area:
                cursor = self.conversation_area.textCursor()
                selected = cursor.selectedText()

                if selected and selected.strip():
                    clipboard = QApplication.clipboard()
                    clipboard.setText(selected)
                    self._update_status(tr('status_copied').format(n=len(selected)))
                    # Flash green effect
                    self._flash_copy_success()
                else:
                    self._update_status(tr('status_select_text_first'))

    def _clear_input_field(self):
        """Clear the input text field."""
        self.input_field.clear()
        self.input_field.setFocus()

    def _add_media(self):
        """Open file dialog to add media files."""
        file_filter = (
            f"{tr('dlg_media_all_supported')} (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.pdf *.doc *.docx *.txt *.csv *.xlsx *.xls *.json *.xml *.zip *.tar *.gz);;"
            f"{tr('dlg_media_images')} (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;"
            f"{tr('dlg_media_documents')} (*.pdf *.doc *.docx *.txt *.csv *.xlsx *.xls);;"
            f"{tr('dlg_media_data')} (*.json *.xml *.csv);;"
            f"{tr('dlg_media_archives')} (*.zip *.tar *.gz);;"
            f"{tr('dlg_media_all_files')} (*.*)"
        )

        files, _ = styled_get_open_file_names(
            self,
            tr('dlg_media_add_title'),
            "",
            file_filter
        )

        if files:
            for file_path in files:
                if file_path not in self.attached_files:
                    self.attached_files.append(file_path)
            self._update_attachments_display()
            self._update_status(tr('status_files_added').format(n=len(files)))

    def _remove_attachment(self, file_path: str):
        """Remove an attachment from the list."""
        if file_path in self.attached_files:
            self.attached_files.remove(file_path)
            self._update_attachments_display()

    def _update_attachments_display(self):
        """Update the attachments display area."""
        # Clear existing widgets (except stretch)
        while self.attachments_layout.count() > 1:
            item = self.attachments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add file chips
        for file_path in self.attached_files:
            chip = self._create_attachment_chip(file_path)
            self.attachments_layout.insertWidget(self.attachments_layout.count() - 1, chip)

        # Show/hide attachments area
        self.attachments_widget.setVisible(len(self.attached_files) > 0)

    def _create_attachment_chip(self, file_path: str) -> QWidget:
        """Create a chip widget for an attachment."""
        import os
        from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton

        chip = QWidget()
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 4, 4, 4)
        chip_layout.setSpacing(4)

        # Get file info
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        # Icon based on file type
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            icon = "🖼️"
        elif ext == '.pdf':
            icon = "📄"
        elif ext in ['.doc', '.docx']:
            icon = "📝"
        elif ext in ['.xls', '.xlsx', '.csv']:
            icon = "📊"
        elif ext in ['.zip', '.tar', '.gz']:
            icon = "📦"
        else:
            icon = "📁"

        # File label
        label = QLabel(f"{icon} {filename}")
        label.setStyleSheet(f"""
            QLabel {{
                color: {self.skin_colors.get('text_color', '#ffffff')};
                font-size: 11px;
            }}
        """)
        label.setToolTip(file_path)
        chip_layout.addWidget(label)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #ef4444;
                border: none;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: #ff6b6b;
            }}
        """)
        remove_btn.clicked.connect(lambda: self._remove_attachment(file_path))
        chip_layout.addWidget(remove_btn)

        # Chip styling
        chip.setStyleSheet(f"""
            QWidget {{
                background-color: {self.skin_colors.get('button_bg', '#4a1a3a')};
                border: 1px solid {self.skin_colors.get('border_color', '#4a1a3a')};
                border-radius: 12px;
            }}
        """)

        return chip

    def _flash_copy_success(self):
        """Flash copy button green to indicate success."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        # Change to green checkmark icon + green border
        tab.copy_btn.setIcon(self._icon('copy', 'active'))
        tab.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px solid #22c55e;
                border-radius: 12px;
            }
        """)
        # Reset after 500ms
        QTimer.singleShot(500, self._reset_copy_style)

    def _reset_copy_style(self):
        """Reset copy button to default style."""
        tab = self._get_current_agent_tab()
        if tab:
            tab.copy_btn.setIcon(self._icon('copy', 'normal'))
            self._apply_button_icon_style(tab.copy_btn, 'icon_copy_color')

    def _toggle_pause(self):
        """Toggle TTS pause/resume."""
        self.tts.toggle_pause()

    def _stop_all(self):
        """Stop TTS and STT only. Does NOT interrupt Claude Code in the terminal.

        Each sub-stop is isolated — a pygame/SDL segfault in TTS must not prevent
        STT/timer cleanup and must not bubble up to kill the GUI process.
        """
        try:
            self.tts.stop()
        except Exception as e:
            print(f"[_stop_all] TTS stop failed: {e}", file=sys.stderr)
        try:
            self.stt.cancel_recording()
        except Exception as e:
            print(f"[_stop_all] STT cancel failed: {e}", file=sys.stderr)

        self._terminal_output_buffer = ""
        if hasattr(self, '_tts_timer') and self._tts_timer is not None:
            self._tts_timer.stop()

        self._update_status(tr('status_reading_stopped'))

    def _insert_quick_action(self, command: str):
        """Insert quick action command."""
        self.input_field.setText(command)
        self.input_field.setFocus()

    def _add_quick_action(self):
        """Add new quick action via dialog with both fields."""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('dlg_quick_add_title'))
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # Form with two fields
        form_layout = QFormLayout()

        label_input = QLineEdit()
        label_input.setPlaceholderText(tr('dlg_quick_label_placeholder'))
        label_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form_layout.addRow(tr('dlg_quick_action_name_label'), label_input)

        command_input = QLineEdit()
        command_input.setPlaceholderText(tr('dlg_quick_command_placeholder'))
        command_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form_layout.addRow(tr('dlg_quick_command_label'), command_input)

        layout.addLayout(form_layout)

        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec_() == QDialog.Accepted:
            label = label_input.text().strip()
            command = command_input.text().strip()

            if not label:
                QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_quick_no_name_msg'))
                return
            if not command:
                QMessageBox.warning(self, tr('dlg_quick_no_command_title'), tr('dlg_quick_no_command_msg'))
                return

            self.quick_actions.append({'label': label, 'command': command})
            self._save_quick_actions()
            self._update_quick_actions_menu()

    def _manage_quick_actions(self):
        """Show quick actions manager dialog."""
        dialog = QuickActionsDialog(self, self.quick_actions)

        if dialog.exec_() == QDialog.Accepted:
            self.quick_actions = dialog.get_quick_actions()
            self._save_quick_actions()
            self._update_quick_actions_menu()
            self._update_status(tr('status_quick_actions_saved'))

    def _new_session(self):
        """Start new terminal/Claude session."""
        reply = QMessageBox.question(self, tr('dlg_new_session_title'),
            tr('dlg_new_session_msg'),
            QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            if self.terminal_backend:
                # Clear terminal and restart shell
                self.terminal_backend.send_text("clear\n")
                self._terminal_output_buffer = ""
                # Licznik tokenów NIE jest resetowany - liczy do końca sesji
            else:
                self.conversation_area.clear()
                self.claude.stop()
                self._start_claude()
                # Licznik tokenów NIE jest resetowany - liczy do końca sesji

    def _show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self, self.stt.api_key)
        if dialog.exec_() == QDialog.Accepted:
            api_key = dialog.get_api_key()
            self.stt.set_api_key(api_key)
            self._save_settings()

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, tr('dlg_about_title').format(name=APP_NAME),
            tr('dlg_about_body').format(name=APP_NAME, version=APP_VERSION))

    def _show_trial_dialog(self):
        """Show trial registration dialog."""
        email, ok = QInputDialog.getText(self, tr('dlg_trial_start_title'),
            tr('dlg_trial_start_prompt'))

        if ok and email:
            if self.license_manager.start_trial(email):
                self._check_license()
                QMessageBox.information(self, tr('dlg_trial_active_title'),
                    tr('dlg_trial_active_msg').format(email=email))
            else:
                QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_trial_activate_failed'))

    def _show_license_dialog(self):
        """Show license management dialog."""
        dialog = LicenseDialog(self, self.license_manager)
        dialog.exec_()
        self._check_license()

    def _show_license_expired_dialog(self):
        """Show dialog when license/trial expired."""
        reply = QMessageBox.warning(self, tr('dlg_license_expired_title'),
            tr('dlg_license_expired_msg'),
            QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            import webbrowser
            webbrowser.open(self.license_manager.get_purchase_url())

    def _show_skin_settings(self):
        """Show skin customization dialog."""
        dialog = SkinSettingsDialog(self, self.skin_colors, self.skin_icons)

        # Store originals for cancel
        original_colors = self.skin_colors.copy()
        original_icons = {k: v.copy() for k, v in self.skin_icons.items()}

        if dialog.exec_() == QDialog.Accepted:
            # User clicked Apply - save new colors and icons
            self.skin_colors = dialog.get_colors()
            self.skin_icons = dialog.get_icons()
            self._apply_skin_icons()  # Apply new icons to buttons
            self._save_settings()
            self._update_status(tr('status_skin_saved'))
        else:
            # User cancelled - restore originals
            self.skin_colors = original_colors
            self.skin_icons = original_icons
            self.apply_skin_colors(original_colors)
            self._apply_skin_icons()

    def _apply_skin_icons(self):
        """Ustaw ikony SVG przycisków dolnego panelu we wszystkich zakładkach.

        Dawniej ustawiało emoji-tekst ze skin_icons; teraz przyciski używają
        spójnych, kolorowych ikon SVG (icon_set), identycznych na Linux/Mac/
        Windows. send_btn pozostaje przyciskiem tekstowym ('↵ Enter').
        """
        for agent_id, tab in self.agent_tabs.items():
            for attr, key in (
                ('dictate_btn', 'dictate'),
                ('read_btn', 'read'),
                ('pause_btn', 'pause'),
                ('stop_btn', 'stop'),
                ('copy_btn', 'copy'),
                ('clear_input_btn', 'clear_input'),
                ('add_media_btn', 'add_media'),
                ('quick_actions_btn', 'quick_actions'),
            ):
                btn = getattr(tab, attr, None)
                if btn is not None:
                    btn.setIcon(self._icon(key))

            # Przełącznik trybu myszy trzyma DWIE ikony (stan przewijania /
            # zaznaczania) poza pętlą powyżej — przemaluj obie i odśwież bieżącą.
            if hasattr(tab, '_update_mouse_mode_btn'):
                mouse_color = self.skin_colors.get('icon_copy_color', theme.TEXT_DIM)
                tab._icon_mouse_scroll = icon_set.icon_by_name("mouse-scroll", mouse_color)
                tab._icon_mouse_select = icon_set.icon_by_name("mouse-select", mouse_color)
                tab._update_mouse_mode_btn()

    def _icon(self, key: str, state: str = 'normal', color_key: str = None) -> QIcon:
        """Ikona przycisku pomalowana kolorem z bieżącej skórki.

        Ikony SVG są jednokolorowe (`currentColor`), więc barwę podaje skórka —
        inaczej ustawienia „Kolor ikony…" w oknie Skórka nie robiłyby nic.
        """
        ck = color_key or f'icon_{key}_color'
        color = self.skin_colors.get(ck, theme.TEXT_DIM)
        return icon_set.button_icon(key, state, color)

    def _get_icon(self, button_name: str, state: str = 'normal') -> str:
        """Get icon for a button from skin_icons."""
        return self.skin_icons.get(button_name, {}).get(state, '?')

    def _apply_button_icon_style(self, button, color_key: str, font_size: int = 22, with_disabled: bool = False):
        """Apply transparent style with colored icon to a button.

        Args:
            button: QPushButton to style
            color_key: Key in skin_colors for icon color (e.g., 'icon_dictate_color')
            font_size: Font size for the icon
            with_disabled: If True, add :disabled pseudo-selector styling
        """
        icon_color = self.skin_colors.get(color_key, theme.TEXT_DIM)
        border_color = self.skin_colors.get('border_color', theme.BORDER)
        surface = self.skin_colors.get('button_bg', theme.SURFACE)

        disabled_style = ""
        if with_disabled:
            disabled_style = f"""
            QPushButton:disabled {{
                background-color: {surface};
                color: {theme.BORDER};
                border: 1px solid {theme.BORDER_SUBTLE};
            }}"""

        # Miękki kwadrat na powierzchni wypukłej; po najechaniu rozświetla się
        # ramka w kolorze akcentu (jak w makiecie), a nie całe tło.
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {surface};
                color: {icon_color};
                border: 1px solid {border_color};
                border-radius: {theme.RADIUS}px;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: {theme.SURFACE_HOVER};
                border: 1px solid {theme.ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {theme.BG_INPUT};
            }}
            QPushButton:checked {{
                color: #ffffff;
                background-color: {theme.DANGER};
                border: 1px solid {theme.DANGER};
            }}{disabled_style}
        """)

    def _apply_send_button_style(self, button):
        """Przycisk „Wyślij" — akcent aplikacji: gradient fioletowy + biały napis.

        Napis pozostaje ten ze skórki (użytkownik może mieć własny, np. „Poszło"),
        ale kolor liter wymuszamy na biały: dowolna barwa ze skórki na fioletowym
        gradiencie bywa nieczytelna. Poświatę pod przyciskiem daje jaśniejsza
        ramka — QSS nie zna box-shadow.
        """
        button.setStyleSheet(f"""
            QPushButton {{
                background: {theme.accent_gradient()};
                color: #ffffff;
                border: 1px solid {theme.ACCENT};
                border-radius: {theme.RADIUS_LG}px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background: {theme.accent_gradient()};
                border: 1px solid {theme.ACCENT_GLOW};
            }}
            QPushButton:pressed {{
                background: {theme.ACCENT_DEEP};
            }}
            QPushButton:disabled {{
                background: {theme.SURFACE};
                color: {theme.TEXT_FAINT};
                border: 1px solid {theme.BORDER_SUBTLE};
            }}
        """)

    def _apply_button_icon_styles(self):
        """Apply transparent styles with colored icons to all main buttons in all tabs."""
        # Apply to all agent tabs
        for agent_id, tab in self.agent_tabs.items():
            if hasattr(tab, 'dictate_btn'):
                self._apply_button_icon_style(tab.dictate_btn, 'icon_dictate_color')

            if hasattr(tab, 'read_btn'):
                self._apply_button_icon_style(tab.read_btn, 'icon_read_color')

            if hasattr(tab, 'stop_btn'):
                self._apply_button_icon_style(tab.stop_btn, 'icon_stop_color')

            if hasattr(tab, 'copy_btn'):
                self._apply_button_icon_style(tab.copy_btn, 'icon_copy_color')

            if hasattr(tab, 'clear_input_btn'):
                self._apply_button_icon_style(tab.clear_input_btn, 'icon_clear_input_color')

            if hasattr(tab, 'add_media_btn'):
                self._apply_button_icon_style(tab.add_media_btn, 'icon_add_media_color')

            # Przełącznik trybu myszy — ten sam styl (przezroczyste tło + zaokrąglenie),
            # inaczej zostawał domyślny biały kwadrat (ikona niewidoczna na białym).
            if hasattr(tab, 'mouse_mode_btn'):
                self._apply_button_icon_style(tab.mouse_mode_btn, 'icon_copy_color')

            # Pause button - uses same style as other buttons but with disabled state
            if hasattr(tab, 'pause_btn'):
                self._apply_button_icon_style(tab.pause_btn, 'icon_pause_color', with_disabled=True)

            # Wyślij — jedyny przycisk „pierwszoplanowy": gradient akcentu z
            # poświatą, biały napis (kolor ze skórki byłby nieczytelny na fiolecie).
            if hasattr(tab, 'send_btn'):
                self._apply_send_button_style(tab.send_btn)

            # Quick actions button (QToolButton - needs different selector)
            if hasattr(tab, 'quick_actions_btn'):
                icon_color = self.skin_colors.get('icon_quick_actions_color', '#facc15')
                border_color = self.skin_colors.get('border_color', '#4a1a3a')
                hover_color = self.skin_colors.get('hover_color', '#6a2a5a')

                tab.quick_actions_btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: transparent;
                        color: {icon_color};
                        border: 1px solid {border_color};
                        border-radius: 12px;
                        font-size: 20px;
                    }}
                    QToolButton:hover {{
                        background-color: {hover_color};
                    }}
                    QToolButton::menu-indicator {{
                        image: none;
                    }}
                """)

    def _apply_terminal_colors(self, colors: dict = None, terminal_backend=None):
        """Zastosuj kolory terminala przez backend (M2.3).

        Generuje plik .colorscheme (format QTermWidget) i wczytuje go przez
        backend. Na Linuksie (QTermWidget) działa jak dawniej; na WebTerminalu
        backend bierze na razie samo tło/tekst — pełne mapowanie skin → motyw
        xterm.js to M2.4. Gdy terminal_backend=None — stosuje do wszystkich zakładek.
        """
        if colors is None:
            colors = self.skin_colors

        # Helper to convert hex to RGB tuple
        def hex_to_rgb(hex_color: str) -> str:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r},{g},{b}"

        # Create custom color scheme content
        scheme_content = f"""[General]
Description=CustomSkin
Opacity=1
Wallpaper=

[Background]
Color={hex_to_rgb(colors.get('terminal_bg', '#300A24'))}

[BackgroundIntense]
Color={hex_to_rgb(colors.get('terminal_bg', '#300A24'))}

[Foreground]
Color={hex_to_rgb(colors.get('terminal_fg', '#EEEEEC'))}

[ForegroundIntense]
Color={hex_to_rgb(colors.get('terminal_fg', '#EEEEEC'))}

[Color0]
Color={hex_to_rgb(colors.get('terminal_color_0', '#2E3436'))}

[Color0Intense]
Color={hex_to_rgb(colors.get('terminal_color_0_bright', '#555753'))}

[Color1]
Color={hex_to_rgb(colors.get('terminal_color_1', '#CC0000'))}

[Color1Intense]
Color={hex_to_rgb(colors.get('terminal_color_1_bright', '#EF2929'))}

[Color2]
Color={hex_to_rgb(colors.get('terminal_color_2', '#4E9A06'))}

[Color2Intense]
Color={hex_to_rgb(colors.get('terminal_color_2_bright', '#8AE234'))}

[Color3]
Color={hex_to_rgb(colors.get('terminal_color_3', '#C4A000'))}

[Color3Intense]
Color={hex_to_rgb(colors.get('terminal_color_3_bright', '#FCE94F'))}

[Color4]
Color={hex_to_rgb(colors.get('terminal_color_4', '#3465A4'))}

[Color4Intense]
Color={hex_to_rgb(colors.get('terminal_color_4_bright', '#729FCF'))}

[Color5]
Color={hex_to_rgb(colors.get('terminal_color_5', '#75507B'))}

[Color5Intense]
Color={hex_to_rgb(colors.get('terminal_color_5_bright', '#AD7FA8'))}

[Color6]
Color={hex_to_rgb(colors.get('terminal_color_6', '#06989A'))}

[Color6Intense]
Color={hex_to_rgb(colors.get('terminal_color_6_bright', '#34E2E2'))}

[Color7]
Color={hex_to_rgb(colors.get('terminal_color_7', '#D3D7CF'))}

[Color7Intense]
Color={hex_to_rgb(colors.get('terminal_color_7_bright', '#EEEEEC'))}
"""

        # Create custom color scheme directory and file
        import os
        custom_scheme_dir = Path.home() / '.config' / 'vibe-coding-assistant' / 'color-schemes'
        custom_scheme_dir.mkdir(parents=True, exist_ok=True)

        scheme_file = custom_scheme_dir / 'CustomSkin.colorscheme'
        with open(scheme_file, 'w') as f:
            f.write(scheme_content)

        # Zastosuj schemat do wskazanego backendu albo do wszystkich zakładek.
        scheme_name = 'CustomSkin'
        bg = colors.get('terminal_bg', '#300A24')
        fg = colors.get('terminal_fg', '#EEEEEC')

        def _apply(backend):
            if backend is None:
                return
            try:
                backend.set_color_scheme(
                    scheme_dir=str(custom_scheme_dir), scheme_name=scheme_name,
                    background=bg, foreground=fg, colors=colors,
                )
            except Exception:
                pass

        if terminal_backend is not None:
            _apply(terminal_backend)
        else:
            for agent_id, tab in self.agent_tabs.items():
                _apply(getattr(tab, 'terminal_backend', None))

    @staticmethod
    def _macos_close_btn_bg() -> str:
        """macOS: obszar przycisku zamykania zakładki bywa jasny, przez co biały
        X (close_x.svg) zlewa się z tłem i widać go dopiero na hover (czerwone
        tło). Ciemna półprzezroczysta podkładka przywraca kontrast. Na Linux/Win
        nic nie zmieniamy (tam X jest dobrze widoczny na ciemnej zakładce)."""
        return ("background-color: rgba(0,0,0,0.38); border-radius: 3px;"
                if sys.platform == "darwin" else "")

    def _compose_tabbar_qss(self, colors: dict) -> str:
        """Arkusz stylu paska zakładek — JEDNO źródło dla startu i zmiany skórki.

        Wcześniej ten sam QSS istniał w dwóch kopiach (budowa UI i
        `apply_skin_colors`), które potrafiły się rozjechać. Gradientowej kreski
        nad aktywną zakładką tu NIE ma — QSS nie zna gradientu w ramce, rysuje ją
        `_AccentTabBar.paintEvent`.

        Uwaga: `padding`/`font-size` w `QTabBar::tab` są IGNOROWANE, bo pasek ma
        własny QStyle (Fusion). Rozmiar czcionki i ikon ustawiamy przez API.
        """
        close_icon_url = (Path(__file__).parent / "close_x.svg").as_posix()
        close_hover_url = (Path(__file__).parent / "close_x_hover.svg").as_posix()
        chevron_left_url = (Path(__file__).parent / "chevron-left.svg").as_posix()
        chevron_right_url = (Path(__file__).parent / "chevron-right.svg").as_posix()
        panel = colors.get('menu_bar_bg', theme.BG_PANEL)
        surface = colors.get('button_bg', theme.SURFACE)
        return f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabWidget::tab-bar {{
                alignment: left;
            }}
            QTabBar {{
                background-color: {panel};
            }}
            /* UWAGA: żadnej reguły `color` — nadpisałaby setTabTextColor, czyli
               kolor zakładki per agent (Funkcja #2 z 1.0.21). */
            QTabBar::tab {{
                background-color: transparent;
                padding: 8px 14px;
                margin-right: 2px;
                border: 1px solid transparent;
                border-bottom: none;
                border-top-left-radius: 9px;
                border-top-right-radius: 9px;
            }}
            QTabBar::tab:selected {{
                background-color: {surface};
                border: 1px solid {colors.get('border_color', theme.BORDER)};
                border-bottom: none;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {theme.SURFACE_HOVER};
            }}
            /* X zamykający: cienki, szary; po najechaniu biały na czerwonym kółku. */
            QTabBar::close-button {{
                image: url({close_icon_url});
                subcontrol-position: right;
                width: 16px;
                height: 16px;
                margin: 2px;
                border-radius: 4px;
                {self._macos_close_btn_bg()}
            }}
            QTabBar::close-button:hover {{
                image: url({close_hover_url});
                background-color: {theme.DANGER};
                border-radius: 4px;
            }}
            /* Strzałki przewijania (gdy zakładki się nie mieszczą). */
            QTabBar QToolButton {{
                background-color: {panel};
                border: none;
                border-radius: 6px;
                margin: 2px 0;
            }}
            QTabBar QToolButton:hover {{
                background-color: {theme.SURFACE_HOVER};
            }}
            QTabBar QToolButton::left-arrow {{
                image: url({chevron_left_url});
                width: 14px;
                height: 14px;
            }}
            QTabBar QToolButton::right-arrow {{
                image: url({chevron_right_url});
                width: 14px;
                height: 14px;
            }}
        """

    def _compose_main_qss(self, colors: dict) -> str:
        """Arkusz stylu QMainWindow + menu/dialogi/checkboxy. BEZ ramki akcentu —
        ramkę koloru aktywnego agenta rysuje ręcznie centralny widget (_AccentFrame),
        żeby nie kaskadować stylu na QTermWidget i nie gubić górnej/dolnej krawędzi."""
        checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")
        toggle_off_path = str(ASSETS_DIR / "icons" / "toggle-off.svg").replace("\\", "/")
        toggle_on_path = str(ASSETS_DIR / "icons" / "toggle-on.svg").replace("\\", "/")
        return f"""
            QMainWindow {{
                background-color: {colors['main_window_bg']};
            }}
            QMenuBar {{
                background-color: {colors['menu_bar_bg']};
                color: {colors['text_color']};
                border-bottom: 1px solid {colors['border_color']};
            }}
            QMenuBar::item:selected {{
                background-color: {colors['hover_color']};
            }}
            QMenu {{
                background-color: {colors['main_window_bg']};
                color: {colors['text_color']};
                border: 1px solid {colors['border_color']};
            }}
            QMenu::item:selected {{
                background-color: {colors['hover_color']};
            }}
            QStatusBar {{
                background-color: {colors['status_bar_bg']};
                color: {colors['text_color']};
                border-top: 1px solid {colors['border_color']};
            }}
            QLabel {{
                color: {colors['text_color']};
            }}
            QCheckBox {{
                color: {colors['text_color']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {colors['border_color']};
                border-radius: 5px;
                background-color: {theme.SURFACE};
            }}
            QCheckBox::indicator:hover {{
                border-color: {theme.ACCENT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {theme.ACCENT};
                border-color: {theme.ACCENT};
                border-radius: 5px;
                image: url("{checkmark_path}");
            }}
            /* „Auto-czytaj odpowiedzi" — przełącznik zamiast kwadracika.
               Qt nie animuje gałki, więc oba stany to gotowe obrazki. */
            QCheckBox#autoReadToggle {{
                color: {theme.TEXT_DIM};
                spacing: 10px;
            }}
            QCheckBox#autoReadToggle::indicator {{
                width: 42px;
                height: 24px;
                border: none;
                border-radius: 12px;
                background-color: transparent;
                image: url("{toggle_off_path}");
            }}
            QCheckBox#autoReadToggle::indicator:checked {{
                background-color: transparent;
                image: url("{toggle_on_path}");
            }}
            QCheckBox#autoReadToggle:hover {{
                color: {theme.TEXT};
            }}
            QMessageBox {{
                background-color: {colors['main_window_bg']};
                color: {colors['text_color']};
            }}
            QMessageBox QLabel {{
                color: {colors['text_color']};
            }}
            QMessageBox QPushButton {{
                background-color: {colors['button_bg']};
                color: {colors['text_color']};
                border: 1px solid {colors['border_color']};
                border-radius: 5px;
                padding: 6px 16px;
                min-width: 60px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {colors['button_hover']};
            }}
            QDialog {{
                background-color: {colors['main_window_bg']};
                color: {colors['text_color']};
            }}
            QDialog QLabel {{
                color: {colors['text_color']};
            }}
            QDialog QLineEdit {{
                background-color: {colors['input_bg']};
                color: {colors['text_color']};
                border: 1px solid {colors['border_color']};
                border-radius: 5px;
                padding: 6px;
            }}
            QDialog QPushButton {{
                background-color: {colors['button_bg']};
                color: {colors['text_color']};
                border: 1px solid {colors['border_color']};
                border-radius: 5px;
                padding: 6px 16px;
            }}
            QDialog QPushButton:hover {{
                background-color: {colors['button_hover']};
            }}
            QInputDialog {{
                background-color: {colors['main_window_bg']};
            }}
            QInputDialog QLabel {{
                color: {colors['text_color']};
            }}
            QInputDialog QLineEdit {{
                background-color: {colors['input_bg']};
                color: {colors['text_color']};
                border: 1px solid {colors['border_color']};
                border-radius: 5px;
                padding: 6px;
            }}
        """

    def apply_skin_colors(self, colors: dict = None):
        """Apply skin colors to all UI elements.

        This method updates all styled elements with the new colors.
        Can be called for live preview or permanent application.
        """
        if colors is None:
            colors = self.skin_colors

        # Główny arkusz stylu okna w osobnej metodzie — bo ramkę akcentu
        # (kolor aktywnego agenta) doklejamy do reguły QMainWindow, a NIE do
        # centralnego widżetu (tamto kaskadowało styl na QTermWidget: białe
        # ramki wokół terminala + zmienione suwaki).
        self.setStyleSheet(self._compose_main_qss(colors))

        # Apply styles to all agent tabs
        for agent_tab in self.agent_tabs.values():
            agent_tab.apply_styles(colors, self.skin_icons)

        # Tab widget styling — ten sam arkusz co przy budowie UI (jedno źródło,
        # inaczej zmiana skórki gubiła ikonę X i kształt zakładek).
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setStyleSheet(self._compose_tabbar_qss(colors))
            # Kolor tekstu zakładek (zależy od skórki). Ramka akcentu jest już
            # nałożona przez self.setStyleSheet(_compose_main_qss(...)) na górze
            # apply_skin_colors (z właściwym `colors`, ważne przy podglądzie skórki).
            self._recolor_all_tabs()

        # Button icon styles (transparent with colored icons)
        self._apply_button_icon_styles()

        # Store inactive panel color for changeEvent
        self._inactive_panel_bg = colors['inactive_panel_bg']

        # Apply terminal colors to all tabs
        self._apply_terminal_colors(colors)

    def _show_groq_api_dialog(self):
        """Show dialog to enter Groq API key."""
        current_key = self.stt.api_key or ""
        # Show masked key if exists
        display_key = current_key[:8] + "..." if len(current_key) > 8 else current_key

        key, ok = QInputDialog.getText(self, tr('dlg_groq_key_title'),
            tr('dlg_groq_key_prompt').format(key=display_key if display_key else tr('dlg_key_none')),
            QLineEdit.Normal)

        if ok and key:
            self.stt.set_api_key(key)
            self._save_settings()
            QMessageBox.information(self, tr('dlg_saved_title'),
                tr('dlg_groq_key_saved'))

    def _show_anthropic_api_dialog(self):
        """Show dialog to enter Anthropic API key."""
        current_key = getattr(self, 'anthropic_api_key', "") or ""
        # Show masked key if exists
        display_key = current_key[:8] + "..." if len(current_key) > 8 else current_key

        key, ok = QInputDialog.getText(self, tr('dlg_anthropic_key_title'),
            tr('dlg_anthropic_key_prompt').format(key=display_key if display_key else tr('dlg_key_none')),
            QLineEdit.Normal)

        if ok and key:
            self.anthropic_api_key = key
            self._save_settings()
            QMessageBox.information(self, tr('dlg_saved_title'),
                tr('dlg_anthropic_key_saved'))

    def _show_claude_command_dialog(self):
        """Show dialog to configure Claude Code command."""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('dlg_claude_cmd_title'))
        dialog.setMinimumWidth(500)

        # Path to checkmark icon
        checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")

        layout = QVBoxLayout(dialog)

        # Description
        desc_label = QLabel(tr('dlg_claude_cmd_desc'))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Command input
        cmd_layout = QHBoxLayout()
        cmd_label = QLabel(tr('dlg_claude_cmd_command_label'))
        cmd_input = QLineEdit(self.claude_command)
        cmd_input.setPlaceholderText("/usr/bin/claude")
        cmd_layout.addWidget(cmd_label)
        cmd_layout.addWidget(cmd_input, stretch=1)
        layout.addLayout(cmd_layout)

        # Auto-run checkbox
        auto_run_checkbox = QCheckBox(tr('dlg_claude_cmd_autorun'))
        auto_run_checkbox.setChecked(self.auto_run_claude)
        layout.addWidget(auto_run_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(dialog.reject)
        save_btn = QPushButton(tr('dlg_save'))
        save_btn.clicked.connect(dialog.accept)
        save_btn.setDefault(True)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)

        # Apply dark theme to dialog
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {self.skin_colors.get('main_window_bg', '#300A24')};
                color: {self.skin_colors.get('text_color', '#ffffff')};
            }}
            QLabel {{
                color: {self.skin_colors.get('text_color', '#ffffff')};
            }}
            QLineEdit {{
                background-color: {self.skin_colors.get('input_bg', '#300A24')};
                color: {self.skin_colors.get('text_color', '#ffffff')};
                border: 1px solid {self.skin_colors.get('border_color', '#4a1a3a')};
                border-radius: 5px;
                padding: 8px;
            }}
            QCheckBox {{
                color: {self.skin_colors.get('text_color', '#ffffff')};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {self.skin_colors.get('border_color', '#4a1a3a')};
                border-radius: 3px;
                background-color: transparent;
            }}
            QCheckBox::indicator:hover {{
                border-color: #22c55e;
            }}
            QCheckBox::indicator:checked {{
                background-color: #22c55e;
                border-color: #22c55e;
                border-radius: 3px;
                image: url("{checkmark_path}");
            }}
            QPushButton {{
                background-color: {self.skin_colors.get('button_bg', '#4a1a3a')};
                color: {self.skin_colors.get('text_color', '#ffffff')};
                border: 1px solid {self.skin_colors.get('border_color', '#4a1a3a')};
                border-radius: 5px;
                padding: 8px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {self.skin_colors.get('button_hover', '#6a2a5a')};
            }}
        """)

        if dialog.exec_() == QDialog.Accepted:
            self.claude_command = cmd_input.text().strip() or "/usr/bin/claude"
            self.auto_run_claude = auto_run_checkbox.isChecked()
            self._save_settings()
            QMessageBox.information(self, tr('dlg_saved_title'),
                tr('dlg_claude_cmd_saved').format(
                    command=self.claude_command,
                    autorun=tr('dlg_yes') if self.auto_run_claude else tr('dlg_no')))

    # ==================== Helpers ====================

    def _append_user_message(self, text: str):
        """Append user message to conversation - yellow/orange like terminal."""
        if not self.conversation_area:
            return  # Using QTermWidget - no need to append

        cursor = self.conversation_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Yellow/orange color for user prompt - like terminal
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#f59e0b"))
        fmt.setFontWeight(QFont.Bold)

        cursor.insertText("\n", QTextCharFormat())
        cursor.insertText(f"> {text}", fmt)
        cursor.insertText("\n", QTextCharFormat())

        self.conversation_area.setTextCursor(cursor)

    def _append_system_message(self, text: str):
        """Append system message to conversation - cyan like terminal."""
        if not self.conversation_area:
            # For terminal mode - just update status bar
            self._update_status(text)
            return

        cursor = self.conversation_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Cyan color for system messages
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#22d3ee"))

        cursor.insertText("\n", QTextCharFormat())
        cursor.insertText(f"[System] {text}", fmt)
        cursor.insertText("\n", QTextCharFormat())

        self.conversation_area.setTextCursor(cursor)

    # ============ Flaga "agent czeka na odpowiedź" (pomarańczowy ?) ============
    # Wykrywanie "agent czeka" idzie z dziennika sesji (reader.waiting_for_user()
    # w _poll_transcripts), NIE ze strumienia terminala — patrz tamten komentarz.

    def _agent_label_icon(self, agent_config):
        """Zwróć (tekst_zakładki, QIcon) dla agenta wg jego pola 'icon'.

        Emoji → prefiks w TEKŚCIE (renderuje się jak dotychczasowe '🤖 ');
        własny plik → QIcon (setTabIcon) + sam tekst nazwy; brak → '🤖 Nazwa'."""
        name = agent_config.get('name', 'Agent')
        spec = agent_config.get('icon')
        if isinstance(spec, dict):
            kind, val = spec.get('kind'), spec.get('value')
            if kind == 'emoji' and val:
                return f"{val} {name}", QIcon()
            if kind == 'file' and val:
                try:
                    if Path(val).exists():
                        return name, QIcon(str(val))
                except Exception:
                    pass
        # Domyślnie (brak własnej ikony): wbudowany OBRAZEK robota — nie emoji 🤖,
        # które na Windows renderowało się jak „diabełek". Ten sam wygląd wszędzie.
        return name, self._default_agent_icon()

    def _default_agent_icon(self) -> QIcon:
        """Domyślna ikona agenta = wbudowana grafika robota (src/assets/agent-robot.png).
        Cache'owana — jedna instancja QIcon na cały program."""
        ic = getattr(self, '_robot_icon', None)
        if ic is None:
            ic = QIcon(str(ASSETS_DIR / "agent-robot.png"))
            self._robot_icon = ic
        return ic

    # ============ Kolor zakładki + ramka okna (Funkcja #2) ============

    def _agent_tab_color(self, agent_config):
        """Zwróć hex koloru zakładki agenta (np. '#3b82f6') albo None."""
        if isinstance(agent_config, dict):
            c = agent_config.get('tab_color')
            if isinstance(c, str) and c:
                return c
        return None

    def _agent_voice(self, tab):
        """Głos TTS dla zakładki (Funkcja #3): własny 'tts_voice' agenta, a gdy
        brak — domyślny głos dla języka aplikacji (zachowanie sprzed Funkcji #3)."""
        cfg = getattr(tab, 'agent_config', None)
        if isinstance(cfg, dict):
            v = cfg.get('tts_voice')
            if isinstance(v, str) and v:
                return v
        if self.current_language in SUPPORTED_LANGUAGES:
            return SUPPORTED_LANGUAGES[self.current_language][2]
        return None

    def _recolor_all_tabs(self):
        """Ustaw kolor TEKSTU każdej zakładki: własny kolor agenta albo domyślny
        kolor skórki. Sterujemy przez API (setTabTextColor), bo jawne 'color'
        w arkuszu stylu QTabBar nadpisałoby ten kolor — dlatego usunęliśmy je
        z QSS. Zakładka „+" i terminalowe bez koloru dostają domyślny."""
        if not hasattr(self, 'tab_widget'):
            return
        bar = self.tab_widget.tabBar()
        default = QColor(self.skin_colors.get('text_color', '#ffffff'))
        for i in range(self.tab_widget.count()):
            w = self.tab_widget.widget(i)
            color = self._agent_tab_color(getattr(w, 'agent_config', None)) \
                if isinstance(w, AgentTab) else None
            bar.setTabTextColor(i, QColor(color) if color else default)

    def _active_accent_color(self):
        """Kolor akcentu = tab_color AKTYWNEGO agenta (albo None)."""
        tab = self._get_current_agent_tab()
        return self._agent_tab_color(getattr(tab, 'agent_config', None)) \
            if isinstance(tab, AgentTab) else None

    def _apply_active_tab_frame(self):
        """Ustaw kolor ramki akcentu = kolor AKTYWNEGO agenta (Funkcja #2).
        Ramkę rysuje ręcznie centralny widget (_AccentFrame.paintEvent) — pełne
        4 boki, bez arkusza stylu (więc bez białych ramek/suwaków na terminalu)."""
        central = self.centralWidget()
        if isinstance(central, _AccentFrame):
            central.set_accent(self._active_accent_color())

    def _question_icon(self) -> QIcon:
        icon = getattr(self, "_question_icon_cached", None)
        if icon is None:
            # SVG, nie emoji — emoji na Linuksie renderują się monochromatycznie.
            icon = QIcon(str(ASSETS_DIR / "icons" / "question.svg"))
            self._question_icon_cached = icon
        return icon

    def _arm_question(self, tab, armed: bool):
        """Ustaw stan 'agent czeka na odpowiedź' dla zakładki i odśwież ikonę.

        Stan jest niezależny od tego, czy zakładka jest aktywna — ikona pokaże
        się dopiero, gdy zakładka NIE jest na wierzchu (patrz _refresh). Dzięki
        temu pytanie, które padło, gdy patrzyłeś na zakładkę, zapali flagę
        zaraz po przełączeniu się gdzie indziej (nie ginie po konsumpcji).
        """
        if tab is None:
            return
        tab._armed_question = bool(armed)
        self._refresh_question_flag(tab)

    def _icon_with_flag(self, base_icon: QIcon) -> QIcon:
        """Ikona agenta z ŻÓŁTYM znaczkiem „?" wmalowanym w LEWY GÓRNY róg.
        Dla agentów z ikoną-obrazkiem: flaga skrajnie z lewej, NA ikonie, żółta
        (widoczna niezależnie od koloru nazwy), bez odstępu (część grafiki)."""
        size = 30
        src = base_icon.pixmap(size, size)
        canvas = QPixmap(size, size)
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing, True)
        if not src.isNull():
            p.drawPixmap(0, 0, src)
        d = 16  # średnica żółtego znaczka
        p.setBrush(QColor("#ffd400"))
        p.setPen(QPen(QColor("#7a5c00"), 1))
        p.drawEllipse(0, 0, d, d)
        p.setPen(QColor("#3a2c00"))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(12)
        p.setFont(f)
        p.drawText(QRect(0, 0, d, d), Qt.AlignCenter, "?")
        p.end()
        return QIcon(canvas)

    def _flag_only_icon(self) -> QIcon:
        """Samodzielny ŻÓŁTY znaczek „?" jako ikona zakładki — dla agentów z emoji
        (emoji zostaje w tekście; flaga jako ikona = skrajnie z lewej, żółta, BEZ
        zmiany koloru nazwy)."""
        size = 30
        canvas = QPixmap(size, size)
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing, True)
        d = 22
        off = (size - d) // 2
        p.setBrush(QColor("#ffd400"))
        p.setPen(QPen(QColor("#7a5c00"), 1))
        p.drawEllipse(off, off, d, d)
        p.setPen(QColor("#3a2c00"))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(15)
        p.setFont(f)
        p.drawText(QRect(off, off, d, d), Qt.AlignCenter, "?")
        p.end()
        return QIcon(canvas)

    def _tab_default_color(self, tab) -> QColor:
        """Normalny kolor tekstu zakładki: kolor agenta albo domyślny ze skórki."""
        c = self._agent_tab_color(getattr(tab, 'agent_config', None))
        return QColor(c) if c else QColor(self.skin_colors.get('text_color', '#ffffff'))

    def _flag_dbg(self, tab, state: str, key: str = "poll"):
        """Czujnik flagi „?": zapisz stan do pliku, ale TYLKO gdy się zmienił
        (throttle per (tab, key)) — żeby nie zalać logu. Aktywny wyłącznie przy
        CVA_FLAG_DEBUG=1. Pasywny: nie zmienia żadnego zachowania apki."""
        if not _FLAG_DEBUG:
            return
        try:
            name = (getattr(tab, 'agent_config', {}) or {}).get('name', '?')
            cache = getattr(tab, '_flag_dbg_last', None)
            if cache is None:
                cache = {}
                tab._flag_dbg_last = cache
            line = f"[{name}] {key}: {state}"
            if cache.get(key) == line:
                return  # bez zmiany — nie loguj ponownie
            cache[key] = line
            ts = datetime.now().strftime('%H:%M:%S')
            with open(CONFIG_DIR / "flag-debug.log", "a", encoding="utf-8") as f:
                f.write(f"{ts} {line}\n")
        except Exception:
            pass

    def _read_last_dbg(self, selected=None):
        """Diagnostyka przycisku 🔊 „czytaj ostatnią": dlaczego czyta coś innego?

        Loguje do read-last-debug.log stan DOKŁADNIE w chwili kliknięcia:
          • czy w terminalu jest ZAZNACZENIE (wtedy apka czyta je, NIE ostatnią
            odpowiedź — najczęstszy podejrzany o „czyta zupełnie coś innego");
          • stan pliku sesji: świeżość zapisu, liczbę wypowiedzi Claude'a, treść
            ostatniej i przedostatniej, kompletność ostatniej linii JSON;
          • co zwróci last_response() (ścieżka poprawna).
        Dzięki temu widać, KTÓRĄ gałęzią pójdzie odczyt. Aktywne tylko przy
        CVA_FLAG_DEBUG=1. Pasywne — NIE zmienia zachowania."""
        if not _FLAG_DEBUG:
            return
        try:
            tab = self._get_current_agent_tab()
            name = (getattr(tab, 'agent_config', {}) or {}).get('name', '?')
            reader = getattr(tab, '_transcript_reader', None) if tab else None
            ts = datetime.now().strftime('%H:%M:%S')
            sel = selected if isinstance(selected, str) else ''
            sel_prev = ' '.join(sel.split())[:80]
            branch = ("ZAZNACZENIE (czyta zaznaczenie!)" if sel.strip()
                      else "czytnik/last_response" if reader is not None
                      else "fallback bufor terminala")
            out = [f"{ts} [{name}] KLIK 🔊 czytaj-ostatnią  -> gałąź: {branch}"]
            out.append(f"   selected_text: len={len(sel)} treść={sel_prev!r}")
            if reader is None:
                out.append("   reader=None (brak czytnika)")
            else:
                ds = reader.debug_state() if hasattr(reader, 'debug_state') else {}
                sf = ds.get('session_file')
                out.append(f"   session_file={sf}")
                out.append(f"   exists={ds.get('exists')} pinned={ds.get('pinned')} "
                           f"offset={ds.get('offset')} wait_stable={ds.get('wait_stable')}")
                try:
                    out.append(f"   waiting_for_user={reader.waiting_for_user()}")
                except Exception as e:
                    out.append(f"   waiting_for_user błąd: {e}")
                texts = []
                last_line_ok = None  # czy ostatnia niepusta linia = kompletny JSON?
                if sf and os.path.exists(sf):
                    age = time.time() - os.path.getmtime(sf)
                    out.append(f"   plik: rozmiar={os.path.getsize(sf)}B  "
                               f"ostatni_zapis={age:.1f}s temu")
                    try:
                        with open(sf, encoding='utf-8', errors='ignore') as f:
                            for ln in f:
                                ln = ln.strip()
                                if not ln:
                                    continue
                                try:
                                    o = json.loads(ln)
                                    last_line_ok = True
                                except Exception:
                                    last_line_ok = False
                                    continue
                                if o.get('type') != 'assistant' or o.get('isSidechain'):
                                    continue
                                msg = o.get('message') or {}
                                c = msg.get('content')
                                if isinstance(c, list):
                                    parts = [b.get('text') for b in c if isinstance(b, dict)
                                             and b.get('type') == 'text' and b.get('text')]
                                    if parts:
                                        texts.append(' '.join('\n\n'.join(parts).split())[:80])
                    except Exception as e:
                        out.append(f"   (błąd czytania pliku: {e})")
                out.append(f"   ostatnia_linia_kompletny_JSON={last_line_ok}")
                out.append(f"   wypowiedzi_Claude_w_pliku={len(texts)}")
                if texts:
                    out.append(f"   OSTATNIA w pliku (to PRZECZYTA): {texts[-1]!r}")
                if len(texts) >= 2:
                    out.append(f"   PRZEDOSTATNIA w pliku:           {texts[-2]!r}")
                try:
                    lr = reader.last_response() or ''
                    out.append(f"   last_response() -> {' '.join(lr.split())[:80]!r}")
                except Exception as e:
                    out.append(f"   last_response() błąd: {e}")
            with open(CONFIG_DIR / "read-last-debug.log", "a", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
        except Exception:
            pass

    def _refresh_question_flag(self, tab):
        """Pokaż flagę „agent czeka", gdy zakładka uzbrojona I nieaktywna —
        SKRAJNIE Z LEWEJ i ŻÓŁTĄ, by była widoczna i przy ikonie:
          • agent z ikoną-obrazkiem → żółty znaczek „?" wmalowany w lewy róg ikony;
          • agent z emoji (ikona = emoji w tekście) → żółty prefiks „❓ " + żółta nazwa.
        Samonaprawiająca się (porównuje stan docelowy z realnym przy każdym ticku)."""
        if tab is None:
            return
        index = self.tab_widget.indexOf(tab)
        if index < 0:
            return
        cfg = getattr(tab, 'agent_config', {})
        base_label, base_icon = self._agent_label_icon(cfg)
        show = getattr(tab, "_armed_question", False) \
            and tab is not self.tab_widget.currentWidget()
        # NO-OP, gdy nic się nie zmieniło. KLUCZOWE: ta metoda biegnie co ~0,8 s
        # (timer flag), a setTabIcon/setTabTextColor RESETUJĄ przewinięcie paska
        # zakładek — bez tego strażnika tabki wracały na miejsce zaraz po kliknięciu
        # strzałki przewijania. Sygnatura ze STABILNYCH danych (nie z QIcon, bo dla
        # ikony-pliku tworzona jest świeża instancja przy każdym wywołaniu).
        sig = (show, base_label, repr(cfg.get('icon')))
        _skipped = getattr(tab, "_flag_sig", None) == sig
        if _FLAG_DEBUG:
            try:
                _icon_null = int(self.tab_widget.tabIcon(index).isNull())
            except Exception:
                _icon_null = -1
            self._flag_dbg(
                tab,
                f"show={int(show)} skip={int(_skipped)} "
                f"real_icon_null={_icon_null} base_icon_null={int(base_icon.isNull())}",
                key="refresh",
            )
        if _skipped:
            return
        tab._flag_sig = sig
        bar = self.tab_widget.tabBar()
        # Nazwa i kolor tytułu ZAWSZE normalne — flaga to wyłącznie ŻÓŁTA IKONA z lewej.
        if self.tab_widget.tabText(index) != base_label:
            self.tab_widget.setTabText(index, base_label)
        bar.setTabTextColor(index, self._tab_default_color(tab))
        if not base_icon.isNull():
            # Ikona-obrazek: żółty znaczek „?" wmalowany w róg ikony agenta.
            self.tab_widget.setTabIcon(
                index, self._icon_with_flag(base_icon) if show else base_icon)
        else:
            # Emoji w tekście: flaga jako samodzielna żółta ikonka „?" (emoji zostaje
            # w tekście, tytuł normalny). Brak flagi → brak ikony (emoji w nazwie).
            self.tab_widget.setTabIcon(
                index, self._flag_only_icon() if show else QIcon())
        self.tab_widget.setTabToolTip(
            index, tr('dlg_agent_waiting_tooltip') if show else "")

    def _refresh_all_question_flags(self):
        """Przelicz flagi wszystkich zakładek (np. po zmianie aktywnej)."""
        for tab in list(getattr(self, "agent_tabs", {}).values()):
            if isinstance(tab, AgentTab):
                self._refresh_question_flag(tab)

    def _update_status(self, text: str):
        """Update status bar."""
        # Przy starcie pierwszy addTab() emituje currentChanged ZANIM powstanie
        # status_bar — na ścieżce WebTerminal (Windows/macOS) _on_tab_changed
        # dochodził tu i AttributeError PRZERYWAŁ resztę slotu (agent się nie
        # uruchamiał). Brak paska = po prostu pomiń komunikat.
        bar = getattr(self, "status_bar", None)
        if bar is not None:
            bar.showMessage(text)

    def _update_context_usage(self, additional_chars: int = 0):
        """Dolicz znaki do licznika aktywnej zakładki + globalnego sumatora aplikacji.

        Wzór: 1 token ≈ 3,5 znaku (przybliżenie dla polskiego).
        Per-agent licznik resetuje się przy /clear, /compact, restarcie.
        Globalny licznik resetuje się tylko przy restarcie aplikacji.

        Odświeżanie UI jest throttlowane (max 1 raz na 200 ms) — patrz
        _schedule_tokens_refresh. Liczniki same akumulują się bez strat.
        """
        tab = self._get_current_agent_tab()
        if tab is None:
            return
        additional_tokens = int(additional_chars / self._chars_per_token)
        tab.total_context_tokens += additional_tokens
        self._total_app_tokens += additional_tokens
        self._schedule_tokens_refresh()

    def _schedule_tokens_refresh(self):
        """Throttle: pierwsze wywołanie schedują odświeżenie za 200 ms,
        kolejne (do tego momentu) tylko podbijają liczniki bez kolejnych timerów."""
        if self._refresh_tokens_pending:
            return
        self._refresh_tokens_pending = True
        QTimer.singleShot(200, self._do_tokens_refresh)

    def _do_tokens_refresh(self):
        self._refresh_tokens_pending = False
        self._refresh_context_label()
        self._refresh_total_tokens_label()

    def _refresh_context_label(self):
        """Pokaż licznik tokenów + procent okna kontekstu modelu aktywnej zakładki.

        Kolor zależy od procentu wykorzystania okna modelu:
          <50% zielony, 50–70% żółty, 70–90% pomarańczowy, ≥90% czerwony.
        Format: "10,333 (5%)".
        """
        tab = self._get_current_agent_tab()
        tokens = tab.total_context_tokens if tab is not None else 0
        model_key = tab.model if tab is not None else DEFAULT_AGENT_MODEL
        limit = CLAUDE_MODEL_CONTEXT_LIMITS.get(model_key) or \
                CLAUDE_MODEL_CONTEXT_LIMITS.get(DEFAULT_AGENT_MODEL, 1_000_000)
        percentage = (tokens / limit) * 100.0 if limit > 0 else 0.0

        if percentage < 50:
            color = "#4ade80"   # zielony
        elif percentage < 70:
            color = "#facc15"   # żółty
        elif percentage < 90:
            color = "#f97316"   # pomarańczowy
        else:
            color = "#ef4444"   # czerwony

        self._context_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                padding: 0 10px 0 4px;
                font-weight: bold;
            }}
        """)
        # Wyświetl % bez miejsc po przecinku poniżej 10%, jedno miejsce powyżej 100% nie wystąpi.
        pct_text = f"{percentage:.0f}%" if percentage >= 1 else f"{percentage:.1f}%"
        # 2× NBSP dla odstępu między liczbą a procentem (fonty proporcjonalne
        # potrafią łączyć wielokrotne zwykłe spacje w jedną — NBSP gwarantuje rozdzielenie).
        self._context_label.setText(f"{tokens:,}  ({pct_text})")

        # Pasek postępu: to samo wypełnienie i ten sam kolor co liczba.
        if hasattr(self, "_context_bar"):
            bar_value = int(round(min(100.0, percentage)))
            # Przy bardzo małym, ale niezerowym zużyciu pokaż widoczny „okruszek",
            # żeby pasek nie wyglądał na całkiem pusty gdy tokeny już są.
            if bar_value == 0 and tokens > 0:
                bar_value = 1
            self._context_bar.setValue(bar_value)
            self._context_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #2a2a2e;
                    border: 1px solid #3a3a3e;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 2px;
                }}
            """)

    def _refresh_total_tokens_label(self):
        """Aktualizuj globalny licznik (Σ N) w widgecie statusu."""
        if hasattr(self, "mcp_status_widget") and self.mcp_status_widget is not None:
            self.mcp_status_widget.set_total_tokens(self._total_app_tokens)

    def _reset_context_usage(self):
        """Wyzeruj licznik tokenów aktywnej zakładki (np. po /clear lub /compact).

        UWAGA: globalny licznik aplikacji NIE jest zerowany — to suma od startu.
        """
        tab = self._get_current_agent_tab()
        if tab is not None:
            tab.total_context_tokens = 0
        self._refresh_context_label()

    def resizeEvent(self, event):
        """Handle window resize."""
        super().resizeEvent(event)
        # NOTE: Removed auto-scroll on resize - user controls scroll position manually
        # This prevents unwanted jumps on rotated/portrait monitors

    def closeEvent(self, event):
        """Handle window close.

        Aktualizacje sprawdzamy WYŁĄCZNIE przy starcie aplikacji (patrz
        `_maybe_auto_check_updates`). Zamykanie jest natychmiastowe — żadnego
        odpytywania serwera „na wyjściu", które kiedyś opóźniało zamknięcie.
        """
        # Remove menu position fixer
        if hasattr(self, '_menu_fixer'):
            QApplication.instance().removeEventFilter(self._menu_fixer)

        # Stop scroll manager
        if hasattr(self, '_scroll_manager') and self._scroll_manager:
            self._scroll_manager.stop()

        # Zatrzymaj wskaźnik zużycia RAM (timer odświeżania).
        if hasattr(self, 'resource_monitor') and self.resource_monitor is not None:
            self.resource_monitor.stop()

        self.tts.stop()
        self.stt.cancel_recording()

        if self.terminal_backend:
            # Terminal cleanup
            if hasattr(self, '_tts_timer'):
                self._tts_timer.stop()
        else:
            self.claude.stop()

        # Zamknij backendy wszystkich zakładek (WebTerminal ubija wątek-czytnik
        # PTY i proces powłoki; QTermWidget — no-op, sprząta się sam).
        for tab in self.agent_tabs.values():
            backend = getattr(tab, 'terminal_backend', None)
            if backend is not None:
                try:
                    backend.shutdown()
                except Exception:
                    pass

        self._save_settings()
        event.accept()

    def changeEvent(self, event):
        """Handle window activation/deactivation - change bottom panel color."""
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                # Window is active - use custom bottom panel color
                self.bottom_panel.setStyleSheet(f"""
                    QFrame {{
                        background-color: {self.skin_colors['bottom_panel_bg']};
                        border-radius: 10px;
                        padding: 5px;
                    }}
                """)
            else:
                # Window is inactive - use custom inactive color
                inactive_bg = getattr(self, '_inactive_panel_bg', self.skin_colors.get('inactive_panel_bg', '#3a3a3c'))
                self.bottom_panel.setStyleSheet(f"""
                    QFrame {{
                        background-color: {inactive_bg};
                        border-radius: 10px;
                        padding: 5px;
                    }}
                """)
        super().changeEvent(event)


class QuickActionsDialog(QDialog):
    """Dialog do zarządzania szybkimi akcjami."""

    def __init__(self, parent, quick_actions: list):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_qa_manage_title'))
        self.setMinimumSize(500, 450)
        self.quick_actions = [a.copy() for a in quick_actions]  # Deep copy
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel(tr('dlg_qa_manage_header'))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # List of actions
        list_layout = QHBoxLayout()

        # Table-like list with two columns
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([tr('dlg_qa_col_label'), tr('dlg_qa_col_command')])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                gridline-color: #4a1a3a;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #6a2a5a;
            }
            QHeaderView::section {
                background-color: #4a1a3a;
                color: #ffffff;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        """)
        self._populate_table()
        list_layout.addWidget(self.table, 1)

        # Buttons on the right side
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)

        self.up_btn = QPushButton(tr('dlg_qa_up'))
        self.up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton(tr('dlg_qa_down'))
        self.down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self.down_btn)

        btn_layout.addSpacing(10)

        self.edit_btn = QPushButton(f"✏️ {tr('dlg_edit')}")
        self.edit_btn.clicked.connect(self._edit_action)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton(f"🗑️ {tr('dlg_delete')}")
        self.delete_btn.clicked.connect(self._delete_action)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout)

        # Add new action section
        add_group = QGroupBox(tr('dlg_qa_add_group'))
        add_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        add_layout = QFormLayout(add_group)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText(tr('dlg_quick_label_placeholder'))
        self.label_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        add_layout.addRow(tr('dlg_qa_label_label'), self.label_input)

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(tr('dlg_quick_command_placeholder'))
        self.command_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        add_layout.addRow(tr('dlg_quick_command_label'), self.command_input)

        add_btn_layout = QHBoxLayout()
        add_btn_layout.addStretch()
        self.add_btn = QPushButton(f"➕ {tr('dlg_add')}")
        self.add_btn.clicked.connect(self._add_action)
        self.add_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        add_btn_layout.addWidget(self.add_btn)
        add_layout.addRow("", add_btn_layout)

        layout.addWidget(add_group)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        restore_btn = QPushButton(tr('dlg_qa_restore_defaults'))
        restore_btn.clicked.connect(self._restore_defaults)
        bottom_layout.addWidget(restore_btn)

        bottom_layout.addStretch()

        close_btn = QPushButton(tr('dlg_close'))
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _populate_table(self):
        """Fill table with quick actions."""
        self.table.setRowCount(len(self.quick_actions))
        for i, action in enumerate(self.quick_actions):
            label_item = QTableWidgetItem(action['label'])
            command_item = QTableWidgetItem(action['command'])
            self.table.setItem(i, 0, label_item)
            self.table.setItem(i, 1, command_item)

    def _get_selected_row(self) -> int:
        """Get currently selected row index, or -1 if none."""
        selected = self.table.selectedItems()
        if selected:
            return selected[0].row()
        return -1

    def _move_up(self):
        """Move selected action up."""
        row = self._get_selected_row()
        if row > 0:
            self.quick_actions[row], self.quick_actions[row - 1] = \
                self.quick_actions[row - 1], self.quick_actions[row]
            self._populate_table()
            self.table.selectRow(row - 1)

    def _move_down(self):
        """Move selected action down."""
        row = self._get_selected_row()
        if 0 <= row < len(self.quick_actions) - 1:
            self.quick_actions[row], self.quick_actions[row + 1] = \
                self.quick_actions[row + 1], self.quick_actions[row]
            self._populate_table()
            self.table.selectRow(row + 1)

    def _edit_action(self):
        """Edit selected action."""
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_qa_select_to_edit'))
            return

        action = self.quick_actions[row]

        label, ok1 = QInputDialog.getText(
            self, tr('dlg_qa_edit_title'), tr('dlg_qa_label_label'),
            text=action['label']
        )
        if ok1 and label:
            command, ok2 = QInputDialog.getText(
                self, tr('dlg_qa_edit_title'), tr('dlg_quick_command_label'),
                text=action['command']
            )
            if ok2 and command:
                self.quick_actions[row] = {'label': label, 'command': command}
                self._populate_table()
                self.table.selectRow(row)

    def _delete_action(self):
        """Delete selected action."""
        row = self._get_selected_row()
        if row < 0:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_qa_select_to_delete'))
            return

        action = self.quick_actions[row]
        reply = QMessageBox.question(
            self, tr('dlg_confirm_delete_title'),
            tr('dlg_qa_confirm_delete_msg').format(label=action['label']),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.quick_actions[row]
            self._populate_table()

    def _add_action(self):
        """Add new action from input fields."""
        label = self.label_input.text().strip()
        command = self.command_input.text().strip()

        if not label:
            QMessageBox.warning(self, tr('dlg_qa_no_label_title'), tr('dlg_qa_no_label_msg'))
            self.label_input.setFocus()
            return

        if not command:
            QMessageBox.warning(self, tr('dlg_qa_no_command_title'), tr('dlg_qa_no_command_msg'))
            self.command_input.setFocus()
            return

        self.quick_actions.append({'label': label, 'command': command})
        self._populate_table()

        # Clear inputs
        self.label_input.clear()
        self.command_input.clear()
        self.label_input.setFocus()

        # Select newly added row
        self.table.selectRow(len(self.quick_actions) - 1)

    def _restore_defaults(self):
        """Restore default quick actions."""
        reply = QMessageBox.question(
            self, tr('dlg_qa_restore_defaults'),
            tr('dlg_qa_restore_confirm_msg'),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # DEFAULT_QUICK_ACTIONS jest importowane na górze modułu (absolutnie).
            self.quick_actions = [a.copy() for a in DEFAULT_QUICK_ACTIONS]
            self._populate_table()

    def get_quick_actions(self) -> list:
        """Return the modified quick actions list."""
        return self.quick_actions


class SkinSettingsDialog(QDialog):
    """Dialog do personalizacji kolorów i ikon skórki aplikacji."""

    def __init__(self, parent, current_colors: dict, current_icons: dict = None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_skin_title'))
        self.setMinimumSize(550, 700)
        self.setStyleSheet("""
            QToolTip {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                padding: 5px;
                border-radius: 4px;
            }
        """)
        self.parent_window = parent
        self.colors = current_colors.copy()
        self.icons = {k: v.copy() for k, v in (current_icons or DEFAULT_SKIN_ICONS).items()}
        self.color_buttons = {}
        self.icon_buttons = {}

        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel(tr('dlg_skin_header'))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Import/Export buttons row
        import_export_layout = QHBoxLayout()

        import_btn = QPushButton(tr('dlg_skin_import'))
        import_btn.clicked.connect(self._import_skin)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        import_export_layout.addWidget(import_btn)

        export_btn = QPushButton(tr('dlg_skin_export'))
        export_btn.clicked.connect(self._export_skin)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
        """)
        import_export_layout.addWidget(export_btn)

        # Help button
        help_btn = QPushButton(tr('dlg_skin_help_btn'))
        help_btn.clicked.connect(self._show_icons_help)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        import_export_layout.addWidget(help_btn)

        import_export_layout.addStretch()
        layout.addLayout(import_export_layout)

        # Scroll area for color buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #4a1a3a;
                border-radius: 8px;
                background-color: #1a0a14;
            }
        """)

        # Container for color settings
        container = QWidget()
        container.setStyleSheet("background-color: #2d0a1e;")
        colors_layout = QVBoxLayout(container)
        colors_layout.setSpacing(10)

        # Group: Main colors
        main_group = QGroupBox(tr('dlg_skin_group_main'))
        main_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QGroupBox QLabel {
                color: #ffffff;
            }
        """)
        main_layout = QGridLayout(main_group)

        main_colors = ['main_window_bg', 'menu_bar_bg', 'status_bar_bg', 'bottom_panel_bg']
        for i, key in enumerate(main_colors):
            self._add_color_row(main_layout, i, key)

        colors_layout.addWidget(main_group)

        # Group: Borders and effects
        borders_group = QGroupBox(tr('dlg_skin_group_borders'))
        borders_group.setStyleSheet(main_group.styleSheet())
        borders_layout = QGridLayout(borders_group)

        border_colors = ['border_color', 'hover_color', 'splitter_color']
        for i, key in enumerate(border_colors):
            self._add_color_row(borders_layout, i, key)

        colors_layout.addWidget(borders_group)

        # Group: Text and buttons
        text_group = QGroupBox(tr('dlg_skin_group_text'))
        text_group.setStyleSheet(main_group.styleSheet())
        text_layout = QGridLayout(text_group)

        text_colors = ['text_color', 'button_bg', 'button_hover', 'input_bg', 'inactive_panel_bg']
        for i, key in enumerate(text_colors):
            self._add_color_row(text_layout, i, key)

        colors_layout.addWidget(text_group)

        # Group: Terminal background and text
        terminal_bg_group = QGroupBox(tr('dlg_skin_group_terminal'))
        terminal_bg_group.setStyleSheet(main_group.styleSheet())
        terminal_bg_layout = QGridLayout(terminal_bg_group)

        terminal_bg_colors = ['terminal_bg', 'terminal_fg']
        for i, key in enumerate(terminal_bg_colors):
            self._add_color_row(terminal_bg_layout, i, key)

        colors_layout.addWidget(terminal_bg_group)

        # Group: Icon colors
        icon_colors_group = QGroupBox(tr('dlg_skin_group_icon_colors'))
        icon_colors_group.setStyleSheet(main_group.styleSheet())
        icon_colors_layout = QGridLayout(icon_colors_group)

        icon_color_keys = ['icon_dictate_color', 'icon_read_color', 'icon_pause_color',
                           'icon_stop_color', 'icon_copy_color', 'icon_clear_input_color',
                           'icon_add_media_color', 'icon_send_color', 'icon_quick_actions_color']
        for i, key in enumerate(icon_color_keys):
            self._add_color_row(icon_colors_layout, i, key)

        colors_layout.addWidget(icon_colors_group)

        # Group: Button icons
        icons_group = QGroupBox(tr('dlg_skin_group_icons'))
        icons_group.setStyleSheet(main_group.styleSheet())
        icons_layout = QGridLayout(icons_group)

        row = 0
        for icon_key in SKIN_ICON_NAMES.keys():
            self._add_icon_row(icons_layout, row, icon_key)
            row += 1

        colors_layout.addWidget(icons_group)

        colors_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Buttons row
        buttons_layout = QHBoxLayout()

        # Reset to defaults button
        reset_btn = QPushButton(tr('dlg_skin_reset'))
        reset_btn.clicked.connect(self._reset_to_defaults)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        buttons_layout.addWidget(reset_btn)

        buttons_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #6a2a5a;
            }
        """)
        buttons_layout.addWidget(cancel_btn)

        # Apply button
        apply_btn = QPushButton(tr('dlg_skin_apply'))
        apply_btn.clicked.connect(self._apply_colors)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #0f172a;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
        """)
        buttons_layout.addWidget(apply_btn)

        layout.addLayout(buttons_layout)

    def _add_color_row(self, layout: QGridLayout, row: int, color_key: str):
        """Add a color picker row to the layout."""
        # Label
        label = QLabel(_skin_color_name(color_key))
        label.setStyleSheet("color: #ffffff; font-weight: 500;")
        layout.addWidget(label, row, 0)

        # Color button (shows current color)
        color_btn = QPushButton()
        color_btn.setFixedSize(80, 30)
        color_btn.setCursor(Qt.PointingHandCursor)
        self._update_color_button(color_btn, self.colors[color_key])
        color_btn.clicked.connect(lambda checked, k=color_key: self._pick_color(k))
        layout.addWidget(color_btn, row, 1)

        # Hex value label
        hex_label = QLabel(self.colors[color_key])
        hex_label.setStyleSheet("color: #9ca3af; font-family: monospace;")
        hex_label.setFixedWidth(80)
        layout.addWidget(hex_label, row, 2)

        self.color_buttons[color_key] = (color_btn, hex_label)

    def _update_color_button(self, button: QPushButton, color: str):
        """Update button appearance with the selected color."""
        # Calculate contrasting text color
        qcolor = QColor(color)
        luminance = (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
        text_color = "#000000" if luminance > 0.5 else "#ffffff"

        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: 2px solid #6a2a5a;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: #ffffff;
            }}
        """)
        button.setText(color)

    def _pick_color(self, color_key: str):
        """Open color picker for the specified color."""
        current_color = QColor(self.colors[color_key])
        color = QColorDialog.getColor(
            current_color,
            self,
            tr('dlg_skin_pick_color').format(name=_skin_color_name(color_key)),
            QColorDialog.ShowAlphaChannel
        )

        if color.isValid():
            hex_color = color.name()
            self.colors[color_key] = hex_color

            # Update button appearance
            btn, hex_label = self.color_buttons[color_key]
            self._update_color_button(btn, hex_color)
            hex_label.setText(hex_color)

            # Live preview
            self._preview_colors()

    def _preview_colors(self):
        """Apply colors as live preview."""
        if hasattr(self.parent_window, 'apply_skin_colors'):
            self.parent_window.apply_skin_colors(self.colors)

    def _add_icon_row(self, layout: QGridLayout, row: int, icon_key: str):
        """Add an icon picker row to the layout."""
        # Label
        label = QLabel(_skin_icon_name(icon_key))
        label.setStyleSheet("color: #ffffff; font-weight: 500;")
        layout.addWidget(label, row, 0)

        icon_data = self.icons.get(icon_key, {})
        default_icon_data = DEFAULT_SKIN_ICONS.get(icon_key, {})

        # Get colors for each state
        normal_color = icon_data.get('normal_color', self.colors.get(f'icon_{icon_key}_color', '#ffffff'))
        active_color = icon_data.get('active_color', self.colors.get(f'icon_{icon_key}_color', '#ffffff'))

        # Normal icon button with its color
        normal_btn = QPushButton(icon_data.get('normal', '?'))
        normal_btn.setFixedSize(50, 30)
        normal_btn.setToolTip(tr('dlg_skin_icon_normal_tooltip'))
        normal_btn.setCursor(Qt.PointingHandCursor)
        normal_btn.setStyleSheet(self._get_icon_btn_style(normal_color))
        normal_btn.clicked.connect(lambda: self._edit_icon(icon_key, 'normal'))
        layout.addWidget(normal_btn, row, 1)

        # Active icon button with its color
        active_btn = QPushButton(icon_data.get('active', icon_data.get('normal', '?')))
        active_btn.setFixedSize(50, 30)
        active_btn.setToolTip(tr('dlg_skin_icon_active_tooltip'))
        active_btn.setCursor(Qt.PointingHandCursor)
        active_btn.setStyleSheet(self._get_icon_btn_style(active_color))
        active_btn.clicked.connect(lambda: self._edit_icon(icon_key, 'active'))
        layout.addWidget(active_btn, row, 2)

        self.icon_buttons[icon_key] = {'normal': normal_btn, 'active': active_btn}

        # Processing icon button (only for icons that have processing state)
        if 'processing' in default_icon_data:
            processing_color = icon_data.get('processing_color', self.colors.get(f'icon_{icon_key}_color', '#ffffff'))
            processing_btn = QPushButton(icon_data.get('processing', default_icon_data.get('processing', '⏳')))
            processing_btn.setFixedSize(50, 30)
            processing_btn.setToolTip(tr('dlg_skin_icon_processing_tooltip'))
            processing_btn.setCursor(Qt.PointingHandCursor)
            processing_btn.setStyleSheet(self._get_icon_btn_style(processing_color))
            processing_btn.clicked.connect(lambda: self._edit_icon(icon_key, 'processing'))
            layout.addWidget(processing_btn, row, 3)
            self.icon_buttons[icon_key]['processing'] = processing_btn

    def _get_icon_btn_style(self, color: str) -> str:
        """Get button style with specified icon color."""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 1px solid #6a2a5a;
                border-radius: 4px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: rgba(106, 42, 90, 0.5);
            }}
        """

    def _edit_icon(self, icon_key: str, state: str):
        """Edit icon text/emoji with color picker."""
        icon_data = self.icons.get(icon_key, {})
        current_text = icon_data.get(state, '')
        color_key = f'{state}_color'
        current_color = icon_data.get(color_key, self.colors.get(f'icon_{icon_key}_color', '#ffffff'))

        # Create custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('dlg_skin_change_icon_title').format(name=_skin_icon_name(icon_key)))
        dialog.setFixedWidth(300)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2d1a2d;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #1a0a1a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 4px;
                padding: 8px;
                font-size: 18px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(dialog)

        # Label
        label = QLabel(tr('dlg_skin_icon_input_label').format(state=state))
        layout.addWidget(label)

        # Text input with color preview
        input_layout = QHBoxLayout()

        text_input = QLineEdit(current_text)
        text_input.setFixedHeight(40)

        # Color picker button
        color_btn = QPushButton()
        color_btn.setFixedSize(40, 40)
        color_btn.setCursor(Qt.PointingHandCursor)
        color_btn.setToolTip(tr('dlg_skin_pick_icon_color_tooltip'))

        selected_color = [current_color]  # Use list to allow modification in nested function

        def update_color_btn():
            qcolor = QColor(selected_color[0])
            luminance = (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
            text_color = "#000000" if luminance > 0.5 else "#ffffff"
            color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {selected_color[0]};
                    color: {text_color};
                    border: 2px solid #6a2a5a;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 2px solid #ffffff;
                }}
            """)
            # Update text input color preview
            text_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #1a0a1a;
                    color: {selected_color[0]};
                    border: 1px solid #6a2a5a;
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 18px;
                }}
            """)

        def pick_color():
            color = QColorDialog.getColor(
                QColor(selected_color[0]),
                dialog,
                tr('dlg_skin_pick_icon_color_title'),
                QColorDialog.ShowAlphaChannel
            )
            if color.isValid():
                selected_color[0] = color.name()
                update_color_btn()

        color_btn.clicked.connect(pick_color)
        update_color_btn()

        input_layout.addWidget(text_input, stretch=1)
        input_layout.addWidget(color_btn)
        layout.addLayout(input_layout)

        # Buttons
        buttons_layout = QHBoxLayout()

        cancel_btn = QPushButton("✕ Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #6a2a5a;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)

        ok_btn = QPushButton("✓ OK")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #000000;
                border: none;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        ok_btn.setDefault(True)

        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(ok_btn)
        layout.addLayout(buttons_layout)

        # Show dialog
        if dialog.exec_() == QDialog.Accepted:
            text = text_input.text()
            if text:
                if icon_key not in self.icons:
                    self.icons[icon_key] = {}
                self.icons[icon_key][state] = text
                self.icons[icon_key][color_key] = selected_color[0]

                # Update button text and color
                if icon_key in self.icon_buttons and state in self.icon_buttons[icon_key]:
                    btn = self.icon_buttons[icon_key][state]
                    btn.setText(text)
                    btn.setStyleSheet(self._get_icon_btn_style(selected_color[0]))

    def _show_icons_help(self):
        """Show help dialog with instructions for icons."""
        help_text = tr('dlg_skin_help_body')

        msg = QMessageBox(self)
        msg.setWindowTitle(tr('dlg_skin_help_title'))
        msg.setTextFormat(Qt.RichText)
        msg.setText(help_text)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1a0a14;
            }
            QMessageBox QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 5px;
                padding: 6px 20px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #6a2a5a;
            }
        """)
        msg.exec_()

    def _import_skin(self):
        """Import skin from JSON file."""
        file_path, _ = styled_get_open_file_name(
            self,
            tr('dlg_skin_import_title'),
            str(Path.home()),
            tr('dlg_skin_filter')
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    skin_data = json.load(f)

                # Load colors
                if 'colors' in skin_data:
                    for key, value in skin_data['colors'].items():
                        if key in DEFAULT_SKIN_COLORS:
                            self.colors[key] = value
                    # Update color buttons
                    for key, (btn, hex_label) in self.color_buttons.items():
                        self._update_color_button(btn, self.colors[key])
                        hex_label.setText(self.colors[key])

                # Load icons
                if 'icons' in skin_data:
                    for key, states in skin_data['icons'].items():
                        if key in DEFAULT_SKIN_ICONS:
                            self.icons[key] = states
                    # Update icon buttons
                    for key, buttons in self.icon_buttons.items():
                        icon_data = self.icons.get(key, {})
                        if 'normal' in buttons:
                            buttons['normal'].setText(icon_data.get('normal', '?'))
                        if 'active' in buttons:
                            buttons['active'].setText(icon_data.get('active', icon_data.get('normal', '?')))

                self._preview_colors()
                QMessageBox.information(self, tr('dlg_skin_success_title'), tr('dlg_skin_loaded_msg').format(path=file_path))

            except Exception as e:
                QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_skin_load_failed_msg').format(error=e))

    def _export_skin(self):
        """Export skin to JSON file."""
        file_path, _ = styled_get_save_file_name(
            self,
            tr('dlg_skin_export_title'),
            str(Path.home() / "moja_skorka.skin.json"),
            tr('dlg_skin_filter')
        )
        if file_path:
            try:
                skin_data = {
                    'name': tr('dlg_skin_default_name'),
                    'version': '1.0',
                    'colors': self.colors,
                    'icons': self.icons
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(skin_data, f, indent=2, ensure_ascii=False)

                QMessageBox.information(self, tr('dlg_skin_success_title'), tr('dlg_skin_saved_msg').format(path=file_path))

            except Exception as e:
                QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_skin_save_failed_msg').format(error=e))

    def _reset_to_defaults(self):
        """Reset all colors and icons to Ubuntu defaults."""
        self.colors = DEFAULT_SKIN_COLORS.copy()
        self.icons = {k: v.copy() for k, v in DEFAULT_SKIN_ICONS.items()}

        # Update all color buttons
        for key, (btn, hex_label) in self.color_buttons.items():
            self._update_color_button(btn, self.colors[key])
            hex_label.setText(self.colors[key])

        # Update all icon buttons
        for key, buttons in self.icon_buttons.items():
            icon_data = self.icons.get(key, {})
            if 'normal' in buttons:
                buttons['normal'].setText(icon_data.get('normal', '?'))
            if 'active' in buttons:
                buttons['active'].setText(icon_data.get('active', icon_data.get('normal', '?')))

        # Apply preview
        self._preview_colors()

    def _apply_colors(self):
        """Apply colors and close dialog."""
        self.accept()

    def get_colors(self) -> dict:
        """Return the selected colors."""
        return self.colors

    def get_icons(self) -> dict:
        """Return the selected icons."""
        return self.icons


class SettingsDialog(QDialog):
    """Settings dialog."""

    def __init__(self, parent, current_api_key: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_settings_title'))
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        # Groq API Key
        self.api_key_field = QLineEdit()
        self.api_key_field.setEchoMode(QLineEdit.Password)
        self.api_key_field.setText(current_api_key)
        self.api_key_field.setPlaceholderText("gsk_...")
        layout.addRow(tr('dlg_settings_groq_label'), self.api_key_field)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_api_key(self) -> str:
        return self.api_key_field.text()


class LicenseDialog(QDialog):
    """License management dialog."""

    def __init__(self, parent, license_manager: LicenseManager):
        super().__init__(parent)
        self.license_manager = license_manager
        self.setWindowTitle(tr('dlg_license_title'))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Status
        status = license_manager.get_status()
        status_label = QLabel(tr('dlg_license_status').format(status=status.value))
        layout.addWidget(status_label)

        # Email
        email = license_manager.get_email()
        if email:
            email_label = QLabel(tr('dlg_license_email').format(email=email))
            layout.addWidget(email_label)

        # Trial days
        if status == LicenseStatus.TRIAL:
            days = license_manager.get_trial_days_left()
            days_label = QLabel(tr('dlg_license_trial_days').format(days=days))
            layout.addWidget(days_label)

        # License key input
        layout.addWidget(QLabel(tr('dlg_license_key_label')))
        self.key_field = QLineEdit()
        self.key_field.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        layout.addWidget(self.key_field)

        # Activate button
        activate_btn = QPushButton(tr('dlg_license_activate'))
        activate_btn.clicked.connect(self._activate)
        layout.addWidget(activate_btn)

        # Buy button
        buy_btn = QPushButton(tr('dlg_license_buy'))
        buy_btn.clicked.connect(self._buy)
        layout.addWidget(buy_btn)

        # Close button
        close_btn = QPushButton(tr('dlg_close'))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _activate(self):
        key = self.key_field.text().strip()
        if key:
            success, message = self.license_manager.activate_license(key)
            if success:
                QMessageBox.information(self, tr('dlg_license_success_title'), message)
                self.accept()
            else:
                QMessageBox.warning(self, tr('dlg_error_title'), message)

    def _buy(self):
        import webbrowser
        webbrowser.open(self.license_manager.get_purchase_url())
