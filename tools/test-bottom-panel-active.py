#!/usr/bin/env python3
"""Bramka: kolor DOLNEGO PANELU zgodny ze stanem okna po zmianie zakładki.

ZGŁOSZENIE 2026-10-14 (zrzut 16:52): okno aktywne, a dolny panel zakładki CRM
w kolorze „okno nieaktywne" (`inactive_panel_bg`). Każda zakładka ma WŁASNY
panel; kolor zmieniało tylko `changeEvent` i tylko na panelu bieżącej
zakładki. Zmiana zakładki przy nieaktywnym oknie zostawiała panel poprzedniej
„nieaktywny" na stałe — po powrocie do niej nikt go nie przemalowywał.

⚠️ Bramka nie buduje całego MainWindow (ciężki): tworzy pusty obiekt klasy
MainWindow bez konstruktora, daje mu PRAWDZIWE zakładki AgentTab i woła
PRAWDZIWE metody `changeEvent`, `_update_current_tab_references`,
`_paint_bottom_panels`. Kolor MIERZY na wyrenderowanych pikselach panelu.

URUCHOMIENIE:
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u CLAUDE_CODE_SUBAGENT_MODEL \\
        QT_QPA_PLATFORM=offscreen venv/bin/python -B tools/test-bottom-panel-active.py
Sabotaż: tools/sabotaz-bottom-panel-active.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PyQt5.QtCore import Qt, QEvent                          # noqa: E402
from PyQt5.QtGui import QPixmap                              # noqa: E402
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_app = QApplication(sys.argv)

from gui.agent_tab import AgentTab                           # noqa: E402
from gui.main_window import MainWindow, DEFAULT_SKIN_COLORS  # noqa: E402

wyniki = []


def spr(nr, opis, war, szczegol=""):
    wyniki.append(bool(war))
    print(f"[{'OK ' if war else 'FAIL'}] {nr}. {opis}" + (f"  ({szczegol})" if szczegol else ""))


AKTYWNY = DEFAULT_SKIN_COLORS["bottom_panel_bg"].lower()
NIEAKTYWNY = DEFAULT_SKIN_COLORS["inactive_panel_bg"].lower()
assert AKTYWNY != NIEAKTYWNY, "skórka ma oba kolory równe — bramka nic nie odróżni"


def kolor(tab) -> str:
    """Barwa tła panelu z pikseli (lewa krawędź, połowa wysokości — tam nie ma przycisków)."""
    p = tab.bottom_panel
    # ⚠️ NIE resize + stały punkt: panel w ukrytym QSplitterze przyjmuje
    # resize z opóźnieniem — pierwszy pomiar miał jeszcze 100×24, punkt (3,40)
    # wypadał POZA obrazek i czytał czerń (3 fałszywe FAIL przy pisaniu bramki).
    # Mierzymy przy lewej krawędzi, w połowie RZECZYWISTEJ wysokości.
    pix = QPixmap(p.size())
    pix.fill(Qt.transparent)
    p.render(pix)
    c = pix.toImage().pixelColor(2, p.height() // 2)
    return "#%02x%02x%02x" % (c.red(), c.green(), c.blue())


def nazwa(k):
    return {AKTYWNY: "aktywny", NIEAKTYWNY: "NIEAKTYWNY"}.get(k, k)


# ---- obiekt okna bez ciężkiego konstruktora -----------------------------------
okno = MainWindow.__new__(MainWindow)
QMainWindow.__init__(okno)
okno.skin_colors = dict(DEFAULT_SKIN_COLORS)
okno.terminal_backend = None
okno.bottom_panel = None
okno.tab_widget = QTabWidget()
okno.agent_tabs = {}
for aid in ("A", "B", "C"):
    t = AgentTab({"id": aid, "name": aid, "working_directory": ROOT})
    t.apply_styles(okno.skin_colors, {})
    okno.agent_tabs[aid] = t
    okno.tab_widget.addTab(t, aid)
A, B, C = (okno.agent_tabs[k] for k in "ABC")

_stan = {"aktywne": True}
okno.isActiveWindow = lambda: _stan["aktywne"]       # podmiana na instancji


def fokus(aktywne: bool):
    """Okno zyskuje / traci fokus → Qt wysyła ActivationChange."""
    _stan["aktywne"] = aktywne
    okno.changeEvent(QEvent(QEvent.ActivationChange))


def przelacz(tab):
    okno.tab_widget.setCurrentWidget(tab)
    okno._update_current_tab_references()


przelacz(A)
fokus(True)
spr(1, "okno aktywne → panel bieżącej zakładki w kolorze zwykłym",
    kolor(A) == AKTYWNY, nazwa(kolor(A)))

fokus(False)
spr(2, "KONTROLA ODWROTNA: okno nieaktywne → panel bieżącej zakładki jaśniejszy",
    kolor(A) == NIEAKTYWNY, nazwa(kolor(A)))

# Scenariusz zgłoszenia: zakładka zmienia się, ZANIM okno dostanie fokus.
przelacz(B)
spr(3, "zmiana zakładki przy nieaktywnym oknie: nowa zakładka też „nieaktywna”",
    kolor(B) == NIEAKTYWNY, nazwa(kolor(B)))
fokus(True)
spr(4, "potem okno aktywne → nowa zakładka w kolorze zwykłym",
    kolor(B) == AKTYWNY, nazwa(kolor(B)))
przelacz(A)
spr(5, "SEDNO: powrót do poprzedniej zakładki → kolor zwykły (był zostawał „nieaktywny”)",
    kolor(A) == AKTYWNY, nazwa(kolor(A)))
spr(6, "żadna zakładka nie zostaje „nieaktywna” przy aktywnym oknie",
    all(kolor(t) == AKTYWNY for t in (A, B, C)),
    ", ".join(f"{k}={nazwa(kolor(t))}" for k, t in okno.agent_tabs.items()))

# Zmiana skórki przy nieaktywnym oknie (apply_styles maluje „aktywny”).
fokus(False)
for t in (A, B, C):
    t.apply_styles(okno.skin_colors, {})
okno._paint_bottom_panels(okno.skin_colors, force=True)
spr(7, "po przemalowaniu skórki przy nieaktywnym oknie bieżący panel dalej „nieaktywny”",
    kolor(A) == NIEAKTYWNY, nazwa(kolor(A)))
spr(8, "…a pozostałe zakładki w kolorze zwykłym",
    kolor(B) == AKTYWNY and kolor(C) == AKTYWNY, f"B={nazwa(kolor(B))} C={nazwa(kolor(C))}")

# Pamięć podręczna nie może zatrzymać koloru po zewnętrznym nadpisaniu (force).
fokus(True)
spr(9, "powrót fokusu po zmianie skórki → kolor zwykły",
    kolor(A) == AKTYWNY, nazwa(kolor(A)))

# Zakładka utworzona w trakcie (apply_styles bez znacznika pamięci podręcznej).
fokus(False)
D = AgentTab({"id": "D", "name": "D", "working_directory": ROOT})
D.apply_styles(okno.skin_colors, {})
okno.agent_tabs["D"] = D
okno.tab_widget.addTab(D, "D")
przelacz(D)
spr(10, "nowa zakładka otwarta przy nieaktywnym oknie → „nieaktywna”",
    kolor(D) == NIEAKTYWNY, nazwa(kolor(D)))

padle = wyniki.count(False)
print(f"\nPODSUMOWANIE: wykonane={len(wyniki)} padle={padle}")
sys.exit(1 if padle else 0)
