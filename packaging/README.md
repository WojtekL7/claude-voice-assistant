# Packaging & Release — Claude Voice Assistant

Konfiguracja budowania, pakowania, podpisu i auto-aktualizacji.
Wieloplatformowo: **Linux**, **macOS** (najpierw), **Windows** (w przyszłości).

> Uwaga: katalogi `build/` i `dist/` to **tymczasowe wyjścia PyInstallera**
> (są w `.gitignore`). Wszystko, co ma być w repo, trzymamy TUTAJ, w `packaging/`.

> Stan na Etap **M1**: tu są na razie *gniazda na przyszłość* (szkielet + przykłady,
> oraz istniejący `linux/build.sh`). Skrypt macOS (`.app`/`.dmg`) powstanie w **M4**,
> a updater + feed aktualizacji w **M3**.

---

## Mapa etapów

| Etap | Zakres | Status |
|------|--------|--------|
| M1 | Fundament wieloplatformowy (`src/core/platform_utils.py`, `APP_VERSION`, gniazda) | ✅ |
| M2 | Terminal xterm.js + QtWebEngine + PTY (wspólny dla wszystkich OS) | — |
| M3 | Auto-aktualizacja: `appcast.json` na VPS + updater w aplikacji | — |
| M4 | Pakowanie macOS (`.app`/`.dmg`), Info.plist, **opcjonalny** podpis | — |
| (przyszłość) | Pakowanie Windows (`.exe`/instalator) + podpis Authenticode | — |

## Struktura

```
packaging/
├── README.md
├── signing.conf.example   # szablon podpisu (skopiuj → signing.conf, poza gitem)
├── appcast.example.json   # format feedu aktualizacji (docelowy)
├── .gitignore             # chroni signing.conf i sekrety
├── linux/build.sh         # build Linux (PyInstaller) — istniejący
├── macos/                 # M4: skrypt .app/.dmg + Info.plist
└── windows/               # przyszłość: skrypt .exe/instalator
```

## Gniazdo na PODPIS (na razie wyłączone)

Podpisywanie to **osobny krok po zbudowaniu**, sterowany przez `packaging/signing.conf`
(skopiuj z `signing.conf.example`). Plik jest **poza gitem** (sekrety). Gdy
pusty/nieobecny → build **niepodpisany** (na macOS pierwsze uruchomienie:
prawy klik → „Otwórz").

- **macOS:** Developer ID Application + notaryzacja (`notarytool`) → brak ostrzeżeń.
- **Windows (przyszłość):** certyfikat Authenticode (`signtool`).

Dodanie podpisu później = wypełnienie jednego pliku, **bez zmian w kodzie aplikacji**.

## Auto-aktualizacja

Aplikacja porównuje `config.APP_VERSION` z wpisem dla swojej platformy w
`appcast.json` na VPS (`srv1251441.hstgr.cloud`). Identyfikator platformy:
`core.platform_utils.update_platform_id()` → `macos-arm64` / `macos-x64` /
`linux-x64` / `windows-x64`. Format: patrz `appcast.example.json`.
