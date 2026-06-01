# Strona pobierania (landing page)

Prosta strona dla zwykłych użytkowników: wchodzą, klikają przycisk dla swojego
systemu, pobierają, instalują jak każdy program. Bez Terminala.

## Pliki

```
packaging/web/
├── index.html              # cała strona (jeden plik, samowystarczalny)
└── downloads/              # tu wgrywasz gotowe pliki do pobrania
    ├── ClaudeVoiceAssistant-macos.dmg        (po zbudowaniu na Macu)
    ├── ClaudeVoiceAssistant-linux.AppImage   (po zbudowaniu na Linuksie)
    └── ClaudeVoiceAssistant-windows.exe       (w przyszłości — przycisk wyszarzony)
```

**Ważne:** przyciski na stronie wskazują DOKŁADNIE te nazwy plików powyżej.
Gdy zbudujesz aplikację, **zmień nazwę** pliku na tę z listy i wrzuć do
`downloads/`. (Albo zmień adres w `index.html` — szukaj `href="downloads/...`.)

## Jak obejrzeć stronę u siebie (bez serwera)

Kliknij dwukrotnie `index.html` — otworzy się w przeglądarce. Tak wygląda.

## Jak wystawić ją w internecie (na VPS)

Strona to jeden plik + folder `downloads/`. Wgrywasz oba na serwer
`srv1251441.hstgr.cloud` pod publiczny katalog, np. `/cva/`:

```
https://srv1251441.hstgr.cloud/cva/index.html   ← strona
https://srv1251441.hstgr.cloud/cva/downloads/   ← pliki do pobrania
```

Adresy w `index.html` są **względne** (`downloads/...`), więc strona działa
niezależnie od tego, w jakim katalogu ją położysz.

## Status przycisków

| System | Przycisk | Plik |
|--------|----------|------|
| macOS | aktywny | `downloads/ClaudeVoiceAssistant-macos.dmg` |
| Linux | aktywny | `downloads/ClaudeVoiceAssistant-linux.AppImage` |
| Windows | **wyszarzony** („Wkrótce") | — (włączymy, gdy powstanie `.exe`) |

Aby później **włączyć Windows**: w `index.html` znajdź `id="dl-windows"`,
zamień `<button class="btn disabled" disabled>` na link
`<a class="btn" href="downloads/ClaudeVoiceAssistant-windows.exe" download>`.
