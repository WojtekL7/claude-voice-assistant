#!/usr/bin/env python3
"""SABOTAŻ bramki `test-read-last-screen.py` — czy ona w ogóle ROZRÓŻNIA?

Zielony zestaw nie dowodzi niczego, dopóki nie wiadomo, że czerwienieje na
zepsutym kodzie. Każdy wariant psuje JEDNĄ własność i sprawdza, ile asercji padło.

⛔ JEDEN WARIANT = JEDNO WYWOŁANIE. Limit czasu nakładaj na pojedyncze
uruchomienie, NIGDY na pętlę po wariantach — pętla ubita w połowie zostawia
sabotaż w kodzie (zdarzyło się w tym projekcie trzy razy).
⛔ Przywracamy z PAMIĘCI PROCESU (`finally`), nie z gita: kod bywa jeszcze
niezacommitowany, więc `git checkout` skasowałby dorobek sesji. Na końcu
wypisujemy sha256 przed/po jako DOWÓD przywrócenia.

Użycie:
    python3 -B tools/sabotaz-read-last-screen.py --kotwice     # czy wzorce pasują
    python3 -B tools/sabotaz-read-last-screen.py <wariant>     # jeden sabotaż
"""
import hashlib
import os
import shutil
import subprocess
import sys

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MW = os.path.join(KORZEN, 'src', 'gui', 'main_window.py')
TC = os.path.join(KORZEN, 'src', 'core', 'text_cleaner.py')
HTML = os.path.join(KORZEN, 'src', 'assets', 'web', 'terminal.html')
BRAMKA = os.path.join(KORZEN, 'tools', 'test-read-last-screen.py')

# wariant -> (plik, szukaj, zastap, opis)
WARIANTY = {
    'bez-ogona': (
        MW,
        "        ogon = czysty[-TERMINAL_SCREEN_TAIL_CHARS:]",
        "        ogon = ''  # SABOTAZ: powrot do oddawania pustki",
        "TOR 3 wyciety — wraca CISZA zgłoszona przez usera",
    ),
    'bez-naprawy-kodowania': (
        MW,
        "        czysty = repair_terminal_mojibake(surowy)",
        "        czysty = surowy  # SABOTAZ: porownanie na surowych bajtach",
        "kotwica porównywana PRZED naprawą mojibake",
    ),
    'bez-progu-ekstraktora': (
        MW,
        "        if len(wyluskane) >= 40 and (len(wyluskane) >= 200 or widoczne < 400):",
        "        if len(wyluskane) >= 40:  # SABOTAZ: ufamy okruchom",
        "próg zaufania do ekstraktora zdjęty — czyta 79 zn. z 490",
    ),
    'bez-siatki': (
        MW,
        "        if siatka and siatka.strip():\n            return siatka, \"siatka\"",
        "        if False:\n            return siatka, \"siatka\"  # SABOTAZ: ignoruj siatke",
        "siatka xterma ignorowana — zostaje bufor 5000 zn.",
    ),
    'filtr-nic-nie-robi': (
        TC,
        "    if not text:\n        return text\n    wynik = []",
        "    if True:\n        return text  # SABOTAZ: filtr przepuszcza smieci\n    wynik = []",
        "filtr ozdób TUI wyłączony — lektor czyta 'Working…'",
    ),
    'wzorzec-wklejony-inline': (
        MW,
        "    def _screen_source(self, tab):",
        "    _TUI_NOISE_LINE_RE = re.compile(r'^x$')  # SABOTAZ: druga kopia wzorca\n\n    def _screen_source(self, tab):",
        "wzorzec ozdób wklejony inline w drugim pliku",
    ),
    'bez-mostka-js': (
        HTML,
        "    window.__termScreenText = function (maxLines) {",
        "    window.__termScreenTextWYLACZONE = function (maxLines) {",
        "funkcja JS czytająca siatkę usunięta",
    ),
}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]


