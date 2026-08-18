#!/usr/bin/env python3
"""Bramka: sprzątanie plików przy starcie (`UpdateManager.cleanup_stale_files`).

Po co: apka zbierała po sobie śmieci — pobrane paczki aktualizacji (~2,5 GB
w lipcu 2026), zrzuty crashu z zamkniętych spraw i logi rosnące bez limitu.
Sprzątanie działa od 2026-07-13, ale miało ZŁOŚLIWĄ dziurę: `read-last-debug.log`
stał na liście „martwych logów", choć czujnik bugu 🔊 ODŻYŁ przy rundzie 5 —
czyli KAŻDY start aplikacji kasował dziennik dowodowy trwającej diagnozy.
Objaw zerowy: nikt nie zgłosi braku pliku, o którego istnieniu nie wie.

Bramka pilnuje więc DWÓCH rzeczy naraz: że śmieci znikają ORAZ że żywe pliki
(dowody, konfiguracja) przeżywają.

⚠️ Test NIGDY nie dotyka prawdziwego katalogu konfiguracji — buduje atrapę HOME
w katalogu tymczasowym i podmienia `Path.home()`. Powód nie jest teoretyczny:
bramka pożyczająca produkcyjne metody potrafi zatruć żywy log diagnostyczny
atrapowymi wpisami, nieodróżnialnymi od prawdziwych (COMMON, „TESTY NA ŻYWYCH
DANYCH"). Kontrola po uruchomieniu: rozmiar i mtime prawdziwego
`~/.vibe-coding-assistant/read-last-debug.log` mają być NIETKNIĘTE.

═══ WYNIKI SABOTAŻU — ZMIERZONE 2026-08-18, nie przewidziane (23 asercje) ═══
  1. `read-last-debug.log` z powrotem na liście martwych  → padły 3  ← TEN BUG
  2. bramka znacznika wyłączona (`if False`)              → padły 2
  3. bramka zmiennej środowiskowej wyłączona              → padł  1
  4. podłoga zrzutów zniesiona (`logs[0:]`)               → padły 2
  5. zrzuty tylko `crash-*.log` (bez terminal-glitch)     → padły 2
  6. limit rosnących logów nie wołany                     → padł  1
  7. `keep=1` → `keep=99` przy sprzątaniu paczek          → padły 2
Każdy wariant wykryty przez co najmniej jeden test. W KAŻDYM przebiegu wykonały
się wszystkie 23 asercje — bramka nigdy nie wywaliła się w połowie, co przy
filtrowanym wyjściu (`grep FAIL`) wyglądałoby jak komplet zielonych
(COMMON: „przy sabotażu licz też, ILE testów się wykonało").
"""
import os
import sys
import time
import pathlib
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DAY = 86400
PASS, FAIL = [], []


def check(label, condition):
    """Jedna asercja. Zliczana, żeby spadek LICZBY WYKONANYCH testów był widoczny
    (COMMON: „przy sabotażu licz też, ILE testów się wykonało")."""
    if condition:
        PASS.append(label)
        print(f"[OK]   {label}")
    else:
        FAIL.append(label)
        print(f"[FAIL] {label}")


