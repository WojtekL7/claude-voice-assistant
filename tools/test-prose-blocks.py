#!/usr/bin/env python3
r"""Bramka: proza dla lektora a ramki bloków kodu (`text_cleaner.prose_from_markdown`).

Po co: user kliknął 🔊 i lektor **zamilkł w połowie zdania** (2026-08-11, zakładka AI —
„doczytało mi do słowa *czysto*, dalej nie czytało"). To nie była awaria dźwięku:
do lektora dotarł już przycięty tekst (`tts.log` bez ani jednego wpisu z tego dnia).

Mechanizm: wypowiedź OPISYWAŁA ramki bloku kodu („oddaje JSON owinięty w znaczniki ```"),
więc potrójnych znaczników było PIĘĆ — liczba NIEPARZYSTA, trzy z nich w ŚRODKU LINII.
Stary wzorzec parował je na ślepo (```` ```.*?``` ````), więc parowanie przesuwało się
o jeden: prawdziwa ramka bloku znikała jako „domknięcie", a ostatni niesparowany
znacznik trafiał na regułę „niedomknięty blok = wytnij do końca" i **kasował treść**.

⛔ Objaw ma DWIE postacie i to jest najważniejsze przy rozpoznawaniu:
  • **urwanie do końca** — lektor milknie w pół zdania; GŁOŚNE, user to zgłosi;
  • **ciche POŁKNIĘCIE ŚRODKA** — czyta płynnie do końca, brakuje tylko fragmentu.
Odnaleziona wypowiedź ze zgłoszenia (2026-08-11 08:52, 3035 zn., 5 znaczników, tylko
2 na początku linii) okazała się przypadkiem DRUGIEGO rodzaju: stary kod połknął
~950 zn. ZE ŚRODKA, a zakończenie przeczytał w całości. Na produkcji (316 wypowiedzi
z dzienników) okaleczonych było 8 — do lektora docierało średnio 50% treści, teraz 75%.

Naprawa: ramką bloku jest WYŁĄCZNIE znacznik na POCZĄTKU LINII (tak działa Markdown);
znacznik w środku zdania to zwykły tekst.

Bramka pilnuje OBU kierunków naraz, bo lek łatwo przedawkować:
  (A) treść po znaczniku w środku zdania MA zostać przeczytana,
  (B) prawdziwy blok kodu MA dalej być wycinany (inaczej lektor zacznie czytać kod).

⚠️ Ta sama funkcja obsługuje TRZY drogi czytania (auto-czytanie, przycisk 🔊, lupa),
więc test sprawdza też strukturalnie, że wszystkie trzy dalej przez nią przechodzą —
gdyby ktoś w którejś z nich zrobił własne czyszczenie, usterka wróciłaby tylko tam.

Funkcja jest CZYSTA (tekst → tekst), więc bramka nie dotyka żadnych plików użytkownika —
w szczególności nie zaśmieca `read-last-debug.log`, na czym potknęliśmy się 2026-08-11.

Uruchomienie:  python3 tools/test-prose-blocks.py

═══ WYNIKI SABOTAŻU — ZMIERZONE 2026-08-26, nie przewidziane (44 asercje) ═══
  1. CODE_FENCE_RE bez kotwicy ^ (stary, ślepy wzorzec)      → padło 8   ← TEN BUG
  2. „niedomknięty blok = wytnij do końca" bez kotwicy ^      → padło 8   ← TEN BUG
  3. prose_from_markdown bez zdejmowania osieroconych         → padło 7
  4. prose_from_markdown bez sprzątania spacji                → padły 3
  5. TextCleanerForTTS bez zdejmowania osieroconych           → padły 2
  6. extract_last_claude_response bez zdejmowania osieroconych→ padł  1
  7. extract_last_claude_response bez sprzątania spacji       → padł  1
  8. bloki kodu w ogóle nie wycinane                          → padło 5
Każdy wariant wykryty. W KAŻDYM przebiegu wykonały się wszystkie asercje — bramka
ani razu nie padła w połowie (COMMON: „przy sabotażu licz też, ILE testów się
WYKONAŁO", bo urwany przebieg wygląda jak komplet zielonych). Plik przywracany
z pamięci procesu w `finally`, z dowodem sha256 przed/po każdego wariantu.

⚠️ CZEGO TA BRAMKA NIE DOWODZI — wyszło dopiero z sabotażu. Asercje „kod został
wycięty" (B1, B2, B5, B6, F4) przechodzą MIMO wyłączenia reguły ramek, bo kod
usuwają wtedy INNE reguły (w prose_from_markdown — „niedomknięty blok do końca";
w TextCleanerForTTS — filtry ścieżek i identyfikatorów). Sabotaż łapią dopiero
asercje o PROZIE WOKÓŁ bloku (B4, B7, A6) i o ETYKIECIE JĘZYKA (F5b), bo etykieta
jest jedynym świadkiem, którego nie usuwa nic innego. Wniosek na przyszłość:
sprawdzając, że coś zostało wycięte, sprawdzaj RÓWNIEŻ, że sąsiedztwo przetrwało —
inaczej „wycięte" bywa zaspokojone przez regułę, której wcale nie badasz.

⚠️ Sabotaż 3 pokazał, że zdejmowanie osieroconych znaczników NIE jest kosmetyką:
bez niego zostaje pojedynczy znak, który wpada na regułę kodu-w-zdaniu i kasuje
tekst POMIĘDZY dwoma takimi znakami (albo, w prose, znów do końca). Nie usuwaj
tej linijki jako „porządków".
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.text_cleaner import (                              # noqa: E402
    prose_from_markdown as proza,
    TextCleanerForTTS,
    extract_last_claude_response,
)

B = "`" * 3          # potrójny znacznik — trzymany w stałej, żeby nie mylił w źródle
PASS = FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"[OK]   {label}")


def bad(label, szczegol=""):
    global FAIL
    FAIL += 1
    print(f"[FAIL] {label}" + (f"\n         {szczegol}" if szczegol else ""))


def jest(label, warunek, szczegol=""):
    ok(label) if warunek else bad(label, szczegol)


def zawiera(label, tekst, fragment):
    jest(label, fragment in tekst, f"brak {fragment!r} w {tekst!r}")


def nie_zawiera(label, tekst, fragment):
    jest(label, fragment not in tekst, f"niechciane {fragment!r} w {tekst!r}")


print("=" * 78)
print("A. TREŚĆ PO ZNACZNIKU W ŚRODKU ZDANIA MUSI PRZETRWAĆ (to był bug)")
print("=" * 78)

t = f"Zdanie pierwsze. Model oddaje JSON owinięty w znaczniki {B}, więc trzeba je zdjąć. Zdanie ostatnie."
r = proza(t)
zawiera("A1 jeden znacznik w środku: koniec wypowiedzi zachowany", r, "Zdanie ostatnie.")
nie_zawiera("A2 sam znacznik jednak wycięty (nie czytamy go na głos)", r, "`")

t = f"Start. Owija w {B} a potem {B} i jeszcze {B}. Koniec zdania tu."
r = proza(t)
zawiera("A3 pięć znaczników (nieparzyście): koniec zachowany", r, "Koniec zdania tu.")
zawiera("A4 pięć znaczników: środek zdania zachowany", r, "a potem")

t = f"Ważne zdanie na końcu kończy się znacznikiem {B}"
r = proza(t)
zawiera("A5 znacznik na samym końcu nie zjada zdania przed sobą", r, "Ważne zdanie")

t = f"Opisuję znaczniki {B} w zdaniu.\n{B}python\nprint('kod')\n{B}\nZdanie po bloku."
r = proza(t)
zawiera("A6 opis + PRAWDZIWY blok: zdanie po bloku zachowane", r, "Zdanie po bloku.")
nie_zawiera("A7 opis + PRAWDZIWY blok: kod mimo to wycięty", r, "print")

# Kształt zgłoszenia usera: długa wypowiedź z opisem znaczników w środku.
dlugi = (
    "Sprawdziłem to na żywym kodzie i wygląda czysto. "
    + f"Model oddaje JSON owinięty w znaczniki {B}, więc trzeba je zdjąć przed parsowaniem. "
    + "Druga sprawa: limit czasu jest ustawiony na trzy sekundy. " * 12
    + "To jest ostatnie zdanie odpowiedzi."
)
r = proza(dlugi)
udzial = len(r) / len(dlugi)
zawiera("A8 długa wypowiedź: ostatnie zdanie dociera do lektora", r, "ostatnie zdanie odpowiedzi.")
jest("A9 długa wypowiedź: zostaje ≥70% treści (zdrowy zakres 70–85%)",
     udzial >= 0.70, f"zostało {udzial:.0%} ({len(dlugi)} → {len(r)} zn.)")

print()
print("=" * 78)
print("B. KONTROLA ODWROTNA — PRAWDZIWY KOD DALEJ MA BYĆ WYCINANY")
print("=" * 78)

t = f"Przed blokiem.\n{B}python\nprint('tajny kod')\n{B}\nPo bloku."
r = proza(t)
nie_zawiera("B1 blok kodu wycięty", r, "tajny kod")
nie_zawiera("B2 etykieta języka przy ramce nieczytana", r, "python")
zawiera("B3 proza wokół bloku zachowana", r, "Przed blokiem.")
zawiera("B4 proza po bloku zachowana", r, "Po bloku.")

t = f"A.\n{B}\nkod_jeden\n{B}\nB.\n{B}js\nkod_dwa\n{B}\nC."
r = proza(t)
nie_zawiera("B5 pierwszy z dwóch bloków wycięty", r, "kod_jeden")
nie_zawiera("B6 drugi z dwóch bloków wycięty", r, "kod_dwa")
zawiera("B7 tekst między blokami zachowany", r, "B.")

t = f"Tekst.\n  {B}\n  kod_wciety\n  {B}\nDalej."
r = proza(t)
nie_zawiera("B8 blok WCIĘTY spacjami też wycięty", r, "kod_wciety")

t = f"Przed blokiem.\n{B}python\nprint('jeszcze pisze')"
r = proza(t)
nie_zawiera("B9 blok NIEDOMKNIĘTY (agent w trakcie pisania) wycięty", r, "jeszcze pisze")
zawiera("B10 przy niedomkniętym bloku proza sprzed niego zostaje", r, "Przed blokiem.")

t = "Tekst.\n~~~\nkod_tylda\n~~~\nDalej."
r = proza(t)
nie_zawiera("B11 blok na tyldach wycięty", r, "kod_tylda")
zawiera("B12 proza wokół bloku tyldowego zachowana", r, "Dalej.")

t = "Użyj `git status --porcelain` żeby sprawdzić. Koniec."
r = proza(t)
nie_zawiera("B13 kod w zdaniu (pojedyncze znaczniki) wycięty", r, "porcelain")
zawiera("B14 zdanie wokół kodu zachowane", r, "żeby sprawdzić. Koniec.")

print()
print("=" * 78)
print("C. SPRZĄTANIE SPACJI PRZED INTERPUNKCJĄ")
print("=" * 78)

r = proza(f"Owinięty w znaczniki {B}, więc zdejmij. Druga rzecz {B}. Koniec!")
for znak in (" ,", " .", " !"):
    nie_zawiera(f"C1 brak osieroconej spacji przed {znak.strip()!r}", r, znak)
zawiera("C2 interpunkcja zdania nietknięta", r, "więc zdejmij.")
jest("C3 słowa nie sklejone", "znaczniki, więc" in r, r)

print()
print("=" * 78)
print("F. SIOSTRZANE CZYŚCIKI — TA SAMA ŚLEPA REGUŁA ŻYŁA W TRZECH KOPIACH")
print("=" * 78)

# TextCleanerForTTS obsługuje „czytaj zaznaczenie"; extract_last_claude_response —
# odczyt z ekranu. Obie miały wklejony inline ten sam wzorzec parujący ramki
# gdziekolwiek w tekście. Nie mają reguły „wytnij do końca", więc wariant był
# łagodniejszy, ale realny: kasowały tekst POMIĘDZY dwoma znacznikami w zdaniu.
zdanie = f"Zdanie pierwsze. Owija w {B} a potem {B} i jeszcze {B}. Zdanie ostatnie tu."
blok = f"Przed blokiem.\n{B}python\nprint('tajny_kod')\n{B}\nPo bloku."
RAMKA = "╭──────────────╮\n│ > pytanie usera │\n╰──────────────╯\n"

r = TextCleanerForTTS("pl_PL").clean(zdanie, use_dictionary=False)
zawiera("F1 zaznaczenie: tekst MIĘDZY znacznikami przetrwał", r, "a potem")
zawiera("F2 zaznaczenie: koniec zdania przetrwał", r, "Zdanie ostatnie tu.")
nie_zawiera("F3 zaznaczenie: surowy znacznik nie idzie do lektora", r, "`")
r = TextCleanerForTTS("pl_PL").clean(blok, use_dictionary=False)
nie_zawiera("F4 zaznaczenie KONTROLA ODWROTNA: kod dalej wycinany", r, "tajny_kod")
zawiera("F5 zaznaczenie KONTROLA ODWROTNA: proza po bloku zostaje", r, "Po bloku.")
# ⚠️ „tajny_kod" wycina na tej drodze TAKŻE inna reguła, więc sama jego nieobecność
# nie dowodzi, że ramka działa (COMMON: „ładunek odrzuciła INNA bramka niż testowana").
# Etykieta języka przy ramce jest tu jedynym świadkiem: bez ramki przecieka do lektora.
nie_zawiera("F5b zaznaczenie: etykieta języka przy ramce nie przecieka", r, "python")

r = extract_last_claude_response(RAMKA + zdanie)
zawiera("F6 ekran: tekst MIĘDZY znacznikami przetrwał", r, "a potem")
zawiera("F7 ekran: koniec zdania przetrwał", r, "Zdanie ostatnie tu.")
nie_zawiera("F8 ekran: brak osieroconej spacji przed kropką", r, " .")
r = extract_last_claude_response(RAMKA + blok)
nie_zawiera("F9 ekran KONTROLA ODWROTNA: kod dalej wycinany", r, "tajny_kod")
zawiera("F10 ekran KONTROLA ODWROTNA: proza po bloku zostaje", r, "Po bloku.")

zrodlo = (ROOT / "src" / "core" / "text_cleaner.py").read_text(encoding="utf-8")
kopie = len(re.findall(r"re\.compile\(r['\"]" + "`" * 3, zrodlo))
jest("F11 wzorzec ramki NIE jest wklejony inline (jedno źródło: CODE_FENCE_RE)",
     kopie == 0, f"znaleziono {kopie} wklejonych kopii — naprawa jednej zostawi resztę zepsute")
jest("F12 wszystkie trzy czyściki używają wspólnej stałej",
     zrodlo.count("CODE_FENCE_RE") >= 4, f"wystąpień CODE_FENCE_RE: {zrodlo.count('CODE_FENCE_RE')}")

print()
print("=" * 78)
print("D. WSZYSTKIE TRZY DROGI CZYTANIA IDĄ PRZEZ TĘ SAMĄ FUNKCJĘ")
print("=" * 78)

mw = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
wywolania = len(re.findall(r"(?<!import )prose_from_markdown\(", mw))
jest("D1 main_window woła prose_from_markdown w 3 miejscach "
     "(auto-czytanie, 🔊 czytaj ostatnią, lupa)",
     wywolania == 3, f"znaleziono {wywolania}, oczekiwano 3 — czy któraś droga "
                     f"dostała własne czyszczenie?")

print()
print("=" * 78)
print("E. KONTROLA PRZYTOMNOŚCI BRAMKI")
print("=" * 78)

czysty = "Zdanie pierwsze bez żadnych znaczników. Zdanie drugie. Zdanie trzecie."
jest("E1 tekst bez znaczników przechodzi nietknięty",
     proza(czysty) == czysty, repr(proza(czysty)))
jest("E2 asercje faktycznie rozróżniają (pusty tekst nie zdaje A1)",
     "Zdanie ostatnie." not in proza(""), "kontrola negatywna sama padła")

print()
print("=" * 78)
print(f"PODSUMOWANIE: {PASS} OK, {FAIL} FAIL")
print("=" * 78)
sys.exit(1 if FAIL else 0)
