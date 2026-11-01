"""Protein preparation pipeline for FazeraDock.

Cleans PDB files (water/HETATM removal, chain selection), adds hydrogens
via OpenBabel, and converts to PDBQT format using AutoDockTools or OpenBabel.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .pdb_utils import (
    get_chains,
    get_waters,
    get_heteroatoms,
    remove_waters,
    remove_hetatm,
    select_chain,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# External tool paths
# ------------------------------------------------------------------

ADT_PYTHON: str = r"C:\AMDock-win-master\python.exe"
ADT_PREPARE_RECEPTOR: str = (
    r"C:\AMDock-win-master\Lib\site-packages\AutoDockTools"
    r"\Utilities24\prepare_receptor4.py"
)


def _find_obabel() -> str:
    """Locate the ``obabel`` executable.

    Search order:
    1. ``obabel`` on the system PATH
    2. ``C:\\Program Files\\OpenBabel-3.1.1\\obabel.exe``
    3. ``C:\\openbabel-3.1.1\\obabel.exe``

    Raises
    ------
    FileNotFoundError
        If ``obabel`` cannot be found.
    """
    # 1. Check PATH
    found = shutil.which("obabel")
    if found:
        return found

    # 2-3. Well-known locations
    for candidate in (
        r"C:\Program Files\OpenBabel-3.1.1\obabel.exe",
        r"C:\openbabel-3.1.1\obabel.exe",
    ):
        if Path(candidate).is_file():
            return candidate

    raise FileNotFoundError(
        "obabel not found. Install OpenBabel 3.1.1 or add it to PATH."
    )


OBABEL_PATH: str = ""  # resolved lazily on first use


def _get_obabel() -> str:
    """Return the resolved obabel path, caching the result."""
    global OBABEL_PATH  # noqa: PLW0603
    if not OBABEL_PATH:
        OBABEL_PATH = _find_obabel()
    return OBABEL_PATH


# ------------------------------------------------------------------
# Result dataclass
# ------------------------------------------------------------------

@dataclass
class PrepResult:
    """Result of the protein preparation pipeline."""

    clean_pdb_path: str = ""
    pdbqt_path: str = ""
    removed_waters: int = 0
    removed_het: int = 0
    chains_found: list[str] = field(default_factory=list)
    success: bool = False
    message: str = ""


# ------------------------------------------------------------------
# Pipeline
# ------------------------------------------------------------------

def prepare_protein(
    input_pdb: str | Path,
    output_dir: str | Path,
    chain: Optional[str] = None,
    remove_water: bool = True,
    remove_het: bool = True,
    keep_ligands: Optional[list[str]] = None,
    add_hydrogens: bool = True,
) -> PrepResult:
    """Run the full protein preparation pipeline.

    Steps:
    1. Analyse the input PDB (chains, waters, heteroatoms).
    2. Remove waters (optional).
    3. Remove HETATM records (optional; *keep_ligands* preserves
       specific residue names).
    4. Select a single chain (optional).
    5. Add hydrogens via OpenBabel.
    6. Convert to PDBQT (AutoDockTools first, OpenBabel fallback).

    Parameters
    ----------
    input_pdb:
        Path to the input PDB file.
    output_dir:
        Directory where intermediate and output files are written.
    chain:
        If set, only this chain is retained.
    remove_water:
        Remove water molecules.
    remove_het:
        Remove HETATM records.
    keep_ligands:
        Residue names to keep even when *remove_het* is ``True``.
    add_hydrogens:
        Add hydrogens via ``obabel -h``.

    Returns
    -------
    PrepResult
    """
    input_pdb = Path(input_pdb)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = PrepResult()

    stem = input_pdb.stem

    # ---- Step 1: Analyse input ----------------------------------
    try:
        result.chains_found = get_chains(input_pdb)
        n_waters = len(get_waters(input_pdb))
        n_het = len(get_heteroatoms(input_pdb))
        logger.info(
            "Input PDB: chains=%s  waters=%d  hetatm=%d",
            result.chains_found, n_waters, n_het,
        )
    except Exception as exc:
        result.message = f"Failed to analyse input PDB: {exc}"
        logger.error(result.message)
        return result

    current_pdb = input_pdb

    # ---- Step 2: Remove waters ----------------------------------
    if remove_water:
        dewater_pdb = output_dir / f"{stem}_nowater.pdb"
        try:
            result.removed_waters = remove_waters(current_pdb, dewater_pdb)
            current_pdb = dewater_pdb
        except Exception as exc:
            result.message = f"Failed to remove waters: {exc}"
            logger.error(result.message)
            return result

    # ---- Step 3: Remove HETATM ----------------------------------
    if remove_het:
        nohet_pdb = output_dir / f"{stem}_nohet.pdb"
        try:
            result.removed_het = remove_hetatm(
                current_pdb, nohet_pdb, keep_resnames=keep_ligands
            )
            current_pdb = nohet_pdb
        except Exception as exc:
            result.message = f"Failed to remove HETATM: {exc}"
            logger.error(result.message)
            return result

    # ---- Step 4: Select chain -----------------------------------
    if chain:
        chain_pdb = output_dir / f"{stem}_chain{chain}.pdb"
        try:
            select_chain(current_pdb, chain, chain_pdb)
            current_pdb = chain_pdb
        except Exception as exc:
            result.message = f"Failed to select chain '{chain}': {exc}"
            logger.error(result.message)
            return result

    # ---- Step 5: Add hydrogens via obabel -----------------------
    if add_hydrogens:
        h_pdb = output_dir / f"{stem}_h.pdb"
        try:
            obabel = _get_obabel()
            cmd = [obabel, str(current_pdb), "-O", str(h_pdb), "-h"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                logger.warning("obabel add-H returned %d: %s", proc.returncode, proc.stderr)
            else:
                current_pdb = h_pdb
                logger.info("Hydrogens added via obabel")
        except FileNotFoundError:
            logger.warning("obabel not found; skipping hydrogen addition")
        except subprocess.TimeoutExpired:
            logger.warning("obabel hydrogen addition timed out")

    result.clean_pdb_path = str(current_pdb)

    # ---- Step 6: Convert to PDBQT --------------------------------
    pdbqt_path = output_dir / f"{stem}.pdbqt"
    pdbqt_ok = False

    # 6a. Try AutoDockTools (prepare_receptor4.py)
    if Path(ADT_PYTHON).is_file() and Path(ADT_PREPARE_RECEPTOR).is_file():
        try:
            cmd = [
                ADT_PYTHON, ADT_PREPARE_RECEPTOR,
                "-r", str(current_pdb),
                "-o", str(pdbqt_path),
                "-A", "hydrogens",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode == 0 and pdbqt_path.is_file():
                pdbqt_ok = True
                logger.info("PDBQT created via AutoDockTools")
            else:
                logger.warning(
                    "ADT prepare_receptor4 failed (rc=%d): %s",
                    proc.returncode, proc.stderr,
                )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("ADT conversion failed: %s", exc)

    # 6b. Fallback to obabel
    if not pdbqt_ok:
        try:
            obabel = _get_obabel()
            cmd = [obabel, str(current_pdb), "-O", str(pdbqt_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode == 0 and pdbqt_path.is_file():
                pdbqt_ok = True
                logger.info("PDBQT created via obabel (fallback)")
            else:
                logger.error("obabel PDBQT conversion failed: %s", proc.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.error("obabel PDBQT conversion failed: %s", exc)

    if pdbqt_ok:
        result.pdbqt_path = str(pdbqt_path)
        result.success = True
        result.message = "Protein preparation completed successfully"
    else:
        result.message = "PDBQT conversion failed with both ADT and obabel"

    logger.info("Protein prep result: %s", result.message)
    return result
