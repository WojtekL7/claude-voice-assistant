# DZIENNIK SESJI — claude-voice-assistant

Zapis PRACY („co robiliśmy dnia X"), najnowsze NA GÓRZE. **NIE czytany na starcie sesji.**

⛔ **Nauki i reguły tu NIE trafiają** — one idą do `CLAUDE-VOICE-ASSISTANT.md` (żywa pamięć)
albo do plików wspólnych. Dziennik odpowiada na pytanie „co się działo w tym projekcie
w zeszły czwartek", na które `git log` odpowiada zbyt drobno. Wpis: 3–8 linii.

---

## 2026-09-12

- **Dyktowanie przepięte na zadanie `task/transcribe`** (`9b5729b`) — wcześniej wołaliśmy model po
  nazwie, więc awaria Groqa zostawiała nas bez zejścia. Dowód ze skutku z żywej bramki + kontrola
  przeciwna (`task/nie-istnieje` → 400). Restart bety wstrzymany na pół dnia, bo w ówczesnym
  układzie łańcucha przepięcie byłoby regresją jakości; AI Manager przestawił kolejność
  (pełny `whisper-large-v3` na czele) i wieczorem domknął też swoje ryzyko kod↔baza.
- **Prośba do AI Managera dostarczona kontraktem** (`35ae1bd` w ich repo) + zwrotka u nas
  (`docs/ZWROTKA-AI-MANAGER-TRANSCRIBE.md`). Zgłoszone im przy okazji, że `STT_FIX_MODEL` woła po
  nazwie modelu ŚWIADOMIE — przyjęli to jako decyzję, nie dług.
- **Trzy poprawki paska przycisków na zgłoszenie właściciela:** szybkie akcje wyglądają i zachowują
  się jak reszta (`9cc72e9`), zielony błysk „Kopiuj" ze wspólnego malarza (`528dc9f`), przycisk
  świeci akcentem przez CAŁY czas używania (`dde1164`), „Wyczyść pole" mruga na czerwono (`002183a`).
  Bramka paska 18 → 37 asercji, nowy `tools/sabotaz-bottom-bar.py` (15 wariantów, każdy wykryty).
- **Pamięć:** `87d6e01` (status przepięcia + pułapka selektora QSS), wpisy zamykające dzień.
- ⏳ **ZOSTAJE:** wszystko powyżej jest NIEPRZETESTOWANE u właściciela — testy jutro, po otwarciu
  nowej bety. Plik pamięci projektu ma 490 linii przy budżecie ~350 (odchudzanie = osobne zadanie).

---

## 2026-09-11

**Temat:** zgłoszenie właściciela „dziurawe dyktowanie, tekst nie jest tym, co dyktuję"
(przykład: zakładka AI Manager, dużo ręcznych poprawek).

- **Diagnoza pomiarem** całej drogi dyktowania — wyszło, że droga tekstu w apce jest ZDROWA
  (328/328 nagrań bez zgubionej ramki, 325/325 trafień w zakładkę, długości zgodne).
  Obalone pięć hipotez, każda pomiarem: `language=pl`, `prompt`, `temperature`,
  ciche wzmocnienie mikrofonu (21%), `whisper-large-v3-turbo`.
- **Wdrożone trzy kroki (A/B/C):** pomiar kursora i zaznaczenia w `dictation.log` ·
  ochrona przed kasowaniem zaznaczonego tekstu · poprawianie transkrypcji przez bramkę
  AI Managera (model wybrany pomiarem: `gemini-3.5-flash-lite`, 1,0–1,5 s).
- **Bramki:** nowe `tools/test-dictation-fix.py` (30/30) i `tools/sabotaz-dictation-fix.py`
  (11 wariantów, wszystkie wykryte). Sabotaż znalazł 2 dziury w mojej własnej bramce —
  obie naprawione. Regresja: 24/24 bramek projektu zielone.
- **Decyzja właściciela:** checkboxa do wyłączania poprawiania w Ustawieniach NIE robimy.
- **Commity:** `f79b1da` (kod + bramki, oznaczony NIEPRZETESTOWANE u usera).

**Zostaje otwarte:** 7 testów po restarcie bety (właściciel na niej pracuje i nie mógł
zrestartować) oraz odczyt z `dictation.log`, czy ochrona zaznaczenia faktycznie się uruchamia.
