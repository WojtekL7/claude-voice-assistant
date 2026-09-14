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
# Druga kopia strony — układ z odwrotnymi apostrofami przy identyfikatorach.
# Obie są testowane: stara pilnuje zgodności wstecz, nowa dzisiejszego zapisu.
FIXTURE_2026_09 = ROOT / "tools" / "fixtures" / "models-overview-2026-09-14.md"

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

# ------------------------- 1b. strona w układzie z 2026-09-14 (identyfikatory
# w odwrotnych apostrofach) — TO JEST FIXTURE, KTÓREGO BRAK KOSZTOWAŁ 27 DNI.
#
# ⛔ Bramka pytająca WYŁĄCZNIE starą kopię strony jest ślepa na to, co realnie
# się zepsuło: Anthropic zaczął zapisywać `` `claude-fable-5-1` ``, parser
# przestał rozpoznawać rodzinę, fail-open przykrył to po cichu — a ta bramka
# świeciła 61/61 nad produkcją, która od miesiąca nie widziała nowego modelu.
# Dlatego fixture są DWA i oba muszą przechodzić: stary chroni przed regresją,
# nowy dowodzi, że nadążamy za dzisiejszym zapisem.
md_new = FIXTURE_2026_09.read_text(encoding="utf-8")
# ⛔ OSLONA OBOWIAZKOWA. Badany blad SPRAWIA, ze `parse_catalog` rzuca wyjatkiem
# — czyli dokladnie tu bramka bez `try` URYWA SIE zamiast zglosic [FAIL], a
# wyjscie po odfiltrowaniu wyglada jak komplet zielonych. Zlapal to sabotaz S1
# (7. wystapienie tej rodziny bledu w projekcie), nie czytanie kodu.
_powod_nowy = ""
try:
    cat_new = mc.parse_catalog(md_new)
    _nowy_ok = True
except Exception as _exc:
    # ⚠️ Powód zapisujemy TERAZ, do zwykłej zmiennej: nazwa z `except ... as`
    # znika po wyjściu z bloku, a oba argumenty `check()` liczą się ZAWSZE —
    # odwołanie do niej przy zdrowym kodzie wywaliłoby bramkę (zaliczone).
    cat_new, _nowy_ok = {}, False
    _powod_nowy = f"{type(_exc).__name__}: {_exc}"
check("[nowy układ] dzisiejsza strona Anthropic W OGÓLE się parsuje",
      _nowy_ok, _powod_nowy)

_fable = cat_new.get("fable", {})
_opus = cat_new.get("opus", {})
_haiku = cat_new.get("haiku", {})

check("[nowy układ] parser zwraca 4 znane rodziny",
      set(cat_new) >= set(mc.KNOWN_FAMILIES), f"dostałem: {sorted(cat_new)}")
check("[nowy układ] fable = Fable 5.1 (apka pokazywała 'Fable 5')",
      _fable.get("name") == "Fable 5.1", _fable)
check("[nowy układ] identyfikator w odwrotnych apostrofach rozpoznany",
      _fable.get("api_id") == "claude-fable-5-1", _fable)
check("[nowy układ] w identyfikatorze NIE ZOSTAŁ odwrotny apostrof",
      "`" not in _fable.get("api_id", "") and "`" not in _opus.get("api_id", ""))
check("[nowy układ] okno kontekstu Fable 5.1 = 1 mln",
      _fable.get("context_window") == 1_000_000, _fable)

# Ceny — powód, dla którego w ogóle je czytamy: wybór modelu to wybór rachunku.
check("[nowy układ] cena Fable 5.1 = 10 $ / 50 $ za mln tokenów",
      _fable.get("price_input") == 10.0 and _fable.get("price_output") == 50.0, _fable)
check("[nowy układ] cena Opus 5 = 5 $ / 25 $",
      _opus.get("price_input") == 5.0 and _opus.get("price_output") == 25.0, _opus)
check("[nowy układ] domyślny wysiłek Fable 5.1 = high",
      _fable.get("default_effort") == "high", _fable)
check("[nowy układ] 'Not supported' NIE jest brane za poziom wysiłku",
      "default_effort" not in _haiku, _haiku)

# Kontrola odwrotna: STARA strona nie ma wiersza z cenami, więc pól ceny NIE
# MOŻE być — inaczej braliby się znikąd (czyli parser by je zmyślał).
check("[stary układ] brak wiersza cen → brak pól ceny",
      "price_input" not in catalog["opus"], catalog["opus"])

