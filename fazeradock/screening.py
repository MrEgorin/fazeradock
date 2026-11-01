# Author: Yehor Franchuk (@MrEgorin) | FAZENA Project
"""Virtual screening controller for FazeraDock.

Supports single docking, library screening (many ligands vs. one receptor),
and cross-docking (many ligands vs. many receptors). Generates summary CSVs
and ranked results.
"""

from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .docking_engine import DockingConfig, DockingResult, run_docking
from .grid_manager import GridBox

logger = logging.getLogger(__name__)


class ScreeningMode(Enum):
    """Modes of virtual screening."""

    SINGLE = "single"
    LIBRARY = "library"   # Many ligands vs 1 receptor
    CROSS = "cross"       # Many ligands vs many receptors


@dataclass
class ScreeningConfig:
    """Configuration for a virtual screening campaign."""

    mode: ScreeningMode = ScreeningMode.SINGLE
    receptor_pdbqts: list[str] = field(default_factory=list)
    ligand_pdbqts: list[str] = field(default_factory=list)
    grid_boxes: dict[str, GridBox] = field(default_factory=dict)
    # grid_boxes maps receptor PDBQT path -> GridBox
    exhaustiveness: int = 8
    num_modes: int = 9
    energy_range: int = 3
    cpu: int = 0
    output_base_dir: str = ""


@dataclass
class ScreeningResult:
    """Aggregated result of a screening run."""

    results: list[DockingResult] = field(default_factory=list)
    summary_csv_path: str = ""
    best_hit: dict = field(default_factory=dict)
    total_runtime: float = 0.0


# ------------------------------------------------------------------
# Summary & ranking
# ------------------------------------------------------------------

def generate_summary_csv(
    results: list[dict],
    output_path: str | Path,
) -> str:
    """Write a CSV summary of screening results.

    Parameters
    ----------
    results:
        List of dicts with keys: receptor, ligand, best_affinity, all_modes.
    output_path:
        Path for the output CSV.

    Returns
    -------
    str
        The absolute path of the written CSV file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["receptor", "ligand", "best_affinity", "all_modes"]
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        logger.info("Summary CSV written to %s", output_path)
    except OSError as exc:
        logger.error("Failed to write summary CSV: %s", exc)
        raise

    return str(output_path.resolve())


def rank_results(results: list[dict]) -> list[dict]:
    """Sort screening results by best affinity (most negative first).

    Parameters
    ----------
    results:
        List of dicts with at least a ``best_affinity`` key.

    Returns
    -------
    list[dict]
        Sorted copy of the list.
    """
    return sorted(results, key=lambda r: r.get("best_affinity", 0.0))


# ------------------------------------------------------------------
# Screening runner
# ------------------------------------------------------------------

def run_screening(
    config: ScreeningConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> ScreeningResult:
    """Execute a virtual screening campaign.

    Parameters
    ----------
    config:
        Screening configuration.
    progress_callback:
        Callable receiving progress messages.

    Returns
    -------
    ScreeningResult
    """
    result = ScreeningResult()
    t0 = time.perf_counter()

    base_dir = Path(config.output_base_dir) if config.output_base_dir else Path("screening_output")
    base_dir.mkdir(parents=True, exist_ok=True)

    # Build the list of (receptor, ligand) pairs to dock
    pairs: list[tuple[str, str]] = []

    if config.mode == ScreeningMode.SINGLE:
        if config.receptor_pdbqts and config.ligand_pdbqts:
            pairs.append((config.receptor_pdbqts[0], config.ligand_pdbqts[0]))

    elif config.mode == ScreeningMode.LIBRARY:
        receptor = config.receptor_pdbqts[0] if config.receptor_pdbqts else ""
        for lig in config.ligand_pdbqts:
            pairs.append((receptor, lig))

    elif config.mode == ScreeningMode.CROSS:
        for rec in config.receptor_pdbqts:
            for lig in config.ligand_pdbqts:
                pairs.append((rec, lig))

    total = len(pairs)
    if total == 0:
        result.total_runtime = 0.0
        result.summary_csv_path = ""
        logger.warning("No docking pairs to process")
        return result

    logger.info("Screening: %d docking job(s) in %s mode", total, config.mode.value)

    summary_rows: list[dict] = []

    for idx, (receptor, ligand) in enumerate(pairs, 1):
        rec_stem = Path(receptor).stem
        lig_stem = Path(ligand).stem
        pair_dir = base_dir / f"{rec_stem}_vs_{lig_stem}"
        pair_dir.mkdir(parents=True, exist_ok=True)

        # Resolve grid box for this receptor
        grid = config.grid_boxes.get(receptor, GridBox())

        status = f"[{idx}/{total}] Docking {lig_stem} vs {rec_stem}"
        logger.info(status)
        if progress_callback:
            progress_callback(status)

        dock_config = DockingConfig(
            receptor_pdbqt=receptor,
            ligand_pdbqt=ligand,
            grid=grid,
            exhaustiveness=config.exhaustiveness,
            num_modes=config.num_modes,
            energy_range=config.energy_range,
            cpu=config.cpu,
            output_dir=str(pair_dir),
        )

        dock_result = run_docking(dock_config, progress_callback=progress_callback)
        result.results.append(dock_result)

        summary_rows.append({
            "receptor": rec_stem,
            "ligand": lig_stem,
            "best_affinity": dock_result.best_affinity,
            "all_modes": ";".join(str(a) for a in dock_result.all_affinities),
        })

    # Generate summary CSV
    csv_path = base_dir / "screening_summary.csv"
    try:
        result.summary_csv_path = generate_summary_csv(summary_rows, csv_path)
    except OSError:
        result.summary_csv_path = ""

    # Determine best hit
    ranked = rank_results(summary_rows)
    if ranked:
        result.best_hit = {
            "ligand": ranked[0]["ligand"],
            "receptor": ranked[0]["receptor"],
            "affinity": ranked[0]["best_affinity"],
        }

    result.total_runtime = round(time.perf_counter() - t0, 2)
    logger.info(
        "Screening complete: %d jobs in %.1f s — best hit: %s",
        total, result.total_runtime, result.best_hit,
    )
    if progress_callback:
        progress_callback(
            f"Screening complete: {total} jobs, best affinity "
            f"{result.best_hit.get('affinity', 'N/A')} kcal/mol"
        )

    return result
