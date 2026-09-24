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

# ------------------ 7c. premiera Opusa 5.5 (2026-09-24): ceny i wysiłek przy STARCIE
# Usterka, którą to pilnuje: ceny z katalogu nakładała WYŁĄCZNIE droga „odśwież
# z sieci", a nie start apki z pliku podręcznego — więc po restarcie wracały
# ceny wpisane w kod i podpowiedź mówiła „Fable 2× droższy" zamiast 2,5×.
# Import w PODPROCESIE z atrapą HOME, bo w tym procesie `config` już siedzi.
import json as _json  # noqa: E402
import subprocess as _sp  # noqa: E402
import tempfile as _tf  # noqa: E402
import time as _time  # noqa: E402

# ⛔ Osłonięte: parser zepsuty przez badany błąd nie może WYWALIĆ bramki
# w połowie (sabotaż S1 tak ją urwał: 92 z 138) — ma dać czerwone, nie ciszę.
try:
    cat_0924 = mc.parse_catalog(
        (ROOT / "tools" / "fixtures" / "models-overview-2026-09-24.md").read_text(encoding="utf-8"))
except Exception as _exc:
    cat_0924 = {}
    print(f"       (parser padł na stronie z 2026-09-24: {_exc!r})")
check("strona z 2026-09-24 w ogóle się parsuje (4 rodziny)",
      set(cat_0924) == {"fable", "opus", "sonnet", "haiku"}, sorted(cat_0924))
cat_0924 = cat_0924 or {k: {} for k in ("fable", "opus", "sonnet", "haiku")}
check("strona z 2026-09-24: Opus nazywa się Opus 5.5",
      cat_0924.get("opus", {}).get("name") == "Opus 5.5", cat_0924.get("opus"))
check("strona z 2026-09-24: cena Opusa 5.5 = 4 / 20",
      (cat_0924["opus"].get("price_input"), cat_0924["opus"].get("price_output")) == (4.0, 20.0))
check("strona z 2026-09-24: Opus 5.5 startuje na medium, Fable na high",
      cat_0924["opus"].get("default_effort") == "medium"
      and cat_0924["fable"].get("default_effort") == "high")
check("strona z 2026-09-24: Haiku nie ma domyślnego wysiłku (nie zgadujemy)",
      "default_effort" not in cat_0924["haiku"])

_PROBE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import config as c
print(json.dumps({"prices": c.CLAUDE_MODEL_PRICES, "effort": c.CLAUDE_MODEL_DEFAULT_EFFORT,
                  "names": c.CLAUDE_MODELS, "hint": c.model_cost_hint("fable")},
                 ensure_ascii=False))
