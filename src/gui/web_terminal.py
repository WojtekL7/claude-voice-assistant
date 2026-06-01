"""
Claude Voice Assistant - WebTerminal (Etap M2.1)

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
import codecs
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.platform_utils import default_shell, is_windows

# PTY: ptyprocess to wariant uniksowy (Linux/macOS). Windows = ConPTY w przyszłości.
try:
    import ptyprocess
    _PTY_AVAILABLE = not is_windows()
except Exception:
    _PTY_AVAILABLE = False

ASSET_DIR = Path(__file__).parent.parent / "assets" / "web"


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
        self._frontend_ready = False
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
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

        self.view.load(QUrl.fromLocalFile(str(ASSET_DIR / "terminal.html")))

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

    def set_theme(self, background: str, foreground: str):
        self.view.page().runJavaScript(
            f"window.__termTheme && window.__termTheme('{background}','{foreground}');")

    def focus_terminal(self):
        self.view.setFocus()
        self.view.page().runJavaScript("window.__termFocus && window.__termFocus();")

    def is_available(self) -> bool:
        return _PTY_AVAILABLE

    # ==================== Wewnętrzne ====================

    def _on_frontend_ready(self, cols, rows):
        self._frontend_ready = True
        self._pending_size = (cols, rows)
        if self._proc is None:
            self._spawn()

    def _spawn(self):
        if not _PTY_AVAILABLE:
            # TODO(Windows): backend ConPTY (pywinpty) zamiast tego komunikatu.
            self._data_ready.emit(
                "\r\n\x1b[33m[Terminal niedostępny: brak PTY na tym systemie]\x1b[0m\r\n")
            return
        cols, rows = self._pending_size
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        try:
            self._proc = ptyprocess.PtyProcess.spawn(
                [self._shell], dimensions=(rows, cols), env=env, cwd=self._cwd)
        except Exception as e:
            self._data_ready.emit(f"\r\n\x1b[31m[Nie udało się uruchomić powłoki: {e}]\x1b[0m\r\n")
            return
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

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
            text = self._decoder.decode(data)
            if text:
                self._data_ready.emit(text)
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
        if self._proc is not None:
            try:
                self._proc.write(data.encode("utf-8"))
            except Exception:
                pass

    def _resize_pty(self, cols, rows):
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
