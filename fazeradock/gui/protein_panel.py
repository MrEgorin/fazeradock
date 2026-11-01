"""
FazeraDock – Protein Preparation Panel
=======================================

Provides the *Protein* tab for loading, inspecting and preparing
receptor PDB / CIF files for docking.
"""

from __future__ import annotations

import os
import traceback
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Worker thread for protein preparation
# ---------------------------------------------------------------------------
class _ProteinPrepWorker(QThread):
    """Runs protein preparation in a background thread."""

    log = pyqtSignal(str)
    finished = pyqtSignal(object)  # PrepResult or None
    error = pyqtSignal(str)

    def __init__(
        self,
        pdb_path: str,
        remove_water: bool,
        remove_het: bool,
        add_h: bool,
        selected_chain: Optional[str],
        parent: Optional[QThread] = None,
    ) -> None:
        super().__init__(parent)
        self.pdb_path = pdb_path
        self.remove_water = remove_water
        self.remove_het = remove_het
        self.add_h = add_h
        self.selected_chain = selected_chain

    def run(self) -> None:  # noqa: D401
        try:
            from fazeradock.protein_prep import prepare_protein

            self.log.emit("Starting protein preparation …")
            self.log.emit(f"  Input file : {self.pdb_path}")
            self.log.emit(f"  Remove water : {self.remove_water}")
            self.log.emit(f"  Remove HET   : {self.remove_het}")
            self.log.emit(f"  Add hydrogens: {self.add_h}")
            chain = self.selected_chain if self.selected_chain != "All" else None
            self.log.emit(f"  Chain        : {chain or 'All'}")

            result = prepare_protein(
                pdb_path=self.pdb_path,
                remove_water=self.remove_water,
                remove_het=self.remove_het,
                add_hydrogens=self.add_h,
                chain=chain,
            )

            self.log.emit("Protein preparation completed successfully.")
            self.finished.emit(result)
        except Exception as exc:
            tb = traceback.format_exc()
            self.log.emit(f"ERROR: {exc}")
            self.error.emit(f"{exc}\n\n{tb}")


