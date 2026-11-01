"""Grid box management for molecular docking in FazeraDock.

Provides the :class:`GridBox` dataclass and functions for automatic grid
generation, Vina argument formatting, and JSON persistence.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .pdb_utils import (
    get_center_of_mass,
    get_ligand_center,
    parse_pdb_atoms,
)

logger = logging.getLogger(__name__)


@dataclass
class GridBox:
    """Defines the search space for a docking run."""

    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    size_x: float = 20.0
    size_y: float = 20.0
    size_z: float = 20.0


# ------------------------------------------------------------------
# Automatic grid generation
# ------------------------------------------------------------------

def auto_grid_from_ligand(
    pdb_path: str | Path,
    ligand_resname: str,
    padding: float = 5.0,
) -> GridBox:
    """Create a grid box centred on an existing ligand.

    The box dimensions are computed from the ligand's bounding box plus
    *padding* Ångströms on each side.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file containing the ligand.
    ligand_resname:
        Three-letter residue name of the ligand.
    padding:
        Extra space (Å) added to each side of the ligand bounding box.
    """
    atoms = parse_pdb_atoms(pdb_path)
    ligand_atoms = [
        a for a in atoms
        if a["res_name"] == ligand_resname and a["element"] not in ("H", "D")
    ]

    if not ligand_atoms:
        logger.warning("Ligand '%s' not found; returning default grid", ligand_resname)
        center = get_center_of_mass(pdb_path)
        return GridBox(center_x=center[0], center_y=center[1], center_z=center[2])

    xs = [a["x"] for a in ligand_atoms]
    ys = [a["y"] for a in ligand_atoms]
    zs = [a["z"] for a in ligand_atoms]

    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0

    sx = (max(xs) - min(xs)) + 2.0 * padding
    sy = (max(ys) - min(ys)) + 2.0 * padding
    sz = (max(zs) - min(zs)) + 2.0 * padding

    grid = GridBox(
        center_x=round(cx, 3),
        center_y=round(cy, 3),
        center_z=round(cz, 3),
        size_x=round(sx, 3),
        size_y=round(sy, 3),
        size_z=round(sz, 3),
    )
    logger.info(
        "Auto-grid from ligand '%s': center=(%.2f, %.2f, %.2f) size=(%.1f, %.1f, %.1f)",
        ligand_resname, grid.center_x, grid.center_y, grid.center_z,
        grid.size_x, grid.size_y, grid.size_z,
    )
    return grid


def auto_grid_from_center_of_mass(
    pdb_path: str | Path,
    size: float = 25.0,
) -> GridBox:
    """Create a cubic grid box centred on the protein's centre of mass.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file.
    size:
        Edge length (Å) for the cubic grid.
    """
    center = get_center_of_mass(pdb_path)
    grid = GridBox(
        center_x=center[0],
        center_y=center[1],
        center_z=center[2],
        size_x=size,
        size_y=size,
        size_z=size,
    )
    logger.info(
        "Auto-grid from COM: center=(%.2f, %.2f, %.2f) size=%.1f",
        grid.center_x, grid.center_y, grid.center_z, size,
    )
    return grid


def auto_grid_whole_protein(
    pdb_path: str | Path,
    padding: float = 10.0,
) -> GridBox:
    """Create a grid box that covers the entire protein plus *padding*.

    Parameters
    ----------
    pdb_path:
        Path to the PDB file.
    padding:
        Extra space (Å) added to each side of the protein bounding box.
    """
    atoms = parse_pdb_atoms(pdb_path)
    heavy = [a for a in atoms if a["element"] not in ("H", "D")]
    if not heavy:
        logger.warning("No heavy atoms found; returning default grid")
        return GridBox()

    xs = [a["x"] for a in heavy]
    ys = [a["y"] for a in heavy]
    zs = [a["z"] for a in heavy]

    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0

    sx = (max(xs) - min(xs)) + 2.0 * padding
    sy = (max(ys) - min(ys)) + 2.0 * padding
    sz = (max(zs) - min(zs)) + 2.0 * padding

    grid = GridBox(
        center_x=round(cx, 3),
        center_y=round(cy, 3),
        center_z=round(cz, 3),
        size_x=round(sx, 3),
        size_y=round(sy, 3),
        size_z=round(sz, 3),
    )
    logger.info(
        "Auto-grid whole protein: center=(%.2f, %.2f, %.2f) size=(%.1f, %.1f, %.1f)",
        grid.center_x, grid.center_y, grid.center_z,
        grid.size_x, grid.size_y, grid.size_z,
    )
    return grid


# ------------------------------------------------------------------
# Vina argument conversion
# ------------------------------------------------------------------

def grid_to_vina_args(grid: GridBox) -> list[str]:
    """Convert a :class:`GridBox` to AutoDock Vina command-line arguments.

    Returns
    -------
    list[str]
        Arguments such as ``["--center_x", "10.0", "--center_y", ...]``.
    """
    return [
        "--center_x", str(grid.center_x),
        "--center_y", str(grid.center_y),
        "--center_z", str(grid.center_z),
        "--size_x", str(grid.size_x),
        "--size_y", str(grid.size_y),
        "--size_z", str(grid.size_z),
    ]


# ------------------------------------------------------------------
# JSON persistence
# ------------------------------------------------------------------

def save_grid(grid: GridBox, path: str | Path) -> None:
    """Save a :class:`GridBox` to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "center_x": grid.center_x,
        "center_y": grid.center_y,
        "center_z": grid.center_z,
        "size_x": grid.size_x,
        "size_y": grid.size_y,
        "size_z": grid.size_z,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    logger.info("Grid saved to %s", path)


def load_grid(path: str | Path) -> GridBox:
    """Load a :class:`GridBox` from a JSON file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    grid = GridBox(**data)
    logger.info("Grid loaded from %s", path)
    return grid
