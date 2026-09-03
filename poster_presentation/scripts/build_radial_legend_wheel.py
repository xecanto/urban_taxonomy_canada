"""
Standalone legend images for the radial taxonomy wheel (build_radial_rings.py),
styled to match the source paper's own legend conventions instead of plain
rectangular swatches: ring characters get small curved ARC swatches (a wedge
of the actual colour ramp), and dendrogram branches get short LINE swatches
(matching the dendrogram's own line style) rather than boxes.

Kept separate from the main wheel image so they can be placed independently
in your own poster layout.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_legend_wheel.py
"""

import argparse
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Wedge

sys.path.insert(0, str(Path(__file__).parent))
import build_radial_dendrogram as dendro
from build_radial_rings import RINGS


def build_ring_legend(data_dir: Path, out_path: Path, dpi: int = 400, width_in: float = 7.0, level: str = "level_5"):
    cdata = pd.read_parquet(data_dir / "cdata.parquet")
    cmap_df = pd.read_parquet(data_dir / "cluster_mapping.parquet")
    n = len(RINGS) + 1  # +1 for the outermost abundance ring (not a character -- bar height, not colour)
    row_h = 0.9
    fig_h = row_h * n + 0.4
    fig, ax = plt.subplots(figsize=(width_in, fig_h), dpi=dpi)
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    # A very gentle bend: 10x the radius of the previous version with the
    # span narrowed to match, so the swatch keeps the same on-page width and
    # thickness but reads as almost-flat. The wedge's own centre sits far
    # below the row (equal to the radius) -- offset it back up by r_avg so
    # the visible sliver still lands at the row's own height, next to its
    # label, instead of blowing out the figure's bounding box.
    chord_w = 0.76  # on-page width of the swatch, matches the earlier version
    arc_r_out, arc_r_in = 1.3, 1
    r_avg = (arc_r_out + arc_r_in) / 2
    span = 2 * math.degrees(math.asin(chord_w / (2 * arc_r_out)))
    n_shades = 5
    for i, r in enumerate(RINGS):
        y = fig_h - 0.5 - i * row_h
        cmap = plt.get_cmap(r["cmap"])
        cx = 0.55
        wedge_cy = y - r_avg
        theta0 = 90 - span / 2
        for k in range(n_shades):
            shade = cmap(0.2 + 0.7 * (k / (n_shades - 1)))
            a0 = theta0 + span * k / n_shades
            a1 = theta0 + span * (k + 1) / n_shades
            w = Wedge((cx, wedge_cy), arc_r_out, a0, a1, width=arc_r_out - arc_r_in, facecolor=shade, edgecolor="white", linewidth=0.5)
            ax.add_patch(w)
        s = cdata[r["col"]]
        lo, hi = s.quantile(0.02), s.quantile(0.98)
        fmt = (lambda v: f"{v:.2f}") if hi < 5 else (lambda v: f"{v:.0f}")
        ax.text(1.15, y, r["label"], fontsize=15, va="center", ha="left", fontweight="bold", color="#222222")
        ax.text(1.15, y - 0.32, f"range {fmt(lo)}–{fmt(hi)}", fontsize=11, va="center", ha="left", color="#777777")

    # -- outermost ring: morphotope abundance -- bar HEIGHT encodes value
    # (log-scaled count), not colour, so it gets a bar-icon swatch instead
    # of an arc, matching build_radial_rings.py's own "#7fb8e0" bar colour.
    counts = cdata.join(cmap_df).groupby(level).size()
    lo_n, hi_n = int(counts.min()), int(counts.max())
    y = fig_h - 0.5 - len(RINGS) * row_h
    cx = 0.55
    bar_color = "#7fb8e0"
    n_bars = 5
    bar_w, gap, max_h = 0.11, 0.05, 0.75
    total_w = n_bars * bar_w + (n_bars - 1) * gap
    x0 = cx - total_w / 2
    for k in range(n_bars):
        h = max_h * ((k + 1) / n_bars) ** 1.6  # same easing shape as the log-scaled bar ring
        bx = x0 + k * (bar_w + gap)
        ax.add_patch(plt.Rectangle((bx, y - max_h / 2), bar_w, h, facecolor=bar_color, edgecolor="none"))
    ax.text(1.15, y, "morphotope abundance (outer ring)", fontsize=15, va="center", ha="left", fontweight="bold", color="#222222")
    ax.text(1.15, y - 0.32, f"{lo_n}–{hi_n} morphotopes per cluster, log-scaled bar length", fontsize=11, va="center", ha="left", color="#777777")

    fig.savefig(out_path, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"saved {out_path}")


def build_branch_legend(dendro_data_path: Path, out_path: Path, dpi: int = 400, width_in: float = 4.5):
    import json
    with open(dendro_data_path, encoding="utf-8") as f:
        summary = json.load(f)
    cluster_ids = sorted(s["cluster"] for s in summary["cluster_summary"].get("level_3", []))
    counts = {s["cluster"]: s["morphotopes"] for s in summary["cluster_summary"].get("level_3", [])}

    n = len(cluster_ids)
    row_h = 0.55
    fig_h = row_h * n + 0.5
    fig, ax = plt.subplots(figsize=(width_in, fig_h), dpi=dpi)
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    ax.text(0.05, fig_h - 0.15, "Fabric branch (level_3)", fontsize=16, fontweight="bold", va="top", ha="left")

    for i, cid in enumerate(cluster_ids):
        y = fig_h - 0.75 - i * row_h
        color = dendro.BOLD_RAMP[i % len(dendro.BOLD_RAMP)]
        ax.plot([0.05, 0.55], [y, y], color=color, linewidth=4.5, solid_capstyle="round")
        ax.text(0.72, y, f"Cluster {cid}", fontsize=13, va="center", ha="left", fontweight="bold", color="#222222")
        ax.text(width_in - 0.1, y, f"{counts.get(cid, 0):,}", fontsize=12, va="center", ha="right", color="#666666")

    fig.savefig(out_path, facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"saved {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default="outputs_canada_cma_ca/09_hierarchy")
    p.add_argument("--dendro-data", default="../urban_taxonomy_viewer/public/data/global_cluster_summary.json")
    p.add_argument("--out-dir", default="poster_presentation/assets/figures")
    p.add_argument("--dpi", type=int, default=400)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    build_ring_legend(Path(args.data_dir), out_dir / "legend_wheel_rings.png", args.dpi)
    build_branch_legend(Path(args.dendro_data), out_dir / "legend_wheel_branches.png", args.dpi)
