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

BUNDLE_VERSION = 2   # v2: definicje skilli + (warunkowo) sekrety w paczce SZYFROWANEJ

# BIAŁA lista (bezpieczniej niż czarna): TYLKO te pola config.json trafiają do
# chmury. Każdy inny/nowy/nieznany klucz jest domyślnie pomijany, więc przypadkiem
# dodany sekret NIE wycieknie.
PORTABLE_CONFIG_KEYS = frozenset({
    "language", "auto_read", "skin_version", "skin_colors", "skin_icons",
    "auto_check_updates", "dictation_reminder_dismissed",
})

# Pola wrażliwe. Domyślnie ZAKAZANE w paczce (druga linia obrony — twarda asercja).
# Wchodzą WYŁĄCZNIE ścieżką `export_sealed()`, czyli tylko gdy paczka jest realnie
# zaszyfrowana. Decyzja usera 2026-07-20: „nowy komputer ma działać bez wpisywania
# czegokolwiek" — patrz `docs/PLAN-CHMURA-SYNC.md` sekcja 9.
SECRET_CONFIG_KEYS = frozenset({
    "groq_api_key", "anthropic_api_key",
})
# `claude_command` NIE jest sekretem, ale jest ŚCIŚLE lokalny (ścieżka do binarki
# różna na każdym systemie — patrz pułapka „claude zepsuty/niezgodny na Windows”).
# Nigdy nie przenosimy go między urządzeniami.
LOCAL_ONLY_CONFIG_KEYS = frozenset({"claude_command"})

FORBIDDEN_CONFIG_KEYS = SECRET_CONFIG_KEYS | LOCAL_ONLY_CONFIG_KEYS

# Ile najwyżej bajtów definicji skilli pakujemy (ochrona przed wrzuceniem do
# ~/.claude/skills/ czegoś wielkiego — paczka ma zostać „mózgiem", nie archiwum).
MAX_SKILL_BYTES = 2 * 1024 * 1024


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


def _assert_no_secrets(manifest: dict, *, allow_secrets: bool = False) -> None:
    """Bezpiecznik sekretów — WARUNKOWY od 2026-07-20.

    `allow_secrets=True` wolno podać WYŁĄCZNIE z `export_sealed()`, które gwarantuje,
    że wynik zostanie zaszyfrowany. `claude_command` (lokalna ścieżka do binarki) jest
    blokowany ZAWSZE — nie jest sekretem, ale przeniesiony na inny system psuje apkę.
    """
    banned = LOCAL_ONLY_CONFIG_KEYS if allow_secrets else FORBIDDEN_CONFIG_KEYS
    leaked = banned & set(manifest.get("config", {}))
    if leaked:
        raise RuntimeError(f"Filtr sekretów zablokował wysyłkę pól: {sorted(leaked)}")


def _collect_skills(zf: zipfile.ZipFile) -> List[dict]:
    """Spakuj definicje skilli z `~/.claude/skills/<nazwa>/` (pliki tekstowe).

    Skille to zwykłe pliki tekstowe (instrukcje) — pakujemy ich TREŚĆ, żeby na nowym
    urządzeniu agent miał komplet umiejętności bez ręcznego odtwarzania. Pomijamy
    pliki binarne i zbyt duże (paczka ma zostać „mózgiem", nie archiwum).
    """
    from core.skills_manager import SKILLS_DIR
    out: List[dict] = []
    if not SKILLS_DIR.is_dir():
        return out
    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        files: List[dict] = []
        for f in sorted(skill_dir.rglob("*")):
            if not f.is_file():
                continue
            try:
                if f.stat().st_size > MAX_SKILL_BYTES:
                    continue
                content = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # binarny/nieczytelny — pomijamy świadomie
            name = f"skills/{skill_dir.name}/{f.relative_to(skill_dir).as_posix()}"
            zf.writestr(name, content)
            files.append({"rel": f.relative_to(skill_dir).as_posix(), "stored": name})
        if files:
            out.append({"name": skill_dir.name, "files": files})
    return out


def _is_inside(child: Path, parent: str) -> Optional[Path]:
    """Zwraca ścieżkę względną, gdy `child` leży w `parent`; inaczej None."""
    if not parent:
        return None
    try:
        return child.relative_to(parent)
    except ValueError:
        return None


# ------------------------------------------------------------------ eksport

def export_bundle(config_dir: Optional[Path] = None, *,
                  include_secrets: bool = False,
                  include_skills: bool = True) -> bytes:
    """Zbuduj paczkę 'mózgu' (bajty zip) ze WSZYSTKICH agentów.

    ⚠️ `include_secrets=True` produkuje paczkę JAWNĄ z kluczami API — wolno tego użyć
    wyłącznie wewnątrz `export_sealed()`, które od razu ją szyfruje. Nie wołaj tego
    wprost z UI ani nie zapisuj wyniku na dysk.
    """
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

        bundled_config = _portable_config(config)
        if include_secrets:
            for k in SECRET_CONFIG_KEYS:
                if config.get(k):
                    bundled_config[k] = config[k]

        manifest = {
            "bundle_version": BUNDLE_VERSION,
            "app": "vibe-coding-assistant",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "contains_secrets": bool(include_secrets),
            "agents": agent_entries,
            "config": bundled_config,
            "skills": _collect_skills(zf) if include_skills else [],
            "memory_projects": memory_projects,
            "quick_actions": quick_actions,
        }
        _assert_no_secrets(manifest, allow_secrets=include_secrets)
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return buf.getvalue()


