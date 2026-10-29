#!/usr/bin/env python3
"""Bramka: licznik zakładki z DZIENNIKA SESJI, a Σ = DZISIEJSZE zużycie.

ZGŁOSZENIE 2026-10-29: „licznik Σ na dole nie współgra z sumą agentów".
Przyczyny (z kodu): (1) wyjście terminala zakładki W TLE doliczało się do
zakładki AKTYWNEJ; (2) Σ nie zerowała się przy /clear i pamiętała zamknięte
zakładki; (3) liczba to były znaki z ekranu ÷ 3,5 — przerysowania TUI,
animacje i migająca kropka zawyżały wynik; (4) wiadomość usera liczona 2×.
Lek: licznik zakładki = `usage` ostatniej odpowiedzi z JEJ dziennika
(TranscriptReader.context_usage).
DRUGIE polecenie tego samego dnia: Σ ma liczyć DZISIEJSZE zużycie także
zamkniętych zakładek → core/daily_usage.py (wersja „B": wejście + zapis do
pamięci podręcznej + wyjście, każda odpowiedź raz — Claude Code zapisuje
jedną odpowiedź w kilku wpisach z identycznym `usage`).

Sekcje:
  A — czytnik: prawdziwy wpis, pod-agent i komunikat techniczny pomijane,
      wielki wpis `api-request` nie zasłania, nowa odpowiedź = nowa liczba.
  B — okno: praca zakładki w tle zmienia TYLKO jej licznik,
      /clear → 0 do NOWEJ odpowiedzi, brak sesji → 0.
  C — kod: nic już nie liczy znaków z terminala.
  D — DailyUsage: duplikaty odpowiedzi raz, wczoraj pomijane, pod-agent
      liczony, <synthetic> nie, plik niezmieniony nie zmienia sumy,
      dopisek doliczany przyrostowo, zmiana dnia zeruje, warianty A/B/C.
  E — okno: Σ i podpowiedź pochodzą z DailyUsage, zamknięcie zakładki
      Σ NIE zmniejsza.

⚠️ Okno nie jest budowane w całości: obiekt MainWindow bez konstruktora,
PRAWDZIWE metody `_sync_context_tokens`,
`_reset_context_usage`, `_refresh_total_tokens_label` i pętla
`_poll_transcripts` na prawdziwych zakładkach AgentTab z atrapą czytnika.

URUCHOMIENIE:
    env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH -u CLAUDE_CODE_SUBAGENT_MODEL \\
        QT_QPA_PLATFORM=offscreen venv/bin/python -B tools/test-token-counter.py
"""
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# Atrapa HOME PRZED importem config (inaczej czytałby prawdziwy katalog usera).
_HOME = tempfile.mkdtemp(prefix="cva-token-home-")
os.environ["HOME"] = _HOME
os.environ.setdefault("CVA_APPEARANCE", "dark")

from PyQt5.QtCore import Qt                                  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_app = QApplication(sys.argv)

from core.transcript_reader import TranscriptReader          # noqa: E402
from gui.agent_tab import AgentTab                           # noqa: E402
from gui.main_window import MainWindow                       # noqa: E402

wyniki = []


def spr(nr, opis, war, szczegol=""):
    wyniki.append(bool(war))
    print(f"[{'OK ' if war else 'FAIL'}] {nr}. {opis}" + (f"  ({szczegol})" if szczegol else ""))


def odp(mid, inp, cr, cc, out, **extra):
    """Wpis odpowiedzi agenta w kształcie Claude Code."""
    e = {"type": "assistant", "uuid": "u-" + mid,
         "message": {"id": mid, "model": "claude-opus-5-5",
                     "usage": {"input_tokens": inp, "cache_read_input_tokens": cr,
                               "cache_creation_input_tokens": cc, "output_tokens": out}}}
    e.update(extra)
    return e


def dopisz(path, *wpisy):
    with open(path, "a", encoding="utf-8") as f:
        for w in wpisy:
            f.write((w if isinstance(w, str) else json.dumps(w)) + "\n")


def czytnik_na(path):
    """Czytnik przypięty do konkretnego pliku (bez katalogu ~/.claude)."""
    r = TranscriptReader(os.path.dirname(path))
    r._session_file = path
    r._ensure_session = lambda: None
    return r


# ============================== A — czytnik ==============================
tmp = tempfile.mkdtemp(prefix="cva-token-")
plik = os.path.join(tmp, "sesja.jsonl")
dopisz(plik,
       {"type": "user", "message": {"role": "user", "content": "cześć"}},
       odp("m1", 10, 1000, 200, 50))
