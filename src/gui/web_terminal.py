"""
Vibe Coding Assistant - WebTerminal (Etap M2.1)

Wieloplatformowy terminal: xterm.js renderowany w QtWebEngine, napędzany
pythonowym PTY. Zastąpi linuksowy QTermWidget na macOS/Windows (i opcjonalnie
na Linuksie). API celowo zbliżone do QTermWidget, by wpięcie w AgentTab (M2.3)
było proste.

Warstwa PTY jest odseparowana: teraz wariant uniksowy (Linux + macOS przez
`ptyprocess`); Windows dostanie ConPTY (`pywinpty`) w to samo miejsce — patrz
TODO(Windows).
"""
import os
import sys
import json
import codecs
import threading
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl, Qt, QTimer, QEvent
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEngineSettings, QWebEnginePage, QWebEngineProfile,
)
from PyQt5.QtWebChannel import QWebChannel

# Ten moduł bywa uruchamiany WPROST (`python3 src/gui/web_terminal.py` — izolowany
# test WebTerminala), a wtedy korzeniem sys.path jest src/gui, nie src.
try:
    from gui import theme
except ImportError:  # pragma: no cover - ścieżka tylko dla trybu demo
    import theme

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.platform_utils import default_shell, is_windows
from config import ASSETS_DIR, CONFIG_DIR

# PTY: dwa warianty za jednym interfejsem.
#  - Unix (Linux/macOS): ptyprocess (read=bytes, write=bytes, terminate(force=)).
#  - Windows: winpty (pywinpty) → ConPTY (read=str, write=str, terminate()).
# _PTY_KIND wybiera gałąź w _spawn/_read_loop/_write_pty/shutdown.
if is_windows():
    try:
        import winpty  # pywinpty — ConPTY (Windows 10+)
        _PTY_AVAILABLE = True
        _PTY_KIND = "winpty"
    except Exception:
        _PTY_AVAILABLE = False
        _PTY_KIND = None
else:
    try:
        import ptyprocess
        _PTY_AVAILABLE = True
        _PTY_KIND = "ptyprocess"
    except Exception:
        _PTY_AVAILABLE = False
        _PTY_KIND = None

# Jedno źródło prawdy o ścieżce zasobów (config.ASSETS_DIR jest świadomy
# wersji spakowanej — sys._MEIPASS — więc terminal.html działa też w .app/.exe).
ASSET_DIR = ASSETS_DIR / "web"

# Log diagnostyczny WebTerminala — w spakowanej aplikacji okienkowej (zwłaszcza
# Windows, console=False) stderr nie istnieje, więc awarie QtWebEngine/PTY były
# niewidoczne ("puste pole" w 1.0.12). Każde zdarzenie cyklu życia trafia tutaj.
WEBTERMINAL_LOG = CONFIG_DIR / "webterminal.log"
try:  # prosta rotacja: nie pozwól plikowi rosnąć w nieskończoność
    if WEBTERMINAL_LOG.exists() and WEBTERMINAL_LOG.stat().st_size > 512 * 1024:
        WEBTERMINAL_LOG.unlink()
except Exception:
    pass


