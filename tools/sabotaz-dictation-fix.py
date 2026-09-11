#!/usr/bin/env python3
"""Sabotazysta bramki dyktowania (poprawka transkrypcji + ochrona zaznaczenia).

PO CO: zielona bramka NIE ODROZNIA „warunek dziala" od „warunku nie ma".
Dopiero swiadome zepsucie produkcji pokazuje, czy asercje cokolwiek lapia.

Wzorowane na `sabotaz-window-geometry.py` — ten sam sprawdzony uklad:
  * JEDEN wariant = JEDNO wywolanie (limit czasu na petli zostawial sabotaz w kodzie),
  * przywracanie w `finally` + dowod sha256 przed/po,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__ (stary bytecode podsuwal wynik poprzedniego
    wariantu przy plikach tej samej dlugosci w tej samej sekundzie),
  * interpreter podawany JAWNIE, nie przez sys.executable.

Uzycie:  python3 tools/sabotaz-dictation-fix.py S1
         python3 tools/sabotaz-dictation-fix.py --kotwice
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SILNIK = REPO / "src" / "core" / "stt_engine.py"
OKNO = REPO / "src" / "gui" / "main_window.py"
BRAMKA = REPO / "tools" / "test-dictation-fix.py"

_VENV = REPO / "venv" / "bin" / "python"
PYTHON = str(_VENV) if _VENV.exists() else sys.executable

# (plik, opis, szukane, zamiennik) — kotwice UNIKALNE dla badanej funkcji
WARIANTY = {
    "S1": (SILNIK, "zdjety przelacznik — poprawka dziala nawet wylaczona",
           "        if not self.fix_enabled:\n            return text",
           "        if False:\n            return text"),
    "S2": (SILNIK, "poprawka wysylana bez klucza API",
           "        if not self.api_key:\n            return text",
           "        if False:\n            return text"),
    "S3": (SILNIK, "zdjete widelki dlugosci — model moze zmienic tresc",
           "        if not (STT_FIX_MIN_RATIO <= stosunek <= STT_FIX_MAX_RATIO):",
           "        if False:"),
    "S4": (SILNIK, "zdjete sprawdzanie kodu odpowiedzi (bierzemy tresc z bledu)",
           "        if odpowiedz.status_code != 200:",
           "        if False:"),
    "S5": (SILNIK, "model wpisany na sztywno zamiast z config",
           '                    "model": self.fix_model,',
           '                    "model": "groq/whisper-large-v3",'),
    "S6": (SILNIK, "zdjeta temperatura 0",
           '                    "temperature": 0,',
           '                    "temperature": 1,'),
    "S7": (SILNIK, "pelny klucz API leci do dziennika",
           '        dictation_log(f"POPRAWKA: {len(surowy)}->{len(poprawiony)} znakow po {dt:.1f}s")',
           '        dictation_log(f"POPRAWKA: klucz={self.api_key} znakow po {dt:.1f}s")'),
    "S8": (SILNIK, "zdjeta druga kontrola porzuconego podejscia",
           '                    dictation_log(f"WYNIK PORZUCONY PO POPRAWCE: podejscie #{attempt} "',
           '                    dictation_log(f"nic tu nie ma podejscie #{attempt} "'),
    "S9": (OKNO, "zdjeta OCHRONA zaznaczenia (linia zwijajaca kursor)",
           "                cursor.setPosition(cursor.selectionEnd())",
           "                pass  # SABOTAZ"),
    "S10": (OKNO, "zdjety pomiar kursora i zaznaczenia w dzienniku",
            '            dictation_log(f"    pole: znakow={len(current_text)} "',
            '            dictation_log(f"    pole: (nic nie mierze) "'),
    "S11": (OKNO, "ochrona OMIJANA warunkiem, a linia ZOSTAJE w pliku "
                  "(sprawdza, czy asercja na zrodle wystarcza)",
            "            if cursor.hasSelection():",
            "            if False:"),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wyczysc_cache():
    for d in REPO.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def sprawdz_kotwice():
    """Czy KAZDY wariant ma DOKLADNIE jedno trafienie? Kotwica gnije przy refaktorze
    CICHO — wariant-widmo niczego nie psuje, wiec 'nie wykryto' czyta sie jak dziura
    w tescie albo, gorzej, jak dowod odpornosci kodu."""
    zle = 0
    for nazwa, (plik, opis, szukane, _) in sorted(WARIANTY.items(), key=lambda x: int(x[0][1:])):
        n = plik.read_text(encoding="utf-8").count(szukane)
        if n != 1:
            zle += 1
        print("  %-4s trafien=%d  %-9s %s  (%s)"
              % (nazwa, n, "OK" if n == 1 else "!! WIDMO", plik.name, opis))
    print("\nKotwice niepasujace: %d" % zle)
    return 1 if zle else 0


def uruchom(wariant):
    plik, opis, szukane, zamiennik = WARIANTY[wariant]
    oryginal = plik.read_text(encoding="utf-8")
    sha_przed = sha(plik)
    if oryginal.count(szukane) != 1:
        print("PRZERWANE: kotwica %s ma %d trafien (ma byc 1)"
              % (wariant, oryginal.count(szukane)))
        return 2
    try:
        zepsuty = oryginal.replace(szukane, zamiennik)
        if zepsuty == oryginal:
            print("PRZERWANE: wariant NIC nie zmienil (widmo)")
            return 2
        plik.write_text(zepsuty, encoding="utf-8")
        wyczysc_cache()
        print("=== SABOTAZ %s (%s): %s ===" % (wariant, plik.name, opis))
        r = subprocess.run([PYTHON, "-B", str(BRAMKA)],
                           capture_output=True, text=True, timeout=300, cwd=str(REPO))
        wyjscie = r.stdout + r.stderr
        padly = wyjscie.count("[FAIL]")
        wykonane = wyjscie.count("[OK]") + padly
        nazwy = [l.split("  ->")[0].replace("[FAIL] ", "").split()[0]
                 for l in wyjscie.splitlines() if l.startswith("[FAIL]")]
        print("PADLYCH: %d  WYKONANYCH: %d  kod=%d  -> %s"
              % (padly, wykonane, r.returncode, ", ".join(nazwy) if nazwy else "(nic)"))
        if wykonane != 30:
            print(">>> UWAGA: bramka NIE DOBIEGLA DO KONCA (%d z 30) — "
                  "wynik nie mowi nic o asercjach" % wykonane)
        if padly == 0:
            print(">>> UWAGA: bramka NIC nie wykryla — nie chroni przed tym bledem")
        return 0
    finally:
        plik.write_text(oryginal, encoding="utf-8")
        wyczysc_cache()
        sha_po = sha(plik)
        print("PRZYWROCONO %s: %s (sha przed=%s, po=%s)"
              % (plik.name, "TAK" if sha_po == sha_przed else "!!! NIE !!!",
                 sha_przed[:12], sha_po[:12]))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "--kotwice":
        sys.exit(sprawdz_kotwice())
    if sys.argv[1] not in WARIANTY:
        print("nieznany wariant: %s (dostepne: %s)"
              % (sys.argv[1], ", ".join(sorted(WARIANTY, key=lambda x: int(x[1:])))))
        sys.exit(2)
    sys.exit(uruchom(sys.argv[1]))
