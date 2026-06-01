"""
Claude Voice Assistant - Platform utilities (Linux / macOS / Windows)

Jedno miejsce rozstrzygające różnice między systemami operacyjnymi: backend Qt,
Input Method, natywny pasek menu, domyślna powłoka, ścieżka do CLI `claude`,
katalog transkryptów oraz identyfikator platformy dla auto-aktualizacji.

Założenie wieloplatformowe od fundamentu (Etap M1): kod aplikacji NIE rozsiewa
`if linux/mac/windows` po całym projekcie — pyta ten moduł. Windows jest tu
obecny jako pełnoprawny obywatel; miejsca wymagające osobnej implementacji
(np. ConPTY zamiast `pty` w terminalu) są oznaczone `TODO(Windows)`.
"""
import os
import sys
import shutil
import platform
from pathlib import Path


# ==================== Rozpoznanie systemu ====================

def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def os_key() -> str:
    """Krótki klucz systemu: 'macos' | 'windows' | 'linux'."""
    if is_macos():
        return "macos"
    if is_windows():
        return "windows"
    return "linux"


def arch() -> str:
    """Architektura znormalizowana: 'arm64' | 'x64' | (surowa nazwa)."""
    m = (platform.machine() or "").lower()
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("x86_64", "amd64"):
        return "x64"
    return m or "unknown"


# ==================== Qt / środowisko ====================

def configure_qt_environment():
    """Ustaw zmienne środowiskowe Qt zależne od systemu.

    MUSI być wołane na samym początku main.py — PRZED utworzeniem QApplication
    (a najlepiej przed importem PyQt5), bo Qt czyta te zmienne przy starcie.
    """
    if is_linux():
        # X11 (XWayland pod sesją Wayland) domyślnie — historycznie naprawiało
        # pozycjonowanie menu; przełącznik VOICE_USE_WAYLAND=1 wymusza natywny
        # Wayland. Patrz DIAGNOSE-ENTER-FIX.md.
        if os.environ.get("VOICE_USE_WAYLAND") != "1":
            os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        # iBus pod XWayland "zjada" Enter, gdy w terminalu pojawiają się
        # podpowiedzi Claude Code → wyłączamy Input Method TYLKO na Linuksie.
        os.environ.setdefault("QT_IM_MODULE", "none")
    # macOS: backend 'cocoa' i IM systemowy są poprawne — nic nie ruszamy.
    # Windows: backend 'windows' domyślny — nic nie ustawiamy.


def use_native_menu_bar() -> bool:
    """Czy używać natywnego paska menu systemu (u góry ekranu).

    Windows: TAK (menu w oknie jest natywne i poprawne).
    macOS: NIE — natywny pasek u góry ekranu potrafił całkowicie znikać w tej
      aplikacji (PyQt5), blokując dostęp do ustawień. Używamy menu WBUDOWANEGO
      w okno (pod tytułem) — zawsze widoczne i odporne na ten problem.
    Linux: NIE (pozycjonowanie pod XWayland bywa błędne).
    """
    return is_windows()


def prefer_webengine_terminal() -> bool:
    """Czy to uruchomienie najpewniej użyje WebTerminala (QtWebEngine).

    Używane w main.py do ustawienia Qt.AA_ShareOpenGLContexts ORAZ wczesnego
    importu QtWebEngine PRZED utworzeniem QApplication (oba wymagane przez
    QtWebEngine). Celowo LEKKA — nie importuje QTermWidget ani WebTerminala,
    by main.py mógł ją wywołać u samego startu.

    Reguła: macOS/Windows → zawsze (tam terminalem jest WebTerminal);
    Linux → tylko gdy CVA_WEBTERMINAL=1 (tryb testowy). Pełną, dokładną decyzję
    (z uwzględnieniem braku QTermWidget) podejmuje
    terminal_backend.selected_backend_kind() już po starcie QApplication.
    """
    if is_macos() or is_windows():
        return True
    return os.environ.get("CVA_WEBTERMINAL") == "1"


# ==================== Powłoka / proces ====================

def default_shell() -> str:
    """Ścieżka domyślnej powłoki dla wbudowanego terminala."""
    if is_windows():
        # TODO(Windows): preferowany PowerShell + backend ConPTY (M2-Windows).
        return os.environ.get("COMSPEC") or "powershell.exe"
    if is_macos():
        # macOS domyślnie zsh; uszanuj $SHELL użytkownika, jeśli ustawiony.
        return os.environ.get("SHELL") or "/bin/zsh"
    # Linux
    return os.environ.get("SHELL") or "/usr/bin/bash"


def find_claude_command() -> str:
    """Znajdź CLI `claude` niezależnie od systemu (PATH + typowe lokalizacje)."""
    found = shutil.which("claude")
    if found:
        return found

    home = Path.home()
    candidates = [home / ".local" / "bin" / "claude"]
    if is_macos():
        candidates += [Path("/opt/homebrew/bin/claude"),
                      Path("/usr/local/bin/claude")]
    elif is_windows():
        candidates += [home / "AppData" / "Roaming" / "npm" / "claude.cmd",
                      home / "AppData" / "Roaming" / "npm" / "claude"]
    else:  # Linux
        candidates += [Path("/usr/bin/claude"), Path("/usr/local/bin/claude")]

    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            continue
    # Fallback: gołe 'claude' (powłoka znajdzie je na PATH przy uruchomieniu).
    return "claude"


# ==================== Ścieżki danych ====================

def claude_projects_dir() -> Path:
    """Katalog transkryptów Claude Code — ten sam układ na każdym systemie
    (`~/.claude/projects`). Używane przez auto-czytanie (Droga A)."""
    return Path.home() / ".claude" / "projects"


# ==================== Auto-aktualizacja (gniazdo; szczegóły w M3) ====================

def update_platform_id() -> str:
    """Identyfikator wpisu w pliku aktualizacji (appcast), np.:
    'macos-arm64', 'macos-x64', 'linux-x64', 'windows-x64'.
    Pozwala jednemu serwerowi serwować paczki dla wszystkich systemów."""
    return f"{os_key()}-{arch()}"
