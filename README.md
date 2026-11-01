<p align="center">
  <h1 align="center">🧬 FazeraDock</h1>
  <p align="center"><strong>Era of Accessible, User-Friendly Molecular Docking</strong></p>
  <p align="center">
    <a href="https://github.com/MrEgorin/fazeradock">Repository</a> •
    <a href="#features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#documentation">Documentation</a> •
    <a href="#license">License</a>
  </p>
</p>

---

**FazeraDock** is a modern, user-friendly molecular docking platform built on [AutoDock Vina 1.2.7](https://github.com/ccsb-scripps/AutoDock-Vina). It provides an intuitive graphical interface for protein-ligand docking, automatic protein/ligand preparation, integrated 3D visualization with [PyMOL](https://pymol.org/), and publication-quality 2D interaction diagrams.

Part of the **FAZENA** project — making computational chemistry accessible to everyone.

## Features

### 🎯 Molecular Docking
- **AutoDock Vina 1.2.7** engine with full parameter control
- **GPU acceleration** support (Vina-GPU) with automatic GPU detection
- **Flexible screening modes:**
  - Single docking (1 ligand vs 1 receptor)
  - Virtual screening (N ligands vs 1 receptor)
  - Cross-docking (N ligands vs M receptors)

### 🔬 Automatic Preparation
- **Protein preparation pipeline:**
  - Water molecule removal
  - Heteroatom/ligand removal
  - Chain selection
  - Hydrogen addition
  - Automatic PDBQT conversion
- **Ligand preparation:**
  - Support for SDF, MOL2, PDB, SMILES formats
  - Multi-molecule SDF library splitting
  - 3D coordinate generation
  - Batch processing

### 💾 Project Management
- Save and load complete docking configurations
- Store protein, grid box, and parameter settings
- Return to previous experiments instantly
- JSON-based project files

### 🖼️ Visualization
- **3D PyMOL visualization:**
  - Automatic highlighting of interacting amino acids
  - Color-coded interaction types (H-bonds, hydrophobic, ionic, π-stacking)
  - White background for publication-ready images
  - Interactive PyMOL sessions (.pse)
  - High-resolution ray-traced PNG export
- **2D interaction diagrams:**
  - Circular interaction map
  - Color-coded by interaction type
  - Distance annotations
  - Publication-quality matplotlib output

### 🖥️ User Interface
- Modern PyQt5 graphical interface
- Step-by-step workflow: Protein → Ligand → Grid → Dock → Results
- Real-time docking progress and log output
- Sortable results table with CSV export
- One-click visualization

## Requirements

### Software Dependencies
| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Runtime environment |
| AutoDock Vina | 1.2.7 | Docking engine (included) |
| Open Babel | 3.1.1+ | Format conversion |
| PyMOL | 3.0+ (open-source) | 3D visualization |
| PyQt5 | 5.15+ | GUI framework |

### Python Packages
```
numpy
matplotlib
PyQt5
biopython (optional)
```

### Optional
- **NVIDIA GPU + CUDA** — for Vina-GPU acceleration
- **AutoDockTools (MGLTools)** — for advanced PDBQT preparation

## Installation

### 1. Prerequisites

Ensure you have the following installed:
- **Python 3.10+** (or use the PyMOL bundled Python)
- **Open Babel 3.1.1+** ([download](https://openbabel.org/wiki/Category:Installation))
- **PyMOL open-source** ([download](https://pymol.org/))

### 2. Clone the Repository

```bash
git clone https://github.com/MrEgorin/fazeradock.git
cd fazeradock
```

### 3. Install Dependencies

**Windows (using PyMOL's Python):**
```batch
install.bat
```

**Manual installation:**
```bash
pip install numpy matplotlib PyQt5
```

### 4. Run FazeraDock

```batch
run_fazeradock.bat
```

Or directly:
```bash
python run_fazeradock.py
```

## Quick Start

### 1. Load Protein
1. Go to the **Protein** tab
2. Click **"Load Protein (PDB)"** and select your receptor PDB file
3. Review the protein information (chains, residues, waters)
4. Configure preparation options (remove waters, add hydrogens)
5. Click **"Prepare Protein"**

### 2. Load Ligand(s)
1. Go to the **Ligand** tab
2. Choose your screening mode:
   - **Single Ligand** — for one compound
   - **Ligand Library** — for a multi-molecule SDF file
   - **Multiple Files** — for individual ligand files
3. Click **"Prepare Ligand(s)"**

### 3. Configure Grid Box
1. Go to the **Grid** tab
2. Set the search space:
   - **Center on Ligand** — auto-detect from co-crystallized ligand
   - **Center on Protein** — use center of mass
   - **Manual** — enter coordinates directly
3. Adjust grid dimensions and docking parameters

### 4. Run Docking
1. Go to the **Docking** tab
2. Review the docking summary
3. Click **"Start Docking"**
4. Monitor real-time progress

### 5. Analyze Results
1. Go to the **Results** tab
2. Review ranked binding affinities
3. Click **"View 3D in PyMOL"** for interactive visualization
4. Click **"Generate 2D Diagram"** for interaction maps
5. Export results as CSV

## Project Structure

```
fazeradock/
├── bin/                    # AutoDock Vina binaries
│   ├── vina.exe
│   └── vina_split.exe
├── fazeradock/             # Python package
│   ├── __init__.py
│   ├── config.py           # Project/settings management
│   ├── protein_prep.py     # Protein preparation pipeline
│   ├── ligand_prep.py      # Ligand preparation
│   ├── docking_engine.py   # Vina docking execution
│   ├── gpu_detect.py       # GPU auto-detection
│   ├── grid_manager.py     # Grid box management
│   ├── screening.py        # Screening controller
│   ├── results_parser.py   # Results analysis
│   ├── visualization_3d.py # PyMOL 3D visualization
│   ├── interaction_2d.py   # 2D interaction diagrams
│   ├── pdb_utils.py        # PDB file utilities
│   └── gui/                # PyQt5 GUI
│       ├── main_window.py
│       ├── protein_panel.py
│       ├── ligand_panel.py
│       ├── grid_panel.py
│       ├── docking_panel.py
│       ├── results_panel.py
│       ├── project_manager.py
│       └── styles.py
├── results/                # Docking results
├── projects/               # Saved configurations
├── docs/                   # Documentation
├── README.md
├── LICENSE
├── requirements.txt
├── run_fazeradock.py       # Entry point
├── run_fazeradock.bat      # Windows launcher
└── install.bat             # Dependency installer
```

## Docking Engines

### AutoDock Vina 1.2.7 (CPU)
The default engine. Works on all systems. Uses multi-core CPU parallelization.

### Vina-GPU (Optional)
Automatically detected when an NVIDIA GPU with CUDA support is available. Provides significant speedup for virtual screening campaigns.

FazeraDock automatically detects your GPU hardware and selects the optimal engine:

| GPU | Engine | Status |
|-----|--------|--------|
| NVIDIA (CUDA) | Vina-GPU | ✅ Auto-selected |
| AMD Radeon | Vina CPU | ⚠️ GPU not supported |
| No GPU | Vina CPU | ✅ Default |

## Screening Modes

### Single Docking
One ligand against one receptor. Ideal for studying specific protein-ligand interactions.

### Virtual Screening (Library Mode)
Multiple ligands against one receptor. Use with:
- Multi-molecule SDF files
- Directories of individual ligand files
- Results ranked by binding affinity

### Cross-Docking
Multiple ligands against multiple receptors. Useful for:
- Selectivity studies
- Multi-target drug design
- Binding site comparison

## Output Files

All results are saved in the `results/` directory:

```
results/
└── project_name_YYYYMMDD_HHMMSS/
    ├── receptor_ligand/
    │   ├── docking_output.pdbqt    # All poses
    │   ├── best_pose.pdbqt         # Best binding mode
    │   ├── docking.log             # Vina log
    │   ├── visualization.png       # 3D render
    │   ├── visualization.pse       # PyMOL session
    │   ├── interactions_2d.png     # 2D diagram
    │   └── report.txt              # Text report
    ├── summary.csv                 # All results ranked
    └── screening_report.txt        # Overall summary
```

## Interaction Analysis

FazeraDock automatically identifies and classifies protein-ligand interactions:

| Type | Criteria | Color (3D) | Color (2D) |
|------|----------|------------|------------|
| Hydrogen Bond | N/O atoms < 3.5 Å | Cyan | 🔵 Cyan |
| Hydrophobic | C-C < 4.5 Å | Orange | 🟠 Orange |
| Ionic | Charged residues < 4.0 Å | Red | 🔴 Red |
| π-Stacking | Aromatic residues < 5.5 Å | Purple | 🟣 Purple |

## Citation

If you use FazeraDock in your research, please cite:

```bibtex
@software{fazeradock2026,
  title = {FazeraDock: Accessible, User-Friendly Molecular Docking},
  author = {FAZENA Team},
  year = {2026},
  url = {https://github.com/MrEgorin/fazeradock}
}
```

Also cite AutoDock Vina:
```bibtex
@article{eberhardt2021autodock,
  title={AutoDock Vina 1.2.0: New docking methods, expanded force field, and Python bindings},
  author={Eberhardt, Jerome and Santos-Martins, Diogo and Tillack, Andreas F and Forli, Stefano},
  journal={Journal of Chemical Information and Modeling},
  volume={61},
  number={8},
  pages={3891--3898},
  year={2021}
}
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [AutoDock Vina](https://github.com/ccsb-scripps/AutoDock-Vina) — Molecular docking engine
- [Open Babel](https://openbabel.org/) — Chemical format conversion
- [PyMOL](https://pymol.org/) — Molecular visualization (open-source)
- [FAZENA](https://github.com/MrEgorin/fazena) — Parent project

---

<p align="center">
  Made with ❤️ by the FAZENA Team
</p>
