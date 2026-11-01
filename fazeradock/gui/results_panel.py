"""
FazeraDock – Docking Results & Visualization Panel
===================================================

Provides the *Results* tab for browsing docking output, sorting by binding affinity,
launching integrated 3D PyMOL visualization (with white background, highlighted residues,
and hydrogen bonds), generating 2D ligand-receptor interaction diagrams, exporting CSVs,
and generating reports.
"""

from __future__ import annotations

import csv
import os
import subprocess
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..docking_engine import DockingResult
from ..interaction_2d import generate_2d_interaction_diagram
from ..results_parser import (
    classify_interactions,
    extract_best_pose,
    find_interacting_residues,
    generate_results_report,
)
from ..screening import ScreeningResult
from ..visualization_3d import launch_pymol_interactive, visualize_docking_result


def _open_path_crossplatform(path: str) -> None:
    if not os.path.exists(path):
        return
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------------------
# 2D Diagram Preview Dialog
# ---------------------------------------------------------------------------
class _ImagePreviewDialog(QDialog):
    """Modal dialog displaying the 2D interaction diagram or 3D rendering."""

    def __init__(self, image_path: str, title: str = "Interaction Diagram", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 750)

        layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        if os.path.exists(image_path):
            pix = QPixmap(image_path)
            if not pix.isNull():
                lbl.setPixmap(pix.scaled(760, 680, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                lbl.setText("Unable to load rendered image.")
        else:
            lbl.setText(f"Image file not found:\n{image_path}")

        scroll.setWidget(lbl)
        layout.addWidget(scroll)

        btn_box = QHBoxLayout()
        btn_open = QPushButton("Open with Default Viewer")
        btn_open.clicked.connect(lambda: _open_path_crossplatform(image_path))
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_open)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)


