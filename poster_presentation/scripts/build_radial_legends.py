"""
Build the small colour-binned distribution histograms that sit under the
radial taxonomy wheel (one per character ring), matching the source paper's
"Selected morphometric characters" legend row style. Each character gets its
own standalone PNG.

Reusable — rerun any time the underlying data or ring definitions change.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_legends.py
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_radial_legends.py --data-dir outputs_canada_cma_ca_nochm/09_hierarchy
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ring definitions: column, human label, unit, colormap, output filename.
# Keep in sync with the rings used in the main radial taxonomy figure.
#
# Selection criteria: real, informative spread across the 58,684 morphotopes
# -- not just "used in the source paper". Checked via quantiles + fraction of
# rows at a single value before picking these 5. Dropped as too degenerate to
# visualize meaningfully: ltbIBD (98.4% of rows exactly 0), lcdMes (43% at 0),
# xcnSCl (92% at 0), mibCou (96% at exactly 1) -- these would render as a
# nearly-solid spike with almost nothing else visible, not a real histogram.
RINGS = [
    {"col": "sdbAre",    "label": "building area",             "unit": "m²", "cmap": "Oranges", "out": "legend_building_area.png"},
    {"col": "ssbCCo",    "label": "building compactness",       "unit": "",   "cmap": "Blues",   "out": "legend_building_compactness.png"},
    {"col": "sicCAR",    "label": "coverage area ratio",        "unit": "",   "cmap": "Purples", "out": "legend_coverage_ratio.png"},
    {"col": "mtbNDi",    "label": "distance to neighbouring buildings", "unit": "m", "cmap": "Reds", "out": "legend_neighbour_distance.png"},
    {"col": "chm_cover", "label": "canopy cover", "unit": "",   "cmap": "Greens",  "out": "legend_canopy_cover.png"},
]

N_BINS = 5
HIST_BINS = 40


def build_one(series: pd.Series, ring: dict, out_dir: Path, dpi: int = 400, size_px: int = 960):
    lo, hi = series.quantile(0.01), series.quantile(0.99)
    clipped = series.clip(lo, hi)

    unit = f" [{ring['unit']}]" if ring["unit"] else ""
    label_chars = len(ring["label"]) + len(unit)
    # Widen the panel if the label is too long to fit the default width.
    # ~12.5px/char at 150dpi was the empirical fit (checked against actual
    # rendered output); scale it with dpi since px/char is dpi-dependent
    # (points -> pixels), not a fixed constant.
    min_w_px = label_chars * 12.5 * (dpi / 150) + 40
    w_px = max(size_px, min_w_px)
    fig_w, fig_h = w_px / dpi, (size_px * 0.62) / dpi
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    counts, edges = np.histogram(clipped, bins=HIST_BINS, range=(lo, hi))
    centers = (edges[:-1] + edges[1:]) / 2
    bin_of_center = np.clip((centers - lo) / (hi - lo + 1e-12), 0, 1)
    quantile_bin = np.clip((bin_of_center * N_BINS).astype(int), 0, N_BINS - 1)

    cmap = plt.get_cmap(ring["cmap"])
    shades = [cmap(0.25 + 0.65 * (i / (N_BINS - 1))) for i in range(N_BINS)]
    colors = [shades[q] for q in quantile_bin]

    width = (edges[1] - edges[0]) * 0.98
    ax.bar(centers, counts, width=width, color=colors, edgecolor="none")

    ax.set_yticks([])
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#888888")
    ax.spines["bottom"].set_linewidth(1)

    ax.set_xticks([lo, hi])
    fmt = (lambda v: f"{v:.2f}") if hi < 5 else (lambda v: f"{v:.0f}")
    ax.set_xticklabels([fmt(lo), fmt(hi)], fontsize=10)
    ax.tick_params(axis="x", length=3, pad=2)

    ax.set_xlabel(f"{ring['label']}{unit}", fontsize=11, labelpad=6)

    fig.tight_layout(pad=0.3)
    out_path = out_dir / ring["out"]
    fig.savefig(out_path, facecolor="white", transparent=False)
    plt.close(fig)
    print(f"saved {out_path}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default="outputs_canada_cma_ca/09_hierarchy")
    p.add_argument("--out-dir", default="poster_presentation/assets/figures")
    p.add_argument("--dpi", type=int, default=400)
    p.add_argument("--size-px", type=int, default=960, help="Width in px at --dpi")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cdata = pd.read_parquet(data_dir / "cdata.parquet")

    for ring in RINGS:
        if ring["col"] not in cdata.columns:
            print(f"SKIP {ring['col']} -- not in data")
            continue
        build_one(cdata[ring["col"]], ring, out_dir, dpi=args.dpi, size_px=args.size_px)


if __name__ == "__main__":
    main()
