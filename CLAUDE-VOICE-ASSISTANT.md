# CLAUDE-VOICE-ASSISTANT — Agent aplikacji desktopowej

**Przed pracą załaduj również:** 🔴 [`docs/PRD.md`](docs/PRD.md) (roadmap komercjalizacji 2026) · [`../CLAUDE-COMMON.md`](../CLAUDE-COMMON.md) (procedury, pułapki uniwersalne) · [`CLAUDE.md`](CLAUDE.md) (auto-ładowany w tym katalogu).

> **Historia, pełne narracje i wycięte szczegóły:** `CLAUDE-VOICE-ASSISTANT-ARCHIVE.md` (NIE czytany na starcie) + `git log`.
> **Utrzymanie:** tylko trwałe, aktualne, reużywalne rzeczy. Bez sekcji „SESJA <data>", bez stopek-dzienników. Budżet ~350 linii — przy przekroczeniu konsoliduj (przepis: COMMON „ODCHUDZANIE PLIKÓW PAMIĘCI"; sukces mierz ZNAKAMI, nie liniami).

---

## Projekt

- **Lokalizacja:** `/home/hdkrytbhdkf/Projekty/claude-voice-assistant/` · **GitHub:** https://github.com/WojtekL7/claude-voice-assistant
- **Tech:** Python 3.12, PyQt5, QTermWidget (Linux), WebTerminal = xterm.js+QtWebEngine+PTY (Mac/Win), edge-tts, Groq Whisper, pygame
- **Czym jest:** „pilot" nad CLI **Claude Code** — uruchamia `claude` w terminalu, dokłada głos (TTS/STT), zakładki agentów, MCP/Skills, skórki, auto-aktualizację. **Apka NIE hostuje modelu ani nie zawiera CLI** — konto/logowanie siedzi u usera (`~/.claude`).

```bash
cd /home/hdkrytbhdkf/Projekty/claude-voice-assistant && source venv/bin/activate && python3 src/main.py
```
WebTerminal na Linuksie do testów: `CVA_WEBTERMINAL=1 python3 src/main.py`. Wheel: `wheels/qtermwidget-1.4.0-cp310-abi3-manylinux_2_17_x86_64.whl`.

