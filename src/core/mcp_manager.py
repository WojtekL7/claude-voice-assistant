"""
MCP Manager - lokalne zarządzanie serwerami MCP Claude Code.

Operuje przez oficjalne CLI `claude mcp` (add/list/remove/get/add-json).
Stan serwerów jest zapisywany przez Claude Code w `~/.claude.json`:
  - top-level `mcpServers`        → scope "user"  (globalny)
  - `projects.<path>.mcpServers`  → scope "local" (per katalog)

Niektóre serwery (np. zarządzane przez claude.ai — Drive/Calendar/Gmail)
pojawiają się na liście, ale nie są w pliku konfiguracyjnym — są
oznaczane jako "managed" i nie można ich usuwać tym CLI.
"""
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


CLAUDE_CONFIG_FILE = Path.home() / ".claude.json"

# Status z `claude mcp list` (po dwukropku)
STATUS_CONNECTED = "connected"
STATUS_NEEDS_AUTH = "needs_auth"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"

# Dozwolone scope dla `claude mcp add/remove`
VALID_SCOPES = ("local", "user", "project")

# Linia z `claude mcp list`:  "<name>: <command_or_url> - <status_text>"
# Statusy ze znakami: "✓ Connected", "✗ Failed to connect", "! Needs authentication"
_LIST_LINE_RE = re.compile(
    r"^(?P<name>.+?):\s+(?P<target>.+?)\s+-\s+(?P<status>.+?)\s*$"
)


class McpError(Exception):
    """Raised when an MCP CLI operation fails."""


@dataclass
class McpServer:
    name: str
    transport: str = "stdio"          # "stdio" | "http" | "sse"
    target: str = ""                  # command (stdio) lub URL (http/sse)
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    status: str = STATUS_UNKNOWN
    status_text: str = ""             # surowy tekst z `claude mcp list`
    scope: str = "local"              # "local" | "user" | "managed"
    managed: bool = False             # True jeśli nie ma w ~/.claude.json (np. claude.ai)

    @property
    def sanitized_name(self) -> str:
        """Nazwa po sanityzacji do reguł permissions (mcp__<name>__*)."""
        return sanitize_mcp_name(self.name)


def sanitize_mcp_name(name: str) -> str:
    """Zamienia spacje, kropki i inne znaki specjalne na podkreślenia.

    Zgodne z konwencją Claude Code: tooli MCP są nazywane
    `mcp__<sanitized_server_name>__<tool_name>`. Sanityzacja musi być
    deterministyczna i identyczna z tym, co robi sam Claude Code.
    """
    # Zachowujemy litery/cyfry/podkreślenia, resztę zamieniamy na '_'.
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


