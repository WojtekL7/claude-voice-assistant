#!/usr/bin/env python3
"""Sabotazysta bramki ETAPU 3 (`tools/test-skill-doctor.py`).

PO CO: zielona bramka NIE ODROZNIA „lekarz skilli dziala" od „nikt tego nie
sprawdza". Wariant S4 pilnuje najdrozszej pomylki tej sesji: wylaczanie przez
`permissions.deny` NIE zdejmuje kosztu kontekstu (zmierzone - skill zostaje
na liscie z pelna cena), wiec przycisk podpiety tam obiecywalby oszczednosc,
ktorej nie ma.

Uklad przepisany z `sabotaz-model-catalog.py` (sprawdzony):
  * JEDEN wariant = JEDNO wywolanie, przywracanie w `finally` + dowod sha256,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__,
  * liczba WYKONANYCH sprawdzen obok liczby padlych.

Uzycie:  python3 tools/sabotaz-skill-doctor.py S1
         python3 tools/sabotaz-skill-doctor.py --kotwice

SABOTAZ - WYNIKI ZMIERZONE (uruchomione 2026-09-14, NIE przewidziane).
Wpisane PO przebiegu - patrz COMMON „NIGDY nie wpisuj PRZEWIDYWANYCH wynikow".
Zdrowy kod: 76 sprawdzen, 76 OK, 0 FAIL. Kazdy wariant: 76 WYKONANYCH
(bramka ani razu nie urwala sie w polowie), przywrocenie dowiedzione sha256.
  wariant | co popsute                                          | padlo
  --------+-----------------------------------------------------+------
  S1      | kreska w koszcie czytana jako ZERO                  | 4
  S2      | pusty wynik parsera udaje sukces                    | 3
  S3      | wejscie standardowe OTWARTE (`claude` wisi)         | 1
  S4      | okno wraca do `permissions.deny`                    | 2
  S5      | proponowany stan ODBIERA skill userowi              | 1
  S6      | kolejnosc przegladu ignoruje uzycia                 | 2
  S7      | marnowany kontekst liczony ze wszystkich skilli     | 1
  S8      | stan 'on' wpisywany jawnie zamiast kasowac wpis     | 2
  S9      | pozycja menu nie otwiera okna                       | 1
  S10     | naglowek tabeli brany za skilla                     | 0  ← patrz nizej

⚠️ S10 NIE JEST WYKRYWANY I TO JEST POPRAWNY WYNIK, nie dziura. Jawne
pomijanie naglowka tabeli w `parse_report` to DRUGA LINIA OBRONY: wzorzec
wiersza i tak odrzuca naglowek, bo w kolumnie kosztu stoi tam slowo „context",
a nie liczba. Zapisane rowniez przy kodzie, zeby nikt nie posprzatal tej linii
jako martwej ani nie liczyl na test, ktorego nie ma.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRAMKA = REPO / "tools" / "test-skill-doctor.py"
PYTHON = str(REPO / "venv" / "bin" / "python3")
if not Path(PYTHON).exists():          # ⚠️ NIE `sys.executable` — przy aktywnym
    PYTHON = "python3"                 # cudzym venv badalibysmy inny interpreter

LEKARZ = REPO / "src" / "core" / "skill_doctor.py"
USTAWIENIA = REPO / "src" / "core" / "claude_settings.py"
OKNO = REPO / "src" / "gui" / "main_window.py"

# Liczba sprawdzen na ZDROWYM kodzie. Rozna liczba przy sabotazu = bramka
# urwala sie w polowie i jej wynik nie mowi nic o asercjach.
OCZEKIWANE = 76

# (plik, opis, szukane, zamiennik) - kotwice UNIKALNE dla badanego miejsca
WARIANTY = {
    "S1": (LEKARZ, "kreska w koszcie czytana jako ZERO zamiast braku wpisu",
           '    if text == "-":\n        return None',
           '    if text == "-":\n        return 0  # SABOTAZ'),
    "S2": (LEKARZ, "pusty wynik parsera udaje sukces (zamiast bledu)",
           '        raise SkillDoctorError("nie znalazłem ani jednego skilla — raport ma inny układ")',
           '        pass  # SABOTAZ'),
    "S3": (LEKARZ, "wejscie standardowe OTWARTE - `claude` wisi w nieskonczonosc",
           "            stdin=subprocess.DEVNULL,        # ⛔ patrz wyżej — bez tego wisi",
           "            stdin=subprocess.PIPE,  # SABOTAZ"),
    # ⛔ NAJWAZNIEJSZY WARIANT tego pliku.
    "S4": (OKNO, "okno wraca do `permissions.deny` (droga, ktora NIE zdejmuje kosztu)",
           "            nowy = sd.DEFAULT_OFF_STATE if chce_wylaczyc else None",
           "            from core.agent_skills_settings import AgentSkillsSettings\n"
           "            AgentSkillsSettings(katalog).disable(nazwa)  # SABOTAZ deny\n"
           "            nowy = None"),
    "S5": (LEKARZ, "proponowany stan ODBIERA skill userowi (off zamiast user-invocable-only)",
           'DEFAULT_OFF_STATE = "user-invocable-only"',
           'DEFAULT_OFF_STATE = "off"'),
    "S6": (LEKARZ, "kolejnosc przegladu ignoruje uzycia (nieuzywane nie ida pierwsze)",
           '                  key=lambda s: (s.get("uses", 0) != 0,',
           '                  key=lambda s: (False,'),
    "S7": (LEKARZ, "marnowany kontekst liczony ze WSZYSTKICH skilli, nie z nieuzywanych",
           '               if s.get("uses") == 0)',
           '               )'),
    "S8": (USTAWIENIA, "stan 'on' wpisywany jawnie zamiast kasowac wpis",
           '    if state is None or state == "on":',
           "    if state is None:"),
    "S9": (OKNO, "pozycja menu nie otwiera lekarza skilli",
           "        skill_doctor_action.triggered.connect(self._show_skill_doctor_dialog)",
           "        pass  # SABOTAZ"),
    "S10": (LEKARZ, "naglowek tabeli brany za skilla (zawyzony koszt, skill o nazwie 'skill')",
            '        if re.match(r"^\\s+skill\\s+source\\s+context", line):\n            continue',
            "        if False:\n            continue"),
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
