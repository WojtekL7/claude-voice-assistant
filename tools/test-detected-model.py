#!/usr/bin/env python3
"""Bramka: wykrywanie modelu, który REALNIE odpowiada w zakładce.

Dotyczy ustawienia agenta „Domyślny" — apka nie przekazuje wtedy `--model`,
więc nazwę modelu zna wyłącznie dziennik sesji (`message.model`).

Uruchomienie:  python3 tools/test-detected-model.py

⚠️ Ten plik NIE może nazywać się jak moduł stdlib (patrz CLAUDE-COMMON:
„skrypt testowy nazwany jak moduł stdlib") — stąd prefiks `test-`.

Sabotaż potwierdzający, że testy ROZRÓŻNIAJĄ (wykonany 2026-07-27 — WYNIKI
ZMIERZONE, nie przewidziane; pierwsze podejście pokazało DWIE dziury):
  • `_entry_model` bez odrzucania `isSidechain`         → pada [4]
  • `_entry_model` bez odrzucania "<synthetic>"         → pada [5b]
      ⚠️ [5] przechodziło mimo tego sabotażu (odrzucała pieczątka
      `isApiErrorMessage`) — dlatego dopisano [5b] na samą nazwę.
  • `active_model` bez skanu ogona (sam poll)           → pada [2], [6]
  • `_forget_active_model` puste (brak zerowania)       → pada [8]
  • `_scan_tail_for_model` bez porzucenia uciętej linii → NIE pada NIC.
      To NIE luka w testach: ucięta linia i tak nie parsuje się jako JSON
      i wypada w `except`. `f.readline()` zostaje jako tania jawność
      intencji, ale jest zabezpieczeniem drugiej linii — nie mechanizmem.
Testy [1], [3], [7], [9]–[12] przechodziły też przy części sabotaży — są
strażnikami braku regresji, nie dowodem tych konkretnych mechanizmów.
"""
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.transcript_reader import TranscriptReader  # noqa: E402
import config  # noqa: E402

PASSED = 0
FAILED = 0


def check(name, got, expected):
    global PASSED, FAILED
    if got == expected:
        PASSED += 1
        print(f"[OK]   {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}\n         oczekiwano: {expected!r}\n         otrzymano:  {got!r}")


# ---------- pomocnicze: budowanie sztucznego dziennika ----------

def entry_assistant(model, text="Cześć", sidechain=False, api_error=False):
    obj = {
        "type": "assistant",
        "message": {"model": model, "content": [{"type": "text", "text": text}]},
    }
    if sidechain:
        obj["isSidechain"] = True
    if api_error:
        obj["isApiErrorMessage"] = True
    return json.dumps(obj, ensure_ascii=False)


def entry_user(text="pytanie"):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}},
                      ensure_ascii=False)


class Fixture:
    """Sztuczny katalog transkryptów + czytnik wskazany na konkretną sesję."""

    def __init__(self, root):
        self.root = Path(root)
        self.workdir = self.root / "projekt"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.base = self.root / "projects"
        self.session_id = str(uuid.uuid4())
        self.project_dir = self.base / self._encoded()
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def _encoded(self):
        import re
        return re.sub(r'[^A-Za-z0-9]', '-', str(self.workdir.resolve()))

    @property
    def session_file(self):
        return self.project_dir / f"{self.session_id}.jsonl"

    def write(self, lines):
        self.session_file.write_text("".join(l + "\n" for l in lines), encoding="utf-8")

    def append(self, lines):
        with open(self.session_file, "a", encoding="utf-8") as f:
            for l in lines:
                f.write(l + "\n")

    def reader(self):
        r = TranscriptReader(str(self.workdir))
        r._projects_base = self.base            # katalog testowy zamiast ~/.claude
        r.set_working_directory(str(self.workdir))
        r.pin_session(self.session_id)
        return r


