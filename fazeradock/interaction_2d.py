"""
FazeraDock — 2D Interaction Diagram Module
============================================

Generates publication-quality 2D radial interaction diagrams and tabular
summary images of ligand–receptor contacts using **matplotlib**.

Requires :func:`fazeradock.results_parser.find_interacting_residues` and
:func:`fazeradock.results_parser.classify_interactions` from the backend.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour / style palette
# ---------------------------------------------------------------------------

_INTERACTION_STYLES: dict[str, dict] = {
    "hydrogen_bond": {
        "color":     "#00BCD4",
        "linestyle": "--",       # dashed
        "label":     "H-bond",
    },
    "hydrophobic": {
        "color":     "#FF9800",
        "linestyle": "-",        # solid
        "label":     "Hydrophobic",
    },
    "ionic": {
        "color":     "#F44336",
        "linestyle": ":",        # dotted
        "label":     "Ionic",
    },
    "pi_stacking": {
        "color":     "#9C27B0",
        "linestyle": "-.",       # dash-dot
        "label":     "π-stacking",
    },
    "other": {
        "color":     "#9E9E9E",
        "linestyle": "-",
        "label":     "Other",
    },
}


def _style_for(interaction_type: str) -> dict:
    return _INTERACTION_STYLES.get(interaction_type, _INTERACTION_STYLES["other"])


# ---------------------------------------------------------------------------
# Internal drawing helpers
# ---------------------------------------------------------------------------

def _draw_rounded_rect(
    ax,
    cx: float,
    cy: float,
    width: float,
    height: float,
    facecolor: str,
    edgecolor: str = "black",
    linewidth: float = 1.5,
    alpha: float = 0.85,
    zorder: int = 3,
):
    """Draw a rounded rectangle centred at (*cx*, *cy*)."""
    from matplotlib.patches import FancyBboxPatch  # type: ignore[import-untyped]

    patch = FancyBboxPatch(
        (cx - width / 2, cy - height / 2),
        width,
        height,
        boxstyle="round,pad=0.05",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        alpha=alpha,
        zorder=zorder,
    )
    ax.add_patch(patch)


def _draw_central_ligand(ax, label: str, radius: float = 0.22):
    """Draw the central ligand circle."""
    from matplotlib.patches import Circle as MplCircle  # type: ignore[import-untyped]

    circle = MplCircle(
        (0.0, 0.0),
        radius,
        facecolor="#4CAF50",
        edgecolor="#2E7D32",
        linewidth=2.5,
        zorder=5,
        alpha=0.9,
    )
    ax.add_patch(circle)
    # Multi-line label: "Ligand" on top, filename below
    ax.text(
        0, 0.03, "Ligand",
        ha="center", va="center", fontsize=11, fontweight="bold",
        color="white", zorder=6,
    )
    # Truncate long filenames
    short = label if len(label) <= 18 else label[:15] + "…"
    ax.text(
        0, -0.06, short,
        ha="center", va="center", fontsize=7.5,
        color="white", zorder=6, style="italic",
    )


# ---------------------------------------------------------------------------
# Public API — radial 2D interaction diagram
# ---------------------------------------------------------------------------

def generate_2d_interaction_diagram(
    receptor_pdb: str,
    ligand_pdbqt: str,
    output_path: str,
    title: str = "Ligand–Receptor Interactions",
) -> str:
    """Create a publication-quality 2D radial interaction diagram.

    Parameters
    ----------
    receptor_pdb:
        Path to the receptor PDB file.
    ligand_pdbqt:
        Path to the docked ligand PDBQT file.
    output_path:
        Destination PNG file path.
    title:
        Figure title.

    Returns
    -------
    str
        Absolute path to the saved PNG image.
    """
    # ── gather interactions ───────────────────────────────────────────
    from fazeradock.results_parser import (
        find_interacting_residues,
        classify_interactions,
    )

    residues = find_interacting_residues(receptor_pdb, ligand_pdbqt, distance_cutoff=4.0)
    classified = classify_interactions(receptor_pdb, ligand_pdbqt, cutoff=4.0)

    try:
        import matplotlib
        matplotlib.use("Agg")  # headless backend
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    except ImportError:
        # Fallback to Pillow if matplotlib is not installed
        return _generate_2d_pillow(
            residues=residues,
            classified=classified,
            output_path=output_path,
            title=title,
            ligand_name=Path(ligand_pdbqt).stem,
        )

    # Build a per-residue record with its dominant interaction type + distance
    residue_records: list[dict] = []
    for res in residues:
        chain = res.get("chain", "")
        resseq = res.get("resseq", "")
        resname = res.get("resname", "UNK")
        closest_dist = res.get("closest_distance", 0.0)

        # Find best (highest-priority) interaction type
        priority = ["hydrogen_bond", "ionic", "pi_stacking", "hydrophobic", "other"]
        types_found: set[str] = set()
        min_dist = closest_dist
        for item in classified:
            if item.get("chain") == chain and str(item.get("resseq")) == str(resseq):
                types_found.add(item.get("interaction_type", "other"))
                d = item.get("distance", 999.0)
                if d < min_dist:
                    min_dist = d
        best_type = "other"
        for t in priority:
            if t in types_found:
                best_type = t
                break

        residue_records.append({
            "chain": chain,
            "resname": resname,
            "resseq": resseq,
            "interaction_type": best_type,
            "distance": round(min_dist, 2),
        })

    n = len(residue_records)

    # ── create figure ─────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 12), dpi=300)
    ax.set_aspect("equal")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.axis("off")

    ligand_name = Path(ligand_pdbqt).stem
    _draw_central_ligand(ax, ligand_name, radius=0.22)

    if n == 0:
        # No interactions — just show the ligand
        ax.text(
            0, -0.40, "No interactions detected",
            ha="center", va="center", fontsize=13, color="#757575",
        )
        ax.set_xlim(-1, 1)
        ax.set_ylim(-1, 1)
        fig.suptitle(title, fontsize=18, fontweight="bold", y=0.95)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        logger.info("2D diagram saved (no interactions): %s", output_path)
        return os.path.abspath(output_path)

    # Adaptive layout parameters
    ring_radius = 0.55 + 0.015 * max(0, n - 8)   # grow ring for many residues
    box_w = 0.20
    box_h = 0.10

    # Check if we have multiple chains (show chain ID on labels)
    chains_present = {r["chain"] for r in residue_records if r["chain"]}
    show_chain = len(chains_present) > 1

    # ── place residues on a circle ────────────────────────────────────
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]

    for idx, (rec, angle) in enumerate(zip(residue_records, angles)):
        rx = ring_radius * math.cos(angle)
        ry = ring_radius * math.sin(angle)

        style = _style_for(rec["interaction_type"])
        colour = style["color"]

        # Rounded rectangle for residue
        _draw_rounded_rect(
            ax, rx, ry, box_w, box_h, facecolor=colour,
            edgecolor="#424242", linewidth=1.2,
        )

        # Residue label
        label = f"{rec['resname']} {rec['resseq']}"
        if show_chain and rec["chain"]:
            label += f" ({rec['chain']})"
        ax.text(
            rx, ry, label,
            ha="center", va="center", fontsize=8, fontweight="bold",
            color="white", zorder=4,
        )

        # Connection line from ligand centre to residue
        # Shorten line so it starts at ligand circle edge and ends at box edge
        dx, dy = rx, ry
        dist_to_center = math.hypot(dx, dy)
        if dist_to_center == 0:
            continue
        ux, uy = dx / dist_to_center, dy / dist_to_center

        start_r = 0.23  # just past ligand circle
        end_r = dist_to_center - box_w / 2 - 0.02

        x0, y0 = ux * start_r, uy * start_r
        x1, y1 = ux * end_r, uy * end_r

        ax.plot(
            [x0, x1], [y0, y1],
            linestyle=style["linestyle"],
            linewidth=1.8,
            color=colour,
            alpha=0.8,
            zorder=2,
        )

        # Distance annotation at midpoint of line
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2
        # Offset the label perpendicular to the line direction
        perp_x, perp_y = -uy * 0.03, ux * 0.03
        ax.text(
            mx + perp_x, my + perp_y,
            f"{rec['distance']:.1f} Å",
            ha="center", va="center", fontsize=6.5,
            color="#616161", zorder=4,
            bbox=dict(
                boxstyle="round,pad=0.15", facecolor="white",
                edgecolor="none", alpha=0.85,
            ),
        )

    # ── legend ────────────────────────────────────────────────────────
    from matplotlib.lines import Line2D  # type: ignore[import-untyped]

    legend_handles: list = []
    types_in_diagram = {r["interaction_type"] for r in residue_records}
    for itype in ["hydrogen_bond", "hydrophobic", "ionic", "pi_stacking", "other"]:
        if itype not in types_in_diagram:
            continue
        s = _INTERACTION_STYLES[itype]
        handle = Line2D(
            [0], [0],
            color=s["color"],
            linestyle=s["linestyle"],
            linewidth=3,
            marker="s",
            markersize=10,
            markerfacecolor=s["color"],
            markeredgecolor="#424242",
            label=s["label"],
        )
        legend_handles.append(handle)

    if legend_handles:
        leg = ax.legend(
            handles=legend_handles,
            loc="lower center",
            ncol=min(len(legend_handles), 5),
            fontsize=10,
            frameon=True,
            framealpha=0.9,
            edgecolor="#BDBDBD",
            fancybox=True,
            bbox_to_anchor=(0.5, -0.02),
        )
        leg.set_zorder(10)

    # ── axis limits and title ─────────────────────────────────────────
    margin = ring_radius + 0.25
    ax.set_xlim(-margin, margin)
    ax.set_ylim(-margin - 0.10, margin + 0.08)

    fig.suptitle(title, fontsize=18, fontweight="bold", y=0.96)

    # ── save ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    abs_path = os.path.abspath(output_path)
    logger.info("2D interaction diagram saved: %s", abs_path)
    return abs_path


# ---------------------------------------------------------------------------
# Public API — tabular interaction summary image
# ---------------------------------------------------------------------------

def generate_interaction_table_image(
    interactions: list[dict],
    output_path: str,
    title: str = "Interaction Summary",
) -> str:
    """Create a clean table image summarising ligand–receptor interactions.

    Parameters
    ----------
    interactions:
        List of dicts from :func:`classify_interactions`.  Each dict must
        have keys: *chain*, *resname*, *resseq*, *interaction_type*,
        *distance*, *receptor_atom*, *ligand_atom*.
    output_path:
        Destination PNG file path.
    title:
        Table title.

    Returns
    -------
    str
        Absolute path to the saved PNG image.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # ── build table data ──────────────────────────────────────────────
    col_labels = ["Residue", "Chain", "Type", "Distance (Å)", "Receptor Atom", "Ligand Atom"]

    if not interactions:
        cell_data = [["—"] * len(col_labels)]
        row_colors = [["#F5F5F5"] * len(col_labels)]
    else:
        cell_data: list[list[str]] = []
        row_colors: list[list[str]] = []
        for idx, item in enumerate(interactions):
            resname = item.get("resname", "UNK")
            resseq = item.get("resseq", "?")
            chain = item.get("chain", "—")
            itype = item.get("interaction_type", "other")
            dist = item.get("distance", 0.0)
            r_atom = item.get("receptor_atom", "—")
            l_atom = item.get("ligand_atom", "—")

            style = _style_for(itype)
            type_label = style["label"]

            cell_data.append([
                f"{resname} {resseq}",
                chain if chain else "—",
                type_label,
                f"{dist:.2f}",
                str(r_atom),
                str(l_atom),
            ])

            # Alternate row background; tint with interaction colour
            base = "#FFFFFF" if idx % 2 == 0 else "#F5F5F5"
            row_colors.append([base] * len(col_labels))

    n_rows = len(cell_data)
    fig_height = max(2.0, 0.8 + n_rows * 0.45)
    fig, ax = plt.subplots(figsize=(12, fig_height), dpi=300)
    ax.axis("off")

    table = ax.table(
        cellText=cell_data,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.6)

    # Style header
    for col_idx in range(len(col_labels)):
        cell = table[0, col_idx]
        cell.set_facecolor("#37474F")
        cell.set_text_props(color="white", fontweight="bold", fontsize=10)
        cell.set_edgecolor("#263238")

    # Style data rows
    for row_idx in range(1, n_rows + 1):
        for col_idx in range(len(col_labels)):
            cell = table[row_idx, col_idx]
            cell.set_facecolor(row_colors[row_idx - 1][col_idx])
            cell.set_edgecolor("#E0E0E0")
            # Colour the "Type" column text by interaction colour
            if col_idx == 2 and interactions:
                item = interactions[row_idx - 1]
                style = _style_for(item.get("interaction_type", "other"))
                cell.set_text_props(
                    color=style["color"], fontweight="bold",
                )

    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    abs_path = os.path.abspath(output_path)
    logger.info("Interaction table image saved: %s", abs_path)
    return abs_path


