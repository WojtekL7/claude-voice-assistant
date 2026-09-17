#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabotazysta bramki TEMPA CZYTANIA — czy `tools/test-tts-speed.py` ROZROZNIA.

UZYCIE:
    venv/bin/python tools/sabotaz-tts-speed.py --kotwice      # czy wzorce pasuja
    venv/bin/python tools/sabotaz-tts-speed.py S1             # jeden wariant
    venv/bin/python tools/sabotaz-tts-speed.py --lista

⛔ JEDEN WARIANT = JEDNO WYWOLANIE. Petla po wariantach w jednym poleceniu jest
ZAKAZANA: limit czasu naklada sie wtedy na CALA petle i potrafi ubic proces
miedzy podmiana a przywroceniem — w tym projekcie zdarzylo sie to juz cztery
razy i za kazdym razem sabotaz ZOSTAWAL w kodzie produkcyjnym.

Pliki w repo bywaja BRUDNE (praca w toku), wiec NIE przywracamy przez
`git checkout` — oryginal trzyma ten proces w pamieci, oddaje go w `finally`
i DOWODZI przywrocenia suma kontrolna sha256 przed/po.

=== ZMIERZONE WYNIKI 2026-09-17 (uruchomione, NIE przewidziane) ==============
Na zdrowym kodzie bramka daje 24/24 i ZERO porazek. Kazdy wariant ponizej
zostal URUCHOMIONY; liczba WYKONANYCH sprawdzen byla 24 w KAZDYM przebiegu,
czyli bramka ani razu nie urwala sie w polowie.

  S1  -> 1  (E1)                     S8  -> 1  (B1)
  S2  -> 1  (F1)  ⚠️ patrz nizej      S9  -> 1  (C3)
  S3  -> 1  (F2)                     S10 -> 1  (A6)
  S4  -> 1  (F3)                     S11 -> 1  (E2)
  S5  -> 1  (D1)  ⭐ patrz nizej      S12 -> 1  (F4)
  S6  -> 3  (D1, D2, G1)             S13 -> 1  (C1)
  S7  -> 9  (A1-A5, B1, B2, C1, C2)  S14 -> 3  (D1, D2, G1)

WYKRYTE: 14/14.

⚠️ S2 ZA PIERWSZYM RAZEM NIE WYKRYL NICZEGO (0 padlych przy 24 wykonanych) —
i winna byla BRAMKA, nie kod. Asercja F1 pytala `"_apply_button_icon_style(
tab.speed_btn" in zrodlo`, a sabotaz zamienia warunek na `if False:`,
ZOSTAWIAJAC te linie w pliku. Po przepisaniu F1 na POMIAR SKUTKU (wolanie
prawdziwej `_apply_button_icon_styles` na atrapie + odczyt `styleSheet()`)
ten sam sabotaz zapala dokladnie jedna asercje. Rodzina: „asercja bada
ISTNIENIE nazwy zamiast WYWOLANIA".

