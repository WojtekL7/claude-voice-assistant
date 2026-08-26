# ARCHIWUM — CLAUDE-VOICE-ASSISTANT (pełny snapshot sprzed odchudzenia 2026-06-17)

> Ten plik NIE jest czytany na starcie sesji — to pełna kopia pliku pamięci sprzed odchudzenia.
> Żywa, szczupła wersja: `CLAUDE-VOICE-ASSISTANT.md`. Dziennik zmian: `git log`.

---

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

## 🍎 DYSTRYBUCJA / WYDANIA macOS (od 2026-06-01) — działa na realnym Macu

Port doprowadzony do **działającego `.dmg`** na Macu (potwierdzone na MacBooku Magdy).
Pełna automatyzacja „użytkownik nie buduje nic". Uniwersalne nauki → `CLAUDE-COMMON.md`
(sekcja PAKOWANIE / DYSTRYBUCJA APLIKACJI DESKTOPOWEJ).

### Budowanie i wydania (chmura)
- **GitHub Actions:** `.github/workflows/build-macos.yml` — runner `macos-14` (arm64),
  uruchamia `packaging/macos/build-macos.sh`, artefakt + Release przy tagu `vX.Y.Z`.
  Wyzwalanie: `gh workflow run build-macos.yml` albo `git tag vX.Y.Z && git push origin vX.Y.Z`.
- **Launchery dwuklik (dla nie-programisty):** `Uruchom-Mac.command` (uruchom z kodu),
  `Zbuduj-DMG-Mac.command` (zbuduj `.dmg` lokalnie na Macu).
- **Podmiana pliku na stronie po buildzie:** `gh release download vX -p '*.dmg'` → `scp`
  na serwer jako `…/downloads/ClaudeVoiceAssistant-macos.dmg` (nazwa stała = przycisk działa).

### Strona pobierania (z hasłem)
- **URL:** `https://pobierz.srv1251441.hstgr.cloud` — basicauth (login `pobierz`; hasło
  regenerowalne: `openssl passwd -apr1` + podwojone `$$` w compose).
- Kontener `cva-web` (nginx) na VPS Hostinger w **`/opt/cva-web/`** (osobny
  `docker-compose.yml` za traefik, sieć `n8n_default`, middleware basicauth). Pliki:
  `/opt/cva-web/html/` (+ `downloads/`). Źródło strony: `packaging/web/index.html`.
  Wyłączenie: `cd /opt/cva-web && docker compose down`; włączenie: `up -d`.

### Wydane wersje i co naprawiają
- **1.0.0** — pierwszy `.dmg`. **1.0.1** — terminal jako **login shell** (`claude` znajduje
  `node`; był `env: node: No such file`). **1.0.2** — **menu wbudowane w okno** (natywny pasek
  macOS znikał, też po restarcie). **1.0.3** — dołączony **font Ubuntu Mono/Ubuntu**
  (`src/assets/fonts/`, czytelność jak na Linuksie; macowy zamiennik był cienki). **1.0.4** —
  **działa Pauza czytania (TTS)**.

### Pauza TTS — uwaga na przyszłość
Silnik `tts_engine.py` MA gotową pauzę (`pause/resume/toggle_pause`, pygame). Bug był w GUI:
`AgentTab._toggle_pause` było puste (`pass`). Naprawa: sygnał **`request_pause`** → podłączony
w MainWindow (`_create_agent_tab` i `_add_new_terminal`) do `_toggle_pause` → `tts.toggle_pause()`.
Przycisk ⏸ widoczny tylko podczas `PLAYING` (`_on_tts_state_changed`).

### requirements pod macOS
Usunięto pakiet `asyncio` (to stdlib; pip-backport psuł instalację na Py3.x). `pyenchant`
**opcjonalny** (zakomentowany — wymaga systemowego `enchant`; kod działa bez:
`ENCHANT_AVAILABLE` w `text_cleaner.py`).

### TODO (następna sesja)
- 🎤 **Klucz Groq** do dyktowania — pole w Ustawieniach domyślnie puste, user wkleja własny.
  ✅ Klik mikrofonu bez klucza pokazuje już komunikat + dialog (naprawione w 1.0.7 — patrz sekcja
  „SESJA 2026-06-02" niżej). Brak mikrofonu na macOS = pozwolenie systemowe
  (`NSMicrophoneUsageDescription` jest w Info.plist).
- 🍏 **Podpis Apple** (Developer ID + notaryzacja, `signing.conf`) — żeby zniknął krok
  „Otwórz mimo to" (Sequoia: Ustawienia→Prywatność→„Otwórz mimo to").
- 💻 **Intel Mac** (`macos-13`) + **Linux AppImage** w automacie + włączenie ich przycisków
  na stronie (teraz Linux/Windows nieaktywne).
