#!/usr/bin/env python3
"""Test silnika paczki 'mózgu' (agent_bundle) + CloudProvider — bez sieci."""
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core.cloud import agent_bundle as ab
from core.cloud.cloud_provider import InMemoryProvider
from core.agent_skills_settings import AgentSkillsSettings

SECRET = "TOPSECRET-groq-XYZ-should-never-leak"
fails = []
def check(cond, msg):
    print(("[PASS] " if cond else "[FAIL] ") + msg)
    if not cond:
        fails.append(msg)

tmp = Path(tempfile.mkdtemp())
# --- źródłowe urządzenie ---
src_cfg = tmp / "src_config"; src_cfg.mkdir()
proj_base = tmp / "Projekty"; proj_base.mkdir()
proj = proj_base / "moj-projekt"; proj.mkdir()

# repo git z origin + commit (żeby _git_info miało remote i branch)
def git(*a): subprocess.run(["git", "-C", str(proj), *a], capture_output=True, check=False)
git("init", "-q")
git("remote", "add", "origin", "git@github.com:test/moj-projekt.git")
(proj / "CLAUDE-PROJ.md").write_text("# pamięć w repo (przyjdzie z git clone)\n", encoding="utf-8")
git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")

# plik pamięci WSPÓLNY, POZA projektem (nie w git) → powinien być zapisany na imporcie
(proj_base / "CLAUDE-SHARED.md").write_text("# wspólny mózg\n", encoding="utf-8")

# wyłączony skill dla katalogu (gating do przechwycenia)
AgentSkillsSettings(proj).set_disabled_global_skills(["jakis-skill"])

# agents.json
agents = [{
    "id": "a1", "name": "Agent Ż", "working_directory": str(proj),
    "memory_files": [str(proj_base / "CLAUDE-SHARED.md"), str(proj / "CLAUDE-PROJ.md")],
    "auto_start": False, "send_memory_on_start": True, "model": "default",
    "icon": {"kind": "emoji", "value": "🧪"}, "tab_color": "#7c3aed",
    "tts_voice": "pl-PL-MarekNeural", "splitter_sizes": [1500, 190],
}]
(src_cfg / "agents.json").write_text(json.dumps(agents), encoding="utf-8")
(src_cfg / "config.json").write_text(json.dumps({
    "language": "pl", "auto_read": True, "skin_version": 2,
    "groq_api_key": SECRET, "anthropic_api_key": SECRET, "claude_command": "/local/path/claude",
    "last_active_agent_id": "a1",
}), encoding="utf-8")
(src_cfg / "memory_projects.json").write_text(json.dumps({"proj": ["x"]}), encoding="utf-8")
(src_cfg / "quick_actions.json").write_text(json.dumps([{"label": "Test"}]), encoding="utf-8")

# ================= EKSPORT =================
data = ab.export_bundle(config_dir=src_cfg)
check(isinstance(data, bytes) and len(data) > 0, "export_bundle zwrócił bajty")
check(SECRET.encode() not in data, "SEKRET NIE występuje w bajtach paczki")
check(b"claude_command" not in data and b"/local/path/claude" not in data,
      "claude_command (ścieżka lokalna) NIE w paczce")

with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
    man = json.loads(zf.read("manifest.json"))
check("groq_api_key" not in man["config"] and "anthropic_api_key" not in man["config"],
      "manifest.config bez kluczy API")
check(man["config"].get("language") == "pl" and man["config"].get("skin_version") == 2,
      "manifest.config MA przenośne pola (language, skin_version)")
ae = man["agents"][0]
check(ae["git"] and ae["git"]["remote"] == "git@github.com:test/moj-projekt.git",
      "git remote przechwycony")
check(ae["disabled_skills"] == ["jakis-skill"], "wyłączony skill przechwycony")

# ================= IMPORT (nowe urządzenie) =================
dst_cfg = tmp / "dst_config"; dst_cfg.mkdir()
# na nowym urządzeniu user ma JUŻ swój lokalny klucz — import NIE może go skasować
(dst_cfg / "config.json").write_text(json.dumps({"groq_api_key": "LOCALKEY", "language": "en"}), encoding="utf-8")
new_root = tmp / "NowyKomputer" / "Projekty"; new_root.mkdir(parents=True)

summary = ab.import_bundle(data, project_root=new_root, config_dir=dst_cfg)
new_agents = json.loads((dst_cfg / "agents.json").read_text())
new_wd = new_agents[0]["working_directory"]
check(new_wd == str(new_root / "moj-projekt"), "working_directory przemapowany na nowy root")
check(summary["agents_imported"] == 1, "1 agent zaimportowany")
check(any(c["remote"] == "git@github.com:test/moj-projekt.git" for c in summary["clone"]),
      "podsumowanie zawiera git clone")

shared_new = new_root / "CLAUDE-SHARED.md"
check(shared_new.exists() and "wspólny mózg" in shared_new.read_text(),
      "wspólny plik pamięci (poza repo) ZAPISANY na nowym urządzeniu")
proj_mem_new = Path(new_wd) / "CLAUDE-PROJ.md"
check(not proj_mem_new.exists(), "plik pamięci W REPO NIE nadpisany (przyjdzie z git clone)")

dst_conf = json.loads((dst_cfg / "config.json").read_text())
check(dst_conf.get("groq_api_key") == "LOCALKEY", "lokalny klucz API zachowany (nie skasowany importem)")
check(dst_conf.get("language") == "pl", "przenośne 'language' nadpisane z paczki")

# ================= CloudProvider (atrapa) =================
prov = InMemoryProvider()
prov.auth()
prov.upload("brain.vcabundle", data)
check(prov.list() == ["brain.vcabundle"], "atrapa: upload + list")
check(prov.download("brain.vcabundle") == data, "atrapa: download == to co wysłane")
prov.delete("brain.vcabundle")
check(prov.list() == [], "atrapa: delete")

print("\n=== WYNIK:", "WSZYSTKO OK" if not fails else f"{len(fails)} FAIL ===")
sys.exit(1 if fails else 0)
