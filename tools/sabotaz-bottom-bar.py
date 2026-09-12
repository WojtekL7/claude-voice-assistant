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
Zdrowy kod: 37 sprawdzen, 37 OK, 0 FAIL. Kazdy wariant: 37 WYKONANYCH (czyli
bramka ani razu nie urwala sie w polowie) i przywrocenie dowiedzione sha256.
  wariant | co popsute                                        | co padlo
  --------+---------------------------------------------------+--------------------
  B1      | przywrocony recznie pisany arkusz szybkich akcji   | 7, 8, 9, 9b
  B2      | selektor wpisany na sztywno jako QPushButton       | 7, 10, 12
  B3      | zdjete ukrycie strzalki menu                       | 10
  B4      | zdjete wywolanie malarza dla szybkich akcji        | 7, 8, 9, 9b, 10, 12
  B5      | powrot wlasnego arkusza zielonego blysku           | 13b, 13d
  B6      | blysk gubi SYGNAL (ramka nie jest zielona)         | 13, 13c
  B7      | zdjety caly stan „w uzyciu"                        | 14, 14b
  B8      | ikona zostaje szara na fiolecie (znika)            | 14c
  B9      | mysz nie zglasza trybu zaznaczania                 | 16
  B10     | dodaj media nie gasnie po anulowaniu               | 17
  B11     | okno glowne znowu wpina menu wlasnym setMenu       | 15
  B12     | wyczyszczenie pola nie zglasza mrugniecia          | 18
  B13     | mrugniecie na ZIELONO zamiast czerwono            | 18c
  B14     | blysk NIE WRACA sam (zostaje kolorowy na zawsze)  | 13d, 18e
  B15     | zerwany kabel sygnalu mrugniecia (okno nie wpina) | 18b
⭐ B5 i B6 sa PARA i to jest celowe: B5 pilnuje, zeby stan chwilowy nie mial
   wlasnego wygladu, a B6 - zeby przy tym ujednoliceniu nie zgubic SYGNALU.
   Sam B5 przeszedlby tez nad blyskiem, ktory w ogole przestal byc zielony.
⭐ B7 i B8 to ta sama para o poziom nizej: B7 pilnuje, ze stan „w uzyciu" W OGOLE
   istnieje, B8 - ze jest CZYTELNY. B7 nie zapala [14c] i tak ma byc: przy zdjetym
   stanie ikona zostaje na ciemnym tle, wiec kontrast jest w porzadku - problemem
   jest wtedy brak fioletu, nie kontrast.
⛔ B10 pilnuje ryzyka, ktore najbardziej zabolaloby uzytkownika: okno wyboru pliku
   da sie zamknac „Anuluj" albo krzyzykiem, a bez `finally` przycisk zostalby
   fioletowy NA ZAWSZE i wygladalby na zepsuty. Dlatego bramka anuluje okno
   (podstawia puste okno), zamiast wybierac plik - sciezka „udalo sie" tego nie lapie.

⭐ B14 pilnuje rzeczy, ktorej bramka do 2026-09-12 NIE SPRAWDZALA: powrot po blysku
   wolala RECZNIE, wiec dowodzila, ze „da sie wrocic", a nie ze program wraca SAM.
   Teraz bramka kreci prawdziwa petle zdarzen i czeka na zegar - dlatego B14
   (zdjety `QTimer.singleShot`) zapala az dwie asercje, zielona i czerwona.

⛔ KOTWICE B5 i B6 BYLY WIDMAMI przez jedna sesje - ich kod przeniesiono do
   `_flash_button` i stary wzorzec przestal pasowac. Zglosil to tryb `--kotwice`,
   nie czlowiek. Przy KAZDYM wyniesieniu kodu do wspolnej funkcji przelec kotwice.

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
ZAKLADKA = REPO / "src" / "gui" / "agent_tab.py"
BRAMKA = REPO / "tools" / "test-bottom-bar-icons.py"
OCZEKIWANE = 37          # ile sprawdzen ma WYKONAC bramka na zdrowym kodzie

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
    # ⚠️ B5 i B6 PRZECELOWANE 2026-09-12: po wyniesieniu migania do `_flash_button`
    # ich stare kotwice przestaly pasowac i tryb `--kotwice` zglosil je jako WIDMA.
    # Dokladnie po to ten tryb jest - wariant-widmo niczego nie psuje, wiec "nie
    # wykryto" czytaloby sie jak dowod odpornosci kodu.
    "B5": (OKNO, "powrot wlasnego arkusza zielonego blysku (przezroczyste tlo, rog 12px)",
           "        self._flash_button(\n"
           "            tab, 'copy_btn', theme.SUCCESS,\n"
           "            po_powrocie=lambda: tab.copy_btn.setIcon(self._icon('copy', 'normal')))",
           '        tab.copy_btn.setStyleSheet(f"""\n'
           '            QPushButton {{\n'
           '                background-color: transparent;\n'
           '                border: 2px solid {theme.SUCCESS};\n'
           '                border-radius: 12px;\n'
           '            }}\n'
           '        """)'),
    "B6": (OKNO, "blysk gubi SYGNAL - ramka zwyczajna zamiast zielonej",
           "            tab, 'copy_btn', theme.SUCCESS,",
           "            tab, 'copy_btn', theme.BORDER,"),
    # --- stan „W UZYCIU" (fiolet trwa tyle, ile trwa uzywanie) ---
    "B7": (OKNO, "zdjety caly stan aktywny - przycisk w uzyciu wyglada jak w spoczynku",
           "        if active:",
           "        if False:"),
    "B8": (OKNO, "ikona zostaje szara na fiolecie (znika - ponizej progu kontrastu)",
           "            icon_color = theme.TEXT",
           "            icon_color = theme.TEXT_DIM"),
    "B9": (ZAKLADKA, "przelacznik myszy nie zglasza wlaczonego trybu zaznaczania",
           "        self.button_active_changed.emit('mouse_mode_btn', sel)",
           "        pass  # SABOTAZ"),
    "B10": (ZAKLADKA, "dodawanie mediow nie gasnie po anulowaniu (zostaje fioletowe NA ZAWSZE)",
            "            self.button_active_changed.emit('add_media_btn', False)",
            "            pass  # SABOTAZ"),
    "B11": (OKNO, "okno glowne znowu wpina menu wlasnym setMenu (traci sygnaly)",
            "                tab._attach_quick_menu(menu)",
            "                tab.quick_actions_btn.setMenu(menu)"),
    # --- blysk „zrobione" (zielony po skopiowaniu, czerwony po wyczyszczeniu) ---
    "B12": (ZAKLADKA, "wyczyszczenie pola nie zglasza mrugniecia (brak potwierdzenia)",
            "        self.request_button_flash.emit('clear_input_btn')",
            "        pass  # SABOTAZ"),
    "B13": (OKNO, "mrugniecie po wyczyszczeniu na ZIELONO zamiast czerwono",
            "        'clear_input_btn': theme.DANGER,",
            "        'clear_input_btn': theme.SUCCESS,"),
    "B14": (OKNO, "blysk NIE WRACA sam - przycisk zostaje kolorowy na zawsze",
            "        QTimer.singleShot(ms, wroc_do_normy)",
            "        pass  # SABOTAZ"),
    "B15": (OKNO, "zerwany kabel: okno nie wpina sygnalu mrugniecia",
            "        agent_tab.request_button_flash.connect(",
            "        _ = (lambda *a: None)("),
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
