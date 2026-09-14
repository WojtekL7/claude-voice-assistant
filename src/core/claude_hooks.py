"""Hooki Claude Code — skąd apka wie, CO SIĘ DZIEJE w zakładce.

PO CO TO JEST
-------------
Dwie rzeczy, których VCA do tej pory nie wiedziała na pewno:

1. **Jaki model naprawdę pracuje.** Przy ustawieniu „Domyślny" apka nie wie
   z góry, co uruchomi Claude Code — dowiadywała się PO FAKCIE, z dziennika
   sesji, więc pasek statusu spóźniał się o całą wypowiedź, a licznik tokenów
   brał okno kontekstu nie tego modelu. Po `/model ...` w środku rozmowy
   rozjazd trwał do następnej odpowiedzi.
2. **Które rozmowy żyły, gdy program się zamykał.** Bez tego po restarcie
   (albo po padzie `claude`) zakładki wstają puste, a rozmowy zostają
   w dzienniku i nikt ich nie wznawia.

Claude Code umie o obu powiedzieć sam — hookami. ZMIERZONE 2026-09-14 na żywym
`claude` 2.1.270 (ładunki zdjęte z produkcji, nie wymyślone):

    SessionStart     session_id, transcript_path, cwd, source ("startup")
    SessionEnd       session_id, transcript_path, cwd, reason ("other")
    PostModelSwitch  session_id, from_model, to_model, requested_model, source

⭐ `from_model` przy pierwszym przełączeniu niesie model, na którym sesja
RUSZYŁA — czyli odpowiedź na pytanie „co uruchomił «Domyślny»".
⚠️ `SessionStart` MA pole `model` tylko czasem (u nas go nie było) — dlatego
model bierzemy z `PostModelSwitch`, a dziennik zostaje jako druga droga.

⛔ HOOKÓW NIE WPISUJEMY DO `~/.claude/settings.json`. Tamten plik obowiązuje
KAŻDĄ sesję Claude Code na tym komputerze, także uruchamianą poza apką —
zostawialibyśmy ślad w cudzej pracy. Zamiast tego trzymamy WŁASNY plik ustawień
i podajemy go przy starcie (`claude --settings <plik>`). Zmierzone: taki plik
DOKŁADA się do ustawień użytkownika, a nie zastępuje ich (skille z jego
`userSettings` ładowały się normalnie). Zasięg hooków = wyłącznie zakładki VCA.

⛔ FAIL-OPEN: gdy pliku nie da się zapisać, zakładka ma wstać BEZ hooków.
Wiedza o modelu to wygoda, nie warunek pracy — dziennik sesji nadal działa.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from core.platform_utils import is_windows

# Nazwy plików w katalogu konfiguracji użytkownika (`~/.vibe-coding-assistant`).
HOOKS_SETTINGS_NAME = "claude-hooks.json"
EVENTS_NAME = "session-events.jsonl"
SCRIPT_NAME_UNIX = "zapisz-zdarzenie.sh"
SCRIPT_NAME_WINDOWS = "zapisz-zdarzenie.cmd"

# Zdarzenia, o które prosimy. Świadomie TYLKO te trzy — hook odpala się przy
# każdej turze rozmowy, więc każdy dodatkowy to koszt płacony bez przerwy.
HOOK_EVENTS = ("SessionStart", "SessionEnd", "PostModelSwitch")

# Twardy limit dziennika zdarzeń. Pasywny log bez limitu urósł kiedyś w tym
# projekcie do 99 MB — nie powtarzamy tego.
MAX_EVENTS_BYTES = 512 * 1024


class HooksError(RuntimeError):
    """Nie udało się przygotować hooków (wołający ma fail-open)."""


def events_path(config_dir: Path) -> Path:
    return Path(config_dir) / EVENTS_NAME


def settings_path(config_dir: Path) -> Path:
    return Path(config_dir) / HOOKS_SETTINGS_NAME


def script_path(config_dir: Path) -> Path:
    return Path(config_dir) / (SCRIPT_NAME_WINDOWS if is_windows() else SCRIPT_NAME_UNIX)


def _script_body(dziennik: Path) -> str:
    """Treść dopisywacza: weź JSON z wejścia, dopisz linię do dziennika.

    Hook MUSI kończyć się kodem 0 i nic nie wypisywać na wyjście — wyjście
    trafia do Claude jako dodatkowy kontekst, czyli kosztowałoby tokeny przy
    każdej turze.
    """
    if is_windows():
        # `more` czyta wejście standardowe; `echo.` dokłada koniec linii.
        # ⚠️ NIE używamy PowerShella: na Windows domyślnie blokuje on
        # uruchamianie skryptów (zmierzone u współpracownika 2026-09-03).
        return (
            "@echo off\r\n"
            f'more >> "{dziennik}"\r\n'
            f'echo.>> "{dziennik}"\r\n'
            "exit /b 0\r\n"
        )
    return (
        "#!/bin/sh\n"
        f'cat >> "{dziennik}"\n'
        f'printf "\\n" >> "{dziennik}"\n'
        "exit 0\n"
    )


def build_settings(script: Path) -> dict:
    """Plik ustawień z samymi hookami — nic poza nimi tu nie wchodzi."""
    polecenie = str(script)
    return {
        "hooks": {
            zdarzenie: [{"hooks": [{"type": "command", "command": polecenie}]}]
            for zdarzenie in HOOK_EVENTS
        }
    }


def ensure_hooks(config_dir: Path) -> Path:
    """Przygotuj skrypt i plik ustawień; zwróć ścieżkę pliku ustawień.

    Idempotentne — wołane przy każdym starcie zakładki. Rzuca `HooksError`,
    gdy czegoś nie da się zapisać; wołający MUSI to złapać i wystartować
    zakładkę bez hooków.
    """
    config_dir = Path(config_dir)
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        dziennik = events_path(config_dir)
        skrypt = script_path(config_dir)
        skrypt.write_text(_script_body(dziennik), encoding="utf-8")
        if not is_windows():
            skrypt.chmod(skrypt.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        ustawienia = settings_path(config_dir)
        ustawienia.write_text(
            json.dumps(build_settings(skrypt), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return ustawienia
    except Exception as exc:
        raise HooksError(f"nie udało się przygotować hooków: {exc}") from exc


def trim_events(config_dir: Path, max_bytes: int = MAX_EVENTS_BYTES) -> bool:
    """Przytnij dziennik zdarzeń od GÓRY, gdy przekroczy limit.

    Tniemy po CAŁYCH liniach — ucięta w połowie linia JSON byłaby śmieciem,
    który czytnik musiałby odsiewać przy każdym odczycie. Zwraca True, gdy
    coś przycięto.
    """
    p = events_path(config_dir)
    try:
        if not p.exists() or p.stat().st_size <= max_bytes:
            return False
        dane = p.read_bytes()[-max_bytes:]
        nowa_linia = dane.find(b"\n")
        p.write_bytes(dane[nowa_linia + 1:] if nowa_linia >= 0 else dane)
        return True
    except Exception:
        return False


def read_events(config_dir: Path, offset: int = 0) -> tuple[list, int]:
    """Nowe zdarzenia od podanego miejsca w pliku. Zwraca (zdarzenia, nowy offset).

    ⚠️ Gdy plik SKURCZY SIĘ poniżej offsetu (przycinanie), zaczynamy od nowa
    od jego końca — a nie od zera. Odczyt od zera odegrałby całą historię
    jeszcze raz; ta sama pułapka wywróciła kiedyś auto-czytanie po
    kompaktowaniu dziennika.
    """
    p = events_path(config_dir)
    try:
        rozmiar = p.stat().st_size
    except Exception:
        return [], 0
    if rozmiar < offset:
        return [], rozmiar
    zdarzenia = []
    try:
        with p.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            tresc = f.read()
            nowy_offset = offset + len(tresc.encode("utf-8", "replace"))
    except Exception:
        return [], offset
    for linia in tresc.splitlines():
        linia = linia.strip()
        if not linia:
            continue
        try:
            dane = json.loads(linia)
        except Exception:
            continue          # niedopisana linia — przyjdzie w całości później
        if isinstance(dane, dict) and dane.get("hook_event_name"):
            zdarzenia.append(dane)
    return zdarzenia, nowy_offset


def model_from_event(zdarzenie: dict) -> str | None:
    """Identyfikator modelu, na którym sesja pracuje PO tym zdarzeniu.

    `PostModelSwitch` → `to_model`; `SessionStart` → `model`, jeśli jest
    (bywa pominięty — sprawdzone na żywym Claude Code).
    """
    if not isinstance(zdarzenie, dict):
        return None
    nazwa = zdarzenie.get("hook_event_name")
    if nazwa == "PostModelSwitch":
        model = zdarzenie.get("to_model")
    elif nazwa == "SessionStart":
        model = zdarzenie.get("model")
    else:
        return None
    model = (model or "").strip()
    return model or None


def normalize_model_id(model_id: str) -> str:
    """'claude-opus-5[1m]' → 'claude-opus-5' — zdejmij dopisek wariantu okna.

    ZMIERZONE: `from_model` przychodzi z sufiksem `[1m]` (milionowe okno
    kontekstu). Bez zdjęcia go mapa „identyfikator → nasz klucz" nie trafia
    i pasek pokazałby surowy identyfikator zamiast nazwy modelu.
    """
    model_id = (model_id or "").strip()
    if model_id.endswith("]") and "[" in model_id:
        model_id = model_id[:model_id.rindex("[")]
    return model_id.strip()


def settings_argument(sciezka: Path) -> str:
    """Fragment polecenia `--settings <plik>` gotowy do wklejenia do powłoki.

    Ścieżka bywa ze spacjami (Windows: „C:\\Users\\Jan Kowalski\\…"), więc
    zawsze w cudzysłowie. Cudzysłów w samej ścieżce jest niemożliwy na
    Windows i skrajnie nietypowy gdzie indziej, ale i tak go odsiewamy —
    wpuszczony do polecenia rozerwałby je na dwoje.
    """
    tekst = str(sciezka).replace('"', "")
    return f'--settings "{tekst}"'
