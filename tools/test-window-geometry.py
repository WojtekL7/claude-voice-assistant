#!/usr/bin/env python3
"""Bramka: rozmiar okna startowego MUSI miescic sie na ekranie uzytkownika.

Dlaczego powstala (zgloszenie 2026-09-03, Windows u Tomka): okno otwieralo sie
w sztywnym rozmiarze 1100x750 z minimum 900x650 pikseli LOGICZNYCH. Na ekranie
1366x768 przy powiekszeniu Windows 150% obszar roboczy jest mniejszy niz to
minimum, wiec okna NIE DALO SIE zmiescic nawet po maksymalizacji — minimum
blokowalo zmniejszenie, a dol programu zostawal pod krawedzia ekranu.

Bramka pyta CZYSTA FUNKCJE `startup_geometry_for(avail_w, avail_h)`, a nie
zbudowane okno — warunek wpisany w srodku `_setup_ui` nie ma czego odpytac.

WYNIKI SABOTAZU — ZMIERZONE 2026-09-03 (narzedzie: tools/sabotaz-window-geometry.py;
kazdy przebieg wykonal komplet 25 sprawdzen, wiec zadna liczba nie jest artefaktem
przerwanej bramki):
  S1  minimum z powrotem na sztywno 900x650                  -> padly 3 asercje
  S2  rozmiar startowy z powrotem na sztywno 1100x750        -> padly 7 asercji
  S3  zdjety zapas na ramke (mnozniki 1.0 zamiast 0.95/0.92) -> padly 2 asercje
  S4  `dopasowane` zawsze False                              -> padla 1 asercja
  S5  brak ochrony przed ekranem 0x0                         -> padly 2 asercje
Kazdy wariant wykryty. (Pierwsza wersja tego naglowka niosla liczby PRZEWIDZIANE
przed uruchomieniem — 4/5/2/2/2 — i trzy z pieciu byly nieprawdziwe. Nie wpisuj
tu niczego, czego nie uruchomiles.) Kontrola negatywna na koncu pliku dowodzi, ze bramka
w ogole potrafi zglosic blad.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

PASSED = 0
FAILED = 0


def check(nazwa, got, expected):
    global PASSED, FAILED
    if got == expected:
        PASSED += 1
        print("[OK]   %s" % nazwa)
    else:
        FAILED += 1
        print("[FAIL] %s\n         oczekiwano: %r\n         otrzymano:  %r"
              % (nazwa, expected, got))


def check_true(nazwa, warunek, opis=""):
    check(nazwa + (" — " + opis if opis else ""), bool(warunek), True)


# Import BEZ budowania QApplication — funkcja jest czysta.
from gui.main_window import (                      # noqa: E402
    startup_geometry_for, DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_MINIMUM)

PREF_W, PREF_H = DEFAULT_WINDOW_SIZE
MIN_W, MIN_H = DEFAULT_WINDOW_MINIMUM


def t1_duzy_ekran_bez_zmian():
    """Na duzym ekranie NIC sie nie zmienia — ochrona Linuksa przed regresja."""
    min_w, min_h, w, h, dop = startup_geometry_for(1920, 1080)
    check("[1a] duzy ekran: rozmiar startowy jak dotad", (w, h), (PREF_W, PREF_H))
    check("[1b] duzy ekran: minimum jak dotad", (min_w, min_h), (MIN_W, MIN_H))
    check("[1c] duzy ekran: nie ma potrzeby srodkowania", dop, False)


def t2_maly_ekran_miesci_sie():
    """Ekran Tomka 1366x768: okno MUSI zmiescic sie w obszarze roboczym."""
    # Windows zabiera pasek zadan -> obszar roboczy ok. 1366x728.
    avail_w, avail_h = 1366, 728
    min_w, min_h, w, h, dop = startup_geometry_for(avail_w, avail_h)
    check_true("[2a] szerokosc miesci sie na ekranie", w <= avail_w, "%d<=%d" % (w, avail_w))
    check_true("[2b] wysokosc miesci sie na ekranie", h <= avail_h, "%d<=%d" % (h, avail_h))
    check_true("[2c] MINIMUM tez sie miesci (inaczej nie da sie zmniejszyc)",
               min_w <= avail_w and min_h <= avail_h, "%dx%d" % (min_w, min_h))
    check("[2d] ekran wymusil zmniejszenie -> srodkujemy", dop, True)


def t3_ekran_po_powiekszeniu_150():
    """To jest PRZYPADEK ZE ZGLOSZENIA: 1366x768 przy powiekszeniu 150%.

    Qt oddaje wtedy obszar roboczy w pikselach logicznych, czyli ok. 911x485.
    Stare minimum 900x650 bylo WYZSZE niz caly ekran -> dol nieosiagalny.
    """
    avail_w, avail_h = 911, 485
    min_w, min_h, w, h, dop = startup_geometry_for(avail_w, avail_h)
    check_true("[3a] okno miesci sie w pionie", h <= avail_h, "%d<=%d" % (h, avail_h))
    check_true("[3b] okno miesci sie w poziomie", w <= avail_w, "%d<=%d" % (w, avail_w))
    check_true("[3c] MINIMUM nie przekracza wysokosci ekranu (sedno usterki)",
               min_h <= avail_h, "min_h=%d, ekran=%d" % (min_h, avail_h))
    check_true("[3d] minimum nie przekracza szerokosci ekranu",
               min_w <= avail_w, "min_w=%d, ekran=%d" % (min_w, avail_w))
    check_true("[3e] okno nie jest zdegenerowane (ma sensowny rozmiar)",
               w >= 200 and h >= 200, "%dx%d" % (w, h))


def t4_zapas_na_ramke():
    """Okno NIE MOZE zajmowac calego obszaru co do piksela — ramka i pasek
    tytulu doliczaja sie POZA rozmiarem tresci."""
    avail_w, avail_h = 1000, 700
    _, _, w, h, _ = startup_geometry_for(avail_w, avail_h)
    check_true("[4a] zostaje zapas w poziomie", w < avail_w, "%d<%d" % (w, avail_w))
    check_true("[4b] zostaje zapas w pionie", h < avail_h, "%d<%d" % (h, avail_h))


def t5_brak_danych_o_ekranie():
    """Fail-open: gdy Qt nie zna ekranu (render offscreen), zostajemy przy
    dotychczasowych wartosciach zamiast dawac okno 0x0."""
    for opis, arg in (("zera", (0, 0)), ("wartosci ujemne", (-1, -1)),
                      ("None", (None, None)), ("tekst", ("a", "b"))):
        min_w, min_h, w, h, dop = startup_geometry_for(*arg)
        check("[5] brak danych (%s) -> wartosci domyslne" % opis,
              (min_w, min_h, w, h, dop),
              (MIN_W, MIN_H, PREF_W, PREF_H, False))


def t6_monotonicznosc():
    """Wiekszy ekran nie moze dac MNIEJSZEGO okna — banalne, ale lapie
    pomylki w znaku i w kolejnosci min()."""
    _, _, w_maly, h_maly, _ = startup_geometry_for(800, 600)
    _, _, w_duzy, h_duzy, _ = startup_geometry_for(1600, 1200)
    check_true("[6a] szerokosc rosnie z ekranem", w_duzy >= w_maly,
               "%d >= %d" % (w_duzy, w_maly))
    check_true("[6b] wysokosc rosnie z ekranem", h_duzy >= h_maly,
               "%d >= %d" % (h_duzy, h_maly))


def t7_minimum_nie_wieksze_niz_okno():
    """Minimum wieksze niz rozmiar startowy = okno startuje juz za male
    i Qt je natychmiast rozciaga — sprzecznosc, ktora latwo wprowadzic."""
    for avail in ((1920, 1080), (1366, 728), (911, 485), (640, 480)):
        min_w, min_h, w, h, _ = startup_geometry_for(*avail)
        check_true("[7] minimum <= rozmiar startowy przy ekranie %dx%d" % avail,
                   min_w <= w and min_h <= h,
                   "min %dx%d vs okno %dx%d" % (min_w, min_h, w, h))


def t_control():
    """Czy ten plik w ogole UMIE zglosic blad? Bez tego komplet [OK] nic nie znaczy."""
    global PASSED, FAILED
    before = FAILED
    check("(kontrola negatywna — TA linia MA paść)", "cokolwiek", "coś innego")
    if FAILED == before + 1:
        FAILED = before
        PASSED += 1
        print("[OK]   kontrola negatywna zadzialala (test potrafi paść)")
    else:
        print("[FAIL] kontrola negatywna NIE zadzialala — testom nie mozna ufac")
        FAILED += 1


def main():
    t1_duzy_ekran_bez_zmian()
    t2_maly_ekran_miesci_sie()
    t3_ekran_po_powiekszeniu_150()
    t4_zapas_na_ramke()
    t5_brak_danych_o_ekranie()
    t6_monotonicznosc()
    t7_minimum_nie_wieksze_niz_okno()
    t_control()
    print("\nWynik: %d OK / %d FAIL" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
