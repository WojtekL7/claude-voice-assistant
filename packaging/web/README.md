# Strona pobierania (landing page)

Prosta strona dla zwykłych użytkowników: wchodzą, klikają przycisk dla swojego
systemu, pobierają, instalują jak każdy program. Bez Terminala.

## Pliki

```
packaging/web/
├── index.html              # cała strona (jeden plik, samowystarczalny)
└── downloads/              # tu wgrywasz gotowe pliki do pobrania
    ├── VibeCodingAssistant-macos.dmg        (po zbudowaniu na Macu)
    ├── VibeCodingAssistant-linux.AppImage   (po zbudowaniu na Linuksie)
    └── VibeCodingAssistant-windows.exe       (w przyszłości — przycisk wyszarzony)
```

**Ważne:** przyciski na stronie wskazują DOKŁADNIE te nazwy plików powyżej.
Gdy zbudujesz aplikację, **zmień nazwę** pliku na tę z listy i wrzuć do
`downloads/`. (Albo zmień adres w `index.html` — szukaj `href="downloads/...`.)

## 🟢 LIVE — strona jest już opublikowana

**Adres:** **https://pobierz.srv1251441.hstgr.cloud** (HTTPS, certyfikat Let's Encrypt).

Hostowana na VPS `srv1251441.hstgr.cloud` jako osobny kontener nginx (NIE rusza
stacka n8n/CRM), routowany przez istniejący traefik:

```
/opt/cva-web/                      # na serwerze
├── docker-compose.yml             # izolowany kontener 'cva-web' (nginx:alpine)
└── html/
    ├── index.html                 # = ta strona
    └── downloads/                 # tu trafiają paczki do pobrania
```

- Kontener: `docker compose -f /opt/cva-web/docker-compose.yml up -d` (restart unless-stopped).
- Etykiety traefik: Host `pobierz.srv1251441.hstgr.cloud`, TLS `mytlschallenge`, sieć `n8n_default`.
- Cofnięcie: `cd /opt/cva-web && docker compose down` (usuwa tylko ten kontener).

### Aktualizacja strony / wgranie paczek (przez SSH)

```bash
# nowa wersja strony
scp packaging/web/index.html root@168.231.127.133:/opt/cva-web/html/index.html

# wgranie gotowej paczki (przykład — Mac); nazwa MUSI zgadzać się z linkiem w index.html
scp dist/VibeCodingAssistant-1.0.0-macos-arm64.dmg \
    root@168.231.127.133:/opt/cva-web/html/downloads/VibeCodingAssistant-macos.dmg
```
nginx serwuje na żywo — bez restartu kontenera.

## Jak obejrzeć stronę u siebie (bez serwera)

Kliknij dwukrotnie `index.html` — otworzy się w przeglądarce. Tak wygląda.

## Status przycisków

| System | Przycisk | Plik |
|--------|----------|------|
| macOS | aktywny | `downloads/VibeCodingAssistant-macos.dmg` |
| Linux | aktywny | `downloads/VibeCodingAssistant-linux.AppImage` |
| Windows | **wyszarzony** („Wkrótce") | — (włączymy, gdy powstanie `.exe`) |

Aby później **włączyć Windows**: w `index.html` znajdź `id="dl-windows"`,
zamień `<button class="btn disabled" disabled>` na link
`<a class="btn" href="downloads/VibeCodingAssistant-windows.exe" download>`.
