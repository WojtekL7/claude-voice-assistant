#!/usr/bin/env python3
"""Bramka: lektor NIE MOŻE wymawiać emotikon — ale MUSI czytać godziny i adresy.

Zgłoszenie 2026-09-18 (właściciel): „czyta co chwilę emotikon smutek, kiedy widzi
nawias i dwukropek — wytnij to". Polecenie objęło DWA kształty, wprost nazwane:
  · „gotowe, spacja, dwukropek, nawias"  → "Gotowe :( koniec"   (działało)
  · „gotowe, dwukropek, nawias"          → "Gotowe:( koniec"    (DZIURA)

DLACZEGO to w ogóle jest problem — zmierzone na edge-tts pl-PL-ZofiaNeural
(rozmiar mp3 ∝ czas mowy; ta sama technika co przy tempie czytania):
    ' '     (cisza)        →     0 B     ← kontrola przytomności
    ':('    (samo)         → 12 816 B    ← ≈1,3 s MOWY, czyli głos czyta to jako słowa
    'Ala Ola'              → 11 232 B
    'Ala :( Ola'           → 22 032 B    (+10 800 B względem odniesienia)
Czyli emotikona to nie „dziwny znaczek", tylko ~sekunda wypowiadanego tekstu.

CZEGO ŚWIADOMIE NIE WYCINAMY (każde ma zmierzoną cenę na prawdziwych danych
użytkownika — 8162 wypowiedzi z dzienników sesji):
    '8)'  → 139 kolizji  ("art. 28)", "wersja 1.0.28)")
    ':*'  →  13 kolizji  (pogrubienie markdown: "Powód:**notatka**")  — tylko wolnostojące
    ':/'  →      ścieżki i adresy ("log:/tmp", "https://…")
    ':3'  →      godziny ("13:39", "10:30")
Nowy wzorzec przyklejony dał na tych samych 8162 wypowiedziach **0 trafień**,
czyli nie tknął ani jednego istniejącego zdania.

⛔ Wzorzec żyje w DWÓCH kopiach (text_cleaner.py + tts_engine.py). Kopia jest
ŚWIADOMA (silnik TTS bywa współdzielony między projektami), więc bramka nie każe
jej usuwać — pilnuje, żeby się nie ROZJECHAŁY (sekcja C).
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from core.text_cleaner import strip_emoji_and_emoticons, prose_from_markdown  # noqa: E402
from core.tts_engine import _sanitize_for_speech, TTSEngine  # noqa: E402

OK = FAIL = 0
WYKONANE = 0


def sprawdz(warunek, opis):
    """Jedna asercja. Liczymy też WYKONANE — bramka urwana w połowie kłamie."""
    global OK, FAIL, WYKONANE
    WYKONANE += 1
    if warunek:
        OK += 1
        print(f"[OK]   {opis}")
    else:
        FAIL += 1
        print(f"[FAIL] {opis}")


def zniknelo(tekst, ksztalt, funkcja):
    return ksztalt not in funkcja(tekst)


def zostalo(tekst, ksztalt, funkcja):
    return ksztalt in funkcja(tekst)


print("=" * 72)
print("A. EMOTIKONY WOLNOSTOJĄCE — muszą zniknąć (obie drogi)")
print("=" * 72)

WOLNE = [":(", ":)", ";)", ":-(", ":'(", ">:(", ":|", ":D", ":P", ":/",
         ":O", "^^", "<3", "=(", "xD", ":*"]
for e in WOLNE:
    tekst = f"Ala {e} Ola"
    sprawdz(zniknelo(tekst, e, strip_emoji_and_emoticons),
            f"A1 czyścik usuwa wolnostojące {e!r}")
    sprawdz(zniknelo(tekst, e, _sanitize_for_speech),
            f"A2 bramka głosu usuwa wolnostojące {e!r}")

print()
print("=" * 72)
print("B. EMOTIKONY PRZYKLEJONE DO SŁOWA — to jest naprawa ze zgłoszenia")
print("=" * 72)

# Dokładnie to, co podyktował właściciel.
sprawdz(zniknelo("Gotowe :( koniec", ":(", strip_emoji_and_emoticons),
        "B1 'gotowe, SPACJA, dwukropek, nawias' — wycięte (wariant 1 ze zgłoszenia)")
sprawdz(zniknelo("Gotowe:( koniec", ":(", strip_emoji_and_emoticons),
        "B2 'gotowe, dwukropek, nawias' — wycięte (wariant 2 ze zgłoszenia, była DZIURA)")
sprawdz(zniknelo("Gotowe:( koniec", ":(", _sanitize_for_speech),
        "B3 ten sam przypadek ginie też na bramce głosu")

for e in [":(", ":)", ":-(", ":'(", ";)", ":D", ":P", ":[", ":]"]:
    sprawdz(zniknelo(f"Gotowe{e} koniec", e, strip_emoji_and_emoticons),
            f"B4 przyklejone {e!r} po literze — wycięte")

# Litera JEST warunkiem; po cyfrze zostawiamy (patrz sekcja C).
sprawdz(zostalo("Punkt 8) drugi", "8)", strip_emoji_and_emoticons),
        "B5 '8)' NIE jest wycinane (139 kolizji z numeracją) — świadoma granica")

print()
print("=" * 72)
print("C. KONTROLA ODWROTNA — czego lektor NIE MOŻE stracić")
print("=" * 72)

MUSI_ZOSTAC = [
    ("Spotkanie o 10:30 dzisiaj", "10:30", "godzina"),
    ("Zgłoszenie z 13:39 rano", "13:39", "godzina (kolizja z ':3')"),
    ("Zgodnie z art. 28) ustawy", "28)", "numer artykułu"),
    ("Wydanie 1.0.28) na kanale", "28)", "numer wersji"),
    ("Adres https://example.com/a", "https://", "adres www (kolizja z ':/')"),
    ("Log w log:/tmp/plik.log", "log:/tmp", "ścieżka (kolizja z ':/')"),
    ("Powód:**notatka bez źródła**", "Powód:*", "pogrubienie markdown (kolizja z ':*')"),
    ("Wynik: 3 z 4 (75%) gotowe", "(75%)", "nawias z liczbą"),
    ("Pozycje 2026:(brak)", "2026:(", "dwukropek po CYFRZE — ochrona liczb"),
    # ⚠️ Poniższe trzy dobrane SABOTAŻEM, nie z głowy. Pierwsza wersja bramki
    # miała tylko przypadek wyżej i przespała trzy warianty zepsucia, bo tam
    # domknięcie (?!\w) i tak blokowało cięcie — czyli asercja była prawdziwa
    # niezależnie od kodu. Każdy z tych trzech pada przy zdjęciu innego guarda:
    ("Wynik 2026:( koniec", "2026:(", "cyfra przed emotikoną — pilnuje (?<!\\d) [S3]"),
    ("Rok 5:) dalej", "5:)", "jednocyfrowa liczba — pilnuje (?<!\\d) [S3]"),
    ("wywolanie:(argument) dalej", ":(a", "zapis funkcyjny — pilnuje (?!\\w) [S6]"),
    ("Pole:[indeks] dalej", ":[i", "indeks w nawiasie — pilnuje (?!\\w) [S6]"),
    # ⚠️ NIE ma tu przypadku dla guarda (?<![:/\\\\]). Sprawdzone: "std::)" i
    # "sciezka/:(" są cięte przez STARSZY wzorzec wolnostojący — tak samo PRZED
    # tą zmianą (git show HEAD potwierdza: 'namespace std: dalej'). Guard jest
    # więc ostrożnościowy i NIEOBSERWOWALNY przez publiczne API; asercja na niego
    # wymagałaby zmiany zachowania spoza zgłoszenia. Patrz „ZNANE GRANICE"
    # w tools/sabotaz-emoticon-speech.py (wariant S11).
]
for tekst, ksztalt, opis in MUSI_ZOSTAC:
    sprawdz(zostalo(tekst, ksztalt, strip_emoji_and_emoticons),
            f"C1 czyścik NIE rusza: {opis}")
    sprawdz(zostalo(tekst, ksztalt, _sanitize_for_speech),
            f"C2 bramka głosu NIE rusza: {opis}")

print()
print("=" * 72)
print("D. DWIE KOPIE WZORCA NIE MOGĄ SIĘ ROZJECHAĆ")
print("=" * 72)
print("    (kopia w tts_engine.py jest ŚWIADOMA — silnik bywa współdzielony;")
print("     bramka nie każe jej usuwać, tylko pilnuje zgodności zachowania)")

ZESTAW_WSPOLNY = ([f"Ala {e} Ola" for e in WOLNE]
                  + [f"Gotowe{e} koniec" for e in [":(", ":)", ":D", ":P"]]
                  + [t for t, _, _ in MUSI_ZOSTAC])
rozjazdy = []
for tekst in ZESTAW_WSPOLNY:
    a = strip_emoji_and_emoticons(tekst)
    b = _sanitize_for_speech(tekst)
    if a != b:
        rozjazdy.append((tekst, a, b))
sprawdz(not rozjazdy,
        f"D1 obie kopie dają identyczny wynik na {len(ZESTAW_WSPOLNY)} próbkach")
for tekst, a, b in rozjazdy[:5]:
    print(f"       ROZJAZD {tekst!r}: text_cleaner={a!r} tts_engine={b!r}")

print()
print("=" * 72)
print("E. PEŁNA DROGA PRODUKCYJNA (proza z markdownu → głos)")
print("=" * 72)

md = "## Wynik\n\nNie udało się:( — sprawdź `plik.py` o 10:30 pod https://a.pl/x\n"
przez_cala_droge = _sanitize_for_speech(prose_from_markdown(md))
sprawdz(":(" not in przez_cala_droge, "E1 emotikona ginie na pełnej drodze")
sprawdz("10:30" in przez_cala_droge, "E2 godzina przeżywa pełną drogę")

# ⚠️ Adresu NIE ma tu w asercji świadomie. Pierwsza wersja tej bramki wymagała,
# żeby "https://a.pl/x" przeżyło pełną drogę — i padła. Sprawdzenie na wersji
# z repo (git show HEAD) pokazało, że adres znikał TAK SAMO przed zmianą:
#     STARA: 'Wynik Nie udalo sie:( — sprawdz o 10:30 pod'
#     NOWA:  'Wynik Nie udalo sie — sprawdz o 10:30 pod'
# czyli prose_from_markdown wycina linki CELOWO (lektor ich nie czyta), a moja
# asercja była PRZESTARZAŁĄ PREMISĄ, nie wykrytą regresją. Tego, co naprawdę
# pilnujemy — że filtr emotikon nie rusza adresów — dowodzi sekcja C.
sprawdz("https://a.pl/x" in strip_emoji_and_emoticons("adres https://a.pl/x"),
        "E3 filtr emotikon NIE rusza adresu (linki wycina osobno proza, celowo)")
sprawdz("10:30" in _sanitize_for_speech(prose_from_markdown("Start:( o 10:30")),
        "E4 godzina przeżywa obok naprawionej emotikony w jednym zdaniu")

print()
print("=" * 72)
print("F. CZUJKA AUDYTU — mierzona SKUTKIEM, nie obecnością napisu w pliku")
print("=" * 72)


class AtrapaLogu(TTSEngine):
    """Prawdziwa metoda audytu, podstawiony tylko zapis do pliku."""

    def __init__(self):
        self.zapisane = []

    def _log_error(self, msg):
        self.zapisane.append(msg)


atrapa = AtrapaLogu()
atrapa._audit_emoticons("Numer 8) i adres log:/tmp koniec")
sprawdz(len(atrapa.zapisane) == 1,
        "F1 czujka MELDUJE kształt, którego świadomie nie wycinamy ('8)', ':/')")
# ⚠️ Pierwsza wersja pytała tylko „czy '8)' gdziekolwiek w meldunku" — i przespała
# sabotaż wycinający LISTĘ kształtów, bo ten sam '8)' siedział też w cytowanym
# kontekście. Pytamy więc o WYLICZENIE kształtów, czyli o to, co sabotaż usuwa.
sprawdz(any("['8)'" in z or "'8)'," in z or "'8)']" in z for z in atrapa.zapisane),
        "F2 meldunek niesie WYLICZENIE kształtów, nie tylko cytat kontekstu [S8]")

atrapa2 = AtrapaLogu()
atrapa2._audit_emoticons("Zwykłe zdanie bez niczego podejrzanego.")
sprawdz(atrapa2.zapisane == [],
        "F3 kontrola odwrotna: czysty tekst NIE produkuje szumu w logu")

atrapa3 = AtrapaLogu()
atrapa3._audit_emoticons(_sanitize_for_speech("Gotowe:( koniec"))
sprawdz(atrapa3.zapisane == [],
        "F4 po naprawie tekst ze zgłoszenia jest czysty — czujka milczy")

# Czujka nie może wywalić lektora, cokolwiek dostanie.
try:
    AtrapaLogu()._audit_emoticons(None)
    bezpieczna = True
except Exception:
    bezpieczna = False
sprawdz(bezpieczna, "F5 czujka nie wywala lektora na wejściu None")

print()
print("=" * 72)
print("G. KONTROLA PRZYTOMNOŚCI BRAMKI")
print("=" * 72)
print("    (bez tego 'wszystko zielone' nie dowodzi niczego)")

sprawdz(strip_emoji_and_emoticons("Ala :( Ola") != "Ala :( Ola",
        "G1 czyścik w ogóle COKOLWIEK robi")
sprawdz(strip_emoji_and_emoticons("Zwykłe zdanie.") == "Zwykłe zdanie.",
        "G2 czyścik nie rusza zdania, w którym nie ma czego ruszać")
sprawdz(re.search(r"\bpygame\b", "pygame") is not None,
        "G3 same asercje się wykonują (kontrola techniczna)")

print()
print("=" * 72)
print(f"WYKONANYCH ASERCJI: {WYKONANE}   OK: {OK}   FAIL: {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
