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
import time

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


def barwa_ikony(przycisk) -> str:
    """Dominująca barwa NIEPRZEZROCZYSTYCH pikseli ikony przycisku, jako `#rrggbb`.

    ⛔ Ta miara istnieje, bo poprzednia wersja bramki pytała o ARKUSZ STYLÓW
    (`color:`), a ikony paska to OBRAZKI (`QIcon`) — arkusz ich nie dotyczy.
    Dzięki temu bramka świeciła na zielono nad stanem, w którym ikona zostawała
    szara na fioletowym tle (zgłoszenie właściciela 2026-09-15). Pytaj o PIKSELE
    ikony, nigdy o deklarację w arkuszu.
    """
    ikona = przycisk.icon()
    if ikona.isNull():
        return ""
    obraz = ikona.pixmap(22, 22).toImage()
    liczniki = {}
    for y in range(obraz.height()):
        for x in range(obraz.width()):
            px = obraz.pixelColor(x, y)
            if px.alpha() < 200:          # obrys jest cienki, tło przezroczyste
                continue
            klucz = "#%02x%02x%02x" % (px.red(), px.green(), px.blue())
            liczniki[klucz] = liczniki.get(klucz, 0) + 1
    if not liczniki:
        return ""
    return max(liczniki.items(), key=lambda kv: kv[1])[0]


def podobna_barwa(a: str, b: str, tolerancja: int = 8) -> bool:
    """Czy dwie barwy to ta sama barwa z dokładnością do rysowania?

    ⚠️ Nie porównuj ikon dosłownie: renderer SVG wygładza krawędzie, więc
    dominujący piksel bywa o 1-2 jednostki obok żądanej wartości (zmierzone:
    prosiliśmy o #f0616d, na obrazku wyszło #f0606c). Tolerancja jest mała,
    więc nadal odróżnia czerwień od szarości ikony spoczynkowej (#9b93a8).
    """
    if not a or not b:
        return False
    a, b = a.lstrip("#"), b.lstrip("#")
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tolerancja
               for i in (0, 2, 4))


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

# ---- 3h-3k. DWA SYGNAŁY STANU OKNA — próg WYŻSZY niż ogólne 20 ---------------
# ⛔ POWÓD OSOBNEGO, WYŻSZEGO PROGU (zgłoszenie właściciela 2026-09-14): oba te
# sygnały MIEŚCIŁY SIĘ w regule „≥20/255" — zakładka miała 26, panel nieaktywny
# 31 — a mimo to zgłosił OBA naraz jako za słabe. Na tle o jasności 14/255
# dwadzieścia punktów to za mało, żeby cokolwiek było widać. Ogólne 20 zostaje
# podłogą dla wszystkich sygnałów; TE DWA mają własny, wyższy próg.
PROG_SYGNALU_OKNA = 40

_tlo_paska = _jasnosc(theme.BG_PANEL)
_roznica_zakladki = _jasnosc(theme.TAB_ACTIVE) - _tlo_paska
_roznica_panelu = _jasnosc(theme.SURFACE_INACTIVE) - _tlo_paska

spr("3h", f"wybrana zakładka odcina się od pozostałych (≥{PROG_SYGNALU_OKNA}/255)",
    _roznica_zakladki >= PROG_SYGNALU_OKNA,
    f"{theme.TAB_ACTIVE}={_jasnosc(theme.TAB_ACTIVE):.0f} wobec paska "
    f"{theme.BG_PANEL}={_tlo_paska:.0f}, różnica {_roznica_zakladki:.0f}")
spr("3i", f"panel przy NIEAKTYWNYM oknie jest wyraźnie jaśniejszy (≥{PROG_SYGNALU_OKNA}/255)",
    _roznica_panelu >= PROG_SYGNALU_OKNA,
    f"{theme.SURFACE_INACTIVE}={_jasnosc(theme.SURFACE_INACTIVE):.0f} wobec "
    f"{theme.BG_PANEL}={_tlo_paska:.0f}, różnica {_roznica_panelu:.0f}")
