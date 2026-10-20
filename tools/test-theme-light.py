#!/usr/bin/env python3
"""Bramka: tryb JASNY palety — czytelność (kontrast) + nietknięty tryb ciemny.

Uruchomienie:  python3 tools/test-theme-light.py

Co pilnuje:
  [A] tryb ciemny po zmianie = DOKŁADNIE ten sprzed wprowadzenia trybu jasnego
      (porównanie z zamrożoną kopią wartości z commita 76d0e71),
  [B] obie palety mają te same tokeny (brak dziury = brak „wyspy" ciemnego),
  [C] kontrast WCAG w trybie jasnym: tekst ≥ 4,5:1, drobne/metadane i kolory
      znaczeniowe ≥ 3:1 — mierzone na każdym tle, na którym dany kolor leży,
  [D] sygnały (aktywna zakładka, panel „nieaktywny") wyraźnie odcięte od tła,
  [E] wybór trybu: zmienna CVA_APPEARANCE, config.json, fail-safe na ciemny,
  [F] motyw Claude Code w zakładkach: od 2026-10-20 ZAWSZE "dark-ansi" w NASZYM
      pliku --settings (przełącza się w locie kolorami terminala — szczegóły
      i pomiar w tools/test-theme-live.py [E]); wariant dla daltonistów szanowany,
  [G] stare kolory wpisane na sztywno (theme.by_mode): ciemny = dawna wartość,
  [H] kolory agentów (paleta + dowolny wybrany) czytelne na jasnym pasku,
      a w trybie ciemnym nietknięte,
  [I] ikony SVG przemalowane w trybie jasnym, oryginał w ciemnym,
  [J] OSOBNA skórka każdego trybu w config.json + zapis wybranego wyglądu,
  [R] ponowne uruchomienie: właściwe polecenie z kodu, z AppImage i z paczki,
  [K] kontrola negatywna: miara kontrastu odrzuca znaną złą parę
      (jasny fiolet trybu ciemnego na bieli).
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


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"[OK]   {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


def load(mode, home=None):
    """Słownik tokenów + skin_colors w danym trybie (osobny proces = czysty import)."""
    env = dict(os.environ)
    env.pop("CVA_APPEARANCE", None)
    if mode:
        env["CVA_APPEARANCE"] = mode
    if home:
        env["HOME"] = home
    code = ("import sys,json;sys.path.insert(0,'src');from gui import theme as t;"
            "d={k:getattr(t,k) for k in dir(t) if k.isupper() and isinstance(getattr(t,k),str)};"
            "print(json.dumps({'mode':t.APPEARANCE,'tok':d,'skin':t.skin_colors()}))")
    out = subprocess.run([PY, "-B", "-c", code], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def lum(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def brightness(hexc):
    return sum(int(hexc[i:i + 2], 16) for i in (1, 3, 5)) / 3


# Wartości trybu ciemnego z commita 76d0e71 (przed trybem jasnym) — zamrożone.
DARK_REFERENCE_SKIN_SHA = None   # liczone niżej z git show


def dark_reference():
    src = subprocess.run(["git", "show", "76d0e71:src/gui/theme.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    ns = {}
    exec(compile(src, "theme_76d0e71", "exec"), ns)
    tok = {k: v for k, v in ns.items() if k.isupper() and isinstance(v, str)}
    return tok, ns["skin_colors"]()


def run_py(mode, home, code):
    env = dict(os.environ)
    env.pop("CVA_APPEARANCE", None)
    if mode:
        env["CVA_APPEARANCE"] = mode
    env["HOME"] = home
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run([PY, "-B", "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True)


GHI_CODE = r"""
import sys, json, os
sys.path.insert(0, 'src')
from gui import theme as t
from gui.dialogs import AGENT_TAB_COLORS
light = t.is_light()
def out(ok, name, detail=''):
    print(json.dumps([bool(ok), name, str(detail)]))
