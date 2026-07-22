#!/usr/bin/env python3
"""Test: 🔊 „czytaj ostatnią" czeka na dokończenie wypowiedzi.

Bug (zgłoszenie usera 2026-07-22): przycisk czytał PRZEDOSTATNIĄ wypowiedź
„mniej więcej w 50%". Przyczyna zmierzona na żywym dzienniku: Claude Code
dopisuje wypowiedź do pliku sesji DOPIERO po jej dokończeniu (13,9 / 14,8 /
16,2 s dla odpowiedzi 1,7–2,4 tys. znaków), a na ekranie widać ją od razu →
klik w tym oknie czytał to, co jeszcze leżało w pliku, czyli poprzednią.

Testujemy DECYZJĘ (czekać czy czytać) bez okna GUI: metody MainWindow
wołamy na atrapie obiektu. Każdy test ma kontrolę negatywną — inaczej
komplet zielonych niczego by nie dowodził.

Uruchomienie:  python3 tools/test-read-last-wait.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from gui.main_window import MainWindow  # noqa: E402

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
    def __init__(self, idle_secs):
        self._last_terminal_data_ts = time.monotonic() - idle_secs


class FakeReader:
    """Dziennik sesji: kolejne odczyty zwracają kolejne wartości."""

    def __init__(self, values):
        self._values = list(values)
        self.seek_calls = 0

    def last_response(self):
        return self._values[0] if len(self._values) == 1 else self._values.pop(0)

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


class FakeWindow:
    """Atrapa MainWindow z podpiętymi PRAWDZIWYMI metodami z produkcji."""

    def __init__(self, tab, reader, before, deadline_in=30.0):
        self.tts = FakeTts()
        self.statuses = []
        self._current_tab = tab
        self._read_wait_timer = FakeTimer()
        self._read_wait_tab = tab
        self._read_wait_reader = reader
        self._read_wait_before = before
        self._read_wait_deadline = time.monotonic() + deadline_in
        for meth in ('_agent_is_writing', '_speak_journal_text',
                     '_cancel_read_last_wait', '_check_read_last_wait'):
            setattr(self, meth, getattr(MainWindow, meth).__get__(self))

    def _get_current_agent_tab(self):
        return self._current_tab

    def _update_status(self, text):
        self.statuses.append(text)


# ---------------------------------------------------------------- 1. czujnik
w = FakeWindow(None, None, None)
check("agent PISZE, gdy terminal ruszał się przed chwilą",
      w._agent_is_writing(FakeTab(idle_secs=0.2)) is True)
check("agent NIE pisze, gdy terminal milczy dłużej niż próg (kontrola negatywna)",
      w._agent_is_writing(FakeTab(idle_secs=5.0)) is False)
check("brak zakładki = nie pisze", w._agent_is_writing(None) is False)

# ------------------------------------------- 2. nowa wypowiedź kończy czekanie
tab = FakeTab(0.2)
reader = FakeReader(["STARA odpowiedź", "STARA odpowiedź", "NOWA odpowiedź"])
w = FakeWindow(tab, reader, before="STARA odpowiedź")
w._check_read_last_wait()                      # dziennik wciąż stary
check("czeka, dopóki w dzienniku leży STARA wypowiedź", w.tts.spoken == [],
      f"powiedziano: {w.tts.spoken}")
w._check_read_last_wait()                      # nadal stary
check("dalej czeka przy kolejnym sprawdzeniu", w.tts.spoken == [])
w._check_read_last_wait()                      # doszła nowa
check("po dojściu NOWEJ — czyta właśnie ją",
      len(w.tts.spoken) == 1 and "NOWA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")
check("NIE przeczytał starej (sedno buga)",
      all("STARA" not in s for s in w.tts.spoken))
check("czekanie zostało zatrzymane", w._read_wait_timer is None)
check("czytnik przesunięty na koniec = brak podwójnego czytania",
      reader.seek_calls == 1, f"seek_calls={reader.seek_calls}")

# ------------------------------------------------------ 3. bezpiecznik czasowy
tab = FakeTab(0.2)
reader = FakeReader(["STARA odpowiedź"])
w = FakeWindow(tab, reader, before="STARA odpowiedź", deadline_in=-1.0)
w._check_read_last_wait()
check("po upływie limitu czyta to, co jest (dawne zachowanie)",
      len(w.tts.spoken) == 1 and "STARA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")
check("i mówi o tym na pasku",
      any("pisze" in s or "writing" in s for s in w.statuses),
      f"statusy: {w.statuses}")

# --------------------------------------------- 4. zmiana zakładki przerywa cicho
tab = FakeTab(0.2)
reader = FakeReader(["STARA", "NOWA"])
w = FakeWindow(tab, reader, before="STARA")
w._current_tab = FakeTab(0.2)                  # user przeszedł do innej zakładki
w._check_read_last_wait()
check("po zmianie zakładki nic nie czyta", w.tts.spoken == [],
      f"powiedziano: {w.tts.spoken}")
check("i sprząta po sobie", w._read_wait_timer is None)

# --------------------------------------------------- 5. pusta proza nie „mówi"
reader = FakeReader(["```\nkod\n```"])
w = FakeWindow(FakeTab(0.2), reader, before=None)
spoke = w._speak_journal_text(reader, "```\nsam kod, zero prozy\n```")
check("sam blok kodu → nie czytamy (kontrola negatywna)",
      spoke is False and w.tts.spoken == [], f"powiedziano: {w.tts.spoken}")

# ------------------------------- 6. samo WEJŚCIE w oczekiwanie (ścieżka przycisku)
# py_compile nie łapie błędnej nazwy w niewykonanym kodzie, a to jest metoda,
# którą woła 🔊 — musi zostać naprawdę uruchomiona. QTimer(self) wymaga QObject,
# więc atrapa dziedziczy po QObject.
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
        self._read_wait_deadline = 0.0
        for meth in ('_agent_is_writing', '_speak_journal_text',
                     '_cancel_read_last_wait', '_check_read_last_wait',
                     '_start_read_last_wait'):
            setattr(self, meth, getattr(MainWindow, meth).__get__(self))

    def _get_current_agent_tab(self):
        return self._current_tab

    def _update_status(self, text):
        self.statuses.append(text)


tab = FakeTab(0.2)
qw = FakeQWindow(tab, FakeReader(["STARA"]))
qw._start_read_last_wait(tab, qw._read_wait_reader, "STARA")
check("przycisk potrafi wejść w tryb czekania (bez błędu nazw)",
      qw._read_wait_timer is not None and qw._read_wait_timer.isActive())
check("i od razu informuje na pasku, że czeka",
      any("czekam" in s.lower() or "waiting" in s.lower() for s in qw.statuses),
      f"statusy: {qw.statuses}")
qw._cancel_read_last_wait()
check("odwołanie czekania czyści stan", qw._read_wait_timer is None)

print(f"\nWynik: {PASS} OK / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
