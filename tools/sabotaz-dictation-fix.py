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

WYNIKI ZMIERZONE 2026-09-24 (po dolozeniu bezpiecznika SLOW i zejsciu z Gemini),
wpisane PO przebiegu. Zdrowy kod: 46/46 (S12: 50/50 w test-dictation.py).
Kazdy wariant wykonal komplet sprawdzen, przywrocenie potwierdzone sha256.
  S1 A1 · S2 A2 · S3 G12,G13 · S4 A4 · S5 B2 · S6 B5 · S7 B9,D2 · S8 F1 · S9 E1
  S10 D1 · S11 E2 · S12 F7 · S13 G1,G2,G3,G9 · S14 G3 · S15 G5 · S16 G3
  S17 G10 · S18 G11 · S19 G2,G3                         → 19/19 wykrytych
⚠️ Pierwszy przebieg: S3 (zdjete widelki dlugosci) NIE ZAPALIL NICZEGO — nowy
bezpiecznik slow przejal A6/A7, wiec stara warstwa przestala byc badana.
Dolozone G12/G13: sprawdzaja widelki z WYLACZONYM bezpiecznikiem slow.
Drugie znalezisko przy pisaniu bramki: limit dopisanych slow liczony od
ODPOWIEDZI przepuszczal „…, zrob to teraz" (3 slowa do 12) — poprawione, S14.
"""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SILNIK = REPO / "src" / "core" / "stt_engine.py"
OKNO = REPO / "src" / "gui" / "main_window.py"
CONFIG = REPO / "src" / "config.py"
BRAMKA = REPO / "tools" / "test-dictation-fix.py"
BRAMKA_STT = REPO / "tools" / "test-dictation.py"
# Ile sprawdzen ma WYKONAC domyslna bramka na zdrowym kodzie. Liczba jest tu po to,
# zeby odroznic „nic nie padlo, bo kod odporny" od „bramka urwala sie w polowie" —
# bez niej oba wygladaja identycznie po odfiltrowaniu wyjscia.
OCZEKIWANE = 46

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
    # Wariant psujacy INNA funkcje niz reszta pliku, wiec ma WLASNA bramke:
    # przepiecie dyktowania na zadanie pilnuje `test-dictation.py`, nie `-fix`.
    "S12": (CONFIG, "cofniete przepiecie na zadanie — wolanie po NAZWIE MODELU "
                    "(bramka rotuje wtedy tylko miedzy kontami jednego dostawcy)",
            'STT_MODEL = "task/transcribe"',
            'STT_MODEL = "groq/whisper-large-v3"',
            BRAMKA_STT, 50),
    # --- 2026-09-24: bezpiecznik SLOW + zejscie z Gemini (awaria 21-24.09) ---
    "S13": (SILNIK, "zdjety bezpiecznik SLOW (tlumaczenie/parafraza wchodza do pola)",
            "        ok, zgubione, dopisane, ile = ocena_slow(surowy, poprawiony)\n        if not ok:",
            "        ok, zgubione, dopisane, ile = ocena_slow(surowy, poprawiony)\n        if False:"),
    "S14": (SILNIK, "limit dopisanych slow liczony znow od ODPOWIEDZI (luka z pisania G3)",
            "    ok = n_a > 0 and zgubione <= limit and dopisane <= limit",
            "    ok = n_a > 0 and zgubione <= limit and dopisane <= max(1, int(STT_FIX_MAX_LOST_SHARE * n_b))"),
    "S15": (SILNIK, "ogonki NIE zdejmowane — bezpiecznik odrzuca kazda prawdziwa poprawke",
            '    t = "".join(ch for ch in t if not unicodedata.combining(ch))',
            '    t = t  # SABOTAZ'),
    "S16": (SILNIK, "bezpiecznik ignoruje DOPISANE slowa",
            "    ok = n_a > 0 and zgubione <= limit and dopisane <= limit",
            "    ok = n_a > 0 and zgubione <= limit"),
    "S17": (CONFIG, "poprawka z powrotem przez task/fix-transcript (6/8 wykonane)",
            'STT_FIX_MODEL = "groq/qwen/qwen3.8-27b"',
            'STT_FIX_MODEL = "task/fix-transcript"'),
    "S18": (CONFIG, "czekanie na poprawke z powrotem 12 s",
            "STT_FIX_HTTP_TIMEOUT = 5.0",
            "STT_FIX_HTTP_TIMEOUT = 12.0"),
    "S19": (CONFIG, "prog bezpiecznika poluzowany 20% -> 25% (parafraza przechodzi)",
            "STT_FIX_MAX_LOST_SHARE = 0.20",
            "STT_FIX_MAX_LOST_SHARE = 0.25"),
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
    for nazwa, dane in sorted(WARIANTY.items(), key=lambda x: int(x[0][1:])):
        plik, opis, szukane = dane[0], dane[1], dane[2]
        n = plik.read_text(encoding="utf-8").count(szukane)
        if n != 1:
            zle += 1
        print("  %-4s trafien=%d  %-9s %s  (%s)"
              % (nazwa, n, "OK" if n == 1 else "!! WIDMO", plik.name, opis))
    print("\nKotwice niepasujace: %d" % zle)
    return 1 if zle else 0


def uruchom(wariant):
    dane = WARIANTY[wariant]
    plik, opis, szukane, zamiennik = dane[0], dane[1], dane[2], dane[3]
    # Wariant moze wskazac WLASNA bramke (psuje inna funkcje niz reszta pliku).
    bramka = dane[4] if len(dane) > 4 else BRAMKA
    oczekiwane = dane[5] if len(dane) > 5 else OCZEKIWANE
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
        print("    bramka: %s" % bramka.name)
        r = subprocess.run([PYTHON, "-B", str(bramka)],
                           capture_output=True, text=True, timeout=300, cwd=str(REPO))
        wyjscie = r.stdout + r.stderr
        padly = wyjscie.count("[FAIL]")
        wykonane = wyjscie.count("[OK]") + padly
        nazwy = [l.split("  ->")[0].replace("[FAIL] ", "").split()[0]
                 for l in wyjscie.splitlines() if l.startswith("[FAIL]")]
        print("PADLYCH: %d  WYKONANYCH: %d  kod=%d  -> %s"
              % (padly, wykonane, r.returncode, ", ".join(nazwy) if nazwy else "(nic)"))
        if wykonane != oczekiwane:
            print(">>> UWAGA: bramka NIE DOBIEGLA DO KONCA (%d z %d) — "
                  "wynik nie mowi nic o asercjach" % (wykonane, oczekiwane))
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