r = czytnik_na(plik)
spr("A1", "zwykła odpowiedź → suma 4 pól usage",
    r.context_usage() == (1260, "m1"), r.context_usage())

# Pod-agent ma WIĘKSZE liczby i stoi później — nie może wygrać.
dopisz(plik, odp("sub", 1, 900000, 0, 1, isSidechain=True))
spr("A2", "wpis pod-agenta (isSidechain) pomijany",
    r.context_usage() == (1260, "m1"), r.context_usage())

# Komunikat techniczny Claude Code: model <synthetic>.
syn = odp("syn", 5, 5, 5, 5)
syn["message"]["model"] = "<synthetic>"
dopisz(plik, syn)
spr("A3", "komunikat <synthetic> pomijany",
    r.context_usage() == (1260, "m1"), r.context_usage())

# Wielki wpis techniczny (jak `api-request` od Claude Code 2.1.300, do 154 KB).
dopisz(plik, '{"type":"api-request","payload":"' + "x" * 300_000 + '"}')
spr("A4", "wpis api-request 300 KB nie zasłania odpowiedzi",
    r.context_usage() == (1260, "m1"), r.context_usage())

dopisz(plik, odp("m2", 3, 5000, 0, 40))
spr("A5", "nowa odpowiedź → nowa liczba i nowy identyfikator",
    r.context_usage() == (5043, "m2"), r.context_usage())

pusty = os.path.join(tmp, "pusty.jsonl")
dopisz(pusty, {"type": "user", "message": {"role": "user", "content": "x"}})
spr("A6", "dziennik bez odpowiedzi agenta → None", czytnik_na(pusty).context_usage() is None)

# Pamięć podręczna: bez wzrostu pliku drugi odczyt NIE czyta dysku.
_licz = {"n": 0}
import core.transcript_reader as _tr                       # noqa: E402
_orig_tail = _tr._tail_lines_reversed


def _liczacy(*a, **k):
    _licz["n"] += 1
    return _orig_tail(*a, **k)


_tr._tail_lines_reversed = _liczacy
r.context_usage(); r.context_usage(); r.context_usage()
_tr._tail_lines_reversed = _orig_tail
spr("A7", "plik bez zmian → bez ponownego skanu (pętla co tick)", _licz["n"] == 0, _licz["n"])


# ============================== B — okno ==============================
class Czytnik:
    """Atrapa czytnika: zwraca to, co mu ustawimy."""

    def __init__(self, wynik, sesja=True):
        self.wynik = wynik
        self.sesja = sesja

    def context_usage(self):
        return self.wynik

    def has_session(self):
        return self.sesja


class Widget:
    def __init__(self):
        self.total = None
        self.tip = None

    def set_total_tokens(self, v, tooltip=None):
        self.total = v
        self.tip = tooltip


def zakladka(nazwa, wynik, sesja=True):
    t = AgentTab({"id": nazwa, "name": nazwa, "working_directory": ROOT})
    t.total_context_tokens = 0
    t._transcript_reader = Czytnik(wynik, sesja)
    return t


w = MainWindow.__new__(MainWindow)
QMainWindow.__init__(w)
w.mcp_status_widget = Widget()
w._daily_usage = None          # sekcja B nie dotyczy Σ
w._refresh_tokens_pending = False
odswiezenia = []
w._schedule_tokens_refresh = lambda: odswiezenia.append(1)
w._refresh_context_label = lambda: None

A = zakladka("A", (120_000, "a1"))
B = zakladka("B", (300_000, "b1"))
w.agent_tabs = {"A": A, "B": B}
w._get_current_agent_tab = lambda: A

w._sync_context_tokens(A, A._transcript_reader, True)
w._sync_context_tokens(B, B._transcript_reader, False)
spr("B1", "każda zakładka dostaje SWOJĄ liczbę z dziennika",
    (A.total_context_tokens, B.total_context_tokens) == (120_000, 300_000),
    (A.total_context_tokens, B.total_context_tokens))

# B pracuje w tle (A aktywna) — zmienia się TYLKO B.
B._transcript_reader.wynik = (310_000, "b2")
w._sync_context_tokens(B, B._transcript_reader, False)
spr("B3", "praca zakładki w TLE nie rusza licznika aktywnej",
    A.total_context_tokens == 120_000 and B.total_context_tokens == 310_000,
    (A.total_context_tokens, B.total_context_tokens))

