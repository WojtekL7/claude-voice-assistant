"""
Vibe Coding Assistant - Claude Code Bridge
Handles communication with Claude Code CLI using --print mode.

Implementacja na QProcess (PyQt5) zamiast subprocess.Popen + threading.Thread.

DLACZEGO QProcess:
- Wcześniejsza wersja używała subprocess.Popen + osobnego wątku tła i czytała
  stdout BLOKUJĄCO (for line in stdout). Callback `on_output` był wtedy
  wywoływany z wątku tła i bezpośrednio modyfikował widgety Qt — to jest
  niewspierane przez PyQt (cross-thread GUI access = undefined behavior:
  deadlocki, crashe, czasem zamarzanie całego systemu pod XWayland).
- QProcess emituje sygnały (readyReadStandardOutput, finished) NATYWNIE z
  wątku Qt event loopa — odbiorca zawsze działa w głównym GUI threadzie.
- Brak blokującego I/O, brak wątków własnego zarządzania, brak deadlocku
  pipe buffer'a (subprocess.PIPE blokuje po 65KB jeśli nikt nie czyta).
"""
import time
from typing import Callable, Optional
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, pyqtSignal

# Debug log file
DEBUG_LOG = Path.home() / ".vibe-coding-assistant" / "debug.log"


def debug_log(msg: str):
    """Write debug message to log file."""
    try:
        with open(DEBUG_LOG, 'a') as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


class ClaudeBridge(QObject):
    """
    Bridge for communicating with Claude Code CLI using QProcess.

    Sygnały (emitowane w GUI threadzie, bezpieczne dla bezpośredniej
    modyfikacji widgetów):
    - output_received(str) — fragment odpowiedzi w czasie rzeczywistym
    - response_complete(str) — pełna odpowiedź po zakończeniu procesu
    - error_occurred(str) — błąd uruchomienia/wykonania
    """

    output_received = pyqtSignal(str)
    response_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, command: str = "claude", parent=None):
        super().__init__(parent)
        self.command = command
        self.running = False
        self.process: Optional[QProcess] = None
        self._response_buffer = ""

    def start(self) -> bool:
        """Initialize the bridge (check if claude command exists).

        Używa QProcess synchronicznie (z timeoutem) tylko do sprawdzenia
        wersji — to jednorazowe wywołanie przy starcie, krótkie, więc OK.
        """
        try:
            probe = QProcess()
            probe.start(self.command, ['--version'])
            # Czekamy max 10s na zakończenie. To jednorazowo przy starcie.
            if not probe.waitForFinished(10_000):
                probe.kill()
                self.error_occurred.emit(
                    f"Timeout: '{self.command} --version' nie odpowiedział w 10s."
                )
                return False
            version_out = bytes(probe.readAllStandardOutput()).decode(errors='ignore').strip()
            debug_log(f"Claude version: {version_out}")
            self.running = True
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to start Claude Code: {e}")
            debug_log(f"start() error: {e}")
            return False

    def stop(self):
        """Stop any running process."""
        self.running = False
        self._terminate_current()

    def _terminate_current(self):
        """Bezpieczne zatrzymanie aktualnego procesu (jeśli istnieje)."""
        if self.process is not None:
            try:
                if self.process.state() != QProcess.NotRunning:
                    self.process.terminate()
                    if not self.process.waitForFinished(2000):
                        self.process.kill()
                        self.process.waitForFinished(1000)
            except Exception as e:
                debug_log(f"_terminate_current error: {e}")
            self.process.deleteLater()
            self.process = None

    def send(self, text: str):
        """Send text to Claude Code and stream response back via signals."""
        debug_log(f"send() called with: {text[:100]}")

        if not self.running:
            debug_log("Not running, cannot send")
            return

        # Zatrzymaj poprzedni proces jeśli wciąż działa (np. user wysłał
        # nową wiadomość zanim poprzednia odpowiedź się skończyła).
        self._terminate_current()

        self._response_buffer = ""
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._on_ready_read_stdout)
        self.process.readyReadStandardError.connect(self._on_ready_read_stderr)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_process_error)

        self.output_received.emit("⏳ Processing...\n")
        debug_log(f"Starting QProcess: {self.command} --print <text>")
        self.process.start(self.command, ['--print', text])

    def _on_ready_read_stdout(self):
        """Slot wywoływany w GUI threadzie gdy są nowe dane na stdout."""
        if self.process is None:
            return
        try:
            chunk = bytes(self.process.readAllStandardOutput()).decode(
                'utf-8', errors='ignore'
            )
        except Exception as e:
            debug_log(f"stdout decode error: {e}")
            return
        if not chunk:
            return
        self._response_buffer += chunk
        debug_log(f"Output chunk: {chunk[:100]}")
        self.output_received.emit(chunk)

    def _on_ready_read_stderr(self):
        """Slot dla stderr — logujemy ale nie traktujemy jako fatal error
        (Claude Code może wypisywać warningi do stderr)."""
        if self.process is None:
            return
        try:
            chunk = bytes(self.process.readAllStandardError()).decode(
                'utf-8', errors='ignore'
            )
            if chunk.strip():
                debug_log(f"Stderr: {chunk[:200]}")
        except Exception as e:
            debug_log(f"stderr decode error: {e}")

    def _on_finished(self, exit_code: int, exit_status):
        """Slot wywoływany gdy proces się zakończył."""
        debug_log(
            f"Process finished: exit_code={exit_code}, "
            f"status={exit_status}, response_len={len(self._response_buffer)}"
        )
        if self._response_buffer.strip():
            self.response_complete.emit(self._response_buffer)
        # Sprzątanie referencji — sam proces zostanie usunięty przez
        # deleteLater() przy następnym send() lub stop().
        # Tutaj nie wołamy deleteLater bo jesteśmy w slocie tego procesu.

    def _on_process_error(self, error):
        """Slot dla błędów QProcess (np. FailedToStart, Crashed)."""
        msg_map = {
            QProcess.FailedToStart: f"Nie udało się uruchomić '{self.command}'. Czy Claude Code jest zainstalowany?",
            QProcess.Crashed: "Proces Claude Code crashował.",
            QProcess.Timedout: "Timeout procesu Claude Code.",
            QProcess.WriteError: "Błąd zapisu do procesu Claude Code.",
            QProcess.ReadError: "Błąd odczytu z procesu Claude Code.",
        }
        msg = msg_map.get(error, f"Nieznany błąd QProcess: {error}")
        debug_log(f"Process error: {msg}")
        self.error_occurred.emit(msg)

    def send_interrupt(self):
        """Interrupt current operation."""
        debug_log("send_interrupt() called")
        self._terminate_current()

    def is_running(self) -> bool:
        """Check if bridge is active."""
        return self.running


