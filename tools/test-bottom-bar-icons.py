#!/usr/bin/env python3
"""Bramka: DOLNY PASEK przycisków — kolejność + styl lupy.

Pilnuje dwóch rzeczy zgłoszonych przez usera 2026-08-04:
  1. lupa stoi na SAMYM KOŃCU paska, za przełącznikiem myszy,
  2. lupa ma CIEMNE tło i jasny glif, jak reszta paska.

Punkt 2 to trzecie wystąpienie tego samego przeoczenia w projekcie: przycisk
nieujęty w `MainWindow._apply_button_icon_styles` zostaje z fabrycznym BIAŁYM
kwadratem Qt. Wcześniej złapało to `mouse_mode_btn` i `repair_terminal_btn`.
Zmierzone na zrzucie usera: tło lupy RGB(248,248,248) wobec RGB(23,18,33)
u wszystkich sąsiadów.

⚠️ Test NIE opiera się na czytaniu źródeł — buduje PRAWDZIWY `AgentTab`
(terminal powstaje dopiero w `activate()`, więc konstrukcja jest tania i nie
uruchamia powłoki) i woła PRAWDZIWĄ metodę `MainWindow._apply_button_icon_style`,
a wynik MIERZY na wyrenderowanych pikselach.

URUCHOMIENIE (z katalogu projektu):
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH \
        QT_QPA_PLATFORM=offscreen ./venv/bin/python3 tools/test-bottom-bar-icons.py

⚠️ `env -u …` obowiązkowe przy uruchamianiu z Claude Code (eksportuje własne Qt).

WYNIKI SABOTAŻU — URUCHOMIONE I ZMIERZONE 2026-08-04:
  1. usunięcie wywołania `_apply_button_icon_style(tab.search_btn, …)` → padają
     [4] i [5]; jasność tła lupy skacze **24 → 252** przy sąsiedzie 24, czyli
     test odtwarza objaw usera co do liczby (na jego zrzucie było 248 vs 24).
  2. przeniesienie CAŁEGO bloku lupy z powrotem przed `quick_actions_btn` →
     padają [1] i [2] (kolejność: … add_media → search → quick_actions → mouse).
⚠️ Pułapka przy powtarzaniu sabotażu 2: przeniesienie SAMEJ linii
   `layout.addWidget(self.search_btn)` bez bloku tworzącego przycisk daje
   `AttributeError`, a nie inną kolejność — test wtedy nie „wykrywa regresji",
   tylko wywala się na błędzie kodu. Przenoś cały blok.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PyQt5.QtCore import Qt                                  # noqa: E402
from PyQt5.QtGui import QPixmap                              # noqa: E402
from PyQt5.QtWidgets import QApplication                     # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_app = QApplication(sys.argv)

from gui import theme                                        # noqa: E402
from gui.agent_tab import AgentTab                           # noqa: E402
from gui.main_window import MainWindow, DEFAULT_SKIN_COLORS  # noqa: E402

wyniki = []


def spr(nr, opis, war, szczegol=""):
    wyniki.append(bool(war))
    print(f"[{'OK ' if war else 'FAIL'}] {nr}. {opis}" + (f"  ({szczegol})" if szczegol else ""))


def jasnosc_tla(przycisk) -> int:
    """Średnia jasność LEWEGO GÓRNEGO rogu przycisku = jego tło (nie glif)."""
    przycisk.resize(44, 44)
    pix = QPixmap(przycisk.size())
    pix.fill(Qt.transparent)
    przycisk.render(pix)
    obraz = pix.toImage()
    px = obraz.pixelColor(6, 6)          # róg — glif siedzi na środku
    return (px.red() + px.green() + px.blue()) // 3


tab = AgentTab({"id": "test", "name": "Test", "working_directory": ROOT})

# ---- 1-2. KOLEJNOŚĆ na pasku -------------------------------------------------
def znajdz_uklad(uklad, szukany):
    """Układ, który BEZPOŚREDNIO zawiera dany widżet (pasek jest zagnieżdżony)."""
    if uklad is None:
        return None
    for i in range(uklad.count()):
        it = uklad.itemAt(i)
        if it.widget() is szukany:
            return uklad
        if it.layout() is not None:
            zn = znajdz_uklad(it.layout(), szukany)
            if zn is not None:
                return zn
        if it.widget() is not None and it.widget().layout() is not None:
            zn = znajdz_uklad(it.widget().layout(), szukany)
            if zn is not None:
                return zn
    return None


# ⚠️ NIE zaczynaj od `tab.layout()` — pasek wisi w QSplitterze, a ten trzyma
# dzieci POZA układem, więc rekurencja od korzenia go nie znajdzie (sprawdzone).
uklad = znajdz_uklad(tab.search_btn.parentWidget().layout(), tab.search_btn)
assert uklad is not None, "nie znaleziono układu z przyciskiem lupy"
kolejnosc = []
for i in range(uklad.count()):
    w = uklad.itemAt(i).widget()
    if w is None:
        continue
    for nazwa in ("dictate_btn", "read_btn", "pause_btn", "stop_btn", "copy_btn",
                  "clear_input_btn", "add_media_btn", "quick_actions_btn",
                  "mouse_mode_btn", "search_btn", "repair_terminal_btn", "send_btn"):
        if getattr(tab, nazwa, None) is w:
            kolejnosc.append(nazwa)
print("kolejność w układzie:", " → ".join(kolejnosc), "\n")

widoczne = [n for n in kolejnosc if not getattr(tab, n).isHidden() or n != "repair_terminal_btn"]
widoczne = [n for n in kolejnosc if n != "repair_terminal_btn"]   # ten jest ukryty
spr(1, "lupa jest OSTATNIM widocznym przyciskiem paska",
    widoczne and widoczne[-1] == "search_btn", f"ostatni = {widoczne[-1] if widoczne else '—'}")
spr(2, "lupa stoi ZA przełącznikiem myszy",
    "mouse_mode_btn" in kolejnosc and "search_btn" in kolejnosc
    and kolejnosc.index("search_btn") > kolejnosc.index("mouse_mode_btn"),
    f"mysz={kolejnosc.index('mouse_mode_btn')} lupa={kolejnosc.index('search_btn')}")

# ---- 3. Klucz skórki ---------------------------------------------------------
# ⚠️ PRZESTARZAŁA PREMISA (2026-08-28): ta asercja wymagała, żeby lupa była
# BIELĄ motywu. Premisa wygasła — user zgłosił, że mikrofon, X i błyskawica są
# „bardziej białe niż pozostałe”, i zdecydował, że ikony paska mają trzymać
# JEDNĄ przygaszoną tonację. Nie odwracamy asercji na ślepo: pytamy, czego
# pilnowała (że klucz ISTNIEJE i ma sensowny kolor motywu) i zastępujemy ją
# REGUŁĄ mocniejszą niż poprzednia — wszystkie ikony niosące samą funkcję mają
# TEN SAM odcień, a wyjątki są wymienione z nazwy i z powodem.
IKONY_PASKA = ('dictate', 'read', 'copy', 'clear_input', 'add_media',
               'quick_actions', 'search')
_tony = {k: DEFAULT_SKIN_COLORS.get(f"icon_{k}_color") for k in IKONY_PASKA}
spr(3, "wszystkie ikony paska niosące FUNKCJĘ mają jedną tonację",
    len(set(_tony.values())) == 1 and set(_tony.values()) == {theme.TEXT_DIM},
    f"rozjazd: {_tony}")
spr("3b", "cztery zgłoszone przez usera zeszły z prawie bieli",
    all(_tony[k] != theme.TEXT for k in ('dictate', 'clear_input', 'quick_actions', 'search')),
    f"{_tony}")
spr("3c", "kolory ZNACZENIOWE nietknięte (pauza=akcent, stop=czerwień, wyślij=biel)",
    DEFAULT_SKIN_COLORS.get("icon_pause_color") == theme.ACCENT_LIGHT
    and DEFAULT_SKIN_COLORS.get("icon_stop_color") == theme.DANGER
    and DEFAULT_SKIN_COLORS.get("icon_send_color") == "#ffffff",
    "ktoś ujednolicił kolor niosący STAN — to gasi sygnał")

# Gałki przełącznika „Auto-czytaj odpowiedzi” — ta biała kropka ze zgłoszenia.
import re as _re
_ICONS = os.path.join(ROOT, "src", "assets", "icons")


def _fill(nazwa):
    with open(os.path.join(_ICONS, nazwa), encoding="utf-8") as fh:
        return _re.findall(r'fill="(#[0-9a-fA-F]{6})"', fh.read())


def _jasnosc(hexcol):
    h = hexcol.lstrip("#")
    return sum(int(h[i:i + 2], 16) for i in (0, 2, 4)) / 3


_off_tor, _off_galka = _fill("toggle-off.svg")
_on_tor, _on_galka = _fill("toggle-on.svg")

spr("3d", "gałka WYŁĄCZONEGO przełącznika ma tonację przycisków (nie biel)",
    _off_galka.lower() == theme.TEXT_DIM.lower(), f"{_off_galka} vs {theme.TEXT_DIM}")
spr("3e", "gałka WŁĄCZONEGO przełącznika nie jest już czystą bielą",
    _on_galka.lower() != "#ffffff", _on_galka)
# ⚠️ Na fiolecie nie wolno zejść do TEXT_DIM: różnica byłaby 10/255, poniżej
# progu 20 zapisanego w projekcie dla odcienia niosącego SYGNAŁ — kropka zlałaby
# się z tłem i user przestałby widzieć, czy auto-czytanie działa.
spr("3f", "...ale zachowuje margines kontrastu na fioletowym torze (≥20/255)",
    abs(_jasnosc(_on_galka) - _jasnosc(_on_tor)) >= 20,
    f"gałka {_on_galka}={_jasnosc(_on_galka):.0f}, tor {_on_tor}={_jasnosc(_on_tor):.0f}, "
    f"różnica {abs(_jasnosc(_on_galka) - _jasnosc(_on_tor)):.0f}")
spr("3g", "gałka wyłączonego też jest widoczna na ciemnym torze (kontrola odwrotna)",
    abs(_jasnosc(_off_galka) - _jasnosc(_off_tor)) >= 20,
    f"różnica {abs(_jasnosc(_off_galka) - _jasnosc(_off_tor)):.0f}")


# ---- 4-6. KOLOR — mierzony na pikselach --------------------------------------
# ⚠️ Wołamy `_apply_button_icon_styles` (LICZBA MNOGA) — czyli tę samą metodę,
# którą woła aplikacja. Testowanie samego `_apply_button_icon_style` (pojedyncza)
# NIC BY NIE DAŁO: prawdziwym błędem był BRAK WYWOŁANIA dla lupy, a nie zepsuta
# funkcja stylująca. Test musi umieć wykryć DOKŁADNIE tę pomyłkę.
class Atrapa:
    """Minimum, którego potrzebuje prawdziwa `_apply_button_icon_styles`."""
    skin_colors = DEFAULT_SKIN_COLORS
    _apply_button_icon_style = MainWindow._apply_button_icon_style
    _apply_send_button_style = MainWindow._apply_send_button_style

    def __init__(self, zakladka):
        self.agent_tabs = {"test": zakladka}


przed = jasnosc_tla(tab.search_btn)                      # stan BEZ stylowania
MainWindow._apply_button_icon_styles(Atrapa(tab))        # tak robi aplikacja
po = jasnosc_tla(tab.search_btn)
sasiad = jasnosc_tla(tab.copy_btn)

print(f"\njasność tła lupy: przed stylowaniem={przed}, po={po}; sąsiad (kopiuj)={sasiad}\n")

spr(4, "po stylowaniu tło lupy jest CIEMNE (nie biały kwadrat)", po < 60, f"jasność={po}")
spr(5, "tło lupy zgadza się z sąsiednim przyciskiem", abs(po - sasiad) <= 6,
    f"lupa={po} kopiuj={sasiad}")
spr(6, "KONTROLA NEGATYWNA: bez stylowania tło JEST jasne (miara odróżnia)",
    przed > 200, f"jasność bez stylu={przed}")

zle = wyniki.count(False)
print(f"\n{'=' * 58}\nWYNIK: {wyniki.count(True)}/{len(wyniki)} OK, {zle} FAIL")
sys.exit(1 if zle else 0)
