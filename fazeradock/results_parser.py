"""Docking results parsing and interaction analysis for FazeraDock.

Parses multi-model PDBQT files produced by AutoDock Vina, identifies
protein–ligand interactions, and generates text reports.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .pdb_utils import parse_pdb_atoms

logger = logging.getLogger(__name__)

# Residues considered charged for ionic interaction classification
CHARGED_RESIDUES: set[str] = {"ARG", "LYS", "ASP", "GLU", "HIS"}

# Aromatic residues for pi-stacking classification
AROMATIC_RESIDUES: set[str] = {"PHE", "TYR", "TRP", "HIS"}

# Hydrogen-bond donor/acceptor elements
HB_ELEMENTS: set[str] = {"N", "O"}

# Hydrophobic atom element
HYDROPHOBIC_ELEMENT: str = "C"


# ------------------------------------------------------------------
# PDBQT parsing
# ------------------------------------------------------------------

def _parse_pdbqt_atom_line(line: str) -> Optional[dict]:
    """Parse a single ATOM or HETATM line from a PDBQT file.

    PDBQT lines follow PDB-like formatting with the AutoDock atom type
    appended in columns 77–79 and a partial charge in columns 70–76.
    """
    record = line[0:6].strip()
    if record not in ("ATOM", "HETATM"):
        return None

    try:
        atom: dict = {
            "record_type": record,
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
        }
        # Partial charge (columns 70-76 in PDBQT)
        if len(line) >= 77:
            try:
                atom["partial_charge"] = float(line[70:77].strip())
            except ValueError:
                atom["partial_charge"] = 0.0
        else:
            atom["partial_charge"] = 0.0

        # AutoDock atom type (columns 77+)
        if len(line) >= 79:
            atom["ad_type"] = line[77:].strip()
        else:
            atom["ad_type"] = ""

        # Derive element from AD type (first uppercase letter)
        ad = atom["ad_type"]
        if ad:
            atom["element"] = ad[0].upper()
        else:
            atom["element"] = atom["atom_name"][0] if atom["atom_name"] else ""

        return atom
    except (ValueError, IndexError) as exc:
        logger.debug("Failed to parse PDBQT line: %s — %s", line.rstrip(), exc)
        return None


def parse_pdbqt_models(pdbqt_path: str | Path) -> list[dict]:
    """Parse a multi-model PDBQT file (e.g. Vina output).

    Parameters
    ----------
    pdbqt_path:
        Path to the PDBQT file.

    Returns
    -------
    list[dict]
        Each dict contains: ``model_num`` (int), ``affinity`` (float),
        ``atoms`` (list of atom dicts).
    """
    pdbqt_path = Path(pdbqt_path)
    models: list[dict] = []
    current_model: int = 0
    current_affinity: float = 0.0
    current_atoms: list[dict] = []

    try:
        with open(pdbqt_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("MODEL"):
                    parts = line.split()
                    current_model = int(parts[1]) if len(parts) > 1 else len(models) + 1
                    current_atoms = []
                    current_affinity = 0.0

                elif line.startswith("REMARK VINA RESULT:"):
                    # Format: REMARK VINA RESULT:    -7.5      0.000      0.000
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            current_affinity = float(parts[3])
                        except ValueError:
                            pass

                elif line.startswith(("ATOM", "HETATM")):
                    atom = _parse_pdbqt_atom_line(line)
                    if atom:
                        current_atoms.append(atom)

                elif line.startswith("ENDMDL"):
                    models.append({
                        "model_num": current_model,
                        "affinity": current_affinity,
                        "atoms": current_atoms,
                    })

        # Handle single-model files (no MODEL/ENDMDL records)
        if not models and current_atoms:
            models.append({
                "model_num": 1,
                "affinity": current_affinity,
                "atoms": current_atoms,
            })

    except OSError as exc:
        logger.error("Cannot read PDBQT file %s: %s", pdbqt_path, exc)
        raise

    logger.info("Parsed %d model(s) from %s", len(models), pdbqt_path.name)
    return models


def extract_best_pose(pdbqt_path: str | Path, output_path: str | Path) -> None:
    """Extract MODEL 1 (best pose) from a multi-model PDBQT to a separate file.

    Parameters
    ----------
    pdbqt_path:
        Path to the input multi-model PDBQT.
    output_path:
        Path for the output single-model PDBQT.
    """
    pdbqt_path = Path(pdbqt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    in_first_model = False
    found_model = False
    lines_out: list[str] = []

    try:
        with open(pdbqt_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("MODEL"):
                    if not found_model:
                        in_first_model = True
                        found_model = True
                    else:
                        break  # stop at MODEL 2
                elif line.startswith("ENDMDL"):
                    if in_first_model:
                        lines_out.append(line)
                        break
                if in_first_model:
                    lines_out.append(line)

        # Handle files without MODEL records (single model)
        if not found_model:
            with open(pdbqt_path, "r", encoding="utf-8", errors="replace") as fh:
                lines_out = fh.readlines()

        with open(output_path, "w", encoding="utf-8") as fh:
            fh.writelines(lines_out)

        logger.info("Best pose extracted to %s", output_path.name)
    except OSError as exc:
        logger.error("Failed to extract best pose: %s", exc)
        raise


# ------------------------------------------------------------------
# Distance calculation
# ------------------------------------------------------------------

def _distance(a: dict, b: dict) -> float:
    """Euclidean distance between two atom dicts with x, y, z."""
    return math.sqrt(
        (a["x"] - b["x"]) ** 2
        + (a["y"] - b["y"]) ** 2
        + (a["z"] - b["z"]) ** 2
    )


# ------------------------------------------------------------------
# Interaction analysis
# ------------------------------------------------------------------

def find_interacting_residues(
    receptor_pdb: str | Path,
    ligand_pdbqt: str | Path,
    distance_cutoff: float = 4.0,
) -> list[dict]:
    """Find protein residues within *distance_cutoff* of any ligand atom.

    Only heavy atoms (non-hydrogen) are considered.

    Parameters
    ----------
    receptor_pdb:
        Path to the receptor PDB file.
    ligand_pdbqt:
        Path to the ligand PDBQT file (single model or best pose).
    distance_cutoff:
        Distance threshold in Ångströms.

    Returns
    -------
    list[dict]
        Each dict: ``{chain, resname, resseq, closest_distance,
        interacting_atoms}``.
    """
    rec_atoms = parse_pdb_atoms(receptor_pdb)
    lig_models = parse_pdbqt_models(ligand_pdbqt)
    if not lig_models:
        logger.warning("No models found in ligand PDBQT")
        return []

    lig_atoms = lig_models[0]["atoms"]

    # Filter to heavy atoms
    rec_heavy = [a for a in rec_atoms if a["element"] not in ("H", "D")]
    lig_heavy = [a for a in lig_atoms if a["element"] not in ("H", "D")]

    # Accumulate closest contacts per residue
    residue_contacts: dict[tuple[str, str, int], dict] = {}

    for ra in rec_heavy:
        res_key = (ra["chain_id"], ra["res_name"], ra["res_seq"])
        for la in lig_heavy:
            d = _distance(ra, la)
            if d <= distance_cutoff:
                if res_key not in residue_contacts:
                    residue_contacts[res_key] = {
                        "chain": ra["chain_id"],
                        "resname": ra["res_name"],
                        "resseq": ra["res_seq"],
                        "closest_distance": d,
                        "interacting_atoms": [],
                    }
                entry = residue_contacts[res_key]
                if d < entry["closest_distance"]:
                    entry["closest_distance"] = d
                entry["interacting_atoms"].append({
                    "receptor_atom": ra["atom_name"],
                    "ligand_atom": la["atom_name"],
                    "distance": round(d, 2),
                })

    results = list(residue_contacts.values())
    # Round closest distance
    for r in results:
        r["closest_distance"] = round(r["closest_distance"], 2)

    results.sort(key=lambda r: r["closest_distance"])
    logger.info(
        "Found %d interacting residue(s) within %.1f Å",
        len(results), distance_cutoff,
    )
    return results


def classify_interactions(
    receptor_pdb: str | Path,
    ligand_pdbqt: str | Path,
    cutoff: float = 4.0,
) -> list[dict]:
    """Classify protein–ligand interactions by type.

    Interaction types and criteria:

    * **hydrogen_bond** – N or O atoms within 3.5 Å
    * **hydrophobic** – C–C contacts within 4.5 Å
    * **ionic** – charged residues (ARG, LYS, ASP, GLU, HIS) within 4.0 Å
    * **pi_stacking** – aromatic residues (PHE, TYR, TRP, HIS) within 5.5 Å
    * **other** – any contact within *cutoff* not matching above criteria

    Parameters
    ----------
    receptor_pdb:
        Path to the receptor PDB file.
    ligand_pdbqt:
        Path to the ligand PDBQT (best pose).
    cutoff:
        General distance cutoff (Å) for non-specific contacts.

    Returns
    -------
    list[dict]
        Each dict: ``{type, chain, resname, resseq, receptor_atom,
        ligand_atom, distance}``.
    """
    rec_atoms = parse_pdb_atoms(receptor_pdb)
    lig_models = parse_pdbqt_models(ligand_pdbqt)
    if not lig_models:
        return []

    lig_atoms = lig_models[0]["atoms"]
    rec_heavy = [a for a in rec_atoms if a["element"] not in ("H", "D")]
    lig_heavy = [a for a in lig_atoms if a["element"] not in ("H", "D")]

    # Use the largest specific cutoff to pre-filter pairs
    max_cutoff = max(cutoff, 5.5)

    interactions: list[dict] = []

    for ra in rec_heavy:
        for la in lig_heavy:
            d = _distance(ra, la)
            if d > max_cutoff:
                continue

            interaction_type: Optional[str] = None
            rec_elem = ra["element"]
            lig_elem = la["element"]
            res_name = ra["res_name"]

            # Hydrogen bond: N or O atoms within 3.5 Å
            if d <= 3.5 and rec_elem in HB_ELEMENTS and lig_elem in HB_ELEMENTS:
                interaction_type = "hydrogen_bond"

            # Hydrophobic: C–C within 4.5 Å
            elif d <= 4.5 and rec_elem == HYDROPHOBIC_ELEMENT and lig_elem == HYDROPHOBIC_ELEMENT:
                interaction_type = "hydrophobic"

            # Ionic: charged residue within 4.0 Å
            elif d <= 4.0 and res_name in CHARGED_RESIDUES:
                interaction_type = "ionic"

            # Pi-stacking: aromatic residue within 5.5 Å
            elif d <= 5.5 and res_name in AROMATIC_RESIDUES:
                interaction_type = "pi_stacking"

            # Other contact within general cutoff
            elif d <= cutoff:
                interaction_type = "other"

            if interaction_type:
                interactions.append({
                    "type": interaction_type,
                    "chain": ra["chain_id"],
                    "resname": res_name,
                    "resseq": ra["res_seq"],
                    "receptor_atom": ra["atom_name"],
                    "ligand_atom": la["atom_name"],
                    "distance": round(d, 2),
                })

    interactions.sort(key=lambda i: i["distance"])
    logger.info("Classified %d interaction(s)", len(interactions))
    return interactions


def generate_results_report(
    docking_result: "DockingResult",  # noqa: F821
    receptor_pdb: str | Path,
    output_dir: str | Path,
) -> str:
    """Generate a plain-text report for a docking result.

    The report includes binding energies, interacting residues, and
    interaction-type classification.

    Parameters
    ----------
    docking_result:
        A :class:`~fazeradock.docking_engine.DockingResult` instance.
    receptor_pdb:
        Path to the receptor PDB used in docking.
    output_dir:
        Directory to write the report file.

    Returns
    -------
    str
        Absolute path to the generated report file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "docking_report.txt"
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("  FazeraDock — Docking Results Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Engine used     : {docking_result.engine_used}")
    lines.append(f"  Runtime         : {docking_result.runtime_seconds:.1f} s")
    lines.append(f"  Output PDBQT    : {docking_result.output_pdbqt}")
    lines.append(f"  Log file        : {docking_result.log_path}")
    lines.append("")

    # Binding energies
    lines.append("-" * 60)
    lines.append("  Binding Energies (kcal/mol)")
    lines.append("-" * 60)
    if docking_result.all_affinities:
        for i, aff in enumerate(docking_result.all_affinities, 1):
            marker = " <-- best" if i == 1 else ""
            lines.append(f"    Mode {i:>2d}:  {aff:>7.1f}{marker}")
    else:
        lines.append("    No affinity data available.")
    lines.append("")

    # Interaction analysis (only if output PDBQT exists)
    if docking_result.output_pdbqt and Path(docking_result.output_pdbqt).is_file():
        try:
            residues = find_interacting_residues(
                receptor_pdb, docking_result.output_pdbqt, distance_cutoff=4.0
            )
            lines.append("-" * 60)
            lines.append("  Interacting Residues (within 4.0 Å)")
            lines.append("-" * 60)
            if residues:
                for r in residues:
                    lines.append(
                        f"    {r['chain']}:{r['resname']}{r['resseq']}  "
                        f"closest: {r['closest_distance']:.2f} Å  "
                        f"contacts: {len(r['interacting_atoms'])}"
                    )
            else:
                lines.append("    No interacting residues found.")
            lines.append("")

            # Interaction types
            interactions = classify_interactions(
                receptor_pdb, docking_result.output_pdbqt, cutoff=4.0
            )
            lines.append("-" * 60)
            lines.append("  Interaction Classification")
            lines.append("-" * 60)
            if interactions:
                # Summarise by type
                type_counts: dict[str, int] = {}
                for ix in interactions:
                    t = ix["type"]
                    type_counts[t] = type_counts.get(t, 0) + 1
                for t, count in sorted(type_counts.items()):
                    lines.append(f"    {t:<20s}: {count} contact(s)")
                lines.append("")
                # Detailed list (top 20)
                lines.append("  Top contacts:")
                for ix in interactions[:20]:
                    lines.append(
                        f"    {ix['type']:<16s}  "
                        f"{ix['chain']}:{ix['resname']}{ix['resseq']}:{ix['receptor_atom']} — "
                        f"LIG:{ix['ligand_atom']}  {ix['distance']:.2f} Å"
                    )
            else:
                lines.append("    No classified interactions found.")

        except Exception as exc:
            lines.append(f"  [Interaction analysis failed: {exc}]")
            logger.warning("Interaction analysis failed: %s", exc)

    lines.append("")
    lines.append("=" * 60)
    lines.append("  End of Report")
    lines.append("=" * 60)

    report_text = "\n".join(lines)
    try:
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(report_text)
        logger.info("Report written to %s", report_path)
    except OSError as exc:
        logger.error("Failed to write report: %s", exc)
        raise

    return str(report_path.resolve())
