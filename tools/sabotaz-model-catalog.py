#!/usr/bin/env python3
"""Sabotazysta bramki KATALOGU MODELI (`tools/test-model-catalog.py`).

PO CO: zielona bramka NIE ODROZNIA „czujka modeli dziala" od „nikt tego nie
sprawdza". I to nie jest teoria — dokladnie tak przeleciala usterka z 2026-09-14:
bramka swiecila 61/61, a produkcja od 27 dni nie widziala nowego modelu, bo
bramka pytala WYLACZNIE stara kopie strony Anthropic (fixture z 26.07), a zmiana
zaszla na stronie dzisiejszej. Stad drugi fixture i ten sabotazysta.

Uklad przepisany z `sabotaz-bottom-bar.py` (sprawdzony):
  * JEDEN wariant = JEDNO wywolanie (limit czasu na petli zostawial sabotaz w kodzie),
  * przywracanie w `finally` + dowod sha256 przed/po,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__ (stary bytecode podsuwal wyniki
    poprzedniego wariantu — trzy rozne sabotaze raportowaly to samo),
  * liczba WYKONANYCH sprawdzen obok liczby padlych: bramka urwana w polowie
    wyglada po odfiltrowaniu identycznie jak komplet zielonych.

Uzycie:  python3 tools/sabotaz-model-catalog.py S1
         python3 tools/sabotaz-model-catalog.py --kotwice

SABOTAZ - WYNIKI ZMIERZONE (uruchomione 2026-09-14, NIE przewidziane).
Wpisane PO przebiegu — patrz COMMON „NIGDY nie wpisuj PRZEWIDYWANYCH wynikow".
Zdrowy kod: 111 sprawdzen, 111 OK, 0 FAIL. Kazdy wariant: 111 WYKONANYCH
(czyli bramka ani razu nie urwala sie w polowie) i przywrocenie dowiedzione sha256.
  wariant | co popsute                                          | padlo
  --------+-----------------------------------------------------+------
  S1      | czyscik zostawia odwrotne apostrofy (PRZYCZYNA)     | 9
  S2      | wzorzec ceny nie pasuje do niczego                  | 3
  S3      | zdjeta bramka przytomnosci parsera                  | 1
  S4      | nieudana proba nie zostawia sladu                   | 1
  S5      | podpowiedz o koszcie zawsze pusta                   | 4
  S6      | mnoznik z jednej stawki zamiast z obu               | 1
  S7      | cicha awaria znowu milczy bez konca                 | 1
  S8      | etykieta kosztu nie odswieza sie przy zmianie       | 1
  S9      | stary plik podreczny przykrywa wartosc wbudowana    | 1

⛔ NAUKA Z PISANIA TEJ BRAMKI (7. wystapienie tej rodziny w projekcie):
pierwszy przebieg S1 NIE dal „9 padlo", tylko WYWALIL bramke — `parse_catalog`
stalo w niej goles, poza oslona, wiec badany blad zabijal ja w polowie, a
wyjscie po odfiltrowaniu wygladalo jak komplet zielonych. Sabotaz to zlapal,
czytanie kodu nie. Kazdy krok bramki zakladajacy, ze badana rzecz SIE UDA,
musi byc osloniety — inaczej bramka pada zamiast orzec.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRAMKA = REPO / "tools" / "test-model-catalog.py"
PYTHON = str(REPO / "venv" / "bin" / "python3")
if not Path(PYTHON).exists():          # ⚠️ NIE `sys.executable` — przy aktywnym
    PYTHON = "python3"                 # cudzym venv badalibysmy inny interpreter

KATALOG = REPO / "src" / "core" / "model_catalog.py"
KONFIG = REPO / "src" / "config.py"
OKNO = REPO / "src" / "gui" / "main_window.py"
DIALOGI = REPO / "src" / "gui" / "dialogs.py"

# Liczba sprawdzen na ZDROWYM kodzie. Rozna liczba przy sabotazu = bramka
# urwala sie w polowie i jej wynik nie mowi nic o asercjach.
OCZEKIWANE = 111

# (plik, opis, szukane, zamiennik) - kotwice UNIKALNE dla badanego miejsca
WARIANTY = {
    # PRZYCZYNA ZRODLOWA usterki z 2026-09-14 — bez tego wariantu bramka nie
    # dowodzi niczego o tym, co realnie sie zepsulo.
    "S1": (KATALOG, "czyscik komorek znowu zostawia odwrotne apostrofy",
           'text = text.replace("**", "").replace("`", "").replace("\\\\", "")',
           'text = text.replace("**", "").replace("\\\\", "")'),
    "S2": (KATALOG, "wzorzec ceny nie pasuje do niczego",
           '_PRICE_RE = re.compile(r"\\$\\s*([\\d.]+)\\s*/\\s*(input|output)", re.I)',
           '_PRICE_RE = re.compile(r"NIE-MA-TAKIEJ-CENY")'),
    "S3": (KATALOG, "zdjeta bramka przytomnosci (parser na smieciach udaje sukces)",
           "    if len(usable) < 2:",
           "    if False:"),
    "S4": (KATALOG, "nieudana proba NIE zostawia sladu (powrot do cichej awarii)",
           "        record_failure(cache_file, str(exc))",
           "        pass  # SABOTAZ"),
    "S5": (KONFIG, "podpowiedz o koszcie zawsze pusta",
           "    if not mine or not ref:",
           "    if True:"),
    "S6": (KONFIG, "mnoznik liczony z jednej stawki (rozjechane proporcje zmyslone)",
           "    if abs(r_in - r_out) <= 0.05:",
           "    if True:"),
    "S7": (OKNO, "cicha awaria znowu milczy bez konca (brak wolania ostrzezenia)",
           "        self._maybe_warn_models_stale(msg)",
           "        pass  # SABOTAZ"),
    "S8": (DIALOGI, "etykieta kosztu nie odswieza sie przy zmianie modelu",
           "        self.model_combo.currentIndexChanged.connect(self._update_model_cost_label)",
           "        pass  # SABOTAZ"),
    "S9": (KONFIG, "stary plik podreczny znowu przykrywa wartosc wbudowana",
           "    if age_days is None:\n        return False",
           "    if age_days is None:\n        return True  # SABOTAZ"),
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
