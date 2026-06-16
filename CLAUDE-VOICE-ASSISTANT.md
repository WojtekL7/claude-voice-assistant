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

---

*Ostatnia aktualizacja: 2026-06-16 (popołudnie) — **LINUX APPIMAGE 1.0.16: start Claude + czytelna czcionka, odzysk po awarii** (commit `d65857f`). Komputer zawiesił się w poprzedniej sesji (dziennik `be2b7aff`, urwany 13:16) — praca NIE przepadła: niezacommitowane zmiany przetrwały na dysku, przebieg odtworzony z `~/.claude/projects/<cwd>/*.jsonl`, kod nieuszkodzony. Dwie naprawy WebTerminala (xterm.js w AppImage): (1) **bufor wejścia do PTY** — `claude` przychodził ZANIM powłoka wstała (start po `frontend_ready`, ~2 s w AppImage) i `_write_pty` gubił go po cichu → Claude nie startował; fix = `_pending_input` w `__init__`, buforowanie gdy `_proc is None`, opróżnianie w `_spawn()`. (2) **czcionka pt-vs-px** — wspólny `set_font` przekazuje PUNKTY (QTermWidget=`QFont 13pt`~17px), a xterm.js liczył je jako PIKSELE (13px, ~30% mniej, nieczytelne); fix = `_push_font` przelicza `px=round(size*96/72)` → 13pt=17px + `fontSize:17` startowo w `terminal.html`. Oba potwierdzone na realnym ekranie. Plus przebudowa `packaging/linux/build.sh` (WebTerminal w paczce, CVA_SKIP_DEPS, logi etapów). Reguła: konwersja pt→px tylko na styku WebTerminala (jedyny backend w px). Nauki uniwersalne (odzysk z dziennika `.jsonl`; jednostki czcionki terminala) → kandydaci do CLAUDE-COMMON. Szczegóły w sekcji „🐧🛠️ SESJA 2026-06-16 (popołudnie)".*

*Ostatnia aktualizacja: 2026-06-16 — **SELF-UPDATE WINDOWS POTWIERDZONY E2E (1.0.16)**: użytkownik potwierdził, że Windows sam zaktualizował się do najnowszej wersji na realnej maszynie — cały przebieg pomyślny. Pierwszy potwierdzony end-to-end self-update na Windows + pierwszy realny test odpornego downloadera z 1.0.14 (TLS 1.2 + Range + retry) → przeszedł bez `SSL BAD_RECORD_MAC`. Zamyka wątek pobierania aktualizacji Windows ciągnący się od 1.0.12. Stan: macOS (od 1.0.8) i Windows (od 1.0.14) self-update ✅; Linux = brak paczki (AppImage do dorobienia). Pozostaje: potwierdzić self-update Mac do 1.0.16, test „nodecli" na świeżym Windows, Linux AppImage. Szczegóły w sekcji „🪟✅ SESJA 2026-06-16".*

