"""Ligand preparation module for FazeraDock.

Converts ligand files (SDF, MOL2, MOL, PDB, SMI) to PDBQT format
using OpenBabel, with support for batch and library processing.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .protein_prep import _get_obabel

logger = logging.getLogger(__name__)

# Supported input extensions
SUPPORTED_FORMATS: set[str] = {".sdf", ".mol2", ".mol", ".pdb", ".smi"}


# ------------------------------------------------------------------
# Result dataclass
# ------------------------------------------------------------------

@dataclass
class LigandPrepResult:
    """Result of preparing a single ligand."""

    pdbqt_path: str = ""
    name: str = ""
    formula: str = ""
    num_atoms: int = 0
    success: bool = False
    message: str = ""


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _extract_ligand_name(input_file: Path) -> str:
    """Derive a human-readable ligand name from the file.

    Tries to read the molecule title from the first line (SDF/MOL2),
    falls back to the file stem.
    """
    name = input_file.stem
    try:
        with open(input_file, "r", encoding="utf-8", errors="replace") as fh:
            first_line = fh.readline().strip()
            if first_line and not first_line.startswith(("$", "@", "#")):
                # SDF first line is the molecule name
                candidate = first_line.strip()
                if candidate and len(candidate) < 120:
                    name = candidate
    except OSError:
        pass
    return name


def _count_atoms_in_pdbqt(pdbqt_path: Path) -> int:
    """Count ATOM/HETATM records in a PDBQT file."""
    count = 0
    try:
        with open(pdbqt_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith(("ATOM", "HETATM")):
                    count += 1
    except OSError:
        pass
    return count


def _get_formula_obabel(input_file: Path) -> str:
    """Use obabel to retrieve the molecular formula."""
    try:
        obabel = _get_obabel()
        ext = input_file.suffix.lstrip(".")
        cmd = [obabel, str(input_file), "-o", "report", "-xl"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # The report format contains formula info; we'll parse it simply
        for line in proc.stdout.splitlines():
            if "FORMULA" in line.upper():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    except Exception:  # noqa: BLE001
        pass
    return ""


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def prepare_ligand(
    input_file: str | Path,
    output_dir: str | Path,
    add_hydrogens: bool = True,
    gen_3d: bool = False,
) -> LigandPrepResult:
    """Prepare a single ligand file for docking.

    Steps:
    1. Detect format from extension.
    2. If SMILES (``.smi``), generate 3D coordinates with ``--gen3d``.
    3. Add hydrogens if requested.
    4. Convert to PDBQT via ``obabel``.

    Parameters
    ----------
    input_file:
        Path to the input ligand file.
    output_dir:
        Directory for the output PDBQT.
    add_hydrogens:
        Add hydrogens before conversion.
    gen_3d:
        Force 3D coordinate generation (always ``True`` for SMILES).

    Returns
    -------
    LigandPrepResult
    """
    input_file = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = LigandPrepResult()

    # Validate format
    ext = input_file.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        result.message = f"Unsupported format: {ext}. Supported: {SUPPORTED_FORMATS}"
        logger.error(result.message)
        return result

    result.name = _extract_ligand_name(input_file)

    try:
        obabel = _get_obabel()
    except FileNotFoundError as exc:
        result.message = str(exc)
        logger.error(result.message)
        return result

    pdbqt_name = input_file.stem + ".pdbqt"
    pdbqt_path = output_dir / pdbqt_name

    # Build obabel command
    cmd: list[str] = [obabel, str(input_file), "-O", str(pdbqt_path)]

    if add_hydrogens:
        cmd.append("-h")

    # 3D generation for SMILES or when explicitly requested
    if ext == ".smi" or gen_3d:
        cmd.append("--gen3d")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not pdbqt_path.is_file():
            result.message = f"obabel conversion failed: {proc.stderr.strip()}"
            logger.error(result.message)
            return result
    except subprocess.TimeoutExpired:
        result.message = "obabel conversion timed out"
        logger.error(result.message)
        return result
    except OSError as exc:
        result.message = f"obabel execution error: {exc}"
        logger.error(result.message)
        return result

    result.pdbqt_path = str(pdbqt_path)
    result.num_atoms = _count_atoms_in_pdbqt(pdbqt_path)
    result.formula = _get_formula_obabel(input_file)
    result.success = True
    result.message = "Ligand prepared successfully"
    logger.info("Ligand '%s' prepared -> %s", result.name, pdbqt_path.name)
    return result


def prepare_ligand_batch(
    input_files: list[str | Path],
    output_dir: str | Path,
    add_hydrogens: bool = True,
    gen_3d: bool = False,
) -> list[LigandPrepResult]:
    """Prepare multiple ligand files sequentially.

    Parameters
    ----------
    input_files:
        List of paths to ligand files.
    output_dir:
        Output directory for all PDBQT files.
    add_hydrogens:
        Add hydrogens to each ligand.
    gen_3d:
        Force 3D coordinate generation.

    Returns
    -------
    list[LigandPrepResult]
    """
    results: list[LigandPrepResult] = []
    for i, f in enumerate(input_files, 1):
        logger.info("Preparing ligand %d/%d: %s", i, len(input_files), f)
        r = prepare_ligand(f, output_dir, add_hydrogens=add_hydrogens, gen_3d=gen_3d)
        results.append(r)
    return results


def prepare_ligand_library(
    sdf_file: str | Path,
    output_dir: str | Path,
    add_hydrogens: bool = True,
) -> list[LigandPrepResult]:
    """Split a multi-molecule SDF file and prepare each molecule individually.

    Parameters
    ----------
    sdf_file:
        Path to the multi-molecule SDF file.
    output_dir:
        Directory for the individual PDBQT files.
    add_hydrogens:
        Add hydrogens to each ligand.

    Returns
    -------
    list[LigandPrepResult]
    """
    sdf_file = Path(sdf_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Split the SDF into individual files using obabel
    try:
        obabel = _get_obabel()
    except FileNotFoundError as exc:
        logger.error("obabel not found: %s", exc)
        return []

    split_dir = output_dir / "_split_sdf"
    split_dir.mkdir(parents=True, exist_ok=True)

    split_pattern = str(split_dir / "mol_.sdf")
    cmd = [obabel, str(sdf_file), "-O", split_pattern, "-m"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            logger.error("SDF splitting failed: %s", proc.stderr)
            return []
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.error("SDF splitting error: %s", exc)
        return []

    # Collect split files (obabel names them mol_1.sdf, mol_2.sdf, …)
    split_files = sorted(split_dir.glob("mol_*.sdf"))
    logger.info("Split SDF into %d molecules", len(split_files))

    # Prepare each individual molecule
    results: list[LigandPrepResult] = []
    for i, sf in enumerate(split_files, 1):
        logger.info("Preparing molecule %d/%d from library", i, len(split_files))
        r = prepare_ligand(sf, output_dir, add_hydrogens=add_hydrogens)
        results.append(r)

    return results