- 🔒 **Ochrona/licencja/własna nazwa** (NIE „Claude" — to znak Anthropic) — rozmowa 2026-06-01:
  warstwy = prawo+marka, logika na serwerze, aktywacja licencji, Nuitka/PyArmor+podpis.

---

## 🛠️ SESJA 2026-06-02 — licznik, ikony SVG, UI agentów/plików, mikrofon (wydania 1.0.5→1.0.7)

### Terminal i sygnały zakładki — pułapki/naprawy
- **`QTermWidgetBackend._on_received` (terminal_backend.py): `receivedData` niesie `str`, nie QByteArray.**
  Stare `bytes(data)` na stringu rzucało `TypeError` połykany w `try/except` → `output_received`
  NIGDY nie leciało → **całe wyjście terminala gubione na Linuksie od refaktoru backendu M2.3**
  (licznik tokenów milczał, bo karmi go ten strumień). Fix: obsługa `isinstance(str)` /
  `hasattr('data')` (QByteArray) / `bytes()`. Uniwersalna wersja → CLAUDE-COMMON „DIAGNOZA SYGNAŁÓW QT".
- **`MainWindow._connect_agent_tab_signals(agent_tab)` = JEDNO źródło prawdy** dla podłączania
  sygnałów zakładki. Wcześniej lista była zdublowana w `_create_agent_tab` i `_add_new_terminal`,
  a w tym drugim (zakładki „+") **brakowało `terminal_output`** → licznik nie rósł na „+".
  Reguła: oba tory tworzenia zakładek wołają tę metodę.
- **`self.terminal_backend` = None przy starcie primary taba (index 0).** Lazy activation +
  `setCurrentIndex(0)` NIE emituje `currentChanged` → referencja kopiowana w `__init__` zanim
  powstanie terminal i nigdy nieodświeżana (przy jednej zakładce). Objaw: **🔊/⧉ nie działają do
  pierwszej zmiany zakładki.** Fix: `_update_current_tab_references()` w `_on_terminal_ready`,
  gdy to aktywna zakładka.

### Ikony dolnego panelu — kolorowe SVG (zamiast emoji)
- Pliki: **`src/assets/icons/*.svg`** (13: mic, speaker-low/mid/high, pause, play, stop, copy,
  check, close, clip, bolt, hourglass) ładowane przez **`gui/icon_set.py`**:
  `button_icon(key, state)` (mapowanie (klucz,stan)→plik, te same klucze/stany co
  `DEFAULT_SKIN_ICONS`), `SPEAKER_LEVELS` do animacji głośnika.
- Przyciski: `setIcon(...)` + `setIconSize(QSize(24,24))`, **nie** emoji-tekst. `agent_tab.py`
  ustawia ikony przy tworzeniu; `main_window` zmienia je przy stanach (pauza↔play, kopiuj↔ptaszek,
  mikrofon nagrywanie/przetwarzanie, animacja głośnika); `_apply_skin_icons` ustawia QIcon.
- **`send_btn` pozostaje tekstowy** („↵ Enter"). Paczka PyInstaller dołącza **całe `src/assets`
  automatycznie** (`datas` w `.spec`) — nowe ikony trafiają do `.app`/`.dmg` bez zmian w spec.
- Dialog „zmień emoji ikony" przestał dotyczyć tych przycisków (do ewentualnej przeróbki na wybór ikon).

### Pasek statusu — licznik + pasek postępu
- Licznik tokenów (zielony „N (X%)") i globalny „Σ N" mają **stałą szerokość** (anty-skakanie).
- **Pasek postępu zużycia kontekstu** (QProgressBar 70×10) po lewej od liczby; wypełnienie i kolor
  z `_refresh_context_label` (te same progi: <50 zielony / <70 żółty / <90 pomarańcz / ≥90 czerwony).
  Zero ruchu: liczba o stałej szerokości, wyrównana do prawej. Szczegóły trade-offu → CLAUDE-COMMON.

### „Zarządzaj agentami" — tło = auto-start
- Wskaźnik auto-startu to teraz **TŁO wiersza** (zielone `rgba(34,160,84,70)` = uruchamiany przy
  starcie, szare `rgba(120,125,135,65)` = nie), **półprzezroczyste** by fioletowe zaznaczenie
  (`item:selected #6a2a5a`) prześwitywało. Kółko 🟢/⚪ usunięte (na Linuksie było szare/nieczytelne).

### Okna plików — neutralna ciemna paleta
- Natywne okno GNOME niedostępne dla Qt tutaj (patrz CLAUDE-COMMON). `DIALOG_COLORS` (dialogs.py,
  używane TYLKO w `get_file_dialog_stylesheet`) zmienione z fioletu na neutralne ciemne
  (tło `#2e2e2e`, pola `#1e1e1e`, zaznaczenie = niebieski GNOME `#3584e4`). Polskie etykiety bez zmian.

### Groq / dyktowanie
- **Groq = WYŁĄCZNIE dyktowanie (STT, Whisper). Czytanie (TTS) = edge-tts, działa BEZ klucza.**
- `_toggle_dictation` przy pustym kluczu wołało nieistniejące `_show_api_key_dialog` →
  `AttributeError` → mikrofon „nic nie robił". Fix (1.0.7): `QMessageBox` wyjaśniający +
  `_show_groq_api_dialog` (istniejący dialog wpisania klucza; menu „Klucz API Groq…").
- Ustawienia użytkownika: `~/.claude-voice-assistant/config.json` (`groq_api_key`); jest backup
  `config.json.bak-*` (przydatny do odzyskania klucza po pomyłce).

---

## 🔄 AUTO-AKTUALIZACJA — start/zamknięcie + samo-podmiana macOS (2026-06-03)

> Rozbudowa M3. Aplikacja sama dostaje info o nowej wersji i (na macOS) aktualizuje
> się bez ręcznego wgrywania. Etap 1+2 + publiczny feed na VPS — zrobione i przetestowane
> na żywym serwerze (commit `d9f4ed2`). Suwak boczny xterm.js spójny z Linuksem: `28e0137`.

### Etap 1 — sprawdzanie przy starcie I zamknięciu (wszystkie systemy)
`main_window.closeEvent` na wejściu odpala async-check (raz/sesję — `_update_checked_on_close`),
robi `event.ignore()` i bezpiecznik `QTimer.singleShot(4000, _close_check_timeout)` (brak/wolny
internet NIE blokuje zamykania). Wynik wraca do współdzielonych slotów
`_on_update_available / _on_no_update / _on_update_check_failed`, które rozróżniają tryb przez
flagę `_close_check_in_progress` i kończą zamykanie przez `_finish_close()`
(`_force_close=True; self.close()` — drugi `closeEvent` pomija sprawdzanie). Start (3 s) bez zmian.

### Etap 2 — macOS sam się podmienia (`core/update_manager.py`)
`apply_update_async(path)` → `_apply_worker`: gdy `can_self_replace` (**macOS + `.zip` +
`macos_app_bundle()`≠None**) → `_macos_self_replace`: `ditto -x -k` (NIE zipfile — symlinki Qt!)
→ skrypt bash czeka na PID, `rm -rf` stary pakiet, `mv||cp` nowy, `xattr -dr` kwarantanna,
`open` → sygnał `relaunch_ready`. Inaczej `open_installer` → `installer_opened`. Błąd →
`apply_failed`. `platform_utils`: `is_frozen()`, `macos_app_bundle()` (pakiet z
`sys.executable.parents[2]`, gdy `.suffix==".app"`).
**Dialog** (`dialogs.UpdateAvailableDialog`): `_on_finished` woła `apply_update_async` (nie
bezpośrednio `open_installer`); sloty `_on_relaunch_ready` (komunikat + `QApplication.quit()` —
pomocnik wznawia), `_on_installer_opened`, `_on_apply_failed`.

### Build + feed
- `packaging/macos/build-macos.sh` tworzy też **`.zip`** pakietu (`ditto -c -k --keepParent`)
  obok `.dmg`: **`.zip` = samo-aktualizacja**, **`.dmg` = strona pobierania**. Wpis do feedu
  generuj z `.zip`: `make-appcast-entry.py …zip --version X --base-url …/cva/ --appcast packaging/appcast.json --merge`.
- `config.UPDATE_APPCAST_URL = https://pobierz.srv1251441.hstgr.cloud/cva/appcast.json` (PUBLICZNY).
- **VPS:** pliki w `/opt/cva-web/html/cva/`; w `cva-web/docker-compose.yml` drugi router traefik
  `cva-pub` = `Host(pobierz…) && PathPrefix(/cva)`, `priority=100`, **bez basicauth**,
  `service=cva` → `/cva` publiczne, reszta strony za hasłem. Backup: `docker-compose.yml.bak-*`.
  Apex `srv1251441.hstgr.cloud` (bez subdomeny) NIE jest routowany — dlatego host = `pobierz.`.

### Stan i wydawanie kolejnej wersji
- Feed = **1.0.7** (== zainstalowana → „brak aktualizacji", bezpiecznie). **Auto-update aktywny
  od 1.0.8 w górę** — pierwszą (1.0.8) instalujesz **raz ręcznie** z `.dmg` (stara 1.0.7 ma w środku
  martwy apex-URL i nie zna nowego mechanizmu). Od 1.0.8 Mac aktualizuje się sam.
- **appcast MUSI mieć wpis dla bieżącej platformy** (`update_platform_id()`), inaczej cicho
  „no_update" mimo wyższej `version` (kosztowało fałszywy no_update w teście, póki nie dodano
  `linux-x64`). Linux/Windows: na razie `open_installer` (do czasu AppImage/.exe).
- Uniwersalne nauki (ditto vs zipfile, publiczny router /cva bez auth, appcast-per-platforma,
  bootstrap, sprawdzanie-przy-zamknięciu z bezpiecznikiem) → CLAUDE-COMMON „AUTO-AKTUALIZACJA
  APLIKACJI DESKTOPOWEJ".

### ⏭️ DO ZROBIENIA — oczekuje na użytkownika (ustalone 2026-06-03)
**1.0.8 jest WYDANE i feed na VPS aktywny** (build GitHub Actions OK; `.zip`+`appcast.json` na
`https://pobierz.srv1251441.hstgr.cloud/cva/`, sha256 zweryfikowane; `.dmg` na stronie pobierania).
Brakuje już TYLKO kroków po stronie użytkownika (nie zrobione teraz — „zrobimy później"):
- [ ] **Zainstalować 1.0.8 RĘCZNIE raz na Macu** z `.dmg` (`https://pobierz.srv1251441.hstgr.cloud`,
      login `pobierz` + hasło; Sequoia: Ustawienia→Prywatność→„Otwórz mimo to"). Konieczne, bo
      zainstalowana 1.0.7 ma w środku martwy apex-URL i **sama się nie zaktualizuje** do 1.0.8.
      **Od 1.0.8 w górę Mac aktualizuje się już sam.**
- [ ] **(Opcjonalnie) Pełny test samo-podmiany na żywym Macu:** po instalacji 1.0.8 wydać **1.0.9**
      (drobna zmiana) i zobaczyć cały cykl: okno „aktualizować?" → pobranie → podmiana → restart,
      bez klikania w instalator. To pierwszy realny test self-replace na prawdziwej maszynie.
- [ ] **Linux/Windows self-update:** czeka na paczki (AppImage / `.exe`) — wtedy ten sam mechanizm
      (`apply_update_async`) dostanie gałąź swap zamiast „otwórz instalator". Osobne TODO.

---

## 🎉 SESJA 2026-06-08 — pierwszy udany SELF-UPDATE na żywym Macu (1.0.8→1.0.9) + zakładki macOS (dokończone 2026-06-09 w 1.0.11)

> **Kamień milowy:** auto-aktualizacja przeszła **end-to-end na realnym Macu** — program
> sam pobrał `.zip`, podmienił się i zrestartował jako **1.0.9**, BEZ instalatora i bez
> ręcznego przeciągania. Cały mechanizm (M3 + Etap 1/2 samo-podmiany + publiczny feed)
> potwierdzony w praniu. Numeracja w programie zmieniła się na 1.0.9.

### Wydanie 1.0.9 — sprawdzony przebieg (runbook na przyszłe wydania)
1. `APP_VERSION` 1.0.8→1.0.9 w `src/config.py` → commit + push.
2. `git tag v1.0.9 && git push origin v1.0.9` → GitHub Actions (`build-macos.yml`, runner `macos-14`) buduje `.dmg`+`.zip` i publikuje Release (~1,5 min).
3. `gh release download v1.0.9 -p '*.zip' -p '*.dmg'` (paczki ~123/144 MB; do tymczasowego `dist-release/`, jest w `.gitignore`).
4. **NAJPIERW** wgraj `.zip` do `/opt/cva-web/html/cva/`, **POTEM** `appcast.json` — kolejność krytyczna (feed po paczce, inaczej okno błędu 404 jak wcześniej na Linuksie).
5. `.dmg` → `/opt/cva-web/html/downloads/ClaudeVoiceAssistant-macos.dmg` (STAŁA nazwa = przycisk pobierania działa; starą zachowaj jako `…-1.0.8.dmg.bak`).
6. Wpis do feedu: `python3 packaging/make-appcast-entry.py PACZKA.zip --version 1.0.9 --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ --appcast packaging/appcast.json --merge` (liczy sha256 + rozmiar), potem `scp appcast.json`.
7. Weryfikacja **publicznym URL** (jak widzi to aplikacja): `curl …/cva/appcast.json` (version=1.0.9) + `curl -I …-1.0.9-macos-arm64.zip` (HTTP 200, `content-length` == `size` w feedzie).

### ✅ Zakładki na macOS wyrównane do lewej — ROZWIĄZANE w 1.0.11 (potwierdzone na realnym Macu 2026-06-09)
Droga przez trzy wydania (każde testowane na żywym Macu przez self-update):
- **1.0.9** — CSS `QTabWidget::tab-bar { alignment: left }` (commit `6f33996`) — **NIE działa**.
- **1.0.10** — `QProxyStyle` nadpisujący **sam** `styleHint(SH_TabBar_Alignment)→AlignLeft` — **NIE działa**.
- **1.0.11** — **DZIAŁA** (commit `d1404b6`).

**Dlaczego dwie pierwsze padły:** `QMacStyle` **IGNORUJE** `SH_TabBar_Alignment`. Centrowanie liczy
**styl `QTabWidget`** w `subElementRect(QStyle.SE_TabWidgetTabBar)` (zwraca prostokąt paska
wyśrodkowany), a nie style-hint ani QSS. Forum Qt uznaje to za nierozwiązane.

**Działający fix (`_LeftAlignedTabStyle` w `main_window.py`):** `QProxyStyle` oparty o **silnik
Fusion** (`QStyleFactory.create("Fusion")` — nie-macowy, respektuje lewą) z override **`subElementRect`**
dosuwającym pasek do lewej krawędzi (gdy baza wycentrowała) + `styleHint→AlignLeft` dla porządku.
Podpięty do **`self.tab_widget.setStyle(...)`** (decyduje o położeniu paska!) **ORAZ**
`self.tab_widget.tabBar().setStyle(...)`. Referencja na `self._tab_style` (GC). `setStyle` na
widżecie NIE propaguje na dzieci → reszta okna zostaje natywnie macowa; kolory/kształt/„X" z QSS bez
zmian; Linux bez regresji. Uniwersalna wersja → CLAUDE-COMMON „PUŁAPKI QT / PYQT5" pkt 5.

---

## 🪟 SESJA 2026-06-09 (wieczór) — WERSJA WINDOWS 1.0.12: zbudowana, wdrożona, zainstalowana — ⛔ TERMINAL NIE DZIAŁA (jutro zaczynamy OD TEGO)

> **Stan:** instalator Windows powstał, wdrożony na stronę + feed, **zainstalowany na realnym
> Windows**. Instalacja/okno/menu — OK. **BUG: terminal w aplikacji nie działa.**
> **➡️ JUTRO ZACZYNAMY OD NAPRAWY TERMINALA NA WINDOWS.**

### Co zrobione (W1–W5, wszystko na `main`, wydanie 1.0.12)
- **W1 terminal ConPTY:** `web_terminal.py` — backend `pywinpty` (moduł `winpty`) za tym samym
  interfejsem co `ptyprocess` (Unix). `_PTY_KIND` wybiera gałąź w
  `_spawn`/`_read_loop`/`_write_pty`/`shutdown` (winpty: read/write=`str`, `terminate()` bez `force`;
  ptyprocess: `bytes`, `terminate(force=True)`). `pywinpty` w requirements (marker `sys_platform=="win32"`).
- **W2 pakowanie:** `packaging/windows/ClaudeVoiceAssistant.spec` (onedir `.exe`, ikona `.ico`,
  `winpty` w hiddenimports, QTermWidget wykluczony) + `build-windows.ps1` (ico←png przez
  `make_ico.py` → PyInstaller → Inno) + wyjątek `.spec` w `.gitignore`.
- **W3 CI:** `.github/workflows/build-windows.yml` (runner `windows-latest`, `choco innosetup`).
- **W4 instalator+strona:** `installer.iss` (Inno, **per-user `{localappdata}` → bez UAC**, skróty,
  `CloseApplications`) + aktywny przycisk Windows na stronie pobierania.
- **W5 self-update:** `update_manager.can_self_replace`/`_windows_self_replace` — pobrany
  `Setup.exe` uruchamiany `/VERYSILENT` odłączony (DETACHED_PROCESS); Inno (Restart Manager)
  podmienia pliki i wznawia program (`[Run]`). **NIE przetestowane e2e** (1. instalacja ręczna =
  bootstrap; test self-update = wydanie 1.0.13).

### ✅ ROZWIĄZANE w 1.0.13 (2026-06-10) — patrz sekcja „SESJA 2026-06-10 (wieczór)" niżej. Pełnych przyczyn było **PIĘĆ**, nie jedna; hipoteza pywinpty była tylko częścią.

### 🔴 (ARCHIWALNE) BUG DO NAPRAWY — terminal nie działa na Windows
**Krok 1: odczytać komunikat w okienku terminala** (rozróżnia przyczynę):
- „[Terminal niedostępny: brak pywinpty…]" → `import winpty` padł = moduł NIE dołączony do `.exe`.
- „[Nie udało się uruchomić powłoki: …]" → `winpty.PtyProcess.spawn` rzucił = brak natywnych
  zależności winpty albo zły argument powłoki.

**Hipoteza nr 1 (najbardziej prawdopodobna):** PyInstaller **nie dołącza natywnych binariów
`pywinpty`** (`winpty-agent.exe`, `winpty.dll`/`conpty.dll`, `OpenConsole.exe`) — `winpty` się
importuje, ale `spawn` pada, bo helper-exe nie ma w paczce. **Fix do sprawdzenia:** w
`ClaudeVoiceAssistant.spec` dodać `from PyInstaller.utils.hooks import collect_all` i
`datas, binaries, hiddenimports += collect_all('winpty')` (lub `--collect-all winpty`).
Potem rebuild **1.0.13** + przy okazji pierwszy test self-update Windows.
Inne tropy: powłoka z `default_shell()` (COMSPEC=cmd.exe) — czy winpty chce string vs listę;
ewentualnie wymusić `powershell.exe`.

### Runbook wydania Windows (sprawdzony 1.0.12)
1. Bump `APP_VERSION` → commit/push. 2. `gh workflow run build-windows.yml --ref main` (iteracja
   na buildzie; **tag `vX.Y.Z`** = pełne wydanie mac+win + Release). 3. `gh run download <id>` → `Setup.exe`.
4. Feed: `make-appcast-entry.py Setup.exe --version X --platform windows-x64 --base-url …/cva/ --appcast … --merge`.
5. Wgraj `.exe` do `/opt/cva-web/html/cva/` (PRZED appcast), potem `appcast.json`.
6. `Setup.exe` → `/opt/cva-web/html/downloads/ClaudeVoiceAssistant-Setup.exe` (stała nazwa).
7. **Wgraj `index.html` jeśli zmieniony** (omyłka tej sesji: strona miała stary „Wkrótce", bo
   zapomniałem `scp index.html` — sam `.exe` był wgrany). 8. Weryfikacja publicznym URL.

### Uwaga o feedzie (jedna globalna `version`)
Appcast ma **jedną** `latest.version` dla wszystkich platform, a wdrożony klient czyta ją
globalnie. Dodając Windows ujednolicono **mac i win na 1.0.12** (inaczej Mac na 1.0.11 wpadłby
w pętlę aktualizacji). Mac dostał nieszkodliwą aktualizację 1.0.11→1.0.12.

---

## 🪟🏁 SESJA 2026-06-10 (wieczór) — 1.0.13: TERMINAL WINDOWS NAPRAWIONY (5 przyczyn) + FLAGA „?" (agent czeka)

> **Stan: 1.0.13 WYDANE (mac + win), feed na VPS zweryfikowany.** Terminal na Windows
> działa (potwierdzony zrzutem ekranu z żywym `cmd.exe` na maszynie CI). Nowa funkcja:
> flaga „?" na zakładce, gdy agent czeka na odpowiedź.

### 🔬 Metoda diagnozy: GitHub Actions jako środowisko GUI (Windows bez własnego Windowsa)
Nie mam Windowsa — diagnozę „pustego terminala" zrobiłem **na runnerze `windows-latest`**:
workflow **`.github/workflows/diagnose-windows.yml`** (build PyInstallerem → uruchom appkę
z kodu I spakowaną → **zrzut całego ekranu** `System.Drawing.CopyFromScreen` + zbiór logów)
+ `packaging/windows/diag_run_and_screenshot.ps1` + `packaging/windows/diag_winpty.py`
(test ConPTY bez pakowania). Artefakt `diagnose-windows` = PNG-i + logi do `gh run download`.
Każda iteracja: commit → `gh workflow run diagnose-windows.yml` → pobierz artefakt → czytaj.
**To kluczowy reużywalny wzorzec** (uniwersalna wersja → CLAUDE-COMMON).

### Pięć przyczyn „pustego pola bez kursora" (każda osobno blokowała, jedna pod drugą)
Diagnoza warstwa po warstwie (każdy fix odsłaniał następny błąd):
1. **`pygame.mixer.init()` crash bez karty dźwiękowej** (`WASAPI can't find requested audio
   endpoint`) — appka padała ZANIM pokazało okno. Maszyna CI/PC bez głośników/pulpit zdalny.
   Fix: `try/except` w `tts_engine.__init__` → `audio_available=False`, TTS wyłączone, reszta gra.
2. **`print()` z polskim znakiem na Windows** — przekierowany stdout ma **cp1252**, `print("ą")`
   rzuca `UnicodeEncodeError` (i to **w handlerze błędu TTS** → appka dalej padała). Fix u źródła:
   `sys.stdout/err.reconfigure(errors="replace")` w `main.py` + komunikat TTS w ASCII.
3. **Renderer Chromium ginął natychmiast w spakowanej appce** (`renderProcessTerminated
   status=2 exitCode=-2147483645 = 0x80000003`) → pole martwe. Sandbox Chromium vs układ
   katalogów PyInstallera. Fix: `QTWEBENGINE_DISABLE_SANDBOX=1` na Windows (wyświetlamy tylko
   lokalny `terminal.html`, więc bezpieczne).
4. **PyQtWebEngine-Qt5 5.15.2 na Windows = Chromium 83**, a xterm.js 5.x używa
   `Element.replaceChildren` (Chromium **86+**) → JS padał (`replaceChildren is not a function`)
   → terminal nie powstawał. Na macOS Qt jest nowszy, więc tam działało. Fix: **polyfill**
   `replaceChildren` w `terminal.html` PRZED `vendor/xterm.js` (no-op na nowszym Chromium).
5. **Niedołączone natywne binaria `pywinpty`** (hipoteza z 2026-06-09, potwierdzona połowicznie):
   paczka 1.0.12 miała tylko 3 z 5 plików — brakowało `winpty-agent.exe` i `OpenConsole.exe`.
   Fix: `collect_all('winpty')` w `ClaudeVoiceAssistant.spec` (`datas/binaries/hiddenimports +=`).
   To NIE była przyczyna „pustego pola" (dałoby czerwony komunikat), ale i tak konieczne.

**Plus 2 błędy poboczne (regresja od naprawy Windows):**
- **`_update_status` crashował na braku `status_bar`** przy starcie (pierwszy `addTab` emituje
  `currentChanged` zanim powstanie pasek). Guard `getattr(self,'status_bar',None)`.
- **Terminal znikał przy starcie po naprawieniu (a) tego crasha** — tamten `AttributeError`
  PRZYPADKIEM chronił przed za wczesną aktywacją zakładki (QTermWidget/WebTerminal w
  niezamontowanym kontekście = niewidoczny). Jawny guard **`self._ui_ready`** (False przez
  cały `__init__`, True na końcu) w `_on_tab_changed`; primary tab aktywuje odroczony QTimer.

### Komunikat awarii zamiast martwego pola (web_terminal.py)
Doszły: log `~/.claude-voice-assistant/webterminal.log` (cykl życia + konsola JS przez
`_LoggingWebEnginePage.javaScriptConsoleMessage`), obsługa `loadFinished`/
`renderProcessTerminated` + watchdog 10 s → strona błędu zamiast pustego pola. **Uwaga:**
log Chromium (`--enable-logging`) na Windows otwiera **czarne okna konsoli**
`QtWebEngineProcess.exe` — dlatego TYLKO pod `CVA_WEBENGINE_LOG=1` (domyślnie off;
`webterminal.log` w zupełności wystarcza do diagnozy).

### Funkcja: flaga „?" — agent czeka na odpowiedź (zakładki)
Pomarańczowa ikona SVG „?" (`src/assets/icons/question.svg` — NIE emoji: monochromat na
Linuksie) na **nieaktywnej** zakładce, gdy jej agent zatrzymał się i czeka na decyzję. Znika
po wejściu na zakładkę lub odpowiedzi. **Wykrywanie z dziennika sesji, NIE ze strumienia
terminala** (terminal zawodny: zniekształcone kodowanie ramek/`❯`, a popup **AskUserQuestion
zapisuje wpis `tool_use` do dziennika DOPIERO po odpowiedzi** → przy pytaniu z opcjami ostatnim
wpisem zostaje `user`!). Finalny sygnał: **`transcript_reader.waiting_for_user()` — plik sesji
STOI ~1,6 s (2-tick) = agent czeka; rośnie = pracuje** (rola ostatniego wpisu nieistotna,
byle rozmowa ruszyła). Łapie jednym warunkiem: pytanie tekstem, AskUserQuestion, prośbę o zgodę
Write/Edit/Bash, „skończyłem — co dalej?". GUI: `_arm_question`/`_refresh_question_flag`
(ikona tylko gdy uzbrojona I nieaktywna)/`_refresh_all_question_flags` (przy zmianie zakładki);
sprawdzane CO TICK w `_poll_transcripts` (nie zależy od nowej prozy).

### Bonus: przypięcie sesji w transcript_reader (naprawia też auto-czytanie)
`TranscriptReader.set_working_directory` zapamiętuje `_preexisting` (pliki .jsonl istniejące
przy starcie zakładki); `_newest_session_file` bierze TYLKO plik powstały PO starcie. Dzięki
temu **równoległa sesja Claude Code w tym samym katalogu** (np. nasza w CVA) nie jest podczepiana
— wcześniej zakładka czytała cudzy dziennik (psuło flagę I auto-czytanie głosem).

### Wydanie 1.0.13 — przebieg (runbook potwierdzony)
Bump `APP_VERSION` → tag `v1.0.13` → Actions buduje **mac+win naraz** (oba na `push: tags`,
publikują do jednego Release) → `gh release download v1.0.13` → wgranie na VPS: `.zip`+`.exe`
do `cva/` **PRZED** `appcast.json`, `.dmg`/`Setup.exe` do `downloads/` pod stałą nazwą (+ backup
1.0.12) → `make-appcast-entry.py` ×2 (`--platform windows-x64` dla exe) → weryfikacja publicznym
URL: version=1.0.13, HTTP 200, **content-length I sha256 na serwerze == feed**. Commity:
`6a511b3` (flaga), `f23b22a` (bump), `e5e9630` (feed).

### 🟢 POTWIERDZONE NA REALNYM WINDOWS (2026-06-10 noc) — terminal działa, onboarding Claude Code
Użytkownik zainstalował 1.0.13 na swoim Windows (10.0.19045) i **terminal DZIAŁA** (zrzut:
`Microsoft Windows [Version ...]` + znak zachęty `C:\Users\HP\Desktop\Projekty>`, `cmd.exe`
odpowiada, Enter działa). **Bug pustego terminala definitywnie zamknięty na żywej maszynie.**

**KOREKTA wcześniejszej notatki:** Windows 1.0.12 **JEDNAK wykrył** aktualizację 1.0.13
(okno „Dostępna aktualizacja" + start pobierania) — czyli mechanizm self-update (feed+detekcja)
działa też na Windows, wbrew wcześniejszemu założeniu „1.0.12 sama się nie zaktualizuje".
**Padło tylko POBIERANIE:** `[SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC] (_ssl.c:2580)`
**konsekwentnie pod koniec** ~100 MB pliku. Serwer OK (pełne `curl` z zewnątrz + sha256 zgodne).
Objaw „pada pod koniec dużego pobierania" = klasyczny **TLS 1.3 KeyUpdate** w starym OpenSSL
spakowanego Pythona **albo antywirus/firewall** psujący rekord. **Obejście dla usera:** pobranie
**przez przeglądarkę** z PUBLICZNEGO linku (bez logowania — `/cva/` jest publiczne):
`https://pobierz.srv1251441.hstgr.cloud/cva/ClaudeVoiceAssistant-Setup-1.0.13.exe` → zadziałało.

**Onboarding Claude Code na świeżym Windows (app jest „pilotem", NIE zawiera CLI):** po instalacji
1.0.13 terminal działał, ale `claude` → `'claude' is not recognized`. Trzeba u usera **doinstalować
CLI**: (1) Node.js LTS z nodejs.org (instalator GUI), (2) `npm install -g @anthropic-ai/claude-code`
(„added 2 packages" = OK), (3) restart aplikacji (wtedy `find_claude_command` znajdzie
`%APPDATA%\npm\claude.cmd`), (4) `claude` → logowanie OAuth. **Pułapka Node.js:** instalator ma
opcję „Tools for Native Modules" → uruchamia PowerShell z Chocolatey/VS Build Tools, który sypie
groźnie wyglądającymi błędami („Didn't find any channel feed", „RequestCanceled") — **nieistotne
dla nas, zamknąć okno**. **Logowanie:** w WebTerminalu przeglądarka NIE otworzyła się sama →
Claude Code pokazuje URL OAuth + „c to copy" (naciśnij `c` = kopiuje link do schowka systemowego;
wklej w przeglądarce, zaloguj, skopiuj kod, wklej w „Paste code here >"). NIE przepisywać URL
ręcznie (300+ znaków, jedna literka psuje PKCE). Lekcja UX: dla nie-programisty rozpisuj
DOSŁOWNIE każdy klik, tłumacz „co to terminal", preferuj kopiuj-wklej nad pisaniem.

### 🔧 DO ZROBIENIA NASTĘPNA SESJA — uodpornić pobieranie updatera (1.0.14)
`update_manager._download_worker` (linia ~171) pobiera **jedną próbą** `requests.get(stream=True)`
— stąd `BAD_RECORD_MAC` ubija całość. Plan (zaproponowany, NIEzaimplementowany): **wymusić TLS 1.2**
(custom `SSLContext maximum_version=TLSv1_2` — typowy fix na KeyUpdate) + **pobieranie kawałkami
przez `Range`** (mniej danych/połączenie + wznawianie) + **ponawianie 3×**. Wejdzie do 1.0.14 =
przy okazji pierwszy realny test self-update Windows (1.0.13→1.0.14).

### 📘 DO ZROBIENIA (priorytet usera, 2026-06-10) — SZCZEGÓŁOWA INSTRUKCJA INSTALACJI dla 3 systemów
Napisać **bardzo szczegółową instrukcję instalacji krok-po-kroku dla NIE-programisty** (Windows,
macOS, Linux), obejmującą **doinstalowanie programów dodatkowych**, których aplikacja wymaga, a
których NIE zawiera (jest „pilotem" nad Claude Code CLI). Powód: dzisiejszy onboarding na Windows
pokazał, że sama instalacja `.exe`/`.dmg` to za mało — user utknął na braku `claude` (Node.js +
`npm i -g @anthropic-ai/claude-code` + logowanie OAuth). Wymagania instrukcji:
- **Per system:** Windows (Node.js LTS z nodejs.org → npm install → restart → login), macOS
  (Node przez instalator lub brew → npm install → login), Linux (Node + npm install; QTermWidget z wheela).
- **Język laika:** wyjaśnić „co to terminal", każdy klik dosłownie, zrzuty/oczekiwany widok na każdym kroku.
- **Pułapki do uwzględnienia:** Node.js „Tools for Native Modules" (groźne błędy VS Build Tools — zignorować);
  logowanie gdy przeglądarka się nie otwiera („c to copy", nie przepisywać URL ręcznie); literówki
  (`cloude`≠`claude`) → preferuj kopiuj-wklej; restart aplikacji po instalacji `claude`.
- **Forma:** prawdopodobnie strona „Pierwsze kroki" na stronie pobierania (`packaging/web/`) i/lub
  `docs/INSTALL.md`. Rozważyć też, czy aplikacja może **wykryć brak Node/claude** i pokazać
  przyjazny kreator instalacji zamiast surowego `'claude' is not recognized`.

### ⏭️ Pozostałe TODO
- [ ] **macOS** zaktualizuje się sam 1.0.12→1.0.13 (mechanizm sprawdzony) — do potwierdzenia.
- [ ] Diagnostyczne logi/workflow nieinwazyjne (gated), mogą zostać; `qflag.log` już nie pisany.

---

## 🤖 PRZEPIS: JAK DODAĆ NOWY MODEL CLAUDE CODE DO APLIKACJI (2026-06-10)

Aplikacja **nie hostuje modelu** — jest „pilotem" nad CLI Claude Code: uruchamia
`claude --model <klucz>` (`main_window.py` ~`1839`, dolepia `--model` gdy agent ma model
≠ `default`). Dodanie modelu = **jeden plik `src/config.py`**, bo lista jest tam
**jedynym źródłem prawdy** — lista rozwijana w konfiguracji agenta (`dialogs.py` iteruje
`CLAUDE_MODELS`), panel „Zarządzaj agentami" (`CLAUDE_MODELS_SHORT`) i licznik tokenów
(`CLAUDE_MODEL_CONTEXT_LIMITS`) **same się z tego zasilają**.

**Kroki:**
1. **Zweryfikuj alias na żywo** (zanim dopiszesz): `claude --model <alias> -p "OK"` → exit 0
   = Claude Code przyjmuje ten alias. (Tak potwierdzono `fable` = Fable 5; działa też pełny
   `claude-fable-5`.) Aliasy `opus`/`sonnet`/`haiku`/`fable` rozwiązują się po stronie Claude
   Code na najnowszą wersję — etykiety w `config.py` są tylko informacyjne.
2. **Dopisz ten sam klucz do WSZYSTKICH 3 słowników** (`CLAUDE_MODELS`,
   `CLAUDE_MODELS_SHORT`, `CLAUDE_MODEL_CONTEXT_LIMITS`) — inaczej np. licznik tokenów nie
   zna okna i bierze fallback. Weryfikacja spójności: `set(A)==set(B)==set(C)`.
3. `NEW_AGENT_DEFAULT_MODEL` zmieniaj tylko świadomie (zostaje **Opus** — tańszy od Fable).
4. Test po zmianie: `python3 -m py_compile src/config.py` + odpalenie appki (model na liście,
   Stop→Uruchom agenta, realna odpowiedź).

**Fable 5 (dodany, commit `a6c59aa`):** alias `fable`, okno kontekstu **1M = jak Opus 4.8**,
max output 128K, ale **~2× droższy** ($10/$50 vs $5/$25 za mln tok.) → szybciej zużywa limit
planu. **Rozliczenie:** do **22.06.2026** wliczony w subskrypcję bez dopłat (ale „draws from
your plan's usage"); po tej dacie warunki mogą się zmienić (koniec maila był ucięty). Dlatego
domyślny = Opus; Fable do świadomego wyboru przy najtrudniejszych zadaniach. Etykiety
przy okazji zaktualizowane Opus 4.7 → **Opus 4.8** (Fable 5 to nowy tier nad Opusem).

**Kiedy używać Fable vs Opus (wskazówka dla usera).** Programowanie na Fable działa
**identycznie** jak na Opusie — w aplikacji tylko wybierasz „Fable 5" w konfiguracji agenta
(Stop→Uruchom), reszta workflow bez zmian (`claude --model fable`). **Fable** = duże/wielokrokowe
refaktory, trudne bugi „przez wiele warstw", długie zadania „odpal i zostaw", głęboki research,
trudne code review. **Opus (domyślny)** = bieżączka: drobne poprawki, pojedyncze pliki, szybkie
pytania — taniej zużywa limit. Praktyka: **dwóch agentów w zakładkach** (Opus do bieżączki +
Fable do ciężkich zadań), przełączanie wg potrzeby.

---

## 🛠️ SESJA 2026-06-11 — NAPRAWA FLAGI „?" (cisza terminala) + onboarding (kreator, instrukcje WWW, instalator z Node.js) + hardening updatera

> **AKTUALIZACJA (koniec sesji): 1.0.14 WYDANE** (bump `78161f8`, feed `0ce41f3`) —
> buildy mac+win zielone, paczki + appcast na VPS, weryfikacja publicznym URL:
> version=1.0.14, HTTP 200, **sha256 serwer == feed == release** (potrójna zgodność).
> Stare instalatory 1.0.13 zachowane jako `.bak` w `downloads/`.
>
> **⏭️ NA JUTRO (user sprawdza, 2026-06-12):**
> - [ ] **Mac**: samo-aktualizacja 1.0.13→1.0.14 (mechanizm sprawdzony — oczekiwane OK).
> - [ ] **Windows**: PIERWSZY realny test self-update (1.0.13→1.0.14). UWAGA:
>       pobieranie pójdzie jeszcze STARYM kodem (bez TLS 1.2) → możliwy znany błąd
>       `SSL DECRYPTION_FAILED_OR_BAD_RECORD_MAC` pod koniec ~100 MB; obejście =
>       przeglądarka, publiczny link `…/cva/ClaudeVoiceAssistant-Setup-1.0.14.exe`.
>       **Od 1.0.14 w górę pobieranie jest już odporne** (TLS 1.2 + Range + retry).
> - [ ] Test zadania „nodecli" instalatora na świeżym Windows — nadal otwarty.

### 🚩 Naprawa flagi „?" (commit `a3fd485`) — cisza dziennika to ZA MAŁO
Objaw: flaga zawsze włączona, nie znikała nawet gdy agent pisał. Przyczyna (zmierzona
eksperymentem): **dziennik .jsonl dostaje WYŁĄCZNIE ukończone wpisy** — podczas generowania
odpowiedzi plik stał **20,4 s**, potem cały tekst wpadł jednym wpisem → warunek „plik stoi
1,6 s = czeka" był spełniony przez większość czasu PRACY agenta. **Fix: drugi sygnał = puls
terminala.** Pracujący Claude Code animuje pasek (spinner + licznik sekund ~1×/s) → dane płyną
ciągle (zmierzone w PTY: max przerwa **0,96 s** przy generowaniu; po zakończeniu cisza 8+ s).
Flaga = `reader.waiting_for_user()` **AND** `monotonic() - tab._last_terminal_data_ts >=
MainWindow.QUESTION_TERMINAL_QUIET_SECS (3.0)`. Znacznik aktualizowany w
`AgentTab._on_terminal_output` (PO guardzie `terminal_backend`); czytnik dziennika wołany
ZAWSZE (nie za leniwym `and`) — świeży licznik stabilności. Potwierdzone przez usera na żywo.
Korekta uniwersalna → CLAUDE-COMMON „INTEGRACJA Z CLI/TUI" pkt 4 (stary wpis był błędny).

### 🔄 Hardening pobierania aktualizacji (commit `f57fb58`) — wejdzie w 1.0.14
`update_manager._download_worker` przepisany: wymuszony **TLS 1.2** (`_tls12_session` —
HTTPAdapter z `maximum_version`; omija KeyUpdate/`BAD_RECORD_MAC` z Windowsa), pobieranie
**segmentami 8 MB przez `Range` z wznawianiem** (`_download_resumable`; serwer bez Range →
pełny strumień), **3 ponowienia** bez postępu (postęp zeruje licznik), sha256 liczone PO
całości, plik `.part` → docelowa nazwa dopiero po weryfikacji. Przetestowane na żywym feedzie:
pełne 102 MB w 43 s + wznowienie od 60 MB, sha zgodne. Do userów trafi w 1.0.14 — wtedy
1. realny test self-update Windows.

### 🧭 Kreator „Dokończ instalację" przy braku `claude`
`dialogs.ClaudeSetupDialog` — 3 kroki (nodejs.org → `npm install -g @anthropic-ai/claude-code`
→ `claude` + login „c to copy"), pułapki Windows („Tools for Native Modules"); przycisk
„Sprawdź ponownie" → sygnał `claude_found` → MainWindow podmienia `claude_command` bez restartu
(`_on_claude_cli_found` + `_save_settings`). Start: `_maybe_show_claude_setup` (QTimer 1500 ms,
raz na sesję) gdy `_claude_cli_available()`=False (pełna ścieżka LUB `shutil.which` 1. członu
komendy). Ręcznie: **menu Pomoc → „Jak zainstalować Claude Code…"**.
`config.INSTALL_GUIDE_BASE_URL` = `https://pobierz.srv1251441.hstgr.cloud/cva/` (publiczne).

### 🌐 Strony WWW (wdrożone, `/opt/cva-web/html/`)
- **`cva/instrukcja-{windows,macos,linux}.html`** — instalacja krok po kroku dla laika
  (PUBLICZNE — aplikacja może je otwierać bez logowania). Win/mac pełne (SmartScreen/
  Gatekeeper, Node + pułapki, npm, login OAuth, FAQ, klucz Groq → `console.groq.com/keys`);
  Linux = uczciwe „AppImage w przygotowaniu".
- **`cva/instrukcja-agenci.html`** — „Zarządzaj agentami" dla laika: każdy przycisk managera
  (▲▼/▶️/➕/✏️/📋/🗑️, zielone vs szare tło = auto-start), 4 zakładki konfiguracji pole po polu,
  przepis „pierwszy agent w 6 krokach", FAQ. Link w aplikacji: **menu Pomoc → „Instrukcja:
  Zarządzaj agentami…"** (`_open_agents_guide`).
- **`index.html`**: linki 📖 przy kafelkach, **Linux „⏳ Wkrótce"** (przycisk prowadził do
  nieistniejącego AppImage = 404!), wersja w stopce dynamicznie z `cva/appcast.json`.

### 🪟 Instalator Windows — zadanie „nodecli" (commity `f57fb58`+`892009e`) — wejdzie w 1.0.14
`installer.iss`: checkbox (domyślnie ✓) „Pobierz i zainstaluj Node.js + Claude Code",
pokazywany TYLKO gdy czegoś brakuje (`NodeCliMissing` — node/claude wykrywane w Program Files
ORAZ w PATH przez `where` → łapie nvm/scoop/winget/choco). wpReady: pobiera `dist/index.json`
→ parsuje najnowsze LTS (pierwsze `"lts":"`, ostatnie `"version":"` przed nim — algorytm
zweryfikowany na żywych danych nodejs.org) → pobiera MSI; ssPostInstall: `msiexec /passive`
(1× UAC — Node instaluje się systemowo) → `npm.cmd install -g` (pełna ścieżka, bo PATH
instalatora nie zna świeżego Node; fallback npm z PATH). Przy `/VERYSILENT` (self-update)
NIGDY się nie odpala (brak wpReady → `NodeMsiReady=False`). Błędy ŁAGODNE (komunikat,
instalacja idzie dalej — kreator w aplikacji dokończy). Build CI zielony; **e2e na realnym
Windows NIEtestowane** — przy 1.0.14.
**Pułapki .iss:** plik MUSI być **UTF-8 Z BOM** (bez BOM Inno czyta ANSI → krzaki w polskich
komunikatach [Code]); `{tmp}` w komentarzu klamrowym Pascala **ZAMYKA komentarz** → syntax
error (kosztowało 1 build CI).

### ⏭️ TODO przy wydaniu 1.0.14
- [ ] Bump + tag v1.0.14 → build mac+win → feed (runbook jak 1.0.13).
- [ ] 1. realny test self-update Windows (1.0.13→1.0.14) = zarazem test fixu TLS/Range.
- [ ] Test instalatora z „nodecli" na świeżym Windows (checkbox, Node z MSI, npm, UAC).
- [ ] Uzupełnić `instrukcja-linux.html` przy premierze AppImage + aktywować przycisk Linux.

---

## 🛠️ SESJA 2026-06-12 — suwak nowych zakładek + czarna strona po zamknięciu zakładki + WYDANIE 1.0.15

> **Stan: 1.0.15 WYDANE** (bump `96c45b6`, feed `dad967b`) — buildy mac+win zielone,
> paczki + appcast na VPS, weryfikacja publicznym URL: version=1.0.15, HTTP 200,
> **sha256 lokalnie == serwer == feed** (potrójna zgodność). Stare instalatory 1.0.14
> zachowane jako `.bak` w `downloads/`. Runbook jak 1.0.13/1.0.14 — działa bez zmian.

### 🔧 Naprawa 1: nowa zakładka miała inne proporcje suwaka (commit `b8a39af`)
Objaw: nowy agent / nowy terminal „+" pokazywał suwak terminal↔panel dolny dużo
wyżej (gruby panel) niż używane zakładki. Przyczyna: każda NOWA zakładka dostawała
sztywny fabryczny `[600, 150]` (~80/20), a używane zakładki miały zapisane ~`[1500, 187]`
(~89/11) w `agents.json` (zapis per zakładka przy ruchu suwaka, `_on_splitter_changed`).
Fix:
- `config.py`: **`DEFAULT_SPLITTER_SIZES = [1500, 190]`** — JEDYNE źródło prawdy
  (cienki panel dolny dla świeżych instalacji Win/Mac/Linux); `DEFAULT_AGENTS` z niej korzysta.
- `main_window.py`: **`_inherit_splitter_sizes(config)`** — nowa zakładka dziedziczy
  proporcje z AKTYWNEJ zakładki; wpięte we wszystkie 3 drogi tworzenia: `_add_new_agent`,
  `_show_agents_manager_dialog` (agents_to_run), `_add_new_terminal` („+").
- `dialogs.py` `get_data()`: NIE wpycha już defaultu nowemu agentowi — `splitter_sizes`
  przekazuje tylko przy edycji agenta, który już je miał (inaczej dziedziczenie nigdy
  by nie zadziałało, bo klucz istnieje).
- `agent_tab.py`: fallback z `config.DEFAULT_SPLITTER_SIZES` (był sztywny literal).
- Dane: `~/.claude-voice-assistant/agents.json` — Fable 5 i Strona F-P poprawione
  `[600,150]` → `[1503,187]`; backup `agents.json.bak-2026-06-12`.

### 🔧 Naprawa 2: czarna strona po zamknięciu zakładki (commit `c85e451`)
Objaw: zamknięcie zakładki X-em pokazywało czarną stronę bez terminala. Przyczyna:
zakładka **„+" to pusta atrapa-przycisk** (goły `QWidget`, czarne tło) — po
`removeTab()` aktywnej zakładki **Qt samo wybiera sąsiada**, który wskoczył na jej
indeks; przy ostatniej zakładce przed „+" jest nim właśnie atrapa. Druga wada: przy
zamykaniu środkowej Qt aktywowałoby sąsiada (lazy activation → niechciany start claude).
Fix (wszystko `main_window.py`):
- **`self._tab_mru`** — historia ostatnio używanych zakładek (agent_id, najnowsza na
  początku), aktualizowana w `_on_tab_changed`.
- **`_close_agent_tab`**: przy zamykaniu AKTYWNEJ zakładki najpierw
  `setCurrentWidget(cel z MRU)`, DOPIERO POTEM `removeTab` — wybór świadomy, „+"
  nigdy nie zostaje aktywna, brak przypadkowej aktywacji sąsiada.
- **`_most_recent_tab(exclude)`**: MRU → fallback ostatnia prawdziwa zakładka przed
  „+"; jawnie pomija zakładkę właśnie zamykaną (wciąż wisi w pasku do `removeTab`).

**⚠️ LEKCJA QT (decyzją usera trzymana tu, nie w COMMON):** `QTabWidget.removeTab()`
aktywnej zakładki oddaje wybór następnej Qt — z pseudo-zakładką „+" (atrapa-przycisk
na końcu paska) Qt potrafi uaktywnić właśnie ją (pusty/czarny widok), a przy
lazy-activation przypadkiem aktywować ciężkiego sąsiada. **Reguła: najpierw
`setCurrentWidget(cel)` (np. z własnej historii MRU), potem `removeTab`** — zero
stanu pośredniego. Dotyczy każdego miejsca w aplikacji, które usuwa zakładki.

### ℹ️ FAQ: pominięcie kilku wersji = bezpieczny przeskok prosto do najnowszej
Aktualizacje są **pełnopaczkowe** (cały `.app`/`Setup.exe`), NIE przyrostowe — appcast
ma zawsze JEDNĄ pozycję `latest`, więc klient z dowolnej starszej wersji skacze
bezpośrednio do najnowszej ze wszystkimi poprawkami po drodze; ustawienia usera
(`~/.claude-voice-assistant/`) są poza programem i przeskok ich nie rusza.
Jedyne wyjątki: **Mac ≤1.0.7** (martwy apex-URL feedu — nie zobaczy aktualizacji,
trzeba raz ręcznie z `.dmg`), **Windows 1.0.12–1.0.13** (wykryje i skoczy, ale kruchy
downloader — możliwy SSL BAD_RECORD_MAC pod koniec ~100 MB; obejście: przeglądarka,
publiczny link `/cva/`). Od Win 1.0.14 i Mac 1.0.8 przeskok dowolnej liczby wersji = OK.

### ⏭️ TODO następna sesja (user sprawdza)
- [ ] Self-update **Mac** i **Windows** — teraz test 1.0.14→1.0.15; na Windows to
      **pierwszy realny test odpornego downloadera** (TLS 1.2 + Range + retry z 1.0.14).
      Checklista 1.0.13→1.0.14 z 2026-06-11 nie została dziś potwierdzona.
- [ ] Test zadania „nodecli" instalatora na świeżym Windows — nadal otwarty.
- [ ] Uzupełnić `instrukcja-linux.html` przy premierze AppImage + aktywować przycisk Linux.

---

## 🌍 SESJA 2026-06-15 — PEŁNA ANGIELSKA WERSJA (program + strona) + WYDANIE 1.0.16

> **Stan: 1.0.16 WYDANE (mac+win), feed na VPS zweryfikowany.** Cały interfejs + strona WWW/FAQ dwujęzyczne (PL/EN). Domyślny język = **ANGIELSKI** (PL tylko gdy system operacyjny polski).

### i18n aplikacji (A1: chrome, A2a: status, A2b: dialogi)
- **Centralny tłumacz `config.t(key)`** czyta globalny `_CURRENT_UI_LANGUAGE` — działa też w oknach dialogowych (osobne klasy). Import w GUI: `from config import t as tr`.
- Napisy = klucze w `config.UI_TRANSLATIONS` (3 języki `pl-PL`/`en-US`/`en-GB`, **parytet OBOWIĄZKOWY** `set(pl)==set(us)==set(gb)`, ~640 kluczy; en-GB = pisownia brytyjska).
- `detect_system_language()` (1. start): **DOMYŚLNIE en-US**; `pl*`→pl-PL; `en-GB/en-UK`→en-GB. Zapisany `language` ma pierwszeństwo. `_set_language→set_ui_language→_update_ui_language` odświeża menu+zakładki **na żywo** — przebudowa menu USUWA stare QAction-y (+ ich skróty) PRZED odbudową, inaczej kumulacja Ctrl+N/Ctrl+T → „ambiguous shortcut".
- Helpery w config: `model_label()/model_label_short()/model_default_prefix()` (etykiety modeli), `install_guide_url(name)` (zwraca instrukcję `-en` gdy interfejs EN).
- **Robota mechaniczna (dialogs.py + dialogi w main_window) zrobiona 2 subagentami** wg ścisłego wzorca; potem NIEZALEŻNA weryfikacja (kompilacja, parytet kluczy, każdy `tr()` istnieje, brak polskich diakrytyków w setterach UI, parytet placeholderów `{..}`, import). Wzorzec → CLAUDE-COMMON.
- **BUG naprawiony:** import względny `from ..config import` w `gui/main_window.py` (helpery skórki `_skin_color_name`/`_skin_icon_name` + „Przywróć domyślne") → `ImportError: beyond top-level package` (moduł działa jako top-level `gui.*`, `src` na ścieżce). Zawsze **absolutnie** `from config import`. Crashował okno „Zmień kolory i skórki" w OBU językach.

### Strona WWW EN (osobne pliki `-en` + dropdown)
- Przełącznik = **rozwijane menu** `<details class="lang-switch">` (English-first, skalowalne na kolejne języki) na 5 stronach PL; angielskie kopie: `index-en.html` + `instrukcja-{windows,macos,linux,agenci}-en.html` (FAQ przetłumaczone). Wzorzec CSS/HTML w `index.html`.
- Układ VPS: `index*.html` w `/opt/cva-web/html/`, instrukcje w `/opt/cva-web/html/cva/` (publiczne). Deploy `scp` **kluczem SSH** (po rotacji 2026-06-15 — bez sshpass).

### Wydanie 1.0.16 — runbook bez zmian
bump→tag `v1.0.16`→Actions mac+win→`gh release download`→`.zip`+`.exe` do `/cva/` PRZED appcast, `.dmg`/`Setup.exe` do `downloads/` (stałe nazwy + backup 1.0.15)→`make-appcast-entry.py` ×2 (--merge)→`scp appcast.json`→weryfikacja publicznym URL (version=1.0.16, content-length==rozmiar, **sha256 potrójnie zgodne**). Commity: `d1afe84` (bump), `da39dd6` (feed).
- **`gh` zalogowany NA STAŁE (keyring)** po dzisiejszej rotacji PAT — przyszłe wydania w pełni automatyczne (jak re-auth gh bez wpisywania tokena → CLAUDE-COMMON).

### Na następną sesję
- [x] **Windows (≥1.0.14) sam zaktualizował się do 1.0.16 — ✅ POTWIERDZONE na realnej maszynie 2026-06-16.** Pierwszy realny test odpornego downloadera (TLS 1.2 + Range + retry z 1.0.14) — przeszedł, cały przebieg pomyślny, bez błędu `SSL DECRYPTION_FAILED_OR_BAD_RECORD_MAC`. Self-update Windows zamknięty end-to-end.
- [ ] Potwierdzić, że Mac (≥1.0.8) sam zaktualizował się do 1.0.16 (angielska wersja).
- [ ] Kolejne języki: dopisać słownik w `UI_TRANSLATIONS` (parytet!) + `SUPPORTED_LANGUAGES` + `detect_system_language` + pliki `-xx.html` + pozycja w dropdownie. Architektura: pamięć projektu `i18n-architektura.md`.

---

## 🪟✅ SESJA 2026-06-16 — SELF-UPDATE WINDOWS POTWIERDZONY E2E (1.0.16)

> **Kamień milowy:** użytkownik potwierdził, że Windows **sam zaktualizował się do najnowszej wersji (1.0.16)** na realnej maszynie — cały przebieg pomyślny. To **pierwszy potwierdzony end-to-end self-update na Windows** i zarazem pierwszy realny test odpornego downloadera (TLS 1.2 + Range + retry) wprowadzonego w 1.0.14.

- **Co to zamyka:** ciągnący się od 1.0.12 wątek niepewności wokół pobierania aktualizacji na Windows — wcześniej padał `SSL DECRYPTION_FAILED_OR_BAD_RECORD_MAC` pod koniec ~100 MB (jedyne obejście = pobranie przez przeglądarkę). Hardening z 1.0.14 (`update_manager._download_worker`: wymuszony TLS 1.2 + pobieranie segmentami przez `Range` z wznawianiem + retry 3×) **działa w praniu** — pełna paczka pobrała się bez błędu, podmiana przez instalator Inno (`/VERYSILENT`, Restart Manager) i restart zadziałały.
- **Stan mechanizmu self-update:** macOS (od 1.0.8) ✅ potwierdzony wielokrotnie; **Windows (od 1.0.14) ✅ potwierdzony teraz**; Linux = nadal brak paczki (AppImage do dorobienia).
- **Pozostaje na później:** potwierdzić jeszcze samo-aktualizację **Mac** do 1.0.16; test zadania „nodecli" instalatora na świeżym Windows; Linux AppImage (+ `instrukcja-linux.html` + aktywacja przycisku Linux na stronie).

---

## 🐧🛠️ SESJA 2026-06-16 (popołudnie) — LINUX APPIMAGE 1.0.16: start Claude + czytelna czcionka (odzysk po awarii) — commit `d65857f`

> **Kontekst:** komputer zawiesił się w trakcie poprzedniej sesji (dziennik `be2b7aff`, urwany 13:16). Praca **nie przepadła** — niezacommitowane zmiany przetrwały na dysku (edytor zapisuje od razu); odtworzony przebieg z dziennika `.jsonl`, kod nieuszkodzony (kompiluje się). Lekcja procesowa: po awarii NAJPIERW `git status` / `git stash list` / `git reflog` + ostatni dziennik sesji `~/.claude/projects/<cwd>/*.jsonl` (zawiera całą rozmowę i akcje) — zwykle wszystko jest, brakuje tylko commita.

### 🚩 Pułapka #1 — `claude` nie startował w AppImage (WebTerminal): wejście przed startem powłoki
**Objaw:** świeżo uruchomiona paczka AppImage (lub prawy-klik ikony → „New Window") nie odpalała Claude w terminalu — pusty bash albo „command not found".
**Przyczyna:** powłoka WebTerminala startuje dopiero po `frontend_ready` (gdy xterm.js się załaduje — w AppImage bywa ~2 s przy wolniejszym QtWebEngine). Komenda `claude` / wiadomość pamięci przychodziła WCZEŚNIEJ, a `_write_pty` przy `self._proc is None` gubił ją po cichu.
**Fix (`web_terminal.py`):** `self._pending_input = []` w `__init__`; `_write_pty` przy braku powłoki **buforuje** zamiast gubić; `_spawn()` po starcie opróżnia bufor w kolejności wysłania (log „spawn: opróżniam bufor wejścia (N fragm.)"). Potwierdzone na realnym ekranie (Claude startuje sam).

### 🔤 Pułapka #2 — czcionka nieczytelna w WebTerminal: PUNKTY vs PIKSELE
**Objaw:** w AppImage (WebTerminal/xterm.js) litery ~30% mniejsze i nieczytelne, mimo że stara wersja (QTermWidget, uruchamiana z kodu przez `run-safe.sh`) miała duże.
**Przyczyna (root):** wspólny interfejs `terminal_backend.set_font(family, size)` przekazuje rozmiar w **PUNKTACH** — `QTermWidgetBackend` robi z „13" `QFont(13 pt)` (~17 px), a `WebTerminalBackend`→`web_terminal._push_font` wstawiał `term.options.fontSize = 13` gdzie xterm.js liczy w **PIKSELACH**. Ten sam „13", dwie jednostki.
**Fix (`web_terminal.py` + `terminal.html`):** w `_push_font` przelicznik CSS `px = round(size * 96/72)` → 13 pt = **17 px**; wartość startowa `fontSize: 17` w `terminal.html` (żeby nie „mrugało" mniejszym przy 1. klatce). Wizualnie 1:1 z QTermWidget. Potwierdzone na ekranie.
**Reguła:** WebTerminal (xterm.js) to JEDYNY backend liczący czcionkę w px — konwersja pt→px MUSI siedzieć na jego styku (`web_terminal`), nie w wywołującym; reszta programu i config posługują się punktami (jak QFont).

### Pozostałe
- `packaging/linux/build.sh` — przebudowa skryptu AppImage (WebTerminal w paczce, QTermWidget wykluczony ze `.spec`, `CVA_SKIP_DEPS=1` do szybkich rebuildów, czytelne logi etapów). Build: `CVA_SKIP_DEPS=1 bash packaging/linux/build.sh` → `dist/ClaudeVoiceAssistant-1.0.16-linux-x64.AppImage`.
- Dwa skróty `.desktop` na maszynie usera: zwykła ikona „Claude Voice Assistant" → `run-safe.sh` (kod źródłowy = **QTermWidget** na Linuksie!), a „…(AppImage 1.0.16 — test)" → paczka = **WebTerminal**. Do testów WebTerminala używać ikony AppImage (albo z kodu `CVA_WEBTERMINAL=1`).
- Nauki uniwersalne (odzysk po awarii z dziennika `.jsonl`; jednostki czcionki terminala pt-vs-px) → kandydaci do `CLAUDE-COMMON.md`.

### ⏭️ ZAPLANOWANE NA NASTĘPNĄ SESJĘ — LINUX SELF-UPDATE (od zera do działania)

> **Cel:** Linux ma się aktualizować sam, jak macOS (od 1.0.8) i Windows (od 1.0.14). Dziś NIE działa z DWÓCH niezależnych powodów: (a) feed na serwerze NIE ma wpisu `linux-x64` (apka raportuje `update_platform_id()=="linux-x64"`, a w `appcast.json` są tylko `macos-arm64`+`windows-x64` → `_parse_appcast` zwraca None → cicho `no_update`); (b) `update_manager.can_self_replace()` zwraca True tylko dla macOS(.zip)/Windows(.exe frozen) → Linux leci w `open_installer` (dla AppImage bez sensu). Paczka AppImage 1.0.16 istnieje TYLKO lokalnie w `dist/` (nie wgrana na VPS).

**Stan startowy (już gotowe — nie trzeba dłubać):** `build.sh` produkuje `dist/ClaudeVoiceAssistant-1.0.16-linux-x64.AppImage`; `platform_utils.is_linux()` istnieje; `make-appcast-entry.py` JUŻ obsługuje `.AppImage` (`guess_platform` → `linux-x64`); `macos_app_bundle()` = wzorzec dla linuksowego helpera; sygnały `relaunch_ready`/`installer_opened`/`apply_failed` gotowe.

**Część A — KOD samo-podmiany (`update_manager.py` + `platform_utils.py`):**
1. `platform_utils`: dodać `appimage_path()` → `Path(os.environ["APPIMAGE"])` jeśli zmienna ustawiona, inaczej `None`. ⚠️ `$APPIMAGE` ustawia runtime AppImage i wskazuje **plik `.AppImage` na dysku** (NIE mount `/tmp/.mount_*`). Brak zmiennej = uruchomione „z kodu"/rozpakowane → wtedy NIE samo-podmiana.
2. `can_self_replace`: dodać gałąź `if is_linux() and p.endswith(".appimage") and appimage_path() is not None: return True`.
3. `_apply_worker`: dodać `elif is_linux(): self._linux_self_replace(path)`.
4. Napisać `_linux_self_replace(new_appimage)` wzorowane na `_macos_self_replace`: helper-skrypt bash czeka aż PID apki zniknie → `cp new → $APPIMAGE` (nadpisanie starego pliku, bezpieczne PO wyjściu procesu) → `chmod +x $APPIMAGE` → `exec "$APPIMAGE"` (relaunch) → emit `relaunch_ready`; `xattr` NIE dotyczy Linuksa (pomiń).

**Część B — FEED/DYSTRYBUCJA (runbook jak przy Mac/Win, kolejność krytyczna):**
5. (opcjonalnie) bump wersji, by było co testować (np. 1.0.16→1.0.17), `git tag` jeśli chcemy też build w CI; ale Linux można złożyć lokalnie: `CVA_SKIP_DEPS=1 bash packaging/linux/build.sh`.
6. **NAJPIERW** `scp` AppImage do `/opt/cva-web/html/cva/`, **POTEM** appcast.json (paczka przed feedem — inaczej 404).
7. Wpis do feedu: `python3 packaging/make-appcast-entry.py dist/...linux-x64.AppImage --version X --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ --appcast packaging/appcast.json --merge` → `scp appcast.json` na VPS.
8. Weryfikacja PUBLICZNYM URL: `curl …/cva/appcast.json` (jest `linux-x64`?) + `curl -I …linux-x64.AppImage` (HTTP 200, `content-length`==`size`).

**Część C — STRONA + pierwszy bootstrap:**
9. `packaging/web/index.html` (+ `-en`): aktywować przycisk Linux (dziś „Wkrótce"/nieaktywny), dograć `instrukcja-linux.html` (chmod +x + klik) → `scp` na VPS.
10. **Bootstrap jak Mac 1.0.7:** użytkownik na wersji BEZ linuksowego self-update musi PIERWSZĄ paczkę z mechanizmem zainstalować ręcznie raz; od niej w górę Linux aktualizuje się sam.

**Pułapki do zapamiętania:** `$APPIMAGE` tylko gdy uruchomione jako AppImage (nie przy `--appimage-extract`/z kodu); `chmod +x` na nowym pliku obowiązkowy; feed MUSI mieć wpis `linux-x64` albo cisza `no_update`; paczka na serwer PRZED appcast.json. Test e2e wymaga realnego uruchomienia AppImage na ekranie usera (jak przy Mac/Win).

---

*Ostatnia aktualizacja: 2026-06-16 (popołudnie) — **LINUX APPIMAGE 1.0.16: start Claude + czytelna czcionka, odzysk po awarii** (commit `d65857f`). Komputer zawiesił się w poprzedniej sesji (dziennik `be2b7aff`, urwany 13:16) — praca NIE przepadła: niezacommitowane zmiany przetrwały na dysku, przebieg odtworzony z `~/.claude/projects/<cwd>/*.jsonl`, kod nieuszkodzony. Dwie naprawy WebTerminala (xterm.js w AppImage): (1) **bufor wejścia do PTY** — `claude` przychodził ZANIM powłoka wstała (start po `frontend_ready`, ~2 s w AppImage) i `_write_pty` gubił go po cichu → Claude nie startował; fix = `_pending_input` w `__init__`, buforowanie gdy `_proc is None`, opróżnianie w `_spawn()`. (2) **czcionka pt-vs-px** — wspólny `set_font` przekazuje PUNKTY (QTermWidget=`QFont 13pt`~17px), a xterm.js liczył je jako PIKSELE (13px, ~30% mniej, nieczytelne); fix = `_push_font` przelicza `px=round(size*96/72)` → 13pt=17px + `fontSize:17` startowo w `terminal.html`. Oba potwierdzone na realnym ekranie. Plus przebudowa `packaging/linux/build.sh` (WebTerminal w paczce, CVA_SKIP_DEPS, logi etapów). Reguła: konwersja pt→px tylko na styku WebTerminala (jedyny backend w px). Nauki uniwersalne (odzysk z dziennika `.jsonl`; jednostki czcionki terminala) → kandydaci do CLAUDE-COMMON. Szczegóły w sekcji „🐧🛠️ SESJA 2026-06-16 (popołudnie)".*

*Ostatnia aktualizacja: 2026-06-16 — **SELF-UPDATE WINDOWS POTWIERDZONY E2E (1.0.16)**: użytkownik potwierdził, że Windows sam zaktualizował się do najnowszej wersji na realnej maszynie — cały przebieg pomyślny. Pierwszy potwierdzony end-to-end self-update na Windows + pierwszy realny test odpornego downloadera z 1.0.14 (TLS 1.2 + Range + retry) → przeszedł bez `SSL BAD_RECORD_MAC`. Zamyka wątek pobierania aktualizacji Windows ciągnący się od 1.0.12. Stan: macOS (od 1.0.8) i Windows (od 1.0.14) self-update ✅; Linux = brak paczki (AppImage do dorobienia). Pozostaje: potwierdzić self-update Mac do 1.0.16, test „nodecli" na świeżym Windows, Linux AppImage. Szczegóły w sekcji „🪟✅ SESJA 2026-06-16".*

*Ostatnia aktualizacja: 2026-06-15 (koniec sesji) — **1.0.16 WYDANE** (mac+win; bump d1afe84, feed da39dd6; sha256 potrójnie zgodne lokalnie==serwer==feed; instalatory 1.0.15 jako .bak). PEŁNA ANGIELSKA WERSJA: i18n aplikacji (central `config.t` + parytet 3 słowników ~640 kluczy + `detect_system_language` DOMYŚLNIE EN, PL tylko gdy system polski; helpery model_label/install_guide_url; menu/zakładki odświeżane na żywo z USUWANIEM starych QAction by nie kumulować skrótów; dialogs.py zrobione 2 subagentami + niezależna weryfikacja) + strona WWW EN (osobne pliki `-en` + dropdown English-first, wdrożone na VPS) + aplikacja otwiera instrukcję wg języka (`install_guide_url`). BUG: `from ..config import` (relative beyond top-level) crashował okno skórki w OBU językach → absolutny `from config import`. `gh` zalogowany na stałe (keyring) po rotacji → przyszłe wydania automatyczne. Nauki uniwersalne (re-auth gh przez background device-flow, i18n-at-scale subagentami + bramki weryfikacji) → CLAUDE-COMMON. Architektura i18n → pamięć projektu `i18n-architektura.md`. Wcześniej: 2026-06-12 (koniec sesji) — dopisek FAQ: aktualizacje pełnopaczkowe → pominięcie kilku wersji = bezpieczny przeskok prosto do najnowszej (wyjątki: Mac ≤1.0.7 bootstrap, Win 1.0.12–1.0.13 kruchy downloader). Wcześniej tego dnia — **1.0.15 WYDANE** (bump 96c45b6, feed dad967b; sha potrójnie zgodne lokalnie==serwer==feed; instalatory 1.0.14 jako .bak). SESJA: (1) suwak nowych zakładek (commit b8a39af): nowa zakładka dostawała fabryczne [600,150] (~80/20, gruby panel) zamiast proporcji usera ~[1500,187]; fix = `DEFAULT_SPLITTER_SIZES=[1500,190]` w config.py (jedyne źródło prawdy, cienki panel dla świeżych instalacji) + `_inherit_splitter_sizes()` (dziedziczenie z AKTYWNEJ zakładki) wpięty w 3 drogi tworzenia (Dodaj agenta / manager→uruchom / „+"); dialogs.get_data NIE wpycha defaultu nowemu agentowi (inaczej dziedziczenie martwe); agents.json: Fable 5 + Strona F-P naprawione na [1503,187] (backup .bak-2026-06-12). (2) czarna strona po zamknięciu zakładki (commit c85e451): „+" to pusta atrapa-QWidget; po removeTab aktywnej Qt samo wybierało sąsiada (przy ostatniej przed „+" = atrapę → czarny widok; przy środkowej = przypadkowa lazy-activation/start claude); fix = historia MRU `_tab_mru` (aktualizacja w `_on_tab_changed`) + `_close_agent_tab` robi `setCurrentWidget(cel z MRU)` PRZED removeTab + `_most_recent_tab(exclude)` (pomija zamykaną i „+", fallback ostatnia prawdziwa). LEKCJA QT (decyzją usera w tym pliku, nie COMMON): przy usuwaniu aktywnej zakładki NAJPIERW setCurrentWidget, POTEM removeTab. NA NASTĘPNĄ SESJĘ: test self-update Mac/Win 1.0.14→1.0.15 (Windows = 1. realny test downloadera TLS 1.2+Range+retry; checklista z 2026-06-11 niepotwierdzona), test „nodecli" na świeżym Windows, instrukcja-linux przy AppImage.*

*Wcześniej: 2026-06-11 (koniec sesji) — **1.0.14 WYDANE** (bump 78161f8, feed 0ce41f3; sha potrójnie zgodne; weryfikacja publicznym URL OK). NA JUTRO: user sprawdza self-update Mac (oczekiwane OK) i PIERWSZY self-update Windows (stary downloader bez TLS 1.2 → możliwy SSL BAD_RECORD_MAC; obejście: przeglądarka, publiczny /cva/...Setup-1.0.14.exe; od 1.0.14 pobieranie odporne) + test „nodecli" na świeżym Windows. Wcześniej tego dnia — SESJA: (1) NAPRAWA FLAGI „?" (commit a3fd485): przyczyna = dziennik .jsonl dostaje tylko UKOŃCZONE wpisy (zmierzone 20,4 s ciszy pliku W TRAKCIE pisania odpowiedzi) → warunek „plik stoi 1,6 s = czeka" zapalał flagę przy każdej pracy agenta i nie gasła; fix = DRUGI warunek: cisza strumienia terminala ≥ 3 s (pracujący TUI animuje spinner+licznik ~1×/s → zmierzone max 0,96 s przerwy przy generowaniu, przy czekaniu cisza 8+ s; `_last_terminal_data_ts` w AgentTab._on_terminal_output + `QUESTION_TERMINAL_QUIET_SECS=3.0`; reader wołany ZAWSZE, nie za leniwym `and`); potwierdzone przez usera; KOREKTA uniwersalna → CLAUDE-COMMON „INTEGRACJA Z CLI/TUI" pkt 4 (stary wpis błędny). (2) Hardening updatera (f57fb58): TLS 1.2 + Range/wznawianie segmentami 8 MB + retry 3× + sha po całości + .part→rename po weryfikacji; przetestowane na żywym feedzie (102 MB + wznowienie od 60 MB) — wejdzie w 1.0.14. (3) Kreator ClaudeSetupDialog przy braku claude (start raz/sesję + menu Pomoc; claude_found → podmiana claude_command bez restartu); INSTALL_GUIDE_BASE_URL = publiczne /cva/. (4) Strony WWW wdrożone: instrukcja-{windows,macos,linux,agenci}.html na /cva (publiczne; Groq → console.groq.com/keys; agenci = każdy przycisk managera + 4 zakładki konfiguracji + FAQ; link w menu Pomoc „Instrukcja: Zarządzaj agentami…"); index.html: Linux „Wkrótce" (był 404!), wersja z appcast, linki 📖. (5) installer.iss zadanie „nodecli" (Node LTS z dist/index.json → MSI → npm claude-code; wykrywanie node/claude w Program Files I PATH przez `where`; nigdy przy /VERYSILENT; pułapki: .iss MUSI być UTF-8 Z BOM, `{tmp}` w komentarzu Pascala zamyka komentarz; CI zielony, e2e przy 1.0.14). Wydania NIE było — TODO 1.0.14 w sekcji sesji. Wcześniej (2026-06-10 noc) — DOPISEK do sesji 1.0.13: POTWIERDZONO terminal Windows DZIAŁA na realnej maszynie usera (10.0.19045; `cmd.exe` odpowiada, Enter działa) — bug pustego terminala zamknięty na żywo. KOREKTA: Windows 1.0.12 JEDNAK wykrył update 1.0.13 (self-update feed+detekcja działa na Win), padło tylko POBIERANIE: `SSL DECRYPTION_FAILED_OR_BAD_RECORD_MAC` konsekwentnie pod koniec ~100 MB (TLS 1.3 KeyUpdate w starym OpenSSL albo antywirus; serwer OK — curl+sha256 z zewnątrz przeszły); obejście = pobranie przez PRZEGLĄDARKĘ z publicznego `/cva/...Setup.exe` (zadziałało). Onboarding Claude Code na świeżym Windows: app NIE zawiera CLI → user musi Node.js LTS + `npm i -g @anthropic-ai/claude-code` + restart app + login OAuth; pułapka: Node installer „Tools for Native Modules" sypie błędami VS Build Tools (zignorować, zamknąć); login gdy przeglądarka się nie otwiera = „c to copy" URL (nie przepisywać 300+ znaków ręcznie — PKCE); literówka `cloude`≠`claude`. TODO 1.0.14: uodpornić `update_manager._download_worker` (TLS 1.2 + Range + retry 3×) — przy okazji 1. realny test self-update Windows. NOWE TODO (priorytet usera): napisać SZCZEGÓŁOWĄ instrukcję instalacji krok-po-kroku dla nie-programisty na Windows/macOS/Linux z doinstalowaniem programów dodatkowych (Node+claude+login) — strona „Pierwsze kroki"/docs/INSTALL.md; rozważyć kreator wykrywający brak Node/claude. Nauki uniwersalne (SSL BAD_RECORD_MAC przy dużym pobieraniu, onboarding pilota-nad-CLI) → CLAUDE-COMMON. Wcześniej (wieczór) — SESJA: WYDANIE 1.0.13 (mac+win). (1) TERMINAL WINDOWS NAPRAWIONY — diagnoza na runnerze `windows-latest` (workflow `diagnose-windows.yml`: build → uruchom z kodu I spakowaną → zrzut ekranu + logi → `gh run download`); „puste pole bez kursora" miało PIĘĆ przyczyn warstwa-pod-warstwą: (a) `pygame.mixer.init()` crash bez audio → try/except `audio_available`; (b) `print()` z „ą" na Windows crashował (stdout cp1252 UnicodeEncodeError, w handlerze błędu TTS) → `sys.stdout/err.reconfigure(errors="replace")` w main.py; (c) renderer Chromium ginął w spakowanej appce (`renderProcessTerminated status=2 0x80000003`, sandbox vs PyInstaller) → `QTWEBENGINE_DISABLE_SANDBOX=1`; (d) PyQtWebEngine-Qt5 5.15.2=Chromium 83, xterm.js 5.x wymaga `replaceChildren` (Chromium 86+) → polyfill w terminal.html przed xterm.js (na macOS Qt nowszy, działało); (e) pywinpty bez `winpty-agent.exe`/`OpenConsole.exe` → `collect_all('winpty')` w .spec. Plus 2 poboczne: `_update_status` guard na brak `status_bar`; jawny `self._ui_ready` w `_on_tab_changed` (terminal znikał przy starcie, bo wcześniejszy crash status_bar PRZYPADKIEM chronił przed za wczesną aktywacją). web_terminal: log `~/.claude-voice-assistant/webterminal.log` + obsługa loadFinished/renderProcessTerminated + watchdog 10 s → komunikat zamiast pustego pola; log Chromium tylko pod CVA_WEBENGINE_LOG=1 (--enable-logging otwiera czarne okna konsoli QtWebEngineProcess.exe). (2) FLAGA „?" — pomarańczowa ikona SVG na nieaktywnej zakładce gdy agent czeka; wykrywanie z DZIENNIKA (`transcript_reader.waiting_for_user()`: plik sesji STOI ~1,6 s = czeka, rośnie = pracuje), NIE ze strumienia terminala (zniekształcone kodowanie + AskUserQuestion zapisuje tool_use do dziennika DOPIERO po odpowiedzi → ostatni wpis zostaje `user`). GUI: `_arm_question`/`_refresh_question_flag`/`_refresh_all_question_flags`, sprawdzane co tick w `_poll_transcripts`. Bonus: przypięcie sesji w transcript_reader (`_preexisting` → bierze tylko plik powstały PO starcie zakładki) — ignoruje równoległą sesję Claude Code w tym samym katalogu (psuło flagę I auto-czytanie). Commity 6a511b3/f23b22a/e5e9630. TODO usera: Windows install 1.0.13 ręcznie raz (1.0.12 ma zepsuty terminal; self-update Windows test przy 1.0.14); macOS sam się zaktualizuje. Nauki uniwersalne (CI-jako-GUI-środowisko, QtWebEngine-na-Windows pułapki, wykrywanie „agent czeka" z transcript) → CLAUDE-COMMON. Wcześniej tego dnia — SESJA: dodano model Fable 5 do listy wyboru (commit `a6c59aa`). Nowa sekcja „🤖 PRZEPIS: JAK DODAĆ NOWY MODEL CLAUDE CODE DO APLIKACJI": aplikacja jest pilotem nad CLI (claude --model <klucz>), dodanie modelu = JEDEN plik src/config.py = 3 słowniki (CLAUDE_MODELS / CLAUDE_MODELS_SHORT / CLAUDE_MODEL_CONTEXT_LIMITS) jako jedyne źródło prawdy (dropdown/panel agentów/licznik tokenów zasilają się same); KROK 1 = weryfikuj alias na żywo `claude --model <alias> -p "OK"` (exit 0) zanim dopiszesz; dopisz TEN SAM klucz do wszystkich 3 słowników (inaczej licznik nie zna okna); NEW_AGENT_DEFAULT_MODEL zmieniaj świadomie. Fable 5: alias `fable` (zweryfikowany), okno 1M = jak Opus 4.8, max 128K, ~2× droższy ($10/$50 vs $5/$25) → szybciej zużywa limit; rozliczenie: do 22.06.2026 wliczony w subskrypcję bez dopłat (draws from plan usage), potem warunki mogą się zmienić. Domyślny = Opus (tańszy). Etykiety Opus 4.7→4.8. Dodano też wskazówkę „kiedy Fable vs Opus": programowanie na Fable działa identycznie (wybór modelu w konfiguracji agenta, Stop→Uruchom); Fable = duże refaktory / trudne bugi przez wiele warstw / długie zadania „odpal i zostaw" / głęboki research / trudne code review; Opus (domyślny) = bieżączka (drobne poprawki, pojedyncze pliki, szybkie pytania, taniej); praktyka = dwóch agentów w zakładkach (Opus bieżączka + Fable ciężkie). Wcześniej 2026-06-09 (wieczór) — SESJA: WERSJA WINDOWS 1.0.12 zbudowana/wdrożona/zainstalowana na realnym Windows, ale ⛔ TERMINAL NIE DZIAŁA (JUTRO ZACZYNAMY OD TEGO). Krok 1 jutro: odczytać komunikat w okienku terminala (brak pywinpty vs spawn padł). Hipoteza nr 1: PyInstaller nie dołącza natywnych binariów pywinpty (winpty-agent.exe/conpty.dll/OpenConsole.exe) → w ClaudeVoiceAssistant.spec dodać collect_all('winpty'); rebuild 1.0.13 + przy okazji 1. test self-update Windows. Zrobione W1–W5: W1 ConPTY pywinpty (_PTY_KIND wybiera winpty/ptyprocess; winpty read/write=str, terminate() bez force), W2 spec onedir+build-windows.ps1+make_ico.py, W3 build-windows.yml (windows-latest, choco innosetup), W4 installer.iss Inno per-user {localappdata} bez UAC, W5 _windows_self_replace Setup.exe /VERYSILENT (nietestowane e2e). Pułapki sesji: (a) .ps1 MUSI być ASCII — PS5.1 czyta bez BOM jako ANSI → polskie znaki/emoji rozbiły parser (ParserError/MissingTypename); (b) .spec w .gitignore → dodany wyjątek; (c) ZAPOMNIANY scp index.html (strona pokazywała stary „Wkrótce" mimo wgranego .exe). Feed: jedna globalna version → mac+win ujednolicone na 1.0.12. Runbook wydania Windows w sekcji wyżej. Nauki uniwersalne w CLAUDE-COMMON (pakowanie Windows + auto-update Windows). Wcześniej tego dnia — SESJA: ZAKŁADKI macOS DOKOŃCZONE w 1.0.11 (potwierdzone na realnym Macu — po lewej). 1.0.9 (CSS) i 1.0.10 (QProxyStyle na samym SH_TabBar_Alignment) NIE działały bo QMacStyle IGNORUJE ten hint; centrowanie liczy styl QTabWidget w subElementRect(SE_TabWidgetTabBar). Fix 1.0.11 (commit d1404b6): _LeftAlignedTabStyle = QProxyStyle oparty o silnik Fusion (QStyleFactory.create) + override subElementRect dosuwający pasek w lewo + styleHint→AlignLeft, podpięty do tab_widget.setStyle(...) ORAZ tabBar().setStyle(...) (referencja self._tab_style; setStyle nie propaguje na dzieci → reszta okna macowa). Sekcja „Zakładki na macOS" przepisana na ✅ ROZWIĄZANE. Self-update potwierdzony też 1.0.10→1.0.11 (mechanizm stabilny przez 3 wydania pod rząd). KOREKTA pamięci uniwersalnej CLAUDE-COMMON „PUŁAPKI QT/PYQT5" pkt 5 (był błędny). Wcześniej 2026-06-08 — SESJA: pierwszy udany SELF-UPDATE na żywym Macu (1.0.8→1.0.9, sam pobrał/podmienił/zrestartował, bez instalatora — cały mechanizm auto-aktualizacji potwierdzony end-to-end) + runbook wydania 1.0.9 (bump APP_VERSION → tag v1.0.9 → Actions build .dmg/.zip → gh release download → wgraj .zip PRZED appcast.json (kolejność!) → .dmg pod stałą nazwą downloads/ClaudeVoiceAssistant-macos.dmg + .bak → make-appcast-entry --merge → weryfikacja publicznym URL version/HTTP200/content-length==size). ZAKŁADKI macOS — wtedy niedokończone; DOKOŃCZONE 2026-06-09 w 1.0.11 (Fusion + subElementRect, patrz wpis na górze stopki). Wcześniej 2026-06-03 — AUTO-AKTUALIZACJA (commit `d9f4ed2`) + suwak xterm.js (`28e0137`): nowa sekcja 🔄 AUTO-AKTUALIZACJA — Etap 1 (sprawdzanie przy starcie I zamknięciu: closeEvent async-check + bezpiecznik 4 s + flagi `_close_check_in_progress`/`_force_close`/`_update_checked_on_close` + `_finish_close`), Etap 2 (macOS samo-podmiana: `apply_update_async`/`can_self_replace`/`_macos_self_replace` przez `ditto -x -k` + pomocnik bash czeka na PID→swap→relaunch; `platform_utils.is_frozen()`/`macos_app_bundle()`; dialog `relaunch_ready`/`installer_opened`/`apply_failed`), build `.zip` (ditto -c -k --keepParent) obok `.dmg`, feed PUBLICZNY `pobierz…/cva/appcast.json` (router traefik cva-pub bez basicauth, priority=100; /opt/cva-web/html/cva/). Feed=1.0.7; auto-update aktywny od 1.0.8. Suwak xterm.js (Mac/WebTerminal) 1:1 jak QTermWidget (`::-webkit-scrollbar` w terminal.html: gradient #888→#aaa→#888, 12px, rogi 5px). Wcześniej 2026-06-02 — sesja licznik/ikony/UI, wydania 1.0.5→1.0.7: nowa sekcja 🛠️ SESJA 2026-06-02 — (a) fix licznika tokenów: `QTermWidgetBackend._on_received` gubił całe wyjście terminala bo `receivedData` niesie str a kod robił `bytes(data)` (TypeError połykany) — od M2.3; + `_connect_agent_tab_signals` (jedno źródło sygnałów, „+" gubiło terminal_output); + `self.terminal_backend`=None przy starcie primary taba index 0 → fix w `_on_terminal_ready` (objaw: 🔊/⧉ nie działają do 1. zmiany zakładki). (b) kolorowe ikony SVG `src/assets/icons/*.svg` + `gui/icon_set.py` (setIcon zamiast emoji; emoji na Linuksie monochromatyczne). (c) pasek postępu zużycia kontekstu + stałe szerokości liczników (anty-skakanie). (d) „Zarządzaj agentami": tło wiersza = auto-start (zielone/szare) zamiast 🟢/⚪. (e) okna plików: neutralna ciemna paleta `DIALOG_COLORS` (natywne GNOME niedostępne dla Qt). (f) Groq tylko STT (TTS=edge-tts bez klucza); klik 🎤 bez klucza → komunikat + dialog (fix AttributeError `_show_api_key_dialog`→`_show_groq_api_dialog`). Nauki uniwersalne (emoji-monochromat, natywne QFileDialog, anty-skakanie, diagnoza sygnałów Qt) w CLAUDE-COMMON.md. Wcześniej 2026-06-01 (wieczór) — DYSTRYBUCJA macOS DZIAŁA NA REALNYM MACU: nowa sekcja 🍎 DYSTRYBUCJA / WYDANIA macOS — GitHub Actions buduje `.dmg` (macos-14 arm64, tag v* → Release), launchery dwuklik (Uruchom-Mac.command / Zbuduj-DMG-Mac.command), strona pobierania z hasłem `https://pobierz.srv1251441.hstgr.cloud` (kontener cva-web w /opt/cva-web za traefik+basicauth), automat gh release download + scp podmienia plik. Wydania 1.0.0→1.0.4: 1.0.1 login shell (claude↔node), 1.0.2 menu w oknie (natywny pasek znikał), 1.0.3 font Ubuntu dołączony (cienki na Macu), 1.0.4 pauza TTS (brakowało sygnału request_pause). requirements: usunięto asyncio, pyenchant opcjonalny. TODO: klucz Groq, podpis Apple, Intel+Linux w automacie, ochrona/licencja/własna nazwa. Wcześniej 2026-06-01 — PORT macOS UKOŃCZONY (strona kodu): M2.2 (terminal_backend.py — wspólny interfejs + fabryka), M2.3 (wpięcie do AgentTab/MainWindow; Linux=QTermWidget, Mac/Win/CVA_WEBTERMINAL=1=WebTerminal; gotcha AA_ShareOpenGLContexts w main.py), M2.4 (pełny motyw xterm ze skórki + czcionka + scrollback 10000), M3 (update_manager.py + UpdateAvailableDialog + menu Pomoc + ciche sprawdzanie przy starcie; sha256 obowiązkowe, Ed25519 wyłączone; instalacja=otwórz instalator; HTTP przez requests NIE httpx), M4 (packaging/macos: spec PyInstallera + Info.plist z mikrofonem + entitlements + build-macos.sh + make-appcast-entry.py; config.BASE_DIR świadomy sys._MEIPASS frozen-only). Sekcja PORT przepisana na ✅ UKOŃCZONE + architektura terminala + CO ZOSTAŁO (build na Macu, feed VPS, Windows ConPTY). Poprawka ZALEŻNOŚCI: httpx→requests. Commity: ade4a25, 716946e, f9c030d, 0338b07, 61d5774. Wcześniej 2026-05-30 — dodano sekcję 🚧 PORT macOS — STATUS I PLAN [wznowienie 2026-05-31]: cel (Mac Apple Silicon, architektura pod Windows, auto-aktualizacja z VPS, podpis odłożony z gotowym gniazdem); zablokowane decyzje; ZROBIONE M1 (platform_utils, packaging, APP_VERSION) + M2.1 (WebTerminal xterm.js+QtWebEngine+PTY, działa); NASTĘPNY KROK = M2.2 (wspólny interfejs + fabryka backendów), dalej M2.3 wpięcie do AgentTab (Linux=QTermWidget domyślnie, Mac/Win=WebTerminal; gotcha AA_ShareOpenGLContexts), M2.4, M3 updater, M4 pakowanie. Wcześniej 2026-05-30 — nowa sekcja ARCHITEKTURA AUTO-CZYTANIA (Droga A): auto-czytanie czyta czystą prozę z dziennika `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.* `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.*

## WYDANIA 1.0.20 – 1.0.24 (szczegóły, przeniesione z żywego pliku 2026-07-20)

- **1.0.24 (WYDANE 2026-06-26, 3 platformy, appcast podbity, pipeline e2e OK):** dwie naprawy realnych bugów zgłoszonych przez usera, **POTWIERDZONE przez usera na pobranej apce** (1.0.23 „naprawione" działało tylko z logu, nie u usera — stąd 1.0.24 najpierw szła do poczekalni). Linux = opublikowany DOKŁADNIE ten testowany AppImage (`sha 3eb75d1d…`, nie budowany od nowa); Mac/Win zbudowane z tagu `v1.0.24` (CI). Weryfikacja: sha serwer==feed ×3, HTTP 200 ×3, `.exe` 644. **(A) Czytnik sesji samonaprawiający** (`transcript_reader.py`): gdy zakładka/apka wystartuje już PO powstaniu pliku sesji (self-update/restart/reopen), czytnik przygarnia żywą sesję (`mtime>_reader_start`) i przeskakuje na koniec → naprawia naraz auto-czytanie, ręczny 🔊 i flagę „?" (test 9/9). **(B) Zaznaczanie w WebTerminalu BEZ Shift** (`terminal.html`): B1 wycięcie sekwencji raportowania myszy + B2 zamrożenie rysowania na czas przeciągania (strip 10/10, JS OK). ⚠️ kompromis: Claude traci mysz w swoim oknie (do ew. przełącznika — patrz TODO).
- **1.0.23 (WYDANE 2026-06-25, 3 platformy, pipeline e2e OK):** naprawa flagi „?" (samonaprawiająca się — `_refresh_question_flag` porównuje zamiar z REALNYM stanem paska `bar.tabButton`, NIE z notatką `_question_flag_shown`; commit `e25bd2a`) + **kopiowanie w WebTerminalu** (xterm.js gubił zaznaczenie przy odświeżeniach Claude; fix = próbkowanie w trakcie przeciągania → ostatnie niepuste do `_selection`; commit `e4627e5`). Build: tag `v1.0.23`→CI(mac/win)+lokalny AppImage; rsync→`/cva/` (sha256 serwer==appcast ×3); appcast podbity; stałe nazwy w `/downloads/`. Flaga potwierdzona przez usera; kopiowanie — capture potwierdzony logiem, podświetlenie wciąż miga (ograniczenie xterm.js, pełne „zamrożenie" = osobna przebudowa).
- **1.0.22 (zbudowana 2026-06-24; Windows .exe w `/cva/`, appcast WCIĄŻ 1.0.21 — świadomie):** wskaźnik RAM (kolorowa „kość pamięci" w pasku statusu, `src/gui/resource_monitor.py`, `psutil` opcjonalne); aktualizacje sprawdzane TYLKO przy starcie (usunięto check przy zamykaniu); **naprawa self-update Windows** (pomocnik `.cmd` czeka na zamknięcie + brak modala + `[InstallDelete]` — patrz pamięć `windows-selfupdate-fix-in-source`); pewniejsze kopiowanie/odczyt zaznaczenia + podpowiedź o Shift (kopiuj w terminalu z TUI wymaga Shift — pamięć `terminal-shift-selection`). User na Windows: 1.0.21 zainstalowana ręcznie, 1.0.22 do ręcznej instalacji z `…/cva/VibeCodingAssistant-Setup-1.0.22.exe` (sha256 `d9852e9a…`). Mac/Linux 1.0.22 NIEzbudowane. **Prawdziwy test self-update = 1.0.22→1.0.23.**
- **1.0.21 (WYDANE 2026-06-23, 3 platformy, pipeline e2e OK):** Funkcja #2 (kolor zakładki per agent + ramka okna aktywnego agenta), Funkcja #3 (głos czytającego per agent: lista PL/EN + wyszukiwarka), naprawy: białe linie terminala (`QTermWidget border:none`), flaga „?" jako osobny widżet LeftSide (obok ikony, nie zasłania), szare pole na pionowym ekranie, pamięć agenta SEO (cwd nie $HOME — ekran zaufania Claude), macOS X zamykania (podkładka, do weryfikacji na buildzie), `agents.json.autobak`. Appcast/paczki publiczne (`/cva/`, HTTP 200 ×3).
- **1.0.20 (wydane):** fix białego błysku terminala + kreator ustawień jako lista kontrolna 3 punktów; scalenie instrukcji OS w jedną stronę (`config.install_guide_url`).

## ROZWIĄZANE TODO (przeniesione z żywego pliku 2026-07-20)

- [x] ~~**Redesign — Porcja C (dialogi) DO TESTU NA ŻYWO**~~ POTWIERDZONE przez usera 2026-07-14 (izolowane drugie okno `test-druga-instancja-izolowana`): 4 karty konfiguracji, listy Skills/MCP z pełnymi opisami, ogonki w napisach, podgląd skórki + „Anuluj" (przywraca kolory), kolory zakładek, wskaźnik RAM — wszystko OK.
- [x] ~~**Flaga „agent czeka" — runda 5**~~ **POTWIERDZONA JAKO DZIAŁAJĄCA przez usera (2026-07-03).** Fix `ae17a79` (ignoruj migającą kropkę bezczynności ● jako „ruch terminala" — idle Claude Code miga co ~0,5 s, więc terminal nigdy nie był „cichy" → flaga się nie uzbrajała) działa poprawnie. Diagnostyka flagi (`transcript_reader.debug_state()`, `_flag_dbg`, baner) ZOSTAJE jeszcze w kodzie — pasywna, gated `CVA_FLAG_DEBUG` (OFF domyślnie), a ta sama zmienna gatuje diagnostykę „czytaj ostatnią", której potrzebujemy na następną rundę. **Sprzątanie (następna runda, razem z read-last):** po potwierdzeniu fixu „czytaj ostatnią" usunąć OBIE diagnostyki (`_flag_dbg`/`debug_state`/`_read_last_dbg`) + `CVA_FLAG_DEBUG=1` z `run-safe.sh`.
- [x] ~~**1.0.24 — POTWIERDZIĆ u usera**~~ POTWIERDZONE + WYDANE 3-platformowo (2026-06-26, appcast 1.0.24, commit `8c17f7c`). ~~**Otwarta obserwacja:** PRZEWIJANIE w Claude (B1 zabiera mysz) → przełącznik trybu myszy~~ ZROBIONE: przycisk `mouse_mode_btn` w panelu dolnym (`agent_tab.py`, `_toggle_mouse_mode`) przełącza „Mysz: przewijanie" (kółko przewija Claude, zaznaczanie z Shift) ↔ „Mysz: zaznaczanie" (drag zaznacza bez Shift); ikony `mouse-select.svg`, i18n PL/EN.
- [x] ~~**Flaga „?" — fałszywy negatyw**~~ ROZWIĄZANE (1.0.23, 2026-06-25): NIE zapalnik (arming działał — log potwierdził), tylko WYŚWIETLANIE — cache `_question_flag_shown` rozjeżdżał się z paskiem. Fix samonaprawiający (patrz PUŁAPKI, commit `e25bd2a`). Diagnostyka usunięta.
- [x] ~~Opublikować 1.0.22 Mac/Linux~~ — pominięte; wydano od razu **1.0.23** (3 platformy, appcast podbity 2026-06-25) z naprawami flagi + kopiowania.
- [x] ~~**Funkcja #2: kolor zakładki + obramówka na cały program**~~ ZROBIONE (wydane w 1.0.21): per-agent kolor zakładki + ramka okna aktywnego agenta.
- [x] ~~**Funkcja #3: wybór głosu czytającego**~~ ZROBIONE (wydane w 1.0.21): głos czytającego per agent (dropdown PL/EN z `edge_tts.list_voices()` + wyszukiwarka).
- [x] ~~Zweryfikować wtyczki Qt na Mac/Win~~ — paczki Mac/Win **startują** (obserwacja usera 2026-06-22); brak crashu z wtyczek na tych OS (PyInstaller dociąga `cocoa`/`qwindows` sam). Specki Mac/Win NIE wymagają fixu z Linuksa.
- [x] ~~Potwierdzić self-update **Mac**~~ POTWIERDZONE: Mac pobrał i zaktualizował się do **1.0.26** (self-update Mac działa).

### 1.0.25 — szczegóły (przeniesione 2026-07-20)

  - **REBRANDING „Claude Voice Assistant" → „Vibe Coding Assistant"** (publiczna nazwa potwierdzona przez usera): nazwa widoczna + nazwy plików paczek `ClaudeVoiceAssistant-*`→`VibeCodingAssistant-*` + instalator Inno (AppId STAŁY → aktualizacja w miejscu) + strony WWW + WM_CLASS `vibe-coding-assistant`. **ZOSTAJE infrastruktura** (zmiana zerwałaby self-update): `/cva/` URL + appcast, repo GitHub `claude-voice-assistant`, nazwy plików `.spec`, wewn. binarka Linuksa. **Migracja ustawień** w `config.py`: 1. start kopiuje `~/.claude-voice-assistant`→`~/.vibe-coding-assistant` (user nic nie traci). ⚠️ rebrand MUSI objąć też `.ps1/.yml/.command` (pominięte → build Windows padł: `build-windows.ps1` sprawdzał starą ścieżkę).
  - **Ikona:** domyślna ikona agenta = wbudowany OBRAZEK uśmiechniętego robota (`src/assets/agent-robot.png`) zamiast emoji 🤖 (na Windows renderowało się jak „diabełek"). Ikona aplikacji = marka VCA „Prompt Wave" (`icon.png`/`icon.ico`/`icon.icns`).
  - **Zakładki:** ikona agenta 30px (`setIconSize`), czcionka 12pt (`tabBar().setFont`), flaga „?" jako ŻÓŁTA ikona z lewej (badge w rogu ikony-obrazka / samodzielna ikonka dla emoji), dzióbki przewijania w kolorze zakładek + białe SVG.
  - **Inne:** przełącznik trybu myszy (kółko przewija Claude/zaznaczanie bez Shift), auto-update okno przy starcie + co 30 min, „odczytaj ostatnią" czyta ostatnią wypowiedź, okno Pomocy ciemne tło, suwaki (terminal: pojawia się gdy jest co przewijać; pole poleceń: >5 linii), WebTerminal off-the-record profil (koniec „database is locked").

## PRZENIESIONE Z ŻYWEGO PLIKU 2026-07-20 (konsolidacja)

### XSS panelu admina (domkniete 2026-07-14)

## ✅ XSS panel admina — DOMKNIĘTE 2026-07-14 (commit `6b70b5a`)

Panel `panel/index.html` (serwowany OSOBNO, otwierany w PRZEGLĄDARCE — nie desktop): domknięte 3 luki
`esc()` (surowa platforma z serwera w `osName(v.platform)`, `l.max_devices`, `data-id="${l.id}"`) +
**CSP w `<meta>`** jako druga warstwa: `script-src` tylko po odcisku `sha256-…` inline skryptu (helper
`panel/_csp_hash.py` przelicza hash po KAŻDEJ zmianie skryptu — inaczej panel wczyta się pusty),
`style-src 'unsafe-inline'`, `connect-src http:/https:` (konfigurowalne API), `default-src 'none'`.
Nagłówki `nosniff`+`Referrer-Policy` na API (`server/app/main.py`). Test Playwright 9/9 + kontrola
negatywna (bez ochrony payload się wykonuje → test realnie wykrywa XSS). Warstwa terminala
(xterm.js `term.write()`, NIE `innerHTML`) była i jest BEZPIECZNA. Wzorzec → `CLAUDE-COMMON.md`.
- ⚠️ **Zostało (niski prio, statyczny):** `src/gui/web_terminal.py:408-416` `_show_failure_page` skleja HTML
  f-stringiem z NIEescapowanym `reason` — dziś deweloperski, ale owiń escaperem, gdyby wpłynął tam tekst
  zewnętrzny (stderr/ścieżka).


### Potwierdzenia usera 2026-07-13

## ✅ POTWIERDZONE PRZEZ USERA 2026-07-13 (żywa beta, WebTerminal)
- **🔊 „czytaj ostatnią" z dziennika** (`9485c0d`+`9ae59c3`) — bez śmieci („Read 2 files"/ramek), DO KOŃCA,
  bez limitu 500 słów. → `czytaj-ostatnia-czyta-inna.md`.
- **Polskie znaki AltGr WPROST w terminalu** (WebTerminal `c38775f`) — `żółć ąę` w czarnym terminalu. ⚠️ liczył się
  tylko fix WebTerminala (`9aad8dd` był tylko QTermWidget). → `qtermwidget-polskie-znaki-altgr.md`.
- **Pole „Wpisz polecenie"** (`782120a`) — ogonki liter (p/y/ż) w całości.
- **Dyktowanie (STT) przez bramkę AI Managera** (`eab76b3`) — PL i EN wchodzą w pole; klucz `aim-…`
  w Ustawieniach → „Klucz AI Managera (dyktowanie)". → `stt-bramka-ai-manager.md`.

**Zweryfikowane Z KODU (nie wymaga bety):**
- **JEDEN silnik = WebTerminal domyślny wszędzie** (`1dc983a`) — fabryka `selected_backend_kind()` zwraca
  `webterminal`, chyba że `CVA_QTERMWIDGET=1`. Nagłówek `terminal_backend.py` zgodny z kodem (naprawiony
  w `dd9b5e6`). → `testy-uruchamianie-beta.md`.
- **Diagnostyka flagi usunięta** (`9ae59c3`) — grep pusto w `src/` i `run-safe.sh`, log przestał rosnąć.
  Auto-kasowanie starych paczek (zostawia 1) + martwych `*-debug.log` przy starcie dodane w `dd9b5e6`
  (⏳ do testu na żywej becie po restarcie). → `todo-sprzatanie-starych-plikow.md`.


### Wydania 1.0.25 i 1.0.26 - szczegoly

- **1.0.26 (WYDANE 2026-06-29, 3 platformy, appcast 1.0.26, pipeline e2e OK):** naprawa flagi „agent czeka", która nie pokazywała się na zakładkach w tle. **Przyczyna (zdiagnozowana czujnikiem `CVA_FLAG_DEBUG=1`):** wykrywanie „agent czeka" zależało od ZGADYWANIA pliku sesji w `~/.claude/projects` (reguła „plik zapisany po starcie zakładki") — zawodziło dla sesji wznowionych/cichych (agent czeka = nic nie pisze → `has_session=N` → flaga się nie uzbraja) i myliło sesje między oknami. **Fix u źródła:** apka uruchamia `claude --session-id <uuid>` i PRZYPINA czytnik do dokładnego `<uuid>.jsonl` (`transcript_reader.pin_session` + tryb przypięty w `_ensure_session`; `main_window._build_claude_command`/`_pin_tab_session`). Koniec zgadywania → flaga działa od razu, deterministycznie, bez kolizji okien; stary tryb zgadywania zostaje jako zapas (ręczny `--resume` po crashu). **Bonus:** pasywny czujnik flagi (`CVA_FLAG_DEBUG=1`, domyślnie OFF) → log `~/.vibe-coding-assistant/flag-debug.log`. Weryfikacja: `claude --session-id` tworzy `<uuid>.jsonl` (test bezpośredni), przypięty czytnik wykrywa sesję+ciszę, rysowanie ikony przy SHOW=1, potwierdzone przez usera. sha256 serwer==feed ×3, HTTP 200 ×3. Commity `d567975`(fix)+`87cbb44`(bump)+`f2a670d`(appcast), tag `v1.0.26`.
- **1.0.25 (WYDANE 2026-06-26, 3 platformy, appcast 1.0.25, self-update zweryfikowany):** wielki **rebranding** + cała seria poprawek UI (potwierdzane na żywo w becie). Weryfikacja: sha256 serwer==lokalne ×3, HTTP 200 ×3, `.exe` 644, appcast `version=1.0.25`. Tag `v1.0.25`→`243efff`.
  - ⚠️ **Trwałe z rebrandingu:** infrastruktura ZOSTAJE stara (`/cva/` URL, appcast, repo GitHub
    `claude-voice-assistant`, wewn. binarka) — zmiana zerwałaby self-update. Migracja ustawień
    `~/.claude-voice-assistant`→`~/.vibe-coding-assistant` w `config.py` (stary katalog skasowany
    2026-07-20). Rebrand MUSI obejmować też `.ps1/.yml/.command` (pominięcie = padł build Windows).



---

# ARCHIWUM — konsolidacja 2026-07-21 (plik żywy 475 → 372 linii)

_Przeniesione z `CLAUDE-VOICE-ASSISTANT.md` w całości, bez zmian w treści._


## [2026-07-21] XSS panelu admina — domkniete (bylo na szczycie pliku)

## ✅ XSS panel admina — DOMKNIĘTE 2026-07-14 (`6b70b5a`)
Panel `panel/index.html`: 3 luki `esc()` + CSP w `<meta>` po odcisku `sha256` inline skryptu
(helper `panel/_csp_hash.py` — **przelicz po KAŻDEJ zmianie skryptu**, inaczej panel wczyta się pusty).
Test Playwright 9/9 + kontrola negatywna. Szczegóły → archiwum. Wzorzec → `CLAUDE-COMMON.md`.
- ⚠️ **Zostało (niski prio):** `src/gui/web_terminal.py` `_show_failure_page` — surowy f-string z `reason`.


## [2026-07-21] Potwierdzone przez usera 2026-07-20 + historia (pliki pamieci, BUG #6)

## ✅ POTWIERDZONE PRZEZ USERA 2026-07-20 (żywa beta)
- **Auto-czytanie (zwykłe)** — lektor sam czyta nowe wypowiedzi z dziennika, do końca, bez śmieci.
  Potwierdzone na żywo. ⚠️ To NIE domyka przypadku po auto-compact (wyżej) — inny tor kodu.
- **Pliki pamięci w OSTATNICH zakładkach** (`0361565`) — wszystkie auto-startujące zakładki wczytują pamięć.
- **🔊 „czytaj ostatnią" BUG #6 — dziennik ZAWSZE pierwszy** (`0ce9609`) — czyta właściwą wypowiedź.
  ⚠️ User OBSERWUJE dalej (bug był przerywany: „raz ostatnia, raz przedostatnia") — nie zamykać tematu
  na twardo, dopóki nie przeżyje kilku dni użytkowania. → `czytaj-ostatnia-czyta-inna.md`.
- **Sprzątanie starych paczek** — potwierdzone: `updates/` trzyma tylko 1 paczkę. Doczyszczone RĘCZNIE
  ~3 GB (2026-07-20): martwy `~/.claude-voice-assistant` (po rebrandingu, migracja dawno wykonana),
  pobrana kopia 1.0.26, backup zepsutej 1.0.19, `dist-release/`, `dist/`, `build/`.

<details><summary>Historia (rozwiązane) — pliki pamięci, opis przyczyny</summary>

- **Pliki pamięci nie wchodziły w OSTATNICH zakładkach** (`0361565`, 2026-07-17) — AI Manager/ReShip
  startują jako ostatnie → claude nie zdążył wstać przed sztywnym terminem 8,5 s → tekst + Enter (50 ms)
  sklejały się w JEDEN odczyt PTY → Claude brał to za wklejkę, Enter = nowa linia, wiadomość WISIAŁA
  niewysłana w polu. Fix: `AgentTab.start_memory_files_watch` czeka na baner + ciszę, Enter osobno po
  500 ms, bezpiecznik 60 s. Zweryfikowane sondą PTY vs prawdziwy claude (stara 2/2 porażki, nowa 2/2 OK
  także pod obciążeniem) + bramka 9/9. ⏳ **user testuje na NOWEJ becie 2026-07-18**: czy wszystkie
  7 auto-startujących zakładek wczytuje pamięć (zwł. AI Manager i ReShip) + regresja: zwykłe pisanie,
  ręczny „Uruchom" dla agenta z `auto_start=False`. → `pty-tekst-enter-sklejenie.md`.
- **„czytaj ostatnią" BUG #6 — rozwiązanie STRUKTURALNE** (`0ce9609`, 2026-07-17) — „raz ostatnia, raz
  przedostatnia". Odkrycie: Claude Code **2.1.212** NIE odracza już zapisu wypowiedzi (przesłanka BUG #1
  nieaktualna), zapisuje przyrostowo → bramka `journal_lags_screen()` losowo słała na kruchy ekran, który
  przy długiej wypowiedzi wyłuskiwał OPCJE PYTANIA zamiast wypowiedzi. Fix: **dziennik ZAWSZE pierwszy**,
  ekran tylko gdy dziennik pusty; bramka wypada z toru decyzyjnego (zastępuje też BUG #5). Sonda PTY na
  żywym claude 2.1.212: 4/4 (okno odroczenia) + 2/2 (zwykła tura). ⏳ **test na becie 2026-07-18**: 🔊
  czyta najnowszą po (a) zwykłej długiej odpowiedzi, (b) moim pytaniu z przyciskami — klik PRZED
  odpowiedzią, (c) zaznaczenie Shift = czyta zaznaczone. → `czytaj-ostatnia-czyta-inna.md` (BUG #6).
</details>


## [2026-07-21] AKTUALNY STAN 1.0.27 — szczegoly wydania + redesign (details)

## AKTUALNY STAN (wersja 1.0.27 — WYDANA 2026-07-20, 3 platformy)

- **1.0.27 (WYDANE 2026-07-20, appcast 1.0.27, pipeline e2e OK):** DUŻE wydanie — po raz pierwszy trafia
  do userów **CAŁY redesign „Vibe Purple"** (leżał niewydany od 2026-07-09) + naprawy z ostatnich dwóch
  tygodni: pliki pamięci w ostatnich zakładkach (`0361565`), „czytaj ostatnią" BUG #6 (`0ce9609`), polskie
  znaki w WebTerminalu (`c38775f`), STT przez bramkę AI Managera (`eab76b3`), jeden silnik terminala
  wszędzie (`1dc983a`). Tag `v1.0.27`, commity `65f0e25`(kolory)+`bump`+`appcast`.
  - **Dwie poprawki czytelności sygnałów** (`65f0e25`, `SKIN_VERSION` 3 → 4): redesign zbliżył AKTYWNĄ
    zakładkę i tło NIEAKTYWNEGO okna do tła (różnica ~10/255 = 4%) i oba przestały cokolwiek znaczyć —
    user zgłosił „praktycznie nie ma różnicy" dla OBU naraz. Mechanizmy działały, za blisko były same
    kolory. Nowy token `theme.TAB_ACTIVE` `#251c37` (aktywna zakładka) + `SURFACE_INACTIVE`
    `#17141c`→`#2b2438`. Różnice wróciły do 10,2% i 12,2% (przed redesignem było 15%).
    ⚠️ Kolor aktywnej zakładki **celowo NIE idzie ze skórki** (`button_bg`) — patrz KONWENCJA KOLORU niżej.
  - ⚠️ **Mac i Windows dostały redesign PIERWSZY RAZ tym wydaniem** — paczki na tych systemach nie były
    z nim nigdy uruchomione przed publikacją (user świadomie wybrał publikację od razu, zamiast poczekalni).
    Przy zgłoszeniach „dziwny wygląd na Macu/Windows" zaczynaj od tej informacji.
  - **Weryfikacja przed publikacją (wzorzec do powtórzenia):** sha256 lokalne == serwer == feed (×4 paczki),
    HTTP 200 ×3, `.exe` 644, wpisy dla wszystkich 3 platform w feedzie, AppImage rozpakowany (wtyczki Qt
    obecne, `APP_VERSION` zgodna, zero sekretów) **oraz DOWÓD, że poprawka jest w środku paczki** — stałe
    `#251c37`/`#2b2438` w `gui.theme` i nazwa `tab_active` w `gui.main_window`, czytane z archiwum PYZ.
    ⚠️ Nazw zmiennych szukaj w `co_names`/`co_varnames`, NIE w stałych: `f"…{tab_active}…"` kompiluje się
    na kawałki tekstu + odczyt zmiennej, więc dosłownego `{tab_active}` w stałych NIE MA (mój pierwszy
    przebieg dał z tego powodu fałszywy `[FAIL]` — patrz „każdy [FAIL] najpierw WYJAŚNIJ").

<details><summary>Redesign „Vibe Purple" — szczegóły (wydany w 1.0.27)</summary>

- **DOKAŃCZANIE 2026-07-16 (4 commity):** poprawki wyglądu zgłaszane przez usera,
  każda potwierdzona przez niego na żywo w izolowanym drugim oknie. **`SKIN_VERSION` = 2 → 3** (`64840e2`).
  - `01afb7e` — **biała kreska nad paskiem zakładek** usunięta. Styl rysował „półkę" (`PE_FrameTabBarBase`)
    kolorami z PALETY, której nie przemalowaliśmy → 1 px czystej bieli; QSS tam NIE sięga. Fix:
    `_LeftAlignedTabStyle.drawPrimitive()` pomija ten prymityw. ⚠️ `setDocumentMode(True)` POGARSZA.
  - `3b75223` — kreska aktywnej zakładki **NA DOLE** (podkreślenie). ⚠️ **ŚWIADOME ODEJŚCIE OD MAKIETY**
    (makieta ma `top:0`) — decyzja usera, NIE „naprawiać" z powrotem.
  - `cc9bccf` — **obwódka pola poleceń w kolorze agenta** (ten sam, co ramka okna); agent bez `tab_color` →
    kolor skórki; focus = jaśniejszy wariant. ⚠️ grubość musi zostać 2 px (`AutoResizeTextEdit` liczy
    wysokość z oprawy → zmiana na focusie ucinałaby ogonki). Odświeżanie na żywo przez `update_config`.
    Ukryty też przycisk naprawy terminala (wyżej).
  - `64840e2` — **białe ikony** (mikrofon / „wyczyść pole" / błyskawica), **kolor niesie STAN**: nagrywanie =
    pulsująca czerwona IKONA (tło jak w sąsiednich przyciskach), przetwarzanie = biała klepsydra, czytanie =
    zielony głośnik, pauza = migający zielony trójkąt. Stop zostaje czerwony.

</details>


## [2026-07-21] Narracje wydan 1.0.26 / 1.0.25 + pelny akapit redesignu

- **REDESIGN „Vibe Purple" (2026-07-09, wydany w 1.0.27; commity `bc81a03` + `410c9ab`):** nowy wygląd wg makiety Cloud Design (`Vibe Coding Assistant redesign.zip`), funkcje bez zmian. Paleta w `src/gui/theme.py` (jedyne źródło kolorów), migracja skórki `SKIN_VERSION=2` (bez niej zmiana palety byłaby NIEWIDOCZNA), czcionki IBM Plex Sans + JetBrains Mono w paczce, terminal przemalowany w obu silnikach, gradientowa kreska nad aktywną zakładką (`_AccentTabBar`), gradientowy przycisk Wyślij, suwak „Auto-czytaj", kreskowe ikony SVG w kolorze skórki, dialogi/pasek statusu/wskaźnik RAM na palecie. Szczegóły → pamięć `redesign-vibe-purple.md`, pułapki → `qt-pulapki-qss-redesign.md`. **Porcje A+B+C potwierdzone przez usera na żywo** (C = 2026-07-14, izolowane drugie okno `test-druga-instancja-izolowana`: ogonki w dialogach, listy Skills/MCP z pełnymi opisami, podgląd skórki + „Anuluj" przywraca kolory, kolory zakładek, wskaźnik RAM).
- **1.0.26 (WYDANE 2026-06-29):** naprawa flagi „agent czeka" u ŹRÓDŁA — apka uruchamia
  `claude --session-id <uuid>` i PRZYPINA czytnik do dokładnego pliku sesji (koniec zgadywania).
  ⚠️ Bez `--session-id` (ręczny `--resume` po crashu) czytnik jest odpięty → 🔊 czyta złą wypowiedź.
- **1.0.25 (WYDANE 2026-06-26):** rebranding na „Vibe Coding Assistant" + seria poprawek UI.
  ⚠️ **Trwałe z rebrandingu:** infrastruktura ZOSTAJE stara (`/cva/` URL, appcast, repo GitHub
  `claude-voice-assistant`, wewn. binarka) — zmiana zerwałaby self-update. Migracja ustawień
  `~/.claude-voice-assistant`→`~/.vibe-coding-assistant` w `config.py` (stary katalog skasowany
  2026-07-20). Rebrand MUSI obejmować też `.ps1/.yml/.command` (pominięcie = padł build Windows).
  Szczegóły obu wydań → archiwum.


## [2026-07-21] Wyscig /login — pelna os czasu dowodow

**Zmierzone dowody (2026-07-20, laptop usera):** 8 procesów `claude` naraz (wszystkie z VCA, start 08:51), jeden
wspólny `~/.claude/.credentials.json`. Token wygasał **16:51**; w dziennikach sesji: `16:47:44` (79ed45af),
`16:50:32` (e7f7fb7f), `16:50:47` (c4e0146e), `16:51:40` i `16:52:45` (6e69f262) — **5 błędów w 4 zakładkach
w 5 minut**, a o `16:55:15` plik poświadczeń został ODŚWIEŻONY i był ważny kolejne 8 h. Zjawisko powtarzalne
(tego samego dnia też ~08:52, ~10:38, ~14:03, ~14:08).

**Przyczyna:** każda zakładka odświeża token SAMODZIELNIE. Bilet do odnowienia (`refreshToken`) jest jednorazowy
— pierwsza zakładka go zużywa i zapisuje nowy komplet, a pozostałe trzymają w pamięci bilet, który właśnie
przestał być ważny → dostają odmowę. Klasyczny wyścig wielu pisarzy o jeden rotujący sekret.
⚠️ **To NIE jest wina kolektora AI Managera** — on ten plik wyłącznie CZYTA, nigdy nie zapisuje i nigdy nie używa
`refreshToken` (sprawdzone; błędy występowały też przed jego dzisiejszymi zmianami).


## [2026-07-21] TODO: zrobione auto-sprzatanie kanalu aktualizacji (retencja VPS)

- [x] ~~**AUTO-SPRZĄTANIE KANAŁU AKTUALIZACJI NA VPS**~~ **ZROBIONE 2026-07-20** (zgłoszenie: agent
      SEO Managera). Automat: `packaging/prune-release-channel.py` (w repo) → na VPS jako
      `/usr/local/bin/cva-prune-releases.py` + cron `/etc/cron.d/cva-prune-releases`
      (**poniedziałki 4:30** — celowo NIE w niedzielę, wtedy leci czyszczenie Dockera).
      Domyślnie PRÓBA NA SUCHO, kasuje z `--apply`; `--drop-app NAZWA` kasuje całą porzuconą markę.
      Jednorazowo odzyskane **2,96 GB** (13 starych paczek Maca + 10 paczek sprzed rebrandingu):
      VPS **78% → 72%** (14 GB wolnego), `/opt/cva-web` 5,1 → **2,3 GB**. Kanał zweryfikowany po
      skasowaniu: appcast 200, wszystkie 3 instalatory 1.0.27 pobierają się. Ponowna próba na sucho
      = „nic do sprzątania" (skrypt idempotentny).
      **Trwałe zasady wbudowane w skrypt** (każda okupiona osobną rundą analizy):
      1. Lista NIETYKALNYCH z `appcast.json` + `*.html` — nigdy nie kasuj po dacie. Brak/uszkodzony
         appcast = skrypt PRZERYWA (nie zgaduje, co jest w użyciu).
      2. „N najnowszych" liczone w GRUPIE aplikacja+platforma (globalnie skasowałoby jedyny `.exe`).
         `.dmg` i `.zip` Maca to OSOBNE grupy — `.zip` niesie self-update, `.dmg` jest do ręcznej instalacji.
      3. Weryfikuj pod `https://pobierz.srv1251441.hstgr.cloud/cva/` — adres bez `pobierz.` nie ma trasy
         w Traefiku (404 + certyfikat zastępczy, wygląda jak „skasowałem za dużo"). Poprawione też
         w `~/Projekty/CLAUDE.md` ⚠️ (ten plik NIE jest wersjonowany — whitelist łapie tylko `CLAUDE-*.md`).


## [2026-07-21] TODO: duplikat wpisu o auto-compact (jest juz w sekcji DO TESTU NA ZYWO)

- [ ] ⏳ **Auto-czytanie ZAPĘTLA całą rozmowę po auto-compact — FIX ZAAPLIKOWANY + test automatyczny OK; czeka na TEST NA ŻYWO** (2026-07-06). `transcript_reader.poll()`: gdy Claude Code skompaktuje dziennik (przepisuje `<uuid>.jsonl` na krótszy → plik MNIEJSZY niż offset), stary kod robił `self._offset = 0` → `poll()` oddawał CAŁY plik → lektor recytował rozmowę od początku (powtarzało się przy każdym compact w długich zakładkach). **Zastosowany fix:** na skurczeniu `self._offset = size; return []` (skok na koniec jak priming — czytaj tylko nowe). `py_compile` OK + test na prawdziwym kodzie (rośnięcie→compact→nowa) przeszedł 3/3. Bez wpływu na flagę „?" (`waiting_for_user` ma osobny `_wait_last_size`). **ZOSTAŁO:** ZACOMMITOWANE 2026-07-06 (razem z zestawem 🔊/emoji/polskie-znaki) — czeka tylko na TEST NA ŻYWO po restarcie bety (compact zdarza się po długiej rozmowie). Szczegóły: pamięć `auto-czytanie-loop-po-kompaktowaniu.md`. Kandydat do COMMON (tailing pliku bywającego przepisanym krócej → seek-to-end, nie 0).


## [2026-07-21] AI Manager — pelny opis podlaczenia (domkniete)

## PODŁĄCZENIE DO AI MANAGERA (monitor zużycia tokenów) — ✅ DOMKNIĘTE

> Notatka od agenta AI Managera (2026-07-11; zaktualizowana 2026-07-15). Bramka działa i jest otwarta.
> ⚠️ **To apka „Vibe Coding Assistant"** (repo `claude-voice-assistant`), a jej klucz w panelu AI Managera nazywa się
> **„VCA" (id=3)**. Istnieje OSOBNA apka „Voice Assistant" (repo `voice-assistant`, lektor/tłumacz) — inne repo, inny
> kod, własny (jeszcze nieutworzony) klucz. NIE mylić; klucz „VCA" NIE należy do tamtej apki.
> **Stan:** STT (dyktowanie) na bramce ✅; rozmowa z Claude idzie przez CLI (nie HTTP) i jest monitorowana osobno →
> nic więcej do wpięcia po naszej stronie.

**WAŻNE — większość jest JUŻ zrobiona:** rozmowa z Claude idzie przez **CLI w terminalu (nie HTTP)**, więc
bramka jej NIE złapie i **nie musi** — zużycie Claude jest **już monitorowane osobno** przez kolektor Claude Code
AI Managera (czyta lokalne dzienniki `~/.claude/projects/**/*.jsonl`, timer co godzinę). Widać je w panelu
AI Managera → zakładka **„Claude Code"**.

**Dyktowanie (Groq Whisper) — ZROBIONE + POTWIERDZONE PRZEZ USERA 2026-07-13 (PL i EN działają na żywo)** (→ `stt-bramka-ai-manager.md`):
- Przepnij STT na bramkę: `POST https://ai.srv1251441.hstgr.cloud/v1/audio/transcriptions`,
  nagłówek `Authorization: Bearer aim-…` (klucz aplikacji **„VCA" (id=3)** z panelu AI Managera; widoczny raz),
  model z prefiksem `groq/…` (np. `groq/whisper-large-v3`).
- Auto-detekcja języka = nie wysyłaj pola `language` (jak dotąd).
- Kody: `401` zły klucz · `429` limit (+`Retry-After`) · `503` brak wolnego konta.
- Reszta bez zmian.


## [2026-07-21] Dwie pulapki uniwersalne (bialy blysk input / WebTerminal) — przeniesione do COMMON

- **Biały błysk pola input (QTextEdit) po Enter.** Samo `background-color` w stylesheet zostawia paletę `Base`=biała; przy `clear()`+zmianie wysokości (po wysłaniu) Qt na ~1 klatkę maluje biały Base ZANIM nałoży styl → migający biały prostokąt (intermittentnie, „tylko czasem" — zależnie od trafienia między klatkami). Fix: ustaw też `QPalette.Base/Text` (kolor skórki) na polu **i jego `viewport()`**, nie tylko w stylesheet (commit `fccd618`). Uniwersalna pułapka PyQt — gdyby powstał 2. projekt PyQt, kandydat do COMMON.
- **Biały błysk całego terminala (WebTerminal) ~1 s przy starcie.** `QWebEngineView`/`QWebEnginePage` maluje stronę na BIAŁO, dopóki `terminal.html` się nie wczyta (xterm.js + czcionka). Mimo że html ma ciemne tło, przez sekundę widać białą „pustą kartkę" silnika. Fix (1.0.20): `self._page.setBackgroundColor(QColor(0x1b,0x1b,0x1d))` PRZED `view.load(...)` w `web_terminal.__init__`. Dotyczy tylko WebTerminala (AppImage/Mac/Win), nie QTermWidgetu. Uniwersalna pułapka QtWebEngine → kandydat do COMMON.


---

# PELNA KOPIA CLAUDE-VOICE-ASSISTANT.md SPRZED KONSOLIDACJI 2026-07-26

> Doslowna kopia calego pliku (470 linii / 66 085 znakow), nie wybor fragmentow.
> Zywa wersja jest krotsza — tutaj szukaj wycietych szczegolow i pelnych narracji.

---

# CLAUDE-VOICE-ASSISTANT — Agent aplikacji desktopowej

**Przed pracą załaduj również:**
1. 🔴 [`docs/PRD.md`](docs/PRD.md) — Roadmap komercjalizacji 2026 (wizja, fazy, funkcje)
2. [`../CLAUDE-COMMON.md`](../CLAUDE-COMMON.md) — wspólne procedury i pułapki (uniwersalne)
3. [`CLAUDE.md`](CLAUDE.md) — auto-loaded przy starcie Claude Code w tym katalogu

> **Historia sesji (pełne narracje, dziennik zmian):** `CLAUDE-VOICE-ASSISTANT-ARCHIVE.md` (NIE czytany na starcie) + `git log`.
> **Zasada utrzymania:** do tego pliku trafiają TYLKO trwałe, aktualne, reużywalne rzeczy. Bez sekcji „SESJA <data>", bez stopki-dziennika. Gdy plik urośnie ponad budżet (~350 linii) → konsolidacja do archiwum (patrz CLAUDE-COMMON „ODCHUDZANIE PLIKÓW PAMIĘCI").

---

## Projekt

- **Lokalizacja:** `/home/hdkrytbhdkf/Projekty/claude-voice-assistant/`
- **Tech:** Python 3.12, PyQt5, QTermWidget (Linux), WebTerminal = xterm.js+QtWebEngine+PTY (Mac/Win), edge-tts, Groq Whisper, pygame
- **GitHub:** https://github.com/WojtekL7/claude-voice-assistant
- **Czym jest:** „pilot" nad CLI **Claude Code** — uruchamia `claude` w terminalu, dokłada głos (TTS/STT), zakładki agentów, MCP/Skills, skórki, auto-aktualizację. **Aplikacja NIE hostuje modelu ani nie zawiera CLI** — logowanie/konto Claude Code siedzi u usera (`~/.claude`).

## Uruchomienie
```bash
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant
source venv/bin/activate
python3 src/main.py
```
WebTerminal na Linuksie do testów: `CVA_WEBTERMINAL=1 python3 src/main.py`. QTermWidget wheel: `wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl`.

## Kluczowe pliki
| Plik | Rola |
|------|------|
| `src/config.py` | Konfiguracja: języki, głosy TTS, modele, ścieżki, `APP_VERSION`, `UI_TRANSLATIONS`, `DEFAULT_SPLITTER_SIZES` |
| `src/gui/main_window.py` | Główne okno, menu, TTS/STT, skórki, zakładki, auto-update, `_poll_transcripts` |
| `src/gui/agent_tab.py` | Zakładka agenta: terminal, splitter, input, przyciski |
| `src/gui/dialogs.py` | Dialogi (4-tab konfiguracja agenta, update, ClaudeSetupDialog) |
| `src/gui/terminal_backend.py` | Wspólny interfejs terminala + fabryka (QTermWidget vs WebTerminal) |
| `src/gui/web_terminal.py` | WebTerminal (xterm.js+QtWebEngine+PTY); ConPTY na Windows |
| `src/core/tts_engine.py` | TTS (edge-tts + pygame), kolejka z prefetch |
| `src/core/transcript_reader.py` | Czyta dziennik sesji `.jsonl` (auto-czytanie + flaga „?") |
| `src/core/text_cleaner.py` | `prose_from_markdown()` — proza dla TTS |
| `src/core/update_manager.py` | Self-update (pobieranie, sha256, samo-podmiana per OS) |
| `src/core/platform_utils.py` | OS/arch, env Qt, `update_platform_id()`, `macos_app_bundle()` |
| `tools/scan-dialog-clipping.py` | Skan regresji: buduje 16 okien offscreen, zgłasza widżety ucinające tekst |

## Konfiguracja użytkownika — `~/.claude-voice-assistant/`
`config.json` (język, głos, skin, `groq_api_key`, `auto_check_updates`) · `agents.json` (agenci + `splitter_sizes` per zakładka) · `memory_projects.json` · `quick_actions.json` · `tts.log` (błędy TTS) · `crash-logs/` (zrzuty „czarnej skrzynki" po crashu `claude` — patrz pułapka niżej).

## Zależności (uwagi)
- Klient HTTP = **`requests`**, NIE httpx (stt/license/update).
- **Groq = tylko STT** (Whisper, wymaga `GROQ_API_KEY`). **TTS = edge-tts, działa BEZ klucza.**
- `pyenchant` opcjonalny (`ENCHANT_AVAILABLE`); `asyncio` usunięte z requirements (stdlib).
- `pygame.mixer.init()` owinięte try/except (brak audio = TTS off, reszta działa).

---

## 🔴 PIERWSZE ZADANIE NASTĘPNEJ SESJI (user zatwierdził 2026-07-25)
**Konsolidacja tego pliku** (465 linii / 65,7 tys. zn. wobec budżetu ~350) — zanim weźmiesz cokolwiek innego.
Co ciąża i jaki przepis → pamięć `pamiec-odchudzanie-status.md`. ⚠️ Sukces mierz ZNAKAMI, nie liniami;
archiwum (`CLAUDE-VOICE-ASSISTANT-ARCHIVE.md`) dostaje PEŁNĄ kopię PRZED cięciem.

## ⏳ WCIĄŻ DO TESTU NA ŻYWO
- **🔍 SZUKANIE W ROZMOWIE — NOWA FUNKCJA** (2026-07-25). Lupa w dolnym pasku zakładki + `Ctrl+F`.
  Szuka w **dzienniku sesji** (`transcript_reader.conversation_entries()` — cała rozmowa: Twoje
  wiadomości i wypowiedzi agenta, bez myślenia/narzędzi/pod-agentów), NIE w buforze ekranu — bo bufor
  ma cap 5000 zn., niesie znaki sterujące i RÓŻNI SIĘ między silnikami. Dopasowanie bez ogonków
  i wielkości liter (`conversation_search.fold` — ⚠️ musi zachowywać DŁUGOŚĆ, inaczej pozycje trafień
  wskazują nie to miejsce). Klik w wynik: pełny fragment + Kopiuj/Przeczytaj **oraz** próba przewinięcia
  terminala (`TerminalBackend.scroll_to_text`, wynik asynchroniczny; WebTerminal = po buforze xterma
  BEZ dodatkowej biblioteki, QTermWidget zwraca `None` = „nie umiem", i wtedy apka NIC nie twierdzi).
  Bramki: `tools/test-conversation-search.py` **46/0** (z fixture z prawdziwego dziennika + kontrole
  negatywne + budowa okna i przycisku). Test u usera: (1) lupa i Ctrl+F otwierają okno; (2) fraza bez
  ogonków znajduje słowo z ogonkami; (3) klik w wynik przewija terminal, gdy fragment jest jeszcze
  w oknie; (4) Przeczytaj czyta fragment; (5) dwie zakładki = dwa niezależne okna szukania.
- **Serwery MCP** — sprawdzić na żywo (dodawanie/usuwanie, gating per agent, czy licznik i status w pasku
  pokazują prawdę). Zgłoszone przez usera 2026-07-25 jako zaległość.
- **Ładowanie agenta z CHMURY** — pobranie paczki na drugim komputerze i sprawdzenie, czy agent staje się
  używalny (agenci, pamięć, skille, klucze API, komunikat o projektach do `git clone`). Kod Fazy 1 gotowy
  i sprawdzony na atrapie oraz na prawdziwym Dysku Google, ale **klienckiego „pobierz i pracuj" user
  jeszcze nie przeszedł**. → `chmura-sync-agentow.md`
- **🔊 BUG #7 — RUNDA 3** (`d1ec938`, 2026-07-25). Rundy 1 (`e365307`) i 2 (`d825e6d`) były **przetestowane
  przez usera i OBIE zawiodły** — obie pytały terminal „czy leci tekst" (progi 2,0 s → 4,0 s + 200 zn./2 s).
  **Zmierzone na kliknięciu usera:** po jego odpowiedzi na pytanie agenta (11:20:13) agent **MYŚLAŁ 30 s**
  — w dzienniku ZERO wpisów, na ekranie animacja poniżej progu → karencja 4 s mijała w środku myślenia
  i apka czytała wypowiedź sprzed 6 minut (nowa doszła 11:20:47). Żaden próg liczony ze strumienia tej
  dziury nie zamknie. Runda 3: decyduje **STRUKTURA TURY** z dziennika (`transcript_reader.turn_snapshot()`
  → `idle` / `owes_text` / `tool_pending` / `unknown`, z pominięciem wpisów księgowych i pod-agentów);
  czekamy WYŁĄCZNIE przy `owes_text`, koniec czekania na DOWÓD (nowa wypowiedź · agent stanął bez pisania:
  cisza terminala **I** dziennik nie rośnie ≥4 s · narzędzie >4 s · bezpiecznik 60 s). Bramki: 45/0 na
  fixture z PRAWDZIWYCH wpisów CRM + mutacja kontrolna; regresja auto-czytania 22/22 i wyścigu /login 23/23.
  Test: (1) w CRM klik 🔊 tuż po wysłaniu zadania → ⏳ i czyta TĘ nową odpowiedź; (2) bezczynny agent →
  natychmiast; (3) pytanie na ekranie → w ~4 s czyta ostatnią + komunikat „agent zatrzymał się";
  (4) długie narzędzie → odpowiedź w kilka sekund; (5) zaznaczenie i auto-czytanie bez zmian.
  → `czytaj-ostatnia-czyta-inna.md`.
  - ⚠️ **PROFIL ZAKŁADKI CRM wywraca założenia projektowane pod „jedna długa odpowiedź na turę"**
    (zmierzone: 58 wypowiedzi, mediana **134 znaki**, mediana odstępu **40 s**, narzędzia 10 s–4 min).
    Bezpiecznik 30 s z rundy 1 zamieniał tam przycisk w pół minuty ciszy. Każdą zmianę w 🔊 / auto-czytaniu
    / fladze sprawdzaj na CRM, nie tylko na zakładce z rozmową.
- ~~**Nadganianie lektora**~~ ✅ **POTWIERDZONE 2026-07-25** — przeniesione do sekcji „POTWIERDZONE" niżej.
  ⚠️ **Przestroga z tamtej sesji zostaje aktualna:** pomiar „7/7 żywych dzienników nie kończy się znakiem nowej linii"
  (i wyciągnięty z niego wniosek „czytnik gubi najnowszy wpis") był **artefaktem złapania zapisu w locie** —
  8/8 plików USTABILIZOWANYCH kończy się `\n`. Zielony test jednostkowy dowodził tylko, że mechanizm *zadziała*,
  nie że w ogóle *występuje*. Nie idźcie tą drogą drugi raz. → `diagnoza-czytnika-dziennika-jsonl.md`.
- **Wykrywanie wyścigu „/login"** (`e6af2c3`) — patrz sekcja niżej. ✅ **Mechanizm ŻYJE** (2026-07-23:
  pierwszy wpis w `login-events.log` — `blad-api … zakladka=AI Manager … ENOTIMP`), ale to był błąd SIECI,
  nie wyścig o token → najważniejsza część (werdykt „wyścig vs prawdziwe wylogowanie") wciąż niewywołana.
- **Co JEST w uruchomionej becie (stan 2026-07-25):** wszystko powyższe **poza 🔊 rundą 3** (`d1ec938`) —
  beta wstała 10:47, commit powstał później. Po odhaczeniu 2026-07-25 zostają już tylko rzeczy, których
  NIE DA SIĘ wywołać na życzenie (wyścig /login, auto-compact) — nie czekają na chwilę usera, tylko na okazję. ⚠️ Sprawdzaj to ZAWSZE przed diagnozą „fix nie
  działa": `ps -o lstart= -p $(pgrep -f '[s]rc/main.py')` vs `git log -1 --format=%ad <commit>` — dwa razy
  uratowało to przed szukaniem błędu w kodzie, którego apka w ogóle nie miała.
- **Auto-czytanie po auto-compact** (`1b57c60`) — najstarsza niepotwierdzona rzecz. ⚠️ **NIE mylić z „auto-czytanie
  działa"** (to user potwierdził 2026-07-20 — patrz niżej): tu chodzi WYŁĄCZNIE o zachowanie po tym, jak Claude
  Code sam skróci długi dziennik. Wtedy plik ROBI SIĘ MNIEJSZY niż zapamiętany offset i stary kod ustawiał
  `offset=0` → lektor recytował rozmowę od początku. Test wymaga realnego compactu (długa rozmowa), więc nie da
  się go „zrobić na życzenie" — łapiemy przy okazji. → `auto-czytanie-loop-po-kompaktowaniu.md`.

## ✅ POTWIERDZONE PRZEZ USERA NA ŻYWO (2026-07-20, uzupełnione 2026-07-25)
Działają: auto-czytanie (zwykłe), pliki pamięci w OSTATNICH zakładkach (`0361565`), 🔊 „czytaj ostatnią"
po naprawie BUG #6 (`0ce9609`), sprzątanie starych paczek (`updates/` trzyma 1 paczkę).
**2026-07-25 — user potwierdził DWIE zaległe rzeczy naraz:**
- **Polskie znaki w terminalu + DYKTOWANIE** (`9aad8dd` wpisywanie wprost, `c38775f` WebTerminal) — bug
  „dyktowanie ucina litery po `ł`/`ó`" (otwarty od 2026-07-23) **ZAMKNIĘTY**. Potwierdza też diagnozę:
  to był JEDEN kanał (`sendText` → PTY → pole Claude Code), nie dwie osobne usterki, więc STT i bramka
  AI Managera były niewinne — jak pokazywał pomiar. → `qtermwidget-polskie-znaki-altgr.md`
- **Nadganianie lektora** (`2156fe8`) — kolejka TTS dogania ekran przy dłuższych zadaniach.
  → `auto-czytanie-spoznione-kolejka.md`
- **Filtr emoji/emotikonów w TTS** (`f80c35a`, czekał na test od 2026-07-06) — na tekście próbnym
  pominięte WSZYSTKIE: `:( :) ;) :-D xD :/ <3 -_- ^^ T_T o_O` oraz ⏳ ✅ → ▶ ░ ▪; kontrola odwrotna
  przeszła (`10:30`, `(netto)`, `3:1`, `(x)` przeczytane normalnie). ⚠️ Strażnika `(?<!\w)`/`(?!\w)`
  NIE ruszać: emotikon przyklejony do słowa (`gotowe:(`) zostaje w tekście, ale edge-tts i tak nie
  wymawia samej interpunkcji → luka bez kosztu, a strażnik chroni `10:30`, `C:\Users`, `https://`.
- **Auto-czytanie (zwykłe) na silniku WebTerminal** — długa wypowiedź (~3,3 tys. zn.) przeczytana
  od pierwszego zdania DO KOŃCA, w becie z `CVA_WEBTERMINAL=1`. Wcześniejsze potwierdzenie (2026-07-20)
  dotyczyło QTermWidgetu, a **pobrany AppImage Linuksa chodzi właśnie na WebTerminalu** → to domyka
  silnik, którego realnie używają użytkownicy. ⚠️ Nadal NIE domyka przypadku po auto-compact (inny tor).
⚠️ „Auto-czytanie działa" NIE domyka przypadku po auto-compact — to inny tor kodu (patrz ⏳ wyżej).
⚠️ 🔊 był bugiem PRZERYWANYM — user obserwuje dalej. Przyczyny i dowody → archiwum,
`czytaj-ostatnia-czyta-inna.md`, `pty-tekst-enter-sklejenie.md`.

- ~~**Przycisk „🔄 Napraw wygląd terminala"**~~ **UKRYTY 2026-07-16** (`cc9bccf`, `setVisible(False)`) — user
  schował, bo usterka nie wystąpiła od kilku dni, a przycisk świecił białym kwadratem. ⚠️ **Usterka NIE jest
  naprawiona, tylko uśpiona** — mechanizm (zrzut dowodowy + `claude --resume`) ZOSTAJE w kodzie i da się go
  wywołać bez przycisku. Powrót = skasuj `setVisible(False)` **I dopisz przycisk do
  `_apply_button_icon_styles`** (inaczej znów biały). → `tekst-rozstrzelony-w-terminalu.md`.

## AKTUALNY STAN (wersja 1.0.27 — WYDANA 2026-07-20, 3 platformy)

- **1.0.27** — pierwsze wydanie z CAŁYM redesignem „Vibe Purple" + naprawy: pliki pamięci w ostatnich
  zakładkach (`0361565`), 🔊 BUG #6 (`0ce9609`), polskie znaki w WebTerminalu (`c38775f`), STT przez
  bramkę AI Managera (`eab76b3`), jeden silnik terminala wszędzie (`1dc983a`). `SKIN_VERSION` = 4.
  ⚠️ **Mac i Windows dostały redesign PIERWSZY RAZ tym wydaniem** — paczki na tych systemach nie były
  z nim uruchomione przed publikacją. Przy zgłoszeniach „dziwny wygląd na Macu/Windows" zacznij od tego.
  Szczegóły wydania i weryfikacji przed publikacją → archiwum + runbook „DYSTRYBUCJA / WYDANIA" niżej.
- **KONWENCJA KOLORU (ustalona z userem 2026-07-16, rozszerzona 2026-07-20): skórka rządzi SPOCZYNKIEM,
  kod niesie STAN.** Kolory znaczeniowe (`DANGER` nagrywanie/stop, `SUCCESS` czytanie/wznów) siedzą w kodzie —
  w skórce dałoby się ustawić zielone nagrywanie i sygnał przestałby znaczyć. Nie dokładaj kluczy skórki
  „per stan" (39 kluczy = dialog skórki i config działają bez zmian). „Biel" = `theme.TEXT` `#eae6f2`,
  NIE `#ffffff` (czysta biel tylko na Wyślij, bo leży na gradiencie).
  - **Rozszerzenie: „gdzie jestem" to też STAN.** `theme.TAB_ACTIVE` (aktywna zakładka) NIE idzie ze skórki,
    choć kusi (`button_bg` był tam wcześniej) — ze skórki dałoby się ustawić aktywną zakładkę CIEMNIEJSZĄ
    od pozostałych i sygnał zniknąłby. Ta sama zasada, co przy nagrywaniu/czytaniu.
  - ⚠️ **Odcień NIOSĄCY SYGNAŁ musi mieć MARGINES kontrastu, nie tylko „inny numerek".** Redesign zszedł
    z 15% do 4% różnicy wobec tła i dwa sygnały naraz („aktywna zakładka", „okno nieaktywne") stały się
    nieczytelne, choć kod działał bez zarzutu. Przy zmianie palety **zmierz różnicę wobec SĄSIADA**
    (średnia RGB wystarcza), nie oceniaj na oko w edytorze — próg roboczy: **≥20/255 (~8%)**.
- **REDESIGN „Vibe Purple"** (`bc81a03`+`410c9ab`, wydany w 1.0.27): paleta w `src/gui/theme.py` =
  JEDYNE źródło kolorów; zmiana palety wymaga podbicia `SKIN_VERSION` (inaczej NIEWIDOCZNA — config
  nadpisuje). Szczegóły → `redesign-vibe-purple.md`, pułapki → `qt-pulapki-qss-redesign.md`, historia → archiwum.
- **1.0.26:** `claude --session-id <uuid>` przypina czytnik do dokładnego pliku sesji.
  ⚠️ Bez `--session-id` (ręczny `--resume` po crashu) czytnik jest odpięty → 🔊 czyta złą wypowiedź.
- **1.0.25 (rebranding na „Vibe Coding Assistant"):** ⚠️ infrastruktura ZOSTAJE stara (`/cva/` URL, appcast,
  repo `claude-voice-assistant`, wewn. binarka) — zmiana zerwałaby self-update. Rebrand MUSI obejmować też
  `.ps1/.yml/.command` (pominięcie = padł build Windows). Ustawienia: `~/.vibe-coding-assistant`.
- **Wieloplatformowość:** Linux (z kodu + AppImage), macOS (.dmg/.zip), Windows (.exe Inno). Pełna wersja PL/EN (domyślnie EN; PL gdy system polski).
- **Self-update:** macOS ✅ (od 1.0.8) · Windows ✅ (od 1.0.14) · **Linux ✅** (kod od 1.0.16, w feedzie od 1.0.17). **Pipeline WYDANIA potwierdzony e2e 2× (1.0.18, 1.0.19)** — tag→Actions(mac/win)+lokalny AppImage→rsync paczek (sha256!)→appcast→downloads. **URUCHOMIENIE spakowanego AppImage POTWIERDZONE 2026-06-20** (okno + terminal działają — PO naprawie braku wtyczek Qt/xcb; paczka 1.0.19 przebudowana, sha `325378b4…`, wydana). Wciąż DO POTWIERDZENIA: pełny **kliencki cykl self-update** (feed→pobierz→podmień→wstań) — uruchomienie i samo-podmiana niepotwierdzone razem. Mac/Win: spakowane paczki **URUCHAMIAJĄ się** (obserwacja usera: Mac pokazuje kreator przy starcie, Windows startuje) → podejrzenie crashu z braku wtyczek Qt na Mac/Win **ODRZUCONE** (PyInstaller na mac/win dociąga `cocoa`/`qwindows` sam). Do potwierdzenia zostaje tylko pełny kliencki cykl self-update.
- **Języki:** PL + jeden angielski (`en-US`); wariant brytyjski `en-GB` usunięty w 1.0.17 (scalony do en-US, migracja wsteczna w `set_ui_language`).
- **Strona pobierania:** `https://pobierz.srv1251441.hstgr.cloud` (basicauth) + publiczny feed `…/cva/appcast.json` (bez auth). Kontener `cva-web` (nginx) na VPS w `/opt/cva-web/`.

## KOMERCJALIZACJA 2026 — START (branding + strona, sesja 2026-06-22)
Ruszył plan z `docs/PRD.md` od strony brandingu/strony (NIE od kodu monetyzacji).
- **Nazwa publiczna: „Vibe Coding Assistant" (VCA)**; wewn. kod zostaje `claude-voice-assistant` (CVA). Marka bez „Claude". Domena do KUPIENIA (wolne `.app`: preferowana `vibe-code-app`, też `vibecoding`/`vca`/`vibecode`). → pamięć `vca-nazwa-domena.md`.
- **Logo** (Koncept „Prompt Wave": `>` terminala + fala): źródła + eksport w `branding/logo/` (SVG, PNG 16–1024, `vca.ico`, `vca.icns`, favicon; generowane `rsvg-convert` + Pillow). **WPIĘTE w aplikację** → `src/assets/icon.{png,svg,128,64}` (okno przez `main.py`; paczki generują `.icns`/`.ico` z `icon.png`). Galeria konceptów: `branding/logo-concepts.html`.
- **Strona produktowa (NA BRUDNO, staging):** `website/` → VPS `/opt/cva-web/html/cva/staging/` (publiczny, `noindex`), URL `https://pobierz.srv1251441.hstgr.cloud/cva/staging/`. PL+EN (`index.html`/`index-en.html`): loader, hero, funkcje (z wyróżnioną „Słuchaj, co wygenerował Claude Code"), cennik Free/Pro, pobieranie, FAQ, kontakt. **Makiety** (alert): płatności, pobieranie, formularz. Przełącznik 🌙/☀️ (+`prefers-color-scheme`), **auto-język po IP** (GeoJS `country.json` PL→pl, inne→en; ręczny wybór w `localStorage` nadrzędny; zabezpieczenie przed pętlą).
- **Dokumenty prawne (wersja robocza):** `polityka-prywatnosci`/`licencja` (PL) + `privacy-policy`/`license` (EN). Dostawca = **Fulfillment Polska**; placeholdery `[forma prawna/adres/NIP]`. ⚠️ przed publikacją: przegląd prawny + DOPISAĆ geolokalizację (GeoJS wysyła IP) do polityki.
- **Funkcje aplikacji (po kolei):** #1 ✅ własna ikona per zakładka (emoji/plik/paleta-popup). #2 ✅ kolor zakładki + ramka okna aktywnego agenta (1.0.21). #3 ✅ wybór głosu czytającego per agent (1.0.21; **322 darmowe głosy edge-tts**: 2 PL `Marek`/`Zofia`, 47 EN — dropdown z `edge_tts.list_voices()`).

## Architektura terminala
`terminal_backend.py` = interfejs `TerminalBackend` (metody: `set_shell_program`, `start_shell_program`, `send_text`, `selected_text`, `copy_selection`, `set_font`, `set_color_scheme`, `shutdown`; sygnały `output_received(str)`, `finished`). Fabryka: **Linux→QTermWidget** (chyba że `CVA_WEBTERMINAL=1`/brak wheela), **macOS/Windows→WebTerminal**. AgentTab woła backend, nie surowy widget → oba silniki tą samą ścieżką. Gotcha: `AA_ShareOpenGLContexts` + wczesny import QtWebEngine w `main.py`.

## Architektura auto-czytania (Droga A — z dziennika, NIE z terminala)
Auto-czytanie bierze prozę z **dziennika sesji** `~/.claude/projects/<zakodowana-cwd>/<sesja>.jsonl`, **nie** ze strumienia terminala (TUI = przerysowania, spinner literka-po-literce, ghost-text, skoki kursora → śmieci). Pipeline:
| Klocek | Plik | Rola |
|--------|------|------|
| Czytnik dziennika | `transcript_reader.py` | offset bajtowy, `poll()` zwraca NOWE bloki `type=="text"` z `assistant` nie-sidechain; `seek_to_end()` priming |
| Filtr prozy | `text_cleaner.prose_from_markdown()` | wycina kod/tabele/linki/emoji → proza |
| Lektor | `tts_engine.py` | kolejka z prefetch (`enqueue`), `clear_queue()` przy zmianie zakładki |
| Spinacz | `main_window._poll_transcripts()` (QTimer 800 ms) | aktywna zakładka → `enqueue`; nieaktywne → `pending_backlog` (cap 50) |

Tylko **aktywna** zakładka czyta; przełączenie ucisza poprzednią. Priming `seek_to_end()` pomija historię.

---

## TRWAŁE PUŁAPKI PROJEKTU
*(uniwersalne wersje wielu z nich są w CLAUDE-COMMON — tu skrót projektowy)*

- **QSS NIE SIĘGA DO TEGO, CO MALUJE SAM STYL Z PALETY → jasne artefakty w ciemnym motywie (2026-07-16).**
  Biała kreska nad zakładkami = „półka" paska (`PE_FrameTabBarBase`) rysowana kolorami PALETY, której nigdy
  nie przemalowaliśmy; `QTabBar { background }` maluje TŁO, nie ten prymityw → „stylujemy, a i tak świeci".
  Ta sama rodzina co biały błysk pola input (paleta `Base`) i domyślny biały kwadrat przycisku bez stylu.
  **Reguła: objaw „stylowane, a jasne" → podejrzewaj PALETĘ/prymityw stylu, nie QSS.** Fix przez
  `QProxyStyle.drawPrimitive()` (pomiń prymityw), nie przez `setDocumentMode` (POGARSZA — kreska szersza).
  Diagnoza: **mierz piksele** (PIL `getpixel`, skan pionowy) — ujawniło DWIE różne linie brane za jedną
  (3 px `#E2E8F0` = ramka koloru agenta, czyli FUNKCJA; 1 px `#FFFFFF` = bug). Bisekcja na replice z
  PRAWDZIWYCH klas (`_AccentTabBar`/`_LeftAlignedTabStyle`/`_AccentFrame` + realny QSS + `QMainWindow` z tłem),
  zwalidowanej zgodnością z realnym zrzutem — goły offscreen `QTabWidget` myli (patrz pułapka QTabBar niżej).
- **KOLOR PRZYCISKU MA WIĘCEJ NIŻ JEDNO ŹRÓDŁO — popraw animację I sprawdź pseudostany QSS (2026-07-16).**
  Mikrofon zalewała czerwień z DWÓCH miejsc naraz: `_animate_mic_pulse` ORAZ reguły
  `QPushButton:checked { background: DANGER }` we WSPÓLNYM `_apply_button_icon_style` (`dictate_btn` = jedyny
  `setCheckable(True)` na tym arkuszu). Naprawa samej animacji NIE wystarczyła — user słusznie zgłosił „tło
  dalej czerwone". Reguła USUNIĘTA, nie przywracać. Pytając „skąd ten kolor?" sprawdź `setIcon` **oraz**
  `:checked`/`:hover`/`:pressed`/`:disabled`. Weryfikacja bez GUI: wyrenderuj
  `icon_set.button_icon(k, state, color).pixmap()` i policz dominujący nieprzezroczysty piksel; kształt per
  stan = porównanie bajtów z `icon_by_name(...)` + KONTROLA NEGATYWNA (mic != hourglass), inaczej test
  „przechodzi", nie rozróżniając niczego.
- **Sztywne wysokości w GUI + wyższe czcionki redesignu = ucięte litery (2026-07-10).** Qt nie pokazuje suwaka,
  gdy widżet dostaje mniej miejsca niż potrzebuje — po cichu ściska rzędy i przycina glify. Objawy: ogonki p/y/ż
  w polu poleceń i oknie agenta, opisy skilli urwane w pół zdania. Zasada: **MIERZ, nie wpisuj liczby** (oprawa
  = `height() - viewport().height()`; wysokość linii = `blockBoundingRect`, NIE `lineSpacing`; wysokość wiersza
  listy = `heightForWidth` + zmierzona oprawa `QListWidget::item`). Regresję łapie `tools/scan-dialog-clipping.py`
  (16 okien). Pełny opis pułapek pomiaru → pamięć `qt-pulapki-qss-redesign.md`. Commity `782120a` + `694251c`.
- **WebTerminal — kopiowanie ginie przez odświeżenia Claude (1.0.23).** xterm.js KASUJE zaznaczenie przy każdym zapisie do bufora, a Claude (TUI) odświeża ekran ~1×/s → zaznaczenie z Shiftem POWSTAJE, ale znika w ~1–2 s (QTermWidget trzyma je mimo odświeżeń — stąd „działa w becie, nie w pobranej"). Fix (`terminal.html`): w trakcie przeciągania PRÓBKUJ zaznaczenie (`setInterval` 80 ms) i wysyłaj OSTATNIE NIEPUSTE do `_selection`; strażnik na `onSelectionChange` (tylko niepuste), by odświeżenie nie zerowało. Kopiowanie czyta `_selection` (`WebTerminalBackend.copy_selection`) → działa mimo migającego podświetlenia. Pełne „zamrożenie" jak QTermWidget = osobna przebudowa. **1.0.24 (TEST) — porządne rozwiązanie B1+B2** (samo próbkowanie z 1.0.23 było za słabe, u usera dalej nie działało): **B1** `_stripMouse()` wycina z wyjścia DECSET raportowania myszy (`?1000/1001/1002/1003/1005/1006/1015/1016 h`; WYŁĄCZAJĄCE `l` przepuszcza, carry na styku porcji) → xterm NIE wchodzi w tryb myszy → drag zaznacza natywnie, BEZ Shift (jak czysty bash). **B2** `safeWrite()` + `_writePaused`: na czas przeciągania (mousedown→mouseup, `el`/`window` capture) KOLEJKUJE `term.write`, po puszczeniu łapie zaznaczenie i `_flushWrites()` (bezpiecznik 6 s). Kompromis: Claude traci mysz w swoim oknie (przewijanie kółkiem działa natywnie). Wyjście PTY idzie `bridge.output → safeWrite` (`web_terminal._push_to_js`).
- **Flaga „?" — wyświetlanie samonaprawiające się (1.0.23).** `_refresh_question_flag` porównuje zamiar `show` z REALNYM stanem paska (`bar.tabButton(index, LeftSide) is not None`), NIE z notatką `_question_flag_shown` (USUNIĘTA) — rozjazd cache↔rzeczywistość trwale blokował znaczek przez early-return (objaw: armed=True w tle, a flagi brak; arming DZIAŁAŁ — potwierdził log). Teraz znaczek odtwarza się sam przy najbliższym ticku (≤0,8 s). Pokazuje się tylko na zakładce NIEaktywnej. Diagnoza: czujnik logujący + offscreen Qt (`QT_QPA_PLATFORM=offscreen`) — render OK, więc błąd był w logice cache.
- **QTabBar — pakiet pułapek (1.0.25, dużo iteracji).** (1) **QSS `QTabBar::tab` GEOMETRIA (padding/font-size) jest IGNOROWANA**, gdy pasek ma własny `QStyle` (Fusion `_LeftAlignedTabStyle`) — KOLORY z QSS działają, ale rozmiar/odstęp nie. Czcionkę i rozmiar ikony ustawiaj API: `tabBar().setFont(QFont(pt))`, `tab_widget.setIconSize(QSize)`. (2) **Widżet LeftSide (`setTabButton`) ma NIEUSUWALNY odstęp od ikony** — `margin`, szerokość ani override `subElementRect(SE_TabBarTabLeftButton)` go nie zamykają (próbowane, nie działa na realnym pasku). Flaga „?" jest teraz **ŻÓŁTĄ IKONĄ z lewej**: badge wmalowany w róg ikony-obrazka (`_icon_with_flag`) albo samodzielna ikonka dla agentów z emoji (`_flag_only_icon`); NIE kolorujemy tytułu (źle wg usera). (3) **`setTabIcon`/`setTabText`/`setTabTextColor` RESETUJĄ przewinięcie paska** — timer flagi (~0,8 s) wołający je co tick robił, że taby wracały po kliknięciu strzałki. Fix: `_refresh_question_flag` jest NO-OP gdy sygnatura `(show, nazwa, repr(icon_spec))` bez zmian (sig ze STABILNYCH danych — nie z `QIcon`, bo ikona-plik tworzona świeżo co wywołanie). (4) **emoji-ikona = TEKST** (rośnie z czcionką, `setIconSize` jej nie rusza, renderuje się monochromatycznie/kolorem tytułu); **obrazek = `setTabIcon`** (rośnie z `setIconSize`). (5) Dzióbki przewijania (`QTabBar QToolButton`) stylowalne tłem QSS + własne strzałki przez `::left-arrow/::right-arrow { image }`. ⚠️ **Render offscreen QTabWidget NIE oddaje wiarygodnie realnego paska** (wielokrotnie mylił) — sprawdzaj ZACHOWANIE testem funkcjonalnym (klik + geometria `tabRect`), a wygląd potwierdzaj u usera; najpierw sprawdź `ps -o etimes` instancji vs czas commita, czy beta na pewno ma nowy kod.
- **WebTerminal — kilka kopii apki naraz = zalew `Cookie sqlite error: database is locked`** (współdzielony domyślny profil QtWebEngine). Fix: profil **off-the-record** (`QWebEngineProfile(parent)` bez nazwy → wszystko w pamięci, zero zapisu) podany do `QWebEnginePage(profile, parent)` w `web_terminal.py`. Terminal (lokalny `terminal.html`) nie potrzebuje ciasteczek/cache.
- **Izolowane testy WebTerminala z kodu:** `python3 src/gui/web_terminal.py` = goły WebTerminal (jedno okno, BEZ `agents.json`) → reprodukcja błędów tylko-WebTerminalowych bez drugiej pełnej instancji apki (dwie instancje biją się o `agents.json`). Konsola JS → `~/.claude-voice-assistant/webterminal.log` (przez `_LoggingWebEnginePage`) = miejsce na tymczasowe `console.log`. Pełna apka w trybie WebTerminala: `CVA_WEBTERMINAL=1 python3 src/main.py`.
- **WebTerminal — bufor wejścia do PTY.** Powłoka startuje dopiero po `frontend_ready` (~2 s w AppImage); `claude`/wiadomość wysłane wcześniej `_write_pty` gubił po cichu. Fix: `_pending_input` w `__init__`, buforuj gdy `_proc is None`, opróżnij w `_spawn()`.
- **WebTerminal — czcionka pt vs px.** `set_font(size)` przekazuje PUNKTY; QTermWidget=`QFont(pt)`, xterm.js liczy w PIKSELACH. Konwersja `px=round(size*96/72)` TYLKO na styku `web_terminal._push_font` + `fontSize` startowy w `terminal.html`.
- **WebTerminal (QtWebEngine) — drag&drop pliku: ścieżki NIE ma w JS.** Chromium ukrywa ścieżkę upuszczonego pliku → JS w `terminal.html` jej nie dostanie (sam `preventDefault` na `dragover`/`drop` likwiduje tylko pułapkę „otwarcia pliku na całe okno", bez wklejenia). Ścieżkę bierz PO STRONIE Qt: `eventFilter` na `view.focusProxy()` (to ON dostaje `QDropEvent`), `mimeData().urls()`→`toLocalFile()`→`_write_pty`. **Reinstaluj filtr w `showEvent`** — Qt PODMIENIA focusProxy przy ukryciu/przenoszeniu między zakładkami/splitterami (stary filtr przepada). Pole input (QTextEdit) obsłuż osobno: `insertFromMimeData` z `hasUrls()` (inaczej wkleja surowy obrazek). Objaw zgłaszany przez usera: „upuściłem obrazek i apka się zacięła, nie dało się wyjść" (commit `a123504`).
- **Białe błyski (pole input po Enter, start WebTerminala)** — przyczyna leży w PALECIE Qt / tle
  `QWebEnginePage`, nie w stylach. Obie pułapki są uniwersalne dla apek Qt → przeniesione do
  `CLAUDE-COMMON.md` (sekcje „PUŁAPKI QT" i „PUŁAPKI QtWebEngine").
- **Emoji w `QPushButton` bywa NIEWIDOCZNE przy ściśniętym layoucie; paleta emoji = klikalny `QLabel` w POPUPIE.** Inline siatka emoji w `QFormLayout` (zakładka „Podstawowe") wcisnęła się — etykiety nachodziły na rzędy, glify zniknęły. Fix: paleta w osobnym `QDialog` (własna przestrzeń, `QScrollArea`), a komórki to `_ClickableLabel(QLabel)` z sygnałem `clicked` (QLabel renderuje KOLOROWE emoji; przycisk przy ciasnym layoucie gubi glif). ⚠️ ciemne tło popupu trzeba ustawić jawnie na `QScrollArea` + jego `viewport()` + widget treści (`setStyleSheet` na samym `QDialog` nie wystarcza — viewport świeci na biało). Konwencja ikony zakładki (`_agent_label_icon`): **emoji = prefiks w TEKŚCIE** zakładki (renderuje się jak '🤖 '), **własny plik = `setTabIcon(QIcon)`** + sama nazwa, brak = '🤖 Nazwa'; flaga „?" po zniknięciu przywraca ikonę pliku (nie pustą). Edycja istniejącego agenta odświeża zakładkę na żywo (`_refresh_open_agent_tabs`).
- **Wykrywanie `claude` MUSI iść przez powłokę logowania, nie przez PATH aplikacji.** GUI z Findera/Docka (macOS) dostaje OKROJONY PATH (bez Homebrew/nvm/npm) → `shutil.which("claude")` zawodzi mimo że CLI jest, a terminal go uruchamia (login shell `-l`). Skutek przed 1.0.20: kreator ustawień wyskakiwał na Macu PRZY KAŻDYM starcie. Fix: `platform_utils.claude_runnable()` pyta `zsh -lc 'command -v claude'` (mac/linux) / `where` (win) na wzbogaconym PATH — zgodnie z tym, co zobaczy terminal. Logowanie: `claude_logged_in()` = plik `~/.claude/.credentials.json` LUB wpis Keychain `␣Claude Code-credentials` (mac; `security find-generic-password -s`, returncode 44=brak). Gotowość liczona w wątku tła (powłoka logowania bywa wolna) → sygnał `_readiness_ready` do GUI.
- **„Pobrana apka działa inaczej niż z kodu" (Linux) = inny backend terminala.** AppImage celowo wyklucza QTermWidget (`excludes=["QTermWidget"]` w `.spec`) i odpala z `CVA_WEBTERMINAL=1` → pobrana wersja = **WebTerminal (Chromium)**, beta z kodu = **QTermWidget**. Bug „tylko w pobranej apce" reprodukuj z kodu: `CVA_WEBTERMINAL=1 python3 src/main.py`.
- **Flaga „?" (agent czeka).** Wykrywanie z dziennika+terminala, NIE z treści. Warunek = DWIE cisze: `transcript_reader.waiting_for_user()` (dziennik stoi) **I** `monotonic()-_last_terminal_data_ts >= QUESTION_TERMINAL_QUIET_SECS (3.0)` (TUI animuje pasek ~1×/s → cisza terminala = czeka). Sama cisza dziennika NIE wystarcza (dostaje tylko ukończone wpisy → stoi 20+ s podczas pisania).
- **transcript_reader — przypięcie sesji + SAMONAPRAWA (1.0.24 TEST).** `set_working_directory` zapamiętuje `_preexisting` + `_reader_start`; **Poziom 1** (preferowany): plik `.jsonl` powstały PO starcie zakładki (ignoruje równoległą/starą sesję — ochrona zachowana). **Poziom 2** (samonaprawa, gdy brak pliku z Poziomu 1): przygarnij plik istniejący WCZEŚNIEJ, ale zapisywany PO starcie czytnika (`_safe_mtime>_reader_start` = WZNOWIONA żywa sesja tej zakładki), z przeskokiem na koniec w `_ensure_session` (`offset=size`, nie odgrywaj historii). Stare NIETKNIĘTE pliki (`mtime<=start`) dalej pomijane. **Bug 1.0.23:** po self-update/restarcie/reopenie czytnik był ślepy na trwającą rozmowę → cisza w czytaniu I flaga nie wykrywała ciszy (objaw F-P: ręczny 🔊 milczał mimo żywej rozmowy). Potwierdzony danymi: apka start 12:56, plik sesji „birth" 13:02 → reguła „ignoruj preexisting na zawsze" gubiła go. Test logiki 9/9.
- **Lazy activation zakładek.** `self._ui_ready` (False przez `__init__`) w `_on_tab_changed`; primary tab aktywowany odroczonym `QTimer` (bo `setCurrentIndex(0)` nie emituje `currentChanged`). Guard idempotencji w 3 ogniwach (create / `_on_terminal_ready` / final-action).
- **Sygnały zakładki = jedno źródło.** `MainWindow._connect_agent_tab_signals(tab)` — oba tory tworzenia (Dodaj agenta / „+") muszą wołać tę metodę (inaczej „+" gubi `terminal_output` → licznik tokenów milczy).
- **`QTermWidgetBackend._on_received`.** `receivedData` niesie `str`, nie QByteArray — obsłuż `isinstance(str)` / `hasattr('data')` / `bytes()` (inaczej `bytes(str)` TypeError połykany → całe wyjście gubione).
- **Zamykanie zakładki.** Najpierw `setCurrentWidget(cel z MRU `_tab_mru`)`, POTEM `removeTab` — „+" to atrapa-QWidget; inaczej Qt aktywuje ją (czarny ekran) lub przypadkowo sąsiada (start claude).
- **Splitter nowej zakładki.** `config.DEFAULT_SPLITTER_SIZES=[1500,190]` (jedyne źródło) + `_inherit_splitter_sizes()` (dziedziczenie z aktywnej); `dialogs.get_data` NIE wpycha defaultu nowemu agentowi.
- **Zakładki macOS do lewej.** `_LeftAlignedTabStyle` = QProxyStyle na silniku Fusion + override `subElementRect(SE_TabWidgetTabBar)` (QMacStyle IGNORUJE `SH_TabBar_Alignment`); podpięty do `tab_widget.setStyle` ORAZ `tabBar().setStyle`. → CLAUDE-COMMON „PUŁAPKI QT" pkt 5.
- **Pauza TTS.** Sygnał `request_pause` → `_toggle_pause` → `tts.toggle_pause()`; przycisk ⏸ tylko podczas `PLAYING`.
- **i18n.** Centralny `config.t(key)` (import `from config import t as tr` — ABSOLUTNIE, nie `from ..config`); parytet 2 słowników `pl-PL`/`en-US` w `UI_TRANSLATIONS` (en-GB usunięty w 1.0.17 — `set(pl)==set(us)`); przy zmianie języka USUWAJ stare QAction przed odbudową menu (inaczej „ambiguous shortcut"). → pamięć projektu `i18n-architektura.md`.
- **TTS limit czasu.** `tts_engine._async_generate` ma `asyncio.wait_for(save, TTS_GEN_TIMEOUT=12)`, `_generate_audio` ponawia `TTS_GEN_ATTEMPTS=2`, błędy → `tts.log`; po nieudanych próbach pomija zdanie (lektor nie wisi). Bez tego zatkany edge-tts wieszał czytanie.
- **Windows spakowany (QtWebEngine).** `QTWEBENGINE_DISABLE_SANDBOX=1`; polyfill `replaceChildren` w `terminal.html` przed xterm.js (Chromium 83 z PyQtWebEngine-Qt5 5.15.2); `collect_all('winpty')` w `.spec`; `sys.stdout/err.reconfigure(errors="replace")` w `main.py`. → CLAUDE-COMMON „PAKOWANIE" pkt 10/12.
- **Rozróżnienie okna „z kodu (beta)" vs wydanego (AppImage).** `config.IS_DEV = not getattr(sys,'frozen',False)` (spakowane=frozen) → `APP_WM_CLASS` (`-beta` w dev), `APP_TITLE_SUFFIX` (' — beta'); `main.py`: `setApplicationName(APP_NAME + " (beta)")` + **`setDesktopFileName(APP_WM_CLASS)`**. Na **GNOME Wayland** dock/Show-Apps grupuje okna po **app_id** (= `setDesktopFileName`), NIE po X11 `WM_CLASS` → samo Qt nie wystarcza: trzeba zainstalować/poprawić `.desktop` w `~/.local/share/applications/` z `StartupWMClass` == app_id (beta=`claude-voice-assistant-beta`→`run-safe.sh`+ikona ze wstążką BETA; wydana=`claude-voice-assistant`→AppImage w `~/Applications/`+czysta `icon.png`). Nowy/zmieniony `.desktop` pojawia się w „Show Apps" dopiero **po wylogowaniu** (cache powłoki GNOME; na Wayland brak restartu powłoki w locie). Skróty są lokalne (poza repo).
- **PyInstaller NIE dociągnął wtyczek platformowych Qt → AppImage crashuje przy starcie.** W buildach Linuksa do 1.0.19 w paczce brakowało CAŁEGO katalogu `PyQt5/Qt5/plugins/` (m.in. `platforms/libqxcb.so` + jego zależność `libQt5XcbQpa`) → `"Could not find the Qt platform plugin xcb"` i crash w 1. sekundzie (exit 134, core dump). Nikt nie wyłapał, bo spakowanej wersji NIGDY nie odpalano (testy „z kodu"). Fix w `packaging/linux/ClaudeVoiceAssistant.spec` (commit `075ff54`): JAWNIE dołącz grupy wtyczek jako **`binaries`** (nie `datas`! — binaries każą PyInstallerowi przeanalizować i wciągnąć zależności wtyczki: `libQt5XcbQpa`, `libxcb-*`) z miejscem docelowym `PyQt5/Qt5/plugins/<grupa>` (bo `qt.conf` ma `Prefix=..`). Grupy: `platforms`, `xcbglintegrations`, `platformthemes`, `platforminputcontexts`, `iconengines`, `imageformats`, `wayland-*`. Dodany twardy bezpiecznik: build przerywa się gdy brak grupy `platforms`. Weryfikacja: rozmiar AppImage 168→189 MB; `find -name libqxcb.so` w rozpakowanej paczce; przeżycie procesu >5 s zamiast crashu. ⚠️ **Specki macOS (`binaries=[]`) i Windows (tylko `winpty`) mają TEN SAM brak — paczki Mac/Win 1.0.19 prawdopodobnie tak samo zepsute, NIEZWERYFIKOWANE.** Uniwersalna pułapka PyInstaller+PyQt → kandydat do COMMON „PAKOWANIE".
- **Linuksowy `.spec` był nieśledzony przez git** (reguła `*.spec` w `.gitignore`; specki macOS/Windows dodane przez `git add -f`, linuksowy nigdy). Skutek: recepta pakowania Linuksa poza wersjonowaniem → wadliwy build niereviewowany. Linuksowy `.spec` dodany przez `git add -f` (spójnie z pozostałymi). Reguła: każdy nowy `packaging/<os>/*.spec` → `git add -f`.
- **Paczka jest „świeża" — sekrety NIE są w buildzie.** `GROQ_API_KEY = os.getenv('GROQ_API_KEY','')` (brak hardcode); klucz Groq zapisuje NASZA apka do `~/.claude-voice-assistant/config.json` (`CONFIG_DIR.mkdir` + `json.dump` w `main_window`), login Claude tworzy **samo Claude Code** w `~/.claude/.credentials.json` (my tylko czytamy `~/.claude/skills/`). `datas` w spec = tylko `src/assets`+`config.py`+`i18n`+`gui/*.svg`. „Pobrana apka ma moje ustawienia" = ZŁUDZENIE: na własnym kompie czyta pliki z HOME, nie z paczki. **Weryfikacja czystości paczki:** `AppImage --appimage-extract` + `grep -r` po WYPAKOWANYCH plikach — raw-grep na samym `.AppImage` myli (squashfs kompresuje → przypadkowe `gsk_` w szumie ORAZ przeoczenia realnych sekretów w plikach).
- ⛔ **SPROSTOWANIE 2026-08-12: zdanie o „binarce dla Linuksa" i „bugu 2.1.113–114" w poniższym wpisie jest NIEPRAWDZIWE** (obalone pomiarem na `npm pack @anthropic-ai/claude-code@2.1.228`: to ATRAPA — 500 B tekstu — zostawiona przez niewykonany `postinstall`, kształt żywy nadal). Reszta wpisu (przesłanianie PATH, persystencja `claude_command`, naprawa) pozostaje aktualna. Aktualna wersja → `CLAUDE-VOICE-ASSISTANT.md` + `windows-claude-niezgodny-npm.md`.
- **`claude` zepsuty/niezgodny na Windows — apka utyka na STAREJ ścieżce (wsparcie 2026-06-30).** Objaw u usera: Windows „Nieobsługiwana aplikacja 16-bitowa" / „`…\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe` nie jest zgodna z wersją Windows", a w terminalu apki widać wpisaną PEŁNĄ ścieżkę `C:\…\Roaming\npm\claude.CMD`. **Przyczyna NIE u nas** — to bug Claude Code (`@anthropic-ai/claude-code` 2.1.113–2.1.114: `claude update`/instalacja na Windows pobiera binarkę dla Linuksa zamiast Windows; reprodukuje się w gołym PowerShellu `claude --version`). Nasza apka woła `claude.CMD` poprawnie. **Dlaczego instalacja natywnej wersji + restart NIC nie dają:** (1) `find_claude_command()`=`shutil.which('claude')` zwraca PIERWSZY z PATH → zepsuty `…\npm\claude.CMD` przesłania natywną w `~\.local\bin`; (2) `main_window` PERSYSTUJE `claude_command` (pełną ścieżkę) w `config.json` (load ~2224 / save ~2247) i podmienia ją tylko gdy `find_claude_command()` zwróci INNĄ (`_on_readiness_checked` ~2062) — a dalej zwraca npm. **Naprawa u usera:** `npm uninstall -g @anthropic-ai/claude-code` (usuwa shadowing) → natywny instalator `irm https://claude.ai/install.ps1 | iex` (PowerShell) → Ustawienia→„Komenda Claude Code" = samo `claude` → restart apki. **TODO produktowe:** `claude_runnable()` testuje tylko OBECNOŚĆ (`where claude`→0), nie URUCHAMIALNOŚĆ → zwraca True dla obecnego-ale-zepsutego `claude.exe`; dla nietech. usera dołożyć wykrycie „niezgodny/16-bit" + podpowiedź natywnej reinstalacji zamiast surowego okna Windows.

---

## DIAGNOZA CRASHU `claude` W ZAKŁADCE + „czarna skrzynka"
Objaw: zakładka „wypada" do gołego promptu basha z hintem `claude --resume <uuid>` — user widzi to jako „wylogowanie". To **crash procesu `claude`** (Claude Code), NIE crash CVA: powłoka (QTermWidget/WebTerminal) przeżywa, bo `claude` to jej dziecko → `backend.finished` NIE odpala. Ten sam ekran „Resume this session" to **ekran ratunkowy Claude Code po crashu**.

**Kolejność wykluczania (potwierdzona na crashu 2026-06-17, sesja `2b03a6c5`):**
1. **RAM/OOM?** → `journalctl --since today | grep -iE "earlyoom|oom-kill|killed process"`. Jest `earlyoom -m 8 -s 8 --prefer (claude|node|chrome|signal-desktop)` (ubija PREFEROWANE, m.in. `claude`, przy <8% mem+swap). Brak wpisu kill + log pokazuje sporo wolnego → NIE RAM. (Wtedy: 74% wolnej pamięci.)
2. **Wylogowanie/token?** → mtime + `expiresAt` z `~/.claude/.credentials.json` (8h token). Ważny + brak realnego `401` w dzienniku → NIE auth. ⚠️ „401" w `.jsonl` to zwykle fałszywka (treść pamięci, cyfry w timestampach `…19.401Z`).
3. **Błąd API/limit?** → w dzienniku sesji szukaj wpisu z `isApiErrorMessage:true`. Brak → claude nie zdążył odpowiedzieć (crash przed odpowiedzią).
4. Zostaje **crash wewnętrzny `claude`** (np. przy przetwarzaniu konkretnego promptu/załącznika). Współbieżne sesje współdzielą `~/.claude.json` + `.credentials.json` (backup `~/.claude/backups/.claude.json.backup.<ms>` co do sekundy crashu = kolizja na wspólnym stanie to podejrzany trop).

Dziennik sesji: `~/.claude/projects/<cwd-z-myślnikami>/<uuid>.jsonl`; padła sesja w pełni odzyskiwalna: `claude --resume <uuid>`.

**„Czarna skrzynka" (od 2026-06-17):** dokładny stack trace szedł na stderr terminala i się przewijał (CVA czyta `.jsonl`, NIE stderr). Dlatego `AgentTab` trzyma ring-bufor surowego wyjścia (`_terminal_capture`, ~64 KB, `config.TERMINAL_CAPTURE_BYTES`) i przy wykryciu podpisu `claude --resume <uuid>` w strumieniu zrzuca go (ANSI usunięte) do `~/.claude-voice-assistant/crash-logs/crash-<agent>-<data>.log`. **Pierwsze miejsce do czytania przy NASTĘPNYM crashu.** Implementacja: `_on_terminal_output` (tani pre-check `"resume" in`), `_maybe_dump_crash_log` (regex `_CRASH_SIGNATURE_RE` + debounce 30 s), `_dump_crash_log`. Pasywne — nie zmienia uruchamiania `claude`.

## PRZEPIS: dodać nowy model Claude Code
Aplikacja woła `claude --model <klucz>`. Dodanie modelu = **jeden plik `src/config.py`** = 3 słowniki jako jedyne źródło prawdy: `CLAUDE_MODELS`, `CLAUDE_MODELS_SHORT`, `CLAUDE_MODEL_CONTEXT_LIMITS` (dropdown/panel agentów/licznik tokenów zasilają się same).
1. **Zweryfikuj alias na żywo:** `claude --model <alias> -p "OK"` → exit 0.
2. Dopisz TEN SAM klucz do **wszystkich 3** słowników (`set(A)==set(B)==set(C)`).
3. `NEW_AGENT_DEFAULT_MODEL` zmieniaj świadomie (domyślny = **Opus**, tańszy).
4. Test: `py_compile src/config.py` + odpalenie apki.

Dostępne aliasy: `opus`/`sonnet`/`haiku`/`fable` (rozwiązują się po stronie CLI). **Fable 5** = okno 1M (jak Opus 4.8), ~2× droższy → do ciężkich zadań; Opus do bieżączki.

## ⚠️ Pamięć/RAM — każda zakładka = osobny proces `claude`
Aplikacja w Pythonie jest lekka (~80 MB). **Pamięć zżera Claude Code CLI: 3–5 GB NA ZAKŁADKĘ** (node, rośnie z długością sesji + dużym kontekstem startowym). 4 auto-startujące zakładki × ~4 GB przebijają RAM → swap → zawieszanie (i spowolnienie dyktowania/wszystkiego). Łagodzenie: mniej auto-startu (`auto_start=False`), restart długich zakładek (Stop→Uruchom / `/clear`), szczupłe pliki pamięci (mniejszy kontekst startowy), `earlyoom` jako siatka. Sam dokup RAM nie wystarczy — klucz to mniej jednoczesnych zakładek.

---

## 🟡 „Please run /login" = WYŚCIG O ODŚWIEŻENIE TOKENU — ETAP 1 (OBSERWACJA) ZROBIONY (`e6af2c3`, 2026-07-21)

> Zgłoszenie usera: „coś mnie wylogowało z Claude Code". **User NIE był wylogowany** — plik poświadczeń był
> cały i świeży. To zakładki VCA przewracają się nawzajem (diagnoza od agenta AI Managera, 2026-07-20).
> **Stan:** apka WYKRYWA odmowę, po opóźnieniu orzeka „wyścig vs prawdziwe wylogowanie" i zapisuje zdarzenie
> do `~/.vibe-coding-assistant/login-events.log` + komunikat na pasku. **Automatycznego restartu jeszcze NIE MA**
> — świadomie, do czasu potwierdzenia rozpoznania na żywych danych. ⏳ niesprawdzone u usera na żywo.

**Objaw:** jedna lub kilka zakładek nagle pokazuje `Please run /login` / `Unauthorized`, choć logowanie jest ważne.
Proces `claude` NIE ginie — wisi dalej z martwą sesją, więc wygląda to na zawieszenie, nie na problem z logowaniem.

**Zmierzone dowody (2026-07-20, laptop usera):** 8 procesów `claude` na jednym
`~/.claude/.credentials.json`; 5 odmów w 4 zakładkach w ciągu 5 minut wokół wygaśnięcia tokenu (16:51),
plik odnowiony 16:55 i ważny kolejne 8 h. Zjawisko powtarzalne kilka razy dziennie. Pełna oś czasu → archiwum.
⚠️ **To NIE jest wina kolektora AI Managera** — on ten plik wyłącznie CZYTA i nigdy nie używa `refreshToken`.

**Naprawa: pozbieranie się po przegranym wyścigu — NIE własne odświeżanie tokenu.**
⛔ Nie dokładaj w VCA logiki odnawiania tokenu: to dołożyłoby DZIEWIĄTEGO uczestnika wyścigu i pogorszyło sprawę.
Naprawą jest wykrycie odmowy i restart tej jednej zakładki — plik na dysku jest już wtedy poprawny.

Kroki (masz gotowe wszystkie klocki):
1. ✅ **ZROBIONE — Wykryj.** `TranscriptReader._is_api_error` + `take_api_errors()` → `_on_claude_api_error`.
   ⚠️ Rozpoznanie idzie po **PIECZĄTCE `isApiErrorMessage`** (Claude Code stawia ją sam; taki wpis ma też
   `message.model=="<synthetic>"`), **NIGDY po treści** — fraza „Please run /login" występuje w NORMALNEJ
   rozmowie (te pliki pamięci, opis tej usterki), więc dopasowanie po tekście restartowałoby zakładkę za
   każdym razem, gdy ktoś o tej usterce *napisze*. Kontrola negatywna w `tools/test-login-race.py`.
   Przy okazji: komunikaty błędów przestały iść do lektora (nie czyta już „Login expired" na głos).
2. ✅ **ZROBIONE — Odróżnij wyścig od PRAWDZIWEGO wylogowania** (bez tego pętla restartów):
   `platform_utils.claude_credentials_state()` (data zapisu + `expiresAt`, BEZ czytania samych tokenów)
   + `credentials_refreshed_since()` (czysta reguła, testowalna bez okna).
   ⚠️ **WERDYKT MUSI ZAPADAĆ Z OPÓŹNIENIEM** — zwycięzca odnawia plik dopiero po kilku minutach (zmierzone
   2026-07-20: **8 min** po pierwszej odmowie), więc ocena natychmiastowa orzekłaby „wylogowanie" dla KAŻDEGO
   wyścigu. Dopytujemy co minutę przez 12 min (`LOGIN_VERDICT_INTERVAL_SECS`/`_MAX_CHECKS`).
   ⚠️ **Pułapka wieloplatformowa:** na macOS poświadczeń NIE MA w pliku — siedzą w Pęku kluczy (`security
   find-generic-password -s "Claude Code-credentials"`), więc test „mtime pliku" tam nie zadziała →
   `available=False` = werdykt „nierozstrzygnięty" + bezpieczna rada „wpisz /login".

**Do ETAPU 2 (automatyczny restart) zostało — włączyć DOPIERO gdy `login-events.log` pokaże, że werdykty
trafiają bezbłędnie (dowód z żywych danych, nie z testów syntetycznych):**

3. **Restart zakładki** — proces startuje z `claude --session-id <uuid>` (`main_window.py:2344`), a czytnik jest
   przypięty do tego pliku (`TranscriptReader.pin_session`). Restart z TYM SAMYM `--session-id` zachowuje wątek
   rozmowy; świeży proces czyta odnowione poświadczenia i wraca do pracy. User nie powinien niczego zauważyć
   poza krótką przerwą (rozważ dyskretny komunikat na pasku, bez modala).
4. **Bezpieczniki:** maks. 1 restart na zdarzenie wygaśnięcia (np. cooldown ~2 min per zakładka) + licznik prób;
   po drugiej nieudanej próbie przestań i powiedz userowi wprost. Restart NIE może wejść w środek pisania odpowiedzi
   — sprawdź `waiting_for_user()` albo odczekaj do końca tury.
5. **Testy (oba kierunki, jak przy innych naprawach):** (a) wyścig → podstaw dziennik z `Please run /login`
   + świeży plik poświadczeń → zakładka ma się zrestartować raz; (b) prawdziwe wylogowanie → ten sam błąd, ale plik
   NIE odświeżony → zero restartów i komunikat. Bez (b) grozi pętla restartów przy realnym wylogowaniu.

**Łagodzenie dla usera do czasu naprawy (bez kodu):** mniej jednoczesnych zakładek — każda to kolejny uczestnik
wyścigu (przy jednej problem nie występuje, przy ośmiu jest niemal pewny co kilka godzin). Zbieżne z notatką
„Pamięć/RAM — każda zakładka = osobny proces `claude`" wyżej: mniej zakładek pomaga na oba problemy naraz.

---

## DYSTRYBUCJA / WYDANIA — runbook (sprawdzony 1.0.13→1.0.17; 1.0.17 = pierwsze pełne 3-platformowe z Linuksem)
1. Bump `APP_VERSION` w `src/config.py` → commit/push.
2. `git tag vX.Y.Z && git push origin vX.Y.Z` → GitHub Actions buduje **mac+win naraz** (`build-macos.yml` runner `macos-14`, `build-windows.yml` `windows-latest`) i publikuje Release. (Iteracja bez wydania: `gh workflow run build-*.yml --ref main`.)
3. `gh release download vX.Y.Z -p '*.zip' -p '*.dmg' -p '*.exe'` (do `dist-release/`, w .gitignore). ⚠️ Wzorzec **`*Setup.exe` NIE łapie** `VibeCodingAssistant-Setup-1.0.20.exe` (kończy się na `-X.Y.Z.exe`, nie na `Setup.exe`) — używaj `*.exe`.
4. **Wgraj paczki PRZED appcastem** (inaczej okno błędu 404): `.zip`(mac)+`Setup.exe`(win)+`.AppImage`(linux, build lokalny `CVA_SKIP_DEPS=1 bash packaging/linux/build.sh`) → `/opt/cva-web/html/cva/`; potem `appcast.json`. ⚠️ **Duże paczki (~200 MB AppImage) przez `scp` BYWAJĄ UCINANE (broken pipe) — wgrany plik krótszy, bez błędu widocznego od razu.** Używaj `rsync --partial --inplace -e ssh PLIK host:ścieżka` (wznawialny) i ZAWSZE sprawdź rozmiar/sha256 na serwerze PRZED uploadem appcastu (potwierdzone na 1.0.17: AppImage przyszedł 167/198 MB). ⚠️ **`rsync --inplace` PRZENOSI uprawnienia źródła — a `gh release download` zapisuje `.exe` jako `-rw-------` (600) → nginx nie może go odczytać → publiczny URL `.exe` daje HTTP 403** (`.zip`/`.AppImage` z gh są 644, działają). Po uploadzie ZAWSZE `chmod 644` na `.exe` (w `cva/` ORAZ w `downloads/` po `cp`). Potwierdzone na 1.0.21. Build LINUX 1.0.21 = 179 MB (OK). Uwaga: `/downloads/` jest za basicauth (HTTP 401 przez curl bez hasła — to NORMALNE); publiczny jest tylko `/cva/`.
5. `.dmg`/`Setup.exe`/`.AppImage` → `/opt/cva-web/html/downloads/` pod **stałą nazwą** (`VibeCodingAssistant-macos.dmg`, `VibeCodingAssistant-Setup.exe`, `VibeCodingAssistant-linux.AppImage`+`chmod +x`; starą jako `.bak`). Oszczędność łącza: exe/AppImage z cva/ skopiuj server-side (`cp`) zamiast wgrywać drugi raz.
6. Wpis do feedu: `python3 packaging/make-appcast-entry.py PACZKA --version X --platform <macos-arm64|windows-x64|linux-x64> --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ --appcast packaging/appcast.json --merge` → `scp appcast.json`.
7. **Weryfikacja publicznym URL:** `curl …/cva/appcast.json` (version + wpis dla platformy!) + `curl -I …PACZKA` (HTTP 200, `content-length`==`size`, sha256 serwer==feed).

**Retencja paczek na VPS:** cotygodniowy cron `/etc/cron.d/cva-prune-releases` (poniedziałki 4:30; źródło
w repo: `packaging/prune-release-channel.py`, domyślnie PRÓBA NA SUCHO, kasuje z `--apply`). Chroni pliki
wskazane przez `appcast.json` i strony; „N najnowszych" liczy w grupie aplikacja+platforma (`.dmg` i `.zip`
Maca to OSOBNE grupy). Uruchomienie i wyniki z 2026-07-20 → archiwum.

Uwagi: appcast ma **jedną** globalną `version` dla wszystkich platform (musi mieć wpis dla `update_platform_id()` bieżącej platformy, inaczej cicho „no_update"). `gh` zalogowany w keyring (po rotacji PAT). Aktualizacje pełnopaczkowe → przeskok wielu wersji bezpieczny (wyjątki: Mac ≤1.0.7 bootstrap, Win 1.0.12–1.0.13 kruchy downloader). Onboarding na świeżej maszynie: user musi doinstalować Node.js + `npm i -g @anthropic-ai/claude-code` + login (kreator `ClaudeSetupDialog` prowadzi).

---

## LINUX SELF-UPDATE (AppImage) — ZROBIONE (kod 1.0.16; commity `e91b76f` + `175b683`)
Działa jak na Macu, prościej (AppImage = JEDEN plik, nie katalog ze symlinkami → bez `ditto`, bez kwarantanny):
- `platform_utils.appimage_path()` → `$APPIMAGE` (plik .AppImage na dysku) lub `None`.
- `update_manager`: `can_self_replace` (Linux + `.appimage` + `appimage_path()`), `_apply_worker` → `_linux_self_replace()` = skrypt bash czeka aż PID zniknie → atomowa podmiana (`cp` do pliku tymcz. obok celu + `mv`) → `chmod +x` → restart `setsid` → `relaunch_ready`.
- Feed `linux-x64` w appcaście (publiczny `cva/`), strona PL+EN przycisk aktywny (`downloads/VibeCodingAssistant-linux.AppImage`, stała nazwa), instrukcje `instrukcja-linux.html(-en)`.

**Trwałe pułapki:** podmieniaj **`$APPIMAGE`**, NIE `sys.executable`/`/tmp/.mount_*` (mount znika po zamknięciu); `chmod +x` obowiązkowy; feed MUSI mieć wpis `linux-x64` (inaczej cicho „no_update"); paczka na serwer **PRZED** appcastem; `$APPIMAGE` istnieje tylko gdy uruchomione jako AppImage (z kodu → ścieżka „otwórz", to OK).

**Przetestowane:** gating `can_self_replace`/`appimage_path()` (oba tryby) + **mechanizm podmiany e2e na żywych plikach** (harness: proces-dziecko woła `_linux_self_replace` i ginie → pomocnik czeka na zgon PID → atomowy `mv` zmienia inode → `chmod +x` zachowany → `setsid` odpala nową wersję; zero śmieci `.new-*`). `UPDATE_APPCAST_URL` jest ZAPIEKANY w configu (brak env-override), więc pełny test GUI wymaga zbudowania paczki testowej.

**Zostało (uznane za wystarczająco bezpieczne):** jedyna niepokryta luka = pełny KLIENCKI cykl w SPAKOWANYM AppImage (uruchom→feed→dialog→pobierz→podmień→wstań). Część „pobierz/dialog/sha" wspólna z Mac/Win (sprawdzona e2e); zostaje „czy zapakowany AppImage wstaje po podmianie". **Stan 2026-06-19:** 1.0.18 i 1.0.19 są w feedzie (pipeline wydania potwierdzony e2e 2×), więc test klienckiego cyklu = po prostu uruchomić zainstalowany AppImage i pozwolić mu się zaktualizować. Wciąż NIE potwierdzony przez usera (poprawki testowane z kodu). Pierwszą paczkę user instaluje raz ręcznie, od niej w górę aktualizuje się sama.

## STRONY INSTRUKCJI (`packaging/web` → VPS `/opt/cva-web/html/cva/`, publiczne)
PL + `-en`. Instalacja 3 systemów **SCALONA** w `instrukcja-instalacja.html` (górne menu macOS·Linux·Windows·Dyktowanie·Agenci; OS-y przełączane zakładkami JS — kotwica `#os`). Stare `instrukcja-{macos,linux,windows}{,-en}` = przekierowania na scaloną → **stare apki dalej działają**. Generatory (uruchamiać z `packaging/web/`): `build-instalacja.py` scala sekcje stron OS — **MUSI prefiksować `id`/anchory/`copyCmd('id')` per panel** (3 strony używały tych samych `id` cz1..cz5/npmcmd → kolizja `getElementById`; `copyCmd` siedzi PO `<footer>`, więc dołączany osobno); `inject-menu.py` wstrzykuje górne menu + sekcję „jak uruchomić dyktowanie" (idempotentny, pomija gdy `topnav` jest). ⚠️ `build-instalacja.py` nadpisuje strony OS przekierowaniami — przed ponownym uruchomieniem `git checkout` oryginałów. Aplikacja linkuje przez `config.install_guide_url`. Test układu: headless Chromium (Playwright) na `file://`.

## Inne otwarte TODO
- [x] ~~🔴 **DYKTOWANIE ucina litery po `ł`/`ó`**~~ ✅ **ZAMKNIĘTE 2026-07-25** (user potwierdził na żywo).
      Hipoteza „ten sam kanał co wpisywanie wprost" okazała się trafna — naprawił to `9aad8dd`
      (eventFilter → `sendText`), bez ruszania STT. → sekcja „POTWIERDZONE" wyżej.
- [ ] **XSS (niski prio):** `src/gui/web_terminal.py` `_show_failure_page` — surowy f-string z `reason`
      (reszta panelu admina domknięta 2026-07-14, `6b70b5a`; opis → archiwum).
- [ ] **Redesign — do rozważenia po testach:** własna belka tytułowa (świadomie pominięta — ryzyko Wayland/macOS); okno ustawień jako jeden modal z bocznym menu zamiast menu górnego + osobnych dialogów — to zmiana UKŁADU, nie wyglądu, więc poza zakresem redesignu.
      **Makieta tego ekranu żyje w repo:** `design/makieta-2026-07-09/` (`.dc.html` + `support.js`
      + README ze stanem wdrożenia; `settingsTabs` = ten niewdrożony ekran). Zrzuty świadomie POMINIĘTE
      — repo jest **publiczne**; pełny eksport z nimi: `~/Projekty/makiety/vca-redesign-2026-07-09.zip`.
      ⚠️ `.gitignore` ma teraz `*.zip` — kolejny eksport makiety rozpakuj do `design/`, nie commituj archiwum.
- [ ] **Strona/branding (po stronie usera/decyzji):** uzupełnić dane firmy `[forma prawna/adres/NIP]` w polityce+licencji (PL+EN naraz); kupić domenę; dopisać geolokalizację (GeoJS) do polityki prywatności; podpiąć link „Instrukcje" na stronie (teraz `#`) do `instrukcja-instalacja.html`; przegląd prawny przed publikacją; potem przepiąć stronę ze stagingu na docelową domenę.
- [ ] Potwierdzić **kliencki** self-update spakowanego AppImage: uruchomić zainstalowany AppImage i sprawdzić aktualizację do 1.0.19 (patrz sekcja LINUX SELF-UPDATE).
- [ ] **BUG Mac — CRASH QtWebEngine po wybudzeniu (nie „ostrzeżenie"!):** zrzut od usera (26.06, wersja **1.0.25**) = macOS „Raport problemu / Aplikacja nieoczekiwanie zakończyła pracę" (OK / Otwórz ponownie) → user bierze to za cykliczne ostrzeżenie, bo „Otwórz ponownie" → znów crash. Sygnatura: `Crashed Thread 0 CrBrowserMain` (QtWebEngine/Chromium), `EXC_BAD_ACCESS (SIGSEGV)`, **Time Since Wake: 88 s** = crash krótko po śnie. To DOKŁADNIE pamięć `mac-qtwebengine-crash-po-snie.md` (crash w CrBrowserMain po wybudzeniu, nie błąd wersji, raport leci do Apple; nasz `crash-logs/` łapie tylko crash `claude`, NIE QtWebEngine). Na **1.0.26** wystąpił RAZ (user niepewny czy po wybudzeniu), po zamknięciu+otwarciu apki NIE wraca → rzadki, niereprodukowalny przy normalnym starcie = niski priorytet. Kierunek naprawy (do analizy, NIE wdrażać, tylko gdyby się nasilił): flagi QtWebEngine na macOS (np. wyłączenie GPU/sandbox po wzorze `QTWEBENGINE_DISABLE_SANDBOX` z Windows) LUB reinicjalizacja WebTerminala na sygnał wybudzenia.
- [ ] **Mac — Claude Code (CLI) przez npm: 401 + auto-update failed (NIE bug naszej apki).** Zrzut 1.07 (v1.0.26, apka działa OK): w terminalu dwa komunikaty CLAUDE CODE (nie naszej apki) — `Please run /login · API Error: 401 Invalid authentication credentials` (Claude Code wylogowany → user wpisuje `/login` w terminalu) + `Auto-update failed: no write permission to npm prefix · Run /doctor` (npm-owy Claude Code nie ma praw zapisu do prefiksu → nie aktualizuje się sam). Macowy odpowiednik znanego problemu npm z Windows (`windows-claude-niezgodny-npm`). Priorytet: `/login` odblokowuje agenta; auto-update do naprawy osobno (reinstalacja Claude Code natywnym instalatorem zamiast npm, albo naprawa praw prefiksu npm). Powiązanie z TODO „wykrywanie zepsutego `claude`".
- [ ] Test zadania „nodecli" instalatora na świeżym Windows (auto-instalacja Node+Claude Code).
- [ ] Kolejne języki: dopisać słownik w `UI_TRANSLATIONS` (parytet!) + `SUPPORTED_LANGUAGES` + `detect_system_language` + pliki `-xx.html` + dropdown.
- [ ] **Wykrywanie ZEPSUTEGO `claude` (nietech. user, Windows):** `claude_runnable()` testuje tylko obecność, nie uruchamialność → przy zepsutej binarce npm apka utyka i pokazuje surowy błąd Windows („16-bit"/„niezgodny"). Dodać wykrycie tego stanu + czytelną podpowiedź natywnej reinstalacji (`irm https://claude.ai/install.ps1|iex` + `npm uninstall -g @anthropic-ai/claude-code`). Patrz pułapka „`claude` zepsuty/niezgodny na Windows" (2026-06-30).

## CHMURA — stan prac (Faza 1)
Plan: `docs/PLAN-CHMURA-SYNC.md` (sekcja 9 = szyfrowanie). Pamięć: `chmura-sync-agentow.md`.
- **GOTOWE:** silnik paczki (`src/core/cloud/agent_bundle.py`) + szyfrowanie end-to-end
  (`bundle_crypto.py`, AES-256-GCM + scrypt). Testy `tools/test-cloud-crypto.py` (26/26)
  + `tools/test-cloud-bundle.py`. Na żywych danych: 10 agentów, 23 skille (273 pliki),
  15 plików pamięci, szybkie akcje → **1081 KB** zaszyfrowanej paczki.
- **Paczka niesie:** agentów (ikony/kolory/głosy), pliki pamięci, definicje skilli, gating
  MCP, szybkie akcje, projekty pamięci, skórkę, język **oraz klucze API** (decyzja usera).
  NIE niesie: kodu projektów (idzie przez `git clone`) ani `claude_command` (ścieżka lokalna).
- **✅ POŁĄCZENIE Z DYSKIEM GOOGLE DZIAŁA NA ŻYWO (2026-07-21, `a7663f5`+`a6c5ddc`).**
  `google_drive.py`: OAuth desktop + PKCE, loopback `127.0.0.1`, zakres `drive.file`
  (apka widzi TYLKO własne pliki → Google nie wymaga audytu), token lokalnie z prawami 600.
  Testy: 22 na atrapie serwera + 22 e2e („przeprowadzka na nowy komputer") + **przebieg
  na PRAWDZIWYM Google** (logowanie → folder → wysyłka → pobranie bajt w bajt → sprzątnięcie).
  Projekt Google usera: `impressive-bay-503111-d1` („VCA Google"), klient typu `installed`;
  dane klienta i token w `~/.vibe-coding-assistant/cloud-google-{client,token}.json` (600).
  ⚠️ Aplikacja MUSI być w trybie **Produkcja** (nie „Testowanie") — inaczej Google kasuje
  bilet odnowienia po 7 dniach i user loguje się co tydzień.
- **✅ FAZA 1 KOMPLETNA W KODZIE (2026-07-21).** Ekran „Chmura" (`src/gui/cloud_dialog.py`,
  menu Ustawienia, prosty — user odrzucił makietę Cloud Design): konto, hasło paczki,
  wyślij/pobierz. Praca z siecią w wątku roboczym (logowanie czeka minuty na zgodę
  w przeglądarce → w wątku okna zamroziłoby apkę). Testy: `tools/test-cloud-dialog.py` (22).
  **Hasło:** apka proponuje kod z `generate_passphrase()`, ale user może wpisać własne
  (jego decyzja); kod zapamiętany w `cloud-passphrase.txt` (600), na nowym komputerze
  przepisywany z kartki. Funkcja docelowo **Pro** (`license_manager` to wciąż zaślepka —
  miejsce na sprawdzenie licencji oznaczyć, ale NIE udawać działającej blokady).
- **✅ PRZEPROWADZKA POTWIERDZONA NA PRAWDZIWYCH DANYCH + PRAWDZIWYM DYSKU (2026-07-21):**
  10 agentów, 1098 KB zaszyfrowanej paczki, 12 zapisanych plików pamięci, 273 pliki skilli,
  **8 projektów do `git clone`**, 0 ostrzeżeń; ścieżki przemapowane, klucze API dojechały,
  `claude_command` NIE. Import szedł do katalogu tymczasowego → konfiguracja usera nietknięta.
  ⚠️ **Pliki pamięci leżące w repo gitowym są ŚWIADOMIE pomijane przy imporcie** (przyjdą
  z `git clone`; kopiowanie wywaliłoby klon do niepustego katalogu) → okno MUSI mówić, ile
  projektów czeka na sklonowanie, inaczej user widzi agentów bez kodu i zgłasza to jako błąd
  (`7daddb4`). Pułapka pomiaru: „tylko 4 pliki .md w katalogu" było artefaktem liczenia —
  ten sam `CLAUDE-COMMON.md` zapisywany dla 10 agentów to JEDEN plik na dysku.
- ⚠️ **Etykieta bez jawnego `color:` = czarny tekst na czarnym tle** (zgłoszone przez usera,
  `24eb386`). Qt bierze wtedy barwę z palety, nie ze skórki. W `cloud_dialog` pilnuje tego
  reguła strukturalna w teście (każdy `QLabel` musi mieć `color:`), sprawdzona kontrolą
  negatywną. ⚠️ Podgląd okna renderowany z WŁASNYM, doraźnym stylem tego NIE pokazał —
  zrzut offscreen z ad-hoc QSS nie odtwarza warunków aplikacji.
- ⚠️ **Znane ograniczenie: KASOWANIE NIE PROPAGUJE SIĘ.** Usunięta szybka akcja / plik pamięci
  zostaje na drugim urządzeniu (import tylko dodaje i nadpisuje). Bez znaczenia przy ręcznym
  „wyślij/pobierz", do rozwiązania przy automatycznej synchronizacji (Faza 2/3).
- ⚠️ **`cryptography` + PyInstaller:** działa BEZ własnego hooka (rozszerzenie Rust
  `_rust.abi3.so` wchodzi samo) — **zweryfikowane tylko na Linuksie 2026-07-20**.
  Mac/Windows do potwierdzenia przy najbliższym buildzie CI (wcześniej paczki nie importowały
  tej biblioteki, więc 1.0.27 niczego tu nie dowodzi).

## Sygnały PyQt (AgentTab)
`message_sent(str)` · `terminal_output(object)` · `status_changed(str)` · `request_tts(str)` · `request_dictation(bool)` · `request_pause` · `splitter_changed(list)`.

## Częste problemy
| Problem | Rozwiązanie |
|---------|-------------|
| QTermWidget not found | `pip install wheels/qtermwidget-*.whl` |
| TTS nie działa | internet (edge-tts); sprawdź `~/.claude-voice-assistant/tts.log` |
| STT nie nagrywa | `GROQ_API_KEY`, mikrofon |
| `claude` not recognized | doinstalować Node + `npm i -g @anthropic-ai/claude-code` + restart |
| `claude.exe` „niezgodny z Windows"/16-bit | ⛔ przyczyna SPROSTOWANA 2026-08-12 (atrapa po `postinstall`, nie binarka Linuksa) — ~~Zła binarka z npm (bug Claude Code 2.1.113–114)~~ — `npm uninstall -g @anthropic-ai/claude-code` + natywny instalator `irm https://claude.ai/install.ps1\|iex`; w apce komenda=`claude` (patrz pułapka „`claude` zepsuty/niezgodny na Windows") |
| Apka nie startuje | `python3 -m py_compile src/main.py` |
| Zawieszanie przy 2+ zakładkach | RAM — patrz „Pamięć/RAM" wyżej |

---

## PODŁĄCZENIE DO AI MANAGERA — ✅ DOMKNIĘTE
Rozmowa z Claude idzie przez CLI (nie HTTP) → bramka jej nie łapie i nie musi; zużycie liczy osobno
kolektor Claude Code AI Managera z lokalnych `.jsonl`. Po naszej stronie nic więcej do wpięcia.
**STT (dyktowanie) na bramce** (potwierdzone na żywo 2026-07-13): `POST https://ai.srv1251441.hstgr.cloud/v1/audio/transcriptions`,
`Authorization: Bearer aim-…` (klucz aplikacji **„VCA" (id=3)**), model z prefiksem `groq/…`; język auto = NIE wysyłaj
pola `language`; kody: `401` zły klucz · `429` limit · `503` brak wolnego konta. → `stt-bramka-ai-manager.md`.
⚠️ NIE mylić z osobną apką „Voice Assistant" (repo `voice-assistant`) — inny projekt, inny klucz.

## 🔊 „czytaj ostatnią" — RUNDY 1–3 (historia, bug ZAMKNIĘTY 2026-08-26 rundą 6)

- ~~🔴 **🔊 „czytaj ostatnią" — RUNDA 3 PRZETESTOWANA 2026-07-27: ZAWIODŁA**~~ (historia, wciąż aktualne ostrzeżenia niżej). User: „nadal czasem czyta przedostatnią". Kod rundy 3 BYŁ w becie (start 27.07 09:19 vs commit 25.07 12:08 — sprawdzone), więc to realna porażka naprawy, trzecia z rzędu. ⛔ **Runda 4 zaczyna się od POMIARU na kliknięciu usera, NIE od poprawki logiki** — trzy rundy poprawiały decyzję (ruch terminala → wolumen strumienia → struktura tury) i każda zawiodła. Najpierw dopytaj: która zakładka · czy było ⏳ „czekam" czy przeczytało natychmiast · co robił agent w chwili kliknięcia · jak często. Szczegóły i kandydat na hipotezę → `czytaj-ostatnia-czyta-inna.md`.
- ~~**🔊 „czytaj ostatnią" — RUNDA 3**~~ (`d1ec938`, historia). Rundy 1 (`e365307`) i 2 (`d825e6d`) user przetestował i OBIE zawiodły — obie pytały terminal „czy leci tekst" (progi 2,0 s → 4,0 s + 200 zn./2 s). Zmierzone na kliknięciu usera: agent **MYŚLAŁ 30 s** (zero wpisów w dzienniku, animacja poniżej progu) → karencja mijała w środku myślenia i apka czytała wypowiedź sprzed 6 minut. Żaden próg ze strumienia tej dziury nie zamknie. Runda 3 decyduje **STRUKTURĄ TURY** z dziennika (`turn_snapshot()` → `idle`/`owes_text`/`tool_pending`/`unknown`, z pominięciem wpisów księgowych i pod-agentów); czekamy WYŁĄCZNIE przy `owes_text`, koniec czekania na DOWÓD (nowa wypowiedź · cisza terminala **I** brak przyrostu pliku ≥4 s · narzędzie >4 s · bezpiecznik 60 s). Bramki 45/0 + regresje 22/22 i 23/23. Test: w CRM klik 🔊 tuż po wysłaniu zadania → ⏳ i czyta TĘ nową · bezczynny agent → natychmiast · pytanie na ekranie → ~4 s i komunikat „agent zatrzymał się" · długie narzędzie → odpowiedź w kilka sekund · zaznaczenie i auto-czytanie bez zmian. → `czytaj-ostatnia-czyta-inna.md`
  - ⚠️ **Profil zakładki CRM wywraca założenie „jedna długa odpowiedź na turę"** (zmierzone: 58 wypowiedzi, mediana **134 znaki**, mediana odstępu **40 s**, narzędzia 10 s–4 min). Każdą zmianę w 🔊 / auto-czytaniu / fladze sprawdzaj NA CRM, nie na zakładce z rozmową.
