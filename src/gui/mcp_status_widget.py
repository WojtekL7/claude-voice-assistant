"""
Claude Voice Assistant - MCP Status Widget
Pasek statusu MCP w QStatusBar — pokazuje liczbę aktywnych/needs_auth/failed
serwerów MCP dla bieżącego agenta.

Cache: 30 sekund per working_dir (klikanie po zakładkach jest natychmiastowe).
Refresh: w tle (threading.Thread + pyqtSignal — nie blokuje UI).
"""
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QToolButton,
    QMenu, QAction, QMessageBox,
)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.mcp_manager import (
    McpManager, McpServer, McpError,
    STATUS_CONNECTED, STATUS_NEEDS_AUTH, STATUS_FAILED, STATUS_UNKNOWN,
)
from core.agent_mcp_settings import AgentMcpSettings


CACHE_TTL_SECONDS = 30


class McpStatusWidget(QWidget):
    """Widget statusu MCP w QStatusBar.

    Pokazuje 3 kafelki (✅/🔐/❌) z liczbą serwerów + przyciski [🔄] [⚙️].
    Sygnały:
      - request_open_manager(working_dir) — gdy user klika cyfry albo ⚙️→Otwórz
      - mcp_changed() — gdy stan się zmienia (po toggle all)
    """

    request_open_manager = pyqtSignal(object)  # Optional[Path]
    mcp_changed = pyqtSignal()

    # Wewnętrzny sygnał — z wątku roboczego do GUI
    _data_loaded = pyqtSignal(object)  # list[McpServer] albo None gdy błąd

    def __init__(self, parent=None):
        super().__init__(parent)
        self._working_dir: Optional[Path] = None
        self._agent_name: Optional[str] = None
        # Cache: {working_dir_str: (timestamp, [McpServer, ...])}
        self._cache: Dict[str, Tuple[float, List[McpServer]]] = {}
        self._loading: bool = False
        self._setup_ui()
        self._data_loaded.connect(self._on_data_loaded)
        self._render_idle()

    # ---------- Public API ----------

    def set_agent(self, working_dir: Optional[Path], agent_name: Optional[str] = None):
        """Ustaw kontekst (zmiana zakładki). Próbuje cache, w razie potrzeby ładuje w tle."""
        self._working_dir = Path(working_dir) if working_dir else None
        self._agent_name = agent_name

        if self._working_dir is None:
            self._render_idle()
            return

        cached = self._read_cache(self._working_dir)
        if cached is not None:
            self._render_servers(cached)
            return

        self._render_loading()
        self._refresh_async()

    def force_refresh(self):
        """Wymuszone odświeżenie — ignoruje cache."""
        if self._working_dir is None:
            self._render_idle()
            return
        # Inwaliduj cache dla bieżącego working_dir
        self._cache.pop(str(self._working_dir), None)
        self._render_loading()
        self._refresh_async()

    # ---------- UI ----------

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # Główny "kafelek" z licznikami — klikalny (otwiera menedżer)
        self.summary_btn = QPushButton()
        self.summary_btn.setFlat(True)
        self.summary_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.summary_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a1a3a;
                border-color: #6a2a5a;
            }
        """)
        self.summary_btn.clicked.connect(self._on_summary_click)
        layout.addWidget(self.summary_btn)

        # Refresh button
        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("🔄")
        self.refresh_btn.setToolTip("Odśwież status MCP")
        self.refresh_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.refresh_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #4a1a3a;
                border-color: #6a2a5a;
            }
        """)
        self.refresh_btn.clicked.connect(self.force_refresh)
        layout.addWidget(self.refresh_btn)

        # Menu button
        self.menu_btn = QToolButton()
        self.menu_btn.setText("⚙️")
        self.menu_btn.setToolTip("Akcje MCP dla bieżącego agenta")
        self.menu_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.menu_btn.setStyleSheet(self.refresh_btn.styleSheet())
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self._build_menu()
        layout.addWidget(self.menu_btn)

    def _build_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
            }
            QMenu::item:selected {
                background-color: #6a2a5a;
            }
            QMenu::separator {
                background-color: #4a1a3a;
                height: 1px;
            }
        """)
        self._action_open = QAction("🔌 Otwórz menedżer MCP", self)
        self._action_open.triggered.connect(self._on_summary_click)
        menu.addAction(self._action_open)

        menu.addSeparator()

        self._action_disable_all = QAction("🔇 Wyłącz wszystkie globalne dla tego agenta", self)
        self._action_disable_all.triggered.connect(self._on_disable_all_global)
        menu.addAction(self._action_disable_all)

        self._action_enable_all = QAction("🔊 Włącz wszystkie z powrotem", self)
        self._action_enable_all.triggered.connect(self._on_enable_all_global)
        menu.addAction(self._action_enable_all)

        self.menu_btn.setMenu(menu)

    # ---------- Renderowanie ----------

    def _render_idle(self):
        """Brak aktywnej zakładki / brak working_dir."""
        self.summary_btn.setText("🔌 —")
        self.summary_btn.setToolTip("Wybierz aktywną zakładkę z agentem.")
        self._set_actions_enabled(False)

    def _render_loading(self):
        self.summary_btn.setText("🔌 …")
        self.summary_btn.setToolTip("Sprawdzam status MCP...")

    def _render_invalid(self, msg: str):
        self.summary_btn.setText("🔌 ?")
        self.summary_btn.setToolTip(msg)
        self._set_actions_enabled(False)

    def _render_servers(self, servers: List[McpServer]):
        """Renderuje liczniki + tooltip z pełną listą."""
        self._set_actions_enabled(True)

        # Filtruj wg deny list bieżącego agenta
        disabled_set = self._get_disabled_set()
        active = [s for s in servers if s.sanitized_name not in disabled_set]
        disabled = [s for s in servers if s.sanitized_name in disabled_set]

        # Liczniki po statusie (tylko dla aktywnych)
        counts = {STATUS_CONNECTED: 0, STATUS_NEEDS_AUTH: 0, STATUS_FAILED: 0, STATUS_UNKNOWN: 0}
        for s in active:
            counts[s.status] = counts.get(s.status, 0) + 1

        # Skrót dla pustej listy
        if not servers:
            self.summary_btn.setText("🔌 brak")
            self.summary_btn.setToolTip(
                f"Agent „{self._agent_name or '—'}\" nie ma żadnych zarejestrowanych MCP."
            )
            return

        # Tekst kafelka — pomijamy zera, ale pokazujemy ✅ zawsze (dla wskazania że są aktywne)
        parts = []
        parts.append(f"{counts[STATUS_CONNECTED]}✅")
        if counts[STATUS_NEEDS_AUTH]:
            parts.append(f"{counts[STATUS_NEEDS_AUTH]}🔐")
        if counts[STATUS_FAILED]:
            parts.append(f"{counts[STATUS_FAILED]}❌")
        if counts[STATUS_UNKNOWN]:
            parts.append(f"{counts[STATUS_UNKNOWN]}❓")
        self.summary_btn.setText("🔌 " + " ".join(parts))

        # Tooltip — pełna lista
        self.summary_btn.setToolTip(self._build_tooltip(active, disabled))

    def _build_tooltip(self, active: List[McpServer], disabled: List[McpServer]) -> str:
        agent_label = self._agent_name or "—"
        lines = [f"<b>Aktywne MCP dla agenta „{agent_label}\":</b>"]
        if active:
            for s in active:
                icon = self._status_icon(s.status)
                scope_label = self._scope_label(s.scope)
                lines.append(f"  {icon} {s.name} <span style='color:#888'>({scope_label})</span>")
        else:
            lines.append("  <i>(brak aktywnych)</i>")

        if disabled:
            lines.append("")
            lines.append("<b>Wyłączone dla tego agenta:</b>")
            for s in disabled:
                lines.append(f"  🚫 {s.name}")

        lines.append("")
        lines.append(
            f"<i>Razem: {len(active) + len(disabled)} zarejestrowanych, "
            f"{len(disabled)} wyłączonych dla tego agenta.</i>"
        )
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

    def _set_actions_enabled(self, enabled: bool):
        self.refresh_btn.setEnabled(enabled)
        self.menu_btn.setEnabled(enabled)

    # ---------- Cache ----------

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

    # ---------- Background refresh ----------

    def _refresh_async(self):
        if self._loading:
            return
        if self._working_dir is None:
            return
        if not self._working_dir.is_dir():
            self._render_invalid(
                f"Katalog roboczy nie istnieje: {self._working_dir}"
            )
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
            self._data_loaded.emit(servers)

        threading.Thread(target=worker, daemon=True).start()

    def _on_data_loaded(self, servers):
        self._loading = False
        if servers is None:
            self._render_invalid(
                "Nie udało się sprawdzić statusu MCP. "
                "Sprawdź czy Claude Code (komenda 'claude') jest zainstalowany."
            )
            return
        if self._working_dir is not None:
            self._write_cache(self._working_dir, servers)
        self._render_servers(servers)

    def _get_disabled_set(self) -> set:
        if self._working_dir is None or not self._working_dir.is_dir():
            return set()
        try:
            return set(AgentMcpSettings(self._working_dir).get_disabled_mcp_sanitized())
        except Exception:
            return set()

    # ---------- Akcje ----------

    def _on_summary_click(self):
        if self._working_dir is None:
            return
        self.request_open_manager.emit(self._working_dir)

    def _on_disable_all_global(self):
        if self._working_dir is None or not self._working_dir.is_dir():
            return
        cached = self._read_cache(self._working_dir)
        servers = cached if cached is not None else []
        # Ten widget jest dla "globalnych" — czyli scope user + managed
        global_servers = [s for s in servers if s.scope in ("user", "managed")]
        if not global_servers:
            QMessageBox.information(
                self, "Brak globalnych MCP",
                "Ten agent nie ma globalnych MCP do wyłączenia."
            )
            return

        names = [s.name for s in global_servers]
        reply = QMessageBox.question(
            self, "Potwierdź",
            f"Wyłączyć dla agenta „{self._agent_name or '—'}\" wszystkie globalne MCP?\n\n"
            f"Lista: {', '.join(names[:5])}{'…' if len(names) > 5 else ''}\n\n"
            "Możesz to cofnąć przez „🔊 Włącz wszystkie z powrotem\".",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            AgentMcpSettings(self._working_dir).disable_all(names)
        except Exception as exc:
            QMessageBox.warning(self, "Błąd zapisu", f"Nie udało się zapisać: {exc}")
            return

        self.mcp_changed.emit()
        self.force_refresh()

    def _on_enable_all_global(self):
        if self._working_dir is None or not self._working_dir.is_dir():
            return
        try:
            settings = AgentMcpSettings(self._working_dir)
            if not settings.get_disabled_mcp_sanitized():
                QMessageBox.information(
                    self, "Nic do włączenia",
                    "Żaden globalny MCP nie jest wyłączony dla tego agenta."
                )
                return
            settings.enable_all()
        except Exception as exc:
            QMessageBox.warning(self, "Błąd zapisu", f"Nie udało się zapisać: {exc}")
            return

        self.mcp_changed.emit()
        self.force_refresh()