def _log(message: str):
    """Dopisz linię do logu diagnostycznego (nigdy nie wywala aplikacji)."""
    try:
        with open(WEBTERMINAL_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


class _LoggingWebEnginePage(QWebEnginePage):
    """Strona przechwytująca komunikaty konsoli JS do logu diagnostycznego.

    Bez tego błąd JavaScriptu (np. nie załadowany xterm.js) umiera po cichu,
    a użytkownik widzi tylko puste pole bez kursora.
    """
    _LEVELS = {0: "INFO", 1: "WARN", 2: "ERROR"}

    def javaScriptConsoleMessage(self, level, message, line, source):
        _log(f"JS[{self._LEVELS.get(int(level), level)}] {source}:{line}: {message}")


class _Bridge(QObject):
    """Most QWebChannel między JS (xterm.js) a Pythonem (PTY)."""
    output = pyqtSignal(str)   # Python → terminal (wyjście PTY)
    closed = pyqtSignal()      # proces PTY zakończony

    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    @pyqtSlot(str)
    def send_input(self, data):
        self._owner._write_pty(data)

    @pyqtSlot(int, int)
    def resize(self, cols, rows):
        self._owner._resize_pty(cols, rows)

    @pyqtSlot(int, int)
    def frontend_ready(self, cols, rows):
        self._owner._on_frontend_ready(cols, rows)

    @pyqtSlot(str)
    def set_selection(self, text):
        self._owner._selection = text or ""


class WebTerminal(QWidget):
    """Terminal oparty o xterm.js + QtWebEngine + PTY."""

    finished = pyqtSignal()
    output_bytes = pyqtSignal(str)   # surowe wyjście (do liczenia tokenów w M2.3)
    _data_ready = pyqtSignal(str)     # wewn.: wątek-czytnik → GUI (bezpieczne wątkowo)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._reader = None
        self._stop = threading.Event()
        self._selection = ""
        self._shell = default_shell()
        self._cwd = None
        self._pending_size = (80, 24)
        # Motyw/czcionka mogą przyjść z Pythona ZANIM xterm.js się załaduje —
        # buforujemy i wysyłamy po frontend_ready (inaczej runJavaScript przepada).
        self._pending_theme = None
        self._pending_font = None
        # Tryb myszy: 'claude' (domyślny — kółko przewija Claude, zaznaczanie z Shift)
        # albo 'select' (zaznaczanie/kopiowanie bez Shift). Przełączany z UI.
        self._mouse_mode = 'claude'
        # Wejście (np. komenda `claude`) potrafi przyjść ZANIM powłoka wstanie —
        # a powłoka startuje dopiero po frontend_ready (gdy xterm.js się załaduje,
        # bywa ~2 s przy wolniejszym QtWebEngine, np. w AppImage). Bez bufora
        # write-do-PTY przepadał po cichu (objaw: `claude` nie startował, a
        # wiadomość pamięci trafiała wprost do bash-a → "command not found").
        # Buforujemy i opróżniamy w _spawn(), w kolejności wysłania.
        self._pending_input = []
        self._frontend_ready = False
        self._logged_first_output = False
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        self._failure_shown = False
        # Drag&drop pliku NA terminal — patrz _install_drop_filter/eventFilter.
        # QtWebEngine renderuje treść w wewnętrznym widgecie (focusProxy); to ON
        # dostaje QDropEvent z OS. JS w terminal.html NIE dostaje prawdziwej ścieżki
        # (Chromium ją ukrywa), więc upuszczenie pliku obsługujemy po stronie Qt.
        self._drop_filter_target = None
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        # Profil "off-the-record" (bez nazwy magazynu) = wszystko w PAMIĘCI, ZERO
        # zapisu na dysk. Terminal (xterm.js z pliku) nie potrzebuje ciasteczek ani
        # cache. Dzięki temu nie powstaje współdzielona baza ciasteczek QtWebEngine,
        # więc kilka kopii programu naraz NIE wywołuje już zalewu błędów
        # "Cookie sqlite error: database is locked" (każda kopia ma własną pamięć).
        self._profile = QWebEngineProfile(self.view)   # bez nazwy → off-the-record
        # Własna strona NA TYM profilu: loguje konsolę JS (diagnoza "pustego pola").
        # Ustawiana PRZED settings/webchannel — one działają na bieżącej stronie widoku.
        self._page = _LoggingWebEnginePage(self._profile, self.view)
        self.view.setPage(self._page)
        # QtWebEngine maluje stronę na BIAŁO, dopóki terminal.html się nie wczyta
        # (~1 s: xterm.js + czcionka) → widoczny biały błysk przy starcie.
        # Ustawiamy z góry tło strony na ten sam ciemny kolor co terminal.html
        # (theme.BG_CANVAS), żeby od pierwszej klatki było ciemno.
        self._page.setBackgroundColor(QColor(theme.BG_CANVAS))
        st = self.view.settings()
        st.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        st.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        st.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        layout.addWidget(self.view)

        self.bridge = _Bridge(self)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self._data_ready.connect(self._push_to_js)
        self.finished.connect(self._on_finished_gui)

        # Diagnostyka cyklu życia strony: nieudane ładowanie / śmierć procesu
        # renderowania mają pokazać czytelny komunikat, nie martwe puste pole.
        self.view.loadFinished.connect(self._on_load_finished)
        self._page.renderProcessTerminated.connect(self._on_render_terminated)

        url = ASSET_DIR / "terminal.html"
        _log(f"WebTerminal: start, html={url} (istnieje={url.exists()}), "
             f"PTY={_PTY_KIND or 'BRAK'}, shell={self._shell}")
        self.view.load(QUrl.fromLocalFile(str(url)))

    # ==================== API zbliżone do QTermWidget ====================

    def set_shell_program(self, program: str):
        self._shell = program

    def set_working_directory(self, path: str):
        """Katalog roboczy powłoki. Ustaw PRZED start_shell_program()."""
        self._cwd = path or None

    def start_shell_program(self):
        """Odpal powłokę (jeśli front gotowy; inaczej zrobi to frontend_ready)."""
        if self._frontend_ready and self._proc is None:
            self._spawn()

    def send_text(self, text: str):
        self._write_pty(text)

    def selected_text(self) -> str:
        return self._selection

    def clear(self):
        self.view.page().runJavaScript("window.__termClear && window.__termClear();")

    def set_theme(self, theme: dict):
        """Zastosuj pełny motyw xterm (dict ITheme: background/foreground/cursor/
        selectionBackground + 16 kolorów ANSI). Przed gotowością frontu — buforuj."""
        self._pending_theme = dict(theme) if theme else None
        if self._frontend_ready:
            self._push_theme()

    def set_font(self, family: str, size: int):
        """Ustaw czcionkę terminala (rodzina + rozmiar). Przed gotowością — buforuj."""
        self._pending_font = (family, int(size))
        if self._frontend_ready:
            self._push_font()

    def _push_theme(self):
        if self._pending_theme is None:
            return
        # json.dumps daje poprawny literał JS (klucze/wartości w cudzysłowach).
        payload = json.dumps(self._pending_theme)
        self.view.page().runJavaScript(
            f"window.__termTheme && window.__termTheme({payload});")

    def _push_font(self):
        if self._pending_font is None:
            return
        family, size = self._pending_font
        fam = json.dumps(family)
        # Wspólny interfejs przekazuje rozmiar w PUNKTACH (jak QTermWidget/QFont),
        # a xterm.js liczy fontSize w PIKSELACH. Bez przeliczenia te same "13"
        # dają na WebTerminalu litery ~30% mniejsze niż na QTermWidget (objaw:
        # "czcionka nieczytelna w AppImage"). Przelicznik CSS: 1pt = 96/72 px.
        px = round(int(size) * 4 / 3)
        self.view.page().runJavaScript(
            f"window.__termFont && window.__termFont({fam}, {px});")

    def focus_terminal(self):
        self.view.setFocus()
        self.view.page().runJavaScript("window.__termFocus && window.__termFocus();")

    def set_mouse_mode(self, mode: str):
        """Ustaw tryb myszy terminala:
          'claude' = mysz do Claude (kółko przewija rozmowę, klik w menu, zaznaczanie z Shift),
          'select' = zaznaczanie/kopiowanie przeciągnięciem BEZ Shift.
        Przed gotowością frontu — buforuj (wyślemy w _on_frontend_ready)."""
        self._mouse_mode = 'select' if mode == 'select' else 'claude'
        if self._frontend_ready:
            self._push_mouse_mode()

    def _push_mouse_mode(self):
        mode = json.dumps(getattr(self, '_mouse_mode', 'claude'))
        self.view.page().runJavaScript(
            f"window.__termSetMouseMode && window.__termSetMouseMode({mode});")

    def is_available(self) -> bool:
        return _PTY_AVAILABLE

    # ==================== Drag & drop pliku na terminal ====================

    def _drop_paths_to_text(self, mime) -> str:
        """Zamień upuszczone lokalne pliki na tekst ścieżek (spacje → cudzysłów).

        Zwraca pusty string, jeśli nie ma lokalnych plików (np. upuszczono sam
        tekst albo zdalny URL) — wtedy nie ingerujemy i zdarzenie idzie dalej."""
        if not mime.hasUrls():
            return ""
        paths = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local:
                paths.append('"%s"' % local if " " in local else local)
        return " ".join(paths)

    def _install_drop_filter(self):
        """Wepnij filtr zdarzeń w widget renderujący QtWebEngine (focusProxy).

        Robione po załadowaniu strony i przy każdym pokazaniu zakładki — bo Qt
        potrafi PODMIENIĆ render widget (przy ukryciu/przeniesieniu między
        zakładkami/splitterami) i stary filtr przepada. Idempotentne: instaluje
        tylko gdy proxy się zmieniło."""
        proxy = self.view.focusProxy()
        if proxy is None or proxy is self._drop_filter_target:
            return
        proxy.installEventFilter(self)
        try:
            proxy.setAcceptDrops(True)
        except Exception:
            pass
        self._drop_filter_target = proxy
        _log("drop: filtr zdarzeń zainstalowany na render widget")

    def eventFilter(self, obj, event):
        """Przechwytuje upuszczenie PLIKU na terminal, zanim zrobi to Chromium.

        Tylko dla URL-i z lokalnymi plikami: akceptujemy DragEnter/Move i na Drop
        wpisujemy ścieżkę do PTY (jak natywny terminal). Inne zrzuty (np. tekst)
        puszczamy dalej do strony — tam obsłuży je JS w terminal.html."""
        et = event.type()
        if et in (QEvent.DragEnter, QEvent.DragMove):
            if event.mimeData().hasUrls() and self._drop_paths_to_text(event.mimeData()):
                event.acceptProposedAction()
                return True
        elif et == QEvent.Drop:
            text = self._drop_paths_to_text(event.mimeData())
            if text:
                self._write_pty(text)
                event.acceptProposedAction()
                self.focus_terminal()
                return True
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        # Render widget bywa tworzony/podmieniany po pokazaniu — (re)instaluj filtr.
        self._install_drop_filter()
        QTimer.singleShot(200, self._install_drop_filter)

    # ==================== Wewnętrzne ====================

    def _on_load_finished(self, ok: bool):
        _log(f"loadFinished ok={ok}")
        if not ok:
            self._show_failure_page(
                "Strona terminala nie załadowała się (loadFinished=false).")
            return
        # Strona wstała — jeśli xterm.js nie zgłosi gotowości w 10 s, to JS
        # umarł po cichu (np. brak pliku vendor) → pokaż komunikat zamiast
        # pustego pola. Watchdog tylko przy pierwszym ładowaniu (nie po setHtml).
        if not self._failure_shown and not self._frontend_ready:
            QTimer.singleShot(10000, self._frontend_watchdog)

    def _frontend_watchdog(self):
        if self._frontend_ready or self._failure_shown:
            return
        _log("watchdog: frontend_ready NIE nadeszło w 10 s od załadowania strony")
        self._show_failure_page(
            "Strona terminala załadowała się, ale xterm.js nie zgłosił "
            "gotowości w 10 sekund (prawdopodobnie błąd JavaScript).")

    def _on_render_terminated(self, status, exit_code):
        _log(f"renderProcessTerminated status={int(status)} exitCode={exit_code}")
        self._show_failure_page(
            f"Proces renderowania terminala zakończył się nieoczekiwanie "
            f"(status={int(status)}, kod={exit_code}).")

    def _show_failure_page(self, reason: str):
        """Zamiast martwego pustego pola — czytelny komunikat + ścieżka logu."""
        if self._failure_shown:
            return
        self._failure_shown = True
        _log(f"FAILURE: {reason}")
        html = (
            f"<html><body style='background:{theme.BG_CANVAS};color:{theme.TEXT};"
            "font-family:sans-serif;padding:18px'>"
            "<h3 style='color:#ef8080'>Terminal nie wystartował</h3>"
            f"<p>{reason}</p>"
            "<p style='color:#999'>Szczegóły w pliku:<br>"
            f"<code>{WEBTERMINAL_LOG}</code></p>"
            "</body></html>")
        self.view.setHtml(html)

    def _on_frontend_ready(self, cols, rows):
        _log(f"frontend_ready cols={cols} rows={rows}")
        self._frontend_ready = True
        self._pending_size = (cols, rows)
        # Render widget istnieje po załadowaniu strony — wepnij filtr drag&drop.
        self._install_drop_filter()
        QTimer.singleShot(300, self._install_drop_filter)
        # Wyślij zbuforowany motyw/czcionkę, gdy xterm.js jest już gotowy.
        self._push_theme()
        self._push_font()
        # Tryb myszy inny niż domyślny ('claude') — odtwórz po (re)starcie frontu.
        if getattr(self, '_mouse_mode', 'claude') != 'claude':
            self._push_mouse_mode()
        if self._proc is None:
            self._spawn()

    def _spawn(self):
        if not _PTY_AVAILABLE:
            _log("spawn: PTY niedostępne (import nie powiódł się)")
            hint = ("\r\n\x1b[33m[Terminal niedostępny: brak pakietu 'pywinpty' "
                    "— zainstaluj: pip install pywinpty]\x1b[0m\r\n") if is_windows() else \
                   "\r\n\x1b[33m[Terminal niedostępny: brak PTY na tym systemie]\x1b[0m\r\n"
            self._data_ready.emit(hint)
            return
        cols, rows = self._pending_size
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        # macOS/Linux: aplikacja z Findera/menu dostaje UBOGI PATH i nie widzi
        # narzędzi z profilu (Homebrew, nvm, node) → `claude` nie znajduje `node`.
        # Zaradczo: 1) login shell (-l), 2) dołożenie typowych lokalizacji do PATH.
        # Na Windows te ścieżki nie istnieją i PATH ustawia instalator — pomijamy.
        if not is_windows():
            for extra in ("/opt/homebrew/bin", "/usr/local/bin",
                          str(Path.home() / ".local" / "bin"),
                          str(Path.home() / ".npm-global" / "bin")):
                parts = env.get("PATH", "").split(os.pathsep)
                if extra not in parts:
                    env["PATH"] = (env.get("PATH", "") + os.pathsep + extra).strip(os.pathsep)
        argv = [self._shell]
        if not is_windows():
            argv.append("-l")  # login shell (Unix); na Windows powłoka jest non-login
        try:
            if _PTY_KIND == "winpty":
                # pywinpty: komenda jako string (powłoka bez argów); wymiary (rows, cols).
                self._proc = winpty.PtyProcess.spawn(
                    self._shell, dimensions=(rows, cols), env=env, cwd=self._cwd)
            else:
                self._proc = ptyprocess.PtyProcess.spawn(
                    argv, dimensions=(rows, cols), env=env, cwd=self._cwd)
        except Exception as e:
            _log(f"spawn: BŁĄD uruchamiania powłoki ({self._shell}): {e!r}")
            self._data_ready.emit(f"\r\n\x1b[31m[Nie udało się uruchomić powłoki: {e}]\x1b[0m\r\n")
            return
        _log(f"spawn: powłoka uruchomiona ({self._shell}, {cols}x{rows})")
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        # Opróżnij wejście zbuforowane przed startem powłoki (np. komenda
        # `claude` wysłana zanim xterm.js się załadował) — w kolejności wysłania.
        if self._pending_input:
            pending, self._pending_input = self._pending_input, []
            _log(f"spawn: opróżniam bufor wejścia ({len(pending)} fragm.)")
            for chunk in pending:
                self._write_pty(chunk)

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                data = self._proc.read(65536)
            except EOFError:
                break
            except Exception:
                break
            if not data:
                break
            # winpty zwraca str (już zdekodowany), ptyprocess — bytes.
            text = data if _PTY_KIND == "winpty" else self._decoder.decode(data)
            if text:
                if not self._logged_first_output:
                    self._logged_first_output = True
                    _log(f"PTY: pierwsze dane z powłoki ({len(text)} znaków)")
                self._data_ready.emit(text)
        _log("read_loop: koniec (proces powłoki zakończony)")
        self.finished.emit()

    def _push_to_js(self, text: str):
        # GUI thread: przekaż do xterm.js i wystaw do liczenia tokenów.
        self.bridge.output.emit(text)
        self.output_bytes.emit(text)

    def _on_finished_gui(self):
        try:
            self.bridge.closed.emit()
        except Exception:
            pass

    def _write_pty(self, data: str):
        if self._proc is None:
            # Powłoka jeszcze nie wstała — zbuforuj i wyślij po _spawn()
            # (inaczej write przepada po cichu; patrz _pending_input w __init__).
            self._pending_input.append(data)
            return
        try:
            # winpty pisze str, ptyprocess — bytes.
            self._proc.write(data if _PTY_KIND == "winpty" else data.encode("utf-8"))
        except Exception:
            pass

    def _resize_pty(self, cols, rows):
        _log(f"resize: {cols}x{rows}")
        self._pending_size = (cols, rows)
        if self._proc is not None:
            try:
                self._proc.setwinsize(rows, cols)
            except Exception:
                pass

    def shutdown(self):
        self._stop.set()
        if self._proc is not None:
            try:
                if _PTY_KIND == "winpty":
                    self._proc.terminate()  # winpty.terminate() nie przyjmuje force=
                else:
                    self._proc.terminate(force=True)
            except Exception:
                pass
            self._proc = None

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


# ==================== Mini-demo (test na Linuksie) ====================
# Uruchom:  source venv/bin/activate && python3 src/gui/web_terminal.py
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    # QtWebEngine wymaga współdzielenia kontekstu OpenGL — ustawić PRZED QApplication.
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    term = WebTerminal()
    term.resize(900, 560)
    term.setWindowTitle("WebTerminal demo (M2.1)")
    term.show()
    sys.exit(app.exec_())
