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
    QListView, QPlainTextEdit, QStackedWidget, QTabWidget, QProgressBar,
    QScrollArea, QGridLayout, QColorDialog
)
from PyQt5.QtCore import Qt, QSize, QUrl, QTimer, pyqtSignal
import threading
from PyQt5.QtGui import QFont, QDesktopServices, QPixmap, QColor

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MEMORY_PROJECTS_FILE, AGENTS_FILE, MEMORY_FILE_EXTENSIONS,
    DEFAULT_AGENTS, DEFAULT_MEMORY_PROJECTS, ASSETS_DIR,
    CLAUDE_MODELS, CLAUDE_MODELS_SHORT, DEFAULT_AGENT_MODEL,
    NEW_AGENT_DEFAULT_MODEL, TTS_VOICE_CHOICES, tts_voice_label,
    t as tr, model_label, model_label_short,
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
# Paleta okien wyboru plików (QFileDialog). Neutralna, „systemowa" — ciemny
# GNOME-owy wygląd zamiast fioletu aplikacji. Prawdziwie natywne okno GNOME nie
# jest tu dostępne dla Qt (brak aktywnej integracji portal/GTK dla okien plików),
# więc dajemy czysty, neutralny zamiennik dopasowany do ciemnej aplikacji.
DIALOG_COLORS = {
    'bg': '#2e2e2e',          # tło okna (ciemnoszare)
    'text': '#eeeeee',        # jasny tekst
    'input_bg': '#1e1e1e',    # pola/listy (ciemniejsze)
    'border': '#4a4a4a',      # neutralna ramka
    'hover': '#3a3a3a',       # podświetlenie najechania
    'selection': '#3584e4',   # zaznaczenie = niebieski akcent GNOME
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
    dialog.setLabelText(QFileDialog.LookIn, tr('dlg_file_look_in'))
    dialog.setLabelText(QFileDialog.FileName, tr('dlg_file_name'))
    dialog.setLabelText(QFileDialog.FileType, tr('dlg_file_type'))
    dialog.setLabelText(QFileDialog.Accept, tr('dlg_file_select'))
    dialog.setLabelText(QFileDialog.Reject, tr('dlg_cancel'))


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
    dialog.setLabelText(QFileDialog.Accept, tr('dlg_file_save'))

    if dialog.exec_() == QFileDialog.Accepted:
        selected = dialog.selectedFiles()
        return (selected[0] if selected else "", dialog.selectedNameFilter())
    return "", ""


class MemoryProjectsDialog(QDialog):
    """Dialog for managing memory projects and their files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_mem_title'))
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
            QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_mem_cannot_save').format(error=e))

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Path to checkmark icon
        checkmark_path = str(ASSETS_DIR / "checkmark.png").replace("\\", "/")

        # Header
        header = QLabel(tr('dlg_mem_header'))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Description
        desc = QLabel(tr('dlg_mem_desc'))
        desc.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Tree widget for projects and files
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr('dlg_mem_col_name'), tr('dlg_mem_col_path')])
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

        add_project_btn = QPushButton(f"➕ {tr('dlg_mem_add_project')}")
        add_project_btn.clicked.connect(self._add_project)
        project_btn_layout.addWidget(add_project_btn)

        add_file_btn = QPushButton(f"📄 {tr('dlg_mem_add_file')}")
        add_file_btn.clicked.connect(self._add_file)
        project_btn_layout.addWidget(add_file_btn)

        add_folder_btn = QPushButton(f"📁 {tr('dlg_mem_add_folder')}")
        add_folder_btn.clicked.connect(self._add_folder)
        project_btn_layout.addWidget(add_folder_btn)

        project_btn_layout.addStretch()

        edit_btn = QPushButton(f"✏️ {tr('dlg_edit')}")
        edit_btn.clicked.connect(self._edit_selected)
        project_btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton(f"🗑️ {tr('dlg_delete')}")
        delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        delete_btn.clicked.connect(self._delete_selected)
        project_btn_layout.addWidget(delete_btn)

        layout.addLayout(project_btn_layout)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr('dlg_save'))
        save_btn.clicked.connect(self._save_and_close)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        bottom_layout.addWidget(save_btn)

        layout.addLayout(bottom_layout)

    def _populate_tree(self):
        """Populate tree with projects and files."""
        self.tree.clear()

        for project in self.memory_projects:
            project_item = QTreeWidgetItem([
                f"📁 {project.get('name', tr('dlg_mem_unnamed'))}",
                ""
            ])
            project_item.setData(0, Qt.UserRole, {'type': 'project', 'data': project})
            project_item.setCheckState(0, Qt.Checked if project.get('enabled', True) else Qt.Unchecked)

            for file_info in project.get('files', []):
                file_path = file_info.get('path', '')
                file_name = Path(file_path).name if file_path else tr('dlg_mem_no_file')

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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mem_select_project_for_file'))
            return

        # Get project (either selected or parent)
        item_data = selected.data(0, Qt.UserRole)
        if item_data['type'] == 'file':
            project = item_data['project']
        else:
            project = item_data['data']

        # File dialog (stylizowany)
        file_filter = tr('dlg_mem_file_filter')
        files, _ = styled_get_open_file_names(
            self, tr('dlg_mem_choose_files'), str(Path.home()), file_filter
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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mem_select_project_for_files'))
            return

        # Get project
        item_data = selected.data(0, Qt.UserRole)
        if item_data['type'] == 'file':
            project = item_data['project']
        else:
            project = item_data['data']

        # Folder dialog (stylizowany)
        folder = styled_get_existing_directory(
            self, tr('dlg_mem_choose_folder'), str(Path.home())
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
                QMessageBox.information(self, tr('dlg_mem_files_added_title'), tr('dlg_mem_files_added_n').format(n=files_added))
            else:
                QMessageBox.information(self, tr('dlg_mem_no_files_title'), tr('dlg_mem_no_new_files'))

    def _edit_selected(self):
        """Edit selected project or file."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mem_select_to_edit'))
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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mem_select_to_delete'))
            return

        item_data = selected.data(0, Qt.UserRole)

        if item_data['type'] == 'project':
            project = item_data['data']
            reply = QMessageBox.question(
                self, tr('dlg_confirm_delete_title'),
                tr('dlg_mem_confirm_delete_project').format(name=project.get('name')),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.memory_projects.remove(project)
                self._populate_tree()

        elif item_data['type'] == 'file':
            file_info = item_data['data']
            project = item_data['project']

            reply = QMessageBox.question(
                self, tr('dlg_confirm_delete_title'),
                tr('dlg_mem_confirm_delete_file').format(name=Path(file_info.get('path', '')).name),
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
        self.setWindowTitle(tr('dlg_proj_edit_title') if project else tr('dlg_proj_new_title'))
        self.setMinimumWidth(400)

        self.project = project or {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_input = QLineEdit(self.project.get('name', ''))
        self.name_input.setPlaceholderText(tr('dlg_proj_name_placeholder'))
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form.addRow(tr('dlg_proj_name_label'), self.name_input)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr('dlg_save'))
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save(self):
        """Validate and save."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_proj_give_name'))
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


# Gotowa pula ikon (emoji) do szybkiego wyboru w konfiguracji agenta.
# Pogrupowana wg typowych obszarów pracy. Klucz = i18n nazwy kategorii.
AGENT_ICON_PALETTE = [
    ("dlg_agent_icon_cat_dev",
     ["💻", "🖥️", "⌨️", "👨‍💻", "🐍", "🐛", "🚀", "⚙️", "🔧", "🛠️", "📦", "🗄️", "🔌", "🧩", "☁️"]),
    ("dlg_agent_icon_cat_sales",
     ["🛒", "🛍️", "💰", "💳", "🏷️", "🤝", "🧾", "💼", "🏪"]),
    ("dlg_agent_icon_cat_seo",
     ["🔍", "🔑", "📈", "📊", "🎯", "🌐", "🏆", "📑"]),
    ("dlg_agent_icon_cat_social",
     ["📱", "📣", "💬", "📸", "🎬", "🔔", "✉️", "🎨", "💡"]),
    ("dlg_agent_icon_cat_project",
     ["📁", "🗂️", "📋", "✅", "🧠", "⭐", "🔥", "🤖"]),
]

# Gotowa paleta kolorów zakładki (Funkcja #2). Kolor zabarwia tekst zakładki
# oraz ramkę całego okna, gdy zakładka jest aktywna. Dobrane tak, by były
# czytelne na ciemnym tle skórki.
AGENT_TAB_COLORS = [
    "#ef4444", "#f97316", "#f59e0b", "#eab308",
    "#22c55e", "#10b981", "#14b8a6", "#06b6d4",
    "#3b82f6", "#6366f1", "#8b5cf6", "#a855f7",
    "#ec4899", "#f43f5e", "#94a3b8", "#e2e8f0",
]


class _ClickableLabel(QLabel):
    """QLabel z sygnałem clicked — renderuje kolorowe emoji (inaczej niż przycisk
    przy ściśniętym layoucie). Używane na podgląd ikony i komórki palety."""
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        super().mouseReleaseEvent(event)


class AgentConfigDialog(QDialog):
    """Dialog for configuring a single agent."""

    # Funkcja #3: pełna lista głosów dociągana w wątku tła — wynik wraca
    # do GUI sygnałem (lista dictów z edge_tts.list_voices() albo [] przy błędzie).
    _voices_loaded = pyqtSignal(list)

    def __init__(self, parent=None, agent: dict = None, memory_projects: list = None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_agent_edit_title') if agent else tr('dlg_agent_new_title'))

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
        header = QLabel(tr('dlg_agent_config_header'))
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
        self.tabs.addTab(self._build_tab_basic(), tr('dlg_agent_tab_basic'))
        self.tabs.addTab(self._build_tab_memory(), tr('dlg_agent_tab_memory'))
        self.tabs.addTab(self._build_tab_skills(), tr('dlg_agent_tab_skills'))
        self.tabs.addTab(self._build_tab_mcp(), tr('dlg_agent_tab_mcp'))
        main_layout.addWidget(self.tabs, stretch=1)

        # Single connection — wszystkie sekcje (skills 1A/1B + MCP 1A/1B) odświeżają się
        # gdy user zmieni katalog roboczy. Łączymy DOPIERO po utworzeniu wszystkich zakładek.
        self.dir_input.textChanged.connect(self._on_working_dir_changed)

        # Buttons (poza zakładkami — zawsze widoczne na dole)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr('dlg_save'))
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        btn_layout.addWidget(save_btn)

        save_run_btn = QPushButton(tr('dlg_agent_save_run'))
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
        self.name_input.setPlaceholderText(tr('dlg_agent_name_placeholder'))
        self.name_input.setStyleSheet(self._input_style())
        form.addRow(tr('dlg_agent_name_label'), self.name_input)

        # Working directory
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit(self.agent.get('working_directory', str(Path.home())))
        self.dir_input.setStyleSheet(self._input_style())
        dir_layout.addWidget(self.dir_input)

        browse_btn = QPushButton("📁")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_btn)
        form.addRow(tr('dlg_agent_working_dir_label'), dir_layout)

        # Tab icon (emoji ALBO własny plik graficzny)
        self.icon_spec = self.agent.get('icon') if isinstance(self.agent.get('icon'), dict) else None
        icon_layout = QHBoxLayout()
        self.icon_preview = _ClickableLabel()
        self.icon_preview.setFixedSize(34, 34)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setCursor(Qt.PointingHandCursor)
        self.icon_preview.setToolTip(tr('dlg_agent_icon_pick_tooltip'))
        self.icon_preview.setStyleSheet(
            "background:#2d0a1e;border:1px solid #4a1a3a;border-radius:4px;font-size:20px;")
        self.icon_preview.clicked.connect(self._open_icon_palette)
        icon_layout.addWidget(self.icon_preview)
        self.icon_emoji_input = QLineEdit()
        self.icon_emoji_input.setPlaceholderText(tr('dlg_agent_icon_emoji_ph'))
        self.icon_emoji_input.setMaxLength(8)
        self.icon_emoji_input.setStyleSheet(self._input_style())
        if self.icon_spec and self.icon_spec.get('kind') == 'emoji':
            self.icon_emoji_input.setText(self.icon_spec.get('value', ''))
        self.icon_emoji_input.textChanged.connect(self._on_icon_emoji_changed)
        icon_layout.addWidget(self.icon_emoji_input)
        icon_file_btn = QPushButton(tr('dlg_agent_icon_file_btn'))
        icon_file_btn.clicked.connect(self._pick_icon_file)
        icon_layout.addWidget(icon_file_btn)
        icon_clear_btn = QPushButton(tr('dlg_agent_icon_clear'))
        icon_clear_btn.clicked.connect(self._clear_icon)
        icon_layout.addWidget(icon_clear_btn)
        form.addRow(tr('dlg_agent_icon_label'), icon_layout)
        icon_hint = QLabel(tr('dlg_agent_icon_hint'))
        icon_hint.setStyleSheet("color: #888888; font-size: 11px;")
        icon_hint.setWordWrap(True)
        form.addRow("", icon_hint)
        self._update_icon_preview()

        # Kolor zakładki (Funkcja #2): zabarwia tekst zakładki + ramkę okna gdy aktywna.
        self.tab_color = self.agent.get('tab_color') if isinstance(self.agent.get('tab_color'), str) else None
        color_layout = QHBoxLayout()
        color_layout.setSpacing(4)
        # _ClickableLabel (jak przy ikonie) — QLabel nie ma sygnału clicked.
        self.color_preview = _ClickableLabel()
        self.color_preview.setFixedSize(34, 34)
        self.color_preview.setToolTip(tr('dlg_agent_color_tooltip'))
        self.color_preview.setCursor(Qt.PointingHandCursor)
        self.color_preview.clicked.connect(self._open_color_dialog)
        color_layout.addWidget(self.color_preview)
        # Inline paleta gotowych kolorów (szybki wybór bez dialogu systemowego).
        for hexc in AGENT_TAB_COLORS:
            sw = _ClickableLabel()
            sw.setFixedSize(20, 20)
            sw.setCursor(Qt.PointingHandCursor)
            sw.setToolTip(hexc)
            sw.setStyleSheet(
                f"QLabel{{background:{hexc};border:1px solid #00000055;border-radius:4px;}}"
                f"QLabel:hover{{border:2px solid #ffffff;}}")
            sw.clicked.connect(lambda c=hexc: self._set_tab_color(c))
            color_layout.addWidget(sw)
        color_layout.addStretch()
        color_clear_btn = QPushButton(tr('dlg_agent_color_clear'))
        color_clear_btn.clicked.connect(self._clear_tab_color)
        color_layout.addWidget(color_clear_btn)
        form.addRow(tr('dlg_agent_color_label'), color_layout)
        color_hint = QLabel(tr('dlg_agent_color_hint'))
        color_hint.setStyleSheet("color: #888888; font-size: 11px;")
        color_hint.setWordWrap(True)
        form.addRow("", color_hint)
        self._update_color_preview()

        # Głos czytającego (Funkcja #3): per-agent. Puste = domyślny dla języka.
        self.tts_voice = self.agent.get('tts_voice') if isinstance(self.agent.get('tts_voice'), str) else None
        self._all_voices = []  # cache pełnej listy z internetu (po „Więcej głosów…")
        voice_chevron = str(ASSETS_DIR / "chevron-down.svg").replace("\\", "/")
        voice_layout = QHBoxLayout()
        voice_layout.setSpacing(6)
        self.voice_combo = _StyledComboBox()
        self.voice_combo.setMinimumHeight(34)
        _voice_view = QListView()
        _voice_view.setMouseTracking(True)
        _voice_view.setFrameShape(QFrame.NoFrame)
        self.voice_combo.setView(_voice_view)
        # Ciemny styl rozwijanej listy — bez tego pozycje są czarne na ciemnym tle.
        self.voice_combo.setStyleSheet(self._combo_dark_style(voice_chevron))
        self._populate_voice_combo(TTS_VOICE_CHOICES)
        voice_layout.addWidget(self.voice_combo, stretch=1)
        self.voice_more_btn = QPushButton(tr('dlg_agent_voice_more'))
        self.voice_more_btn.setToolTip(tr('dlg_agent_voice_hint'))
        self.voice_more_btn.clicked.connect(self._open_voice_search)
        voice_layout.addWidget(self.voice_more_btn)
        form.addRow(tr('dlg_agent_voice_label'), voice_layout)
        voice_hint = QLabel(tr('dlg_agent_voice_hint'))
        voice_hint.setStyleSheet("color: #888888; font-size: 11px;")
        voice_hint.setWordWrap(True)
        form.addRow("", voice_hint)
        self._voices_loaded.connect(self._on_voices_loaded)

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
        for key in CLAUDE_MODELS.keys():
            self.model_combo.addItem(model_label(key), key)
        current_model = (NEW_AGENT_DEFAULT_MODEL if self.is_new_agent
                         else self.agent.get('model', DEFAULT_AGENT_MODEL))
        idx = self.model_combo.findData(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        form.addRow(tr('dlg_agent_model_label'), self.model_combo)

        model_hint = QLabel(tr('dlg_agent_model_hint'))
        model_hint.setStyleSheet("color: #888888; font-size: 11px;")
        form.addRow("", model_hint)

        layout.addLayout(form)

        # Checkboxes
        cb_style = self._checkbox_style()

        self.auto_start_checkbox = QCheckBox(tr('dlg_agent_auto_start'))
        self.auto_start_checkbox.setChecked(self.agent.get('auto_start', True))
        self.auto_start_checkbox.setStyleSheet(cb_style)
        layout.addWidget(self.auto_start_checkbox)

        self.send_memory_checkbox = QCheckBox(tr('dlg_agent_load_memory'))
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

        memory_label = QLabel(tr('dlg_agent_memory_files_label'))
        memory_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(memory_label)

        memory_info = QLabel(tr('dlg_agent_memory_info'))
        memory_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        memory_info.setWordWrap(True)
        layout.addWidget(memory_info)

        self.memory_files_container = QVBoxLayout()
        self.memory_files_container.setSpacing(5)

        for file_path in self.memory_files:
            self._add_memory_file_chip(file_path)

        layout.addLayout(self.memory_files_container)

        add_file_btn = QPushButton(tr('dlg_agent_add_file'))
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
        skills_label = QLabel(tr('dlg_agent_skills_label'))
        skills_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(skills_label)

        skills_info = QLabel(tr('dlg_agent_skills_info'))
        skills_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        skills_info.setWordWrap(True)
        layout.addWidget(skills_info)

        self.manage_agent_skills_btn = QPushButton()
        self.manage_agent_skills_btn.setStyleSheet(self._section_button_style())
        self.manage_agent_skills_btn.clicked.connect(self._open_agent_skills)
        layout.addWidget(self.manage_agent_skills_btn)
        self._update_agent_skills_button()

        # === Wyłączanie globalnych skilli ===
        disable_skills_label = QLabel(tr('dlg_agent_disable_skills_label'))
        disable_skills_label.setStyleSheet("color: #ffffff; margin-top: 6px;")
        layout.addWidget(disable_skills_label)

        disable_skills_info = QLabel(tr('dlg_agent_disable_skills_info'))
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
        mcp_label = QLabel(tr('dlg_agent_mcp_label'))
        mcp_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(mcp_label)

        mcp_info = QLabel(tr('dlg_agent_mcp_info'))
        mcp_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        mcp_info.setWordWrap(True)
        layout.addWidget(mcp_info)

        self.manage_agent_mcp_btn = QPushButton()
        self.manage_agent_mcp_btn.setStyleSheet(self._section_button_style())
        self.manage_agent_mcp_btn.clicked.connect(self._open_agent_mcp)
        layout.addWidget(self.manage_agent_mcp_btn)
        self._update_agent_mcp_button()

        # === Wyłączanie globalnych MCP ===
        disable_mcp_label = QLabel(tr('dlg_agent_disable_mcp_label'))
        disable_mcp_label.setStyleSheet("color: #ffffff; margin-top: 6px;")
        layout.addWidget(disable_mcp_label)

        disable_mcp_info = QLabel(tr('dlg_agent_disable_mcp_info'))
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
            self, tr('dlg_agent_choose_working_dir'),
            self.dir_input.text() or str(Path.home())
        )
        if directory:
            self.dir_input.setText(directory)

    # ---------- Ikona zakładki (emoji albo plik) ----------

    def _open_icon_palette(self):
        """Popup z gotową pulą emoji (klik podglądu/robota). Własne okno → nic się
        nie ściska, emoji widoczne. Wybór ustawia ikonę i zamyka popup."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('dlg_agent_icon_label'))
        dlg.setStyleSheet("QDialog{background:#1a0b14;}")
        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(8)

        content = QWidget()
        content.setStyleSheet("background:#1a0b14;")
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        cols = 12
        for cat_key, emojis in AGENT_ICON_PALETTE:
            lab = QLabel(tr(cat_key))
            lab.setStyleSheet("color:#c084fc;font-size:11px;font-weight:bold;margin-top:4px;")
            v.addWidget(lab)
            grid = QGridLayout()
            grid.setSpacing(5)
            grid.setContentsMargins(0, 0, 0, 0)
            for i, emoji in enumerate(emojis):
                cell = _ClickableLabel(emoji)
                cell.setAlignment(Qt.AlignCenter)
                cell.setFixedSize(42, 42)
                cell.setCursor(Qt.PointingHandCursor)
                cell.setToolTip(emoji)
                cell.setStyleSheet(
                    "QLabel{background:#2d0a1e;border:1px solid #4a1a3a;"
                    "border-radius:8px;font-size:24px;}"
                    "QLabel:hover{border:2px solid #22c55e;background:#3a0f28;}")
                cell.clicked.connect(
                    lambda em=emoji: (self._set_emoji_icon(em), dlg.accept()))
                grid.addWidget(cell, i // cols, i % cols)
            holder = QWidget()
            holder.setLayout(grid)
            v.addWidget(holder)
        v.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        scroll.setMinimumWidth(560)
        scroll.setMinimumHeight(420)
        scroll.setStyleSheet("QScrollArea{background:#1a0b14;border:none;}")
        scroll.viewport().setStyleSheet("background:#1a0b14;")
        outer.addWidget(scroll)

        close_btn = QPushButton(tr('dlg_close'))
        close_btn.setStyleSheet(
            "QPushButton{background:#2d0a1e;color:#ece7f5;border:1px solid #4a1a3a;"
            "border-radius:6px;padding:7px 18px;}QPushButton:hover{border-color:#22c55e;}")
        close_btn.clicked.connect(dlg.reject)
        outer.addWidget(close_btn, alignment=Qt.AlignRight)
        dlg.exec_()

    def _set_emoji_icon(self, emoji: str):
        """Wybór z palety → wpisuje emoji (textChanged ustawi spec + podgląd)."""
        self.icon_emoji_input.setText(emoji)

    def _on_icon_emoji_changed(self, text):
        text = (text or '').strip()
        self.icon_spec = {'kind': 'emoji', 'value': text} if text else None
        self._update_icon_preview()

    def _pick_icon_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('dlg_agent_icon_file_title'), str(Path.home()),
            "Obrazy (*.png *.svg *.jpg *.jpeg *.ico *.gif)")
        if path:
            self.icon_spec = {'kind': 'file', 'value': path}
            self.icon_emoji_input.blockSignals(True)
            self.icon_emoji_input.clear()
            self.icon_emoji_input.blockSignals(False)
            self._update_icon_preview()

    def _clear_icon(self):
        self.icon_spec = None
        self.icon_emoji_input.blockSignals(True)
        self.icon_emoji_input.clear()
        self.icon_emoji_input.blockSignals(False)
        self._update_icon_preview()

    def _update_icon_preview(self):
        """Pokaż w podglądzie: emoji (tekst), obrazek (pixmap) albo domyślne 🤖."""
        spec = self.icon_spec
        if spec and spec.get('kind') == 'emoji' and spec.get('value'):
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText(spec['value'])
        elif spec and spec.get('kind') == 'file' and Path(spec.get('value', '')).exists():
            self.icon_preview.setText("")
            pm = QPixmap(spec['value'])
            if not pm.isNull():
                self.icon_preview.setPixmap(
                    pm.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.icon_preview.setPixmap(QPixmap())
            self.icon_preview.setText("🤖")

    # ---------- Kolor zakładki (Funkcja #2) ----------

    def _open_color_dialog(self):
        """Systemowy wybór koloru (pełna paleta). Pusty wybór = bez zmian."""
        initial = QColor(self.tab_color) if self.tab_color else QColor("#8b5cf6")
        color = QColorDialog.getColor(initial, self, tr('dlg_agent_color_label'))
        if color.isValid():
            self._set_tab_color(color.name())

    def _set_tab_color(self, hexc: str):
        self.tab_color = hexc
        self._update_color_preview()

    def _clear_tab_color(self):
        self.tab_color = None
        self._update_color_preview()

    def _update_color_preview(self):
        """Pokaż aktualny kolor w podglądzie; brak = szary placeholder ze znakiem."""
        if self.tab_color:
            self.color_preview.setText("")
            self.color_preview.setStyleSheet(
                f"background:{self.tab_color};border:1px solid #00000055;border-radius:4px;")
        else:
            self.color_preview.setText("∅")
            self.color_preview.setStyleSheet(
                "background:#2d0a1e;color:#888888;border:1px solid #4a1a3a;"
                "border-radius:4px;font-size:16px;")
            self.color_preview.setAlignment(Qt.AlignCenter)

    # ---------- Głos czytającego (Funkcja #3) ----------

    @staticmethod
    def _combo_dark_style(chevron_path: str) -> str:
        """Ciemny styl QComboBox + rozwijanej listy (jasny tekst na ciemnym tle)."""
        return f"""
            QComboBox {{
                background-color: #2d0a1e; color: #ffffff;
                border: 1px solid #4a1a3a; border-radius: 4px;
                padding: 6px 36px 6px 10px; combobox-popup: 0;
            }}
            QComboBox:hover {{ border-color: #22c55e; }}
            QComboBox:on {{ border-color: #22c55e; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: top right;
                width: 28px; border-left: 1px solid #4a1a3a;
                background-color: #3a0f28;
                border-top-right-radius: 4px; border-bottom-right-radius: 4px;
            }}
            QComboBox::drop-down:hover {{ background-color: #4a1a3a; }}
            QComboBox::down-arrow {{ image: url("{chevron_path}"); width: 10px; height: 6px; }}
            QComboBox QAbstractItemView {{
                background-color: #2d0a1e; color: #ffffff;
                border: 1px solid #4a1a3a; outline: 0;
                selection-background-color: #4a1a3a; selection-color: #ffffff;
            }}
            QComboBox QListView::item {{ padding: 8px 12px; min-height: 26px; border: none; }}
            QComboBox QListView::item:selected {{ background-color: #4a1a3a; color: #ffffff; }}
        """

    def _populate_voice_combo(self, choices, selected=None):
        """Wypełnij dropdown: 'Domyślny (wg języka)' + (voice_id, etykieta).
        Zachowuje aktualnie wybrany głos spoza listy (np. dobrany wcześniej
        z pełnej listy z internetu), żeby był widoczny i zaznaczony."""
        sel = selected if selected is not None else self.tts_voice
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        self.voice_combo.addItem(tr('dlg_agent_voice_default'), None)
        ids = set()
        for vid, label in choices:
            self.voice_combo.addItem(label, vid)
            ids.add(vid)
        if sel and sel not in ids:
            self.voice_combo.addItem(tts_voice_label(sel), sel)
        idx = self.voice_combo.findData(sel) if sel else 0
        self.voice_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.voice_combo.blockSignals(False)

    def _open_voice_search(self):
        """Otwórz wyszukiwarkę pełnej listy głosów. Pierwsze użycie dociąga listę
        z internetu w tle (potem z cache), następnie otwiera okno z wyszukiwarką."""
        if self._all_voices:
            self._open_voice_picker(self._all_voices)
            return
        self.voice_more_btn.setEnabled(False)
        self.voice_more_btn.setText(tr('dlg_agent_voice_loading'))

        def worker():
            try:
                import asyncio
                import edge_tts
                voices = asyncio.run(edge_tts.list_voices())
            except Exception:
                voices = []
            # emit jest wątkowo bezpieczny — slot wykona się w wątku GUI.
            self._voices_loaded.emit(voices or [])

        threading.Thread(target=worker, daemon=True).start()

    def _on_voices_loaded(self, voices):
        """Slot GUI: zapisz cache i otwórz wyszukiwarkę."""
        self.voice_more_btn.setEnabled(True)
        self.voice_more_btn.setText(tr('dlg_agent_voice_more'))
        if not voices:
            QMessageBox.information(self, tr('dlg_agent_voice_label'),
                                    tr('dlg_agent_voice_load_failed'))
            return
        self._all_voices = voices
        self._open_voice_picker(voices)

    @staticmethod
    def _voice_picker_label(v) -> str:
        """Etykieta z pełnych danych edge-tts: '<język (region)> — <Imię> ♀/♂'."""
        sn = v.get('ShortName', '')
        sym = "♀" if (v.get('Gender', '') or '').lower().startswith('f') else "♂"
        fn = v.get('FriendlyName', '') or ''
        lang = fn.split(' - ')[-1].strip() if ' - ' in fn else v.get('Locale', '')
        tail = sn.split('-')[-1].replace('Neural', '').replace('Multilingual', ' (multi)')
        return f"{lang} — {tail} {sym}".strip()

    def _open_voice_picker(self, voices):
        """Okno wyboru głosu z pełnej listy, z wyszukiwarką po języku (po nazwie
        języka z FriendlyName, kodzie locale lub imieniu głosu)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('dlg_agent_voice_search_title'))
        dlg.setStyleSheet("QDialog{background:#1a0b14;} QLabel{color:#c9c2d6;}")
        dlg.setMinimumSize(560, 520)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 16, 16, 12)
        v.setSpacing(8)

        search = QLineEdit()
        search.setPlaceholderText(tr('dlg_agent_voice_search_ph'))
        search.setStyleSheet(
            "QLineEdit{background:#2d0a1e;color:#fff;border:1px solid #4a1a3a;"
            "border-radius:6px;padding:8px;}")
        v.addWidget(search)

        count_lbl = QLabel("")
        count_lbl.setStyleSheet("color:#888;font-size:11px;")
        v.addWidget(count_lbl)

        listw = QListWidget()
        listw.setStyleSheet(
            "QListWidget{background:#2d0a1e;color:#fff;border:1px solid #4a1a3a;border-radius:6px;}"
            "QListWidget::item{padding:7px 10px;}"
            "QListWidget::item:selected{background:#4a1a3a;color:#fff;}")
        v.addWidget(listw, stretch=1)

        # Pozycje: (etykieta, voice_id, tekst-do-wyszukania).
        items = []
        for vc in sorted(voices, key=lambda x: (x.get('Locale', ''), x.get('ShortName', ''))):
            sn = vc.get('ShortName', '')
            if not sn:
                continue
            label = self._voice_picker_label(vc)
            search_text = f"{vc.get('FriendlyName', '')} {sn} {vc.get('Locale', '')}".lower()
            items.append((label, sn, search_text))

        def repopulate(query=""):
            q = (query or "").strip().lower()
            listw.clear()
            n = 0
            for label, sn, st in items:
                if not q or q in st:
                    it = QListWidgetItem(label)
                    it.setData(Qt.UserRole, sn)
                    listw.addItem(it)
                    n += 1
            count_lbl.setText(tr('dlg_agent_voice_search_count').format(n=n))

        repopulate()
        search.textChanged.connect(repopulate)

        # Zaznacz bieżący głos, jeśli widoczny.
        if self.tts_voice:
            for i in range(listw.count()):
                if listw.item(i).data(Qt.UserRole) == self.tts_voice:
                    listw.setCurrentRow(i)
                    break

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(tr('dlg_cancel'))
        cancel.setStyleSheet(
            "QPushButton{background:#2d0a1e;color:#ece7f5;border:1px solid #4a1a3a;"
            "border-radius:6px;padding:7px 16px;}QPushButton:hover{border-color:#22c55e;}")
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(cancel)
        ok = QPushButton(tr('dlg_save'))
        ok.setStyleSheet(
            "QPushButton{background:#2d0a1e;color:#22c55e;font-weight:bold;"
            "border:1px solid #4a1a3a;border-radius:6px;padding:7px 16px;}"
            "QPushButton:hover{border-color:#22c55e;}")
        ok.clicked.connect(dlg.accept)
        btns.addWidget(ok)
        v.addLayout(btns)

        listw.itemDoubleClicked.connect(lambda _it: dlg.accept())

        if dlg.exec_() == QDialog.Accepted:
            it = listw.currentItem()
            if it is not None:
                sn = it.data(Qt.UserRole)
                if sn:
                    self.tts_voice = sn
                    # Dołóż wybrany głos do dropdowna (PL+EN) i zaznacz.
                    self._populate_voice_combo(TTS_VOICE_CHOICES, selected=sn)

    def _save(self):
        """Validate and save."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_agent_give_name'))
            return

        directory = self.dir_input.text().strip()
        if not Path(directory).is_dir():
            QMessageBox.warning(self, tr('dlg_agent_invalid_dir_title'), tr('dlg_agent_dir_not_exist'))
            return

        self.accept()

    def _save_and_run(self):
        """Validate, save and mark for immediate run."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_agent_give_name'))
            return

        directory = self.dir_input.text().strip()
        if not Path(directory).is_dir():
            QMessageBox.warning(self, tr('dlg_agent_invalid_dir_title'), tr('dlg_agent_dir_not_exist'))
            return

        self.run_immediately = True
        self.accept()

    def get_run_immediately(self) -> bool:
        """Return whether agent should be run immediately after save."""
        return self.run_immediately

    def get_data(self) -> dict:
        """Return agent configuration."""
        data = {
            'id': self.agent.get('id', str(uuid.uuid4())[:8]),
            'name': self.name_input.text().strip(),
            'working_directory': self.dir_input.text().strip(),
            'memory_files': self.memory_files,
            'auto_start': self.auto_start_checkbox.isChecked(),
            'send_memory_on_start': self.send_memory_checkbox.isChecked(),
            'model': self.model_combo.currentData() or DEFAULT_AGENT_MODEL,
            'icon': self.icon_spec,
            'tab_color': self.tab_color,
            'tts_voice': self.voice_combo.currentData(),
        }
        # splitter_sizes tylko dla agenta, który już je ma (edycja istniejącego).
        # Nowy agent zostaje bez klucza — MainWindow dziedziczy proporcje
        # z aktywnej zakładki, a fallbackiem jest config.DEFAULT_SPLITTER_SIZES.
        if self.agent.get('splitter_sizes'):
            data['splitter_sizes'] = self.agent['splitter_sizes']
        return data

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
            self.manage_agent_skills_btn.setText(tr('dlg_agent_manage_skills_no_dir'))
            self.manage_agent_skills_btn.setEnabled(False)
            self.manage_agent_skills_btn.setToolTip(tr('dlg_set_valid_dir_first'))
            return

        # Count installed local skills (silently — directory may not exist yet)
        try:
            count = len(SkillsManager(skills_dir=local_dir).list_skills())
        except Exception:
            count = 0

        if count == 0:
            label = tr('dlg_agent_manage_skills_none')
        elif count == 1:
            label = tr('dlg_agent_manage_skills_1')
        elif count < 5:
            label = tr('dlg_agent_manage_skills_few').format(n=count)
        else:
            label = tr('dlg_agent_manage_skills_many').format(n=count)

        self.manage_agent_skills_btn.setText(label)
        self.manage_agent_skills_btn.setEnabled(True)
        self.manage_agent_skills_btn.setToolTip(
            tr('dlg_agent_skills_local_tooltip').format(path=local_dir)
        )

    def _open_agent_skills(self):
        """Open SkillsManagerDialog scoped to <working_directory>/.claude/skills/."""
        local_dir = self._agent_local_skills_dir()
        if local_dir is None:
            QMessageBox.warning(
                self,
                tr('dlg_no_dir_title'),
                tr('dlg_set_valid_dir_first')
            )
            return

        agent_name = self.name_input.text().strip() or tr('dlg_agent_fallback_name')
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
            self.global_skills_count_label.setText(tr('dlg_agent_skills_count_no_dir'))
            self.global_skills_count_label.setStyleSheet(
                "color: #f59e0b; font-size: 11px;"
            )
        elif not global_skills:
            self.global_skills_count_label.setText(tr('dlg_agent_skills_count_none'))
            self.global_skills_count_label.setStyleSheet(
                "color: #cccccc; font-size: 11px;"
            )
        else:
            disabled_count = sum(1 for s in global_skills if s.name in disabled_set)
            self.global_skills_count_label.setText(
                tr('dlg_agent_disabled_of_global').format(disabled=disabled_count, total=len(global_skills))
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

            full_description = skill.description or tr('dlg_agent_skills_no_desc')
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
                self, tr('dlg_save_error_title'),
                tr('dlg_agent_skills_save_failed').format(error=exc)
            )
            return

        # Refresh just the count label (avoid full list rebuild — it would
        # detach checkbox widgets and lose the keyboard focus).
        global_skills = SkillsManager().list_skills()
        disabled_count = len(settings.get_disabled_global_skills())
        self.global_skills_count_label.setText(
            tr('dlg_agent_disabled_of_global').format(disabled=disabled_count, total=len(global_skills))
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
            self.manage_agent_mcp_btn.setText(tr('dlg_agent_manage_mcp_no_dir'))
            self.manage_agent_mcp_btn.setEnabled(False)
            self.manage_agent_mcp_btn.setToolTip(tr('dlg_set_valid_dir_first'))
            return

        # Count local-scope MCP servers for this working_dir (silently)
        try:
            servers = McpManager(working_dir=wd_path).list_servers()
            count = sum(1 for s in servers if s.scope == "local" and not s.managed)
        except Exception:
            count = 0

        if count == 0:
            label = tr('dlg_agent_manage_mcp_none')
        elif count == 1:
            label = tr('dlg_agent_manage_mcp_1')
        elif count < 5:
            label = tr('dlg_agent_manage_mcp_few').format(n=count)
        else:
            label = tr('dlg_agent_manage_mcp_many').format(n=count)

        self.manage_agent_mcp_btn.setText(label)
        self.manage_agent_mcp_btn.setEnabled(True)
        self.manage_agent_mcp_btn.setToolTip(
            tr('dlg_agent_mcp_local_tooltip').format(path=wd_path)
        )

    def _open_agent_mcp(self):
        """Open McpManagerDialog scoped to this agent's working_dir."""
        wd_path = self._agent_working_dir_path()
        if wd_path is None:
            QMessageBox.warning(self, tr('dlg_no_dir_title'), tr('dlg_set_valid_dir_first'))
            return
        agent_name = self.name_input.text().strip() or tr('dlg_agent_fallback_name')
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
            self.global_mcp_count_label.setText(tr('dlg_agent_skills_count_no_dir'))
            self.global_mcp_count_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
        elif not global_mcps:
            self.global_mcp_count_label.setText(tr('dlg_agent_mcp_count_none'))
            self.global_mcp_count_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        else:
            disabled_count = sum(1 for s in global_mcps if s.sanitized_name in disabled_set)
            self.global_mcp_count_label.setText(
                tr('dlg_agent_disabled_of_global').format(disabled=disabled_count, total=len(global_mcps))
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
            scope_label = _mcp_scope_label(srv.scope)
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
                self, tr('dlg_save_error_title'),
                tr('dlg_agent_mcp_save_failed').format(error=exc)
            )
            return
        # Refresh just the count label (avoid full list rebuild — would lose checkbox focus)
        global_mcps = self._list_global_mcp_servers()
        disabled_count = len(settings.get_disabled_mcp_sanitized())
        self.global_mcp_count_label.setText(
            tr('dlg_agent_disabled_of_global').format(disabled=disabled_count, total=len(global_mcps))
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
        file_filter = tr('dlg_mem_file_filter')
        files, _ = styled_get_open_file_names(
            self, tr('dlg_agent_choose_memory_files'), str(Path.home()), file_filter
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
        self.setWindowTitle(tr('dlg_agents_title'))
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
        header = QLabel(tr('dlg_agents_header'))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Description
        desc = QLabel(tr('dlg_agents_desc'))
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

        self.up_btn = QPushButton(tr('dlg_agents_move_up'))
        self.up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton(tr('dlg_agents_move_down'))
        self.down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self.down_btn)

        btn_layout.addSpacing(15)

        self.run_btn = QPushButton(tr('dlg_agents_run'))
        self.run_btn.clicked.connect(self._run_agent)
        self.run_btn.setStyleSheet("QPushButton { color: #3b82f6; }")
        btn_layout.addWidget(self.run_btn)

        btn_layout.addSpacing(15)

        self.add_btn = QPushButton(tr('dlg_agents_add'))
        self.add_btn.clicked.connect(self._add_agent)
        self.add_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton(tr('dlg_agents_edit'))
        self.edit_btn.clicked.connect(self._edit_agent)
        btn_layout.addWidget(self.edit_btn)

        self.duplicate_btn = QPushButton(tr('dlg_agents_duplicate'))
        self.duplicate_btn.clicked.connect(self._duplicate_agent)
        btn_layout.addWidget(self.duplicate_btn)

        self.delete_btn = QPushButton(tr('dlg_agents_delete'))
        self.delete_btn.clicked.connect(self._delete_agent)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr('dlg_save'))
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
                memory_info = tr('dlg_agents_no_files')
            elif file_count == 1:
                memory_info = tr('dlg_agents_files_1')
            elif file_count < 5:
                memory_info = tr('dlg_agents_files_few').format(n=file_count)
            else:
                memory_info = tr('dlg_agents_files_many').format(n=file_count)

            # Model used by this agent
            model_key = agent.get('model', DEFAULT_AGENT_MODEL)
            model_label_text = model_label_short(model_key)

            auto_start = agent.get('auto_start', True)
            agent_name = agent.get('name', tr('dlg_agents_unnamed'))

            # Empty list item — visual content lives in the attached widget.
            item = QListWidgetItem()
            item.setData(Qt.UserRole, agent)
            item.setSizeHint(QSize(0, 56))
            self.list_widget.addItem(item)

            # Custom widget for this row. TŁO sygnalizuje auto-start: zielone =
            # agent uruchamiany przy starcie aplikacji, szare = nie. Kolor jest
            # PÓŁPRZEZROCZYSTY, żeby fioletowe podświetlenie zaznaczenia
            # (QListWidget::item:selected) prześwitywało. Zastąpiło nieczytelne
            # na Linuksie emoji 🟢/⚪ (renderowały się monochromatycznie — szaro).
            row_widget = QWidget()
            row_bg = "rgba(34, 160, 84, 70)" if auto_start else "rgba(120, 125, 135, 65)"
            row_widget.setStyleSheet(f"background-color: {row_bg};")
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(2)

            name_label = QLabel(agent_name)
            name_label.setStyleSheet(
                "color: #ffffff; font-size: 13px; font-weight: bold; background: transparent; border: none;"
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

            model_mid_label = QLabel(f"  •  🤖 {model_label_text}  •  ")
            model_mid_label.setStyleSheet(info_style)

            # Placeholder — właściwą zawartość wstawi _on_summary_ready po wątku.
            skills_label = QLabel(f"🧩 {tr('dlg_agents_loading')}")
            skills_label.setStyleSheet(info_style)
            skills_label.setToolTip(tr('dlg_agents_skills_loading_tooltip'))

            mcp_sep_label = QLabel("  •  ")
            mcp_sep_label.setStyleSheet(info_style)

            mcp_label = QLabel(f"🔌 {tr('dlg_agents_loading')}")
            mcp_label.setStyleSheet(info_style)
            mcp_label.setToolTip(tr('dlg_agents_mcp_loading_tooltip'))

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
            text, tooltip = tr('dlg_agents_skills_error'), tr('dlg_agents_skills_error_tooltip').format(error=e)
        if token == self._populate_token:
            self._summary_ready.emit(token, row, "skills", text, tooltip)

        # MCP — wolne (claude mcp list ~2s na agenta, czasem timeout 30s).
        try:
            text, tooltip = self._format_mcp_summary(agent)
        except Exception as e:
            text, tooltip = tr('dlg_agents_mcp_error'), tr('dlg_agents_mcp_error_tooltip').format(error=e)
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
            return tr('dlg_agents_mem_tooltip_none')
        lines = [tr('dlg_agents_mem_tooltip_header'), ""]
        for path in files:
            lines.append(f"   • {Path(path).name}")
        return "\n".join(lines)

    @staticmethod
    def _pl_local(n: int) -> str:
        """Liczba mnoga dla 'lokalny' (PL ma formy 1/2-4/inne; EN ma jedną)."""
        if n == 1:
            return tr('dlg_agents_local_1').format(n=n)
        last_digit = n % 10
        last_two = n % 100
        if 2 <= last_digit <= 4 and not 12 <= last_two <= 14:
            return tr('dlg_agents_local_few').format(n=n)
        return tr('dlg_agents_local_many').format(n=n)

    @staticmethod
    def _pl_global_only(n: int) -> str:
        """Liczba mnoga dla 'globalny' (bez ułamka): 1, 2-4, inne."""
        if n == 1:
            return tr('dlg_agents_global_1').format(n=n)
        last_digit = n % 10
        last_two = n % 100
        if 2 <= last_digit <= 4 and not 12 <= last_two <= 14:
            return tr('dlg_agents_global_few').format(n=n)
        return tr('dlg_agents_global_many').format(n=n)

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
                tr('dlg_agents_skills_unknown'),
                tr('dlg_agents_skills_unknown_tooltip')
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
            display = tr('dlg_agents_no_skills')
        elif n_disabled == 0 and n_local == 0:
            display = tr('dlg_agents_skills_global').format(**{'global': self._pl_global_only(n_global_on)})
        elif n_disabled == 0 and n_local > 0:
            display = tr('dlg_agents_skills_global_local').format(
                **{'global': self._pl_global_only(n_global_on), 'local': self._pl_local(n_local)}
            )
        elif n_disabled > 0 and n_local == 0:
            display = tr('dlg_agents_skills_cut').format(on=n_global_on, total=n_global_total)
        else:
            display = tr('dlg_agents_skills_cut_local').format(
                on=n_global_on, total=n_global_total, local=self._pl_local(n_local)
            )

        # === Tooltip — pełna lista nazw ===
        tooltip_parts = [tr('dlg_agents_skills_tooltip_header')]
        if enabled_global:
            tooltip_parts.append(tr('dlg_agents_tooltip_global_active').format(n=len(enabled_global)))
            tooltip_parts.extend(f"   • {name}" for name in enabled_global)
        if disabled_global:
            tooltip_parts.append(tr('dlg_agents_tooltip_global_disabled').format(n=len(disabled_global)))
            tooltip_parts.extend(f"   • {name}" for name in disabled_global)
        if local_names:
            tooltip_parts.append(tr('dlg_agents_tooltip_local').format(n=len(local_names)))
            tooltip_parts.extend(f"   • {name}" for name in local_names)
        if not enabled_global and not disabled_global and not local_names:
            tooltip_parts.append(tr('dlg_agents_skills_tooltip_none'))

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
                tr('dlg_agents_mcp_unknown'),
                tr('dlg_agents_mcp_unknown_tooltip')
            )

        wd_path = Path(working_dir)

        try:
            servers = McpManager(working_dir=wd_path).list_servers()
        except Exception:
            return (
                tr('dlg_agents_mcp_unknown'),
                tr('dlg_agents_mcp_fetch_failed_tooltip')
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
            display = tr('dlg_agents_no_mcp')
        elif n_disabled == 0 and n_local == 0:
            display = tr('dlg_agents_mcp_global').format(**{'global': self._pl_global_only(n_global_on)})
        elif n_disabled == 0 and n_local > 0:
            display = tr('dlg_agents_mcp_global_local').format(
                **{'global': self._pl_global_only(n_global_on), 'local': self._pl_local(n_local)}
            )
        elif n_disabled > 0 and n_local == 0:
            display = tr('dlg_agents_mcp_cut').format(on=n_global_on, total=n_global_total)
        else:
            display = tr('dlg_agents_mcp_cut_local').format(
                on=n_global_on, total=n_global_total, local=self._pl_local(n_local)
            )

        # === Tooltip — pełna lista nazw ===
        tooltip_parts = [tr('dlg_agents_mcp_tooltip_header')]
        if enabled_global:
            tooltip_parts.append(tr('dlg_agents_tooltip_global_active').format(n=len(enabled_global)))
            tooltip_parts.extend(f"   • {s.name}" for s in enabled_global)
        if disabled_global:
            tooltip_parts.append(tr('dlg_agents_tooltip_global_disabled').format(n=len(disabled_global)))
            tooltip_parts.extend(f"   • {s.name}" for s in disabled_global)
        if local_servers:
            tooltip_parts.append(tr('dlg_agents_tooltip_local').format(n=len(local_servers)))
            tooltip_parts.extend(f"   • {s.name}" for s in local_servers)
        if not enabled_global and not disabled_global and not local_servers:
            tooltip_parts.append(tr('dlg_agents_mcp_tooltip_none'))

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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_agents_select_to_run'))
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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_agents_select_to_edit'))
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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_agents_select_to_duplicate'))
            return

        agent = self.agents[row].copy()
        agent['id'] = str(uuid.uuid4())[:8]
        agent['name'] = tr('dlg_agents_copy_suffix').format(name=agent.get('name', tr('dlg_agent_fallback_name')))
        self.agents.append(agent)
        self._populate_list()
        self.list_widget.setCurrentRow(len(self.agents) - 1)

    def _delete_agent(self):
        """Delete selected agent."""
        row = self._get_selected_index()
        if row < 0:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_agents_select_to_delete'))
            return

        if len(self.agents) <= 1:
            QMessageBox.warning(self, tr('dlg_agents_cannot_delete_title'), tr('dlg_agents_must_keep_one'))
            return

        agent = self.agents[row]
        reply = QMessageBox.question(
            self, tr('dlg_confirm_delete_title'),
            tr('dlg_agents_confirm_delete').format(name=agent.get('name')),
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
            self.setWindowTitle(tr('dlg_skills_agent_title_named').format(name=agent_name))
        elif self._is_per_agent:
            self.setWindowTitle(tr('dlg_skills_agent_title'))
        else:
            self.setWindowTitle(tr('dlg_skills_global_title'))

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
                tr('dlg_skills_agent_header_named').format(name=self._agent_name)
                if self._agent_name
                else tr('dlg_skills_agent_header')
            )
        else:
            header_text = tr('dlg_skills_global_title')

        header = QLabel(header_text)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        if self._is_per_agent:
            desc_text = tr('dlg_skills_agent_desc')
        else:
            desc_text = tr('dlg_skills_global_desc')
        desc = QLabel(desc_text)
        desc.setStyleSheet("color: #cccccc; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        path_label = QLabel(tr('dlg_skills_location').format(path=self.skills_manager.skills_dir))
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

        self.add_zip_btn = QPushButton(tr('dlg_skills_add_zip'))
        self.add_zip_btn.clicked.connect(self._add_from_zip)
        self.add_zip_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_zip_btn)

        self.add_folder_btn = QPushButton(tr('dlg_skills_add_folder'))
        self.add_folder_btn.clicked.connect(self._add_from_folder)
        self.add_folder_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_folder_btn)

        btn_layout.addSpacing(15)

        self.open_folder_btn = QPushButton(tr('dlg_skills_show_folder'))
        self.open_folder_btn.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.open_folder_btn)

        self.refresh_btn = QPushButton(tr('dlg_skills_refresh'))
        self.refresh_btn.clicked.connect(self._populate_list)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addSpacing(15)

        self.delete_btn = QPushButton(tr('dlg_skills_delete'))
        self.delete_btn.clicked.connect(self._delete_skill)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        close_btn = QPushButton(tr('dlg_close'))
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
            empty_label = QLabel(tr('dlg_skills_empty'))
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

            description = skill.description or tr('dlg_skills_no_desc')
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
        file_filter = tr('dlg_skills_zip_filter')
        zip_path, _ = styled_get_open_file_name(
            self, tr('dlg_skills_choose_zip'), str(Path.home()), file_filter
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
            self, tr('dlg_skills_choose_folder'), str(Path.home())
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
            if tr('dlg_skills_already_exists_marker') in msg:
                reply = QMessageBox.question(
                    self,
                    tr('dlg_skills_already_exists_title'),
                    tr('dlg_skills_overwrite_prompt').format(msg=msg),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
                try:
                    skill = install_fn(True)
                except SkillInstallError as exc2:
                    QMessageBox.warning(self, tr('dlg_install_error_title'), str(exc2))
                    return
            else:
                QMessageBox.warning(self, tr('dlg_install_error_title'), msg)
                return
        except Exception as exc:
            QMessageBox.warning(self, tr('dlg_install_error_title'), tr('dlg_skills_unexpected_error').format(error=exc))
            return

        QMessageBox.information(
            self, tr('dlg_installed_title'), tr('dlg_skills_installed_msg').format(name=skill.name)
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
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_skills_select_to_delete'))
            return

        reply = QMessageBox.question(
            self,
            tr('dlg_confirm_delete_title'),
            tr('dlg_skills_confirm_delete').format(name=skill.name, path=skill.folder_path),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            removed = self.skills_manager.remove(skill.folder_name)
        except SkillInstallError as exc:
            QMessageBox.warning(self, tr('dlg_delete_error_title'), str(exc))
            return

        if removed:
            QMessageBox.information(self, tr('dlg_removed_title'), tr('dlg_skills_removed_msg').format(name=skill.name))
        else:
            QMessageBox.warning(self, tr('dlg_not_found_title'), tr('dlg_skills_folder_gone'))
        self._populate_list()


# ============================================================================
# MCP Manager — zarządzanie serwerami Model Context Protocol
# ============================================================================

# Mapowanie statusu na ikonę + kolor (do listy). Etykieta tekstowa jest
# tłumaczona w locie przez _mcp_status_badge() — tu trzymamy tylko ikonę,
# kolor i klucz tłumaczenia.
_MCP_STATUS_BADGE_DATA = {
    STATUS_CONNECTED: ("✅", "#22c55e", "dlg_mcp_status_connected"),
    STATUS_NEEDS_AUTH: ("🔐", "#eab308", "dlg_mcp_status_needs_auth"),
    STATUS_FAILED: ("❌", "#ef4444", "dlg_mcp_status_failed"),
    STATUS_UNKNOWN: ("❓", "#94a3b8", "dlg_mcp_status_unknown"),
}

_MCP_SCOPE_LABEL_KEY = {
    "user": "dlg_mcp_scope_user",
    "local": "dlg_mcp_scope_local",
    "managed": "dlg_mcp_scope_managed",
}


def _mcp_status_badge(status):
    """Zwraca (ikona, kolor, przetłumaczona_etykieta) dla statusu MCP."""
    icon, color, key = _MCP_STATUS_BADGE_DATA.get(
        status, _MCP_STATUS_BADGE_DATA[STATUS_UNKNOWN]
    )
    return icon, color, tr(key)


def _mcp_scope_label(scope: str) -> str:
    """Przetłumaczona etykieta zakresu MCP (fallback: surowy scope)."""
    key = _MCP_SCOPE_LABEL_KEY.get(scope)
    return tr(key) if key else scope


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
            self.setWindowTitle(tr('dlg_mcp_agent_title_named').format(name=agent_name))
        elif self._is_per_agent:
            self.setWindowTitle(tr('dlg_mcp_agent_title'))
        else:
            self.setWindowTitle(tr('dlg_mcp_global_title'))

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
                tr('dlg_mcp_agent_header_named').format(name=self._agent_name)
                if self._agent_name else tr('dlg_mcp_agent_header')
            )
            desc_text = tr('dlg_mcp_agent_desc')
        else:
            header_text = tr('dlg_mcp_global_header')
            desc_text = tr('dlg_mcp_global_desc')

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

        self.add_template_btn = QPushButton(tr('dlg_mcp_add_template'))
        self.add_template_btn.clicked.connect(self._add_from_template)
        self.add_template_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_template_btn)

        self.add_manual_btn = QPushButton(tr('dlg_mcp_add_manual'))
        self.add_manual_btn.clicked.connect(self._add_manual)
        self.add_manual_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_manual_btn)

        self.add_json_btn = QPushButton(tr('dlg_mcp_add_json'))
        self.add_json_btn.clicked.connect(self._add_from_json)
        self.add_json_btn.setStyleSheet("QPushButton { color: #22c55e; }")
        btn_layout.addWidget(self.add_json_btn)

        btn_layout.addSpacing(15)

        # Akcje na zaznaczonym serwerze
        self.authorize_btn = QPushButton(tr('dlg_mcp_authorize'))
        self.authorize_btn.clicked.connect(self._authorize_selected)
        self.authorize_btn.setStyleSheet("QPushButton { color: #eab308; }")
        self.authorize_btn.setToolTip(tr('dlg_mcp_authorize_tooltip'))
        btn_layout.addWidget(self.authorize_btn)

        self.test_btn = QPushButton(tr('dlg_mcp_test'))
        self.test_btn.clicked.connect(self._test_selected)
        self.test_btn.setToolTip(tr('dlg_mcp_test_tooltip'))
        btn_layout.addWidget(self.test_btn)

        self.edit_btn = QPushButton(tr('dlg_mcp_edit'))
        self.edit_btn.clicked.connect(self._edit_selected)
        self.edit_btn.setToolTip(tr('dlg_mcp_edit_tooltip'))
        btn_layout.addWidget(self.edit_btn)

        btn_layout.addSpacing(15)

        self.refresh_btn = QPushButton(tr('dlg_mcp_refresh'))
        self.refresh_btn.clicked.connect(self._populate_list)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addSpacing(15)

        self.delete_btn = QPushButton(tr('dlg_mcp_delete'))
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setStyleSheet("QPushButton { color: #ef4444; }")
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout, stretch=1)

        # Stopka
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        close_btn = QPushButton(tr('dlg_close'))
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)
        layout.addLayout(bottom_layout)

    # ---------- Lista ----------

    def _populate_list(self):
        self.list_widget.clear()
        try:
            all_servers = self.manager.list_servers()
        except McpError as exc:
            QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_mcp_fetch_failed').format(error=exc))
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
            empty_label = QLabel(tr('dlg_mcp_empty'))
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

            icon, color, status_label = _mcp_status_badge(srv.status)
            scope_label = _mcp_scope_label(srv.scope)

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
            QMessageBox.warning(self, tr('dlg_add_error_title'), str(exc))
            return
        QMessageBox.information(
            self, tr('dlg_added_title'),
            tr('dlg_mcp_added_msg').format(
                name=config_dlg.final_name,
                hint=picker.selected_template.install_hint
            ).strip()
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
            QMessageBox.warning(self, tr('dlg_add_error_title'), str(exc))
            return
        QMessageBox.information(self, tr('dlg_added_title'), tr('dlg_mcp_added_simple').format(name=dlg.final_name))
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
            QMessageBox.warning(self, tr('dlg_add_error_title'), str(exc))
            return
        QMessageBox.information(self, tr('dlg_added_title'), tr('dlg_mcp_added_simple').format(name=dlg.final_name))
        self._populate_list()

    # ---------- Akcje: autoryzacja ----------

    def _authorize_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mcp_select_to_authorize'))
            return

        if srv.managed:
            # claude.ai* — autoryzacja przez panel claude.ai
            QDesktopServices.openUrl(QUrl("https://claude.ai/settings/connectors"))
            QMessageBox.information(
                self, tr('dlg_mcp_browser_opened_title'),
                tr('dlg_mcp_browser_opened_msg').format(name=srv.name)
            )
            return

        # Serwery OAuth (Notion, Sentry, GitHub OAuth) — autoryzacja w terminalu Claude Code
        target_dir = self._working_dir or Path.home()
        QMessageBox.information(
            self, tr('dlg_mcp_oauth_title'),
            tr('dlg_mcp_oauth_msg').format(name=srv.name, dir=target_dir)
        )

    # ---------- Akcje: test połączenia ----------

    def _test_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mcp_select_to_test'))
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
            QMessageBox.warning(self, tr('dlg_mcp_test_error_title'), str(exc))
            return
        finally:
            self.unsetCursor()

        if updated is None:
            QMessageBox.warning(
                self, tr('dlg_not_found_title'),
                tr('dlg_mcp_server_gone').format(name=srv.name)
            )
            self._populate_list()
            return

        icon, color, status_label = _mcp_status_badge(updated.status)
        QMessageBox.information(
            self, tr('dlg_mcp_test_result_title'),
            tr('dlg_mcp_test_result_msg').format(
                icon=icon, name=updated.name, status=status_label,
                ms=elapsed_ms, raw=updated.status_text or tr('dlg_mcp_raw_status_none')
            )
        )
        self._populate_list()

    # ---------- Akcje: edycja ----------

    def _edit_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mcp_select_to_edit'))
            return
        if srv.managed:
            QMessageBox.information(
                self, tr('dlg_mcp_managed_title'),
                tr('dlg_mcp_managed_edit_msg').format(name=srv.name)
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
            QMessageBox.warning(self, tr('dlg_edit_error_title'), str(exc))
            return

        QMessageBox.information(
            self, tr('dlg_saved_title'),
            tr('dlg_mcp_updated_msg').format(name=dlg.final_name)
        )
        self._populate_list()

    # ---------- Akcje: usuwanie ----------

    def _delete_selected(self):
        srv = self._selected_server()
        if srv is None:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mcp_select_to_delete'))
            return

        if srv.managed:
            QMessageBox.information(
                self, tr('dlg_mcp_managed_title'),
                tr('dlg_mcp_managed_delete_msg').format(name=srv.name)
            )
            return

        reply = QMessageBox.question(
            self, tr('dlg_confirm_delete_title'),
            tr('dlg_mcp_confirm_delete').format(name=srv.name, scope=_mcp_scope_label(srv.scope)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            scope = srv.scope if srv.scope in ("user", "local") else None
            self.manager.remove(srv.name, scope=scope)
        except McpError as exc:
            QMessageBox.warning(self, tr('dlg_delete_error_title'), str(exc))
            return

        QMessageBox.information(self, tr('dlg_removed_title'), tr('dlg_mcp_deleted_msg').format(name=srv.name))
        self._populate_list()


class _McpTemplatePickerDialog(QDialog):
    """Wybór jednego z wbudowanych szablonów MCP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_mcptpl_title'))
        self.setMinimumSize(640, 460)
        self.selected_template: Optional[McpTemplate] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(tr('dlg_mcptpl_header'))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        desc = QLabel(tr('dlg_mcptpl_desc'))
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
        cancel_btn = QPushButton(tr('dlg_cancel'))
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        next_btn = QPushButton(tr('dlg_next'))
        next_btn.setDefault(True)
        next_btn.clicked.connect(self._accept)
        bottom.addWidget(next_btn)
        layout.addLayout(bottom)

    def _accept(self):
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.warning(self, tr('dlg_no_selection_title'), tr('dlg_mcptpl_select'))
            return
        self.selected_template = item.data(Qt.UserRole)
        self.accept()


class _McpTemplateConfigDialog(QDialog):
    """Dynamicznie generowany formularz na podstawie szablonu MCP."""

    def __init__(self, parent, template: McpTemplate, default_scope: str, scope_locked: bool):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_mcpcfg_title').format(title=template.title))
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
        form.addRow(tr('dlg_mcpcfg_server_name'), name_input)

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
            inp.setPlaceholderText(tr('dlg_mcpcfg_optional_prefix').format(label=label))
            self._inputs[f"envopt::{key}"] = inp
            form.addRow(tr('dlg_mcpcfg_env_opt_label').format(key=key), inp)

        # headers_required
        for key, label in self.template.headers_required:
            # Etykieta to wzorzec — wartość podstawiamy do {VAR}
            # Na razie pole jest dla wartości tokenu (obsługa GitHub: TOKEN)
            # Pomijamy bo i tak idzie przez env_required (TOKEN dla GitHub)
            pass

        # Scope
        self.scope_combo = QComboBox()
        self.scope_combo.addItem(tr('dlg_mcpcfg_scope_user'), "user")
        self.scope_combo.addItem(tr('dlg_mcpcfg_scope_local'), "local")
        idx = 0 if self._default_scope == "user" else 1
        self.scope_combo.setCurrentIndex(idx)
        self.scope_combo.setEnabled(not self._scope_locked)
        form.addRow(tr('dlg_mcpcfg_scope_label'), self.scope_combo)

        layout.addLayout(form)

        if self.template.homepage:
            home = QLabel(f"<a href='{self.template.homepage}' style='color:#7dd3fc;'>{tr('dlg_mcpcfg_docs')}</a>")
            home.setTextFormat(Qt.RichText)
            home.setOpenExternalLinks(True)
            layout.addWidget(home)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel = QPushButton(tr('dlg_cancel'))
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        install = QPushButton(tr('dlg_mcpcfg_install'))
        install.setDefault(True)
        install.setStyleSheet("QPushButton { color: #22c55e; }")
        install.clicked.connect(self._validate_and_accept)
        bottom.addWidget(install)
        layout.addLayout(bottom)

    def _validate_and_accept(self):
        name = self._inputs["__name__"].text().strip()
        if not name:
            QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_mcpcfg_give_server_name'))
            return
        # Walidacja wymaganych pól
        for key, label in self.template.args_required:
            if not self._inputs[f"arg::{key}"].text().strip():
                QMessageBox.warning(self, tr('dlg_no_data_title'), tr('dlg_mcpcfg_field_required').format(label=label))
                return
        for key, label in self.template.env_required:
            if not self._inputs[f"env::{key}"].text().strip():
                QMessageBox.warning(self, tr('dlg_no_data_title'), tr('dlg_mcpcfg_field_required').format(label=key))
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
            raise McpError(tr('dlg_mcpcfg_unknown_transport').format(transport=tpl.transport))


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
        title = tr('dlg_mcpman_edit_title').format(name=edit_server.name) if self._is_edit else tr('dlg_mcpman_add_title')
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

        header_text = tr('dlg_mcpman_edit_header') if self._is_edit else tr('dlg_mcpman_add_header')
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        if self._is_edit:
            note = QLabel(tr('dlg_mcpman_edit_note'))
            note.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            note.setWordWrap(True)
            layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr('dlg_mcpman_name_placeholder'))
        form.addRow(tr('dlg_mcpman_name_label'), self.name_input)

        self.transport_combo = QComboBox()
        self.transport_combo.addItem(tr('dlg_mcpman_transport_stdio'), "stdio")
        self.transport_combo.addItem(tr('dlg_mcpman_transport_http'), "http")
        self.transport_combo.addItem(tr('dlg_mcpman_transport_sse'), "sse")
        self.transport_combo.currentIndexChanged.connect(self._on_transport_change)
        form.addRow(tr('dlg_mcpman_transport_label'), self.transport_combo)

        # stdio: command + args
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("npx")
        form.addRow(tr('dlg_mcpman_command_label'), self.command_input)

        self.args_input = QLineEdit()
        self.args_input.setPlaceholderText(tr('dlg_mcpman_args_placeholder'))
        form.addRow(tr('dlg_mcpman_args_label'), self.args_input)

        # http/sse: url
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/mcp")
        form.addRow(tr('dlg_mcpman_url_label'), self.url_input)

        # env (multi-line: KEY=value)
        self.env_input = QPlainTextEdit()
        self.env_input.setPlaceholderText(tr('dlg_mcpman_env_placeholder'))
        self.env_input.setMaximumHeight(70)
        self.env_input.setStyleSheet(
            "QPlainTextEdit { background-color: #4a1a3a; color: #ffffff; "
            "border: 1px solid #6a2a5a; border-radius: 4px; padding: 4px; }"
        )
        form.addRow(tr('dlg_mcpman_env_label'), self.env_input)

        # headers (multi-line: Key: value)
        self.headers_input = QPlainTextEdit()
        self.headers_input.setPlaceholderText(tr('dlg_mcpman_headers_placeholder'))
        self.headers_input.setMaximumHeight(70)
        self.headers_input.setStyleSheet(self.env_input.styleSheet())
        form.addRow(tr('dlg_mcpman_headers_label'), self.headers_input)

        # scope
        self.scope_combo = QComboBox()
        self.scope_combo.addItem(tr('dlg_mcpcfg_scope_user'), "user")
        self.scope_combo.addItem(tr('dlg_mcpcfg_scope_local'), "local")
        self.scope_combo.setCurrentIndex(0 if self._default_scope == "user" else 1)
        self.scope_combo.setEnabled(not self._scope_locked)
        form.addRow(tr('dlg_mcpman_scope_label'), self.scope_combo)

        layout.addLayout(form)

        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel = QPushButton(tr('dlg_cancel'))
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        ok_label = tr('dlg_mcpman_ok_save') if self._is_edit else tr('dlg_mcpman_ok_add')
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
        self.name_input.setToolTip(tr('dlg_mcpman_name_immutable_tooltip'))

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
            QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_mcpman_give_server_name'))
            return
        transport = self.transport_combo.currentData()
        if transport == "stdio":
            if not self.command_input.text().strip():
                QMessageBox.warning(self, tr('dlg_mcpman_no_command_title'), tr('dlg_mcpman_give_command'))
                return
        else:
            url = self.url_input.text().strip()
            if not url.startswith(("http://", "https://")):
                QMessageBox.warning(self, tr('dlg_mcpman_bad_url_title'), tr('dlg_mcpman_bad_url_msg'))
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
        self.setWindowTitle(tr('dlg_mcpjson_title'))
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

        header = QLabel(tr('dlg_mcpjson_header'))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        desc = QLabel(tr('dlg_mcpjson_desc'))
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet("color: #cccccc; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr('dlg_mcpjson_name_placeholder'))
        form.addRow(tr('dlg_mcpjson_name_label'), self.name_input)

        self.scope_combo = QComboBox()
        self.scope_combo.addItem(tr('dlg_mcpcfg_scope_user'), "user")
        self.scope_combo.addItem(tr('dlg_mcpcfg_scope_local'), "local")
        self.scope_combo.setCurrentIndex(0 if self._default_scope == "user" else 1)
        self.scope_combo.setEnabled(not self._scope_locked)
        form.addRow(tr('dlg_mcpjson_scope_label'), self.scope_combo)
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
        cancel = QPushButton(tr('dlg_cancel'))
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        ok = QPushButton(tr('dlg_mcpjson_ok_add'))
        ok.setDefault(True)
        ok.setStyleSheet("QPushButton { color: #22c55e; }")
        ok.clicked.connect(self._validate_and_accept)
        bottom.addWidget(ok)
        layout.addLayout(bottom)

    def _validate_and_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, tr('dlg_no_name_title'), tr('dlg_mcpjson_give_server_name'))
            return
        text = self.json_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, tr('dlg_mcpjson_no_json_title'), tr('dlg_mcpjson_paste_json'))
            return
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, tr('dlg_mcpjson_bad_json_title'), tr('dlg_mcpjson_bad_json_msg').format(error=exc))
            return
        self.final_name = name
        self.final_scope = self.scope_combo.currentData()
        self.json_text = text
        self.accept()


class UpdateAvailableDialog(QDialog):
    """Okno „dostępna nowa wersja" — pobiera, weryfikuje i otwiera instalator (M3).

    Współpracuje z core.update_manager.UpdateManager przez jego sygnały
    (download_progress/finished/failed). Samo pobieranie idzie w wątku tła
    managera, więc to okno tylko pokazuje postęp i nie blokuje.
    """

    def __init__(self, update_manager, info, current_version, parent=None):
        super().__init__(parent)
        self.manager = update_manager
        self.info = info
        self.setWindowTitle(tr('dlg_update_title'))
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(tr('dlg_update_new_version').format(version=info.version))
        tf = QFont()
        tf.setPointSize(13)
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        layout.addWidget(QLabel(tr('dlg_update_current_version').format(version=current_version)))

        if info.mandatory:
            layout.addWidget(QLabel(tr('dlg_update_mandatory')))

        if info.notes_url:
            notes_btn = QPushButton(tr('dlg_update_release_notes'))
            notes_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(info.notes_url)))
            layout.addWidget(notes_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.later_btn = QPushButton(tr('dlg_update_later'))
        self.later_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.later_btn)
        self.download_btn = QPushButton(tr('dlg_update_download_install'))
        self.download_btn.setDefault(True)
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn)
        layout.addLayout(btn_row)

        self.manager.download_progress.connect(self._on_progress)
        self.manager.download_finished.connect(self._on_finished)
        self.manager.download_failed.connect(self._on_failed)
        # Instalacja pobranej paczki (Etap 2) — wynik wraca jednym z tych sygnałów.
        self.manager.relaunch_ready.connect(self._on_relaunch_ready)
        self.manager.installer_opened.connect(self._on_installer_opened)
        self.manager.apply_failed.connect(self._on_apply_failed)

    def _start_download(self):
        self.download_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # nieokreślony do pierwszej porcji
        self.status_label.setText(tr('dlg_update_downloading'))
        self.manager.download_async(self.info)

    def _on_progress(self, downloaded, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(downloaded)
            self.status_label.setText(
                tr('dlg_update_downloading_progress').format(done=downloaded/1048576, total=total/1048576))
        else:
            self.progress.setRange(0, 0)
            self.status_label.setText(tr('dlg_update_downloading_simple').format(done=downloaded/1048576))

    def _on_finished(self, path):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        # macOS (.zip): aplikacja podmieni się sama i wystartuje ponownie.
        # Inne systemy: otworzy się instalator. Decyzję podejmuje manager.
        if self.manager.can_self_replace(path):
            self.status_label.setText(tr('dlg_update_installing'))
        else:
            self.status_label.setText(tr('dlg_update_downloaded_opening'))
        self.manager.apply_update_async(path)

    def _on_relaunch_ready(self):
        """Podmiana przygotowana — zamknij aplikację, pomocnik ją wznowi.

        Windows: NIE pokazujemy blokującego okienka — pomocnik (cva-update.cmd)
        czeka, aż program zniknie, i dopiero wtedy podmienia pliki. Każda sekunda
        z otwartym modalem to sekunda z ZABLOKOWANYMI plikami → instalacja by się
        nie udała (to był właśnie błąd „zostaje na starej wersji"). Dlatego na
        Windows zamykamy NATYCHMIAST. Na macOS zostawiamy krótką informację —
        tam pomocnik też czeka na PID, więc modal niczego nie blokuje."""
        from PyQt5.QtWidgets import QApplication
        from core.platform_utils import is_windows
        self.status_label.setText(tr('dlg_update_relaunch_status'))
        if not is_windows():
            QMessageBox.information(
                self, tr('dlg_update_ready_title'),
                tr('dlg_update_ready_msg'))
        self.accept()
        # Zamknij całą aplikację — pomocnik czeka na to, by podmienić pliki.
        QApplication.instance().quit()

    def _on_installer_opened(self, path):
        QMessageBox.information(
            self, tr('dlg_update_downloaded_title'),
            tr('dlg_update_installer_opened_msg'))
        self.accept()

    def _on_apply_failed(self, msg):
        self.progress.setVisible(False)
        self.status_label.setText("")
        self.download_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        QMessageBox.warning(self, tr('dlg_update_error_title'), msg)

    def _on_failed(self, msg):
        self.progress.setVisible(False)
        self.status_label.setText("")
        self.download_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        QMessageBox.warning(self, tr('dlg_update_error_title'), msg)


class ClaudeSetupDialog(QDialog):
    """Kreator „dokończ instalację" — w systemie nie znaleziono Claude Code.

    Aplikacja jest „pilotem" nad CLI Claude Code: bez zainstalowanego `claude`
    terminal pokazuje tylko surowe „command not found" / „'claude' is not
    recognized", z którego laik nic nie wyczyta. Ten dialog tłumaczy prostym
    językiem, że potrzebny jest darmowy dodatek (Node.js + Claude Code),
    prowadzi przez instalację krok po kroku i linkuje pełną instrukcję online
    (publiczna podstrona /cva — bez logowania).

    Pokazywany przez MainWindow przy starcie, gdy CLI nie znaleziono; dostępny
    też ręcznie z menu Pomoc.
    """

    NPM_COMMAND = "npm install -g @anthropic-ai/claude-code"

    # Ścieżka znalezionego CLI po kliknięciu „Sprawdź ponownie" — MainWindow
    # podmienia claude_command bez restartu aplikacji.
    claude_found = pyqtSignal(str)
    # Użytkownik chce wpisać klucz Groq → MainWindow otwiera okno klucza.
    open_groq_settings = pyqtSignal()
    # Zmiana pola „nie przypominaj o dyktowaniu" → MainWindow zapisuje w configu.
    dictation_reminder_changed = pyqtSignal(bool)

    def __init__(self, parent=None, readiness=None, dictation_dismissed=False,
                 readiness_provider=None):
        super().__init__(parent)
        from core.platform_utils import os_key
        from config import install_guide_url
        self._os = os_key()
        # Język interfejsu decyduje o wersji instrukcji (-en dla angielskiego).
        self._guide_url = install_guide_url(self._os)
        self._dictation_guide_url = install_guide_url('dyktowanie')
        # Funkcja zwracająca świeży stan gotowości (3 punkty) — do „Sprawdź ponownie".
        self._provider = readiness_provider
        self._readiness = dict(readiness) if readiness else {}
        self._dictation_dismissed = bool(dictation_dismissed)

        self.setWindowTitle(tr('dlg_setup_check_title'))
        self.setMinimumWidth(600)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(tr('dlg_setup_check_title'))
        tf = QFont()
        tf.setPointSize(13)
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        intro = QLabel(tr('dlg_setup_check_intro'))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        layout.addWidget(intro)

        # Obszar treści (przewijalny — przy wielu brakujących punktach bywa wysoki).
        self._content = QVBoxLayout()
        self._content.setSpacing(12)
        content_host = QWidget()
        content_host.setLayout(self._content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content_host)
        layout.addWidget(scroll, 1)

        # ---- Przyciski ----
        btn_row = QHBoxLayout()
        guide_btn = QPushButton(tr('dlg_setup_full_guide'))
        guide_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self._guide_url)))
        btn_row.addWidget(guide_btn)
        btn_row.addStretch()
        check_btn = QPushButton(tr('dlg_setup_check_again'))
        check_btn.clicked.connect(lambda: self._recheck())
        btn_row.addWidget(check_btn)
        close_btn = QPushButton(tr('dlg_close'))
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._render()

    # ---------- Budowa listy kontrolnej ----------

    def _clear_content(self):
        """Usuń wszystkie widgety/układy z obszaru treści (przed przerysowaniem)."""
        while self._content.count():
            item = self._content.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    sw = sub.takeAt(0).widget()
                    if sw is not None:
                        sw.deleteLater()

    def _render(self):
        """Przerysuj listę kontrolną z aktualnego stanu gotowości."""
        self._clear_content()
        r = self._readiness
        claude_ok = bool(r.get('claude_installed'))
        login_ok = bool(r.get('claude_logged_in'))
        dict_ok = bool(r.get('dictation'))

        self._content.addWidget(self._status_row(tr('dlg_setup_item_claude'), claude_ok))
        self._content.addWidget(self._status_row(tr('dlg_setup_item_login'), login_ok))
        self._content.addWidget(self._status_row(tr('dlg_setup_item_dictation'), dict_ok))

        if claude_ok and login_ok and dict_ok:
            done = QLabel(tr('dlg_setup_all_ready'))
            done.setWordWrap(True)
            self._content.addWidget(done)

        # Szczegóły „co zrobić" pokazujemy TYLKO przy brakujących punktach.
        if not claude_ok:
            self._content.addWidget(self._claude_install_box())
        elif not login_ok:
            # Zainstalowany, ale niezalogowany — wystarczy sam krok logowania.
            self._content.addWidget(self._login_box())
        if not dict_ok:
            self._content.addWidget(self._dictation_box())

        self._content.addStretch()

    def _status_row(self, label_text, ok):
        """Wiersz: nazwa punktu + chip „gotowe / do zrobienia"."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        name = QLabel(label_text)
        nf = QFont()
        nf.setBold(True)
        name.setFont(nf)
        h.addWidget(name)
        h.addStretch()
        status = QLabel(tr('dlg_setup_ready') if ok else tr('dlg_setup_missing'))
        status.setStyleSheet("color:#16a34a;font-weight:700;" if ok
                             else "color:#dc2626;font-weight:700;")
        h.addWidget(status)
        return row

    def _rich_label(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        return lbl

    def _claude_install_box(self):
        """Pełna instrukcja instalacji (Node + npm + logowanie) — gdy brak CLI."""
        box = QGroupBox(tr('dlg_setup_item_claude'))
        v = QVBoxLayout(box)
        v.addWidget(self._rich_label(tr('dlg_setup_intro')))
        # Krok 1 — Node.js
        v.addWidget(self._rich_label("<b>%s</b>" % tr('dlg_setup_step1_title')))
        v.addWidget(self._rich_label(tr('dlg_setup_step1_label')))
        if self._os == "windows":
            v.addWidget(self._rich_label(tr('dlg_setup_step1_warn')))
        node_btn = QPushButton(tr('dlg_setup_node_btn'))
        node_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://nodejs.org/")))
        v.addWidget(node_btn)
        # Krok 2 — npm install
        v.addWidget(self._rich_label("<b>%s</b>" % tr('dlg_setup_step2_title')))
        v.addWidget(self._rich_label(tr('dlg_setup_step2_label')))
        cmd_row = QHBoxLayout()
        self.cmd_field = QLineEdit(self.NPM_COMMAND)
        self.cmd_field.setReadOnly(True)
        cmd_row.addWidget(self.cmd_field)
        self.copy_btn = QPushButton(tr('dlg_setup_copy'))
        self.copy_btn.clicked.connect(self._copy_command)
        cmd_row.addWidget(self.copy_btn)
        v.addLayout(cmd_row)
        # Krok 3 — logowanie (część instalacji)
        v.addWidget(self._rich_label("<b>%s</b>" % tr('dlg_setup_step3_title')))
        v.addWidget(self._rich_label(tr('dlg_setup_step3_label')))
        return box

    def _login_box(self):
        """Sam krok logowania — gdy CLI jest, ale użytkownik się nie zalogował."""
        box = QGroupBox(tr('dlg_setup_item_login'))
        v = QVBoxLayout(box)
        v.addWidget(self._rich_label("<b>%s</b>" % tr('dlg_setup_step3_title')))
        v.addWidget(self._rich_label(tr('dlg_setup_step3_label')))
        return box

    def _dictation_box(self):
        """Sekcja dyktowania: link do instrukcji Groq + otwórz Ustawienia + „nie przypominaj"."""
        box = QGroupBox(tr('dlg_setup_item_dictation'))
        v = QVBoxLayout(box)
        v.addWidget(self._rich_label(tr('dlg_setup_dictation_intro')))
        row = QHBoxLayout()
        groq_btn = QPushButton(tr('dlg_setup_groq_btn'))
        groq_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self._dictation_guide_url)))
        row.addWidget(groq_btn)
        settings_btn = QPushButton(tr('dlg_setup_settings_btn'))
        settings_btn.clicked.connect(self._open_settings)
        row.addWidget(settings_btn)
        v.addLayout(row)
        dismiss = QCheckBox(tr('dlg_setup_dictation_dismiss'))
        dismiss.setChecked(self._dictation_dismissed)
        dismiss.toggled.connect(self._on_dismiss_toggled)
        v.addWidget(dismiss)
        return box

    def _open_settings(self):
        """Otwórz okno klucza Groq w MainWindow, potem odśwież stan."""
        self.open_groq_settings.emit()
        self._recheck(silent=True)

    def _on_dismiss_toggled(self, checked):
        self._dictation_dismissed = bool(checked)
        self.dictation_reminder_changed.emit(self._dictation_dismissed)

    def _copy_command(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.NPM_COMMAND)
        self.copy_btn.setText(tr('dlg_setup_copied'))
        QTimer.singleShot(2000, lambda: self.copy_btn.setText(tr('dlg_setup_copy')))

    def _recheck(self, silent=False):
        """Sprawdź gotowość ponownie (3 punkty) i przerysuj listę kontrolną.

        Świeży stan bierze z funkcji `readiness_provider` przekazanej przez
        MainWindow (to samo źródło, co przy starcie). Gdy CLI właśnie się
        pojawiło — przekazuje jego ścieżkę do MainWindow (podmiana komendy bez
        restartu). `silent=True` po wpisaniu klucza Groq (bez okienek)."""
        if self._provider is not None:
            try:
                fresh = self._provider()
                if fresh:
                    self._readiness = dict(fresh)
            except Exception:
                pass
        r = self._readiness
        path = r.get('claude_command_path')
        if r.get('claude_installed') and path:
            self.claude_found.emit(str(path))
        self._render()
        if not silent:
            all_ok = (r.get('claude_installed') and r.get('claude_logged_in')
                      and r.get('dictation'))
            if all_ok:
                QMessageBox.information(self, tr('dlg_setup_found_title'),
                                        tr('dlg_setup_all_ready'))
            elif not r.get('claude_installed'):
                QMessageBox.information(self, tr('dlg_setup_not_found_title'),
                                        tr('dlg_setup_not_found_msg'))
