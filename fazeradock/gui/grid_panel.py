"""
FazeraDock – Grid Configuration Panel
======================================

Provides the *Grid* tab for setting up the docking search-space box
(center, size) and docking parameters (exhaustiveness, modes, etc.).
"""

from __future__ import annotations

import os
import traceback
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class GridPanel(QWidget):
    """Widget for configuring the docking grid box and search parameters."""

    grid_configured = pyqtSignal(object)  # GridBox

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._protein_path: Optional[str] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        heading = QLabel("Grid Box & Docking Parameters")
        heading.setProperty("cssClass", "heading")
        main.addWidget(heading)

        # --- Grid center ---
        center_group = QGroupBox("Grid Center (Å)")
        center_lay = QHBoxLayout(center_group)
        self._spin_cx = self._make_coord_spin("X")
        self._spin_cy = self._make_coord_spin("Y")
        self._spin_cz = self._make_coord_spin("Z")
        for label, spin in [("X:", self._spin_cx), ("Y:", self._spin_cy), ("Z:", self._spin_cz)]:
            center_lay.addWidget(QLabel(label))
            center_lay.addWidget(spin)
        center_lay.addStretch()
        main.addWidget(center_group)

        # --- Grid size ---
        size_group = QGroupBox("Grid Size (Å)")
        size_lay = QHBoxLayout(size_group)
        self._spin_sx = self._make_size_spin("X")
        self._spin_sy = self._make_size_spin("Y")
        self._spin_sz = self._make_size_spin("Z")
        for label, spin in [("X:", self._spin_sx), ("Y:", self._spin_sy), ("Z:", self._spin_sz)]:
            size_lay.addWidget(QLabel(label))
            size_lay.addWidget(spin)
        size_lay.addStretch()
        main.addWidget(size_group)

        # --- Auto-detect buttons ---
        auto_group = QGroupBox("Auto-Detect Grid Center")
        auto_lay = QHBoxLayout(auto_group)

        self._cmb_ligands = QComboBox()
        self._cmb_ligands.setMinimumWidth(160)
        self._cmb_ligands.setPlaceholderText("(detected ligands)")
        auto_lay.addWidget(QLabel("Ligand:"))
        auto_lay.addWidget(self._cmb_ligands)

        self._btn_center_lig = QPushButton("Center on Ligand")
        self._btn_center_lig.clicked.connect(self._center_on_ligand)
        auto_lay.addWidget(self._btn_center_lig)

        self._btn_center_prot = QPushButton("Center on Protein")
        self._btn_center_prot.clicked.connect(self._center_on_protein)
        auto_lay.addWidget(self._btn_center_prot)

        self._btn_whole = QPushButton("Whole Protein")
        self._btn_whole.clicked.connect(self._whole_protein)
        auto_lay.addWidget(self._btn_whole)

        auto_lay.addStretch()
        main.addWidget(auto_group)

        # --- Docking parameters ---
        param_group = QGroupBox("Docking Parameters")
        param_lay = QHBoxLayout(param_group)

        # Exhaustiveness
        param_lay.addWidget(QLabel("Exhaustiveness:"))
        self._spin_exhaust = QSpinBox()
        self._spin_exhaust.setRange(1, 128)
        self._spin_exhaust.setValue(8)
        self._spin_exhaust.setToolTip("Higher values = more thorough search, slower")
        param_lay.addWidget(self._spin_exhaust)

        # Num modes
        param_lay.addWidget(QLabel("Modes:"))
        self._spin_modes = QSpinBox()
        self._spin_modes.setRange(1, 20)
        self._spin_modes.setValue(9)
        self._spin_modes.setToolTip("Maximum number of binding poses to generate")
        param_lay.addWidget(self._spin_modes)

        # Energy range
        param_lay.addWidget(QLabel("Energy range (kcal/mol):"))
        self._spin_energy = QDoubleSpinBox()
        self._spin_energy.setRange(1.0, 10.0)
        self._spin_energy.setValue(3.0)
        self._spin_energy.setDecimals(1)
        self._spin_energy.setSingleStep(0.5)
        param_lay.addWidget(self._spin_energy)

        param_lay.addStretch()
        main.addWidget(param_group)

        # --- CPU / seed ---
        hw_group = QGroupBox("Hardware & Reproducibility")
        hw_lay = QHBoxLayout(hw_group)

        hw_lay.addWidget(QLabel("CPU cores (0 = auto):"))
        self._spin_cpu = QSpinBox()
        self._spin_cpu.setRange(0, 64)
        self._spin_cpu.setValue(0)
        hw_lay.addWidget(self._spin_cpu)

        hw_lay.addWidget(QLabel("Random seed (0 = random):"))
        self._spin_seed = QSpinBox()
        self._spin_seed.setRange(0, 999999999)
        self._spin_seed.setValue(0)
        hw_lay.addWidget(self._spin_seed)

        hw_lay.addStretch()
        main.addWidget(hw_group)

        # --- Summary / preview ---
        summary_group = QGroupBox("Grid Summary")
        summary_lay = QVBoxLayout(summary_group)
        self._txt_summary = QTextEdit()
        self._txt_summary.setReadOnly(True)
        self._txt_summary.setMaximumHeight(100)
        summary_lay.addWidget(self._txt_summary)
        main.addWidget(summary_group)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self._btn_apply = QPushButton("  Apply Grid Settings  ")
        self._btn_apply.setProperty("cssClass", "success")
        self._btn_apply.clicked.connect(self._apply_settings)
        btn_row.addWidget(self._btn_apply)
        btn_row.addStretch()
        main.addLayout(btn_row)

        main.addStretch()

        # Connect spin changes to summary update
        for spin in (
            self._spin_cx, self._spin_cy, self._spin_cz,
            self._spin_sx, self._spin_sy, self._spin_sz,
            self._spin_exhaust, self._spin_modes, self._spin_cpu,
            self._spin_seed,
        ):
            spin.valueChanged.connect(self._update_summary)
        self._spin_energy.valueChanged.connect(self._update_summary)

        self._update_summary()

    # ------------------------------------------------------------------
    # Spin-box factories
    # ------------------------------------------------------------------
    @staticmethod
    def _make_coord_spin(axis: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1000.0, 1000.0)
        spin.setDecimals(3)
        spin.setValue(0.0)
        spin.setSingleStep(1.0)
        spin.setToolTip(f"Grid center {axis} coordinate (Å)")
        spin.setMinimumWidth(100)
        return spin

    @staticmethod
    def _make_size_spin(axis: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(1.0, 200.0)
        spin.setDecimals(1)
        spin.setValue(20.0)
        spin.setSingleStep(2.0)
        spin.setToolTip(f"Grid size along {axis} (Å)")
        spin.setMinimumWidth(100)
        return spin

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _update_summary(self) -> None:
        cx, cy, cz = self._spin_cx.value(), self._spin_cy.value(), self._spin_cz.value()
        sx, sy, sz = self._spin_sx.value(), self._spin_sy.value(), self._spin_sz.value()
        volume = sx * sy * sz
        lines = [
            f"Center : ({cx:.3f}, {cy:.3f}, {cz:.3f}) Å",
            f"Size   : {sx:.1f} × {sy:.1f} × {sz:.1f} Å  (volume ≈ {volume:,.0f} ų)",
            f"Exhaustiveness: {self._spin_exhaust.value()}  |  "
            f"Modes: {self._spin_modes.value()}  |  "
            f"Energy range: {self._spin_energy.value():.1f} kcal/mol",
            f"CPU: {'auto' if self._spin_cpu.value() == 0 else self._spin_cpu.value()}  |  "
            f"Seed: {'random' if self._spin_seed.value() == 0 else self._spin_seed.value()}",
        ]
        self._txt_summary.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Auto-detect actions
    # ------------------------------------------------------------------
    def _center_on_ligand(self) -> None:
        lig_name = self._cmb_ligands.currentText()
        if not lig_name:
            QMessageBox.information(
                self, "No Ligand", "No ligands detected in the protein structure."
            )
            return
        if not self._protein_path:
            QMessageBox.warning(self, "No Protein", "Please load a protein first.")
            return
        try:
            from fazeradock.pdb_utils import get_ligand_center

            x, y, z = get_ligand_center(self._protein_path, lig_name)
            self._spin_cx.setValue(x)
            self._spin_cy.setValue(y)
            self._spin_cz.setValue(z)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to find ligand center:\n{exc}")

    def _center_on_protein(self) -> None:
        if not self._protein_path:
            QMessageBox.warning(self, "No Protein", "Please load a protein first.")
            return
        try:
            from fazeradock.pdb_utils import get_center_of_mass

            x, y, z = get_center_of_mass(self._protein_path)
            self._spin_cx.setValue(x)
            self._spin_cy.setValue(y)
            self._spin_cz.setValue(z)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to compute center of mass:\n{exc}")

    def _whole_protein(self) -> None:
        if not self._protein_path:
            QMessageBox.warning(self, "No Protein", "Please load a protein first.")
            return
        try:
            from fazeradock.grid_manager import auto_grid_whole_protein

            grid = auto_grid_whole_protein(self._protein_path)
            self._spin_cx.setValue(grid.center_x)
            self._spin_cy.setValue(grid.center_y)
            self._spin_cz.setValue(grid.center_z)
            self._spin_sx.setValue(grid.size_x)
            self._spin_sy.setValue(grid.size_y)
            self._spin_sz.setValue(grid.size_z)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to compute whole-protein grid:\n{exc}")

    # ------------------------------------------------------------------
    # Apply / emit
    # ------------------------------------------------------------------
    def _apply_settings(self) -> None:
        try:
            from fazeradock.grid_manager import GridBox

            grid = GridBox(
                center_x=self._spin_cx.value(),
                center_y=self._spin_cy.value(),
                center_z=self._spin_cz.value(),
                size_x=self._spin_sx.value(),
                size_y=self._spin_sy.value(),
                size_z=self._spin_sz.value(),
            )
            self.grid_configured.emit(grid)
            QMessageBox.information(
                self,
                "Grid Applied",
                "Grid settings have been saved and will be used for docking.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not create grid:\n{exc}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_protein_path(self, path: str) -> None:
        """Set the protein path and populate ligand dropdown."""
        self._protein_path = path
        self._cmb_ligands.clear()
        try:
            from fazeradock.pdb_utils import detect_existing_ligands

            ligs = detect_existing_ligands(path)
            for lig in ligs:
                self._cmb_ligands.addItem(lig)
        except Exception:
            pass

    def get_grid_box(self) -> GridBox:
        from fazeradock.grid_manager import GridBox
        return GridBox(
            center_x=self._spin_cx.value(),
            center_y=self._spin_cy.value(),
            center_z=self._spin_cz.value(),
            size_x=self._spin_sx.value(),
            size_y=self._spin_sy.value(),
            size_z=self._spin_sz.value(),
        )

    def set_grid_box(self, grid: GridBox) -> None:
        self._spin_cx.setValue(grid.center_x)
        self._spin_cy.setValue(grid.center_y)
        self._spin_cz.setValue(grid.center_z)
        self._spin_sx.setValue(grid.size_x)
        self._spin_sy.setValue(grid.size_y)
        self._spin_sz.setValue(grid.size_z)
        self._update_preview()

    def get_grid_center(self) -> tuple[float, float, float]:
        return (self._spin_cx.value(), self._spin_cy.value(), self._spin_cz.value())

    def get_grid_size(self) -> tuple[float, float, float]:
        return (self._spin_sx.value(), self._spin_sy.value(), self._spin_sz.value())

    def get_exhaustiveness(self) -> int:
        return self._spin_exhaust.value()

    def get_num_modes(self) -> int:
        return self._spin_modes.value()

    def get_energy_range(self) -> float:
        return self._spin_energy.value()

    def get_cpu(self) -> int:
        return self._spin_cpu.value()

    def get_seed(self) -> int:
        return self._spin_seed.value()

    def load_from_project(
        self,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        exhaustiveness: int,
        num_modes: int,
        energy_range: float,
        cpu: int,
        seed: Optional[int],
    ) -> None:
        """Restore grid settings from a DockingProject."""
        if center:
            self._spin_cx.setValue(center[0])
            self._spin_cy.setValue(center[1])
            self._spin_cz.setValue(center[2])
        if size:
            self._spin_sx.setValue(size[0])
            self._spin_sy.setValue(size[1])
            self._spin_sz.setValue(size[2])
        self._spin_exhaust.setValue(exhaustiveness or 8)
        self._spin_modes.setValue(num_modes or 9)
        self._spin_energy.setValue(energy_range or 3.0)
        self._spin_cpu.setValue(cpu or 0)
        self._spin_seed.setValue(seed or 0)
