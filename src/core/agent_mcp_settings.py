"""
AgentMcpSettings — per-agent włączanie/wyłączanie globalnych serwerów MCP
poprzez `permissions.deny` w pliku <working_dir>/.claude/settings.local.json.

Claude Code natywnie odczytuje ten plik. Reguła `mcp__<sanitized>__*`
w sekcji `permissions.deny` blokuje wszystkie tools danego serwera MCP
dla tego konkretnego katalogu (czyli dla tego agenta).

Operacje są bezpieczne dla istniejących reguł — modyfikujemy wyłącznie
wpisy typu `mcp__<name>__*`, pozostawiając resztę (Bash, Skill, itp.) bez zmian.

Sanityzacja nazwy MUSI być zgodna z `core.mcp_manager.sanitize_mcp_name`.
"""
import json
import re
from pathlib import Path
from typing import List, Optional

from core.mcp_manager import sanitize_mcp_name


# Reguła deny dla MCP — np. "mcp__claude_ai_Gmail__*" albo "mcp__n8n_server__*"
MCP_RULE_PATTERN = re.compile(r"^\s*mcp__(?P<name>[A-Za-z0-9_]+)__\*\s*$")


class AgentMcpSettings:
    """Zarządza wyłączonymi serwerami MCP w settings.local.json wybranego katalogu."""

    def __init__(self, working_dir: Path):
        self.working_dir = Path(working_dir)
        self.settings_path = self.working_dir / ".claude" / "settings.local.json"

    # ---------- Public API ----------

    def get_disabled_mcp_sanitized(self) -> List[str]:
        """Zwraca listę zsanityzowanych nazw serwerów MCP wyłączonych dla tego agenta."""
        data = self._read_settings()
        deny = self._extract_deny_list(data)
        return self._extract_mcp_sanitized_names(deny)

    def set_disabled_mcp_servers(self, server_names: List[str]) -> None:
        """Zapisuje dokładnie taki zestaw wyłączonych serwerów MCP (po nazwach oryginalnych).

        Zachowuje wszystkie pozostałe reguły deny (Skill(...), Bash(...), itp.).
        """
        data = self._read_settings()
        permissions = data.setdefault("permissions", {})
        old_deny = permissions.get("deny", []) or []

        # Zachowaj wszystkie reguły niezwiązane z mcp__*__*
        non_mcp_rules = [
            rule for rule in old_deny
            if not isinstance(rule, str) or MCP_RULE_PATTERN.match(rule) is None
        ]
        # Dodaj nowe mcp__<sanitized>__* reguły
        sanitized = sorted({sanitize_mcp_name(n) for n in server_names if n})
        new_mcp_rules = [f"mcp__{s}__*" for s in sanitized]
        permissions["deny"] = non_mcp_rules + new_mcp_rules

        # Wyczyść puste 'deny' żeby nie zaśmiecać pliku
        if not permissions["deny"]:
            permissions.pop("deny", None)
        if not permissions:
            data.pop("permissions", None)

        self._write_settings(data)

    def is_disabled(self, server_name: str) -> bool:
        return sanitize_mcp_name(server_name) in self.get_disabled_mcp_sanitized()

    def disable(self, server_name: str) -> None:
        sanitized = sanitize_mcp_name(server_name)
        current = self.get_disabled_mcp_sanitized()
        if sanitized not in current:
            self._set_sanitized(current + [sanitized])

    def enable(self, server_name: str) -> None:
        sanitized = sanitize_mcp_name(server_name)
        current = self.get_disabled_mcp_sanitized()
        if sanitized in current:
            current.remove(sanitized)
            self._set_sanitized(current)

    # ---------- Helpers ----------

    def _set_sanitized(self, sanitized_names: List[str]) -> None:
        """Wewnętrzny zapis listy zsanityzowanych nazw (omijając ponowną sanityzację)."""
        data = self._read_settings()
        permissions = data.setdefault("permissions", {})
        old_deny = permissions.get("deny", []) or []
        non_mcp_rules = [
            rule for rule in old_deny
            if not isinstance(rule, str) or MCP_RULE_PATTERN.match(rule) is None
        ]
        new_rules = [f"mcp__{s}__*" for s in sorted(set(sanitized_names))]
        permissions["deny"] = non_mcp_rules + new_rules
        if not permissions["deny"]:
            permissions.pop("deny", None)
        if not permissions:
            data.pop("permissions", None)
        self._write_settings(data)

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
    def _extract_mcp_sanitized_names(deny_list: list) -> List[str]:
        names = []
        for rule in deny_list:
            if not isinstance(rule, str):
                continue
            match = MCP_RULE_PATTERN.match(rule)
            if match:
                names.append(match.group("name"))
        return names
