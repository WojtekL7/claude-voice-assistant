#!/usr/bin/env python3
"""Bramka: wielkie wpisy TECHNICZNE w dzienniku nie zasłaniają rozmowy.

Usterka (2026-10-16, zakładka CRM): Claude Code od 2.1.300 dopisuje do
dziennika sesji wpisy `api-request` — kopię zapytania do serwera. Rosną razem
z rozmową (w CRM do 154 KB). Czytnik roli ostatniego wpisu brał sztywne 64 KB
z końca pliku, a te mieściły SAME wpisy techniczne → rola None →
`waiting_for_user()` zawsze False → flaga „agent czeka" nie zapalała się nigdy.
Zmierzone na kopii dziennika CRM z 10:53: stary kod 3× False, nowy True po
dwóch cichych tickach.

Uruchomienie:  python3 tools/test-journal-tech-entries.py
Kontrola negatywna (test MUSI paść na starym kodzie):
    CVA_SRC=<katalog z core/transcript_reader.py> python3 tools/test-journal-tech-entries.py

Sabotaż wykonany 2026-10-16 (WYNIK ZMIERZONY): kod sprzed poprawki (HEAD
31efe15) → padają [1] [2] [3] [4] [5] [7] [10]; [6] [8] [9] przechodzą też na
starym kodzie — to strażnicy braku regresji, nie dowód poprawki.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

SRC = os.environ.get("CVA_SRC") or str(Path(__file__).resolve().parent.parent / "src")
sys.path.insert(0, SRC)

from core import transcript_reader as tr  # noqa: E402
from core.transcript_reader import TranscriptReader  # noqa: E402

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


# ---------- sztuczny dziennik w kształcie Claude Code 2.1.300+ ----------

def e_user(text="policz ofertę"):
    return {"type": "user", "message": {"role": "user", "content": text}}


def e_tool_result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "wynik"}]}}


def e_assistant(text="Gotowe.", model="claude-opus-5-5"):
    return {"type": "assistant", "message": {"role": "assistant", "model": model,
            "content": [{"type": "text", "text": text}]}}


def e_api_request(kb):
    # Kolejność pól jak w prawdziwym dzienniku: "type" pierwsze.
    return {"type": "api-request", "sessionId": "x", "id": "r1",
            "params": {"messages": "m" * (kb * 1024)}}


def e_tech(kind):
    return {"type": kind, "sessionId": "x"}


TECH_TAIL = [e_tech("last-prompt"), e_tech("ai-title"), e_tech("mode"),
             e_tech("permission-mode"), e_tech("atis-latch"),
             {"type": "attachment", "isSidechain": False}]


class Fixture:
    def __init__(self, root):
        self.root = Path(root)
        self.workdir = self.root / "projekt"
        self.workdir.mkdir(parents=True)
        self.base = self.root / "projects"
        import re
        self.project_dir = self.base / re.sub(r'[^A-Za-z0-9]', '-', str(self.workdir.resolve()))
        self.project_dir.mkdir(parents=True)
        self.session_id = str(uuid.uuid4())

    @property
    def session_file(self):
        return self.project_dir / f"{self.session_id}.jsonl"

    def write(self, entries):
        with open(self.session_file, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def append(self, entries):
        with open(self.session_file, "a", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def reader(self):
        r = TranscriptReader(str(self.workdir))
        r._projects_base = self.base
        r.set_working_directory(str(self.workdir))
        r.pin_session(self.session_id)
        # Jak w GUI: pętla pyta najpierw has_session(), co ustala plik sesji.
        # Bez tego _last_entry_role() widzi „brak pliku" i test kłamie.
        r.has_session()
        return r


def with_fixture(fn):
    tmp = tempfile.mkdtemp(prefix="cva-tech-test-")
    try:
        fn(Fixture(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# Układ końca dziennika CRM z 10:53 (zmierzony): wypowiedź, wynik narzędzia,
# 154 KB `api-request`, a za nim drobne wpisy techniczne.
def crm_like(api_kb=154):
    return ([e_user(), e_assistant("Mam wszystko."), e_tool_result(),
             e_tech("api-request-blob"), e_api_request(api_kb)] + TECH_TAIL)


# ---------- testy ----------

def t1_role_behind_big_api_request(fx):
    fx.write(crm_like())
    check("[1] rola ostatniego wpisu widoczna zza 154 KB api-request",
          fx.reader()._last_entry_role(), "user")


def t2_waiting_flag_arms(fx):
    fx.write(crm_like())
    r = fx.reader()
    got = [r.waiting_for_user() for _ in range(3)]
    check("[2] flaga „agent czeka” zapala się po dwóch cichych tickach",
          got, [False, False, True])


def t3_model_behind_huge_tail(fx):
    # Wpis techniczny WIĘKSZY niż cały budżet skanu modelu (256 KB).
    fx.write([e_assistant(model="claude-sonnet-5-5"), e_api_request(400)] + TECH_TAIL)
    r = fx.reader()
    r.seek_to_end()
    check("[3] model widoczny zza 400 KB wpisów technicznych",
          r.active_model(), "claude-sonnet-5-5")


def t4_journal_lags_screen(fx):
    # Pytanie z polami wyboru: ostatni wpis z rolą = polecenie użytkownika.
    fx.write([e_assistant(), e_user("decyzja?"), e_api_request(154)] + TECH_TAIL)
    check("[4] 🔊: „dziennik w tyle za ekranem” rozpoznany zza api-request",
          fx.reader().journal_lags_screen(), True)


def t5_big_real_line_across_blocks(fx):
    # PRAWDZIWA wypowiedź dłuższa niż kawałek odczytu (64 KB) — musi się skleić.
    fx.write([e_user(), e_assistant("x" * (150 * 1024))] + TECH_TAIL)
    check("[5] wypowiedź 150 KB sklejona z kilku kawałków odczytu",
          fx.reader()._last_entry_role(), "assistant")


def t6_hard_cap_no_hang(fx):
    # Sam wpis techniczny większy niż twardy sufit: ma być szybkie None, bez zawieszki.
    cap_kb = getattr(tr, "TAIL_HARD_CAP_BYTES", 4 * 1024 * 1024) // 1024
    fx.write([e_assistant(), e_api_request(cap_kb + 512)] + TECH_TAIL)
    t0 = time.monotonic()
    role = fx.reader()._last_entry_role()
    dt = time.monotonic() - t0
    check("[6] wpis większy niż sufit → None (nie zgadujemy)", role, None)
    check("[6b] … i to szybko (< 0,5 s)", dt < 0.5, True)


def t7_cache_and_refresh(fx):
    fx.write(crm_like())
    r = fx.reader()
    calls = {"n": 0}
    orig = r._scan_last_entry_role if hasattr(r, "_scan_last_entry_role") else None

    def counting(skip):
        calls["n"] += 1
        return orig(skip)

    if orig is None:
        check("[7] pamięć wyniku przy stojącym pliku", "brak mechanizmu", "jest")
        return
    r._scan_last_entry_role = counting
    for _ in range(5):
        r._last_entry_role()
    check("[7] stojący plik: ogon czytany raz, nie co tick", calls["n"], 1)
    fx.append([e_assistant("Nowa odpowiedź.")])
    check("[7b] plik urósł → wynik odświeżony",
          (r._last_entry_role(), calls["n"]), ("assistant", 2))


def t8_full_scans_skip_tech(fx):
    fx.write([e_user("pierwsze"), e_assistant("Odpowiedź A"), e_api_request(154),
              e_user("drugie"), e_assistant("Odpowiedź B"), e_api_request(154)] + TECH_TAIL)
    r = fx.reader()
    last, state = r.turn_snapshot()
    check("[8] turn_snapshot: ostatnia wypowiedź i stan bez zmian",
          (last, state), ("Odpowiedź B", "idle"))
    texts = [e["text"] for e in r.conversation_entries()]
    check("[8b] wyszukiwarka widzi całą rozmowę, bez wpisów technicznych",
          texts, ["pierwsze", "Odpowiedź A", "drugie", "Odpowiedź B"])


def t9_old_journal_unchanged(fx):
    # Dziennik sprzed 2.1.300 (bez api-request) — zachowanie jak dotąd.
    fx.write([e_user(), e_assistant(), e_tool_result()] + TECH_TAIL)
    r = fx.reader()
    check("[9] stary kształt dziennika: rola", r._last_entry_role(), "user")
    check("[9b] stary kształt dziennika: rola z pominięciem tury agenta",
          r._last_entry_role(skip_agent_turns=True), "assistant")


def t10_compact_form_like_claude_code(fx):
    # Prawdziwy Claude Code pisze JSON BEZ spacji; reszta bramki — ze spacjami.
    # Oba zapisy muszą być rozpoznane jako techniczne (przepuszczenie zapełnia
    # budżet ogona: zmierzone przy pisaniu tej bramki, padało [3]).
    fx.write([e_assistant(model="claude-haiku-5-5")])
    with open(fx.session_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(e_api_request(400), separators=(",", ":")) + "\n")
    r = fx.reader()
    r.seek_to_end()
    check("[10] zwarty zapis Claude Code (bez spacji) też pomijany",
          r.active_model(), "claude-haiku-5-5")


def main():
    print(f"Kod pod testem: {SRC}")
    for fn in (t1_role_behind_big_api_request, t2_waiting_flag_arms,
               t3_model_behind_huge_tail, t4_journal_lags_screen,
               t5_big_real_line_across_blocks, t6_hard_cap_no_hang,
               t7_cache_and_refresh, t8_full_scans_skip_tech,
               t9_old_journal_unchanged, t10_compact_form_like_claude_code):
        try:
            with_fixture(fn)
        except Exception as ex:
            global FAILED
            FAILED += 1
            print(f"[FAIL] {fn.__name__}: wyjątek {ex!r}")
    print(f"\nWynik: {PASSED} OK / {FAILED} FAIL")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
