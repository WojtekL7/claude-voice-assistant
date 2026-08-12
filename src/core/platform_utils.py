"""
Vibe Coding Assistant - Platform utilities (Linux / macOS / Windows)

Jedno miejsce rozstrzygające różnice między systemami operacyjnymi: backend Qt,
Input Method, natywny pasek menu, domyślna powłoka, ścieżka do CLI `claude`,
katalog transkryptów oraz identyfikator platformy dla auto-aktualizacji.

Założenie wieloplatformowe od fundamentu (Etap M1): kod aplikacji NIE rozsiewa
`if linux/mac/windows` po całym projekcie — pyta ten moduł. Windows jest tu
obecny jako pełnoprawny obywatel; miejsca wymagające osobnej implementacji
(np. ConPTY zamiast `pty` w terminalu) są oznaczone `TODO(Windows)`.
"""
import os
import re
import sys
import json
import shutil
import platform
import subprocess
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


# ==================== Pamięć (RAM) ====================

def total_ram_gb():
    """Całkowita pamięć RAM maszyny w GB (float), albo None gdy nie da się ustalić.

    Bez dodatkowych zależności (psutil NIE jest w projekcie):
      • Linux/macOS: `sysconf` SC_PAGE_SIZE × SC_PHYS_PAGES,
      • Windows: GlobalMemoryStatusEx przez ctypes (ullTotalPhys).
    Dowolny błąd / nieobsługiwana platforma → None (wołający traktuje jako
    „nie wiem" i niczego nie blokuje)."""
    try:
        if is_windows():
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            return stat.ullTotalPhys / (1024 ** 3)
        # Linux + macOS — oba mają sysconf z tymi kluczami.
        return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3)
    except Exception:
        return None


