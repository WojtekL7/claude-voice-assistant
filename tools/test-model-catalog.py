#!/usr/bin/env python3
"""Bramka dla katalogu modeli (`src/core/model_catalog.py`).

Uruchom:  python3 tools/test-model-catalog.py

Fixture = PRAWDZIWA strona Anthropic zdjęta 2026-07-26
(`tools/fixtures/models-overview-2026-07-26.md`). Parser cudzego formatu
testowany na danych „napisanych z głowy" przechodzi na zielono i milczy
na produkcji — dlatego tu leży dosłowny ładunek.

Każdy test pozytywny ma parę negatywną: sprawdzamy nie tylko że coś działa,
ale też że NIE działa tam, gdzie nie powinno (inaczej zielone nic nie dowodzi).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core import model_catalog as mc  # noqa: E402

FIXTURE = ROOT / "tools" / "fixtures" / "models-overview-2026-07-26.md"

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


def raises_catalog_error(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except mc.CatalogError:
        return True
    except Exception:
        return False
    return False


# ------------------------------------------------ 1. parsowanie prawdziwej strony
md = FIXTURE.read_text(encoding="utf-8")
catalog = mc.parse_catalog(md)

check("parser zwraca 4 znane rodziny", set(catalog) >= set(mc.KNOWN_FAMILIES),
      f"dostałem: {sorted(catalog)}")
check("opus = Opus 5 (a NIE 4.8 z tabeli starszych modeli)",
      catalog["opus"]["name"] == "Opus 5", catalog["opus"])
check("sonnet = Sonnet 5", catalog["sonnet"]["name"] == "Sonnet 5", catalog["sonnet"])
check("fable = Fable 5", catalog["fable"]["name"] == "Fable 5", catalog["fable"])
check("haiku = Haiku 4.5", catalog["haiku"]["name"] == "Haiku 4.5", catalog["haiku"])

check("okno kontekstu Opus 5 = 1 mln", catalog["opus"]["context_window"] == 1_000_000)
check("okno kontekstu Sonnet 5 = 1 mln (apka miała 200 tys.!)",
      catalog["sonnet"]["context_window"] == 1_000_000)
check("okno kontekstu Haiku = 200 tys.", catalog["haiku"]["context_window"] == 200_000)
check("max wyjścia Opus 5 = 128 tys.", catalog["opus"].get("max_output") == 128_000)
check("identyfikator API Opus 5", catalog["opus"]["api_id"] == "claude-opus-5",
      catalog["opus"])
check("z komórek zdjęte znaczniki Tooltip/HTML",
      all("<" not in e.get("name", "") for e in catalog.values()))
check("opis modelu jest tekstem, nie linkiem markdown",
      "](" not in catalog["opus"].get("description", ""))

# KONTROLA NEGATYWNA parsera: strona bez tabeli / uszkodzona MUSI wypaść błędem,
# inaczej „udany" parse na śmieciach nadpisałby dobre dane wbudowane.
check("pusta strona → błąd", raises_catalog_error(mc.parse_catalog, ""))
check("strona bez tabeli → błąd",
      raises_catalog_error(mc.parse_catalog, "# Models\n\nsome prose\n"))
check("tabela bez wiersza aliasów → błąd", raises_catalog_error(
    mc.parse_catalog, "| A | B |\n| --- | --- |\n| **Context window** | 1M tokens |\n"))
check("tylko JEDEN model z oknem kontekstu → błąd (bramka przytomności)",
      raises_catalog_error(mc.parse_catalog,
                           "| Feature | Claude Opus 5 |\n| --- | --- |\n"
                           "| **Claude API alias** | claude-opus-5 |\n"
                           "| **Context window** | 1M tokens |\n"))

# ------------------------------------------------------ 2. liczby z tekstu
check("'1M tokens' → 1000000", mc._parse_tokens("1M tokens") == 1_000_000)
check("'200k tokens' → 200000", mc._parse_tokens("200k tokens") == 200_000)
check("'64k tokens' → 64000", mc._parse_tokens("64k tokens") == 64_000)
check("tekst bez liczby → None", mc._parse_tokens("brak danych") is None)
check("liczba bez słowa 'tokens' → None (nie zgadujemy)",
      mc._parse_tokens("1M") is None)

# --------------------------------------------------- 3. scalanie z wbudowanymi
BUILTIN_NAMES = {"default": "Domyślny", "opus": "STARE", "sonnet": "STARE", "haiku": "STARE"}
BUILTIN_LIMITS = {"default": 1_000_000, "opus": 1, "sonnet": 1, "haiku": 1}

names, limits = mc.merge_into(BUILTIN_NAMES, BUILTIN_LIMITS, catalog)
check("scalanie podmienia nazwę znanej rodziny", names["opus"] == "Opus 5", names)
check("scalanie podmienia okno kontekstu", limits["sonnet"] == 1_000_000, limits)
check("scalanie NIE rusza pozycji 'default'", names["default"] == "Domyślny")
check("scalanie NIE dodaje rodziny, której apka nie ma (fable poza listą)",
      "fable" not in names,
      "katalog nie może dokładać aliasu, którego CLI może nie przyjąć")

# KONTROLA NEGATYWNA scalania: śmieci w katalogu nie mogą zepsuć wartości.
brudny = {"opus": {"name": "   ", "context_window": 0},
          "neo": {"name": "Neo 1", "context_window": 5_000_000}}
n2, l2 = mc.merge_into(BUILTIN_NAMES, BUILTIN_LIMITS, brudny)
check("pusta nazwa w katalogu → zostaje wbudowana", n2["opus"] == "STARE", n2)
check("zerowe okno w katalogu → zostaje wbudowane", l2["opus"] == 1, l2)
check("nieznana rodzina 'neo' nie wchodzi do listy", "neo" not in n2 and "neo" not in l2)
check("pusty katalog → wartości wbudowane bez zmian",
      mc.merge_into(BUILTIN_NAMES, BUILTIN_LIMITS, {}) == (BUILTIN_NAMES, BUILTIN_LIMITS))

# --------------------------------------------------------- 4. wykrywanie zmian
poprzednie = {"opus": {"name": "Opus 4.8"}, "sonnet": {"name": "Sonnet 5"}}
zmiany = mc.diff_against(poprzednie, catalog)
check("zmiana nazwy wykryta (Opus 4.8 → Opus 5)",
      any(z["family"] == "opus" and z["to"] == "Opus 5" for z in zmiany["renamed"]),
      zmiany)
check("nazwa bez zmian nie jest zgłaszana",
      all(z["family"] != "sonnet" for z in zmiany["renamed"]), zmiany)
nowa = dict(catalog)
nowa["neo"] = {"name": "Neo 1", "context_window": 2_000_000}
check("nowa RODZINA zgłoszona osobno (do decyzji człowieka, nie auto-dodania)",
      [n["family"] for n in mc.diff_against(poprzednie, nowa)["new_families"]] == ["neo"])

# ------------------------------------------------------- 5. plik podręczny
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    cache = Path(tmp) / "models-cache.json"
    check("brak pliku → uznany za nieświeży", mc.is_stale(cache) is True)
    check("brak pliku → brak modeli", mc.cached_models(cache) == {})

    mc._save_cache(cache, catalog, mc.CATALOG_URL)
    check("po zapisie plik istnieje", cache.exists())
    check("odczyt zwraca te same modele", mc.cached_models(cache)["opus"]["name"] == "Opus 5")
    check("świeżo zapisany plik nie jest nieświeży", mc.is_stale(cache) is False)
    check("plik z TTL=0 jest nieświeży", mc.is_stale(cache, ttl=0) is True)
    check("zapis nie zostawia pliku tymczasowego",
          not list(Path(tmp).glob("*.tmp")))

    cache.write_text("{to nie jest json", encoding="utf-8")
    check("uszkodzony plik → None zamiast wyjątku", mc.load_cached(cache) is None)
    check("uszkodzony plik → puste modele (fail-open)", mc.cached_models(cache) == {})

    cache.write_text('{"models": {}}', encoding="utf-8")
    check("plik z pustą listą modeli → traktowany jak brak", mc.load_cached(cache) is None)

# ------------------------------------------- 6. fail-open przy awarii sieci
with tempfile.TemporaryDirectory() as tmp:
    cache = Path(tmp) / "models-cache.json"
    mc._save_cache(cache, catalog, mc.CATALOG_URL)
    before = cache.read_text(encoding="utf-8")
    err = raises_catalog_error(mc.refresh, cache,
                               "http://127.0.0.1:9/nie-ma-takiego-serwera", 2)
    check("nieosiągalny adres → CatalogError (a nie wysypka apki)", err)
    check("nieudane odświeżenie NIE psuje poprzedniego pliku",
          cache.read_text(encoding="utf-8") == before)

# ------------------------------------------------- 7. wpięcie w konfigurację
import config as cfg  # noqa: E402

check("config zna ścieżkę pliku podręcznego", hasattr(cfg, "MODEL_CATALOG_CACHE"))
check("config ma funkcję nakładającą katalog", callable(getattr(cfg, "apply_model_catalog", None)))
check("na liście jest przypięty starszy Opus", "claude-opus-4-8" in cfg.CLAUDE_MODELS)
check("Sonnet ma okno 1 mln (nie 200 tys.)",
      cfg.CLAUDE_MODEL_CONTEXT_LIMITS["sonnet"] == 1_000_000)
check("etykieta domyślnego modelu nie niesie numeru wersji",
      not any(ch.isdigit() for ch in cfg.model_label("default")),
      cfg.model_label("default"))

_stary = cfg.CLAUDE_MODELS
cfg.apply_model_catalog({"opus": {"name": "Opus 9", "context_window": 3_000_000}})
check("nałożenie katalogu MUTUJE słownik w miejscu (inne moduły mają referencję)",
      cfg.CLAUDE_MODELS is _stary)
check("nałożenie zmienia nazwę i okno", cfg.CLAUDE_MODELS["opus"] == "Opus 9"
      and cfg.CLAUDE_MODEL_CONTEXT_LIMITS["opus"] == 3_000_000)
check("etykieta łączy nazwę z katalogu i opis z tłumaczeń",
      cfg.model_label("opus") == "Opus 9 (najbardziej zdolny)", cfg.model_label("opus"))
cfg.apply_model_catalog({"opus": {"name": "Opus 5", "context_window": 1_000_000}})

# --------------------------------------------- 8. wpięcie w okno główne (AST)
# Świadomie NIE budujemy MainWindow — terminal w trybie bezokienkowym potrafi
# wywalić proces. Sprawdzamy strukturę pliku, co wystarcza, by wyłapać literówkę
# w nazwie metody podpiętej do menu (typowy cichy błąd: pozycja menu nic nie robi).
import ast  # noqa: E402

tree = ast.parse((ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8"))
classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
check("jest klasa robocza ModelCatalogChecker", "ModelCatalogChecker" in classes)

mw = classes.get("MainWindow")
methods = {n.name for n in ast.walk(mw) if isinstance(n, ast.FunctionDef)} if mw else set()
for name in ("_check_models_manual", "_maybe_auto_check_models",
             "_on_models_refreshed", "_on_models_check_failed"):
    check(f"MainWindow ma metodę {name}", name in methods)

src_txt = (ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
check("pozycja menu podpięta do istniejącej metody",
      "check_models_action.triggered.connect(self._check_models_manual)" in src_txt)
check("sygnały katalogu podpięte", "self.model_catalog_checker.refreshed.connect" in src_txt
      and "self.model_catalog_checker.failed.connect" in src_txt)
check("odświeżanie paska statusu woła ISTNIEJĄCY widżet",
      "mcp_status_widget" in src_txt and "force_refresh()" in src_txt)
check("import threading jest na poziomie modułu (wątek tła)",
      "\nimport threading\n" in src_txt)

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
