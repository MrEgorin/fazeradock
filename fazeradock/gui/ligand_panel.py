"""
FazeraDock – Ligand Preparation Panel
======================================

Provides the *Ligand* tab for loading single ligands, multi-molecule SDF
libraries, or multiple individual ligand files and preparing them for docking.
"""

from __future__ import annotations

import os
import traceback
from typing import List, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Worker thread for ligand preparation
# ---------------------------------------------------------------------------
class _LigandPrepWorker(QThread):
    """Background worker for ligand preparation."""

    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(list)  # list of LigandPrepResult
    error = pyqtSignal(str)

    def __init__(
        self,
        mode: str,  # "single" | "library" | "multiple"
        paths: List[str],
        add_h: bool,
        gen_3d: bool,
        parent: Optional[QThread] = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.paths = paths
        self.add_h = add_h
        self.gen_3d = gen_3d

    def run(self) -> None:  # noqa: D401
        try:
            from fazeradock.ligand_prep import (
                prepare_ligand,
                prepare_ligand_batch,
                prepare_ligand_library,
            )

            results: list = []

            if self.mode == "single":
                self.log.emit(f"Preparing single ligand: {self.paths[0]}")
                res = prepare_ligand(
                    self.paths[0],
                    add_hydrogens=self.add_h,
                    gen_3d=self.gen_3d,
                )
                results = [res]

            elif self.mode == "library":
                self.log.emit(f"Preparing ligand library: {self.paths[0]}")
                results = prepare_ligand_library(
                    self.paths[0],
                    add_hydrogens=self.add_h,
                    gen_3d=self.gen_3d,
                )

            elif self.mode == "multiple":
                self.log.emit(f"Preparing {len(self.paths)} ligand file(s) …")
                results = prepare_ligand_batch(
                    self.paths,
                    add_hydrogens=self.add_h,
                    gen_3d=self.gen_3d,
                )

            self.log.emit(f"Prepared {len(results)} ligand(s) successfully.")
            self.finished.emit(results)

        except Exception as exc:
            tb = traceback.format_exc()
            self.log.emit(f"ERROR: {exc}")
            self.error.emit(f"{exc}\n\n{tb}")


# ---------------------------------------------------------------------------
# Ligand panel widget
# ---------------------------------------------------------------------------
class LigandPanel(QWidget):
    """Widget for loading and preparing ligands."""

    ligands_prepared = pyqtSignal(list)  # list of pdbqt paths

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._prepared_paths: List[str] = []
        self._worker: Optional[_LigandPrepWorker] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # Heading
        heading = QLabel("Ligand Preparation")
        heading.setProperty("cssClass", "heading")
        main.addWidget(heading)

        # --- Mode selection ---
        mode_group = QGroupBox("Ligand Source")
        mode_lay = QVBoxLayout(mode_group)

        self._rb_single = QRadioButton("Single Ligand")
        self._rb_single.setChecked(True)
        self._rb_library = QRadioButton("Ligand Library (multi-molecule SDF)")
        self._rb_multiple = QRadioButton("Multiple Individual Files")
        mode_lay.addWidget(self._rb_single)
        mode_lay.addWidget(self._rb_library)
        mode_lay.addWidget(self._rb_multiple)

        self._rb_single.toggled.connect(self._on_mode_changed)
        self._rb_library.toggled.connect(self._on_mode_changed)
        self._rb_multiple.toggled.connect(self._on_mode_changed)

        main.addWidget(mode_group)

        # --- Single file ---
        self._grp_single = QGroupBox("Single Ligand File")
        single_lay = QHBoxLayout(self._grp_single)
        self._btn_single = QPushButton("Browse …")
        self._btn_single.clicked.connect(self._browse_single)
        single_lay.addWidget(self._btn_single)
        self._le_single = QLineEdit()
        self._le_single.setReadOnly(True)
        self._le_single.setPlaceholderText("Select .sdf, .mol2, .mol, .pdb, .pdbqt")
        single_lay.addWidget(self._le_single)
        main.addWidget(self._grp_single)

        # --- Library file ---
        self._grp_library = QGroupBox("SDF Library File")
        lib_lay = QHBoxLayout(self._grp_library)
        self._btn_library = QPushButton("Browse …")
        self._btn_library.clicked.connect(self._browse_library)
        lib_lay.addWidget(self._btn_library)
        self._le_library = QLineEdit()
        self._le_library.setReadOnly(True)
        self._le_library.setPlaceholderText("Select multi-molecule .sdf file")
        lib_lay.addWidget(self._le_library)
        self._grp_library.setVisible(False)
        main.addWidget(self._grp_library)

        # --- Multiple files ---
        self._grp_multi = QGroupBox("Multiple Ligand Files")
        multi_lay = QVBoxLayout(self._grp_multi)
        btn_row = QHBoxLayout()
        self._btn_add_multi = QPushButton("Add Files …")
        self._btn_add_multi.clicked.connect(self._browse_multiple)
        btn_row.addWidget(self._btn_add_multi)
        self._btn_rm_multi = QPushButton("Remove Selected")
        self._btn_rm_multi.setProperty("cssClass", "danger")
        self._btn_rm_multi.clicked.connect(self._remove_selected_files)
        btn_row.addWidget(self._btn_rm_multi)
        btn_row.addStretch()
        multi_lay.addLayout(btn_row)
        self._list_multi = QListWidget()
        self._list_multi.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list_multi.setMaximumHeight(120)
        multi_lay.addWidget(self._list_multi)
        self._grp_multi.setVisible(False)
        main.addWidget(self._grp_multi)

        # --- Options ---
        opts_group = QGroupBox("Preparation Options")
        opts_lay = QVBoxLayout(opts_group)
        self._chk_addh = QCheckBox("Add hydrogens")
        self._chk_addh.setChecked(True)
        opts_lay.addWidget(self._chk_addh)
        self._chk_gen3d = QCheckBox("Generate 3D coordinates (for SMILES / 2D structures)")
        opts_lay.addWidget(self._chk_gen3d)
        main.addWidget(opts_group)

        # --- Prepare button ---
        self._btn_prepare = QPushButton("  Prepare Ligand(s)  ")
        self._btn_prepare.setProperty("cssClass", "accent")
        self._btn_prepare.clicked.connect(self._run_preparation)
        main.addWidget(self._btn_prepare, alignment=Qt.AlignLeft)

        # --- Results table ---
        tbl_group = QGroupBox("Prepared Ligands")
        tbl_lay = QVBoxLayout(tbl_group)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Atoms", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setMaximumHeight(180)
        tbl_lay.addWidget(self._table)
        main.addWidget(tbl_group)

        # --- Log ---
        log_group = QGroupBox("Preparation Log")
        log_lay = QVBoxLayout(log_group)
        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        self._txt_log.setMaximumHeight(120)
        log_lay.addWidget(self._txt_log)
        main.addWidget(log_group)

        main.addStretch()

    # ------------------------------------------------------------------
    # Mode toggling
    # ------------------------------------------------------------------
    def _on_mode_changed(self) -> None:
        self._grp_single.setVisible(self._rb_single.isChecked())
        self._grp_library.setVisible(self._rb_library.isChecked())
        self._grp_multi.setVisible(self._rb_multiple.isChecked())

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------
    def _browse_single(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Ligand File",
            "",
            "Ligand files (*.sdf *.mol2 *.mol *.pdb *.pdbqt);;All files (*)",
        )
        if path:
            self._le_single.setText(os.path.normpath(path))

    def _browse_library(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SDF Library",
            "",
            "SDF files (*.sdf);;All files (*)",
        )
        if path:
            self._le_library.setText(os.path.normpath(path))

    def _browse_multiple(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Ligand Files",
            "",
            "Ligand files (*.sdf *.mol2 *.mol *.pdb *.pdbqt);;All files (*)",
        )
        for p in paths:
            norm = os.path.normpath(p)
            # Avoid duplicates
            existing = [
                self._list_multi.item(i).text()
                for i in range(self._list_multi.count())
            ]
            if norm not in existing:
                self._list_multi.addItem(QListWidgetItem(norm))

    def _remove_selected_files(self) -> None:
        for item in self._list_multi.selectedItems():
            self._list_multi.takeItem(self._list_multi.row(item))

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------
    def _current_mode_and_paths(self) -> tuple[str, list[str]]:
        if self._rb_single.isChecked():
            p = self._le_single.text().strip()
            return ("single", [p] if p else [])
        if self._rb_library.isChecked():
            p = self._le_library.text().strip()
            return ("library", [p] if p else [])
        # multiple
        paths = [
            self._list_multi.item(i).text()
            for i in range(self._list_multi.count())
        ]
        return ("multiple", paths)

    def _run_preparation(self) -> None:
        mode, paths = self._current_mode_and_paths()
        if not paths:
            QMessageBox.warning(self, "No Files", "Please select at least one ligand file.")
            return

        self._btn_prepare.setEnabled(False)
        self._txt_log.clear()
        self._table.setRowCount(0)

        self._worker = _LigandPrepWorker(
            mode=mode,
            paths=paths,
            add_h=self._chk_addh.isChecked(),
            gen_3d=self._chk_gen3d.isChecked(),
        )
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_prep_finished)
        self._worker.error.connect(self._on_prep_error)
        self._worker.start()

    def _append_log(self, msg: str) -> None:
        self._txt_log.append(msg)

    def _on_prep_finished(self, results: list) -> None:
        self._btn_prepare.setEnabled(True)
        self._prepared_paths.clear()
        self._table.setRowCount(0)

        for res in results:
            name = getattr(res, "name", "unknown")
            atoms = str(getattr(res, "num_atoms", "?"))
            status = getattr(res, "status", "OK")
            pdbqt = getattr(res, "pdbqt_path", "")
            if pdbqt:
                self._prepared_paths.append(pdbqt)

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(atoms))
            item_status = QTableWidgetItem(status)
            if "error" in str(status).lower():
                item_status.setForeground(Qt.red)
            else:
                item_status.setForeground(Qt.darkGreen)
            self._table.setItem(row, 2, item_status)

        if self._prepared_paths:
            self.ligands_prepared.emit(self._prepared_paths)
            self._append_log(
                f"✓  {len(self._prepared_paths)} ligand(s) prepared and ready for docking."
            )

    def _on_prep_error(self, msg: str) -> None:
        self._btn_prepare.setEnabled(True)
        QMessageBox.critical(self, "Ligand Preparation Error", msg)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def prepared_paths(self) -> List[str]:
        """Return list of prepared PDBQT paths."""
        return list(self._prepared_paths)

    def set_ligand_paths(self, paths: List[str]) -> None:
        """Programmatically set ligand paths (e.g. from project)."""
        if not paths:
            return
        if len(paths) == 1:
            self._rb_single.setChecked(True)
            self._le_single.setText(paths[0])
        else:
            self._rb_multiple.setChecked(True)
            self._list_multi.clear()
            for p in paths:
                self._list_multi.addItem(QListWidgetItem(p))
