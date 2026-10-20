"""Polecenia „/" Claude Code — lista do przycisku „/" na dolnym pasku.

PO CO TO JEST
-------------
Użytkownik nietechniczny nie wie, co można wpisać po ukośniku. Przycisk „/"
rozwija listę poleceń z opisem po polsku; kliknięcie WPISUJE polecenie w pole
(nie wysyła — można dopisać argument i dopiero wtedy Enter).

SKĄD LISTA — ZMIERZONE, NIE ZGADNIĘTE (2026-10-20)
-------------------------------------------------
⛔ Claude Code NIE ma sposobu, żeby zapytać „podaj swoje polecenia". Są trzy źródła:

1. WBUDOWANE — spisane niżej RĘCZNIE. Każda nazwa sprawdzona w programie
   Claude Code 2.1.304 (obiekty `{type:"local"|"local-jsx"|"prompt",name:…}`
   oraz skille wbudowane z `menuDescription`). Z każdą wersją coś może dojść
   albo zniknąć — dlatego menu ma na dole „Pokaż pełną listę w Claude", które
   otwiera ORYGINALNĄ listę w terminalu (zawsze aktualna). Ta pozycja jest
   siatką bezpieczeństwa, nie ozdobą: nie usuwaj jej.
2. SKILLE i WŁASNE POLECENIA użytkownika — czytane z dysku przy KAŻDYM
   rozwinięciu menu (zawsze aktualne): `~/.claude/skills/*/SKILL.md`,
   `~/.claude/commands/**/*.md` oraz to samo w `.claude/` katalogu projektu
   agenta danej zakładki.
3. WTYCZKI — tu pominięte (u właściciela żadna nie jest włączona, więc nie ma
   na czym tego zmierzyć); widać je w „pełnej liście w Claude".

CZEGO CELOWO NIE MA NA LIŚCIE
-----------------------------
Polecenia, które w zakładce VCA PSUJĄ pracę albo nie mają sensu:
  exit/background/stop/teleport/session/remote-control/desktop — wyprowadzają
    sesję z zakładki (apka traci przypiętą sesję: flaga, 🔊, auto-czytanie),
  theme/tui/terminal-setup/scroll-speed — apka sama ustawia motyw `dark-ansi`
    (przełączanie jasny/ciemny w locie) i silnik terminala,
  voice — VCA ma własne dyktowanie,
  restart/install/heapdump — techniczne, nie dla użytkownika,
  ultraplan/ultrareview — płatne uruchomienia w chmurze,
  oraz polecenia instalacyjne/chmurowe/firmowe (setup-*, install-*-app,
  web-setup, remote-env, cloud-plugins, daemon, design-*, upgrade, stickers,
  radio, mobile, ide, import, team-onboarding, autofix-pr, …).
Wszystkie nadal działają wpisane ręcznie i są w „pełnej liście w Claude".
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

SOURCE_BUILTIN = "builtin"
SOURCE_USER = "user"
SOURCE_PROJECT = "project"

# Ile znaków opisu skilla pokazujemy w menu (pełny opis idzie do podpowiedzi).
MENU_DESC_MAX = 70


@dataclass(frozen=True)
class SlashCommand:
    name: str            # bez ukośnika, np. "compact"
    description: str     # w języku interfejsu (wbudowane) albo z pliku (skille)
    source: str          # SOURCE_BUILTIN / SOURCE_USER / SOURCE_PROJECT
    common: bool = False # „Najczęstsze" — na samej górze menu

    @property
    def text(self) -> str:
        """Co trafia do pola: ukośnik + nazwa + spacja (pod argument)."""
        return f"/{self.name} "


# (nazwa, opis PL, opis EN, najczęstsze?) — sprawdzone na Claude Code 2.1.304.
# Kolejność = kolejność w menu (najczęstsze w kolejności ważności).
_BUILTIN = [
    ("compact", "Streść rozmowę, żeby zwolnić miejsce (pamięć agenta)",
     "Summarize the conversation to free up context", True),
    ("clear", "Zacznij nową, pustą rozmowę (stara zostaje do wznowienia)",
     "Start a new empty conversation (old one can be resumed)", True),
    ("resume", "Wróć do jednej z wcześniejszych rozmów",
     "Resume an earlier conversation", True),
    ("model", "Zmień model AI (np. Opus, Sonnet)",
     "Change the AI model", True),
    ("effort", "Ustaw, jak mocno model ma się wysilać",
     "Set the model's effort level", True),
    ("context", "Pokaż, ile pamięci rozmowy jest już zajęte",
     "Show current context usage", True),
    ("usage", "Pokaż zużycie i limity planu",
     "Show cost, plan usage and limits", True),
    ("btw", "Zadaj szybkie pytanie poboczne, bez przerywania pracy",
     "Ask a quick side question without interrupting", True),
    ("plan", "Włącz tryb planowania (najpierw plan, potem praca)",
     "Enable plan mode or view the current plan", True),
    ("memory", "Edytuj pliki pamięci CLAUDE.md",
     "Edit CLAUDE.md memory files", True),
    ("init", "Utwórz plik CLAUDE.md z opisem projektu",
     "Create a CLAUDE.md file describing the project", True),
    ("help", "Pomoc i lista poleceń Claude Code",
     "Help and available commands", True),

    ("add-dir", "Dodaj kolejny katalog roboczy", "Add a working directory", False),
    ("advisor", "Pozwól Claude radzić się mocniejszego modelu",
     "Let Claude consult a stronger model", False),
    ("artifacts", "Przeglądaj opublikowane strony (artefakty)",
     "Browse published artifacts", False),
    ("autocompact", "Ustaw, kiedy rozmowa ma się sama streszczać",
     "Set when auto-summarizing kicks in", False),
    ("branch", "Utwórz odgałęzienie rozmowy w tym miejscu",
     "Branch the conversation at this point", False),
    ("brief", "Włącz/wyłącz tryb krótkich odpowiedzi", "Toggle brief-only mode", False),
    ("cd", "Przenieś sesję do innego katalogu", "Move the session to another directory", False),
    ("code-review", "Przejrzyj zmiany w kodzie pod kątem błędów",
     "Review code changes for bugs", False),
    ("config", "Otwórz ustawienia Claude Code", "Open Claude Code settings", False),
    ("copy", "Skopiuj ostatnią odpowiedź Claude do schowka",
     "Copy Claude's last response to clipboard", False),
    ("diff", "Pokaż niezapisane zmiany w plikach", "View uncommitted changes", False),
    ("export", "Zapisz rozmowę do pliku lub schowka",
     "Export the conversation to a file or clipboard", False),
    ("fast", "Włącz/wyłącz tryb szybki", "Toggle fast mode", False),
    ("feedback", "Wyślij opinię do Anthropic albo zgłoś błąd",
     "Send feedback or report a bug", False),
    ("fewer-permission-prompts", "Mniej pytań o zgodę (bezpieczne polecenia)",
     "Pre-approve safe read-only commands", False),
    ("focus", "Widok skupienia: tylko pytanie, streszczenie i odpowiedź",
     "Toggle focus view", False),
    ("fork", "Uruchom agenta w tle z całą tą rozmową",
     "Spawn a background agent with this conversation", False),
    ("goal", "Ustaw cel, który Claude sprawdzi przed zakończeniem",
     "Set a goal Claude checks before stopping", False),
    ("hooks", "Pokaż automatyczne reakcje (hooki)", "View hook configuration", False),
    ("insights", "Raport z analizą Twoich sesji", "Report analyzing your sessions", False),
    ("list-agents", "Lista agentów i sesji, do których można pisać",
     "List agents and sessions you can message", False),
    ("login", "Zaloguj się do konta Anthropic", "Sign in to your Anthropic account", False),
    ("logout", "Wyloguj się z konta Anthropic", "Sign out of your Anthropic account", False),
    ("loop", "Powtarzaj polecenie co jakiś czas", "Run a prompt on a recurring interval", False),
    ("loops", "Lista zaplanowanych powtórzeń", "List, create and delete loops", False),
    ("mcp", "Zarządzaj serwerami MCP", "Manage MCP servers", False),
    ("output-style", "Zmień styl odpowiedzi", "List or switch output styles", False),
    ("permissions", "Zarządzaj zgodami na narzędzia", "Manage tool permission rules", False),
    ("plugin", "Zarządzaj wtyczkami Claude Code", "Manage Claude Code plugins", False),
    ("powerup", "Krótkie interaktywne lekcje funkcji Claude Code",
     "Quick interactive feature lessons", False),
    ("privacy-settings", "Ustawienia prywatności", "Privacy settings", False),
    ("recap", "Streszczenie sesji w jednym zdaniu", "One-line session recap", False),
    ("reload-plugins", "Wczytaj zmienione wtyczki", "Activate pending plugin changes", False),
    ("reload-skills", "Wczytaj skille dodane w trakcie sesji",
     "Pick up skills added during this session", False),
    ("rename", "Zmień nazwę rozmowy", "Rename the conversation", False),
    ("schedule", "Zaplanuj agentów działających w chmurze",
     "Schedule remote Claude Code agents", False),
    ("security-review", "Przegląd bezpieczeństwa zmian w kodzie",
     "Security review of pending changes", False),
    ("simplify", "Uprość i uporządkuj zmieniony kod",
     "Simplify and clean up changed code", False),
    ("skill-doctor", "Które skille są nieużywane i zajmują pamięć",
     "Which skills are unused and costing context", False),
    ("skills", "Lista dostępnych skilli", "List available skills", False),
    ("status", "Stan: wersja, model, konto, połączenie",
     "Status: version, model, account, connectivity", False),
    ("subtask", "Wyślij podagenta z pełnym kontekstem",
     "Send a subagent off with your full context", False),
    ("tasks", "Co działa w tle", "View background tasks", False),
    ("update-config", "Zmień ustawienia: hooki, zgody, zmienne",
     "Change settings: hooks, permissions, env vars", False),
    ("usage-credits", "Ustaw dodatkowe kredyty po przekroczeniu limitu",
     "Configure usage credits", False),
    ("version", "Pokaż wersję Claude Code", "Show the Claude Code version", False),
    ("workflows", "Przeglądaj przepływy pracy (workflows)",
     "Browse workflows", False),
]


def builtin_commands(lang: str = "pl-PL") -> list[SlashCommand]:
    """Wbudowane polecenia z opisem w języku interfejsu (polski albo angielski)."""
    pl = str(lang or "").lower().startswith("pl")
    return [SlashCommand(n, d_pl if pl else d_en, SOURCE_BUILTIN, common)
            for n, d_pl, d_en, common in _BUILTIN]


def _frontmatter(text: str) -> dict:
    """Pola `klucz: wartość` z nagłówka `---`.

    ⚠️ Obsługuje też wartość WIELOLINIJKOWĄ (`description: >-` + wcięte linie).
    Zmierzone u właściciela: 7 z 23 skilli ma tak zapisany opis — prosty parser
    (jak w skills_manager) oddawał im opis „>-".
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out, key = {}, None
    for raw in text[3:end].splitlines():
        if key and raw[:1] in (" ", "\t") and raw.strip():
            out[key] = (out[key] + " " + raw.strip()).strip()
            continue
        line = raw.strip()
        key = None
        if ":" in line and not line.startswith("#"):
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if v in (">", ">-", ">+", "|", "|-", "|+"):
                out[k], key = "", k          # treść w kolejnych wciętych liniach
            else:
                out[k] = v.strip('"').strip("'")
    return out


