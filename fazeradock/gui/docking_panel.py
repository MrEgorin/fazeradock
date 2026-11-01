"""
FazeraDock – Docking Execution Panel
====================================

Provides the *Docking* tab for reviewing configuration, choosing screening mode
(Single, Library, Cross-Docking), executing docking runs via AutoDock Vina / Vina-GPU,
streaming real-time output, and handling cancellation.
"""

from __future__ import annotations

import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..docking_engine import DockingConfig, DockingResult, run_docking
from ..gpu_detect import detect_gpu, get_recommended_engine, GPUInfo
from ..grid_manager import GridBox
from ..screening import ScreeningConfig, ScreeningMode, ScreeningResult, run_screening


# ---------------------------------------------------------------------------
# Background Worker Thread
# ---------------------------------------------------------------------------
class _DockingWorker(QThread):
    """Background worker for single docking or virtual screening."""

    log_line = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)  # current, total, label
    finished = pyqtSignal(object)  # DockingResult or ScreeningResult
    error = pyqtSignal(str)

    def __init__(
        self,
        mode: ScreeningMode,
        receptors: List[str],
        ligands: List[str],
        grid_boxes: Dict[str, GridBox],
        exhaustiveness: int,
        num_modes: int,
        energy_range: int,
        cpu: int,
        output_dir: str,
        use_gpu: bool,
        parent: Optional[QThread] = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.receptors = receptors
        self.ligands = ligands
        self.grid_boxes = grid_boxes
        self.exhaustiveness = exhaustiveness
        self.num_modes = num_modes
        self.energy_range = energy_range
        self.cpu = cpu
        self.output_dir = output_dir
        self.use_gpu = use_gpu
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            os.makedirs(self.output_dir, exist_ok=True)

            if self.mode == ScreeningMode.SINGLE:
                # 1 receptor vs 1 ligand
                if not self.receptors or not self.ligands:
                    self.error.emit("Receptor and ligand PDBQT must be specified for docking.")
                    return

                rec = self.receptors[0]
                lig = self.ligands[0]
                grid = self.grid_boxes.get(rec)
                if not grid:
                    self.error.emit(f"No grid box configured for receptor: {os.path.basename(rec)}")
                    return

                pair_out = os.path.join(
                    self.output_dir,
                    f"{Path(rec).stem}_{Path(lig).stem}"
                )
                os.makedirs(pair_out, exist_ok=True)

                cfg = DockingConfig(
                    receptor_pdbqt=rec,
                    ligand_pdbqt=lig,
                    grid=grid,
                    exhaustiveness=self.exhaustiveness,
                    num_modes=self.num_modes,
                    energy_range=self.energy_range,
                    cpu=self.cpu,
                    output_dir=pair_out,
                    use_gpu=self.use_gpu,
                )

                self.progress.emit(0, 1, f"Docking {Path(lig).stem} into {Path(rec).stem}...")

                def _cb(line: str) -> None:
                    self.log_line.emit(line)

                res = run_docking(cfg, progress_callback=_cb)
                self.progress.emit(1, 1, "Completed.")
                self.finished.emit(res)

            else:
                # Library or Cross-docking
                sc_cfg = ScreeningConfig(
                    mode=self.mode,
                    receptor_pdbqts=self.receptors,
                    ligand_pdbqts=self.ligands,
                    grid_boxes=self.grid_boxes,
                    exhaustiveness=self.exhaustiveness,
                    num_modes=self.num_modes,
                    energy_range=self.energy_range,
                    cpu=self.cpu,
                    output_base_dir=self.output_dir,
                )

                total_runs = len(self.receptors) * len(self.ligands)
                current_run = 0

                def _cb(line: str) -> None:
                    nonlocal current_run
                    self.log_line.emit(line)
                    if "[Vina]" in line and "Executing" in line:
                        current_run += 1
                        self.progress.emit(
                            current_run,
                            total_runs,
                            f"Running pair {current_run}/{total_runs}..."
                        )

                scr_res = run_screening(sc_cfg, progress_callback=_cb)
                self.progress.emit(total_runs, total_runs, "Screening finished.")
                self.finished.emit(scr_res)

        except Exception as exc:
            self.log_line.emit(f"[ERROR] Exception during docking: {exc}")
            self.log_line.emit(traceback.format_exc())
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Docking Panel UI
# ---------------------------------------------------------------------------
class DockingPanel(QWidget):
    """Panel for configuring and launching molecular docking runs."""

    docking_completed = pyqtSignal(object)  # DockingResult or ScreeningResult

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._receptor_pdbqt: Optional[str] = None
        self._additional_receptors: List[str] = []
        self._ligand_pdbqts: List[str] = []
        self._grid_box: Optional[GridBox] = None
        self._worker: Optional[_DockingWorker] = None
        self._gpu_info: GPUInfo = detect_gpu()
        self._start_time: float = 0.0

        self._build_ui()
        self._update_summary()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Mode Selection Group
        mode_box = QGroupBox("Docking & Screening Mode")
        mode_layout = QHBoxLayout(mode_box)

        self._btn_single = QRadioButton("Single Docking (1 Ligand vs 1 Receptor)")
        self._btn_single.setChecked(True)
        self._btn_single.toggled.connect(self._on_mode_changed)

        self._btn_library = QRadioButton("Virtual Screening (Many Ligands vs 1 Receptor)")
        self._btn_library.toggled.connect(self._on_mode_changed)

        self._btn_cross = QRadioButton("Cross-Docking (Many Ligands vs Many Receptors)")
        self._btn_cross.toggled.connect(self._on_mode_changed)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._btn_single)
        self._mode_group.addButton(self._btn_library)
        self._mode_group.addButton(self._btn_cross)

        mode_layout.addWidget(self._btn_single)
        mode_layout.addWidget(self._btn_library)
        mode_layout.addWidget(self._btn_cross)
        main_layout.addWidget(mode_box)

        # 2. Additional receptors section (for cross docking)
        self._cross_box = QGroupBox("Additional Receptors for Cross-Docking")
        cross_layout = QVBoxLayout(self._cross_box)
        btn_bar = QHBoxLayout()
        self._btn_add_receptors = QPushButton("+ Add Receptors (PDBQT)")
        self._btn_add_receptors.clicked.connect(self._add_receptors_dialog)
        self._btn_clear_receptors = QPushButton("Clear")
        self._btn_clear_receptors.clicked.connect(self._clear_additional_receptors)
        btn_bar.addWidget(self._btn_add_receptors)
        btn_bar.addWidget(self._btn_clear_receptors)
        btn_bar.addStretch()

        self._receptors_list = QListWidget()
        self._receptors_list.setMaximumHeight(80)
        cross_layout.addLayout(btn_bar)
        cross_layout.addWidget(self._receptors_list)
        self._cross_box.setVisible(False)
        main_layout.addWidget(self._cross_box)

        # 3. Summary & Hardware Group
        summary_box = QGroupBox("Docking Setup Summary")
        summary_layout = QVBoxLayout(summary_box)

        self._lbl_receptor_info = QLabel("<b>Receptor:</b> None selected")
        self._lbl_ligand_info = QLabel("<b>Ligands:</b> None prepared")
        self._lbl_grid_info = QLabel("<b>Grid Box:</b> Not configured")
        self._lbl_engine_info = QLabel(
            f"<b>Docking Engine:</b> AutoDock Vina 1.2.7 (CPU) | "
            f"<b>GPU Status:</b> {self._gpu_info.gpu_name} (CUDA: {'Yes' if self._gpu_info.cuda_available else 'No'})"
        )

        summary_layout.addWidget(self._lbl_receptor_info)
        summary_layout.addWidget(self._lbl_ligand_info)
        summary_layout.addWidget(self._lbl_grid_info)
        summary_layout.addWidget(self._lbl_engine_info)
        main_layout.addWidget(summary_box)

        # 4. Action Buttons & Progress Bar
        action_layout = QHBoxLayout()
        self._btn_start = QPushButton("▶  Start Docking")
        self._btn_start.setObjectName("startDockingBtn")
        self._btn_start.setFixedHeight(42)
        self._btn_start.setStyleSheet(
            "QPushButton#startDockingBtn { background-color: #2E7D32; color: white; font-weight: bold; font-size: 14px; border-radius: 4px; padding: 0 24px; }"
            "QPushButton#startDockingBtn:hover { background-color: #388E3C; }"
            "QPushButton#startDockingBtn:disabled { background-color: #BDBDBD; }"
        )
        self._btn_start.clicked.connect(self.start_docking)

        self._btn_stop = QPushButton("⏹  Stop Docking")
        self._btn_stop.setObjectName("stopDockingBtn")
        self._btn_stop.setFixedHeight(42)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            "QPushButton#stopDockingBtn { background-color: #C62828; color: white; font-weight: bold; font-size: 14px; border-radius: 4px; padding: 0 24px; }"
            "QPushButton#stopDockingBtn:hover { background-color: #D32F2F; }"
            "QPushButton#stopDockingBtn:disabled { background-color: #BDBDBD; }"
        )
        self._btn_stop.clicked.connect(self.stop_docking)

        action_layout.addWidget(self._btn_start)
        action_layout.addWidget(self._btn_stop)
        action_layout.addStretch()
        main_layout.addLayout(action_layout)

        # Progress bar & status
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._lbl_progress_status = QLabel("Ready to dock.")
        main_layout.addWidget(self._progress_bar)
        main_layout.addWidget(self._lbl_progress_status)

        # 5. Live Console Log
        log_box = QGroupBox("Docking Engine Output")
        log_layout = QVBoxLayout(log_box)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet("font-family: Consolas, Courier New, monospace; font-size: 11px; background-color: #1E1E1E; color: #D4D4D4;")
        log_layout.addWidget(self._log_text)
        main_layout.addWidget(log_box, stretch=1)

    # ------------------------------------------------------------------
    # State update methods
    # ------------------------------------------------------------------
    def set_receptor_pdbqt(self, path: str) -> None:
        self._receptor_pdbqt = path
        self._update_summary()

    def set_ligand_pdbqts(self, paths: List[str]) -> None:
        self._ligand_pdbqts = list(paths)
        if len(self._ligand_pdbqts) > 1 and self._btn_single.isChecked():
            self._btn_library.setChecked(True)
        self._update_summary()

    def set_grid_box(self, grid: GridBox) -> None:
        self._grid_box = grid
        self._update_summary()

    def _on_mode_changed(self) -> None:
        is_cross = self._btn_cross.isChecked()
        self._cross_box.setVisible(is_cross)
        self._update_summary()

    def _add_receptors_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Additional Receptors (PDBQT)",
            "",
            "PDBQT Files (*.pdbqt);;All Files (*)",
        )
        for f in files:
            if f not in self._additional_receptors:
                self._additional_receptors.append(f)
                self._receptors_list.addItem(os.path.basename(f))
        self._update_summary()

    def _clear_additional_receptors(self) -> None:
        self._additional_receptors.clear()
        self._receptors_list.clear()
        self._update_summary()

    def _update_summary(self) -> None:
        if self._receptor_pdbqt:
            rec_text = f"<b>Receptor:</b> {os.path.basename(self._receptor_pdbqt)}"
            if self._btn_cross.isChecked() and self._additional_receptors:
                rec_text += f" (+{len(self._additional_receptors)} additional receptors)"
            self._lbl_receptor_info.setText(rec_text)
        else:
            self._lbl_receptor_info.setText("<b>Receptor:</b> <span style='color: #D32F2F;'>None selected</span>")

        n_lig = len(self._ligand_pdbqts)
        if n_lig > 0:
            self._lbl_ligand_info.setText(f"<b>Ligands:</b> {n_lig} prepared file(s)")
        else:
            self._lbl_ligand_info.setText("<b>Ligands:</b> <span style='color: #D32F2F;'>None prepared</span>")

        if self._grid_box:
            g = self._grid_box
            self._lbl_grid_info.setText(
                f"<b>Grid Box:</b> Center=({g.center_x:.1f}, {g.center_y:.1f}, {g.center_z:.1f}) | "
                f"Size=({g.size_x:.1f}, {g.size_y:.1f}, {g.size_z:.1f}) Å"
            )
        else:
            self._lbl_grid_info.setText("<b>Grid Box:</b> <span style='color: #D32F2F;'>Not configured</span>")

    # ------------------------------------------------------------------
    # Docking execution
    # ------------------------------------------------------------------
    def start_docking(self) -> None:
        if not self._receptor_pdbqt or not os.path.isfile(self._receptor_pdbqt):
            QMessageBox.warning(self, "Missing Receptor", "Please load and prepare a receptor first.")
            return

        if not self._ligand_pdbqts:
            QMessageBox.warning(self, "Missing Ligands", "Please prepare at least one ligand first.")
            return

        if not self._grid_box:
            QMessageBox.warning(self, "Missing Grid Box", "Please configure the grid box first.")
            return

        # Determine screening mode
        if self._btn_single.isChecked():
            mode = ScreeningMode.SINGLE
            receptors = [self._receptor_pdbqt]
            ligands = [self._ligand_pdbqts[0]]
        elif self._btn_library.isChecked():
            mode = ScreeningMode.LIBRARY
            receptors = [self._receptor_pdbqt]
            ligands = list(self._ligand_pdbqts)
        else:
            mode = ScreeningMode.CROSS
            receptors = [self._receptor_pdbqt] + list(self._additional_receptors)
            ligands = list(self._ligand_pdbqts)

        # Output folder in results/
        results_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"dock_{Path(self._receptor_pdbqt).stem}_{timestamp}"
        out_dir = os.path.join(results_root, run_name)

        grid_boxes = {r: self._grid_box for r in receptors}

        # Check GPU availability
        use_gpu = self._gpu_info.cuda_available

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._progress_bar.setValue(0)
        self._log_text.clear()
        self._start_time = time.time()

        self._log_text.append(f"=== Starting FazeraDock Docking Job ===")
        self._log_text.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log_text.append(f"Mode: {mode.value.upper()}")
        self._log_text.append(f"Receptors: {len(receptors)}, Ligands: {len(ligands)}")
        self._log_text.append(f"Engine: {'Vina-GPU' if use_gpu else 'AutoDock Vina 1.2.7 (CPU)'}")
        self._log_text.append(f"Output Directory: {out_dir}")
        self._log_text.append("-" * 50)

        self._worker = _DockingWorker(
            mode=mode,
            receptors=receptors,
            ligands=ligands,
            grid_boxes=grid_boxes,
            exhaustiveness=8,
            num_modes=9,
            energy_range=3,
            cpu=0,
            output_dir=out_dir,
            use_gpu=use_gpu,
        )

        self._worker.log_line.connect(self._append_log)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def stop_docking(self) -> None:
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Docking",
                "Are you sure you want to stop the ongoing docking job?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._worker.cancel()
                self._worker.terminate()
                self._append_log("[INFO] Docking job cancelled by user.")
                self._btn_start.setEnabled(True)
                self._btn_stop.setEnabled(False)
                self._lbl_progress_status.setText("Docking cancelled.")

    def _append_log(self, text: str) -> None:
        self._log_text.append(text)
        sb = self._log_text.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _update_progress(self, current: int, total: int, status: str) -> None:
        if total > 0:
            pct = int((current / total) * 100)
            self._progress_bar.setValue(pct)
        self._lbl_progress_status.setText(f"[{current}/{total}] {status}")

    def _on_finished(self, result: object) -> None:
        elapsed = time.time() - self._start_time
        self._append_log("-" * 50)
        self._append_log(f"=== Docking Completed Successfully in {elapsed:.1f}s ===")
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._progress_bar.setValue(100)
        self._lbl_progress_status.setText(f"Completed in {elapsed:.1f}s.")

        QMessageBox.information(
            self,
            "Docking Finished",
            f"Docking calculation completed in {elapsed:.1f} seconds!\nCheck the Results tab to view poses and interactions.",
        )
        self.docking_completed.emit(result)

    def _on_error(self, err_msg: str) -> None:
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._lbl_progress_status.setText("Error encountered.")
        QMessageBox.critical(self, "Docking Error", f"Docking encountered an error:\n{err_msg}")