def wyczysc_cache():
    # ⛔ __pycache__ potrafi podsunąć STARY bytecode wariantom dającym plik tej
    # samej długości w tej samej sekundzie — trzy różne sabotaże raportowały
    # wtedy identyczny wynik. Kasujemy przed każdym przebiegiem.
    for katalog, podkatalogi, _ in os.walk(os.path.join(KORZEN, 'src')):
        for d in list(podkatalogi):
            if d == '__pycache__':
                shutil.rmtree(os.path.join(katalog, d), ignore_errors=True)


def przebieg():
    srodowisko = dict(os.environ)
    for zmienna in ('LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
        srodowisko.pop(zmienna, None)
    srodowisko['QT_QPA_PLATFORM'] = 'offscreen'
    w = subprocess.run([sys.executable, '-B', BRAMKA], capture_output=True,
                       text=True, cwd=KORZEN, env=srodowisko)
    wyj = w.stdout + w.stderr
    # Liczymy OBIE liczby: same porażki nie wystarczą — bramka przerwana w połowie
    # daje „0 porażek" wyglądające jak komplet zielonych.
    return wyj.count('[FAIL]'), wyj.count('[OK ]'), w.returncode


def kotwice():
    print("KONTROLA KOTWIC (każda ma pasować DOKŁADNIE raz):")
    zle = 0
    for nazwa, (plik, szukaj, _, _) in WARIANTY.items():
        ile = open(plik, encoding='utf-8').read().count(szukaj)
        print("  %-24s %s  (%d trafień)" % (nazwa, "OK " if ile == 1 else "ZLE", ile))
        if ile != 1:
            zle += 1
    print("\nkotwic niepasujących: %d" % zle)
    return 1 if zle else 0


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        print("Warianty: " + ", ".join(sorted(WARIANTY)))
        return 2
    if sys.argv[1] == '--kotwice':
        return kotwice()
    nazwa = sys.argv[1]
    if nazwa not in WARIANTY:
        print("Nieznany wariant: %s" % nazwa)
        return 2
    plik, szukaj, zastap, opis = WARIANTY[nazwa]

    wyczysc_cache()
    print("== PRZEBIEG ODNIESIENIA (zdrowy kod) ==")
    f0, o0, rc0 = przebieg()
    print("   porażek=%d  wykonanych=%d  kod=%d" % (f0, o0, rc0))

    oryginal = open(plik, encoding='utf-8').read()
    sha_przed = sha(plik)
    try:
        if oryginal.count(szukaj) != 1:
            print("\n⛔ KOTWICA NIE PASUJE (%d trafień) — wariant-widmo, nic nie mierzy."
                  % oryginal.count(szukaj))
            return 3
        zepsuty = oryginal.replace(szukaj, zastap, 1)
        assert zepsuty != oryginal, "sabotaż nic nie zmienił"
        open(plik, 'w', encoding='utf-8').write(zepsuty)
        wyczysc_cache()
        print("\n== SABOTAŻ: %s ==\n   %s" % (nazwa, opis))
        f1, o1, rc1 = przebieg()
        print("   porażek=%d  wykonanych=%d  kod=%d" % (f1, o1, rc1))
    finally:
        open(plik, 'w', encoding='utf-8').write(oryginal)
        wyczysc_cache()

    sha_po = sha(plik)
    print("\n   przywrócenie: sha256 %s -> %s  %s"
          % (sha_przed, sha_po, "ZGODNE" if sha_przed == sha_po else "⛔ ROZJAZD"))
    if o1 < o0 * 0.5:
        print("   ⚠️ UWAGA: bramka wykonała o wiele mniej sprawdzeń (%d z %d) — mogła "
              "przerwać w połowie, a wtedy 'porażki' nic nie znaczą." % (o1, o0))
    print("\n   WYNIK: sabotaż '%s' zapalił %d asercji" % (nazwa, f1))
    return 0 if sha_przed == sha_po else 4


if __name__ == '__main__':
    sys.exit(main())
