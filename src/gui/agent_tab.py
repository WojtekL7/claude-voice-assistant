"""
Claude Voice Assistant - Agent Tab
Single agent tab with terminal and input panel.
"""
import json
from pathlib import Path
from typing import Optional, Dict, List, Callable

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QToolButton, QCheckBox,
    QFrame, QMenu, QAction, QLabel, QFileDialog,
    QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# QTermWidget for real terminal emulation
try:
    from QTermWidget import QTermWidget
    QTERMWIDGET_AVAILABLE = True
except ImportError:
    QTERMWIDGET_AVAILABLE = False

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MEMORY_PROJECTS_FILE, MEMORY_FILE_EXTENSIONS,
    DEFAULT_QUICK_ACTIONS, QUICK_ACTIONS_FILE
)


class AutoResizeTextEdit(QTextEdit):
    """Text input that auto-resizes based on content."""

    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document().contentsChanged.connect(self._adjust_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._min_height = 55
        self._max_height = 180
        self.setMinimumHeight(self._min_height)
        self.setMaximumHeight(self._min_height)

    def _adjust_height(self):
        """Adjust height based on content."""
        doc_height = self.document().size().height()
        new_height = max(self._min_height, min(int(doc_height) + 20, self._max_height))
        self.setMinimumHeight(new_height)
        self.setMaximumHeight(new_height)

    def keyPressEvent(self, event):
        """Handle Enter key to send message."""
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)

    def text(self):
        """Get plain text content."""
        return self.toPlainText()

    def setText(self, text):
        """Set plain text content."""
        self.setPlainText(text)


