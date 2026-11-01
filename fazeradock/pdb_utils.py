"""PDB file parsing and manipulation utilities for FazeraDock.

Provides functions to parse ATOM/HETATM records, extract chains, residues,
ligands, and perform common cleaning operations on PDB files.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Standard amino-acid and nucleotide residue names.
# HETATM records whose res_name is NOT in this set are considered ligands.
STANDARD_RESIDUES: set[str] = {
    # Amino acids
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    # Common protonation variants
    "HID", "HIE", "HIP", "CYX", "ASH", "GLH",
    # DNA / RNA
    "DA", "DT", "DG", "DC", "A", "U", "G", "C",
    # Water
    "HOH", "WAT", "TIP", "TIP3", "SOL",
}

WATER_RESIDUES: set[str] = {"HOH", "WAT", "TIP", "TIP3", "SOL"}


# ------------------------------------------------------------------
# Parsing
# ------------------------------------------------------------------

def _parse_pdb_line(line: str) -> Optional[dict]:
    """Parse a single ATOM or HETATM line from a PDB file.

    Returns a dictionary with parsed fields or ``None`` if the line is
    not an ATOM/HETATM record.
    """
    record_type = line[0:6].strip()
    if record_type not in ("ATOM", "HETATM"):
        return None

    try:
        return {
            "record_type": record_type,
            "atom_serial": int(line[6:11]),
            "atom_name": line[12:16].strip(),
            "alt_loc": line[16:17].strip(),
            "res_name": line[17:20].strip(),
            "chain_id": line[21:22].strip(),
            "res_seq": int(line[22:26]),
            "x": float(line[30:38]),
            "y": float(line[38:46]),
            "z": float(line[46:54]),
            "occupancy": float(line[54:60]) if len(line) >= 60 and line[54:60].strip() else 1.0,
            "temp_factor": float(line[60:66]) if len(line) >= 66 and line[60:66].strip() else 0.0,
            "element": line[76:78].strip() if len(line) >= 78 else "",
        }
    except (ValueError, IndexError) as exc:
        logger.debug("Failed to parse PDB line: %s — %s", line.rstrip(), exc)
        return None


def parse_pdb_atoms(pdb_path: str | Path) -> list[dict]:
    """Parse all ATOM and HETATM records from a PDB file.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file.

    Returns
    -------
    list[dict]
        Each dict contains fields: record_type, atom_serial, atom_name,
        alt_loc, res_name, chain_id, res_seq, x, y, z, occupancy,
        temp_factor, element.
    """
    pdb_path = Path(pdb_path)
    atoms: list[dict] = []

    try:
        with open(pdb_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                atom = _parse_pdb_line(line)
                if atom is not None:
                    atoms.append(atom)
    except OSError as exc:
        logger.error("Cannot read PDB file %s: %s", pdb_path, exc)
        raise

    logger.info("Parsed %d atoms from %s", len(atoms), pdb_path.name)
    return atoms


# ------------------------------------------------------------------
# Query helpers
# ------------------------------------------------------------------

def get_chains(pdb_path: str | Path) -> list[str]:
    """Return a sorted list of unique chain IDs found in the PDB file."""
    atoms = parse_pdb_atoms(pdb_path)
    chains = sorted({a["chain_id"] for a in atoms if a["chain_id"]})
    logger.info("Chains in %s: %s", Path(pdb_path).name, chains)
    return chains


def get_residues(pdb_path: str | Path, chain: Optional[str] = None) -> list[tuple[str, str, int]]:
    """Return a list of unique residues as ``(chain_id, res_name, res_seq)`` tuples.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file.
    chain:
        If given, restrict results to this chain.
    """
    atoms = parse_pdb_atoms(pdb_path)
    seen: set[tuple[str, str, int]] = set()
    residues: list[tuple[str, str, int]] = []

    for a in atoms:
        if chain is not None and a["chain_id"] != chain:
            continue
        key = (a["chain_id"], a["res_name"], a["res_seq"])
        if key not in seen:
            seen.add(key)
            residues.append(key)

    return residues


def get_waters(pdb_path: str | Path) -> list[dict]:
    """Return all ATOM/HETATM records that belong to water molecules."""
    atoms = parse_pdb_atoms(pdb_path)
    return [a for a in atoms if a["res_name"] in WATER_RESIDUES]


def get_heteroatoms(pdb_path: str | Path) -> list[dict]:
    """Return HETATM records that are *not* water molecules."""
    atoms = parse_pdb_atoms(pdb_path)
    return [
        a for a in atoms
        if a["record_type"] == "HETATM" and a["res_name"] not in WATER_RESIDUES
    ]


def get_center_of_mass(
    pdb_path: str | Path,
    chain: Optional[str] = None,
) -> tuple[float, float, float]:
    """Compute the geometric centre (unweighted) of all heavy atoms.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file.
    chain:
        Restrict to atoms belonging to this chain.

    Returns
    -------
    tuple[float, float, float]
        (x, y, z) coordinates of the centre.
    """
    atoms = parse_pdb_atoms(pdb_path)
    filtered = [
        a for a in atoms
        if (chain is None or a["chain_id"] == chain)
        and a["element"] not in ("H", "D")
    ]

    if not filtered:
        logger.warning("No heavy atoms found for center-of-mass calculation")
        return (0.0, 0.0, 0.0)

    n = len(filtered)
    cx = sum(a["x"] for a in filtered) / n
    cy = sum(a["y"] for a in filtered) / n
    cz = sum(a["z"] for a in filtered) / n

    return (round(cx, 3), round(cy, 3), round(cz, 3))


def get_ligand_center(
    pdb_path: str | Path,
    ligand_resname: str,
) -> tuple[float, float, float]:
    """Compute the geometric centre of a specific ligand residue.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file.
    ligand_resname:
        Three-letter residue name of the ligand (e.g. ``"ATP"``).
    """
    atoms = parse_pdb_atoms(pdb_path)
    ligand_atoms = [
        a for a in atoms
        if a["res_name"] == ligand_resname and a["element"] not in ("H", "D")
    ]

    if not ligand_atoms:
        logger.warning("No atoms found for ligand '%s'", ligand_resname)
        return (0.0, 0.0, 0.0)

    n = len(ligand_atoms)
    cx = sum(a["x"] for a in ligand_atoms) / n
    cy = sum(a["y"] for a in ligand_atoms) / n
    cz = sum(a["z"] for a in ligand_atoms) / n

    return (round(cx, 3), round(cy, 3), round(cz, 3))


# ------------------------------------------------------------------
# PDB manipulation
# ------------------------------------------------------------------

def remove_waters(pdb_path: str | Path, output_path: str | Path) -> int:
    """Write a new PDB file with all water molecules removed.

    Returns the number of water atoms removed.
    """
    pdb_path = Path(pdb_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    removed = 0
    try:
        with open(pdb_path, "r", encoding="utf-8", errors="replace") as fin, \
             open(output_path, "w", encoding="utf-8") as fout:
            for line in fin:
                record = line[0:6].strip()
                if record in ("ATOM", "HETATM"):
                    res_name = line[17:20].strip()
                    if res_name in WATER_RESIDUES:
                        removed += 1
                        continue
                fout.write(line)
    except OSError as exc:
        logger.error("Error removing waters from %s: %s", pdb_path, exc)
        raise

    logger.info("Removed %d water atoms from %s", removed, pdb_path.name)
    return removed


def remove_hetatm(
    pdb_path: str | Path,
    output_path: str | Path,
    keep_resnames: Optional[list[str]] = None,
) -> int:
    """Write a new PDB file with HETATM records removed.

    Parameters
    ----------
    pdb_path:
        Input PDB file.
    output_path:
        Output PDB file.
    keep_resnames:
        If provided, HETATM records whose residue name is in this list
        are preserved.

    Returns
    -------
    int
        Number of HETATM atoms removed.
    """
    pdb_path = Path(pdb_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    keep: set[str] = set(keep_resnames) if keep_resnames else set()

    removed = 0
    try:
        with open(pdb_path, "r", encoding="utf-8", errors="replace") as fin, \
             open(output_path, "w", encoding="utf-8") as fout:
            for line in fin:
                record = line[0:6].strip()
                if record == "HETATM":
                    res_name = line[17:20].strip()
                    if res_name not in keep:
                        removed += 1
                        continue
                fout.write(line)
    except OSError as exc:
        logger.error("Error removing HETATM from %s: %s", pdb_path, exc)
        raise

    logger.info("Removed %d HETATM atoms from %s", removed, pdb_path.name)
    return removed


def select_chain(
    pdb_path: str | Path,
    chain_id: str,
    output_path: str | Path,
) -> None:
    """Extract a single chain from a PDB file.

    Non-ATOM/HETATM records (headers, CONECT, etc.) are preserved.
    """
    pdb_path = Path(pdb_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(pdb_path, "r", encoding="utf-8", errors="replace") as fin, \
             open(output_path, "w", encoding="utf-8") as fout:
            for line in fin:
                record = line[0:6].strip()
                if record in ("ATOM", "HETATM"):
                    ch = line[21:22].strip()
                    if ch != chain_id:
                        continue
                fout.write(line)
    except OSError as exc:
        logger.error("Error selecting chain %s from %s: %s", chain_id, pdb_path, exc)
        raise

    logger.info("Chain '%s' extracted from %s -> %s", chain_id, pdb_path.name, output_path.name)


def detect_existing_ligands(pdb_path: str | Path) -> list[dict]:
    """Detect bound ligands in a PDB file.

    Ligands are identified as HETATM groups whose residue name is not
    in :data:`STANDARD_RESIDUES`.

    Returns
    -------
    list[dict]
        Each dict: ``{res_name, chain_id, res_seq, num_atoms, center}``.
    """
    atoms = parse_pdb_atoms(pdb_path)

    # Group HETATM atoms by (chain, resname, resseq)
    groups: dict[tuple[str, str, int], list[dict]] = {}
    for a in atoms:
        if a["record_type"] != "HETATM":
            continue
        if a["res_name"] in STANDARD_RESIDUES:
            continue
        key = (a["chain_id"], a["res_name"], a["res_seq"])
        groups.setdefault(key, []).append(a)

    ligands: list[dict] = []
    for (chain_id, res_name, res_seq), group_atoms in groups.items():
        heavy = [a for a in group_atoms if a["element"] not in ("H", "D")]
        n = len(heavy) if heavy else len(group_atoms)
        coords = heavy if heavy else group_atoms
        cx = sum(a["x"] for a in coords) / len(coords)
        cy = sum(a["y"] for a in coords) / len(coords)
        cz = sum(a["z"] for a in coords) / len(coords)
        ligands.append({
            "res_name": res_name,
            "chain_id": chain_id,
            "res_seq": res_seq,
            "num_atoms": len(group_atoms),
            "center": (round(cx, 3), round(cy, 3), round(cz, 3)),
        })

    logger.info("Detected %d ligand group(s) in %s", len(ligands), Path(pdb_path).name)
    return ligands
