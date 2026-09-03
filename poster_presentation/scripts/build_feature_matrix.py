"""
Build the poster's feature-matrix heatmap: fabric Types (rows) x morphometric
characters (columns), one single combined figure, square cells, fully
horizontal row labels and fully vertical column labels (matches the source
paper's own "14.4 Feature matrices of clusters" style).

Reusable — rerun any time the underlying data changes, or tweak via the
CLI flags below instead of editing the script.

Usage:
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_feature_matrix.py
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_feature_matrix.py --level level_5 --cell-size 90
    .venv\\Scripts\\python.exe poster_presentation\\scripts\\build_feature_matrix.py --data-dir outputs_canada_cma_ca_nochm/09_hierarchy --out feature_matrix_nochm.png
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ground-truth column -> human-readable label, verified against
# notebooks_buidings/04_morphometrics.ipynb (exact momepy calls / renames)
# and the TO_DROP list in notebooks_buidings/09_clustering.ipynb.
# floor_count intentionally excluded (not an actually-used/validated feature).
LABELS = {
    "sdbAre": "area of building",
    "sdbPer": "perimeter of building",
    "sdbCoA": "courtyard area of building",
    "ssbCCo": "circular compactness of building",
    "ssbSqu": "squareness of building",
    "ssbERI": "equiv. rectangular index of building",
    "ssbElo": "elongation of building",
    "libNCo": "number of courtyards of adjacent buildings",
    "ldbPWL": "perimeter wall length of adjacent buildings",
    "ltcBuA": "building adjacency (tessellation neighbourhood)",
    "mtbAli": "alignment of neighbouring buildings",
    "mtbNDi": "mean distance to neighbouring buildings",
    "ltbIBD": "mean inter-building distance",
    "stbSAl": "street alignment of building",
    "mibCou": "connected buildings count",
    "mibAre": "connected buildings area",
    "mibLen": "connected buildings perimeter",
    "mibElo": "connected buildings elongation",
    "mibERI": "connected buildings equiv. rectangular index",
    "mibCCo": "connected buildings circular compactness",
    "mibLAL": "connected buildings longest axis length",
    "mibFR":  "connected buildings facade ratio",
    "mibSCo": "connected buildings square compactness",
    "sdcLAL": "longest axis length of tessellation cell",
    "sdcAre": "area of tessellation cell",
    "sscCCo": "circular compactness of tessellation cell",
    "sscERI": "equiv. rectangular index of tessellation cell",
    "mtcWNe": "weighted neighbours of tessellation cell",
    "mdcAre": "area covered by neighbouring cells",
    "sicCAR": "coverage area ratio (building / cell)",
    "micBAD": "building area deviation in tess. neighbourhood",
    "sdsLen": "length of street segment",
    "sssLin": "linearity of street segment",
    "ldsMSL": "mean segment length of street network (k=3)",
    "sisBpM": "buildings per metre of street segment",
    "sdsSPW": "width of street profile",
    "sdsSPO": "openness of street profile",
    "sdsSWD": "width deviation of street profile",
    "sdsAre": "area covered by street segment",
    "sddAre": "area covered by street node",
    "mtdMDi": "mean distance to neighbouring street nodes",
    "midRea": "reached cells by neighbouring nodes (k=1)",
    "midAre": "reached area by neighbouring nodes (k=1)",
    "lcdMes": "local meshedness of street network (k=5)",
    "ldsCDL": "cul-de-sac length of street network (k=3)",
    "lddNDe": "node density of street network (k=5)",
    "linWID": "weighted node density of street network (k=5)",
    "linPDE": "proportion of dead-ends (k=5)",
    "linP3W": "proportion of 3-way intersections (k=5)",
    "linP4W": "proportion of 4-way intersections (k=5)",
    "lcnClo": "local closeness centrality of street network (k=5)",
    "xcnSCl": "square clustering of street network",
    "midBAD": "building area deviation, node-attached buildings",
    "HEIGHT": "building height",
    "volume": "building volume",
    "chm_mean": "mean canopy height (Meta CHM v2)",
    "chm_std": "canopy height std.dev. (Meta CHM v2)",
    "chm_max": "max canopy height (Meta CHM v2)",
    "chm_cover": "canopy cover fraction (Meta CHM v2)",
    "limLPS": "likely occupied area (indicator)",
    "limAre": "area of largest connected structures",
}

# Genuinely Canada-only columns (not in the original European taxonomy).
# limLPS / limAre are NOT here -- they're part of the original paper's own
# "3 additional indicator variables" (other materials.pdf, section 10).
CANADA_ONLY = {"HEIGHT", "volume", "chm_mean", "chm_std", "chm_max", "chm_cover"}


def build(data_dir: Path, level: str, cell_size: int, out_path: Path, dpi: int = 300):
    cdata = pd.read_parquet(data_dir / "cdata.parquet")
    cmap_df = pd.read_parquet(data_dir / "cluster_mapping.parquet")
    df = cdata.join(cmap_df[[level]])

    cols = [c for c in LABELS if c in df.columns]
    print(f"{len(cols)} columns matched out of {len(LABELS)} labeled / {df.shape[1]} in data")

    agg = df.groupby(level)[cols].mean().sort_index()
    agg.index = [f"Cluster {i}" for i in agg.index]

    norm = (agg - agg.min()) / (agg.max() - agg.min())
    norm = norm.fillna(0.5)

    n_rows, n_cols = agg.shape

    # --- fully square cells ---
    cell = cell_size
    left_margin = 320
    right_margin = 140
    top_margin = 90
    # Vertical column labels need real height: longest label length drives it.
    # Empirical per-character vertical extent for rotated text at this font size.
    longest_label = max(len(LABELS[c]) for c in cols)
    label_fontsize = max(9, min(13, cell_size * 0.16))
    label_fontsize_px = label_fontsize * dpi / 72
    bottom_margin = int(longest_label * label_fontsize_px * 0.62) + 90

    fig_w = (left_margin + n_cols * cell + right_margin) / dpi
    fig_h = (top_margin + n_rows * cell + bottom_margin) / dpi

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    fig.subplots_adjust(
        left=left_margin / (fig_w * dpi),
        right=1 - right_margin / (fig_w * dpi),
        top=1 - top_margin / (fig_h * dpi),
        bottom=bottom_margin / (fig_h * dpi),
    )

    cmap = plt.cm.Greens
    im = ax.imshow(norm.values, cmap=cmap, aspect="equal", vmin=0, vmax=1)

    ax.set_xticks(range(n_cols))
    label_fontsize = max(9, min(13, cell_size * 0.16))
    ax.set_xticklabels(
        [LABELS[c] for c in cols], rotation=90, ha="center", va="top", fontsize=label_fontsize,
        color="black",
    )

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(agg.index, rotation=0, ha="right", fontsize=max(11, label_fontsize + 2), fontweight="bold")

    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(which="major", length=4)
    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar_ax = fig.add_axes([
        1 - (right_margin - 30) / (fig_w * dpi),
        1 - top_margin / (fig_h * dpi) - 0.28,
        0.014, 0.22,
    ])
    cb = fig.colorbar(im, cax=cbar_ax)
    cb.set_ticks([0, 0.5, 1])
    cb.set_ticklabels(["low", "middle", "high"])
    cb.ax.tick_params(labelsize=11)
    cb.outline.set_visible(False)

    ax.set_title(
        f"Feature matrix of the clusters ({level}) — Canada national urban taxonomy\n"
        "relative value per column (min–max across clusters); see feature_matrix_glossary.md for character definitions",
        fontsize=14, loc="left", pad=16,
    )

    fig.text(
        0.01, max(0.005, 12 / (fig_h * dpi)),
        "National production run: 152 CMAs/CAs · ~9.6M buildings · 58,684 morphotopes.  "
        "Streets: OpenStreetMap (Geofabrik Canada extract).  Canopy (chm_*): Meta CHM v2, aggregated in a buffer around each building.",
        fontsize=9, color="#555555",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", transparent=True)
    svg_path = out_path.with_suffix(".svg")
    fig.savefig(svg_path, bbox_inches="tight", transparent=True)
    pdf_path = out_path.with_suffix(".pdf")
    fig.savefig(pdf_path, bbox_inches="tight", transparent=True)
    print(f"saved {out_path}  ({fig.get_size_inches()[0]*dpi:.0f} x {fig.get_size_inches()[1]*dpi:.0f} px)")
    print(f"saved {svg_path} and {pdf_path}  (vector -- text stays crisp at any scale, PDF for Canva/Illustrator import)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default="outputs_canada_cma_ca/09_hierarchy",
                    help="Folder containing cdata.parquet + cluster_mapping.parquet")
    p.add_argument("--level", default="level_3",
                    help="cluster_mapping column to group by (level_1 .. level_7)")
    p.add_argument("--cell-size", type=int, default=280,
                    help="Square cell size in px at the given --dpi")
    p.add_argument("--dpi", type=int, default=400)
    p.add_argument("--out", default="poster_presentation/assets/figures/feature_matrix_full.png")
    args = p.parse_args()

    build(Path(args.data_dir), args.level, args.cell_size, Path(args.out), args.dpi)
