"""Silnik paczki 'mózgu' agenta — eksport/import BEZ sekretów.

Rozdziela **'mózg'** agenta (mały, cenny: ustawienia + pamięć + które skille/MCP
wyłączone) od **'kodu'** projektów (duży, w git). Do chmury idzie tylko mózg; kod
odtwarzamy `git clone`. Sekrety (klucze API, login Claude) NIGDY nie wchodzą do paczki.

Moduł NIE zna sieci ani UI — operuje na bajtach paczki (zip w pamięci) i katalogu
konfiguracji. Chmurę obsługuje osobno `CloudProvider`. Ścieżki (`config_dir`,
`project_root`) są parametrami → w pełni testowalne na katalogach tymczasowych.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Absolutne importy (src na sys.path) — zgodnie z regułą projektu (nie względne).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core.agent_skills_settings import AgentSkillsSettings  # noqa: E402
from core.agent_mcp_settings import AgentMcpSettings  # noqa: E402

BUNDLE_VERSION = 1

# BIAŁA lista (bezpieczniej niż czarna): TYLKO te pola config.json trafiają do
# chmury. Każdy inny/nowy/nieznany klucz jest domyślnie pomijany, więc przypadkiem
# dodany sekret NIE wycieknie.
PORTABLE_CONFIG_KEYS = frozenset({
    "language", "auto_read", "skin_version", "skin_colors", "skin_icons",
    "auto_check_updates", "dictation_reminder_dismissed",
})

# Pola, których obecność w paczce = BŁĄD (druga linia obrony — twarda asercja).
FORBIDDEN_CONFIG_KEYS = frozenset({
    "groq_api_key", "anthropic_api_key", "claude_command",
})


# ------------------------------------------------------------------ pomocnicze

def _default_config_dir() -> Path:
    from config import CONFIG_DIR
    return CONFIG_DIR


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _git_info(working_dir: Path) -> Optional[dict]:
    """`{remote, branch}` katalogu, albo None gdy to nie repo git / brak origin."""
    if not (working_dir / ".git").exists():
        return None

    def _git(*args) -> str:
        try:
            out = subprocess.run(
                ["git", "-C", str(working_dir), *args],
                capture_output=True, text=True, timeout=5)
            return out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    remote = _git("remote", "get-url", "origin")
    if not remote:
        return None
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    return {"remote": remote, "branch": branch or "main"}


def _portable_config(config: dict) -> dict:
    return {k: config[k] for k in PORTABLE_CONFIG_KEYS if k in config}


def _assert_no_secrets(manifest: dict) -> None:
    """Bezpiecznik: nic wrażliwego w sekcji config paczki (poza whitelistą)."""
    leaked = FORBIDDEN_CONFIG_KEYS & set(manifest.get("config", {}))
    if leaked:
        raise RuntimeError(f"Filtr sekretów zablokował wysyłkę pól: {sorted(leaked)}")


def _is_inside(child: Path, parent: str) -> Optional[Path]:
    """Zwraca ścieżkę względną, gdy `child` leży w `parent`; inaczej None."""
    if not parent:
        return None
    try:
        return child.relative_to(parent)
    except ValueError:
        return None


# ------------------------------------------------------------------ eksport

def export_bundle(config_dir: Optional[Path] = None) -> bytes:
    """Zbuduj paczkę 'mózgu' (bajty zip) ze WSZYSTKICH agentów. Bez sekretów."""
    config_dir = Path(config_dir) if config_dir else _default_config_dir()
    agents = _load_json(config_dir / "agents.json", [])
    config = _load_json(config_dir / "config.json", {})
    memory_projects = _load_json(config_dir / "memory_projects.json", {})
    quick_actions = _load_json(config_dir / "quick_actions.json", {})

    buf = io.BytesIO()
    stored_memory: dict = {}  # abs_path(str) -> nazwa wpisu w zipie ("" = brak treści)
    mem_index = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        agent_entries: List[dict] = []
        for agent in agents:
            wd = agent.get("working_directory", "") or ""
            wd_path = Path(wd) if wd else None

            # pliki pamięci -> treść do paczki (deduplikacja po ścieżce)
            mem: List[dict] = []
            for mf in agent.get("memory_files", []) or []:
                p = Path(mf)
                key = str(p)
                if key not in stored_memory:
                    try:
                        content = p.read_text(encoding="utf-8")
                        name = f"memory/{mem_index}"
                        zf.writestr(name, content)
                        stored_memory[key] = name
                        mem_index += 1
                    except (OSError, UnicodeDecodeError):
                        stored_memory[key] = ""  # brak / nie do odczytu
                mem.append({"path": key, "stored": stored_memory[key]})

            # skille/MCP wyłączone dla tego katalogu roboczego
            disabled_skills: List[str] = []
            disabled_mcp: List[str] = []
            if wd_path and wd_path.exists():
                try:
                    disabled_skills = AgentSkillsSettings(wd_path).get_disabled_global_skills()
                    disabled_mcp = AgentMcpSettings(wd_path).get_disabled_mcp_sanitized()
                except Exception:
                    pass

            agent_entries.append({
                "agent": agent,
                "git": _git_info(wd_path) if wd_path else None,
                "disabled_skills": disabled_skills,
                "disabled_mcp": disabled_mcp,
                "memory_files": mem,
            })

        manifest = {
            "bundle_version": BUNDLE_VERSION,
            "app": "vibe-coding-assistant",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "agents": agent_entries,
            "config": _portable_config(config),
            "memory_projects": memory_projects,
            "quick_actions": quick_actions,
        }
        _assert_no_secrets(manifest)
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return buf.getvalue()


# ------------------------------------------------------------------ import

def _merge_portable_config(path: Path, portable: dict) -> None:
    """Nadpisz TYLKO przenośne pola; zachowaj lokalne sekrety/ustawienia urządzenia."""
    existing = _load_json(path, {})
    for k in PORTABLE_CONFIG_KEYS:
        if k in portable:
            existing[k] = portable[k]
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_gating(working_dir: Path, disabled_skills: List[str], disabled_mcp: List[str]) -> None:
    try:
        if disabled_skills:
            AgentSkillsSettings(working_dir).set_disabled_global_skills(disabled_skills)
        if disabled_mcp:
            AgentMcpSettings(working_dir).set_disabled_mcp_servers(disabled_mcp)
    except Exception:
        pass


def import_bundle(data: bytes, project_root, config_dir: Optional[Path] = None) -> dict:
    """Odtwórz agentów z paczki na TYM urządzeniu.

    Ścieżki przemapowane pod `project_root` (nowy katalog projektów). Kod projektów
    NIE jest w paczce — zwracamy listę `git clone` do wykonania. Zwraca podsumowanie.
    """
    project_root = Path(project_root)
    config_dir = Path(config_dir) if config_dir else _default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        mem_contents = {
            n: zf.read(n).decode("utf-8")
            for n in zf.namelist() if n.startswith("memory/")
        }

    summary: dict = {
        "agents_imported": 0, "clone": [], "memory_written": [],
        "apply_after_clone": [], "warnings": [],
    }

    new_agents: List[dict] = []
    for ae in manifest.get("agents", []):
        agent = dict(ae.get("agent", {}))
        old_wd = agent.get("working_directory", "") or ""
        new_wd = str(project_root / Path(old_wd).name) if old_wd else old_wd
        agent["working_directory"] = new_wd
        has_git = bool(ae.get("git"))

        # przemapuj + (warunkowo) zapisz pliki pamięci
        new_mem_paths: List[str] = []
        for mf in ae.get("memory_files", []) or []:
            old_path = Path(mf["path"])
            rel = _is_inside(old_path, old_wd)
            if rel is not None:
                new_path = Path(new_wd) / rel
            else:
                new_path = project_root / old_path.name
            new_mem_paths.append(str(new_path))

            stored = mf.get("stored", "")
            if rel is not None and has_git:
                # plik jest w repo, które i tak sklonujemy → nie nadpisuj (klon w
                # niepusty katalog by się wywalił); przyjdzie z `git clone`.
                continue
            if stored and stored in mem_contents:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                new_path.write_text(mem_contents[stored], encoding="utf-8")
                summary["memory_written"].append(str(new_path))
            else:
                summary["warnings"].append(f"Brak treści pliku pamięci: {old_path}")
        agent["memory_files"] = new_mem_paths
        new_agents.append(agent)

        if has_git:
            summary["clone"].append({**ae["git"], "dir": new_wd})

        wd_path = Path(new_wd) if new_wd else None
        ds, dm = ae.get("disabled_skills", []), ae.get("disabled_mcp", [])
        if wd_path and wd_path.exists():
            _apply_gating(wd_path, ds, dm)
        elif ds or dm:
            summary["apply_after_clone"].append({
                "dir": new_wd, "disabled_skills": ds, "disabled_mcp": dm,
            })

    (config_dir / "agents.json").write_text(
        json.dumps(new_agents, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["agents_imported"] = len(new_agents)

    _merge_portable_config(config_dir / "config.json", manifest.get("config", {}))
    if manifest.get("memory_projects"):
        (config_dir / "memory_projects.json").write_text(
            json.dumps(manifest["memory_projects"], ensure_ascii=False, indent=2), encoding="utf-8")
    if manifest.get("quick_actions"):
        (config_dir / "quick_actions.json").write_text(
            json.dumps(manifest["quick_actions"], ensure_ascii=False, indent=2), encoding="utf-8")

    return summary
