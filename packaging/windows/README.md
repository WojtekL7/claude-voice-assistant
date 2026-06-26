# Windows packaging

Wersja na Windows (64-bit). Terminal działa przez **ConPTY** (`pywinpty`),
pakowanie przez **PyInstaller** (onedir), instalator przez **Inno Setup**
(per-użytkownik → samo-aktualizacja bez UAC).

## Pliki
- `ClaudeVoiceAssistant.spec` — przepis PyInstallera (onedir, `.exe`, ikona `.ico`).
- `installer.iss` — skrypt Inno Setup (Setup.exe, skróty, samo-aktualizacja).
- `build-windows.ps1` — buduje wszystko: `.ico` → `.exe` → instalator.

## Budowanie
Tylko **na Windows** (jak `.dmg` tylko na macOS). W chmurze robi to
`.github/workflows/build-windows.yml` (runner `windows-latest`):
- ręcznie: Actions → „Build Windows app" → Run workflow,
- albo tag `vX.Y.Z` → build + Release z `Setup.exe`.

Lokalnie na Windows:
```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-windows.ps1
```
Wymaga: Python 3.12 na PATH + Inno Setup 6 (`choco install innosetup`).
Wynik: `dist\VibeCodingAssistant-Setup-<wersja>.exe`.

## Auto-aktualizacja
Pobrany `Setup.exe` jest URUCHAMIANY po cichu (`/VERYSILENT`) przez
`core/update_manager._windows_self_replace` — Inno (Restart Manager) podmienia
pliki działającej aplikacji i wznawia ją (sekcja `[Run]`). Wpis do feedu:
`make-appcast-entry.py ... --platform windows-x64`.

## Podpis (TODO)
Authenticode (certyfikat) usunie ekran SmartScreen „Windows chronił Twój
komputer". Na razie bez podpisu — przy pierwszym uruchomieniu: „Więcej
informacji → Uruchom mimo to".
