#!/usr/bin/env python3
"""Sabotazysta bramki ETAPU 2 (`tools/test-subagent-effort.py`).

PO CO: zielona bramka NIE ODROZNIA „model podagentow i poziom wysilku dzialaja"
od „nikt tego nie sprawdza". Tu stawka jest podwojna: (1) pieniadze - podagenci
na Fable 5.1 licza sie po 2x stawce Opusa; (2) CUDZY PLIK - zapis idzie do
`~/.claude/settings.json`, w ktorym mieszka praca uzytkownika i samego Claude
Code. Wariant T4 sprawdza dokladnie to: czy bramka zauwazy, ze zapis KASUJE
cudze ustawienia.

Uklad przepisany z `sabotaz-model-catalog.py` (sprawdzony):
  * JEDEN wariant = JEDNO wywolanie, przywracanie w `finally` + dowod sha256,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__,
  * liczba WYKONANYCH sprawdzen obok liczby padlych.

Uzycie:  python3 tools/sabotaz-subagent-effort.py T1
         python3 tools/sabotaz-subagent-effort.py --kotwice

SABOTAZ - WYNIKI ZMIERZONE (uruchomione 2026-09-14, NIE przewidziane).
Wpisane PO przebiegu - patrz COMMON „NIGDY nie wpisuj PRZEWIDYWANYCH wynikow".
Zdrowy kod: 73 sprawdzenia, 73 OK, 0 FAIL. Kazdy wariant: 73 WYKONANE
(bramka ani razu nie urwala sie w polowie), przywrocenie dowiedzione sha256.
  wariant | co popsute                                          | padlo
  --------+-----------------------------------------------------+------
  T1      | wybor podagenta nie trafia do zmiennej              | 1
  T2      | srodowisko powloki ignoruje dokladki                | 3
  T3      | zakladka nie przekazuje modelu podagentow           | 1
  T4      | zapis KASUJE cudze ustawienia (plik od zera)        | 10
  T5      | uszkodzony plik traktowany jak pusty                | 4
  T6      | brak kopii zapasowej przed pierwsza zmiana          | 2
  T7      | identyfikator modelu skrocony do aliasu             | 1
  T8      | wybor podagenta nie jest zapisywany                 | 1
  T9      | pozycja menu nie otwiera okna                       | 1

⛔ NAUKA (8. wystapienie tej rodziny w projekcie, znow w MOJEJ swiezej bramce):
pierwszy przebieg T6 nie dal „2 padlo", tylko urwal bramke po 22 z 73 sprawdzen
— asercja czytala plik kopii zapasowej, ktorego badany blad wlasnie pozbawia.
Zlapal to WYLACZNIE licznik WYKONANYCH sprawdzen; sama liczba padlych (1)
czytala sie jak poprawny wynik. Kazda asercja siegajaca po plik/element,
ktory badany blad USUWA, musi byc osloniona.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRAMKA = REPO / "tools" / "test-subagent-effort.py"
PYTHON = str(REPO / "venv" / "bin" / "python3")
if not Path(PYTHON).exists():          # ⚠️ NIE `sys.executable` — przy aktywnym
    PYTHON = "python3"                 # cudzym venv badalibysmy inny interpreter

KATALOG = REPO / "src" / "core" / "claude_settings.py"
KONFIG = REPO / "src" / "config.py"
OKNO = REPO / "src" / "gui" / "main_window.py"
DIALOGI = REPO / "src" / "gui" / "dialogs.py"
ZAKLADKA = REPO / "src" / "gui" / "agent_tab.py"
TERMINAL = REPO / "src" / "gui" / "web_terminal.py"

# Liczba sprawdzen na ZDROWYM kodzie. Rozna liczba przy sabotazu = bramka
# urwala sie w polowie i jej wynik nie mowi nic o asercjach.
OCZEKIWANE = 73

# (plik, opis, szukane, zamiennik) - kotwice UNIKALNE dla badanego miejsca
WARIANTY = {
    "T1": (KONFIG, "wybor modelu podagentow nie trafia do zmiennej",
           "    return {SUBAGENT_MODEL_ENV: key}",
           "    return {}  # SABOTAZ"),
    "T2": (TERMINAL, "srodowisko powloki ignoruje dokladki zakladki",
           "    for klucz, wartosc in (extra_env or {}).items():",
           "    for klucz, wartosc in {}.items():"),
    "T3": (ZAKLADKA, "zakladka nie przekazuje modelu podagentow",
           "            extra_env=subagent_env(getattr(self, 'subagent_model', '')),",
           "            extra_env=None,"),
    # ⛔ NAJWAZNIEJSZY WARIANT: zapis buduje plik OD NOWA zamiast go scalac,
    # czyli kasuje uprawnienia, motyw i hooki uzytkownika.
    "T4": (KATALOG, "zapis KASUJE cudze ustawienia (plik budowany od zera)",
           "    dane = read_settings(p)          # uszkodzony plik → wyjątek, zero zapisu",
           "    dane = {}  # SABOTAZ"),
    "T5": (KATALOG, "uszkodzony plik traktowany jak pusty (koniec fail-closed)",
           '        raise SettingsError(f"{p} nie jest poprawnym plikiem JSON: {exc}") from exc',
           "        return {}  # SABOTAZ"),
    "T6": (KATALOG, "brak kopii zapasowej przed pierwsza zmiana",
           "    if p.exists() and not kopia.exists():",
           "    if False:"),
    "T7": (KONFIG, "identyfikator modelu skrocony do aliasu (Haiku bez daty)",
           "    return max(kandydaci, key=len) if kandydaci else key",
           "    return min(kandydaci, key=len) if kandydaci else key"),
    "T8": (DIALOGI, "wybor podagenta nie jest zapisywany",
           "            'subagent_model': self.subagent_combo.currentData() or '',",
           "            'subagent_model': '',"),
    "T9": (OKNO, "pozycja menu nie otwiera okna poziomu wysilku",
           "        effort_action.triggered.connect(self._show_model_effort_dialog)",
           "        pass  # SABOTAZ"),
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
