"""
Vibe Coding Assistant - Wspólny interfejs terminala + fabryka backendów (Etap M2.2)

Cel: dać reszcie aplikacji JEDNĄ „deskę rozdzielczą" terminala, niezależną od
tego, który silnik pracuje pod spodem:

  * QTermWidgetBackend  — linuksowy QTermWidget (dotychczasowy, domyślny na Linuksie)
  * WebTerminalBackend  — xterm.js + QtWebEngine + PTY (wieloplatformowy; macOS/Windows
                          wymuszony, na Linuksie opcjonalny pod flagą CVA_WEBTERMINAL=1)

Fabryka `create_terminal_backend(...)` sama wybiera właściwy silnik wg systemu.

⚠️ M2.2 jest CZYSTO DOKŁADAJĄCY: ten moduł nie jest jeszcze importowany przez
`agent_tab.py` ani `main_window.py`. Wpięcie do zakładek to M2.3, pełne mapowanie
kolorów/skórek i czcionek do xterm.js to M2.4 (oznaczone TODO(M2.4)).

Kontrakt `TerminalBackend` pokrywa WSZYSTKIE operacje na terminalu używane dziś
przez AgentTab i MainWindow (sprawdzone w obu plikach):
  set_shell_program / set_working_directory / start_shell_program / send_text /
  selected_text / copy_selection / clear / set_font / set_color_scheme /
  focus_terminal / shutdown  + sygnały output_received(str) i finished().

Backend jest QObject-em, który OWIJA właściwy QWidget terminala. Widget do
wstawienia w splitter zwraca właściwość `.widget`. Dzięki temu AgentTab w M2.3
będzie wołał metody backendu, a do layoutu dorzuci `backend.widget`.
"""
import os
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, QEvent, pyqtSignal
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QFont, QClipboard

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.platform_utils import is_macos, is_windows, default_shell

# QTermWidget jest tylko-Linux. Import strażniczy — na macOS/Windows go nie ma,
# i to jest OK: fabryka i tak wybierze tam WebTerminal.
try:
    from QTermWidget import QTermWidget
    QTERMWIDGET_AVAILABLE = True
except ImportError:
    QTERMWIDGET_AVAILABLE = False


# Stylizacja paska przewijania QTermWidget — przeniesiona 1:1 z AgentTab.activate(),
# żeby M2.3 było czystą podmianą (backend odtwarza dotychczasowy wygląd terminala).
_QTERMWIDGET_SCROLLBAR_QSS = """
    QTermWidget {
        border: none;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 12px;
        margin: 2px;
    }
    QScrollBar::handle:vertical {
        background: #3a2a5a;
        border-radius: 5px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #6b46a8;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: transparent;
    }
"""


def _xterm_theme_from_colors(colors: dict) -> dict:
    """Zbuduj motyw xterm.js (ITheme) ze słownika skórki.

    Używa DOKŁADNIE tych samych kluczy, co wariant QTermWidget w
    MainWindow._apply_terminal_colors (terminal_bg/fg + terminal_color_0..7 i ich
    warianty _bright) — dzięki temu oba silniki pokazują te same kolory skórki.
    """
    c = colors or {}

    def g(key, default):
        return c.get(key, default)

    bg = g('terminal_bg', '#300A24')
    fg = g('terminal_fg', '#EEEEEC')
    return {
        'background': bg,
        'foreground': fg,
        'cursor': fg,
        'cursorAccent': bg,
        'selectionBackground': g('hover_color', '#6a2a5a'),
        'black':         g('terminal_color_0', '#2E3436'),
        'red':           g('terminal_color_1', '#CC0000'),
        'green':         g('terminal_color_2', '#4E9A06'),
        'yellow':        g('terminal_color_3', '#C4A000'),
        'blue':          g('terminal_color_4', '#3465A4'),
        'magenta':       g('terminal_color_5', '#75507B'),
        'cyan':          g('terminal_color_6', '#06989A'),
        'white':         g('terminal_color_7', '#D3D7CF'),
        'brightBlack':   g('terminal_color_0_bright', '#555753'),
        'brightRed':     g('terminal_color_1_bright', '#EF2929'),
        'brightGreen':   g('terminal_color_2_bright', '#8AE234'),
        'brightYellow':  g('terminal_color_3_bright', '#FCE94F'),
        'brightBlue':    g('terminal_color_4_bright', '#729FCF'),
        'brightMagenta': g('terminal_color_5_bright', '#AD7FA8'),
        'brightCyan':    g('terminal_color_6_bright', '#34E2E2'),
        'brightWhite':   g('terminal_color_7_bright', '#EEEEEC'),
    }


