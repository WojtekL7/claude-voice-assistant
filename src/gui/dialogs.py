"""
Claude Voice Assistant - Dialogs
Dialog windows for agents and memory projects management.
"""
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QFileDialog,
    QMessageBox, QListWidget, QListWidgetItem, QRadioButton,
    QButtonGroup, QWidget, QSplitter, QFrame, QInputDialog,
    QListView, QPlainTextEdit, QStackedWidget, QTabWidget
)
from PyQt5.QtCore import Qt, QSize, QUrl, QTimer, pyqtSignal
import threading
from PyQt5.QtGui import QFont, QDesktopServices

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MEMORY_PROJECTS_FILE, AGENTS_FILE, MEMORY_FILE_EXTENSIONS,
    DEFAULT_AGENTS, DEFAULT_MEMORY_PROJECTS, ASSETS_DIR,
    CLAUDE_MODELS, CLAUDE_MODELS_SHORT, DEFAULT_AGENT_MODEL,
    NEW_AGENT_DEFAULT_MODEL
)
from core.skills_manager import SkillsManager, Skill, SkillInstallError
from core.agent_skills_settings import AgentSkillsSettings
from core.mcp_manager import (
    McpManager, McpServer, McpError,
    STATUS_CONNECTED, STATUS_NEEDS_AUTH, STATUS_FAILED, STATUS_UNKNOWN,
)
from core.agent_mcp_settings import AgentMcpSettings
from core.mcp_templates import MCP_TEMPLATES, McpTemplate


# === Stylizowane dialogi plików ===

# Domyślne kolory dla dialogów (ciemny motyw)
DIALOG_COLORS = {
    'bg': '#300A24',
    'text': '#ffffff',
    'input_bg': '#4a1a3a',
    'border': '#6a2a5a',
    'hover': '#7a3a6a',
    'selection': '#8a4a7a',
}


def get_file_dialog_stylesheet() -> str:
    """Zwraca stylesheet dla stylizowanych dialogów plików."""
    c = DIALOG_COLORS
    return f"""
        QFileDialog {{
            background-color: {c['bg']};
            color: {c['text']};
        }}
        QFileDialog QLabel {{
            color: {c['text']};
        }}
        QFileDialog QLineEdit {{
            background-color: {c['input_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QFileDialog QComboBox {{
            background-color: {c['input_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QFileDialog QComboBox::drop-down {{
            border: none;
        }}
        QFileDialog QComboBox QAbstractItemView {{
            background-color: {c['input_bg']};
            color: {c['text']};
            selection-background-color: {c['selection']};
        }}
        QFileDialog QPushButton {{
            background-color: {c['input_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 6px 16px;
            min-width: 80px;
        }}
        QFileDialog QPushButton:hover {{
            background-color: {c['hover']};
        }}
        QFileDialog QPushButton:pressed {{
            background-color: {c['selection']};
        }}
        QFileDialog QTreeView, QFileDialog QListView {{
            background-color: {c['input_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
        }}
        QFileDialog QTreeView::item:hover, QFileDialog QListView::item:hover {{
            background-color: {c['hover']};
        }}
        QFileDialog QTreeView::item:selected, QFileDialog QListView::item:selected {{
            background-color: {c['selection']};
        }}
        QFileDialog QHeaderView::section {{
            background-color: {c['input_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            padding: 4px;
        }}
        QFileDialog QToolButton {{
            background-color: {c['input_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px;
        }}
        QFileDialog QToolButton:hover {{
            background-color: {c['hover']};
        }}
        QFileDialog QSplitter::handle {{
            background-color: {c['border']};
        }}
        QFileDialog QScrollBar:vertical {{
            background-color: {c['bg']};
            width: 12px;
            border-radius: 6px;
        }}
        QFileDialog QScrollBar::handle:vertical {{
            background-color: {c['border']};
            border-radius: 6px;
            min-height: 20px;
        }}
        QFileDialog QScrollBar::handle:vertical:hover {{
            background-color: {c['hover']};
        }}
        QFileDialog QScrollBar:horizontal {{
            background-color: {c['bg']};
            height: 12px;
            border-radius: 6px;
        }}
        QFileDialog QScrollBar::handle:horizontal {{
            background-color: {c['border']};
            border-radius: 6px;
            min-width: 20px;
        }}
        QFileDialog QScrollBar::add-line, QFileDialog QScrollBar::sub-line {{
            width: 0px;
            height: 0px;
        }}
    """


def setup_file_dialog_labels(dialog: QFileDialog):
    """Ustawia polskie etykiety dla dialogu plików."""
    dialog.setLabelText(QFileDialog.LookIn, "Szukaj w:")
    dialog.setLabelText(QFileDialog.FileName, "Nazwa:")
    dialog.setLabelText(QFileDialog.FileType, "Typ plików:")
    dialog.setLabelText(QFileDialog.Accept, "Wybierz")
    dialog.setLabelText(QFileDialog.Reject, "Anuluj")


def styled_get_existing_directory(parent, title: str, directory: str = "") -> str:
    """Stylizowany dialog wyboru katalogu z polskimi etykietami."""
    dialog = QFileDialog(parent, title, directory or str(Path.home()))
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setStyleSheet(get_file_dialog_stylesheet())
    setup_file_dialog_labels(dialog)

    if dialog.exec_() == QFileDialog.Accepted:
        selected = dialog.selectedFiles()
        return selected[0] if selected else ""
    return ""


def styled_get_open_file_names(parent, title: str, directory: str = "",
                                file_filter: str = "") -> tuple:
    """Stylizowany dialog wyboru wielu plików z polskimi etykietami."""
    dialog = QFileDialog(parent, title, directory or str(Path.home()), file_filter)
    dialog.setFileMode(QFileDialog.ExistingFiles)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setStyleSheet(get_file_dialog_stylesheet())
    setup_file_dialog_labels(dialog)

    if dialog.exec_() == QFileDialog.Accepted:
        return dialog.selectedFiles(), dialog.selectedNameFilter()
    return [], ""


def styled_get_open_file_name(parent, title: str, directory: str = "",
                               file_filter: str = "") -> tuple:
    """Stylizowany dialog wyboru pojedynczego pliku z polskimi etykietami."""
    dialog = QFileDialog(parent, title, directory or str(Path.home()), file_filter)
    dialog.setFileMode(QFileDialog.ExistingFile)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setStyleSheet(get_file_dialog_stylesheet())
    setup_file_dialog_labels(dialog)

    if dialog.exec_() == QFileDialog.Accepted:
        selected = dialog.selectedFiles()
        return (selected[0] if selected else "", dialog.selectedNameFilter())
    return "", ""


def styled_get_save_file_name(parent, title: str, directory: str = "",
                               file_filter: str = "") -> tuple:
    """Stylizowany dialog zapisu pliku z polskimi etykietami."""
    dialog = QFileDialog(parent, title, directory or str(Path.home()), file_filter)
    dialog.setFileMode(QFileDialog.AnyFile)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setStyleSheet(get_file_dialog_stylesheet())
    setup_file_dialog_labels(dialog)
    # Zmień etykietę "Wybierz" na "Zapisz" dla dialogu zapisu
    dialog.setLabelText(QFileDialog.Accept, "Zapisz")

    if dialog.exec_() == QFileDialog.Accepted:
        selected = dialog.selectedFiles()
        return (selected[0] if selected else "", dialog.selectedNameFilter())
    return "", ""


