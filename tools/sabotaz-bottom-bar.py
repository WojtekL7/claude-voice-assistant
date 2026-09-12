#!/usr/bin/env python3
"""Sabotazysta bramki DOLNEGO PASKA (`tools/test-bottom-bar-icons.py`).

PO CO: zielona bramka NIE ODROZNIA „styl dziala" od „nikt tego nie sprawdza".
Dopiero swiadome zepsucie produkcji pokazuje, czy asercje cokolwiek lapia.

Uklad przepisany z `sabotaz-dictation-fix.py` (sprawdzony):
  * JEDEN wariant = JEDNO wywolanie (limit czasu na petli zostawial sabotaz w kodzie),
  * przywracanie w `finally` + dowod sha256 przed/po,
  * kontrola, czy wariant COKOLWIEK zmienil (wzorzec-widmo nie testuje niczego),
  * `python3 -B` + kasowanie __pycache__,
  * interpreter i srodowisko Qt podawane JAWNIE (Claude Code eksportuje wlasne Qt,
    wiec bez `env -u …` bramka pada na „Cannot mix incompatible Qt library").

Uzycie:  python3 tools/sabotaz-bottom-bar.py B1
         python3 tools/sabotaz-bottom-bar.py --kotwice

SABOTAZ - WYNIKI ZMIERZONE (uruchomione 2026-09-12, NIE przewidziane).
Zdrowy kod: 23 sprawdzen, 23 OK, 0 FAIL. Kazdy wariant: 23 WYKONANYCH (czyli
bramka ani razu nie urwala sie w polowie) i przywrocenie dowiedzione sha256.
  wariant | co popsute                                        | co padlo
  --------+---------------------------------------------------+--------------------
  B1      | przywrocony recznie pisany arkusz szybkich akcji   | 7, 8, 9, 9b
  B2      | selektor wpisany na sztywno jako QPushButton       | 7, 10, 12
  B3      | zdjete ukrycie strzalki menu                       | 10
  B4      | zdjete wywolanie malarza dla szybkich akcji        | 7, 8, 9, 9b, 10, 12
  B5      | powrot wlasnego arkusza zielonego blysku           | 13b
  B6      | blysk gubi SYGNAL (ramka nie jest zielona)         | 13
⭐ B5 i B6 sa PARA i to jest celowe: B5 pilnuje, zeby stan chwilowy nie mial
   wlasnego wygladu, a B6 - zeby przy tym ujednoliceniu nie zgubic SYGNALU.
   Sam B5 przeszedlby tez nad blyskiem, ktory w ogole przestal byc zielony.

⛔ CZEGO NAUCZYL SABOTAZ O SAMEJ BRAMCE (wart zapamietania):
   wariant B2 w PIERWSZYM przebiegu zapalil TYLKO [7] i [10] - asercje [8], [9]
   i [9b] przeszly nad kodem, ktorego Qt w ogole nie stosuje. Powod: te asercje
   porownuja ZAPISANY arkusz i celowo zdejmuja z selektora nazwe klasy (inaczej
   nie da sie zestawic QToolButtona z QPushButtonem) - byly wiec slepe dokladnie
   na najgrozniejszy blad z tej rodziny: arkusz napisany dla CUDZEJ klasy.
   Stad dopisana asercja [12], ktora pyta o to wprost. Bez sabotazu bramka
   wygladalaby na komplet i nie chronilaby przed powrotem oryginalnej usterki.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OKNO = REPO / "src" / "gui" / "main_window.py"
BRAMKA = REPO / "tools" / "test-bottom-bar-icons.py"
OCZEKIWANE = 23          # ile sprawdzen ma WYKONAC bramka na zdrowym kodzie

_VENV = REPO / "venv" / "bin" / "python"
PYTHON = str(_VENV) if _VENV.exists() else sys.executable

# Recznie pisany arkusz sprzed poprawki 2026-09-12 - dokladnie to, co bylo w kodzie.
STARY_ARKUSZ = '''            if hasattr(tab, 'quick_actions_btn'):
                icon_color = self.skin_colors.get('icon_quick_actions_color', f'{theme.WARNING}')
                border_color = self.skin_colors.get('border_color', f'{theme.BORDER}')
                hover_color = self.skin_colors.get('hover_color', f'{theme.HOVER}')

                tab.quick_actions_btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: transparent;
                        color: {icon_color};
                        border: 1px solid {border_color};
                        border-radius: 12px;
                        font-size: 20px;
                    }}
                    QToolButton:hover {{
                        background-color: {hover_color};
                    }}
                    QToolButton::menu-indicator {{
                        image: none;
                    }}
                """)'''

NOWE_WOLANIE = ("            if hasattr(tab, 'quick_actions_btn'):\n"
                "                self._apply_button_icon_style(tab.quick_actions_btn, "
                "'icon_quick_actions_color')")

# (plik, opis, szukane, zamiennik) - kotwice UNIKALNE dla badanego miejsca
WARIANTY = {
    "B1": (OKNO, "powrot recznie pisanego arkusza szybkich akcji (stan sprzed poprawki)",
           NOWE_WOLANIE, STARY_ARKUSZ),
    "B2": (OKNO, "selektor wpisany na sztywno - regula znowu omija QToolButton",
           '        sel = button.metaObject().className()',
           '        sel = "QPushButton"'),
    "B3": (OKNO, "zdjete ukrycie strzalki rozwijania menu",
           '        if sel == "QToolButton":',
           '        if False:'),
    "B4": (OKNO, "zdjete wywolanie malarza dla szybkich akcji (bialy kwadrat)",
           NOWE_WOLANIE,
           "            if False:\n                pass  # SABOTAZ"),
    "B5": (OKNO, "powrot wlasnego arkusza zielonego blysku (przezroczyste tlo, rog 12px)",
           "        self._apply_button_icon_style(tab.copy_btn, 'icon_copy_color',\n"
           "                                      border_override=theme.SUCCESS)",
           '        tab.copy_btn.setStyleSheet(f"""\n'
           '            QPushButton {{\n'
           '                background-color: transparent;\n'
           '                border: 2px solid {theme.SUCCESS};\n'
           '                border-radius: 12px;\n'
           '            }}\n'
           '        """)'),
    "B6": (OKNO, "blysk gubi SYGNAL - ramka zwyczajna zamiast zielonej",
           "                                      border_override=theme.SUCCESS)",
           "                                      border_override=None)"),
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
        wykonane = wyjscie.count("[OK ]") + padly
        nazwy = [l.split(".")[0].replace("[FAIL] ", "").strip()
                 for l in wyjscie.splitlines() if l.startswith("[FAIL]")]
        print("PADLYCH: %d  WYKONANYCH: %d  kod=%d  -> %s"
              % (padly, wykonane, r.returncode, ", ".join(nazwy) if nazwy else "(nic)"))
        if wykonane != OCZEKIWANE:
            print(">>> UWAGA: bramka NIE DOBIEGLA DO KONCA (%d z %d) - "
                  "wynik nie mowi nic o asercjach" % (wykonane, OCZEKIWANE))
            print(wyjscie[-1500:])
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