# KONTROLE ODWROTNE — sygnał ma być JAŚNIEJSZY, nie ciemniejszy, i ma zostać
# fioletem. Bez nich „mocniejszy kontrast" dałoby się spełnić czernią albo
# szarością, czyli wypaść z rodziny kolorów całego programu.
spr("3j", "oba sygnały są JAŚNIEJSZE od tła, nie ciemniejsze",
    _roznica_zakladki > 0 and _roznica_panelu > 0,
    f"zakładka {_roznica_zakladki:.0f}, panel {_roznica_panelu:.0f}")


def _jest_fioletem(hexcol):
    """Składowa niebieska wyraźnie nad czerwoną, a czerwona nad zieloną."""
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return b > r > g


spr("3k", "oba sygnały zostają w rodzinie „Vibe Purple” (zmienia się JASNOŚĆ)",
    _jest_fioletem(theme.TAB_ACTIVE) and _jest_fioletem(theme.SURFACE_INACTIVE),
    f"{theme.TAB_ACTIVE}, {theme.SURFACE_INACTIVE}")


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

# ---- 7-11. SZYBKIE AKCJE wyglądają i ZACHOWUJĄ SIĘ jak sąsiedzi -------------
# Zgłoszenie właściciela 2026-09-12: „jest inny niż pozostałe, inaczej się
# zachowuje, jak na niego najadę". Przyczyna: to JEDYNY QToolButton na pasku
# (rozwija menu), a wspólna reguła mówiła `QPushButton {…}` i po prostu go
# OMIJAŁA — Qt nie zgłasza wtedy błędu. Dostał więc własny, ręczny arkusz,
# który rozjechał się z resztą (tło przezroczyste, róg 12 zamiast 10, ikona 20
# zamiast 22, a po najechaniu zalewało się tło zamiast rozświetlić ramkę).
#
# ⚠️ Porównujemy z SĄSIADEM, nie z wpisanymi na sztywno kolorami: paleta jest
# pokrętłem właściciela w skórce, więc test pilnujący konkretnych hexów
# zapaliłby się na czerwono w dniu, w którym zmieni sobie skórkę.


def reguly(widget):
    """Arkusz widżetu → {stan: {własność: wartość}}.

    Nazwę klasy ZDEJMUJEMY (`QToolButton:hover` → `:hover`), bo zestawiamy ze
    sobą dwa różne klocki Qt — pytamy o WYGLĄD, nie o nazwę klasy.
    """
    out = {}
    for blok in _re.finditer(r'([A-Za-z]+Button(?:::?[a-z-]+)?)\s*\{([^}]*)\}',
                             widget.styleSheet()):
        stan = blok.group(1).split("Button", 1)[1]
        out[stan] = {k.strip(): v.strip()
                     for k, v in (l.split(":", 1) for l in blok.group(2).split(";")
                                  if ":" in l)}
    return out


_qa = reguly(tab.quick_actions_btn)
_sas = reguly(tab.add_media_btn)          # dowolny sąsiad z tego samego malarza

jasn_qa = jasnosc_tla(tab.quick_actions_btn)
print(f"jasność tła szybkich akcji={jasn_qa}, sąsiad (dodaj plik)={jasnosc_tla(tab.add_media_btn)}\n")

spr(7, "tło szybkich akcji zgadza się z sąsiednim przyciskiem (piksele)",
    abs(jasn_qa - jasnosc_tla(tab.add_media_btn)) <= 6,
    f"szybkie={jasn_qa} sąsiad={jasnosc_tla(tab.add_media_btn)}")

# `color` (barwa samej ikonki) MA prawo się różnić — każdy przycisk ma własny
# klucz w skórce. Reszta wyglądu spoczynkowego ma być identyczna.
_poza_ikona = lambda d: {k: v for k, v in d.items() if k != "color"}
spr(8, "spoczynek: tło, ramka, zaokrąglenie i wielkość — jak u sąsiada",
    _poza_ikona(_qa.get("", {})) == _poza_ikona(_sas.get("", {})),
    f"szybkie={_poza_ikona(_qa.get('', {}))} vs sąsiad={_poza_ikona(_sas.get('', {}))}")

spr(9, "po najechaniu zachowuje się jak sąsiad (to samo tło I ta sama ramka)",
    _qa.get(":hover") == _sas.get(":hover") and _qa.get(":hover"),
    f"szybkie={_qa.get(':hover')} vs sąsiad={_sas.get(':hover')}")

