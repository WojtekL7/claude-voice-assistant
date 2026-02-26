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
    QToolButton, QSizePolicy, QApplication, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QObject
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


class AutoResizeTextEdit(QTextEdit):
    """QTextEdit that auto-resizes based on content."""

    # Signal emitted when Enter is pressed (without Shift)
    returnPressed = pyqtSignal()

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
            self.setFixedHeight(new_height)

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
        """Set plain text (compatibility with QLineEdit)."""
        self.setPlainText(text)

# Import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    SUPPORTED_LANGUAGES, UI_TRANSLATIONS, DEFAULT_QUICK_ACTIONS,
    CONFIG_FILE, QUICK_ACTIONS_FILE, CLAUDE_COMMAND, GROQ_API_KEY
)
from core.claude_bridge import ClaudeBridgeAsync
from core.tts_engine import TTSEngine, TTSState
from core.stt_engine import STTEngine, STTState
from core.license_manager import LicenseManager, LicenseStatus


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
        self.current_color_scheme = "Ubuntu"  # Default: Ubuntu purple theme
        self.auto_read_responses = False
        self.quick_actions = self._load_quick_actions()

        # Load settings
        self._load_settings()

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._setup_shortcuts()

        # Check license
        self._check_license()

        # Start Claude Code
        self._start_claude()

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
        main_layout.setSpacing(10)

        # Terminal area - real terminal emulator using QTermWidget
        if QTERMWIDGET_AVAILABLE:
            self.terminal = QTermWidget(0)  # 0 = don't start shell yet
            self.terminal.setShellProgram("/usr/bin/bash")
            self.terminal.setWorkingDirectory(str(Path.home()))

            # Terminal font
            terminal_font = QFont("Ubuntu Mono", 13)
            terminal_font.setStyleHint(QFont.Monospace)
            self.terminal.setTerminalFont(terminal_font)

            # Apply saved color scheme (or default to Ubuntu)
            available_schemes = self.terminal.availableColorSchemes()
            if self.current_color_scheme in available_schemes:
                self.terminal.setColorScheme(self.current_color_scheme)
            elif "Ubuntu" in available_schemes:
                self.terminal.setColorScheme("Ubuntu")
                self.current_color_scheme = "Ubuntu"
            elif "Linux" in available_schemes:
                self.terminal.setColorScheme("Linux")
                self.current_color_scheme = "Linux"

            # Terminal settings
            self.terminal.setScrollBarPosition(QTermWidget.ScrollBarRight)
            self.terminal.setTerminalOpacity(1.0)
            self.terminal.setHistorySize(10000)

            # Scrollbar styling (Ubuntu terminal style - light gray)
            self.terminal.setStyleSheet("""
                QScrollBar:vertical {
                    background: transparent;
                    width: 12px;
                    margin: 2px;
                }
                QScrollBar::handle:vertical {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #888888, stop:0.5 #aaaaaa, stop:1 #888888);
                    border-radius: 5px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #999999, stop:0.5 #bbbbbb, stop:1 #999999);
                }
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {
                    background: transparent;
                }
            """)

            # Connect signal for TTS (read terminal output)
            self.terminal.receivedData.connect(self._on_terminal_output)
            self.terminal.finished.connect(self._on_terminal_finished)

            # Buffer for TTS
            self._terminal_output_buffer = ""
            self._tts_timer = QTimer()
            self._tts_timer.setSingleShot(True)
            self._tts_timer.timeout.connect(self._read_terminal_buffer)

            # Start the shell
            self.terminal.startShellProgram()

            main_layout.addWidget(self.terminal, stretch=1)

            # Keep reference for compatibility
            self.conversation_area = None
        else:
            # Fallback to QTextEdit if QTermWidget not available
            self.terminal = None
            self.conversation_area = QTextEdit()
            self.conversation_area.setReadOnly(True)
            terminal_font = QFont("Ubuntu Mono", 13)
            terminal_font.setStyleHint(QFont.Monospace)
            self.conversation_area.setFont(terminal_font)
            self.conversation_area.setCursorWidth(8)
            self.conversation_area.setStyleSheet("""
                QTextEdit {
                    background-color: #300A24;
                    color: #ffffff;
                    border: 1px solid #4a1a3a;
                    border-radius: 8px;
                    padding: 12px;
                    selection-background-color: #6a2a5a;
                }
                QScrollBar:vertical {
                    background-color: #300A24;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #4a1a3a;
                    border-radius: 6px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #6a2a5a;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)
            main_layout.addWidget(self.conversation_area, stretch=1)

        # Bottom panel with dark background for buttons
        bottom_panel = QFrame()
        bottom_panel.setStyleSheet("""
            QFrame {
                background-color: #131314;
                border-radius: 10px;
                padding: 5px;
            }
        """)
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(12, 12, 12, 12)
        bottom_layout.setSpacing(10)

        # Input area
        input_area = self._create_input_area()
        bottom_layout.addLayout(input_area)

        # Control buttons
        control_area = self._create_control_area()
        bottom_layout.addLayout(control_area)

        main_layout.addWidget(bottom_panel)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status("Gotowy")

        # Menu bar
        self._create_menu_bar()

        # Apply dark theme
        self._apply_dark_theme()


    def _create_input_area(self) -> QHBoxLayout:
        """Create input area with text field and quick actions."""
        layout = QHBoxLayout()

        # Text input (auto-resize)
        self.input_field = AutoResizeTextEdit()
        self.input_field.setPlaceholderText("Wpisz polecenie lub użyj dyktowania... (Shift+Enter = nowa linia)")
        input_font = QFont("Ubuntu Mono", 13)
        input_font.setStyleHint(QFont.Monospace)
        self.input_field.setFont(input_font)
        self.input_field.setCursorWidth(8)
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #300A24;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 8px;
            }
            QTextEdit:focus {
                border-color: #6a2a5a;
            }
        """)
        layout.addWidget(self.input_field, stretch=1)

        # Quick actions dropdown
        self.quick_actions_btn = QToolButton()
        self.quick_actions_btn.setText("⚡ Szybkie akcje")
        self.quick_actions_btn.setPopupMode(QToolButton.InstantPopup)
        self.quick_actions_btn.setMinimumHeight(40)
        self.quick_actions_btn.setStyleSheet("""
            QToolButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QToolButton:hover {
                background-color: #6a2a5a;
            }
            QToolButton::menu-indicator {
                image: none;
            }
        """)

        self._update_quick_actions_menu()
        layout.addWidget(self.quick_actions_btn)

        # Send button
        self.send_btn = QPushButton("✨ Wyślij")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setMinimumWidth(100)
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #0f172a;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:pressed {
                background-color: #15803d;
            }
        """)
        layout.addWidget(self.send_btn)

        return layout

    def _create_control_area(self) -> QHBoxLayout:
        """Create control buttons area."""
        layout = QHBoxLayout()

        # Dictate button - green
        self.dictate_btn = QPushButton("🎤 Dyktuj")
        self.dictate_btn.setMinimumHeight(45)
        self.dictate_btn.setCheckable(True)
        self.dictate_btn.clicked.connect(self._toggle_dictation)
        self.dictate_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: #0f172a;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:checked {
                background-color: #ef4444;
                color: white;
            }
        """)
        layout.addWidget(self.dictate_btn)

        # Read button - cyan
        self.read_btn = QPushButton("🔊 Czytaj")
        self.read_btn.setMinimumHeight(45)
        self.read_btn.clicked.connect(self._read_last_response)
        self.read_btn.setStyleSheet("""
            QPushButton {
                background-color: #06b6d4;
                color: #0f172a;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0891b2;
            }
        """)
        layout.addWidget(self.read_btn)

        # Pause button - neutral
        self.pause_btn = QPushButton("⏸ Pauza")
        self.pause_btn.setMinimumHeight(45)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #6a2a5a;
            }
            QPushButton:disabled {
                background-color: #300A24;
                color: #6a2a5a;
                border-color: #4a1a3a;
            }
        """)
        layout.addWidget(self.pause_btn)

        # Stop button - red
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.clicked.connect(self._stop_all)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        layout.addWidget(self.stop_btn)

        layout.addStretch()

        # Auto-read checkbox
        self.auto_read_checkbox = QCheckBox("Auto-czytaj odpowiedzi")
        self.auto_read_checkbox.setChecked(self.auto_read_responses)
        self.auto_read_checkbox.stateChanged.connect(self._on_auto_read_changed)
        self.auto_read_checkbox.setStyleSheet("color: #e4e4e7;")
        layout.addWidget(self.auto_read_checkbox)

        return layout

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

        # Terminal color scheme submenu
        if self.terminal and QTERMWIDGET_AVAILABLE:
            edit_menu.addSeparator()
            self.color_scheme_menu = edit_menu.addMenu("🎨 Schemat kolorów terminala")
            self.color_scheme_actions = {}
            self._populate_color_schemes_menu()

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
        """Apply dark theme matching Ubuntu terminal style."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #300A24;
            }
            QMenuBar {
                background-color: #300A24;
                color: #ffffff;
                border-bottom: 1px solid #4a1a3a;
            }
            QMenuBar::item:selected {
                background-color: #4a1a3a;
            }
            QMenu {
                background-color: #300A24;
                color: #ffffff;
                border: 1px solid #4a1a3a;
            }
            QMenu::item:selected {
                background-color: #4a1a3a;
            }
            QStatusBar {
                background-color: #300A24;
                color: #ffffff;
                border-top: 1px solid #4a1a3a;
            }
            QLabel {
                color: #ffffff;
            }
            QCheckBox {
                color: #ffffff;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                background-color: #22c55e;
                border-radius: 3px;
            }
            QMessageBox {
                background-color: #300A24;
                color: #ffffff;
            }
            QMessageBox QLabel {
                color: #ffffff;
            }
            QMessageBox QPushButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 5px;
                padding: 6px 16px;
                min-width: 60px;
            }
            QMessageBox QPushButton:hover {
                background-color: #6a2a5a;
            }
            QDialog {
                background-color: #300A24;
                color: #ffffff;
            }
            QDialog QLabel {
                color: #ffffff;
            }
            QDialog QLineEdit {
                background-color: #1a0a14;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 5px;
                padding: 6px;
            }
            QDialog QPushButton {
                background-color: #4a1a3a;
                color: #ffffff;
                border: 1px solid #6a2a5a;
                border-radius: 5px;
                padding: 6px 16px;
            }
            QDialog QPushButton:hover {
                background-color: #6a2a5a;
            }
            QInputDialog {
                background-color: #300A24;
            }
            QInputDialog QLabel {
                color: #ffffff;
            }
            QInputDialog QLineEdit {
                background-color: #1a0a14;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 5px;
                padding: 6px;
            }
        """)

    def _load_settings(self):
        """Load settings from file."""
        self.anthropic_api_key = ""  # Initialize

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    settings = json.load(f)
                    self.current_language = settings.get('language', 'pl-PL')
                    self.auto_read_responses = settings.get('auto_read', False)
                    self.current_color_scheme = settings.get('color_scheme', 'Ubuntu')

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

            except Exception as e:
                print(f"Error loading settings: {e}")

    def _save_settings(self):
        """Save settings to file."""
        settings = {
            'language': self.current_language,
            'auto_read': self.auto_read_responses,
            'groq_api_key': self.stt.api_key,
            'anthropic_api_key': getattr(self, 'anthropic_api_key', ''),
            'color_scheme': self.current_color_scheme
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
        """Update quick actions dropdown menu."""
        menu = QMenu(self)

        for action in self.quick_actions:
            item = QAction(action['label'], self)
            item.triggered.connect(lambda checked, cmd=action['command']: self._insert_quick_action(cmd))
            menu.addAction(item)

        menu.addSeparator()

        add_action = QAction("➕ Dodaj własną...", self)
        add_action.triggered.connect(self._add_quick_action)
        menu.addAction(add_action)

        self.quick_actions_btn.setMenu(menu)

    def _check_license(self):
        """Check license status (silent - no UI label)."""
        status = self.license_manager.validate()

        if status == LicenseStatus.NO_LICENSE:
            self._show_trial_dialog()
        elif status == LicenseStatus.TRIAL_EXPIRED:
            self._show_license_expired_dialog()
        elif status == LicenseStatus.EXPIRED:
            self._show_license_expired_dialog()
        # TRIAL and VALID - just continue silently

    def _start_claude(self):
        """Start Claude Code process."""
        self._update_status("Uruchamianie Claude Code...")
        self._append_system_message("Uruchamianie Claude Code...")

        if self.claude.start():
            self._update_status("Claude Code uruchomiony")
            self._append_system_message("Claude Code gotowy. Możesz pisać lub dyktować polecenia.")
        else:
            self._update_status("Błąd uruchamiania Claude Code")
            self._append_system_message("Błąd: Nie można uruchomić Claude Code. Upewnij się, że jest zainstalowany.")

    # ==================== Event Handlers ====================

    def _populate_color_schemes_menu(self):
        """Populate color schemes submenu with available schemes."""
        if not self.terminal or not QTERMWIDGET_AVAILABLE:
            return

        schemes = self.terminal.availableColorSchemes()

        # Clear existing actions
        self.color_scheme_menu.clear()
        self.color_scheme_actions = {}

        # Add schemes with nice names
        scheme_labels = {
            'Ubuntu': '🟣 Ubuntu (fioletowe tło)',
            'Linux': '⚫ Linux (czarne tło)',
            'Tango': '🔵 Tango (ciemne)',
            'DarkPastels': '🌙 Dark Pastels (pastelowe)',
            'Solarized': '🌅 Solarized Dark',
            'SolarizedLight': '☀️ Solarized Light',
            'WhiteOnBlack': '⬛ Białe na czarnym',
            'BlackOnWhite': '⬜ Czarne na białym',
            'GreenOnBlack': '💚 Zielone na czarnym (Matrix)',
            'BreezeModified': '🌊 Breeze',
            'Falcon': '🦅 Falcon',
            'BlackOnLightYellow': '🟡 Czarne na żółtym',
            'BlackOnRandomLight': '🎨 Czarne na losowym jasnym',
        }

        for scheme in sorted(schemes):
            label = scheme_labels.get(scheme, scheme)
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(scheme == self.current_color_scheme)
            action.triggered.connect(lambda checked, s=scheme: self._set_color_scheme(s))
            self.color_scheme_menu.addAction(action)
            self.color_scheme_actions[scheme] = action

    def _set_color_scheme(self, scheme: str):
        """Set terminal color scheme."""
        if not self.terminal or not QTERMWIDGET_AVAILABLE:
            return

        self.terminal.setColorScheme(scheme)
        self.current_color_scheme = scheme

        # Update checkmarks
        for s, action in self.color_scheme_actions.items():
            action.setChecked(s == scheme)

        # Save to settings
        self._save_settings()
        self._update_status(f"Schemat kolorów: {scheme}")

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
        # Update buttons
        self.dictate_btn.setText(f"🎤 {self._get_text('dictate')}")
        self.read_btn.setText(f"🔊 {self._get_text('read')}")
        self.pause_btn.setText(f"⏸ {self._get_text('pause')}")
        self.stop_btn.setText(f"⏹ {self._get_text('stop')}")
        self.send_btn.setText(f"📤 {self._get_text('send')}")

        # Update quick actions button
        self.quick_actions_btn.setText(f"⚡ {self._get_text('quick_actions')}")

        # Update checkbox
        self.auto_read_checkbox.setText(self._get_text('auto_read'))

        # Update input placeholder
        placeholder = "Type a command or use dictation..." if self.current_language.startswith("en") else "Wpisz polecenie lub użyj dyktowania..."
        self.input_field.setPlaceholderText(placeholder)

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
            self._terminal_output_buffer += clean_text + " "

            # Reset timer - wait 1 second after last output before reading
            if self.auto_read_responses:
                self._tts_timer.stop()
                self._tts_timer.start(1000)

    def _read_terminal_buffer(self):
        """Read accumulated terminal output via TTS."""
        if self._terminal_output_buffer.strip():
            # Don't read if it's just prompts or short commands
            text = self._terminal_output_buffer.strip()
            if len(text) > 20:  # Only read substantial output
                self.tts.speak(text)
            self._terminal_output_buffer = ""

    def _on_terminal_finished(self):
        """Handle terminal session finished."""
        self._update_status("Terminal zakończony")
        # Optionally restart
        if self.terminal:
            self.terminal.startShellProgram()

    def _on_tts_state_changed(self, state: TTSState):
        """Handle TTS state change."""
        if state == TTSState.PLAYING:
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("⏸ Pauza")
            self._update_status("Czytam...")
        elif state == TTSState.PAUSED:
            self.pause_btn.setText("▶ Wznów")
            self._update_status("Wstrzymano")
        elif state == TTSState.GENERATING:
            self._update_status("Generowanie mowy...")
        else:
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸ Pauza")
            self._update_status("Gotowy")

    def _on_tts_finished(self):
        """Handle TTS finished."""
        self._update_status("Gotowy")

    def _on_stt_state_changed(self, state: STTState):
        """Handle STT state change."""
        if state == STTState.RECORDING:
            self.dictate_btn.setText("🔴 Nagrywanie...")
            self.dictate_btn.setChecked(True)
            self._update_status("Nagrywanie... (kliknij ponownie aby zakończyć)")
        elif state == STTState.PROCESSING:
            self.dictate_btn.setText("⏳ Przetwarzanie...")
            self._update_status("Przetwarzanie mowy...")
        else:
            self.dictate_btn.setText("🎤 Dyktuj")
            self.dictate_btn.setChecked(False)
            self._update_status("Gotowy")

    def _on_transcription(self, text: str):
        """Handle transcription result."""
        if text.strip():
            self.input_field.setText(text)
            self._append_system_message(f"Rozpoznano: {text}")

    def _on_stt_error(self, error: str):
        """Handle STT error."""
        self._append_system_message(f"Błąd rozpoznawania: {error}")
        self._update_status("Błąd rozpoznawania mowy")

    # ==================== Actions ====================

    def _send_message(self):
        """Send message to terminal or Claude."""
        text = self.input_field.text().strip()

        if self.terminal and QTERMWIDGET_AVAILABLE:
            if text:
                # Send text + Enter (with delay for Claude Code)
                self.terminal.sendText(text)
                QTimer.singleShot(50, lambda: self.terminal.sendText("\r"))
                self.input_field.clear()
            else:
                # Empty field - just send Enter (accept Claude Code proposal)
                self.terminal.sendText("\r")

            self._update_status("Wysłano do terminala...")
            return

        # Fallback for non-terminal mode - require text
        if not text:
            return

        self.input_field.clear()
        # Fallback to Claude bridge
        self._append_user_message(text)
        self.claude.send(text)
        self._update_status("Wysłano...")

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
        """Read the last response aloud."""
        if self.terminal and QTERMWIDGET_AVAILABLE:
            # For terminal mode - read from buffer or selected text
            selected = self.terminal.selectedText()
            if selected:
                self.tts.speak(selected)
            elif self._terminal_output_buffer.strip():
                self.tts.speak(self._terminal_output_buffer.strip())
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

        # Find the last AI response
        # Split by user messages (lines starting with ">")
        lines = text.strip().split('\n')

        # Find the last user message position
        last_user_msg_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith('>'):
                last_user_msg_idx = i
                break

        if last_user_msg_idx >= 0:
            # Get everything after the last user message
            response_lines = lines[last_user_msg_idx + 1:]
        else:
            # No user message found, take last 20 lines
            response_lines = lines[-20:]

        # Clean up the response
        response_text = '\n'.join(response_lines).strip()

        # Remove "Processing..." indicator if present
        response_text = response_text.replace('⏳ Processing...', '').strip()

        # Remove system messages
        clean_lines = []
        for line in response_text.split('\n'):
            if not line.strip().startswith('[System]'):
                clean_lines.append(line)

        response_text = '\n'.join(clean_lines).strip()

        if response_text:
            self.tts.speak(response_text)

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
        """Add new quick action."""
        label, ok1 = QInputDialog.getText(self, "Nowa akcja", "Nazwa akcji:")
        if ok1 and label:
            command, ok2 = QInputDialog.getText(self, "Nowa akcja", "Polecenie:")
            if ok2 and command:
                self.quick_actions.append({'label': label, 'command': command})
                self._save_quick_actions()
                self._update_quick_actions_menu()

    def _manage_quick_actions(self):
        """Show quick actions manager dialog."""
        # TODO: Implement full manager dialog
        QMessageBox.information(self, "Szybkie akcje",
            "Edytuj plik:\n" + str(QUICK_ACTIONS_FILE))

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
            else:
                self.conversation_area.clear()
                self.claude.stop()
                self._start_claude()

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

    def closeEvent(self, event):
        """Handle window close."""
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