def with_fixture(fn):
    tmp = tempfile.mkdtemp(prefix="cva-model-test-")
    try:
        fn(Fixture(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- testy czytnika ----------

def t1_poll_captures(fx):
    fx.write([entry_user(), entry_assistant("claude-opus-5")])
    r = fx.reader()
    r.poll()
    check("[1] poll() łapie model przy okazji czytania", r.active_model(), "claude-opus-5")


def t2_tail_scan_after_priming(fx):
    """Po restarcie apki priming pomija historię — model ma dać skan ogona."""
    fx.write([entry_user(), entry_assistant("claude-sonnet-5")])
    r = fx.reader()
    r.seek_to_end()                      # priming: nic z historii nie przyjdzie przez poll()
    check("[2] skan ogona po primingu (wznowiona sesja)", r.active_model(), "claude-sonnet-5")


def t3_only_user_entries(fx):
    fx.write([entry_user(), entry_user("drugie pytanie")])
    r = fx.reader()
    r.poll()
    check("[3] sam użytkownik → nie wiadomo (None)", r.active_model(), None)


def t4_sidechain_ignored(fx):
    fx.write([entry_user(), entry_assistant("claude-haiku-4-5", sidechain=True)])
    r = fx.reader()
    r.poll()
    check("[4] pod-agent (isSidechain) NIE liczy się jako model zakładki",
          r.active_model(), None)


def t5_synthetic_ignored(fx):
    fx.write([entry_user(), entry_assistant("<synthetic>", api_error=True)])
    r = fx.reader()
    r.poll()
    check("[5] komunikat techniczny (<synthetic>) pomijany", r.active_model(), None)


def t5b_synthetic_without_flag(fx):
    """Sama nazwa "<synthetic>" ma wystarczyć — bez polegania na pieczątce.

    Test [5] przechodził też z WYŁĄCZONYM sprawdzaniem "<": odrzucała go
    pieczątka `isApiErrorMessage`. Ten przypadek pilnuje samej nazwy.
    """
    fx.write([entry_user(), entry_assistant("<synthetic>")])
    r = fx.reader()
    r.poll()
    check("[5b] sztuczna nazwa modelu odrzucana bez pieczątki błędu",
          r.active_model(), None)


def t6_big_tail(fx):
    """Wpis z modelem daleko od początku pliku + ucięta pierwsza linia po skoku."""
    padding = [entry_user("x" * 5000) for _ in range(80)]      # ~400 KB
    fx.write(padding + [entry_assistant("claude-opus-5")])
    assert fx.session_file.stat().st_size > TranscriptReader.MODEL_TAIL_BYTES, "fixture za mały"
    r = fx.reader()
    r.seek_to_end()
    check("[6] duży dziennik: skan ogona radzi sobie z uciętą linią",
          r.active_model(), "claude-opus-5")


def t6b_beyond_tail_is_unknown(fx):
    """ZNANE OGRANICZENIE, udokumentowane testem: dalej niż ogon nie sięgamy.

    Wypowiedź starsza niż MODEL_TAIL_BYTES od końca pliku jest niewidoczna dla
    skanu → „nie wiadomo" (pasek pokaże samo „Domyślny"), nigdy zła nazwa.
    W praktyce nieszkodliwe: pierwsza nowa odpowiedź agenta uzupełnia nazwę.
    """
    padding = [entry_user("x" * 5000) for _ in range(80)]      # ~400 KB po wpisie
    fx.write([entry_assistant("claude-opus-5")] + padding)
    r = fx.reader()
    r.seek_to_end()
    check("[6b] model poza oknem skanu → nie wiadomo (nie zgadujemy)",
          r.active_model(), None)


def t7_newest_wins(fx):
    fx.write([entry_assistant("claude-sonnet-5"), entry_user(),
              entry_assistant("claude-opus-5")])
    r = fx.reader()
    r.poll()
    check("[7] liczy się OSTATNIA wypowiedź, nie pierwsza",
          r.active_model(), "claude-opus-5")


def t8_session_change_forgets(fx):
    fx.write([entry_assistant("claude-opus-5")])
    r = fx.reader()
    r.poll()
    assert r.active_model() == "claude-opus-5"
    fx.session_id = str(uuid.uuid4())          # zakładka wystartowała od nowa
    fx.write([entry_user()])
    r.pin_session(fx.session_id)
    check("[8] nowa sesja = zapomniany model (żadnych starych nazw)",
          r.active_model(), None)


def t9_no_session_file(fx):
    r = fx.reader()                             # plik jeszcze nie powstał
    check("[9] brak pliku sesji → None, bez wyjątku", r.active_model(), None)


# ---------- testy nazewnictwa (config) ----------

def t10_names():
    known = config.model_name_for_api_id("claude-opus-5")
    check("[10a] znany identyfikator → nazwa z katalogu",
          known, config.CLAUDE_MODELS_SHORT.get("opus"))
    check("[10b] pusty identyfikator → pusto (nic nie twierdzimy)",
          config.model_name_for_api_id(""), "")
    check("[10c] nieznany model → nazwa wyprowadzona z identyfikatora",
          config.model_name_for_api_id("claude-neo-9"), "Neo 9")
    check("[10d] data wydania obcinana",
          config.model_name_for_api_id("claude-zeta-4-5-20260101"), "Zeta 4.5")


def t11_limits():
    limit = config.context_limit_for_api_id("claude-opus-5")
    check("[11a] znany identyfikator → okno kontekstu z katalogu",
          isinstance(limit, int) and limit > 0, True)
    check("[11b] nieznany identyfikator → None (licznik nie zgaduje)",
          config.context_limit_for_api_id("claude-neo-9"), None)
    check("[11c] pusty identyfikator → None", config.context_limit_for_api_id(""), None)


def t12_map_survives_missing_catalog():
    """FAIL-OPEN: bez katalogu z sieci mapa nadal zna wpisy wbudowane."""
    backup = dict(config.CLAUDE_MODEL_API_IDS)
    try:
        config._rebuild_api_id_map(None)
        check("[12] bez katalogu: przypięta wersja dalej rozpoznawana",
              config.model_name_for_api_id("claude-opus-4-8"),
              config.CLAUDE_MODELS_SHORT.get("claude-opus-4-8"))
    finally:
        config.CLAUDE_MODEL_API_IDS.clear()
        config.CLAUDE_MODEL_API_IDS.update(backup)


# ---------- kontrola negatywna testu ----------

def t_control():
    """Czy ten plik w ogóle UMIE zgłosić błąd? Bez tego komplet [OK] nic nie znaczy."""
    global PASSED, FAILED
    before_failed = FAILED
    check("(kontrola negatywna — TA linia MA paść)", "cokolwiek", "coś innego")
    if FAILED == before_failed + 1:
        FAILED = before_failed          # spodziewana porażka — nie liczymy jej
        PASSED += 1
        print("[OK]   kontrola negatywna zadziałała (test potrafi paść)")
    else:
        print("[FAIL] kontrola negatywna NIE zadziałała — testom nie można ufać")
        FAILED += 1


def main():
    for fn in (t1_poll_captures, t2_tail_scan_after_priming, t3_only_user_entries,
               t4_sidechain_ignored, t5_synthetic_ignored, t5b_synthetic_without_flag,
               t6_big_tail, t6b_beyond_tail_is_unknown,
               t7_newest_wins, t8_session_change_forgets, t9_no_session_file):
        with_fixture(fn)
    t10_names()
    t11_limits()
    t12_map_survives_missing_catalog()
    t_control()
    print(f"\nWynik: {PASSED} OK / {FAILED} FAIL")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