# To jest DOKŁADNIE to, co widział właściciel: u sąsiadów ramka zapala się
# akcentem, a szybkim akcjom zostawała martwa. Asercja trzyma REGUŁĘ (ramka
# zmienia się po najechaniu), nie konkretny fiolet.
spr("9b", "...czyli ramka po najechaniu JEST inna niż w spoczynku",
    _qa.get(":hover", {}).get("border") not in (None, _qa.get("", {}).get("border")),
    f"spoczynek={_qa.get('', {}).get('border')} hover={_qa.get(':hover', {}).get('border')}")

spr(10, "strzałka rozwijania menu pozostaje UKRYTA (inaczej odstaje w drugą stronę)",
    _qa.get("::menu-indicator", {}).get("image") == "none",
    f"{_qa.get('::menu-indicator')}")

spr(11, "KONTROLA ODWROTNA: sąsiad (QPushButton) NIE dostaje reguły menu",
    "::menu-indicator" not in _sas,
    f"{list(_sas.keys())}")


# ⛔ ŚLEPA PLAMA ASERCJI 8 i 9, ZMIERZONA SABOTAŻEM — nie usuwaj tej asercji.
# 8 i 9 porównują ZAPISANY arkusz i celowo zdejmują z selektora nazwę klasy
# (żeby dało się zestawić QToolButton z QPushButtonem). Skutkiem ubocznym są
# ŚLEPE na najgroźniejszy błąd z tej rodziny: arkusz napisany dla CUDZEJ klasy.
# Qt taką regułę po prostu IGNORUJE — bez błędu, bez śladu — a 8/9/9b dalej
# świecą na zielono, bo tekst się zgadza. Zmierzone: sabotaż wpisujący selektor
# „QPushButton" na sztywno zapalił tylko [7] i [10]; [8], [9] i [9b] przeszły.
def klasy_arkusza(widget):
    return {m.group(1) for m in _re.finditer(r'([A-Za-z]+Button)(?:::?[a-z-]+)?\s*\{',
                                             widget.styleSheet())}


for _nr, _btn, _opis in (("12", tab.quick_actions_btn, "szybkie akcje"),
                         ("12b", tab.add_media_btn, "sąsiad (kontrola odwrotna)")):
    _wlasna = _btn.metaObject().className()
    spr(_nr, f"arkusz {_opis} jest napisany dla JEGO klasy (inaczej Qt go zignoruje)",
        klasy_arkusza(_btn) == {_wlasna},
        f"w arkuszu {sorted(klasy_arkusza(_btn))}, widżet to {_wlasna}")

# ---- 13. ZIELONY BŁYSK po skopiowaniu — sygnał TAK, własny wygląd NIE --------
# Ten sam rozjazd co przy szybkich akcjach, tylko migał przez 500 ms: własny
# arkusz z przezroczystym tłem i rogiem 12 px. Sygnał (zielona ramka) ZOSTAJE —
# konwencja projektu mówi, że skórka rządzi spoczynkiem, a kod niesie stan.
# Zmienia się tylko to, że reszta wyglądu pochodzi ze WSPÓLNEGO malarza.
_atrapa = Atrapa(tab)
_atrapa._icon = lambda *a, **k: tab.copy_btn.icon()     # błysk podmienia też ikonę
_atrapa._get_current_agent_tab = lambda: tab
_atrapa._flash_button = lambda *a, **k: MainWindow._flash_button(_atrapa, *a, **k)
_atrapa._BUTTON_COLOR_KEYS = MainWindow._BUTTON_COLOR_KEYS
_atrapa._FLASH_COLORS = MainWindow._FLASH_COLORS
_atrapa._BUTTON_ICON_KEYS = MainWindow._BUTTON_ICON_KEYS
_atrapa._repaint_button_icon = lambda t, a, c=None: MainWindow._repaint_button_icon(_atrapa, t, a, c)


def przeczekaj(sekundy):
    """Przepuść PRAWDZIWY zegar Qt — bez tego `QTimer.singleShot` nigdy nie wystrzeli.

    ⚠️ `time.sleep` SAM NIC NIE DA: bramka nie ma pętli zdarzeń, więc trzeba ją
    kręcić ręcznie. Do 2026-09-12 powrót po błysku wołaliśmy tu RĘCZNIE — czyli
    bramka sprawdzała, że „da się wrócić", a NIE że program wraca sam. Dokładnie
    tę różnicę zgłosiłby user jako „przycisk został czerwony".
    """
    koniec = time.monotonic() + sekundy
    while time.monotonic() < koniec:
        _app.processEvents()
        time.sleep(0.02)


