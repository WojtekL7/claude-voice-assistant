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
    def __init__(self, idle_secs, stream_chars=0):
        self._last_terminal_data_ts = time.monotonic() - idle_secs
        self._stream_chars = stream_chars

    def recent_output_chars(self, window_secs=None):
        """Ile znaków treści przyszło w ostatnim oknie (czujnik strumienia)."""
        return self._stream_chars


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
        self._read_wait_hard_deadline = time.monotonic() + 20.0
        self._read_wait_started = time.monotonic()
        for meth in ('_agent_is_writing', '_agent_is_streaming', '_speak_journal_text',
                     '_cancel_read_last_wait', '_check_read_last_wait',
                     '_read_last_debug'):
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
        self._read_wait_hard_deadline = 0.0
        self._read_wait_started = 0.0
        for meth in ('_agent_is_writing', '_agent_is_streaming', '_speak_journal_text',
                     '_cancel_read_last_wait', '_check_read_last_wait',
                     '_start_read_last_wait', '_read_last_debug'):
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

# ============================================================================
# NAPRAWA 2026-07-23 — zgłoszenie usera: „w CRM DALEJ czyta przedostatnią"
# ============================================================================
# 7. Okno strażnika musi być SZERSZE niż zmierzone opóźnienie zapisu (1–3 s).
#    Przy dawnym progu 2,0 s klik 2,5 s po dokończeniu odpowiedzi trafiał
#    w szczelinę: terminal już milczał, a wpis jeszcze nie doszedł → apka
#    czytała przedostatnią. To jest test regresyjny DOKŁADNIE na ten objaw.
w = FakeWindow(None, None, None)
check("2,5 s po ostatnim ruchu wciąż CZEKAMY (wpis bywa w drodze do 3 s)",
      w._agent_is_writing(FakeTab(idle_secs=2.5)) is True,
      "to jest szczelina, w którą wpadał user")
check("3,0 s po ostatnim ruchu też czekamy (górna granica pomiaru)",
      w._agent_is_writing(FakeTab(idle_secs=3.0)) is True)
check("ale po 5 s ciszy czytamy od razu (kontrola negatywna — brak zwłoki)",
      w._agent_is_writing(FakeTab(idle_secs=5.0)) is False)

# 8. Czujnik strumienia: odróżnia „sypie tekstem" od „miga paskiem stanu".
check("dużo znaków w oknie = agent sypie tekstem",
      w._agent_is_streaming(FakeTab(0.1, stream_chars=600)) is True)
check("kilkadziesiąt znaków = tylko animacja paska (kontrola negatywna)",
      w._agent_is_streaming(FakeTab(0.1, stream_chars=60)) is False)
check("brak zakładki = brak strumienia", w._agent_is_streaming(None) is False)

# 9. Dopóki leci strumień, karencja jest PRZESUWANA — długa wypowiedź
#    (14–16 s pisania) ma być doczekana w całości, nie ucięta bezpiecznikiem.
tab = FakeTab(0.1, stream_chars=600)               # agent w trakcie pisania
reader = FakeReader(["STARA odpowiedź"])           # dziennik jeszcze się nie zmienił
w = FakeWindow(tab, reader, before="STARA odpowiedź", deadline_in=0.05)
w._check_read_last_wait()
check("strumień przesuwa karencję — nic nie czytamy przedwcześnie",
      w.tts.spoken == [], f"powiedziano: {w.tts.spoken}")
check("i czekanie trwa dalej", w._read_wait_timer is not None)
check("karencja realnie przesunięta w przyszłość",
      w._read_wait_deadline > time.monotonic() + 1.0)

# 10. Gdy strumienia NIE MA (pracuje narzędzie), karencja mija i czytamy to,
#     co jest — bez zawieszania przycisku na cały bezpiecznik.
tab = FakeTab(0.1, stream_chars=0)                 # terminal żyje, ale to nie tekst
reader = FakeReader(["OSTATNIA notka"])
w = FakeWindow(tab, reader, before="OSTATNIA notka", deadline_in=-0.1)
w._check_read_last_wait()
check("bez strumienia karencja mija i czytamy najnowszą z dziennika",
      len(w.tts.spoken) == 1 and "OSTATNIA" in w.tts.spoken[0],
      f"powiedziano: {w.tts.spoken}")
check("czekanie zakończone (przycisk nie wisi do bezpiecznika)",
      w._read_wait_timer is None)

# 11. Twardy bezpiecznik ogranicza przesuwanie — nawet ciągły strumień
#     nie może czekać w nieskończoność.
tab = FakeTab(0.1, stream_chars=600)
reader = FakeReader(["STARA"])
w = FakeWindow(tab, reader, before="STARA", deadline_in=0.05)
w._read_wait_hard_deadline = time.monotonic() + 0.5   # bezpiecznik tuż-tuż
w._check_read_last_wait()
check("karencja nie przeskakuje twardego bezpiecznika",
      w._read_wait_deadline <= w._read_wait_hard_deadline + 0.01,
      f"karencja={w._read_wait_deadline:.2f} bezpiecznik={w._read_wait_hard_deadline:.2f}")

# 12. Czujnik po stronie ZAKŁADKI (liczenie znaków) — bez budowania widżetu.
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
    vt._note_output_volume(80)                 # 800 znaków w oknie
check("licznik sumuje znaki z okna", vt.recent_output_chars() == 800,
      f"policzono {vt.recent_output_chars()}")
check("kolejka nie rośnie w nieskończoność (przycinana do okna)",
      len(vt._output_volume) == 10)
vt2 = FakeVolTab()
vt2._note_output_volume(40)
check("pojedyncza ramka paska stanu daje mało (kontrola negatywna)",
      vt2.recent_output_chars() == 40)

print(f"\nWynik: {PASS} OK / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