# /clear w A: 0, dopóki dziennik nie ma NOWEJ odpowiedzi.
w._reset_context_usage(A)
spr("B5", "/clear → licznik zakładki 0",
    A.total_context_tokens == 0, A.total_context_tokens)
w._sync_context_tokens(A, A._transcript_reader, True)
spr("B6", "po /clear STARA odpowiedź z dziennika nie przywraca liczby",
    A.total_context_tokens == 0, A.total_context_tokens)
A._transcript_reader.wynik = (9_000, "a2")
w._sync_context_tokens(A, A._transcript_reader, True)
spr("B7", "po /clear NOWA odpowiedź → nowa liczba",
    A.total_context_tokens == 9_000, A.total_context_tokens)

# Pętla _poll_transcripts: zakładka bez sesji (restart) → 0; z sesją → z dziennika.
C = zakladka("C", (50_000, "c1"), sesja=False)
C.total_context_tokens = 77_000            # stara liczba sprzed restartu
D = zakladka("D", (64_000, "d1"))
w.agent_tabs = {"C": C, "D": D}
tw = QTabWidget()
w.tab_widget = tw
w._poll_hook_events = lambda: None
w._sync_detected_model = lambda *a: None


class _Stop(Exception):
    pass


def _stop(*a, **k):
    raise _Stop


# Po synchronizacji licznika pętla idzie dalej (priming) — tu przerywamy.
D._transcript_primed = False
D._transcript_reader.seek_to_end = _stop
try:
    w._poll_transcripts()
except _Stop:
    pass
spr("B10", "pętla: zakładka BEZ sesji (restart) → 0 zamiast starej liczby",
    C.total_context_tokens == 0, C.total_context_tokens)
spr("B11", "pętla: zakładka z sesją → liczba z jej dziennika",
    D.total_context_tokens == 64_000, D.total_context_tokens)

# Brak odpowiedzi w dzienniku → 0 (nie poprzednia wartość).
E = zakladka("E", None)
E.total_context_tokens = 5
w._sync_context_tokens(E, E._transcript_reader, True)
spr("B12", "dziennik bez odpowiedzi → 0", E.total_context_tokens == 0, E.total_context_tokens)



# ============================== D — DailyUsage ==============================
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from core.daily_usage import DailyUsage                   # noqa: E402

DZIS = date.today()


def ts(day, hour=12):
    """Znacznik czasu w UTC tak, by LOKALNIE wypadał w `day` o `hour`."""
    local = datetime(day.year, day.month, day.day, hour).astimezone()
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def wpis(mid, inp, cr, cc, out, day=DZIS, **extra):
    e = odp(mid, inp, cr, cc, out, **extra)
    e["timestamp"] = ts(day)
    return e


proj = tempfile.mkdtemp(prefix="cva-daily-")
os.makedirs(os.path.join(proj, "-proj-A", "sesja1", "subagents"))
fa = os.path.join(proj, "-proj-A", "s1.jsonl")
fz = os.path.join(proj, "-proj-B", "zamknieta.jsonl")
os.makedirs(os.path.dirname(fz))
fs = os.path.join(proj, "-proj-A", "sesja1", "subagents", "agent-1.jsonl")
# Jedna odpowiedź w DWÓCH wpisach (jak Claude Code), wczorajsza, techniczna.
dopisz(fa, wpis("r1", 10, 1000, 100, 50), wpis("r1", 10, 1000, 100, 50),
       wpis("old", 9, 9, 9, 9, day=DZIS - timedelta(days=1)))
syn = wpis("syn", 7, 7, 7, 7)
syn["message"]["model"] = "<synthetic>"
dopisz(fa, syn)
dopisz(fz, wpis("z1", 5, 2000, 200, 20))          # „zamknięta zakładka"
dopisz(fs, wpis("p1", 1, 300, 30, 3, isSidechain=True))   # pod-agent
du = DailyUsage(projects_dir=proj)
snap = du.refresh()
B_OCZ = (10 + 100 + 50) + (5 + 200 + 20) + (1 + 30 + 3)
spr("D1", "wersja B: każda odpowiedź RAZ, wczoraj i <synthetic> pominięte, pod-agent liczony",
    snap["b"] == B_OCZ, (snap["b"], B_OCZ))