MainWindow._flash_copy_success(_atrapa)
_blysk = reguly(tab.copy_btn)

spr(13, "błysk NIESIE SYGNAŁ: ramka jest zielona, nie zwyczajna",
    theme.SUCCESS.lower() in _blysk.get("", {}).get("border", "").lower(),
    f"{_blysk.get('', {}).get('border')}")

_bez_ramki = lambda d: {k: v for k, v in d.items() if k not in ("border", "color")}
spr("13b", "poza ramką błysk wygląda jak zwykły przycisk (tło, róg, wielkość)",
    _bez_ramki(_blysk.get("", {})) == _bez_ramki(_sas.get("", {})),
    f"błysk={_bez_ramki(_blysk.get('', {}))} vs sąsiad={_bez_ramki(_sas.get('', {}))}")

# Kontrola przytomności: PRZED upływem pół sekundy błysk ma jeszcze trwać —
# inaczej asercja niżej przechodziłaby także nad błyskiem, którego nigdy nie było.
przeczekaj(0.2)
spr("13c", "po 0,2 s błysk JESZCZE trwa (miara odróżnia)",
    theme.SUCCESS.lower() in reguly(tab.copy_btn).get("", {}).get("border", "").lower(),
    f"{reguly(tab.copy_btn).get('', {}).get('border')}")

przeczekaj(0.6)
spr("13d", "po pół sekundy przycisk wraca SAM (prawdziwy zegar, nie ręczny reset)",
    _bez_ramki(reguly(tab.copy_btn).get("", {})) == _bez_ramki(_sas.get("", {}))
    and theme.SUCCESS.lower() not in reguly(tab.copy_btn).get("", {}).get("border", "").lower(),
    f"po powrocie={reguly(tab.copy_btn).get('', {})}")

# ---- 13e-13h. BŁYSK MUSI BYĆ WIDOCZNY POD KURSOREM --------------------------
# Zgłoszenie właściciela 2026-09-15: „X nie świeci się na czerwono". Błysk DZIAŁAŁ,
# tylko malował samą ramkę — a zaraz po kliknięciu kursor STOI na przycisku, więc
# reguła `:hover` przemalowywała ramkę na akcent i przykrywała czerwień. Sygnał
# widoczny wyłącznie wtedy, gdy user zabierze mysz, jest sygnałem NIEISTNIEJĄCYM.
_ikona_x_spoczynek = barwa_ikony(tab.clear_input_btn)
MainWindow._flash_button(_atrapa, tab, "clear_input_btn", theme.DANGER)
_blysk_x = reguly(tab.clear_input_btn)

spr("13e", "błysk czyszczenia pola przemalowuje IKONĘ na czerwono (nie samą ramkę)",
    podobna_barwa(barwa_ikony(tab.clear_input_btn), theme.DANGER),
    f"ikona={barwa_ikony(tab.clear_input_btn)} oczekiwano={theme.DANGER}")

spr("13f", "...i błysk WYGRYWA z najechaniem myszą (ramka :hover też niesie sygnał)",
    theme.DANGER.lower() in _blysk_x.get(":hover", {}).get("border", "").lower(),
    f"hover podczas błysku={_blysk_x.get(':hover', {}).get('border')}")

spr("13g", "KONTROLA PRZYTOMNOŚCI: poza błyskiem ramka po najechaniu wraca do akcentu",
    theme.ACCENT.lower() in _sas.get(":hover", {}).get("border", "").lower(),
    f"sąsiad hover={_sas.get(':hover', {}).get('border')}")

przeczekaj(0.6)
spr("13h", "KONTROLA ODWROTNA: po pół sekundy ikona X wraca do barwy ze skórki",
    barwa_ikony(tab.clear_input_btn) == _ikona_x_spoczynek
    and not podobna_barwa(_ikona_x_spoczynek, theme.DANGER),
    f"po powrocie={barwa_ikony(tab.clear_input_btn)} spoczynek={_ikona_x_spoczynek}")

