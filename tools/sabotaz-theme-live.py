#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sabotaż bramki tools/test-theme-live.py — czy bramka WYKRYWA zepsucie.

URUCHOMIENIE:  venv/bin/python -B tools/sabotaz-theme-live.py

Każdy wariant psuje JEDNĄ rzecz (czasem w kilku plikach naraz), puszcza bramkę
i przywraca pliki (kontrola sha256). Wariant musi zapalić co najmniej jedną
asercję przy tej samej liczbie WYKONANYCH co na zdrowym kodzie.

⚠️ Poza zasięgiem bramki (nie widać na zrzucie okna, więc nie da się zmierzyć):
  * menu rozwijane „+" (`_style_add_tab_menu`) — zamknięte w chwili zrzutu,
  * lampka „nowa wersja" — ukryta, gdy nie ma aktualizacji,
  * `resource_monitor.update()` — bramka sama odświeża wskaźnik przy
    normalizacji, a w programie i tak robi to jego zegar co 2,5 s,
  * suwak pola wpisywania — widoczny dopiero przy ≥6 liniach polecenia.
Tych pilnuje przegląd kodu (lista w MainWindow._apply_appearance).

WYNIKI ZMIERZONE 2026-10-20 (zdrowy kod: wykonane=24 padle=0):
  S1 3 · S2 3 · S3 2 · S4 2 · S5 3 · S6 4 · S7 3 · S8 3 · S9 4
  — 9/9 wykrytych, wykonane=24 w każdym (bramka nie urywa się w połowie).
"""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
SRC = KORZEN / "src"
MW = "gui/main_window.py"
TH = "gui/theme.py"

# Wariant = lista podmian (plik, stare, nowe) robionych razem.
WARIANTY = {
    "S1 pasek MCP nie przemalowany":
        [(MW, "            self.mcp_status_widget.apply_theme()\n", "            pass\n")],
    "S2 zakładka nie odświeża własnych elementów (lupa, tło)":
        [(MW, "            tab.refresh_theme()\n", "            pass\n")],
    "S3 powrót na ciemny nie przywraca palety":
        [(TH, "    globals().update(_LIGHT if mode == APPEARANCE_LIGHT else _DARK)\n",
              "    globals().update(_LIGHT if mode == APPEARANCE_LIGHT else {})\n")],
    "S4 przełącznik auto-czytania bez jasnej wersji":
        [(TH, "    path = str(path)\n    if not is_light():\n        return path\n    if checked:",
              "    path = str(path)\n    return path\n    if checked:")],
    # ⚠️ Pierwsza wersja wpisywała tu kolor NA SZTYWNO ('#9b93a8') i NIE
    # została wykryta — słusznie: psuła tak samo okno przełączone w locie i
    # okno uruchomione od razu, więc porównanie dwóch jednakowo zepsutych okien
    # nie ma czego znaleźć (zmierzone 2026-10-20). Prawdziwy stary błąd to
    # kolor zapamiętany PRZY IMPORCIE, czyli w trybie, w którym program wstał:
    "S5 domyślny kolor ikon zapamiętany przy imporcie (stary błąd)":
        [("gui/icon_set.py", "from gui import theme  # noqa: E402\n",
          "from gui import theme  # noqa: E402\n_IMPORT_COLOR = theme.TEXT_DIM\n"),
         ("gui/icon_set.py", "    color = color or theme.TEXT_DIM\n",
          "    color = color or _IMPORT_COLOR\n")],
    "S6 skórka nowego trybu nie wczytana (zostaje skórka poprzedniego)":
        [(MW, "        self.skin_colors = DEFAULT_SKIN_COLORS.copy()\n        if saved_skin and saved_version >= SKIN_VERSION:",
              "        if saved_skin and saved_version >= SKIN_VERSION:")],
    "S7 brak przemalowania okna (tylko paleta)":
        [(MW, "        self._apply_dark_theme()\n        # Ramka akcentu",
              "        pass\n        # Ramka akcentu")],
    "S8 Claude Code znów z motywem zwykłym (nie przełączy się w locie)":
        [("core/claude_hooks.py", '    return "dark-ansi"\n',
          '    return "light" if light_app else None\n')],
    "S9 przycisk ☀️/🌙 nie odświeża ikony/podpowiedzi":
        [(MW, "        self._refresh_appearance_button()\n\n        # Okno, zakładki",
              "        pass\n\n        # Okno, zakładki")],
}

ENV = {k: v for k, v in os.environ.items()
       if k not in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "CLAUDE_CODE_SUBAGENT_MODEL")}


def bramka():
    r = subprocess.run([sys.executable, "-B", str(KORZEN / "tools/test-theme-live.py")],
                       cwd=KORZEN, env=ENV, capture_output=True, text=True, timeout=900)
    m = re.search(r"WYNIK: (\d+) OK, (\d+) FAIL", r.stdout)
    padle = [l[7:].split("  ")[0] for l in r.stdout.splitlines() if l.startswith("[FAIL]")]
    if not m:
        return (None, None), padle
    ok, fail = int(m.group(1)), int(m.group(2))
    return (ok + fail, fail), padle


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


(wyk0, pad0), _ = bramka()
print(f"ZDROWY KOD: wykonane={wyk0} padle={pad0}", flush=True)
if pad0 != 0:
    sys.exit("Bramka czerwona na zdrowym kodzie — sabotaż nie ma sensu.")

# Opcjonalny filtr: `sabotaz-theme-live.py S5` puszcza tylko wybrane warianty.
if len(sys.argv) > 1:
    WARIANTY = {k: v for k, v in WARIANTY.items() if k.split()[0] in sys.argv[1:]}

nie_wykryte = 0
for nazwa, podmiany in WARIANTY.items():
    pliki = sorted({SRC / f for f, _, _ in podmiany})
    oryginaly = {p: p.read_bytes() for p in pliki}
    odciski = {p: sha(p) for p in pliki}
    teksty = {p: oryginaly[p].decode("utf-8") for p in pliki}
    martwe = [n for n, (f, stare, _) in enumerate(podmiany) if teksty[SRC / f].count(stare) != 1]
    if martwe:
        print(f"[KOTWICA] {nazwa}: kotwice nr {martwe} nie występują dokładnie raz — wariant MARTWY")
        nie_wykryte += 1
        continue
    for f, stare, nowe in podmiany:
        teksty[SRC / f] = teksty[SRC / f].replace(stare, nowe)
    try:
        for p in pliki:
            p.write_text(teksty[p], encoding="utf-8")
        (wyk, pad), padle = bramka()
    finally:
        for p in pliki:
            p.write_bytes(oryginaly[p])
    for p in pliki:
        assert sha(p) == odciski[p], f"{p} NIE przywrócony!"
    ok = bool(pad) and wyk == wyk0
    if not ok:
        nie_wykryte += 1
    print(f"[{'WYKRYTY' if ok else 'NIE WYKRYTY'}] {nazwa}: padle={pad} wykonane={wyk}"
          + (f" ({'; '.join(padle)})" if padle else ""), flush=True)

print(f"\nSABOTAŻ: wariantów={len(WARIANTY)} niewykrytych={nie_wykryte}")
sys.exit(1 if nie_wykryte else 0)
