"""
AgentSkillsSettings — per-agent włączanie/wyłączanie globalnych skilli
poprzez `permissions.deny` w pliku <working_dir>/.claude/settings.local.json.

Claude Code natywnie odczytuje ten plik. Reguła `Skill(<nazwa>)` w sekcji
`permissions.deny` blokuje aktywację konkretnego skilla — niezależnie czy
pochodzi z ~/.claude/skills/ czy z <working_dir>/.claude/skills/.

Operacje są bezpieczne dla istniejących reguł — modyfikujemy tylko wpisy
typu `Skill(*)`, pozostawiając resztę bez zmian.
"""
import json
import re
from pathlib import Path
from typing import List, Optional


# Reguła deny dla skilli — np. "Skill(pdf)" albo "Skill(pdf *)"
SKILL_RULE_PATTERN = re.compile(r"^\s*Skill\(\s*([^\s)*]+)(?:\s+\*)?\s*\)\s*$")


class AgentSkillsSettings:
    """Zarządza wyłączonymi skillami w settings.local.json wybranego katalogu."""

    def __init__(self, working_dir: Path):
        self.working_dir = Path(working_dir)
        self.settings_path = self.working_dir / ".claude" / "settings.local.json"

    # ---------- Public API ----------

    def get_disabled_global_skills(self) -> List[str]:
        """Zwróć listę nazw skilli wpisanych w permissions.deny jako Skill(...)."""
        data = self._read_settings()
        deny = self._extract_deny_list(data)
        return self._extract_skill_names(deny)

    def set_disabled_global_skills(self, skill_names: List[str]) -> None:
        """Zapisz dokładnie taki zestaw wyłączonych skilli, zachowując pozostałe reguły."""
        data = self._read_settings()
        permissions = data.setdefault("permissions", {})
        old_deny = permissions.get("deny", []) or []

        # Zachowaj wszystkie reguły niezwiązane ze Skill(...)
        non_skill_rules = [
            rule for rule in old_deny
            if not isinstance(rule, str) or SKILL_RULE_PATTERN.match(rule) is None
        ]
        # Dodaj nowe Skill(...) reguły
        new_skill_rules = [f"Skill({name})" for name in sorted(set(skill_names))]
        permissions["deny"] = non_skill_rules + new_skill_rules

        # Wyczyść puste 'deny' żeby nie zaśmiecać pliku
        if not permissions["deny"]:
            permissions.pop("deny", None)
        if not permissions:
            data.pop("permissions", None)

        self._write_settings(data)

    def is_disabled(self, skill_name: str) -> bool:
        return skill_name in self.get_disabled_global_skills()

    def disable(self, skill_name: str) -> None:
        current = self.get_disabled_global_skills()
        if skill_name not in current:
            current.append(skill_name)
            self.set_disabled_global_skills(current)

    def enable(self, skill_name: str) -> None:
        current = self.get_disabled_global_skills()
        if skill_name in current:
            current.remove(skill_name)
            self.set_disabled_global_skills(current)

    # ---------- Helpers ----------

    def _read_settings(self) -> dict:
        if not self.settings_path.exists():
            return {}
        try:
            with self.settings_path.open(encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                data = json.loads(content)
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            # Cichy fallback — nie wywalamy aplikacji przy uszkodzonym pliku.
            # Lepiej traktować jak pusty niż próbować naprawić "na siłę".
            return {}

    def _write_settings(self, data: dict) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp file + rename (chroni przed uszkodzeniem przy crashu)
        tmp_path = self.settings_path.with_suffix(self.settings_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        tmp_path.replace(self.settings_path)

    @staticmethod
    def _extract_deny_list(data: dict) -> list:
        permissions = data.get("permissions") if isinstance(data, dict) else None
        if not isinstance(permissions, dict):
            return []
        deny = permissions.get("deny", [])
        return deny if isinstance(deny, list) else []

    @staticmethod
    def _extract_skill_names(deny_list: list) -> List[str]:
        names = []
        for rule in deny_list:
            if not isinstance(rule, str):
                continue
            match = SKILL_RULE_PATTERN.match(rule)
            if match:
                names.append(match.group(1))
        return names
