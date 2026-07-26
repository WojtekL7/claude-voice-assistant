"""Katalog modeli Claude Code — nazwy i okna kontekstu prosto ze strony Anthropic.

PO CO TO JEST
-------------
Nazwy modeli („Opus 5") i okna kontekstu (1M) zmieniają się przy każdym wydaniu,
a alias `opus` przekazywany do `claude --model` ZAWSZE oznacza NAJNOWSZY model
danej rodziny. Wartości zaszyte w kodzie starzeją się więc po cichu: apka
pokazywała „Opus 4.8", choć uruchamiała już Opus 5, a licznik tokenów liczył
Sonnetowi 200 tys. kontekstu zamiast 1 mln.

Ten moduł pobiera prawdę z oficjalnej strony Anthropic (wersja tekstowa
dokumentacji, bez logowania i bez klucza API) i zapisuje ją w pliku podręcznym.

⛔ ZASADA FAIL-OPEN: katalog to OPTYMALIZACJA, nigdy warunek działania.
Brak internetu / zmiana układu strony / uszkodzony plik podręczny → apka używa
wartości wbudowanych w `config.py` i działa dokładnie jak wcześniej.

⚠️ CELOWO NIE DODAJEMY SAMI NOWYCH RODZIN MODELI. Gdy Anthropic wypuści rodzinę,
której nie znamy (np. „neo"), nie wiemy, czy `claude --model neo` zadziała w CLI
użytkownika — zgadywanie skończyłoby się zakładką, która nie startuje. Taką
rodzinę zgłaszamy jako `new_families`, żeby apka mogła O NIEJ POWIEDZIEĆ,
a decyzję podjął człowiek.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

try:
    import requests  # klient HTTP projektu (NIE httpx)
except Exception:  # pragma: no cover - brak zależności nie może wywalić apki
    requests = None


# Wersja `.md` oficjalnej strony „Models overview" — czysty tekst, bez JS.
CATALOG_URL = "https://platform.claude.com/docs/en/about-claude/models/overview.md"

# Rodziny, których alias rozpoznaje `claude --model`. Tylko dla nich
# aktualizujemy dane; nowe rodziny → `new_families` (patrz nagłówek).
KNOWN_FAMILIES = ("fable", "opus", "sonnet", "haiku")

# Jak długo plik podręczny jest uznawany za świeży (7 dni).
CACHE_TTL_SECONDS = 7 * 24 * 3600

FETCH_TIMEOUT_SECONDS = 15

# Etykiety wierszy w tabeli na stronie (kolumny = modele, wiersze = cechy).
_ROW_ALIAS = "Claude API alias"
_ROW_ID = "Claude API ID"
_ROW_CONTEXT = "Context window"
_ROW_MAX_OUTPUT = "Max output"
_ROW_DESCRIPTION = "Description"

_TOOLTIP_RE = re.compile(r"<Tooltip[^>]*>(.*?)</Tooltip>", re.S)
_FAMILY_RE = re.compile(r"claude-([a-z]+)-[0-9]")
_TOKENS_RE = re.compile(r"([\d.]+)\s*([kKmM])?\s*tokens")


class CatalogError(RuntimeError):
    """Pobranie lub odczytanie katalogu się nie udało (wołający ma fail-open)."""


# ---------------------------------------------------------------- parsowanie


def _strip_cell(cell: str) -> str:
    """Zdejmuje z komórki tabeli ozdobniki dokumentacji (Tooltip, gwiazdki, linki)."""
    text = _TOOLTIP_RE.sub(r"\1", cell)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # [tekst](link) → tekst
    text = text.replace("**", "").replace("\\", "")
    text = re.sub(r"<[^>]+>", "", text)  # resztki znaczników
    return text.strip()


def _parse_tokens(text: str) -> int | None:
    """'1M tokens' → 1000000, '200k tokens' → 200000. Nierozpoznane → None."""
    m = _TOKENS_RE.search(text)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return int(value)


def _table_rows(markdown: str) -> list[list[str]]:
    """Wszystkie wiersze tabel markdown jako listy komórek."""
    rows = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped[1:-1].split("|")]
        if len(cells) >= 2:
            rows.append(cells)
    return rows


def _display_name(header_cell: str) -> str:
    """'Claude Opus 5' → 'Opus 5' (w apce nie powtarzamy słowa Claude)."""
    name = _strip_cell(header_cell)
    return re.sub(r"^Claude\s+", "", name).strip()


def parse_catalog(markdown: str) -> dict[str, dict]:
    """Wyciąga ze strony mapę: rodzina → {name, api_id, context_window, ...}.

    Bierzemy PIERWSZĄ tabelę zawierającą wiersz „Claude API alias" — to tabela
    modeli AKTUALNYCH, czyli dokładnie tych, na które rozwiązują się aliasy CLI.
    Tabela modeli starszych (niżej na stronie) jest świadomie pomijana.

    Rzuca CatalogError, gdy strona nie wygląda jak oczekiwana tabela.
    """
    rows = _table_rows(markdown)
    if not rows:
        raise CatalogError("na stronie nie ma żadnej tabeli")

    # Znajdź wiersz aliasów i nagłówek tabeli, w której leży.
    alias_row = None
    header_row = None
    for idx, cells in enumerate(rows):
        if _strip_cell(cells[0]) == _ROW_ALIAS:
            alias_row = cells
            # Nagłówek = pierwszy wiersz tej tabeli; cofamy się do wiersza
            # o tej samej liczbie kolumn poprzedzającego separator '---'.
            for back in range(idx - 1, -1, -1):
                if set(_strip_cell(rows[back][0])) <= set("-: "):
                    header_row = rows[back - 1] if back > 0 else None
                    break
            break
    if not alias_row or not header_row:
        raise CatalogError('nie znaleziono wiersza „%s” z nagłówkiem' % _ROW_ALIAS)

    def row_for(label: str) -> list[str] | None:
        for cells in rows:
            if _strip_cell(cells[0]) == label and len(cells) == len(alias_row):
                return cells
        return None

    id_row = row_for(_ROW_ID)
    ctx_row = row_for(_ROW_CONTEXT)
    out_row = row_for(_ROW_MAX_OUTPUT)
    desc_row = row_for(_ROW_DESCRIPTION)

    catalog: dict[str, dict] = {}
    for col in range(1, len(alias_row)):
        alias = _strip_cell(alias_row[col])
        api_id = _strip_cell(id_row[col]) if id_row else alias
        family_match = _FAMILY_RE.match(alias) or _FAMILY_RE.match(api_id)
        if not family_match:
            continue
        family = family_match.group(1)
        entry = {
            "name": _display_name(header_row[col]) if col < len(header_row) else family,
            "api_id": api_id or alias,
            "api_alias": alias,
        }
        if ctx_row:
            ctx = _parse_tokens(_strip_cell(ctx_row[col]))
            if ctx:
                entry["context_window"] = ctx
        if out_row:
            out = _parse_tokens(_strip_cell(out_row[col]))
            if out:
                entry["max_output"] = out
        if desc_row:
            entry["description"] = _strip_cell(desc_row[col])
        catalog[family] = entry

    # Kontrola przytomności: parser, który „przeszedł", ale nic sensownego nie
    # zwrócił, jest gorszy niż jawny błąd — wtedy wołający zostaje na wbudowanych.
    usable = [f for f, e in catalog.items() if e.get("context_window")]
    if len(usable) < 2:
        raise CatalogError(
            "sparsowano %d modeli z oknem kontekstu — układ strony się zmienił"
            % len(usable)
        )
    return catalog


# --------------------------------------------------------------- pobieranie


def fetch_markdown(url: str = CATALOG_URL, timeout: int = FETCH_TIMEOUT_SECONDS) -> str:
    """Pobiera stronę. Rzuca CatalogError przy każdym problemie."""
    if requests is None:
        raise CatalogError("brak biblioteki requests")
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "VibeCodingAssistant"})
        resp.raise_for_status()
    except Exception as exc:  # sieć, DNS, 404, timeout — wszystko jednakowo
        raise CatalogError(f"nie udało się pobrać {url}: {exc}") from exc
    if not resp.text or len(resp.text) < 500:
        raise CatalogError("pobrana strona jest podejrzanie krótka")
    return resp.text


# ----------------------------------------------------------- plik podręczny


def load_cached(cache_file: Path) -> dict | None:
    """Czyta zapisany katalog. Uszkodzony/nieczytelny plik → None (fail-open)."""
    try:
        data = json.loads(Path(cache_file).read_text(encoding="utf-8"))
    except Exception:
        return None
    models = data.get("models")
    if not isinstance(models, dict) or not models:
        return None
    return data


def cached_models(cache_file: Path) -> dict[str, dict]:
    """Sam słownik modeli z pliku podręcznego (pusty, gdy brak/uszkodzony)."""
    data = load_cached(cache_file)
    return data.get("models", {}) if data else {}


def is_stale(cache_file: Path, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Czy warto odpytać stronę (brak pliku albo starszy niż TTL)."""
    data = load_cached(cache_file)
    if not data:
        return True
    try:
        return (time.time() - float(data.get("fetched_at", 0))) > ttl
    except (TypeError, ValueError):
        return True