# ---------------------------------------------------------------------------
# Protein panel widget
# ---------------------------------------------------------------------------
class ProteinPanel(QWidget):
    """Widget for loading and preparing a receptor protein."""

    protein_prepared = pyqtSignal(str)  # pdbqt_path

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pdb_path: Optional[str] = None
        self._pdbqt_path: Optional[str] = None
        self._worker: Optional[_ProteinPrepWorker] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # --- Heading ---
        heading = QLabel("Protein / Receptor Preparation")
        heading.setProperty("cssClass", "heading")
        main_layout.addWidget(heading)

        # --- File loader ---
        file_group = QGroupBox("Load Protein Structure")
        file_lay = QHBoxLayout(file_group)
        self._btn_load = QPushButton("Load Protein (PDB / CIF)")
        self._btn_load.setToolTip("Browse for a PDB or CIF protein file")
        self._btn_load.clicked.connect(self._browse_protein)
        file_lay.addWidget(self._btn_load)

        self._le_path = QLineEdit()
        self._le_path.setReadOnly(True)
        self._le_path.setPlaceholderText("No file selected — click button or drag && drop")
        self._le_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        file_lay.addWidget(self._le_path)
        main_layout.addWidget(file_group)

        # Enable drag & drop on the whole panel
        self.setAcceptDrops(True)

        # --- Protein info ---
        info_group = QGroupBox("Protein Information")
        info_lay = QVBoxLayout(info_group)
        self._txt_info = QTextEdit()
        self._txt_info.setReadOnly(True)
        self._txt_info.setMaximumHeight(140)
        self._txt_info.setPlaceholderText(
            "Protein details will appear here after loading a file."
        )
        info_lay.addWidget(self._txt_info)
        main_layout.addWidget(info_group)

        # --- Preparation options ---
        opts_group = QGroupBox("Preparation Options")
        opts_lay = QVBoxLayout(opts_group)

        self._chk_water = QCheckBox("Remove water molecules")
        self._chk_water.setChecked(True)
        opts_lay.addWidget(self._chk_water)

        self._chk_het = QCheckBox("Remove heteroatoms (non-protein residues)")
        self._chk_het.setChecked(True)
        opts_lay.addWidget(self._chk_het)

        self._chk_addh = QCheckBox("Add hydrogens")
        self._chk_addh.setChecked(True)
        opts_lay.addWidget(self._chk_addh)

        chain_row = QHBoxLayout()
        chain_row.addWidget(QLabel("Select chain:"))
        self._cmb_chain = QComboBox()
        self._cmb_chain.addItem("All")
        self._cmb_chain.setMinimumWidth(100)
        chain_row.addWidget(self._cmb_chain)
        chain_row.addStretch()
        opts_lay.addLayout(chain_row)

        main_layout.addWidget(opts_group)

        # --- Prepare button ---
        self._btn_prepare = QPushButton("  Prepare Protein  ")
        self._btn_prepare.setProperty("cssClass", "accent")
        self._btn_prepare.setEnabled(False)
        self._btn_prepare.setToolTip("Prepare the loaded protein for docking")
        self._btn_prepare.clicked.connect(self._run_preparation)
        main_layout.addWidget(self._btn_prepare, alignment=Qt.AlignLeft)

        # --- Log ---
        log_group = QGroupBox("Preparation Log")
        log_lay = QVBoxLayout(log_group)
        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        self._txt_log.setMinimumHeight(100)
        log_lay.addWidget(self._txt_log)
        main_layout.addWidget(log_group)

        # --- Status ---
        self._lbl_status = QLabel("")
        main_layout.addWidget(self._lbl_status)

        main_layout.addStretch()

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith((".pdb", ".cif", ".mmcif", ".ent")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".pdb", ".cif", ".mmcif", ".ent")):
                self._load_protein(path)
                event.acceptProposedAction()
                return
        event.ignore()

    # ------------------------------------------------------------------
    # File browsing / loading
    # ------------------------------------------------------------------
    def _browse_protein(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Protein Structure",
            "",
            "Protein files (*.pdb *.cif *.mmcif *.ent);;All files (*)",
        )
        if path:
            self._load_protein(path)

    def _load_protein(self, path: str) -> None:
        self._pdb_path = os.path.normpath(path)
        self._le_path.setText(self._pdb_path)
        self._btn_prepare.setEnabled(True)
        self._lbl_status.setText("")
        self._pdbqt_path = None

        # Populate info & chains
        self._populate_info(self._pdb_path)

    def _populate_info(self, path: str) -> None:
        """Populate the info box with chain / residue data from the loaded file."""
        lines: list[str] = []
        try:
            from fazeradock.pdb_utils import (
                detect_existing_ligands,
                get_chains,
                get_residues,
            )

            chains = get_chains(path)
            residues = get_residues(path)
            ligands = detect_existing_ligands(path)

            lines.append(f"File    : {os.path.basename(path)}")
            lines.append(f"Chains  : {', '.join(chains) if chains else 'N/A'}")
            lines.append(f"Residues: {len(residues) if residues else 'N/A'}")
            lines.append(
                f"Ligands : {', '.join(ligands) if ligands else 'None detected'}"
            )

            # Update chain combo
            self._cmb_chain.clear()
            self._cmb_chain.addItem("All")
            for ch in chains:
                self._cmb_chain.addItem(ch)
        except Exception as exc:
            lines.append(f"Could not parse protein info: {exc}")

        self._txt_info.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------
    def _run_preparation(self) -> None:
        if not self._pdb_path:
            QMessageBox.warning(self, "No File", "Please load a protein file first.")
            return

        self._btn_prepare.setEnabled(False)
        self._txt_log.clear()
        self._lbl_status.setText("Preparing …")
        self._lbl_status.setProperty("cssClass", "warning")
        self._lbl_status.style().unpolish(self._lbl_status)
        self._lbl_status.style().polish(self._lbl_status)

        self._worker = _ProteinPrepWorker(
            pdb_path=self._pdb_path,
            remove_water=self._chk_water.isChecked(),
            remove_het=self._chk_het.isChecked(),
            add_h=self._chk_addh.isChecked(),
            selected_chain=self._cmb_chain.currentText(),
        )
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_prep_finished)
        self._worker.error.connect(self._on_prep_error)
        self._worker.start()

    def _append_log(self, msg: str) -> None:
        self._txt_log.append(msg)

    def _on_prep_finished(self, result: object) -> None:
        self._btn_prepare.setEnabled(True)
        pdbqt_path: str = getattr(result, "pdbqt_path", "")
        if pdbqt_path:
            self._pdbqt_path = pdbqt_path
            self._lbl_status.setText(f"✓  Protein prepared: {os.path.basename(pdbqt_path)}")
            self._lbl_status.setProperty("cssClass", "success")
            self._lbl_status.style().unpolish(self._lbl_status)
            self._lbl_status.style().polish(self._lbl_status)
            self.protein_prepared.emit(pdbqt_path)
        else:
            self._lbl_status.setText("Preparation finished (no PDBQT path returned).")
            self._lbl_status.setProperty("cssClass", "warning")
            self._lbl_status.style().unpolish(self._lbl_status)
            self._lbl_status.style().polish(self._lbl_status)

    def _on_prep_error(self, msg: str) -> None:
        self._btn_prepare.setEnabled(True)
        self._lbl_status.setText("✗  Preparation failed.")
        self._lbl_status.setProperty("cssClass", "error")
        self._lbl_status.style().unpolish(self._lbl_status)
        self._lbl_status.style().polish(self._lbl_status)
        QMessageBox.critical(self, "Protein Preparation Error", msg)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_raw_pdb_path(self) -> Optional[str]:
        """Alias for pdb_path."""
        return self._pdb_path

    @property
    def pdb_path(self) -> Optional[str]:
        """Return the loaded PDB/CIF path, or *None*."""
        return self._pdb_path

    @property
    def pdbqt_path(self) -> Optional[str]:
        """Return the prepared PDBQT path, or *None*."""
        return self._pdbqt_path

    def set_protein_path(self, path: str) -> None:
        """Programmatically set the protein path (e.g. from a project)."""
        if path and os.path.isfile(path):
            self._load_protein(path)

    def set_pdbqt_path(self, path: str) -> None:
        """Mark an existing PDBQT as already prepared."""
        if path:
            self._pdbqt_path = path
            self._lbl_status.setText(
                f"✓  Previously prepared: {os.path.basename(path)}"
            )
            self._lbl_status.setProperty("cssClass", "success")
            self._lbl_status.style().unpolish(self._lbl_status)
            self._lbl_status.style().polish(self._lbl_status)
