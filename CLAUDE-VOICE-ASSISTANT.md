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

## 🎉 SESJA 2026-06-08 — pierwszy udany SELF-UPDATE na żywym Macu (1.0.8→1.0.9) + zakładki macOS (W TOKU)

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

### ⚠️ Zakładki na macOS wyśrodkowane — NIEDOKOŃCZONE (do zrobienia jutro)
Poprawka CSS `QTabWidget::tab-bar { alignment: left }` (commit `6f33996`, wydana w 1.0.9)
**NIE działa na macOS** — zakładki dalej na środku (**potwierdzone na realnym Macu 2026-06-08**).
macOS (`QMacStyle`) centruje pasek zakładek przez style-hint `SH_TabBar_Alignment`, którego
arkusz stylów Qt nie przebija (kolory/kształt z QSS działają, więc wygląda jakby CSS „brał",
a alignment i tak ignoruje). **Następny krok (plan gotowy, kod NIE wdrożony):** `QProxyStyle`
nadpisujący `styleHint(SH_TabBar_Alignment) → Qt.AlignLeft`, podpięty
`self.tab_widget.tabBar().setStyle(self._tab_style)` (referencję trzymać na `self._tab_style`,
inaczej GC ją zje); importy `QProxyStyle, QStyle` z `PyQt5.QtWidgets`. Na Linuksie i tak lewo
→ zero regresji. Uniwersalna wersja → CLAUDE-COMMON „PUŁAPKI QT / PYQT5" pkt 5. Test: wydać
1.0.10 (przy okazji kolejny test self-update) albo lokalnie `Uruchom-Mac.command` na Macu.

---