⭐ S5 dowodzi, ze D1 i D2 to NIE duplikaty: podstawienie stalej „+0%" zapala
D1 (wyslane != ustawione), ale NIE D2 — bo „+0%" nadal JEST na liscie. Dopiero
S6/S14 zapalaja obie. Nie kasuj zadnej jako nadmiarowej; to ta sama para co
F6/F7 przy przepieciu dyktowania na zadania.
"""
import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
PY = str(KORZEN / "venv" / "bin" / "python")   # ⛔ JAWNIE, nie sys.executable:
# sys.executable wskazuje interpreter, ktorym odpalono TEN skrypt, a nie ten,
# w ktorym zyje projekt — przy aktywnym cudzym venv daje „0 wykonanych / 0 padlych",
# co czyta sie jak „testy nie rozrozniaja" zamiast „pomylilem interpreter".

BRAMKA = KORZEN / "tools" / "test-tts-speed.py"
CONFIG = KORZEN / "src" / "config.py"
TAB = KORZEN / "src" / "gui" / "agent_tab.py"
OKNO = KORZEN / "src" / "gui" / "main_window.py"
SILNIK = KORZEN / "src" / "core" / "tts_engine.py"

# Wartosc podstawiana przez sabotaz ma byc taka, ktora NIGDY nie moze byc
# prawdziwa — inaczej z czasem „przestaje klamac" i wariant slabnie po cichu.
NIGDY = "+1234%"

WARIANTY = {
    "S1": ("odczyt lagodny: kasuje walidacje wczytanego tempa", OKNO,
           "                    if _zapisane_tempo in [r for r, _ in TTS_RATE_LEVELS]:\n"
           "                        self.tts_rate = _zapisane_tempo\n"
           "                    else:\n"
           "                        self.tts_rate = TTS_DEFAULT_RATE\n",
           "                    self.tts_rate = _zapisane_tempo\n"),

    "S2": ("pulapka bialego kwadratu: wypina przycisk z malarza stylow", OKNO,
           "            if hasattr(tab, 'speed_btn'):\n"
           "                self._apply_button_icon_style(tab.speed_btn, 'icon_read_color', font_size=14)\n",
           "            if False:\n"
           "                self._apply_button_icon_style(tab.speed_btn, 'icon_read_color', font_size=14)\n"),

    "S3": ("czcionka jak dla ikony (napis 1,25x by sie nie zmiescil)", OKNO,
           "self._apply_button_icon_style(tab.speed_btn, 'icon_read_color', font_size=14)",
           "self._apply_button_icon_style(tab.speed_btn, 'icon_read_color')"),

    "S4": ("szerokosc wpisana na sztywno zamiast mierzonej", TAB,
           "            najszerszy = max(\n"
           "                fm.horizontalAdvance(tts_rate_label(m)) for _, m in TTS_RATE_LEVELS\n"
           "            )\n"
           "            btn.setFixedWidth(max(btn.height(), najszerszy + 16))\n",
           "            btn.setFixedWidth(48)\n"),

    "S5": ("tempo NIE dojezdza: do edge-tts idzie stala z listy", SILNIK,
           "            text, self.voice, rate=self.rate, volume=self.volume",
           '            text, self.voice, rate="+0%", volume=self.volume'),

    "S6": ("tempo okaleczone w drodze na siec (znak ucieta)", SILNIK,
           "            text, self.voice, rate=self.rate, volume=self.volume",
           '            text, self.voice, rate=self.rate.replace("%", ""), volume=self.volume'),

    "S7": ("wraca spowolnienie, ktorego wlasciciel nie chcial", CONFIG,
           '    ("+0%",   1.0),\n',
           '    ("-50%",  0.5),\n    ("+0%",   1.0),\n'),

    "S8": ("cykl zatrzaskuje sie na jednej wartosci", CONFIG,
           "    return wartosci[(i + 1) % len(wartosci)]",
           "    return wartosci[0]"),

    "S9": ("brak klucza podpowiedzi w slowniku angielskim", CONFIG,
           '        "tts_speed_tooltip": "Reading speed: {tempo}. Click to speed up.",\n',
           ""),

    "S10": ("druga kopia poziomow w GUI (rozjazd nieunikniony)", TAB,
            "        self.speed_btn = QPushButton()\n",
            '        _poziomy_kopia = ["+0%", "+25%", "+50%", "+100%"]\n'
            "        self.speed_btn = QPushButton()\n"),

    "S11": ("wybor nie jest zapisywany (ginie po zamknieciu okna)", OKNO,
            "            'tts_rate': getattr(self, 'tts_rate', TTS_DEFAULT_RATE),\n",
            ""),

    "S12": ("sygnal przycisku niepodlaczony (klik nic nie robi)", OKNO,
            "        agent_tab.request_tts_speed.connect(self._cycle_tts_speed)\n",
            ""),

    "S13": ("etykieta PL z kropka zamiast przecinka", CONFIG,
            '            tekst = tekst.replace(".", ",")',
            '            tekst = tekst'),

    "S14": ("tempo spoza listy dojezdza na siec", SILNIK,
            "            text, self.voice, rate=self.rate, volume=self.volume",
            f'            text, self.voice, rate="{NIGDY}", volume=self.volume'),
}

# ⛔ Zdublowany klucz w literale slownika Python zostawia OSTATNI wpis BEZ
# ostrzezenia — w tym projekcie uczynilo to cztery warianty martwymi na dobe,
# przy naglowku, ktory dalej opisywal, co „lapia".
_klucze = [l.split('"')[1] for l in Path(__file__).read_text(encoding="utf-8").splitlines()
           if l.strip().startswith('"S') and ": (" in l]
_dubel = [k for k, n in Counter(_klucze).items() if n > 1]
if _dubel:
    print(f"[FAIL] zdublowane klucze wariantow: {_dubel} — NAPRAW, zanim cokolwiek uruchomisz.")
    sys.exit(2)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def tryb_kotwice() -> int:
    """Czy KAZDY wzorzec pasuje DOKLADNIE raz.

    Kotwica gnije przy refaktorze — cicho. Wariant-widmo (0 trafien) niczego
    nie psuje, wiec jego „nic nie wykrylem" czyta sie jak odpornosc kodu.
    W tym projekcie kotwice zgnily raz w TEJ SAMEJ sesji, w ktorej powstaly.
    """
    zle = 0
    for klucz, (opis, plik, stare, _) in WARIANTY.items():
        n = plik.read_text(encoding="utf-8").count(stare)
        stan = "OK" if n == 1 else "WIDMO" if n == 0 else "WIELOKROTNA"
        if n != 1:
            zle += 1
        print(f"[{stan:11}] {klucz}: trafien={n}  ({plik.name}) — {opis}")
    print("-" * 70)
    print(f"PODSUMOWANIE KOTWIC: {len(WARIANTY) - zle}/{len(WARIANTY)} pasuje dokladnie raz")
    return 1 if zle else 0


def uruchom_bramke():
    w = subprocess.run([PY, str(BRAMKA)], capture_output=True, text=True)
    wyjscie = w.stdout + w.stderr
    padle = [l for l in wyjscie.splitlines() if l.startswith("[FAIL]")]
    wykonane = None
    for l in wyjscie.splitlines():
        if l.startswith("PODSUMOWANIE:"):
            try:
                wykonane = int(l.split("/")[1].split()[0])
            except Exception:
                pass
    return padle, wykonane, wyjscie


def tryb_wariant(klucz: str) -> int:
    if klucz not in WARIANTY:
        print(f"[FAIL] nieznany wariant {klucz}. Dostepne: {', '.join(sorted(WARIANTY))}")
        return 2
    opis, plik, stare, nowe = WARIANTY[klucz]

    oryginal = plik.read_text(encoding="utf-8")
    sha_przed = sha(plik)
    n = oryginal.count(stare)
    if n != 1:
        print(f"[FAIL] {klucz}: kotwica ma {n} trafien (wymagane 1) — NIC NIE PODMIENIONO.")
        return 2

    print("=" * 70)
    print(f"SABOTAZ {klucz}: {opis}")
    print(f"plik: {plik.relative_to(KORZEN)}  sha przed: {sha_przed}")
    print("=" * 70)

    # Przebieg ZDROWY — liczba wykonanych sprawdzen jest punktem odniesienia.
    padle_zdrowe, wykonane_zdrowe, _ = uruchom_bramke()
    print(f"[zdrowy kod]  wykonanych={wykonane_zdrowe}  padlo={len(padle_zdrowe)}")

    try:
        plik.write_text(oryginal.replace(stare, nowe, 1), encoding="utf-8")
        if sha(plik) == sha_przed:
            print(f"[FAIL] {klucz}: podmiana NIC NIE ZMIENILA w pliku.")
            return 2
        padle, wykonane, wyjscie = uruchom_bramke()
        print(f"[sabotaz   ]  wykonanych={wykonane}  padlo={len(padle)}")
        for l in padle:
            print("   " + l)
    finally:
        # ⛔ Przywracanie w `finally` i NIGDY puste — pusta oslona wyglada przy
        # przegladzie na zrobiona, a zostawia sabotaz w kodzie produkcyjnym.
        plik.write_text(oryginal, encoding="utf-8")
        sha_po = sha(plik)
        zgodne = sha_po == sha_przed
        print("-" * 70)
        print(f"PRZYWROCONE: sha po={sha_po} {'== przed ✅' if zgodne else '!= PRZED ⛔ RATUJ RECZNIE'}")

    if wykonane != wykonane_zdrowe:
        print(f"⚠️  Liczba WYKONANYCH sprawdzen sie zmienila ({wykonane_zdrowe} -> {wykonane}).")
        print("    Sprawdz, czy to LEGALNE (sabotaz dodaje/usuwa badany byt),")
        print("    czy bramka urwala sie w polowie — rozstrzyga OBECNOSC linii PODSUMOWANIE.")
    if not padle:
        print("⚠️  NIC NIE PADLO. To NIE jest dowod odpornosci kodu — zapytaj najpierw:")
        print("    czy psuty fragment ma jeszcze WIDOCZNY SKUTEK, i czy bramka o niego pyta.")
    return 0


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "--lista"
    if arg == "--kotwice":
        return tryb_kotwice()
    if arg == "--lista":
        print("Warianty (jeden na wywolanie):")
        for k, (opis, plik, _, _) in sorted(WARIANTY.items()):
            print(f"  {k:4} {plik.name:16} {opis}")
        return 0
    return tryb_wariant(arg)


if __name__ == "__main__":
    sys.exit(main())
