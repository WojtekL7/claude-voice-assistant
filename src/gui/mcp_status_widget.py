"""
Vibe Coding Assistant - Agent Status Widget (w pasku statusu)

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
from PyQt5.QtGui import QCursor, QIcon, QFont
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
from gui import theme
from core.skills_manager import SkillsManager, Skill
from core.agent_skills_settings import AgentSkillsSettings
from config import (
    CLAUDE_MODELS_SHORT, CLAUDE_MODELS, DEFAULT_AGENT_MODEL,
    t as tr, model_label, model_label_short, model_default_prefix,
    model_name_for_api_id,
)


CACHE_TTL_SECONDS = 30

# Wspólny styl klikalnych "kafelków" w pasku statusu (kolory z palety — gui/theme.py).
_TILE_STYLE = f"""
    QPushButton, QToolButton {{
        background: transparent;
        color: {theme.TEXT};
        border: 1px solid transparent;
        border-radius: {theme.RADIUS_SM}px;
        padding: 2px 6px;
        font-size: 11px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background-color: {theme.SURFACE_HOVER};
        border-color: {theme.ACCENT};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        color: {theme.TEXT_FAINT};
    }}
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
        # Model WYKRYTY z dziennika sesji (identyfikator API, np.
        # "claude-opus-5"). Ma znaczenie tylko przy ustawieniu „Domyślny" —
        # wtedy apka nie narzuca modelu i inaczej nie ma skąd znać nazwy.
        self._detected_model: Optional[str] = None
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
        detected_model: Optional[str] = None,
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
        self._detected_model = detected_model

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
        self.total_tokens_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT};
                font-size: 11px;
                padding: 2px 6px;
                font-weight: 500;
            }}
        """)
        self.total_tokens_label.setToolTip(tr('total_tokens_tooltip'))
        # Stała zarezerwowana szerokość pod największą realną sumę — bez tego
        # rosnąca liczba cyfr przesuwałaby sąsiednie kafelki i przycisk 🔄 przy
        # każdej aktualizacji licznika („skakanie" paska statusu). Σ zostaje
        # wyrównane do lewej (symbol Σ w miejscu, cyfry rosną w prawo w obrębie
        # zarezerwowanego pola).
        _tot_font = QFont(self.total_tokens_label.font())
        _tot_font.setPixelSize(11)
        self.total_tokens_label.setFont(_tot_font)
        self.total_tokens_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.total_tokens_label.setMinimumWidth(
            self.total_tokens_label.fontMetrics().horizontalAdvance("Σ  999,999,999") + 16)
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
        self.refresh_btn.setToolTip(tr('refresh_status_tooltip'))
        self.refresh_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.refresh_btn.setStyleSheet(_TILE_STYLE)
        self.refresh_btn.clicked.connect(self.force_refresh)
        layout.addWidget(self.refresh_btn)

    # ---------- Public API: globalny licznik ----------

    def set_total_tokens(self, value: int):
        """Ustaw globalną sumę tokenów (suma ze wszystkich zakładek)."""
        # 2× NBSP dla odstępu między Σ a liczbą.
        self.total_tokens_label.setText(f"Σ  {value:,}")

    # ---------- Renderowanie: stany puste ----------

    def _render_idle(self):
        """Brak aktywnej zakładki agenta."""
        self._render_idle_mcp()
        self.skills_btn.setText("🧩 —")
        self.skills_btn.setToolTip(tr('status_idle_skills'))
        self.skills_btn.setEnabled(False)
        self.files_btn.setText("📁 —")
        self.files_btn.setToolTip(tr('status_idle_files'))
        self.files_btn.setEnabled(False)
        self.model_btn.setText("🤖 —")
        self.model_btn.setToolTip(tr('status_idle_model'))
        self.model_btn.setEnabled(False)

    def _render_idle_mcp(self):
        self.mcp_btn.setText("🔌 —")
        self.mcp_btn.setToolTip(tr('status_idle_mcp'))
        self.mcp_btn.setEnabled(False)

    def _render_loading_mcp(self):
        self.mcp_btn.setText("🔌 …")
        self.mcp_btn.setToolTip(tr('mcp_checking'))
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
            f"<b>{tr('mcp_servers_title').format(agent=agent_label)}</b>",
            f"  ✅ {tr('mcp_connected')} {counts.get(STATUS_CONNECTED, 0)}",
        ]
        if counts.get(STATUS_NEEDS_AUTH, 0):
            lines.append(f"  🔐 {tr('mcp_needs_auth')} {counts[STATUS_NEEDS_AUTH]}")
        if counts.get(STATUS_FAILED, 0):
            lines.append(f"  ❌ {tr('mcp_failed')} {counts[STATUS_FAILED]}")
        if counts.get(STATUS_UNKNOWN, 0):
            lines.append(f"  ❓ {tr('mcp_unknown')} {counts[STATUS_UNKNOWN]}")

        if active:
            lines.append("")
            lines.append(f"<b>{tr('mcp_active_header')}</b>")
            for s in active:
                icon = self._status_icon(s.status)
                scope_label = self._scope_label(s.scope)
                lines.append(f"  {icon} {s.name} <span style='color:#888'>({scope_label})</span>")

        if disabled:
            lines.append("")
            lines.append(f"<b>{tr('mcp_disabled_header')}</b>")
            for s in disabled:
                lines.append(f"  🚫 {s.name}")

        lines.append("")
        lines.append(f"<i>{tr('mcp_click_open')}</i>")
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
        return {
            "user": tr('scope_user'),
            "local": tr('scope_local'),
            "managed": tr('scope_managed'),
        }.get(scope, scope)

    # ---------- Renderowanie: Skille ----------

    def _render_skills(self):
        """Liczy globalne skille zainstalowane w ~/.claude/skills/, odejmuje
        deny-list bieżącego agenta. Wynik = aktywne dla agenta."""
        self.skills_btn.setEnabled(True)
        try:
            all_skills = SkillsManager().list_skills()
        except Exception:
            self.skills_btn.setText("🧩 ?")
            self.skills_btn.setToolTip(tr('skills_read_error'))
            return

        disabled_names = self._get_disabled_skills_set()
        active = [s for s in all_skills if s.name not in disabled_names and s.folder_name not in disabled_names]
        disabled = [s for s in all_skills if s.name in disabled_names or s.folder_name in disabled_names]

        self.skills_btn.setText(f"🧩 {len(active)}")
        self.skills_btn.setToolTip(self._build_skills_tooltip(active, disabled))

    def _build_skills_tooltip(self, active: List[Skill], disabled: List[Skill]) -> str:
        agent_label = self._agent_name or "—"
        lines = [f"<b>{tr('skills_title').format(agent=agent_label)}</b>"]
        if active:
            lines.append("")
            lines.append(f"<b>{tr('skills_active_n').format(n=len(active))}</b>")
            for s in active[:30]:
                lines.append(f"  🧩 {s.name}")
            if len(active) > 30:
                lines.append(f"  <i>{tr('and_n_more').format(n=len(active) - 30)}</i>")
        else:
            lines.append("")
            lines.append(f"<i>{tr('no_active_skills')}</i>")

        if disabled:
            lines.append("")
            lines.append(f"<b>{tr('skills_disabled_n').format(n=len(disabled))}</b>")
            for s in disabled[:10]:
                lines.append(f"  🚫 {s.name}")
            if len(disabled) > 10:
                lines.append(f"  <i>{tr('and_n_more').format(n=len(disabled) - 10)}</i>")

        lines.append("")
        lines.append(f"<i>{tr('skills_click_open')}</i>")
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
        lines = [f"<b>{tr('files_title').format(agent=agent_label)}</b>"]
        if self._memory_files:
            lines.append("")
            for path_str in self._memory_files[:30]:
                p = Path(path_str)
                # Wyróżnij brak pliku (czerwono)
                if p.exists():
                    lines.append(f"  📄 {p.name} <span style='color:#888'>({p.parent})</span>")
                else:
                    lines.append(f"  ⚠️ {p.name} <span style='color:{theme.DANGER}'>({tr('file_missing')})</span>")
            if len(self._memory_files) > 30:
                lines.append(f"  <i>{tr('and_n_more').format(n=len(self._memory_files) - 30)}</i>")
        else:
            lines.append("")
            lines.append(f"<i>{tr('no_memory_files')}</i>")

        lines.append("")
        if self._agent_id:
            lines.append(f"<i>{tr('files_click_edit')}</i>")
        else:
            lines.append(f"<i>{tr('select_agent_tab')}</i>")
        return "<br>".join(lines)

    # ---------- Renderowanie: Model ----------

    def set_detected_model(self, api_id: Optional[str]):
        """Podaj model WYKRYTY z dziennika sesji aktywnej zakładki.

        Wołane z pętli czytającej dziennik — dlatego przerysowujemy TYLKO przy
        realnej zmianie (inaczej odświeżanie leciałoby kilka razy na sekundę).
        """
        if api_id == self._detected_model:
            return
        self._detected_model = api_id
        self._render_model()

    def _render_model(self):
        """Pokazuje model Claude Code agenta (a przy „Domyślnym" — wykryty)."""
        self.model_btn.setEnabled(self._agent_id is not None)
        short = model_label_short(self._model_key)
        full = model_label(self._model_key)
        # Na pasku jest mało miejsca — pomijamy prefiks "Domyślny —/Default —".
        # W tooltipie pokazujemy pełną etykietę z prefiksem zachowanym.
        prefix = model_default_prefix()
        if short.startswith(prefix):
            short = short[len(prefix):]
        # Ustawienie „Domyślny" NIE mówi, kto realnie odpowiada (Claude Code
        # rozwija je po swojemu, a alias `opus` to zawsze NAJNOWSZY Opus).
        # Nazwę bierzemy z dziennika sesji; gdy jej brak — zostaje samo
        # „Domyślny", bo lepiej nic nie twierdzić niż zgadywać.
        detected = ""
        if self._model_key == DEFAULT_AGENT_MODEL:
            detected = model_name_for_api_id(self._detected_model or "")
            if detected:
                short = tr('model_default_detected').format(name=detected)
        self.model_btn.setText(f"🤖 {short}")
        agent_label = self._agent_name or "—"
        tooltip_lines = [
            f"<b>{tr('model_title').format(agent=agent_label)}</b>",
            "",
            f"  🤖 {full}",
            "",
        ]
        if detected:
            tooltip_lines.insert(3, f"  {tr('model_detected_line').format(name=detected)}")
        if self._agent_id:
            tooltip_lines.append(f"<i>{tr('model_click_change')}</i>")
        else:
            tooltip_lines.append(f"<i>{tr('select_agent_tab')}</i>")
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
            self._render_invalid_mcp(tr('mcp_dir_missing').format(path=self._working_dir))
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
            self._render_invalid_mcp(tr('mcp_check_failed'))
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
