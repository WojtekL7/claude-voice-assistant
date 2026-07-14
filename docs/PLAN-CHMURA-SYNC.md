# Plan: Synchronizacja agentów przez chmurę (Google Drive → potem inne)

*Wersja robocza planu — 2026-07-14. Kod jeszcze NIE zaczęty. Kierunek zatwierdzony przez usera 2026-07-03.*

---

## 1. Po co to robimy (prostym językiem)

Dziś agenci (ich ustawienia, pamięć, przypisane projekty) żyją **tylko na jednym komputerze**.
Cel: **zaloguj się do chmury na dowolnym urządzeniu → pobierz agenta → pracuj dalej tam, gdzie skończyłeś.**
Nowy komputer ze świeżym VCA = po zalogowaniu wszystko wgrywa się samo.

Start: **Google Drive**. Później iCloud / OneDrive / inne (dlatego od początku robimy wspólną „wtyczkę" `CloudProvider`,
żeby dołożenie kolejnej chmury było łatwe).

---

## 2. Kluczowa decyzja architektoniczna: „mózg" osobno od „kodu"

Agent składa się z dwóch bardzo różnych rzeczy:

| | „MÓZG" agenta | „KOD" projektów |
|---|---|---|
| Co to | ustawienia + pamięć + które skille/MCP | katalogi projektów (pliki źródłowe) |
| Rozmiar | malutki (kilobajty) | ogromny (setki MB–GB: `node_modules`, `venv`, `.git`, AppImage) |
| Gdzie już jest | nigdzie — tylko lokalnie | **w GitHub** (większość projektów usera) |
| Ryzyko sekretów | pod kontrolą (filtrujemy) | wysokie (`.env`, `.secrets`, tokeny w katalogach) |

**Wniosek:** „mózg" → chmura (Drive). „Kod" → NIE kopiujemy do Drive, tylko zapamiętujemy `git remote + branch`
i na nowym komputerze proponujemy `git clone`. To omija 4 pułapki: wyciek sekretów, gigabajty w chmurze,
dublowanie gita, konflikty przy dwukierunkowym sync katalogów, które agent aktywnie zapisuje.

> ⚠️ **Uwaga do wcześniejszych wyborów usera** (AskUserQuestion 2026-07-02): padło „automatyczna ciągła
> dwukierunkowa synchronizacja + całe katalogi projektów". To jest **Faza 3** (najtrudniejsza, z filtrami i
> wykrywaniem konfliktów). Zaczynamy od bezpiecznego fundamentu (Faza 1), a pełny auto-sync dokładamy później,
> gdy fundament będzie pewny. **Ten kompromis wymaga potwierdzenia** (patrz sekcja 7).

---

## 3. Co dokładnie wchodzi w „paczkę mózgu" agenta (zweryfikowane w kodzie 2026-07-14)

**DO chmury (portable):**
- `agents.json` — wpisy agentów (pola: `id, name, working_directory, memory_files[], auto_start,
  send_memory_on_start, model, icon{}, tab_color, tts_voice, splitter_sizes`).
  - `working_directory` i `memory_files[]` to ścieżki BEZWZGLĘDNE → na imporcie **przemapowujemy** (pytamy o katalog projektów).