# ------------------------------------- eksport/import ZAPIECZĘTOWANY (do chmury)

def export_sealed(passphrase: str, config_dir: Optional[Path] = None, *,
                  include_secrets: bool = True) -> bytes:
    """JEDYNA droga, którą sekrety mogą trafić do chmury — i tylko zaszyfrowane.

    Inwariant (patrz `docs/PLAN-CHMURA-SYNC.md` 9.2): paczka z kluczami API opuszcza
    tę funkcję WYŁĄCZNIE zaszyfrowana. Dlatego po zaszyfrowaniu **weryfikujemy wynik**:
    czy jest opieczętowany i czy da się go odczytać z powrotem tym samym hasłem. Gdy
    cokolwiek zawiedzie — wyjątek, nigdy cicha wysyłka otwartym tekstem.

    Kosztuje to jedno dodatkowe odszyfrowanie (ułamek sekundy przy paczce rzędu setek
    KB), a chroni przed najgorszym możliwym błędem tej funkcji.
    """
    from core.cloud import bundle_crypto as bc

    if not passphrase:
        raise RuntimeError(
            "Brak hasła szyfrującego — odmawiam wysyłki. "
            "Paczka z kluczami API nigdy nie może pójść do chmury niezaszyfrowana.")

    plain = export_bundle(config_dir, include_secrets=include_secrets)
    sealed = bc.seal(plain, passphrase)

    # --- weryfikacja wyniku (nie ufamy sobie na słowo) ---
    if not bc.is_sealed(sealed):
        raise RuntimeError("Szyfrowanie nie powiodło się — odmawiam wysyłki.")
    if include_secrets:
        try:
            roundtrip = bc.unseal(sealed, passphrase)
        except Exception as exc:
            raise RuntimeError(
                f"Paczka nie daje się odszyfrować po zaszyfrowaniu ({exc}) — odmawiam wysyłki."
            ) from exc
        if roundtrip != plain:
            raise RuntimeError("Odszyfrowana paczka różni się od źródłowej — odmawiam wysyłki.")
        # Ostateczny sprawdzian na BAJTACH: żaden klucz nie może być widoczny w tym,
        # co realnie poleci do chmury.
        cfg = _load_json(Path(config_dir or _default_config_dir()) / "config.json", {})
        for key_name in SECRET_CONFIG_KEYS:
            value = cfg.get(key_name)
            if value and isinstance(value, str) and value.encode("utf-8") in sealed:
                raise RuntimeError(
                    f"Klucz '{key_name}' widoczny w zaszyfrowanej paczce — odmawiam wysyłki.")
    return sealed


def import_sealed(data: bytes, passphrase: str, project_root,
                  config_dir: Optional[Path] = None) -> dict:
    """Odszyfruj paczkę z chmury i odtwórz agentów na tym urządzeniu."""
    from core.cloud import bundle_crypto as bc

    if not bc.is_sealed(data):
        raise RuntimeError("To nie jest zaszyfrowana paczka Vibe Coding Assistant.")
    return import_bundle(bc.unseal(data, passphrase), project_root, config_dir)


# ------------------------------------------------------------------ import

def _restore_skills(manifest: dict, contents: dict) -> List[str]:
    """Odtwórz definicje skilli w `~/.claude/skills/`. NIE nadpisuje istniejących.

    Ostrożność celowa: lokalny skill mógł zostać ręcznie poprawiony na tym urządzeniu,
    a import ma dokładać brakujące umiejętności, nie kasować cudzą pracę.
    """
    from core.skills_manager import SKILLS_DIR
    written: List[str] = []
    for skill in manifest.get("skills", []) or []:
        target_dir = SKILLS_DIR / skill.get("name", "")
        if target_dir.exists():
            continue
        for f in skill.get("files", []):
            stored = f.get("stored", "")
            if stored not in contents:
                continue
            dest = target_dir / f["rel"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(contents[stored], encoding="utf-8")
            written.append(str(dest))
    return written


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
        skill_contents = {
            n: zf.read(n).decode("utf-8")
            for n in zf.namelist() if n.startswith("skills/")
        }

    summary: dict = {
        "agents_imported": 0, "clone": [], "memory_written": [],
        "apply_after_clone": [], "warnings": [],
        "skills_written": [], "secrets_applied": [],
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

    summary["skills_written"] = _restore_skills(manifest, skill_contents)

    _merge_portable_config(config_dir / "config.json", manifest.get("config", {}))
    # Sekrety (jeśli paczka je niosła — czyli była zaszyfrowana) wchodzą OSOBNO,
    # żeby ta gałąź była widoczna w kodzie i w podsumowaniu dla usera.
    incoming_secrets = {
        k: v for k, v in (manifest.get("config") or {}).items()
        if k in SECRET_CONFIG_KEYS and v
    }
    if incoming_secrets:
        cfg_path = config_dir / "config.json"
        cfg = _load_json(cfg_path, {})
        for k, v in incoming_secrets.items():
            cfg[k] = v          # nadpisujemy świadomie: to jest SYNCHRONIZACJA
            summary["secrets_applied"].append(k)
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    if manifest.get("memory_projects"):
        (config_dir / "memory_projects.json").write_text(
            json.dumps(manifest["memory_projects"], ensure_ascii=False, indent=2), encoding="utf-8")
    if manifest.get("quick_actions"):
        (config_dir / "quick_actions.json").write_text(
            json.dumps(manifest["quick_actions"], ensure_ascii=False, indent=2), encoding="utf-8")

    return summary
