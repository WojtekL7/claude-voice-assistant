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

## Konfiguracja użytkownika — `~/.claude-voice-assistant/`
`config.json` (język, głos, skin, `groq_api_key`, `auto_check_updates`) · `agents.json` (agenci + `splitter_sizes` per zakładka) · `memory_projects.json` · `quick_actions.json` · `tts.log` (błędy TTS).

## Zależności (uwagi)
- Klient HTTP = **`requests`**, NIE httpx (stt/license/update).
- **Groq = tylko STT** (Whisper, wymaga `GROQ_API_KEY`). **TTS = edge-tts, działa BEZ klucza.**
- `pyenchant` opcjonalny (`ENCHANT_AVAILABLE`); `asyncio` usunięte z requirements (stdlib).
- `pygame.mixer.init()` owinięte try/except (brak audio = TTS off, reszta działa).

---

## AKTUALNY STAN (wersja 1.0.16)
- **Wieloplatformowość:** Linux (z kodu + AppImage), macOS (.dmg/.zip), Windows (.exe Inno). Pełna wersja PL/EN (domyślnie EN; PL gdy system polski).
- **Self-update:** macOS ✅ (od 1.0.8) · Windows ✅ (od 1.0.14, potwierdzony e2e na 1.0.16) · **Linux ⏳ (do dorobienia — patrz „NASTĘPNE ZADANIE")**.
- **Strona pobierania:** `https://pobierz.srv1251441.hstgr.cloud` (basicauth) + publiczny feed `…/cva/appcast.json` (bez auth). Kontener `cva-web` (nginx) na VPS w `/opt/cva-web/`.

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

- **WebTerminal — bufor wejścia do PTY.** Powłoka startuje dopiero po `frontend_ready` (~2 s w AppImage); `claude`/wiadomość wysłane wcześniej `_write_pty` gubił po cichu. Fix: `_pending_input` w `__init__`, buforuj gdy `_proc is None`, opróżnij w `_spawn()`.
- **WebTerminal — czcionka pt vs px.** `set_font(size)` przekazuje PUNKTY; QTermWidget=`QFont(pt)`, xterm.js liczy w PIKSELACH. Konwersja `px=round(size*96/72)` TYLKO na styku `web_terminal._push_font` + `fontSize` startowy w `terminal.html`.
- **Flaga „?" (agent czeka).** Wykrywanie z dziennika+terminala, NIE z treści. Warunek = DWIE cisze: `transcript_reader.waiting_for_user()` (dziennik stoi) **I** `monotonic()-_last_terminal_data_ts >= QUESTION_TERMINAL_QUIET_SECS (3.0)` (TUI animuje pasek ~1×/s → cisza terminala = czeka). Sama cisza dziennika NIE wystarcza (dostaje tylko ukończone wpisy → stoi 20+ s podczas pisania).
- **transcript_reader — przypięcie sesji.** `set_working_directory` zapamiętuje `_preexisting`; bierze tylko plik `.jsonl` powstały PO starcie zakładki → ignoruje równoległą sesję Claude Code w tym samym katalogu (psuło auto-czytanie I flagę).
- **Lazy activation zakładek.** `self._ui_ready` (False przez `__init__`) w `_on_tab_changed`; primary tab aktywowany odroczonym `QTimer` (bo `setCurrentIndex(0)` nie emituje `currentChanged`). Guard idempotencji w 3 ogniwach (create / `_on_terminal_ready` / final-action).
- **Sygnały zakładki = jedno źródło.** `MainWindow._connect_agent_tab_signals(tab)` — oba tory tworzenia (Dodaj agenta / „+") muszą wołać tę metodę (inaczej „+" gubi `terminal_output` → licznik tokenów milczy).
- **`QTermWidgetBackend._on_received`.** `receivedData` niesie `str`, nie QByteArray — obsłuż `isinstance(str)` / `hasattr('data')` / `bytes()` (inaczej `bytes(str)` TypeError połykany → całe wyjście gubione).
- **Zamykanie zakładki.** Najpierw `setCurrentWidget(cel z MRU `_tab_mru`)`, POTEM `removeTab` — „+" to atrapa-QWidget; inaczej Qt aktywuje ją (czarny ekran) lub przypadkowo sąsiada (start claude).
- **Splitter nowej zakładki.** `config.DEFAULT_SPLITTER_SIZES=[1500,190]` (jedyne źródło) + `_inherit_splitter_sizes()` (dziedziczenie z aktywnej); `dialogs.get_data` NIE wpycha defaultu nowemu agentowi.
- **Zakładki macOS do lewej.** `_LeftAlignedTabStyle` = QProxyStyle na silniku Fusion + override `subElementRect(SE_TabWidgetTabBar)` (QMacStyle IGNORUJE `SH_TabBar_Alignment`); podpięty do `tab_widget.setStyle` ORAZ `tabBar().setStyle`. → CLAUDE-COMMON „PUŁAPKI QT" pkt 5.
- **Pauza TTS.** Sygnał `request_pause` → `_toggle_pause` → `tts.toggle_pause()`; przycisk ⏸ tylko podczas `PLAYING`.
- **i18n.** Centralny `config.t(key)` (import `from config import t as tr` — ABSOLUTNIE, nie `from ..config`); parytet 3 słowników `pl-PL`/`en-US`/`en-GB` w `UI_TRANSLATIONS`; przy zmianie języka USUWAJ stare QAction przed odbudową menu (inaczej „ambiguous shortcut"). → pamięć projektu `i18n-architektura.md`.
- **TTS limit czasu.** `tts_engine._async_generate` ma `asyncio.wait_for(save, TTS_GEN_TIMEOUT=12)`, `_generate_audio` ponawia `TTS_GEN_ATTEMPTS=2`, błędy → `tts.log`; po nieudanych próbach pomija zdanie (lektor nie wisi). Bez tego zatkany edge-tts wieszał czytanie.
- **Windows spakowany (QtWebEngine).** `QTWEBENGINE_DISABLE_SANDBOX=1`; polyfill `replaceChildren` w `terminal.html` przed xterm.js (Chromium 83 z PyQtWebEngine-Qt5 5.15.2); `collect_all('winpty')` w `.spec`; `sys.stdout/err.reconfigure(errors="replace")` w `main.py`. → CLAUDE-COMMON „PAKOWANIE" pkt 10/12.

---

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

## DYSTRYBUCJA / WYDANIA — runbook (sprawdzony 1.0.13→1.0.16)
1. Bump `APP_VERSION` w `src/config.py` → commit/push.
2. `git tag vX.Y.Z && git push origin vX.Y.Z` → GitHub Actions buduje **mac+win naraz** (`build-macos.yml` runner `macos-14`, `build-windows.yml` `windows-latest`) i publikuje Release. (Iteracja bez wydania: `gh workflow run build-*.yml --ref main`.)
3. `gh release download vX.Y.Z -p '*.zip' -p '*.dmg' -p '*Setup.exe'` (do `dist-release/`, jest w .gitignore).
4. **Wgraj paczki PRZED appcastem** (inaczej okno błędu 404): `.zip`(mac)+`Setup.exe`(win) → `/opt/cva-web/html/cva/`; potem `appcast.json`.
5. `.dmg`/`Setup.exe` → `/opt/cva-web/html/downloads/` pod **stałą nazwą** (`ClaudeVoiceAssistant-macos.dmg`, `ClaudeVoiceAssistant-Setup.exe`; starą jako `.bak`).
6. Wpis do feedu: `python3 packaging/make-appcast-entry.py PACZKA --version X --platform <macos-arm64|windows-x64|linux-x64> --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ --appcast packaging/appcast.json --merge` → `scp appcast.json`.
7. **Weryfikacja publicznym URL:** `curl …/cva/appcast.json` (version + wpis dla platformy!) + `curl -I …PACZKA` (HTTP 200, `content-length`==`size`, sha256 serwer==feed).

Uwagi: appcast ma **jedną** globalną `version` dla wszystkich platform (musi mieć wpis dla `update_platform_id()` bieżącej platformy, inaczej cicho „no_update"). `gh` zalogowany w keyring (po rotacji PAT). Aktualizacje pełnopaczkowe → przeskok wielu wersji bezpieczny (wyjątki: Mac ≤1.0.7 bootstrap, Win 1.0.12–1.0.13 kruchy downloader). Onboarding na świeżej maszynie: user musi doinstalować Node.js + `npm i -g @anthropic-ai/claude-code` + login (kreator `ClaudeSetupDialog` prowadzi).

---

## NASTĘPNE ZADANIE: 🐧 LINUX SELF-UPDATE
Dziś nie działa z 2 powodów: (a) feed nie ma wpisu `linux-x64` → `_parse_appcast`=None → cicho `no_update`; (b) `update_manager.can_self_replace()` nie obejmuje Linuksa → `open_installer` (bez sensu dla AppImage). AppImage 1.0.16 jest tylko lokalnie w `dist/`.

**A — kod (`platform_utils.py` + `update_manager.py`):**
1. `platform_utils.appimage_path()` → `Path(os.environ["APPIMAGE"])` jeśli ustawione, inaczej `None` (`$APPIMAGE` = plik .AppImage na dysku, NIE mount `/tmp/.mount_*`).
2. `can_self_replace`: gałąź `if is_linux() and p.endswith(".appimage") and appimage_path() is not None: return True`.
3. `_apply_worker`: `elif is_linux(): self._linux_self_replace(path)`.
4. `_linux_self_replace(new)` wzorem `_macos_self_replace`: skrypt bash czeka aż PID zniknie → `cp new → $APPIMAGE` → `chmod +x` → `exec "$APPIMAGE"` → `relaunch_ready` (xattr NIE dotyczy Linuksa).

**B — feed/dystrybucja:** `CVA_SKIP_DEPS=1 bash packaging/linux/build.sh` → AppImage; `scp` do `/opt/cva-web/html/cva/` **PRZED** appcastem; `make-appcast-entry.py …AppImage --version X --base-url …/cva/ --appcast … --merge` (`guess_platform`→`linux-x64`) → `scp appcast.json`; weryfikacja publicznym URL.

**C — strona + bootstrap:** aktywować przycisk Linux w `packaging/web/index.html`(+`-en`) (dziś „Wkrótce"), dograć `instrukcja-linux.html`; pierwszą paczkę z mechanizmem user instaluje raz ręcznie, od niej w górę aktualizuje się sam.

**Pułapki:** `$APPIMAGE` tylko gdy uruchomione jako AppImage; `chmod +x` obowiązkowy; feed MUSI mieć `linux-x64`; paczka na serwer PRZED appcastem. Test e2e wymaga realnego AppImage na ekranie usera.

## Inne otwarte TODO
- [ ] Potwierdzić self-update **Mac** do 1.0.16 (wersja angielska).
- [ ] Test zadania „nodecli" instalatora na świeżym Windows (auto-instalacja Node+Claude Code).
- [ ] Kolejne języki: dopisać słownik w `UI_TRANSLATIONS` (parytet!) + `SUPPORTED_LANGUAGES` + `detect_system_language` + pliki `-xx.html` + dropdown.

## Sygnały PyQt (AgentTab)
`message_sent(str)` · `terminal_output(object)` · `status_changed(str)` · `request_tts(str)` · `request_dictation(bool)` · `request_pause` · `splitter_changed(list)`.

## Częste problemy
| Problem | Rozwiązanie |
|---------|-------------|
| QTermWidget not found | `pip install wheels/qtermwidget-*.whl` |
| TTS nie działa | internet (edge-tts); sprawdź `~/.claude-voice-assistant/tts.log` |
| STT nie nagrywa | `GROQ_API_KEY`, mikrofon |
| `claude` not recognized | doinstalować Node + `npm i -g @anthropic-ai/claude-code` + restart |
| Apka nie startuje | `python3 -m py_compile src/main.py` |
| Zawieszanie przy 2+ zakładkach | RAM — patrz „Pamięć/RAM" wyżej |
