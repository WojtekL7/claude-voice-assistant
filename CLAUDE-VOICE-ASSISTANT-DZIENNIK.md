# DZIENNIK SESJI — claude-voice-assistant

Zapis PRACY („co robiliśmy dnia X"), najnowsze NA GÓRZE. **NIE czytany na starcie sesji.**

⛔ **Nauki i reguły tu NIE trafiają** — one idą do `CLAUDE-VOICE-ASSISTANT.md` (żywa pamięć)
albo do plików wspólnych. Dziennik odpowiada na pytanie „co się działo w tym projekcie
w zeszły czwartek", na które `git log` odpowiada zbyt drobno. Wpis: 3–8 linii.

---

## 2026-09-25

- Start sesji: wczytana pamięć, lista „co wisi” zmierzona (wykryty zombi: poprawka crashu Maca JEST w 1.0.29).
- ✅ Test dyktowania na qwen potwierdzony przez właściciela: 9 dyktowań, 8 poprawek ≤1,0 s, 1 odrzucona przez bezpiecznik słów, 0 timeoutów (`913c26b`).
- ✅ Test emotikon przyklejonych do słowa potwierdzony: zero `:(` w lektorze, kontrola odwrotna czytana (`d526268`).
- Push na GitHuba raz zawisł (port 22 chwilowo nieosiągalny) — ponowienie przeszło.
- Zostaje: #4 zakładka bez `claude` (decyzja), #7 lupa w skórce, #11 sprzątanie diagnostyki 🔊, konsolidacja pliku pamięci (429 > 350).

## 2026-09-24

- Mail „Opus 5.5": model już w apce (katalog sam pobrał); naprawione ceny przy starcie, wartości awaryjne, podpis domyślnego wysiłku w oknie (`6f42268`, potwierdzone przez właściciela).
- Dyktowanie ~12 s: przyczyna = awaria Gemini u Google od 21.09 (baza bramki). Poprawianie przeniesione na qwen u Groqa + bezpiecznik słów + limit 5 s (`7e91775`, NIEPRZETESTOWANE u usera).
- Zadanie AI Managera `fix-transcript` wykonywało polecenia (6/8) — zwrotka do nich (`401dd7c` w ich repo); odpowiedzieli tego samego dnia i zdjęli doklejany zakaz (`e69a8a8`).
- Dwie bramki (`test-detected-model`, `test-hooks-resume`) czerwone przez premierę modelu — poprawione na identyfikator z katalogu.
- Zostaje: test dyktowania po restarcie; decyzja o powrocie na `task/fix-transcript`; plik pamięci 417+ linii > budżet 350 (konsolidacja w osobnej sesji).

## 2026-09-18

- **Tempo czytania POTWIERDZONE przez właściciela na żywo** („tempo działa") — pozycja wisiała od 17.09 jako `NIEPRZETESTOWANE`; status przestawiony w żywej pamięci, lista 7 punktów testowych usunięta jako wykonana.
- **Naprawiony lektor czytający emotikony na głos** (`27955e3`). Zgłoszenie: „czyta emotikon smutek, kiedy widzi nawias i dwukropek". Czyścik istniał i działał — dziurą był jego strażnik, przepuszczający emotikonę PRZYKLEJONĄ do słowa (`Gotowe:(`). Doszedł drugi, wąski wzorzec + `:*` wolnostojące; `8)` świadomie NIE dodane (139 kolizji z „art. 28)").
- **Dołożona czujka `_audit_emoticons`** pisząca do `tts.log` — bo źródła NIE znaleziono w dziennikach (0 na 8162 wypowiedziach), więc może leżeć poza nimi (ekran, zaznaczenie). Przy nawrocie czyta się log, nie zgaduje.
- Nowe narzędzia: `tools/test-emoticon-speech.py` (84/84) + `tools/sabotaz-emoticon-speech.py` (12/12 wykrytych). Regresja projektu **29/29**.
- Pamięć wspólna: 5 nauk do `CLAUDE-COMMON.md` (2), `-TESTY.md`, `-DESKTOP.md`, `-PROGRAMOWANIE.md` (`8541dd7` w repo `claude-memory`).
- Commity: `27955e3` (poprawka), `8337436` (pamięć projektu). ⏳ **Zostaje: test emotikon u właściciela 19.09** (wymaga restartu bety — 18.09 pracował na programie).

---

## 2026-09-17

- **Nowa funkcja na prośbę właściciela: tempo czytania na dolnym pasku** — jeden przycisk
  z napisem, klik przeskakuje 1× → 1,25× → 1,5× → 2× i wraca. Decyzja właściciela: bez
  spowolnienia 0,5×. Połowa mechanizmu leżała w kodzie od zawsze (`set_rate` → edge-tts)
  i nikt jej nie wołał, więc zmiana to raptem 214 linii w `src/`. Commit `720339d`,
  oznaczony **NIEPRZETESTOWANE** — właściciel nie mógł testować, sprawdza 18.09 przy pracy.
  Dowody: nowa bramka 24/24, sabotażysta 14/14 wykrytych, regresja 28/28.
- **Konsolidacja pamięci projektu do budżetu** (`c7d80b3`): 599 → 351 linii, 123 → 77 kB.
  Nic nie skasowane — powstały dwa pliki tematyczne (`-PULAPKI.md`, `-WYDANIA.md`),
  historia domknięta poszła do archiwum. Bramka złapała przy tym jedną pozycję OTWARTĄ,
  która wyjechała do archiwum razem z sekcją historyczną; wciągnięta z powrotem.
- **Nauki dnia poszły do pamięci wspólnej** (repo `claude-memory`, commity `b29e6fe`
  i `fa1f7cc`): Qt/`QApplication` i odśmiecacz, edge-tts i przejściowe `NoAudioReceived`,
  ślepa asercja na martwym kodzie, grep z wzorcem wieloliniowym. Przy okazji naprawione
  narzędzie `narzedzia/przenies-sekcje.py`, które generowało nagłówek kłamiący o pochodzeniu.
- ⚠️ **Równolegle inny agent odchudzał `CLAUDE-COMMON.md`** (1558 → 735 linii). Przez część
  sesji jego praca była niezacommitowana, więc wpisy do plików wspólnych czekały; po jego
  commitach (`31e73ad`, `56b05fb`) kotwice pobrano świeżo — dwa pliki docelowe rano
  jeszcze nie istniały.

## 2026-09-15

- **Rano: odpowiedź dla agenta AI Manager na pytanie o limity czasu przy dyktowaniu.** W kodzie
  nic nie ruszaliśmy — same pomiary: 12 s limitu na jedną odpowiedź, zero ponowień, najdłuższe
  realne nagranie 364,5 s. Pełna treść w `docs/ZWROTKA-AI-MANAGER-LIMITY-CZASU.md`, doręczone
  do ich pliku pamięci. Commity: `d63c5d2` (u nas), `449f9a5` (u nich).
- **Przy okazji znalezisko, które zmienia ICH rachunek:** ich licznik nie widzi wysyłki pliku —
  to samo nagranie 364,5 s u nich zmierzyło się na 2,6 s, u nas na 7,6 s.
- **Po południu: zgłoszenie właściciela o wygląd przycisków paska** (fioletowe tło zamiast
  fioletowej ikony; krzyżyk nieświecący się na czerwono). Obie rzeczy miały jedną przyczynę —
  sygnał siedział w tle i ramce, a nie w ikonie; `color:` w arkuszu nie dotyczy obrazka `QIcon`,
  a błysk ramki przegrywał z najechaniem myszą. Commit `8d5f6a8`, oznaczony jako nieprzetestowany.
- **Przy okazji naprawione narzędzie sabotażowe:** cztery warianty były martwe od 14.09 przez
  zdublowane klucze w słowniku (Python zostawia ostatni, bez ostrzeżenia); dwie kotwice zgniły
  od moich własnych zmian w tej samej sesji.
- Stan na koniec dnia: 4 commity (2 repozytoria), wszystko wypchnięte i sprawdzone dowodem,
  48/48 na bramce paska, 22/22 warianty sabotażu wykryte, 27/27 bramek projektu zielonych.
  **Testy u właściciela umówione na 2026-09-16** — beta wymaga restartu.

---

## 2026-09-14

- **Cztery etapy przenoszenia nowości Claude Code do VCA, z maila „This week in Claude Code" (12.09).**
  Właściciel poprosił najpierw o RAPORT z maila, potem kazał robić etapy po kolei; etap 5 (panel `/diff`)
  świadomie odwołany jako niepotrzebny. Commity: `b24bb48`, `61c6ec2`, `84e6ddc`, `3943b38`.
- **Po drodze wyszła najdroższa rzecz dnia:** czujka katalogu modeli nie działała od 27 dni i o tym
  milczała — apka pokazywała „Fable 5", uruchamiając dwa razy droższy Fable 5.1, a dwaj agenci
  właściciela już na nim chodzili. Znalezione przy okazji, nie było w zgłoszeniu.
- **Zmiana wyglądu na życzenie** (`261a7d0`): wzmocnione dwa sygnały stanu (wybrana zakładka, panel
  nieaktywnego okna). Właściciel dostał podgląd „teraz vs propozycja" jako obrazek i zdecydował
  PRZED wdrożeniem — dzięki temu nie musiał restartować bety, żeby ocenić.
- **Nic nie zostało przetestowane u właściciela** — pracował na becie przez cały dzień i nie mógł jej
  restartować. Testy umówione na 2026-09-15, lista 12 punktów w żywym pliku pamięci.
- Stan na koniec dnia: 5 commitów kodu + 2 pamięci, wszystko wypchnięte, 27 bramek zielonych,
  repo czyste. Do COMMON poszło 6 nauk (zatwierdzone przez właściciela).

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