# ---------------------------------------------------------------------------
# Pillow Fallback Renderer
# ---------------------------------------------------------------------------

def _generate_2d_pillow(
    residues: Sequence[dict],
    classified: Sequence[dict],
    output_path: str,
    title: str,
    ligand_name: str,
) -> str:
    """Pure-Python fallback rendering of 2D interaction diagram via PIL/Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1200, 1200
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    cx, cy = width // 2, height // 2 - 30

    # Draw Title
    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_bold = ImageFont.truetype("arialbd.ttf", 16)
        font_regular = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font_title = font_bold = font_regular = font_small = ImageFont.load_default()

    draw.text((cx, 40), title, fill="#212121", font=font_title, anchor="mt")

    # Match residues to interactions
    res_type_map: dict[tuple[str, int], dict] = {}
    for item in classified:
        key = (item["chain"], item["resseq"])
        if key not in res_type_map or item.get("distance", 99.0) < res_type_map[key].get("distance", 99.0):
            res_type_map[key] = item

    ring_residues = []
    for r in residues:
        k = (r["chain"], r["resseq"])
        c_info = res_type_map.get(k, {})
        itype = c_info.get("interaction_type", "other")
        dist = c_info.get("distance", r.get("closest_distance", 3.5))
        ring_residues.append({
            "chain": r["chain"],
            "resname": r["resname"],
            "resseq": r["resseq"],
            "interaction_type": itype,
            "distance": dist,
        })

    # Sort residues around ring
    ring_residues.sort(key=lambda x: (x["interaction_type"], x["resseq"]))

    n_res = len(ring_residues)
    radius = 380

    # Draw Central Ligand
    lig_r = 75
    draw.ellipse([cx - lig_r, cy - lig_r, cx + lig_r, cy + lig_r], fill="#1565C0", outline="#0D47A1", width=3)
    draw.text((cx, cy - 12), "LIGAND", fill="white", font=font_bold, anchor="mm")
    short_lig = ligand_name[:16] + ("…" if len(ligand_name) > 16 else "")
    draw.text((cx, cy + 12), short_lig, fill="#BBDEFB", font=font_small, anchor="mm")

    # Hex to RGB helper
    def _hex2rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    # Color map
    color_map = {
        "hydrogen_bond": "#00BCD4",
        "hydrophobic": "#FF9800",
        "ionic": "#F44336",
        "pi_stacking": "#9C27B0",
        "other": "#9E9E9E",
    }

    if n_res == 0:
        draw.text((cx, cy + 120), "No direct residue contacts detected within cutoff.", fill="#757575", font=font_regular, anchor="mm")
    else:
        for idx, res in enumerate(ring_residues):
            angle = (2 * math.pi * idx) / n_res - math.pi / 2
            rx = cx + int(radius * math.cos(angle))
            ry = cy + int(radius * math.sin(angle))

            itype = res["interaction_type"]
            hex_col = color_map.get(itype, "#9E9E9E")
            rgb_col = _hex2rgb(hex_col)

            # Draw connector line
            draw.line([(cx, cy), (rx, ry)], fill=rgb_col, width=2)

            # Distance text near midpoint
            mx = int(cx * 0.45 + rx * 0.55)
            my = int(cy * 0.45 + ry * 0.55)
            dist_str = f"{res['distance']:.2f} Å"
            draw.rectangle([mx - 24, my - 10, mx + 24, my + 10], fill="white", outline="#E0E0E0")
            draw.text((mx, my), dist_str, fill="#424242", font=font_small, anchor="mm")

            # Draw residue badge
            bw, bh = 55, 26
            draw.rounded_rectangle([rx - bw, ry - bh, rx + bw, ry + bh], radius=8, fill=rgb_col, outline="#212121", width=1)
            label = f"{res['resname']} {res['resseq']}"
            draw.text((rx, ry), label, fill="white", font=font_bold, anchor="mm")

    # Draw Legend at bottom
    leg_y = height - 60
    leg_items = [
        ("H-bond", "#00BCD4"),
        ("Hydrophobic", "#FF9800"),
        ("Ionic", "#F44336"),
        ("π-stacking", "#9C27B0"),
        ("Other", "#9E9E9E"),
    ]
    total_w = len(leg_items) * 160
    start_x = (width - total_w) // 2

    for i, (lname, lcol) in enumerate(leg_items):
        lx = start_x + i * 160
        draw.rectangle([lx, leg_y, lx + 20, leg_y + 14], fill=_hex2rgb(lcol), outline="#424242")
        draw.text((lx + 28, leg_y + 7), lname, fill="#212121", font=font_regular, anchor="lm")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, "PNG")
    logger.info("2D interaction diagram (Pillow) saved: %s", output_path)
    return os.path.abspath(output_path)

