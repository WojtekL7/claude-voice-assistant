"""
Vibe Coding Assistant - Agent Tab
Single agent tab with terminal and input panel.
"""
import json
import re
import time
from pathlib import Path
from typing import Optional, Dict, List, Callable

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QToolButton, QCheckBox,
    QFrame, QMenu, QAction, QLabel, QFileDialog,
    QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QFontMetrics, QIcon

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
    DEFAULT_QUICK_ACTIONS, QUICK_ACTIONS_FILE, DEFAULT_SPLITTER_SIZES,
    CRASH_LOG_DIR, TERMINAL_CAPTURE_BYTES, CRASH_LOG_KEEP, CRASH_LOG_DEBOUNCE_SECS,
    ASSETS_DIR,
    t as tr,
)
from core.platform_utils import default_shell
from gui.dialogs import styled_get_open_file_names
from gui.terminal_backend import create_terminal_backend
from gui import icon_set

# Rozmiar ikon SVG w przyciskach dolnego panelu.
PANEL_ICON_SIZE = QSize(24, 24)

# --- Czujnik ruchu terminala a MIGAJĄCA KROPKA bezczynności -------------------
# Gdy agent CZEKA na użytkownika, Claude Code rysuje na dole ekranu migającą
# szarą kropkę „●" (U+25CF; co ~0,5 s na przemian z pustym miejscem). To wysyła
# kilkadziesiąt bajtów co pół sekundy — a nasz czujnik „terminal cichy" (flaga
# „agent czeka", MainWindow._poll_transcripts) traktował KAŻDĄ porcję jako ruch,
# więc licznik ciszy nigdy nie dobijał do progu i flaga się nie uzbrajała.
# Rozwiązanie: porcję będącą WYŁĄCZNIE tą kropką (po zdjęciu kodów ANSI/kursora
# zostaje tylko „●" i/lub biały znak) NIE liczymy jako ruch. Każda inna treść —
# spinner myślenia (gwiazdki „✶✻✽" + „thinking"), strumień odpowiedzi, kod —
# ma realną treść, więc dalej liczy się jako ruch (flaga słusznie nie wchodzi).
# Diagnoza potwierdzona strace: idle = same ramki „●"/spacja, praca = gwiazdki
# i tekst. Uwaga: gdy „●" wystąpi jako punktor WEWNĄTRZ tekstu (biała kropka),
# porcja ma też inną treść → nie zostanie uznana za bezczynność.
_ANSI_STRIP_RE = re.compile(
    r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'      # OSC (np. tytuł okna) ... BEL/ST
    r'|\x1b[\[\]][0-9;?]*[ -/]*[@-~]'          # CSI (kolory, kursor, tryby)
    r'|\x1b[()][A-Za-z0-9]'                    # wybór zestawu znaków
    r'|\x1b[=>]'                               # tryb klawiatury
    r'|[\x00-\x08\x0b-\x1f\x7f]'               # znaki sterujące (bez \n, \t)
)
# Znaki uznawane za „ozdobę bezczynności" (nic nie znaczące dla treści).
_IDLE_MARKER_CHARS = '●'                   # ● — migający wskaźnik „czekam"


def _is_terminal_activity(data: str) -> bool:
    """Czy porcja z terminala to REALNY ruch, czy tylko migająca kropka idle?

    Zwraca False WYŁĄCZNIE, gdy po zdjęciu kodów sterujących zostają jedynie
    znaki-ozdoby bezczynności (● / spacje) — wtedy nie odświeżamy czujnika ruchu,
    dzięki czemu cisza terminala może narosnąć i flaga „agent czeka" się uzbroi.
    Każda inna (choćby jednoznakowa realna) treść → True.
    """
    if not data:
        return False
    text = data if isinstance(data, str) else str(data)
    residual = _ANSI_STRIP_RE.sub('', text)
    # zdejmij białe znaki i znaki-ozdoby; jeśli coś zostaje → realna treść
    for ch in _IDLE_MARKER_CHARS:
        residual = residual.replace(ch, '')
    return residual.strip() != ''


