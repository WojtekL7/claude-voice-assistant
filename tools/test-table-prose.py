#!/usr/bin/env python3
r"""Bramka: TABELE markdown a lektor (`text_cleaner`).

Po co: user kliknął 🔊 i zgłosił „wycięło mi większość rzeczy, czyta tylko początek
i koniec, środek wycina" (2026-08-28, zakładka VCA). To NIE była awaria dźwięku ani
nawrót buga potrójnego znacznika — apka miała naprawę `fc4a1ca` załadowaną (proces
wstał 08:04, poprawka z 26.08).

Mechanizm: wszystkie trzy czyściki kasowały KAŻDY wiersz `|...|` w całości, a w tabeli
siedzi zwykle najgęstsza treść wiadomości. Objaw jest CICHY — proza wokół tabeli czyta
się płynnie, więc „doczytał do końca" niczego nie dowodzi.

ZMIERZONE (nie szacowane):
  • zgłoszona wypowiedź: 2361 zn. -> 703 zn. do lektora = 30% (tabela to 68% treści);
    po naprawie 2135 zn. = 90%;
  • produkcja (dzienniki `.jsonl`, 565 wypowiedzi >=400 zn.): 322 z nich (57%) zawiera
    tabelę, średnio docierało 73% treści, najgorsze przypadki 23% / 24% / 30%.

Naprawa: tabela -> ZDANIA „Nagłówek: wartość." (wariant wybrany przez usera 2026-08-28
spośród trzech przedstawionych; odrzucone: nazwy kolumn raz na starcie, zależnie od
szerokości). Wzorzec stoi RAZ jako `TABLE_ROW_RE`/`tables_to_prose` — wcześniej był
wklejony inline w trzech czyścikach i naprawa jednego zostawiłaby dwa zepsute (dokładnie
ta sama pułapka co przy ramkach bloków kodu, patrz `test-prose-blocks.py`).

Bramka pilnuje OBU kierunków, bo lek łatwo przedawkować: treść tabeli MA być czytana,
ale rysunek tabeli (`|---|`) i tabela w bloku KODU mają dalej ginąć.

⚠️ Sekcja C woła `clean(..., use_dictionary=False)` ŚWIADOMIE: droga „czytaj zaznaczenie"
przepuszcza tekst przez filtr słownikowy pyenchant, który zjada skróty („DPD" znika
z „Kurier DPD działa") i zależy od słowników zainstalowanych w systemie. Bez tego
wyłączenia bramka byłaby niestabilna na innej maszynie i mierzyłaby nie to co trzeba.
(To osobne, WCZEŚNIEJSZE zachowanie tej drogi — nie skutek tej naprawy.)

SABOTAŻ — wyniki ZMIERZONE 2026-08-28 (uruchomione, wpisane po fakcie; każdy przebieg
wykonał komplet 27 sprawdzeń, więc zero porażek znaczy „nie wykrywa", a nie „bramka
się urwała"):
  1. droga 🔊 nie woła wspólnej funkcji            -> 6 padło (A5, B1, B2, B4, C1, F1)
  2. droga „czytaj zaznaczenie" nie woła            -> 2 padło (C2, F1)
  3. droga odczytu z ekranu nie woła                -> 2 padło (C3, F1)
  4. wiersz |---| uznany za treść                   -> 10 padło (B*, C*)
  5. tabele czytane PRZED usunięciem bloków kodu    -> 0 padło  ⚠️ patrz niżej
  6. nagłówek-symbol (#) dostaje etykietę           -> 1 padło (B5)
  7. kreska ekranowana \| dzieli komórkę            -> 2 padło (B7, B7b)

⚠️ WARIANT 5 NIE JEST WYKRYWANY I TO JEST FAKT DO ZAPAMIĘTANIA, nie luka do załatania
na siłę: ramka bloku kodu kasuje swoją zawartość niezależnie od tego, czy tabelę
przerobiono wcześniej, więc D1 przechodzi w obie strony. Kolejność wołania jest
porządkowa, nie jest bezpiecznikiem — nie licz na test, którego nie ma.

⚠️ Uruchamiając sabotaż KASUJ `src/core/__pycache__` i wołaj Pythona z `-B`. Bez tego
warianty dające plik tej samej długości w tej samej sekundzie dostają STARY bytecode
i trzy różne sabotaże raportują identyczny wynik (zdarzyło się 2026-08-28: warianty
1–3 pokazały ten sam zestaw 6 porażek, co wyglądało jak sprzężenie dróg czytania).

⚠️ Sabotaż obnażył też TRZY słabe asercje w pierwszej wersji tej bramki: C1–C3 badały
tylko, czy słowo z tabeli przeżyło (przechodziły na surowych kreskach), a B5 i B7
mierzyły koniec potoku zamiast jednostki. Zielone bez sabotażu nic nie znaczyło.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.text_cleaner import (  # noqa: E402
    TextCleanerForTTS,
    extract_last_claude_response,
    prose_from_markdown,
    tables_to_prose,
)

PASS = 0
FAIL = 0


def jest(nazwa, warunek, szczegol=""):
    global PASS, FAIL
    if warunek:
        PASS += 1
        print(f"[OK] {nazwa}")
    else:
        FAIL += 1
        print(f"[FAIL] {nazwa}")
        if szczegol:
            print(f"       {szczegol}")


TABELA = (
    "Podsumowanie testu.\n\n"
    "| Moduł | Stan |\n"
    "|---|---|\n"
    "| Kurier | działa |\n"
    "| Poczta | wymaga klucza |\n\n"
    "Koniec."
)

print("=" * 78)
print("A. PRAWDZIWA WYPOWIEDŹ ZE ZGŁOSZENIA (fixture z dziennika produkcyjnego)")
print("=" * 78)

fixture = ROOT / "tools" / "fixtures" / "tabela-produkcja-2026-08-28.txt"
oryginal = fixture.read_text(encoding="utf-8")
wynik = prose_from_markdown(oryginal)
udzial = 100 * len(wynik) / len(oryginal)

jest("A1 treść z WNĘTRZA tabeli dociera do lektora (wiersz 4)",
     "Serwery MCP" in wynik, repr(wynik[:200]))
jest("A2 treść z wnętrza tabeli — inny wiersz (kolumna druga)",
     "kliencka droga" in wynik, repr(wynik[:200]))
jest("A3 treść z ostatniego wiersza tabeli",
     "znikała sama" in wynik, repr(wynik[-200:]))
jest(f"A4 do lektora dociera >=80% wypowiedzi (jest {udzial:.0f}%, przed naprawą 30%)",
     udzial >= 80, f"{len(oryginal)} -> {len(wynik)} zn.")
jest("A5 rysunek tabeli NIE jest czytany (żadnej kreski |)",
     "|" not in wynik, repr([f for f in wynik.split() if "|" in f][:5]))

print()
print("=" * 78)
print("B. NAGŁÓWEK PRZY WARTOŚCI (wariant wybrany przez usera)")
print("=" * 78)

b = prose_from_markdown(TABELA)
jest("B1 nazwa kolumny stoi przy wartości",
     "Moduł: Kurier" in b, repr(b))
jest("B2 druga kolumna też dostaje swoją nazwę",
     "Stan: działa" in b, repr(b))
jest("B3 proza wokół tabeli nietknięta",
     b.startswith("Podsumowanie testu.") and b.endswith("Koniec."), repr(b))
jest("B4 wiersz-separator |---| nigdy nie trafia do lektora",
     "---" not in b, repr(b))

symbol = "| # | Sprawa |\n|---|---|\n| 7 | Wydanie paczki |"
# Mierzymy na JEDNOSTCE: w pełnym potoku „#" i tak zniknąłby przy zdejmowaniu
# nagłówków markdown, więc asercja na końcu potoku niczego by nie rozróżniała
# (sabotaż 2026-08-28: usunięcie strażnika _SYMBOL_HEADER_RE nie wywalało nic).
bs_jedn = tables_to_prose(symbol)
jest("B5 kolumna nazwana samym symbolem (#) nie wymyśla etykiety",
     "#:" not in bs_jedn and bs_jedn.startswith("7."), repr(bs_jedn))
jest("B5b ...a normalna kolumna obok NADAL dostaje etykietę",
     "Sprawa: Wydanie paczki" in bs_jedn, repr(bs_jedn))

bez_naglowka = "| Alfa | Beta |\n| Gamma | Delta |"
bn = prose_from_markdown(bez_naglowka)
jest("B6 tabela BEZ wiersza-separatora: komórki i tak czytane",
     "Alfa" in bn and "Delta" in bn, repr(bn))

esc = "| Kolumna | Opis |\n|---|---|\n| potok \\| rura | znak w treści |"
be_jedn = tables_to_prose(esc)
jest("B7 kreska ekranowana (\\|) to DANE — komórka zostaje JEDNA",
     "Kolumna: potok | rura" in be_jedn, repr(be_jedn))
jest("B7b ...i nie gubi sąsiedniej kolumny",
     "Opis: znak w treści" in be_jedn, repr(be_jedn))

print()
print("=" * 78)
print("C. WSZYSTKIE TRZY DROGI CZYTANIA (parytet — tu poległa poprzednia naprawa)")
print("=" * 78)

c1 = prose_from_markdown(TABELA)
c2 = TextCleanerForTTS().clean(TABELA, use_dictionary=False)
c3 = extract_last_claude_response(TABELA)

# ⚠️ Nie wystarczy sprawdzić, że słowo z tabeli PRZEŻYŁO: gdy droga przestanie
# wołać wspólną funkcję, wiersze przelatują SUROWE („| Kurier | działa |") i takie
# słowo dalej tam jest. Dowodem jest ZAMIANA NA ZDANIE: etykieta + zero kresek.
# (Sabotaż 2026-08-28: stara wersja tych trzech asercji nie wywalała się wcale.)
def przerobiona_na_zdania(txt):
    return "Moduł: Kurier" in txt and "Stan: wymaga klucza" in txt and "|" not in txt

jest("C1 droga 🔊 / auto-czytanie / lupa (prose_from_markdown)",
     przerobiona_na_zdania(c1), repr(c1))
jest('C2 droga „czytaj zaznaczenie” (TextCleanerForTTS)',
     przerobiona_na_zdania(c2), repr(c2))
jest("C3 droga odczytu z ekranu (extract_last_claude_response)",
     przerobiona_na_zdania(c3), repr(c3))

print()
print("=" * 78)
print("D. CZEGO NADAL NIE WOLNO CZYTAĆ")
print("=" * 78)

w_kodzie = (
    "Zdanie przed.\n\n"
    "```\n"
    "| Kolumna | Wartość |\n"
    "|---|---|\n"
    "| SEKRET | 12345 |\n"
    "```\n\n"
    "Zdanie po."
)
d = prose_from_markdown(w_kodzie)
jest("D1 tabela W BLOKU KODU nie trafia do lektora",
     "SEKRET" not in d and "12345" not in d, repr(d))
jest("D2 ...a proza wokół bloku przeżywa (kontrola, że D1 nie zdaje przez pustkę)",
     "Zdanie przed." in d and "Zdanie po." in d, repr(d))

print()
print("=" * 78)
print("E. KONTROLA PRZYTOMNOŚCI BRAMKI")
print("=" * 78)

czysty = "Zdanie pierwsze bez tabeli. Zdanie drugie. Zdanie trzecie."
jest("E1 tekst bez tabeli przechodzi nietknięty",
     prose_from_markdown(czysty) == czysty, repr(prose_from_markdown(czysty)))

w_zdaniu = "Uruchom polecenie ps aux | grep claude i sprawdź wynik."
jest("E2 kreska W ŚRODKU ZDANIA to nie tabela — zdanie zostaje",
     "grep claude" in prose_from_markdown(w_zdaniu),
     repr(prose_from_markdown(w_zdaniu)))

jest("E3 asercje faktycznie rozróżniają (pusty tekst NIE zdaje testu A1)",
     "Serwery MCP" not in prose_from_markdown(""), "kontrola negatywna sama padła")
jest("E4 tables_to_prose bez tabeli niczego nie rusza",
     tables_to_prose(czysty) == czysty, repr(tables_to_prose(czysty)))

print()
print("=" * 78)
print("F. STRUKTURA: JEDNO ŹRÓDŁO, ŻADNYCH KOPII INLINE")
print("=" * 78)

zrodlo = (ROOT / "src" / "core" / "text_cleaner.py").read_text(encoding="utf-8")

wywolania = len(re.findall(r"tables_to_prose\(", zrodlo)) - 1  # minus definicja
jest("F1 wspólną funkcję wołają DOKŁADNIE trzy czyściki",
     wywolania == 3,
     f"znaleziono {wywolania}, oczekiwano 3 — czy któraś droga dostała własne czyszczenie?")

def _cialo(zrodlo_pliku, naglowek):
    """Ciało funkcji: od jej `def` do następnego `def` na tym samym wcięciu."""
    start = zrodlo_pliku.index(naglowek)
    wciecie = len(naglowek) - len(naglowek.lstrip())
    reszta = zrodlo_pliku[start + len(naglowek):]
    m = re.search(r"^[ ]{%d}(?:def |class )" % wciecie, reszta, re.MULTILINE)
    return reszta[: m.start()] if m else reszta


# Wzorzec kasujący wiersz tabeli, wklejony inline (tak wyglądały trzy stare kopie).
# Patrzymy WYŁĄCZNIE w ciała trzech czyścików — szukanie po całym pliku dawało
# fałszywy alarm (łapało samo wspólne źródło i wzorzec numerów linii), a bramka
# z fałszywym alarmem jest gorsza niż jej brak, bo uczy ignorowania ostrzeżeń.
CZYSCIKI = ("    def clean(self", "def extract_last_claude_response(", "def prose_from_markdown(")
brudne = []
for naglowek in CZYSCIKI:
    cialo = _cialo(zrodlo, naglowek)
    if re.search(r"re\.(?:sub|compile|match)\([^)]*\\\|", cialo):
        brudne.append(naglowek.strip())
jest("F2 żaden z trzech czyścików nie ma WŁASNEGO wzorca na wiersz |...|",
     not brudne, f"kopia inline wróciła w: {brudne}")

jest("F2b kontrola czułości F2 — wzorzec z kreską JEST wykrywany, gdy istnieje",
     bool(re.search(r"re\.(?:sub|compile|match)\([^)]*\\\|",
                    "x = re.sub(r'^\\s*\\|.*$', '', t)")),
     "asercja F2 nie rozpoznałaby powrotu kopii inline")

jest("F3 przy wspólnym wzorcu stoi ostrzeżenie, po co on tam jest",
     "Nie wklejaj go z powrotem inline" in zrodlo, "zniknął komentarz-ostrzeżenie")

print()
print("=" * 78)
print(f"PODSUMOWANIE: {PASS} OK, {FAIL} FAIL")
print("=" * 78)
sys.exit(1 if FAIL else 0)
