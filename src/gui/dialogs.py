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
    QButtonGroup, QWidget, QSplitter, QFrame, QInputDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    MEMORY_PROJECTS_FILE, AGENTS_FILE, MEMORY_FILE_EXTENSIONS,
    DEFAULT_AGENTS, DEFAULT_MEMORY_PROJECTS
)


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
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #6a2a5a;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none;
                image: none;
            }
            QHeaderView::section {
                background-color: #4a1a3a;
                color: #ffffff;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
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

        # File dialog
        file_filter = "Pliki pamięci (*.md *.txt *.json);;Wszystkie pliki (*)"
        files, _ = QFileDialog.getOpenFileNames(
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

        # Folder dialog
        folder = QFileDialog.getExistingDirectory(
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


class AgentConfigDialog(QDialog):
    """Dialog for configuring a single agent."""

    def __init__(self, parent=None, agent: dict = None, memory_projects: list = None):
        super().__init__(parent)
        self.setWindowTitle("Edytuj agenta" if agent else "Nowy agent")
        self.setMinimumWidth(500)

        self.agent = agent or {}
        self.memory_projects = memory_projects or []
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel("Konfiguracja agenta")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        # Name
        self.name_input = QLineEdit(self.agent.get('name', ''))
        self.name_input.setPlaceholderText("np. CRM Development")
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        form.addRow("Nazwa agenta:", self.name_input)

        # Working directory
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit(self.agent.get('working_directory', str(Path.home())))
        self.dir_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        dir_layout.addWidget(self.dir_input)

        browse_btn = QPushButton("📁")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_btn)

        form.addRow("Katalog roboczy:", dir_layout)

        # Memory project - combo + button to add new
        memory_layout = QHBoxLayout()

        self.memory_combo = QComboBox()
        self.memory_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d0a1e;
                color: #ffffff;
                border: 1px solid #4a1a3a;
                border-radius: 4px;
                padding: 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d0a1e;
                color: #ffffff;
                selection-background-color: #6a2a5a;
            }
        """)
        memory_layout.addWidget(self.memory_combo, stretch=1)

        # Button to quickly add file as new memory project
        add_memory_btn = QPushButton("➕")
        add_memory_btn.setFixedWidth(40)
        add_memory_btn.setToolTip("Dodaj plik jako nowy projekt pamięci")
        add_memory_btn.clicked.connect(self._add_memory_file)
        memory_layout.addWidget(add_memory_btn)

        self._populate_memory_combo()

        # Select current project
        current_project_id = self.agent.get('memory_project_id')
        if current_project_id:
            for i in range(self.memory_combo.count()):
                if self.memory_combo.itemData(i) == current_project_id:
                    self.memory_combo.setCurrentIndex(i)
                    break

        form.addRow("Projekt pamięci:", memory_layout)

        layout.addLayout(form)

        # Checkboxes
        self.auto_start_checkbox = QCheckBox("Uruchamiaj automatycznie przy starcie aplikacji")
        self.auto_start_checkbox.setChecked(self.agent.get('auto_start', True))
        self.auto_start_checkbox.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.auto_start_checkbox)

        self.send_memory_checkbox = QCheckBox("Wczytaj pliki pamięci po starcie Claude Code")
        self.send_memory_checkbox.setChecked(self.agent.get('send_memory_on_start', True))
        self.send_memory_checkbox.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.send_memory_checkbox)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Zapisz")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet("QPushButton { color: #22c55e; font-weight: bold; }")
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _browse_directory(self):
        """Browse for working directory."""
        directory = QFileDialog.getExistingDirectory(
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

    def get_data(self) -> dict:
        """Return agent configuration."""
        return {
            'id': self.agent.get('id', str(uuid.uuid4())[:8]),
            'name': self.name_input.text().strip(),
            'working_directory': self.dir_input.text().strip(),
            'memory_project_id': self.memory_combo.currentData(),
            'auto_start': self.auto_start_checkbox.isChecked(),
            'send_memory_on_start': self.send_memory_checkbox.isChecked(),
        }

    def _populate_memory_combo(self):
        """Populate memory projects combo box."""
        self.memory_combo.clear()
        self.memory_combo.addItem("(Brak - nie wczytuj plików)", None)
        for project in self.memory_projects:
            self.memory_combo.addItem(
                f"📁 {project.get('name', 'Bez nazwy')}",
                project.get('id')
            )

    def _add_memory_file(self):
        """Quick add file as new memory project."""
        file_filter = "Pliki pamięci (*.md *.txt *.json);;Wszystkie pliki (*)"
        files, _ = QFileDialog.getOpenFileNames(
            self, "Wybierz pliki pamięci", str(Path.home()), file_filter
        )

        if not files:
            return

        # Create project name from first file's parent folder
        first_file = Path(files[0])
        project_name = first_file.parent.name or first_file.stem

        # Ask user for project name
        name, ok = QInputDialog.getText(
            self, "Nazwa projektu",
            "Podaj nazwę dla nowego projektu pamięci:",
            text=project_name
        )

        if not ok or not name.strip():
            return

        # Create new memory project
        new_project = {
            'id': str(uuid.uuid4())[:8],
            'name': name.strip(),
            'enabled': True,
            'files': [{'path': f, 'enabled': True} for f in files]
        }

        # Add to local list
        self.memory_projects.append(new_project)

        # Save to file
        self._save_memory_projects()

        # Refresh combo and select new project
        self._populate_memory_combo()

        # Select the new project
        for i in range(self.memory_combo.count()):
            if self.memory_combo.itemData(i) == new_project['id']:
                self.memory_combo.setCurrentIndex(i)
                break

        QMessageBox.information(
            self, "Projekt utworzony",
            f"Utworzono projekt \"{name.strip()}\" z {len(files)} plikami."
        )

    def _save_memory_projects(self):
        """Save memory projects to file."""
        try:
            with open(MEMORY_PROJECTS_FILE, 'w') as f:
                json.dump(self.memory_projects, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Nie można zapisać projektów pamięci: {e}")


class AgentsManagerDialog(QDialog):
    """Dialog for managing all agents."""

    def __init__(self, parent=None, agents: list = None, memory_projects: list = None):
        super().__init__(parent)
        self.setWindowTitle("Zarządzaj agentami")
        self.setMinimumSize(600, 450)

        self.agents = [a.copy() for a in (agents or [])]
        self.memory_projects = memory_projects or []
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
        """Populate list with agents."""
        self.list_widget.clear()

        for agent in self.agents:
            # Find memory project name
            memory_name = "(Brak)"
            if agent.get('memory_project_id'):
                for project in self.memory_projects:
                    if project.get('id') == agent.get('memory_project_id'):
                        memory_name = project.get('name', 'Bez nazwy')
                        break

            auto_icon = "🟢" if agent.get('auto_start', True) else "⚪"
            item_text = f"{auto_icon} {agent.get('name', 'Bez nazwy')}\n   📁 {memory_name}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, agent)
            self.list_widget.addItem(item)

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

    def _add_agent(self):
        """Add new agent."""
        dialog = AgentConfigDialog(self, memory_projects=self.memory_projects)
        if dialog.exec_() == QDialog.Accepted:
            agent_data = dialog.get_data()
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