class McpManager:
    """Wrapper na `claude mcp` CLI."""

    def __init__(self, command: str = "claude", working_dir: Optional[Path] = None):
        self.command = command
        # Working dir wpływa na to, w którym "projekcie" zapisuje się scope=local.
        self.working_dir = Path(working_dir) if working_dir else None

    # ---------- Public API ----------

    def list_servers(self) -> List[McpServer]:
        """Zwraca listę wszystkich skonfigurowanych serwerów MCP."""
        # 1) Pobierz info o "managed" serwerach (np. claude.ai) z `claude mcp list`
        text = self._run(["mcp", "list"], allow_nonzero=True)
        listed = self._parse_list_output(text)

        # 2) Wczytaj konfigurację Claude Code, żeby ustalić scope, transport, env itd.
        config_index = self._read_config_index()

        # 3) Złącz dane: dla wpisów z config bierzemy szczegóły, dla "managed" zostawiamy z list
        servers: List[McpServer] = []
        seen_names = set()

        for entry in listed:
            name = entry["name"]
            seen_names.add(name)
            cfg_entry = config_index.get(name)
            if cfg_entry is not None:
                srv = self._server_from_config(name, cfg_entry["data"], cfg_entry["scope"])
            else:
                # Serwer nie ma wpisu w pliku — zarządzany zewnętrznie (np. claude.ai)
                srv = McpServer(
                    name=name,
                    target=entry["target"],
                    scope="managed",
                    managed=True,
                )
                # Spróbuj wywnioskować transport po targecie
                srv.transport = "http" if entry["target"].startswith(("http://", "https://")) else "stdio"
            srv.status, srv.status_text = self._classify_status(entry["status"])
            servers.append(srv)

        # 4) Dodaj serwery które są w configu, ale nie pojawiły się w `mcp list`
        # (rzadkie, ale dla pewności)
        for name, cfg_entry in config_index.items():
            if name in seen_names:
                continue
            srv = self._server_from_config(name, cfg_entry["data"], cfg_entry["scope"])
            servers.append(srv)

        servers.sort(key=lambda s: (s.scope != "user", s.scope != "local", s.name.lower()))
        return servers

    def get(self, name: str) -> Optional[McpServer]:
        """Zwraca szczegóły serwera z `~/.claude.json` (lub None jeśli nie ma)."""
        config_index = self._read_config_index()
        entry = config_index.get(name)
        if entry is None:
            return None
        return self._server_from_config(name, entry["data"], entry["scope"])

    def add_stdio(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        scope: str = "local",
    ) -> None:
        """Dodaje serwer stdio: `claude mcp add -s <scope> [-e ...] <name> -- <command> [args...]`."""
        self._validate_scope(scope)
        cmd = ["mcp", "add", "-s", scope]
        for k, v in (env or {}).items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [name, "--", command]
        if args:
            cmd += list(args)
        self._run(cmd)

    def add_http(
        self,
        name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        scope: str = "local",
    ) -> None:
        """Dodaje serwer HTTP: `claude mcp add --transport http -s <scope> [-H ...] <name> <url>`."""
        self._validate_scope(scope)
        cmd = ["mcp", "add", "--transport", "http", "-s", scope]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        cmd += [name, url]
        self._run(cmd)

    def add_sse(
        self,
        name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        scope: str = "local",
    ) -> None:
        """Dodaje serwer SSE — analogicznie do add_http."""
        self._validate_scope(scope)
        cmd = ["mcp", "add", "--transport", "sse", "-s", scope]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        cmd += [name, url]
        self._run(cmd)

    def add_from_json(self, name: str, json_str: str, scope: str = "local") -> None:
        """Dodaje serwer z JSON: `claude mcp add-json -s <scope> <name> '<json>'`."""
        self._validate_scope(scope)
        # Walidacja JSON wcześniej — jeśli źle, lepszy komunikat dla użytkownika.
        try:
            json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise McpError(f"Nieprawidłowy JSON: {exc}")
        self._run(["mcp", "add-json", "-s", scope, name, json_str])

    def remove(self, name: str, scope: Optional[str] = None) -> None:
        """Usuwa serwer. Bez scope — Claude Code sam wybiera ten, w którym istnieje."""
        cmd = ["mcp", "remove"]
        if scope is not None:
            self._validate_scope(scope)
            cmd += ["-s", scope]
        cmd += [name]
        self._run(cmd)

    # ---------- Helpers ----------

    def _run(self, args: List[str], *, allow_nonzero: bool = False) -> str:
        """Wykonuje `claude <args...>` i zwraca stdout. Rzuca McpError przy błędzie."""
        try:
            result = subprocess.run(
                [self.command] + args,
                capture_output=True,
                text=True,
                cwd=str(self.working_dir) if self.working_dir else None,
                timeout=60,
            )
        except FileNotFoundError:
            raise McpError(
                f"Nie znaleziono komendy '{self.command}'. "
                "Czy Claude Code jest zainstalowany?"
            )
        except subprocess.TimeoutExpired:
            raise McpError("Komenda 'claude mcp' przekroczyła limit czasu (60s).")

        if result.returncode != 0 and not allow_nonzero:
            err = (result.stderr or result.stdout or "").strip()
            raise McpError(f"`claude {' '.join(args)}` zwróciło błąd: {err}")

        return result.stdout or ""

    @staticmethod
    def _validate_scope(scope: str) -> None:
        if scope not in VALID_SCOPES:
            raise McpError(
                f"Nieprawidłowy scope '{scope}'. Dozwolone: {', '.join(VALID_SCOPES)}."
            )

    @staticmethod
    def _parse_list_output(text: str) -> List[dict]:
        """Parsuje wyjście `claude mcp list` na listę dictów."""
        items = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("checking mcp"):
                continue
            match = _LIST_LINE_RE.match(line)
            if not match:
                continue
            items.append({
                "name": match.group("name").strip(),
                "target": match.group("target").strip(),
                "status": match.group("status").strip(),
            })
        return items

    @staticmethod
    def _classify_status(raw: str) -> tuple:
        """Mapuje surowy tekst statusu na (kod, oryginał)."""
        low = raw.lower()
        if "connected" in low and "failed" not in low:
            return STATUS_CONNECTED, raw
        if "auth" in low:
            return STATUS_NEEDS_AUTH, raw
        if "fail" in low or "error" in low:
            return STATUS_FAILED, raw
        return STATUS_UNKNOWN, raw

    @staticmethod
    def _read_config_index() -> Dict[str, Dict]:
        """Czyta ~/.claude.json i zwraca {server_name: {scope, data}}.

        Sklejamy serwery z user-scope (top-level) i ze wszystkich projektów
        (local-scope). Jeśli ta sama nazwa jest w obu — wygrywa user.
        """
        result: Dict[str, Dict] = {}
        if not CLAUDE_CONFIG_FILE.exists():
            return result
        try:
            data = json.loads(CLAUDE_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return result

        # local scope (per-projekt)
        for project_path, project_data in (data.get("projects") or {}).items():
            if not isinstance(project_data, dict):
                continue
            for srv_name, srv_data in (project_data.get("mcpServers") or {}).items():
                if srv_name not in result:
                    result[srv_name] = {"scope": "local", "data": srv_data, "project_path": project_path}

        # user scope (top-level) — nadpisuje local jeśli ta sama nazwa
        for srv_name, srv_data in (data.get("mcpServers") or {}).items():
            result[srv_name] = {"scope": "user", "data": srv_data}

        return result

    @staticmethod
    def _server_from_config(name: str, data: dict, scope: str) -> McpServer:
        """Tworzy McpServer z wpisu w ~/.claude.json."""
        transport = (data.get("type") or "stdio").lower()
        if transport in ("http", "sse"):
            target = data.get("url", "")
        else:
            cmd_parts = [data.get("command", "")] + list(data.get("args") or [])
            target = " ".join(p for p in cmd_parts if p)

        return McpServer(
            name=name,
            transport=transport,
            target=target,
            args=list(data.get("args") or []),
            env=dict(data.get("env") or {}),
            headers=dict(data.get("headers") or {}),
            scope=scope,
        )
