#!/usr/bin/env python3
"""Bramka: okna POBOCZNE też idą za przełączeniem jasny/ciemny W LOCIE.

ZGŁOSZENIE 2026-10-20 (zrzut właściciela): program ciemny, a okno „Dodaj pliki"
jasne. Przyczyna: kolory zapamiętane w STAŁEJ przy imporcie modułu (paleta ze
startu), więc po przełączeniu trybu w locie zostawały w starym. test-theme-live
tego nie widział — porównuje zrzut GŁÓWNEGO okna, a okna plików nikt tam nie
otwiera. Ten sam błąd siedział w 4 miejscach:

  [1] okno wyboru plików (get_file_dialog_stylesheet),
  [2] ramka listy rozwijanej w oknach ustawień (_StyledComboBox.showPopup),
  [3] kolorowe znaczki stanu serwerów MCP (_mcp_status_badge),
  [4] błysk przycisku czyszczenia pola (MainWindow._FLASH_COLORS).
  [S] SKAN całego src/: żadne przypisanie na poziomie modułu/klasy ani domyślny
      argument funkcji nie czyta tokenu koloru z theme (to jest ta klasa błędu;
      wyjątek: DEFAULT_SKIN_COLORS — odświeżany w miejscu przy przełączeniu).
  [K] kontrola negatywna: oba tryby mają RÓŻNE wartości sprawdzanych tokenów
      (inaczej [1]–[4] przechodziłyby na ślepo).

URUCHOMIENIE:
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u CLAUDE_CODE_SUBAGENT_MODEL \\
        QT_QPA_PLATFORM=offscreen venv/bin/python -B tools/test-theme-live-dialogs.py
"""
import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
# Start zawsze CIEMNY, niezależnie od config.json użytkownika (bramka ma mierzyć
# program, nie stan komputera).
os.environ["CVA_APPEARANCE"] = "dark"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt                                  # noqa: E402
from PyQt5.QtWidgets import QApplication                     # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_app = QApplication(sys.argv[:1])

from gui import theme                                        # noqa: E402
from gui import dialogs                                      # noqa: E402
from gui.main_window import MainWindow                       # noqa: E402

PASSED = FAILED = 0


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"[OK]   {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


def popup_style(mode):
    theme.set_appearance(mode)
    combo = dialogs._StyledComboBox()
    combo.addItems(["a", "b"])
    combo.showPopup()
    style = combo.view().parentWidget().styleSheet()
    combo.hidePopup()
    combo.deleteLater()
    return style


def flash_color():
    # Dokładnie to wyrażenie, którym okno główne wybiera kolor błysku.
    return getattr(theme, MainWindow._FLASH_COLORS.get("clear_input_btn", "ACCENT"))


DARK, LIGHT = dict(theme._DARK), dict(theme._LIGHT)

# [K] — sprawdzane tokeny różnią się między trybami
for tok in ("SURFACE", "BG_WINDOW", "SURFACE_ALT", "SUCCESS", "DANGER"):
    check(f"[K] token {tok} różny w trybach", DARK[tok].lower() != LIGHT[tok].lower(),
          f"{DARK[tok]} == {LIGHT[tok]}")

check("[0] start w trybie ciemnym", theme.APPEARANCE == theme.APPEARANCE_DARK, theme.APPEARANCE)

# Przełączamy tam i z powrotem: ciemny → jasny → ciemny.
for mode, pal, other in (("light", LIGHT, DARK), ("dark", DARK, LIGHT)):
    theme.set_appearance(mode)
    css = dialogs.get_file_dialog_stylesheet().lower()
    check(f"[1] okno plików po przełączeniu na {mode}: tło z tego trybu",
          pal["SURFACE"].lower() in css and other["SURFACE"].lower() not in css)
    check(f"[1] okno plików po przełączeniu na {mode}: pola z tego trybu",
          pal["BG_WINDOW"].lower() in css and other["BG_WINDOW"].lower() not in css)

    st = popup_style(mode).lower()
    check(f"[2] lista rozwijana po przełączeniu na {mode}",
          pal["SURFACE_ALT"].lower() in st and other["SURFACE_ALT"].lower() not in st, st)

    _, col, _ = dialogs._mcp_status_badge(dialogs.STATUS_CONNECTED)
    check(f"[3] znaczek MCP „połączony” po przełączeniu na {mode}",
          col.lower() == pal["SUCCESS"].lower(), col)
    _, col, _ = dialogs._mcp_status_badge(dialogs.STATUS_FAILED)
    check(f"[3] znaczek MCP „błąd” po przełączeniu na {mode}",
          col.lower() == pal["DANGER"].lower(), col)

    check(f"[4] błysk czyszczenia pola po przełączeniu na {mode}",
          str(flash_color()).lower() == pal["DANGER"].lower(), flash_color())

# [4b] okno główne naprawdę używa nazwy tokenu (a nie zamrożonego koloru)
src_mw = (ROOT / "src/gui/main_window.py").read_text(encoding="utf-8")
check("[4b] okno główne czyta kolor błysku w chwili błysku",
      "getattr(theme, self._FLASH_COLORS.get(attr, 'ACCENT'))" in src_mw)

# [S] skan klasy błędu w całym src/
ALLOWED = {("src/gui/main_window.py", "DEFAULT_SKIN_COLORS")}
check("[S0] DEFAULT_SKIN_COLORS odświeżany przy przełączeniu",
      "DEFAULT_SKIN_COLORS.update(theme.skin_colors())" in src_mw)


def frozen_reads(node):
    """Odczyty theme.TOKEN poza lambdą/funkcją wewnątrz węzła."""
    out = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "theme" and n.attr.isupper()):
            out.add(n.attr)
        stack.extend(ast.iter_child_nodes(n))
    return out


hits = []
for p in sorted((ROOT / "src").rglob("*.py")):
    rel = str(p.relative_to(ROOT))
    if p.name == "theme.py":
        continue
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.args.defaults + [d for d in n.args.kw_defaults if d]:
                r = frozen_reads(d)
                if r:
                    hits.append(f"{rel}:{d.lineno} domyślny argument {sorted(r)}")

    def scan(body):
        for n in body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                names = {t.id for t in targets if isinstance(t, ast.Name)}
                if any((rel, nm) in ALLOWED for nm in names):
                    continue
                r = frozen_reads(n.value) if n.value else set()
                if r:
                    hits.append(f"{rel}:{n.lineno} {sorted(names)} {sorted(r)}")
            elif isinstance(n, ast.ClassDef):
                scan(n.body)
    scan(tree.body)

check("[S] żaden kolor z theme nie jest zamrażany przy imporcie (moduł/klasa/argument)",
      not hits, "\n       " + "\n       ".join(hits))

print(f"\nWynik: {PASSED} OK, {FAILED} FAIL")
sys.exit(1 if FAILED else 0)