def _first_line(text: str) -> str:
    """Pierwsza linia treści po nagłówku — opis polecenia bez pola `description`."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        text = text[end + 4:] if end >= 0 else ""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return ""


def _read(path: Path) -> str:
    try:
        # Skille potrafią mieć długie instrukcje — nagłówek siedzi na początku.
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(16384)
    except OSError:
        return ""


def _is_off(value: str) -> bool:
    return str(value).strip().lower() in ("false", "no", "0")


def _scan_skills(base: Path, source: str, overrides: dict) -> list[SlashCommand]:
    out = []
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return out
    for entry in entries:
        skill_md = entry / "SKILL.md"
        if not entry.is_dir() or not skill_md.is_file():
            continue          # np. katalog „synced" bez SKILL.md — to nie skill
        text = _read(skill_md)
        meta = _frontmatter(text)
        # Wywołuje się NAZWĄ KATALOGU, nie polem `name` (zmierzone: skill z
        # `name: Creating Atomic PRs` Claude Code podaje jako /creating-atomic-prs).
        name = entry.name
        # Ukryty z menu „/": sam autor skilla (user-invocable: false) albo
        # użytkownik (skillOverrides = "off" — patrz core/skill_doctor).
        if (_is_off(meta.get("user-invocable", ""))
                or "off" in (overrides.get(name), overrides.get(meta.get("name")))):
            continue
        out.append(SlashCommand(name, meta.get("description") or _first_line(text), source))
    return out


def _scan_commands(base: Path, source: str) -> list[SlashCommand]:
    """Własne polecenia: `commands/x.md` → /x, `commands/dir/x.md` → /dir:x."""
    out = []
    if not base.is_dir():
        return out
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            path = Path(root) / f
            rel = path.relative_to(base).with_suffix("")
            name = ":".join(rel.parts)
            text = _read(path)
            meta = _frontmatter(text)
            out.append(SlashCommand(name, meta.get("description") or _first_line(text), source))
    return out


def custom_commands(cwd: str | None = None, home: Path | None = None,
                    overrides: dict | None = None) -> list[SlashCommand]:
    """Skille i własne polecenia: z katalogu domowego oraz z projektu agenta.

    Czytane z dysku przy każdym wywołaniu (tanie: kilkadziesiąt małych plików).
    Ta sama nazwa w projekcie i w domu = jedna pozycja (projekt wygrywa, jak
    w Claude Code). Wynik posortowany alfabetycznie.
    """
    home = Path(home) if home else Path.home()
    if overrides is None:
        try:
            from core.claude_settings import get_skill_overrides
            overrides = get_skill_overrides(home / ".claude" / "settings.json")
        except Exception:
            overrides = {}

    found: dict[str, SlashCommand] = {}
    sources = [(home / ".claude", SOURCE_USER)]
    if cwd:
        proj = Path(cwd) / ".claude"
        try:
            if proj.resolve() != (home / ".claude").resolve():
                sources.append((proj, SOURCE_PROJECT))
        except OSError:
            pass
    for base, source in sources:      # projekt na końcu = nadpisuje dom
        for cmd in (_scan_skills(base / "skills", source, overrides)
                    + _scan_commands(base / "commands", source)):
            found[cmd.name] = cmd
    builtin = {n for n, *_ in _BUILTIN}
    return sorted((c for c in found.values() if c.name not in builtin),
                  key=lambda c: c.name.lower())


def short(text: str, limit: int = MENU_DESC_MAX) -> str:
    """Opis przycięty do menu (jedna linia, wielokropek)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"