*Ostatnia aktualizacja: 2026-06-15 (koniec sesji) — **1.0.16 WYDANE** (mac+win; bump d1afe84, feed da39dd6; sha256 potrójnie zgodne lokalnie==serwer==feed; instalatory 1.0.15 jako .bak). PEŁNA ANGIELSKA WERSJA: i18n aplikacji (central `config.t` + parytet 3 słowników ~640 kluczy + `detect_system_language` DOMYŚLNIE EN, PL tylko gdy system polski; helpery model_label/install_guide_url; menu/zakładki odświeżane na żywo z USUWANIEM starych QAction by nie kumulować skrótów; dialogs.py zrobione 2 subagentami + niezależna weryfikacja) + strona WWW EN (osobne pliki `-en` + dropdown English-first, wdrożone na VPS) + aplikacja otwiera instrukcję wg języka (`install_guide_url`). BUG: `from ..config import` (relative beyond top-level) crashował okno skórki w OBU językach → absolutny `from config import`. `gh` zalogowany na stałe (keyring) po rotacji → przyszłe wydania automatyczne. Nauki uniwersalne (re-auth gh przez background device-flow, i18n-at-scale subagentami + bramki weryfikacji) → CLAUDE-COMMON. Architektura i18n → pamięć projektu `i18n-architektura.md`. Wcześniej: 2026-06-12 (koniec sesji) — dopisek FAQ: aktualizacje pełnopaczkowe → pominięcie kilku wersji = bezpieczny przeskok prosto do najnowszej (wyjątki: Mac ≤1.0.7 bootstrap, Win 1.0.12–1.0.13 kruchy downloader). Wcześniej tego dnia — **1.0.15 WYDANE** (bump 96c45b6, feed dad967b; sha potrójnie zgodne lokalnie==serwer==feed; instalatory 1.0.14 jako .bak). SESJA: (1) suwak nowych zakładek (commit b8a39af): nowa zakładka dostawała fabryczne [600,150] (~80/20, gruby panel) zamiast proporcji usera ~[1500,187]; fix = `DEFAULT_SPLITTER_SIZES=[1500,190]` w config.py (jedyne źródło prawdy, cienki panel dla świeżych instalacji) + `_inherit_splitter_sizes()` (dziedziczenie z AKTYWNEJ zakładki) wpięty w 3 drogi tworzenia (Dodaj agenta / manager→uruchom / „+"); dialogs.get_data NIE wpycha defaultu nowemu agentowi (inaczej dziedziczenie martwe); agents.json: Fable 5 + Strona F-P naprawione na [1503,187] (backup .bak-2026-06-12). (2) czarna strona po zamknięciu zakładki (commit c85e451): „+" to pusta atrapa-QWidget; po removeTab aktywnej Qt samo wybierało sąsiada (przy ostatniej przed „+" = atrapę → czarny widok; przy środkowej = przypadkowa lazy-activation/start claude); fix = historia MRU `_tab_mru` (aktualizacja w `_on_tab_changed`) + `_close_agent_tab` robi `setCurrentWidget(cel z MRU)` PRZED removeTab + `_most_recent_tab(exclude)` (pomija zamykaną i „+", fallback ostatnia prawdziwa). LEKCJA QT (decyzją usera w tym pliku, nie COMMON): przy usuwaniu aktywnej zakładki NAJPIERW setCurrentWidget, POTEM removeTab. NA NASTĘPNĄ SESJĘ: test self-update Mac/Win 1.0.14→1.0.15 (Windows = 1. realny test downloadera TLS 1.2+Range+retry; checklista z 2026-06-11 niepotwierdzona), test „nodecli" na świeżym Windows, instrukcja-linux przy AppImage.*

*Wcześniej: 2026-06-11 (koniec sesji) — **1.0.14 WYDANE** (bump 78161f8, feed 0ce41f3; sha potrójnie zgodne; weryfikacja publicznym URL OK). NA JUTRO: user sprawdza self-update Mac (oczekiwane OK) i PIERWSZY self-update Windows (stary downloader bez TLS 1.2 → możliwy SSL BAD_RECORD_MAC; obejście: przeglądarka, publiczny /cva/...Setup-1.0.14.exe; od 1.0.14 pobieranie odporne) + test „nodecli" na świeżym Windows. Wcześniej tego dnia — SESJA: (1) NAPRAWA FLAGI „?" (commit a3fd485): przyczyna = dziennik .jsonl dostaje tylko UKOŃCZONE wpisy (zmierzone 20,4 s ciszy pliku W TRAKCIE pisania odpowiedzi) → warunek „plik stoi 1,6 s = czeka" zapalał flagę przy każdej pracy agenta i nie gasła; fix = DRUGI warunek: cisza strumienia terminala ≥ 3 s (pracujący TUI animuje spinner+licznik ~1×/s → zmierzone max 0,96 s przerwy przy generowaniu, przy czekaniu cisza 8+ s; `_last_terminal_data_ts` w AgentTab._on_terminal_output + `QUESTION_TERMINAL_QUIET_SECS=3.0`; reader wołany ZAWSZE, nie za leniwym `and`); potwierdzone przez usera; KOREKTA uniwersalna → CLAUDE-COMMON „INTEGRACJA Z CLI/TUI" pkt 4 (stary wpis błędny). (2) Hardening updatera (f57fb58): TLS 1.2 + Range/wznawianie segmentami 8 MB + retry 3× + sha po całości + .part→rename po weryfikacji; przetestowane na żywym feedzie (102 MB + wznowienie od 60 MB) — wejdzie w 1.0.14. (3) Kreator ClaudeSetupDialog przy braku claude (start raz/sesję + menu Pomoc; claude_found → podmiana claude_command bez restartu); INSTALL_GUIDE_BASE_URL = publiczne /cva/. (4) Strony WWW wdrożone: instrukcja-{windows,macos,linux,agenci}.html na /cva (publiczne; Groq → console.groq.com/keys; agenci = każdy przycisk managera + 4 zakładki konfiguracji + FAQ; link w menu Pomoc „Instrukcja: Zarządzaj agentami…"); index.html: Linux „Wkrótce" (był 404!), wersja z appcast, linki 📖. (5) installer.iss zadanie „nodecli" (Node LTS z dist/index.json → MSI → npm claude-code; wykrywanie node/claude w Program Files I PATH przez `where`; nigdy przy /VERYSILENT; pułapki: .iss MUSI być UTF-8 Z BOM, `{tmp}` w komentarzu Pascala zamyka komentarz; CI zielony, e2e przy 1.0.14). Wydania NIE było — TODO 1.0.14 w sekcji sesji. Wcześniej (2026-06-10 noc) — DOPISEK do sesji 1.0.13: POTWIERDZONO terminal Windows DZIAŁA na realnej maszynie usera (10.0.19045; `cmd.exe` odpowiada, Enter działa) — bug pustego terminala zamknięty na żywo. KOREKTA: Windows 1.0.12 JEDNAK wykrył update 1.0.13 (self-update feed+detekcja działa na Win), padło tylko POBIERANIE: `SSL DECRYPTION_FAILED_OR_BAD_RECORD_MAC` konsekwentnie pod koniec ~100 MB (TLS 1.3 KeyUpdate w starym OpenSSL albo antywirus; serwer OK — curl+sha256 z zewnątrz przeszły); obejście = pobranie przez PRZEGLĄDARKĘ z publicznego `/cva/...Setup.exe` (zadziałało). Onboarding Claude Code na świeżym Windows: app NIE zawiera CLI → user musi Node.js LTS + `npm i -g @anthropic-ai/claude-code` + restart app + login OAuth; pułapka: Node installer „Tools for Native Modules" sypie błędami VS Build Tools (zignorować, zamknąć); login gdy przeglądarka się nie otwiera = „c to copy" URL (nie przepisywać 300+ znaków ręcznie — PKCE); literówka `cloude`≠`claude`. TODO 1.0.14: uodpornić `update_manager._download_worker` (TLS 1.2 + Range + retry 3×) — przy okazji 1. realny test self-update Windows. NOWE TODO (priorytet usera): napisać SZCZEGÓŁOWĄ instrukcję instalacji krok-po-kroku dla nie-programisty na Windows/macOS/Linux z doinstalowaniem programów dodatkowych (Node+claude+login) — strona „Pierwsze kroki"/docs/INSTALL.md; rozważyć kreator wykrywający brak Node/claude. Nauki uniwersalne (SSL BAD_RECORD_MAC przy dużym pobieraniu, onboarding pilota-nad-CLI) → CLAUDE-COMMON. Wcześniej (wieczór) — SESJA: WYDANIE 1.0.13 (mac+win). (1) TERMINAL WINDOWS NAPRAWIONY — diagnoza na runnerze `windows-latest` (workflow `diagnose-windows.yml`: build → uruchom z kodu I spakowaną → zrzut ekranu + logi → `gh run download`); „puste pole bez kursora" miało PIĘĆ przyczyn warstwa-pod-warstwą: (a) `pygame.mixer.init()` crash bez audio → try/except `audio_available`; (b) `print()` z „ą" na Windows crashował (stdout cp1252 UnicodeEncodeError, w handlerze błędu TTS) → `sys.stdout/err.reconfigure(errors="replace")` w main.py; (c) renderer Chromium ginął w spakowanej appce (`renderProcessTerminated status=2 0x80000003`, sandbox vs PyInstaller) → `QTWEBENGINE_DISABLE_SANDBOX=1`; (d) PyQtWebEngine-Qt5 5.15.2=Chromium 83, xterm.js 5.x wymaga `replaceChildren` (Chromium 86+) → polyfill w terminal.html przed xterm.js (na macOS Qt nowszy, działało); (e) pywinpty bez `winpty-agent.exe`/`OpenConsole.exe` → `collect_all('winpty')` w .spec. Plus 2 poboczne: `_update_status` guard na brak `status_bar`; jawny `self._ui_ready` w `_on_tab_changed` (terminal znikał przy starcie, bo wcześniejszy crash status_bar PRZYPADKIEM chronił przed za wczesną aktywacją). web_terminal: log `~/.claude-voice-assistant/webterminal.log` + obsługa loadFinished/renderProcessTerminated + watchdog 10 s → komunikat zamiast pustego pola; log Chromium tylko pod CVA_WEBENGINE_LOG=1 (--enable-logging otwiera czarne okna konsoli QtWebEngineProcess.exe). (2) FLAGA „?" — pomarańczowa ikona SVG na nieaktywnej zakładce gdy agent czeka; wykrywanie z DZIENNIKA (`transcript_reader.waiting_for_user()`: plik sesji STOI ~1,6 s = czeka, rośnie = pracuje), NIE ze strumienia terminala (zniekształcone kodowanie + AskUserQuestion zapisuje tool_use do dziennika DOPIERO po odpowiedzi → ostatni wpis zostaje `user`). GUI: `_arm_question`/`_refresh_question_flag`/`_refresh_all_question_flags`, sprawdzane co tick w `_poll_transcripts`. Bonus: przypięcie sesji w transcript_reader (`_preexisting` → bierze tylko plik powstały PO starcie zakładki) — ignoruje równoległą sesję Claude Code w tym samym katalogu (psuło flagę I auto-czytanie). Commity 6a511b3/f23b22a/e5e9630. TODO usera: Windows install 1.0.13 ręcznie raz (1.0.12 ma zepsuty terminal; self-update Windows test przy 1.0.14); macOS sam się zaktualizuje. Nauki uniwersalne (CI-jako-GUI-środowisko, QtWebEngine-na-Windows pułapki, wykrywanie „agent czeka" z transcript) → CLAUDE-COMMON. Wcześniej tego dnia — SESJA: dodano model Fable 5 do listy wyboru (commit `a6c59aa`). Nowa sekcja „🤖 PRZEPIS: JAK DODAĆ NOWY MODEL CLAUDE CODE DO APLIKACJI": aplikacja jest pilotem nad CLI (claude --model <klucz>), dodanie modelu = JEDEN plik src/config.py = 3 słowniki (CLAUDE_MODELS / CLAUDE_MODELS_SHORT / CLAUDE_MODEL_CONTEXT_LIMITS) jako jedyne źródło prawdy (dropdown/panel agentów/licznik tokenów zasilają się same); KROK 1 = weryfikuj alias na żywo `claude --model <alias> -p "OK"` (exit 0) zanim dopiszesz; dopisz TEN SAM klucz do wszystkich 3 słowników (inaczej licznik nie zna okna); NEW_AGENT_DEFAULT_MODEL zmieniaj świadomie. Fable 5: alias `fable` (zweryfikowany), okno 1M = jak Opus 4.8, max 128K, ~2× droższy ($10/$50 vs $5/$25) → szybciej zużywa limit; rozliczenie: do 22.06.2026 wliczony w subskrypcję bez dopłat (draws from plan usage), potem warunki mogą się zmienić. Domyślny = Opus (tańszy). Etykiety Opus 4.7→4.8. Dodano też wskazówkę „kiedy Fable vs Opus": programowanie na Fable działa identycznie (wybór modelu w konfiguracji agenta, Stop→Uruchom); Fable = duże refaktory / trudne bugi przez wiele warstw / długie zadania „odpal i zostaw" / głęboki research / trudne code review; Opus (domyślny) = bieżączka (drobne poprawki, pojedyncze pliki, szybkie pytania, taniej); praktyka = dwóch agentów w zakładkach (Opus bieżączka + Fable ciężkie). Wcześniej 2026-06-09 (wieczór) — SESJA: WERSJA WINDOWS 1.0.12 zbudowana/wdrożona/zainstalowana na realnym Windows, ale ⛔ TERMINAL NIE DZIAŁA (JUTRO ZACZYNAMY OD TEGO). Krok 1 jutro: odczytać komunikat w okienku terminala (brak pywinpty vs spawn padł). Hipoteza nr 1: PyInstaller nie dołącza natywnych binariów pywinpty (winpty-agent.exe/conpty.dll/OpenConsole.exe) → w ClaudeVoiceAssistant.spec dodać collect_all('winpty'); rebuild 1.0.13 + przy okazji 1. test self-update Windows. Zrobione W1–W5: W1 ConPTY pywinpty (_PTY_KIND wybiera winpty/ptyprocess; winpty read/write=str, terminate() bez force), W2 spec onedir+build-windows.ps1+make_ico.py, W3 build-windows.yml (windows-latest, choco innosetup), W4 installer.iss Inno per-user {localappdata} bez UAC, W5 _windows_self_replace Setup.exe /VERYSILENT (nietestowane e2e). Pułapki sesji: (a) .ps1 MUSI być ASCII — PS5.1 czyta bez BOM jako ANSI → polskie znaki/emoji rozbiły parser (ParserError/MissingTypename); (b) .spec w .gitignore → dodany wyjątek; (c) ZAPOMNIANY scp index.html (strona pokazywała stary „Wkrótce" mimo wgranego .exe). Feed: jedna globalna version → mac+win ujednolicone na 1.0.12. Runbook wydania Windows w sekcji wyżej. Nauki uniwersalne w CLAUDE-COMMON (pakowanie Windows + auto-update Windows). Wcześniej tego dnia — SESJA: ZAKŁADKI macOS DOKOŃCZONE w 1.0.11 (potwierdzone na realnym Macu — po lewej). 1.0.9 (CSS) i 1.0.10 (QProxyStyle na samym SH_TabBar_Alignment) NIE działały bo QMacStyle IGNORUJE ten hint; centrowanie liczy styl QTabWidget w subElementRect(SE_TabWidgetTabBar). Fix 1.0.11 (commit d1404b6): _LeftAlignedTabStyle = QProxyStyle oparty o silnik Fusion (QStyleFactory.create) + override subElementRect dosuwający pasek w lewo + styleHint→AlignLeft, podpięty do tab_widget.setStyle(...) ORAZ tabBar().setStyle(...) (referencja self._tab_style; setStyle nie propaguje na dzieci → reszta okna macowa). Sekcja „Zakładki na macOS" przepisana na ✅ ROZWIĄZANE. Self-update potwierdzony też 1.0.10→1.0.11 (mechanizm stabilny przez 3 wydania pod rząd). KOREKTA pamięci uniwersalnej CLAUDE-COMMON „PUŁAPKI QT/PYQT5" pkt 5 (był błędny). Wcześniej 2026-06-08 — SESJA: pierwszy udany SELF-UPDATE na żywym Macu (1.0.8→1.0.9, sam pobrał/podmienił/zrestartował, bez instalatora — cały mechanizm auto-aktualizacji potwierdzony end-to-end) + runbook wydania 1.0.9 (bump APP_VERSION → tag v1.0.9 → Actions build .dmg/.zip → gh release download → wgraj .zip PRZED appcast.json (kolejność!) → .dmg pod stałą nazwą downloads/ClaudeVoiceAssistant-macos.dmg + .bak → make-appcast-entry --merge → weryfikacja publicznym URL version/HTTP200/content-length==size). ZAKŁADKI macOS — wtedy niedokończone; DOKOŃCZONE 2026-06-09 w 1.0.11 (Fusion + subElementRect, patrz wpis na górze stopki). Wcześniej 2026-06-03 — AUTO-AKTUALIZACJA (commit `d9f4ed2`) + suwak xterm.js (`28e0137`): nowa sekcja 🔄 AUTO-AKTUALIZACJA — Etap 1 (sprawdzanie przy starcie I zamknięciu: closeEvent async-check + bezpiecznik 4 s + flagi `_close_check_in_progress`/`_force_close`/`_update_checked_on_close` + `_finish_close`), Etap 2 (macOS samo-podmiana: `apply_update_async`/`can_self_replace`/`_macos_self_replace` przez `ditto -x -k` + pomocnik bash czeka na PID→swap→relaunch; `platform_utils.is_frozen()`/`macos_app_bundle()`; dialog `relaunch_ready`/`installer_opened`/`apply_failed`), build `.zip` (ditto -c -k --keepParent) obok `.dmg`, feed PUBLICZNY `pobierz…/cva/appcast.json` (router traefik cva-pub bez basicauth, priority=100; /opt/cva-web/html/cva/). Feed=1.0.7; auto-update aktywny od 1.0.8. Suwak xterm.js (Mac/WebTerminal) 1:1 jak QTermWidget (`::-webkit-scrollbar` w terminal.html: gradient #888→#aaa→#888, 12px, rogi 5px). Wcześniej 2026-06-02 — sesja licznik/ikony/UI, wydania 1.0.5→1.0.7: nowa sekcja 🛠️ SESJA 2026-06-02 — (a) fix licznika tokenów: `QTermWidgetBackend._on_received` gubił całe wyjście terminala bo `receivedData` niesie str a kod robił `bytes(data)` (TypeError połykany) — od M2.3; + `_connect_agent_tab_signals` (jedno źródło sygnałów, „+" gubiło terminal_output); + `self.terminal_backend`=None przy starcie primary taba index 0 → fix w `_on_terminal_ready` (objaw: 🔊/⧉ nie działają do 1. zmiany zakładki). (b) kolorowe ikony SVG `src/assets/icons/*.svg` + `gui/icon_set.py` (setIcon zamiast emoji; emoji na Linuksie monochromatyczne). (c) pasek postępu zużycia kontekstu + stałe szerokości liczników (anty-skakanie). (d) „Zarządzaj agentami": tło wiersza = auto-start (zielone/szare) zamiast 🟢/⚪. (e) okna plików: neutralna ciemna paleta `DIALOG_COLORS` (natywne GNOME niedostępne dla Qt). (f) Groq tylko STT (TTS=edge-tts bez klucza); klik 🎤 bez klucza → komunikat + dialog (fix AttributeError `_show_api_key_dialog`→`_show_groq_api_dialog`). Nauki uniwersalne (emoji-monochromat, natywne QFileDialog, anty-skakanie, diagnoza sygnałów Qt) w CLAUDE-COMMON.md. Wcześniej 2026-06-01 (wieczór) — DYSTRYBUCJA macOS DZIAŁA NA REALNYM MACU: nowa sekcja 🍎 DYSTRYBUCJA / WYDANIA macOS — GitHub Actions buduje `.dmg` (macos-14 arm64, tag v* → Release), launchery dwuklik (Uruchom-Mac.command / Zbuduj-DMG-Mac.command), strona pobierania z hasłem `https://pobierz.srv1251441.hstgr.cloud` (kontener cva-web w /opt/cva-web za traefik+basicauth), automat gh release download + scp podmienia plik. Wydania 1.0.0→1.0.4: 1.0.1 login shell (claude↔node), 1.0.2 menu w oknie (natywny pasek znikał), 1.0.3 font Ubuntu dołączony (cienki na Macu), 1.0.4 pauza TTS (brakowało sygnału request_pause). requirements: usunięto asyncio, pyenchant opcjonalny. TODO: klucz Groq, podpis Apple, Intel+Linux w automacie, ochrona/licencja/własna nazwa. Wcześniej 2026-06-01 — PORT macOS UKOŃCZONY (strona kodu): M2.2 (terminal_backend.py — wspólny interfejs + fabryka), M2.3 (wpięcie do AgentTab/MainWindow; Linux=QTermWidget, Mac/Win/CVA_WEBTERMINAL=1=WebTerminal; gotcha AA_ShareOpenGLContexts w main.py), M2.4 (pełny motyw xterm ze skórki + czcionka + scrollback 10000), M3 (update_manager.py + UpdateAvailableDialog + menu Pomoc + ciche sprawdzanie przy starcie; sha256 obowiązkowe, Ed25519 wyłączone; instalacja=otwórz instalator; HTTP przez requests NIE httpx), M4 (packaging/macos: spec PyInstallera + Info.plist z mikrofonem + entitlements + build-macos.sh + make-appcast-entry.py; config.BASE_DIR świadomy sys._MEIPASS frozen-only). Sekcja PORT przepisana na ✅ UKOŃCZONE + architektura terminala + CO ZOSTAŁO (build na Macu, feed VPS, Windows ConPTY). Poprawka ZALEŻNOŚCI: httpx→requests. Commity: ade4a25, 716946e, f9c030d, 0338b07, 61d5774. Wcześniej 2026-05-30 — dodano sekcję 🚧 PORT macOS — STATUS I PLAN [wznowienie 2026-05-31]: cel (Mac Apple Silicon, architektura pod Windows, auto-aktualizacja z VPS, podpis odłożony z gotowym gniazdem); zablokowane decyzje; ZROBIONE M1 (platform_utils, packaging, APP_VERSION) + M2.1 (WebTerminal xterm.js+QtWebEngine+PTY, działa); NASTĘPNY KROK = M2.2 (wspólny interfejs + fabryka backendów), dalej M2.3 wpięcie do AgentTab (Linux=QTermWidget domyślnie, Mac/Win=WebTerminal; gotcha AA_ShareOpenGLContexts), M2.4, M3 updater, M4 pakowanie. Wcześniej 2026-05-30 — nowa sekcja ARCHITEKTURA AUTO-CZYTANIA (Droga A): auto-czytanie czyta czystą prozę z dziennika `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.* `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.*
