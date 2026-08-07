#!/usr/bin/env python3
"""Bramka: KOLEJNOŚĆ niszczenia okna i QApplication przy wychodzeniu z programu.

Po co: crash na Macu (1.0.25/1.0.26/1.0.28, `EXC_BAD_ACCESS` przy ZAMYKANIU) brał się
z tego, że `sys.exit(app.exec_())` pozwalał zniknąć `QApplication` PRZED `MainWindow`.
Wtedy destruktor okna rozsyłał zdarzenia (`setActiveWindow` → `QWidget::palette()`)
po widżetach, które nie miały już strony C++.

Czego ten test NIE robi: nie odtwarza segfaultu (na Linuksie ta kolejność uchodzi
płazem — dlatego usterka siedziała niezauważona). Mierzy PRZYCZYNĘ, nie skutek.

ZMIERZONE WYNIKI (2026-08-07, PyQt5 na Linuksie, `offscreen`):
  • wzorzec STARY (`sys.exit(app.exec_())`)      → APP ginie przed WINDOW   [zła kolejność]
  • wzorzec NOWY  (`del window` + `gc.collect()`) → WINDOW ginie przed APP   [dobra]
Kontrola negatywna JEST wbudowana: stary wzorzec MUSI wypaść źle. Gdyby oba wychodziły
tak samo, test niczego nie dowodzi i jest zepsuty.
"""
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Podproces, bo każdy wzorzec potrzebuje WŁASNEGO, świeżego interpretera:
# QApplication można stworzyć raz na proces, a my mierzymy właśnie jego zniszczenie.
DZIECKO = r'''
import gc, sys, weakref
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget

WZORZEC = sys.argv[1]
slad = []

def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setCentralWidget(QTabWidget())   # QTabWidget = widżet z crashowego stosu
    window.show()

    weakref.finalize(app, lambda: print("APP", flush=True))
    weakref.finalize(window, lambda: print("WINDOW", flush=True))

    QTimer.singleShot(200, app.quit)        # kończymy pętlę bez udziału człowieka

    if WZORZEC == "stary":
        sys.exit(app.exec_())               # <- anty-wzorzec, przyczyna crashu
    else:
        rc = app.exec_()                    # <- poprawka z src/main.py
        del window
        gc.collect()
        sys.exit(rc)

main()
'''


def zmierz(wzorzec: str):
    """Zwraca listę nazw w KOLEJNOŚCI niszczenia oraz kod wyjścia."""
    p = subprocess.run([sys.executable, "-c", DZIECKO, wzorzec],
                       capture_output=True, text=True, timeout=90)
    kolejnosc = [w for w in p.stdout.split() if w in ("APP", "WINDOW")]
    return kolejnosc, p.returncode, p.stderr.strip()


def main() -> int:
    bledy = 0
    wyniki = {}

    for wzorzec in ("stary", "nowy"):
        kolejnosc, rc, err = zmierz(wzorzec)
        wyniki[wzorzec] = kolejnosc
        print(f"wzorzec {wzorzec:6} -> kolejnosc={kolejnosc or '(nic nie zmierzono)'} kod_wyjscia={rc}")
        if err:
            print(f"    stderr: {err[:200]}")

        if rc != 0:
            print(f"    [FAIL] kod wyjscia {rc}, oczekiwano 0")
            bledy += 1
        if len(kolejnosc) != 2:
            # Bez OBU znaczników nie wiemy nic — to zepsuty pomiar, nie wynik.
            print("    [FAIL] nie zmierzono obu zniszczen — pomiar nieważny")
            bledy += 1

    # Wlasciwa asercja: nowy wzorzec niszczy OKNO przed APLIKACJA.
    nowy = wyniki.get("nowy", [])
    if nowy[:2] == ["WINDOW", "APP"]:
        print("[OK]   nowy wzorzec: WINDOW ginie przed APP (o to chodzi w poprawce)")
    else:
        print(f"[FAIL] nowy wzorzec ma zla kolejnosc: {nowy}")
        bledy += 1

    # Kontrola negatywna: gdyby stary wzorzec tez byl poprawny, test nic nie rozroznia.
    stary = wyniki.get("stary", [])
    if stary[:2] == ["APP", "WINDOW"]:
        print("[OK]   kontrola negatywna: stary wzorzec faktycznie ginie w ZLEJ kolejnosci")
    elif stary == nowy:
        print("[FAIL] stary i nowy daja TEN SAM wynik — test nie rozroznia, jest bezwartosciowy")
        bledy += 1
    else:
        print(f"[UWAGA] stary wzorzec dal nieoczekiwane {stary} — sprawdz recznie przed zaufaniem")
        bledy += 1

    print()
    print("WYNIK:", "OK" if bledy == 0 else f"{bledy} BLEDOW")
    return 1 if bledy else 0


if __name__ == "__main__":
    raise SystemExit(main())