spr("D2", "wariant A = B + ponowne czytanie, C = samo wyjście",
    snap["a"] == B_OCZ + 1000 + 2000 + 300 and snap["c"] == 50 + 20 + 3,
    (snap["a"], snap["c"]))
spr("D3", "liczba odpowiedzi bez duplikatów", snap["responses"] == 3, snap["responses"])
spr("D4", "drugi odczyt bez zmian w plikach → ta sama suma", du.refresh()["b"] == B_OCZ)
import builtins                                             # noqa: E402
import core.daily_usage as _du_mod                          # noqa: E402
_czytane = {"b": 0}


class _LiczacyPlik:
    def __init__(self, f):
        self._f = f

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._f.close()

    def seek(self, n):
        self._f.seek(n)

    def read(self):
        data = self._f.read()
        _czytane["b"] += len(data)
        return data


_du_mod.open = lambda *a, **k: _LiczacyPlik(builtins.open(*a, **k))
dopisz(fa, wpis("rx", 0, 0, 0, 1))
du.refresh()
del _du_mod.open
_dopisek = len(json.dumps(wpis("rx", 0, 0, 0, 1))) + 1
spr("D4b", "przyrost: po dopisku czytane są tylko NOWE bajty (pętla co 5 s)",
    _czytane["b"] == _dopisek, (_czytane["b"], _dopisek))
B_OCZ += 1
dopisz(fa, wpis("r2", 1, 5000, 10, 4))
spr("D5", "dopisana odpowiedź doliczona przyrostowo",
    du.refresh()["b"] == B_OCZ + 15, du.snapshot()["b"])
# Niedokończona linia (zapis w toku) — poczekaj, nie licz dwa razy.
with open(fa, "a") as f:
    f.write(json.dumps(wpis("r3", 1, 1, 1, 1))[:40])
spr("D6", "linia w trakcie zapisu nie liczona", du.refresh()["b"] == B_OCZ + 15)
# Plik skrócony (kompakcja) → czytany od nowa, ale bez podwójnego liczenia.
with open(fa, "w") as f:
    f.write(json.dumps(wpis("r2", 1, 5000, 10, 4)) + "\n")
spr("D7", "plik przepisany krócej → bez podwójnego liczenia", du.refresh()["b"] == B_OCZ + 15,
    du.snapshot()["b"])
spr("D8", "nowy dzień → licznik od zera",
    du.refresh(today=DZIS + timedelta(days=1))["b"] == 0)
pusty_katalog = DailyUsage(projects_dir=os.path.join(proj, "nie-ma"))
spr("D9", "brak katalogu dzienników → 0, bez wyjątku", pusty_katalog.refresh()["b"] == 0)

# ============================== E — okno: Σ z DailyUsage ==============================
du2 = DailyUsage(projects_dir=proj)
du2.refresh()
w._daily_usage = du2
w.agent_tabs = {"X": zakladka("X", (1, "x"))}
w._refresh_total_tokens_label()
spr("E1", "Σ na pasku = dzisiejsze zużycie (B), nie suma zakładek",
    w.mcp_status_widget.total == du2.snapshot()["b"], w.mcp_status_widget.total)
tip = w.mcp_status_widget.tip or ""
spr("E2", "podpowiedź niesie warianty A i C",
    f"{du2.snapshot()['a']:,}" in tip and f"{du2.snapshot()['c']:,}" in tip, tip[:80])
przed = w.mcp_status_widget.total
w.agent_tabs = {}
w._refresh_total_tokens_label()
spr("E3", "zamknięcie zakładek NIE zmniejsza Σ", w.mcp_status_widget.total == przed,
    (przed, w.mcp_status_widget.total))

# ============================== C — kod ==============================
src = open(os.path.join(ROOT, "src", "gui", "main_window.py"), encoding="utf-8").read()
spr("C1", "nikt nie woła starego liczenia znaków (_update_context_usage)",
    "_update_context_usage" not in src and "_chars_per_token" not in src
    and re.search(r"[^_a-z]_total_tokens\(", src) is None)
m = re.search(r"    def _on_terminal_output\(self, data\):(.*?)\n    def ", src, re.S)
spr("C2", "wyjście terminala nie dotyka liczników tokenów",
    m is not None and "total_context_tokens" not in m.group(1)
    and "_total" not in m.group(1), "brak funkcji" if m is None else "")

ok = sum(wyniki)
print(f"\nWYNIK: {ok}/{len(wyniki)} OK")
sys.exit(0 if ok == len(wyniki) else 1)
