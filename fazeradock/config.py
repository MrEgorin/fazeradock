# Author: Yehor Franchuk (@MrEgorin) | FAZENA Project
"""Project and settings management for FazeraDock.

Provides the DockingProject dataclass and utilities for saving, loading,
and listing docking projects as JSON files.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Application root directory (parent of the fazeradock package)
APP_DIR: Path = Path(__file__).resolve().parent.parent

# Default directory where projects are stored
PROJECTS_DIR: Path = APP_DIR / "projects"


@dataclass
class DockingProject:
    """Represents a complete molecular docking project configuration."""

    name: str
    protein_path: str = ""
    protein_pdbqt_path: str = ""
    ligand_paths: list[str] = field(default_factory=list)
    grid_center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    grid_size: tuple[float, float, float] = (20.0, 20.0, 20.0)
    exhaustiveness: int = 8
    num_modes: int = 9
    energy_range: int = 3
    cpu: int = 0  # 0 = auto-detect
    seed: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Convert the project to a JSON-serialisable dictionary."""
        data = asdict(self)
        # Tuples become lists in JSON; keep them as lists for round-trip.
        data["grid_center"] = list(self.grid_center)
        data["grid_size"] = list(self.grid_size)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> DockingProject:
        """Construct a DockingProject from a dictionary (e.g. parsed JSON)."""
        # Convert lists back to tuples for grid fields
        if "grid_center" in data and isinstance(data["grid_center"], list):
            data["grid_center"] = tuple(data["grid_center"])
        if "grid_size" in data and isinstance(data["grid_size"], list):
            data["grid_size"] = tuple(data["grid_size"])
        return cls(**data)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def save_project(project: DockingProject, path: str | Path | None = None) -> Path:
    """Save a *DockingProject* to a JSON file.

    Parameters
    ----------
    project:
        The project to save.
    path:
        Explicit file path.  When *None*, the file is written to
        ``PROJECTS_DIR / <project.name>.json``.

    Returns
    -------
    Path
        The absolute path of the written JSON file.
    """
    if path is None:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        path = PROJECTS_DIR / f"{project.name}.json"
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(project.to_dict(), fh, indent=2, ensure_ascii=False)
        logger.info("Project '%s' saved to %s", project.name, path)
    except OSError as exc:
        logger.error("Failed to save project '%s': %s", project.name, exc)
        raise

    return path.resolve()


def load_project(path: str | Path) -> DockingProject:
    """Load a *DockingProject* from a JSON file.

    Parameters
    ----------
    path:
        Path to the JSON file.

    Returns
    -------
    DockingProject
    """
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data: dict = json.load(fh)
        logger.info("Project loaded from %s", path)
        return DockingProject.from_dict(data)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load project from %s: %s", path, exc)
        raise


def list_projects(projects_dir: str | Path | None = None) -> list[dict]:
    """List all saved projects in *projects_dir*.

    Parameters
    ----------
    projects_dir:
        Directory to scan.  Defaults to ``PROJECTS_DIR``.

    Returns
    -------
    list[dict]
        Each dict contains ``name``, ``path``, and ``created_at``.
    """
    projects_dir = Path(projects_dir) if projects_dir else PROJECTS_DIR
    if not projects_dir.exists():
        logger.warning("Projects directory does not exist: %s", projects_dir)
        return []

    results: list[dict] = []
    for json_file in sorted(projects_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            results.append({
                "name": data.get("name", json_file.stem),
                "path": str(json_file),
                "created_at": data.get("created_at", ""),
            })
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping invalid project file %s: %s", json_file, exc)

    return results
