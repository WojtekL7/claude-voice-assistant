#!/usr/bin/env python3
"""Bramka: przycisk „/" — polecenia Claude Code na dolnym pasku (2026-10-20).

  [L] lista wbudowanych: 12 „najczęstszych", bez duplikatów, opisy PL i EN,
      BEZ poleceń, które w zakładce VCA psują pracę (exit, theme, tui, …),
  [D] skille i polecenia czytane z dysku (atrapa HOME + katalog projektu):
      opis wielolinijkowy `>-`, nazwa = KATALOG skilla, ukryte (user-invocable:
      false, skillOverrides „off"), katalog bez SKILL.md pominięty, commands/x.md
      → /x, commands/dir/y.md → /dir:y, projekt nadpisuje dom, nazwa wbudowana
      nie dubluje się,
  [P] przycisk na pasku: między ⚡ a myszą, ikona SVG, tło jak u sąsiada (nie
      biały kwadrat), ikona w kolorze skórki błyskawicy,
  [M] menu: sekcje, liczniki, klik wpisuje „/compact " z kursorem NA KOŃCU i
      NIC nie wysyła; „pełna lista" wpisuje sam „/" w terminal (bez Enter),
  [K] kontrola negatywna: bez stylowania tło przycisku JEST jasne.

URUCHOMIENIE:
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u CLAUDE_CODE_SUBAGENT_MODEL \\
        QT_QPA_PLATFORM=offscreen venv/bin/python -B tools/test-slash-commands.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ["CVA_APPEARANCE"] = "dark"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt                                  # noqa: E402
from PyQt5.QtGui import QPixmap                              # noqa: E402
from PyQt5.QtWidgets import QApplication                     # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_app = QApplication(sys.argv[:1])

from core import slash_commands as sc                        # noqa: E402

PASSED = FAILED = 0


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"[OK]   {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


# ---- [L] lista wbudowanych ---------------------------------------------------
pl, en = sc.builtin_commands("pl-PL"), sc.builtin_commands("en-US")
names = [c.name for c in pl]
check("[L1] 12 najczęstszych", sum(c.common for c in pl) == 12, sum(c.common for c in pl))
check("[L2] bez duplikatów", len(names) == len(set(names)))
check("[L3] każdy ma opis PL i EN, różne języki",
      all(a.description and b.description for a, b in zip(pl, en))
      and pl[0].description != en[0].description)
ZAKAZANE = {"exit", "quit", "theme", "tui", "background", "stop", "teleport",
            "session", "remote-control", "desktop", "voice", "terminal-setup",
            "restart", "ultraplan", "ultrareview"}
check("[L4] brak poleceń psujących zakładkę VCA", not (set(names) & ZAKAZANE),
      set(names) & ZAKAZANE)
check("[L5] wpis to ukośnik + nazwa + spacja", pl[0].text == "/compact ", pl[0].text)

# ---- [D] odczyt z dysku ------------------------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="slash-test-"))
home, proj = tmp / "home", tmp / "proj"


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


w(home / ".claude/skills/zwykly/SKILL.md", "---\nname: zwykly\ndescription: Krótki opis\n---\nTreść")
w(home / ".claude/skills/wielo/SKILL.md",
  "---\nname: wielo\ndescription: >-\n  Pierwsza linia\n  druga linia.\nallowed-tools: x\n---\n")
w(home / ".claude/skills/nazwa-katalogu/SKILL.md", "---\nname: Ładna Nazwa\ndescription: d\n---\n")
w(home / ".claude/skills/ukryty/SKILL.md", "---\nname: ukryty\ndescription: d\nuser-invocable: false\n---\n")
w(home / ".claude/skills/wylaczony/SKILL.md", "---\nname: wylaczony\ndescription: d\n---\n")
(home / ".claude/skills/synced").mkdir(parents=True)                    # bez SKILL.md
w(home / ".claude/skills/compact/SKILL.md", "---\nname: compact\ndescription: d\n---\n")
w(home / ".claude/commands/moje.md", "---\ndescription: Z nagłówka\n---\nciało")
w(home / ".claude/commands/grupa/pod.md", "# Pierwsza linia jako opis\nreszta")
w(home / ".claude/skills/wspolny/SKILL.md", "---\ndescription: z domu\n---\n")
w(proj / ".claude/skills/wspolny/SKILL.md", "---\ndescription: z projektu\n---\n")
w(proj / ".claude/commands/projektowe.md", "Opis projektu")

cc = {c.name: c for c in sc.custom_commands(str(proj), home=home,
                                            overrides={"wylaczony": "off"})}
check("[D1] opis wielolinijkowy `>-` złożony w jedno zdanie",
      cc.get("wielo") and cc["wielo"].description == "Pierwsza linia druga linia.",
      cc.get("wielo"))
check("[D2] skill wywoływany nazwą KATALOGU", "nazwa-katalogu" in cc and "Ładna Nazwa" not in cc)
check("[D3] user-invocable: false ukryty", "ukryty" not in cc)
check("[D4] skillOverrides „off” ukryty", "wylaczony" not in cc)
check("[D5] katalog bez SKILL.md pominięty", "synced" not in cc)
check("[D6] nazwa wbudowana się nie dubluje", "compact" not in cc)
check("[D7] commands/moje.md → /moje z opisem z nagłówka",
      cc.get("moje") and cc["moje"].description == "Z nagłówka")
check("[D8] commands/grupa/pod.md → /grupa:pod, opis z pierwszej linii",
      cc.get("grupa:pod") and cc["grupa:pod"].description == "Pierwsza linia jako opis")
check("[D9] projekt nadpisuje dom",
      cc.get("wspolny") and cc["wspolny"].description == "z projektu"
      and cc["wspolny"].source == sc.SOURCE_PROJECT)
check("[D10] polecenie projektu widoczne", "projektowe" in cc)
check("[D11] brak katalogu .claude = pusta lista, bez wyjątku",
      sc.custom_commands(str(tmp / "nie-ma"), home=tmp / "nie-ma-domu", overrides={}) == [])
check("[D12] skrót opisu w menu ≤ limit, z wielokropkiem",
      len(sc.short("x" * 200)) == sc.MENU_DESC_MAX and sc.short("x" * 200).endswith("…"))

# ---- [P] przycisk na pasku ---------------------------------------------------
from gui import theme                                        # noqa: E402
from gui.agent_tab import AgentTab                           # noqa: E402
from gui.main_window import MainWindow, DEFAULT_SKIN_COLORS  # noqa: E402

tab = AgentTab({"id": "test", "name": "Test", "working_directory": str(proj)})
btn = tab.slash_commands_btn
lay = btn.parentWidget().layout()


def idx(w_):
    def znajdz(uklad):
        for i in range(uklad.count()):
            it = uklad.itemAt(i)
            if it.widget() is w_:
                return uklad, i
            if it.layout() is not None:
                r = znajdz(it.layout())
                if r:
                    return r
        return None
    return znajdz(lay)


a, b, c = idx(tab.quick_actions_btn), idx(btn), idx(tab.mouse_mode_btn)
check("[P1] „/” stoi między ⚡ a myszą",
      a and b and c and a[0] is b[0] is c[0] and a[1] < b[1] < c[1], (a, b, c))
check("[P2] ma ikonę SVG", not btn.icon().isNull())


def jasnosc(przycisk):
    przycisk.resize(44, 44)
    pix = QPixmap(przycisk.size())
    pix.fill(Qt.transparent)
    przycisk.render(pix)
    px = pix.toImage().pixelColor(6, 6)
    return (px.red() + px.green() + px.blue()) // 3


class Atrapa:
    skin_colors = dict(DEFAULT_SKIN_COLORS, icon_quick_actions_color="#ff0000")
    _apply_button_icon_style = MainWindow._apply_button_icon_style
    _apply_send_button_style = MainWindow._apply_send_button_style
    _BUTTON_COLOR_KEYS = MainWindow._BUTTON_COLOR_KEYS
    _icon = MainWindow._icon

    def __init__(self, z):
        self.agent_tabs = {"test": z}


przed = jasnosc(btn)
MainWindow._apply_button_icon_styles(Atrapa(tab))
po, sasiad = jasnosc(btn), jasnosc(tab.quick_actions_btn)
check("[K] bez stylowania tło JEST jasne (miara odróżnia)", przed > 200, przed)
check("[P3] po stylowaniu tło jak u ⚡ (nie biały kwadrat)", abs(po - sasiad) <= 6, (po, sasiad))

MainWindow._apply_skin_icons(Atrapa(tab))
px = btn.icon().pixmap(22, 22).toImage()
czerwone = sum(1 for y in range(22) for x in range(22)
               if px.pixelColor(x, y).alpha() > 200 and px.pixelColor(x, y).red() > 200
               and px.pixelColor(x, y).green() < 60)
check("[P4] ikona w kolorze skórki błyskawicy (zmiana skórki ją przemalowuje)",
      czerwone > 10, f"czerwonych pikseli={czerwone}")
check("[P5] „/” ma stan „w użyciu” jak ⚡",
      "slash_commands_btn" in MainWindow._BUTTONS_WITH_ACTIVE_STATE
      and MainWindow._BUTTON_ICON_KEYS.get("slash_commands_btn") == "slash_commands")

# ---- [M] menu ----------------------------------------------------------------
import gui.agent_tab as at                                   # noqa: E402
_real = at.slash_commands.custom_commands
at.slash_commands.custom_commands = lambda cwd: _real(cwd, home=home, overrides={})
tab._build_slash_menu()
menu = btn.menu()
acts = menu.actions()
teksty = [x.text() for x in acts]
subs = [x.menu() for x in acts if x.menu()]
check("[M1] na górze sekcja „Najczęstsze” i 12 poleceń",
      acts[0].text() == at.tr("slash_common") and not acts[0].isEnabled() and sum(t.startswith("/") for t in teksty) == 12, teksty[:3])
check("[M2] dwa podmenu z licznikami (wbudowane, Twoje)",
      len(subs) == 2 and f"({len(pl) - 12})" in subs[0].title()
      and f"({len(cc) + 1})" in subs[1].title(),          # +1: „wylaczony” (tu bez overrides)
      [s.title() for s in subs])
tab._build_slash_menu()
check("[M3] ponowne rozwinięcie nie dubluje pozycji", len(btn.menu().actions()) == len(acts))

wyslane = []
tab.message_sent.connect(wyslane.append)
compact = next(x for x in btn.menu().actions() if x.text().startswith("/compact"))
compact.trigger()
cur = tab.input_field.textCursor()
check("[M4] klik wpisuje „/compact ” w pole", tab.input_field.text() == "/compact ",
      repr(tab.input_field.text()))
check("[M5] kursor na końcu (gotowy pod argument)", cur.position() == len("/compact "),
      cur.position())
check("[M6] nic nie zostało wysłane", wyslane == [])


class TermAtrapa:
    def __init__(self):
        self.sent, self.focused = [], False

    def send_text(self, t):
        self.sent.append(t)

    def focus_terminal(self):
        self.focused = True


_stary = tab.terminal_backend
tab.terminal_backend = term = TermAtrapa()
next(x for x in btn.menu().actions() if x.text() == at.tr("slash_full_list")).trigger()
check("[M7] „pełna lista” wpisuje sam „/” w terminal (bez Enter) i daje mu fokus",
      term.sent == ["/"] and term.focused, term.sent)
tab.terminal_backend = _stary

print(f"\nWynik: {PASSED} OK, {FAILED} FAIL")
sys.exit(1 if FAILED else 0)
