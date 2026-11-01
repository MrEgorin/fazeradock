"""
FazeraDock – Project Manager Dialog
===================================

Provides a dialog to browse, open, and manage saved docking project configurations (.json).
Allows returning to previous experiments, proteins, and grid box setups.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import DockingProject, list_projects, load_project


class ProjectManagerDialog(QDialog):
    """Dialog for selecting and loading saved FazeraDock projects."""

    def __init__(self, projects_dir: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FazeraDock – Project Manager")
        self.resize(720, 480)

        self._projects_dir = projects_dir
        self._selected_project_path: Optional[str] = None
        self._all_projects: List[dict] = []

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Search filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter Projects:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search by project name or protein...")
        self._filter_edit.textChanged.connect(self._filter_table)
        search_layout.addWidget(self._filter_edit)
        layout.addLayout(search_layout)

        # Projects Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Project Name", "Date Created", "Protein", "Notes"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.itemDoubleClicked.connect(self._on_open_selected)
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_open = QPushButton("Open Selected Project")
        self._btn_open.setStyleSheet("font-weight: bold; background-color: #1565C0; color: white; padding: 6px 14px; border-radius: 4px;")
        self._btn_open.clicked.connect(self._on_open_selected)

        self._btn_delete = QPushButton("Delete Project")
        self._btn_delete.setStyleSheet("background-color: #D32F2F; color: white; padding: 6px 14px; border-radius: 4px;")
        self._btn_delete.clicked.connect(self._on_delete_selected)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self._btn_open)
        btn_layout.addWidget(self._btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_cancel)
        layout.addLayout(btn_layout)

    def _refresh_list(self) -> None:
        self._all_projects = list_projects(self._projects_dir)
        self._populate_table(self._all_projects)

    def _populate_table(self, projects: List[dict]) -> None:
        self._table.setRowCount(len(projects))
        for row, prj in enumerate(projects):
            it_name = QTableWidgetItem(prj.get("name", "Unnamed"))
            it_name.setData(Qt.UserRole, prj.get("path", ""))
            it_date = QTableWidgetItem(prj.get("created_at", ""))
            it_prot = QTableWidgetItem(os.path.basename(prj.get("protein_path", "")))
            it_notes = QTableWidgetItem(prj.get("notes", ""))

            self._table.setItem(row, 0, it_name)
            self._table.setItem(row, 1, it_date)
            self._table.setItem(row, 2, it_prot)
            self._table.setItem(row, 3, it_notes)

        if projects:
            self._table.selectRow(0)

    def _filter_table(self, text: str) -> None:
        filtered = [
            p for p in self._all_projects
            if text.lower() in p.get("name", "").lower()
            or text.lower() in p.get("protein_path", "").lower()
            or text.lower() in p.get("notes", "").lower()
        ]
        self._populate_table(filtered)

    def _on_open_selected(self) -> None:
        sel = self._table.selectedItems()
        if not sel:
            QMessageBox.information(self, "Select Project", "Please select a project to open.")
            return

        row = sel[0].row()
        item = self._table.item(row, 0)
        if item:
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                self._selected_project_path = path
                self.accept()

    def _on_delete_selected(self) -> None:
        sel = self._table.selectedItems()
        if not sel:
            return

        row = sel[0].row()
        item = self._table.item(row, 0)
        if not item:
            return

        path = item.data(Qt.UserRole)
        name = item.text()

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete project '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes and path and os.path.exists(path):
            try:
                os.remove(path)
                self._refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Delete Failed", f"Could not delete project:\n{e}")

    def get_selected_project_path(self) -> Optional[str]:
        return self._selected_project_path