def touch(path, size=0, age_days=0.0):
    """Utwórz plik o zadanym rozmiarze i wieku."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if age_days:
        t = time.time() - age_days * DAY
        os.utime(path, (t, t))
    return path


class FakeHome:
    """Podmienia Path.home() na katalog tymczasowy — na czas jednego scenariusza."""

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cva-cleanup-test-"))
        self._real = pathlib.Path.home
        tmp = self.tmp
        pathlib.Path.home = classmethod(lambda cls: tmp)
        return self.tmp

    def __exit__(self, *exc):
        pathlib.Path.home = self._real
        shutil.rmtree(self.tmp, ignore_errors=True)
        return False


def make_manager(home, um):
    """UpdateManager wskazujący na atrapę HOME (łącznie z katalogiem crash-logów)."""
    mgr = um.UpdateManager(
        appcast_url="https://example.invalid/appcast.json",
        current_version="1.0.0", platform_id="linux-x64",
        download_dir=home / ".vibe-coding-assistant" / "updates")
    # CRASH_LOG_DIR to stała zaimportowana przy ładowaniu modułu — wskazuje na
    # PRAWDZIWY dom, więc bez tej podmiany test kasowałby zrzuty użytkownika.
    um.CRASH_LOG_DIR = home / ".vibe-coding-assistant" / "crash-logs"
    return mgr


def run():
    import core.update_manager as um

    # ---------- 1. ŻYWY log diagnostyczny kontra sprzątanie ----------
    with FakeHome() as home:
        cfg = home / ".vibe-coding-assistant"
        touch(cfg / "read-last-debug.log", 100)
        touch(cfg / "read-last-debug.on")             # czujnik WŁĄCZONY
        os.environ.pop("CVA_READ_LAST_DEBUG", None)
        make_manager(home, um).cleanup_stale_files()
        check("znacznik istnieje → dziennik dowodowy 🔊 PRZEŻYWA",
              (cfg / "read-last-debug.log").exists())
        check("sam znacznik też zostaje nietknięty",
              (cfg / "read-last-debug.on").exists())

    with FakeHome() as home:
        cfg = home / ".vibe-coding-assistant"
        touch(cfg / "read-last-debug.log", 100)       # BEZ znacznika
        os.environ.pop("CVA_READ_LAST_DEBUG", None)
        make_manager(home, um).cleanup_stale_files()
        check("brak znacznika → martwy log diagnostyczny skasowany",
              not (cfg / "read-last-debug.log").exists())

    with FakeHome() as home:
        cfg = home / ".vibe-coding-assistant"
        touch(cfg / "read-last-debug.log", 100)
        os.environ["CVA_READ_LAST_DEBUG"] = "1"       # druga furtka czujnika
        try:
            make_manager(home, um).cleanup_stale_files()
            check("zmienna środowiskowa =1 → dziennik PRZEŻYWA (bez znacznika)",
                  (cfg / "read-last-debug.log").exists())
        finally:
            os.environ.pop("CVA_READ_LAST_DEBUG", None)

    with FakeHome() as home:
        cfg = home / ".claude-voice-assistant"        # STARY katalog konfiguracji
        touch(cfg / "read-last-debug.log", 100)
        touch(cfg / "read-last-debug.on")
        os.environ.pop("CVA_READ_LAST_DEBUG", None)
        make_manager(home, um).cleanup_stale_files()
        check("bramka działa też w starym katalogu sprzed rebrandingu",
              (cfg / "read-last-debug.log").exists())

    # ---------- 2. Logi martwe kontra żywe ----------
    with FakeHome() as home:
        cfg = home / ".vibe-coding-assistant"
        touch(cfg / "flag-debug.log", 4_700_000)
        touch(cfg / "debug_buffer.txt", 1000)
        touch(cfg / "debug.log", 32_000)              # ŻYWY (pisze claude_bridge)
        touch(cfg / "tts.log", 110_000)               # poniżej limitu
        touch(cfg / "agents.json", 6000)              # konfiguracja użytkownika
        touch(cfg / "config.json", 2500)
        make_manager(home, um).cleanup_stale_files()
        check("martwy flag-debug.log skasowany", not (cfg / "flag-debug.log").exists())
        check("martwy debug_buffer.txt skasowany", not (cfg / "debug_buffer.txt").exists())
        check("ŻYWY debug.log NIETKNIĘTY", (cfg / "debug.log").exists())
        check("tts.log poniżej limitu NIETKNIĘTY", (cfg / "tts.log").exists())
        check("agents.json nietknięty (kontrola negatywna)", (cfg / "agents.json").exists())
        check("config.json nietknięty (kontrola negatywna)", (cfg / "config.json").exists())

    # ---------- 3. Limit rosnących logów ----------
    with FakeHome() as home:
        cfg = home / ".vibe-coding-assistant"
        touch(cfg / "tts.log", 512 * 1024 + 1)        # ponad limit
        make_manager(home, um).cleanup_stale_files()
        check("tts.log ponad limit skasowany", not (cfg / "tts.log").exists())

    # ---------- 4. Paczki aktualizacji ----------
    with FakeHome() as home:
        upd = home / ".vibe-coding-assistant" / "updates"
        touch(upd / "VCA-1.0.26-linux-x64.AppImage", 500, age_days=40)
        touch(upd / "VCA-1.0.27-linux-x64.AppImage", 500, age_days=20)
        touch(upd / "VCA-1.0.28-linux-x64.AppImage", 500, age_days=1)
        touch(upd / "VCA-1.0.29-linux-x64.AppImage.part", 500)
        touch(upd / "notatka.txt", 10)                # NIE paczka
        make_manager(home, um).cleanup_stale_files()
        check("najnowsza paczka zostaje",
              (upd / "VCA-1.0.28-linux-x64.AppImage").exists())
        check("starsza paczka skasowana",
              not (upd / "VCA-1.0.27-linux-x64.AppImage").exists())
        check("najstarsza paczka skasowana",
              not (upd / "VCA-1.0.26-linux-x64.AppImage").exists())
        check("niedokończone pobranie (.part) skasowane",
              not (upd / "VCA-1.0.29-linux-x64.AppImage.part").exists())
        check("plik NIE-paczka w updates/ nietknięty (kontrola negatywna)",
              (upd / "notatka.txt").exists())

    # ---------- 5. Zrzuty crashu: wiek + podłoga ----------
    with FakeHome() as home:
        crash = home / ".vibe-coding-assistant" / "crash-logs"
        for i in range(8):                            # 8 sztuk, WSZYSTKIE stare
            touch(crash / f"crash-A-2026060{i}-0900{i}0.log", 1000, age_days=60)
        touch(crash / "terminal-glitch-A-20260601-090000.log", 1000, age_days=60)
        make_manager(home, um).cleanup_stale_files()
        left = sorted(p.name for p in crash.glob("*.log"))
        check(f"stare zrzuty skasowane do podłogi (zostało {len(left)} z 9)",
              len(left) == 5)
        check("podłoga NIE zostawia katalogu pustego", len(left) > 0)

    with FakeHome() as home:
        crash = home / ".vibe-coding-assistant" / "crash-logs"
        touch(crash / "terminal-glitch-A-20260601-090000.log", 1000, age_days=60)
        for i in range(6):
            touch(crash / f"crash-A-2026060{i}-0900{i}0.log", 1000, age_days=60)
        make_manager(home, um).cleanup_stale_files()
        names = [p.name for p in crash.glob("*.log")]
        check("`terminal-glitch-*.log` też podlega sprzątaniu wiekiem "
              "(limit sztuk go NIE widział)",
              "terminal-glitch-A-20260601-090000.log" not in names)

    with FakeHome() as home:
        crash = home / ".vibe-coding-assistant" / "crash-logs"
        for i in range(3):                            # mniej niż podłoga
            touch(crash / f"crash-A-2026060{i}-0900{i}0.log", 1000, age_days=900)
        make_manager(home, um).cleanup_stale_files()
        check("poniżej podłogi nic nie kasujemy, choćby zrzuty były prastare",
              len(list(crash.glob("*.log"))) == 3)

    with FakeHome() as home:
        crash = home / ".vibe-coding-assistant" / "crash-logs"
        for i in range(8):                            # 8 sztuk, wszystkie ŚWIEŻE
            touch(crash / f"crash-A-2026081{i}-0900{i}0.log", 1000, age_days=2)
        make_manager(home, um).cleanup_stale_files()
        check("świeże zrzuty (poniżej 30 dni) przeżywają ponad podłogę",
              len(list(crash.glob("*.log"))) == 8)

    # ---------- 6. Idempotencja ----------
    with FakeHome() as home:
        cfg = home / ".vibe-coding-assistant"
        touch(cfg / "agents.json", 6000)
        mgr = make_manager(home, um)
        mgr.cleanup_stale_files()
        mgr.cleanup_stale_files()                     # drugi przebieg na pustym
        check("dwa przebiegi pod rząd nie wywalają się i nic nie psują",
              (cfg / "agents.json").exists())


if __name__ == "__main__":
    run()
    print()
    print(f"WYKONANYCH ASERCJI: {len(PASS) + len(FAIL)}   OK: {len(PASS)}   FAIL: {len(FAIL)}")
    if FAIL:
        print("PADŁY:")
        for f in FAIL:
            print(f"  - {f}")
    sys.exit(1 if FAIL else 0)
