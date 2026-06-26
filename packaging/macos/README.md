# Pakowanie macOS (Etap M4)

Budowanie `.app`/`.dmg` Vibe Coding Assistant na **macOS** (Apple Silicon M1–M4
lub Intel). Z Linuksa się **nie da** — `.app` powstaje wyłącznie na Macu.

## Pliki tutaj

| Plik | Rola |
|------|------|
| `ClaudeVoiceAssistant.spec` | przepis PyInstallera (zasoby, ukryte importy, `Info.plist` z mikrofonem) |
| `entitlements.plist` | uprawnienia do **podpisu** (mikrofon + JIT dla QtWebEngine) — używane tylko gdy podpisujesz |
| `build-macos.sh` | jeden skrypt: środowisko → ikona → PyInstaller → `.dmg` → opcjonalny podpis/notaryzacja |
| `../make-appcast-entry.py` | generuje wpis do `appcast.json` (sha256 + rozmiar) — domyka auto-aktualizację |

---

## Wymagania na Macu (jednorazowo)

- **Python 3.12** (`brew install python@3.12` lub z python.org)
- **Xcode Command Line Tools** (`xcode-select --install`) — daje `codesign`, `hdiutil`, `sips`, `iconutil`
- Claude Code CLI zainstalowane (aplikacja go uruchamia; nie jest pakowany do `.app`)

---

## Build (niepodpisany — najprostszy)

```bash
cd /ścieżka/do/claude-voice-assistant
chmod +x packaging/macos/build-macos.sh
./packaging/macos/build-macos.sh
```

Wynik:
- `dist/Vibe Coding Assistant.app`
- `dist/ClaudeVoiceAssistant-<wersja>-macos-<arch>.dmg`

**Pierwsze uruchomienie niepodpisanej aplikacji:** Finder → prawy klik na aplikacji
→ **Otwórz** → potwierdź (Gatekeeper zapyta raz). Późniejsze uruchomienia normalnie.

> Aktualizacje pobrane przez wbudowany updater mają **zdejmowaną kwarantannę**
> automatycznie (`core/update_manager.py`), więc kolejne wersje będą „gładkie”.

---

## Build podpisany + notaryzacja (opcjonalnie, bez ostrzeżeń Gatekeepera)

Wymaga konta **Apple Developer**. Konfiguracja w `packaging/signing.conf`
(skopiuj z `packaging/signing.conf.example`; plik jest poza gitem):

```bash
MACOS_SIGN=true
MACOS_DEVELOPER_ID="Developer ID Application: Imię Nazwisko (TEAMID1234)"
MACOS_NOTARY_PROFILE="cva-notary"
```

Profil notaryzacji zapisz raz:
```bash
xcrun notarytool store-credentials "cva-notary" \
  --apple-id "twoj@apple.id" --team-id TEAMID1234 --password "app-specific-password"
```

Potem `./packaging/macos/build-macos.sh` sam podpisze (hardened runtime +
`entitlements.plist`) i znotaryzuje `.dmg`.

---

## Publikacja aktualizacji (domknięcie M3)

1. Zbuduj `.dmg` (wyżej).
2. Wygeneruj/zaktualizuj wpis w feedzie:
   ```bash
   python3 packaging/make-appcast-entry.py \
     "dist/ClaudeVoiceAssistant-1.0.0-macos-arm64.dmg" \
     --version 1.0.0 \
     --base-url https://srv1251441.hstgr.cloud/cva/ \
     --appcast packaging/appcast.json --merge
   ```
   (Powtórz dla `macos-x64`, `linux-x64`, `windows-x64`, jeśli budujesz wiele.)
3. Wgraj na VPS pod `https://srv1251441.hstgr.cloud/cva/`:
   - paczki (`.dmg`/`.tar.gz`/`.exe`),
   - `appcast.json`,
   - opcjonalnie notatki wydania pod `notes_url`.
4. Podbij `APP_VERSION` w `src/config.py` **przy następnym** wydaniu — to ono
   decyduje, czy klient zobaczy „dostępna nowa wersja”.

> **Podpis paczek (Ed25519)** jest opcjonalny i na razie wyłączony. Aby włączyć:
> wygeneruj parę kluczy, wstaw klucz publiczny (base64) do `config.UPDATE_PUBLIC_KEY`,
> a prywatny podawaj do generatora przez `--sign-key` (NIE commituj klucza).

---

## Najczęstsze problemy

| Objaw | Przyczyna / rozwiązanie |
|-------|--------------------------|
| „aplikacja uszkodzona / nie można otworzyć” | Niepodpisany build + kwarantanna z internetu. Prawy klik → Otwórz, albo `xattr -dr com.apple.quarantine "Vibe Coding Assistant.app"` |
| Pusty/biały terminal | QtWebEngine nie doszło do bundla — sprawdź, czy `PyQtWebEngine` jest w venv i czy spec ma `PyQt5.QtWebEngineWidgets` w `hiddenimports` |
| Brak ikony | `icon.icns` nie wygenerowane — sprawdź, czy `src/assets/icon.png` istnieje (skrypt robi `.icns` przez `sips`/`iconutil`) |
| Mikrofon nie działa | Brak zgody systemowej — System Settings → Privacy → Microphone; w `.app` musi być `NSMicrophoneUsageDescription` (jest w spec) |
| Crash QtWebEngine po podpisie | Brakuje entitlements `allow-jit` / `allow-unsigned-executable-memory` — są w `entitlements.plist` |