class AutoResizeTextEdit(QTextEdit):
    """Text input that auto-resizes based on content."""

    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document().contentsChanged.connect(self._adjust_height)
        # Suwak pionowy widoczny TYLKO przy długim poleceniu: pole rośnie do
        # _max_lines (5) linii, a powyżej (≥6 linii) staje i pokazuje suwak
        # (życzenie usera). Krótki tekst = brak suwaka — start jako WYŁĄCZONY,
        # a _adjust_height włącza/wyłącza go jawnie wg wysokości tekstu (samo
        # AsNeeded pokazywało go za wcześnie). Poziomy zawsze wyłączony (zawijamy).
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Wygląd suwaka = ta sama ciemna rynna + szary uchwyt co w terminalu
        # (WebTerminal). Stylujemy TYLKO sam pasek (verticalScrollBar), żeby nie
        # ruszać palety/tła pola (chroni fix białego błysku po Enter).
        self.verticalScrollBar().setStyleSheet(
            "QScrollBar:vertical { width: 12px; background: #2a2a2d; margin: 0; }"
            "QScrollBar::handle:vertical { background: #8a8a8a; border-radius: 5px;"
            " min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: #a6a6a6; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            " height: 0; background: none; border: none; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            " background: #2a2a2d; }")
        self._max_lines = 5
        self._padding = 20  # margines wewn. (ramka + padding dokumentu)
        self._min_height = 55
        self._max_height = 180  # przeliczane w _adjust_height wg czcionki (5 linii)
        self.setMinimumHeight(self._min_height)
        self.setMaximumHeight(self._min_height)

    def _adjust_height(self):
        """Dopasuj wysokość do treści, z górnym limitem _max_lines linii.

        Powyżej limitu pole nie rośnie — pojawia się suwak (ScrollBarAsNeeded).
        Limit liczony z czcionki POLA (ustawianej po konstruktorze), więc działa
        niezależnie od rozmiaru/rodziny czcionki."""
        line_h = QFontMetrics(self.font()).lineSpacing()
        self._max_height = line_h * self._max_lines + self._padding
        doc_height = int(self.document().size().height())
        # Suwak włączamy JAWNIE dopiero, gdy treść nie mieści się w 5 liniach —
        # inaczej trzymamy go wyłączonego (żeby nie pokazywał się przy krótkim
        # tekście ani pustym polu).
        needs_scroll = doc_height + self._padding > self._max_height
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if needs_scroll else Qt.ScrollBarAlwaysOff)
        new_height = max(self._min_height,
                         min(doc_height + self._padding, self._max_height))
        self.setMinimumHeight(new_height)
        self.setMaximumHeight(new_height)

    def keyPressEvent(self, event):
        """Handle Enter key to send message."""
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Paste as plain text — drop colors, fonts, underlines from the source.

        Covers Ctrl+V, Shift+Insert, context-menu Paste, and text/file drag&drop.
        Dropping a file (e.g. an image) inserts its PATH as text — never a raw
        embedded image — matching how a real terminal handles a dropped file.
        """
        if source.hasUrls():
            paths = []
            for url in source.urls():
                local = url.toLocalFile()
                if local:
                    paths.append('"%s"' % local if " " in local else local)
            if paths:
                self.textCursor().insertText(" ".join(paths))
                return
        if source.hasText():
            self.textCursor().insertText(source.text())
        else:
            super().insertFromMimeData(source)

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
    request_pause = pyqtSignal()  # Request TTS pause/resume (przycisk ⏸)
    request_read_last = pyqtSignal()  # Request MainWindow to read last Claude response (with extraction)
    request_dictation = pyqtSignal(bool)  # Request dictation start/stop
    add_quick_action_requested = pyqtSignal()  # Request to add new quick action
    splitter_changed = pyqtSignal(list)  # Emitted when splitter position changes
    terminal_ready = pyqtSignal()  # Emitted from activate() po stworzeniu QTermWidget

    def __init__(self, agent_config: dict, parent=None):
        super().__init__(parent)

        self.agent_config = agent_config
        self.agent_id = agent_config.get('id', 'unknown')
        self.agent_name = agent_config.get('name', 'Agent')
        self.working_directory = agent_config.get('working_directory', str(Path.home()))
        self.memory_files = agent_config.get('memory_files', [])  # list of file paths
        self.auto_start = agent_config.get('auto_start', True)
        self.model = agent_config.get('model', 'default')
        self.splitter_sizes = agent_config.get(
            'splitter_sizes', list(DEFAULT_SPLITTER_SIZES))

        # State
        # terminal_backend — wspólny interfejs (M2.2); terminal — opakowany
        # widget (backend.widget). Na Linuksie to QTermWidget, na macOS/Windows
        # (lub pod CVA_WEBTERMINAL=1) WebTerminal. Reszta kodu rozmawia z
        # backendem, nie z surowym widgetem.
        self.terminal_backend = None
        self.terminal = None
        self.conversation_area = None
        self._terminal_output_buffer = ""
        # Tryb myszy terminala: 'claude' (DOMYŚLNY — kółko przewija rozmowę Claude,
        # klik w menu wyboru, zaznaczanie z Shift) albo 'select' (zaznaczanie/
        # kopiowanie przeciągnięciem bez Shift). Przełącznik w pasku przycisków.
        self._mouse_mode = 'claude'
        # „Czarna skrzynka": ring-bufor SUROWEGO wyjścia terminala (z ANSI) —
        # ostatnie ~64 KB. Niezależny od _terminal_output_buffer (ten liczy
        # tokeny, bywa czyszczony i okrojony do 5000 zn.). Przy wykryciu podpisu
        # ekranu ratunkowego Claude Code zrzucamy go do pliku — bo crash `claude`
        # (dziecko powłoki) NIE odpala backend.finished, a stack trace inaczej
        # bezpowrotnie przewija się z terminala. Patrz _maybe_dump_crash_log.
        self._terminal_capture = ""
        self._last_crash_dump_ts = 0.0
        # Czas OSTATNIEJ porcji danych z terminala (puls aktywności). Pracujący
        # Claude Code animuje pasek (spinner + licznik sekund ~1×/s) → dane
        # płyną ciągle; czekający na użytkownika — ekran stoi. Używane przez
        # flagę „?" (MainWindow._poll_transcripts) jako CZUJNIK RUCHU, bo sam
        # dziennik sesji stoi też podczas pracy (wpisy lądują dopiero po
        # ukończeniu bloku). Start = teraz, żeby świeża zakładka nie była
        # od razu „cicha".
        self._last_terminal_data_ts = time.monotonic()
        self._tts_timer = None
        self._memory_sent = False
        # Lazy activation: zakładka tworzy tylko UI shell w __init__; ciężki
        # QTermWidget + bash + claude CLI startują dopiero przy pierwszym
        # pokazaniu (MainWindow woła activate() z _on_tab_changed). Bez tego
        # 4 agenty × ~700 MB każdy = OOM-kill na 7.7 GB laptopie.
        self._activated = False
        self._terminal_placeholder = None
        self.attached_files = []
        self.quick_actions = []
        # Per-agent licznik przybliżonej liczby tokenów. MainWindow dolicza
        # znaki przez add_chars() i czyta total_context_tokens przy zmianie zakładki.
        self.total_context_tokens = 0

        # UI references (will be set by MainWindow for shared state)
        self.skin_colors = {}
        self.skin_icons = {}
        self.auto_read_responses = False
        self.current_language = "pl-PL"

        # Etap 3 (Droga A): czytanie prozy z dziennika sesji per-zakładka.
        # is_plain_terminal — zwykły terminal bez claude, więc bez dziennika.
        self.is_plain_terminal = agent_config.get('is_plain_terminal', False)
        # Czytnik dziennika (tworzony w MainWindow._on_terminal_ready, gdy
        # terminal i sesja claude już istnieją).
        self._transcript_reader = None
        self._transcript_primed = False
        # Zaległa proza nazbierana, gdy zakładka była NIEAKTYWNA — do doczytania
        # przyciskiem 🔊 po przełączeniu (decyzja: komunikat + przycisk).
        self.pending_backlog = []

        # Najpierw wczytaj listę szybkich akcji — _setup_ui() korzysta z niej
        # przy budowaniu menu (przez _update_quick_actions_menu). Bez tego
        # menu byłoby puste do pierwszej edycji w QuickActionsDialog.
        self._load_quick_actions()
        self._setup_ui()

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

        # Dodatkowa wysokość okna (np. ekran pionowy) ma trafiać do TERMINALA
        # (indeks 0), a nie do panelu wejścia (indeks 1). Bez tego splitter
        # rozdaje nadmiar również panelowi wejścia → rośnie pusta przestrzeń,
        # w której prześwitywało tło (szare pole na pionowym ekranie).
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        # Connect splitter moved signal to save position
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self.main_splitter)

    def _setup_terminal(self):
        """Setup lekkiego placeholdera — prawdziwy terminal powstaje w activate().

        Placeholder zajmuje slot w splitterze (zachowuje rozmiary), ale nie
        spawnuje bash ani claude CLI. Oszczędność RAM przy starcie: zamiast
        4 × QTermWidget+bash+claude (~5 GB) tylko 4 × pusty QWidget (~5 MB).
        """
        self._terminal_placeholder = QWidget()
        # Tło dopasowane do skin terminal_bg — żeby nie błyskało białym przed
        # aktywacją. Bardziej szczegółowe kolory ustawi MainWindow przy
        # apply_terminal_colors po terminal_ready.
        self._terminal_placeholder.setStyleSheet("background-color: #1a1a1a;")
        self.main_splitter.addWidget(self._terminal_placeholder)
        self.terminal = None
        self.conversation_area = None

    def is_activated(self) -> bool:
        """Czy ciężki silnik (terminal + bash) już wstał."""
        return self._activated

    def activate(self):
        """Lazy initialization: stwórz backend terminala (silnik + powłoka). Idempotentne.

        Wołane z MainWindow gdy zakładka po raz pierwszy zostaje aktywna
        (currentChanged → _on_tab_changed). Fabryka (M2.2) wybiera silnik:
        Linux → QTermWidget (bez zmian), macOS/Windows lub CVA_WEBTERMINAL=1 →
        WebTerminal. Po stworzeniu emituje terminal_ready, na który MainWindow
        podpina: apply_terminal_colors, uruchomienie `claude`, pliki pamięci.
        """
        if self._activated:
            return

        # Fabryka tworzy i konfiguruje właściwy silnik. Cała konfiguracja
        # (czcionka, scrollbar, historia, flow control) żyje wewnątrz backendu
        # — patrz terminal_backend.py.
        self.terminal_backend = create_terminal_backend(
            working_directory=self.working_directory,
            shell=default_shell(),
            font_family="Ubuntu Mono",
            font_size=13,
        )
        self.terminal = self.terminal_backend.widget
        self.conversation_area = None

        # Wyjście terminala (już zdekodowane do str) — wyłącznie do liczenia
        # tokenów; auto-czytanie idzie z dziennika sesji (Droga A).
        self.terminal_backend.output_received.connect(self._on_terminal_output)
        self.terminal_backend.finished.connect(self._on_terminal_finished)

        # TTS timer (zachowany jak w oryginale).
        self._tts_timer = QTimer()
        self._tts_timer.setSingleShot(True)
        self._tts_timer.timeout.connect(self._read_terminal_buffer)

        # Kolejność jak w oryginale: start powłoki ZANIM widget trafi do
        # splittera. Odwrotnie QTermWidget renderuje się jako niewidoczny, mimo
        # że bash i claude działają w tle (PyQt5 5.15 + QTermWidget 1.4.0 +
        # XWayland, 2026-05-14). Splitter jest już ostylowany (apply_styles przy
        # tworzeniu zakładki), więc ciężki widget wchodzi w gotową geometrię
        # (pułapka „szare pasy po prawej").
        self.terminal_backend.start_shell_program()
        # Odtwórz wybrany tryb myszy (gdyby user przełączył przed restartem zakładki).
        self.terminal_backend.set_mouse_mode(self._mouse_mode)
        self._swap_placeholder_with(self.terminal)

        self._activated = True
        self.terminal_ready.emit()

    def _swap_placeholder_with(self, widget):
        """Podmiana placeholdera na właściwy widget terminala w splitterze.

        QSplitter.replaceWidget zwraca usunięty widget; my go niszczymy.
        Sizes splittera przywracamy po podmianie, bo replaceWidget potrafi je
        zresetować na default'y.
        """
        if self._terminal_placeholder is None:
            self.main_splitter.insertWidget(0, widget)
        else:
            idx = self.main_splitter.indexOf(self._terminal_placeholder)
            old = self.main_splitter.replaceWidget(idx, widget)
            if old is not None:
                old.setParent(None)
                old.deleteLater()
            self._terminal_placeholder = None
        self.main_splitter.setSizes(self.splitter_sizes)
        # Po podmianie potwierdź: nadmiar wysokości → terminal, nie panel wejścia.
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

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
        self.input_field.setPlaceholderText(tr('input_placeholder'))
        input_font = QFont("Ubuntu Mono", 13)
        input_font.setStyleHint(QFont.Monospace)
        self.input_field.setFont(input_font)
        self.input_field.setCursorWidth(8)
        self.input_field.returnPressed.connect(self._send_message)
        layout.addWidget(self.input_field, stretch=1)

        # Send button
        self.send_btn = QPushButton("↵ Enter")
        self.send_btn.setFixedSize(100, 48)
        self.send_btn.setToolTip(tr('send_tooltip'))
        self.send_btn.clicked.connect(self._send_message)
        layout.addWidget(self.send_btn)

        return layout

    def _create_control_area(self) -> QHBoxLayout:
        """Create control buttons area."""
        layout = QHBoxLayout()
        btn_size = 48

        # Dictate button (ikona SVG zamiast emoji — spójna na Linux/Mac/Windows)
        self.dictate_btn = QPushButton()
        self.dictate_btn.setIcon(icon_set.button_icon('dictate'))
        self.dictate_btn.setIconSize(PANEL_ICON_SIZE)
        self.dictate_btn.setFixedSize(btn_size, btn_size)
        self.dictate_btn.setCheckable(True)
        self.dictate_btn.setToolTip(tr('dictate_tooltip'))
        self.dictate_btn.clicked.connect(self._toggle_dictation)
        layout.addWidget(self.dictate_btn)

        # Read button
        self.read_btn = QPushButton()
        self.read_btn.setIcon(icon_set.button_icon('read'))
        self.read_btn.setIconSize(PANEL_ICON_SIZE)
        self.read_btn.setFixedSize(btn_size, btn_size)
        self.read_btn.setToolTip(tr('read_tooltip'))
        self.read_btn.clicked.connect(self._read_last_response)
        layout.addWidget(self.read_btn)

        # Pause button (hidden by default)
        self.pause_btn = QPushButton()
        self.pause_btn.setIcon(icon_set.button_icon('pause'))
        self.pause_btn.setIconSize(PANEL_ICON_SIZE)
        self.pause_btn.setFixedSize(btn_size, btn_size)
        self.pause_btn.setToolTip(tr('pause_tooltip'))
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setVisible(False)
        layout.addWidget(self.pause_btn)

        # Stop button (hidden by default)
        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(icon_set.button_icon('stop'))
        self.stop_btn.setIconSize(PANEL_ICON_SIZE)
        self.stop_btn.setFixedSize(btn_size, btn_size)
        self.stop_btn.setToolTip(tr('stop_tooltip'))
        self.stop_btn.clicked.connect(self._stop_all)
        self.stop_btn.setVisible(False)
        layout.addWidget(self.stop_btn)

        # Copy button
        self.copy_btn = QPushButton()
        self.copy_btn.setIcon(icon_set.button_icon('copy'))
        self.copy_btn.setIconSize(PANEL_ICON_SIZE)
        self.copy_btn.setFixedSize(btn_size, btn_size)
        self.copy_btn.setToolTip(tr('copy_tooltip'))
        self.copy_btn.clicked.connect(self._copy_selection)
        layout.addWidget(self.copy_btn)

        # Clear input button
        self.clear_input_btn = QPushButton()
        self.clear_input_btn.setIcon(icon_set.button_icon('clear_input'))
        self.clear_input_btn.setIconSize(PANEL_ICON_SIZE)
        self.clear_input_btn.setFixedSize(btn_size, btn_size)
        self.clear_input_btn.setToolTip(tr('clear_input_tooltip'))
        self.clear_input_btn.clicked.connect(self._clear_input_field)
        layout.addWidget(self.clear_input_btn)

        # Add media button
        self.add_media_btn = QPushButton()
        self.add_media_btn.setIcon(icon_set.button_icon('add_media'))
        self.add_media_btn.setIconSize(PANEL_ICON_SIZE)
        self.add_media_btn.setFixedSize(btn_size, btn_size)
        self.add_media_btn.setToolTip(tr('add_media_tooltip'))
        self.add_media_btn.clicked.connect(self._add_media)
        layout.addWidget(self.add_media_btn)

        # Quick actions dropdown
        self.quick_actions_btn = QToolButton()
        self.quick_actions_btn.setIcon(icon_set.button_icon('quick_actions'))
        self.quick_actions_btn.setIconSize(PANEL_ICON_SIZE)
        self.quick_actions_btn.setToolTip(tr('quick_actions'))
        self.quick_actions_btn.setPopupMode(QToolButton.InstantPopup)
        self.quick_actions_btn.setFixedSize(btn_size, btn_size)
        self._update_quick_actions_menu()
        layout.addWidget(self.quick_actions_btn)

        # Przełącznik trybu myszy — NA KOŃCU paska, po „błyskawicy", ikoną w tej
        # samej konwencji co reszta. Ikona pokazuje AKTUALNY tryb: mysz+strzałki
        # (przewijanie) ↔ mysz+ramka (zaznaczanie). Klik przeskakuje między nimi.
        self._icon_mouse_scroll = QIcon(str(ASSETS_DIR / "mouse-scroll.png"))
        self._icon_mouse_select = QIcon(str(ASSETS_DIR / "mouse-select.png"))
        self.mouse_mode_btn = QPushButton()
        self.mouse_mode_btn.setIconSize(PANEL_ICON_SIZE)
        self.mouse_mode_btn.setFixedSize(btn_size, btn_size)
        self.mouse_mode_btn.setToolTip(tr('mouse_mode_tooltip'))
        self.mouse_mode_btn.clicked.connect(self._toggle_mouse_mode)
        self._update_mouse_mode_btn()
        layout.addWidget(self.mouse_mode_btn)

        layout.addStretch()

        # Auto-read checkbox
        self.auto_read_checkbox = QCheckBox(tr('auto_read'))
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

        add_action = QAction(f"➕ {tr('add_action')}", self)
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
        """Handle terminal output (już zdekodowany str z backendu).

        Backend ujednolica wyjście: na Linuksie QTermWidget oddaje QByteArray,
        który backend dekoduje do str; WebTerminal od razu daje str. Bufor służy
        wyłącznie do liczenia tokenów — auto-czytanie idzie z dziennika sesji.
        """
        if not self.terminal_backend:
            return

        # Puls aktywności terminala — ale POMIŃ migającą kropkę bezczynności,
        # bo inaczej „czekający" agent wygląda na wiecznie aktywny i flaga
        # „agent czeka" nigdy się nie uzbraja (patrz _is_terminal_activity).
        if _is_terminal_activity(data):
            self._last_terminal_data_ts = time.monotonic()
        # Emit signal for MainWindow
        self.terminal_output.emit(data)

        text = data if isinstance(data, str) else str(data)

        # „Czarna skrzynka": dopisz SUROWY fragment do ring-bufora i utnij do
        # limitu (tylko gdy przekroczony — bez kosztu przy każdej porcji).
        self._terminal_capture += text
        if len(self._terminal_capture) > TERMINAL_CAPTURE_BYTES:
            self._terminal_capture = self._terminal_capture[-TERMINAL_CAPTURE_BYTES:]
        # Tani pre-check PRZED regexem (ta metoda to gorąca ścieżka: spinner
        # Claude Code odpala ją ~1×/s). Podpis ekranu ratunkowego po crashu:
        # „claude --resume <uuid>". Dopiero gdy „resume" w tej porcji — weryfikuj.
        if "resume" in text:
            self._maybe_dump_crash_log()

        # Clean ANSI codes
        import re
        clean_text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
        clean_text = re.sub(r'\x1b\][^\x07]*\x07', '', clean_text)
        clean_text = clean_text.strip()

        if clean_text:
            self._terminal_output_buffer += clean_text + "\n"

            # Limit buffer size (bufor służy już tylko do liczenia tokenów)
            if len(self._terminal_output_buffer) > 5000:
                self._terminal_output_buffer = self._terminal_output_buffer[-5000:]

            # Auto-czytanie NIE korzysta już z tego śmieciowego bufora terminala.
            # Czytamy czystą prozę z dziennika sesji (Droga A) — patrz
            # MainWindow._poll_transcripts. Tu zostaje tylko liczenie tokenów.

    def _on_terminal_finished(self):
        """Handle terminal process finished."""
        self.status_changed.emit("Terminal zakończony")

    # ---- „Czarna skrzynka": zrzut wyjścia terminala po crashu `claude` ----

    _CRASH_SIGNATURE_RE = re.compile(r"claude\s+--resume\s+[0-9a-fA-F-]{32,40}")

    def _maybe_dump_crash_log(self):
        """Jeśli w buforze jest podpis ekranu ratunkowego Claude Code, zrzuć log.

        Wywoływane tylko gdy świeża porcja zawierała „resume" (tani pre-check
        w _on_terminal_output). Tu pełna weryfikacja regexem + debounce, żeby
        powtarzające się przerysowania ekranu ratunkowego nie tworzyły serii
        plików. Całość defensywna — diagnostyka NIGDY nie może wywrócić apki.
        """
        try:
            if not self._CRASH_SIGNATURE_RE.search(self._terminal_capture):
                return
            now = time.monotonic()
            if now - self._last_crash_dump_ts < CRASH_LOG_DEBOUNCE_SECS:
                return
            self._last_crash_dump_ts = now
            self._dump_crash_log()
        except Exception:
            # świadomie połykamy — log diagnostyczny nie może psuć działania
            pass

    def _dump_crash_log(self):
        """Zapisz ANSI-oczyszczony ring-bufor do pliku z nagłówkiem i przytnij
        liczbę plików do CRASH_LOG_KEEP. Nazwa: crash-<agent>-<RRRRMMDD-GGMMSS>.log."""
        import re as _re
        from datetime import datetime

        raw = self._terminal_capture
        # Oczyść sekwencje ANSI (CSI + OSC) — stack trace node jest czystym
        # tekstem, więc po oczyszczeniu jest najczytelniejszy.
        clean = _re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", raw)
        clean = _re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", clean)
        clean = clean.replace("\r", "")

        # Usuń ZAGNIEŻDŻONE nagłówki czarnej skrzynki, które wpadły do bufora,
        # gdy poprzedni crash-log był wyświetlony w tej zakładce (np. `cat`/odczyt)
        # lub ekran ratunkowy się przerysował. Bez tego nagłówki kumulują się
        # z pokolenia na pokolenie (zaobserwowane: 60× w jednym pliku). Świeży
        # nagłówek doklejamy niżej, więc tu czyścimy tylko stare kopie.
        # Kotwiczymy na linii „=… CVA crash capture …" + kolejnych liniach
        # metadanych (czas/agent/model/cwd/powód/uwaga); końcowy separator
        # „====" bywa zgubiony przy przechwycie z terminala, więc opcjonalny.
        clean = _re.sub(
            r"={2,}\s*CVA crash capture[^\n]*\n"
            r"(?:(?:czas|agent|model|cwd|powód|uwaga):[^\n]*\n)+"
            r"(?:={5,}\n+)?",
            "",
            clean,
        ).lstrip()

        # Sanityzacja nazwy agenta do nazwy pliku (bez separatorów ścieżki).
        safe_name = _re.sub(r"[^\w.-]", "_", str(self.agent_name))[:40] or "agent"
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")

        CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = CRASH_LOG_DIR / f"crash-{safe_name}-{ts}.log"

        header = (
            "=== CVA crash capture (czarna skrzynka terminala) ===\n"
            f"czas:    {datetime.now().isoformat(timespec='seconds')}\n"
            f"agent:   {self.agent_name} (id={self.agent_id})\n"
            f"model:   {self.model}\n"
            f"cwd:     {self.working_directory}\n"
            f"powód:   wykryto ekran ratunkowy Claude Code (claude --resume ...)\n"
            f"uwaga:   to OSTATNIE ~{TERMINAL_CAPTURE_BYTES // 1024} KB wyjścia terminala "
            "(stdout+stderr zlane w PTY), ANSI usunięte.\n"
            "=" * 60 + "\n\n"
        )
        path.write_text(header + clean, encoding="utf-8", errors="replace")

        # Przytnij najstarsze zrzuty ponad limit.
        logs = sorted(CRASH_LOG_DIR.glob("crash-*.log"), key=lambda p: p.stat().st_mtime)
        for old in logs[:-CRASH_LOG_KEEP]:
            try:
                old.unlink()
            except OSError:
                pass

        self.status_changed.emit(f"Zapisano log crashu: {path.name}")

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

        if self.terminal_backend:
            if full_message:
                self.terminal_backend.send_text(full_message)
                QTimer.singleShot(50, lambda: self.terminal_backend.send_text("\r"))
                self.input_field.clear()
                self._clear_attachments()
                self.status_changed.emit("Wysłano do terminala...")
                self.message_sent.emit(full_message)
            else:
                self.terminal_backend.send_text("\r")
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
                parts.append(f"{tr('analyze_files_prefix')} {files_list}")
                parts.append("")
                parts.append(text)
            else:
                parts.append(f"{tr('analyze_files_prefix')} {files_list}")

        return "\n".join(parts) if parts else text

    def send_text_to_terminal(self, text: str):
        """Send text directly to terminal (for memory files)."""
        if self.terminal_backend:
            self.terminal_backend.send_text(text)
            QTimer.singleShot(50, lambda: self.terminal_backend.send_text("\r"))

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
            # Send only paths - Claude Code will read them itself.
            # Każdą ścieżkę w cudzysłowach — inaczej ścieżka ZE SPACJĄ (np.
            # ".../Strona Fulfillment-polska.pl/...") rozpada się na dwa błędne
            # kawałki i Claude nie wczytuje pliku pamięci (objaw: „agent nie
            # startuje z plikami pamięci"). Cudzysłów nie szkodzi ścieżkom bez spacji.
            paths_list = " ".join(f'"{p}"' for p in valid_paths)
            context_message = f"{tr('read_memory_context')} {paths_list}"
            self.send_text_to_terminal(context_message)
            self.status_changed.emit(tr('sent_memory_files').format(n=len(valid_paths)))

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
        """Request MainWindow to read last Claude response.

        Delegates to MainWindow which extracts the last response from the buffer
        (filtering out UI frames, spinners, user prompts) and handles selected text.
        """
        self.request_read_last.emit()

    def _toggle_pause(self):
        """Pauza/wznów czytania (TTS). Obsługę wykonuje MainWindow na silniku TTS."""
        self.request_pause.emit()

    def _stop_all(self):
        """Stop all TTS and dictation."""
        self.request_tts_stop.emit()

    def _copy_selection(self):
        """Copy selected text from terminal.

        Podgląd w pasku statusu pokazuje liczbę skopiowanych znaków (0 = brak
        zaznaczenia) — i informacja dla użytkownika, i szybka diagnoza, czy
        terminal w ogóle widzi zaznaczenie."""
        if self.terminal_backend:
            n = self.terminal_backend.copy_selection() or 0
            if n > 0:
                self.status_changed.emit(tr('status_copied_chars').format(n=n))
            else:
                self.status_changed.emit(tr('status_copy_no_selection'))
        elif self.conversation_area:
            self.conversation_area.copy()
            self.status_changed.emit(tr('status_copied_clipboard'))

    def _toggle_mouse_mode(self):
        """Przełącz tryb myszy terminala: 'claude' (kółko przewija rozmowę,
        klik w menu, zaznaczanie z Shift) ↔ 'select' (zaznaczanie/kopiowanie
        przeciągnięciem bez Shift). Dotyczy WebTerminala (na QTermWidget no-op)."""
        self._mouse_mode = 'select' if self._mouse_mode == 'claude' else 'claude'
        if self.terminal_backend:
            self.terminal_backend.set_mouse_mode(self._mouse_mode)
        self._update_mouse_mode_btn()
        sel = (self._mouse_mode == 'select')
        self.status_changed.emit(
            tr('status_mouse_select') if sel else tr('status_mouse_scroll'))

    def _update_mouse_mode_btn(self):
        """Odśwież IKONĘ przełącznika trybu myszy wg self._mouse_mode (ikona
        pokazuje aktualny tryb: przewijanie ↔ zaznaczanie)."""
        sel = (self._mouse_mode == 'select')
        self.mouse_mode_btn.setIcon(
            self._icon_mouse_select if sel else self._icon_mouse_scroll)

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

        files, _ = styled_get_open_file_names(
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

        # Anti-flash: ten sam ciemny kolor także w PALECIE pola (rola Base), nie
        # tylko w stylesheet. Bez tego po wyczyszczeniu pola (Enter) Qt na ~1 klatkę
        # maluje domyślne białe tło palety, zanim nałoży styl → migający biały
        # prostokąt (intermittentnie, zależnie od trafienia między klatkami).
        # Ustawiamy na samym polu I na jego viewport (właściwy obszar tekstu).
        ipal = self.input_field.palette()
        ipal.setColor(QPalette.Base, QColor(input_bg))
        ipal.setColor(QPalette.Text, QColor(text_color))
        self.input_field.setPalette(ipal)
        self.input_field.viewport().setPalette(ipal)

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
            'model': self.model,
            'splitter_sizes': self.splitter_sizes,
        }

    def update_config(self, config: dict):
        """Update agent configuration."""
        self.agent_config = config
        self.agent_id = config.get('id', self.agent_id)
        self.agent_name = config.get('name', self.agent_name)
        self.auto_start = config.get('auto_start', self.auto_start)
        self.memory_files = config.get('memory_files', [])
        self.model = config.get('model', self.model)

        new_working_dir = config.get('working_directory', self.working_directory)
        if new_working_dir != self.working_directory:
            self.working_directory = new_working_dir
            if self.terminal_backend:
                self.terminal_backend.send_text(f"cd {new_working_dir}\r")

        # Update splitter sizes if provided
        new_splitter_sizes = config.get('splitter_sizes')
        if new_splitter_sizes and new_splitter_sizes != self.splitter_sizes:
            self.splitter_sizes = new_splitter_sizes
            self.main_splitter.setSizes(new_splitter_sizes)
