# CLAUDE-VOICE-ASSISTANT — WYDANIA I DYSTRYBUCJA (plik tematyczny)

Wydzielone 2026-09-17 z `CLAUDE-VOICE-ASSISTANT.md` (pamięć projektu), żeby zmieścić ją w budżecie
~350 linii. ⛔ **NIE czytaj tego na starcie sesji** — czytaj, ZANIM wydasz wersję albo ruszysz
kanał aktualizacji: runbook wydania (tag → Actions → paczki → appcast), self-update Linuksa
(AppImage), strony instrukcji na VPS. Kolejność kroków i pułapki uploadu są tu ZMIERZONE.

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

