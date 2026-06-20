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
`config.json` (język, głos, skin, `groq_api_key`, `auto_check_updates`) · `agents.json` (agenci + `splitter_sizes` per zakładka) · `memory_projects.json` · `quick_actions.json` · `tts.log` (błędy TTS) · `crash-logs/` (zrzuty „czarnej skrzynki" po crashu `claude` — patrz pułapka niżej).

## Zależności (uwagi)
- Klient HTTP = **`requests`**, NIE httpx (stt/license/update).
- **Groq = tylko STT** (Whisper, wymaga `GROQ_API_KEY`). **TTS = edge-tts, działa BEZ klucza.**
- `pyenchant` opcjonalny (`ENCHANT_AVAILABLE`); `asyncio` usunięte z requirements (stdlib).
- `pygame.mixer.init()` owinięte try/except (brak audio = TTS off, reszta działa).

---

## AKTUALNY STAN (wersja 1.0.19)
- **Wieloplatformowość:** Linux (z kodu + AppImage), macOS (.dmg/.zip), Windows (.exe Inno). Pełna wersja PL/EN (domyślnie EN; PL gdy system polski).
- **Self-update:** macOS ✅ (od 1.0.8) · Windows ✅ (od 1.0.14) · **Linux ✅** (kod od 1.0.16, w feedzie od 1.0.17). **Pipeline WYDANIA potwierdzony e2e 2× (1.0.18, 1.0.19)** — tag→Actions(mac/win)+lokalny AppImage→rsync paczek (sha256!)→appcast→downloads. **Kliencki cykl spakowanego AppImage** (uruchom→feed→pobierz→podmień→wstań) wciąż DO POTWIERDZENIA przy najbliższym uruchomieniu zainstalowanej apki (testy poprawek dotąd robione z kodu, nie przez auto-update).
- **Języki:** PL + jeden angielski (`en-US`); wariant brytyjski `en-GB` usunięty w 1.0.17 (scalony do en-US, migracja wsteczna w `set_ui_language`).
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
- **WebTerminal (QtWebEngine) — drag&drop pliku: ścieżki NIE ma w JS.** Chromium ukrywa ścieżkę upuszczonego pliku → JS w `terminal.html` jej nie dostanie (sam `preventDefault` na `dragover`/`drop` likwiduje tylko pułapkę „otwarcia pliku na całe okno", bez wklejenia). Ścieżkę bierz PO STRONIE Qt: `eventFilter` na `view.focusProxy()` (to ON dostaje `QDropEvent`), `mimeData().urls()`→`toLocalFile()`→`_write_pty`. **Reinstaluj filtr w `showEvent`** — Qt PODMIENIA focusProxy przy ukryciu/przenoszeniu między zakładkami/splitterami (stary filtr przepada). Pole input (QTextEdit) obsłuż osobno: `insertFromMimeData` z `hasUrls()` (inaczej wkleja surowy obrazek). Objaw zgłaszany przez usera: „upuściłem obrazek i apka się zacięła, nie dało się wyjść" (commit `a123504`).
- **Biały błysk pola input (QTextEdit) po Enter.** Samo `background-color` w stylesheet zostawia paletę `Base`=biała; przy `clear()`+zmianie wysokości (po wysłaniu) Qt na ~1 klatkę maluje biały Base ZANIM nałoży styl → migający biały prostokąt (intermittentnie, „tylko czasem" — zależnie od trafienia między klatkami). Fix: ustaw też `QPalette.Base/Text` (kolor skórki) na polu **i jego `viewport()`**, nie tylko w stylesheet (commit `fccd618`). Uniwersalna pułapka PyQt — gdyby powstał 2. projekt PyQt, kandydat do COMMON.
- **„Pobrana apka działa inaczej niż z kodu" (Linux) = inny backend terminala.** AppImage celowo wyklucza QTermWidget (`excludes=["QTermWidget"]` w `.spec`) i odpala z `CVA_WEBTERMINAL=1` → pobrana wersja = **WebTerminal (Chromium)**, beta z kodu = **QTermWidget**. Bug „tylko w pobranej apce" reprodukuj z kodu: `CVA_WEBTERMINAL=1 python3 src/main.py`.
- **Flaga „?" (agent czeka).** Wykrywanie z dziennika+terminala, NIE z treści. Warunek = DWIE cisze: `transcript_reader.waiting_for_user()` (dziennik stoi) **I** `monotonic()-_last_terminal_data_ts >= QUESTION_TERMINAL_QUIET_SECS (3.0)` (TUI animuje pasek ~1×/s → cisza terminala = czeka). Sama cisza dziennika NIE wystarcza (dostaje tylko ukończone wpisy → stoi 20+ s podczas pisania).
- **transcript_reader — przypięcie sesji.** `set_working_directory` zapamiętuje `_preexisting`; bierze tylko plik `.jsonl` powstały PO starcie zakładki → ignoruje równoległą sesję Claude Code w tym samym katalogu (psuło auto-czytanie I flagę).
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

## DYSTRYBUCJA / WYDANIA — runbook (sprawdzony 1.0.13→1.0.17; 1.0.17 = pierwsze pełne 3-platformowe z Linuksem)
1. Bump `APP_VERSION` w `src/config.py` → commit/push.
2. `git tag vX.Y.Z && git push origin vX.Y.Z` → GitHub Actions buduje **mac+win naraz** (`build-macos.yml` runner `macos-14`, `build-windows.yml` `windows-latest`) i publikuje Release. (Iteracja bez wydania: `gh workflow run build-*.yml --ref main`.)
3. `gh release download vX.Y.Z -p '*.zip' -p '*.dmg' -p '*Setup.exe'` (do `dist-release/`, jest w .gitignore).
4. **Wgraj paczki PRZED appcastem** (inaczej okno błędu 404): `.zip`(mac)+`Setup.exe`(win)+`.AppImage`(linux, build lokalny `CVA_SKIP_DEPS=1 bash packaging/linux/build.sh`) → `/opt/cva-web/html/cva/`; potem `appcast.json`. ⚠️ **Duże paczki (~200 MB AppImage) przez `scp` BYWAJĄ UCINANE (broken pipe) — wgrany plik krótszy, bez błędu widocznego od razu.** Używaj `rsync --partial --inplace -e ssh PLIK host:ścieżka` (wznawialny) i ZAWSZE sprawdź rozmiar/sha256 na serwerze PRZED uploadem appcastu (potwierdzone na 1.0.17: AppImage przyszedł 167/198 MB).
5. `.dmg`/`Setup.exe`/`.AppImage` → `/opt/cva-web/html/downloads/` pod **stałą nazwą** (`ClaudeVoiceAssistant-macos.dmg`, `ClaudeVoiceAssistant-Setup.exe`, `ClaudeVoiceAssistant-linux.AppImage`+`chmod +x`; starą jako `.bak`). Oszczędność łącza: exe/AppImage z cva/ skopiuj server-side (`cp`) zamiast wgrywać drugi raz.
6. Wpis do feedu: `python3 packaging/make-appcast-entry.py PACZKA --version X --platform <macos-arm64|windows-x64|linux-x64> --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ --appcast packaging/appcast.json --merge` → `scp appcast.json`.
7. **Weryfikacja publicznym URL:** `curl …/cva/appcast.json` (version + wpis dla platformy!) + `curl -I …PACZKA` (HTTP 200, `content-length`==`size`, sha256 serwer==feed).

Uwagi: appcast ma **jedną** globalną `version` dla wszystkich platform (musi mieć wpis dla `update_platform_id()` bieżącej platformy, inaczej cicho „no_update"). `gh` zalogowany w keyring (po rotacji PAT). Aktualizacje pełnopaczkowe → przeskok wielu wersji bezpieczny (wyjątki: Mac ≤1.0.7 bootstrap, Win 1.0.12–1.0.13 kruchy downloader). Onboarding na świeżej maszynie: user musi doinstalować Node.js + `npm i -g @anthropic-ai/claude-code` + login (kreator `ClaudeSetupDialog` prowadzi).

---

## LINUX SELF-UPDATE (AppImage) — ZROBIONE (kod 1.0.16; commity `e91b76f` + `175b683`)
Działa jak na Macu, prościej (AppImage = JEDEN plik, nie katalog ze symlinkami → bez `ditto`, bez kwarantanny):
- `platform_utils.appimage_path()` → `$APPIMAGE` (plik .AppImage na dysku) lub `None`.
- `update_manager`: `can_self_replace` (Linux + `.appimage` + `appimage_path()`), `_apply_worker` → `_linux_self_replace()` = skrypt bash czeka aż PID zniknie → atomowa podmiana (`cp` do pliku tymcz. obok celu + `mv`) → `chmod +x` → restart `setsid` → `relaunch_ready`.
- Feed `linux-x64` w appcaście (publiczny `cva/`), strona PL+EN przycisk aktywny (`downloads/ClaudeVoiceAssistant-linux.AppImage`, stała nazwa), instrukcje `instrukcja-linux.html(-en)`.

**Trwałe pułapki:** podmieniaj **`$APPIMAGE`**, NIE `sys.executable`/`/tmp/.mount_*` (mount znika po zamknięciu); `chmod +x` obowiązkowy; feed MUSI mieć wpis `linux-x64` (inaczej cicho „no_update"); paczka na serwer **PRZED** appcastem; `$APPIMAGE` istnieje tylko gdy uruchomione jako AppImage (z kodu → ścieżka „otwórz", to OK).

**Przetestowane:** gating `can_self_replace`/`appimage_path()` (oba tryby) + **mechanizm podmiany e2e na żywych plikach** (harness: proces-dziecko woła `_linux_self_replace` i ginie → pomocnik czeka na zgon PID → atomowy `mv` zmienia inode → `chmod +x` zachowany → `setsid` odpala nową wersję; zero śmieci `.new-*`). `UPDATE_APPCAST_URL` jest ZAPIEKANY w configu (brak env-override), więc pełny test GUI wymaga zbudowania paczki testowej.

**Zostało (uznane za wystarczająco bezpieczne):** jedyna niepokryta luka = pełny KLIENCKI cykl w SPAKOWANYM AppImage (uruchom→feed→dialog→pobierz→podmień→wstań). Część „pobierz/dialog/sha" wspólna z Mac/Win (sprawdzona e2e); zostaje „czy zapakowany AppImage wstaje po podmianie". **Stan 2026-06-19:** 1.0.18 i 1.0.19 są w feedzie (pipeline wydania potwierdzony e2e 2×), więc test klienckiego cyklu = po prostu uruchomić zainstalowany AppImage i pozwolić mu się zaktualizować. Wciąż NIE potwierdzony przez usera (poprawki testowane z kodu). Pierwszą paczkę user instaluje raz ręcznie, od niej w górę aktualizuje się sama.

## Inne otwarte TODO
- [ ] **Zweryfikować paczki Mac/Win 1.0.19 — czy mają wtyczki Qt** (patrz pułapka „PyInstaller NIE dociągnął wtyczek"). Specki macOS/Windows nie dołączają ich jawnie → prawdopodobnie crash startu jak na Linuksie. Odpalić SPAKOWANĄ paczkę na Macu i Windowsie (nie „z kodu"); jeśli pada na braku `cocoa`/`qwindows` — przenieść fix ze spec Linuksa (jawne `binaries` wtyczek) do `packaging/macos` i `packaging/windows`. Linux już naprawiony i wydany (sha `325378b4…`).
- [ ] **Hasło na strony/instrukcje (roboty/prywatność):** zahasłować całość przez basicauth, ale zostawić PUBLICZNE w `/cva/` TYLKO `appcast.json` + paczki (`.AppImage/.zip/.exe`) — inaczej self-update padnie (klient pobiera feed/paczki bez hasła). Traefik **v3** → zawęź router `cva-pub` przez `PathRegexp` (np. `^/cva/.+\.(AppImage|zip|exe)$` || `Path(/cva/appcast.json)`). NIE robić `robots.txt` (root za auth → 401 → Google traktuje jak brak ograniczeń). Skutek uboczny: przycisk „Pełna instrukcja" w kreatorze też poprosi o hasło (OK w modelu zamkniętej dystrybucji). Czeka na decyzję usera.
- [ ] Potwierdzić **kliencki** self-update spakowanego AppImage: uruchomić zainstalowany AppImage i sprawdzić aktualizację do 1.0.19 (patrz sekcja LINUX SELF-UPDATE).
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