- **treść plików pamięci** (`memory_files` → `CLAUDE-*.md`) — bundlujemy zawartość (mały, cenny „mózg").
- per-agent ustawienia **które skille/MCP włączone** (`agent_skills_settings.py`, `agent_mcp_settings.py`).
- `memory_projects.json`, `quick_actions.json`.
- z `config.json` tylko **przenośne** pola: `language, auto_read, skin_version, skin_colors, skin_icons,
  auto_check_updates, dictation_reminder_dismissed`.

**NIGDY do chmury (sekrety):**
- `config.json`: `groq_api_key`, `anthropic_api_key`.
- `~/.claude/.credentials.json` (login Claude Code).
- (Faza 3) w katalogach projektów: `.env`, `.secrets`, tokeny.

**Pomijamy (lokalne dla urządzenia — nie ma sensu synchronizować):**
- `config.json`: `claude_command` (ścieżka lokalna), `last_active_agent_id`, `auto_run_claude`.
- `device.json`, `license.json` (tożsamość urządzenia / licencja).
- katalogi projektów (→ git, nie Drive).

**Skille (`~/.claude/skills/<name>/`) — decyzja do potwierdzenia:** w Fazie 1 bundlujemy tylko **listę
używanych skilli + ustawienia gatingu**; samych definicji skilli (katalogi Claude Code) NIE wysyłamy
(to domena Claude Code). Na imporcie: jeśli skill nie istnieje lokalnie → ostrzeżenie „zainstaluj skill X".

---

## 4. FAZA 1 — fundament + „mózg" (rozpiska techniczna, plik po pliku)

Styl projektu: czysty `requests` (jest, 2.32.5), zero ciężkich bibliotek Google. Klient publiczny (Desktop OAuth),
loopback `http://localhost:PORT` + PKCE.

**Nowe pliki:**
- `src/core/cloud/__init__.py`
- `src/core/cloud/cloud_provider.py` — interfejs `CloudProvider` (abstrakcja): `auth()`, `upload(name, bytes)`,
  `download(name) -> bytes`, `list()`, `delete(name)`. Pod przyszłe iCloud/OneDrive.
- `src/core/cloud/google_drive.py` — implementacja `CloudProvider`:
  - OAuth 2.0 Desktop: otwórz przeglądarkę na zgodę → lokalny serwer loopback łapie `code` → wymiana na
    `access_token`+`refresh_token` (PKCE). Token (refresh) zapisany lokalnie w `~/.vibe-coding-assistant/`
    (NIE w paczce mózgu, NIE do repo).
  - Wywołania Drive REST (`https://www.googleapis.com/upload/drive/v3/files`, `.../drive/v3/files`) czystym `requests`.
  - Folder aplikacji w Drive (np. `appDataFolder` — ukryty, per-użytkownik) na paczki.
- `src/core/cloud/agent_bundle.py` — eksport/import „paczki mózgu":
  - `export_bundle() -> bytes` (zip): manifest JSON (agenci + przenośne config + per-agent skille/MCP +
    `git remote/branch` per projekt) + treść plików pamięci. **Twardy filtr sekretów** (whitelist pól config,
    nigdy `*_api_key`).
  - `import_bundle(bytes, project_root)`: odtwórz agentów, **przemapuj ścieżki** na `project_root`, dla projektów
    z zapisanym remote → zaproponuj `git clone`, skille → sprawdź obecność, ostrzeż o brakach.

**GUI:**
- Ekran/sekcja „Chmura": login (Połącz z Google Drive), lista agentów w chmurze, przyciski **Wyślij do chmury**
  / **Pobierz z chmury**. (Wygląd — patrz sekcja 6: makieta Cloud Design.)
- Kreator importu na nowym komputerze: zapytaj o katalog projektów → przemapuj → `git clone` → wpisz sekrety raz.

**i18n:** wszystkie nowe napisy przez `config.t()` z parytetem PL/EN (reguła projektu).

**Testy Fazy 1 (bez prawdziwego Drive, żeby dało się na Linuksie):**
- `export_bundle` → `import_bundle` w tę i z powrotem (round-trip) odtwarza agentów 1:1.
- **filtr sekretów**: żaden `*_api_key` ani `.credentials.json` NIE trafia do paczki (asercja na bajtach zipa).
- przemapowanie ścieżek: `working_directory`/`memory_files` wskazują nowy `project_root`.
- `CloudProvider` zamockowany (fake in-memory) → upload/list/download bez sieci.
- OAuth loopback: token wymieniany na atrapie serwera.

---

## 5. FAZA 2 i 3 (skrót — po Fazie 1)

- **Faza 2 — automatyzacja:** auto-wysyłka paczki mózgu przy zmianie (debounce) lub cyklicznie; wskaźnik „zsynchronizowano".
- **Faza 3 — pełny dwukierunkowy sync + kolejne chmury:** wykrywanie konfliktów (znacznik wersji/urządzenia),
  kolejni dostawcy (`CloudProvider`), opcjonalnie katalogi projektów **Z FILTRAMI** (pomiń
  `node_modules/.git/venv/dist/.env/.secrets`). To tu realizujemy pierwotne „ciągłe dwukierunkowe".

---

## 6. Prerekwizyt: klient OAuth „Aplikacja desktopowa" (jednorazowo, poprowadzę usera)

Jak przy GSC w SEO Managerze, ale typ = **Aplikacja desktopowa**:
1. Google Cloud Console → projekt (można reużyć istniejący).
2. Włącz **Google Drive API**.
3. „Platforma uwierzytelniania" → Odbiorcy = **Zewnętrzny** → dane kontaktowe → dodaj siebie jako **użytkownika testowego**.
4. Utwórz klienta OAuth typu **Aplikacja desktopowa** → pobierz `client_id` (+ `client_secret`; przy desktop
   nie musi być tajny, bo używamy PKCE).
5. Sekret NIE do czatu: user pobiera JSON, ja czytam z dysku → zapis lokalny → usuwam plik.

---

## 7. Decyzje do potwierdzenia PRZED kodem

1. **Kolejność:** zaczynamy od bezpiecznej Fazy 1 (mózg bez sekretów, git clone dla kodu), a pełny auto-sync +
   katalogi projektów to Faza 3? (rekomendacja: TAK)
2. **Makieta Cloud Design:** robimy UI tej funkcji najpierw jako makietę w Cloud Design (`.dc.html`), czy buduję
   od razu prosty ekran w Qt? I czy makieta to tylko ekran „Chmura", czy szerszy redesign?
3. **Backend najpierw czy UI najpierw:** mogę zbudować i przetestować cały „silnik" (paczka + filtr sekretów +
   round-trip) BEZ Drive i bez UI — to bezpieczny, testowalny start, niezależny od makiety. Potem OAuth, potem UI.
4. **Skille w paczce:** Faza 1 = tylko lista + gating (bez wysyłania definicji skilli)? (rekomendacja: TAK)

---

## 8. Ryzyka i jak je tniemy

| Ryzyko | Mitygacja |
|---|---|
| Wyciek sekretów do chmury | whitelist pól config; twardy filtr `*_api_key`; test na bajtach paczki; katalogi projektów dopiero Faza 3 z filtrami |
| Gigabajty w Drive | „mózg" (KB) w Drive; kod przez `git clone`, nie kopiowany |
| Konflikty dwukierunkowe | Faza 1 = ręczne Wyślij/Pobierz (bez auto); dwukierunkowość z wykrywaniem konfliktów dopiero Faza 3 |
| Ścieżki bezwzględne między urządzeniami | przemapowanie na imporcie (pytanie o katalog projektów) |
| Uwiązanie do Google | interfejs `CloudProvider` od początku |
