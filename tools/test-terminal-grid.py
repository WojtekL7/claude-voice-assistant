#!/usr/bin/env python3
"""Bramka: SIATKA TERMINALA (kratka na znak) w WebTerminalu.

Pilnuje usterki „rozstrzelone litery" z 2026-08-04. Objaw u użytkownika: litery
z dziurami, a prawa połowa każdej linii znika za krawędzią okna.

PRZYCZYNA (zmierzona, nie zgadnięta): xterm.js mierzy szerokość znaku RAZ, przy
najbliższym rysowaniu po zmianie czcionki. `_push_font` wysyłał GOŁĄ nazwę
rodziny ("Ubuntu Mono") bez łańcucha zapasowego, a nasze .ttf doczytują się
asynchronicznie — więc pomiar potrafił trafić na domyślny SZERYFOWY krój
przeglądarki. Wtedy kratka = 17,8 px zamiast 9,5 px (Noto Serif 'W' = 17,80 px)
i cała siatka jest ~1,88× za szeroka.

DOWÓD ZGODNOŚCI: z logu użytkownika (webterminal.log, resize 122↔65) wychodziła
kratka 17,87 px; sabotaż w tym teście odtwarza 17,82 px — zgodność 0,3%.

URUCHOMIENIE (Linux, z katalogu projektu):
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH \
        QT_QPA_PLATFORM=offscreen ./venv/bin/python3 tools/test-terminal-grid.py

⚠️ `env -u …` jest OBOWIĄZKOWE, gdy uruchamiasz to z Claude Code — eksportuje on
własne Qt i podproces PyQt wywala się na „Cannot mix incompatible Qt library".

WYNIKI SABOTAŻU — WSZYSTKIE URUCHOMIONE I ZMIERZONE 2026-08-04 (nie przewidziane;
jedno z moich przewidywań okazało się fałszywe — patrz punkt 3):
  1. usunięcie `remeasure()` z `fitAfterFontChange`  → pada [3]: kratka zostaje
     10,25 px z czcionki zapasowej zamiast 9,53 px. To ta sama usterka, tylko
     cichsza (litery rozstrzelone o 7%) — i to ONA daje objaw „w jednej zakładce
     jest inna czcionka niż w pozostałych".
  2. usunięcie PLANU B (przywrócenia FONT_STACK przy próbie 2) → pada [6]:
     samo przemierzenie NIE naprawia rodziny bez pokrycia (próba 1 zwraca
     w kółko 17,82 px).
  3. poszerzenie przedziału strażnika do 0,45–1,50 → padają [6] i [7],
     NIE [5]. ⚠️ Przewidywałem [5] i było to BŁĘDNE: [5] mierzy stosunek wobec
     progu zapisanego w TEŚCIE, więc widzi usterkę niezależnie od tego, czy
     aplikacja ją widzi. Tę różnicę warto zachować — [5] pilnuje POMIARU,
     a [6]/[7] pilnują REAKCJI aplikacji.
  4. przywrócenie `Menlo` przed realnym monospace w FONT_STACK → 8/8 OK,
     NIE wywala niczego. To nie luka w teście, tylko fakt do zapisania PRZY
     KODZIE: na tej maszynie Chromium nie bierze podstawienia fontconfiga
     (`fc-match Menlo` → PROPORCJONALNE Noto Sans) i schodzi do DejaVu.
     Kolejność w FONT_STACK jest więc DRUGĄ LINIĄ OBRONY, a nie mechanizmem
     mierzonym tym testem — nie „sprzątać" jej jako martwej i nie liczyć,
     że test jej pilnuje.
"""
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

# Każdy monospace ma kratkę 0,50–0,62 rozmiaru czcionki (Ubuntu Mono 0,56;
# DejaVu i JetBrains 0,60). Zamiennik proporcjonalny dawał 1,05.
MIN_OK, MAX_OK = 0.45, 0.75
MARKER = f"=== BRAMKA SIATKI pid={os.getpid()} ==="

wyniki = []


def sprawdz(nr, opis, warunek, szczegol=""):
    wyniki.append(bool(warunek))
    print(f"[{'OK ' if warunek else 'FAIL'}] {nr}. {opis}"
          + (f"  ({szczegol})" if szczegol else ""))


