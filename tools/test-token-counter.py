#!/usr/bin/env python3
"""Bramka: licznik tokenów z DZIENNIKA SESJI, a Σ = suma liczników zakładek.

ZGŁOSZENIE 2026-10-29: „licznik Σ na dole nie współgra z sumą agentów".
Przyczyny (z kodu): (1) wyjście terminala zakładki W TLE doliczało się do
zakładki AKTYWNEJ; (2) Σ nie zerowała się przy /clear i pamiętała zamknięte
zakładki; (3) liczba to były znaki z ekranu ÷ 3,5 — przerysowania TUI,
animacje i migająca kropka zawyżały wynik; (4) wiadomość usera liczona 2×.
Lek: licznik zakładki = `usage` ostatniej odpowiedzi z JEJ dziennika
(TranscriptReader.context_usage), Σ = suma liczników otwartych zakładek.

Sekcje:
  A — czytnik: prawdziwy wpis, pod-agent i komunikat techniczny pomijane,
      wielki wpis `api-request` nie zasłania, nowa odpowiedź = nowa liczba.
  B — okno: praca zakładki w tle zmienia TYLKO jej licznik, Σ == suma,
      /clear → 0 do NOWEJ odpowiedzi, brak sesji → 0, zamknięta zakładka
      wypada z Σ.
  C — kod: nic już nie liczy znaków z terminala.

⚠️ Okno nie jest budowane w całości: obiekt MainWindow bez konstruktora,
PRAWDZIWE metody `_sync_context_tokens`, `_total_tokens`,
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

    def set_total_tokens(self, v):
        self.total = v


def zakladka(nazwa, wynik, sesja=True):
    t = AgentTab({"id": nazwa, "name": nazwa, "working_directory": ROOT})
    t.total_context_tokens = 0
    t._transcript_reader = Czytnik(wynik, sesja)
    return t


w = MainWindow.__new__(MainWindow)
QMainWindow.__init__(w)
w.mcp_status_widget = Widget()
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
w._refresh_total_tokens_label()
spr("B2", "Σ == suma liczników zakładek", w.mcp_status_widget.total == 420_000,
    w.mcp_status_widget.total)

# B pracuje w tle (A aktywna) — zmienia się TYLKO B.
B._transcript_reader.wynik = (310_000, "b2")
w._sync_context_tokens(B, B._transcript_reader, False)
spr("B3", "praca zakładki w TLE nie rusza licznika aktywnej",
    A.total_context_tokens == 120_000 and B.total_context_tokens == 310_000,
    (A.total_context_tokens, B.total_context_tokens))
spr("B4", "Σ odświeżona od razu przy zmianie zakładki w tle",
    w.mcp_status_widget.total == 430_000, w.mcp_status_widget.total)

# /clear w A: 0, dopóki dziennik nie ma NOWEJ odpowiedzi.
w._reset_context_usage(A)
spr("B5", "/clear → licznik zakładki 0, Σ bez niej",
    A.total_context_tokens == 0 and w.mcp_status_widget.total == 310_000,
    (A.total_context_tokens, w.mcp_status_widget.total))
w._sync_context_tokens(A, A._transcript_reader, True)
spr("B6", "po /clear STARA odpowiedź z dziennika nie przywraca liczby",
    A.total_context_tokens == 0, A.total_context_tokens)
A._transcript_reader.wynik = (9_000, "a2")
w._sync_context_tokens(A, A._transcript_reader, True)
spr("B7", "po /clear NOWA odpowiedź → nowa liczba",
    A.total_context_tokens == 9_000, A.total_context_tokens)
w._refresh_total_tokens_label()
spr("B8", "Σ znów == suma", w.mcp_status_widget.total == 319_000, w.mcp_status_widget.total)

# Zamknięcie zakładki: Σ ją gubi.
del w.agent_tabs["B"]
w._refresh_total_tokens_label()
spr("B9", "zamknięta zakładka wypada z Σ", w.mcp_status_widget.total == 9_000,
    w.mcp_status_widget.total)

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


# ============================== C — kod ==============================
src = open(os.path.join(ROOT, "src", "gui", "main_window.py"), encoding="utf-8").read()
spr("C1", "nikt nie woła starego liczenia znaków (_update_context_usage)",
    "_update_context_usage" not in src and "_chars_per_token" not in src)
m = re.search(r"    def _on_terminal_output\(self, data\):(.*?)\n    def ", src, re.S)
spr("C2", "wyjście terminala nie dotyka liczników tokenów",
    m is not None and "total_context_tokens" not in m.group(1)
    and "_total" not in m.group(1), "brak funkcji" if m is None else "")

ok = sum(wyniki)
print(f"\nWYNIK: {ok}/{len(wyniki)} OK")
sys.exit(0 if ok == len(wyniki) else 1)