"""


def _start_with_cache(models, age_days):
    """Uruchom świeży import `config` z plikiem podręcznym w podanym wieku."""
    with _tf.TemporaryDirectory() as home:
        d = Path(home) / ".vibe-coding-assistant"
        d.mkdir()
        (d / "models-cache.json").write_text(_json.dumps({
            "fetched_at": _time.time() - age_days * 86400,
            "source": "test", "models": models}), encoding="utf-8")
        env = {k: v for k, v in __import__("os").environ.items()}
        env["HOME"] = home
        out = _sp.run([sys.executable, "-B", "-c", _PROBE, str(ROOT / "src")],
                      env=env, capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return {"_err": out.stderr[-400:]}
        return _json.loads(out.stdout.strip().splitlines()[-1])


# Wartości CELOWO nietypowe (8/40, „low") — różne i od wpisanych w kod, i od
# strony, więc trafienie nie może być przypadkiem.
_dziwny = {k: dict(v) for k, v in cat_0924.items()}
_dziwny["opus"].update(price_input=8.0, price_output=40.0, default_effort="low")
_swiezy = _start_with_cache(_dziwny, age_days=1)
check("START z plikiem podręcznym NAKŁADA ceny (nie tylko nazwy)",
      _swiezy.get("prices", {}).get("opus") == {"input": 8.0, "output": 40.0}, _swiezy)
check("START z plikiem podręcznym NAKŁADA domyślny wysiłek",
      _swiezy.get("effort", {}).get("opus") == "low", _swiezy.get("effort"))

_prawdziwy = _start_with_cache(cat_0924, age_days=1)
check("po starcie z dzisiejszym katalogiem: Fable 2,5× droższy niż Opus 5.5",
      "2,5×" in _prawdziwy.get("hint", "") and "Opus 5.5" in _prawdziwy.get("hint", ""),
      _prawdziwy.get("hint"))

# KONTROLA ODWROTNA: plik starszy niż próg zaufania NIE może wnieść cen.
_stary_plik = _start_with_cache(_dziwny, age_days=cfg.MODEL_CACHE_TRUST_DAYS + 5)
check("stary plik podręczny NIE nakłada cen (zostają wbudowane)",
      _stary_plik.get("prices", {}).get("opus") == {"input": 4.0, "output": 20.0},
      _stary_plik.get("prices"))
check("stary plik podręczny NIE nakłada wysiłku",
      _stary_plik.get("effort", {}).get("opus") == "medium", _stary_plik.get("effort"))
check("start BEZ katalogu (stary plik) pokazuje nazwę wbudowaną Opus 5.5",
      _stary_plik.get("names", {}).get("opus") == "Opus 5.5", _stary_plik.get("names"))

# Droga „odśwież z sieci" nakłada wysiłek tak samo jak start.
cfg.apply_model_catalog(_dziwny)
check("odświeżenie z sieci nakłada domyślny wysiłek", cfg.model_default_effort("opus") == "low")
cfg.apply_model_catalog(cat_0924)
check("model_default_effort: Opus 5.5 → medium", cfg.model_default_effort("opus") == "medium")
check("model_default_effort: Haiku → None (nie wiemy, nie zgadujemy)",
      cfg.model_default_effort("haiku") is None)
check("model_default_effort: przypięty Opus 4.8 → None",
      cfg.model_default_effort("claude-opus-4-8") is None)
check("model_default_effort: śmieć → None zamiast wyjątku",
      cfg.model_default_effort(None) is None and cfg.model_default_effort("xyz") is None)
_zly = {k: dict(v) for k, v in cat_0924.items()}
_zly["sonnet"]["default_effort"] = "turbo"
cfg.apply_model_catalog(_zly)
check("nieznany poziom z katalogu NIE nadpisuje dobrego",
      cfg.model_default_effort("sonnet") == "high")
cfg.apply_model_catalog(cat_0924)

check("wbudowana nazwa opus jest AKTUALNA (Opus 5.5)", '"opus": "Opus 5.5"' in _cfg_txt)
check("wbudowana cena Opusa 5.5 = 4 / 20",
      '"opus":   {"input": 4.0,  "output": 20.0}' in _cfg_txt)
for _klucz in ("dlg_effort_model_default_is", "effort_word_low",
               "effort_word_medium", "effort_word_high"):
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

# --- okno „Poziom wysiłku" pokazuje, CO znaczy „Domyślny modelu" (2026-09-24) ---
check("okno wysiłku pyta o domyślny wysiłek modelu",
      "config.model_default_effort(key)" in src_txt)
check("okno wysiłku wpisuje poziom w pozycję 0 (Domyślny modelu)",
      "combo.setItemText(0, tr('dlg_effort_model_default_is')" in src_txt)

# POMIAR SKUTKU: prawdziwa metoda okna na atrapie `self`; exec_ podmieniony tak,
# żeby odczytać listy i ODRZUCIĆ okno — odrzucenie nie zapisuje niczego
# (metoda zapisuje WYŁĄCZNIE po „Zapisz"), więc prawdziwy plik ustawień
# Claude Code jest tu tylko CZYTANY.
try:
    import os as _os
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication, QDialog, QComboBox, QFormLayout, QLabel  # noqa: E402
    _qapp = QApplication.instance() or QApplication([])
    from gui import main_window as _mw  # noqa: E402

    _zlapane = {}

    def _exec_podglad(dlg):
        for form in dlg.findChildren(QFormLayout):
            for r in range(form.rowCount()):
                lab = form.itemAt(r, QFormLayout.LabelRole)
                fld = form.itemAt(r, QFormLayout.FieldRole)
                if lab and fld and isinstance(fld.widget(), QComboBox):
                    _zlapane[lab.widget().text().split("   ")[0]] = fld.widget().itemText(0)
        return QDialog.Rejected

    _stare_exec = QDialog.exec_
    QDialog.exec_ = _exec_podglad
    try:
        from PyQt5.QtWidgets import QWidget  # noqa: E402

        class _Atrapa(QWidget):     # QDialog wymaga prawdziwego rodzica
            def _update_status(self, *_a):
                pass
        cfg.apply_model_catalog(cat_0924)
        _mw.MainWindow._show_model_effort_dialog(_Atrapa())
    finally:
        QDialog.exec_ = _stare_exec
    _opus = next((v for k, v in _zlapane.items() if k.startswith("Opus 5.5")), None)
    _fable = next((v for k, v in _zlapane.items() if k.startswith("Fable")), None)
    _haiku = next((v for k, v in _zlapane.items() if k.startswith("Haiku")), None)
    _t = cfg.t
    check("OKNO: Opus 5.5 pokazuje 'Domyślny modelu (średni/medium)'",
          _opus == _t("dlg_effort_model_default_is").format(level=_t("effort_word_medium")),
          _zlapane)
    check("OKNO: Fable pokazuje domyślny poziom wysoki/high",
          _fable == _t("dlg_effort_model_default_is").format(level=_t("effort_word_high")),
          _fable)
    check("OKNO (kontrola odwrotna): Haiku zostaje przy gołym 'Domyślny modelu'",
          _haiku == _t("dlg_effort_model_default"), _haiku)
except Exception as _exc:  # brak Qt w środowisku = jawny FAIL, nie cisza
    check("OKNO: pomiar skutku wykonany", False, repr(_exc))

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
