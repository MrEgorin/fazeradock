# Author: Yehor Franchuk (@MrEgorin) | FAZENA Project
"""
FazeraDock — PyMOL 3D Visualization Module
===========================================

Generates publication-quality 3D renderings and interactive PyMOL sessions
of molecular docking results (receptor + ligand + interactions).

Requires PyMOL 3.0 open-source (``C:\\pymol``) and the FazeraDock backend
utilities :func:`find_interacting_residues` and :func:`classify_interactions`.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VisualizationResult:
    """Encapsulates the output of a 3D visualization run."""

    png_path: str = ""
    session_path: str = ""
    success: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PYMOL_EXE = r"C:\pymol\PyMOLWin.exe"

# Colour palette keyed by interaction_type coming from classify_interactions
_INTERACTION_COLORS: dict[str, str] = {
    "hydrogen_bond": "cyan",
    "hydrophobic": "orange",
    "ionic":        "red",
    "pi_stacking":  "purple",
    "other":        "magenta",
}


def _extract_best_pose_pdb(ligand_pdbqt: str) -> str:
    """Return a temporary PDB-like file containing only MODEL 1 of *ligand_pdbqt*.

    PyMOL can load PDBQT directly, but when the file contains multiple
    models we only want the best (first) pose.  We write a trimmed copy
    so that PyMOL loads exactly one conformer.
    """
    lines: list[str] = []
    in_model = False
    model_count = 0

    with open(ligand_pdbqt, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            tag = line[:6].strip()
            if tag == "MODEL":
                model_count += 1
                if model_count == 1:
                    in_model = True
                    continue          # skip the MODEL record itself
                else:
                    break             # stop after first model
            if tag == "ENDMDL":
                break
            if model_count <= 1:
                # If there is no MODEL record at all, keep everything
                lines.append(line)

    # Write to a temp file that PyMOL can read
    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdbqt", prefix="ligand_pose1_", delete=False, mode="w",
        encoding="utf-8",
    )
    tmp.writelines(lines)
    tmp.close()
    return tmp.name


def _build_interacting_selection(interacting_residues: list[dict]) -> str:
    """Build a PyMOL selection string for the given residues on the receptor."""
    parts: list[str] = []
    for res in interacting_residues:
        chain = res.get("chain", "")
        resseq = res.get("resseq", "")
        if chain:
            parts.append(f"(chain {chain} and resi {resseq})")
        else:
            parts.append(f"(resi {resseq})")
    return " or ".join(parts) if parts else "none"


def _interaction_type_for_residue(
    residue: dict,
    classified: list[dict],
) -> str:
    """Look up the dominant interaction type for *residue* in *classified*."""
    chain = residue.get("chain", "")
    resseq = residue.get("resseq", "")
    # Priority order
    priority = ["hydrogen_bond", "ionic", "pi_stacking", "hydrophobic", "other"]
    types_found: set[str] = set()
    for item in classified:
        if item.get("chain") == chain and str(item.get("resseq")) == str(resseq):
            types_found.add(item.get("interaction_type", "other"))
    for t in priority:
        if t in types_found:
            return t
    return "other"


# ---------------------------------------------------------------------------
# Public API — headless rendering
# ---------------------------------------------------------------------------

def visualize_docking_result(
    receptor_pdb: str,
    ligand_pdbqt: str,
    output_dir: str,
    interacting_residues: list[dict] | None = None,
    session_name: str = "docking_result",
) -> VisualizationResult:
    """Generate a publication-quality 3D rendering of a docking result.

    Parameters
    ----------
    receptor_pdb:
        Path to the receptor PDB file.
    ligand_pdbqt:
        Path to the docked ligand PDBQT file (may contain multiple models).
    output_dir:
        Directory in which to write the PNG image and PSE session.
    interacting_residues:
        Optional pre-computed list from :func:`find_interacting_residues`.
        If *None*, interactions are computed automatically.
    session_name:
        Base filename (without extension) for output files.

    Returns
    -------
    VisualizationResult
        Dataclass with *png_path*, *session_path*, *success*, and *message*.
    """
    result = VisualizationResult()
    tmp_ligand_path: str | None = None

    try:
        # ── validate inputs ───────────────────────────────────────────
        if not os.path.isfile(receptor_pdb):
            result.message = f"Receptor file not found: {receptor_pdb}"
            return result
        if not os.path.isfile(ligand_pdbqt):
            result.message = f"Ligand file not found: {ligand_pdbqt}"
            return result

        os.makedirs(output_dir, exist_ok=True)

        png_path = os.path.join(output_dir, f"{session_name}.png")
        session_path = os.path.join(output_dir, f"{session_name}.pse")

        # ── launch PyMOL headless ─────────────────────────────────────
        import pymol  # type: ignore[import-untyped]
        pymol.finish_launching(["pymol", "-cq"])
        from pymol import cmd  # type: ignore[import-untyped]

        cmd.reinitialize()

        # ── compute interactions if needed ────────────────────────────
        if interacting_residues is None:
            try:
                from fazeradock.results_parser import find_interacting_residues
                interacting_residues = find_interacting_residues(
                    receptor_pdb, ligand_pdbqt, distance_cutoff=4.0,
                )
            except Exception as exc:
                logger.warning("Could not compute interacting residues: %s", exc)
                interacting_residues = []

        # Classify for colour mapping
        classified: list[dict] = []
        try:
            from fazeradock.results_parser import classify_interactions
            classified = classify_interactions(receptor_pdb, ligand_pdbqt, cutoff=4.0)
        except Exception as exc:
            logger.warning("Could not classify interactions: %s", exc)

        # ── load structures ───────────────────────────────────────────
        cmd.load(receptor_pdb, "receptor")

        # Extract first model of ligand
        tmp_ligand_path = _extract_best_pose_pdb(ligand_pdbqt)
        cmd.load(tmp_ligand_path, "ligand")

        # ── style receptor ────────────────────────────────────────────
        cmd.hide("everything", "receptor")
        cmd.show("cartoon", "receptor")

        # Colour by secondary structure
        cmd.color("marine", "receptor and ss H")      # helices  → blue
        cmd.color("tv_yellow", "receptor and ss S")    # sheets   → yellow
        cmd.color("gray80", "receptor and ss L+''")    # loops    → light grey

        cmd.set("cartoon_transparency", 0.3, "receptor")

        # ── style ligand ──────────────────────────────────────────────
        cmd.hide("everything", "ligand")
        cmd.show("sticks", "ligand")
        cmd.color("tv_green", "ligand and elem C")
        cmd.util.cnc("ligand")  # colour non-carbon by element
        cmd.set("stick_radius", 0.2, "ligand")

        # ── highlight interacting residues ────────────────────────────
        if interacting_residues:
            sel_expr = _build_interacting_selection(interacting_residues)
            cmd.select("interacting_res", f"receptor and ({sel_expr})")

            cmd.show("sticks", "interacting_res")

            # Colour each residue by its dominant interaction type
            for res in interacting_residues:
                itype = _interaction_type_for_residue(res, classified)
                colour = _INTERACTION_COLORS.get(itype, "magenta")
                chain = res.get("chain", "")
                resseq = res.get("resseq", "")
                if chain:
                    sel = f"receptor and chain {chain} and resi {resseq}"
                else:
                    sel = f"receptor and resi {resseq}"
                cmd.color(colour, sel)

            # Labels
            cmd.label(
                "interacting_res and name CA",
                '"%s %s" % (resn, resi)',
            )
            cmd.set("label_color", "black")
            cmd.set("label_size", 14)
            cmd.set("label_font_id", 7)

            # Transparent surface around interacting residues
            cmd.show("surface", "interacting_res")
            cmd.set("surface_transparency", 0.7, "interacting_res")
            cmd.set("surface_color", "salmon", "interacting_res")

            # ── polar contacts (H-bonds as dashes) ────────────────────
            try:
                cmd.distance(
                    "hbonds", "ligand", "interacting_res", 3.5, mode=2,
                )
                cmd.set("dash_color", "yellow", "hbonds")
                cmd.set("dash_width", 2.0, "hbonds")
                cmd.hide("labels", "hbonds")
            except Exception as exc:
                logger.warning("Could not draw polar contacts: %s", exc)

        # ── global visual parameters ──────────────────────────────────
        cmd.bg_color("white")
        cmd.set("ray_opaque_background", 1)
        cmd.set("ray_trace_mode", 1)
        cmd.set("antialias", 2)
        cmd.set("orthoscopic", 1)

        # ── camera ────────────────────────────────────────────────────
        cmd.zoom("ligand", 8)
        cmd.orient("ligand")
        cmd.zoom("ligand", 8)  # re-zoom after orient

        # ── save outputs ──────────────────────────────────────────────
        cmd.save(session_path)
        cmd.ray(2400, 1800)
        cmd.png(png_path, dpi=300)

        cmd.reinitialize()

        result.png_path = png_path
        result.session_path = session_path
        result.success = True
        result.message = "Visualization generated successfully."
        logger.info("3D visualization saved: %s, %s", png_path, session_path)

    except Exception as exc:
        result.message = f"Visualization failed: {exc}"
        logger.exception("3D visualization error")
    finally:
        # Clean up temp ligand file
        if tmp_ligand_path and os.path.isfile(tmp_ligand_path):
            try:
                os.remove(tmp_ligand_path)
            except OSError:
                pass

    return result


# ---------------------------------------------------------------------------
# PML script builder (shared by interactive launcher)
# ---------------------------------------------------------------------------

def _build_pml_script(
    receptor_pdb: str,
    ligand_pdbqt: str,
    interacting_residues: list[dict] | None = None,
    classified: list[dict] | None = None,
) -> str:
    """Return a PyMOL command script (.pml) as a string."""
    lines: list[str] = []

    def _w(line: str = "") -> None:
        lines.append(line)

    _w("# FazeraDock — PyMOL visualisation script")
    _w("# Auto-generated — do not edit")
    _w()
    _w("reinitialize")
    _w()

    # Load structures
    _w(f'load {receptor_pdb}, receptor')
    _w(f'load {ligand_pdbqt}, ligand')
    _w()

    # Receptor styling
    _w("hide everything, receptor")
    _w("show cartoon, receptor")
    _w("color marine, receptor and ss H")
    _w("color tv_yellow, receptor and ss S")
    _w("color gray80, receptor and ss L+''")
    _w("set cartoon_transparency, 0.3, receptor")
    _w()

    # Ligand styling
    _w("hide everything, ligand")
    _w("show sticks, ligand")
    _w("color tv_green, ligand and elem C")
    _w("util.cnc ligand")
    _w("set stick_radius, 0.2, ligand")
    _w()

    # Interacting residues
    if interacting_residues:
        sel_expr = _build_interacting_selection(interacting_residues)
        _w(f"select interacting_res, receptor and ({sel_expr})")
        _w("show sticks, interacting_res")
        _w()

        for res in interacting_residues:
            itype = _interaction_type_for_residue(res, classified or [])
            colour = _INTERACTION_COLORS.get(itype, "magenta")
            chain = res.get("chain", "")
            resseq = res.get("resseq", "")
            if chain:
                sel = f"receptor and chain {chain} and resi {resseq}"
            else:
                sel = f"receptor and resi {resseq}"
            _w(f"color {colour}, {sel}")

        _w()
        _w('label interacting_res and name CA, "%s %s" % (resn, resi)')
        _w("set label_color, black")
        _w("set label_size, 14")
        _w("set label_font_id, 7")
        _w()
        _w("show surface, interacting_res")
        _w("set surface_transparency, 0.7, interacting_res")
        _w("set surface_color, salmon, interacting_res")
        _w()

        # Polar contacts
        _w("distance hbonds, ligand, interacting_res, 3.5, mode=2")
        _w("set dash_color, yellow, hbonds")
        _w("set dash_width, 2.0, hbonds")
        _w("hide labels, hbonds")
        _w()

    # Global visual parameters
    _w("bg_color white")
    _w("set ray_opaque_background, 1")
    _w("set ray_trace_mode, 1")
    _w("set antialias, 2")
    _w("set orthoscopic, 1")
    _w()

    # Camera
    _w("zoom ligand, 8")
    _w("orient ligand")
    _w("zoom ligand, 8")
    _w()
    _w("deselect")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API — interactive PyMOL GUI launch
# ---------------------------------------------------------------------------

def launch_pymol_interactive(
    receptor_pdb: str,
    ligand_pdbqt: str,
    interacting_residues: list[dict] | None = None,
) -> None:
    """Open an interactive PyMOL GUI session with the docking result.

    A ``.pml`` script is written to a temporary directory and PyMOL is
    launched with it so the user can freely explore the structure.

    Parameters
    ----------
    receptor_pdb:
        Path to the receptor PDB file.
    ligand_pdbqt:
        Path to the docked ligand PDBQT file.
    interacting_residues:
        Optional pre-computed residue list.  If *None*, interactions are
        computed automatically.
    """
    # Compute interactions if needed
    if interacting_residues is None:
        try:
            from fazeradock.results_parser import find_interacting_residues
            interacting_residues = find_interacting_residues(
                receptor_pdb, ligand_pdbqt, distance_cutoff=4.0,
            )
        except Exception as exc:
            logger.warning("Could not compute interacting residues: %s", exc)
            interacting_residues = []

    classified: list[dict] = []
    try:
        from fazeradock.results_parser import classify_interactions
        classified = classify_interactions(receptor_pdb, ligand_pdbqt, cutoff=4.0)
    except Exception as exc:
        logger.warning("Could not classify interactions: %s", exc)

    pml_content = _build_pml_script(
        receptor_pdb, ligand_pdbqt, interacting_residues, classified,
    )

    # Write .pml to a temp file
    pml_dir = os.path.join(
        os.path.dirname(ligand_pdbqt) or ".", "pymol_scripts",
    )
    os.makedirs(pml_dir, exist_ok=True)
    pml_path = os.path.join(pml_dir, "fazeradock_view.pml")
    with open(pml_path, "w", encoding="utf-8") as fh:
        fh.write(pml_content)

    logger.info("Launching PyMOL GUI with script: %s", pml_path)

    # Launch PyMOL in the background
    pymol_exe = _PYMOL_EXE
    if not os.path.isfile(pymol_exe):
        # Fallback: assume pymol is on PATH
        pymol_exe = "pymol"

    try:
        subprocess.Popen(
            [pymol_exe, pml_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"PyMOL executable not found at '{pymol_exe}'. "
            "Please ensure PyMOL is installed or adjust the path."
        )