class MemoryProjectsDialog(QDialog):
    """Dialog for managing memory projects and their files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pliki pamięci projektów")
        self.setMinimumSize(650, 550)

        self.memory_projects = self._load_memory_projects()
        self._setup_ui()

    def _load_memory_projects(self) -> list:
        """Load memory projects from file."""
        if MEMORY_PROJECTS_FILE.exists():
            try:
                with open(MEMORY_PROJECTS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return DEFAULT_MEMORY_PROJECTS.copy()

    def _save_memory_projects(self):
        """Save memory projects to file."""
        try:
            with open(MEMORY_PROJECTS_FILE, 'w') as f:
                json.dump(self.memory_projects, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Nie można zapisać: {e}")

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Path to checkmark icon
        checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")

        # Header
        header = QLabel("Zarządzaj projektami i ich plikami pamięci")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Description
        desc = QLabel("Pliki pamięci są automatycznie wysyłane do Claude Code jako kontekst przy starcie sesji.")
        desc.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Tree widget for projects and files
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nazwa", "Ścieżka"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }}
            QTreeWidget::item {{
                padding: 5px;
            }}
            QTreeWidget::item:selected {{
                background-color: #6a2a5a;
            }}
            QTreeWidget::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #4a1a3a;
                border-radius: 3px;
                background-color: transparent;
            }}
            QTreeWidget::indicator:hover {{
                border-color: #22c55e;
            }}
            QTreeWidget::indicator:checked {{
                background-color: #22c55e;
                border-color: #22c55e;
                border-radius: 3px;
                image: url("{checkmark_path}");
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                border-image: none;
                image: none;
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                border-image: none;
                image: none;
            }}
            QHeaderView::section {{
                background-color: #4a1a3a;
                color: #ffffff;
                padding: 5px;
                border: none;
                font-weight: bold;
            }}
        """)
        self._populate_tree()
        layout.addWidget(self.tree, stretch=1)

        # Buttons for projects
        project_btn_layout = QHBoxLayout()

        add_project_btn = QPushButton("➕ Dodaj projekt")
        add_project_btn.clicked.connect(self._add_project)
        project_btn_layout.addWidget(add_project_btn)

        add_file_btn = QPushButton("📄 Dodaj plik")
        add_file_btn.clicked.connect(self._add_file)
        project_btn_layout.addWidget(add_file_btn)

        add_folder_btn = QPushButton("📁 Dodaj folder")
        add_folder_btn.clicked.connect(self._add_folder)
        project_btn_layout.addWidget(add_folder_btn)

        project_btn_layout.addStretch()

        edit_btn = QPushButton("✏️ Edytuj")
        edit_btn.clicked.connect(self._edit_selected)
        project_btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ Usuń")
        delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        delete_btn.clicked.connect(self._delete_selected)
        project_btn_layout.addWidget(delete_btn)

        layout.addLayout(project_btn_layout)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Zapisz")
        save_btn.clicked.connect(self._save_and_close)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        bottom_layout.addWidget(save_btn)

        layout.addLayout(bottom_layout)

    def _populate_tree(self):
        """Populate tree with projects and files."""
        self.tree.clear()

        for project in self.memory_projects:
            project_item = QTreeWidgetItem([
                f"📁 {project.get('name', 'Bez nazwy')}",
                ""
            ])
            project_item.setData(0, Qt.UserRole, {'type': 'project', 'data': project})
            project_item.setCheckState(0, Qt.Checked if project.get('enabled', True) else Qt.Unchecked)

            for file_info in project.get('files', []):
                file_path = file_info.get('path', '')
                file_name = Path(file_path).name if file_path else 'Brak pliku'

                file_item = QTreeWidgetItem([
                    f"  📄 {file_name}",
                    file_path
                ])
                file_item.setData(0, Qt.UserRole, {'type': 'file', 'data': file_info, 'project': project})
                file_item.setCheckState(0, Qt.Checked if file_info.get('enabled', True) else Qt.Unchecked)
                project_item.addChild(file_item)

            self.tree.addTopLevelItem(project_item)
            project_item.setExpanded(True)

    def _add_project(self):
        """Add new project."""
        dialog = ProjectEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            project_data = dialog.get_data()
            project_data['id'] = str(uuid.uuid4())[:8]
            project_data['files'] = []
            project_data['enabled'] = True
            self.memory_projects.append(project_data)
            self._populate_tree()

    def _add_file(self):
        """Add file to selected project."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz projekt, do którego chcesz dodać plik.")
            return

        # Get project (either selected or parent)
        item_data = selected.data(0, Qt.UserRole)
        if item_data['type'] == 'file':
            project = item_data['project']
        else:
            project = item_data['data']

        # File dialog (stylizowany)
        file_filter = "Pliki pamięci (*.md *.txt *.json);;Wszystkie pliki (*)"
        files, _ = styled_get_open_file_names(
            self, "Wybierz pliki pamięci", str(Path.home()), file_filter
        )

        if files:
            for file_path in files:
                # Check if file already exists in project
                existing_paths = [f.get('path') for f in project.get('files', [])]
                if file_path not in existing_paths:
                    project.setdefault('files', []).append({
                        'path': file_path,
                        'enabled': True
                    })

            self._populate_tree()

    def _add_folder(self):
        """Add all compatible files from folder to selected project."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz projekt, do którego chcesz dodać pliki.")
            return

        # Get project
        item_data = selected.data(0, Qt.UserRole)
        if item_data['type'] == 'file':
            project = item_data['project']
        else:
            project = item_data['data']

        # Folder dialog (stylizowany)
        folder = styled_get_existing_directory(
            self, "Wybierz folder z plikami", str(Path.home())
        )

        if folder:
            folder_path = Path(folder)
            files_added = 0

            for ext in MEMORY_FILE_EXTENSIONS:
                for file_path in folder_path.glob(f"*{ext}"):
                    existing_paths = [f.get('path') for f in project.get('files', [])]
                    if str(file_path) not in existing_paths:
                        project.setdefault('files', []).append({
                            'path': str(file_path),
                            'enabled': True
                        })
                        files_added += 1

            if files_added > 0:
                self._populate_tree()
                QMessageBox.information(self, "Dodano pliki", f"Dodano {files_added} plików z folderu.")
            else:
                QMessageBox.information(self, "Brak plików", "Nie znaleziono nowych plików do dodania.")

    def _edit_selected(self):
        """Edit selected project or file."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz element do edycji.")
            return

        item_data = selected.data(0, Qt.UserRole)

        if item_data['type'] == 'project':
            project = item_data['data']
            dialog = ProjectEditDialog(self, project)
            if dialog.exec_() == QDialog.Accepted:
                new_data = dialog.get_data()
                project['name'] = new_data['name']
                self._populate_tree()

    def _delete_selected(self):
        """Delete selected project or file."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz element do usunięcia.")
            return

        item_data = selected.data(0, Qt.UserRole)

        if item_data['type'] == 'project':
            project = item_data['data']
            reply = QMessageBox.question(
                self, "Potwierdź usunięcie",
                f"Czy na pewno usunąć projekt \"{project.get('name')}\" i wszystkie jego pliki?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.memory_projects.remove(project)
                self._populate_tree()

        elif item_data['type'] == 'file':
            file_info = item_data['data']
            project = item_data['project']

            reply = QMessageBox.question(
                self, "Potwierdź usunięcie",
                f"Czy na pewno usunąć plik \"{Path(file_info.get('path', '')).name}\"?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                project['files'].remove(file_info)
                self._populate_tree()

    def _save_and_close(self):
        """Update checkboxes state and save."""
        # Update enabled state from checkboxes
        for i in range(self.tree.topLevelItemCount()):
            project_item = self.tree.topLevelItem(i)
            project_data = project_item.data(0, Qt.UserRole)['data']
            project_data['enabled'] = project_item.checkState(0) == Qt.Checked

            for j in range(project_item.childCount()):
                file_item = project_item.child(j)
                file_data = file_item.data(0, Qt.UserRole)['data']
                file_data['enabled'] = file_item.checkState(0) == Qt.Checked

        self._save_memory_projects()
        self.accept()

    def get_memory_projects(self) -> list:
        """Return memory projects list."""
        return self.memory_projects


class ProjectEditDialog(QDialog):
    """Dialog for editing project name."""

    def __init__(self, parent=None, project: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Edytuj projekt" if project else "Nowy projekt")
        self.setMinimumWidth(400)

        self.project = project or {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_input = QLineEdit(self.project.get('name', ''))
        self.name_input.setPlaceholderText("np. Fulfillment CRM")
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form.addRow("Nazwa projektu:", self.name_input)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Zapisz")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save(self):
        """Validate and save."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę projektu.")
            return
        self.accept()

    def get_data(self) -> dict:
        """Return edited data."""
        return {
            'name': self.name_input.text().strip()
        }


class _StyledComboBox(QComboBox):
    """ComboBox with a popup container styled to match the dark theme.
    Without this override, the popup window's outer frame stays in the
    system default colors and shows as white strips above/below the items.
    """

    _POPUP_CONTAINER_STYLE = (
        "background-color: #2d0a1e;"
        "border: 1px solid #4a1a3a;"
        "border-radius: 4px;"
    )

    def showPopup(self):
        super().showPopup()
        container = self.view().parentWidget()
        if container is not None:
            container.setStyleSheet(self._POPUP_CONTAINER_STYLE)


class AgentConfigDialog(QDialog):
    """Dialog for configuring a single agent."""

    def __init__(self, parent=None, agent: dict = None, memory_projects: list = None):
        super().__init__(parent)
        self.setWindowTitle("Edytuj agenta" if agent else "Nowy agent")

        self.is_new_agent = agent is None
        self.agent = agent or {}
        self.memory_projects = memory_projects or []  # kept for compatibility but not used
        self.memory_files = list(self.agent.get('memory_files', []))  # list of file paths
        self.run_immediately = False  # Flag: should open tab immediately after save

        # Stała wysokość — żeby okno mieściło się na każdym ekranie laptopowym
        self.setFixedHeight(580)
        self.setMinimumWidth(640)

        # Path to checkmark icon (used by checkboxes inside Tab "Podstawowe")
        self._checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")

        self._setup_ui()

    # ---------- Style helpers ----------

    @staticmethod
    def _input_style() -> str:
        return """
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """

    @staticmethod
    def _section_button_style() -> str:
        """Styl przycisków „Zarządzaj lokalnymi skillami/MCP"."""
        return """
            QPushButton {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
                text-align: left;
            }
            QPushButton:hover:enabled {
                border-color: #22c55e;
            }
            QPushButton:disabled {
                color: #777777;
            }
        """

    @staticmethod
    def _list_style() -> str:
        return """
            QListWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #3a1428;
            }
            QListWidget::item:selected {
                background-color: #4a1a3a;
            }
        """

    def _checkbox_style(self) -> str:
        return f"""
            QCheckBox {{
                color: #ffffff;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid #4a1a3a;
                border-radius: 3px;
                background-color: transparent;
            }}
            QCheckBox::indicator:hover {{
                border-color: #22c55e;
            }}
            QCheckBox::indicator:checked {{
                background-color: #22c55e;
                border-color: #22c55e;
                border-radius: 3px;
                image: url("{self._checkmark_path}");
            }}
        """

    # ---------- Main UI ----------

    def _setup_ui(self):
        """Setup dialog UI with 4 tabs (Podstawowe / Pamięć / Skille / MCP)."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QLabel("Konfiguracja agenta")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #4a1a3a;
                background: #2d0a1e;
                border-radius: 4px;
                top: -1px;
            }
            QTabBar::tab {
                background: #1d0518;
                color: #cccccc;
                padding: 8px 14px;
                border: 1px solid #4a1a3a;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #2d0a1e;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #4a1a3a;
                color: #ffffff;
            }
        """)
        self.tabs.addTab(self._build_tab_basic(), "📝 Podstawowe")
        self.tabs.addTab(self._build_tab_memory(), "💾 Pamięć")
        self.tabs.addTab(self._build_tab_skills(), "🧩 Skille")
        self.tabs.addTab(self._build_tab_mcp(), "🔌 MCP")
        main_layout.addWidget(self.tabs, stretch=1)

        # Single connection — wszystkie sekcje (skills 1A/1B + MCP 1A/1B) odświeżają się
        # gdy user zmieni katalog roboczy. Łączymy DOPIERO po utworzeniu wszystkich zakładek.
        self.dir_input.textChanged.connect(self._on_working_dir_changed)

        # Buttons (poza zakładkami — zawsze widoczne na dole)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Zapisz")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        btn_layout.addWidget(save_btn)

        save_run_btn = QPushButton("Zapisz i uruchom")
        save_run_btn.clicked.connect(self._save_and_run)
        save_run_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        btn_layout.addWidget(save_run_btn)

        main_layout.addLayout(btn_layout)

    # ---------- Tab builders ----------

    def _build_tab_basic(self) -> QWidget:
        """Tab 1: nazwa, katalog roboczy, model, checkboxy."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 16, 12, 12)

        form = QFormLayout()
        form.setSpacing(10)

        # Name
        self.name_input = QLineEdit(self.agent.get('name', ''))
        self.name_input.setPlaceholderText("np. CRM Development")
        self.name_input.setStyleSheet(self._input_style())
        form.addRow("Nazwa agenta:", self.name_input)

        # Working directory
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit(self.agent.get('working_directory', str(Path.home())))
        self.dir_input.setStyleSheet(self._input_style())
        dir_layout.addWidget(self.dir_input)

        browse_btn = QPushButton("📁")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_btn)
        form.addRow("Katalog roboczy:", dir_layout)

        # Model Claude Code
        chevron_path = str(ASSETS_DIR / "chevron-down.svg").replace("\\", "/")
        self.model_combo = _StyledComboBox()
        self.model_combo.setMinimumHeight(36)
        model_view = QListView()
        model_view.setMouseTracking(True)
        model_view.setFrameShape(QFrame.NoFrame)
        self.model_combo.setView(model_view)
        self.model_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 6px 36px 6px 10px;
                combobox-popup: 0;
            }}
            QComboBox:hover {{ border-color: #22c55e; }}
            QComboBox:on {{ border-color: #22c55e; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #4a1a3a;
                background-color: #3a0f28;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::drop-down:hover {{ background-color: #4a1a3a; }}
            QComboBox::down-arrow {{
                image: url("{chevron_path}");
                width: 10px;
                height: 6px;
            }}
            QComboBox QListView {{
                background-color: #2d0a1e;
                color: #ffffff;
                border: none;
                outline: 0;
                padding: 0;
            }}
            QComboBox QListView::item {{
                padding: 8px 12px;
                min-height: 26px;
                border: none;
            }}
            QComboBox QListView::item:selected {{
                background-color: #4a1a3a;
                color: #ffffff;
            }}
        """)
        for key, label in CLAUDE_MODELS.items():
            self.model_combo.addItem(label, key)
        current_model = (NEW_AGENT_DEFAULT_MODEL if self.is_new_agent
                         else self.agent.get('model', DEFAULT_AGENT_MODEL))
        idx = self.model_combo.findData(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        form.addRow("Model Claude Code:", self.model_combo)

        model_hint = QLabel("Zmiana modelu wymaga restartu agenta (Stop → Uruchom).")
        model_hint.setStyleSheet("color: #888888; font-size: 11px;")
        form.addRow("", model_hint)

        layout.addLayout(form)

        # Checkboxes
        cb_style = self._checkbox_style()

        self.auto_start_checkbox = QCheckBox("Uruchamiaj automatycznie przy starcie aplikacji")
        self.auto_start_checkbox.setChecked(self.agent.get('auto_start', True))
        self.auto_start_checkbox.setStyleSheet(cb_style)
        layout.addWidget(self.auto_start_checkbox)

        self.send_memory_checkbox = QCheckBox("Wczytaj pliki pamięci po starcie Claude Code")
        self.send_memory_checkbox.setChecked(self.agent.get('send_memory_on_start', True))
        self.send_memory_checkbox.setStyleSheet(cb_style)
        layout.addWidget(self.send_memory_checkbox)

        layout.addStretch()
        return widget

    def _build_tab_memory(self) -> QWidget:
        """Tab 2: pliki pamięci."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 16, 12, 12)

        memory_label = QLabel("📄 Pliki pamięci agenta:")
        memory_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(memory_label)

        memory_info = QLabel(
            "ℹ️ Pliki wczytywane przy starcie agenta — Claude Code dostaje je "
            "jako kontekst rozmowy."
        )
        memory_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        memory_info.setWordWrap(True)
        layout.addWidget(memory_info)

        self.memory_files_container = QVBoxLayout()
        self.memory_files_container.setSpacing(5)

        for file_path in self.memory_files:
            self._add_memory_file_chip(file_path)

        layout.addLayout(self.memory_files_container)

        add_file_btn = QPushButton("+ Dodaj plik")
        add_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d0a1e;
                color: #22c55e;
                border: 1px dashed #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                border-color: #22c55e;
            }
        """)
        add_file_btn.clicked.connect(self._add_memory_file)
        layout.addWidget(add_file_btn)

        layout.addStretch()
        return widget

    def _build_tab_skills(self) -> QWidget:
        """Tab 3: skille agenta + wyłączanie globalnych."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 16, 12, 12)

        # === Lokalne skille agenta ===
        skills_label = QLabel("🧩 Skille tego agenta:")
        skills_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(skills_label)

        skills_info = QLabel(
            "ℹ️ Każdy agent dziedziczy globalne skille z menu Rozszerzenia. "
            "Tutaj możesz dodać dodatkowe — widoczne tylko dla tego agenta."
        )
        skills_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        skills_info.setWordWrap(True)
        layout.addWidget(skills_info)

        self.manage_agent_skills_btn = QPushButton()
        self.manage_agent_skills_btn.setStyleSheet(self._section_button_style())
        self.manage_agent_skills_btn.clicked.connect(self._open_agent_skills)
        layout.addWidget(self.manage_agent_skills_btn)
        self._update_agent_skills_button()

        # === Wyłączanie globalnych skilli ===
        disable_skills_label = QLabel("🚫 Wyłącz globalne skille dla tego agenta:")
        disable_skills_label.setStyleSheet("color: #ffffff; margin-top: 6px;")
        layout.addWidget(disable_skills_label)

        disable_skills_info = QLabel(
            "ℹ️ Globalne skille są domyślnie aktywne. Odznacz te, których ten "
            "agent ma nie używać. Zapis dzieje się natychmiast."
        )
        disable_skills_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        disable_skills_info.setWordWrap(True)
        layout.addWidget(disable_skills_info)

        self.global_skills_count_label = QLabel("")
        self.global_skills_count_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        layout.addWidget(self.global_skills_count_label)

        self.global_skills_list = QListWidget()
        self.global_skills_list.setMinimumHeight(140)
        self.global_skills_list.setWordWrap(True)
        self.global_skills_list.setTextElideMode(Qt.ElideNone)
        self.global_skills_list.setStyleSheet(self._list_style())
        layout.addWidget(self.global_skills_list, stretch=1)

        self._refresh_global_skills_section()

        return widget

    def _build_tab_mcp(self) -> QWidget:
        """Tab 4: serwery MCP agenta + wyłączanie globalnych."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 16, 12, 12)

        # === Lokalne MCP agenta ===
        mcp_label = QLabel("🔌 Serwery MCP tego agenta:")
        mcp_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(mcp_label)

        mcp_info = QLabel(
            "ℹ️ Każdy agent dziedziczy globalne serwery MCP z menu Rozszerzenia. "
            "Tutaj możesz dodać dodatkowe — działające tylko w katalogu tego agenta."
        )
        mcp_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        mcp_info.setWordWrap(True)
        layout.addWidget(mcp_info)

        self.manage_agent_mcp_btn = QPushButton()
        self.manage_agent_mcp_btn.setStyleSheet(self._section_button_style())
        self.manage_agent_mcp_btn.clicked.connect(self._open_agent_mcp)
        layout.addWidget(self.manage_agent_mcp_btn)
        self._update_agent_mcp_button()

        # === Wyłączanie globalnych MCP ===
        disable_mcp_label = QLabel("🚫 Wyłącz globalne MCP dla tego agenta:")
        disable_mcp_label.setStyleSheet("color: #ffffff; margin-top: 6px;")
        layout.addWidget(disable_mcp_label)

        disable_mcp_info = QLabel(
            "ℹ️ Globalne serwery MCP są domyślnie aktywne. Odznacz te, których ten "
            "agent ma nie używać. Zapis dzieje się natychmiast."
        )
        disable_mcp_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        disable_mcp_info.setWordWrap(True)
        layout.addWidget(disable_mcp_info)

        self.global_mcp_count_label = QLabel("")
        self.global_mcp_count_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        layout.addWidget(self.global_mcp_count_label)

        self.global_mcp_list = QListWidget()
        self.global_mcp_list.setMinimumHeight(140)
        self.global_mcp_list.setWordWrap(True)
        self.global_mcp_list.setTextElideMode(Qt.ElideNone)
        self.global_mcp_list.setStyleSheet(self._list_style())
        layout.addWidget(self.global_mcp_list, stretch=1)

        self._refresh_global_mcp_section()

        return widget

    def _browse_directory(self):
        """Browse for working directory."""
        directory = styled_get_existing_directory(
            self, "Wybierz katalog roboczy",
            self.dir_input.text() or str(Path.home())
        )
        if directory:
            self.dir_input.setText(directory)

    def _save(self):
        """Validate and save."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę agenta.")
            return

        directory = self.dir_input.text().strip()
        if not Path(directory).is_dir():
            QMessageBox.warning(self, "Nieprawidłowy katalog", "Podany katalog nie istnieje.")
            return

        self.accept()

    def _save_and_run(self):
        """Validate, save and mark for immediate run."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę agenta.")
            return

        directory = self.dir_input.text().strip()
        if not Path(directory).is_dir():
            QMessageBox.warning(self, "Nieprawidłowy katalog", "Podany katalog nie istnieje.")
            return

        self.run_immediately = True
        self.accept()

    def get_run_immediately(self) -> bool:
        """Return whether agent should be run immediately after save."""
        return self.run_immediately

    def get_data(self) -> dict:
        """Return agent configuration."""
        return {
            'id': self.agent.get('id', str(uuid.uuid4())[:8]),
            'name': self.name_input.text().strip(),
            'working_directory': self.dir_input.text().strip(),
            'memory_files': self.memory_files,
            'auto_start': self.auto_start_checkbox.isChecked(),
            'send_memory_on_start': self.send_memory_checkbox.isChecked(),
            'model': self.model_combo.currentData() or DEFAULT_AGENT_MODEL,
            'splitter_sizes': self.agent.get('splitter_sizes', [600, 150]),  # domyślne proporcje
        }

    # ---------- Per-agent skills (project-local) ----------

    def _agent_local_skills_dir(self) -> Optional[Path]:
        """Return Path to <working_directory>/.claude/skills/ if working_dir is valid."""
        wd = self.dir_input.text().strip()
        if not wd:
            return None
        wd_path = Path(wd)
        if not wd_path.is_dir():
            return None
        return wd_path / ".claude" / "skills"

    def _update_agent_skills_button(self):
        """Refresh label/state of the agent-skills button based on working directory."""
        local_dir = self._agent_local_skills_dir()
        if local_dir is None:
            self.manage_agent_skills_btn.setText(
                "🧩 Zarządzaj lokalnymi skillami (najpierw ustaw poprawny katalog)"
            )
            self.manage_agent_skills_btn.setEnabled(False)
            self.manage_agent_skills_btn.setToolTip(
                "Najpierw ustaw poprawny katalog roboczy."
            )
            return

        # Count installed local skills (silently — directory may not exist yet)
        try:
            count = len(SkillsManager(skills_dir=local_dir).list_skills())
        except Exception:
            count = 0

        if count == 0:
            label = "🧩 Zarządzaj lokalnymi skillami (brak)"
        elif count == 1:
            label = "🧩 Zarządzaj lokalnymi skillami (1 zainstalowany)"
        elif count < 5:
            label = f"🧩 Zarządzaj lokalnymi skillami ({count} zainstalowane)"
        else:
            label = f"🧩 Zarządzaj lokalnymi skillami ({count} zainstalowanych)"

        self.manage_agent_skills_btn.setText(label)
        self.manage_agent_skills_btn.setEnabled(True)
        self.manage_agent_skills_btn.setToolTip(
            f"Skille lokalne dla tego agenta ({local_dir})"
        )

    def _open_agent_skills(self):
        """Open SkillsManagerDialog scoped to <working_directory>/.claude/skills/."""
        local_dir = self._agent_local_skills_dir()
        if local_dir is None:
            QMessageBox.warning(
                self,
                "Brak katalogu",
                "Najpierw ustaw poprawny katalog roboczy."
            )
            return

        agent_name = self.name_input.text().strip() or "Agent"
        dialog = SkillsManagerDialog(self, skills_dir=local_dir, agent_name=agent_name)
        dialog.exec_()

        # Refresh count after the user closed the dialog
        self._update_agent_skills_button()

    # ---------- Wyłączanie globalnych skilli per agent (1B) ----------

    def _on_working_dir_changed(self):
        """Refresh skills (1A/1B) + MCP (1A/1B) sections when the working dir changes."""
        self._update_agent_skills_button()
        self._refresh_global_skills_section()
        self._update_agent_mcp_button()
        self._refresh_global_mcp_section()

    def _agent_skills_settings(self) -> Optional[AgentSkillsSettings]:
        """Return AgentSkillsSettings if working_dir is valid, else None."""
        wd = self.dir_input.text().strip()
        if not wd or not Path(wd).is_dir():
            return None
        return AgentSkillsSettings(Path(wd))

    def _refresh_global_skills_section(self):
        """Rebuild the global-skills list and update count label."""
        # Block signals while rebuilding to avoid spurious itemChanged events.
        self.global_skills_list.blockSignals(True)
        self.global_skills_list.clear()
        self.global_skills_list.blockSignals(False)

        global_skills = SkillsManager().list_skills()
        settings = self._agent_skills_settings()
        disabled_set = set(settings.get_disabled_global_skills()) if settings else set()

        # Update count label
        if settings is None:
            self.global_skills_count_label.setText(
                "⚠ Najpierw ustaw poprawny katalog roboczy."
            )
            self.global_skills_count_label.setStyleSheet(
                "color: #f59e0b; font-size: 11px;"
            )
        elif not global_skills:
            self.global_skills_count_label.setText(
                "Brak zainstalowanych globalnych skilli. "
                "Zainstaluj je w menu Rozszerzenia → Umiejętności."
            )
            self.global_skills_count_label.setStyleSheet(
                "color: #cccccc; font-size: 11px;"
            )
        else:
            disabled_count = sum(1 for s in global_skills if s.name in disabled_set)
            self.global_skills_count_label.setText(
                f"{disabled_count} z {len(global_skills)} globalnych wyłączone dla tego agenta."
            )
            self.global_skills_count_label.setStyleSheet(
                "color: #cccccc; font-size: 11px;"
            )

        # Populate list
        if not global_skills:
            return

        for skill in global_skills:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 75))
            item.setData(Qt.UserRole, skill.name)
            self.global_skills_list.addItem(item)

            row = QWidget()
            row.setAttribute(Qt.WA_TranslucentBackground)
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(8, 6, 8, 6)
            row_h.setSpacing(8)

            cb = QCheckBox()
            cb.setChecked(skill.name not in disabled_set)
            cb.setEnabled(settings is not None)
            cb.setStyleSheet("QCheckBox { background: transparent; }")
            # Default-arg trick to capture name in lambda closure
            cb.toggled.connect(
                lambda checked, name=skill.name: self._toggle_global_skill(name, checked)
            )
            row_h.addWidget(cb)

            text_v = QVBoxLayout()
            text_v.setSpacing(2)
            name_l = QLabel(skill.name)
            name_l.setStyleSheet(
                "color: #ffffff; font-size: 13px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            text_v.addWidget(name_l)

            full_description = skill.description or "(brak opisu)"
            short_description = self._shorten_skill_description(full_description)
            desc_l = QLabel(short_description)
            desc_l.setStyleSheet(
                "color: #aaaaaa; font-size: 11px; background: transparent; border: none;"
            )
            desc_l.setWordWrap(True)
            desc_l.setToolTip(full_description)
            text_v.addWidget(desc_l)
            row_h.addLayout(text_v, stretch=1)

            self.global_skills_list.setItemWidget(item, row)

    @staticmethod
    def _shorten_skill_description(text: str, max_chars: int = 120) -> str:
        """Trim a skill's description for compact display.

        Prefers cutting at the end of the first sentence, falls back to a
        hard char cap. Full text is shown in the tooltip.
        """
        text = text.strip()
        # First-sentence trim
        for sep in (". ", ".\n"):
            idx = text.find(sep)
            if 0 < idx <= max_chars:
                return text[: idx + 1]
        # Hard cap with ellipsis
        if len(text) > max_chars:
            return text[:max_chars].rstrip() + "…"
        return text

    def _toggle_global_skill(self, skill_name: str, checked: bool):
        """Persist a single skill's enabled/disabled state for this agent."""
        settings = self._agent_skills_settings()
        if settings is None:
            return  # working_dir invalid — checkbox should be disabled anyway
        try:
            if checked:
                settings.enable(skill_name)
            else:
                settings.disable(skill_name)
        except Exception as exc:
            QMessageBox.warning(
                self, "Błąd zapisu",
                f"Nie udało się zapisać ustawień: {exc}"
            )
            return

        # Refresh just the count label (avoid full list rebuild — it would
        # detach checkbox widgets and lose the keyboard focus).
        global_skills = SkillsManager().list_skills()
        disabled_count = len(settings.get_disabled_global_skills())
        self.global_skills_count_label.setText(
            f"{disabled_count} z {len(global_skills)} globalnych wyłączone dla tego agenta."
        )

    # ---------- Per-agent MCP servers (project-local) ----------

    def _agent_working_dir_path(self) -> Optional[Path]:
        """Return Path to working_directory if valid, else None."""
        wd = self.dir_input.text().strip()
        if not wd:
            return None
        wd_path = Path(wd)
        return wd_path if wd_path.is_dir() else None

    def _update_agent_mcp_button(self):
        """Refresh label/state of the agent-MCP button based on working directory."""
        wd_path = self._agent_working_dir_path()
        if wd_path is None:
            self.manage_agent_mcp_btn.setText(
                "🔌 Zarządzaj lokalnymi MCP (najpierw ustaw poprawny katalog)"
            )
            self.manage_agent_mcp_btn.setEnabled(False)
            self.manage_agent_mcp_btn.setToolTip(
                "Najpierw ustaw poprawny katalog roboczy."
            )
            return

        # Count local-scope MCP servers for this working_dir (silently)
        try:
            servers = McpManager(working_dir=wd_path).list_servers()
            count = sum(1 for s in servers if s.scope == "local" and not s.managed)
        except Exception:
            count = 0

        if count == 0:
            label = "🔌 Zarządzaj lokalnymi MCP (brak)"
        elif count == 1:
            label = "🔌 Zarządzaj lokalnymi MCP (1 zainstalowany)"
        elif count < 5:
            label = f"🔌 Zarządzaj lokalnymi MCP ({count} zainstalowane)"
        else:
            label = f"🔌 Zarządzaj lokalnymi MCP ({count} zainstalowanych)"

        self.manage_agent_mcp_btn.setText(label)
        self.manage_agent_mcp_btn.setEnabled(True)
        self.manage_agent_mcp_btn.setToolTip(
            f"Serwery MCP lokalne dla tego agenta ({wd_path})"
        )

    def _open_agent_mcp(self):
        """Open McpManagerDialog scoped to this agent's working_dir."""
        wd_path = self._agent_working_dir_path()
        if wd_path is None:
            QMessageBox.warning(self, "Brak katalogu", "Najpierw ustaw poprawny katalog roboczy.")
            return
        agent_name = self.name_input.text().strip() or "Agent"
        dialog = McpManagerDialog(self, working_dir=wd_path, agent_name=agent_name)
        dialog.exec_()
        # Refresh count after the user closed the dialog
        self._update_agent_mcp_button()

    # ---------- Wyłączanie globalnych MCP per agent ----------

    def _agent_mcp_settings(self) -> Optional[AgentMcpSettings]:
        """Return AgentMcpSettings if working_dir is valid, else None."""
        wd_path = self._agent_working_dir_path()
        return AgentMcpSettings(wd_path) if wd_path else None

    def _list_global_mcp_servers(self) -> List[McpServer]:
        """Return MCP servers visible globally (user scope + managed by claude.ai).

        Te serwery są kandydatami do wyłączenia per agent.
        """
        try:
            all_servers = McpManager().list_servers()
        except Exception:
            return []
        return [s for s in all_servers if s.scope in ("user", "managed")]

    def _refresh_global_mcp_section(self):
        """Rebuild the global-MCP list and update count label."""
        self.global_mcp_list.blockSignals(True)
        self.global_mcp_list.clear()
        self.global_mcp_list.blockSignals(False)

        global_mcps = self._list_global_mcp_servers()
        settings = self._agent_mcp_settings()
        # Porównujemy po sanitized name (deny rule używa zsanityzowanej formy)
        disabled_set = set(settings.get_disabled_mcp_sanitized()) if settings else set()

        if settings is None:
            self.global_mcp_count_label.setText("⚠ Najpierw ustaw poprawny katalog roboczy.")
            self.global_mcp_count_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
        elif not global_mcps:
            self.global_mcp_count_label.setText(
                "Brak globalnych serwerów MCP. Dodaj je w menu Rozszerzenia → Serwery MCP."
            )
            self.global_mcp_count_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        else:
            disabled_count = sum(1 for s in global_mcps if s.sanitized_name in disabled_set)
            self.global_mcp_count_label.setText(
                f"{disabled_count} z {len(global_mcps)} globalnych wyłączone dla tego agenta."
            )
            self.global_mcp_count_label.setStyleSheet("color: #cccccc; font-size: 11px;")

        if not global_mcps:
            return

        for srv in global_mcps:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 60))
            item.setData(Qt.UserRole, srv.name)
            self.global_mcp_list.addItem(item)

            row = QWidget()
            row.setAttribute(Qt.WA_TranslucentBackground)
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(8, 6, 8, 6)
            row_h.setSpacing(8)

            cb = QCheckBox()
            cb.setChecked(srv.sanitized_name not in disabled_set)
            cb.setEnabled(settings is not None)
            cb.setStyleSheet("QCheckBox { background: transparent; }")
            cb.toggled.connect(
                lambda checked, name=srv.name: self._toggle_global_mcp(name, checked)
            )
            row_h.addWidget(cb)

            text_v = QVBoxLayout()
            text_v.setSpacing(2)
            scope_label = _MCP_SCOPE_LABEL.get(srv.scope, srv.scope)
            name_l = QLabel(f"{srv.name}  <span style='color:#888;'>[{scope_label}]</span>")
            name_l.setTextFormat(Qt.RichText)
            name_l.setStyleSheet(
                "color: #ffffff; font-size: 13px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            text_v.addWidget(name_l)

            target_text = srv.target if len(srv.target) <= 80 else srv.target[:77] + "..."
            desc_l = QLabel(target_text)
            desc_l.setStyleSheet(
                "color: #aaaaaa; font-size: 11px; background: transparent; border: none;"
            )
            desc_l.setWordWrap(True)
            desc_l.setToolTip(srv.target)
            text_v.addWidget(desc_l)
            row_h.addLayout(text_v, stretch=1)

            self.global_mcp_list.setItemWidget(item, row)

    def _toggle_global_mcp(self, server_name: str, checked: bool):
        """Persist a single MCP server's enabled/disabled state for this agent."""
        settings = self._agent_mcp_settings()
        if settings is None:
            return
        try:
            if checked:
                settings.enable(server_name)
            else:
                settings.disable(server_name)
        except Exception as exc:
            QMessageBox.warning(
                self, "Błąd zapisu",
                f"Nie udało się zapisać ustawień MCP: {exc}"
            )
            return
        # Refresh just the count label (avoid full list rebuild — would lose checkbox focus)
        global_mcps = self._list_global_mcp_servers()
        disabled_count = len(settings.get_disabled_mcp_sanitized())
        self.global_mcp_count_label.setText(
            f"{disabled_count} z {len(global_mcps)} globalnych wyłączone dla tego agenta."
        )

    def _add_memory_file_chip(self, file_path: str):
        """Add a file chip to the memory files list."""
        chip = QFrame()
        chip.setStyleSheet("""
            QFrame {
                background-color: #2d0a1e;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
        """)
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 4, 4, 4)
        chip_layout.setSpacing(8)

        # File icon and name
        file_name = Path(file_path).name
        label = QLabel(f"📄 {file_name}")
        label.setStyleSheet("color: #ffffff; font-size: 12px; border: none;")
        label.setToolTip(file_path)  # Show full path on hover
        chip_layout.addWidget(label, stretch=1)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ef4444;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #ef4444;
                border-radius: 12px;
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_memory_file(file_path, chip))
        chip_layout.addWidget(remove_btn)

        self.memory_files_container.addWidget(chip)

    def _add_memory_file(self):
        """Open file dialog to add memory files."""
        file_filter = "Pliki pamięci (*.md *.txt *.json);;Wszystkie pliki (*)"
        files, _ = styled_get_open_file_names(
            self, "Wybierz pliki pamięci", str(Path.home()), file_filter
        )

        if not files:
            return

        for file_path in files:
            if file_path not in self.memory_files:
                self.memory_files.append(file_path)
                self._add_memory_file_chip(file_path)

    def _remove_memory_file(self, file_path: str, chip: QFrame):
        """Remove a memory file from the list."""
        if file_path in self.memory_files:
            self.memory_files.remove(file_path)
        chip.deleteLater()


