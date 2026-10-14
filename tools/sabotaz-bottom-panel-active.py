#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabotaż bramki tools/test-bottom-panel-active.py — czy bramka WYKRYWA zepsucie.

URUCHOMIENIE:  venv/bin/python -B tools/sabotaz-bottom-panel-active.py

Każdy wariant psuje JEDNĄ rzecz w main_window.py, puszcza bramkę i przywraca
plik (kontrola sha256). Wariant musi zapalić co najmniej jedną asercję przy
tej samej liczbie WYKONANYCH co na zdrowym kodzie.

⚠️ Poza zasięgiem bramki: wywołanie w `apply_skin_colors` (bramka nie buduje
całego okna). Pilnuje go tylko przegląd kodu.

WYNIKI ZMIERZONE 2026-10-14 (zdrowy kod: wykonane=10 padle=0):
  S1 2 · S2 3 · S3 4 · S4 4 · S5 1 — 5/5 wykrytych, wykonane=10 w każdym.
  S4 (stan sprzed poprawki) zapala asercję 5 = dokładnie objaw ze zrzutu.
"""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
MW = KORZEN / "src/gui/main_window.py"

# Wariant = lista podmian (stare, nowe) robionych razem.
_S1 = ("            # Kolor panelu według stanu okna (patrz _paint_bottom_panels).\n            self._paint_bottom_panels()\n", "")
_S4 = ("            nieaktywny = panel is getattr(self, 'bottom_panel', None) and not okno_aktywne\n",
          "            if panel is not getattr(self, 'bottom_panel', None):\n                continue\n"
          "            nieaktywny = not okno_aktywne\n")
WARIANTY = {
    "S1 zmiana zakładki nie maluje panelu": [_S1],
    "S2 aktywacja okna nie maluje panelu":
        [("                        pass\n            self._paint_bottom_panels()\n", "                        pass\n")],
    "S3 kolor bez względu na stan okna":
        [("        okno_aktywne = self.isActiveWindow()\n", "        okno_aktywne = True\n")],
    # ⚠️ SAMO „maluj tylko bieżący panel" (bez S1) NIE jest błędem: przy każdej
    # zmianie zakładki bieżący panel i tak jest przemalowany — to równoważna
    # naprawa, bramka słusznie ją przepuszcza (zmierzone 2026-10-14: padle=0).
    # Stan sprzed poprawki to DOPIERO oba braki naraz:
    "S4 STAN SPRZED POPRAWKI (tylko bieżący panel + zmiana zakładki bez malowania)": [_S1, _S4],
    "S5 pamięć podręczna ignoruje force (po zmianie skórki)":
        [("            if not force and panel.property('_vca_panel_bg') == bg:",
          "            if panel.property('_vca_panel_bg') == bg:")],
}

ENV = {k: v for k, v in os.environ.items()
       if k not in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "CLAUDE_CODE_SUBAGENT_MODEL")}
ENV["QT_QPA_PLATFORM"] = "offscreen"


def bramka():
    r = subprocess.run([sys.executable, "-B", str(KORZEN / "tools/test-bottom-panel-active.py")],
                       cwd=KORZEN, env=ENV, capture_output=True, text=True, timeout=180)
    m = re.search(r"PODSUMOWANIE: wykonane=(\d+) padle=(\d+)", r.stdout)
    padle = [l.split("  (")[0][7:] for l in r.stdout.splitlines() if l.startswith("[FAIL]")]
    return (int(m.group(1)), int(m.group(2))) if m else (None, None), padle


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


(wyk0, pad0), _ = bramka()
print(f"ZDROWY KOD: wykonane={wyk0} padle={pad0}")
if pad0 != 0:
    sys.exit("Bramka czerwona na zdrowym kodzie — sabotaż nie ma sensu.")

nie_wykryte = 0
for nazwa, podmiany in WARIANTY.items():
    oryginal = MW.read_bytes()
    odcisk = sha(MW)
    tekst = oryginal.decode("utf-8")
    martwe = [n for n, (stare, _) in enumerate(podmiany) if tekst.count(stare) != 1]
    if martwe:
        print(f"[KOTWICA] {nazwa}: kotwice nr {martwe} nie występują dokładnie raz — wariant MARTWY")
        nie_wykryte += 1
        continue
    for stare, nowe in podmiany:
        tekst = tekst.replace(stare, nowe)
    try:
        MW.write_text(tekst, encoding="utf-8")
        (wyk, pad), padle = bramka()
    finally:
        MW.write_bytes(oryginal)
    assert sha(MW) == odcisk, "main_window.py NIE przywrócony!"
    ok = pad and wyk == wyk0
    if not ok:
        nie_wykryte += 1
    print(f"[{'WYKRYTY' if ok else 'NIE WYKRYTY'}] {nazwa}: padle={pad} wykonane={wyk}"
          + (f" ({'; '.join(padle)})" if padle else ""))

print(f"\nSABOTAŻ: wariantów={len(WARIANTY)} niewykrytych={nie_wykryte}")
sys.exit(1 if nie_wykryte else 0)
