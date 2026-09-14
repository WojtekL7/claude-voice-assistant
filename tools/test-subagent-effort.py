#!/usr/bin/env python3
"""Bramka ETAPU 2: model podagentów + poziom wysiłku per model.

Uruchom:  python3 tools/test-subagent-effort.py

CO PILNUJE (dwie niezależne rzeczy, obie o pieniądzach):
  1. `CLAUDE_CODE_SUBAGENT_MODEL` — zmienna środowiskowa zakładki, dzięki
     której podagenci mogą chodzić na tańszym modelu niż rozmowa.
  2. `~/.claude/settings.json` → `modelSettings.<model>.effortLevel` — poziom
     wysiłku zapamiętywany OSOBNO DLA KAŻDEGO MODELU.

⛔ NAJWAŻNIEJSZA ASERCJA JEST W SEKCJI 3: zapis do pliku ustawień NIE MOŻE
skasować cudzych kluczy ani ruszyć pliku, którego nie potrafimy odczytać.
To nie jest nasz plik — mieszka w nim praca użytkownika i samego Claude Code.

Każdy test pozytywny ma parę negatywną: sprawdzamy nie tylko że coś działa,
ale też że NIE działa tam, gdzie nie powinno (inaczej zielone nic nie dowodzi).
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_passed = 0
_failed = 0


def check(name, condition, detail=""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"[OK]   {name}")
    else:
        _failed += 1
        print(f"[FAIL] {name}  {detail}")


def raises(blad, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except blad:
        return True
    except Exception:
        return False
    return False


# ============================ 1. zmienna dla podagentów ============================
import config as cfg  # noqa: E402

check("config ma nazwę zmiennej podagentów",
      cfg.SUBAGENT_MODEL_ENV == "CLAUDE_CODE_SUBAGENT_MODEL", cfg.SUBAGENT_MODEL_ENV)
check("wybrany model trafia do zmiennej",
      cfg.subagent_env("opus") == {"CLAUDE_CODE_SUBAGENT_MODEL": "opus"},
      cfg.subagent_env("opus"))
# KONTROLE ODWROTNE — brak wyboru NIE MOŻE ustawiać zmiennej, bo wtedy
# odbieralibyśmy Claude Code jego własną decyzję.
check("brak wyboru → pusto (Claude Code decyduje sam)", cfg.subagent_env("") == {})
check("„Domyślny” → pusto", cfg.subagent_env("default") == {})
check("None → pusto zamiast wyjątku", cfg.subagent_env(None) == {})
check("spacje same w sobie → pusto", cfg.subagent_env("   ") == {})

# ============ 2. środowisko powłoki — DOWÓD ZE SKUTKU, nie z kodu ============
from gui.web_terminal import build_shell_env  # noqa: E402

_env = build_shell_env({"CLAUDE_CODE_SUBAGENT_MODEL": "opus"})
check("zmienna jest w środowisku powłoki", _env.get("CLAUDE_CODE_SUBAGENT_MODEL") == "opus")
check("PATH przeżywa dokładki (bez niego `claude` się nie znajdzie)", bool(_env.get("PATH")))
check("TERM nadal ustawiony", _env.get("TERM") == "xterm-256color")
check("bez dokładek zmiennej NIE MA",
      "CLAUDE_CODE_SUBAGENT_MODEL" not in build_shell_env(None))
check("pusta wartość NIE ustawia zmiennej",
      "CLAUDE_CODE_SUBAGENT_MODEL" not in build_shell_env({"CLAUDE_CODE_SUBAGENT_MODEL": ""}))
check("dokładka wygrywa ze środowiskiem procesu apki",
      build_shell_env({"TERM": "wlasny"}).get("TERM") == "wlasny")

# Dowód KOŃCA DROGI: prawdziwa powłoka logowania musi tę zmienną zobaczyć.
# To jedyny sprawdzian, który obejmuje też profil powłoki (`-l` potrafi
# nadpisywać zmienne) — dlatego nie zastępujemy go porównaniem słowników.
try:
    import ptyprocess
    from core.platform_utils import default_shell

    def _echo_w_powloce(extra):
        import time
        p = ptyprocess.PtyProcess.spawn([default_shell(), "-l"], dimensions=(24, 80),
                                        env=build_shell_env(extra))
        p.write(b"echo ZNACZNIK=[$CLAUDE_CODE_SUBAGENT_MODEL]\n")
        out, koniec = b"", time.time() + 8
        while time.time() < koniec:
            try:
                out += p.read(4096)
            except Exception:
                break
            if b"ZNACZNIK=[" in out.split(b"echo ZNACZNIK")[-1]:
                break
        try:
            p.terminate(force=True)
        except Exception:
            pass
        for line in out.decode("utf-8", "replace").splitlines():
            if line.startswith("ZNACZNIK=["):
                return line.strip()
        return ""

    _wynik = _echo_w_powloce({"CLAUDE_CODE_SUBAGENT_MODEL": "opus"})
    check("PRAWDZIWA powłoka widzi zmienną", _wynik == "ZNACZNIK=[opus]", _wynik)
    _pusty = _echo_w_powloce(None)
    check("kontrola odwrotna: bez ustawienia powłoka ma pustkę",
          _pusty == "ZNACZNIK=[]", _pusty)
except Exception as _exc:
    check("PRAWDZIWA powłoka widzi zmienną", False, f"nie udało się uruchomić PTY: {_exc}")

# ==================== 3. plik ustawień Claude Code — CUDZY ====================
from core import claude_settings as cs  # noqa: E402

check("znane poziomy wysiłku", cs.EFFORT_LEVELS == ("low", "medium", "high"))
check("ścieżka wskazuje na plik Claude Code",
      cs.settings_path().name == "settings.json" and ".claude" in str(cs.settings_path()))

with tempfile.TemporaryDirectory() as tmp:
    plik = Path(tmp) / "settings.json"

    check("brak pliku → puste ustawienia (a nie wyjątek)", cs.read_settings(plik) == {})
    check("brak pliku → brak poziomu", cs.get_effort("claude-fable-5-1", plik) is None)

    # Plik użytkownika z JEGO ustawieniami — dokładnie taki kształt jak realny.
    cudze = {"permissions": {"allow": ["Bash(ls:*)"]}, "theme": "dark",
             "autoMode": True, "tui": {"fullscreen": True}}
    plik.write_text(json.dumps(cudze, indent=2), encoding="utf-8")

    check("zapis poziomu zwraca True (coś się zmieniło)",
          cs.set_effort("claude-fable-5-1", "medium", plik) is True)
    po = json.loads(plik.read_text(encoding="utf-8"))
    check("poziom zapisany tam, gdzie czyta go Claude Code",
          po["modelSettings"]["claude-fable-5-1"]["effortLevel"] == "medium", po.get("modelSettings"))
    # ⛔ ASERCJA NAJWAŻNIEJSZA W TYM PLIKU
    check("CUDZE ustawienia nietknięte co do znaku",
          all(po.get(k) == v for k, v in cudze.items()),
          {k: (v, po.get(k)) for k, v in cudze.items() if po.get(k) != v})
    # ⛔ OSŁONA: badany błąd (brak kopii) SPRAWIA, że pliku nie ma — odczyt bez
    # osłony wywala bramkę zamiast zgłosić [FAIL], a wyjście po odfiltrowaniu
    # wygląda wtedy jak komplet zielonych. Złapał to sabotaż T6, nie czytanie.
    _kopia = plik.parent / (plik.name + cs.BACKUP_SUFFIX)
    check("kopia zapasowa powstała przed pierwszą zmianą", _kopia.exists())
    try:
        _tresc_kopii = json.loads(_kopia.read_text(encoding="utf-8"))
    except Exception:
        _tresc_kopii = None
    check("kopia zapasowa niesie treść SPRZED zmiany", _tresc_kopii == cudze, _tresc_kopii)
    check("zapis nie zostawia pliku tymczasowego", not list(Path(tmp).glob("*.tmp-vca")))

    check("odczyt zwraca zapisany poziom", cs.get_effort("claude-fable-5-1", plik) == "medium")
    check("mapa wszystkich poziomów", cs.all_efforts(plik) == {"claude-fable-5-1": "medium"})
    check("ten sam poziom drugi raz → False (nie piszemy bez potrzeby)",
          cs.set_effort("claude-fable-5-1", "medium", plik) is False)

    # Drugi model NIE MOŻE wypchnąć pierwszego — to osobne wpisy.
    cs.set_effort("claude-opus-5", "high", plik)
    check("dwa modele żyją obok siebie",
          cs.all_efforts(plik) == {"claude-fable-5-1": "medium", "claude-opus-5": "high"},
          cs.all_efforts(plik))

    check("kasowanie poziomu zwraca True", cs.set_effort("claude-fable-5-1", None, plik) is True)
    check("skasowany wpis znika, drugi zostaje",
          cs.all_efforts(plik) == {"claude-opus-5": "high"}, cs.all_efforts(plik))
    check("kasowanie nieistniejącego → False", cs.set_effort("claude-fable-5-1", None, plik) is False)
    cs.set_effort("claude-opus-5", None, plik)
    check("po skasowaniu OSTATNIEGO wpisu znika cała sekcja",
          "modelSettings" not in json.loads(plik.read_text(encoding="utf-8")))
    check("a cudze ustawienia DALEJ są na miejscu",
          all(json.loads(plik.read_text(encoding="utf-8")).get(k) == v for k, v in cudze.items()))

    # KONTROLE NEGATYWNE — fail-CLOSED przy zapisie do cudzego pliku.
    zly = Path(tmp) / "zepsuty.json"
    zly.write_text("{to nie jest json", encoding="utf-8")
    check("uszkodzony plik → odczyt rzuca (nie udajemy, że jest pusty)",
          raises(cs.SettingsError, cs.read_settings, zly))
    check("uszkodzony plik → ZAPIS ODMAWIA",
          raises(cs.SettingsError, cs.set_effort, "claude-opus-5", "low", zly))
    check("uszkodzony plik NIE ZOSTAŁ nadpisany",
          zly.read_text(encoding="utf-8") == "{to nie jest json")
    check("uszkodzony plik → odczyt poziomu jest fail-open (okno ma się otworzyć)",
          cs.get_effort("claude-opus-5", zly) is None)

    lista = Path(tmp) / "lista.json"
    lista.write_text("[1, 2, 3]", encoding="utf-8")
    check("JSON, ale nie obiekt → odmowa", raises(cs.SettingsError, cs.read_settings, lista))

    check("nieznany poziom wysiłku → odmowa",
          raises(cs.SettingsError, cs.set_effort, "claude-opus-5", "turbo", plik))
    check("pusty identyfikator modelu → odmowa",
          raises(cs.SettingsError, cs.set_effort, "", "low", plik))

    # Nieznane pola W NASZYM wpisie też mają przeżyć — Claude Code może tam
    # trzymać rzeczy, o których nie wiemy.
    plik.write_text(json.dumps({"modelSettings": {
        "claude-opus-5": {"effortLevel": "low", "cosNaszegoNieZnamy": 7}}}, indent=2),
        encoding="utf-8")
    cs.set_effort("claude-opus-5", "high", plik)
    check("nieznane pole wewnątrz wpisu modelu przeżywa zmianę poziomu",
          json.loads(plik.read_text(encoding="utf-8"))["modelSettings"]["claude-opus-5"]
          .get("cosNaszegoNieZnamy") == 7)

# =================== 4. identyfikator modelu dla pliku ustawień ===================
import core.model_catalog as mc  # noqa: E402

_kat = mc.parse_catalog((ROOT / "tools" / "fixtures"
                         / "models-overview-2026-09-14.md").read_text(encoding="utf-8"))
cfg.apply_model_catalog(_kat)
check("fable → identyfikator z katalogu", cfg.model_api_id("fable") == "claude-fable-5-1",
      cfg.model_api_id("fable"))
check("opus → identyfikator z katalogu", cfg.model_api_id("opus") == "claude-opus-5")
check("haiku → PEŁNY identyfikator (nie skrócony alias)",
      cfg.model_api_id("haiku") == "claude-haiku-4-5-20251001", cfg.model_api_id("haiku"))
check("pozycja wpisana pełną nazwą zwraca samą siebie",
      cfg.model_api_id("claude-opus-4-8") == "claude-opus-4-8")
check("„Domyślny” nie ma identyfikatora (apka nie wie, co uruchomi)",
      cfg.model_api_id("default") == "")
check("nieznany klucz → zwracamy go bez zmian, nie zgadujemy",
      cfg.model_api_id("cos-nowego") == "cos-nowego")

# ======================== 5. wpięcie w interfejs (AST/treść) ========================
import ast  # noqa: E402

tb_txt = (ROOT / "src" / "gui" / "terminal_backend.py").read_text(encoding="utf-8")
check("fabryka terminala przyjmuje dokładki środowiska",
      "def create_terminal_backend(" in tb_txt and "extra_env" in tb_txt)
check("WebTerminal dostaje dokładki PRZED startem powłoki",
      "self._term.set_extra_env(extra_env)" in tb_txt)
check("QTermWidget dostaje KOMPLET środowiska, nie samą dokładkę",
      "pelne = dict(os.environ)" in tb_txt and "setEnvironment" in tb_txt)

at_txt = (ROOT / "src" / "gui" / "agent_tab.py").read_text(encoding="utf-8")
check("zakładka przekazuje model podagentów do fabryki",
      "extra_env=subagent_env(" in at_txt)
check("zakładka czyta ustawienie z konfiguracji agenta",
      "agent_config.get('subagent_model'" in at_txt)
check("zakładka ZAPISUJE ustawienie z powrotem (inaczej ginie przy edycji)",
      "'subagent_model': self.subagent_model," in at_txt)

dlg_txt = (ROOT / "src" / "gui" / "dialogs.py").read_text(encoding="utf-8")
check("okno agenta ma listę modelu podagentów", "self.subagent_combo" in dlg_txt)
check("wybór podagenta trafia do zapisywanych danych",
      "'subagent_model': self.subagent_combo.currentData() or ''," in dlg_txt)
check("lista podagentów ma wysokość wyrównaną z pozostałymi",
      "self.voice_combo, self.model_combo, self.subagent_combo" in dlg_txt)

mw_txt = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
mw_tree = ast.parse(mw_txt)
mw_cls = {n.name: n for n in mw_tree.body if isinstance(n, ast.ClassDef)}.get("MainWindow")
mw_methods = ({n.name for n in ast.walk(mw_cls) if isinstance(n, ast.FunctionDef)}
              if mw_cls else set())
check("MainWindow ma okno poziomu wysiłku", "_show_model_effort_dialog" in mw_methods)
check("pozycja menu podpięta do ISTNIEJĄCEJ metody",
      "effort_action.triggered.connect(self._show_model_effort_dialog)" in mw_txt)
check("okno odmawia zapisu przy nieczytelnym pliku (fail-closed)",
      "dlg_effort_unreadable" in mw_txt)
check("okno mówi, że ustawienie jest WSPÓLNE, nie per agent",
      "dlg_effort_note" in mw_txt)

for _klucz in ("dlg_agent_subagent_label", "dlg_agent_subagent_default",
               "dlg_agent_subagent_hint", "menu_model_effort", "dlg_effort_desc",
               "dlg_effort_low", "dlg_effort_medium", "dlg_effort_high",
               "dlg_effort_model_default", "dlg_effort_note",
               "dlg_effort_unreadable", "status_effort_saved"):
    check(f"napis '{_klucz}' w OBU językach",
          _klucz in cfg.UI_TRANSLATIONS["pl-PL"] and _klucz in cfg.UI_TRANSLATIONS["en-US"])
check("parytet słowników PL/EN",
      set(cfg.UI_TRANSLATIONS["pl-PL"]) == set(cfg.UI_TRANSLATIONS["en-US"]))

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