# ---- 14-17. „W UŻYCIU" — fiolet trwa tyle, ile trwa używanie ------------------
# Życzenie właściciela 2026-09-12: przycisk ma ZOSTAĆ fioletowy podczas używania,
# a nie mignąć po kliknięciu. Dotyczy: szybkich akcji (otwarte menu), lupy
# (otwarte okno), myszy (włączony tryb zaznaczania) i dodawania mediów (otwarte
# okno wyboru pliku). Kopiuj NIE ma stanu „podczas" — zostaje przy zielonym błysku.
#
# ⛔ PRZECELOWANE 2026-09-15 — WŁAŚCICIEL ODWRÓCIŁ WŁASNE USTALENIE: fiolet ma
# nieść IKONA, a tło ma zostać spoczynkowe („tło się nie zmienia, a ikona robi się
# fioletowa"). Asercji NIE kasujemy — pilnują teraz zasady ODWROTNEJ, bo bramka
# zostawiona przy starej świeciłaby na czerwono nad stanem POPRAWNYM, a skasowana
# zdjęłaby ochronę bez śladu.
# ⭐ Sedno tej rundy: stara asercja [14c] mierzyła kontrast ikony z ARKUSZA STYLÓW
# i była zielona przez cały czas trwania usterki, bo ikona jest OBRAZKIEM i arkusz
# jej nie dotyczy. Dlatego nowe asercje pytają o PIKSELE ikony (`barwa_ikony`).

def jasnosc_hex(h):
    h = h.lstrip("#")
    return sum(int(h[i:i + 2], 16) for i in (0, 2, 4)) / 3


_atrapa2 = Atrapa(tab)
_atrapa2._set_button_active = lambda t, a, on: MainWindow._set_button_active(_atrapa2, t, a, on)
_atrapa2._BUTTON_COLOR_KEYS = MainWindow._BUTTON_COLOR_KEYS
_atrapa2._BUTTONS_WITH_ACTIVE_STATE = MainWindow._BUTTONS_WITH_ACTIVE_STATE
_atrapa2._BUTTON_ICON_KEYS = MainWindow._BUTTON_ICON_KEYS
_atrapa2._repaint_button_icon = lambda t, a, c=None: MainWindow._repaint_button_icon(_atrapa2, t, a, c)

_ikona_qa_spoczynek = barwa_ikony(tab.quick_actions_btn)
_tlo_qa_spoczynek = jasnosc_tla(tab.quick_actions_btn)

MainWindow._set_button_active(_atrapa2, tab, "quick_actions_btn", True)
_akt = reguly(tab.quick_actions_btn)
_ikona_qa_akt = barwa_ikony(tab.quick_actions_btn)

spr(14, "przycisk W UŻYCIU niesie sygnał IKONĄ: obrazek jest w kolorze akcentu",
    podobna_barwa(_ikona_qa_akt, theme.ACCENT),
    f"ikona={_ikona_qa_akt} oczekiwano={theme.ACCENT}")

_tlo_akt = _akt.get("", {}).get("background-color", "")
spr("14b", "tło W UŻYCIU NIE ZMIENIA SIĘ (zasada odwrócona przez właściciela 15.09)",
    _tlo_akt.lower() == _qa.get("", {}).get("background-color", "").lower()
    and abs(jasnosc_tla(tab.quick_actions_btn) - _tlo_qa_spoczynek) <= 6,
    f"arkusz: {_tlo_akt} vs {_qa.get('', {}).get('background-color')}; "
    f"piksele: {jasnosc_tla(tab.quick_actions_btn)} vs {_tlo_qa_spoczynek}")

# Sedno pomiaru: sygnał na CIEMNYM tle potrzebuje własnego progu. Zmierzone 14.09
# na dwóch sygnałach naraz: przy jasności tła poniżej ~30/255 próg 20 jest PODŁOGĄ,
# poniżej której sygnał na pewno ginie — a nie poziomem, przy którym widać.
spr("14c", "ikona w akcencie ma kontrast ≥40/255 wobec ciemnego tła paska",
    abs(jasnosc_hex(_ikona_qa_akt) - _tlo_qa_spoczynek) >= 40,
    f"ikona {_ikona_qa_akt}={jasnosc_hex(_ikona_qa_akt):.0f}, tło={_tlo_qa_spoczynek}, "
    f"różnica {abs(jasnosc_hex(_ikona_qa_akt) - _tlo_qa_spoczynek):.0f}")

