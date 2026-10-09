#!/usr/bin/env python3
"""Bramka: STRAŻNIK ODMALOWANIA w WebTerminalu (objaw „pusty pas", 2026-10-09).

Objaw u właściciela: w środku zakładki pusty pas ~30 wierszy, znikający dopiero
po kliknięciu w okno. Pas powstał w chwili, gdy Claude Code dopisał „※ recap".
Kliknięcie naraz odmalowuje nasz ekran I wysyła Claude „wróciłem", więc z objawu
nie wiadomo, czyja wina. `__termRepaintCheck` (terminal.html) rozdziela to w logu:
  A) xterm ma treść w PAMIĘCI, ale nie ma jej na EKRANIE → „roznic_pamiec_vs_ekran>0"
     (i ten przypadek sam naprawia, odmalowując cały widok);
  B) pas jest pusty już w pamięci (Claude go nie narysował) → „dziura_w_pamieci".

Co sprawdza ta bramka (na prawdziwym xterm.js w QtWebEngine, bez ekranu):
  1. ZDROWY ekran (polskie litery, emoji, ramki, kolory) → strażnik MILCZY.
     Najważniejsze: fałszywy alarm przy każdym powrocie do okna zaśmieciłby log
     i zrobił z dowodu szum.
  2. Sabotaż A: wyczyszczone wiersze NA EKRANIE przy pełnej pamięci → wykryte…
  3. …i NAPRAWIONE: kolejne sprawdzenie po odmalowaniu milczy.
  4. Dziura B w samej pamięci → wykryta jako „dziura_w_pamieci", BEZ różnic
     ekranu (czyli dwa przypadki się nie mylą).

SABOTAŻ ZMIERZONY 2026-10-09: usunięcie `term.refresh(...)` ze strażnika → pada [3]
(po „naprawie" ekran nadal ma 16 pustych wierszy) — test pilnuje NAPRAWY, nie tylko logu.

URUCHOMIENIE (Linux, z katalogu projektu):
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH \\
        QT_QPA_PLATFORM=offscreen ./venv/bin/python3 tools/test-terminal-repaint.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PyQt5.QtCore import Qt, QTimer                      # noqa: E402
from PyQt5.QtWidgets import QApplication                 # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_app = QApplication(sys.argv)

from gui.web_terminal import WebTerminal, WEBTERMINAL_LOG, _log   # noqa: E402

MARKER = f"=== BRAMKA ODMALOWANIA pid={os.getpid()} ==="
wyniki = []


def sprawdz(nr, opis, warunek, szczegol=""):
    wyniki.append(bool(warunek))
    print(f"[{'OK ' if warunek else 'FAIL'}] {nr}. {opis}"
          + (f"  ({szczegol})" if szczegol else ""))


def wpisy(tag):
    """Wpisy strażnika z danym tagiem, ZA naszym znacznikiem w logu."""
    tekst = WEBTERMINAL_LOG.read_text(encoding="utf-8", errors="replace").split(MARKER)[-1]
    return re.findall(r"odmalowanie\[" + re.escape(tag) + r"\][^\n]*", tekst)


def liczba(wpis, klucz):
    m = re.search(klucz + r"=(\d+)", wpis)
    return int(m.group(1)) if m else None


def js(kod):
    term.view.page().runJavaScript(kod)


_log(MARKER)
term = WebTerminal()
term.set_shell_program("/bin/cat")     # cisza z PTY — treść piszemy sami
term.resize(1000, 600)
term.set_font("Ubuntu Mono", 13)
term.show()

# Ekran jak u Claude: ramki, polskie litery, emoji (szerokie), kolory, pogrubienie.
ZDROWY = ["\x1b[2J\x1b[H"] + [
    f"\x1b[1;3{i % 7 + 1}m{i:2}\x1b[0m │ zażółć gęślą jaźń 🔊 ─── wiersz {i} ✓ \x1b[7mODWR\x1b[0m"
    for i in range(1, 26)
]
CRLF = "\r\n"
DZIURA = "\x1b[2J\x1b[H" + "gora ekranu\r\n" + "\r\n" * 15 + "dol ekranu — recap"


def krok_zdrowy():
    js(f"term.write({json.dumps(CRLF.join(ZDROWY))});")
    QTimer.singleShot(600, lambda: term.repaint_check("czysty"))


def krok_sabotaz_a():
    # Ekran traci wiersze 5..20, pamięć zostaje pełna — dokładnie przypadek A.
    js("var r=document.querySelector('#terminal .xterm-rows');"
       "for (var i=5;i<=20;i++) r.children[i].textContent='';")
    QTimer.singleShot(100, lambda: term.repaint_check("sabotazA"))
    QTimer.singleShot(700, lambda: term.repaint_check("poNaprawie"))


def krok_dziura():
    js(f"term.write({json.dumps(DZIURA)});")
    QTimer.singleShot(600, lambda: term.repaint_check("dziura"))


def podsumuj():
    czysty = wpisy("czysty")
    sprawdz(1, "zdrowy ekran → strażnik MILCZY (brak fałszywego alarmu)",
            term._frontend_ready and not czysty,
            f"frontend_ready={term._frontend_ready} wpisy={czysty}")

    a = wpisy("sabotazA")
    roznic = liczba(a[0], "roznic_pamiec_vs_ekran") if a else None
    sprawdz(2, "KONTROLA NEGATYWNA: 16 wyczyszczonych wierszy ekranu przy pełnej pamięci WYKRYTE",
            roznic == 16, f"roznic={roznic} wpis={a}")

    po = wpisy("poNaprawie")
    sprawdz(3, "…i NAPRAWIONY odmalowaniem (kolejne sprawdzenie milczy)",
            bool(a) and not po, f"wpisy={po}")

    d = wpisy("dziura")
    dz = liczba(d[0], "dziura_w_pamieci") if d else None
    rz = liczba(d[0], "roznic_pamiec_vs_ekran") if d else None
    sprawdz(4, "dziura w PAMIĘCI (przypadek B) wykryta, bez różnic ekranu",
            dz is not None and dz >= 8 and rz == 0, f"dziura={dz} roznic={rz}")

    zle = wyniki.count(False)
    print(f"\n{'=' * 58}\nWYNIK: {wyniki.count(True)}/{len(wyniki)} OK, {zle} FAIL")
    term.shutdown()
    _app.exit(1 if zle else 0)


QTimer.singleShot(3000, krok_zdrowy)
QTimer.singleShot(4500, krok_sabotaz_a)
QTimer.singleShot(6000, krok_dziura)
QTimer.singleShot(7500, podsumuj)
sys.exit(_app.exec_())
