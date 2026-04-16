"""
Claude Voice Assistant - Main Window
PyQt5-based GUI for the application.
"""
import sys
import json
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
    QTabWidget, QTabBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QObject, QEvent, QPoint
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QKeySequence, QPalette, QColor, QTextCharFormat

# QTermWidget for real terminal emulation
try:
    from QTermWidget import QTermWidget
    QTERMWIDGET_AVAILABLE = True
except ImportError:
    QTERMWIDGET_AVAILABLE = False
    print("Warning: QTermWidget not available, using fallback QTextEdit")


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
    ASSETS_DIR
)
from core.claude_bridge import ClaudeBridgeAsync
from core.tts_engine import TTSEngine, TTSState
from core.stt_engine import STTEngine, STTState
from core.license_manager import LicenseManager, LicenseStatus
from core.text_cleaner import TextCleanerForTTS, extract_last_claude_response, fix_polish_encoding
from gui.agent_tab import AgentTab
from gui.dialogs import MemoryProjectsDialog, AgentConfigDialog, AgentsManagerDialog

# Domyślne kolory skórki (motyw Ubuntu) - interfejs + terminal
DEFAULT_SKIN_COLORS = {
    # === Kolory interfejsu ===
    'main_window_bg': '#300A24',        # Tło głównego okna
    'menu_bar_bg': '#300A24',           # Tło paska menu
    'status_bar_bg': '#300A24',         # Tło paska statusu
    'bottom_panel_bg': '#131314',       # Tło panelu z przyciskami
    'border_color': '#4a1a3a',          # Kolor obramowań
    'hover_color': '#6a2a5a',           # Kolor przy najechaniu
    'splitter_color': '#4a1a3a',        # Kolor rozdzielacza
    'text_color': '#ffffff',            # Kolor tekstu
    'button_bg': '#4a1a3a',             # Tło przycisków
    'button_hover': '#6a2a5a',          # Przycisk przy najechaniu
    'input_bg': '#300A24',              # Tło pola tekstowego
    'inactive_panel_bg': '#3a3a3c',     # Tło panelu gdy okno nieaktywne
    # === Kolory ikon przycisków ===
    'icon_dictate_color': '#22c55e',    # Kolor ikony mikrofonu (zielony)
    'icon_read_color': '#06b6d4',       # Kolor ikony głośnika (turkusowy)
    'icon_pause_color': '#a855f7',      # Kolor ikony pauzy (fioletowy)
    'icon_stop_color': '#ef4444',       # Kolor ikony stop (czerwony)
    'icon_copy_color': '#f59e0b',       # Kolor ikony kopiuj (pomarańczowy)
    'icon_clear_input_color': '#ef4444',  # Kolor ikony wyczyść (czerwony)
    'icon_add_media_color': '#3b82f6',  # Kolor ikony dodaj media (niebieski)
    'icon_send_color': '#22c55e',       # Kolor ikony wyślij (zielony)
    'icon_quick_actions_color': '#facc15',  # Kolor ikony szybkich akcji (żółty)
    # === Kolory terminala ===
    'terminal_bg': '#300A24',           # Tło terminala
    'terminal_fg': '#EEEEEC',           # Tekst terminala
    'terminal_color_0': '#2E3436',      # Czarny
    'terminal_color_1': '#CC0000',      # Czerwony
    'terminal_color_2': '#4E9A06',      # Zielony
    'terminal_color_3': '#C4A000',      # Żółty
    'terminal_color_4': '#3465A4',      # Niebieski
    'terminal_color_5': '#75507B',      # Magenta
    'terminal_color_6': '#06989A',      # Cyan
    'terminal_color_7': '#D3D7CF',      # Biały
    'terminal_color_0_bright': '#555753',  # Jasny czarny
    'terminal_color_1_bright': '#EF2929',  # Jasny czerwony
    'terminal_color_2_bright': '#8AE234',  # Jasny zielony
    'terminal_color_3_bright': '#FCE94F',  # Jasny żółty
    'terminal_color_4_bright': '#729FCF',  # Jasny niebieski
    'terminal_color_5_bright': '#AD7FA8',  # Jasna magenta
    'terminal_color_6_bright': '#34E2E2',  # Jasny cyan
    'terminal_color_7_bright': '#EEEEEC',  # Jasny biały
}

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


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Thread-safe signal bridge
        self.signals = SignalBridge()

        # Initialize managers
        self.claude = ClaudeBridgeAsync(CLAUDE_COMMAND)
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self.license_manager = LicenseManager()

        # Settings
        self.current_language = "pl-PL"
        self.auto_read_responses = False
        self.quick_actions = self._load_quick_actions()
        self.attached_files = []  # List of attached file paths
        self.skin_colors = DEFAULT_SKIN_COLORS.copy()  # Custom skin colors (interfejs + terminal)
        self.skin_icons = {k: v.copy() for k, v in DEFAULT_SKIN_ICONS.items()}  # Custom icons
        self.claude_command = "/usr/bin/claude"  # Command to run Claude Code
        self.auto_run_claude = True  # Auto-run Claude command on startup

        # Agents and memory projects
        self.agents = self._load_agents()
        self.memory_projects = self._load_memory_projects()
        self.agent_tabs = {}  # Dict of agent_id -> AgentTab

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

        # NOTE: Claude jest teraz uruchamiany w _create_agent_tab() dla każdej zakładki
        # Stare globalne wywołanie usunięte, bo powodowało podwójne uruchomienie

    def _setup_ui(self):
        """Setup user interface."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)  # Domyślny rozmiar startowy

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # Tab widget for agents
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_agent_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Style for tabs
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: #2d0a1e;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #4a1a3a;
            }
            QTabBar::tab:hover {
                background-color: #6a2a5a;
            }
            QTabBar::close-button {
                image: none;
                subcontrol-position: right;
            }
            QTabBar::close-button:hover {
                background-color: #ef4444;
                border-radius: 2px;
            }
        """)

        # Add "+" button to create new tabs
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedSize(30, 26)
        self.add_tab_btn.setToolTip("Dodaj nowego agenta")
        self.add_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a1a3a;
                color: #22c55e;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6a2a5a;
            }
        """)
        self.add_tab_btn.clicked.connect(self._add_new_agent)
        self.tab_widget.setCornerWidget(self.add_tab_btn, Qt.TopRightCorner)

        # Create tabs for auto-start agents
        self._create_agent_tabs()

        main_layout.addWidget(self.tab_widget)

        # Keep references for compatibility with existing code
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
        self._speaker_icons = ["🔈", "🔉", "🔊"]

        self._pause_blink_timer = QTimer()
        self._pause_blink_timer.timeout.connect(self._animate_pause_blink)
        self._pause_blink_state = True

        # Update references to current tab
        self._update_current_tab_references()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status("Gotowy")

        # Context usage counter (permanent widget on the right side of status bar)
        self._total_context_tokens = 0  # Track estimated tokens
        self._max_context_tokens = 13000000  # Session token pool: 13M tokens
        self._chars_per_token = 3.5  # Average for Polish text (English ~4)
        self._context_label = QLabel("0")
        self._context_label.setToolTip(
            "Licznik tokenów sesji.\n"
            "Liczy od startu aplikacji do zamknięcia.\n"
            "Po restarcie zobaczysz pop-up z poprzednią sesją."
        )
        self._context_label.setStyleSheet("""
            QLabel {
                color: #4ade80;
                font-size: 11px;
                padding: 0 10px;
                font-weight: bold;
            }
        """)
        self.status_bar.addPermanentWidget(self._context_label)

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
            with open(AGENTS_FILE, 'w') as f:
                json.dump(self.agents, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving agents: {e}")

    def _load_memory_projects(self) -> list:
        """Load memory projects from file."""
        if MEMORY_PROJECTS_FILE.exists():
            try:
                with open(MEMORY_PROJECTS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return DEFAULT_MEMORY_PROJECTS.copy()

    def _create_agent_tabs(self):
        """Create tabs for all auto-start agents."""
        for agent in self.agents:
            if agent.get('auto_start', True):
                self._create_agent_tab(agent)

        # If no tabs created, create default one
        if self.tab_widget.count() == 0:
            default_agent = DEFAULT_AGENTS[0].copy()
            self.agents = [default_agent]
            self._create_agent_tab(default_agent)

    def _create_agent_tab(self, agent_config: dict) -> AgentTab:
        """Create a single agent tab."""
        agent_tab = AgentTab(agent_config, self)

        # Set shared state
        agent_tab.set_shared_state(
            self.skin_colors, self.skin_icons,
            self.auto_read_responses, self.current_language
        )

        # Connect signals
        agent_tab.status_changed.connect(self._update_status)
        agent_tab.request_tts.connect(self._handle_tts_request)
        agent_tab.request_tts_stop.connect(self._stop_all)
        agent_tab.request_dictation.connect(self._handle_dictation_request)
        agent_tab.message_sent.connect(self._on_message_sent)

        # Add tab
        agent_id = agent_config.get('id', 'unknown')
        agent_name = agent_config.get('name', 'Agent')
        self.agent_tabs[agent_id] = agent_tab

        index = self.tab_widget.addTab(agent_tab, f"🤖 {agent_name}")
        self.tab_widget.setCurrentIndex(index)

        # Apply styles
        agent_tab.apply_styles(self.skin_colors, self.skin_icons)

        # KOLEJNOŚĆ: najpierw uruchom Claude Code, potem wyślij pliki pamięci
        # Używamy SEKWENCYJNEGO wywołania - pliki pamięci są wysyłane
        # dopiero PO wysłaniu komendy claude (nie równoległe timery)
        def uruchom_claude_potem_pliki():
            # 1. Wyślij komendę claude
            if agent_config.get('auto_start', True) and self.claude_command:
                self._run_claude_in_tab(agent_tab)

            # 2. Po 8 sekundach wyślij pliki pamięci (daje Claude Code czas na start)
            if agent_config.get('send_memory_on_start', True):
                QTimer.singleShot(8000, agent_tab.send_memory_files)

        # Uruchom wszystko po 500ms (gdy terminal będzie gotowy)
        QTimer.singleShot(500, uruchom_claude_potem_pliki)

        return agent_tab

    def _add_new_agent(self):
        """Add new agent via dialog."""
        dialog = AgentConfigDialog(self, memory_projects=self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            agent_config = dialog.get_data()
            self.agents.append(agent_config)
            self._save_agents()
            self._create_agent_tab(agent_config)

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

        # Create tab (don't save to agents list - it's temporary)
        agent_tab = AgentTab(terminal_config, self)

        # Set shared state
        agent_tab.set_shared_state(
            self.skin_colors, self.skin_icons,
            self.auto_read_responses, self.current_language
        )

        # Connect signals
        agent_tab.status_changed.connect(self._update_status)
        agent_tab.request_tts.connect(self._handle_tts_request)
        agent_tab.request_tts_stop.connect(self._stop_all)
        agent_tab.request_dictation.connect(self._handle_dictation_request)
        agent_tab.message_sent.connect(self._on_message_sent)

        # Add tab with terminal icon (🖥️ instead of 🤖)
        self.agent_tabs[terminal_id] = agent_tab
        index = self.tab_widget.addTab(agent_tab, f"🖥️ {terminal_config['name']}")
        self.tab_widget.setCurrentIndex(index)

        # Apply styles
        agent_tab.apply_styles(self.skin_colors, self.skin_icons)

        # Apply terminal color scheme (CustomSkin)
        if agent_tab.terminal:
            self._apply_terminal_colors(self.skin_colors, agent_tab.terminal)

        # Apply button icon styles to new tab
        self._apply_button_icon_styles()

        self._update_status(f"Utworzono nowy terminal: {terminal_config['name']}")

    def _close_agent_tab(self, index: int):
        """Close agent tab."""
        if self.tab_widget.count() <= 1:
            QMessageBox.warning(self, "Nie można zamknąć",
                "Musi pozostać co najmniej jedna zakładka.")
            return

        # Get agent tab and remove from dict
        widget = self.tab_widget.widget(index)
        if isinstance(widget, AgentTab):
            agent_id = widget.agent_id
            if agent_id in self.agent_tabs:
                del self.agent_tabs[agent_id]

        self.tab_widget.removeTab(index)
        widget.deleteLater()

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        self._update_current_tab_references()

    def _update_current_tab_references(self):
        """Update references to current tab's widgets."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, AgentTab):
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
                self._update_status("Czytam...")

    def _handle_dictation_request(self, start: bool):
        """Handle dictation request from agent tab."""
        if start:
            self._toggle_dictation()
        else:
            self._toggle_dictation()

    def _on_message_sent(self, message: str):
        """Handle message sent from agent tab."""
        self._update_context_usage(len(message))

    def _show_memory_projects_dialog(self):
        """Show memory projects management dialog."""
        dialog = MemoryProjectsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.memory_projects = dialog.get_memory_projects()

    def _show_agents_manager_dialog(self):
        """Show agents manager dialog."""
        dialog = AgentsManagerDialog(self, self.agents, self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            self.agents = dialog.get_agents()
            self._save_agents()
            QMessageBox.information(self, "Zapisano",
                "Zmiany zostaną zastosowane po restarcie aplikacji.")

    def _create_menu_bar(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("Plik")

        new_session = QAction("Nowa sesja", self)
        new_session.setShortcut("Ctrl+N")
        new_session.triggered.connect(self._new_session)
        file_menu.addAction(new_session)

        file_menu.addSeparator()

        exit_action = QAction("Wyjście", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edycja")

        manage_actions = QAction("Zarządzaj szybkimi akcjami...", self)
        manage_actions.triggered.connect(self._manage_quick_actions)
        edit_menu.addAction(manage_actions)

        edit_menu.addSeparator()

        # Skin colors option
        skin_colors_action = QAction("🎨 Zmień kolory skórki...", self)
        skin_colors_action.triggered.connect(self._show_skin_settings)
        edit_menu.addAction(skin_colors_action)

        # Agents menu
        agents_menu = menubar.addMenu("Zakładki")

        new_agent_action = QAction("➕ Nowy agent...", self)
        new_agent_action.setShortcut("Ctrl+T")
        new_agent_action.triggered.connect(self._add_new_agent)
        agents_menu.addAction(new_agent_action)

        new_terminal_action = QAction("🖥️ Nowy terminal", self)
        new_terminal_action.setShortcut("Ctrl+Shift+T")
        new_terminal_action.triggered.connect(self._add_new_terminal)
        agents_menu.addAction(new_terminal_action)

        agents_menu.addSeparator()

        manage_agents_action = QAction("Zarządzaj agentami...", self)
        manage_agents_action.triggered.connect(self._show_agents_manager_dialog)
        agents_menu.addAction(manage_agents_action)

        memory_projects_action = QAction("📁 Pliki pamięci projektów...", self)
        memory_projects_action.triggered.connect(self._show_memory_projects_dialog)
        agents_menu.addAction(memory_projects_action)

        # Language menu
        self.language_menu = menubar.addMenu("Język")
        self.language_actions = {}

        for code, (native, english, voice) in SUPPORTED_LANGUAGES.items():
            action = QAction(f"{native} ({english})", self)
            action.setCheckable(True)
            action.setChecked(code == self.current_language)
            action.triggered.connect(lambda checked, c=code: self._set_language(c))
            self.language_menu.addAction(action)
            self.language_actions[code] = action

        # Settings menu
        settings_menu = menubar.addMenu("Ustawienia")

        groq_api_action = QAction("Klucz API Groq...", self)
        groq_api_action.triggered.connect(self._show_groq_api_dialog)
        settings_menu.addAction(groq_api_action)

        anthropic_api_action = QAction("Klucz API Anthropic...", self)
        anthropic_api_action.triggered.connect(self._show_anthropic_api_dialog)
        settings_menu.addAction(anthropic_api_action)

        settings_menu.addSeparator()

        claude_command_action = QAction("Komenda Claude Code...", self)
        claude_command_action.triggered.connect(self._show_claude_command_dialog)
        settings_menu.addAction(claude_command_action)

        # Help menu
        help_menu = menubar.addMenu("Pomoc")

        about_action = QAction("O programie", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        license_action = QAction("Licencja...", self)
        license_action.triggered.connect(self._show_license_dialog)
        help_menu.addAction(license_action)

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

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Ctrl+Enter to send
        # Ctrl+D to dictate
        # Ctrl+R to read
        # Escape to stop
        pass

    def _apply_dark_theme(self):
        """Apply dark theme using custom skin colors and icons."""
        # Use the apply_skin_colors method with current skin colors
        self.apply_skin_colors(self.skin_colors)
        # Apply custom icons to buttons
        self._apply_skin_icons()

    def _load_settings(self):
        """Load settings from file."""
        self.anthropic_api_key = ""  # Initialize

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    settings = json.load(f)
                    self.current_language = settings.get('language', 'pl-PL')
                    self.auto_read_responses = settings.get('auto_read', False)

                    # Load custom skin colors including terminal colors (merge with defaults)
                    saved_skin = settings.get('skin_colors', {})
                    for key in DEFAULT_SKIN_COLORS:
                        if key in saved_skin:
                            self.skin_colors[key] = saved_skin[key]

                    # Load custom skin icons (merge with defaults)
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

                    # Load Claude command settings
                    self.claude_command = settings.get('claude_command', '/usr/bin/claude')
                    self.auto_run_claude = settings.get('auto_run_claude', True)

                    # Load last session tokens (popup removed)
                    last_tokens = settings.get('last_session_tokens', 0)

            except Exception as e:
                print(f"Error loading settings: {e}")

    def _save_settings(self):
        """Save settings to file."""
        settings = {
            'language': self.current_language,
            'auto_read': self.auto_read_responses,
            'groq_api_key': self.stt.api_key,
            'anthropic_api_key': getattr(self, 'anthropic_api_key', ''),
            'skin_colors': self.skin_colors,  # Zawiera kolory interfejsu + terminala
            'skin_icons': self.skin_icons,    # Zawiera ikony przycisków
            'last_session_tokens': self._total_context_tokens,
            'claude_command': self.claude_command,
            'auto_run_claude': self.auto_run_claude,
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

                add_action = QAction("➕ Dodaj własną...", self)
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
        self._update_status("Uruchamianie Claude Code...")
        self._append_system_message("Uruchamianie Claude Code...")

        if self.claude.start():
            self._update_status("Claude Code uruchomiony")
            self._append_system_message("Claude Code gotowy. Możesz pisać lub dyktować polecenia.")
        else:
            self._update_status("Błąd uruchamiania Claude Code")
            self._append_system_message("Błąd: Nie można uruchomić Claude Code. Upewnij się, że jest zainstalowany.")

    def _auto_run_claude_command(self):
        """Auto-run Claude command in all terminals with auto_start enabled.

        NOTE: Ta metoda jest używana tylko przy starcie aplikacji.
        Dla nowych zakładek tworzonych później używamy _run_claude_in_tab().
        """
        if not self.claude_command:
            return

        self._update_status(f"Uruchamianie: {self.claude_command}")

        # Send command to all auto-start agent terminals
        for agent_id, tab in self.agent_tabs.items():
            if tab.terminal and tab.auto_start:
                # Send the command followed by Enter
                tab.terminal.sendText(self.claude_command + "\r")
                self._update_status("Claude Code uruchomiony")

    def _run_claude_in_tab(self, agent_tab):
        """Run Claude command in a specific agent tab.

        Używane przy tworzeniu nowych zakładek (po dialogu dodawania agenta).
        """
        if not self.claude_command:
            return

        if agent_tab.terminal and agent_tab.auto_start:
            agent_tab.terminal.sendText(self.claude_command + "\r")
            self._update_status(f"Claude Code uruchomiony w: {agent_tab.agent_name}")

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
        """Get translated text for current language."""
        # Try current language
        if self.current_language in UI_TRANSLATIONS:
            if key in UI_TRANSLATIONS[self.current_language]:
                return UI_TRANSLATIONS[self.current_language][key]
        # Fallback to English
        if "en-US" in UI_TRANSLATIONS and key in UI_TRANSLATIONS["en-US"]:
            return UI_TRANSLATIONS["en-US"][key]
        # Fallback to Polish
        if "pl-PL" in UI_TRANSLATIONS and key in UI_TRANSLATIONS["pl-PL"]:
            return UI_TRANSLATIONS["pl-PL"][key]
        return key

    def _update_ui_language(self):
        """Update all UI elements to current language."""
        # Update tooltips in current tab
        tab = self._get_current_agent_tab()
        if tab:
            # Buttons are icon-only, update only tooltips
            tab.dictate_btn.setToolTip(self._get_text('dictate'))
            tab.read_btn.setToolTip(self._get_text('read'))
            tab.copy_btn.setToolTip(self._get_text('copy'))
            tab.clear_input_btn.setToolTip(self._get_text('clear_input'))
            tab.add_media_btn.setToolTip(self._get_text('add_media'))
            tab.pause_btn.setToolTip(self._get_text('pause'))
            tab.stop_btn.setToolTip(self._get_text('stop'))
            tab.send_btn.setToolTip(self._get_text('send'))
            tab.auto_read_checkbox.setText(self._get_text('auto_read'))

            # Update input placeholder
            placeholder = "Type a command or use dictation..." if self.current_language.startswith("en") else "Wpisz polecenie lub użyj dyktowania..."
            tab.input_field.setPlaceholderText(placeholder)

        # Update window title
        self.setWindowTitle(f"{self._get_text('app_title')} v{APP_VERSION}")

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
            QApplication.processEvents()

    def _on_claude_response(self, text: str):
        """Handle complete response from Claude."""
        if self.auto_read_responses and text.strip():
            self.tts.speak(text)

    def _on_claude_error(self, error: str):
        """Handle Claude error."""
        self._append_system_message(f"Błąd: {error}")
        self._update_status(f"Błąd: {error}")

    # ==================== Terminal Handlers ====================

    def _on_terminal_output(self, data):
        """Handle data received from terminal (for TTS)."""
        if not self.terminal:
            return

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
            # Add to buffer with newline separator
            self._terminal_output_buffer += clean_text + "\n"

            # Update context usage counter
            self._update_context_usage(len(clean_text))

            # LIMIT buffer size to last 5000 characters to prevent memory issues
            if len(self._terminal_output_buffer) > 5000:
                self._terminal_output_buffer = self._terminal_output_buffer[-5000:]

            # Reset timer - wait 2 seconds after last output before auto-reading
            if self.auto_read_responses:
                self._tts_timer.stop()
                self._tts_timer.start(2000)

            # NOTE: Removed auto-scroll on terminal output - user controls scroll manually
            # Previously this caused annoying jumps when trying to read history

    def _read_terminal_buffer(self):
        """Read accumulated terminal output via TTS (auto-read mode)."""
        if not self._terminal_output_buffer.strip():
            return

        # Use the same logic as manual read - extract Claude response only
        last_response = extract_last_claude_response(self._terminal_output_buffer)

        if last_response:
            # Fix Polish encoding first
            last_response = fix_polish_encoding(last_response)
            # Clean for TTS
            # use_dictionary=False because terminal encoding may corrupt Polish chars
            text_cleaner = TextCleanerForTTS(self.current_language)
            cleaned_text = text_cleaner.clean(last_response, use_dictionary=False)

            if cleaned_text and len(cleaned_text) > 20:
                self.tts.speak(cleaned_text)
                self._update_status("Auto-czytam odpowiedź...")

        # Always clear buffer after auto-read attempt
        self._terminal_output_buffer = ""

    def _on_terminal_finished(self):
        """Handle terminal session finished."""
        self._update_status("Terminal zakończony")
        # Optionally restart
        if self.terminal:
            self.terminal.startShellProgram()
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
            tab.pause_btn.setText(self._get_icon('pause', 'normal'))
            # Start speaker animation
            self._speaker_anim_timer.start(300)
            # Stop pause blink if running
            self._pause_blink_timer.stop()
            self._update_status("Czytam...")
        elif state == TTSState.PAUSED:
            # Keep buttons visible during pause
            tab.pause_btn.setVisible(True)
            tab.stop_btn.setVisible(True)
            tab.pause_btn.setText(self._get_icon('pause', 'active'))
            # Stop speaker animation
            self._speaker_anim_timer.stop()
            tab.read_btn.setText(self._get_icon('read', 'normal'))
            # Start pause blink animation
            self._pause_blink_timer.start(500)
            self._update_status("Wstrzymano")
        elif state == TTSState.GENERATING:
            # Show stop button during generation (to allow cancel)
            tab.stop_btn.setVisible(True)
            self._update_status("Generowanie mowy...")
        else:
            # Hide pause and stop buttons when idle
            tab.pause_btn.setVisible(False)
            tab.stop_btn.setVisible(False)
            tab.pause_btn.setEnabled(False)
            tab.pause_btn.setText(self._get_icon('pause', 'normal'))
            # Stop all animations
            self._speaker_anim_timer.stop()
            self._pause_blink_timer.stop()
            tab.read_btn.setText(self._get_icon('read', 'normal'))
            self._update_status("Gotowy")

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
        tab.read_btn.setText(self._get_icon('read', 'normal'))
        self._update_status("Gotowy")

    def _on_stt_state_changed(self, state: STTState):
        """Handle STT state change."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        if state == STTState.RECORDING:
            tab.dictate_btn.setChecked(True)
            # Start microphone pulse animation
            self._mic_pulse_timer.start(400)
            self._update_status("Nagrywanie... (kliknij ponownie aby zakończyć)")
        elif state == STTState.PROCESSING:
            tab.dictate_btn.setText(self._get_icon('dictate', 'processing'))
            # Stop pulse animation
            self._mic_pulse_timer.stop()
            self._update_status("Przetwarzanie mowy...")
        else:
            tab.dictate_btn.setText(self._get_icon('dictate', 'normal'))
            tab.dictate_btn.setChecked(False)
            # Stop pulse animation and reset style
            self._mic_pulse_timer.stop()
            self._reset_mic_style()
            self._update_status("Gotowy")

    # ==================== Animation Methods ====================

    def _animate_mic_pulse(self):
        """Animate microphone button pulsing when recording."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        self._mic_pulse_state = not self._mic_pulse_state
        mic_icon = self._get_icon('dictate', 'active')
        border_color = self.skin_colors.get('border_color', '#4a1a3a')
        if self._mic_pulse_state:
            # Bright recording state - red color, larger
            tab.dictate_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: #ff0000;
                    border: 2px solid #ff0000;
                    border-radius: 12px;
                    font-size: 24px;
                }}
            """)
            tab.dictate_btn.setText(mic_icon)
        else:
            # Darker recording state
            tab.dictate_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: #b91c1c;
                    border: 2px solid #b91c1c;
                    border-radius: 12px;
                    font-size: 22px;
                }}
            """)
            tab.dictate_btn.setText(mic_icon)

    def _reset_mic_style(self):
        """Reset microphone button to default style."""
        tab = self._get_current_agent_tab()
        if tab:
            self._apply_button_icon_style(tab.dictate_btn, 'icon_dictate_color')

    def _animate_speaker(self):
        """Animate speaker icon showing sound waves."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        self._speaker_anim_state = (self._speaker_anim_state + 1) % 3
        tab.read_btn.setText(self._speaker_icons[self._speaker_anim_state])

    def _animate_pause_blink(self):
        """Animate pause button blinking - icon only, button stays in place."""
        tab = self._get_current_agent_tab()
        if not tab:
            return

        self._pause_blink_state = not self._pause_blink_state
        pause_active = self._get_icon('pause', 'active')
        if self._pause_blink_state:
            tab.pause_btn.setText(pause_active)  # Play icon visible
        else:
            # Slightly dimmed version (use same icon or fallback)
            tab.pause_btn.setText(pause_active)

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
        self._update_status("Błąd rozpoznawania mowy")

    # ==================== Actions ====================

    def _send_message(self):
        """Send message to terminal or Claude."""
        text = self.input_field.text().strip()

        # Build full message with attachments
        full_message = self._build_message_with_attachments(text)

        if self.terminal and QTERMWIDGET_AVAILABLE:
            if full_message:
                # Send text + Enter (with delay for Claude Code)
                self.terminal.sendText(full_message)
                QTimer.singleShot(50, lambda: self.terminal.sendText("\r"))
                self.input_field.clear()
                self._clear_attachments()
                # Update context usage with user input
                self._update_context_usage(len(full_message))
            else:
                # Empty field - just send Enter (accept Claude Code proposal)
                self.terminal.sendText("\r")

            # Schedule scroll to bottom via centralized manager
            # The manager handles debouncing and proper timing
            if self._scroll_manager:
                self._scroll_manager.schedule_scroll()

            # NOTE: Removed 30-second auto-scroll timer - was causing unwanted jumps
            # User now has full control over scrolling after sending a message

            self._update_status("Wysłano do terminala...")
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
        self._update_status("Wysłano...")

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
                self._show_api_key_dialog()
                return
            self.stt.start_recording()

    def _read_last_response(self):
        """Read the last Claude Code response aloud (cleaned for TTS)."""
        # Initialize text cleaner with current language
        text_cleaner = TextCleanerForTTS(self.current_language)

        if self.terminal and QTERMWIDGET_AVAILABLE:
            # For terminal mode - read from buffer or selected text
            selected = self.terminal.selectedText()

            if selected:
                # Fix Polish encoding first
                selected = fix_polish_encoding(selected)
                # User selected text - clean and read it
                # use_dictionary=False because terminal encoding may corrupt Polish chars
                cleaned_text = text_cleaner.clean(selected, use_dictionary=False)
                if cleaned_text:
                    self.tts.speak(cleaned_text)
                    self._update_status("Czytam zaznaczony tekst...")
                else:
                    self._update_status("Zaznaczony tekst nie zawiera treści do odczytania")
                return

            # DEBUG: Save buffer to file for analysis
            debug_file = Path.home() / ".claude-voice-assistant" / "debug_buffer.txt"
            try:
                with open(debug_file, 'w') as f:
                    f.write("=== RAW BUFFER ===\n")
                    f.write(self._terminal_output_buffer)
                    f.write("\n\n=== BUFFER LENGTH ===\n")
                    f.write(str(len(self._terminal_output_buffer)))
            except:
                pass

            # No selection - extract last Claude response from buffer
            if self._terminal_output_buffer.strip():
                # Extract only the last response
                last_response = extract_last_claude_response(self._terminal_output_buffer)

                # DEBUG: Save extracted response
                try:
                    with open(debug_file, 'a') as f:
                        f.write("\n\n=== EXTRACTED RESPONSE ===\n")
                        f.write(last_response if last_response else "(empty)")
                except:
                    pass

                if last_response:
                    # Fix Polish encoding first (UTF-8/Latin-1 issues from terminal)
                    last_response = fix_polish_encoding(last_response)

                    # Clean the response for TTS
                    # use_dictionary=False because terminal encoding may corrupt Polish chars
                    cleaned_text = text_cleaner.clean(last_response, use_dictionary=False)

                    # DEBUG: Save cleaned text
                    try:
                        with open(debug_file, 'a') as f:
                            f.write("\n\n=== CLEANED TEXT ===\n")
                            f.write(cleaned_text if cleaned_text else "(empty)")
                    except:
                        pass

                    if cleaned_text:
                        # Stop auto-read timer to prevent double reading
                        self._tts_timer.stop()
                        self.tts.speak(cleaned_text)
                        self._update_status("Czytam ostatnią odpowiedź...")
                        # Clear buffer after reading
                        self._terminal_output_buffer = ""
                    else:
                        self._update_status("Odpowiedź nie zawiera treści do odczytania")
                else:
                    self._update_status("Nie znaleziono odpowiedzi do odczytania")
                    # Clear buffer anyway to prevent accumulation
                    self._terminal_output_buffer = ""
            else:
                self._update_status("Brak tekstu do odczytania")
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
                self._update_status("Odpowiedź nie zawiera treści do odczytania")
        else:
            self._update_status("Nie znaleziono odpowiedzi do odczytania")

    def _copy_selection(self):
        """Copy selected text from terminal to system clipboard."""
        if self.terminal and QTERMWIDGET_AVAILABLE:
            selected = self.terminal.selectedText()

            if selected and selected.strip():
                # Copy to system clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(selected)
                self._update_status(f"Skopiowano do schowka ({len(selected)} znaków)")
                # Flash green effect
                self._flash_copy_success()
            else:
                self._update_status("Najpierw zaznacz tekst w terminalu")
        else:
            # Fallback for QTextEdit mode
            if self.conversation_area:
                cursor = self.conversation_area.textCursor()
                selected = cursor.selectedText()

                if selected and selected.strip():
                    clipboard = QApplication.clipboard()
                    clipboard.setText(selected)
                    self._update_status(f"Skopiowano do schowka ({len(selected)} znaków)")
                    # Flash green effect
                    self._flash_copy_success()
                else:
                    self._update_status("Najpierw zaznacz tekst")

    def _clear_input_field(self):
        """Clear the input text field."""
        self.input_field.clear()
        self.input_field.setFocus()

    def _add_media(self):
        """Open file dialog to add media files."""
        from PyQt5.QtWidgets import QFileDialog

        file_filter = (
            "Wszystkie obsługiwane (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.pdf *.doc *.docx *.txt *.csv *.xlsx *.xls *.json *.xml *.zip *.tar *.gz);;"
            "Obrazy (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;"
            "Dokumenty (*.pdf *.doc *.docx *.txt *.csv *.xlsx *.xls);;"
            "Dane (*.json *.xml *.csv);;"
            "Archiwa (*.zip *.tar *.gz);;"
            "Wszystkie pliki (*.*)"
        )

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Dodaj media",
            "",
            file_filter
        )

        if files:
            for file_path in files:
                if file_path not in self.attached_files:
                    self.attached_files.append(file_path)
            self._update_attachments_display()
            self._update_status(f"Dodano {len(files)} plik(ów)")

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

        # Change to green with checkmark
        border_color = self.skin_colors.get('border_color', '#4a1a3a')
        tab.copy_btn.setText(self._get_icon('copy', 'active'))
        tab.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #22c55e;
                border: 2px solid #22c55e;
                border-radius: 12px;
                font-size: 22px;
            }}
        """)
        # Reset after 500ms
        QTimer.singleShot(500, self._reset_copy_style)

    def _reset_copy_style(self):
        """Reset copy button to default style."""
        tab = self._get_current_agent_tab()
        if tab:
            tab.copy_btn.setText(self._get_icon('copy', 'normal'))
            self._apply_button_icon_style(tab.copy_btn, 'icon_copy_color')

    def _toggle_pause(self):
        """Toggle TTS pause/resume."""
        self.tts.toggle_pause()

    def _stop_all(self):
        """Stop all operations."""
        self.tts.stop()
        self.stt.cancel_recording()

        if self.terminal and QTERMWIDGET_AVAILABLE:
            # Send Ctrl+C to terminal
            self.terminal.sendText("\x03")  # Ctrl+C
            self._terminal_output_buffer = ""
            self._tts_timer.stop()
        else:
            self.claude.send_interrupt()

        self._update_status("Zatrzymano")

    def _insert_quick_action(self, command: str):
        """Insert quick action command."""
        self.input_field.setText(command)
        self.input_field.setFocus()

    def _add_quick_action(self):
        """Add new quick action via dialog with both fields."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Dodaj szybką akcję")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # Form with two fields
        form_layout = QFormLayout()

        label_input = QLineEdit()
        label_input.setPlaceholderText("np. Sprawdź błędy")
        label_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form_layout.addRow("Nazwa akcji:", label_input)

        command_input = QLineEdit()
        command_input.setPlaceholderText("np. Sprawdź czy w kodzie są błędy i je napraw")
        command_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form_layout.addRow("Komenda:", command_input)

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
                QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę akcji.")
                return
            if not command:
                QMessageBox.warning(self, "Brak komendy", "Podaj komendę.")
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
            self._update_status("Szybkie akcje zostały zapisane")

    def _new_session(self):
        """Start new terminal/Claude session."""
        reply = QMessageBox.question(self, "Nowa sesja",
            "Czy na pewno chcesz rozpocząć nową sesję?",
            QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            if self.terminal and QTERMWIDGET_AVAILABLE:
                # Clear terminal and restart shell
                self.terminal.sendText("clear\n")
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
        QMessageBox.about(self, f"O programie {APP_NAME}",
            f"<h2>{APP_NAME}</h2>"
            f"<p>Wersja {APP_VERSION}</p>"
            f"<p>Asystent głosowy dla Claude Code.</p>"
            f"<p>© 2024 Fulfillment Polska</p>")

    def _show_trial_dialog(self):
        """Show trial registration dialog."""
        email, ok = QInputDialog.getText(self, "Rozpocznij trial",
            "Podaj adres email aby rozpocząć 30-dniowy trial:")

        if ok and email:
            if self.license_manager.start_trial(email):
                self._check_license()
                QMessageBox.information(self, "Trial aktywowany",
                    f"Twój 30-dniowy trial został aktywowany!\n"
                    f"Email: {email}")
            else:
                QMessageBox.warning(self, "Błąd", "Nie udało się aktywować trial.")

    def _show_license_dialog(self):
        """Show license management dialog."""
        dialog = LicenseDialog(self, self.license_manager)
        dialog.exec_()
        self._check_license()

    def _show_license_expired_dialog(self):
        """Show dialog when license/trial expired."""
        reply = QMessageBox.warning(self, "Licencja wygasła",
            "Twoja licencja lub okres próbny wygasł.\n"
            "Czy chcesz kupić licencję?",
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
            self._update_status("Skórka została zapisana")
        else:
            # User cancelled - restore originals
            self.skin_colors = original_colors
            self.skin_icons = original_icons
            self.apply_skin_colors(original_colors)
            self._apply_skin_icons()

    def _apply_skin_icons(self):
        """Apply skin icons to all buttons in all tabs."""
        icons = self.skin_icons

        # Apply to all agent tabs
        for agent_id, tab in self.agent_tabs.items():
            # Dictate button (mikrofon)
            if hasattr(tab, 'dictate_btn'):
                dictate_icons = icons.get('dictate', {})
                tab.dictate_btn.setText(dictate_icons.get('normal', '🎤'))

            # Read button (głośnik)
            if hasattr(tab, 'read_btn'):
                read_icons = icons.get('read', {})
                tab.read_btn.setText(read_icons.get('normal', '🔊'))

            # Pause button
            if hasattr(tab, 'pause_btn'):
                pause_icons = icons.get('pause', {})
                tab.pause_btn.setText(pause_icons.get('normal', '⏸'))

            # Stop button
            if hasattr(tab, 'stop_btn'):
                stop_icons = icons.get('stop', {})
                tab.stop_btn.setText(stop_icons.get('normal', '⬜'))

            # Copy button
            if hasattr(tab, 'copy_btn'):
                copy_icons = icons.get('copy', {})
                tab.copy_btn.setText(copy_icons.get('normal', '⧉'))

            # Send button
            if hasattr(tab, 'send_btn'):
                send_icons = icons.get('send', {})
                tab.send_btn.setText(send_icons.get('normal', '↵'))

            # Quick actions button
            if hasattr(tab, 'quick_actions_btn'):
                qa_icons = icons.get('quick_actions', {})
                tab.quick_actions_btn.setText(qa_icons.get('normal', '⚡▼'))

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
        icon_color = self.skin_colors.get(color_key, '#ffffff')
        border_color = self.skin_colors.get('border_color', '#4a1a3a')
        hover_color = self.skin_colors.get('hover_color', '#6a2a5a')

        disabled_style = ""
        if with_disabled:
            disabled_style = f"""
            QPushButton:disabled {{
                background-color: transparent;
                color: {border_color};
                border: 1px solid {border_color};
            }}"""

        button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {icon_color};
                border: 1px solid {border_color};
                border-radius: 12px;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:checked {{
                color: #ff0000;
                border: 2px solid #ff0000;
            }}{disabled_style}
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

            # Pause button - uses same style as other buttons but with disabled state
            if hasattr(tab, 'pause_btn'):
                self._apply_button_icon_style(tab.pause_btn, 'icon_pause_color', with_disabled=True)

            # Send button - transparent style like other buttons
            if hasattr(tab, 'send_btn'):
                self._apply_button_icon_style(tab.send_btn, 'icon_send_color', font_size=16)

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

    def _apply_terminal_colors(self, colors: dict = None, terminal=None):
        """Apply terminal colors by creating a custom color scheme.

        This generates a .colorscheme file and loads it into QTermWidget.
        If terminal is None, applies to all terminals in all tabs.
        """
        if not QTERMWIDGET_AVAILABLE:
            return

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
        custom_scheme_dir = Path.home() / '.config' / 'claude-voice-assistant' / 'color-schemes'
        custom_scheme_dir.mkdir(parents=True, exist_ok=True)

        scheme_file = custom_scheme_dir / 'CustomSkin.colorscheme'
        with open(scheme_file, 'w') as f:
            f.write(scheme_content)

        # Apply scheme to specific terminal or all terminals in all tabs
        scheme_name = 'CustomSkin'

        if terminal:
            terminal.addCustomColorSchemeDir(str(custom_scheme_dir))
            terminal.setColorScheme(scheme_name)
        else:
            # Apply to all terminals in all agent tabs
            for agent_id, tab in self.agent_tabs.items():
                if tab.terminal:
                    tab.terminal.addCustomColorSchemeDir(str(custom_scheme_dir))
                    tab.terminal.setColorScheme(scheme_name)
                    # Force terminal to update/refresh
                    tab.terminal.update()

    def apply_skin_colors(self, colors: dict = None):
        """Apply skin colors to all UI elements.

        This method updates all styled elements with the new colors.
        Can be called for live preview or permanent application.
        """
        if colors is None:
            colors = self.skin_colors

        # Path to checkmark icon for checkboxes
        checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")

        # Main window
        self.setStyleSheet(f"""
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
        """)

        # Apply styles to all agent tabs
        for agent_tab in self.agent_tabs.values():
            agent_tab.apply_styles(colors, self.skin_icons)

        # Tab widget styling
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: none;
                    background-color: transparent;
                }}
                QTabBar::tab {{
                    background-color: {colors.get('button_bg', '#2d0a1e')};
                    color: {colors.get('text_color', '#ffffff')};
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }}
                QTabBar::tab:selected {{
                    background-color: {colors.get('hover_color', '#4a1a3a')};
                }}
                QTabBar::tab:hover {{
                    background-color: {colors.get('hover_color', '#6a2a5a')};
                }}
            """)

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

        key, ok = QInputDialog.getText(self, "Klucz API Groq",
            f"Podaj klucz API Groq (do rozpoznawania mowy STT):\n\nAktualny: {display_key if display_key else 'brak'}",
            QLineEdit.Normal)

        if ok and key:
            self.stt.set_api_key(key)
            self._save_settings()
            QMessageBox.information(self, "Zapisano",
                "Klucz API Groq został zapisany.")

    def _show_anthropic_api_dialog(self):
        """Show dialog to enter Anthropic API key."""
        current_key = getattr(self, 'anthropic_api_key', "") or ""
        # Show masked key if exists
        display_key = current_key[:8] + "..." if len(current_key) > 8 else current_key

        key, ok = QInputDialog.getText(self, "Klucz API Anthropic",
            f"Podaj klucz API Anthropic (Claude):\n\nAktualny: {display_key if display_key else 'brak'}",
            QLineEdit.Normal)

        if ok and key:
            self.anthropic_api_key = key
            self._save_settings()
            QMessageBox.information(self, "Zapisano",
                "Klucz API Anthropic został zapisany.")

    def _show_claude_command_dialog(self):
        """Show dialog to configure Claude Code command."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Komenda Claude Code")
        dialog.setMinimumWidth(500)

        # Path to checkmark icon
        checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")

        layout = QVBoxLayout(dialog)

        # Description
        desc_label = QLabel(
            "Podaj komendę uruchamiającą Claude Code w terminalu.\n"
            "Ta komenda zostanie automatycznie wpisana po uruchomieniu programu."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Command input
        cmd_layout = QHBoxLayout()
        cmd_label = QLabel("Komenda:")
        cmd_input = QLineEdit(self.claude_command)
        cmd_input.setPlaceholderText("/usr/bin/claude")
        cmd_layout.addWidget(cmd_label)
        cmd_layout.addWidget(cmd_input, stretch=1)
        layout.addLayout(cmd_layout)

        # Auto-run checkbox
        auto_run_checkbox = QCheckBox("Automatycznie uruchom po starcie programu")
        auto_run_checkbox.setChecked(self.auto_run_claude)
        layout.addWidget(auto_run_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(dialog.reject)
        save_btn = QPushButton("Zapisz")
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
            QMessageBox.information(self, "Zapisano",
                f"Komenda Claude Code została zapisana.\n\n"
                f"Komenda: {self.claude_command}\n"
                f"Auto-uruchomienie: {'Tak' if self.auto_run_claude else 'Nie'}")

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

    def _update_status(self, text: str):
        """Update status bar."""
        self.status_bar.showMessage(text)

    def _update_context_usage(self, additional_chars: int = 0):
        """Update context usage estimate in tokens.

        Session token pool: 4M tokens.
        Estimate: 1 token ≈ 3.5 characters for Polish text.
        """
        # Convert chars to tokens
        additional_tokens = int(additional_chars / self._chars_per_token)
        self._total_context_tokens += additional_tokens

        # Calculate percentage
        percentage = min(100, (self._total_context_tokens / self._max_context_tokens) * 100)

        # Format token count with thousands separator
        tokens_formatted = f"{self._total_context_tokens:,}".replace(",", ",")
        max_formatted = f"{self._max_context_tokens:,}".replace(",", ",")

        # Color coding based on usage (3 levels)
        if percentage <= 50:
            color = "#4ade80"  # Green: 0-50%
        elif percentage <= 75:
            color = "#f97316"  # Orange: 50-75%
        else:
            color = "#ef4444"  # Red: >75%

        self._context_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 11px;
                padding: 0 10px;
                font-weight: bold;
            }}
        """)
        self._context_label.setText(f"{tokens_formatted}")

    def _reset_context_usage(self):
        """Reset context counter (e.g., when starting new conversation)."""
        self._total_context_tokens = 0
        self._context_label.setText("0")
        self._context_label.setStyleSheet("""
            QLabel {
                color: #4ade80;
                font-size: 11px;
                padding: 0 10px;
                font-weight: bold;
            }
        """)

    def resizeEvent(self, event):
        """Handle window resize."""
        super().resizeEvent(event)
        # NOTE: Removed auto-scroll on resize - user controls scroll position manually
        # This prevents unwanted jumps on rotated/portrait monitors

    def closeEvent(self, event):
        """Handle window close."""
        # Remove menu position fixer
        if hasattr(self, '_menu_fixer'):
            QApplication.instance().removeEventFilter(self._menu_fixer)

        # Stop scroll manager
        if hasattr(self, '_scroll_manager') and self._scroll_manager:
            self._scroll_manager.stop()

        self.tts.stop()
        self.stt.cancel_recording()

        if self.terminal and QTERMWIDGET_AVAILABLE:
            # Terminal cleanup
            if hasattr(self, '_tts_timer'):
                self._tts_timer.stop()
        else:
            self.claude.stop()

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
        self.setWindowTitle("Zarządzaj szybkimi akcjami")
        self.setMinimumSize(500, 450)
        self.quick_actions = [a.copy() for a in quick_actions]  # Deep copy
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel("Zarządzaj swoimi szybkimi akcjami")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # List of actions
        list_layout = QHBoxLayout()

        # Table-like list with two columns
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Etykieta", "Komenda"])
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

        self.up_btn = QPushButton("▲ W górę")
        self.up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton("▼ W dół")
        self.down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self.down_btn)

        btn_layout.addSpacing(10)

        self.edit_btn = QPushButton("✏️ Edytuj")
        self.edit_btn.clicked.connect(self._edit_action)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Usuń")
        self.delete_btn.clicked.connect(self._delete_action)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout)

        # Add new action section
        add_group = QGroupBox("Dodaj nową akcję")
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
        self.label_input.setPlaceholderText("np. Sprawdź błędy")
        self.label_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        add_layout.addRow("Etykieta:", self.label_input)

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("np. Sprawdź czy w kodzie są błędy i je napraw")
        self.command_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        add_layout.addRow("Komenda:", self.command_input)

        add_btn_layout = QHBoxLayout()
        add_btn_layout.addStretch()
        self.add_btn = QPushButton("➕ Dodaj")
        self.add_btn.clicked.connect(self._add_action)
        self.add_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        add_btn_layout.addWidget(self.add_btn)
        add_layout.addRow("", add_btn_layout)

        layout.addWidget(add_group)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        restore_btn = QPushButton("Przywróć domyślne")
        restore_btn.clicked.connect(self._restore_defaults)
        bottom_layout.addWidget(restore_btn)

        bottom_layout.addStretch()

        close_btn = QPushButton("Zamknij")
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
            QMessageBox.warning(self, "Brak wyboru", "Wybierz akcję do edycji.")
            return

        action = self.quick_actions[row]

        label, ok1 = QInputDialog.getText(
            self, "Edytuj akcję", "Etykieta:",
            text=action['label']
        )
        if ok1 and label:
            command, ok2 = QInputDialog.getText(
                self, "Edytuj akcję", "Komenda:",
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
            QMessageBox.warning(self, "Brak wyboru", "Wybierz akcję do usunięcia.")
            return

        action = self.quick_actions[row]
        reply = QMessageBox.question(
            self, "Potwierdź usunięcie",
            f"Czy na pewno usunąć akcję \"{action['label']}\"?",
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
            QMessageBox.warning(self, "Brak etykiety", "Podaj etykietę dla akcji.")
            self.label_input.setFocus()
            return

        if not command:
            QMessageBox.warning(self, "Brak komendy", "Podaj komendę dla akcji.")
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
            self, "Przywróć domyślne",
            "Czy na pewno przywrócić domyślne akcje?\nWszystkie Twoje akcje zostaną usunięte.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from ..config import DEFAULT_QUICK_ACTIONS
            self.quick_actions = [a.copy() for a in DEFAULT_QUICK_ACTIONS]
            self._populate_table()

    def get_quick_actions(self) -> list:
        """Return the modified quick actions list."""
        return self.quick_actions


class SkinSettingsDialog(QDialog):
    """Dialog do personalizacji kolorów i ikon skórki aplikacji."""

    def __init__(self, parent, current_colors: dict, current_icons: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia skórki - Kolory i ikony")
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
        header = QLabel("Dostosuj kolory i ikony aplikacji")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Import/Export buttons row
        import_export_layout = QHBoxLayout()

        import_btn = QPushButton("📥 Importuj skórkę")
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

        export_btn = QPushButton("📤 Eksportuj skórkę")
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
        help_btn = QPushButton("❓ Pomoc - Ikony")
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
        main_group = QGroupBox("Główne elementy")
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
        borders_group = QGroupBox("Obramowania i efekty")
        borders_group.setStyleSheet(main_group.styleSheet())
        borders_layout = QGridLayout(borders_group)

        border_colors = ['border_color', 'hover_color', 'splitter_color']
        for i, key in enumerate(border_colors):
            self._add_color_row(borders_layout, i, key)

        colors_layout.addWidget(borders_group)

        # Group: Text and buttons
        text_group = QGroupBox("Tekst i przyciski")
        text_group.setStyleSheet(main_group.styleSheet())
        text_layout = QGridLayout(text_group)

        text_colors = ['text_color', 'button_bg', 'button_hover', 'input_bg', 'inactive_panel_bg']
        for i, key in enumerate(text_colors):
            self._add_color_row(text_layout, i, key)

        colors_layout.addWidget(text_group)

        # Group: Terminal background and text
        terminal_bg_group = QGroupBox("Terminal - tło i tekst")
        terminal_bg_group.setStyleSheet(main_group.styleSheet())
        terminal_bg_layout = QGridLayout(terminal_bg_group)

        terminal_bg_colors = ['terminal_bg', 'terminal_fg']
        for i, key in enumerate(terminal_bg_colors):
            self._add_color_row(terminal_bg_layout, i, key)

        colors_layout.addWidget(terminal_bg_group)

        # Group: Icon colors
        icon_colors_group = QGroupBox("Kolory ikon przycisków")
        icon_colors_group.setStyleSheet(main_group.styleSheet())
        icon_colors_layout = QGridLayout(icon_colors_group)

        icon_color_keys = ['icon_dictate_color', 'icon_read_color', 'icon_pause_color',
                           'icon_stop_color', 'icon_copy_color', 'icon_clear_input_color',
                           'icon_add_media_color', 'icon_send_color', 'icon_quick_actions_color']
        for i, key in enumerate(icon_color_keys):
            self._add_color_row(icon_colors_layout, i, key)

        colors_layout.addWidget(icon_colors_group)

        # Group: Button icons
        icons_group = QGroupBox("Ikony przycisków")
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
        reset_btn = QPushButton("Przywróć domyślne (Ubuntu)")
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
        cancel_btn = QPushButton("Anuluj")
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
        apply_btn = QPushButton("Zastosuj")
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
        label = QLabel(SKIN_COLOR_NAMES.get(color_key, color_key))
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
            f"Wybierz kolor: {SKIN_COLOR_NAMES.get(color_key, color_key)}",
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
        label = QLabel(SKIN_ICON_NAMES.get(icon_key, icon_key))
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
        normal_btn.setToolTip("Ikona normalna (kliknij aby zmienić)")
        normal_btn.setCursor(Qt.PointingHandCursor)
        normal_btn.setStyleSheet(self._get_icon_btn_style(normal_color))
        normal_btn.clicked.connect(lambda: self._edit_icon(icon_key, 'normal'))
        layout.addWidget(normal_btn, row, 1)

        # Active icon button with its color
        active_btn = QPushButton(icon_data.get('active', icon_data.get('normal', '?')))
        active_btn.setFixedSize(50, 30)
        active_btn.setToolTip("Ikona aktywna (kliknij aby zmienić)")
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
            processing_btn.setToolTip("Ikona procesowania (kliknij aby zmienić)")
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
        dialog.setWindowTitle(f"Zmień ikonę: {SKIN_ICON_NAMES.get(icon_key, icon_key)}")
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
        label = QLabel(f"Wpisz emoji lub tekst dla stanu '{state}':\n(np. 🎤 lub tekst)")
        layout.addWidget(label)

        # Text input with color preview
        input_layout = QHBoxLayout()

        text_input = QLineEdit(current_text)
        text_input.setFixedHeight(40)

        # Color picker button
        color_btn = QPushButton()
        color_btn.setFixedSize(40, 40)
        color_btn.setCursor(Qt.PointingHandCursor)
        color_btn.setToolTip("Zmień kolor ikony")

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
                "Wybierz kolor ikony",
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
        help_text = """
<h2>🎨 Jak zmienić ikony przycisków</h2>

<h3>📝 Instrukcja:</h3>
<ol>
<li>Kliknij na przycisk z ikoną którą chcesz zmienić</li>
<li>Wpisz nowe emoji lub tekst</li>
<li>Kliknij OK</li>
</ol>

<p><b>Ikona "normalna"</b> - wyświetlana gdy przycisk jest nieaktywny<br>
<b>Ikona "aktywna"</b> - wyświetlana gdy przycisk jest wciśnięty/aktywny</p>

<h3>⌨️ Jak wpisać emoji:</h3>
<ul>
<li><b>Windows:</b> Naciśnij <code>Win + .</code> (kropka)</li>
<li><b>Linux:</b> Naciśnij <code>Ctrl + .</code> lub <code>Ctrl + Shift + E</code></li>
<li><b>macOS:</b> Naciśnij <code>Ctrl + Cmd + Space</code></li>
</ul>

<h3>🌐 Strony z ikonami (skopiuj i wklej):</h3>
<ul>
<li><a href="https://emojipedia.org">emojipedia.org</a> - wszystkie emoji</li>
<li><a href="https://getemoji.com">getemoji.com</a> - emoji do kopiowania</li>
<li><a href="https://symbl.cc/en/">symbl.cc</a> - symbole Unicode</li>
<li><a href="https://unicode-table.com">unicode-table.com</a> - tabela Unicode</li>
<li><a href="https://fontawesome.com/search?o=r&m=free">fontawesome.com</a> - ikony (skopiuj jako Unicode)</li>
</ul>

<h3>💡 Przykładowe ikony:</h3>
<table>
<tr><td><b>Mikrofon:</b></td><td>🎤 🎙️ 🎚️ 📢 🔴</td></tr>
<tr><td><b>Głośnik:</b></td><td>🔊 🔉 🔈 🔇 📣 🎵</td></tr>
<tr><td><b>Pauza/Play:</b></td><td>⏸️ ▶️ ⏯️ ⏹️ ⏺️</td></tr>
<tr><td><b>Stop:</b></td><td>⬜ ⏹️ 🛑 ❌ ✖️</td></tr>
<tr><td><b>Kopiuj:</b></td><td>⧉ 📋 📄 📑 ✂️</td></tr>
<tr><td><b>Wyślij:</b></td><td>↵ ➡️ 📤 📨 ✈️</td></tr>
<tr><td><b>Akcje:</b></td><td>⚡ ⭐ 💫 🔥 ✨</td></tr>
</table>

<h3>📁 Import/Eksport skórki:</h3>
<p>Możesz zapisać swoją skórkę do pliku <code>.skin.json</code> i udostępnić innym,
lub wczytać skórkę od kogoś innego.</p>
"""

        msg = QMessageBox(self)
        msg.setWindowTitle("Pomoc - Ikony i skórki")
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
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Importuj skórkę",
            str(Path.home()),
            "Pliki skórki (*.skin.json);;Wszystkie pliki (*)"
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
                QMessageBox.information(self, "Sukces", f"Skórka wczytana z:\n{file_path}")

            except Exception as e:
                QMessageBox.warning(self, "Błąd", f"Nie udało się wczytać skórki:\n{e}")

    def _export_skin(self):
        """Export skin to JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Eksportuj skórkę",
            str(Path.home() / "moja_skorka.skin.json"),
            "Pliki skórki (*.skin.json);;Wszystkie pliki (*)"
        )
        if file_path:
            try:
                skin_data = {
                    'name': 'Moja skórka',
                    'version': '1.0',
                    'colors': self.colors,
                    'icons': self.icons
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(skin_data, f, indent=2, ensure_ascii=False)

                QMessageBox.information(self, "Sukces", f"Skórka zapisana do:\n{file_path}")

            except Exception as e:
                QMessageBox.warning(self, "Błąd", f"Nie udało się zapisać skórki:\n{e}")

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
        self.setWindowTitle("Ustawienia")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        # Groq API Key
        self.api_key_field = QLineEdit()
        self.api_key_field.setEchoMode(QLineEdit.Password)
        self.api_key_field.setText(current_api_key)
        self.api_key_field.setPlaceholderText("gsk_...")
        layout.addRow("Klucz API Groq:", self.api_key_field)

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
        self.setWindowTitle("Licencja")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Status
        status = license_manager.get_status()
        status_label = QLabel(f"Status: {status.value}")
        layout.addWidget(status_label)

        # Email
        email = license_manager.get_email()
        if email:
            email_label = QLabel(f"Email: {email}")
            layout.addWidget(email_label)

        # Trial days
        if status == LicenseStatus.TRIAL:
            days = license_manager.get_trial_days_left()
            days_label = QLabel(f"Pozostało dni trial: {days}")
            layout.addWidget(days_label)

        # License key input
        layout.addWidget(QLabel("Wprowadź klucz licencji:"))
        self.key_field = QLineEdit()
        self.key_field.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        layout.addWidget(self.key_field)

        # Activate button
        activate_btn = QPushButton("Aktywuj licencję")
        activate_btn.clicked.connect(self._activate)
        layout.addWidget(activate_btn)

        # Buy button
        buy_btn = QPushButton("Kup licencję")
        buy_btn.clicked.connect(self._buy)
        layout.addWidget(buy_btn)

        # Close button
        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _activate(self):
        key = self.key_field.text().strip()
        if key:
            success, message = self.license_manager.activate_license(key)
            if success:
                QMessageBox.information(self, "Sukces", message)
                self.accept()
            else:
                QMessageBox.warning(self, "Błąd", message)

    def _buy(self):
        import webbrowser
        webbrowser.open(self.license_manager.get_purchase_url())
