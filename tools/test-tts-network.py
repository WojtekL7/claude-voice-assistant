#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bramka: LEKTOR PRZY ZERWANEJ SIECI (zgloszenie 2026-10-14).

URUCHOMIENIE:
  env -u LD_LIBRARY_PATH -u QT_PLUGIN_PATH QT_QPA_PLATFORM=offscreen \
      venv/bin/python -B tools/test-tts-network.py

ZGLOSZENIE: klik 🔊 w zakladce „Strona Domy", czytanie urwalo sie w polowie
(„…odmowi jej spakowania"). ZMIERZONE: do lektora poszla CALA wypowiedz
(2250 zn.), o 15:28:55 Wi-Fi zerwalo sie na 3 s, a silnik w TEJ SAMEJ SEKUNDZIE
odrzucil 11 pozostalych zdan (2 proby po ulamku sekundy — bez sieci kazda
pada natychmiast) i zamilkl bez slowa, bo jego `on_error` nie byl podlaczony.

CO PILNUJE:
  A. klasyfikacja bledow: brak sieci vs odmowa serwera / brak dzwieku / limit czasu
  B. ⭐ krotka przerwa sieci → WSZYSTKIE zdania przeczytane, w kolejnosci, bez pominiec
  C. dluga przerwa → czytanie przerwane JAWNIE: jeden sygnal, reszta kolejki zdjeta,
     czas ~TTS_NET_WAIT_SECS (a nie wielokrotnosc na kazde zdanie)
  D. kontrola odwrotna: zle ZDANIE (NoAudioReceived) dalej pomijane po 2 probach,
     reszta czytana, bez czekania i bez sygnalu o sieci
  E. „Stop" w trakcie czekania na siec dziala od razu i nie straszy oknem
  F. okno w GUI: podlaczone, z liczba sekund, niemodalne, dlawione; parytet PL/EN

Generowanie dzwieku jest PODMIENIONE (`_async_generate`) — bramka nie dotyka
sieci ani glosnikow. Petle `_gen_loop`/`_generate_audio` sa PRODUKCYJNE.
"""
import asyncio
import os
import queue
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

_ATRAPA_HOME = tempfile.mkdtemp(prefix="cva-test-tts-siec-")
os.environ["HOME"] = _ATRAPA_HOME

KORZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORZEN / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
_APP = QApplication.instance() or QApplication([])

import aiohttp  # noqa: E402
from aiohttp.client_reqrep import ConnectionKey  # noqa: E402
from edge_tts.exceptions import NoAudioReceived  # noqa: E402

import config  # noqa: E402
from core import tts_engine as te  # noqa: E402

WYKONANE = 0
PADLE = 0


def sprawdz(opis, funkcja):
    """Kazde sprawdzenie w oslonie — bramka ma ORZEKAC, nie padac."""
    global WYKONANE, PADLE
    WYKONANE += 1
    try:
        ok, szczegol = funkcja()
    except Exception as e:
        ok, szczegol = False, f"WYJATEK {type(e).__name__}: {e}"
    if ok:
        print(f"[OK] {opis}" + (f" — {szczegol}" if szczegol else ""))
    else:
        PADLE += 1
        print(f"[FAIL] {opis} — {szczegol}")


def blad_dns():
    """Dokladnie ten blad, ktory stoi w tts.log z 2026-10-14 15:28:55."""
    k = ConnectionKey("speech.platform.bing.com", 443, True, None, None, None, None)
    return aiohttp.ClientConnectorDNSError(
        k, socket.gaierror(-3, "Temporary failure in name resolution"))


# Czasy skrocone, zeby bramka trwala sekundy — PROPORCJE jak w produkcji.
te.TTS_NET_WAIT_SECS = 1.2
te.TTS_NET_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4)
ZDANIA = [f"Zdanie numer {i}." for i in range(1, 13)]


def przebieg(awaria, zdania=ZDANIA, stop_po=None):
    """Puszcza PRODUKCYJNY _gen_loop na kolejce zdan; zwraca (pobrane, sygnaly, czas, kolejka).

    `awaria(zdanie, nr_proby)` → wyjatek do rzucenia albo None (sukces).
    `stop_po` → po tylu sekundach klikamy „Stop" (event sesji).
    """
    eng = te.TTSEngine()
    proby = {}
    ostatnia = [time.monotonic()]

    async def falszywe(text, path):
        ostatnia[0] = time.monotonic()
        proby[text] = proby.get(text, 0) + 1
        e = awaria(text, proby[text])
        if e is not None:
            raise e
        with open(path, "wb") as f:
            f.write(b"mp3")

    eng._async_generate = falszywe
    sygnaly = []
    eng.on_network_lost = lambda secs: sygnaly.append(secs)

    stop = threading.Event()
    pending, ready = queue.Queue(), queue.Queue()
    for z in zdania:
        pending.put(z)
    t0 = time.monotonic()
    w = threading.Thread(target=eng._gen_loop, args=(stop, pending, ready), daemon=True)
    w.start()
    pobrane = []
    while time.monotonic() - t0 < 10:
        if stop_po is not None and time.monotonic() - t0 >= stop_po:
            stop.set()
            break
        try:
            zdanie, path = ready.get(timeout=0.05)
            pobrane.append(zdanie)
            eng._safe_remove(path)
        except queue.Empty:
            # Koniec = kolejka pusta i generator CICHY dluzej niz najdluzszy
            # odstep miedzy probami (inaczej zle zdanie, ktorego nigdy nie
            # bedzie w `ready`, trzymaloby bramke do limitu 10 s).
            cisza = time.monotonic() - ostatnia[0]
            if pending.empty() and ready.empty() and cisza > max(te.TTS_NET_RETRY_DELAYS) + 0.2:
                break
    czas = time.monotonic() - t0
    stop.set()
    t_stop = time.monotonic()
    w.join(timeout=5)
    # Ile trwalo, zanim generator NAPRAWDE stanal po „Stop” (sekcja E).
    eng.czas_zatrzymania = time.monotonic() - t_stop
    return pobrane, sygnaly, czas, pending, proby, eng


def log():
    p = Path(_ATRAPA_HOME) / ".vibe-coding-assistant" / "tts.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ------------------------------------------------------- A. klasyfikacja
def a(exc, oczekiwane):
    def f():
        w = te.is_network_error(exc)
        return w is oczekiwane, f"{type(exc).__name__} → siec={w}"
    return f


sprawdz("A1 blad DNS z logu 2026-10-14 = brak sieci", a(blad_dns(), True))
sprawdz("A2 socket.gaierror = brak sieci", a(socket.gaierror(-3, "x"), True))
sprawdz("A3 zerwane polaczenie = brak sieci", a(ConnectionResetError(), True))
sprawdz("A4 serwer rozlaczyl = brak sieci", a(aiohttp.ServerDisconnectedError(), True))
sprawdz("A5 odmowa 403 (WSServerHandshakeError) NIE jest siecia",
        a(aiohttp.WSServerHandshakeError(None, (), status=403), False))
sprawdz("A6 limit czasu NIE jest siecia (TimeoutError to podklasa OSError!)",
        a(asyncio.TimeoutError(), False))
sprawdz("A7 brak dzwieku w odpowiedzi NIE jest siecia", a(NoAudioReceived("x"), False))
sprawdz("A8 dowolny inny blad NIE jest siecia", a(ValueError("x"), False))

# ----------------------------------------------- B. krotka przerwa sieci
# Odtworzenie zdarzenia: siec pada w trakcie 3. zdania i wraca po ~0,4 s
# (w produkcji 3 s przy limicie 30 s — te same proporcje: przerwa << limit).
_b_start = {}


def awaria_krotka(text, nr):
    if text == ZDANIA[2]:
        _b_start.setdefault("t", time.monotonic())
    if "t" in _b_start and time.monotonic() - _b_start["t"] < 0.4:
        return blad_dns()
    return None


B = przebieg(awaria_krotka)
sprawdz("B1 krotka przerwa: przeczytane WSZYSTKIE 12 zdan",
        lambda: (len(B[0]) == 12, f"pobrane={len(B[0])}/12"))
sprawdz("B2 kolejnosc zachowana (czytamy dalej OD TEGO SAMEGO zdania)",
        lambda: (B[0] == ZDANIA, f"pierwsze 4: {B[0][:4]}"))
sprawdz("B3 zadnego sygnalu „przerwano”",
        lambda: (B[1] == [], f"sygnaly={B[1]}"))
sprawdz("B4 zdanie 3 bylo ponawiane wiecej niz 2 razy (proby sieci nie zuzywaja limitu)",
        lambda: (B[4].get(ZDANIA[2], 0) > te.TTS_GEN_ATTEMPTS, f"proby={B[4].get(ZDANIA[2])}"))
sprawdz("B5 log mowi, ze siec wrocila",
        lambda: ("siec wrocila" in log(), "brak wpisu" if "siec wrocila" not in log() else ""))

# ------------------------------------------------- C. dluga przerwa sieci
C = przebieg(lambda text, nr: blad_dns() if text not in ZDANIA[:2] else None)
sprawdz("C1 dluga przerwa: przeczytane tylko zdania sprzed awarii",
        lambda: (C[0] == ZDANIA[:2], f"pobrane={C[0]}"))
sprawdz("C2 DOKLADNIE jeden sygnal „przerwano”, z liczba sekund >= limitu",
        lambda: (len(C[1]) == 1 and C[1][0] >= te.TTS_NET_WAIT_SECS, f"sygnaly={C[1]}"))
sprawdz("C3 reszta kolejki zdjeta (nic nie mieli sie po cichu)",
        lambda: (C[3].empty(), f"zostalo={C[3].qsize()}"))
sprawdz("C4 pozostale zdania NIE byly nawet probowane (czekamy raz, nie 10x)",
        lambda: (all(z not in C[4] for z in ZDANIA[3:]), f"probowane={sorted(C[4])}"))
sprawdz("C5 czas ~ jednego limitu, nie wielokrotnosc",
        lambda: (te.TTS_NET_WAIT_SECS <= C[2] < te.TTS_NET_WAIT_SECS * 2.5, f"{C[2]:.2f}s"))
sprawdz("C6 log mowi, ile zdan nie przeczytano",
        lambda: ("nieprzeczytanych zdan: 10" in log(), log().splitlines()[-1][:120] if log() else "pusty"))

# ------------------------------------- D. kontrola odwrotna: zle ZDANIE
D = przebieg(lambda text, nr: NoAudioReceived("No audio was received.") if text == ZDANIA[2] else None)
sprawdz("D1 zle zdanie pominiete, pozostale 11 przeczytane",
        lambda: (D[0] == ZDANIA[:2] + ZDANIA[3:], f"pobrane={len(D[0])}"))
sprawdz("D2 zle zdanie probowane dokladnie TTS_GEN_ATTEMPTS razy",
        lambda: (D[4].get(ZDANIA[2]) == te.TTS_GEN_ATTEMPTS, f"proby={D[4].get(ZDANIA[2])}"))
sprawdz("D3 bez sygnalu o sieci i bez czekania",
        lambda: (D[1] == [] and D[2] < te.TTS_NET_WAIT_SECS, f"sygnaly={D[1]} czas={D[2]:.2f}s"))

# ----------------------------------------- E. Stop w trakcie czekania
# Dlugi odstep miedzy probami (2 s), zeby bylo widac, czy Stop PRZERYWA czekanie,
# czy tylko czeka na jego koniec. Mierzymy czas od Stop do zatrzymania watku —
# nie chwile klikniecia (pierwsza wersja mierzyla klikniecie i przepuscila
# czekanie przez sleep: sabotaz S7).
_stare = te.TTS_NET_RETRY_DELAYS, te.TTS_NET_WAIT_SECS
te.TTS_NET_RETRY_DELAYS, te.TTS_NET_WAIT_SECS = (2.0,), 5.0
try:
    E = przebieg(lambda text, nr: blad_dns(), stop_po=0.25)
finally:
    te.TTS_NET_RETRY_DELAYS, te.TTS_NET_WAIT_SECS = _stare
sprawdz("E1 Stop podczas czekania na siec: bez okna „przerwano”",
        lambda: (E[1] == [], f"sygnaly={E[1]}"))
sprawdz("E2 Stop przerywa czekanie od razu (watek staje < 0,5 s przy odstepie 2 s)",
        lambda: (E[5].czas_zatrzymania < 0.5, f"{E[5].czas_zatrzymania:.2f}s"))

# ------------------------------------------------------------- F. GUI
from gui import main_window as mw  # noqa: E402

ZRODLO = Path(mw.__file__).read_text(encoding="utf-8")
sprawdz("F1 silnik podlaczony do okna (on_network_lost → sygnal → obsluga)",
        lambda: (all(s in ZRODLO for s in (
            "self.tts.on_network_lost =",
            "tts_network_lost = pyqtSignal(float)",
            "tts_network_lost.connect(self._on_tts_network_lost)")), ""))


class _Okno(QWidget):
    pass


def f2():
    w = _Okno()
    mw.MainWindow._on_tts_network_lost(w, 30.4)
    okno = getattr(w, "_tts_net_dialog", None)
    if okno is None:
        return False, "okno nie powstalo"
    tekst = okno.text()
    ok = "30" in tekst and okno.windowModality() == Qt.NonModal and okno.isVisible()
    pierwsze = okno
    mw.MainWindow._on_tts_network_lost(w, 31.0)
    ok = ok and w._tts_net_dialog is pierwsze
    okno.close()
    return ok, f"tekst={tekst[:60]!r} niemodalne={okno.windowModality() == Qt.NonModal} dlawione={w._tts_net_dialog is pierwsze}"


sprawdz("F2 okno: liczba sekund w tresci, niemodalne, drugie w 5 min dlawione", f2)


def f3():
    braki = []
    for jezyk in config.UI_TRANSLATIONS:
        slownik = config.UI_TRANSLATIONS[jezyk]
        for k in ("dlg_tts_net_lost_title", "dlg_tts_net_lost_msg"):
            if k not in slownik:
                braki.append(f"{jezyk}:{k}")
        if "{secs}" not in slownik.get("dlg_tts_net_lost_msg", ""):
            braki.append(f"{jezyk}:brak {{secs}}")
    return not braki, ", ".join(braki)


sprawdz("F3 parytet PL/EN tresci okna (z miejscem na liczbe sekund)", f3)

print(f"\nPODSUMOWANIE: wykonane={WYKONANE} padle={PADLE}")
sys.exit(1 if PADLE else 0)
