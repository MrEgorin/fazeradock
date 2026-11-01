"""Docking execution engine for FazeraDock.

Wraps AutoDock Vina to run docking jobs, capturing output in real time,
parsing affinities, and saving results to disk.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .grid_manager import GridBox, grid_to_vina_args

logger = logging.getLogger(__name__)

# Path to the AutoDock Vina binary
VINA_PATH: str = r"c:\docs\FAZENA\fazeradock\bin\vina.exe"

# Regex to capture affinity lines from Vina output:
# e.g.  "   1     -7.5      0.000      0.000"
_AFFINITY_RE = re.compile(
    r"^\s*(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*$"
)


# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------

@dataclass
class DockingConfig:
    """Configuration for a single docking run."""

    receptor_pdbqt: str
    ligand_pdbqt: str
    grid: GridBox
    exhaustiveness: int = 8
    num_modes: int = 9
    energy_range: int = 3
    cpu: int = 0  # 0 = auto
    seed: Optional[int] = None
    output_dir: str = ""
    use_gpu: bool = False


@dataclass
class DockingResult:
    """Result of a docking run."""

    output_pdbqt: str = ""
    log_path: str = ""
    best_affinity: float = 0.0
    all_affinities: list[float] = field(default_factory=list)
    runtime_seconds: float = 0.0
    success: bool = False
    message: str = ""
    engine_used: str = ""


# ------------------------------------------------------------------
# Output parsing
# ------------------------------------------------------------------

def parse_vina_output(log_text: str) -> list[dict]:
    """Parse Vina output text for docking modes and affinities.

    Parameters
    ----------
    log_text:
        Full standard-output text from a Vina run.

    Returns
    -------
    list[dict]
        Each dict has keys: ``mode``, ``affinity``, ``rmsd_lb``, ``rmsd_ub``.
    """
    results: list[dict] = []
    for line in log_text.splitlines():
        m = _AFFINITY_RE.match(line)
        if m:
            results.append({
                "mode": int(m.group(1)),
                "affinity": float(m.group(2)),
                "rmsd_lb": float(m.group(3)),
                "rmsd_ub": float(m.group(4)),
            })
    return results


# ------------------------------------------------------------------
# Docking runner
# ------------------------------------------------------------------

def run_docking(
    config: DockingConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> DockingResult:
    """Execute a Vina docking run.

    Parameters
    ----------
    config:
        Docking configuration.
    progress_callback:
        Optional callable that receives status strings in real time.

    Returns
    -------
    DockingResult
    """
    result = DockingResult()

    # Determine output directory
    if config.output_dir:
        out_dir = Path(config.output_dir)
    else:
        out_dir = Path(config.receptor_pdbqt).parent / "docking_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    receptor_stem = Path(config.receptor_pdbqt).stem
    ligand_stem = Path(config.ligand_pdbqt).stem
    output_pdbqt = out_dir / f"{receptor_stem}_{ligand_stem}_out.pdbqt"
    log_path = out_dir / f"{receptor_stem}_{ligand_stem}_log.txt"

    # Resolve engine
    vina_exe = VINA_PATH
    engine_label = "vina"
    if config.use_gpu:
        # GPU-accelerated Vina would use a different binary.
        # For now, fall back to CPU Vina since no NVIDIA GPU is present.
        logger.warning("GPU mode requested but not available; falling back to CPU Vina")
    result.engine_used = engine_label

    # Build command line
    cmd: list[str] = [
        vina_exe,
        "--receptor", config.receptor_pdbqt,
        "--ligand", config.ligand_pdbqt,
        "--out", str(output_pdbqt),
        "--exhaustiveness", str(config.exhaustiveness),
        "--num_modes", str(config.num_modes),
        "--energy_range", str(config.energy_range),
    ]
    cmd.extend(grid_to_vina_args(config.grid))

    if config.cpu > 0:
        cmd.extend(["--cpu", str(config.cpu)])

    if config.seed is not None:
        cmd.extend(["--seed", str(config.seed)])

    logger.info("Vina command: %s", " ".join(cmd))
    if progress_callback:
        progress_callback(f"Starting docking: {ligand_stem} vs {receptor_stem}")

    # Run Vina, capturing output in real time
    t0 = time.perf_counter()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Read stdout line-by-line for real-time progress
        assert proc.stdout is not None
        for line in proc.stdout:
            stripped = line.rstrip("\n\r")
            stdout_lines.append(stripped)
            logger.debug("vina> %s", stripped)
            if progress_callback:
                progress_callback(stripped)

        # Collect remaining stderr
        assert proc.stderr is not None
        stderr_text = proc.stderr.read()
        if stderr_text:
            stderr_lines = stderr_text.splitlines()

        proc.wait()
        elapsed = time.perf_counter() - t0
        result.runtime_seconds = round(elapsed, 2)

        if proc.returncode != 0:
            result.message = (
                f"Vina exited with code {proc.returncode}: "
                + "\n".join(stderr_lines)
            )
            logger.error(result.message)
            return result

    except FileNotFoundError:
        result.message = f"Vina binary not found at {vina_exe}"
        logger.error(result.message)
        return result
    except OSError as exc:
        result.message = f"Failed to run Vina: {exc}"
        logger.error(result.message)
        return result

    # Save log
    full_log = "\n".join(stdout_lines)
    try:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(full_log)
            if stderr_lines:
                fh.write("\n--- STDERR ---\n")
                fh.write("\n".join(stderr_lines))
    except OSError as exc:
        logger.warning("Failed to write log file: %s", exc)

    result.log_path = str(log_path)

    # Parse affinities
    modes = parse_vina_output(full_log)
    if modes:
        result.all_affinities = [m["affinity"] for m in modes]
        result.best_affinity = modes[0]["affinity"]
    else:
        logger.warning("No affinity values parsed from Vina output")

    # Verify output file
    if output_pdbqt.is_file():
        result.output_pdbqt = str(output_pdbqt)
        result.success = True
        result.message = (
            f"Docking completed in {result.runtime_seconds:.1f}s — "
            f"best affinity: {result.best_affinity} kcal/mol"
        )
    else:
        result.message = "Vina completed but output PDBQT file was not created"

    logger.info(result.message)
    if progress_callback:
        progress_callback(result.message)

    return result
