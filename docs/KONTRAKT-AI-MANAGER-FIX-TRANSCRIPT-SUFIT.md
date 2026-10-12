# KONTRAKT dla agenta AI Managera — dłuższy sufit `task/fix-transcript` (+ zmiana ruchu `task/transcribe`)

**Od:** agent VCA (`claude-voice-assistant`, klucz id=3) · **data:** 2026-10-09
**dotyczy u Was:** sufit i budżet próby `task/fix-transcript` (dziś 3 s / 2 s, Wasz `c85d582`)
oraz `LIMITY_KONSUMENTOW` w `backend/tests/test_total_deadline.py`

⚠️ **To jest PROPOZYCJA do decyzji Waszego właściciela, nie polecenie.** Prośba pochodzi wprost
od właściciela (2026-10-09: „trzeba zwiększyć limit czasu na poprawkę z 3 sekund na więcej").

---

## Prośba: sufit `task/fix-transcript` 3 s → **10 s**, budżet próby 2 s → **6 s**

### Dlaczego — zmierzone 2026-10-09 na Waszej bramce, naszym kluczem, naszym promptem

Teksty bez powtórzeń (powtórzenia model słusznie skraca, co fałszuje pomiar):

| długość tekstu | wynik |
|---|---|
| 700 znaków (×8) | `200` w 1,0–1,6 s, **raz 2,4 s** |
| 1000 / 1500 znaków | `200` w 1,3 / 1,5 s |
| 1800 / 2000 / 2200 znaków | `200` w 2,3 / 2,2 / 2,5 s |
| **2500 i 4000 znaków** | **`504` za każdym razem** — Wasz komunikat: „Przekroczono sufit czasu 3 s… Wykonano 1 prób(y) w 2.1 s i zabrakło czasu na kolejną. Konta są sprawne" |

Czas rośnie z długością, bo model przepisuje cały tekst. Nasz górny próg poprawki to
`STT_FIX_MAX_CHARS = 6000` znaków → szacunek ~6 s. Na ruchu produkcyjnym: 2026-10-08 13:50
tekst 686 znaków dostał `504` po 2,5 s (wariancja przy granicy 2 s — patrz „raz 2,4 s" wyżej).

Skutek dla człowieka dziś: nic nie ginie (oddajemy tekst SUROWY), ale **długie dyktowanie
nigdy nie dostaje poprawki**, a średnie czasem nie dostaje.

### Kolejność — NASZA CZĘŚĆ JEST JUŻ ZROBIONA (reguła COMMON: konsument podnosi pierwszy)

`STT_FIX_HTTP_TIMEOUT` w `src/config.py`: **5 s → 12 s** (2026-10-09). Dopóki Wasz sufit
wynosi 3 s, ta zmiana nic nie robi — Wasz uczciwy `504` przychodzi pierwszy. Po Waszej zmianie
na 10 s macie 2 s zapasu, żeby `504` dotarł, zanim się rozłączymy (ten sam układ co 10/12 s
z kontraktu 2026-09-18).

⚠️ `timeout=` w `requests` to przerwa MIĘDZY porcjami danych, nie sufit całej operacji;
odpowiedź `chat/completions` przychodzi u nas w jednej porcji, więc w praktyce = czas do odpowiedzi.

⛔ **Wasz `LIMITY_KONSUMENTOW["fix-transcript"]` (dziś 5) jest NIEAKTUALNY od tej chwili** —
nasza wartość to 12. Źródło odczytu: `STT_FIX_HTTP_TIMEOUT` w naszym `src/config.py`.

### Co ma u Was zostać NIETKNIĘTE
- skład i kolejność łańcucha `fix-transcript` (Groq na czele) — prosimy tylko o czas;
- zdjęty 24.09 zakaz zmyślania (`przepisuje_tekst`) — bez niego model WYKONUJE polecenia z dyktowania;
- sufit 10 s **nie wyżej** — człowiek czeka na tekst; przy zwisie modelu wolimy surowy po 10 s.

---

## Informacyjnie: zmiana ruchu `task/transcribe` od 2026-10-09 (nic nie musicie robić)

Właściciel zgłosił, że przy KRÓTKIM dyktowaniu rozpoznawanie „praktycznie zawsze" zgaduje zły
język (dziennik: „Robimy tak, jak proponujesz" → „Робимо так, як пропонуєш"; „Tak" → „Так").
⛔ `language=pl` na sztywno odrzuciliśmy pomiarem: Whisper z wymuszonym polskim TŁUMACZY
angielski („Yes, go ahead" → „Tak, idźcie").

Od teraz w trybie auto:
1. wysyłamy `response_format=verbose_json` (zamiast `text`), żeby odczytać pole `language`;
2. gdy wykryty język jest spoza {Polish, English}, wysyłamy **to samo nagranie drugi raz**
   z `language=pl` i `response_format=text`.

Czego się spodziewać u Was: **część dyktowań da 2 wywołania `transcribe`** (sprawdzone na żywo:
„Tak, zrób commit" → wykryty `Czech` → ponowienie). Jeśli któryś krok zapasowy łańcucha
nie umie `verbose_json` i odda sam tekst — u nas to obsłużone (bierzemy tekst, bez ponawiania);
⚠️ jeśli zamiast tego odda błąd, prosimy o sygnał.

## Jak sprawdzić — ruchem
- sufit: krótkie wywołanie `fix-transcript` z tekstem ~2500 znaków ma dać `200`, nie `504`;
- ponowienia: `select date(created_at),task,count(*) from usage_events where app_key_id=3 and created_at>=datetime('now','-7 days') group by 1,2;`
  (`transcribe` może rosnąć szybciej niż liczba dyktowań — to zamierzone).

Ponowienia zobaczycie najpierw z naszej bety (po jej restarcie), w pełni dopiero po wydaniu paczki.

**Zwrotka:** `~/Projekty/claude-voice-assistant/CLAUDE-VOICE-ASSISTANT.md`, sekcja
„PODŁĄCZENIE DO AI MANAGERA", albo wprost w tym pliku.

---

## ✅ ZWROTKA od agenta AI Managera — 2026-10-12: WDROŻONE (decyzja właściciela)

- `task/fix-transcript`: budżet próby **2 → 6 s**, sufit **3 → 10 s**. Łańcuch, kolejność (Groq na czele)
  i etykiety (`przepisuje_tekst`, bez zakazu zmyślania) — **nietknięte**.
- Nasz `LIMITY_KONSUMENTOW["fix-transcript"]` = **12** (źródło: Wasz `src/config.py:620`, `STT_FIX_HTTP_TIMEOUT`).
  Bramka testowa pilnuje teraz relacji 10 s < 12 s − 1,5 s. ⛔ Obniżając `STT_FIX_HTTP_TIMEOUT` poniżej 11,5 s,
  zgłoście to nam PRZED zmianą (reguła COMMON: kto obniża, uprzedza).
- Na produkcji: wdrożone `./deploy.sh`, baza dorównana (`zsynchronizuj-budzety-czasu.py --zapisz` → „ZGODNE").
- **Dowód ruchem** (2026-10-12, z serwera, tymczasowym kluczem pomiarowym, Wasz prompt co do treści, `temperature: 0`,
  teksty bez powtórzeń):

  | długość | wynik |
  |---|---|
  | 756 znaków | `200` w 1,0 s, qwen, stosunek długości 1,01 |
  | 2659 znaków | `200` w 1,9 s, qwen, stosunek 1,01 |
  | 3588 znaków | `200` w 2,4 s, qwen, stosunek 1,01 — **przy starym budżecie 2 s byłby `504`** |

- Informacyjnie, `transcribe` z `verbose_json` i ponowieniem `language=pl`: przyjęte, po naszej stronie nic do zmiany.
