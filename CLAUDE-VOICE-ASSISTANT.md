# CLAUDE-VOICE-ASSISTANT - Agent aplikacji desktopowej

**Przed pracą załaduj również:**
1. 🔴 [`docs/PRD.md`](docs/PRD.md) — **Roadmap komercjalizacji 2026 (MUST READ)** — wizja, model freemium, 5 faz, 31 funkcji, task breakdown
2. `CLAUDE-COMMON.md` — wspólne procedury i zasady
3. [`CLAUDE.md`](CLAUDE.md) (lokalny) — auto-loaded przy starcie Claude Code w tym katalogu

---

## Projekt: Claude Voice Assistant

- **Lokalizacja:** `/home/hdkrytbhdkf/Projekty/claude-voice-assistant/`
- **Technologie:** Python 3.12, PyQt5, QTermWidget, edge-tts, Groq Whisper
- **GitHub:** https://github.com/WojtekL7/claude-voice-assistant

---

## FUNKCJE

- Prawdziwy terminal (QTermWidget) zamiast symulacji
- Dyktowanie głosem (STT) → tekst wpisuje się w terminalu
- Czytanie odpowiedzi głosem (TTS)
- Auto-czytanie nowych odpowiedzi
- Wiele agentów w zakładkach
- Pliki pamięci projektu
- Skinowanie (kolory, ikony)

---

## URUCHOMIENIE

```bash
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant
source venv/bin/activate
python3 src/main.py
```

---

## STRUKTURA PROJEKTU

```
claude-voice-assistant/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Konfiguracja, stałe
│   └── gui/
│       ├── main_window.py   # Główne okno aplikacji
│       ├── agent_tab.py     # Zakładka agenta z terminalem
│       └── dialogs/         # Dialogi (ustawienia, agenty)
├── wheels/
│   └── qtermwidget-*.whl    # QTermWidget wheel
└── venv/                    # Środowisko wirtualne
```

---

## KLUCZOWE PLIKI

| Plik | Opis |
|------|------|
| `src/config.py` | Konfiguracja: języki, głosy TTS, domyślni agenci, ścieżki |
| `src/gui/main_window.py` | Główne okno, menu, obsługa TTS/STT, skinowanie |
| `src/gui/agent_tab.py` | Zakładka agenta: terminal, splitter, input, przyciski |

---

## KONFIGURACJA UŻYTKOWNIKA

Pliki konfiguracyjne w: `~/.claude-voice-assistant/`

| Plik | Zawartość |
|------|-----------|
| `config.json` | Ogólne ustawienia (język, głos, skin) |
| `agents.json` | Lista agentów z konfiguracją |
| `memory_projects.json` | Projekty pamięci z plikami |
| `quick_actions.json` | Szybkie akcje użytkownika |

---

## QTERMWIDGET

Wheel: `wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl`

Instalacja (jeśli potrzebna):
```bash
pip install wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl
```

---

## ZALEŻNOŚCI

```
PyQt5
PyQtWebEngine     # WebTerminal (xterm.js w QtWebEngine) — Mac/Win, opcjonalnie Linux
edge-tts          # Text-to-Speech (Microsoft voices)
sounddevice       # Nagrywanie audio
numpy / scipy
requests          # HTTP client (Groq STT, licencje, auto-aktualizacja M3) — NIE httpx
ptyprocess        # PTY dla WebTerminal (Unix); Windows = ConPTY (TODO)
```

> ⚠️ Klientem HTTP jest **`requests`** (`stt_engine.py`, `license_manager.py`,
> `update_manager.py`), a NIE `httpx` (httpx nie ma w `requirements.txt`).

**Groq API** (Speech-to-Text):
- URL: `https://api.groq.com/openai/v1/audio/transcriptions`
- Wymaga: `GROQ_API_KEY` w zmiennych środowiskowych

---

## WORKFLOW WDRAŻANIA

Aplikacja lokalna - nie wymaga deploy na serwer:

```bash
# 1. Git
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant
git add . && git commit -m "opis" && git push

# 2. Test
source venv/bin/activate
python3 src/main.py
```

---

## SYGNAŁY PyQt (ważne przy modyfikacjach)

**AgentTab:**
- `message_sent(str)` - wysłano wiadomość
- `terminal_output(object)` - dane z terminala
- `status_changed(str)` - zmiana statusu
- `request_tts(str)` - żądanie TTS
- `request_dictation(bool)` - start/stop dyktowania
- `splitter_changed(list)` - zmiana pozycji rozdzielacza

---

## CZĘSTE PROBLEMY