out(t.by_mode('#123456', '#abcdef') == ('#abcdef' if light else '#123456'), '[G] by_mode')
bad = [c for c in AGENT_TAB_COLORS + ['#ffffff', '#ffff00', '#fff']
       if light and t.contrast_ratio(t.readable(c) if len(t.readable(c)) == 7 else '#000000', t.BG_PANEL) < 3.0]
out(not bad, '[H1] kolory agentów odcięte od paska ≥ 3:1', bad)
same = [c for c in AGENT_TAB_COLORS if t.readable(c) != c]
out((not same) if not light else True, '[H2] tryb ciemny: kolory agentów bez zmian', same)
out(t.readable('nie-kolor') == 'nie-kolor', '[H3] dziwna wartość przechodzi bez wyjątku')
src = os.path.join('src', 'gui', 'close_x.svg')
p = t.icon_path(src, t.TEXT_DIM)
txt = open(p, encoding='utf-8').read()
if light:
    out(p != src and '#9b93a8' not in txt and t.TEXT_DIM in txt, '[I1] ikona przemalowana', p)
    p2 = t.icon_path(os.path.join('src', 'gui', 'refresh.svg'), t.TEXT_DIM)
    out('#ffffff' not in open(p2, encoding='utf-8').read(), '[I2] biała ikona odświeżania przemalowana')
else:
    out(p == src, '[I1] tryb ciemny: oryginalny plik', p)
"""

J_CODE = r"""
import sys, json
sys.path.insert(0, 'src')
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from gui import main_window as mw
class Stub:
    def __getattr__(self, name):
        return lambda *a, **k: None
class S:
    api_key = ''
    fix_enabled = True
    def __getattr__(self, name):
        return lambda *a, **k: None
w = Stub.__new__(Stub)
w.__dict__.update(stt=S(), tts=S(), skin_colors=mw.DEFAULT_SKIN_COLORS.copy(),
                  skin_icons=dict(mw.DEFAULT_SKIN_ICONS), claude_command='claude',
                  auto_run_claude=True, last_active_agent_id=None, auto_read_responses=False)
mw.MainWindow._load_settings(w)
loaded = dict(w.skin_colors)
if '%NEW%':
    w.skin_colors['text_color'] = '%NEW%'
mw.MainWindow._save_settings(w)
print(json.dumps(loaded))
"""

R_CODE = r"""
import sys, json, os
sys.path.insert(0, 'src')
from core import platform_utils as pu
def out(ok, name, detail=''):
    print(json.dumps([bool(ok), name, str(detail)]))
cmd, env = pu.relaunch_command()
out(cmd[0] == sys.executable and len(cmd) == 2 and cmd[1] == os.path.abspath(sys.argv[0]),
    '[R1] z kodu: ten sam Python + ten sam skrypt', cmd)
os.environ.update(APPIMAGE='%APP%', APPDIR='/tmp/.mount_x', LD_LIBRARY_PATH='/tmp/.mount_x/lib',
                  LD_LIBRARY_PATH_ORIG='/usr/local/lib')
sys.frozen = True
cmd, env = pu.relaunch_command()
out(cmd[0] == '%APP%', '[R2] AppImage: plik .AppImage z dysku, nie montaż /tmp', cmd)
out('APPDIR' not in env and env.get('LD_LIBRARY_PATH') == '/usr/local/lib'
    and 'LD_LIBRARY_PATH_ORIG' not in env, '[R3] środowisko starej instancji wyczyszczone',
    {k: env.get(k) for k in ('APPDIR', 'LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG')})
