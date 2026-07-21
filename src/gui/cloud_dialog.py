"""Ekran „Chmura" — przenoszenie „mózgu" agentów między komputerami.

Trzy rzeczy, które user tu robi: łączy konto Google, wysyła paczkę, pobiera ją
na innym komputerze. Świadomie BEZ automatycznej synchronizacji (Faza 2/3) —
w Fazie 1 wszystko dzieje się na wyraźne kliknięcie, więc nic nie zniknie
użytkownikowi „samo z siebie".

⚠️ Praca z siecią idzie do WĄTKU ROBOCZEGO (`_Worker`). Wołanie `auth()`/`upload()`
wprost z wątku okna zamroziłoby całą aplikację na czas logowania (do kilku minut
czekania na zgodę w przeglądarce).
"""
import json
import os
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QMessageBox, QFileDialog, QFrame,
)

from config import (
    CLOUD_CLIENT_FILE, CLOUD_TOKEN_FILE, CLOUD_PASSPHRASE_FILE,
    CLOUD_FOLDER_NAME, CLOUD_BUNDLE_NAME, t as tr,
)
from gui import theme
from core.cloud import bundle_crypto as bc
from core.cloud.agent_bundle import export_sealed, import_sealed
from core.cloud.google_drive import GoogleDriveProvider


def load_passphrase() -> str:
    """Hasło zapamiętane na TYM komputerze (plik tylko dla właściciela).

    Trzymanie go lokalnie nie osłabia ochrony: kto ma dostęp do tego konta,
    ma i tak dostęp do samych agentów. Chroni wyłącznie paczkę leżącą na
    CUDZYM serwerze — a tam trafia wyłącznie zaszyfrowana.
    """
    try:
        return CLOUD_PASSPHRASE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_passphrase(value: str) -> None:
    value = (value or "").strip()
    if not value:
        return
    CLOUD_PASSPHRASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(CLOUD_PASSPHRASE_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value)
    try:
        os.chmod(CLOUD_PASSPHRASE_FILE, 0o600)
    except OSError:
        pass