# ==================== Wspólny kontrakt ====================

class TerminalBackend(QObject):
    """Wspólna „deska rozdzielcza" terminala.

    Sygnały (identyczne dla obu silników):
      output_received(object) — porcja CZYSTEGO już zdekodowanego tekstu wyjścia
                                (string). MainWindow używa jej do liczenia tokenów.
                                Uwaga: to NIE jest źródło auto-czytania głosem —
                                auto-czytanie idzie z dziennika sesji (Droga A).
      finished()              — proces powłoki w terminalu zakończył się.

    Podklasa MUSI nadpisać metody oznaczone NotImplementedError oraz właściwość
    `widget`. Świadomie NIE używamy ABCMeta — kolidowałaby z metaklasą QObject.
    """

    output_received = pyqtSignal(object)
    finished = pyqtSignal()

    # ----- dostęp do widgetu (do wstawienia w layout/splitter) -----
    @property
    def widget(self) -> QWidget:
        raise NotImplementedError

    # ----- powłoka / cykl życia -----
    def set_shell_program(self, path: str):
        raise NotImplementedError

    def set_working_directory(self, path: str):
        raise NotImplementedError

    def start_shell_program(self):
        raise NotImplementedError

    def send_text(self, text: str):
        raise NotImplementedError

    # ----- zaznaczanie / schowek -----
    def selected_text(self) -> str:
        raise NotImplementedError

    def active_selection(self) -> str:
        """Zaznaczenie do CZYTANIA na głos — tylko jeśli AKTUALNE/świeże.

        Różni się od selected_text() (używanego przez KOPIOWANIE): „czytaj
        ostatnią" NIE może czytać starego, „przyklejonego" zaznaczenia (bug
        WebTerminala — lepkie `_selection` zostawało duchem i wypierało odczyt
        najnowszej odpowiedzi). Domyślnie = selected_text (bezpieczny fallback);
        backendy nadpisują wg swojej semantyki."""
        return self.selected_text()

    def copy_selection(self):
        raise NotImplementedError

    def clear(self):
        """Wyczyść ekran terminala (uruchom `clear` w powłoce)."""
        self.send_text("clear\n")

    # ----- wygląd -----
    def set_font(self, family: str, size: int):
        raise NotImplementedError

    def set_color_scheme(self, scheme_dir=None, scheme_name=None,
                         background=None, foreground=None, colors=None):
        """Zastosuj kolory terminala.

        QTermWidget: używa pary (scheme_dir, scheme_name) — wczytuje plik .colorscheme.
        WebTerminal: buduje pełny motyw xterm.js ze słownika `colors` (skórka);
        gdy go brak — bierze samo (background, foreground).
        """
        raise NotImplementedError

    def focus_terminal(self):
        raise NotImplementedError

    def set_mouse_mode(self, mode: str):
        """Tryb myszy: 'claude' (kółko przewija rozmowę, zaznaczanie z Shift) albo
        'select' (zaznaczanie/kopiowanie bez Shift). Domyślnie no-op — dotyczy
        WebTerminala; QTermWidget obsługuje mysz natywnie (Shift zaznacza)."""
        pass

    # ----- zamknięcie -----
    def shutdown(self):
        """Zatrzymaj proces/wątki terminala (bezpieczne do wielokrotnego wołania)."""
        pass


# ==================== Adapter: QTermWidget (Linux) ====================