out(env.get('PYINSTALLER_RESET_ENVIRONMENT') == '1', '[R4] paczka: nowa, niezależna instancja')
del os.environ['APPIMAGE']
cmd, env = pu.relaunch_command()
out(cmd[0] == sys.executable and len(cmd) == 1 + len(sys.argv[1:]), '[R5] .exe/.app: ten sam plik', cmd)
"""


def main():
    dark = load("dark")
    light = load("light")
    ref_tok, ref_skin = dark_reference()

    # [A]
    check("[A1] tryb ciemny: skórka identyczna jak przed zmianą",
          dark["skin"] == ref_skin,
          str({k: (ref_skin.get(k), dark["skin"].get(k)) for k in set(ref_skin) | set(dark["skin"])
               if ref_skin.get(k) != dark["skin"].get(k)}))
    changed = {k for k in ref_tok if dark["tok"].get(k) != ref_tok[k]}
    check("[A2] tryb ciemny: żaden dawny token nie zmienił wartości", not changed, str(changed))

    # [B]
    tl, td = light["tok"], dark["tok"]
    check("[B1] obie palety: te same tokeny", set(tl) == set(td), str(set(tl) ^ set(td)))
    check("[B2] skórka: te same klucze w obu trybach",
          set(light["skin"]) == set(dark["skin"]))
    same = [k for k in ("BG_WINDOW", "BG_PANEL", "TEXT", "TEXT_DIM", "SURFACE", "BG_CANVAS",
                        "TERM_FG", "ACCENT_LIGHT", "HOVER", "BORDER") if tl[k] == td[k]]
    check("[B3] tryb jasny naprawdę podmienia kluczowe kolory", not same, str(same))

    # [C] kontrast — (kolor, tła, próg)
    T = tl
    bgs_ui = ["BG_WINDOW", "BG_PANEL", "BG_BAR", "BG_INPUT", "SURFACE", "SURFACE_ALT",
              "SURFACE_HOVER", "TAB_ACTIVE", "HOVER"]
    rules = [
        ("TEXT", bgs_ui + ["SURFACE_INACTIVE"], 7.0),
        ("TEXT_DIM", ["BG_WINDOW", "BG_PANEL", "BG_BAR", "BG_INPUT", "SURFACE",
                      "SURFACE_ALT", "TAB_ACTIVE"], 4.5),
        ("TEXT_DIM", ["SURFACE_INACTIVE"], 3.0),
        ("TEXT_FAINT", ["BG_WINDOW", "BG_PANEL", "BG_BAR", "SURFACE"], 3.0),
        ("ACCENT_LIGHT", ["BG_WINDOW", "BG_PANEL", "BG_BAR", "SURFACE", "SURFACE_ALT"], 4.5),
        ("ACCENT", ["BG_WINDOW", "BG_PANEL", "SURFACE"], 4.5),
    ]
    for tokname in ("DANGER", "SUCCESS", "WARNING", "ALERT", "INFO", "TEAL", "DANGER_LIGHT"):
        rules.append((tokname, ["BG_WINDOW", "BG_PANEL", "BG_BAR", "SURFACE"], 3.0))
    term = ["TERM_FG", "TERM_BLACK", "TERM_BLACK_BRIGHT", "TERM_GREEN_BRIGHT",
            "TERM_YELLOW_BRIGHT", "TERM_BLUE_BRIGHT", "TERM_TEAL_BRIGHT",
            "DANGER", "DANGER_LIGHT", "SUCCESS", "WARNING", "INFO", "ACCENT",
            "ACCENT_LIGHT", "TEAL"]
    for tokname in term:
        rules.append((tokname, ["BG_CANVAS"], 4.5 if tokname in ("TERM_FG", "TERM_BLACK") else 3.0))
    rules.append(("TERM_FG", ["HOVER"], 4.5))   # zaznaczony tekst w terminalu
    worst = []
    for fg, bgs, minimum in rules:
        for bg in bgs:
            c = contrast(T[fg], T[bg])
            if c < minimum:
                worst.append(f"{fg} na {bg}: {c:.2f} < {minimum}")
    check(f"[C1] kontrast trybu jasnego ({sum(len(b) for _, b, _ in rules)} par)",
          not worst, "; ".join(worst))
    c_send = min(contrast("#ffffff", T["ACCENT"]), contrast("#ffffff", T["ACCENT_DEEP"]))
    check("[C2] biała ikona „Wyślij” na gradiencie akcentu ≥ 4,5", c_send >= 4.5, f"{c_send:.2f}")

    # [D] sygnały: różnica jasności wobec tła paska (ta sama miara co w trybie ciemnym)
    for sig in ("TAB_ACTIVE", "SURFACE_INACTIVE"):
        d = abs(brightness(T[sig]) - brightness(T["BG_PANEL"]))
        check(f"[D] {sig} odcięty od BG_PANEL o ≥ 30/255", d >= 30, f"{d:.0f}")

    # [E] wybór trybu
    with tempfile.TemporaryDirectory() as home:
        check("[E1] brak config.json → ciemny", load(None, home)["mode"] == "dark")
        cfg = Path(home) / ".vibe-coding-assistant"
        cfg.mkdir(exist_ok=True)
        (cfg / "config.json").write_text(json.dumps({"appearance": "light"}))
        check("[E2] config.json appearance=light → jasny", load(None, home)["mode"] == "light")
        (cfg / "config.json").write_text(json.dumps({"appearance": "fioletowy"}))
        check("[E3] dziwna wartość → ciemny (fail-safe)", load(None, home)["mode"] == "dark")
        (cfg / "config.json").write_text("{ zepsuty")
        check("[E4] zepsuty config.json → ciemny (fail-safe)", load(None, home)["mode"] == "dark")
        (cfg / "config.json").write_text(json.dumps({"appearance": "light"}))
        check("[E5] CVA_APPEARANCE ma pierwszeństwo przed config.json",
              load("dark", home)["mode"] == "dark")

    # [F] motyw Claude Code
    sys.path.insert(0, str(ROOT / "src"))
    from core import claude_hooks as ch
    with tempfile.TemporaryDirectory() as home:
        h = Path(home)
        # Przesłanka zmieniona ŚWIADOMIE 2026-10-20 (przełączanie w locie):
        # dawniej tryb jasny → "light", ciemny → nic. Patrz claude_theme_for.
        check("[F1] tryb ciemny → dark-ansi", ch.claude_theme_for(False, h) == "dark-ansi")
        check("[F2] tryb jasny, user bez motywu → dark-ansi", ch.claude_theme_for(True, h) == "dark-ansi")
        (h / ".claude").mkdir()
        (h / ".claude" / "settings.json").write_text(json.dumps({"theme": "dark"}))
        check("[F3] tryb jasny, user ma dark → dark-ansi", ch.claude_theme_for(True, h) == "dark-ansi")
        (h / ".claude" / "settings.json").write_text(json.dumps({"theme": "light-daltonized"}))
        check("[F4] user wybrał odmianę dla daltonistów pasującą do trybu → zostawiamy",
              ch.claude_theme_for(True, h) is None)
        (h / ".claude" / "settings.json").write_text("{ zepsuty")
        (h / ".claude.json").write_text(json.dumps({"theme": "light-daltonized"}))
        check("[F5] stare miejsce ~/.claude.json też czytane",
              ch.claude_theme_for(True, h) is None)
        kat = h / "cfg"
        plik = ch.ensure_hooks(kat, "light")
        dane = json.loads(plik.read_text())
        check("[F6] plik --settings: motyw + hooki obok siebie",
              dane.get("theme") == "light" and set(dane.get("hooks", {})) == {
                  "SessionStart", "SessionEnd", "PostModelSwitch"})
        dane = json.loads(ch.ensure_hooks(kat, None).read_text())
        check("[F7] bez motywu: klucza 'theme' NIE ma (jak przed zmianą)", "theme" not in dane)
        check("[F8] ~/.claude/settings.json usera nietknięty",
              (h / ".claude" / "settings.json").read_text() == "{ zepsuty")

    # [G] [H] [I] — w osobnych procesach (tryb ustalany przy imporcie)
    for mode in ("dark", "light"):
        with tempfile.TemporaryDirectory() as home:
            r = run_py(mode, home, GHI_CODE)
            if r.returncode != 0:
                check(f"[GHI] {mode}: uruchomienie", False, r.stderr[-800:])
                continue
            for line in r.stdout.splitlines():
                ok, name, detail = json.loads(line)
                check(f"{name} ({mode})", ok, detail)

    # [J] osobna skórka każdego trybu
    with tempfile.TemporaryDirectory() as home:
        cfgdir = Path(home) / ".vibe-coding-assistant"
        cfgdir.mkdir()
        cfg = cfgdir / "config.json"
        dark_skin = dict(dark["skin"], text_color="#123456")
        cfg.write_text(json.dumps({"language": "pl-PL", "skin_version": 6,
                                   "skin_colors": dark_skin, "appearance": "light"}))
        r = run_py(None, home, J_CODE.replace("%NEW%", "#abcdef"))
        check("[J0] jasny: wczytanie/zapis bez błędu", r.returncode == 0, r.stderr[-800:])
        loaded = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
        saved = json.loads(cfg.read_text())
        check("[J1] jasny NIE bierze zapisanej ciemnej skórki",
              loaded.get("text_color") == light["skin"]["text_color"], str(loaded.get("text_color")))
        check("[J2] zapis w jasnym: ciemna skórka w pliku nietknięta",
              saved.get("skin_colors", {}).get("text_color") == "#123456"
              and saved.get("skin_version") == 6, str(saved.get("skin_colors", {}).get("text_color")))
        check("[J3] zapis w jasnym: własna skórka pod skin_colors_light",
              saved.get("skin_colors_light", {}).get("text_color") == "#abcdef"
              and saved.get("skin_version_light") == 6)
        check("[J4] wybrany wygląd zapisany", saved.get("appearance") == "light")
        saved["appearance"] = "dark"
        cfg.write_text(json.dumps(saved))
        r = run_py(None, home, J_CODE.replace("%NEW%", ""))
        loaded = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
        saved = json.loads(cfg.read_text())
        check("[J5] ciemny wczytuje SWOJĄ skórkę (#123456)",
              loaded.get("text_color") == "#123456", str(loaded.get("text_color")))
        check("[J6] zapis w ciemnym: jasna skórka w pliku nietknięta",
              saved.get("skin_colors_light", {}).get("text_color") == "#abcdef")
    with tempfile.TemporaryDirectory() as home:
        cfgdir = Path(home) / ".vibe-coding-assistant"
        cfgdir.mkdir()
        (cfgdir / "config.json").write_text(json.dumps({"language": "pl-PL"}))
        r = run_py(None, home, J_CODE.replace("%NEW%", ""))
        saved = json.loads((cfgdir / "config.json").read_text())
        check("[J7] stary config bez wyglądu → zapis 'dark', skórka pod starym kluczem",
              r.returncode == 0 and saved.get("appearance") == "dark"
              and "skin_colors" in saved and "skin_colors_light" not in saved, r.stderr[-400:])

    # [R] polecenie ponownego uruchomienia
    with tempfile.TemporaryDirectory() as home:
        app = Path(home) / "VCA.AppImage"
        app.write_text("x")
        r = run_py("dark", home, R_CODE.replace("%APP%", str(app)))
        if r.returncode != 0:
            check("[R] uruchomienie", False, r.stderr[-800:])
        else:
            for line in r.stdout.splitlines():
                ok, name, detail = json.loads(line)
                check(name, ok, detail)

    # [K] kontrola negatywna
    bad = contrast(td["ACCENT_LIGHT"], "#ffffff")
    check("[K] miara odrzuca jasny fiolet trybu ciemnego na bieli (< 4,5)", bad < 4.5, f"{bad:.2f}")

    print(f"\nWynik: {PASSED} OK / {FAILED} FAIL")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