| Problem | Rozwiązanie |
|---------|-------------|
| QTermWidget not found | `pip install wheels/qtermwidget-*.whl` |
| TTS nie działa | Sprawdź połączenie internetowe (edge-tts) |
| STT nie nagrywa | Sprawdź GROQ_API_KEY, mikrofon |
| Aplikacja się nie uruchamia | `python3 -m py_compile src/main.py` |

---

## ARCHITEKTURA AUTO-CZYTANIA (Droga A — z dziennika sesji, NIE z terminala)

**Najważniejsza zasada:** auto-czytanie bierze tekst z **dziennika sesji Claude Code**
(`~/.claude/projects/<zakodowana-ścieżka-cwd>/<sesja>.jsonl`), a **NIE** ze strumienia
terminala. Wdrożone 2026-05-30 (3 commity: Etap 1/2/3).

### Dlaczego NIE z terminala (pułapka, w którą łatwo wpaść ponownie)

Strumień terminala Claude Code 2.x to TUI z pełnymi przerysowaniami i skokami kursora.
Po wycięciu ANSI dostajesz śmieci:
- **spinner „Evaporating…/Thinking…"** renderowany literka po literce przez kolejne klatki
  → po sklejeniu daje pojedyncze litery (objaw zgłoszony: **„czyta A dziesiątki razy"**),
- **ghost text** (podpowiedź autouzupełniania w polu input) czytany jako treść
  (objaw: „czyta to, co zaproponował do Entera"),
- **skoki kursora** (`\x1b[58G`) zamiast spacji → **sklejone słowa** („którepotrafiąprzespać"),
- echo prompta, ramki, liczniki tokenów.

Stary `extract_last_claude_response()` w `text_cleaner.py` próbował to czyścić heurystykami —
kruche, zostało **wycofane** z auto-czytania (zostaje tylko jako fallback ręcznego 🔊).

### Jak działa Droga A (mapowanie plików)

| Klocek | Plik | Rola |
|--------|------|------|
| Czytnik dziennika | `core/transcript_reader.py` — `TranscriptReader` | śledzi offset bajtowy w pliku sesji, `poll()` zwraca NOWE wypowiedzi; bierze tylko bloki `type=="text"` z wpisów `assistant` **nie-sidechain** → myślenie, `tool_use` i pod-agenci odpadają same; `seek_to_end()` (priming, pomija historię), `last_response()` (ręczne 🔊) |
| Filtr prozy | `core/text_cleaner.py` — `prose_from_markdown()` | z czystego markdownu wycina bloki kodu, inline-kod, tabele, linki, obrazki, znaczniki, URL-e, emoji → zostawia prozę |
| Lektor | `core/tts_engine.py` | kolejka z wyprzedzeniem (prefetch): `enqueue()` dokłada bez przerywania, generuje N+1 zdanie w tle → brak ciszy; `clear_queue()` przy zmianie zakładki |
| Spinacz | `gui/main_window.py` — `_poll_transcripts()` (QTimer 800ms) | aktywna zakładka z auto-read → `enqueue()` na żywo; nieaktywne → `pending_backlog` (cap 50) |

### Zachowanie per-zakładka

- **Tylko aktywna** zakładka czyta na głos; przełączenie ucisza poprzednią
  (`_handle_active_tab_switch` → `tts.clear_queue()`).
- **Nieaktywna** z auto-read zbiera prozę w `agent_tab.pending_backlog`; po powrocie →
  komunikat „🔔 N nieprzeczytanych… kliknij 🔊", a 🔊 doczytuje (`_read_last_response`).
- **Priming:** przy pierwszym wykryciu sesji `seek_to_end()` — pomija historię i startowe
  „Przeczytaj pliki pamięci…". Czytanie startuje od pierwszej NOWEJ wypowiedzi.
- Czyta **całą wypowiedź po jej ukończeniu** (dziennik dostaje blok po skończeniu), nie literka po literce.

### Fakty z terminala (gdyby ktoś WRACAŁ do Drogi B — z ekranu)

Z nagranej próbki (Claude Code 2.1.158, truecolor): biała kropka = `●` **RGB(255,255,255)**;
proza = kolor domyślny; **kod/ścieżki = RGB(177,185,249)** (jasnoniebieski — „niebieska czcionka");
tabele = znaki ramek `┌┬┐│├┼┤└┴┘` (NIE `|`); spinner/„myślenie" = szary **RGB(153,153,153)** + `✻✢✶✽`.
Nagrywanie surowej próbki: PTY + `claude` w zaufanym katalogu, `TERM=xterm-256color`, marker to `●` (U+25CF), nie `⏺`.

---

## ✅ PORT macOS (+ Windows w przyszłości) — STRONA KODU UKOŃCZONA (2026-06-01)

> **Stan: M1–M4 zrobione i wypchnięte.** Cała strona kodu portu gotowa; zostaje
> tylko zbudowanie `.dmg` **na Macu** (z Linuksa się nie da) + opcjonalnie feed na VPS.

**Cel (osiągnięty):** wersja na **Apple Silicon**, architektura od razu pod **przyszły
Windows**; **auto-aktualizacja** z VPS; **podpis odłożony** (gniazdo gotowe).

### Zablokowane decyzje (uzgodnione z użytkownikiem)
- **Mac:** Apple Silicon. Finalny `.app`/`.dmg` **użytkownik buduje/testuje na swoim Macu** — z Linuksa się nie da (mogę przygotować kod + skrypty + instrukcję).
- **Terminal:** xterm.js w QtWebEngine + PTY (wieloplatformowy). QTermWidget jest **tylko-Linux**.
- **Auto-aktualizacja:** własna, na VPS `srv1251441.hstgr.cloud` (plik `appcast.json` + downloader w aplikacji). Format: `packaging/appcast.example.json`. ID platformy: `platform_utils.update_platform_id()`.
- **Podpis:** na razie **BEZ** (unsigned; pierwszy start na Macu: prawy klik → „Otwórz"). Gniazdo: `packaging/signing.conf.example` (wyłączone). Updater będzie zdejmował kwarantannę z pobranych paczek, by aktualizacje były „gładkie".
- **Windows:** architektura 3-systemowa od początku; PTY za interfejsem (Windows = ConPTY/`pywinpty` w to samo gniazdo, oznaczone `TODO(Windows)`).

### Procedura (jak w całym projekcie)
Każdy etap: zrobić → przetestować na Linuksie → checklista dla użytkownika → po „działa" **commit+push**.
**Główna zasada: NIE psuć działającej wersji linuksowej** — na Linuksie domyślnie zostaje QTermWidget.

### ✅ ZROBIONE (M1–M4, wszystko na `main`)
- **M1** (`fffe6dd`): `src/core/platform_utils.py` (OS/arch, `configure_qt_environment` — X11/iBus tylko Linux, `use_native_menu_bar`, `default_shell`, `find_claude_command`, `claude_projects_dir`, `update_platform_id`, **`prefer_webengine_terminal`** dodane w M2.3); `APP_VERSION` w `config.py`; `packaging/` (gniazdo podpisu + format appcast).
- **M2.1** (`44b387d`): `src/gui/web_terminal.py` (`WebTerminal`) + `src/assets/web/terminal.html` + `vendor/xterm.js`. PTY (ptyprocess) ↔ QWebChannel ↔ xterm.js.
- **M2.2** (`ade4a25`): `src/gui/terminal_backend.py` — wspólny interfejs `TerminalBackend` + adaptery `QTermWidgetBackend`/`WebTerminalBackend` + fabryka `create_terminal_backend()`/`selected_backend_kind()`. Czysto addytywne.
- **M2.3** (`716946e`): wpięcie do `AgentTab`/`MainWindow` za interfejsem (11 punktów styku w main_window). Linux=QTermWidget domyślnie, Mac/Win/`CVA_WEBTERMINAL=1`=WebTerminal. Gotcha `AA_ShareOpenGLContexts` + wczesny import QtWebEngine w `main.py`.
- **M2.4** (`f9c030d`): pełny motyw xterm ze skórki (`_xterm_theme_from_colors`), czcionka, scrollback 10000; zaznaczanie/kopiowanie/resize działały od M2.1.
- **M3** (`0338b07`): `src/core/update_manager.py` (`UpdateManager`+`UpdateInfo`) + `UpdateAvailableDialog` (dialogs.py) + menu Pomoc (Sprawdź aktualizacje / przełącznik) + ustawienie `auto_check_updates` + ciche sprawdzanie 3s po starcie. sha256 obowiązkowe, Ed25519 jako gniazdo wyłączone. Instalacja = otwórz instalator (bez auto-podmiany). HTTP przez **requests**.
- **M4** (`61d5774`): `packaging/macos/` (`ClaudeVoiceAssistant.spec`, `entitlements.plist`, `build-macos.sh`, `README.md`) + `packaging/make-appcast-entry.py`. `config.BASE_DIR` świadomy `sys._MEIPASS` (frozen-only); `web_terminal.ASSET_DIR` z `config.ASSETS_DIR`.

### 🧱 Architektura terminala (po M2) — pamiętaj
Jedna „deska rozdzielcza": **`terminal_backend.py`** definiuje `TerminalBackend` (metody: `set_shell_program`, `start_shell_program`, `send_text`, `selected_text`, `copy_selection`, `clear`, `set_font`, `set_color_scheme`, `focus_terminal`, `shutdown`; sygnały `output_received(str)`, `finished`). Fabryka wybiera silnik: **Linux→QTermWidget** (chyba że `CVA_WEBTERMINAL=1` lub brak QTermWidget), **macOS/Windows→WebTerminal**. AgentTab trzyma `self.terminal_backend` (+ `self.terminal = backend.widget`). Cały kod woła backend, nie surowy widget — dlatego oba silniki działają tą samą ścieżką.

### ⏭️ CO ZOSTAŁO (nie-kodowe / przyszłość)
- **Build na Macu:** `./packaging/macos/build-macos.sh` → `.app`/`.dmg` (instrukcja w `packaging/macos/README.md`). Tylko na macOS.
- **Feed na VPS:** wgrać paczki + `appcast.json` pod `https://srv1251441.hstgr.cloud/cva/` (generator wpisu: `packaging/make-appcast-entry.py`). Bez tego „Sprawdź aktualizacje" zwraca błąd (feedu jeszcze nie ma — to OK).
- **Podpis/notaryzacja macOS:** opcjonalny, wg `packaging/signing.conf` (domyślnie OFF).
- **Windows:** jedyne realne gniazdo do dorobienia = backend PTY **ConPTY/`pywinpty`** w `web_terminal.py` (oznaczone `TODO(Windows)`); reszta warstwy (fabryka, `default_shell`, `open_installer` `os.startfile`, packaging) już Windows-aware. Pakowanie `.exe` w `packaging/windows/`.

### Jak testować WebTerminal na Linuksie
- Demo wizualne: `source venv/bin/activate && python3 src/gui/web_terminal.py`
- Headless smoke: test potoku PTY (echo round-trip) + QtWebEngine `loadFinished`/`frontend_ready` z `QT_QPA_PLATFORM=offscreen` i `QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --in-process-gpu --disable-dev-shm-usage"`. Pełny render wymaga ekranu.

---

*Ostatnia aktualizacja: 2026-06-01 — PORT macOS UKOŃCZONY (strona kodu): M2.2 (terminal_backend.py — wspólny interfejs + fabryka), M2.3 (wpięcie do AgentTab/MainWindow; Linux=QTermWidget, Mac/Win/CVA_WEBTERMINAL=1=WebTerminal; gotcha AA_ShareOpenGLContexts w main.py), M2.4 (pełny motyw xterm ze skórki + czcionka + scrollback 10000), M3 (update_manager.py + UpdateAvailableDialog + menu Pomoc + ciche sprawdzanie przy starcie; sha256 obowiązkowe, Ed25519 wyłączone; instalacja=otwórz instalator; HTTP przez requests NIE httpx), M4 (packaging/macos: spec PyInstallera + Info.plist z mikrofonem + entitlements + build-macos.sh + make-appcast-entry.py; config.BASE_DIR świadomy sys._MEIPASS frozen-only). Sekcja PORT przepisana na ✅ UKOŃCZONE + architektura terminala + CO ZOSTAŁO (build na Macu, feed VPS, Windows ConPTY). Poprawka ZALEŻNOŚCI: httpx→requests. Commity: ade4a25, 716946e, f9c030d, 0338b07, 61d5774. Wcześniej 2026-05-30 — dodano sekcję 🚧 PORT macOS — STATUS I PLAN [wznowienie 2026-05-31]: cel (Mac Apple Silicon, architektura pod Windows, auto-aktualizacja z VPS, podpis odłożony z gotowym gniazdem); zablokowane decyzje; ZROBIONE M1 (platform_utils, packaging, APP_VERSION) + M2.1 (WebTerminal xterm.js+QtWebEngine+PTY, działa); NASTĘPNY KROK = M2.2 (wspólny interfejs + fabryka backendów), dalej M2.3 wpięcie do AgentTab (Linux=QTermWidget domyślnie, Mac/Win=WebTerminal; gotcha AA_ShareOpenGLContexts), M2.4, M3 updater, M4 pakowanie. Wcześniej 2026-05-30 — nowa sekcja ARCHITEKTURA AUTO-CZYTANIA (Droga A): auto-czytanie czyta czystą prozę z dziennika `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.* `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.*
