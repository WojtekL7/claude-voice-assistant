#!/usr/bin/env python3
"""Sabotazysta bramki rozmiaru okna — JEDEN wariant na JEDNO wywolanie.

Po co: zielona bramka nie dowodzi, ze cokolwiek ROZROZNIA. Sabotaz przywraca
usterke i sprawdza, czy bramka ja lapie.

Zasady wymuszone przez wczesniejsze wpadki w tym projekcie:
  * jeden wariant = jedno wywolanie (petla + limit czasu zostawia sabotaz w kodzie),
  * oryginal trzymany W PAMIECI PROCESU i przywracany w `finally`
    (kod bywa niezacommitowany -> `git checkout` skasowalby prace),
  * dowod przywrocenia sumą sha256 przed/po,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__ (stary bytecode podsuwal wyniki
    poprzedniego wariantu przy plikach tej samej dlugosci w tej samej sekundzie).

Uzycie:  python3 tools/sabotaz-window-geometry.py S1
         python3 tools/sabotaz-window-geometry.py --kotwice
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CEL = REPO / "src" / "gui" / "main_window.py"
BRAMKA = REPO / "tools" / "test-window-geometry.py"

# (opis, szukane, zamiennik) — kotwice UNIKALNE dla badanej funkcji
WARIANTY = {
    "S1": ("minimum z powrotem na sztywno (sedno usterki u Tomka)",
           "    return min(min_w, w), min(min_h, h), w, h, (w, h) != (pref_w, pref_h)",
           "    return min_w, min_h, w, h, (w, h) != (pref_w, pref_h)"),
    "S2": ("rozmiar startowy z powrotem na sztywno",
           "    w = min(pref_w, int(avail_w * 0.95))\n    h = min(pref_h, int(avail_h * 0.92))",
           "    w = pref_w\n    h = pref_h"),
    "S3": ("zdjety zapas na ramke okna",
           "    w = min(pref_w, int(avail_w * 0.95))\n    h = min(pref_h, int(avail_h * 0.92))",
           "    w = min(pref_w, int(avail_w * 1.0))\n    h = min(pref_h, int(avail_h * 1.0))"),
    "S4": ("`dopasowane` zawsze False (okno nigdy sie nie wysrodkuje)",
           "    return min(min_w, w), min(min_h, h), w, h, (w, h) != (pref_w, pref_h)",
           "    return min(min_w, w), min(min_h, h), w, h, False"),
    "S5": ("brak ochrony przed ekranem 0x0 / bez danych",
           "    if avail_w <= 0 or avail_h <= 0:\n        # Brak wiarygodnych danych o ekranie -> zachowanie jak dotad.\n        return min_w, min_h, pref_w, pref_h, False",
           "    if False:\n        return min_w, min_h, pref_w, pref_h, False"),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wyczysc_cache():
    for d in REPO.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def sprawdz_kotwice():
    """Czy KAZDY wariant ma DOKLADNIE jedno trafienie? Kotwica gnije przy
    refaktorze CICHO — wariant-widmo niczego nie psuje, wiec 'nie wykryto'
    czyta sie jak dziura w tescie albo, gorzej, jak dowod odpornosci."""
    tekst = CEL.read_text(encoding="utf-8")
    zle = 0
    for nazwa, (opis, szukane, _) in sorted(WARIANTY.items()):
        n = tekst.count(szukane)
        stan = "OK" if n == 1 else "!! WIDMO"
        if n != 1:
            zle += 1
        print("  %-3s trafien=%d  %s  (%s)" % (nazwa, n, stan, opis))
    print("\nKotwice niepasujace: %d" % zle)
    return 1 if zle else 0


def uruchom(wariant):
    opis, szukane, zamiennik = WARIANTY[wariant]
    oryginal = CEL.read_text(encoding="utf-8")
    sha_przed = sha(CEL)
    if oryginal.count(szukane) != 1:
        print("PRZERWANE: kotwica %s ma %d trafien (ma byc 1)"
              % (wariant, oryginal.count(szukane)))
        return 2
    try:
        zepsuty = oryginal.replace(szukane, zamiennik)
        if zepsuty == oryginal:
            print("PRZERWANE: wariant NIC nie zmienil (widmo)")
            return 2
        CEL.write_text(zepsuty, encoding="utf-8")
        wyczysc_cache()
        print("=== SABOTAZ %s: %s ===" % (wariant, opis))
        r = subprocess.run([sys.executable, "-B", str(BRAMKA)],
                           capture_output=True, text=True, timeout=300,
                           cwd=str(REPO))
        wyjscie = r.stdout + r.stderr
        padly = wyjscie.count("[FAIL]") - wyjscie.count("(kontrola negatywna")
        wykonane = wyjscie.count("[OK]") + padly
        print(wyjscie.strip().splitlines()[-1] if wyjscie.strip() else "(brak wyjscia)")
        print("PADLYCH ASERCJI: %d   WYKONANYCH SPRAWDZEN: %d   kod wyjscia: %d"
              % (padly, wykonane, r.returncode))
        if padly == 0:
            print(">>> UWAGA: bramka NIC nie wykryla — nie chroni przed tym bledem")
        return 0
    finally:
        CEL.write_text(oryginal, encoding="utf-8")
        wyczysc_cache()
        sha_po = sha(CEL)
        print("PRZYWROCONO: %s (sha przed=%s, po=%s)"
              % ("TAK" if sha_po == sha_przed else "!!! NIE !!!",
                 sha_przed[:12], sha_po[:12]))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "--kotwice":
        sys.exit(sprawdz_kotwice())
    if sys.argv[1] not in WARIANTY:
        print("nieznany wariant: %s (dostepne: %s)"
              % (sys.argv[1], ", ".join(sorted(WARIANTY))))
        sys.exit(2)
    sys.exit(uruchom(sys.argv[1]))
