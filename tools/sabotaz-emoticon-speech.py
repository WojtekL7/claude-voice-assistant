#!/usr/bin/env python3
"""Sabotaż bramki emotikon: psuje kod na N sposobów i sprawdza, że bramka pada.

Po co: „76/76 zielono" samo w sobie nie dowodzi NICZEGO — bramka mogłaby pytać
o rzeczy, które są prawdziwe niezależnie od kodu. Dopiero zepsucie produkcji
i zobaczenie CZERWIENI dowodzi, że bramka pilnuje czegokolwiek.

⚠️ NAUKA Z POPRZEDNICH RUND (CLAUDE-VOICE-ASSISTANT.md, bug tabel):
   `__pycache__` podsuwa STARY bytecode wariantom, które dają plik tej samej
   długości w tej samej sekundzie — trzy różne sabotaże raportowały wtedy
   identyczny wynik. Dlatego: python3 -B + kasowanie __pycache__ przed każdym
   przebiegiem.

⚠️ Sabotujemy ŚCIEŻKĘ (produkcyjny kod), nigdy ŹRÓDŁO OCZEKIWAŃ (bramkę) —
   sabotaż bramki przesuwa obie strony porównania naraz i „nic nie padło"
   znaczyłoby tylko tyle, że test porównał stałą samą ze sobą.

ZNANE GRANICE (zmierzone, NIE łatane na siłę):
   · Guard `(?<![:/\\])` w _EMOTICONS_GLUED jest NIEOBSERWOWALNY przez publiczne
     API czyścika. Powód: przypadki, których broni („std::)", „sciezka/:("), są
     i tak cięte przez STARSZY wzorzec wolnostojący — jego `(?<!\w)` przepuszcza
     po dwukropku i po ukośniku. Sprawdzone na wersji z repo (git show HEAD):
     zachowanie identyczne PRZED tą zmianą. Guard zostaje jako ochrona w głąb
     (gdyby kiedyś zmienić wzorzec wolnostojący), ale nie udaję, że mam na niego
     test. Nie licz na test, którego nie ma.

WYNIKI ZMIERZONE 2026-09-18 (12 wariantów, KAŻDY wykryty; w nawiasie liczba
zapalonych asercji przy 84 WYKONANYCH w każdym przebiegu — bramka się nie urywa,
pliki przywrócone co do sha256):
   S1(11) S2(3) S3(3) S4(1) S5(2) S6(3) S7(2) S8(1) S9(2) S10(2) S12(9) S13(2)

⚠️ Pierwszy przebieg dał 9/13 — i w KAŻDYM z czterech przeoczeń winna była
BRAMKA, nie kod (ta sama rodzina co nauka z rundy tabel):
   S3  — przypadek testowy "2026:(brak)" miał literę po nawiasie, więc domknięcie
         (?!\w) i tak blokowało cięcie; asercja była prawdziwa niezależnie od kodu.
         Lek: "Wynik 2026:( koniec" i "Rok 5:) dalej" (dobrane pomiarem).
   S6  — brakowało przypadku z zapisem funkcyjnym; doszły "wywolanie:(argument)"
         i "Pole:[indeks]".
   S8  — asercja pytała, czy '8)' jest gdziekolwiek w meldunku, a ten sam kształt
         siedział w cytowanym kontekście; pytamy teraz o WYLICZENIE kształtów.
   S11 — jedyny NIE z winy bramki: guard okazał się nieobserwowalny (patrz
         ZNANE GRANICE wyżej). Wariant usunięty zamiast naciągania testu.
"""
import hashlib
import os
import shutil
import subprocess
import sys

KATALOG = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(KATALOG, '..'))
CLEANER = os.path.join(REPO, 'src', 'core', 'text_cleaner.py')
ENGINE = os.path.join(REPO, 'src', 'core', 'tts_engine.py')
BRAMKA = os.path.join(KATALOG, 'test-emoticon-speech.py')

