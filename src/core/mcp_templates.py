"""
Predefiniowane szablony serwerów MCP — "instalacja jednym kliknięciem".

Każdy szablon ma:
  - id          : klucz wewnętrzny (unikalny)
  - default_name: domyślna nazwa dla `claude mcp add <name>`
  - title       : nazwa wyświetlana po polsku
  - description : krótki opis funkcji (proste wyjaśnienie)
  - transport   : "stdio" | "http" | "sse"
  - command     : (stdio) komenda do uruchomienia
  - args        : (stdio) argumenty komendy — mogą zawierać placeholdery {VAR}
  - url         : (http/sse) adres serwera
  - env_required: lista par (klucz, etykieta) — pól wymaganych od użytkownika (env)
  - env_optional: lista par (klucz, etykieta) — pól opcjonalnych (env)
  - args_required: lista par (placeholder, etykieta) — placeholdery w args do podstawienia
  - headers_required: lista par (klucz, etykieta) — wymagane nagłówki HTTP
  - install_hint: wskazówka instalacyjna pokazywana w UI (np. "wymaga Node.js")
  - homepage    : URL z dokumentacją serwera

Konwencja placeholderów: w polach `args`/`url`/`headers` używamy `{NAZWA}`,
np. `{PATH}`, `{CONNECTION_STRING}`. Dialog instalatora podstawia wartości
podane przez użytkownika przed wywołaniem `claude mcp add`.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class McpTemplate:
    id: str
    default_name: str
    title: str
    description: str
    transport: str = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""
    env_required: List[Tuple[str, str]] = field(default_factory=list)
    env_optional: List[Tuple[str, str]] = field(default_factory=list)
    args_required: List[Tuple[str, str]] = field(default_factory=list)
    headers_required: List[Tuple[str, str]] = field(default_factory=list)
    install_hint: str = ""
    homepage: str = ""

    def render_args(self, values: Dict[str, str]) -> List[str]:
        """Podstawia wartości w placeholderach {KLUCZ}."""
        out = []
        for arg in self.args:
            for key, val in values.items():
                arg = arg.replace("{" + key + "}", val)
            out.append(arg)
        return out

    def render_url(self, values: Dict[str, str]) -> str:
        url = self.url
        for key, val in values.items():
            url = url.replace("{" + key + "}", val)
        return url

    def render_headers(self, values: Dict[str, str]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key, label in self.headers_required:
            template = label  # label jest tu wzorcem nagłówka
            val = values.get(key, "")
            out[key] = template.replace("{" + key + "}", val) if "{" in template else val
        return out


# ---------- Wbudowane szablony (7 starterów) ----------

MCP_TEMPLATES: List[McpTemplate] = [
    McpTemplate(
        id="filesystem",
        default_name="filesystem",
        title="📁 Filesystem (lokalny dysk)",
        description=(
            "Pozwala agentowi czytać i pisać pliki w wybranym przez Ciebie katalogu. "
            "Idealny do dokumentów firmy, notatek, eksportów. Działa lokalnie — nie wysyła nic do chmury."
        ),
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "{PATH}"],
        args_required=[("PATH", "Katalog dostępny dla agenta (np. /home/user/Dokumenty)")],
        install_hint="Wymaga Node.js (npx). Pakiet zostanie pobrany automatycznie przy pierwszym uruchomieniu.",
        homepage="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
    ),
    McpTemplate(
        id="github",
        default_name="github",
        title="🐙 GitHub",
        description=(
            "Agent czyta repozytoria, tworzy issues i pull requesty, sprawdza status CI. "
            "Wymaga osobistego tokenu GitHub (PAT) — minimalne wymagane uprawnienia: "
            "scope „repo\" oraz „read:org\". Dla pełnej funkcjonalności (np. workflow) — także „workflow\"."
        ),
        transport="http",
        url="https://api.githubcopilot.com/mcp/",
        headers_required=[("Authorization", "Bearer {TOKEN}")],
        env_required=[("TOKEN", "Token GitHub (ghp_... albo github_pat_...)")],
        install_hint=(
            "Wygeneruj token z gotowymi scope: "
            "https://github.com/settings/tokens/new?scopes=repo,read:org&description=Claude+Code+MCP "
            "(otwórz link, kliknij „Generate token\" na dole, skopiuj token i wklej powyżej)."
        ),
        homepage="https://github.com/github/github-mcp-server",
    ),
    McpTemplate(
        id="postgres",
        default_name="postgres",
        title="🐘 PostgreSQL",
        description=(
            "Agent wykonuje zapytania SQL w Twojej bazie danych. Idealny do pytań po polsku "
            "typu \"ile mamy klientów z Niemiec\". Wymaga connection string."
        ),
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres", "{CONNECTION_STRING}"],
        args_required=[
            (
                "CONNECTION_STRING",
                "Connection string PostgreSQL "
                "(np. postgresql://user:pass@host:5432/dbname)",
            )
        ],
        install_hint="Wymaga Node.js. Domyślnie tylko-do-odczytu — bezpieczny dla bazy produkcyjnej.",
        homepage="https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
    ),
    McpTemplate(
        id="brave-search",
        default_name="brave-search",
        title="🔎 Brave Search (web)",
        description=(
            "Wyszukiwanie w internecie z poziomu agenta. Agent może sprawdzać aktualne "
            "informacje, ceny, dokumentację itd. Wymaga klucza API Brave (darmowy do 2000 zapytań/mies.)."
        ),
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env_required=[("BRAVE_API_KEY", "Klucz API Brave Search")],
        install_hint="Klucz wygeneruj na https://api.search.brave.com/ (plan Free).",
        homepage="https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search",
    ),
    McpTemplate(
        id="slack",
        default_name="slack",
        title="💬 Slack",
        description=(
            "Agent czyta i wysyła wiadomości na Slacku. Wymaga utworzenia aplikacji Slack "
            "i tokenów: bota oraz zespołu. Działa w wybranych kanałach."
        ),
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env_required=[
            ("SLACK_BOT_TOKEN", "Slack Bot Token (xoxb-...)"),
            ("SLACK_TEAM_ID", "Slack Team/Workspace ID"),
        ],
        env_optional=[
            ("SLACK_CHANNEL_IDS", "Lista ID kanałów (po przecinku) — opcjonalne"),
        ],
        install_hint="Aplikację Slack utwórz na https://api.slack.com/apps (uprawnienia OAuth potrzebne dla bota).",
        homepage="https://github.com/modelcontextprotocol/servers/tree/main/src/slack",
    ),
    McpTemplate(
        id="notion",
        default_name="notion",
        title="📝 Notion (oficjalny)",
        description=(
            "Agent czyta Twoje strony Notion, tworzy nowe, dopisuje notatki. "
            "Oficjalny serwer Notion — autoryzacja przez OAuth (kliknięcie w przeglądarce)."
        ),
        transport="http",
        url="https://mcp.notion.com/mcp",
        install_hint=(
            "Po dodaniu uruchom Claude Code w katalogu agenta — pojawi się prośba "
            "o autoryzację Notion w przeglądarce."
        ),
        homepage="https://developers.notion.com/docs/mcp",
    ),
    McpTemplate(
        id="sentry",
        default_name="sentry",
        title="🛡️ Sentry (błędy aplikacji)",
        description=(
            "Agent czyta błędy i alerty z Sentry. Idealny do diagnostyki — \"co się wywaliło "
            "ostatnio w produkcji?\". Oficjalny serwer Sentry — autoryzacja OAuth."
        ),
        transport="http",
        url="https://mcp.sentry.dev/mcp",
        install_hint=(
            "Po dodaniu autoryzuj się w przeglądarce. Wymaga konta Sentry."
        ),
        homepage="https://docs.sentry.io/product/sentry-mcp/",
    ),
    McpTemplate(
        id="n8n",
        default_name="n8n",
        title="🤖 n8n (Twój własny serwer)",
        description=(
            "Łączy agenta z Twoją instancją n8n — dowolną, własną. Agent uruchamia "
            "Twoje workflow, sprawdza ich status. Każdy użytkownik podaje URL swojego "
            "serwera n8n MCP — działa z dowolną instalacją (chmura, self-hosted, lokalna)."
        ),
        transport="http",
        url="{N8N_MCP_URL}",
        args_required=[
            (
                "N8N_MCP_URL",
                "Pełny URL Twojego MCP w n8n "
                "(np. https://n8n.twojadomena.pl/mcp/abc123)",
            ),
        ],
        env_optional=[
            (
                "BEARER_TOKEN",
                "Bearer token (jeśli Twój workflow MCP wymaga autoryzacji "
                "— pozostaw puste jeśli nie)",
            ),
        ],
        headers_required=[
            ("Authorization", "Bearer {BEARER_TOKEN}"),
        ],
        install_hint=(
            "W n8n: Workflows → New → dodaj node „MCP Server Trigger\" → uruchom "
            "(Active) → skopiuj wygenerowany URL i wklej powyżej. Jeśli Twój endpoint "
            "używa SSE zamiast HTTP — użyj „Dodaj ręcznie\" z transportem SSE."
        ),
        homepage=(
            "https://docs.n8n.io/integrations/builtin/core-nodes/"
            "n8n-nodes-langchain.mcptrigger/"
        ),
    ),
    McpTemplate(
        id="imap",
        default_name="email-imap",
        title="📧 Email (IMAP — Gmail / dowolny dostawca)",
        description=(
            "Agent czyta Twoją skrzynkę e-mail przez protokół IMAP — działa z Gmailem, "
            "Outlookiem, własnym serwerem (np. mail.webwavecms.com). Idealne do "
            "podsumowań „co przyszło dzisiaj?\" albo wyszukiwania w archiwum."
        ),
        transport="stdio",
        command="npx",
        args=["-y", "@takashiishida/imap-mcp-server"],
        env_required=[
            ("IMAP_HOST", "Serwer IMAP (np. imap.gmail.com, mail.webwavecms.com)"),
            ("IMAP_PORT", "Port IMAP (zazwyczaj 993)"),
            ("IMAP_USER", "Adres email (login)"),
            ("IMAP_PASSWORD", "Hasło lub hasło aplikacji (Gmail wymaga App Password)"),
        ],
        install_hint=(
            "Dla Gmaila: włącz 2FA i utwórz „Hasło aplikacji\" "
            "(https://myaccount.google.com/apppasswords) — zwykłego hasła Google użyć NIE MOŻNA. "
            "Wymaga Node.js (npx)."
        ),
        homepage="https://www.npmjs.com/package/@takashiishida/imap-mcp-server",
    ),
    McpTemplate(
        id="gitlab",
        default_name="gitlab",
        title="🦊 GitLab",
        description=(
            "Agent czyta projekty, issues i merge requesty w GitLab. Wspiera GitLab.com "
            "oraz instancje self-hosted (np. firmowy GitLab). Wymaga Personal Access Token."
        ),
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-gitlab"],
        env_required=[
            ("GITLAB_PERSONAL_ACCESS_TOKEN", "GitLab PAT (glpat-...)"),
        ],
        env_optional=[
            (
                "GITLAB_API_URL",
                "URL API GitLab (domyślnie https://gitlab.com/api/v4 — "
                "zmień jeśli używasz self-hosted)",
            ),
        ],
        install_hint=(
            "Token wygeneruj w GitLab → User Settings → Access Tokens → "
            "scope: api (read+write) lub read_api (tylko-do-odczytu). "
            "Dla self-hosted — ustaw GITLAB_API_URL na adres swojej instancji."
        ),
        homepage="https://github.com/modelcontextprotocol/servers/tree/main/src/gitlab",
    ),
]


def get_template(template_id: str) -> Optional[McpTemplate]:
    for tpl in MCP_TEMPLATES:
        if tpl.id == template_id:
            return tpl
    return None
