"""Ustawienia Claude Code (`~/.claude/settings.json`) — bezpieczny odczyt i zapis.

PO CO TO JEST
-------------
Claude Code zapamiętuje POZIOM WYSIŁKU OSOBNO DLA KAŻDEGO MODELU — w sekcji
`modelSettings` tego pliku. Przy Fable 5.1 ma to wymiar pieniężny: model
startuje domyślnie na `high`, jest „bardziej gorliwy" od poprzednika i kosztuje
2× tyle co Opus 5, więc zejście na `medium` bywa największą jednorazową
oszczędnością, jaką da się tu zrobić. Zalecenie pochodzi wprost od zespołu
Claude Code.

⛔ TO NIE JEST NASZ PLIK. Mieszka w nim praca użytkownika (uprawnienia, motyw,
hooki, zmienne) i edytuje go także on sam oraz samo Claude Code. Stąd trzy
twarde zasady, od których nie ma odstępstw:

  1. **Nie rozumiesz pliku — NIE PISZ.** Gdy zawartość nie daje się odczytać
     jako JSON, odmawiamy zapisu i mówimy o tym. Nadpisanie „czegoś dziwnego"
     skasowałoby cudzą pracę bez śladu, a to gorsze niż niewykonana funkcja.
  2. **Zapisujemy MERGE, nigdy nie budujemy pliku od nowa** — wszystkie klucze,
     których nie znamy, wracają na miejsce nietknięte.
  3. **Zapis jest ATOMOWY** (plik tymczasowy + podmiana), więc przerwany zapis
     nie zostawia połowy pliku. Przed PIERWSZĄ naszą zmianą robimy kopię.

Fail-open dotyczy ODCZYTU (brak pliku = brak ustawień, apka działa), ale NIE
zapisu: tam obowiązuje fail-closed, bo w grę wchodzą cudze dane.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

# Poziomy, które rozumie Claude Code. Kolejność = od najtańszego.
EFFORT_LEVELS = ("low", "medium", "high")

# Nazwa kopii robionej PRZED pierwszą naszą zmianą pliku użytkownika.
BACKUP_SUFFIX = ".bak-vca"


class SettingsError(RuntimeError):
    """Nie da się bezpiecznie przeczytać albo zapisać ustawień Claude Code."""


def settings_path() -> Path:
    """Ścieżka pliku ustawień Claude Code (katalog domowy użytkownika)."""
    return Path.home() / ".claude" / "settings.json"


def read_settings(path: Path = None) -> dict:
    """Cała zawartość pliku. Brak pliku → pusty słownik (to normalny stan).

    Uszkodzony plik rzuca `SettingsError` — wołający MUSI odróżnić „nie ma
    ustawień" od „są, ale ich nie rozumiem", bo tylko w pierwszym przypadku
    wolno cokolwiek zapisać.
    """
    p = Path(path or settings_path())
    if not p.exists():
        return {}
    try:
        tekst = p.read_text(encoding="utf-8")
    except Exception as exc:
        raise SettingsError(f"nie udało się odczytać {p}: {exc}") from exc
    if not tekst.strip():
        return {}
    try:
        dane = json.loads(tekst)
    except Exception as exc:
        raise SettingsError(f"{p} nie jest poprawnym plikiem JSON: {exc}") from exc
    if not isinstance(dane, dict):
        raise SettingsError(f"{p} nie zawiera obiektu JSON")
    return dane


def get_effort(model_api_id: str, path: Path = None) -> str | None:
    """Zapisany poziom wysiłku dla modelu albo None (czyli: domyślny modelu).

    Odczyt jest fail-open — uszkodzony plik nie może wywalić okna ustawień.
    """
    try:
        dane = read_settings(path)
    except SettingsError:
        return None
    wpis = (dane.get("modelSettings") or {}).get(str(model_api_id))
    if not isinstance(wpis, dict):
        return None
    poziom = wpis.get("effortLevel")
    return poziom if poziom in EFFORT_LEVELS else None


def all_efforts(path: Path = None) -> dict:
    """Mapa identyfikator modelu → poziom, dla wszystkich zapisanych wpisów."""
    try:
        dane = read_settings(path)
    except SettingsError:
        return {}
    out = {}
    for api_id, wpis in (dane.get("modelSettings") or {}).items():
        if isinstance(wpis, dict) and wpis.get("effortLevel") in EFFORT_LEVELS:
            out[api_id] = wpis["effortLevel"]
    return out


def set_effort(model_api_id: str, level: str | None, path: Path = None) -> bool:
    """Ustaw (albo usuń, gdy `level` to None) poziom wysiłku dla modelu.

    Zwraca True, gdy plik został zmieniony; False, gdy nie było czego zmieniać.
    Rzuca `SettingsError`, gdy pliku nie da się bezpiecznie odczytać — wtedy
    NIC nie zapisujemy.
    """
    model_api_id = str(model_api_id or "").strip()
    if not model_api_id:
        raise SettingsError("brak identyfikatora modelu")
    if level is not None and level not in EFFORT_LEVELS:
        raise SettingsError(f"nieznany poziom wysiłku: {level!r}")

    p = Path(path or settings_path())
    dane = read_settings(p)          # uszkodzony plik → wyjątek, zero zapisu

    sekcja = dane.get("modelSettings")
    if not isinstance(sekcja, dict):
        sekcja = {}
    wpis = sekcja.get(model_api_id)
    if not isinstance(wpis, dict):
        wpis = {}

    obecny = wpis.get("effortLevel")
    if level is None:
        if obecny is None:
            return False
        wpis.pop("effortLevel", None)
        # Pusty wpis modelu zostawiałby śmieć — sprzątamy go, ale WYŁĄCZNIE
        # gdy nie ma w nim niczego innego (Claude Code może tam trzymać własne
        # pola, o których nie wiemy).
        if wpis:
            sekcja[model_api_id] = wpis
        else:
            sekcja.pop(model_api_id, None)
    else:
        if obecny == level:
            return False
        wpis["effortLevel"] = level
        sekcja[model_api_id] = wpis

    if sekcja:
        dane["modelSettings"] = sekcja
    else:
        dane.pop("modelSettings", None)

    _write_atomic(p, dane)
    return True


def get_skill_overrides(path: Path = None) -> dict:
    """Mapa nazwa skilla → stan widoczności (`skillOverrides`).

    Odczyt fail-open: uszkodzony plik nie może zablokować okna z raportem.
    """
    try:
        dane = read_settings(path)
    except SettingsError:
        return {}
    sekcja = dane.get("skillOverrides")
    return {k: v for k, v in sekcja.items() if isinstance(v, str)} \
        if isinstance(sekcja, dict) else {}


def set_skill_override(skill_name: str, state: str | None, path: Path = None) -> bool:
    """Ustaw stan widoczności skilla albo przywróć domyślny (`state=None`).

    Stany opisane w `core/skill_doctor.OVERRIDE_STATES`. Zapis idzie przez tę
    samą drogę co poziom wysiłku: MERGE, atomowo, z kopią — bo to CUDZY plik.
    Zwraca True, gdy coś się realnie zmieniło.
    """
    from core.skill_doctor import OVERRIDE_STATES

    skill_name = str(skill_name or "").strip()
    if not skill_name:
        raise SettingsError("brak nazwy skilla")
    if state is not None and state not in OVERRIDE_STATES:
        raise SettingsError(f"nieznany stan skilla: {state!r}")

    p = Path(path or settings_path())
    dane = read_settings(p)          # uszkodzony plik → wyjątek, zero zapisu

    sekcja = dane.get("skillOverrides")
    if not isinstance(sekcja, dict):
        sekcja = {}
    obecny = sekcja.get(skill_name)

    # „on" to stan domyślny — zamiast wpisywać go jawnie, kasujemy wpis.
    # Plik zostaje czysty, a zachowanie jest dokładnie takie samo.
    if state is None or state == "on":
        if obecny is None:
            return False
        sekcja.pop(skill_name, None)
    else:
        if obecny == state:
            return False
        sekcja[skill_name] = state

    if sekcja:
        dane["skillOverrides"] = sekcja
    else:
        dane.pop("skillOverrides", None)

    _write_atomic(p, dane)
    return True


def _write_atomic(p: Path, dane: dict) -> None:
    """Zapis przez plik tymczasowy + podmiana, z jednorazową kopią zapasową."""
    p.parent.mkdir(parents=True, exist_ok=True)
    kopia = p.with_name(p.name + BACKUP_SUFFIX)
    if p.exists() and not kopia.exists():
        try:
            shutil.copy2(p, kopia)
        except Exception:
            # Kopia jest wygodą, nie warunkiem — ale brak pliku źródłowego
            # oznacza, że i tak nie ma czego stracić.
            pass
    tresc = json.dumps(dane, ensure_ascii=False, indent=2) + "\n"
    tmp = p.with_name(p.name + ".tmp-vca")
    tmp.write_text(tresc, encoding="utf-8")
    try:
        if p.exists():
            os.chmod(tmp, p.stat().st_mode & 0o777)
    except Exception:
        pass
    os.replace(tmp, p)