spr("14e", "KONTROLA PRZYTOMNOŚCI: miernik barwy ikony ODRÓŻNIA stany",
    _ikona_qa_spoczynek != "" and not podobna_barwa(_ikona_qa_spoczynek, theme.ACCENT),
    f"spoczynek={_ikona_qa_spoczynek} akcent={theme.ACCENT}")

MainWindow._set_button_active(_atrapa2, tab, "quick_actions_btn", False)
spr("14d", "KONTROLA ODWROTNA: po zakończeniu wraca wygląd sąsiada I barwa ikony",
    _poza_ikona(reguly(tab.quick_actions_btn).get("", {})) == _poza_ikona(_sas.get("", {}))
    and barwa_ikony(tab.quick_actions_btn) == _ikona_qa_spoczynek,
    f"styl={reguly(tab.quick_actions_btn).get('', {})} ikona={barwa_ikony(tab.quick_actions_btn)}")

# Tryb myszy trzyma DWIE ikony (przewijanie/zaznaczanie) i jest jedynym przyciskiem
# obsługiwanym osobną gałęzią — bez tej asercji przemalowanie mogłoby trafić
# w obrazek, którego akurat nie widać.
_tryb_myszy_przed = getattr(tab, '_mouse_mode', None)
tab._mouse_mode = 'select'
MainWindow._set_button_active(_atrapa2, tab, "mouse_mode_btn", True)
spr("14f", "tryb myszy: przemalowana zostaje ikona AKTUALNEGO trybu",
    podobna_barwa(barwa_ikony(tab.mouse_mode_btn), theme.ACCENT),
    f"ikona={barwa_ikony(tab.mouse_mode_btn)}")
MainWindow._set_button_active(_atrapa2, tab, "mouse_mode_btn", False)
spr("14g", "...i wraca do barwy ze skórki po wyłączeniu trybu",
    not podobna_barwa(barwa_ikony(tab.mouse_mode_btn), theme.ACCENT),
    f"ikona={barwa_ikony(tab.mouse_mode_btn)}")

# ⛔ PRZYWRÓĆ stan, w którym zastałeś zakładkę. Bez tego asercja [16] (dwa
# przełączenia myszy) startuje z odwrotnego trybu i zgłasza kolejność
# (False, True) — czyli MOJA sonda psuje CUDZĄ asercję, a wygląda to jak
# regresja produktu. Zmierzone przy pisaniu tej rundy.
if _tryb_myszy_przed is not None:
    tab._mouse_mode = _tryb_myszy_przed
    tab._update_mouse_mode_btn()

# --- 15. Menu szybkich akcji: DWÓCH autorów, JEDNO wejście --------------------
# Gdyby MainWindow wołało `setMenu` wprost, jego droga (przebudowa po zmianie listy
# akcji) straciłaby sygnały i podświetlenie działałoby „czasem".
_zrodlo_okna = open(os.path.join(ROOT, "src", "gui", "main_window.py"), encoding="utf-8").read()
spr(15, "okno główne wpina menu przez WSPÓLNY helper, nie własnym setMenu",
    "_attach_quick_menu(menu)" in _zrodlo_okna
    and "quick_actions_btn.setMenu(" not in _zrodlo_okna,
    "setMenu w main_window: %s" % ("JEST (źle)" if "quick_actions_btn.setMenu(" in _zrodlo_okna else "brak"))

_zdarzenia = []
tab.button_active_changed.connect(lambda a, on: _zdarzenia.append((a, on)))
tab._attach_quick_menu(tab.quick_actions_btn.menu())
tab.quick_actions_btn.menu().aboutToShow.emit()
tab.quick_actions_btn.menu().aboutToHide.emit()
# ⚠️ Zdarzenia bywają tu ZDUBLOWANE i to NIE jest usterka: bramka wpina sygnały do
# menu, które zostało już wpięte przy budowie zakładki, więc lambda wisi dwa razy.
# W produkcji każda przebudowa tworzy NOWE QMenu, więc dublowania nie ma. Asercja
# pyta o OBECNOŚĆ obu zdarzeń, nie o ich liczbę — celowo.
spr("15b", "otwarcie i zamknięcie menu ZGŁASZA zmianę stanu przycisku",
    ("quick_actions_btn", True) in _zdarzenia and ("quick_actions_btn", False) in _zdarzenia,
    f"{_zdarzenia}")

