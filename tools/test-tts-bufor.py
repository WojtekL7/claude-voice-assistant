#!/usr/bin/env python3
"""Bramka: lektor NIE MOŻE startować z domyślnym buforem dźwięku.

Uruchom:  python3 tools/test-tts-bufor.py

Dlaczego to jest osobna bramka, a nie komentarz w kodzie:
`pygame.mixer.init()` bez parametrów wygląda niewinnie i kusi, żeby „uprościć".
Zmierzone 2026-07-26: taki init negocjuje z PipeWire bufor 128 próbek (2,7 ms),
a PipeWire ustawia CAŁĄ kartę dźwiękową na najmniejszy bufor zażądany przez
kogokolwiek. Nasz strumień jest otwarty przez cały czas życia aplikacji, więc
skutkiem było trzeszczenie KAŻDEGO dźwięku w systemie (przeglądarka, filmy),
dopóki apka działała. Cofnięcie tej poprawki wróci z tym objawem.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

_passed = _failed = 0


def check(name, ok, detail=""):
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"[OK]   {name}")
    else:
        _failed += 1
        print(f"[FAIL] {name}  {detail}")


SRC = ROOT / "src" / "core" / "tts_engine.py"
tree = ast.parse(SRC.read_text(encoding="utf-8"))

# --- 1. stałe formatu istnieją i mają sensowne wartości -------------------
from core import tts_engine as te  # noqa: E402

check("stała MIXER_BUFFER istnieje", hasattr(te, "MIXER_BUFFER"))
check("bufor jest DUŻY (≥2048 próbek)", getattr(te, "MIXER_BUFFER", 0) >= 2048,
      f"jest {getattr(te, 'MIXER_BUFFER', None)} — 128 dawało trzeszczenie w całym systemie")
check("częstotliwość = 24 kHz (natywna dla edge-tts, bez przepróbkowania)",
      getattr(te, "MIXER_FREQUENCY", None) == 24000)
check("mowa jest mono", getattr(te, "MIXER_CHANNELS", None) == 1)

# --- 2. pierwsze wywołanie init() MUSI mieć parametry ---------------------
inits = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    f = node.func
    if isinstance(f, ast.Attribute) and f.attr == "init" and \
       isinstance(f.value, ast.Attribute) and f.value.attr == "mixer":
        inits.append(node)

check("w kodzie jest wywołanie pygame.mixer.init()", len(inits) >= 1)
z_parametrami = [c for c in inits if c.keywords or c.args]
check("PIERWSZY init ma jawne parametry (nie domyślne)",
      bool(z_parametrami), "goły init() = bufor 128 = trzeszczenie")
uzyte = {kw.arg for c in z_parametrami for kw in c.keywords}
check("init dostaje 'buffer'", "buffer" in uzyte, sorted(uzyte))
check("init dostaje 'frequency' i 'channels'",
      {"frequency", "channels"} <= uzyte, sorted(uzyte))
check("zostaje wariant awaryjny (goły init) na wypadek odmowy sterownika",
      len(inits) >= 2, "bez fallbacku brak dźwięku na nietypowym sprzęcie")

# --- 3. sprawdzenie na żywym mikserze (gdy jest karta dźwiękowa) ----------
try:
    import pygame
    pygame.mixer.quit()
    pygame.mixer.init(frequency=te.MIXER_FREQUENCY, size=te.MIXER_SIZE,
                      channels=te.MIXER_CHANNELS, buffer=te.MIXER_BUFFER)
    got = pygame.mixer.get_init()
    pygame.mixer.quit()
    check("mikser realnie startuje w zadanym formacie",
          got == (te.MIXER_FREQUENCY, te.MIXER_SIZE, te.MIXER_CHANNELS), got)
except Exception as e:
    print(f"[   ] pominięto test na żywym mikserze (brak karty dźwiękowej): {e}")

print(f"\n=== {_passed} OK / {_failed} FAIL ===")
sys.exit(1 if _failed else 0)
