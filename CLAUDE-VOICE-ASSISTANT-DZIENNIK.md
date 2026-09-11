# DZIENNIK SESJI — claude-voice-assistant

Zapis PRACY („co robiliśmy dnia X"), najnowsze NA GÓRZE. **NIE czytany na starcie sesji.**

⛔ **Nauki i reguły tu NIE trafiają** — one idą do `CLAUDE-VOICE-ASSISTANT.md` (żywa pamięć)
albo do plików wspólnych. Dziennik odpowiada na pytanie „co się działo w tym projekcie
w zeszły czwartek", na które `git log` odpowiada zbyt drobno. Wpis: 3–8 linii.

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