# --- 16. Mysz: fiolet trzyma się WŁĄCZONEGO trybu zaznaczania ------------------
_zdarzenia.clear()
tab._toggle_mouse_mode()          # claude -> select
tab._toggle_mouse_mode()          # select -> claude
spr(16, "przełącznik myszy zapala się przy trybie zaznaczania i gaśnie po powrocie",
    _zdarzenia == [("mouse_mode_btn", True), ("mouse_mode_btn", False)],
    f"{_zdarzenia}")

# --- 17. Dodaj media: gaśnie TAKŻE po anulowaniu okna --------------------------
# ⚠️ Tu jest realne ryzyko „przycisk zostaje fioletowy na zawsze": użytkownik
# zamyka okno krzyżykiem albo Anuluj. Podstawiamy okno zwracające PUSTĄ listę.
import gui.agent_tab as AT
_zdarzenia.clear()
_stare_okno = AT.styled_get_open_file_names
AT.styled_get_open_file_names = lambda *a, **k: ([], "")
try:
    tab._add_media()
finally:
    AT.styled_get_open_file_names = _stare_okno
spr(17, "dodawanie mediów gaśnie RÓWNIEŻ po anulowaniu (nie zostaje fioletowe)",
    _zdarzenia == [("add_media_btn", True), ("add_media_btn", False)],
    f"{_zdarzenia}")

# ---- 18. WYCZYŚĆ POLE: czerwone mrugnięcie „wyczyszczone" --------------------
# Życzenie właściciela 2026-09-12. Czerwień NIE znaczy tu „błąd", tylko
# „wyczyszczone" — puste pole wygląda tak samo jak pole, w którym nic nie było,
# więc mrugnięcie jest jedynym potwierdzeniem, jakie user dostaje.
_mrugniecia = []
tab.request_button_flash.connect(lambda a: _mrugniecia.append(a))
tab.input_field.setText("cokolwiek do skasowania")
tab._clear_input_field()
spr(18, "wyczyszczenie pola ZGŁASZA mrugnięcie przycisku",
    _mrugniecia == ["clear_input_btn"], f"{_mrugniecia}")

# ⚠️ SZEW, o którym trzeba wiedzieć: powyżej sprawdzamy NADAWCĘ (zakładka zgłasza),
# a niżej ODBIORCĘ (okno miga na czerwono). Sklejenie obu robi `_connect_agent_tab_signals`
# i tego bramka NIE wykonuje (wymagałoby pełnego MainWindow), więc pytamy o nie źródłem —
# inaczej obie połowy mogłyby być sprawne przy przerwanym kablu między nimi.
spr("18b", "okno główne MA wpięty ten sygnał (inaczej nadawca woła w próżnię)",
    "request_button_flash.connect" in _zrodlo_okna,
    "wpięcie w main_window: %s" % (
        "jest" if "request_button_flash.connect" in _zrodlo_okna else "BRAK"))

MainWindow._flash_button(_atrapa, tab, "clear_input_btn",
                         MainWindow._FLASH_COLORS["clear_input_btn"])
_mrug = reguly(tab.clear_input_btn)
spr("18c", 'mrugnięcie jest CZERWONE (nie zielone jak SKOPIOWANE)',
    theme.DANGER.lower() in _mrug.get("", {}).get("border", "").lower()
    and theme.SUCCESS.lower() not in _mrug.get("", {}).get("border", "").lower(),
    f"{_mrug.get('', {}).get('border')}")

spr("18d", "poza ramką wygląda jak zwykły przycisk",
    _bez_ramki(_mrug.get("", {})) == _bez_ramki(_sas.get("", {})),
    f"{_bez_ramki(_mrug.get('', {}))}")

przeczekaj(0.6)
spr("18e", "po pół sekundy wraca SAM — nie zostaje czerwony",
    theme.DANGER.lower() not in reguly(tab.clear_input_btn).get("", {}).get("border", "").lower(),
    f"po powrocie={reguly(tab.clear_input_btn).get('', {}).get('border')}")

zle = wyniki.count(False)
print(f"\n{'=' * 58}\nWYNIK: {wyniki.count(True)}/{len(wyniki)} OK, {zle} FAIL")
sys.exit(1 if zle else 0)