class ClaudeBridgeAsync:
    """
    Adapter: zachowuje stare API callback-based dla kompatybilności z
    main_window.py (connect_output/connect_response/connect_error), ale
    pod spodem używa QObject+QProcess. Sygnały Qt są mapowane na listy
    callbacków.

    Callbacki są wywoływane w GUI threadzie (bo sygnały Qt domyślnie
    używają AutoConnection → DirectConnection gdy emitter i receiver są
    w tym samym threadzie, a tu QProcess i adapter są w GUI threadzie).
    """

    def __init__(self, command: str = "claude"):
        self.bridge = ClaudeBridge(command)
        self._output_callbacks = []
        self._response_callbacks = []
        self._error_callbacks = []

        self.bridge.output_received.connect(self._dispatch_output)
        self.bridge.response_complete.connect(self._dispatch_response)
        self.bridge.error_occurred.connect(self._dispatch_error)

    def connect_output(self, callback: Callable[[str], None]):
        self._output_callbacks.append(callback)

    def connect_response(self, callback: Callable[[str], None]):
        self._response_callbacks.append(callback)

    def connect_error(self, callback: Callable[[str], None]):
        self._error_callbacks.append(callback)

    def _dispatch_output(self, text: str):
        for cb in self._output_callbacks:
            try:
                cb(text)
            except Exception as e:
                debug_log(f"Error in output callback: {e}")

    def _dispatch_response(self, text: str):
        for cb in self._response_callbacks:
            try:
                cb(text)
            except Exception as e:
                debug_log(f"Error in response callback: {e}")

    def _dispatch_error(self, text: str):
        for cb in self._error_callbacks:
            try:
                cb(text)
            except Exception as e:
                debug_log(f"Error in error callback: {e}")

    def start(self) -> bool:
        return self.bridge.start()

    def stop(self):
        self.bridge.stop()

    def send(self, text: str):
        self.bridge.send(text)

    def send_interrupt(self):
        self.bridge.send_interrupt()

    def is_running(self) -> bool:
        return self.bridge.is_running()
