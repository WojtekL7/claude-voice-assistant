"""Okno „Szukaj w rozmowie" (🔍) — jedna zakładka, cała jej rozmowa.

Skąd bierzemy tekst: z DZIENNIKA SESJI, nie z bufora ekranu. Powody zmierzone
wcześniej w tym projekcie: bufor terminala ma cap 5000 znaków, niesie znaki
sterujące i ramki narzędzi, a przede wszystkim RÓŻNI SIĘ między silnikami
(QTermWidget w becie vs WebTerminal w pobranej apce). Dziennik jest jeden,
czysty i kompletny na wszystkich systemach.

Okno jest NIEMODALNE — user ma widzieć terminal, bo klik w wynik próbuje też
przewinąć go do znalezionego miejsca.
"""
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QTextEdit, QApplication,
)

from config import t as tr
from gui import theme, icon_set
from core.conversation_search import find_hits, summarize, utf16_offset

# Po tylu milisekundach od ostatniego znaku uruchamiamy szukanie. Bez tego
# każde naciśnięcie klawisza czytałoby cały plik sesji (ok. 1 MB).
_TYPING_DEBOUNCE_MS = 300


class SearchDialog(QDialog):
    """Szukanie w rozmowie JEDNEJ zakładki.

    Sygnały:
      request_speak(str)      — przeczytaj fragment na głos (lektor z MainWindow)
      request_scroll(str)     — spróbuj przewinąć terminal do tego tekstu
    """

    request_speak = pyqtSignal(str)
    request_scroll = pyqtSignal(str)

    def __init__(self, agent_name: str, reader, parent=None):
        super().__init__(parent)
        self._reader = reader
        self._entries = []
        self._hits = []
        self._current = -1

        self.setWindowTitle(f"{tr('search_title')} — {agent_name}")
        self.setModal(False)
        self.resize(760, 520)
        self.setStyleSheet(
            f"QDialog {{ background: {theme.BG_WINDOW}; }}"
            f"QLineEdit {{ background: {theme.BG_INPUT}; color: {theme.TEXT};"
            f" border: 1px solid {theme.BORDER}; border-radius: 8px; padding: 8px 10px; }}"
            f"QLineEdit:focus {{ border: 1px solid {theme.ACCENT}; }}"
            f"QListWidget {{ background: {theme.SURFACE_ALT}; color: {theme.TEXT};"
            f" border: 1px solid {theme.BORDER_SUBTLE}; border-radius: 8px; }}"
            f"QListWidget::item {{ padding: 6px 8px; }}"
            f"QListWidget::item:selected {{ background: {theme.HOVER}; color: {theme.TEXT}; }}"
            f"QTextEdit {{ background: {theme.SURFACE_ALT}; color: {theme.TEXT};"
            f" border: 1px solid {theme.BORDER_SUBTLE}; border-radius: 8px; padding: 8px; }}"
            f"QPushButton {{ background: {theme.SURFACE}; color: {theme.TEXT};"
            f" border: 1px solid {theme.BORDER}; border-radius: 8px; padding: 7px 14px; }}"
            f"QPushButton:hover {{ background: {theme.SURFACE_HOVER}; }}"
            f"QPushButton:disabled {{ color: {theme.TEXT_FAINT}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # --- pasek szukania ---
        top = QHBoxLayout()
        self.field = QLineEdit()
        self.field.setPlaceholderText(tr('search_placeholder'))
        self.field.textChanged.connect(self._on_text_changed)
        self.field.returnPressed.connect(self.go_next)
        top.addWidget(self.field, 1)

        self.prev_btn = QPushButton("▲")
        self.prev_btn.setToolTip(tr('search_prev'))
        self.prev_btn.clicked.connect(self.go_prev)
        top.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▼")
        self.next_btn.setToolTip(tr('search_next'))
        self.next_btn.clicked.connect(self.go_next)
        top.addWidget(self.next_btn)
        root.addLayout(top)

        # --- podpis z liczbą trafień (ZAWSZE z jawnym color:, inaczej czarny
        #     tekst na czarnym tle — pułapka zgłoszona przy oknie „Chmura") ---
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {theme.TEXT_DIM}; padding: 0 2px;")
        root.addWidget(self.status)

        # --- lista trafień ---
        # Zawijanie zamiast POZIOMEGO suwaka: fragment ma ~120 znaków, więc
        # w jednej linii trafienie uciekało poza prawą krawędź i trzeba było
        # przewijać w bok, żeby je w ogóle zobaczyć (zgłoszenie usera 2026-08-03).
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self.results, 2)

        # --- pełny fragment + akcje ---
        # Podgląd dostaje WIĘCEJ miejsca niż lista (3:2, wcześniej 2:3) — to on
        # niesie treść, a lista przy jednym trafieniu świeciła pustką.
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        root.addWidget(self.preview, 3)

        actions = QHBoxLayout()
        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color: {theme.TEXT_FAINT};")
        actions.addWidget(self.hint, 1)

        self.copy_btn = QPushButton(tr('search_copy'))
        self.copy_btn.clicked.connect(self._copy_current)
        actions.addWidget(self.copy_btn)

        self.read_btn = QPushButton(tr('search_read'))
        self.read_btn.setIcon(icon_set.button_icon('read', 'normal', theme.TEXT))
        self.read_btn.clicked.connect(self._speak_current)
        actions.addWidget(self.read_btn)

        self.close_btn = QPushButton(tr('search_close'))
        self.close_btn.clicked.connect(self.close)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run_search)

        self._set_enabled_actions(False)
        self.field.setFocus()

    # ---------- dane ----------

    def _load_entries(self):
        """Świeży odczyt rozmowy (rozmowa rośnie, gdy okno jest otwarte)."""
        try:
            self._entries = self._reader.conversation_entries() if self._reader else []
        except Exception:
            self._entries = []

    def _on_text_changed(self, _text):
        self._timer.start(_TYPING_DEBOUNCE_MS)

    def _run_search(self):
        query = self.field.text().strip()
        self.results.clear()
        self._hits = []
        self._current = -1
        self._set_enabled_actions(False)
        self.preview.clear()
        self.hint.setText("")

        if not query:
            self.status.setText("")
            return

        self._load_entries()
        if not self._entries:
            self.status.setText(tr('search_empty_journal'))
            return

        self._hits = find_hits(self._entries, query)
        if not self._hits:
            self.status.setText(tr('search_none'))
            return

        counts = summarize(self._hits)
        self.status.setText(tr('search_count').format(
            hits=counts['hits'],
            hits_word=tr('search_word_hit_one' if counts['hits'] == 1
                         else 'search_word_hit_many'),
            entries=counts['entries'],
            entries_word=tr('search_word_entry_one' if counts['entries'] == 1
                            else 'search_word_entry_many')))
        for hit in self._hits:
            who = tr('search_role_user') if hit.role == 'user' else tr('search_role_assistant')
            label = f"[{hit.time}] {who}: {hit.snippet()}" if hit.time else f"{who}: {hit.snippet()}"
            QListWidgetItem(label, self.results)
        self.results.setCurrentRow(0)

    # ---------- nawigacja ----------

    def go_next(self):
        if not self._hits:
            self._run_search()
            return
        self.results.setCurrentRow((self.results.currentRow() + 1) % len(self._hits))

    def go_prev(self):
        if not self._hits:
            return
        self.results.setCurrentRow((self.results.currentRow() - 1) % len(self._hits))

    def _on_row_changed(self, row: int):
        if row < 0 or row >= len(self._hits):
            self._set_enabled_actions(False)
            return
        self._current = row
        hit = self._hits[row]
        self._show_preview(hit)
        self._set_enabled_actions(True)
        # „Jedno i drugie": pokazujemy fragment ORAZ próbujemy przewinąć terminal.
        self.request_scroll.emit(hit.matched_text() or hit.snippet(0))

    def _show_preview(self, hit):
        """Pełna wypowiedź z podświetlonym trafieniem.

        Trzy pułapki naraz, wszystkie ZMIERZONE (2026-08-03, zgłoszenie usera):

        1. `QTextEdit.setPlainText` wpisuje tekst BIEŻĄCYM formatem znaku widżetu,
           a po poprzednim podświetleniu był nim akcent → od DRUGIEGO szukania
           cała wypowiedź robiła się fioletowa (0 px akcentu przy 1. szukaniu,
           25 283 px przy 2.). Dlatego zerujemy format PRZED i PO wpisaniu.
        2. Pozycje trafienia są pythonowe, Qt liczy w UTF-16 → `utf16_offset`.
        3. Zostawione ZAZNACZENIE malowało się systemowym niebieskim NA WIERZCHU
           koloru skórki (widać było #308cc6 zamiast akcentu), więc po nadaniu
           formatu zwijamy je do samego początku trafienia.

        ⚠️ KOLEJNOŚĆ NIE JEST DOWOLNA (zmierzone sabotażem, patrz nagłówek
        `tools/test-conversation-search.py`):
        · `setCurrentCharFormat` przy AKTYWNYM zaznaczeniu nadaje format temu
          zaznaczeniu — zerowanie przed zwinięciem SKASOWAŁOBY podświetlenie
          (sabotaż zdejmujący zwinięcie dał puste podświetlenie, nie niebieskie).
        · Samo zwinięcie kursora JUŻ chroni przed pkt 1 wyżej (kursor przejmuje
          format znaku SPRZED trafienia, czyli czysty). Zerowania to DRUGA LINIA
          OBRONY — sabotaż ich usunięcia nie wywalił żadnego testu. Zostawiamy je
          świadomie (chronią, gdyby ktoś kiedyś przestał zwijać zaznaczenie), ale
          NIE licz na test, którego nie ma.
        """
        self.preview.setCurrentCharFormat(QTextCharFormat())
        self.preview.setPlainText(hit.text)

        start = utf16_offset(hit.text, hit.start)
        end = utf16_offset(hit.text, hit.end)
        cursor = self.preview.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(theme.ACCENT))
        fmt.setForeground(QColor('#ffffff'))
        cursor.mergeCharFormat(fmt)

        cursor.setPosition(start)
        self.preview.setTextCursor(cursor)
        self.preview.setCurrentCharFormat(QTextCharFormat())
        self.preview.ensureCursorVisible()

    # ---------- akcje ----------

    def _current_hit(self):
        if 0 <= self._current < len(self._hits):
            return self._hits[self._current]
        return None

    def _copy_current(self):
        hit = self._current_hit()
        if hit is None:
            return
        QApplication.clipboard().setText(hit.text)
        self.hint.setText(tr('search_copied'))

    def _speak_current(self):
        hit = self._current_hit()
        if hit is None:
            return
        self.request_speak.emit(hit.text)

    def _set_enabled_actions(self, on: bool):
        self.copy_btn.setEnabled(on)
        self.read_btn.setEnabled(on)
        self.prev_btn.setEnabled(bool(self._hits))
        self.next_btn.setEnabled(bool(self._hits))

    # ---------- informacja zwrotna z terminala ----------

    def report_scroll(self, scrolled: bool):
        """MainWindow mówi, czy udało się przewinąć terminal do trafienia."""
        self.hint.setText(tr('search_scrolled') if scrolled else tr('search_not_on_screen'))

    def focus_field(self):
        self.field.setFocus()
        self.field.selectAll()
