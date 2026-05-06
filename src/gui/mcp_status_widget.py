"""
Claude Voice Assistant - Agent Status Widget (w pasku statusu)

Pokazuje 4 liczniki dla aktywnego agenta:
  🔌 N  — aktywne (connected) serwery MCP
  🧩 N  — skille aktywne dla agenta (globalne minus deny-list agenta)
  📁 N  — pliki pamięci agenta z konfiguracji (memory_files)
  🤖 X  — etykieta wybranego modelu Claude Code

Plus jeden 🔄 odświeżający wszystkie 4 liczniki.

Cache MCP: 30 sekund per working_dir (klikanie po zakładkach jest natychmiastowe).
Refresh MCP w tle (threading.Thread + pyqtSignal — nie blokuje UI).
Skille i pliki czytane synchronicznie (operacja jest tania — list dirów / lookup w configu).
"""
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QToolButton,
)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.mcp_manager import (
    McpManager, McpServer, McpError,
    STATUS_CONNECTED, STATUS_NEEDS_AUTH, STATUS_FAILED, STATUS_UNKNOWN,
)
from core.agent_mcp_settings import AgentMcpSettings
from core.skills_manager import SkillsManager, Skill
from core.agent_skills_settings import AgentSkillsSettings
from config import CLAUDE_MODELS_SHORT, CLAUDE_MODELS, DEFAULT_AGENT_MODEL


CACHE_TTL_SECONDS = 30

# Wspólny styl klikalnych "kafelków" w pasku statusu.
_TILE_STYLE = """
    QPushButton, QToolButton {
        background: transparent;
        color: #ffffff;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
    }
    QPushButton:hover, QToolButton:hover {
        background-color: #4a1a3a;
        border-color: #6a2a5a;
    }
    QPushButton:disabled, QToolButton:disabled {
        color: #888888;
    }
"""