def recommended_max_agents(per_agent_gb=4.0, reserve_gb=3.0):
    """Ilu agentów (zakładek z Claude Code) maszyna bezpiecznie uniesie naraz.

    ≈ (RAM_total − rezerwa_systemu) / apetyt_na_agenta, minimum 1. Zwraca None
    gdy RAM nieznany — wtedy wołający NIE blokuje niczego. Domyślne wartości to
    tylko fallback; realne progi wstrzykuje config (RAM_PER_AGENT_GB itd.)."""
    total = total_ram_gb()
    if not total or per_agent_gb <= 0:
        return None
    return max(1, int((total - reserve_gb) // per_agent_gb))


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
    if is_windows():
        # W spakowanej aplikacji (PyInstaller) proces renderowania Chromium
        # ginął NATYCHMIAST (renderProcessTerminated status=2, kod 0x80000003)
        # → terminal zostawał pustym polem (bug 1.0.12; diagnoza CI 2026-06-10).
        # Sandbox Chromium nie współpracuje z układem katalogów PyInstallera.
        # Wyświetlamy WYŁĄCZNIE lokalny terminal.html (zero treści z sieci),
        # więc wyłączenie sandboxa jest tu bezpieczne.
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
        # Log Chromium TYLKO na żądanie (CVA_WEBENGINE_LOG=1): flaga
        # --enable-logging na Windows otwiera CZARNE OKNA KONSOLI procesów
        # QtWebEngineProcess.exe na wierzchu aplikacji (potwierdzone na CI).
        # Do diagnozy zwykle wystarcza webterminal.log (konsola JS + zdarzenia
        # cyklu życia strony — pisze go gui/web_terminal.py).
        if os.environ.get("CVA_WEBENGINE_LOG") == "1":
            try:
                log_dir = Path.home() / ".vibe-coding-assistant"
                log_dir.mkdir(parents=True, exist_ok=True)
                os.environ.setdefault(
                    "QTWEBENGINE_CHROMIUM_FLAGS",
                    "--enable-logging --log-file="
                    + str(log_dir / "webengine_chromium.log"))
            except Exception:
                pass


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


# ==================== Zdrowie binarki `claude` ====================
#
# Paczka `@anthropic-ai/claude-code` z npm NIE zawiera gotowego programu — wozi
# ATRAPĘ (plik `bin/claude.exe`, w środku zwykły TEKST) i dociąga prawdziwą
# binarkę dopiero krokiem po instalacji (`install.cjs`, z optionalDependencies
# `…-win32-x64` itd.). Gdy ten krok się nie wykona (`--ignore-scripts`, część
# konfiguracji pnpm, `--omit=optional`), na dysku ZOSTAJE atrapa.
#
# Skutek na Windows jest wyjątkowo mylący: system próbuje uruchomić tekst nazwany
# `.exe`, nie rozpoznaje formatu i pokazuje modalne „Nieobsługiwana aplikacja
# 16-bitowa" — użytkownik czyta to jako awarię NASZEJ aplikacji. Na Linux/macOS
# ta sama atrapa wypisuje czytelny komunikat i kończy się kodem 1.
#
# Dlatego sprawdzamy plik, a NIE uruchamiamy go: uruchomienie zepsutej binarki
# przez nakładkę `.cmd` samo wywołałoby to modalne okno Windows, czyli dokładnie
# to, co chcemy przed użytkownikiem schować.
_CLAUDE_PLACEHOLDER_MARK = b"native binary not installed"
_WIN_EXECUTABLE_MAGIC = b"MZ"
# Ścieżka wewnątrz nakładki npm (`claude.cmd`) liczona od jej katalogu: `%dp0%\…`.
_WIN_SHIM_PATH_RE = re.compile(r"%~?dp0%?[\\/]+([^\"\r\n]+)")
_NODE_SCRIPT_SUFFIXES = (".js", ".cjs", ".mjs")
_WIN_WRAPPER_SUFFIXES = (".cmd", ".bat", ".ps1")


def _win_shim_target(path: Path):
    """Plik, który realnie uruchamia nakładka npm `claude.cmd`/`.ps1`.

    Zwraca `None`, gdy nie da się tego ustalić — świadomie, bo zgadywanie
    kończyłoby się oskarżeniem sprawnej instalacji."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    base = path.parent
    for rel in reversed(_WIN_SHIM_PATH_RE.findall(text)):
        rel = rel.strip().strip('"').split('" ')[0].strip('"')
        if not rel.lower().endswith((".exe",) + _NODE_SCRIPT_SUFFIXES):
            continue
        try:
            target = (base / rel.replace("\\", os.sep).replace("/", os.sep)).resolve()
            if target.exists():
                return target
        except Exception:
            continue
    # Zapasowo: typowy układ globalnej instalacji npm obok nakładki.
    fallback = (base / "node_modules" / "@anthropic-ai" / "claude-code"
                / "bin" / "claude.exe")
    try:
        if fallback.exists():
            return fallback
    except Exception:
        pass
    return None


def claude_binary_health(command: str = None) -> dict:
    """Czy plik `claude` jest PRAWDZIWYM programem, czy atrapą po nieudanej instalacji.

    Zwraca `{'status', 'path', 'target', 'reason'}`, gdzie status to:
      * `ok`      — plik wygląda na sprawny program (albo nie mamy podstaw sądzić inaczej),
      * `missing` — nie ma czego sprawdzać,
      * `broken`  — to atrapa albo plik nie jest programem tego systemu,
      * `unknown` — nie umiemy rozstrzygnąć (błąd odczytu, nietypowa nakładka).

    ⚠️ NIE uruchamia sprawdzanego pliku (patrz komentarz nad znacznikami wyżej)
    i celowo działa FAIL-OPEN: przy jakiejkolwiek wątpliwości oddaje `ok`/`unknown`,
    nigdy `broken`. Fałszywe „zepsute" zablokowałoby pracę na sprawnej instalacji,
    a to koszt większy niż przepuszczenie rzadkiego przypadku."""
    out = {'status': 'unknown', 'path': None, 'target': None, 'reason': None}
    raw = (command or "").strip()
    name = (raw.split()[0] if raw else "claude") or "claude"
    name = name.strip('"')

    path = None
    absolute = False
    try:
        p = Path(name)
        absolute = p.is_absolute()
        if absolute and p.exists():
            path = p
    except Exception:
        path = None
    # Pytanie o KONKRETNĄ ścieżkę, której nie ma, to „missing" — NIE wolno po
    # cichu podstawiać innego `claude` z PATH: werdykt dotyczyłby wtedy pliku,
    # o który nikt nie pytał (a rozjazd byłby niewidoczny dla wołającego).
    if path is None and not absolute:
        which = shutil.which(name) or shutil.which("claude")
        if which:
            try:
                path = Path(which)
            except Exception:
                path = None
    if path is None:
        out['status'] = 'missing'
        return out
    out['path'] = str(path)

    target = path
    try:
        if is_windows() and path.suffix.lower() in _WIN_WRAPPER_SUFFIXES:
            resolved = _win_shim_target(path)
            if resolved is None:
                # Nietypowa nakładka — nie oskarżamy, mówimy „nie wiem".
                out['reason'] = 'wrapper_unresolved'
                return out
            target = resolved
        out['target'] = str(target)

        with open(target, "rb") as fh:
            head = fh.read(4096)

        if _CLAUDE_PLACEHOLDER_MARK in head:
            out['status'] = 'broken'
            out['reason'] = 'placeholder'
            return out
        # Skrypt Node (np. `cli-wrapper.cjs`) jest poprawną drogą uruchomienia —
        # jego treść to tekst i sprawdzanie magii pliku byłoby tu bez sensu.
        if target.suffix.lower() in _NODE_SCRIPT_SUFFIXES:
            out['status'] = 'ok'
            return out
        if is_windows() and not head.startswith(_WIN_EXECUTABLE_MAGIC):
            out['status'] = 'broken'
            out['reason'] = 'not_windows_program'
            return out
        out['status'] = 'ok'
        return out
    except Exception:
        out['reason'] = 'unreadable'
        return out


def claude_is_broken(command: str = None) -> bool:
    """Skrót do bramkowania: TYLKO jednoznaczne „to atrapa" blokuje uruchomienie."""
    try:
        return claude_binary_health(command).get('status') == 'broken'
    except Exception:
        return False


def _claude_candidates() -> list:
    """Kolejność szukania CLI `claude` — od najbardziej wiarygodnej lokalizacji."""
    home = Path.home()
    candidates = []
    found = shutil.which("claude")
    if found:
        candidates.append(Path(found))
    if is_windows():
        # Instalator natywny Anthropic (zalecany po awarii npm) ląduje w .local\bin.
        candidates += [home / ".local" / "bin" / "claude.exe",
                       home / ".local" / "bin" / "claude",
                       home / "AppData" / "Roaming" / "npm" / "claude.cmd",
                       home / "AppData" / "Roaming" / "npm" / "claude"]
    elif is_macos():
        candidates += [home / ".local" / "bin" / "claude",
                       Path("/opt/homebrew/bin/claude"),
                       Path("/usr/local/bin/claude")]
    else:  # Linux
        candidates += [home / ".local" / "bin" / "claude",
                       Path("/usr/bin/claude"), Path("/usr/local/bin/claude")]
    out = []
    for c in candidates:
        try:
            if c.exists() and str(c) not in out:
                out.append(str(c))
        except Exception:
            continue
    return out


def find_claude_command() -> str:
    """Znajdź CLI `claude` niezależnie od systemu (PATH + typowe lokalizacje).

    Wybiera pierwszy SPRAWNY plik, a nie pierwszy znaleziony: zepsuta instalacja
    z npm leży zwykle wcześniej na PATH niż naprawiona natywna, więc bez tego
    aplikacja po naprawie u użytkownika dalej trzymałaby się atrapy."""
    candidates = _claude_candidates()
    for c in candidates:
        if claude_binary_health(c).get('status') != 'broken':
            return c
    # Wszystkie zepsute → oddaj pierwszy, żeby aplikacja mogła powiedzieć
    # „zainstalowany, ale uszkodzony" zamiast mylącego „nie znaleziono".
    if candidates:
        return candidates[0]
    # Fallback: gołe 'claude' (powłoka znajdzie je na PATH przy uruchomieniu).
    return "claude"


def _enriched_path_env() -> dict:
    """Środowisko z PATH wzbogaconym o typowe lokalizacje narzędzi użytkownika.

    GUI uruchomione z Findera/Docka (macOS) dostaje OKROJONY PATH — bez Homebrew,
    nvm i npm-global — więc `claude` „znika", choć jest zainstalowany. Dokładamy
    te same ścieżki, co terminal w web_terminal._spawn, żeby wykrywanie zgadzało
    się z tym, co realnie zobaczy powłoka."""
    env = dict(os.environ)
    if not is_windows():
        home = Path.home()
        extras = ["/opt/homebrew/bin", "/usr/local/bin",
                  str(home / ".local" / "bin"),
                  str(home / ".npm-global" / "bin")]
        parts = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        for extra in extras:
            if extra not in parts:
                parts.append(extra)
        env["PATH"] = os.pathsep.join(parts)
    return env


def claude_runnable(command: str = None, timeout: float = 5.0) -> bool:
    """Czy CLI `claude` realnie da się uruchomić w tym systemie.

    Pyta system TAK SAMO, jak zrobi to wbudowany terminal: na macOS/Linux przez
    POWŁOKĘ LOGOWANIA (`-lc`), która wczytuje profil użytkownika i pełny PATH
    (Homebrew, nvm, npm). Dzięki temu nie ma fałszywego „nie znaleziono", gdy
    aplikacja startuje z Findera/Docka z okrojonym PATH (przyczyna ciągłego
    kreatora na Macu). Krótki limit czasu, by nie blokować startu."""
    cmd = (command or "").strip()
    name = (cmd.split()[0] if cmd else "claude") or "claude"
    # 1) Pełna ścieżka do istniejącego pliku — pewne i natychmiastowe.
    try:
        if Path(name).is_absolute() and Path(name).exists():
            return True
    except Exception:
        pass
    env = _enriched_path_env()
    # 2) Zapytaj system tak jak terminal.
    try:
        if is_windows():
            r = subprocess.run(["where", name], env=env, timeout=timeout,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                return True
        else:
            shell = default_shell()
            r = subprocess.run([shell, "-lc", "command -v %s" % name],
                               env=env, timeout=timeout,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                return True
    except Exception:
        pass
    # 3) Zapasowo: wyszukiwanie po wzbogaconym PATH + typowe lokalizacje.
    if shutil.which(name, path=env.get("PATH")):
        return True
    found = find_claude_command()
    try:
        return Path(found).is_absolute() and Path(found).exists()
    except Exception:
        return False


def claude_logged_in() -> bool:
    """Czy użytkownik kiedykolwiek zalogował się do Claude Code.

    Logowanie zostawia ślad poświadczeń: na Linux/Windows plik
    `~/.claude/.credentials.json`, na macOS wpis w Pęku kluczy (Keychain).
    Sprawdzamy OBECNOŚĆ, nie ważność (token odświeża samo Claude Code). Na macOS
    czytamy tylko metadane wpisu (bez `-w`) → nieinteraktywne, bez pytania o hasło.
    Przy niepewności zwracamy True, żeby nie nagabywać fałszywie."""
    try:
        if (Path.home() / ".claude" / ".credentials.json").exists():
            return True
    except Exception:
        pass
    if is_macos():
        try:
            r = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials"],
                timeout=4, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                return True
            if r.returncode == 44:   # errSecItemNotFound — na pewno brak wpisu
                return False
            return True              # inny błąd → niepewność → nie nagabuj
        except Exception:
            return True
    return False


def claude_credentials_state() -> dict:
    """Stan poświadczeń Claude Code — BEZ czytania samych sekretów.

    Zwraca `{'available': bool, 'mtime': float|None, 'expires_at': float|None}`:
    - `available` — czy potrafimy ten stan zmierzyć (Linux/Windows: plik
      `~/.claude/.credentials.json`). Na macOS poświadczenia siedzą w Pęku
      kluczy i pliku NIE MA → `available=False`, a wołający musi mieć
      zamiennik (nie da się tam porównać daty zapisu).
    - `mtime` — kiedy plik ostatnio ZAPISANO = kiedy ktoś odnowił token.
    - `expires_at` — kiedy bieżący token wygasa (czas uniksowy w sekundach).

    Służy do odróżnienia WYŚCIGU o odświeżenie tokenu (kilka zakładek naraz;
    plik zostaje odnowiony chwilę po błędzie) od PRAWDZIWEGO wylogowania
    (nikt go nie odnawia). Nigdy nie zwracamy ani nie logujemy wartości
    tokenów — wyłącznie znaczniki czasu.
    """
    state = {"available": False, "mtime": None, "expires_at": None}
    path = Path.home() / ".claude" / ".credentials.json"
    try:
        if not path.exists():
            return state
        state["available"] = True
        state["mtime"] = path.stat().st_mtime
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        expires = (data.get("claudeAiOauth") or {}).get("expiresAt")
        if isinstance(expires, (int, float)):
            state["expires_at"] = expires / 1000.0     # Claude Code trzyma ms
    except Exception:
        pass
    return state


def credentials_refreshed_since(mtime_at_error, state_now: dict) -> bool:
    """Czy poświadczenia zapisano PONOWNIE już po podanym momencie?

    To jedyny pewny sygnał, że ktoś WYGRAŁ wyścig i odnowił token — a więc że
    user wcale nie jest wylogowany. `False` gdy nic się nie zmieniło ALBO gdy
    nie da się tego zmierzyć (macOS: poświadczenia w Pęku kluczy, brak pliku)
    — wołający musi traktować te dwa przypadki osobno.

    Wydzielone z GUI, żeby regułę dało się przetestować bez okna aplikacji.
    """
    if not state_now.get("available"):
        return False
    now_mtime = state_now.get("mtime")
    if mtime_at_error is None or now_mtime is None:
        return False
    return now_mtime > mtime_at_error


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


def is_frozen() -> bool:
    """Czy aplikacja działa jako spakowana paczka (PyInstaller .app/.exe),
    a NIE „z kodu źródłowego" (python src/main.py). Tylko spakowaną da się
    podmienić w miejscu (samo-aktualizacja)."""
    return bool(getattr(sys, "frozen", False))


def appimage_path() -> Path:
    """Ścieżka do pliku .AppImage bieżącej (spakowanej) aplikacji na Linuksie,
    albo None gdy nie uruchomiono jako AppImage.

    Runtime AppImage ustawia `$APPIMAGE` na BEZWZGLĘDNĄ ścieżkę pliku .AppImage
    na dysku (np. ~/Pulpit/Foo.AppImage) — to cel samo-podmiany. UWAGA: NIE
    używać `sys.executable` ani `/proc/self`, bo te wskazują na tymczasowy mount
    `/tmp/.mount_*`, który znika po zamknięciu aplikacji. Brak `$APPIMAGE`
    (uruchomienie „z kodu" lub inny format) → None."""
    env = os.environ.get("APPIMAGE")
    if not env:
        return None
    try:
        p = Path(env)
        return p if p.exists() else None
    except Exception:
        return None


def macos_app_bundle() -> Path:
    """Ścieżka do pakietu `.app` bieżącej (spakowanej) aplikacji na macOS,
    albo None gdy to nie macOS / nie spakowana / nie wygląda na `.app`.

    `sys.executable` w spakowanej apce to
    `…/Vibe Coding Assistant.app/Contents/MacOS/Vibe Coding Assistant` —
    pakiet `.app` to katalog trzy poziomy wyżej. Ta ścieżka jest celem
    samo-podmiany (updater wymienia cały ten katalog)."""
    if not (is_macos() and is_frozen()):
        return None
    try:
        exe = Path(sys.executable).resolve()
    except Exception:
        return None
    # …/Foo.app/Contents/MacOS/Foo  → parents[2] == …/Foo.app
    if len(exe.parents) >= 3:
        bundle = exe.parents[2]
        if bundle.suffix == ".app" and bundle.is_dir():
            return bundle
    return None