class _Worker(QThread):
    """Jedno zadanie sieciowe w tle; wynik wraca sygnałem do okna."""
    done = pyqtSignal(bool, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self.done.emit(True, self._fn() or "")
        except Exception as exc:                      # noqa: BLE001 — pokazujemy userowi
            self.done.emit(False, str(exc))


class CloudDialog(QDialog):
    """Okno „Chmura": konto Google, hasło paczki, wyślij/pobierz."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('cloud_title'))
        self.setMinimumSize(620, 520)
        self._worker = None                 # referencja: bez niej Qt sprząta wątek w locie
        self._provider = None
        self._build_ui()
        self._refresh_state()

    # ------------------------------------------------------------------ UI

    def _section(self, layout, tekst):
        lbl = QLabel(tekst)
        lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {theme.TEXT};")
        layout.addWidget(lbl)

    def _hint(self, layout, tekst):
        lbl = QLabel(tekst)
        lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

    def _separator(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {theme.BORDER};")
        layout.addWidget(line)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # --- konto -------------------------------------------------------
        self._section(root, tr('cloud_account'))
        row = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        row.addWidget(self.status_lbl, 1)
        self.connect_btn = QPushButton(tr('cloud_connect'))
        self.connect_btn.clicked.connect(self._on_connect)
        row.addWidget(self.connect_btn)
        self.disconnect_btn = QPushButton(tr('cloud_disconnect'))
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        row.addWidget(self.disconnect_btn)
        root.addLayout(row)
        self._hint(root, tr('cloud_scope_note').format(folder=CLOUD_FOLDER_NAME))

        self._separator(root)

        # --- hasło paczki ------------------------------------------------
        self._section(root, tr('cloud_pass_header'))
        self._hint(root, tr('cloud_pass_desc'))
        prow = QHBoxLayout()
        self.pass_edit = QLineEdit(load_passphrase())
        self.pass_edit.setPlaceholderText(tr('cloud_pass_placeholder'))
        self.pass_edit.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; color: {theme.TEXT}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 4px; padding: 6px;")
        prow.addWidget(self.pass_edit, 1)
        gen_btn = QPushButton(tr('cloud_pass_generate'))
        gen_btn.clicked.connect(self._on_generate)
        prow.addWidget(gen_btn)
        root.addLayout(prow)
        warn = QLabel(tr('cloud_pass_warn'))
        warn.setStyleSheet(f"color: {theme.WARNING}; font-size: 11px;")
        warn.setWordWrap(True)
        root.addWidget(warn)

        self._separator(root)

        # --- wyślij / pobierz --------------------------------------------
        self._section(root, tr('cloud_transfer'))
        self.send_btn = QPushButton(tr('cloud_send'))
        self.send_btn.clicked.connect(self._on_send)
        root.addWidget(self.send_btn)
        self._hint(root, tr('cloud_send_desc'))
        self.get_btn = QPushButton(tr('cloud_get'))
        self.get_btn.clicked.connect(self._on_get)
        root.addWidget(self.get_btn)
        self._hint(root, tr('cloud_get_desc'))

        root.addStretch(1)
        self.info_lbl = QLabel("")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        root.addWidget(self.info_lbl)

        close_btn = QPushButton(tr('dlg_close'))
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignRight)

    # --------------------------------------------------------------- stan

    def _client_data(self):
        try:
            return json.loads(CLOUD_CLIENT_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _get_provider(self):
        if self._provider is not None:
            return self._provider
        data = self._client_data()
        if not data or not data.get("client_id"):
            return None
        self._provider = GoogleDriveProvider(
            client_id=data["client_id"],
            client_secret=data.get("client_secret", ""),
            token_path=CLOUD_TOKEN_FILE,
            folder_name=CLOUD_FOLDER_NAME,
        )
        return self._provider

    def _refresh_state(self):
        provider = self._get_provider()
        if provider is None:
            self.status_lbl.setText(tr('cloud_no_client'))
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.get_btn.setEnabled(False)
            return
        polaczony = provider.is_connected()
        self.status_lbl.setText(
            tr('cloud_connected') if polaczony else tr('cloud_not_connected'))
        self.connect_btn.setEnabled(not polaczony)
        self.disconnect_btn.setEnabled(polaczony)
        self.send_btn.setEnabled(polaczony)
        self.get_btn.setEnabled(polaczony)

    def _busy(self, czy: bool, komunikat: str = ""):
        """W trakcie pracy blokujemy WSZYSTKIE akcje; po niej stan odtwarza
        `_refresh_state()` (on wie, co wolno klikać przy danym stanie konta)."""
        if komunikat:
            self.info_lbl.setText(komunikat)
        if czy:
            for w in (self.connect_btn, self.disconnect_btn, self.send_btn, self.get_btn):
                w.setEnabled(False)
        else:
            self._refresh_state()

    def _run(self, fn, komunikat_startowy: str):
        """Odpal zadanie sieciowe w tle (okno zostaje responsywne)."""
        self._busy(True, komunikat_startowy)
        self._worker = _Worker(fn, self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str):
        self._busy(False)
        self.info_lbl.setText(message if ok else tr('cloud_err').format(error=message))
        if not ok:
            QMessageBox.warning(self, tr('cloud_title'), message)

    # -------------------------------------------------------------- akcje

    def _on_connect(self):
        provider = self._get_provider()
        if provider is None:
            return

        def zadanie():
            provider.auth()
            return tr('cloud_connect_ok')

        self._run(zadanie, tr('cloud_connect_working'))

    def _on_disconnect(self):
        provider = self._get_provider()
        if provider is None:
            return
        provider.disconnect()
        self.info_lbl.setText(tr('cloud_disconnected'))
        self._refresh_state()

    def _on_generate(self):
        self.pass_edit.setText(bc.generate_passphrase())
        QMessageBox.information(self, tr('cloud_title'), tr('cloud_pass_written'))

    def _current_passphrase(self) -> str:
        haslo = self.pass_edit.text().strip()
        if not haslo:
            QMessageBox.warning(self, tr('cloud_title'), tr('cloud_need_pass'))
            return ""
        save_passphrase(haslo)
        return haslo

    def _on_send(self):
        provider = self._get_provider()
        haslo = self._current_passphrase()
        if provider is None or not haslo:
            return

        def zadanie():
            paczka = export_sealed(haslo)          # szyfruje i SAM sprawdza wynik
            provider.upload(CLOUD_BUNDLE_NAME, paczka)
            return tr('cloud_sent_ok').format(kb=max(1, len(paczka) // 1024))

        self._run(zadanie, tr('cloud_send_working'))

    def _on_get(self):
        provider = self._get_provider()
        haslo = self._current_passphrase()
        if provider is None or not haslo:
            return
        katalog = QFileDialog.getExistingDirectory(self, tr('cloud_pick_root'),
                                                   str(Path.home()))
        if not katalog:
            return
        if QMessageBox.question(
                self, tr('cloud_overwrite_title'), tr('cloud_overwrite_text'),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return

        def zadanie():
            paczka = provider.download(CLOUD_BUNDLE_NAME)
            import_sealed(paczka, haslo, katalog)
            return tr('cloud_got_ok')

        self._run(zadanie, tr('cloud_get_working'))