class McpStatusWidget(QWidget):
    """Widget statusu agenta w QStatusBar (4 liczniki + refresh).

    Sygnały:
      - request_open_manager(working_dir) — kliknięcie 🔌 (Menedżer MCP)
      - request_open_skills() — kliknięcie 🧩 (Menedżer Skills)
      - request_edit_agent(agent_id) — kliknięcie 📁 lub 🤖 (Edycja agenta)
      - mcp_changed() — gdy stan MCP się zmienił (po toggle all w innym miejscu)
    """

    request_open_manager = pyqtSignal(object)        # Optional[Path]
    request_open_skills = pyqtSignal()
    request_edit_agent = pyqtSignal(str)             # agent_id
    mcp_changed = pyqtSignal()

    # Wewnętrzny sygnał — z wątku roboczego do GUI (lista MCP)
    _mcp_loaded = pyqtSignal(object)  # list[McpServer] albo None gdy błąd

    def __init__(self, parent=None):
        super().__init__(parent)
        self._working_dir: Optional[Path] = None
        self._agent_name: Optional[str] = None
        self._agent_id: Optional[str] = None
        self._memory_files: List[str] = []
        self._model_key: str = DEFAULT_AGENT_MODEL
        # Cache MCP: {working_dir_str: (timestamp, [McpServer, ...])}
        self._cache: Dict[str, Tuple[float, List[McpServer]]] = {}
        self._loading: bool = False
        self._setup_ui()
        self._mcp_loaded.connect(self._on_mcp_loaded)
        self._render_idle()

    # ---------- Public API ----------

    def set_agent(
        self,
        working_dir: Optional[Path],
        agent_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        memory_files: Optional[List[str]] = None,
        model_key: Optional[str] = None,
    ):
        """Ustaw kontekst agenta (zmiana zakładki).

        Aktualizuje wszystkie 4 liczniki. MCP korzysta z cache (30s);
        skille/pliki/model są tanie więc liczone synchronicznie.
        """
        self._working_dir = Path(working_dir) if working_dir else None
        self._agent_name = agent_name
        self._agent_id = agent_id
        self._memory_files = list(memory_files or [])
        self._model_key = model_key or DEFAULT_AGENT_MODEL

        # Statyczne liczniki — od razu
        self._render_skills()
        self._render_files()
        self._render_model()

        # MCP — z cache lub w tle
        if self._working_dir is None:
            self._render_idle_mcp()
            return

        cached = self._read_cache(self._working_dir)
        if cached is not None:
            self._render_mcp(cached)
            return

        self._render_loading_mcp()
        self._refresh_mcp_async()

    def force_refresh(self):
        """Pełne odświeżenie wszystkich liczników (ignoruje cache MCP)."""
        # Skills/files/model — od razu (mogły się zmienić w dialogach)
        self._render_skills()
        self._render_files()
        self._render_model()

        if self._working_dir is None:
            self._render_idle_mcp()
            return
        # Inwaliduj cache i pobierz świeży stan MCP
        self._cache.pop(str(self._working_dir), None)
        self._render_loading_mcp()
        self._refresh_mcp_async()

    # ---------- UI ----------

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # 🔌 MCP
        self.mcp_btn = QPushButton()
        self.mcp_btn.setFlat(True)
        self.mcp_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.mcp_btn.setStyleSheet(_TILE_STYLE)
        self.mcp_btn.clicked.connect(self._on_mcp_click)
        layout.addWidget(self.mcp_btn)

        # 🧩 Skille
        self.skills_btn = QPushButton()
        self.skills_btn.setFlat(True)
        self.skills_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.skills_btn.setStyleSheet(_TILE_STYLE)
        self.skills_btn.clicked.connect(self._on_skills_click)
        layout.addWidget(self.skills_btn)

        # 📁 Pliki pamięci agenta
        self.files_btn = QPushButton()
        self.files_btn.setFlat(True)
        self.files_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.files_btn.setStyleSheet(_TILE_STYLE)
        self.files_btn.clicked.connect(self._on_edit_agent_click)
        layout.addWidget(self.files_btn)

        # 🤖 Model
        self.model_btn = QPushButton()
        self.model_btn.setFlat(True)
        self.model_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.model_btn.setStyleSheet(_TILE_STYLE)
        self.model_btn.clicked.connect(self._on_edit_agent_click)
        layout.addWidget(self.model_btn)

        # Σ Globalny licznik tokenów (suma ze wszystkich zakładek). Biały,
        # nieklikalny — czysta informacja. Aktualizowany przez set_total_tokens()
        # wywoływane z MainWindow.
        self.total_tokens_label = QLabel("Σ 0")
        self.total_tokens_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 11px;
                padding: 2px 6px;
                font-weight: 500;
            }
        """)
        self.total_tokens_label.setToolTip(
            "Łączne (przybliżone) tokeny ze wszystkich zakładek od startu aplikacji.\n"
            "Wzór: liczba znaków ÷ 3,5.\n"
            "Reset przy: restarcie aplikacji.\n"
            "(Indywidualny licznik agenta — po prawej, z kolorem zależnym od % okna kontekstu.)"
        )
        layout.addWidget(self.total_tokens_label)

        # 🔄 Refresh wszystkich liczników — ikona SVG (biała strzałka anticlockwise).
        self.refresh_btn = QToolButton()
        refresh_icon_path = Path(__file__).parent / "refresh.svg"
        if refresh_icon_path.exists():
            self.refresh_btn.setIcon(QIcon(str(refresh_icon_path)))
            self.refresh_btn.setIconSize(QSize(16, 16))
        else:
            # Fallback gdyby brakowało pliku
            self.refresh_btn.setText("⟳")
        self.refresh_btn.setToolTip(
            "Odśwież status agenta (MCP, skille, pliki, model).\n"
            "Klika się gdy zmieniłeś coś w menedżerach lub edycji agenta."
        )
        self.refresh_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.refresh_btn.setStyleSheet(_TILE_STYLE)
        self.refresh_btn.clicked.connect(self.force_refresh)
        layout.addWidget(self.refresh_btn)

    # ---------- Public API: globalny licznik ----------

    def set_total_tokens(self, value: int):
        """Ustaw globalną sumę tokenów (suma ze wszystkich zakładek)."""
        self.total_tokens_label.setText(f"Σ {value:,}")

    # ---------- Renderowanie: stany puste ----------

    def _render_idle(self):
        """Brak aktywnej zakładki agenta."""
        self._render_idle_mcp()
        self.skills_btn.setText("🧩 —")
        self.skills_btn.setToolTip("Wybierz zakładkę agenta, aby zobaczyć liczbę aktywnych skilli.")
        self.skills_btn.setEnabled(False)
        self.files_btn.setText("📁 —")
        self.files_btn.setToolTip("Wybierz zakładkę agenta, aby zobaczyć pliki pamięci.")
        self.files_btn.setEnabled(False)
        self.model_btn.setText("🤖 —")
        self.model_btn.setToolTip("Wybierz zakładkę agenta, aby zobaczyć model AI.")
        self.model_btn.setEnabled(False)

    def _render_idle_mcp(self):
        self.mcp_btn.setText("🔌 —")
        self.mcp_btn.setToolTip("Wybierz zakładkę agenta, aby zobaczyć aktywne serwery MCP.")
        self.mcp_btn.setEnabled(False)

    def _render_loading_mcp(self):
        self.mcp_btn.setText("🔌 …")
        self.mcp_btn.setToolTip("Sprawdzam status MCP...")
        self.mcp_btn.setEnabled(True)

    def _render_invalid_mcp(self, msg: str):
        self.mcp_btn.setText("🔌 ?")
        self.mcp_btn.setToolTip(msg)
        self.mcp_btn.setEnabled(False)

    # ---------- Renderowanie: MCP ----------

    def _render_mcp(self, servers: List[McpServer]):
        """Pokazuje liczbę AKTYWNYCH (connected) MCP + tooltip z pełną listą."""
        self.mcp_btn.setEnabled(True)

        disabled_set = self._get_disabled_mcp_set()
        active = [s for s in servers if s.sanitized_name not in disabled_set]
        disabled = [s for s in servers if s.sanitized_name in disabled_set]

        counts = {STATUS_CONNECTED: 0, STATUS_NEEDS_AUTH: 0, STATUS_FAILED: 0, STATUS_UNKNOWN: 0}
        for s in active:
            counts[s.status] = counts.get(s.status, 0) + 1

        # Główny licznik = "aktywne" = connected. Pozostałe statusy są w tooltipie.
        self.mcp_btn.setText(f"🔌 {counts[STATUS_CONNECTED]}")
        self.mcp_btn.setToolTip(self._build_mcp_tooltip(active, disabled, counts))

    def _build_mcp_tooltip(
        self, active: List[McpServer], disabled: List[McpServer], counts: dict
    ) -> str:
        agent_label = self._agent_name or "—"
        lines = [
            f"<b>Serwery MCP — agent „{agent_label}\":</b>",
            f"  ✅ Połączone: {counts.get(STATUS_CONNECTED, 0)}",
        ]
        if counts.get(STATUS_NEEDS_AUTH, 0):
            lines.append(f"  🔐 Wymagają autoryzacji: {counts[STATUS_NEEDS_AUTH]}")
        if counts.get(STATUS_FAILED, 0):
            lines.append(f"  ❌ Błąd: {counts[STATUS_FAILED]}")
        if counts.get(STATUS_UNKNOWN, 0):
            lines.append(f"  ❓ Nieznany: {counts[STATUS_UNKNOWN]}")

        if active:
            lines.append("")
            lines.append("<b>Aktywne:</b>")
            for s in active:
                icon = self._status_icon(s.status)
                scope_label = self._scope_label(s.scope)
                lines.append(f"  {icon} {s.name} <span style='color:#888'>({scope_label})</span>")

        if disabled:
            lines.append("")
            lines.append("<b>Wyłączone dla tego agenta:</b>")
            for s in disabled:
                lines.append(f"  🚫 {s.name}")

        lines.append("")
        lines.append("<i>Kliknij aby otworzyć menedżer MCP.</i>")
        return "<br>".join(lines)

    @staticmethod
    def _status_icon(status: str) -> str:
        return {
            STATUS_CONNECTED: "✅",
            STATUS_NEEDS_AUTH: "🔐",
            STATUS_FAILED: "❌",
        }.get(status, "❓")

    @staticmethod
    def _scope_label(scope: str) -> str:
        return {"user": "globalny", "local": "lokalny", "managed": "zarządzany"}.get(scope, scope)

    # ---------- Renderowanie: Skille ----------

    def _render_skills(self):
        """Liczy globalne skille zainstalowane w ~/.claude/skills/, odejmuje
        deny-list bieżącego agenta. Wynik = aktywne dla agenta."""
        self.skills_btn.setEnabled(True)
        try:
            all_skills = SkillsManager().list_skills()
        except Exception:
            self.skills_btn.setText("🧩 ?")
            self.skills_btn.setToolTip("Nie udało się odczytać katalogu ~/.claude/skills/")
            return

        disabled_names = self._get_disabled_skills_set()
        active = [s for s in all_skills if s.name not in disabled_names and s.folder_name not in disabled_names]
        disabled = [s for s in all_skills if s.name in disabled_names or s.folder_name in disabled_names]

        self.skills_btn.setText(f"🧩 {len(active)}")
        self.skills_btn.setToolTip(self._build_skills_tooltip(active, disabled))

    def _build_skills_tooltip(self, active: List[Skill], disabled: List[Skill]) -> str:
        agent_label = self._agent_name or "—"
        lines = [f"<b>Skille — agent „{agent_label}\":</b>"]
        if active:
            lines.append("")
            lines.append(f"<b>Aktywne ({len(active)}):</b>")
            for s in active[:30]:
                lines.append(f"  🧩 {s.name}")
            if len(active) > 30:
                lines.append(f"  <i>… i {len(active) - 30} więcej</i>")
        else:
            lines.append("")
            lines.append("<i>(brak aktywnych skilli)</i>")

        if disabled:
            lines.append("")
            lines.append(f"<b>Wyłączone dla tego agenta ({len(disabled)}):</b>")
            for s in disabled[:10]:
                lines.append(f"  🚫 {s.name}")
            if len(disabled) > 10:
                lines.append(f"  <i>… i {len(disabled) - 10} więcej</i>")

        lines.append("")
        lines.append("<i>Kliknij aby otworzyć menedżer skilli.</i>")
        return "<br>".join(lines)

    # ---------- Renderowanie: Pliki ----------

    def _render_files(self):
        """Pokazuje liczbę memory_files agenta (z konfiguracji w 'Zarządzaj agentami')."""
        self.files_btn.setEnabled(self._agent_id is not None)
        count = len(self._memory_files)
        self.files_btn.setText(f"📁 {count}")
        self.files_btn.setToolTip(self._build_files_tooltip())

    def _build_files_tooltip(self) -> str:
        agent_label = self._agent_name or "—"
        lines = [f"<b>Pliki pamięci — agent „{agent_label}\":</b>"]
        if self._memory_files:
            lines.append("")
            for path_str in self._memory_files[:30]:
                p = Path(path_str)
                # Wyróżnij brak pliku (czerwono)
                if p.exists():
                    lines.append(f"  📄 {p.name} <span style='color:#888'>({p.parent})</span>")
                else:
                    lines.append(f"  ⚠️ {p.name} <span style='color:#cc4444'>(brak pliku)</span>")
            if len(self._memory_files) > 30:
                lines.append(f"  <i>… i {len(self._memory_files) - 30} więcej</i>")
        else:
            lines.append("")
            lines.append("<i>(brak plików pamięci)</i>")

        lines.append("")
        if self._agent_id:
            lines.append("<i>Kliknij aby edytować agenta (zakładka „Pliki\").</i>")
        else:
            lines.append("<i>Wybierz zakładkę agenta.</i>")
        return "<br>".join(lines)

    # ---------- Renderowanie: Model ----------

    def _render_model(self):
        """Pokazuje wybrany model Claude Code dla agenta."""
        self.model_btn.setEnabled(self._agent_id is not None)
        short = CLAUDE_MODELS_SHORT.get(self._model_key, self._model_key)
        full = CLAUDE_MODELS.get(self._model_key, self._model_key)
        # Na pasku jest mało miejsca — pomijamy prefiks "Domyślny — ".
        # W tooltipie pokazujemy pełną etykietę z "Domyślny" zachowaną.
        if short.startswith("Domyślny — "):
            short = short[len("Domyślny — "):]
        self.model_btn.setText(f"🤖 {short}")
        agent_label = self._agent_name or "—"
        tooltip_lines = [
            f"<b>Model AI — agent „{agent_label}\":</b>",
            "",
            f"  🤖 {full}",
            "",
        ]
        if self._agent_id:
            tooltip_lines.append("<i>Kliknij aby zmienić model w edycji agenta.</i>")
        else:
            tooltip_lines.append("<i>Wybierz zakładkę agenta.</i>")
        self.model_btn.setToolTip("<br>".join(tooltip_lines))

    # ---------- Cache MCP ----------

    def _read_cache(self, working_dir: Path) -> Optional[List[McpServer]]:
        key = str(working_dir)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, servers = entry
        if (time.monotonic() - ts) > CACHE_TTL_SECONDS:
            return None
        return servers

    def _write_cache(self, working_dir: Path, servers: List[McpServer]):
        self._cache[str(working_dir)] = (time.monotonic(), servers)

    # ---------- Background refresh MCP ----------

    def _refresh_mcp_async(self):
        if self._loading:
            return
        if self._working_dir is None:
            return
        if not self._working_dir.is_dir():
            self._render_invalid_mcp(f"Katalog roboczy nie istnieje: {self._working_dir}")
            return

        self._loading = True
        wd = self._working_dir

        def worker():
            servers: Optional[List[McpServer]]
            try:
                manager = McpManager(working_dir=wd)
                servers = manager.list_servers()
            except McpError:
                servers = None
            except Exception:
                servers = None
            self._mcp_loaded.emit(servers)

        threading.Thread(target=worker, daemon=True).start()

    def _on_mcp_loaded(self, servers):
        self._loading = False
        if servers is None:
            self._render_invalid_mcp(
                "Nie udało się sprawdzić statusu MCP. "
                "Sprawdź czy Claude Code (komenda 'claude') jest zainstalowany."
            )
            return
        if self._working_dir is not None:
            self._write_cache(self._working_dir, servers)
        self._render_mcp(servers)

    # ---------- Helpers: deny-listy ----------

    def _get_disabled_mcp_set(self) -> set:
        if self._working_dir is None or not self._working_dir.is_dir():
            return set()
        try:
            return set(AgentMcpSettings(self._working_dir).get_disabled_mcp_sanitized())
        except Exception:
            return set()

    def _get_disabled_skills_set(self) -> set:
        if self._working_dir is None or not self._working_dir.is_dir():
            return set()
        try:
            return set(AgentSkillsSettings(self._working_dir).get_disabled_global_skills())
        except Exception:
            return set()

    # ---------- Akcje (kliknięcia) ----------

    def _on_mcp_click(self):
        if self._working_dir is None:
            return
        self.request_open_manager.emit(self._working_dir)

    def _on_skills_click(self):
        self.request_open_skills.emit()

    def _on_edit_agent_click(self):
        if self._agent_id:
            self.request_edit_agent.emit(self._agent_id)
