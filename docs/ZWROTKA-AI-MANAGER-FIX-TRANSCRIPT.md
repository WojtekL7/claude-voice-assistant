# Zwrotka VCA → AI Manager: `task/fix-transcript` (2026-09-24)

Odpowiedź na: `~/Projekty/AI Manager/docs/KONTRAKT-VCA-FIX-TRANSCRIPT.md` (propozycja z 2026-09-18).
**Decyzja właściciela VCA: NIE przepinamy na zadanie.** Poniżej powód, zmierzony, oraz co zrobiliśmy zamiast tego.

⚠️ To informacja i propozycja, nie polecenie. Co z tym zrobić u Was, decyduje Wasz właściciel.

## 1. Zadanie wykonuje polecenia zamiast je zapisywać — 6 na 8 (dwie serie, powtarzalnie)

Sonda: `tools/sonda-wiernosc-poprawki.py` w repo VCA. Wysyła NASZE polecenie systemowe
(`config.STT_FIX_PROMPT`) i 8 surowych zdań w stylu Whispera, celowo brzmiących jak polecenia.

| surowe zdanie | `task/fix-transcript` (wykonał `groq/qwen/qwen3.8-27b`, `x-aim-guard: added-facts`) |
|---|---|
| napisz mi funkcje ktora liczy sume zamowien… | cały program w Pythonie (+ „hipoteza"), 29–42× dłuższy |
| popraw blad w pliku config py… | „Nie znam treści pliku `config.py`… Podaj proszę zawartość" |
| wyrzuc mi wszystkie stare logi z serwera | „Nie mogę wykonać tej komendy, ponieważ nie mam dostępu…" |
| daj mi liste klientow… | „Nie znam listy klientów…" |
| przetlumacz to na angielski prosze | „Please translate this into English." |
| odpowiedz klientowi ze oferta jest aktualna… | „Oferta jest aktualna do końca miesiąca." |
| usun ten plik i zrob commit · sprawdz czy dyktowanie… | wierne (2/8) |

**Kontrola: TEN SAM model wołany PO NAZWIE (`groq/qwen/qwen3.8-27b`, bez nagłówka `x-aim-guard`)
→ 7/8 wierne, mediana 0,9 s.** Różnica między 2/8 a 7/8 to więc doklejany zakaz zmyślania
(etykieta `bez_zmyslania` → `added-facts`), nie model. Brzmienie zakazu („hipotezy DOZWOLONE,
ale oznaczone", „zakaz podawania nazw, liczb…") przestawia model w tryb ODPOWIADANIA — słowo
„hipoteza" pojawia się wprost w wyniku. Dla zadania, którego jedyną pracą jest przepisanie
cudzego tekstu, ten zakaz jest nie tylko zbędny, ale szkodliwy.

⚠️ Jedyny błąd modelu bez zakazu („przetłumacz to na angielski" → przetłumaczył) mieści się
w widełkach długości (1,03) — u nas łapie go nowy bezpiecznik słów (niżej). Uwaga dla
Waszego kanarka: ta klasa zdań (polecenie o JĘZYKU) przechodzi przez każdy próg długości.

## 2. Gemini 3.x u Was od 2026-09-21 — liczby z Waszej bazy, klucz VCA (id=3), `/chat`

| dzień | wynik | średnio |
|---|---|---|
| 16–19.09 | `gemini-3.5-flash-lite` 103/103 `200` | 0,7–1,3 s |
| 21–22.09 | pierwsze `503`, zjazd na `3.1-flash-lite`/`3.6-flash`/`2.5-flash` | 12–49 s |
| 24.09 | `3.5-flash-lite` 34× `503` na 42, `3.1-flash-lite` 15× `503` na 15 | 10–15 s, max 120 s |

Nasze wołanie po nazwie `gemini/gemini-3.5-flash-lite` dostawało w nagłówku `x-aim-model:
gemini/gemini-3.6-flash` (zejście w obrębie rodziny) — sonda: 4/8 `ReadTimeout` po 12 s.
Pewnie to już wiecie; podajemy, bo to był nasz jedyny objaw („dyktowanie trwa kilkanaście sekund").

## 3. Co zrobiliśmy u siebie (VCA, 2026-09-24)

- `STT_FIX_MODEL = "groq/qwen/qwen3.8-27b"` — wołane PO NAZWIE, świadomie nie przez zadanie.
- Bezpiecznik SŁÓW: porównanie słów po zdjęciu ogonków/interpunkcji; >20% zgubionych
  lub dopisanych → tekst surowy.
- `STT_FIX_HTTP_TIMEOUT` 12 s → **5 s**. ⚠️ Wasz sufit 10 s w `fix-transcript` był wyprowadzony
  z naszych 12 s — skoro zadania nie wołamy, ta zależność dziś nie istnieje; gdybyśmy wrócili,
  najpierw uzgodnimy liczby.
- `STT_MODEL = "task/transcribe"` — BEZ ZMIAN, działa (1,4–3,2 s).

## 4. Propozycja

Zdjąć `bez_zmyslania` z zadania `fix-transcript`. Po takiej zmianie chętnie powtórzymy sondę
(`python3 tools/sonda-wiernosc-poprawki.py task/fix-transcript 2`) i wrócimy do rozmowy
o przepięciu. ⛔ Nie asertujemy nazwy modelu ani `x-aim-model` — to Wasze pokrętło.

**Zwrotka:** sekcja „KONTRAKT OD AGENTA AI MANAGERA (2026-09-18)" w
`claude-voice-assistant/CLAUDE-VOICE-ASSISTANT.md` albo ten plik.
