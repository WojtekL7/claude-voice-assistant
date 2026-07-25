#!/usr/bin/env python3
"""Test: 🔊 „czytaj ostatnią" czeka, gdy agent jest WINIEN odpowiedź.

Historia buga (ten sam objaw, trzy podejścia):
  * runda 1 (2026-07-22) — dziennik dostaje wypowiedź dopiero po jej
    dokończeniu (13,9 / 14,8 / 16,2 s dla 1,7–2,4 tys. znaków), a na ekranie
    widać ją od razu → klik w tym oknie czytał POPRZEDNIĄ. Lek: czekaj, gdy
    terminal się rusza (próg 2,0 s).
  * runda 2 (2026-07-23) — próg 2,0 s był WĘŻSZY niż zasłaniana luka (1–3 s);
    poszerzony do 4,0 s + licznik znaków strumienia.
  * runda 3 (2026-07-25) — user: „DALEJ czyta przedostatnią". Zmierzone na
    żywym dzienniku CRM: po odpowiedzi usera (11:20:13) agent MYŚLAŁ 30 s
    (wpis „thinking" 11:20:43), tekst dopisał 11:20:47. Przez te 30 s w pliku
    NIE MA ani jednego wpisu, a terminal pokazuje tylko animację poniżej progu
    200 zn./2 s → strażnik orzekał „nic nie leci" i czytał wypowiedź sprzed
    6 minut. Wniosek: pytanie „czy leci tekst" jest ZŁE. Pytamy dziennik
    o STRUKTURĘ TURY (`TranscriptReader.turn_snapshot`).

Testujemy DECYZJĘ (czekać czy czytać) bez okna GUI: metody MainWindow wołamy
na atrapie. Fixture'y stanu tury pochodzą z PRAWDZIWEGO dziennika CRM zdjętego
w chwili zgłoszenia (nie z formatu odtworzonego z pamięci). Każdy test ma
kontrolę negatywną — inaczej komplet zielonych niczego by nie dowodził.

Uruchomienie:  python3 tools/test-read-last-wait.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from gui.main_window import MainWindow  # noqa: E402
from core.transcript_reader import (  # noqa: E402
    TranscriptReader, TURN_IDLE, TURN_OWES_TEXT, TURN_TOOL_PENDING, TURN_UNKNOWN,
)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[OK]   {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


class FakeTab:
    def __init__(self, idle_secs, stream_chars=0):
        self._last_terminal_data_ts = time.monotonic() - idle_secs
        self._stream_chars = stream_chars

    def recent_output_chars(self, window_secs=None):
        return self._stream_chars


class FakeReader:
    """Dziennik sesji: kolejne odczyty zwracają kolejne wartości.

    `states` (opcjonalne) to stany tury zwracane równolegle z wypowiedziami;
    `sizes` — rozmiar pliku (przyrost = agent pracuje).
    """

    def __init__(self, values, states=None, sizes=None):
        self._values = list(values)
        self._states = list(states) if states else None
        self._sizes = list(sizes) if sizes else None
        self.seek_calls = 0
        self._size = 1000

    def last_response(self):
        return self._values[0] if len(self._values) == 1 else self._values.pop(0)

    def turn_snapshot(self):
        text = self.last_response()
        if self._states is None:
            return text, TURN_OWES_TEXT
        state = self._states[0] if len(self._states) == 1 else self._states.pop(0)
        return text, state

    def session_size(self):
        if self._sizes:
            self._size = self._sizes[0] if len(self._sizes) == 1 else self._sizes.pop(0)
        return self._size

    def seek_to_end(self):
        self.seek_calls += 1


class FakeTts:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


class FakeTimer:
    def __init__(self):
        self.stopped = 0

    def stop(self):
        self.stopped += 1


_WAIT_METHODS = ('_agent_is_writing', '_terminal_idle_secs', '_should_wait_for_response',
                 '_speak_journal_text', '_cancel_read_last_wait', '_check_read_last_wait',
                 '_finish_read_last_wait', '_session_size', '_read_last_debug')


class FakeWindow:
    """Atrapa MainWindow z podpiętymi PRAWDZIWYMI metodami z produkcji."""

    def __init__(self, tab, reader, before, hard_deadline_in=60.0,
                 terminal_idle=0.2, journal_idle=0.0):
        self.tts = FakeTts()
        self.statuses = []
        self._current_tab = tab
        self._read_wait_timer = FakeTimer()
        self._read_wait_tab = tab
        self._read_wait_reader = reader
        self._read_wait_before = before
        self._read_wait_hard_deadline = time.monotonic() + hard_deadline_in
        self._read_wait_started = time.monotonic()
        self._read_wait_size = 1000
        self._read_wait_size_changed = time.monotonic() - journal_idle
        self._read_wait_tool_since = None
        for meth in _WAIT_METHODS:
            setattr(self, meth, getattr(MainWindow, meth).__get__(self))

    def _get_current_agent_tab(self):
        return self._current_tab

    def _update_status(self, text):
        self.statuses.append(text)


# ============================================================================
# 1. Czujnik terminala (już tylko dla stanu NIEROZSTRZYGNIĘTEGO)
# ============================================================================
w = FakeWindow(None, None, None)
check("terminal ruszał się przed chwilą = agent pracuje",
      w._agent_is_writing(FakeTab(idle_secs=0.2)) is True)
check("2,5 s po ostatnim ruchu wciąż uznajemy za pracę (luka zapisu 1–3 s)",
      w._agent_is_writing(FakeTab(idle_secs=2.5)) is True)
check("po 5 s ciszy terminal uchodzi za martwy (kontrola negatywna)",
      w._agent_is_writing(FakeTab(idle_secs=5.0)) is False)
check("brak zakładki = brak pracy", w._agent_is_writing(None) is False)
check("cisza bez zakładki jest nieskończona",
      w._terminal_idle_secs(None) == float('inf'))

# ============================================================================
# 2. SEDNO RUNDY 3 — decyzja płynie ze stanu tury, nie z ruchu w terminalu
# ============================================================================
w = FakeWindow(None, None, None)
quiet = FakeTab(idle_secs=30.0)     # terminal MILCZY (agent myśli — nic nie drukuje)
busy = FakeTab(idle_secs=0.1)

check("agent winien odpowiedź → CZEKAMY, choć terminal milczy 30 s "
      "(dokładnie przypadek usera z 11:20)",
      w._should_wait_for_response(quiet, TURN_OWES_TEXT) is True)
check("agent bezczynny → czytamy natychmiast, nawet gdy terminal drga "
      "(kontrola negatywna — zero zwłoki na bezczynnej zakładce)",
      w._should_wait_for_response(busy, TURN_IDLE) is False)
check("pracuje narzędzie → czytamy natychmiast (przycisk nie wisi)",
      w._should_wait_for_response(busy, TURN_TOOL_PENDING) is False)
check("stan nieznany + żywy terminal → czekamy (stary czujnik jako zapas)",
      w._should_wait_for_response(busy, TURN_UNKNOWN) is True)
check("stan nieznany + martwy terminal → czytamy (kontrola negatywna)",
      w._should_wait_for_response(quiet, TURN_UNKNOWN) is False)

# ============================================================================
# 3. Nowa wypowiedź kończy czekanie i to JĄ czytamy
# ============================================================================
tab = FakeTab(0.2)
reader = FakeReader(["STARA odpowiedź", "STARA odpowiedź", "NOWA odpowiedź"],
                    states=[TURN_OWES_TEXT, TURN_OWES_TEXT, TURN_OWES_TEXT],
                    sizes=[1000, 1100, 1200])
w = FakeWindow(tab, reader, before="STARA odpowiedź")
w._check_read_last_wait()
check("czeka, dopóki w dzienniku leży STARA wypowiedź", w.tts.spoken == [],
      f"powiedziano: {w.tts.spoken}")
w._check_read_last_wait()
check("dalej czeka przy kolejnym sprawdzeniu", w.tts.spoken == [])
w._check_read_last_wait()
check("po dojściu NOWEJ — czyta właśnie ją",
      len(w.tts.spoken) == 1 and "NOWA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")
check("NIE przeczytał starej (sedno buga)",
      all("STARA" not in s for s in w.tts.spoken))
check("czekanie zostało zatrzymane", w._read_wait_timer is None)
check("czytnik przesunięty na koniec = brak podwójnego czytania",
      reader.seek_calls == 1, f"seek_calls={reader.seek_calls}")

# ============================================================================
# 4. Agent MYŚLI: terminal animuje, dziennik stoi → NIE wolno przerwać czekania
# ============================================================================
tab = FakeTab(idle_secs=0.3, stream_chars=60)      # tylko animacja, nie strumień
reader = FakeReader(["STARA"], states=[TURN_OWES_TEXT], sizes=[1000])
w = FakeWindow(tab, reader, before="STARA", journal_idle=25.0)
w._check_read_last_wait()
check("myślenie (mało znaków, dziennik stoi) NIE kończy czekania — "
      "tu wywracały się rundy 1 i 2",
      w.tts.spoken == [] and w._read_wait_timer is not None,
      f"powiedziano: {w.tts.spoken}")

# ============================================================================
# 5. Agent STANĄŁ bez pisania (pytanie / prośba o zgodę) → czytamy, co jest
# ============================================================================
tab = FakeTab(idle_secs=10.0)                      # ekran zamarł
reader = FakeReader(["OSTATNIA notka"], states=[TURN_OWES_TEXT], sizes=[1000])
w = FakeWindow(tab, reader, before="OSTATNIA notka", journal_idle=10.0)
w._check_read_last_wait()
check("cisza w terminalu + dziennik nie rośnie → czytamy najnowszą z dziennika",
      len(w.tts.spoken) == 1 and "OSTATNIA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")
check("i mówi na pasku, że agent się zatrzymał",
      any("zatrzyma" in s.lower() or "paused" in s.lower() for s in w.statuses),
      f"statusy: {w.statuses}")
check("przycisk nie wisi do bezpiecznika", w._read_wait_timer is None)

# kontrola negatywna: dziennik ROŚNIE (agent pracuje) → czekamy dalej
tab = FakeTab(idle_secs=10.0)
reader = FakeReader(["OSTATNIA notka"], states=[TURN_OWES_TEXT], sizes=[1500])
w = FakeWindow(tab, reader, before="OSTATNIA notka", journal_idle=10.0)
w._check_read_last_wait()
check("rosnący dziennik trzyma czekanie mimo ciszy w terminalu (kontrola negatywna)",
      w.tts.spoken == [] and w._read_wait_timer is not None,
      f"powiedziano: {w.tts.spoken}")

# ============================================================================
# 6. Narzędzie: krótkiemu dajemy szansę, długie zwalnia przycisk
# ============================================================================
tab = FakeTab(0.2)
reader = FakeReader(["STARA"], states=[TURN_TOOL_PENDING], sizes=[1000, 1100])
w = FakeWindow(tab, reader, before="STARA")
w._check_read_last_wait()
check("krótkie narzędzie nie przerywa czekania od razu",
      w.tts.spoken == [] and w._read_wait_tool_since is not None,
      f"powiedziano: {w.tts.spoken}")
w._read_wait_tool_since = time.monotonic() - 5.0        # narzędzie mieli już 5 s
w._check_read_last_wait()
check("narzędzie pracujące dłużej niż próg → czytamy, co jest",
      len(w.tts.spoken) == 1 and "STARA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")

# ============================================================================
# 7. Twardy bezpiecznik i przerwanie po zmianie zakładki
# ============================================================================
tab = FakeTab(0.2)
reader = FakeReader(["STARA"], states=[TURN_OWES_TEXT], sizes=[1000, 1100])
w = FakeWindow(tab, reader, before="STARA", hard_deadline_in=-1.0)
w._check_read_last_wait()
check("po twardym limicie czytamy to, co jest (nigdy cisza bez wyjaśnienia)",
      len(w.tts.spoken) == 1 and "STARA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")
check("i mówi o tym na pasku",
      any("pisze" in s or "writing" in s for s in w.statuses),
      f"statusy: {w.statuses}")

tab = FakeTab(0.2)
reader = FakeReader(["STARA", "NOWA"], states=[TURN_OWES_TEXT, TURN_OWES_TEXT])
w = FakeWindow(tab, reader, before="STARA")
w._current_tab = FakeTab(0.2)                       # user przeszedł gdzie indziej
w._check_read_last_wait()
check("po zmianie zakładki nic nie czyta", w.tts.spoken == [],
      f"powiedziano: {w.tts.spoken}")
check("i sprząta po sobie", w._read_wait_timer is None)

# ============================================================================
# 8. Pusta proza nie „mówi"
# ============================================================================
reader = FakeReader(["```\nkod\n```"])
w = FakeWindow(FakeTab(0.2), reader, before=None)
spoke = w._speak_journal_text(reader, "```\nsam kod, zero prozy\n```")
check("sam blok kodu → nie czytamy (kontrola negatywna)",
      spoke is False and w.tts.spoken == [], f"powiedziano: {w.tts.spoken}")

# ============================================================================
# 9. Wejście w tryb czekania (ścieżka, którą realnie woła przycisk)
# ============================================================================
# py_compile nie łapie błędnej nazwy w niewykonanym kodzie, a to jest metoda,
# którą woła 🔊 — musi zostać naprawdę uruchomiona. QTimer(self) wymaga QObject.
from PyQt5.QtCore import QCoreApplication, QObject  # noqa: E402

_app = QCoreApplication.instance() or QCoreApplication(sys.argv)


class FakeQWindow(QObject):
    """Atrapa musi BYĆ QObject — produkcyjny kod tworzy QTimer(self)."""

    def __init__(self, tab, reader):
        QObject.__init__(self)
        self.tts = FakeTts()
        self.statuses = []
        self._current_tab = tab
        self._read_wait_timer = None
        self._read_wait_tab = None
        self._read_wait_reader = reader
        self._read_wait_before = None
        self._read_wait_hard_deadline = 0.0
        self._read_wait_started = 0.0
        self._read_wait_size = -1
        self._read_wait_size_changed = 0.0
        self._read_wait_tool_since = None
        for meth in _WAIT_METHODS + ('_start_read_last_wait',):
            setattr(self, meth, getattr(MainWindow, meth).__get__(self))

    def _get_current_agent_tab(self):
        return self._current_tab

    def _update_status(self, text):
        self.statuses.append(text)


tab = FakeTab(0.2)
qw = FakeQWindow(tab, FakeReader(["STARA"], states=[TURN_OWES_TEXT]))
qw._start_read_last_wait(tab, qw._read_wait_reader, "STARA", TURN_OWES_TEXT)
check("przycisk potrafi wejść w tryb czekania (bez błędu nazw)",
      qw._read_wait_timer is not None and qw._read_wait_timer.isActive())
check("i od razu informuje na pasku, że czeka",
      any("czekam" in s.lower() or "waiting" in s.lower() for s in qw.statuses),
      f"statusy: {qw.statuses}")
check("dowód z dziennika = dłuższy limit czekania niż przy zgadywaniu",
      qw._read_wait_hard_deadline - time.monotonic() > 30.0,
      f"limit={qw._read_wait_hard_deadline - time.monotonic():.1f}s")
qw._cancel_read_last_wait()
check("odwołanie czekania czyści stan", qw._read_wait_timer is None)

qw2 = FakeQWindow(tab, FakeReader(["STARA"], states=[TURN_UNKNOWN]))
qw2._start_read_last_wait(tab, qw2._read_wait_reader, "STARA", TURN_UNKNOWN)
check("stan nieznany = krótszy limit (zgadywanie, nie dowód)",
      qw2._read_wait_hard_deadline - time.monotonic() < 25.0,
      f"limit={qw2._read_wait_hard_deadline - time.monotonic():.1f}s")
qw2._cancel_read_last_wait()

# ============================================================================
# 10. Czujnik treści w zakładce (filtr animacji bezczynności)
# ============================================================================
from collections import deque  # noqa: E402

from gui.agent_tab import AgentTab, _activity_residual  # noqa: E402

check("animacja bezczynności nie jest treścią",
      _activity_residual("\x1b[2K\r  ●  ") == "")
check("tekst odpowiedzi JEST treścią (kontrola negatywna)",
      len(_activity_residual("\x1b[32mSprawdzam plik konfiguracyjny\x1b[0m")) > 20)


class FakeVolTab:
    def __init__(self):
        self._output_volume = deque()
        for meth in ('_note_output_volume', 'recent_output_chars'):
            setattr(self, meth, getattr(AgentTab, meth).__get__(self))


vt = FakeVolTab()
for _ in range(10):
    vt._note_output_volume(80)
check("licznik sumuje znaki z okna", vt.recent_output_chars() == 800,
      f"policzono {vt.recent_output_chars()}")
check("kolejka nie rośnie w nieskończoność (przycinana do okna)",
      len(vt._output_volume) == 10)

# ============================================================================
# 11. STAN TURY NA PRAWDZIWYM DZIENNIKU (fixture zdjęty z sesji CRM usera)
# ============================================================================
# Kształt wpisów bierzemy z produkcji, nie z pamięci: `tool_use(AskUserQuestion)`
# → `tool_result` → `thinking` → `text`, plus wpisy księgowe, które Claude Code
# dopisuje PO turze (`system/turn_duration`, `last-prompt`, `ai-title`, `mode`,
# `permission-mode`). To one przesądzają, czy bezczynny agent nie wygląda na
# wiecznie zajętego.
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fixtures', 'crm-turn-states.jsonl')


def _rows():
    with open(FIXTURE, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


class FileReader(TranscriptReader):
    """Czytnik wpięty w konkretny plik (bez katalogu ~/.claude/projects)."""

    def __init__(self, path):
        self._projects_base = None
        self._project_dir = None
        self._session_file = path
        self._offset = 0
        self._pinned_session_id = None
        self._api_errors = []
        self._wait_last_size = -1
        self._wait_stable = 0

    def _ensure_session(self):
        return


def snapshot_of(rows, tmp_path):
    with open(tmp_path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    return FileReader(tmp_path).turn_snapshot()


if not os.path.exists(FIXTURE):
    check("fixture z prawdziwego dziennika CRM istnieje", False, FIXTURE)
else:
    rows = _rows()
    tmp = os.path.join(os.path.dirname(FIXTURE), '_tmp-turn.jsonl')

    # (a) DOKŁADNY moment kliknięcia usera: tool_result + thinking, tekstu brak
    text, state = snapshot_of(rows[:4], tmp)
    check("przypadek usera (11:20:43): agent WINIEN odpowiedź",
          state == TURN_OWES_TEXT, f"stan={state}")
    check("…a w dzienniku leży wtedy PRZEDOSTATNIA wypowiedź",
          text is not None and "Stan potwierdzony" in text, f"tekst={str(text)[:60]!r}")

    # (b) po dojściu nowej wypowiedzi tura się „zeruje"
    text, state = snapshot_of(rows[:5], tmp)
    check("po dopisaniu nowej wypowiedzi → agent nic nie jest winien",
          state == TURN_IDLE, f"stan={state}")
    check("…i to ona jest do przeczytania",
          text is not None and "Świetnie" in text, f"tekst={str(text)[:60]!r}")

    # (c) wpisy księgowe po turze NIE mogą udawać pracy
    text, state = snapshot_of(rows[:10], tmp)
    check("wpisy księgowe (system/last-prompt/ai-title/mode) nie blokują odczytu",
          state == TURN_IDLE, f"stan={state}")

    # (d) uruchomione narzędzie bez wyniku = nic nie nadchodzi zaraz
    text, state = snapshot_of(rows[:2], tmp)
    check("pytanie AskUserQuestion bez odpowiedzi → narzędzie w toku",
          state == TURN_TOOL_PENDING, f"stan={state}")

    # (e) pod-agent (isSidechain) prowadzi własną turę — dla nas niewidoczny
    text, state = snapshot_of(rows[:5] + [r for r in rows if r.get('isSidechain')], tmp)
    check("wypowiedź pod-agenta nie zmienia stanu naszej tury (kontrola negatywna)",
          state == TURN_IDLE and text is not None and "Świetnie" in text,
          f"stan={state} tekst={str(text)[:40]!r}")

    # (f) kontrola negatywna testu: gdyby reguła nie działała, (a) i (d) byłyby
    #     tym samym stanem — sprawdzamy, że test w ogóle coś ROZRÓŻNIA
    _, s_owed = snapshot_of(rows[:4], tmp)
    _, s_tool = snapshot_of(rows[:2], tmp)
    _, s_idle = snapshot_of(rows[:5], tmp)
    check("trzy różne sytuacje dają TRZY różne stany (kontrola negatywna testu)",
          len({s_owed, s_tool, s_idle}) == 3, f"{s_owed} / {s_tool} / {s_idle}")

    if os.path.exists(tmp):
        os.remove(tmp)

print(f"\nWynik: {PASS} OK / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
