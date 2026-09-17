#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bramka: TEMPO CZYTANIA (przycisk 1x / 1,25x / 1,5x / 2x na dolnym pasku).

URUCHOMIENIE:  venv/bin/python tools/test-tts-speed.py

CO PILNUJE (i czego NIE pilnuje — patrz na koncu pliku):
  A. lista poziomow ma JEDNO zrodlo i wlasciwa kolejnosc cyklu
  B. cykl przycisku + fail-safe na smiec w konfiguracji
  C. etykiety dla czlowieka (PL przecinek / EN kropka) + parytet i18n
  D. ⭐ LADUNEK WYCHODZACY: wybrane tempo realnie dojezdza do edge-tts
  E. odczyt LAGODNY: smiec z config.json nie dojedzie do lektora
  F. przycisk jest w malarzu stylow (pulapka „bialego kwadratu", 4. wystapienie)
  G. kontrola odwrotna: na 1x wysylamy „+0%", czyli dokladnie stan sprzed zmiany

WYNIKI SABOTAZU — ZMIERZONE, nie przewidziane: patrz naglowek
`tools/sabotaz-tts-speed.py` (uruchamiany osobno).
"""
import os
import sys
import tempfile
from pathlib import Path

# HOME podmieniamy PRZED importem config — sciezki licza sie w chwili importu,
# a bramka nie moze dotykac prawdziwej konfiguracji uzytkownika (w tym projekcie
# doraznys krypt raz zatrul prawdziwy dictation.log atrapami).
_ATRAPA_HOME = tempfile.mkdtemp(prefix="cva-test-tempo-")
os.environ["HOME"] = _ATRAPA_HOME

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / "src"))

# Qt BEZ EKRANU — sekcja F mierzy realny skutek stylowania przycisku, wiec
# potrzebuje zywych widzetow. Kolejnosc jest tu obowiazkowa i nieoczywista:
#   1. QT_QPA_PLATFORM przed importem PyQt,
#   2. atrybut AA_ShareOpenGLContexts przed QApplication,
#   3. ⛔ QApplication w zmiennej MODULOWEJ — trzymana lokalnie zostaje zebrana
#      przez odsmiecacz, a nastepny QWidget wywala caly proces core dumpem
#      (zmierzone przy pisaniu tej bramki: zero wyjscia, zero PODSUMOWANIA).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_APP = QApplication.instance() or QApplication([])

import config  # noqa: E402

WYKONANE = 0
PADLE = 0


def sprawdz(opis, funkcja):
    """Kazde sprawdzenie w OSLONIE — bramka ma ORZEKAC, nie padac.

    W tym projekcie rodzina „bramka pada zamiast orzec" zaliczyla 10 wystapien;
    wyjscie po odfiltrowaniu wyglada wtedy identycznie jak komplet zielonych.
    Dlatego liczymy WYKONANE i na koncu drukujemy PODSUMOWANIE — brak tej linii
    jest jedynym wiarygodnym sygnalem, ze przebieg sie urwal.
    """
    global WYKONANE, PADLE
    WYKONANE += 1
    try:
        ok, szczegol = funkcja()
    except Exception as e:
        ok, szczegol = False, f"WYJATEK {type(e).__name__}: {e}"
    if ok:
        print(f"[OK] {opis}" + (f" — {szczegol}" if szczegol else ""))
    else:
        PADLE += 1
        print(f"[FAIL] {opis} — {szczegol}")


# ---------------------------------------------------------------- A. lista
def a1():
    p = config.TTS_RATE_LEVELS
    return (isinstance(p, list) and len(p) == 4,
            f"poziomow={len(p)}")


def a2():
    return ([r for r, _ in config.TTS_RATE_LEVELS] == ["+0%", "+25%", "+50%", "+100%"],
            f"{[r for r, _ in config.TTS_RATE_LEVELS]}")


def a3():
    return ([m for _, m in config.TTS_RATE_LEVELS] == [1.0, 1.25, 1.5, 2.0],
            f"{[m for _, m in config.TTS_RATE_LEVELS]}")


def a4():
    """Pierwszy poziom MUSI byc 1x — inaczej sama aktualizacja programu
    zmienilaby tempo czytania komus, kto nigdy o to nie prosil."""
    return (config.TTS_RATE_LEVELS[0][0] == config.TTS_DEFAULT_RATE,
            f"pierwszy={config.TTS_RATE_LEVELS[0][0]} domyslny={config.TTS_DEFAULT_RATE}")


def a5():
    """Swiadoma decyzja wlasciciela 2026-09-17: BEZ spowolnienia.
    Kontrola przeciwna — gdyby ktos dolozyl „-50%", ma sie zapalic."""
    ujemne = [r for r, _ in config.TTS_RATE_LEVELS if r.startswith("-")]
    return (not ujemne, f"spowolnien na liscie: {len(ujemne)}")


def a6():
    """JEDNO ZRODLO: poziomy nie moga byc wpisane drugi raz w GUI.
    Szukamy literalow „+25%"/„+100%" poza config.py."""
    trafienia = []
    for plik in (KORZEN / "src" / "gui" / "agent_tab.py",
                 KORZEN / "src" / "gui" / "main_window.py"):
        tresc = plik.read_text(encoding="utf-8")
        for lit in ('"+25%"', "'+25%'", '"+100%"', "'+100%'"):
            if lit in tresc:
                trafienia.append(f"{plik.name}:{lit}")
    return (not trafienia, f"kopii poziomow poza config.py: {len(trafienia)}")


# ---------------------------------------------------------------- B. cykl
def b1():
    kolejne = []
    biezace = config.TTS_DEFAULT_RATE
    for _ in range(4):
        biezace = config.tts_rate_next(biezace)
        kolejne.append(biezace)
    return (kolejne == ["+25%", "+50%", "+100%", "+0%"], f"{kolejne}")


def b2():
    """Fail-safe: wartosc spoza listy (recznie wpisana w config.json,
    pozostalosc po innej wersji) NIE MOZE zablokowac przycisku."""
    return (config.tts_rate_next("nie-ma-takiego") == config.TTS_DEFAULT_RATE,
            f"oddalo {config.tts_rate_next('nie-ma-takiego')}")


def b3():
    return (config.tts_rate_multiplier("+50%") == 1.5
            and config.tts_rate_multiplier("smiec") == 1.0,
            "mnozniki + fail-safe")


# ------------------------------------------------------------ C. etykiety
def c1():
    config.set_ui_language("pl-PL")
    etyk = [config.tts_rate_label(m) for _, m in config.TTS_RATE_LEVELS]
    return (etyk == ["1×", "1,25×", "1,5×", "2×"], f"{etyk}")


def c2():
    config.set_ui_language("en-US")
    etyk = [config.tts_rate_label(m) for _, m in config.TTS_RATE_LEVELS]
    return (etyk == ["1×", "1.25×", "1.5×", "2×"], f"{etyk}")


def c3():
    """Parytet slownikow — klucz dodany w jednym jezyku musi byc w obu."""
    pl = set(config.UI_TRANSLATIONS["pl-PL"])
    en = set(config.UI_TRANSLATIONS["en-US"])
    brak = (pl ^ en)
    ok = "tts_speed_tooltip" in pl and "tts_speed_tooltip" in en and not brak
    return (ok, f"klucz w obu slownikach, roznic: {len(brak)}")


def c4():
    """Podpowiedz MUSI miec miejsce na wartosc — bez {tempo} uzytkownik
    nie dowie sie z niej, jakie ma teraz tempo."""
    config.set_ui_language("pl-PL")
    pl = config.t("tts_speed_tooltip")
    config.set_ui_language("en-US")
    en = config.t("tts_speed_tooltip")
    return ("{tempo}" in pl and "{tempo}" in en, f"PL={'{tempo}' in pl} EN={'{tempo}' in en}")


# --------------------------------------- D. LADUNEK WYCHODZACY (najwazniejsze)
def _zloc_ladunek(rate_ustawione):
    """Odpal produkcyjna sciezke generowania i zlap, CO poszlo do edge-tts.

    Atrapujemy WYLACZNIE brzeg sieci (`edge_tts.Communicate`) — reszta to
    prawdziwy kod TTSEngine. Atrapa wyglada jak SUKCES we wszystkim poza tym,
    co badamy: `save` tworzy plik, wiec silnik nie zejdzie na zadna sciezke
    awaryjna i nie zmierzymy przypadkiem sasiedniego bezpiecznika.
    """
    import asyncio
    import core.tts_engine as te

    zlapane = {}

    class AtrapaCommunicate:
        def __init__(self, text, voice, rate="+0%", volume="+0%", **kw):
            zlapane["text"] = text
            zlapane["voice"] = voice
            zlapane["rate"] = rate
            zlapane["volume"] = volume

        async def save(self, sciezka):
            Path(sciezka).write_bytes(b"\x00" * 64)

    oryginal = te.edge_tts.Communicate
    te.edge_tts.Communicate = AtrapaCommunicate
    try:
        silnik = te.TTSEngine()
        silnik.set_rate(rate_ustawione)
        plik = Path(_ATRAPA_HOME) / "proba.mp3"
        asyncio.run(silnik._async_generate("Zdanie probne.", str(plik)))
    finally:
        te.edge_tts.Communicate = oryginal
    return zlapane


def d1():
    """Czy wybrane tempo W OGOLE opuszcza program."""
    lad = _zloc_ladunek("+50%")
    return (lad.get("rate") == "+50%", f"wyslane rate={lad.get('rate')!r}")


def d2():
    """DRUGA asercja, celowo INNEGO rodzaju — i NIE jest duplikatem d1.

    d1 porownuje wyslana wartosc z ta, ktora sam przed chwila ustawilem: przy
    cofnieciu calej funkcji OBIE strony porownania przesuwaja sie razem i d1
    dalej przechodzi (ta sama pulapka co para F6/F7 przy przepieciu dyktowania
    na zadania — opisana w pamieci projektu). Tu pytamy o KSZTALT niezalezny
    od mojego ustawienia: wyslane tempo ma byc jedna z wartosci Z LISTY.
    """
    lad = _zloc_ladunek("+100%")
    dozwolone = [r for r, _ in config.TTS_RATE_LEVELS]
    return (lad.get("rate") in dozwolone,
            f"wyslane {lad.get('rate')!r} wobec listy {dozwolone}")


def d3():
    """Zmiana tempa NIE MOZE po drodze zepsuc glosu ani glosnosci —
    kontrola, ze ruszamy dokladnie jedno pokretlo."""
    lad = _zloc_ladunek("+25%")
    return (lad.get("volume") == "+0%" and bool(lad.get("voice")),
            f"volume={lad.get('volume')!r} voice={lad.get('voice')!r}")


# ----------------------------------------------------- E. odczyt lagodny
def e1():
    """Wartosc spoza listy w config.json nie moze dojechac do lektora.

    Czytamy WARUNEK Z KODU PRODUKCJI (nie przepisujemy go), zeby bramka nie
    pilnowala wlasnej kopii reguly.
    """
    zrodlo = (KORZEN / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    ma_walidacje = "_zapisane_tempo in [r for r, _ in TTS_RATE_LEVELS]" in zrodlo
    return (ma_walidacje, f"walidacja listy w _load_settings: {ma_walidacje}")


def e2():
    zrodlo = (KORZEN / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    jest = "'tts_rate': getattr(self, 'tts_rate', TTS_DEFAULT_RATE)" in zrodlo
    return (jest, f"zapis tts_rate w _save_settings: {jest}")


# --------------------------------------------------- F. pulapka bialego kwadratu
def f1():
    """CZWARTE wystapienie rodziny: przycisk paska pominiety w malarzu stylow
    zostaje fabrycznym BIALYM kwadratem (zlapalo juz mouse_mode_btn,
    repair_terminal_btn i search_btn).

    ⛔ MIERZYMY SKUTEK, NIE OBECNOSC NAPISU W PLIKU. Pierwsza wersja tej asercji
    pytala `"_apply_button_icon_style(tab.speed_btn" in zrodlo` i byla SLEPA:
    sabotaz S2 zamienia warunek na `if False:`, ZOSTAWIAJAC linie wywolania
    w pliku — asercja przechodzila nad przyciskiem, ktorego nikt nie stylowal
    (zmierzone: 0 padlych przy 24 wykonanych). To ta sama rodzina co „asercja
    bada ISTNIENIE nazwy zamiast liczby WYWOLAN".

    Dlatego wolamy PRAWDZIWA `MainWindow._apply_button_icon_styles` (LICZBA
    MNOGA — badanym bledem jest BRAK WYWOLANIA, nie zepsuty malarz) na lekkiej
    atrapie zakladki i pytamy, czy przycisk realnie dostal arkusz.
    """
    from gui.main_window import MainWindow, DEFAULT_SKIN_COLORS

    class AtrapaZakladki:
        def __init__(self):
            self.speed_btn = QPushButton("1\u00d7")

    class AtrapaOkna:
        skin_colors = DEFAULT_SKIN_COLORS
        _apply_button_icon_style = MainWindow._apply_button_icon_style
        _apply_send_button_style = MainWindow._apply_send_button_style

        def __init__(self, zakladka):
            self.agent_tabs = {"test": zakladka}

    zakladka = AtrapaZakladki()
    przed = zakladka.speed_btn.styleSheet()
    MainWindow._apply_button_icon_styles(AtrapaOkna(zakladka))
    po = zakladka.speed_btn.styleSheet()
    # Kontrola przytomnosci wbudowana: PRZED stylowaniem arkusz MUSI byc pusty,
    # inaczej mierzylibysmy cos, co bylo tam od poczatku.
    return (not przed and len(po) > 0,
            f"arkusz przed={len(przed)} zn., po={len(po)} zn.")


def f2():
    """Napis, nie ikona — czcionka 22 px (rozmiar glifu) ucielaby „1,25×"."""
    zrodlo = (KORZEN / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    jest = "self._apply_button_icon_style(tab.speed_btn, 'icon_read_color', font_size=14)" in zrodlo
    return (jest, f"font_size=14 dla napisu: {jest}")


def f3():
    """Szerokosc MIERZONA, nie wpisana — etykiety maja rozna dlugosc."""
    zrodlo = (KORZEN / "src" / "gui" / "agent_tab.py").read_text(encoding="utf-8")
    jest = "horizontalAdvance" in zrodlo and "setFixedWidth" in zrodlo
    return (jest, f"pomiar szerokosci z fontMetrics: {jest}")


def f4():
    """Sygnal musi byc podlaczony w JEDNYM miejscu wspolnym dla OBU sciezek
    tworzenia zakladek (historia „zgubionego kabelka" przy przycisku +)."""
    zrodlo = (KORZEN / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    ile = zrodlo.count("agent_tab.request_tts_speed.connect")
    return (ile == 1, f"polaczen sygnalu: {ile} (ma byc 1, w _connect_agent_tab_signals)")


# ----------------------------------------------- G. kontrola odwrotna (regresja)
def g1():
    """Na 1x wysylamy dokladnie to, co program wysylal PRZED ta zmiana.

    Bez tej asercji „dziala szybciej" nie odroznia sie od „zepsulismy
    dotychczasowe czytanie".
    """
    lad = _zloc_ladunek(config.TTS_DEFAULT_RATE)
    return (lad.get("rate") == "+0%", f"wyslane {lad.get('rate')!r} (przed zmiana bylo '+0%')")


def g2():
    """Kontrola PRZYTOMNOSCI: czy bramka w ogole czyta zywy kod.

    Bez niej „zero trafien" i „nie umiem szukac" wygladaja identycznie.
    """
    znaki = sum(len((KORZEN / "src" / "gui" / p).read_text(encoding="utf-8"))
                for p in ("agent_tab.py", "main_window.py"))
    return (znaki > 200_000, f"przeczytano {znaki} znakow kodu GUI")


TESTY = [
    ("A1 lista ma 4 poziomy", a1),
    ("A2 wartosci wysylane do edge-tts", a2),
    ("A3 mnozniki 1 / 1,25 / 1,5 / 2", a3),
    ("A4 cykl zaczyna sie od tempa domyslnego", a4),
    ("A5 BEZ spowolnien (decyzja wlasciciela)", a5),
    ("A6 poziomy tylko w config.py (jedno zrodlo)", a6),
    ("B1 cykl 1x -> 1,25x -> 1,5x -> 2x -> 1x", b1),
    ("B2 fail-safe na smiec w konfiguracji", b2),
    ("B3 mnoznik z wartosci + fail-safe", b3),
    ("C1 etykiety PL (przecinek)", c1),
    ("C2 etykiety EN (kropka)", c2),
    ("C3 parytet slownikow PL/EN", c3),
    ("C4 podpowiedz niesie {tempo}", c4),
    ("D1 tempo DOJEZDZA do edge-tts", d1),
    ("D2 wyslane tempo jest Z LISTY (nie stala sama ze soba)", d2),
    ("D3 ruszamy tylko tempo (glos i glosnosc nietkniete)", d3),
    ("E1 odczyt lagodny: smiec nie dojedzie do lektora", e1),
    ("E2 wybor zapisywany do config.json", e2),
    ("F1 przycisk stylowany (nie bialy kwadrat)", f1),
    ("F2 czcionka dobrana pod NAPIS", f2),
    ("F3 szerokosc mierzona, nie wpisana", f3),
    ("F4 sygnal podlaczony w jednym miejscu", f4),
    ("G1 kontrola odwrotna: 1x = zachowanie sprzed zmiany", g1),
    ("G2 kontrola przytomnosci bramki", g2),
]

if __name__ == "__main__":
    print("=" * 72)
    print("BRAMKA: tempo czytania (1x / 1,25x / 1,5x / 2x)")
    print("=" * 72)
    for opis, fn in TESTY:
        sprawdz(opis, fn)
    print("-" * 72)
    # ⭐ Ta linia jest DOWODEM, ze bramka dobiegla do konca. Jej BRAK (a nie
    # nierownosc licznika) oznacza przerwanie w polowie.
    print(f"PODSUMOWANIE: {WYKONANE - PADLE}/{WYKONANE} OK, porazek: {PADLE}")
    sys.exit(1 if PADLE else 0)

# ---------------------------------------------------------------------------
# CZEGO TA BRAMKA NIE PILNUJE (zapisane jawnie, zeby nikt na to nie liczyl):
#  · nie sprawdza WYGLADU przycisku na ekranie (piksele) — to robi
#    tools/test-bottom-bar-icons.py; tutaj mierzymy tylko DECYZJE kodu;
#  · nie dowodzi, ze uzytkownik USLYSZY roznice — to potwierdza czlowiek;
#  · nie pilnuje, ze tempo lapie „od nastepnego zdania" (to skutek prefetchu
#    w silniku, nie nasza decyzja) — opisane w komentarzu `_apply_tts_rate`.
