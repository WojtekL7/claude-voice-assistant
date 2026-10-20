#!/usr/bin/env python3
"""Bramka: przełączanie jasny/ciemny W LOCIE = wygląd jak po uruchomieniu w tym trybie.

ZAMÓWIENIE 2026-10-20: „zmiana motywu bez restartu, jednym kliknięciem".
Dotąd paleta była ustalana raz przy starcie, a kilka miejsc zapamiętywało
kolory przy budowie okna. Każde takie miejsce, które ZAPOMNI się przemalować,
zostaje po przełączeniu „wyspą" starego trybu — objaw widać tylko na ekranie.

Dlatego dowodem jest PIKSEL, nie kod: budujemy PRAWDZIWE okno programu
(osobny proces, atrapa HOME, offscreen) w trzech wariantach i porównujemy zrzuty:
  [A] start ciemny → przełącz na jasny   ==  start od razu jasny
  [B] start jasny  → przełącz na ciemny  ==  start od razu ciemny
  [C] ciemny → jasny → ciemny            ==  start od razu ciemny (powrót bez śladów)
  [D] każdy tryb ma WŁASNĄ skórkę: własne kolory obu trybów przeżywają
      przełączanie tam i z powrotem, w oknie i w config.json,
  [E] Claude Code w zakładkach dostaje motyw `dark-ansi` w OBU trybach
      (rysuje kolorami terminala, więc przełącza się razem z oknem);
      wariant dla daltonistów wybrany przez użytkownika jest szanowany,
  [F] przełącznik „Auto-czytaj": w jasnym JASNA szyna (zgłoszenie 2026-10-20),
      w ciemnym oryginalny obrazek bez zmian,
  [G] przycisk ☀️/🌙 pokazuje tryb, na który przełączy, i zapisuje wybór.
  [K] kontrola negatywna: porównanie zrzutów WYKRYWA różnicę trybów
      (zrzut ciemny ≠ jasny) — inaczej [A]–[C] przechodziłyby na ślepym teście.

Normalizacja przed zrzutem (identyczna we wszystkich wariantach): wskaźnik RAM
zamrożony na jednej wartości, licznik kontekstu odświeżony raz, pasek statusu
bez komunikatu — to treść zmienna w czasie, nie kolor.

URUCHOMIENIE:
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u CLAUDE_CODE_SUBAGENT_MODEL \\
        venv/bin/python -B tools/test-theme-live.py
Sabotaż: tools/sabotaz-theme-live.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
PASSED = 0
FAILED = 0

CHILD = r'''
import json, os, sys, time
sys.path.insert(0, os.path.join(sys.argv[1], "src"))
out_png, switches = sys.argv[2], [m for m in sys.argv[3].split(",") if m]
from PyQt5.QtCore import Qt, QCoreApplication
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
app = QApplication(sys.argv[:1])
app.setCursorFlashTime(0)          # kursor bez mrugania = powtarzalne piksele
# Okna wymagające kliknięcia (kreator, pytanie o wznowienie) — automatyczne „nie".
QDialog.exec_ = QDialog.exec = lambda *a, **k: 0
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
from gui import main_window as mw, theme

def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents(); time.sleep(0.02)

w = mw.MainWindow()
w.resize(1200, 800); w.show()
# Czekamy na GOTOWOŚĆ terminali, nie na stały czas: zmierzone 2026-10-20 —
# zrzut zrobiony w trakcie wczytywania strony terminala różnił się w CAŁYM
# jego obszarze (564 040 px), co wyglądało jak błąd przełączania.
def terminals_ready():
    for tab in w.agent_tabs.values():
        be = getattr(tab, "terminal_backend", None)
        term = getattr(be, "_term", None)
        if term is not None and not getattr(term, "_frontend_ready", True):
            return False
    return True
end = time.time() + 25
while time.time() < end and not terminals_ready():
    pump(0.2)
pump(1.5)
for m in switches:
    if m == "toggle":
        w._appearance_btn.click()
    else:
        w._set_appearance(m)
    pump(1.5)
rm = w.resource_monitor
if getattr(rm, "_timer", None) is not None:
    rm._timer.stop()
rm._pct = rm._pressure = 34
rm.update()
w._refresh_context_label()
w.status_bar.clearMessage()
pump(0.8)
# Terminal rysuje osobny proces przeglądarki: zrzut potrafi złapać jego
# OSTATNIĄ klatkę sprzed przemalowania (zmierzone 2026-10-20: ~1 na 10
# przebiegów pod obciążeniem obszar terminala był jeszcze w starym trybie).
# Dlatego zrzut robimy, aż obraz się USTALI (dwa kolejne identyczne), i
# raportujemy, ile to trwało — wynik końcowy porównujemy, czas pilnujemy osobno.
t0 = time.time()
prev = w.grab().toImage()
settled = None
while time.time() - t0 < 8:
    pump(0.5)
    img = w.grab().toImage()
    if img == prev:
        settled = round(time.time() - t0, 1)
        break
    prev = img
prev.save(out_png)
cfg = json.load(open(mw.CONFIG_FILE, encoding="utf-8"))
print("WYNIK " + json.dumps({
    "settled_s": settled,
    "mode": theme.APPEARANCE,
    "skin_bottom": w.skin_colors.get("bottom_panel_bg"),
    "skin_term": w.skin_colors.get("terminal_bg"),
    "tooltip": w._appearance_btn.toolTip(),
    "cfg_appearance": cfg.get("appearance"),
    "cfg_dark_bottom": (cfg.get("skin_colors") or {}).get("bottom_panel_bg"),
    "cfg_light_bottom": (cfg.get("skin_colors_light") or {}).get("bottom_panel_bg"),
    "menu_checked": [m for m, a in w.appearance_actions.items() if a.isChecked()],
}))
sys.stdout.flush()
os._exit(0)
'''


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"[OK]   {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


def run_window(tmp, label, start, switches=(), config_extra=None):
    """Zbuduj prawdziwe okno w osobnym procesie; zwróć (ścieżka PNG, słownik wyników)."""
    home = Path(tmp) / f"home-{label}"
    cfg_dir = home / ".vibe-coding-assistant"
    cfg_dir.mkdir(parents=True)
    cfg = {"language": "pl", "appearance": start, "auto_run_claude": False,
           "auto_check_updates": False, "dictation_reminder_dismissed": True}
    cfg.update(config_extra or {})
    (cfg_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    child = Path(tmp) / "child.py"
    child.write_text(CHILD, encoding="utf-8")
    png = Path(tmp) / f"{label}.png"
    env = {k: v for k, v in os.environ.items()
           if k not in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "CLAUDECODE",
                        "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SUBAGENT_MODEL")}
    env.update(HOME=str(home), CVA_APPEARANCE=start, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([PY, "-B", str(child), str(ROOT), str(png), ",".join(switches)],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    wynik = None
    for line in proc.stdout.splitlines():
        if line.startswith("WYNIK "):
            wynik = json.loads(line[6:])
    if wynik is None or not png.exists():
        print(f"--- {label}: proces nie oddał wyniku (kod {proc.returncode})")
        print(proc.stderr[-2000:])
    return png, wynik


def diff_pixels(a, b):
    """(liczba różnych pikseli, prostokąt różnic) dla dwóch zrzutów."""
    import numpy as np
    from PyQt5.QtGui import QImage

    def arr(p):
        img = QImage(str(p)).convertToFormat(QImage.Format_RGB32)
        ptr = img.constBits()
        ptr.setsize(img.byteCount())
        return np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine())[:, :img.width() * 4].copy()

    x, y = arr(a), arr(b)
    if x.shape != y.shape:
        return -1, f"rozmiary {x.shape} vs {y.shape}"
    mask = (x.reshape(x.shape[0], -1, 4) != y.reshape(y.shape[0], -1, 4)).any(axis=2)
    n = int(mask.sum())
    if not n:
        return 0, ""
    ys, xs = np.nonzero(mask)
    cy, cx = int(ys[len(ys) // 2]), int(xs[len(xs) // 2])
    px = lambda arr_, y_, x_: "#%02x%02x%02x" % tuple(arr_.reshape(arr_.shape[0], -1, 4)[y_, x_, 2::-1])
    return n, (f"x {xs.min()}–{xs.max()}, y {ys.min()}–{ys.max()}; "
               f"piksel ({cx},{cy}): {Path(a).stem}={px(x, cy, cx)} {Path(b).stem}={px(y, cy, cx)}")


def brightness_of_svg_fill(svg_text, tag="rect"):
    import re
    m = re.search(rf'<{tag}[^>]*fill="(#[0-9a-fA-F]{{6}})"', svg_text)
    if not m:
        return None, None
    c = m.group(1)
    return c, sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) / 3


def main():
    with tempfile.TemporaryDirectory() as tmp:
        png_dark, r_dark = run_window(tmp, "swiezy-ciemny", "dark")
        png_light, r_light = run_window(tmp, "swiezy-jasny", "light")
        png_d2l, r_d2l = run_window(tmp, "ciemny-na-jasny", "dark", ["light"])
        png_l2d, r_l2d = run_window(tmp, "jasny-na-ciemny", "light", ["dark"])
        png_rt, r_rt = run_window(tmp, "tam-i-z-powrotem", "dark", ["light", "dark"])
        png_btn, r_btn = run_window(tmp, "przycisk", "dark", ["toggle"])

        wszystkie = (r_dark, r_light, r_d2l, r_l2d, r_rt, r_btn)
        check("[0] wszystkie okna zbudowane", all(wszystkie),
              str([r is not None for r in wszystkie]))
        if not all(wszystkie):
            return

        n, gdzie = diff_pixels(png_dark, png_light)
        check("[K] kontrola negatywna: zrzut ciemny ≠ jasny (porównanie widzi różnicę)",
              n > 100000, f"różnych pikseli: {n}")

        czasy = {"ciemny→jasny": r_d2l["settled_s"], "jasny→ciemny": r_l2d["settled_s"],
                 "tam i z powrotem": r_rt["settled_s"]}
        check("[S] obraz po przełączeniu ustala się (< 8 s) — nie miga w nieskończoność",
              all(v is not None for v in czasy.values()), str(czasy))

        n, gdzie = diff_pixels(png_d2l, png_light)
        check("[A] ciemny → jasny w locie = start od razu w jasnym (co do piksela)",
              n == 0, f"różnych pikseli: {n}, obszar: {gdzie}")
        n, gdzie = diff_pixels(png_l2d, png_dark)
        check("[B] jasny → ciemny w locie = start od razu w ciemnym (co do piksela)",
              n == 0, f"różnych pikseli: {n}, obszar: {gdzie}")
        n, gdzie = diff_pixels(png_rt, png_dark)
        check("[C] ciemny → jasny → ciemny = start w ciemnym (powrót bez śladów)",
              n == 0, f"różnych pikseli: {n}, obszar: {gdzie}")
        n, gdzie = diff_pixels(png_btn, png_light)
        check("[G1] przycisk ☀️/🌙 kliknięty w ciemnym = start w jasnym",
              n == 0, f"różnych pikseli: {n}, obszar: {gdzie}")

        check("[G2] tryb i zapis po przełączeniu: tryb=light, config.json appearance=light",
              r_d2l["mode"] == "light" and r_d2l["cfg_appearance"] == "light", str(r_d2l))
        check("[G3] menu Wygląd zaznacza tryb po przełączeniu",
              r_d2l["menu_checked"] == ["light"] and r_l2d["menu_checked"] == ["dark"],
              f"{r_d2l['menu_checked']} / {r_l2d['menu_checked']}")
        check("[G4] podpowiedź przycisku mówi, NA CO przełączy",
              "ciemny" in r_light["tooltip"] and "jasny" in r_dark["tooltip"]
              and r_btn["tooltip"] == r_light["tooltip"],
              f"ciemny:{r_dark['tooltip']!r} jasny:{r_light['tooltip']!r}")

        # [D] osobne skórki trybów przeżywają przełączanie
        from_dark, from_light = "#123456", "#fedcba"
        extra = {"skin_version": 6, "skin_colors": {"bottom_panel_bg": from_dark},
                 "skin_version_light": 6, "skin_colors_light": {"bottom_panel_bg": from_light}}
        _, s1 = run_window(tmp, "skorki-tam", "dark", ["light"], extra)
        _, s2 = run_window(tmp, "skorki-tam-i-z-powrotem", "dark", ["light", "dark"], extra)
        check("[D1] po przełączeniu na jasny okno bierze JASNĄ skórkę użytkownika",
              s1 and s1["skin_bottom"] == from_light, str(s1))
        check("[D2] ciemna skórka użytkownika zapisana nietknięta obok jasnej",
              s1 and s1["cfg_dark_bottom"] == from_dark and s1["cfg_light_bottom"] == from_light,
              str(s1))
        check("[D3] po powrocie na ciemny wraca CIEMNA skórka użytkownika, jasna zostaje w pliku",
              s2 and s2["skin_bottom"] == from_dark and s2["cfg_light_bottom"] == from_light,
              str(s2))
        check("[D4] domyślne kolory nieustawione przez usera idą za trybem (terminal)",
              s1 and s2 and s1["skin_term"] != s2["skin_term"],
              f"{s1 and s1['skin_term']} / {s2 and s2['skin_term']}")

    # [E] motyw Claude Code
    sys.path.insert(0, str(ROOT / "src"))
    from core import claude_hooks as ch
    with tempfile.TemporaryDirectory() as h:
        h = Path(h)
        check("[E1] tryb ciemny → dark-ansi", ch.claude_theme_for(False, h) == "dark-ansi")
        check("[E2] tryb jasny → dark-ansi (ten sam: przełącza się kolorami terminala)",
              ch.claude_theme_for(True, h) == "dark-ansi")
        (h / ".claude").mkdir()
        (h / ".claude" / "settings.json").write_text('{"theme": "light"}')
        check("[E3] zwykły wybór usera (light) nie blokuje przełączania → dark-ansi",
              ch.claude_theme_for(True, h) == "dark-ansi")
        (h / ".claude" / "settings.json").write_text('{"theme": "dark-daltonized"}')
        check("[E4] daltonizm szanowany: ciemny + dark-daltonized → nie narzucamy",
              ch.claude_theme_for(False, h) is None)
        check("[E5] daltonizm szanowany: jasny + dark-daltonized → light-daltonized",
              ch.claude_theme_for(True, h) == "light-daltonized")

    # [F] przełącznik auto-czytania
    code = ("import sys,json;sys.path.insert(0,'src');from gui import theme as t;"
            "from config import ASSETS_DIR as A;"
            "off=t.toggle_icon_path(A/'icons'/'toggle-off.svg',False);"
            "on=t.toggle_icon_path(A/'icons'/'toggle-on.svg',True);"
            "print(json.dumps({'off':off,'on':on,'offsvg':open(off).read(),"
            "'onsvg':open(on).read(),'panel':t.BG_PANEL,'accent':t.ACCENT}))")
    with tempfile.TemporaryDirectory() as h:
        res = {}
        for mode in ("dark", "light"):
            env = dict(os.environ, HOME=h, CVA_APPEARANCE=mode)
            res[mode] = json.loads(subprocess.run([PY, "-B", "-c", code], cwd=ROOT, env=env,
                                                  capture_output=True, text=True,
                                                  check=True).stdout)
    d, l = res["dark"], res["light"]
    check("[F1] ciemny: oryginalne obrazki przełącznika (wygląd bez zmian)",
          d["off"].endswith("assets/icons/toggle-off.svg")
          and d["on"].endswith("assets/icons/toggle-on.svg"), f"{d['off']} {d['on']}")
    kolor, jasnosc = brightness_of_svg_fill(l["offsvg"])
    check("[F2] jasny, wyłączony: szyna JASNA (jasność > 200/255)",
          jasnosc is not None and jasnosc > 200, f"szyna {kolor} jasność {jasnosc}")
    _, ciemna = brightness_of_svg_fill(d["offsvg"])
    check("[F3] kontrola: w ciemnym szyna była ciemna (< 60/255) — test widzi różnicę",
          ciemna is not None and ciemna < 60, f"jasność {ciemna}")
    gal, _ = brightness_of_svg_fill(l["offsvg"], "circle")
    sys.path.insert(0, str(ROOT / "src"))
    from gui import theme as T
    check("[F4] jasny, wyłączony: gałka odcina się od szyny (kontrast ≥ 3:1)",
          gal and kolor and T.contrast_ratio(gal, kolor) >= 3.0,
          f"gałka {gal} szyna {kolor} kontrast {gal and kolor and round(T.contrast_ratio(gal, kolor), 2)}")
    kol_on, _ = brightness_of_svg_fill(l["onsvg"])
    check("[F5] jasny, włączony: szyna w kolorze akcentu (sygnał STANU zostaje)",
          kol_on == l["accent"], f"{kol_on} vs {l['accent']}")


if __name__ == "__main__":
    main()
    print(f"\nWYNIK: {PASSED} OK, {FAILED} FAIL")
    sys.exit(1 if FAILED else 0)