*Ostatnia aktualizacja: 2026-06-08 — SESJA: pierwszy udany SELF-UPDATE na żywym Macu (1.0.8→1.0.9, sam pobrał/podmienił/zrestartował, bez instalatora — cały mechanizm auto-aktualizacji potwierdzony end-to-end) + runbook wydania 1.0.9 (bump APP_VERSION → tag v1.0.9 → Actions build .dmg/.zip → gh release download → wgraj .zip PRZED appcast.json (kolejność!) → .dmg pod stałą nazwą downloads/ClaudeVoiceAssistant-macos.dmg + .bak → make-appcast-entry --merge → weryfikacja publicznym URL version/HTTP200/content-length==size). ZAKŁADKI macOS NIEDOKOŃCZONE (jutro): CSS `QTabWidget::tab-bar{alignment:left}` (commit 6f33996, w 1.0.9) NIE przebija centrowania QMacStyle (potwierdzone na Macu) — następny krok QProxyStyle nadpisujący styleHint SH_TabBar_Alignment→Qt.AlignLeft na tab_widget.tabBar() (trzymać referencję self._tab_style; importy QProxyStyle/QStyle z QtWidgets), kod nie wdrożony. Wcześniej 2026-06-03 — AUTO-AKTUALIZACJA (commit `d9f4ed2`) + suwak xterm.js (`28e0137`): nowa sekcja 🔄 AUTO-AKTUALIZACJA — Etap 1 (sprawdzanie przy starcie I zamknięciu: closeEvent async-check + bezpiecznik 4 s + flagi `_close_check_in_progress`/`_force_close`/`_update_checked_on_close` + `_finish_close`), Etap 2 (macOS samo-podmiana: `apply_update_async`/`can_self_replace`/`_macos_self_replace` przez `ditto -x -k` + pomocnik bash czeka na PID→swap→relaunch; `platform_utils.is_frozen()`/`macos_app_bundle()`; dialog `relaunch_ready`/`installer_opened`/`apply_failed`), build `.zip` (ditto -c -k --keepParent) obok `.dmg`, feed PUBLICZNY `pobierz…/cva/appcast.json` (router traefik cva-pub bez basicauth, priority=100; /opt/cva-web/html/cva/). Feed=1.0.7; auto-update aktywny od 1.0.8. Suwak xterm.js (Mac/WebTerminal) 1:1 jak QTermWidget (`::-webkit-scrollbar` w terminal.html: gradient #888→#aaa→#888, 12px, rogi 5px). Wcześniej 2026-06-02 — sesja licznik/ikony/UI, wydania 1.0.5→1.0.7: nowa sekcja 🛠️ SESJA 2026-06-02 — (a) fix licznika tokenów: `QTermWidgetBackend._on_received` gubił całe wyjście terminala bo `receivedData` niesie str a kod robił `bytes(data)` (TypeError połykany) — od M2.3; + `_connect_agent_tab_signals` (jedno źródło sygnałów, „+" gubiło terminal_output); + `self.terminal_backend`=None przy starcie primary taba index 0 → fix w `_on_terminal_ready` (objaw: 🔊/⧉ nie działają do 1. zmiany zakładki). (b) kolorowe ikony SVG `src/assets/icons/*.svg` + `gui/icon_set.py` (setIcon zamiast emoji; emoji na Linuksie monochromatyczne). (c) pasek postępu zużycia kontekstu + stałe szerokości liczników (anty-skakanie). (d) „Zarządzaj agentami": tło wiersza = auto-start (zielone/szare) zamiast 🟢/⚪. (e) okna plików: neutralna ciemna paleta `DIALOG_COLORS` (natywne GNOME niedostępne dla Qt). (f) Groq tylko STT (TTS=edge-tts bez klucza); klik 🎤 bez klucza → komunikat + dialog (fix AttributeError `_show_api_key_dialog`→`_show_groq_api_dialog`). Nauki uniwersalne (emoji-monochromat, natywne QFileDialog, anty-skakanie, diagnoza sygnałów Qt) w CLAUDE-COMMON.md. Wcześniej 2026-06-01 (wieczór) — DYSTRYBUCJA macOS DZIAŁA NA REALNYM MACU: nowa sekcja 🍎 DYSTRYBUCJA / WYDANIA macOS — GitHub Actions buduje `.dmg` (macos-14 arm64, tag v* → Release), launchery dwuklik (Uruchom-Mac.command / Zbuduj-DMG-Mac.command), strona pobierania z hasłem `https://pobierz.srv1251441.hstgr.cloud` (kontener cva-web w /opt/cva-web za traefik+basicauth), automat gh release download + scp podmienia plik. Wydania 1.0.0→1.0.4: 1.0.1 login shell (claude↔node), 1.0.2 menu w oknie (natywny pasek znikał), 1.0.3 font Ubuntu dołączony (cienki na Macu), 1.0.4 pauza TTS (brakowało sygnału request_pause). requirements: usunięto asyncio, pyenchant opcjonalny. TODO: klucz Groq, podpis Apple, Intel+Linux w automacie, ochrona/licencja/własna nazwa. Wcześniej 2026-06-01 — PORT macOS UKOŃCZONY (strona kodu): M2.2 (terminal_backend.py — wspólny interfejs + fabryka), M2.3 (wpięcie do AgentTab/MainWindow; Linux=QTermWidget, Mac/Win/CVA_WEBTERMINAL=1=WebTerminal; gotcha AA_ShareOpenGLContexts w main.py), M2.4 (pełny motyw xterm ze skórki + czcionka + scrollback 10000), M3 (update_manager.py + UpdateAvailableDialog + menu Pomoc + ciche sprawdzanie przy starcie; sha256 obowiązkowe, Ed25519 wyłączone; instalacja=otwórz instalator; HTTP przez requests NIE httpx), M4 (packaging/macos: spec PyInstallera + Info.plist z mikrofonem + entitlements + build-macos.sh + make-appcast-entry.py; config.BASE_DIR świadomy sys._MEIPASS frozen-only). Sekcja PORT przepisana na ✅ UKOŃCZONE + architektura terminala + CO ZOSTAŁO (build na Macu, feed VPS, Windows ConPTY). Poprawka ZALEŻNOŚCI: httpx→requests. Commity: ade4a25, 716946e, f9c030d, 0338b07, 61d5774. Wcześniej 2026-05-30 — dodano sekcję 🚧 PORT macOS — STATUS I PLAN [wznowienie 2026-05-31]: cel (Mac Apple Silicon, architektura pod Windows, auto-aktualizacja z VPS, podpis odłożony z gotowym gniazdem); zablokowane decyzje; ZROBIONE M1 (platform_utils, packaging, APP_VERSION) + M2.1 (WebTerminal xterm.js+QtWebEngine+PTY, działa); NASTĘPNY KROK = M2.2 (wspólny interfejs + fabryka backendów), dalej M2.3 wpięcie do AgentTab (Linux=QTermWidget domyślnie, Mac/Win=WebTerminal; gotcha AA_ShareOpenGLContexts), M2.4, M3 updater, M4 pakowanie. Wcześniej 2026-05-30 — nowa sekcja ARCHITEKTURA AUTO-CZYTANIA (Droga A): auto-czytanie czyta czystą prozę z dziennika `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.* `~/.claude/projects/<cwd>/*.jsonl` (transcript_reader.py + prose_from_markdown + kolejka TTS z prefetch + _poll_transcripts), a NIE ze śmieciowego strumienia terminala (źródło „A ×N" = spinner literka po literce, oraz czytania ghost-text). Tylko aktywna zakładka czyta; nieaktywne zbierają zaległości + komunikat. Wcześniej 2026-05-09 — dodano reference do `docs/PRD.md` (Roadmap komercjalizacji 2026 v2.2) jako MUST READ przed pracą.*
