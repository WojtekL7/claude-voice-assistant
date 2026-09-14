"""Rejestr rozmów — co żyło w zakładkach, gdy program się zamykał.

PO CO TO JEST
-------------
VCA przypina każdej zakładce WŁASNY identyfikator sesji (`claude --session-id`),
ale nigdzie go nie zapisywała. Skutek: po restarcie apki, po padzie `claude`
albo po restarcie komputera zakładki wstają PUSTE, a cała rozmowa leży
nietknięta w dzienniku i nikt jej nie wznawia — trzeba pamiętać identyfikator
i wpisać `claude --resume <uuid>` ręcznie.

Ten moduł zapamiętuje przypisanie „agent → ostatnia sesja" i potrafi
powiedzieć, KTÓRE z nich da się jeszcze wznowić.

⛔ WZNOWIĆ WOLNO TYLKO SESJĘ, KTÓREJ DZIENNIK ISTNIEJE. Sam wpis w naszym
pliku jest OBIETNICĄ, nie dowodem: `claude` mógł nie wstać, użytkownik mógł
wyczyścić katalog, sesja mogła paść przed zapisaniem czegokolwiek. Wznowienie
nieistniejącej sesji kończy się błędem w terminalu, którego użytkownik nie ma
jak powiązać z przyczyną — dlatego pytamy DYSK, nie pamięć.

⚠️ Zapis jest atomowy i fail-open: to wygoda, nie warunek pracy. Gdy pliku nie
da się zapisać ani odczytać, zakładki startują jak dotąd — od nowej rozmowy.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

REGISTRY_NAME = "sessions.json"

# Ile wpisów trzymamy. Rejestr ma służyć „wznów to, co miałem", a nie być
# archiwum — stare sesje i tak wypadają przy kontroli istnienia dziennika.
MAX_ENTRIES = 60


def registry_path(config_dir: Path) -> Path:
    return Path(config_dir) / REGISTRY_NAME


def load(config_dir: Path) -> dict:
    """Cały rejestr: agent_id → wpis. Brak/uszkodzony plik → pusty (fail-open)."""
    try:
        dane = json.loads(registry_path(config_dir).read_text(encoding="utf-8"))
    except Exception:
        return {}
    wpisy = dane.get("sessions") if isinstance(dane, dict) else None
    return wpisy if isinstance(wpisy, dict) else {}


def record(config_dir: Path, agent_id: str, session_id: str,
           working_directory: str = "", agent_name: str = "") -> bool:
    """Zapamiętaj, że ten agent pracuje w tej sesji. Zwraca True przy zapisie.

    Wołane w chwili BUDOWANIA polecenia `claude`, czyli zanim cokolwiek
    powstanie na dysku — dlatego przy odczycie sprawdzamy dziennik.
    """
    agent_id = str(agent_id or "").strip()
    session_id = str(session_id or "").strip()
    if not agent_id or not session_id:
        return False
    try:
        config_dir = Path(config_dir)
        config_dir.mkdir(parents=True, exist_ok=True)
        wpisy = load(config_dir)
        wpisy[agent_id] = {
            "session_id": session_id,
            "working_directory": str(working_directory or ""),
            "agent_name": str(agent_name or ""),
            "started_at": time.time(),
        }
        if len(wpisy) > MAX_ENTRIES:
            najstarsze = sorted(wpisy.items(),
                                key=lambda kv: kv[1].get("started_at", 0))
            for klucz, _ in najstarsze[:len(wpisy) - MAX_ENTRIES]:
                wpisy.pop(klucz, None)
        _write_atomic(registry_path(config_dir), {"sessions": wpisy})
        return True
    except Exception:
        return False


def forget(config_dir: Path, agent_id: str) -> bool:
    """Usuń wpis agenta (np. gdy user świadomie zaczyna rozmowę od nowa)."""
    try:
        wpisy = load(config_dir)
        if str(agent_id) not in wpisy:
            return False
        wpisy.pop(str(agent_id), None)
        _write_atomic(registry_path(Path(config_dir)), {"sessions": wpisy})
        return True
    except Exception:
        return False


def encode_project_dir(working_directory: str) -> str:
    """Ścieżka katalogu roboczego → nazwa folderu w `~/.claude/projects`.

    Ten sam zapis, którego używa czytnik dziennika (`transcript_reader`).
    """
    from core.transcript_reader import _encode_project_dir
    return _encode_project_dir(working_directory)


def transcript_for(session_id: str, working_directory: str,
                   projects_base: Path = None) -> Path | None:
    """Plik dziennika tej sesji albo None, gdy go nie ma.

    Najpierw pytamy o katalog wyliczony ze ścieżki roboczej; gdy tam pusto,
    przeszukujemy pozostałe katalogi projektów — katalog roboczy zakładki mógł
    się zmienić, a sam identyfikator sesji jest unikalny, więc to bezpieczne.
    """
    session_id = str(session_id or "").strip()
    if not session_id:
        return None
    baza = Path(projects_base or (Path.home() / ".claude" / "projects"))
    if not baza.is_dir():
        return None
    kandydat = baza / encode_project_dir(working_directory or "") / f"{session_id}.jsonl"
    if kandydat.is_file():
        return kandydat
    try:
        for katalog in baza.iterdir():
            plik = katalog / f"{session_id}.jsonl"
            if plik.is_file():
                return plik
    except Exception:
        return None
    return None


def resumable(config_dir: Path, projects_base: Path = None) -> list:
    """Wpisy, które DA SIĘ wznowić — z dowodem w postaci istniejącego dziennika.

    Najnowsze pierwsze. Każdy wpis dostaje `transcript_path` i `size`, żeby
    okno mogło pokazać, czy rozmowa jest w ogóle niepusta.
    """
    out = []
    for agent_id, wpis in (load(config_dir) or {}).items():
        if not isinstance(wpis, dict):
            continue
        plik = transcript_for(wpis.get("session_id", ""),
                              wpis.get("working_directory", ""), projects_base)
        if plik is None:
            continue          # ⛔ brak dziennika = nie ma czego wznawiać
        try:
            rozmiar = plik.stat().st_size
        except Exception:
            rozmiar = 0
        out.append(dict(wpis, agent_id=agent_id,
                        transcript_path=str(plik), size=rozmiar))
    return sorted(out, key=lambda w: w.get("started_at", 0), reverse=True)


def _write_atomic(p: Path, dane: dict) -> None:
    """Zapis przez plik tymczasowy — przerwany nie zostawia połowy rejestru."""
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, p)