class AgentsManagerDialog(QDialog):
    """Dialog for managing all agents."""

    # Async load summaries: (populate_token, row, kind='skills'|'mcp', text, tooltip).
    # populate_token unieważnia wątki z poprzedniej wersji listy (po move/edit/add).
    _summary_ready = pyqtSignal(int, int, str, str, str)

    def __init__(self, parent=None, agents: list = None, memory_projects: list = None):
        super().__init__(parent)
        self.setWindowTitle("Zarządzaj agentami")
        self.setMinimumSize(600, 450)

        self.agents = [a.copy() for a in (agents or [])]
        self.memory_projects = memory_projects or []
        # Lazy loading skille/MCP — synchroniczne wywołania `claude mcp list`
        # blokowały GUI ~2s × liczba agentów. Teraz: placeholdery od razu,
        # właściwe summary przychodzą z wątków przez sygnał.
        self._populate_token = 0
        self._row_labels: Dict[int, Dict[str, QLabel]] = {}
        self._summary_ready.connect(self._on_summary_ready)
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel("Zarządzaj agentami (zakładkami terminala)")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Description
        desc = QLabel("Każdy agent to osobna zakładka z własnym terminalem i przypisanym projektem pamięci.")
        desc.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # List and buttons layout
        list_layout = QHBoxLayout()

        # Agents list
        self.list_widget = QListWidget()
        # Enable word wrap so the per-item second line (file count + model)
        # is rendered. Without this, QListWidget collapses '\n' and elides
        # long names with "...", hiding the second line entirely.
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.ElideNone)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #4a1a3a;
            }
            QListWidget::item:selected {
                background-color: #6a2a5a;
            }
        """)
        self._populate_list()
        list_layout.addWidget(self.list_widget, stretch=1)

        # Buttons on the right
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)

        self.up_btn = QPushButton("▲ W górę")
        self.up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton("▼ W dół")
        self.down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self.down_btn)

        btn_layout.addSpacing(15)

        self.run_btn = QPushButton("▶️ Uruchom")
        self.run_btn.clicked.connect(self._run_agent)
        self.run_btn.setStyleSheet("QPushButton { color: #3b82f6; }")
        btn_layout.addWidget(self.run_btn)

        btn_layout.addSpacing(15)

        self.add_btn = QPushButton("➕ Dodaj")
        self.add_btn.clicked.connect(self._add_agent)
        self.add_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Edytuj")
        self.edit_btn.clicked.connect(self._edit_agent)
        btn_layout.addWidget(self.edit_btn)

        self.duplicate_btn = QPushButton("📋 Duplikuj")
        self.duplicate_btn.clicked.connect(self._duplicate_agent)
        btn_layout.addWidget(self.duplicate_btn)

        self.delete_btn = QPushButton("🗑️ Usuń")
        self.delete_btn.clicked.connect(self._delete_agent)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Zapisz")
        save_btn.clicked.connect(self.accept)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        bottom_layout.addWidget(save_btn)

        layout.addLayout(bottom_layout)

    def _populate_list(self):
        """Populate list with agents.

        Uses setItemWidget with a real QWidget per row so that the second
        line (file count + model) reliably renders for every agent.
        QListWidget's default text rendering does not handle '\n' across
        items consistently — a custom widget bypasses that limitation.

        Skille/MCP są ładowane LAZY — najpierw placeholder "⏳ ładowanie...",
        potem wątek liczy i wraca przez sygnał _summary_ready. populate_token
        unieważnia wątki z poprzedniej wersji listy (np. po Edytuj).
        """
        self._populate_token += 1
        self._row_labels = {}
        self.list_widget.clear()

        for row, agent in enumerate(self.agents):
            # Memory files count (always shown, even when zero)
            memory_files = agent.get('memory_files', [])
            file_count = len(memory_files)
            if file_count == 0:
                memory_info = "Brak plików"
            elif file_count == 1:
                memory_info = "1 plik"
            elif file_count < 5:
                memory_info = f"{file_count} pliki"
            else:
                memory_info = f"{file_count} plików"

            # Model used by this agent
            model_key = agent.get('model', DEFAULT_AGENT_MODEL)
            model_label = CLAUDE_MODELS_SHORT.get(model_key, model_key)

            auto_icon = "🟢" if agent.get('auto_start', True) else "⚪"
            agent_name = agent.get('name', 'Bez nazwy')

            # Empty list item — visual content lives in the attached widget.
            item = QListWidgetItem()
            item.setData(Qt.UserRole, agent)
            item.setSizeHint(QSize(0, 56))
            self.list_widget.addItem(item)

            # Custom widget for this row.
            row_widget = QWidget()
            row_widget.setAttribute(Qt.WA_TranslucentBackground)
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(2)

            name_label = QLabel(f"{auto_icon} {agent_name}")
            name_label.setStyleSheet(
                "color: #ffffff; font-size: 13px; background: transparent; border: none;"
            )
            row_layout.addWidget(name_label)

            # Druga linia: trzy osobne etykiety. Tooltipy tylko tam, gdzie
            # niosą dodatkową informację (📁 pliki, 🧩 skille); część z modelem
            # jest już w pełni widoczna w tekście, więc nie ma tooltipa.
            info_style = (
                "color: #aaaaaa; font-size: 11px; background: transparent; border: none;"
            )

            files_label = QLabel(f"   📁 {memory_info}")
            files_label.setStyleSheet(info_style)
            files_label.setToolTip(self._format_memory_files_tooltip(agent))

            model_mid_label = QLabel(f"  •  🤖 {model_label}  •  ")
            model_mid_label.setStyleSheet(info_style)

            # Placeholder — właściwą zawartość wstawi _on_summary_ready po wątku.
            skills_label = QLabel("🧩 ⏳ ładowanie…")
            skills_label.setStyleSheet(info_style)
            skills_label.setToolTip("Ładuję listę skilli tego agenta...")

            mcp_sep_label = QLabel("  •  ")
            mcp_sep_label.setStyleSheet(info_style)

            mcp_label = QLabel("🔌 ⏳ ładowanie…")
            mcp_label.setStyleSheet(info_style)
            mcp_label.setToolTip("Ładuję listę MCP tego agenta (wymaga uruchomienia 'claude mcp list')...")

            # Zapamiętaj referencje, żeby slot mógł je zaktualizować po przyjściu wyniku z wątku.
            self._row_labels[row] = {"skills": skills_label, "mcp": mcp_label}

            info_row = QHBoxLayout()
            info_row.setContentsMargins(0, 0, 0, 0)
            info_row.setSpacing(0)
            info_row.addWidget(files_label)
            info_row.addWidget(model_mid_label)
            info_row.addWidget(skills_label)
            info_row.addWidget(mcp_sep_label)
            info_row.addWidget(mcp_label)
            info_row.addStretch()
            row_layout.addLayout(info_row)

            self.list_widget.setItemWidget(item, row_widget)

        # Po wstawieniu wszystkich wierszy — odpal ładowanie summary w wątkach.
        # singleShot(0) odroczy to do następnej iteracji event loopa, dzięki czemu
        # dialog zdąży się wyrenderować zanim zaczniemy spawnowanie wątków.
        QTimer.singleShot(0, lambda t=self._populate_token: self._load_summaries_async(t))

    def _load_summaries_async(self, token: int):
        """Spawn jeden wątek per agent — każdy liczy skille + MCP i emituje sygnał."""
        if token != self._populate_token:
            return  # Lista została w międzyczasie przebudowana — nie startuj.
        for row, agent in enumerate(self.agents):
            threading.Thread(
                target=self._compute_summaries,
                args=(token, row, agent),
                daemon=True,
            ).start()

    def _compute_summaries(self, token: int, row: int, agent: dict):
        """Działa W WĄTKU — wywołuje drogie operacje I/O i subprocess.

        WAŻNE: nie wolno tu dotykać widgetów Qt. Wynik wraca tylko przez sygnał.
        """
        # Skille — szybkie (czytanie katalogu), ale dla porządku też w wątku.
        try:
            text, tooltip = self._format_skills_summary(agent)
        except Exception as e:
            text, tooltip = "⚠ błąd skille", f"Nie udało się załadować skilli:\n{e}"
        if token == self._populate_token:
            self._summary_ready.emit(token, row, "skills", text, tooltip)

        # MCP — wolne (claude mcp list ~2s na agenta, czasem timeout 30s).
        try:
            text, tooltip = self._format_mcp_summary(agent)
        except Exception as e:
            text, tooltip = "⚠ błąd MCP", f"Nie udało się załadować MCP:\n{e}"
        if token == self._populate_token:
            self._summary_ready.emit(token, row, "mcp", text, tooltip)

    def _on_summary_ready(self, token: int, row: int, kind: str, text: str, tooltip: str):
        """Slot w GUI thread — aktualizuje konkretną etykietę po przyjściu wyniku z wątku."""
        if token != self._populate_token:
            return  # Stary wynik z poprzedniej wersji listy.
        labels = self._row_labels.get(row)
        if not labels:
            return
        label = labels.get(kind)
        if label is None:
            return
        try:
            label.setText(text)
            label.setToolTip(tooltip)
        except RuntimeError:
            # C++ widget już usunięty (np. zamknięto dialog) — ignoruj.
            pass

    @staticmethod
    def _format_memory_files_tooltip(agent: dict) -> str:
        """List the agent's memory files (filenames only) for a hover tooltip.

        Full paths are not shown — they're long and break tooltip layout.
        The full path is visible inside the agent edit dialog anyway.
        """
        files = agent.get('memory_files') or []
        if not files:
            return "Pliki pamięci tego agenta:\n\n   (brak plików pamięci)"
        lines = ["Pliki pamięci tego agenta:", ""]
        for path in files:
            lines.append(f"   • {Path(path).name}")
        return "\n".join(lines)

    @staticmethod
    def _pl_local(n: int) -> str:
        """Polish plural for 'lokalny': 1 lokalny, 2-4 lokalne, else lokalnych."""
        if n == 1:
            return f"{n} lokalny"
        last_digit = n % 10
        last_two = n % 100
        if 2 <= last_digit <= 4 and not 12 <= last_two <= 14:
            return f"{n} lokalne"
        return f"{n} lokalnych"

    @staticmethod
    def _pl_global_only(n: int) -> str:
        """Polish plural for 'globalny' (no fraction): 1, 2-4, else."""
        if n == 1:
            return f"{n} globalny"
        last_digit = n % 10
        last_two = n % 100
        if 2 <= last_digit <= 4 and not 12 <= last_two <= 14:
            return f"{n} globalne"
        return f"{n} globalnych"

    def _format_skills_summary(self, agent: dict) -> tuple:
        """Compute skills info for one agent's row.

        Returns (display_text, tooltip_text). The display text includes an
        icon + short summary; the tooltip lists every skill name grouped
        into: globalne aktywne, globalne wyłączone, lokalne.
        """
        working_dir = (agent.get('working_directory') or '').strip()

        # Invalid working dir → can't read local skills or disabled list.
        if not working_dir or not Path(working_dir).is_dir():
            return (
                "⚠ skille nieznane",
                "Katalog roboczy agenta jest pusty lub nie istnieje —\n"
                "nie da się odczytać listy skilli."
            )

        wd_path = Path(working_dir)

        # Globalne (z ~/.claude/skills/)
        global_skills = SkillsManager().list_skills()
        global_names = [s.name for s in global_skills]

        # Wyłączone globalne dla tego agenta
        disabled_set = set(AgentSkillsSettings(wd_path).get_disabled_global_skills())
        enabled_global = [n for n in global_names if n not in disabled_set]
        disabled_global = [n for n in global_names if n in disabled_set]

        # Lokalne (z <wd>/.claude/skills/)
        local_skills = SkillsManager(wd_path / ".claude" / "skills").list_skills()
        local_names = [s.name for s in local_skills]

        n_global_total = len(global_names)
        n_global_on = len(enabled_global)
        n_disabled = len(disabled_global)
        n_local = len(local_names)

        # === Tekst wyświetlany ===
        if n_global_total == 0 and n_local == 0:
            display = "🚫 brak skilli"
        elif n_disabled == 0 and n_local == 0:
            display = f"🧩 {self._pl_global_only(n_global_on)}"
        elif n_disabled == 0 and n_local > 0:
            display = (
                f"🧩 {self._pl_global_only(n_global_on)} + "
                f"{self._pl_local(n_local)}"
            )
        elif n_disabled > 0 and n_local == 0:
            display = f"✂️ {n_global_on} z {n_global_total} globalnych"
        else:
            display = (
                f"✂️ {n_global_on} z {n_global_total} globalnych + "
                f"{self._pl_local(n_local)}"
            )

        # === Tooltip — pełna lista nazw ===
        tooltip_parts = ["Skille tego agenta:"]
        if enabled_global:
            tooltip_parts.append(f"\n✓ Globalne aktywne ({len(enabled_global)}):")
            tooltip_parts.extend(f"   • {name}" for name in enabled_global)
        if disabled_global:
            tooltip_parts.append(f"\n✗ Globalne wyłączone ({len(disabled_global)}):")
            tooltip_parts.extend(f"   • {name}" for name in disabled_global)
        if local_names:
            tooltip_parts.append(f"\n+ Lokalne ({len(local_names)}):")
            tooltip_parts.extend(f"   • {name}" for name in local_names)
        if not enabled_global and not disabled_global and not local_names:
            tooltip_parts.append("\n(brak zainstalowanych skilli)")

        return (display, "\n".join(tooltip_parts))

    def _format_mcp_summary(self, agent: dict) -> tuple:
        """Compute MCP info for one agent's row.

        Returns (display_text, tooltip_text). Format identical to
        _format_skills_summary but for MCP servers (icon 🔌).

        Performance: wywołuje claude mcp list per agent (~500ms-1s przez
        health checks). Dla 3-5 agentów to akceptowalne; jeśli kiedyś
        będzie problem — można dodać cache na poziomie _populate_list.
        """
        working_dir = (agent.get('working_directory') or '').strip()

        if not working_dir or not Path(working_dir).is_dir():
            return (
                "⚠ MCP nieznane",
                "Katalog roboczy agenta jest pusty lub nie istnieje —\n"
                "nie da się odczytać listy MCP."
            )

        wd_path = Path(working_dir)

        try:
            servers = McpManager(working_dir=wd_path).list_servers()
        except Exception:
            return (
                "⚠ MCP nieznane",
                "Nie udało się pobrać listy MCP (komenda 'claude' nieaktywna?)."
            )

        # Wyłączone dla tego agenta — porównujemy po sanitized name
        # (deny rule używa zsanityzowanej formy).
        disabled_set = set(AgentMcpSettings(wd_path).get_disabled_mcp_sanitized())

        # Globalne = scope user + managed (claude.ai*)
        global_servers = [s for s in servers if s.scope in ("user", "managed")]
        # Lokalne = scope local (working_dir-specific)
        local_servers = [s for s in servers if s.scope == "local"]

        enabled_global = [s for s in global_servers if s.sanitized_name not in disabled_set]
        disabled_global = [s for s in global_servers if s.sanitized_name in disabled_set]

        n_global_total = len(global_servers)
        n_global_on = len(enabled_global)
        n_disabled = len(disabled_global)
        n_local = len(local_servers)

        # === Tekst wyświetlany ===
        if n_global_total == 0 and n_local == 0:
            display = "🚫 brak MCP"
        elif n_disabled == 0 and n_local == 0:
            display = f"🔌 {self._pl_global_only(n_global_on)}"
        elif n_disabled == 0 and n_local > 0:
            display = (
                f"🔌 {self._pl_global_only(n_global_on)} + "
                f"{self._pl_local(n_local)}"
            )
        elif n_disabled > 0 and n_local == 0:
            display = f"✂️ {n_global_on} z {n_global_total} globalnych MCP"
        else:
            display = (
                f"✂️ {n_global_on} z {n_global_total} globalnych MCP + "
                f"{self._pl_local(n_local)}"
            )

        # === Tooltip — pełna lista nazw ===
        tooltip_parts = ["Serwery MCP tego agenta:"]
        if enabled_global:
            tooltip_parts.append(f"\n✓ Globalne aktywne ({len(enabled_global)}):")
            tooltip_parts.extend(f"   • {s.name}" for s in enabled_global)
        if disabled_global:
            tooltip_parts.append(f"\n✗ Globalne wyłączone ({len(disabled_global)}):")
            tooltip_parts.extend(f"   • {s.name}" for s in disabled_global)
        if local_servers:
            tooltip_parts.append(f"\n+ Lokalne ({len(local_servers)}):")
            tooltip_parts.extend(f"   • {s.name}" for s in local_servers)
        if not enabled_global and not disabled_global and not local_servers:
            tooltip_parts.append("\n(brak zarejestrowanych MCP)")

        return (display, "\n".join(tooltip_parts))

    def _get_selected_index(self) -> int:
        """Get selected item index."""
        row = self.list_widget.currentRow()
        return row if row >= 0 else -1

    def _move_up(self):
        """Move selected agent up."""
        row = self._get_selected_index()
        if row > 0:
            self.agents[row], self.agents[row - 1] = self.agents[row - 1], self.agents[row]
            self._populate_list()
            self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        """Move selected agent down."""
        row = self._get_selected_index()
        if 0 <= row < len(self.agents) - 1:
            self.agents[row], self.agents[row + 1] = self.agents[row + 1], self.agents[row]
            self._populate_list()
            self.list_widget.setCurrentRow(row + 1)

    def _run_agent(self):
        """Run selected agent (open tab immediately)."""
        row = self._get_selected_index()
        if row < 0:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz agenta do uruchomienia.")
            return

        # Mark agent for immediate run and force Claude start
        self.agents[row]['_run_immediately'] = True
        self.agents[row]['_force_start'] = True
        # Close dialog and apply changes
        self.accept()

    def _add_agent(self):
        """Add new agent."""
        dialog = AgentConfigDialog(self, memory_projects=self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            agent_data = dialog.get_data()
            # Mark agent for immediate run if requested
            if dialog.get_run_immediately():
                agent_data['_run_immediately'] = True
            self.agents.append(agent_data)
            self._populate_list()
            self.list_widget.setCurrentRow(len(self.agents) - 1)

    def _edit_agent(self):
        """Edit selected agent."""
        row = self._get_selected_index()
        if row < 0:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz agenta do edycji.")
            return

        agent = self.agents[row]
        dialog = AgentConfigDialog(self, agent=agent, memory_projects=self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            self.agents[row] = dialog.get_data()
            self._populate_list()
            self.list_widget.setCurrentRow(row)

    def _duplicate_agent(self):
        """Duplicate selected agent."""
        row = self._get_selected_index()
        if row < 0:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz agenta do duplikacji.")
            return

        agent = self.agents[row].copy()
        agent['id'] = str(uuid.uuid4())[:8]
        agent['name'] = f"{agent.get('name', 'Agent')} (kopia)"
        self.agents.append(agent)
        self._populate_list()
        self.list_widget.setCurrentRow(len(self.agents) - 1)

    def _delete_agent(self):
        """Delete selected agent."""
        row = self._get_selected_index()
        if row < 0:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz agenta do usunięcia.")
            return

        if len(self.agents) <= 1:
            QMessageBox.warning(self, "Nie można usunąć", "Musi pozostać co najmniej jeden agent.")
            return

        agent = self.agents[row]
        reply = QMessageBox.question(
            self, "Potwierdź usunięcie",
            f"Czy na pewno usunąć agenta \"{agent.get('name')}\"?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.agents[row]
            self._populate_list()

    def get_agents(self) -> list:
        """Return agents list."""
        return self.agents

    def get_agents_to_run(self) -> list:
        """Return list of agents marked for immediate run."""
        return [a for a in self.agents if a.get('_run_immediately', False)]


class SkillsManagerDialog(QDialog):
    """Dialog for managing Claude Code skills.

    By default operates on the global ~/.claude/skills/ directory.
    When `skills_dir` is provided, scopes to that directory (e.g. for
    project-local skills inside <agent_working_dir>/.claude/skills/).
    """

    def __init__(self, parent=None, skills_dir: Optional[Path] = None,
                 agent_name: Optional[str] = None):
        super().__init__(parent)
        self._agent_name = agent_name
        self._is_per_agent = skills_dir is not None

        if self._is_per_agent and agent_name:
            self.setWindowTitle(f"Skille agenta — {agent_name}")
        elif self._is_per_agent:
            self.setWindowTitle("Skille agenta")
        else:
            self.setWindowTitle("Umiejętności (Skills)")

        self.setMinimumSize(700, 500)
        self.skills_manager = SkillsManager(skills_dir=skills_dir)
        self._skills: list = []
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if self._is_per_agent:
            header_text = (
                f"🧩 Skille agenta — {self._agent_name}"
                if self._agent_name
                else "🧩 Skille agenta"
            )
        else:
            header_text = "Umiejętności (Skills)"

        header = QLabel(header_text)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        if self._is_per_agent:
            desc_text = (
                "Skille tutaj są widoczne TYLKO dla tego agenta. "
                "Globalne (dla wszystkich agentów) zarządzasz w menu "
                "Rozszerzenia → Umiejętności (Skills)."
            )
        else:
            desc_text = (
                "Skille rozszerzają możliwości Claude Code o gotowe procedury "
                "(np. analiza PDF, tworzenie dokumentów). Claude sam je aktywuje "
                "gdy ich opis pasuje do treści rozmowy."
            )
        desc = QLabel(desc_text)
        desc.setStyleSheet("color: #cccccc; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        path_label = QLabel(f"📂 Lokalizacja: {self.skills_manager.skills_dir}")
        path_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        layout.addWidget(path_label)

        list_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.ElideNone)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #4a1a3a;
            }
            QListWidget::item:selected {
                background-color: #6a2a5a;
            }
        """)
        list_layout.addWidget(self.list_widget, stretch=1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)

        self.add_zip_btn = QPushButton("📦 Dodaj z ZIP")
        self.add_zip_btn.clicked.connect(self._add_from_zip)
        self.add_zip_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_zip_btn)

        self.add_folder_btn = QPushButton("📂 Dodaj z folderu")
        self.add_folder_btn.clicked.connect(self._add_from_folder)
        self.add_folder_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_folder_btn)

        btn_layout.addSpacing(15)

        self.open_folder_btn = QPushButton("📁 Pokaż folder")
        self.open_folder_btn.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.open_folder_btn)

        self.refresh_btn = QPushButton("🔄 Odśwież")
        self.refresh_btn.clicked.connect(self._populate_list)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addSpacing(15)

        self.delete_btn = QPushButton("🗑️ Usuń")
        self.delete_btn.clicked.connect(self._delete_skill)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _populate_list(self):
        self.list_widget.clear()
        self._skills = self.skills_manager.list_skills()

        if not self._skills:
            placeholder = QListWidgetItem()
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setSizeHint(QSize(0, 70))
            self.list_widget.addItem(placeholder)

            placeholder_widget = QWidget()
            placeholder_widget.setAttribute(Qt.WA_TranslucentBackground)
            placeholder_layout = QVBoxLayout(placeholder_widget)
            placeholder_layout.setContentsMargins(16, 8, 16, 8)
            placeholder_layout.setSpacing(4)
            empty_label = QLabel(
                "Brak zainstalowanych skilli.\n"
                "Użyj „Dodaj z ZIP\" lub „Dodaj z folderu\" żeby zainstalować pierwszy."
            )
            empty_label.setStyleSheet(
                "color: #cccccc; font-size: 14px; background: transparent;"
            )
            empty_label.setWordWrap(True)
            empty_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            placeholder_layout.addWidget(empty_label)
            self.list_widget.setItemWidget(placeholder, placeholder_widget)
            return

        for skill in self._skills:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, skill)
            item.setSizeHint(QSize(0, 64))
            self.list_widget.addItem(item)

            row_widget = QWidget()
            row_widget.setAttribute(Qt.WA_TranslucentBackground)
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(2)

            icon = "🧩" if skill.has_metadata else "⚠️"
            name_label = QLabel(f"{icon} {skill.name}")
            name_label.setStyleSheet(
                "color: #ffffff; font-size: 13px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            row_layout.addWidget(name_label)

            description = skill.description or "(brak opisu)"
            desc_label = QLabel(f"   {description}")
            desc_label.setStyleSheet(
                "color: #aaaaaa; font-size: 11px; background: transparent; border: none;"
            )
            desc_label.setWordWrap(True)
            row_layout.addWidget(desc_label)

            self.list_widget.setItemWidget(item, row_widget)

    def _selected_skill(self) -> Optional[Skill]:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return data if isinstance(data, Skill) else None

    def _add_from_zip(self):
        file_filter = "Plik ZIP (*.zip);;Wszystkie pliki (*)"
        zip_path, _ = styled_get_open_file_name(
            self, "Wybierz plik ZIP ze skillem", str(Path.home()), file_filter
        )
        if not zip_path:
            return

        self._install_with_overwrite_prompt(
            install_fn=lambda overwrite: self.skills_manager.install_from_zip(
                Path(zip_path), overwrite=overwrite
            ),
        )

    def _add_from_folder(self):
        folder = styled_get_existing_directory(
            self, "Wybierz folder ze skillem", str(Path.home())
        )
        if not folder:
            return

        self._install_with_overwrite_prompt(
            install_fn=lambda overwrite: self.skills_manager.install_from_folder(
                Path(folder), overwrite=overwrite
            ),
        )

    def _install_with_overwrite_prompt(self, install_fn):
        try:
            skill = install_fn(False)
        except SkillInstallError as exc:
            msg = str(exc)
            if "już istnieje" in msg:
                reply = QMessageBox.question(
                    self,
                    "Skill już istnieje",
                    f"{msg}\n\nNadpisać istniejącego skilla?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
                try:
                    skill = install_fn(True)
                except SkillInstallError as exc2:
                    QMessageBox.warning(self, "Błąd instalacji", str(exc2))
                    return
            else:
                QMessageBox.warning(self, "Błąd instalacji", msg)
                return
        except Exception as exc:
            QMessageBox.warning(self, "Błąd instalacji", f"Nieoczekiwany błąd: {exc}")
            return

        QMessageBox.information(
            self, "Zainstalowano", f"Skill „{skill.name}\" został zainstalowany."
        )
        self._populate_list()

    def _open_folder(self):
        skill = self._selected_skill()
        target = skill.folder_path if skill else self.skills_manager.skills_dir

        if not target.exists():
            self.skills_manager.ensure_dir()

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _delete_skill(self):
        skill = self._selected_skill()
        if skill is None:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz skill do usunięcia.")
            return

        reply = QMessageBox.question(
            self,
            "Potwierdź usunięcie",
            f"Czy na pewno usunąć skill „{skill.name}\"?\n"
            f"Folder zostanie nieodwracalnie usunięty:\n{skill.folder_path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            removed = self.skills_manager.remove(skill.folder_name)
        except SkillInstallError as exc:
            QMessageBox.warning(self, "Błąd usuwania", str(exc))
            return

        if removed:
            QMessageBox.information(self, "Usunięto", f"Skill „{skill.name}\" został usunięty.")
        else:
            QMessageBox.warning(self, "Nie znaleziono", "Folder skilla już nie istniał.")
        self._populate_list()


# ============================================================================
# MCP Manager — zarządzanie serwerami Model Context Protocol
# ============================================================================

# Mapowanie statusu na ikonę + kolor (do listy)
_MCP_STATUS_BADGES = {
    STATUS_CONNECTED: ("✅", "#22c55e", "Aktywny"),
    STATUS_NEEDS_AUTH: ("🔐", "#eab308", "Wymaga autoryzacji"),
    STATUS_FAILED: ("❌", "#ef4444", "Błąd połączenia"),
    STATUS_UNKNOWN: ("❓", "#94a3b8", "Status nieznany"),
}

_MCP_SCOPE_LABEL = {
    "user": "globalny",
    "local": "lokalny (agenta)",
    "managed": "zarządzany (claude.ai)",
}


class McpManagerDialog(QDialog):
    """Dialog zarządzania serwerami MCP.

    Tryby:
      - globalny (working_dir=None): pokazuje wszystkie serwery, dodawanie
        domyślnie w scope=user.
      - per-agent (working_dir=Path): pokazuje serwery dotyczące tego agenta
        (user + managed + local-tego-katalogu), dodawanie zawsze w scope=local.
    """

    def __init__(self, parent=None, working_dir: Optional[Path] = None,
                 agent_name: Optional[str] = None):
        super().__init__(parent)
        self._working_dir = Path(working_dir) if working_dir else None
        self._agent_name = agent_name
        self._is_per_agent = working_dir is not None

        if self._is_per_agent and agent_name:
            self.setWindowTitle(f"Serwery MCP agenta — {agent_name}")
        elif self._is_per_agent:
            self.setWindowTitle("Serwery MCP agenta")
        else:
            self.setWindowTitle("Serwery MCP")

        self.setMinimumSize(780, 560)
        self.manager = McpManager(working_dir=self._working_dir)
        self._servers: List[McpServer] = []
        self._setup_ui()
        self._populate_list()

    # ---------- UI ----------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        if self._is_per_agent:
            header_text = (
                f"🔌 Serwery MCP agenta — {self._agent_name}"
                if self._agent_name else "🔌 Serwery MCP agenta"
            )
            desc_text = (
                "Serwery dodane tutaj działają TYLKO w katalogu tego agenta. "
                "Globalne serwery (dla wszystkich agentów) zarządzasz w menu "
                "Rozszerzenia → Serwery MCP."
            )
        else:
            header_text = "🔌 Serwery MCP (Model Context Protocol)"
            desc_text = (
                "Serwery MCP to „wtyczki z narzędziami\" dla Claude Code — "
                "pozwalają agentowi czytać Twój dysk, kalendarz, bazy danych, "
                "wysyłać wiadomości itp. Claude sam decyduje, kiedy ich użyć."
            )

        header = QLabel(header_text)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        desc = QLabel(desc_text)
        desc.setStyleSheet("color: #cccccc; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Lista + panel przycisków
        list_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.ElideNone)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #4a1a3a;
            }
            QListWidget::item:selected {
                background-color: #6a2a5a;
            }
        """)
        list_layout.addWidget(self.list_widget, stretch=1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)

        self.add_template_btn = QPushButton("📚 Dodaj z szablonu...")
        self.add_template_btn.clicked.connect(self._add_from_template)
        self.add_template_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_template_btn)

        self.add_manual_btn = QPushButton("✏️ Dodaj ręcznie...")
        self.add_manual_btn.clicked.connect(self._add_manual)
        self.add_manual_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_manual_btn)

        self.add_json_btn = QPushButton("📋 Dodaj z JSON...")
        self.add_json_btn.clicked.connect(self._add_from_json)
        self.add_json_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_json_btn)

        btn_layout.addSpacing(15)

        # Akcje na zaznaczonym serwerze
        self.authorize_btn = QPushButton("🔓 Autoryzuj")
        self.authorize_btn.clicked.connect(self._authorize_selected)
        self.authorize_btn.setStyleSheet("QPushButton { color: #eab308; }")
        self.authorize_btn.setToolTip("Dla serwerów wymagających autoryzacji (claude.ai, OAuth)")
        btn_layout.addWidget(self.authorize_btn)

        self.test_btn = QPushButton("🔍 Test")
        self.test_btn.clicked.connect(self._test_selected)
        self.test_btn.setToolTip("Sprawdź czy zaznaczony serwer odpowiada")
        btn_layout.addWidget(self.test_btn)

        self.edit_btn = QPushButton("✏️ Edytuj")
        self.edit_btn.clicked.connect(self._edit_selected)
        self.edit_btn.setToolTip("Edytuj zaznaczony serwer (nie działa dla zarządzanych przez claude.ai)")
        btn_layout.addWidget(self.edit_btn)

        btn_layout.addSpacing(15)

        self.refresh_btn = QPushButton("🔄 Odśwież")
        self.refresh_btn.clicked.connect(self._populate_list)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addSpacing(15)

        self.delete_btn = QPushButton("🗑️ Usuń")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        # Stopka
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        close_btn = QPushButton("Zamknij")
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)
        layout.addLayout(bottom_layout)

    # ---------- Lista ----------

    def _populate_list(self):
        self.list_widget.clear()
        try:
            all_servers = self.manager.list_servers()
        except McpError as exc:
            QMessageBox.warning(self, "Błąd", f"Nie udało się pobrać listy MCP:\n{exc}")
            all_servers = []

        # Filtr per-agent: pokazuj user + managed + local (z tego working_dir)
        # W praktyce `claude mcp list` uruchomione z cwd=working_dir zwraca
        # tylko local-tego-katalogu, więc nic nie obetnie wieleagenta.
        self._servers = all_servers

        if not self._servers:
            placeholder = QListWidgetItem()
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setSizeHint(QSize(0, 70))
            self.list_widget.addItem(placeholder)

            placeholder_widget = QWidget()
            placeholder_widget.setAttribute(Qt.WA_TranslucentBackground)
            pl_layout = QVBoxLayout(placeholder_widget)
            pl_layout.setContentsMargins(16, 8, 16, 8)
            empty_label = QLabel(
                "Brak serwerów MCP.\n"
                "Użyj „Dodaj z szablonu\" żeby zainstalować pierwszy."
            )
            empty_label.setStyleSheet(
                "color: #cccccc; font-size: 14px; background: transparent;"
            )
            empty_label.setWordWrap(True)
            pl_layout.addWidget(empty_label)
            self.list_widget.setItemWidget(placeholder, placeholder_widget)
            return

        for srv in self._servers:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, srv)
            item.setSizeHint(QSize(0, 76))
            self.list_widget.addItem(item)

            row_widget = QWidget()
            row_widget.setAttribute(Qt.WA_TranslucentBackground)
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(2)

            icon, color, status_label = _MCP_STATUS_BADGES.get(
                srv.status, _MCP_STATUS_BADGES[STATUS_UNKNOWN]
            )
            scope_label = _MCP_SCOPE_LABEL.get(srv.scope, srv.scope)

            name_html = (
                f"{icon} <b>{srv.name}</b> "
                f"<span style='color: #aaaaaa; font-weight: normal;'>"
                f"[{srv.transport} · {scope_label}]</span>"
            )
            name_label = QLabel(name_html)
            name_label.setStyleSheet(
                "color: #ffffff; font-size: 13px; background: transparent; border: none;"
            )
            name_label.setTextFormat(Qt.RichText)
            row_layout.addWidget(name_label)

            target_text = srv.target if len(srv.target) <= 90 else srv.target[:87] + "..."
            detail_label = QLabel(
                f"<span style='color: {color};'>{status_label}</span> "
                f"<span style='color: #888888;'>· {target_text}</span>"
            )
            detail_label.setStyleSheet(
                "font-size: 11px; background: transparent; border: none;"
            )
            detail_label.setTextFormat(Qt.RichText)
            detail_label.setWordWrap(True)
            row_layout.addWidget(detail_label)

            self.list_widget.setItemWidget(item, row_widget)

    def _selected_server(self) -> Optional[McpServer]:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return data if isinstance(data, McpServer) else None

    # ---------- Akcje: dodawanie ----------

    def _default_scope(self) -> str:
        return "local" if self._is_per_agent else "user"

    def _add_from_template(self):
        picker = _McpTemplatePickerDialog(self)
        if picker.exec_() != QDialog.Accepted or picker.selected_template is None:
            return
        config_dlg = _McpTemplateConfigDialog(
            self,
            template=picker.selected_template,
            default_scope=self._default_scope(),
            scope_locked=self._is_per_agent,
        )
        if config_dlg.exec_() != QDialog.Accepted:
            return
        try:
            config_dlg.install_into(self.manager)
        except McpError as exc:
            QMessageBox.warning(self, "Błąd dodawania", str(exc))
            return
        QMessageBox.information(
            self, "Dodano",
            f"Serwer „{config_dlg.final_name}\" został dodany.\n\n"
            f"{picker.selected_template.install_hint}".strip()
        )
        self._populate_list()

    def _add_manual(self):
        dlg = _McpAddManualDialog(
            self,
            default_scope=self._default_scope(),
            scope_locked=self._is_per_agent,
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            dlg.install_into(self.manager)
        except McpError as exc:
            QMessageBox.warning(self, "Błąd dodawania", str(exc))
            return
        QMessageBox.information(self, "Dodano", f"Serwer „{dlg.final_name}\" został dodany.")
        self._populate_list()

    def _add_from_json(self):
        dlg = _McpJsonImportDialog(
            self,
            default_scope=self._default_scope(),
            scope_locked=self._is_per_agent,
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            self.manager.add_from_json(dlg.final_name, dlg.json_text, scope=dlg.final_scope)
        except McpError as exc:
            QMessageBox.warning(self, "Błąd dodawania", str(exc))
            return
        QMessageBox.information(self, "Dodano", f"Serwer „{dlg.final_name}\" został dodany.")
        self._populate_list()

    # ---------- Akcje: autoryzacja ----------

    def _authorize_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz serwer do autoryzacji.")
            return

        if srv.managed:
            # claude.ai* — autoryzacja przez panel claude.ai
            QDesktopServices.openUrl(QUrl("https://claude.ai/settings/connectors"))
            QMessageBox.information(
                self, "Otwarto przeglądarkę",
                f"Otworzyłem panel integracji claude.ai. Tam zaloguj się i autoryzuj "
                f"serwer „{srv.name}\". Po zakończeniu wróć tutaj i kliknij „🔄 Odśwież\"."
            )
            return

        # Serwery OAuth (Notion, Sentry, GitHub OAuth) — autoryzacja w terminalu Claude Code
        target_dir = self._working_dir or Path.home()
        QMessageBox.information(
            self, "Autoryzacja OAuth",
            f"Aby autoryzować serwer „{srv.name}\":\n\n"
            f"1. Otwórz Claude Code w katalogu:\n   {target_dir}\n\n"
            f"2. Poproś go o jakiekolwiek użycie tego serwera "
            f"(np. „pokaż mi listę narzędzi z {srv.name}\").\n\n"
            f"3. Claude Code otworzy przeglądarkę i poprowadzi przez OAuth.\n\n"
            f"4. Wróć tutaj i kliknij „🔄 Odśwież\"."
        )

    # ---------- Akcje: test połączenia ----------

    def _test_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz serwer do przetestowania.")
            return

        # Cursor zajęty + ponowne pobranie statusu z `claude mcp list`
        from PyQt5.QtCore import Qt as _Qt
        from PyQt5.QtGui import QCursor as _QCursor
        self.setCursor(_QCursor(_Qt.WaitCursor))
        try:
            import time as _time
            t0 = _time.monotonic()
            updated = self.manager.test_connection(srv.name)
            elapsed_ms = int((_time.monotonic() - t0) * 1000)
        except McpError as exc:
            self.unsetCursor()
            QMessageBox.warning(self, "Błąd testu", str(exc))
            return
        finally:
            self.unsetCursor()

        if updated is None:
            QMessageBox.warning(
                self, "Nie znaleziono",
                f"Serwer „{srv.name}\" nie istnieje już w konfiguracji."
            )
            self._populate_list()
            return

        icon, color, status_label = _MCP_STATUS_BADGES.get(
            updated.status, _MCP_STATUS_BADGES[STATUS_UNKNOWN]
        )
        QMessageBox.information(
            self, "Wynik testu",
            f"{icon} Serwer „{updated.name}\"\n\n"
            f"Status: {status_label}\n"
            f"Czas sprawdzenia: {elapsed_ms} ms\n"
            f"Surowy status: {updated.status_text or '(brak)'}"
        )
        self._populate_list()

    # ---------- Akcje: edycja ----------

    def _edit_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz serwer do edycji.")
            return
        if srv.managed:
            QMessageBox.information(
                self, "Serwer zarządzany",
                f"Serwer „{srv.name}\" jest zarządzany przez claude.ai i nie można go "
                "edytować z poziomu tej aplikacji."
            )
            return

        dlg = _McpAddManualDialog(
            self,
            default_scope=srv.scope if srv.scope in ("user", "local") else self._default_scope(),
            scope_locked=self._is_per_agent,
            edit_server=srv,  # tryb edycji — dialog prefilluje pola
        )
        if dlg.exec_() != QDialog.Accepted:
            return

        # Atomowy update: remove starego + add nowego z rollbackiem
        try:
            self.manager.update_server(
                old_name=srv.name,
                old_scope=srv.scope,
                add_callable=lambda: dlg.install_into(self.manager),
                old_server=srv,
            )
        except McpError as exc:
            QMessageBox.warning(self, "Błąd edycji", str(exc))
            return

        QMessageBox.information(
            self, "Zapisano",
            f"Serwer „{dlg.final_name}\" został zaktualizowany."
        )
        self._populate_list()

    # ---------- Akcje: usuwanie ----------

    def _delete_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz serwer do usunięcia.")
            return

        if srv.managed:
            QMessageBox.information(
                self, "Serwer zarządzany",
                f"Serwer „{srv.name}\" jest zarządzany przez claude.ai i nie można go "
                "usunąć z poziomu tej aplikacji. Aby go odłączyć, zaloguj się na "
                "claude.ai i odepnij integrację w ustawieniach."
            )
            return

        reply = QMessageBox.question(
            self, "Potwierdź usunięcie",
            f"Czy na pewno usunąć serwer MCP „{srv.name}\" "
            f"(scope: {_MCP_SCOPE_LABEL.get(srv.scope, srv.scope)})?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            scope = srv.scope if srv.scope in ("user", "local") else None
            self.manager.remove(srv.name, scope=scope)
        except McpError as exc:
            QMessageBox.warning(self, "Błąd usuwania", str(exc))
            return

        QMessageBox.information(self, "Usunięto", f"Serwer „{srv.name}\" został usunięty.")
        self._populate_list()


class _McpTemplatePickerDialog(QDialog):
    """Wybór jednego z wbudowanych szablonów MCP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wybierz szablon MCP")
        self.setMinimumSize(640, 460)
        self.selected_template: Optional[McpTemplate] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel("📚 Wybierz szablon serwera MCP")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        desc = QLabel(
            "Każdy szablon to gotowy serwer MCP — kliknij i podaj wymagane dane "
            "(np. token, ścieżkę). Szczegóły konfiguracji w następnym kroku."
        )
        desc.setStyleSheet("color: #cccccc; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.ElideNone)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #4a1a3a;
            }
            QListWidget::item:selected {
                background-color: #6a2a5a;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._accept())
        layout.addWidget(self.list_widget, stretch=1)

        for tpl in MCP_TEMPLATES:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, tpl)
            item.setSizeHint(QSize(0, 70))
            self.list_widget.addItem(item)

            row = QWidget()
            row.setAttribute(Qt.WA_TranslucentBackground)
            v = QVBoxLayout(row)
            v.setContentsMargins(4, 4, 4, 4)
            v.setSpacing(2)

            title = QLabel(f"{tpl.title} <span style='color:#aaaaaa;'>[{tpl.transport}]</span>")
            title.setTextFormat(Qt.RichText)
            title.setStyleSheet(
                "color: #ffffff; font-size: 13px; font-weight: bold; "
                "background: transparent; border: none;"
            )
            v.addWidget(title)
            d = QLabel(tpl.description)
            d.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent; border: none;")
            d.setWordWrap(True)
            v.addWidget(d)
            self.list_widget.setItemWidget(item, row)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        next_btn = QPushButton("Dalej →")
        next_btn.setDefault(True)
        next_btn.clicked.connect(self._accept)
        bottom.addWidget(next_btn)
        layout.addLayout(bottom)

    def _accept(self):
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.warning(self, "Brak wyboru", "Wybierz szablon z listy.")
            return
        self.selected_template = item.data(Qt.UserRole)
        self.accept()


class _McpTemplateConfigDialog(QDialog):
    """Dynamicznie generowany formularz na podstawie szablonu MCP."""

    def __init__(self, parent, template: McpTemplate, default_scope: str, scope_locked: bool):
        super().__init__(parent)
        self.setWindowTitle(f"Konfiguracja: {template.title}")
        self.setMinimumWidth(560)
        self.template = template
        self._scope_locked = scope_locked
        self._default_scope = default_scope
        self.final_name: str = template.default_name
        self.final_scope: str = default_scope
        self._inputs: Dict[str, QLineEdit] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(f"⚙️ {self.template.title}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        desc = QLabel(self.template.description)
        desc.setStyleSheet("color: #cccccc; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        if self.template.install_hint:
            hint = QLabel(f"💡 {self.template.install_hint}")
            hint.setStyleSheet("color: #eab308; font-size: 11px;")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(8)

        # Nazwa serwera
        name_input = QLineEdit(self.template.default_name)
        self._inputs["__name__"] = name_input
        form.addRow("Nazwa serwera:", name_input)

        # args_required (placeholdery)
        for key, label in self.template.args_required:
            inp = QLineEdit()
            inp.setPlaceholderText(label)
            self._inputs[f"arg::{key}"] = inp
            form.addRow(f"{label}:", inp)

        # env_required
        for key, label in self.template.env_required:
            inp = QLineEdit()
            inp.setPlaceholderText(label)
            if "token" in key.lower() or "key" in key.lower() or "secret" in key.lower():
                inp.setEchoMode(QLineEdit.Password)
            self._inputs[f"env::{key}"] = inp
            form.addRow(f"{key}:", inp)

        # env_optional
        for key, label in self.template.env_optional:
            inp = QLineEdit()
            inp.setPlaceholderText(f"(opcjonalne) {label}")
            self._inputs[f"envopt::{key}"] = inp
            form.addRow(f"{key} (opc.):", inp)

        # headers_required
        for key, label in self.template.headers_required:
            # Etykieta to wzorzec — wartość podstawiamy do {VAR}
            # Na razie pole jest dla wartości tokenu (obsługa GitHub: TOKEN)
            # Pomijamy bo i tak idzie przez env_required (TOKEN dla GitHub)
            pass

        # Scope
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Globalny (dla wszystkich agentów)", "user")
        self.scope_combo.addItem("Lokalny (tylko ten agent)", "local")
        idx = 0 if self._default_scope == "user" else 1
        self.scope_combo.setCurrentIndex(idx)
        self.scope_combo.setEnabled(not self._scope_locked)
        form.addRow("Zakres:", self.scope_combo)

        layout.addLayout(form)

        if self.template.homepage:
            home = QLabel(f"<a href='{self.template.homepage}' style='color:#7dd3fc;'>📖 Dokumentacja serwera</a>")
            home.setTextFormat(Qt.RichText)
            home.setOpenExternalLinks(True)
            layout.addWidget(home)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel = QPushButton("Anuluj")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        install = QPushButton("✅ Zainstaluj")
        install.setDefault(True)
        install.setStyleSheet("QPushButton { color: #22c55e; }")
        install.clicked.connect(self._validate_and_accept)
        bottom.addWidget(install)
        layout.addLayout(bottom)

    def _validate_and_accept(self):
        name = self._inputs["__name__"].text().strip()
        if not name:
            QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę serwera.")
            return
        # Walidacja wymaganych pól
        for key, label in self.template.args_required:
            if not self._inputs[f"arg::{key}"].text().strip():
                QMessageBox.warning(self, "Brak danych", f"Pole „{label}\" jest wymagane.")
                return
        for key, label in self.template.env_required:
            if not self._inputs[f"env::{key}"].text().strip():
                QMessageBox.warning(self, "Brak danych", f"Pole „{key}\" jest wymagane.")
                return
        self.final_name = name
        self.final_scope = self.scope_combo.currentData()
        self.accept()

    def install_into(self, manager: McpManager) -> None:
        """Wykonuje instalację — wywołuje odpowiednią metodę McpManager."""
        tpl = self.template
        # Zbierz wartości
        arg_values = {k: self._inputs[f"arg::{k}"].text().strip() for k, _ in tpl.args_required}
        env_values: Dict[str, str] = {}
        for k, _ in tpl.env_required:
            v = self._inputs[f"env::{k}"].text().strip()
            if v:
                env_values[k] = v
        for k, _ in tpl.env_optional:
            v = self._inputs[f"envopt::{k}"].text().strip()
            if v:
                env_values[k] = v

        if tpl.transport == "stdio":
            args = tpl.render_args(arg_values)
            manager.add_stdio(
                self.final_name,
                command=tpl.command,
                args=args,
                env=env_values or None,
                scope=self.final_scope,
            )
        elif tpl.transport in ("http", "sse"):
            # URL może mieć placeholdery z arg_values lub env_values (np. {N8N_MCP_URL})
            url_values = {**arg_values, **env_values}
            url = tpl.render_url(url_values)
            # Headers — render z env_values. Jeśli pattern zawiera placeholder bez wartości
            # (np. opcjonalny BEARER_TOKEN nie podany) — pomijamy header.
            import re as _re
            headers: Dict[str, str] = {}
            for hkey, hpattern in tpl.headers_required:
                placeholders = _re.findall(r"\{([A-Z_][A-Z0-9_]*)\}", hpattern)
                missing = [p for p in placeholders if not env_values.get(p)]
                if missing:
                    continue  # opcjonalny env nie podany — header pomijamy
                rendered = hpattern
                for k, v in env_values.items():
                    rendered = rendered.replace("{" + k + "}", v)
                headers[hkey] = rendered
            if tpl.transport == "http":
                manager.add_http(self.final_name, url=url, headers=headers or None, scope=self.final_scope)
            else:
                manager.add_sse(self.final_name, url=url, headers=headers or None, scope=self.final_scope)
        else:
            raise McpError(f"Nieznany transport szablonu: {tpl.transport}")


class _McpAddManualDialog(QDialog):
    """Ręczne dodawanie/edycja serwera MCP — formularz dla zaawansowanych.

    Jeśli `edit_server` jest podane → tryb edycji: formularz prefillowany,
    nazwa zablokowana (zmiana nazwy = remove+add z nową nazwą — niepotrzebny
    dla MVP), pola wypełnione.
    """

    def __init__(self, parent, default_scope: str, scope_locked: bool,
                 edit_server: Optional[McpServer] = None):
        super().__init__(parent)
        self._edit_server = edit_server
        self._is_edit = edit_server is not None
        title = f"Edytuj serwer MCP — {edit_server.name}" if self._is_edit else "Dodaj serwer MCP ręcznie"
        self.setWindowTitle(title)
        self.setMinimumWidth(580)
        self._scope_locked = scope_locked
        self._default_scope = default_scope
        self.final_name: str = edit_server.name if self._is_edit else ""
        self.final_scope: str = (
            edit_server.scope if self._is_edit and edit_server.scope in ("user", "local")
            else default_scope
        )
        self._setup_ui()
        if self._is_edit:
            self._prefill_from_server(edit_server)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header_text = "✏️ Edytuj serwer MCP" if self._is_edit else "✏️ Dodaj serwer MCP ręcznie"
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        if self._is_edit:
            note = QLabel(
                "ℹ️ Zmiany zostaną zapisane jako: usunięcie starego wpisu + dodanie "
                "z nowymi danymi. W razie błędu — automatyczny powrót do poprzedniej konfiguracji."
            )
            note.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            note.setWordWrap(True)
            layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("np. moje-narzedzie")
        form.addRow("Nazwa:", self.name_input)

        self.transport_combo = QComboBox()
        self.transport_combo.addItem("stdio (komenda lokalna)", "stdio")
        self.transport_combo.addItem("http (serwer HTTP)", "http")
        self.transport_combo.addItem("sse (Server-Sent Events)", "sse")
        self.transport_combo.currentIndexChanged.connect(self._on_transport_change)
        form.addRow("Transport:", self.transport_combo)

        # stdio: command + args
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("npx")
        form.addRow("Komenda:", self.command_input)

        self.args_input = QLineEdit()
        self.args_input.setPlaceholderText("-y @scope/package arg1 arg2  (oddziel spacjami)")
        form.addRow("Argumenty:", self.args_input)

        # http/sse: url
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/mcp")
        form.addRow("URL:", self.url_input)

        # env (multi-line: KEY=value)
        self.env_input = QPlainTextEdit()
        self.env_input.setPlaceholderText("KEY1=value1\nKEY2=value2")
        self.env_input.setMaximumHeight(70)
        self.env_input.setStyleSheet(
            "QPlainTextEdit { background-color: #4a1a3a; color: #ffffff; "
            "border: 1px solid #6a2a5a; border-radius: 4px; padding: 4px; }"
        )
        form.addRow("ENV (po linii):", self.env_input)

        # headers (multi-line: Key: value)
        self.headers_input = QPlainTextEdit()
        self.headers_input.setPlaceholderText("Authorization: Bearer xxx\nX-Api-Key: yyy")
        self.headers_input.setMaximumHeight(70)
        self.headers_input.setStyleSheet(self.env_input.styleSheet())
        form.addRow("Nagłówki (po linii):", self.headers_input)

        # scope
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Globalny (dla wszystkich agentów)", "user")
        self.scope_combo.addItem("Lokalny (tylko ten agent)", "local")
        self.scope_combo.setCurrentIndex(0 if self._default_scope == "user" else 1)
        self.scope_combo.setEnabled(not self._scope_locked)
        form.addRow("Zakres:", self.scope_combo)

        layout.addLayout(form)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel = QPushButton("Anuluj")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        ok_label = "💾 Zapisz" if self._is_edit else "✅ Dodaj"
        ok = QPushButton(ok_label)
        ok.setDefault(True)
        ok.setStyleSheet("QPushButton { color: #22c55e; }")
        ok.clicked.connect(self._validate_and_accept)
        bottom.addWidget(ok)
        layout.addLayout(bottom)

        self._on_transport_change()

    def _prefill_from_server(self, srv: McpServer) -> None:
        """Wypełnia formularz danymi istniejącego serwera (tryb edycji)."""
        self.name_input.setText(srv.name)
        # W edycji blokujemy zmianę nazwy — to upraszcza rollback
        self.name_input.setReadOnly(True)
        self.name_input.setStyleSheet("QLineEdit { color: #aaaaaa; }")
        self.name_input.setToolTip("W trybie edycji nazwa jest niezmienna.")

        # Transport
        transport_idx = {"stdio": 0, "http": 1, "sse": 2}.get(srv.transport, 0)
        self.transport_combo.setCurrentIndex(transport_idx)

        if srv.transport == "stdio":
            self.command_input.setText(srv.command)
            self.args_input.setText(" ".join(srv.args))
            if srv.env:
                env_text = "\n".join(f"{k}={v}" for k, v in srv.env.items())
                self.env_input.setPlainText(env_text)
        else:
            self.url_input.setText(srv.target)
            if srv.headers:
                hdr_text = "\n".join(f"{k}: {v}" for k, v in srv.headers.items())
                self.headers_input.setPlainText(hdr_text)

        # Scope
        scope_idx = 0 if srv.scope == "user" else 1
        self.scope_combo.setCurrentIndex(scope_idx)

    def _on_transport_change(self):
        transport = self.transport_combo.currentData()
        is_stdio = transport == "stdio"
        self.command_input.setVisible(is_stdio)
        self.args_input.setVisible(is_stdio)
        self.url_input.setVisible(not is_stdio)
        self.env_input.setVisible(is_stdio)
        self.headers_input.setVisible(not is_stdio)

    def _parse_kv_lines(self, text: str, sep: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or sep not in line:
                continue
            k, _, v = line.partition(sep)
            k = k.strip()
            v = v.strip()
            if k:
                out[k] = v
        return out

    def _validate_and_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę serwera.")
            return
        transport = self.transport_combo.currentData()
        if transport == "stdio":
            if not self.command_input.text().strip():
                QMessageBox.warning(self, "Brak komendy", "Podaj komendę do uruchomienia.")
                return
        else:
            url = self.url_input.text().strip()
            if not url.startswith(("http://", "https://")):
                QMessageBox.warning(self, "Zły URL", "URL musi zaczynać się od http:// lub https://")
                return
        self.final_name = name
        self.final_scope = self.scope_combo.currentData()
        self.accept()

    def install_into(self, manager: McpManager) -> None:
        transport = self.transport_combo.currentData()
        if transport == "stdio":
            command = self.command_input.text().strip()
            args = [a for a in self.args_input.text().split() if a]
            env = self._parse_kv_lines(self.env_input.toPlainText(), "=")
            manager.add_stdio(
                self.final_name, command=command, args=args,
                env=env or None, scope=self.final_scope,
            )
        else:
            url = self.url_input.text().strip()
            headers = self._parse_kv_lines(self.headers_input.toPlainText(), ":")
            if transport == "http":
                manager.add_http(self.final_name, url=url, headers=headers or None, scope=self.final_scope)
            else:
                manager.add_sse(self.final_name, url=url, headers=headers or None, scope=self.final_scope)


class _McpJsonImportDialog(QDialog):
    """Wklej JSON konfiguracji serwera MCP."""

    def __init__(self, parent, default_scope: str, scope_locked: bool):
        super().__init__(parent)
        self.setWindowTitle("Dodaj serwer MCP z JSON")
        self.setMinimumWidth(560)
        self._scope_locked = scope_locked
        self._default_scope = default_scope
        self.final_name: str = ""
        self.final_scope: str = default_scope
        self.json_text: str = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel("📋 Dodaj serwer MCP z JSON")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        desc = QLabel(
            "Wklej JSON konfiguracji serwera MCP (np. z dokumentacji). "
            "Format: <code>{\"type\":\"stdio\",\"command\":\"npx\",\"args\":[...],\"env\":{...}}</code>"
        )
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet("color: #cccccc; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("np. moj-serwer")
        form.addRow("Nazwa:", self.name_input)

        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Globalny (dla wszystkich agentów)", "user")
        self.scope_combo.addItem("Lokalny (tylko ten agent)", "local")
        self.scope_combo.setCurrentIndex(0 if self._default_scope == "user" else 1)
        self.scope_combo.setEnabled(not self._scope_locked)
        form.addRow("Zakres:", self.scope_combo)
        layout.addLayout(form)

        self.json_input = QPlainTextEdit()
        self.json_input.setPlaceholderText(
            '{\n  "type": "stdio",\n  "command": "npx",\n  "args": ["-y", "@scope/server"]\n}'
        )
        self.json_input.setStyleSheet(
            "QPlainTextEdit { background-color: #4a1a3a; color: #ffffff; "
            "border: 1px solid #6a2a5a; border-radius: 4px; padding: 6px; "
            "font-family: monospace; }"
        )
        layout.addWidget(self.json_input, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel = QPushButton("Anuluj")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        ok = QPushButton("✅ Dodaj")
        ok.setDefault(True)
        ok.setStyleSheet("QPushButton { color: #22c55e; }")
        ok.clicked.connect(self._validate_and_accept)
        bottom.addWidget(ok)
        layout.addLayout(bottom)

    def _validate_and_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Brak nazwy", "Podaj nazwę serwera.")
            return
        text = self.json_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Brak JSON", "Wklej JSON konfiguracji serwera.")
            return
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "Zły JSON", f"Nieprawidłowy JSON: {exc}")
            return
        self.final_name = name
        self.final_scope = self.scope_combo.currentData()
        self.json_text = text
        self.accept()
