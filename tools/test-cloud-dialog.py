#!/usr/bin/env python3
"""Testy okna „Chmura" bez uruchamiania aplikacji (offscreen).

Lapie to, czego `py_compile` NIE lapie: brakujace klucze tlumaczen, literowki
w nazwach kolorow motywu, NameError w metodach budujacych UI oraz ucinanie
tekstu na przyciskach (pulapka projektu: sztywne wysokosci + wyzsze czcionki).

Uruchomienie:  QT_QPA_PLATFORM=offscreen python3 tools/test-cloud-dialog.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PyQt5.QtWidgets import QApplication, QLabel, QPushButton   # noqa: E402
import config                                                   # noqa: E402

PASS = FAIL = 0
KLUCZ_RE = re.compile(r"^(cloud|menu|dlg|btn)_[a-z_]+$")


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         oczekiwano: {want!r}\n         otrzymano : {got!r}")


def main():
    app = QApplication([])
    import gui.cloud_dialog as cd

    # Haslo zapisujemy do katalogu tymczasowego — test nie moze ruszyc
    # prawdziwej konfiguracji usera.
    tmp = Path(tempfile.mkdtemp(prefix="cva-dlg-"))
    cd.CLOUD_PASSPHRASE_FILE = tmp / "cloud-passphrase.txt"

    print("\n1. Parytet tlumaczen (wszystkie napisy okna w obu jezykach)")
    pl, en = config.UI_TRANSLATIONS["pl-PL"], config.UI_TRANSLATIONS["en-US"]
    klucze = sorted(k for k in pl if k.startswith("cloud_") or k == "menu_cloud")
    check(f"kluczy okna Chmura: {len(klucze)} — komplet w EN",
          [k for k in klucze if k not in en], [])
    check("slowniki nadal maja komplet tych samych kluczy", set(pl) ^ set(en), set())
    for k in ("cloud_scope_note", "cloud_sent_ok", "cloud_err"):
        check(f"{k}: zgodne pola do podstawienia",
              set(re.findall(r"\{(\w+)\}", pl[k])),
              set(re.findall(r"\{(\w+)\}", en[k])))

    print("\n2. Okno buduje sie w obu jezykach")
    for lang in ("pl-PL", "en-US"):
        config.set_ui_language(lang)
        dlg = cd.CloudDialog()
        etykiety = dlg.findChildren(QLabel) + dlg.findChildren(QPushButton)
        teksty = [w.text() for w in etykiety if w.text()]
        check(f"[{lang}] okno ma tresc", len(teksty) > 8, True)
        surowe = [t for t in teksty if KLUCZ_RE.match(t)]
        check(f"[{lang}] zaden napis nie jest surowym kluczem", surowe, [])
        puste = [w.objectName() for w in dlg.findChildren(QPushButton) if not w.text()]
        check(f"[{lang}] kazdy przycisk ma napis", puste, [])

        # ⚠️ KAZDA etykieta musi miec JAWNY kolor. Bez tego bierze barwe z palety
        # Qt, co w ciemnym motywie daje CZARNY TEKST NA CZARNYM TLE — realny blad
        # zgloszony przez usera 2026-07-21 ("Polaczono z Dyskiem Google" bylo
        # niewidoczne). Podglad renderowany z WLASNYM stylem tego nie pokazal,
        # bo nie odtwarzal warunkow aplikacji — dlatego regula strukturalna.
        bez_koloru = [(w.text() or "(pusta)")[:34] for w in dlg.findChildren(QLabel)
                      if "color:" not in (w.styleSheet() or "")]
        check(f"[{lang}] kazda etykieta ma jawny kolor", bez_koloru, [])

        # Ucinanie tekstu — miara jak w tools/scan-dialog-clipping.py: porownujemy
        # REALNA geometrie po pokazaniu okna z tym, ile widzet sam deklaruje, ze
        # potrzebuje. ⚠️ Nie zgaduj marginesow (pierwsza wersja tego testu dodawala
        # "+24 px na oko" i oskarzala WSZYSTKIE przyciski w obu jezykach — falszywy
        # alarm). Dla etykiet z zawijaniem wlasciwa miara to heightForWidth().
        dlg.resize(dlg.sizeHint())
        dlg.show()
        app.processEvents()
        sciete = []
        for w in dlg.findChildren(QPushButton) + dlg.findChildren(QLabel):
            if not w.isVisible():
                continue
            potrzeba_h = (w.heightForWidth(w.width())
                          if w.hasHeightForWidth() and w.width() > 0
                          else w.sizeHint().height())
            if w.height() < potrzeba_h or w.width() < w.sizeHint().width():
                sciete.append(w.text()[:30])
        check(f"[{lang}] nic nie jest sciete", sciete, [])
        dlg.hide()
        dlg.deleteLater()

    print("\n3. Haslo paczki: zapis i odczyt")
    config.set_ui_language("pl-PL")
    check("brak pliku -> puste haslo", cd.load_passphrase(), "")
    cd.save_passphrase("ABCD-EFGH-IJKL")
    check("zapisane i odczytane", cd.load_passphrase(), "ABCD-EFGH-IJKL")
    check("plik tylko dla wlasciciela (600)",
          oct(cd.CLOUD_PASSPHRASE_FILE.stat().st_mode & 0o777), "0o600")
    cd.save_passphrase("   ")
    check("puste haslo NIE nadpisuje zapisanego", cd.load_passphrase(), "ABCD-EFGH-IJKL")

    print("\n4. Generator kodu (do przepisania z kartki)")
    from core.cloud import bundle_crypto as bc
    kod = bc.generate_passphrase()
    check("kod ma sensowna dlugosc", 20 <= len(kod) <= 40, True)
    mylace = set("0O1lI") & set(kod)
    check("bez znakow mylonych przy przepisywaniu (0/O, 1/l/I)", mylace, set())

    print(f"\n=== WYNIK: {PASS} OK, {FAIL} FAIL ===")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
