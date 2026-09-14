#!/usr/bin/env python3
"""Sabotazysta bramki ETAPU 4 (`tools/test-hooks-resume.py`).

PO CO: zielona bramka NIE ODROZNIA „hooki i wznawianie dzialaja" od „nikt tego
nie sprawdza". Wariant H6 pilnuje najwiekszego ryzyka tego etapu: hooki NIE MOGA
trafiac do `~/.claude/settings.json`, bo tamten plik obowiazuje KAZDA sesje
Claude Code na tym komputerze - takze uruchomiona poza apka.

Uklad przepisany z `sabotaz-model-catalog.py` (sprawdzony):
  * JEDEN wariant = JEDNO wywolanie, przywracanie w `finally` + dowod sha256,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__,
  * liczba WYKONANYCH sprawdzen obok liczby padlych.

Uzycie:  python3 tools/sabotaz-hooks-resume.py H1
         python3 tools/sabotaz-hooks-resume.py --kotwice

SABOTAZ - WYNIKI ZMIERZONE (uruchomione 2026-09-14, NIE przewidziane).
Wpisane PO przebiegu - patrz COMMON „NIGDY nie wpisuj PRZEWIDYWANYCH wynikow".
Zdrowy kod: 64 sprawdzenia, 64 OK, 0 FAIL. Kazdy wariant: 64 WYKONANE
(bramka ani razu nie urwala sie w polowie), przywrocenie dowiedzione sha256.
  wariant | co popsute                                          | padlo
  --------+-----------------------------------------------------+------
  H1      | skurczony dziennik odgrywa historie OD ZERA         | 1
  H2      | dopisek wariantu okna nie jest zdejmowany           | 2
  H3      | przycinanie tnie w polowie linii                    | 2
  H4      | sciezka w argumencie bez cudzyslowu                 | 1
  H5      | wznawiamy sesje BEZ dziennika                       | 1
  H6      | hooki wpisywane do ~/.claude/settings.json          | 2
  H7      | dziennik nadpisuje model z hooka (miganie paska)    | 2
  H8      | sesja nie jest zapisywana do rejestru               | 1
  H9      | polecenie startowe nie doklada hookow               | 1
  H10     | prosimy o WSZYSTKIE zdarzenia                       | 1

⛔ CZTERY WARIANTY (H1, H3, H8, H10) ZA PIERWSZYM RAZEM NIC NIE WYKRYLY -
i za kazdym razem wina byla w BRAMCE, nie w kodzie. Wszystkie cztery to
podrecznikowe pulapki z COMMON, zaliczone mimo ich znajomosci:
  H1  - scenariusz NIE ROZROZNIAL: skurczylem plik do PUSTKI, a wtedy poprawne
        i zepsute zachowanie daja identyczny wynik ([], 0). Lek: plik skurczony,
        ale NIEPUSTY.
  H3  - limit przycinania (200 B) dzielil sie BEZ RESZTY przez dlugosc linii
        (8 B), wiec ciecie trafialo w granice linii PRZEZ PRZYPADEK. Lek: linie
        roznej dlugosci i limit niebedacy ich wielokrotnoscia.
  H8  - asercja pytala, czy NAZWA `session_registry.record(` wystepuje w pliku;
        sabotaz zostawil wywolanie MARTWE (`None and record(...)`) i napis
        zostal. Lek: liczenie wywolan przez AST, nie szukanie napisu.
  H10 - asercja porownywala wygenerowany plik ze STALA `HOOK_EVENTS`, ktora
        sabotaz wlasnie zmienil - obie strony przesunely sie razem. Lek: zbior
        zdarzen wypisany w tescie WPROST.
⭐ Przy okazji H3 bramka URWALA SIE po 28 z 63 sprawdzen (`json.loads` na
uszkodzonej linii) - dziewiate wystapienie rodziny „bramka pada zamiast orzec".
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRAMKA = REPO / "tools" / "test-hooks-resume.py"
PYTHON = str(REPO / "venv" / "bin" / "python3")
if not Path(PYTHON).exists():          # ⚠️ NIE `sys.executable` — przy aktywnym
    PYTHON = "python3"                 # cudzym venv badalibysmy inny interpreter

HOOKI = REPO / "src" / "core" / "claude_hooks.py"
REJESTR = REPO / "src" / "core" / "session_registry.py"
OKNO = REPO / "src" / "gui" / "main_window.py"

# Liczba sprawdzen na ZDROWYM kodzie. Rozna liczba przy sabotazu = bramka
# urwala sie w polowie i jej wynik nie mowi nic o asercjach.
OCZEKIWANE = 64

# (plik, opis, szukane, zamiennik) - kotwice UNIKALNE dla badanego miejsca
WARIANTY = {
    "H1": (HOOKI, "skurczony dziennik odgrywa historie OD ZERA",
           "    if rozmiar < offset:\n        return [], rozmiar",
           "    if rozmiar < offset:\n        offset = 0  # SABOTAZ"),
    "H2": (HOOKI, "dopisek wariantu okna NIE jest zdejmowany z identyfikatora",
           '    if model_id.endswith("]") and "[" in model_id:',
           "    if False:"),
    "H3": (HOOKI, "przycinanie tnie w POLOWIE LINII (smiec dla czytnika)",
           "        nowa_linia = dane.find(b\"\\n\")\n        p.write_bytes(dane[nowa_linia + 1:] if nowa_linia >= 0 else dane)",
           "        p.write_bytes(dane)  # SABOTAZ"),
    "H4": (HOOKI, "sciezka w argumencie bez cudzyslowu (rozpada sie na spacji)",
           '    return f\'--settings "{tekst}"\'',
           "    return f'--settings {tekst}'"),
    "H5": (REJESTR, "wznawiamy sesje BEZ dziennika (blad w terminalu u usera)",
           "        if plik is None:\n            continue          # ⛔ brak dziennika = nie ma czego wznawiać",
           "        if False:\n            continue"),
    # ⛔ NAJWAZNIEJSZY WARIANT tego pliku.
    "H6": (OKNO, "hooki wpisywane do ~/.claude/settings.json (cudzy plik!)",
           "            return claude_hooks.settings_argument(claude_hooks.ensure_hooks(CONFIG_DIR))",
           "            from core import claude_settings\n"
           "            claude_settings.read_settings()  # SABOTAZ: cudzy plik\n"
           "            return ''"),
    "H7": (OKNO, "dziennik nadpisuje model, o ktorym powiedzial hook (miganie paska)",
           "        if (getattr(tab, '_model_from_hook_session', None)\n"
           "                and getattr(tab, '_model_from_hook_session', None)\n"
           "                == getattr(tab, '_pinned_session_id', None)):\n            return",
           "        if False:\n            return"),
    "H8": (OKNO, "sesja NIE jest zapisywana do rejestru (nie ma czego wznawiac)",
           "            session_registry.record(",
           "            None and session_registry.record("),
    "H9": (OKNO, "polecenie startowe nie dokłada hookow",
           '        cmd = f"{cmd} {self._hooks_argument()}".rstrip()',
           "        pass  # SABOTAZ"),
    "H10": (HOOKI, "prosimy o WSZYSTKIE zdarzenia (koszt przy kazdej turze)",
            'HOOK_EVENTS = ("SessionStart", "SessionEnd", "PostModelSwitch")',
            'HOOK_EVENTS = ("SessionStart", "SessionEnd", "PostModelSwitch", "PreToolUse")'),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wyczysc_cache():
    for d in REPO.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def srodowisko():
    """Qt Claude Code w podprocesie wywraca PyQt5 projektu - zdejmujemy je jawnie."""
    env = dict(os.environ)
    for zmienna in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(zmienna, None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    return env


def sprawdz_kotwice():
    """Czy KAZDY wariant ma DOKLADNIE jedno trafienie? Kotwica gnije przy refaktorze
    CICHO - wariant-widmo niczego nie psuje, wiec „nie wykryto" czyta sie jak dziura
    w tescie albo, gorzej, jak dowod odpornosci kodu."""
    zle = 0
    for nazwa, (plik, opis, szukane, _) in sorted(WARIANTY.items()):
        n = plik.read_text(encoding="utf-8").count(szukane)
        if n != 1:
            zle += 1
        print("  %-4s trafien=%d  %-9s %s" % (nazwa, n, "OK" if n == 1 else "!! WIDMO", opis))
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
        r = subprocess.run([PYTHON, "-B", str(BRAMKA)], capture_output=True, text=True,
                           timeout=300, cwd=str(REPO), env=srodowisko())
        wyjscie = r.stdout + r.stderr
        padly = wyjscie.count("[FAIL]")
        wykonane = wyjscie.count("[OK]") + padly
        nazwy = [l.replace("[FAIL]", "").strip()[:60]
                 for l in wyjscie.splitlines() if l.startswith("[FAIL]")]
        print("PADLYCH: %d  WYKONANYCH: %d  kod=%d" % (padly, wykonane, r.returncode))
        for n in nazwy:
            print("    - %s" % n)
        if wykonane != OCZEKIWANE:
            print(">>> UWAGA: bramka NIE DOBIEGLA DO KONCA (%d z %d) - "
                  "wynik nie mowi nic o asercjach" % (wykonane, OCZEKIWANE))
            print(wyjscie[-1200:])
        if padly == 0:
            print(">>> UWAGA: bramka NIC nie wykryla - nie chroni przed tym bledem")
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
              % (sys.argv[1], ", ".join(sorted(WARIANTY))))
        sys.exit(2)
    sys.exit(uruchom(sys.argv[1]))