| Plik | Rola |
|------|------|
| `src/config.py` | Języki, głosy TTS, modele, ścieżki, `APP_VERSION`, `UI_TRANSLATIONS`, `DEFAULT_SPLITTER_SIZES` |
| `src/gui/main_window.py` | Główne okno, menu, TTS/STT, skórki, zakładki, auto-update, `_poll_transcripts` |
| `src/gui/agent_tab.py` | Zakładka agenta: terminal, splitter, input, przyciski |
| `src/gui/dialogs.py` | Dialogi (4-tab konfiguracja agenta, update, ClaudeSetupDialog) |
| `src/gui/terminal_backend.py` | Wspólny interfejs terminala + fabryka (QTermWidget vs WebTerminal) |
| `src/gui/web_terminal.py` | WebTerminal (xterm.js+QtWebEngine+PTY); ConPTY na Windows |
| `src/gui/theme.py` | Paleta „Vibe Purple" — JEDYNE źródło kolorów |
| `src/core/tts_engine.py` | TTS (edge-tts + pygame), kolejka z prefetch |
| `src/core/transcript_reader.py` | Czyta dziennik sesji `.jsonl` (auto-czytanie, flaga „?", `turn_snapshot()`) |
| `src/core/text_cleaner.py` | `prose_from_markdown()` — proza dla TTS |
| `src/core/update_manager.py` | Self-update (pobieranie, sha256, samo-podmiana per OS) |
| `src/core/platform_utils.py` | OS/arch, env Qt, `update_platform_id()`, `macos_app_bundle()`, `claude_runnable()` |
| `tools/scan-dialog-clipping.py` | Skan regresji: 16 okien offscreen, zgłasza widżety ucinające tekst |
| `tools/test-terminal-grid.py` | Bramka siatki terminala (kratka na znak) — odtwarza „rozstrzelone litery" sabotażem |
| `tools/test-bottom-bar-icons.py` | Bramka dolnego paska: kolejność przycisków + styl lupy, mierzone na pikselach |

**Konfiguracja użytkownika — `~/.vibe-coding-assistant/`** (⚠️ po rebrandingu 1.0.25; `~/.claude-voice-assistant` to tylko ŹRÓDŁO MIGRACJI, `config._OLD_CONFIG_DIR`): `config.json` (język, głos, skin, `groq_api_key`, `auto_check_updates`, `claude_command`) · `agents.json` (+`splitter_sizes` per zakładka; jest `agents.json.autobak`) · `memory_projects.json` · `quick_actions.json` · `tts.log` · `login-events.log` · `webterminal.log` · `crash-logs/` · `cloud-*.json` (600).

**Zależności:** klient HTTP = **`requests`**, NIE httpx · **Groq = tylko STT** (wymaga klucza), **TTS = edge-tts, działa BEZ klucza** · `pyenchant` opcjonalny (`ENCHANT_AVAILABLE`) · `pygame.mixer.init()` w try/except (brak audio = TTS off, reszta działa).

---

## ⏳ CZEKA NA TEST NA ŻYWO

- **🔍 Lupa — DWIE usterki podglądu NAPRAWIONE** (`5c21d0f`, 2026-08-03; zgłoszenie + zrzut usera). ⏳ czeka na test w GUI (wymaga restartu bety). Reszta funkcji POTWIERDZONA na żywo — patrz „POTWIERDZONE" niżej.
  - **(1) Podświetlenie przesunięte w lewo** — `_show_preview` dawał `QTextCursor.setPosition` indeks PYTHONOWY (punkty kodowe), Qt liczy w UTF-16 → każde emoji spoza BMP przed trafieniem przesuwało o 1 (realnie: 5 emoji → „wie " zamiast „lupa"). Fix: `conversation_search.utf16_offset()` TYLKO na styku z Qt. ⚠️ To NIE jest złamanie zasady „`fold` zachowuje długość" (tamta pilnuje ogonków) — i dlatego bramki 46/0 przechodziły: liczyły po stronie Pythona, nie patrzyły na widżet.
  - **(2) Od DRUGIEGO szukania cała wypowiedź na fioletowo** — `QTextEdit.setPlainText` wpisuje tekst BIEŻĄCYM formatem znaku, którym po poprzednim podświetleniu był akcent. Zmierzone: 1. szukanie 0 px akcentu, 2. i dalsze 25 283 px (zrzut usera: 28 319 px). Fix: zwinięcie kursora do początku trafienia (to ONO jest mechanizmem) + zerowanie formatu jako druga linia obrony. ⚠️ **Kolejność nie jest dowolna:** `setCurrentCharFormat` przy AKTYWNYM zaznaczeniu nadaje format zaznaczeniu → zerowanie przed zwinięciem SKASOWAŁOBY podświetlenie.
  - Przy okazji: odmiana liczby („1 raz w 1 wypowiedzi") i zawijanie listy wyników zamiast poziomego suwaka. Bramki 46→**62/0**; nagłówek `tools/test-conversation-search.py` niesie ZMIERZONE wyniki 5 sabotaży, w tym wynik negatywny (usunięcie zerowania formatu nie wywala NICZEGO).
  - ⚠️ **Metoda, która to rozstrzygnęła — warta powtórzenia:** render offscreen NIE odtworzył fioletu, więc dowód dał dopiero **pomiar pikseli na zrzucie usera** (`#a855f7` = 28 tys. px, rozkład wiersz po wierszu pokazał, że akcent obejmuje CAŁY tekst, a zaznaczenie tylko 4 znaki) + odtworzenie przez POWTÓRZENIE akcji. Objaw „widać u usera, nie widać u mnie" znaczył: brakuje mi jego HISTORII kliknięć, nie jego środowiska.
- 🖥️ **TERMINAL — „rozstrzelone litery" NAPRAWIONE** (`1c625c8`, 2026-08-04). Kratka xterm.js była mierzona na SZERYFOWYM zamienniku, bo `_push_font` słał gołą nazwę czcionki bez łańcucha zapasowego (17,8 px zamiast 9,52 px = 1,88×). Objaw dawał JEDNOCZEŚNIE dziury między literami i **uciętą prawą połowę linii**. Wyzwalacz potwierdzony: przeniesienie okna na drugi (pionowy) monitor. Ta sama przyczyna dawała „w zakładce VCA inna czcionka niż w pozostałych". Bramka `tools/test-terminal-grid.py` 8/8. ⏳ czeka na test w GUI. → `tekst-rozstrzelony-w-terminalu.md`
- 🔬 **🔊 „czytaj ostatnią" — RUNDA 5, wciąż SAM POMIAR** (`46cf522`, 2026-08-04, NIEPRZETESTOWANE — wymaga restartu bety). Czujnik rundy 4 (`d71e827`) **zadziałał**: pierwsze realne pomiary z kliknięć usera — **29 klików, 5 błędnych (17%)**, za każdym razem czytany krótki wtręt (120–182 zn.) zamiast nowszej długiej odpowiedzi (1343–3559 zn.).
  - ⛔ **Hipoteza „ostatnia odpowiedź trafia do pliku dopiero, gdy user odpisze" — OBALONA pomiarem** (8 sesji/300 s: zapis 0,7–31 s; odpowiedzi 4565 zn. → 0,7 s i 3805 zn. → 2,1 s przed odpowiedzią usera). Nie wracać do niej; potwierdza to ustalenie z BUG #6.
  - Wykluczone pomiarem: odpięta/zła sesja, rozwidlenie, zły plik, kompaktowanie, błąd filtra, logika czekania. Została sprzeczność → runda 5 dokłada **stan PLIKU** (`debug_file_state`: nazwa, rozmiar, mtime, liczba linii i wypowiedzi, ostatnia FIZYCZNA linia).
  - **Protokół:** znacznik `~/.vibe-coding-assistant/read-last-debug.on` jest włączony; gdy 🔊 przeczyta źle, user pisze **„źle"** → czytam blok z `read-last-debug.log`.
  - 🧹 **Dług:** po zamknięciu sprawy skasować znacznik i rozważyć usunięcie diagnostyki (poprzednia urosła do 99 MB).
- ~~🔴 **🔊 „czytaj ostatnią" — RUNDA 3 PRZETESTOWANA 2026-07-27: ZAWIODŁA**~~ (historia, wciąż aktualne ostrzeżenia niżej). User: „nadal czasem czyta przedostatnią". Kod rundy 3 BYŁ w becie (start 27.07 09:19 vs commit 25.07 12:08 — sprawdzone), więc to realna porażka naprawy, trzecia z rzędu. ⛔ **Runda 4 zaczyna się od POMIARU na kliknięciu usera, NIE od poprawki logiki** — trzy rundy poprawiały decyzję (ruch terminala → wolumen strumienia → struktura tury) i każda zawiodła. Najpierw dopytaj: która zakładka · czy było ⏳ „czekam" czy przeczytało natychmiast · co robił agent w chwili kliknięcia · jak często. Szczegóły i kandydat na hipotezę → `czytaj-ostatnia-czyta-inna.md`.
- ~~**🔊 „czytaj ostatnią" — RUNDA 3**~~ (`d1ec938`, historia). Rundy 1 (`e365307`) i 2 (`d825e6d`) user przetestował i OBIE zawiodły — obie pytały terminal „czy leci tekst" (progi 2,0 s → 4,0 s + 200 zn./2 s). Zmierzone na kliknięciu usera: agent **MYŚLAŁ 30 s** (zero wpisów w dzienniku, animacja poniżej progu) → karencja mijała w środku myślenia i apka czytała wypowiedź sprzed 6 minut. Żaden próg ze strumienia tej dziury nie zamknie. Runda 3 decyduje **STRUKTURĄ TURY** z dziennika (`turn_snapshot()` → `idle`/`owes_text`/`tool_pending`/`unknown`, z pominięciem wpisów księgowych i pod-agentów); czekamy WYŁĄCZNIE przy `owes_text`, koniec czekania na DOWÓD (nowa wypowiedź · cisza terminala **I** brak przyrostu pliku ≥4 s · narzędzie >4 s · bezpiecznik 60 s). Bramki 45/0 + regresje 22/22 i 23/23. Test: w CRM klik 🔊 tuż po wysłaniu zadania → ⏳ i czyta TĘ nową · bezczynny agent → natychmiast · pytanie na ekranie → ~4 s i komunikat „agent zatrzymał się" · długie narzędzie → odpowiedź w kilka sekund · zaznaczenie i auto-czytanie bez zmian. → `czytaj-ostatnia-czyta-inna.md`
  - ⚠️ **Profil zakładki CRM wywraca założenie „jedna długa odpowiedź na turę"** (zmierzone: 58 wypowiedzi, mediana **134 znaki**, mediana odstępu **40 s**, narzędzia 10 s–4 min). Każdą zmianę w 🔊 / auto-czytaniu / fladze sprawdzaj NA CRM, nie na zakładce z rozmową.
- **Serwery MCP** — nigdy niesprawdzone na żywo (dodawanie/usuwanie, gating per agent, licznik i status w pasku). Zaległość zgłoszona 2026-07-25.
- **Ładowanie agenta z CHMURY** na drugim komputerze — kod Fazy 1 sprawdzony na atrapie i na prawdziwym Dysku Google, ale kliencka droga „pobierz i pracuj" nieprzeszła. → `chmura-sync-agentow.md`
- **Wyścig „/login"** (`e6af2c3`) — mechanizm ŻYJE (pierwszy wpis w `login-events.log` 2026-07-23), ale to był błąd SIECI (`ENOTIMP`), więc werdykt „wyścig vs prawdziwe wylogowanie" wciąż niewywołany.
- **Auto-czytanie po auto-compact** (`1b57c60`) — najstarsza niepotwierdzona rzecz. ⚠️ NIE mylić z „auto-czytanie działa" (potwierdzone): tu chodzi wyłącznie o zachowanie po tym, jak Claude Code sam skróci dziennik (plik maleje poniżej offsetu; stary kod ustawiał `offset=0` → recytacja od początku). → `auto-czytanie-loop-po-kompaktowaniu.md`

⚠️ **Zanim zdiagnozujesz „fix nie działa" — sprawdź, czy beta w ogóle ma ten kod:** `ps -o lstart= -p $(pgrep -f '[s]rc/main.py')` vs `git log -1 --format=%ad <commit>`. Dwa razy uratowało to przed szukaniem błędu w kodzie, którego apka nie miała. Rzeczy niewywoływalne na życzenie (wyścig /login, auto-compact) czekają na okazję, nie na chwilę usera.

## ✅ POTWIERDZONE PRZEZ USERA NA ŻYWO

Auto-czytanie zwykłe (2026-07-20) · pliki pamięci w ostatnich zakładkach (`0361565`) · 🔊 po naprawie BUG #6 (`0ce9609`) · sprzątanie starych paczek (`updates/` trzyma 1) · **2026-08-03 (testy usera na żywo):**
- **🤖 „Domyślny (Opus 5)" na pasku** (`7c3e264`) — DZIAŁA w GUI. ⚠️ Napis dalej opisuje stan Z DZIENNIKA, nie ustawienie agenta (`agents.json` ma `model: "default"`) — przy diagnozie nie czytaj z paska, że agent ma przypięty Opus. Licznik tokenów bierze okno WYKRYTEGO modelu zamiast założonego 1 mln.
- **🆕 KATALOG MODELI** (`model_catalog.py`) — DZIAŁA (lista Opus 5 / Sonnet 5, „Sprawdź nowe modele", fail-open bez sieci). → sekcja „MODELE" niżej.
- **🔍 Szukanie w rozmowie** (lupa + `Ctrl+F`) — okno, wyszukiwanie w DZIENNIKU sesji, licznik trafień, fragment i przewijanie terminala DZIAŁAJĄ; JEDYNA usterka to przesunięte podświetlenie (patrz 🔴 wyżej). Bramki `tools/test-conversation-search.py` 46/0. ⚠️ Szuka w `conversation_entries()`, NIE w buforze ekranu; `TerminalBackend.scroll_to_text` zwraca `None` na QTermWidget = „nie umiem" i apka wtedy NIC nie twierdzi.

**2026-07-25:**
- **Polskie znaki w terminalu + DYKTOWANIE** (`9aad8dd` + `c38775f`) — bug „dyktowanie ucina litery po `ł`/`ó`" ZAMKNIĘTY. To był JEDEN kanał (`sendText` → PTY → pole Claude Code), nie dwie usterki; STT i bramka AI Managera były niewinne. → `qtermwidget-polskie-znaki-altgr.md`
- **Nadganianie lektora** (`2156fe8`) — kolejka TTS dogania ekran. → `auto-czytanie-spoznione-kolejka.md`
- **Filtr emoji/emotikonów w TTS** (`f80c35a`) — pominięte `:( :) ;) :-D xD :/ <3 -_- ^^ T_T o_O` + ⏳ ✅ → ▶ ░ ▪; kontrola odwrotna OK (`10:30`, `(netto)`, `3:1` czytane). ⚠️ Strażnika `(?<!\w)`/`(?!\w)` NIE ruszać: chroni `10:30`, `C:\Users`, `https://`; emotikon przyklejony do słowa zostaje, ale edge-tts i tak nie wymawia interpunkcji.
- **Auto-czytanie na silniku WebTerminal** (`CVA_WEBTERMINAL=1`, ~3,3 tys. zn. od pierwszego zdania do końca) — domyka silnik, którego realnie używa pobrany AppImage Linuksa.

⚠️ 🔊 był bugiem PRZERYWANYM — user obserwuje dalej. ⚠️ „Auto-czytanie działa" NIE domyka przypadku po auto-compact (inny tor kodu).

- **Przycisk „🔄 Napraw wygląd terminala" — UKRYTY** 2026-07-16 (`cc9bccf`, `setVisible(False)`): usterka nie wracała, a przycisk świecił białym kwadratem. ⚠️ Usterka **uśpiona, nie naprawiona** — mechanizm (zrzut dowodowy + `claude --resume`) ZOSTAJE w kodzie. Powrót = skasuj `setVisible(False)` **I** dopisz przycisk do `_apply_button_icon_styles` (inaczej znów biały). → `tekst-rozstrzelony-w-terminalu.md`

---

## AKTUALNY STAN — wersja 1.0.27 (wydana 2026-07-20, 3 platformy)

- **1.0.27** — pierwsze wydanie z całym redesignem „Vibe Purple" + naprawy: pliki pamięci w ostatnich zakładkach (`0361565`), 🔊 BUG #6 (`0ce9609`), polskie znaki w WebTerminalu (`c38775f`), STT przez bramkę AI Managera (`eab76b3`), jeden silnik terminala wszędzie (`1dc983a`). `SKIN_VERSION` = 4. ⚠️ **Mac i Windows dostały redesign PIERWSZY RAZ tym wydaniem**, paczki na tych systemach nie były z nim uruchomione przed publikacją → przy „dziwny wygląd na Macu/Windows" zacznij od tego.
- **1.0.26:** `claude --session-id <uuid>` przypina czytnik do dokładnego pliku sesji. ⚠️ Bez `--session-id` (ręczny `--resume` po crashu) czytnik jest odpięty → 🔊 czyta złą wypowiedź.
- **1.0.25 (rebranding „Vibe Coding Assistant"):** ⚠️ infrastruktura ZOSTAJE stara (`/cva/` URL, appcast, repo `claude-voice-assistant`, wewn. binarka) — zmiana zerwałaby self-update. Rebrand MUSI obejmować też `.ps1/.yml/.command` (pominięcie = padł build Windows).
- **Wieloplatformowość:** Linux (kod + AppImage), macOS (.dmg/.zip), Windows (.exe Inno). PL/EN (domyślnie EN; PL gdy system polski); en-GB usunięty w 1.0.17 (scalony do en-US + migracja wsteczna w `set_ui_language`).
- **Self-update:** macOS ✅ (1.0.8) · Windows ✅ (1.0.14) · Linux ✅ (kod 1.0.16, feed 1.0.17). Pipeline WYDANIA potwierdzony e2e 2× (1.0.18, 1.0.19); uruchomienie spakowanego AppImage potwierdzone 2026-06-20. **Do potwierdzenia zostaje wyłącznie pełny KLIENCKI cykl self-update** (feed→pobierz→podmień→wstań). Podejrzenie crashu Mac/Win z braku wtyczek Qt ODRZUCONE (PyInstaller dociąga `cocoa`/`qwindows` sam).
- **Kanał:** `https://pobierz.srv1251441.hstgr.cloud` (strona za basicauth) + publiczny feed `…/cva/appcast.json`. Kontener `cva-web` (nginx) na VPS w `/opt/cva-web/`.

**KONWENCJA KOLORU (ustalona z userem): skórka rządzi SPOCZYNKIEM, kod niesie STAN.** Kolory znaczeniowe (`DANGER` nagrywanie/stop, `SUCCESS` czytanie/wznów) siedzą w kodzie — w skórce dałoby się ustawić zielone nagrywanie i sygnał przestałby znaczyć. Nie dokładaj kluczy skórki „per stan" (39 kluczy = dialog i config bez zmian). „Biel" = `theme.TEXT` `#eae6f2`, NIE `#ffffff` (czysta biel tylko na Wyślij, bo leży na gradiencie).
- **„Gdzie jestem" to też STAN:** `theme.TAB_ACTIVE` NIE idzie ze skórki (choć kusi) — inaczej dałoby się ustawić aktywną zakładkę CIEMNIEJSZĄ od reszty.
- ⚠️ **Odcień niosący SYGNAŁ musi mieć MARGINES kontrastu, nie tylko „inny numerek".** Redesign zszedł z 15% do 4% wobec tła i wygasił dwa sygnały naraz, choć kod działał. Mierz różnicę wobec SĄSIADA (średnia RGB), próg roboczy **≥20/255 (~8%)** — nie oceniaj na oko w edytorze.
- **Redesign „Vibe Purple"** (`bc81a03`+`410c9ab`): `src/gui/theme.py` = jedyne źródło kolorów; **zmiana palety wymaga podbicia `SKIN_VERSION`**, inaczej jest NIEWIDOCZNA (config nadpisuje). → `redesign-vibe-purple.md`, `qt-pulapki-qss-redesign.md`
  - ⭐ **ALE: DODANIE nowego klucza skórki podbicia NIE wymaga** — i nie wolno go robić bez potrzeby, bo skasowałoby kolory usera. `_load_settings` iteruje po `DEFAULT_SKIN_COLORS` i bierze z `config.json` tylko klucze, KTÓRE TAM SĄ; nowego nie ma, więc zostaje wartość domyślna. Podbicie jest konieczne wyłącznie przy ZMIANIE wartości istniejącego klucza. (Sprawdzone przy `icon_search_color`, 2026-08-04.)

## KOMERCJALIZACJA 2026 (branding + strona)

Plan z `docs/PRD.md` ruszył od brandingu/strony, NIE od kodu monetyzacji.
- **Nazwa publiczna „Vibe Coding Assistant" (VCA)**, wewn. kod zostaje `claude-voice-assistant` (CVA). Marka bez „Claude". Domena DO KUPIENIA (wolne `.app`: preferowana `vibe-code-app`). → `vca-nazwa-domena.md`
- **Logo** („Prompt Wave": `>` + fala): `branding/logo/` (SVG, PNG 16–1024, `vca.ico`, `vca.icns`, favicon; `rsvg-convert` + Pillow). Wpięte w apkę → `src/assets/icon.{png,svg,128,64}`; paczki generują `.icns`/`.ico` z `icon.png`. Galeria: `branding/logo-concepts.html`.
- **Strona produktowa (staging, NA BRUDNO):** `website/` → VPS `/opt/cva-web/html/cva/staging/` (publiczny, `noindex`). PL+EN: loader, hero, funkcje, cennik Free/Pro, pobieranie, FAQ, kontakt. **Makiety** (alert): płatności, pobieranie, formularz. Przełącznik 🌙/☀️ + auto-język po IP (GeoJS; ręczny wybór w `localStorage` nadrzędny).
- **Dokumenty prawne (robocze):** polityka/licencja/regulamin/cookies PL+EN w `website/`. Dostawca = **Fulfillment Polska**; placeholdery `[forma prawna/adres/NIP]`. ⚠️ przed publikacją: przegląd prawny + DOPISAĆ geolokalizację (GeoJS wysyła IP). → `sekcja-prawna-stan.md`
- **Funkcje po kolei:** #1 ✅ ikona per zakładka · #2 ✅ kolor zakładki + ramka okna aktywnego agenta (1.0.21) · #3 ✅ głos per agent (1.0.21; **322 darmowe głosy edge-tts**: 2 PL, 47 EN, z `edge_tts.list_voices()`).
- **Panel admina:** backend Fazy A gotowy w `server/` (FastAPI+Postgres: licencje/pobrania/wersje); frontend z cloud.co.design pending; Faza B = płatności/deploy. → `panel-admin-stan.md`

## Architektura terminala

`terminal_backend.py` = interfejs `TerminalBackend` (`set_shell_program`, `start_shell_program`, `send_text`, `selected_text`, `copy_selection`, `set_font`, `set_color_scheme`, `scroll_to_text`, `shutdown`; sygnały `output_received(str)`, `finished`). Fabryka: **Linux→QTermWidget** (chyba że `CVA_WEBTERMINAL=1`/brak wheela), **macOS/Windows→WebTerminal**. AgentTab woła backend, nie surowy widget. Gotcha: `AA_ShareOpenGLContexts` + wczesny import QtWebEngine w `main.py`.

## Architektura auto-czytania (Droga A — z dziennika, NIE z terminala)

Proza idzie z **dziennika sesji** `~/.claude/projects/<zakodowana-cwd>/<sesja>.jsonl`, **nie** ze strumienia terminala (TUI = przerysowania, spinner, ghost-text, skoki kursora → śmieci).

| Klocek | Plik | Rola |
|--------|------|------|
| Czytnik dziennika | `transcript_reader.py` | offset bajtowy, `poll()` zwraca NOWE bloki `type=="text"` z `assistant` nie-sidechain; `seek_to_end()` priming |
| Filtr prozy | `text_cleaner.prose_from_markdown()` | wycina kod/tabele/linki/emoji |
| Lektor | `tts_engine.py` | kolejka z prefetch (`enqueue`), `clear_queue()` przy zmianie zakładki, nadganianie zaległości |
| Spinacz | `main_window._poll_transcripts()` (QTimer 800 ms) | aktywna zakładka → `enqueue`; nieaktywne → `pending_backlog` (cap 50) |

Tylko **aktywna** zakładka czyta; przełączenie ucisza poprzednią. Priming `seek_to_end()` pomija historię.

---

## TRWAŁE PUŁAPKI PROJEKTU
*(uniwersalne wersje wielu z nich są w CLAUDE-COMMON — tu skrót projektowy)*

- **QSS NIE SIĘGA DO TEGO, CO MALUJE SAM STYL Z PALETY.** Objaw „stylowane, a mimo to jasne" (biała kreska nad zakładkami = `PE_FrameTabBarBase`, biały błysk inputa = paleta `Base`, biały kwadrat przycisku bez stylu) → podejrzewaj PALETĘ/prymityw stylu, nie QSS. Fix przez `QProxyStyle.drawPrimitive()` (pomiń prymityw), NIE `setDocumentMode` (pogarsza). Diagnoza: **mierz piksele** (PIL `getpixel`, skan pionowy) — ujawniło DWIE linie brane za jedną (3 px `#E2E8F0` = ramka koloru agenta = FUNKCJA; 1 px `#FFFFFF` = bug). Bisekcja na replice z PRAWDZIWYCH klas + realny QSS + `QMainWindow` z tłem; goły offscreen `QTabWidget` myli.
- **Kolor przycisku ma WIĘCEJ NIŻ JEDNO ŹRÓDŁO.** Mikrofon zalewała czerwień z `_animate_mic_pulse` ORAZ z reguły `QPushButton:checked { background: DANGER }` we wspólnym `_apply_button_icon_style` (`dictate_btn` = jedyny `setCheckable`). Reguła USUNIĘTA — nie przywracać. Pytając „skąd ten kolor?" sprawdź `setIcon` **oraz** `:checked`/`:hover`/`:pressed`/`:disabled`. Weryfikacja bez GUI: wyrenderuj `icon_set.button_icon(...).pixmap()` i policz dominujący nieprzezroczysty piksel + KONTROLA NEGATYWNA (mic != hourglass).
- ⛔ **KAŻDY NOWY PRZYCISK PASKA MUSI TRAFIĆ DO `MainWindow._apply_button_icon_styles`** — inaczej Qt zostawia fabryczny BIAŁY kwadrat, krzyczący na ciemnym pasku. **Złapało to już TRZY przyciski**: `mouse_mode_btn`, `repair_terminal_btn` i (2026-08-04, zgłoszone przez usera jako „lupa ma odwrotne kolory niż reszta") `search_btn`. Objaw jest mierzalny: tło pominiętego przycisku ~248 jasności wobec ~24 u sąsiadów. Dodając przycisk, dopisz go w OBU miejscach naraz (utworzenie w `agent_tab` + stylowanie w `main_window`); bramka `tools/test-bottom-bar-icons.py` wykrywa to pomiarem pikseli. ⚠️ Test MUSI wołać `_apply_button_icon_styles` (l. mnoga) — sprawdzanie samego `_apply_button_icon_style` przechodzi mimo braku wywołania, czyli nie łapie właśnie tego błędu.
- **Sztywne wysokości + wyższe czcionki redesignu = ucięte litery.** Qt nie pokazuje suwaka, gdy widżet dostaje mniej miejsca niż potrzebuje — po cichu przycina glify (ogonki p/y/ż, opisy skilli urwane). Zasada: **MIERZ, nie wpisuj liczby** (oprawa = `height() - viewport().height()`; wysokość linii = `blockBoundingRect`, NIE `lineSpacing`; wiersz listy = `heightForWidth` + zmierzona oprawa). Regresję łapie `tools/scan-dialog-clipping.py`. Commity `782120a` + `694251c`.
- **WebTerminal — kopiowanie ginie przez odświeżenia Claude.** xterm.js kasuje zaznaczenie przy każdym zapisie do bufora, a TUI odświeża ~1×/s (QTermWidget trzyma je mimo odświeżeń → „działa w becie, nie w pobranej"). Rozwiązanie 1.0.24 (B1+B2, samo próbkowanie z 1.0.23 było za słabe): **B1** `_stripMouse()` wycina z wyjścia DECSET raportowania myszy (`?1000/1001/1002/1003/1005/1006/1016 h`; wyłączające `l` przepuszcza, carry na styku porcji) → drag zaznacza natywnie, BEZ Shift; **B2** `safeWrite()` + `_writePaused` kolejkuje `term.write` na czas przeciągania (mousedown→mouseup na `el`/`window` capture), po puszczeniu łapie zaznaczenie i `_flushWrites()` (bezpiecznik 6 s). Kompromis: Claude traci mysz w swoim oknie (kółko przewija natywnie). Wyjście PTY idzie `bridge.output → safeWrite`.
- **Flaga „?" — wyświetlanie samonaprawiające się.** `_refresh_question_flag` porównuje zamiar `show` z REALNYM stanem paska (`bar.tabButton(index, LeftSide) is not None`), NIE z notatką w cache (usunięta) — rozjazd cache↔rzeczywistość trwale blokował znaczek przez early-return. Teraz odtwarza się sam przy najbliższym ticku (≤0,8 s). Pokazuje się TYLKO na zakładce NIEaktywnej.
- **Flaga „?" — wykrywanie:** z dziennika + terminala, NIGDY z treści. Warunek = DWIE cisze: `transcript_reader.waiting_for_user()` **I** `monotonic()-_last_terminal_data_ts >= QUESTION_TERMINAL_QUIET_SECS (3.0)`. Sama cisza dziennika NIE wystarcza (dostaje tylko ukończone wpisy → stoi 20+ s podczas pisania). ⚠️ Idle Claude Code MIGA kropką ● co 0,5 s → bez progu terminal nigdy nie jest „cichy" (fix `ae17a79`, potwierdzony). → `flaga-migajaca-kropka-idle.md`, `czujnik-flagi-debug.md`
- **QTabBar — pakiet pułapek (1.0.25):** (1) QSS `QTabBar::tab` **GEOMETRIA (padding/font-size) jest IGNOROWANA**, gdy pasek ma własny `QStyle` (Fusion `_LeftAlignedTabStyle`) — kolory działają, rozmiar nie; czcionkę/ikonę ustawiaj API (`tabBar().setFont`, `setIconSize`). (2) Widżet LeftSide (`setTabButton`) ma NIEUSUWALNY odstęp od ikony → flaga „?" jest ŻÓŁTĄ IKONĄ z lewej (badge wmalowany w róg `_icon_with_flag` / `_flag_only_icon` dla emoji); tytułu NIE kolorujemy. (3) `setTabIcon`/`setTabText`/`setTabTextColor` **RESETUJĄ przewinięcie paska** → `_refresh_question_flag` jest NO-OP przy niezmienionej sygnaturze `(show, nazwa, repr(icon_spec))` (sygnatura ze STABILNYCH danych, nie z `QIcon`). (4) emoji-ikona = TEKST (rośnie z czcionką, monochromatyczna), obrazek = `setTabIcon` (rośnie z `setIconSize`). (5) Dzióbki przewijania stylowalne przez `QTabBar QToolButton` + `::left-arrow/::right-arrow { image }`. ⚠️ Render offscreen `QTabWidget` NIE oddaje realnego paska — zachowanie sprawdzaj testem funkcjonalnym (klik + `tabRect`), wygląd potwierdzaj u usera.
- **Ikona zakładki (`_agent_label_icon`):** emoji = prefiks w TEKŚCIE ('🤖 '), własny plik = `setTabIcon(QIcon)` + sama nazwa, brak = '🤖 Nazwa'; flaga „?" po zniknięciu przywraca ikonę pliku. Edycja agenta odświeża zakładkę na żywo (`_refresh_open_agent_tabs`). **Paleta emoji = klikalny `QLabel` w POPUPIE** — inline siatka w `QFormLayout` wciska się i gubi glify; `QLabel` renderuje KOLOROWE emoji (przycisk przy ciasnym layoucie gubi glif). ⚠️ Ciemne tło popupu ustaw jawnie na `QScrollArea` + `viewport()` + widget treści (sam `QDialog` nie wystarcza).
- **WebTerminal — kilka kopii apki = zalew `Cookie sqlite error: database is locked`** (wspólny domyślny profil QtWebEngine). Fix: profil **off-the-record** (`QWebEngineProfile(parent)` bez nazwy) podany do `QWebEnginePage(profile, parent)`.
- **Izolowane testy WebTerminala:** `python3 src/gui/web_terminal.py` = goły WebTerminal (jedno okno, BEZ `agents.json`) → reprodukcja błędów bez drugiej pełnej instancji (dwie instancje biją się o `agents.json`). Konsola JS → `~/.vibe-coding-assistant/webterminal.log`.
- **WebTerminal — bufor wejścia do PTY.** Powłoka startuje dopiero po `frontend_ready` (~2 s w AppImage); wcześniejsze `claude`/wiadomość `_write_pty` gubił po cichu. Fix: `_pending_input` + opróżnianie w `_spawn()`.
- **WebTerminal — czcionka pt vs px.** `set_font(size)` przekazuje PUNKTY; xterm.js liczy w PIKSELACH → `px=round(size*96/72)` TYLKO na styku `_push_font` + `fontSize` startowy w `terminal.html`.
- ⛔ **WebTerminal — NIGDY nie wysyłaj gołej nazwy czcionki; xterm.js mierzy kratkę RAZ.** Nasze kroje idą przez `@font-face` i doczytują się asynchronicznie, więc sama nazwa („Ubuntu Mono") jest przez chwilę BEZ POKRYCIA → przeglądarka rysuje domyślnym SZERYFOWYM, xterm mierzy na nim kratkę i **zostaje z nią**. Skutki: litery z dziurami, ucięta prawa połowa linii, „inna czcionka w jednej zakładce". Zasady: rodzina ZAWSZE z łańcuchem zapasowym · realne monospace PRZED `Menlo`/`Consolas` (na Linuksie `fc-match Menlo` → PROPORCJONALNE Noto Sans) · `fit()` NIGDY w tym samym takcie co zmiana czcionki (dwie klatki) · po zmianie wymuś `remeasure()` (xterm przemierza tylko przy ZMIANIE opcji — samo czekanie nie wystarcza) · strażnik: kratka poza 0,45–0,75 rozmiaru czcionki = usterka. Diagnoza: `webterminal.log` (dwie różne liczby kolumn dla tego samego okna) + pomiar pikseli na zrzucie. Bramka: `tools/test-terminal-grid.py`.
- **WebTerminal — drag&drop pliku: ścieżki NIE ma w JS** (Chromium ją ukrywa). Bierz PO STRONIE Qt: `eventFilter` na `view.focusProxy()` (to ON dostaje `QDropEvent`) → `mimeData().urls()` → `toLocalFile()` → `_write_pty`. **Reinstaluj filtr w `showEvent`** — Qt PODMIENIA focusProxy przy ukryciu/przenoszeniu (stary filtr przepada). Pole input osobno: `insertFromMimeData` z `hasUrls()`. Objaw zgłoszony przez usera: „upuściłem obrazek i apka się zacięła" (`a123504`).
- **transcript_reader — przypięcie sesji + SAMONAPRAWA.** `set_working_directory` zapamiętuje `_preexisting` + `_reader_start`. **Poziom 1:** plik `.jsonl` powstały PO starcie zakładki. **Poziom 2 (samonaprawa):** gdy brak takiego — przygarnij plik istniejący wcześniej, ale zapisywany PO starcie czytnika (`_safe_mtime > _reader_start` = WZNOWIONA żywa sesja), z przeskokiem na koniec (`offset=size`, bez odgrywania historii). Stare NIETKNIĘTE pliki dalej pomijane. Bez tego po self-update/restarcie czytnik był ślepy na trwającą rozmowę (cisza w czytaniu + flaga nie wykrywała ciszy).
- **Wykrywanie `claude` MUSI iść przez powłokę logowania, nie przez PATH aplikacji.** GUI z Findera/Docka (macOS) ma OKROJONY PATH → `shutil.which("claude")` zawodzi mimo działającego CLI (przed 1.0.20 kreator wyskakiwał przy każdym starcie). Fix: `platform_utils.claude_runnable()` pyta `zsh -lc 'command -v claude'` (mac/linux) / `where` (win). Logowanie: `claude_logged_in()` = `~/.claude/.credentials.json` LUB wpis Keychain `Claude Code-credentials` (mac; `security find-generic-password -s`, rc 44 = brak). Gotowość liczona w wątku tła → sygnał `_readiness_ready`.
- **`claude` zepsuty/niezgodny na Windows — apka utyka na STAREJ ścieżce.** Objaw: „Nieobsługiwana aplikacja 16-bitowa"/„niezgodna z wersją Windows" dla `…\npm\…\claude.exe`. **Przyczyna NIE u nas** — bug Claude Code 2.1.113–114 (npm pobiera binarkę Linuksa; reprodukuje się w gołym PowerShellu). Dlaczego reinstalacja nie pomaga: (1) `find_claude_command()` = `shutil.which` bierze PIERWSZY z PATH → zepsuty npm przesłania natywną w `~\.local\bin`; (2) `main_window` PERSYSTUJE `claude_command` w `config.json` i podmienia tylko gdy `find_claude_command()` zwróci INNĄ. Naprawa u usera: `npm uninstall -g @anthropic-ai/claude-code` → `irm https://claude.ai/install.ps1 | iex` → w Ustawieniach komenda = samo `claude` → restart.
- **„Pobrana apka działa inaczej niż z kodu" (Linux) = inny backend terminala.** AppImage wyklucza QTermWidget (`excludes=["QTermWidget"]` w `.spec`) i startuje z `CVA_WEBTERMINAL=1`. Bug „tylko w pobranej" reprodukuj: `CVA_WEBTERMINAL=1 python3 src/main.py`.
- **PyInstaller NIE dociąga wtyczek platformowych Qt → AppImage crashuje w 1. sekundzie** (`Could not find the Qt platform plugin xcb`, exit 134). Nie wyłapano, bo spakowanej wersji NIGDY nie odpalano. Fix (`075ff54`): JAWNIE dołącz grupy wtyczek jako **`binaries`** (nie `datas`! — binaries wciągają zależności: `libQt5XcbQpa`, `libxcb-*`) z celem `PyQt5/Qt5/plugins/<grupa>` (bo `qt.conf` ma `Prefix=..`): `platforms`, `xcbglintegrations`, `platformthemes`, `platforminputcontexts`, `iconengines`, `imageformats`, `wayland-*` + twardy bezpiecznik (build pada bez grupy `platforms`). Weryfikacja: 168→189 MB, `find -name libqxcb.so`, przeżycie procesu >5 s. ⚠️ Specki macOS/Windows mają TEN SAM brak — NIEZWERYFIKOWANE.
- **Każdy nowy `packaging/<os>/*.spec` → `git add -f`** (`.gitignore` ma `*.spec`). Linuksowy `.spec` był nieśledzony → wadliwy build był poza reviewem.
- **Paczka jest „świeża" — sekretów NIE ma w buildzie.** `GROQ_API_KEY = os.getenv(...)` (zero hardcode); klucz zapisuje NASZA apka do `config.json`, login Claude tworzy samo Claude Code. `datas` = `src/assets` + `config.py` + `i18n` + `gui/*.svg`. „Pobrana apka ma moje ustawienia" = ZŁUDZENIE (czyta HOME). **Weryfikacja czystości:** `--appimage-extract` + `grep -r` po WYPAKOWANYCH plikach — raw-grep na `.AppImage` myli w obie strony (squashfs kompresuje).
- **Lazy activation zakładek.** `self._ui_ready` (False przez `__init__`) w `_on_tab_changed`; primary tab aktywowany odroczonym `QTimer` (bo `setCurrentIndex(0)` nie emituje `currentChanged`). Guard idempotencji w 3 ogniwach.
- **Sygnały zakładki = jedno źródło:** `MainWindow._connect_agent_tab_signals(tab)` — oba tory tworzenia (Dodaj agenta / „+") muszą ją wołać, inaczej „+" gubi `terminal_output` (licznik tokenów milczy).
- **`QTermWidgetBackend._on_received`:** `receivedData` niesie `str`, nie QByteArray → obsłuż `isinstance(str)`/`hasattr('data')`/`bytes()` (inaczej `TypeError` połykany i całe wyjście ginie).
- **Zamykanie zakładki:** najpierw `setCurrentWidget(cel z MRU _tab_mru)`, POTEM `removeTab` — „+" to atrapa-QWidget (inaczej czarny ekran albo przypadkowy start claude w sąsiedniej).
- **Splitter nowej zakładki:** `config.DEFAULT_SPLITTER_SIZES=[1500,190]` (jedyne źródło) + `_inherit_splitter_sizes()`; `dialogs.get_data` NIE wpycha defaultu nowemu agentowi.
- **Zakładki macOS do lewej:** `_LeftAlignedTabStyle` = QProxyStyle na Fusion + override `subElementRect(SE_TabWidgetTabBar)` (QMacStyle IGNORUJE `SH_TabBar_Alignment`); podpięty do `tab_widget.setStyle` ORAZ `tabBar().setStyle`.
- **Pauza TTS:** sygnał `request_pause` → `_toggle_pause` → `tts.toggle_pause()`; przycisk ⏸ tylko podczas `PLAYING`.
- **TTS limit czasu:** `asyncio.wait_for(save, TTS_GEN_TIMEOUT=12)`, `TTS_GEN_ATTEMPTS=2`, błędy → `tts.log`; po nieudanych próbach zdanie pomijane (lektor nie wisi). Bez tego zatkany edge-tts wieszał czytanie.
- **i18n:** centralny `config.t(key)` (import `from config import t as tr` — ABSOLUTNIE, nie `from ..config`); parytet `pl-PL`/`en-US` (`set(pl)==set(us)`); przy zmianie języka USUWAJ stare QAction przed odbudową menu (inaczej „ambiguous shortcut"). → `i18n-architektura.md`
- **Rozróżnienie okna „z kodu (beta)" vs wydanego:** `config.IS_DEV = not getattr(sys,'frozen',False)` → `APP_WM_CLASS` (`-beta`), `APP_TITLE_SUFFIX`; `main.py`: `setApplicationName(APP_NAME + " (beta)")` + **`setDesktopFileName(APP_WM_CLASS)`**. Na **GNOME Wayland** dock grupuje po **app_id** (= `setDesktopFileName`), nie po X11 WM_CLASS → trzeba `.desktop` w `~/.local/share/applications/` ze `StartupWMClass` == app_id. Nowy `.desktop` wchodzi do „Pokaż aplikacje" dopiero **po wylogowaniu**. → `dock-zebatka-wmclass.md`
- **Windows spakowany (QtWebEngine):** `QTWEBENGINE_DISABLE_SANDBOX=1`; polyfill `replaceChildren` w `terminal.html` przed xterm.js (Chromium 83); `collect_all('winpty')` w `.spec`; `sys.stdout/err.reconfigure(errors="replace")` w `main.py`.

---

## DIAGNOZA CRASHU `claude` W ZAKŁADCE + „czarna skrzynka"

Objaw: zakładka „wypada" do gołego basha z hintem `claude --resume <uuid>` — user widzi to jako „wylogowanie". To **crash procesu `claude`**, NIE crash CVA: powłoka przeżywa (claude to jej dziecko), więc `backend.finished` NIE odpala. Ekran „Resume this session" to ratunkowy ekran Claude Code.

**Kolejność wykluczania:** (1) **RAM/OOM** → `journalctl --since today | grep -iE "earlyoom|oom-kill|killed process"`; (2) **token** → mtime + `expiresAt` z `~/.claude/.credentials.json` (⚠️ „401" w `.jsonl` to zwykle fałszywka — treść pamięci, cyfry w timestampach); (3) **błąd API** → wpis z `isApiErrorMessage:true`; (4) zostaje **crash wewnętrzny `claude`** (współbieżne sesje dzielą `~/.claude.json` + `.credentials.json`; backup `~/.claude/backups/…` co do sekundy crashu = trop kolizji).

Padła sesja jest w pełni odzyskiwalna: `claude --resume <uuid>`.

**„Czarna skrzynka":** stack trace szedł na stderr i się przewijał (CVA czyta `.jsonl`, nie stderr). `AgentTab` trzyma ring-bufor surowego wyjścia (`_terminal_capture`, ~64 KB, `config.TERMINAL_CAPTURE_BYTES`) i przy wykryciu `claude --resume <uuid>` zrzuca go (bez ANSI) do `~/.vibe-coding-assistant/crash-logs/crash-<agent>-<data>.log` — **pierwsze miejsce do czytania przy następnym crashu**. Implementacja: `_on_terminal_output` (tani pre-check) → `_maybe_dump_crash_log` (`_CRASH_SIGNATURE_RE` + debounce 30 s) → `_dump_crash_log`. Pasywne. → `cva-crash-diagnostyka.md`

## MODELE — katalog samoaktualizujący się (2026-07-26)

**Alias = ZAWSZE NAJNOWSZY model rodziny.** `claude --model opus` to dziś **Opus 5**, `sonnet` → **Sonnet 5** (zweryfikowane na żywo; pomoc CLI mówi wprost „alias for the latest model"). Dlatego etykiety z numerem wersji starzeją się PO CICHU — apka pokazywała „Opus 4.8", uruchamiając Opus 5, a licznik tokenów dawał Sonnetowi 200 tys. zamiast 1 mln.

**Nazwa modelu ma JEDNO źródło:** `config.CLAUDE_MODELS` (+ nadpisanie z sieci). Tłumaczenia niosą wyłącznie OPIS (`model_*_desc`); etykieta = nazwa + opis (`model_label()`). ⚠️ Wcześniej nazwa żyła w 6 miejscach (2 słowniki + PL + EN) — stąd rozjazd. Nie przywracaj `model_*_full`/`_short`.

**`core/model_catalog.py`** pobiera nazwy i okna kontekstu z `platform.claude.com/docs/en/about-claude/models/overview.md` (czysty `.md`, bez klucza API i bez logowania), cache w `~/.vibe-coding-assistant/models-cache.json`.
- ⛔ **FAIL-OPEN**: brak sieci / zmieniony układ strony / uszkodzony plik → wartości wbudowane, apka działa jak wcześniej. Parser ma bramkę przytomności (<2 modele z oknem kontekstu = błąd, nie cicha podmiana dobrych danych śmieciami).
- **Sieci NIE MA w imporcie `config.py`** — pobiera wątek tła 5 s po starcie i tylko gdy cache >7 dni; ręcznie: Ustawienia → „Sprawdź nowe modele".
- ⚠️ **Nowej RODZINY nie dodajemy sami** — nie wiadomo, czy `claude --model <alias>` przyjmie ją w CLI usera; apka o niej INFORMUJE (`new_families`), decyduje człowiek.
- ⚠️ **Nałożenie katalogu MUTUJE słowniki w miejscu** (`apply_model_catalog`) — inne moduły zrobiły `from config import CLAUDE_MODELS` i trzymają referencję; podmiana przypisania byłaby dla nich niewidoczna.
- Bramka: `tools/test-model-catalog.py` (61/0) — parser na PRAWDZIWEJ stronie w `tools/fixtures/`, z kontrolami negatywnymi.

**Czego uruchomi „Domyślny", apka NIE WIE z góry** — dowiaduje się po fakcie z dziennika (`message.model`); mapę `identyfikator API → klucz` trzyma `config.CLAUDE_MODEL_API_IDS` (katalog + wpisy wbudowane). Stąd pasek „Domyślny (Opus 5)" — patrz „⏳ CZEKA NA TEST NA ŻYWO".

**Dodanie modelu ręcznie** (gdy trzeba przypiąć konkretną wersję): klucz = to, co idzie do `claude --model` (pełna nazwa, np. `claude-opus-4-8`, nie alias — alias by się przesunął). Dopisz do `CLAUDE_MODELS` + `CLAUDE_MODEL_CONTEXT_LIMITS` + opcjonalnie `model_<klucz>_desc` w OBU językach. Zweryfikuj na żywo: `claude --model <klucz> -p "OK"` → exit 0 (⚠️ przez `env -u CLAUDECODE …`, patrz COMMON).
**Zużycie — ZMIERZONE na 42 tys. wypowiedzi z dzienników usera (2026-07-26), nie z cennika:** Opus 4.8 = 100%, **Opus 5 = 118%**, **Fable 5 = 177%** (Fable ma 2× cenę za token — to on zjada limit, nie Opus 5). Cena za token Opus 5 = identyczna jak 4.8; różnica siedzi w większym przeładowywanym kontekście, a nie w dłuższych odpowiedziach (wyjście na turę jest wręcz o 6% KRÓTSZE). ⚠️ Część z tych 18% to dłuższe sesje, nie model (rozrzut per projekt 0–36%). ⛔ **Nie powtarzaj mojego błędu:** napisałem userowi, że „Opus 5 domyślnie myśli, więc zużyje więcej" — to prawda dla SUROWEGO API, ale Claude Code ustawia `thinking` sam, więc go nie dotyczy; pomiar to obalił. Metoda pomiaru → COMMON „Monitorowanie ZUŻYCIA TOKENÓW Claude Code".
⚠️ **`~/.claude.json` ma wpisane `model: claude-opus-4-8`, a bez `--model` odpowiada Opus 5** (zmierzone w dwóch katalogach). Ten wpis to martwa pozostałość, której CLI już nie honoruje — **nie czytaj z niego domyślnego modelu**, zmierz `claude -p … --output-format json` i sprawdź `modelUsage`. Stąd etykieta „Domyślny (z konfiguracji Claude Code)" celowo BEZ numeru wersji.

## ⚠️ Pamięć/RAM — każda zakładka = osobny proces `claude`

Apka w Pythonie jest lekka (~80 MB). Pamięć zżera **Claude Code CLI: 3–5 GB NA ZAKŁADKĘ** (node, rośnie z długością sesji i kontekstem startowym). 4 auto-startujące zakładki × ~4 GB przebijają RAM → swap → zawieszanie (i spowolnienie dyktowania). Łagodzenie: mniej auto-startu, restart długich zakładek (Stop→Uruchom / `/clear`), szczuplejsze pliki pamięci, `earlyoom` jako siatka. Sam dokup RAM nie wystarczy. → `pamiec-ram-claude-cli.md`, `run-safe-limity-ram.md`

## 🟡 „Please run /login" = WYŚCIG O ODŚWIEŻENIE TOKENU — ETAP 1 (obserwacja) ZROBIONY (`e6af2c3`)

**User NIE był wylogowany** — to zakładki VCA przewracają się nawzajem. Zmierzone 2026-07-20: 8 procesów `claude` na jednym `~/.claude/.credentials.json`, 5 odmów w 4 zakładkach w 5 minut wokół wygaśnięcia (16:51), plik odnowiony 16:55. Proces NIE ginie — wisi z martwą sesją, więc wygląda na zawieszenie. ⚠️ To NIE wina kolektora AI Managera (on plik tylko CZYTA).

**Stan:** apka WYKRYWA odmowę, po opóźnieniu orzeka „wyścig vs prawdziwe wylogowanie", zapisuje do `login-events.log` + komunikat na pasku. Automatycznego restartu NIE MA — świadomie, do potwierdzenia werdyktów na żywych danych.
1. ✅ **Wykryj:** `TranscriptReader._is_api_error` + `take_api_errors()` → `_on_claude_api_error`. ⚠️ Rozpoznanie po **PIECZĄTCE `isApiErrorMessage`**, NIGDY po treści — fraza „Please run /login" występuje w normalnej rozmowie (choćby w tych plikach pamięci) → dopasowanie tekstowe restartowałoby zakładkę, gdy ktoś o usterce *napisze*. Kontrola negatywna w `tools/test-login-race.py`. Przy okazji błędy przestały iść do lektora.
2. ✅ **Odróżnij wyścig od PRAWDZIWEGO wylogowania** (bez tego pętla restartów): `platform_utils.claude_credentials_state()` + `credentials_refreshed_since()`. ⚠️ **Werdykt MUSI zapadać Z OPÓŹNIENIEM** — zwycięzca odnawia plik po kilku minutach (zmierzone: 8 min) → ocena natychmiastowa orzekłaby „wylogowanie" dla KAŻDEGO wyścigu; dopytujemy co minutę przez 12 min. ⚠️ Na macOS poświadczenia są w Pęku kluczy, nie w pliku → `available=False` = werdykt „nierozstrzygnięty" + rada „wpisz /login".

**ETAP 2 (auto-restart) — włączyć DOPIERO gdy `login-events.log` pokaże bezbłędne werdykty na żywych danych:** (3) restart zakładki z TYM SAMYM `--session-id` (`main_window.py` ~2344; `TranscriptReader.pin_session`) zachowuje wątek rozmowy; (4) bezpieczniki: 1 restart na zdarzenie + cooldown ~2 min per zakładka + licznik prób, po drugiej nieudanej — powiedz userowi wprost; restart NIE może wejść w środek pisania (`waiting_for_user()`); (5) testy OBA kierunki: wyścig → jeden restart, prawdziwe wylogowanie → zero restartów i komunikat.
⛔ **Nie dokładaj w VCA własnego odnawiania tokenu** — to DZIEWIĄTY uczestnik wyścigu. **Łagodzenie bez kodu:** mniej jednoczesnych zakładek (zbieżne z notatką o RAM).

---

## DYSTRYBUCJA / WYDANIA — runbook (sprawdzony 1.0.13→1.0.17, potem 1.0.21)

1. Bump `APP_VERSION` w `src/config.py` → commit/push.
2. `git tag vX.Y.Z && git push origin vX.Y.Z` → Actions buduje mac+win (`build-macos.yml` runner `macos-14`, `build-windows.yml` `windows-latest`) i publikuje Release. (Iteracja bez wydania: `gh workflow run build-*.yml --ref main`.)
3. `gh release download vX.Y.Z -p '*.zip' -p '*.dmg' -p '*.exe'` → `dist-release/`. ⚠️ Wzorzec `*Setup.exe` NIE łapie `VibeCodingAssistant-Setup-1.0.20.exe` — używaj `*.exe`.
4. **Wgraj paczki PRZED appcastem** (inaczej okno błędu 404): `.zip`(mac) + `Setup.exe`(win) + `.AppImage` (build lokalny `CVA_SKIP_DEPS=1 bash packaging/linux/build.sh`) → `/opt/cva-web/html/cva/`. ⚠️ **Duże paczki przez `scp` BYWAJĄ UCINANE bez widocznego błędu** (1.0.17: AppImage przyszedł 167/198 MB) → używaj `rsync --partial --inplace -e ssh` i ZAWSZE sprawdź rozmiar/sha256 na serwerze przed uploadem appcastu. ⚠️ **`rsync --inplace` PRZENOSI uprawnienia źródła, a `gh release download` zapisuje `.exe` jako 600 → nginx nie czyta → HTTP 403** (`.zip`/`.AppImage` są 644). Po uploadzie ZAWSZE `chmod 644` na `.exe` (w `cva/` ORAZ w `downloads/`).
5. `.dmg`/`Setup.exe`/`.AppImage` → `/opt/cva-web/html/downloads/` pod **stałą nazwą** (`VibeCodingAssistant-macos.dmg`, `-Setup.exe`, `-linux.AppImage` + `chmod +x`; starą jako `.bak`). Oszczędność łącza: kopiuj server-side (`cp`) zamiast wgrywać drugi raz.
6. Wpis do feedu: `python3 packaging/make-appcast-entry.py PACZKA --version X --platform <macos-arm64|windows-x64|linux-x64> --base-url https://pobierz.srv1251441.hstgr.cloud/cva/ --appcast packaging/appcast.json --merge` → `scp appcast.json`.
7. **Weryfikacja publicznym URL:** `curl …/cva/appcast.json` (version + wpis dla platformy) + `curl -I …PACZKA` (200, `content-length`==`size`, sha256 serwer==feed).

Uwagi: appcast ma **jedną globalną `version`** dla wszystkich platform (brak wpisu dla `update_platform_id()` = cicho „no_update"). `/downloads/` jest za basicauth (401 przez curl = normalne), publiczny jest tylko `/cva/`. Aktualizacje pełnopaczkowe → przeskok wielu wersji bezpieczny (wyjątki: Mac ≤1.0.7, Win 1.0.12–1.0.13). Onboarding świeżej maszyny: Node.js + `npm i -g @anthropic-ai/claude-code` + login (prowadzi `ClaudeSetupDialog`).
**Retencja paczek:** cotygodniowy cron `/etc/cron.d/cva-prune-releases` (pon. 4:30; źródło `packaging/prune-release-channel.py`, domyślnie PRÓBA NA SUCHO, kasuje z `--apply`). Chroni pliki wskazane przez `appcast.json` i strony; „N najnowszych" liczy w grupie aplikacja+platforma (`.dmg` i `.zip` Maca to OSOBNE grupy).
**Wydanie „do poczekalni":** `workflow_dispatch` buduje `.exe` jako artefakt (nie Release) — wgraj do `/cva/` (**chmod 644!**) bez podbijania appcastu. → `wydanie-do-poczekalni-appcast.md`

## LINUX SELF-UPDATE (AppImage) — ZROBIONE (kod 1.0.16, `e91b76f` + `175b683`)

Jak na Macu, prościej (AppImage = JEDEN plik): `platform_utils.appimage_path()` → `$APPIMAGE` lub `None`; `update_manager.can_self_replace` (Linux + `.appimage` + `appimage_path()`), `_linux_self_replace()` = skrypt bash czeka aż PID zniknie → atomowa podmiana (`cp` obok celu + `mv`) → `chmod +x` → restart `setsid` → `relaunch_ready`.
**Trwałe pułapki:** podmieniaj **`$APPIMAGE`**, NIE `sys.executable`/`/tmp/.mount_*` (mount znika po zamknięciu); `chmod +x` obowiązkowy; feed MUSI mieć wpis `linux-x64`; paczka na serwer PRZED appcastem; `$APPIMAGE` istnieje tylko przy uruchomieniu jako AppImage. `UPDATE_APPCAST_URL` jest ZAPIEKANY w configu (brak env-override) → pełny test GUI wymaga zbudowanej paczki testowej.
**Przetestowane:** gating + mechanizm podmiany e2e na żywych plikach. **Zostało:** kliencki cykl w spakowanym AppImage (uruchom zainstalowaną paczkę i pozwól jej się zaktualizować).

## STRONY INSTRUKCJI (`packaging/web` → VPS `/opt/cva-web/html/cva/`, publiczne)

PL + `-en`. Instalacja 3 systemów **SCALONA** w `instrukcja-instalacja.html` (menu macOS·Linux·Windows·Dyktowanie·Agenci, OS-y przełączane JS, kotwica `#os`). Stare `instrukcja-{macos,linux,windows}{,-en}` = przekierowania → stare apki dalej działają. Generatory (uruchamiać z `packaging/web/`): `build-instalacja.py` — **MUSI prefiksować `id`/anchory/`copyCmd('id')` per panel** (3 strony miały te same `id` → kolizja `getElementById`; `copyCmd` siedzi PO `<footer>`); `inject-menu.py` wstrzykuje menu + sekcję o dyktowaniu (idempotentny). ⚠️ `build-instalacja.py` nadpisuje strony OS przekierowaniami — przed ponownym uruchomieniem `git checkout` oryginałów. Apka linkuje przez `config.install_guide_url`.

## CHMURA — Faza 1 KOMPLETNA W KODZIE (2026-07-21)

Plan: `docs/PLAN-CHMURA-SYNC.md` (sekcja 9 = szyfrowanie). Pamięć: `chmura-sync-agentow.md`.
- **Silnik:** `src/core/cloud/agent_bundle.py` + `bundle_crypto.py` (AES-256-GCM + scrypt), testy 26/26 + `tools/test-cloud-bundle.py`. **Paczka niesie:** agentów (ikony/kolory/głosy), pliki pamięci, definicje skilli, gating MCP, szybkie akcje, projekty pamięci, skórkę, język **oraz klucze API** (decyzja usera). NIE niesie kodu projektów (idzie przez `git clone`) ani `claude_command`.
- **Dysk Google działa na żywo** (`a7663f5`+`a6c5ddc`): `google_drive.py` — OAuth desktop + PKCE, loopback `127.0.0.1`, zakres `drive.file` (apka widzi TYLKO własne pliki → bez audytu Google), token 600. Projekt usera: `impressive-bay-503111-d1` („VCA Google"), klient `installed`; dane w `~/.vibe-coding-assistant/cloud-google-{client,token}.json`. ⚠️ Aplikacja MUSI być w trybie **Produkcja** (nie „Testowanie") — inaczej Google kasuje bilet odnowienia po 7 dniach.
- **Ekran „Chmura"** (`src/gui/cloud_dialog.py`, menu Ustawienia; prosty — user odrzucił makietę Cloud Design): konto, hasło paczki, wyślij/pobierz. Sieć w wątku roboczym (logowanie czeka minuty na zgodę w przeglądarce). Testy 22. **Hasło:** apka proponuje kod z `generate_passphrase()`, user może wpisać własne; zapamiętane w `cloud-passphrase.txt` (600). Funkcja docelowo **Pro** (`license_manager` to zaślepka — miejsce na sprawdzenie licencji oznaczyć, ale NIE udawać blokady).
- **Przeprowadzka potwierdzona na prawdziwych danych i prawdziwym Dysku:** 10 agentów, 1098 KB, 12 plików pamięci, 273 pliki skilli, **8 projektów do `git clone`**, 0 ostrzeżeń; klucze API dojechały, `claude_command` NIE. ⚠️ **Pliki pamięci z repo gitowych są ŚWIADOMIE pomijane przy imporcie** (przyjdą z klonem; kopiowanie wywaliłoby klon do niepustego katalogu) → okno MUSI mówić, ile projektów czeka na sklonowanie (`7daddb4`), inaczej user widzi agentów bez kodu i zgłasza to jako błąd.
- ⚠️ **Etykieta bez jawnego `color:` = czarny tekst na czarnym tle** (`24eb386`) — Qt bierze wtedy barwę z palety. W `cloud_dialog` pilnuje tego reguła strukturalna w teście (każdy `QLabel` ma `color:`) ze sprawdzoną kontrolą negatywną. ⚠️ Podgląd renderowany z WŁASNYM, doraźnym QSS tego NIE pokazał.
- ⚠️ **Znane ograniczenie: KASOWANIE NIE PROPAGUJE SIĘ** (import tylko dodaje i nadpisuje) — do rozwiązania przy auto-synchronizacji (Faza 2/3).
- ⚠️ **`cryptography` + PyInstaller** działa BEZ własnego hooka (`_rust.abi3.so` wchodzi samo) — zweryfikowane TYLKO na Linuksie; Mac/Windows do potwierdzenia przy najbliższym buildzie CI.

---

## Inne otwarte TODO

- [ ] **XSS (niski prio):** `web_terminal._show_failure_page` — surowy f-string z `reason`.
- [ ] **Wykrywanie ZEPSUTEGO `claude`:** `claude_runnable()` testuje obecność, nie uruchamialność → przy zepsutej binarce npm apka utyka i pokazuje surowy błąd Windows. Dodać wykrycie + podpowiedź natywnej reinstalacji.
- [ ] **Sprzątanie po aktualizacji:** `update_manager` zbiera stare AppImage w `updates/` (2,5 GB sprzątnięte ręcznie 2026-07-13) + martwe `*-debug.log`. → `todo-sprzatanie-starych-plikow.md`
- [ ] **BUG Mac — CRASH QtWebEngine po wybudzeniu** (nie „ostrzeżenie"!): zrzut usera z 1.0.25 = `Crashed Thread 0 CrBrowserMain`, `EXC_BAD_ACCESS`, **Time Since Wake 88 s**. Na 1.0.26 wystąpił RAZ, po restarcie nie wraca → niski priorytet. Nasz `crash-logs/` łapie tylko crash `claude`, NIE QtWebEngine. Kierunek naprawy (NIE wdrażać, tylko gdyby się nasiliło): flagi QtWebEngine na macOS lub reinicjalizacja WebTerminala na sygnał wybudzenia. → `mac-qtwebengine-crash-po-snie.md`
- [ ] **Mac — Claude Code przez npm: 401 + „Auto-update failed: no write permission to npm prefix"** (NIE bug naszej apki; macowy odpowiednik problemu z Windows). `/login` odblokowuje agenta; auto-update naprawić osobno (natywny instalator zamiast npm).
- [ ] **Redesign — do rozważenia:** własna belka tytułowa (świadomie pominięta — ryzyko Wayland/macOS); okno ustawień jako jeden modal z bocznym menu (to zmiana UKŁADU, poza zakresem redesignu). Makieta żyje w repo: `design/makieta-2026-07-09/` (`settingsTabs` = niewdrożony ekran); zrzuty POMINIĘTE, bo repo jest publiczne (pełny eksport: `~/Projekty/makiety/vca-redesign-2026-07-09.zip`). ⚠️ `.gitignore` ma `*.zip` — kolejny eksport rozpakuj do `design/`, nie commituj archiwum.
- [ ] **Strona/branding (decyzje usera):** dane firmy `[forma prawna/adres/NIP]` w polityce+licencji (PL+EN), zakup domeny, geolokalizacja GeoJS w polityce, link „Instrukcje" (teraz `#`) → `instrukcja-instalacja.html`, przegląd prawny, przepięcie ze stagingu na docelową domenę.
- [ ] Test zadania „nodecli" instalatora na świeżym Windows (auto-instalacja Node+Claude Code).
- [ ] Kolejne języki: słownik w `UI_TRANSLATIONS` (parytet!) + `SUPPORTED_LANGUAGES` + `detect_system_language` + pliki `-xx.html` + dropdown.
- [ ] Potwierdzić kliencki self-update spakowanego AppImage.

## Sygnały PyQt (AgentTab)

`message_sent(str)` · `terminal_output(object)` · `status_changed(str)` · `request_tts(str)` · `request_dictation(bool)` · `request_pause` · `splitter_changed(list)`.

## Częste problemy

| Problem | Rozwiązanie |
|---------|-------------|
| QTermWidget not found | `pip install wheels/qtermwidget-*.whl` |
| TTS nie działa | internet (edge-tts); `~/.vibe-coding-assistant/tts.log` |
| STT nie nagrywa | `GROQ_API_KEY`, mikrofon |
| `claude` not recognized | Node + `npm i -g @anthropic-ai/claude-code` + restart |
| `claude.exe` „niezgodny z Windows"/16-bit | Zła binarka npm (bug CC 2.1.113–114) — `npm uninstall -g` + `irm https://claude.ai/install.ps1\|iex`; w apce komenda = `claude` |
| Apka nie startuje | `python3 -m py_compile src/main.py` |
| Zawieszanie przy 2+ zakładkach | RAM — patrz „Pamięć/RAM" |
| Kopiowanie/odczyt zaznaczenia zwraca pustkę | Claude (TUI) przejmuje mysz → zaznaczaj z **Shift** (nie błąd kodu) |

## PODŁĄCZENIE DO AI MANAGERA — ✅ DOMKNIĘTE

Rozmowa z Claude idzie przez CLI (nie HTTP) → bramka jej nie łapie i nie musi; zużycie liczy osobno kolektor Claude Code AI Managera z lokalnych `.jsonl`.
**STT (dyktowanie) na bramce** (potwierdzone 2026-07-13): `POST https://ai.srv1251441.hstgr.cloud/v1/audio/transcriptions`, `Authorization: Bearer aim-…` (klucz aplikacji **„VCA" (id=3)**), model z prefiksem `groq/…`; język auto = NIE wysyłaj pola `language`; kody: `401` zły klucz · `429` limit · `503` brak wolnego konta. → `stt-bramka-ai-manager.md`
⚠️ NIE mylić z osobną apką „Voice Assistant" (repo `voice-assistant`) — inny projekt, inny klucz.