def _save_cache(cache_file: Path, models: dict[str, dict], url: str) -> None:
    """Zapis ATOMOWY — przerwany zapis nie może zostawić uszkodzonego pliku."""
    cache_file = Path(cache_file)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": time.time(),
        "source": url,
        "models": models,
    }
    tmp = cache_file.with_suffix(cache_file.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, cache_file)


def diff_against(previous: dict[str, dict], fresh: dict[str, dict]) -> dict:
    """Co się zmieniło — do komunikatu dla użytkownika.

    `new_families` = rodziny spoza KNOWN_FAMILIES; ich NIE dodajemy same
    (nie wiemy, czy alias zadziała w CLI usera) — to materiał na powiadomienie.
    """
    renamed, new_families = [], []
    for family, entry in fresh.items():
        if family not in KNOWN_FAMILIES:
            if family not in previous:
                new_families.append({"family": family, "name": entry.get("name", family)})
            continue
        old_name = (previous.get(family) or {}).get("name")
        if old_name and old_name != entry.get("name"):
            renamed.append({"family": family, "from": old_name, "to": entry["name"]})
    return {"renamed": renamed, "new_families": new_families}


def refresh(cache_file: Path, url: str = CATALOG_URL,
            timeout: int = FETCH_TIMEOUT_SECONDS) -> tuple[dict[str, dict], dict]:
    """Pobierz → sparsuj → zapisz. Zwraca (modele, co-się-zmieniło).

    Rzuca CatalogError; wołający MUSI to złapać i zostać na wbudowanych.
    """
    markdown = fetch_markdown(url, timeout)
    fresh = parse_catalog(markdown)
    changes = diff_against(cached_models(cache_file), fresh)
    _save_cache(cache_file, fresh, url)
    return fresh, changes


def merge_into(builtin_names: dict[str, str], builtin_limits: dict[str, int],
               models: dict[str, dict]) -> tuple[dict[str, str], dict[str, int]]:
    """Nakłada świeże nazwy i okna kontekstu na wartości wbudowane.

    Ruszamy WYŁĄCZNIE rodziny, które apka już zna (KNOWN_FAMILIES) i które
    realnie ma w swojej liście — żeby katalog nie mógł dołożyć pozycji,
    której `claude --model` może nie przyjąć.
    """
    names = dict(builtin_names)
    limits = dict(builtin_limits)
    for family, entry in (models or {}).items():
        if family not in KNOWN_FAMILIES or family not in names:
            continue
        name = entry.get("name")
        if isinstance(name, str) and name.strip():
            names[family] = name.strip()
        ctx = entry.get("context_window")
        if isinstance(ctx, int) and ctx > 0:
            limits[family] = ctx
    return names, limits