check("odwrotny apostrof to OZDOBNIK, nie treść",
      mc._strip_cell("`claude-opus-5`") == "claude-opus-5")
check("cena z wiersza 'Pricing'",
      mc._parse_prices("$10 / input MTok, $50 / output MTok")
      == {"input": 10.0, "output": 50.0})
check("tekst bez ceny → pusty słownik (nie zgadujemy)",
      mc._parse_prices("Not available") == {})

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
    modele_przed = mc.cached_models(cache)
    err = raises_catalog_error(mc.refresh, cache,
                               "http://127.0.0.1:9/nie-ma-takiego-serwera", 2)
    check("nieosiągalny adres → CatalogError (a nie wysypka apki)", err)
    # ⚠️ PRZECELOWANE 2026-09-14. Ta asercja porównywała plik BAJT W BAJT, a od
    # tej daty nieudana próba DOPISUJE do niego ślad (`record_failure`) — czyli
    # równość bajtów przestała opisywać to, czego test pilnował. Pilnował: że
    # nieudane odświeżenie NIE ZABIERA modeli (fail-open). To zostaje w mocy.
    check("nieudane odświeżenie NIE psuje zapisanych modeli (fail-open)",
          mc.cached_models(cache) == modele_przed)
    stan = mc.catalog_status(cache)
    check("nieudana próba zostawia ŚLAD (inaczej cisza trwa w nieskończoność)",
          stan["consecutive_failures"] == 1 and bool(stan["last_error"]))
    check("ślad po awarii niesie wiek danych", isinstance(stan["age_days"], float))
    # Kontrola odwrotna: UDANE odświeżenie musi ten ślad skasować, inaczej
    # apka straszyłaby starymi danymi po tym, jak problem minął.
    mc._save_cache(cache, catalog, mc.CATALOG_URL)
    check("udane odświeżenie kasuje ślad porażki",
          mc.catalog_status(cache)["consecutive_failures"] == 0)

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

# ---------------------------------- 7b. ostrzeżenie o koszcie przy wyborze modelu
# Wybór modelu jest wyborem RACHUNKU: Fable 5.1 kosztuje 2× tyle co Opus 5,
# a przez brak tej informacji dwaj agenci chodzili na nim bez niczyjej decyzji.
cfg.apply_model_catalog(cat_new)   # świeży katalog z cenami (fixture 2026-09-14)

check("cena wjeżdża z katalogu do konfiguracji",
      cfg.CLAUDE_MODEL_PRICES["fable"] == {"input": 10.0, "output": 50.0},
      cfg.CLAUDE_MODEL_PRICES.get("fable"))
check("Fable 5.1 ostrzega, że jest 2× droższy od Opusa",
      "2×" in cfg.model_cost_hint("fable") and "Opus 5" in cfg.model_cost_hint("fable"),
      cfg.model_cost_hint("fable"))
check("ostrzeżenie o droższym modelu niesie znak uwagi",
      cfg.model_cost_hint("fable").startswith("⚠️"), cfg.model_cost_hint("fable"))
check("tańszy model mówi 'tańszy', nie 'droższy'",
      "tańszy" in cfg.model_cost_hint("sonnet"), cfg.model_cost_hint("sonnet"))
# KONTROLE ODWROTNE — bez nich „napis jest" nie znaczy „napis ma sens".
check("model odniesienia nie porównuje się sam ze sobą", cfg.model_cost_hint("opus") == "")
check('model DOMYSLNY nie ma ceny (apka nie wie z góry, co uruchomi)',
      cfg.model_cost_hint("default") == "")
check("model bez znanej ceny → pusto, nie zgadujemy",
      cfg.model_cost_hint("claude-opus-4-8") == "")
check("nieznany klucz → pusto zamiast wyjątku", cfg.model_cost_hint("nie-ma-takiego") == "")

# Proporcje liczone z OBU stawek: gdy skalują się różnie, jeden mnożnik byłby
# zmyśleniem → wtedy pokazujemy surowe stawki.
cfg.apply_model_catalog({"sonnet": {"price_input": 5.0, "output": 0,
                                    "price_output": 50.0, "name": "Sonnet 5",
                                    "context_window": 1_000_000}})
check("rozjechane proporcje → surowe stawki zamiast wymyślonego mnożnika",
      "$" in cfg.model_cost_hint("sonnet") or "za milion" in cfg.model_cost_hint("sonnet"),
      cfg.model_cost_hint("sonnet"))
