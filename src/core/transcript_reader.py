"""
Claude Voice Assistant - Transcript Reader (Etap 2, Droga A)

Czyta czyste wypowiedzi Claude'a z pliku-dziennika sesji Claude Code
(`~/.claude/projects/<katalog>/<sesja>.jsonl`) — zamiast parsować śmieciowy,
"skaczący" strumień terminala.

Bierzemy WYŁĄCZNIE:
- wpisy typu "assistant",
- nie będące pod-agentem (isSidechain == False/brak),
- z bloków treści tylko typ "text" (pomijamy "thinking" i "tool_use").

Dzięki temu narzędzia, myślenie i pod-agenci odpadają automatycznie, a tekst
jest czysty (poprawny markdown, polskie znaki OK) — gotowy do filtra prozy.

Klasa jest "głupia" i nieblokująca: trzyma offset bajtowy w aktywnym pliku
sesji i przy poll() dokłada tylko NOWE, kompletne linie. Logikę "kiedy czytać"
(aktywna zakładka, zaległości) zostawiamy warstwie GUI (Etap 3).
"""
import os
import re
import json
import glob
from pathlib import Path
from typing import List, Optional


def _encode_project_dir(working_directory: str) -> str:
    """Zamień ścieżkę katalogu roboczego na nazwę folderu w ~/.claude/projects.

    Claude Code koduje ścieżkę zamieniając znaki niealfanumeryczne na '-'.
    Np. /home/u/Projekty/claude-voice-assistant
        -> -home-u-Projekty-claude-voice-assistant
    """
    abspath = os.path.abspath(os.path.expanduser(working_directory))
    return re.sub(r'[^A-Za-z0-9]', '-', abspath)


class TranscriptReader:
    """Czyta nowe wypowiedzi tekstowe Claude'a z dziennika sesji."""

    def __init__(self, working_directory: str):
        self._projects_base = Path.home() / ".claude" / "projects"
        self.working_directory = ""
        self._project_dir: Optional[Path] = None
        self._session_file: Optional[str] = None
        self._offset = 0
        self.set_working_directory(working_directory)

    # ---------- konfiguracja ----------

    def set_working_directory(self, working_directory: str):
        """Ustaw katalog roboczy zakładki i znajdź jego folder w transkrypcie."""
        self.working_directory = os.path.abspath(os.path.expanduser(working_directory))
        self._project_dir = self._find_project_dir()
        self._session_file = None
        self._offset = 0

    def _find_project_dir(self) -> Optional[Path]:
        """Znajdź folder transkryptu odpowiadający katalogowi roboczemu."""
        if not self._projects_base.is_dir():
            return None
        # 1) Wprost po zakodowanej nazwie.
        cand = self._projects_base / _encode_project_dir(self.working_directory)
        if cand.is_dir():
            return cand
        # 2) Fallback: przeszukaj foldery i dopasuj po polu 'cwd' w pierwszym wpisie.
        for d in self._projects_base.iterdir():
            if not d.is_dir():
                continue
            try:
                jsonls = list(d.glob("*.jsonl"))
                if not jsonls:
                    continue
                newest = max(jsonls, key=lambda p: p.stat().st_mtime)
                with open(newest, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        if obj.get("cwd") and os.path.abspath(obj["cwd"]) == self.working_directory:
                            return d
                        break  # sprawdzamy tylko pierwszy sensowny wpis
            except Exception:
                continue
        return None

    # ---------- wybór pliku sesji ----------

    def _newest_session_file(self) -> Optional[str]:
        if not self._project_dir or not self._project_dir.is_dir():
            # katalog mógł powstać dopiero teraz — spróbuj ponownie
            self._project_dir = self._find_project_dir()
            if not self._project_dir:
                return None
        files = glob.glob(str(self._project_dir / "*.jsonl"))
        if not files:
            return None
        return max(files, key=lambda p: os.path.getmtime(p))

    def _ensure_session(self):
        """Upewnij się, że śledzimy najnowszy plik sesji (obsługa rotacji)."""
        newest = self._newest_session_file()
        if newest != self._session_file:
            # Pojawił się nowy plik sesji (np. po /clear) — czytaj od początku.
            self._session_file = newest
            self._offset = 0

    def seek_to_end(self):
        """Przeskocz na koniec bieżącej sesji (pomiń zaległości)."""
        self._ensure_session()
        if self._session_file and os.path.exists(self._session_file):
            self._offset = os.path.getsize(self._session_file)
        else:
            self._offset = 0

    def has_session(self) -> bool:
        self._ensure_session()
        return self._session_file is not None

    # ---------- odczyt ----------

    def poll(self) -> List[str]:
        """Zwróć listę NOWYCH wypowiedzi tekstowych Claude'a od ostatniego poll().

        Każdy element listy = jeden blok tekstowy asystenta (surowy markdown).
        Niekompletna ostatnia linia (jeszcze dopisywana) jest pomijana do
        kolejnego wywołania.
        """
        self._ensure_session()
        if not self._session_file or not os.path.exists(self._session_file):
            return []

        try:
            size = os.path.getsize(self._session_file)
            if size < self._offset:
                # Plik się skurczył (rotacja/truncate) — zacznij od początku.
                self._offset = 0
            if size == self._offset:
                return []
            with open(self._session_file, "rb") as f:
                f.seek(self._offset)
                raw = f.read()
        except Exception:
            return []

        # Przetwarzamy tylko kompletne linie (do ostatniego '\n').
        last_nl = raw.rfind(b"\n")
        if last_nl == -1:
            return []  # nic kompletnego jeszcze nie ma
        consumed = last_nl + 1
        complete = raw[:consumed]
        self._offset += consumed

        results: List[str] = []
        for bline in complete.split(b"\n"):
            if not bline.strip():
                continue
            try:
                obj = json.loads(bline.decode("utf-8", "ignore"))
            except Exception:
                continue
            text = self._extract_text(obj)
            if text:
                results.append(text)
        return results

    def last_response(self) -> Optional[str]:
        """Zwróć OSTATNIĄ wypowiedź tekstową Claude'a z bieżącej sesji.

        Używane przez przycisk 🔊 (ręczne "czytaj"), gdy nie ma zaznaczenia
        ani zaległości. Czyta cały plik sesji — w sam raz na akcję na żądanie.
        """
        self._ensure_session()
        if not self._session_file or not os.path.exists(self._session_file):
            return None
        last = None
        try:
            with open(self._session_file, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    t = self._extract_text(obj)
                    if t:
                        last = t
        except Exception:
            return None
        return last

    @staticmethod
    def _extract_text(obj: dict) -> Optional[str]:
        """Wyciągnij prozę z wpisu, jeśli to wypowiedź tekstowa głównego agenta."""
        if obj.get("type") != "assistant":
            return None
        if obj.get("isSidechain"):
            return None
        msg = obj.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            return None
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if t:
                    parts.append(t)
        if not parts:
            return None
        return "\n\n".join(parts)
