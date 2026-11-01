"""
FazeraDock – Main Application Window
====================================

Orchestrates the entire FazeraDock application. Integrates the 5 workflow panels:
Protein Preparation, Ligand Preparation, Grid Box Setup, Docking Execution, and Results/Visualization.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_DIR, PROJECTS_DIR, DockingProject, load_project, save_project
from ..gpu_detect import detect_gpu, GPUInfo
from ..grid_manager import GridBox
from .docking_panel import DockingPanel
from .grid_panel import GridPanel
from .ligand_panel import LigandPanel
from .project_manager import ProjectManagerDialog
from .protein_panel import ProteinPanel
from .results_panel import ResultsPanel
from .styles import MAIN_STYLESHEET


def _open_path_crossplatform(path: str) -> None:
    if not os.path.exists(path):
        return
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class MainWindow(QMainWindow):
    """Main application window for FazeraDock."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FazeraDock v1.0.0 – Era of Accessible Molecular Docking | by Yehor Franchuk (@MrEgorin) & FAZENA")
        self.resize(1180, 800)
        self.setMinimumSize(960, 680)

        self._current_project: Optional[DockingProject] = None
        self._current_project_path: Optional[str] = None
        self._gpu_info: GPUInfo = detect_gpu()

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()
        self._connect_signals()

        self.setStyleSheet(MAIN_STYLESHEET)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File Menu
        file_menu = mb.addMenu("&File")

        act_new = QAction("&New Project", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._new_project)
        file_menu.addAction(act_new)

        act_open = QAction("&Open Project...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_project_dialog)
        file_menu.addAction(act_open)

        act_save = QAction("&Save Project", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._save_project)
        file_menu.addAction(act_save)

        act_save_as = QAction("Save Project &As...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._save_project_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Tools Menu
        tools_menu = mb.addMenu("&Tools")

        act_gpu = QAction("&Hardware & GPU Info...", self)
        act_gpu.triggered.connect(self._show_gpu_info)
        tools_menu.addAction(act_gpu)

        act_pymol = QAction("Launch &PyMOL Standalone", self)
        act_pymol.triggered.connect(self._launch_pymol)
        tools_menu.addAction(act_pymol)

        tools_menu.addSeparator()

        act_results_dir = QAction("Open &Results Directory", self)
        act_results_dir.triggered.connect(self._open_results_dir)
        tools_menu.addAction(act_results_dir)

        act_projects_dir = QAction("Open &Projects Directory", self)
        act_projects_dir.triggered.connect(self._open_projects_dir)
        tools_menu.addAction(act_projects_dir)

        # Help Menu
        help_menu = mb.addMenu("&Help")

        act_guide = QAction("&User Guide", self)
        act_guide.setShortcut("F1")
        act_guide.triggered.connect(self._show_user_guide)
        help_menu.addAction(act_guide)

        act_about = QAction("&About FazeraDock", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _build_tabs(self) -> None:
        self._tabs = QTabWidget(self)
        self._tabs.setDocumentMode(True)

        self._protein_panel = ProteinPanel(self)
        self._ligand_panel = LigandPanel(self)
        self._grid_panel = GridPanel(self)
        self._docking_panel = DockingPanel(self)
        self._results_panel = ResultsPanel(self)

        self._tabs.addTab(self._protein_panel, "1. Protein Preparation")
        self._tabs.addTab(self._ligand_panel, "2. Ligand Preparation")
        self._tabs.addTab(self._grid_panel, "3. Grid Box Setup")
        self._tabs.addTab(self._docking_panel, "4. Docking Execution")
        self._tabs.addTab(self._results_panel, "5. Results & Visualization")

        self.setCentralWidget(self._tabs)

    def _build_status_bar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)

        gpu_desc = self._gpu_info.gpu_name
        cuda_desc = "CUDA Enabled" if self._gpu_info.cuda_available else "CPU Mode"
        engine_desc = "AutoDock Vina 1.2.7"

        status_text = f"Ready | Engine: {engine_desc} | {gpu_desc} ({cuda_desc})"
        sb.showMessage(status_text)

        # Author credits in subtle small letters at the bottom right
        from PyQt5.QtWidgets import QLabel
        lbl_credit = QLabel("FazeraDock by Yehor Franchuk (@MrEgorin) | FAZENA  ")
        lbl_credit.setStyleSheet("font-size: 11px; color: #78909C; font-style: italic;")
        sb.addPermanentWidget(lbl_credit)

    def _connect_signals(self) -> None:
        # Protein prepared -> notify grid panel and docking panel
        self._protein_panel.protein_prepared.connect(self._on_protein_prepared)

        # Ligands prepared -> notify docking panel
        self._ligand_panel.ligands_prepared.connect(self._on_ligands_prepared)

        # Grid configured -> notify docking panel
        self._grid_panel.grid_configured.connect(self._on_grid_configured)

        # Docking completed -> populate results and switch to results tab
        self._docking_panel.docking_completed.connect(self._on_docking_completed)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------
    def _on_protein_prepared(self, pdbqt_path: str) -> None:
        raw_pdb = self._protein_panel.get_raw_pdb_path()
        self._grid_panel.set_protein_path(raw_pdb)
        self._docking_panel.set_receptor_pdbqt(pdbqt_path)
        self._results_panel.set_receptor_pdb(raw_pdb)
        self.statusBar().showMessage(f"Protein prepared: {os.path.basename(pdbqt_path)}", 5000)

    def _on_ligands_prepared(self, pdbqt_paths: list) -> None:
        self._docking_panel.set_ligand_pdbqts(pdbqt_paths)
        self.statusBar().showMessage(f"{len(pdbqt_paths)} ligand(s) ready for docking.", 5000)

    def _on_grid_configured(self, grid: GridBox) -> None:
        self._docking_panel.set_grid_box(grid)
        self.statusBar().showMessage(
            f"Grid configured: center=({grid.center_x:.1f}, {grid.center_y:.1f}, {grid.center_z:.1f})", 5000
        )

    def _on_docking_completed(self, result: object) -> None:
        self._results_panel.load_docking_result(result)
        # Automatically navigate to Results tab
        self._tabs.setCurrentWidget(self._results_panel)
        self.statusBar().showMessage("Docking run completed. Results displayed.", 8000)

    # ------------------------------------------------------------------
    # Project Save / Load
    # ------------------------------------------------------------------
    def _new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Enter Project Name:", text="NewDockingExperiment")
        if ok and name.strip():
            self._current_project = DockingProject(name=name.strip())
            self._current_project_path = None
            self.setWindowTitle(f"FazeraDock – [{name.strip()}] | FAZENA")
            self.statusBar().showMessage(f"Created new project: {name.strip()}", 4000)

    def _open_project_dialog(self) -> None:
        os.makedirs(str(PROJECTS_DIR), exist_ok=True)
        dlg = ProjectManagerDialog(str(PROJECTS_DIR), parent=self)
        if dlg.exec_():
            proj_path = dlg.get_selected_project_path()
            if proj_path:
                self._load_project_file(proj_path)

    def _load_project_file(self, path: str) -> None:
        try:
            prj = load_project(path)
            self._current_project = prj
            self._current_project_path = path

            # Apply loaded project settings to panels
            if prj.protein_path and os.path.exists(prj.protein_path):
                self._protein_panel.load_protein(prj.protein_path)

            if prj.protein_pdbqt_path:
                self._docking_panel.set_receptor_pdbqt(prj.protein_pdbqt_path)

            if prj.ligand_paths:
                existing_ligs = [p for p in prj.ligand_paths if os.path.exists(p)]
                self._docking_panel.set_ligand_pdbqts(existing_ligs)

            # Grid
            grid = GridBox(
                center_x=prj.grid_center[0],
                center_y=prj.grid_center[1],
                center_z=prj.grid_center[2],
                size_x=prj.grid_size[0],
                size_y=prj.grid_size[1],
                size_z=prj.grid_size[2],
            )
            self._grid_panel.set_grid_box(grid)
            self._docking_panel.set_grid_box(grid)

            self.setWindowTitle(f"FazeraDock – [{prj.name}] | FAZENA")
            self.statusBar().showMessage(f"Loaded project: {prj.name}", 5000)
            QMessageBox.information(self, "Project Loaded", f"Project '{prj.name}' loaded successfully.")

        except Exception as exc:
            QMessageBox.critical(self, "Load Error", f"Failed to load project:\n{exc}")

    def _save_project(self) -> None:
        if self._current_project_path:
            self._save_to_path(self._current_project_path)
        else:
            self._save_project_as()

    def _save_project_as(self) -> None:
        os.makedirs(str(PROJECTS_DIR), exist_ok=True)
        initial_name = self._current_project.name if self._current_project else "DockingProject"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save FazeraDock Project",
            os.path.join(str(PROJECTS_DIR), f"{initial_name}.json"),
            "FazeraDock Project (*.json)",
        )
        if save_path:
            self._save_to_path(save_path)

    def _save_to_path(self, path: str) -> None:
        try:
            name = Path(path).stem
            grid = self._grid_panel.get_grid_box()
            raw_pdb = self._protein_panel.get_raw_pdb_path() or ""
            pdbqt = self._docking_panel._receptor_pdbqt or ""
            ligands = self._docking_panel._ligand_pdbqts or []

            prj = DockingProject(
                name=name,
                protein_path=raw_pdb,
                protein_pdbqt_path=pdbqt,
                ligand_paths=ligands,
                grid_center=(grid.center_x, grid.center_y, grid.center_z),
                grid_size=(grid.size_x, grid.size_y, grid.size_z),
                exhaustiveness=self._grid_panel._spin_exhaustiveness.value() if hasattr(self._grid_panel, "_spin_exhaustiveness") else 8,
                num_modes=self._grid_panel._spin_modes.value() if hasattr(self._grid_panel, "_spin_modes") else 9,
                energy_range=int(self._grid_panel._spin_energy_range.value()) if hasattr(self._grid_panel, "_spin_energy_range") else 3,
                cpu=self._grid_panel._spin_cpu.value() if hasattr(self._grid_panel, "_spin_cpu") else 0,
            )

            save_project(prj, path)
            self._current_project = prj
            self._current_project_path = path
            self.setWindowTitle(f"FazeraDock – [{name}] | FAZENA")
            self.statusBar().showMessage(f"Project saved to: {path}", 5000)
            QMessageBox.information(self, "Project Saved", f"Project saved successfully to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save project:\n{exc}")

    # ------------------------------------------------------------------
    # Tools & Help
    # ------------------------------------------------------------------
    def _show_gpu_info(self) -> None:
        info = self._gpu_info
        lines = [
            f"GPU Name: {info.gpu_name}",
            f"NVIDIA GPU Detected: {'Yes' if info.has_nvidia else 'No'}",
            f"AMD GPU Detected: {'Yes' if info.has_amd else 'No'}",
            f"CUDA Acceleration Available: {'Yes' if info.cuda_available else 'No'}",
            f"OpenCL Available: {'Yes' if info.opencl_available else 'No'}",
            "",
            "Vina Engine In Use: AutoDock Vina 1.2.7 (CPU Multi-threaded)",
            "Note: On machines with NVIDIA CUDA GPUs, Vina-GPU acceleration is auto-activated.",
        ]
        QMessageBox.information(self, "Hardware & GPU Information", "\n".join(lines))

    def _launch_pymol(self) -> None:
        pymol_exe = r"C:\pymol\PyMOLWin.exe"
        if os.path.exists(pymol_exe):
            subprocess.Popen([pymol_exe])
        else:
            QMessageBox.warning(self, "PyMOL Not Found", f"PyMOL executable not found at:\n{pymol_exe}")

    def _open_results_dir(self) -> None:
        results_dir = os.path.abspath(os.path.join(str(APP_DIR), "results"))
        os.makedirs(results_dir, exist_ok=True)
        _open_path_crossplatform(results_dir)

    def _open_projects_dir(self) -> None:
        os.makedirs(str(PROJECTS_DIR), exist_ok=True)
        _open_path_crossplatform(str(PROJECTS_DIR))

    def _show_user_guide(self) -> None:
        guide_path = os.path.join(str(APP_DIR), "docs", "user_guide.md")
        if os.path.exists(guide_path):
            _open_path_crossplatform(guide_path)
        else:
            QMessageBox.information(self, "User Guide", "User Guide is located in docs/user_guide.md.")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About FazeraDock",
            "<h2>🧬 FazeraDock v1.0.0</h2>"
            "<p><b>Era of Accessible, User-Friendly Molecular Docking</b></p>"
            "<p><b>Lead Developer:</b> Yehor Franchuk (<a href='https://github.com/MrEgorin'>@MrEgorin</a>)</p>"
            "<p><b>Project:</b> FAZENA</p>"
            "<hr>"
            "<p>Built on top of <b>AutoDock Vina 1.2.7</b>, <b>Open Babel</b>, and <b>PyMOL Open-Source</b>.</p>"
            "<p>Features automated protein & ligand preparation, cross-docking screening, "
            "interactive PyMOL visualization with contact highlights, and 2D interaction diagrams.</p>"
            "<p><b>Repository:</b> <a href='https://github.com/MrEgorin/fazeradock'>https://github.com/MrEgorin/fazeradock</a></p>"
            "<p>© 2026 Yehor Franchuk / FAZENA. Released under the MIT License.</p>",
        )


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FazeraDock")
    app.setOrganizationName("FAZENA")
    app.setStyleSheet(MAIN_STYLESHEET)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