class AgentTab(QWidget):
    """Single agent tab with terminal and controls."""

    # Signals
    message_sent = pyqtSignal(str)  # Emitted when user sends a message
    terminal_output = pyqtSignal(object)  # Emitted when terminal receives data
    status_changed = pyqtSignal(str)  # Emitted to update status bar
    request_tts = pyqtSignal(str)  # Request TTS to speak text
    request_tts_stop = pyqtSignal()  # Request TTS to stop
    request_dictation = pyqtSignal(bool)  # Request dictation start/stop
    add_quick_action_requested = pyqtSignal()  # Request to add new quick action
    splitter_changed = pyqtSignal(list)  # Emitted when splitter position changes

    def __init__(self, agent_config: dict, parent=None):
        super().__init__(parent)

        self.agent_config = agent_config
        self.agent_id = agent_config.get('id', 'unknown')
        self.agent_name = agent_config.get('name', 'Agent')
        self.working_directory = agent_config.get('working_directory', str(Path.home()))
        self.memory_files = agent_config.get('memory_files', [])  # list of file paths
        self.auto_start = agent_config.get('auto_start', True)
        self.splitter_sizes = agent_config.get('splitter_sizes', [600, 150])

        # State
        self.terminal = None
        self.conversation_area = None
        self._terminal_output_buffer = ""
        self._tts_timer = None
        self._memory_sent = False
        self.attached_files = []
        self.quick_actions = []

        # UI references (will be set by MainWindow for shared state)
        self.skin_colors = {}
        self.skin_icons = {}
        self.auto_read_responses = False
        self.current_language = "pl-PL"

        self._setup_ui()
        self._load_quick_actions()

    def set_shared_state(self, skin_colors: dict, skin_icons: dict,
                         auto_read: bool, language: str):
        """Set shared state from MainWindow."""
        self.skin_colors = skin_colors
        self.skin_icons = skin_icons
        self.auto_read_responses = auto_read
        self.current_language = language
        self.auto_read_checkbox.setChecked(auto_read)

    def _setup_ui(self):
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main splitter (terminal + bottom panel)
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setHandleWidth(6)

        # Terminal area
        self._setup_terminal()

        # Bottom panel
        self._setup_bottom_panel()

        self.main_splitter.addWidget(self.bottom_panel)
        self.main_splitter.setSizes(self.splitter_sizes)

        # Connect splitter moved signal to save position
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self.main_splitter)

    def _setup_terminal(self):
        """Setup terminal widget."""
        if QTERMWIDGET_AVAILABLE:
            self.terminal = QTermWidget(0)
            self.terminal.setShellProgram("/usr/bin/bash")
            self.terminal.setWorkingDirectory(self.working_directory)

            # Terminal font
            terminal_font = QFont("Ubuntu Mono", 13)
            terminal_font.setStyleHint(QFont.Monospace)
            self.terminal.setTerminalFont(terminal_font)

            # Terminal settings
            self.terminal.setScrollBarPosition(QTermWidget.ScrollBarRight)
            self.terminal.setTerminalOpacity(1.0)
            self.terminal.setHistorySize(10000)
            self.terminal.setFlowControlEnabled(False)
            self.terminal.setFlowControlWarningEnabled(False)
            self.terminal.setTerminalSizeHint(False)

            # Scrollbar styling
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

            # Connect signals
            self.terminal.receivedData.connect(self._on_terminal_output)
            self.terminal.finished.connect(self._on_terminal_finished)

            # TTS timer
            self._tts_timer = QTimer()
            self._tts_timer.setSingleShot(True)
            self._tts_timer.timeout.connect(self._read_terminal_buffer)

            # Start shell
            self.terminal.startShellProgram()

            self.main_splitter.addWidget(self.terminal)
            self.conversation_area = None
        else:
            # Fallback
            self.terminal = None
            self.conversation_area = QTextEdit()
            self.conversation_area.setReadOnly(True)
            terminal_font = QFont("Ubuntu Mono", 13)
            terminal_font.setStyleHint(QFont.Monospace)
            self.conversation_area.setFont(terminal_font)
            self.conversation_area.setStyleSheet("""
                QTextEdit {
                    background-color: #300A24;
                    color: #ffffff;
                    border: 1px solid #4a1a3a;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
            self.main_splitter.addWidget(self.conversation_area)

    def _setup_bottom_panel(self):
        """Setup bottom panel with input and controls."""
        self.bottom_panel = QFrame()
        bottom_layout = QVBoxLayout(self.bottom_panel)
        bottom_layout.setContentsMargins(12, 12, 12, 12)
        bottom_layout.setSpacing(10)

        # Input area
        input_layout = self._create_input_area()
        bottom_layout.addLayout(input_layout)

        # Attachments area (hidden by default)
        self.attachments_widget = QWidget()
        self.attachments_layout = QHBoxLayout(self.attachments_widget)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setSpacing(5)
        self.attachments_widget.setVisible(False)
        bottom_layout.addWidget(self.attachments_widget)

        # Control buttons
        control_layout = self._create_control_area()
        bottom_layout.addLayout(control_layout)

    def _create_input_area(self) -> QHBoxLayout:
        """Create input area with text field."""
        layout = QHBoxLayout()

        self.input_field = AutoResizeTextEdit()
        self.input_field.setPlaceholderText("Wpisz polecenie lub użyj dyktowania... (Shift+Enter = nowa linia)")
        input_font = QFont("Ubuntu Mono", 13)
        input_font.setStyleHint(QFont.Monospace)
        self.input_field.setFont(input_font)
        self.input_field.setCursorWidth(8)
        self.input_field.returnPressed.connect(self._send_message)
        layout.addWidget(self.input_field, stretch=1)

        # Send button
        self.send_btn = QPushButton("↵ Enter")
        self.send_btn.setFixedSize(100, 48)
        self.send_btn.setToolTip("Wyślij (Enter)")
        self.send_btn.clicked.connect(self._send_message)
        layout.addWidget(self.send_btn)

        return layout

    def _create_control_area(self) -> QHBoxLayout:
        """Create control buttons area."""
        layout = QHBoxLayout()
        btn_size = 48

        # Dictate button
        self.dictate_btn = QPushButton("🎤")
        self.dictate_btn.setFixedSize(btn_size, btn_size)
        self.dictate_btn.setCheckable(True)
        self.dictate_btn.setToolTip("Dyktuj (nagrywanie głosu)")
        self.dictate_btn.clicked.connect(self._toggle_dictation)
        layout.addWidget(self.dictate_btn)

        # Read button
        self.read_btn = QPushButton("🔊")
        self.read_btn.setFixedSize(btn_size, btn_size)
        self.read_btn.setToolTip("Czytaj ostatnią odpowiedź")
        self.read_btn.clicked.connect(self._read_last_response)
        layout.addWidget(self.read_btn)

        # Pause button (hidden by default)
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setFixedSize(btn_size, btn_size)
        self.pause_btn.setToolTip("Pauza / Wznów")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setVisible(False)
        layout.addWidget(self.pause_btn)

        # Stop button (hidden by default)
        self.stop_btn = QPushButton("⬜")
        self.stop_btn.setFixedSize(btn_size, btn_size)
        self.stop_btn.setToolTip("Zatrzymaj wszystko")
        self.stop_btn.clicked.connect(self._stop_all)
        self.stop_btn.setVisible(False)
        layout.addWidget(self.stop_btn)

        # Copy button
        self.copy_btn = QPushButton("⧉")
        self.copy_btn.setFixedSize(btn_size, btn_size)
        self.copy_btn.setToolTip("Kopiuj zaznaczony tekst")
        self.copy_btn.clicked.connect(self._copy_selection)
        layout.addWidget(self.copy_btn)

        # Clear input button
        self.clear_input_btn = QPushButton("✕")
        self.clear_input_btn.setFixedSize(btn_size, btn_size)
        self.clear_input_btn.setToolTip("Wyczyść pole tekstowe")
        self.clear_input_btn.clicked.connect(self._clear_input_field)
        layout.addWidget(self.clear_input_btn)

        # Add media button
        self.add_media_btn = QPushButton("📎")
        self.add_media_btn.setFixedSize(btn_size, btn_size)
        self.add_media_btn.setToolTip("Dodaj media (zdjęcia, dokumenty, pliki)")
        self.add_media_btn.clicked.connect(self._add_media)
        layout.addWidget(self.add_media_btn)

        # Quick actions dropdown
        self.quick_actions_btn = QToolButton()
        self.quick_actions_btn.setText("⚡▼")
        self.quick_actions_btn.setToolTip("Szybkie akcje")
        self.quick_actions_btn.setPopupMode(QToolButton.InstantPopup)
        self.quick_actions_btn.setFixedSize(btn_size, btn_size)
        self._update_quick_actions_menu()
        layout.addWidget(self.quick_actions_btn)

        layout.addStretch()

        # Auto-read checkbox
        self.auto_read_checkbox = QCheckBox("Auto-czytaj odpowiedzi")
        self.auto_read_checkbox.setChecked(self.auto_read_responses)
        self.auto_read_checkbox.stateChanged.connect(self._on_auto_read_changed)
        layout.addWidget(self.auto_read_checkbox)

        return layout

    # ==================== Quick Actions ====================

    def _load_quick_actions(self):
        """Load quick actions from file."""
        if QUICK_ACTIONS_FILE.exists():
            try:
                with open(QUICK_ACTIONS_FILE, 'r') as f:
                    self.quick_actions = json.load(f)
                    return
            except:
                pass
        self.quick_actions = DEFAULT_QUICK_ACTIONS.copy()

    def _update_quick_actions_menu(self):
        """Update quick actions dropdown menu."""
        menu = QMenu(self.quick_actions_btn)

        for action in self.quick_actions:
            item = QAction(action['label'], self)
            item.triggered.connect(lambda checked, cmd=action['command']: self._insert_quick_action(cmd))
            menu.addAction(item)

        menu.addSeparator()

        add_action = QAction("➕ Dodaj własną...", self)
        add_action.triggered.connect(self._add_quick_action)
        menu.addAction(add_action)

        self.quick_actions_btn.setMenu(menu)

    def _insert_quick_action(self, command: str):
        """Insert quick action command into input field."""
        self.input_field.setText(command)
        self.input_field.setFocus()

    def _add_quick_action(self):
        """Add new quick action - delegate to MainWindow via signal."""
        self.add_quick_action_requested.emit()

    # ==================== Terminal Handling ====================

    def _on_terminal_output(self, data):
        """Handle terminal output for TTS."""
        if not self.terminal:
            return

        # Emit signal for MainWindow
        self.terminal_output.emit(data)

        try:
            text = data.data().decode('utf-8', errors='ignore')
        except:
            text = str(data)

        # Clean ANSI codes
        import re
        clean_text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
        clean_text = re.sub(r'\x1b\][^\x07]*\x07', '', clean_text)
        clean_text = clean_text.strip()

        if clean_text:
            self._terminal_output_buffer += clean_text + "\n"

            # Limit buffer size
            if len(self._terminal_output_buffer) > 5000:
                self._terminal_output_buffer = self._terminal_output_buffer[-5000:]

            # Auto-read timer
            if self.auto_read_responses and self._tts_timer:
                self._tts_timer.stop()
                self._tts_timer.start(2000)

    def _on_terminal_finished(self):
        """Handle terminal process finished."""
        self.status_changed.emit("Terminal zakończony")

    def _read_terminal_buffer(self):
        """Read accumulated terminal output via TTS."""
        if not self._terminal_output_buffer.strip():
            return

        # Request TTS from MainWindow
        self.request_tts.emit(self._terminal_output_buffer)
        self._terminal_output_buffer = ""

    # ==================== Message Handling ====================

    def _send_message(self):
        """Send message to terminal."""
        text = self.input_field.text().strip()
        full_message = self._build_message_with_attachments(text)

        if self.terminal and QTERMWIDGET_AVAILABLE:
            if full_message:
                self.terminal.sendText(full_message)
                QTimer.singleShot(50, lambda: self.terminal.sendText("\r"))
                self.input_field.clear()
                self._clear_attachments()
                self.status_changed.emit("Wysłano do terminala...")
                self.message_sent.emit(full_message)
            else:
                self.terminal.sendText("\r")
        elif self.conversation_area:
            if full_message:
                self.conversation_area.append(f">>> {full_message}")
                self.input_field.clear()
                self._clear_attachments()

    def _build_message_with_attachments(self, text: str) -> str:
        """Build message with attached file paths."""
        if not self.attached_files:
            return text

        parts = []
        if self.attached_files:
            files_list = " ".join(self.attached_files)
            if text:
                parts.append(f"Przeanalizuj te pliki: {files_list}")
                parts.append("")
                parts.append(text)
            else:
                parts.append(f"Przeanalizuj te pliki: {files_list}")

        return "\n".join(parts) if parts else text

    def send_text_to_terminal(self, text: str):
        """Send text directly to terminal (for memory files)."""
        if self.terminal and QTERMWIDGET_AVAILABLE:
            self.terminal.sendText(text)
            QTimer.singleShot(50, lambda: self.terminal.sendText("\r"))

    # ==================== Memory Files ====================

    def send_memory_files(self):
        """Send memory file paths to Claude Code (not full content)."""
        if self._memory_sent:
            return

        if not self.memory_files:
            self._memory_sent = True
            return

        # Collect paths of existing files
        valid_paths = []
        for file_path in self.memory_files:
            if Path(file_path).exists():
                valid_paths.append(file_path)

        if valid_paths:
            # Send only paths - Claude Code will read them itself
            paths_list = " ".join(valid_paths)
            context_message = f"Przeczytaj pliki pamięci projektu i zapamiętaj ich zawartość jako kontekst: {paths_list}"
            self.send_text_to_terminal(context_message)
            self.status_changed.emit(f"Wysłano {len(valid_paths)} plików pamięci")

        self._memory_sent = True

    # ==================== UI Actions ====================

    def showEvent(self, event):
        """Apply splitter sizes after widget is shown."""
        super().showEvent(event)
        # Delay to let Qt finish layout calculations
        QTimer.singleShot(50, self._apply_saved_splitter_sizes)

    def _apply_saved_splitter_sizes(self):
        """Apply saved splitter sizes after widget is visible."""
        if self.splitter_sizes and hasattr(self, 'main_splitter'):
            self.main_splitter.setSizes(self.splitter_sizes)

    def _on_splitter_moved(self, pos: int, index: int):
        """Handle splitter position change - save new sizes."""
        self.splitter_sizes = self.main_splitter.sizes()
        self.splitter_changed.emit(self.splitter_sizes)

    def _toggle_dictation(self, checked: bool):
        """Toggle dictation mode."""
        self.request_dictation.emit(checked)

    def _read_last_response(self):
        """Request TTS to read last response."""
        if self._terminal_output_buffer.strip():
            self.request_tts.emit(self._terminal_output_buffer)
            self._terminal_output_buffer = ""

    def _toggle_pause(self):
        """Toggle TTS pause."""
        # Will be connected to MainWindow's TTS
        pass

    def _stop_all(self):
        """Stop all TTS and dictation."""
        self.request_tts_stop.emit()

    def _copy_selection(self):
        """Copy selected text from terminal."""
        if self.terminal and QTERMWIDGET_AVAILABLE:
            self.terminal.copyClipboard()
            self.status_changed.emit("Skopiowano do schowka")
        elif self.conversation_area:
            self.conversation_area.copy()
            self.status_changed.emit("Skopiowano do schowka")

    def _clear_input_field(self):
        """Clear the input field."""
        self.input_field.clear()
        self._clear_attachments()

    def _add_media(self):
        """Open file dialog to add media attachments."""
        file_filter = (
            "Wszystkie obsługiwane (*.png *.jpg *.jpeg *.gif *.bmp *.webp "
            "*.pdf *.doc *.docx *.txt *.csv *.xlsx *.xls *.json *.xml *.zip *.tar *.gz);;"
            "Obrazy (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;"
            "Dokumenty (*.pdf *.doc *.docx *.txt);;"
            "Dane (*.csv *.xlsx *.xls *.json *.xml);;"
            "Archiwa (*.zip *.tar *.gz);;"
            "Wszystkie pliki (*)"
        )

        files, _ = QFileDialog.getOpenFileNames(
            self, "Dodaj pliki", str(Path.home()), file_filter
        )

        if files:
            for file_path in files:
                if file_path not in self.attached_files:
                    self.attached_files.append(file_path)
                    self._add_attachment_chip(file_path)

            self.attachments_widget.setVisible(True)

    def _add_attachment_chip(self, file_path: str):
        """Add attachment chip to UI."""
        chip = QFrame()
        chip.setStyleSheet("""
            QFrame {
                background-color: #4a1a3a;
                border-radius: 12px;
                padding: 2px;
            }
        """)
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 4, 4, 4)
        chip_layout.setSpacing(4)

        # File icon and name
        file_name = Path(file_path).name
        ext = Path(file_path).suffix.lower()

        icon = "📷" if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'] else \
               "📄" if ext in ['.pdf', '.doc', '.docx', '.txt'] else \
               "📊" if ext in ['.csv', '.xlsx', '.xls', '.json', '.xml'] else \
               "📦" if ext in ['.zip', '.tar', '.gz'] else "📎"

        label = QLabel(f"{icon} {file_name}")
        label.setStyleSheet("color: #ffffff; font-size: 11px;")
        chip_layout.addWidget(label)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ef4444;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_attachment(file_path, chip))
        chip_layout.addWidget(remove_btn)

        self.attachments_layout.addWidget(chip)

    def _remove_attachment(self, file_path: str, chip: QFrame):
        """Remove attachment from list."""
        if file_path in self.attached_files:
            self.attached_files.remove(file_path)
        chip.deleteLater()

        if not self.attached_files:
            self.attachments_widget.setVisible(False)

    def _clear_attachments(self):
        """Clear all attachments."""
        self.attached_files.clear()

        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.attachments_widget.setVisible(False)

    def _on_auto_read_changed(self, state):
        """Handle auto-read checkbox change."""
        self.auto_read_responses = state == Qt.Checked

    # ==================== Styling ====================

    def apply_styles(self, skin_colors: dict, skin_icons: dict):
        """Apply skin colors and icons."""
        self.skin_colors = skin_colors
        self.skin_icons = skin_icons

        # Set background for the entire tab using palette
        main_bg = skin_colors.get('main_window_bg', '#300A24')
        from PyQt5.QtGui import QPalette, QColor
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(main_bg))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        # Splitter styling - set background and handle
        splitter_color = skin_colors.get('splitter_color', '#4a1a3a')
        self.main_splitter.setStyleSheet(f"""
            QSplitter {{
                background-color: {main_bg};
            }}
            QSplitter::handle {{
                background-color: {splitter_color};
            }}
        """)

        # Bottom panel
        bottom_bg = skin_colors.get('bottom_panel_bg', '#131314')
        self.bottom_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {bottom_bg};
                border-radius: 10px;
                padding: 5px;
            }}
        """)

        # Input field
        input_bg = skin_colors.get('input_bg', '#300A24')
        text_color = skin_colors.get('text_color', '#ffffff')
        border_color = skin_colors.get('border_color', '#4a1a3a')
        hover_color = skin_colors.get('hover_color', '#6a2a5a')

        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 2px solid {border_color};
                border-radius: 12px;
                padding: 12px;
                selection-background-color: {hover_color};
            }}
            QTextEdit:focus {{
                border: 2px solid {hover_color};
            }}
        """)

        # Note: Terminal colors are applied by MainWindow._apply_terminal_colors()
        # which creates a custom color scheme and applies it to all terminals

    def get_config(self) -> dict:
        """Get current agent configuration."""
        return {
            'id': self.agent_id,
            'name': self.agent_name,
            'auto_start': self.auto_start,
            'memory_files': self.memory_files,
            'working_directory': self.working_directory,
            'splitter_sizes': self.splitter_sizes,
        }

    def update_config(self, config: dict):
        """Update agent configuration."""
        self.agent_config = config
        self.agent_id = config.get('id', self.agent_id)
        self.agent_name = config.get('name', self.agent_name)
        self.auto_start = config.get('auto_start', self.auto_start)
        self.memory_files = config.get('memory_files', [])

        new_working_dir = config.get('working_directory', self.working_directory)
        if new_working_dir != self.working_directory:
            self.working_directory = new_working_dir
            if self.terminal and QTERMWIDGET_AVAILABLE:
                self.terminal.sendText(f"cd {new_working_dir}\r")

        # Update splitter sizes if provided
        new_splitter_sizes = config.get('splitter_sizes')
        if new_splitter_sizes and new_splitter_sizes != self.splitter_sizes:
            self.splitter_sizes = new_splitter_sizes
            self.main_splitter.setSizes(new_splitter_sizes)