class QTermWidgetBackend(TerminalBackend):
    """Owija linuksowy QTermWidget, tłumacząc go na wspólny kontrakt.

    Konfiguracja (czcionka, scrollbar, historia, flow control, QSS) odtwarza
    dokładnie to, co dziś robi AgentTab.activate() — by M2.3 było podmianą 1:1.
    """

    def __init__(self, working_directory: str, shell: str,
                 font_family: str = "Ubuntu Mono", font_size: int = 13,
                 parent=None):
        super().__init__(parent)
        if not QTERMWIDGET_AVAILABLE:
            # Nie powinno się zdarzyć (fabryka pilnuje), ale chronimy się jawnie.
            raise RuntimeError("QTermWidget niedostępny na tym systemie")

        self._term = QTermWidget(0)
        self._term.setShellProgram(shell)
        self._term.setWorkingDirectory(working_directory)

        self.set_font(font_family, font_size)

        self._term.setScrollBarPosition(QTermWidget.ScrollBarRight)
        self._term.setTerminalOpacity(1.0)
        self._term.setHistorySize(10000)
        self._term.setFlowControlEnabled(False)
        self._term.setFlowControlWarningEnabled(False)
        self._term.setTerminalSizeHint(False)
        self._term.setStyleSheet(_QTERMWIDGET_SCROLLBAR_QSS)

        # receivedData (PyQt5) niesie str (QString), NIE QByteArray — normalizujemy
        # w _on_received i wystawiamy ujednolicony sygnał output_received(str).
        self._term.receivedData.connect(self._on_received)
        self._term.finished.connect(self.finished)

        # Zaznaczenie tekstu — pamięć podręczna. Chwytamy zaznaczony tekst
        # W MOMENCIE puszczenia myszy (sygnał `copyAvailable(True)`), żeby
        # kopiowanie/odczyt miały pewne źródło, gdyby późniejszy odczyt na żywo
        # zwrócił pustkę. UWAGA: gdy program w terminalu (Claude Code) używa myszy
        # do swojego interfejsu, zwykłe przeciągnięcie NIE zaznacza — trzeba
        # przytrzymać Shift (standard terminali). Wtedy to wszystko działa.
        self._cached_selection = ""
        try:
            self._term.copyAvailable.connect(self._on_copy_available)
        except Exception:
            pass  # starszy QTermWidget bez tego sygnału — zostaje sam odczyt na żywo

        # Most dla POLSKICH liter wpisywanych WPROST w terminalu (AltGr/iBus).
        # QTermWidget (Konsole) gubi znaki narodowe składane prawym Altem lub
        # metodą wprowadzania — docierają jako znak spoza ASCII w KeyPress albo
        # jako commit InputMethod, a wewnętrzna obsługa NIE przekazuje ich do
        # PTY (objaw: 'żółć' nie wchodzi w terminalu, choć w polu na dole tak).
        # Przechwytujemy je filtrem i wysyłamy wprost przez sendText (UTF-8) —
        # tą samą pewną drogą co pole na dole. Filtr wisi na widgecie ORAZ na
        # jego focusProxy (to ON dostaje zdarzenia klawiatury).
        self._term.installEventFilter(self)
        _fp = self._term.focusProxy()
        if _fp is not None:
            _fp.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Przepuść polskie/narodowe znaki (spoza ASCII) wprost do PTY.

        Ryzyko zerowe: reagujemy WYŁĄCZNIE na drukowalne znaki spoza ASCII
        (ą, ż, ó… — dziś i tak nieobsługiwane w terminalu) oraz na commit
        metody wprowadzania. ASCII, Enter, strzałki, Ctrl+C, skróty — nietknięte
        (płyną normalną drogą QTermWidget)."""
        try:
            et = event.type()
            if et == QEvent.KeyPress:
                text = event.text()
                if text and text.isprintable() and any(ord(c) > 127 for c in text):
                    self._term.sendText(text)
                    return True
            elif et == QEvent.InputMethod:
                commit = event.commitString()
                if commit:
                    self._term.sendText(commit)
                    return True
        except Exception:
            pass  # nigdy nie blokuj pętli zdarzeń z powodu tego mostu
        return super().eventFilter(obj, event)

    @property
    def widget(self) -> QWidget:
        return self._term

    def _on_received(self, data):
        # QTermWidget (PyQt5) emituje receivedData jako str (QString → str),
        # a NIE QByteArray. Wcześniejsze `bytes(data)` na stringu rzucało
        # TypeError ("string argument without an encoding"); wyjątek był po
        # cichu połykany → output_received nigdy nie leciało → cały odbiór
        # wyjścia terminala milczał (m.in. licznik tokenów stał w miejscu na
        # Linuksie od refaktoru backendu M2.3). Obsługujemy oba typy defensywnie.
        try:
            if isinstance(data, str):
                text = data
            elif hasattr(data, "data"):              # QByteArray
                text = bytes(data.data()).decode("utf-8", errors="ignore")
            else:                                    # bytes / bytearray
                text = bytes(data).decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        if text:
            self.output_received.emit(text)

    def set_shell_program(self, path: str):
        self._term.setShellProgram(path)

    def set_working_directory(self, path: str):
        self._term.setWorkingDirectory(path)

    def start_shell_program(self):
        self._term.startShellProgram()

    def send_text(self, text: str):
        self._term.sendText(text)

    def _on_copy_available(self, available: bool):
        """Sygnał QTermWidget: zmieniła się dostępność zaznaczenia (mysz puszczona).
        Gdy jest co kopiować — zapamiętaj tekst od razu (najpewniejszy moment)."""
        if available:
            try:
                self._cached_selection = self._term.selectedText() or ""
            except Exception:
                self._cached_selection = ""
        else:
            self._cached_selection = ""

    def selected_text(self) -> str:
        """Zaznaczony tekst: najpierw świeży odczyt, w razie pustki — zapamiętany."""
        live = ""
        try:
            live = self._term.selectedText() or ""
        except Exception:
            live = ""
        return live or self._cached_selection

    def active_selection(self) -> str:
        """Tylko ŻYWE zaznaczenie (BEZ fallbacku na _cached_selection, którego
        używa kopiowanie). QTermWidget czyści zaznaczenie sam po przerysowaniu,
        więc gdy nic nie jest teraz zaznaczone → '' → „czytaj ostatnią" idzie do
        najnowszej odpowiedzi z dziennika, nie do starego zaznaczenia."""
        try:
            return self._term.selectedText() or ""
        except Exception:
            return ""

    def copy_selection(self):
        """Skopiuj zaznaczenie do schowka. Pewniej niż `copyClipboard()`:
        wprost przez Qt do schowka „Clipboard" (Ctrl+V) ORAZ „Selection"
        (środkowy przycisk) — działa też na Wayland/GNOME. Zwraca liczbę
        skopiowanych znaków (0 = brak zaznaczenia) do podglądu w pasku statusu."""
        text = self.selected_text()
        if text:
            cb = QApplication.clipboard()
            cb.setText(text, QClipboard.Clipboard)
            if cb.supportsSelection():
                cb.setText(text, QClipboard.Selection)
        else:
            # Brak zaznaczenia w modelu — ostatnia próba przez natywną kopię.
            try:
                self._term.copyClipboard()
            except Exception:
                pass
        return len(text)

    def set_font(self, family: str, size: int):
        font = QFont(family, size)
        font.setStyleHint(QFont.Monospace)
        self._term.setTerminalFont(font)

    def set_color_scheme(self, scheme_dir=None, scheme_name=None,
                         background=None, foreground=None, colors=None):
        # QTermWidget wczytuje plik .colorscheme; `colors` ignoruje (to ścieżka
        # WebTerminala).
        if scheme_dir and scheme_name:
            self._term.addCustomColorSchemeDir(str(scheme_dir))
            self._term.setColorScheme(scheme_name)
            self._term.update()

    def focus_terminal(self):
        self._term.setFocus()

    def shutdown(self):
        # QTermWidget sprząta proces przy zniszczeniu widgetu — nic ekstra.
        pass


# ==================== Adapter: WebTerminal (wieloplatformowy) ====================

class WebTerminalBackend(TerminalBackend):
    """Owija WebTerminal (xterm.js + QtWebEngine + PTY).

    Import WebTerminal jest LENIWY (w konstruktorze) — żeby samo zaimportowanie
    tego modułu nie ściągało QtWebEngine na ścieżce linuksowej (QTermWidget).
    """

    def __init__(self, working_directory: str, shell: str,
                 font_family: str = "Ubuntu Mono", font_size: int = 13,
                 parent=None):
        super().__init__(parent)
        from gui.web_terminal import WebTerminal  # lazy: nie ciągnij QtWebEngine bez potrzeby

        self._term = WebTerminal(parent)
        if shell:
            self._term.set_shell_program(shell)
        if working_directory:
            self._term.set_working_directory(working_directory)
        self._font = (font_family, font_size)
        self._term.set_font(font_family, font_size)  # zbuforuje do frontend_ready

        # WebTerminal.output_bytes jest typu str, a nasz output_received(object)
        # — bezpośrednie połączenie sygnał-w-sygnał Qt odrzuca (niezgodne typy),
        # więc mostkujemy przez slot, który re-emituje.
        self._term.output_bytes.connect(self._forward_output)
        self._term.finished.connect(self.finished)

    def _forward_output(self, text):
        self.output_received.emit(text)

    @property
    def widget(self) -> QWidget:
        return self._term

    def set_shell_program(self, path: str):
        self._term.set_shell_program(path)

    def set_working_directory(self, path: str):
        self._term.set_working_directory(path)

    def start_shell_program(self):
        self._term.start_shell_program()

    def send_text(self, text: str):
        self._term.send_text(text)

    def selected_text(self) -> str:
        return self._term.selected_text()

    def active_selection(self) -> str:
        # WebTerminal sam pilnuje świeżości (lepkie _selection ma znacznik czasu).
        return self._term.active_selection()

    def copy_selection(self):
        # Schowek przez Qt działa wszędzie (w tym macOS/Windows).
        text = self.selected_text() or ""
        QApplication.clipboard().setText(text)
        return len(text)

    def set_font(self, family: str, size: int):
        self._font = (family, size)
        self._term.set_font(family, size)

    def set_color_scheme(self, scheme_dir=None, scheme_name=None,
                         background=None, foreground=None, colors=None):
        # Pełny motyw ze skórki; awaryjnie samo tło/tekst.
        if colors:
            self._term.set_theme(_xterm_theme_from_colors(colors))
        elif background and foreground:
            self._term.set_theme({'background': background, 'foreground': foreground})

    def focus_terminal(self):
        self._term.focus_terminal()

    def set_mouse_mode(self, mode: str):
        self._term.set_mouse_mode(mode)

    def shutdown(self):
        self._term.shutdown()


# ==================== Wybór backendu + fabryka ====================

def selected_backend_kind() -> str:
    """Który silnik zostanie użyty: 'qtermwidget' albo 'webterminal'.

    Reguły:
      * macOS / Windows                 → 'webterminal' (QTermWidget tam nie istnieje)
      * Linux + CVA_WEBTERMINAL=1        → 'webterminal' (tryb testowy)
      * Linux bez dostępnego QTermWidget → 'webterminal' (bezpieczna droga zapasowa)
      * Linux (domyślnie)                → 'qtermwidget' (bez zmian w zachowaniu)
    """
    if is_macos() or is_windows():
        return "webterminal"
    if os.environ.get("CVA_WEBTERMINAL") == "1":
        return "webterminal"
    if not QTERMWIDGET_AVAILABLE:
        return "webterminal"
    return "qtermwidget"


def webengine_required() -> bool:
    """Czy w tym uruchomieniu użyjemy QtWebEngine (WebTerminal).

    Używane w M2.3 przez main.py do ustawienia Qt.AA_ShareOpenGLContexts PRZED
    utworzeniem QApplication (gotcha QtWebEngine)."""
    return selected_backend_kind() == "webterminal"


def create_terminal_backend(working_directory: str, shell: str = None,
                            font_family: str = "Ubuntu Mono", font_size: int = 13,
                            parent=None) -> TerminalBackend:
    """Stwórz właściwy backend terminala dla bieżącego systemu.

    Parametry odpowiadają temu, co AgentTab ustawia dziś na QTermWidget
    (katalog roboczy, powłoka, czcionka).
    """
    if shell is None:
        shell = default_shell()

    kind = selected_backend_kind()
    if kind == "qtermwidget":
        return QTermWidgetBackend(working_directory, shell, font_family, font_size, parent)
    return WebTerminalBackend(working_directory, shell, font_family, font_size, parent)
