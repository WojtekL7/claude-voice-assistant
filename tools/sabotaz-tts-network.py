#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabotaz bramki tools/test-tts-network.py — czy bramka WYKRYWA zepsucie.

URUCHOMIENIE:  venv/bin/python -B tools/sabotaz-tts-network.py

Kazdy wariant psuje JEDNA rzecz w kodzie produkcyjnym, puszcza bramke
i przywraca plik (kontrola sha256 po kazdym wariancie). Wariant musi zapalic
co najmniej jedna asercje, a liczba WYKONANYCH ma byc taka sama jak na zdrowym
kodzie (inaczej bramka sie urwala, zamiast orzec).

WYNIKI ZMIERZONE 2026-10-14 (zdrowy kod: wykonane=27 padle=0):
  S1 12 · S2 1 · S3 1 · S4 5 · S5 1 · S6 7 · S7 1 · S8 1 · S9 1 — 9/9 wykrytych,
  wykonane=27 w KAZDYM przebiegu.
  ⚠️ Pierwsza runda dala 7/9 i oba przeoczenia byly winą NARZEDZI, nie kodu:
  S3 (stary) usuwal wykluczenie odmow 403, ktore bylo MARTWE (w aiohttp odmowy
  nie sa ani OSError, ani bledem polaczenia) — wykluczenie skasowane z kodu,
  S3 psuje teraz realne miejsce (szerszy ClientError); S7 przechodzil, bo E2
  mierzyl chwile klikniecia Stop, a nie zatrzymanie watku — bramka poprawiona.
"""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
TTS = KORZEN / "src/core/tts_engine.py"
MW = KORZEN / "src/gui/main_window.py"

WARIANTY = {
    "S1 kazdy blad traktowany jak zle zdanie (stare zachowanie)":
        (TTS, "    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):\n        return False\n",
              "    return False\n"),
    "S2 limit czasu wziety za brak sieci":
        (TTS, "    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):\n        return False\n", ""),
    "S3 odmowa serwera (403) wzieta za brak sieci":
        (TTS, "        if isinstance(exc, aiohttp.ClientConnectionError):",
              "        if isinstance(exc, aiohttp.ClientError):"),
    "S4 po poddaniu sie reszta kolejki NIE zdjeta":
        (TTS, "left = self._drain_queue(pending)", "left = []"),
    "S5 brak sygnalu do okna":
        (TTS, "                        self.on_network_lost(e.waited)\n", "                        pass\n"),
    "S6 proby sieci zuzywaja limit prob zdania":
        (TTS, "                    net_tries += 1\n", "                    net_tries += 1\n                    attempt += 1\n"),
    "S7 czekanie przez sleep (Stop nie przerywa)":
        (TTS, "if stop_event.wait(min(delay, TTS_NET_WAIT_SECS - waited)):",
              "if time.sleep(min(delay, TTS_NET_WAIT_SECS - waited)) or stop_event.is_set():"),
    "S8 okno niepodlaczone do silnika":
        (MW, "        self.tts.on_network_lost = lambda secs: self.signals.tts_network_lost.emit(secs)\n", ""),
    "S9 okno modalne (blokuje prace)":
        (MW, "        okno.setWindowModality(Qt.NonModal)\n        # Referencja MUSI przeżyć wyjście z metody (inaczej okno znika od razu).\n",
             "        # Referencja MUSI przeżyć wyjście z metody (inaczej okno znika od razu).\n"),
}

ENV = {k: v for k, v in os.environ.items()
       if k not in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "CLAUDE_CODE_SUBAGENT_MODEL")}
ENV["QT_QPA_PLATFORM"] = "offscreen"


def bramka():
    r = subprocess.run([sys.executable, "-B", str(KORZEN / "tools/test-tts-network.py")],
                       cwd=KORZEN, env=ENV, capture_output=True, text=True, timeout=180)
    m = re.search(r"PODSUMOWANIE: wykonane=(\d+) padle=(\d+)", r.stdout)
    padle = [l for l in r.stdout.splitlines() if l.startswith("[FAIL]")]
    return (int(m.group(1)), int(m.group(2))) if m else (None, None), padle


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


(wyk0, pad0), _ = bramka()
print(f"ZDROWY KOD: wykonane={wyk0} padle={pad0}")
if pad0 != 0:
    sys.exit("Bramka czerwona na zdrowym kodzie — sabotaz nie ma sensu.")

nie_wykryte = 0
for nazwa, (plik, stare, nowe) in WARIANTY.items():
    oryginal = plik.read_bytes()
    odcisk = sha(plik)
    tekst = oryginal.decode("utf-8")
    if tekst.count(stare) != 1:
        print(f"[KOTWICA] {nazwa}: kotwica wystepuje {tekst.count(stare)}x — wariant MARTWY")
        nie_wykryte += 1
        continue
    try:
        plik.write_text(tekst.replace(stare, nowe), encoding="utf-8")
        (wyk, pad), padle = bramka()
    finally:
        plik.write_bytes(oryginal)
    assert sha(plik) == odcisk, f"plik {plik} NIE przywrocony!"
    ok = pad and wyk == wyk0
    if not ok:
        nie_wykryte += 1
    print(f"[{'WYKRYTY' if ok else 'NIE WYKRYTY'}] {nazwa}: padle={pad} wykonane={wyk}"
          + (f" ({', '.join(l.split(' — ')[0][7:] for l in padle)})" if padle else ""))

print(f"\nSABOTAZ: wariantow={len(WARIANTY)} niewykrytych={nie_wykryte}")
sys.exit(1 if nie_wykryte else 0)