cfg.apply_model_catalog(cat_new)   # przywróć stan zgodny z katalogiem

# --- plik podręczny ma TERMIN WAŻNOŚCI (inaczej stare dane przykrywają kod) ---
check("config ma próg zaufania do pliku podręcznego", hasattr(cfg, "MODEL_CACHE_TRUST_DAYS"))
check("świeży plik podręczny jest nakładany", cfg.should_trust_model_cache(1.0) is True)
check("plik na granicy progu jeszcze ufamy",
      cfg.should_trust_model_cache(float(cfg.MODEL_CACHE_TRUST_DAYS)) is True)
check("plik starszy niż próg NIE przykrywa wartości wbudowanych",
      cfg.should_trust_model_cache(cfg.MODEL_CACHE_TRUST_DAYS + 0.1) is False)
check("brak danych o wieku → nie ufamy", cfg.should_trust_model_cache(None) is False)
check("śmieć zamiast wieku → nie ufamy (zamiast wyjątku)",
      cfg.should_trust_model_cache("wczoraj") is False)
# Wartość wbudowaną czytamy ZE ŹRÓDŁA, bo w żywym module przykrywa ją plik
# podręczny — a pilnujemy tu właśnie tego, co apka wiezie w swoim wydaniu.
_cfg_txt = (ROOT / "src" / "config.py").read_text(encoding="utf-8")
check("wbudowana nazwa fable jest AKTUALNA (Fable 5.1, nie 'Fable 5')",
      '"fable": "Fable 5.1"' in _cfg_txt)
check("wbudowana cena Fable 5.1 = 10 / 50 (2× Opus)",
      '"fable":  {"input": 10.0, "output": 50.0}' in _cfg_txt)

check("parytet słowników PL/EN po dołożeniu napisów o koszcie",
      set(cfg.UI_TRANSLATIONS["pl-PL"]) == set(cfg.UI_TRANSLATIONS["en-US"]))
for _klucz in ("model_cost_more", "model_cost_less", "model_cost_raw",
               "models_stale_title", "models_stale_msg"):
    check(f"napis '{_klucz}' istnieje w OBU językach",
          _klucz in cfg.UI_TRANSLATIONS["pl-PL"] and _klucz in cfg.UI_TRANSLATIONS["en-US"])

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

# --- cicha awaria czujki ma termin ważności (naprawa usterki z 2026-09-14) ---
check("MainWindow ma metodę ostrzegającą o starych danych",
      "_maybe_warn_models_stale" in methods)
check("obsługa nieudanego sprawdzenia WOŁA tę metodę (sama definicja nie wystarcza)",
      src_txt.count("self._maybe_warn_models_stale(") >= 1, )
check("jest próg wieku danych", "MODELS_STALE_WARN_DAYS" in src_txt)
check("ostrzeżenie jest NIEMODALNE (nie blokuje pracy)",
      "models_stale_title" in src_txt and "Qt.NonModal" in src_txt)
check("okno ostrzeżenia trzymane w polu — inaczej znika w tej samej klatce",
      "self._models_stale_dialog = okno" in src_txt)
check("ostrzeżenie dławione — raz na uruchomienie apki",
      "_models_stale_warned" in src_txt)

# --- ostrzeżenie o koszcie wpięte w OKNO AGENTA, nie tylko w config ---
dlg_txt = (ROOT / "src" / "gui" / "dialogs.py").read_text(encoding="utf-8")
check("okno agenta importuje podpowiedź o koszcie", "model_cost_hint" in dlg_txt)
check("etykieta kosztu dodana pod listą modeli", "self.model_cost_label" in dlg_txt)
check("etykieta ODŚWIEŻA SIĘ przy zmianie modelu (inaczej pokazuje pierwszy wybór)",
      "self.model_combo.currentIndexChanged.connect(self._update_model_cost_label)" in dlg_txt)
dlg_tree = ast.parse(dlg_txt)
dlg_cls = {n.name: n for n in dlg_tree.body if isinstance(n, ast.ClassDef)}
_agent_dlg = dlg_cls.get("AgentConfigDialog")
_agent_methods = ({n.name for n in ast.walk(_agent_dlg) if isinstance(n, ast.FunctionDef)}
                  if _agent_dlg else set())
check("okno agenta ma metodę odświeżającą koszt",
      "_update_model_cost_label" in _agent_methods)

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
