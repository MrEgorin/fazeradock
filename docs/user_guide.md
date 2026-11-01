# FazeraDock User Guide

**Author:** Yehor Franchuk ([@MrEgorin](https://github.com/MrEgorin))
**Project:** FAZENA (Era of Accessible Molecular Docking)

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Interface Overview](#interface-overview)
5. [Protein Preparation](#protein-preparation)
6. [Ligand Preparation](#ligand-preparation)
7. [Grid Box Configuration](#grid-box-configuration)
8. [Running Docking](#running-docking)
9. [Analyzing Results](#analyzing-results)
10. [3D Visualization](#3d-visualization)
11. [2D Interaction Diagrams](#2d-interaction-diagrams)
12. [Project Management](#project-management)
13. [Virtual Screening](#virtual-screening)
14. [GPU Acceleration](#gpu-acceleration)
15. [Troubleshooting](#troubleshooting)
16. [Command-Line Usage](#command-line-usage)

---

## Overview

FazeraDock is a graphical application for molecular docking — the computational prediction of how a small molecule (ligand) binds to a protein (receptor). It wraps AutoDock Vina 1.2.7 with an intuitive interface and adds automatic preparation, visualization, and analysis tools.

### Typical Workflow

```
Load Protein → Prepare Protein → Load Ligand(s) → Prepare Ligand(s) 
    → Configure Grid Box → Run Docking → Analyze Results → Visualize
```

---

## System Requirements

### Minimum
- **OS:** Windows 10/11 (64-bit)
- **RAM:** 4 GB
- **Disk:** 500 MB free
- **CPU:** Any modern x64 processor

### Recommended
- **RAM:** 8+ GB
- **CPU:** 4+ cores (docking speed scales with cores)
- **GPU:** NVIDIA with CUDA (optional, for Vina-GPU)

### Software
- Python 3.10+ (included with PyMOL)
- Open Babel 3.1.1+
- PyMOL 3.0+ open-source

---

## Installation

### Quick Install (Windows)

1. Ensure PyMOL open-source and Open Babel are installed
2. Download or clone FazeraDock
3. Run `install.bat` to install Python dependencies
4. Run `run_fazeradock.bat` to start

### Verifying Installation

After running `install.bat`, you should see:
```
Installation Complete!
Run FazeraDock with: run_fazeradock.bat
```

---

## Interface Overview

FazeraDock uses a tab-based interface with 5 main tabs:

### Protein Tab
Load and prepare receptor proteins. Supports PDB and CIF formats.

### Ligand Tab
Load and prepare ligands. Supports SDF, MOL2, PDB, and SMILES formats. Handles single ligands, libraries, and batch processing.

### Grid Tab
Configure the docking search space (grid box). Set center coordinates, dimensions, and docking parameters.

### Docking Tab
Execute docking calculations. Monitor progress in real-time. Supports single, library, and cross-docking modes.

### Results Tab
View, sort, and export docking results. Launch 3D visualization and generate 2D interaction diagrams.

---

## Protein Preparation

### What is Protein Preparation?

Before docking, the protein structure must be cleaned and converted to PDBQT format. This involves:
- Removing crystallographic water molecules
- Removing co-crystallized ligands and buffer molecules
- Adding hydrogen atoms (critical for accurate docking)
- Assigning partial charges and atom types

### Steps

1. **Load Protein:** Click "Load Protein (PDB)" and select your file
2. **Review Info:** Check the protein summary (chains, residues, waters, ligands)
3. **Configure Options:**
   - ✅ Remove water molecules (recommended)
   - ✅ Remove heteroatoms (recommended unless you need cofactors)
   - Select specific chain if multi-chain protein
   - ✅ Add hydrogens (required)
4. **Prepare:** Click "Prepare Protein" and wait for completion

### Tips
- Always use structures from the PDB (rcsb.org)
- For ensemble docking, prepare each conformer separately
- If a cofactor is essential, uncheck "Remove heteroatoms" or specify it to keep

---

## Ligand Preparation

### Supported Formats
| Format | Extension | Notes |
|--------|-----------|-------|
| SDF | .sdf | Recommended. Supports multi-molecule files |
| MOL2 | .mol2 | Good 3D format with atom types |
| PDB | .pdb | Protein Data Bank format |
| SMILES | .smi | 2D notation, 3D will be generated |

### Single Ligand
Select "Single Ligand" mode and browse for your file.

### Ligand Library
Select "Ligand Library (SDF)" for screening campaigns. FazeraDock will automatically split the multi-molecule SDF file and prepare each ligand individually.

### Multiple Files
Select "Multiple Files" to load several individual ligand files at once.

---

## Grid Box Configuration

The grid box defines where Vina searches for binding poses.

### Auto-Detection Methods

1. **Center on Ligand:** If a co-crystallized ligand exists in the PDB, FazeraDock can center the grid on its position. This is the most reliable method for re-docking studies.

2. **Center on Protein:** Places the grid at the protein's center of mass. Useful when the binding site is unknown.

3. **Whole Protein:** Creates a grid covering the entire protein surface. Use for blind docking (not recommended for large proteins).

### Manual Configuration
Enter X, Y, Z coordinates for the center and dimensions. Typical grid sizes:
- **Focused docking:** 15-25 Å per dimension
- **Blind docking:** 40-60 Å per dimension

### Docking Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| Exhaustiveness | 8 | 1-128 | Search thoroughness. Higher = slower but more accurate |
| Num Modes | 9 | 1-20 | Maximum binding poses to generate |
| Energy Range | 3.0 | 1-10 | Max energy difference from best pose (kcal/mol) |
| CPU Cores | Auto | 1-64 | Number of CPU cores to use |

---

## Running Docking

### Screening Modes

1. **Single:** One ligand vs one receptor
2. **Library:** Multiple ligands vs one receptor (virtual screening)
3. **Cross-docking:** Multiple ligands vs multiple receptors

### Process
1. Verify the docking summary on the Docking tab
2. Click "Start Docking"
3. Monitor progress in the log window
4. Wait for completion (or click "Stop" to cancel)

### Runtime Estimates
- Single docking: 30 seconds - 5 minutes
- Library of 100 ligands: 1-8 hours
- Exhaustiveness 32 is ~4x slower than 8

---

## Analyzing Results

### Results Table
Results are displayed in a sortable table showing:
- Rank (by binding affinity)
- Ligand name
- Receptor name
- Best affinity (kcal/mol) — more negative = stronger binding
- Top 3 mode affinities

### Interpreting Binding Affinities
| Affinity (kcal/mol) | Interpretation |
|---------------------|----------------|
| < -10 | Very strong binding |
| -8 to -10 | Strong binding |
| -6 to -8 | Moderate binding |
| -4 to -6 | Weak binding |
| > -4 | Very weak / no binding |

### Export
Click "Export CSV" to save results as a spreadsheet-compatible CSV file.

---

## 3D Visualization

FazeraDock integrates with PyMOL for publication-quality 3D visualization.

### Automatic Visualization
Click "View 3D in PyMOL" on a selected result to automatically:
- Load the protein and best docking pose
- Color protein by secondary structure
- Highlight interacting residues as sticks
- Show hydrogen bonds as dashed lines
- Label key residues
- Set white background
- Generate high-resolution PNG (2400×1800, 300 DPI)
- Save PyMOL session (.pse)

### Interaction Colors
| Interaction | Residue Color | Line Style |
|-------------|---------------|------------|
| Hydrogen Bond | Cyan | Dashed |
| Hydrophobic | Orange | Solid |
| Ionic | Red | Dotted |
| π-Stacking | Purple | Dash-dot |

### Interactive Mode
Click "Open in PyMOL" to launch the full PyMOL GUI for interactive exploration.

---

## 2D Interaction Diagrams

Generate publication-quality 2D diagrams showing protein-ligand interactions.

The diagram shows:
- Ligand at the center
- Interacting residues arranged in a circle
- Color-coded connection lines by interaction type
- Distance annotations in Angstroms
- Legend with interaction types

---

## Project Management

### Saving Projects
File → Save Project saves all current settings:
- Protein file path and preparation status
- Ligand file paths
- Grid box coordinates and dimensions
- Docking parameters
- Notes

### Loading Projects
File → Open Project or use the Project Manager dialog to browse and load saved projects.

### Project Files
Projects are stored as JSON files in the `projects/` directory.

---

## Virtual Screening

### Preparing a Screening Campaign

1. **Prepare your receptor** in the Protein tab
2. **Load your ligand library** (SDF file) in the Ligand tab
3. **Configure the grid** — use "Center on Ligand" with a known binding site
4. **Increase exhaustiveness** to 16 or 32 for better accuracy
5. **Start docking** in Library mode

### Best Practices
- Use a focused grid box (not whole protein)
- Set exhaustiveness ≥ 16 for screening
- Use at least 4 CPU cores
- Review the top 10-20 hits manually

---

## GPU Acceleration

### Requirements
- NVIDIA GPU with CUDA support
- CUDA Toolkit installed
- Vina-GPU binary

### How It Works
FazeraDock automatically detects your GPU on startup:
- **NVIDIA + CUDA detected:** Uses Vina-GPU
- **AMD or no GPU:** Falls back to Vina CPU

The GPU status is shown in the status bar at the bottom of the window.

---

## Troubleshooting

### Common Issues

**"Open Babel not found"**
- Ensure Open Babel is installed and on your PATH
- Default locations: `C:\Program Files\OpenBabel-3.1.1\`

**"PDBQT conversion failed"**
- Try cleaning the PDB file first (remove problematic atoms)
- Ensure the PDB file is not corrupted
- Check the log for specific error messages

**"PyMOL visualization failed"**
- Ensure PyMOL is installed at `C:\pymol\`
- Check that `pymol` module is importable

**"Docking produces no results"**
- Verify the grid box covers the binding site
- Increase exhaustiveness
- Check that receptor and ligand PDBQT files are valid

### Getting Help
- Check the log output for detailed error messages
- Report issues on GitHub

---

## Command-Line Usage

FazeraDock can also be used from the command line for scripting and automation:

```python
from fazeradock.protein_prep import prepare_protein
from fazeradock.ligand_prep import prepare_ligand
from fazeradock.grid_manager import GridBox, auto_grid_from_ligand
from fazeradock.docking_engine import DockingConfig, run_docking
from fazeradock.visualization_3d import visualize_docking_result

# Prepare protein
result = prepare_protein("receptor.pdb", "output/")

# Prepare ligand
lig = prepare_ligand("ligand.sdf", "output/")

# Configure grid
grid = GridBox(center_x=10.0, center_y=20.0, center_z=30.0,
               size_x=25.0, size_y=25.0, size_z=25.0)

# Run docking
config = DockingConfig(
    receptor_pdbqt=result.pdbqt_path,
    ligand_pdbqt=lig.pdbqt_path,
    grid=grid,
    exhaustiveness=8
)
dock_result = run_docking(config)

# Visualize
visualize_docking_result("receptor.pdb", dock_result.output_pdbqt, "output/")
```