# (nazwa, plik, szukaj, zamień_na, co ma paść)
WARIANTY = [
    ("S1  czyścik przestaje usuwać PRZYKLEJONE", CLEANER,
     "    text = _EMOTICONS_GLUED.sub(\" \", text)",
     "    pass  # SABOTAZ",
     "B2/B4 — naprawa ze zgłoszenia"),

    ("S2  bramka głosu przestaje usuwać PRZYKLEJONE", ENGINE,
     "    text = _SPEECH_EMOTICON_GLUED_RE.sub(\" \", text)",
     "    pass  # SABOTAZ",
     "B3/D1 — druga droga"),

    ("S3  zdjęta ochrona LICZB w czyścliku", CLEANER,
     r'r"(?<!\d)(?<![:/\\])[:;][-~^' + "'" + r']?[)(\]\[DdPp](?!\w)"',
     r'r"(?<![:/\\])[:;][-~^' + "'" + r']?[)(\]\[DdPp](?!\w)"',
     "C — '2026:(' straciłoby dwukropek"),

    ("S4  '8' dopisane do przyklejonych (kolizja z numeracją)", CLEANER,
     r'[:;][-~^' + "'" + r']?[)(\]\[DdPp](?!\w)"',
     r'[:;8][-~^' + "'" + r']?[)(\]\[DdPp](?!\w)"',
     "B5 — numery artykułów"),

    ("S5  '*' dopisana do przyklejonych (kolizja z pogrubieniem)", CLEANER,
     r'[)(\]\[DdPp](?!\w)"',
     r'[)(\]\[DdPp*](?!\w)"',
     "C — 'Powód:**…**'"),

    ("S6  zdjęte domknięcie (?!\\w) w przyklejonych", CLEANER,
     r'[)(\]\[DdPp](?!\w)"',
     r'[)(\]\[DdPp]"',
     "C — zwykły tekst zaczyna znikać"),

    ("S7  czujka audytu wyłączona", ENGINE,
     "            trafienia = _SPEECH_EMOTICON_AUDIT_RE.findall(text)",
     "            trafienia = []  # SABOTAZ",
     "F1/F2 — brak dowodu na przyszłość"),

    ("S8  czujka melduje bez KSZTAŁTU", ENGINE,
     '                f"{len(trafienia)} ksztaltow {sorted(set(trafienia))} | " + " ".join(fragmenty)',
     '                f"{len(trafienia)} ksztaltow | " + " ".join(fragmenty)',
     "F2 — meldunek bez treści jest bezużyteczny"),

    ("S9  ROZJAZD kopii: tylko czyścik traci ':*'", CLEANER,
     r"[:;=][-~^'" + r']?[)(\]\[DPpOo|/\\3<>*]"',
     r"[:;=][-~^'" + r']?[)(\]\[DPpOo|/\\3<>]"',
     "A/D1 — dwie kopie się rozjeżdżają"),

    ("S10 ROZJAZD kopii: tylko silnik traci ':*'", ENGINE,
     r"[:;=][-~^'" + r']?[)(\]\[DPpOo|/\\3<>*]"',
     r"[:;=][-~^'" + r']?[)(\]\[DPpOo|/\\3<>]"',
     "A2/D1 — rozjazd w drugą stronę"),

    ("S12 czyścik emotikon wyłączony CAŁKIEM", CLEANER,
     '    text = _EMOTICONS.sub(" ", text)',
     '    pass  # SABOTAZ',
     "A — wszystko przestaje działać"),

    ("S13 czujka nie odróżnia pustego wyniku", ENGINE,
     "            if not trafienia:\n                return",
     "            if False:\n                return",
     "F3 — log zasypywany szumem"),
]


def sha256(sciezka):
    with open(sciezka, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def wyczysc_cache():
    for korzen, katalogi, _ in os.walk(os.path.join(REPO, 'src')):
        for k in list(katalogi):
            if k == '__pycache__':
                shutil.rmtree(os.path.join(korzen, k), ignore_errors=True)


def uruchom_bramke():
    wyczysc_cache()
    wynik = subprocess.run([sys.executable, '-B', BRAMKA],
                           capture_output=True, text=True, cwd=REPO, timeout=300)
    wyjscie = wynik.stdout + wynik.stderr
    padlo = wyjscie.count('[FAIL]')
    wykonane = 0
    for linia in wyjscie.splitlines():
        if 'WYKONANYCH ASERCJI:' in linia:
            try:
                wykonane = int(linia.split('WYKONANYCH ASERCJI:')[1].split()[0])
            except Exception:
                pass
    return wynik.returncode, padlo, wykonane


print("=" * 74)
print("SABOTAŻ BRAMKI EMOTIKON")
print("=" * 74)

odciski = {CLEANER: sha256(CLEANER), ENGINE: sha256(ENGINE)}

kod, padlo, wykonane = uruchom_bramke()
print(f"\nZDROWY KOD: kod wyjścia={kod}, [FAIL]={padlo}, WYKONANYCH={wykonane}")
if kod != 0:
    print("!!! Bramka pada na ZDROWYM kodzie — napraw to, zanim sabotujesz.")
    sys.exit(1)
WYKONANE_ZDROWE = wykonane

wykryte = 0
przeoczone = []

for nazwa, plik, szukaj, zamien, spodziewane in WARIANTY:
    oryginal = open(plik, encoding='utf-8').read()
    if szukaj not in oryginal:
        print(f"\n{nazwa}\n   !!! KOTWICA NIE PASUJE — wariant MARTWY, popraw sabotaż")
        przeoczone.append(nazwa + " (martwa kotwica)")
        continue
    try:
        open(plik, 'w', encoding='utf-8').write(oryginal.replace(szukaj, zamien, 1))
        kod, padlo, wykonane = uruchom_bramke()
    finally:
        open(plik, 'w', encoding='utf-8').write(oryginal)
        assert sha256(plik) == odciski[plik], f"NIE PRZYWRÓCONO {plik}"

    if kod != 0:
        wykryte += 1
        urwana = " ⚠️ BRAMKA URWANA" if wykonane < WYKONANE_ZDROWE else ""
        print(f"\n{nazwa}\n   WYKRYTY — zapaliło {padlo} asercji "
              f"({wykonane} wykonanych){urwana}\n   spodziewane: {spodziewane}")
    else:
        print(f"\n{nazwa}\n   !!! PRZEOCZONY — bramka nie widzi tego zepsucia")
        przeoczone.append(nazwa)

wyczysc_cache()
print("\n" + "=" * 74)
print(f"WYKRYTYCH: {wykryte}/{len(WARIANTY)}")
for p in odciski:
    print(f"przywrócono co do sha256: {os.path.basename(p)} ✓")
if przeoczone:
    print("PRZEOCZONE (bramka do wzmocnienia):")
    for p in przeoczone:
        print(f"   · {p}")
print("=" * 74)
sys.exit(1 if przeoczone else 0)
