#!/usr/bin/env python3
"""Bramka ETAPU 3: lekarz skilli (`/skill-doctor`) + wyłączanie z kontekstu.

Uruchom:  python3 tools/test-skill-doctor.py

Fixture = DWA PRAWDZIWE wyjścia `claude -p /skill-doctor` zdjęte 2026-09-14:
  * `skill-doctor-2026-09-14.txt`           — stan zastany (23 skille, 16 nieużytych),
  * `skill-doctor-overrides-2026-09-14.txt` — ten sam zestaw z ustawionymi
    `skillOverrides`, czyli z kosztem zbitym do zera.
Parser cudzego formatu pisany „z głowy" przechodzi na zielono i milczy na
produkcji — dlatego tu leżą dosłowne ładunki, a nie ich wyobrażenie.

⛔ ASERCJA, KTÓRA PILNUJE NAJDROŻSZEJ POMYŁKI TEJ SESJI (sekcja 5): okno MUSI
wyłączać skille przez `skillOverrides`, a NIE przez `permissions.deny`.
Zmierzone: `deny` blokuje uruchomienie, ale zostawia skill na liście z pełnym
kosztem (~150 tokenów na turę) — przycisk podpięty tam obiecywałby oszczędność,
której nie ma.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIX_STAN = ROOT / "tools" / "fixtures" / "skill-doctor-2026-09-14.txt"
FIX_OVER = ROOT / "tools" / "fixtures" / "skill-doctor-overrides-2026-09-14.txt"

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


from core import skill_doctor as sd  # noqa: E402

# ===================== 1. parsowanie PRAWDZIWEGO raportu =====================
# ⛔ Osłona: badany błąd sprawia, że parser rzuca — bez niej bramka URYWA SIĘ
# zamiast zgłosić [FAIL], a wyjście wygląda jak komplet zielonych (zaliczone
# dwa razy w tej sesji, sekcje 1b katalogu modeli i kopii zapasowej).
_powod = ""
try:
    raport = sd.parse_report(FIX_STAN.read_text(encoding="utf-8"))
    _ok = True
except Exception as exc:
    raport, _ok, _powod = {"skills": []}, False, f"{type(exc).__name__}: {exc}"
check("prawdziwy raport w ogóle się parsuje", _ok, _powod)

_skille = {s["name"]: s for s in raport.get("skills", [])}
check("wszystkie 23 skille odczytane", len(raport.get("skills", [])) == 23,
      len(raport.get("skills", [])))
check("liczba nigdy nieużytych wzięta z podsumowania", raport.get("never_used") == 16,
      raport.get("never_used"))
check("koszt kontekstu razem = 2850 tokenów/turę", raport.get("total_context") == 2850,
      raport.get("total_context"))
check("marnowane na nieużywanych = 2120 tokenów/turę", sd.wasted_context(raport) == 2120,
      sd.wasted_context(raport))

check("skill nieużywany: koszt i zero użyć",
      _skille.get("pptx", {}).get("context") == 230
      and _skille.get("pptx", {}).get("uses") == 0
      and _skille.get("pptx", {}).get("last_used") == "never", _skille.get("pptx"))
check("skill używany: liczba użyć i data",
      _skille.get("pdf", {}).get("uses") == 7
      and _skille.get("pdf", {}).get("last_used_days") == 7, _skille.get("pdf"))
check("skill z pojedynczym użyciem sprzed miesięcy",
      _skille.get("writing-plans", {}).get("uses") == 1
      and _skille.get("writing-plans", {}).get("last_used_days") == 60,
      _skille.get("writing-plans"))
check("kreska w koszcie = brak kosztu (None, nie zero-udające-liczbę)",
      _skille.get("changelog", {}).get("context") is None, _skille.get("changelog"))
check("źródło skilla odczytane",
      _skille.get("pdf", {}).get("source") == "userSettings", _skille.get("pdf"))
# KONTROLA ODWROTNA: nagłówek tabeli ma te same odstępy co wiersze — gdyby
# wpadł do wyniku, mielibyśmy skilla o nazwie „skill" i zawyżony koszt.
check("nagłówek tabeli NIE jest brany za skilla", "skill" not in _skille, sorted(_skille)[:3])

# ============ 1b. ten sam zestaw PO wyłączeniu — dowód, że to działa ============
_powod2 = ""
try:
    raport2 = sd.parse_report(FIX_OVER.read_text(encoding="utf-8"))
    _ok2 = True
except Exception as exc:
    raport2, _ok2, _powod2 = {"skills": []}, False, f"{type(exc).__name__}: {exc}"
check("raport z ustawionymi skillOverrides się parsuje", _ok2, _powod2)
_s2 = {s["name"]: s for s in raport2.get("skills", [])}
check("„user-invocable-only” zbija koszt do zera",
      _s2.get("pdf", {}).get("context") is None, _s2.get("pdf"))
check("„off” zbija koszt do zera", _s2.get("pptx", {}).get("context") is None, _s2.get("pptx"))
check("„name-only” tylko ZMNIEJSZA koszt (< 20, było ~260)",
      _s2.get("docx", {}).get("context") == 20, _s2.get("docx"))
check("skill nietknięty zachowuje pełny koszt (kontrola)",
      _s2.get("qt-qml-docs", {}).get("context") == 230, _s2.get("qt-qml-docs"))
check("wyłączenie realnie obniża sumę", raport2.get("total_context", 0) < 2850,
      raport2.get("total_context"))

# ===================== 2. liczby i kolejność do przeglądu =====================
check("'~150' → 150", sd._parse_context("~150") == 150)
check("'< 20' → 20", sd._parse_context("< 20") == 20)
check("'-' → None", sd._parse_context("-") is None)
check("pusty tekst → None", sd._parse_context("") is None)

_kolejnosc = sd.sort_for_review(raport.get("skills", []))
check("nieużywane idą PRZED używanymi",
      all(s["uses"] == 0 for s in _kolejnosc[:16]), [s["name"] for s in _kolejnosc[:3]])
check("wśród nieużywanych najdroższy jest pierwszy",
      _kolejnosc[0]["context"] == 230, _kolejnosc[0])
check("sortowanie nie gubi ani nie dubluje skilli",
      len(_kolejnosc) == len(raport.get("skills", []))
      and len({s["name"] for s in _kolejnosc}) == len(_kolejnosc))
check("pusta lista nie wywraca sortowania", sd.sort_for_review([]) == [])

# KONTROLE NEGATYWNE parsera — „udany" odczyt pustki byłby gorszy niż błąd.
check("pusty tekst → błąd", raises(sd.SkillDoctorError, sd.parse_report, ""))
check("tekst bez tabeli → błąd",
      raises(sd.SkillDoctorError, sd.parse_report, "Skills loaded this session\n\nnic tu nie ma\n"))
check("sam nagłówek bez wierszy → błąd", raises(
    sd.SkillDoctorError, sd.parse_report,
    "  skill      source    context  7d tokens   uses  last used\n"))

# ============ 3. uruchomienie cudzego programu — pułapki z pamięci ============
import inspect  # noqa: E402

_zrodlo = inspect.getsource(sd.run_report)
check("WEJŚCIE STANDARDOWE ZAMKNIĘTE (inaczej `claude` wisi w nieskończoność)",
      "stdin=subprocess.DEVNULL" in _zrodlo)
check("zdejmujemy CLAUDECODE (podproces zachowuje się inaczej niż u człowieka)",
      "CLAUDECODE" in _zrodlo)
check("jest limit czasu", "timeout=timeout" in _zrodlo)
check("puste wyjście traktowane jak błąd, nie jak brak skilli",
      "raport jest pusty" in _zrodlo)
check("nieistniejące polecenie → SkillDoctorError, a nie wysypka apki",
      raises(sd.SkillDoctorError, sd.run_report, "nie-ma-takiego-polecenia-vca", None, 10))

check("domyślny stan wyłączenia NIC NIE ODBIERA użytkownikowi",
      sd.DEFAULT_OFF_STATE == "user-invocable-only", sd.DEFAULT_OFF_STATE)
check("znane stany widoczności", set(sd.OVERRIDE_STATES) ==
      {"on", "name-only", "user-invocable-only", "off"})

# ================= 4. zapis skillOverrides do CUDZEGO pliku =================
from core import claude_settings as cs  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    plik = Path(tmp) / "settings.json"
    cudze = {"permissions": {"allow": ["Bash(ls:*)"]}, "theme": "dark", "autoMode": True}
    plik.write_text(json.dumps(cudze, indent=2), encoding="utf-8")

    check("brak wpisów → pusta mapa", cs.get_skill_overrides(plik) == {})
    check("zapis stanu zwraca True",
          cs.set_skill_override("pdf", "user-invocable-only", plik) is True)
    po = json.loads(plik.read_text(encoding="utf-8"))
    check("stan zapisany tam, gdzie czyta go Claude Code",
          po.get("skillOverrides", {}).get("pdf") == "user-invocable-only",
          po.get("skillOverrides"))
    check("CUDZE ustawienia nietknięte co do znaku",
          all(po.get(k) == v for k, v in cudze.items()),
          {k: (v, po.get(k)) for k, v in cudze.items() if po.get(k) != v})
    check("ten sam stan drugi raz → False",
          cs.set_skill_override("pdf", "user-invocable-only", plik) is False)

    cs.set_skill_override("pptx", "off", plik)
    check("dwa skille żyją obok siebie",
          cs.get_skill_overrides(plik) == {"pdf": "user-invocable-only", "pptx": "off"},
          cs.get_skill_overrides(plik))
    check("włączenie z powrotem (None) kasuje wpis",
          cs.set_skill_override("pdf", None, plik) is True
          and "pdf" not in cs.get_skill_overrides(plik))
    check("stan 'on' też kasuje wpis (to stan domyślny, nie wpisujemy go jawnie)",
          cs.set_skill_override("pptx", "on", plik) is True
          and cs.get_skill_overrides(plik) == {})
    check("pusta sekcja znika z pliku",
          "skillOverrides" not in json.loads(plik.read_text(encoding="utf-8")))
    check("a cudze ustawienia DALEJ są na miejscu",
          all(json.loads(plik.read_text(encoding="utf-8")).get(k) == v
              for k, v in cudze.items()))

    check("nieznany stan → odmowa",
          raises(cs.SettingsError, cs.set_skill_override, "pdf", "byle-co", plik))
    check("pusta nazwa skilla → odmowa",
          raises(cs.SettingsError, cs.set_skill_override, "", "off", plik))

    zly = Path(tmp) / "zepsuty.json"
    zly.write_text("{to nie jest json", encoding="utf-8")
    check("uszkodzony plik → ZAPIS ODMAWIA",
          raises(cs.SettingsError, cs.set_skill_override, "pdf", "off", zly))
    check("uszkodzony plik NIE ZOSTAŁ nadpisany",
          zly.read_text(encoding="utf-8") == "{to nie jest json")
    check("uszkodzony plik → odczyt fail-open (okno ma się otworzyć)",
          cs.get_skill_overrides(zly) == {})

# ===================== 5. wpięcie w okno główne (AST/treść) =====================
import ast  # noqa: E402

mw_txt = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
mw_tree = ast.parse(mw_txt)
mw_cls = {n.name: n for n in mw_tree.body if isinstance(n, ast.ClassDef)}.get("MainWindow")
mw_methods = ({n.name for n in ast.walk(mw_cls) if isinstance(n, ast.FunctionDef)}
              if mw_cls else set())
check("MainWindow ma okno lekarza skilli", "_show_skill_doctor_dialog" in mw_methods)
check("pozycja menu podpięta do ISTNIEJĄCEJ metody",
      "skill_doctor_action.triggered.connect(self._show_skill_doctor_dialog)" in mw_txt)

_okno, _okno_kod = "", ""
for n in ast.walk(mw_cls) if mw_cls else []:
    if isinstance(n, ast.FunctionDef) and n.name == "_show_skill_doctor_dialog":
        _okno = ast.get_source_segment(mw_txt, n) or ""
        # ⚠️ Do pytania „czy kod tego UŻYWA" bierzemy CIAŁO BEZ OPISU. Pierwsza
        # wersja tej asercji pytała o samo SŁOWO i zapaliła się na komentarzu
        # tłumaczącym, czemu tej drogi NIE używamy — czyli tam, gdzie wzmianka
        # jest POŻĄDANA. Kontrola ma pytać o wywołanie, nie o wystąpienie nazwy.
        _ciało = [w for w in n.body
                  if not (isinstance(w, ast.Expr) and isinstance(w.value, ast.Constant)
                          and isinstance(w.value.value, str))]
        _okno_kod = "\n".join(ast.unparse(w) for w in _ciało)
        break
check("okno w ogóle ma treść do zbadania", bool(_okno) and bool(_okno_kod))
# ⛔ NAJWAŻNIEJSZA ASERCJA PLIKU — patrz nagłówek.
check("okno wyłącza przez skillOverrides",
      "set_skill_override" in _okno_kod and "get_skill_overrides" in _okno_kod)
check("okno NIE używa permissions.deny (ta droga NIE zdejmuje kosztu)",
      "AgentSkillsSettings" not in _okno_kod and "deny" not in _okno_kod,
      [w for w in ("AgentSkillsSettings", "deny") if w in _okno_kod])
check("powód tej decyzji ZOSTAJE zapisany w opisie okna (żeby nikt nie „naprawił”)",
      "permissions.deny" in _okno)
check("okno proponuje stan, który nic nie odbiera",
      "sd.DEFAULT_OFF_STATE" in _okno)
check("okno pokazuje stan FAKTYCZNY (zaznacza już wyłączone)",
      "pole.setChecked(" in _okno)
check("okno mówi, ile to oszczędza", "wasted_context" in _okno)
check("okno sortuje wg kosztu i użycia", "sort_for_review" in _okno)
check("błąd raportu nie wywraca apki, tylko mówi userowi",
      "dlg_skills_failed" in _okno)

import config as cfg  # noqa: E402

for _k in ("menu_skill_doctor", "dlg_skills_running", "dlg_skills_failed",
           "dlg_skills_summary", "dlg_skills_col_off", "dlg_skills_col_name",
           "dlg_skills_col_context", "dlg_skills_col_uses", "dlg_skills_col_last",
           "dlg_skills_never", "dlg_skills_select_unused", "dlg_skills_note",
           "status_skills_saved"):
    check(f"napis '{_k}' w OBU językach",
          _k in cfg.UI_TRANSLATIONS["pl-PL"] and _k in cfg.UI_TRANSLATIONS["en-US"])
check("parytet słowników PL/EN",
      set(cfg.UI_TRANSLATIONS["pl-PL"]) == set(cfg.UI_TRANSLATIONS["en-US"]))
check("opis mówi WPROST, że skill nie znika (bo to decyduje o zgodzie usera)",
      "/nazwa" in cfg.UI_TRANSLATIONS["pl-PL"]["dlg_skills_note"])

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
