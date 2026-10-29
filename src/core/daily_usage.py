"""Dzisiejsze zużycie tokenów — ze WSZYSTKICH dzienników Claude Code (Σ na pasku).

Polecenie właściciela 2026-10-29: Σ ma mówić, ile DZIŚ zużył, także w
zakładkach już zamkniętych i po ponownym uruchomieniu programu. Licznik przy
agencie (rozmiar rozmowy) się do tego nie nadaje — spada do zera po /clear.
Dlatego liczymy wprost z dzienników `~/.claude/projects/**/*.jsonl`: każda
odpowiedź agenta z dzisiejszą datą (czas lokalny) wnosi swoje `usage`.

Wersja „B" (wybór właściciela): wejście + zapis do pamięci podręcznej +
wyjście — BEZ `cache_read_input_tokens` (ponowne czytanie rozmowy przy każdej
odpowiedzi; to 99% surowej sumy, a Anthropic liczy je dużo taniej). Wszystkie
trzy warianty (A = z odczytem, B, C = samo wyjście) oddajemy do podpowiedzi.

⛔ Claude Code zapisuje JEDNĄ odpowiedź w kilku wpisach (po jednym na blok
treści) z IDENTYCZNYM `usage` — zmierzone 2026-10-29: 1684 wpisy = 836
odpowiedzi. Bez deduplikacji po `message.id` wynik byłby ~2× zawyżony.

Pod-agenci (`isSidechain`, pliki w `<sesja>/subagents/`) SĄ liczeni — to
prawdziwe zużycie. Komunikaty techniczne (`<synthetic>`) nie.
Czytanie przyrostowe: pamiętamy pozycję w każdym pliku, więc kolejne
odświeżenie czyta tylko dopisane bajty. Przy zmianie dnia liczymy od nowa.
"""

import json
import os
import threading
from datetime import date, datetime, time as dtime
from pathlib import Path
from typing import Dict, Optional

_KEYS = ("input_tokens", "cache_creation_input_tokens",
         "cache_read_input_tokens", "output_tokens")


def _local_date(timestamp) -> Optional[date]:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone().date()
    except ValueError:
        return None


class DailyUsage:
    """Sumator dzisiejszego zużycia. `refresh()` bezpieczne z wątku tła."""

    def __init__(self, projects_dir: Optional[Path] = None):
        self._projects_dir = Path(projects_dir) if projects_dir else \
            Path.home() / ".claude" / "projects"
        self._lock = threading.Lock()
        self._reset(date.today())

    def _reset(self, day: date):
        self._day = day
        self._offsets: Dict[str, tuple] = {}   # ścieżka → (inode, pozycja)
        self._seen = set()                     # identyfikatory policzonych odpowiedzi
        self._totals = {k: 0 for k in _KEYS}

    # ---------- odczyt ----------

    def refresh(self, today: Optional[date] = None) -> dict:
        """Doczytaj nowe wpisy ze wszystkich dzisiejszych dzienników."""
        today = today or date.today()
        with self._lock:
            if today != self._day:
                self._reset(today)
            midnight = datetime.combine(today, dtime.min).timestamp()
            try:
                files = list(self._projects_dir.glob("**/*.jsonl"))
            except OSError:
                files = []
            for path in files:
                try:
                    st = path.stat()
                except OSError:
                    continue
                if st.st_mtime < midnight:
                    continue
                self._read_file(str(path), st)
            return self._snapshot()

    def _read_file(self, path: str, st):
        inode, offset = self._offsets.get(path, (st.st_ino, 0))
        if inode != st.st_ino or st.st_size < offset:
            # Plik podmieniony albo skrócony (kompakcja) — czytamy od nowa;
            # już policzone odpowiedzi odsiewa `_seen`.
            offset = 0
        if st.st_size == offset:
            self._offsets[path] = (st.st_ino, offset)
            return
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                raw = f.read()
        except OSError:
            return
        last_nl = raw.rfind(b"\n")
        if last_nl == -1:
            return   # ostatnia linia w trakcie zapisu — poczekaj
        self._offsets[path] = (st.st_ino, offset + last_nl + 1)
        for line in raw[:last_nl].split(b"\n"):
            # Szybki filtr bez parsowania: wielkie wpisy techniczne pomijamy.
            if b'"usage"' not in line or b'"assistant"' not in line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            self._count(obj)

    def _count(self, obj):
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            return
        if obj.get("isApiErrorMessage"):
            return
        msg = obj.get("message")
        if not isinstance(msg, dict):
            return
        model = msg.get("model")
        if isinstance(model, str) and model.strip().startswith("<"):
            return
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            return
        if _local_date(obj.get("timestamp")) != self._day:
            return
        ident = msg.get("id") or obj.get("uuid")
        if ident:
            if ident in self._seen:
                return
            self._seen.add(ident)
        for k in _KEYS:
            v = usage.get(k)
            if isinstance(v, int) and v > 0:
                self._totals[k] += v

    # ---------- wynik ----------

    def _snapshot(self) -> dict:
        t = self._totals
        b = t["input_tokens"] + t["cache_creation_input_tokens"] + t["output_tokens"]
        return {
            "day": self._day,
            "b": b,                                     # wyświetlane w Σ
            "a": b + t["cache_read_input_tokens"],      # z ponownym czytaniem
            "c": t["output_tokens"],                    # samo pisanie agentów
            "responses": len(self._seen),
        }

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot()