# ---------------------------------------------------------------------------
# Results Panel
# ---------------------------------------------------------------------------
class ResultsPanel(QWidget):
    """Widget for inspecting, sorting, exporting and visualizing docking results."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._results_data: List[Dict[str, Any]] = []
        self._receptor_pdb: Optional[str] = None
        self._current_selected_row: int = -1

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Action Toolbar
        tb_box = QGroupBox("Actions & Visualization")
        tb_layout = QHBoxLayout(tb_box)

        self._btn_pymol_3d = QPushButton("🔬  View 3D in PyMOL")
        self._btn_pymol_3d.setStyleSheet("font-weight: bold; background-color: #0288D1; color: white; padding: 6px 14px; border-radius: 4px;")
        self._btn_pymol_3d.clicked.connect(self._on_view_3d_pymol)
        self._btn_pymol_3d.setEnabled(False)

        self._btn_render_2d = QPushButton("📊  Generate 2D Diagram")
        self._btn_render_2d.setStyleSheet("font-weight: bold; background-color: #00897B; color: white; padding: 6px 14px; border-radius: 4px;")
        self._btn_render_2d.clicked.connect(self._on_generate_2d_diagram)
        self._btn_render_2d.setEnabled(False)

        self._btn_report = QPushButton("📝  Generate Report")
        self._btn_report.clicked.connect(self._on_generate_report)
        self._btn_report.setEnabled(False)

        self._btn_export_csv = QPushButton("💾  Export CSV")
        self._btn_export_csv.clicked.connect(self._export_csv)
        self._btn_export_csv.setEnabled(False)

        self._btn_open_folder = QPushButton("📁  Open Results Folder")
        self._btn_open_folder.clicked.connect(self._open_results_folder)

        tb_layout.addWidget(self._btn_pymol_3d)
        tb_layout.addWidget(self._btn_render_2d)
        tb_layout.addWidget(self._btn_report)
        tb_layout.addWidget(self._btn_export_csv)
        tb_layout.addWidget(self._btn_open_folder)
        tb_layout.addStretch()
        main_layout.addWidget(tb_box)

        # 2. Main content splitter (Table on left, Details on right)
        splitter = QSplitter(Qt.Horizontal)

        # Left: Results table
        table_container = QWidget()
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_table_header = QLabel("<b>Docking Poses Ranked by Binding Energy</b> (kcal/mol)")
        tc_layout.addWidget(self._lbl_table_header)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Rank",
            "Ligand",
            "Receptor",
            "Best Affinity (kcal/mol)",
            "Mode 2",
            "Mode 3",
            "Output PDBQT",
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        tc_layout.addWidget(self._table)
        splitter.addWidget(table_container)

        # Right: Details & Interactions
        details_box = QGroupBox("Selected Pose Details & Interactions")
        details_layout = QVBoxLayout(details_box)
        self._txt_details = QTextEdit()
        self._txt_details.setReadOnly(True)
        self._txt_details.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        details_layout.addWidget(self._txt_details)
        splitter.addWidget(details_box)

        splitter.setSizes([600, 400])
        main_layout.addWidget(splitter, stretch=1)

    # ------------------------------------------------------------------
    # Data Population
    # ------------------------------------------------------------------
    def set_receptor_pdb(self, pdb_path: str) -> None:
        self._receptor_pdb = pdb_path

    def load_docking_result(self, result: object) -> None:
        """Populate table from DockingResult or ScreeningResult."""
        self._results_data.clear()
        self._table.setRowCount(0)

        if isinstance(result, DockingResult):
            if result.success and result.all_affinities:
                lig_name = Path(result.output_pdbqt).stem.replace("docked_", "")
                self._results_data.append({
                    "ligand": lig_name,
                    "receptor": Path(self._receptor_pdb).stem if self._receptor_pdb else "Receptor",
                    "best_affinity": result.best_affinity,
                    "affinities": result.all_affinities,
                    "output_pdbqt": result.output_pdbqt,
                    "log_path": result.log_path,
                })
        elif isinstance(result, ScreeningResult):
            for res in result.results:
                if res.success and res.all_affinities:
                    lig_name = Path(res.output_pdbqt).stem.replace("docked_", "")
                    rec_name = Path(res.output_pdbqt).parent.name
                    self._results_data.append({
                        "ligand": lig_name,
                        "receptor": rec_name,
                        "best_affinity": res.best_affinity,
                        "affinities": res.all_affinities,
                        "output_pdbqt": res.output_pdbqt,
                        "log_path": res.log_path,
                    })

        # Sort by affinity ascending (more negative = stronger binding)
        self._results_data.sort(key=lambda x: x["best_affinity"])

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._results_data))

        for row, item in enumerate(self._results_data):
            affs = item["affinities"]
            m1 = f"{affs[0]:.2f}" if len(affs) > 0 else "-"
            m2 = f"{affs[1]:.2f}" if len(affs) > 1 else "-"
            m3 = f"{affs[2]:.2f}" if len(affs) > 2 else "-"

            it_rank = QTableWidgetItem(str(row + 1))
            it_rank.setTextAlignment(Qt.AlignCenter)
            it_lig = QTableWidgetItem(item["ligand"])
            it_rec = QTableWidgetItem(item["receptor"])
            it_m1 = QTableWidgetItem(m1)
            it_m1.setTextAlignment(Qt.AlignCenter)
            it_m2 = QTableWidgetItem(m2)
            it_m2.setTextAlignment(Qt.AlignCenter)
            it_m3 = QTableWidgetItem(m3)
            it_m3.setTextAlignment(Qt.AlignCenter)
            it_path = QTableWidgetItem(os.path.basename(item["output_pdbqt"]))

            # Color styling based on affinity
            # Strong binding (<-8.0 kcal/mol) highlighted green
            best_aff = item["best_affinity"]
            if best_aff <= -8.0:
                bg = QColor("#E8F5E9")
                it_m1.setForeground(QColor("#2E7D32"))
                it_m1.setFont(QFont("Segoe UI", 9, QFont.Bold))
            elif best_aff <= -6.5:
                bg = QColor("#FFFDE7")
            else:
                bg = QColor("#FAFAFA")

            for it in (it_rank, it_lig, it_rec, it_m1, it_m2, it_m3, it_path):
                it.setBackground(bg)

            self._table.setItem(row, 0, it_rank)
            self._table.setItem(row, 1, it_lig)
            self._table.setItem(row, 2, it_rec)
            self._table.setItem(row, 3, it_m1)
            self._table.setItem(row, 4, it_m2)
            self._table.setItem(row, 5, it_m3)
            self._table.setItem(row, 6, it_path)

        self._table.setSortingEnabled(True)

        has_data = len(self._results_data) > 0
        self._btn_export_csv.setEnabled(has_data)
        if has_data:
            self._table.selectRow(0)

    # ------------------------------------------------------------------
    # Selection & Details
    # ------------------------------------------------------------------
    def _on_row_selected(self) -> None:
        sel = self._table.selectedItems()
        if not sel:
            self._current_selected_row = -1
            self._btn_pymol_3d.setEnabled(False)
            self._btn_render_2d.setEnabled(False)
            self._btn_report.setEnabled(False)
            self._txt_details.clear()
            return

        row = sel[0].row()
        self._current_selected_row = row
        self._btn_pymol_3d.setEnabled(True)
        self._btn_render_2d.setEnabled(True)
        self._btn_report.setEnabled(True)

        if row < len(self._results_data):
            item = self._results_data[row]
            self._update_details_panel(item)

    def _update_details_panel(self, item: Dict[str, Any]) -> None:
        pdbqt = item["output_pdbqt"]
        affs = item["affinities"]

        txt = []
        txt.append("==================================================")
        txt.append(f"  LIGAND: {item['ligand']}")
        txt.append(f"  RECEPTOR: {item['receptor']}")
        txt.append(f"  BEST BINDING ENERGY: {item['best_affinity']:.2f} kcal/mol")
        txt.append("==================================================")
        txt.append("\nBinding Modes:")
        for idx, aff in enumerate(affs):
            txt.append(f"  Mode {idx+1:>2}: {aff:>6.2f} kcal/mol")

        txt.append(f"\nPose File: {pdbqt}")

        # Compute interacting residues if receptor PDB is available
        rec_pdb = self._get_receptor_pdb_path(item)
        if rec_pdb and os.path.exists(rec_pdb) and os.path.exists(pdbqt):
            try:
                interactions = classify_interactions(rec_pdb, pdbqt, cutoff=4.0)
                txt.append(f"\nInteracting Residues Detected ({len(interactions)} contacts within 4.0 Å):")
                txt.append(f"{'Residue':<12} {'Type':<16} {'Distance':<10} {'Details'}")
                txt.append("-" * 55)

                for inter in interactions:
                    res_str = f"{inter['resname']} {inter['resseq']} (Ch {inter['chain']})"
                    t_str = inter['interaction_type'].replace("_", " ").title()
                    d_str = f"{inter['distance']:.2f} Å"
                    det = f"{inter['receptor_atom']} ↔ {inter['ligand_atom']}"
                    txt.append(f"{res_str:<12} {t_str:<16} {d_str:<10} {det}")

            except Exception as e:
                txt.append(f"\n[Note] Could not compute interaction residues: {e}")
        else:
            txt.append("\n[Note] Load the prepared receptor PDB to inspect residue contacts.")

        self._txt_details.setText("\n".join(txt))

    def _get_receptor_pdb_path(self, item: Dict[str, Any]) -> Optional[str]:
        if self._receptor_pdb and os.path.exists(self._receptor_pdb):
            return self._receptor_pdb
        # Try finding in parent directory of pdbqt
        parent_dir = Path(item["output_pdbqt"]).parent
        for cand in parent_dir.glob("*.pdb"):
            return str(cand)
        return None

    # ------------------------------------------------------------------
    # Visualization & Reports
    # ------------------------------------------------------------------
    def _on_view_3d_pymol(self) -> None:
        if self._current_selected_row < 0 or self._current_selected_row >= len(self._results_data):
            return

        item = self._results_data[self._current_selected_row]
        pdbqt = item["output_pdbqt"]
        rec_pdb = self._get_receptor_pdb_path(item)

        if not rec_pdb or not os.path.exists(rec_pdb):
            # Prompt user to locate receptor PDB
            f, _ = QFileDialog.getOpenFileName(self, "Select Receptor PDB for PyMOL", "", "PDB Files (*.pdb)")
            if f:
                rec_pdb = f
            else:
                return

        out_dir = str(Path(pdbqt).parent)

        try:
            # Generate publication-quality 3D session and image, and launch PyMOL
            res = visualize_docking_result(
                receptor_pdb=rec_pdb,
                ligand_pdbqt=pdbqt,
                output_dir=out_dir,
                session_name=f"{item['ligand']}_docked",
            )

            # Launch interactive PyMOL window with automatic white background and contacts
            launch_pymol_interactive(receptor_pdb=rec_pdb, ligand_pdbqt=pdbqt)

            if res.png_path and os.path.exists(res.png_path):
                dlg = _ImagePreviewDialog(res.png_path, title=f"3D Rendering – {item['ligand']}", parent=self)
                dlg.exec_()

        except Exception as exc:
            QMessageBox.critical(self, "PyMOL Visualization Error", f"Error launching PyMOL:\n{exc}\n{traceback.format_exc()}")

    def _on_generate_2d_diagram(self) -> None:
        if self._current_selected_row < 0 or self._current_selected_row >= len(self._results_data):
            return

        item = self._results_data[self._current_selected_row]
        pdbqt = item["output_pdbqt"]
        rec_pdb = self._get_receptor_pdb_path(item)

        if not rec_pdb or not os.path.exists(rec_pdb):
            f, _ = QFileDialog.getOpenFileName(self, "Select Receptor PDB for 2D Diagram", "", "PDB Files (*.pdb)")
            if f:
                rec_pdb = f
            else:
                return

        out_img = os.path.join(str(Path(pdbqt).parent), f"{item['ligand']}_2d_interactions.png")

        try:
            diag_path = generate_2d_interaction_diagram(
                receptor_pdb=rec_pdb,
                ligand_pdbqt=pdbqt,
                output_path=out_img,
                title=f"Interaction Diagram: {item['ligand']} ({item['best_affinity']:.2f} kcal/mol)",
            )
            if os.path.exists(diag_path):
                dlg = _ImagePreviewDialog(diag_path, title=f"2D Interaction Diagram – {item['ligand']}", parent=self)
                dlg.exec_()
            else:
                QMessageBox.warning(self, "Diagram Notice", "2D Diagram generated, but file could not be displayed.")

        except Exception as exc:
            QMessageBox.critical(self, "2D Diagram Error", f"Failed to generate 2D diagram:\n{exc}\n{traceback.format_exc()}")

    def _on_generate_report(self) -> None:
        if self._current_selected_row < 0 or self._current_selected_row >= len(self._results_data):
            return

        item = self._results_data[self._current_selected_row]
        pdbqt = item["output_pdbqt"]
        rec_pdb = self._get_receptor_pdb_path(item)
        out_dir = str(Path(pdbqt).parent)

        if not rec_pdb or not os.path.exists(rec_pdb):
            rec_pdb = pdbqt

        try:
            # Create a mock DockingResult for the report
            dock_res = DockingResult(
                output_pdbqt=pdbqt,
                log_path=item["log_path"],
                best_affinity=item["best_affinity"],
                all_affinities=item["affinities"],
                success=True,
                engine_used="AutoDock Vina 1.2.7",
            )
            rep_path = generate_results_report(dock_res, rec_pdb, out_dir)
            if os.path.exists(rep_path):
                _open_path_crossplatform(rep_path)
            else:
                QMessageBox.information(self, "Report", f"Report generated at:\n{rep_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Report Error", f"Failed to generate report:\n{exc}")

    def _export_csv(self) -> None:
        if not self._results_data:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results CSV",
            "docking_results_summary.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Rank", "Ligand", "Receptor", "Best Affinity (kcal/mol)", "Mode 1", "Mode 2", "Mode 3", "Output PDBQT"])
                for rank, it in enumerate(self._results_data, 1):
                    affs = it["affinities"]
                    writer.writerow([
                        rank,
                        it["ligand"],
                        it["receptor"],
                        f"{it['best_affinity']:.2f}",
                        f"{affs[0]:.2f}" if len(affs) > 0 else "",
                        f"{affs[1]:.2f}" if len(affs) > 1 else "",
                        f"{affs[2]:.2f}" if len(affs) > 2 else "",
                        it["output_pdbqt"],
                    ])
            QMessageBox.information(self, "Export Successful", f"Results exported to:\n{save_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not write CSV file:\n{exc}")

    def _open_results_folder(self) -> None:
        results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results"))
        if self._current_selected_row >= 0 and self._current_selected_row < len(self._results_data):
            pose_dir = str(Path(self._results_data[self._current_selected_row]["output_pdbqt"]).parent)
            if os.path.exists(pose_dir):
                results_dir = pose_dir

        if os.path.exists(results_dir):
            _open_path_crossplatform(results_dir)
        else:
            QMessageBox.warning(self, "Folder Not Found", f"Directory does not exist:\n{results_dir}")