def odczyt_pomiarow():
    """Wyłuskaj z logu wpisy czujnika ZA naszym znacznikiem: [(tag, stosunek)]."""
    tekst = WEBTERMINAL_LOG.read_text(encoding="utf-8", errors="replace")
    tekst = tekst.split(MARKER)[-1]
    out = []
    for m in re.finditer(r"siatka\[([^\]]+)\][^\n]*?kratka=([\d.]+)px"
                         r"[^\n]*?kratka/fontSize=([\d.]+)", tekst):
        out.append((m.group(1), float(m.group(2)), float(m.group(3))))
    return out


_log(MARKER)
term = WebTerminal()
term.resize(1000, 600)
term.set_font("Ubuntu Mono", 13)      # dokładnie to, co robi gui/agent_tab.py
term.show()


def sabotaz():
    """Odtwórz usterkę: rodzina BEZ POKRYCIA → przeglądarka bierze swój
    domyślny (szeryfowy) krój, dokładnie jak przy niedoczytanym .ttf."""
    _log("--- sabotaz: rodzina bez pokrycia ---")
    term.view.page().runJavaScript("term.options.fontFamily = 'KrojWidmoNieIstnieje';")
    QTimer.singleShot(1200, lambda: term.view.page().runJavaScript("safeFit('sabotaz');"))


def przywroc():
    _log("--- przywracam poprawna czcionke ---")
    term.set_font("Ubuntu Mono", 13)


def podsumuj():
    p = odczyt_pomiarow()
    tagi = [t for t, _, _ in p]
    print(f"\nZebrane pomiary ({len(p)}):")
    for t, kr, r in p:
        print(f"    {t:34s} kratka={kr:6.2f}px  kratka/fontSize={r:.3f}")
    print()

    def znajdz(frag):
        for t, kr, r in p:
            if frag in t:
                return kr, r
        return None, None

    sprawdz(1, "czujnik w ogóle pisze do webterminal.log", len(p) >= 4,
            f"{len(p)} wpisów")

    kr, r = znajdz("start")
    sprawdz(2, "start: kratka to MONOSPACE (łańcuch zapasowy trzyma)",
            r is not None and MIN_OK <= r <= MAX_OK, f"stosunek={r}")

    kr, r = znajdz("fonty-gotowe")
    sprawdz(3, "po doczytaniu .ttf kratka = Ubuntu Mono (~9,5 px), NIE zapasowa",
            kr is not None and abs(kr - 9.53) < 0.6, f"kratka={kr}px")

    kr, r = znajdz("sabotaz")
    sprawdz(4, "KONTROLA NEGATYWNA: sabotaż odtwarza usterkę (~17,8 px)",
            kr is not None and kr > 15.0, f"kratka={kr}px")
    sprawdz(5, "strażnik WIDZI usterkę (stosunek poza 0,45–0,75)",
            r is not None and not (MIN_OK <= r <= MAX_OK), f"stosunek={r}")

    kr, r = znajdz("naprawa2")
    sprawdz(6, "strażnik NAPRAWIA (plan B wraca na pełny łańcuch)",
            r is not None and MIN_OK <= r <= MAX_OK, f"stosunek={r}")

    kr1, r1 = znajdz("naprawa1")
    sprawdz(7, "…i naprawa1 SAMA nie wystarcza (dowód, że plan B niesie robotę)",
            r1 is not None and not (MIN_OK <= r1 <= MAX_OK), f"stosunek={r1}")

    ostatni = [x for x in p if x[0].startswith("python-font")]
    sprawdz(8, "po przywróceniu czcionki kratka wraca do 9,5 px",
            bool(ostatni) and abs(ostatni[-1][1] - 9.53) < 0.6,
            f"kratka={ostatni[-1][1] if ostatni else None}px")

    zle = wyniki.count(False)
    print(f"\n{'=' * 58}\nWYNIK: {wyniki.count(True)}/{len(wyniki)} OK, {zle} FAIL")
    term.shutdown()
    _app.exit(1 if zle else 0)


QTimer.singleShot(3000, sabotaz)
QTimer.singleShot(7000, przywroc)
QTimer.singleShot(10000, podsumuj)
sys.exit(_app.exec_())
